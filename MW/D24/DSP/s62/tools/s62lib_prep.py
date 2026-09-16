#!/usr/bin/env python3
"""s62lib_prep.py — fill TEST_MEAS's capture buffer with a real chirp (strip 6, -20 dBFS pk, post-fader), then
switch the chirp and the oscillator off so the buffer is static for s62_hammer.py (SYM=_meas_cap_buf_C1_TEST_MEAS).
Also times DIGITAL fast-battery captures (env CAPS, default 11): chirp on strip 6 captured on strip 6 through
dsp4_meascap (arm + fill + bulk read), the S61-3 capture step without the chain and the analog loop."""
import json, os, sys, time
os.environ['SYMDIR'] = '/home/app/s62'
sys.path.insert(0, '/home/app/dspboot'); sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s62')
import s54lib as T                                        # noqa: E402
import dsp4_meascap as MC                                 # noqa: E402
import dsp4_chirp as CH                                   # noqa: E402
X = T.X
R = T.Rig('/home/app/s62/s62_prep.jsonl')
A_SWEEPON, A_SWEEPSTEP = 4979, 4980
R.wv(A_SWEEPSTEP, 0)
R.wv(T.A_OSCLEVEL, X.f32(10 ** (-20 / 20.0)))
R.wv(T.A_OSCCHAN, 6)
R.wv(T.A_OSCON, 1)
R.wv(A_SWEEPON, 1)
if R.rd(T.A_MEASCHAN) != 6:
    R.wv(T.A_MEASCHAN, 6)
L = CH.period(0)
time.sleep(1.2 * L / 48000.0)
rows = []
for k in range(int(os.environ.get('CAPS', '11'))):
    t0 = time.time()
    lines = []
    cap = MC.capture(16384, '/home/app/s62', sc=R.sc, log=lines.append)
    rows.append({'k': k, 't_capture_s': round(time.time() - t0, 3), 'read_s': cap.get('read_s'),
                 'overruns': cap.get('overruns'), 'nonzero': sum(1 for v in cap['samples'] if v)})
    T.log({'ev': 'digcap', **rows[-1], 'lines': lines[-3:]})
    print(json.dumps(rows[-1]), flush=True)
R.wv(A_SWEEPON, 0)
R.wv(T.A_OSCON, 0)
ts = sorted(r['t_capture_s'] for r in rows)
rs = sorted(r['read_s'] for r in rows)
print(json.dumps({'ev': 'digcap_summary', 'n': len(rows), 't_capture_med': ts[len(ts) // 2], 't_capture_max': ts[-1],
                  'read_med': rs[len(rs) // 2], 'read_max': rs[-1], 'overruns': sum(r['overruns'] or 0 for r in rows)}))
