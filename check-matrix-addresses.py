#!/usr/bin/env python3
"""check-matrix-addresses.py — the published matrix must carry the DSP
addresses its landed map defines.

THE CLASS OF FAILURE THIS EXISTS FOR (S45-3). `MW/D24/MX/_matrix.csv`
carried DspSpi/DspPage/DspAdd/DspAddHex on 0 of its 4,985 rows from the day
the file was generated until S45, while `defs/products/d24/dsp.csv` mapped
3,737 of those cells. Nothing noticed for a year of sessions, because every
check in the intake path asked a different question:

  * `sync-defs.sh` verifies the EXPANSION against `defs.lock`, and the
    expansion has no DSP columns in it by design;
  * `validate-matrix-contract.py` checks MxAdd continuity and the family
    allowlist, neither of which involves a DSP address;
  * `check-contract-drift.sh --strict` asks git whether the file CHANGED,
    and a file that was never right does not change;
  * `gen_dsp.py` validated the product it backfilled and was silent about
    the one it did not.

So the one artefact the console app loads (mx26
`AppContext.ResolveMatrixPath`) could be missing every address it exists to
publish, and each gate would pass, individually correct. The matrix is the
app's only source of DSP addresses: an empty address column is not a
cosmetic gap, it is a D24 that cannot write a single per-strip DSP node
state.

WHAT IS CHECKED, per product with a landed `dsp.csv`:

  1. the matrix carries at least one DSP address if the landed map carries
     any -- the S44-5 class, stated as loudly as it deserves;
  2. every cell the landed map covers and the matrix defines carries an
     address, and it is the map's address, not some other one;
  3. no cell carries an address the landed map does not give it;
  4. the columns add up: DspSpi/DspPage/DspAdd/DspAddHex are filled
     together or not at all, and DspAddHex agrees with DspAdd.

WHICH PRODUCTS ARE CHECKED is asked of `gen_dsp.py --backfill-products`,
so this gate and the tool it gates cannot hold different lists. D12 and D16
are not on it: nothing has landed a `dsp.csv` for them in `defs`, nothing
backfills their matrix, and asserting a contract that does not exist is the
failure mode the no-fallback policy is about. `--propose` writes a map for
them, and a proposal is not a contract.

Usage:
    python3 check-matrix-addresses.py
    python3 check-matrix-addresses.py --tree /path/to/scratch/copy
"""

from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path

ADDRESS_COLUMNS = ("DspSpi", "DspPage", "DspAdd", "DspAddHex")


def read_landed(path: Path) -> dict[str, dict[str, str]]:
    """`defs/products/<p>/dsp.csv`, comment lines stripped, keyed by cell."""
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(l for l in f if not l.startswith("#")))
    return {r["_Cell"]: r for r in rows}


def read_matrix(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def check_product(product: str, matrix_path: Path, landed_path: Path,
                  errors: list[str]) -> str:
    landed = read_landed(landed_path)
    rows = read_matrix(matrix_path)
    defined = {r["_Cell"] for r in rows if r.get("_Cell")}
    covered = defined & set(landed)

    missing_col = [c for c in ADDRESS_COLUMNS
                   if rows and c not in rows[0]]
    if missing_col:
        errors.append(
            f"{product}: {matrix_path} has no {', '.join(missing_col)} "
            f"column. The app reads the address off the matrix by column "
            f"name; a column that is not there cannot be read.")
        return f"{product}: NO ADDRESS COLUMNS"

    with_addr = {r["_Cell"] for r in rows if (r.get("DspAdd") or "").strip()}

    # 1. The S44-5 class, on its own, because it is the one that hid.
    if covered and not with_addr:
        errors.append(
            f"{product}: {matrix_path} carries a DSP address on 0 of its "
            f"{len(defined)} rows, while {landed_path} maps {len(covered)} "
            f"of those cells. The matrix is the ONLY source of DSP "
            f"addresses the app has, so this product cannot write a single "
            f"DSP node state. Fix: MW/D32/DSP/gen_dsp.py backfills every "
            f"product in --backfill-products; run "
            f"./regenerate-dsp-contract.sh.")
        return f"{product}: 0/{len(covered)} addresses — EMPTY"

    # 2/3. The map and the matrix, cell by cell.
    absent = sorted(covered - with_addr)
    if absent:
        errors.append(
            f"{product}: {len(absent)} cells are mapped in {landed_path} "
            f"and carry no address in the matrix "
            f"({', '.join(absent[:5])}{', ...' if len(absent) > 5 else ''})")

    unexpected = sorted(with_addr - set(landed))
    if unexpected:
        errors.append(
            f"{product}: {len(unexpected)} matrix rows carry a DSP address "
            f"that {landed_path} does not give them "
            f"({', '.join(unexpected[:5])}"
            f"{', ...' if len(unexpected) > 5 else ''}). An address no "
            f"landed map names is an address no kernel answers on.")

    wrong: list[str] = []
    ragged: list[str] = []
    for r in rows:
        cell = r.get("_Cell")
        filled = [c for c in ADDRESS_COLUMNS if (r.get(c) or "").strip()]
        if filled and len(filled) != len(ADDRESS_COLUMNS):
            ragged.append(f"{cell} (has {', '.join(filled)})")
            continue
        if not filled:
            continue
        try:
            addr = int(r["DspAdd"])
        except ValueError:
            wrong.append(f"{cell}: DspAdd={r['DspAdd']!r} is not a number")
            continue
        if (r["DspAddHex"] or "").strip().lower() != f"0x{addr:04x}":
            wrong.append(f"{cell}: DspAddHex={r['DspAddHex']!r} "
                         f"does not match DspAdd={addr}")
            continue
        m = landed.get(cell)
        if m is None:
            continue        # already reported as unexpected
        want = (m["DspSpi"], m["DspPage"], m["DspAdd"])
        got = (r["DspSpi"], r["DspPage"], r["DspAdd"])
        if want != got:
            wrong.append(f"{cell}: matrix says chip/page/addr {'/'.join(got)}, "
                         f"the landed map says {'/'.join(want)}")
    if ragged:
        errors.append(
            f"{product}: {len(ragged)} rows fill some address columns and "
            f"not others ({'; '.join(ragged[:5])}"
            f"{'; ...' if len(ragged) > 5 else ''})")
    if wrong:
        errors.append(
            f"{product}: {len(wrong)} rows disagree with the landed map "
            f"({'; '.join(wrong[:5])}{'; ...' if len(wrong) > 5 else ''})")

    return (f"{product}: {len(with_addr)}/{len(covered)} mapped cells carry "
            f"an address ({len(defined)} cells defined)")


def backfill_products(root: Path) -> list[str]:
    """The products whose matrix gen_dsp.py finishes — asked of the tool
    rather than restated here, because a gate holding its own copy of the
    list is how the gap this file exists for stayed invisible."""
    gen = root / "MW" / "D32" / "DSP" / "gen_dsp.py"
    out = subprocess.run([sys.executable, str(gen), "--backfill-products"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"ERROR: {gen} --backfill-products failed:\n{out.stderr}")
    products = [line.strip() for line in out.stdout.split() if line.strip()]
    if not products:
        sys.exit(f"ERROR: {gen} --backfill-products named no product; there "
                 f"is nothing this gate could check.")
    return products


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tree", default=None,
                    help="Repository root to check (default: this script's "
                         "own). A scratch copy is how the negative control "
                         "is run without touching the committed tree.")
    ap.add_argument("--landed-dir", default=os.environ.get("DSP_LANDED_DIR"),
                    help="products/ directory holding the landed maps, "
                         "relative to the tree root. Defaults to "
                         "$DSP_LANDED_DIR, then defs/products.")
    args = ap.parse_args()

    root = Path(args.tree).resolve() if args.tree else Path(__file__).resolve().parent
    landed_dir = root / (args.landed_dir or os.path.join("defs", "products"))

    if not landed_dir.is_dir():
        print(f"ERROR: no landed maps at {landed_dir}", file=sys.stderr)
        return 1
    if landed_dir.resolve() != (root / "defs" / "products").resolve():
        print(f"NOTE: address maps read from {landed_dir} — NOT defs/products. "
              f"These rows have not passed the hub gate.", file=sys.stderr)

    products = backfill_products(root)
    errors: list[str] = []
    print("matrix DSP address check")
    for p in products:
        P = p.upper()
        landed_path = landed_dir / p / "dsp.csv"
        matrix_path = root / "MW" / P / "MX" / "_matrix.csv"
        if not matrix_path.is_file():
            errors.append(f"{P}: {matrix_path} does not exist, but "
                          f"gen_dsp.py backfills this product.")
            continue
        if not landed_path.is_file():
            errors.append(f"{P}: {landed_path} does not exist, but "
                          f"gen_dsp.py backfills this product from it.")
            continue
        print("  " + check_product(P, matrix_path, landed_path, errors))
    for other in sorted(q.name for q in (root / "MW").iterdir()
                        if (q / "MX" / "_matrix.csv").is_file()
                        and q.name.lower() not in products):
        print(f"  {other}: not a backfilled product — skipped (no landed "
              f"dsp.csv in defs, nothing fills its address columns)")

    if errors:
        print()
        sys.stdout.flush()
        print("ERROR: the published matrix does not carry the DSP addresses "
              "its landed map defines:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
