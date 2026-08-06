#!/usr/bin/env python3
"""dsp_memreport.py — Report SHARC memory headroom from linker map XMLs.

Usage: python3 dsp_memreport.py <chipN.map.xml> [...]
       python3 dsp_memreport.py MW/D32/DSP/SHARC/build/chip*.map.xml

Why this exists
---------------
The LDF fills a primary region and spills the remainder into an overflow
region (code: block3 -> block2; DM data: block0 -> block1; delay lines:
L2 -> L2CTL1). A primary region therefore sits at ~100% as a matter of
course — that is the design working, not a wall. Reading a single region's
percentage as "headroom" understates the space left by the whole overflow
chain and has caused false alarms twice (2026-07-30, 2026-08-06).

This script reports per-region usage AND the per-purpose totals across each
primary+overflow pair, which is the number that actually gates growth. It
also flags the real risk: an overflow tier filling up, because there is no
third tier behind it.

Exit codes:
  0  — every pool below the warn threshold
  1  — one or more pools at/above the warn threshold (default 90%)
"""

import re
import sys

WARN_PCT = 90.0

# Purpose -> ordered (primary, overflow...) regions, per the LDF fill order.
# 'fixed' pools are hardware-sized and always 100% full by definition — they
# are reported but never warn.
POOLS = [
    ('code (VISA SW)', ['mem_block3_bw', 'mem_block2_bw'], False),
    ('DM data + stack', ['mem_block0_bw', 'mem_block1_bw'], False),
    ('delay lines', ['mem_L2_bw', 'mem_L2CTL1_bw'], False),
    ('IVT (NW code)', ['mem_iv_code'], True),
]


def parse_map(path):
    """Return {region_name: (used, capacity, [section names])} from a map XML."""
    with open(path) as fh:
        txt = fh.read()
    regions = {}
    for m in re.finditer(r"<MEMORY\b([^>]*)>(.*?)</MEMORY>", txt, re.S):
        attrs = dict(re.findall(r"(\w+)='([^']*)'", m.group(1)))
        used = int(attrs['words_used'], 16)
        cap = used + int(attrs['words_unused'], 16)
        secs = [dict(re.findall(r"(\w+)='([^']*)'", o.group(1)))['name']
                for o in re.finditer(r"<OUTPUT_SECTION\b([^>]*)>", m.group(2))]
        regions[attrs['name']] = (used, cap, secs)
    return regions


def pct(used, cap):
    return 100.0 * used / cap if cap else 0.0


def report(path):
    regions = parse_map(path)
    print(f"=== {path}")
    worst = 0.0

    for label, names, fixed in POOLS:
        present = [n for n in names if n in regions]
        if not present:
            continue
        tot_u = sum(regions[n][0] for n in present)
        tot_c = sum(regions[n][1] for n in present)
        p = pct(tot_u, tot_c)
        if fixed:
            print(f"  {label:<18} {tot_u:>9}/{tot_c:<9} {p:5.1f}%  "
                  f"free {tot_c - tot_u:>9}  (fixed hardware size)")
            continue
        worst = max(worst, p)
        flag = '  <-- WARN' if p >= WARN_PCT else ''
        print(f"  {label:<18} {tot_u:>9}/{tot_c:<9} {p:5.1f}%  "
              f"free {tot_c - tot_u:>9}{flag}")

        for i, name in enumerate(present):
            used, cap, secs = regions[name]
            tier = 'primary ' if i == 0 else 'overflow'
            note = ''
            if i == 0 and len(present) > 1 and pct(used, cap) >= 99.0:
                note = '  (full — spilling to overflow, expected)'
            if i > 0 and pct(used, cap) >= WARN_PCT:
                note = '  (LAST TIER — no region behind this one)'
            print(f"      {tier} {name:<15} {used:>9}/{cap:<9} "
                  f"{pct(used, cap):5.1f}%  [{' '.join(secs) or '-'}]{note}")

    unlisted = [n for n in regions
                if not any(n in names for _, names, _f in POOLS)]
    for name in unlisted:
        used, cap, secs = regions[name]
        print(f"  (unpooled) {name:<15} {used:>9}/{cap:<9} {pct(used, cap):5.1f}%")

    return worst


def main(argv):
    paths = argv[1:]
    if not paths:
        print(__doc__.strip())
        return 2
    worst = 0.0
    for path in paths:
        worst = max(worst, report(path))
        print()
    if worst >= WARN_PCT:
        print(f"WARN: a memory pool is at {worst:.1f}% "
              f"(threshold {WARN_PCT:.0f}%) — rebalance the LDF before growing.")
        return 1
    print(f"OK: all pools below {WARN_PCT:.0f}%.")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
