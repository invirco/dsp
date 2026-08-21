#!/usr/bin/env python3
"""dsp4_scopedrive.py — steady square waves on the boot bus, for a scope.

A boot is a 1 kB burst that is over in about eight milliseconds and then
does not repeat. That is awkward to catch and useless for judging a
LEVEL. This drives the same three nets as plain push-pull GPIO outputs,
continuously, at scope-friendly rates, so a probe can be clipped on and
left there.

The test it exists for: `dsp4_netprobe.py` reports SCK and MOSI as "HELD
HIGH by something stronger than the Pi pull". That is a statement about a
~50 K internal pull, and it proves nothing on its own — but if the Pi
drives the net PUSH-PULL at J6 and the DSP-side pad still does not swing,
then something between the header and the part is holding the net, and no
boot stream has ever reached the die. That is a break/contention fault,
and it is a different animal from a dead part.

Each net gets its OWN frequency, so a single probe identifies which pin it
is sitting on without moving anything else:

    SCK   GPIO11  J6 pin 23   1 kHz     DSP-side pad: R52.2 (DSPA) / R19.2 (DSPB)
    MOSI  GPIO10  J6 pin 19   500 Hz    DSP-side pad: R51.2 (DSPA) / R18.2 (DSPB)
    RST_D GPIO16  J6 pin 36   250 Hz    SYS_HWRST, p104

Expect a full 0 V / 3.3 V swing at J6. At the DSP-side pad, expect the
same swing minus the drop across the 33 R (negligible into a CMOS input).
Anything that will not leave the rail is the answer to this investigation.

Two things to know before running it:

  * GPIO10/11 normally belong to spidev (ALT0). This claims them as GPIO,
    so no boot can run while it does. `--restore` (and the wrapper's
    `stop`) puts them back to ALT0 — nothing else does, not even a
    matrix-app restart, because the pinmux is applied once at probe time.
  * GPIO16 is !RST_D and resets BOTH DSPs. Driving it at 250 Hz holds the
    parts in a permanent reset-release cycle. That is intended here and
    harmless, but it means the DSPs are not running while this runs.

Usage:
  dsp4_scopedrive.py                       # drive until Ctrl-C / SIGTERM
  dsp4_scopedrive.py --pins SCK,MOSI       # leave the DSPs out of reset
  dsp4_scopedrive.py --freq 2000 --seconds 60
  dsp4_scopedrive.py --restore             # give the pins back, drive nothing
  dsp4_scopedrive.py --hold RST_D=0        # hold one pin at a DC level

--hold is the DMM version of the same test, and it is the easier one to
trust: a static level can be measured at both ends of a net with a meter,
where a square wave has to be caught on a scope and believed. Hold
!RST_D low, then measure at J6 pin 36 AND at SYS_HWRST (p104) on U5/U6.
If the Pi end is at 0 V and the card end is at 3.3 V, the net is open
between them and neither SHARC has ever been reset by the host.
"""

import argparse
import mmap
import os
import signal
import struct
import subprocess
import sys
import time

GPLEV0 = 0x34
MAP_LEN = 0x1000

# name -> (bcm gpio, J6 header pin, divider on the base tick, note)
PINS = {
    'SCK':   (11, 'J6 pin 23', 1, 'SPI2_CLK -> PA_04; DSP pad R52.2 / R19.2'),
    'MOSI':  (10, 'J6 pin 19', 2, 'SPI2_MOSI -> PA_01; DSP pad R51.2 / R18.2'),
    'RST_D': (16, 'J6 pin 36', 4, 'SYS_HWRST p104, both DSPs, active low'),
}
DEFAULT_PINS = ['SCK', 'MOSI', 'RST_D']

# Restore state: what each pin must look like for normal operation.
#   GPIO9/10/11 = ALT0 (SPI0), which is how the DT overlay leaves them at
#   boot and how spidev expects to find them. GPIO16 = output, high
#   (!RST_D deasserted) — dsp4_boot.py re-claims it anyway.
RESTORE = [('9', 'a0'), ('10', 'a0'), ('11', 'a0'), ('16', 'op dh')]


def restore_pins(verbose=True):
    for gpio, mode in RESTORE:
        subprocess.run(['pinctrl', 'set', gpio] + mode.split(), check=False)
    if verbose:
        out = subprocess.run(['pinctrl', 'get', '9,10,11,16'],
                             capture_output=True, text=True).stdout
        print('pins restored (SPI0 = ALT0, !RST_D = output high):')
        print(out.rstrip())


class Readback:
    """Pad-level sampler that runs alongside the drive loop.

    Driving a pin and reading it back is not a tautology on this board:
    the read is of the PAD, so a net clamped by another driver shows up
    as a pin that will not follow its own output register. One GPLEV0
    read per tick costs about a microsecond, so it is taken inline —
    sampling in a separate burst would only ever see the level held
    between two edges.
    """

    def __init__(self, gpios):
        fd = os.open('/dev/gpiomem', os.O_RDONLY)
        try:
            self._mm = mmap.mmap(fd, MAP_LEN, mmap.MAP_SHARED, mmap.PROT_READ)
        finally:
            os.close(fd)
        self._unpack = struct.Struct('<I').unpack_from
        self._gpios = gpios
        self.reset()

    def reset(self):
        self.seen = {g: set() for g in self._gpios}

    def sample(self):
        w = self._unpack(self._mm, GPLEV0)[0]
        for g in self._gpios:
            self.seen[g].add((w >> g) & 1)

    def verdicts(self):
        return {g: ('follows 0/1' if len(v) > 1 else
                    f'STUCK {"high" if 1 in v else "low"}'
                    if v else 'no samples')
                for g, v in self.seen.items()}

    def close(self):
        self._mm.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--pins', default=','.join(DEFAULT_PINS),
                    help='comma-separated subset of ' + ','.join(PINS))
    ap.add_argument('--freq', type=float, default=1000.0,
                    help='SCK frequency in Hz (default 1000); MOSI runs at '
                         'half of it and RST_D at a quarter, so the scope '
                         'tells you which pin you are on')
    ap.add_argument('--seconds', type=float, default=0.0,
                    help='stop after this long (default 0 = until stopped)')
    ap.add_argument('--report-every', type=float, default=10.0,
                    help='seconds between Pi-side readback lines')
    ap.add_argument('--hold',
                    help='hold pins at DC instead of driving a square wave, '
                         'e.g. --hold RST_D=0 or --hold SCK=1,MOSI=0. Runs '
                         'until stopped; the pins are restored on exit.')
    ap.add_argument('--restore', action='store_true',
                    help='restore the pins to SPI0/reset-deasserted and exit')
    args = ap.parse_args()

    if args.restore:
        restore_pins()
        return

    names = [n.strip() for n in args.pins.split(',') if n.strip()]
    for n in names:
        if n not in PINS:
            sys.exit(f'unknown pin {n!r}; known: {", ".join(PINS)}')

    import gpiod
    from gpiod.line import Direction, Value

    if args.hold:
        held = {}
        for item in args.hold.split(','):
            name, _, want = item.partition('=')
            name = name.strip()
            if name not in PINS:
                sys.exit(f'unknown pin {name!r}; known: {", ".join(PINS)}')
            held[name] = 1 if want.strip() not in ('0', 'low', 'lo') else 0
        req = gpiod.request_lines(
            '/dev/gpiochip0', consumer='dsp4_scopedrive',
            config={PINS[n][0]: gpiod.LineSettings(
                direction=Direction.OUTPUT,
                output_value=Value.ACTIVE if v else Value.INACTIVE)
                for n, v in held.items()})
        rb = Readback([PINS[n][0] for n in held])
        for n, v in held.items():
            gpio, hdr, _div, note = PINS[n]
            print(f'holding {n} (GPIO{gpio}, {hdr}) '
                  f'{"HIGH ~3.3 V" if v else "LOW ~0 V"}  —  {note}')
        print('  measure at the header AND at the part; a DC level needs only '
              'a meter.\n  Stop with: dsp4_scopedrive.sh stop')
        stop = {'now': False}
        signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__('now', True))
        signal.signal(signal.SIGINT, lambda *_: stop.__setitem__('now', True))
        try:
            while not stop['now']:
                rb.reset()
                end = time.monotonic() + args.report_every
                while time.monotonic() < end and not stop['now']:
                    rb.sample()
                    time.sleep(0.001)
                parts = []
                for n, want in held.items():
                    got = rb.seen[PINS[n][0]]
                    if got == {want}:
                        parts.append(f'{n} reads back '
                                     f'{"high" if want else "low"} as driven')
                    elif len(got) > 1:
                        parts.append(f'{n} UNSTABLE — another driver is '
                                     f'fighting the Pi')
                    else:
                        parts.append(f'{n} WILL NOT FOLLOW: driven '
                                     f'{"high" if want else "low"}, pad reads '
                                     f'{"high" if 1 in got else "low"}')
                print('  Pi-side readback: ' + '; '.join(parts), flush=True)
        finally:
            rb.close()
            req.release()
            restore_pins()
            print('stopped.')
        return

    half = 1.0 / (2.0 * args.freq)      # base tick = SCK half-period
    config = {}
    for n in names:
        config[PINS[n][0]] = gpiod.LineSettings(
            direction=Direction.OUTPUT,      # push-pull; no open-drain here
            output_value=Value.ACTIVE)
    req = gpiod.request_lines('/dev/gpiochip0', consumer='dsp4_scopedrive',
                              config=config)

    print(f'Driving push-pull, base {args.freq:g} Hz on SCK '
          f'(tick {half * 1e6:.0f} us):')
    for n in names:
        gpio, hdr, div, note = PINS[n]
        print(f'  {n:6s} GPIO{gpio:<3d} {hdr:11s} {args.freq / div:7.1f} Hz  '
              f'{note}')
    print('  scope any of them against a ground pin on J6; expect 0 V / 3.3 V '
          'full swing.\n  Stop with: dsp4_scopedrive.sh stop   (that also '
          'gives SPI0 its pins back)')

    stop = {'now': False}
    signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__('now', True))
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__('now', True))

    gpios = [PINS[n][0] for n in names]
    rb = Readback(gpios)
    names_by_gpio = {PINS[n][0]: n for n in names}
    t0 = time.monotonic()
    next_report = t0 + args.report_every
    tick = 0
    try:
        while not stop['now']:
            # Deadline-referenced sleep: the edges jitter by whatever the
            # scheduler costs (tens of us), but the mean rate does not
            # drift, which is all a level check needs.
            target = t0 + tick * half
            slack = target - time.monotonic()
            if slack > 0:
                time.sleep(slack)
            for n in names:
                gpio, _hdr, div, _note = PINS[n]
                v = (tick // div) & 1
                req.set_value(gpio, Value.ACTIVE if v else Value.INACTIVE)
            rb.sample()
            tick += 1

            now = time.monotonic()
            if now >= next_report:
                v = rb.verdicts()
                print(f'  t+{now - t0:6.1f}s  ' + '  '.join(
                    f'{names_by_gpio[g]}(GPIO{g}) {v[g]}' for g in gpios),
                    flush=True)
                rb.reset()
                next_report = now + args.report_every
            if args.seconds and now - t0 >= args.seconds:
                break
    finally:
        rb.close()
        req.release()
        restore_pins()
        print('stopped.')


if __name__ == '__main__':
    main()
