## MW-D24-2 — factory mode

| path | panel | verdict | T1 | T2 | T3 | T4 | T4b | T5 | T6 | T7 | T8 | A1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d24-in-mic05 | MIC 5 | PASS | pass | pass | pass |  | pass | pass |  | pass | pass |  |
| d24-in-mic06 | MIC 6 | INCOMPLETE | pass | pass | · |  | pass | pass |  | · | pass |  |
| d24-in-mic07 | MIC 7 | FLAG | **FLAG** | pass | · |  | pass | pass |  | · | pass |  |
| d24-in-mic08 | MIC 8 | FLAG | pass | pass | · |  | **FLAG** | pass |  | · | pass |  |
| d24-in-mic09 | MIC 9 | INCOMPLETE | pass | pass | · |  | pass | pass |  | · | pass |  |
| d24-in-mic10 | MIC 10 | INCOMPLETE | pass | pass | · |  | pass | pass |  | · | pass |  |
| d24-in-mic11 | MIC 11 | INCOMPLETE | pass | pass | · |  | pass | pass |  | · | pass |  |
| d24-in-mic12 | MIC 12 | INCOMPLETE | pass | pass | · |  | pass | pass |  | · | pass |  |
| d24-in-mic17 | MIC 17 | INCOMPLETE | pass | pass | · |  | pass | pass |  | · | pass |  |
| d24-in-mic18 | MIC 18 | INCOMPLETE | pass | pass | · |  | pass | pass |  | · | pass |  |
| d24-in-mic19 | MIC 19 | INCOMPLETE | pass | pass | · |  | pass | pass |  | · | pass |  |
| d24-in-mic20 | MIC 20 | FLAG | pass | pass | · |  | **FLAG** | pass |  | · | pass |  |
| d24-in-mic21 | MIC 21 | INCOMPLETE | pass | pass | · |  | pass | pass |  | · | pass |  |
| d24-in-mic22 | MIC 22 | INCOMPLETE | pass | pass | · |  | pass | pass |  | · | pass |  |
| d24-in-mic23 | MIC 23 | INCOMPLETE | pass | pass | · |  | pass | pass |  | · | pass |  |
| d24-in-mic24 | MIC 24 | INCOMPLETE | pass | pass | · |  | pass | pass |  | · | pass |  |
| d24-node-cue-rta | cue | PASS | pass | pass |  |  |  |  |  |  |  |  |
| d24-out-aux01 | Aux Out A1 | INCOMPLETE | · | · | · | pass |  | · |  | · | · |  |

### Detail

**d24-in-mic05 (MIC 5) — PASS.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic05.json (MIC 5 / J25: S61 chirps + tones, S63 THD avg + spans, S57 150 ohm, S60 T7, S54/S55 law).
- T1 PASS: code 0 +5.578 dB, code 63 +58.743 dB (range 53.16 dB); code 63 vs stage sum -0.068 dB; worst stage vs universal +0.026 dB (code 32)
- T2 PASS: code 0: 20 Hz -0.42, 20 kHz -0.12; code 63: 20 Hz -2.07, 20 kHz -0.20
- T3 PASS: THD+N code 0 -88.96 dB = 0.0036 %; THD code 63 -64.33 dB = 0.0608 % (coherent average), single capture -60.98 dB = 0.0893 %
- T4b PASS: EIN -127.2 dBu 20-20k / -130.5 dBu(A) (DC-24k -124.6; 20 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 PASS: worst neighbour strip 17 -133.06 dB of 22, detector floor -144.18 dB
- T8 PASS: 91.398 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic06 (MIC 6) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic06.json (MIC 6 / J27: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.580 dB, code 63 +58.668 dB (range 53.09 dB); code 63 vs stage sum -0.097 dB; worst stage vs universal -0.047 dB (code 32)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.08, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -88.43 dB = 0.0038 %; THD-only at code 63 not measured (THD+N -43.48 dB = 0.6698 %, noise-limited)
- T4b PASS: EIN -126.5 dBu 20-20k / -130.2 dBu(A) (DC-24k -122.0; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.399 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic07 (MIC 7) — FLAG.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic07.json (MIC 7 / J29: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 FLAG: code 0 +5.577 dB, code 63 +58.600 dB (range 53.02 dB); code 63 vs stage sum -0.098 dB; worst stage vs universal -0.849 dB (code 8)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.11, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -87.76 dB = 0.0041 %; THD-only at code 63 not measured (THD+N -43.48 dB = 0.6699 %, noise-limited)
- T4b PASS: EIN -127.2 dBu 20-20k / -130.4 dBu(A) (DC-24k -124.2; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.407 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic08 (MIC 8) — FLAG.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic08.json (MIC 8 / J31: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.574 dB, code 63 +58.674 dB (range 53.10 dB); code 63 vs stage sum -0.100 dB; worst stage vs universal -0.022 dB (code 16)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.07, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -88.39 dB = 0.0038 %; THD-only at code 63 not measured (THD+N -43.67 dB = 0.6550 %, noise-limited)
- T4b FLAG: EIN -123.2 dBu 20-20k / -128.7 dBu(A) (DC-24k -119.5; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.407 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic09 (MIC 9) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic09.json (MIC 9 / J35: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.553 dB, code 63 +58.607 dB (range 53.05 dB); code 63 vs stage sum -0.100 dB; worst stage vs universal -0.084 dB (code 32)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.06, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -88.80 dB = 0.0036 %; THD-only at code 63 not measured (THD+N -43.19 dB = 0.6924 %, noise-limited)
- T4b PASS: EIN -127.8 dBu 20-20k / -130.6 dBu(A) (DC-24k -125.3; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.399 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic10 (MIC 10) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic10.json (MIC 10 / J37: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.552 dB, code 63 +58.631 dB (range 53.08 dB); code 63 vs stage sum -0.102 dB; worst stage vs universal -0.045 dB (code 16)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.13, 20 kHz -0.11
- T3 NO DATA: THD+N code 0 -87.04 dB = 0.0044 %; THD-only at code 63 not measured (THD+N -43.25 dB = 0.6879 %, noise-limited)
- T4b PASS: EIN -128.0 dBu 20-20k / -130.7 dBu(A) (DC-24k -126.1; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.399 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic11 (MIC 11) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic11.json (MIC 11 / J39: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.553 dB, code 63 +58.628 dB (range 53.08 dB); code 63 vs stage sum -0.105 dB; worst stage vs universal -0.055 dB (code 32)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.09, 20 kHz -0.11
- T3 NO DATA: THD+N code 0 -86.83 dB = 0.0046 %; THD-only at code 63 not measured (THD+N -43.31 dB = 0.6831 %, noise-limited)
- T4b PASS: EIN -127.7 dBu 20-20k / -130.6 dBu(A) (DC-24k -125.5; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.407 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic12 (MIC 12) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic12.json (MIC 12 / J41: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.552 dB, code 63 +58.660 dB (range 53.11 dB); code 63 vs stage sum -0.106 dB; worst stage vs universal -0.015 dB (code 8)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.16, 20 kHz -0.11
- T3 NO DATA: THD+N code 0 -88.61 dB = 0.0037 %; THD-only at code 63 not measured (THD+N -43.22 dB = 0.6903 %, noise-limited)
- T4b PASS: EIN -127.6 dBu 20-20k / -130.6 dBu(A) (DC-24k -125.6; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.407 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic17 (MIC 17) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic17.json (MIC 17 / J26: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.574 dB, code 63 +58.748 dB (range 53.17 dB); code 63 vs stage sum -0.101 dB; worst stage vs universal +0.087 dB (code 32)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.12, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -87.71 dB = 0.0041 %; THD-only at code 63 not measured (THD+N -44.32 dB = 0.6081 %, noise-limited)
- T4b PASS: EIN -128.7 dBu 20-20k / -130.9 dBu(A) (DC-24k -126.4; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.399 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic18 (MIC 18) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic18.json (MIC 18 / J28: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.575 dB, code 63 +58.690 dB (range 53.11 dB); code 63 vs stage sum -0.104 dB; worst stage vs universal +0.016 dB (code 16)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.13, 20 kHz -0.11
- T3 NO DATA: THD+N code 0 -87.61 dB = 0.0042 %; THD-only at code 63 not measured (THD+N -43.10 dB = 0.6998 %, noise-limited)
- T4b PASS: EIN -128.2 dBu 20-20k / -130.8 dBu(A) (DC-24k -126.0; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.399 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic19 (MIC 19) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic19.json (MIC 19 / J30: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.569 dB, code 63 +58.701 dB (range 53.13 dB); code 63 vs stage sum -0.099 dB; worst stage vs universal +0.031 dB (code 32)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.15, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -87.68 dB = 0.0041 %; THD-only at code 63 not measured (THD+N -43.98 dB = 0.6328 %, noise-limited)
- T4b PASS: EIN -128.2 dBu 20-20k / -130.9 dBu(A) (DC-24k -126.2; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.408 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic20 (MIC 20) — FLAG.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic20.json (MIC 20 / J32: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.579 dB, code 63 +58.686 dB (range 53.11 dB); code 63 vs stage sum -0.103 dB; worst stage vs universal +0.012 dB (code 16)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.13, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -88.49 dB = 0.0038 %; THD-only at code 63 not measured (THD+N -43.16 dB = 0.6951 %, noise-limited)
- T4b FLAG: EIN -125.2 dBu 20-20k / -129.8 dBu(A) (DC-24k -121.3; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.408 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic21 (MIC 21) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic21.json (MIC 21 / J36: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.551 dB, code 63 +58.687 dB (range 53.14 dB); code 63 vs stage sum -0.104 dB; worst stage vs universal +0.040 dB (code 32)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.13, 20 kHz -0.11
- T3 NO DATA: THD+N code 0 -87.73 dB = 0.0041 %; THD-only at code 63 not measured (THD+N -43.37 dB = 0.6787 %, noise-limited)
- T4b PASS: EIN -128.0 dBu 20-20k / -130.8 dBu(A) (DC-24k -125.8; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.399 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic22 (MIC 22) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic22.json (MIC 22 / J38: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.548 dB, code 63 +58.651 dB (range 53.10 dB); code 63 vs stage sum -0.104 dB; worst stage vs universal -0.018 dB (code 32)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.19, 20 kHz -0.11
- T3 NO DATA: THD+N code 0 -88.09 dB = 0.0039 %; THD-only at code 63 not measured (THD+N -44.40 dB = 0.6025 %, noise-limited)
- T4b PASS: EIN -128.2 dBu 20-20k / -130.9 dBu(A) (DC-24k -126.1; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.400 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic23 (MIC 23) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic23.json (MIC 23 / J40: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.544 dB, code 63 +58.681 dB (range 53.14 dB); code 63 vs stage sum -0.106 dB; worst stage vs universal +0.041 dB (code 32)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.13, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -88.47 dB = 0.0038 %; THD-only at code 63 not measured (THD+N -44.41 dB = 0.6022 %, noise-limited)
- T4b PASS: EIN -128.0 dBu 20-20k / -130.8 dBu(A) (DC-24k -125.6; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.407 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-in-mic24 (MIC 24) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic24.json (MIC 24 / J42: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.550 dB, code 63 +58.669 dB (range 53.12 dB); code 63 vs stage sum -0.107 dB; worst stage vs universal +0.020 dB (code 16)
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.14, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -86.74 dB = 0.0046 %; THD-only at code 63 not measured (THD+N -43.50 dB = 0.6686 %, noise-limited)
- T4b PASS: EIN -127.6 dBu 20-20k / -130.7 dBu(A) (DC-24k -125.3; 6 captures, source 150 ohm across pins 2-3 (loop cable off))
- T5 PASS: inverted (loop expects inverted)
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.407 samples = 1.904 ms (loop nominal 91.40 +- 0.50)

**d24-node-cue-rta (cue) — PASS.** Source: replay MW/D24/DSP/s66/replay/d24-node-cue-rta.json (cue bus + RTA: S65 proof rows through the parameter link).
- T1 PASS: 7 rows; worst level -0.072 dB re expected
- T2 PASS: octave neighbours >= 40.74 dB down; cold side <= -162.3 dBFS; mono cases equal on both sides

**d24-out-aux01 (Aux Out A1) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-out-aux01.json (AUX 1 / J45 output noise: S57, looped into MIC 5 at code 0).
- T1 NO DATA: output/node T1 not in the recorded sets
- T2 NO DATA: output/node response not in the recorded sets
- T3 NO DATA: output THD+N not in the recorded sets
- T4 PASS: -84.55 dBu 20-20k, -86.96 dBu(A), -83.78 dBu DC-24k (20 captures; floor-corrected -85.18 / -88.13)
- T5 NO DATA: no chirp or phase fit
- T7 NO DATA: no output crosstalk measurement exists
- T8 NO DATA: no chirp or phase fit

## MW-D24-2 — full mode

| path | panel | verdict | T1 | T2 | T3 | T4 | T4b | T5 | T6 | T7 | T8 | A1 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| d24-in-mic05 | MIC 5 | FLAG | pass | pass | pass | · | pass | pass | · | pass | pass | **FLAG** |
| d24-in-mic06 | MIC 6 | INCOMPLETE | pass | pass | · | · | pass | pass | · | · | pass | · |
| d24-in-mic07 | MIC 7 | FLAG | **FLAG** | pass | · | · | pass | pass | · | · | pass | · |
| d24-in-mic08 | MIC 8 | FLAG | pass | pass | · | · | **FLAG** | pass | · | · | pass | · |
| d24-in-mic09 | MIC 9 | INCOMPLETE | pass | pass | · | · | pass | pass | · | · | pass | · |
| d24-in-mic10 | MIC 10 | INCOMPLETE | pass | pass | · | · | pass | pass | · | · | pass | · |
| d24-in-mic11 | MIC 11 | INCOMPLETE | pass | pass | · | · | pass | pass | · | · | pass | · |
| d24-in-mic12 | MIC 12 | INCOMPLETE | pass | pass | · | · | pass | pass | · | · | pass | · |
| d24-in-mic17 | MIC 17 | INCOMPLETE | pass | pass | · | · | pass | pass | · | · | pass | · |
| d24-in-mic18 | MIC 18 | INCOMPLETE | pass | pass | · | · | pass | pass | · | · | pass | · |
| d24-in-mic19 | MIC 19 | INCOMPLETE | pass | pass | · | · | pass | pass | · | · | pass | · |
| d24-in-mic20 | MIC 20 | FLAG | pass | pass | · | · | **FLAG** | pass | · | · | pass | · |
| d24-in-mic21 | MIC 21 | INCOMPLETE | pass | pass | · | · | pass | pass | · | · | pass | · |
| d24-in-mic22 | MIC 22 | INCOMPLETE | pass | pass | · | · | pass | pass | · | · | pass | · |
| d24-in-mic23 | MIC 23 | INCOMPLETE | pass | pass | · | · | pass | pass | · | · | pass | · |
| d24-in-mic24 | MIC 24 | INCOMPLETE | pass | pass | · | · | pass | pass | · | · | pass | · |
| d24-node-cue-rta | cue | PASS | pass | pass |  |  |  |  |  |  |  |  |
| d24-out-aux01 | Aux Out A1 | INCOMPLETE | · | · | · | pass |  | · | · | · | · |  |

### Detail

**d24-in-mic05 (MIC 5) — FLAG.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic05.json (MIC 5 / J25: S61 chirps + tones, S63 THD avg + spans, S57 150 ohm, S60 T7, S54/S55 law).
- T1 PASS: code 0 +5.578 dB, code 63 +58.717 dB (range 53.14 dB); code 63 vs stage sum -0.101 dB; worst stage vs universal +0.042 dB (code 33); monotonic yes
- T2 PASS: code 0: 20 Hz -0.42, 20 kHz -0.12; code 63: 20 Hz -2.07, 20 kHz -0.20
- T3 PASS: THD+N code 0 -88.96 dB = 0.0036 %; THD code 63 -64.33 dB = 0.0608 % (coherent average), single capture -60.98 dB = 0.0893 %
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b PASS: EIN -127.2 dBu 20-20k / -130.5 dBu(A) (DC-24k -124.6; 20 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -95.1 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists: S54's T6 toggled the 595 bit 0, which is the PHANTOM SHUNT (PW 09-16), not a mute
- T7 PASS: worst neighbour strip 17 -133.06 dB of 22, detector floor -144.18 dB
- T8 PASS: 91.398 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 FLAG: silent: 70 transitions, 68 PASS / 2 FLAG; worst detected -74.0 dBFS hw_up 0->1; flagged: hw_up 0->1 (pump), bit 0->1 (pump)

**d24-in-mic06 (MIC 6) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic06.json (MIC 6 / J27: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.580 dB, code 63 +58.668 dB (range 53.09 dB); code 63 vs stage sum -0.097 dB; worst stage vs universal -0.047 dB (code 32); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.08, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -88.43 dB = 0.0038 %; THD-only at code 63 not measured (THD+N -43.48 dB = 0.6698 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b PASS: EIN -126.5 dBu 20-20k / -130.2 dBu(A) (DC-24k -122.0; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -94.6 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.399 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-in-mic07 (MIC 7) — FLAG.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic07.json (MIC 7 / J29: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 FLAG: code 0 +5.577 dB, code 63 +58.600 dB (range 53.02 dB); code 63 vs stage sum -0.098 dB; worst stage vs universal -0.849 dB (code 8); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.11, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -87.76 dB = 0.0041 %; THD-only at code 63 not measured (THD+N -43.48 dB = 0.6699 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b PASS: EIN -127.2 dBu 20-20k / -130.4 dBu(A) (DC-24k -124.2; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -95.0 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.407 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-in-mic08 (MIC 8) — FLAG.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic08.json (MIC 8 / J31: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.574 dB, code 63 +58.674 dB (range 53.10 dB); code 63 vs stage sum -0.100 dB; worst stage vs universal -0.023 dB (code 17); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.07, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -88.39 dB = 0.0038 %; THD-only at code 63 not measured (THD+N -43.67 dB = 0.6550 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b FLAG: EIN -123.2 dBu 20-20k / -128.7 dBu(A) (DC-24k -119.5; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -94.6 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.407 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-in-mic09 (MIC 9) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic09.json (MIC 9 / J35: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.553 dB, code 63 +58.607 dB (range 53.05 dB); code 63 vs stage sum -0.100 dB; worst stage vs universal -0.085 dB (code 33); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.06, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -88.80 dB = 0.0036 %; THD-only at code 63 not measured (THD+N -43.19 dB = 0.6924 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b PASS: EIN -127.8 dBu 20-20k / -130.6 dBu(A) (DC-24k -125.3; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -94.8 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.399 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-in-mic10 (MIC 10) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic10.json (MIC 10 / J37: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.552 dB, code 63 +58.631 dB (range 53.08 dB); code 63 vs stage sum -0.102 dB; worst stage vs universal -0.045 dB (code 16); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.13, 20 kHz -0.11
- T3 NO DATA: THD+N code 0 -87.04 dB = 0.0044 %; THD-only at code 63 not measured (THD+N -43.25 dB = 0.6879 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b PASS: EIN -128.0 dBu 20-20k / -130.7 dBu(A) (DC-24k -126.1; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -94.5 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.399 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-in-mic11 (MIC 11) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic11.json (MIC 11 / J39: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.553 dB, code 63 +58.628 dB (range 53.08 dB); code 63 vs stage sum -0.105 dB; worst stage vs universal -0.055 dB (code 32); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.09, 20 kHz -0.11
- T3 NO DATA: THD+N code 0 -86.83 dB = 0.0046 %; THD-only at code 63 not measured (THD+N -43.31 dB = 0.6831 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b PASS: EIN -127.7 dBu 20-20k / -130.6 dBu(A) (DC-24k -125.5; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -94.4 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.407 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-in-mic12 (MIC 12) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic12.json (MIC 12 / J41: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.552 dB, code 63 +58.660 dB (range 53.11 dB); code 63 vs stage sum -0.106 dB; worst stage vs universal -0.015 dB (code 8); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.16, 20 kHz -0.11
- T3 NO DATA: THD+N code 0 -88.61 dB = 0.0037 %; THD-only at code 63 not measured (THD+N -43.22 dB = 0.6903 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b PASS: EIN -127.6 dBu 20-20k / -130.6 dBu(A) (DC-24k -125.6; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -94.8 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.407 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-in-mic17 (MIC 17) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic17.json (MIC 17 / J26: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.574 dB, code 63 +58.748 dB (range 53.17 dB); code 63 vs stage sum -0.101 dB; worst stage vs universal +0.087 dB (code 32); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.12, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -87.71 dB = 0.0041 %; THD-only at code 63 not measured (THD+N -44.32 dB = 0.6081 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b PASS: EIN -128.7 dBu 20-20k / -130.9 dBu(A) (DC-24k -126.4; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -94.7 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.399 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-in-mic18 (MIC 18) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic18.json (MIC 18 / J28: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.575 dB, code 63 +58.690 dB (range 53.11 dB); code 63 vs stage sum -0.104 dB; worst stage vs universal +0.016 dB (code 16); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.13, 20 kHz -0.11
- T3 NO DATA: THD+N code 0 -87.61 dB = 0.0042 %; THD-only at code 63 not measured (THD+N -43.10 dB = 0.6998 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b PASS: EIN -128.2 dBu 20-20k / -130.8 dBu(A) (DC-24k -126.0; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -95.2 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.399 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-in-mic19 (MIC 19) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic19.json (MIC 19 / J30: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.569 dB, code 63 +58.701 dB (range 53.13 dB); code 63 vs stage sum -0.099 dB; worst stage vs universal +0.031 dB (code 32); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.15, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -87.68 dB = 0.0041 %; THD-only at code 63 not measured (THD+N -43.98 dB = 0.6328 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b PASS: EIN -128.2 dBu 20-20k / -130.9 dBu(A) (DC-24k -126.2; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -94.9 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.408 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-in-mic20 (MIC 20) — FLAG.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic20.json (MIC 20 / J32: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.579 dB, code 63 +58.686 dB (range 53.11 dB); code 63 vs stage sum -0.103 dB; worst stage vs universal +0.012 dB (code 16); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.13, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -88.49 dB = 0.0038 %; THD-only at code 63 not measured (THD+N -43.16 dB = 0.6951 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b FLAG: EIN -125.2 dBu 20-20k / -129.8 dBu(A) (DC-24k -121.3; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -94.5 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.408 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-in-mic21 (MIC 21) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic21.json (MIC 21 / J36: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.551 dB, code 63 +58.687 dB (range 53.14 dB); code 63 vs stage sum -0.104 dB; worst stage vs universal +0.040 dB (code 32); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.13, 20 kHz -0.11
- T3 NO DATA: THD+N code 0 -87.73 dB = 0.0041 %; THD-only at code 63 not measured (THD+N -43.37 dB = 0.6787 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b PASS: EIN -128.0 dBu 20-20k / -130.8 dBu(A) (DC-24k -125.8; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -94.9 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.399 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-in-mic22 (MIC 22) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic22.json (MIC 22 / J38: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.548 dB, code 63 +58.651 dB (range 53.10 dB); code 63 vs stage sum -0.104 dB; worst stage vs universal -0.020 dB (code 33); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.19, 20 kHz -0.11
- T3 NO DATA: THD+N code 0 -88.09 dB = 0.0039 %; THD-only at code 63 not measured (THD+N -44.40 dB = 0.6025 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b PASS: EIN -128.2 dBu 20-20k / -130.9 dBu(A) (DC-24k -126.1; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -95.0 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.400 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-in-mic23 (MIC 23) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic23.json (MIC 23 / J40: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.544 dB, code 63 +58.681 dB (range 53.14 dB); code 63 vs stage sum -0.106 dB; worst stage vs universal +0.042 dB (code 33); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.13, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -88.47 dB = 0.0038 %; THD-only at code 63 not measured (THD+N -44.41 dB = 0.6022 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b PASS: EIN -128.0 dBu 20-20k / -130.8 dBu(A) (DC-24k -125.6; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -94.8 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.407 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-in-mic24 (MIC 24) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-in-mic24.json (MIC 24 / J42: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)).
- T1 PASS: code 0 +5.550 dB, code 63 +58.669 dB (range 53.12 dB); code 63 vs stage sum -0.107 dB; worst stage vs universal +0.020 dB (code 16); monotonic yes
- T2 PASS: code 0: 20 Hz -0.41, 20 kHz -0.12; code 63: 20 Hz -2.14, 20 kHz -0.12
- T3 NO DATA: THD+N code 0 -86.74 dB = 0.0046 %; THD-only at code 63 not measured (THD+N -43.50 dB = 0.6686 %, noise-limited)
- T4 NO DATA: no tone-off floors at the T1 codes
- T4b PASS: EIN -127.6 dBu 20-20k / -130.7 dBu(A) (DC-24k -125.3; 6 captures, source 150 ohm across pins 2-3 (loop cable off)); code 0 -95.0 dBu 20-20k (converter floor)
- T5 PASS: inverted (loop expects inverted)
- T6 NO DATA: no DSP strip-mute measurement exists
- T7 NO DATA: S55 did not measure crosstalk (S60 did, on MIC 5 only)
- T8 PASS: 91.407 samples = 1.904 ms (loop nominal 91.40 +- 0.50)
- A1 NO DATA: S63 ran MIC 5 only; the WATCH path for the other channels was not exercised

**d24-node-cue-rta (cue) — PASS.** Source: replay MW/D24/DSP/s66/replay/d24-node-cue-rta.json (cue bus + RTA: S65 proof rows through the parameter link).
- T1 PASS: 7 rows; worst level -0.072 dB re expected
- T2 PASS: octave neighbours >= 40.74 dB down; cold side <= -162.3 dBFS; mono cases equal on both sides

**d24-out-aux01 (Aux Out A1) — INCOMPLETE.** Source: replay MW/D24/DSP/s66/replay/d24-out-aux01.json (AUX 1 / J45 output noise: S57, looped into MIC 5 at code 0).
- T1 NO DATA: output/node T1 not in the recorded sets
- T2 NO DATA: output/node response not in the recorded sets
- T3 NO DATA: output THD+N not in the recorded sets
- T4 PASS: -84.55 dBu 20-20k, -86.96 dBu(A), -83.78 dBu DC-24k (20 captures; floor-corrected -85.18 / -88.13)
- T5 NO DATA: no chirp or phase fit
- T6 NO DATA: no output mute measurement exists
- T7 NO DATA: no output crosstalk measurement exists
- T8 NO DATA: no chirp or phase fit

