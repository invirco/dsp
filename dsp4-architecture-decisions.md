# DSP4 architecture decisions

Status: accepted 2026-07-29 (D1-D5); D6 added 2026-08-02; D7 2026-08-04;
D8 2026-08-05; D10 2026-08-21. **D9 (2026-08-06) is a DRAFT awaiting
sign-off — not binding; see its banner.**
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

**Supporting evidence added 2026-08-22 (pin audit).** The 32 ch / 48 kHz
line is not only an engineering preference — it is where the part's
external SPORT clock runs out. Data sheet Rev. A Table 14 caps
`fSPTCLKEXT` at **31.25 MHz when transmitting data or frame sync** (and
at fSCLK0, which is 61.44 MHz on this clock tree). At 48 kHz a TDM16
lane needs 24.576 MHz BCK and passes with 27 % headroom; at 96 kHz it
needs 49.152 MHz and exceeds the limit outright. See
`MW/D32/DSP/dsp4-pin-audit.md`.

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
  table; Lattice 32-ch sizing incl. the 18×18 composition factor
  (**first pass done 2026-08-06 — `fpga/sizing-32ch.md`: DSP is not the
  constraint on either candidate; delay memory forces external DRAM**);
  per-part DDR verification; coefficient-conversion location
  (on-fabric float→fixed converter preserving the D5 float wire vs
  Pi-side prep — decide before table formats freeze); `ch.fir` tap
  ceiling; 16-bit address check at d128 scale; MW-Net frame spec.
- Revisit triggers: FIR ceiling lands high → flagship stays on
  wide-DSP silicon (AMD/Altera); a small tier specs disproportionate
  FX → sidecar logic re-enters at that tier; fabric TM-FX proven at
  volume → depopulate the sidecar.

## D8 — DSP4 rev D: CM4-core SPI control, supervisor shrink, CPLD downsize, xSPI PSRAM

- Decided 2026-08-05. Scopes the DSP4 card rev D (driven by the xSPI
  PSRAM addition; part candidates and the rev-C pin analysis in
  tasks.md HW section). Amends D1's S-MCU clause; D1's
  master-and-no-relay rules otherwise stand unchanged.
- **CM4 dedicated core owns all SHARC SPI control** (refinement of
  D1, not a new master): one isolated A72 core (isolcpus, pinned
  thread, gpiod CS) runs param writes, meter polling, scene bursts,
  and the host-side float control plane (coefficient prep). The GUI
  never shares that core. Host timing remains non-critical by design
  (on-chip ramps, per D1).
- **Supervisor MCU shrinks; boot-relay fallback DELETED.** The only
  jobs that must stay off the Pi are watchdog/Pi-hang detection with
  DSP safe-state mute, power sequencing/resets, and PSU/thermal
  supervision — G0-class work. D1's "boot-image delivery may move to
  the S MCU" clause is withdrawn: DSP slave boot over Pi SPI2 is the
  permanent boot path (CM4 boots fast enough; scenes live on CM4
  storage; no Pi-less operation requirement, so nothing needs ROM).
  H1S1 (U7, STM32U575RIT6): near-term drop-in STM32U535RET6 (same
  LQFP-64 / U5-family pinout; firmware ~266 KB fits 512 KB); rev D
  target is G0-class or merging into U8 — GATED on an inventory of
  U7's SRX/MRX matrix-comms role (the one job not yet dispositioned).
- **xSPI PSRAM lands; Pi runtime link moves.** One xSPI PSRAM per
  ADSP-21564 on OSPI0 (bulk delay memory). The Pi RUNTIME param link
  moves to SPI0/SPI1 per DSP; SPI2 becomes boot-only — resolving the
  OSPI0/Port-A pin conflict found in the rev-C schematic review. No
  boot NOR (see fallback deletion above). Open items: OSPI I/O
  voltage domain (3V3 VDD_EXT vs 1.8 V octal parts; APS6404L 3V3
  quad fallback), exact 21564 OSPI clock ceiling, XDELAY DMA-pattern
  prototype.
- **LOGIC CPLD → 5M570ZT144C4N** (from 5M1270ZT144C4N, ~13% used).
  Verified 2026-08-05 against the real schematic-extracted qsf
  (scratch Quartus run): identical TQFP-144 land pattern; exactly ONE
  illegal pin (PIN_137 = MEMS input, not user I/O on the 570Z die —
  one trace moves); C4 grade closes 51.95 MHz vs 49.152 required;
  **C5 grade FAILS (36.9 MHz) — never substitute it**; 148/570 LE
  (26%), 67/114 pins. Riders: ~5% timing margin is thin — the STA
  gate in shared/dsp4-logic/build.sh stays mandatory on every RTL
  change; pipeline the divider path if margin erodes. 5M240ZT144
  fits (62%) but leaves no growth room — rejected.
- **Hardwiring pass** (CPLD muxing → PCB copper): permitted for
  product-static routing only (net_sel is already fixed per product
  in RTL), and only for facts PROVEN at rev-C bring-up — BCKI/FSI
  pair order, CKRE/MFD, and D24 within-ADC8 slot order are still
  provisional and stay in reprogrammable logic until verified. The
  irreducible CPLD core remains: clock generation, Pi PCM reframer,
  reset glue. D24/D32 differences that become copper are
  0R-strap/BOM-variant choices, recorded in the slot-map SOT.
- **Sequencing**: rev C bring-up first (verifies the provisional TDM
  facts and the plumbing register model), then rev D schematic
  freeze. The U535 drop-in may ride any earlier rev-C BOM update.
- Revisit triggers: SRX/MRX inventory shows more than G0-class load →
  keep a U5-class supervisor; rev-C bring-up overturns a provisional
  fact → the affected routing stays in the CPLD, not copper.

## D9 — FPGA parameter plane: float wire, on-fabric ingest conversion [DRAFT]

> **STATUS: DRAFT — awaiting PW sign-off. Not binding until this banner
> is removed.** Argued in session 2026-08-05; written up 2026-08-06 from
> that discussion. Everything below is the proposal, not accepted policy.

- Scope: the parameter/control plane of the FPGA mixer engine (`fpga/`),
  the fabric-side counterpart to D5's SHARC parameter boundary. Closes
  the **coefficient-conversion location** gate that D7 left open
  (on-fabric converter vs Pi-side prep) and shortlist action item 8.
- **The SPI wire stays float32 — unchanged from D1/D5.** Same protocol,
  same address map, same cell tables, same host tooling. The CM writes
  float words to an address; mx26, ghost cells, and the D32/D24 control
  path do not learn that the engine underneath is fabric rather than
  SHARC. This is the whole point: one control plane across both engines.
- **Conversion happens ON FABRIC, at ingest** — not on the Pi. A single
  small float→fixed converter sits at the SPI ingest boundary and feeds
  the parameter RAM in the destination format.
  - Rationale: Pi-side prep would push per-address Q-format knowledge
    into the host, forking host tooling per engine and re-forking it on
    every table change — exactly the coupling D3/D5 removed. It would
    also make the float wire a lie (float-shaped words carrying
    pre-quantized values).
  - Cost is small and bounded: conversion is control-rate, so ONE
    time-multiplexed converter serves every address. It is not
    per-node hardware.
- **Per-address format map, generated.** Each parameter address carries
  its target format (Q profile, saturation policy, semantic) in a table
  generated from `dsp.csv` by `fpga_codegen.py` — same generator-owned
  discipline as the SHARC dispatch tables. Formats are governed by
  `shared/numeric-spec.md` (D5); the FPGA does not get a second numeric
  spec.
- **Ramps run FIXED in fabric** — this is the deliberate divergence
  from D5. On SHARC the entire parameter plane stayed float with a
  per-block FIX inside each kernel (float adds are free on a
  dual-format core). Fabric has no float adder worth spending, so the
  ramp engine increments in the destination fixed format directly:
  exact, cheap, and control-rate. Consequence to verify against the
  golden harness: ramp trajectories are quantized earlier than on
  SHARC, so ramp-precision tolerance is a numeric-spec question, not a
  free choice.
- **Sample-serial audio, block-rate control.** The audio datapath is
  sample-serial (channels time-multiplexed through the shared TM
  engine); the control plane updates at block rate. This is what makes
  the single shared converter and the single ramp engine sizeable at
  all — they have a whole block of cycles to service every address that
  changed. Sizing follows from block length × channel count, and
  belongs in the per-tier pin/resource budget.
- **Acceptance**: unchanged in kind from D5 — the float64 model in
  `tools/dsp/` stays the normative reference, and the fabric engine is
  validated as tolerance-vs-golden, never target-vs-target.
- Open items this decision does NOT settle: exact parameter-RAM sizing
  per tier; ramp-precision tolerance for fixed ramps (numeric-spec
  amendment); whether meters return over the same path or a separate
  readback channel.
- Revisit triggers: a tier lands on hard-FP silicon where float ramps
  are genuinely free (then the SHARC pattern applies unchanged); or the
  format map proves too dynamic to generate, which would mean the
  address space is under-specified upstream in mx26.

## D8 amendment (PW, 2026-08-20) — CM4 core also masters analog mic-pre gain

The D8 dedicated CM4 core's SPI scope extends to the analog mic preamp
gain: one control-plane master for SHARC boot/runtime params, coeff prep,
AND preamp gain. Rev-C copper terminates the housekeeping SPI selects
(!CS_L/!CS_C/!CS_M) at H1S1, so direct CM4 mastering is rev-D wiring:
CS_M rides a spare stack CS line (CS5 or CS6 — CS7/8 are permanently the
CM4-owned SWD_EN selects, CS1-4 the boot bus; the 2026-08-20 H1S1
CS1-6→inputs flash makes CS5/6 safe to claim). Three housekeeping selects
vs two spare lines: if only CS_M moves, CS5 suffices; all three need one
more route or a select expander. CM4 CS is gpiod-driven — the constraint
is copper reach, not SPI CE hardware. Feeds the supervisor-shrink scope.

## D10 — The CPLD is the DSP clock source; 24.576 MHz into a 0.9 V pin

Accepted 2026-08-21, from the ADSP-2156x datasheet (Rev. A, Feb 2026) and
the rev-C bring-up. This is a clock-discipline contract, not a preference:
rev C violated both halves of it and neither SHARC has ever been shown to
run.

**The contract.**

- The LOGIC CPLD is the **single clock source** for both SHARCs'
  `SYS_CLKIN0`, derived from the one 49.152 MHz XO (Y1) that also makes
  every audio clock. One oscillator on the card, one clock domain,
  everything audio-rational. Programmability is the point: the divider
  lives in RTL, so the DSP clock can be changed without a board spin.
- `dsp_clk` = **24.576 MHz** = sysclk / 2 = 512 × 48 kHz, 50 % duty from a
  dedicated toggle flop. The part specifies **fCKIN = 20–30 MHz** (Table
  23, crystal and external clock alike) and tCKINH/L ≥ 16.67 ns. The raw
  49.152 MHz XO is 64 % over that maximum, which is the violation — the
  reset-default CGU arithmetic is a separate check and it passes at both
  frequencies. Get it right: the HRM gives **PLLCLK = SYS_CLKIN × MSEL / 2**
  and the reset defaults are **MSEL = 40, CSEL = 1, SYSSEL = 2, S0SEL = 4**
  (HRM Tables 2-10 / 2-11 and the register diagrams). At 24.576 MHz that is
  PLLCLK 491.5 MHz, CCLK 491.5 MHz, SYSCLK 245.8 MHz, SCLK0 61.4 MHz — all
  in range (fPLLCLK 0.40–1.00 GHz, fCCLK 400–1000 MHz, fSYSCLK 200–500 MHz,
  fSCLK0 30–125 MHz), so the boot ROM runs correctly clocked with no CGU
  programming at all. At 49.152 MHz it was PLLCLK/CCLK 983 MHz: inside the
  family maxima, but about double the 21564's grade. Any future change to
  the divider must keep fCKIN inside 20–30 MHz **and** re-check all four
  reset-default derived clocks against those ranges. An earlier version of
  this decision said the PLL was asked for 2.95 GHz and could not lock;
  that was wrong (it dropped the /2 and used MSEL = 60), and no conclusion
  should rest on it.
- `SYS_CLKIN0` is a **VDD_INT-domain pin** — the only signal pin on the
  part that is. Table 7 puts it in the VDD_INT domain, Table 19 makes its
  absolute maximum `−0.3 V to VDD_INT`, and the operating conditions give
  VIHCLKIN = 0.68 V … VDD_INT with VILCLKIN ≤ +0.12 V. The datasheet is
  explicit: the external clock "must not exceed the internal (VDD_INT)
  voltage level". **A 3.3 V CMOS output may not drive this pin.** Any
  board carrying a DSP4-derived clock chain must level-translate between
  the CPLD and each SHARC and must state the target level (0.68–0.855 V)
  in its schematic notes.
- CLKIN jitter is not in the audio path — the SPORTs are clocked
  externally by BCKI/FSI from the same CPLD — so translation may be
  passive. Correct levels beat elegant clocking here.

**Rev-C state and the bodge.** Rev C drives the pin at 3.3 V through 22 R
(R65 → DSPA U6 pin 5, R33 → DSPB U5 pin 5), so both parts have had their
clock input clamped ~2.4 V above absolute maximum, continuously, since
March, with the clamp current injected into the +0.9 V core rail. **Both
halves are now corrected on the bench card and the contract above is met
by measurement:** the ÷2 in the CPLD (`dsp4_logic.a1f6672af6c3`, programmed
2026-08-21) and the divider fitted 2026-08-21 (1 k replacing R65/R33 plus
330 R from each DSP-side pad to GND — ratio 0.248, the specified 1k2/390 R
to within 1 %), scope-verified by PW at the R33/R65 pad: **0.70–0.82 V
high, 24.576 MHz**. Values, fitting and the bench checklist:
`TransferOnly/PCB mods/dsp4-revC-clkin-bodge.md` (Dropbox); the permanent
fix is mod 8 in `dsp4-revD-modlist.md`.

**What it did not fix.** With that verified clock, the boot retest is
unchanged: `rdyprobe1`/`rdyprobe2` boot and SPI_RDY stays flat on both
chips, the reset-pulse RDY trace shows no HIGH in a 1 s window on either
chip, and LD2/LD3 do not light. So the clock chain was a genuine two-part
fault that had to be fixed, and it was not the sole cause. The contract
stands on its own merits (it is what the datasheet requires); the search
for why the parts are dead continues in
`TransferOnly/PCB mods/dsp4-revC-liveness-checklist.md`, whose cheapest
item is that **neither SHARC has any decoupling in the rev-C schematic**
(rev-D mod 14).

**Why this is recorded as a decision.** The alternative — a crystal per
DSP across SYS_CLKIN0/SYS_XTAL0, which is what ADI's Figure 5 shows —
would be correct by construction and is explicitly NOT chosen: it costs
two crystals and four capacitors, and it gives up the single programmable
clock source that D2's single-sourced slot map and the CPLD's clkgen are
built around. The cost of keeping the CPLD as the source is the level
translation. That trade is now deliberate.

### Addendum 2026-08-21 — the clock tree is MEASURED, and the firmware
### does not program the CGU

**CCLK = 491.52 MHz.** Measured on chip 1 off the SHARC core timer,
which decrements once per core-clock cycle by construction, so the
number depends on no assumption about instruction timing:
`src/blink/clkprobe.asm` frames a known count of timer reloads onto
PB_05 and `tools/pi/dsp4_clkprobe.py` times it. Two independent
readings in the same transcript — the tick unit and a 32-tick square —
gave 491.52 MHz to five figures.

The same image reads the CGU registers back out of the running part and
serialises them on the same wire:

| register | value | fields |
|---|---|---|
| `CGU0_CTL`   | `0x00002800` | DF=0, MSEL=40 |
| `CGU0_DIV`   | `0x05144281` | CSEL=1, SYSSEL=2, S0SEL=4, S1SEL=2, DSEL=20, OSEL=20 |
| `CGU0_STAT`  | `0x00000005` | |
| `CGU0_DIVEX` | `0x00200030` | |

Those are the reset defaults this decision predicted, and with
SYS_CLKIN0 = 24.576 MHz and the PLL's built-in /2 they give PLLCLK
491.52, **CCLK 491.52**, SYSCLK 245.76, SCLK0 61.44, SCLK1 122.88 MHz —
every one inside the datasheet ranges (fCCLK 400–1000, fSYSCLK 200–500,
fSCLK0 30–125), and fCCLK = 2 × fSYSCLK as Table 14 requires. **D10's
arithmetic is confirmed by measurement, including the /2.**

**DECISION: the firmware does NOT program the CGU.** The reset defaults
already land on a fully in-spec, audio-rational tree from the one
24.576 MHz CLKIN, so a CGU write in early init would buy nothing and
cost a PLL relock during boot — with the boot kernel's own SPI transfer
still in flight on the shared port. The firmware's *assumptions* are
corrected instead: `DIAG_TPERIOD` is 491520 (a 1.000 ms tick) and the
blink images carry `CCLK_HZ = 491520000`. If a future board changes the
CPLD divider, D10's rule stands — re-check all four derived clocks, and
re-measure with `clkprobe`.

**RETRACTED: the "~190 MHz" reading.** It came from the blink images
running 2.1x slower than their nominal rate, divided by an *assumed* 5
cycles per iteration of a two-instruction delay loop. The real cost is
**13 cycles** per iteration on this core (measured: the bisect park's
15,000,000-iteration half period is 397 ms at 491.52 MHz), and
13/5 × 400/491.52 = 2.12 — the whole of the discrepancy. Nothing was
ever wrong with the clock. No conclusion should rest on the 190 MHz
figure, and nothing in the tree does any more.

## D14 — SPI target boot requires a SPICMD byte before the stream (2026-08-21)

**Decision/fact, verified on hardware.** A 2156x booting in SPI *target*
mode (BMODE 0b010) reads **the first byte the host sends** as SPICMD, not as
boot data. HRM ch.36, Table 36-18, host starting in single-bit mode:
`0x03` = keep single-bit, `0x07` = switch to dual, `0x0B` = switch to quad.
The command byte is sent with SS already asserted and before the first
stream byte (host flow, Figure 36-6).

Omit it and the kernel consumes the first byte of the `.ldr` as SPICMD;
every block header after that is misaligned by one byte, HDRSIGN is never
`0xAD`, no block passes its XOR check, and the boot silently never
completes — while the host sees a stream clocked out from end to end and
reports success. **This was the root cause of the entire boot-handoff
failure from March to 2026-08-21**, and it survived a byte-by-byte audit of
the stream format on 2026-08-20 because the stream was never the problem:
the framing was correct, the host was simply one byte early.

`dsp4_boot.py --spi-cmd` implements it, default `0x03`; `--spi-cmd none`
restores the old behaviour and reproduces the failure on demand. Any other
host that ever boots these parts — a bootloader, a production jig, an MCU
relay — must send it too.

**Corollary for bring-up practice:** "the stream was accepted end to end" is
not evidence that a target received it. Insist on a positive liveness
signal from the part itself. On the 2156x, **SYS_CLKOUT (pin 10) is a free
one**: with BMODE non-zero it outputs SYS_CLKIN directly as soon as
hardware reset deasserts, with no code and no JTAG, so it reports power,
clock and reset state at a single probe point.


## D15 — The bare-metal firmware owns the cc21k C runtime contract (2026-08-21)

**Decision/fact, verified on hardware.** This firmware has its own `_start`
and does not link CCES's CRT or `___lib_setup_c`. That is the right choice
for a 258 KB slave-booted image, but it makes the C calling convention the
firmware's own responsibility, and until 2026-08-21 it was not being met.
Two rules, both now enforced from `src/c_abi.h`:

1. **The compiler's registers must be set up before the first C call.**
   `cc21k` returns from a C function with `jump (m14, i12) (db); rframe;`
   after fetching the return address with `i12 = dm(m7, i6)`. That needs
   **M7 = -1** and **M14 = 1** (plus M5/M6/M13/M15), not just the B/I/L
   stack registers `_start` was setting. With M7 and M14 left at whatever
   the boot kernel had put there, `sru_init()` executed every one of its
   SRU writes and then returned to a garbage address.
2. **Assembly and C must call each other the compiler's way.** A `call` /
   `rts` pair is not the convention: the caller must use
   `cjump fn (db); dm(i7,m7)=r2; dm(i7,m7)=pc;` and an assembly function
   that C calls must return with the sequence in rule 1, not `rts`.
   `CCALL()` and `C_RETURN` in `c_abi.h` are those two sequences and
   nothing else — copied from what the compiler emits and from CCES's
   `SHARC/lib/src/libc_src/set_c.asm`.

**Deliberate divergences from `___lib_setup_c`, and why** (they are listed
in `c_abi.h` too, so the file itself says which differences are choices):
L6/L7 stay 0 — ADI makes the stack circular only so an overflow wraps;
NESTM is NOT set, because `diag.asm` and `_sec_isr` are written for
non-nesting interrupts and set_c.asm's default would silently reverse
that; MMASK is left alone for the same reason; IRPTEN stays `_diag_init`'s
to own.

3. **IMASK and IRPTL must be cleared at reset.** The SPI target boot kernel
   hands control over with its own interrupts still unmasked and latched.
   `_diag_init` only ORs TMZLI in, so those survived into the firmware and
   fired into an IVT with no handler the moment IRPTEN went on. It only
   showed up under load: arming eleven DMA channels with the leftovers
   enabled killed the core, and the same code with interrupts off ran
   clean. `___lib_setup_c` clears both for exactly this reason.

4. **CMMR_SYSCTL.IIVT must be set at reset.** It selects the internal
   interrupt vector table — the one `src/ivt.asm` assembles at
   0x00090000. Reset entry does not need it, because the boot kernel
   jumps straight to the entry address rather than vectoring, so a
   firmware that never takes an interrupt looks perfectly healthy
   without it. The first interrupt TAKEN goes somewhere else and never
   returns. Bench evidence 2026-08-22: with the core timer as the only
   unmasked source the core died, and it died identically with an
   RTI-only TMZLI vector, which is what separates "taking the
   interrupt" from "running the handler". `___lib_setup_c` sets it for
   every SHARC+ part. With it set, `DIAG_TICKS` climbs for the first
   time and the SEC/SPI interrupt path runs.

**The pattern these four share** is worth naming, because it will
generate more of them: everything CCES's CRT does that this firmware
skipped is invisible until the exact feature it enables is first used,
and each one presented as a fault in a completely different subsystem —
a dead SRU, a dead DMA channel, a dead SPI link. When a subsystem looks
dead on this part, check what `set_c.asm` does about it BEFORE
suspecting the peripheral.

**Why this is recorded as a decision.** The alternative is to adopt the
CCES CRT, which would give all of the above for free — and is explicitly
NOT chosen: the CRT drags in heap setup, the dispatched-interrupt tables
and a `main()`-shaped entry, none of which this image wants, and it would
have to be reconciled with the hand-written IVT and the `-NoFillBlock`
boot-stream shape. Owning the contract is cheaper, but only if it is
written down and centralised — hence `c_abi.h` rather than four copies of
the idiom. **Any new assembly that calls C, or C that calls assembly, uses
those macros.**
