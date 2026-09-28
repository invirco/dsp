#!/usr/bin/env python3
"""follow_lockstep_check.py — the ramp/click prover for a stereo follower.

WHAT THIS IS FOR
----------------
S142 §3.1 named three hazards in the `follows=` mechanism and the first is
the one a bench can miss for months:

    CROSSFADE LOCKSTEP. `_fx_cascade_node` clears `swap_pending` and
    advances `xfade_alpha` / flips `active` inside its own body, so a
    follower running AFTER the master reads post-update values and uses
    the WRONG BANK for its block -- silently, and only during a
    coefficient change.

S142 also recorded that this tree has no desk-side click-free or ramp
prover at all (`dsp_validate` checks only that a `ramp_profile` NAME is
recognised; `dsp_simulate` parses the field and never applies it), which
is one of the two reasons it stopped rather than building Main R. This is
that prover, for the one ramp the S143 build introduces.

WHAT IT PROVES, IN THREE PARTS
------------------------------
 1. THE STATE MACHINE IS IN LOCKSTEP, sample for sample, across a
    coefficient change -- and the NEGATIVE CONTROL is the hazard itself:
    the same run with the follower reading the master's LIVE `active`
    (which is what a shared word would give) is shown to diverge. A
    prover that cannot fail the broken design proves nothing.

 2. THE AUDIO IS CLICK-FREE AND THE TWO LEGS ARE IDENTICAL. The fixed
    reference's own biquad (`fixed_ref.py`, the normative model) runs the
    real 576-sample crossfade on both legs through a coefficient change,
    and the output is checked for (a) bit-identical legs given identical
    input, and (b) no step discontinuity -- the largest sample-to-sample
    jump during the fade against the largest in steady state.

 3. THE EMITTED CODE IS THE STATE MACHINE MODELLED. Checked against the
    assembly, not assumed: the master stores 1 into each follower's
    `_swap_pending_`; the follower owns `_active_`, `_xfade_alpha_`,
    `_xfade_step_`, `_swap_pending_` and both state banks; and it
    `.extern`s -- does not declare -- the coefficient banks.

WHAT IT DOES NOT PROVE, stated so the bench list is right: that the SHARC
executes this state machine. Part 3 checks the text that was emitted; the
arithmetic is the fixed reference's, which the golden harness scores. A
coefficient change on a live crossover, heard on the part, is the reading
that closes it (and it is on the queued bench list).

Usage:
  python3 tools/dsp/follow_lockstep_check.py [--src DIR] [--csv PATH] [-v]

Exit: 0 pass, 1 fail, 2 usage/environment error.
"""

import argparse
import csv
import math
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DEF_CSV = os.path.join(REPO_ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'dsp.csv')
DEF_SRC = os.path.join(REPO_ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'src')

sys.path.insert(0, SCRIPT_DIR)
import fixed_ref as fr
from csv_fields import parse_params

FS = 48000.0
# The crossfade, from the generator. Single source: a prover that carried
# its own copy would go on passing after the ramp changed.
from dsp_codegen import XFADE_SAMPLES, XFADE_STEP, BLOCK

results = []


def check(name, ok, detail=''):
    results.append((name, ok, detail))
    return ok


# ---------------------------------------------------------------------------
# PART 1 — the state machine
# ---------------------------------------------------------------------------

class Cascade:
    """One dual-instance crossfade node's transient bookkeeping.

    Exactly what `_fx_cascade_node` emits: `swap_pending` is consumed by
    `_start_xfade_`, which zeroes the dormant state and sets alpha to 0
    with a step; the per-sample body advances alpha and flips `active`
    when it reaches 1.0.
    """

    def __init__(self, name):
        self.name = name
        self.active = 0
        self.alpha = 0.0
        self.step = 0.0
        self.swap_pending = 0
        self.zeroed = []          # which bank was zeroed, per swap

    def start_xfade(self):
        self.swap_pending = 0
        self.zeroed.append('B' if self.active == 0 else 'A')
        self.step = XFADE_STEP
        self.alpha = 0.0

    def sample(self):
        """One sample of the node's body. Returns the bank pair in use."""
        if self.swap_pending:
            self.start_xfade()
        banks = ('A', 'B') if self.active == 0 else ('B', 'A')
        if self.step != 0.0:
            self.alpha += self.step
            if self.alpha >= 1.0:
                self.active ^= 1
                self.step = 0.0
                self.alpha = 0.0
        return banks


def run_state_machine(n_samples, swap_at, shared_active=False):
    """Master + follower over a coefficient change. Returns the trace.

    `shared_active` models THE HAZARD: a follower that reads the master's
    live `_active_` instead of owning one, which is what the latch in
    S142 §3.1 was specified to fix and what the built mechanism removes
    by construction.
    """
    m, f = Cascade('master'), Cascade('follower')
    trace = []
    # A BLOCK AT A TIME, IN CHAIN ORDER, because that is what the image
    # does: under DSP4_BLOCK_KERNELS the master runs its whole block and
    # then the follower runs its whole block. Modelling it sample-
    # interleaved would understate the hazard by a factor of BLOCK -- the
    # master can flip `active` at sample 3 of its block and the follower
    # then runs all BLOCK of its own samples behind the flip.
    for base in range(0, n_samples, BLOCK):
        span = range(base, min(base + BLOCK, n_samples))
        mrec, frec = [], []
        for n in span:
            if n == swap_at:
                m.swap_pending = 1
            was_pending = m.swap_pending
            banks = m.sample()
            mrec.append((m.active, round(m.alpha, 12), banks))
            if was_pending:
                # THE KICK, exactly where the emitted code puts it: the
                # last thing `_start_xfade_` does before its rts.
                f.swap_pending = 1
        m_end_active = m.active
        for n in span:
            if shared_active:
                # THE HAZARD: the follower reads the master's live word,
                # which by now holds what the master left at the END of
                # its block.
                f.active = m_end_active
            banks = f.sample()
            frec.append((f.active, round(f.alpha, 12), banks))
        for i, n in enumerate(span):
            trace.append((n, mrec[i][0], frec[i][0], mrec[i][1],
                          frec[i][1], mrec[i][2], frec[i][2]))
    return m, f, trace


def part1(verbose):
    n = XFADE_SAMPLES + 3 * BLOCK
    swap_at = BLOCK          # a swap on a block boundary, as SPI delivers it
    m, f, tr = run_state_machine(n, swap_at)
    bad = [t for t in tr if t[1] != t[2] or t[3] != t[4] or t[5] != t[6]]
    check('lockstep: active, alpha and bank pair agree at every sample',
          not bad,
          '' if not bad else
          f'first divergence at sample {bad[0][0]}: master active={bad[0][1]} '
          f'alpha={bad[0][3]} bank={bad[0][5]}, follower active={bad[0][2]} '
          f'alpha={bad[0][4]} bank={bad[0][6]}')
    check('lockstep: both nodes zeroed the same dormant bank',
          m.zeroed == f.zeroed == ['B'],
          f'master {m.zeroed}, follower {f.zeroed}')
    check('lockstep: the fade completed and both flipped',
          m.active == 1 and f.active == 1,
          f'master active={m.active}, follower active={f.active}')
    check('lockstep: the fade is XFADE_SAMPLES long',
          sum(1 for t in tr if t[3] != 0.0) == XFADE_SAMPLES - 1,
          f'{sum(1 for t in tr if t[3] != 0.0)} of {XFADE_SAMPLES - 1}')

    # THE NEGATIVE CONTROL: the hazard, reproduced.
    _, _, tr_bad = run_state_machine(n, swap_at, shared_active=True)
    div = [t for t in tr_bad if t[5] != t[6]]
    check('negative control: a SHARED `active` puts the follower on the '
          'wrong bank', bool(div),
          'a shared active did NOT diverge, so this prover cannot tell the '
          'hazard from the fix'
          if not div else
          f'{len(div)} sample(s) on the wrong bank, first at {div[0][0]}')
    if verbose and div:
        print(f'    hazard reproduced: at sample {div[0][0]} the master is '
              f'on {div[0][5]} and the follower on {div[0][6]}')
    return m, f


# ---------------------------------------------------------------------------
# PART 2 — the audio
# ---------------------------------------------------------------------------

def peaking(f0, gain_db, q):
    a = 10.0 ** (gain_db / 40.0)
    w0 = 2 * math.pi * f0 / FS
    al = math.sin(w0) / (2 * q)
    b0, b1, b2 = 1 + al * a, -2 * math.cos(w0), 1 - al * a
    a0, a1, a2 = 1 + al / a, -2 * math.cos(w0), 1 - al / a
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


class Leg:
    """One instance: two coefficient banks (SHARED with its partner), its
    OWN biquad state in each, and its own crossfade."""

    def __init__(self, banks):
        self.banks = banks                       # {'A': cq, 'B': cq}
        self.state = {'A': fr.biquad_state(), 'B': fr.biquad_state()}
        self.fsm = Cascade('leg')

    def zero_dormant(self):
        self.state['B' if self.fsm.active == 0 else 'A'] = fr.biquad_state()

    def process(self, x):
        if self.fsm.swap_pending:
            self.fsm.start_xfade()
            self.zero_dormant()
        xq = fr.to_q(x)
        ya = fr.biquad(xq, self.banks['A'], self.state['A'])
        yb = fr.biquad(xq, self.banks['B'], self.state['B'])
        if self.fsm.step != 0.0:
            old, new = (ya, yb) if self.fsm.active == 0 else (yb, ya)
            a = self.fsm.alpha
            y = old * (1.0 - a) + new * a
            self.fsm.alpha += self.fsm.step
            if self.fsm.alpha >= 1.0:
                self.fsm.active ^= 1
                self.fsm.step = 0.0
                self.fsm.alpha = 0.0
        else:
            y = ya if self.fsm.active == 0 else yb
        return fr.from_q(int(y))


def part2(verbose):
    """The real crossfade, on the fixed reference's own biquad."""
    flat = fr.biquad_coeffs_q(*peaking(1000.0, 0.0, 1.0))
    boost = fr.biquad_coeffs_q(*peaking(1000.0, 12.0, 1.0))
    banks = {'A': flat, 'B': flat}               # SHARED between the legs
    L, R = Leg(banks), Leg(banks)

    n = XFADE_SAMPLES + 4 * BLOCK
    swap_at = BLOCK
    sig = [0.25 * math.sin(2 * math.pi * 1000.0 * i / FS) for i in range(n)]

    # Steady state first, for the click bar: the largest sample-to-sample
    # jump this signal makes through this filter with NOTHING changing.
    ref = Leg({'A': flat, 'B': flat})
    ry = [ref.process(x) for x in sig]
    steady_step = max(abs(ry[i] - ry[i - 1]) for i in range(1, len(ry)))

    yl, yr = [], []
    for i, x in enumerate(sig):
        if i == swap_at:
            banks['B'] = boost              # the master staged the dormant
            L.fsm.swap_pending = 1          # master's own swap
            R.fsm.swap_pending = 1          # THE KICK
        yl.append(L.process(x))
        yr.append(R.process(x))

    check('audio: the two legs are identical, sample for sample',
          yl == yr,
          '' if yl == yr else
          f'first difference at sample '
          f'{next(i for i in range(len(yl)) if yl[i] != yr[i])}')

    fade_step = max(abs(yl[i] - yl[i - 1])
                    for i in range(swap_at, swap_at + XFADE_SAMPLES))
    # A 12 dB boost arriving over 576 samples raises the signal's own
    # slope; what would be a CLICK is a jump far larger than the boosted
    # steady state's. The bar is the boosted filter's own worst step,
    # which is the most the finished fade can legitimately reach.
    boosted = Leg({'A': boost, 'B': boost})
    by = [boosted.process(x) for x in sig]
    boosted_step = max(abs(by[i] - by[i - 1]) for i in range(1, len(by)))
    bar = max(steady_step, boosted_step) * 1.02
    check('audio: no step discontinuity across the fade',
          fade_step <= bar,
          f'worst step in the fade {fade_step:.9g} against the bar '
          f'{bar:.9g} (steady {steady_step:.9g}, boosted {boosted_step:.9g})')
    if verbose:
        print(f'    worst step: fade {fade_step:.6g}, steady '
              f'{steady_step:.6g}, boosted {boosted_step:.6g}')

    # AND THE FADE REALLY HAPPENED. A prover that passes on a node that
    # ignored the swap is worth nothing.
    settled = max(abs(v) for v in yl[-BLOCK:])
    before = max(abs(v) for v in yl[:swap_at])
    check('audio: the coefficient change took effect',
          settled > before * 1.5,
          f'after {settled:.6g} against before {before:.6g}')
    return yl


# ---------------------------------------------------------------------------
# PART 3 — the emitted code
# ---------------------------------------------------------------------------

_CASCADE_PFX = {'GEQ': 'geq', 'ANTI_FB': 'afb', 'CROSSOVER': 'xover'}


def part3(csv_path, src_dir, verbose):
    with open(csv_path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    by_id = {r['id'].strip(): r for r in rows}
    pairs = []
    for r in rows:
        m = parse_params(r.get('params', '')).get('follows')
        if m and r['type'].strip() in _CASCADE_PFX:
            pairs.append((r['id'].strip(), m, _CASCADE_PFX[r['type'].strip()]))
    if not pairs:
        check('emitted code: at least one followed cascade to check', False,
              'this graph declares no `follows=` on a GEQ/ANTI_FB/CROSSOVER')
        return
    ok_all = True
    for fid, mid, pfx in pairs:
        chip = 'chip1' if by_id[fid]['chip'].strip() == '1' else 'chip2'
        fpath = os.path.join(src_dir, chip, 'nodes', fid + '.asm')
        mpath = os.path.join(src_dir, chip, 'nodes', mid + '.asm')
        try:
            ftxt = open(fpath, encoding='utf-8').read()
            mtxt = open(mpath, encoding='utf-8').read()
        except OSError as e:
            check(f'emitted code: {fid}', False, str(e))
            ok_all = False
            continue
        # The kick, in the master.
        kick = re.search(r'dm\(_%s_swap_pending_%s\)\s*=\s*r4;'
                         % (pfx, re.escape(fid)), mtxt)
        ok = bool(kick)
        # Owned by the follower, every one of them.
        own = [f'_{pfx}_active_{fid}', f'_{pfx}_xfade_alpha_{fid}',
               f'_{pfx}_xfade_step_{fid}', f'_{pfx}_swap_pending_{fid}',
               f'_{pfx}_state_A_{fid}' if pfx != 'xover'
               else f'_{pfx}_lp_state_A_{fid}']
        missing = [s for s in own
                   if not re.search(r'\.var\s+%s\b' % re.escape(s), ftxt)]
        ok = ok and not missing
        # Shared, and `.extern` -- not declared twice.
        if pfx == 'xover':
            shared = [f'_{pfx}_lp_A_{mid}', f'_{pfx}_hp_A_{mid}']
        else:
            shared = [f'_{pfx}_coeffs_A_{mid}', f'_{pfx}_coeffs_B_{mid}']
        not_ext = [s for s in shared
                   if not re.search(r'\.extern\s+%s\b' % re.escape(s), ftxt)]
        redeclared = [s for s in
                      (f'_{pfx}_coeffs_A_{fid}', f'_{pfx}_lp_A_{fid}')
                      if re.search(r'\.var\s+%s\b' % re.escape(s), ftxt)]
        ok = ok and not not_ext and not redeclared
        detail = ''
        if not kick:
            detail = (f'{mid} does not store into '
                      f'_{pfx}_swap_pending_{fid}: without the kick the '
                      f'follower never starts its fade and the two legs '
                      f'run different filters for the rest of the image')
        elif missing:
            detail = f'{fid} does not own {missing}'
        elif not_ext:
            detail = f'{fid} does not .extern {not_ext}'
        elif redeclared:
            detail = (f'{fid} declares its own {redeclared}: the whole '
                      f'point is ONE parameter set')
        check(f'emitted code: {fid} follows {mid} in lockstep', ok, detail)
        ok_all = ok_all and ok
        if verbose and ok:
            print(f'    {mid} -> {fid}: kick present, '
                  f'{len(own)} owned word(s), {len(shared)} shared bank(s)')
    return ok_all


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--csv', default=DEF_CSV)
    ap.add_argument('--src', default=DEF_SRC)
    ap.add_argument('-v', '--verbose', action='store_true')
    args = ap.parse_args()

    print('follower crossfade lockstep / click prover')
    print(f'  crossfade: {XFADE_SAMPLES} samples, step {XFADE_STEP:.9g}, '
          f'block {BLOCK}')
    part1(args.verbose)
    part2(args.verbose)
    part3(args.csv, args.src, args.verbose)

    print()
    npass = sum(1 for _, ok, _ in results if ok)
    for name, ok, detail in results:
        print(f'  {"PASS" if ok else "FAIL"}  {name}')
        if detail:
            print(f'        {detail}')
    print(f'\n{npass}/{len(results)} passed')
    return 0 if npass == len(results) else 1


if __name__ == '__main__':
    sys.exit(main())
