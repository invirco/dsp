# tasks

Status: active
Date: 2026-07-31
Purpose: current work state for the mx26 -> mx-dsp workflow and DSP4 firmware.

Status colors:
- <span style="color:#16a34a"><b>DONE</b></span>
- <span style="color:#d97706"><b>IN PROGRESS</b></span>
- <span style="color:#2563eb"><b>NEXT</b></span>
- <span style="color:#6b7280"><b>BLOCKED/DEFERRED</b></span>

## Resume notes (saved 2026-07-31, evening)

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

- [ ] <span style="color:#d97706"><b>IN PROGRESS</b></span> Fixed-point conversion (decision D5, started 2026-07-31)
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
    - NEXT: ROUTING (send shadows + _acc64_mac contributions),
      block_io I/O scaling (Q1.31<->Q4.28 at converter lanes only),
      meters (integer peak scan + decay), DELAY/TUBE_SAT/monitor/
      aux-input/talkback/noise small kernels, then dynamics (log2/exp2
      poly tables from fixed_ref as asm data, envelope + gain
      computer), then FX float-island boundaries. --format fixed
      becomes buildable only when every family is converted.

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

- Contract version: defs-v2026.07.31
  (source commit 8714f2f28d280fe254cbc5a29cb933539b92a54b)
- Rows: D24 4887, D32 6940; D32 cells matched/backfilled: 5537
  (EVERY DSP cell now has a matrix home — the not-in-matrix list is empty)
- Tier-2 DSP config slots: ABSENT in defs.lock
- Repo direction: unified DSP4 firmware per dsp4-architecture-decisions.md

## Owners and cadence

- Owner: DSP workflow maintainer
- Review cadence: update on every contract bump and when P1 items move.
