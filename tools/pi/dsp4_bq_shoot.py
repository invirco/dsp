#!/usr/bin/env python3
"""dsp4_bq_shoot.py — RIG A2 of the biquad shootout, read back off the part.

src/lib/bq_shootout.asm times four 28-stage cascade rungs inside the DSP:
today's FIXED cascade scalar and SIMD, and a FLOAT DF-II-T cascade scalar
and SIMD. Same loop form, same iteration count, same bank, same block
size, so the only difference between the fixed rungs and the float ones is
the arithmetic.

Every window is (ticks, tcount) at each end, three repeats, and the
MINIMUM is reported, for dsp4_call_cal's measured reason: the diag tick
ISR fires at 1 kHz and a repeat it landed in is longer by exactly its own
cost. Rung 0 is the empty loop and is SUBTRACTED, so what is reported is
the cascade and not the harness.

THE CYCLE NUMBER IS HALF THE ANSWER. The float rungs change the
arithmetic, and tools/dsp/bq_float_delta.py prices that at 0.0001 dB on
ordinary EQ and 0.52 dB on an LF shelf at +15 dB Q3.16 -- eleven times the
0.046 dB bar golden_harness holds the current contract to. Read the two
together or not at all.

Usage:  python3 dsp4_bq_shoot.py [--chip 1]
"""
import argparse
import sys

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SENTINEL = {}

# (label, channels, arm, unit)  unit 'bq' = per band-sample, 'g' = per sample
RUNGS = [
    ('0  NULL       empty loop',             None, None,   None),
    ('1  FX_SCALAR  _bq_fx_cascade_blk',        1, 'fixed', 'bq'),
    ('2  FX_SIMD    _bq_fx_cascade_simd',       2, 'fixed', 'bq'),
    ('3  FL_SCALAR  _bqf_cascade_blk',          1, 'float', 'bq'),
    ('4  FL_SIMD    _bqf_cascade_simd',         2, 'float', 'bq'),
    ('5  C_SCALAR   _bqc_cascade_blk  rnd',     1, 'rigc',  'bq'),
    ('6  C_SIMD     _bqc_cascade_simd rnd',     2, 'rigc',  'bq'),
    ('7  T_SCALAR   _bqt_cascade_blk  trunc',   1, 'rigc',  'bq'),
    ('8  T_SIMD     _bqt_cascade_simd trunc',   2, 'rigc',  'bq'),
    ('9  G_NOW      gain today   +meter',       1, 'gain',  'g'),
    ('10 G_R1       gain round1  +meter',       1, 'gain',  'g'),
    ('11 G_R1T      gain round1+D20 tap',       1, 'gain',  'g'),
    ('12 G_NOW_NM   gain today   -meter',       1, 'gain',  'g'),
    ('13 G_R1_NM    gain round1  -meter',       1, 'gain',  'g'),
    ('14 E_SCALAR   _bqe_cascade_blk  efb',     1, 'rigc',  'bq'),
    ('15 E_SIMD     _bqe_cascade_simd efb',     2, 'rigc',  'bq'),
    ('16 H_ENT      guard entry scale /stage',  2, 'rigc',  'bq'),
    ('17 H_EXI      guard exit+clamp  /stage',  2, 'rigc',  'bq'),
]


def _sentinel(sc):
    if not SENTINEL:
        return True
    seen = {}
    for _ in range(7):
        v = sc.peek(SENTINEL['addr'])
        seen[v] = seen.get(v, 0) + 1
        if seen[v] >= 2:
            return v == SENTINEL['want']
    return False


def vpeek(sc, addr, need=2, limit=7, rounds=3):
    """Voted peek; a zero has to prove the link is still alive. Same
    discipline and the same measured reason as dsp4_call_cal.vpeek: this
    link answers a dropped transaction with a well-formed stale word, and
    a timing word that read zero would come out as a null loop."""
    for _ in range(rounds):
        seen = {}
        for _ in range(limit):
            v = sc.peek(addr)
            seen[v] = seen.get(v, 0) + 1
            if seen[v] >= need:
                if v != 0:
                    return v
                if _sentinel(sc):
                    return 0
                break
        sc.d.resync()
    raise IOError('0x%X never returned a corroborated value in %d rounds of '
                  '%d reads: %r' % (addr, rounds, limit, seen))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chip', type=int, default=1)
    a = ap.parse_args()
    sc = S.Scope(a.chip)

    done = vpeek(sc, sc.sym['_bqsh_done'])
    if done != 1:
        print(f'LADDER NEVER RAN (_bqsh_done = {done}) -- is this a '
              f'DSP4_BQ_SHOOTOUT image?')
        return 2
    SENTINEL.update(addr=sc.sym['_bqsh_done'], want=1)

    magic = vpeek(sc, sc.sym['_bqsh_magic'])
    if magic != 0xD5B4B001:
        print(f'BAD MAGIC 0x{magic:08X} -- wrong image or a dead link')
        return 2

    iters  = vpeek(sc, sc.sym['_bqsh_iters'])
    reps   = vpeek(sc, sc.sym['_bqsh_reps'])
    rungs  = vpeek(sc, sc.sym['_bqsh_rungs'])
    stages = vpeek(sc, sc.sym['_bqsh_stages'])
    tper   = vpeek(sc, sc.sym['_bqsh_tper'])
    blk    = vpeek(sc, sc.sym['_bqsh_blk'])

    base = sc.sym['_bqsh_tick']
    raw = [[0] * reps for _ in range(rungs)]
    for p in range(reps):
        for r in range(rungs):
            o = base + ((p * rungs) + r) * 4
            ts, cs = vpeek(sc, o + 0), vpeek(sc, o + 1)
            te, ce = vpeek(sc, o + 2), vpeek(sc, o + 3)
            raw[r][p] = (te - ts) * tper + (cs - ce)

    print(f'  {iters} iterations x {reps} repeats, TPERIOD {tper}, '
          f'BLOCK {blk}, {stages} stages')
    null = min(raw[0]) / iters
    print(f'  {RUNGS[0][0]:34s} {null:9.2f} c/iter  (subtracted below)')
    print()
    print(f'  {"rung":34s} {"c/call":>9s} {"per unit":>10s}  unit')
    print('  ' + '-' * 76)
    res = {}
    for r in range(1, min(rungs, len(RUNGS))):
        name, ch, kind, unit = RUNGS[r]
        per = min(raw[r]) / iters - null
        div = (stages * blk * ch) if unit == 'bq' else blk
        cbs = per / div
        res[name.split()[1]] = (per, cbs)
        u = 'c/band-sample' if unit == 'bq' else 'c/sample/strip'
        print(f'  {name:34s} {per:9.1f} {cbs:10.2f}  {u}')
    print('  ' + '-' * 76)
    fx = res.get('FX_SIMD', (0, 0))[1]
    if fx:
        print('  CASCADE, paired, against today:')
        for k in ('FX_SCALAR', 'FX_SIMD', 'FL_SIMD', 'E_SIMD', 'C_SIMD',
                  'T_SIMD'):
            if k in res:
                print(f'    {k:12s} {res[k][1]:6.2f} c/band-sample'
                      f'   ratio vs FX_SIMD {fx / res[k][1]:5.2f}x')
    gn = res.get('G_NOW', (0, 0))[1]
    if gn:
        print('  GAIN, against today:')
        for k in ('G_NOW', 'G_R1', 'G_R1T', 'G_NOW_NM', 'G_R1_NM'):
            if k in res:
                print(f'    {k:12s} {res[k][1]:6.2f} c/sample/strip'
                      f'   ratio vs G_NOW {gn / res[k][1]:5.2f}x')
    print()
    print('  THE CYCLES ARE HALF THE ANSWER. The float rungs cost 0.52 dB on an')
    print('  LF shelf (tools/dsp/bq_float_delta.py); the RIG C rungs cost')
    print('  headroom bits and a recursive-state guard')
    print('  (tools/dsp/roundonce_noise.py, tools/dsp/bq_state_bound.py).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
