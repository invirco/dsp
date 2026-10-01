#!/usr/bin/env python3
"""s160_audit.py -- the MIC 1-4 (+ MIC 5) noise-floor FFT audit (S160, HUB
ADDENDUM 3+4 to S159, PW 2026-10-01): OPEN inputs, nothing plugged, no hand
steps.

Per setting (input, gain code): that input's preamp at the code with its
phantom shunt released and phantom off, every other input shunted at gain 0
(the station's own `Analog.step_image`); MeasChan on the input's strip; the
node polled until two windows agree; then N x 16,384-sample captures of the
strip post-fader through the TEST_MEAS capture arm (dsp4_meascap, the S56/S57
instrument) and the node's RmsResult over 4 windows. Raw samples go to JSON
for the desk.

THE STRIP IS MADE TRANSPARENT FIRST, the station's way: every processing cell
in the list's `_standing_bypass` is READ, bypassed, and written back to the
value found at the end (verified), and every strip assign is shut, so the
captured block is the converter lane at unity and nothing else.

Symbols: the BOOTED pair (pair.conf via d24_patch), never a default SYMDIR.
Rails: raised here, lowered here on every way out; CS_M driven high.

    cd /home/app/s160 && python3 -u s160_audit.py [--caps 6] [--only MIC2@63]
"""
import argparse
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)                       # dsp4_meascap / dsp4_bulk
sys.path.insert(1, '/home/app/selftest')       # d24_patch and its imports
import d24_patch as PT                         # noqa: E402
import dsp4_meascap as MC                      # noqa: E402

PLAN = [('MIC 1', 63), ('MIC 2', 63), ('MIC 3', 63), ('MIC 4', 63),
        ('MIC 5', 63), ('MIC 2', 0), ('MIC 2', 32), ('MIC 2', 48)]
SETTLE_MIN_S = 5.0
SETTLE_MAX_S = 20.0
SETTLE_AGREE_DB = 0.3


def lanes_from_list(plist):
    """MIC n -> (strip, send_pos), from the generated list (defs' input table),
    the same map the factory pass proved today: AUX 1 into MIC n arrived on
    lane n, isolated, for every n."""
    out = {}
    for r in plist.paths:
        if r.get('send_pos') not in (None, '') and str(r['lane']).isdigit() \
                and str(r['in']).startswith('MIC ') and 'line' not in r['in']:
            out[r['in']] = (int(r['lane']), int(r['send_pos']))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--caps', type=int, default=6)
    ap.add_argument('--n', type=int, default=16384)
    ap.add_argument('--only', default='')
    ap.add_argument('--seq', default='',
                    help='an ordered plan with repeats, e.g. MIC2@63,MIC2@48,'
                         'MIC2@63 -- files are tagged with their position')
    ap.add_argument('--out', default=os.path.join(HERE, 'data'))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    plan = PLAN
    if a.only:
        want = set(a.only.split(','))
        plan = [p for p in PLAN if '%s@%d' % (p[0].replace(' ', ''), p[1])
                in want]
    if a.seq:
        plan = [('MIC %s' % s.split('@')[0][3:], int(s.split('@')[1]))
                for s in a.seq.split(',')]
    plist = PT.PatchList(PT.find_list_dir())
    lanes = lanes_from_list(plist)
    u = PT.Unit()
    print('symbols: %s (booted pair)' % u.symdir, flush=True)
    sc = u.chip(1)
    an = PT.Analog(enabled=True, log=lambda s: print('   ..', s, flush=True),
                   own_rails=True)
    found = {}
    byp = plist.bypass()
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
        an.up()
        for k, (inp, code) in enumerate(plan):
            strip, pos = lanes[inp]
            tag = '%s_c%02d_open' % (inp.replace(' ', ''), code)
            if a.seq:
                tag = 'seq%02d_%s' % (k, tag)
            an.chain(an.step_image(pos, code), '%s at code %d' % (inp, code))
            u.meas_chan(strip)
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
            caps = []
            for i in range(a.caps):
                c = MC.capture(a.n, symdir=u.symdir, sc=sc,
                               log=lambda s: None)
                caps.append(dict(samples=c['samples'], overruns=c['overruns'],
                                 t=round(time.time() - t0, 2)))
            node = u.measure(None, 0.0, windows=4, settle=1)
            rec = dict(input=inp, strip=strip, send_pos=pos, code=code,
                       termination='open', symdir=u.symdir,
                       settle_trail=trail, node_rms=node.get('rms'),
                       node_rms_spread=node.get('rms_spread'),
                       captures=caps, stamp=time.strftime(
                           '%Y-%m-%dT%H:%M:%SZ', time.gmtime()))
            with open(os.path.join(a.out, tag + '.json'), 'w') as fh:
                json.dump(rec, fh)
            print('%-6s code %2d strip %2d: settled %.1f s, node RMS %.2f dBFS, '
                  '%d x %d captures, overruns %s'
                  % (inp, code, strip, trail[-1][0], node.get('rms'),
                     len(caps), a.n, [c['overruns'] for c in caps]),
                  flush=True)
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
