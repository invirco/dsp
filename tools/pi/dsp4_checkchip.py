#!/usr/bin/env python3
"""dsp4_checkchip.py — assert that each DSP is the chip it is supposed to be.

The bench can boot chip 2 with chip 1's firmware and nothing else on this
card will tell you. `pinctrl set ...,24,... a0` — the pin hand-back line every
run script carried until 2026-09-09 — puts GPIO24 into ALT0, which is
SD0_DAT2, not a deasserted chip select; chip 2's CS then sits asserted while
chip 1's boot stream clocks out and BOTH parts load chip1.ldr. Six
consecutive boots did that (findings S8-3). Through `dsp4_diag.py` the card
then looks completely healthy: MAGIC right, BOOT_STAGE right, ticks running
— with a CHIP_ID of 1 on the part that should say 2, and every symbol address
read from chip2.sym.json landing somewhere else entirely.

So this is the gate that goes after every boot, and it is deliberately a
separate, symbol-free tool: it needs no build directory, no .sym.json and no
configured graph, so it can be run at BOOT_STAGE 5 before anything else has
happened. The test itself is dsp4_scope.check_chip_id, imported rather than
re-spelt.

  dsp4_checkchip.py                 # both chips; exit 0 only if both agree
  dsp4_checkchip.py --chip 2        # one chip
  dsp4_checkchip.py --timeout 20    # wait longer for a chip to come up

Exit 0 = every requested chip answered its own id. Exit 3 = it did not, and
NOTHING measured through this boot may be recorded.
"""
import argparse
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
from dsp4_config import SpiLink
from dsp4_diag import DiagLink
from dsp4_scope import check_chip_id, CS_GPIO, RDY_GPIO

DIAG_MAGIC, DIAG_CHIP_ID = 0xE000, 0xE001
MAGIC = 0xD5B40001


def read_id(chip, timeout):
    """Return the CHIP_ID the part at `chip`'s CS/RDY answers with.

    Retried against a deadline because a chip a few seconds out of reset has
    not raised its parameter link yet, and 'no answer' at t=0 is not the same
    finding as 'the wrong answer'.
    """
    deadline = time.monotonic() + timeout
    last = None
    while True:
        try:
            d = DiagLink(SpiLink('0.0', 1_000_000, CS_GPIO[chip],
                                 rdy_gpio=RDY_GPIO[chip]))
            d.resync()
            if d.read(DIAG_MAGIC) == MAGIC:
                return d.read(DIAG_CHIP_ID)
            last = 'MAGIC absent'
        except (IOError, OSError) as e:
            last = e
        if time.monotonic() >= deadline:
            return 'no answer (%s)' % last
        time.sleep(0.5)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--chip', type=int, choices=(1, 2), action='append',
                    help='check only this chip (repeatable); default both')
    ap.add_argument('--timeout', type=float, default=15.0,
                    help='seconds to wait for a chip to answer at all')
    ap.add_argument('--quiet', action='store_true')
    args = ap.parse_args()

    chips = sorted(set(args.chip)) if args.chip else [1, 2]
    got = {c: read_id(c, args.timeout) for c in chips}
    for c in chips:
        if not args.quiet:
            print('chip %d (CS GPIO%d, RDY GPIO%d): CHIP_ID %s'
                  % (c, CS_GPIO[c], RDY_GPIO[c], got[c]))
    try:
        for c in chips:
            check_chip_id(got[c], c)
    except SystemExit as e:
        print('CHIP CHECK FAILED: %s' % e, file=sys.stderr)
        return 3
    if not args.quiet:
        print('chip check OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
