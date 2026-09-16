"""s55_preflight.py — base image, TEST_OSC 1 kHz -20 dBFS via donor 6 then donor 1 then back to 6; AUX 1 TX lane read
each time (chip 2 peeks, 1.0 = DAC FS); one lane scan printed. Leaves the WATCH state (tone on strip 6 -> AUX 1)."""
import math, sys
sys.path.insert(0, '/home/app/s55')
import s55_run as S
T, X = S.T, S.X
R = S.S55()
c2 = X.Chip(2); sc2 = c2.sc


def aux1():
    ptrs, offs, strd = sc2.sym['_c2_tx_ptrs'], sc2.sym['_c2_tx_off'], sc2.sym['_c2_tx_stride']
    want = sc2.sym['_tx_out_slot_C2_AUX_OUT_01']
    idx = [i for i in range(24) if sc2.peek(ptrs + i) == want][0]
    w = []
    while len(w) < 800:
        try:
            b = sc2.peek(sc2.sym['_tx_active_buf'])
            w.extend(X.s32(sc2.peek(b + sc2.peek(offs + idx) + k * sc2.peek(strd + idx))) / 2.0 ** 31 for k in range(16))
        except IOError:
            pass
    return 20 * math.log10(max(abs(x) for x in w))


S.P('AN_EN', R.an_en())
S.P('image', R.chain(0))
for d in (6, 1, 6):
    S.P('donor %d, strips on AUX 1: %s' % (d, R.set_donor(d)))
    R.osc(1000.0, -20.0)
    S.P('  AUX 1 TX lane peak %.2f dBFS' % aux1())
res = R.scan([c[2] for c in S.CHANNELS])
S.P('scan: ' + '  '.join('L%d %.1f' % (n, v[1]) for n, v in sorted(res.items())))
