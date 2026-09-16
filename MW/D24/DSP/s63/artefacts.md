provenance: AI-drafted 2026-09-16 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S63 — gain-change artefacts, MIC 5 (J25), MW-D24-2

Session 63, 2026-09-16. Findings S63-1..4 in `findings.md`. Captures, logs and the analysis output are in `data/`. Tools are in `tools/`.

## Set-up

- **Pair:** the s62 handshake pair (`DSP4_TEST_NODES=1`, chip1 `57948d77`, chip2 `251ce3b2`), staged at `~/s63` and booted
  and configured D24 twice. The bulk read (S61/S62) read every capture: median 0.220 s, max 0.293 s, **0 overruns in 144 + 8 + 64 captures**.
- **Loop:** TEST_OSC on donor strip 6 → AUX 1 → J45 → loop cable → J25 → MIC 5 preamp (U41, send p15) → U39 → strip 5
  (transparent) → TEST_MEAS capture arm (post-fader).
- **Chain:** the S55 image, with the 16 powered registers open at code 0 and U15's muted, sent by spidev. `app cli chain-set`
  was not used because `matrix-app` was inactive as found. **CS_M (GPIO 27) was driven by a GPSET0/GPCLR0 register write on
  `/dev/gpiomem`**, so the latch is one instruction. The pin was already an output, and its function and pull were never changed.
- AN_EN and CS_M both read `hi` before and after, and neither was written.
- **Stimulus A (silent):** oscillator off. The source is the loop cable into the AUX 1 output stage; no 150 Ω is fitted.
  That source's floor at the lane is −104.6 dBFS RMS at code 0 and −51.9 dBFS RMS at code 63
  (S61 EIN on the same loop source: −52.25 dBFS).
- **Stimulus B (tone):** 1 kHz, set so the louder side of each transition is −8 dBFS pk at the ADC and at the lane, from the S55 law.
  The fitted level change matched the law to within 0.004 dB on all 70 transitions.
- **Walk:** each transition starts where the last one ended, ≥ 3.00 s after the previous change of any kind (min 3.00 s).
  One capture per transition per stimulus; 8.6 min for all 144.

## Timing: where the change is in the capture

- **Arm and poll.** `s63lib.Rig.span` arms 16,384 samples, then polls `_meas_cap_idx_C1_TEST_MEAS`, the samples copied so far.
  The poll runs at ~1 ms (104 polls to the 4,800 mark). The polls give the host-clock → capture-sample map.
  - Residual spread within a capture: median 10.1 samples, max 16.4, i.e. one 16-sample block.
  - A poll read just after the change landed within −20…+4 samples of the map's prediction.
  - The latch edge is bracketed to ≤ 1.4 samples, a Gain001 write to ≤ 16.2.
  - **The host places a change to ± 16 samples (± 0.33 ms).**
- **Digital trim.** The lane starts moving at the write's own sample (host +0), so the map is good to within a block.
  The GainFast ramp is **linear**: exactly 144 samples up (3 ms) and 384 down (8 ms).
- **Hardware step (`s63_latch.py`, `data/latch.out`).** The **pass-1 CS_M rising edge applies the gain**.
  - With a 50 ms gap before pass 2, the lane still reaches 50 % at the same place: +436…+503 samples after pass 1, and
    2,081…2,149 samples *before* pass 2's edge.
  - **Latch → 50 %: 9.1 ms down, 10.2–10.5 ms up (0↔1), repeatable to ± 6 samples.**
  - Over all clean table steps: up median 10.5 ms (10.2–12.2), down median 9.0 ms (8.4–9.4).
  - That delay belongs to the preamp's control path. The DSP and converter path accounts for ~1 ms (S60 loop latency 91 samples, DAC + ADC).

## Summary

**J25 summary.** SILENT: 70 transitions, **68 PASS / 2 FLAG** (0 peak, 2 pump); artefact detected above the floor on 4; worst -74.0 dBFS hw_up 0→1; longest pump > 231 ms bit 0→1. TONE: 2 PASS / 68 FLAG against an instantaneous step (worst residual -10.1 dBFS bit 31→32); hardware delay latch→50 % 6.1/9.8/15.3 ms (min/median/max); trim write→50 % 1.3..3.9 ms; 25 of 62 hardware/combined steps glitch > 1 dB past the step (worst +0.0 / -36.0 dB bit 31→32). No-change captures detected: 0 of 4.

- **SILENT: 68 PASS / 2 FLAG on PW's limit (artefact peak ≤ −60 dBFS at the lane, no DC pump > 50 ms).**
  - Only 4 of 70 transitions put anything above the floor, all at codes 0↔1:
    - **0→1 is a thump**: DC ↓ −78.2 dBFS (5.0 × floor RMS), τ 163 ms, pump 229 ms. The second capture of 0→1 (bit set)
      shows DC −85 dBFS, still open at the capture end. Both captures FLAG on pump.
    - 1→0 is a −81 dBFS click with an 11 ms pump. It passes.
  - No other hardware step, trim or combined change is detectable in silence.
  - **But the floor rises with gain.** From code 29 up, the floor RMS is ≥ −60 dBFS (peak ≥ −46 dBFS), so the −60 dBFS
    limit cannot be tested in silence at the gains where it matters. The tone residual is the sensitive measurement there.
- **TONE: 2 PASS / 68 FLAG against an instantaneous step.**
  - As specified, the residual subtracts an *instantaneous* step, so it also carries the change's own finite transition.
    Clean hardware steps take median 1.5 ms 10–90 % (max 5.0) and 10.9 ms median to settle to 0.1 dB. Trims take the
    3/8 ms ramp. The residual peak therefore reads −10…−43 dBFS on every change except 61↔63 (0.16 dB, in the floor:
    the 2 PASS).
  - The flag says "not instantaneous". It does not say "an artefact was added".
- **THE ARTEFACT THE TONE DOES FIND: a gain DROPOUT on multi-bit hardware steps**, 25 of 62 hardware/combined steps
  (table below).
  - During the transition the gain falls to the gain of **(from AND to)**: bits switching off act before bits switching on.
  - The partial dips match the S55 law's gain at the AND code to 0.1 dB (23↔25, 47↔53, 11→13, 31↔37 within 0.8 dB).
  - The deep ones read shallower than predicted because they last only a few ms and the 1-cycle envelope smooths them:
    31→32 predicted −46.2 dB, measured −36.0.
  - Settle to 0.1 dB takes 12–24 ms.
  - Steps that only switch bits on, or only off (0→1, 2→3, 4→5, 6→7 …), are clean. 5→6 dips 0.8 dB (predicted 1.2), under the 1 dB note threshold.
- **Level and phase are continuous.** Level change matches the law within 0.004 dB. Phase step is ≤ 0.14°.
  The fitted DC shift post − pre is ≤ 1.9 × the residual floor everywhere.
- **Combined 30 ↔ 31 dB** (code 6↔7 latch, then the trim write 3.8 ms later): no glitch, delay 9.2/10.3 ms, and nothing in silence.
  The trim lands ~6 ms *before* the preamp step reaches the lane, because of the hardware delay above.

### Dropout on multi-bit steps (tone, 1-cycle amplitude envelope)

| kind | from | to | from AND to | predicted dip below the quieter code, dB (S55 law, J25) | measured 1-cycle envelope dip, dB | settle to 0.1 dB, ms |
|---|---:|---:|---:|---:|---:|---:|
| bit | 31 | 32 | 0 | -46.2 | -36.0 | 24.2 |
| bit | 32 | 31 | 0 | -46.2 | -34.4 | 18.8 |
| bit | 15 | 16 | 0 | -38.6 | -30.5 | 20.2 |
| bit | 7 | 8 | 0 | -30.6 | -26.8 | 17.8 |
| bit | 16 | 15 | 0 | -38.6 | -25.6 | 16.9 |
| hw_up | 15 | 17 | 1 | -25.7 | -23.2 | 19.7 |
| hw_dn | 17 | 15 | 1 | -25.7 | -21.7 | 16.8 |
| hw_up | 3 | 4 | 0 | -22.1 | -18.5 | 14.7 |
| bit | 8 | 7 | 0 | -30.6 | -18.5 | 14.4 |
| bit | 3 | 4 | 0 | -22.1 | -18.5 | 14.7 |
| hw_up | 31 | 37 | 5 | -18.0 | -17.4 | 23.0 |
| hw_dn | 37 | 31 | 5 | -18.0 | -17.2 | 19.0 |
| hw_up | 7 | 9 | 1 | -17.8 | -16.8 | 17.5 |
| hw_dn | 9 | 7 | 1 | -17.8 | -13.5 | 14.3 |
| bit | 4 | 3 | 0 | -22.1 | -11.7 | 13.0 |
| hw_dn | 4 | 3 | 0 | -22.1 | -11.2 | 13.0 |
| hw_dn | 2 | 1 | 0 | -12.8 | -8.9 | 12.2 |
| bit | 2 | 1 | 0 | -12.8 | -8.9 | 12.2 |
| bit | 1 | 2 | 0 | -12.8 | -6.7 | 13.2 |
| hw_up | 1 | 2 | 0 | -12.8 | -6.5 | 13.0 |
| hw_up | 23 | 25 | 17 | -1.8 | -1.8 | 14.8 |
| hw_dn | 25 | 23 | 17 | -1.8 | -1.7 | 12.7 |
| hw_up | 47 | 53 | 37 | -1.6 | -1.6 | 15.8 |
| hw_dn | 53 | 47 | 37 | -1.6 | -1.6 | 13.9 |
| hw_up | 11 | 13 | 9 | -1.2 | -1.2 | 12.9 |

## T3 addendum — THD only (h2..h10) at maximum and minimum gain, MIC 5

`s63_thd.py` / `s63_thd_analyse.py`, `data/thd.out`, `data/s63_thd_J25.json`. **Method:**
- 1 kHz in 16,320-sample captures: exactly 340 cycles, 1,020 blocks, every harmonic on a bin, rectangular window.
- Lane trimmed to **−3.00 dBFS pk** (3 dB below clip) at each code.
- 32 bulk-read captures per code, **averaged coherently**: each capture's bins are rotated by k × its fundamental phase,
  so noise falls by 10 log 32 = 15 dB per bin and the harmonics stay.
- A first attempt at 999.0234 Hz (341 cycles in 16,384) was off-bin. TEST_OSC read the word back exact but ran at
  1000.0000 Hz, so it does not honour a fractional frequency. That run is not used.

| code | THD (h2–h10) | per-bin floor, 32 averaged / 1 capture | h2 | h3 | h4 | h5 | h6 | h7 | h8 | h9 | h10 |
|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 63 (max) | **−64.3 dB = 0.061 %** | −103.2 / −88.0 dBc | **−70.7** | **−71.7** | −71.8 | −77.0 | −76.0 | −91.3 | −77.4 | −96.1 | −70.7 dBc |
| 0 | **−89.5 dB = 0.0034 %** | −154.7 / −139.9 dBc | **−102.1** | **−90.1** | −133.7 | −100.5 | −122.6 | −119.3 | −126.2 | −127.2 | −127.3 dBc |

- **Every harmonic is well clear of the averaged per-bin floor**: ≥ 7 dB at code 63 (h9), ≥ 27 dB at code 0.
- **At code 63 the harmonics are the signal's own.** The incoherent (power) average agrees with the coherent one to
  ≤ 1 dB at h2–h6, h8 and h10, and h10's rotated phase holds within ± 16° across captures.
  - h7 and h9 read lower coherently than incoherently (9 kHz: −96 vs −77 dBc), so a component at 9 kHz is not phase-locked
    to the tone. The coherent value is the harmonic.
  - No 3 kHz block-rate line stands above the floor at code 63 in the silent captures, so h3/h6/h9 are not a block-rate artefact.
- The code-63 figure is preamp + ADC at maximum gain. The DAC runs at −61.7 dBFS digital there.
- At code 0 the DAC runs at −8.6 dBFS, so that figure is the whole loop. It agrees with S61's THD+N at code 0 (−88.96 dB).

## Running it on the other 15 channels (the runner is ready)

On the bench, with the loop cable moved by hand and the unit as S63 found it:

    cd ~/s63 && bash boot.sh /home/app/s63                   # the s62 handshake pair, D24, twice
    SYMDIR=/home/app/s63 python3 s56_setup.py                 # donor strip 6 -> AUX 1, MIC 5 strip transparent
    DONE=J25 python3 s63_run.py | tee s63_run_all.out         # WATCH -> channel -> "PROMPT >>> move the loop cable" -> WATCH

- **Lane detection** is S55's WATCH: 1 kHz on AUX 1, all 16 powered registers at code 0, 3 agreeing scans.
- **Per channel:** presence check against the S55 law, then 144 captures (≈ 8.6 min).
- **All 15:** ≈ 2.2 h of instrument time plus the cable moves.
- **J27 = strip 6:** the donor moves to strip 1, as in S55.
- **Desk:** `scp app@192.168.1.219:s63/data/J*.{bin,jsonl} DIR/`, then `python3 tools/s63_analyse.py DIR` for every channel's
  tables and summary line.
- **Hand-back:** as this session (s60 pair twice, `s56_setup.py`, `s60_handback.py`, `s60_found.py`).
- **Not exercised this session:** the WATCH path. MIC 5 ran with `CHAN=J25`. `scan`, `set_donor` and `watch` are S55's own
  code on this rig; `set_donor`, strip save/restore and the AN_EN read did run.
- Single-channel form: `CHAN=J3x python3 s63_run.py`.

## Full tables — MIC 5 (J25)

Columns are defined in `tools/s63_analyse.py`'s header.
- Silent-case detection thresholds come from the no-change captures. At every 480-sample offset, the AC peak never
  exceeded the floor RMS by more than 14.6 dB, and the DC excursion never exceeded 0.90 × floor RMS. Detection is
  set at AC peak > 3 dB over the old/new floor peak, or DC > 1.5 × floor RMS. 0 of 4 no-change captures detect.
- `*` / `>`: the pump is still open at the capture end. "drift": no decay inside the capture.

**J25 — A SILENT (oscillator off; source = loop cable into the AUX 1 output stage) — NO CHANGE (the analysis floor)**

| from | to | peak dBFS | duration ms | energy dB re floor | DC step dBFS / τ / pump | character | new floor rms / pk dBFS | pass/flag |
|---|---|---:|---:|---:|---|---|---|---|
| 0 | 0 | ≤ floor | 0 | -0.6 | — | none | -104.6 / -92.7 | PASS (in floor) |
| 63 | 63 | ≤ floor | 0 | -0.3 | — | none | -51.9 / -39.1 | PASS (in floor) |

**J25 — A SILENT (oscillator off; source = loop cable into the AUX 1 output stage) — HARDWARE STEPS — consecutive table codes, trim 0 dB**

| from | to | peak dBFS | duration ms | energy dB re floor | DC step dBFS / τ / pump | character | new floor rms / pk dBFS | pass/flag |
|---|---|---:|---:|---:|---|---|---|---|
| 0 | 1 | -74.0 | 18 | +1.0 | ↓-78.2 / τ 163 ms, pump 229 ms | thump | -92.2 / -80.1 | FLAG (pump) |
| 1 | 2 | ≤ floor | 0 | -5.7 | — | none | -85.5 / -74.1 | PASS (in floor) |
| 2 | 3 | ≤ floor | 0 | -2.4 | — | none | -82.8 / -70.7 | PASS (in floor) |
| 3 | 4 | ≤ floor | 0 | -4.8 | — | none | -78.2 / -65.8 | PASS (in floor) |
| 4 | 5 | ≤ floor | 0 | -1.3 | — | none | -76.9 / -64.4 | PASS (in floor) |
| 5 | 6 | ≤ floor | 0 | -1.9 | — | none | -75.3 / -63.3 | PASS (in floor) |
| 6 | 7 | ≤ floor | 0 | +0.0 | — | none | -74.5 / -61.1 | PASS (in floor) |
| 7 | 9 | ≤ floor | 0 | -4.4 | — | none | -70.2 / -56.7 | PASS (in floor) |
| 9 | 10 | ≤ floor | 0 | +0.1 | — | none | -69.5 / -57.2 | PASS (in floor) |
| 10 | 11 | ≤ floor | 0 | -0.3 | — | none | -68.7 / -55.7 | PASS (in floor) |
| 11 | 13 | ≤ floor | 0 | -1.5 | — | none | -67.3 / -54.9 | PASS (in floor) |
| 13 | 15 | ≤ floor | 0 | -0.7 | — | none | -66.3 / -54.3 | PASS (in floor) |
| 15 | 17 | ≤ floor | 0 | -2.9 | — | none | -63.3 / -52.0 | PASS (in floor) |
| 17 | 20 | ≤ floor | 0 | -1.1 | — | none | -62.0 / -47.8 | PASS (in floor) |
| 20 | 23 | ≤ floor | 0 | -0.6 | — | none | -61.2 / -50.9 | PASS (in floor) |
| 23 | 25 | ≤ floor | 0 | -1.3 | — | none | -60.1 / -47.5 | PASS (in floor) |
| 25 | 29 | ≤ floor | 0 | -1.0 | — | none | -59.0 / -45.6 | PASS (in floor) |
| 29 | 31 | ≤ floor | 0 | -0.5 | — | none | -58.6 / -46.5 | PASS (in floor) |
| 31 | 37 | ≤ floor | 0 | -3.7 | — | none | -56.0 / -40.9 | PASS (in floor) |
| 37 | 42 | ≤ floor | 0 | -1.0 | — | none | -54.8 / -43.0 | PASS (in floor) |
| 42 | 47 | ≤ floor | 0 | -0.1 | — | none | -54.5 / -40.6 | PASS (in floor) |
| 47 | 53 | ≤ floor | 0 | -1.5 | — | none | -53.2 / -39.5 | PASS (in floor) |
| 53 | 61 | ≤ floor | 0 | -1.2 | — | none | -51.9 / -39.9 | PASS (in floor) |
| 61 | 63 | ≤ floor | 0 | -0.5 | — | none | -51.9 / -38.5 | PASS (in floor) |
| 63 | 61 | ≤ floor | 0 | +0.6 | — | none | -52.0 / -40.1 | PASS (in floor) |
| 61 | 53 | ≤ floor | 0 | +1.0 | — | none | -53.1 / -40.6 | PASS (in floor) |
| 53 | 47 | ≤ floor | 0 | +1.4 | — | none | -54.4 / -41.1 | PASS (in floor) |
| 47 | 42 | ≤ floor | 0 | +0.2 | — | none | -54.9 / -42.8 | PASS (in floor) |
| 42 | 37 | ≤ floor | 0 | +1.1 | — | none | -56.0 / -41.4 | PASS (in floor) |
| 37 | 31 | ≤ floor | 0 | +1.2 | — | none | -58.8 / -46.7 | PASS (in floor) |
| 31 | 29 | ≤ floor | 0 | +1.0 | — | none | -59.2 / -47.4 | PASS (in floor) |
| 29 | 25 | ≤ floor | 0 | +0.8 | — | none | -60.0 / -47.5 | PASS (in floor) |
| 25 | 23 | ≤ floor | 0 | +1.8 | — | none | -61.4 / -50.0 | PASS (in floor) |
| 23 | 20 | ≤ floor | 0 | +0.8 | — | click | -62.0 / -48.3 | PASS (in floor) |
| 20 | 17 | ≤ floor | 0 | +0.8 | — | zipper | -63.0 / -51.9 | PASS (in floor) |
| 17 | 15 | ≤ floor | 0 | +1.8 | — | none | -66.3 / -51.3 | PASS (in floor) |
| 15 | 13 | ≤ floor | 0 | +0.7 | — | none | -67.3 / -55.3 | PASS (in floor) |
| 13 | 11 | ≤ floor | 0 | +1.2 | — | none | -68.8 / -55.6 | PASS (in floor) |
| 11 | 10 | ≤ floor | 0 | +0.3 | — | none | -69.2 / -57.1 | PASS (in floor) |
| 10 | 9 | ≤ floor | 0 | +0.6 | — | none | -70.1 / -58.6 | PASS (in floor) |
| 9 | 7 | ≤ floor | 0 | +4.2 | — | none | -74.4 / -62.4 | PASS (in floor) |
| 7 | 6 | ≤ floor | 0 | +0.4 | — | none | -75.1 / -62.9 | PASS (in floor) |
| 6 | 5 | ≤ floor | 0 | +1.9 | — | none | -77.0 / -63.7 | PASS (in floor) |
| 5 | 4 | ≤ floor | 0 | +0.9 | — | none | -78.0 / -64.7 | PASS (in floor) |
| 4 | 3 | ≤ floor | 0 | +4.5 | — | zipper | -82.9 / -70.8 | PASS (in floor) |
| 3 | 2 | ≤ floor | 0 | +2.9 | — | click | -85.3 / -72.9 | PASS (in floor) |
| 2 | 1 | ≤ floor | 0 | +6.5 | — | click | -92.1 / -80.0 | PASS (in floor) |
| 1 | 0 | -81.1 | 17 | +10.5 | ↓-93.6 / τ 5 ms, pump 11 ms | click | -104.6 / -93.2 | PASS |

**J25 — A SILENT (oscillator off; source = loop cable into the AUX 1 output stage) — MAJOR-CARRY CODE CHANGES, trim 0 dB**

| from | to | peak dBFS | duration ms | energy dB re floor | DC step dBFS / τ / pump | character | new floor rms / pk dBFS | pass/flag |
|---|---|---:|---:|---:|---|---|---|---|
| 31 | 32 | ≤ floor | 0 | -2.9 | — | none | -56.7 / -45.3 | PASS (in floor) |
| 32 | 31 | ≤ floor | 0 | +0.3 | — | none | -58.8 / -47.4 | PASS (in floor) |
| 15 | 16 | ≤ floor | 0 | -3.7 | — | none | -63.3 / -50.0 | PASS (in floor) |
| 16 | 15 | ≤ floor | 0 | +1.5 | — | none | -66.5 / -53.5 | PASS (in floor) |
| 7 | 8 | ≤ floor | 0 | -3.6 | — | none | -70.9 / -58.4 | PASS (in floor) |
| 8 | 7 | ≤ floor | 0 | +3.1 | — | none | -74.5 / -62.9 | PASS (in floor) |
| 3 | 4 | ≤ floor | 0 | -5.3 | — | none | -78.0 / -65.5 | PASS (in floor) |
| 4 | 3 | ≤ floor | 0 | +4.7 | — | click | -83.0 / -70.2 | PASS (in floor) |
| 1 | 2 | ≤ floor | 0 | -6.4 | — | none | -85.7 / -72.1 | PASS (in floor) |
| 2 | 1 | ≤ floor | 0 | +7.1 | — | click | -92.0 / -80.0 | PASS (in floor) |
| 0 | 1 | -75.4 | 17 | -1.9 | ↑-85.0 / drift, > 231 ms | thump | -91.9 / -79.9 | FLAG (pump) |
| 1 | 0 | -81.0 | 14 | +11.0 | ↓-95.1 / τ 63 ms, pump 11 ms | click | -104.6 / -92.2 | PASS |

**J25 — A SILENT (oscillator off; source = loop cable into the AUX 1 output stage) — DIGITAL TRIM at code 0 (Gain001, GainFast ramp)**

| from | to | peak dBFS | duration ms | energy dB re floor | DC step dBFS / τ / pump | character | new floor rms / pk dBFS | pass/flag |
|---|---|---:|---:|---:|---|---|---|---|
| +0 dB | +1 dB | ≤ floor | 0 | -0.6 | — | none | -103.4 / -89.7 | PASS (in floor) |
| +1 dB | +0 dB | ≤ floor | 0 | +0.6 | — | thump | -104.4 / -92.8 | PASS (in floor) |
| +0 dB | +3 dB | ≤ floor | 0 | +0.0 | — | none | -101.6 / -90.1 | PASS (in floor) |
| +3 dB | +0 dB | ≤ floor | 0 | +1.3 | — | none | -104.6 / -91.6 | PASS (in floor) |
| +0 dB | +6 dB | ≤ floor | 0 | -0.5 | — | none | -98.5 / -86.5 | PASS (in floor) |
| +6 dB | +0 dB | ≤ floor | 0 | +3.8 | — | none | -104.7 / -93.2 | PASS (in floor) |
| +0 dB | +12 dB | ≤ floor | 0 | -0.9 | — | none | -92.6 / -79.7 | PASS (in floor) |
| +12 dB | +0 dB | ≤ floor | 0 | +7.8 | — | none | -104.5 / -92.4 | PASS (in floor) |

**J25 — A SILENT (oscillator off; source = loop cable into the AUX 1 output stage) — COMBINED — target 30 ↔ 31 dB through the table (code latch, then the trim write)**

| from | to | peak dBFS | duration ms | energy dB re floor | DC step dBFS / τ / pump | character | new floor rms / pk dBFS | pass/flag |
|---|---|---:|---:|---:|---|---|---|---|
| c6 +0.315 | c7 +0.401 | ≤ floor | 0 | -0.6 | — | none | -74.0 / -58.7 | PASS (in floor) |
| c7 +0.401 | c6 +0.315 | ≤ floor | 0 | +0.6 | — | none | -74.9 / -61.1 | PASS (in floor) |

**J25 — B TONE 1 kHz, louder side −8 dBFS pk; artefact metrics on the RESIDUAL against an instantaneous step at the 50 % point — NO CHANGE (the analysis floor)**

| from | to | Δlevel dB (law) | Δphase ° | delay ms | 10–90 % ms | settle 0.1 dB ms | excursion dB over / under | residual peak dBFS | duration ms | energy dB | DC shift dBFS (×floor) | character | residual floor rms dBFS | pass/flag |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|---:|---|
| 0 | 0 | -0.00 (+0.00) | +0.00 | — | — | — | +0.0 / +0.0 | ≤ floor | 0 | +2.6 | ↓-136.9 (0.0) | none | -104.4 | PASS (in floor) |
| 63 | 63 | +0.00 (+0.00) | +0.08 | — | — | — | +0.0 / +0.0 | ≤ floor | 0 | +0.3 | ↓-81.2 (0.0) | none | -53.7 | PASS (in floor) |

**J25 — B TONE 1 kHz, louder side −8 dBFS pk; artefact metrics on the RESIDUAL against an instantaneous step at the 50 % point — HARDWARE STEPS — consecutive table codes, trim 0 dB**

| from | to | Δlevel dB (law) | Δphase ° | delay ms | 10–90 % ms | settle 0.1 dB ms | excursion dB over / under | residual peak dBFS | duration ms | energy dB | DC shift dBFS (×floor) | character | residual floor rms dBFS | pass/flag |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|---:|---|
| 0 | 1 | +12.85 (+12.84) | -0.07 | 10.3 | 1.5 | 11.9 | +0.0 / -0.0 | -18.5 | 35 | +54.2 | ↑-96.6 (0.7) | click | -93.1 | FLAG (peak) |
| 1 | 2 | +6.62 (+6.62) | -0.00 | 10.7 | 1.3 | 13.0 | +0.0 / -6.5 | -18.3 | 36 | +51.1 | ↑-100.1 (0.2) | click | -87.5 | FLAG (peak, glitch) |
| 2 | 3 | +2.67 (+2.67) | +0.00 | 10.2 | 1.4 | 11.2 | +0.0 / -0.0 | -27.7 | 23 | +38.1 | ↑-97.7 (0.2) | click | -84.9 | FLAG (peak) |
| 3 | 4 | +4.76 (+4.76) | +0.01 | 11.7 | 1.6 | 14.7 | +0.0 / -18.5 | -13.6 | 36 | +50.0 | ↓-117.4 (0.0) | click | -80.0 | FLAG (peak, glitch) |
| 4 | 5 | +1.24 (+1.24) | +0.01 | 10.4 | 1.3 | 11.0 | +0.0 / -0.0 | -29.7 | 19 | +28.3 | ↓-105.8 (0.0) | click | -79.0 | FLAG (peak) |
| 5 | 6 | +1.56 (+1.56) | +0.01 | 10.8 | 1.3 | 11.8 | +0.0 / -0.8 | -28.6 | 22 | +32.5 | ↓-97.9 (0.1) | click | -77.1 | FLAG (peak) |
| 6 | 7 | +0.91 (+0.91) | +0.01 | 10.3 | 1.4 | 10.9 | +0.0 / -0.0 | -34.8 | 19 | +22.2 | ↓-92.7 (0.2) | click | -76.5 | FLAG (peak) |
| 7 | 9 | +4.29 (+4.29) | +0.04 | 12.7 | 2.5 | 17.5 | +0.0 / -16.8 | -13.6 | 37 | +43.2 | ↓-118.8 (0.0) | click | -72.1 | FLAG (peak, glitch) |
| 9 | 10 | +0.75 (+0.75) | +0.01 | 10.8 | 1.4 | 11.2 | +0.0 / -0.4 | -34.5 | 19 | +21.4 | ↓-95.2 (0.1) | click | -71.4 | FLAG (peak) |
| 10 | 11 | +0.47 (+0.47) | +0.00 | 10.4 | 1.2 | 10.8 | +0.0 / -0.0 | -38.3 | 18 | +12.9 | ↑-90.4 (0.1) | click | -70.8 | FLAG (peak) |
| 11 | 13 | +1.57 (+1.57) | +0.02 | 11.5 | 1.6 | 12.9 | +0.0 / -1.2 | -27.4 | 24 | +27.9 | ↓-86.0 (0.1) | click | -69.3 | FLAG (peak, glitch) |
| 13 | 15 | +0.90 (+0.90) | +0.02 | 10.4 | 1.6 | 11.2 | +0.0 / -0.0 | -35.0 | 20 | +15.2 | ↑-90.5 (0.1) | click | -68.3 | FLAG (peak) |
| 15 | 17 | +3.25 (+3.25) | +0.07 | 13.4 | 3.9 | 19.7 | +0.0 / -23.2 | -11.8 | 37 | +38.1 | ↓-87.6 (0.1) | click | -65.0 | FLAG (peak, glitch) |
| 17 | 20 | +1.16 (+1.16) | +0.03 | 11.2 | 1.7 | 12.4 | +0.0 / -0.2 | -32.8 | 20 | +14.3 | ↑-107.5 (0.0) | click | -64.0 | FLAG (peak) |
| 20 | 23 | +0.69 (+0.69) | +0.02 | 10.4 | 1.6 | 11.0 | +0.0 / -0.0 | -35.6 | 16 | +9.3 | ↓-101.9 (0.0) | click | -63.1 | FLAG (peak) |
| 23 | 25 | +1.14 (+1.14) | +0.03 | 12.8 | 2.6 | 14.8 | +0.0 / -1.8 | -23.5 | 23 | +25.2 | ↑-84.9 (0.1) | click | -62.0 | FLAG (peak, glitch) |
| 25 | 29 | +0.98 (+0.98) | +0.04 | 11.1 | 1.9 | 12.2 | +0.0 / -0.0 | -35.6 | 18 | +9.8 | ↓-110.4 (0.0) | click | -61.2 | FLAG (peak) |
| 29 | 31 | +0.36 (+0.36) | +0.02 | 10.4 | 1.5 | 10.8 | +0.0 / -0.0 | -43.1 | 16 | +2.6 | ↑-90.6 (0.0) | click | -60.8 | FLAG (peak) |
| 31 | 37 | +2.79 (+2.78) | +0.13 | 14.5 | 5.3 | 23.0 | +0.0 / -17.4 | -12.0 | 35 | +32.2 | ↑-98.7 (0.0) | click | -58.1 | FLAG (peak, glitch) |
| 37 | 42 | +1.00 (+1.00) | +0.06 | 12.2 | 2.4 | 14.1 | +0.0 / -0.7 | -30.6 | 20 | +13.5 | ↑-82.6 (0.1) | click | -57.2 | FLAG (peak) |
| 42 | 47 | +0.64 (+0.64) | +0.04 | 11.2 | 1.8 | 12.0 | +0.0 / -0.0 | -36.4 | 17 | +4.0 | ↑-80.2 (0.1) | click | -56.3 | FLAG (peak) |
| 47 | 53 | +1.37 (+1.38) | +0.11 | 12.9 | 3.2 | 15.8 | +0.0 / -1.6 | -24.5 | 22 | +17.7 | ↑-91.7 (0.0) | click | -54.9 | FLAG (peak, glitch) |
| 53 | 61 | +1.02 (+1.02) | +0.08 | 12.1 | 2.5 | 13.6 | +0.0 / -0.0 | -31.7 | 18 | +5.7 | ↑-80.9 (0.0) | click | -54.0 | FLAG (peak) |
| 61 | 63 | +0.16 (+0.16) | +0.11 | 10.6 | 1.8 | 10.2 | +0.0 / -0.0 | ≤ floor | 0 | -0.4 | ↑-87.8 (0.0) | none | -53.7 | PASS (in floor) |
| 63 | 61 | -0.15 (-0.16) | -0.01 | 8.9 | 5.0 | 8.8 | +0.0 / -0.0 | ≤ floor | 0 | +0.7 | ↑-89.9 (0.0) | none | -53.8 | PASS (in floor) |
| 61 | 53 | -1.02 (-1.02) | -0.08 | 8.9 | 2.1 | 9.5 | +0.0 / -0.0 | -32.4 | 14 | +6.7 | ↑-88.4 (0.0) | click | -54.9 | FLAG (peak) |
| 53 | 47 | -1.37 (-1.38) | -0.02 | 7.7 | 2.8 | 13.9 | +0.0 / -1.6 | -25.0 | 19 | +19.6 | ↑-102.1 (0.0) | click | -56.3 | FLAG (peak, glitch) |
| 47 | 42 | -0.64 (-0.64) | -0.03 | 9.2 | 1.5 | 9.8 | +0.0 / -0.0 | -36.5 | 14 | +4.7 | ↓-85.4 (0.0) | click | -57.1 | FLAG (peak) |
| 42 | 37 | -1.00 (-1.00) | -0.06 | 8.4 | 1.7 | 11.9 | +0.0 / -0.7 | -30.6 | 17 | +14.7 | ↓-88.7 (0.0) | click | -58.0 | FLAG (peak) |
| 37 | 31 | -2.79 (-2.78) | -0.14 | 6.5 | 3.2 | 19.0 | +0.0 / -17.2 | -12.0 | 36 | +34.9 | ↑-93.7 (0.0) | click | -60.8 | FLAG (peak, glitch) |
| 31 | 29 | -0.36 (-0.36) | -0.01 | 9.0 | 1.5 | 9.3 | +0.0 / -0.0 | -41.6 | 14 | +3.6 | ↓-83.7 (0.1) | click | -61.1 | FLAG (peak) |
| 29 | 25 | -0.98 (-0.98) | -0.04 | 9.2 | 1.5 | 9.7 | +0.0 / -0.0 | -33.5 | 14 | +11.2 | ↓-85.7 (0.1) | click | -62.1 | FLAG (peak) |
| 25 | 23 | -1.14 (-1.14) | -0.04 | 8.2 | 2.0 | 12.7 | +0.0 / -1.7 | -23.9 | 19 | +25.6 | ↑-120.1 (0.0) | click | -63.1 | FLAG (peak, glitch) |
| 23 | 20 | -0.69 (-0.69) | -0.02 | 9.2 | 1.4 | 9.7 | +0.0 / -0.0 | -35.8 | 14 | +10.0 | ↑-81.2 (0.1) | click | -63.8 | FLAG (peak) |
| 20 | 17 | -1.15 (-1.16) | -0.03 | 9.0 | 1.4 | 10.4 | +0.0 / -0.1 | -31.4 | 19 | +14.5 | ↑-100.5 (0.0) | click | -65.2 | FLAG (peak) |
| 17 | 15 | -3.25 (-3.25) | -0.07 | 7.3 | 2.6 | 16.8 | +0.0 / -21.7 | -12.0 | 31 | +42.2 | ↓-126.3 (0.0) | click | -68.4 | FLAG (peak, glitch) |
| 15 | 13 | -0.90 (-0.90) | -0.02 | 9.0 | 1.5 | 9.4 | +0.0 / -0.0 | -33.0 | 16 | +16.4 | ↓-78.1 (0.4) | click | -69.3 | FLAG (peak) |
| 13 | 11 | -1.57 (-1.57) | -0.02 | 9.0 | 1.2 | 11.5 | +0.0 / -0.9 | -28.9 | 19 | +27.4 | ↓-98.8 (0.0) | click | -70.9 | FLAG (peak) |
| 11 | 10 | -0.47 (-0.47) | -0.01 | 9.4 | 1.3 | 9.5 | +0.0 / -0.0 | -38.1 | 14 | +13.3 | ↓-90.6 (0.1) | click | -71.3 | FLAG (peak) |
| 10 | 9 | -0.75 (-0.75) | -0.01 | 8.7 | 1.1 | 10.9 | +0.0 / -0.5 | -34.2 | 18 | +23.2 | ↑-107.4 (0.0) | click | -72.0 | FLAG (peak) |
| 9 | 7 | -4.29 (-4.29) | -0.04 | 8.1 | 2.0 | 14.3 | +0.0 / -13.5 | -13.9 | 29 | +47.1 | ↓-93.7 (0.1) | click | -76.5 | FLAG (peak, glitch) |
| 7 | 6 | -0.91 (-0.91) | -0.01 | 9.4 | 1.2 | 9.9 | +0.0 / -0.0 | -33.2 | 27 | +21.7 | ↑-97.1 (0.1) | click | -77.3 | FLAG (peak) |
| 6 | 5 | -1.56 (-1.56) | -0.01 | 8.7 | 1.1 | 11.1 | +0.0 / -1.0 | -27.8 | 20 | +35.8 | ↑-104.9 (0.1) | click | -78.9 | FLAG (peak) |
| 5 | 4 | -1.24 (-1.24) | -0.01 | 9.4 | 1.2 | 9.9 | +0.0 / -0.0 | -30.1 | 19 | +28.5 | ↑-97.5 (0.1) | click | -80.1 | FLAG (peak) |
| 4 | 3 | -4.76 (-4.76) | -0.01 | 8.7 | 1.3 | 13.0 | +0.0 / -11.2 | -14.7 | 28 | +53.2 | ↑-93.9 (0.4) | click | -85.0 | FLAG (peak, glitch) |
| 3 | 2 | -2.67 (-2.67) | -0.00 | 9.2 | 1.2 | 10.1 | +0.0 / -0.0 | -25.9 | 19 | +41.4 | ↑-109.1 (0.1) | click | -87.5 | FLAG (peak) |
| 2 | 1 | -6.62 (-6.62) | +0.00 | 8.8 | 1.0 | 12.2 | +0.0 / -8.9 | -17.7 | 28 | +59.7 | ↓-106.2 (0.2) | click | -94.0 | FLAG (peak, glitch) |
| 1 | 0 | -12.85 (-12.84) | +0.07 | 9.3 | 1.2 | 10.5 | +0.0 / -0.0 | -16.0 | 20 | +69.6 | ↓-128.0 (0.1) | click | -105.7 | FLAG (peak) |

**J25 — B TONE 1 kHz, louder side −8 dBFS pk; artefact metrics on the RESIDUAL against an instantaneous step at the 50 % point — MAJOR-CARRY CODE CHANGES, trim 0 dB**

| from | to | Δlevel dB (law) | Δphase ° | delay ms | 10–90 % ms | settle 0.1 dB ms | excursion dB over / under | residual peak dBFS | duration ms | energy dB | DC shift dBFS (×floor) | character | residual floor rms dBFS | pass/flag |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|---:|---|
| 31 | 32 | +2.01 (+2.00) | +0.10 | 15.3 | 6.4 | 24.2 | +0.0 / -36.0 | -10.1 | 37 | +34.5 | ↑-89.9 (0.0) | click | -58.7 | FLAG (peak, glitch) |
| 32 | 31 | -2.00 (-2.00) | -0.09 | 6.1 | 3.2 | 18.8 | +0.0 / -34.4 | -10.1 | 31 | +37.6 | ↑-88.1 (0.0) | click | -60.9 | FLAG (peak, glitch) |
| 15 | 16 | +3.01 (+3.01) | +0.06 | 13.8 | 3.9 | 20.2 | +0.0 / -30.5 | -11.2 | 43 | +38.6 | ↓-83.8 (0.1) | click | -65.4 | FLAG (peak, glitch) |
| 16 | 15 | -3.01 (-3.01) | -0.06 | 7.4 | 2.6 | 16.9 | +0.0 / -25.6 | -11.3 | 29 | +43.1 | ↓-81.8 (0.2) | click | -68.4 | FLAG (peak, glitch) |
| 7 | 8 | +3.75 (+3.75) | +0.03 | 13.1 | 2.9 | 17.8 | +0.0 / -26.8 | -12.1 | 38 | +45.1 | ↓-96.4 (0.1) | click | -72.7 | FLAG (peak, glitch) |
| 8 | 7 | -3.75 (-3.75) | -0.03 | 8.1 | 2.1 | 14.4 | +0.0 / -18.5 | -12.8 | 29 | +48.3 | ↓-103.0 (0.0) | click | -76.4 | FLAG (peak, glitch) |
| 3 | 4 | +4.76 (+4.76) | +0.01 | 11.8 | 1.8 | 14.7 | +0.0 / -18.5 | -13.7 | 38 | +49.8 | ↑-96.6 (0.1) | click | -80.0 | FLAG (peak, glitch) |
| 4 | 3 | -4.76 (-4.76) | -0.01 | 8.7 | 1.3 | 13.0 | +0.0 / -11.7 | -14.9 | 27 | +53.1 | ↑-91.1 (0.5) | click | -84.8 | FLAG (peak, glitch) |
| 1 | 2 | +6.62 (+6.62) | -0.00 | 10.9 | 1.3 | 13.2 | +0.0 / -6.7 | -18.0 | 36 | +51.1 | ↓-116.2 (0.0) | click | -87.4 | FLAG (peak, glitch) |
| 2 | 1 | -6.62 (-6.62) | +0.00 | 8.8 | 1.0 | 12.2 | +0.0 / -8.9 | -17.5 | 33 | +59.4 | ↑-88.8 (1.9) | click | -94.2 | FLAG (peak, glitch) |
| 0 | 1 | +12.85 (+12.84) | -0.07 | 10.3 | 1.5 | 12.1 | +0.0 / -0.0 | -20.2 | 32 | +54.2 | ↓-99.7 (0.5) | click | -93.1 | FLAG (peak) |
| 1 | 0 | -12.85 (-12.84) | +0.07 | 9.4 | 1.4 | 10.5 | +0.0 / -0.0 | -15.3 | 24 | +68.9 | ↓-110.1 (0.6) | click | -105.8 | FLAG (peak) |

**J25 — B TONE 1 kHz, louder side −8 dBFS pk; artefact metrics on the RESIDUAL against an instantaneous step at the 50 % point — DIGITAL TRIM at code 0 (Gain001, GainFast ramp)**

| from | to | Δlevel dB (law) | Δphase ° | delay ms | 10–90 % ms | settle 0.1 dB ms | excursion dB over / under | residual peak dBFS | duration ms | energy dB | DC shift dBFS (×floor) | character | residual floor rms dBFS | pass/flag |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|---:|---|
| +0 dB | +1 dB | +1.00 (+1.00) | +0.00 | 1.3 | 2.5 | 2.6 | +0.0 / +0.0 | -34.3 | 12 | +56.7 | ↓-121.0 (0.1) | click | -103.9 | FLAG (peak) |
| +1 dB | +0 dB | -1.00 (-1.00) | -0.00 | 3.8 | 6.2 | 7.1 | +0.0 / -0.0 | -33.3 | 19 | +60.0 | ↓-126.7 (0.1) | click | -104.8 | FLAG (peak) |
| +0 dB | +3 dB | +3.00 (+3.00) | -0.00 | 1.3 | 2.2 | 2.8 | +0.0 / +0.0 | -25.7 | 16 | +62.6 | ↓-117.5 (0.2) | click | -102.6 | FLAG (peak) |
| +3 dB | +0 dB | -3.00 (-3.00) | -0.00 | 3.9 | 6.2 | 7.7 | +0.0 / -0.0 | -24.7 | 17 | +69.8 | ↑-113.1 (0.4) | click | -105.5 | FLAG (peak) |
| +0 dB | +6 dB | +6.00 (+6.00) | +0.00 | 1.3 | 2.2 | 2.8 | +0.0 / +0.0 | -21.1 | 12 | +65.9 | ↑-121.9 (0.1) | click | -99.9 | FLAG (peak) |
| +6 dB | +0 dB | -6.00 (-6.00) | -0.00 | 3.8 | 6.5 | 7.9 | +0.0 / -0.0 | -20.3 | 17 | +74.7 | ↑-133.8 (0.0) | click | -105.9 | FLAG (peak) |
| +0 dB | +12 dB | +12.00 (+12.00) | +0.00 | 1.3 | 2.2 | 2.8 | +0.0 / +0.0 | -17.6 | 12 | +63.4 | ↑-119.4 (0.1) | click | -93.8 | FLAG (peak) |
| +12 dB | +0 dB | -12.00 (-12.00) | +0.00 | 3.8 | 6.5 | 8.1 | +0.0 / -0.0 | -16.7 | 17 | +78.2 | ↓-134.0 (0.0) | click | -105.9 | FLAG (peak) |

**J25 — B TONE 1 kHz, louder side −8 dBFS pk; artefact metrics on the RESIDUAL against an instantaneous step at the 50 % point — COMBINED — target 30 ↔ 31 dB through the table (code latch, then the trim write)**

| from | to | Δlevel dB (law) | Δphase ° | delay ms | 10–90 % ms | settle 0.1 dB ms | excursion dB over / under | residual peak dBFS | duration ms | energy dB | DC shift dBFS (×floor) | character | residual floor rms dBFS | pass/flag |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|---:|---|
| c6 +0.315 | c7 +0.401 | +1.00 (+1.00) | +0.01 | 10.3 | 1.6 | 10.9 | +0.0 / -0.0 | -33.2 | 18 | +24.7 | ↓-97.1 (0.1) | click | -75.9 | FLAG (peak) |
| c7 +0.401 | c6 +0.315 | -1.00 (-1.00) | -0.01 | 9.2 | 1.5 | 9.8 | +0.0 / -0.0 | -31.8 | 30 | +22.5 | ↑-110.0 (0.0) | click | -76.9 | FLAG (peak) |

