#!/usr/bin/env python3
"""s130_drive.py -- walk a pass from the app's own START with no finger at the
bench (S130 items 1-2), based on S128's glass_drive.py.

Extends it with:
  * tapping the SAME primary-button position for 'exit' as for 'enter' (the
    summary grid and the paged EXIT use the one Primary border -- see
    FactoryView.axaml.cs, buttons_for(SUMMARY) == ['exit']);
  * firing an on-demand DRM capture (MX_DRM_CAPTURE_PATH's capture.request)
    and saving a copy under --shots for every distinct 'summary' page and for
    the 'handsoff' state (AL1), plus one after EXIT returns to armed START;
  * never firing a capture during a 'network'/NW instruction (S129 addendum 2:
    a capture.request during the NW window is itself a perturbation).

Runs ON THE UNIT, same prerequisites as glass_drive.py:
    sudo python3 d24_touch_inject.py --serve /tmp/tap &
    # MX_DRM_CAPTURE_PATH / MX_DRM_CAPTURE_MS set via a systemd drop-in, then:
    sudo systemctl restart matrix-app
    python3 s130_drive.py --start --secs 1800 --shots /home/app/selftest/s130-screens
"""
import argparse
import json
import os
import sys
import time

RUNALL = '/home/app/selftest/runall'
LIVE = os.path.join(RUNALL, 'live.json')
TAP = '/tmp/tap'
PRIMARY = (400, 955)   # ENTER / START / EXIT all share this Border


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


def fire_capture(cap, shots, name, log):
    if not cap:
        return
    reqdir = os.path.dirname(cap)
    req = os.path.join(reqdir, 'capture.request')
    try:
        open(req, 'w').close()
    except OSError as e:
        log('capture request failed: %s' % e)
        return
    t0 = time.time()
    while time.time() - t0 < 3.0 and os.path.exists(req):
        time.sleep(0.05)
    time.sleep(0.2)   # the app writes cap, then deletes req -- give the save a beat
    if shots and os.path.exists(cap):
        os.makedirs(shots, exist_ok=True)
        dst = os.path.join(shots, '%s.png' % name)
        with open(cap, 'rb') as fh:
            data = fh.read()
        with open(dst, 'wb') as fh:
            fh.write(data)
        log('capture -> %s (%d bytes)' % (dst, len(data)))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--start', action='store_true')
    ap.add_argument('--until', default='')
    ap.add_argument('--secs', type=float, default=1800.0)
    ap.add_argument('--settle', type=float, default=1.2)
    ap.add_argument('--cap', default='/home/app/selftest/s130-cap.png',
                    help='the MX_DRM_CAPTURE_PATH the app was started with')
    ap.add_argument('--shots', default='/home/app/selftest/s130-screens')
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
    summary_pages_shot = set()
    handsoff_shot = False
    exited_shot = False
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
            tap(PRIMARY, log)
    while time.time() - t0 < a.secs:
        d = read_live()
        if d is None:
            time.sleep(0.2)
            continue
        instr = (d.get('instruction') or '').strip()
        state = d.get('state')
        btns = d.get('buttons') or []
        status = (d.get('status') or '').strip()
        key = (state, instr, status, d.get('n'))
        if key != last:
            last = key
            seen.append((round(time.time() - t0, 1), state, instr, status,
                         '%s/%s' % (d.get('n'), d.get('total'))))
            log('SCREEN [%s] n=%s/%s status=%r :: %s'
                % (state, d.get('n'), d.get('total'), status, instr[:150]))

            is_network = 'network' in instr.lower() or 'nw' in status.lower()

            if state == 'handsoff' and not handsoff_shot and not is_network:
                time.sleep(0.6)
                fire_capture(a.cap, a.shots, 'handsoff-01', log)
                time.sleep(1.5)
                fire_capture(a.cap, a.shots, 'handsoff-02-progress', log)
                handsoff_shot = True

            if state == 'summary':
                n = d.get('n')
                if n not in summary_pages_shot and not is_network:
                    time.sleep(a.settle)
                    fire_capture(a.cap, a.shots, 'summary-page-%s' % n, log)
                    summary_pages_shot.add(n)
                if 'exit' in btns:
                    time.sleep(a.settle)
                    tap(PRIMARY, log)

            if a.until and a.until in instr:
                log('reached %r -- stopping' % a.until)
                break
            if 'enter' in btns:
                time.sleep(a.settle)
                tap(PRIMARY, log)
        else:
            # armed START reached again after a summary EXIT: one more shot
            if state is None and summary_pages_shot and not exited_shot:
                time.sleep(a.settle)
                fire_capture(a.cap, a.shots, 'armed-after-exit', log)
                exited_shot = True
                log('back at armed START after EXIT -- stopping')
                break
            # NO PERIODIC RETRY TAP (S130, corrected): glass_drive.py retried
            # every 3 s on an unchanged 'enter' screen to cover a missed first
            # tap, but `buttons_for(WAITING)` is ALSO ['enter','pause'] during
            # every panel-loop button -- a step that is never answered by that
            # button at all (it grades off a real panel press or a timeout).
            # Retrying there just means tapping the touchscreen every 3 s for
            # up to 30 s per button, which is a touch on the very panel AL1's
            # hands-off window exists to protect -- and AL1 runs concurrently
            # with the panel loop's own first button, not before it. One tap
            # per NEW screen (already done above) is enough; a genuinely
            # missed tap just costs the rest of --secs, which is cheap next to
            # disturbing the one measurement this session exists to prove.
            time.sleep(0.4)
    log('--- %d distinct screens ---' % len(seen))
    for s in seen:
        log('  %6.1fs [%s] %s | %s | %s' % (s[0], s[1], s[4], s[3], s[2][:120]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
