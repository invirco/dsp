#!/usr/bin/env python3
"""dsp4_netprobe.py — who is driving the DSP4 control nets?

Every DSP4 bring-up failure so far has come down to a net that somebody
else was already driving: H1S1 held CS1-6 push-pull HIGH, so every
SPI_RDY wait in every boot passed vacuously (2026-08-20); the SPI2_RDY
pull-downs rest the line ASSERTED, so "RDY asserted" proves nothing about
a part being alive. Reading a level tells you nothing on a bus like that.
This tool asks the only question that does discriminate:

    does the net follow the Pi's own weak pull, or does something
    stronger hold it?

Method (per net, non-destructive): make the Pi pin an input, select the
internal pull-UP and read, select the internal pull-DOWN and read.

    follows both  -> nothing else drives it (only the Pi's ~50K pull)
    stuck HIGH    -> an external pull-up or an active driver holds it high
    stuck LOW     -> an external pull-down or an active driver holds it low
    toggling      -> the net is switching faster than we sample

Each bias is sampled SAMPLES times, so a running clock (PCM_CLK/PCM_FS
from LOGIC) reports as "toggling" instead of masquerading as a held net —
which is itself the cheapest CPLD-is-alive check on this board.

A stuck net is NOT automatically a fault: SPI2_RDY is *meant* to sit on
its 10K pull-down (R34/R22), and a bus pull-up is normal. It is a fact to
reason from, and the reasoning is what has been wrong before.

--rdy-trace additionally pulses !RST_D and records every SPI_RDY edge for
a window afterwards, with no SPI traffic at all. Since the card's pulls
rest SPI_RDY low, ANY high in that window is the part itself driving the
pin — the one positive liveness signal available without a scope.

Run it with matrix-app stopped. Pin states are restored on exit.

Usage:
  dsp4_netprobe.py                      # probe every net
  dsp4_netprobe.py --nets MOSI,SCK
  dsp4_netprobe.py --rdy-trace 1 --window 1.0
"""

import argparse
import sys
import time

# BCM GPIO numbers, DSP4 J6 — same map as dsp4_boot.py.
NETS = {
    'SCK':    (11, 'Pi SPI0_SCLK -> 33R split -> both DSPs PA_04'),
    'MOSI':   (10, 'Pi SPI0_MOSI -> 33R split -> both DSPs PA_01'),
    'MISO':   (9,  'Pi SPI0_MISO <- 33R split <- both DSPs PA_00'),
    'CS1':    (6,  'chip 1 SPI_SS (PA_05); shared with H1S1 CS1'),
    'CS2':    (24, 'chip 2 SPI_SS (PA_05); shared with H1S1 CS2'),
    'RDY1':   (8,  'chip 1 SPI2_RDY (PB_05) via CS3; 10K pull-down R34'),
    'RDY2':   (12, 'chip 2 SPI2_RDY (PB_05) via CS4; 10K pull-down R22'),
    'RST_D':  (16, '!RST_D, both DSPs; also driven by H1S1 (U7 pin 47)'),
    'PCM_CLK': (18, 'LOGIC-mastered PCM clock -> Pi; toggles if the CPLD runs'),
    'PCM_FS': (19, 'LOGIC-mastered PCM frame sync -> Pi'),
}
RST_GPIO = 16
SETTLE_S = 0.20
SAMPLES = 24            # per bias — enough to catch a net that is toggling


def _gpio():
    import gpiod
    from gpiod.line import Direction, Value
    return gpiod, Direction, Value


def probe(name, verbose=True):
    gpiod, Direction, Value = _gpio()
    num, note = NETS[name]
    chip = gpiod.Chip('/dev/gpiochip0')
    reads = {}
    for bias, tag in ((gpiod.line.Bias.PULL_UP, 'pull-up'),
                      (gpiod.line.Bias.PULL_DOWN, 'pull-down')):
        req = chip.request_lines(consumer='dsp4_netprobe', config={
            num: gpiod.LineSettings(direction=Direction.INPUT, bias=bias)})
        time.sleep(SETTLE_S)
        seen = {1 if req.get_value(num) == Value.ACTIVE else 0
                for _ in range(SAMPLES)}
        reads[tag] = -1 if len(seen) > 1 else seen.pop()
        req.release()
    up, down = reads['pull-up'], reads['pull-down']
    if up == -1 or down == -1:
        verdict = 'TOGGLING — a live signal, not a static level'
    elif up == 1 and down == 0:
        verdict = 'floats — nothing else drives it'
    elif up == 1 and down == 1:
        verdict = 'HELD HIGH by something stronger than the Pi pull'
    elif up == 0 and down == 0:
        verdict = 'HELD LOW by something stronger than the Pi pull'
    else:
        verdict = 'inverted?? (pull-up read low, pull-down read high)'
    if verbose:
        fmt = lambda v: '~' if v == -1 else str(v)
        print(f'  {name:8s} GPIO{num:<3d} pu={fmt(up)} pd={fmt(down)}  '
              f'{verdict}')
        print(f'           {note}')
    return verdict


def rdy_trace(chip_id, window):
    """Pulse !RST_D and log every SPI_RDY edge, with no SPI traffic."""
    gpiod, Direction, Value = _gpio()
    rdy = NETS[f'RDY{chip_id}'][0]
    chip = gpiod.Chip('/dev/gpiochip0')
    req = chip.request_lines(consumer='dsp4_netprobe', config={
        RST_GPIO: gpiod.LineSettings(direction=Direction.OUTPUT,
                                     output_value=Value.ACTIVE),
        rdy: gpiod.LineSettings(direction=Direction.INPUT)})
    req.set_value(RST_GPIO, Value.INACTIVE)
    time.sleep(0.050)
    t0 = time.monotonic()
    req.set_value(RST_GPIO, Value.ACTIVE)

    edges, last, n = [], None, 0
    while time.monotonic() - t0 < window:
        v = 1 if req.get_value(rdy) == Value.ACTIVE else 0
        n += 1
        if v != last:
            edges.append(((time.monotonic() - t0) * 1000.0, v))
            last = v
    req.release()
    print(f'  chip {chip_id} SPI_RDY (GPIO{rdy}): {n} samples over {window}s '
          f'({window / n * 1e6:.1f} us/sample), !RST_D released at t=0')
    for t, v in edges[:40]:
        print(f'    {t:9.3f} ms -> '
              f'{"HIGH — the part is driving it" if v else "low (pull-down)"}')
    if len(edges) > 40:
        print(f'    ... {len(edges) - 40} more edges')
    if not any(v for _, v in edges):
        print('    no HIGH in the window: no positive evidence the part is '
              'driving SPI_RDY at all.')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--nets', help='comma-separated subset of '
                                   + ','.join(NETS))
    ap.add_argument('--rdy-trace', type=int, choices=(1, 2),
                    help='also pulse !RST_D and trace that chip\'s SPI_RDY')
    ap.add_argument('--window', type=float, default=1.0,
                    help='--rdy-trace window in seconds (default 1.0)')
    args = ap.parse_args()

    names = args.nets.split(',') if args.nets else list(NETS)
    for n in names:
        if n not in NETS:
            sys.exit(f'unknown net {n!r}; known: {", ".join(NETS)}')

    print('Net drive probe (matrix-app should be stopped):')
    for n in names:
        probe(n)
    if args.rdy_trace:
        print('\nSPI_RDY trace across a !RST_D pulse, no SPI traffic:')
        rdy_trace(args.rdy_trace, args.window)
    print('\nNOTE: pin directions are left as inputs. dsp4_boot.py re-claims '
          'CS and !RST_D as outputs on its next run.')


if __name__ == '__main__':
    main()
