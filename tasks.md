# tasks

Status: active
Date: 2026-07-30
Purpose: current work state for the mx26 -> mx-dsp workflow and DSP4 firmware.

Status colors:
- <span style="color:#16a34a"><b>DONE</b></span>
- <span style="color:#d97706"><b>IN PROGRESS</b></span>
- <span style="color:#2563eb"><b>NEXT</b></span>
- <span style="color:#6b7280"><b>BLOCKED/DEFERRED</b></span>

## Resume notes (saved 2026-07-30, evening)

Today (all UNCOMMITTED — see "Uncommitted work" below):
1. **Build verification DONE** — the big one. CCES licence rehosted to this
   machine; fit-proxy build as ADSP-21568 assembled all 642 objects with 0
   errors and linked both chips. Firmware fits, with two nearly-full memory
   regions (details in P2 section). 21564 targets still need a full
   AD-CCES-NODE-1 licence ($995).
2. **Quartus Prime Lite 21.1.1 installed + verified** for the LOGIC CPLD —
   real 5M1270ZT144C4 compile (map/fit/asm/sta) and .pof→SVF conversion
   both pass on Debian 13. CPLD work is now tooling-unblocked.
3. **DSP4 rev C schematic reviewed** against the full D24 set; marked-up PDF
   + regeneration script in `MW/D24/HW/schematics/`. Analog I/O resolved to
   DSP4 digital nets; hardware-map.md corrected.
4. **SPI-RAM (xSPI PSRAM) investigation** — deferred HW task added; the
   OSPI-vs-Pi-SPI2 pin conflict is the key constraint.

Yesterday: D24 schematics imported (`1d617ac`), hardware map + D1-D4
decisions mandated (`128f13b`), tasks reprioritized (`ba9853d`).

### Uncommitted work (tree is NOT clean)

- `tasks.md`, `MW/D24/HW/hardware-map.md` (analog→digital resolution table,
  AK4916 location fix, DA3/DAC-MAIN findings)
- `MW/D32/DSP/SHARC/build.sh` (PROC_TARGET override)
- new: `MW/D24/HW/schematics/D24 DSP rev C - review markup 2026-07-30.pdf`
  and `rebuild-review-markup.py`
- Suggested commit split: (a) schematic review + hardware map, (b) build
  verification + build.sh override + tasks.

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

Tomorrow's entry point — UNCHANGED from yesterday (P1 task 1: the slot-map
source table). Today cleared the tooling around it rather than the task
itself. Two new inputs now feed it: (a) the LDF memory rebalance must ride
along with the fabric remap, since chip1 block3 (97.3%) and chip2 L2
(95.6%) are the regions the 128-bus rework will grow into, while block2 sits
at 0% on both chips; (b) the slot map must route DSPB O1 → DA3, not DA1
(schematic review finding). Original plan:
1. KEY FINDING: D32 dsp.csv models the chip link as ONE logical SPORT
   (`sport_id=7`, ~26 bus slots). Architecture already matches D4 (mix
   summing on chip 1), but hardware is 8× TDM16 = 128 mix buses — so the
   rework is sport/slot plumbing (sport_init.asm, block_io.asm, dsp.csv
   sport params), not kernels.
2. Start by defining the slot-map source table (bus → TDM line/slot); it
   must feed BOTH gen_dsp_csv.py and the future shared/dsp4-logic/ Verilog
   (decision D2), so shape it for two consumers from day one.
3. Then rework gen_dsp_csv.py: map D32's ~26 logical buses onto physical
   MIX lines 0-1, reserve lines 2-7 for future/128-bus growth, add superset
   I/O nodes behind product config.

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
  - Repro: `PROC_TARGET=ADSP-21568 ./build.sh all` then relink with an LDF
    whose ARCHITECTURE() matches (repo LDF hardcodes ADSP-21564; the
    fit-proxy used a sed'd temp copy — do NOT commit a 21568 LDF).
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

## HW - DSP4 card rev candidates (investigated 2026-07-30, deferred)

- [ ] <span style="color:#6b7280"><b>DEFERRED</b></span> Add one xSPI PSRAM per ADSP-21564 ("RAM insurance" for long delays)
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

- Contract version: defs-v2026.07.18
  (source commit 2f92f8b9ef3465e716ea90bddaa67d91e0da77e8)
- Rows: D24 4702, D32 6856; D32 cells matched/backfilled: 5405
- Tier-2 DSP config slots: ABSENT in defs.lock
- Repo direction: unified DSP4 firmware per dsp4-architecture-decisions.md

## Owners and cadence

- Owner: DSP workflow maintainer
- Review cadence: update on every contract bump and when P1 items move.
