#!/usr/bin/env python3
"""s63_thd.py — hub addendum T3: THD ONLY (h2..h10) at MAXIMUM gain on MIC 5, and at code 0 for comparison.

TEST_OSC on donor strip 6 -> AUX 1 -> loop cable -> J25 -> MIC 5 lane. 1 kHz in a 16,320-sample capture = exactly 340
cycles and 1,020 whole blocks (bin-centred: every harmonic on a bin, no window). A first attempt asked 999.0234375 Hz
(341 cycles in 16,384): the word read back exact but the captured tone fitted 1000.0000 Hz, so TEST_OSC does not
honour a fractional frequency and that run was off-bin (kept on the bench as thd_J25_offbin, not used). Lane level trimmed to
-3.0 dBFS pk (3 dB below clip) at each code by a coherent fit of the first capture. N captures per code (bulk read);
the desk (s63_thd_analyse.py) averages them COHERENTLY (each capture's bins rotated by its fundamental's phase,
k x phi1 for harmonic k), so the per-bin noise floor falls 10 log N dB under a single capture while the harmonics stay.
Raw -> DATA/thd_<XLR>.bin/.jsonl.   env: N=32  CODES=63,0  TARGET=-3.0"""
import math, os, time
import s63lib as S
import s63_run as RUN
T, X, MC, BULK = S.T, S.X, S.MC, S.BULK

N = int(os.environ.get('N', '32'))
CODES = [int(c) for c in os.environ.get('CODES', '63,0').split(',')]
TARGET = float(os.environ.get('TARGET', '-3.0'))
F = 1000.0
NCAP = 16320
CYCLES = 340


def fund_pk(vals):
    x = [(v - (1 << 32) if v & 0x80000000 else v) / float(1 << 28) for v in vals]
    w = 2 * math.pi * CYCLES / len(x)
    a = sum(v * math.sin(w * i) for i, v in enumerate(x)) * 2 / len(x)
    b = sum(v * math.cos(w * i) for i, v in enumerate(x)) * 2 / len(x)
    return 20 * math.log10(math.hypot(a, b)), max(abs(v) for v in x)


def cap(R):
    lines = []
    c = MC.capture(NCAP, S.SYMDIR, sc=R.sc, log=lines.append)
    assert len(c['samples']) == NCAP, len(c['samples'])
    return c


R = RUN.Rig()
ok, pin = R.an_en()
S.P('AN_EN: %s' % pin)
if not ok:
    raise SystemExit('AN_EN LOW — blocked (never written)')
xlr, p, lane = 'J25', S.D24.MIC5.send, S.D24.MIC5_STRIP
R.select(xlr, p, lane)
G = S.loop_gain(xlr)
R.meas(lane)
R.set_trim(0.0)
R.wv(4979, 0)                                    # SweepOn 0
R.wv(T.A_OSCFREQ, X.f32(F))
S.P('OscFreq word %.7f Hz (asked %.7f)' % (X.from_f32(R.rd(T.A_OSCFREQ)), F))
for code in CODES:
    R.set_code(code)
    L = TARGET - G[code]
    for it in range(4):
        R.tone(L)
        time.sleep(3.0 if it == 0 else 0.5)
        c = cap(R)
        pk, mx = fund_pk(c['samples'])
        S.P('code %d osc %.3f dBFS pk: lane fundamental %.3f dBFS pk (sample max %.2f dBFS)' % (code, L, pk, 20 * math.log10(mx)))
        if abs(pk - TARGET) <= 0.05:
            break
        L += TARGET - pk
    t0 = time.time()
    for i in range(N):
        c = cap(R)
        rec = {'xlr': xlr, 'lane': lane, 'code': code, 'k': i, 'osc_dbfs_pk': L, 'freq': F, 'n': len(c['samples']),
               'overruns': c['overruns'], 'read_s': c['read_s'], 't_wall': round(time.time(), 3)}
        S.save(c['samples'], rec, 'thd_' + xlr)
        if c['overruns']:
            S.P('  capture %d: overruns %d' % (i, c['overruns']))
    S.P('code %d: %d captures in %.1f s' % (code, N, time.time() - t0))
R.tone(None)
R.set_code(0)
R.wv(T.A_OSCFREQ, X.f32(1000.0))
S.P('done; AN_EN %s' % R.an_en()[1])
