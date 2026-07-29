# tasks

Status: active
Date: 2026-07-29
Purpose: current work state for the mx26 -> mx-dsp workflow and DSP4 firmware.

Status colors:
- <span style="color:#16a34a"><b>DONE</b></span>
- <span style="color:#d97706"><b>IN PROGRESS</b></span>
- <span style="color:#2563eb"><b>NEXT</b></span>
- <span style="color:#6b7280"><b>BLOCKED/DEFERRED</b></span>

## P1 - DSP4 unified firmware & D24 bring-up (top priority)

Binding decisions: [dsp4-architecture-decisions.md](dsp4-architecture-decisions.md)
(D1 Pi masters DSP SPI, D2 CPLD in-repo w/ single-sourced slot map,
D3 one DSP4 firmware for D24+D32, D4 topology per schematic).
Hardware ground truth: [MW/D24/HW/hardware-map.md](MW/D24/HW/hardware-map.md)
(schematics in MW/D24/HW/schematics/, imported 2026-07-29).

- [ ] <span style="color:#2563eb"><b>NEXT</b></span> Rework `tools/dsp/gen_dsp_csv.py` to the DSP4 superset topology
  - Mix summing on chip 1 (128-bus output over 8× TDM16); chip 2 = bus
    processing + output router (DAC 1-16, DAC MAIN, codec/snake, NET 1-32).
  - Add superset I/O nodes (codec return, Pi PCM, MEMS, snake, AUX) behind
    boot-time product config; keep ONE shared DSP address map.
  - Then regenerate dsp.csv + node ASM; update dsp.plan.md (Link-Port/MCU
    relay diagram is obsolete per D1).

- [ ] <span style="color:#2563eb"><b>NEXT</b></span> Create `shared/dsp4-logic/` CPLD tree
  - Slot/bus map source table + generator emitting Verilog constants AND
    SPORT config for gen_dsp_csv.py; pin bitstream/source hash per change.

## P2 - Blocked on CCES license

License diagnosis (2026-07-29): SHARC eval expired 2026-07-17; host ID
28cfe91f1e85 matches this machine (binding fine, eval lapsed). Permanent
ADSP-21568 EZ-KIT entry does not cover 21564 CLI builds (tested).
Fix: buy permanent CCES license (recommended) or request new 90-day eval at
my.analog.com for host 28cfe91f1e85; install to `~/.analog/cces/license.dat`
(path expected by MW/D32/DSP/SHARC/build.sh — directory currently missing).
Decision 2026-07-29: defer license until code is ready to test.

- [ ] <span style="color:#6b7280"><b>BLOCKED</b></span> Build verification of unified DSP4 firmware
- [ ] <span style="color:#6b7280"><b>BLOCKED</b></span> Group GEQ DSP node
  - Matrix has 48 GrpPeq rows (4 groups × 12 bands), no GEQ nodes in dsp.csv.
  - Draft ready: guarded flag `--enable-grp-geq-alias` in MW/D32/DSP/gen_dsp.py.
  - Resume: license → build.sh → gen_dsp.py --enable-grp-geq-alias.

## P3 - Contract evolution (waiting on mx26 / SOT work)

- [ ] <span style="color:#d97706"><b>IN PROGRESS</b></span> Expand contract beyond current CSV set
  - Tier-2 slots staged in defs.lock (D24_DSP_CFG_SHA256, D32_DSP_CFG_SHA256,
    ABSENT until mx26 provides dsp.csv files).
  - Resume: when mx26 adds src/pd/d24/dsp.csv or src/pd/d32/dsp.csv, run
    `./regenerate-dsp-contract.sh --update-lock`.
- [ ] <span style="color:#6b7280"><b>DEFERRED</b></span> mx_master.csv as cross-domain SOT
  - Design notes + schema draft + milestones: [ideas.md](ideas.md).
  - Milestone A (lock schema/glossary) not started; D2 slot map intends to
    migrate into this SOT when it lands.

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

- Contract version: defs-v2026.07.18
  (source commit 2f92f8b9ef3465e716ea90bddaa67d91e0da77e8)
- Rows: D24 4702, D32 6856; D32 cells matched/backfilled: 5405
- Tier-2 DSP config slots: ABSENT in defs.lock
- Repo direction: unified DSP4 firmware per dsp4-architecture-decisions.md

## Owners and cadence

- Owner: DSP workflow maintainer
- Review cadence: update on every contract bump and when P1 items move.
