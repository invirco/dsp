#!/usr/bin/env python3
"""s133_pause_rails.py -- proves both halves of the S133 hub ruling on the
real unit, in one pass:

  1. THE HANDS-OFF SCREEN, RAISED OFF THE FLAG ITSELF. Every panel row is
     pre-ignored (S133's bench harness, restored after), so the panel walk
     inside `overlapped()` finds nothing owed and returns at once -- the exact
     gap S132 found: nothing was left watching `quiet.flag` for the rest of
     the dsp phase's own run. `d24_runall.Background.join()`'s new `hold=`
     wiring is what is under test here, not the acoustic result itself.
  2. PAUSE DROPS THE RAILS. The pass is let through to the analog station's
     own CARD -- which `overlapped()` raises the rails for and hands to
     (`--al1-keep-rails`) -- and PAUSE is pressed THERE, before
     `patch_station()` (and its own `finish_early()`/`teardown()`) is ever
     entered. That is the one door `main()`'s `except Paused:` did not cover
     until this dispatch.

Drives the pass through the SAME file protocol the armed factory screen
answers (`runall/live.json` out, `runall/command.json` in) -- `d24-testui` is
already running and drawing whatever this writes, so a real screenshot is one
`capture.request` away. No touch injection: nothing here has to tap a pixel
to set one JSON field, and the app's own words are read back unchanged.
"""
import json
import os
import subprocess
import sys
import time

RUNALL = '/home/app/selftest/runall'
LIVE = os.path.join(RUNALL, 'live.json')
CMD = os.path.join(RUNALL, 'command.json')
FACTORY_LOG = '/home/app/selftest/factory.log'
CAP = '/home/app/selftest/s128-shot.png'
REQ = '/home/app/selftest/capture.request'
CHAIN_MARKER = '/home/app/s90/.chain_last'


def log(msg):
    line = '%s %s' % (time.strftime('%H:%M:%S'), msg)
    print(line, flush=True)
    return line


def live():
    try:
        with open(LIVE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def send(cmd):
    tmp = CMD + '.tmp'
    with open(tmp, 'w') as f:
        json.dump({'command': cmd, 'stamp': time.time()}, f)
    os.replace(tmp, CMD)
    log('  command.json <- %r' % cmd)


def an_en():
    return subprocess.run(['pinctrl', 'get', '26'], capture_output=True,
                          text=True).stdout.strip()


def chain_marker():
    try:
        with open(CHAIN_MARKER) as f:
            return f.read().strip()
    except OSError as e:
        return '(no marker: %s)' % e


def capture(shots, name):
    open(REQ, 'w').close()
    t0 = time.time()
    while time.time() - t0 < 3.0 and os.path.exists(REQ):
        time.sleep(0.05)
    time.sleep(0.25)
    os.makedirs(shots, exist_ok=True)
    dst = os.path.join(shots, name + '.png')
    try:
        with open(CAP, 'rb') as a, open(dst, 'wb') as b:
            b.write(a.read())
        log('  capture -> %s (%d bytes)' % (dst, os.path.getsize(dst)))
    except OSError as e:
        log('  capture failed: %s' % e)


def main():
    shots = sys.argv[1] if len(sys.argv) > 1 else '/home/app/selftest/s133-screens'
    log('AN_EN at start: %s' % an_en())
    t0 = time.time()
    handsoff_seen = False
    card_seen = False
    paused_sent = False
    last_key = None
    setup_pages_answered = 0
    an_en_at_card = None
    while time.time() - t0 < 600:
        d = live()
        if d is None:
            time.sleep(0.2)
            continue
        key = (d.get('state'), (d.get('status') or '')[:60],
              (d.get('instruction') or '')[:90], d.get('n'), d.get('total'))
        if key != last_key:
            last_key = key
            log('SCREEN [%s] %s/%s %s :: %s'
                % (key[0], d.get('n'), d.get('total'), key[1], key[2]))
        # -- 1. the hands-off screen, raised off the flag alone -------------
        if d.get('state') == 'handsoff' and not handsoff_seen:
            handsoff_seen = True
            log('*** HANDS-OFF REACHED (S133 join()-watcher) -- capturing')
            capture(shots, 's133-handsoff')
        # -- setup pages: one ENTER each, exactly as PW's own passes get ----
        if (d.get('state') == 'waiting' and (d.get('status') or '') == 'Set the bench up'
                and 'enter' in (d.get('buttons') or [])):
            time.sleep(0.3)
            send('enter')
            setup_pages_answered += 1
            time.sleep(0.5)
            continue
        # -- 2. the analog station's own CARD: rails are live, and PAUSE ---
        #    lands BEFORE patch_station()/station.run() is ever entered.
        if (not card_seen and (d.get('instruction') or '').startswith('Next: analog paths')):
            card_seen = True
            an_en_at_card = an_en()
            log('*** ANALOG STATION CARD REACHED -- AN_EN: %s' % an_en_at_card)
            capture(shots, 's133-card-rails-up')
            time.sleep(0.5)
            log('*** SENDING PAUSE AT THE CARD (before the station ever runs)')
            send('pause')
            paused_sent = True
            time.sleep(0.5)
            continue
        if paused_sent and d.get('state') == 'paused':
            log('*** SCREEN SHOWS PAUSED')
            capture(shots, 's133-paused')
            break
        time.sleep(0.2)
    an_en_after_pause = an_en()
    chain_after_pause = chain_marker()
    log('AN_EN after PAUSE at the card: %s' % an_en_after_pause)
    log('chain marker after PAUSE: %s' % chain_after_pause)
    result = dict(setup_pages_answered=setup_pages_answered,
                 handsoff_seen=handsoff_seen, card_seen=card_seen,
                 an_en_at_card=an_en_at_card,
                 an_en_after_pause=an_en_after_pause,
                 chain_after_pause=chain_after_pause)
    print('RESULT %s' % json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    main()
