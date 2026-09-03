#!/usr/bin/env python3
"""gen_bqg_vectors.py — vectors for the HEADROOM GUARD bar (bqguard.sh).

Two claims are made about the guard and neither has been shown on the
part:

  1. the SIZER agrees with its model -- lib/bq_headroom.asm computes the
     H that tools/dsp/bq_h_load.py computes, for the same quantised
     coefficients;
  2. the GUARD does what it is for -- with H applied the round-once
     cascade no longer inverts sign against the per-stage-saturating
     contract, and without it, it does.

This emits one table that supports both: for each named worst-case
cascade, the quantised offset coefficients (with the guard's header word
in front, zeroed, because the PART is supposed to fill it in), the
matched-sign drive that achieves |h|_1, the SIGN of the contract's
output sample by sample, the H the model picks, and the number of sign
inversions the model predicts UNGUARDED.

THE DRIVE IS MATCHED-SIGN AT 0 dBFS, over exactly the horizon the part
runs. sign(h[k]) reversed in time is the input that achieves |h|_1; a
square wave reaches only max|H|, which is the whole reason headroom
sized off an EQ curve is the wrong headroom. Computing it over the same
N the part uses keeps the bar self-consistent: whatever the model
predicts for that input, the part has to reproduce.

Usage:
    gen_bqg_vectors.py --out src/lib/bqg_vectors.h --json vectors.json
"""

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixed_ref as F
import bq_headroom_guard as G
import bq_h_load as L

UNITY = 1 << F.QB


def u32(v):
    return v & 0xFFFFFFFF


# The cascades the state-bound and guard work singled out, hottest first.
# Names are the ones bq_headroom_guard.CASES uses, so the two scripts
# cannot drift apart about what "the four-band case" means.
# One design that is NOT in bq_headroom_guard.CASES, and it is the one
# the whole prefix argument is about: two boosts and two cuts on the SAME
# frequency. The bands cancel at the OUTPUT -- unity gain, nothing clips
# -- while the partial cascade after the second stage is +33 dB. That is
# a wrap with no clipping anywhere near it, which is what makes it a
# clean before/after: any sign inversion it produces is an internal wrap
# fed back into the poles and cannot be confused with an overdriven
# output. Every other named case either clips at the output too (the
# four-band all-+15) or does not reach the ceiling at all.
EXTRA = {
    'EQ 4-band +15/+15/-15/-15 @1k Q1': [G.rbj_peak(1000, 1.0, 15.0),
                                         G.rbj_peak(1000, 1.0, 15.0),
                                         G.rbj_peak(1000, 1.0, -15.0),
                                         G.rbj_peak(1000, 1.0, -15.0)],
}

PICK = [
    'EQ 4-band +15/+15/-15/-15 @1k Q1',
    '4-band all +15 dB @1k Q1',
    '28-band GEQ all +6 dB',
    'HF shelf +12 dB Q5.01 @20',
    'LF shelf +15 dB Q3.16 @20',
    'peak +15 dB Q0.1 @5k',
    'FILT: HPF 20 + LPF 20k',
]


def contract_run(xs, cqs):
    """The per-stage-saturating contract, for reference only."""
    sts = [F.biquad_state() for _ in cqs]
    out = []
    for x in xs:
        y = x
        for cq, st in zip(cqs, sts):
            y = F.biquad(y, cq, st)
        out.append(y)
    return out


def float_run(xs, cqs):
    """float64 on the DE-QUANTISED coefficients: the sign that is RIGHT.

    THE REFERENCE IS NOT THE CONTRACT, and that is a correction. On a
    cascade whose partial gain is +33 dB the per-stage-saturating
    contract CLIPS internally -- it is bounded, but it is not correct --
    so scoring the guard against it penalises the guard for being more
    correct than the thing it is compared with. The first run of this
    generator did exactly that and reported the cancelling cascade as
    "19 inversions guarded and 19 unguarded", which reads as the guard
    doing nothing and is in fact the contract clipping. Against float the
    three arms separate the way the argument says they should: clipping
    preserves SIGN, wrapping inverts it.
    """
    sts = [[0.0] * 4 for _ in cqs]
    cfs = [G.dequant(c) for c in cqs]
    out = []
    for x in xs:
        y = x / UNITY
        for cf, st in zip(cfs, sts):
            y = F.biquad_f(y, cf, st)
        out.append(y)
    return out


def roundonce_run(xs, cqs, H):
    """The landed kernel, with the guard's entry/exit scaling when H > 0.

    Exactly bq_headroom_guard.cascade_roundonce with guard=(H > 0), which
    is what the kernels do: shift in, run, shift out and saturate ONCE.
    """
    out, _ = G.cascade_roundonce(xs, cqs, H, H > 0)
    return out


def hashsum(words):
    """bqe_verify.asm's reduction: h = rot(h,1) xor w, and a plain sum.

    The rotate is what makes it order-sensitive and the sum is what
    catches a rotate that is quietly a shift.
    """
    h = 0
    ssum = 0
    for w in words:
        w &= 0xFFFFFFFF
        h = (((h << 1) | (h >> 31)) & 0xFFFFFFFF) ^ w
        ssum = (ssum + w) & 0xFFFFFFFF
    return h, ssum


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--json', required=True)
    ap.add_argument('--nsamp', type=int, default=128)
    args = ap.parse_args()

    nsamp = args.nsamp
    cases = []
    maxst = 0
    all_gd, all_un = [], []
    for name in PICK:
        cqs = G.q(EXTRA[name] if name in EXTRA else G.CASES[name])
        maxst = max(maxst, len(cqs))
        drive = G.matched_sign_drive(cqs, nsamp)
        ref = float_run(drive, cqs)
        con = contract_run(drive, cqs)
        h_model, bound, n_run = L.size_h(cqs)
        h_off = G.headroom_bits(G.l1_partial(cqs, ncap=60000))
        # what the part must find: sign inversions against the contract
        unguarded = roundonce_run(drive, cqs, 0)
        guarded = roundonce_run(drive, cqs, h_model)
        n_un = sum(1 for a, b in zip(ref, unguarded) if (a < 0) != (b < 0))
        n_gd = sum(1 for a, b in zip(ref, guarded) if (a < 0) != (b < 0))
        n_co = sum(1 for a, b in zip(ref, con) if (a < 0) != (b < 0))
        all_gd += guarded
        all_un += unguarded
        cases.append(dict(name=name, stages=len(cqs), cq=cqs, drive=drive,
                          ref=ref, h_model=h_model, h_offline=h_off,
                          bound=bound, n_run=n_run, n_contract=n_co,
                          n_unguarded=n_un, n_guarded=n_gd))

    with open(args.out, 'w') as f:
        w = f.write
        w('/* bqg_vectors.h — GENERATED by tools/dsp/gen_bqg_vectors.py.\n'
          ' * The headroom guard\'s bar: quantised worst-case cascades, the\n'
          ' * matched-sign drive that achieves |h|_1, and the sign of the\n'
          ' * per-stage-saturating contract\'s output for each sample. Do\n'
          ' * not edit; regenerate. */\n')
        w(f'#define BQG_NCAS   {len(cases)}\n')
        w(f'#define BQG_NSAMP  {nsamp}\n')
        w(f'#define BQG_MAXST  {maxst}\n')
        w('.var _bqg_stg[BQG_NCAS] = '
          + ', '.join(str(c['stages']) for c in cases) + ';\n')
        w('.var _bqg_href[BQG_NCAS] = '
          + ', '.join(str(c['h_model']) for c in cases) + ';\n')
        # coefficients: header slot + MAXST*5 per cascade, zero-padded
        w('.var _bqg_cf[BQG_NCAS * (BQG_MAXST * 5 + 1)] =\n')
        rows = []
        for c in cases:
            flat = [0]
            for cq in c['cq']:
                flat += list(cq)
            flat += [0] * ((maxst - c['stages']) * 5)
            rows.append(', '.join(f'0x{u32(v):08X}' for v in flat))
        w(',\n'.join('    ' + r for r in rows) + ';\n')
        w('.var _bqg_drv[BQG_NCAS * BQG_NSAMP] =\n')
        rows = [', '.join(f'0x{u32(v):08X}' for v in c['drive'])
                for c in cases]
        w(',\n'.join('    ' + r for r in rows) + ';\n')
        # the contract's SIGN per sample, as a full word (0 or 0x80000000):
        # the part xors and tests, which is two instructions and no bit
        # addressing inside the sample loop.
        w('/* the FLOAT reference\'s sign per sample */\n')
        w('.var _bqg_sgn[BQG_NCAS * BQG_NSAMP] =\n')
        rows = [', '.join('0x80000000' if v < 0 else '0x00000000'
                          for v in c['ref']) for c in cases]
        w(',\n'.join('    ' + r for r in rows) + ';\n')

    hgd, sgd = hashsum(all_gd)
    hun, sun = hashsum(all_un)
    print(f'  guarded stream   hash 0x{hgd:08X} sum 0x{sgd:08X}')
    print(f'  unguarded stream hash 0x{hun:08X} sum 0x{sun:08X}')

    json.dump(dict(nsamp=nsamp, maxst=maxst,
                   hash_gd=hgd, sum_gd=sgd, hash_un=hun, sum_un=sun,
                   cases=[{k: v for k, v in c.items()
                           if k not in ('cq', 'drive', 'ref')}
                          for c in cases]),
              open(args.json, 'w'), indent=1)

    print(f'gen_bqg_vectors: {len(cases)} cascades, {nsamp} samples, '
          f'max {maxst} stages')
    for c in cases:
        print(f"  {c['name']:30s} stages {c['stages']:2d}  H model "
              f"{c['h_model']} (offline {c['h_offline']})  "
              f"sign inversions vs float: contract {c['n_contract']:3d}  "
              f"unguarded {c['n_unguarded']:4d}  guarded {c['n_guarded']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
