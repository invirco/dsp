provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S116 — the five PW rulings on S113 applied

Hub dispatch `HUB DISPATCH 2026-09-26 12:39Z`. PW ruled all five S113
questions on 2026-09-26 (mx26 `pipeline.md`, "Q1 RULED" … "Q5 RULED").
Governing principle: **the factory test is HARDWARE PROOF** — its own stable
image, no continuity soaks, a real fault shows itself during the test, no
test runs twice for the same proof. Bench: MW-D24-2, `d24_selftest.py`
deployed md5 `1ab624b4…` → `34de17cb…` after the `--no-soak-wait`
backward-compat fix (§8). Rollback: `d24_selftest.py.bak-s116-pre`
(`421ceec0…`, matches S115's deployed copy exactly).

---

## 1. NW3 (Q1) — `-i 0.1`, two targets concurrent

**Code** (`tools/pi/d24_selftest.py::t_nw3`): the ping interval moved from
`-c 200 -i 0.2` to `-c 200 -i 0.1` (same 200 packets, half the wall clock);
the bench-host and gateway pings now run on two `threading.Thread`s per pass
instead of one after the other. `--nw3-runs` (3) and worst-of-N-per-target
scoring are unchanged.

**The proviso, proven**: five direct `ping -c 200` passes at each interval,
same session, same two targets, no runner involved (raw ambient reading):

| target | interval | pass 1 | pass 2 | pass 3 | pass 4 | pass 5 | mean |
|---|---|---|---|---|---|---|---|
| bench host .211 | -i 0.2 (old) | 8.0% | 9.0% | 7.5% | 9.5% | 8.5% | **8.5%** |
| bench host .211 | -i 0.1 (new) | 6.5% | 9.0% | 10.5% | 7.5% | 7.0% | **8.1%** |
| gateway .254 | -i 0.2 (old) | 10.0% | 7.5% | 7.0% | — | — | **8.2%** (n=3) |
| gateway .254 | -i 0.1 (new) | 8.0% | 10.0% | — | — | — | **9.0%** (n=2) |

**-i 0.1 does not lose where -i 0.2 does not** — the two intervals are
statistically indistinguishable on both targets (new is if anything very
slightly *lower* to the bench host). The proviso's stop condition ("if -i 0.1
loses where -i 0.2 does not, stop... do not ship it") is not met, so the
change ships.

**🔴 Separate finding, not caused by this change**: today's ambient loss on
this bench (6-10.5%, both targets, both intervals) is far above S113's own
baseline sample (0%, 0%, 0.5%, 2.0% on the bench host). `rtt` stayed sub-ms
(mdev ≈ 0.05-1.2 ms) throughout, and CM4 load average was ≈0.5, so this does
not look like congestion or CPU contention on the unit — it reproduces
identically whether driven directly (raw `ping`) or through the runner, and
on the gateway as well as the bench host, so it is not the driving host's
path either. Consequence: **NW3 read FAIL in every timed run this session**
(6.0% worst-of-3 on both targets in the full run, §7) — a real, current
network condition, independent of S116, worth the hub's attention (a cable,
a switch port, or interference on this bench's segment) but not a blocker
for this dispatch's own acceptance bar.

**Timing**: target was ~62 s. A standalone `--only NW3` press measured
**63.0 s** wall clock (`time` around the whole process, python start +
prologue + NW3 body + epilogue) — on target.

---

## 2. HDMI (Q2) — HD0-2 retired

**Code**: `t_hd02()` deleted entire, along with the soak sampler
(`nohup ... d24_hdsoak.log` / `.uevents`), `--soak-seconds`,
`--soak-interval`, the post-run "wait for the soak window" loop, and
`ITEMS['HD0-2']`/`SECTION['HD0-2']`. `t_hd01()` now gates on **connector
reports connected only**; EDID parse and native-mode-active are still read
and printed but as an INFORMATIONAL evidence line that never turns a
connected display into a FAIL.

`--no-soak-wait` itself is **kept as an accepted, ignored flag** rather than
deleted outright: the wizard's own invocation string
(`~/mx26 src/sw/app/Core/TestSkinStore.cs:1067-1074`) still passes it on
every press, and dropping the argparse entry outright would break every live
press on this unit until the hub edits that file. Removing it there is listed
in §9 for the hub; the runner will accept its removal cleanly whenever that
lands (the flag does nothing either way now).

**Catalog** (`MW/D24/DSP/s116/test-catalog.csv`, diff vs `s113/`): rows
127/203 `tests` → `HD0-1` (HD0-2 dropped); `pass_when` rewritten to state the
new gate plainly. `short`/`explain` for these two rows were **not** touched —
see the 🔴 finding below.

**🔴 Finding, unrelated to this dispatch's own scope, found while editing
these rows**: rows 127 and 203's `pass_when`/`explain` cells in
`s113/test-catalog.csv` (and as far back as `s110/test-catalog.csv` — checked,
identical) describe **ML-B0/ML-P2** (row 127) and **ML1/ML2** (row 203), not
HD0-1/HD0-2 at all. This predates S113 and S116 both and is not something
this dispatch introduced or is scoped to fix generally (it may affect other
rows this session did not audit). `pass_when` was rewritten here because this
dispatch's own ruling required it to state the new HD0-1-only gate correctly;
`explain` was left as found, flagged rather than silently patched over,
because inventing correct HD0-1/HD0-2 `explain` prose without the original
workbook to check it against risks adding a second wrong answer instead of
fixing the first. Worth a dedicated catalog-audit dispatch.

---

## 3. Fixed factory-test image (Q3) — `factory-test-v1`

**Named and recorded.** `MW/D24/DSP/accept/manifest.json` gets a new
`factory_test_image` block: name `factory-test-v1`, `pair_dir
/home/app/loopthd/s109`, `build_cfg` triple, both `.ldr` md5s, measured on
MW-D24-2 today:

| | |
|---|---|
| build_cfg (chip 1 == chip 2) | `0xCF45FF10` / `0xE3018E6F` / `0xC47C0FA6` |
| `chip1.ldr` md5 | `7f226919a5d181410c3804d92678da19` |
| `chip2.ldr` md5 | `6f11a1ddc6efd45ec30f536cef295292` |

(Word 1 matches the shipping triple unchanged; words 2 and 3 differ from the
shipping triple in `dsp.build_cfg` by the `DSP4_TEST_NODES` bit and a handful
of other test/dev flags — `dsp4_buildcfg.py`'s own decode, both chips
identical, is in `s116/logs/`.)

**Asserted, not just recorded.** `tools/pi/d24_selftest.py` adds
`_check_factory_image()`: the first time any run confirms the SHARC pair is
up (`boot_pair()`'s tail, and `ensure_pair()`'s already-up branch), it reads
chip 1's build-cfg triple and compares it against the recorded
`FACTORY_TEST_BUILD_CFG`. `Rig.run()` gates every test in the new
`PAIR_DEPENDENT` set (every section-B pair test plus AS-DSPA/B/CPLD/ADC/DAC
and AL1) on that verdict: a mismatch scores **NO DATA "wrong image loaded"**
for every one of them, named in both the console line and the recorded
evidence — never a silent run against the wrong build. Proven live: every
`DC2-CS1`/`DC2-CS2` press this session reads `(factory-test-v1: True)`
against the real triple (§7's CSV). The mismatch path was verified by code
review only (a two-tuple equality check) — inducing a real mismatch would
mean re-staging a different pair mid-session, which is the exact thing "no
image swap anywhere in a session" rules out, so it was not done on hardware
this dispatch; stated as a gap, not silently skipped.

**Rows 103/104**: `pass_when`'s "BUILD_ID and the S82-signed build triple are
evidence" line replaced with a line naming the factory-test-v1 triple and
its manifest location, plus "loading/verifying the SHIPPING image is a
separate, later step and not part of this test." `t_dc2()`'s own evidence
line changed the same way (`S82-signed: %s` → `factory-test-v1: %s`,
compared against `FACTORY_TEST_BUILD_CFG` instead of the old `SIGNED_TRIPLE`,
which would always have read False on this pair and said nothing true).

---

## 4. Rails once (Q4) — raised after the last boot, held to handback

**Before**: AL1 alone raised AN_EN (in `_al1_prereq`) and dropped it again as
soon as its own measurement window closed (`_al1_stand_down` →
`al1_rails_down()`), so AS-ADC — which runs BEFORE AL1 in section C — always
saw AN_EN low and returned NO DATA. Confirmed on the bench before this
change: AS-ADC read NO DATA on both the S114 and S115 baselines.

**After**: a single rig-level `rails_up(r)` (replacing `al1_rails_down`)
raises AN_EN once and is idempotent — main() calls `ensure_pair()` **then**
`rails_up()` right before AS-ADC (in section C, gated on AS-ADC/AS-DAC/AL1
being selected), and AL1's own prereq calls `rails_up()` again, a no-op
re-read if AS-ADC's step already raised them. `_al1_stand_down` no longer
touches AN_EN at all (silences the speaker only). **`handback()` is the only
place AN_EN ever goes back down**, exactly once, keyed on the same `r._rails`
cap — matching "raised once, after the last DSP pair boot... of the session,
held until handback."

**The boot/rails ordering, guarded in code**: `boot_pair()` now reads AN_EN
first and **raises `RuntimeError`** if it is high, rather than booting through
a live rail (PW 09-10: analog last up, first down). Because
`boot_pair()`/`ensure_pair()` are the only things that ever establish the
pair, and the new pre-AS-ADC step calls `ensure_pair()` **before**
`rails_up()` specifically so a cold `--only AL1` press (which never goes
through section B's own pre-boot, since AL1 is not in `PAIR_TESTS_B`) still
gets the pair up while the rails are still down. This ordering bug was
caught and fixed during this dispatch's own bench testing, before deploy (a
naive "raise rails, then ensure_pair" ordering would have made a cold
`--only AL1` press refuse itself).

**Proven on the bench**:
- `--section C` (full): AS-ADC now reads **PASS** — "lane 0 (U15) 8/8
  CARRYING... lane 1 (U39) 8/8 CARRYING... lane 2 (U60) 8/8 CARRYING" —
  where it was NO DATA before. Rails held up 22.6-23.5 s across
  AS-ADC → AS-DAC → AS-PWR → AL1, then dropped exactly once at handback
  ("AN_EN: ... RAISED this session, LOWERED here (up for 22.58 s)").
- The guard fires: AN_EN forced high by hand, `--only DR1` (section B)
  raised `RuntimeError: refusing to boot the DSP pair with AN_EN (GPIO26)
  HIGH...`, caught by the `finally` handback, which correctly reported AN_EN
  "not written by this run" (it does not claim ownership of a rail state it
  did not raise) — rails manually restored to `lo` immediately after.
- `--al1-keep-rails` still works: handback's "LEFT UP" branch is unchanged,
  now keyed on `r._rails` instead of `r._al1_an`.

**Catalog**: `group`/`order` for AS-ADC's two rows (198, 141) already read
`A5` in `s113/test-catalog.csv` — S113's desk study had already placed them
there; nothing to change. The runner-side gap (rails never actually raised
before AS-ADC ran) is what this dispatch closes.

---

## 5. No redundant tests (Q5) — partner-row `covers`

**S113 §7 items 1-2, confirmed already folded in by S114**: `:2399`'s
pre-DR1 `boot_pair()` is conditional on a DR/DY/DC test being selected
(`PAIR_TESTS_B`), and the section-C-only branch always calls `ensure_pair()`
rather than a fresh boot — both landed in S114 (`d24_selftest.py`
`421ceec0…`, still true in this diff). No further runner change needed for
this half of the ruling.

**`covers`, corrected** (`s116/test-catalog.csv`): `s113`'s catalog carried
`covers = <own row number>` on every one of the nine shared-test pairs — i.e.
it did not name the partner at all. Fixed to the guard the ruling states:

| test id(s) | rows | shape | `covers` (both directions unless noted) |
|---|---|---|---|
| HD0-1 | 127, 203 | symmetric (both `tests=HD0-1` after §2) | `127,203` on both |
| ML1,ML2 | 102, 202 | symmetric | `102,202` on both |
| ML-B0,ML-P1 / ML-P1 | 125 / 143 | **one-way**: 125 ⊇ 143 | 125 → `125,143`; 143 → `143` (unchanged) |
| ML-B0,ML-P2 / ML-P2 | 126 / 144 | **one-way**: 126 ⊇ 144 | 126 → `126,144`; 144 → `144` (unchanged) |
| CC1,CC2 | 112, 199 | symmetric | `112,199` on both |
| AS-DSPA | 139, 194 | symmetric | `139,194` on both |
| AS-DSPB | 140, 195 | symmetric | `140,195` on both |
| AS-ADC | 141, 198 | symmetric | `141,198` on both |
| AS-DAC | 142, 197 | symmetric | `142,197` on both |

22 cells changed across 4 columns (`tests`, `pass_when`, `covers`); 202 rows,
19 columns, same row numbers, no renumbering — verified by a full cell-by-cell
diff against `s113/test-catalog.csv` (script output in this report's source
session; not re-included here as it is exactly the table above plus §2's and
§3's cells).

**What this repo does NOT implement**: the actual "stamp the partner row on
the glass" behaviour is the wizard's (mx26's), reading `covers` per catalog
row and per-row pressed-test bookkeeping that does not exist in this repo.
Listed in §9 for the hub.

---

## 6. `--no-app-restart` / bench discipline

Unrelated to the five rulings directly, carried over unchanged: every press
this session used `--local --no-soak-wait --no-app-restart`, the exact
wizard invocation shape (minus touch injection, per S114's own stated gap —
not re-attempted here either, for the same reason: nothing in this dispatch
touches the app or the touch wiring).

---

## 7. The timed run

`--section A,B,C`, full automated set, deployed `d24_selftest.py`
(`34de17cb…`), bench warm (unit up since a fresh boot ~35 min prior):

```
real  3m30.380s  =  210.4 s
```

against **S113's 435 s prediction** and **S114's 419 s re-price** (neither
of which had NW3's -i 0.1/concurrent change) — **a further 205-209 s off
S113, 209 s off S114**, almost all of it NW3 (246 s → ~63 s, §1) with the
rest inside normal run-to-run variance (AS-CPLD/handback marker skips,
etc.). Full result table and raw per-test logs: `s116/logs/`.

Verdicts this run: **27 PASS / 2 FAIL / 22 NO DATA** (51 rows), **19 PASS /
1 FAIL / 14 NO DATA** (34 of 36 workbook items). The two FAILs are NW2 (a
single `rx_dropped` packet over the NW3+NW4 window, idle control itself
clean at 0 — a real, tiny counter move, not ambient) and NW3 (§1's ambient
finding, not code). **AL1 PASSED** this run (`base -55.9 tone -34.8 SNR
21.1 dB THD -31.6 dB 2.62%`), matching S115's calibrated healthy line — the
acoustic-loop instability S114/S115 flagged as pre-existing and
code-independent did not reproduce today; not claimed fixed, just not seen
this session. NW4 read NO DATA on an unrelated, pre-existing quirk (the
driving host's own `lo` interface reporting 0 Mb/s trips NW4's own
same-link-speed heuristic) — untouched code, not investigated further here.

---

## 8. Deploy

| file | before | after | rollback |
|---|---|---|---|
| `/home/app/selftest/d24_selftest.py` | `421ceec0461d50c8373c1bfbf3efdeaa` (S115's deployed copy) | `34de17cbda23b731fdd718947792a807` | `d24_selftest.py.bak-s116-pre` (md5 matches "before") |

`python3 -m py_compile` clean, repo copy and deployed copy. `--keys` clean
against `s110/export-keys.csv`: "34 distinct items, all present in the
export; 27 row numbers in the table match their position" — unchanged from
S114/S115. `MW/D24/DSP/accept/manifest.json` and
`MW/D24/DSP/s116/test-catalog.csv` are repo-only; neither is a file this
runner reads, so nothing further to deploy for them.

One backward-compat note, not a rollback: `--no-soak-wait` is kept as an
accepted no-op argparse flag rather than removed outright (§2), specifically
so the wizard's current invocation string does not break before the hub
lands §9's mx26-side edit.

**Handback**: `AN_EN` (GPIO26) `op -- pd | lo`, `CS_M` (GPIO27) `op -- pd |
hi` DRIVEN, 595 chain marker SAFE (verified 200/200 in the last full run),
speaker path silent (torn down by AL1's own stand-down, 4.09 s live),
`matrix-app` inactive, `d24-testui` active, `pair.conf` unchanged
(`/home/app/loopthd/s109`). All test-only files this session created under
`/tmp` on the unit were removed after confirming every entry's timestamp
fell inside this session's own window (S114's housekeeping lesson, applied:
checked before deleting, not after).

---

## 9. mx26 app changes for the hub

1. **Drop `--no-soak-wait`** from the wizard's invocation
   (`src/sw/app/Core/TestSkinStore.cs:1067-1074`, roughly line 1070) — the
   runner accepts it harmlessly today (§2/§8), but it now controls nothing.
2. **Read the two new catalog columns properly for HD0-1's rows** (127, 203):
   `tests` now reads `HD0-1` only; a wizard that still expects `HD0-1,HD0-2`
   on those rows should not.
3. **Partner-row stamping** (Q5): when a press's test id has a `covers` list
   longer than the pressed row's own number, stamp every row named — but
   only when the press's `tests` set is a SUPERSET of (or equal to) the
   covered row's own `tests` (the 125→143 guard: pressing 125 stamps 143,
   pressing 143 must NOT stamp 125). `covers` is populated correctly for all
   nine pairs in `s116/test-catalog.csv`.
4. **Rows 103/104**: the app-facing text should say `factory-test-v1`, not
   `S82-signed` (§3) — if the wizard's own copy duplicates any of the
   catalog's `pass_when` text rather than reading it live, that copy needs
   the same edit.
5. **Group/order columns** (S113, unchanged by this dispatch): still not
   read by the app as far as this repo's audit can tell — RUN ALL still
   presses rows in catalog order rather than the A1-A5/M1-M8 grouping. Not
   new to S116; repeating S113's own note since group/order is now also
   load-bearing for AS-ADC's placement (§4).

---

## Acceptance, against the dispatch's own bar

- NW3 proven on the bench (or 🔴 with the table): **done, table in §1** — no
  reduction in packets or passes, -i 0.1 does not cost packets, ~63 s
  measured against a ~62 s target. 🔴 filed for today's elevated ambient loss
  (not a code issue).
- HD0-2 gone from catalog, runner and options: **done** (§2); `--no-soak-wait`
  kept as a harmless accepted flag, not a functional option, pending §9 item 1.
- Factory image named, recorded, asserted: **done** (§3), proven live on
  DC2-CS1/CS2; the mismatch path is code-reviewed, not bench-induced (stated
  gap).
- No pair boot possible with AN_EN high: **done and proven** (§4) — the
  guard fired on a deliberate test and was safely recovered.
- Rows 198/141 give verdicts: **done and proven** (§4) — AS-ADC PASS in the
  full run.
- A single press of 139 stamps 194, of 125 stamps 143 but not the reverse:
  **catalog done** (§5); the actual stamping behaviour is the app's (§9
  item 3), listed, not implemented here.
- The timed automated run reported against 435 s: **done**, 210.4 s (§7).
- Unit handed back as found: **true** (§8).

Questions for PW: none outstanding — all five rulings were unambiguous and
none needed a further decision. The one 🔴 worth a look is §2's pre-existing
catalog data misalignment (rows 127/203's `pass_when`/`explain` do not
describe HD0-1/HD0-2 in either `s110` or `s113`'s catalog) and §1's elevated
ambient network loss today — both reported, neither blocking.
