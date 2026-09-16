provenance: AI-drafted 2026-09-16 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Contract proposal S60 — `SweepOn` / `SweepStep` now drive the log chirp (descriptions only)

**Status: PROPOSED, not landed.** No cell is added, no address moves, no range
changes. The firmware already implements the meaning below (S60,
`tools/dsp/dsp_codegen.py::gen_test_osc`); only the master's description text
lags it. Evidence: `findings.md` S60-1.

## 1. What changes

| cell | SPI addr | hex | master description today | proposed description | range (unchanged) |
|---|---|---|---|---|---|
| `Test[1-1]SweepOn[1-1]` | 4979 | `0x1373` | Start frequency sweep | Periodic log sine sweep (chirp) 20 Hz–20 kHz on OscChan at OscLevel; needs OscOn | 2 (0 = tone, 1 = chirp) |
| `Test[1-1]SweepStep[1-1]` | 4980 | `0x1374` | Sweep step count | Chirp period in units of 1,024 samples; 0 = 16 (16,384 samples = one capture) | 255 |

## 2. Why the meaning moved

The S49 sweep stepped `OscFreq` through its 128-code law once per TEST_MEAS
window (85 ms). S49 recorded that the link cannot follow it: a voted read
takes about 350 ms, so every tool since has driven frequencies one point at a
time and left `SweepOn` at 0. Nothing on the host used the stepped sweep, and
the two words are exactly what the chirp needs: an on/off and a length.

## 3. How the chirp behaves (the firmware contract the description names)

- **Waveform:** `sin(2π·p)`, phase `p` in cycles, per-sample increment `w`
  starting at 20/48000 and multiplied by `r = 1000^(1/L)` every sample, so
  the instantaneous frequency is exponential from 20 Hz to 20 kHz over the
  period `L`. `OscLevel` is the peak amplitude (linear, 1.0 = 0 dBFS) and
  `OscFreq` is ignored while `SweepOn = 1`.
- **Periodic:** at every period boundary the phase and increment reset, so
  every period is the same samples. Measured on the part: two 16,384-sample
  captures 13 s apart are identical in all 16,384 words.
- **Capture alignment:** with the chirp running, `CaptureArm` starts a run
  only on the pass that injects a period's first block. Capture sample 0 is
  sweep sample 0, so the deconvolved impulse sits at the path latency.
- **Reference:** TEST_MEAS's fit reference is zeroed during a chirp.
  `RmsResult` reads the chirp RMS, and ThdResult/NoiseResult have no tone
  to fit.
- **Cost:** +732 to +791 cycles per chip-1 pass compared with the tone
  (0.24 % of 327,680). No overruns. TEST_NODES builds only.

## 4. Suggested master rows (description text is the hub's call)

```
Test[1-1]SweepOn[1-1],1,,,true,false,Periodic log sweep (chirp) 20Hz-20kHz on OscChan,,,2,...,-
Test[1-1]SweepStep[1-1],1,,,true,false,Chirp period x1024 samples (0=16),,,255,...,-
```
