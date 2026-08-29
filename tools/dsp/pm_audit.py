#!/usr/bin/env python3
"""pm_audit.py -- what actually fills PROGRAM MEMORY, per object and per symbol.

Session 3 (2026-08-29) opened with chip 1's sec_swco full (131,070 of
131,072 bytes) in every block-kernel build, everything spilling to the
block-2 overflow, and fused+paired refusing to link at all. dsp_memreport.py
answers "how much is left"; this answers "who is using it", which is the
question a reclamation pass has to start from.

It parses a CCES linker map XML and attributes every byte of the code
output sections (sec_swco, sec_swco_ovf, sec_pmco) to the object file that
contributed it, and within a file to the symbols the linker recorded.
Objects are also rolled up into groups (nodes by class, lib, infra) because
the interesting unit is usually "all 32 ROUTING bodies", not one of them.

Usage:
  pm_audit.py <map.xml>                 # per-group and per-file totals
  pm_audit.py <map.xml> --syms          # add per-symbol detail
  pm_audit.py <map.xml> --file <substr> # symbols of matching objects only
  pm_audit.py --diff <a.map.xml> <b.map.xml>   # per-group before/after
"""

import re
import sys
from collections import defaultdict

CODE_SECTIONS = ('sec_swco', 'sec_swco_ovf', 'sec_pmco')

# The code output sections are SW (memory_width 0x10), so the linker map
# counts their INPUT_SECTION sizes in 16-bit short words while the MEMORY
# regions they land in are byte-wide (WIDTH(8)). Everything here is
# reported in BYTES so it can be compared against dsp_memreport.py and
# against the linker's own "N words were not mapped" shortfall, which is
# also bytes. Totals run a few hundred bytes under the region figure --
# that difference is INPUT_SECTION_ALIGN padding, which belongs to no
# object file.
UNIT_BYTES = 2

OUT_RE = re.compile(r"<OUTPUT_SECTION name='([^']+)'[^>]*>")
IN_RE = re.compile(r"<INPUT_SECTION [^>]*size='(0x[0-9a-fA-F]+)'[^>]*>")
FILE_RE = re.compile(r"<INPUT_FILE><!\[CDATA\[([^\]]+)\]\]></INPUT_FILE>")
SYM_RE = re.compile(r"<SYMBOL name='([^']+)' address='(0x[0-9a-fA-F]+)' size='(0x[0-9a-fA-F]+)'")


def parse(path):
    """-> {objfile: {'bytes': n, 'syms': {name: size}}} for code sections."""
    text = open(path, errors='ignore').read()
    files = defaultdict(lambda: {'bytes': 0, 'syms': defaultdict(int)})
    cur_out = None
    cur_file = None
    for line in text.splitlines():
        m = OUT_RE.search(line)
        if m:
            cur_out = m.group(1)
            continue
        if cur_out not in CODE_SECTIONS:
            continue
        m = IN_RE.search(line)
        if m:
            pending = int(m.group(1), 16)
            cur_file = None
            _pending[0] = pending
            continue
        m = FILE_RE.search(line)
        if m:
            cur_file = m.group(1)
            files[cur_file]['bytes'] += _pending[0] * UNIT_BYTES
            continue
        m = SYM_RE.search(line)
        if m and cur_file:
            files[cur_file]['syms'][m.group(1)] += int(m.group(3), 16) * UNIT_BYTES
    return files


_pending = [0]


def group_of(path):
    """Roll an object path up into a reporting group."""
    name = path.rsplit('/', 1)[-1][:-4]          # strip .doj
    if '/lib/' in path:
        return 'lib/' + name
    if '/chip1/' in path or '/chip2/' in path:
        # node objects are C<chip>_<TYPE>_<NN>
        m = re.match(r'^C\d_([A-Z0-9]+(?:_[A-Z]+)*)_\d+$', name)
        if m:
            return 'nodes:' + m.group(1)
        return 'infra/' + name
    return 'other/' + name


def totals(files):
    g = defaultdict(int)
    n = defaultdict(int)
    for path, d in files.items():
        g[group_of(path)] += d['bytes']
        n[group_of(path)] += 1
    return g, n


def report(path, show_syms=False, file_filter=None):
    files = parse(path)
    total = sum(d['bytes'] for d in files.values())
    g, n = totals(files)
    print(f"=== {path}")
    print(f"    total code bytes: {total:,} in {len(files)} objects\n")
    print(f"{'group':32} {'objs':>5} {'bytes':>10} {'each':>8}  {'%':>5}")
    for k in sorted(g, key=lambda k: -g[k]):
        each = g[k] // n[k]
        print(f"{k:32} {n[k]:5} {g[k]:10,} {each:8,}  {100.0*g[k]/total:5.1f}")
    if show_syms or file_filter:
        print()
        for path_, d in sorted(files.items(), key=lambda kv: -kv[1]['bytes']):
            if file_filter and file_filter not in path_:
                continue
            print(f"--- {path_.rsplit('/',1)[-1]}  {d['bytes']:,} B")
            for s, sz in sorted(d['syms'].items(), key=lambda kv: -kv[1]):
                if sz:
                    print(f"      {s:44} {sz:7,}")


def diff(a, b):
    ga, na = totals(parse(a))
    gb, nb = totals(parse(b))
    keys = set(ga) | set(gb)
    ta, tb = sum(ga.values()), sum(gb.values())
    print(f"A = {a}   {ta:,} B")
    print(f"B = {b}   {tb:,} B")
    print(f"delta = {tb-ta:+,} B\n")
    print(f"{'group':32} {'A':>10} {'B':>10} {'delta':>10}")
    for k in sorted(keys, key=lambda k: -abs(gb.get(k, 0) - ga.get(k, 0))):
        d = gb.get(k, 0) - ga.get(k, 0)
        if d == 0:
            continue
        print(f"{k:32} {ga.get(k,0):10,} {gb.get(k,0):10,} {d:+10,}")


if __name__ == '__main__':
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(2)
    if args[0] == '--diff':
        diff(args[1], args[2])
    else:
        ff = None
        if '--file' in args:
            ff = args[args.index('--file') + 1]
        report(args[0], show_syms='--syms' in args, file_filter=ff)
