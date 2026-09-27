provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S134 — overnight, NO HANDS: NW4 must never crash; the S131 runbook

**Outcome: both closed.** NW4's crash is root-caused, fixed, and proven with
a full automatic batch from a clean state — no crash, NW4 correctly NOT
TESTED, AL1 PASSES, everything else unchanged. `MW/D24/DSP/s131-runbook.md`
is written, with a dry run of everything that could be dry-run (matrix.h
regeneration and a real rebuild of all three panel MCU images, diffed
against the flashed ones), and one 🔴 open question for the hub where the
runbook's own step 5 turned out not to be the same shape as step 4.

No flashing, no fuses, no app deploy. The unit is left exactly as found:
`app` `b05e9fd5`, AN_EN low, CS_M high, chain SAFE, `d24-testui` active,
`matrix-app` inactive, cumulative self-test state reset.

---

## 1. NW4's crash — root cause, fix, proof

**Root cause.** `NW4_PEER` on this bench is `''` (no gigabit peer — the
driving host's link negotiates 100 Mb/s, documented at length beside
`NW4_PEER` in `tools/pi/d24_selftest.py` since S129). `t_nw4()` already did
exactly the right thing on that condition: return `NOTTESTED` *before*
running anything. The crash was never in that decision — it was two places
downstream in the same file that had never been taught `NOTTESTED` was a
legal verdict, because until now nothing had ever actually returned it in a
live run:

- `TestRun.record()`'s own assertion: `assert verdict in (PASS, FAIL,
  NODATA)` — raised `AssertionError` on `NOTTESTED`, **uncaught**, because
  `run()`'s `try/except` only wraps the call to the test function itself
  (`fn()`), not the `self.record(...)` call after it (`d24_selftest.py`
  around what is now line 498). This is the exact crash S133 hit and
  reported as "a known, pre-existing limitation... nothing to do with this
  dispatch" — it had everything to do with this dispatch.
- `summary()`'s two local tallies (`tally = {PASS: 0, FAIL: 0, NODATA: 0}`
  and the per-item `rank = {PASS: 0, NODATA: 1, FAIL: 2}`) would have thrown
  `KeyError` on the same verdict immediately afterward, had the assertion
  not fired first.

Neither gap was reachable before tonight: NW4 is the only test in the whole
file that ever returns `NOTTESTED`, and nothing on this bench had run it
since `NW4_PEER` was set to `''` with a live `--auto-only`/`--local` pass
that reached NW4 and then also reached `summary()`.

**Fix (`tools/pi/d24_selftest.py`):**
- `record()`'s assertion now allows `NOTTESTED` alongside `PASS`/`FAIL`/
  `NODATA` — it was already the file's own documented fourth verdict
  (`NOTTESTED = 'NOT TESTED'`, commented "outranks nothing" since S129); the
  assertion just hadn't been told.
- `summary()`'s row/item tallies and the per-item worst-verdict `rank` both
  gained a `NOTTESTED` entry (ranked below `PASS`, per the same "outranks
  nothing" comment — any real measurement on the same catalog item wins).
  The two summary print lines now report a NOT TESTED count alongside PASS/
  FAIL/NO DATA.

No change to `d24_runall.py`: its own `RANK`/`stamp_auto()`/
`record_not_run()` already handled `NOTTESTED` correctly (it's `d24_runall`'s
own catalog-level classification for rows the wizard never routes to the
subprocess at all) — the entire bug was inside `d24_selftest.py`'s own
single-subprocess bookkeeping, never reaching `d24_runall.py` at all because
the crash happened first.

**Proven on the unit (MW-D24-2).** Deployed via
`tools/pi/deploy-bench-tools.sh` (only `d24_selftest.py` differed; the other
14 tools matched — no repeat of S132's stale-tool trap). State reset
(`--reset-only`), then a real `--auto-only` pass driven the same way S133's
proof was (`d24_runall.py` directly — the same `RunLock` door the glass's
own START uses, per its own docstring: "the factory screen's START launches
`d24_patch.py --run`, which is the whole ruled sequence and therefore this"):

```
NW4 ...
-- 2026-09-27T23:37:09Z NW4 took 0.0 s
  NW4       NOT TESTED no gigabit peer on this bench
...
AL1       PASS     PASS base -46.0 tone -29.7 SNR 16.3 dB THD -24.9 dB 5.67%
...
TEST       VERDICT  MEASURED
------------------------------------------------------------------------------
...
NW4        NOT TESTED
------------------------------------------------------------------------------
rows:  36 PASS / 0 FAIL / 14 NO DATA / 1 NOT TESTED  (51 rows)
   .. auto set finished in 153 s
pass 1: 23 PASS / 0 FAIL / 13 NO DATA / 0 ignored / 0 skipped / 87 not tested (of 202 rows) in 154 s
```

No traceback, no `RUNNER ERROR`, exit code 0, `auto set finished in 153 s`
(never `DIED`). AL1 PASSED in the same pass. Full log:
`MW/D24/DSP/s134/logs/s134-auto-run-full-batch.log`.

State reset again afterward (`--reset-only`) so tomorrow's window starts
clean at pass 1. Unit verified after: AN_EN (GPIO26) low, CS_M (GPIO27)
driven high, chain marker SAFE, no `d24_runall.py`/`d24_selftest.py` process
left running, `app` untouched (`b05e9fd5`).

---

## 2. The S131 runbook

`MW/D24/DSP/s131-runbook.md`. Read `mx26 docs/investigation-matrix-generation-2026-09-27.md`
first (as instructed) — its numbers were independently reproduced here (see
below) rather than just copied.

**Confirmed:** dsp's own `defs.lock` already pins the target generation
(`D24_MATRIX_GEN=f9677e5fae5e`), and `defs-v2026.09.27.4`/`.5` touch only
`mic-gain-codes.csv` and `defs-publish.sh` portability — the D24 matrix is
identical to `.3`. This repo's own `MW/D24/MX/_matrix.csv` reproduces the
published matrix's name→address mapping exactly (`matrix_gen_id.py` reports
the same base-id and the same `Sys001Skin001`=4698; only the exact CSV bytes
differ, from `gen_dsp.py`'s DSP-backfill columns) — it was used as tonight's
CSV source instead of pulling a fresh Dropbox copy, and the runbook says so
and tells tomorrow's run to re-verify hashes against the live Dropbox file
rather than trust this session's copy.

**Dry-run, not paper-only.** Beyond writing the ordered steps + rollback +
timing the dispatch asked for, this session actually:
- Regenerated `matrix.h` from the CSV (5006 `#define`s) and confirmed
  `matrix_gen_id.py --compare` reports `ALIGNED (full-id f9677e5fae5e)`.
- Diffed it against the currently-flashed `matrix.h`: 3309 names only on the
  unit, 2903 only in the target, 2103 shared, **0 shared at the same
  address** — independently reproduces the mx26 doc's own count (off by
  exactly the 2 new cells, since that doc compared against an older defs
  tag).
- Built all **three** panel MCU images from scratch copies of
  `/home/app/fwbuild/{H1S1,H1S3,H1S4}/` under `/home/app/s134fw/` (same
  toolchain and the same one-line Windows-linker-path makefile fix S129
  proved byte-identical with): H1S4 gets `Sys001SwLeft001` bound into
  `MATRIX[]`/enum with all 15 `rsw[]`/`wled[]` entries repointed off
  `Sys001Skin001`; H1S3 gets `Sys001SwTalk001` declared (binding deferred,
  see below); H1S1 gets the header swap alone. All three built clean,
  produced `.hex`→`.shex` via `fwbuild/hex2shex.py`, and are archived under
  `MW/D24/DSP/s134/gen/`. Nothing was flashed; the scratch trees were
  deleted after.

**One finding changes the runbook's own step 5.** `Sys001SwTalk001`'s defs
note specifies bitmask LED writes (both indicators independently, "3 = both
lit") and edge-reported switch reads — neither of which the existing
`rsw[]`/`wled[]` one-hot radio-scan mechanism can express; it needs new
firmware logic, not a table entry, unlike the H1S4 case it otherwise mirrors.
This was not invented or guessed at speed — it's recorded as a 🔴 open
question in the runbook (§7) with three concrete options for the hub,
per the no-question-dialogs rule.

---

## 3. What's on the unit now

Unchanged from before this session except the deployed
`tools/pi/d24_selftest.py` (verified md5 `fc7588ab`, backed up as
`d24_selftest.py.bak-20260928-003536` on the unit by `deploy-bench-tools.sh`
itself). `app` `b05e9fd5`, matrix pack, and all three panel `.shex` images:
untouched. Self-test cumulative state: reset (next pass is pass 1).
