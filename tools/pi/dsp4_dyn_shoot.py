#!/usr/bin/env python3
"""dsp4_dyn_shoot.py — the dynamics gain-computer shootout, off the part.

src/lib/dyn_shootout.asm times fourteen rungs of ONE loop nest -- 28 x 15,
bq_probe.asm's harness -- against the same envelope and the same gain
application, so what differs between them is the GAIN COMPUTER.

WHY. PW, 2026-09-09: dynamics is the hog, and "the compressor and gate
cycles could be improved a lot, using LUTs with interpolation, and still
fit the SIMD structure" -- with "the envelope and knee become part of the
LUT graph", against a ruling that the dynamics accuracy target is 0.1 dB
worst case over 0 to -100 dBFS rather than the polynomial's 0.0001 dB.

THE THREE CONTENDERS: today's 6-term polynomial log2/knee/exp2; a 3-term
one; and ONE level->gain table with the whole static curve baked in by a
design step, indexed by leftz + the top K mantissa bits so it is
log-spaced without computing a logarithm. The table's SIMD gather is
answered three ways rather than avoided -- PEYEN down for the gather over
DM, the same over DM and PM in one instruction, and the whole computer
unpaired.

Every window is (ticks, tcount) at each end, DSH_REPS repeats, and the
MINIMUM is reported, for dsp4_call_cal's measured reason: the diag tick
ISR fires at 1 kHz and a repeat it landed in is longer by exactly its own
cost. Rung 0 is the nest and is SUBTRACTED, so what is reported is the
body.

THE CYCLES ARE HALF THE ANSWER. The table's contents do not change the
instruction stream, so this rig cannot see the error; the point count and
the interpolation order that hold 0.1 dB are a host-side question.

Usage:  python3 dsp4_dyn_shoot.py [--chip 1]
"""
import argparse
import sys

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SENTINEL = {}

# (label, instructions in the inner body, group)
# (label, group). Cycles are per SAMPLE for a PAIR of channels; the
# per-channel column is half of that, which is the unit the cycle budget
# and the class ladder are kept in.
RUNGS = [
    ('0  NULL       the loop nest',                     'base'),
    ('1  ENV        envelope + attack/release',         'part'),
    ('2  CG_POLY    gain computer TODAY, 6-term poly',  'gain'),
    ('3  CG_POLY3   the same, 3-term poly',             'gain'),
    ('4  CG_LUT_DM  level->gain LUT, gather over DM',   'gain'),
    ('5  CG_LUT_PM  the same, gather DM+PM one instr',  'gain'),
    ('6  CG_LUT_UNP the same, whole computer unpaired', 'gain'),
    ('7  LOG2_POLY  LOG2Q_SIMD alone (GATE pays this)', 'part'),
    ('8  RNS        MRF_RNS28_SIMD alone',              'part'),
    ('9  COMP_TODAY the whole COMP per-sample body',    'body'),
    ('10 COMP_LUT   the same, LUT gain computer',       'body'),
    ('11 GATE_TODAY the whole GATE per-sample body',    'body'),
    ('12 GATE_LIN   the same, LINEAR-domain threshold', 'body'),
    ('13 GATE_LUT   the same, level->gain LUT',         'body'),
]

# (label, rung_b, rung_a) -- b minus a, in cycles per sample-pair.
DELTAS = [
    ('LUT vs TODAY, gain computer',              2,  4),
    ('LUT vs 3-term polynomial',                 3,  4),
    ('DM+PM gather vs DM only',                  5,  4),
    ('unpaired vs paired-with-gather',           6,  4),
    ('COMP body: today - LUT',                   9, 10),
    ('GATE body: today - linear threshold',     11, 12),
    ('GATE body: today - LUT',                  11, 13),
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
    discipline and the same measured reason as dsp4_call_cal.vpeek."""
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

    done = vpeek(sc, sc.sym['_dsh_done'])
    if done != 1:
        print(f'PROBE NEVER RAN (_dsh_done = {done}) -- is this a '
              f'DSP4_BQ_PROBE image?')
        return 2
    SENTINEL.update(addr=sc.sym['_dsh_done'], want=1)

    magic = vpeek(sc, sc.sym['_dsh_magic'])
    if magic != 0xD5B4D003:
        print(f'BAD MAGIC 0x{magic:08X} -- wrong image or a dead link')
        return 2

    iters  = vpeek(sc, sc.sym['_dsh_iters'])
    reps   = vpeek(sc, sc.sym['_dsh_reps'])
    rungs  = vpeek(sc, sc.sym['_dsh_rungs'])
    stages = vpeek(sc, sc.sym['_dsh_stages'])
    inner  = vpeek(sc, sc.sym['_dsh_inner'])
    tper   = vpeek(sc, sc.sym['_dsh_tper'])
    blk    = vpeek(sc, sc.sym['_dsh_blk'])
    kbits  = vpeek(sc, sc.sym['_dsh_kbits'])
    tbln   = vpeek(sc, sc.sym['_dsh_tbln'])

    # Every rung runs the same total number of inner iterations per call:
    # PRB_STAGES x PRB_INNER. Rung 20 splits them 7 x 60 instead of 28 x 15,
    # deliberately, and the product is the same.
    per_call = stages * inner

    base = sc.sym['_dsh_tick']
    raw = [[0] * reps for _ in range(rungs)]
    for p in range(reps):
        for r in range(rungs):
            o = base + ((p * rungs) + r) * 4
            ts, cs = vpeek(sc, o + 0), vpeek(sc, o + 1)
            te, ce = vpeek(sc, o + 2), vpeek(sc, o + 3)
            raw[r][p] = (te - ts) * tper + (cs - ce)

    print(f'  {iters} calls x {reps} repeats, TPERIOD {tper}, BLOCK {blk}, '
          f'{stages} stages x {inner} inner = {per_call} samples/call')
    print(f'  table: K = {kbits} mantissa bits = {1 << kbits} points per '
          f'octave, {tbln} words')
    print()
    null = min(raw[0]) / iters / per_call
    print(f'  {RUNGS[0][0]:44s} {null:9.2f} c/sample-pair  (subtracted)')
    print()
    print(f'  {"rung":44s} {"c/s-pair":>9s} {"c/s/chan":>9s} {"spread":>7s}')
    print('  ' + '-' * 76)
    c = [0.0] * len(RUNGS)
    for r in range(min(rungs, len(RUNGS))):
        name, grp = RUNGS[r]
        c[r] = min(raw[r]) / iters / per_call - null
        spread = (max(raw[r]) - min(raw[r])) / iters / per_call
        if r == 0:
            continue
        print(f'  {name:44s} {c[r]:9.1f} {c[r] / 2:9.1f} {spread:7.2f}')
    print('  ' + '-' * 76)
    print()
    print('  THE DELTAS')
    for label, b, x in DELTAS:
        if b >= len(c) or x >= len(c):
            continue
        d = c[b] - c[x]
        pct = (100.0 * d / c[b]) if c[b] else 0.0
        print(f'  {label:44s} {d:9.1f} c/sample-pair  ({pct:5.1f} %)')
    print()
    print('  THE CYCLES ARE HALF THE ANSWER: the table contents do not change')
    print('  the instruction stream, so this rig cannot see the error. The')
    print('  point count and interpolation order that hold the 0.1 dB bar are')
    print('  a host-side question.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
