#!/usr/bin/env python3
"""dsp4_mtr_verify.py — the meter against its golden reference, on the part.

THE BAR (2026-08-28 ruling): golden-reference tests for the RMS window
and the peak against fixed_ref, NOT an A/B against the meter being
replaced. The old meter was wrong four ways, so agreeing with it would
have been the failure.

WHAT IS COMPARED, and it is the FIXED-POINT state, exactly:

    _mtr_st_<id>[0..3]  = pk64, ms64   (two 64-bit Q8.56 words)

against fixed_ref.meter_block driven with the same stimulus from a zero
state. Both are integer recurrences, so "close" is not a category: the
words either are the reference's or they are not.

The stimulus is DSP4_PROFILE_SIGNAL's square wave -- +/-0.5 Q4.28 written
into every sample of every block by the IN kernel -- which makes each
block identical and the recurrence's limit set small and exact:

    pk_blk = 0x08000000 (0.5)     every block
    ms_blk = 0x04000000 (0.25)    every block, and exactly, because the
                                  block mean is a shift when BLOCK is a
                                  power of two

The RMS window converges to a SINGLE fixed point, so its two words are
compared as one exact 64-bit integer.

The peak sits in a TWO-STATE limit cycle -- latch, decay, latch -- one
step per block, and the diag link reads one 32-bit word per transaction
at about a millisecond each. At BLOCK=8 a block is 167 us, so the two
halves of pk64 are necessarily read in different phases and the pair as
read is torn: the first run of this test returned lo from the decay state
and hi from the latch state and called it a mismatch. The peak is
therefore compared WORD-WISE -- every word read must be exactly one of
the reference's words for that half -- and each half is read several
times so that a word which is in neither state cannot slip through as a
single unlucky sample. Nothing here is a tolerance: the words are exact
reference integers or the test fails.

The float readback (peak, rms) is checked to a TOLERANCE, not bit-exactly,
and deliberately: the DSP takes its square root by RSQRTS plus three
Newton steps and the reference takes it in float64. The fixed-point state
is the contract; the float is the presentation.

NEGATIVE CONTROL, always run: the same comparison against a reference
built with the BLOCK-32 coefficients. It must FAIL. A test that cannot
tell the right time constant from a 4x-wrong one is not testing the thing
the third recorded meter defect was about.

usage:  dsp4_mtr_verify.py [meter_id]        (default C1_MTR_01)
needs:  a DSP4_BLOCK_KERNELS=1 DSP4_PROFILE_SIGNAL=1 image, booted and
        configured, with strip 1's GAIN at unity (run gainfix.py first).
"""
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
sys.path.insert(0, '.')
import dsp4_scope as S
import fixed_ref as F

try:
    from dsp4_block import BLOCK
except ImportError:
    BLOCK = 8

MTR = sys.argv[1] if len(sys.argv) > 1 else 'C1_MTR_01'
AMP = F.to_q(0.5)                      # what DSP4_PROFILE_SIGNAL injects
SETTLE_BLOCKS = 200000                 # >> 100 tau at any block size


def fl(v):
    return struct.unpack('<f', struct.pack('<I', (v or 0) & 0xFFFFFFFF))[0]


def s64(lo, hi):
    v = ((hi & 0xFFFFFFFF) << 32) | (lo & 0xFFFFFFFF)
    return v - (1 << 64) if v & (1 << 63) else v


def peek(sc, a):
    """Two consecutive agreeing reads. The diag link intermittently answers
    0xFFFFFFFF to a peek and one read cannot tell that from a value."""
    last = None
    for _ in range(24):
        try:
            v = sc.d.peek(a)
        except Exception:
            time.sleep(0.05)
            last = None
            continue
        if v == 0xFFFFFFFF:
            last = None
            time.sleep(0.03)
            continue
        if v == last:
            return v
        last = v
        time.sleep(0.03)
    return None


REPEATS = 5


def reference(block):
    """Settled states of the reference for this stimulus, at this block
    size. Returns (set of (pk64, ms64), (peak, rms) floats)."""
    alpha, beta = F.meter_coeffs(block)
    xs = [AMP if (i % 2 == 0) else -AMP for i in range(block)]
    st = F.meter_state()
    tail = []
    for i in range(SETTLE_BLOCKS):
        F.meter_block(xs, st, alpha, beta)
        if i >= SETTLE_BLOCKS - 4:
            tail.append((st[0], st[1]))
    states = set(tail)
    # The readback is taken in whichever phase the fold was in, so BOTH
    # settled states are legitimate answers -- 0.5 and 0.5 minus one decay
    # step differ by 1.25e-4 at BLOCK=8 and a test that admits only one of
    # them fails half the time for no reason.
    reads = [F.meter_readback(list(st)) for st in sorted(states)]
    return states, reads


def words(states, idx):
    """The set of 32-bit words the reference's settled states can show at
    one half of one 64-bit state word."""
    out = set()
    for st in states:
        v = st[0] if idx < 2 else st[1]
        out.add((v >> (32 * (idx % 2))) & 0xFFFFFFFF)
    return out


def main():
    sc = S.Scope(1)
    sc.check_chip()
    base = sc.sym['_mtr_st_%s' % MTR]

    reads = [[], [], [], []]
    for _ in range(REPEATS):
        for k in range(4):
            reads[k].append(peek(sc, base + k))
    pf = peek(sc, sc.sym['_mtr_peak_%s' % MTR])
    rf = peek(sc, sc.sym['_mtr_rms_%s' % MTR])
    if any(v is None for r in reads for v in r) or None in (pf, rf):
        print('UNREADABLE: the link did not give a stable answer')
        return 2

    states, rreads = reference(BLOCK)
    print('%s   (block=%d, %d reads per word)' % (MTR, BLOCK, REPEATS))
    print('  reference settled states:')
    for st in sorted(states):
        print('    pk64=%-22d ms64=%d' % (st[0], st[1]))
    print('  reference readback (either phase of the peak cycle):')
    for p, r in rreads:
        print('    peak=%.9g  rms=%.9g' % (p, r))

    # RMS: single fixed point, so the 64-bit word is compared whole.
    ms_ref = {st[1] for st in states}
    ok_ms = len(ms_ref) == 1 and all(
        s64(lo, hi) in ms_ref for lo, hi in zip(reads[2], reads[3]))
    print('  ms64 read %s -> %s'
          % (sorted({s64(lo, hi) for lo, hi in zip(reads[2], reads[3])}),
             'EXACT' if ok_ms else 'MISMATCH'))

    # Peak: two-state cycle, read word-wise (see the header).
    ok_pk = True
    for k, name in ((0, 'pk_lo'), (1, 'pk_hi')):
        want = words(states, k)
        got = sorted(set(reads[k]))
        good = all(v in want for v in reads[k])
        ok_pk = ok_pk and good
        print('  %s read %s  against %s -> %s'
              % (name, ['0x%08X' % v for v in got],
                 ['0x%08X' % v for v in sorted(want)],
                 'EXACT' if good else 'MISMATCH'))

    dp = min(abs(fl(pf) - p) / max(p, 1e-30) for p, _ in rreads)
    dr = min(abs(fl(rf) - r) / max(r, 1e-30) for _, r in rreads)
    ok_float = dp < 1e-6 and dr < 1e-6
    print('  float readback  peak=%.9g rms=%.9g  best relative error %.3e / %.3e'
          % (fl(pf), fl(rf), dp, dr))

    # Negative control: the other block size's coefficients must not match.
    other = 32 if BLOCK != 32 else 8
    nstates, _nr = reference(other)
    n_ms = {st[1] for st in nstates}
    n_lo, n_hi = words(nstates, 0), words(nstates, 1)
    neg_ok = not (
        all(s64(lo, hi) in n_ms for lo, hi in zip(reads[2], reads[3]))
        and all(v in n_lo for v in reads[0])
        and all(v in n_hi for v in reads[1]))
    print('  negative control (BLOCK=%d coefficients): %s'
          % (other, 'correctly rejected' if neg_ok else 'ALSO MATCHED'))

    if ok_ms and ok_pk and ok_float and neg_ok:
        print('METER_BIT_EXACT')
        return 0
    print('METER_MISMATCH: ms=%s peak=%s float=%s negctl=%s'
          % (ok_ms, ok_pk, ok_float, neg_ok))
    return 1


if __name__ == '__main__':
    sys.exit(main())
