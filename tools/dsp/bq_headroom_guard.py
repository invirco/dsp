#!/usr/bin/env python3
"""bq_headroom_guard.py — the per-cascade headroom guard, sized, priced and
tested against the golden bar.

RIG C's write-up ends on one unbuilt thing: "headroom sized on |h|_1 per
cascade at PARAMETER-LOAD time ... that variant was priced by instruction
count and NEVER BUILT; it is the honest next spike." This is the numeric
half of that spike. The cycle half is rungs 16-18 of
SHARC/src/lib/bq_shootout.asm.

THE DESIGN, IN ONE PARAGRAPH. Round-once deletes the per-stage saturate,
so a cascade whose reachable internal magnitude exceeds Q4.28's ceiling of
8.0 WRAPS -- and in a direct-form-I recursion a wrap is a sign inversion
fed straight back into the poles. The bound that decides it is |h|_1, the
l1 norm of the impulse response, because that is what an arbitrary bounded
input can reach; max|H| is only what a sine can. So at PARAMETER-LOAD
time, once per coefficient swap, take the worst |h|_1 over every PARTIAL
cascade -- the wrap happens INSIDE, so a prefix that overflows overflows
whether or not the full cascade's gain comes back down -- and pick

    H = max(0, ceil(log2(|h|_1 * xmax / 8)))

Then in the sample loop the input is shifted down H bits on entry to the
cascade and the output is shifted back up and saturated ONCE on exit. Two
instructions per sample per CASCADE, not per stage, and H = 0 for the
overwhelming majority of the DEFS design space -- which is the whole point:
the settings that pay the headroom are the ones running +40 dB of gain,
where the noise floor that H costs is far below a signal that loud.

WHAT THIS SCRIPT REPORTS.

  1. H over the DEFS design space: how often the guard costs anything.
  2. For the named worst cascades -- including the two the state-bound
     work singled out, the HF shelf +12 dB Q5.01 and the four-band
     all-+15 dB coherent EQ -- the H it picks, whether the guarded kernel
     WRAPS under matched-sign worst-case drive (it must not), the response
     error against the contract, and the noise floor.
  3. The same three for the UNGUARDED round-once kernel, which is what
     shipped on 2026-09-03, so the guard's value is stated as a delta and
     not as an assertion.

The bar is golden_harness's 0.046 dB.

Usage: python3 bq_headroom_guard.py [--quick]
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixed_ref as F
from bq_float_delta import rbj_peak, rbj_shelf, curve_db, FS
from bound_efb import design_space
import bq_state_bound as SB

QB = F.QB
UNITY = 1 << QB
CEIL = 8.0                      # Q4.28's representable ceiling
BAR = 0.046                     # golden_harness's response bar


def _wrap32(v):
    return ((v + (1 << 31)) & 0xFFFFFFFF) - (1 << 31)


# ---------------------------------------------------------------------------
# The three kernels, as models. All three keep the ERROR FEEDBACK -- the
# ruling is to delete the saturate and nothing else.
# ---------------------------------------------------------------------------

def bq_contract(x, cq, st):
    """fixed_ref.biquad, per-stage saturating. The reference."""
    return F.biquad(x, cq, st)


def bq_roundonce(x, cq, st):
    """What landed 2026-09-03: the extract WRAPS instead of clamping."""
    b0, n1h, n2, c1, c2 = cq
    x1, x2, y1, y2, efb = st
    acc = (b0 * (x - 2 * x1 + x2) + n1h * x1 + n1h * x1 + n2 * x2
           - c1 * y1 + c2 * y2)
    acc += (2 * y1 - y2) << QB
    acc += efb
    y = _wrap32(F.rns(acc, QB))
    st[4] = acc - (y << QB)
    st[0], st[1] = x, x1
    st[2], st[3] = y, y1
    return y


def cascade_contract(xs, cqs):
    sts = [F.biquad_state() for _ in cqs]
    out = []
    for x in xs:
        y = x
        for cq, st in zip(cqs, sts):
            y = bq_contract(y, cq, st)
        out.append(y)
    return out


def cascade_roundonce(xs, cqs, H=0, guard=False):
    """The round-once cascade, optionally with the per-cascade guard.

    guard=False is the landed kernel: no entry shift, no exit clamp.
    guard=True is the spike: `x >> H` on entry (an arithmetic shift, one
    instruction), `sat32(y << H)` on exit (a shift and the same
    branch-free clamp the per-stage form used, once per cascade instead
    of once per stage).
    """
    sts = [F.biquad_state() for _ in cqs]
    out, wrapped = [], 0
    for x in xs:
        y = (x >> H) if guard else x
        for cq, st in zip(cqs, sts):
            yp = bq_roundonce(y, cq, st)
            # A wrap is detectable exactly: the unsaturated value of the
            # extract against the 32-bit word the kernel keeps.
            y = yp
        if guard:
            v = y << H
            if v > F.I32_MAX or v < F.I32_MIN:
                wrapped += 1
            y = F.sat32(v)
        out.append(y)
    return out, wrapped


def internal_wraps(xs, cqs, H=0, guard=False):
    """Count samples where any STAGE's extract left the 32-bit range.

    This is the event the guard exists to prevent, and it is not the same
    as the cascade output clipping: the wrap happens inside, in y1/y2, and
    is fed back into the poles before the cascade output exists.
    """
    sts = [F.biquad_state() for _ in cqs]
    n = 0
    for x in xs:
        y = (x >> H) if guard else x
        for cq, st in zip(cqs, sts):
            b0, n1h, n2, c1, c2 = cq
            x1, x2, y1, y2, efb = st
            acc = (b0 * (y - 2 * x1 + x2) + n1h * x1 + n1h * x1 + n2 * x2
                   - c1 * y1 + c2 * y2 + ((2 * y1 - y2) << QB) + efb)
            r = F.rns(acc, QB)
            if r > F.I32_MAX or r < F.I32_MIN:
                n += 1
            y = bq_roundonce(y, cq, st)
    return n


# ---------------------------------------------------------------------------
# |h|_1 over PARTIAL cascades -- the bound the guard is sized on
# ---------------------------------------------------------------------------

NCAP = 60000            # impulse-response length cap for the l1 sum


def dequant(cq):
    """The DIRECT-form float coefficients the quantised offset words mean.

    Exactly bq_float_delta.run_float's de-quantisation -- 2*nh IS n1 in
    Q4.28, because nh is n1/2 stored in Q5.27 and the kernel accumulates
    its product twice. Sizing the headroom off the DESIGN rather than off
    the loaded words would be sizing it off a filter the part does not
    run.
    """
    b0, n1h, n2, c1, c2 = cq
    return (F.from_q(b0),
            F.from_q(2 * n1h) - 2 * F.from_q(b0),
            F.from_q(n2) + F.from_q(b0),
            F.from_q(c1) - 2.0,
            1.0 - F.from_q(c2))


def _stage_filter(x, cf):
    b0, b1, b2, a1, a2 = cf
    y = np.empty_like(x)
    x1 = x2 = y1 = y2 = 0.0
    for i in range(x.size):
        v = b0 * x[i] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1 = x1, x[i]
        y2, y1 = y1, v
        y[i] = v
    return y


def l1_partial(cqs, ncap=NCAP):
    """max over PREFIXES of the l1 norm of the prefix's impulse response.

    Prefixes, because the wrap happens INSIDE: a four-band EQ whose bands
    cancel at the output can still have a partial cascade at +62 dB, and
    the partial cascade is what lives in y1/y2.

    Computed INCREMENTALLY -- prefix k's response is prefix k-1's
    response run through stage k -- so a 28-band GEQ costs 28 stage-runs
    and not 406. Whatever is still moving at the cap is BOUNDED AND
    ADDED, (|h[N-1]| + |h[N-2]|) * r/(1-r) with r the largest pole radius
    in the prefix, so the number is an UPPER bound on |h|_1 and never a
    truncation that flatters the guard.
    """
    cfs = [dequant(c) for c in cqs]
    r = max(min(math.sqrt(min(abs(cf[4]), 1.0)), 1 - 1e-12) for cf in cfs)
    n = int(min(ncap, math.ceil(25.0 / (1.0 - r)) + 4))
    x = np.zeros(n)
    x[0] = 1.0
    worst = 0.0
    for k, cf in enumerate(cfs):
        rk = max(min(math.sqrt(min(abs(c[4]), 1.0)), 1 - 1e-12)
                 for c in cfs[:k + 1])
        x = _stage_filter(x, cf)
        tail = (abs(x[-1]) + abs(x[-2])) * rk / (1.0 - rk)
        worst = max(worst, float(np.abs(x).sum()) + tail)
    return worst


def headroom_bits(l1, xmax=1.0):
    """H = ceil(log2(|h|_1 * xmax / 8)), floored at 0. Control rate."""
    need = l1 * xmax / CEIL
    return 0 if need <= 1.0 else int(math.ceil(math.log2(need)))


# ---------------------------------------------------------------------------
# Test material
# ---------------------------------------------------------------------------

def q(designs):
    return [F.biquad_coeffs_q(*d) for d in designs]


def lshelf(f0, qq, g):
    return rbj_shelf(f0, qq, g, False)


def hshelf(f0, qq, g):
    return rbj_shelf(f0, qq, g, True)


CASES = {
    'FILT: HPF 20 + LPF 20k':      None,     # filled below
    'peak +15 dB Q3 @1k':          [rbj_peak(1000, 3.0, 15.0)],
    'peak +15 dB Q10 @20':         [rbj_peak(20, 10.0, 15.0)],
    'peak +15 dB Q0.1 @5k':        [rbj_peak(5000, 0.1, 15.0)],
    'LF shelf +15 dB Q3.16 @20':   [lshelf(20, 3.16, 15.0)],
    'HF shelf +12 dB Q5.01 @20':   [hshelf(20, 5.01, 12.0)],
    '4-band EQ, mixed':            [rbj_peak(80, 1.1, 8.0),
                                    rbj_peak(400, 1.5, -6.0),
                                    rbj_peak(2500, 2.0, 6.0),
                                    rbj_peak(9000, 0.8, -4.0)],
    '4-band all +15 dB @1k Q1':    [rbj_peak(1000, 1.0, 15.0)] * 4,
    '28-band GEQ all +6 dB':       [rbj_peak(25 * (2 ** (i / 6.0)), 4.3, 6.0)
                                    for i in range(28)],
}


def hplp(f0, qq, hp):
    w0 = 2 * math.pi * f0 / FS
    al = math.sin(w0) / (2 * qq)
    c = math.cos(w0)
    b = ((1 + c) / 2, -(1 + c), (1 + c) / 2) if hp else \
        ((1 - c) / 2, (1 - c), (1 - c) / 2)
    a0 = 1 + al
    return (b[0] / a0, b[1] / a0, b[2] / a0, -2 * c / a0, (1 - al) / a0)


CASES['FILT: HPF 20 + LPF 20k'] = [hplp(20, 0.707, True),
                                   hplp(20, 0.707, True),
                                   hplp(20000, 0.707, False),
                                   hplp(20000, 0.707, False)]


def matched_sign_drive(cqs, n):
    """The input that ACHIEVES |h|_1: sign(h[k]) reversed in time.

    A square wave at f0 reaches only max|H|, which is exactly why sizing
    headroom off an EQ curve is the mistake the state-bound work names.
    """
    sts = [F.biquad_state() for _ in cqs]
    h = []
    for i in range(n):
        y = UNITY if i == 0 else 0
        for cq, st in zip(cqs, sts):
            y = bq_contract(y, cq, st)
        h.append(y)
    sgn = [1 if v >= 0 else -1 for v in h]
    return [sgn[n - 1 - i] * UNITY for i in range(n)]


def response_err(cqs, kernel, H=0, guard=False, N=8192):
    imp = [UNITY // 2] + [0] * (N - 1)          # -6 dBFS impulse
    ref = cascade_contract(imp, cqs)
    if kernel == 'contract':
        got = ref
    else:
        got, _ = cascade_roundonce(imp, cqs, H, guard)
    freqs = np.fft.rfftfreq(N, 1 / FS)
    band = (freqs >= 20) & (freqs <= 20000)
    a = curve_db(np.array(ref, dtype=float) / UNITY, N)
    b = curve_db(np.array(got, dtype=float) / UNITY, N)
    return float(np.max(np.abs(a[band] - b[band])))


def noise_floor(cqs, H=0, guard=False, n=16384, l1=1.0):
    """Residual RMS against float64 on the same quantised coefficients.

    THE DRIVE IS BACKED OFF WHEN THE CASCADE'S GAIN WOULD CLIP IT, and
    the level used is reported. A four-band +15 dB EQ has +62 dB of
    coherent gain: driven at -20 dBFS its output is +42 dBFS, the exit
    clamp fires on most samples, and what comes back is a clipping
    residual with a noise floor's name on it. That is the measurement
    error the first run of this script made.
    """
    amp = min(0.1, 4.0 / max(l1, 1e-9))          # -20 dBFS, or less
    xs = [int(round(amp * UNITY * math.sin(2 * math.pi * 997.0 * i / FS)))
          for i in range(n)]
    got, _ = cascade_roundonce(xs, cqs, H, guard)
    ref = []
    stf = [[0.0] * 4 for _ in cqs]
    cfs = [dequant(c) for c in cqs]
    for x in xs:
        y = x / UNITY
        for cf, st in zip(cfs, stf):
            y = F.biquad_f(y, cf, st)
        ref.append(y)
    e = np.array([g / UNITY for g in got]) - np.array(ref)
    r = float(np.sqrt(np.mean(e[1000:] ** 2)))
    return 20 * math.log10(max(r, 1e-30)), 20 * math.log10(amp)


def main():
    quick = '--quick' in sys.argv
    print('bq_headroom_guard — the per-cascade |h|_1 headroom guard\n')

    # ---- 1. how often the guard costs anything, over the DEFS space ----
    print('1. H over the DEFS design space (single stages, 0 dBFS drive)')
    # The single-stage sweep uses bq_state_bound.l1_norm, which is
    # vectorised ACROSS filters and picks its own length from each pole
    # radius (up to 400,000 samples) with the tail bounded and added.
    # l1_partial's incremental form is the right instrument for a
    # CASCADE and the wrong one for a quarter of a million single stages.
    # The coefficients handed to it are the DE-QUANTISED words, not the
    # float design, so what is bounded is the filter the part runs.
    tags, cfs = [], []
    for cf, tag in design_space(*(41, 21, 15) if quick else (121, 61, 41)):
        cq = F.biquad_coeffs_q(*cf)
        tags.append(tag)
        cfs.append(dequant(cq))
    l1s, tailfrac = SB.l1_norm(cfs)
    total = len(cfs)
    hist = {}
    for v in l1s:
        H = headroom_bits(float(v))
        hist[H] = hist.get(H, 0) + 1
    wi = int(np.argmax(l1s))
    worst = (float(l1s[wi]), tags[wi])
    print(f'   {total} quantised coefficient sets')
    for H in sorted(hist):
        print(f'   H = {H}: {hist[H]:7d}  {100.0 * hist[H] / total:6.2f}%')
    print(f'   worst single stage |h|_1 = {worst[0]:.1f} '
          f'(+{20 * math.log10(worst[0]):.1f} dB) at {worst[1]}')
    print(f'   l1 tail still moving at the cap: worst '
          f'{100.0 * float(np.max(tailfrac)):.4f}% of the sum')

    # ---- 2/3. the named cascades ----
    print('\n2. The named cascades: sizing, safety, response, noise')
    hdr = (f'{"cascade":30s} {"|h|_1":>8s} {"H":>2s} '
           f'{"wraps RO":>9s} {"wraps G":>8s} '
           f'{"err RO":>9s} {"err G":>9s} {"floor G":>9s} {"drive":>7s}')
    print('   ' + hdr)
    print('   ' + '-' * len(hdr))
    ndrive = 2000 if quick else 8000
    fails = []
    for name, designs in CASES.items():
        cqs = q(designs)
        l1 = l1_partial(cqs, ncap=8000 if quick else NCAP)
        H = headroom_bits(l1)
        drive = matched_sign_drive(cqs, ndrive)
        wro = internal_wraps(drive, cqs, 0, False)
        wg = internal_wraps(drive, cqs, H, True)
        ero = response_err(cqs, 'ro', 0, False)
        eg = response_err(cqs, 'ro', H, True)
        fg, drv = noise_floor(cqs, H, True,
                              n=4096 if quick else 16384, l1=l1)
        print(f'   {name:30s} {l1:8.1f} {H:2d} '
              f'{wro:9d} {wg:8d} {ero:9.4f} {eg:9.4f} {fg:9.1f} '
              f'{drv:7.1f}')
        if wg:
            fails.append(f'{name}: the GUARDED kernel wrapped {wg} times')
        if eg > BAR:
            fails.append(f'{name}: guarded response error {eg:.4f} dB '
                         f'is outside the {BAR} dB bar')
    print(f'\n   wraps counted over {ndrive} samples of MATCHED-SIGN drive at '
          f'0 dBFS -- the input that achieves |h|_1, not a sine')
    print(f'   response error is max |dB| over 20 Hz-20 kHz against the '
          f'contract; the golden bar is {BAR} dB')
    print('   noise floor is residual RMS against float64, dBFS, at the '
          '997 Hz drive named in the last column')
    if fails:
        print('\n   FAIL:')
        for f in fails:
            print(f'     {f}')
        return 1
    print('\n   PASS — the guard holds every named worst case with no '
          'internal wrap and inside the golden bar')
    return 0


if __name__ == '__main__':
    sys.exit(main())
