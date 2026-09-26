#!/usr/bin/env python3
"""The seven gain steps, on the part, through the station's own code -- and a
dead element caught.

WHY THIS AND NOT A LEAD. The station's gain step is three things in series: a
595 byte, a preamp, and a reading. Only the middle one needs a lead, and
nobody is at the bench. The other two are what S125 found wrong, so they are
what this proves, and it proves them through `Analog.step_image`,
`Station.gain_step` and `Scorer` themselves rather than a copy of them.

The preamp is replaced by arithmetic and nothing else is:

  a GOOD element    the drive is dropped by the step's expected gain and the
                    preamp makes it back up, so the converter sees the same
                    level at every step. Modelled by holding the oscillator
                    at GAIN_TONE_DBFS while the row still says the drive was
                    dropped -- which is exactly what a working preamp does to
                    the lane.
  a DEAD element    the drive is dropped and nothing makes it back up, so the
                    lane reads low by that element's own gain. Modelled by
                    actually setting the oscillator to the row's drive.

The 595 write is REAL (the chain is written and read back at every step), the
reading is REAL (the measurement node, through `Station.gain_step`), and the
verdict is REAL (`Scorer`, the same object the station scores a pass with).
"""
import argparse
import json
import sys

sys.path.insert(0, '/home/app/selftest')
import d24_patch as P                                      # noqa: E402


class Fixture(P.Unit):
    """The unit, with the preamp's effect on the lane done in arithmetic."""

    def __init__(self, dead=None, **kw):
        P.Unit.__init__(self, **kw)
        self.dead = set(dead or ())
        self.expect = {}
        self.code = None

    def osc(self, chan=None, freq=None, level_dbfs=None, on=None):
        if level_dbfs is not None and self.code is not None:
            want = self.expect.get(self.code, 0.0)
            # A working element puts back exactly what the drive took away.
            level_dbfs = level_dbfs + (0.0 if self.code in self.dead else want)
        P.Unit.osc(self, chan=chan, freq=freq, level_dbfs=level_dbfs, on=on)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--mic', type=int, default=7)
    ap.add_argument('--dead', type=int, action='append', default=[],
                    metavar='CODE', help='gain codes whose element is dead')
    ap.add_argument('--quick', default='/home/app/selftest/quick')
    ap.add_argument('--floor', type=float, default=-114.0,
                    help="the lane's own floor, measured on this unit")
    ap.add_argument('--out', default='/home/app/selftest/s125-gainproof.json')
    a = ap.parse_args()

    plist = P.PatchList(a.quick)
    rows = [r for r in plist.paths
            if r['in'] == 'MIC %d' % a.mic and str(r.get('gain_code') or '') != ''
            and r['expect'] != 'noise']
    if not rows:
        raise SystemExit('no gain rows for MIC %d in %s' % (a.mic, a.quick))
    u = Fixture(dead=a.dead)
    u.expect = dict((c, s['expected_db']) for c, s in plist.gain.items())
    an = P.Analog(enabled=True, log=lambda s: None)
    an.up()
    lim = P.Limits.load(plist.dir)
    st = P.Station(plist, u, None, None, lim, analog=an)
    sc = P.Scorer(lim)
    out = []
    try:
        lane = int(rows[0]['lane'])
        u.meas_chan(lane)
        u.osc(chan=lane, freq=float(rows[0]['freq_hz'] or 1000.0), on=True)
        sibs, secs = [], []
        for r in rows:
            u.code = int(r['gain_code'])
            t0 = P.now()
            m = st.gain_step(r)
            secs.append(P.now() - t0)
            v, why, notes = sc.score(r, m, a.floor, {}, sibs,
                                     donor=int(r['donor']))
            sibs.append(dict(level_ref=r['level_ref'], h_db=m.get('h_db'),
                             h_deg=m.get('h_deg'), gain_code=m.get('gain_code'),
                             rms=m.get('rms'), meter_db=m.get('meter_db'),
                             drive_dbfs=m.get('drive_dbfs')))
            out.append(dict(code=u.code, verdict=v, why=why, notes=notes,
                            rms=m.get('rms'), meter_db=m.get('meter_db'),
                            drive_dbfs=m.get('drive_dbfs'),
                            expected_db=m.get('expected_db'),
                            secs=secs[-1]))
            print('code %3d  %-7s  %.3f s  node %8.2f  meter %8s  %s'
                  % (u.code, v, secs[-1], m.get('rms') or float('nan'),
                     ('%.2f' % m['meter_db']) if m.get('meter_db') is not None
                     else '--', why))
        print('\n%d steps, %.3f s each, %.2f s for the input'
              % (len(secs), sum(secs) / len(secs), sum(secs)))
    finally:
        try:
            u.osc(on=False)
        except Exception:
            pass
        an.down()
    json.dump(out, open(a.out, 'w'), indent=1, default=str)
    print('wrote %s' % a.out)


if __name__ == '__main__':
    sys.exit(main())
