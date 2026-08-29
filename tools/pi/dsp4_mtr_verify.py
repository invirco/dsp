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

    pk_blk = 0x08000000 (0.5)     every block, Q4.28 after the fold's
                                  Q8.24 -> Q4.28 conversion
    ms_blk = 0x04000000 (0.25)    every block, and exactly, because the
                                  block mean is a shift when BLOCK is a
                                  power of two

The wide-word ruling does NOT move these numbers at unity gain and half
scale -- Q8.24 0.5 squared and meaned is Q4.28 0.25 either way -- which is
exactly why this test cannot tell the two formats apart on its own and why
the OVER-RANGE control below exists.

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

NEGATIVE CONTROL 1, always run: the same comparison against a reference
built with the BLOCK-32 coefficients. It must FAIL. A test that cannot
tell the right time constant from a 4x-wrong one is not testing the thing
the third recorded meter defect was about.

NEGATIVE CONTROL 2 -- THE WIDE-WORD CONTROL (PW ruling 2026-08-29) -- and
why it needs a second operating point. At unity gain the wide Q8.24 word
and the retired rounded Q4.28 store carry the SAME value, so the primary
comparison above cannot tell the ruling's arithmetic from the arithmetic
it replaced. At a gain whose product has nonzero low bits they diverge
exactly: the meter now sees floor((x*g) / 2^32) and used to see
sat32(rns(x*g, 28)). This test therefore moves strip 1's GAIN to
one of WIDE_CTL_GAINS, re-settles, and requires BOTH:

    the part matches the WIDE model exactly, and
    the part does NOT match the NARROW (pre-ruling) model,

with the narrow model computed here rather than in fixed_ref, because the
narrow form is retired and a normative module should not carry it.

usage:  dsp4_mtr_verify.py [meter_id] [--no-wide-control]
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

ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
FLAGS = {a for a in sys.argv[1:] if a.startswith('--')}
MTR = ARGS[0] if ARGS else 'C1_MTR_01'
WIDE_CTL_GAINS = (0.497, 0.493, 0.489, 0.3, 0.7, 0.31)   # see separates()
GAIN_SPI_ADDR = 0x0000       # strip 1's GAIN, dsp.csv spi_addr
WIDE_CTL_SETTLE = 30.0       # >> the 1.333 s peak decay and 0.3 s window
# WHAT THE METER SEES (PW ruling 2026-08-29, wide-word metering). The
# stimulus is still +/-0.5 at the input, but the meter no longer reads a
# stored Q4.28 block: it reads the MS word of GAIN's product, which at unity
# gain is the same value in Q8.24. fixed_ref.meter_block takes Q8.24, so the
# stimulus is converted once, here, and NOT by scaling the answer.
AMP = F.to_q(0.5, F.QM)                # what the meter sees, Q8.24
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


def narrow_meter_block(xs, state, alpha_q, beta_q):
    """The RETIRED pre-ruling meter: Q4.28 samples out of a rounded,
    saturated store, mean-square shift 28 + log2(BLOCK), no peak format
    conversion. Kept HERE and not in fixed_ref because it is the thing the
    ruling replaced -- the normative module carries one meter."""
    block = len(xs)
    shift = block.bit_length() - 1
    hi, lo = max(xs), min(xs)
    pk_blk = F.sat32(hi if hi > -lo else -lo)
    ssq = sum(x * x for x in xs)
    ms_blk = F.sat32(ssq >> (F.QS + shift))
    ms_q = state[1] >> F.QS
    state[1] += alpha_q * (ms_blk - ms_q)
    pk_q = state[0] >> F.QS
    if pk_blk > pk_q:
        state[0] = pk_blk << F.QS
    else:
        state[0] -= beta_q * pk_q
    return pk_blk, ms_blk


def settled(block, xs, fn):
    """The settled state set of a meter recurrence under a fixed block."""
    alpha, beta = F.meter_coeffs(block)
    st = F.meter_state()
    tail = []
    for i in range(SETTLE_BLOCKS):
        fn(xs, st, alpha, beta)
        if i >= SETTLE_BLOCKS - 4:
            tail.append((st[0], st[1]))
    return set(tail)


def stim_wide(gq):
    """What the WIDE meter sees for the +/-0.5 stimulus at Q4.28 gain gq:
    the MS 32-bit word of x*g, which is an arithmetic (floor) shift of 32
    on the exact product."""
    amp = F.to_q(0.5)
    return [((amp if (i % 2 == 0) else -amp) * gq) >> 32 for i in range(BLOCK)]


def stim_narrow(gq):
    """What the RETIRED meter saw: the rounded, saturated Q4.28 store."""
    amp = F.to_q(0.5)
    return [F.sat32(F.rns((amp if (i % 2 == 0) else -amp) * gq, F.QS))
            for i in range(BLOCK)]


def words(states, idx):
    """The set of 32-bit words the reference's settled states can show at
    one half of one 64-bit state word."""
    out = set()
    for st in states:
        v = st[0] if idx < 2 else st[1]
        out.add((v >> (32 * (idx % 2))) & 0xFFFFFFFF)
    return out


def wide_control(sc, base):
    """THE WIDE-WORD CONTROL (PW ruling 2026-08-29).

    At unity gain the wide Q8.24 word and the retired rounded Q4.28 store
    carry the same value, so the primary comparison above cannot tell the
    ruling's arithmetic from the arithmetic it replaced. Move the gain to a
    point where they diverge and the two are separated exactly.

    THE GAIN IS READ BACK, NOT PREDICTED. The Q4.28 shadow comes from a
    float multiply and a `fix` inside the part, and reproducing that here
    would be a guess about a rounding mode; _gain_q_<node> is a DM symbol,
    so the models are driven with the coefficient the part is ACTUALLY
    using and the control tests the meter rather than the conversion.

    WHAT IS COMPARED, and it is not the 64-bit state. The one-pole's
    integer fixed point is an INTERVAL -- it stops when ms_blk == state>>28
    and where in that interval it stops depends on the trajectory -- so a
    state settled from unity down to 0.6 is not the state settled from
    zero, and comparing whole words here would fail for a reason that has
    nothing to do with the format. The block quantities ms_blk = ms64>>28
    and pk_blk = max(pk64>>28) ARE path-independent once settled, and they
    are exact integers, so the verdict stays exact.
    """
    from dsp4_tubedly_probe import wrv, f32
    import re as _re
    m = _re.match(r'^C1_MTR_(\d+)$', MTR)
    if not m:
        print('  wide-word control: SKIPPED -- only the chip-1 strip meters '
              'have a GAIN this test can move (%s)' % MTR)
        return True
    gsym = '_gain_q_C1_GAIN_%s' % m.group(1)
    if gsym not in sc.sym:
        print('  wide-word control: SKIPPED -- %s not in this build' % gsym)
        return True
    gaddr = sc.sym[gsym]
    spi = GAIN_SPI_ADDR + (int(m.group(1)) - 1) * 144

    gq = None
    for cand in WIDE_CTL_GAINS:
        try:
            wrv(sc, spi, f32(cand), ramp_id=1, settle=0.05)
        except Exception as e:
            print('  wide-word control: gain write failed (%s)' % e)
            return False
        time.sleep(1.0)
        g = peek(sc, gaddr)
        if g is None:
            continue
        if g & 0x80000000:
            g -= 1 << 32
        if separates(g):
            gq = g
            print('  wide-word control: GAIN -> %.4f, part converted it to '
                  '0x%08X' % (cand, g & 0xFFFFFFFF))
            break
        print('  wide-word control: gain %.4f gave q=0x%08X, which the two '
              'forms agree on -- trying the next' % (cand, g & 0xFFFFFFFF))
    if gq is None:
        print('  wide-word control: no candidate gain separated the forms')
        restore_gain(sc, spi)
        return False

    xs_w, xs_n = stim_wide(gq), stim_narrow(gq)
    pk_w, ms_w = blk_wide(xs_w)
    pk_n, ms_n = blk_narrow(xs_n)
    print('    the meter should see %s, not %s'
          % (['0x%08X' % (x & 0xFFFFFFFF) for x in xs_w[:2]],
             ['0x%08X' % (x & 0xFFFFFFFF) for x in xs_n[:2]]))
    print('    wide model   pk_blk=%d (>>4 %d) ms_blk=%d'
          % (pk_w, pk_w >> 4, ms_w))
    print('    narrow model pk_blk=%d (>>4 %d) ms_blk=%d'
          % (pk_n, pk_n >> 4, ms_n))

    time.sleep(WIDE_CTL_SETTLE)
    reads = [[], [], [], []]
    for _ in range(REPEATS):
        for k in range(4):
            reads[k].append(peek(sc, base + k))
    restore_gain(sc, spi)
    if any(v is None for r in reads for v in r):
        print('  wide-word control: UNREADABLE')
        return False

    # The PEAK is read as its HIGH WORD ALONE, which is pk_blk >> 4 in the
    # latch phase and less in the decay phase, so the maximum over the
    # reads is the latch value exactly. Pairing it with pk_lo would be a
    # torn read -- the two halves are necessarily sampled in different
    # phases of the two-state cycle, which is the same trap the primary
    # comparison documents, and it moves the result by up to 15.
    ms_got = {s64(lo, hi) >> 28 for lo, hi in zip(reads[2], reads[3])}
    pk_got = max(reads[1])
    print('    part  pk_blk>>4=%d ms_blk=%s' % (pk_got, sorted(ms_got)))
    ok_w = (pk_got == pk_w >> 4) and ms_got == {ms_w}
    hit_n = (pk_got == pk_n >> 4) and ms_got == {ms_n}
    print('    against the WIDE model:   %s' % ('MATCH' if ok_w else 'MISS'))
    print('    against the NARROW model: %s'
          % ('ALSO MATCHED -- the control did not fire' if hit_n
             else 'correctly rejected'))
    return ok_w and not hit_n


def restore_gain(sc, spi):
    from dsp4_tubedly_probe import wrv, f32
    try:
        wrv(sc, spi, f32(1.0), ramp_id=1, settle=0.05)
    except Exception:
        pass


def separates(gq):
    """Do the two forms disagree at this coefficient? They agree exactly
    when the rounded Q4.28 store and the wide word left-shifted by four are
    the same number, which happens whenever the product's low bits are
    already zero -- unity is the obvious case and it is why this control
    needs its own operating point."""
    xw, xn = stim_wide(gq), stim_narrow(gq)
    if [x << (F.QS - F.QM) for x in xw] == xn:
        return False
    (pw, mw), (pn, mn) = blk_wide(xw), blk_narrow(xn)
    return (pw >> 4) != (pn >> 4) and mw != mn


def blk_wide(xs):
    """(pk_blk, ms_blk) in Q4.28 from Q8.24 samples -- fixed_ref's fold."""
    shift = len(xs).bit_length() - 1
    hi, lo = max(xs), min(xs)
    pk = F.sat32(hi if hi > -lo else -lo)
    pk = min(pk, (1 << (F.QM + 3)) - 1) << (F.QS - F.QM)
    return pk, F.sat32(sum(x * x for x in xs) >> (2 * F.QM - F.QS + shift))


def blk_narrow(xs):
    """(pk_blk, ms_blk) the RETIRED meter would have produced."""
    shift = len(xs).bit_length() - 1
    hi, lo = max(xs), min(xs)
    pk = F.sat32(hi if hi > -lo else -lo)
    return pk, F.sat32(sum(x * x for x in xs) >> (F.QS + shift))


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

    wide_ok = True
    if '--no-wide-control' not in FLAGS:
        wide_ok = wide_control(sc, base)

    if ok_ms and ok_pk and ok_float and neg_ok and wide_ok:
        print('METER_BIT_EXACT')
        return 0
    print('METER_MISMATCH: ms=%s peak=%s float=%s negctl=%s widectl=%s'
          % (ok_ms, ok_pk, ok_float, neg_ok, wide_ok))
    return 1


if __name__ == '__main__':
    sys.exit(main())
