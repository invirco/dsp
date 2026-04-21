# dsp.csv Schema Reference

This document defines the schema for `dsp.csv`, the signal graph definition file for the ADSP-21564 digital mixer DSP.

## Overview

`dsp.csv` is a plain-text, comma-separated file where each row defines one DSP processing node. The file is:
- **Git-diffable** — plain text, meaningful diffs on any change
- **Scriptable** — consumed by Python tools for validation, diagram generation, and ASM code generation
- **Engineer-editable** — can be modified in any spreadsheet or text editor

## Workflow

```
dsp.csv
  │
  ├──► tools/dsp_validate.py    → errors/warnings to stdout
  ├──► tools/dsp_diagram.py     → dsp_diagram.png (Graphviz)
  └──► tools/dsp_codegen.py     → src/chip1/nodes/*.asm, src/chip2/nodes/*.asm
```

## Columns

| # | Column | Type | Required | Description |
|---|--------|------|----------|-------------|
| 1 | `id` | string | yes | Unique node identifier. Convention: `C1_xxx` for Chip 1, `C2_xxx` for Chip 2. Examples: `C1_IN_01`, `C1_GAIN_01`, `C2_MIX_L` |
| 2 | `chip` | int | yes | Target chip: `1` (Input DSP) or `2` (Output DSP) |
| 3 | `type` | string | yes | Node type — see Node Types table below |
| 4 | `label` | string | yes | Human-readable label for diagrams. Example: `"Ch 1 Input"`, `"Master L EQ"` |
| 5 | `ch_count` | int | yes | Number of audio channels this node processes |
| 6 | `inputs` | string | yes | Comma-separated list of source node `id`s (semicolon-delimited within cell). Empty string `""` for source nodes (INPUT_TDM, INTERCHIP_RECV) |
| 7 | `outputs` | string | yes | Comma-separated list of destination node `id`s (semicolon-delimited within cell). Empty string `""` for sink nodes (OUTPUT_TDM, INTERCHIP_SEND) |
| 8 | `spi_page` | int | no | SPI parameter page address (aligns with matrix.csv DspPage). `-1` if not SPI-controllable |
| 9 | `spi_addr` | int | no | SPI parameter base address within page (aligns with matrix.csv DspAdd). `-1` if not SPI-controllable |
| 10 | `params` | string | no | Type-specific parameters as `key=value` pairs separated by semicolons. See per-type param definitions below |

## Node Types

### Source Nodes (no audio input)

#### `INPUT_TDM`
SPORT TDM input — receives audio from external ADC.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `sport_id` | int | — | SPORT peripheral ID (0–7) |
| `slot_start` | int | — | First TDM slot |
| `slot_count` | int | — | Number of TDM slots consumed |

#### `INTERCHIP_RECV`
Receives audio from the other chip via dedicated inter-chip SPORT TDM32.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `sport_id` | int | — | SPORT peripheral ID used for inter-chip link |
| `slot` | int | — | TDM slot number (0–31) |

### Processing Nodes

#### `GAIN`
Per-channel gain / fader. SPI-controllable.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `gain_db` | float | `0.0` | Initial gain in dB. Range: -inf to +20.0 |
| `mute` | int | `0` | Mute flag (0 = unmuted, 1 = muted) |

#### `EQ_BIQUAD`
Parametric EQ — cascaded biquad sections. SPI-controllable (coefficients written per band).

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `bands` | int | `4` | Number of biquad stages (1–8) |
| `coeffs` | string | `"default"` | Initial coefficient set name or `"default"` for flat response (all b0=1, others=0) |

Coefficients per band (5 values): `b0, b1, b2, a1, a2` — written via SPI at runtime.

#### `FIR`
FIR filter using ADSP-21564 hardware FIR accelerator engine. SPI-controllable (coefficient table).

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `taps` | int | `64` | Number of FIR taps |
| `coeff_addr` | hex | — | L2 SRAM base address for coefficient storage |

#### `COMPRESSOR`
Dynamics processor — compressor. SPI-controllable.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `threshold_db` | float | `-20.0` | Threshold in dB |
| `ratio` | float | `4.0` | Compression ratio (1.0 = no compression) |
| `attack_ms` | float | `5.0` | Attack time in ms |
| `release_ms` | float | `100.0` | Release time in ms |
| `knee_db` | float | `6.0` | Soft knee width in dB (0 = hard knee) |
| `makeup_db` | float | `0.0` | Makeup gain in dB |

#### `GATE`
Dynamics processor — noise gate. SPI-controllable.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `threshold_db` | float | `-40.0` | Gate threshold in dB |
| `attack_ms` | float | `1.0` | Attack time in ms |
| `hold_ms` | float | `50.0` | Hold time in ms |
| `release_ms` | float | `100.0` | Release time in ms |
| `range_db` | float | `-80.0` | Maximum attenuation when gate is closed |

#### `MIX_BUS`
Summing bus — accumulates multiple source channels with individual gains. SPI-controllable (per-source gains).

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `bus_id` | int | — | Mix bus identifier |
| `source_gains` | string | `"0.0"` | Semicolon-separated list of initial gains (dB) per source, matching `inputs` order |

#### `REVERB`
Stereo reverb (Freeverb architecture). Runs on Chip 2. SPI-controllable.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `room_size` | float | `0.7` | Room size (0.0–1.0) |
| `damping` | float | `0.5` | HF damping (0.0–1.0) |
| `wet` | float | `0.3` | Wet signal level (0.0–1.0) |
| `dry` | float | `0.7` | Dry signal level (0.0–1.0) |
| `width` | float | `1.0` | Stereo width (0.0–1.0) |

#### `EQ_MASTER`
Master output EQ — same structure as `EQ_BIQUAD` but placed on Chip 2 output path.
Same params as `EQ_BIQUAD`.

#### `LIMITER`
Output limiter — brick-wall peak limiter. SPI-controllable.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `threshold_db` | float | `-0.5` | Limit threshold in dB |
| `attack_ms` | float | `0.1` | Attack time in ms |
| `release_ms` | float | `50.0` | Release time in ms |

#### `ROUTER`
Output routing — maps a source channel to an output slot. SPI-controllable.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `dest_slot` | int | — | Destination TDM output slot |

### Sink Nodes (no audio output)

#### `INTERCHIP_SEND`
Sends audio to the other chip via dedicated inter-chip SPORT TDM32.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `sport_id` | int | — | SPORT peripheral ID used for inter-chip link |
| `slot` | int | — | TDM slot number (0–31) |

#### `OUTPUT_TDM`
SPORT TDM output — sends audio to external DAC.

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `sport_id` | int | — | SPORT peripheral ID (0–7) |
| `slot_start` | int | — | First TDM slot |
| `slot_count` | int | — | Number of TDM slots produced |

## Validation Rules

Rules enforced by `tools/dsp_validate.py`:

1. **Unique IDs**: Every `id` must be unique across the file
2. **Valid chip**: `chip` must be `1` or `2`
3. **Valid type**: `type` must be one of the defined node types
4. **Input references**: Every ID listed in `inputs` must exist as a node `id`
5. **Output references**: Every ID listed in `outputs` must exist as a node `id`
6. **Bidirectional links**: If node A lists B in `outputs`, node B must list A in `inputs` (and vice versa)
7. **Source nodes**: `INPUT_TDM` and `INTERCHIP_RECV` must have empty `inputs`
8. **Sink nodes**: `OUTPUT_TDM` and `INTERCHIP_SEND` must have empty `outputs`
9. **Channel count consistency**: Connected nodes must have compatible `ch_count` values
10. **INTERCHIP pairs**: Each `INTERCHIP_SEND` on Chip 1 must have a matching `INTERCHIP_RECV` on Chip 2
11. **SPI address uniqueness**: No two nodes on the same chip may share the same `spi_page` + `spi_addr` combination
12. **Required params**: Each node type must have all required (non-default) params present
13. **No orphan nodes**: Every node must have at least one connection (input or output)
14. **No cross-chip audio links**: Direct audio connections must stay within the same chip; cross-chip links use INTERCHIP_SEND/RECV only

## SPI Address Mapping

SPI addresses in `dsp.csv` align with the existing `matrix.csv` `DspPage` and `DspAdd` columns. This ensures the Matrix control system can address DSP parameters without translation.

When H1S1 receives a control change (e.g. fader move on Channel 3):
1. Matrix app sends parameter update via serial protocol
2. H1S1 looks up `DspPage` + `DspAdd` from its config
3. H1S1 writes the new value to the ADSP-21564 via SPI at that page/address
4. The DSP's SPI receive ISR updates the coefficient in L2 SRAM
5. On the next audio ISR frame, the updated coefficient is used

For scene/preset recall, H1S1 bulk-writes all coefficient blocks in a single SPI burst. The DSP uses double-buffered coefficients with an atomic swap on the next ISR boundary to avoid glitches.

## Example Row

```csv
id,chip,type,label,ch_count,inputs,outputs,spi_page,spi_addr,params
C1_IN_01,1,INPUT_TDM,Ch 1 Input,1,"","C1_GAIN_01",-1,-1,"sport_id=0;slot_start=0;slot_count=1"
C1_GAIN_01,1,GAIN,Ch 1 Gain,1,"C1_IN_01","C1_EQ_01",1,100,"gain_db=0.0;mute=0"
```

## Conventions

- Use `C1_` prefix for Chip 1 nodes, `C2_` for Chip 2 nodes
- Channel numbers in IDs use two-digit zero-padded format: `01`–`32`
- Bus names use descriptive suffixes: `_L`, `_R`, `_MAIN`, `_AUX1`, etc.
- Params with default values can be omitted from the `params` column
- Quote any cell containing commas or semicolons

---

## Fixed vs Floating Point (ADSP-21564 / SHARC+)

### Key Architecture Fact
Fixed-point and single-precision float execute at the **same speed** on SHARC+ (1-cycle ALU/multiply for both). There is no FP penalty — both are first-class hardware citizens.

### Same Register File
`R0–R15` (fixed) and `F0–F15` (float) are **aliases of the same physical registers**. No separate register bank. Conversion between types costs 1 cycle via `FLOAT`/`FIX` instructions.

### When to Use Float
- Internal signal processing (mixing, routing, gain staging)
- Multi-stage chains where dynamic range or overflow avoidance matters
- Simpler code — no Q-format bookkeeping between stages

### When to Use Fixed
- **Hardware IIR accelerator** — operates in fixed-point (1.31 or 5.27); using float adds a 1-cycle convert per tap
- **SigmaDSP I/O boundary** — SigmaDSP uses 5.23 fixed-point; conversion required at the interface
- Bit-exact determinism requirements

### Mixing Fixed and Float
Freely mixable within the same C file, function, or ASM routine.

```c
// Fixed → float (e.g. from TDM input or SigmaDSP)
float32_t sample_f = (float32_t)sample_fixed / (float32_t)(1 << 31);

// Float → fixed (e.g. for IIR accelerator or SigmaDSP output)
int32_t out_fixed = (int32_t)(out_f * (float32_t)(1 << 31));
```

```asm
F0 = FLOAT R4;       // fixed → float (1 cycle)
R4 = FIX F0 BY 0;   // float → fixed (1 cycle)
```

### Recommended Pattern
Use **float** throughout the internal signal graph. Convert only at boundaries:
- SigmaDSP coefficient writes (5.23 fixed)
- Hardware IIR accelerator input/output
- TDM sample I/O if the peripheral delivers raw fixed-point samples

For heavy EQ filter banks using the IIR accelerator, keep those paths in fixed-point to avoid per-tap conversion overhead.
