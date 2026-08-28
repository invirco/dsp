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

Exit 0 = the coefficient reads 1.0f (repaired or already good),
       1 = still wrong, 2 = unreadable.
"""
import json
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
from dsp4_tubedly_probe import wrv

GAIN_ADDR = 0x0000
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


def main():
    sc = S.Scope(1)
    sc.check_chip()
    addr = sc.sym['_gain_coeff_C1_GAIN_01']

    v = read_coeff(sc, addr)
    if v is None:
        print('gainfix: coefficient unreadable')
        return 2
    if v == UNITY_F32:
        print('gainfix: already 0x%08X' % v)
        return 0

    print('gainfix: coefficient is 0x%08X, rewriting GAIN = 1.0' % v)
    for attempt in range(3):
        try:
            wrv(sc, GAIN_ADDR, UNITY_F32, ramp_id=1, settle=0.05)
        except Exception as e:
            print('gainfix: write failed (%s)' % e)
        time.sleep(0.4)
        v = read_coeff(sc, addr)
        if v == UNITY_F32:
            print('gainfix: repaired on attempt %d' % (attempt + 1))
            return 0
    print('gainfix: still 0x%s' % ('unreadable' if v is None else '%08X' % v))
    return 1


if __name__ == '__main__':
    sys.exit(main())
