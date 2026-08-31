#!/usr/bin/env python3
"""dsp4_diag.py — read the DSP4 diagnostic register block from the Pi/CM4.

Rev C gives no emulator access to either SHARC (JTG_* floating on both
DSP sheets), so this tool and the per-chip LED are the debug channel.
The DSP side is MW/D32/DSP/SHARC/src/diag.asm; the register map is
src/diag.h and is mirrored below — keep the two in step.

READ PROTOCOL. The DSP's RX watermark interrupt only fires once both
words of a transaction have arrived, by which time the master has
already shifted MISO. A read therefore takes two transactions:

    1. {addr | READ, 0}    -> answer is queued in the DSP's TFIFO
    2. {DIAG_NOP, 0}       -> MISO carries {echo, value}

`echo` is word 0 of the request, verbatim, so every value returned here
is checked against the question that produced it. A mismatch means the
response pipeline has slipped and is reported rather than silently
believed — which is the whole point on a board with no other way to
tell a wrong answer from a right one.

Usage:
  dsp4_diag.py --chip 1 --cs-gpio 6 --rdy-gpio 8        # dump everything
  dsp4_diag.py --chip 1 --cs-gpio 6 --watch             # live, 1 Hz
  dsp4_diag.py --chip 1 --cs-gpio 6 --peek 0x31030040   # any MMR
  dsp4_diag.py --chip 1 --cs-gpio 6 --led on|off|auto
  dsp4_diag.py --chip 1 --cs-gpio 6 --clear             # zero the counters
  dsp4_diag.py --chip 1 --cs-gpio 6 --rate 2.0          # measure CCLK

Requires python3-spidev + python3-libgpiod on the Pi.
"""

import argparse
import os
import sys
import time

from dsp4_config import SpiLink, frame

try:
    import dsp4_bootlog
except ImportError:
    dsp4_bootlog = None

# Audio block size. Generated into dsp4_block.py by tools/dsp/dsp_codegen.py
# from the same BLOCK constant the firmware is built with, so the nominal
# block rate quoted here can never disagree with the image on the part.
try:
    from dsp4_block import BLOCK as _BLK
except ImportError:
    _BLK = None
BLOCK = int(os.environ.get('DSP4_BLOCK', _BLK if _BLK else 32))

READ_FLAG = 0x2000

# ---- register map, mirroring SHARC/src/diag.h -------------------------
DIAG_BASE = 0xE000
DIAG_PEEK_ADDR = 0xE0F0
DIAG_PEEK_DATA = 0xE0F1
DIAG_NOP = 0xE0FE
DIAG_CLEAR = 0xE0FF
DIAG_LED_MODE = 0xE011

# How many times read() will clock a single word to repair the answer
# phase before giving up. Each try costs one 4-byte transfer.
REALIGN_TRIES = 6

# How many collect transactions to clock before concluding the stream is
# out of phase rather than merely slow. The DSP polls this link from the
# block loop, so under load an answer can be a block or more away; each
# collect is ~64 us at 1 MHz, so 24 covers well over a millisecond.
COLLECT_TRIES = 24

MAGIC_VALUE = 0xD5B40001

# (addr, name, formatter)
HEX = 'hex'
DEC = 'dec'

REGISTERS = [
    (0xE000, 'MAGIC',         HEX),
    (0xE001, 'CHIP_ID',       DEC),
    (0xE002, 'BOOT_STAGE',    DEC),
    (0xE003, 'BOOT_CFG',      DEC),
    (0xE004, 'FRAME_COUNT',   DEC),
    (0xE005, 'TICKS',         DEC),
    (0xE006, 'SEC_COUNT',     DEC),
    (0xE007, 'LAST_CSID',     DEC),
    (0xE008, 'UNK_CSID',      DEC),
    (0xE009, 'UNK_COUNT',     DEC),
    (0xE00A, 'BLK_OVERRUN',   DEC),
    (0xE00B, 'SPI_RX_COUNT',  DEC),
    (0xE00C, 'SPI_ERR_COUNT', DEC),
    (0xE00D, 'SPI_STAT',      HEX),
    (0xE00E, 'SPI_STAT_STK',  HEX),
    (0xE00F, 'RESP_DROP',     DEC),
    (0xE010, 'PRODUCT_ID',    DEC),
    (0xE011, 'LED_MODE',      DEC),
    (0xE012, 'SPORT0_ERR_A',  HEX),
    (0xE013, 'DMA0_STAT',     HEX),
    (0xE014, 'SPI_CTL',       HEX),
    (0xE015, 'SPI_RXCTL',     HEX),
    (0xE016, 'SPI_TXCTL',     HEX),
    (0xE017, 'BUILD_ID',      HEX),
    # DSP4_CFG_WATCH block — reads 0 on an image built without it.
    (0xE019, 'CFG_PHASE',     DEC),
    (0xE01A, 'CGU_FAIL',      DEC),
    (0xE01B, 'CGU_IT1',       DEC),
    (0xE01C, 'CGU_IT2',       DEC),
    (0xE01D, 'CGU_IT3',       DEC),
    (0xE01E, 'CGU_IT4',       DEC),
    (0xE01F, 'SPI_PART_FIX',  DEC),
    (0xE020, 'SPI_PART_TICKS', DEC),
    (0xE021, 'SPI_PART_SEEN', DEC),
    (0xE022, 'SPI_PART_SKIP', DEC),
    (0xE023, 'SPI_REQ_WORD',  HEX),
]

BOOT_STAGES = {
    1: 'core + diag timer alive; stuck in _sru_init',
    2: 'SRU routed; stuck in _sport_cfg_init',
    3: 'half-SPORTs configured; stuck in _dma_cfg_init',
    4: 'DMA/SEC/SPI2 up; stuck enabling interrupts',
    5: 'waiting for host product config (no CONFIG_COMMIT yet)',
    6: 'configured; waiting for the first audio block',
    7: 'running',
}

SEC_SOURCES = {37: 'SPORT0_A_DMA (block clock)', 71: 'SPI2_STAT (param link)'}

# Bits worth naming when they turn up. HRM Table 15-32 / SPORT / DMA.
SPI_STAT_BITS = [
    (0x00000010, 'ROR  receive overrun'),
    (0x00000020, 'TUR  transmit underrun'),
    (0x00000040, 'TC   transmit collision'),
    (0x00000080, 'MF   mode fault'),
    (0x00100000, 'FCS  flow-control stall'),
    (0x20000000, 'MMRE memory-mapped read error'),
    (0x10000000, 'MMWE memory-mapped write error'),
    (0x80000000, 'MMAE memory-mapped access error'),
]

# What the SPI2 config SHOULD read back if dma_config.c took effect.
SPI_CTL_EXPECT = [
    (0x00000001, 'EN    enabled'),
    (0x00000400, 'SIZE  32-bit'),
    (0x00000100, 'EMISO slave drives MISO'),
    (0x00002000, 'FCEN  flow control on'),
    (0x00008000, 'FCPL  RDY active high'),
]
SPI_RXCTL_EXPECT = [
    (0x00000001, 'REN   receive enabled'),
    (0x00040000, 'RUWM  urgent watermark = full (NOT disabled)'),
]
SPI_TXCTL_EXPECT = [(0x00000001, 'TEN   transmit enabled')]


class DiagLink:
    """The host half of the parameter link, with an EXPLICIT answer phase.

    D74 (2026-08-31). The firmware answers every accepted transaction with
    two words, `echo` then `value`, and the master collects them on the
    transaction after the one that asked. What the master actually sees is
    a continuous word stream, and its 8-byte windows can sit on either of
    two offsets in it. Measured on the part, both occur:

        PRE   window = (value, echo)          <- the arrangement this file
                                                 has always assumed
        POST  window = (<previous value>, echo), and THIS request's value
              is word 0 of the NEXT window

    The echo lands in word 1 in BOTH, so the echo check — the only
    integrity mechanism the link has — passes either way. In POST it
    passes while handing back the value belonging to the PREVIOUS request,
    which in an ask/collect loop is the NOP's, and a NOP answers 0. That
    is the whole of "the link answers as CHIP 0", "MAGIC reads 0" and the
    all-zero register dumps taken off parts that were running perfectly:
    nothing was dropped and nothing was wedged, the answer was read one
    word away from where it lay. It is also what made the 2026-08-22
    stuck-partial recovery in `_diag_timer_isr` look load-bearing — its
    word discard is the only thing in the system that shifts this phase,
    which is why suppressing it (DSP4_SPI_PARTIAL_FIX2, the D71 fix) left
    the scope path stuck in POST for good.

    So the phase is CALIBRATED rather than assumed: DIAG_MAGIC is a
    compile-time constant, so one read of it says which arrangement is
    live, and every read after that is decoded with it. A decode that
    stops matching re-calibrates.

    RESIDUAL RISK, stated rather than hidden: a phase that flips PARTWAY
    through a session is decoded with the stale calibration and returns
    the previous request's value with no error, because the echo still
    matches. The only thing known to flip it is the timer ISR's word
    discard, which DSP4_SPI_PARTIAL_FIX2 keeps from firing while the host
    is polling — so under the shipping configuration a flip needs an idle
    gap. Reads that matter are still voted (Scope.rd), and a register with
    a known constant beside them (MAGIC travels with BOOT_STAGE in
    dump()) is what catches it. Re-calibrating per read would cost a
    transaction per read and was not measured to be necessary.
    """

    def __init__(self, link):
        self.link = link
        self.pending = None      # word0 of the request awaiting collection
        self.phase = None        # 'pre' | 'post', see the class docstring

    def calibrate(self, tries=8):
        """Decide which arrangement this link is in, against a constant.

        MAGIC is the only register whose value is known before it is read,
        which is exactly what a phase test needs: in PRE the window that
        carries the echo also carries 0xD5B40001, in POST the next window
        starts with it. Anything else is a link that is not answering at
        all, and that is reported as such rather than guessed at."""
        want0 = int.from_bytes(frame(0xE000, 0, read=True)[0:4], 'big')
        for _ in range(tries):
            self._fetch(0xE000, next_read=True)
            for _ in range(COLLECT_TRIES):
                w0, w1 = self._fetch()
                if w0 == want0 and w1 == MAGIC_VALUE:
                    self.phase = 'pre'      # aligned window, same handling
                    return self.phase
                if w1 == want0:
                    if w0 == MAGIC_VALUE:
                        self.phase = 'pre'
                        return self.phase
                    x0, _x1 = self._fetch()
                    if x0 == MAGIC_VALUE:
                        self.phase = 'post'
                        return self.phase
                    break
            self.link.realign()
        raise IOError('cannot phase the parameter link: MAGIC never came '
                      'back in either arrangement')

    def _value(self, w0, w1, want0):
        """Pull this request's value out of one collect window, or None."""
        if w0 == want0:
            return w1                      # (echo, value) in one window
        if w1 == want0:
            if self.phase == 'post':
                x0, _x1 = self._fetch()    # value leads the NEXT window
                return x0
            return w0                      # PRE: (value, echo)
        return None

    def _fetch(self, next_addr=None, next_read=False):
        """Clock one transaction; return the (echo, value) it collects."""
        if next_addr is None:
            next_addr, next_read = DIAG_NOP, False
        rx = self.link.xfer(next_addr, 0, read=next_read)
        echo = int.from_bytes(rx[0:4], 'big')
        value = int.from_bytes(rx[4:8], 'big')
        return echo, value

    def read(self, addr):
        """Read one diagnostic register, verifying the echoed request.

        The answer is two words, (echo, value), collected on the
        transaction after the one that asked, and the pair can arrive in
        either of the two arrangements described on the class.

        CORRECTED 2026-08-31 (D74). This used to say that trying both
        arrangements and letting the ECHO decide was safe, because "an
        answer is only accepted when the request word comes back
        verbatim, so a wrong guess cannot be mistaken for data". That is
        false, and it is the defect: the echo lands in word 1 in BOTH
        arrangements, so the echo check cannot separate them, and picking
        the wrong one returns the value of the PREVIOUS request. The
        arrangement is decided by calibrate(), not by the echo.
        """
        if self.phase is None:
            self.calibrate()
        want = frame(addr, 0, read=True)
        want0 = int.from_bytes(want[0:4], 'big')
        w0 = w1 = 0
        for attempt in range(REALIGN_TRIES):
            self._fetch(addr, next_read=True)      # ask
            # COLLECT PATIENTLY BEFORE ASSUMING A PHASE ERROR.
            #
            # The DSP services this link by polling, so an answer appears
            # only after the firmware next looks -- at worst one audio
            # block, ~667 us, and longer while the block loop is busy.
            # The host clocks its collect microseconds after the ask, so
            # "no echo yet" is the NORMAL case under load, not a phase
            # error. Realigning here would shift a stream that was never
            # out of step and turn a slow answer into a real fault; that
            # is what made a loaded but perfectly healthy card look dead.
            for _ in range(COLLECT_TRIES):
                w0, w1 = self._fetch()             # collect (sends NOP)
                v = self._value(w0, w1, want0)
                if v is not None:
                    return v
            # Still nothing after waiting. NOW treat it as a lost answer
            # leaving master and slave a word apart -- see
            # SpiLink.realign -- and re-ask. The phase goes with it: a
            # realign moves the window, so the calibration is stale.
            self.link.realign()
            self.phase = None
            self.calibrate()
        raise IOError(
            f'response out of step reading 0x{addr:04X} after '
            f'{REALIGN_TRIES} realign attempts of {COLLECT_TRIES} collects: '
            f'got 0x{w0:08X} 0x{w1:08X}, neither is the echo '
            f'0x{want0:08X}. Check RESP_DROP.')

    def resync(self):
        """Drain any answer left queued by an interrupted earlier run, then
        establish the answer phase (see the class docstring). Draining
        alone was never enough: it clears the queue but says nothing about
        which of the two arrangements the window lands on."""
        for _ in range(3):
            self._fetch()
        self.phase = None
        self.calibrate()

    def write(self, addr, value):
        self.link.write(addr, value)

    def peek(self, mmr):
        self.write(DIAG_PEEK_ADDR, mmr)
        return self.read(DIAG_PEEK_DATA)


def decode_bits(value, table):
    return [name for bit, name in table if value & bit]


def missing_bits(value, table):
    return [name for bit, name in table if not value & bit]


def dump(diag, verbose=True):
    vals = {}
    for addr, name, _fmt in REGISTERS:
        vals[name] = diag.read(addr)

    magic = vals['MAGIC']
    # One line per dump, MAGIC and BOOT_STAGE together (dsp4_bootlog.py).
    # They have to travel together: the read protocol's echo check accepts
    # a DROPPED answer, which comes back as a well-formed (echo, 0), so a
    # BOOT_STAGE of 0 read on its own does not distinguish a wedged part
    # from a lost answer. MAGIC is a constant compiled into the image — if
    # it reads back, the part is answering and the stage beside it is real.
    if dsp4_bootlog is not None:
        dsp4_bootlog.log(chip=vals.get('CHIP_ID', ''),
                         ok=int(magic == MAGIC_VALUE),
                         magic=f'0x{magic:08X}',
                         stage=vals.get('BOOT_STAGE', ''),
                         note='dump')
    print(f'  {"MAGIC":<14} 0x{magic:08X}'
          + ('' if magic == MAGIC_VALUE else
             f'   <-- expected 0x{MAGIC_VALUE:08X}: this is NOT diag firmware'))
    if magic != MAGIC_VALUE:
        print('\n  Everything below is meaningless until MAGIC reads back.')
        return vals

    for addr, name, fmt in REGISTERS:
        if name == 'MAGIC':
            continue
        v = vals[name]
        shown = f'0x{v:08X}' if fmt == HEX else f'{v}'
        note = ''
        if name == 'BOOT_STAGE':
            note = '   ' + BOOT_STAGES.get(v, 'unknown stage')
        elif name == 'LAST_CSID':
            note = '   ' + SEC_SOURCES.get(v, 'unrecognised source')
        elif name == 'BUILD_ID':
            note = f'   ({v >> 16:04X}-{(v >> 8) & 0xFF:02X}-{v & 0xFF:02X})'
        elif name == 'CHIP_ID':
            note = '   (DSPA/U6)' if v == 1 else '   (DSPB/U5)' if v == 2 else '   (?)'
        print(f'  {name:<14} {shown}{note}')

    if not verbose:
        return vals

    print()
    problems = []

    if vals['FRAME_COUNT'] == 0:
        problems.append('FRAME_COUNT is 0 — no audio block has ever arrived. '
                        'The LOGIC CPLD sources DSP_CLK and the frame sync; '
                        'an unprogrammed CPLD looks exactly like this.')
    if vals['SEC_COUNT'] == 0:
        problems.append('SEC_COUNT is 0 — the SEC has never raised an '
                        'interrupt. Nothing peripheral is reaching the core.')
    if vals['UNK_COUNT']:
        problems.append(f'UNK_COUNT = {vals["UNK_COUNT"]}, last source '
                        f'{vals["UNK_CSID"]} — a SEC source is routed to the '
                        'core with no handler behind it.')
    if vals['BLK_OVERRUN']:
        problems.append(f'BLK_OVERRUN = {vals["BLK_OVERRUN"]} — the main loop '
                        'missed that many blocks; audio was dropped.')
    if vals['SPI_ERR_COUNT']:
        problems.append(f'SPI_ERR_COUNT = {vals["SPI_ERR_COUNT"]} — writes to '
                        'unmapped parameter addresses.')
    if vals['RESP_DROP']:
        problems.append(f'RESP_DROP = {vals["RESP_DROP"]} — read responses '
                        'discarded because the TFIFO was still occupied.')

    stuck = decode_bits(vals['SPI_STAT_STK'], SPI_STAT_BITS)
    if stuck:
        problems.append('SPI_STAT sticky bits: ' + '; '.join(stuck))
    for reg, table in (('SPI_CTL', SPI_CTL_EXPECT),
                       ('SPI_RXCTL', SPI_RXCTL_EXPECT),
                       ('SPI_TXCTL', SPI_TXCTL_EXPECT)):
        absent = missing_bits(vals[reg], table)
        if absent:
            problems.append(f'{reg} 0x{vals[reg]:08X} is missing: '
                            + '; '.join(absent))
    if vals['SPORT0_ERR_A']:
        problems.append(f'SPORT0_ERR_A = 0x{vals["SPORT0_ERR_A"]:08X} — the '
                        'block-clock lane has latched a framing or '
                        'overflow error.')

    if problems:
        print('  ISSUES')
        for p in problems:
            print(f'    - {p}')
    else:
        print('  No issues flagged.')
    return vals


def measure_rate(diag, seconds):
    """Turn DIAG_TICKS into a core-clock measurement.

    The diag timer counts CCLK cycles (DIAG_TPERIOD per tick), so the
    observed tick rate against wall clock IS the core clock, divided by
    DIAG_TPERIOD. This is the measurement the blink note in tasks.md asks
    for, without having to count LED flashes by eye.
    """
    t0 = time.monotonic()
    a_ticks, a_frames = diag.read(0xE005), diag.read(0xE004)
    time.sleep(seconds)
    b_ticks, b_frames = diag.read(0xE005), diag.read(0xE004)
    dt = time.monotonic() - t0

    tick_hz = (b_ticks - a_ticks) / dt
    frame_hz = (b_frames - a_frames) / dt
    print(f'  interval        {dt:.3f} s')
    print(f'  diag ticks      {b_ticks - a_ticks}  ->  {tick_hz:.1f} Hz '
          f'(nominal 1000 Hz at CCLK = 400 MHz)')
    print(f'  implied CCLK    {tick_hz * 400000 / 1e6:.2f} MHz')
    print(f'  audio blocks    {b_frames - a_frames}  ->  {frame_hz:.1f} Hz '
          f'(nominal {48000 // BLOCK} Hz = 48 kHz / {BLOCK})')
    if frame_hz > 0:
        print(f'  implied Fs      {frame_hz * BLOCK / 1000:.3f} kHz')


LED_MODES = {'auto': 0, 'off': 1, 'on': 2}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--chip', type=int, choices=(1, 2), default=1)
    ap.add_argument('--dev', default='0.0', help='spidev bus.device')
    ap.add_argument('--speed', type=int, default=1_000_000)
    ap.add_argument('--cs-gpio', type=int,
                    help='BCM GPIO driving CS (chip 1 = 6, chip 2 = 7)')
    ap.add_argument('--rdy-gpio', type=int,
                    help='BCM GPIO carrying SPI_RDY (chip 1 = 8, chip 2 = 12)')
    ap.add_argument('--rdy-active-low', action='store_true')
    ap.add_argument('--resync', action='store_true',
                    help='drain stale responses before reading')
    ap.add_argument('--watch', action='store_true',
                    help='re-dump once a second until interrupted')
    ap.add_argument('--peek', help='read one MMR/DM address (hex or dec)')
    ap.add_argument('--led', choices=sorted(LED_MODES),
                    help='override the status LED')
    ap.add_argument('--clear', action='store_true',
                    help='zero the counters and sticky latches')
    ap.add_argument('--rate', type=float, metavar='SECONDS',
                    help='measure the tick and block rates over SECONDS')
    args = ap.parse_args()

    if args.cs_gpio is None:
        # CS1 -> GPIO6, CS2 -> GPIO24. NOT GPIO7: that was wrong
        # from the start and is why chip 2 answered all-zero on
        # MISO while chip 1 worked - the tool was asserting a chip
        # select DSPB does not listen on. dsp4_boot.py has had the
        # right map all along (CS_GPIO = {1: 6, 2: 24}); these two
        # tools disagreed with it.
        args.cs_gpio = 6 if args.chip == 1 else 24

    link = SpiLink(args.dev, args.speed, args.cs_gpio,
                   rdy_gpio=args.rdy_gpio,
                   rdy_active_low=args.rdy_active_low)
    diag = DiagLink(link)

    if args.resync:
        diag.resync()

    try:
        if args.clear:
            diag.write(DIAG_CLEAR, 1)
            print('counters cleared')
        if args.led:
            diag.write(DIAG_LED_MODE, LED_MODES[args.led])
            print(f'LED mode -> {args.led}')
        if args.peek:
            mmr = int(args.peek, 0)
            print(f'  0x{mmr:08X} = 0x{diag.peek(mmr):08X}')
            return
        if args.rate:
            measure_rate(diag, args.rate)
            return
        if args.clear or args.led:
            return

        if args.watch:
            while True:
                print(f'=== chip {args.chip} @ {time.strftime("%H:%M:%S")} ===')
                dump(diag)
                print()
                time.sleep(1.0)
        else:
            print(f'=== DSP4 chip {args.chip} diagnostics ===')
            dump(diag)
    except KeyboardInterrupt:
        pass
    except IOError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main() or 0)
