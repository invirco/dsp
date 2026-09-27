#!/usr/bin/env python3
"""s132_al1_glass.py -- press the glass's own armed START, let the pass reach
AL1 with NOBODY TOUCHING ANYTHING, read AL1's verdict, PAUSE, and do it again.

Runs ON THE UNIT. Prerequisite, as for S128/S130:
    sudo nohup python3 /home/app/selftest/d24_touch_inject.py --serve /tmp/tap &

WHY A DRIVER OF ITS OWN RATHER THAN S130'S. S130's `s130_drive.py` walks a WHOLE
pass to prove the summary grid, which is 20 minutes and answers ENTER on every
screen. The only thing asked here is AL1, three times from START, and every tap
this driver does not make is one less thing that can be blamed for the reading:

  * THE HANDS COME OFF THE MOMENT AL1'S OWN BATCH STARTS, and the signal is
    external to the glass: while a `d24_selftest.py` child WITH `AL1` IN ITS
    ARGUMENTS is alive, this driver makes NO tap of any kind -- no ENTER, no
    re-tap, no capture.request. AL1 lives inside that child, so "that batch is
    running" and "hands off" are one condition and neither is a guess about
    screen text.
    `AL1` and not merely `d24_selftest.py`: a pass launches THREE self-test
    batches and the first, the `[serial]` auto set, starts at SETUP step 1 and
    runs while the operator is still plugging leads in -- by design, and it has
    no acoustic window. Keying on the process name alone would keep the driver
    still through the setup station it has to answer, and the pass would never
    reach AL1 at all.
  * The SETUP station ahead of it (7 ENTER steps: the network lead, the kit and
    so on) is answered once per NEW screen. A pass that is never set up never
    reaches AL1.
  * A PASS IS RESUMABLE, so each repeat RESETS the run state first
    (`d24_runall.py --reset-only`). Without that the second START resumes at the
    operator set -- "the next START resumes here" -- and AL1, already recorded,
    is never taken again: three PASSes would be one reading printed three times.
  * The verdict is read from `factory.log`, the station's own record, not from
    anything this driver computes.
  * Then ONE tap on PAUSE to wind the pass up, and the next repeat waits for the
    glass to be armed again (`buttons` carries `start`) before pressing it.

The one capture it does take is of the `handsoff` state, and only if the state
is ever reached -- S130 asked whether it is, given AL1 runs in the AUTO batch
ahead of the panel step whose `hold=` is the only thing that sets it.
"""
import argparse
import json
import os
import re
import sys
import time

RUNALL = '/home/app/selftest/runall'
LIVE = os.path.join(RUNALL, 'live.json')
FACTORY_LOG = '/home/app/selftest/factory.log'
TAP = '/tmp/tap'
PRIMARY = (400, 955)       # ENTER / START / EXIT share one Border
PAUSE = (913, 955)
AL1_LINE = re.compile(r'^\s*(?:\[dsp\]\s*)?\s*AL1\s+(PASS|FAIL|NO DATA)\s*(.*)$')


def log(msg, fh=None):
    line = '%s %s' % (time.strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    if fh:
        fh.write(line + '\n')
        fh.flush()


def tap(point, fh=None):
    with open(TAP, 'w') as f:
        f.write('%d %d\n' % point)
    log('tap %d,%d' % point, fh)


def live():
    try:
        with open(LIVE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def log_size():
    try:
        return os.path.getsize(FACTORY_LOG)
    except OSError:
        return 0


def al1_verdict_after(off):
    """The first AL1 verdict line written past byte `off`, or None."""
    try:
        with open(FACTORY_LOG, errors='replace') as f:
            f.seek(off)
            for ln in f:
                m = AL1_LINE.match(ln.rstrip('\n'))
                if m and m.group(2).strip():
                    return m.group(1), m.group(2).strip()
    except OSError:
        pass
    return None


def capture(cap, shots, name, fh=None):
    if not cap:
        return
    req = os.path.join(os.path.dirname(cap), 'capture.request')
    try:
        open(req, 'w').close()
    except OSError as e:
        return log('capture request failed: %s' % e, fh)
    t0 = time.time()
    while time.time() - t0 < 3.0 and os.path.exists(req):
        time.sleep(0.05)
    time.sleep(0.25)
    if shots and os.path.exists(cap):
        os.makedirs(shots, exist_ok=True)
        dst = os.path.join(shots, '%s.png' % name)
        with open(cap, 'rb') as a, open(dst, 'wb') as b:
            b.write(a.read())
        log('capture -> %s (%d bytes)' % (dst, os.path.getsize(dst)), fh)


def al1_batch_running():
    """Is the self-test batch that CONTAINS AL1 alive right now.

    THE HANDS-OFF CONDITION, and deliberately not a screen state. `LV.HANDSOFF`
    is set only inside `panel_station`'s `hold=` callback, so a pass that reaches
    AL1 inside the automatic batch -- which is every pass -- never shows it (S130
    asked; S132 measured it: see `handsoff_reached` in the JSON). A driver that
    waited for that state to know when to keep still would keep still never.
    """
    # `[.]` AND NOT `.`, because `pgrep -f` reads the whole command line and
    # `os.system` runs this through `sh -c`, whose OWN command line contains the
    # pattern. With a bare dot the pattern matches the shell that is asking, so
    # this answered True for ever, the driver went hands-off at SETUP step 1 and
    # the pass stalled with nobody to press ENTER. `d24_selftest[.]py` requires a
    # literal dot, which the pattern text itself does not have.
    return os.system("pgrep -f 'd24_selftest[.]py.*AL1' >/dev/null 2>&1") == 0


def rails_down(fh=None):
    """AN_EN (GPIO26) LOW before the pass starts, and say what it was.

    THE PRECONDITION THAT EATS A WHOLE PASS SILENTLY. `boot_pair` refuses to boot
    the DSP pair with the analog rails up -- "analog last up, first down" (PW
    09-10), raised once after the last boot of the session and held to handback
    (S116 Q4). A session that ended with `--al1-keep-rails`, or any bench probe
    that raised them by hand, therefore leaves GPIO26 high; the next pass's whole
    `[dsp]` batch then dies on that RuntimeError in under a second, the AUTO set
    reports "finished in 0 s", and AL1 -- which lives in that batch -- is never
    taken at all. Nothing on the glass says why.

    This is the same write the runner's own `handback()` makes, to the same safe
    state, and it is made BEFORE the pass rather than during it."""
    was = os.popen('pinctrl get 26 2>&1').read().strip()
    os.system('sudo pinctrl set 26 op dl >/dev/null 2>&1')
    now = os.popen('pinctrl get 26 2>&1').read().strip()
    log('AN_EN before the pass: %s -> %s' % (was, now), fh)
    return 'lo' in now


def reset_state(fh=None):
    """Put the station back to a pass that has not been taken yet.

    `d24_runall.py --reset-only` -- the station's own reset (S129), not a file
    this driver deletes behind its back."""
    rc = os.system("python3 /home/app/selftest/d24_runall.py --dir "
                   "/home/app/selftest --reset-only >>%s 2>&1"
                   % '/home/app/selftest/s132-reset.log')
    log('run state reset (--reset-only, exit %d)' % (rc >> 8), fh)
    return rc == 0


def wait_armed(secs, fh=None):
    """True once the glass is showing an armed START again."""
    t0 = time.time()
    while time.time() - t0 < secs:
        d = live()
        if d is None or 'start' in (d.get('buttons') or []):
            return True
        time.sleep(0.5)
    return False


def one_pass(a, n, fh):
    rails_down(fh)
    if a.reset:
        reset_state(fh)
    if not wait_armed(a.arm_secs, fh):
        log('pass %d: the glass never came back to an armed START' % n, fh)
        return None
    off = log_size()
    # A BEAT BEFORE THE FIRST TAP. The repeat that precedes this one ends with a
    # PAUSE and a `--reset-only`, and a tap that lands while the app is still
    # repainting that transition is swallowed: the glass stays on the paused page
    # with only START on it and the whole 480 s budget is spent waiting for a
    # pass that never began. Seen once, take 4, pass 2.
    time.sleep(a.settle)
    log('pass %d: pressing the armed START (factory.log at %d bytes)' % (n, off), fh)
    tap(PRIMARY, fh)
    started = time.time()
    start_taps = 1
    t0 = time.time()
    states = []
    handsoff = False
    verdict = None
    quiet = False
    last_tap = 0.0
    retapped = False
    while time.time() - t0 < a.al1_secs:
        d = live()
        busy = al1_batch_running()
        if busy and not quiet:
            quiet = True
            log("  AL1's own batch is running -- HANDS OFF from here: no tap "
                'of any kind until AL1 has reported', fh)
        if d is not None:
            # THE INSTRUCTION AND THE STEP NUMBER ARE PART OF THE KEY. The
            # setup station's 7 steps all carry state 'waiting' and status 'Set
            # the bench up' and differ only in the instruction, so a key of
            # (state, status) makes steps 2..7 look like step 1 already answered
            # and the driver never taps again: the pass stops at SETUP 2 of 7
            # and AL1 is never reached.
            k = (d.get('state'), (d.get('status') or '').strip()[:60],
                 (d.get('instruction') or '').strip()[:120], d.get('n'))
            fresh = not states or states[-1][1:] != k
            if fresh:
                states.append((round(time.time() - t0, 1),) + k)
                log('  SCREEN [%s] %s/%s %s :: %s%s'
                    % (k[0], d.get('n'), d.get('total'), k[1], k[2][:90],
                       ' (hands off)' if busy else ''), fh)
            if d.get('state') == 'handsoff' and not handsoff:
                handsoff = True
                log('  the HANDS-OFF state IS reached', fh)
                if not busy:
                    capture(a.cap, a.shots, 'pass%d-handsoff' % n, fh)
            # AND THE START ITSELF MAY NEED ASKING AGAIN, for the same reason:
            # while the glass still offers only START, the pass has not begun, so
            # there is nothing to disturb and a repeat tap costs nothing. Three
            # at most, so a station that is genuinely stuck stays stuck loudly.
            if ('start' in (d.get('buttons') or []) and not busy
                    and start_taps < 3 and time.time() - started > 10.0):
                start_taps += 1
                log('  the glass still offers only START after %.0f s -- '
                    'pressing it again (%d)'
                    % (time.time() - started, start_taps), fh)
                tap(PRIMARY, fh)
                started = time.time()
            # The SETUP station ahead of AL1's batch: one tap per NEW screen,
            # and only while that batch is not running.
            if fresh and not busy and 'enter' in (d.get('buttons') or []):
                last_tap = time.time()
                retapped = False
                time.sleep(a.settle)
                if not al1_batch_running():
                    tap(PRIMARY, fh)
            elif (not busy and not retapped and last_tap
                  and time.time() - last_tap > a.retap_after
                  and 'enter' in (d.get('buttons') or [])):
                # ONE re-tap per screen, and never while AL1's batch is live.
                # S130 removed a 3 s periodic re-tap for good reason -- it taps
                # the very panel the acoustic window exists to protect -- but a
                # first tap that does not register leaves a pass parked for ever
                # on an unchanged screen, which is how one repeat here was lost.
                # Once, after a long wait, with the batch idle, is the middle.
                retapped = True
                log('  the screen has not moved in %.0f s and no batch is '
                    'running -- one re-tap' % a.retap_after, fh)
                tap(PRIMARY, fh)
        verdict = al1_verdict_after(off)
        if verdict:
            break
        time.sleep(0.4)
    if verdict:
        log('pass %d: AL1 %s  %s' % (n, verdict[0], verdict[1]), fh)
    else:
        log('pass %d: AL1 never reported inside %.0f s' % (n, a.al1_secs), fh)
    log('pass %d: PAUSE, winding the pass up' % n, fh)
    tap(PAUSE, fh)
    time.sleep(a.settle)
    # PAUSE lands on a screen with a button; answering it once returns the
    # station to an armed START without walking the rest of the pass.
    for _ in range(int(a.arm_secs / 2)):
        d = live()
        if d is None or 'start' in (d.get('buttons') or []):
            break
        if 'enter' in (d.get('buttons') or []) or 'exit' in (d.get('buttons') or []):
            tap(PRIMARY, fh)
        time.sleep(2.0)
    return {'pass': n, 'verdict': verdict[0] if verdict else 'NO REPORT',
            'measured': verdict[1] if verdict else '',
            'handsoff_reached': handsoff,
            'screens': states}


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--passes', type=int, default=3)
    ap.add_argument('--no-reset', dest='reset', action='store_false',
                    help='do NOT reset the run state before each pass -- only '
                         'useful for watching a resume; AL1 is then taken once')
    ap.add_argument('--al1-secs', type=float, default=240.0,
                    help='how long to wait for AL1 to report in one pass')
    ap.add_argument('--arm-secs', type=float, default=180.0)
    ap.add_argument('--settle', type=float, default=2.0)
    ap.add_argument('--retap-after', type=float, default=45.0,
                    help='seconds an unchanged ENTER screen may sit before ONE '
                         're-tap; never fired while AL1\'s batch is running')
    ap.add_argument('--cap', default='/home/app/selftest/s128-shot.png',
                    help='the MX_DRM_CAPTURE_PATH d24-testui was started with')
    ap.add_argument('--shots', default='/home/app/selftest/s132-screens')
    ap.add_argument('--json', default='/home/app/selftest/s132-al1-glass.json')
    ap.add_argument('--log', default='/home/app/selftest/s132-al1-glass.log')
    a = ap.parse_args()
    fh = open(a.log, 'a') if a.log else None
    out = []
    for n in range(1, a.passes + 1):
        r = one_pass(a, n, fh)
        if r is None:
            break
        out.append(r)
    log('--- %d passes, AL1: %s ---'
        % (len(out), ', '.join(r['verdict'] for r in out)), fh)
    if a.json:
        with open(a.json, 'w') as f:
            json.dump(out, f, indent=1)
    return 0 if out and all(r['verdict'] == 'PASS' for r in out) else 1


if __name__ == '__main__':
    sys.exit(main())
