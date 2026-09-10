#!/usr/bin/env python3
"""dsp_codepool.py — what the SHARC code pool actually holds, by object and
by symbol, across all three code tiers.

Usage:
    python3 dsp_codepool.py <chipN.map.xml> [--by symbol|object|class]
                            [--tier 1|2|3] [--top N]
    python3 dsp_codepool.py <a.map.xml> --diff <b.map.xml>

Why this exists
---------------
dsp_memreport.py answers "how much room is left". It cannot answer "left
after WHAT", and on chip 1 that is the only question worth asking: the pool
has been at 98–100% since the pairing arm landed, and every decision about
what may ship next is a decision about which bytes are in it.

The linker map already carries the answer — per output section, per input
section, per input FILE, per SYMBOL — and nothing in the tree read it. So a
session would measure the pool's percentage, find it full, and stop, with no
list of what filled it (S15 §6: "the binding resource is the code pool", and
then no table).

Three tiers, because there are three:
    tier 1  sec_swco       Block 3, primary
    tier 2  sec_swco_ovf   Block 2, overflow
    tier 3  sec_swco_ovf2  Block 1's leftover — shared with the DM overflow
                           and the DMA ping-pong buffers, so code here is
                           fetched against DDE traffic every block. Which
                           objects land there is decided by link order, i.e.
                           by build.sh's DSP4_COLD_OBJS list.

`--by class` folds the generated per-node instances (C1_EQ_07 -> EQ) so the
32-copies-of-one-kernel structure is visible as one row: that is where the
pool is, and it is what a shared-routine change would collect.

Sizes are bytes. The map's INPUT_SECTION `size` and OUTPUT_SECTION
`word_size` count words of the section's own width (SW code is 16-bit), so
everything here is multiplied out to bytes before it is printed — a report
that mixes the two units is worse than no report.
"""

import argparse
import collections
import re
import sys

TIERS = [('sec_swco', 'Block 3 (primary)'),
         ('sec_swco_ovf', 'Block 2 (overflow)'),
         ('sec_swco_ovf2', 'Block 1 (contended)')]

NODE_RE = re.compile(r'^C(\d)_([A-Z0-9]+(?:_[A-Z0-9]+)*?)_(\d+)$')


def parse(path):
    """Return [(tier_index, object_name, bytes, [(symbol, bytes)])]."""
    txt = open(path).read()
    out = []
    for ti, (sec, _label) in enumerate(TIERS):
        m = re.search(r"<OUTPUT_SECTION name='%s'[^>]*>(.*?)</OUTPUT_SECTION>"
                      % sec, txt, re.S)
        if not m:
            continue
        for i in re.finditer(r"<INPUT_SECTION\b([^>]*)>(.*?)</INPUT_SECTION>",
                             m.group(1), re.S):
            attrs = dict(re.findall(r"(\w+)='([^']*)'", i.group(1)))
            fm = re.search(r"INPUT_FILE><!\[CDATA\[(.*?)\]\]", i.group(2))
            obj = fm.group(1).split('/')[-1].rsplit('.', 1)[0] if fm else '?'
            syms = [(s, int(z, 16) * 2) for s, _a, z in re.findall(
                r"<SYMBOL name='([^']*)' address='([^']*)' size='([^']*)'",
                i.group(2))]
            out.append((ti, obj, int(attrs['size'], 16) * 2, syms))
    return out


def classify(obj):
    """Fold a generated node instance onto its class; leave the rest alone."""
    m = NODE_RE.match(obj)
    return 'node ' + m.group(2) if m else obj


def totals(rows, key):
    size = collections.Counter()
    count = collections.Counter()
    for _ti, obj, nbytes, _syms in rows:
        k = key(obj)
        size[k] += nbytes
        count[k] += 1
    return size, count


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[1],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('map', help='linker map XML')
    ap.add_argument('--by', choices=('object', 'symbol', 'class'),
                    default='class')
    ap.add_argument('--tier', type=int, choices=(1, 2, 3),
                    help='restrict to one tier')
    ap.add_argument('--top', type=int, default=40)
    ap.add_argument('--diff', metavar='OTHER.map.xml',
                    help='report the per-object delta against another map')
    args = ap.parse_args(argv)

    rows = parse(args.map)
    if args.tier:
        rows = [r for r in rows if r[0] == args.tier - 1]

    if args.diff:
        a, _ = totals(rows, lambda o: o)
        b, _ = totals(parse(args.diff), lambda o: o)
        delta = {k: b.get(k, 0) - a.get(k, 0)
                 for k in set(a) | set(b) if b.get(k, 0) != a.get(k, 0)}
        print(f"=== {args.diff} minus {args.map}")
        for k, v in sorted(delta.items(), key=lambda kv: -abs(kv[1])):
            print(f"  {k:<40s} {v:+8d}")
        print(f"  {'TOTAL':<40s} {sum(b.values()) - sum(a.values()):+8d}")
        return 0

    grand = sum(r[2] for r in rows)
    print(f"=== {args.map}")
    per_tier = collections.Counter()
    for ti, _obj, nbytes, _s in rows:
        per_tier[ti] += nbytes
    for ti, (sec, label) in enumerate(TIERS):
        if per_tier[ti] or ti < 2:
            note = ''
            if ti == 2 and per_tier[ti]:
                note = '  <-- fetched against the DM overflow and DMA buffers'
            print(f"  tier {ti + 1}  {sec:<14} {label:<20} "
                  f"{per_tier[ti]:>8d} bytes{note}")
    print(f"  {'':>7}{'TOTAL':<14} {'':<20} {grand:>8d} bytes\n")

    if args.by == 'symbol':
        syms = collections.Counter()
        for _ti, obj, _b, ss in rows:
            for s, z in ss:
                if z:
                    syms[f'{s}  [{obj}]'] = z
        items = syms.most_common(args.top)
        width = max((len(k) for k, _ in items), default=10)
        for k, v in items:
            print(f"  {k:<{width}s} {v:7d}  {100.0 * v / grand:4.1f}%")
        return 0

    key = classify if args.by == 'class' else (lambda o: o)
    size, count = totals(rows, key)
    for k, v in size.most_common(args.top):
        n = count[k]
        each = f"  n={n:<3d} each={v // n:6d}" if n > 1 else ''
        print(f"  {k:<28s} {v:7d}  {100.0 * v / grand:4.1f}%{each}")
    if len(size) > args.top:
        rest = grand - sum(v for _k, v in size.most_common(args.top))
        print(f"  {'(%d more)' % (len(size) - args.top):<28s} {rest:7d}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
