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

RUNGS = [
    ('0 NULL       empty loop',              None, None),
    ('1 FX_SCALAR  _bq_fx_cascade_blk',         1, 'fixed'),
    ('2 FX_SIMD    _bq_fx_cascade_simd',        2, 'fixed'),
    ('3 FL_SCALAR  _bqf_cascade_blk',           1, 'float'),
    ('4 FL_SIMD    _bqf_cascade_simd',          2, 'float'),
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
    print(f'  {"rung":34s} {"c/call":>9s} {"c/band-sample":>14s} {"vs fixed SIMD":>14s}')
    print('  ' + '-' * 76)
    res = {}
    for r in range(1, rungs):
        name, ch, kind = RUNGS[r]
        per = min(raw[r]) / iters - null
        cbs = per / (stages * blk * ch)
        res[name.split()[1]] = (per, cbs)
        print(f'  {name:34s} {per:9.1f} {cbs:14.2f}', end='')
        print(f' {"":>14s}' if kind is None else f' {"":>14s}')
    print('  ' + '-' * 76)
    fx = res.get('FX_SIMD', (0, 0))[1]
    if fx:
        for k in ('FX_SCALAR', 'FX_SIMD', 'FL_SCALAR', 'FL_SIMD'):
            if k in res:
                print(f'  {k:12s} {res[k][1]:6.2f} c/band-sample'
                      f'   ratio vs FX_SIMD {fx / res[k][1]:5.2f}x')
    print()
    print('  NUMERIC PRICE OF THE FLOAT RUNGS (tools/dsp/bq_float_delta.py):')
    print('    ordinary EQ 0.0001 dB   28-band GEQ all +6  0.176 dB')
    print('    LF shelf +15 dB Q3.16   0.520 dB  = 11x the 0.046 dB bar')
    return 0


if __name__ == '__main__':
    sys.exit(main())
