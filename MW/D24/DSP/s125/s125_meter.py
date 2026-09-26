#!/usr/bin/env python3
"""s125_meter.py -- is the strip meter an honest instrument for a gain step?

Runs ON the unit. Reads nothing the patch station does not already read and
writes nothing it does not already write; it just does it slowly enough to see
what the station's one 50 ms peek cannot.

THE QUESTION (review flag A, S125 item 1). `d24_patch.py gain_step()` writes
the mic-pre chain first (gain UP, 6-13 dB), lowers the oscillator second, waits
50 ms and peeks the strip meter. The meter LATCHES peaks and decays slowly, so:

  * the transient between the two writes -- old drive at the NEW gain -- is a
    genuine level, it is the loudest thing in the window, and the meter holds
    it. A step then reads HIGH by about its own size.
  * reverse the order and a step whose element is DEAD reads the previous
    step's peak instead of its own silence, and PASSES.

Both are properties of the METER, not of the analog path, so both can be
measured with the oscillator alone, on a strip with no lead in it.

  --decay      how fast the peak falls, dB/s, from a real step down
  --latch      the two-write transient, the coded order and the reverse
  --node       the measurement node's cost and reading for the same change
  --steps N    the seven gain steps on input N with NO LEAD, meter vs node
  --all        every one of the above

Nothing here raises AN_EN by itself unless --rails is given, and --rails also
lowers them again at the end.
"""
import argparse
import json
import os
import statistics
import sys
import time

sys.path.insert(0, '/home/app/selftest')
import d24_patch as P                                      # noqa: E402


def dbv(x):
    return P.dbv(x)


def peak(u, strip):
    return u.meter_peak(strip)


def peak_db(u, strip):
    import math
    v = peak(u, strip)
    if not v:
        return None
    d = dbv(v)
    return d if math.isfinite(d) else None


# ---------------------------------------------------------------------------
def decay(u, strip, high_dbfs, low_dbfs, seconds, dt):
    """Drive the strip hard, drop the drive in ONE write, then watch the peak.

    The drop is a single cell write, so whatever the meter does afterwards is
    the meter and not the stimulus. The RmsResult of the measurement node is
    read in the same breath as the second opinion: it has no peak hold, so it
    shows where the signal ACTUALLY is while the meter is still coming down.
    """
    u.meas_chan(strip)
    u.osc(chan=strip, freq=1000.0, level_dbfs=high_dbfs, on=True)
    time.sleep(0.5)
    before = peak_db(u, strip)
    t0 = time.time()
    u.osc(level_dbfs=low_dbfs)
    rows = []
    while time.time() - t0 < seconds:
        t = time.time() - t0
        rows.append(dict(t=t, meter_db=peak_db(u, strip)))
        time.sleep(dt)
    u.osc(on=False)
    # The slope over the part of the record that is actually decaying: from the
    # first sample at least 1 dB below the start to the last one at least 1 dB
    # above the floor the drive sets.
    pts = [x for x in rows
           if x['meter_db'] is not None
           and x['meter_db'] < before - 1.0
           and x['meter_db'] > low_dbfs + 1.0]
    slope = None
    if len(pts) >= 3:
        n = float(len(pts))
        mt = sum(x['t'] for x in pts) / n
        md = sum(x['meter_db'] for x in pts) / n
        stt = sum((x['t'] - mt) ** 2 for x in pts)
        if stt:
            slope = sum((x['t'] - mt) * (x['meter_db'] - md) for x in pts) / stt
    return dict(strip=strip, high_dbfs=high_dbfs, low_dbfs=low_dbfs,
                before_db=before, rows=rows, n_fitted=len(pts),
                decay_db_per_s=slope)


# ---------------------------------------------------------------------------
def latch(u, strip, base_dbfs, step_db, settle_s, reps):
    """The two-write transient, exactly as the station times it.

    The chain write cannot be modelled with a lead out, so the OSCILLATOR
    stands in for it: raising the drive by `step_db` puts the same level on the
    lane that raising the preamp gain by `step_db` would. The point being
    tested is the METER's response to two writes a few milliseconds apart, and
    that is identical either way.

      coded    up by step_db (the 'gain'), then down by step_db (the 'drive')
               -- the order gain_step() uses
      reverse  down first, then up -- the order the review proposes
      settled  one write straight to the target, the truth to compare against
    """
    out = {'strip': strip, 'base_dbfs': base_dbfs, 'step_db': step_db,
           'settle_s': settle_s, 'coded': [], 'reverse': [], 'settled': []}
    u.meas_chan(strip)
    for _ in range(reps):
        # settled: the honest answer. Park well away first so no earlier peak
        # can be what we read.
        u.osc(chan=strip, freq=1000.0, level_dbfs=base_dbfs - 40.0, on=True)
        time.sleep(1.5)
        u.osc(level_dbfs=base_dbfs)
        time.sleep(settle_s)
        out['settled'].append(peak_db(u, strip))

        u.osc(level_dbfs=base_dbfs - 40.0)
        time.sleep(1.5)
        t0 = time.time()
        u.osc(level_dbfs=base_dbfs + step_db)     # 'gain up'
        u.osc(level_dbfs=base_dbfs)               # 'drive down'
        gap = time.time() - t0
        time.sleep(settle_s)
        out['coded'].append(dict(db=peak_db(u, strip), write_gap_s=gap))

        u.osc(level_dbfs=base_dbfs - 40.0)
        time.sleep(1.5)
        t0 = time.time()
        u.osc(level_dbfs=base_dbfs - step_db)     # 'drive down' first
        u.osc(level_dbfs=base_dbfs)               # 'gain up'
        gap = time.time() - t0
        time.sleep(settle_s)
        out['reverse'].append(dict(db=peak_db(u, strip), write_gap_s=gap))
    u.osc(on=False)
    return out


def stale_peak(u, strip, base_dbfs, settle_s, reps):
    """The second failure the review names: a step that is DEAD reading the
    PREVIOUS step's peak and passing.

    'Dead' is modelled the only way it can be with no lead: the drive goes to
    silence where the step expects a level. If the meter still reads the old
    peak `settle_s` later, a dead element cannot be caught off the meter.
    """
    out = {'strip': strip, 'base_dbfs': base_dbfs, 'settle_s': settle_s,
           'after_dead_db': [], 'node_after_dead_db': []}
    u.meas_chan(strip)
    for _ in range(reps):
        u.osc(chan=strip, freq=1000.0, level_dbfs=base_dbfs, on=True)
        time.sleep(1.5)
        out.setdefault('live_db', []).append(peak_db(u, strip))
        u.osc(on=False)                           # the element is dead
        time.sleep(settle_s)
        out['after_dead_db'].append(peak_db(u, strip))
        m = u.measure(None, 0.0, windows=1, settle=0)
        out['node_after_dead_db'].append(m.get('rms'))
    return out


# ---------------------------------------------------------------------------
def node_cost(u, strip, base_dbfs, settles, reps):
    """What the measurement node costs and reads for the same change.

    One number per settle length, so the honest reading's price is measured
    rather than assumed from WIN_S.
    """
    out = []
    u.meas_chan(strip)
    for settle in settles:
        for _ in range(reps):
            u.osc(chan=strip, freq=1000.0, level_dbfs=base_dbfs - 40.0, on=True)
            time.sleep(1.0)
            t0 = time.time()
            u.osc(level_dbfs=base_dbfs + 12.0)
            u.osc(level_dbfs=base_dbfs)
            m = u.measure(1000.0, base_dbfs, windows=P.READ_WINDOWS,
                          settle=settle)
            out.append(dict(settle=settle, secs=time.time() - t0,
                            rms=m.get('rms'), thd=m.get('thd'),
                            h_db=m.get('h_db')))
    u.osc(on=False)
    return out


# ---------------------------------------------------------------------------
def seven_steps(u, an, plist, mic, reps, settle_s):
    """The seven steps on one input with NO LEAD: the lane's own noise.

    With nothing plugged in there is no tone to drive, so the oscillator write
    the station makes is a no-op on this lane and the ONLY thing that moves is
    the preamp gain. That is the cleanest possible look at what the two
    instruments say about the same seven chain images: a preamp's own noise
    rises with its gain, and the meter and the node have to agree about by how
    much or one of them is not measuring the element.
    """
    steps = sorted(plist.gain.items())
    out = {'mic': mic, 'reps': reps, 'settle_s': settle_s, 'runs': []}
    u.osc(on=False)
    u.meas_chan(mic)
    pos = None
    for r in plist.paths:
        if str(r.get('in') or '') == 'MIC %d' % mic and r.get('send_pos') != '':
            pos = int(r['send_pos'])
            break
    if pos is None:
        raise SystemExit('MIC %d has no send position in the list' % mic)
    out['send_pos'] = pos
    for rep in range(reps):
        run = []
        for code, spec in steps:
            t0 = time.time()
            an.image = None
            an.chain(an.step_image(pos, code),
                     'gain step, MIC %d at code %d' % (mic, code))
            time.sleep(settle_s)
            mtr = peak_db(u, mic)
            t_meter = time.time() - t0
            m = u.measure(None, 0.0, windows=P.GAIN_READ_WINDOWS,
                          settle=P.GAIN_SETTLE_WINDOWS)
            run.append(dict(code=code, expected_db=spec.get('expected_db'),
                            meter_db=mtr, node_rms=m.get('rms'),
                            meter_s=t_meter, total_s=time.time() - t0))
        out['runs'].append(run)
    return out


# ---------------------------------------------------------------------------
def honest(u, strip, base_dbfs, grid, reps):
    """What each (settle, windows) pair costs and whether it can tell a live
    element from a dead one.

    Two readings per point, taken the way a gain step takes them: one with the
    level there (LIVE) and one with the oscillator off (DEAD, which is an open
    or shorted element as far as the lane is concerned). A reading that cannot
    separate those two by more than the step tolerance is not a test.
    """
    out = []
    u.meas_chan(strip)
    for settle, windows in grid:
        for _ in range(reps):
            u.osc(chan=strip, freq=1000.0, level_dbfs=base_dbfs - 40.0, on=True)
            time.sleep(1.0)
            t0 = time.time()
            u.osc(level_dbfs=base_dbfs)
            live = u.measure(1000.0, base_dbfs, windows=windows, settle=settle)
            t_live = time.time() - t0
            t0 = time.time()
            u.osc(on=False)
            dead = u.measure(1000.0, base_dbfs, windows=windows, settle=settle)
            t_dead = time.time() - t0
            u.osc(on=True)
            out.append(dict(settle=settle, windows=windows,
                            live_rms=live.get('rms'), dead_rms=dead.get('rms'),
                            live_s=t_live, dead_s=t_dead,
                            live_meter=peak_db(u, strip)))
    u.osc(on=False)
    return out


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--strip', type=int, default=P.DONOR_DEFAULT)
    ap.add_argument('--mic', type=int, default=2)
    ap.add_argument('--reps', type=int, default=5)
    ap.add_argument('--settle', type=float, default=0.05)
    ap.add_argument('--decay', action='store_true')
    ap.add_argument('--latch', action='store_true')
    ap.add_argument('--node', action='store_true')
    ap.add_argument('--steps', action='store_true')
    ap.add_argument('--honest', action='store_true')
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--rails', action='store_true',
                    help='raise AN_EN for the run and lower it at the end '
                         '(needed for --steps; the rest are digital)')
    ap.add_argument('--quick', default='/home/app/selftest/quick')
    ap.add_argument('--out', default='/home/app/selftest/s125-meter.json')
    a = ap.parse_args()
    if a.all:
        a.decay = a.latch = a.node = a.steps = a.honest = True
    if not (a.decay or a.latch or a.node or a.steps or a.honest):
        ap.error('nothing selected: one of --decay --latch --node --honest '
                 '--steps --all')

    u = P.Unit()
    res = {'stamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
           'strip': a.strip, 'settle_s': a.settle}
    an = None
    if a.steps:
        an = P.Analog(enabled=True, log=lambda s: print('   %s' % s))
        if a.rails:
            an.up()
    try:
        if a.decay:
            print('-- decay')
            res['decay'] = decay(u, a.strip, -6.0, -46.0, 4.0, 0.02)
            print('   %.2f dB/s over %d points (from %.2f dBFS)'
                  % (res['decay']['decay_db_per_s'] or float('nan'),
                     res['decay']['n_fitted'], res['decay']['before_db']))
        if a.latch:
            print('-- latch')
            res['latch'] = latch(u, a.strip, -18.0, 12.845, a.settle, a.reps)
            for k in ('settled', 'coded', 'reverse'):
                vals = [x if isinstance(x, float) else x['db']
                        for x in res['latch'][k]]
                vals = [v for v in vals if v is not None]
                if vals:
                    print('   %-8s %8.2f dBFS  (spread %.2f, n %d)'
                          % (k, statistics.median(vals),
                             max(vals) - min(vals), len(vals)))
            res['stale'] = stale_peak(u, a.strip, -18.0, a.settle, a.reps)
            print('   stale    live %s -> after the element died %s (node %s)'
                  % (['%.2f' % v for v in res['stale'].get('live_db', []) if v],
                     ['%.2f' % v for v in res['stale']['after_dead_db'] if v],
                     ['%.2f' % v for v in res['stale']['node_after_dead_db']
                      if v is not None]))
        if a.node:
            print('-- node')
            res['node'] = node_cost(u, a.strip, -18.0, (0, 1, 2, 4), a.reps)
            for settle in (0, 1, 2, 4):
                xs = [x for x in res['node'] if x['settle'] == settle]
                if xs:
                    print('   settle %d: %.3f s, rms %s'
                          % (settle,
                             statistics.median(x['secs'] for x in xs),
                             ['%.2f' % x['rms'] for x in xs
                              if x['rms'] is not None]))
        if a.honest:
            print('-- honest: cost and separation, live against dead')
            grid = [(0, 1), (1, 1), (2, 1), (2, 2), (3, 2), (4, 2)]
            res['honest'] = honest(u, a.strip, -18.0, grid, a.reps)
            for settle, windows in grid:
                xs = [x for x in res['honest']
                      if x['settle'] == settle and x['windows'] == windows]
                lv = [x['live_rms'] for x in xs if x['live_rms'] is not None]
                dd = [x['dead_rms'] for x in xs if x['dead_rms'] is not None]
                if not lv or not dd:
                    continue
                print('   settle %d win %d: %.3f s  live %7.2f (spread %.2f)  '
                      'dead %7.2f (spread %.2f)  separation %6.2f dB'
                      % (settle, windows,
                         statistics.median(x['live_s'] for x in xs),
                         statistics.median(lv), max(lv) - min(lv),
                         statistics.median(dd), max(dd) - min(dd),
                         statistics.median(lv) - statistics.median(dd)))
        if a.steps:
            print('-- seven steps on MIC %d, no lead' % a.mic)
            plist = P.PatchList(a.quick)
            res['steps'] = seven_steps(u, an, plist, a.mic, a.reps, a.settle)
            for run in res['steps']['runs']:
                print('   ' + '  '.join(
                    '%d:%s' % (x['code'],
                               ('%.1f' % x['meter_db']) if x['meter_db'] else '--')
                    for x in run))
    finally:
        try:
            u.osc(on=False)
        except Exception:
            pass
        if an is not None:
            an.down()
    with open(a.out, 'w') as fh:
        json.dump(res, fh, indent=1, default=str)
    print('\nwrote %s' % a.out)


if __name__ == '__main__':
    sys.exit(main())
