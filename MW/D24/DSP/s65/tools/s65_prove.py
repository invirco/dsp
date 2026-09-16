#!/usr/bin/env python3
"""s65_prove.py — the RTA on the cue bus, through the parameter link, on the S65 pair (digital; nothing analog).

Stimulus: TEST_OSC -20 dBFS pk on strip 6 (s56_setup: strip 6 -> AUX 1 at unity, MainOn 0, fader unity).
Expected band reading for a centred tone: 10 log10(0.1^2/2) = -23.010 dBFS.
  A. CUED STRIP, AFL (Sys CueMode 1), strip 6 panned hard LEFT (Pan 0.0f: L leg 1.0, R leg 0.0):
     63 Hz / 1 kHz / 8 kHz -> the band on L within 0.5 dB, one-octave neighbours >= 40 dB down, R silent;
     then pan hard RIGHT (Pan 1.0f) at 1 kHz -> the tone moves to R only.
  B. CUED STRIP, PFL (mode 0): 1 kHz on both L and R at -23.01 (pre-fader, mono, unity).
  C. NOTHING CUED, the ASSIGNED SOURCE: Cue Src 0 (main L/R) with strip 6's MainOn 1 and pan hard left -> L hot, R
     silent; Cue Src 1 (AUX 1) -> both sides (a mono bus).
  D. Ballistics on the 1 kHz band (A's route): fast / slow decay slope -> tau; peak-hold held 1 s, reset.
  E. Delivery to chip 2: Mon001InputSel001 = 13 (Cue), bulk-read one block of chip 2's cue L/R receive and of
     `_blk_C2_MON`, fit the 1 kHz sine: amplitude 0.1 on L and on the monitor, R zero.
Every table row is the median of 3 reads of all 62 words. The strip's pan and MainOn are put back at the end."""
import json, math, os, statistics as st, struct, sys, time
import s65lib as L
T, X = L.T, L.X
R = T.Rig(os.environ['SYMDIR'] + '/s65_prove.jsonl')
C = L.Cue(R)
c1 = R.c1
EXP = 10 * math.log10(0.1 ** 2 / 2)
PAN = 'Chan006Pan001'
MAINON = 'Chan006MainOn001'
pan0, main0 = c1.r(PAN), c1.r(MAINON)
T.log({'ev': 'found', 'pan': pan0, 'mainon': main0})
print('strip 6 pan %r mainon %r' % (pan0, main0))


def med_bands(n=3):
    Ls, Rs = [], []
    for _ in range(n):
        l, r = C.bands(); Ls.append(l); Rs.append(r)
    return [st.median(c) for c in zip(*Ls)], [st.median(c) for c in zip(*Rs)]


def row(label, f, hot, cold, ref=None, cold_expected_silent=True):
    i = L.nearest(f)
    nb = {L.LABELS[j]: round(hot[i] - hot[j], 2) for j in (i - 3, i + 3) if 0 <= j < 31}
    r = {'case': label, 'f': f, 'band': L.LABELS[i], 'hot_db': round(hot[i], 3), 'err_db': round(hot[i] - EXP, 3),
         'oct_db': nb, 'adjacent': {L.LABELS[j]: round(hot[i] - hot[j], 2) for j in (i - 1, i + 1) if 0 <= j < 31},
         'cold_max_db': round(max(cold), 2), 'cold_same_band_db': round(cold[i], 3), 'testmeas_rms': ref,
         'hot': [round(v, 2) for v in hot], 'cold': [round(v, 2) for v in cold]}
    ok = abs(r['err_db']) <= 0.5 and all(v >= 40 for v in nb.values())
    if cold_expected_silent:
        ok = ok and r['cold_max_db'] < hot[i] - 60
    else:
        ok = ok and abs(cold[i] - hot[i]) <= 0.05
    r['pass'] = ok
    T.log(dict(ev='row', **r))
    print(json.dumps({k: v for k, v in r.items() if k not in ('hot', 'cold')}))
    return r


rows = []
C.clear()
C.wr(L.RTA_MODE, 0)
C.wr(L.RTA_ON, 1)
s0 = R._retry(R.sc.peek, R.sc.sym['_rta_seq']); time.sleep(0.5); s1 = R._retry(R.sc.peek, R.sc.sym['_rta_seq'])
print('_rta_seq advances %d in 0.5 s' % (s1 - s0)); T.log({'ev': 'seq', 'd': s1 - s0})

# ---- A: cued strip, AFL, pan hard L / R ----
C.wr(L.MODE, 1)
C.wr(L.SEL(6), 1)
c1.wv(PAN, X.f32(0.0))
for f in (63.0, 1000.0, 8000.0):
    R.osc(freq=f, level_db=-20.0, on=True, chan=6)
    R.meas(6)
    ref = T.summ(R.windows(2, settle_windows=3, tag='ref%d' % f), 'rms')
    time.sleep(0.8)
    l, r = med_bands()
    print('  active', C.rd(L.ACTIVE))
    rows.append(row('A afl pan L', f, l, r, ref))
c1.wv(PAN, X.f32(1.0))
R.osc(freq=1000.0, level_db=-20.0, on=True, chan=6)
time.sleep(1.2)
l, r = med_bands()
rows.append(row('A afl pan R', 1000.0, r, l))
# ---- B: PFL ----
c1.wv(PAN, X.f32(0.0))
C.wr(L.MODE, 0)
time.sleep(1.2)
l, r = med_bands()
rows.append(row('B pfl', 1000.0, l, r, cold_expected_silent=False))
# ---- C: nothing cued, the assigned source ----
C.wr(L.SEL(6), 0)
c1.wv(MAINON, 1)
C.wr(L.SRC, 0)
time.sleep(1.2)
print('  active (expect 0)', C.rd(L.ACTIVE))
l, r = med_bands()
rows.append(row('C source main L/R, pan L', 1000.0, l, r))
C.wr(L.SRC, 1)
time.sleep(1.2)
l, r = med_bands()
rows.append(row('C source aux 1', 1000.0, l, r, cold_expected_silent=False))
C.wr(L.SRC, 0)
c1.wv(MAINON, main0)
print('ROWS PASS' if all(x['pass'] for x in rows) else 'ROWS FAIL')

# ---- D: ballistics on route A ----
C.wr(L.MODE, 1); C.wr(L.SEL(6), 1); c1.wv(PAN, X.f32(0.0))
i1k = L.nearest(1000.0)


def decay(mode, span_s):
    C.wr(L.RTA_MODE, mode)
    R.osc(freq=1000.0, level_db=-20.0, on=True, chan=6)
    time.sleep(1.5)
    R.wv(T.A_OSCON, 0)
    t0 = time.time(); pts = []
    while time.time() - t0 < span_s:
        tm = time.time() - t0
        pts.append((tm, C.band('L', i1k)))
    top = pts[0][1]
    sel = [(t, v) for t, v in pts if top - 40 < v < top - 3]
    n = len(sel)
    if n < 3:
        return {'mode': mode, 'points': n, 'fail': 'too few points', 'top': top}
    mt = sum(t for t, _ in sel) / n; mv = sum(v for _, v in sel) / n
    slope = sum((t - mt) * (v - mv) for t, v in sel) / sum((t - mt) ** 2 for t, _ in sel)
    return {'mode': mode, 'points': n, 'slope_db_per_s': round(slope, 1), 'tau_ms': round(-10 / math.log(10) / slope * 1e3, 1)}


bal = [decay(0, 0.6), decay(1, 1.6)]
for b in bal:
    T.log(dict(ev='decay', **b)); print(json.dumps(b))
C.wr(L.RTA_MODE, 2)
R.osc(freq=1000.0, level_db=-20.0, on=True, chan=6)
time.sleep(1.0)
R.wv(T.A_OSCON, 0)
time.sleep(1.0)
held = C.band('L', i1k)
C.raw(L.RTA_RESET, 1)          # consumed within one block
time.sleep(0.5)
after = C.band('L', i1k)
pk = {'held_1s_after_off_db': round(held, 2), 'after_reset_db': round(after, 2), 'reset_consumed': C.rd(L.RTA_RESET) == 0}
T.log(dict(ev='peakhold', **pk)); print(json.dumps(pk))
C.wr(L.RTA_MODE, 0)

# ---- E: delivery to chip 2 ----
# The chip-2 bulk read returned the SAME 16 words from three different arrays on three reads (stale; S65-3), so the
# delivery is proven by sampling: N single peeks of word 0 of each chip-2 array at random block phases. A 1 kHz tone of
# peak 0.1 gives RMS 0.0707 and |max| -> 0.1; silence gives exactly 0. Arms: cue on (strip 6 AFL, pan L) with the
# monitor on Cue (13); then nothing cued with Cue Src = main (strip 6 MainOn 0 -> silent), monitor still on Cue.
R.osc(freq=1000.0, level_db=-20.0, on=True, chan=6)
c2 = X.Chip(2)
sc2 = c2.sc
m0 = R._retry(sc2.rd, L.MON_INPUTSEL_C2)
NPK = int(os.environ.get('NPK', '200'))


def sample(name):
    a = sc2.sym[name]
    v = [X.s32(R._retry(sc2.peek, a)) / 2.0 ** 28 for _ in range(NPK)]
    return {'rms': round(math.sqrt(sum(x * x for x in v) / len(v)), 5), 'max': round(max(abs(x) for x in v), 5)}


deliv = {'mon_inputsel_found': m0}
R._retry(c2.raw_w, L.MON_INPUTSEL_C2, 13)
deliv['mon_inputsel_set'] = R._retry(sc2.rd, L.MON_INPUTSEL_C2)
for arm_ in ('cued_afl_panL', 'nothing_cued_src_main_silent'):
    if arm_ == 'cued_afl_panL':
        C.wr(L.MODE, 1); C.wr(L.SEL(6), 1); c1.wv(PAN, X.f32(0.0))
    else:
        C.wr(L.SEL(6), 0); C.wr(L.SRC, 0)
    time.sleep(0.3)
    deliv[arm_] = {n: sample(n) for n in ('_rx_ic_slot_C2_RECV_CUE_L', '_rx_ic_slot_C2_RECV_CUE_R', '_blk_C2_MON')}
    print(arm_, json.dumps(deliv[arm_]))
R._retry(c2.raw_w, L.MON_INPUTSEL_C2, m0)
time.sleep(0.2)
C.wr(L.MODE, 1); C.wr(L.SEL(6), 1)
time.sleep(0.3)
deliv['cued_mon_on_main'] = {'_blk_C2_MON': sample('_blk_C2_MON')}
print('cued, monitor back on source %d' % m0, json.dumps(deliv['cued_mon_on_main']))
deliv['mon_inputsel_restored'] = R._retry(sc2.rd, L.MON_INPUTSEL_C2)
T.log(dict(ev='delivery', **deliv))

# ---- restore ----
C.clear(); C.wr(L.MODE, 0); C.wr(L.RTA_ON, 0); C.wr(L.SRC, 0)
c1.wv(PAN, pan0); c1.wv(MAINON, main0)
R.osc(freq=1000.0, level_db=-20.0, on=True, chan=6)
print('restored pan %r mainon %r' % (c1.r(PAN), c1.r(MAINON)))
