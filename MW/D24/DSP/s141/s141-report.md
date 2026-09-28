# S141 report — NO FLASH: post-S131 tool drift, codec4619 pair drop, auto pass, S131 evidence

## 1. Station-tool deploy

`./deploy-bench-tools.sh` reported three DIFFERS: `d24_runall.py`,
`d24_panel.py`, `d24_live.py` (S137's changes had never reached the unit).
Guard (`check-no-hardcoded-matrix-addr.py`) ran clean first. Deployed and
re-verified; backups `*.bak-20260928-123626` in `/home/app/selftest`.

## 2. `codec4619.py` pair-drop drift — root cause and fix

**Root cause:** `d24_bus_probe.py` imports `codec4619` from
`/home/app/dspboot/codec4619.py` by absolute path — that directory is the
pair drop, never covered by `deploy-bench-tools.sh`'s `TOOLS`/`$DEST` list
because the runner stages it as a symlink, not a copy. The unit's copy was
still the pre-S136 version, literal `SYS001TEST001 = 0x1526` (5414). The
current pack (generation `46109e9fb812`) resolves `Sys001Test001` to 4361, so
every `--mode cell` read against 5414 got NO DATA.

**Also found:** `check-no-hardcoded-matrix-addr.py`'s guard, written in S136
specifically to catch this class of bug, never actually scanned
`codec4619.py` itself — it only scans files that `import codec4619`, and
`codec4619.py` does not import itself. The S136 literal sat in the one file
the guard exists for, undetected, for two sessions.

**Fixed:**
- Backed up the unit's stale `codec4619.py`
  (`/home/app/dspboot/codec4619.py.bak-20260928-123634`), then copied this
  repo's name-resolving `codec4619.py` and its `matrix_addr.py` dependency
  into `/home/app/dspboot/`. Verified live: `matrix_addr.py --describe` →
  generation `46109e9fb812`, 5767 cells; `matrix_addr.py Sys001Test001
  Sys001Test002` → 4361 / 4362, matching the pack. `codec4619.py --test`
  resolved both names at import time and only failed later on
  `/dev/serial0` busy (matrix-app holds the port — expected, not touched).
- `check-no-hardcoded-matrix-addr.py`: `codec4619.py` is now scanned
  unconditionally (`needs_scan()`), not gated on self-import. The bare
  "any 4-hex-digit NUMBER token" scan false-positived on `cell_prefix()`'s
  genuine bitmasks (`0xF000`..`0xFFFF`) the moment the file was scanned
  directly, so the literal check was narrowed to the actual bug shape — a
  4-hex-digit literal **assigned directly to a bare name**
  (`NAME = 0xNNNN`), which is what both `SYS001TEST001 = 0x1526` and the
  original `SKIN = 0x1524` look like, and what `cell_prefix()`'s inline
  tuple literals do not. Verified: current `codec4619.py` passes; a
  simulated re-introduction of `SYS001TEST001 = 0x1526` is still caught.
- `deploy-bench-tools.sh`: added a `PAIRDROP` list (`codec4619.py`,
  `matrix_addr.py`) checked/deployed straight to `/home/app/dspboot`
  (`$DSPBOOT_DEST`), same md5/backup/re-verify discipline as the existing
  `TOOLS`/`$DEST` loop, refactored into a shared `sync_set()` function so
  both destinations share one code path. `--check` now reports both sets;
  ran clean after the fix (`nothing to deploy`).
- Grepped `/home/app/dspboot` and `/home/app/selftest` for other
  `0x15xx`/`54xx`-shaped literals: everything else found is either
  `codec4619.py`'s own non-address constants (one/two hex digits, e.g.
  `0xFB`, `0xC3`), historical narration in docstrings/comments already
  describing the fixed bug (`d24_panel.py`, `matrix_addr.py`), or unrelated
  (`d24_runall.py`'s `secs_words()`, `v < 5400` seconds, not a cell). No
  other real literal found.

## 3. Fresh auto pass

`d24_runall.py --dir /home/app/s141fw/pass1 --catalog
/home/app/selftest/test-catalog.csv --tools /home/app/selftest --csv
/home/app/s141fw/pass1/results.csv --auto-only --no-review --app-restart`,
launched detached, did not touch `/home/app/selftest/runall/state.json` (the
unit's own cumulative state — a separate `--dir` gives an isolated
`state.json`, nothing was reset).

Result: **ML1, ML-M, CC1, CC2 all PASS** (were NO DATA in S131's `pass2`) —
confirms the codec4619.py fix live:
- `ML1`: `Sys001Test001 (4361)` × 3, identical replies.
- `ML-M`: `S_TEST` identities all read (`H1S1`/`H1S3`/`H1S4`).
- `CC1`: `05H = 0xBB`.
- `CC2`: write/read-back/restore round-trip on `05H` via `MGN2R`.

`NW3` FAILed (5% loss over 3 passes against both the bench host and gateway)
— this is the known bench IP clash (192.168.1.211 answers from both the dsp
machine's `ens9` and an LG TV on the LAN, per S131's dispatch note).
Recorded, not fixed. Full pass: 23 PASS / 1 FAIL (NW3) / 99 not tested
(197 of 202 catalog rows; the rest are MANUAL rows this `--auto-only` pass
does not touch). Archived: `MW/D24/DSP/s141/pass1/`.

Unit state before and after: `app` md5 `dfebca8275940e68b6ec906c6e8f44fe`
(unchanged), AN_EN (GPIO26) low, matrix-app active.

## 4. S131 evidence archive

Archived under `MW/D24/DSP/s131/` — see `MW/D24/DSP/s131/s131-report.md` for
the full account: the hub's `~/s131/H1S1` rebuild (hex/shex/matrix.h,
including the pre-S131 byte-for-byte reproduction that proved the source
tree sound), the unit's `H1S3-B` talkback-variant-B rebuild, and both of
S131's auto-pass reports (`pass/`, `pass2/`).

`s139-report.md`'s H1S1 bullet marked WRONG SOURCE (its `8067f1d4…` `.shex`
was built from the unit's then-stale `/home/app/fwbuild/H1S1` and is what
regressed ML1/CC/MC during S131). `s131-runbook.md` step 6 carries the same
correction. `/home/app/fwbuild/H1S1`'s `matrix.h`/`matrix.cs`/`main.c`
synced from `~/build-h1s1` on the unit (old stale copies kept as
`*.bak-s141-stale-20260928-124440`) so a future on-unit rebuild from that
path can no longer reproduce the stale image.

## Rules followed

NO flashing, no app deploy. AN_EN left low, matrix-app left active. No
dialogs opened.
