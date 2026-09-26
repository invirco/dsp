#!/usr/bin/env python3
"""s117-tap-through.py -- answer the RUN ALL wizard THROUGH THE GLASS.

Runs on the unit beside `d24_touch_inject.py --serve /tmp/tap`. It watches
`runall/prompt.json`, decides which of the six on-screen slots to press, and
taps that slot's centre on the real touch device. Every answer this session
recorded therefore went in the way an operator's finger goes in: uinput ->
libinput -> Avalonia's DRM backend -> the control under the point -> the store
-> answer.json. It is NOT a test of the panel's own ILITEK controller.

The slot geometry is the skin's own: six buttons 295 x 68 at y=844, the first at
x=40, pitch 307 (mx26 tools/d24/build-d24-test-skin.py). START ALL is the second
footer button, 400 x 100 at (456, 920).

    python3 s117-tap-through.py --plan bench     # the S117 bench walk
"""
import argparse
import json
import os
import subprocess
import sys
import time

DIR = '/home/app/selftest/runall'
TAP = '/tmp/tap'
SLOT_Y = 878
SLOT_X = [40 + i * 307 + 147 for i in range(6)]
STARTALL = (656, 970)
REASONS = ['awaiting part', 'known rev-C erratum', 'fixture not built', 'other']


def tap(x, y, why=''):
    with open(TAP, 'w') as fh:
        fh.write('%d %d\n' % (x, y))
    print('   tap (%d,%d) %s' % (x, y, why), flush=True)
    time.sleep(1.2)


def read_prompt():
    try:
        with open(os.path.join(DIR, 'prompt.json')) as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def answer(p, button, reason=''):
    if button not in p['buttons']:
        print('   !! %r not offered: %s' % (button, p['buttons']))
        return False
    slot = p['buttons'].index(button)
    tap(SLOT_X[slot], SLOT_Y, '%s (slot %d) for %s' % (button, slot + 1,
                                                       p['title']))
    if button in ('skip', 'ignore'):
        r = REASONS.index(reason if reason in REASONS else 'other')
        tap(SLOT_X[r], SLOT_Y, 'reason %r (slot %d)' % (REASONS[r], r + 1))
    return True


def policy(p, overrides):
    row = p.get('row') or 0
    key = (p['kind'], row)
    for i, (k, b, r) in enumerate(overrides):
        if k == key or k == row or k == p['kind']:
            overrides.pop(i)
            return b, r
    if p['kind'] == 'station':
        return 'ack', ''
    if p['kind'] == 'review':
        return 'next-pass', ''
    if row in (130, 131):
        return 'done', ''
    if row == 133:
        return 'skip', 'other'
    return 'skip', 'fixture not built'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--start', action='store_true', help='press START ALL first')
    ap.add_argument('--overrides', default='',
                    help='one-shot answers, "row:button[:reason],..."')
    ap.add_argument('--stop-after', type=int, default=400)
    ap.add_argument('--idle-exit', type=float, default=0,
                    help='exit after this many seconds with no prompt (0 = never)')
    a = ap.parse_args()
    overrides = []
    for spec in [x for x in a.overrides.split(',') if x]:
        bits = spec.split(':')
        overrides.append((int(bits[0]) if bits[0].isdigit() else bits[0],
                          bits[1], bits[2] if len(bits) > 2 else ''))
    if a.start:
        tap(*STARTALL, why='START ALL')
    seen, n, idle = -1, 0, time.time()
    while n < a.stop_after:
        p = read_prompt()
        if p is None or p['seq'] == seen:
            if a.idle_exit and time.time() - idle > a.idle_exit:
                print('idle for %.0f s -- done' % a.idle_exit)
                return
            time.sleep(0.5)
            continue
        seen = p['seq']
        idle = time.time()
        # THE APP POLLS THE PROMPT FILE EVERY 2 s. This reads it the moment the
        # runner writes it, so a tap sent straight away lands on a page that
        # has not drawn the dialog yet and is thrown away -- measured on the
        # first attempt: ACT1 pressed at 14:50:24.82, the store loaded the
        # dialog at 14:50:25.55. A finger cannot be that fast; this wait is
        # what makes the robot as slow as a person.
        time.sleep(3.0)
        b, r = policy(p, overrides)
        print('\n[%d] %s seq=%d row=%s -> %s %s'
              % (n, p['title'], p['seq'], p.get('row'), b, r), flush=True)
        answer(p, b, r)
        n += 1
        if b in ('pause', 'stop'):
            print('stopping: answered %s' % b)
            return
    print('hit --stop-after')


if __name__ == '__main__':
    main()
