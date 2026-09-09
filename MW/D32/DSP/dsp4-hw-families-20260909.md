| family | cells | chip / node | landed addrs answering | numeric | audio | verdict | reference model |
|---|---:|---|---:|---|---|---|---|
| `ANTI_FB` | 160 | chip 2 C2_AUX_AFB_01 | 20/20 | - | LIVE | **PASS** | bq_float_ref (float cascade, bit-exact) |
| `AUX_INPUT` | 8 | chip 2 C2_BT_IN | 2/2 | - | NO_STIMULUS_PATH | **NOT EXERCISED** | none declared |
| `COMPRESSOR` | 544 | chip 1 C1_COMP_01 | 17/17 | BIT_EXACT | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `CROSSOVER` | 8 | chip 2 C2_MAIN_XOVER | 8/8 | - | LIVE | **PASS** | bq_float_ref (float cascade, bit-exact) |
| `DCA` | 16 | chip 2 C2_DCA_01 | 2/2 | - | NO_PROBE | **NOT EXERCISED** | none declared |
| `DELAY` | 34 | chip 1 C1_DLY_01 | 1/1 | - | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `EQ_BIQUAD` | 616 | chip 1 C1_EQ_01 | 14/14 | NOT_APPLICABLE | LIVE | **PASS** | bq_float_ref (float cascade, bit-exact) |
| `FADER_PAN` | 118 | chip 1 C1_FDR_01 | 3/3 | BIT_EXACT | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `FX_ENGINE` | 114 | chip 2 C2_FX_ENG_01 | 16/16 | - | LIVE | **PASS** | none declared |
| `GAIN` | 96 | chip 1 C1_GAIN_01 | 2/2 | - | LIVE | **PASS** | bq_float_ref arm — the GAIN audio word is float under DSP4_GAIN_FLOAT; its METER stays fixed |
| `GATE` | 336 | chip 1 C1_GATE_01 | 12/12 | BIT_EXACT | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `GEQ` | 403 | chip 2 C2_AUX_GEQ_01 | 31/31 | - | LIVE | **PASS** | bq_float_ref (float cascade, bit-exact) |
| `HPF_LPF` | 72 | chip 1 C1_FILT_01 | 3/3 | NOT_APPLICABLE | LIVE | **PASS** | bq_float_ref (float cascade, bit-exact) |
| `LIMITER` | 48 | chip 2 C2_AUX_LIM_01 | 4/4 | - | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `METER` | 94 | chip 1 C1_MTR_01 | 0/0 | - | NO_PROBE | **NOT EXERCISED** | fixed_ref (fixed arm, bit-exact) |
| `MONITOR` | 3 | chip 2 C2_MON | 3/3 | - | LIVE | **PASS** | none declared |
| `NOISE_GEN` | 3 | chip 1 C1_NOISE | 3/3 | - | LIVE | **PASS** | none declared |
| `ROUTING` | 1008 | chip 1 C1_RTG_01 | 42/42 | - | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |
| `TALKBACK` | 8 | chip 1 C1_TALK_01 | 4/4 | - | LIVE | **PASS** | none declared |
| `TUBE_SAT` | 48 | chip 1 C1_TUBE_01 | 2/2 | BIT_EXACT | LIVE | **PASS** | fixed_ref (fixed arm, bit-exact) |

**Coverage.** Of the **20** D24 cell families `dsp.csv` addresses (3737 cells), **17 families PASSED on hardware (85 %)**, covering **3619 of 3737 addressed cells (97 %)**. **4 families passed on the strict bar** — the part's own samples reproduced word for word by the reference model — covering 1046 cells (28 %). 0 families FAILED.

| family | why |
|---|---|
| `ANTI_FB` | audio — moves 64 of 64 captured words over a floor of 0 |
| `AUX_INPUT` | contract — 2/2 landed addresses answer; no stimulus path on this bench |
| `COMPRESSOR` | numeric — bit-exact on 1 stimuli |
| `CROSSOVER` | audio — moves 64 of 64 captured words over a floor of 0 |
| `DCA` | contract — 2/2 landed addresses answer; no audio probe exists |
| `DELAY` | audio — moves 64 of 64 captured words over a floor of 64 |
| `EQ_BIQUAD` | audio — moves 64 of 64 captured words over a floor of 0 |
| `FADER_PAN` | numeric — bit-exact on 2 stimuli |
| `FX_ENGINE` | audio — moves 2 of 64 captured words over a floor of 0 |
| `GAIN` | audio — moves 64 of 64 captured words over a floor of 0 |
| `GATE` | numeric — bit-exact on 1 stimuli |
| `GEQ` | audio — moves 64 of 64 captured words over a floor of 0 |
| `HPF_LPF` | audio — moves 64 of 64 captured words over a floor of 0 |
| `LIMITER` | audio — moves 64 of 64 captured words over a floor of 0 |
| `METER` | meter — the peak-hold readback carries state from the probe before it — mtrverify.sh is this family's bar |
| `MONITOR` | audio — moves 64 of 64 captured words over a floor of 0 |
| `NOISE_GEN` | audio — moves 64 of 64 captured words over a floor of 0 |
| `ROUTING` | audio — moves 64 of 64 captured words over a floor of 64 |
| `TALKBACK` | audio — moves 64 of 64 captured words over a floor of 0 |
| `TUBE_SAT` | numeric — bit-exact on 2 stimuli |
