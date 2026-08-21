## HUB DISPATCH 2026-08-21 07:23Z — SHARC testing ① — CPLD dsp_clk ÷2 (CLKIN out of range) + closed-loop retest   [status: 🟡 dispatched]   [model: opus]

model: opus

PW decision 2026-08-21: SHARC testing is the TOP priority for this machine;
reorder the NOW queue behind it (edit the NOW header to say so).

HUB HARDWARE REVIEW RESULT (mx26 docs/backlog-d24-schematic-errata.md
"DSP4 rev C", commit 5e1d419 — read it first): **SYS_CLKIN0 is driven at
49.152 MHz, outside the ADSP-2156x CLKIN range (20–30 MHz).** The CPLD
passes the XO straight through (`shared/dsp4-logic/rtl/dsp4_logic_top.v`
line ~100: `assign dsp_clk = sysclk;`). HRM CGU: reset-default MSEL = 60,
DF = 0 → PLLCLK ≈ 2.95 GHz at reset; the boot ROM can never have run.
This fits your 08-20 conclusion that there is no evidence either SHARC
ever received a byte. It is the prime suspect — test it first.

**TASK A — CPLD dsp_clk ÷2 (24.576 MHz).**
1. Replace the pass-through with a divide-by-2 flop on sysclk (50 % duty,
   glitch-free), keep pin 140; no other RTL changes. Add an SDC
   `create_generated_clock` for it. Update tb_logic_top to check dsp_clk
   = sysclk/2. Quartus build: fitter clean, STA met, LE delta noted.
   Commit the bitstream hash-named per the existing convention.
2. Flash it via the proven path (hub did it 08-19: SVF over the CM4 at
   app@192.168.1.219 — see mx26 tasks.md "dsp4_logic.fd6a5ec69198" and
   the IDCODE 0x020a30dd before/after check). Verify PCM_CLK/PCM_FS
   still toggle (netprobe) so the rest of the CPLD is unaffected.
3. Rerun the closed loop exactly as the 08-20 dispatch defines it
   (rdyprobe1.ldr on chip 1, sample GPIO8). Also repeat the
   "!RST_D pulse with no SPI traffic" RDY observation: with a live
   part the kernel should now show behaviour that differs from the
   dead-part baseline you recorded.
4. If GPIO8 toggles: boot blink1/blink2 (LD3/LD2 for PW at the bench),
   then the production chip1/chip2 images, and resume P2.2
   (dma_cfg_init) with working instruments. Record the verdict in
   findings/tasks as "CLKIN out of range — fixed in CPLD; rev D errata".
5. If still flat after a correct ÷2 (verified by build + a GPIO-side
   sanity where possible): STOP and write the scope checklist for PW's
   bench session — probe points are the 22R pads only: R65/R33 (CLKIN,
   expect 24.576 MHz, 3V3 swing), R51/R52 (SPI2 MOSI/CLK during a
   boot), p104 (HWRST), +0.9 V at J1 P1-6. Then the JTAG-bodge decision
   goes to PW (no DSP JTAG exists on the board).

**TASK B — bookkeeping.** Restate the clock finding in
dsp4-architecture-decisions.md (CPLD is the DSP clock source; 24.576 MHz
is the contract; programmable is a feature). Add the rev-D items from the
errata list to your "Blocked on PW" or rev-D section if not already there
(no JTAG, TRST floating, RDY pull-down, !RST_D dual master + PA13=SWDIO,
RESOUT/FAULT N/C, no test points). Datasheet gap: the 21560/61/64/68
datasheet is NOT in Dropbox or the repo (analog.com blocks fetch) — PW
asked to drop it into `_mx/_temp/adsp-2156x-docs/`; when it appears,
confirm the fCLKIN min/max line and close the [verify] tags.

**HUB ADDENDUM 2026-08-21 08:45Z — datasheet now in hand (PW).** Files:
`~/db/_mx/_temp/adsp-2156x-docs/adsp-21560-21561-21564-21568.pdf` (Rev. A,
Feb 2026) + the 21564-specific HRM, EE-461 and the anomaly list, same
folder. mx26 errata DSP4 section updated (mx26 3371173). Two CONFIRMED
clock faults, which change TASK A:
1. fCKIN = 20–30 MHz (Table 23, crystal and external alike) — the ÷2 is
   right; finish step 1 (RTL/SDC/tb/build/commit).
2. **SYS_CLKIN0 is a VDD_INT-domain pin.** Abs max SYS_CLKIN0 input =
   –0.3 V to VDD_INT (Table 19); VIHCLKIN max = VDD_INT, VILCLKIN max
   +0.12 V; "must not exceed the internal (VDD_INT) voltage level". The
   CPLD drives it at 3.3 V through 22R → both SHARCs overdriven since
   first power-up; the pin clamp pumps the +0.9 V rail; parts may be
   damaged.
So: do NOT flash + retest expecting a verdict. Instead (a) commit the ÷2
build; (b) size a proto level-shift at R65/R33 to a ~0.8 V swing at pin 5
(e.g. ~560R series + ~180R shunt on the DSP side; check RC against the
24.576 MHz edges and the CPLD drive) and write it as a RED mod for PW to
fit, plus the scope checklist (first: +0.9 V sane with the card fitted,
clamping at pin 5); (c) downgrade TRST (internal pull-down per the signal
table), note BMODE2 internal PD and SYS_FAULT open-drain (external pull-up
if used). Record in this block + the decisions doc; when the desk work is
done mark the block 🔴 blocked on PW hands (bodge); push.

Constraints: chips may be freely booted/reset; ALWAYS restart matrix-app
and confirm the three MCUs verify before ending the session or between
long gaps; Dropbox via ~/db. The rev C unit is yours (no other machine
dispatched to it). Single trunk; update the dispatch block status; no AI
attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

## HUB DISPATCH 2026-08-20 18:43Z — Boot handoff investigation — apps never execute   [status: 🔴 blocked]

ROOT QUESTION: SHARC boot streams are fully consumed by the ROM (per-chunk
RDY back-pressure works end-to-end with the fixed active-low tool) but
APPLICATION CODE NEVER EXECUTES — proven tonight with a closed loop:
`src/blink/rdyprobe.asm` (blink.asm with PORTA→PORTB, bit 5 = PB_05 =
SPI2_RDY) booted on chip 1 and the Pi sampled GPIO8 flat low; the PA_12
blink images also never light LD2/LD3 (PW verified LED wiring anode→R→
PA_12, cathode→GND: pin-high = lit). All dma_cfg_init work is downstream
of this and moot until fixed.

Find why the ROM→application handoff fails. Investigate at the desk, then
verify with the closed loop (no bench eyes needed).

Suspects, in order:
1. Boot-stream format: elfloader flags are `-b SPI -bcode 1 -f BINARY
   -width 8`. Check HRM ch.40 (text already extracted to hrm.txt in your
   scratchpad from the previous session — regenerate if gone) for the
   BLOCK CODE / BCODE the 2156x ROM expects in SPI SLAVE boot (BMODE
   0b010), and whether -b SPI + bcode 1 encodes master vs slave. Parse
   the actual bytes of build/rdyprobe1.ldr (block headers: dBlockCode,
   dTargetAddress, dByteCount, dArgument; FIRST/FINAL/INIT flags) and
   check: final block flags, jump target address, and whether the ROM
   requires anything the stream lacks.
2. Entry/IVT: the .dxe has NO ELF entry (elfloader "Defaulting to
   0x90004"). Verify in the built blink/rdyprobe images that address
   0x90004 (RSTI slot) actually receives a jump to _start (dump the dxe:
   elfdump, or parse the .ldr payload for the 0x90000-block content).
   Check blink_ivt.asm places the IVT at 0x90000 and the LDF puts
   seg_pmco somewhere the ROM actually loads.
3. Post-boot core state: does the 2156x ROM hand off with the core in a
   state our code mishandles (e.g. executes from an address alias we
   didn't link for)? Compare with an ADI example loader stream if any
   ships in CCES (look under /opt/analog/cces/3.0.3/SHARC/ldr or
   examples) — diff their header/entry conventions against ours.
4. If a stream fix is identified: apply to build.sh loader() (and
   dsp4_boot.py only if the transport itself must change), rebuild
   rdyprobe1.ldr, and VERIFY with the loop below. Iterate until GPIO8
   toggles.

CLOSED-LOOP VERIFICATION (run as often as needed):
  ssh app@192.168.1.219 'cd /home/app/dspboot && python3 dsp4_boot.py \
    --ldr rdyprobe1.ldr --chip 1' \
  && ssh app@192.168.1.219 'for i in $(seq 1 12); do pinctrl get 8 | \
    grep -oE "lo|hi"; sleep 0.25; done'
Success = alternating lo/hi (~1 Hz). Copy fresh rdyprobe1.ldr to
/home/app/dspboot/ before each run. rdyprobe.asm is untracked — commit it
(it is now a permanent bring-up tool) with a header comment.

After GPIO8 toggles: boot blink1/blink2 and note in tasks.md that PW
should confirm LD3/LD2 blink at next bench visit (1 Hz / 2 Hz — also the
free CCLK measurement); then the production/park builds become meaningful
again and P2.2 resumes with working instruments.

Constraints: chips may be freely booted/reset (PW has released the
bench; the bisect state is void anyway). ALWAYS restart matrix-app
(sudo systemctl restart matrix-app) and confirm the three MCUs verify in
/home/app/logs/log before ending the session or between long gaps —
the unit must not be left on a frozen splash. Dropbox via ~/db. Single
trunk; update the dispatch block status; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

**Outcome 2026-08-20 20:20Z — 🔴 NOT FIXED. GPIO8 is still flat low after
every variant tried, so the handoff still fails. But the suspect list is
now much shorter: the boot stream and the toolchain flags are CLEARED with
evidence, two genuine defects in the boot host were found and fixed, and
the one assumption everything rested on — that the parts were receiving —
turns out to have no supporting evidence at all. Unit restored, all three
MCUs verify, app running.**

### The closed loop, run many times — always flat

`rdyprobe1.ldr` booted on chip 1 and GPIO8 sampled, across the full cross
product of SPI mode {0, 1} × post-reset settle {0.05 s, 0.5 s, 2.0 s}:
`lo` on every sample of every run. Nothing tried tonight moved it.

### Suspect 1 (boot-stream format) — CLEARED, with the bytes

Every block of `rdyprobe1.ldr`, `blink1.ldr` and the 207 KB production
`chip1.ldr` was parsed field by field against HRM ch.40 Fig. 40-15 /
Table 40-27. The streams are textbook:

- Headers are 16 B: BLOCK CODE / TARGET ADDRESS / BYTE COUNT / ARGUMENT.
  HDRSIGN = 0xAD (core 0) on every block; the HDRCHK XOR checksum was
  recomputed and matches on every block; `chip1.ldr` parses cleanly
  through 608 blocks and lands exactly on EOF (0x32814 = file length).
- First block = `BFLAG_FIRST|BFLAG_IGNORE`, count 0, TARGET_ADDRESS
  **0x00090004** (the RSTI slot — the entry point the kernel writes to
  RCU_SVECT0 at termination), ARGUMENT = offset of the final block.
  Final block = `BFLAG_FINAL`, count 0, same target. Both correct.
- The IVT **is** in the stream: a 48-byte payload block (8 NW slots × 6
  bytes) to 0x28240000. That address is right: NW 0x00090000 ↔ BW
  0x00240000, 6 bytes per 48-bit word, which is exactly why the stock
  CCES `ADSP-21564.ldf` starts `mem_block0_bw` at 0x002403F0 (0xA8 words
  × 6). Slot 1 (RSTI, word index 4) decodes as `jump 0x1C0000` — the SW
  address of `_start` at BW 0x380000. `BFLAG_AUX` is correctly absent:
  elfloader already emits byte-space addresses, so no PM translation is
  wanted.
- `-b SPI` vs `-b SPIHOST`: elfloader 6.4.2.1 emits **byte-identical**
  output for both (checked on blink1). `build.sh` now says `SPIHOST`
  anyway, because `-b SPI` documents the master/flash case and this is
  the host-push case. `-bcode 1` is right — HRM Table 40-19 gives
  SPIS_BCODE `00xx` = single-bit SPI bus, and 1 is in that range. (The
  BCODE nibble is also the first byte of the stream, which is what
  Table 40-18's SPICMD auto-detect reads.)

Nothing in the image explains the failure.

### Suspect 2/3 (entry, board straps, clock) — CLEARED off the schematic

Read at 1200 DPI from `D24 DSP.pdf` p5/10 (DSPA, U6):

- `SYS_BMODE0` = **pin 105 → GND**, `SYS_BMODE1` = **pin 106 → VDD_EXT**,
  `SYS_BMODE2` = **pin 82 → GND**. BMODE[2:0] = 0b010 = SPI Slave Boot
  (HRM Table 40-14). The strap is right. (`SYS_RESOUT` p107 is NC, so
  there is no reset-done signal to watch.)
- `SYS_CLKIN0` = pin 5, fed from **DSP_CLK through R65 (22R)**.
- `SPI2_RDY` → **PB_05** through R38 (22R), with R34 10K to GND —
  confirming what `rdyprobe.asm` drives is the right pin.
- SPI2 on DSPA: MISO→PA_00, MOSI→PA_01, CLK→PA_04, SS→PA_05.
- The S MCU (U7, p3/10) housekeeping SPI is on **ISPI0/1/2**, which are
  DIFFERENT nets from the Pi's SPI0/1/2 — so H1S1 is not a second master
  on the boot bus. It *is* a second driver on `!RST_D` (U7 pin 47).

**The LOGIC CPLD is alive and clocking.** LOGIC masters the Pi PCM port,
and `PCM_CLK` (GPIO18) / `PCM_FS` (GPIO19) read as TOGGLING at the Pi.
`dsp_clk` is a pass-through of the same `sysclk` that feeds the clkgen,
so the "unprogrammed CPLD = no DSP clock" theory is dead as stated.
`!RST_D` really does go low when the Pi drives it (verified by reading
the net back).

### TWO REAL DEFECTS FOUND AND FIXED in `dsp4_boot.py`

1. **SPI clock mode was 0; the boot kernel uses mode 1.** HRM ch.40:
   "In SPI slave boot mode, the boot kernel sets the SPI_CTL.CPHA bit and
   clears the SPI_CTL.CPOL bit", and ch.15 fixes the numbering —
   "mode-0 (CPHA=CPOL=0) and mode-3 (CPHA=CPOL=1)" — so CPHA=1/CPOL=0 is
   **mode 1**: MOSI is latched on the FALLING edge. A mode-0 host changes
   MOSI on exactly the edge the kernel samples. Now `SPI_MODE = 1`, with
   `--spi-mode` as an escape hatch. (The RUNTIME link is a separate
   question and correctly stays mode 0 — `spi2_init()` leaves CPOL and
   CPHA clear, matching `dsp4_diag.py`.)
2. **No settle time after reset release.** HRM Fig. 40-7 does not use a
   timer: the host waits for SPI_RDY DEASSERTED then ASSERTED, which is
   the kernel saying "SPI2 is up". That handshake does not exist on this
   card (pull-downs, see below), so the host was clocking bytes
   microseconds after `!RST_D` released, while the part was still in
   pre-boot. Now `POST_RESET_S = 0.500`, `--post-reset-delay` to override.

Both are real bugs by the manual. Neither, alone or together, made GPIO8
move — so there is at least one more cause.

### The finding that matters most: "the stream was consumed" was never evidence

New tool **`tools/pi/dsp4_netprobe.py`** asks the only question that
discriminates on a bus like this one: make the Pi pin an input, select the
internal pull-up, read; select the internal pull-down, read. Follows both
= nothing else drives it. Result:

| net | Pi | verdict |
|---|---|---|
| SCK | GPIO11 | HELD HIGH by something stronger than the Pi pull |
| MOSI | GPIO10 | HELD HIGH by something stronger than the Pi pull |
| MISO | GPIO9 | floats |
| CS1 / CS2 | GPIO6 / GPIO24 | floats (the H1S1 CS1-6 fix holds) |
| RDY1 / RDY2 | GPIO8 / GPIO12 | HELD LOW (R34 / R22, as designed) |
| !RST_D | GPIO16 | HELD HIGH (H1S1 U7 p47 also drives it) |
| PCM_CLK / PCM_FS | GPIO18 / GPIO19 | TOGGLING — the CPLD is running |

And a `!RST_D` pulse with **no SPI traffic at all**, sampling SPI_RDY every
~15 µs for 1 s: not one HIGH, on either chip, on any run. A 64 KB blast of
deliberate garbage at 20 MHz with no flow control: also not one sustained
HIGH — and a kernel that rejects a bad header should stop draining and let
the RX FIFO fill within ~32 bytes.

Because the card's pulls rest SPI_RDY ASSERTED, "every chunk was accepted"
is what a *dead* part looks like too. **There is currently no positive
evidence that either SHARC has ever received a single byte.** Every prior
"the stream was consumed" reading is compatible with the parts never
having listened. That is the honest state of the investigation.

### Committed alongside

- `src/blink/rdyprobe.asm` — now a permanent bring-up tool with a proper
  header, plus a `./build.sh rdyprobe` target. `blink()` and `rdyprobe()`
  are one parameterised `tiny_image()`; `blink1.ldr` is byte-identical
  after the refactor, checked.
- `LDRFLAGS` is now defined once and shared by `loader()` and
  `tiny_image()`.
- `tools/pi/dsp4_netprobe.py` (above), deployed to `/home/app/dspboot/`.

### Next — in this order

1. **Prove or disprove that a SHARC is receiving.** Everything else is
   guesswork until this is settled, and it needs a scope at the part:
   SYS_CLKIN0 (p5) for DSP_CLK actually arriving, then PA_04/PA_01
   (SPI2 CLK/MOSI) during a boot, then SYS_HWRST (p104). One session with
   a probe answers what a week of desk work cannot.
2. ~~The one board assumption still unverified~~ **VERIFIED 2026-08-20
   (hub): PA_00=SPI2_MISO, PA_01=SPI2_MOSI, PA_04=SPI2_CLK,
   PA_05=SPI2_SEL1/SS, PB_05=SPI2_RDY — from ADI's own pinmux data:**
   `ADSP-21564-pinmux.xml` inside CCES
   `Eclipse/plugins/com.analog.crosscore.addins.pinmux_*.jar`
   (extracted to /tmp/pinmuxjar on this machine; the jar is the local
   authoritative pin-function source — datasheet fetch no longer
   blocks anything). Schematic net names correct on every SPI2 pin;
   rdyprobe drives the right pin. Suspect list for the scope session
   accordingly narrows to the physical layer: VDD_INT (+0.9 V core
   rail) actually present at the card, SYS_CLKIN0 actually clocking,
   SYS_HWRST behavior, then PA_04/PA_01 during a boot. The HRM has no pin-function table
   (it is in the datasheet, which is not in `_mx/_temp/adsp-2156x-docs` —
   only `adsp-2156x_hwr.pdf`), and analog.com times out on fetch. If the
   two are the other way round the parts have never seen MOSI. **Get
   `adsp-21560-21561-21564-21568.pdf` into the Dropbox docs folder and
   check PORTA against p5/10.**
3. Rev-D hardware items, both from tonight: R34/R22 want to be pull-UPs
   (already logged 17:16Z; tonight shows exactly what it costs — no
   liveness signal at all); and `!RST_D` has two masters (Pi GPIO16 and
   H1S1 U7 p47) with no arbitration.
4. Left in the working tree, NOT committed, from an earlier session: a
   `DSP4_BISECT == 4` park in `src/dma_config.c` (its `#error` guard text
   still says 0-3). It is out of scope for this dispatch — finish or drop
   it deliberately.

## HUB DISPATCH 2026-08-20 17:16Z — P2.2 fix flash + readback verification   [status: 🔴 blocked]

**Outcome 2026-08-20 18:30Z — production images built and BOOTED into both
SHARCs (a first: with real flow control), but the readback verdict is FAIL
— both chips still echo all-zero, so P2.2 is NOT verified. Separate and
bigger find on the way there: `dsp4_boot.py` had the SPI_RDY polarity
INVERTED, and every boot before today only worked because H1S1 was
driving the shared CS3/CS4 nets high. Fixed and proven. Unit restored,
all three MCUs verify, app running.**

### What was done

1. **Build.** `DSP4_BISECT=0 ./build.sh all` — production, 0 errors.
   Confirmed the scaffolding really is compiled out: `elfdump -sym` on
   `build/chip{1,2}/dma_config.doj` shows no `_diag_stage_set` reference
   on either chip. Artifacts `chip1.b4090de01d5d.ldr` (207108 B) +
   `chip2.bb2b24db8617.ldr` (108172 B), hash-named, `ldr/manifest.txt`
   updated with the superseded pair recorded.
2. **Deploy.** scp'd to `app@192.168.1.219:/home/app/dspboot/`, sha256
   re-verified on the unit. matrix-app stopped, `S_RESET` (`*`) sent
   twice at 115200 8N1 on `/dev/serial0` with 2 s between, matching
   `Boot.FlashFirmwareViaSerial`.
3. **Boot — failed, then root-caused, then succeeded.** See below.
4. **Readback — FAIL.** See "The readback verdict".
5. **Restore.** matrix-app restarted; `MCU verified: // H1S4 SW Left`,
   `// H1S1 DSP`, `// H1S3 SW Right` and `Boot.Loop() - MCU boot
   verified: H1S1 / H1S3 / H1S4` at 18:30:31-37Z. Unit left whole with
   the production images loaded in both DSPs.

### THE BOOT-TOOL BUG — SPI_RDY polarity was inverted (fixed)

First boot attempt failed on BOTH of the tool's attempts, chip 1, before
a single byte: `SPI_RDY never asserted within 2.0s`. GPIO state read at
the time: `!RST_D` (GPIO16) = 1 (released), CS1 (GPIO6) = 1, **both RDY
lines low** — chip1 GPIO8 = 0, chip2 GPIO12 = 0.

- **The tool waited for HIGH.** Its docstring reasoned from the board's
  10K pulldowns (R34 DSPA / R22 DSPB) that asserted must be high.
- **The HRM says the opposite for boot.** Ch.40, SPI Slave Boot Mode:
  "In SPI slave boot mode, SPIx_RDY functionality is critical. The
  SPIx_RDY output is used for back pressure and requires a pulling
  resistor. **The boot code requires the SPIx_RDY signal function as
  active-low.**" The polarity during boot is the on-chip boot kernel's
  and is not configurable. Asserted = 0. Both parts were sitting there
  ready and the tool was waiting for the one level that never comes.
- **Why it only broke today.** CS3/CS4 are SHARED nets — Pi RDY inputs
  AND H1S1's "DSP 1/2 chip SPI_RDY" monitors (`MW/D24/HW/hardware-map.md`
  §3a). Until the 2026-08-20 17:17Z reflash, H1S1 drove CS1-6 push-pull
  HIGH, so the Pi always read 1 and **every RDY wait in every boot to
  date passed vacuously — all previous boots ran with no flow control at
  all.** Making CS1-6 inputs exposed the real line. The CS1-6-inputs
  change is correct and stays; it just uncovered this.
- **This also explains the "first attempt always fails, retry works"
  quirk** (reproduced ×3, 2026-08-19/20) — a timing race against a line
  nobody was reading correctly. With the polarity fixed, both chips
  booted on **attempt 1/2**, no retry.
- **Fix** (`tools/pi/dsp4_boot.py`): `wait_ready()` now takes
  `active_low`, defaulting to `RDY_ACTIVE_LOW = True` with the HRM
  citation; `--rdy-active-high` is an escape hatch, not a normal option.
  Threaded through `boot_chip`/`boot_chip_retrying`; module docstring
  corrected; the timeout message now names the expected level and points
  at the shared-net cause. Exercised off-target (asserted/stuck/timeout
  in both polarities) plus `--dry-run`; deployed to `/home/app/dspboot/`,
  md5 matches the repo copy.
- **Result:** `chip 1: attempt 1/2 OK — 207872 bytes sent on CS1`,
  `chip 2: attempt 1/2 OK — 108544 bytes sent on CS2`.

**HARDWARE ITEM for rev D — R34/R22 are the wrong way round.** The HRM
wants the pull to hold the line DEASSERTED while the part is in reset
("allows the processor to hold off the host while the processor is in
reset"). With boot fixed active-low, a pull-DOWN rests the line
ASSERTED, so the hold-off does not exist on this card and no host-side
wait can prove a part is alive or out of reset. Back pressure mid-stream
still works (the DSP drives the pin push-pull to deassert). Changing
R34/R22 to pull-UPS restores the hold-off — and would then also flip the
runtime `SPI_CTL.FCPL` to 0. Until that happens boot and runtime
legitimately disagree on polarity: `dsp4_boot.py` active-low,
`dsp4_diag.py`/`dsp4_config.py` active-high. Noted in `dma_config.c`
beside the `FCPL` write.

### The readback verdict — FAIL, and it cannot localise the fault

Against BOTH chips (`--cs-gpio 6 --rdy-gpio 8` / `--cs-gpio 24
--rdy-gpio 12`):

- With the runtime RDY gate honoured: `SPI_RDY never asserted` — SPI2 is
  never configured, so the pin is never driven and the pulldown holds it
  at 0.
- With the gate bypassed (`--rdy-active-low --resync`, which makes the
  resting-low line read as asserted so the transaction goes out):
  `response out of step reading 0xE000: echo 0x00000000, expected
  0xE0002000` — **all-zero echo, identical to the pre-fix symptom.**
- MAGIC / CHIP_ID / BOOT_STAGE / TICKS: none obtainable. No acceptance
  criterion from the dispatch was met.

**Why this is not evidence against the P2.2 fix.** `spi2_init()` runs at
DIAG_STAGE(5), *after* `arm_region(A)`, `arm_region(B)` and `sec_init()`
— i.e. the diagnostic link comes up downstream of the entire suspect
region. An all-zero readback therefore means "did not reach stage 5" and
says nothing about WHERE. It reads the same whether the part still dies
on lane index 4 of region A or now dies somewhere new. The SPI readback
was never able to bisect this; **LD2/LD3 is the only instrument that
can, and that needs bench eyes.**

**The addressing fix itself re-verified at desk level** against
`/opt/analog/cces/3.0.3/SHARC/include/sys/ADSP-21564.h`:
`REG_DMA10_DSCPTR_NXT = 0x31023000`, `REG_DMA17_DSCPTR_NXT = 0x31023380`,
`REG_DMA7_DSCPTR_NXT = 0x31022380`, and DMA8/DMA9 (MDMA0) sit off at
0x310A7000/0x310A7080. `sport_dma_base()` reproduces all of these
exactly. The fix is right; it was simply not sufficient on its own, or
the remaining fault is elsewhere.

### Next at the bench (PW, LD2 needed)

1. `DSP4_BISECT=1 ./build.sh` (park after `arm_region(A)`) and boot chip 1
   with the **fixed** boot tool. Steady 1 Hz square on LD2 = the SPORT4-7
   base fix closed the region-A wedge and the remaining fault is
   downstream; slow single blink = region A still dies and there is a
   second cause in `arm_region`.
2. Then `DSP4_BISECT=2` (park after `arm_region(B)`), then `=3`
   (EN-last) if A is implicated again.
3. Item 3 (clear the bisect scaffolding) stays BLOCKED — the scaffolding
   is now the only working instrument. Item 4 (`dsp4_config.py`, stage
   5→6) stays blocked behind a stage-5 readback.

### Deviation from the dispatch, declared

The dispatch's step 5 said one boot retry maximum and then mark 🔴. The
first boot failure was diagnosed to a tool bug with a documented HRM
citation rather than retried blind, the tool was fixed, and the boot was
run once more — which is what got both images loaded at all. The
readback that followed is the honest verdict and is reported as FAIL.
No CPLD or MCU was flashed; only the DSPs, `/home/app/dspboot`, and the
app stop/start were touched.


Flash the P2.2 wedge fix and verify by SPI readback — no bench eyes
available; the diag readback IS the verdict. PW has waived the
before-datapoint LD2 read; chip1's parked bisect state may be discarded.

Context: root cause fixed in fff7506 (sport_dma_base — SPORT4-7 at
0x31023000). Chip1 currently runs the round-1 park build, chip2 the
l1_to_sys-only build (both hung, harmless). Unit app is running with the
new H1S1 build; H1S1 proven not to drive !RST_D. dsp4_boot.py now has
the auto-retry. Dropbox via ~/db only.

Sequence:
1. Pull main. Build BOTH chips with **DSP4_BISECT=0** (production — no
   park, no stamps; note the current default is 1). `./build.sh all`,
   commit the .ldr pair hash-named per the artifact convention.
2. scp the .ldr pair to app@192.168.1.219:/home/app/dspboot/. Stop
   matrix-app, S_RESET '*' (hold slaves), run dsp4_boot.py for both
   chips (its auto-retry covers the hung-state first-attempt quirk).
3. Verify via dsp4_diag.py against EACH chip. Acceptance:
   - MAGIC correct, CHIP_ID = 1 and 2 on the right chips (proves CS
     routing), echo protocol passing (no all-zero echoes).
   - BOOT_STAGE = 5 (waiting for host product config) on both.
   - TICKS advancing between two reads (core alive), no unexpected
     ISSUES from the tool.
4. On PASS: restart matrix-app, confirm the three MCUs still verify,
   leave the unit whole. Update tasks.md: P2.2 marked VERIFIED ON
   HARDWARE with the readback evidence; note that item 3 (clear bisect
   scaffolding) is now unblocked and item 4 (dsp4_config.py, stage 5→6)
   is the next bench step. Commit + push.
5. On FAIL (readback still all-zero / stage < 5): do NOT thrash — one
   boot retry maximum beyond the tool's built-in retry; record exactly
   what the readback shows, restore matrix-app, mark the block 🔴 with
   findings; the staged LED bisect (DSP4_BISECT=1/2) resumes at PW's
   bench.

Constraints: touch ONLY the DSPs and /home/app/dspboot + app
stop/start — no CPLD flashing, no MCU flashing. Single trunk; update
this block's status; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

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
   - **FLASHED AND BOOTED 2026-08-20 18:2xZ** (hub dispatch 17:16Z, at the
     top of this file): production `DSP4_BISECT=0` images loaded into both
     SHARCs. **Readback still all-zero on both chips — P2.2 NOT verified.**
     The SPI diagnostic link comes up at DIAG_STAGE(5), downstream of the
     whole suspect region, so an all-zero echo cannot say where it dies;
     LD2 is the only instrument that can. The SPORT4-7 base fix itself was
     re-verified against `sys/ADSP-21564.h` and is correct.
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
     and never re-pulses `!RST_D` on the retry. **EXPLAINED 2026-08-20
     18:2xZ: the quirk was the inverted SPI_RDY polarity** (boot kernel is
     fixed active-LOW, HRM ch.40; the tool waited for HIGH and only ever
     "passed" because H1S1 drove the shared CS3/CS4 nets high until the
     CS1-6-inputs reflash). Polarity corrected; both chips now boot on
     attempt 1/2. The retry is kept — it costs nothing and keeps a part
     that genuinely needs it visible. Full write-up in the 17:16Z
     dispatch block, including the rev-D item: **R34/R22 are pull-DOWNS
     where the HRM's in-reset hold-off needs pull-UPS.**
   - Before any slave boot with H1S1 flashed: confirm !RST_D ownership
     (H1S1 PA13 = `!RST_D` vs the boot script's GPIO16 pulse). Checked
     2026-08-20: GPIO16 read 1 (released) throughout, and H1S1 does not
     drive the line — the Pi owns it in practice.

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
