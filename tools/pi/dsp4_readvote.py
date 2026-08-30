#!/usr/bin/env python3
"""dsp4_readvote.py — how often does a HEALTHY part answer a diag read with 0?

The parameter link's read protocol verifies the ECHO of every answer, and that
check exists so a wrong value can never be mistaken for a right one. It does
not do that. The firmware says so in as many words (main.asm, 2026-08-23): "a
dropped answer comes back as a well-formed (echo, 0) -- a wrong value that
cannot be told from a real one." So a read that returns 0 is either the
register's value or a dropped answer, and nothing in the protocol separates
them.

Every bench script in this tree decides whether the part came up by reading
BOOT_STAGE, one register, once. A dropped answer to that one read produces
BOOT_STAGE 0 — which is the exact failure signature the record has carried as
"the intermittent boot+config failure" since session 5.

This measures the artifact rate on a part known to be healthy, by reading
registers whose correct value cannot be 0:

    MAGIC       0xD5B40001, a constant compiled into the image
    CHIP_ID     1 or 2
    BOOT_STAGE  7 once running
    PRODUCT_ID  1 after a d24 config

and it scores three host-side read policies over the SAME samples:

    single      believe the first answer                 (what every tool does)
    vote2       re-ask once; believe only if both agree
    vote3       best of three, majority

Usage (on the Pi, after a boot+config):
    python3 dsp4_readvote.py --reads 400
"""

import argparse
import collections
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dsp4_boot import CS_GPIO

CHECKS = [(0xE000, 'MAGIC', 0xD5B40001), (0xE001, 'CHIP_ID', None),
          (0xE002, 'BOOT_STAGE', None), (0xE010, 'PRODUCT_ID', None)]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--reads', type=int, default=400)
    ap.add_argument('--chip', type=int, default=1, choices=(1, 2))
    ap.add_argument('--gap', type=float, default=0.0,
                    help='seconds between reads (0 = as fast as the host can)')
    args = ap.parse_args()

    from dsp4_config import SpiLink
    from dsp4_diag import DiagLink
    link = SpiLink('0.0', 1_000_000, CS_GPIO[args.chip])
    d = DiagLink(link)
    d.resync()

    # Truth is taken as the modal answer over a settling burst, so the
    # scoring never depends on an assumption about what the part holds.
    truth = {}
    for addr, name, expect in CHECKS:
        seen = collections.Counter()
        for _ in range(9):
            try:
                seen[d.read(addr)] += 1
            except IOError:
                seen[None] += 1
        truth[addr] = expect if expect is not None else seen.most_common(1)[0][0]
        print(f'  {name:11s} truth {truth[addr]}  (burst {dict(seen)})')

    stats = {name: collections.Counter() for _, name, _ in CHECKS}
    policies = {p: collections.Counter() for p in ('single', 'vote2', 'vote3')}
    for i in range(args.reads):
        for addr, name, _ in CHECKS:
            vals = []
            for _ in range(3):
                try:
                    vals.append(d.read(addr))
                except IOError:
                    vals.append(None)
            good = truth[addr]
            stats[name]['n'] += 1
            if vals[0] == good:
                stats[name]['ok'] += 1
            elif vals[0] == 0:
                stats[name]['zero'] += 1
            else:
                stats[name]['other'] += 1
            # single: believe vals[0]
            policies['single']['n'] += 1
            policies['single']['wrong'] += (vals[0] != good)
            # vote2: believe only when the first two agree, else no answer
            policies['vote2']['n'] += 1
            if vals[0] == vals[1]:
                policies['vote2']['wrong'] += (vals[0] != good)
            else:
                policies['vote2']['abstain'] += 1
            # vote3: majority of three
            m = collections.Counter(vals).most_common(1)[0]
            policies['vote3']['n'] += 1
            if m[1] >= 2:
                policies['vote3']['wrong'] += (m[0] != good)
            else:
                policies['vote3']['abstain'] += 1
        if args.gap:
            time.sleep(args.gap)

    print()
    for _, name, _ in CHECKS:
        c = stats[name]
        n = c['n'] or 1
        print(f'  {name:11s} {c["ok"]}/{c["n"]} correct on the first answer, '
              f'{c["zero"]} read 0 ({100.0 * c["zero"] / n:.2f}%), '
              f'{c["other"]} read something else')
    print()
    for p in ('single', 'vote2', 'vote3'):
        c = policies[p]
        n = c['n'] or 1
        print(f'  policy {p:7s} wrong {c["wrong"]}/{c["n"]} '
              f'({100.0 * c["wrong"] / n:.3f}%), abstained {c["abstain"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
