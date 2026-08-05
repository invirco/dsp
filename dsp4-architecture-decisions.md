# DSP4 architecture decisions

Status: accepted 2026-07-29 (D1-D5); D6 added 2026-08-02
Scope: DSP4 card (dual ADSP-21564 + MAX V LOGIC CPLD) as used by D24 and
D32; D6 extends scope to platform selection across the product range.
These decisions are binding for work in this repo. Change them only by
editing this file deliberately (record why), not by drifting in code.

Hardware ground truth: [MW/D24/HW/hardware-map.md](MW/D24/HW/hardware-map.md)
(derived from D24 schematics rev C). Where older plan docs
(e.g. `MW/D24/DSP/SHARC/dsp.plan.md`) conflict with it, the hardware map wins.

## D1 — The Pi (CM4) is the DSP control master; no MCU relay

- All DSP parameter writes, coefficient bundles, and meter/level reads go
  directly over Pi-mastered SPI: shared SCK/MOSI/MISO, CS1 → DSPA, CS2 →
  DSPB, SPI_RDY back on CS3/CS4 (gpiod edge-driven flow control).
- The S MCU (STM32U575) is NOT in the parameter path. Its scope is:
  power sequencing, resets (IRST_D/O/C), watchdog / Pi-hang detection with
  DSP safe-state (mute), PSU and thermal supervision.
- Timing safety is the DSP's job: parameter targets ramp on-chip
  (ramp_engine); the host never needs sample-accurate delivery.
- DSP slave-boot over Pi SPI is accepted (audio up after Linux boots).
  If fast audio-up or Pi-less failsafe is ever required, boot-image
  delivery may move to the S MCU — that is the only relay job ever on the
  table.
- Obsoletes: the Link-Port control path and MCU-relay diagram in
  `dsp.plan.md`.

## D2 — The LOGIC CPLD is developed in this repo, single-sourced slot map

- DSP4 LOGIC (MAX V 5M1270Z) HDL lives in `shared/dsp4-logic/` (card-level,
  product-agnostic — not under any `MW/<PRODUCT>/`).
- The TDM bus/slot map is defined ONCE (source table in
  `shared/dsp4-logic/`, migrating to the mx_master.csv SOT when that
  lands). Generators emit BOTH the CPLD Verilog constants/LUT and the
  SPORT config consumed by `tools/dsp/gen_dsp_csv.py`. Hand-editing either
  output is drift, same as any generated file in this repo.
- A CPLD change is behaviourally a contract bump: pin the bitstream/source
  hash (defs.lock-style key or release-notes entry) on every change.
- Committed: HDL source, constraints, slot-map source, built `.pof`
  labelled with source hash. Never committed: Quartus toolchain or license
  material (same rule as CCES).

## D3 — One DSP4 firmware serves both D24 and D32

- Single card-level firmware image ("superset firmware + product config"),
  not per-product builds:
  - Superset of I/O nodes compiled in (codec return, Pi PCM, MEMS talkback,
    snake, AUX); a boot-time product-config block enables/routes them.
  - Full 32-channel processing always present; D24 leaves 8 input strips
    unused/muted.
  - ONE stable DSP parameter address map shared by both products. Product
    differences live at the contract layer (d24.csv / d32.csv cell sets,
    ProductScope in the future SOT), never as diverging address maps.
- Consequences accepted: coupled releases (a DSP fix revalidates both
  products); single CCES build target.
- Revisit trigger: if one product needs DSP features the other's cycle
  budget cannot carry, fork deliberately at that point — do not pre-fork.

## D5 — Fixed-point audio path, one numeric spec across targets

- Decided 2026-07-31 (pre-shipping window, no hardware run yet): the
  DSP4 audio sample path converts from FP32 to fixed point, governed by
  ONE numeric specification (`shared/numeric-spec.md`) shared with the
  future FPGA mixer engine (see `fpga/`). Rationale: fixed is the only
  format native-fast on both the dual-format SHARC+ and every FPGA
  family; wide accumulators improve LF biquad noise and make mix
  summing exact.
- The float kernel work is ARCHIVED, not lost: git tag
  `float-kernels-2026-07-31`. Float remains the buildable mainline only
  until each kernel family is replaced by its verified fixed version;
  no further float feature work.
- Exception: FX engines (reverbs) STAY FLOAT indefinitely — the SHARC+
  is dual-format per instruction and mixed-format is free; converting
  FX is a separate decision if ever needed.
- The contract does NOT change: the SPI wire keeps carrying float32
  words; a single on-target conversion at the parameter-write/ramp
  boundary feeds the fixed kernels. mx26, cell tables, address map,
  ghost cells and host tooling are untouched.
- Acceptance: every converted family must pass the golden-vector
  harness (float64 reference in tools/dsp/) within the tolerances in
  the numeric spec, plus a clean fit-proxy build, before it replaces
  the float version.

## D4 — D24 node-graph topology follows the schematic, not the old plan

- Mix summing lives on chip 1 (DSPA emits 128 mix buses over 8× TDM16);
  chip 2 (DSPB) is bus processing + output routing (DAC 1-16, DAC MAIN,
  codec/snake, NET 1-32).
- Change path: `tools/dsp/gen_dsp_csv.py` → `dsp.csv` →
  `tools/dsp/dsp_codegen.py` → node ASM. Generated files are never edited.

## D6 — Platform split: SHARC to 32 ch/48 kHz, FPGA from 32 ch/96 kHz up

- Decided 2026-08-02. Two engine platforms, split by product tier:
  - **Products up to 32 ch @ 48 kHz** (D24/D32 line): the DSP4 card
    (dual ADSP-21564 + MAX V CPLD) remains the engine. D1-D5 stand
    unchanged; nothing in D6 disturbs the shipping path.
  - **Products at 32 ch @ 96 kHz and above** (64/128-ch tiers, d64/d128
    definitions): a single-chip FPGA engine — Zynq UltraScale+ class,
    parts and pricing per `fpga/platform-shortlist.md` (K26/ZU5EV
    flagship; Agilex 5 E is the named second source). No new multi-DSP
    designs above 32 ch/48 kHz.
- Rationale (analysis in `fpga/platform-shortlist.md`): at 96 kHz with
  d128-grade processing the multi-SHARC route is equal-or-costlier on
  silicon and carries the multi-chip system tax (backplane, per-chip
  memory/boot/power, inter-chip TDM scheduling — which needs a
  CPLD/FPGA anyway); its spec-creep costs discrete chips, the FPGA's
  costs utilization %. Streaming (MW-Net, full-bandwidth Dante card)
  is native to the FPGA and required by the product definitions.
- The FPGA is a **third codegen backend, not a fork** (extends D3's
  one-firmware principle): same contract flow (defs.lock → dsp.csv),
  an `fpga_codegen.py` beside `dsp_codegen.py` in `tools/dsp/`, one
  RTL/codegen platform spanning 32-128 ch with per-product generated
  tables; `dsp_simulate.py` golden vectors are normative; the D5
  numeric spec (`shared/numeric-spec.md`) governs both targets.
- Networking (binding, from `fpga/README.md`): own-brand I/O rides the
  proprietary MW-Net isochronous P2P link (no PTP/IP; clock-from-link;
  switchless premise); standards interop lives on a full-mixer-
  bandwidth Dante option card; no native MW-Net computer endpoints —
  DAW connectivity is class-compliant USB at the edges.
- Design gates before FPGA code lands (tracked in `fpga/README.md`):
  architect-at-128×128/build-small rules; 16-bit address-space check
  at d128 scale; `ch.fir` tap ceiling into the product definition; FX
  placement (fabric vs A53 vs hybrid); MW-Net frame-format spec.
- Revisit triggers: AMD supply/pricing turns hostile → Agilex 5 E
  plan-B (`fpga/platform-shortlist.md`); a future ≤32 ch product
  needing 96 kHz forces either the FPGA entry tier (7020-class) or a
  deliberate DSP4-at-96k exception recorded here.

## D7 — Fabric-only FPGA baseline; per-tier hybrid FX (SHARC sidecar)

- Decided 2026-08-04 (scope amendment text in
  `fpga/platform-shortlist.md`; research-phase costing may still move
  part choices — not the rules below).
- **Product scope, 96 kHz range**: no onboard recording, no USB UAC
  audio. Multitrack capture rides the customer's Dante ecosystem: the
  Dante slot gets TDM lanes + clock + control and inherits the fitted
  card's capacity (Broadway/Brooklyn/HC = market-tiered, customer-paid
  card SKUs) — D6's "full-mixer-bandwidth Dante card" and
  "DAW connectivity is class-compliant USB" clauses are withdrawn.
  MW-Net is confined to own-brand I/O boxes and remains the only
  full-mixer-bandwidth network path (no recording, no computer
  endpoints). A standalone MW-Net recorder appliance may return later
  as a separate catalog product.
- **Engine baseline**: pure-fabric FPGA at every tier — D6's
  "Zynq US+ class / K26-ZU5EV flagship" part naming is superseded
  (the D6 platform SPLIT itself stands). The CM4/CM5 is sole control
  master (D1 pattern) and never touches audio. No GT transceivers
  anywhere; the per-tier pin budget drives package selection.
  Baseline parts per the shortlist amendment (Spartan US+ / GT-less
  Artix-7 / Artix US+; Lattice sizing pass open for the 32-ch tier).
- **Hybrid FX strategy (the mandate)**: FX placement is a PER-TIER
  PARTITION of the same dsp.csv graph across existing codegen
  backends — not a per-product fork:
  - 32/64-ch tiers: light FX in fabric (TM engine); no sidecar —
    protects the cost floor and the candidate Lattice part.
  - 128-ch flagship: launches with a SHARC (21569-class) FX sidecar,
    TDM-attached as ordinary slot-map banks, SPI param plane
    unchanged; FX nodes emit via `dsp_codegen.py`, everything else
    via `fpga_codegen.py`; one golden harness validates both sides.
  - The sidecar is a TRANSITION component: the fabric TM-FX engine is
    the designed-in cost-down, and the flagship board places the
    sidecar on a depopulatable boundary (removal = BOM change, not
    respin).
  - FX round-trip latency (TDM transit + SHARC block size) is in the
    delay-compensation budget from day one.
  - Rationale: hybrid efficiency scales with tier (FX spec grows,
    BOM sensitivity falls, unit volume falls) and with lifecycle
    (sidecar early, fabric late) — D6's buy-vs-build logic applied
    inside a single product.
  - Clarification of D6's "no new multi-DSP designs" rule: it bars
    multi-DSP MIXING engines; a single FX sidecar is not one and is
    permitted by this decision.
- Design gates updated (tracked in `fpga/` docs): per-tier pin-budget
  table; Lattice 32-ch sizing incl. the 18×18 composition factor;
  per-part DDR verification; coefficient-conversion location
  (on-fabric float→fixed converter preserving the D5 float wire vs
  Pi-side prep — decide before table formats freeze); `ch.fir` tap
  ceiling; 16-bit address check at d128 scale; MW-Net frame spec.
- Revisit triggers: FIR ceiling lands high → flagship stays on
  wide-DSP silicon (AMD/Altera); a small tier specs disproportionate
  FX → sidecar logic re-enters at that tier; fabric TM-FX proven at
  volume → depopulate the sidecar.
