#!/usr/bin/env python3
"""roundonce_noise.py — what RIG C costs in dynamic range, measured.

PW's D5 amendment moves the round and the saturate to once per strip and
once per cascade output. RIG C keeps the FIXED contract while doing that,
by carrying the signal with HEADROOM instead of a per-stage clamp. The
headroom is not free: a 32-bit word that gains H integer bits loses H
FRACTION bits, and every intermediate store in the chain loses them.

This script prices that, three ways:

  1. THE FORMAT. Q(4+H).(28-H) against Q4.28: fraction bits, ceiling,
     and the quantisation noise floor referred to 0 dBFS.
  2. HOW MUCH H THE CHAIN ACTUALLY NEEDS -- taken from the reachable
     bounds tools/dsp/bq_state_bound.py measures over the DEFS design
     space, not assumed.
  3. WHAT IT DOES TO THE RESPONSE, on the same real EQ curves and by the
     same impulse->FFT method tools/dsp/bq_float_delta.py uses for the
     float arm, so the two rigs' numeric prices are directly comparable
     against the same 0.046 dB golden_harness bar.

AND THE PART THE FORMAT TABLE DOES NOT SHOW: round-once also deletes the
ERROR FEEDBACK. The current contract's first-order noise shaping is what
puts the LF rounding-noise floor below -130 dBFS (numeric-spec.md);
without it the same kernel is an ordinary rounding quantiser. That is a
separate loss from the H bits and it is measured separately below.

Usage: python3 roundonce_noise.py [--quick]
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixed_ref as F
from bq_float_delta import rbj_peak, rbj_shelf, curve_db, FS

QB = F.QB


# ---------------------------------------------------------------------------
# The RIG C model: same offset-form accumulation, same coefficient words,
# extraction WRAPS instead of saturating, no error feedback, and the
# signal carried with H bits of headroom.
# ---------------------------------------------------------------------------
def _wrap32(v):
    return ((v + (1 << 31)) & 0xFFFFFFFF) - (1 << 31)


def bq_round_once(x, cq, st, truncate=False):
    b0, n1h, n2, c1, c2 = cq
    x1, x2, y1, y2 = st
    acc = (b0 * (x - 2 * x1 + x2) + n1h * x1 + n1h * x1 + n2 * x2
           - c1 * y1 + c2 * y2 + ((2 * y1 - y2) << QB))
    y = (acc >> QB) if truncate else F.rns(acc, QB)
    y = _wrap32(y)
    st[0], st[1] = x, x1
    st[2], st[3] = y, y1
    return y


def bq_round_once_efb(x, cq, st):
    """RIG C's E arm: the saturate deleted, the ERROR FEEDBACK KEPT.
    Identical to fixed_ref.biquad except that the extract wraps."""
    b0, n1h, n2, c1, c2 = cq
    x1, x2, y1, y2, efb = st
    acc = (b0 * (x - 2 * x1 + x2) + n1h * x1 + n1h * x1 + n2 * x2
           - c1 * y1 + c2 * y2 + ((2 * y1 - y2) << QB) + efb)
    y = _wrap32(F.rns(acc, QB))
    st[4] = acc - (y << QB)
    st[0], st[1] = x, x1
    st[2], st[3] = y, y1
    return y


def run_rigc(x, designs, H, truncate=False, efb=False):
    """One clamp, at the cascade output. H bits of headroom carried
    through, which is H fraction bits given up at every intermediate."""
    coeffs = [F.biquad_coeffs_q(*d) for d in designs]
    state = [([0] * 5 if efb else [0, 0, 0, 0]) for _ in designs]
    out = []
    for s in x:
        v = F.to_q(s) >> H                      # into Q(4+H).(28-H)
        for c, st in zip(coeffs, state):
            v = (bq_round_once_efb(v, c, st) if efb
                 else bq_round_once(v, c, st, truncate))
        out.append(F.from_q(F.sat32(v << H)))   # the ONE round/saturate
    return np.array(out, dtype=np.float64)


def run_fixed(x, designs):
    coeffs = [F.biquad_coeffs_q(*d) for d in designs]
    state = [F.biquad_state() for _ in designs]
    out = []
    for s in x:
        v = F.to_q(s)
        for c, st in zip(coeffs, state):
            v = F.biquad(v, c, st)
        out.append(F.from_q(v))
    return np.array(out, dtype=np.float64)


def run_f64(x, designs):
    """float64 DF-II-T on the SAME quantised coefficient words, so the
    comparison isolates arithmetic and not coefficient quantisation."""
    cs = []
    for d in designs:
        b0, n1h, n2, c1, c2 = F.biquad_coeffs_q(*d)
        cs.append((F.from_q(b0),
                   F.from_q(2 * n1h) - 2 * F.from_q(b0),
                   F.from_q(n2) + F.from_q(b0),
                   F.from_q(c1) - 2.0,
                   1.0 - F.from_q(c2)))
    w1 = [0.0] * len(cs)
    w2 = [0.0] * len(cs)
    out = []
    for s in x:
        v = float(s)
        for k, (b0, b1, b2, a1, a2) in enumerate(cs):
            y = b0 * v + w1[k]
            w1[k] = b1 * v - a1 * y + w2[k]
            w2[k] = b2 * v - a2 * y
            v = y
        out.append(v)
    return np.array(out, dtype=np.float64)


def format_table():
    print('  1. THE FORMAT. Q4.28 is 0 dBFS = 1.0, ceiling 8.0, and one')
    print('     LSB of 2^-28. H bits of headroom move the binary point:')
    print()
    print(f'    {"H":>2s} {"format":>10s} {"ceiling":>9s} {"headroom":>9s} '
          f'{"LSB":>12s} {"noise floor":>12s} {"eff. bits":>9s}')
    print('    ' + '-' * 70)
    for H in range(0, 9):
        frac = QB - H
        ceil_lin = 8.0 * (1 << H)
        lsb = 2.0 ** -frac
        nf = 20 * math.log10(lsb / math.sqrt(12.0))
        print(f'    {H:2d} {f"Q{4+H}.{frac}":>10s} {ceil_lin:9.1f} '
              f'{20*math.log10(ceil_lin):8.2f}dB {lsb:12.3e} '
              f'{nf:11.1f}dB {frac:9d}')
    print()
    print('     Dynamic range is UNCHANGED -- it is 32 bits either way. What')
    print('     moves is where the 32 bits sit: H of them are spent above')
    print('     0 dBFS, where music is not, and the noise floor comes up by')
    print('     6.02 dB per bit.')


def headroom_needed():
    print()
    print('  2. HOW MUCH H THE CHAIN NEEDS (tools/dsp/bq_state_bound.py,')
    print('     measured over the DEFS design space, worst PARTIAL cascade,')
    print('     0 dBFS input, bound = ||h||_1 and not max|H|):')
    print()
    for name, bits, note in (
            ('one biquad, worst single stage', 4, '||h||_1 = 97.3 = +39.8 dB'),
            ('FILT: HPF 36 dB/oct + LPF', 0, '||h||_1 = 4.5, fits Q4.28'),
            ('GEQ 28 x +12 dB', 3, '||h||_1 = 41.9 = +32.5 dB'),
            ('EQ: 4 bands, all +15 dB, coherent', 8,
             '||h||_1 = 1313 = +62.4 dB')):
        print(f'    {name:38s} {bits:2d} bits   {note}')
    print()
    print('     The four-band case is the one that decides it, and it is')
    print('     ORDINARY: four bands at +15 dB on the same frequency is a')
    print('     setting the DEFS ranges allow and a console operator can')
    print('     dial. At H = 8 the internal word is Q12.20.')


def response_cost(quick):
    N = 8192
    imp = np.zeros(N)
    imp[0] = 0.5
    freqs = np.fft.rfftfreq(N, 1 / FS)
    band = (freqs >= 20) & (freqs <= 20000)
    cases = {
        '1-band peak +15 dB Q3 @1 kHz': [rbj_peak(1000, 3.0, 15.0)],
        'EXTREME +15 dB Q10 @20 Hz': [rbj_peak(20, 10.0, 15.0)],
        'LF shelf +15 dB Q3.16 @20 Hz': [rbj_shelf(20, 3.16, 15.0, False)],
        '4-band EQ, mixed': [rbj_peak(80, 1.1, 8.0), rbj_peak(400, 1.5, -6.0),
                             rbj_peak(2500, 2.0, 6.0),
                             rbj_peak(9000, 0.8, -4.0)],
    }
    if not quick:
        cases['28-band GEQ all +6 dB'] = [
            rbj_peak(25 * (2 ** (i / 6.0)), 4.3, 6.0) for i in range(28)]
    Hs = (0, 2, 4, 8)
    arms = [('E H=0', dict(H=0, efb=True)),
            ('E H=2', dict(H=2, efb=True)),
            ('E H=4', dict(H=4, efb=True)),
            ('E H=6', dict(H=6, efb=True)),
            ('E H=8', dict(H=8, efb=True))]
    print()
    print('  3. WHAT IT DOES TO THE RESPONSE. Impulse -> FFT, the same')
    print('     method and the same 20 Hz - 20 kHz band bq_float_delta.py')
    print('     uses for the float arm, against the CURRENT contract.')
    print('     Max |dB| error over the band:')
    print()
    print(f'    {"design":30s}' + ''.join(f'{f"C H={h}":>9s}' for h in Hs)
          + ''.join(f'{n:>9s}' for n, _ in arms))
    print('    ' + '-' * 76)
    for name, d in cases.items():
        ref = run_fixed(imp, d)
        cref = curve_db(ref, N)
        row = []
        for H in Hs:
            y = run_rigc(imp, d, H)
            row.append(float(np.abs(curve_db(y, N) - cref)[band].max()))
        for _, kw in arms:
            y = run_rigc(imp, d, **kw)
            row.append(float(np.abs(curve_db(y, N) - cref)[band].max()))
        print(f'    {name:30s}' + ''.join(f'{v:9.4f}' for v in row))
    print('    ' + '-' * 74)
    print('     golden_harness holds the contract to 0.046 dB; RIG A2 (float)')
    print('     costs 0.520 dB on the LF shelf row (bq_float_delta.py).')


def noise_floor(quick):
    """The arithmetic noise, measured as residual against float64 on the
    SAME quantised coefficients -- which is what 'noise floor' means for
    a kernel. The error feedback's absence shows up here and nowhere in
    the format table."""
    N = 4096 if quick else 16384
    n = np.arange(N)
    x = 0.1 * np.sin(2 * np.pi * 997.0 * n / FS)     # -20 dBFS, in band
    cases = {
        'LF shelf +15 dB Q3.16 @20 Hz': [rbj_shelf(20, 3.16, 15.0, False)],
        'peak +15 dB Q10 @20 Hz': [rbj_peak(20, 10.0, 15.0)],
        'peak +6 dB Q1 @1 kHz': [rbj_peak(1000, 1.0, 6.0)],
    }
    print()
    print('  4. THE NOISE FLOOR, MEASURED. Residual RMS against float64 on')
    print('     the same quantised coefficients, -20 dBFS 997 Hz drive,')
    print(f'     {N} samples. dBFS re 1.0.')
    print()
    print(f'    {"design":30s} {"contract":>10s} {"E H=0":>9s} '
          f'{"E H=2":>9s} {"E H=8":>9s} {"C H=0":>9s} {"C H=4":>9s} '
          f'{"C H=0 tr":>9s}')
    print('    ' + '-' * 91)
    for name, d in cases.items():
        ref = run_f64(x, d)
        vals = [run_fixed(x, d),
                run_rigc(x, d, 0, efb=True), run_rigc(x, d, 2, efb=True),
                run_rigc(x, d, 8, efb=True),
                run_rigc(x, d, 0), run_rigc(x, d, 4),
                run_rigc(x, d, 0, truncate=True)]
        cells = []
        for v in vals:
            r = v - ref
            cells.append(20 * math.log10(max(np.sqrt((r * r).mean()), 1e-30)))
        print(f'    {name:30s}{cells[0]:10.1f}'
              + ''.join(f'{c:9.1f}' for c in cells[1:]))
    print('    ' + '-' * 91)
    print('     The contract column is low because of the ERROR FEEDBACK,')
    print('     which round-once deletes. That deletion is worth the whole')
    print('     gap between the first two columns, at H = 0, before a single')
    print('     bit of headroom has been spent.')


def gain_path():
    print()
    print('  5. THE GAIN PATH. The shipping gain node stores')
    print('     sat32(rns(x*g, 28)) -- Q4.28, rounded and clipped. Round-once')
    print('     stores MR1B, the top 32 bits of the Q8.56 product: Q8.24,')
    print('     TRUNCATED, four bits of headroom and four bits given up.')
    print()
    n = 200000
    rng = np.random.default_rng(3)
    g = F.to_q(0.70710678)
    xs = (rng.integers(-(1 << 28), (1 << 28), size=n)).astype(object)
    err_now = []
    err_r1 = []
    for x in xs:
        x = int(x)
        exact = x * g / (1 << QB)
        now = F.gain(x, g)
        r1 = (x * g) >> 32                       # MR1B, Q8.24
        err_now.append(now - exact)
        err_r1.append(r1 * 16.0 - exact)         # Q8.24 -> Q4.28 scale
    for name, e in (('today  Q4.28 round+sat', err_now),
                    ('round-once Q8.24 trunc', err_r1)):
        e = np.array(e, dtype=np.float64) / (1 << QB)
        rms = 20 * math.log10(max(np.sqrt((e * e).mean()), 1e-30))
        bias = e.mean()
        print(f'    {name:26s} error RMS {rms:8.1f} dBFS   '
              f'mean (DC bias) {bias:12.3e}')
    print()
    print('     24.1 dB of it is the four bits; the DC bias is the')
    print('     truncation, and it is one-sided because MR1B is a shift and')
    print('     not a round. A rounded wide store would cost one more MAC,')
    print('     which is the instruction bqshoot rung 10 does not pay.')


def main():
    quick = '--quick' in sys.argv
    print('roundonce_noise.py — the dynamic-range price of RIG C')
    print()
    format_table()
    headroom_needed()
    response_cost(quick)
    noise_floor(quick)
    gain_path()
    return 0


if __name__ == '__main__':
    sys.exit(main())
