#!/usr/bin/env python3
"""s162_audit.py -- S162, the Q542 Schottky A/B against S160 (MW-D24-2, analog
board 2, SS210A fitted at the Q542 gate as a DC restore). OPEN inputs, nothing
plugged, no hand steps.

Same instrument and same strip handling as s160_audit.py (TEST_MEAS capture
arm, the list's 219 `_standing_bypass` cells read, bypassed and restored,
sends shut, every other input shunted at gain 0, the booted pair's symbols),
in two phases inside ONE rails-up so the converters see one cold start:

  1. DRIFT MAP from the moment the rails come up: MIC 2 open at code 63,
     2 x 16k captures every 30 s for 15 min; MIC 4 at code 63 at 0, 5, 10
     and 15 min (2 x 16k, then straight back to MIC 2). Every capture carries
     its time since rails-up.
  2. The S160 set: MIC 1-5 at code 63 and MIC 2 at codes 0/32/48, 6 x 16k
     each, after the same node settle as S160.

The cold start is the caller's job: AN_EN low for at least 5 minutes before
this runs (checked here against --cold-since, refused if short).

    cd /home/app/s162 && python3 -u s162_audit.py --cold-since EPOCH
"""
import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, '/home/app/selftest')
import d24_patch as PT                         # noqa: E402
import dsp4_meascap as MC                      # noqa: E402

PLAN = [('MIC 1', 63), ('MIC 2', 63), ('MIC 3', 63), ('MIC 4', 63),
        ('MIC 5', 63), ('MIC 2', 0), ('MIC 2', 32), ('MIC 2', 48)]
SETTLE_MIN_S = 5.0
SETTLE_MAX_S = 20.0
SETTLE_AGREE_DB = 0.3
COLD_MIN_S = 300.0


def lanes_from_list(plist):
    out = {}
    for r in plist.paths:
        if r.get('send_pos') not in (None, '') and str(r['lane']).isdigit() \
                and str(r['in']).startswith('MIC ') and 'line' not in r['in']:
            out[r['in']] = (int(r['lane']), int(r['send_pos']))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--cold-since', type=float, required=True,
                    help='epoch seconds the rails have been down since')
    ap.add_argument('--drift-min', type=float, default=15.0)
    ap.add_argument('--drift-every', type=float, default=30.0)
    ap.add_argument('--drift-caps', type=int, default=2)
    ap.add_argument('--caps', type=int, default=6)
    ap.add_argument('--n', type=int, default=16384)
    ap.add_argument('--out', default=os.path.join(HERE, 'data'))
    a = ap.parse_args()
    cold = time.time() - a.cold_since
    if cold < COLD_MIN_S:
        raise SystemExit('rails down only %.0f s (< %.0f s): not a cold start'
                         % (cold, COLD_MIN_S))
    os.makedirs(os.path.join(a.out, 'drift'), exist_ok=True)
    plist = PT.PatchList(PT.find_list_dir())
    lanes = lanes_from_list(plist)
    u = PT.Unit()
    print('symbols: %s (booted pair); rails down %.0f s before this run'
          % (u.symdir, cold), flush=True)
    sc = u.chip(1)
    an = PT.Analog(enabled=True, log=lambda s: print('   ..', s, flush=True),
                   own_rails=True)
    found = {}
    byp = plist.bypass()

    def select(inp, code):
        strip, pos = lanes[inp]
        an.chain(an.step_image(pos, code), '%s at code %d' % (inp, code))
        u.meas_chan(strip)
        return strip, pos

    def grab(k):
        out = []
        for _ in range(k):
            c = MC.capture(a.n, symdir=u.symdir, sc=sc, log=lambda s: None)
            out.append(dict(samples=c['samples'], overruns=c['overruns'],
                            t_rails=round(time.time() - t_up, 2)))
        return out

    try:
        for spec in byp:
            name = spec.partition('=')[0]
            found[name] = u.read(name) & 0xFFFFFFFF
        with open(os.path.join(a.out, 'bypass-found.json'), 'w') as fh:
            json.dump(found, fh, indent=0, sort_keys=True)
        bad = u.write(plist.standing() + byp)
        print('standing + %d bypass cells written (%d did not read back)'
              % (len(byp), len(bad)), flush=True)
        u.osc(on=False)
        # the chain is set to MIC 2 BEFORE the rails rise, so the first
        # capture can follow the rails-up with nothing else in between
        select('MIC 2', 63)
        an.up()
        t_up = time.time()
        print('RAILS UP at %s' % time.strftime('%H:%M:%SZ', time.gmtime(t_up)),
              flush=True)
        # ---- phase 1: drift map --------------------------------------
        select('MIC 2', 63)
        mic4_due = [0.0, 300.0, 600.0, 900.0]
        k = 0
        end = a.drift_min * 60.0
        while True:
            tsched = k * a.drift_every
            now = time.time() - t_up
            if tsched > end + 0.5:
                break
            if now < tsched:
                time.sleep(tsched - now)
            caps = grab(a.drift_caps)
            rec = dict(input='MIC 2', strip=lanes['MIC 2'][0], code=63,
                       termination='open', symdir=u.symdir, t_sched=tsched,
                       captures=caps, rails_up=t_up)
            with open(os.path.join(a.out, 'drift', 'd%02d_MIC2.json' % k),
                      'w') as fh:
                json.dump(rec, fh)
            print('drift %02d t+%6.1f s MIC 2 overruns %s'
                  % (k, caps[0]['t_rails'], [c['overruns'] for c in caps]),
                  flush=True)
            if mic4_due and tsched >= mic4_due[0] - 0.5:
                mic4_due.pop(0)
                select('MIC 4', 63)
                time.sleep(2.0)
                caps = grab(a.drift_caps)
                rec = dict(input='MIC 4', strip=lanes['MIC 4'][0], code=63,
                           termination='open', symdir=u.symdir,
                           t_sched=tsched, captures=caps, rails_up=t_up)
                with open(os.path.join(a.out, 'drift', 'd%02d_MIC4.json' % k),
                          'w') as fh:
                    json.dump(rec, fh)
                print('drift %02d t+%6.1f s MIC 4 overruns %s'
                      % (k, caps[0]['t_rails'], [c['overruns'] for c in caps]),
                      flush=True)
                select('MIC 2', 63)
                time.sleep(2.0)
            k += 1
        # ---- phase 2: the S160 set -----------------------------------
        for inp, code in PLAN:
            strip, pos = select(inp, code)
            tag = '%s_c%02d_open' % (inp.replace(' ', ''), code)
            t0 = time.time()
            prev, trail = None, []
            while True:
                m = u.measure(None, 0.0, windows=1, settle=1)
                v = m.get('rms')
                trail.append((round(time.time() - t0, 2), v))
                if (prev is not None and time.time() - t0 >= SETTLE_MIN_S
                        and abs(v - prev) <= SETTLE_AGREE_DB) \
                        or time.time() - t0 >= SETTLE_MAX_S:
                    break
                prev = v
            caps = grab(a.caps)
            for c in caps:
                c['t'] = round(c['t_rails'] - (t0 - t_up), 2)
            node = u.measure(None, 0.0, windows=4, settle=1)
            rec = dict(input=inp, strip=strip, send_pos=pos, code=code,
                       termination='open', symdir=u.symdir,
                       settle_trail=trail, node_rms=node.get('rms'),
                       node_rms_spread=node.get('rms_spread'),
                       captures=caps, rails_up=t_up, stamp=time.strftime(
                           '%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
            with open(os.path.join(a.out, tag + '.json'), 'w') as fh:
                json.dump(rec, fh)
            print('%-6s code %2d strip %2d: settled %.1f s, node RMS %.2f dBFS, '
                  '%d x %d captures at t+%.0f s, overruns %s'
                  % (inp, code, strip, trail[-1][0], node.get('rms'),
                     len(caps), a.n, caps[0]['t_rails'],
                     [c['overruns'] for c in caps]), flush=True)
    finally:
        try:
            u.osc(on=False)
        except Exception as e:
            print('osc off failed: %s' % e)
        an.down()
        if found:
            bad = u.write(['%s=0x%08X' % (n, w) for n, w in sorted(found.items())])
            print('bypass: %d cells restored to the values found (%d did not '
                  'read back)' % (len(found), len(bad)), flush=True)
        u.write(plist.routes['_standing_close'], verify=False)
        print('handed back: rails down, chain safe, sends shut', flush=True)


if __name__ == '__main__':
    main()
