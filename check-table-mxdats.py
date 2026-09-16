#!/usr/bin/env python3
"""check-table-mxdats.py — Table's top code must equal MxDatS-1.

WHY THIS EXISTS (S53). `MW/D32/DSP/gen_dsp.py` carried a second, hand-typed
copy of the master's `Table` column at every `add_cell()` call site, and
S47's `--force` landing let it overwrite the master's own string on 733
D24 matrix fields. The generator no longer carries that copy (Table comes
from the pinned `defs` master row only, via the matrix expansion), but
nothing checked that the MASTER's own Table string agrees with its own
MxDatS -- the exact class of error the literal duplication masked. This
gate reads that agreement off the master directly, once, rather than off
every product's expansion of it.

WHAT IS CHECKED: for every master cell row that gives a Table string in
the `N=V/M=W/.../[scale]` breakpoint form (a leading-integer-then-`=`
pattern; the scale-only forms like `Pan:dB:0:Off` or the stepped
`dB:Off:-50@31:...` tables carry no comparable "top code" and are
skipped) and a numeric MxDatS, the highest breakpoint code must equal
MxDatS-1 -- MxDatS is documented as the number of valid codes 0..MxDatS-1
a cell's wire byte may carry, and the top of the Table's own range is
supposed to be the last of them.

THIS DOES NOT FAIL THE BUILD. A violation here may be a real Table/MxDatS
disagreement in the master, or it may be one of the master's own
intentional exceptions (S53 found 25 such rows in the family set S47
corrupted; there may be more elsewhere the master has not resolved yet).
Fixing the master is not this repo's call -- it is a CONSUMER of the
definitions -- so this script reports every violator by name and exits
0. `check-contract-drift.sh` runs it and prints its output; nothing
upstream of it is blocked.

Usage:
    python3 check-table-mxdats.py
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MASTER = ROOT / "defs" / "common" / "cells" / "mx_master.csv"

_TOP_RE = re.compile(r"(\d+)\s*=")


def top_code(table: str) -> int | None:
    """The highest `N=` breakpoint code in a Table string, or None if the
    string carries no comparable breakpoint (a scale-only or stepped
    form)."""
    matches = _TOP_RE.findall(table)
    return int(matches[-1]) if matches else None


def main() -> int:
    if not MASTER.is_file():
        print(f"ERROR: no master at {MASTER}", file=sys.stderr)
        return 1

    with MASTER.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    checked = 0
    violators: list[tuple[str, str, str, int, int]] = []
    for r in rows:
        table = (r.get("Table") or "").strip()
        mxdats = (r.get("MxDatS") or "").strip()
        if not table or not mxdats or not re.fullmatch(r"\d+", mxdats):
            continue
        top = top_code(table)
        if top is None:
            continue
        checked += 1
        expected = int(mxdats) - 1
        if top != expected:
            violators.append((r["_Cell"], mxdats, table, top, expected))

    print(f"Table/MxDatS agreement: {checked} master rows carry a "
          f"comparable Table breakpoint and a numeric MxDatS")
    if violators:
        print(f"  {len(violators)} rows where Table's top code != MxDatS-1 "
              f"(not fixed here -- this repo is a consumer of the master; "
              f"reported for the hub):")
        for cell, mxdats, table, top, expected in violators:
            print(f"    - {cell}: MxDatS={mxdats} (expect top {expected}), "
                  f"Table={table!r} (top {top})")
    else:
        print("  no violations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
