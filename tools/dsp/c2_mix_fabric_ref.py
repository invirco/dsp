#!/usr/bin/env python3
"""c2_mix_fabric_ref.py — the bar for S149 lever L1 (DSP4_C2_MIX_FABRIC).

WHAT THIS EXISTS TO PROVE, and why a comment would not have done. Lever L1
takes chip 2's mix buses off the generic block wrapper and onto a shared
live-crosspoint pass (src/chip2/mix_fabric.asm). The claim attached to it —
PW approved it on that basis — is that the change is EXACT: the same audio,
bit for bit, not "close enough to a rounding". Two things could break that
and neither is obvious by eye:

  * the fabric SKIPS a crosspoint whose coefficient is zero, so the sum is
    taken over a different list of terms;
  * the fabric INLINES `_mrf_rns28` with its early `rts` turned into a
    conditional move, because a shared routine's return cannot live inside
    a hardware loop.

So both paths are transliterated here from the emitted assembly —
register by register, 80-bit MRF and all — and fuzzed against each other
and against fixed_ref.mix_sum, which is the normative definition
(shared/numeric-spec.md). `busgold.sh` is chip 1's equivalent and runs on
the part; this is the desk-side one, and it is what S149 had instead of a
bench.

    python3 tools/dsp/c2_mix_fabric_ref.py          # 0 = every vector agrees
    python3 tools/dsp/c2_mix_fabric_ref.py -n 50000

THE NEGATIVE CONTROL IS RUN TOO. `--negctl` skips crosspoints whose
coefficient is merely SMALL rather than zero, which is the plausible-looking
mistake this lever could have shipped, and the fuzz must FAIL on it — a
proof that cannot fail is not a proof.
"""
import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixed_ref                                                # noqa: E402

M80 = 1 << 80
M32 = 0xFFFFFFFF


def s80(v):
    """The MRF as the hardware holds it: 80 bits, wrapping."""
    v &= M80 - 1
    return v - M80 if v >= (M80 >> 1) else v


def u32(v):
    return v & M32


def s32(v):
    v = u32(v)
    return v - (1 << 32) if v >= (1 << 31) else v


def lshift(r, n):
    """SHARC `lshift r by n` — LOGICAL, 32-bit, n<0 shifts right."""
    r = u32(r)
    return u32(r << n) if n >= 0 else (r >> -n)


def ashift(r, n):
    """SHARC `ashift r by n` — ARITHMETIC, 32-bit."""
    if n >= 0:
        return u32(u32(r) << n)
    return u32(s32(r) >> -n)


def mac(mrf, x, g):
    """`mrf = mrf + r0 * r4 (ssi)` — signed integer MAC into the MRF."""
    return s80(mrf + s32(x) * s32(g))


# ---------------------------------------------------------------------------
# The two readouts
# ---------------------------------------------------------------------------

def mrf_rns28(mrf):
    """src/lib/mac64_fx.asm `_mrf_rns28`, transliterated.

    This is what the GENERIC WRAPPER path calls once per sample, and it is
    the behaviour lever L1 has to reproduce.
    """
    mrf = s80(mrf + 0x08000000 * 1)
    r1 = u32(mrf)                       # mr0f
    r2 = u32(mrf >> 32)                 # mr1f
    r1 = lshift(r1, -28)
    r3 = lshift(r2, 4)
    r0 = u32(r1 | r3)
    if ashift(r2, -28) == ashift(r0, -31):
        return s32(r0)
    return s32(u32(0x7FFFFFFF ^ ashift(r2, -31)))


def mrf_rns28_inline(mrf):
    """chip2/mix_fabric.asm's `.cmf_smp` tail, transliterated.

    The same arithmetic with the early `rts` replaced by a conditional
    move — the saturated value is formed unconditionally and moved in on
    the compare — because the readout sits inside a hardware loop.
    """
    mrf = s80(mrf + 0x08000000 * 1)
    r1 = u32(mrf)
    r2 = u32(mrf >> 32)
    r1 = lshift(r1, -28)
    r3 = lshift(r2, 4)
    r0 = u32(r1 | r3)
    r6 = u32(0x7FFFFFFF ^ ashift(r2, -31))
    if ashift(r2, -28) != ashift(r0, -31):
        r0 = r6
    return s32(r0)


# ---------------------------------------------------------------------------
# The two block paths
# ---------------------------------------------------------------------------

def wrapper_block(src, gq):
    """The generic wrapper + `gen_mix_bus_fixed`'s per-sample body.

    src[k][s] is source k's sample s; gq[k] is its Q4.28 coefficient. Every
    DECLARED source is staged and MAC'd on every sample, whatever gq[k] is
    — which is the cost S148-1 priced and this lever removes.
    """
    out = []
    for s in range(len(src[0])):
        mrf = 0
        for k in range(len(src)):
            mrf = mac(mrf, src[k][s], gq[k])
        out.append(mrf_rns28(mrf))
    return out


def fabric_block(src, gq, dead_below=0):
    """`_c2_mix_fabric`, transliterated.

    `dead_below` is the NEGATIVE CONTROL: 0 is the shipping rule (drop a
    crosspoint only when its coefficient is exactly zero); anything larger
    is the mistake of treating "small" as "absent".
    """
    live = [k for k in range(len(src))
            if not (abs(s32(gq[k])) <= dead_below)]
    n = len(src[0])
    if not live:
        return [0] * n
    out = []
    for s in range(n):
        mrf = 0
        for k in live:
            mrf = mac(mrf, src[k][s], gq[k])
        out.append(mrf_rns28_inline(mrf))
    return out


# ---------------------------------------------------------------------------

Q = 1 << 28
BLOCK = 16


def _rand_word(rng):
    """A sample word, weighted toward the edges the readout branches on."""
    pick = rng.random()
    if pick < 0.15:
        return rng.choice([0, 1, -1, fixed_ref.I32_MAX, fixed_ref.I32_MIN,
                           Q, -Q, Q - 1, -(Q - 1), 1 << 27, -(1 << 27)])
    if pick < 0.35:
        return rng.randint(-(1 << 27), 1 << 27)
    return rng.randint(fixed_ref.I32_MIN, fixed_ref.I32_MAX)


def _rand_coeff(rng, zero_bias):
    if rng.random() < zero_bias:
        return 0
    pick = rng.random()
    if pick < 0.25:
        return Q                            # unity
    if pick < 0.4:
        return rng.choice([1, -1, -Q, Q // 2, 2 * Q])
    return rng.randint(-(1 << 30), 1 << 30)


# THE DOMAIN `_mrf_rns28` IS EXACT ON, stated rather than assumed.
#
# `_mrf_rns28` asks only test (a) — "bits 63..59 are the sign of y" — and
# deliberately not test (b), the 80-bit one `_acc64_rns28` carries, because
# its own comment says its callers MAC ONE Q4.28 x Q4.28 product and are
# "inside the 64-bit domain by construction". A chip-2 mix bus MACs up to 23
# of them, so it is NOT, and past |acc| = 2**63 -- a bus sum past +/-128.0,
# which needs seventeen simultaneously-clipping sources at unity -- the
# readout wraps where fixed_ref.mix_sum saturates.
#
# That is the CHIP-2 MIX BUS's behaviour today and lever L1 reproduces it
# bit for bit, which is what a bit-exact lever is required to do. It is
# recorded as a finding (S149-1) rather than fixed here, because fixing it
# is an audio change and this lever is not. So the normative comparison is
# run on the domain the current image is exact on, and the vectors outside
# it are COUNTED and still required to agree wrapper-vs-fabric.
ACC64 = 1 << 63


def fuzz(n_vec, seed=20260929, dead_below=0, quiet=False):
    rng = random.Random(seed)
    bad = 0
    checked = 0
    norm_checked = 0
    out_of_domain = 0
    for _ in range(n_vec):
        n_src = rng.randint(1, 23)
        zero_bias = rng.choice([0.0, 0.3, 0.7, 0.95])
        gq = [_rand_coeff(rng, zero_bias) for _ in range(n_src)]
        src = [[_rand_word(rng) for _ in range(BLOCK)] for _ in range(n_src)]
        a = wrapper_block(src, gq)
        b = fabric_block(src, gq, dead_below=dead_below)
        checked += BLOCK
        if a != b:
            bad += 1
            if bad <= 3 and not quiet:
                s = next(i for i in range(BLOCK) if a[i] != b[i])
                print(f'  MISMATCH n_src={n_src} sample={s} '
                      f'wrapper={a[s]} fabric={b[s]}')
                print(f'    gq  = {gq}')
                print(f'    src = {[c[s] for c in src]}')
        if dead_below:
            continue
        for s in range(BLOCK):
            acc = sum(s32(c[s]) * s32(g) for c, g in zip(src, gq))
            if abs(acc) >= ACC64:
                out_of_domain += 1
                continue
            norm_checked += 1
            if fixed_ref.mix_sum([c[s] for c in src], gq) != a[s]:
                bad += 1
                if not quiet:
                    print('  MISMATCH against fixed_ref.mix_sum INSIDE the '
                          '64-bit domain — the transliteration is wrong, '
                          'not the lever')
    return bad, checked, norm_checked, out_of_domain


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('-n', '--vectors', type=int, default=4000)
    ap.add_argument('--seed', type=int, default=20260929)
    ap.add_argument('--negctl', action='store_true',
                    help='run the negative control alone and expect it to '
                         'FAIL')
    args = ap.parse_args()

    if args.negctl:
        bad, checked, _, _ = fuzz(args.vectors, args.seed, dead_below=16,
                                  quiet=True)
        print(f'negative control (drop |coeff| <= 16): {bad} disagreeing '
              f'vectors over {checked} words')
        if bad == 0:
            print('NEGATIVE CONTROL DID NOT FIRE — the fuzz proves nothing')
            return 1
        print('OK: the fuzz does detect a wrong liveness rule')
        return 0

    bad, checked, norm, ood = fuzz(args.vectors, args.seed)
    print(f'c2 mix fabric: {args.vectors} vectors, {checked} block words')
    print(f'  wrapper path vs fabric path      : '
          f'{"OK" if bad == 0 else str(bad) + " DISAGREE"}')
    print(f'  wrapper vs fixed_ref.mix_sum     : {norm} words inside the '
          f'64-bit domain')
    print(f'  outside it (S149-1, pre-existing): {ood} words — '
          f'wrapper and fabric still agree on every one')
    if bad:
        return 1
    # The negative control, every run: a proof that cannot fail is not one.
    nbad, ncheck, _, _ = fuzz(max(200, args.vectors // 10), args.seed,
                              dead_below=16, quiet=True)
    print(f'  negative control (|coeff| <= 16) : '
          f'{"fires — OK" if nbad else "DID NOT FIRE"}')
    if not nbad:
        return 1
    print('OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
