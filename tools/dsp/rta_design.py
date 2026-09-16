#!/usr/bin/env python3
"""rta_design.py — the 1/3-octave RTA filterbank (S64): band centres, section
coefficients, and a float32 reference of the exact recurrence the chip-2
kernel (`src/chip2/rta.asm`, emitted by dsp_codegen.gen_rta) runs.

Stdlib only for the design (the generator must not grow a numpy dependency);
numpy is used only by the reference/self-check under __main__.

BANDS. IEC 61260 base-ten 1/3-octave: fm = 1000 * G**(k/3), G = 10**0.3,
k = -17..13 -> 31 bands, 19.95 Hz .. 19.95 kHz; band edges fm * G**(+-1/6).

SHAPE. Each band is a digital Butterworth bandpass of prototype order
RTA_SECTIONS, by bilinear transform with BOTH edges prewarped, so the -3 dB
points sit exactly on the nominal edges at every band including the top one.
A Butterworth bandpass of prototype order N has N conjugate pole pairs and
its zeros are N at z = +1 and N at z = -1, so every second-order section is

        H_k(z) = (1 - z^-2) / (1 + a1_k z^-1 + a2_k z^-2)

with NO numerator multiply at all: the kernel carries only (a1, a2) per
section and folds the band's gain into its power normaliser at block rate.

WHY THREE SECTIONS, NOT TWO (findings S64-2). Attenuation one octave from
centre, every band below 5 kHz:
    N = 2 (two biquads):   32.2-32.5 dB -- fails a >= 40 dB neighbour gate
    N = 3 (three biquads): 48.3-48.8 dB -- passes (measured on the part: 48.5-50.9)
Narrowing an N = 2 band until its edges read -5 dB only buys 35.9 dB.

RECURRENCE, float32, per band per sample (DF1 with the shared numerator):
    d  = x[n] - x[n-2]                     (once per channel per sample)
    for each section: y = d - a1*y1 - a2*y2;  d_next = y - y2;  y2 = y1; y1 = y
    acc += y3 * y3
and at block rate  P = acc * K,  K = g**2 / BLOCK,  g = 1/|H(f0)|, so P is the
band's MEAN SQUARE in full-scale units (x = Q4.28 word * 2^-28): a sine of
peak A centred in the band reads A**2 / 2, i.e. 10*log10(P) is the dBFS law
TEST_MEAS's RmsResult already uses (-20 dBFS pk -> -23.01).
"""
import cmath
import math
import struct

FS = 48000.0
G = 10 ** 0.3
RTA_K = range(-17, 14)          # 31 bands
RTA_BANDS = len(RTA_K)
RTA_SECTIONS = 3

# Ballistics, one-pole on the block power, alpha = 1 - exp(-Tblock / tau).
# PW 2026-09-16 (S64 dispatch): fast ~35 ms, slow ~125 ms, peak-hold.
RTA_TAU_FAST_S = 0.035
RTA_TAU_SLOW_S = 0.125
RTA_MODES = ('fast', 'slow', 'peak')


def centres():
    return [1000.0 * G ** (k / 3.0) for k in RTA_K]


def nominal(fm):
    """The label a desk prints for a centre (20, 25, 31.5, ... 20k)."""
    lab = (20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400,
           500, 630, 800, 1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000,
           6300, 8000, 10000, 12500, 16000, 20000)
    return min(lab, key=lambda v: abs(math.log(v / fm)))


def design(fm, n=RTA_SECTIONS, fs=FS):
    """-> (sections [(a1, a2)], g, f0_digital) for the band centred on fm."""
    f1 = fm * G ** (-1.0 / 6)
    f2 = fm * G ** (1.0 / 6)
    w1 = 2 * fs * math.tan(math.pi * f1 / fs)
    w2 = 2 * fs * math.tan(math.pi * f2 / fs)
    w0 = math.sqrt(w1 * w2)
    bw = w2 - w1
    secs = []
    for k in range(1, n + 1):
        p = cmath.exp(1j * math.pi * (2 * k + n - 1) / (2 * n))
        disc = cmath.sqrt(p * p * bw * bw - 4 * w0 * w0)
        for s in ((p * bw + disc) / 2, (p * bw - disc) / 2):
            if s.imag <= 0:
                continue
            z = (1 + s / (2 * fs)) / (1 - s / (2 * fs))
            secs.append((-2 * z.real, abs(z) ** 2))
    if len(secs) != n:
        raise ValueError('band %.2f Hz: %d sections, expected %d' % (fm, len(secs), n))
    # lowest-frequency pole pair first: the smallest-gain section leads
    secs.sort(key=lambda s: s[0], reverse=True)
    f0 = fs / math.pi * math.atan(w0 / (2 * fs))
    g = 1.0 / abs(response(secs, f0, fs))
    return secs, g, f0


def response(secs, f, fs=FS):
    z1 = cmath.exp(-2j * math.pi * f / fs)
    h = 1.0
    for a1, a2 in secs:
        h *= (1 - z1 * z1) / (1 + a1 * z1 + a2 * z1 * z1)
    return h


def band_db(fm, f, n=RTA_SECTIONS):
    secs, g, _ = design(fm, n)
    return 20 * math.log10(abs(response(secs, f)) * g)


def f32bits(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def alpha(tau_s, block):
    return 1.0 - math.exp(-(block / FS) / tau_s)


def table(block):
    """The kernel's coefficient table: per band a1,a2 x SECTIONS then K."""
    rows = []
    for fm in centres():
        secs, g, _ = design(fm)
        row = []
        for a1, a2 in secs:
            row += [a1, a2]
        row.append(g * g / block)
        rows.append((fm, row))
    return rows


def reference(x, block, n=RTA_SECTIONS):
    """float32 model of the kernel for ONE channel: x = full-scale samples
    (len a multiple of block). Returns per-block mean square, bands x blocks."""
    import numpy as np
    f32 = np.float32
    rows = table(block)
    nb = len(x) // block
    out = np.zeros((RTA_BANDS, nb))
    xs = np.asarray(x, dtype=np.float32)
    d = np.zeros(len(xs), dtype=np.float32)
    d[0] = xs[0]
    d[1] = xs[1]
    d[2:] = xs[2:] - xs[:-2]
    for b, (_fm, row) in enumerate(rows):
        a = [f32(v) for v in row[:-1]]
        k = f32(row[-1])
        y1 = [f32(0)] * n
        y2 = [f32(0)] * n
        for j in range(nb):
            acc = f32(0)
            for dn in d[j * block:(j + 1) * block]:
                dd = f32(dn)
                for s in range(n):
                    y = f32(dd - f32(a[2 * s] * y1[s]))
                    y = f32(y - f32(a[2 * s + 1] * y2[s]))
                    dd = f32(y - y2[s])
                    y2[s] = y1[s]
                    y1[s] = y
                acc = f32(acc + f32(y * y))
            out[b, j] = float(f32(acc * k))
    return out


if __name__ == '__main__':
    for n in (2, 3):
        worst = min(min(-band_db(fm, fm / 2, n), -band_db(fm, fm * 2, n))
                    for fm in centres() if fm * 2 < 10000)
        edge = max(max(-band_db(fm, fm * G ** (-1 / 6), n), -band_db(fm, fm * G ** (1 / 6), n))
                   for fm in centres())
        print('sections %d: min attenuation one octave from centre (bands < 5 kHz) %.1f dB, '
              'worst edge %.2f dB' % (n, worst, edge))
    print('alpha fast %.6f slow %.6f at block 16' % (alpha(RTA_TAU_FAST_S, 16), alpha(RTA_TAU_SLOW_S, 16)))
