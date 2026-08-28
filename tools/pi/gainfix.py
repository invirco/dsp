#!/usr/bin/env python3
"""gainfix.py — repair strip 1's GAIN coefficient without a reboot.

Roughly one boot+config in three leaves _gain_coeff_C1_GAIN_01 and
_gain_target_C1_GAIN_01 holding the CFG_COMMIT transaction's own header
word instead of 1.0f (root-caused 2026-08-28: a one-word phase slip in
the two-word parameter protocol). Everything else reads clean, the strip
runs on a garbage gain, and any cycle number taken in that state is the
SILENCE number.

Re-running boot+config clears it, at ~40 s a go. Writing the parameter
again over the same link clears it too, at ~1 s -- and it is the path the
host uses in service anyway. GAIN is a RAMPED parameter, so the write
must carry ramp_id=1 or it takes the instant path and the node's own
block-rate code clobbers it from a target that was never set.

Takes an optional strip count (default 1). GAIN parameters are 144
apart on the SPI page, so strip n lives at (n-1)*144 -- a ceiling sweep
can have the slip land on any of its strips, and one dead strip is a
CHEAP strip, so it flatters the number rather than failing it.

Exit 0 = every coefficient asked for reads 1.0f (repaired or already
good), 1 = at least one is still wrong, 2 = at least one is unreadable.
"""
import json
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
from dsp4_tubedly_probe import wrv

GAIN_ADDR = 0x0000
GAIN_STRIDE = 144        # per strip, from dsp.csv's spi_addr column
UNITY_F32 = struct.unpack('<I', struct.pack('<f', 1.0))[0]   # 0x3F800000


def read_coeff(sc, addr):
    """Two agreeing reads: the link answers 0xFFFFFFFF intermittently and
    one read cannot tell that from a value."""
    last = None
    for _ in range(24):
        try:
            v = sc.peek(addr)
        except Exception:
            last = None
            time.sleep(0.05)
            continue
        if v is None or v == 0xFFFFFFFF:
            last = None
            time.sleep(0.03)
            continue
        if v == last:
            return v
        last = v
        time.sleep(0.03)
    return None


def fix_one(sc, strip):
    """strip is 1-based. Returns 0 ok, 1 still wrong, 2 unreadable."""
    sym = '_gain_coeff_C1_GAIN_%02d' % strip
    if sym not in sc.sym:
        return 0                       # strip not in this build
    addr = sc.sym[sym]
    spi = GAIN_ADDR + (strip - 1) * GAIN_STRIDE

    v = read_coeff(sc, addr)
    if v is None:
        print('gainfix: strip %d coefficient unreadable' % strip)
        return 2
    if v == UNITY_F32:
        return 0

    print('gainfix: strip %d is 0x%08X, rewriting GAIN = 1.0' % (strip, v))
    for attempt in range(3):
        try:
            wrv(sc, spi, UNITY_F32, ramp_id=1, settle=0.05)
        except Exception as e:
            print('gainfix: strip %d write failed (%s)' % (strip, e))
        time.sleep(0.4)
        v = read_coeff(sc, addr)
        if v == UNITY_F32:
            print('gainfix: strip %d repaired on attempt %d' % (strip, attempt + 1))
            return 0
    print('gainfix: strip %d still 0x%s'
          % (strip, 'unreadable' if v is None else '%08X' % v))
    return 1


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    sc = S.Scope(1)
    sc.check_chip()
    worst = 0
    for strip in range(1, n + 1):
        worst = max(worst, fix_one(sc, strip))
    if worst == 0:
        print('gainfix: %d strip(s) at 0x%08X' % (n, UNITY_F32))
    return worst


if __name__ == '__main__':
    sys.exit(main())
