#!/usr/bin/env python3
"""fit_log2exp2_poly.py — regenerate fixed_ref.py's LOG2_POLY/EXP2_POLY.

LOG2_POLY/EXP2_POLY (the degree-5 Chebyshev fits used by log2_q()/exp2_q())
are checked-in constants in fixed_ref.py, not computed at import time. Run
this script and paste its output back into fixed_ref.py if the fit degree,
range, or quantization (QC) ever changes.
"""

import math

import numpy as np

QC = 30  # poly coeff fraction bits (Q2.30) — must match fixed_ref.QC
I32_MAX = (1 << 31) - 1
I32_MIN = -(1 << 31)


def _sat32(v):
    return I32_MAX if v > I32_MAX else (I32_MIN if v < I32_MIN else v)


def _fit_poly(fn, lo, hi, degree=5):
    k = np.arange(degree + 1)
    nodes = (lo + hi) / 2 + (hi - lo) / 2 * np.cos((2 * k + 1) * np.pi
                                                   / (2 * (degree + 1)))
    c = np.polyfit(nodes, [fn(t) for t in nodes], degree)
    return [_sat32(int(round(v * (1 << QC)))) for v in c]   # Q2.30, high->low


if __name__ == '__main__':
    log2_poly = _fit_poly(lambda t: math.log2(1.0 + t), 0.0, 1.0)
    exp2_poly = _fit_poly(lambda f: 2.0 ** f, 0.0, 1.0)
    print(f'LOG2_POLY = {log2_poly}')
    print(f'EXP2_POLY = {exp2_poly}')
