#!/usr/bin/env python3
"""bound_direct.py — is the DIRECT regrouping of the biquad cascade safe?

The cascade kernel (lib/biquad_fx.asm) issues TWELVE MACs per stage per
sample because the normative offset form is written out term by term:

    acc = efb + b0*x + b0*x2 - b0*x1 - b0*x1
              + nh*x1 + nh*x1 + n2*x2 - c1*y1 + c2*y2
              + y1*2^29 - y2*2^28

Collecting the terms by the variable they multiply is an EXACT INTEGER
identity on the stored coefficient words -- the 80-bit MAC accumulator is
exact, so regrouping cannot change the sum:

    g1h = nh - b0                (MACed twice, as nh is)
    g2  = n2 + b0
    g3  = 0x20000000 - c1
    g4  = c2 - 0x10000000
    acc = efb + b0*x + g1h*x1 + g1h*x1 + g2*x2 + g3*y1 + g4*y2

SIX MACs instead of twelve, with the offset form's whole benefit intact:
the derived words come from the STORED offset words, so the coefficient
QUANTISATION is untouched and only the arithmetic's grouping changes.

WHAT THIS SCRIPT CHECKS, because the identity is only exact while every
derived word fits a 32-bit register: g1h ~ b1*2^27, g2 ~ b2*2^28,
g3 ~ -a1*2^28, g4 ~ -a2*2^28, and none of the four is a coefficient the
existing range argument covers -- b1 and b2 are not stored anywhere. It
sweeps the same design space as bound_efb.py and reports the worst
magnitude of each derived word as a fraction of full scale, plus any set
where the derivation would wrap.

Usage: python3 bound_direct.py [--quick]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixed_ref as fr
from bound_efb import design_space

I32_MIN, I32_MAX = fr.I32_MIN, fr.I32_MAX


def derive(cq):
    """The four derived words, as the kernel's stage prologue computes
    them: plain 32-bit integer adds and subtracts on the stored words."""
    b0, nh, n2, c1, c2 = cq
    return (nh - b0, n2 + b0, 0x20000000 - c1, c2 - 0x10000000)


def check_identity(cq, x, st):
    """The regrouped accumulator must equal the normative one, exactly,
    for arbitrary state -- this is the identity itself, not a bound."""
    b0, nh, n2, c1, c2 = cq
    x1, x2, y1, y2, efb = st
    ref = (b0 * (x - 2 * x1 + x2) + nh * x1 + nh * x1 + n2 * x2
           - c1 * y1 + c2 * y2 + ((2 * y1 - y2) << fr.QB) + efb)
    g1h, g2, g3, g4 = derive(cq)
    new = (efb + b0 * x + g1h * x1 + g1h * x1 + g2 * x2 + g3 * y1 + g4 * y2)
    return ref == new


def main():
    quick = '--quick' in sys.argv
    names = ('g1h', 'g2', 'g3', 'g4')
    worst = [(0, None)] * 4
    wrapped = 0
    total = 0
    for cf, tag in design_space(*(61, 31, 21) if quick else (121, 61, 41)):
        cq = fr.biquad_coeffs_q(*cf)
        total += 1
        for i, v in enumerate(derive(cq)):
            if not (I32_MIN <= v <= I32_MAX):
                wrapped += 1
            if abs(v) > worst[i][0]:
                worst[i] = (abs(v), tag)

    print(f'coefficient sets swept: {total}')
    for name, (mag, tag) in zip(names, worst):
        print(f'  worst |{name}| = {mag} = {mag / float(1 << 31):.4f} '
              f'of int32 full scale   at {tag}')
    print(f'  sets where a derived word leaves int32: {wrapped}')

    # The identity, on adversarial state rather than on a design point:
    # full-scale history, worst coefficients, a full-scale error feedback.
    import random
    rnd = random.Random(4)
    bad = 0
    for _ in range(20000):
        cq = tuple(rnd.randrange(I32_MIN, I32_MAX) for _ in range(5))
        st = [rnd.randrange(I32_MIN, I32_MAX) for _ in range(4)]
        st.append(rnd.randrange(-(1 << 56), 1 << 56))
        if not check_identity(cq, rnd.randrange(I32_MIN, I32_MAX), st):
            bad += 1
    print(f'  regrouping identity, 20000 random coefficient/state sets: '
          f'{"OK" if bad == 0 else str(bad) + " MISMATCH"}')

    ok = wrapped == 0 and bad == 0
    print('VERDICT:', 'SAFE' if ok else 'NOT SAFE')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
