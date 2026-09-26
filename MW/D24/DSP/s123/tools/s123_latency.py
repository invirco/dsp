#!/usr/bin/env python3
"""s123_latency.py -- how long after the lead goes in does the screen say so?

S123 item 2 sets a target -- "Signal found" on the glass within 0.5 s of the
lead going into the socket -- and asks for it measured. Nobody in this session
can plug a lead, so the copper is the one link in the chain this cannot
exercise. Everything on either side of it can be, and is, ON THE PART:

    the lead goes in
      -> the lane's meter rises            <- REPLACED HERE by turning the
                                              station's own oscillator on into
                                              the strip the detector is
                                              watching. Same word, same peek,
                                              same rise.
      -> the detector's next poll sees it        MEASURED: t_seen - t_stimulus
      -> the runner writes runall/live.json      (the write is inside that)
      -> the display's watcher/tick reads it     MEASURED: the display's own
      -> the screen is drawn                     latency log, written by the
                                                 app when it applies a status

The detector here is not a copy of the station's: `watch()` and the poll
interval come out of d24_patch itself, so a change to either moves this
measurement with it.

    s123_latency.py --trials 12 [--strip 24] [--live /home/app/selftest/runall]
"""
import argparse
import math
import os
import sys
import time

sys.path.insert(0, '/home/app/selftest')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', '..', '..', '..', 'tools', 'pi'))
import d24_patch as P                                   # noqa: E402
import d24_live as LV                                   # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--trials', type=int, default=12)
    ap.add_argument('--strip', type=int, default=24,
                    help='the strip the oscillator is injected into and the '
                         'detector watches: the station\'s own donor')
    ap.add_argument('--settle', type=float, default=2.0,
                    help='seconds of quiet before the stimulus, so the lane\'s '
                         'meter has fallen back from the trial before')
    ap.add_argument('--live', default='/home/app/selftest/runall')
    ap.add_argument('--list-dir', default='/home/app/selftest/quick')
    ap.add_argument('--symdir', default=P.FACTORY_TEST_PAIR_DIR)
    a = ap.parse_args(argv)

    plist = P.PatchList(a.list_dir)
    lim = P.Limits.load(plist.dir)
    rise = lim['detect_rise_db']
    u = P.Unit(symdir=a.symdir)
    live = LV.Live(a.live, run='patch', total=len(plist.patches))
    row = plist.paths[4] if len(plist.paths) > 4 else plist.paths[0]

    st = P.Station(plist, u, P.pick_patcher(None), None, lim, live=live)
    print('stimulus: the oscillator into strip %d; detector: the same '
          'watch() the station uses; rise %.1f dB' % (a.strip, rise))

    out = []
    try:
        u.osc(on=False)
        time.sleep(0.3)
        for n in range(a.trials):
            live.set(state=LV.WAITING, instruction=LV.instruction_for(row),
                     lead_line='', extra='', n=n + 1, lead_n=1, lead_total=4)
            # ONE loop, exactly the shape of the station's detect(): the
            # baseline is the quietest the lane has been SINCE THE PROMPT WENT
            # UP, updated on every poll, so a meter still decaying from the
            # trial before lowers it instead of hiding the next rise. The
            # stimulus is applied part way through that same loop.
            lo = None
            t_open = time.time()
            t0 = None
            t_seen = None
            seq = None
            deadline = t_open + 8.0
            while time.time() < deadline:
                live.beat()
                v = st.watch(a.strip)
                if v is not None and math.isfinite(v):
                    lo = v if lo is None else min(lo, v)
                    if t0 is not None and v - lo >= rise:
                        t_seen = time.time()
                        live.set(state=LV.CHECKING)
                        seq = live.seq
                        break
                if t0 is None and time.time() - t_open >= a.settle:
                    t0 = time.time()               # "the lead goes in"
                    u.osc(chan=a.strip, freq=1000.0, level_dbfs=-12.0, on=True)
                time.sleep(0.05)
            u.osc(on=False)
            if t_seen is None:
                print('  %2d  NO RISE' % (n + 1))
                continue
            out.append((seq, t0, t_seen))
            print('  %2d  seq %d  stimulus -> detector %.3f s'
                  % (n + 1, seq, t_seen - t0))
            time.sleep(0.5)
    finally:
        try:
            u.osc(on=False)
        except Exception:
            pass
        live.clear()

    if not out:
        return 1
    d = sorted(t - s for _q, s, t in out)
    print('\nstimulus -> detector: n=%d  min %.3f  median %.3f  max %.3f s'
          % (len(d), d[0], d[len(d) // 2], d[-1]))
    with open('/home/app/selftest/s123-latency-stimulus.csv', 'w') as fh:
        fh.write('seq,t_stimulus,t_detector\n')
        for q, s, t in out:
            fh.write('%d,%.3f,%.3f\n' % (q, s, t))
    print('wrote /home/app/selftest/s123-latency-stimulus.csv')
    return 0


if __name__ == '__main__':
    sys.exit(main())
