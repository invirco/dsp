#!/usr/bin/env python3
"""dsp4_bq_probe.py — the per-instruction cycle probe, read back off the part.

src/lib/bq_probe.asm runs 22 rungs of ONE loop nest -- 28 outer x 15 inner,
the pipelined biquad kernel's own trip counts -- whose inner body is the
only thing that differs between them. Rungs 0-3 are 2, 3, 5 and 8 nops;
rungs 4-8 build the shipping pipelined body up one instruction at a time;
rungs 9-17 take it apart; rungs 18-21 do the same for the old eight-
instruction loop and for the structure around both.

WHY IT EXISTS. S13 pipelined the loop 8 instructions to 5, bit-exact, and
got 5.5 % where the instruction count predicted 25 %. Something other than
instruction count sets the rate and the ADSP-2156x Hardware Reference does
not say what: it has no core chapter at all -- no pipeline depth, no
compute-result latency, no stall rule in 101,300 lines. The part is the
only document, so this reads it.

Every window is (ticks, tcount) at each end, PRB_REPS repeats, and the
MINIMUM is reported, for dsp4_call_cal's measured reason: the diag tick ISR
fires at 1 kHz and a repeat it landed in is longer by exactly its own cost.

WHAT TO READ. Not the absolute column -- the DELTAS. Adjacent rungs differ
by one instruction or by one property, and the loop nest, the subroutine
call, the register seeding and the pointer reset are identical in all 22,
so they cancel.

Usage:  python3 dsp4_bq_probe.py [--chip 1]
"""
import argparse
import sys

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SENTINEL = {}

# (label, instructions in the inner body, group)
RUNGS = [
    ('0  NOP2       loop nest, 2 nops',                    2, 'issue'),
    ('1  NOP3       loop nest, 3 nops',                    3, 'issue'),
    ('2  NOP5       loop nest, 5 nops',                    5, 'issue'),
    ('3  NOP8       loop nest, 8 nops',                    8, 'issue'),
    ('4  PIPE1      I1',                                   1, 'build'),
    ('5  PIPE2      I1-I2',                                2, 'build'),
    ('6  PIPE3      I1-I3',                                3, 'build'),
    ('7  PIPE4      I1-I4  (+DM store)',                   4, 'build'),
    ('8  PIPE5      I1-I5  THE SHIPPING BODY',             5, 'build'),
    ('9  FREE5      same 5 forms, deps broken',            5, 'apart'),
    ('10 FREE5_NM   same, memory moves deleted',           5, 'apart'),
    ('11 FREE5_PM   same, store to PM not DM',             5, 'apart'),
    ('12 MUL_DEP    4 dependent float multiplies',         4, 'apart'),
    ('13 MUL_IND    4 independent float multiplies',       4, 'apart'),
    ('14 ALU_DEP    4 dependent float ALU ops',            4, 'apart'),
    ('15 ALU_IND    4 independent float ALU ops',          4, 'apart'),
    ('16 MIX_DEP    4 alternating mul->ALU deps',          4, 'apart'),
    ('17 PIPE5_SC   THE SHIPPING BODY, PEYEN off',         5, 'apart'),
    ('18 OLD8       the old 8-instruction body',           8, 'old'),
    ('19 OLD8_FREE  the same 8 forms, deps broken',        8, 'old'),
    ('20 PIPE5_LONG the body in a 60-trip loop',           5, 'struct'),
    ('21 PIPE5_STG  the body + the real per-stage code',   5, 'struct'),
]

# The deltas that carry the finding, as (label, rung_b, rung_a, divisor,
# what the difference means). divisor is the number of inner iterations the
# difference is spread over unless stated.
DELTAS = [
    ('nop issue rate, per instruction',        3,  0, 6),
    ('I1 added to an empty loop',              4,  0, 1),
    ('I2 added',                               5,  4, 1),
    ('I3 added',                               6,  5, 1),
    ('I4 added (carries the DM store)',        7,  6, 1),
    ('I5 added (carries the DM load)',         8,  7, 1),
    ('DEPENDENCE COST of the shipping body',   8,  9, 1),
    ('the two memory moves',                   9, 10, 1),
    ('PM store instead of DM store',          11,  9, 1),
    ('multiply -> multiply latency, per edge',12, 13, 4),
    ('ALU -> ALU latency, per edge',          14, 15, 4),
    ('mul<->ALU latency, per edge',           16, 13, 4),
    ('the SIMD pair (PEYEN on vs off)',        8, 17, 1),
    ('DEPENDENCE COST of the old body',       18, 19, 1),
    ('old body vs new body',                  18,  8, 1),
    ('a 15-trip loop vs a 60-trip loop',       8, 20, 1),
    ('the real per-stage prologue+epilogue',  21,  8, 1),
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

    done = vpeek(sc, sc.sym['_prb_done'])
    if done != 1:
        print(f'PROBE NEVER RAN (_prb_done = {done}) -- is this a '
              f'DSP4_BQ_PROBE image?')
        return 2
    SENTINEL.update(addr=sc.sym['_prb_done'], want=1)

    magic = vpeek(sc, sc.sym['_prb_magic'])
    if magic != 0xD5B4C002:
        print(f'BAD MAGIC 0x{magic:08X} -- wrong image or a dead link')
        return 2

    iters  = vpeek(sc, sc.sym['_prb_iters'])
    reps   = vpeek(sc, sc.sym['_prb_reps'])
    rungs  = vpeek(sc, sc.sym['_prb_rungs'])
    stages = vpeek(sc, sc.sym['_prb_stages'])
    inner  = vpeek(sc, sc.sym['_prb_inner'])
    tper   = vpeek(sc, sc.sym['_prb_tper'])
    blk    = vpeek(sc, sc.sym['_prb_blk'])

    # Every rung runs the same total number of inner iterations per call:
    # PRB_STAGES x PRB_INNER. Rung 20 splits them 7 x 60 instead of 28 x 15,
    # deliberately, and the product is the same.
    per_call = stages * inner

    base = sc.sym['_prb_tick']
    raw = [[0] * reps for _ in range(rungs)]
    for p in range(reps):
        for r in range(rungs):
            o = base + ((p * rungs) + r) * 4
            ts, cs = vpeek(sc, o + 0), vpeek(sc, o + 1)
            te, ce = vpeek(sc, o + 2), vpeek(sc, o + 3)
            raw[r][p] = (te - ts) * tper + (cs - ce)

    print(f'  {iters} calls x {reps} repeats, TPERIOD {tper}, BLOCK {blk}, '
          f'{stages} stages x {inner} inner = {per_call} iterations/call')
    print()
    print(f'  {"rung":46s} {"instr":>5s} {"c/iter":>9s} {"c/instr":>8s} '
          f'{"spread":>7s}')
    print('  ' + '-' * 82)
    ci = []
    for r in range(min(rungs, len(RUNGS))):
        name, n, grp = RUNGS[r]
        c = min(raw[r]) / iters / per_call
        spread = (max(raw[r]) - min(raw[r])) / iters / per_call
        ci.append(c)
        print(f'  {name:46s} {n:5d} {c:9.3f} {c / n:8.3f} {spread:7.3f}')
    print('  ' + '-' * 82)
    print()
    print('  THE DELTAS -- this is the measurement; the column above is not.')
    print(f'  {"":52s} {"cycles":>9s}')
    for label, b, x, div in DELTAS:
        if b >= len(ci) or x >= len(ci):
            continue
        d = (ci[b] - ci[x]) / div
        print(f'  {label:52s} {d:9.3f}')
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
