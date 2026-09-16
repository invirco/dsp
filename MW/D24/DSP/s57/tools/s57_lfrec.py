"""s57_lfrec.py <tag> <seconds> — a long, slow record of MIC 5's raw RX lane (strip 20's converter slot, rx24in32,
before any strip processing): one live RX word peeked per sample, wall-clock stamped, for <seconds>. At ~600 point
samples/s the audio-band noise aliases flat across 0-300 Hz, and anything concentrated below a few Hz stands far
above it -- the record the 0.34 s capture is too short to give (is the sub-20 Hz wander periodic, and at what rate).
No chain write: the code is whatever was set last."""
import json, os, sys, time
os.environ.setdefault('SYMDIR', '/home/app/s56')
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s56')
import s54lib as T
X = T.X
tag, secs = sys.argv[1], float(sys.argv[2])
r = T.Rig(logpath='/home/app/s57/s57_lfrec.jsonl')
sc = r.sc
e = sc.peek(sc.sym['_c1_rx_node_entry'] + 20 - 1)
off = sc.peek(sc.sym['_c1_rx_off'] + e); st = sc.peek(sc.sym['_c1_rx_stride'] + e)
bufs = sc.sym['_rx_active_buf']
t, v = [], []
t0 = time.time(); errs = 0
while time.time() - t0 < secs:
    try:
        b = sc.peek(bufs)
        w = sc.peek(b + off)
    except (IOError, OSError):
        errs += 1; continue
    t.append(round(time.time() - t0, 5)); v.append(X.s32(w))
json.dump({'tool': 's57_lfrec', 'tag': tag, 'entry': e, 'off': off, 'stride': st, 't0': t0, 't': t, 'v': v,
           'scale': 'rx24in32', 'errs': errs}, open('/home/app/s57/data/lf_%s.json' % tag, 'w'))
print('lf_%s: %d samples in %.1f s (%.0f/s), %d link errors' % (tag, len(v), secs, len(v) / secs, errs), flush=True)
