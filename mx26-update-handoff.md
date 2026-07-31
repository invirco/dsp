# mx26 update handoff — superset cells + GrpPeq→GrpGeq rename

Prepared 2026-07-31 for the mx26-side edit (while the CCES licence is
pending). Everything below is expressed against mx26's actual flow:
`mx_master.csv` (SOT) + product defs (`d24.csv`/`d32.csv`) →
`tools/def_master.py` → `d2x-mx-master.csv` → (this repo)
`sync-from-mx26.sh` → `_matrix.csv`. The dsp-repo side is ALREADY
staged: the 7 new families are in `matrix-families-allowlist.txt`, and
the DSP cells exist at fixed addresses (chip 2, 1818–1837 for the aux
inputs; 1840–1951 for the group GEQs) — mx26 only needs to define the
matrix cells; the backfill matches them by `_Cell` name.

## 1. New cell families (src/sw/app/config/mx_master.csv)

Rows modeled on the existing `Usb[1-1]On/Level` pair (data width 2 for
On, 255 + level table for Level):

```csv
CodecAux[1-1]On[1-1],1,,,,false,Codec aux input on/off,,,2,,,,,,,,,,,,,,,,,,,,
CodecAux[1-1]Level[1-1],1,,,,false,Codec aux input level,,,255,,,,,,,,,,0=-20/127=6/[Lin],,,,,,,,,,
Pi[1-1]On[1-1],1,,,,false,Pi playback input on/off,,,2,,,,,,,,,,,,,,,,,,,,
Pi[1-1]Level[1-1],1,,,,false,Pi playback input level,,,255,,,,,,,,,,0=-20/127=6/[Lin],,,,,,,,,,
Snk[1-8]On[1-1],1,,,,false,Snake return input on/off,,,2,,,,,,,,,,,,,,,,,,,,
Snk[1-8]Level[1-1],1,,,,false,Snake return input level,,,255,,,,,,,,,,0=-20/127=6/[Lin],,,,,,,,,,
```

Matching dsp-side cells (already live): `CodecAux001Level001/On001`,
`Pi001Level001/On001`, `Snk001..008Level001/On001`.

## 2. def_master.py PREFIX_RULES + product keys

New prefixes with their own gate keys (suggested names — pick your own
vocabulary, the dsp side doesn't care):

```python
"CodecAux": ("io", "io.codecaux"),
"Pi":       ("io", "io.pipcm"),
"Snk":      ("io", "io.snake"),
```

Product defs:
- `d24.csv`: `io.codecaux,1` and `io.pipcm,1` (no `io.snake` — D24 has
  no snake; the dsp side scope-gates Snk nodes off on D24 anyway).
- `d32.csv`: `io.codecaux,1`, `io.pipcm,1`, `io.snake,1`.

Caveat: check the `io` scope exists in the def vocabulary the way
`io.bt`/`io.card` do; otherwise reuse whichever scope fits.

## 3. GrpPeq → GrpGeq rename

Current master row (line ~239 of the generated d32-mx-master.csv; the
SOT row lives in mx_master.csv):

```csv
Grp[1-4]Peq[1-12],1,,,,,Group 28-band graphic EQ gain,,,65,32,,,,,,,GrpEq,,0=20/127=20000/[Log],,,,,,,,,,
```

- Rename `Peq` → `Geq` (dsp-side cells are `Grp00xGeq001..028`).
- **Band count choice**: the DSP node is a 28-band GEQ; the matrix
  currently exposes 12. `[1-12]` keeps today's surface (backfill works
  fine — bands 13-28 stay DSP-only); `[1-28]` exposes the full GEQ.
  Your call — the dsp side needs no change either way.
- **Suspected pre-existing bug while you're there**: this row's Table
  is `0=20/127=20000/[Log]` — a frequency table on a *gain* cell. The
  Main GEQ gain row uses `0=-12/127=12/[Lin]`, and the dsp side
  publishes the Geq cells with `0=-12/127=12/[Lin]`. Looks like a
  copy-paste from a frequency cell.
- Check any `FUNC_GATES` entry for `^Peq` under the `grp` scope and
  rename alongside.

## 4. After your mx26 push — dsp-repo steps (this side)

1. `git -C ~/mx26 pull`
2. `./regenerate-dsp-contract.sh --update-lock` (contract bump; record
   per release-notes-contract-convention.md)
3. Expect: the 48-cell GrpPeq backfill moves to GrpGeq automatically;
   the 20 aux-input cells gain DSP columns; "not in _matrix" INFO
   drops accordingly.
4. Cleanup once the rename is in: remove `GrpPeq` from
   `matrix-families-allowlist.txt`, drop `--enable-grp-geq-alias` from
   `regenerate-dsp-contract.sh`, and delete the alias block in
   `MW/D32/DSP/gen_dsp.py` (`ENABLE_GRP_GEQ_ALIAS`).

Already staged here (committed): `CodecAuxLevel/On`, `PiLevel/On`,
`SnkLevel/On`, `GrpGeq` added to the allowlist (GrpPeq retained until
the rename lands).
