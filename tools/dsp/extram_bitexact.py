#!/usr/bin/env python3
"""extram_bitexact.py — acceptance harness for the EXTRAM delay-pool backend.

Why this exists
----------------
S75 adds an external-RAM (HyperRAM on xSPI0) backend for the delay lines.
The part is not on the board (the HyperRAM footprint needs a board
modification that hasn't happened), so nothing here can be checked
against silicon. What CAN be checked, using extram_model.py's host model
plus a simulated HyperRAM:

  1. adding the backend does not perturb what already ships: everywhere
     the L2 backend serves today (offsets inside the head), the EXTRAM
     backend must produce IDENTICAL output, sample for sample;
  2. the range the EXTRAM backend newly serves (offsets past the head, up
     to the full 250 ms spec length) is bit-exact against an
     infinite-precision reference, including across the 750-slot history
     ring's wraparound and through an offset change mid-stream;
  3. the simulated bus traffic this needs fits the bandwidth budget the
     design document quotes;
  4. the comparison itself is real — a deliberately corrupted RAM word
     must make the tail-range check FAIL, or none of the above proves
     anything.

Exit code 0 = all checks pass. Usage: python3 extram_bitexact.py [-v]
"""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import extram_model as em

results = []
sample_counts = []


def check(name, value, limit, unit, lower_is_better=True):
    ok = value <= limit if lower_is_better else value >= limit
    results.append((name, value, limit, unit, ok))
    return ok


def note_samples(check_name, n):
    sample_counts.append((check_name, n))


def _rand_stream(rng, n_blocks, n_lines, block):
    """A (n_blocks, n_lines, block) int32 array covering the full int32
    range, and each line's flattened (n_blocks*block,) stream."""
    total = n_blocks * n_lines * block
    flat = rng.integers(em.I32_MIN, em.I32_MAX, size=total, dtype=np.int64)
    arr = flat.reshape(n_blocks, n_lines, block).astype(np.int32)
    streams = [arr[:, i, :].reshape(-1) for i in range(n_lines)]
    return arr, streams


# ---------------------------------------------------------------------------
# 1. HEAD-RANGE BIT-EXACTNESS
# ---------------------------------------------------------------------------

def t_head_range(verbose):
    """Both backends read the same head-ring formula for off < head_len --
    this is the proof that adding the EXTRAM backend does not perturb the
    L2 path that already ships."""
    HEAD = 960
    MAXLEN = 12000
    N_BLOCKS = 400
    offset_set = [0, 1, 15, 16, 17, 100, 959]
    n_lines = 32
    offsets = [offset_set[i % len(offset_set)] for i in range(n_lines)]

    rng = np.random.default_rng(20260919)
    inputs, _streams = _rand_stream(rng, N_BLOCKS, n_lines, em.BLOCK)

    ram = em.HyperRamModel(em.SLOTS * n_lines * em.BLOCK)
    pool_l2 = em.DelayPool(n_lines, HEAD, MAXLEN, 'l2')
    pool_er = em.DelayPool(n_lines, HEAD, MAXLEN, 'extram', ram=ram)

    worst = 0
    n_compared = 0
    for b in range(N_BLOCKS):
        out_l2 = pool_l2.process_block(b, inputs[b], offsets)
        out_er = pool_er.process_block(b, inputs[b], offsets)
        d = int(np.max(np.abs(out_l2.astype(np.int64) - out_er.astype(np.int64))))
        worst = max(worst, d)
        n_compared += out_l2.size

    check('head-range: l2 vs extram, every offset in {0,1,15,16,17,100,959}',
          worst, 0, 'LSB')
    note_samples('1 head-range bit-exactness', n_compared)
    if verbose:
        print(f'  head-range: {n_compared} samples compared, worst diff {worst}')


# ---------------------------------------------------------------------------
# 2. TAIL-RANGE CORRECTNESS
# ---------------------------------------------------------------------------

def t_tail_range(verbose):
    """extram must equal the infinite-precision reference past the head
    (after the two-block arming transient); l2 must NOT match, so the
    check cannot pass vacuously."""
    HEAD = 960
    MAXLEN = 12000
    N_BLOCKS = 1000
    offsets_list = [960, 961, 1000, 1024, 4799, 6000, 11999]
    n_lines = len(offsets_list)

    rng = np.random.default_rng(1000019)
    inputs, streams = _rand_stream(rng, N_BLOCKS, n_lines, em.BLOCK)

    ram = em.HyperRamModel(em.SLOTS * n_lines * em.BLOCK)
    pool_er = em.DelayPool(n_lines, HEAD, MAXLEN, 'extram', ram=ram)
    pool_l2 = em.DelayPool(n_lines, HEAD, MAXLEN, 'l2')

    out_er_all = np.zeros((N_BLOCKS, n_lines, em.BLOCK), dtype=np.int32)
    out_l2_all = np.zeros((N_BLOCKS, n_lines, em.BLOCK), dtype=np.int32)
    for b in range(N_BLOCKS):
        out_er_all[b] = pool_er.process_block(b, inputs[b], offsets_list)
        out_l2_all[b] = pool_l2.process_block(b, inputs[b], offsets_list)

    worst = 0
    n_compared = 0
    l2_mismatches = 0
    for i, off in enumerate(offsets_list):
        ref = em.reference_delay(streams[i], off, MAXLEN)
        got = out_er_all[:, i, :].reshape(-1)
        # skip the two-block (32-sample) arming transient
        skip = 2 * em.BLOCK
        d = int(np.max(np.abs(got[skip:].astype(np.int64) - ref[skip:].astype(np.int64))))
        worst = max(worst, d)
        n_compared += len(ref) - skip

        got_l2 = out_l2_all[:, i, :].reshape(-1)
        l2_mismatches += int(np.sum(got_l2[skip:] != ref[skip:]))

        if verbose:
            print(f'  tail off={off}: extram worst diff {d}, '
                  f'l2 mismatches {int(np.sum(got_l2[skip:] != ref[skip:]))}')

    check('tail-range: extram vs infinite-precision reference (all offsets)',
          worst, 0, 'LSB')
    check('tail-range: l2 does NOT match the reference (negative control)',
          l2_mismatches, 1, 'mismatches', lower_is_better=False)
    note_samples('2 tail-range correctness', n_compared)


# ---------------------------------------------------------------------------
# 3. RING-WRAP
# ---------------------------------------------------------------------------

def t_ring_wrap(verbose):
    """1600 blocks is more than two full revolutions of the 750-slot
    history; offsets 11999 and 6001 must stay exact across the wrap."""
    HEAD = 960
    MAXLEN = 12000
    N_BLOCKS = 1600
    offsets_list = [11999, 6001]
    n_lines = len(offsets_list)

    rng = np.random.default_rng(160019)
    inputs, streams = _rand_stream(rng, N_BLOCKS, n_lines, em.BLOCK)

    ram = em.HyperRamModel(em.SLOTS * n_lines * em.BLOCK)
    pool = em.DelayPool(n_lines, HEAD, MAXLEN, 'extram', ram=ram)

    out_all = np.zeros((N_BLOCKS, n_lines, em.BLOCK), dtype=np.int32)
    for b in range(N_BLOCKS):
        out_all[b] = pool.process_block(b, inputs[b], offsets_list)

    worst = 0
    n_compared = 0
    skip = 2 * em.BLOCK
    for i, off in enumerate(offsets_list):
        ref = em.reference_delay(streams[i], off, MAXLEN)
        got = out_all[:, i, :].reshape(-1)
        d = int(np.max(np.abs(got[skip:].astype(np.int64) - ref[skip:].astype(np.int64))))
        worst = max(worst, d)
        n_compared += len(ref) - skip
        if verbose:
            print(f'  ring-wrap off={off} ({N_BLOCKS} blocks, '
                  f'{N_BLOCKS / em.SLOTS:.2f} revolutions): worst diff {d}')

    check('ring-wrap: exact across >2 revolutions of the 750-slot history',
          worst, 0, 'LSB')
    note_samples('3 ring-wrap', n_compared)


# ---------------------------------------------------------------------------
# 4. OFFSET CHANGE MID-STREAM
# ---------------------------------------------------------------------------

def t_offset_change(verbose):
    """960 -> 11999 -> 16 -> 5000 on one line. No crash; head-range exact
    immediately on the switch to 16; tail-range exact from the third
    block after each switch to a tail offset (two-block arming)."""
    HEAD = 960
    MAXLEN = 12000
    PHASE = 800     # long enough that later phases see real (nonzero) history
    phases = [960, 11999, 16, 5000]
    n_blocks = PHASE * len(phases)
    n_lines = 1

    rng = np.random.default_rng(40019)
    inputs, streams = _rand_stream(rng, n_blocks, n_lines, em.BLOCK)
    stream = streams[0]

    offsets_per_block = []
    for p in phases:
        offsets_per_block += [p] * PHASE

    completed = 0
    worst = 0
    n_compared = 0
    arming_nonzero = 0
    try:
        ram = em.HyperRamModel(em.SLOTS * n_lines * em.BLOCK)
        pool = em.DelayPool(n_lines, HEAD, MAXLEN, 'extram', ram=ram)
        out_all = np.zeros((n_blocks, n_lines, em.BLOCK), dtype=np.int32)
        for b in range(n_blocks):
            out_all[b] = pool.process_block(b, inputs[b], [offsets_per_block[b]])
        got = out_all[:, 0, :].reshape(-1)

        for phase_idx, off in enumerate(phases):
            b0 = phase_idx * PHASE
            b1 = b0 + PHASE
            changed_from_different = (phase_idx == 0 or phases[phase_idx - 1] != off)
            ref = em.reference_delay(stream, off, MAXLEN)
            if off < HEAD:
                # head-range: exact immediately, no arming at all
                lo, hi = b0 * em.BLOCK, b1 * em.BLOCK
                d = int(np.max(np.abs(got[lo:hi].astype(np.int64) -
                                       ref[lo:hi].astype(np.int64))))
                worst = max(worst, d)
                n_compared += hi - lo
            else:
                arm_lo, arm_hi = b0 * em.BLOCK, (b0 + 2) * em.BLOCK
                if changed_from_different:
                    arming_nonzero += int(np.sum(got[arm_lo:arm_hi] != 0))
                lo, hi = (b0 + 2) * em.BLOCK, b1 * em.BLOCK
                d = int(np.max(np.abs(got[lo:hi].astype(np.int64) -
                                       ref[lo:hi].astype(np.int64))))
                worst = max(worst, d)
                n_compared += hi - lo
            if verbose:
                print(f'  phase off={off} blocks[{b0}:{b1}): worst diff so far {worst}')
        completed = 1
    except Exception as e:
        if verbose:
            print(f'  offset-change run raised: {e!r}')

    check('offset-change: run completes without exception', completed, 1,
          'bool', lower_is_better=False)
    check('offset-change: arming blocks are exactly zero on every switch to tail',
          arming_nonzero, 0, 'samples')
    check('offset-change: head-range exact immediately; '
          'tail-range exact from 3rd block after switch', worst, 0, 'LSB')
    note_samples('4 offset change', n_compared)


# ---------------------------------------------------------------------------
# 5. BANDWIDTH
# ---------------------------------------------------------------------------

def t_bandwidth(verbose):
    """All 32 lines at offset 11999: worst-block bus busy fraction at
    100 MHz must stay below 0.35, the figure the design doc quotes."""
    HEAD = 960
    MAXLEN = 12000
    N_BLOCKS = 20
    n_lines = 32
    offsets_list = [11999] * n_lines

    rng = np.random.default_rng(50019)
    inputs, _streams = _rand_stream(rng, N_BLOCKS, n_lines, em.BLOCK)

    ram = em.HyperRamModel(em.SLOTS * n_lines * em.BLOCK, clk_mhz=100.0)
    pool = em.DelayPool(n_lines, HEAD, MAXLEN, 'extram', ram=ram)
    for b in range(N_BLOCKS):
        pool.process_block(b, inputs[b], offsets_list)

    ram.assert_no_overrun()
    fractions = [ram.busy_fraction(b) for b in range(N_BLOCKS)]
    worst = max(fractions)
    check('bandwidth: worst-block busy fraction @ 100 MHz, 32 lines @ off=11999',
          worst, 0.35, 'frac')
    note_samples('5 bandwidth', N_BLOCKS)
    if verbose:
        print(f'  busy fraction per block: '
              f'{[round(f, 4) for f in fractions]}')
        print(f'  worst {worst:.4f}, budget 0.35')


# ---------------------------------------------------------------------------
# 6. NEGATIVE CONTROL
# ---------------------------------------------------------------------------

def t_negative_control(verbose):
    """Corrupt one word of the simulated RAM mid-run and require the
    tail-range comparison to FAIL -- proving check 2's comparison is
    against real, independently-stored data, not against itself."""
    HEAD = 960
    MAXLEN = 12000
    N_BLOCKS = 100
    off = 1000
    n_lines = 1

    rng = np.random.default_rng(60019)
    inputs, streams = _rand_stream(rng, N_BLOCKS, n_lines, em.BLOCK)
    stream = streams[0]

    ram = em.HyperRamModel(em.SLOTS * n_lines * em.BLOCK)
    pool = em.DelayPool(n_lines, HEAD, MAXLEN, 'extram', ram=ram)

    out_all = np.zeros((N_BLOCKS, n_lines, em.BLOCK), dtype=np.int32)
    corrupted = False
    for b in range(N_BLOCKS):
        out_all[b] = pool.process_block(b, inputs[b], [off])
        if b == 0 and not corrupted:
            # Slot 0, line 0's row: written by block 0's flush. It will be
            # read back by the prefetch that serves block ~62 (q = 1000//16
            # = 62), well inside this run -- corrupt it now, after it is
            # written and before it is read.
            row_stride = n_lines * em.BLOCK
            ram.mem[0 * row_stride:0 * row_stride + em.BLOCK] = 0x7EADBEEF % (1 << 31)
            corrupted = True

    got = out_all[:, 0, :].reshape(-1)
    ref = em.reference_delay(stream, off, MAXLEN)
    skip = 2 * em.BLOCK
    n_mismatch = int(np.sum(got[skip:] != ref[skip:]))

    check('negative control: corrupted RAM word is detected as a mismatch',
          n_mismatch, 1, 'samples', lower_is_better=False)
    note_samples('6 negative control', len(ref) - skip)
    if verbose:
        print(f'  negative control: {n_mismatch} mismatching samples after corruption')


def main(argv):
    verbose = '-v' in argv
    for t in (t_head_range, t_tail_range, t_ring_wrap, t_offset_change,
              t_bandwidth, t_negative_control):
        t(verbose)

    print(f'{"test":68s} {"value":>12s} {"limit":>10s}  unit   result')
    fails = 0
    for name, value, limit, unit, ok in results:
        fails += (not ok)
        print(f'{name:68s} {value:12.6f} {limit:10.4f}  {unit:6s} '
              f'{"PASS" if ok else "FAIL"}')
    print(f'\n{len(results) - fails}/{len(results)} passed')

    print('\nsamples compared:')
    for name, n in sample_counts:
        print(f'  {name:32s} {n:8d}')

    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
