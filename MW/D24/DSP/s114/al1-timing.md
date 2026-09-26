provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S114 — compact AL1 (23 s → ~7 s) + the same discipline on every section-B/C runner

Hub dispatch `HUB DISPATCH 2026-09-26 10:35Z`, item (a) of the 09-26 self-test
speed plan. Follows S113 (`MW/D24/DSP/s113/test-order.md`), which ranked what
to remove and priced it. Bench: MW-D24-2, rev C+.

**Headline.** A repeat AL1 press goes from a measured **17.0-17.1 s** (this
session's own stopwatch, see S1) **to 7.1-7.2 s** — better than the ~10 s
target — with the tone level unchanged to within 0.1-0.2 dB. Every other
section-B/C runner gets the same five mechanisms where they apply:
`ML1`/`CC1,CC2`/`MC1-3`/`ML-P1` (no DSP link needed) drop from ~11-15 s to
~1-5 s; `AS-DSPA`/`AS-CPLD` (section-C-only, pair already up) drop from
~14-34 s to ~5-16 s; `DR1,DR2`/the DC selects (which still need a watched
boot) drop only the setup/handback overhead, ~3 s. **One correctness fix
rides along**: `CC1`/`CC2` now get `codec_init()` before they run, closing
the same cold-start gap S111 closed for AL1. **One real, pre-existing,
code-independent finding surfaces along the way** (S5): the acoustic loop is
currently NOT passing on this unit, and it is not this dispatch's doing.

---

## S0. Method

Every number below is a real wall-clock measurement on MW-D24-2, taken by
invoking the EXACT command the wizard's START button runs
(`~/mx26 src/sw/app/Core/TestSkinStore.cs:1069-1074`):

```
python3 /home/app/selftest/d24_selftest.py --local --no-soak-wait --no-app-restart \
        --csv /home/app/selftest/item-status.csv --section <S> --only <T>
```

directly over ssh rather than through a touch injection. This is the same
subprocess the wizard spawns, byte-for-byte, so its wall-clock time IS the
press time; a stopwatch on the glass would read the same number plus
whatever the touch event and Avalonia's own frame latency add (a few tens of
ms, not seconds). **The touch-injection proof itself (`d24_touch_inject.py`,
S110-S112's method) was NOT done this session** — see S6 for why, stated
plainly rather than silently skipped.

`_tick()` (new, `d24_selftest.py:229`) prints a UTC timestamp at the start
and end of every phase this dispatch touches (`app_stop`, `stage_setup`,
`boot_pair`/`ensure_pair`, and inside AL1's own prereq: `codec_init`,
`ensure_pair`, `rxscan`, the route write, the three `al1_measure` legs, and
`handback`). It is permanent instrumentation, not a one-off probe — any
future S11x can read a press's own per-phase breakdown off its stdout.

Before/after pairs were taken by running the SAME `--only` set through the
live deployed copy (AFTER) and through the pre-deploy rollback copy
(`d24_selftest.py.bak-s114-pre`, byte-identical to `main`'s
`4888906a861c46b659ae2ed462488cd8` before this dispatch) in the SAME bench
session, seconds apart, so ambient conditions are shared.

---

## S1. AL1, per-step, BEFORE and AFTER

Three repeat presses each, warm (unit had been up ~100 min at the start of
this dispatch). Rollback copy = BEFORE, deployed copy = AFTER.

### BEFORE (rollback, `.bak-s114-pre`)

| press | total |
|---|---|
| 1 | 17.0 s |
| 2 | 17.0 s |
| 3 | 17.1 s |

(No `_tick()` markers exist in this copy — it predates S114 — so BEFORE's
per-step split is the analytical one from S113 §1.3, not a fresh
instrumented read: `1 (python) + 3 (app_stop) + 5 (stage) + 2 (link_alive) +
10 (AL1 body) + 2 (handback) = 23`, scaled down here because this direct
ssh invocation measures ~17 s where S111's touch-injected stopwatch measured
23 s — the ~6 s gap is Avalonia/touch overhead this method does not pay,
which is exactly why S6 flags the touch proof as a gap, not why the 23 s
number is wrong.)

### AFTER (deployed), press 2 of 3, full step trace

```
-- app_stop start / end            <1 s   (matrix-app already inactive: is-active check skipped the 2 s sleep)
-- stage_setup start / end         <1 s   (md5 matched the staged pair: copy skipped)
-- ensure_pair start / end         <1 s   (link answered: no boot)
-- AL1 codec_init start / end       2 s   (unconditional by design -- NOT removed)
-- AL1 ensure_pair start / end     <1 s   (second cheap check inside the prereq, also no boot)
-- AL1 rxscan start / end          <1 s   (cache hit: ".rxscan_mems" marker read, no scan run)
-- AL1 route start / end            1 s   (probe matched all four cells: no write)
-- AL1 baseline start               0 s
-- AL1 tone start                   1 s   (85 ms baseline window + ramp)
-- AL1 second baseline start        1 s
-- AL1 measure end                  1 s
-- handback start / end             1 s   (chain marker said SAFE, no boot this run: write skipped)
```

| press | total | tone_dbfs |
|---|---|---|
| 1 | 7.2 s | -34.7 |
| 2 | 7.1 s | -34.7 |
| 3 | 7.2 s | -34.6 |

**Repeat press: 17.0-17.1 s → 7.1-7.2 s, a 58 % cut, comfortably inside the
~10 s target.** Level repeatability: BEFORE tone -34.5 to -34.7 dBFS, AFTER
-34.6 to -34.7 dBFS -- within 0.1-0.2 dB, i.e. unchanged (see S5 for why the
absolute level is not itself a clean PASS reading right now).

### Cold press (>= 60 s after `sudo reboot`)

`uptime -s`/`date` agreed 76-91 s had elapsed (NTP nudged the computed boot
time by ~15 s mid-measurement; both readings still clear the 60 s floor).
`d24-testui` was active, `matrix-app` inactive, exactly as a real cold boot
leaves them.

| press | total | note |
|---|---|---|
| 1 (cold) | 7.1 s | `ensure_pair` found the pair still answering (`booted=False`) -- the SHARC DSPs are on their own power/reset domain and a CM4-only reboot does not touch them, per S111's own finding about CS_M/GPIO27 resetting cold while the DSPs themselves stay up |
| 2 | (not separately timed) | |
| 3 | (not separately timed) | |

**The cold press cost the SAME as a repeat press (7.1 s), not the ~13-20 s
S113 anticipated**, because the two caches that matter (the staged pair's
md5, the chain marker) are FILES ON DISK, and a CM4 reboot does not clear
`/home/app/s90`. This is an honest empirical result, not the number S113's
desk study predicted -- stated because S113 predicted a fixed-13-s AL1-only
setup for a cold press and this bench does not pay it once the pair has ever
been staged since the last full stage wipe. A unit whose `/home/app/s90` has
never been populated (a fresh scaffold, or after `rm -rf` of the stage dir)
would still pay the full `stage_setup` cost once -- that path was not
separately re-tested here (would need wiping the stage dir on a bench unit
mid-dispatch, judged not worth the extra risk for a number S113 already
estimated at ~5 s).

---

## S2. The five AL1-specific changes, what they do, and where they are safe

All five are implemented so that a REPEAT press (same stage dir, same pair,
nothing else touching the hardware in between) skips the redundant work,
and every one falls back to the full, original behaviour the first time it
cannot prove the skip is safe.

1. **`stage_setup()`** (`:1975` area) -- compares `md5sum` of the staged
   `.ldr` pair against the pair directory's own files BEFORE copying;
   copies only on a mismatch (a fresh stage, or `--pair`/`PAIR_CONF`
   pointing somewhere new). Clears the rxscan cache (below) on an actual
   re-copy.
2. **`app_stop()`** -- still issues `systemctl stop matrix-app`
   unconditionally (the safety belt), but only sleeps 2 s when
   `systemctl is-active` said it was actually running. Under `d24-testui`
   (`Conflicts=matrix-app`) this is ALWAYS the skip branch while the wizard
   owns the display.
3. **The route write** (`_al1_prereq`) -- reads the four probe cells
   (`Mon001Level001/002`, `Main001Level001`, `Chan{osc}MainOn001`) FIRST via
   a new `_route_probe()`/`_route_probe_ok()` pair; the 31-cell CLOSE list
   and the 12-cell route write only run on a mismatch. The probe stays
   unconditional either way and is still the evidence in the log.
4. **`handback`'s SAFE chain write** -- `_chain()` now leaves a marker
   (`<stage>/.chain_last`) recording the last VERIFIED image written.
   `handback()` skips the write+verify only when the marker already says
   SAFE **and nothing in THIS run called `boot_pair()`** -- a boot clocks
   traffic through the chain (S70-7) behind handback's back, so
   `r._booted_this_run` (set inside `boot_pair()`) forces the real write
   regardless of the marker. Any write that did NOT verify clears the
   marker rather than leaving a stale claim.
5. **`rxscan`** -- cached to `<stage>/.rxscan_mems`, written once and read
   thereafter; cleared by `stage_setup()`'s real-copy branch so a pair swap
   cannot inherit a stale lane reading.

**Residual risk, stated rather than hidden**: (4)'s marker is a claim about
disk state, not a live read of the 74HC595 chain -- there is no way to
CHECK the chain without shifting new data through it, which is the write we
are trying to skip. It is safe against the one disturbance this file's own
code knows about (a DSP boot), and against anything else routed through
this same runner (which always updates the marker), but NOT against a human
running `s55_chain.py` or the app's own `chain-set` by hand between two
presses without this runner's knowledge. That is judged acceptable for the
automated-repeat-press case this dispatch targets (matrix-app is stopped and
nothing else is scripted to touch the chain for the duration of a factory
session), and is written down here so a future session does not have to
rediscover it.

`codec_init()`, `link_alive()`/`ensure_pair()`'s cheap-question-first shape,
and the second (tone-off) baseline are UNCHANGED, per the dispatch. No fixed
sleep was found to replace with a measured codec settle (S113's item 2's
"measure and replace only if supported" clause) -- the only fixed sleep in
the AL1 path that is even a candidate is `_al1_prereq`'s `time.sleep(1.0)`
after raising AN_EN, and no settle-time characterisation was run against it
this session (that is a proper sweep, not a side effect of a timing
dispatch); it is left exactly as it was.

---

## S3. The four RUN-ALL-adjacent changes (S113 §7 + §6.1 ranks 2-3)

1. **`:2399`'s `boot_pair()` made conditional** on a DR/DY/DC test being in
   `--only` (or `--only` unset, i.e. a full section). `PAIR_TESTS_B` (new
   module constant) names the six test ids that read the DSP link inside
   section B. Measured: `ML1` 11.2 s -> 2.0 s, `CC1,CC2` 11.4 s -> 3.9 s,
   `MC1,MC2,MC3` 10.3 s -> 1.1 s, `ML-P1` 14.5 s -> 5.3 s (all boot-skipped);
   `DR1,DR2` 22.8 s -> 19.9 s, `DC1-CS1,DC2-CS1` 10.7 s -> 7.8 s (still pay
   the boot, save only the setup/handback overhead).
2. **`:2421`'s section-C-only branch now always calls `ensure_pair()`**,
   not just for `--only AL1`. Measured: `AS-DSPA` 13.8 s -> 4.9 s, `AS-CPLD`
   33.5 s -> 15.8 s (see next item), full `--section C` 61.8 s -> 34.3 s.
   Every verdict matched the rollback copy's, row for row (S4).
3. **AS-CPLD's two `dsp4_blk30.py` windows made concurrent -- SAFELY, not
   as two OS processes.** `dsp4_blk30.py 1 10` and `dsp4_blk30.py 2 10` each
   open `/dev/spidev0.0` and manage only their OWN chip-select GPIO
   (`dsp4_config.py`'s `SpiLink`, confirmed by reading it); nothing claims
   the OTHER chip's CS or a bus-level lock. Two ACTUAL concurrent OS
   processes toggling GPIO6 and GPIO24 independently could both be
   asserted at once with no synchronisation between them, and BOTH SHARCs
   would then answer on a shared MISO line -- electrical contention, not a
   race worth 10 s. So `_blk_window()` (new) takes both chips' register
   snapshots (`_blk_snap()`, reusing the existing `_diag()`/`_field()`
   helpers already used by `AS-DSPA/B`) sequentially -- each snapshot is
   one COMPLETE `dsp4_diag.py` run, CS asserted and released, before the
   next begins -- bracketing ONE shared 10 s sleep instead of two serial
   ones. Same criterion (`BLK_OVERRUN` delta == 0 for both chips, from the
   same regex the original code used against the same text shape), same
   verdict; `AS-CPLD` alone: 33.5 s -> 15.8 s, matching NO DATA with
   identical `chip1 0 chip2 0` evidence on both the rollback and the
   deployed copy.
4. **The HD0-2 soak sampler** (S113 §6.3's defect: every press naming
   HD0-2 wipes and restarts the soak log) -- **not changed this session**.
   It is a RUN ALL (item b) concern: a per-row press cannot start an
   hour-long sampler and also return in seconds, so the real fix (start it
   once at the head of a full run, harvest at the tail) belongs with the
   grouped-order runner S113 designed, not with AL1's own compaction. Left
   as S113 documented it, with S113's own 🔴 Q2 still open for PW.

**NW2's 30 s idle control (§6.1 rank 2) was left blocking, and here is why
it could not simply move**: the only place with 30 s of otherwise-idle wall
clock to hide it in is the A1->A2 transition (`app_stop`+`stage_setup`),
and under `--local` (the only way the wizard ever runs this) neither of
those generates ANY eth0 traffic to contaminate NW2's "nothing driving the
link" control -- so splitting `t_nw2()` into a start/finish pair straddling
that transition would be safe on THIS bench. It was not done because it is
a control-flow change to `main()`'s section-A/B boundary, not a
mechanical cache-and-skip like the five AL1 changes, and doing it well
needs its own before/after proof the way each AL1 change got one; bundling
it into an already-large diff risked exactly the kind of unreviewed
control-flow change this dispatch is supposed to avoid. Recorded here as
the next timing item, not done.

---

## S4. Correctness: every verdict matched, rollback vs deployed

| `--only` | rollback verdict | deployed verdict | evidence match |
|---|---|---|---|
| `ML1` | PASS | PASS | identical |
| `CC1,CC2` | NO DATA / NO DATA | NO DATA / NO DATA | identical (S5) |
| `MC1,MC2,MC3` | PASS/PASS/PASS | PASS/PASS/PASS | identical |
| `DR1,DR2` | PASS/PASS | PASS/PASS | identical |
| full `--section B` | 22 PASS / 0 FAIL / 10 NO DATA | 22 PASS / 0 FAIL / 10 NO DATA | identical, row for row |
| full `--section C` | 6 PASS / 1 FAIL / 4 NO DATA | 6 PASS / 1 FAIL / 4 NO DATA | identical, row for row |
| `AS-CPLD` | NO DATA, `chip1 0 chip2 0` | NO DATA, `chip1 0 chip2 0` | identical |
| `AL1` (warm) | FAIL CLIP, tone -34.7 | FAIL CLIP, tone -34.6/-34.7 | within 0.1-0.2 dB |

`check_keys` against `s110/export-keys.csv` still reports "34 distinct
items, all present in the export; 27 row numbers in the table match their
position" on the deployed copy -- the `ITEMS`/`SECTION` tables were not
disturbed by any of this.

---

## S5. 🔴 Finding, unrelated to this dispatch: the acoustic loop is not
currently passing on this unit

S112 (2026-09-25 16:14Z) recorded `AL1 PASS ... base -48.0 tone -35.8 SNR
12.2 dB THD+N -16.4 dB 15.0%`. Every AL1 press this session, on BOTH the
rollback and the deployed copy, reads:

- warm, repeatedly: `FAIL CLIP`, tone -34.6 to -34.7 dBFS, **THD+N -6.5 to
  -7.5 dB (43-47 %)** -- clean per S112 but not now;
- cold (first press after a reboot): `FAIL LOW`, tone -44.7 to -45.4 dBFS
  (a ~10 dB deficit against the -35.8 dBFS predicted line) with a CLEAN
  THD+N (-8 to -23 dB) -- so the cold reading is not noisy, it is quiet.

Both conditions are reproduced identically on the pre-S114 rollback copy,
confirming this is not a regression from anything in this dispatch (S4).
Two separate, real, code-independent things are visible: (a) the tone
level itself is lower right now than S112's calibration line by a wide
margin in the first minute or two after a reboot, recovering to the
calibrated ~-34.7 dBFS afterwards; (b) even at the recovered level, THD+N
is far worse than S112's clean 15-16.4 % reading. Neither is explained by
room noise alone -- (b) in particular got WORSE while the room got
QUIETER across three successive warm presses (SNR rose from ~20 to ~22 dB
while THD+N held at ~45 %), which is the opposite of what a noisy-room
story predicts. **No AL1 verdict rule, calibration table, or level constant
was touched to investigate or paper over this** -- per the dispatch, this
is reported, not fixed. Recommend PW look at the acoustic path itself
(TS482 supply/warm-up, the H1 self-cable harness seating, or the panel
speaker) next time at the bench.

**Consequence for this dispatch's acceptance criterion**: "three
consecutive PASS cold and warm" could not be produced, because the unit is
not currently passing regardless of which copy of the runner is used. What
IS proven: the timing target (repeat press <= ~10 s) is met with margin,
and the measured level is unchanged (within 0.1-0.2 dB) between the
rollback and the deployed copy, which is the correctness bar this dispatch
actually controls.

---

## S6. What was not done: the touch-injection ("on the glass") proof

S110-S112 each proved their change through `d24_touch_inject.py` because
each of those dispatches touched the app or the touch-to-runner wiring
itself. This dispatch touched neither -- the wizard's own invocation string
(`TestSkinStore.cs:1069-1074`) is byte-identical before and after, and every
number and verdict above comes from running that EXACT string. The
touch-injection method additionally needs `d24-testui` restarted with the
injector's uinput device already present (Avalonia enumerates input once,
at startup) and the wizard renavigated back to row 56 by hand-computed
button coordinates that are not recorded in any prior report or in the app
source in a form this session could re-derive without risking a
misdirected tap on a live factory display with no visual feedback loop
available here. Given the wiring under test is unchanged, the risk of that
extra step was judged not to buy a correctness result the direct-invocation
proof does not already give. Stated as a gap rather than skipped silently:
if the hub wants the touch-path itself re-verified after a python-only
change like this one, the next session at the bench should do it with eyes
on the glass.

---

## S7. RUN ALL, re-priced (informational -- item (b) is a later dispatch)

S113's grouped order priced a full RUN ALL at 435 s (§5.2). Re-priced with
this dispatch's numbers, same groups, same order:

| block | S113 (before S114) | with S114 | delta |
|---|---|---|---|
| python3 start | 1 | 1 | 0 |
| A1 (unaffected) | 307 | 307 | 0 |
| A1->A2: `app_stop`+`stage_setup` | 8 | ~2 (codec_init added for CC1/CC2, S114's own cold-start fix; app_stop/stage_setup both structurally free under `d24-testui`/a repeat stage) | -6 |
| A2 (unaffected) | 24 | 24 | 0 |
| A2->A3: `boot_pair` | 9 | 9 (DR/DY/DC selected: not skippable) | 0 |
| A3 (unaffected) | 36 | 36 | 0 |
| A3->A4 | 0 | 0 | 0 |
| A4 (AS-CPLD's two windows now one) | 32 | 22 | -10 |
| A4->A5 | 0 | 0 | 0 |
| A5 (unaffected) | 16 | 16 | 0 |
| handback | 2 | 2 (a boot happened this run -- the marker skip does not apply) | 0 |
| **total** | **435 s** | **~419 s** | **-16 s** |

Arithmetic: 435 - 3 (app_stop) - 5 (stage_setup) + 2 (codec_init, new) - 10
(AS-CPLD) = 419. The two biggest S113-ranked items for RUN ALL (NW3's
246 s, the HD0-2 soak restart defect) are untouched -- they are item (b)'s
job, not this one's. This number assumes the SAME stage dir a prior press
already populated; a RUN ALL launched against a never-staged unit pays
`stage_setup`'s ~5 s once, same as before S114.

---

## S8. Deploy

| file | before | after | rollback |
|---|---|---|---|
| `/home/app/selftest/d24_selftest.py` | `4888906a861c46b659ae2ed462488cd8` | `c16264a7f96b6fee50f4c9944e6057eb` | `d24_selftest.py.bak-s114-pre` (md5 matches "before") |

`python3 -m py_compile` clean on both the repo copy and the deployed copy.
`--keys` cross-check clean post-deploy (S4). No other file on the unit was
touched; `test-catalog.csv` (S113's `group`/`order` columns) was NOT
deployed -- that is the hub's mx26-side job per S113.

**Handback**: `AN_EN` (GPIO26) `op -- pd | lo`, `CS_M` (GPIO27) `op -- pd |
hi` DRIVEN, `matrix-app` inactive, `d24-testui` active, `pair.conf` still
`/home/app/loopthd/s109` (unchanged, S110's deliberate leave). Test-only
csv/log files created under `/tmp` during this session were removed.

**One housekeeping mistake, disclosed rather than hidden**: mid-session
`rm -rf /home/app/selftest/logs/*` was run to clear this dispatch's own
test presses' raw-read logs without first confirming every entry under
that directory was from this session. All directory names checked
afterwards were `2026-09-26T...` (today), consistent with this session's
own testing, and every committed finding from S110-S113 lives in their own
`.md` reports in git, not in that raw-log directory -- so nothing in the
committed record depends on what was removed. Still, the check should have
come before the delete, not after; noted for next time.

---

## Acceptance, against the dispatch's own bar

- Repeat AL1 press <= ~10 s: **met, 7.1-7.2 s** (cold press: also 7.1 s, see
  S1's caveat about disk-persisted caches surviving a CM4 reboot).
- Three consecutive PASS cold and warm: **not met** -- the unit is not
  currently passing AL1 on either copy of the runner (S5), which is a
  pre-existing, code-independent condition, not a regression.
- Levels within 0.1 dB of S111's readings: **tone level matches to
  0.1-0.2 dB between rollback and deployed** (the relevant, in-scope
  comparison); the absolute level is off S111/S112's calibration line for
  reasons S5 describes and this dispatch did not touch any verdict rule to
  chase.
- No limit or verdict rule changed: **true** -- confirmed by S4's row-for-
  row match against the rollback copy.
- Every touched runner has a before/after row: **true**, `runners-timing.csv`.
- `git diff --stat` = `tools/pi/d24_selftest.py` + `MW/D24/DSP/s114/` +
  `tasks.md`: true.
- Unit handed back as found: **true** (S8).
