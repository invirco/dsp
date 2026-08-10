# ADSP-21564 Digital Mixer DSP — Implementation Plan

> **SUPERSEDED (2026-07-31).** This plan predates the D24 schematics and the
> binding DSP4 architecture decisions. Known-wrong content kept only for
> history: the Link Port LP0 control path does not exist in hardware (D1:
> the Pi/CM4 masters each DSP directly over SPI; no MCU relay, no
> inter-chip control link), and the inter-chip audio transport is 8× TDM16
> mix-fabric lines (128 slots), not a single SPORT TDM32. Current ground
> truth: `dsp4-architecture-decisions.md`, `MW/D24/HW/hardware-map.md`,
> and the slot map in `shared/dsp4-logic/`. The unified firmware lives in
> `MW/D32/DSP/SHARC/` (D3); this D24 tree is retired from active work.

## 1. Target Hardware

- **DSP**: 2× ADSP-21564 SHARC+ (up to 1 GHz, 2 MB L2 SRAM, 8× SPORT TDM/I2S, HW FIR/IIR accelerators)
- **PCB**: Single 32-channel DSP module used in both D24 and D32 products
  - D32: all 32 channels active
  - D24: 32 channels present, 8 redundant (inactive / available for test)
- **Replaces**: All 8× ADAU1466 SigmaDSP chips (completely removed from design)
- **Sample rate**: 48 kHz / 32-bit float

## 2. Architecture

```
                   ┌─────────────────────────────────────────────────┐
                   │                  DSP PCB Module                 │
                   │                                                 │
  ADC TDM ────────►│  CHIP 1 (Input DSP)    CHIP 2 (Output DSP)     │────────► DAC TDM
  (32 ch in)       │  ┌──────────────┐      ┌──────────────────┐    │  (32 ch out)
                   │  │ Per-channel:  │      │ Mix bus summing   │    │
                   │  │  Gain         │      │ Master EQ         │    │
                   │  │  EQ (Biquad)  │      │ Reverb (Freeverb) │    │
                   │  │  FIR          │      │ Limiter           │    │
                   │  │  Comp/Gate    │      │ Output router     │    │
                   │  └──────┬───────┘      └───────▲───────────┘    │
                   │         │ SPORT TDM32 (audio)  │                │
                   │         └──────────────────────┘                │
                   │         ┌──────────────────────┐                │
                   │         │ Link Port LP0 (ctrl) │                │
                   │         └──────────────────────┘                │
                   └─────────────────────────────────────────────────┘
                                       ▲
                                       │ SPI (boot + params)
                                       │
                              H1S1 MCU (STM32U575)
                                       ▲
                                       │ Serial (S_SCAN / S_RUN / S_TICK)
                                       │
                                  Pi (MH1)
                                       ▲
                                       │
                                Matrix App
```

### Chip 1 — Input DSP
- 32 input channels received via SPORT TDM from ADCs
- Per-channel processing strip: GAIN → EQ_BIQUAD → FIR → COMPRESSOR/GATE
- Sends 32 processed channels to Chip 2 via dedicated SPORT TDM32

### Chip 2 — Output DSP
- Receives 32 processed channels from Chip 1 via SPORT TDM32
- Mix bus summing (routing matrix)
- Master EQ, reverb, limiter
- Output routing to DACs via SPORT TDM

### Inter-chip Communication
- **Audio**: 1× SPORT TDM32 — 32 channels, 48 kHz/32-bit = 49.152 Mbps (uses 1 of 8 SPORTs per chip)
- **Control params**: SHARC Link Port LP0 — coefficient updates, routing matrix changes, mutes

### Product Differentiation
- Same binary image for D24 and D32
- H1S1 sends a channel-mask config register on boot
- D24 masks 8 channels inactive; D32 enables all 32

## 3. Control Architecture

The existing Matrix system (as defined in the Matrix Bible) controls the DSP:

1. **Matrix App** sends control messages via serial protocol to Pi (MH1)
2. **Pi** relays to **H1S1 MCU** (STM32U575RIT6) via serial bus (115200 baud)
3. **H1S1** communicates with ADSP-21564 chips via **SPI**:
   - **Boot**: loads DSP firmware image on power-up (replaces existing ADAU1466 dsp_boot.c pattern)
   - **Runtime params**: writes gain coefficients, EQ biquad coefficients, routing matrix, mutes
   - **Scene/preset recall**: bulk-writes stored coefficient blocks from H1S1 flash
   - **Individual controls**: fader, EQ, mute mapped via `matrix.csv` `DspSpi`/`DspPage`/`DspAdd` columns

Serial protocol tokens: `S_SCAN` (enumerate), `S_RUN` (start), `S_TICK` (100 ms heartbeat), `S_FLASH` (firmware update).

Chip 1 receives all SPI traffic from H1S1. Parameters destined for Chip 2 are forwarded via Link Port LP0.

## 4. DSP Architecture & Feature Set

This document is the single source of truth for DSP signal chain topology, full feature set, and SPI parameter addressing. No CSV graph or code generation tools are used. Architecture decisions live here; implementation reads directly from this spec.

### Signal Flow Overview

```
ADC TDM (32 ch)
  │
  ▼
[Chip 1 — Input Processing]                             48 kHz / 32-bit float
  Per channel ×32:
    TRIM → PHASE → HPF → EQ_4BAND → GATE → COMP → PAN → FADER → MUTE
                                                      │
                                         AUX SEND ×8 (pre or post fader)
                                         GROUP / MAIN ASSIGN (bitmask)
  │
  ▼ SPORT TDM — bus pre-sums to Chip 2 (8 aux + 8 groups + 2 main L/R)
  │
[Chip 2 — Bus Processing & Output]
  AUX BUSES ×8:   SUMMING → FADER → EQ_4BAND → COMP → LIMITER → out
  GROUP BUSES ×8: SUMMING → FADER → EQ_4BAND → COMP → out
  MAIN L/R BUS:   SUMMING → FADER → GEQ_31BAND → COMP → LIMITER → out
  REVERB:         FREEVERB stereo ← aux send → return → main
  OUTPUT ROUTER:  assign bus outputs to DAC TDM slots
  │
  ▼
DAC TDM (32 ch)
```

> **Inter-chip data**: Chip 1 accumulates per-channel sends into bus pre-sums and forwards over a dedicated SPORT TDM link. Exact slot allocation TBD pending final output count.

### Per-Channel Strip (Chip 1 — 32 channels)

| Stage | Description | Controllable Parameters |
|-------|-------------|------------------------|
| **TRIM** | Input gain ±24 dB | `gain_db` |
| **PHASE** | Phase invert 0° / 180° | `invert` (bool) |
| **HPF** | 2nd-order Butterworth high-pass | `enabled`, `freq_hz` (20–500 Hz) |
| **EQ_4BAND** | 4-band parametric EQ | Per band: `freq_hz`, `gain_db`, `q`, `type` (peak / lo-shelf / hi-shelf / HPF / LPF) |
| **GATE** | Noise gate / expander | `threshold_db`, `ratio`, `attack_ms`, `hold_ms`, `release_ms`, `range_db` |
| **COMPRESSOR** | VCA-style downward compressor | `threshold_db`, `ratio`, `attack_ms`, `release_ms`, `knee_db`, `makeup_db` |
| **PAN** | Stereo pan, −3 dB centre law | `pan` (−1.0 to +1.0) |
| **FADER** | Channel level fader | `fader_db` (−∞ to +10 dB) |
| **MUTE** | Hard mute | `mute` (bool) |
| **AUX SEND ×8** | Pre or post-fader send to each aux bus | Per send: `send_db`, `pre_fader` (bool), `send_mute` (bool) |
| **GROUP ASSIGN** | Route to group buses and/or main L/R | `group_mask` (8-bit), `main_assign` (bool) |

> **Solo** is AFL/PFL logic managed by H1S1 MCU, not computed in DSP.

### Aux Buses (Chip 2 — 8 buses)

Typical use: monitor mixes, FX sends, IEM feeds.

| Stage | Description | Controllable Parameters |
|-------|-------------|------------------------|
| **SUMMING** | Sum per-channel sends for this bus | — |
| **FADER** | Bus master fader | `fader_db` |
| **EQ_4BAND** | 4-band parametric EQ | Same param set as channel EQ |
| **COMPRESSOR** | Bus compressor | Same param set as channel compressor |
| **LIMITER** | Output limiter | `threshold_db`, `attack_ms`, `release_ms` |
| **OUTPUT ASSIGN** | Map to DAC output slot(s) | `out_slot` |

### Group Buses (Chip 2 — up to 8 groups)

Typical use: drum group, band stem, mix minus.

| Stage | Description | Controllable Parameters |
|-------|-------------|------------------------|
| **SUMMING** | Sum assigned channels | — |
| **FADER** | Group fader | `fader_db` |
| **EQ_4BAND** | 4-band parametric EQ | Same param set as channel EQ |
| **COMPRESSOR** | Group compressor | Same param set as channel compressor |
| **OUTPUT ASSIGN** | Feed main L/R and/or DAC | `feeds_main` (bool), `out_slot` |

### Main L/R Bus (Chip 2)

| Stage | Description | Controllable Parameters |
|-------|-------------|------------------------|
| **SUMMING** | Sum assigned channels and groups | — |
| **FADER** | Master fader | `fader_db` |
| **GEQ_31BAND** | 31-band graphic EQ — 1/3-octave ISO centres | Per band: `gain_db` (±12 dB) |
| **COMPRESSOR** | Master bus compressor | Same param set as channel compressor |
| **LIMITER** | Brick-wall output limiter | `threshold_db`, `attack_ms`, `release_ms` |
| **OUTPUT ASSIGN** | Map to DAC output slot(s) | `out_slot` |

### Effects (Chip 2)

| Effect | Description | Controllable Parameters |
|--------|-------------|------------------------|
| **REVERB** | Stereo Freeverb (Schroeder-Moorer) | `room_size`, `damping`, `wet_db`, `dry_db`, `width` |

- Fed from a configurable aux send bus (typically AUX 7 or 8)
- Stereo return summed into main L/R (and optionally other buses)
- Single instance; a second may be added if L2 SRAM headroom permits after Phase 5 profiling

### Metering (Chip 1 + 2)

Values accumulated per ISR frame, packaged every `S_TICK` (100 ms), returned to H1S1 via SPI reads, forwarded serial → Pi → Matrix App.

| Meter | Tap Point | Format |
|-------|-----------|--------|
| Input level | Post-TRIM | Peak + RMS, per channel |
| Gate GR | Post-GATE | Gain reduction dB, per channel |
| Compressor GR | Post-COMPRESSOR | Gain reduction dB, per channel |
| Channel output | Post-FADER | Peak, per channel |
| Aux bus | Post-FADER | Peak + RMS, per bus |
| Group bus | Post-FADER | Peak + RMS, per group |
| Main L/R | Post-LIMITER | Peak + RMS, stereo |

### SPI Parameter Addressing

Parameters are addressed by `page` (node instance) and `addr` (parameter within that node). These appear in `matrix.csv` as `DspPage` and `DspAdd` and must stay in sync with this table.

| Page Range | Node | Notes |
|------------|------|-------|
| 0x00–0x1F | Channel strip 0–31 | One page per channel; offsets below |
| 0x20–0x27 | Aux bus 0–7 | One page per bus |
| 0x28–0x2F | Group bus 0–7 | One page per group |
| 0x30 | Main L/R bus | — |
| 0x31 | Reverb | — |
| 0x40 | Global config | Channel mask (D24 vs D32), sample rate |
| 0x50 | Meter poll | Read-only — DSP returns packed meter block |

**Channel page parameter offsets (pages 0x00–0x1F):**

| Offset | Parameter | Type | Range |
|--------|-----------|------|-------|
| 0x00 | `gain_db` | float32 | −24.0 to +24.0 |
| 0x01 | `invert` | uint8 | 0 / 1 |
| 0x02 | `hpf_enabled` | uint8 | 0 / 1 |
| 0x03 | `hpf_freq_hz` | float32 | 20–500 |
| 0x04–0x13 | `eq_band[0–3]` (freq / gain / q / type) | 4× float32 ×4 | — |
| 0x14 | `gate_threshold_db` | float32 | −80 to 0 |
| 0x15 | `gate_ratio` | float32 | 1–100 |
| 0x16 | `gate_attack_ms` | float32 | 0.1–100 |
| 0x17 | `gate_hold_ms` | float32 | 1–1000 |
| 0x18 | `gate_release_ms` | float32 | 10–4000 |
| 0x19 | `gate_range_db` | float32 | −80 to 0 |
| 0x1A | `comp_threshold_db` | float32 | −60 to 0 |
| 0x1B | `comp_ratio` | float32 | 1–∞ |
| 0x1C | `comp_attack_ms` | float32 | 0.1–100 |
| 0x1D | `comp_release_ms` | float32 | 10–4000 |
| 0x1E | `comp_knee_db` | float32 | 0–12 |
| 0x1F | `comp_makeup_db` | float32 | 0–24 |
| 0x20 | `pan` | float32 | −1.0 to +1.0 |
| 0x21 | `fader_db` | float32 | −144 to +10 |
| 0x22 | `mute` | uint8 | 0 / 1 |
| 0x23–0x2A | `aux_send_db[0–7]` | float32 ×8 | −144 to +10 |
| 0x2B | `aux_pre_fader_mask` | uint8 | bit n = aux n pre-fader |
| 0x2C | `aux_mute_mask` | uint8 | bit n = aux n muted |
| 0x2D | `group_mask` | uint8 | bit n = routed into group n |
| 0x2E | `main_assign` | uint8 | 0 / 1 |

> **Aux / group / main bus page offsets** to be defined when Chip 2 implementation begins (Phase 4). Follow the same `fader_db`, `eq_band[n]`, `comp_*`, `lim_*` naming conventions.

### Scene / Preset Recall

- All parameters above constitute a **scene** — stored and managed in H1S1 flash
- Recall: H1S1 bulk-writes all coefficients in SPI page order
- DSP holds **double-buffered coefficient arrays** — swaps atomically at ISR frame boundary
- DSP is a stateless coefficient receiver; no scene storage on DSP side

## 5. Toolchain

- **CCES CLI** (`cc21k.exe`, `asm21k.exe`, `ld21k.exe`) runs under **Wine** on Linux
- **VS Code** for editing — `tasks.json` wraps Wine calls for Build / Clean tasks
- **build.sh**: thin shell wrapper calling `wine cc21k.exe` / `wine asm21k.exe` / `wine ld21k.exe`
- **JTAG flashing** (via ADZS-ICE-1500 emulator): deferred until hardware available; will use Wine USB passthrough or a Windows machine

## 6. Code Strategy: C vs ASM

| Layer | Language | Rationale |
|-------|----------|-----------|
| Boot / init | C | Readable, maintainable — SPORT, DMA, SPI slave, Link Port setup |
| Peripheral config | C | Register setup is not cycle-critical |
| SPI parameter handler | C | Coefficient parsing, scene/preset bulk load |
| DSP inner loops | **ASM** | Full parallel issue, SIMD, deterministic cycle count |
| HW FIR/IIR engine setup | C + ASM | C for config, ASM for trigger/data marshalling |

### Per-node ASM approach
- **GAIN**: SIMD multiply-accumulate, 2 channels per cycle
- **EQ_BIQUAD**: Hardware IIR accelerator engine
- **FIR**: Hardware FIR accelerator engine
- **MIX_BUS**: SIMD parallel accumulate across source channels
- **COMPRESSOR/GATE**: Peak/RMS detect → gain reduction curve → smooth apply
- **DELAY / REVERB**: Circular buffers in L2 SRAM (2 MB available)
- **LIMITER**: Peak detect → brick-wall gain reduction

## 7. Reverb

### Available Reference Code
ADI's SAM Bare Metal Audio Framework (`analogdevicesinc/sam-audio-starter`, Apache 2.0) includes:

| File | Purpose |
|------|---------|
| `effect_stereo_reverb.c/.h` | Complete stereo Freeverb implementation |
| `allpass_filter.c/.h` | Allpass filter (allpass-from-two-combs, per Stanford CCRMA) |
| `integer_delay_lpf.c/.h` | Single-tap delay with feedback LPF dampening |
| `integer_delay_multitap.c/.h` | Multi-tap delay (up to 32 taps per delay line) |

Written for ADSP-SC589 SHARC+ — same ISA as ADSP-21564, directly portable. Block-based, float32, struct-instanced.

### SigmaStudio Reverb — Not Convertible
SigmaStudio reverb blocks compile to proprietary SigmaDSP microcode (opaque `.dat` binary). No published ISA, cannot be disassembled or translated. The algorithm must be reimplemented, not ported from SigmaStudio exports.

### Reverb Implementation Plan
1. **Start**: Port ADI Freeverb C code to ADSP-21564 (minimal changes expected)
2. **Optimise**: Profile and convert hot inner loops (allpass, delay tap reads) to ASM
3. **Upgrade** (if needed): Implement Schroeder/Moorer or plate reverb for higher quality

## 8. Implementation Phases

### Phase 0 — CCES CLI Scaffold *(superseded — Wine plan obsolete)*

The original plan wrapped a Windows CCES install in Wine with a licence
copied into the prefix. That is dead: CCES 3.0.3 runs natively on Linux
from `/opt/analog/cces/3.0.3` under the node-locked AD-CCES-NODE-1
licence, and D32's `MW/D32/DSP/SHARC/build.sh` is the reference native
build (D24 converges on the same unified DSP4 firmware). Do not build a
Wine prefix or copy licence material around.

### Phase 1 — Architecture Spec *(current phase)*
5. Define full feature set in `dsp.plan.md` (this document)
6. Define SPI parameter addressing table (Section 4)
7. Iterate on signal chain design before writing any code

### Phase 2 — Core ISR Scaffold
8. Boot/init C: SPORT, DMA, SPI slave, Link Port setup (both chips)
9. Minimal ISR loop: TDM in → passthrough → SPORT TDM → Chip 2 → TDM out
10. Verify 32-channel audio passes through on hardware without corruption

### Phase 3 — Input Strip (Chip 1)
11. Per-channel strip: TRIM → PHASE → HPF → EQ_4BAND → GATE → COMP → PAN → FADER → MUTE
12. Aux send accumulation (8 sends × 32 channels → 8 aux bus pre-sums)
13. Group / main bus accumulation → forward all bus pre-sums to Chip 2 via SPORT TDM
14. Verify individual stages against spec measurements

### Phase 4 — Bus Processing (Chip 2)
15. Aux bus: summing, fader, EQ, compressor, limiter, DAC slot output
16. Group bus: summing, fader, EQ, compressor, DAC / main feed
17. Main L/R bus: summing, fader, 31-band GEQ, compressor, limiter
18. Output router: assign bus outputs to physical DAC TDM slots

### Phase 5 — Effects
19. Port ADI Freeverb from `sam-audio-starter` to ADSP-21564
20. Integrate as Chip 2 reverb return into main L/R bus
21. SPI parameter control: `room_size`, `damping`, `wet_db`, `dry_db`, `width`

### Phase 6 — Metering & Scene Recall
22. ISR accumulation: peak + RMS at all tap points (Section 4)
23. SPI read handler: pack and return meter block on H1S1 `S_TICK` poll
24. SPI bulk-write handler: scene recall, atomic double-buffer coefficient swap

## 9. Verification

| # | Test | Pass Criteria |
|---|------|---------------|
| 1 | `wine asm21k.exe --version` | Returns version string |
| 2 | 2-channel SPORT loopback | Audio in → passthrough → out on scope |
| 3 | Full 32-channel pass | All channels pass without corruption |
| 4 | Per-channel TRIM | Gain change measures correctly on scope |
| 5 | HPF | Roll-off at configured frequency confirmed |
| 6 | EQ 4-band | Boost/cut at each band frequency confirmed |
| 7 | Gate / Compressor | GR measurable, thresholds and ratios correct |
| 8 | Fader + mute | Level changes and hard mute confirmed |
| 9 | Aux send routing | Channel send appears on aux bus output |
| 10 | Group + main bus | Full mix present on main L/R output |
| 11 | GEQ 31-band | Band gain at ISO frequencies confirmed |
| 12 | Main limiter | Output brickwalled at threshold |
| 13 | SPI coefficient write | H1S1 writes gain → DSP updates next ISR frame |
| 14 | Scene recall | H1S1 bulk-writes → all params update atomically |
| 15 | Metering | Reported peak/RMS matches scope measurements |
| 16 | Reverb | Wet signal audible on main output when enabled |

## 10. File Structure

```
MW/D24/DSP/SHARC/
├── dsp.plan.md              ← this file (architecture spec + feature set + SPI map)
├── build.sh                 ← Wine-wrapped CCES CLI build script
├── .vscode/
│   └── tasks.json           ← VS Code build tasks
└── src/
    ├── chip1/
    │   ├── boot.c            ← Chip 1 init, SPORT, DMA, SPI slave
    │   ├── main.asm          ← Chip 1 ISR audio loop
    │   ├── input_strip.asm   ← Per-channel strip (trim, phase, HPF, EQ, gate, comp, pan, fader)
    │   ├── aux_send.asm      ← Aux send accumulation (8 sends × 32 channels)
    │   └── bus_accum.asm     ← Group / main bus pre-summing
    └── chip2/
        ├── boot.c            ← Chip 2 init, SPORT, DMA, Link Port
        ├── main.asm          ← Chip 2 ISR audio loop
        ├── aux_bus.asm       ← Aux bus processing (summing, fader, EQ, comp, limiter)
        ├── group_bus.asm     ← Group bus processing
        ├── main_bus.asm      ← Main L/R bus (fader, GEQ, comp, limiter)
        ├── reverb.asm        ← Freeverb stereo reverb
        ├── output_router.asm ← DAC slot assignment
        └── metering.asm      ← Peak/RMS accumulation, SPI meter pack
```

## 11. Key References

- **Matrix Bible**: `_0/app-avalonia/docs/MatrixBible.md` — serial protocol, boot sequence, control architecture
- **matrix.csv**: `MW/D32/MX/matrix.csv` — `DspSpi`/`DspPage`/`DspAdd` columns — must stay in sync with SPI map in Section 4
- **fw.csv**: `MW/D32/FW/fw.csv` — H1S1 MCU definition (STM32U575RIT6)
- **dsp_boot.c**: `MW/D24/DSP/dsp_boot.c` — existing ADAU1466 SPI boot code (reference pattern)
- **ADI SAM Audio Starter**: `github.com/analogdevicesinc/sam-audio-starter` — Freeverb, audio elements (Apache 2.0)
- **ADI SHARC Reusable Components**: `github.com/analogdevicesinc/sharc-reusable-components` — drivers, services (Apache 2.0)
- **ADSP-21564 Data Sheet**: `analog.com/media/en/technical-documentation/data-sheets/adsp-21560-21561-21564-21568.pdf`
- **ADSP-21564 Hardware Reference**: `analog.com/media/en/dsp-documentation/processor-manuals/adsp-21560-21561-21564-21568-hrm.pdf`
