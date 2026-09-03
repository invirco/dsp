#!/usr/bin/env python3
"""bq_h_load.py — the LOAD-TIME sizer for the per-cascade headroom guard.

`bq_headroom_guard.py` sizes H the way an offline study can: it runs the
impulse response of every partial cascade to convergence, up to 60,000
samples, and bounds whatever is still moving. That is the right
instrument for deciding whether the guard is worth building. It is NOT
an algorithm a DSP can run at parameter-load time: a 20 Hz Q10 section
has a pole radius of 1 - 6.5e-5, so "to convergence" is a quarter of a
million samples, and a 28-band GEQ is twenty-eight of them.

THIS module is the algorithm the PART runs -- the normative model for
`SHARC/src/lib/bq_headroom.asm`, in the same relation to it as
`fixed_ref.py` is to `biquad_fx.asm`. It computes an UPPER BOUND on
max-over-prefixes |h|_1 from a BOUNDED number of samples, so its cost is
known before it starts.

THE ALGORITHM, and why each piece is there.

  N = clamp(ceil(6 / (1 - r_max)), 128, 1024)   samples, r_max = the
      largest pole radius in the cascade. Fast filters converge and stop;
      slow ones stop at the cap and lean on the tail bound.

  Run an impulse through the cascade ONE sample at a time, accumulating
  per PREFIX k:
      tot[k] += |h_k[n]|                      the truncated l1 sum
      env[k]  = max(env[k] * r_k, |h_k[n]|)   for n >= N/2

  bound[k] = tot[k] + env[k] * r_k / (1 - r_k)
  H        = max(0, ceil(log2(max_k bound[k] * xmax / 8)))

  env is a DECAYING PEAK-HOLD, and both halves of that matter. A plain
  window MAX under-reads by an unbounded factor when the window lands on
  a null of a low-frequency ring -- a 20 Hz mode has a 2400-sample
  period, so any window a load-time budget can afford is a fraction of
  one. Decaying the held peak by r per sample is what makes a peak found
  anywhere in the window still count, correctly discounted.

  THE WARM-UP (n >= N/2) IS NOT A REFINEMENT, IT IS THE DIFFERENCE
  BETWEEN 1.4x AND 2300x. The impulse itself is h[0] ~ 1 for any filter
  with a direct path; held at r ~ 1 it dominates env forever and the
  tail bound becomes |h[0]|/(1-r), which for a 20 Hz Q10 peak is 18,000
  against a true |h|_1 of 7.3. Excluding the first half of the run makes
  env an estimate of the RINGING amplitude, which is the thing the tail
  is made of.

  The tail term is an upper bound in the direction that matters: the
  true remaining sum of a decaying oscillation is about 2/pi of
  env*r/(1-r), because |cos| averages 2/pi and this bounds it by 1.

WHAT IS LOST AGAINST THE OFFLINE SIZER. Nothing, in the safe direction:
over the DEFS design space this bound is never below the converged
|h|_1 (`--check` is that bar) and is at worst a small multiple above it,
which spends a headroom bit that was not strictly needed. On CASCADES
the cap bites: a 28-band GEQ at N = 1024 is 1.6x, and the guard costs
one more bit than the offline sizer would pick.

Usage:
    python3 bq_h_load.py [--quick] [--check]
"""

import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixed_ref as F
import bq_state_bound as SB
from bound_efb import design_space

QB = F.QB
CEIL = 8.0                      # Q4.28's representable ceiling
NMIN = 128                      # samples: floor on the impulse run
NMAX = 1024                     # samples: the load-time work cap per prefix
NLEAD = 6.0                     # time constants of r_max to aim for
HMAX = 12                       # H is a 4-bit field; 12 bits is 72 dB
SAFETY = 1.125                  # bound + bound/8: one shift and one add


# ---------------------------------------------------------------------------
# de-quantisation: the DIRECT float coefficients the stored offset words mean
# ---------------------------------------------------------------------------

def dequant(cq):
    """[b0, nh, n2, c1, c2] Q4.28/Q5.27 -> (b0, b1, b2, a1, a2) float.

    Identical to bq_headroom_guard.dequant. The part sizes the filter it
    RUNS, not the filter that was designed: the quantised words are what
    the recursion has.
    """
    b0, n1h, n2, c1, c2 = cq
    return (F.from_q(b0),
            F.from_q(2 * n1h) - 2 * F.from_q(b0),
            F.from_q(n2) + F.from_q(b0),
            F.from_q(c1) - 2.0,
            1.0 - F.from_q(c2))


def pole_radius(a1, a2):
    """The LARGER pole radius, clamped off the unit circle.

    sqrt(|a2|) is the GEOMETRIC MEAN of the two roots and is the right
    answer only when they are a conjugate pair. For REAL roots -- every
    low-Q design, and every cascade of two identical HP/LP sections --
    it under-reads the slow one badly: a 20 Hz Q0.1 shelf has roots at
    0.9987 and 0.9948 and a geometric mean that says the ring dies
    faster than it does. That is an under-bound on the tail, which is
    the one direction a headroom sizer must never be wrong in.
    """
    disc = a1 * a1 - 4.0 * a2
    if disc <= 0.0:
        r = math.sqrt(max(abs(a2), 0.0))
    else:
        r = 0.5 * (abs(a1) + math.sqrt(disc))
    return min(r, 1.0 - 1e-9)


def run_length(rmax):
    """N, the sample budget. One number, computable before the run."""
    n = math.ceil(NLEAD / max(1.0 - rmax, 1e-12))
    return int(min(NMAX, max(NMIN, n)))


# ---------------------------------------------------------------------------
# the sizer itself — this is what bq_headroom.asm implements
# ---------------------------------------------------------------------------

def l1_bound(cfs):
    """Upper bound on max-over-prefixes |h|_1, from N samples.

    cfs: direct float coefficients per stage, first stage first.
    Returns (bound, N).
    """
    k = len(cfs)
    rad, rr = [], 0.0
    for cf in cfs:
        rr = max(rr, pole_radius(cf[3], cf[4]))
        rad.append(rr)                      # r_max over the PREFIX
    n_run = run_length(rad[-1])
    half = n_run // 2

    st = [[0.0, 0.0, 0.0, 0.0] for _ in cfs]
    tot = [0.0] * k
    env = [0.0] * k
    for n in range(n_run):
        v = 1.0 if n == 0 else 0.0
        for j, cf in enumerate(cfs):
            b0, b1, b2, a1, a2 = cf
            x1, x2, y1, y2 = st[j]
            y = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            st[j] = [v, x1, y, y1]
            v = y
            a = abs(y)
            tot[j] += a
            if n >= half:
                e = env[j] * rad[j]
                env[j] = a if a > e else e

    worst = 0.0
    for j in range(k):
        r = rad[j]
        worst = max(worst, tot[j] + env[j] * r / (1.0 - r))
    return worst * SAFETY, n_run


def headroom_bits(l1, xmax=1.0):
    """H = ceil(log2(|h|_1 * xmax / 8)), floored at 0, capped at HMAX."""
    need = l1 * xmax / CEIL
    if need <= 1.0:
        return 0
    return min(HMAX, int(math.ceil(math.log2(need))))


def size_h(cqs, xmax=1.0):
    """The whole parameter-load step: quantised words in, H out."""
    bound, n_run = l1_bound([dequant(c) for c in cqs])
    return headroom_bits(bound, xmax), bound, n_run


# ---------------------------------------------------------------------------
# vectorised single-stage form, for sweeping the DEFS space
# ---------------------------------------------------------------------------

def l1_bound_batch(cf):
    """l1_bound for a batch of SINGLE stages, vectorised over designs.

    Same arithmetic as l1_bound with k = 1, grouped by run length so a
    batch runs only as long as its slowest member needs.
    """
    arr = np.asarray(cf, dtype=np.float64)
    n = arr.shape[0]
    disc = arr[:, 3] ** 2 - 4.0 * arr[:, 4]
    r = np.where(disc <= 0.0,
                 np.sqrt(np.abs(arr[:, 4])),
                 0.5 * (np.abs(arr[:, 3]) + np.sqrt(np.maximum(disc, 0.0))))
    r = np.minimum(r, 1 - 1e-9)
    want = np.minimum(NMAX, np.maximum(NMIN, np.ceil(NLEAD / (1.0 - r))))
    want = want.astype(np.int64)
    out = np.zeros(n)
    order = np.argsort(want)
    step = 4000
    for s0 in range(0, n, step):
        idx = order[s0:s0 + step]
        a = arr[idx]
        b0, b1, b2, a1, a2 = (a[:, i].copy() for i in range(5))
        rr = r[idx]
        big = int(want[idx].max())
        mine = want[idx]
        x1 = np.zeros_like(b0); x2 = np.zeros_like(b0)
        y1 = np.zeros_like(b0); y2 = np.zeros_like(b0)
        tot = np.zeros_like(b0); env = np.zeros_like(b0)
        for i in range(big):
            v = 1.0 if i == 0 else 0.0
            y = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
            x2, x1 = x1, np.full_like(b0, v)
            y2, y1 = y1, y
            av = np.abs(y)
            live = i < mine
            tot += np.where(live, av, 0.0)
            warm = live & (i >= mine // 2)
            env = np.where(warm, np.maximum(env * rr, av), env)
        out[idx] = (tot + env * rr / (1.0 - rr)) * SAFETY
    return out


# ---------------------------------------------------------------------------
# the bar
# ---------------------------------------------------------------------------

def check(quick):
    import bq_headroom_guard as G

    print('bq_h_load — the load-time sizer, against the offline one\n')
    print(f'   N = clamp(ceil({NLEAD:.0f}/(1-r_max)), {NMIN}, {NMAX}); '
          f'env warm-up at N/2; tail = env*r/(1-r)')

    # ---- 1. single stages over the DEFS design space ----
    print('\n1. DEFS design space, single stages: sized bound vs converged '
          '|h|_1')
    cfs, tags = [], []
    for cf, tag in design_space(*(41, 21, 15) if quick else (121, 61, 41)):
        cq = F.biquad_coeffs_q(*cf)
        cfs.append(dequant(cq))
        tags.append(tag)
    exact, _ = SB.l1_norm(cfs)
    got = l1_bound_batch(cfs)
    total = len(cfs)

    under = got < exact * (1.0 - 1e-9)
    nunder = int(under.sum())
    ratio = got / np.maximum(exact, 1e-30)
    hist_e, hist_g, extra = {}, {}, {}
    for e, g in zip(exact, got):
        he, hg = headroom_bits(float(e)), headroom_bits(float(g))
        hist_e[he] = hist_e.get(he, 0) + 1
        hist_g[hg] = hist_g.get(hg, 0) + 1
        extra[hg - he] = extra.get(hg - he, 0) + 1
    print(f'   {total} quantised coefficient sets')
    print(f'   {"H":>3s} {"offline":>9s} {"load-time":>10s}')
    for h in sorted(set(hist_e) | set(hist_g)):
        print(f'   {h:3d} {hist_e.get(h, 0):9d} {hist_g.get(h, 0):10d}')
    print(f'   bound/exact: median {np.median(ratio):.3f}, '
          f'p99 {np.percentile(ratio, 99):.3f}, max {ratio.max():.3f}')
    print('   extra headroom bits vs the offline sizer:')
    for d in sorted(extra):
        print(f'      {d:+d}: {extra[d]:8d}  {100.0 * extra[d] / total:6.2f}%')
    wi = int(np.argmax(ratio))
    print(f'   loosest: {tags[wi]}  exact {exact[wi]:.2f} -> '
          f'bound {got[wi]:.2f}')
    if nunder:
        wu = int(np.argmin(ratio))
        print(f'   UNDER-SIZED on {nunder} sets, worst {ratio.min():.4f} '
              f'at {tags[wu]}')

    # ---- 2. the named cascades ----
    print('\n2. The named cascades (bq_headroom_guard.CASES)')
    hdr = (f'{"cascade":30s} {"exact":>9s} {"H off":>5s} {"N":>5s} '
           f'{"bound":>10s} {"H load":>6s} {"ratio":>6s}')
    print('   ' + hdr)
    print('   ' + '-' * len(hdr))
    cund = []
    for name, designs in G.CASES.items():
        cqs = G.q(designs)
        ex = G.l1_partial(cqs, ncap=60000)
        h, bound, n_run = size_h(cqs)
        he = G.headroom_bits(ex)
        print(f'   {name:30s} {ex:9.2f} {he:5d} {n_run:5d} '
              f'{bound:10.2f} {h:6d} {bound / ex:6.2f}')
        if bound < ex * (1.0 - 1e-9):
            cund.append(f'{name}: bound {bound:.2f} < |h|_1 {ex:.2f}')

    ok = (nunder == 0) and not cund
    if ok:
        print('\n   PASS — the load-time bound is never below the converged '
              '|h|_1, on any DEFS single stage or named cascade')
    else:
        print('\n   FAIL:')
        if nunder:
            print(f'     {nunder} single stages under-sized')
        for c in cund:
            print(f'     {c}')
    return 0 if ok else 1


def main():
    if '--check' in sys.argv or len(sys.argv) == 1 or '--quick' in sys.argv:
        return check('--quick' in sys.argv)
    return 0


if __name__ == '__main__':
    sys.exit(main())
