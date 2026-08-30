#!/usr/bin/env python3
"""tubeon.py -- drive every strip's TubeOn without a reboot.

TUBE defaults OFF (`_tube_on_C1_TUBE_NN = 0`, the shipping plugin-off
state), so sigprofile.sh's NODE_LIMIT 6->7 difference on an unmodified
boot measures the ~2-cycle bypass copy, not the ~52-cycle active body
the emitted stream predicts. This flips every strip's TubeOn over the
parameter link the same way gainfix.py repairs GAIN, so a profiling
window can see the ENGAGED node -- and flips it back after, so a run
that stops here leaves the bench in its shipped default rather than a
half-changed state.

TubeOn is INSTANT (dsp_address_map.md: InstantCtl), so ramp_id=0 and a
single write applies immediately -- unlike TUBE_SAT, which ramps and
needs ramp_id=1 (dsp4_tubedly_probe.py's TUBE_ON/TUBE_SAT split already
established this split).

Usage: tubeon.py on|off [n]   -- n strips, default 32
Exit 0 = every strip asked for reads back the requested value (or the
symbol is absent from this build), 1 = at least one is still wrong,
2 = at least one is unreadable.
"""
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
from dsp4_tubedly_probe import wrv

TUBE_ON_BASE = 0x004C
TUBE_ON_STRIDE = 144           # per strip, from dsp.csv's spi_addr column


def read_on(sc, addr):
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


def set_one(sc, strip, val):
    """strip is 1-based. Returns 0 ok, 1 still wrong, 2 unreadable."""
    sym = '_tube_on_C1_TUBE_%02d' % strip
    if sym not in sc.sym:
        return 0                       # strip not in this build
    addr = sc.sym[sym]
    spi = TUBE_ON_BASE + (strip - 1) * TUBE_ON_STRIDE

    v = read_on(sc, addr)
    if v == val:
        return 0

    for attempt in range(3):
        try:
            wrv(sc, spi, val, ramp_id=0, settle=0.05)
        except Exception as e:
            print('tubeon: strip %d write failed (%s)' % (strip, e))
        time.sleep(0.2)
        v = read_on(sc, addr)
        if v == val:
            return 0
    print('tubeon: strip %d still 0x%s (wanted %d)'
          % (strip, 'unreadable' if v is None else '%08X' % v, val))
    return 1 if v is not None else 2


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ('on', 'off'):
        print('usage: tubeon.py on|off [n]')
        return 2
    val = 1 if sys.argv[1] == 'on' else 0
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 32

    sc = S.Scope(1)
    sc.check_chip()
    worst = 0
    for strip in range(1, n + 1):
        worst = max(worst, set_one(sc, strip, val))
    if worst == 0:
        print('tubeon: %d strip(s) TubeOn=%d' % (n, val))
    return worst


if __name__ == '__main__':
    sys.exit(main())
