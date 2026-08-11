# tasks

Status: active
Date: 2026-08-11
Purpose: current work state for the mx26 -> mx-dsp workflow and DSP4 firmware.

> **Repo/workflow change 2026-08-11: the trunk is `main`, not `master`.**
> `origin/master` is deleted and blocked by a ruleset; the two histories
> were unified in `b75b43a` (master's working line became main's tree, so
> nothing was lost — the bring-up commit `1dbcabd` is an ancestor of
> main). If a checkout is still on `master`, switch: `git fetch origin &&
> git checkout main`. Mandates now live in `CLAUDE.md` under "Mandates".

Status colors:
- <span style="color:#16a34a"><b>DONE</b></span>
- <span style="color:#d97706"><b>IN PROGRESS</b></span>
- <span style="color:#2563eb"><b>NEXT</b></span>
- <span style="color:#6b7280"><b>BLOCKED/DEFERRED</b></span>

## Top action

Priority order set 2026-08-07 (Peter). Three lanes; the CCES licence
landed 2026-08-10, and **on 2026-08-11 lanes 1 and 2 both moved together
rather than one leading** — the work converged on one goal, so the "which
lane leads" question is answered in practice: **everything now points at
getting the rev-C card on the bench.**

1. **LOGIC CPLD for D24/D32 — ACTIVE.** RTL complete, simulated, fitted,
   STA'd, and as of 2026-08-11 carrying the TEST1-4 bring-up pins.
   Ready to flash; has still never run on hardware.
2. **DSP code for D24/D32 (ONE firmware) — ACTIVE.** Real 21564 images
   since 2026-08-10; since 2026-08-11 the build also emits bootable
   `.ldr` streams and there is a host-side loader, so the images can
   actually reach the parts. Two would-be-fatal bugs fixed (IVT SEC
   vector, wrong SPI port) — see the 2026-08-11 entry.
3. **FPGA — procurement only.** The EVK gets ordered so lead time runs in
   the background; **no FPGA engineering work starts until a stable
   DSP + LOGIC combination is running on the DSP4 rev C card.**

- [ ] <span style="color:#d97706"><b>IN PROGRESS</b></span> **(1) LOGIC CPLD — D24/D32 shared card logic**
  — `shared/dsp4-logic/` (MAX V 5M1270ZT144C4N, U3; one CPLD image serves
  both products per D2/D3 — no per-product fork). It is on the critical
  path: rev C bring-up needs a correct LOGIC image before the DSP images
  mean anything. As of 2026-08-07 the RTL is mapped, fitted, STA'd **and
  simulated** (the sim gate found two real framing bugs on its first run —
  see below); it has still **never run on hardware**.
  Work queue, in order:
  a. ~~**Simulation gate**~~ **DONE 2026-08-07** — `shared/dsp4-logic/sim/`,
     three self-checking testbenches + two behavioural models, wired into
     `build.sh` ahead of the STA gate.
  b. ~~Fix whatever (a) finds, re-fit, re-hash the bitstream.~~ **DONE
     2026-08-07** — it found two: the TDM output was launched one BCK late
     against MFD=1, and the I2S capture implemented left-justified framing
     instead of I2S. Both fixed, rebuilt, re-hashed
     (`f827e1243536`). Full write-up below.
  c. **UART pass-through routing matrix** — the standing
     `TODO(uart-passthrough)`; **now unblocked** by the S-MCU pin inventory
     (hardware-map §3a, 2026-08-05): S0-S3/BUSY + SRX/MRX are the matrix
     endpoint shared with U8, LOGIC pins are known (SRX 72, MRX 71,
     MHTX/MHRX 73/74, STRX1/0 75/76, PTRX1/0 77/84). Needs a routing
     decision from Peter before RTL.
  d. Rev-D `5M570ZT144C4N` target committed as a build variant (D8 verified
     it in a scratch Quartus run that was never committed: one illegal pin
     PIN_137/mems, C4 closes 51.95 MHz, C5 FAILS).
  e. Provisional items that can only close at bring-up stay listed, not
     guessed: BCKI/FSI in/out pair order per DSP, S4 personality strap,
     snake/DAC-MAIN parked pins.

- [ ] <span style="color:#2563eb"><b>NEXT</b></span> **(2) DSP code for D24/D32 — licence LANDED, lane open**
  — AD-CCES-NODE-1 **activated 2026-08-10** (requested 2026-07-31,
  purchased 2026-08-07). Serial delivered as an xlsx in Dropbox
  `TransferOnly/`, activated through the CCES *Manage Licenses* wizard
  (one-step online); the `ADI-CCES-…-SW01` INCREMENT now sits in
  `~/.analog/cces/license.dat` alongside the old `EZK-CCES-…` EZ-KIT
  entry, host-locked to this machine (`28cfe91f1e85` / `38f9d30efa11`).
  **Seat terms — ADI Tools Support, case CS-601771-T5L1J6, 2026-08-07,
  verbatim:** "Each node locked license is tied to a single user but can
  be loaded on up to four machines… simultaneously on 4 different
  machines (Home, Workplace, Lab, etc.) with its MAC ID. Once the
  activation count reaches the maximum limit, there is no way to archive
  the license registrations by customer itself. To reset the activation
  count, customer must contact the ADI Tools Support team via email."
  Practical reading: **it is an activation counter, not a movable seat.**
  There is no self-service way to release a machine, so a wipe, re-image,
  or NIC change spends one of the 4 permanently until ADI resets the
  count. 1 of 4 is spent on this box; spend the other 3 deliberately.
  Evidence (both untracked, see below): the policy email and the licence
  generation email + key.
  One firmware serves both products (D3); there is no D24-vs-D32 code
  split to write.
  **First real 21564 images built the same day** — plain `./build.sh all`
  from `MW/D32/DSP/SHARC/`: 692 ASM sources, 0 errors, chip1.dxe (456
  objects) + chip2.dxe (260 objects) linked against the repo
  `ADSP-21564.ldf`, no compatibility banner and no `build/COMPAT-BUILD.txt`.
  The `PROC_TARGET=ADSP-21568` fit proxy is **retired** — plain
  `./build.sh all` is the build path from here.
  Next: rev C bring-up (which in turn gates the rev D layout freeze).

- [ ] <span style="color:#6b7280"><b>PARKED (procurement only)</b></span> **(3) FPGA — order the EVK, do no work**
  — Buy the **AMD KR260** (`SK-KR260-G`, one version only, authorized
  distributor; Farnell £323.57 / 163 in stock vs ~$431 DigiKey/Mouser,
  prices captured 2026-08-06 in `docs/part-quotes-2026-08-06.csv`).
  Ordering now is purely so shipping time overlaps the DSP/LOGIC work.
  **Gate (Peter, 2026-08-07): no FPGA engineering — no HDL, no sizing
  follow-ups, no quote round — until a stable DSP + LOGIC combination is
  proven on the DSP4 rev C card.** Everything already researched stays
  recorded and idle: D9 draft sign-off, the 32-ch DRAM/pin-budget/Fmax
  thread, the parts quote round, XPE power estimates, the `ch.fir` d128
  gate. None of it is scheduled work while this gate holds.
  Next concrete action: place the order, capture order number + ETA here.

- [x] <span style="color:#16a34a"><b>DONE then RETIRED</b></span> (built 2026-08-06, retired 2026-08-10) **21568 fit-proxy build path**
  — a temporary 21568 target carrying 21564 constraints and memory map,
  used to keep the toolchain and codegen pipeline exercised before the
  21564 entitlement existed. It PASSED (692 ASM sources, 0 errors, both
  chips linked; evidence in "2026-08-06 — temporary compatibility build"
  below), and is now **retired** — plain `./build.sh all` produces real
  21564 images. `PROC_TARGET=ADSP-21568` still works as an env var, but
  anything it produces is a fit proxy and is banner-marked as one.

### KR260 order detail (folded into action 3 above)

Part **SK-KR260-G**, one version only, authorized distributor
(Mouser/DigiKey/Newark/Avnet/AMD direct; PSU, cables, SD included; avoid
bare-SoM broker listings) — the single eval system for the whole D7
fabric-only ladder (US+ fabric superset, 2× PL RGMII for MW-Net dev,
PL-only discipline per `fpga/platform-shortlist.md` Prototype path note).
Pre-order check DONE (2026-08-04, kria-apps docs): J10A (Eth3, HPB) and
J10B (Eth2, HPA) are PL RGMII; J10C/J10D are PS; SFP+ is PL GTH — 2×
fabric RGMII confirmed. Consider a second unit later for star/daisy-chain
link tests. Toolchain ready: Vivado 2026.1 licensed on this machine
(`~/.local/bin/vivado`) — **installed and idle under the 2026-08-07 gate.**

## 2026-08-11 — bring-up work: TEST pins, boot path, and TWO dead-board bugs

Peter asked whether LOGIC and DSP are ready for the rev-C card, whether
there are "hello world" pin toggles, and whether both chips boot from the
CM4. Answers went into three worked steps. **Two bugs found that would
each have produced a board that looks dead**, both verified in the linked
binary rather than by reading.

**Signs-of-life hardware (was undocumented; now in the map above).**
The card has THREE green LEDs, one per chip, each private — no
contention: LD1 off LOGIC pin 59 (`BLINK_LED`, R1 1K), LD3 off DSPA/U6
`PA_12` (R37), LD2 off DSPB/U5 `PA_12` (R4). `PA_13` is the SHARED
`!BLINK` net (also LOGIC pin 58 + supervisor) — input, never drive it.
TEST1-4 are **CPLD-only** (U3 pins 13/12/8/7): they leave on J1/J2
P17-P20, cross to D24 Digital J17/J18, and land on **J15, a DNP
DIL254-10** (pin 1/2 = +3V3, odd 3-9 = GND, even 4-10 = TEST1-4 — a
ground beside every signal). Fit a header there or probe the pads.

**(1) LOGIC — TEST1-4 assigned, bitstream re-cut.** `test[3:0]` added to
`dsp4_logic_top.v`: TEST1=fs8, TEST2=bck8 (12.288 MHz), TEST3=fs16,
TEST4=frame_pos[9] (24 kHz). Existing clkgen nets only — **156 LE,
unchanged**; 67 → 71 pins; Fmax 68.24 → 67.06 MHz, timing met, STA gate
passed. `tb_logic_top` extended (check 5): each pin must mirror its
clkgen net at every falling-sysclk sample AND actually toggle — a pin
stuck at the same value as a stuck source passes the mirror check alone.
Both checks were negative-tested (swap TEST3/TEST4 → 1023 mismatches;
tie TEST1 low → stuck). New artifact
`bitstream/dsp4_logic.2be52d4ad5b5.{pof,svf,manifest}`; slot-map
`source_hash` unchanged (`sha256:efd8d555…`) so this is an RTL/pin
change, not a contract bump. **The superseded `f827e1243536.*` was
deleted** (recoverable from git) — same call as 2026-08-07: two
committed `.pof`s with no "current" marker is a bring-up hazard. Say so
if you'd rather keep it with a warning file.
**Rev-D 570Z re-check** (scratch run, nothing committed): only ONE of
the four test pins is illegal on the 570Z die — **PIN_8 = TEST3** joins
PIN_137/mems, so rev D either moves that trace or drops TEST3. With the
other three assigned it closes at **55.88 MHz, slack +2.448 ns**. Note
that is *better* than the 50.67 MHz measured 2026-08-07 with fewer pins:
the number is fitter-placement variance of roughly ±10%, so treat "~3%
margin" as unstable and keep letting the STA gate arbitrate.

**(2) DSP — boot path built, and the two bugs.**
- **BUG 1, the SEC vector was one slot late.** `src/ivt.asm` opened with
  an unnumbered `_ivt_default` filler, which pushed every labelled entry
  one slot past its comment. Reset survived *by luck* (the filler landed
  on EMUI so `jump _start` landed on RSTI at 0x004), but `jump _sec_isr`
  landed at **0x040** — a reserved slot — while SECI at **0x03C** held an
  `rti`. Since 2156x routes every peripheral through the SEC, that is:
  no block-clock interrupt, no SPI parameter interrupt, so the DSP boots,
  reaches `.wait_boot`, and hangs forever waiting for a product config
  that can never arrive. Confirmed by dumping `sec_rth` out of the linked
  `chip1.dxe` before (jump at 0x040) and after (jump at 0x03C). Table
  rewritten against the hardware layout from CCES
  `crt_src/int_vector_code_SC5XX.asm` under `__ADSP2156x__`, every slot
  labelled with its true offset and name. IVT is now 128/260 words
  (was 260/260 — the old size was the off-by-one, not a requirement).
- **BUG 2, the firmware drove the wrong SPI port.** `dma_config.c` and
  both `spi_handler.asm` used **SPI1**; the rev-C card wires the host to
  each DSP's **SPI2** (PA_00/01/04/05, SPI_RDY on PB_05), which is also
  the `BMODE[2:0]=0b010` slave-boot port. D8's move to SPI0/SPI1 is a
  *rev-D* change. Now SPI2 throughout (0x31030000, SEC source 71,
  `_spi2_rx_work`). Also enabled RDY flow control: **FCPL=1 (active-high)
  is dictated by the board** — SPI2_RDY has a 10K pulldown (R34/R22), and
  HRM Figure 40-7 pairs pull-down with FCPL=1. That is the safe polarity:
  a part held in reset reads "not ready".
- **Chip-ID detect deleted.** `main.asm` read "FLAG0" at invented address
  0x08004040; the 2156x has no FLAG pins, and the schematic has no
  per-chip strap at all (the DSPA and DSPB sheets are identical — the
  parts differ only in which CS reaches them). `-DCHIP_ID` is the single
  source; `_start` now just publishes it.
- **Boot streams exist.** `build.sh` gained a `loader()` step:
  `elfloader -b SPI -bcode 1 -f BINARY -width 8` → `chip1.ldr` (205,760 B)
  + `chip2.ldr` (106,824 B). It ASSERTS the entry address resolves to
  0x90004 (IVT base + RSTI), because the ELF carries no entry point and a
  silently wrong default would boot the board into garbage. The fit-proxy
  marker text now covers `.ldr` too.
- **Host side: `tools/pi/dsp4_boot.py`** — HRM Figure 40-7 flow (pulse
  !RST_D, wait RDY, assert CS, chunk with RDY checks, deassert), pads to
  the mandatory 1024-byte units, refuses to run if `COMPAT-BUILD.txt` is
  present. GPIO map read off DSP4 J6: CS1=GPIO6, CS2=GPIO7, RDY on
  GPIO8/GPIO12, !RST_D=GPIO16 (**one reset line for BOTH DSPs**, so a
  reset means re-booting both — the tool defaults to both and warns
  otherwise). Also fixed `dsp4_config.py`, whose usage examples said
  `--cs-gpio 5`/`6`: **GPIO5 is CS7**, not CS1.
- Build after all of it: 692 ASM, **0 errors**, 2 pre-existing
  `biquad.asm` loop-end warnings. Memory pools unchanged, `dsp_memreport`
  exit 0.

**(3) Blink image — `./build.sh blink`.** `src/blink/{blink.asm,
blink_ivt.asm}` → `blink1.ldr` / `blink2.ldr`, 180 bytes each. Toggles
`PA_12` and nothing else: no SRU, SPORT, DMA, SEC or SPI, so it
separates "the boot stream never landed" from "it landed but the
plumbing hangs". Chip 1 ~1 Hz, chip 2 ~2 Hz, so one glance says which
part booted which image. Verified the two images differ in exactly three
bytes — the delay immediate (0x02625A00 vs 0x01312D00) — and that RSTI
sits at slot 1. The absolute rate assumes CCLK=400 MHz, which is NOT yet
measured: if the observed rate is off by N, CCLK is off by N, so
**write the measured rate down** rather than just retuning the constant.

**Still open before the card can run audio** (unchanged by today):
SPI_RDY is not honoured on the HOST side yet; `sport_init.asm` /
`spi_handler.asm` still carry 0x0800xxxx placeholder MMRs; and every
provisional TDM fact (BCKI/FSI pair order, CKRE/MFD on the scope, D24
within-ADC8 slot order, S4 strap) still needs the scope. **Also worth
confirming on the bench: the SHARC `JTG_*` pins appear unconnected on
both DSP sheets** — the ROOT DSPA/DSPB blocks carry no JTAG ports — which
would mean no emulator access to either SHARC on rev C, making the LEDs
and SPI readback the entire debug channel. The JTAG that does reach the
Pi header (TDO GPIO22, TDI 23, TMS 24, TCK 25) is the CPLD's, so the CM4
can play the committed `.svf` itself; `LEN` (S-MCU driven) gates it.

Suggested bench order: flash the CPLD first (it sources DSP_CLK — an
unprogrammed CPLD means neither DSP has a clock), confirm LD1 at ~1.5 Hz
and TEST1-4 on the scope, then `dsp4_boot.py` with the blink images,
then the real images.

### 2026-08-11 addendum — SHARC debug access: what rev C can and can't do

Peter asked whether wiring the SHARC JTAG pins would add diagnostic
value, and whether the CPLD's JTAG lines could be muxed to the DSPs.
Analysis recorded here so it does not have to be redone.

**Confirmed: `JTG_TCK/TMS/TDI/TDO` and `JTG_TRST` are floating on BOTH
DSPs.** They carry sheet-local net stubs only, and the ROOT DSPA/DSPB
blocks expose no JTAG ports, so nothing can leave the sheet. There is no
emulator access to either SHARC on rev C.

**Worth having at rev D — it is more than breakpoints.** The 21564 debug
block is a CoreSight DAP (HRM ch. 44): run control and memory/MMR
inspection after a hang; **STM with 32 hardware-event + 32
software-stimulus channels** (instrumented trace that does NOT stop the
core — the one that matters for an audio engine you cannot halt without
destroying what you are inspecting); PTM core trace with ETR routing
into system memory (no trace-port pin explosion); IDCODE as a
firmware-free presence check; and No-Boot mode (HRM 40) to halt before
the boot kernel clobbers an emulator-loaded image.

**The CPLD cannot mux its own JTAG.** On MAX V, TCK/TMS/TDI/TDO are
DEDICATED pins, invisible to the fabric — the CPLD cannot switch the
lines it is itself programmed through. Muxing would need a second copy
of the host JTAG on CPLD user I/O (~9-10 pins plus logic), and it would
put the debug path behind the part you would most want to debug.
**A daisy-chain needs no mux and no logic**: Pi TDI → U3 → DSPA → DSPB →
Pi TDO, TCK/TMS common. Costs: Quartus must be told the chain holds two
non-Altera devices (needs 21564 BSDL/IR length) when programming the
CPLD, and an unpowered or depopulated device breaks the chain.
**Cheaper still: SWD is 2 pins per DSP.** The HRM names the pin
"TMS/SWDIO" and `PADS_PCFG0.PUTMS` is a pull-up for "TMS/SWDIO (debug
port)" enabled by default at reset — i.e. an SWJ-DP, so `JTG_TMS` +
`JTG_TCK` alone give a debug port: 4 pins for both chips.
**Unverified**: whether ADI tooling gives CCES run control over SW-DP
(ICE-1000/2000 are JTAG probes) — SWD may only yield DAP/memory access
from an ARM-style probe. Confirm before betting on it.
Also: `JTG_TRST` floating — check the datasheet's unused-pin table, a
floating TRST is the classic cause of a TAP wandering out of reset.
Precedent already on the card: J3/J4 carry SWDIO (P36) / SWCLK (P76) for
the MCUs, and the Digital board's `OPT_SWD` block fans one SWD pair to
several targets via `SWD_EN[0..3]`.

**What rev C can do TODAY with no rewiring** (do this first — rev C is
fabricated, all of the above is rev D):
1. **SPI readback as a telemetry channel — biggest win.**
   `spi_handler.asm` already implements the READ flag (bit 13) and
   preloads the TX FIFO for master readback. Add read-only diagnostic
   addresses (last SEC_CSID serviced, block counter, DMA/SPORT error
   latches, boot stage reached, FIFO overruns) and the CM4 can
   interrogate a running DSP over the link it already has. That is most
   of what a debugger would be used for, in firmware already being built.
2. **SPI_RDY on CS3/CS4 as a hardware liveness bit** — driven by the
   boot ROM BEFORE application code runs, so polling GPIO8/GPIO12
   separates dead/held-in-reset from in-boot-kernel from running, with
   no transaction at all.
3. **LED fault codes** — blink patterns on PA_12 encoding the bring-up
   stage reached, on top of the plain heartbeat already built.
4. **Make TEST1-4 a switchable probe mux in the CPLD** — they are
   hard-assigned to clocks today, but LOGIC sees every DSPA input lane,
   every DSPB output lane and both clock domains. A small select
   (strap, or the provisioned S-MCU SPI on pins 60/61/62) turns four
   pins into a general-purpose scope tap. Pure RTL.
5. **Boundary-scan the CPLD over the JTAG that already reaches the Pi** —
   MAX V supports SAMPLE/EXTEST and sits on every DSP↔CPLD net, so
   interconnect (and possibly the provisional BCKI/FSI pair order) can be
   checked with neither SHARC running.

Disposition: do (1) and (2) now — firmware, on the critical path anyway,
and they largely close the gap that missing JTAG leaves. Put the
daisy-chain (or the 2-pin SWD pair) on the rev-D mod list. Skip the
CPLD-as-JTAG-mux entirely.

## TOMORROW'S ENTRY POINTS (set 2026-08-11, for 2026-08-12)

1. **Order KR260** (SK-KR260-G) — still procurement-only, still
   unblocked, and still the only thing whose lead time runs in the
   background. Farnell £323.57 vs ~$431 DigiKey/Mouser
   (`docs/part-quotes-2026-08-06.csv`). Capture order number + ETA here.
2. **Decide the AI-attribution history question.** Mandate `150620f`
   forbids AI references in git history; **59 of the 108 commits on main
   carry a `Co-Authored-By` trailer**, back to `8833abe` (2026-07-29) —
   every Claude Code session since the repo reorg, not one stray commit.
   Recommendation: LEAVE IT. Stripping means rewriting 59 commits and
   force-pushing past the ruleset, which changes every SHA from `8833abe`
   forward — and this file alone cites ~15 of them (`7175af3`, `e865f28`,
   `76c54f6`, `e16e817`, `0361e6f`, `94447ec`, `4a51e08`, …), every one
   of which would silently become a dangling reference. New commits
   carry no trailer from 2026-08-11 onward.
3. **Rev-C bench session** — the real goal. Order: CPLD `.pof`
   (`dsp4_logic.2be52d4ad5b5.pof`) → LD1 at ~1.5 Hz → TEST1-4 on the
   scope → `dsp4_boot.py` with `blink1/2.ldr` → full images. Record the
   measured blink rate: it is a free core-clock measurement (see the
   blink note above).
4. **Diagnostic readback registers + LED fault codes** (items 1-3 of the
   debug addendum). Firmware only, no hardware change, and the thing
   that makes a bench session diagnosable rather than a guessing game.
   Not yet started.
5. **Sign off or mark up D9** in `dsp4-architecture-decisions.md` — still
   carrying `[DRAFT] — not binding`. Untouched since 2026-08-06.
6. **LOGIC `TODO(uart-passthrough)`** — still needs a routing decision
   from Peter before any RTL (buffered pass-through vs selectable mux vs
   strobed arbiter). Pin inventory is done; the system decision is not.
7. Small/hygiene: `provenance:` header question for `dsp4-plumbing.md`
   (design doc vs working tracker — `tasks.md` and code are exempt);
   stale remote branch `copilot/review-tasks-md-firmware-bottleneck`
   (`ec6ab7e`) is a deletion candidate under the short-lived-branch rule;
   rev-D `5M570ZT144C4N` needs PIN_8/TEST3 rerouted or TEST3 dropped.

## 2026-08-10 — CCES licence activated; FIRST REAL 21564 IMAGES

The DSP lane is unblocked. AD-CCES-NODE-1 activated on this host and the
21568 fit proxy is retired.

**Licence.** Serial arrived as an xlsx in Dropbox `TransferOnly/`
(`License Keys-…-AD-CCES-NODE-1-….xlsx`, `ADI-CCES-…-SW01` — distinct
from the old `EZK-CCES-…` EZ-KIT serial). Activated through the CCES
*Manage Licenses* wizard, one-step online (SOAP to
`license.analog.com/cces/oneclick/v2`; there is no CLI activation path,
so don't try to hand-roll it). Headless launch, no need for the full IDE:
`cd /opt/analog/cces/3.0.3/Eclipse && DISPLAY=:1 ./cces -nosplash
-application com.analog.crosscore.licensing.manageLicenses`. Result is a
second `INCREMENT` in `~/.analog/cces/license.dat` (the EZ-KIT entry
stays), `ISSUED=10-Aug-2026`, node-locked to this box's NICs.

**Seat terms, now evidenced.** ADI Tools Support (case
CS-601771-T5L1J6, 2026-08-07): a node-locked licence is tied to a single
user and may be loaded on **up to 4 machines simultaneously** by MAC ID;
once the activation count hits the limit there is **no customer-side way
to release a registration** — only ADI Tools Support can reset the count.
So it is a counter, not a movable seat: a wipe, re-image or NIC change
burns one of the 4 until ADI resets it. 1 of 4 spent here.

**Source emails — copied into the repo but deliberately UNTRACKED**
(`cces-tools/.gitignore` is `*`; licence material is never committed per
CLAUDE.md/README), at `MW/D32/DSP/SHARC/cces-tools/license/`:
- `adi-2026-08-07-node-lock-policy-CS-601771-T5L1J6.eml` — the 4-machine
  policy above, in ADI's own words.
- `adi-2026-08-09-license-generated.eml` — myAnalog generation notice,
  order #1004067573 / web ref 2016519891, AD-CCES-NODE-1 ×1.
- `adi-2026-08-09-license-keys-AD-CCES-NODE-1.xlsx` — the key itself
  (that email's attachment).
Originals stay in Dropbox `TransferOnly/` under their myAnalog names.

**First real 21564 build.** Plain `./build.sh all` from
`MW/D32/DSP/SHARC/`: 692 ASM sources, 0 errors, chip1.dxe (456 objects,
1.27 MB) + chip2.dxe (260 objects, 2.51 MB), linked against the repo
`ADSP-21564.ldf` — no proxy LDF generated, no compatibility banner, no
`build/COMPAT-BUILD.txt`. These are production-target images. The only
warnings are the two pre-existing `ea2019/ea2020` loop-end notes in
`src/lib/biquad.asm` (unrelated to licensing; still worth a look).

**Docs de-staled** (same session): the P2 licence-diagnosis section, the
Wine/`mac-build.sh` MAC-swap material in `dsp-def.md`, the D24
`dsp.plan.md` Phase 0, `dsp4-plumbing.md`, and the licence-pending
framing across the resume notes are all gone or marked closed.

NOT done: nothing is committed (5 modified docs in the tree), and no
hardware has run — every DSP fact above is toolchain-level only.

TOMORROW'S ENTRY POINTS (priority order):
> SUPERSEDED by "TOMORROW'S ENTRY POINTS (set 2026-08-11)" above. Kept
> for the day's evidence. Both lanes moved together on 2026-08-11, so
> item 1 is answered in practice and item 2 is done (commit `1dbcabd`).
1. **Pick the lead lane.** LOGIC (1) and DSP (2) are both open now — the
   2026-08-07 priority set assumed only LOGIC could move, so it needs
   your call. Both converge on rev-C bring-up, which gates the rev-D
   layout freeze.
2. **Commit today's work** — 5 modified docs (tasks.md, dsp-def.md,
   dsp4-plumbing.md, D24 dsp.plan.md, mx26-update-handoff.md). No code
   or contract changed, so no regenerate/contract bump is due.
3. **Order KR260** (SK-KR260-G) — still unblocked and still procurement
   only. Farnell £323.57 (163 in stock) vs ~$431 DigiKey/Mouser, prices
   from `docs/part-quotes-2026-08-06.csv`.
4. **Sign off or mark up D9** in `dsp4-architecture-decisions.md` — it
   carries `[DRAFT] — not binding` until you do.
5. LOGIC lane, if it leads: the `TODO(uart-passthrough)` routing matrix
   is next and needs a routing decision from you before RTL.
6. DSP lane, if it leads: rev-C bring-up checklist — FLAGS_REG chip-id
   detect, SPI watermark + SPI_RDY flow, SEC/MMR semantics on the wire,
   BCKI/FSI pair order, CKRE/MFD on the scope, D24 within-ADC8 slot
   order. Needs the rev C card on the bench.

## 2026-08-07 — LOGIC lane opened: sim gate added, TWO framing bugs found and fixed

Priorities reset (see Top action). First LOGIC work item done: the CPLD
RTL now has a **simulation gate**, and running it for the first time found
that the never-simulated design would not have worked on the wire.

**New: `shared/dsp4-logic/sim/`** — Icarus, Verilog-2001, self-checking,
wired into `build.sh` ahead of the STA gate (`SKIP_SIM=1` overrides and is
recorded in the manifest). Two behavioural models are the arbiters:
`model_tdm_rx.v` (a SPORT with CKRE=1/MFD=1 as it sees the wire) and
`model_pi_i2s_tx.v` (the Pi PCM block transmitting I2S as a clock slave).
Three testbenches: `tb_clkgen`, `tb_pcm_reframe`, `tb_logic_top`.
`tb_clkgen` and `tb_logic_top` **passed first time** — divide ratios, FS
width, frame length, launch/sample strobe alignment, clock-pair roles by
measured format, and every routing wire including B_O1→DA3 and the
D24/D32 personality split are all as documented.

`tb_pcm_reframe` **failed**, and the failure decomposed into two
independent one-bit errors that together shifted the Pi audio by two bit
positions (`12345678` came back as `448d159e`, and slot 1's LSB leaked
into slot 2):

1. **TDM output launched one BCK period late.** The bit launched on the
   falling edge of BCK8 period P is sampled by the DSP on the RISING edge
   of period P+1, and MFD=1 puts slot 0 bit 31 on the edge AFTER the one
   that reads FS high. The old code launched the bit indexed P at period
   P, so the DSP's slot 0 bit 31 was actually slot 7's last bit (a zero)
   and the whole payload arrived one bit rotated. Fixed by launching from
   `out_period = frame_pos[9:2] + 1`.
2. **I2S capture latched one BCK early** — the old latch points
   (period 32 for left, 0 for right) implement the LEFT-JUSTIFIED format,
   not I2S. Philips I2S delays the MSB one BCK after the LRCLK edge, so
   the words complete at periods 33 and 1. Fixed and **parameterised**:
   `PCM_DATA_DELAY` (default 1 = I2S, 0 = left-justified), because the
   Pi's CH1POS is programmable — if bring-up shows different framing, one
   constant moves instead of the logic. `tb_pcm_reframe` runs BOTH
   settings, so the parameter is proven to re-align the capture rather
   than merely existing.

Also removed the dead `bit_cnt` register (assigned, never read).

Rebuild after the fix: **sim gate PASS, 156 LE / 1270 (12%), 67 pins,
Fmax 68.24 MHz** (setup slack +5.690 ns), timing met, new artifact
`bitstream/dsp4_logic.f827e1243536.{pof,svf,manifest}`. The slot-map
`source_hash` is unchanged (`sha256:efd8d555…`) — this is an RTL fix, not
a contract bump.

**The superseded `dsp4_logic.233db2b02906.*` bitstream was deleted**, not
kept alongside: it is a flashable image that is now known to corrupt the
Pi PCM lane, and D2 makes committed `.pof` files something people
program. It stays recoverable from git history. Say so if you'd rather
keep it with a warning file instead.

**Rev-D timing warning (D8).** The 5M570ZT144C4 margin measured
2026-08-05 (51.95 MHz, ~5%) is stale. Re-measured 2026-08-07 with the
fixed RTL in a scratch run (device swapped, PIN_137/mems released for the
fitter, nothing committed): **50.67 MHz, setup slack +0.611 ns, ~3%
margin** over the required 49.152 MHz, 156 LE = 27% of 570. It still
closes, but the margin is thin and every RTL addition now costs some of
it — the UART pass-through work in particular. The mandatory-STA-gate
rule from D8 is doing real work; keep it.

**Open, needs Peter before RTL:** the `TODO(uart-passthrough)` routing
matrix. The pin inventory is no longer the blocker (hardware-map §3a):
LOGIC sees SRX 72, MRX 71, MHTX/MHRX 73/74, STRX1/0 75/76, PTRX1/0 77/84,
and the matrix nets S0-S3/BUSY are multi-drop across U7 and U8 with U9
muxing the SRX source. What is undefined is what LOGIC should DO with
them — straight buffered pass-through, a selectable mux, or a strobed
arbiter — and that is a system decision, not one to invent in HDL.

## Resume notes (2026-08-06 session end)

> Entry-point list below is SUPERSEDED by the 2026-08-07 priority set in
> "Top action". Kept for the day's evidence. Where it schedules FPGA work
> (items 1, 4, 5, 7, 8) that work is now parked behind the rev-C
> DSP/LOGIC gate; ordering the KR260 is the only FPGA action that stands.

Today: Dropbox `_Matrix` cross-repo store absorbed from mx26 `fbaf2be`
(`matrix-shared-store.md`, pointers in README/CLAUDE.md/hardware-map);
**21568 compatibility build PASSED** (692 ASM, 0 errors, banner +
`build/COMPAT-BUILD.txt` marker so proxy DXEs can't pass as production);
**memory-headroom correction** — the old "block3 is TIGHT" readings were
wrong, primary regions fill then spill, so count primary+overflow pairs
(`tools/dsp/dsp_memreport.py` now does it); GAIN `.extern` generator fix
(34 → 2 warnings, and the `--force` regen proved no hand-edit drift in
the node ASM); **D9 drafted, awaiting your sign-off**; **32-ch sizing
pass** (`fpga/sizing-32ch.md`); shortlist price corrections.
Commits `7175af3`, `e865f28` — pushed, tree clean.

TOMORROW'S ENTRY POINTS (priority order):
1. **Order KR260** (SK-KR260-G) — unchanged and unblocked. **Farnell
   £323.57** (163 in stock) vs ~$431 at DigiKey/Mouser; prices captured
   2026-08-06 in `docs/part-quotes-2026-08-06.csv`. Only shipping time
   sits between here and having the eval system, so this goes first.
2. **Sign off or mark up D9** in `dsp4-architecture-decisions.md` —
   it carries a `[DRAFT] — not binding` banner until you do. Three
   things left open inside it on purpose: parameter-RAM sizing per tier,
   ramp-precision tolerance for fixed ramps (numeric-spec amendment),
   meter readback path.
3. ~~**Check CCES licence arrival**~~ **DONE 2026-08-10** — activated,
   first real 21564 images built (692 ASM, 0 errors, both chips linked).
   Rev-C bring-up is now the live follow-on; it gates the rev-D layout
   freeze. See action (2) in "Top action".
4. **Finish the 32-ch comparison**: DRAM support per part (ECP5 DDR3 vs
   SU35P DDR4/LPDDR4, soft vs hardened controller, LUT cost) → pin
   budget → Fmax → ECP5-85 quote. Also confirm the SU35P DSP48E2 count
   against DS930 (the 48 figure is from search summaries and may be
   conflated with its 48 × 36 Kb BRAM blocks; verdict holds either way).
5. **Quote round** — best placed after 4 and the pin-budget table, so it
   is one informed call rather than two. List unchanged: SU35P /
   SU55P-SU100P / AU25P @1k + Agilex 3 availability + Agilex 5 Quartus
   licensing + LFCPNX-100 + an Avant-E part + 5M570ZT144C4N +
   STM32G0B1RET6 / U535RET6 + Infineon 3.0 V octal-xSPI HyperRAM.
   Exception: if any part has a long lead time, this jumps ahead of 4.
6. **Rev D remaining OSPI open**: 21564 OSPI clock ceiling +
   xSPI-profile-2/RWDS RAM support — check the EV-21568-SOM reference
   design in the ADI portal (datasheet mirrors bot-block curl; the
   rlocman paged mirror worked for pin tables).
7. Desk work queued: per-tier pin-budget table + Vivado XPE power
   estimates (SU35P/AU25P) — feeds both 4 and 5.
8. Unchanged hub-side gate: `ch.fir` tap ceiling into d128 (biggest open
   number, ~$150-200 BOM swing). Now known NOT to affect the 32-ch tier
   — `ch.fir` is absent from d32.csv — so it is purely a flagship gate.

Low-priority tidy-ups, not blocking anything: chip2 delay pool is at
82.4% of L2+L2CTL1 and is the only pool whose overflow tier is loaded —
revisit the LDF when it passes ~90%; `TransferOnly/PCB mods/` mod lists
are a migrate-later candidate for `_Matrix/Products/D24/hw/`.

## Temporary compatibility build checklist — COMPLETE (2026-08-06)

- [x] Confirm the temporary target selection: 21568 build path with
  21564-compatible constraints and memory-map assumptions.
  — `PROC_TARGET=ADSP-21568` selects `-proc` for easm21k/cc21k/linker;
  `resolve_ldf()` generates `build/ADSP-21568.ldf` from the repo
  `ADSP-21564.ldf` by rewriting only `ARCHITECTURE()`, so every memory
  region, section, and placement rule is the 21564 map unchanged.
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

## Resume notes (2026-08-05 session end — tree clean at push)

> SUPERSEDED by the 2026-08-06 resume note above — the entry-point list
> below is kept for history. Items 1 (compatibility build) and 2 (licence
> check) are done; the rest carried forward and were re-prioritised.

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
1-2. ~~21568/21564 compatibility build; check CCES licence arrival~~ —
   **both closed**; the licence is active and real 21564 images build.
   See action (2) in "Top action".
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
- Sequencing: rev C bring-up verifies the provisional TDM facts →
  then rev D schematic freeze.

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
1. ~~CCES licence arrival → first real 21564 images~~ — **DONE
   2026-08-10**, see action (2) in "Top action".
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

The mx26 update is prepared: [mx26-update-handoff.md](mx26-update-handoff.md)
(exact mx_master.csv rows, def_master PREFIX_RULES + product keys,
GrpPeq→GrpGeq rename incl. a suspected wrong Table on the old row, and
this repo's post-sync steps). The 7 new families are pre-staged in
matrix-families-allowlist.txt (validator passes; GrpPeq retained until
the rename lands).

Remaining = hardware bring-up (rev C card):
FLAGS_REG chip-id detect, SPI watermark + SPI_RDY flow, SEC/MMR
semantics on the wire, BCKI/FSI pair order, CKRE/MFD on the scope,
D24 within-ADC8 slot order, S4 personality + S-MCU firmware side.
mx26-side: DONE 2026-07-31 (mx26 8714f2f, applied from
mx26-update-handoff.md incl. the full 28-band GrpGeq choice and the
Table bug fix). Contract bumped to defs-v2026.07.31; alias flag +
GrpPeq allowlist entry retired; matched cells 5453→5537; the
"DSP cells not in matrix" list is now EMPTY.

### Checked, no action needed
`cces-tools/license/` holds licence material — `license.dat`, and (added
2026-08-10) the two ADI source emails plus the AD-CCES-NODE-1 key xlsx.
NONE of it is tracked: the `cces-tools/.gitignore` (`*`) covers the whole
folder, re-verified with `git check-ignore -v` when the emails were
copied in. Licence material is safely untracked; nothing to purge.

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

## P2 - CCES licence — RESOLVED 2026-08-10

The 2026-07-29/30 licence diagnosis (expired evals, an EZ-KIT entry
node-locked to a Parallels VM NIC, the IDE-vs-CLI contradiction) is
**closed and no longer relevant** — it was resolved first by rehosting
the EZ-KIT entry to this machine, then permanently by activating
AD-CCES-NODE-1 on 2026-08-10. Current state, and the only licence facts
worth carrying forward, live in action (2) under "Top action".

- [x] <span style="color:#16a34a"><b>DONE</b></span> Build verification of unified DSP4 firmware (2026-07-30)
  - Ran against the rehosted EZ-KIT entry, which covered ADSP-21568 only;
    the 21564 entitlement arrived later (2026-08-10).
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
