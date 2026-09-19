#!/usr/bin/env python3
"""codec4619.py -- write AK4619 registers on a D24 through H1S1's matrix-bus cells (S69).

THE GAIN OF THE TALKBACK INPUT IS NOT A 595 CODE. The talkback XLR (J1) lands on the
AK4619's IN4 -> MIC Gain Amp 2 Rch -> ADC2 Rch, and that amp's gain is MGN2R[3:0] in the
codec's own register 05H -- twelve codes, -6 .. +27 dB in 3 dB steps (datasheet Table 9).
The mic-pre 595 chain does not reach it. PW's ruling 2026-09-19 was "use h1s1 to get the
test spec, and we'll add a dedicated CS6 wire later", so until that wire exists the only
master on the codec's SPI is H1S1, and this tool drives it through two matrix cells the
app does not use:

    Sys001Test001 (5414, 0x1526 -> "imjn")  the register address
    Sys001Test002 (5415, 0x1527 -> "imjo")  the data byte -- WRITING IT TRIGGERS THE WRITE

H1S1's `CodecPoll()` (S69) sees RXF set on the second cell and sends
`{0xC3, 0x00, reg, val}` -- command 0xC3 = write, 16-bit address, one data byte
(datasheet 9.12 Table 27 / 9.13). Register 0xFF is not a codec register and means
"re-run StartAK4619()".

TWO MASTERS ON ONE SET OF WIRES. hspi1 shares SCK/MOSI copper with the CM4's SPI0 (the
rev-D two-master wiring; the 2026-08-21 change removed H1S1's periodic writes for exactly
this reason). A codec write must not coincide with CM4 SPI0 traffic, so every caller
pauses its own DSP link around the write -- this tool simply does not touch SPI, and
--settle (default 60 ms) holds the bus quiet afterwards. Do not run it concurrently with
a DSP link tool in another process.

The matrix bus is MH1's, not ours: lines are newline-terminated (the app's
`serialPort1.WriteLine`), address nibbles are the letters 'h'..'w' = 0..F and data nibbles
'0'..'9','A'..'F'. `--run` sends S_RUN first, which is what MH1 needs after it has been
left in its flash dispatcher; `--reset` sends S_RESET twice first and RE-RUNS H1S1's
MainInit -- which pulses RST_C, re-loads the codec init image AND CLEARS THE 595 CHAIN,
so anything that cares about the mic-pre image must restore it afterwards.

  codec4619.py --reg 05 --val B2            reg 05H := 0xB2 (MGN2L +27 dB, MGN2R 0 dB)
  codec4619.py --mgn2r 5                    MGN2R code 5 only, MGN2L left at its current value
  codec4619.py --reinit                     re-run StartAK4619() on the part
  codec4619.py --test                       S_TEST: print the MCUs' test lines
"""
import argparse
import os
import sys
import termios
import time

PORT = '/dev/serial0'
AX = 'hijklmnopqrstuvw'          # address nibble alphabet (0..F)
DX = '0123456789ABCDEF'          # data nibble alphabet
SYS001TEST001 = 0x1526           # 5414 -- the register address cell
SYS001TEST002 = 0x1527           # 5415 -- the data cell; writing it triggers the write

# MIC Gain AMP setting, datasheet Table 9. Twelve codes; 0xC..0xF are not defined.
MGN_DB = {0: -6.0, 1: -3.0, 2: 0.0, 3: 3.0, 4: 6.0, 5: 9.0, 6: 12.0,
          7: 15.0, 8: 18.0, 9: 21.0, 10: 24.0, 11: 27.0}
# The init image H1S1's StartAK4619() writes, registers 00H..14H (matrix.cs `ak4619[]`).
INIT_IMAGE = [0x37, 0xAC, 0x10, 0x00, 0xBB, 0xBB, 0x30, 0x30, 0x30, 0x30, 0x00,
              0x00, 0x00, 0x00, 0x18, 0x18, 0x18, 0x18, 0x04, 0x05, 0x0A]


def cell_line(addr, data):
    """One matrix-bus line: address nibbles as letters, data nibbles as hex, newline.

    Only the nibbles a cell actually needs are sent -- H1S1's Poll() emits the same
    shape -- but sending all four address nibbles is always legal and is what the app
    does for a 16-bit address, so that is what this writes."""
    s = ''.join(AX[(addr >> sh) & 0xF] for sh in (12, 8, 4, 0))
    if data > 0xF:
        s += DX[(data >> 4) & 0xF]
    s += DX[data & 0xF]
    return (s + '\n').encode()


class Bus:
    """The MX bus over /dev/serial0, 115200 8N1, opened raw.

    pyserial is NOT installed on the bench, so the port is configured through termios
    directly. Reads are non-blocking and drained on a timer: MH1 emits a steady '.'/':'
    heartbeat when it is idle, so "no reply" has to be distinguished from "no traffic"
    by what the line CONTAINS, never by whether anything arrived."""

    def __init__(self, port=PORT):
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        a = termios.tcgetattr(self.fd)
        a[4] = a[5] = termios.B115200
        a[2] = ((a[2] & ~termios.CSIZE & ~termios.PARENB & ~termios.CSTOPB)
                | termios.CS8 | termios.CREAD | termios.CLOCAL)
        a[0] = a[1] = a[3] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, a)
        termios.tcflush(self.fd, termios.TCIOFLUSH)

    def close(self):
        os.close(self.fd)

    def read(self, secs):
        out, t0 = b'', time.time()
        while time.time() - t0 < secs:
            try:
                out += os.read(self.fd, 512)
            except BlockingIOError:
                time.sleep(0.02)
        return out

    def send(self, raw, settle=0.0):
        os.write(self.fd, raw)
        if settle:
            time.sleep(settle)

    def run(self):
        """S_RUN. MH1 answers '// resuming normal operation' about 43 ms later."""
        self.send(b'+\n')
        return self.read(1.5)

    def reset(self):
        """S_RESET, twice as Boot.cs sends it. EVERY bus device re-runs its init --
        H1S1 pulses RST_C, re-writes the codec image and CLEARS THE 595 CHAIN."""
        self.send(b'*\n', 0.2)
        self.send(b'*\n', 2.0)
        return self.read(1.5)

    def test(self):
        self.send(b'&\n')
        return self.read(3.0)

    def write_reg(self, reg, val, settle=0.06):
        """Address cell first, then the data cell -- the second one triggers the write.

        H1S1 stores the address cell without acting and acts on the data cell, so the
        order is not a convention, it is the mechanism. `settle` holds the bus quiet
        afterwards: SpiTx blocks in H1S1's main loop and shares copper with CM4 SPI0."""
        self.send(cell_line(SYS001TEST001, reg), 0.05)
        self.send(cell_line(SYS001TEST002, val), settle)


def decode(image=None):
    """Decode a register image (00H..14H) against the map in datasheet 9.14."""
    r = list(image or INIT_IMAGE)
    # Table 2 is indexed by (TDM, DCF) TOGETHER -- the SAME DCF code names a different
    # format in each half of the table, so a decode that reads DCF alone is wrong.
    # DCF=010 with TDM=0 is not a listed mode at all; with TDM=1 it is TDM256 I2S.
    fmt = {(0, 0): 'Stereo I2S compatible', (0, 5): 'Stereo MSB justified',
           (0, 6): 'Stereo PCM short frame', (0, 7): 'Stereo PCM long frame',
           (1, 2): 'TDM256 I2S compatible', (1, 7): 'TDM256 MSB justified'}
    # TDM128 shares DCF 010/111 with TDM256 and is separated by BICK (128fs vs 256fs),
    # which is a board fact and not in any register, so the name carries both.
    dsl = {0: '24-bit slot', 1: '20-bit slot', 2: '16-bit slot', 3: '32-bit slot'}
    out = []
    out.append('00H %02X  Power: PMAD2=%d PMAD1=%d PMDA2=%d PMDA1=%d RSTN=%d'
               % (r[0], (r[0] >> 5) & 1, (r[0] >> 4) & 1, (r[0] >> 2) & 1,
                  (r[0] >> 1) & 1, r[0] & 1))
    _tdm, _dcf = (r[1] >> 7) & 1, (r[1] >> 4) & 7
    out.append('01H %02X  Audio I/F: TDM=%d DCF=%d -> %s; DSL=%d (%s) BCKP=%d (%s) SDOPH=%d'
               % (r[1], _tdm, _dcf,
                  fmt.get((_tdm, _dcf), 'NOT A LISTED MODE (Table 2)'),
                  (r[1] >> 2) & 3, dsl[(r[1] >> 2) & 3], (r[1] >> 1) & 1,
                  'BICK falling edge' if not ((r[1] >> 1) & 1) else 'BICK rising edge',
                  r[1] & 1))
    wl_in = {0: '24-bit', 1: '20-bit', 2: '16-bit', 3: '32-bit'}
    wl_out = {0: '24-bit', 1: '20-bit', 2: '16-bit', 3: 'N/A'}
    out.append('02H %02X  Audio I/F: SLOT=%d (%s) DIDL=%d (SDIN %s) DODL=%d (SDOUT %s)'
               % (r[2], (r[2] >> 4) & 1,
                  'slot-length basis' if (r[2] >> 4) & 1 else 'LRCK edge basis',
                  (r[2] >> 2) & 3, wl_in[(r[2] >> 2) & 3], r[2] & 3, wl_out[r[2] & 3]))
    out.append('03H %02X  System clock: FS=%d' % (r[3], r[3] & 7))
    for i, name in ((4, '1'), (5, '2')):
        hi, lo = (r[i] >> 4) & 0xF, r[i] & 0xF
        out.append('%02XH %02X  MIC gain: MGN%sL=%X (%s dB)  MGN%sR=%X (%s dB)'
                   % (i, r[i], name, hi, MGN_DB.get(hi, '??'),
                      name, lo, MGN_DB.get(lo, '??')))
    for i, name in ((6, 'ADC1 L'), (7, 'ADC1 R'), (8, 'ADC2 L'), (9, 'ADC2 R')):
        out.append('%02XH %02X  %s digital volume (%s)'
                   % (i, r[i], name, voladc_db(r[i])))
    out.append('0AH %02X  ADC digital filter: AD2VO=%d AD2SD=%d AD2SL=%d AD1VO=%d AD1SD=%d AD1SL=%d'
               % (r[10], (r[10] >> 6) & 1, (r[10] >> 5) & 1, (r[10] >> 4) & 1,
                  (r[10] >> 2) & 1, (r[10] >> 1) & 1, r[10] & 1))
    sel = {0: 'differential', 1: 'single-ended Ain1', 2: 'single-ended Ain2',
           3: 'pseudo-differential'}
    out.append('0BH %02X  ADC analog input: AD1L=%s AD1R=%s AD2L=%s AD2R=%s'
               % (r[11], sel[(r[11] >> 6) & 3], sel[(r[11] >> 4) & 3],
                  sel[(r[11] >> 2) & 3], sel[r[11] & 3]))
    out.append('0DH %02X  ADC mute/HPF: ATSPAD=%d AD2MUTE=%d AD1MUTE=%d AD2HPFN=%d AD1HPFN=%d'
               % (r[13], (r[13] >> 7) & 1, (r[13] >> 6) & 1, (r[13] >> 5) & 1,
                  (r[13] >> 2) & 1, (r[13] >> 1) & 1))
    for i, name in ((14, 'DAC1 L'), (15, 'DAC1 R'), (16, 'DAC2 L'), (17, 'DAC2 R')):
        out.append('%02XH %02X  %s digital volume' % (i, r[i], name))
    out.append('12H %02X  DAC input select: DAC2SEL=%d DAC1SEL=%d'
               % (r[18], (r[18] >> 2) & 3, r[18] & 3))
    out.append('13H %02X  DAC de-emphasis: DEM2=%d DEM1=%d'
               % (r[19], (r[19] >> 2) & 3, r[19] & 3))
    out.append('14H %02X  DAC mute/filter: ATSPDA=%d DA2MUTE=%d DA1MUTE=%d DA2SD=%d DA2SL=%d DA1SD=%d DA1SL=%d'
               % (r[20], (r[20] >> 7) & 1, (r[20] >> 5) & 1, (r[20] >> 4) & 1,
                  (r[20] >> 3) & 1, (r[20] >> 2) & 1, (r[20] >> 1) & 1, r[20] & 1))
    return '\n'.join(out)


def voladc_db(code):
    """ADC digital volume, datasheet Tables 11/14.

    THE LAW RUNS THE OTHER WAY FROM THE OBVIOUS GUESS, and getting it backwards makes a
    measurement unreadable rather than merely wrong: the column is ATTENUATION, so a
    HIGHER code is QUIETER. 0x00 = +24.0 dB, 0x30 = 0.0 dB (default), 0xFF = mute, half
    a dB a step. 0x00 is the loudest setting, NOT mute. Measured on the part 2026-09-19
    (S69): writing 0x00 to 06H/08H/09H raised the matching TDM slot by 24.1/24.2/24.2 dB."""
    if code == 0xFF:
        return 'MUTE'
    return '%+.1f dB' % ((0x30 - code) * 0.5)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--reg', help='register address, hex (e.g. 05)')
    ap.add_argument('--val', help='data byte, hex (e.g. B2)')
    ap.add_argument('--mgn2r', type=int, help='MGN2R code 0..11 (-6..+27 dB), 05H low nibble')
    ap.add_argument('--mgn2l', type=int, help='MGN2L code 0..11, 05H high nibble')
    ap.add_argument('--reinit', action='store_true', help='re-run StartAK4619() (reg 0xFF)')
    ap.add_argument('--run', action='store_true', help='send S_RUN first')
    ap.add_argument('--reset', action='store_true',
                    help='send S_RESET first -- RE-INITS EVERY MCU and clears the 595 chain')
    ap.add_argument('--test', action='store_true', help='send S_TEST and print the replies')
    ap.add_argument('--decode', action='store_true', help='decode the init image and exit')
    ap.add_argument('--settle', type=float, default=0.06,
                    help='seconds to hold the bus quiet after the write (default 0.06)')
    ap.add_argument('--port', default=PORT)
    a = ap.parse_args()

    if a.decode:
        print(decode())
        return 0

    b = Bus(a.port)
    try:
        if a.reset:
            print('S_RESET ->', b.reset())
        if a.run or a.reset:
            print('S_RUN   ->', b.run())
        if a.test:
            print('S_TEST  ->', b.test())

        if a.reinit:
            b.write_reg(0xFF, 0x00, a.settle)
            print('re-init: StartAK4619() requested (reg 0xFF)')
            return 0

        if a.mgn2r is not None or a.mgn2l is not None:
            # 05H is one byte for both channels and the codec cannot be read back through
            # this path, so a caller that sets one nibble has to say what the other is.
            # The default is the init image's +27 dB, which is what the part comes up at.
            hi = a.mgn2l if a.mgn2l is not None else 0xB
            lo = a.mgn2r if a.mgn2r is not None else 0xB
            for n, v in (('mgn2l', hi), ('mgn2r', lo)):
                if not 0 <= v <= 11:
                    sys.exit('%s: code %d is outside 0..11 (Table 9 defines twelve)' % (n, v))
            reg, val = 0x05, (hi << 4) | lo
            print('05H := 0x%02X  MGN2L=%X (%+g dB)  MGN2R=%X (%+g dB)'
                  % (val, hi, MGN_DB[hi], lo, MGN_DB[lo]))
        elif a.reg is not None and a.val is not None:
            reg, val = int(a.reg, 16), int(a.val, 16)
            print('%02XH := 0x%02X' % (reg, val))
        else:
            if not (a.test or a.run or a.reset):
                ap.error('give --reg/--val, --mgn2r/--mgn2l, --reinit, --test or --decode')
            return 0

        b.write_reg(reg, val, a.settle)
    finally:
        b.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
