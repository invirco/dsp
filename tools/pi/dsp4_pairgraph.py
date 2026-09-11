#!/usr/bin/env python3
"""dsp4_pairgraph.py — is the PAIRED GRAPH bit-exact against the scalar one?

The paired dynamics KERNELS were proved bit-exact in isolation (963f181,
dyn_selftest). That is not this question. Wiring the GRAPH for pairing
changes the chain order, splits the block pool in two, hands each pair's
two channels to one instruction stream, and gives sample 0 back to the
scalar per-sample body for its block-rate parameter conversion. Every one
of those can be wrong while the kernel is right.

So this measures the graph. It drives a known step into one strip of a
pair, mutes the other, and captures 1024 consecutive samples of the MAIN
BUS from inside the DSP. The comparison is between two BUILDS of the same
graph -- DSP4_SIMD_DYN=0 and =1 -- and the bar is that all 1024 words
match, word for word.

WHY THE BUS AND NOT A POOL SLOT. Under pairing the odd strip of a pair
lives in a second pool, so "strip 1's chain slot" is a different address in
the two builds and comparing those would be comparing two different things.
The bus is where both builds must agree by construction: it is the sum of
every strip's router output and it is the same symbol either way.

WHY ONE LANE DRIVEN AND ONE MUTED, and this is the point of the test. It
puts the pair's two lanes in OPPOSITE arms of every predicated branch in
the dynamics -- the driven lane's gate open and its compressor down on the
knee, the muted lane's gate closing into hold and its compressor on the
unity path -- with different thresholds, attacks, releases, ratios and hold
times on the two strips as well. A pair that quietly computes ONE channel
twice, which is exactly what DSP4_SIMD_NEGCTL builds on purpose, cannot
produce the same bus sum. Run it for both strips of the pair in turn so
neither lane is only ever the silent one.

ONE CAPTURE PER BOOT, and the tool enforces it (S23-1). The first capture
of a boot carries no dynamics history and every later one does, so the two
are different measurements -- and every golden in goldens/ is a first
capture. A second capture on the same boot is REFUSED unless the caller
passes --force (a bar that compares within one boot and carries its own
control) or --settle (a throwaway capture first, so the history term is
settled; stamped, and not comparable with the stored goldens).

Usage:
    dsp4_pairgraph.py [--strip N] [--out FILE] [--settle|--force]

Writes the captured words to FILE and prints a one-line digest. Run it
against both builds and diff the files with --compare.
"""
import argparse
import hashlib
import json
import os
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
from dsp4_block import BLOCK
from dsp4_tubedly_probe import wrv

# SPI parameter offsets inside a strip's page, and the per-strip stride.
# The same numbers chain.py and gainfix.py use, from dsp.csv's spi_addr.
STRIDE = 144
GAIN = 0x0000
# Order on the page is On, Thr, Att, HOLD, Rel -- checked against
# dsp_address_map.md rather than assumed sequential, because a guessed
# offset writes a real parameter and the probe would still "pass".
GATE_ON, GATE_THR, GATE_ATT, GATE_HOLD, GATE_REL = (
    0x0028, 0x0029, 0x002A, 0x002B, 0x002C)
COMP_ON, COMP_THR, COMP_RATIO, COMP_ATT, COMP_REL = (
    0x0038, 0x0039, 0x003A, 0x003B, 0x003C)
TUBE_ON = 0x004C
# FILT and EQ take FLOAT RBJ coefficient words on the wire and convert to
# the Q4.28 offset form themselves (dsp4_eq_probe.py, review finding D51).
HPF_COEFF0, HPF_SWAP = 0x0004, 0x0009
LPF_COEFF0, LPF_SWAP = 0x000A, 0x000F
EQ_COEFF0, EQ_SWAP = 0x0010, 0x0024
DLY_OFF = 0x004E
FDR_LEVEL, FDR_PAN, FDR_MUTE = 0x0050, 0x0051, 0x0052
FDR_RESERVED = 0x0053            # was Dca; host-managed since 2026-08-30

AMP = 0x08000000                       # -6 dBFS in Q4.28, the injected step

# Deliberately unequal between the two strips of a pair, so a pair that
# computes one channel twice cannot land on the same answer as one that
# computes two.
PARAMS = {
    'odd':  dict(gate_thr=-30.0, gate_att=0.25, gate_rel=0.01,
                 comp_thr=-20.0, comp_ratio=4.0, comp_att=0.01, comp_rel=0.001),
    'even': dict(gate_thr=-45.0, gate_att=0.50, gate_rel=0.005,
                 comp_thr=-30.0, comp_ratio=2.0, comp_att=0.02, comp_rel=0.004),
}


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def rbj_peak(f0, q, gain_db, fs=48000.0):
    """One RBJ peaking section, normalised to a0. Enough of a design to
    put a NON-BYPASS filter in the cascade, which is the whole point: with
    bypass coefficients the paired and scalar cascades are bit-identical BY
    CONSTRUCTION and the comparison proves nothing about the pairing. That
    is exactly why the session-3 bus golden reproduced with no biquad
    coefficient coverage at all."""
    import math
    a = 10.0 ** (gain_db / 40.0)
    w = 2.0 * math.pi * f0 / fs
    al = math.sin(w) / (2.0 * q)
    b0, b1, b2 = 1 + al * a, -2 * math.cos(w), 1 - al * a
    a0, a1, a2 = 1 + al / a, -2 * math.cos(w), 1 - al / a
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def load_biquads(sc, strip, seed):
    """Put a real, strip-specific filter in FILT and EQ.

    The two strips of a pair get DIFFERENT designs on purpose, for the same
    reason their dynamics parameters differ: a pair that computes one
    channel twice has to be unable to land on the right bus sum.
    """
    b = (strip - 1) * STRIDE
    for base, swap, (f0, q, g) in (
            (HPF_COEFF0, HPF_SWAP, (60.0 + 25.0 * seed, 0.9, 4.0 + seed)),
            (LPF_COEFF0, LPF_SWAP, (7000.0 - 1500.0 * seed, 0.8, -3.0 - seed))):
        for k, c in enumerate(rbj_peak(f0, q, g)):
            sc.d.write(b + base + k, f32(c))
            time.sleep(S.SETTLE)
        sc.d.write(b + swap, 1)
        time.sleep(S.SETTLE)
    for band in range(4):
        f0 = 200.0 * (band + 1) * (1.0 + 0.3 * seed)
        for k, c in enumerate(rbj_peak(f0, 1.1 + 0.4 * band, 6.0 - 2.0 * band
                                       + seed)):
            sc.d.write(b + EQ_COEFF0 + band * 5 + k, f32(c))
            time.sleep(S.SETTLE)
    sc.d.write(b + EQ_SWAP, 1)
    time.sleep(S.SETTLE)


def configure(sc, strip, loud, gain=1.0, dly=0):
    """Put one strip in a known state. Nothing is assumed: a probe that
    sets only what it thinks changed measures whatever the last boot left
    behind, which is how a dead strip reads as a cheap one.

    `gain` is the driven strip's GAIN, and it is a parameter because the
    default of 1.0 makes this harness BLIND TO ROUNDING. GAIN computes
    sat(rns(x*g, 28)); at g = 1.0 the Q4.28 word is 2^28 exactly, so every
    product's low 28 bits are zero and the rounding half never changes an
    answer. A kernel that dropped the round entirely reproduces the golden
    word for word -- which is exactly what happened to the first cut of the
    SIMD gain kernel on 2026-09-02. Pass a value with bits under the round
    (gainsimd.sh uses 0.70710678, Q4.28 0x0B504F33) when the thing under
    test IS the rounding."""
    b = (strip - 1) * STRIDE
    p = PARAMS['odd' if strip % 2 else 'even']
    wrv(sc, b + GAIN, f32(gain if loud else 0.0), ramp_id=1, settle=0.05)
    for addr, val in ((b + GATE_ON, 1), (b + COMP_ON, 1), (b + TUBE_ON, 0),
                      (b + FDR_MUTE, 0), (b + DLY_OFF, dly),
                      (b + GATE_THR, f32(p['gate_thr'])),
                      (b + GATE_ATT, f32(p['gate_att'])),
                      (b + GATE_REL, f32(p['gate_rel'])),
                      (b + COMP_THR, f32(p['comp_thr'])),
                      (b + COMP_RATIO, f32(p['comp_ratio'])),
                      (b + COMP_ATT, f32(p['comp_att'])),
                      (b + COMP_REL, f32(p['comp_rel']))):
        sc.d.write(addr, val)
        time.sleep(S.SETTLE)
    # The DCA write is GONE. 0x0053 was the DCA cell -- a linear gain
    # until D57 and a stored assignment after it -- and PW's 2026-08-30
    # ruling makes `Dca` host-managed, so the address is now RESERVED and
    # a write to it is an SPI error rather than a no-op. Dropping it
    # cannot move the capture: the cell reached no audio either way, which
    # was measured on the part the same day (0 of 32 bus words differ
    # between DCA 0 and DCA 1.0).
    for addr, val in ((b + FDR_LEVEL, 1.0), (b + FDR_PAN, 0.5)):
        wrv(sc, addr, f32(val), ramp_id=1, settle=0.05)


# THE MATRIX SENDS' SPI BLOCK IS NOT ON THE STRIP'S PAGE, and that is the
# whole of S22-4: the routing block is sixty words and growing it to
# sixty-four would have moved every chip-1 address above channel 1's
# router, so the matrix sends were allocated after every other chip-1
# address. Four words per channel, On[1-2] then Send[1-2].
MTX_ON, MTX_SEND, MTX_STRIDE = 0x12C6, 0x12C8, 4
# Inside the sixty-word routing block: MainOn, CtrOn, GrpOn[4], AuxOn[12],
# AuxSend[12], AuxPick[12], FxOn[6], FxSend[6], FxPick[6].
MAIN_ON = 0x0054
AUX_ON, AUX_SEND = 0x005A, 0x0066

# WHICH ONE CROSSPOINT IS LEFT LIVE, and the bus it feeds. `main` is the
# arm every stored golden was taken with. The rest exist for the S23 gate-1
# vector: the dense crosspoint path is ONE path, so a channel sent at unity
# into aux 1, matrix 1 and matrix 2 must produce THE SAME BUS SUM in all
# three -- same source block, same Q4.28 coefficient of exactly 2^28, same
# exact 80-bit accumulate, read out with the same rns+saturate. Any
# difference is a bus row indexed wrong, a coefficient stride slipped, or
# one accumulator aliasing another; a tolerance would hide all three, so
# the bar is word-for-word.
CROSSPOINTS = {
    'main': ('_buf_C1_BUS_MAIN_L', None),
    'aux1': ('_buf_C1_BUS_AUX_01', (AUX_ON, AUX_SEND)),
    'mtx1': ('_buf_C1_BUS_MTX_01', (MTX_ON, MTX_SEND)),
    'mtx2': ('_buf_C1_BUS_MTX_02', (MTX_ON + 1, MTX_SEND + 1)),
}


def set_crosspoint(sc, strip, kind, on=True):
    """Leave exactly one of the strip's crosspoints live.

    MainOn is taken off for everything but `main`, because a strip that is
    still assigned to the main bus proves nothing about the bus under test
    -- and because the point of the vector is that the OTHER bus carries
    the same sum, which needs the sources to be identical and not merely
    similar.

    `on=False` is the negative control and it writes the ASSIGN bit only:
    the send level is left where it is, so a bus that still carries
    anything is carrying it through a coefficient the assign bit failed to
    zero, which is the one failure this can have.
    """
    b = (strip - 1) * STRIDE
    spec = CROSSPOINTS[kind][1]
    if spec is None:
        sc.d.write(b + MAIN_ON, 1)
        time.sleep(S.SETTLE)
        return
    on_addr, send_addr = spec
    if on_addr >= MTX_ON:                       # the matrix block, not the page
        on_addr += (strip - 1) * MTX_STRIDE
        send_addr += (strip - 1) * MTX_STRIDE
    else:
        on_addr += b
        send_addr += b
    sc.d.write(b + MAIN_ON, 0)
    time.sleep(S.SETTLE)
    # UNITY IS 1.0 AND NOT 0.0 dB. `_rtg_<kind>_send_` is a LINEAR gain --
    # the send-ramp prep multiplies it by 2^28 and FIXes the result into
    # the crosspoint coefficient. The cell's `dB:` table is the surface
    # mapping and the SPI handler applies no conversion to it (0 of 2,168
    # chip-2 and 0 of the chip-1 addresses carry one), so writing 0.0 here
    # asks for silence. S22's matrix probe lost a run to this.
    wrv(sc, send_addr, f32(1.0), ramp_id=1, settle=0.05)
    sc.d.write(on_addr, 1 if on else 0)
    time.sleep(0.3)

def inject_addr(sc, strip):
    """Where the step goes: the driven strip's own chain slot.

    _scope_inject_blk drops a block-long step into whatever address the
    host names, once per block, straight after the first node in the chain.
    Under pairing the ODD strip of each pair is on the second pool, so the
    address of "strip N's chain slot" is a build-dependent fact -- and the
    SYMBOL TABLE is what settles it. _blk_pool1 exists only in a
    paired-graph build, so one lookup answers both "is this that build"
    and "where does the odd strip's chain live".
    """
    if strip % 2 and '_blk_pool1' in sc.sym:
        return sc.sym['_blk_pool1']
    return sc.sym['_blk_pool']


def capture(sc, inj, src, n):
    """The buffer holds 1024 samples but reading it back is two link
    transactions per word, so the default reads the first N. Eight blocks
    is already past the gate's hold and well into the compressor's release,
    which is where the two lanes are furthest apart."""
    sc.arm(src, inj, AMP, 2)                   # mode 2 = step
    if not sc.wait():
        raise SystemExit('scope never disarmed — the sample loop is not turning')
    return sc.fetch(min(n, S.SCOPE_MAX))


# ---------------------------------------------------------------------------
# WHERE A CAPTURE SITS IN ITS BOOT, AND WHY THE TOOL HAS TO KNOW (S23-1)
# ---------------------------------------------------------------------------
#
# The FIRST capture of a boot is not the same measurement as the second.
# S23-1 measured it: aux 1 taken first and aux 1 taken last on one boot
# differ in 235 of 256 words, first at word 21, maxdiff 1,412 LSB -- while
# `aux1b`, `mtx1` and `mtx2`, three captures of three DIFFERENT buses taken
# later on that same boot, are byte for byte identical. The odd one out is
# the first capture, and the term is the strip's own dynamics history: a
# capture is 256 samples from the arm, and the gate and the compressor are
# wherever the PREVIOUS capture's step injection left their envelopes. On
# the first capture of a boot there is no previous injection.
#
# Every stored golden in `goldens/` was taken as the first capture of its
# boot, and `busgold.sh`, `ctlgate.sh`, `bqgraph.sh` and `gainsimd.sh` are
# valid today for one reason only: they take ONE capture per boot, so both
# sides of the comparison carry the same history term and it cancels. That
# rule lived in a finding and in nothing the tool could enforce -- and the
# run scripts BREAK it by accident, because `pairgraph_run.sh` retries a
# failed capture up to four times on the same boot and compares whichever
# attempt succeeds against a golden taken as a first capture.
#
# So the rule is in the tool now. A capture knows its own index within the
# boot, stamps it into the JSON, and REFUSES to be the second capture of a
# boot unless the caller says which of the two comparable regimes it wants:
#
#   --force    take it anyway. For a bar that compares captures WITHIN one
#              boot and carries its own control -- mtxgold.sh is the one,
#              and its `aux1b` arm is precisely S23-1's measurement.
#   --settle   take a throwaway capture FIRST and measure the second, so
#              the capture carries a settled history term whatever its
#              position in the boot. This is the forward path: it makes the
#              first capture of a boot comparable instead of documenting
#              that it is not. It is NOT the default and it is STAMPED,
#              because a settled capture and an unsettled golden are two
#              different measurements and compare() must be able to say so.
#
# BOOT IDENTITY is DIAG_FRAME_COUNT, which counts blocks from zero at every
# DSP boot: a value BELOW the last one this ledger saw is a new boot. The
# counter wraps after ~8.3 days of continuous running, which would read as
# a new boot and let a second capture through -- the pre-existing
# behaviour, not a new failure mode, and the bench boots per arm anyway.
# The same is true of anything that strobes DIAG_CLEAR (dsp4_capacity.py
# does, between rows): if that also zeroes the frame counter the guard
# reads a new boot and PERMITS. Every way this witness can be wrong makes
# the tool behave as it did before the guard existed, never stricter than
# the evidence, which is the only direction an instrument guard may fail
# in -- it must not be able to fail a bar that is sound.
DIAG_FRAME_COUNT = 0xE004
LEDGER = os.environ.get('PAIRGRAPH_BOOT_LEDGER',
                        '/tmp/dsp4_pairgraph_boot.json')


def read_frames(sc, tries=16):
    """DIAG_FRAME_COUNT, read the way a COUNTING register has to be.

    `Scope.rd` is a VOTED reader: it asks until one value comes back
    twice. A free-running counter never repeats -- it advances about
    eight counts between two asks at 3,000 blocks/s -- so the voted
    reader reports a healthy part as an unsettled register, which is
    exactly what it did on the first bench run of this guard
    (`register 0xE004 never settled: {0x9c13: 1, 0x9c1a: 1, ...}` --
    twelve distinct, monotonically increasing values, i.e. twelve
    correct readings rejected for not being identical).

    So: single unvoted asks, and the sanity check is MONOTONICITY
    rather than repetition -- three asks that do not go backwards, none
    of them zero, since a dropped answer on this link reads as zero.
    This is dsp4_capacity.moving()'s rule and is the same rule for the
    same reason; it is duplicated rather than imported because
    dsp4_capacity pulls in the whole capacity instrument.
    """
    last, seen = None, []
    for _ in range(tries):
        v = sc._ask(DIAG_FRAME_COUNT)
        if not v:
            continue
        if last is not None and v < last:
            seen = []
        else:
            seen.append(v)
        last = v
        if len(seen) >= 3:
            return seen[-1]
    return None


def boot_capture_index(sc, ledger=LEDGER):
    """1 for the first capture of this DSP boot, 2 for the next, ...

    Returns None if the frame counter could not be read: an instrument
    guard that cannot read its witness says so and stands aside rather
    than failing a bar, and the capture is stamped with a null index so
    compare() knows it was never guarded.
    """
    try:
        frames = read_frames(sc)
    except (Exception, SystemExit) as exc:     # dsp4_scope raises BOTH
        frames = None
        print('  WARNING: DIAG_FRAME_COUNT raised (%s)' % exc)
    if not frames:
        print('  WARNING: DIAG_FRAME_COUNT unreadable -- this capture '
              'carries NO boot-position stamp and the S23-1 guard is not '
              'applied to it')
        return None
    prev = {}
    try:
        prev = json.load(open(ledger))
    except Exception:                          # noqa: BLE001 — absent is fine
        prev = {}
    if not isinstance(prev, dict) or frames < prev.get('frames', -1):
        prev = {'count': 0}
    idx = int(prev.get('count', 0)) + 1
    try:
        json.dump({'frames': frames, 'count': idx}, open(ledger, 'w'))
    except Exception as exc:                   # noqa: BLE001
        print('  WARNING: could not write the boot ledger %s (%s)'
              % (ledger, exc))
    return idx


def compare(a, b):
    # A comparison between two captures that were taken from the SAME
    # wiring is not a test of the wiring. Say so rather than printing a
    # clean verdict that means nothing.
    for k in ('paired_build', 'bq_paired_build', 'bq'):
        if a.get(k) is not None and a.get(k) == b.get(k) and k != 'bq':
            print('  note: both captures have %s=%s' % (k, a.get(k)))
    if a.get('bq') is False or b.get('bq') is False:
        print('  WARNING: at least one capture was taken with BYPASS '
              'biquads, which are bit-identical paired or not -- this '
              'comparison says nothing about the paired biquads')
    # The same rule applied to the GAIN kernel's rounding. Older captures
    # carry no 'gain' key at all and were taken at unity, so a missing key
    # is treated as 1.0 rather than as unknown.
    ga, gb = a.get('gain', 1.0), b.get('gain', 1.0)
    if ga != gb:
        print('  WARNING: the two captures were taken at DIFFERENT gains '
              '(%r vs %r) -- they are not comparable' % (ga, gb))
    elif ga == 1.0:
        print('  WARNING: both captures were taken at UNITY gain, whose '
              'Q4.28 word is 2^28 exactly -- every product\'s low 28 bits '
              'are zero, so this comparison says nothing about GAIN\'s '
              'rounding, and its products cannot saturate either')
    # WHERE EACH SIDE SAT IN ITS BOOT (S23-1). Two captures are only
    # comparable word for word if their dynamics history term is the same,
    # and there are exactly two ways for that to be true: both are the
    # FIRST capture of their boot (every stored golden is, and that is the
    # rule the one-capture-per-boot bars keep), or both are SETTLED. A
    # capture with no stamp at all is an older file or one taken through
    # an unreadable frame counter; say which rather than assuming either.
    sa, sb = bool(a.get('settled')), bool(b.get('settled'))
    ia, ib = a.get('boot_capture_index'), b.get('boot_capture_index')
    if sa != sb:
        print('  WARNING: one capture is SETTLED and the other is not '
              '(%s vs %s) -- they carry different dynamics history and a '
              'word-for-word verdict between them is not a bit-exactness '
              'claim (S23-1)' % (sa, sb))
    elif not sa:
        for who, i in (('a', ia), ('b', ib)):
            if i is None:
                print('  note: capture %s carries no boot-position stamp; '
                      'if it was not the first capture of its boot this '
                      'comparison straddles the S23-1 term' % who)
            elif i > 1:
                print('  WARNING: capture %s was #%d of its boot, not the '
                      'first, and is not settled -- against a first '
                      'capture this comparison straddles the S23-1 '
                      'dynamics-history term (up to 1,412 LSB)' % (who, i))

    wa, wb = a['words'], b['words']
    n = min(len(wa), len(wb))
    diffs = [(i, wa[i], wb[i]) for i in range(n) if wa[i] != wb[i]]
    print('%s vs %s: %d of %d words differ'
          % (a.get('tag', '?'), b.get('tag', '?'), len(diffs), n))
    if diffs:
        i, x, y = diffs[0]
        md = max(abs((x - (1 << 32) if x & 0x80000000 else x)
                     - (y - (1 << 32) if y & 0x80000000 else y))
                 for _, x, y in diffs)
        print('  first=%d  0x%08X vs 0x%08X  maxdiff=%d' % (i, x, y, md))
    print('GRAPH %s' % ('BIT-EXACT' if not diffs else 'DIFFERS'))
    return 1 if diffs else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strip', type=int, default=1,
                    help='which strip of the pair is driven (1-based)')
    ap.add_argument('--out', default='pairgraph.json')
    ap.add_argument('--tag', default='')
    ap.add_argument('-n', type=int, default=64,
                    help='samples to read back (2 link transactions each)')
    ap.add_argument('--bq', action='store_true',
                    help='load real FILT and EQ coefficients first -- '
                         'REQUIRED for any verdict about the paired biquads')
    ap.add_argument('--gain', type=float, default=1.0,
                    help='the driven strip\'s GAIN (default 1.0, which is '
                         'EXACT in Q4.28 and therefore blind to the '
                         'kernel\'s rounding -- see configure())')
    ap.add_argument('--dly', type=int, default=0,
                    help='DlyOff (samples) on BOTH strips. Default 0, which '
                         'is what every stored golden was taken with. A '
                         'non-zero value under BLOCK is the case the delay '
                         'line\'s two-pass form (DSP4_DLY_SPLIT) has to be '
                         'proved on: the block\'s reads then land INSIDE '
                         'the block\'s own writes, partially.')
    ap.add_argument('--xp', default='main', choices=sorted(CROSSPOINTS),
                    help='which crosspoint is left live, and therefore '
                         'which bus is captured (default main, the arm '
                         'every stored golden was taken with)')
    ap.add_argument('--xp-off', action='store_true',
                    help='the negative control for --xp: write the assign '
                         'bit to 0 and leave the send level alone. The bus '
                         'must then read exactly zero.')
    ap.add_argument('--compare', nargs=2, metavar='FILE',
                    help='compare two captures instead of taking one')
    # S23-1, and see boot_capture_index() for the mechanism and the rule.
    ap.add_argument('--force', action='store_true',
                    help='take a SECOND (or later) capture on this boot. '
                         'Only for a bar that compares captures within one '
                         'boot and carries its own control -- mtxgold.sh. '
                         'A forced capture is stamped and compare() will '
                         'not silently weigh it against a first capture.')
    ap.add_argument('--settle', action='store_true',
                    help='take a THROWAWAY capture first and measure the '
                         'second, so the dynamics history term is settled '
                         'whatever this capture\'s position in the boot. '
                         'Stamped: a settled capture is NOT comparable '
                         'with the unsettled goldens in goldens/.')
    args = ap.parse_args()

    if args.compare:
        return compare(json.load(open(args.compare[0])),
                       json.load(open(args.compare[1])))

    sc = S.Scope(1)
    # The link intermittently answers a read with nothing, and check_chip
    # reads that as "CHIP 0". One failed read is not proof the wrong part
    # is on the other end, so re-open and ask again before giving up --
    # but never SKIP the check: a Scope(1) answering as chip 2 makes every
    # symbol address in the capture wrong.
    # Retry on the SAME Scope. Constructing a second one grabs the RDY
    # GPIO line while the first still holds it and the request fails with
    # EBUSY -- which looks like a dead part and is not. check_chip's read
    # is a voting read, so calling it again is a fresh vote and is all the
    # retry that is wanted here.
    for attempt in range(4):
        try:
            sc.check_chip()
            break
        except SystemExit:
            if attempt == 3:
                raise
            time.sleep(1.0)

    partner = args.strip + 1 if args.strip % 2 else args.strip - 1
    configure(sc, args.strip, True, args.gain, args.dly)
    configure(sc, partner, False, 1.0, args.dly)
    if args.bq:
        # Both strips, not just the driven one: the pair runs paired only
        # when BOTH are in steady state, and a silent lane still has to be
        # filtered by its own coefficients for the negative control to be
        # able to fail.
        load_biquads(sc, args.strip, 0)
        load_biquads(sc, partner, 1)
    # A coefficient swap starts a 576-sample CROSSFADE, and a crossfading
    # pair falls back to the two scalar nodes -- so capturing too early
    # would compare two builds that are BOTH running the scalar path and
    # would pass whatever the pairing did.
    time.sleep(2.0)

    bus = CROSSPOINTS[args.xp][0]
    if bus not in sc.sym:
        raise SystemExit('no %s in this image — %s is not a bus this build '
                         'carries' % (bus, args.xp))
    set_crosspoint(sc, args.strip, args.xp, on=not args.xp_off)
    inj = inject_addr(sc, args.strip)
    src = sc.sym[bus]

    # WHERE THIS CAPTURE SITS IN ITS BOOT (S23-1). The ledger is read and
    # bumped BEFORE the arm, because an arm that fails its readback has
    # still injected its step and still left the dynamics with a history --
    # so a retry after a failed capture is a second capture, and that is
    # exactly the case pairgraph_run.sh's retry loop produces.
    idx = boot_capture_index(sc)
    if idx is not None and idx > 1 and not (args.force or args.settle):
        print('REFUSED: this is capture %d of this DSP boot, and the first '
              'capture of a boot is a DIFFERENT measurement (S23-1: 235 of '
              '256 words, maxdiff 1,412 LSB). Every golden in goldens/ was '
              'taken as a first capture.' % idx)
        print('  Re-boot and take one capture, or pass --settle (a '
              'throwaway capture first, stamped, and NOT comparable with '
              'the stored goldens), or --force if this bar compares '
              'captures within one boot and carries its own control.')
        return 3

    if args.settle:
        # The throwaway. Same arm, same stimulus, result discarded: all it
        # exists to do is leave the gate and the compressor in the state
        # the NEXT capture will find them in.
        capture(sc, inj, src, min(args.n, 8))
        time.sleep(0.2)

    words = capture(sc, inj, src, args.n)

    digest = hashlib.sha256(
        b''.join(struct.pack('<I', w & 0xFFFFFFFF) for w in words)).hexdigest()
    nz = sum(1 for w in words if w)
    json.dump({'tag': args.tag or args.out, 'strip': args.strip,
               'xp': args.xp, 'xp_off': bool(args.xp_off), 'bus': bus,
               'partner': partner, 'block': BLOCK, 'gain': args.gain,
               'paired_build': '_blk_pool1' in sc.sym,
               'bq_paired_build': any(k.startswith('_BQPFILT_')
                                      for k in sc.sym),
               'bq': bool(args.bq),
               'boot_capture_index': idx, 'settled': bool(args.settle),
               'forced': bool(args.force),
               'inj': inj, 'src': src, 'sha256': digest,
               'nonzero': nz, 'words': words}, open(args.out, 'w'))
    print('strip %d driven, %d muted, xp=%s%s (%s), paired_build=%s '
          'bq_paired_build=%s bq_loaded=%s: %d/%d non-zero, sha256 %s'
          % (args.strip, partner, args.xp, ' OFF' if args.xp_off else '',
             bus, '_blk_pool1' in sc.sym,
             any(k.startswith('_BQPFILT_') for k in sc.sym), bool(args.bq),
             nz, len(words), digest[:16]))
    print('  boot capture #%s%s%s'
          % ('?' if idx is None else idx,
             ', SETTLED' if args.settle else '',
             ', FORCED' if args.force else ''))
    # A capture of all zeros proves nothing: it is what a dead strip, a
    # dropped arm and a muted graph all look like -- EXCEPT under
    # --xp-off, where all zeros IS the answer and anything else is the
    # failure.
    if args.xp_off:
        if nz:
            print('NEGATIVE CONTROL FAILED: %d of %d words non-zero with '
                  'the assign bit at 0' % (nz, len(words)))
        return 1 if nz else 0
    return 0 if nz else 1


if __name__ == '__main__':
    sys.exit(main())
