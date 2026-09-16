"""s52_quietcap.py <node> <out> [quiet_s] [pre_s] — scope capture with NO SPI traffic during the 21 ms window.
Sets src/inj/amp/mode (verified), then ONE ARM write, then silence for quiet_s, then verifies the run
counter advanced and fetches. pre_s: extra silence before the ARM write (default 0)."""
import sys, time, json
A = sys.argv[1:]
import s52lib as X
S = X.S
node, out = A[0], A[1]
quiet = float(A[2]) if len(A) > 2 else 0.5
pre = float(A[3]) if len(A) > 3 else 0.0
import os
CH = int(os.environ.get("CHIP", "1"))
c1 = X.Chip(CH); sc = c1.sc
sym = node if node.startswith('_') else '_buf_%s' % node
sc.d.write(S.SCOPE_ARM, 0); time.sleep(S.SETTLE)
sc.wr(S.SCOPE_SRC, sc.sym[sym]); sc.wr(S.SCOPE_INJ, 0); sc.wr(S.SCOPE_AMP, 0); sc.wr(S.SCOPE_MODE, 0)
before = sc.rd(S.SCOPE_RUNS)
time.sleep(pre)
t0 = time.time()
sc.d.write(S.SCOPE_ARM, 1)
time.sleep(quiet)
after = sc.rd(S.SCOPE_RUNS)
print('runs %s -> %s (%s), quiet %.2f s after the arm write' % (before, after, 'ARMED' if after != before else 'NOT ARMED', quiet))
if after == before:
    raise SystemExit(2)
vals = sc.fetch(1024)
json.dump({'tool': 's52_quietcap', 'version': 1, 'fs_hz': 48000, 'node': sym, 'scale': 'q4.28', 'lanes': 1,
           'symdir': X.SYMDIR, 'samples': vals}, open(out, 'w'))
print('wrote', out)
