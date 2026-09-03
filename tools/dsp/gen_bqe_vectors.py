#!/usr/bin/env python3
"""gen_bqe_vectors.py — the coefficient/stimulus vector set the round-once
cascade kernel is diffed against fixed_ref on, and the reference results.

RIG C measured the round-once arm (`_bqe_cascade_simd`, per-stage SATURATE
deleted, error feedback KEPT) on ZEROED banks: sound for timing, and proof
of nothing about the arithmetic. Its bit-identity claim was measured on the
PYTHON model. This module is the other half -- it produces

  1. `src/lib/bqe_vectors.h`, a table of NCAS four-stage cascades drawn
     from the DEFS design space plus the named worst cases the state-bound
     work found, and a stimulus set at three drive levels; and
  2. the REFERENCE results for both arms, from fixed_ref itself: the
     contract arm (saturating) and the round-once arm (wrapping), as the
     two order-sensitive hashes and the running sums the part accumulates,
     plus the per-(cascade, level) divergence bitmap.

The part runs both kernels over the SAME words and diffs them on-chip; the
host compares the part's hashes against these. Two things are proved at
once: that the round-once kernel is the round-once MODEL, and that where
the model says nothing overflows the two kernels agree to the bit.

The divergence bitmap is the two-sided control. A bar that only asserted
"0 differences" would pass on a rig that never drove anything hard enough
to saturate; this one predicts WHICH cascades diverge at WHICH drive, and
the part has to diverge on exactly those and no others.

Usage:
    gen_bqe_vectors.py --block 8 --out src/lib/bqe_vectors.h \
                       --json /tmp/bqe_vectors.json
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixed_ref as fr

FS = 48000.0
QB = fr.QB
UNITY = 1 << QB          # 0 dBFS in Q4.28

# DEFS ranges (ghost_cells.c / bound_efb.py): EqFreq 20..20000 Log,
# EqGain -15..+15 Lin, EqQ 0.1..10 Log, Hpf 20..1000, Lpf 1000..20000.
F_LO, F_HI = 20.0, 20000.0
G_LO, G_HI = -15.0, 15.0
Q_LO, Q_HI = 0.1, 10.0


# ---------------------------------------------------------------------------
# RBJ designs -- the same derivation bound_efb.py and golden_harness.py use
# ---------------------------------------------------------------------------

def peaking(f0, g, q):
    a = 10 ** (g / 40.0)
    w0 = 2 * math.pi * f0 / FS
    al = math.sin(w0) / (2 * q)
    a0 = 1 + al / a
    return ((1 + al * a) / a0, (-2 * math.cos(w0)) / a0, (1 - al * a) / a0,
            (-2 * math.cos(w0)) / a0, (1 - al / a) / a0)


def shelf(f0, g, q, low=True):
    a = 10 ** (g / 40.0)
    w0 = 2 * math.pi * f0 / FS
    t = (a + 1 / a) * (1 / q - 1) + 2
    if t <= 0:
        return None
    al = math.sin(w0) / 2 * math.sqrt(t)
    c, s = math.cos(w0), 2 * math.sqrt(a) * al
    if low:
        b = (a * ((a + 1) - (a - 1) * c + s), 2 * a * ((a - 1) - (a + 1) * c),
             a * ((a + 1) - (a - 1) * c - s))
        d = ((a + 1) + (a - 1) * c + s, -2 * ((a - 1) + (a + 1) * c),
             (a + 1) + (a - 1) * c - s)
    else:
        b = (a * ((a + 1) + (a - 1) * c + s), -2 * a * ((a - 1) + (a + 1) * c),
             a * ((a + 1) + (a - 1) * c - s))
        d = ((a + 1) - (a - 1) * c + s, 2 * ((a - 1) - (a + 1) * c),
             (a + 1) - (a - 1) * c - s)
    return (b[0] / d[0], b[1] / d[0], b[2] / d[0], d[1] / d[0], d[2] / d[0])


def hplp(f0, q, hp):
    w0 = 2 * math.pi * f0 / FS
    al = math.sin(w0) / (2 * q)
    c = math.cos(w0)
    b = ((1 + c) / 2, -(1 + c), (1 + c) / 2) if hp else \
        ((1 - c) / 2, (1 - c), (1 - c) / 2)
    a0 = 1 + al
    return (b[0] / a0, b[1] / a0, b[2] / a0, -2 * c / a0, (1 - al) / a0)


UNITY_STAGE = (1.0, 0.0, 0.0, 0.0, 0.0)


def design(fam, f0, g, q):
    if fam == 'unity':
        return UNITY_STAGE
    if fam == 'peak':
        return peaking(f0, g, q)
    if fam == 'lshelf':
        return shelf(f0, g, q, True)
    if fam == 'hshelf':
        return shelf(f0, g, q, False)
    if fam == 'hp':
        return hplp(f0, q, True)
    if fam == 'lp':
        return hplp(f0, q, False)
    raise SystemExit(f'gen_bqe_vectors: unknown family {fam!r}')


# ---------------------------------------------------------------------------
# The cascade set
# ---------------------------------------------------------------------------

# The named cascades: the sets the state-bound work (bq_state_bound.py) and
# the RIG C write-up singled out, so the bar carries the worst cases by name
# and not only by whatever a sampler happened to land on.
NAMED = [
    ('bypass x4',
     [('unity', 0, 0, 0)] * 4),
    ('FILT: HPF 20 Q.707 x2 + LPF 20k Q.707 x2',
     [('hp', 20.0, 0, 0.707), ('hp', 20.0, 0, 0.707),
      ('lp', 20000.0, 0, 0.707), ('lp', 20000.0, 0, 0.707)]),
    ('LF shelf +15 Q3.16 @20 (the D5 axis) + bypass x3',
     [('lshelf', 20.0, 15.0, 3.16)] + [('unity', 0, 0, 0)] * 3),
    ('worst single stage: HF shelf +12 Q5.01 @20 + bypass x3',
     [('hshelf', 20.0, 12.0, 5.01)] + [('unity', 0, 0, 0)] * 3),
    ('worst peaking: +15 Q0.1 @5k + bypass x3',
     [('peak', 5000.0, 15.0, 0.1)] + [('unity', 0, 0, 0)] * 3),
    ('peak +15 Q10 @20 + bypass x3',
     [('peak', 20.0, 15.0, 10.0)] + [('unity', 0, 0, 0)] * 3),
    ('EQ 4 bands all +15 dB @1k Q1 (the coherent case)',
     [('peak', 1000.0, 15.0, 1.0)] * 4),
    ('EQ 4 bands all +15 dB @100 Q0.7 (coherent, LF)',
     [('peak', 100.0, 15.0, 0.7)] * 4),
    ('EQ 4 bands all -15 dB @1k Q1',
     [('peak', 1000.0, -15.0, 1.0)] * 4),
    ('GEQ-ish: +6 dB @100/300/1k/3k Q4',
     [('peak', 100.0, 6.0, 4.0), ('peak', 300.0, 6.0, 4.0),
      ('peak', 1000.0, 6.0, 4.0), ('peak', 3000.0, 6.0, 4.0)]),
    ('mixed EQ: LF shelf +9, peak +12 Q3, peak -9 Q0.5, HF shelf +9',
     [('lshelf', 80.0, 9.0, 0.9), ('peak', 900.0, 12.0, 3.0),
      ('peak', 4000.0, -9.0, 0.5), ('hshelf', 9000.0, 9.0, 0.9)]),
    ('HF shelf +12 Q5.01 @20 x2 + bypass x2 (cascaded worst)',
     [('hshelf', 20.0, 12.0, 5.01)] * 2 + [('unity', 0, 0, 0)] * 2),
]

SAMPLED_FAMS = ['peak', 'lshelf', 'hshelf', 'peak', 'hp', 'lp']


def _lcg(seed):
    s = seed & 0xFFFFFFFF
    while True:
        s = (1664525 * s + 1013904223) & 0xFFFFFFFF
        yield s


def sampled_stage(rng, k):
    """One design-space point, stratified in f0/gain/Q and then jittered.

    Stratified rather than uniform-random so the corners of the DEFS box --
    which is where |h|_1 lives -- are reached in a set this size, and
    deterministic so the header and the reference are the same vectors.
    """
    fam = SAMPLED_FAMS[k % len(SAMPLED_FAMS)]
    u = (next(rng) / 2.0 ** 32)
    v = (next(rng) / 2.0 ** 32)
    w = (next(rng) / 2.0 ** 32)
    nf, ng, nq = 17, 13, 11
    fi, gi, qi = (k // 1) % nf, (k // nf) % ng, (k // (nf * ng)) % nq
    tf = (fi + u) / nf
    tg = (gi + v) / ng
    tq = (qi + w) / nq
    if fam == 'hp':
        f0 = 20.0 * (1000.0 / 20.0) ** tf
    elif fam == 'lp':
        f0 = 1000.0 * (20000.0 / 1000.0) ** tf
    else:
        f0 = F_LO * (F_HI / F_LO) ** tf
    g = G_LO + (G_HI - G_LO) * tg
    q = Q_LO * (Q_HI / Q_LO) ** tq
    return (fam, f0, g, q)


def build_cascades(ncas, nstage):
    """(labels, coefficient sets) for ncas cascades of nstage stages."""
    assert nstage == 4, 'the named cascades are written for four stages'
    rng = _lcg(0xB19AD5)
    out, labels = [], []
    for name, spec in NAMED[:ncas]:
        stages = []
        for fam, f0, g, q in spec:
            cf = design(fam, f0, g, q)
            if cf is None:
                raise SystemExit(f'gen_bqe_vectors: named cascade {name!r} '
                                 f'has an undefined design {fam} '
                                 f'{f0} {g} {q} -- the RBJ shelf is not '
                                 f'realisable at that gain and Q')
            stages.append(fr.biquad_coeffs_q(*cf))
        out.append(stages)
        labels.append(name)
    k = 0
    while len(out) < ncas:
        stages, tags = [], []
        while len(stages) < nstage:
            fam, f0, g, q = sampled_stage(rng, k)
            k += 1
            cf = design(fam, f0, g, q)
            if cf is None:                 # shelf design undefined here
                continue
            stages.append(fr.biquad_coeffs_q(*cf))
            tags.append(f'{fam} {f0:.0f}Hz {g:+.1f}dB Q{q:.2f}')
        out.append(stages)
        labels.append(' | '.join(tags))
    return labels, out


# ---------------------------------------------------------------------------
# Stimulus
# ---------------------------------------------------------------------------

LEVELS = [
    ('-20 dBFS pseudo-random', 'rand', 0.1),
    ('-6 dBFS square, period 8', 'sq8', 0.5),
    ('0 dBFS square, period 8', 'sq8', 1.0),
]


def build_stim(block, nblk):
    """NLVL x (nblk*block) stimulus words, Q4.28.

    Deterministic, and generated identically here and nowhere else: the
    header and the reference read the same list.
    """
    n = block * nblk
    stim = []
    rng = _lcg(0x571303)
    for _, kind, amp in LEVELS:
        peak = int(round(amp * UNITY))
        row = []
        for i in range(n):
            if kind == 'rand':
                r = next(rng)
                v = ((r >> 8) & 0x1FFFF) - 0x10000        # +/- 2^16
                row.append(int(round(v * peak / 65536.0)))
            else:
                row.append(peak if (i // 4) % 2 == 0 else -peak)
        stim.append(row)
    return stim


# ---------------------------------------------------------------------------
# The reference: both arms, and the hashes the part accumulates
# ---------------------------------------------------------------------------

def _rns_wrap(acc):
    """The round-once extract: rns(acc, 28) taken as a 32-bit word.

    The kernel forms (acc + 2^27) >> 28 in the 80-bit MRF and keeps the
    LOW 32 BITS of it. Where the contract would have saturated, this wraps
    -- that is the whole of the deletion, and the whole of its risk.
    """
    return fr.wrap32(fr.rns(acc, QB))


def biquad_ro(x, coeffs, state):
    """fixed_ref.biquad with the per-stage saturate deleted, feedback kept."""
    b0, n1h, n2, c1, c2 = coeffs
    x1, x2, y1, y2, efb = state
    acc = (b0 * (x - 2 * x1 + x2) + n1h * x1 + n1h * x1 + n2 * x2
           - c1 * y1 + c2 * y2)
    acc += (2 * y1 - y2) << QB
    acc += efb
    y = _rns_wrap(acc)
    state[4] = acc - (y << QB)
    state[0], state[1] = x, x1
    state[2], state[3] = y, y1
    return y


def _hupd(h, w):
    w &= 0xFFFFFFFF
    h = ((h << 1) | (h >> 31)) & 0xFFFFFFFF
    return h ^ w


def reference(cascades, stim, block, nblk):
    """Run both arms over the vectors in the part's own order.

    Order is (pair, level, block, word) with the two channels of a pair
    INTERLEAVED -- cascade 2p in the even words, cascade 2p+1 in the odd
    ones -- because that is the layout the SIMD kernels consume and the
    order the part hashes in.
    """
    ncas = len(cascades)
    nlvl = len(stim)
    npair = ncas // 2
    ha = sa = hb = sb = 0
    ndiff = 0
    maxdiff = 0
    first = -1
    idx = 0
    bits = [0] * (ncas * nlvl)
    for p in range(npair):
        cs = (cascades[2 * p], cascades[2 * p + 1])
        for lv in range(nlvl):
            sta = [[fr.biquad_state() for _ in c] for c in cs]
            stb = [[fr.biquad_state() for _ in c] for c in cs]
            for kb in range(nblk):
                xs = stim[lv][kb * block:(kb + 1) * block]
                for i in range(block):
                    for ch in (0, 1):
                        ya = xs[i]
                        for s, st in zip(cs[ch], sta[ch]):
                            ya = fr.biquad(ya, s, st)
                        yb = xs[i]
                        for s, st in zip(cs[ch], stb[ch]):
                            yb = biquad_ro(yb, s, st)
                        ha, sa = _hupd(ha, ya), (sa + ya) & 0xFFFFFFFF
                        hb, sb = _hupd(hb, yb), (sb + yb) & 0xFFFFFFFF
                        # EXACTLY what the part computes: a 32-bit
                        # wrapping subtract, then `Rn = ABS Rx` with
                        # ALUSAT clear (so abs(I32_MIN) is I32_MIN), then
                        # a SIGNED compare against the running maximum.
                        # A true |difference| does not fit in 32 bits when
                        # one arm has wrapped, so the metric has to be
                        # defined by the instruction and not by the
                        # arithmetic -- taking abs() in Python instead
                        # scores a correct part as a mismatch, which is
                        # what it did on the first run of this bar.
                        d = fr.alu_abs(fr.wrap32(ya - yb))
                        if ya != yb:
                            ndiff += 1
                            if d > maxdiff:
                                maxdiff = d
                            if first < 0:
                                first = idx
                            bits[(2 * p + ch) * nlvl + lv] = 1
                        idx += 1
    bm = [0] * ((len(bits) + 31) // 32)
    for i, b in enumerate(bits):
        if b:
            bm[i >> 5] |= 1 << (i & 31)
    return dict(hash_a=ha, sum_a=sa, hash_b=hb, sum_b=sb,
                ndiff=ndiff, maxdiff=maxdiff & 0xFFFFFFFF, first=first,
                nwords=idx, bmap=bm, bits=bits)


# ---------------------------------------------------------------------------

def emit_header(path, cascades, stim, block, nblk, labels):
    ncas, nstage, nlvl = len(cascades), len(cascades[0]), len(stim)
    bmw = (ncas * nlvl + 31) // 32
    L = []
    L.append('/* bqe_vectors.h — GENERATED by tools/dsp/gen_bqe_vectors.py.')
    L.append(' * Do not edit; change the generator and re-run the bar.')
    L.append(f' * {ncas} cascades x {nstage} stages, {nlvl} drive levels,')
    L.append(f' * {nblk} consecutive blocks of {block} samples.')
    L.append(' */')
    L.append(f'#define BQEV_NCAS    {ncas}')
    L.append(f'#define BQEV_NSTAGE  {nstage}')
    L.append(f'#define BQEV_NLVL    {nlvl}')
    L.append(f'#define BQEV_NBLK    {nblk}')
    L.append(f'#define BQEV_BMWORDS {bmw}')
    L.append('')
    L.append('/* [b0, nh, n2, c1, c2] per stage, Q4.28 offset form. */')
    L.append('.global _bqev_ctab;')
    L.append(f'.var _bqev_ctab[{ncas * nstage * 5}] =')
    words = []
    for ci, c in enumerate(cascades):
        for s in c:
            words.append(tuple(s))
    for i, w in enumerate(words):
        end = ',' if i != len(words) - 1 else ';'
        L.append('    ' + ', '.join(f'0x{v & 0xFFFFFFFF:08X}' for v in w) + end)
    L.append('')
    L.append('.global _bqev_stim;')
    flat = [v for row in stim for v in row]
    L.append(f'.var _bqev_stim[{len(flat)}] =')
    for i in range(0, len(flat), 8):
        chunk = flat[i:i + 8]
        end = ',' if i + 8 < len(flat) else ';'
        L.append('    ' + ', '.join(f'0x{v & 0xFFFFFFFF:08X}'
                                    for v in chunk) + end)
    L.append('')
    with open(path, 'w') as f:
        f.write('\n'.join(L) + '\n')
    return dict(ncas=ncas, nstage=nstage, nlvl=nlvl, nblk=nblk,
                block=block, bmwords=bmw, labels=labels)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--block', type=int, default=8)
    ap.add_argument('--ncas', type=int, default=96)
    ap.add_argument('--nstage', type=int, default=4)
    ap.add_argument('--nblk', type=int, default=4)
    ap.add_argument('--out', required=True)
    ap.add_argument('--json', required=True)
    a = ap.parse_args()
    if a.ncas % 2:
        raise SystemExit('gen_bqe_vectors: --ncas must be even (SIMD pairs)')
    labels, cascades = build_cascades(a.ncas, a.nstage)
    stim = build_stim(a.block, a.nblk)
    meta = emit_header(a.out, cascades, stim, a.block, a.nblk, labels)
    ref = reference(cascades, stim, a.block, a.nblk)
    meta.update(ref)
    with open(a.json, 'w') as f:
        json.dump(meta, f)
    nfire = sum(ref['bits'])
    print(f'bqe vectors: {meta["ncas"]} cascades x {meta["nstage"]} stages, '
          f'{meta["nlvl"]} levels x {meta["nblk"]} blocks x {a.block} samples')
    print(f'  {ref["nwords"]} output words per arm')
    print(f'  model predicts {ref["ndiff"]} differing words '
          f'({100.0 * ref["ndiff"] / ref["nwords"]:.3f}%), '
          f'{nfire} of {meta["ncas"] * meta["nlvl"]} (cascade,level) cells '
          f'diverge')
    print(f'  contract hash 0x{ref["hash_a"]:08X} sum 0x{ref["sum_a"]:08X}')
    print(f'  round-once hash 0x{ref["hash_b"]:08X} sum 0x{ref["sum_b"]:08X}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
