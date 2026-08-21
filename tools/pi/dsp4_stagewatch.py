#!/usr/bin/env python3
"""dsp4_stagewatch.py — read the DSP status-LED code over ssh.

diag.asm drives one green LED per SHARC (LD3 on DSPA/chip 1, LD2 on
DSPB/chip 2) with the boot stage: N flashes then a long gap = "stuck
after stage N" (diag.h DIAG_STAGE_*), and a steady 1 Hz 50% square =
DIAG_STAGE_RUNNING. That is the only instrument that can see inside
dma_cfg_init, because the SPI diagnostic link is not up until
DIAG_STAGE_WAITCFG(5) — downstream of everything the P2.2 bisect is
asking about.

The LED itself needs eyes at the card. A DSP4_BISECT build mirrors every
LED transition onto PB_05 (SPI2_RDY), which lands on the Pi as GPIO8 for
chip 1 and GPIO12 for chip 2, so this tool samples that pin and decodes
the same pattern with nobody at the bench. Against a production
(DSP4_BISECT=0) image there is no mirror and the pin will read flat —
that is not a verdict, it just means the instrument is not fitted.

  ./dsp4_stagewatch.py            # chip 1, 8 s
  ./dsp4_stagewatch.py --chip 2 --seconds 12 --raw

Sampling is a plain 1 kHz poll of one input line; it claims no other
line, drives nothing, and changes no pull, so it is safe to run while
anything else is going on.
"""
import argparse
import sys
import time

import gpiod
from gpiod.line import Direction

RDY_GPIO = {1: 8, 2: 12}          # CS3 / CS4 back from DSPA / DSPB

# diag.asm LED shape, in diag ticks (nominally 1 ms at CCLK 400 MHz):
#   fault stage N:  N * (150 on / 250 off) then 1200 off
#   running:        500 on / 500 off  -> 1 Hz square
FAULT_ON_MS, FAULT_INTER_MS, FAULT_GAP_MS = 150, 250, 1200
RUN_HALF_MS = 500


def sample(pin, seconds, hz):
    """Poll one line and return [(level, milliseconds), ...] run lengths."""
    chip = gpiod.Chip('/dev/gpiochip0')
    req = chip.request_lines(
        consumer='dsp4_stagewatch',
        config={pin: gpiod.LineSettings(direction=Direction.INPUT)})
    period = 1.0 / hz
    runs = []
    try:
        t_end = time.monotonic() + seconds
        cur = int(bool(req.get_value(pin).value))
        t_run = time.monotonic()
        nxt = t_run + period
        while True:
            now = time.monotonic()
            if now >= t_end:
                break
            v = int(bool(req.get_value(pin).value))
            if v != cur:
                runs.append((cur, (now - t_run) * 1000.0))
                cur, t_run = v, now
            slp = nxt - time.monotonic()
            if slp > 0:
                time.sleep(slp)
            nxt += period
        runs.append((cur, (time.monotonic() - t_run) * 1000.0))
    finally:
        req.release()
    return runs


def decode(runs):
    """Turn run lengths into a verdict string plus supporting numbers.

    Deliberately shape-based rather than absolute-time-based: the diag
    tick is derived from an assumed CCLK of 400 MHz which has never been
    measured on this card, so every interval may be off by one common
    factor. Ratios are not.
    """
    # Drop the first and last run: both are truncated by the window.
    body = runs[1:-1]
    if not body:
        if len(runs) > 1:
            # One clean transition and nothing else: the pin moved, so the
            # part is alive, but the window is too short to read a shape.
            return ('TOGGLING but only 1 transition — alive; sample longer '
                    'to read the pattern'), {'transitions': len(runs) - 1}
        flat = 'high' if runs[0][0] else 'low'
        return f'FLAT {flat} — no transitions in the window', {}
    if len(body) < 3:
        return (f'TOGGLING ({len(runs) - 1} transitions) — alive, but the '
                f'window is too short to read the pattern'), \
               {'transitions': len(runs) - 1}

    highs = [d for lvl, d in body if lvl]
    lows = [d for lvl, d in body if not lvl]
    if not highs or not lows:
        return 'FLAT — one level only', {}

    facts = {
        'transitions': len(body),
        'high_ms': f'{min(highs):.0f}..{max(highs):.0f}',
        'low_ms': f'{min(lows):.0f}..{max(lows):.0f}',
    }

    # Steady square: one low population, and it matches the high one.
    long_low, short_low = max(lows), min(lows)
    if long_low <= 2.0 * short_low:
        duty = sum(highs) / (sum(highs) + sum(lows))
        facts['duty'] = f'{duty:.2f}'
        if 0.35 <= duty <= 0.65:
            return ('STEADY SQUARE — DIAG_STAGE_RUNNING (7): the firmware '
                    'reached the end of this build\'s path'), facts
        return 'periodic but not 50% — unrecognised pattern', facts

    # Fault code: bursts of flashes separated by the long gap.
    gap_thresh = (long_low * short_low) ** 0.5     # geometric midpoint
    bursts, n = [], 0
    for lvl, d in body:
        if lvl:
            n += 1
        elif d >= gap_thresh:
            if n:
                bursts.append(n)
            n = 0
    if n:
        bursts.append(n)
    facts['bursts'] = bursts
    facts['gap_ms'] = f'{long_low:.0f}'
    if not bursts:
        return 'no complete burst in the window — sample longer', facts
    counts = set(bursts[1:-1]) or set(bursts)      # ends may be clipped
    if len(counts) != 1:
        return f'INCONSISTENT burst lengths {bursts}', facts
    stage = counts.pop()
    return (f'FAULT CODE {stage} flashes — stuck after DIAG stage {stage} '
            f'(diag.h DIAG_STAGE_*; a bisect build stamps its own 1..7 '
            f'inside dma_cfg_init)'), facts


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--chip', type=int, choices=(1, 2), default=1)
    ap.add_argument('--pin', type=int, help='override the GPIO to sample')
    ap.add_argument('--seconds', type=float, default=8.0)
    ap.add_argument('--hz', type=float, default=1000.0)
    ap.add_argument('--raw', action='store_true', help='print every run length')
    args = ap.parse_args()

    pin = args.pin if args.pin is not None else RDY_GPIO[args.chip]
    print(f'sampling GPIO{pin} (chip {args.chip}) for {args.seconds:g}s '
          f'at {args.hz:g} Hz')
    runs = sample(pin, args.seconds, args.hz)
    if args.raw:
        for lvl, d in runs:
            print(f'  {"hi" if lvl else "lo"} {d:8.1f} ms')
    verdict, facts = decode(runs)
    for k, v in facts.items():
        print(f'  {k}: {v}')
    print(f'VERDICT: {verdict}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
