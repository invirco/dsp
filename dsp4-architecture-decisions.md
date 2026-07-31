# DSP4 architecture decisions

Status: accepted 2026-07-29
Scope: DSP4 card (dual ADSP-21564 + MAX V LOGIC CPLD) as used by D24 and D32.
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
