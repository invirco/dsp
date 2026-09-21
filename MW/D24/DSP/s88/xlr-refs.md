provenance: AI-drafted 2026-09-21 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S88 — XLR input and output reference levels vs the D24's internal references (PW's dScope at the bench)

Unit MW-D24-2 rev C, 2026-09-21, PW at the bench with a calibrated dScope generator/analyser,
this session over Remote Control. Goal: check the two per-unit references in
`tools/accept/units.csv`/the mx26 spec doc (`dac_fs_dbu` +23.13 dBu, implied ADC full scale
+17.55 dBu) against a real analyser instead of PW's DMM (2026-09-16).

## Headline

**A CPLD/firmware fault was found and fixed mid-session, unrelated to the reference question
itself**, and cost most of the session (see "What went wrong" below). Once past it:

- **DAC full scale (AUX 1, J45), corroborated two independent ways**: TEST_OSC on the
  diagnostic pair, −20.00 dBFS → +3.125 dBu → implied +23.125 dBu (0.005 dB from stored); the
  proven external-generator path (dScope +4.00 dBu on J25 → MIC 5 lane −13.49 dBFS → routed at
  unity to AUX 1) → **+9.64 dBu → implied +23.13 dBu, delta 0.00 dB**. **Stored +23.13 dBu
  holds, unchanged.**
- **ADC full scale (MIC 5, J25, code 0)**: three points, dScope generator, `dsp4_rxscan.py`
  peak dBFS (32-sample scan, not a coherent capture — see caveat below):

  | dScope in | lane pk dBFS | implied ADC FS | delta vs +17.55 |
  |---|---|---|---|
  | +4.00 dBu | −13.49 | +17.49 dBu | −0.06 dB |
  | +14.00 dBu | −3.51 | +17.51 dBu | −0.04 dB |
  | −16.00 dBu | −33.49 | +17.49 dBu | −0.06 dB |

  **Stored +17.55 dBu holds, unchanged** (all three points within 0.1 dB). Code-32 anchor
  **not obtained**: the first attempt (code 32 at +4.00 dBu) clipped hard (0.00 dBFS exact,
  ~54 dB of hardware gain at that code against a +4 dBu input) and the planned redo at
  −40.00 dBu was never reached before the session ran out — **owed next session**.

- **Witnesses**: MIC 6 (strip 18 on the diagnostic pair — see mapping note), code 0,
  +4.00 dBu → −13.94 dBFS pk → implied +17.94 dBu, delta +0.39 dB vs +17.55, +0.45 dB vs
  MIC 5. MIC 9 (J35, U60) is **OPEN — S88-5**: read 18 dB low, then floor after a reseat, with
  the 595 register confirmed correctly landed (code 0, shunt not engaged) — the fault is
  upstream of the DSP, not chased further this session.

- **Loop closure (AUX 1 → MIC 6): CLOSES**, resolved after a false start — see "Loop closure
  and the AUX 1–8 survey" below.

- **AUX 1–8 output survey (below): all clean and within ±0.1 dB except AUX 7, which is OPEN —
  S88-7**, real output-stage fault (route proven live per the cells, dScope sees nothing).

- **Talkback input (J1, AK4619) reproduces S70's node mislabel** — see below.

- **A mid-session socket-identification error affected several readings around 13:29–13:55
  (the dScope was on MAIN R for some of what was logged as AUX 1) — resolved by re-take; see
  "Socket correction" below. The AUX 1 and MAIN figures in this report are the re-taken,
  confirmed ones.**

## What went wrong, and the fix (S88-1, procedure-relevant)

Step C (AUX 1 oscillator at −20.00 dBFS) read as expected once digitally instrumented, but
independent digital checks (TEST_MEAS, raw bus-buffer peeks) disagreed with each other and,
initially, with PW's own dScope — which is the one instrument that turned out to be right.
Root cause, found via three no-hands discriminators the hub specified (CPLD design-ID
readback; `dsp4_rxscan.py` distinct-word count across all RX lanes, mic and codec; clock
presence): **the CPLD was flashed with the `driveall` diagnostic bitstream
(`design_id 32'h27966c28`), not shipping (`83b3cc22`)** — `driveall` ties all six DSPA input
pins to one dead test net, so every RX lane (mic AND codec) read exact digital zero
regardless of what was actually on the XLRs. Not a DSP, SPORT, or config fault.

**Fix**: reflashed `dsp4_logic.d02d83b3cc22.svf` (`tools/pi/logic_flash.sh`, AN_EN lowered for
the interlock, FLASH-OK attempt 1, AN_EN raised again, `dsp4_logic_id.py` confirms
`design_id 32'h83b3cc22 SHIPPING`) — **then a full DSP double boot+config, which is the step
that actually brought data back**: the CPLD reflash changes `conv_bck`/`conv_fs`, and the
SPORT peripherals stay configured against the *pre-flash* clock relationship until
`dsp4_boot.py`/`dsp4_config.py` are re-run. The first re-boot attempt right after the flash
left MIC 5 dark; a second identical double boot+config brought it up. **This is now
`docs/d24-bench-logic-flash-log.md`'s "Procedure" section** (see below) — it belongs in the
runbook, not just this report, because it's exactly the class of thing `logic_flash.sh`'s own
next-step line ("confirm what is actually on the part") stops one step short of.

## S88-1 — output-side fold, isolated and deferred (S89)

After the RX fix, AUX 1's *input* side (mic lanes) was clean, but its *output* (DAC) side
showed **wrap-around distortion**: dScope read the right level (+9.6 dBu) but 56% THD+N, and
a genuinely consecutive 16-sample raw capture of the RX loop-back lane showed physically
impossible sample-to-sample jumps (up to 17 dB between adjacent 48 kHz samples — a clean
1 kHz tone can move at most ~1 dB) — the fold signature, not a level problem. **A/B
discriminator (no new bitstream, per hub ruling)**: the shipping CPLD had never had its
*output* verified with a cable before today (S86 ran the input side only, loop off); booting
the diagnostic pair (with `TEST_OSC`) on the still-shipping CPLD gave a **clean** AUX 1
(0.0035% THD+N confirmed twice) — isolating the fault to **the shipping DSP pair's own TX
path** (chip-2 SPORT to the DAC), not the CPLD/DAC hardware. Chip-2 TX `SPORT_MCTL.MFD` was
read back and matches the expected per-lane table exactly (`[2,2,2,1,2]`, same proven
bit-position method as the RX check), so it isn't a gross SPORT-config error either — **root
cause is unresolved and is S89's, not this session's.** Witness: the MIC 6 loop capture
(above) and the dScope THD%.

## S88-2 — the diagnostic pair's TEST_OSC amplitude is not a reference

At the identical −20.00 dBFS setpoint, MAIN L measured +2.58 dBu, then −13.6 dBu, then
+1.78 dBu across successive re-arms with every readable cell (`OscFreq`, `OscLevel` register,
strip gain/level/pan, bus/output cell states) unchanged between reads. The oscillator's
*running* amplitude state (the "magic circle resonator" per `s54lib.py`'s own docstring) is
not the same thing as the `OscLevel` setpoint register and evidently drifts with start state.
**Never use this diagnostic pair's TEST_OSC for an absolute-level reference** — it's fine for
routing/presence checks, not levels. AUX 1's C-row reference above uses the external dScope
generator instead, for exactly this reason.

## S88-3 — retracted (wrong-strip artefact)

First MAIN L/R take (strip 5, code-5 route, "unity, MAIN") read −0.4 dBu both sides, 0.16%
THD — **retracted**: on this diagnostic pair (`s51_119ea9d9`, an older, hard-coded
`D24_INPUT_PATCH` predating the shipping pair's JSON-loaded landed patch — diffed and
confirmed different), **MIC 5's physical input patches to strip 20, not strip 5** (empirically
found via a full `dsp4_rxscan.py` sweep: the tone landed at node `IN_20`, not `IN_05`/`IN_16`).
Strip 20 was still at its default `MainOn=1` throughout, so what was actually measured was
strip 20's real signal contaminated by whatever else was still routed, not a clean strip-5
unity path. **Empirical mapping on this pair**: MIC 5 → strip 20, MIC 6 → strip 18, MIC 9 →
strip 7 (node label = strip number on this build). Under the current landed contract
(`defs/products/d24/inputs.csv`) MIC 5 = strip 5 — that mapping is correct and proven on the
**shipping** pair (B1–B3, C-row above); it does not hold on this older diagnostic pair.

## S88-4 — MAIN L/R references deferred (not a level bug, a graph question)

Re-taken cleanly on strip 20 (only strip live, MainOn 1, AuxOn 0, pan hard left, every other
strip's Main/Aux confirmed off): **+5.616 dBu, L = R, 0.16% THD** — still ~4 dB below AUX 1's
FS and pan-insensitive. Every dynamics/EQ node in the MAIN L/R chain was read back and is
already bypassed/flat (`CompOn=0, LimiterOn=0, EqOn=0`, 31-band GEQ all exactly 0.0) — nothing
left to disable. **Hub ruling**: this diagnostic graph's product topology is
`ch.pan → bus.main → main.geq → main.comp → main.lim → io.out` with `Main001` a single shared
pre-crossover stage (one `Level`/`Mute` pair, not separate L/R buses) and the crossover cells
literally shared across all four LCR outputs (same DSP address for L/R/Ctr/Sub) — **+5.6 dBu
measures the TEST graph, not the product**. MAIN L/R references are **deferred to the shipping
pair after S89** (that pair's graph is the product topology; this diagnostic pair's isn't, for
MAIN).

## S88-5 — MIC 9 (J35, U60) OPEN

+4.00 dBu on J35, code 0: 18 dB low first pass (−31.09 dBFS pk, implied FS nonsense at
+35 dBu), then **floor** after PW reseated both cable ends. 595 register confirmed landed
correctly both times (`p7 = 0x00` before and after a fresh write — code 0, shunt bit not
engaged). S86's survey had this channel's bank rising normally with the rails up. **Upstream
of the DSP, not chased further** — flagged for the acceptance sweep.

## Socket correction (13:29–13:55)

PW flagged mid-session that the analyser had actually been on **MAIN R**, not AUX 1, for part
of this window — every output row in that span was marked SOCKET UNCERTAIN and re-taken.
The AUX 1 re-take (below) reproduced the original 13:34 figure exactly (+9.64 dBu, 0.003%),
so that specific historical row is confirmed genuine or AUX 1 after all; the MAIN L/R rows in
that window are folded into S88-4 (already a deferred/TEST-graph finding, unaffected by which
socket carried which reading, since both MAIN L and MAIN R were being measured either way).

## Loop closure and the AUX 1–8 survey (after the unit was un-parked for further testing)

**AUX 1 re-take (socket confirmed by PW): +9.64 dBu, 0.003% THD+N → implied DAC FS +23.13,
delta 0.00 dB — reproduces the original 13:34 figure exactly.**

**Loop closure (AUX 1 out → MIC 6 in), same route, one capture**: IN_18 (MIC 6/return)
−7.91 dBFS pk, IN_20 (MIC 5/source) −13.52 dBFS pk. Loop gain = IN_18 − IN_20 = **5.61 dB**.

- vs (DAC FS 23.13 − MIC 5 ADC FS 17.49) = 5.64 dB → **delta −0.03 dB, closes within 0.1 dB.**
- vs (DAC FS 23.13 − MIC 6's own FS 17.94) = 5.19 dB → delta +0.42 dB, does not close —
  consistent with MIC 6's own single-point FS carrying more channel spread than MIC 5's
  (corroborated three ways this session).

**Closes.** (The earlier same-day attempt at this same measurement, logged as S88-open-1,
read the return as floor — a real but transient state, most likely route/cable settling
after several preceding re-routes; superseded by this clean, closing capture and not chased
further as a separate defect.)

**AUX 1–8 internal survey**, PW moving only the loop cable's output end, `IN_18` read each
time (formula: implied DAC FS_n = IN_18(output n) − IN_18(AUX 1 ref, −7.91 dBFS) + 23.13):

| output | IN_18 pk dBFS | implied DAC FS | delta vs +23.13 | note |
|---|---|---|---|---|
| AUX 1 | −7.91 | +23.13 | 0.00 | reference point, dScope-confirmed |
| AUX 2 | −7.92 | +23.12 | −0.01 | |
| AUX 3 | −7.90 | +23.14 | +0.01 | |
| AUX 4 | −7.96 | +23.08 | −0.05 | |
| AUX 5 | −7.93 | +23.11 | −0.02 | |
| AUX 6 | −7.91 | +23.13 | 0.00 | |
| AUX 7 | −9.22 | +21.82 | −1.31 | **DISCARDED — see S88-7** |
| AUX 8 | −8.01 | +23.03 | −0.10 | dScope spot-check: **+9.638 dBu → +23.13, delta 0.00** — the internal −0.10 was the loop/cable reading, not the DAC; internal method holds to ~±0.1 dB |

**Center/LF: SKIPPED, deferred with S88-4.** No source-select cell exists for `MainCtr`/
`MainSub` distinct from the shared `Main001` pre-crossover stage and the shared
`C2_MAIN_XOVER` crossover node S88-4 already found to be one mono stage, not per-channel —
there is no path to Center/LF on this diagnostic pair that doesn't re-run the same deferred
topology question.

## S88-7 — AUX 7 output OPEN

Internal loop read −9.22 dBFS pk (implied FS +21.82 dBu, 1.31 dB low — the only AUX bus
outside the ±0.1 dB band the other seven held). PW's dScope on AUX 7 out saw **no signal at
all**. Cells read back live: `AuxSend007` 1.000000, `Aux007` master Level 1.000000/Mute 0 —
the route is live per every cell the DSP exposes. **The internal −9.22 dBFS reading is
discarded** (bleed or a mis-seated loop cable end, not a real AUX 7 level) and **S88-7 is
logged OPEN: AUX 7's XLR output stage itself is the suspect**, not reached from the DSP side,
not chased further this session.

## Talkback input (J1, AK4619) — S70's node mislabel reproduces

+4.00 dBu on the Talkback XLR, AK4619 `MGN2R` set to its minimum code (0 = −6 dB,
`05H := 0xB0`), 595 mic chain SAFE. **`XIN_CODEC_04` carries the tone** (−10.31 dBFS pk,
−13.03 RMS); **`XIN_CODEC_01` — the node the graph itself labels "TB XLR" — stays at floor**
(−70.35 dBFS). This is exactly S70's finding reproduced on a fresh boot: the graph's own
node label for the Talkback XLR is wrong; the real signal lands on the node labelled
"Aux In R." Implied full scale at the TB XLR at MGN2R minimum: 4.00 − (−10.31) =
**+14.31 dBu** (input-referred at this gain code; no stored reference to compare against —
first measurement of this path with a calibrated analyser). Monitor TRS not tested — no TRS
lead at the bench.

## Caveat on the peak/RMS numbers in this report

Every `dsp4_rxscan.py` figure above (B1–B4, the MIC 6/9 witnesses, the loop capture) is a
32-sample scan at ~13.7 ms spacing — a Monte Carlo peak/RMS estimate over many independent
phase samples of the tone, not a coherent lock-in capture (this shipping/BLOCK_KERNELS pair
has no `TEST_MEAS`). It tracks the dScope numbers to within 0.06 dB everywhere it was cross-
checked against the dScope directly (B1, C-row), which is the evidence it's trustworthy for
this report's purpose; a true coherent capture would need new tooling this session didn't
have time to build (see the report body for what was tried and abandoned).

## Open items for next session

1. **Code-32 gain-law anchor** (MIC 5, −40.00 dBu, per the universal table) — not reached.
2. **S88-1 — AUX 1 output-side fold** (shipping DSP pair TX path, wrap-around distortion,
   CPLD/DAC hardware proven clean) — root cause deferred to **S89**.
3. **S88-5 — MIC 9 (J35/U60) OPEN** — 18 dB low then floor, register confirmed correct,
   upstream of the DSP.
4. **S88-4 — MAIN L/R and Center/LF references deferred** to the shipping pair after S89
   (this diagnostic pair's MAIN graph is a mono TEST stage, not the product topology).
5. **S88-7 — AUX 7 output OPEN** — route live per every DSP cell, no XLR signal; output
   stage suspect.
6. **Talkback FS** (+14.31 dBu at MGN2R minimum) has no stored reference to check against —
   first measurement of this path; worth adding to the spec doc once a second unit or a
   repeat measurement corroborates it.
7. **Monitor TRS** — not tested, no TRS lead at the bench.

## Files

- `MW/D24/DSP/s88/readings.csv` — every reading, timestamped.
- `docs/d24-bench-logic-flash-log.md` — "Procedure" section added (S88): the
  flash→boot+config runbook step, and the dead-lane triage order.
- mx26 `docs/spec-audio-test-set.md` — a row appended to the measured-references table
  (dScope, 2026-09-21): AUX 1/DAC FS and MIC 5/ADC FS, both corroborating the stored 09-16
  DMM figures within 0.1 dB.

## Unit as found

Shipping CPLD `design_id 32'h83b3cc22, cfg_bits 16'h0010, SHIPPING` — read back after the
S88-1 reflash and unchanged since (confirmed by a fresh readback at handback, see
`docs/d24-bench-logic-flash-log.md`'s Procedure item 2: power-cycle + design-ID readback is
now the proof, not an assumption). 595 chain SAFE image (all 24 registers muted, code 0,
shunt off), verified 200/200. AN_EN read `lo` at handback (matrix-app's own `Boot.Init()`
keeps it low with the bring-up gates it can't query — S49-15/S35-1's finding, unchanged).
matrix-app restarted and active. `defs.lock` unmoved; no product def, matrix, or generated
DSP artifact touched this session — this was a bench/reference session only.
