# Node-type portability map (SHARC kernel → FPGA strategy)

Per node type in `dsp.csv` / `tools/dsp/dsp_codegen.py`, the porting
strategy and confidence that FPGA behaviour matches the cell-level
semantics (not bit-exactness — see README). "TM" = time-multiplexed
shared engine walking per-instance state/coeff BRAM.

| Node type | Instances today | FPGA strategy | Confidence | Notes |
|---|---|---|---|---|
| INPUT_TDM / OUTPUT_TDM | 46 in / 20 out | TDM (de)serializers, slot-map SOT driven | High | Same slot map; or step up to network audio |
| INTERCHIP_SEND/RECV | 37+37 | Disappears | High | Single-chip fabric; the 128-bus limit vanishes |
| GAIN / FADER_PAN / DCA | ~90 | TM multiply engine + ramp | High | dB laws from cell tables, unchanged |
| MIX_BUS / ROUTING | 27 + 32 | TM MAC engine, schedule ROM from dsp.csv | High | FPGA's home turf; scales with clock, not code |
| EQ_BIQUAD / HPF_LPF / CROSSOVER / ANTI_FB | ~90 | TM biquad engine (TDF-II, 48-64b acc) | High | Identical coefficient sets; better LF noise than FP32 |
| GEQ (28-band) | 17 | Same biquad engine, more sections | High | coeffs_next crossfade-swap idea carries over |
| GATE / COMPRESSOR / LIMITER | ~150 | TM dynamics engine (envelope + gain computer) | High-Med | Envelope math ports directly; verify knee/log approximations against golden model |
| TUBE_SAT | 32 | Poly/LUT waveshaper | Med | Cheap either way; match the curve, not the bits |
| DELAY (ch/bus) + pool | ~50 | DDR-backed delay engine | High | Native DDR replaces the xSPI-PSRAM rev question |
| FX_ENGINE (reverb etc.) | 6 | REDESIGN or hybrid (DSP/ARM sidecar) | Low-Med | The one genuine port problem; decide strategy early |
| TALKBACK / NOISE_GEN / AUX_INPUT / MONITOR | ~20 | Small dedicated blocks | High | Trivial |
| METER | ~70 | Peak/decay in the TM engines, readback RAM | High | Same READ-flag protocol path |
| Ramp engine / profiles | global | Fabric block, same profile tables | High | Direct port of semantics |
| SPI param plane + product config | global | SPI slave + param RAM + generated decode | High | Wire-identical; Pi tooling unchanged |

Aggregate: everything except FX_ENGINE ports with high confidence as a
generated, time-multiplexed implementation of the same dsp.csv graph.
FX is the strategic decision; the rest is engineering volume.

Next concrete step when this activates: extend `dsp_simulate.py` into a
golden-vector harness (per node type: cell values in → expected
response out) so SHARC and FPGA validate against the same reference.
