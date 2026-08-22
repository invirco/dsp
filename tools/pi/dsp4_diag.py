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
import sys
import time

from dsp4_config import SpiLink, frame

READ_FLAG = 0x2000

# ---- register map, mirroring SHARC/src/diag.h -------------------------
DIAG_BASE = 0xE000
DIAG_PEEK_ADDR = 0xE0F0
DIAG_PEEK_DATA = 0xE0F1
DIAG_NOP = 0xE0FE
DIAG_CLEAR = 0xE0FF
DIAG_LED_MODE = 0xE011

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
    def __init__(self, link):
        self.link = link
        self.pending = None      # word0 of the request awaiting collection

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

        The collect transaction repeats the SAME read rather than sending
        a DIAG_NOP. The DSP queues its two-word answer for the master's
        NEXT transaction, and on the bench (2026-08-22) a run of
        back-to-back real reads pipelines perfectly - each transaction
        carries the previous request's echo and value - while inserting a
        NOP to collect slips the stream by one word, because a NOP queues
        no answer and the 2-deep SPI_TFIFO is left holding a partial pair.
        Asking twice costs one extra transaction and keeps the FIFO
        always carrying whole pairs. The second ask leaves one answer
        outstanding, which the next read's first transaction discards.
        """
        want = frame(addr, 0, read=True)
        want0 = int.from_bytes(want[0:4], 'big')
        self._fetch(addr, next_read=True)          # ask; collects stale
        echo, value = self._fetch(addr, next_read=True)   # ask again; collect
        # Bounded self-resync. WORKAROUND, not a fix: a transaction that
        # produces NO response - a register write, or DIAG_NOP - still
        # clocks two words out of the 2-deep SPI_TFIFO, so mixing writes
        # and reads slips the stream by one word and every later echo is
        # a value. The real fix is on the DSP side: make every accepted
        # transaction queue exactly one two-word answer (a write echoing
        # its request with value 0), so the stream is aligned by
        # construction. Until then, re-ask until the echo matches.
        for _ in range(3):
            if echo == want0:
                return value
            echo, value = self._fetch(addr, next_read=True)
        if echo != want0:
            raise IOError(
                f'response out of step reading 0x{addr:04X}: '
                f'echo 0x{echo:08X}, expected 0x{want0:08X}. '
                'Check RESP_DROP, and re-run with --resync.')
        return value

    def resync(self):
        """Drain any answer left queued by an interrupted earlier run."""
        for _ in range(3):
            self._fetch()

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
          f'(nominal 1500 Hz = 48 kHz / 32)')
    if frame_hz > 0:
        print(f'  implied Fs      {frame_hz * 32 / 1000:.3f} kHz')


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
