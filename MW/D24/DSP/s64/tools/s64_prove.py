#!/usr/bin/env python3
"""s64_prove.py — gate 2 through the digital loop: tones 63 Hz / 1 kHz / 8 kHz at -20 dBFS pk on strip 6 -> AUX 1 -> the
RTA's L; the right band at the right dBFS (expected -23.01, and TEST_MEAS on strip 6 as the measured reference) within
0.5 dB, the one-octave neighbours (band +-3) >= 40 dB down, R (AUX 2) silent; then the source swapped (L = AUX 2, R = AUX 1)
at 1 kHz so the tone must move to R only. Every table row is the median of 3 reads of all 62 words."""
import json, os, statistics as st, time
import s64lib as L
T = L.T
R = T.Rig(os.environ['SYMDIR'] + '/s64_prove.jsonl')
A = L.Rta(R)
SRC_A = os.environ.get('SRCL', 'C2_MIX_AUX_01')
SRC_B = os.environ.get('SRCR', 'C2_MIX_AUX_02')
T.log({'ev': 'src', 'L': SRC_A, 'R': SRC_B})
print('source L', SRC_A, 'R', SRC_B)
A.wr(L.RTA_MODE, 0)
A.src(SRC_A, SRC_B)
A.wr(L.RTA_ON, 1)
s0 = A.sc.rd_counter(L.RTA_SEQ); time.sleep(0.5); s1 = A.sc.rd_counter(L.RTA_SEQ)
print('RTA_SEQ advances %d in 0.5 s (%.0f blocks/s)' % (s1 - s0, (s1 - s0) / 0.5))
T.log({'ev': 'seq', 'd': s1 - s0})
EXP = 10 * __import__('math').log10(0.1 ** 2 / 2)


def med_bands(n=3):
    Ls, Rs = [], []
    for _ in range(n):
        l, r = A.bands(); Ls.append(l); Rs.append(r)
    return [st.median(c) for c in zip(*Ls)], [st.median(c) for c in zip(*Rs)]


rows = []
for f, swap in ((63.0, False), (1000.0, False), (8000.0, False), (1000.0, True)):
    if swap:
        A.src(SRC_B, SRC_A)
    R.osc(freq=f, level_db=-20.0, on=True, chan=6)
    R.meas(6)
    ref = R.windows(2, settle_windows=3, tag='ref%d' % f)
    ref_rms = T.summ(ref, 'rms')
    time.sleep(1.0)
    l, r = med_bands()
    hot, cold = (r, l) if swap else (l, r)
    i = L.nearest(f)
    nb = {L.LABELS[j]: round(hot[i] - hot[j], 2) for j in (i - 3, i + 3) if 0 <= j < 31}
    row = {'f': f, 'swap': swap, 'band': L.LABELS[i], 'hot_db': round(hot[i], 3), 'expected': round(EXP, 3),
           'err_db': round(hot[i] - EXP, 3), 'testmeas_rms': ref_rms, 'err_vs_testmeas': round(hot[i] - ref_rms, 3),
           'oct_down_db': nb, 'adjacent': {L.LABELS[j]: round(hot[i] - hot[j], 2) for j in (i - 1, i + 1) if 0 <= j < 31},
           'cold_max_db': round(max(cold), 2), 'cold_same_band_db': round(cold[i], 2),
           'hot': [round(v, 2) for v in hot], 'cold': [round(v, 2) for v in cold]}
    row['pass'] = abs(row['err_db']) <= 0.5 and all(v >= 40 for v in nb.values()) and row['cold_max_db'] < hot[i] - 60
    rows.append(row)
    T.log(dict(ev='tone', **row))
    print(json.dumps({k: v for k, v in row.items() if k not in ('hot', 'cold')}))
A.src(SRC_A, SRC_B)
print('TONES PASS' if all(r_['pass'] for r_ in rows) else 'TONES FAIL')

# ---- ballistics on the 1 kHz band: decay slope after the tone stops, fast and slow; then peak-hold and its reset ----
import math
i1k = L.nearest(1000.0)


def decay(mode, span_s):
    A.wr(L.RTA_MODE, mode)
    R.osc(freq=1000.0, level_db=-20.0, on=True, chan=6)
    time.sleep(1.5)
    R.wv(T.A_OSCON, 0)
    t0 = time.time(); pts = []
    while time.time() - t0 < span_s:
        pts.append((time.time() - t0, A.band('L', i1k)))
    # slope over the points between -3 and -40 dB below the first reading
    top = pts[0][1]
    sel = [(t, v) for t, v in pts if top - 40 < v < top - 3]
    n = len(sel)
    if n < 3:
        return {'mode': mode, 'points': n, 'fail': 'too few points', 'top': top}
    mt = sum(t for t, _ in sel) / n; mv = sum(v for _, v in sel) / n
    slope = sum((t - mt) * (v - mv) for t, v in sel) / sum((t - mt) ** 2 for t, _ in sel)
    tau = -10 / math.log(10) / slope
    return {'mode': mode, 'points': n, 'slope_db_per_s': round(slope, 1), 'tau_ms': round(tau * 1e3, 1)}


bal = [decay(0, 0.6), decay(1, 1.6)]
for b in bal:
    T.log(dict(ev='decay', **b)); print(json.dumps(b))
A.wr(L.RTA_MODE, 2)
R.osc(freq=1000.0, level_db=-20.0, on=True, chan=6)
time.sleep(1.0)
R.wv(T.A_OSCON, 0)
time.sleep(1.0)
held = A.band('L', i1k)
A.sc.d.write(L.RTA_RESET, 1)   # consumed within one block: a read-back verify cannot see it
time.sleep(0.5)
after = A.band('L', i1k)
pk = {'held_1s_after_off_db': round(held, 2), 'after_reset_db': round(after, 2), 'reset_consumed': A.rd(L.RTA_RESET) == 0}
T.log(dict(ev='peakhold', **pk)); print(json.dumps(pk))
A.wr(L.RTA_MODE, 0)
