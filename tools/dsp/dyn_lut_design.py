#!/usr/bin/env python3
"""dyn_lut_design.py — the level->gain table: design it, and MEASURE its error.

WHY THIS EXISTS.  S14 measured the level->gain LUT on the part and found
it worth 77 % of the dynamics gain computer and 58.5 % of the whole
compressor body.  What the rig could NOT see is the error: the table's
contents do not change the instruction stream, so cycles and accuracy are
two different instruments.  S14 modelled the error and reported point
counts and dB figures from that model.  This tool is the model made
runnable and checkable, so the point count that goes into the generator is
one this repo can re-derive rather than one it remembers.

THE FORM (PW, 2026-09-09: "the envelope and knee become part of the LUT
graph").  ONE table, level -> gain.  The whole static curve -- threshold,
ratio, knee, and for the LIMITER its ceiling -- is baked in by a DESIGN
step that runs only when a parameter changes.  Per sample the kernel does:
envelope -> index -> two adjacent words -> interpolate -> gain.  No log2,
no knee arithmetic, no exp2.

THE INDEX IS A LOGARITHM WITHOUT A LOGARITHM, and this file computes it
bit for bit the way the kernel does, because a table designed on a
different grid from the one the kernel indexes is worse than no table:

    z    = leftz(env)                       count of leading zeros
    oct  = (31 - OCT_LO) - z                the octave, biased
    man  = (env << z) & 0x7FFFFFFF          mantissa fraction, Q0.31
    idx  = (oct << K) + (man >> (31 - K))   clamped to [0, N-2]
    frac = (man << K) & 0xFFFFFFFF          the interpolation fraction
    gain = T[idx] + rns((T[idx+1] - T[idx]) * frac, 31)

So the grid is log-spaced by construction -- one octave per exponent step,
2^K points per octave -- and OCT_LO throws away the octaves below the
bottom of the audio range, where every curve is flat and a table would be
spending words on nothing.

THE ACCURACY BAR is PW's ruling of 2026-09-09: 0.1 dB worst case over 0 to
-100 dBFS, not the polynomial's 0.0001 dB.

Usage:
    python3 dyn_lut_design.py                 the ladder: K vs error
    python3 dyn_lut_design.py --sweep         the full parameter sweep
    python3 dyn_lut_design.py --emit comp --thr -20 --ratio 4 --knee 6
"""
import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixed_ref as FR

QS = 28                       # Q4.28, the envelope and the gain
UNITY = 1 << QS
FULL = 1 << QS                # 0 dBFS in Q4.28

# The bottom of the table.  -100 dBFS is 1e-5 of full scale, which in
# Q4.28 has its leading 1 at bit 11, so octave 11 is the lowest the bar
# asks about.  One octave of margin below it, and everything under that
# clamps to the table's floor entry -- which is correct, not approximate,
# because every one of these curves is exactly flat down there.
OCT_LO = 10


def leftz(v):
    """The core's leftz: leading zeros of a 32-bit word, 32 for zero."""
    if v <= 0:
        return 32
    return 32 - v.bit_length()


def index_of(env_q28, kbits, ntab):
    """Bit for bit what LUT_INDEX_SIMD computes.  Returns (idx, frac)."""
    z = leftz(env_q28)
    oct_ = (31 - OCT_LO) - z
    man = (env_q28 << z) & 0x7FFFFFFF if z < 32 else 0
    idx = (oct_ << kbits) + (man >> (31 - kbits))
    if idx < 0:
        idx = 0
    if idx > ntab - 2:
        idx = ntab - 2
    # THE FRACTION MUST NOT REACH BIT 31.  `man` is Q0.31, so shifting
    # it left by K to drop the K bits already spent on the sub-index
    # pushes what is left up into the sign bit, and the kernel's
    # interpolation multiply is SIGNED -- a fraction of 0.75 arrives as
    # -0.25.  S15 found this in the S14 rig, where it could not show:
    # the table's contents do not change the instruction stream, so a
    # cycle measurement is blind to it.  The mask is two instructions in
    # the kernel and it is the difference between 0.39 dB and 0.01 dB.
    frac = (man << kbits) & 0x7FFFFFFF
    return idx, frac


def grid_env(idx, kbits):
    """The envelope value, Q4.28, that lands exactly on table entry idx.

    THE TOP GUARD ENTRY IS CLAMPED, and the kernel clamps it the same
    way (S15-11). Index N-1 is the guard the interpolation reads as
    T[i+1] for the last real cell, and its grid point is octave
    OCT_HI+1 = 31, whose envelope is 1 << 31 -- outside a signed 32-bit
    word. On the part that reads as NEGATIVE and _compgain_fx returns
    unity for it, so the top cell would interpolate back UP to unity
    above +17.8 dBFS. Q4.28's largest positive value is the right value
    there, in both places.
    """
    oct_ = (idx >> kbits) + OCT_LO
    sub = idx & ((1 << kbits) - 1)
    # leading 1 at bit oct_, then the top kbits of the mantissa = sub
    e = (((1 << kbits) + sub) << oct_) >> kbits
    return min(e, 0x7FFFFFFF)


def n_words(kbits, oct_hi=30):
    """Table length: the octaves OCT_LO..oct_hi at 2^K points each, plus
    the guard entry the interpolation's T[i+1] reads."""
    return ((oct_hi - OCT_LO + 1) << kbits) + 1


# ---------------------------------------------------------------------------
# The exact curves.  These are the repo's own fixed-point reference
# (tools/dsp/fixed_ref.py), NOT a float restatement of it, so the table is
# designed against the arithmetic that ships.
# ---------------------------------------------------------------------------
_K_DB = 20.0 * math.log10(2.0)          # dB per log2 unit


def db_to_log2q(db):
    return int(round(db / _K_DB * (1 << 25)))


def comp_params(thr_db, ratio, knee_db):
    thr = db_to_log2q(thr_db)
    slope = int(round((1.0 - 1.0 / ratio) * (1 << 31)))
    halfk = db_to_log2q(knee_db / 2.0)
    if knee_db > 0:
        k2 = int(round((1.0 - 1.0 / ratio) / (2.0 * knee_db / _K_DB)
                       * (1 << 25)))
    else:
        k2 = 0
    return thr, slope, halfk, k2


def curve_comp(env_q28, thr_db, ratio, knee_db):
    thr, slope, halfk, k2 = comp_params(thr_db, ratio, knee_db)
    if env_q28 <= 0:
        return UNITY
    return FR.comp_gain(env_q28, thr, slope, halfk, k2)


def curve_limiter(env_q28, thr_db):
    """The LIMITER is the compressor at an infinite ratio and a hard knee
    -- that is what its kernel computes, and it is why one table form
    serves both."""
    return curve_comp(env_q28, thr_db, 1e9, 0.0)


def curve_gate(env_q28, thr_db, range_db):
    """HERE FOR COMPLETENESS AND AS A WARNING, not as a shipping form.
    S14-3 measured this: the gate's static curve is a STEP -- unity above
    the threshold, `range` below -- and linear interpolation smears a
    discontinuity across a whole cell whatever the mesh.  The error this
    function reports is 52-60 dB at every point count, which is the
    measurement that says the gate's lever is the linear-domain threshold
    and not a table."""
    thr = db_to_log2q(thr_db)
    if env_q28 <= 0:
        lvl = -(1 << 31)
    else:
        lvl = FR.log2_q(env_q28)
    if lvl >= thr:
        return UNITY
    return FR.exp2_q(db_to_log2q(-abs(range_db)))


CURVES = {
    'comp': lambda e, p: curve_comp(e, p['thr'], p['ratio'], p['knee']),
    'limiter': lambda e, p: curve_limiter(e, p['thr']),
    'gate': lambda e, p: curve_gate(e, p['thr'], p['range']),
}


# ---------------------------------------------------------------------------
# The design step
# ---------------------------------------------------------------------------

def design(kind, params, kbits, oct_hi=30, minimax=True):
    """Build the table.  Straight sampling first, then ONE correction
    pass that is the whole reason a modest point count reaches the bar.

    WHY A CORRECTION PASS AT ALL.  Sampling puts the error entirely
    between the knots, and on these curves it is not spread evenly: the
    hard-knee corner and the threshold are KINKS, and a cell that
    straddles a kink carries all of the error while its neighbours carry
    almost none.  S14 proposed moving a knot onto the kink, which cannot
    be done on a grid the kernel indexes by shifting.  Nudging the two
    knots bounding a kinked cell costs nothing at run time and does the
    same job: the cell's worst error drops to about a quarter, because
    the interpolant is being fitted to the curve rather than pinned to
    it at the ends.

    The correction is bounded to the cells that actually carry error and
    is a strict improvement by construction -- a knot only moves if the
    move lowers the worst error of every cell it touches.
    """
    n = n_words(kbits, oct_hi)
    f = CURVES[kind]
    tab = [f(grid_env(i, kbits), params) for i in range(n)]
    if not minimax:
        return tab
    for _ in range(3):
        moved = False
        for i in range(n):
            cur = tab[i]
            base = max(_cell_err(tab, j, kbits, f, params)
                       for j in _cells_touching(i, n))
            best, bestv = base, cur
            step = max(1, abs(cur) >> 10)
            for d in (-step, step, -step // 2 or -1, step // 2 or 1):
                tab[i] = max(0, cur + d)
                e = max(_cell_err(tab, j, kbits, f, params)
                        for j in _cells_touching(i, n))
                if e < best - 1e-9:
                    best, bestv = e, tab[i]
            tab[i] = bestv
            if bestv != cur:
                moved = True
        if not moved:
            break
    return tab


def _cells_touching(i, n):
    out = []
    if i - 1 >= 0:
        out.append(i - 1)
    if i <= n - 2:
        out.append(i)
    return out or [0]


def _cell_err(tab, cell, kbits, f, params, pts=9):
    """Worst dB error inside one cell, sampled at its own grid."""
    lo = grid_env(cell, kbits)
    hi = grid_env(cell + 1, kbits)
    worst = 0.0
    for j in range(pts + 1):
        env = lo + (hi - lo) * j // pts
        if env <= 0:
            continue
        got = lookup(tab, env, kbits)
        want = f(env, params)
        worst = max(worst, _db_err(got, want))
    return worst


def lookup(tab, env_q28, kbits):
    """The kernel's own read: two adjacent words and a Q0.31 blend."""
    idx, frac = index_of(env_q28, kbits, len(tab))
    a, b = tab[idx], tab[idx + 1]
    return a + FR.rns((b - a) * frac, 31)


def _db_err(got, want):
    if want <= 0 and got <= 0:
        return 0.0
    if want <= 0 or got <= 0:
        return 999.0
    return abs(20.0 * math.log10(got / want))


def worst_error_db(tab, kind, params, kbits, lo_db=-100.0, hi_db=0.0,
                   pts=20000):
    """Worst error over the bar's range, on a dense LOG sweep -- dense
    enough that it is sampling inside every cell, which is where the
    error lives."""
    f = CURVES[kind]
    worst, at = 0.0, None
    for i in range(pts + 1):
        db = lo_db + (hi_db - lo_db) * i / pts
        env = int(round(FULL * (10.0 ** (db / 20.0))))
        if env <= 0:
            continue
        e = _db_err(lookup(tab, env, kbits), f(env, params))
        if e > worst:
            worst, at = e, db
    return worst, at


# ---------------------------------------------------------------------------
# The reports
# ---------------------------------------------------------------------------
SHIPPED = {
    'comp': {'thr': -20.0, 'ratio': 4.0, 'knee': 6.0},
    'limiter': {'thr': -0.5},
    'gate': {'thr': -40.0, 'range': 60.0},
}

# The documented parameter ranges, from the mx master and dsp.csv.
SWEEP_COMP = [{'thr': t, 'ratio': r, 'knee': k}
              for t in (-60.0, -40.0, -20.0, -10.0, -3.0)
              for r in (1.5, 2.0, 4.0, 10.0, 100.0)
              for k in (0.0, 6.0, 18.0)]
SWEEP_LIM = [{'thr': t} for t in (-30.0, -20.0, -10.0, -3.0, -0.5, 0.0)]


def ladder(args):
    print('THE LADDER — worst dB error over 0 to -100 dBFS, against the bar')
    print('of 0.1 dB (PW ruling 2026-09-09).  OCT_LO = %d, so the table '
          'covers' % OCT_LO)
    print('octaves %d..30 -- the whole positive range of a Q4.28 word --'
          % OCT_LO)
    print('and everything below clamps to the table\'s floor entry.')
    print()
    print('  %-9s %3s %6s %7s   %9s %9s' %
          ('curve', 'K', 'pts/oct', 'words', 'sampled', 'corrected'))
    print('  ' + '-' * 60)
    for kind in ('comp', 'limiter'):
        for k in (2, 3, 4, 5):
            p = SHIPPED[kind]
            t0 = design(kind, p, k, minimax=False)
            e0, _ = worst_error_db(t0, kind, p, k)
            t1 = design(kind, p, k, minimax=True)
            e1, _ = worst_error_db(t1, kind, p, k)
            print('  %-9s %3d %6d %7d   %8.4f %9.4f%s' %
                  (kind, k, 1 << k, n_words(k), e0, e1,
                   '   <= BAR' if e1 <= 0.1 else ''))
    print()
    print('  THE GATE IS NOT A TABLE PROBLEM (S14-3), and this is the')
    print('  measurement rather than the assertion:')
    for k in (2, 3, 4, 5, 6):
        p = SHIPPED['gate']
        t = design('gate', p, k, minimax=False)
        e, at = worst_error_db(t, 'gate', p, k)
        print('  %-9s %3d %6d %7d   %8.2f dB at %.1f dBFS' %
              ('gate', k, 1 << k, n_words(k), e, at or 0.0))
    print('  A step interpolates to a ramp at every mesh.  The gate\'s')
    print('  lever is DSP4_GATE_LINTHR, not a table.')


def sweep(args):
    print('THE FULL PARAMETER SWEEP at K = %d (%d words/node).'
          % (args.k, n_words(args.k)))
    print()
    # PER CLASS, because they ship behind different switches on different
    # chips: the COMPRESSOR's table went into chip 1 at S15 and the
    # LIMITER's into chip 2 at S16, and "the worst over 81 sets" hid the
    # limiter's own number behind a compressor set that is worse. Each
    # class has to clear the bar on its own.
    #
    # The LIMITER sweep spans its CONTRACT range and both endpoints:
    # `Aux001LimiterThr001` is `0=-30/127=0/[Lin]`.
    best = {}
    for kind, sets in (('comp', SWEEP_COMP), ('limiter', SWEEP_LIM)):
        w, wp = 0.0, None
        for p in sets:
            t = design(kind, p, args.k)
            e, at = worst_error_db(t, kind, p, args.k, pts=4000)
            if e > w:
                w, wp = e, (dict(p), at)
        best[kind] = (w, wp, len(sets))
        print('  %-8s worst over %2d sets: %.4f dB  (%s at %.1f dBFS)  %s'
              % (kind, len(sets), w, wp[0], wp[1] or 0.0,
                 'PASS' if w <= 0.1 else 'FAIL'))
    worst = max(v[0] for v in best.values())
    kind = max(best, key=lambda k: best[k][0])
    n = sum(v[2] for v in best.values())
    print()
    print('  worst over %d parameter sets: %.4f dB  (%s %s at %.1f dBFS)'
          % (n, worst, kind, best[kind][1][0], best[kind][1][1] or 0.0))
    print('  the bar is 0.1 dB: %s' % ('PASS' if worst <= 0.1 else 'FAIL'))


def emit_raw(args):
    """Design from the RAW converted parameters, exactly the four words
    the node's block-rate conversion wrote into _comp_cgp_.

    WHY THIS MODE EXISTS. The node converts its curve from the float
    parameters in dsp.csv with its own arithmetic; this tool converts
    from dB with Python's. Those two can differ in the last bit, and a
    one-bit difference in the threshold moves every word in the table.
    Comparing the part's table against a model built from the part's own
    key removes that question entirely, and leaves only the one being
    asked: does the DESIGN STEP agree with the model about the GRID and
    the curve?
    """
    thr, slope, halfk, k2 = [int(x, 0) for x in args.raw.split(',')]
    thr = thr - (1 << 32) if thr >= (1 << 31) else thr
    slope = slope - (1 << 32) if slope >= (1 << 31) else slope
    halfk = halfk - (1 << 32) if halfk >= (1 << 31) else halfk
    k2 = k2 - (1 << 32) if k2 >= (1 << 31) else k2
    n = n_words(args.k)
    for i in range(n):
        e = grid_env(i, args.k)
        g = UNITY if e <= 0 else FR.comp_gain(e, thr, slope, halfk, k2)
        print('%08X' % (g & 0xFFFFFFFF))


def emit_words(args):
    """The table as bare hex words, one per line -- what
    tools/pi/dsp4_dyn_lut_check.py diffs against what the part designed."""
    p = dict(SHIPPED[args.emit])
    if args.thr is not None:
        p['thr'] = args.thr
    if args.ratio is not None:
        p['ratio'] = args.ratio
    if args.knee is not None:
        p['knee'] = args.knee
    # NO minimax pass: the on-part design step samples the curve, and a
    # model that post-processed the samples would not be modelling it.
    for w in design(args.emit, p, args.k, minimax=False):
        print('%08X' % (w & 0xFFFFFFFF))


def emit(args):
    p = dict(SHIPPED[args.emit])
    if args.thr is not None:
        p['thr'] = args.thr
    if args.ratio is not None:
        p['ratio'] = args.ratio
    if args.knee is not None:
        p['knee'] = args.knee
    t = design(args.emit, p, args.k)
    e, at = worst_error_db(t, args.emit, p, args.k)
    print('/* %s %s  K=%d  %d words  worst %.4f dB at %.1f dBFS */'
          % (args.emit, p, args.k, len(t), e, at or 0.0))
    for i in range(0, len(t), 8):
        print('    ' + ' '.join('0x%08X,' % (w & 0xFFFFFFFF)
                                for w in t[i:i + 8]))


def blend_error(args):
    """THE RAMPING BLEND'S OWN ERROR.  A ramping parameter is served by
    blending two tables rather than rebuilding one per block (the design
    step is ~211 instructions per point, 3-6 % of a whole block for one
    node).  The blend is linear between two DESIGNED tables, so its error
    is not the table error: it is the error of a straight line between
    two curves against the curve at the intermediate parameter.  That is
    a real deviation and it is reported here rather than assumed small.
    """
    print('THE RAMPING BLEND, K = %d.  Blending table(thr=A) to' % args.k)
    print('table(thr=B) over a ramp, against the exact curve at each')
    print('intermediate threshold.')
    print()
    print('  %-24s %9s %9s' % ('ramp', 'table only', 'with blend'))
    print('  ' + '-' * 46)
    for a_db, b_db in ((-20.0, -10.0), (-40.0, -20.0), (-10.0, -3.0),
                       (-60.0, -3.0)):
        pa = {'thr': a_db, 'ratio': 4.0, 'knee': 6.0}
        pb = {'thr': b_db, 'ratio': 4.0, 'knee': 6.0}
        ta = design('comp', pa, args.k)
        tb = design('comp', pb, args.k)
        worst_t, worst_b = 0.0, 0.0
        for step in range(1, 8):
            mu = step / 8.0
            pm = {'thr': a_db + (b_db - a_db) * mu, 'ratio': 4.0, 'knee': 6.0}
            tm = design('comp', pm, args.k)
            for i in range(0, 20001, 20):
                db = -100.0 + 100.0 * i / 20000.0
                env = int(round(FULL * (10.0 ** (db / 20.0))))
                if env <= 0:
                    continue
                want = curve_comp(env, pm['thr'], 4.0, 6.0)
                got_t = lookup(tm, env, args.k)
                ga = lookup(ta, env, args.k)
                gb = lookup(tb, env, args.k)
                got_b = ga + FR.rns(int((gb - ga) * (1 << 28) * mu) >> 28, 0) \
                    if False else int(round(ga + (gb - ga) * mu))
                worst_t = max(worst_t, _db_err(got_t, want))
                worst_b = max(worst_b, _db_err(got_b, want))
        print('  thr %6.1f -> %6.1f dB %9.4f %9.4f' %
              (a_db, b_db, worst_t, worst_b))
    print()
    print('  The blend is an APPROXIMATION OF THE RAMP, not of the curve:')
    print('  it is exact at both ends and deviates in between, and the')
    print('  deviation above is the price of not rebuilding per block.')


def selftest():
    """The checks that would have caught S15-4 before the part ran.

    Three properties, and each of them is a way the index arithmetic can
    be wrong that the CYCLE rig cannot see:

      1. ROUND TRIP. index_of(grid_env(i)) must be (i, 0) for every i --
         a grid point lands exactly on its own knot with a zero
         fraction. This catches an octave bias or a shift by the wrong
         amount.
      2. THE FRACTION IS A FRACTION. For every index and every sample
         inside its cell, 0 <= frac < 2^31. S15-4 is exactly the failure
         of this one: the fraction reached bit 31 and the kernel's
         signed multiply read it as negative.
      3. MONOTONE AND EXACT AT THE KNOTS. A table built by sampling
         returns the sampled value at every knot, and the interpolated
         value between two knots lies between them.
    """
    bad = 0
    n = n_words(4)
    for i in range(n):
        e = grid_env(i, 4)
        idx, frac = index_of(e, 4, n)
        if idx != min(i, n - 2) or (frac != 0 and i < n - 1):
            print('  ROUND TRIP FAILED at %d: env 0x%X -> (%d, %d)'
                  % (i, e, idx, frac))
            bad += 1
    for i in range(0, n - 1, 7):
        lo, hi = grid_env(i, 4), grid_env(i + 1, 4)
        for j in range(1, 8):
            e = lo + (hi - lo) * j // 8
            idx, frac = index_of(e, 4, n)
            if not (0 <= frac < (1 << 31)):
                print('  FRACTION OUT OF RANGE at env 0x%X: %d' % (e, frac))
                bad += 1
            if idx != i:
                print('  CELL FAILED: env 0x%X in cell %d landed in %d'
                      % (e, i, idx))
                bad += 1
    p = SHIPPED['comp']
    t = design('comp', p, 4, minimax=False)
    for i in range(0, n - 1, 11):
        if lookup(t, grid_env(i, 4), 4) != t[i]:
            print('  NOT EXACT AT KNOT %d' % i)
            bad += 1
        lo, hi = grid_env(i, 4), grid_env(i + 1, 4)
        mid = lookup(t, (lo + hi) // 2, 4)
        if not (min(t[i], t[i + 1]) <= mid <= max(t[i], t[i + 1])):
            print('  INTERPOLATION LEFT ITS CELL at %d: %d not in [%d, %d]'
                  % (i, mid, t[i], t[i + 1]))
            bad += 1
    print('dyn_lut_design selftest: %s' % ('PASS' if not bad else
                                           'FAIL (%d)' % bad))
    return 0 if not bad else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--sweep', action='store_true')
    ap.add_argument('--blend', action='store_true')
    ap.add_argument('--emit', choices=('comp', 'limiter', 'gate'))
    ap.add_argument('--raw', help='thr,slope,halfk,k2 as the node '
                                  'converted them; design from those')
    ap.add_argument('--words', action='store_true',
                    help='bare hex words for dsp4_dyn_lut_check.py')
    ap.add_argument('--k', type=int, default=4)
    ap.add_argument('--thr', type=float)
    ap.add_argument('--ratio', type=float)
    ap.add_argument('--knee', type=float)
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.raw:
        emit_raw(a)
    elif a.emit and a.words:
        emit_words(a)
    elif a.emit:
        emit(a)
    elif a.sweep:
        sweep(a)
    elif a.blend:
        blend_error(a)
    else:
        ladder(a)
    return 0


if __name__ == '__main__':
    sys.exit(main())
