#!/usr/bin/env python3
"""dsp4_busmon.py — passive capture of the DSP4 boot bus while a boot runs.

The question this answers is the one every "boot reported OK" line has
begged since 2026-08-19: **is the Pi actually clocking the DSP?**

`dsp4_netprobe.py` cannot answer it. Its method (bias the pin up, bias it
down, read) claims the line with gpiod, which takes SCK/MOSI *away* from
the SPI0 peripheral and would break the very transfer we want to watch —
so netprobe can only ever report the bus at rest, where it reads
"MOSI/SCK HELD HIGH" because that is what an idle SPI0 output looks like.
A held-high static read is not evidence of a dead bus and never was.

This tool instead reads GPLEV0 through /dev/gpiomem and touches nothing:
no line is claimed, no function select is changed, no pull is altered. It
is a pure observer, so it can run concurrently with (or, with --exec,
around) a real `dsp4_boot.py` run.

What you get and what it is worth:

  * The sampler is a Python loop at roughly 1 MSa/s against a 1 MHz SPI
    clock, so it ALIASES. It cannot show you a waveform and it cannot
    count SCK cycles. It can tell you, unambiguously, whether a net was
    STATIC or ACTIVE across the boot — which is the discriminator we
    need. Waveform work is the scope's job; the scope-point map is in
    dsp4-revC-liveness-checklist.md §2.
  * Levels are read at the Pi end of the harness. "SCK active here"
    proves the host peripheral clocked; it does not prove the edges
    reached PA_04 on the part. That last hop is the R52/R51 (DSPA) and
    R19/R18 (DSPB) pads, with a probe on them.

Reading the verdicts:

  ACTIVE ... during the CS-asserted window
      The Pi drove real traffic at the DSP. If SPI_RDY still never
      deasserts and GPIO8/GPIO12 stay flat, the part is being given
      clock, data and reset and is not responding — that points at the
      parts (or at what is between the pad and the die), not at the host.
  STATIC high ... during the CS-asserted window
      The Pi never clocked anything, whatever dsp4_boot.py reported.
      That is a host-side fault — driver, spidev binding, pin mux, or
      another master on the net — and it is a different class of problem
      entirely.

Usage:
  dsp4_busmon.py --exec 'python3 dsp4_boot.py --ldr rdyprobe1.ldr --chip 1'
  dsp4_busmon.py --window 3.0            # observe only, e.g. under a boot loop
  dsp4_busmon.py --nets SCK,MOSI,RST_D --window 1.0
"""

import argparse
import mmap
import os
import struct
import subprocess
import sys
import time

# BCM2711 GPIO block; /dev/gpiomem maps it at offset 0 for the gpio group.
GPLEV0 = 0x34
MAP_LEN = 0x1000

# BCM GPIO numbers, DSP4 J6 — same map as dsp4_boot.py / dsp4_netprobe.py,
# with the 0.1" header pin so a probe can be clipped on without a netlist.
NETS = {
    'SCK':     (11, 'J6 pin 23', 'Pi SPI0_SCLK -> 33R -> both DSPs PA_04'),
    'MOSI':    (10, 'J6 pin 19', 'Pi SPI0_MOSI -> 33R -> both DSPs PA_01'),
    'MISO':    (9,  'J6 pin 21', 'Pi SPI0_MISO <- 33R <- both DSPs PA_00'),
    'CS1':     (6,  'J6 pin 31', 'chip 1 SPI_SS (PA_05), active low'),
    'CS2':     (24, 'J6 pin 18', 'chip 2 SPI_SS (PA_05), active low'),
    'RDY1':    (8,  'J6 pin 24', 'chip 1 SPI2_RDY (PB_05); 10K pull-down R34'),
    'RDY2':    (12, 'J6 pin 32', 'chip 2 SPI2_RDY (PB_05); 10K pull-down R22'),
    'RST_D':   (16, 'J6 pin 36', '!RST_D, both DSPs; U7 p47 also drives it'),
    'PCM_CLK': (18, 'J6 pin 12', 'LOGIC-mastered PCM clock -> Pi'),
    'PCM_FS':  (19, 'J6 pin 35', 'LOGIC-mastered PCM frame sync -> Pi'),
}

DEFAULT_NETS = ['SCK', 'MOSI', 'MISO', 'CS1', 'CS2', 'RDY1', 'RDY2', 'RST_D']
DEFAULT_WINDOW = 2.5
TIME_CHECK_MASK = 0x3FF     # check the clock every 1024 samples, not every one


def capture(mask, window, max_samples, exec_cmd=None):
    """Sample GPLEV0 as fast as CPython manages, for `window` seconds.

    Returns (rle, n, rate, proc_result) where rle is [(masked_value,
    run_length), ...]. Run-length encoding is what makes the analysis
    affordable: a static net collapses to one entry, and an active one
    only costs entries while it is actually switching.
    """
    from array import array

    fd = os.open('/dev/gpiomem', os.O_RDONLY)
    try:
        mm = mmap.mmap(fd, MAP_LEN, mmap.MAP_SHARED, mmap.PROT_READ)
    finally:
        os.close(fd)

    n_max = max_samples
    buf = array('I', bytes(4 * n_max))
    unpack = struct.Struct('<I').unpack_from
    monotonic = time.monotonic

    proc = None
    if exec_cmd:
        proc = subprocess.Popen(exec_cmd, shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True)

    i = 0
    t0 = monotonic()
    deadline = t0 + window
    while i < n_max:
        buf[i] = unpack(mm, GPLEV0)[0]
        i += 1
        if not (i & TIME_CHECK_MASK) and monotonic() > deadline:
            break
    t1 = monotonic()
    mm.close()

    out = None
    if proc is not None:
        out = proc.communicate()[0]
        out = (proc.returncode, out)

    n = i
    rate = n / (t1 - t0) if t1 > t0 else 0.0

    rle = []
    append = rle.append
    prev = buf[0] & mask
    run = 1
    for k in range(1, n):
        v = buf[k] & mask
        if v == prev:
            run += 1
        else:
            append((prev, run))
            prev, run = v, 1
    append((prev, run))
    return rle, n, rate, out


def slice_rle(rle, start, stop):
    """Sub-range of an RLE by absolute sample index [start, stop)."""
    out, pos = [], 0
    for value, run in rle:
        lo, hi = pos, pos + run
        pos = hi
        if hi <= start:
            continue
        if lo >= stop:
            break
        out.append((value, min(hi, stop) - max(lo, start)))
    return out


def net_stats(rle, bit):
    """(samples, high, low, transitions) for one bit of an RLE."""
    total = high = trans = 0
    prev = None
    for value, run in rle:
        v = (value >> bit) & 1
        total += run
        if v:
            high += run
        if prev is not None and v != prev:
            trans += 1
        prev = v
    return total, high, total - high, trans


def find_window(rle, bit, want=0):
    """First and last sample index where `bit` reads `want`; None if never."""
    pos, first, last = 0, None, None
    for value, run in rle:
        if ((value >> bit) & 1) == want:
            if first is None:
                first = pos
            last = pos + run
        pos += run
    return None if first is None else (first, last)


def transitions(rle, bit):
    """Sample indices at which `bit` changes, plus its initial value."""
    pos, prev, out = 0, None, []
    for value, run in rle:
        v = (value >> bit) & 1
        if prev is None:
            first = v
        elif v != prev:
            out.append(pos)
        prev = v
        pos += run
    return first, out


def intervals(rle, bit, want=0):
    """Maximal [start, stop) ranges where `bit` reads `want`."""
    pos, out, open_at = 0, [], None
    for value, run in rle:
        v = (value >> bit) & 1
        if v == want and open_at is None:
            open_at = pos
        elif v != want and open_at is not None:
            out.append((open_at, pos))
            open_at = None
        pos += run
    if open_at is not None:
        out.append((open_at, pos))
    return out


def clusters(positions, gap):
    """Group transition indices into bursts separated by >= `gap` samples."""
    out = []
    for p in positions:
        if out and p - out[-1][1] < gap:
            out[-1][1], out[-1][2] = p, out[-1][2] + 1
        else:
            out.append([p, p, 1])
    return [tuple(c) for c in out]


def verdict(total, high, trans):
    if total == 0:
        return 'no samples'
    if trans == 0:
        return f'STATIC {"high" if high else "low"}'
    return (f'ACTIVE — {trans} observed transitions, '
            f'{100.0 * high / total:.0f}% high')


def report(title, rle, names, rate):
    print(f'\n{title}')
    print(f'  {"net":8s} {"gpio":5s} {"header":10s} {"samples":>9s} '
          f'{"high":>9s} {"low":>9s}  verdict')
    for name in names:
        bit, hdr, _note = NETS[name]
        total, high, low, trans = net_stats(rle, bit)
        print(f'  {name:8s} {bit:<5d} {hdr:10s} {total:9d} {high:9d} '
              f'{low:9d}  {verdict(total, high, trans)}')
    if rate:
        print(f'  (sample interval ~{1e6 / rate:.2f} us; this sampler aliases '
              f'a 1 MHz clock — it shows activity, not waveform)')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--nets', help='comma-separated subset of '
                                   + ','.join(NETS))
    ap.add_argument('--window', type=float, default=DEFAULT_WINDOW,
                    help=f'capture seconds (default {DEFAULT_WINDOW})')
    ap.add_argument('--exec', dest='exec_cmd',
                    help='shell command to run under the capture (typically '
                         'a dsp4_boot.py invocation); its output is printed '
                         'after the capture so the two line up')
    ap.add_argument('--chip', type=int, choices=(1, 2), default=1,
                    help='which CS delimits the boot window (default 1)')
    ap.add_argument('--max-samples', type=int, default=4_000_000,
                    help='hard cap on samples (memory: 4 bytes each)')
    args = ap.parse_args()

    names = args.nets.split(',') if args.nets else list(DEFAULT_NETS)
    for name in names:
        if name not in NETS:
            sys.exit(f'unknown net {name!r}; known: {", ".join(NETS)}')
    for extra in (f'CS{args.chip}', 'RST_D'):
        if extra not in names:
            names.append(extra)

    mask = 0
    for name in names:
        mask |= 1 << NETS[name][0]

    print(f'Passive GPLEV0 capture, {args.window:.1f} s window'
          + (f', running: {args.exec_cmd}' if args.exec_cmd else '')
          + '\nNo line is claimed and no pull is changed — SPI0 keeps the '
            'pins throughout.')

    rle, n, rate, out = capture(mask, args.window, args.max_samples,
                                args.exec_cmd)
    print(f'\n{n} samples in {args.window:.1f} s '
          f'({rate / 1e6:.2f} MSa/s, ~{1e6 / rate:.2f} us/sample)'
          if rate else f'\n{n} samples')

    if out is not None:
        rc, text = out
        print(f'\n--- boot command (exit {rc}) ---')
        print((text or '').rstrip() or '  (no output)')
        print('--- end boot command ---')

    report('WHOLE CAPTURE:', rle, names, rate)

    ms = (lambda i: i / rate * 1e3) if rate else (lambda i: 0.0)

    print('\nEDGE TIMELINE (slow nets, t=0 at the start of the capture):')
    slow = [n for n in ('RST_D', f'CS{args.chip}', f'RDY{args.chip}')
            if n in names]
    events = []
    for name in slow:
        bit = NETS[name][0]
        first, pos = transitions(rle, bit)
        print(f'  {name} starts {"high" if first else "low"}'
              + ('' if pos else '  (never changes)'))
        level = first
        for p in pos:
            level ^= 1
            events.append((p, name, level))
    for p, name, level in sorted(events)[:60]:
        print(f'    {ms(p):9.2f} ms  {name:6s} -> {"high" if level else "low"}')
    if len(events) > 60:
        print(f'    ... {len(events) - 60} more edges')

    # A 1 MHz SPI burst produces transitions at least every couple of
    # samples; anything quieter than 1 ms apart is a separate burst.
    gap = max(int(rate * 1e-3), 2) if rate else 2
    for name in ('SCK', 'MOSI'):
        if name not in names:
            continue
        _first, pos = transitions(rle, NETS[name][0])
        cl = clusters(pos, gap)
        print(f'\n{name} (GPIO{NETS[name][0]}) activity: {len(pos)} '
              f'transitions in {len(cl)} burst(s)')
        for start, stop, count in cl[:10]:
            print(f'    {ms(start):9.2f} .. {ms(stop):9.2f} ms  '
                  f'({ms(stop - start):7.2f} ms)  {count} transitions')
        if len(cl) > 10:
            print(f'    ... {len(cl) - 10} more bursts')
        if not pos:
            print('    NONE — this net never moved. The Pi did not drive it.')

    cs_bit = NETS[f'CS{args.chip}'][0]
    sck_first, sck_pos = transitions(rle, NETS['SCK'][0]) if 'SCK' in names \
        else (0, [])
    print(f'\nCS{args.chip}-ASSERTED WINDOWS (GPIO{cs_bit} low):')
    windows = intervals(rle, cs_bit, want=0)
    if not windows:
        print(f'  none — CS{args.chip} never went low, so no part was ever '
              f'selected in this capture.')
    for start, stop in windows:
        inside = sum(1 for p in sck_pos if start <= p < stop)
        print(f'  {ms(start):9.2f} .. {ms(stop):9.2f} ms '
              f'({ms(stop - start):8.2f} ms): {inside} SCK transitions inside')
        if inside:
            report(f'  within this window:', slice_rle(rle, start, stop),
                   names, rate)

    rst = intervals(rle, NETS['RST_D'][0], want=0)
    if not rst:
        print('\n!RST_D never went low in this capture (--no-reset, or the '
              'reset fell outside the window).')
    for start, stop in rst:
        print(f'\n!RST_D low {ms(start):.2f} .. {ms(stop):.2f} ms '
              f'({ms(stop - start):.1f} ms) — the Pi end of the net did reach '
              f'0. Whether pin 104 does is checklist step 3, at the pad, with '
              f'a scope.')


if __name__ == '__main__':
    main()
