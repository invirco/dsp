# FPGA mixer engine — idea gathering

Status: exploration, started 2026-07-31. Nothing here is binding; this
folder collects feasibility notes for porting the DSP4 processing to an
FPGA for larger mixers — the product window is **32 channels and up at
96 kHz+**, where the dual-21564 card runs out of fabric slots, memory,
or cycles. The competing architecture for that window is multiple DSP
modules on a CPLD-muxed TDM backplane (sketched in
[../ideas.md](../ideas.md), "128×128 TDM DSP Fabric"); a single FPGA
replaces that backplane-and-modules story with one chip, and natively
carries the own-brand networked-I/O link (a proprietary isochronous
P2P protocol over standard GbE — see the I/O sketch below); standards
interop stays on a Dante option card.

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
  48 kHz sample (~2600 at 96 kHz), so ONE time-multiplexed MAC engine
  serves hundreds of channel×bus sends from BRAM coefficient/state
  tables. At 96 kHz a full 64×64 matrix (4096 sends) needs two MAC
  lanes instead of one — trivial against the hundreds of DSP slices on
  any candidate part; sample rate halves the multiplexing depth but
  doesn't change the architecture.
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

**Control-plane split (established by the D5 kernel conversion):** the
firmware keeps the parameter plane FLOAT (wire, dispatch, ramps) and
converts to Q4.28 "shadows" once per block inside each kernel. On the
FPGA this becomes the hardware/software boundary: the control CPU
(SoC ARM / soft core / the Pi) runs the SAME float control logic at
block rate and writes shadows + offset-coefficient sets into
double-buffered BRAM; the fabric engines only ever see fixed values.
Same semantics and quantization points on both targets — they differ
only in WHERE the float control code executes. (The one configuration
this strains is a CPU-less pure-fabric part — not on the platform
shortlist; it would force fixed words onto the wire.)

## Sketch of the engine (strawman, to be argued with)

- Time-multiplexed pipelines fed by schedule ROM/BRAM generated from
  dsp.csv: one biquad engine, one dynamics engine, one MAC/summing
  engine, one delay-address engine against DDR, all walking per-node
  state/coeff tables. Channel count scales with clock budget + BRAM,
  not with code size.
- Parameter plane: SPI (or AXI-lite behind a SoC bridge) → parameter
  RAM → ramp engine → coefficient staging (same crossfade-swap idea as
  the GEQ `coeffs_next` staging).
- I/O: TDM lanes as today (the slot-map SOT extends), plus network
  audio in a two-tier split (decided direction, 2026-08-02):
  - **Standards interop (Dante/AES67) lives on an option card**, not in
    fabric. The card presents itself to the FPGA as TDM/I2S lanes, so
    to the slot-map SOT it's just another bank of slots and carries
    none of its protocol complexity (PTP servo, SAP/SDP discovery,
    IGMP) into the mixer platform.
    **Bandwidth requirement (2026-08-02): the Dante card and the prop
    link are FULL-mixer-bandwidth paths** (d128: 128 in / 64 out @
    96 kHz); only USB-SSD recording and DAW streams may be
    channel-limited as product decisions. Consequences: (a) a
    Brooklyn-II-class module (32×32 @ 96 kHz) is NOT sufficient — the
    card needs Dante HC / Dante-IP-core class (256×256 @ 96 kHz) or
    ganged modules; (b) the card boundary at ~192 ch @ 96 kHz is
    ~12× TDM-16 lanes at 49 MHz bit clock — chunky but routable;
    alternatively the card could speak the prop link itself (one GbE
    lane, same framing as I/O modules) — decide with the card design.
  - **Own-brand I/O modules connect over a proprietary isochronous
    P2P link handled natively by the FPGA** (decided 2026-08-02 over
    an AES67-subset approach — the AES50/GigaACE/SoundGrid pattern,
    not the Dante one). Design point: *proprietary payload, standard
    plumbing* — commodity GbE PHYs and standard Ethernet frames with
    our own EtherType (cheap parts, cable diagnostics, Wireshark-able),
    filled with fixed-size, fixed-cadence audio blocks whose channel
    layout is generated from the same slot-map SOT. Conceptually the
    link is the TDM backplane over a cable. **No PTP, no IP/RTP**: on
    a switchless P2P link the continuous frame stream carries the
    sample clock itself (receiver PLLs to the frame cadence, AES50
    style), which dissolves the distributed-sync problem and puts
    latency in the tens-of-µs class instead of AES67's ~1 ms packet
    time. The residual control plane (link bring-up, module
    enumeration) is small enough for a soft core or the Pi.
    Topologies: star (each module home-run to a console port) and
    daisy chain (each module has two PHYs, does cut-through forwarding
    and regenerates the clock with a fixed, known per-hop delay).
    Switchless is a design premise, not an accident: inserting a COTS
    switch reintroduces jitter and forces timestamps + buffering —
    i.e. rebuilds AES67. If switched infrastructure is ever required,
    that traffic belongs on the Dante card.
- Platform candidates: Zynq UltraScale+ / Versal (ARM cores could
  absorb FX, the AES67 protocol stack, and even the Pi role) vs
  mid-range Artix/Cyclone + external Pi keeping today's D1 architecture
  unchanged. Keeping the Pi keeps the whole host stack identical —
  attractive for a first prototype. With standards interop pushed to
  the option card and the own-brand link being fabric-friendly (see
  I/O above), full AES67 no longer forces an SoC part — the SoC case
  now rests on FX and integration, not networking. Concrete part
  proposals per tier: [platform-shortlist.md](platform-shortlist.md).
  Toolchain rule extends unchanged: never commit Vivado/Vitis/Quartus
  or license material.

## Design approach: architect at max, bring up small (2026-08-02)

Design the architecture for the 128×128 ceiling from day one; build
first hardware at the smallest sellable tier. The split:

**Fixed at 128×128 scale immediately (these fossilize):**

- Address space, node ID scheme, schedule-ROM entry width, BRAM
  state/coeff record layouts — field widths come from the max config;
  spare bits are free now, contract breaks later.
- The scaling mechanism itself: at 96 kHz (~2600 cycles/sample) a
  128×128 send matrix needs ~7 MAC lanes, so the architecture is
  "N parallel lanes per engine, N chosen per product" — and the first
  thing to design is the schedule generator in `fpga_codegen.py` that
  partitions the dsp.csv graph across lanes. Scaling then lives in the
  generator; scale-down is regeneration from a smaller matrix (the
  same move the repo makes everywhere else).
- The link frame format: channel fields, daisy-chain aggregate
  capacity, marketed per-lane number — permanent once modules ship.
- DDR bandwidth + BRAM budgets at 128 ch (paper exercise; decides
  whether the flagship needs UltraRAM/DDR4 — see
  [platform-shortlist.md](platform-shortlist.md)).

**Sized to the floor as well as the ceiling:** the 32-ch tier wants
7020-class silicon, so engine RTL must fit DOWN — parameterized lane
counts and table depths, BRAM by inference (7-series has no UltraRAM;
device-specific primitives behind wrappers), no baked-in DDR4/A53
assumptions. Per-tier resource budgets are part of the design, not an
afterthought.

**First build:** smallest sellable tier on the flagship architecture —
engines on a KV260 or 7020 board, a 32-ch product config generated
from the real contract flow, validated against dsp_simulate.py golden
vectors. Only generated tables and lane counts differ from the
128-ch product (D3's one-firmware rule, applied to fabric).

**Anti-pattern to refuse:** a quick 32-ch prototype with hardcoded
widths "to get audio passing" — that's how schedule formats, address
fields, or link framing end up unable to stretch, i.e. the per-product
fork D3 exists to prevent.

## What would make or break it (open questions)

1. Number format — analysed in [number-format.md](number-format.md):
   prefer hardened-FP32 silicon (Agilex/Cyclone 10 GX/Versal) for a
   near-1:1 kernel port; if fixed point is forced, contain it inside
   the engines with float interfaces. Either way dsp_simulate.py
   (float64) becomes the normative golden model, and mix summing is a
   candidate for exact wide-accumulator fixed even in an FP32 design.
2. FX strategy: fabric redesign vs hybrid (DSP/ARM sidecar).
3. Coefficient computation location: today biquad coeffs are computed
   on-DSP from cell values; on FPGA either a soft/hard CPU does this or
   the Pi precomputes (protocol already carries raw words — either
   works, but pick one and note it in the contract docs).
4. Scale target — ANSWERED (2026-08-02): the product window is 32
   channels and up at 96 kHz+. Size silicon for a 64×64 @ 96 kHz
   headline configuration so 32-channel products are comfortable and
   128-channel variants are a clock/BRAM stretch, not a redesign.
5. Latency budget: FPGA can beat the DSP's block-32 latency
   (sample-serial processing) — decide whether that's a product goal
   or whether block processing is kept for simplicity.
6. Network audio — direction set (2026-08-02): standards interop on a
   Dante option card (TDM-facing, slot-map-mapped); own-brand I/O
   modules over the proprietary isochronous P2P link described in the
   I/O sketch (own EtherType on standard GbE, clock-from-link, no
   PTP/IP/RTP), star or daisy-chain. An AES67-subset variant was
   considered and rejected: its benefits (COTS-switch operation,
   standards endpoints) are either excluded by the switchless-P2P
   premise or already served by the Dante card.
   Capacity requirement SET (2026-08-02): the link is a full-mixer-
   bandwidth path — headline capacity covers the whole I/O complement
   (d128: 128 in / 64 out @ 96 kHz). The math holds on one full-duplex
   GbE lane: 128 ch ≈ 393 Mb/s + 64 ch ≈ 197 Mb/s payload, i.e.
   ~40-60% utilization with framing overhead. Consequence for daisy
   chains: all modules on a chain share one lane's capacity, so
   chain depth × module channels ≤ lane budget — full-density systems
   use star or dual-star, chains serve distributed partial I/O.
   Remaining opens: the frame-format spec itself; per-hop latency
   figure and max chain depth; redundancy (dual-cable?); whether
   module control/management rides in-band or on a sideband; and the
   option-card electrical/slot-map boundary (full-bandwidth TDM vs
   card-speaks-the-link — see I/O sketch). The I/O modules' own
   FPGA/PHY design becomes a sibling project sharing the link block.
7. EARLY ACTION ITEM — 16-bit address-space check at 128×128: on
   paper, count nodes × params for a full 128-channel graph against
   the flat 16-bit parameter map (minus the 0xF000+ config block).
   This is the one contract-level ceiling that is expensive to change
   after anything ships; do it before freezing any FPGA table format.

## Relationship to existing repo rules

- `shared/dsp4-logic/` conventions (slot-map SOT, timing conventions,
  hash-pinned bitstreams) are the template for how FPGA artifacts
  would be managed — same D2-style rules, bigger chip.
- This folder is idea-gathering only; adopting any of it becomes a
  numbered architecture decision in dsp4-architecture-decisions.md
  (or a successor doc) before code lands.
