#!/usr/bin/env python3
"""glass_drive.py -- walk the factory screen with no finger at the bench (S128).

Runs ON THE UNIT. Watches `runall/live.json` and taps the app's own ENTER (or
PAUSE, or the armed START) through the injected touch device, so a dispatched
session can prove the WHOLE chain a worker uses: the runner writes the screen,
the app draws it, a press lands on the app's own button, the app writes
`command.json`, the runner reads it.

WHAT THIS PROVES AND WHAT IT DOES NOT. The tap goes in through `/dev/uinput`, so
libinput and Avalonia deliver it to the control under the point exactly as they
deliver one from the panel's ILITEK controller. It proves the SCREEN and the APP.
It proves nothing about the touch panel, its cable or its controller -- PW's
finger is the only thing that does that.

    # once, before the app starts (Avalonia enumerates input devices at startup):
    sudo python3 d24_touch_inject.py --serve /tmp/tap &
    sudo systemctl restart d24-testui
    python3 glass_drive.py --start --until "Station 3" --secs 1200

The button coordinates are read off `FactoryView.axaml`: a 1920x1080 panel, the
outer Grid at Margin="80,50,80,50" with RowDefinitions="170,*,300,190", and the
button row bottom-aligned with Height=150. ENTER is Column 0, Width 640; PAUSE is
Column 2 after a 28 px gap, Width 330.
"""
import argparse
import json
import os
import sys
import time

RUNALL = '/home/app/selftest/runall'
LIVE = os.path.join(RUNALL, 'live.json')
TAP = '/tmp/tap'
ENTER = (400, 955)
PAUSE = (913, 955)


def tap(point, log):
    x, y = point
    with open(TAP, 'w') as fh:
        fh.write('%d %d\n' % (x, y))
    log('tap %d,%d' % (x, y))


def read_live():
    try:
        with open(LIVE) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--start', action='store_true',
                    help='tap the armed START first')
    ap.add_argument('--until', default='',
                    help='stop once the instruction contains this')
    ap.add_argument('--pause-at', default='',
                    help='tap PAUSE instead of ENTER once the instruction '
                         'contains this, then stop')
    ap.add_argument('--secs', type=float, default=900.0)
    ap.add_argument('--settle', type=float, default=1.2,
                    help='seconds to leave a page on the glass before tapping, '
                         'so a witness capture has something to catch')
    ap.add_argument('--log', default='')
    a = ap.parse_args()
    out = open(a.log, 'a') if a.log else None

    def log(msg):
        line = '%s %s' % (time.strftime('%H:%M:%S'), msg)
        print(line, flush=True)
        if out:
            out.write(line + '\n')
            out.flush()

    seen = []
    last = None
    t0 = time.time()
    if a.start:
        for _ in range(40):
            d = read_live()
            if d is not None and 'start' not in (d.get('buttons') or []):
                log('a run is already live; not pressing START')
                break
            time.sleep(0.25)
        else:
            log('pressing the armed START')
            tap(ENTER, log)
    while time.time() - t0 < a.secs:
        d = read_live()
        if d is None:
            time.sleep(0.2)
            continue
        instr = (d.get('instruction') or '').strip()
        state = d.get('state')
        btns = d.get('buttons') or []
        key = (state, instr, (d.get('extra') or '').strip())
        if key != last:
            last = key
            seen.append((round(time.time() - t0, 1), state, instr,
                         d.get('status'), '%s/%s' % (d.get('n'), d.get('total'))))
            log('SCREEN [%s] n=%s/%s status=%r :: %s'
                % (state, d.get('n'), d.get('total'), d.get('status'),
                   instr[:150]))
            if a.pause_at and a.pause_at in instr:
                time.sleep(a.settle)
                log('PAUSE at %r' % instr[:80])
                tap(PAUSE, log)
                break
            if a.until and a.until in instr:
                log('reached %r -- stopping' % a.until)
                break
            if 'enter' in btns:
                time.sleep(a.settle)
                tap(ENTER, log)
        else:
            # The same page, still waiting: it wants a press the first tap did
            # not deliver. Try once more, slowly, rather than sitting for ever.
            if 'enter' in btns and time.time() - t0 > 3:
                time.sleep(3.0)
                d2 = read_live()
                if d2 and (d2.get('instruction') or '').strip() == instr \
                        and 'enter' in (d2.get('buttons') or []):
                    tap(ENTER, log)
            time.sleep(0.4)
    log('--- %d distinct screens ---' % len(seen))
    for s in seen:
        log('  %6.1fs [%s] %s | %s | %s' % (s[0], s[1], s[4], s[3], s[2][:120]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
