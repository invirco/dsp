#!/usr/bin/env python3
"""dsp4_call_cal.py — what a call/rts pair costs on this part (D66).

Reads back the eight-rung ladder that src/lib/call_selftest.asm timed
inside the part and turns it into cycles per iteration, then into the
three numbers the review is waiting for:

  * is a hardware loop really one instruction per cycle?  (rung 0)
  * what does a bare call/rts pair cost with no body at all? (rung 1)
  * does a pair around a REAL body cost the same? (rungs 2-3, 4-5) —
    if it does, the ~17 c/s session 9 inferred is generic branch
    overhead and every floor row built by instruction counting is
    understated by the same rule; if it does not, the cost is specific
    to _mrf_rns28 and only TUBE's row moves.

CROSS-CHECK, and it is the point of rung 6: that rung is TUBE's
per-sample body instruction for instruction. Session 9 measured the same
body THROUGH THE GRAPH, by a same-boot TubeOn 0->1 diff, at 829-834
cycles per 8-sample block. If this instrument disagrees with that one,
neither number is usable and nothing here should be believed.

Every window is (ticks, tcount) at each end, three repeats, and the
MINIMUM is reported: the diag tick ISR fires at 1 kHz and a repeat it
landed in is longer by exactly its own cost.

Usage:  python3 dsp4_call_cal.py [--chip 1]
"""
import argparse
import sys

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SENTINEL = {}

RUNGS = [
    ('0 NULL        empty loop',                        2,  None),
    ('1 CALL_BARE   call -> rts',                        4,  None),
    ('2 CALL_NOP8   call -> nop x8; rts',               12,  None),
    ('3 INLINE_NOP8 nop x8 inline',                     10,  None),
    ('4 CALL_RNS    _mrf_rns28 called',                 17,  None),
    ('5 INLINE_RNS  _mrf_rns28 inlined',                16,  None),
    ('6 TUBE_CALL   TUBE per-sample body, 3 calls',     50,  None),
    ('7 TUBE_INLINE the same body, calls inlined',      47,  None),
    ('8 JUMP_UNCOND one unconditional taken jump',      10,  None),
    ('9 INLINE_FREE _mrf_rns28 inlined, branch-free',   19,  None),
    ('10 TUBE_FREE  TUBE body inlined, branch-free',    47,  None),
]
# The "naive" column is the one-cycle-per-instruction count of what the
# rung ISSUES on the non-saturating path, trailing loop nops included.
# It is exactly the arithmetic AXIS 1's floor rows are built from, which
# is why it is printed beside the measurement rather than left implicit.


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
    """Voted peek; a zero has to prove the link is still alive.

    Same discipline as dsp4_num_verify.vpeek and for the same measured
    reason: this link answers a dropped transaction with a well-formed
    stale word, and on 2026-08-30 a run of settled zeroes was scored as
    a numeric result. A timing word that reads zero would come out as a
    null loop of 0 cycles, which is why zero is CHECKED, not trusted."""
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
    sc.check_chip()

    done = vpeek(sc, sc.sym['_cst_done'])
    if done != 1:
        print(f'LADDER NEVER RAN (_cst_done = {done}) — is this a '
              f'DSP4_CALL_SELFTEST build, and did the main loop reach it?')
        return 3
    SENTINEL.update(addr=sc.sym['_cst_done'], want=1)

    magic = vpeek(sc, sc.sym['_cst_magic'])
    if magic != 0xD5B4C001:
        print(f'MAGIC MISMATCH: 0x{magic:08X} — stale symbol table or a '
              f'different image. Refusing to score it.')
        return 3

    iters = vpeek(sc, sc.sym['_cst_iters'])
    reps = vpeek(sc, sc.sym['_cst_reps'])
    rungs = vpeek(sc, sc.sym['_cst_rungs'])
    tper = vpeek(sc, sc.sym['_cst_tper'])
    blk = vpeek(sc, sc.sym['_cst_blk'])
    if rungs != len(RUNGS):
        print(f'RUNG COUNT MISMATCH: image says {rungs}, this scorer knows '
              f'{len(RUNGS)}. Refusing to mislabel a ladder.')
        return 3

    base = sc.sym['_cst_tick']
    raw = [[0] * reps for _ in range(rungs)]
    for p in range(reps):
        for r in range(rungs):
            o = base + ((p * rungs) + r) * 4
            ts, cs = vpeek(sc, o + 0), vpeek(sc, o + 1)
            te, ce = vpeek(sc, o + 2), vpeek(sc, o + 3)
            raw[r][p] = (te - ts) * tper + (cs - ce)

    print(f'--- CALL/RTS CALIBRATION LADDER (D66)')
    print(f'    {iters} iterations x {reps} repeats, TPERIOD {tper}, '
          f'BLOCK {blk}')
    print(f'    per-iteration cycles = min over repeats; naive = the '
          f'one-cycle-per-instruction count')
    print()
    print(f'    {"rung":46s} {"cyc/iter":>9s} {"naive":>6s} {"excess":>8s}'
          f'  {"spread":>7s}')
    cyc = []
    for r, (name, naive, _) in enumerate(RUNGS):
        vals = sorted(raw[r])
        lo = vals[0] / iters
        hi = vals[-1] / iters
        cyc.append(lo)
        spread = (hi - lo) / lo * 100 if lo else 0.0
        print(f'    {name:46s} {lo:9.3f} {naive:6d} {lo - naive:+8.3f}'
              f'  {spread:6.2f}%')

    print()
    print('--- WHAT THE LADDER SAYS')
    print(f'  hardware loop, 2 instructions      {cyc[0]:8.3f} cyc/iter '
          f'({cyc[0] / 2:.3f} per instruction)')
    print(f'  bare call/rts pair, no body        '
          f'{cyc[1] - cyc[0]:+8.3f} cyc  '
          f'(naive 2 -> excess {cyc[1] - cyc[0] - 2:+.3f})')
    print(f'  pair around an 8-nop body (near)   '
          f'{cyc[2] - cyc[3]:+8.3f} cyc  '
          f'(naive 2 -> excess {cyc[2] - cyc[3] - 2:+.3f})')
    print(f'  pair around _mrf_rns28 (far obj)   '
          f'{cyc[4] - cyc[5]:+8.3f} cyc  '
          f'(naive 1 -> the inline form ends `if eq jump` where the '
          f'callee ends `if eq rts`)')
    print(f'  _mrf_rns28 body itself, inlined    '
          f'{cyc[5] - cyc[0]:+8.3f} cyc over the null loop, naive '
          f'{RUNGS[5][1] - RUNGS[0][1]}')
    print()
    print('--- THE MECHANISM, NAMED')
    print(f'  taken branch penalty, uncond jump  '
          f'{cyc[8] - cyc[3]:+8.3f} cyc  (rung 8 - rung 3, same 10 '
          f'instructions)')
    print(f'  taken branch penalty, comp+cond    '
          f'{cyc[5] - RUNGS[5][1]:+8.3f} cyc  (rung 5 excess; one taken '
          f'`if eq jump` after a `comp`)')
    print(f'  call + rts, both taken             '
          f'{cyc[1] - cyc[0] - 2:+8.3f} cyc  (rung 1 excess)')
    print(f'  branch-free inline, rung 9 excess  '
          f'{cyc[9] - RUNGS[9][1]:+8.3f} cyc over its naive count')
    print(f'  branch-free inline, rung 10 excess '
          f'{cyc[10] - RUNGS[10][1]:+8.3f} cyc over its naive count '
          f'({RUNGS[10][1]} instructions, no branch)')
    print(f'  -> the part issues straight-line code at one instruction '
          f'per cycle and pays the penalty ONLY at a taken branch')
    print()
    print('--- TUBE, AND THE CROSS-CHECK AGAINST THE GRAPH')
    print(f'  TUBE body as it ships (3 calls)    {cyc[6]:8.3f} cyc/sample '
          f'= {cyc[6] * blk:8.1f} cyc/block')
    print(f'  session 9, same body, in the GRAPH  {103.9:8.3f} cyc/sample '
          f'= {829:4d}-{834:d} cyc/block (same-boot TubeOn 0->1 diff)')
    d = (cyc[6] - 103.9) / 103.9 * 100
    print(f'  agreement                          {d:+8.2f}%'
          f'   {"<-- the two instruments agree" if abs(d) < 10 else "<-- THEY DISAGREE; neither number is usable"}')
    print(f'  TUBE body with the calls inlined   {cyc[7]:8.3f} cyc/sample '
          f'= {cyc[7] * blk:8.1f} cyc/block')
    print(f'  RECOVERED BY INLINING 3 PAIRS      {cyc[6] - cyc[7]:8.3f} '
          f'cyc/sample = {(cyc[6] - cyc[7]) / 3:.3f} per pair')
    print(f'  TUBE body inlined AND branch-free  {cyc[10]:8.3f} cyc/sample '
          f'= {cyc[10] * blk:8.1f} cyc/block')
    print(f'  RECOVERED BY BOTH, PER PAIR SITE   '
          f'{(cyc[6] - cyc[10]) / 3:8.3f} cyc/sample'
          f'   (total {cyc[6] - cyc[10]:.3f} c/s off a {cyc[6]:.1f} c/s body)')

    print()
    print(f'CALLCAL: pair cost = {cyc[1] - cyc[0]:.2f} cyc bare, '
          f'{cyc[2] - cyc[3]:.2f} cyc around a body; taken-branch penalty '
          f'{cyc[8] - cyc[3]:.2f} cyc; '
          f'{(cyc[6] - cyc[10]) / 3:.2f} cyc recovered per pair site by '
          f'inlining branch-free')
    return 0


if __name__ == '__main__':
    sys.exit(main())
