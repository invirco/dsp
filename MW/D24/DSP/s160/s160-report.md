provenance: AI-drafted 2026-10-01 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S160 — MIC 1-4 noise-floor FFT audit, OPEN inputs (MW-D24-2, 2026-10-01)

Ordered by HUB ADDENDUM 3/4 to S159 (PW ~13:50/13:55 BST): "run some manual fft audits on mic 1-4 noise floors, to see what is causing noise failures", **unterminated, nothing plugged, no hand steps**.

**These are open-input figures. They are not EIN.** EIN is defined with a 150 ohm source (limits.csv `t4b_ein_max_dbu` −126.0 dBu, `t4b_ein_a_max_dbu` −129.5 dBu(A)), and nothing in this audit is graded against those limits. The open-input spectra are for finding the source of the excess.

## Method

- Booted pair `/home/app/loopthd/s154` (pair.conf), its own symbol map. Tools in `/home/app/s160` (nothing in `/home/app/selftest` changed).
- Per setting: that input's preamp at the gain code with the phantom shunt released and phantom off; the other 23 inputs shunted at gain 0 (`Analog.step_image`, the factory station's image). Rails raised and lowered by the audit, CS_M driven.
- The strip made transparent the station's way: the list's 219 `_standing_bypass` processing cells are read, bypassed, and restored to the values found (219/219 read back). Every strip assign is shut.
- MeasChan on the strip. The node is polled until two windows agree (≥ 5 s), then **6 × 16,384-sample captures** through the TEST_MEAS capture arm (`dsp4_meascap`, the S56/S57 instrument), plus node RmsResult over 4 windows. Zero block overruns on every capture.
- Desk: mean-removed Hann periodograms, averaged (2.93 Hz bins). Band totals are mean square (a full-scale sine reads −3.01 dBFS). Input-referred by S57-R: dBu = P + 3.01 + 23.13 (units.csv) − G, where G = the lane's code-0 loop gain from today's factory pass 4 (5.28 dB on MIC 1, 5.54–5.55 dB on MIC 2–5) + the code's step from defs `mic-gain-codes.csv` (53.108 dB at code 63).
- Tools: `tools/s160_audit.py` (unit), `tools/s160_analyse.py`, `tools/s160_hf.py`, `tools/s160_ab.py` (desk). Raw data: `data/*.json`, `data/ab/`. Outputs: `s160_analyse.out`, `s160_hf.out`, `s160_ab.out`.

## Results (code 63, open)

| input | node RMS dBFS | 20–20k dBFS | A dBFS | input-ref. 20–20k dBu | input-ref. A dBu |
|---|---:|---:|---:|---:|---:|
| MIC 1 | −75.09 | −80.56 | −83.77 | −112.8 | −116.0 |
| MIC 2 | −73.44 | −73.87 | −80.80 | −106.4 | −113.3 |
| MIC 3 | −74.26 | −74.68 | −81.08 | −107.2 | −113.6 |
| MIC 4 | −72.64 | −74.29 | −80.47 | −106.8 | −113.0 |
| MIC 5 | −77.25 | −81.14 | −84.19 | −113.7 | −116.7 |

MIC 2 by code (open): code 0 −114.47 dBFS (converter floor), code 32 −78.75, code 48 −76.09, code 63 −73.87 (20–20k, lane).

**Per octave, input-referred, MIC 2/3/4 over MIC 5:** every octave from 20 Hz to 10 kHz is within about ±1.5 dB (MIC 1 likewise). **10–20 kHz: +9.0 / +8.1 / +8.5 dB.** All of the excess is in the top octave (`s160_analyse.out`, plots `s160-excess-vs-mic5.png`, `s160-mic1-5-open-c63.png`).

**The shape is one narrowband component, not a raised floor.** In 1 kHz bands the excess is a hump about 1–2 kHz wide, +16 to +22 dB over MIC 5 in its band: MIC 2 at 18.9 kHz, MIC 3 at 18.2 kHz, MIC 4 at 17.8 kHz (`s160_hf.out`). Every channel, MIC 1 and MIC 5 included, also carries a small fixed bump in the 19 kHz band (about +8 dB over its neighbours, present at code 0 too). That is a separate, common, converter-side feature, and it matches the hub's 19.7–19.9 kHz lines in the S55 captures.

**A/B, time vs gain (`s160_ab.out`): the hump DRIFTS WITH TIME, not with the gain code.** On MIC 2, codes alternated 63 → 48 → 63 → 32 → 63 over about 2.5 min. At the SAME code 63 the peak walked **18.9 → 17.7 → 16.9 kHz**, while codes 48 (19.9k) and 32 (19.4k) sat off that trend. MIC 4, captured straight after MIC 2, peaked at the same frequency (16.6 kHz, then 18.1k at code 48, then 16.0k at code 63). The first run's MIC 2 → 3 → 4 order (18.9 → 18.2 → 17.8k) is the same drift. **One source, shared by the MIC 1–4 group at a given moment, sliding about 1 kHz/min downward after the rails come up.** Its lane level hardly moves between codes 48 and 63 (−75.1 vs −75.2 dBFS, 14–21.5 kHz), so part of it does not scale with preamp gain.

**Not found:** no 60/120/240 Hz family on MIC 1–5 (all within ±3.5 dB of the local floor). A 49.8 Hz line at +11 to +17 dB on EVERY open input at code 63, MIC 1 and MIC 5 included: open-input mains pickup, not a MIC 2–4 feature. No 1/f excess: 10–50 Hz is within ±3 dB of MIC 1/5. No broadband floor rise.

## Verdict per input

- **MIC 1** — reference-like. Floor matches MIC 5 within ±1.5 dB in every octave; only a weak trace of the group's HF component (+8 dB at 19.7 kHz).
- **MIC 2** — floor normal below 10 kHz; total dominated by a drifting 16.7–19.9 kHz narrowband component (+18 dB in band). Not the input pair's floor.
- **MIC 3** — same component, +21 dB at 18.2 kHz; floor normal below 10 kHz.
- **MIC 4** — same component, +22 dB at 17.8 kHz (16.0–18.1k in the A/B); floor normal below 10 kHz.
- **MIC 5** — reference; its own small 19 kHz bump is common to every channel.

## What it points at

A narrowband component whose frequency drifts by kilohertz over minutes and is shared across the group at one instant is not an input transistor, a bias network or a wrong resistor (those give a fixed, broadband or 1/f rise). It is not fixed-frequency PWM (LEDs, backlight), which cannot drift. The candidate on the board is **the MIC 1–4 group's ±15 V converter** (L5 / Q542 / U59, mx26 d24-converter-review.md). It is hysteretic and clock-gated: PSU_12_CLK at 1 MHz is gated by the section comparator through AND gate U58 into driver U59, so the BURST RATE is set by load and ripple, sits in the audio band, and drifts as things warm. **This is the group reworked in rev C (gate-drive cap + IRFR220 replaced).** MIC 1's much weaker pickup would then be layout (distance or decoupling from the switcher). This is inference from the spectrum, not a measurement of the rail.

The open-input reading makes a component like this look larger than a 150 ohm reading would, so how big a share of today's terminated MIC 2–4 excess it is (node −78 dBFS against −87..−94 on the good inputs) is not established here. The terminated spectra, or an EIN reading with this band excluded, would settle it.

## For PW (scope, about 5 minutes; no unit-side probe point exists)

1. Scope the MIC 1–4 group +15 V and −15 V rails (output of L5/Q542) AC-coupled with the rails up: look for a burst envelope at 16–20 kHz that slides downward over the first minutes. Compare with the MIC 5–8 group (L3/Q200) at the same moment.
2. If the burst is there: a few µF more output capacitance or an LC post-filter on the MIC 1–4 group rail is the quick A/B (the hump should drop or move).
3. The unit was left as found: rails down, chain safe, 219 processing cells restored and read back, sends shut, matrix-app not started.
