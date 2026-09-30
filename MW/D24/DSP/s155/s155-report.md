provenance: AI-drafted 2026-09-30 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S155 — patch-station usability fixes, the P1 bug, and one open ruling

Hub dispatch `tasks.md` 2026-09-30 17:36Z, plus three addenda added while this
session was running (2026-09-30 ~18:50, ~18:55, ~19:00). Proofs:
`MW/D24/DSP/s155/measure_stall_check.py` (+ `.out`),
`MW/D24/DSP/s155/patch_glass_checks.py` (+ `.out`).

## 1. ALREADY-CARRYING SOCKET -- and the real bug underneath it

The dispatch's original item 1 asked for a status line the moment `hot0`
fires. The mid-session addenda (hub ~18:50, PW ~19:00) reframed it: P1 (AUX 1
-> MIC 1) failed the same way on four separate runs, and PW confirmed nothing
was plugged before the prompt. That ruled out operator timing. The real bug:

**`hot0` compared two different instruments.** For a MIC-strip tone row,
`lvl0` (`detect`'s baseline at the prompt) comes off the strip's PEAK meter
(`watch`'s own branch). `prep['floor']` was `self.floors[lane]`, a NODE RMS
reading taken once at `measure_floors()`. A peak-hold meter reads well above
an RMS number on ordinary idle noise alone -- no lead, no transient -- and
MIC 1's gap was apparently over `detect_rise_db` (12 dB), so `hot0` came back
True on an empty socket. The removal edge it then demanded never came (there
was nothing to remove), the step burned its full 40 s, and `find_loop`'s own
retry-then-give-up path silently moved the walk on to the next candidate
(MIC 3) -- which is the "reparked to MIC 3" PW watched happen.

**Fix (`d24_patch.py`):** `Station` now keeps a second per-lane baseline,
`self.peak_floors`, taken on the SAME instrument as `lvl0` -- two peeks of
`meter_peak`, `WIN_S` apart, the lower one kept, right beside the existing RMS
`measure_floors()` loop. `_prepare` carries it in `prep['peak_floor']`.
`detect`'s `hot0` now reads `prep['peak_floor']` for a MIC-strip lane (same
instrument as `lvl0`) and only falls back to the RMS `floor` for the lanes
whose own `watch()` reading already is RMS (the codec/mini-jack returns,
which were never the mismatched case). `where_is_it`'s sweep had the
identical mismatch -- its readings are peak too, and it was comparing them
against the same RMS `self.floors` -- fixed the same way (see item 2).

Also done, per the addendum's own list:
- **(a) logged at every prompt:** one line per tone row -- lane, `lvl0`,
  `floor0`, which instrument, `rise`, `hot0` -- so a stuck step reads off the
  log, not the bench.
- The UX line from the original item 1 stays: the moment `hot0` is true the
  glass says "`<socket>` already has signal - unplug the lead and plug it
  back in" and the log says so too (`LV.status_already_carrying`). With the
  instrument fixed this now only fires on a genuinely hot socket.
- **(c) PW's proposed relaxation** (accept a correct tone at the prompt
  without a removal edge when nothing else carries it, demanding the edge
  only when the previous patch used the same socket) is **not implemented**.
  PW's ~19:00 message treats the cause as a pure detector bug and asks for
  the instrument fix, not the relaxation -- left as a 🔴 note below in case
  it is still wanted once (c) is read against the fixed detector.

**Proof (`patch_glass_checks.py`):**
- `test_p1_an_idle_lane_with_a_loud_peak_floor_still_arrives`: MIC 1 modelled
  with an RMS floor of -90 dBFS and a peak floor of -76 dBFS (14 dB gap, close
  to MIC 15's measured -75.5 dBFS -- S153), **nothing on the lane until poll
  5**, then the operator's plug. The old formula (`peak - RMS >= rise`) is
  shown true on the unchanged numbers; the fixed station still arrives, at
  the plug-in (dt < 2 s, not the 40 s hard stop), and the log carries
  `hot0 False` on the peak instrument.
- `test_p1_vs_p3_why_lane_1_differs_from_lane_3`: MIC 1 modelled with a 14 dB
  peak/RMS gap (clears `rise`, the one that broke); MIC 3 modelled with a 5 dB
  gap (does not) -- consistent with MIC 3 passing normally on the bench in
  today's runs while MIC 1 did not. (These are modelled gaps, not bench
  measurements; the real two numbers are stated as a 🔴 ask below.)
- `test_already_carrying_says_so_at_once` / `..._never_hot_gets_the_plain_screen`:
  the UX line fires exactly when `hot0` is true and never otherwise; the
  removal+arrival rule is unchanged.

## 2. WRONG-SOCKET FALSE ALARM

`where_is_it`'s sweep used a flat -90 dBFS cutoff on `meter_sweep`'s peak
readings. MIC 15's own floor (-75.5 dBFS, S153, the noisiest on the unit)
clears that on its own. Fixed two ways, both proven on a modelled noisy-floor
lane:

- **The margin is now over that lane's own PEAK floor** (`self.peak_floors`,
  not the RMS `self.floors` -- the identical instrument mismatch as item 1,
  fixed the same way), by the same `detect_rise_db` an arrival has to clear.
- **The claim needs `DETECT_STABLE_SAMPLES` (2) consecutive sweeps naming
  the SAME lane**, not one peek, before it is shown -- `_look_elsewhere` now
  tracks a streak (`self._wrong_candidate` / `self._wrong_hits`) instead of
  acting on the first hit. A lane that clears the margin once and is gone on
  the next sweep is never named.

Proof: a lane sitting still at its own (loud) floor is never named across a
full run; the same lane genuinely carrying `rise` dB over its own floor is
still named, inside two sweep cycles (not the 20 s/40 s timeout fallback); a
single noisy sweep that does not repeat is never named.

## 3. NO SILENT INFINITE WAITS

`Unit.measure()`'s two wait-for-counter loops (the settle wait, and the
per-window read loop, including its "window turned over mid-read" retry,
which had no bound at all) now raise `MeasureStalled` -- a named exception,
caught by the station's existing generic error reporting (`AutoPhase._go`
and its like already turn any exception into a line on the glass) -- when the
TEST_MEAS counter sits still for `MEASURE_STALL_S` (20 windows, ~1.7 s,
comfortably more than any settle/read request in the tree). A live counter
that keeps moving is unaffected.

Proof (`measure_stall_check.py`): a counter frozen from the first call raises
in the settle loop; one that settles and then freezes raises in the read
loop; one that keeps moving (tied to the virtual clock, one turnover per
`WIN_S`, as a real counter behaves) never raises and returns well inside the
bound.

## What is NOT done: the "never move past a fail" ruling

PW's ruling (~18:55): no station of RUN ALL may advance past a failed step
(timeout, no signal, wrong socket, undeclared NO DATA) without an explicit
operator decision (NO SIGNAL / RETRY / PAUSE) -- no auto-repark, no
auto-advance on a timeout, applied to every station, not only the patch one.

**This is not implemented.** It is a cross-station control-flow change, not a
bounded bug fix, and per the session's own tiering rule (`CLAUDE.md`, "a
session launched on sonnet... does NOT push through" design-grade or
unknown-shape work) it needs scoping beyond what this dispatch gave. Two
concrete mechanisms are already identified as in scope for the patch station:

- `Station.find_loop()` (`d24_patch.py` ~L3940 area): after `MAX_DEAF_IN_A_ROW`
  misses on a candidate input it silently tries the next one -- this is the
  literal "MIC 3 -> MIC 4 -> MIC 5" PW watched.
- `Station._run()`'s per-patch retry path (~L3770 area): after `MAX_RETRIES`
  reprompts, `nodata()` records NODATA and the `for` loop silently continues
  to the next patch.

Neither the panel loop nor the gain-step phase in `d24_runall.py` has been
read this session, so "every station" is still unscoped there. A new
operator-facing decision (NO SIGNAL / RETRY / PAUSE, as a positive choice
rather than a timeout's fallback) also does not exist yet on the glass for
this failure shape.

## Deployed

Between runs, with backups, per the dispatch's own authority (a script/config
deploy, no DSP pair boot, no flash). MW-D24-2 (`app@192.168.1.219`):

- The live run was at the SUMMARY page when stopped (`sudo systemctl stop
  d24-factory`) -- already past its own handback (AN_EN low, SAFE chain
  verified 200/200 per the log), not mid-patch. `runall/state.json` untouched
  (md5 `ef070f58bc48db544b46c076b82a4afb`), resumable.
- Backup: `/home/app/backup-s155-pre/` (`d24_patch.py` `c55013b6`,
  `d24_live.py` `a4f47340`, `d24_runall.py` `ea21925d` -- all three matched
  this repo's pre-S155 HEAD before the copy).
- Deployed: `d24_patch.py` (md5 `62a4616c`), `d24_live.py` (md5 `950b43b2`),
  both matching this repo; `d24_runall.py` untouched (unchanged by this
  dispatch, still `ea21925d`).
- `d24-factory` left INACTIVE. Nobody should press START without reading the
  🔴 notes below first.

## 🔴 for PW / the hub

1. **Deployed items 1-3 only.** The "never move past a fail" ruling above is
   not in this deploy -- the CONCRETE bug that caused P1's repark (the
   instrument mismatch) is fixed, so the specific failure should not recur,
   but the GENERAL auto-repark-on-exhausted-retries mechanism is still there
   for any other failure. Wanted: confirm whether to press START now on
   items 1-3 alone, or hold for the ruling. If held, this needs a fresh
   dispatch scoped across `d24_runall.py`'s panel and gain phases (opus-tier
   per the tiering rule, given it is cross-station and touches the confirm
   protocol).
2. **PW's proposed relaxation (addendum item c)** -- accept a correct tone at
   the prompt without demanding a removal edge, when nothing else on the unit
   carries it, demanding the edge only when the previous patch used the same
   socket -- was not built. PW's later ~19:00 message treated this as a pure
   detector bug rather than asking for the relaxation; if the relaxation is
   still wanted on top of the instrument fix, say so and it is a small,
   separate change.
3. **The real MIC 1 vs MIC 3 numbers.** `test_p1_vs_p3_why_lane_1_differs_from_lane_3`
   is a MODEL (14 dB vs 5 dB, chosen to straddle `rise`), not a bench
   reading -- this session had no live access to take the actual peak/RMS
   pair for MIC 1 and MIC 3. If it is useful for the record, a
   `dsp4_mtr_state.py`-style peek of both lanes' peak meter against a fresh
   `measure_floors()`-style RMS read, idle, would confirm or correct the
   model.
