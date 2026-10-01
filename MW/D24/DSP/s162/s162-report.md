provenance: AI-drafted 2026-10-01 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S162 — Q542 Schottky A/B: open-input FFT + cold drift map vs S160 (MW-D24-2, 2026-10-01)

PW fitted an SS210A at Q542 on analog board 2 (cathode to the gate after the 10 nF, anode to GND; the 10 nF + 4K7 AC-coupled drive stays) as a DC restore for the MIC 1–4 group ±15 V converter. This run repeats S160 on the same unit with the same instrument.

**These are open-input figures. They are not EIN.** Nothing here is graded against limits.csv (`t4b_ein_max_dbu` −126.0, `t4b_ein_a_max_dbu` −129.5). The graded EIN comes from PW's failed-only re-run with the 150 ohm plug.

## Verdict

**The hump has moved out of the audio band. It has not gone away.** With the Schottky fitted, MIC 2/3/4 match MIC 5 within 0.7 dB in 20 Hz–20 kHz (input-referred, open, code 63), and the 16.6–18.9 kHz hump is gone. The same group component now sits at the top of the converter's band, at **22.2 kHz at rails-up, rising to about 23.6–23.9 kHz and steady from about 5 min**. It is about as strong as before (lane −73.3 dBFS in 22–24 kHz on MIC 2, against about −74.8 dBFS for the S160 in-band hump), and that is as measured through the ADC filter's roll-off. It no longer drifts once warm: the peak holds 23.58–23.70 kHz from 5 to 15 min.

| input (code 63, open) | 20–20k dBu in.-ref. S160 → S162 | A dBu S160 → S162 | 10–20k octave over MIC 5, S160 → S162 | 22–24 kHz lane dBFS S160 → S162 | node RMS (DC–24k) dBFS S160 → S162 |
|---|---:|---:|---:|---:|---:|
| MIC 1 | −112.8 → −114.2 | −116.0 → −116.5 | +1.0 → +0.7 | −92.6 → −85.5 | −75.09 → −75.12 |
| MIC 2 | −106.4 → **−114.7** | −113.3 → −117.1 | **+9.0 → +0.3** | −91.8 → **−73.3** | −73.44 → −72.24 |
| MIC 3 | −107.2 → **−114.8** | −113.6 → −117.2 | **+8.1 → +0.2** | −92.2 → **−74.2** | −74.26 → −73.01 |
| MIC 4 | −106.8 → **−114.2** | −113.0 → −116.6 | **+8.5 → +0.8** | −91.2 → **−72.3** | −72.64 → −70.78 |
| MIC 5 | −113.7 → −114.9 | −116.7 → −117.1 | (ref) | −92.7 → −85.4 | −77.25 → −77.34 |

Per input, one line:

- **MIC 1**: still reference-like in band. S160's weak 19.7 kHz trace is gone, and a weak line now sits near 23.65 kHz (22–24 kHz up 7 dB).
- **MIC 2**: the 18.9 kHz hump (+18 dB) has **moved** to 23.6–23.9 kHz (+23 dB peak over MIC 5). 20–20k is down 8.3 dB, to MIC 5's level.
- **MIC 3**: the 18.2 kHz hump has **moved** to about 23.6 kHz (+21.5 dB). 20–20k is down 7.6 dB, to MIC 5's level.
- **MIC 4**: the 17.8 kHz hump has **moved** to about 23.6 kHz (+23.8 dB). 20–20k is down 7.4 dB, to MIC 5's level.
- **MIC 5**: S160's small 19.2 kHz bump is **gone**, and a small line now appears near 23.9 kHz (22–24 kHz up 7 dB). S160 called that bump a separate, common, converter-side feature. It was this component coupling across.

Plots: `s162-before-after-12-24k.png` (linear zoom, the clearest view), `s162-before-after-mic1-4.png`, `s162-excess-vs-mic5-before-after.png`, `s162-drift-map.png`, plus the S160-format `s162-mic1-5-open-c63.png`, `s162-mic2-by-code.png`, `s162-excess-vs-mic5.png`.

## Drift map (cold rails-up)

Rails down for 336 s before the run (unit power-cycled by PW for the fit, pair booted with the rails down). Rails up at 16:40:42Z. MIC 2 open at code 63, 2 × 16k captures every 30 s for 15 min, and MIC 4 at 0/5/10/15 min. Zero overruns on all 70 captures.

| t since rails-up | MIC 2 peak (14–23.9 kHz) | peak over MIC 5 | 20–24 kHz over MIC 5 | 10–20 kHz over MIC 5 |
|---|---:|---:|---:|---:|
| 0.6 s | 22.19 kHz | +11.5 dB | +0.8 dB | +0.5 dB |
| 30 s | 22.71 kHz | +16.2 | +2.9 | +0.1 |
| 60 s | 23.23 kHz | +20.8 | +6.7 | −0.0 |
| 90 s | 23.66 kHz | +21.3 | +8.8 | +0.1 |
| 150–180 s | 23.90 kHz | +10.4 / +14.5 | +10.2 / +10.7 | +0.4 / +0.3 |
| 5 min | 23.74 kHz | +22.1 | +11.2 | +0.5 |
| 5–15 min | 23.58–23.70 kHz | +22.2 … +24.9 | +11.2 … +11.5 | +0.3 … +0.6 |

MIC 4 sat at the same frequency every time: 22.13 kHz at t+4 s, then 23.73/23.60/23.63 kHz at 5/10/15 min, +22.3 to +24.8 dB. That is still one source for the group, as in S160.

**The drift is no longer a slide down through the audio band.** S160's points (red on the drift plot) went 18.9 → 16.0 kHz in about one minute. The S160 records' own timestamps put the A/B at 12:37:29–12:38:28Z, so the S160 report's "about 2.5 min" was too long. In S162 the component rises by about 1.7 kHz over the first 2.5 min, turns at 23.9 kHz, and sits at 23.6–23.7 kHz from about 5 min to the end. The 10–20 kHz octave stays within 0.6 dB of MIC 5 at every point, cold or warm.

**These captures cannot tell whether the component crosses Nyquist.** It turns at 23.9 kHz, and the peak excess dips to +10 dB at the turn. The data fit a component that peaks at 23.9 kHz and relaxes to 23.65 kHz, and they fit equally well a component that keeps rising through 24 kHz to about 24.3–24.4 kHz and folds back (48 − 24.35 = 23.65). The AK4619 sharp roll-off ADC filter (datasheet 8.2 1-1, the register default; this unit's setting was not checked) is flat to 22.1 kHz, −3 dB at 23.7 kHz, and stops only from 27.8 kHz, so either way **the true level at the converter input is at least 3 dB above what is measured here**. A scope on the rail settles it.

## By gain code (MIC 2, 22–24 kHz)

Lane −79.5 / −75.4 / −73.3 dBFS at codes 32 / 48 / 63 (G 53.68 / 56.94 / 58.66 dB). Input-referred that is −107.1 / −106.2 / −105.8 dBu, so the component now **scales with the preamp gain**. It enters at or before the gain stage, and the input-referred number is meaningful for sizing. At code 0 the band also rose, from −126.7 to −120.4 dBFS.

## Not changed

- 100 Hz–10 kHz: every octave on MIC 1–4 is within ±1.7 dB of MIC 5, as in S160. Below 100 Hz MIC 5 reads 2–5 dB under the others on this run (open-input LF pickup; `s162_analyse.out`).
- No 60 Hz family. The 49.8 Hz open-input line is still there (+7 to +15 dB on MIC 1–4, +3 dB on MIC 5).
- Node RmsResult (DC–24 kHz) **did not improve** on MIC 2–4. It is 1–2 dB higher than in S160 and 5–6.5 dB above MIC 5, because the component is still inside DC–24k. Anything graded on the node's DC–24k RMS still sees MIC 2–4 as noisy. The S159 capture-arm EIN grade (20–20k and A) should not see the component on this board.

## For the hub: sizing the next step

- **The component to remove:** the MIC 1–4 group converter's burst rate, now at **≥ 22.2 kHz cold and 23.6–24.4 kHz warm**. Before the fix it was 16–20 kHz.
- **Its strength:** about −105 to −107 dBu input-referred in 22–24 kHz on MIC 2–4 at code 63, as measured, and at least 3 dB more at the input because of the ADC roll-off. Its peak bin is +23 to +25 dB over MIC 5. Its band power is about 18.5 dB over the same band before the fix, and about equal to the old in-band hump's power.
- **An LC post-filter or added output C on the MIC 1–4 ±15 V** needs about **25–30 dB at ≥ 22 kHz** to bring the line to MIC 5's floor on this board. To also cover a board without the Schottky, or a burst rate that wanders down again, it needs the same at 16 kHz. Two poles near 3 kHz give about 30 dB at 16 kHz and about 35 dB at 22 kHz. That is a starting point, not a design.
- The Schottky alone may be judged sufficient for audio-band EIN (20–20k and A), since the hump is out of band. It is not sufficient for anything that reads DC–24k or works near Nyquist.

## Method

- Booted pair `/home/app/loopthd/s154` (pair.conf). PW's power cycle had left the pair unbooted, so it was booted with `d24_selftest.py --local --ensure-pair` (the RUN ALL path, rails down; both chips MAGIC 0xD5B40001 BOOT_STAGE 7, chain SAFE verified 200/200). No runner.lock, no RUN ALL, matrix-app not running, d24-testui untouched.
- `tools/s162_audit.py` (on the unit in `/home/app/s162`; `/home/app/selftest` unchanged) is s160_audit.py with a drift phase. It refuses to start unless the rails have been down for ≥ 300 s. It reads, bypasses and restores the same 219 `_standing_bypass` cells (219/219 restored, 0 failed read-back), shuts the sends, and shunts the other 23 inputs at gain 0. The chain is set to MIC 2/63 before the rails rise, so the first capture is 0.6 s after rails-up. Phase 2 is the S160 set (6 × 16k per setting after the same node settle), run without dropping the rails at t+15–16 min. In S160 the inputs were at most a few minutes warm.
- Desk: `tools/s162_analyse.py` (s160_analyse.py, only the names changed) gives `s162_analyse.out`, and `tools/s162_compare.py` gives `s162_compare.out` and the plots. Same input-referred method (S57-R, units.csv 23.13 dBu, pass-4 G0 + mic-gain-codes). Raw data and the unit log are in `data/`.
- **Unit left as found:** rails down (GPIO26 lo), CS_M driven high, chain SAFE, processing restored, sends shut, nothing deployed. The one difference is that the DSP pair is now booted (it was down after the power cycle). That is harmless: RUN ALL's own ensure-pair finds it up and skips the boot.
