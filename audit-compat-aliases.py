#!/usr/bin/env python3
"""Audit compatibility alias usage in D32 matrix.

Outputs a markdown report with counts for known alias families and their
canonical replacements to guide safe retirement.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MATRIX = ROOT / "MW" / "D32" / "MX" / "_matrix.csv"
REPORT = ROOT / "alias-audit.md"

CELL_RE = re.compile(r"^([A-Za-z]+)(\d{3})([A-Za-z0-9]+)(\d{3})$")

# alias family, canonical family, rationale
PAIRS = [
    ("FxDuckThr", "FxDuckSens", "Legacy threshold alias of DuckSens"),
    ("FxEqHi", "FxEqPresence", "Legacy FX high EQ alias"),
    ("AuxPeq", "AuxGeq", "Compatibility alias for GEQ gains"),
    ("MainPeqGain", "MainGeq", "Compatibility alias for main GEQ gains"),
    ("MainMtr", "AaMainMtr", "Unprefixed main meter alias"),
    ("SubMtr", "AaSubMtr", "Unprefixed sub meter alias"),
]


def family(cell: str) -> str:
    m = CELL_RE.match(cell)
    if not m:
        raise ValueError(f"Unparseable _Cell: {cell}")
    return f"{m.group(1)}{m.group(3)}"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def counts(rows: list[dict[str, str]]) -> tuple[dict[str, int], dict[str, int]]:
    total: dict[str, int] = {}
    mapped: dict[str, int] = {}
    for r in rows:
        fam = family((r.get("_Cell") or "").strip())
        total[fam] = total.get(fam, 0) + 1
        if (r.get("DspAdd") or "").strip():
            mapped[fam] = mapped.get(fam, 0) + 1
    return total, mapped


def status(alias_total: int, canonical_total: int, alias_mapped: int) -> str:
    if alias_total == 0:
        return "ready (alias absent)"
    if canonical_total == 0:
        return "blocked (no canonical family present)"
    if alias_mapped > 0:
        return "in progress (alias still DSP-mapped)"
    return "in progress (alias still present)"


def main() -> int:
    rows = read_rows(MATRIX)
    total, mapped = counts(rows)

    lines = [
        "# alias audit",
        "",
        "Status: active",
        "Date: 2026-07-15",
        "Scope: compatibility alias usage in MW/D32/MX/_matrix.csv.",
        "",
        "| Alias family | Canonical family | Alias rows | Alias DSP-mapped | Canonical rows | Status | Notes |",
        "|---|---|---:|---:|---:|---|---|",
    ]

    for alias, canonical, note in PAIRS:
        alias_total = total.get(alias, 0)
        alias_mapped = mapped.get(alias, 0)
        canonical_total = total.get(canonical, 0)
        s = status(alias_total, canonical_total, alias_mapped)
        lines.append(
            f"| {alias} | {canonical} | {alias_total} | {alias_mapped} | {canonical_total} | {s} | {note} |"
        )

    lines.extend(
        [
            "",
            "## Gate for retirement",
            "",
            "A family can be removed when:",
            "- alias rows are 0 in generated matrix,",
            "- canonical family rows are non-zero,",
            "- strict drift and smoke checks pass.",
        ]
    )

    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
