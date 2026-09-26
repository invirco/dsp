#!/usr/bin/env python3
"""bench-probe.py -- what the analog station can be proved to do with nobody
at the bench to plug a lead in (S121).

Runs ON THE UNIT. Everything here is a real write and a real read on the real
part; nothing is modelled. What it cannot prove is the copper, because that
needs a hand.

  1  THE IMAGE GUARD. The station refuses anything but a DSP4_TEST_NODES=1
     pair. Proved by pointing it at a shipping symbol map and requiring the
     refusal.
  2  THE STANDING WRITE. Every cell of it, written and read back on the part.
     This is the list's own cell names meeting the product's dispatch table
     for the first time, and it is the thing most likely to be wrong.
  3  THE FLOORS. All twenty-seven lanes the list measures, including the three
     codec return lanes -- the talkback XLR and the two mini-jack legs, which
     MeasChan 1..50 cannot reach at all.
  4  THE ROUTE, IN THE DIGITAL DOMAIN. The oscillator into the donor strip and
     the bus tap on the far side: MeasChan 33..46 name the buses, so a route
     can be proved to reach aux 1, aux 2, the main bus and the crossover
     without a cable existing. If the route cells were wrong, this is where it
     shows.
  5  THE DETECTOR. The auto-advance watches a lane's meter for a rise. Point
     the oscillator AT a measured strip and switch it on, and the same code
     path sees the same rise it would see from a lead going in. That proves
     the peek, the decibel arithmetic and the threshold on the part; only the
     connector is simulated.
  6  THE SECONDS. What one patch actually costs the machine.
  7  IS ANYTHING PATCHED? A sweep of all twenty-four mic lanes with each aux
     driven in turn, which finds any loop cable that happens to be on the
     bench and proves a whole analog path if one is.

It leaves the unit as it found it: oscillator off, every assign shut, the
monitor bus at zero and the rails wherever they were.
"""
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
for p in ('/home/app/selftest', HERE, os.path.join(HERE, '..', '..', '..', '..',
                                                   'tools', 'pi')):
    if os.path.isdir(p):
        sys.path.insert(0, os.path.abspath(p))

import d24_patch as PT                                        # noqa: E402

OUT = []


def say(s=''):
    print(s, flush=True)
    OUT.append(s)


def head(n, t):
    say('')
    say('=== %d. %s' % (n, t))


def main():
    shipping = sys.argv[1] if len(sys.argv) > 1 else '/home/app/dspboot'
    plist = PT.PatchList(PT.find_list_dir())
    lim = PT.Limits.load(plist.dir)
    say('list: %s -- %d patches, %d measurements'
        % (plist.dir, len(plist.patches), len(plist.paths)))

    # 1 ---------------------------------------------------------------------
    head(1, 'the image guard')
    try:
        PT.Unit(symdir=shipping)
        say('  !! NOT REFUSED: the station accepted %s. That is the failure the'
            % shipping)
        say('     guard exists to stop -- four zeros that look like a reading.')
    except SystemExit as e:
        say('  refused, correctly:')
        for ln in str(e).splitlines():
            say('    %s' % ln)
    except Exception as e:
        say('  refused with %s: %s' % (type(e).__name__, e))

    u = PT.Unit()
    say('  accepted the factory pair at %s' % PT.FACTORY_TEST_PAIR_DIR)

    # 2 ---------------------------------------------------------------------
    head(2, 'the standing write')
    donors = sorted({int(r['donor']) for r in plist.paths})
    cells = plist.standing(donors)
    t0 = time.time()
    bad = u.write(cells)
    dt = time.time() - t0
    say('  %d cells, %.2f s (%.1f ms each), %d did not read back'
        % (len(cells), dt, 1000.0 * dt / len(cells), len(bad)))
    if bad:
        say('  !! %s' % ', '.join(sorted(bad)[:12]))
    say('  the monitor bus: Level001=%.3f Level002=%.3f (the speaker is silent '
        'only if both are zero)'
        % (u.readf('Mon001Level001'), u.readf('Mon001Level002')))

    # 3 ---------------------------------------------------------------------
    head(3, 'the floors')
    u.osc(on=False)
    lanes = sorted({int(r['lane']) for r in plist.paths})
    floors = {}
    t0 = time.time()
    for lane in lanes:
        u.meas_chan(lane)
        floors[lane] = u.measure(None, 0.0).get('rms')
    dt = time.time() - t0
    say('  %d lanes in %.1f s (%.0f ms each)'
        % (len(lanes), dt, 1000.0 * dt / len(lanes)))
    for lane in lanes:
        name = ('MIC %d' % lane if lane <= 24 else
                {51: 'mini-jack tip', 53: 'talkback XLR',
                 55: 'mini-jack ring'}.get(lane, 'lane %d' % lane))
        say('    %-16s %8.2f dBFS' % (name, floors[lane]))

    # 4 ---------------------------------------------------------------------
    head(4, 'the route, in the digital domain')
    say('  the oscillator into the donor strip, read at the BUS tap on the far')
    say('  side. No cable is involved and none is needed: if the route cells')
    say('  were wrong this is where it shows.')
    BUS = {'aux:1': (35, 'aux 1'), 'aux:2': (36, 'aux 2'),
           'aux:1+2': (35, 'aux 1, with aux 2 driven too'),
           'main:L': (33, 'main L'), 'main:R': (34, 'main R')}
    donor = 24
    for drive, (code, label) in BUS.items():
        rid = '%s@%d' % (drive.replace(':', '').replace('+', 'p'), donor)
        if rid not in plist.routes:
            say('    %-10s no route in the list' % drive)
            continue
        u.write(plist.routes[rid])
        u.osc(chan=donor, freq=1000.0, level_dbfs=-12.0, on=True)
        u.meas_chan(code)
        m = u.measure(1000.0, -12.0)
        say('    %-10s -> %-28s %8.2f dBFS   THD+N %s'
            % (drive, label, m.get('rms', float('nan')),
               PT.dbpct(m.get('thd'))))
    u.write(plist.routes['%s@%d' % ('mainL', donor)])
    u.osc(chan=donor, freq=1000.0, level_dbfs=-12.0, on=True)
    u.meas_chan(34)
    m = u.measure(1000.0, -12.0)
    say('    main:L     -> main R (the OTHER side)   %8.2f dBFS  -- a pan that'
        % m.get('rms', float('nan')))
    say('               did not land would read the same on both')

    # 5 ---------------------------------------------------------------------
    head(5, 'the detector')
    say('  the auto-advance watches one lane and waits for it to rise. Here the')
    say('  oscillator is pointed AT a measured strip, so the same code sees the')
    say('  same rise a lead going in would make.')
    strip = 5
    u.osc(on=False)
    u.write(['Chan%03dMainOn001=0' % strip])
    time.sleep(0.2)
    base = u.meter_peak(strip)
    base_db = PT.dbv(base) if base else None
    u.osc(chan=strip, freq=1000.0, level_dbfs=-12.0, on=True)
    t0 = time.time()
    fired, lvl = None, None
    while time.time() - t0 < 3.0:
        v = u.meter_peak(strip)
        lvl = PT.dbv(v) if v else None
        if lvl is not None and base_db is not None and lvl - base_db >= lim['detect_rise_db']:
            fired = time.time() - t0
            break
        time.sleep(0.02)
    say('    MIC %d meter: %s dBFS quiet -> %s dBFS driven'
        % (strip, '%.1f' % base_db if base_db is not None else '--',
           '%.1f' % lvl if lvl is not None else '--'))
    if fired is not None:
        say('    the %.0f dB threshold fired %.0f ms after the tone started'
            % (lim['detect_rise_db'], 1000.0 * fired))
    else:
        say('    !! the threshold did NOT fire: the detector would time out and')
        say('       every patch would fall through to the wrong-socket sweep')
    u.osc(on=False)

    # 6 ---------------------------------------------------------------------
    head(6, 'the seconds')
    donor = 24
    u.write(plist.routes['aux1@%d' % donor])
    u.osc(chan=donor, freq=1000.0, level_dbfs=-12.0, on=True)
    u.meas_chan(35)
    t0 = time.time()
    for _ in range(3):
        u.measure(1000.0, -12.0)
    say('  one settled reading: %.0f ms' % (1000.0 * (time.time() - t0) / 3))
    t0 = time.time()
    for _ in range(5):
        u.write(plist.routes['aux1@%d' % donor])
    say('  one route assert (%d cells): %.0f ms'
        % (len(plist.routes['aux1@%d' % donor]),
           1000.0 * (time.time() - t0) / 5))
    t0 = time.time()
    for _ in range(5):
        u.meter_sweep(range(1, 25))
    say('  one 24-lane meter sweep: %.0f ms' % (1000.0 * (time.time() - t0) / 5))
    t0 = time.time()
    for _ in range(20):
        u.meter_peak(5)
    say('  one detector poll: %.1f ms' % (1000.0 * (time.time() - t0) / 20))

    # 7 ---------------------------------------------------------------------
    head(7, 'is anything actually patched?')
    say('  each aux driven in turn, every mic lane read. Anything lit is a lead')
    say('  somebody left on the bench -- and a whole analog path proved with it.')
    found = []
    for a in range(1, 9):
        u.write(plist.routes['aux%d@%d' % (a, donor)])
        u.osc(chan=donor, freq=1000.0, level_dbfs=-12.0, on=True)
        sweep = u.meter_sweep(range(1, 25))
        lit = [(PT.dbv(v), s) for s, v in sweep.items() if v and PT.dbv(v) > -70]
        lit.sort(reverse=True)
        if lit:
            say('    AUX %d -> %s' % (a, ', '.join('MIC %d at %.1f dBFS'
                                                   % (s, d) for d, s in lit[:3])))
            found.append((a, lit[0][1]))
    if not found:
        say('    nothing: no analog loop is cabled on the bench right now, so')
        say('    no copper can be proved from here.')
    else:
        for a, s in found:
            u.write(plist.routes['aux%d@%d' % (a, donor)])
            u.osc(chan=donor, freq=1000.0, level_dbfs=-12.0, on=True)
            u.meas_chan(s)
            m = u.measure(1000.0, -12.0)
            say('    AUX %d -> MIC %d: loop gain %.2f dB, phase %.1f deg, '
                'THD+N %s' % (a, s, m.get('h_db', float('nan')),
                              m.get('h_deg', float('nan')), PT.dbpct(m.get('thd'))))

    # handback -------------------------------------------------------------
    say('')
    say('=== handback')
    u.osc(on=False)
    u.write(plist.routes['_standing_close'], verify=False)
    u.write(['Mon001Level001=f0.0', 'Mon001Level002=f0.0'])
    say('  oscillator off, every assign shut, the monitor bus at zero')
    say('  Mon001Level001=%.3f Mon001Level002=%.3f'
        % (u.readf('Mon001Level001'), u.readf('Mon001Level002')))
    say('  Test001OscOn001=%d' % u.read('Test001OscOn001'))
    return 0


if __name__ == '__main__':
    rc = main()
    p = os.environ.get('PROBE_OUT')
    if p:
        with open(p, 'w') as fh:
            fh.write('\n'.join(OUT) + '\n')
    sys.exit(rc)
