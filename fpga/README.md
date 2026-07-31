# FPGA mixer engine — idea gathering

Status: exploration, started 2026-07-31. Nothing here is binding; this
folder collects feasibility notes for porting the DSP4 processing to an
FPGA for larger mixers (128+ channels, where the dual-21564 card runs
out of fabric slots, memory, or cycles).

## The two headline questions

### 1. Could the FPGA use the same algorithms as the DSP?

**Yes at the semantic level, with one deliberate decision (number
format), and no at the bit-exact level — which doesn't matter.**

What "same algorithm" actually means here is pinned down by how this
repo already works: node behaviour is defined by the ~30 kernel
generators in `tools/dsp/dsp_codegen.py` (biquad EQ, dynamics with the
shared envelope model, delay pools, ramp engine, routing/summing), and
node *semantics* are specified by dsp.csv params + the cell tables
(coefficient formats, dB laws, ramp profiles). All of that is
target-independent. Concretely:

- **Biquads (EQ/HPF/LPF/xover/anti-FB/GEQ)**: coefficients are computed
  host/DSP-side from the same cell values; an FPGA biquad engine
  consumes identical coefficient sets. Standard practice: transposed
  direct-form II with wide accumulators (48-64 bit fixed point) —
  audibly transparent at 48 kHz, and *better* numerically than
  single-precision float at low frequencies. Alternatively some
  families (Cyclone 10 GX, Agilex, Versal) have hardened FP32 DSP
  blocks if float parity is wanted.
- **Dynamics (gate/comp/limiter)**: envelope followers + gain computers
  are a few multiplies and compares per sample; port directly. The
  attack/release *frame-count semantics* come from the ramp/cell tables
  and stay identical.
- **Ramp engine**: trivially an FPGA block, same profiles table.
- **Summing/routing**: this is where the FPGA *wins outright* — the
  128-bus inter-chip fabric limit and the chip1-block3/chip2-L2 memory
  ceilings simply disappear; a 250 MHz fabric gives ~5200 cycles per
  48 kHz sample, so ONE time-multiplexed MAC engine serves hundreds of
  channel×bus sends from BRAM coefficient/state tables.
- **Delays**: FPGA boards bring DDR — the whole xSPI-PSRAM "RAM
  insurance" problem (tasks.md HW section) is native here.
- **Hardest to port: the FX engines** (reverbs). Feasible in fabric but
  a redesign, not a port. Pragmatic option used by large consoles:
  hybrid — FPGA does strips/summing/buses, FX stays on a DSP or on the
  SoC's ARM cores.

Bit-exactness with the SHARC (FP32, its own rounding) is not achievable
and not a goal; the goal is *cell-value parity*: same cell in → same
dB/frequency/time behaviour out, within measurement tolerance. The
existing `dsp_simulate.py` golden model is the reference for that (it
already validates the SHARC the same way).

**Key architectural thesis**: the FPGA is a *third codegen backend*, not
a fork. `dsp.csv` (from the same gen_dsp_csv.py/slot-map SOT) already
expresses the full graph; an `fpga_codegen.py` would emit schedule
tables, coefficient/state RAM maps and address-decode tables for a
time-multiplexed engine, exactly as dsp_codegen.py emits node ASM. The
no-fork rule (D3) extends naturally: one graph, N execution targets.

### 2. Could it use the same matrix control protocols?

**Yes — essentially for free. This is the strongest part of the story.**

The contract stack was built DSP-agnostic end to end:

- mx26 SOT → `_matrix.csv` cells → flat 16-bit parameter addresses +
  tables + ramp profiles. Nothing in the contract knows it's a SHARC.
- The wire protocol (spi_handler.asm / product-config.md) is two 32-bit
  words: `{addr, flags/ramp-id}` + `{value}`, plus the 0xF000+ config
  block. An FPGA implements the same SPI slave + parameter RAM +
  address decode in a few hundred LUTs — the *generated dispatch table*
  becomes a generated address-decode/BRAM-init instead.
- Host side is unchanged: the Pi remains control master (D1),
  `tools/pi/dsp4_config.py` works as-is, ghost_cells.h / mx_dsp_map.h
  stay valid because the address map is generated from the same SOT.
- Ramping stays on-target (D1's "host never needs sample-accurate
  delivery"), served by the same ramp-profile tables.

So a larger FPGA mixer would join the existing contract flow like any
product tree (`MW/<PRODUCT>/` + scaffold-product.sh), with the FPGA
consuming the same defs.lock-pinned artifacts.

## Sketch of the engine (strawman, to be argued with)

- Time-multiplexed pipelines fed by schedule ROM/BRAM generated from
  dsp.csv: one biquad engine, one dynamics engine, one MAC/summing
  engine, one delay-address engine against DDR, all walking per-node
  state/coeff tables. Channel count scales with clock budget + BRAM,
  not with code size.
- Parameter plane: SPI (or AXI-lite behind a SoC bridge) → parameter
  RAM → ramp engine → coefficient staging (same crossfade-swap idea as
  the GEQ `coeffs_next` staging).
- I/O: TDM lanes as today (the slot-map SOT extends), or the natural
  step up — network audio directly into fabric.
- Platform candidates: Zynq UltraScale+ / Versal (ARM cores could
  absorb FX and even the Pi role) vs mid-range Artix/Cyclone + external
  Pi keeping today's D1 architecture unchanged. Keeping the Pi keeps
  the whole host stack identical — attractive for a first prototype.

## What would make or break it (open questions)

1. Fixed-point migration plan per kernel family (accumulator widths,
   saturation policy) — needs a golden-model comparison harness
   (extend dsp_simulate.py to emit test vectors; same harness then
   validates the SHARC too).
2. FX strategy: fabric redesign vs hybrid (DSP/ARM sidecar).
3. Coefficient computation location: today biquad coeffs are computed
   on-DSP from cell values; on FPGA either a soft/hard CPU does this or
   the Pi precomputes (protocol already carries raw words — either
   works, but pick one and note it in the contract docs).
4. Scale target: define "larger" (e.g. 128×64) to size DSP blocks,
   BRAM and DDR bandwidth before choosing silicon.
5. Latency budget: FPGA can beat the DSP's block-32 latency
   (sample-serial processing) — decide whether that's a product goal
   or whether block processing is kept for simplicity.

## Relationship to existing repo rules

- `shared/dsp4-logic/` conventions (slot-map SOT, timing conventions,
  hash-pinned bitstreams) are the template for how FPGA artifacts
  would be managed — same D2-style rules, bigger chip.
- This folder is idea-gathering only; adopting any of it becomes a
  numbered architecture decision in dsp4-architecture-decisions.md
  (or a successor doc) before code lands.
