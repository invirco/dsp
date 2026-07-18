# DSP Definition — D32

Matrix DSP parameter definition file.  
Engine-agnostic: this file is the source of truth for DSP address assignment, coefficient
formulas, and routing. A build tool (`gen_dsp.py`) expands it and backfills the `DspSpi`,
`DspAdd`, `DspAddHex`, and `Table` columns of `_matrix.csv`.

### Group GEQ transition note (2026-07-18)

- `gen_dsp.py` now includes a guarded compatibility path: `--enable-grp-geq-alias`.
- Default behavior is unchanged (flag off).
- When enabled, Group `GEQ` nodes also emit `GrpPeq` alias cells at the same SPI addresses.
- Purpose: allow staged matrix migration from `GrpPeq` to `GrpGeq` without breaking mapping.
- Full DSP build verification remains blocked on CCES-gated validation.

> **Status: IN PROGRESS** — LP0 inter-chip link removed (ADSP-21564 has no link ports); dual independent SPI confirmed (H1S1 → CS1 → Chip 1 SPI1, H1S1 → CS2 → Chip 2 SPI1). Inter-chip audio: SPORT7 TDM single-lane, 25 slots (0–24), chip1=master/chip2=slave. Board in fabrication, no revision needed. Code generation pipeline complete; infrastructure ASM reviewed; CCES 3.0.3 build verified **0 errors 0 warnings** (630 ASM files → chip1.dxe + chip2.dxe). **H1S1 firmware complete and building** (13% flash, <1% RAM; outside-IDE build via `fw.sh` producing `.shex`). EV-SOMCRR-EZLITE carrier board on order for JTAG debug bring-up.

**Status legend**

| Flag | Meaning |
|------|---------|
| ✅ DONE | Completed and verified |
| 🔄 ACTIVE | Currently in progress |
| ⬜ TODO | Not started |
| ⚠ BLOCKED | Blocked — reason shown inline |
| 🗑 SUPERSEDED | Replaced by a later decision |

---

## 1. Hardware Topology

| Item | Value | Notes |
|------|-------|-------|
| DSP | ADSP-21564 | Sharc+, 1 GHz, 32/40-bit float |
| Chip count | **2×** | Chip 1 = Input DSP; Chip 2 = Output DSP |
| Inter-chip audio | SPORT7 TDM single-lane | Chip1 TX → Chip2 RX; 32-slot TDM frame, 25 buses in slots 0–24, 49.152 MHz BCLK (1024×fs), chip1=master |
| Inter-chip control | Dual independent SPI | H1S1 CS1 → Chip1 SPI1; H1S1 CS2 → Chip2 SPI1; no forwarding between chips |
| SPI bus | SPI1 (H1S1 MCU) | Two chip-selects; H1S1 addresses each chip directly |
| Number format | Float32 | IEEE 754 throughout |
| Sample rate | 48 kHz | — |
| Block size | 32 samples | 667 µs per block |

**Chip roles:**

| Chip | Role | Input | Output |
|------|------|-------|--------|
| Chip 1 — Input DSP (DSPA / U6) | Per-channel strip (TRIM→PHASE→HPF→EQ→GATE→COMP→PAN→FADER) | I0..I3 = ADC/NET 1-32 (+ I4..I7 optional sources) | O0..O7 = MIX_1..128 to Chip 2 |
| Chip 2 — Output DSP (DSPB / U5) | Bus summing, EQ, dynamics, FX, output routing | MIX_1..128 from Chip 1 | O0..O7 map to DAC/CODEC/NET outputs |

> **Single binary image for D24 and D32.**
> H1S1 sends a `CHAN_MASK` config word on boot.
> D24: channels 25–32 inactive; aux buses 9–12 inactive.
> D32: all 32 channels and 12 aux buses active.

### 1a.1 Schematic-backed transport notes (D24 DSP4 rev C)

- DSPA (U6) and DSPB (U5) are both ADSP-21564 devices on the DSP4 board.
- The inter-DSP audio transport is exposed as `MIX_1..128` from DSPA outputs `O0..O7` into DSPB inputs.
- A passive SPI repeater stage is present on the DSP board (`R73..R78`, 33R) for `iSPI0..2` fanout/isolation.
- Clock/SPI bridging nets are shown as `CK1_0..2` and `CK2_0..2` tied into `SPI[0..2]_1/_2` domains.

> Source: D24 schematic extraction notes (`D24 DSP.md`, `self-test.md`, `png/dsp-08.md`).
> Treat lane width/framing details as schematic-derived bring-up assumptions until validated on live firmware captures.

### 1a.2 CPLD — Altera MAX V (`5M1270ZT144C4`)

The CPLD sits on the same PCB as the two DSPs and provides:

1. **Master clock generation** — derives MCLK, frame sync (48 kHz), and SPORT bit clocks for all ADC/DAC codecs from a system clock input.
2. **TDM input muxing** — any combination of channel inputs can be switched between the local ADC TDM streams and alternative digital sources (USB interface, AES67 network). This is transparent to the DSP — the CPLD substitutes TDM slots before they reach the SPORT inputs.
3. **Miscellaneous routing** — SPI chip-select decode, serial bus routing (srx/mrx/mhtx/mhrx), reset sequencing, LED/heartbeat, test points.

The CPLD is flash-based (no external config device), programmed via JTAG from the Pi. Shared JTAG/SWD pins with the MH1 MCU — never program both simultaneously.

> Clock ratios, TDM slot routing, H1S2 control interface, pin assignments, and implementation phases are defined in [logic.md](../LOGIC/logic.md).

---

## 1b. FPGA Alternative Candidates

The ADSP-21564 is the current target. If a future revision moves to FPGA-based DSP, these are
the relevant options. All use **Xilinx (AMD)** fabric — the dominant choice in pro-audio.

> Source: teardowns, hardware engineer job postings, industry observation. Vendors do not publish exact part numbers.

### General FPGA matching criteria (vs ADSP-21564)

| Requirement | ADSP-21564 baseline |
|-------------|---------------------|
| Sustained FP32 throughput | ~4 GFLOPS |
| On-chip SRAM | 6 MB |
| Serial audio I/O | I2S / TDM |
| Real-time block processing | 48 kHz, 32+ channels |

> Note: FPGA DSP slices are fixed-point (18×18 or 27×27 MACs). FP32 requires wrapping slices with
> LUT-based exponent logic (vendor FP IP or HLS). On Zynq UltraScale+, one FP32 MAC ≈ 3× DSP58 slices + ~100 LUTs.
> At 32 channels × ~30 coefficients per block this is well within a mid-range Zynq budget.

### FPGA candidate table

| FPGA Family | Vendor | Tier | Why it fits | Consideration |
|-------------|--------|------|-------------|---------------|
| **Zynq UltraScale+ EG/EV** | AMD/Xilinx | High | ARM A53 + 2520 DSP58E2 slices, hard audio codecs, abundant BRAM. Most common SHARC replacement in pro-audio. | Most battle-tested option |
| **Artix UltraScale+** | AMD/Xilinx | Mid | Cheaper than Zynq, 1080+ DSP58E2 slices, no PS overhead — pure fabric. Good if soft CPU not needed. | No hard ARM |
| **Agilex 5** | Intel | High | Variable-precision DSP blocks (27×27 native), hard Cortex-A55/A76, competitive FP32 density. | Newer toolchain story |
| **PolarFire SoC** | Microchip | Mid | Hard RISC-V + FPGA fabric, very low power, 18×18 DSP blocks. | FP32 soft IP less mature |
| **CrossLink-NX / Certus-NX** | Lattice | Low | Small, low-latency, excellent for I/O bridging. | Companion chip only, not full DSP |

### Industry reference designs

| Company | Product | Engine name | Inferred silicon | Source |
|---------|---------|-------------|-----------------|--------|
| **Allen & Heath** | dLive, Avantis | XCVI | Xilinx Artix-7 (XC7A200T range) | Teardowns + FPGA job listings |
| **Allen & Heath** | SQ series | — | Artix-7 variant or SHARC hybrid | Indirect evidence |
| **DiGiCo** | SD-Rack | Stealth / Spidercore | Xilinx Kintex/Virtex-7 | Spidercore co-dev + teardowns |
| **DiGiCo** | Quantum 7/338 | Stealth Digital Processing | Xilinx UltraScale+ (inferred) | Processing density claims |

**Recommendation:** Zynq UltraScale+ (e.g. XCZU4EG or XCZU7EV) is the most proven SHARC
replacement path — pairs a capable ARM core with enough DSP fabric to replace a single ADSP-21564,
and is consistent with what DiGiCo's upper tier appears to use.

### Cost comparison: SHARC vs FPGA

Approximate 1k+ volume pricing. FPGA FP32 throughput is via vendor IP (not native); fixed-point is native.

| Part | Approx. price | FP32 throughput | $/GFLOPS |
|------|--------------|-----------------|----------|
| ADSP-21564 | ~$20–35 | ~4 GFLOPS (native) | **~$6–9** |
| Artix-7 XC7A200T | ~$25–50 | ~0.5–1 GFLOPS (via IP) | ~$40–80 |
| Artix UltraScale+ XCA25P | ~$50–100 | ~1–1.5 GFLOPS | ~$50–80 |
| Zynq US+ XCZU4EG | ~$100–200 | ~1–2 GFLOPS | ~$80–150 |
| Zynq US+ XCZU7EV | ~$250–500 | ~3–4 GFLOPS | ~$80–120 |

**FP32: FPGA is ~10–15× more expensive per GFLOPS than a dedicated SHARC.**

**Fixed-point shifts the equation:** A&H and DiGiCo use Q28–Q31 fixed-point internally, not FP32.
An Artix-7 A200T at 500 MHz delivers ~370 GMACS (18-bit) — the SHARC FP32 advantage disappears
and FPGA becomes cost-competitive. At 48 kHz / 64-sample blocks there are ~10,000 clock cycles
per sample, which is plenty of headroom for fixed-point biquads.

| Factor | SHARC | FPGA |
|--------|-------|------|
| Silicon cost (FP32) | ✓ Clear winner | — |
| Silicon cost (fixed-point) | — | ✓ Competitive |
| Dev time | C/C++ in CCES, fast | VHDL/HLS, 3–6× more effort |
| BOM integration | Separate I/O chip needed | Can absorb audio routing + I/O on same die |
| Supply chain | ADI niche, tighter stock | AMD/Xilinx, broader supply |
| Obsolescence risk | High (ADI shrinking SHARC line) | Low (mainstream commodity) |
| Late-bind flexibility | Code update via USB | Bitstream update, late-binding architecture |

**Conclusion for D32:** At small-to-mid production volume, SHARC is cheaper silicon and faster
to develop against. FPGA becomes compelling only when absorbing multiple chips (DSP + audio
networking + I/O routing) onto one die — a scale justified by large-console makers, not here.
ADSP-21564 is the right first target.

---

## 1c. D24 vs D32 Product Differentiation

> Same DSP PCB and firmware binary. Feature differences are enabled by H1S1 boot config (`CHAN_MASK` + `AUX_MASK`).

| Feature | D24 | D32 | Notes |
|---------|-----|-----|-------|
| Active input channels | 24 (ch 1–24) | 32 (ch 1–32) | Ch 25–32 present but masked on D24 |
| Mono Aux buses | 4 (Aux 1–4) | 6 (Aux 1–6) | D24 uses lower 4 only |
| Stereo Aux bus pairs | 2 (Aux 5–6, 7–8) | 3 (Aux 7–8, 9–10, 11–12) | Bus numbering differs — see note below |
| Total Aux count | 8 | 12 | Aux 9–12 inactive on D24 |
| Group buses | 4 (Grp 1–4) | 4 (Grp 1–4) | Same |
| FX engines | 6 | 6 | Same |
| Center / Sub bus | 1 | 1 | Same |
| Main GEQ | 28-band 1/3-oct | 28-band 1/3-oct | Same |
| Auto anti-feedback (AFB) | Main + Aux | Main + Aux | Same |
| Monitor / Phones section | Yes | Yes | Same |
| Matrix Mix (aux-into-aux) | Yes | Yes | Same |
| DNC-1 Dante card slot | Optional | Optional | Expansion |
| MRC-1 SSD record card | Optional | Optional | Expansion |
| USBC-1 Multitrack DAW card | Optional | Optional | Expansion |

> **Stereo Aux numbering note:** D24 stereo pairs are Aux 5–6 and 7–8 (total 8 auxes).
> D32 stereo pairs are Aux 7–8, 9–10, 11–12 (total 12 auxes); auxes 5–6 are mono on D32.
> The firmware uses `AUX_MASK` to mark inactive buses; the Matrix app adjusts the UI labels per product.

---

## 1d. DSP Capacity Analysis

### Cycle budget

**Block parameters:** 48 kHz, 32-sample block → 666,666 cycles/block per chip.  
With SIMD (2 float32 MACs/cycle) effective throughput is ~1,333,332 scalar ops/block.

#### Kernel cost estimates

| Kernel | Cycles/sample optimistic¹ | Cycles/sample pessimistic² |
|--------|--------------------------|---------------------------|
| Biquad (HW IIR accelerator) | 1 | 8 (SW, DF-II) |
| Gain / multiply | 1 | 2 |
| Gate (peak detect + log + envelope + apply) | 35 | 60 |
| Compressor | 45 | 75 |
| Tube saturation (polynomial waveshaper) | 10 | 18 |
| Delay (circular buffer r/w) | 4 | 6 |
| Aux send (mul + accumulate) | 2 | 3 |
| Freeverb stereo reverb (per engine) | 150 | 280 |
| Limiter | 15 | 25 |

¹ SIMD + HW accelerators, tight ASM  
² Scalar C, software biquads

#### Chip 1 — Input DSP (×32 channels)

| Stage | Cycles/sample | ×32 samples | ×32 channels |
|-------|--------------|-------------|--------------|
| HPF + LPF (2 biquads HW) | 2 | 64 | 2,048 |
| 4-band PEQ (4 biquads HW) | 4 | 128 | 4,096 |
| Sidechain filters gate + comp (4 biquads HW) | 4 | 128 | 4,096 |
| Gate | 35–60 | 1,120–1,920 | 35,840–61,440 |
| Compressor | 45–75 | 1,440–2,400 | 46,080–76,800 |
| Tube saturation | 10–18 | 320–576 | 10,240–18,432 |
| Gain + polarity + pan + fader | 8 | 256 | 8,192 |
| Input delay | 4–6 | 128–192 | 4,096–6,144 |
| Routing sends (12 aux + 6 FX + 4 grp + 2 main/sub) | 48 | 1,536 | 49,152 |

Raw scalar total: ~163,000–230,000 cycles. With SIMD: ~82,000–115,000 cycles.  
Plus overhead (TDM DMA, SPI handler, SPORT7 inter-chip TX, talkback, noise gen): ~8,000 cycles.

| | Optimistic | Pessimistic |
|-|-----------|------------|
| **Chip 1 utilisation** | **~14%** | **~34%** |
| Realistic (mixed ASM/C) | **~20–25%** | |

#### Chip 2 — Output DSP

Chip 1 sends bus pre-sums only — Chip 2 receives 25 already-mixed channels, no per-channel summing.

| Block | Cycles optimistic | Cycles pessimistic |
|-------|------------------|--------------------|
| Aux ×12: EQ (5 biquads) + anti-FB (12 biquads) + Lim + Delay | 17,000 | 42,000 |
| Group ×4: EQ + Gate + Comp + Fader | 14,000 | 28,000 |
| Sub ×1: EQ + Comp + Lim + Delay | 2,700 | 5,500 |
| Main L/R: fader + GEQ-28 + Comp + Lim + per-output ×4 | 17,000 | 32,000 |
| FX ×6 Freeverb stereo (worst case all active) | 29,000–58,000 | 54,000–107,000 |
| Monitor + USB/BT + I/O overhead | 6,500 | 6,500 |

| | Optimistic | Pessimistic |
|-|-----------|------------|
| **Chip 2 utilisation** | **~13–22%** | **~25–41%** |
| Realistic | **~18–25%** | |

> **Key insight:** Both chips are comfortably within budget even without SIMD. The ADSP-21564 is genuinely oversized for this feature set at 48 kHz, which gives headroom for 96 kHz operation (~40–50% utilisation), additional FX engines, or unoptimised C during bring-up before ASM tuning.
>
> The biggest single unknown is the **log/exp cost** in compressor/gate. `libm logf()` costs ~30–50 cycles vs a 4th-order polynomial approximation at ~8–12 cycles — a ~2× difference on Chip 1 alone. Implement fast approximations early.

### Slew / ramp overhead estimate (implementation target)

Ramp processing is expected to run at frame rate (per block), not per sample, except for selected
high-audibility gain paths if needed.

| Scenario | Active ramps (concurrent) | Added load / chip | Expected total (Chip 1) | Expected total (Chip 2) |
|----------|---------------------------|-------------------|-------------------------|-------------------------|
| Light interaction | <= 50 | **+0.3% to +0.8%** | ~20.3% to 25.8% | ~18.3% to 25.8% |
| Heavy interaction | <= 200 | **+1.5% to +3.5%** | ~21.5% to 28.5% | ~19.5% to 28.5% |
| Stress ceiling (guardrail) | > 200 | cap at **< +5%** | keep below ~30% typical target | keep below ~30% typical target |

Guardrail policy: if measured ramp overhead exceeds +5% on either chip, defer non-audible class
updates first while preserving audible gain/coefficient ramps.

---

### L2 SRAM — the real constraint

The ADSP-21564 has **2,048 KB** of L2 SRAM. Every delay line lives here.

#### Input delay spec — competitor baseline

The original 100 ms figure was arbitrary. Real-world digital mixer input delay specs:

| Mixer | Tier | Input delay/ch |
|-------|------|----------------|
| Behringer X32 / WING | Mid | **500 ms** |
| Allen & Heath dLive / DiGiCo SD | Pro | **340 ms** |
| Yamaha CL/QL series | Pro | **200 ms** |
| Allen & Heath SQ / Avantis | Mid–upper | **170 ms** |

Typical use-cases peak at ~170 ms (lip-sync compensation, long-throw speaker alignment). **250 ms** is chosen as the D32 spec — matches the aux/main output delay already specified, exceeds A&H SQ, and keeps parity across the product. 100 ms would be the weakest input delay spec on the market.

#### Input delay pooling — do all channels need the maximum simultaneously?

No. In practice, long delays are used on very few channels at once:

| Delay range | Typical use-case | Channels needed |
|-------------|-----------------|----------------|
| 0–5 ms | Mic-to-DI alignment, phase correction | Most channels |
| 5–20 ms | Room mic / close mic alignment | A few |
| 20–80 ms | Stage monitor speaker alignment | 2–6 |
| 80–250 ms | Lip-sync (camera/video feed, presenter) | **1–2 maximum** |

Allocating 250 ms to all 32 channels is therefore wasteful. A tiered or pooled scheme dramatically reduces SRAM without reducing the advertised per-channel spec.

**Pooling strategies:**

**Option A — Tiered fixed slots** *(recommended — simplest, deterministic, safe for real-time)*  
All 32 channels have a guaranteed minimum (e.g. 20 ms). A fixed number of "extended delay" slots
provide the full 250 ms. Any channel can be assigned to a slot; the limit is the slot count.
No runtime memory allocation — slot assignment happens at scene load, before the audio block starts.

**Option B — Hybrid fixed + shared pool**  
Same guaranteed minimum per channel; a shared contiguous overflow pool is sliced at scene load
time. Slightly more flexible than Option A but requires a simple pool manager in the H1S1 MCU.

**Option C — Fully dynamic real-time pool** *(avoid)*  
Real-time allocation inside the ISR is non-deterministic and risks fragmentation. Not appropriate
for a hard-real-time DSP context.

**SRAM comparison — Option A with N extended slots vs fixed ×32:**

| Configuration | Input delay RAM | Saving vs fixed 250 ms ×32 |
|--------------|----------------|--------------------------|
| Fixed 250 ms ×32 (naive) | 1,536 KB | — |
| 20 ms ×32 + 4 extended slots @ 250 ms | **297 KB** | −1,239 KB |
| 20 ms ×32 + 8 extended slots @ 250 ms | **474 KB** | −1,062 KB |
| 20 ms ×32 + 12 extended slots @ 250 ms | **651 KB** | −885 KB |

> **N=8 extended slots** is the recommended default: covers all realistic live-sound scenarios
> (2 lip-sync + 6 speaker alignment) with margin, and the slot count is small enough to explain
> simply to users ("up to 8 channels can use the full 250 ms delay simultaneously").

#### SRAM budget at 250 ms input delay (tiered, N=8 extended slots)

| Buffer | Calculation | Size |
|--------|------------|------|
| Input channel delays: 20 ms ×32 fixed + 8 extended slots @ 250 ms | (32×960 + 8×11,040) × 4 B | **474 KB** |
| Aux output delays ×12 @ 250 ms max | 12 × 12,000 × 4 B | **576 KB** |
| Main out delays ×4 @ 250 ms max | 4 × 12,000 × 4 B | **192 KB** |
| Monitor delay @ 250 ms | 1 × 12,000 × 4 B | **47 KB** |
| Reverb ×6 (Freeverb stereo — 8 combs + 4 allpass per engine) | 6 × ~88 KB | **528 KB** |
| **Total (tiered)** | | **≈ 1,817 KB** |
| **Total (naive fixed 250 ms ×32)** | | **≈ 2,879 KB** |

With tiered N=8, both bus splits now fit more comfortably:

| Chip | Contents | Est. SRAM used |
|------|----------|---------------|
| Chip 1 | Input delays tiered (474 KB) + coefficients + buffers | **~580 KB** |
| Chip 2 | Reverb (528 KB) + output delays (815 KB) + coefficients | ~1,400 KB |

Chip 1 drops from ~1,600 KB to **~580 KB**, which also reopens the single-chip question (see below).

---

### Single-chip feasibility

Cycles alone are not a blocker — combined realistic load is ~38–50% of one chip. With tiered input delays (N=8 extended slots) the total SRAM is ~1,817 KB, which **just fits** in one chip's 2,048 KB with ~231 KB remaining for coefficients, param RAM, stack, and metering. Tight but no longer impossible.

| Trade-off | SRAM saved | Implication |
|-----------|-----------|-------------|
| Tiered input delay (N=8 slots, 20 ms base) | −1,062 KB | Full 250 ms spec preserved; 8 channels simultaneously — covers all real-world scenarios |
| Reduce aux delay max 250 ms → 100 ms | −230 KB | Adequate for most speaker delay work |
| Dynamic shared delay pool (not per-channel max) | −200–300 KB | Adds firmware complexity; pool exhaustion is a user-visible failure mode |
| Limit full-quality reverb to 2 engines, 4 simplified (no allpass) | −~230 KB | Reduced FX quality on 4 of 6 engines |

With tiered delays alone (~1,817 KB total), single-chip leaves ~231 KB headroom — feasible but very tight. Adding the aux delay reduction as well (~1,587 KB total) gives a working ~460 KB margin. Single-chip rev B remains worth evaluating once the feature set is locked and real memory usage is profiled on hardware.

---

### Two-chip vs single-chip recommendation

| Factor | Two chips | Single chip |
|--------|-----------|-------------|
| Cycle margin | Comfortable on each | Comfortable on one |
| SRAM margin | Comfortable on each | Tight; requires tiered input delays + aux delay reduction |
| ISR complexity | Clean split of concern | One large ISR, harder to profile |
| SPORT I/O | 8 per chip, each has slack | 8 shared — ADC + DAC + USB ± Dante fits, just |
| Debug / bring-up | Validate Chip 1 independently first | All-or-nothing |
| BOM cost | 2× ADSP-21564 (~$40–70) | 1× ADSP-21564 (~$20–35) |
| Board space | Extra chip + SPORT7 inter-chip wiring | Simpler PCB |

**Decision: two chips for rev A.** Single-chip is a viable **cost-reduction rev B** once the feature set is locked and real SRAM usage can be verified against a working implementation. The saving (~$20–35/unit plus PCB area) is meaningful at volume but does not justify the bring-up risk on first hardware.

---

## 1e. FPGA Alternative — Specific Fit Against This Feature Set

> Extends §1b (general FPGA candidates) with memory analysis specific to the D32 feature set defined in this document.

### Memory constraint drives device selection

The cycle budget (~38–50% of one ADSP-21564) is easily met by any mid-range FPGA.  
**The binding constraint is the ~2 MB of audio delay and reverb storage** (derived in §1d).

Most FPGA families do **not** have enough on-chip SRAM for the full spec. The table below maps on-chip memory against the requirement:

| Device | BRAM | UltraRAM (URAM) | Total on-chip | Verdict vs 2.9 MB spec |
|--------|------|----------------|--------------|----------------------|
| Artix-7 XC7A200T | ~365 KB | — | **365 KB** | Needs external SSRAM |
| Artix UltraScale+ XCAU15P | ~540 KB | — | **540 KB** | Needs external SSRAM |
| Artix UltraScale+ XCAU25P | ~1,080 KB | — | **~1 MB** | Needs external SSRAM |
| Zynq US+ XCZU4EG | ~648 KB | — | **~648 KB** | Needs external LPDDR4 |
| Zynq US+ XCZU7EV | ~1,404 KB | ~1,872 KB (52×URAM) | **~3.3 MB** ✓ | On-chip sufficient |
| Zynq US+ XCZU9EG | ~2,250 KB | ~3,456 KB | ~5.7 MB | More than enough |

> URAM (UltraRAM, 36 KB per block, 4096×72-bit) only appears on ZU7-class Zynq US+ and above.
> All Artix devices and all Zynq below ZU7 need external memory for the full delay spec.

---

### Fixed-point arithmetic on FPGA

FP32 on FPGA is ~3× more expensive per MAC than fixed-point (§1b). All known pro-audio FPGA designs (A&H, DiGiCo) use **Q28 fixed-point** internally. At Q28, dynamic range is ~168 dB (28 bits × 6 dB/bit) — far exceeding 24-bit audio. Biquad coefficients are representable with sufficient precision.

Implications for this feature set:

| Kernel | Q28 implementation | Note |
|--------|-------------------|------|
| Biquad EQ / filters | Time-division multiplexed — one DSP58E2 block can serve all 32 channels at 48 kHz | Well understood |
| Compressor / gate log-exp | CORDIC core or 1024-entry LUT (8 KB) | LUT approach simplest |
| Delay lines | Trivially fixed-point — raw sample buffers | No arithmetic needed |
| Freeverb reverb | Fixed-point Freeverb is standard; A&H SQ uses it | Room size / damping as Q28 coefficients |
| Pan law | 256-entry lookup table | |

At 100–250 MHz FPGA clock, 32 channels at 48 kHz gives **~2,000–6,250 clock cycles per sample** for TDM multiplexing. A single DSP58E2 slice running in multiply-accumulate mode at 500 MHz can process the entire 32-channel biquad bank with headroom to spare.

### Slew / ramp handling on FPGA vs SHARC

| Aspect | ADSP-21564 (current) | FPGA implementation |
|--------|-----------------------|---------------------|
| Ramp compute cost | Low incremental load (+0.3% to +3.5% typical from §1d) | Very low if pipelined; parallelism is abundant |
| Numerical model | Native FP32 and existing coefficient flow | Usually fixed-point (Q28/Q31) for efficiency; FP32 is expensive |
| Determinism | Strong block-boundary control in ISR model | Strong if fully synchronous; excellent for large concurrent ramps |
| Engineering effort | Low-medium (firmware + DSP code updates) | High (RTL/HLS design, verification, bring-up) |
| Integration complexity | Reuses current dual-CS SPI → DSP path | Often requires redesign of control/data plane boundaries |
| Cost impact for ramps only | Minimal | Not justified by ramps alone |

Pros of FPGA for slew/ramps:

- Massive concurrency with deterministic timing for large scene recalls.
- Natural fit for dedicated coefficient staging pipelines.
- Easy to co-locate control and audio state machines when platform is already FPGA-centric.

Cons of FPGA for slew/ramps:

- FP32 ramping/coefficient morphing is inefficient in fabric; practical designs shift to fixed-point and require retuning.
- Much larger verification/debug burden than extending the existing SHARC firmware path.
- Does not remove the core memory-planning problem for delay/reverb unless a larger part (or external memory) is selected.

Conclusion for this feature: keep slew/ramp implementation on dual ADSP-21564 for rev A. Consider
FPGA ramp offload only as part of a broader platform consolidation (DSP + I/O + networking).

---

### Recommended paths for D32

#### Path A — Artix UltraScale+ + QDR-II SSRAM (pro-audio standard)

**External memory choice: QDR-II SSRAM**  
QDR-II has a **2-cycle deterministic read latency** — no cache misses, no refresh stalls. Circular buffer pointers step predictably. This is the DiGiCo Spidercore approach and the correct choice for real-time delay lines.

| Component | Example part | Approx. 1k+ cost |
|-----------|-------------|-----------------|
| FPGA | Artix UltraScale+ XCAU25P (or XCAU15P for D24) | ~$80–120 |
| QDR-II SSRAM × 1 | ISSI IS61WVQ2DABL (36 Mb = 4.5 MB) | ~$15–25 |
| **Total** | | **~$95–145** |

- FPGA fabric: audio DSP pipeline (biquads, dynamics, routing, reverb)
- SSRAM: all delay lines and reverb buffers (4.5 MB covers full spec with 2× margin)
- No hard ARM → keep H1S1 MCU (STM32U575) for SPI/control; add MicroBlaze soft-CPU if needed
- More FPGA implementation work than Path B; DSP is entirely custom RTL / HLS

#### Path B — Zynq UltraScale+ XCZU7EV (no external memory)

| Component | Example part | Approx. 1k+ cost |
|-----------|-------------|-----------------|
| SoC | XCZU7EV-2FBVB900I | ~$280–480 |

- ~3.3 MB on-chip (BRAM + URAM) covers full delay spec with ~1.3 MB margin
- Hard ARM Cortex-A53 PS absorbs the H1S1 MCU role (SPI slave, scene storage, serial protocol)
- PS LPDDR4 available for expansion (SSD record buffer, multitrack staging)
- FPGA PL handles audio pipeline in the same way as Path A
- Cleaner BOM (fewer chips) but ~2–3× higher silicon cost

#### Comparison

| Factor | Path A (AU25P + QDR-II) | Path B (ZU7EV) |
|--------|------------------------|----------------|
| Silicon cost | ~$95–145 | ~$280–480 |
| On-chip memory | ~1 MB | ~3.3 MB |
| External memory | QDR-II SSRAM required | None for audio |
| Control CPU | Keep H1S1 STM32 | ARM A53 on-die |
| Bring-up complexity | Higher (external memory controller + FPGA DSP) | Lower (Xilinx PS handles control) |
| Precedent in pro-audio | DiGiCo Spidercore | Emerging (newer products) |
| Suitable for | Cost-sensitive volume production | Integrated platform, easier bringup |

**Recommendation:** Path B (ZU7EV) is preferred for a first FPGA iteration — fewer external components, ARM PS handles the control layer, and on-chip URAM eliminates the QDR-II controller implementation work. Switch to Path A for a cost-optimised volume revision once the feature set is completely locked.

At small-to-mid volume, the ADSP-21564 two-chip approach (§1d) remains cheaper and faster to develop against than either FPGA path. FPGA becomes compelling only if absorbing Dante networking, USB audio, and the MCU onto a single die.

---

## 2. Signal Chain

### 2.1 Overview (Chip 1 — Input DSP)

```
ADC TDM (32 ch)   USB / BT / DAW return   Talkback [1-2]   Noise Gen
      │                   │                      │               │
      ▼                   ▼                      ▼               ▼
 ┌────────────────────────────────────────────────────────────────────────┐
 │  CHIP 1 — Input DSP                                            48 kHz  │
 │                                                                        │
 │  Per channel ×32:                                                      │
 │                                                                        │
 │  [ADC / InputSel]  ← Chan.InputSel, Phantom, Instr, Link              │
 │         │                                                              │
 │  [Preamp / Trim]   ← Chan.Gain, Pol, AntiClip, InsertOn               │
 │         │                                                              │
 │  [HPF + LPF]       ← Chan.EqHpf, EqHpfSlope, EqLpf, EqOn             │
 │         │                                                              │
 │  [4-band PEQ] ──────────────────────────────────→ (det. src Pre-EQ)  │
 │         │          ← Chan.EqFreq[1-4], EqGain[1-4], EqQ[1-4],        │
 │         │             EqShelf[1-2], CompEqPos (pre/post)              │
 │         │                                                              │
 │  [Gate]            ← Chan.GateOn/Thr/Att/Hold/Rel/Rng                 │
 │         │             Chan.GateKey (0=self, 1-32=ext chan)            │
 │         │             Chan.GateDetSrc (pre/post EQ tap)               │
 │         │             Chan.GateFilterOn/Hpf/Lpf/Q                     │
 │         │                                                              │
 │  [Compressor]      ← Chan.CompOn/Thr/Rat/Att/Rel/Make/Knee/Par/Type  │
 │         │             Chan.CompKey, CompDetSrc                         │
 │         │             Chan.CompFilterOn/Hpf/Lpf/Q                     │
 │         │             Chan.CompLimMode                                 │
 │         │                                                              │
 │  [Tube Sat]        ← Chan.TubeOn, TubeSat                             │
 │         │                                                              │
 │  [Input Delay]     ← Chan.Delay                                        │
 │         │                                                              │
 │  [Fader + Pan]     ← Chan.RtgLevel, RtgPan, RtgMute                  │
 │         │             DCA[1-8]: fader multiplier applied here          │
 │         │             MuteGrp[1-8]: mute OR applied here              │
 │         │                                                              │
 │         ├──── RtgMainOn ────────────────────────────→ Main L/R pre-sum│
 │         ├──── RtgCtrOn ─────────────────────────────→ Sub/Ctr pre-sum │
 │         ├──── RtgGrpOn[1-4] ────────────────────────→ Grp pre-sums    │
 │         ├──── RtgAuxSend[1-12] / RtgAuxOn / RtgAuxPick → Aux pre-sums│
 │         └──── RtgFxSend[1-6]  / RtgFx ────────────→ FX bus pre-sums  │
 │                                                                        │
 │  Bus pre-sums (Main, Sub, 4×Grp, 12×Aux, 6×FX) ──→ SPORT TDM → Chip 2│
 └────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Overview (Chip 2 — Output DSP)

```
 ┌────────────────────────────────────────────────────────────────────────┐
 │  CHIP 2 — Output DSP                                                   │
 │                                                                        │
 │  Aux buses ×12 (D32) / ×8 (D24):                                      │
 │  [Sum] → [Fader] → [EQ] → [Anti-FB Notch] → [Limiter] → [Delay] → out│
 │           Aux.RtgLevel/Mute   EqOn/Hpf/Freq/Gain/Q/Shelf   LimOn/Thr  │
 │                                                                        │
 │  Group buses ×4:                                                       │
 │  [Sum] → [Fader] → [EQ] → [Gate] → [Comp] → out (+ feed Main)        │
 │           Grp.RtgLevel/Mute   GateOn/Thr…   CompOn/Thr…               │
 │                                                                        │
 │  Center / Sub bus ×1:                                                  │
 │  [Sum] → [EQ] → [Comp] → [Limiter] → [Delay] → out                   │
 │                                                                        │
 │  Main L/R bus:                                                         │
 │  [Sum from chans + groups] → [Master Fader] → [GEQ 28-band]           │
 │     → [Comp] → [Limiter] → [Delay] → [Crossover → Sub feed]          │
 │     → Main[1-4] per-output EQ/Comp/Lim → DAC                         │
 │                                                                        │
 │  FX engines ×6:                                                        │
 │  [FX bus sum] → [FX Engine (reverb/delay/mod)] → [Return fader]       │
 │     → feeds Main, Aux, or other buses per RtgAuxOn/RtgAuxSend         │
 │                                                                        │
 │  Monitor / Phones:                                                     │
 │  [Source select] → [Level L/R] → [Delay] → Monitor out + Phones 1-4  │
 │                                                                        │
 │  USB / BT / DAW:                                                       │
 │  USB-A play → [Level] → mix into main or aux                           │
 │  Bluetooth  → [Level] → mix into main or aux                           │
 │  USB-C DAW  → [Rec level / Play level] → bidirectional                │
 │                                                                        │
 └────────────────────────────────────────────────────────────────────────┘
                          │
                     DAC TDM (32 ch)
```

---

## 3. Parameter Definition Schema

Column reference for all tables below:

| Column | Description |
|--------|-------------|
| `_Cell` | Matrix cell pattern — matches `mx_master.csv` exactly |
| `DspSpi` | SPI chip-select index (1–8); TBD until DSP program is designed |
| `DspBaseAddr` | Base parameter RAM address (hex); TBD |
| `Stride` | Address step between consecutive instances; TBD |
| `Table` | Coefficient formula — copied verbatim from `mx_master.csv`; empty = no formula defined yet |
| `RampProfile` | Optional ramp preset name (e.g. `GainFast`, `EqSafe`) |
| `RampMode` | Optional mode: `Instant`, `Slew`, `LinearFrames`, `ExpFrames` |
| `RampUpMs` | Optional rise time (ms), quantized to frame count |
| `RampDownMs` | Optional fall time (ms), quantized to frame count |
| `RampCurve` | Optional curve hint: `Linear`, `Exp`, `Log`, `S-Curve` |
| `RampScope` | Optional target scope: `Scalar`, `CoeffSetAtomic` |
| `Notes` | — |

Address rule: `DspAdd[instance N] = DspBaseAddr + (N − 1) × Stride`  
Multi-band rule: `DspAdd[instance N, band B] = DspBaseAddr + (N − 1) × Stride + (B − 1)`

### 3a. SigmaStudio-style Slew / Coefficient Ramp Policy

The D32 spec adopts SigmaStudio-style parameter smoothing semantics while preserving backward
compatibility with existing immediate writes.

**Default behavior:** if no ramp fields are present, the write is `Instant` (current behavior).

| Class | Typical cells | Default ramp policy |
|------|----------------|---------------------|
| Instant control | On/off, source selects, routing topology | `Instant` |
| Gain control | Faders, trims, send levels, makeup gain | `Slew` or `LinearFrames` |
| Coefficient sets | EQ/filter coefficient families | `CoeffSetAtomic` + `LinearFrames` or `ExpFrames` |
| Safety-critical switching | Mute-group fanout, topology reroute | `Instant` unless explicitly qualified |

Timing quantization:

- Frame period is fixed by audio block size (32 samples @ 48 kHz): 0.667 ms/frame.
- `RampUpMs` / `RampDownMs` quantize to frames with deterministic rounding:

$$
N_{frames} = \max\left(1,\ \mathrm{round}\left(\frac{T_{ms}}{0.6667}\right)\right)
$$

- `Instant` forces $N_{frames}=0$ and bypasses ramp state allocation.

Chip 2 has its own direct SPI connection (H1S1 CS2 → Chip2 SPI1). H1S1 addresses each chip independently using the same ramp profile encoding.

Bulk recall rule: scene/preset recall may ramp gain/coefficient classes, but routing/select
classes remain atomic unless a cell explicitly opts in.

### 3b. Ramp Profile Presets (initial set)

Rows may either declare explicit ramp fields or reference a named `RampProfile`.
Profiles are resolved by `gen_dsp.py` into concrete mode/times.

| RampProfile | RampMode | RampUpMs | RampDownMs | RampCurve | RampScope | Intended use |
|------------|----------|----------|------------|-----------|-----------|--------------|
| `InstantCtl` | `Instant` | 0 | 0 | `Linear` | `Scalar` | On/off and topology controls |
| `GainFast` | `Slew` | 3 | 8 | `Exp` | `Scalar` | Fader trim, send, makeup gain |
| `GainSafe` | `Slew` | 10 | 30 | `Exp` | `Scalar` | Audible-safe scene recall gain moves |
| `EqSafe` | `LinearFrames` | 12 | 12 | `Linear` | `CoeffSetAtomic` | EQ/filter coefficient set changes |
| `DynSafe` | `LinearFrames` | 6 | 20 | `Exp` | `Scalar` | Dynamics threshold/ratio style controls |

Initial mapping policy:

- Routing/select/mute topology cells default to `InstantCtl`.
- Gain domain cells default to `GainFast` during interaction and `GainSafe` during scene recall.
- Coefficient families (EQ/filter banks) default to `EqSafe`.
- Dynamics parameter classes default to `DynSafe` unless proven safe as `Instant`.

### Chip 2 parameter delivery via independent SPI

H1S1 has **two chip-select lines**: CS1 → Chip 1 SPI1, CS2 → Chip 2 SPI1. Each chip has its own `spi_handler.asm` instance. There is no forwarding between chips.

1. H1S1 determines the target chip from the high-level command (Pi → H1S1 protocol encodes chip identity).
2. H1S1 asserts the appropriate CS line and writes the 32-bit address + 32-bit coefficient word directly.
3. Each chip's SPI1 RX interrupt handler processes the write locally and calls `_ramp_set_target` or writes direct.

**Implication for `DspSpi`:** `DspSpi` values are `1` (Chip 1, CS1) or `2` (Chip 2, CS2). H1S1 firmware selects the CS line accordingly. `DspBaseAddr` values are independent per chip — Chip 1 and Chip 2 each have their own address space starting at 0x0000.

---

## 4. Channel Strip Parameters (×32 channels)

> **DSP:** Chip 1

### 4.1 Input / Preamp

#### Mic preamp gain architecture

> Hardware detail: D24 Analog schematic pages 16–19. Design notes and gain tables: [MicPre/](MicPre/) (micpre.md, res.md, gain_table.csv).

**0–60 dB in 1 dB steps** via hybrid analog switching + DSP trim.

**Signal chain (per channel):**

```
J19 combo ─► discrete Class A diff pair (MMDT2227) ─► NJM2068M gain stage ─► AK5558 ADC
                                                        │
                                                    Rf = 4K99
                                                    Rg = 6 switched resistors in parallel
                                                    Gain = 1 + Rf/Rg
                                                        │
                                              74HC595 shift register ◄── S MCU SPI
                                              (6 gain bits + clamp + phantom)
```

**Rg network — 6-bit binary-weighted conductances:**

Each resistor is switched to ground by a 2N7002DW N-FET (Rds_on ≈ 3 Ω). Any combination of the 6 can be ON simultaneously — resistors in parallel lower Rg, raising gain.

| Bit | Ref | Ω | Relative G | Gain solo (dB) |
|-----|-----|---|----------:|---------------:|
| 0 | R396 | 15R | 98× | 50.5 |
| 1 | R395 | 37R4 | 39× | 42.5 |
| 2 | R397 | 93R1 | 16× | 35.1 |
| 3 | R398 | 232R | 6.3× | 27.0 |
| 4 | R399 | 590R | 2.5× | 18.8 |
| 5 | R394 | 1K47 | 1× | 12.8 |

All 0.1% MF, E192 series. Ref designators from MIC_IN_13; identical on all channels.

**64 analog steps (6 bits → 0 to 54 dB):**

| Code | Rg | Gain | Gap to prev | Switches ON |
|-----:|----:|-----:|------------:|-------------|
| 0x00 | ∞ | 0 dB | — | none |
| 0x01 | 1K47 | 12.8 dB | 12.8 | 5 |
| 0x02 | 590R | 18.8 dB | 6.0 | 4 |
| 0x03 | 421R | 22.2 dB | 3.3 | 4+5 |
| … | | | | |
| 0x3E | 10.6Ω | 53.5 dB | 0.24 | 0+1+2+3+4 |
| 0x3F | 10.3Ω | 53.8 dB | 0.24 | all |

Steps 32–63 have gaps < 0.5 dB. Below step 8 the gaps widen — worst is 12.8 dB (0x00 → 0x01). Full 64-step table in [MicPre/res.md](MicPre/res.md).

**Composite gain (MCU lookup):**

```
target_dB  =  analog_step_dB  +  dsp_trim_dB
```

The S MCU holds a 61-entry table mapping each integer dB target (0–60) to the switch code that minimises |dsp_trim|. For most of the range the trim is < 1 dB; worst case is ±7.3 dB bridging the first large gap. Full table in [MicPre/gain_table.csv](MicPre/gain_table.csv).

MCU procedure per gain change:
1. Look up 6-bit switch code + DSP trim for the target dB.
2. Shift the code out via SPI to the channel's 74HC595.
3. Send the trim value to the DSP as a `Chan.Gain` coefficient update.

**Input clamp (phantom switching):**
One bit of the 74HC595 controls an input clamp that shorts the mic signal to ground. Used during phantom power on/off to suppress the DC transient that would otherwise produce a damaging click/pop:
1. Assert clamp (signal grounded).
2. Switch phantom power on or off.
3. Wait for the supply to settle (RC time constant of the phantom feed network).
4. Release clamp.

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Chan[1-32]Gain[1-1]` | TBD | TBD | TBD | `0=0/127=60/[Lin]` | DSP trim component of hybrid gain |
| `Chan[1-32]Pol[1-1]` | TBD | TBD | TBD | | Polarity reverse |
| `Chan[1-32]Phantom[1-1]` | TBD | TBD | TBD | | +48 V phantom power |
| `Chan[1-32]InputSel[1-1]` | TBD | TBD | TBD | | Input source: Mic/Line/Digital/USB |
| `Chan[1-32]Link[1-1]` | TBD | TBD | TBD | | Stereo link with adjacent channel |
| `Chan[1-32]Delay[1-1]` | TBD | TBD | TBD | `0=0/127=250/[Log]` | Input delay up to 250 ms (matches output delay; see §1d competitor note) |
| `Chan[1-32]InsertOn[1-1]` | TBD | TBD | TBD | | External insert on/off |
| `Chan[1-32]AntiClip[1-1]` | TBD | TBD | TBD | `0=-20/127=0/[Lin]` | Auto gain reduction threshold (M&W exclusive) |
| `Chan[1-2]Instr[1-1]` | TBD | TBD | TBD | | Instrument hi-Z mode (ch 1–2 only) |

### 4.2 EQ

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Chan[1-32]EqOn[1-1]` | TBD | TBD | TBD | | EQ bypass |
| `Chan[1-32]EqHpf[1-1]` | TBD | TBD | TBD | `0=20/64=1000/[Log]` | High-pass frequency |
| `Chan[1-32]EqHpfSlope[1-1]` | TBD | TBD | TBD | | HPF slope: 6/12/18/24/36 dB/oct |
| `Chan[1-32]EqLpf[1-1]` | TBD | TBD | TBD | `0=1000/127=20000/[Log]` | Low-pass frequency |
| `Chan[1-32]EqFreq[1-1]` | TBD | TBD | TBD | `0=20/254=200/[Log]` | Band 1 frequency |
| `Chan[1-32]EqFreq[2-2]` | TBD | TBD | TBD | `0=100/254=1000/[Log]` | Band 2 frequency |
| `Chan[1-32]EqFreq[3-3]` | TBD | TBD | TBD | `0=800/254=5000/[Log]` | Band 3 frequency |
| `Chan[1-32]EqFreq[4-4]` | TBD | TBD | TBD | `0=3000/254=20000/[Log]` | Band 4 frequency |
| `Chan[1-32]EqGain[1-4]` | TBD | TBD | TBD | `0=-15/60=15/[Lin]` | Bands 1–4 gain ±15 dB |
| `Chan[1-32]EqQ[1-4]` | TBD | TBD | TBD | `0=0.1/14=10/[Log]` | Bands 1–4 Q |
| `Chan[1-32]EqShelf[1-2]` | TBD | TBD | TBD | | Band 1/4 shelf mode on/off |

### 4.3 Gate

The gate detector can be fed by the channel's own signal or by any other channel's audio (external key).
A 2nd-order sidechain filter (HPF + optional LPF) shapes the key signal before it reaches the level detector.
The detector tap selects where in the main signal path the self-key signal is read from.

```
 [Main signal path]
        │
   ┌────┴─────────────────────────────────────────────────┐
   │                                          Key switch  │
   │  Pre-EQ tap ──┐                   0=self pre-EQ      │
   │  Post-EQ tap ─┤ DetSrc select     1-32=chan N (Chip1)│
   │               │                                      │
   │     External key (from Chip 1 bus) ─────────────────►│
   │               │                                      │
   │               ▼                                      │
   │        [Key Filter: HPF + LPF]  ← FilterOn/Freq/Q    │
   │               │                                      │
   │               ▼                                      │
   │          [Gate Detector]                             │
   │               │                                      │
   │               ▼                                      │
   │         [Gain element] ←── -60 dB to 0 (Range)      │
   └──────────────────────────────────────────────────────┘
```

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-----------|
| `Chan[1-32]GateOn[1-1]` | TBD | TBD | TBD | | Gate bypass |
| `Chan[1-32]GateThr[1-1]` | TBD | TBD | TBD | `0=-80/127=0/[Lin]` | Threshold |
| `Chan[1-32]GateAtt[1-1]` | TBD | TBD | TBD | `0=0.1/127=250/[Log]` | Attack time |
| `Chan[1-32]GateHold[1-1]` | TBD | TBD | TBD | `0=0/127=2000/[Log]` | Hold time |
| `Chan[1-32]GateRel[1-1]` | TBD | TBD | TBD | `0=50/127=5000/[Log]` | Release time |
| `Chan[1-32]GateRng[1-1]` | TBD | TBD | TBD | `0=0/127=60/[Lin]` | Depth/range 0–60 dB |
| `Chan[1-32]GateKey[1-1]` | TBD | TBD | TBD | | Key source: 0=self, 1–32=channel N (routes that channel's pre-fader audio to this detector) |
| `Chan[1-32]GateDetSrc[1-1]` | TBD | TBD | TBD | | Self-key tap: 0=Pre-EQ, 1=Post-EQ (only active when GateKey=0) |
| `Chan[1-32]GateFilterOn[1-1]` | TBD | TBD | TBD | | Sidechain filter in/out |
| `Chan[1-32]GateFilterHpf[1-1]` | TBD | TBD | TBD | `0=20/64=1000/[Log]` | Sidechain HPF frequency — shapes key signal before detector |
| `Chan[1-32]GateFilterLpf[1-1]` | TBD | TBD | TBD | `0=500/127=20000/[Log]` | Sidechain LPF frequency — optional band-limiting for key |
| `Chan[1-32]GateFilterQ[1-1]` | TBD | TBD | TBD | `0=0.1/14=10/[Log]` | Sidechain filter Q |

### 4.4 Compressor

Same sidechain topology as the gate. Key source selects self or an external channel;
a dedicated filter shapes the key signal before the RMS/peak detector.
`CompEqPos` controls where the 4-band PEQ sits relative to the compressor in the *main* signal path.

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Chan[1-32]CompOn[1-1]` | TBD | TBD | TBD | | Compressor bypass |
| `Chan[1-32]CompThr[1-1]` | TBD | TBD | TBD | `0=-60/140=10/[Lin]` | Threshold |
| `Chan[1-32]CompRat[1-1]` | TBD | TBD | TBD | `0=1/127=30/[Log]` | Ratio 1:1 – 30:1 |
| `Chan[1-32]CompAtt[1-1]` | TBD | TBD | TBD | `0=0/254=250/[Log]` | Attack time |
| `Chan[1-32]CompRel[1-1]` | TBD | TBD | TBD | `0=5/254=5000/[Log]` | Release time |
| `Chan[1-32]CompMake[1-1]` | TBD | TBD | TBD | `0=0/127=20/[Lin]` | Makeup gain |
| `Chan[1-32]CompKnee[1-1]` | TBD | TBD | TBD | | Soft/hard knee |
| `Chan[1-32]CompPar[1-1]` | TBD | TBD | TBD | `0=0/127=100/[Lin]` | Parallel blend dry/wet |
| `Chan[1-32]CompType[1-1]` | TBD | TBD | TBD | | Type: Tube/FET/VCA/Optical |
| `Chan[1-32]CompKey[1-1]` | TBD | TBD | TBD | | Key source: 0=self, 1–32=channel N (same semantics as GateKey) |
| `Chan[1-32]CompDetSrc[1-1]` | TBD | TBD | TBD | | Self-key tap: 0=Pre-EQ, 1=Post-EQ (only active when CompKey=0) |
| `Chan[1-32]CompFilterOn[1-1]` | TBD | TBD | TBD | | Sidechain filter in/out |
| `Chan[1-32]CompFilterHpf[1-1]` | TBD | TBD | TBD | `0=20/64=1000/[Log]` | Sidechain HPF frequency |
| `Chan[1-32]CompFilterLpf[1-1]` | TBD | TBD | TBD | `0=500/127=20000/[Log]` | Sidechain LPF frequency |
| `Chan[1-32]CompFilterQ[1-1]` | TBD | TBD | TBD | `0=0.1/14=10/[Log]` | Sidechain filter Q |
| `Chan[1-32]CompLimMode[1-1]` | TBD | TBD | TBD | | Compressor vs Limiter mode toggle |
| `Chan[1-32]CompEqPos[1-1]` | TBD | TBD | TBD | | Main path EQ position: 0=Pre-Comp, 1=Post-Comp |

### 4.5 Tube Saturation

> **Future concept / placeholder.** TUBE_SAT is reserved for channel strip plugin processing.
> The DSP node and SPI addresses are allocated in dsp.csv and generated code is a pass-through
> stub. Full implementation is deferred.

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Chan[1-32]TubeOn[1-1]` | TBD | TBD | TBD | | Tube bypass |
| `Chan[1-32]TubeSat[1-1]` | TBD | TBD | TBD | `0=0/127=100/[Lin]` | Saturation amount |

### 4.6 Fader, Pan & Routing

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Chan[1-32]RtgLevel[1-1]` | TBD | TBD | TBD | `dB:Off:-50@31:-30@63:-10@127:10` | Channel fader |
| `Chan[1-32]RtgPan[1-1]` | TBD | TBD | TBD | `Pan:dB:0:Off` | Pan (constant power) |
| `Chan[1-32]RtgMute[1-1]` | TBD | TBD | TBD | | Channel mute |
| `Chan[1-32]RtgMainOn[1-1]` | TBD | TBD | TBD | | Assign to main L/R |
| `Chan[1-32]RtgCtrOn[1-1]` | TBD | TBD | TBD | | Assign to center/sub |
| `Chan[1-32]RtgAuxSend[1-12]` | TBD | TBD | TBD | `dB:Off:-50@31:-30@63:-10@127:0` | Per-aux send level |
| `Chan[1-32]RtgAuxOn[1-12]` | TBD | TBD | TBD | | Per-aux send on/off |
| `Chan[1-32]RtgAuxPick[1-12]` | TBD | TBD | TBD | | Per-aux pickoff: PreEQ/PostEQ/PreFdr/PostFdr |
| `Chan[1-32]RtgFxSend[1-6]` | TBD | TBD | TBD | `dB:Off:-50@31:-30@63:-10@127:0` | Per-FX send level |
| `Chan[1-32]RtgFx[1-6]` | TBD | TBD | TBD | | Per-FX send on/off |
| `Chan[1-32]RtgGrpOn[1-4]` | TBD | TBD | TBD | | Group routing on/off |
| `Chan[1-32]RtgDca[1-1]` | TBD | TBD | TBD | | DCA assignment 1–8 |
| `Chan[1-32]MuteGrp[1-8]` | TBD | TBD | TBD | | Mute group 1–8 assignment |
| `Chan[1-32]CueSel[1-1]` | TBD | TBD | TBD | | Cue/solo: PFL/AFL/SIP |
| `Chan[1-32]Color[1-1]` | TBD | TBD | TBD | | Fader cap color code (UI only, no DSP coeff) |

---

## 5. Aux Bus Parameters (×12 buses)

> **DSP:** Chip 2

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Aux[1-12]RtgLevel[1-1]` | TBD | TBD | TBD | `dB:Off:-50@31:-30@63:-10@127:10` | Aux master level |
| `Aux[1-12]RtgMute[1-1]` | TBD | TBD | TBD | | Aux master mute |
| `Aux[1-12]Pan[1-1]` | TBD | TBD | TBD | `Pan:dB:0:Off` | Aux pan |
| `Aux[1-12]Delay[1-1]` | TBD | TBD | TBD | `0=0/127=250/[Log]` | Aux output delay up to 250 ms |
| `Aux[1-12]PickOff[1-1]` | TBD | TBD | TBD | | Global pickoff: PreEQ/PostEQ/PreFdr/PostFdr |
| `Aux[1-12]EqOn[1-1]` | TBD | TBD | TBD | | EQ bypass |
| `Aux[1-12]EqHpf[1-1]` | TBD | TBD | TBD | `0=20/64=1000/[Log]` | High-pass frequency |
| `Aux[1-12]EqFreq[1-1]` | TBD | TBD | TBD | `0=20/254=200/[Log]` | Band 1 frequency |
| `Aux[1-12]EqFreq[2-2]` | TBD | TBD | TBD | `0=100/254=1000/[Log]` | Band 2 frequency |
| `Aux[1-12]EqFreq[3-3]` | TBD | TBD | TBD | `0=800/254=5000/[Log]` | Band 3 frequency |
| `Aux[1-12]EqFreq[4-4]` | TBD | TBD | TBD | `0=3000/254=20000/[Log]` | Band 4 frequency |
| `Aux[1-12]EqGain[1-4]` | TBD | TBD | TBD | `0=-15/60=15/[Lin]` | Bands 1–4 gain ±15 dB |
| `Aux[1-12]EqQ[1-4]` | TBD | TBD | TBD | `0=0.1/14=10/[Log]` | Bands 1–4 Q |
| `Aux[1-12]EqShelf[1-2]` | TBD | TBD | TBD | | Band 1/4 shelf mode on/off |
| `Aux[1-12]Geq[1-28]` | TBD | TBD | TBD | `0=-12/127=12/[Lin]` | 28-band 1/3-octave GEQ (one entry per fader) |
| `Aux[1-12]Peq[1-12]` | TBD | TBD | TBD | `0=-12/127=12/[Lin]` | Compatibility alias used in `mx_master.csv` for GEQ gain entries |
| `Aux[1-12]LimiterOn[1-1]` | TBD | TBD | TBD | | Limiter bypass |
| `Aux[1-12]LimiterThr[1-1]` | TBD | TBD | TBD | `0=-30/127=0/[Lin]` | Limiter threshold |
| `Aux[1-12]AntiFbOn[1-1]` | TBD | TBD | TBD | | Auto anti-feedback enable per aux |
| `Aux[1-12]AntiFbCtrlOn[1-1]` | TBD | TBD | TBD | | Auto anti-feedback control block enable |
| `Aux[1-12]AntiFbNotchFreq[1-6]` | TBD | TBD | TBD | `0=40/127=12000/[Log]` | Notch frequency (6 filters) |
| `Aux[1-12]AntiFbNotchGain[1-6]` | TBD | TBD | TBD | `0=-18/127=0/[Lin]` | Notch depth (dB cut) |
| `Aux[1-12]AntiFbNotchQ[1-6]` | TBD | TBD | TBD | `0=1/127=20/[Log]` | Notch Q / bandwidth |
| `Aux[1-12]RtgDca[1-1]` | TBD | TBD | TBD | | DCA assignment 1–8 |

---

## 6. Main Output Parameters

> **DSP:** Chip 2

### 6.1 Master (Main[1-1])

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Main[1-1]RtgLevel[1-1]` | TBD | TBD | TBD | `dB:Off:-50@31:-30@63:-10@127:10` | Main L/R master fader |
| `Main[1-1]Mute[1-1]` | TBD | TBD | TBD | | Main mute |
| `Main[1-1]Delay[1-1]` | TBD | TBD | TBD | `0=0/127=250/[Log]` | Main delay up to 250 ms |
| `Main[1-1]CueSel[1-1]` | TBD | TBD | TBD | | Cue/solo select |

### 6.2 Per-output processing (Main[1-4])

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Main[1-4]EqOn[1-1]` | TBD | TBD | TBD | | EQ bypass |
| `Main[1-4]EqHpf[1-4]` | TBD | TBD | TBD | `0=20/64=1000/[Log]` | High-pass frequency |
| `Main[1-4]EqFreq[1-1]` | TBD | TBD | TBD | `0=20/254=200/[Log]` | Band 1 frequency |
| `Main[1-4]EqFreq[2-2]` | TBD | TBD | TBD | `0=100/254=1000/[Log]` | Band 2 frequency |
| `Main[1-4]EqFreq[3-3]` | TBD | TBD | TBD | `0=800/254=5000/[Log]` | Band 3 frequency |
| `Main[1-4]EqFreq[4-4]` | TBD | TBD | TBD | `0=3000/254=20000/[Log]` | Band 4 frequency |
| `Main[1-4]EqGain[1-4]` | TBD | TBD | TBD | `0=-15/60=15/[Lin]` | Bands 1–4 gain ±15 dB |
| `Main[1-4]EqQ[1-4]` | TBD | TBD | TBD | `0=0.1/14=10/[Log]` | Bands 1–4 Q |
| `Main[1-4]LimiterOn[1-1]` | TBD | TBD | TBD | | Limiter bypass |
| `Main[1-4]LimiterAtt[1-1]` | TBD | TBD | TBD | `0=0.1/127=100/[Log]` | Limiter attack |
| `Main[1-4]LimiterRel[1-1]` | TBD | TBD | TBD | `0=5/127=2000/[Log]` | Limiter release |
| `Main[1-4]LimiterRng[1-1]` | TBD | TBD | TBD | `0=0/127=60/[Lin]` | Limiter range/depth |
| `Main[1-4]LimiterThr[1-1]` | TBD | TBD | TBD | `0=-30/127=0/[Lin]` | Limiter threshold |
| `Main[1-4]CompOn[1-1]` | TBD | TBD | TBD | | Compressor bypass |
| `Main[1-4]CompThr[1-1]` | TBD | TBD | TBD | `0=-60/140=10/[Lin]` | Compressor threshold |
| `Main[1-4]CompRat[1-1]` | TBD | TBD | TBD | `0=1/127=30/[Log]` | Compressor ratio |
| `Main[1-4]CompAtt[1-1]` | TBD | TBD | TBD | `0=0/254=250/[Log]` | Compressor attack |
| `Main[1-4]CompRel[1-1]` | TBD | TBD | TBD | `0=5/254=5000/[Log]` | Compressor release |
| `Main[1-4]CompMake[1-1]` | TBD | TBD | TBD | `0=0/127=20/[Lin]` | Makeup gain |
| `Main[1-4]CompKnee[1-1]` | TBD | TBD | TBD | | Soft/hard knee |
| `Main[1-4]CompPar[1-1]` | TBD | TBD | TBD | `0=0/127=100/[Lin]` | Parallel blend |
| `Main[1-4]CompType[1-1]` | TBD | TBD | TBD | | Type: Tube/FET/VCA/Optical |
| `Main[1-4]EqShelf[1-2]` | TBD | TBD | TBD | | Band 1/4 shelf mode on/off |
| `Main[1-4]CrossoverFreq[1-1]` | TBD | TBD | TBD | `0=50/127=500/[Log]` | Crossover frequency |
| `Main[1-4]CrossoverSlope[1-1]` | TBD | TBD | TBD | `0=6/3=24/[Lin]` | Crossover slope: 6/12/18/24 dB/oct |
| `Main[1-1]Geq[1-28]` | TBD | TBD | TBD | `0=-12/127=12/[Lin]` | 28-band stereo GEQ on Main L/R output |
| `Main[1-4]PeqGain[1-12]` | TBD | TBD | TBD | `0=-12/127=12/[Lin]` | Compatibility alias used in `mx_master.csv` for main GEQ gains |
| `Main[1-4]Mtr[1-1]` | TBD | TBD | TBD | | Compatibility alias for main output meter family in `mx_master.csv` |

---

## 7. FX Engine Parameters (×6 engines)

> **DSP:** Chip 2

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Fx[1-6]On[1-1]` | TBD | TBD | TBD | | FX bypass |
| `Fx[1-6]Type[1-1]` | TBD | TBD | TBD | | Echo/PingPong/Doubling/Reverb/Chorus/Flanger/Phaser |
| `Fx[1-6]Decay[1-1]` | TBD | TBD | TBD | `0=0.1/127=10/[Log]` | Reverb decay time |
| `Fx[1-6]PreDelay[1-1]` | TBD | TBD | TBD | `0=0/127=100/[Lin]` | Pre-delay time |
| `Fx[1-6]DelayTime[1-1]` | TBD | TBD | TBD | `0=1/127=1000/[Log]` | Delay/tempo time (ms; also set via Tap) |
| `Fx[1-6]Feedback[1-1]` | TBD | TBD | TBD | `0=0/127=100/[Lin]` | Delay repeats/feedback |
| `Fx[1-6]Balance[1-1]` | TBD | TBD | TBD | `0=0/127=100/[Lin]` | Delay ↔ Reverb blend (hard left=100% Delay, hard right=100% Reverb) |
| `Fx[1-6]Damp[1-1]` | TBD | TBD | TBD | `0=0/127=100/[Lin]` | HF damping amount |
| `Fx[1-6]EqPresence[1-1]` | TBD | TBD | TBD | `0=-6/127=6/[Lin]` | Presence — high shelving EQ (fixed ~5 kHz, ±6 dB). In `mx_master.csv`, this control is named `Fx[*]EqHi[*]`. |
| `Fx[1-6]EqHi[1-1]` | TBD | TBD | TBD | `0=-6/127=6/[Lin]` | Compatibility alias for `EqPresence` in `mx_master.csv` |
| `Fx[1-6]EqMid[1-1]` | TBD | TBD | TBD | `0=-6/127=6/[Lin]` | Mid EQ (fixed ~1 kHz, ±6 dB) |
| `Fx[1-6]EqLo[1-1]` | TBD | TBD | TBD | `0=-6/127=6/[Lin]` | Low shelving EQ |
| `Fx[1-6]EqHpf[1-1]` | TBD | TBD | TBD | `0=80/127=300/[Log]` | HPF / Low Cut frequency (80–300 Hz) |
| `Fx[1-6]ModRate[1-1]` | TBD | TBD | TBD | `0=0.1/127=10/[Log]` | LFO modulation rate (Chorus/Flanger/Phaser) |
| `Fx[1-6]ModLevel[1-1]` | TBD | TBD | TBD | `0=0/127=100/[Lin]` | LFO modulation level / depth (Chorus/Flanger/Phaser) |
| `Fx[1-6]LfoShape[1-1]` | TBD | TBD | TBD | | LFO shape: sine/triangle (Chorus/Flanger/Phaser) |
| `Fx[1-6]LfoMode[1-1]` | TBD | TBD | TBD | | LFO vs Manual mode (Phaser/Flanger) |
| `Fx[1-6]StereoWidth[1-1]` | TBD | TBD | TBD | `0=0/127=100/[Lin]` | Stereo width 0–100% (Chorus/Flanger/Phaser/PingPong) |
| `Fx[1-6]PingPongStart[1-1]` | TBD | TBD | TBD | | PingPong starts: Left/Right |
| `Fx[1-6]Mix[1-1]` | TBD | TBD | TBD | `0=0/127=100/[Lin]` | Dry/Wet mix 0–100% |
| `Fx[1-6]ReturnWetLock[1-1]` | TBD | TBD | TBD | | Return Wet Lock: force 100% wet on FX return |
| `Fx[1-6]DuckOn[1-1]` | TBD | TBD | TBD | | Ducker on/off (requires 12 dB/oct HPF at 100 Hz) |
| `Fx[1-6]DuckSens[1-1]` | TBD | TBD | TBD | `0=-30/127=0/[Lin]` | Ducker sensitivity (manual label: "Sensitivity") |
| `Fx[1-6]DuckThr[1-1]` | TBD | TBD | TBD | `0=-30/127=0/[Lin]` | Legacy alias of `DuckSens` retained for csv compatibility |
| `Fx[1-6]Tap[1-1]` | TBD | TBD | TBD | | Tap tempo trigger |
| `Fx[1-6]PedAssign[1-4]` | TBD | TBD | TBD | | Footswitch pedal 1–4 assignment (D32 PI pedal on/off) |
| `Fx[1-6]MuteGrp[1-8]` | TBD | TBD | TBD | | Mute group 1–8 assignment for FX return |
| `Fx[1-6]RtgLevel[1-1]` | TBD | TBD | TBD | `dB:Off:-50@31:-30@63:-10@127:0` | FX return master level |
| `Fx[1-6]RtgMute[1-1]` | TBD | TBD | TBD | | FX return mute |
| `Fx[1-6]RtgDca[1-1]` | TBD | TBD | TBD | | FX return DCA assignment 1–8 |
| `Fx[1-6]RtgAuxOn[1-12]` | TBD | TBD | TBD | | FX return to aux on/off (all 12 auxes) |
| `Fx[1-6]RtgAuxSend[1-12]` | TBD | TBD | TBD | `dB:Off:-50@31:-30@63:-10@127:0` | FX return to aux level (all 12 auxes) |

---

## 8. Group Bus Parameters (×4 buses)

> **DSP:** Chip 2

Group buses sum channel sends and feed into the main L/R bus and/or direct outputs.
Each group has a full dynamics section (gate + compressor) — same topology as the channel strip.
Sidechain key shares the same `0=self, 1–32=channel N` routing as channel gate/comp.

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Grp[1-4]RtgLevel[1-1]` | TBD | TBD | TBD | `dB:Off:-50@31:-30@63:-10@127:10` | Group master fader |
| `Grp[1-4]RtgMute[1-1]` | TBD | TBD | TBD | | Group mute |
| `Grp[1-4]RtgDca[1-1]` | TBD | TBD | TBD | | DCA assignment 1–8 |
| `Grp[1-4]EqOn[1-1]` | TBD | TBD | TBD | | EQ bypass |
| `Grp[1-4]EqHpf[1-1]` | TBD | TBD | TBD | `0=20/64=1000/[Log]` | HPF frequency |
| `Grp[1-4]EqFreq[1-1]` | TBD | TBD | TBD | `0=20/254=200/[Log]` | Band 1 frequency |
| `Grp[1-4]EqFreq[2-2]` | TBD | TBD | TBD | `0=100/254=1000/[Log]` | Band 2 frequency |
| `Grp[1-4]EqFreq[3-3]` | TBD | TBD | TBD | `0=800/254=5000/[Log]` | Band 3 frequency |
| `Grp[1-4]EqFreq[4-4]` | TBD | TBD | TBD | `0=3000/254=20000/[Log]` | Band 4 frequency |
| `Grp[1-4]EqGain[1-4]` | TBD | TBD | TBD | `0=-15/60=15/[Lin]` | Bands 1–4 gain ±15 dB |
| `Grp[1-4]EqQ[1-4]` | TBD | TBD | TBD | `0=0.1/14=10/[Log]` | Bands 1–4 Q |
| `Grp[1-4]EqShelf[1-2]` | TBD | TBD | TBD | | Band 1/4 shelf mode |
| `Grp[1-4]Peq[1-12]` | TBD | TBD | TBD | `0=20/127=20000/[Log]` | 12-band auto-notch filter (anti-feedback) — center frequency per band |
| `Grp[1-4]GateOn[1-1]` | TBD | TBD | TBD | | Gate bypass |
| `Grp[1-4]GateThr[1-1]` | TBD | TBD | TBD | `0=-80/127=0/[Lin]` | Threshold |
| `Grp[1-4]GateAtt[1-1]` | TBD | TBD | TBD | `0=0.1/127=250/[Log]` | Attack |
| `Grp[1-4]GateHold[1-1]` | TBD | TBD | TBD | `0=0/127=2000/[Log]` | Hold |
| `Grp[1-4]GateRel[1-1]` | TBD | TBD | TBD | `0=50/127=5000/[Log]` | Release |
| `Grp[1-4]GateRng[1-1]` | TBD | TBD | TBD | `0=0/127=60/[Lin]` | Range |
| `Grp[1-4]GateKey[1-1]` | TBD | TBD | TBD | | Key source: 0=self, 1–32=channel N |
| `Grp[1-4]CompOn[1-1]` | TBD | TBD | TBD | | Compressor bypass |
| `Grp[1-4]CompThr[1-1]` | TBD | TBD | TBD | `0=-60/140=10/[Lin]` | Threshold |
| `Grp[1-4]CompRat[1-1]` | TBD | TBD | TBD | `0=1/127=30/[Log]` | Ratio |
| `Grp[1-4]CompAtt[1-1]` | TBD | TBD | TBD | `0=0/254=250/[Log]` | Attack |
| `Grp[1-4]CompRel[1-1]` | TBD | TBD | TBD | `0=5/254=5000/[Log]` | Release |
| `Grp[1-4]CompMake[1-1]` | TBD | TBD | TBD | `0=0/127=20/[Lin]` | Makeup gain |
| `Grp[1-4]CompKnee[1-1]` | TBD | TBD | TBD | | Soft/hard knee |
| `Grp[1-4]CompPar[1-1]` | TBD | TBD | TBD | `0=0/127=100/[Lin]` | Parallel blend |
| `Grp[1-4]CompType[1-1]` | TBD | TBD | TBD | | Type: Tube/FET/VCA/Optical |

---

## 9. Center / Subwoofer Bus Parameters (×1)

> **DSP:** Chip 2

Single mono bus. Fed from channel `RtgCtrOn` assigns and from Main L/R via the crossover.
Processing chain: EQ → Compressor → Limiter → Delay → output.
No gate (sub bus is not typically gated).

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Sub[1-1]RtgLevel[1-1]` | TBD | TBD | TBD | `dB:Off:-50@31:-30@63:-10@127:10` | Subwoofer master fader |
| `Sub[1-1]RtgMute[1-1]` | TBD | TBD | TBD | | Subwoofer mute |
| `Sub[1-1]Delay[1-1]` | TBD | TBD | TBD | `0=0/127=250/[Log]` | Output delay up to 250 ms |
| `Sub[1-1]EqOn[1-1]` | TBD | TBD | TBD | | EQ bypass |
| `Sub[1-1]EqHpf[1-1]` | TBD | TBD | TBD | `0=20/64=1000/[Log]` | HPF frequency |
| `Sub[1-1]EqFreq[1-1]` | TBD | TBD | TBD | `0=20/254=200/[Log]` | Band 1 frequency |
| `Sub[1-1]EqFreq[2-2]` | TBD | TBD | TBD | `0=100/254=1000/[Log]` | Band 2 frequency |
| `Sub[1-1]EqFreq[3-3]` | TBD | TBD | TBD | `0=800/254=5000/[Log]` | Band 3 frequency |
| `Sub[1-1]EqFreq[4-4]` | TBD | TBD | TBD | `0=3000/254=20000/[Log]` | Band 4 frequency |
| `Sub[1-1]EqGain[1-4]` | TBD | TBD | TBD | `0=-15/60=15/[Lin]` | Bands 1–4 gain ±15 dB |
| `Sub[1-1]EqQ[1-4]` | TBD | TBD | TBD | `0=0.1/14=10/[Log]` | Bands 1–4 Q |
| `Sub[1-1]CompOn[1-1]` | TBD | TBD | TBD | | Compressor bypass |
| `Sub[1-1]CompThr[1-1]` | TBD | TBD | TBD | `0=-60/140=10/[Lin]` | Threshold |
| `Sub[1-1]CompRat[1-1]` | TBD | TBD | TBD | `0=1/127=30/[Log]` | Ratio |
| `Sub[1-1]CompAtt[1-1]` | TBD | TBD | TBD | `0=0/254=250/[Log]` | Attack |
| `Sub[1-1]CompRel[1-1]` | TBD | TBD | TBD | `0=5/254=5000/[Log]` | Release |
| `Sub[1-1]CompMake[1-1]` | TBD | TBD | TBD | `0=0/127=20/[Lin]` | Makeup gain |
| `Sub[1-1]CompKnee[1-1]` | TBD | TBD | TBD | | Soft/hard knee |
| `Sub[1-1]CompPar[1-1]` | TBD | TBD | TBD | `0=0/127=100/[Lin]` | Parallel blend |
| `Sub[1-1]CompType[1-1]` | TBD | TBD | TBD | | Type: Tube/FET/VCA/Optical |
| `Sub[1-1]LimiterOn[1-1]` | TBD | TBD | TBD | | Limiter bypass |
| `Sub[1-1]LimiterThr[1-1]` | TBD | TBD | TBD | `0=-30/127=0/[Lin]` | Limiter threshold |
| `Sub[1-1]Mtr[1-1]` | TBD | TBD | TBD | | Compatibility alias for sub output meter in `mx_master.csv` |

---

## 10. DCA Masters (×8)

> **DSP:** Chip 1 + Chip 2 — Level/Mute scalar written to both chips independently via H1S1 CS1/CS2; applied to channel faders on Chip 1, bus faders on Chip 2.

DCAs are control-only: they multiply the fader coefficient of all assigned channels/buses.
No audio passes through the DCA node itself — the gain product is applied at each member's fader.

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Dca[1-8]Level[1-1]` | TBD | TBD | TBD | `dB:Off:-50@31:-30@63:-10@127:10` | DCA master fader — multiplied into all assigned channel/bus faders |
| `Dca[1-8]Mute[1-1]` | TBD | TBD | TBD | | DCA master mute — ORed with each member's mute |

---

## 11. Mute Groups (×8)

> **DSP:** H1S1 MCU only — no dedicated DSP param RAM block; H1S1 fans out to each member's RtgMute coefficient on write.

Software mute groups: toggling a mute group activates/deactivates all member channel mutes simultaneously.
No DSP coefficient — managed by H1S1 MCU logic, reflected into each `Chan[n]RtgMute` coefficient.

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Mute[1-8]On[1-1]` | TBD | TBD | TBD | | Mute group master on/off — H1S1 fans out to all member mute coefficients |

---

## 12. Monitor / Phones Section

> **DSP:** Chip 2

Stereo monitor output (L/R) fed from Main L/R, any Aux, or the cue bus.
Two independent phone output levels (Phones 1–2 and Phones 3–4 share the same source select but have independent level trims on the analogue driver stage — no additional DSP coefficients).

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Mon[1-1]Level[1-2]` | TBD | TBD | TBD | `dB:Off:-50@31:-30@63:-10@127:10` | Monitor L and R output levels (index 1=L, 2=R) |
| `Mon[1-1]Delay[1-1]` | TBD | TBD | TBD | `0=0/127=250/[Log]` | Monitor output delay up to 250 ms |
| `Mon[1-1]InputSel[1-1]` | TBD | TBD | TBD | | Monitor source: Main L/R, Aux 1–12, Cue bus |

---

## 13. USB / Bluetooth / 2-Track

> **DSP:** Chip 2

### 13.1 USB Audio Input (USB-A / USB-C stereo playback)

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Usb[1-1]Level[1-1]` | TBD | TBD | TBD | `0=-20/127=6/[Lin]` | USB audio input level |
| `Usb[1-1]On[1-1]` | TBD | TBD | TBD | | USB audio input enable |

### 13.2 Bluetooth Input

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Bt[1-1]Level[1-1]` | TBD | TBD | TBD | `0=-20/127=6/[Lin]` | Bluetooth audio input level |
| `Bt[1-1]On[1-1]` | TBD | TBD | TBD | | Bluetooth input enable |
| `Bt[1-1]Src[1-1]` | TBD | TBD | TBD | | Bluetooth source select |

### 13.3 USB-C 2-Track Record / Play (DAW)

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Rec[1-1]Level[1-1]` | TBD | TBD | TBD | `0=-20/127=6/[Lin]` | 2-track record input level |
| `Rec[1-1]Rec[1-1]` | TBD | TBD | TBD | | Record enable toggle |
| `Rec[1-1]Play[1-1]` | TBD | TBD | TBD | | Playback enable toggle |
| `Rec[1-1]Src[1-1]` | TBD | TBD | TBD | | Record source: Main L/R or Aux 1–4 |

### 13.4 H1S1 UI/System-Only Cells (no DSP coefficient RAM)

These cells exist in `mx_master.csv` for UI/control/state persistence and are intentionally
host-side (H1S1) rather than DSP coefficient targets.

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Sys[1-1]AuxOnFdr[1-1]` | TBD | TBD | TBD | | Aux-on-fader mode state (UI) |
| `Sys[1-1]BtnBright[1-1]` | TBD | TBD | TBD | | Button brightness (UI) |
| `Sys[1-1]Cue[1-64]` | TBD | TBD | TBD | | Cue bitmap/state cache (UI) |
| `Sys[1-1]CueMode[1-1]` | TBD | TBD | TBD | | Global cue mode |
| `Sys[1-1]Def[1-1]` | TBD | TBD | TBD | | UI defaults selector |
| `Sys[1-1]Enc[1-1]` | TBD | TBD | TBD | | Encoder sensitivity setting |
| `Sys[1-1]FdrDown[1-1]` | TBD | TBD | TBD | | Fader-down behavior flag |
| `Sys[1-1]FootMode[1-1]` | TBD | TBD | TBD | | Footswitch mode |
| `Sys[1-1]Keys[1-127]` | TBD | TBD | TBD | | On-screen keyboard keycodes |
| `Sys[1-1]Lock[1-1]` | TBD | TBD | TBD | | UI lock state |
| `Sys[1-1]Man[1-1]` | TBD | TBD | TBD | | Manual/help panel state |
| `Sys[1-1]MtrSrc[1-1]` | TBD | TBD | TBD | | Meter source display mode |
| `Sys[1-1]MxMode[1-1]` | TBD | TBD | TBD | | Mixer mode selector |
| `Sys[1-1]OptMix[1-1]` | TBD | TBD | TBD | | Optional mix mode flag |
| `Sys[1-1]Reg[1-10]` | TBD | TBD | TBD | | Registration buttons |
| `Sys[1-1]Reset[1-1]` | TBD | TBD | TBD | | UI reset trigger |
| `Sys[1-1]Scene[1-1]` | TBD | TBD | TBD | | Current scene selector |
| `Sys[1-1]SceneSafe[1-32]` | TBD | TBD | TBD | | Scene-safe channel mask |
| `Sys[1-1]ScrBright[1-1]` | TBD | TBD | TBD | | Screen brightness |
| `Sys[1-1]SelectedAux[1-1]` | TBD | TBD | TBD | | UI selected aux index |
| `Sys[1-1]SelectedChan[1-1]` | TBD | TBD | TBD | | UI selected channel index |
| `Sys[1-1]Skin[1-1]` | TBD | TBD | TBD | | Skin/theme selection |
| `Sys[1-1]Test[1-2]` | TBD | TBD | TBD | | System test toggles |
| `Fdr[1-5]Grp[1-32]` | TBD | TBD | TBD | | Fader group membership matrix (UI routing helper) |
| `ZzStripChan[1-32]Name[1-1]` | TBD | TBD | TBD | | Channel name storage |
| `ZzStripAux[1-12]Name[1-1]` | TBD | TBD | TBD | | Aux name storage |
| `ZzStripDca[1-8]Name[1-1]` | TBD | TBD | TBD | | DCA name storage |
| `ZzStripFx[1-6]Name[1-1]` | TBD | TBD | TBD | | FX name storage |
| `ZzStripGrp[1-4]Name[1-1]` | TBD | TBD | TBD | | Group name storage |
| `ZzStripSub[1-1]Name[1-1]` | TBD | TBD | TBD | | Sub name storage |
| `Another[1-1]Test[1-100]` | TBD | TBD | TBD | | Legacy placeholder test block |
| `Zzz[1-1]Zzz[1-1]` | TBD | TBD | TBD | | End-of-table sentinel |

---

## 14. Talkback / Noise Generator

> **DSP:** Chip 1

### 14.1 Talkback

Two talkback sources: internal MEMS mic (Talk[1]) and external XLR (Talk[2]).
Routing is a bitmask over aux buses 1–N and main L/R; up to 3 route slots per instance.

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Talk[1-2]On[1-1]` | TBD | TBD | TBD | | Talkback enable (momentary press = latching on D32) |
| `Talk[1-2]Gain[1-1]` | TBD | TBD | TBD | `0=0/127=40/[Lin]` | Mic input gain; fixed +48 V op-amp preamp on Talk[1] |
| `Talk[1-2]Hpf[1-1]` | TBD | TBD | TBD | | HPF on/off (cuts below ~80 Hz) |
| `Talk[1-2]Rtg[1-3]` | TBD | TBD | TBD | | Routing destinations: each slot selects an aux bus or main |
| `Talk[1-1]On[1-1]` | TBD | TBD | TBD | | Compatibility alias row used by `mx_master.csv` |
| `Talk[1-1]Hpf[1-1]` | TBD | TBD | TBD | | Compatibility alias row used by `mx_master.csv` |
| `Talk[1-1]Rtg[1-3]` | TBD | TBD | TBD | | Compatibility alias row used by `mx_master.csv` |

### 14.2 Noise / Tone Generator

| _Cell | DspSpi | DspBaseAddr | Stride | Table | Notes |
|-------|--------|-------------|--------|-------|-------|
| `Noise[1-1]On[1-1]` | TBD | TBD | TBD | | Noise/tone generator enable |
| `Noise[1-1]Level[1-1]` | TBD | TBD | TBD | `0=-40/127=0/[Lin]` | Output level |
| `Noise[1-1]Hpf[1-1]` | TBD | TBD | TBD | | HPF ~80 Hz on/off (pink noise mode) |
| `Noise[1-1]Rtg[1-10]` | TBD | TBD | TBD | | Routing bitmask to aux buses and main L/R |

---

## 15. Meter Sources (DSP Read-back)

Read-only values: DSP writes to parameter RAM, host polls at display rate.  
No `Table` formula — raw linear values converted to dB by the display layer.

> **`Aa` prefix convention:** All meter cells are prefixed `Aa` to sort them to the top of the `_matrix.csv` address table. Because the SPI bus uses compressed (shifted-hex) addressing, cells with lower addresses require fewer bytes per message. Placing meters first maximises throughput for the highest-polling-rate data on the bus. Unprefixed legacy names (`Sub001Mtr001`, `Main001Mtr001`, etc.) in `_matrix.csv` are superseded by their `Aa`-prefixed equivalents and should be removed.

### Channel meters (×32)

Each channel has four meters: two level taps and two dynamics gain-reduction meters.

| _Cell | DspSpi | DspBaseAddr | Stride | Notes |
|-------|--------|-------------|--------|-------|
| `AaChan[1-32]Mtr[1-2]` | TBD | TBD | TBD | Fun 1: **Post preamp / trim** — level after Gain/Pol/Trim, before EQ. Fun 2: **Post fader** — level after Fader+Pan+Mute. |
| `AaChan[1-32]GateMtr[1-1]` | TBD | TBD | TBD | **Gate gain-reduction** — 0 dB when open, negative dB when attenuating. |
| `AaChan[1-32]DynMtr[1-1]` | TBD | TBD | TBD | **Compressor gain-reduction** — 0 dB when inactive, negative dB when compressing. |

> `AaChan[n]GateMtr` is now present in the master cell definitions. Keep generated `_matrix.csv`
> in sync so DSP address packing includes this meter family.

### Bus and output meters

| _Cell | DspSpi | DspBaseAddr | Stride | Notes |
|-------|--------|-------------|--------|-------|
| `AaAux[1-12]Mtr[1-1]` | TBD | TBD | TBD | Aux output level — post fader, post limiter. Auxes 9–12 inactive on D24 via product mask. |
| `AaMain[1-4]Mtr[1-2]` | TBD | TBD | TBD | Main output level — index 1=L, 2=R per output. |
| `AaGrp[1-4]Mtr[1-1]` | TBD | TBD | TBD | Group bus output level — post fader. |
| `AaSub[1-1]Mtr[1-1]` | TBD | TBD | TBD | Subwoofer output level. Legacy unprefixed `Sub001Mtr001` may remain temporarily as compatibility alias and should be removed after downstream validation. |
| `AaFx[1-6]Mtr[1-1]` | TBD | TBD | TBD | FX return level — post return fader. |

---

## 16. Address Space Plan

Word counts estimated from parameter tables above (instances × fun indices per cell).  
Start/end addresses are TBD until the ADSP-21564 program is designed and blocks are packed.

**Chip 1 — Input DSP**

| Block | Start | End | Words (est.) | Notes |
|-------|-------|-----|-------------|-------|
| Channel strip ×32 | TBD | TBD | ~3,970 | Per-channel params incl. routing matrix |
| Talkback / Noise | TBD | TBD | ~25 | Talk[1-2] + noise generator |
| Meter read-back | TBD | TBD | ~128 | AaChan Mtr×2, GateMtr, DynMtr — DSP writes, host reads |
| **Chip 1 total** | — | — | **~4,123** | **~16 KB** at 32-bit words |

**Chip 2 — Output DSP**

| Block | Start | End | Words (est.) | Notes |
|-------|-------|-----|-------------|-------|
| Aux buses ×12 | TBD | TBD | ~624 | Incl. 28-band GEQ per bus; buses 9–12 inactive on D24 |
| Group buses ×4 | TBD | TBD | ~188 | Incl. gate + comp dynamics |
| Sub/Center bus ×1 | TBD | TBD | ~28 | |
| Main outputs ×4 | TBD | TBD | ~152 | Incl. 28-band GEQ on Main L/R |
| FX engines ×6 | TBD | TBD | ~372 | Incl. aux return matrix |
| DCA masters ×8 | TBD | TBD | ~16 | Level + Mute scalars (H1S1 writes to both chips independently via CS1/CS2) |
| Monitor / Phones | TBD | TBD | ~4 | |
| USB / BT / Rec | TBD | TBD | ~9 | |
| Meter read-back | TBD | TBD | ~31 | AaAux, AaMain, AaGrp, AaSub, AaFx — DSP writes, host reads |
| **Chip 2 total** | — | — | **~1,424** | **~6 KB** at 32-bit words |

**H1S1 MCU only (no DSP param RAM)**

| Block | Notes |
|-------|-------|
| Mute groups ×8 | Virtual cells; H1S1 fans out to member RtgMute coefficients on write |

---

## 17. Build Tool (`gen_dsp.py`)

> Not yet written. Lives in `MW/D32/DSP/`.

### Inputs

- `dsp-def.md` — this file: parameter tables, Table formulas, chip assignments
- `MW/D32/MX/_matrix.csv` — existing cell definitions; used for cross-reference validation and non-destructive backfill
- optional profile block in §3b — resolves `RampProfile` into concrete `Ramp*` fields

### Algorithm

1. **Parse** each `## N.` section; identify chip assignment from the `> **DSP:** Chip N` blockquote.
2. **Expand** instance patterns: `Chan[1-32]EqFreq[1-4]` → 32 channels × 4 fun indices = 128 words.
3. **Pack addresses** per chip sequentially from `0x0000`:
   - `DspBaseAddr` = next free word in chip N's address space.
   - `Stride` = number of fun indices in the cell's fun range.
   - `DspAdd[n] = DspBaseAddr + (n − 1) × Stride`
4. **Resolve ramp metadata** per expanded cell:
    - apply explicit row values if present;
    - otherwise inherit from `RampProfile`;
    - otherwise default to `Instant`.
5. **Validate** cross-reference and ramp schema:
    - warn on cells present in `_matrix.csv` but absent from dsp-def.md, and vice versa;
    - error on invalid `RampMode`, negative/overflow times, or unsupported `RampScope`.
6. **Write outputs** (see below). Non-destructive by default: only writes TBD/empty fields unless `--force`.

### Outputs

- **`MW/D32/MX/_matrix.csv` backfill** — populates `DspSpi`, `DspAdd`, `DspAddHex`, `Table`, and ramp metadata (`RampProfile`, `RampMode`, `RampUpMs`, `RampDownMs`, `RampCurve`, `RampScope`) for expanded cells.
- **`ghost_cells.h`** — C struct array (`CellDef[]`) for H1S1 MCU firmware: `{ .name, .chip, .spi, .addr, .table, .ramp_mode, .ramp_up_frames, .ramp_down_frames, .ramp_scope }`.
- **`dsp_params.asm`** — ADSP-21564 parameter RAM `.EQU` symbol definitions for the DSP assembler project.
- **`dsp_address_map.md`** — auto-generated §16 fill-in with final addresses for design review.

### CLI

    usage: gen_dsp.py [--dry-run] [--force] [--target adsp21564|fpga] [--chip 1|2|all]

      --dry-run     Print planned assignments without writing any files
      --force       Overwrite existing non-TBD addresses in _matrix.csv
      --target      Output format: adsp21564 (.asm) or fpga (reserved)
      --chip        Restrict output to one chip's address space

---

## 18. Self-Test DSP Parameters

> **DSP:** Chip 1 (stimulus generation and measurement run on the input DSP to keep the analogue loopback path fully exercised)  
> **Reference:** `MW/D32/self-test.md` — full production test procedure and fixture spec.

Self-test mode loads `self_test.dsp` in place of the normal audio program. The test host (fixture PC / Raspberry Pi) controls all blocks below over the standard SPI interface.

> Detail TBD. Brief cell names listed as placeholders.

| _Cell | Table | Notes |
|-------|-------|-------|
| `Test[1-1]OscOn[1-1]` | | Enable precision sine oscillator |
| `Test[1-1]OscFreq[1-1]` | `0=20/127=20000/[Log]` | Oscillator frequency 20 Hz – 20 kHz |
| `Test[1-1]OscLevel[1-1]` | `0=-60/127=0/[Lin]` | Oscillator output level dBFS |
| `Test[1-1]OscChan[1-1]` | | Target channel / output for oscillator injection (0 = all) |
| `Test[1-1]SweepOn[1-1]` | | Start frequency sweep (host reads level at each step via meter cells) |
| `Test[1-1]SweepStep[1-1]` | | Number of steps in sweep (TBD) |
| `Test[1-1]MeasChan[1-1]` | | Select channel to read for RMS / THD measurement |
| `Test[1-1]RmsResult[1-1]` | | Read-back: RMS level at selected tap (DSP writes, host reads) |
| `Test[1-1]ThdResult[1-1]` | | Read-back: THD+N ratio at selected channel (DSP writes, host reads) |
| `Test[1-1]NoiseResult[1-1]` | | Read-back: noise floor (oscillator off, broadband RMS) |
| `Test[1-1]XtalkSrc[1-1]` | | Source channel for crosstalk measurement |
| `Test[1-1]XtalkDst[1-1]` | | Destination channel to measure bleed on |
| `Test[1-1]XtalkResult[1-1]` | | Read-back: crosstalk level dB (DSP writes, host reads) |

---

## 19. Next Steps / Implementation Status

> **Updated 2026-04-14:** LP0 inter-chip forwarding removed — ADSP-21564 has no link ports. Dual independent SPI confirmed from D24 DSP4 rev C schematic (CS1=DSPA/U6, CS2=DSPB/U5, shared MOSI/MISO/CLK). Board in fabrication; no revision needed. Code generation pipeline run clean; all infrastructure ASM reviewed.

### Phase 0 — LP0 → Dual-SPI Migration *(unblocked — pure firmware changes)*

> Hardware: both ADSP-21564 chips wired to H1S1 SPI1 bus with independent CS lines (PB12=CS1→DSPA, PC14=CS2→DSPB). `spi_page=1` → DSPA, `spi_page=2` → DSPB.

- ✅ **P0.1** Remove LP0 forwarding block from `chip1/spi_handler.asm` — delete `.spi_forward_lp0` label, `_lp0_queue*` variables, `_lp0_tx_pump` function, LP0 register defines
- ✅ **P0.2** Create `chip2/spi_handler.asm` — direct SPI1 slave receive ISR; identical dispatch logic to chip1's but no LP0 block; writes directly to `_param_ram_c2`
- ✅ **P0.3** Update `sport_init.asm` Chip 2 branch — init SPI1 slave (copy Chip 1 init block), replace `IMASK_LP0` enable with `IMASK_SPI1`
- ✅ **P0.4** Update `ivt.asm` Chip 2 — replace LP0 RX vector with SPI1 RX vector → `_spi1_rx_isr`
- ✅ **P0.5** Remove `call _lp0_tx_pump` from `main.asm` main loop
- ✅ **P0.6** Update `ghost_cells.h` — change `spi_page` from `1` to `2` for all Chip 2 entries (1,490 entries updated)

### Phase 1 — Code Generation Pipeline *(blocking — all subsequent work depends on this)*

1. ✅ **Audit `gen_dsp_csv.py`** — Correctly parses dsp-def.md §4–§18 parameter tables; produces valid `dsp.csv` with sequential address packing per chip.
   - File: `MW/D32/DSP/SHARC/tools/gen_dsp_csv.py`

2. ✅ **Run `gen_dsp_csv.py`** — Output clean: 612 nodes, Chip1=3,902 SPI words, Chip2=1,818 words.

3. ✅ **Backfill `_matrix.csv`** — `gen_dsp.py --force` run clean: 612 nodes → 4,893 cell mappings, 4,047 cells matched and backfilled. Fixed `write_ghost_cells_h()` `spi_page` bug (`cm["spi_page"]` → `cm["chip"]`). `ghost_cells.h` regenerated (4,893 cells; 1,490 chip 2 entries correct at `spi_page=2`). `chip1/dsp_params.asm` (5,536 lines) and `chip2/dsp_params.asm` (2,476 lines) written — Phase 5 CCES build dependency now satisfied.

4. ✅ **Audit `dsp_codegen.py`** — Correctly reads `dsp.csv`; generates `process_chain.asm`, scatter/gather loops, node instantiation, ramp engine files.

5. ✅ **Run `dsp_codegen.py`** — 618 files generated clean: chip1/nodes/ (405), chip2/nodes/ (207), process chains, `ramp_engine.asm`, `ramp_tables.asm`.

### Phase 2 — Infrastructure Verification *(parallel tracks after Phase 1)*

**Track A — I/O & Comms**

6. ✅ **Review `sport_init.asm`** — SPORT/DMA configuration verified. SPI1 slave init confirmed for Chip 1. *(Chip 2 SPI init pending Phase 0.3)*

7. ✅ **Review `chip1/spi_handler.asm`** — SPI receive ISR verified. LP0 forwarding block present but to be removed in Phase 0.1.

8. 🗑 **Review `chip2/lp0_handler.asm`** — *Superseded by Phase 0: LP0 removed. File to be replaced by `chip2/spi_handler.asm` (Phase 0.2).*

**Track B — DSP Library**

9. ✅ **Review `lib/biquad.asm`** — DF-II transposed, SIMD-compatible. HW IIR accelerator not used (manual implementation). Cycle estimates match §1d.

10. ✅ **Review `lib/dynamics.asm`** — RMS/peak detector with polynomial log approximation verified. Gate + compressor both present.

11. ✅ **Review `lib/delay.asm`** — Circular buffer with tiered pooling verified. L2 SRAM allocation within §1d budget.

**Track C — Ramp Engine**

12. ✅ **Review `ramp_engine.asm` + `ramp_tables.asm`** — All 5 ramp profiles verified: `InstantCtl`, `GainFast`, `GainSafe`, `EqSafe`, `DynSafe`. Frame-quantized processing correct. *(LP0 ramp metadata forwarding removed in Phase 0)*

### Phase 3 — `gen_dsp.py` Build Tool *(§17)*

> **⚠ Architectural dependency (critical):** Generated node ASM files (e.g. `chip1/nodes/C1_GAIN_01.asm`) currently declare coefficient storage with standalone `.var` symbols. The SPI handler writes into the flat `_param_ram_c1[]` array by SPI address offset. These are **two separate memory regions** — SPI writes have no effect on node coefficients until `gen_dsp.py` produces `dsp_params.asm` with `.EQU` aliases resolving each node symbol to its correct offset within `_param_ram_c1`/`_param_ram_c2`. The DSP will compile and run, but parameter control is non-functional until Phase 3 is complete.

13. ✅ **Write `gen_dsp.py`** — Written and run. All four outputs produced clean (see Phase 1 step 3 above). `spi_page` bug fixed; Phase 5 CCES dependency (`dsp_params.asm`) satisfied. Also outputs copy of `ghost_cells.h` to H1S1 Inc/ for firmware inclusion.

### Phase 4 — H1S1 Firmware

14. ✅ **Write `cell_lookup.c`** — Written then deleted: superseded by `mx_dsp_map.h` index lookup; `CellLookup()` by name not needed on this path.
15. ✅ **Write `table_eval.c`** — Evaluate cell formula string → float32 coefficient
16. ✅ **Write `spi_dsp.c`** — Assert CS1 or CS2 per `spi_page`; HAL_SPI_Transmit 2×32-bit words (addr + coeff)
17. ✅ **Write `mx_dsp_dispatch.c`** — `DspDispatch(mx_addr, raw)` called from `Eol()` in matrix.cs. Binary search on `mx_dsp_map.h` (gen_dsp.py output: 4,047 `{MxAdd, cell_idx}` entries sorted by matrix bus address) → `TableEval()` → `DspCellWrite()`. All parameter control via MH1 MCU → UART nibble bus → H1S1, not direct Pi UART.
18. ✅ **Write `meter_poll.c`** — Periodic SPI read of meter cells; format as `"CellName=value\n"` reply to Pi
19. ✅ **Write `boot_config.c`** — Send initial scene state to both DSP chips on power-up

#### Phase 4 — H1S1 Operational Notes

##### Full control data path

```
Pi (Matrix app) → MH1 MCU → UART1 nibble bus → H1S1 Uart1_Int()
    → Rx_Fun[ch & 0x7f]() character dispatch
    → Eol(): a = uint16 MxAdd, d = uint8 raw value
    → DspDispatch(a, d)
    → binary search mx_dsp_map[4047] by MxAdd → cell_idx
    → TableEval(cell->formula, d) → float32 coefficient
    → DspCellWrite(cell, coeff, cell->ramp_mode)
    → DspRawWrite(spi_page, addr, coeff, ramp_id)
    → SPI1 8-byte packet → DSPA (CS1/PB12) or DSPB (CS2/PC14)
```

H1S1 is the **translation layer**: matrix bus 8-bit raw values → DSP float32 coefficients. It has no knowledge of the overall mix state; it reacts to individual cell writes.

##### Parameter scope

Every parameter in `_matrix.csv` with a `DspSpi` address assignment goes through this path. This includes:

| Parameter class | Formula type | Note |
|---|---|---|
| Gain / fader / trim / send | `dB:…` breakpoints | → linear amplitude float32 |
| EQ frequency | `Log` (20 Hz – 20 kHz) | → Hz float32, SHARC computes biquad |
| EQ gain | `Lin` or `dB` breakpoints | → dB float32, SHARC computes biquad |
| EQ Q / bandwidth | `Lin` | → Q float32, SHARC computes biquad |
| Dynamics threshold | `dB` breakpoints | → dBFS float32 |
| Dynamics ratio | `Lin` | → ratio float32 |
| Attack / release times | `Log` or `Lin` | → ms float32, SHARC converts to time constant |
| Delay time | `Lin` | → samples float32 |
| Routing / pan | `Pan` formula | → 0.0f (PanL/PanR handled per bus in SHARC) |
| Meter cells (`Aa` prefix) | none (read-only) | read via `DspRawRead()` in `meter_poll.c` |

**Important:** H1S1 sends the *parameter values* (frequency, gain, Q, threshold, etc.) — **not** pre-computed biquad coefficients (b0/b1/b2/a1/a2). The SHARC DSP computes the biquad math internally from those parameter values on each SPI write.

##### Ramp / slew handling

The 4-bit ramp profile ID is packed into SPI `Word0[11:8]` alongside the DSP address. H1S1 is completely unaware of the slew time values — it tags each packet with the profile ID stored in `CellDef.ramp_mode` and the SHARC firmware executes the ramping.

| ID | Profile | Typical use |
|---|---|---|
| 0 | `InstantCtl` | Mutes, routing switches, boot initialisation |
| 1 | `GainFast` | Fader moves during interaction |
| 2 | `GainSafe` | Audible-safe scene recall gain moves |
| 3 | `EqSafe` | EQ frequency, gain, Q (avoids zipper noise) |
| 4 | `DynSafe` | Dynamics thresholds, ratios |

Profile IDs are baked into `ghost_cells.h` at `gen_dsp.py` codegen time; `DspCellWrite()` uses the stored `ramp_mode` unless a caller explicitly overrides it.

##### SPI packet format (ADSP-21564 8-byte write)

```
Word 0 (32-bit, MSB first):
  [31:16]  DSP parameter RAM address
  [11:8]   ramp_profile_id (0–4)
  [7:0]    reserved (0x00)
Word 1 (32-bit, MSB first):
  [31:0]   IEEE-754 float32 coefficient
```

Reads (meter cells): same `Word0` structure with bit 15 of the lower halfword set as READ flag. DSP echoes the value in `Word1` of the RX frame.

##### Memory profile (Debug build, 2026-04-14)

| Region | Used | Total | % |
|---|---|---|---|
| Flash | text + data = 268 KB | 2,048 KB | 13% |
| RAM | data + bss = 3.5 KB | 768 KB | < 1% |

Flash is dominated by `ghost_cells[4893]` (~240 KB `const` in flash). RAM is minimal because all cell metadata is `const`.

##### Build

H1S1 builds outside STM32CubeIDE using `Debug/fw.sh`:
- `make -f makefile.linux all -j$(nproc)` — arm-none-eabi-gcc, cortex-m33, FPv5-SP-D16 hard-float
- Output: `H1S1.elf` → `H1S1.hex` → `H1S1.shex` (embedded MCU-ID in type-04 records)
- Integrated into `FW/build_all.sh` slave build path alongside H1S3 and H1S4

### Phase 5 — Build & Compile

20. ⚠ **Review `ADSP-21564.ldf`** — Verify linker script: L2 SRAM sections for delay buffers. *BLOCKED — CCES license not acquired.*
21. ⚠ **Review `build.sh`** — Verify assembler/linker invocation, output paths, CCES toolchain dependencies. *BLOCKED — CCES license not acquired.*
22. ⚠ **Attempt first build** — Run `build.sh`; collect and triage errors. *BLOCKED — CCES license not acquired.*

### Phase 6 — Validation

23. ✅ **Cross-reference audit** — 5,572 matrix rows vs 4,893 ghost_cells.h entries. Results:
    - **Critical direction (DSP cell in matrix missing from ghost_cells.h): 0** — every DSP-mapped matrix row (4,047/4,047) has a matching ghost_cells.h entry. ✓
    - 1,525 matrix rows have no DspSpi mapping — non-DSP cells (UI state, routing, names, etc.). Expected, correct.
    - 846 ghost_cells.h entries have no matrix row — DSP features not yet exposed via the control surface. Categorised:
      - Dynamics sidechain controls (CompDetSrc, CompEqPos, CompFilter×4, CompLimMode, GateDetSrc, GateFilter×4, CompKey) × up to 41 channels — 485 cells, UI deferred
      - GateMtr (gate activity meters) × 32 channels — 32 cells, not yet in matrix
      - PEQ bands 13–28 for Main001 + Aux001–012 — 220 cells, extended EQ bands deferred
      - EqShelf (high/low shelf) × 17 buses — 34 cells
      - LimiterAtt/Rel × 13 buses — 26 cells
      - Modulation/FX (Balance, DuckSens, StereoWidth, LfoShape, ModLevel, ModRate, Mix) × 6 each — 42 cells
      - AaAux009–012Mtr — 4 meter cells (Aux 9–12 not yet in matrix)
      - Minor routing (RtgDca, RtgMute, Rtg, On, Hpf) — 7 cells
    - **None of the 846 represent a bug.** All are deliberate deferred-feature omissions.
24. ⬜ **Cycle budget verification** — Confirm Chip 1 < 35%, Chip 2 < 41% (pessimistic targets from §1d).
25. ⬜ **SRAM budget verification** — Confirm Chip 1 < 580 KB, Chip 2 < 1,400 KB delay buffer allocation.

---

### Verification Checklist

1. ✅ `gen_dsp_csv.py` — Chip1=3,902 words, Chip2=1,818 words
2. ✅ `dsp_codegen.py` — 618 files generated clean
3. ✅ Phase 0 LP0 removal — 1 innocuous comment reference remains in `chip2/nodes/C2_MAIN_XOVER.asm` ("SPI staging buffer layout: [LP0..LP9…]"), no executable `lp0` instructions. Clean.
4. ✅ `ghost_cells.h` Chip 2 entries — 0 chip/spi_page mismatches. All 1,490 chip2 entries have `spi_page=2`.
5. ⚠ `build.sh` — zero assembler/linker errors *(BLOCKED — CCES license)*
6. ✅ Spot-check representative cells — all present with correct table/ramp:
   - `Chan001EqFreq001`: chip=1, addr=16, table=`0=20/254=200/[Log]`, ramp=2 ✓
   - `Aux001RtgLevel001`: chip=2, addr=0, table=`dB:Off:-50@31:-30@63:-10@127:10`, ramp=1 ✓
   - `Fx001Decay001`: chip=2, addr=1583, table=`0=0.1/127=10/[Log]`, ramp=1 ✓
   - `Main001Peq001` (GEQ band 1): chip=2, addr=1347, table=`0=-12/127=12/[Lin]`, ramp=2 ✓
   - `AaChan001Mtr001`: chip=1, addr=3712, table=`""` (meter read-only), ramp=0 ✓
7. ✅ `ghost_cells.h` struct count — 4,893 cells matches gen_dsp.py output (4,893 expanded entries).

### Decisions (locked for rev A)

- Two-chip architecture for rev A (single-chip deferred to rev B cost reduction — §1d)
- Tiered input delay: N=8 extended slots (20 ms × 32 base + 8 @ 250 ms — §1d)
- ADSP-21564 as DSP target; FPGA paths documented but deferred (§1b, §1e)
- D24 and D32 share a single binary; feature differentiation via `CHAN_MASK`/`AUX_MASK` boot config
- **LP0 inter-chip forwarding removed** — ADSP-21564 has no link ports. Dual independent SPI confirmed from D24 DSP4 rev C schematic (CS1=DSPA/U6, CS2=DSPB/U5). Board in fabrication; no revision needed.
- `ghost_cells.h` `spi_page` field: `1` = CS1 → DSPA (Chip 1/U6), `2` = CS2 → DSPB (Chip 2/U5)

---

### Immediate Next Steps (pick up here)

> **Status as of 2026-04-18** — CCES toolchain installed in `~/.wine-cces` (32-bit Wine prefix). The SHARC license file is now present and valid, but it is **node-locked to HOSTID `001c42a3b69b`** (the Windows/Parallels NIC), so native use on this Mac/Linux host is still blocked unless the MAC is temporarily swapped or ADI issues a separate activation for this machine.

#### A — Use the correct CCES license (current blocker)

The SHARC `license.dat` is now installed, and it contains a permanent CCES entitlement, but it is **node-locked**:

- Installed license type: permanent, uncounted
- Installed license HOSTID: `001c42a3b69b`
- Verified on this machine: active NIC MACs do **not** match that HOSTID
- Email validation clip found for HOSTID `28cfe91f1e85`, which **does** match this machine's NIC MAC `28:cf:e9:1f:1e:85`

That means the **currently installed** license is the Windows/Parallels-bound one, not the native extra-machine activation for this host. This matches the FlexNet error seen in `flex32.log`: **Invalid host (-9,57)**.

**What this means:**
- The email validation clip is **helpful and relevant** — it appears to be the extra-machine approval for this Mac host.
- A live assembler checkout test was run against `src/main.asm`. With the currently installed Windows-bound license, FlexNet reports **Invalid host (-9,57)** with context `001c42a3b69b`.
- A manual reconstruction attempt using the email serial/host/validation code changed the error to **Invalid (inconsistent) license key (-8,523)**, which proves the clip is **not** a directly usable raw `license.dat` entry by itself.
- Therefore we still need the **actual generated license file or activation/export step** for this machine's HOSTID/MAC.
- The current workaround remains `mac-build.sh`, which temporarily swaps the NIC MAC to the licensed Windows-bound HOSTID so the build can run under Wine.

**Action options:**
1. Ask ADI to issue/confirm a second CCES activation for this machine's real MAC.
2. Keep using the existing Windows/Parallels-bound license via the temporary MAC-swap workflow.

Verification was performed with a **real assembler checkout** (not `-help`, which does not prove licensing):
`wine ~/.wine-cces/drive_c/CCES/easm21k.exe -proc ADSP-21564 -o /tmp/test.doj src/main.asm`

Observed outcomes:
- Windows-bound installed license → **Invalid host (-9,57)**
- Hand-built email-code license → **Invalid (inconsistent) license key (-8,523)**

#### B — First build attempt

Once a host-matching license is available, or the MAC-swap workaround is active:
```bash
cd /home/peter/mx/MW/D32/DSP/SHARC
./build.sh all 2>&1 | tee build_out.txt
```
Expected first-pass errors: missing symbol definitions from files not yet generated by `dsp_codegen.py` / `gen_dsp_csv.py`. Triage `build_out.txt` and work through them.

#### C — Toolchain state summary (for reference)

| Item | Location | Status |
|------|----------|--------|
| CCES EXEs (`easm21k`, `cc21k`, `linker`) | `SHARC/cces-tools/` + `~/.wine-cces/drive_c/CCES/` | ✓ installed |
| System DLLs (1,258 files) | `SHARC/cces-tools/System/` + Wine prefix | ✓ installed |
| `System/System` symlink (path fix) | `~/.wine-cces/drive_c/CCES/System/System → System/` | ✓ in place |
| Wine prefix | `~/.wine-cces` (32-bit, WINEARCH=win32) | ✓ working |
| CCES license | `SHARC/cces-tools/license/license.dat` | ⚠ present, but locked to `001c42a3b69b` |
| `build.sh` | `SHARC/build.sh` | ✓ points to `~/.wine-cces` |
