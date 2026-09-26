provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S119 — retire the meter station from RUN ALL; deploy the corrected catalog

Hub dispatch `tasks.md` 2026-09-26 14:57Z. Built on S117 (`d24_runall.py`) and
S118 (silent handback, no catalog/app/CPLD/H1S1/`pair.conf` change). Ruling:
PW 2026-09-26 — component and assembly faults are the assembler's QC job, not
a lid-off bench step; the unit test stays hardware proof, fastest, fewest
manual steps.

---

## 1. The meter station is out

`STATIONS` in `tools/pi/d24_runall.py` no longer carries `M7` ("Meter checks,
lid off"): no card, no rails, no dialog, no "with the meter, check..." prompt.
Its 24 rows moved to a new catalog group, `QC`, and are classified NOT RUN in
`classify()` — never silently dropped (S117 §1) — with a per-row reason in a
new `QC_REASON` table, on the same footing as the existing M6/M8 not-run
buckets.

Every row is one of:

* **covered by \<test\>** — an automatic test elsewhere in the catalog already
  proves the connector, because the header's own nets (per
  `defs/products/d24/d24-hw-inventory.csv`) are exactly what that test
  exercises (`ITEMS` / `fw.csv` in `tools/pi/d24_selftest.py` gives the
  net-to-test map). Named in plain English, not by bench test id — the report
  carries no Matrix-internal vocabulary (`INTERNAL`, checked by
  `--check-md`), so "AS-CPLD" is "the clock master test", not the code.
* **board-level test at the assembler** — nothing in this catalog proves the
  connector, so it is the assembler's job, not a bench one. No row is
  reworded beyond this fixed phrase (PW: "no designators beyond what the row
  already names").

| row | connector | nets (from `d24-hw-inventory.csv`) | wording |
|---|---|---|---|
| 153 | Analog J11 (power link / header) | `+5V` link | board-level test at the assembler |
| 163 | Analog J56 (board header) | generic header | board-level test at the assembler |
| 164 | DSP PCBA J1 (power link / header) | `C1`/`L0` clock, `LOGIC_AD/DA` bus | covered by the clock master test |
| 165 | DSP PCBA J2 (power link / header) | `C1`/`L0` clock, `LOGIC_AD/DA` bus | covered by the clock master test |
| 166 | DSP PCBA J3 (power link / header) | `CS_C`, `CS_M`, both chips' SPI2 `SS`/`RDY` | covered by the converter-select, mic-gain-latch and audio-processor select/ready tests |
| 167 | DSP PCBA J4 (power link / header) | identical to J3 (duplicate header) | covered by the converter-select, mic-gain-latch and audio-processor select/ready tests |
| 168 | DSP PCBA J6 (power link / header) | both chips' SPI2 `SS`/`RDY`, `I2C1` | covered by the audio-processor select and ready tests |
| 169 | Digital J4 (power link / header) | CM4 USB hub port 2 (internal, unexposed) | board-level test at the assembler |
| 170 | Digital J5 (board header) | GND only | board-level test at the assembler |
| 171 | Digital J6 (board header) | GND only | board-level test at the assembler |
| 172 | Digital J7 (power link / header) | Ethernet magjack — the same connector as row 128 | covered by the network link/error-counter/packet-loss/throughput tests |
| 173 | Digital J10 (power link / header) | CM4 USB hub port 1 (internal, unexposed) | board-level test at the assembler |
| 174 | Digital J14 (debug / test header) | SWD programming header | board-level test at the assembler |
| 175 | Digital J15 (debug / test header) | `TEST1`-`TEST4` bench test points | board-level test at the assembler |
| 177 | Digital J20 (board header) | GND only | board-level test at the assembler |
| 178 | Digital J21 (board header) | generic header | board-level test at the assembler |
| 179 | Digital J22 (power link / header) | `PI_SD_*` — no automated fixture claims this bus | board-level test at the assembler |
| 180 | Digital J23 (debug / test header) | `PI_RPIBOOT` — flashing-mode entry only | board-level test at the assembler |
| 181 | Digital J24 (power link / header) | CM4 module B2B #1 | covered by the compute-module test |
| 182 | Digital J25 (power link / header) | CM4 module B2B #2 | covered by the compute-module test |
| 183 | Digital J26 (board header) | GND only | board-level test at the assembler |
| 184 | Digital J27 (power link / header) | HDMI1 (placeholder, not fitted) | board-level test at the assembler |
| 186 | Digital J31 (power link / header) | power switch | board-level test at the assembler |
| 187 | Digital J32 (debug / test header) | power switch's own SWD header | board-level test at the assembler |

**Why the DSP PCBA and CM4 rows are the two "covered by" clusters, and why
nothing else is.** Every net on DSP PCBA J3/J4/J6 already has its own
dedicated automatic test: `CS_C`→CC1/CC2, `CS_M`→MC1/MC2/MC3, both chips'
SPI2 `SS`→DC1/DC2-CS1/CS2, both chips' SPI2 `RDY`→DY1-RDY1/RDY2 (`fw.csv`
Dsp1/Dsp2/RdyDspA/RdyDspB/MicGainLatch/Codec). J1/J2 carry the CPLD's own
clock and logic-bus lines, which AS-CPLD's "clocks present and locked" check
cannot pass without. J24/J25 are named in `build-d24-connector-status.py`'s
own assemblies table as the CM4's "2×100 B2B" module connectors, proven by
AS-CM4 (the unit up and SSH-reachable). J7 is the same physical magjack as
row 128, already NW1-4. Every other header's nets are either bare GND,
unnamed net numbers, a debug/programming header used only off-line, or (J22)
a bus with no automated test naming it — so they default to the assembler.

## 2. Proof, on MW-D24-2

Deployed `d24_runall.py` and the new `test-catalog.csv`, then ran RUN ALL
(`--autoskip --no-review`, three times while the wording was being fixed —
see finding S119-1) with the unit as S118 left it (`matrix-app` inactive,
`d24-testui` active):

* **One fewer station.** `STATIONS` has five entries (`M1`, `M2`, `M3`,
  `M5`, `M4`); the run's own console output and the station cards it put up
  show only Foot Pedal / Rear panel sockets / Analog loopback — no "Station
  6 — Meter checks, lid off" card, no meter prompt, anywhere in three runs.
* **202 rows, every time.** `pass 5: 22 PASS / 1 FAIL / 11 NO DATA / 1
  ignored / 53 skipped / 114 not tested (of 202 rows)` — no row renumbered,
  none dropped.
* **All 24 QC rows carry their new wording** in the final report
  (`s119-report3.md`, row table checked directly): 8 "covered by ..." and 16
  "board-level test at the assembler", verbatim as designed.
* **`--check-md` on the final report: clean — no Matrix-internal
  vocabulary.** The first two runs were not (finding S119-1): fixed before
  redeploying a third time.

### Finding S119-1 — two bugs the proof run caught

1. **`classify()` order bug.** Row 153 (Analog J11) has `automation` `—`, so
   the `r.automation in ('', '—', '-')` branch caught it before the new
   `r.group == 'QC'` branch ever ran, and it printed the generic "no test is
   declared" reason instead of "board-level test at the assembler." Fixed by
   moving the `QC` check first in `classify()`.
2. **Stale verdicts never clear (real bug, not just this session's).**
   `State.put()`'s rank gate (`RANK[verdict] <= RANK.get(e['verdict'], 9)`)
   ranks `SKIPPED` (2) as "better" than `NOT TESTED` (3), so a row already
   `SKIPPED` at the old meter station in an earlier pass kept that verdict
   and its stale "run it when what it needs is at the bench" reason forever
   — `record_not_run()`'s new `NOT TESTED` could never outrank it. 23 of the
   24 QC rows hit this on MW-D24-2's own accumulated state (pass 3 of this
   session's own testing). Fixed with `State.put(..., force=True)`, used
   only by `record_not_run()`: NOT TESTED there is the catalog's own
   classification, not a graded measurement, so it must land regardless of
   rank. The old entry is kept in `history`, so nothing is lost from the
   report. **This bug pre-dates S119** — any row moved into M6/M8/QC after
   having been run or skipped under an older catalog would have the same
   stale-verdict problem; S119 only found it because it is the first session
   to move a live unit's rows into a new not-run bucket.
3. **Report wording must not leak bench test ids.** The first `QC_REASON`
   draft named tests by id (`AS-CPLD`, `MC1-3`, `DC1/DC2-CS1/CS2`,
   `NW1-4`) and relied on `scrub()`'s token substitution to plain-English
   them for the report. `scrub()`'s regex requires the token be bounded by
   non-alnum/non-dash characters, so `MC1-3` and `NW1-4` (both trailing a
   dash) never matched and leaked raw into the human page, and `DC1/DC2-
   CS1/CS2` matched only its middle token and left the text garbled.
   `--check-md` caught both `MC1` instances and one `NW1`. Fixed by writing
   `QC_REASON` in plain English directly (no test ids at all), matching how
   every other reason in this file is written.

## 3. The corrected catalog (S117-1, fixed hub-side)

Regenerated `test-catalog.csv` from mx26 `83f76b8`
(`tools/d24/build-d24-test-skin.py`, `--keys` from
`build-d24-connector-status.py --export-keys`, `--spec
docs/spec-d24-selftest.md`, `--runner` this repo's `tools/pi/d24_selftest.py`).
`--check`: **0 violations over 202 rows** (mx26 `7bb7c84`'s citation-shift fix
holds).

Diffed every column against S116's catalog. Only the five corrected columns
changed (`explain`, `manual`, `spec_section`, `short`, `pass_when`) plus two
that the dispatch flagged as already disputed:

* **`covers` (16 rows, 8 pairs) — the fresh generator is right.** S116 had
  hand-added eight "nine pairs" (S116 Q5) entries, e.g. row 102 covering 202
  and 202 covering 102, so that `stamp_auto()`'s partner-row stamping would
  carry a verdict from one to the other. It never fires: both rows in every
  one of these pairs already declare the **same** `tests` (e.g. `ML1,ML2`
  on both 102 and 202), so `d24_selftest.py`'s `record()` writes each of them
  its own direct result row per `ITEMS[test]` entry, and `stamp_auto()`'s
  guard (`if by_key.get(p.key): continue`) skips the partner-stamp path
  because the partner already has its own direct reading. The S116 pairs
  were inert, not wrong in effect, but they assert a stamping relationship
  that never triggers. Adopted the fresh, self-only `covers` for all 202
  rows.
* **`remedy` (2 rows: 127, 203) — the fresh generator is right.** S116's
  remedy text for the HDMI FPC / TFT display rows still carried an "HD0-2:
  The soak FAILs only if..." clause for a test retired in S116 itself
  (`ITEMS` comment: "HD0-2 (the 3600 s dropout soak) is RETIRED (PW ruling,
  S116 Q2)"). S116's own catalog kept the stale clause; the fresh build
  correctly drops it, since `HD0-2` is no longer a runner test.

`group`/`order` carried over from S116 verbatim, except the 24 rows moved to
`group=QC` per §1; `order` is untouched everywhere, including on the moved
rows.

Rows 133, 134, 198 and 202, on the glass DETAIL page (their own `pass_when`
in the new catalog):

* **133** (Digital IEC Power Inlet): `PM-IEC: mains present at the inlet;
  +12 V at the Digital board entry J16/J19 within spec`
* **134** (Digital Power Switch): `PS-PWR: the unit powers down cleanly (the
  power MCU's save-and-shutdown contract completes) and comes back up to a
  booted app, both times`
* **198** (Assemblies ADC AK5558 ×3): `AS-ADC: U39 and U60 lanes alive and
  not stuck-at; U15's eight lanes reported as dead (known)`
* **202** (Assemblies S MCU H1S1): `ML1: three identical, well-formed
  answers within the bus timeout\nML2: non-zero, equals the version in
  /home/app/firmware/H1S1.shex's manifest. INFORMATIONAL (S99): does not
  gate the row — ML1 already`

## Deployed

`/home/app/selftest/`:

* `d24_runall.py` `f2cb40e76d22399c3972a1586d99dd58` (rollback
  `.bak-s119-pre` = `d46962b528106612fa0c66f6f0d6737b`, S117/S118's)
* `test-catalog.csv` `28ed8a28ba9916548781567ec8255a5b` (rollback
  `.bak-s119-pre` = `96694c1357912229ad6e5b4feaf33884`, S116's)

`d24_selftest.py`, the app, the CPLD, H1S1 and `pair.conf` NOT touched;
`defs.lock` unmoved, no contract bump owed.

**Unit as left:** `matrix-app` inactive, `d24-testui` active, AN_EN
(GPIO26) `op -- pd | lo`, CS_M (GPIO27) `op -- pd | hi` DRIVEN, SAFE image
verified 200/200 — the same silent-handback shape S118 left it in.

Reports: `MW/D24/DSP/s119/test-catalog.csv` (deployed), console logs and the
three on-bench reports referenced above are in the session's own scratch
directory, not committed (factory-run artifacts, not contract or code).
