#!/usr/bin/env python3
"""golden_harness.py — acceptance harness for the fixed-point audio path.

Tests the bit-accurate fixed reference (fixed_ref.py) against float64
per the tolerances in shared/numeric-spec.md. Exit code 0 = all pass.

Two-step equivalence model (numeric-spec.md): the SHARC asm / FPGA RTL
must match fixed_ref BIT-EXACTLY (checked elsewhere, per target);
fixed_ref must match float64 within these tolerances (checked here).

Usage: python3 golden_harness.py [-v]
"""

import math
import sys

import numpy as np

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import fixed_ref as fr

FS = 48000.0
results = []


def check(name, value, limit, unit, lower_is_better=True):
    ok = value <= limit if lower_is_better else value >= limit
    results.append((name, value, limit, unit, ok))
    return ok


# ---------------------------------------------------------------------------
# Biquad design helpers (RBJ cookbook, float — the shared derivation)
# ---------------------------------------------------------------------------

def peaking(f0, gain_db, q):
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2 * math.pi * f0 / FS
    al = math.sin(w0) / (2 * q)
    b0, b1, b2 = 1 + al * a, -2 * math.cos(w0), 1 - al * a
    a0, a1, a2 = 1 + al / a, -2 * math.cos(w0), 1 - al / a
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def freq_response_db(process, n=16384, amp=0.25):
    """Impulse-response FFT magnitude of a sample processor (float in/out)."""
    out = np.zeros(n)
    for i in range(n):
        out[i] = process(amp if i == 0 else 0.0)
    h = np.fft.rfft(out)
    with np.errstate(divide='ignore'):
        return 20 * np.log10(np.abs(h) / amp + 1e-30)


def t_biquad(verbose):
    worst_mag = 0.0
    worst_mag_hf = 0.0
    worst_noise = -999.0
    cases = [(f0, g, q) for f0 in (20, 100, 1000, 10000, 20000)
             for g in (-12, -3, 6, 12) for q in (0.5, 1.0, 4.0)]
    for f0, g, q in cases:
        cf = peaking(f0, g, q)
        cq = fr.biquad_coeffs_q(*cf)
        sf, sq = [0.0] * 4, fr.biquad_state()
        db_f = freq_response_db(lambda x: fr.biquad_f(x, cf, sf))
        db_q = freq_response_db(
            lambda x: fr.from_q(fr.biquad(fr.to_q(x), cq, sq)))
        n = len(db_f)
        band = slice(int(20 / (FS / 2) * n), int(20000 / (FS / 2) * n))
        sel = db_f[band] > -100
        d = np.max(np.abs((db_q[band] - db_f[band])[sel]))
        worst_mag = max(worst_mag, d)
        if f0 >= 50:
            worst_mag_hf = max(worst_mag_hf, d)
        if verbose:
            print(f'  biquad f0={f0} g={g} q={q}: mag err {d:.5f} dB')

    # Noise/limit-cycle floor: -6 dBFS sine through a tough LF boost,
    # residual = fixed - float64
    cf = peaking(40, 12, 2.0)
    cq = fr.biquad_coeffs_q(*cf)
    sf, sq = [0.0] * 4, fr.biquad_state()
    n = 48000
    x = 0.5 * np.sin(2 * np.pi * 997 * np.arange(n) / FS)
    res = np.empty(n)
    for i in range(n):
        yf = fr.biquad_f(float(x[i]), cf, sf)
        yq = fr.from_q(fr.biquad(fr.to_q(float(x[i])), cq, sq))
        res[i] = yq - yf
    noise_dbfs = 20 * math.log10(np.sqrt(np.mean(res * res)) + 1e-30)
    worst_noise = max(worst_noise, noise_dbfs)

    check('biquad magnitude error (worst incl. 20 Hz)', worst_mag, 0.05, 'dB')
    check('biquad magnitude error (f0 >= 50 Hz)', worst_mag_hf, 0.01, 'dB')
    check('biquad residual vs float64 (RMS)', worst_noise, -120.0, 'dBFS')


def t_gain_sum(verbose):
    rng = np.random.default_rng(1)
    # gains: ±0.5 LSB vs exact rounding of float product
    worst = 0
    for _ in range(2000):
        x = int(rng.integers(fr.I32_MIN // 8, fr.I32_MAX // 8))
        g = fr.to_q(float(rng.uniform(0, 4.0)))
        yq = fr.gain(x, g)
        yf = int(round((x * g) / (1 << fr.QS)))
        worst = max(worst, abs(yq - fr.sat32(yf)))
    check('gain error vs exact rounding', worst, 1, 'LSB')

    # summing: must be exact vs arbitrary-precision reference
    worst = 0
    for _ in range(200):
        xs = rng.integers(fr.I32_MIN // 16, fr.I32_MAX // 16, 128)
        gs = [fr.to_q(float(v)) for v in rng.uniform(0, 1, 128)]
        yq = fr.mix_sum([int(v) for v in xs], gs)
        acc = sum(int(v) * g for v, g in zip(xs, gs))
        worst = max(worst, abs(yq - fr.sat32(fr.rns(acc, fr.QS))))
    check('128-way mix summing vs exact', worst, 0, 'LSB')


def t_log_exp(verbose):
    # dB round-trip accuracy across ±60 dB
    k = 20 * math.log10(2.0)
    worst = 0.0
    for db in np.arange(-60, 18.01, 0.25):
        x = fr.to_q(10 ** (db / 20.0))
        if x == 0:
            continue
        l = fr.log2_q(x)
        db_meas = l / (1 << 25) * k
        worst = max(worst, abs(db_meas - db))
    check('log2 dB error (-60..+18 dB)', worst, 0.001, 'dB')

    worst = 0.0
    for db in np.arange(-72, 18.01, 0.25):
        l = int(round(db / k * (1 << 25)))
        y = fr.exp2_q(l)
        y_ref = 10 ** (db / 20.0)
        err_db = abs(20 * math.log10(fr.from_q(y) / y_ref + 1e-30))
        worst = max(worst, err_db)
    check('exp2 dB error (-72..+18 dB)', worst, 0.001, 'dB')


def t_dynamics(verbose):
    k = 20 * math.log10(2.0)
    # Static compressor curve vs float64
    worst = 0.0
    for thr_db, ratio in [(-20, 4), (-40, 2), (-10, 10), (-30, 1.5)]:
        thr_q = int(round(thr_db / k * (1 << 25)))
        slope_q = fr.to_q(1.0 - 1.0 / ratio, fr.QA)
        for db in np.arange(-59.9, 17.9, 0.2):
            x = 10 ** (db / 20.0)
            gq = fr.from_q(fr.comp_gain(fr.to_q(x), thr_q, slope_q))
            gf = fr.comp_gain_f(x, thr_db, ratio)
            d = abs(20 * math.log10(gq / gf + 1e-30))
            worst = max(worst, d)
        if verbose:
            print(f'  comp thr={thr_db} ratio={ratio}: worst {worst:.5f} dB')
    check('compressor static curve error', worst, 0.05, 'dB')

    # Envelope time constant: alpha for 10 ms attack, measure 63.2% time
    tau_s = 0.010
    alpha = 1.0 - math.exp(-1.0 / (tau_s * FS))
    aq = fr.to_q(alpha, fr.QA)
    env, target = 0, fr.to_q(1.0)
    n63 = None
    for i in range(1, 48000):
        env = fr.envelope_step(env, target, aq)
        if n63 is None and env >= fr.to_q(1 - math.exp(-1)):
            n63 = i
            break
    err_pct = abs(n63 / FS - tau_s) / tau_s * 100
    check('envelope tau error (10 ms attack)', err_pct, 2.0, '%')


def main():
    verbose = '-v' in sys.argv
    for t in (t_biquad, t_gain_sum, t_log_exp, t_dynamics):
        t(verbose)
    print(f'{"test":44s} {"value":>12s} {"limit":>10s}  unit   result')
    fails = 0
    for name, value, limit, unit, ok in results:
        fails += (not ok)
        print(f'{name:44s} {value:12.6f} {limit:10.4f}  {unit:5s}  '
              f'{"PASS" if ok else "FAIL"}')
    print(f'\n{len(results) - fails}/{len(results)} passed')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
