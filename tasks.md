# tasks

Status: active
Date: 2026-08-05
Purpose: current work state for the mx26 -> mx-dsp workflow and DSP4 firmware.

Status colors:
- <span style="color:#16a34a"><b>DONE</b></span>
- <span style="color:#d97706"><b>IN PROGRESS</b></span>
- <span style="color:#2563eb"><b>NEXT</b></span>
- <span style="color:#6b7280"><b>BLOCKED/DEFERRED</b></span>

## Top action

- [x] <span style="color:#16a34a"><b>DONE</b></span> (2026-08-06) **Temporary build fallback: 21568 target using 21564 constraints**
  — while the full ADI CCES license is still pending, use the 21568 build
  path with 21564-compatible constraints and memory-map assumptions to keep
  the firmware bring-up moving. Goal: get the toolchain and codegen pipeline
  compiling and exercising the same DSP/boot path, then revisit the true
  21564/21568 split once the license is available. Keep the build output
  clearly labeled as a temporary compatibility build, not a final production
  image.
  **Result: PASSED — 692 ASM sources, 0 errors, both chips linked.** Full
  evidence in "2026-08-06 — temporary compatibility build" below. Standing
  command: `PROC_TARGET=ADSP-21568 ./build.sh all` from
  `MW/D32/DSP/SHARC/`. Reopen only when the 21564 licence lands (then the
  plain `./build.sh all` path replaces this one).

- [ ] <span style="color:#d97706"><b>IN PROGRESS</b></span> **Buy AMD KR260 dev kit**
  — part number **SK-KR260-G**, one version only, from an authorized
  distributor (Mouser/DigiKey/Newark/Avnet/AMD direct if available; PSU,
  cables, SD included; avoid bare-SoM broker listings) (~$349-399) — the
  single eval system for the whole D7 fabric-only ladder (US+ fabric
  superset, 2× PL RGMII for MW-Net dev, PL-only discipline per
  `fpga/platform-shortlist.md` Prototype path note).
  Pre-order check DONE (2026-08-04, kria-apps docs): J10A (Eth3, HPB)
and J10B (Eth2, HPA) are PL RGMII; J10C/J10D are PS; SFP+ is PL GTH
  — 2× fabric RGMII confirmed. Consider a second unit later for
  star/daisy-chain link tests. Toolchain ready: Vivado 2026.1
  licensed on this machine (`~/.local/bin/vivado`).
  Next concrete action: place the order from an authorized distributor,
  capture the order number and ETA, and record the result here.

## Temporary compatibility build checklist

- [x] Confirm the temporary target selection: 21568 build path with
  21564-compatible constraints and memory-map assumptions.
  — `PROC_TARGET=ADSP-21568` selects `-proc` for easm21k/cc21k/linker;
  `resolve_ldf()` generates `build/ADSP-21568.ldf` from the repo
  `ADSP-21564.ldf` by rewriting only `ARCHITECTURE()`, so every memory
  region, section, and placement rule is the 21564 map unchanged. Licence
  probe re-confirmed the need: `-proc ADSP-21564` still fails with
  `[Error ea1156] The hardware found (ADSP-21564) does not match the
  licensed hardware (ADSP-21568)`.
- [x] Review the SHARC build scripts, target definitions, and any
  21564-specific flags that need to be relaxed for the short-term path.
  — Nothing had to be relaxed. The only 21564-specific inputs are the LDF
  `ARCHITECTURE()` (handled above) and the `<def21564.h>` / `<sru21564.h>`
  includes in `main.asm`, `sport_init.asm`, `sport_config.c`,
  `dma_config.c`, `sru_config.c`; those resolve from the CCES SHARC include
  path regardless of `-proc` and describe MMRs identical across the 2156x
  family. No per-target branch was added to `build.sh`.
- [x] Run the first compatibility build and capture the output.
  — `PROC_TARGET=ADSP-21568 ./build.sh all` (clean + full). Log kept for
  this session; summary below.
- [x] If the build succeeds, record the produced artifacts and note any
  remaining incompatibilities for the later full-CCES pass.
  — Artifacts, memory fit, and the two watch items are recorded in the
  results section below.
- [x] If the build fails, document the exact blocker and keep the work
  focused on the smallest root-cause fix. — n/a, build passed (0 errors).
- [x] Mark the build as temporary compatibility-only in any notes or
  release artifacts so it is not mistaken for a final production image.
  — `build.sh` now prints a `TEMPORARY COMPATIBILITY BUILD` banner before
  and after any non-21564 build and writes `build/COMPAT-BUILD.txt` beside
  the DXEs (target, generated LDF, UTC timestamp, reason, and an explicit
  "do not flash / do not release" validity note). Both are no-ops on a real
  21564 build.

## 2026-08-06 — 32-ch sizing pass: DSP is not the constraint, DRAM is

New: `fpga/sizing-32ch.md`. Closes the first half of the D7 gate "Lattice
32-ch sizing incl. the 18×18 composition factor" (gate line updated in
`dsp4-architecture-decisions.md`; summary box added to the shortlist).

- Workload from `MW/D32/DEFS/d32.csv` at 96 kHz: 32 ch × ~31 destinations
  = 992 sends, plus ~318 biquads (5 MACs each) and ~500 dynamics MACs →
  **~3,100 MACs/sample**. At 250 MHz that is ~2,600 cycles/sample, so
  **two time-multiplexed MAC lanes** (one at 400 MHz). `ch.fir` is NOT in
  d32.csv — the biggest DSP swing factor is a flagship feature and does
  not load this tier.
- **The 18×18 worry does not bite.** Q4.28 × Q4.28 is 32×32 on both sides,
  which costs **4 primitives on either vendor** (Xilinx 27×18: 2×2;
  Lattice 18×18: 2×2). The narrow-primitive penalty only appears for a
  27-bit data path with ≤18-bit coefficients, which D5's LF biquad
  measurements rule out. Two lanes = ~8 primitives = **~5% of ECP5-85's
  156 × 18×18, ~17% of SU35P's 48 DSP48E2**.
- **The real constraint is delay memory.** `MW/D32/DSP/dsp-def.md` already
  budgets the tiered delay pool at ~1.29 MB at 48 kHz → **~2.6 MB (20.6
  Mb) at 96 kHz**, against 3.7 Mb of block RAM on ECP5-85 and 1.7 Mb on
  SU35P. Neither is within 5×, so **external DRAM is mandatory at this
  tier on either vendor** and the part choice turns on the memory
  interface and pins, not DSP or BRAM.
- Next on this thread (in order): DRAM support per part (ECP5 DDR3 vs
  SU35P DDR4/LPDDR4, soft vs hardened controller, LUT cost) → pin budget
  → Fmax → ECP5-85 quote. Also flagged: the SU35P "48 DSP slices" figure
  came from search summaries, not a primary DS930 table read, and SU35P
  has 48 × 36 Kb BRAM blocks too — confirm before quoting. The verdict
  holds either way.

## 2026-08-06 — D9 drafted (AWAITING SIGN-OFF) + shortlist corrections

Entry point 6 done as far as it can go without you. **D9 — FPGA parameter
plane** written up in `dsp4-architecture-decisions.md` from the 2026-08-05
argument, carrying a `[DRAFT] / not binding until the banner is removed`
header (the decisions doc's status line says the same). Content: float32
stays on the SPI wire unchanged from D1/D5; conversion happens **on fabric
at ingest** via one time-multiplexed converter, not Pi-side (Pi-side prep
would push per-address Q-format knowledge into the host and fork host
tooling per engine); **per-address format map generated** from `dsp.csv` by
`fpga_codegen.py`, formats governed by the existing `shared/numeric-spec.md`
— no second numeric spec; **ramps run fixed** in fabric (the deliberate
divergence from D5's all-float param plane, since fabric has no free float
adder); sample-serial audio + block-rate control is what makes one shared
converter and one ramp engine sizeable.

Left open inside D9 on purpose: parameter-RAM sizing per tier, the
ramp-precision tolerance for fixed ramps (a numeric-spec amendment, since
trajectories quantize earlier than on SHARC), and whether meters return on
the same path. **Read the draft and sign it off or mark it up** — that is
the only remaining action on entry point 6.

Shortlist corrections applied at the same time (`fpga/platform-shortlist.md`):
- **Lattice price corrected** — CPNX-100 is ~$131 catalog, NOT the ~$25-50
  the ladder and vendor bullet both carried; that figure applied to small
  ECP5 module parts. At 32 ch the real race is **ECP5-85 vs SU35P**;
  CPNX-100 now needs a capability reason, not a price one. Avant-E flagged
  for its own quote.
- **Microchip bullet rewritten** — PolarFire is **fabric-fit** (objection
  withdrawn) but **4-5× the price** at equivalent capacity; status is watch
  item ranked behind Agilex 5, revisit trigger = PolarFire 2 pricing or a
  hard fanless requirement.
- Action item 8 (coefficient-computation location) struck through and
  pointed at D9.

## 2026-08-06 — temporary compatibility build (21568 fit proxy) PASSED

Command: `PROC_TARGET=ADSP-21568 ./build.sh all` in `MW/D32/DSP/SHARC/`.

- **692 ASM sources** (chip1 431 nodes + 5 infra, chip2 235 nodes + 5 infra,
  8 shared, 8 lib) + 5 C files compiled per chip. **0 errors**, 34 warnings.
- Linked: `build/chip1.dxe` **1,270,640 B** (456 objects),
  `build/chip2.dxe` **2,505,220 B** (260 objects).
- Grown since the 2026-07-30 proxy run: 642 → 692 ASM, chip1 1.23 → 1.27 MB,
  chip2 2.46 → 2.51 MB.

Memory fit (words used/capacity, from the linker map XMLs):

| Region | chip1 | chip2 |
|---|---|---|
| mem_iv_code | 260/260 (100%) | 260/260 (100%) |
| mem_block0_bw | 170292/195040 (87.3%) | 178708/195040 (91.6%) |
| mem_block1_bw | 0/180224 (0%) | 0/180224 (0%) |
| mem_block2_bw | 19492/131072 (14.9%) | 0/131072 (0%) |
| mem_block3_bw | **131070/131072 (100.0%)** | 60786/131072 (46.4%) |
| mem_L2_bw | 506880/1024000 (49.5%) | **978808/1024000 (95.6%)** |
| mem_L2CTL1_bw | 0/1048576 (0%) | 729408/1048576 (69.6%) |
| total | 827994/2710244 (30.6%) | 1947970/2710244 (71.9%) |

**Reading these numbers correctly** — this supersedes the "TIGHT" readings in
P2 (2026-07-30) and the first version of this entry, both of which called a
full primary region a wall. It is not. The LDF fills a primary region then
spills the remainder into an overflow region: code `block3` → `block2`, DM
data `block0` → `block1`, delay `L2` → `L2CTL1`. A primary region at ~100% is
the design working, and a single region's percentage is NOT headroom. chip1
`block3` at 131070/131072 looks alarming and is not: `sec_swco_ovf` is live in
`block2` and only 14.9% used. The number that gates growth is the
primary+overflow pair:

| Pool (primary + overflow) | chip1 | chip2 |
|---|---|---|
| code (block3+block2) | 150562/262144 (57.4%) — 111582 free | 60786/262144 (23.2%) — 201358 free |
| DM data + stack (block0+block1) | 170292/375264 (45.4%) — 204972 free | 178708/375264 (47.6%) — 196556 free |
| delay lines (L2+L2CTL1) | 506880/2072576 (24.5%) | **1708216/2072576 (82.4%)** — 364360 free |

Use `python3 tools/dsp/dsp_memreport.py MW/D32/DSP/SHARC/build/chip*.map.xml`
(added 2026-08-06) instead of eyeballing regions — it prints the pair totals,
marks a full primary as expected, treats the fixed-size IVT as fixed, and
warns only when an *overflow* tier climbs, since nothing sits behind it.
Exit 1 above 90%; currently exit 0 for both chips.

**Real watch item — chip2 delay pool at 82.4%**, the only pool whose overflow
tier is actually loaded (`L2CTL1` 69.6%). When that tier fills, the link fails
with no third region behind it; 364360 bytes left. Every other pool still has
a completely idle overflow tier (chip1 `block1`/`L2CTL1`, chip2
`block1`/`block2` all at 0%). **No LDF rebalance is needed to keep growing
right now** — the fabric remap (128 buses) and superset I/O nodes are not
blocked by memory. Revisit when the chip2 delay pair passes ~90%, or when
chip1 code starts landing in `block2` in bulk.

Warnings: **34 on the first run, now 2** (both long-standing loop-end
advisories in `lib/biquad.asm`). The 32 removed were
`[Warning ea1092] Symbol '_mrf_rns28' is undefined`, one per `C1_GAIN_*`
node: the GAIN template in `tools/dsp/dsp_codegen.py` omitted the
`.extern _mrf_rns28;` that the GATE/TUBE/FDR/BUS templates declare. It was
noise, not a bad call target — `elfdump -n .rela.seg_pmco C1_GAIN_01.doj`
showed the relocation was emitted anyway and the linker resolved it
(`_mrf_rns28 = 0x1825C1` in `chip1.dxe`). Fixed at the generator (one line)
and regenerated with `--force`: exactly 32 files changed, each by exactly
`+.extern _mrf_rns28;`, and the other 646 regenerated byte-identical — so
there was no hand-edit drift in the node ASM. Rebuild after the fix: 0
errors, 2 warnings, identical DXE sizes and identical memory pools.

**Validity of this build:** it proves toolchain, codegen, link, and memory
fit only. It says nothing about 21564 part-specific behaviour and must not
be flashed or released — see `build/COMPAT-BUILD.txt`.

CCES licence check (entry point 2, same session): **not arrived.**
`-proc ADSP-21564` still returns `[Error ea1156] ... does not match the
licensed hardware (ADSP-21568)`. AD-CCES-NODE-1 requested 2026-07-31; the
21568 EZ-KIT entry remains the only usable entitlement on this host.

## Resume notes (2026-08-05 session end — tree clean at push)

Today: D7 committed (`76c54f6`); **D8 decided + committed** (`e16e817`,
rev D scope: CM4-core SPI control, supervisor shrink, CPLD 570Z
verified by scratch Quartus run, PSRAM + SPI0/1 remap, no boot NOR);
U7/SRX-MRX pin inventory DONE (`0361e6f`, hardware-map §3a — S MCU is
the serial hub; rev-D part = STM32G0B1RET6, NOT a drop-in, U535RET6
is); mod lists moved to Dropbox `TransferOnly/PCB mods/` (cross-repo
convention + README; D24 Digital rev-C mods pdf/txt rescued from the
ECAD folder); OSPI voltage gate ANSWERED (3.3 V VDD_EXT only → 1.8 V
octal excluded; 3.0 V octal-xSPI HyperRAM S27KL-class preferred,
APS6404L quad fallback). Also: PolarFire assessed (fabric-fit but
4-5× price — watch item behind Agilex 5; PolarFire 2 = revisit
trigger); Lattice deep-dive (CPNX-100 is ~$131 catalog NOT $25-50 —
shortlist correction pending; ECP5-85 vs SU35P is the real 32-ch
race; Avant-E = first Lattice mid-range, quote it); KR260 heatsink
concern defused (ZU5EV SoC thermals ≠ fabric-only product; US+ needs
copper/small sink at most — Vivado power estimates queued).

TOMORROW'S ENTRY POINTS (priority order):
1. **Temporary 21568/21564 compatibility build** — keep the toolchain
   moving while CCES is pending by building the 21568 path with 21564
   constraints and matching the same boot/dispatch assumptions. This is
   the immediate next step until the full license arrives.
2. **Check CCES licence arrival** (AD-CCES-NODE-1, requested
   2026-07-31) → plain `./build.sh all` = first real 21564 images →
   unblocks rev-C bring-up, which gates the rev-D layout freeze.
3. **Order KR260** (SK-KR260-G) — still fully unblocked, see Top
   action.
4. **Quote round** (one call, now extended): SU35P / SU55P-SU100P /
   AU25P @1k + Agilex 3 availability + Agilex 5 Quartus licensing +
   LFCPNX-100 + an Avant-E part + 5M570ZT144C4N + STM32G0B1RET6 /
   U535RET6 + Infineon 3.0 V octal-xSPI HyperRAM (S27KL-class)
   availability.
5. **Rev D remaining OSPI open**: 21564 OSPI clock ceiling +
   xSPI-profile-2/RWDS RAM support — check EV-21568-SOM reference
   design in the ADI portal (datasheet mirrors bot-block curl; the
   rlocman paged mirror worked for pin tables, OSPI timing pages
   could be fished the same way).
6. **FPGA D9 decision text** (param plane: float wire, on-fabric
   ingest conversion + per-address format map, fixed ramps,
   sample-serial audio / block-rate control) — argued 2026-08-05 in
   session, ready to record when Peter signs off. Shortlist edits
   pending from the same discussion: Lattice price correction,
   Microchip bullet rewrite (fabric-fit/cost/PolarFire-2 trigger).
7. Desk work queued: per-tier pin-budget table + Vivado XPE power
   estimates (SU35P/AU25P) — feeds quotes AND the thermal question.
8. Unchanged hub-side gate: `ch.fir` tap ceiling into d128 (biggest
   open number, ~$150-200 BOM swing).

Cross-repo state: mod lists live in Dropbox `TransferOnly/PCB mods/`
(dsp4-revD-modlist.md = single rev-D source incl. gate statuses;
d24 digital mods.txt/pdf = Digital rev-C Schottky review). Memory
updated with the convention.

## 2026-08-06 — Dropbox `_Matrix` shared store adopted (doc-only)

mx26 commit `fbaf2be` (2026-08-06) declares the Dropbox `_Matrix` folder
the canonical **cross-repo** shared data store (mx26 `sot.md` concept 16,
`docs/decision-mx26-mandates.md`, `matrix_direction.md`): mx26 owns the
layout — `Products/<P>/{dsp,fw,hw,logic,net,pd,sw,sys}` mirroring its
src/ domains — spokes consume it, D24 is the template product, essential
and durable content only, no bulk migration, nothing there is a build
input. Absorbed here as `matrix-shared-store.md`, with pointers added to
`README.md`, `CLAUDE.md`, and `MW/D24/HW/hardware-map.md`. No tooling
change: `defs.lock` / `sync-from-mx26.sh` still read the mx26 checkout —
mx26 names `_Matrix` as the *eventual* home of the pinned Dropbox mirror,
not today's.

Verified locally: store is fully synced offline (~110 MB, no online-only
placeholders); `Products/D24/hw/` holds all 9 D24 PCBAs (BOM + renders +
CADCAM zip + base design + schematic PDF + DipTrace `.pdsprj` each); the
other D24 domains are empty, and `Products/D32/` does not exist yet. The
D24 DSP/Digital/Analog PDFs in `MW/D24/HW/schematics/` are byte-identical
to the store copies, so hardware-map derivations still hold. Open item:
`TransferOnly/PCB mods/` mod lists are a migrate-later candidate for
`_Matrix/Products/D24/hw/` — PW/mx26's call, nothing moved.

## Resume notes (2026-08-04 session end)

UNCOMMITTED: CLAUDE.md, dsp4-architecture-decisions.md (new **D7**),
fpga/README.md, fpga/platform-shortlist.md, tasks.md — the whole D7
scope amendment (fabric-only baseline, hybrid FX, recording/USB
deleted). Commit this first (suggest: "D7: fabric-only baseline +
per-tier hybrid FX; recording/USB deleted from 96k scope").

TOMORROW'S ENTRY POINTS (priority order):
1. Order KR260 (SK-KR260-G) — fully unblocked, see Top action above.
2. Quote round: SU35P / SU55P–SU100P / AU25P @1k via Avnet/Arrow;
   while at it, check **Agilex 3** availability/pricing (Altera's
   cost-optimized tier — the one event that reopens the small-tier
   vendor question) and Agilex 5 Quartus Pro licensing terms.
3. `ch.fir` tap ceiling into the d128 product definition (hub-side,
   mx26) — gates part choice AND vendor floor; biggest open number.
4. Toolchain ready: `~/.local/bin/vivado` (2026.1, Basic license to
   2027-08-04, node-locked to this machine); Quartus Lite 21.1 stays
   CPLD-only — do not touch for FPGA work.

## Addendum 2026-08-02 — D6 platform mandate

D6 recorded in dsp4-architecture-decisions.md: SHARC DSP4 card serves
up to 32 ch @ 48 kHz (D24/D32 path untouched); single-chip FPGA engine
(ZU5EV/K26 class) mandated for 32 ch @ 96 kHz and up. Full platform
dossier: `fpga/platform-shortlist.md` (parts, 1k pricing, cost case vs
multi-SHARC, DAW/recording strategy, MW-Net link decisions in
`fpga/README.md`). Pre-code gates: ch.fir tap ceiling (hub-side,
~$150-200 BOM swing), FX placement, 16-bit address check at d128
scale (needs d128 mx-master generated in mx26), MW-Net frame spec.

## Addendum 2026-08-04 — FPGA scope amendment (fabric-only baseline)

Product scope narrowed (research phase, cost-driven; full text:
`fpga/platform-shortlist.md` SCOPE AMENDMENT section): onboard
recording + USB UAC deleted from all 96 kHz products; Dante card =
customer-paid option inheriting the fitted card's capacity (full-
bandwidth-Dante rule withdrawn); MW-Net confined to own I/O boxes
(full-bandwidth, no recording). Consequence: SoC mandate collapses —
pure-fabric FPGA + CM master is baseline for all tiers ("ZU5EV/K26
class" in the D6 addendum above is superseded as baseline; D6's
platform split itself unchanged). CM never touches audio. FX strategy
decided as **D7 per-tier hybrid**: 32/64 ch fabric-light; flagship
launches with SHARC 21569 TDM sidecar (depopulatable), fabric TM-FX
as designed-in cost-down. All of the above now recorded as **D7** in
dsp4-architecture-decisions.md (CLAUDE.md hard-rules updated to
match). New gates: per-tier pin
budget, Lattice 32-ch sizing pass, per-part DDR verification,
coeff-conversion location (D5 float wire vs Pi-side prep). Toolchain
now ready: Vivado 2026.1 licensed + verified on this machine
(use `~/.local/bin/vivado` wrapper).

## Addendum 2026-08-05 — DSP4 rev D scoped (decision D8)

Rev D of the DSP4 card scoped and recorded as **D8** in
dsp4-architecture-decisions.md (amends D1's S-MCU clause; D7 scope
amendment committed + pushed as `76c54f6` the same day):

- **CM4 dedicated core** takes ALL SHARC SPI control (D1 refinement:
  isolated A72, pinned thread, gpiod CS); host-side float control
  plane / coeff prep lives there too.
- **Supervisor shrink**: boot-relay fallback DELETED (slave boot over
  SPI2 permanent; scenes on CM4; no Pi-less requirement). H1S1/U7
  (STM32U575RIT6) → **STM32U535RET6 drop-in** near term (same
  LQFP-64/U5 pinout; fw ~266K fits 512K); G0-class or merge into U8
  at rev D. GATE: SRX/MRX matrix-comms role inventory.
- **PSRAM activated** (HW section item joins rev D): one xSPI PSRAM
  per DSP on OSPI0; Pi runtime link → SPI0/SPI1 per DSP, SPI2
  boot-only. No boot NOR. Open: OSPI voltage domain (1.8 V rail vs
  3V3 quad APS6404L), 21564 OSPI clock ceiling, XDELAY DMA prototype.
- **CPLD → 5M570ZT144C4N**: VERIFIED 2026-08-05 on the real qsf
  (scratch Quartus run, not committed): only ONE illegal pin
  (PIN_137/mems — one trace moves), C4 closes 51.95 MHz vs 49.152
  needed, **C5 FAILS (36.9 MHz)**, 148/570 LE / 67 of 114 pins.
  ~5% margin → STA gate mandatory on RTL changes; 240Z fits at 62%
  but rejected (no growth room).
- **Hardwire-chunk pass**: only routing proven static at rev-C
  bring-up becomes copper (net_sel already product-static); CPLD
  keeps clkgen + Pi PCM reframer + reset glue.
- Sequencing: rev C bring-up (still gated on the CCES licence)
  verifies the provisional TDM facts → then rev D schematic freeze.

NEXT (rev D, priority order): 1) ~~SRX/MRX inventory~~ DONE
2026-08-05 — see hardware-map.md §3a: "matrix comms" = strobed
matrix-protocol endpoint (S0-S3/BUSY + SRX/MRX, shared with U8,
routed through LOGIC = the uart-passthrough TODO) PLUS a 6-UART
option-card hub (USB/DAW, Dante, USB-SSD cards) + housekeeping SPI
(!CS_L/!CS_C/!CS_M) + PAD0-11 PSU ADC + resets. Disposition:
supervisor stays a separate part; rev-D target STM32G0B1RET6
(6 USART, LQFP-64, ~$3.5-4); do NOT merge into U8; U535RET6 remains
the drop-in. 2) OSPI voltage-domain answer; 3) rev-C bring-up
checklist unchanged.

**Consolidated rev-D mod list**: kept OUTSIDE the repo (Peter,
2026-08-05: mod files live in Dropbox so every repo can reach them) at
`~/Stonepower Dropbox/Peter Watts/TransferOnly/PCB mods/dsp4-revD-modlist.md`
(folder renamed DSP4 mods → PCB mods 2026-08-05 when the D24 Digital
rev-C mod docs — `d24 digital mods.txt`/`.pdf`, ex `_mx/MW/D24/HW/D24
Digital PCBA rev C/` — joined it)

OSPI voltage gate ANSWERED 2026-08-05 (recorded in the mod list):
2156x OSPI pins are VDD_EXT-domain = **3.3 V only** (VDD_REF is a
1.8 V reference input, not a pad supply) → 1.8 V octal PSRAMs
excluded; part paths = 3.0 V octal-xSPI HyperRAM 2.0 (S27KL-class,
uses the NC xSPI_RWDS pin 9) or 3.3 V quad APS6404L fallback.
Remaining OSPI open: clock ceiling + xSPI-profile-2/RWDS RAM support
confirmation (datasheet mirrors bot-blocked; check EV-21568-SOM
reference design).
— single source for all rev-D mods, deletions, doc fixes, and freeze
gates. The schematic originals live one level up in
`TransferOnly/D24 schematics/` (verified byte-identical to
MW/D24/HW/schematics/ on 2026-08-05). FPGA-side: the param-plane
ingest-conversion proposal (float wire, on-fabric conversion, fixed
ramps) is drafted in discussion but NOT yet recorded — becomes D9
when settled.

## Resume notes (final save 2026-07-31 — 32 commits today, tree clean)

TOMORROW'S ENTRY POINTS (in priority order):
1. CCES licence arrival → plain `./build.sh all` = first real 21564
   images (of the FIXED firmware). Delete the fit-proxy caveat +
   cces-license-status memory when it succeeds.
2. Peter [REVIEW] sign-offs in shared/numeric-spec.md: +18 dB headroom
   (vs Q5.27/+24), tolerance set, knee behaviour.
3. CPLD pin-constraint verification prep + hardware bring-up checklist
   (see P1 plumbing bullet: FLAGS_REG, SPI_RDY, SEC on the wire,
   BCKI/FSI pair order, CKRE/MFD on the scope, D24 ADC slot order).
4. Optional pre-hardware: cycle profiling of first-cut fixed kernels;
   CCES simulator investigation for fixed_ref bit-exactness checks.

State: firmware mainline = FIXED-POINT (D5 complete, 700-obj build
green, float at tag float-kernels-2026-07-31); contract at
defs-v2026.07.31 fully closed both directions; CPLD RTL + hash-pinned
bitstream committed (pins from schematic, .pof 233db2b02906); Pi config
tool ready; FPGA idea folder seeded.

---

## Day log (2026-07-31, sessions 1-4)

Today, session 1: committed 2026-07-30 work (`ae6973d`, `b675143`);
created the D2 slot-map source table + generator in `shared/dsp4-logic/`
(`8439b18`).

Today, session 2 — **P1 fabric remap DONE** (gen_dsp_csv.py rework):
1. **Slot map extended**: fabric pass-through slots XFER_* on global mix
   slots 25-36 (codec aux L/R, Pi L/R, snake 1-8; MIX_1 slots 9-15 +
   MIX_2 slots 0-4). 37 of 128 fabric slots now assigned. New
   source_hash sha256:6e89117c4d173ecf….
2. **gen_dsp_csv.py rewritten** to consume `sport_map.json`: interchip
   nodes now carry `sport_id=<line>;slot;global_slot;sport_slots=16;
   signal=…` (legacy sport7 numbering preserved 1:1 as global slots);
   INPUT/OUTPUT nodes carry `sport_slots` + `signal`; CLI gained
   `--out`/`--sport-map` (stale `tools/dsp.csv` output path fixed).
   Superset I/O per D3: chip1 XIN nodes (codec ret 1/3/4, Pi L/R, MEMS,
   snake 1-8 [D32]) — codec-1/MEMS wired to TALKBACK 1/2, the rest
   pass through the fabric to chip2 XR recvs + AUX_INPUT nodes
   (default-off) feeding the main mix. Output patch onto real hardware:
   Aux 1-12 → DAC_01-12, Main xover 1-4 → DAC_13-16, Sub → NET_OUT_01,
   Monitor → CODEC_OUT_1/2 (D24), new C2_MAIN_ST_OUT → DAC MAIN and
   C2_CODEC_AUX_OUT → CODEC_OUT_3/4 (both fed from post-delay main).
   D32 snake OUTPUT patch deliberately deferred to the product-config
   output layer (B_O2 slots are scope-shared with D24 codec; block_io
   is scope-blind today). Also fixed: USB/BT aux inputs were declared
   as main-mix outputs but missing from MIX_MAIN inputs (silently
   dropped contribution).
   **Address stability verified by diff**: 0 spi addr changes, 0 removals,
   50 nodes added (662 total; new cells 1818-1837 appended on chip 2).
3. **dsp_codegen.py linearization parameterized**: IC tables keyed by
   global_slot with a contiguity assertion (packed DMA); TX frame index
   uses per-node sport_slots (uniformity asserted); RX sort by
   (sport, slot). block_io strides now: c1 rx=46, ic=37; c2 tx stride=33.
4. **sport_init.asm geometry updated** (RX/TX buffers to 64-slot frame
   capacity = 2048 words, IC_CHANNELS 25→37, honest header: LOGIC is
   clock master everywhere, register-level SPORT config still implements
   the superseded single-SPORT7 model — loud TODO(dsp4-plumbing) for
   hardware bring-up). Old buffer sizing had a latent overflow (tx
   stride 42 > 32-slot buffer) — never ran on hardware.
5. **gen_dsp.py (D32 backfill)**: new node-id patterns (CodecAux/Pi/Snk
   cells 1818-1837 on chip 2); unmatched node ids now FAIL LOUDLY
   (previously fell through to a silent '000' cell family — no-fallback
   policy violation, found because it produced 000Level001/000On001).
   20 new cells await mx26 matrix adoption (INFO list).
6. **build.sh**: fit-proxy now auto-generates a matching temp LDF when
   PROC_TARGET≠21564 (never committed).
7. dsp.plan.md marked SUPERSEDED (Link-Port/MCU-relay diagram obsolete
   per D1). dsp_validate + dsp_simulate pass on the new graph.
8. **Fit-proxy build PASSED post-remap** (`PROC_TARGET=ADSP-21568
   ./build.sh all`): 687 objects, 0 errors, both chips linked
   (chip1.dxe 1.27 MB, chip2.dxe 2.50 MB). Memory: chip1 block3 97.8%
   (+0.5 vs 2026-07-30; sec_swco_ovf → idle block2 catches overflow),
   chip1 block1 28.7% (doubled DMA buffers fit easily), chip2 L2 95.6% /
   L2CTL1 69.6% (unchanged — delay lines). No LDF change needed yet.

mx26 availability RESOLVED (2026-07-31): cloned read-only from
github.com/invirco/mx26 (gh auth: invirco account, repo scope) to
`~/mx26` — the first candidate path sync-from-mx26.sh probes, so no
MX26_REPO env needed. Full `./regenerate-dsp-contract.sh` +
`./check-contract-drift.sh` then ran clean with a byte-identical tree
(the earlier direct-step run was equivalent). Upstream head d7b795b is
one commit past the pinned 2f92f8b (workflow/tasks only; contract files
unchanged). `git -C ~/mx26 pull` before future syncs.

2026-07-30: build verification (fit proxy PASSED as 21568), Quartus
verified, rev C schematic review, xSPI PSRAM investigation.

Afternoon session (2026-07-31, continued): GrpGeq DONE (`4a51e08`),
product-config boot block DONE (`3376f84`, incl. the stale SPI bounds
bug fix), plumbing design + slices 1-2 DONE (`657de55`, `497bbca`,
`259ebc8`). HRM found already fetched in Dropbox (Peter's resilient-
fetch effort); mx26 cloned to ~/mx26 and full contract flow verified.

Evening session (2026-07-31): plumbing slice 3 DONE (`94447ec` — DDE
rings, SEC dispatch via SECI vector 15, real SPI MMRs, SPEN). CPLD RTL
STARTED (`e9b0f7d`): clkgen + Pi PCM reframer + routing top, Quartus
map/fit/STA clean (169 LEs, Fmax 118.8 MHz). Timing conventions LOCKED
in the slot-map SOT (sample rising / launch falling / MFD=1; firmware
CKRE=1). Two architecture facts settled from the schematics: the mix
fabric is DIRECT DSP-to-DSP PCB routing (not through the CPLD), and
DAC MAIN has no D24 sink BY DESIGN (D24 main outs are Analog-PCBA line
outs via DA0/DA3 — traced with Peter's pointer). Slot-map hash now
sha256:efd8d555440094b6.

Late session (2026-07-31): pre-hardware wrap-up.
- CPLD pins REAL: all 144 pins extracted from the LOGIC sheet (300 DPI
  crops, four banks); qsf rewritten; RTL de-reset (MAX V powers up
  cleared — the board has no reset to U3); net_sel resolved (fixed per
  product in RTL; runtime muxing later via the DISCOVERED S-MCU SPI
  provision on ISPI0/ISPI1/ICS_L pins 60-62); PCM pin roles from the
  hardware map (0=CLK 1=DOUT 2=DIN 3=FS); codec = PLL8_0/1.
  PROVISIONAL: S4 personality strap; snake/DAC-MAIN parked PLL5_0-2;
  BCKI/FSI pair in/out order per DSP (verify at bring-up).
- Hash-labelled bitstream COMMITTED (D2): bitstream/dsp4_logic.
  233db2b02906.{pof,svf,manifest} via shared/dsp4-logic/build.sh
  (STA-gated; Fmax 75.9 MHz with pins). UART pass-through pins are
  TODO(uart-passthrough) — routing matrix undefined.
- Firmware hygiene: ramp_tables ea1092 warnings fixed at the generator
  (dead alias globals removed); _sec_isr now banks the FULL regfile +
  DAG1 (SRRFH/SRD1H added — the ramp path uses i4/f8/f10/r10; low-half
  banking alone corrupted interrupted block processing).
- Pi host tool: tools/pi/dsp4_config.py — boot config writer (product
  profiles incl. the D24 interleave patch, 51 writes chip1 / 5 writes
  chip2, COMMIT last, GPIO-CS via gpiod, --dry-run verified).

CCES licence: AD-CCES-NODE-1 REQUESTED 2026-07-31 (Peter; ~a day's
wait). Until it arrives, fit-proxy (PROC_TARGET=ADSP-21568) remains the
build path; first real 21564 images once entitled. Meanwhile the mx26
update is prepared: [mx26-update-handoff.md](mx26-update-handoff.md)
(exact mx_master.csv rows, def_master PREFIX_RULES + product keys,
GrpPeq→GrpGeq rename incl. a suspected wrong Table on the old row, and
this repo's post-sync steps). The 7 new families are pre-staged in
matrix-families-allowlist.txt (validator passes; GrpPeq retained until
the rename lands).

Remaining = hardware bring-up (rev C card + full 21564 licence):
FLAGS_REG chip-id detect, SPI watermark + SPI_RDY flow, SEC/MMR
semantics on the wire, BCKI/FSI pair order, CKRE/MFD on the scope,
D24 within-ADC8 slot order, S4 personality + S-MCU firmware side.
mx26-side: DONE 2026-07-31 (mx26 8714f2f, applied from
mx26-update-handoff.md incl. the full 28-band GrpGeq choice and the
Table bug fix). Contract bumped to defs-v2026.07.31; alias flag +
GrpPeq allowlist entry retired; matched cells 5453→5537; the
"DSP cells not in matrix" list is now EMPTY.

### Checked, no action needed
`cces-tools/license/license.dat` exists on disk but is NOT tracked — the
`cces-tools/.gitignore` (`*`) covers it. Licence material is safely
untracked; nothing to purge.

State assessment — unified DSP4 firmware ~75-80% written (weighted by
effort, not lines; hardware-verified fraction much lower, nothing has run
on the rev C card):
- D32 SHARC tree is the foundation: 613-node dsp.csv, 74.5k lines generated
  node ASM, 13k infra/libs. Kernels ~95%, node coverage ~90%, infra ~75%.
- D24 SHARC tree (202-row dsp.csv) is a superseded skeleton — retire into
  the unified build, do not extend.
- Remaining 20-25%: fabric remap, product-config layer, superset I/O nodes
  (MEMS/Pi PCM/codec return), GrpGeq, D24 contract wiring.

2026-07-30 plan status: step 2 (slot-map source table shaped for two
consumers) DONE 2026-07-31 — see `shared/dsp4-logic/`. Step 3
(gen_dsp_csv.py rework: 25 buses onto MIX lines 0-1, lines 2-7 reserved,
superset I/O behind product config) is now the P1 NEXT task, with the LDF
rebalance riding along (chip1 block3 97.3% / chip2 L2 95.6% grow under
the 128-bus rework; block2 idle at 0%) and the mechanical fixes listed
there. The rework is sport/slot plumbing (sport_init.asm, block_io.asm,
dsp.csv sport params), not kernels.

## P1 - DSP4 unified firmware & D24 bring-up (top priority)

- [x] <span style="color:#16a34a"><b>DONE</b></span> Fixed-point conversion (decision D5) — COMPLETE 2026-07-31
  - **The mainline firmware is now fixed-point (Q4.28)**: dsp_codegen
    default flipped to --format fixed; repo src/ regenerated; full
    fit-proxy build 700 objects / 0 errors, both chips link; gen_dsp.py
    dispatch/backfill clean (all param symbols preserved by design —
    the float control plane is byte-compatible).
  - Float kernels remain regenerable via --format float and archived at
    tag float-kernels-2026-07-31.
  - Float islands (documented): FX_ENGINE bodies + NOISE_GEN synthesis,
    with Q4.28<->float32 conversion at their node edges.
  - Late additions to the family list: DELAY needed NO conversion
    (pure storage + integer pointers, format-agnostic; the float
    interp/comb lib helpers are dead code). Dynamics implemented
    against fixed_ref (log2-domain gain computer with soft knee —
    extended in the model + harness first, still 9/9), with generated
    poly tables guaranteeing the asm constants equal the model's. rns
    redefined to the hardware-natural (v+half)>>shift form (model
    updated, harness revalidated) fixing a latent model/asm rounding
    mismatch.
  - REMAINING for bring-up: bit-exactness vs fixed_ref on
    simulator/hardware (asserted by construction, unproven in
    execution); cycle-budget profiling of the first-cut kernels
    (~40cyc/biquad-stage — optimize after parity); Peter's [REVIEW]
    sign-offs in numeric-spec.md (headroom, tolerances).

- [x] <span style="color:#6b7280"><b>ARCHIVE</b></span> (superseded ledger below)
  - Float kernels ARCHIVED at git tag `float-kernels-2026-07-31`; float
    stays the buildable mainline until each family is replaced (no new
    float feature work). FX engines stay float permanently.
  - DONE: `shared/numeric-spec.md` (Q4.28 samples/+18 dB headroom,
    offset-coefficient biquad topology + error feedback, log2-domain
    dynamics, Q0.31 alphas, contract-preserving float32 wire);
    `tools/dsp/fixed_ref.py` (bit-accurate normative model);
    `tools/dsp/golden_harness.py` — **9/9 PASS**: biquad 0.046 dB worst
    (FP32 baseline: 0.41 dB — 9× better), noise −132.6 dBFS, summing
    exact, log2/exp2 ≤ 0.0001 dB, comp curve 0.00008 dB, envelope 0.2%.
  - [REVIEW] items for Peter in the spec: +18 dB headroom choice,
    tolerance set, dynamics knee behaviour at the log2 boundary.
  - Kernel conversion progress (behind `dsp_codegen.py --format fixed`;
    float default stays byte-identical, verified):
    - DONE 2026-07-31: `lib/biquad_fx.asm` — offset-form cascade
      (`_bq_fx_cascade_N`, b0-only MAC grouping for bit-exactness, MRF
      80-bit, error feedback, saturation) + `_bq_fx_convert_N` (staged
      FLOAT RBJ words → Q4.28 offset set at swap time; wire unchanged);
      EQ_BIQUAD fixed generator (same dual-instance crossfade contract,
      fixed blend, 6-word/stage state). Both assemble clean; full float
      build still green. Bit-exactness vs fixed_ref is asserted by
      construction and must be verified on simulator/hardware at
      bring-up (correspondence comments in the asm).
    - DONE 2026-07-31 (cont.): full biquad family — GEQ + ANTI_FB via a
      shared fixed-cascade emitter, HPF_LPF (independent hpf/lpf float
      staging, fixed baseline copy + selective convert) and CROSSOVER
      (LP/HP paths, both outputs blended). All five node types assemble
      clean under --format fixed; float output byte-identical. Register
      contract fixed en route: the fixed core clobbers r5-r12, so
      crossfade bodies hold input/old-output in r13/r14 (lib preserves
      r13-r15 — documented in biquad_fx.asm).
    - DONE 2026-07-31 (cont.): SPEC REVISION — the parameter plane
      (dispatch, ramp engine, target/step scalars) stays FLOAT and
      byte-identical; fixed kernels convert control values to Q4.28
      shadows once per block (FIX at sample_idx==0). Gains family:
      lib/mac64_fx.asm (_acc64_mac exact pair accumulate, _acc64_rns28,
      shared _mrf_rns28 extractor); fixed GAIN, FADER_PAN (incl. L/R
      pan shadows), MIX_BUS (chip1 = exact 64-bit acc readout, chip2 =
      MRF-unrolled with gain shadows); generated fixed
      bus_accumulators.asm (64-bit pairs + ptr tables + loop clear;
      float hand file untouched). All assemble clean.
    - DONE 2026-07-31 (cont.): ROUTING fixed — send ramps advance at
      BLOCK rate (n=min(frames,32) float steps consumed, then Q4.28
      shadow), pickoff taps read fixed strip values, and every bus
      contribution is an exact _acc64_mac (improvement over float,
      which rounded each send product before accumulating). Assembles
      clean; float output untouched.
    - DONE 2026-07-31 (cont.): block_io format-aware — converter-lane
      scaling only (RX Q1.31->Q4.28 >>3; TX <<3 with saturation; IC
      fabric carries raw Q4.28); meter scan reads fixed samples but
      PEAKS STAY FLOAT32 (host readback contract + lib decay
      unchanged). Small kernels fixed: TUBE_SAT (all-MRF waveshaper),
      AUX_INPUT, MONITOR, TALKBACK (fixed 1-stage HPF, block-rate
      coeff conversion), NOISE_GEN (documented float island — synthesis
      has no parity requirement; output converts at the store). All
      assemble clean; float output byte-identical.
    - NEXT (final fixed families): DELAY (+pool — Q4.28 lines in
      seg_delay, fixed crossfade), dynamics GATE/COMPRESSOR/LIMITER
      (log2/exp2 poly tables from fixed_ref LOG2_POLY/EXP2_POLY as asm
      data; envelope + gain computer vs fixed_ref.comp_gain — the
      careful one), FX_ENGINE float-island boundaries (Q4.28<->float32
      at node edges). Then: --format fixed full build, swap default,
      retire float src (tag exists).

Binding decisions: [dsp4-architecture-decisions.md](dsp4-architecture-decisions.md)
(D1 Pi masters DSP SPI, D2 CPLD in-repo w/ single-sourced slot map,
D3 one DSP4 firmware for D24+D32, D4 topology per schematic).
Hardware ground truth: [MW/D24/HW/hardware-map.md](MW/D24/HW/hardware-map.md)
(schematics in MW/D24/HW/schematics/, imported 2026-07-29).

- [x] <span style="color:#16a34a"><b>DONE</b></span> (2026-07-31) Rework `tools/dsp/gen_dsp_csv.py` to the DSP4 superset topology
  - Consumes `sport_map.json`; 8× TDM16 mix fabric (37/128 slots), bus
    numbering preserved 1:1; superset I/O nodes + output patch onto real
    hardware map; 662 nodes, 0 address changes to legacy cells; validate +
    simulate + fit-proxy build (687 obj, 0 err) all pass. Details in
    resume notes above. LDF rebalance NOT needed yet (block2 overflow
    section absorbs code growth; DMA buffers fit block1 at 28.7%).

- [x] <span style="color:#16a34a"><b>DONE</b></span> (2026-07-31) Product-config boot block
  - Register block at SPI 0xF000+ (PRODUCT_ID/CHAN_MASK/AUX_MASK/OUT_MUX/
    CONFIG_COMMIT + chip-1 INPUT_PATCH regs at 0xF010+); spec + D24
    interleave preset table in
    [MW/D32/DSP/product-config.md](MW/D32/DSP/product-config.md).
  - New `src/product_config.asm` (hand infra); generated per-chip
    `scope_gates.asm` (from dsp.csv `scope=` params; force-off
    wrong-product enables at commit) and RX patch machinery in chip-1
    block_io (`_rx_patch_regs`/`_rx_patch_apply`, identity default,
    clamped). Main loop still gates on `_boot_config_received`, now set
    by CONFIG_COMMIT.
  - BUG FIXED en route: both spi_handlers bounds-checked against stale
    hardcoded sizes (3904/1820) — parameters above those addresses
    (incl. the new superset/GEQ cells at 1818-1951) were rejected. Now
    data-driven via generated `_spi_dispatch_cN_size`.
  - Open: D32 snake output patch + OUT_MUX consumption in the TX gather;
    verify D24 within-ADC8 slot order before bring-up (note in doc).
  - Fit-proxy build: 695 objects, 0 errors, both chips link.

- [ ] <span style="color:#d97706"><b>IN PROGRESS</b></span> sport_init.asm register plumbing — TODO(dsp4-plumbing)
  - Design DONE (2026-07-31): [MW/D32/DSP/dsp4-plumbing.md](MW/D32/DSP/dsp4-plumbing.md)
    — HRM/header-verified register model, lane-major DMA layout, SRU
    route list, DDE ping-pong rings, SEC block clock. HRM at Dropbox
    `_mx/_temp/adsp-2156x-docs/adsp-2156x_hwr.pdf` (rev 1.0).
  - Slice 1 DONE (2026-07-31): block_io.asm is now DMA-layout-accurate —
    lane-major regions, per-node {off, stride} addressing, GENERATED
    per-lane config tables (sport/CS/words/offset; codec lane CS 0x0D
    since CODEC_RET_2 has no node) and exact-size DMA buffers moved into
    generated code. sport_init.asm stripped to an honest stub: the old
    body wrote INVENTED MMR addresses (0x0800xxxx) implementing the
    superseded single-SPORT7 model — removed rather than left to
    mislead; ISR + pointer init retained per chip. Fit-proxy build 695
    objects / 0 errors.
  - Slice 2 DONE (2026-07-31): register bring-up is in C (ADI's SRU()
    macros are C-only; def-header constants work in asm but not the
    route macros). New `src/sru_config.c` (full DAI0/DAI1 route set incl.
    the pin-19/20 swap) + `src/sport_config.c` (CTL/MCTL/CS per half
    from generated tables; SPEN deferred to slice 3). Lane tables now
    generate as `chipN/lane_config.c` (C-to-C linkage — the BA-SHARC C
    ABI dot-mangles symbols; asm↔C data sharing avoided; entry fns use
    `#pragma linkage_name`). main.asm gained C-ABI stack init
    (ldf_stack link-time expressions, ADI lib_setup_c idiom). build.sh:
    per-chip C compiles with -DCHIP_ID; CFLAGS -O2→-O (cc21k). LDF:
    added BW-qualified seg_dmda output sections — cc21k emits
    byte-addressed data that a DM-only mapping silently drops
    (li1060), same dual-mapping idiom as the CCES stock LDF.
  - Slice 3 DONE (2026-07-31): full interrupt/DMA architecture in
    place. DMA buffers moved to generated lane_config.c (byte world —
    descriptors take byte addresses); new `src/dma_config.c` builds
    2-descriptor DDE list rings per lane ({NXT,ADDRSTART,CFG,XCNT,XMOD},
    FETCH05, MSIZE/PSIZE 4, WNR on RX, XCNT_INT on the block-clock lane
    SPORT0_A), inits SEC (GCTL/CCTL0 + sources 37 and 91), SPI1 slave
    (real REG_SPI1_*; RX watermark PROVISIONAL), hands asm the buffer
    pointers via _set_rx_bufs/_set_tx_bufs (byte→word >>2, L1 NW=BW/4),
    then sets SPENPRI. sport_init.asm now owns _sec_isr (core SECI =
    IVT slot 15 — there are NO per-peripheral core vectors on 2156x;
    demux via SEC_CSID, ack SEC_END, secondary regs SRRFL+SRD1L) +
    _sport_dma_work ping/pong toggle. spi_handler ISRs became
    _spi1_rx_work (rts) with real MMR addresses. main.asm enables
    IMASK SECI + MODE1 IRPTEN before the config wait (config arrives
    over SPI).
  - Remaining for hardware bring-up (all marked in-source):
    FLAGS_REG chip-id detect is still an invented address; SPI RX
    watermark + SPI_RDY flow control provisional; CKRE/MFD pending
    dsp4-logic RTL; verify SEC CSID/END + asm MMR dm() semantics;
    ISR-clobber conventions in the generated node kernels unaudited.
  - CKRE/MFD are PROVISIONAL until dsp4-logic RTL fixes them — encode
    the choice in shared/dsp4-logic conventions when made.
  - Pre-existing warning to clear while in there: ramp_tables.asm
    references `_ramp_profile_GainSafe`/`_ramp_profile_InstantCtl`
    without .extern (ea1092 ×3, benign but sloppy).

- [ ] <span style="color:#d97706"><b>IN PROGRESS</b></span> Create `shared/dsp4-logic/` CPLD tree
  - [x] <span style="color:#16a34a"><b>DONE</b></span> (2026-07-31) Slot/bus map source table + generator:
    `tdm-lines.csv` + `slot-map.csv` → `gen_slot_map.py` → committed
    `generated/sport_map.json` + `generated/dsp4_slot_map.vh`, stamped
    with source hash (pin per release-notes convention on every change).
    See `shared/dsp4-logic/README.md` for conventions (sport_id = DAI port
    index; global mix slot = 16*line+slot; O1→DA3 encoded).
  - Remaining: `rtl/` Verilog (clock gen, ADC/NET + NET output muxes,
    DA-lane routing) consuming dsp4_slot_map.vh; `constraints/` pin map
    for 5M1270ZT144C4N; built `.pof` labelled with source hash.
  - Open before HDL freeze: `provisional` rows in tdm-lines.csv (A_I6 Pi
    re-framing, B_O3 DAC MAIN sink) + clock-pair assignment (CG0-3).
  - Toolchain: Quartus Prime Lite 21.1.1 INSTALLED + verified 2026-07-30
    at `/opt/intelFPGA_lite/21.1` (smoke compile map→fit→asm→sta for
    5M1270ZT144C4 OK on Debian 13; .pof→SVF via quartus_cpf OK; PATH
    profile + USB-Blaster udev rule in place). Do not commit Quartus per
    repo rules. Programming: bench USB-Blaster or Pi GPIO JTAG (SVF +
    OpenOCD on CM4).

## P2 - Blocked on CCES license

License diagnosis (updated 2026-07-30): `~/.analog/cces/license.dat` EXISTS
(the 2026-07-29 "directory missing" note was stale) with 3 entries:
- EVAL exp 09-may-2026, host 001c42a3b69b — wrong host, expired.
- PERMANENT EZK-CCES (ADSP-21568 EZ-KIT), host 001c42a3b69b — activated on
  a DIFFERENT machine (this machine's NICs: 28cfe91f1e85 / 38f9d30efa11),
  and does not cover 21564 anyway (tested 2026-07-29). Rehost via ADI
  support if ever wanted here.
- EVAL exp 17-jul-2026, host 28cfe91f1e85 (this machine) — lapsed.
TESTED 2026-07-30 (definitive): builds fail 383/383 at assembly with
`[Error ea1156] A valid license is required` for BOTH `-proc ADSP-21564`
AND `-proc ADSP-21568`. Tool message enumerates file contents, not
validity: "Blackfin, SHARC (via Evaluation License - Expired),
ADSP-21568 (via EZ-KIT License)". No usable entry exists on this host —
the EZ-KIT permanent entry is node-locked to 001c42a3b69b (another
machine), so its part scope is moot here. CCES IDE showing "license
active" is not sufficient: the CLI tools resolve
`~/.analog/cces/license.dat` and every entry there fails host or date.
No other license file exists (searched home, /opt/analog, Dropbox — the
Dropbox `cces license.txt` files are just the registration email for the
expired 17-jul eval, serial EVAL-CCES-UHNY-...-NS01, host 28cfe91f1e85).
WHY THE IDE CONTRADICTS ITSELF (resolved 2026-07-30): CCES startup says
"no valid license" while Manage Licenses lists a valid 21568 with 200+
days. Both are true — the Manager LISTS file entries and shows the EZ-KIT
entry's SUPPORT window (ISSUED 15-Apr-2026 + 1yr = 15-Apr-2027 = 259 days
from today, i.e. the "200+"), but the entry fails the HOST check so no
build is entitled. Decisive clue: host 001c42a3b69b has OUI 00:1C:42 =
Parallels virtual NIC — that license was activated inside a VM (Mac
Parallels), never on this Debian host. All 5 license.dat copies on this
system (~/.analog, wine prefix, 2x repo cces-tools, ~/mx) are byte-
identical; ~/.flexlmrc points at ~/.analog/cces/license.dat. So there is
nothing to find locally — it must be rehosted.
ACTION: ask ADI to REHOST the EV-21568-SOM permanent license
(EZK-CCES-HU6H-ZAJ7-CV2K-GIAI-YPS4-B5AQ-I201) from 001c42a3b69b to
28cfe91f1e85, or request a fresh 90-day eval for this host. Then:
`PROC_TARGET=ADSP-21568 ./build.sh all` for an immediate fit proxy
(same core/L1/L2 as 21564), and plain `./build.sh all` once 21564 is
entitled. (build.sh gained the PROC_TARGET override 2026-07-30.)

- [x] <span style="color:#16a34a"><b>DONE</b></span> Build verification of unified DSP4 firmware (2026-07-30)
  - License rehosted to this machine (EZK permanent, host 28cfe91f1e85 +
    38f9d30efa11). Scope is ADSP-21568 ONLY — `-proc ADSP-21564` now fails
    with the explicit part-mismatch error, so a full CCES node-locked
    licence (AD-CCES-NODE-1, $995, covers all SHARC + up to 4 machines) is
    still needed for real 21564 card images.
  - FIT PROXY BUILD PASSED as ADSP-21568 (identical core/L1/L2 to 21564):
    ALL 642 objects assembled with 0 errors; both chips LINKED.
    chip1.dxe 1.23 MB, chip2.dxe 2.46 MB.
  - Memory headroom (words used/capacity):
    chip1 29.4% total — block3 97.3% (TIGHT), block0 68.2%, L2 49.5%,
    block2 + L2CTL1 entirely unused.
    chip2 70.5% total — L2 95.6% (TIGHT), L2CTL1 69.6%, block0 64.3%.
  - Watch items: chip1 mem_block3_bw at 97.3% and chip2 mem_L2_bw at 95.6%
    leave almost no room; the fabric remap (128 buses) and superset I/O
    nodes land on exactly these regions. Rebalance into the idle
    mem_block2_bw (0%) / chip1 L2CTL1 (0%) when reworking the LDF.
    **CORRECTED 2026-08-06:** these two "almost no room" readings were
    wrong — they measured primary regions that the LDF deliberately fills
    before spilling into an overflow region. Counting each
    primary+overflow pair, chip1 code was and is ~57% used and chip2 delay
    ~82%. See the 2026-08-06 compatibility-build entry and
    `tools/dsp/dsp_memreport.py`.
  - Repro: `PROC_TARGET=ADSP-21568 ./build.sh all` then relink with an LDF
    whose ARCHITECTURE() matches (repo LDF hardcodes ADSP-21564; the
    fit-proxy used a sed'd temp copy — do NOT commit a 21568 LDF).
- [x] <span style="color:#16a34a"><b>DONE</b></span> (2026-07-31) Group GEQ DSP node
  - C2_GRP_GEQ_01-04 added to the group chains (RECV→FDR→EQ→**GEQ**→GATE→
    COMP), 28-band, addresses appended at chip-2 1840-1951 (0 changes to
    existing cells). The 48 GrpPeq matrix cells now backfill via the
    12-band alias (alias capped at 12 — bands 13-28 have no matrix
    counterpart); `--enable-grp-geq-alias` is now passed by
    regenerate-dsp-contract.sh (remove when mx26 renames GrpPeq→GrpGeq).
  - Matrix matched cells 5405→5453; 112 canonical GrpGeq cells await the
    mx26 rename (in the not-in-matrix INFO list with the 20 superset
    cells).

## P3 - Contract evolution (waiting on mx26 / SOT work)

- [ ] <span style="color:#d97706"><b>IN PROGRESS</b></span> Expand contract beyond current CSV set
  - Tier-2 slots staged in defs.lock (D24_DSP_CFG_SHA256, D32_DSP_CFG_SHA256,
    ABSENT until mx26 provides dsp.csv files).
  - Resume: when mx26 adds src/pd/d24/dsp.csv or src/pd/d32/dsp.csv, run
    `./regenerate-dsp-contract.sh --update-lock`.
- [ ] <span style="color:#6b7280"><b>DEFERRED</b></span> FPGA mixer engine for larger products
  - Idea-gathering started 2026-07-31: [fpga/README.md](fpga/README.md)
    (feasibility: same algorithms — yes at cell-semantics level via a
    third codegen backend; same matrix control protocols — yes,
    wire-identical) + [fpga/node-portability.md](fpga/node-portability.md)
    (per-kernel map; FX engines are the one redesign item).
  - Activation gate: becomes a numbered architecture decision first.

- [ ] <span style="color:#6b7280"><b>DEFERRED</b></span> mx_master.csv as cross-domain SOT
  - Design notes + schema draft + milestones: [ideas.md](ideas.md).
  - Milestone A (lock schema/glossary) not started; D2 slot map intends to
    migrate into this SOT when it lands.

## HW - DSP4 card rev candidates (investigated 2026-07-30; ACTIVATED into rev D 2026-08-05, see D8)

- [ ] <span style="color:#2563eb"><b>NEXT</b></span> (rev D per **D8**) Add one xSPI PSRAM per ADSP-21564 ("RAM insurance" for long delays)
  - Why: 21564 has no DDR controller; its OSPI + serial RAM is ADI's intended
    external-memory path (EV-21568-SOM pairs the same no-DDR family with
    256Mb xSPI RAM). Buys bulk delay memory with a minor rev — card stays
    LQFP, no DDR routing. Staying on 21564 (vs 21569) otherwise confirmed:
    same core/1 GHz, 2MB L2 vs 1MB, no BGA respin.
  - Capacity/bandwidth: 32 MB ≈ 85 channel-seconds @96k/32-bit per chip;
    block DMA (2 bursts/channel/block, ≥128 B payload, ~30 B-equiv overhead
    per burst) → all 32 inputs delayed ≈ 10% of octal bus @133 MHz DDR.
    Bandwidth is not the limit; capacity is. Min external delay ≈ 2 blocks.
  - Part candidates: ISSI IS72WVO32M8BLO256-133HLA2 (256Mb octal xSPI,
    133 MHz DDR, 1.8 V, BGA-24 — exact EV-21568-SOM part; IS66WVO32M8
    industrial sibling). Alt: AP Memory APS25608N/12808L/6408L (verify
    Xccela dialect vs OSPI driver). Budget fallback: APS6404L-3SQR
    (64Mb quad, 3.3 V, SOIC-8, no 1.8 V rail needed).
  - Schematic review 2026-07-30 (see `MW/D24/HW/schematics/D24 DSP rev C -
    review markup 2026-07-30.pdf`): xSPI_RWDS (p9) / xSPI_SEL2 (p23) NC and
    PA_02/03/06-10 free on the LQFP-120, BUT OSPI0 shares the SPI2/Port-A
    pin group and the Pi link already occupies PA_00/01/04/05 — shared by
    BOTH DSPs via the 33R CK1/CK2 branch split (R sheet). BMODE[2:0]
    strapped 0b010 = SPI2 slave boot (matches D1). So PSRAM retrofit needs
    a rev: move Pi RUNTIME param link to SPI0/SPI1 per DSP, keep SPI2 for
    boot only.
  - Remaining open items: (1) exact OSPI pin mux + OSPI I/O voltage domain
    on LQFP (VDD_EXT=3V3; 133-200 MHz octal PSRAMs are 1.8 V — may need a
    3V-capable PSRAM variant or confirm a separate xSPI supply domain);
    (2) exact 21564 OSPI max clock (133 vs 200 MHz);
    (3) prototype XDELAY node DMA pattern (chained MDMA, one IRQ/block)
    on EV-21568-SOM — same memory config, kit already referenced in P2.
  - Unrelated rev D fixes found in same review: CAPS child sheets (pages
    9-10) are EMPTY in the schematic — caps ARE fitted on the board
    (confirmed by Peter 2026-07-30), documentation-only fix; ROOT block
    labels still say ADSP21560; DSPB "TDM B IN" label typo; verify
    JTG_TRST pull (H1S2 JTAG header has no TRST).
  - Firmware tie-in: new external-delay node family in
    `tools/dsp/dsp_codegen.py` (shared, not per-product per D3); optional
    later: boot flash on second OSPI CS for Pi-less self-boot.

## Done (foundation, collapsed 2026-07-29)

- Contract pipeline complete (was P0-P2): defs.lock, sync-from-mx26.sh,
  hash verification, [validate-matrix-contract.py](validate-matrix-contract.py)
  (family allowlist + address sanity), regenerate-dsp-contract.sh,
  [contract-baseline.md](contract-baseline.md),
  [check-contract-drift.sh](check-contract-drift.sh),
  [release-notes-contract-convention.md](release-notes-contract-convention.md),
  [smoke-checklist.md](smoke-checklist.md),
  payload spec in [mx26-mx-dsp-integration.md](mx26-mx-dsp-integration.md).
- Alias retirement complete (2026-07-18): no active transitional families;
  see [alias-retirement-plan.md](alias-retirement-plan.md),
  [alias-audit.md](alias-audit.md) (refresh: python3 audit-compat-aliases.py).
- DSP mapping gap closed (2026-07-18): 349 missing DSP-backed matrix cells
  added upstream; remaining 951 unmapped _matrix.csv cells are expected
  MCU-only or deferred items.
- D24 schematics imported + hardware map derived; DSP4 architecture
  decisions mandated (2026-07-29).

## Workflow reference (to resume quickly)

| Command | Purpose |
|---|---|
| ./regenerate-dsp-contract.sh | Full sync + validate + generate |
| ./regenerate-dsp-contract.sh --update-lock | Same but bumps defs.lock hashes |
| ./check-contract-drift.sh | Pre-merge check |
| ./check-contract-drift.sh --strict | Strict gate — fails on any unintended drift |
| python3 audit-compat-aliases.py | Refresh alias-audit.md |
| python3 validate-matrix-contract.py | MxAdd continuity + family allowlist check |

## State snapshot (2026-07-29)

- Contract version: defs-v2026.07.31
  (source commit 8714f2f28d280fe254cbc5a29cb933539b92a54b)
- Rows: D24 4887, D32 6940; D32 cells matched/backfilled: 5537
  (EVERY DSP cell now has a matrix home — the not-in-matrix list is empty)
- Tier-2 DSP config slots: ABSENT in defs.lock
- Repo direction: unified DSP4 firmware per dsp4-architecture-decisions.md

## Owners and cadence

- Owner: DSP workflow maintainer
- Review cadence: update on every contract bump and when P1 items move.
