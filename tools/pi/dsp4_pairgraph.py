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
DLY_OFF = 0x004E
FDR_LEVEL, FDR_PAN, FDR_MUTE, FDR_DCA = 0x0050, 0x0051, 0x0052, 0x0053

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
    for addr, val in ((b + FDR_LEVEL, 1.0), (b + FDR_PAN, 0.5),
                      (b + FDR_DCA, 1.0)):
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
    time.sleep(1.0)                            # let the ramped writes land

    inj = inject_addr(sc, args.strip)
    src = sc.sym['_buf_C1_BUS_MAIN_L']
    words = capture(sc, inj, src, args.n)

    digest = hashlib.sha256(
        b''.join(struct.pack('<I', w & 0xFFFFFFFF) for w in words)).hexdigest()
    nz = sum(1 for w in words if w)
    json.dump({'tag': args.tag or args.out, 'strip': args.strip,
               'partner': partner, 'block': BLOCK,
               'paired_build': '_blk_pool1' in sc.sym,
               'inj': inj, 'src': src, 'sha256': digest,
               'nonzero': nz, 'words': words}, open(args.out, 'w'))
    print('strip %d driven, %d muted, paired_build=%s: %d/%d non-zero, '
          'sha256 %s' % (args.strip, partner, '_blk_pool1' in sc.sym,
                         nz, len(words), digest[:16]))
    # A capture of all zeros proves nothing: it is what a dead strip, a
    # dropped arm and a muted graph all look like.
    return 0 if nz else 1


if __name__ == '__main__':
    sys.exit(main())
