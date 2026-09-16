#!/usr/bin/env python3
"""s64_fx.py [read|park|restore FILE] — the six chip-2 FX engines' On/Type cells: read them, park them (FxnOn 0, S23: an
engine at On 0 publishes zero and the wrapper parks the node), or put back a saved read."""
import json, sys
_ARGV = list(sys.argv)
import s64lib as L
T = L.T
R = T.Rig()
A = L.Rta(R)
c2 = A.c2
cmd = _ARGV[1] if len(_ARGV) > 1 else 'read'
names = ['Fx%03dOn001' % n for n in range(1, 7)] + ['Fx%03dType001' % n for n in range(1, 7)]
if cmd == 'read':
    st = {}
    for k in names:
        try:
            st[k] = c2.r(k)
        except Exception as e:
            st[k] = 'ERR %s' % e
    print(json.dumps(st))
elif cmd == 'park':
    for n in range(1, 7):
        c2.wv('Fx%03dOn001' % n, 0)
    print('parked', {k: c2.r(k) for k in names[:6]})
elif cmd == 'restore':
    st = json.load(open(_ARGV[2]))
    for k, v in st.items():
        if isinstance(v, int) and c2.r(k) != v:
            c2.wv(k, v)
    print('restored', {k: c2.r(k) for k in names})
