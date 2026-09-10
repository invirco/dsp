#!/usr/bin/env python3
"""dsp4_shk_perstrip.py — does the SHARED kernel address the RIGHT strip? (S18)

A shared per-strip kernel is entered with the strip's record base in a DAG
register. If it were entered with the WRONG base -- one strip's, every time
-- the image would still link, would have the same byte count, would pass
`golden_harness`, and would pass `famverify`, because famverify drives
`C1_COMP_01` and a kernel stuck on strip 1's record is exactly right for
strip 1. So the shared kernels get a witness that is per STRIP.

WHAT IT USES, and why it needs no signal and no capture: the compressor's
block-rate conversion READS `_comp_threshold_<nid>` and WRITES
`_comp_cgp_<nid>[0]`, both in that node's own record, once per block. Write
a DIFFERENT threshold to each strip over SPI, let a block run, and read the
converted words back:

  * every strip's `_comp_cgp[0]` must equal fix(thr * 2^25/log2-dB) computed
    here -- the same arithmetic the kernel does;
  * and they must therefore all DIFFER, which is the thing a wrong base
    cannot produce.

A kernel on one record leaves 31 of the 32 words at their `.var` initialiser
of zero and moves the 32nd; that is reported as the failure it is.

    python3 dsp4_shk_perstrip.py [--strips 1,7,16,24,32]
"""
import argparse
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

STRIP_STRIDE = 144          # words per strip page (dsp_params.asm)
COMP_ON = 0x0038
COMP_THR = 0x0039
DB_TO_Q625 = 0x4AAA152D     # the constant the kernel multiplies by


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def fromf32(u):
    return struct.unpack('<f', struct.pack('<I', u & 0xFFFFFFFF))[0]


def f32r(x):
    """Round a Python float to float32, which is what the part holds."""
    return struct.unpack('<f', struct.pack('<f', float(x)))[0]


def fix(x):
    """`r1 = fix f1` -- truncate toward zero into int32, saturating."""
    v = int(x)
    return max(-2**31, min(2**31 - 1, v)) & 0xFFFFFFFF


def wrv(sc, addr, val, tries=12):
    val &= 0xFFFFFFFF
    for _ in range(tries):
        sc.d.write(addr, val)
        time.sleep(S.SETTLE)
        try:
            if sc.rd(addr) == val:
                return
        except IOError:
            pass
    raise IOError('SPI 0x%04X would not take 0x%08X' % (addr, val))


def main():
    ap = argparse.ArgumentParser()
    # DEFAULTS INSIDE THE PRODUCT. A strip the channel mask has off is
    # never CALLED -- process_chain jumps the whole gate group -- so its
    # `_comp_cgp` keeps its `.var` initialiser of zero however correct the
    # kernel is. The control arm read 0 on strips 31 and 32 at D24 for
    # exactly that reason. Pass --strips explicitly for a D32 run.
    ap.add_argument('--strips', default='1,2,7,16,23,24')
    ap.add_argument('--chip', type=int, default=1)
    a = ap.parse_args()
    strips = [int(x) for x in a.strips.split(',')]

    sc = S.Scope(a.chip)
    sc.check_chip()

    scale = fromf32(DB_TO_Q625)
    want = {}
    for n in strips:
        # A different threshold per strip, and none of them a default.
        thr = f32r(-6.0 - 1.5 * n)
        base = (n - 1) * STRIP_STRIDE
        wrv(sc, base + COMP_ON, 1)
        wrv(sc, base + COMP_THR, f32(thr))
        # THE MODEL IS THE PART'S ARITHMETIC, NOT A MORE PRECISE ONE. The
        # kernel does `f1 = f1 * f2; r1 = fix f1` in 32-bit float; computing
        # the same thing in float64 here disagreed with the CONTROL arm by
        # 1-3 LSB on four strips out of seven, which is a defect in the
        # witness and not in the kernel.
        want[n] = (thr, fix(f32r(thr * scale)))
    time.sleep(0.5)

    bad = 0
    seen = {}
    print('strip  threshold   _comp_cgp[0] read   model        verdict')
    for n in strips:
        nid = 'C%d_COMP_%02d' % (a.chip, n)
        try:
            got = sc.peek(sc.addr('_comp_cgp_%s' % nid))
        except (IOError, SystemExit) as e:
            print('%5d  UNREADABLE (%s)' % (n, e))
            bad += 1
            continue
        thr, exp = want[n]
        ok = (got == exp)
        seen.setdefault(got, []).append(n)
        print('%5d  %9.1f   0x%08X          0x%08X   %s'
              % (n, thr, got, exp, 'OK' if ok else '**WRONG**'))
        if not ok:
            bad += 1

    dups = {v: ns for v, ns in seen.items() if len(ns) > 1}
    if dups:
        print('\nSTRIPS SHARING ONE CONVERTED WORD -- the kernel is not '
              'addressing per strip:')
        for v, ns in dups.items():
            print('  0x%08X on strips %s' % (v, ns))
        bad += 1
    if bad:
        print('\nPER-STRIP WITNESS FAILED (%d)' % bad)
        return 1
    print('\nPER-STRIP OK: %d strips, %d distinct converted thresholds, every '
          'one the model\'s' % (len(strips), len(seen)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
