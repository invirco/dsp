#!/usr/bin/env python3
"""dsp4_fft.py <capture.json> [--lane N] [--png FILE] — the spectrum of a
DSP4 lane capture: fundamental, THD+N, SNR, noise floor, spurs.

WHY THIS EXISTS (S49 R4). The DSP publishes RmsResult / ThdResult /
NoiseResult out of TEST_MEAS, and a number a part publishes about itself is
worth exactly as much as the independent measurement that agrees with it.
This is that independent measurement: it takes the SAME block of samples the
scope tap captured, on the host, in a completely different arithmetic, by a
completely different method -- a windowed DFT rather than a least-squares fit
in the time domain -- and prints the same four quantities. Agreement between
the two is evidence about the signal. Disagreement is evidence about one of
the two instruments, and the one to distrust is whichever cannot say how it
got its answer.

IT IS ALSO THE TROUBLESHOOTING INSTRUMENT PW ASKED FOR. A THD+N figure says
a path is dirty; a spectrum says WHY -- harmonic 2 above harmonic 3 is a
clipping asymmetry, a spur at 48 kHz/N is a converter or fabric artefact, a
rising skirt around the fundamental is phase noise or a level that is moving
during the capture, and a floor that is flat and featureless is dither and
nothing to chase.

STDLIB ONLY, ON PURPOSE. The bench CM4 (MW-D24-2) has no numpy and no
matplotlib, and a tool that only runs somewhere else is not a CM4-side tool.
The DFT below is a plain iterative radix-2 FFT in `cmath`; at the capture
sizes the scope produces (1024 words, 4096 at most) it finishes in well under
a second. numpy IS used when it happens to be importable, purely for speed,
and the tool SAYS which arithmetic produced the answer -- the two agree to
better than 1e-9 dB on the same input, which is checked by --selftest. The
PNG is written by a small encoder at the bottom of this file, so a figure can
be produced on the bench without installing anything there either.

THE CAPTURE FORMAT is written by dsp4_s49_cap.py and is deliberately dull:

    {"tool": "dsp4_s49_cap", "version": 1,
     "fs_hz": 48000,
     "node": "C1_FDR_05",          # what was tapped
     "scale": "q4.28",             # or "rx24in32"  -- see SCALES
     "lanes": 1,                   # interleaved if > 1
     "samples": [<int32>, ...]}

`scale` is not decoration: it is the whole difference between a level quoted
against converter full scale and one quoted against the 8.0 accumulator
ceiling, which is 18.06 dB, and S48 section 7.2 is the record of that costing
a session's worth of confusion. The file says which one it is and this tool
does not guess.

Usage:
    dsp4_fft.py capture.json
    dsp4_fft.py capture.json --lane 1 --png spectrum.png
    dsp4_fft.py --selftest            # synthetic signals, known answers
"""
import cmath
import json
import math
import struct
import sys
import zlib

# --------------------------------------------------------------------------
# Sample scales. THE FILE DECLARES ONE; this table turns it into a divisor
# that puts 0 dBFS at 1.0.
#
#   q4.28      a node's block, where 1.0 = 0x10000000 is converter full
#              scale (S48 7.2). The accumulator ceiling is 8.0, three bits
#              above, and is NOT full scale.
#   rx24in32   a converter RX slot, 24 bits left-justified in 32, so full
#              scale is 2^31.
# --------------------------------------------------------------------------
SCALES = {
    'q4.28':    float(1 << 28),
    'rx24in32': float(1 << 31),
}

# Harmonics counted into THD (THD+N counts everything, harmonic or not).
N_HARMONICS = 10


def db(x):
    return 10.0 * math.log10(x) if x > 0 else float('-inf')


def db20(x):
    return 20.0 * math.log10(x) if x > 0 else float('-inf')


# --------------------------------------------------------------------------
# The transform
# --------------------------------------------------------------------------

def _fft_py(x):
    """Iterative radix-2 FFT, stdlib only. len(x) must be a power of two."""
    n = len(x)
    if n & (n - 1):
        raise ValueError('FFT length %d is not a power of two' % n)
    a = list(x)
    # bit-reversal permutation
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
        ang = -2.0 * math.pi / length
        wl = cmath.exp(complex(0.0, ang))
        for i in range(0, n, length):
            w = complex(1.0, 0.0)
            half = length >> 1
            for k in range(i, i + half):
                u = a[k]
                v = a[k + half] * w
                a[k] = u + v
                a[k + half] = u - v
                w *= wl
        length <<= 1
    return a


def fft(x):
    """(spectrum, which) -- numpy when it is there, cmath when it is not."""
    try:
        import numpy as _np
    except ImportError:
        return _fft_py(x), 'cmath (stdlib)'
    return list(_np.fft.fft(_np.asarray(x, dtype=float))), \
        'numpy %s' % _np.__version__


# --------------------------------------------------------------------------
# The window
#
# A 7-TERM BLACKMAN-HARRIS, and the choice is the measurement and not taste.
#
# The capture is NOT coherent -- nothing makes the oscillator's frequency an
# exact multiple of fs/N, and TEST_MEAS deliberately does not require it -- so
# the fundamental leaks into every other bin, and whatever leaks is counted as
# distortion or noise by anything that measures what is left. A Hann window
# leaks to -31 dB and would bury the measurement. The FOUR-term Blackman-
# Harris that this tool carried first leaks to -92 dB, which sounds like
# plenty and is not: integrated across a half spectrum it puts the
# instrument's own THD+N floor at -97 dB with a 4-bin band and -111 dB with a
# 16-bin one -- ABOVE the DSP node's -115 dB floor, so the FFT would have been
# the limiting instrument in the very comparison it exists to make.
#
# The 7-term window leaks below -180 dB. Measured on a synthetic pure tone
# (--selftest), the floor is then -140 to -160 dB depending on where the tone
# falls between bins, and for a tone that lands exactly on a bin it is the
# float64 transform's own noise -- i.e. the window has stopped being the
# limit. Nothing in this system is within 40 dB of that.
#
# The price is a main lobe 14 bins wide, so a tone owns +-TONE_BAND bins and
# not one. At a 1024-sample capture that is +-375 Hz, which is why `analyse`
# warns when the fundamental's band and DC's band would touch: below about
# 800 Hz a 1024-point capture cannot separate the two, and the answer is a
# longer capture, not a narrower band.
# --------------------------------------------------------------------------
_BH7 = (0.27105140069342, -0.43329793923448, 0.21812299954311,
        -0.06592544638803, 0.01081174209837, -0.00077658482522,
        0.00001388721735)
# Bins either side of a tone that belong to that tone: half the main lobe,
# rounded up. 7 would do; 8 is one bin of margin.
TONE_BAND = 8


def blackman_harris(n):
    """The PERIODIC form -- 2*pi*i/n, not /(n-1). The DFT assumes the window
    repeats with period n; the symmetric form is for filter design, and using
    it here costs a hundredth of a dB on the level and a good deal more on
    the leakage."""
    return [sum(_BH7[k] * math.cos(2.0 * math.pi * k * i / n)
                for k in range(len(_BH7)))
            for i in range(n)]


def _band_energy(psd, centre, half):
    """Sum the one-sided power in bins [centre-half, centre+half]."""
    lo = max(0, centre - half)
    hi = min(len(psd) - 1, centre + half)
    return sum(psd[lo:hi + 1]), lo, hi


# --------------------------------------------------------------------------
# The analysis
# --------------------------------------------------------------------------

def analyse(samples, fs, half_lobe=TONE_BAND, dc_bins=TONE_BAND):
    """Everything this tool knows about one lane, as a dict.

    Powers are RMS dBFS against Q4.28 (or RX) full scale, the SAME
    reference TEST_MEAS publishes on, so the two instruments' numbers can
    be put side by side without a conversion. A full-scale sine reads
    -3.01 dBFS on both.
    """
    n = 1
    while n * 2 <= len(samples):
        n *= 2
    if n < 64:
        raise SystemExit('dsp4_fft.py: %d samples is too few to transform'
                         % len(samples))
    x = samples[:n]
    w = blackman_harris(n)
    xw = [x[i] * w[i] for i in range(n)]
    spec, engine = fft(xw)

    half = n // 2
    # PARSEVAL NORMALISATION, and this is the line that makes the tool
    # comparable with the DSP at all.
    #
    # Sum_k |X_k|^2 = n * Sum_i |x_i w_i|^2, and for any signal whose
    # spectrum does not move across the window the right-hand side is
    # (mean square of x) * Sum_i w_i^2. So dividing every bin by
    # n * Sum w^2 makes the ONE-SIDED SUM OF THE SPECTRUM EQUAL THE MEAN
    # SQUARE -- which is exactly what TEST_MEAS publishes as RmsResult,
    # 10*log10(Sxx/N). Every level here is therefore RMS dBFS on the same
    # reference as the node, and a full-scale SINE reads -3.01 dBFS, not 0.
    #
    # The obvious alternative -- coherent gain, |X_k|/(n*Sum(w)/n) -- is
    # right for reading ONE bin's amplitude and wrong for summing a band,
    # because it normalises amplitude and the band sum is a power. It was
    # in this tool first and it was 0.01 dB out on a 4-term window and
    # 1.18 dB out on a 7-term one, which is how it was caught.
    pg = sum(v * v for v in w)
    psd = []
    for k in range(half + 1):
        p = (abs(spec[k]) ** 2) / (n * pg)
        if 0 < k < half:
            p *= 2.0
        psd.append(p)

    total = sum(psd)
    # DC is not signal and is not noise; it is offset, and it is reported
    # separately rather than counted into either.
    dc = sum(psd[:dc_bins + 1])

    # THE FUNDAMENTAL is the largest band away from DC.
    search = psd[dc_bins + 1:]
    if not search:
        raise SystemExit('dsp4_fft.py: nothing above DC to analyse')
    kf = dc_bins + 1 + max(range(len(search)), key=lambda i: search[i])
    pf, flo, fhi = _band_energy(psd, kf, half_lobe)

    # Interpolated frequency: the power centroid across the fundamental's
    # own band. Good to a small fraction of a bin and needs no assumption
    # about the window's shape.
    num = sum(psd[k] * k for k in range(flo, fhi + 1))
    f_bin = num / pf if pf > 0 else float(kf)
    f_hz = f_bin * fs / n

    claimed = set(range(flo, fhi + 1)) | set(range(0, dc_bins + 1))
    # THE ONE CASE THIS CANNOT RESOLVE, said out loud rather than folded
    # into the answer: a tone low enough that its band touches DC's.
    crowded = flo <= dc_bins + 1

    # HARMONICS, each integrated over its own band, each band claimed so it
    # is not also counted as a spur below.
    harmonics = []
    for h in range(2, N_HARMONICS + 1):
        kh = int(round(f_bin * h))
        if kh > half - half_lobe:
            break
        ph, hlo, hhi = _band_energy(psd, kh, half_lobe)
        harmonics.append({'n': h, 'bin': kh, 'hz': kh * fs / n,
                          'dbc': db(ph / pf) if pf > 0 else float('-inf'),
                          'dbfs': db(ph)})
        claimed |= set(range(hlo, hhi + 1))

    # NOISE+DISTORTION is everything that is not the fundamental and not DC.
    resid = total - pf - dc
    if resid < 0.0:
        resid = 0.0
    # NOISE alone leaves the harmonics out as well.
    noise_only = resid - sum(10.0 ** (h['dbfs'] / 10.0) for h in harmonics)
    if noise_only < 0.0:
        noise_only = 0.0
    thd = sum(10.0 ** (h['dbfs'] / 10.0) for h in harmonics)

    # SPURS: the loudest unclaimed bins, which is where a fabric or
    # converter artefact shows up and a harmonic analysis will not find it.
    spurs = sorted(((psd[k], k) for k in range(dc_bins + 1, half + 1)
                    if k not in claimed), reverse=True)[:8]
    spurs = [{'bin': k, 'hz': k * fs / n, 'dbfs': db(p),
              'dbc': db(p / pf) if pf > 0 else float('-inf')}
             for p, k in spurs]

    # Per-bin noise floor: the MEDIAN unclaimed bin, which is immune to the
    # handful of spurs a mean would be dragged by.
    unclaimed = sorted(psd[k] for k in range(dc_bins + 1, half + 1)
                       if k not in claimed)
    floor_bin = unclaimed[len(unclaimed) // 2] if unclaimed else 0.0

    # IS THERE A TONE AT ALL? Everything above assumes the largest band is a
    # fundamental; on a silent capture the largest band is just the largest
    # NOISE bin, and the tool then prints a positive THD+N and a negative
    # SNR -- which happened on the S49 negative arm and reads like a
    # measurement if nobody is looking. The test is how far the fundamental
    # stands above the median bin: a real tone in a 1024-point transform
    # clears it by tens of dB, and 20 dB is comfortably below anything this
    # instrument is used for.
    tone = (pf > 0 and floor_bin > 0
            and db(pf / (floor_bin * (2 * half_lobe + 1))) > 20.0)

    return {
        'engine': engine, 'n': n, 'fs': fs, 'bin_hz': fs / n,
        'psd': psd,
        'total_dbfs': db(total),
        'dc_dbfs': db(dc),
        'fund_bin': kf, 'fund_hz': f_hz, 'fund_dbfs': db(pf),
        'thdn_db': db(resid / pf) if pf > 0 else float('-inf'),
        'thdn_dbfs': db(resid),
        'thd_db': db(thd / pf) if pf > 0 else float('-inf'),
        'snr_db': db(pf / noise_only) if noise_only > 0 else float('inf'),
        'noise_dbfs': db(noise_only),
        'floor_bin_dbfs': db(floor_bin),
        'harmonics': harmonics,
        'spurs': spurs,
        'crowded': crowded,
        'tone': tone,
        'band_hz': half_lobe * fs / n,
    }


# --------------------------------------------------------------------------
# A PNG, without matplotlib
#
# One plot, the one that is worth looking at: the one-sided spectrum in dBFS
# against a log frequency axis, with the fundamental and the harmonics marked
# and the measured floor drawn across. Everything is rasterised into a byte
# array and deflated; there is no font, so the axis is labelled by tick marks
# and the numbers live in the caption the caller writes beside it.
# --------------------------------------------------------------------------
_W, _H = 1000, 460
_L, _R, _T, _B = 70, 20, 24, 44


def _png_write(path, rows, w, h):
    raw = b''.join(b'\x00' + bytes(r) for r in rows)

    def chunk(tag, data):
        c = tag + data
        return (struct.pack('>I', len(data)) + c
                + struct.pack('>I', zlib.crc32(c) & 0xFFFFFFFF))
    hdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)   # 8-bit truecolour
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', hdr))
        f.write(chunk(b'IDAT', zlib.compress(raw, 9)))
        f.write(chunk(b'IEND', b''))


def write_png(path, res, title_hz):
    w, h = _W, _H
    px = [[0xF8] * (w * 3) for _ in range(h)]

    def put(x, y, rgb):
        if 0 <= x < w and 0 <= y < h:
            px[y][x * 3:x * 3 + 3] = list(rgb)

    def vline(x, y0, y1, rgb):
        for y in range(min(y0, y1), max(y0, y1) + 1):
            put(x, y, rgb)

    def hline(y, x0, x1, rgb):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            put(x, y, rgb)

    psd = res['psd']
    fs, n = res['fs'], res['n']
    f_lo, f_hi = 10.0, fs / 2.0
    d_lo, d_hi = -180.0, 6.0

    def sx(f):
        f = max(f, f_lo)
        return int(_L + (w - _L - _R) * (math.log10(f) - math.log10(f_lo))
                   / (math.log10(f_hi) - math.log10(f_lo)))

    def sy(d):
        d = min(max(d, d_lo), d_hi)
        return int(_T + (h - _T - _B) * (d_hi - d) / (d_hi - d_lo))

    # frame and grid
    GRID, AXIS, TRACE = (0xDD, 0xDD, 0xDD), (0x44, 0x44, 0x44), (0x1F, 0x4E, 0x9C)
    for d in range(-180, 7, 20):
        hline(sy(d), _L, w - _R, GRID)
    for f in (10, 20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000):
        if f <= f_hi:
            vline(sx(f), _T, h - _B, GRID)
            vline(sx(f), h - _B, h - _B + 6, AXIS)
    hline(sy(0), _L, w - _R, (0xBB, 0xBB, 0xBB))
    vline(_L, _T, h - _B, AXIS)
    hline(h - _B, _L, w - _R, AXIS)

    # the trace: one column per pixel, holding the LOUDEST bin in that
    # column, because a log axis maps thousands of bins onto one pixel at
    # the top end and a mean would hide exactly what is being looked for.
    col = {}
    for k in range(1, len(psd)):
        f = k * fs / n
        if f < f_lo:
            continue
        x = sx(f)
        v = db(psd[k])
        if x not in col or v > col[x]:
            col[x] = v
    xs = sorted(col)
    prev = None
    for x in xs:
        y = sy(col[x])
        if prev is not None and abs(y - prev[1]) > 1:
            vline(x, prev[1], y, TRACE)
        put(x, y, TRACE)
        put(x, y + 1, TRACE)
        prev = (x, y)

    # the measured per-bin floor
    hline(sy(res['floor_bin_dbfs']), _L, w - _R, (0x9A, 0x9A, 0x9A))

    # fundamental and harmonics
    vline(sx(res['fund_hz']), sy(res['fund_dbfs']) - 10,
          sy(res['fund_dbfs']), (0xC0, 0x39, 0x2B))
    for hh in res['harmonics']:
        if hh['hz'] <= f_hi:
            vline(sx(hh['hz']), sy(hh['dbfs']) - 8, sy(hh['dbfs']),
                  (0xE6, 0x7E, 0x22))
    for sp in res['spurs'][:4]:
        if sp['dbc'] > -140.0:
            vline(sx(sp['hz']), sy(sp['dbfs']) - 5, sy(sp['dbfs']),
                  (0x27, 0xAE, 0x60))

    _png_write(path, px, w, h)


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def pct(db):
    """A ratio in dB as percent, printed beside every THD, THD+N and
    harmonic figure (PW 2026-09-16): % = 100 * 10^(dB/20)."""
    if db == float('-inf'):
        return '0 %'
    return '%.5f %%' % (100.0 * 10.0 ** (db / 20.0))


def report(res, cap, lane):
    print('dsp4_fft — %s%s' % (cap.get('node', '?'),
                               '' if cap.get('lanes', 1) == 1
                               else '  lane %d' % lane))
    print('  %d samples at %g Hz, scale %s, %d-point transform (%s)'
          % (len(cap['samples']) // cap.get('lanes', 1), res['fs'],
             cap.get('scale', '?'), res['n'], res['engine']))
    print('  bin %.4f Hz, 7-term Blackman-Harris, tone bands +-%d bins '
          '(+-%.1f Hz)' % (res['bin_hz'], TONE_BAND, res['band_hz']))
    if res['crowded']:
        print('  ** the fundamental\'s band touches DC\'s: at %.1f Hz a '
              '%d-point capture' % (res['fund_hz'], res['n']))
        print('  ** cannot separate them. THD+N and noise are UPPER BOUNDS '
              'here; capture longer.')
    print('')
    if not res['tone']:
        print('  ** NO TONE IN THIS CAPTURE. The largest band is only %.1f dB'
              % (res['fund_dbfs'] - res['floor_bin_dbfs']))
        print('  ** above the median bin, so it is noise and not a')
        print('  ** fundamental. THD+N and SNR below are MEANINGLESS -- the')
        print('  ** figure worth reading is `total`, which is the capture\'s')
        print('  ** RMS level and is valid either way.')
        print('')
    print('  fundamental     %10.4f Hz   %8.2f dBFS  (bin %d)'
          % (res['fund_hz'], res['fund_dbfs'], res['fund_bin']))
    print('  total           %28.2f dBFS' % res['total_dbfs'])
    print('  DC              %28.2f dBFS' % res['dc_dbfs'])
    print('  THD+N           %28.2f dB    = %s   (%.2f dBFS)'
          % (res['thdn_db'], pct(res['thdn_db']), res['thdn_dbfs']))
    print('  THD (2..%d)      %27.2f dB    = %s'
          % (N_HARMONICS, res['thd_db'], pct(res['thd_db'])))
    print('  SNR             %28.2f dB' % res['snr_db'])
    print('  noise           %28.2f dBFS' % res['noise_dbfs'])
    print('  floor / bin     %28.2f dBFS' % res['floor_bin_dbfs'])
    print('')
    print('  harmonics')
    any_h = False
    for hh in res['harmonics']:
        if hh['dbc'] > -160.0:
            any_h = True
            print('    h%-2d %10.2f Hz   %8.2f dBc = %s   %8.2f dBFS'
                  % (hh['n'], hh['hz'], hh['dbc'], pct(hh['dbc']),
                     hh['dbfs']))
    if not any_h:
        print('    none above -160 dBc')
    print('')
    print('  loudest non-harmonic bins (spurs)')
    for sp in res['spurs'][:6]:
        print('    %10.2f Hz   %8.2f dBc   %8.2f dBFS'
              % (sp['hz'], sp['dbc'], sp['dbfs']))


# --------------------------------------------------------------------------
# Self-test: synthetic signals whose answers are known in closed form.
# --------------------------------------------------------------------------

def selftest():
    fs, n = 48000.0, 4096
    ok = True

    def check(name, got, want, tol):
        nonlocal ok
        good = abs(got - want) <= tol
        ok = ok and good
        print('  %-38s got %11.4f  want %11.4f  %s'
              % (name, got, want, 'OK' if good else 'FAIL'))

    # 1. a pure tone at a NON-integer number of cycles per window -- the
    #    case coherent-sampling instruments get wrong and this one must not
    f0, amp = 997.3, 0.5
    sig = [amp * math.sin(2 * math.pi * f0 * i / fs) for i in range(n)]
    r = analyse(sig, fs)
    check('pure tone: frequency, Hz', r['fund_hz'], f0, 0.5)
    # RMS dBFS -- the same reference TEST_MEAS publishes on, so a sine of
    # peak 0.5 reads 20*log10(0.5/sqrt(2)) and NOT 3 dB above it.
    check('pure tone: level, RMS dBFS', r['fund_dbfs'],
          db20(amp / math.sqrt(2)), 0.01)
    # THE INSTRUMENT'S OWN FLOOR, which is the number that says whether this
    # tool can be a witness for the DSP node at all. With the 7-term window
    # it is below -130 dB and often below what float64 can represent at all
    # (-inf here means the leakage vanished into the rounding of a sum of
    # 2049 positive numbers, not that something went wrong).
    print('  %-38s %s dB   (the instrument floor)'
          % ('pure tone: THD+N', ('%11.4f' % r['thdn_db'])
             if r['thdn_db'] > float('-inf') else '       -inf'))
    if r['thdn_db'] > -130.0:
        print('    FAIL -- the window is the limit, not the signal')
        ok = False

    # 2. a tone with a known second harmonic: THD must come back at the
    #    amplitude ratio and nothing else
    h2 = 0.01                      # -40 dB relative to the fundamental
    sig = [math.sin(2 * math.pi * f0 * i / fs)
           + h2 * math.sin(4 * math.pi * f0 * i / fs) for i in range(n)]
    r = analyse(sig, fs)
    check('tone + h2 at -40 dB: h2, dBc', r['harmonics'][0]['dbc'],
          db20(h2), 0.2)
    check('tone + h2 at -40 dB: THD, dB', r['thd_db'], db20(h2), 0.2)

    # 3. a tone plus a known white noise floor: SNR must come back at the
    #    ratio of the two powers
    import random
    random.seed(20260915)
    nf = 1e-3
    sig = [math.sin(2 * math.pi * f0 * i / fs)
           + random.gauss(0.0, nf) for i in range(n)]
    r = analyse(sig, fs)
    want_snr = db(0.5 / (nf * nf))
    check('tone + noise: SNR, dB', r['snr_db'], want_snr, 1.0)

    # 4. the two transforms must agree
    try:
        import numpy  # noqa: F401
        a = _fft_py(sig[:1024])
        b = list(numpy.fft.fft(numpy.asarray(sig[:1024], dtype=float)))
        worst = max(abs(a[i] - b[i]) for i in range(1024))
        check('cmath vs numpy, worst bin', worst, 0.0, 1e-7)
    except ImportError:
        print('  (numpy absent; the cmath transform is the only arithmetic)')

    print('')
    print('SELFTEST %s' % ('PASSED' if ok else 'FAILED'))
    return 0 if ok else 1


# --------------------------------------------------------------------------

def main(argv):
    if '--selftest' in argv:
        return selftest()
    args = [a for a in argv if not a.startswith('--')]
    if not args:
        print(__doc__)
        return 2
    lane = 0
    png = None
    for i, a in enumerate(argv):
        if a == '--lane':
            lane = int(argv[i + 1])
        elif a.startswith('--lane='):
            lane = int(a.split('=', 1)[1])
        elif a == '--png':
            png = argv[i + 1]
        elif a.startswith('--png='):
            png = a.split('=', 1)[1]

    with open(args[0]) as f:
        cap = json.load(f)
    scale = cap.get('scale')
    if scale not in SCALES:
        raise SystemExit(
            'dsp4_fft.py: capture declares scale %r, which is not one of %s. '
            'The scale decides what 0 dBFS means and the difference between '
            'the two is 18.06 dB (S48 7.2) -- this tool will not guess it.'
            % (scale, '/'.join(sorted(SCALES))))
    fsdiv = SCALES[scale]
    lanes = int(cap.get('lanes', 1))
    if not 0 <= lane < lanes:
        raise SystemExit('dsp4_fft.py: lane %d of %d' % (lane, lanes))
    raw = cap['samples'][lane::lanes] if lanes > 1 else cap['samples']
    sig = [(v - (1 << 32) if v & 0x80000000 else v) / fsdiv
           if v >= 0 else v / fsdiv for v in raw]

    res = analyse(sig, float(cap.get('fs_hz', 48000)))
    report(res, cap, lane)
    if png:
        write_png(png, res, res['fund_hz'])
        print('')
        print('  figure: %s' % png)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
