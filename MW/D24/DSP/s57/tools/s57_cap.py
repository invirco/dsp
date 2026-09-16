"""s57_cap.py <tag> <code> <count> [gap_s] [tone] — MIC 5 at <code> (150 ohm on J25), MeasChan 20, TEST_OSC off
(or 1 kHz -20 dBFS pk on AUX 1 when tone=1), <count> 16k capture-arm captures of strip 20 post-fader, start-to-start
<gap_s> apart (0 = back to back). Each capture saved as data/<tag>_<i>.json with wall time, overruns and one TEST_MEAS
window (RmsResult) taken straight after it."""
import json, os, sys, time
os.environ.setdefault('SYMDIR', '/home/app/s56')
A = sys.argv[1:]
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s56')
import s54lib as T
import dsp4_meascap as MC
tag, code, count = A[0], int(A[1]), int(A[2])
gap = float(A[3]) if len(A) > 3 else 0.0
tone = int(A[4]) if len(A) > 4 else 0
D = '/home/app/s57/data'
os.makedirs(D, exist_ok=True)
r = T.Rig(logpath='/home/app/s57/s57_cap.jsonl')
r.meas(20)
if tone:
    r.osc(1000.0, -20.0, on=True)
else:
    r.osc(on=False)
p15 = r.chain(code)
print('code %d  %s  tone %d' % (code, p15, tone), flush=True)
r.windows(1, settle_windows=60, tag='%s:settle' % tag)
t_start = time.time()
for i in range(count):
    if gap:
        while time.time() < t_start + i * gap:
            time.sleep(0.2)
    t0 = time.time()
    cap = MC.capture(16384, '/home/app/s56', sc=r.sc, log=lambda *a: None)
    node = r.windows(1, settle_windows=1, tag='%s_%d' % (tag, i))
    cap.update({'t_arm': round(t0, 3), 'code': code, 'tone': tone, 'tag': tag, 'idx': i, 'p15': p15,
                'node_rms_dbfs': node['rows'][0]['rms']})
    json.dump(cap, open('%s/%s_%02d.json' % (D, tag, i), 'w'))
    T.log({'ev': 'cap', 'tag': tag, 'idx': i, 'code': code, 'tone': tone, 't_arm': round(t0, 3),
           'overruns': cap['overruns'], 'n': len(cap['samples']), 'node_rms': node['rows'][0]['rms']})
    print('%s_%02d  t+%.0f s  n %d  ovr +%d  node RMS %.2f dBFS' % (tag, i, t0 - t_start, len(cap['samples']),
          cap['overruns'], node['rows'][0]['rms']), flush=True)
