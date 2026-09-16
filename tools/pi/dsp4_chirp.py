#!/usr/bin/env python3
"""dsp4_chirp.py — the swept-sine (chirp) side of dsp4_fft.py (S60).

TEST_OSC with SweepOn = 1 injects a PERIODIC exponential sine sweep from 20 Hz
to 20 kHz, one period = SweepStep x 1024 samples (0 = 16 -> 16,384 = one
capture buffer), and the TEST_MEAS capture arm starts a capture only on the
pass that injects a period's first block. So a capture of N = one period of
MeasChan's post-fader signal, taken after the path has seen at least one whole
period, is one period of the path's steady-state response to a known periodic
excitation, and sample 0 of it lines up with sample 0 of the sweep.

WHAT IS COMPUTED, from ONE capture:

  impulse response   h = F^-1{ Y . X* / (|X|^2 + eps) } over the swept band,
                     with raised-cosine band edges. This is Farina's inverse
                     filter (the time-reversed sweep with its 6 dB/oct
                     envelope) written in the frequency domain, where for a
                     periodic excitation it is exact rather than approximate.
  latency            the linear impulse's position: peak of the band-limited
                     h(t) interpolated between samples, and the phase-slope
                     group delay over 1-10 kHz (the S54 T8 definition).
  polarity           the sign of h at the peak.
  response           |H(f)| from the bins of the regularised ratio: power mean
                     over a 1/48-octave band around each point (two-bin
                     interpolation where the band holds < 2 bins), in
                     dB re 1 kHz; the gain at 1 kHz in dB. Harmonic products
                     sit inside those bins at their own level, so the error
                     bound is the THD: 0.03 dB at -50 dB, 0.0003 dB at -90.
  THD (2..5)         an exponential sweep moves harmonic k's impulse EARLIER
                     by L.ln(k)/ln(f_hi/f_lo) samples; each is windowed out and
                     read at k.f0, relative to H1(f0). A check figure: it is
                     the distortion at the sweep's instantaneous level.
  SNR per band       with a SECOND capture of the same condition, noise =
                     (y1 - y2)/sqrt(2); SNR at 20 Hz = mean |Y|^2 / mean
                     |Noise|^2 over the bins 20 Hz +- 9 Hz.

THE REFERENCE X is either the injected sweep modelled on the host (the DSP's
own algorithm in float64: phase in cycles, w *= r per sample, r from the same
table the generator emits) scaled by OscLevel, or a capture of the donor
strip's post-fader block (--ref), which is the injected sequence exactly.
Both are offered because the part's 40-bit register arithmetic is not
float64; `compare_model()` reports how far apart they are.

Stdlib only (numpy used when importable, for speed), like dsp4_fft.py.
"""
import cmath
import math
import struct

FS = 48000.0
F_LO = 20.0
F_HI = 20000.0
UNIT = 1024
DEFAULT_STEPS = 16
CAP_SCALE = float(1 << 28)          # q4.28: 1.0 = converter full scale

try:
    import numpy as _np
except ImportError:                 # the bench CM4 has none
    _np = None


def f32(v):
    return struct.unpack('<f', struct.pack('<f', v))[0]


def period(steps):
    return (steps if steps > 0 else DEFAULT_STEPS) * UNIT


def ratio(steps):
    """r as the part holds it: the generator's float64 value, assembled to
    float32 (the table is `.var` floats)."""
    L = period(steps)
    return f32(math.exp(math.log(F_HI / F_LO) / L))


def model(steps=0, level=1.0, n=None):
    """One period of the injected sweep in FS units (1.0 = 0 dBFS peak), the
    TEST_OSC chirp kernel in float64."""
    L = period(steps)
    n = L if n is None else n
    r = ratio(steps)
    w = f32(F_LO / FS)
    p = 0.0
    out = []
    tp = 2.0 * math.pi
    for i in range(n):
        if i and i % L == 0:
            p, w = 0.0, f32(F_LO / FS)
        out.append(level * math.sin(tp * p))
        p += w
        if p >= 1.0:
            p -= 1.0
        w *= r
    return out


# ---------------------------------------------------------------------------
# transforms
# ---------------------------------------------------------------------------

def _fft_py(x):
    n = len(x)
    a = list(x)
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j |= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    length = 2
    while length <= n:
        wl = cmath.exp(complex(0.0, -2.0 * math.pi / length))
        half = length >> 1
        for i in range(0, n, length):
            w = 1.0 + 0j
            for k in range(i, i + half):
                u = a[k]
                v = a[k + half] * w
                a[k] = u + v
                a[k + half] = u - v
                w *= wl
        length <<= 1
    return a


def fft(x):
    if _np is not None:
        return list(_np.fft.fft(_np.asarray(x, dtype=complex)))
    return _fft_py([complex(v) for v in x])


def ifft(X):
    n = len(X)
    if _np is not None:
        return list(_np.fft.ifft(_np.asarray(X, dtype=complex)))
    y = _fft_py([complex(v).conjugate() for v in X])
    return [v.conjugate() / n for v in y]


def _band_weight(f):
    """1 across [F_LO, F_HI]; raised-cosine to 0 over [F_LO/2, F_LO] and
    [F_HI, min(1.15 F_HI, fs/2)], so the band edge does not ring for
    hundreds of samples into the harmonic windows."""
    lo0, hi1 = F_LO / 2.0, min(1.15 * F_HI, FS / 2.0)
    if f <= lo0 or f >= hi1:
        return 0.0
    if f < F_LO:
        return 0.5 - 0.5 * math.cos(math.pi * (f - lo0) / (F_LO - lo0))
    if f > F_HI:
        return 0.5 + 0.5 * math.cos(math.pi * (f - F_HI) / (hi1 - F_HI))
    return 1.0


def deconvolve(y, x):
    """The raw regularised ratio R = Y X* / (|X|^2 + eps) over all N bins,
    unmasked, plus X and Y. Masks are applied per use: see analyse()."""
    n = len(y)
    X, Y = fft(x), fft(y)
    mx = max(abs(v) ** 2 for v in X)
    eps = 1e-10 * mx
    R = [Y[k] * X[k].conjugate() / (abs(X[k]) ** 2 + eps) for k in range(n)]
    return R, X, Y


def _masked(R, weight):
    n = len(R)
    return [R[k] * weight(min(k, n - k) * FS / n) for k in range(n)]


def _hp_weight(f, lo=500.0, hi=1000.0):
    """0 below lo, raised cosine to 1 at hi, then the band weight: an impulse
    with no slow low-frequency ringing, for the harmonic windows."""
    if f <= lo:
        return 0.0
    g = 1.0 if f >= hi else 0.5 - 0.5 * math.cos(math.pi * (f - lo) / (hi - lo))
    return g * _band_weight(f)


SMOOTH = 2 ** (1 / 96.0) - 1.0       # +-1/96 octave = a 1/48-octave band


def mag_at(R, f, smooth=SMOOTH):
    """|H| at f. A periodic excitation defines H only AT the bins; the
    reading is the power mean of |H| over the bins within +-smooth*f (a
    1/48-octave band -- the response is smooth on that scale, the noise is
    not), or, where that band holds fewer than two bins (below ~140 Hz at
    16,384 samples), the linear interpolation between the two bins around f."""
    n = len(R)
    b = f * n / FS
    lo, hi = int(math.ceil(b * (1 - smooth))), int(math.floor(b * (1 + smooth)))
    if hi - lo + 1 >= 2:
        return math.sqrt(sum(abs(R[k]) ** 2 for k in range(lo, hi + 1)) / (hi - lo + 1))
    k = int(math.floor(b))
    t = b - k
    return (1 - t) * abs(R[k]) + t * abs(R[k + 1])


def dtft_mag(seg, f):
    """|sum seg[n] e^{-j w n}| at frequency f (Hz)."""
    w = 2.0 * math.pi * f / FS
    if _np is not None:
        s = _np.asarray(seg)
        return abs(_np.sum(s * _np.exp(-1j * w * _np.arange(len(s)))))
    acc = 0j
    for i, v in enumerate(seg):
        acc += v * cmath.exp(complex(0.0, -w * i))
    return abs(acc)


def _circ(h, start, length):
    n = len(h)
    return [h[(start + i) % n] for i in range(length)]


def _taper(seg, t):
    m = len(seg)
    out = list(seg)
    for i in range(min(t, m // 2)):
        g = 0.5 - 0.5 * math.cos(math.pi * (i + 0.5) / t)
        out[i] *= g
        out[m - 1 - i] *= g
    return out


def _h_at(H, t, kmax):
    """band-limited h at fractional sample t (bins 1..kmax, both signs)."""
    n = len(H)
    acc = 0.0
    for k in range(1, kmax + 1):
        if H[k]:
            acc += 2.0 * (H[k] * cmath.exp(complex(0.0, 2.0 * math.pi * k * t / n))).real
    return acc / n


def harmonic_delay(k, L):
    return L * math.log(k) / math.log(F_HI / F_LO)


# ---------------------------------------------------------------------------
# the analysis
# ---------------------------------------------------------------------------

POINTS = (20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 15000, 20000)


def analyse(y, x, steps=0, f0=1000.0, points=POINTS, y2=None, kmax_h=5):
    n = len(y)
    L = period(steps)
    if n != L or len(x) != n:
        raise ValueError('capture %d / reference %d must both be one period (%d)'
                         % (n, len(x), L))
    R, X, Y = deconvolve(y, x)
    H = _masked(R, _band_weight)
    h = [v.real for v in ifft(H)]
    i0 = max(range(n), key=lambda i: abs(h[i]))
    pol = 1 if h[i0] > 0 else -1
    # sub-sample peak: golden section on pol*h(t) over [i0-1, i0+1]
    kmax = int(min(1.15 * F_HI, FS / 2) * n / FS)
    g = (math.sqrt(5) - 1) / 2
    a_, b_ = i0 - 1.0, i0 + 1.0
    c_, d_ = b_ - g * (b_ - a_), a_ + g * (b_ - a_)
    fc, fd = pol * _h_at(H, c_, kmax), pol * _h_at(H, d_, kmax)
    for _ in range(30):
        if fc > fd:
            b_, d_, fd = d_, c_, fc
            c_ = b_ - g * (b_ - a_)
            fc = pol * _h_at(H, c_, kmax)
        else:
            a_, c_, fc = c_, d_, fd
            d_ = a_ + g * (b_ - a_)
            fd = pol * _h_at(H, d_, kmax)
    peak_t = (a_ + b_) / 2.0
    lat = peak_t if peak_t < n / 2 else peak_t - n
    # group delay by a phase-slope fit, phase unwrapped along bins: 1-2 kHz
    # (the S54 T8 figure) and 1-10 kHz (the path's delay is not constant)
    def gdfit(lo, hi):
        k1, k2 = int(round(lo * n / FS)), int(round(hi * n / FS))
        ph, prev = [], None
        for k in range(k1, k2 + 1):
            v = cmath.phase(R[k] * pol)
            if prev is not None:
                v += 2 * math.pi * round((prev - v) / (2 * math.pi))
            ph.append(v)
            prev = v
        ks = list(range(k1, k2 + 1))
        mk, mp = sum(ks) / len(ks), sum(ph) / len(ph)
        slope = (sum((k - mk) * (p - mp) for k, p in zip(ks, ph))
                 / sum((k - mk) ** 2 for k in ks))
        return -slope * n / (2 * math.pi)
    gd = gdfit(1000.0, 10000.0)
    gd12 = gdfit(1000.0, 2000.0)
    # response: |R| at the bins (every harmonic's contribution is inside it,
    # at its own level re the fundamental -- see the THD figure)
    ref = mag_at(R, f0)
    resp = [(f, 20 * math.log10(mag_at(R, f) / ref)) for f in points]
    gain_db = 20 * math.log10(ref)
    # harmonics, from an impulse with the slow LF ringing removed
    hh = [v.real for v in ifft(_masked(R, _hp_weight))]
    harm = []
    L_ = L
    for k in range(2, kmax_h + 1):
        dk = harmonic_delay(k, L_)
        a = int(0.5 * (harmonic_delay(k + 1, L_) - dk))
        b = int(0.5 * (dk - harmonic_delay(k - 1, L_)))
        c = int(round(peak_t - dk))
        seg = _taper(_circ(hh, c - a, a + b), 48)
        if k * f0 < F_HI:
            m = dtft_mag(seg, k * f0)
            harm.append((k, 20 * math.log10(m / ref) if m > 0 else float('-inf')))
    thd_lin = sum(10 ** (d / 10.0) for _, d in harm if d > float('-inf'))
    thd_db = 10 * math.log10(thd_lin) if thd_lin > 0 else float('-inf')
    out = {'n': n, 'period': L, 'latency_peak': lat, 'latency_gd_1k_10k': gd,
           'latency_gd_1k_2k': gd12,
           'polarity': pol, 'peak_h': h[i0], 'gain_1k_db': gain_db,
           'response': resp, 'harmonics': harm, 'thd_db': thd_db,
           'thd_pct': 100 * 10 ** (thd_db / 20.0)}
    if y2 is not None:
        Nz = fft([(a - b) / math.sqrt(2.0) for a, b in zip(y, y2)])
        out['snr'] = {}
        for fc_ in (20.0, 100.0, 1000.0, 10000.0, 20000.0):
            kc = int(round(fc_ * n / FS))
            half = max(1, int(round(9.0 * n / FS))) if fc_ < 100 else int(round(fc_ * 0.05 * n / FS))
            ks_ = [k for k in range(kc - half, kc + half + 1) if 0 < k < n // 2]
            s_ = sum(abs(Y[k]) ** 2 for k in ks_) / len(ks_)
            z_ = sum(abs(Nz[k]) ** 2 for k in ks_) / len(ks_)
            out['snr'][fc_] = 10 * math.log10(s_ / z_) if z_ > 0 else float('inf')
        dd = sum((a - b) ** 2 for a, b in zip(y, y2))
        out['repeat_rms_db'] = (10 * math.log10(dd / sum(a * a for a in y))
                                if dd > 0 else float('-inf'))
    return out


def compare_model(xcap, steps, level):
    """xcap: a captured reference (FS units). Returns (error re signal dB,
    max abs difference) against the host model scaled by `level`."""
    m = model(steps, level, len(xcap))
    e = sum((a - b) ** 2 for a, b in zip(xcap, m))
    s = sum(a * a for a in xcap)
    return (10 * math.log10(e / s) if e > 0 else float('-inf'),
            max(abs(a - b) for a, b in zip(xcap, m)))


def report(res, title=''):
    pr = print
    if title:
        pr(title)
    pr('  period %d samples (%.1f ms), sweep %g Hz -> %g Hz' % (res['period'], 1000 * res['period'] / FS, F_LO, F_HI))
    pr('  latency: impulse peak %.3f samples; group delay 1-2 kHz %.3f, 1-10 kHz %.3f samples'
       % (res['latency_peak'], res['latency_gd_1k_2k'], res['latency_gd_1k_10k']))
    pr('  polarity: %s (h at peak %+.4g)' % ('INVERTED' if res['polarity'] < 0 else 'non-inverted', res['peak_h']))
    pr('  gain at 1 kHz: %+.3f dB' % res['gain_1k_db'])
    pr('  response re 1 kHz:')
    for f, d in res['response']:
        pr('    %6g Hz  %+8.3f dB' % (f, d))
    pr('  harmonics at f0 = 1 kHz, re H1(1 kHz):')
    for k, d in res['harmonics']:
        pr('    h%d  %8.2f dB = %.5f %%' % (k, d, 100 * 10 ** (d / 20.0)))
    pr('  THD (2..%d) %.2f dB = %.5f %%' % (len(res['harmonics']) + 1, res['thd_db'], res['thd_pct']))
    if 'snr' in res:
        pr('  SNR per band (two captures): ' + ', '.join('%g Hz %.1f dB' % (f, v) for f, v in sorted(res['snr'].items())))
        pr('  capture-to-capture difference %.1f dB re signal' % res['repeat_rms_db'])


def _synthetic(x, D, G, a2=0.0, a3=0.0):
    L = len(x)
    z = [v + a2 * v * v + a3 * v * v * v for v in x]
    Z = fft(z)
    Yv = []
    for k in range(L):
        kk = k if k < L // 2 else k - L
        Yv.append(-G * Z[k] * cmath.exp(complex(0.0, -2 * math.pi * kk * D / L)))
    return [v.real for v in ifft(Yv)]


def selftest():
    """A synthetic path: fractional delay D, gain G, inverted; then the same
    with a memoryless x + a2 x^2 + a3 x^3 in front. Known answers: latency
    D, polarity -1, gain G, flat response; h2 = a2 A/2, h3 = a3 A^2/4."""
    ok = True
    A, a2, a3, D, G = 0.5, 0.01, 0.004, 91.4, 1.9
    x = model(0, A)

    def chk(name, got, want, tol):
        nonlocal ok
        good = abs(got - want) <= tol
        ok = ok and good
        print('  %-30s got %10.4f want %10.4f %s' % (name, got, want, 'OK' if good else 'FAIL'))
    r = analyse(_synthetic(x, D, G), x)
    report(r, 'SELFTEST 1 (linear: D=91.4, G=%.3f dB, inverted)' % (20 * math.log10(G)))
    chk('latency (peak)', r['latency_peak'], D, 0.02)
    chk('latency (group delay 1-10k)', r['latency_gd_1k_10k'], D, 0.02)
    chk('latency (group delay 1-2k)', r['latency_gd_1k_2k'], D, 0.02)
    chk('polarity', r['polarity'], -1, 0)
    chk('gain 1 kHz dB', r['gain_1k_db'], 20 * math.log10(G), 0.002)
    for f, d in r['response']:
        chk('response %g Hz' % f, d, 0.0, 0.005)
    r = analyse(_synthetic(x, D, G, a2, a3), x)
    report(r, 'SELFTEST 2 (a2=%.3g a3=%.3g at A=%.2f)' % (a2, a3, A))
    h = dict(r['harmonics'])
    chk('h2 dB', h[2], 20 * math.log10(a2 * A / 2), 0.1)
    chk('h3 dB', h[3], 20 * math.log10(a3 * A * A / 4 / (1 + 0.75 * a3 * A * A)), 0.1)
    print('SELFTEST', 'PASS' if ok else 'FAIL')
    return ok


if __name__ == '__main__':
    import sys
    sys.exit(0 if selftest() else 1)
