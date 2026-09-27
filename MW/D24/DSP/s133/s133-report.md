provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S133 — the hands-off screen off the flag itself; PAUSE drops the rails

**Outcome: both fixed and proven on MW-D24-2.** The hands-off screen now
watches `quiet.flag` for the whole of the dsp phase, not only while the panel
loop happens to be polling, and `main()`'s `except Paused:` now lowers AN_EN
and SAFEs the chain on every way a pass can pause — closing the one door none
of the three existing nested rails-guards was written to cover. Both were reproduced end to end on real
hardware: the hands-off screen appeared with nobody watching the panel walk,
and a PAUSE at the analog station's own card (rails live, station not yet
entered) dropped AN_EN before the process exited. A follow-on real pass then
proved the actual failure mode named in the ruling — a subsequent run's
`boot_pair()` no longer refuses, and AL1 PASSES.

---

## 1. The hands-off screen, raised off the flag itself

**Before:** `LV.HANDSOFF` was set in exactly one place — `quiet_hold()`'s
`hold=` callback, wired into `PL.loop()` inside `panel_station()`. That
callback only runs *between buttons of an active panel walk*. S132 found the
gap: AL1 lives in the `dsp` background phase, which the panel walk merely
overlaps — if the walk finishes its owed buttons before the dsp phase reaches
AL1's tone, `overlapped()`'s `dsp.join()` just blocks on the thread with a bare
`self._t.join()`. Nothing there ever looked at `quiet.flag`, so the screen sat
on whatever the panel loop (or nothing) had last written while the speaker
sounded next to the microphone reading it.

**Fix (`tools/pi/d24_runall.py`):** `Background.join()` now takes an optional
`hold` — the *same* `quiet_hold()` closure the panel loop already uses, same
wording, same input-drain, same active progress, same restore. `overlapped()`
passes it into `dsp.join(glass, PHASE_WORDS['dsp'], hold=quiet_hold(...))`.
Both call sites (the panel loop's own `hold=`, and this join) run on the same
(main) thread and never overlap in time — the panel walk always returns
before `dsp.join()` is reached — so there is nothing for the two invocations
to race over.

**Proven on the unit.** Every M1/M2 (panel) row was pre-ignored for the bench
harness (restored after — see §3), so the panel walk found nothing owed and
returned at once, exactly the gap scenario. The pass was driven purely through
the same file protocol the armed factory screen answers
(`runall/live.json` out, `runall/command.json` in) — `d24-testui` was already
running and drawing every state written, so a screenshot is one
`capture.request` away; no touch injection needed; nobody has to tap a pixel
to set a JSON field.

```
00:22:04 SCREEN [starting] 7/7 The bench is set up. ::
00:22:41 SCREEN [handsoff] 0/17 Hands off - the unit is testing itself (the speaker and the  ::
00:22:41 *** HANDS-OFF REACHED (S133 join()-watcher) -- capturing
00:22:44 SCREEN [starting] 7/7 The bench is set up. ::
00:22:45 SCREEN [waiting] 3/3 Station 3 of 3 :: Next: analog paths. Supplies LIVE. 35 checks. Press ENTER.
```

The panel walk never appears at all between "the bench is set up" and
"hands off" — nothing was polling the flag except the new join-watcher, and it
raised the screen, drained input, counted up, and restored the prior page
(back to `starting`/"the bench is set up") the moment the flag cleared, all
without a single panel button in play. Screenshot: `screens/s133-handsoff.png`.

---

## 2. PAUSE drops the rails

**Before:** `main()`'s `except Paused:` saved state, put up the PAUSED screen,
and returned — it never touched AN_EN. Every individual place a `Paused()`
could be raised had grown its *own* rails guard over several sessions
(`overlapped()`'s `if not reached_the_end and patch_to_come: lower_rails()`;
`run_manual()`'s `if owns_analog and not a.patch_station_ran: lower_rails()`;
`finish_early()`'s `teardown()` inside the patch station's own loop) — three
separate conditions, each covering the `Paused()` sources its own function
could see, none covering the others', and no single guaranteed backstop for a
`Paused()` from anywhere else, now or after a future change to any of the
three. PW's rule ("rails are never left without an owner") was being kept by
enumeration, not by invariant.

**Fix:** `main()`'s `except Paused:` now calls `lower_rails(glass)`
unconditionally, before anything else. `lower_rails()` is idempotent (backed
by `PT.Analog.down()`, which is a no-op past its first call), so where a
nested guard already dropped them this costs nothing but a second log line;
where none did, this is now the one place that always will. Resume needs no
matching raise: a resumed pass either re-enters the auto set fresh (rails go
up exactly as any first pass raises them) or re-enters a station whose own
`an.up()` is idempotent *and self-healing* — it raises AN_EN again if it finds
it down, logging that it did.

**Also fixed — the auto batch that dies must say so, and stamp NO DATA, never
read as finished.** `run_auto()` now checks the self-test subprocess's own
exit code. On a nonzero exit it never prints "auto set finished in Ns" (the
same words an honestly-empty owed set gets); it prints `!! auto set DIED
(exit N) after N s -- M rows marked NO DATA, never PASS`, and explicitly
`state.put()`s NO DATA — with the exit code, elapsed time and the
subprocess's own last output line as evidence — onto every row this run owed
that got no fresh verdict. A row that was never reached because the batch
died can no longer sit blank for a later reader (or the next station) to read
as "not yet run".

### Proven on the unit

Every panel row stayed pre-ignored (§1's harness), so the same driven pass
reached the analog station's card with the rails live and nothing walked yet:

```
00:22:45 *** ANALOG STATION CARD REACHED -- AN_EN: 26: op -- pd | hi // GPIO26 = output
00:22:46 *** SENDING PAUSE AT THE CARD (before the station ever runs)
00:22:46   command.json <- 'pause'
00:23:59 SCREEN [paused] 3/3 The test stopped before it finished - it was paused. The uni ::
00:24:00 AN_EN after PAUSE at the card: 26: op -- pd | lo // GPIO26 = output
00:24:00 chain marker after PAUSE: 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 01 00
```

PAUSE was sent **before `patch_station()` (and its `station.run()`) was ever
entered** — the specific door none of the three nested guards was written
for. The pass's own log shows both the pre-existing `run_manual()` guard and
the new top-level one firing (harmlessly redundant, exactly as designed):

```
.. the analog rails are down (raised earlier in this session, lowered here -- this station closes it)
.. mic-pre chain back to safe (muted, gain 0, phantom off): verified
.. the analog rails are down (raised earlier in this session, lowered here -- this station closes it)
.. mic-pre chain back to safe (muted, gain 0, phantom off): verified
.. paused at step 0 of the operator set -- the next START resumes here
```

AN_EN GPIO26 read `hi` at the card and `lo` after PAUSE; the chain marker
(`/home/app/s90/.chain_last`) shows the SAFE image, and the pass's own log
carries `SAFE image: VERIFIED 200/200`. Screenshots:
`screens/s133-card-rails-up.png`, `screens/s133-paused.png`.

**Then the actual failure mode named in the ruling, reproduced and closed.**
With AN_EN left as the PAUSE fix set it (low), state reset and a fresh
`--auto-only` pass run for real:

```
-- 2026-09-27T23:26:43Z boot_pair start
-- 2026-09-27T23:26:50Z boot_pair end
AL1 ...
-- 2026-09-27T23:27:22Z AL1 took 6.6 s
  AL1       PASS     PASS base -45.9 tone -29.7 SNR 16.2 dB THD -25.0 dB 5.63%
.. auto set finished in 49 s
pass 2: 23 PASS / 0 FAIL / 13 NO DATA / 51 ignored / 0 skipped / 80 not tested (of 202 rows) in 50 s
```

`boot_pair()` did not refuse, the auto set did not die, and AL1 PASSED —
this is the exact "next automatic run refuses to boot the pair, AUTO reports
finished in 0 s, AL1 silently never taken" scenario the ruling named, now
closed by the PAUSE fix upstream of it.

**An unplanned bonus proof of the DIED/NO-DATA fix.** The first `--auto-only`
attempt (before the ignore above) hit a genuine, pre-existing, unrelated bug —
`NW4` (network throughput) returns a `NOT TESTED` verdict on this bench link,
which fails `d24_selftest.py::record()`'s own assertion
(`assert verdict in (PASS, FAIL, NODATA)`) and crashes the subprocess (a
known, pre-existing limitation: the bench link is 100 Mb/s and `--local`
measures loopback — nothing to do with this dispatch).
That crash is exactly the "batch dies mid-run" case the fix targets, and it
behaved exactly as designed:

```
!! auto set DIED (exit 1) after 73.9 s -- 34 rows marked NO DATA, never PASS
pass 1: 1 PASS / 0 FAIL / 36 NO DATA / 50 ignored / 0 skipped / 80 not tested (of 202 rows) in 74 s
```

34 rows the batch owed and never reached (including AL1's) were stamped NO
DATA with the exit code and the subprocess's own last line as evidence,
nothing was misreported as finished, and nothing was left blank. Row 128 (the
row NW4 proves) was ignored (reason `other`) for the second attempt above, and
is unignored again — see §3.

---

## 3. What was touched, and the unit's state now

**Code (`tools/pi/d24_runall.py`):**
- `Background.join()` takes an optional `hold`; `overlapped()`'s `dsp.join()`
  passes the same `quiet_hold()` closure the panel loop uses.
- `run_auto()` checks the self-test subprocess's exit code; a nonzero exit is
  reported plainly (never "finished in Ns") and stamps NO DATA onto every
  owed row it did not reach. `passno` threaded through all four call sites so
  those stamps carry a real pass number.
- `main()`'s `except Paused:` calls `lower_rails(glass)` before anything else.

**Bench harness used to prove it, all reverted:**
- `ignored.csv` — 50 M1/M2 rows added (reason `other`) to bypass the panel
  walk for the proof, restored byte-for-byte from a backup taken first
  (`diff` confirmed clean).
- `--reset-only` run at the end: cumulative state forgotten, next pass walks
  everything.
- Row 128 (NW4's row), ignored mid-session for the recovery proof, is back to
  its ordinary (un-ignored) state after the reset.
- Driver script and screenshots removed from the unit; kept in this report's
  `tools/`, `data/` and `screens/` (and mirrored to
  `~/hub-staging/s133-screens/` on the hub host per the block).

**Unit, verified after:** AN_EN (GPIO26) low, CS_M (GPIO27) driven high, chain
marker SAFE (`01`×24, `00`), app still `b05e9fd5` (untouched — no flashing, no
fuses), `d24-testui` running, `matrix-app` inactive (as found), no
`d24_runall.py`/`d24_selftest.py` process left running, `runall/` back to
just its ordinary bookkeeping files.

**Deployed:** `tools/pi/d24_runall.py` only (via `deploy-bench-tools.sh`,
md5-verified). No panel/MCU/CPLD firmware, no fuse, no app.
