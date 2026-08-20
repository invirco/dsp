## HUB DISPATCH 2026-08-20 15:18Z — H1S1 aligned reflash + P2.2 prep (PW absent)   [status: 🟢 done]

**Outcome 2026-08-20 — both tasks done. TASK A: H1S1 reflashed with the
CS1-6-inputs build compiled against the RUNNING app generation
(`e80ccab5d6d8`); all three MCUs verify on reboot, DSPs untouched.
TASK B: boot-tool auto-retry + bisect variants B/C landed, and the HRM
desk-review FOUND THE P2.2 WEDGE — SPORT4-7 use DMA10-DMA17 at
0x31023000, not DMA8+ at 0x31022400; `2*sport+dir` off one base was
writing unpopulated MMR space. Fix applied (not flashed).**

### TASK A — H1S1 aligned reflash

- **Generation.** Built against `/home/app/fwbuild/matrix-aligned.h`
  (generated on-unit 2026-08-19 from `config/_matrix.mxc`, app build
  260714102659). `matrix_gen_id.py --compare` vs the unit's own
  decrypted matrix: **ALIGNED, full-id `e80ccab5d6d8`, 5412 cells,
  Sys001Skin001 = 5412**. Against mx26's baked
  `MatrixBus.Matrix.g.cs` it reports DRIFT of exactly one cell
  (`base-id 9b3c3d8f0286`): the g.cs predates `Sys001SwUpd001` (MxAdd
  6416, added on-device 2026-08-18) and still carries the dev-only
  `Aaa001Aaa001` placeholder, which shifts the `Zzz001Zzz001` sentinel
  6417 vs 6415. Hub confirmed the unit generation is the operative one.
  Immaterial either way for this image: **all four cells H1S1 actually
  compiles in are identical in both generations** — Sys001Enc001 5232,
  Sys001Skin001 5412, Sys001Test001 5414, Sys001Test002 5415 —
  confirmed in the linked ELF, `MATRIX[]` at `.rodata 0x080083b0` =
  {0, 5232, 5412, 5414, 5415}. The abandoned Dropbox-generation build
  had {0, 19479, 19727, 19730, 19731}.
- **Build.** `Debug/makefile.linux all` in the scratch copy
  `~/build-h1s1` (nothing written into Dropbox): exit 0, 0 errors,
  34036 text / 657 data / 1940 bss. 29 warnings, all pre-existing
  (`-Wpointer-sign` in DspTx/SpiTx/HAL_UART_Receive, three unused
  micGain* variables, CubeIDE `.cyclo` peer-target noise). Disassembly
  is byte-identical to the 2026-08-20 verified build except debug
  section sizes — the generation change lives in `.rodata`.
- **CS pins (acceptance 2).** All eight `GPIO_MODE_INPUT` in
  `H1S1.list`: CS5|CS2|CS7, CS8, and CS1|CS4|CS3|CS6(+BUSY,S3) groups
  each set `GPIO_InitStruct.Mode` to 0 in the disassembly.
- **Flash.** `hex2shex.py H1S1.hex H1S1` -> 2171 records / 34693 B
  image; previous pack image kept as
  `/home/app/fwbuild/pack-backup-H1S1.shex`. matrix-app stopped,
  S_RESET `*` on `/dev/serial0`, `app cli loadfw H1S1` -> MH1 loopback
  OK, S_SCAN found H1S1, all 2171 records ACKed, `// flash end of
  firmware record`, `OK: H1S1` (`logs/flash.log` 17:17-17:18Z).
- **Boot (acceptance 3).** matrix-app restarted and left running:
  `MCU verified: // H1S1 DSP`, `// H1S3 SW Right`, `// H1S4 SW Left`,
  then `Boot.Loop() - MCU boot verified: H1S1 / H1S3 / H1S4`. No new
  warnings — the only ones present are the 25 pre-existing SkinLoader
  "not in the matrix" notices (those cells are genuinely absent from
  the unit matrix, a skin<->matrix drift item, nothing to do with
  H1S1) and the pre-existing `mh1=?` build-stamp MISMATCH line.
- **DSPs untouched, as instructed.** No `dsp4_boot.py`, no `!RST_D`, no
  DSP reset. H1S1's own firmware never drives `!RST_D` — the only two
  writes to it in `main.c` are commented out and the pin is not in the
  `.ioc` — so the MCU reset during flashing did not reset either SHARC.
  Chip 1's bisect park should be intact for PW's LD2 read.
- **Flagged, not changed:** H1S1's blink handler still issues
  `DspTx(GPIOx, CSn_Pin, 0xF520, ...)` on SPI1 for all eight CS lines
  on every S_BLINK edge (ADAU-era LED writes, `matrix.cs` MainLoop).
  With CS1-6 now inputs it selects nothing, so this is strictly less
  intrusive than the build it replaced, but SPI1 SCK/MOSI still toggle
  on the housekeeping bus that carries the DSP CS provision. Deleting
  those dead calls belongs in the next H1S1 pass.

### TASK B — P2.2 prep

1. **`tools/pi/dsp4_boot.py` auto-retry.** `BOOT_ATTEMPTS = 2` with a
   `--attempts` override; every attempt is logged (`attempt n/m OK` /
   `attempt n/m FAILED`) so a part that needs the retry every time
   still says so. The retry restarts that chip's stream from byte 0 and
   deliberately does NOT re-pulse `!RST_D` (one reset line serves both
   DSPs). `Gpio` now releases and re-claims a line so the second
   attempt can re-request CS/RDY. Exercised off-target against a stub
   GPIO/SPI (fail-then-succeed and `--attempts 1` raise) plus
   `--dry-run`. Copied to `/home/app/dspboot/` so the next bench run
   picks it up (md5 matches the repo copy).
2. **Bisect round 2 ready to build, NOT flashed.** `DSP4_BISECT` in
   `dma_config.c`: 0 = production (no park, no stamps), 1 = round 1
   (default, park after `arm_region(A)`), 2 = **variant B** (park after
   `arm_region(B)`), 3 = **variant C** (write DSCPTR + CFG with
   `DMA_CFG.EN` clear, then set EN separately; parks after A so LD2
   answers the same question). `build.sh` passes it through:
   `DSP4_BISECT=2 ./build.sh`. All four values compile clean for both
   CHIP_IDs; an out-of-range value is a compile-time `#error`.
3. **HRM desk-review — root cause found (see the P2.2 note below).**
4. **`tools/pi/` sync.** `dsp4_config.py` pulled back from
   `/home/app/dspboot/` (the gpiod-v2 port) and committed verbatim;
   `dsp4_diag.py` and `dsp4_boot.py` were already byte-identical. Two
   rough edges in the ported `dsp4_config.py` left as-is so repo and
   unit stay identical, worth a tidy pass: the `if True:` block claims
   the RDY line unconditionally (crashes when `rdy_gpio is None` but
   `cs_gpio` is set), and the CS request is likewise unconditional.

Housekeeping: `~/mx26`'s `origin` was still HTTPS against a dead `gh`
token, so `git pull` there failed. Switched it to
`git@github.com:invirco/mx26.git` (same SSH key the dsp remote uses);
pulls work again and `tools/matrix_gen_id.py` is present.


Two tasks, PW absent — everything here is verifiable over SSH, no bench
eyes available. Unit access: app@192.168.1.219 (this machine's key works).
Dropbox via the space-free symlink ~/db ONLY. mx26 checkout at ~/mx26
(git pull it first; it has tools/matrix_gen_id.py and the app's baked
table src/sw/app/Core/MatrixBus.Matrix.g.cs).

**TASK A — reflash H1S1 with the CS1-6-inputs build (tasks.md NOW item 2).**
Correction to tasks.md first: it says H1S1 "has never been flashed" — STALE.
The hub flashed a matrix-aligned CS7/CS8-only build on 2026-08-19 night
(all three MCUs verify at boot since). What supersedes it is the CS1-6
build from the 2026-08-20 dispatch. Fix the tasks.md wording as part of
this task.

CRITICAL — matrix generation: the 2026-08-20 scratch build (~/build-h1s1)
compiled against the Dropbox MX/matrix.h generation (Sys001Skin001=19727),
which is NOT the running app's generation (5412). Do NOT flash that binary.
Rebuild against the running app's generation: the hub's 2026-08-19 flow
left an aligned header (matrix-aligned.h) on the unit or in its build area
— find it (check /home/app and the FW-home mechanics used that night), or
regenerate from the unit's own decrypted matrix as that flow did.
Verify alignment BEFORE flashing:
  python3 ~/mx26/tools/matrix_gen_id.py --compare <the matrix.h you built
  against> ~/mx26/src/sw/app/Core/MatrixBus.Matrix.g.cs
must print ALIGNED (base-id match).

Then: pack (H1S1.shex into the unit's firmware pack, same as 08-19) →
send S_RESET '*' on /dev/serial0 first (MH1 '?' responder is pre-loop
only) → `app cli loadfw H1S1` → confirm on reboot the app verifies
"// H1S1 DSP" AND both panels still verify.

Acceptance:
1. matrix_gen_id --compare says ALIGNED for the header actually compiled in.
2. H1S1.list of the flashed build: all eight CS pins GPIO_MODE_INPUT.
3. Boot log: H1S1 + SW Left + SW Right all verified, no new warnings.
4. tasks.md updated (item 2 done + the "never flashed" correction).

Constraints: do NOT touch the DSPs — no dsp4_boot.py, no !RST_D, no DSP
resets (chip1 carries the overnight bisect state; PW reads LD2 on return —
if the loadfw path unavoidably disturbs it, note that in the outcome, it
is re-establishable). Leave the unit with the app running.

**TASK B — P2.2 prep (desk work, no hardware contact with the DSPs).**
1. dsp4_boot.py: add auto-retry — a re-boot from a RUNNING/hung state
   fails its first attempt (SPI_RDY timeout) and works on the immediate
   retry (reproduced ×3). One automatic retry, log both attempts.
2. Prepare bisect round-2 as ready-to-build variants (guarded #ifdefs or
   committed patches — NOT flashed): variant B = park moved after
   arm_region(B); variant C = EN-write-order experiment (write DSCPTR +
   CFG with EN clear, then set EN separately).
3. HRM desk-review of the remaining dma_cfg_init suspects (DMA CFG EN
   write ordering, descriptor alignment, the lane-4/cs-mask special
   case) — findings appended to the P2.2 notes in tasks.md.
4. Sync the gpiod-v2-ported dsp4_config.py + dsp4_diag.py copies back
   from app@192.168.1.219:/home/app/dspboot/ into tools/pi/, commit.

Rules for both: work on main (pull first, push on completion); update this
dispatch block's status with a per-task outcome; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

# tasks — dsp spoke

Status: active · reprioritized 2026-08-20 (hub declutter — the full prior
text, day logs, and done-evidence live verbatim in
[archive/tasks-archive-2026-08-20.md](archive/tasks-archive-2026-08-20.md);
nothing was deleted).
Purpose: current work state for the mx26 → mx-dsp workflow and DSP4
firmware. This file is also the HUB DISPATCH queue (mx26 "machines"
model): the hub prepends dispatch blocks; sessions on this machine
execute them, commit, push `main`; the hub reviews on pull.

Trunk is `main` (`master` deleted + blocked). Mandates: `CLAUDE.md`.
Contract pin: **defs-v2026.08.20** (mx26 `345470a`; see `defs.lock` —
sync-from-mx26.sh now refuses an untagged mx26 HEAD).

## NOW — priority order (set 2026-08-20)

**Context:** the rev-C card is LIVE on the fresh digital board — CPLD
`fd6a5ec69198` flashed + regression-passed, MH1/H1S3/H1S4 verify on every
boot, H1S1 flashed 2026-08-19 (CS7/8 build) and reflashed 2026-08-20
with the CS1-6-inputs build on the running app's matrix generation, and
both SHARCs slave-boot from the CM4 — still wedged in `dma_cfg_init` on
the bench (P2.2 bisect build left running on chip1 overnight
08-19→08-20), though the cause is now understood and fixed in the tree
(item 1). This machine has direct SSH to the unit
(`app@192.168.1.219`) since 2026-08-20 — the hub-relay era is over.

1. **P2.2 — dma_cfg_init wedge: ROOT CAUSE FOUND 2026-08-20 (desk
   review), fix in the tree, NOT yet flashed.**
   - **The SPORT DMA channels are not one contiguous block, and the two
     blocks are not adjacent in the MMR map** (HRM Table 27-2 "ADSP-2156x
     DMA Channel List", Table 23-6, and `sys/ADSP-21564.h`):

     | half-SPORT | DMA channel | MMR base |
     |---|---|---|
     | SPORT0-3 A/B | DMA0-DMA7 | 0x31022000 + (2n+dir)·0x80 |
     | — | DMA8/DMA9 = MDMA0_SRC/DST | 0x310A7000 (different SCB node) |
     | SPORT4-7 A/B | DMA10-DMA17 | **0x31023000** + (2(n-4)+dir)·0x80 |

     `arm_region()` used `0x31022000 + (2*sport + dir)*0x80` for every
     lane, which is right only for SPORT0-3. From SPORT4 up it wrote
     0x31022400, 0x31022480, … — **unpopulated MMR space just past
     DMA7**. An SCB access there never completes, and the core stalls on
     its next MMR access: exactly the observed 1-flash hang. Chip 1's
     region A carries SPORT0-7, so it dies on lane index 4 (SPORT4)
     *inside* `arm_region(A)`, which is where the round-1 park says it
     dies. Chip 2 reaches SPORT4 in its region B (`c2_tx` lane index 4).
   - **Fix applied** (`dma_config.c`): `sport_dma_base(sport, dir)`
     picks the right base and half index; verified for all 16 half-SPORTs
     against the vendor header. Compiles clean for both CHIP_IDs.
     `dsp4-plumbing.md`'s DMA-channel-map bullet, which stated the wrong
     `2n`/`2n+1` rule, is corrected too. **Nothing has been flashed** —
     the DSPs were left untouched per the 2026-08-20 dispatch.
   - **Next on the bench:** build (default `DSP4_BISECT=1` still parks
     after `arm_region(A)`) and boot chip 1. If LD2 now shows the steady
     1 Hz square, the wedge is closed — then `DSP4_BISECT=2` (park after
     B), then `DSP4_BISECT=0` for a full run. PW's LD2 read on the
     CURRENT image is still useful as a before/after datapoint but is no
     longer a gate.
   - Suspects cleared by the same review, for the record: **descriptor
     alignment** is fine — the HRM requires only 32-bit alignment for
     descriptor sets ("Descriptor Set Address Alignment"), `DMA_ADDRSTART`
     only needs MSIZE alignment (MSIZE04 = 4 bytes, and the buffers are
     `unsigned int` arrays), and the descriptor element order
     {DSCPTR_NXT, ADDRSTART, CFG, XCNT, XMOD} matches the MMR order at
     +0x00/04/08/0C/10 that NDSIZE=5 fetches. **DMA_CFG.EN write order**
     is already legal — `DMA_OFF_DSCPTR` (0x00) *is* `DMA_DSCPTR_NXT`,
     which is precisely what "Startup Minimum-Enable Requirements"
     requires be written before `DMA_CFG` for descriptor-LIST flow. The
     `DSP4_BISECT=3` variant keeps the EN-last experiment available
     anyway. **The lane-4/cs-mask special case** was the right instinct
     pointing at the wrong mechanism: lane index 4 is where it dies, but
     because that lane is SPORT4, not because `cs_mask = 0x000D` is
     non-contiguous.
   - Real fix already applied (KEEP): `arm_region` converts every
     DDE-visible address core-L1 → SYSTEM via inlined `l1_to_sys()`
     (+0x28000000 for 0x00240000..0x003FFFFF; ADI libcc math). The hang
     persists at sub-step ≤4 after it — SPI2 diag readback still all-zero
     echoes.
   - Temp instrumentation in the tree (REVERT when done): `diag_stage_set()`
     stamps 1..7 in `dma_cfg_init` + `_diag_stage_set` helper in
     `diag.asm` + the park loop — now all behind `DSP4_BISECT` (0 =
     production, no park and no stamps; see item 3). Chip 2 runs the
     fixed un-instrumented build (hung, harmless).
   - Flash/boot loop, all runnable from here now: build → scp `.ldr` to
     `app@192.168.1.219:/home/app/dspboot/` → S_RESET `*` on
     `/dev/serial0` (hold slaves; matrix-app stopped) → `dsp4_boot.py
     --dir /home/app/dspboot` → observe/readback → app restart.
   - Boot-tool quirk (re-boot from a RUNNING/hung state fails its first
     attempt on an SPI_RDY timeout and works on the immediate retry,
     ×3): **auto-retry added 2026-08-20** — `dsp4_boot.py` now takes two
     attempts per chip by default (`--attempts` to override), logs both,
     and never re-pulses `!RST_D` on the retry.
   - Before any slave boot with H1S1 flashed: confirm !RST_D ownership
     (H1S1 PA13 = `!RST_D` vs the boot script's GPIO16 pulse).

2. ~~**Flash H1S1.**~~ **DONE 2026-08-20** — full evidence in the
   dispatch outcome at the top of this file. Reflashed with the
   CS1-6-inputs build compiled against the running app's generation
   (`matrix-aligned.h`, full-id `e80ccab5d6d8`); all eight CS pins
   `GPIO_MODE_INPUT` in the disassembly; `app cli loadfw H1S1` clean;
   H1S1 + SW Left + SW Right all verify on reboot.
   **Correction to the earlier wording here: H1S1 had NOT "never been
   flashed"** — the hub flashed a matrix-aligned CS7/CS8-only build on
   2026-08-19 night (`logs/flash.log` ends 18:24Z, and all three MCUs
   have verified at every boot since). What the 2026-08-20 reflash
   superseded was that CS7/8-only image.
   Still open from this pass: H1S1's blink handler issues `DspTx(...)`
   SPI1 writes for CS1-8 every S_BLINK edge (dead ADAU-era LED writes —
   they select nothing now that CS1-6 are inputs, but they still clock
   the housekeeping bus). Delete them at the next H1S1 pass.

3. **Clear the bisect scaffolding in `dma_config.c`** once P2.2
   concludes — it is all behind `DSP4_BISECT` now (`DSP4_BISECT=0`
   already compiles the clean production path), so the deletion is
   mechanical: drop the `DSP4_BISECT` block, `DIAG_STAGE`, the parks,
   the `build.sh` passthrough, and `_diag_stage_set` in `diag.asm`.
   `bca0dde`'s deliberate `for(;;)` park + diag stamps go; the
   `l1_to_sys()` fix and the `sport_dma_base()` fix STAY. No image is
   shippable before this.

4. **dsp4_config.py — next tool up** once the wedge clears: expect LED
   stage 5 (waiting for host product config) → configure → stage 6 →
   audio → steady 1 Hz. Procedure + failure signatures:
   `MW/D32/DSP/diagnostics.md`. (Sync back from `/home/app/dspboot/`
   is DONE 2026-08-20 — `dsp4_config.py` was the only one that had
   drifted; see the dispatch outcome for the two rough edges in that
   gpiod-v2 port that are worth tidying when the tool is next used.)

5. **SPORT I/O pin check via CPLD feedback loop (PW 2026-08-20).** A
   loopback build of the LOGIC bitstream (STA-gated, hash-named, clearly
   NON-SHIPPING) routes SHARC SPORT outputs back to inputs so the DSPs
   self-verify EVERY SPORT pin/lane end-to-end: firmware counter-pattern
   generator + checker per lane, verdicts via the 0xE000 diag readback.
   Also closes the provisional TDM facts without a scope (BCKI/FSI pair
   order, CKRE/MFD, D24 within-ADC8 slot order) and settles the NI0-3/
   NO0-3 crossed-direction/reversed-index question against slot-map.csv.
   Gate: wedge fix verified on the bench + SPORTs configured (stage 6).

6. **Unified D24/D32 SPORT/TDM lane map (PW, decided 2026-08-20 — full
   detail + resolutions in mx26 tasks.md "decisions queue"):** rev C =
   converters 4×TDM8/direction as fabbed; rev D = 2×TDM16/direction via
   AK5558 cascade (TDM512 @48k/24.576 MHz, datasheet-verified; clkgen
   must pin BICK↓ vs MCLK↑ ±10 ns for cascaded slaves), freeing two
   lanes/direction; 1×TDM8 AK4619; Pi lane I2S→TDM8 with ADAU7302 MEMS
   injection at slots 5-6 (chip already strapped TDM8-slot-5, R42=47K);
   ONE TDM32 pair for the network role — OUT lane broadcast to USB +
   Dante simultaneously, IN lane single granted driver with enforced
   tri-state defaults (grant toggle = virtual soundcheck), D32 snake =
   the AES67 role on the same pair. Lands as tdm-lines.csv/slot-map
   revision + rev-D modlist entries. Open: 570Z scratch-fit for the
   freed pins/LEs; AK4458 slot-select check; D32_COMPAT legacy-box
   yes/no (PW). See also the D8 amendment (CM4 masters mic-pre gain;
   CS_M via spare CS5/6) in dsp4-architecture-decisions.md.

7. **Bench observations owed (PW):** LD1 ~1.5 Hz with the CPLD live;
   TEST1-4 on the scope (J15 DNP pads); blink-image rate = free CCLK
   measurement — write the measured rate down, don't just retune.

8. **Design note queued (PW 2026-08-19):** once RUNNING, the DSP diag
   LED and LOGIC LD1 should sync to the MH1 S_BLINK system heartbeat
   rather than free-run; diagnostic burst codes stay local.

## Blocked on PW (decisions, not work)

- **UART pass-through routing matrix** (`TODO(uart-passthrough)`):
  buffered pass-through vs selectable mux vs strobed arbiter. Pin
  inventory done; system decision needed before RTL. Audio bring-up
  only — not on the panel path.
- **D9 sign-off** (`dsp4-architecture-decisions.md`, [DRAFT] since
  2026-08-06): FPGA param plane — float wire, on-fabric ingest
  conversion, fixed ramps.
- **KR260 order** (SK-KR260-G; Farnell £323.57 vs ~$431 elsewhere,
  prices 2026-08-06). Procurement ONLY — the 2026-08-07 gate stands: no
  FPGA engineering until stable DSP+LOGIC on rev C. Capture order # +
  ETA here.
- **AI-attribution history question** — recommendation stands: LEAVE IT
  (59 pre-mandate commits keep trailers; rewriting means force-pushing
  new SHAs under ~15 cross-references). New commits carry none.

## Standing reference (condensed — full history in the archive)

**Lanes (2026-08-07 set):** (1) LOGIC CPLD — on hardware since 08-18;
unused-pin root cause fixed (`RESERVE_ALL_UNUSED_PINS` primary was unset
— every prior build ground-drove unused pins; trap documented in the
qsf), `fd6a5ec69198` flashed + regression-passed 08-19. (2) DSP firmware
— both SHARCs boot; six would-be-fatal bugs already found by HRM review
(IVT SEC vector, wrong SPI port, RUWM, EMISO, TXCTL, SEC ack); P2.2
wedge in progress. (3) FPGA — procurement only, gated.

**Card signs of life:** LD1 = LOGIC pin 59; LD3 = DSPA `PA_12`; LD2 =
DSPB `PA_12`; `PA_13` = shared `!BLINK` net (input — never drive).
TEST1-4 = CPLD pins 13/12/8/7 → J15 (DNP DIL254-10: pins 1/2 +3V3, odd
GND, even TEST1-4). LED fault codes: N flashes = completed stage N,
stuck in N+1 (1 SRU, 2 SPORT, 3 DMA, 4 int-enable, 5 waiting host
config, 6 configured/no audio); healthy = steady 1 Hz square. Diag
readback block at 0xE000 (24 regs + generic MMR peek window) via
`dsp4_diag.py` — the emulator substitute; every read carries an echo
word, checked host-side. SPI_RDY: chip1 GPIO8, chip2 GPIO12, FCPL=1
(ready = high; the 10K pulldown means in-reset reads not-ready). No
SHARC JTAG on rev C (JTG_* float; rev-D item — 2-pin SWD per chip is the
cheap option, ADI-tooling support unverified).

**Boot path:** CM4 SPI2 slave boot, BMODE 0b010; CS1/CS3 = DSPA, CS2/CS4
= DSPB (CS2 = GPIO24, NOT GPIO7); `!RST_D` = GPIO16 — ONE reset line for
BOTH DSPs (a reset re-boots both); 1024-byte units; spi0-0cs overlay (no
CE pins — GPIO7/8 stay JTAG TCK / CS3-RDY1). `dsp4_boot.py` = gpiod v2.
CM4 CPLD JTAG: TCK=GPIO7 TDO=22 TDI=23 TMS=25, IDCODE 0x020a30dd.

**Build:** `./build.sh all` in `MW/D32/DSP/SHARC/` (native 21564;
fit-proxy retired). Scratch copies need `cp -aL` — `Core/Inc/matrix.h`
is a symlink into `MX/` and plain `cp -a` leaves it dangling. H1S1/panel
MCU builds: Dropbox FW home via `Debug/makefile.linux` (CM4 or here);
access Dropbox through the space-free symlink `~/db` (escaped spaces
stall dispatched sessions).

**CCES licence (AD-CCES-NODE-1):** a node-locked activation COUNTER —
4 max, no customer-side release (ADI case CS-601771-T5L1J6); 1 of 4
spent on this box; a wipe or NIC change burns one permanently. Licence
material untracked in `cces-tools/` (gitignored); originals in Dropbox
`TransferOnly/`.

**Rev D:** single mod source = Dropbox
`TransferOnly/PCB mods/dsp4-revD-modlist.md` (D8 scope: CM4-core SPI
control; supervisor shrink → G0B1/U535; PSRAM on OSPI0 + runtime link to
SPI0/1; 5M570Z CPLD — PIN_8/TEST3 must move; hardwire-chunk pass;
OSPI = 3.3 V domain → S27KL-class HyperRAM or APS6404L). Rev-C bring-up
verifies the provisional TDM facts (BCKI/FSI pair order, CKRE/MFD, D24
within-ADC8 slot order, S4 strap) → then rev-D freeze. CPLD-driven
SWD_EN3 = rev-D wiring candidate (SPARE reaches neither CPLD nor U7 in
rev C).

**MCU hygiene notes:** MH1 `'?'` responder is pre-loop only (S_RESET
before `loadfw`; proper fix = `'?'` in the ISR dispatcher). CheckS
unbounded ready/BUSY spin-waits + the blocking-HAL-read-in-ISR pattern =
rev-D firmware hygiene (patched on MH1/H1S3/H1S4 2026-08-19 — audit
other CubeIDE projects before reuse).

**Cross-repo:** Dropbox `_Matrix` = canonical cross-repo store (absorbed
as `matrix-shared-store.md`); mx26 checkout at `~/mx26` for contract
syncs (`git -C ~/mx26 pull` first).

## P3 — contract evolution (waiting on mx26)

- Tier-2 slots staged in `defs.lock` (`D24_DSP_CFG_SHA256`,
  `D32_DSP_CFG_SHA256`, ABSENT until mx26 provides dsp.csv files).
  Resume: when mx26 adds `src/pd/d24/dsp.csv` or `src/pd/d32/dsp.csv`,
  run `./regenerate-dsp-contract.sh --update-lock`.
- FPGA mixer engine for larger products — idea folder seeded
  (`fpga/README.md`, `fpga/node-portability.md`); activation gate:
  becomes a numbered architecture decision first.
- `mx_master.csv` as cross-domain SOT — deferred; notes in `ideas.md`.

## Done (foundation, collapsed)

- Contract pipeline complete: defs.lock, sync-from-mx26.sh, hash
  verification, validate-matrix-contract.py, regenerate-dsp-contract.sh,
  check-contract-drift.sh, release-notes convention, smoke checklist.
- Alias retirement complete (2026-07-18); DSP mapping gap closed
  (349 cells added upstream).
- Fixed-point conversion (D5) COMPLETE 2026-07-31 — mainline is Q4.28;
  float archived at tag `float-kernels-2026-07-31`; golden harness 9/9.
- Fabric remap + product-config boot block + plumbing slices 1-3 DONE
  2026-07-31; diagnostics instrumentation DONE 2026-08-12.
- D24 schematics imported + hardware map derived
  (`MW/D24/HW/hardware-map.md`); binding decisions D1-D8 in
  `dsp4-architecture-decisions.md`.

## Workflow reference

| Command | Purpose |
|---|---|
| ./regenerate-dsp-contract.sh | Full sync + validate + generate |
| ./regenerate-dsp-contract.sh --update-lock | Same but bumps defs.lock hashes |
| ./check-contract-drift.sh | Pre-merge check |
| ./check-contract-drift.sh --strict | Strict gate — fails on any unintended drift |
| python3 audit-compat-aliases.py | Refresh alias-audit.md |
| python3 validate-matrix-contract.py | MxAdd continuity + family allowlist check |

## State snapshot (2026-08-20)

- Contract: defs-v2026.08.20 (mx26 `345470a`) — first pin on the clean
  5161-cell post-naming-pass D24 master; D24 _matrix 5125 rows, D32 6940.
- Firmware: unified DSP4 per dsp4-architecture-decisions.md; ~75-80%
  written, hardware-verified fraction low — bring-up is the work.
- Hardware: rev-C card live; SHARCs boot; dma_cfg_init wedge = the one
  open blocker on the audio path.

## Owners and cadence

- Owner: DSP workflow maintainer (dispatched sessions + PW bench).
- Review cadence: update on every contract bump and when NOW items move.
