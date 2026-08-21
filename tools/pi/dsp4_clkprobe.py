#!/usr/bin/env python3
"""dsp4_clkprobe.py — decode the clkprobe frame on PB_05.

src/blink/clkprobe.asm times everything off the SHARC core timer, which
decrements once per CCLK cycle, and reports on the one wire that leaves
the card (SPI2_RDY -> Pi GPIO8 for chip 1, GPIO12 for chip 2). One
"tick" is TICK_CYCLES core-clock cycles, so measuring a tick measures
CCLK — no assumption about how many cycles an instruction takes, which
is what made the blink-rate estimate unusable.

Frame shape (see the asm for the authoritative description):
  phase A  3 * (1 tick high, 1 tick low), 8 ticks low
  phase B  5 words: the constant 0xA5C3F00D then CGU0_CTL, CGU0_DIV,
           CGU0_STAT, CGU0_DIVEX. Word = 8 high / 4 low header, then 32
           bits MSB first, bit 0 = 1 tick high, bit 1 = 3 ticks high,
           each followed by 1 tick low
  phase C  6 periods of SQ_TICKS high / SQ_TICKS low
  phase D  2 more words (PORTB_DATA, DAI0_DAT0)
  phase E  6 more periods, then the transcript repeats from phase B

Words are reported in order. A short transcript is itself the result:
the phase the DSP stopped in says which read did not return.

  ./dsp4_clkprobe.py --chip 1 --seconds 40

Sampling uses gpiod edge events, so run lengths are kernel-timestamped
rather than polled. The line is claimed as an input only; it drives
nothing and changes no pull, but the pin is handed back to its ALT
function (pinctrl a0) on exit because spidev does not do that itself.
"""
import argparse
import subprocess
import sys
import time

import gpiod
from gpiod.line import Direction, Edge

RDY_GPIO = {1: 8, 2: 12}

TICK_CYCLES = 2000000     # keep in step with clkprobe.asm
SQ_TICKS = 32
MAGIC = 0xA5C3F00D
FRAMES = {
    'clk': ['MAGIC', 'CGU0_CTL', 'CGU0_DIV', 'CGU0_STAT', 'CGU0_DIVEX',
            'PORTB_DATA', 'DAI0_DAT0'],
    'sru': ['DAI0_DAT0', 'DAI0_CLK0', 'DAI0_PIN0'],
}


def sample(pin, seconds):
    """Return [(level, milliseconds), ...] run lengths, edge-timestamped."""
    chip = gpiod.Chip('/dev/gpiochip0')
    req = chip.request_lines(
        consumer='dsp4_clkprobe',
        config={pin: gpiod.LineSettings(direction=Direction.INPUT,
                                        edge_detection=Edge.BOTH)})
    runs = []
    try:
        level = int(bool(req.get_value(pin).value))
        t_prev = None
        t_end = time.monotonic() + seconds
        while True:
            left = t_end - time.monotonic()
            if left <= 0:
                break
            if not req.wait_edge_events(left):
                continue
            for ev in req.read_edge_events():
                t = ev.timestamp_ns / 1e6
                if t_prev is not None:
                    runs.append((level, t - t_prev))
                t_prev = t
                level = 1 if ev.event_type == ev.Type.RISING_EDGE else 0
    finally:
        req.release()
    return runs


def find_unit(runs):
    """The 1-tick run length, in ms.

    Every bit contributes a 1-tick low and half the bits a 1-tick high,
    so 1-tick runs are always the shortest and always the most common.
    """
    d = sorted(r[1] for r in runs)
    if not d:
        return None
    floor = d[0]
    short = [x for x in d if x <= 1.6 * floor]
    return short[len(short) // 2]


def q(ms, unit):
    return int(round(ms / unit))


def bursts(runs, unit):
    """Lengths of the runs of 1-tick pulses.

    sruprobe emits one 1-tick pulse per completed SRU write, so a burst
    length IS a count of operations that returned. Reported in order, so
    [3, 36] reads as "alive marker, then all 36 DAI0 writes".
    """
    out, n = [], 0
    for i in range(0, len(runs) - 1):
        lvl, ms = runs[i]
        nxt = runs[i + 1]
        if lvl == 1 and q(ms, unit) <= 1 and nxt[0] == 0:
            n += 1
        elif lvl == 1:
            if n:
                out.append(n)
            n = 0
    if n:
        out.append(n)
    return out


def rle(runs, unit):
    """Compact the transcript to 'HI n x k' / 'lo n x k' lines."""
    out, prev, count = [], None, 0
    for lvl, ms in runs:
        key = ('HI' if lvl else 'lo', q(ms, unit))
        if key == prev:
            count += 1
            continue
        if prev is not None:
            out.append(f"{prev[0]} {prev[1]:>3d}" +
                       (f"  x{count}" if count > 1 else ""))
        prev, count = key, 1
    if prev is not None:
        out.append(f"{prev[0]} {prev[1]:>3d}" +
                   (f"  x{count}" if count > 1 else ""))
    return out


def decode(runs, unit):
    """Pull the 32-bit words out of the run list, in order."""
    ticks = [(lvl, q(ms, unit), ms) for lvl, ms in runs]
    words, squares, i = [], [], 0
    while i < len(ticks) - 1:
        lvl, n, _ = ticks[i]
        if lvl == 1 and 6 <= n <= 10 and ticks[i + 1][0] == 0 \
                and 3 <= ticks[i + 1][1] <= 5:
            bits, j, ok = 0, i + 2, True
            for _ in range(32):
                if j + 1 >= len(ticks):
                    ok = False
                    break
                hi, lo = ticks[j], ticks[j + 1]
                if hi[0] != 1 or lo[0] != 0:
                    ok = False
                    break
                if hi[1] <= 1:
                    bits = (bits << 1)
                elif 2 <= hi[1] <= 4:
                    bits = (bits << 1) | 1
                else:
                    ok = False
                    break
                j += 2
            if ok:
                words.append(bits)
                i = j
                continue
        if lvl == 1 and abs(n - SQ_TICKS) <= SQ_TICKS // 4:
            squares.append(ticks[i][2])
        i += 1
    return words, squares


def align(words):
    """Drop everything before the first MAGIC, so a capture that started
    mid-transcript still lines its words up with WORD_NAMES."""
    for i, w in enumerate(words):
        if w == MAGIC:
            return words[i:]
    return words


def cclk_from(unit_ms, squares):
    """CCLK in Hz, from the tick unit and (if present) the square wave."""
    out = {}
    if unit_ms:
        out['unit'] = TICK_CYCLES / (unit_ms / 1000.0)
    if squares:
        med = sorted(squares)[len(squares) // 2]
        out['square'] = (SQ_TICKS * TICK_CYCLES) / (med / 1000.0)
    return out


def report_cgu(words, clkin_hz):
    """Turn CGU0_CTL/CGU0_DIV into the clock tree they describe."""
    if len(words) < 2:
        return
    if words[0] != MAGIC or len(words) < 3:
        return
    ctl, div = words[1], words[2]
    df = ctl & 1
    msel = (ctl >> 8) & 0x7F
    msel = 128 if msel == 0 else msel
    csel = div & 0x1F
    csel = 32 if csel == 0 else csel
    syssel = (div >> 8) & 0x1F
    syssel = 32 if syssel == 0 else syssel
    s0sel = (div >> 5) & 0x7
    s0sel = 8 if s0sel == 0 else s0sel
    s1sel = (div >> 13) & 0x7
    s1sel = 8 if s1sel == 0 else s1sel
    # PLLCLK = SYS_CLKIN / (DF+1) * MSEL / 2 — the /2 is part of the
    # 2156x PLL path (HRM Tables 2-10/2-11; dsp4-architecture-decisions.md
    # D10), and leaving it out is what makes the arithmetic come out an
    # octave high. The measured CCLK above is the check on this.
    pll = clkin_hz / (df + 1) * msel / 2
    print(f"  DF={df} MSEL={msel} CSEL={csel} SYSSEL={syssel} "
          f"S0SEL={s0sel} S1SEL={s1sel}")
    print(f"  with SYS_CLKIN0 = {clkin_hz/1e6:.3f} MHz:")
    print(f"    PLLCLK  = {pll/1e6:9.3f} MHz")
    print(f"    CCLK    = {pll/csel/1e6:9.3f} MHz")
    print(f"    SYSCLK  = {pll/syssel/1e6:9.3f} MHz")
    print(f"    SCLK0   = {pll/syssel/s0sel/1e6:9.3f} MHz")
    print(f"    SCLK1   = {pll/syssel/s1sel/1e6:9.3f} MHz")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--chip', type=int, choices=(1, 2), default=1)
    ap.add_argument('--pin', type=int, help='override the GPIO to sample')
    ap.add_argument('--seconds', type=float, default=40.0)
    ap.add_argument('--clkin', type=float, default=24.576e6,
                    help='SYS_CLKIN0 in Hz for the derived-frequency table')
    ap.add_argument('--frame', choices=sorted(FRAMES), default='clk',
                    help='which probe image is running (clkprobe or sruprobe)')
    ap.add_argument('--rle', action='store_true',
                    help='print the whole transcript run-length encoded in '
                         'ticks — the readable form for a progress-pulse '
                         'image such as sruprobe')
    ap.add_argument('--raw', action='store_true')
    args = ap.parse_args()

    names = FRAMES[args.frame]
    pin = args.pin if args.pin is not None else RDY_GPIO[args.chip]
    runs = sample(pin, args.seconds)
    subprocess.run(['pinctrl', 'set', str(pin), 'a0'],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    if len(runs) < 4:
        print(f"chip {args.chip}: GPIO{pin} flat ({len(runs)} edges in "
              f"{args.seconds:.0f} s) — the image is not running, or it "
              f"stalled before phase A")
        return 1

    unit = find_unit(runs)
    words, squares = decode(runs, unit)
    if args.frame == 'clk':
        frames = words.count(MAGIC)
        words = align(words)[:len(names)]
    else:
        frames = None
        words = words[:len(names)]

    if args.raw:
        for lvl, ms in runs:
            print(f"    {'HI' if lvl else 'lo'} {ms:8.2f} ms  "
                  f"{ms/unit:6.2f} ticks")

    print(f"chip {args.chip} (GPIO{pin}): {len(runs)} edges, "
          f"tick = {unit:.2f} ms")
    freqs = cclk_from(unit, squares)
    for k, v in freqs.items():
        print(f"  CCLK from {k:6s} = {v/1e6:8.3f} MHz")

    print(f"  1-tick pulse bursts: {bursts(runs, unit)}")
    if args.rle:
        print("  transcript (ticks, run-length encoded, first 120 runs):")
        for line in rle(runs, unit)[:120]:
            print(f"    {line}")
    if frames is not None:
        print(f"  frames seen: {frames}; words in the first frame: "
              f"{len(words)} of {len(names)}")
    else:
        print(f"  words decoded: {len(words)} of {len(names)}")
    for i, w in enumerate(words):
        name = names[i] if i < len(names) else f'word{i}'
        note = '  (expected 0xA5C3F00D)' if name == 'MAGIC' and w != MAGIC else ''
        print(f"    {name:<11s} = 0x{w:08X}{note}")
    if args.frame == 'clk':
        if words and words[0] != MAGIC:
            print("  WARNING: no MAGIC word — frame alignment is not trusted")
        report_cgu(words, args.clkin)
    if len(words) < len(names):
        missing = names[len(words):]
        print(f"  DID NOT RETURN: {', '.join(missing)} — the read of "
              f"{missing[0]} is where the core stopped")
    return 0


if __name__ == '__main__':
    sys.exit(main())
