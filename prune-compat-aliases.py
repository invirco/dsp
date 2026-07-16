#!/usr/bin/env python3
"""Prune selected compatibility alias families from expanded matrix CSV files.

- Removes rows whose _Cell family is in a configured set.
- Re-numbers MxAdd sequentially from 1.
- Recomputes Shex from MxAdd.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

AX = "hijklmnopqrstuvw"
CELL_RE = re.compile(r"^([A-Za-z]+)(\d{3})([A-Za-z0-9]+)(\d{3})$")


def to_shex(n: int) -> str:
    nibbles = [(n >> 12) & 0xF, (n >> 8) & 0xF, (n >> 4) & 0xF, n & 0xF]
    out = ""
    started = False
    for nib in nibbles:
        if nib or started:
            out += AX[nib]
            started = True
    return out


def family(cell: str) -> str:
    m = CELL_RE.match(cell)
    if not m:
        raise ValueError(f"Unparseable _Cell: {cell}")
    return f"{m.group(1)}{m.group(3)}"


def read_aliases(path: Path) -> set[str]:
    aliases: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        aliases.add(line)
    return aliases


def prune(path: Path, aliases: set[str]) -> tuple[int, int]:
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
        fieldnames = list(rows[0].keys()) if rows else []

    if not rows or not fieldnames:
        return 0, 0

    kept = []
    removed = 0
    for r in rows:
        fam = family((r.get("_Cell") or "").strip())
        if fam in aliases:
            removed += 1
            continue
        kept.append(r)

    for i, r in enumerate(kept, start=1):
        r["MxAdd"] = str(i)
        r["Shex"] = to_shex(i)

    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(kept)

    return removed, len(kept)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--aliases", required=True, help="Alias family config file")
    ap.add_argument("matrix", nargs="+", help="Expanded _matrix.csv paths")
    args = ap.parse_args()

    aliases = read_aliases(Path(args.aliases))
    if not aliases:
        print("No aliases configured; nothing to do")
        return 0

    for m in args.matrix:
        path = Path(m)
        removed, kept = prune(path, aliases)
        print(f"{path}: removed={removed}, kept={kept}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
