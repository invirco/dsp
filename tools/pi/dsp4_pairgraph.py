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

Usage:
    dsp4_pairgraph.py [--strip N] [--out FILE]

Writes the captured words to FILE and prints a one-line digest. Run it
against both builds and diff the files with --compare.
"""
import argparse
import hashlib
import json
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


def configure(sc, strip, loud):
    """Put one strip in a known state. Nothing is assumed: a probe that
    sets only what it thinks changed measures whatever the last boot left
    behind, which is how a dead strip reads as a cheap one."""
    b = (strip - 1) * STRIDE
    p = PARAMS['odd' if strip % 2 else 'even']
    wrv(sc, b + GAIN, f32(1.0 if loud else 0.0), ramp_id=1, settle=0.05)
    for addr, val in ((b + GATE_ON, 1), (b + COMP_ON, 1), (b + TUBE_ON, 0),
                      (b + FDR_MUTE, 0), (b + DLY_OFF, 0),
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
    ap.add_argument('--compare', nargs=2, metavar='FILE',
                    help='compare two captures instead of taking one')
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
    configure(sc, args.strip, True)
    configure(sc, partner, False)
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

    inj = inject_addr(sc, args.strip)
    src = sc.sym['_buf_C1_BUS_MAIN_L']
    words = capture(sc, inj, src, args.n)

    digest = hashlib.sha256(
        b''.join(struct.pack('<I', w & 0xFFFFFFFF) for w in words)).hexdigest()
    nz = sum(1 for w in words if w)
    json.dump({'tag': args.tag or args.out, 'strip': args.strip,
               'partner': partner, 'block': BLOCK,
               'paired_build': '_blk_pool1' in sc.sym,
               'bq_paired_build': any(k.startswith('_BQPFILT_')
                                      for k in sc.sym),
               'bq': bool(args.bq),
               'inj': inj, 'src': src, 'sha256': digest,
               'nonzero': nz, 'words': words}, open(args.out, 'w'))
    print('strip %d driven, %d muted, paired_build=%s bq_paired_build=%s '
          'bq_loaded=%s: %d/%d non-zero, sha256 %s'
          % (args.strip, partner, '_blk_pool1' in sc.sym,
             any(k.startswith('_BQPFILT_') for k in sc.sym), bool(args.bq),
             nz, len(words), digest[:16]))
    # A capture of all zeros proves nothing: it is what a dead strip, a
    # dropped arm and a muted graph all look like.
    return 0 if nz else 1


if __name__ == '__main__':
    sys.exit(main())
