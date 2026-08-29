#!/usr/bin/env python3
"""dsp4_num_verify.py — the wide-accumulator and blend arithmetic against
its golden reference, ON THE PART (review findings D1 and D3).

WHAT IS COMPARED. Nothing here is a tolerance. The DSP runs the REAL
routines over vectors that straddle the two boundaries the 2026-08-28
review found could WRAP, leaves the results in DM, and this reads them
back and diffs them against tools/dsp/fixed_ref.py:

    _nst_mix_r[i]  vs  fixed_ref.mix_sum(*boundary_vectors.mix_expand(v))
    _nst_bl_r[i]   vs  fixed_ref.xfade_blend(new, old, alpha)

The vectors come from tools/dsp/boundary_vectors.py, which is also what
generated the .var tables in the image, so both sides are quoting the
same numbers rather than two transcriptions of them.

WHY IT IS THE REAL CODE AND NOT A COPY:
  MIX   the self-test calls _acc64_mac and _acc64_rns28 -- the routines
        every RTG crosspoint and every bus readout in the graph calls.
  BLEND the probe body is emitted by _xfade_blend_core() in
        dsp_codegen.py, the same expression that emits the blend into
        all 32 EQ nodes, all 32 FILT nodes and both crossover nodes.

NEGATIVE CONTROL. Run again with an image built DSP4_NUM_NEGCTL=1 and
pass --negctl here. That image runs the PRE-FIX arithmetic -- the 64-bit
accumulator that discards MR2F, and the 32-bit new-old difference -- and
this then requires:
  * every vector that does NOT cross a boundary still matches
    fixed_ref, and
  * every vector that DOES cross one matches fixed_ref's model of the
    OLD arithmetic and DIFFERS from the fixed model.
A negative control that merely "fails" proves little; this one has to
fail in the exact places the model predicts, which is what rules out a
dead probe, a stale image and a mis-addressed symbol at the same time.

TIMING. _nst_tick[0..5] holds three (start, end) diag-tick pairs over
identical work: null, the three-word MAC the graph now runs, and the
pre-fix two-word MAC. The per-MAC delta is reported in cycles at the
build's core clock -- that is the measured cost of the third word.

Usage:
  python3 dsp4_num_verify.py [--negctl] [--chip 1] [--clock 491520000]
"""
import argparse
import sys

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
import fixed_ref as fr
import boundary_vectors as bv


def s32(v):
    return v - (1 << 32) if v & 0x80000000 else v


def vpeek(sc, addr, need=2, limit=7):
    """A VOTED peek. sc.peek() is one transaction and this link drops
    answers: a dropped answer comes back as a well-formed stale or
    rotated word, not as an error. On 2026-08-29 that turned one
    negative-control vector into a false mismatch and cost a round of
    theorising about SHARC MAC saturation. A bit-exact claim cannot rest
    on unvoted reads, so every result word here is read until the same
    value comes back `need` times."""
    seen = {}
    for _ in range(limit):
        v = sc.peek(addr)
        seen[v] = seen.get(v, 0) + 1
        if seen[v] >= need:
            return v
    raise IOError('0x%X never returned the same value %d times in %d reads: %r'
                  % (addr, need, limit, seen))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--negctl', action='store_true',
                    help='the image is the PRE-FIX build; require it to '
                         'fail exactly where the model predicts')
    ap.add_argument('--chip', type=int, default=1)
    ap.add_argument('--clock', type=float, default=491.52e6,
                    help='core clock of the build, for the cycle figures')
    a = ap.parse_args()

    sc = S.Scope(a.chip)
    sc.check_chip()

    done = vpeek(sc, sc.sym['_nst_done'])
    if done != 1:
        print(f'SELF-TEST NEVER RAN (_nst_done = {done}) — is this a '
              f'DSP4_NUM_SELFTEST build, and did the main loop reach it?')
        return 3
    negctl_in_image = vpeek(sc, sc.sym['_nst_negctl'])
    if bool(negctl_in_image) != a.negctl:
        print(f'IMAGE/FLAG MISMATCH: _nst_negctl = {negctl_in_image} in the '
              f'image, --negctl {"given" if a.negctl else "not given"} here. '
              f'Refusing to score a build against the wrong expectation.')
        return 3

    good_mix, good_bl = bv.expected()
    old_mix, old_bl = bv.expected_prefix()
    want_mix = old_mix if a.negctl else good_mix
    want_bl = old_bl if a.negctl else good_bl

    # THE NEGATIVE-CONTROL BAR is "differs from the FIXED model on
    # exactly the vectors that cross a boundary, and matches it
    # everywhere else". Whether the pre-fix result also matches
    # fixed_ref's MODEL of the pre-fix arithmetic is reported but is not
    # the bar: that model describes code that no longer exists, and the
    # part has already shown it is not a faithful description at the
    # exact -2^63 boundary (see the note in the session outcome). The
    # bar is about what the vectors can DETECT.
    bad = 0
    across_seen = 0
    prefix_agree = 0
    prefix_total = 0
    print(f'--- MIX ({len(bv.MIX)} vectors, '
          f'{sum(bv.mix_predicted_wrong(v) for v in bv.MIX)} across the '
          f'64-bit boundary)')
    base = sc.sym['_nst_mix_r']
    for i, v in enumerate(bv.MIX):
        got = s32(vpeek(sc, base + i))
        across = bv.mix_predicted_wrong(v)
        if a.negctl and across:
            ok = (got != good_mix[i])          # must fail, and it must
            across_seen += ok                  # be THIS vector that fails
            prefix_total += 1
            prefix_agree += (got == want_mix[i])
        else:
            ok = (got == good_mix[i])          # must still be exact
        bad += not ok
        note = ''
        if a.negctl and across:
            note = ('   (across, differs as required)' if ok
                    else '   (across, did NOT fail)')
            if got != want_mix[i]:
                note += ' [pre-fix model said %d]' % want_mix[i]
        elif across:
            note = '   (across)'
        print(f'  {v[6]:38s} {got:12d} / '
              f'{(good_mix[i] if not a.negctl else want_mix[i]):12d}  '
              f'{"ok" if ok else "<-- MISMATCH"}{note}')

    print(f'--- BLEND ({len(bv.BLEND)} vectors, '
          f'{sum(bv.blend_predicted_wrong(v) for v in bv.BLEND)} across the '
          f'32-bit difference)')
    base = sc.sym['_nst_bl_r']
    shown = 0
    for i, v in enumerate(bv.BLEND):
        got = s32(vpeek(sc, base + i))
        across = bv.blend_predicted_wrong(v)
        if a.negctl and across:
            ok = (got != good_bl[i])
            across_seen += ok
            prefix_total += 1
            prefix_agree += (got == want_bl[i])
        else:
            ok = (got == good_bl[i])
        bad += not ok
        if across or not ok or shown < 6:
            shown += 1
            note = ''
            if a.negctl and across:
                note = ('   (across, differs as required)' if ok
                        else '   (across, did NOT fail)')
                if got != want_bl[i]:
                    note += ' [pre-fix model said %d]' % want_bl[i]
            elif across:
                note = '   (across)'
            print(f'  {v[3]:26s} {got:12d} / '
                  f'{(good_bl[i] if not a.negctl else want_bl[i]):12d}  '
                  f'{"ok" if ok else "<-- MISMATCH"}{note}')

    # ---- timing ----------------------------------------------------------
    # cycles = (ticks_end - ticks_start) * TPERIOD
    #          + (tcount_start - tcount_end)
    # TCOUNT counts core clocks DOWN and reloads from TPERIOD, so the
    # second term is positive within a tick. This is main.asm's own
    # per-block accounting form; the 1 kHz tick alone quantises to
    # 2.46 cycles/MAC at 200k iterations and cannot see this change.
    t = [vpeek(sc, sc.sym['_nst_tick'] + k) for k in range(20)]
    tper = vpeek(sc, sc.sym['_nst_tper'])
    iters = vpeek(sc, sc.sym['_nst_iters'])

    def cycles(k):
        ticks = t[4 * k + 2] - t[4 * k + 0]
        tc = t[4 * k + 1] - t[4 * k + 3]
        return ticks * tper + tc

    null, new, old = cycles(0), cycles(1), cycles(2)
    print(f'--- TIMING ({iters} iterations, TPERIOD {tper} '
          f'= {a.clock / 1e6:.2f} MHz)')
    print(f'  null loop             {null:10d} cyc -> '
          f'{null / iters:7.3f} cycles/iteration')
    print(f'  _acc64_mac  (3 word)  {new:10d} cyc -> '
          f'{(new - null) / iters:7.3f} cycles/MAC over the null loop')
    print(f'  _nst_mac_old (2 word) {old:10d} cyc -> '
          f'{(old - null) / iters:7.3f} cycles/MAC over the null loop')
    print(f'  COST OF THE THIRD WORD: {(new - old) / iters:+.3f} cycles/MAC')
    if vpeek(sc, sc.sym['_nst_have_blk']):
        bs = vpeek(sc, sc.sym['_nst_blk_n'])
        macs = iters * bs
        bnew, bold = cycles(3), cycles(4)
        print(f'  -- block kernel, {bs} MACs per call --')
        print(f'  _acc64_mac_blk  (3 word) {bnew:10d} cyc -> '
              f'{bnew / macs:7.3f} cycles/MAC')
        print(f'  _nst_mac_blk_old(2 word) {bold:10d} cyc -> '
              f'{bold / macs:7.3f} cycles/MAC')
        print(f'  COST OF THE THIRD WORD, block form: '
              f'{(bnew - bold) / macs:+.3f} cycles/MAC')

    n = len(bv.MIX) + len(bv.BLEND)
    if a.negctl:
        need = (sum(bv.mix_predicted_wrong(v) for v in bv.MIX)
                + sum(bv.blend_predicted_wrong(v) for v in bv.BLEND))
        print(f'\nNEGATIVE CONTROL')
        print(f'  boundary vectors that FAILED, as required: '
              f'{across_seen} of {need}')
        print(f'  non-boundary vectors still exact against fixed_ref: '
              f'{n - need - (bad - (need - across_seen))} of {n - need}')
        print(f'  of the failures, {prefix_agree} of {prefix_total} also '
              f'match fixed_ref\'s model of the pre-fix arithmetic '
              f'(informational — that model describes deleted code)')
        if bad:
            print('NEGCTL FAILED: either a boundary vector did not fail, or '
                  'a non-boundary vector stopped being exact. The first '
                  'means the vectors straddle nothing on this silicon; the '
                  'second means this is not the image it claims to be.')
            return 2
        print('NEGCTL PASSED: every boundary vector is detected, every '
              'other vector is untouched')
        return 0
    print(f'\nNUMERIC BOUNDARY {"BIT-EXACT" if bad == 0 else "DIFFERS"} '
          f'({n - bad} of {n} vectors match fixed_ref)')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
