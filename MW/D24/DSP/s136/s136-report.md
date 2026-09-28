provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S136 — the station tools resolve matrix addresses by cell name from the unit's own deployed pack (no flash, no app deploy)

Hub ruling: "cell names are the invariant contract, addresses are per-build
artifacts" / "generate, never transcribe". S135 found `tools/pi/d24_panel.py`
hard-coding `SKIN = 0x1524` / `ENC = 0x1470`, true of MW-D24-2's 2026-08-18
pack alone; after the S131 switch-over the same names are 4698 / 4514.

**Nothing was flashed, no app was deployed, no rail or GPIO state was
touched.** `app` (`matrix-app.service`) was already `inactive` at session
start (stopped by an earlier session) and stayed that way throughout; GPIO26
(AN_EN) `lo`, GPIO27 (CS_M) `hi`, unchanged before and after. The only writes
made anywhere were `tools/pi/*.py` deployed to `/home/app/selftest` via
`deploy-bench-tools.sh` (which took its own `.bak-20260928-013037` backups
first) and reads of `/home/app/config/_matrix.mxc`.

---

## 1. What changed

`tools/pi/matrix_addr.py` (new) resolves a cell name to an address off this
unit's own deployed pack, in the same order `Core/AppContext.
ResolveMatrixPath` uses (findings S45-2): `{HomePath}/config/_matrix.mxc`
packed (the `MXC1` container `defs/tools/mxc_pack.py` defines — magic, a
little-endian length, then the CSV XORed with a fixed key; unpacked here
rather than imported, because `defs/` is not staged on the unit), else
`_matrix.csv`. It parses the same `_Cell`/`MxAdd` columns
`defs/tools/matrix_gen_id.py` does and fingerprints the pack the same way
(`base-id`, sha256 of `name=address` lines, truncated to 12 hex), so a
generation this module reports matches that tool's answer for the same file.

A name absent from the pack raises `CellNotInPack` (`try_resolve()` returns
`(None, reason)` instead, for callers that want a row rather than an
exception) — never a guessed address, never a crash. A pack that cannot be
found or parsed at all is `MatrixPackError`, always fatal: a tool that
cannot read the pack has no business guessing at any of it.

**Converted to name resolution, every hard-coded matrix-bus cell address in
`tools/pi`:**

| file | was | now |
|---|---|---|
| `d24_panel.py` | `SKIN = 0x1524`, `ENC = 0x1470`, `SW_LEFT = 0x138D` | resolved by name; `SW_TALK` added (was absent entirely) |
| `codec4619.py` | `SYS001TEST001 = 0x1526`, `SYS001TEST002 = 0x1527` | resolved by name |
| `d24_bus_probe.py` | `--cell` default `'0x1526'` | default is `codec4619.SYS001TEST001` (resolved); `--cell` still accepts a raw override for ad hoc probing |
| `d24_selftest.py` | `t_ml1`'s message hard-coded `(5414)` | reads the address the probe actually used out of its own JSON (`j['cell']`) |

`SKIN`/`ENC` (and `codec4619`'s two test cells) are treated as **required**:
every generation this tool has run against has carried them, so a pack
missing one is broken, not "not yet switched over", and the tool exits
loudly (`sys.exit('FATAL: …')`) rather than guessing. `SW_LEFT`/`SW_TALK`
are **optional-by-name**: `defs-v2026.09.27`/`.3` cells that do not exist on
packs built before them, and their absence is reported, not fatal.

**`d24_panel.py --mode resolve`** (new mode) prints what the process
resolved and from where — no bus, no matrix-app stop, no hands. This is the
whole of tonight's proof surface; every other mode's behavior is unchanged
except that its addresses now come from `matrix_addr` instead of a literal.

**`--panel left` on a pack without `Sys001SwLeft001`** no longer falls back
to the old pre-S129 "write SKIN too, let a press disambiguate" aliasing
guess (that guess predates the name existing in defs at all, and guessing an
address for a name absent from THIS pack is exactly what the hub ruling
forbids). `loop()` now short-circuits: every row of the left panel comes
back `NO DATA` with `SW_LEFT`'s absence reason, and the bus is never
touched. `cells_for()` gained a defensive check (raises `CellNotInPack`
rather than ever returning `[None]`) in case that short-circuit is bypassed.

Row 92 (`right` panel, talkback) in `d24_panel.py`'s `UNREACHED` table now
says *why* dynamically: "cell not in this unit's matrix" on a pack without
`Sys001SwTalk001`, or "exists but no read/light logic wired to it yet" once
a pack has the name — `Sys001SwTalk001`'s own read/write behavior is S135's
bespoke H1S3 image (still optional) and out of this dispatch's scope; this
row only stopped saying something the switch-over would make untrue.

**`codec4619.py` is not deployed by this change.** It lives in the "pair
drop" (`/home/app/dspboot`, symlinked into the runner's stage) by
`deploy-bench-tools.sh`'s own long-standing convention — a copy in
`/home/app/selftest` "would be read by nothing". Its repo source is fixed
(name resolution replaces the literal) so the next pair drop carries the
fix, but tonight `codec4619.py` on the unit is still the unmodified,
pre-S136 copy; `d24_bus_probe.py`/`d24_panel.py` still work because neither
depends on `codec4619`'s two test-cell constants, only its transport
(`Bus`/`cell_line`/`cell_prefix`/`PORT`), which is unchanged.

## 2. Scope boundary: `tools/pi/dsp4_*.py` is NOT touched, deliberately

Several `dsp4_*.py` tools (`dsp4_matrix_probe.py`, `dsp4_pairgraph.py`, …)
also hard-code 4-hex-digit constants next to a cell-shaped name
(`MTX_ON_BASE = 0x12C6  # Chan001MatrixOn001/002`). These are a different
product's (D32) DSP data-memory offsets, computed from that product's own
`defs/products/d32/dsp.csv` and resolved at BUILD time into the SHARC ELF
map (`dsp4_scope`'s `sym[]` table, already used elsewhere in the same
files) — never from a unit's deployed `_matrix.mxc`. There is no runtime
pack for this module to read on that path, and inventing one to satisfy the
letter of "grep ALL of tools/pi" would be designing a mechanism this
dispatch was not scoped to build, on a unit this session never touched, with
no flash and no test recipe for it. The generator-side guard
(`check-no-hardcoded-matrix-addr.py`) is scoped the same way: it only scans
files that `import codec4619`, which is exactly the D24 CM4-serial-bus
station-tool set, and says so in its own docstring. If a `dsp4_*` tool ever
starts reading a runtime pack the way the D24 tools do, it joins that scope
then, not before — flagged here for the hub rather than silently dropped.

## 3. The generator-side guard

`tools/pi/check-no-hardcoded-matrix-addr.py`: tokenizes every `tools/pi/*.py`
file that `import`s `codec4619` and fails if any code token (never a string,
never a comment or docstring — `tokenize` already tells those apart) is
spelled as exactly four hex digits (`0x` + 4), the shape of every address in
mx26's own `DspAddHex` column. `matrix_addr.py` is exempt (it is where a
`0x` literal is allowed to live — MXC's own magic/parsing). `GUARD_FETCH =
0xFB` and `codec4619`'s `INIT_IMAGE` register bytes do not match (1–2 hex
digits); confirmed no false positive on the fixed tree.

Wired into `deploy-bench-tools.sh`: it runs the guard before comparing or
copying anything and aborts the deploy (exit 4) on a hit, so a literal
cannot reach the unit even if it is reintroduced later.

Negative-control tested: reintroducing `SKIN = 0x1524` as a literal in a
scratch copy of `d24_panel.py` is caught (`d24_panel_negtest.py:85:
0x1524`); the real, fixed tree passes clean.

## 4. Proved on the part, on the OLD pack (MW-D24-2, no switch-over)

`matrix_addr.py`/`d24_panel.py --mode resolve`, run live on the unit against
its own `/home/app/config/_matrix.mxc` (never a copy pulled off it):

```
pack       /home/app/config/_matrix.mxc
generation e80ccab5d6d8
cells      5412
Sys001Skin001        5412
Sys001Enc001         5232
Sys001SwLeft001      ABSENT (cell not in this unit's matrix (generation e80ccab5d6d8): Sys001SwLeft001)
Sys001SwTalk001      ABSENT (cell not in this unit's matrix (generation e80ccab5d6d8): Sys001SwTalk001)
Sys001Test001        5414
Sys001Test002        5415
```

`e80ccab5d6d8` matches `defs/tools/matrix_gen_id.py`'s own fingerprint of the
unpacked pack, independently computed here off a pulled copy. `5412`/`5232`/
`5414`/`5415` match the pre-S136 literals exactly — **the panel station
resolves the same addresses it always has, by name, with no behavior
change** — and `Sys001SwLeft001`/`Sys001SwTalk001` report absent rather than
a guess, matching the acceptance criteria verbatim.

`d24_panel.py --mode loop --panel left --inject /dev/null` on the same pack
(off-unit, no hardware needed for this one): all twelve left-panel rows come
back `NO DATA` with the exact "cell not in this unit's matrix" reason, and
no bus call is ever made (proved by running it with no serial device
present at all).

Unit state after, re-checked: GPIO26 `lo`, GPIO27 `hi`, `matrix-app`
`inactive` — identical to session start; nothing else on the unit was
touched.

## 5. Runbook

`MW/D24/DSP/s131-runbook.md` §6a closed: the address step is now automatic,
no edit is owed to the tools before step 10. Step 10's checklist gained a
first check — `d24_panel.py --mode resolve`'s header must show generation
`f9677e5fae5e` after step 8, with `Sys001Skin001`/`Sys001Enc001`/
`Sys001SwLeft001`/`Sys001SwTalk001` at 4698/4514/5005/5006 and none of them
NOT TESTED any more.

## 6. Deploy record

`deploy-bench-tools.sh`, two passes (guard passed both times; the second was
a one-line cleanup, `matrix_addr._pack()` → a proper `matrix_addr.describe()`
public accessor, no behavior change — re-verified live after): `d24_selftest.py`
`4c63b095`, `d24_bus_probe.py` `91dcec99`, `d24_panel.py` `faf953d8`,
`matrix_addr.py` `d8af1d52`. Backups on the unit: `*.bak-20260928-013037` and
`*.bak-20260928-013350`. Every other staged tool was already byte-identical
and untouched.
