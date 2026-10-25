provenance: AI-drafted 2026-10-25 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# DSP card (MW DSP4) rev C vs rev D — what the app and the DSP firmware must handle (S173)

PW 2026-10-25: *"the app must be compatible with both dsp card revs, and allow
for the differences, esp ram addition to revD."* This is the list the next mx26
(app) task works from. Desk only: nothing was flashed or powered.

**Sources.** Rev D: invirco/dspcard at `709a6af` (DSPC-L11, hub DRC clean),
netlist `review/l11/netlist.net`, MOD table `review/stage2-mods.md`, stage 2b
report, L8d/L8e/L8k CPLD hand-offs, L11 report. Rev C: mx26
`docs/d24-netlist-global-pins.csv` (the rev C copper). Part-level diff of the two
BOMs: rev D adds U10/U11 (HyperRAM), U12/U13 (bus switches), J7 (JTAG), R79-R86,
R89-R92, C206-C213, H1-H4; removes J5, J6, C200/C201; changes U7 (STM32U575RIT6 →
STM32G0B1RET6) and R33/R65 (22R → 1K, as already fitted on the rev C proto).

## 0. How the app tells the revisions apart

| # | detector | where it comes from | rev C | rev D | available |
|---|---|---|---|---|---|
| R | **`Sys001DspCardRev001`** (proposed cell, `proposals/CONTRACT-PROPOSAL-S173.md`) | H1S1 reads straps U7 PC1-PC3 at boot | **no reply** | **1** | after the H1S1 G0B1 port + the defs landing |
| U | **U7 chip ID** from the STM32 ROM bootloader `GET_ID` over the MH1 relay (the `loadfw` path) | the silicon itself | `0x482` (U575) | `0x467` (G0B1) | **today**, any firmware or none; disruptive (U7 is reset into its loader) |
| K | **CPLD ID knock**, reply word `0xD594<cfg>`: `cfg[10]` rev D image, `cfg[11]` strap low | `tools/pi/dsp4_logic_id.py` | `cfg[11:10] = 00` (rev C image) | `11` | once the rev D CPLD image is on the card |
| X | DSP `_extram_present` (S75 probe) | each DSP after boot | 0 | 1 when the RAM answers | rev D DSP image with the pool armed |

**Rule for the app — runtime vs flashing.** For *runtime* behaviour, R is enough
and "no reply = rev C" is fine (PW L11 Q4). For *flashing* the CPLD or H1S1,
"no reply" is NOT enough: a rev D card whose U7 is blank or not yet ported also
says nothing, and the rev C CPLD image on rev D copper is a bus fight (item 3).
**Every CPLD / H1S1 flash must first identify the card positively by U** (or K
reading a rev D image), and refuse on doubt. (Q4 in the S173 block.)

## 1. The list

Behaviour columns: what the app (A) / DSP firmware (F) does on each revision.

| # | difference | rev C | rev D | transparent? | app / firmware behaviour |
|---|---|---|---|---|---|
| 1 | **HyperRAM per DSP** (MOD 1) | none | U11 on DSPA (U6), U10 on DSPB (U5): **S27KL0642GABHI020**, Infineon HyperRAM, **64 Mbit = 8 MB each**, 3.0 V (KL family — so S75-2's voltage worry is closed for the primary part; alternates IS66WVH8M8DBLL-100B1LI, and S70KL1282 = 128 Mbit drop-in). On xSPI0 = PA_00..PA_09 + RWDS (lead 9), octal HyperBus DDR; the 3.0 V grade runs **100 MHz = 200 MB/s raw** (~170 MB/s effective, S75 §2.1) | **no** | A: show "extended delay / FX memory" features only when X = 1 (not merely rev D: a rev D card with a failed RAM must degrade to rev C limits). F: see §2 |
| 1a | — what the RAM buys (S75 §5) | chip 1 L2: 32 × 20 ms channel delays + 8 shared 250 ms slots; chip 2: 6 **mono** reverbs, FX echo clamped to **250 ms**, one main delay | chip 1: **all 32 channels up to 250 ms at once** (coded today, `DSP4_EXTRAM=1`, bit-exact vs a simulated part, zero added latency). Chip 2 (needs block kernels first, S75-8): **stereo reverbs**, FX echo to the contract's **1000 ms**, four main output delays. Each part holds ~44 s of mono 32-bit/48 kHz audio | — | A: per-rev limits on `Chan001..024Delay001` (20 ms vs 250 ms per channel; the 8-slot allocator becomes unnecessary with RAM), `Fx001DelayTime001` (250 vs 1000 ms), reverb stereo/mono. **Not** more channels (bounded by TDM lanes and chip 1's 98 % cycle budget, not memory). Not a recorder (8 MB is seconds, not minutes). |
| 1b | — costs and blockers | — | chip 1 code pool has **946 B free** in the EXTRAM arm (S75-5): code reclamation before arming; bus load 22 % worst block (chip 1) | — | F: reclaim chip-1 code first; then arm |
| 2 | **DSP runtime parameter link moves SPI2 → SPI1** (MOD 2) | boot AND runtime on SPI2 (PA_00/01/04/05, RDY PB_05) | boot on SPI2 through **U12/U13 bus switches**; runtime on **SPI1** (PA_10 CLK, PA_11 MISO, PA_12 MOSI, PA_13 SS, RDY PB_04 joined to PB_05). **CM4 side unchanged**: same B2B pins, same CS (GPIO6/24), same 33R | yes for the CM4 | A/host tools: no pin change. F: the DSP must switch its slave port to SPI1 when it enables the RAM (XSPI_EN high cuts SPI2 off the CM4). **With XSPI_EN low the rev D card behaves exactly like rev C on SPI2** — the safe common subset (§2) |
| 3 | **XSPI_EN** (PB_00, one per DSP) | PB_00 unconnected | PB_00 → RAM RESET#, the four bus-switch enables, 10K **pull-down**: low = RAM held in reset + boot path connected (power-up, any RST_D, boot); high = RAM running, SPI2 pads cut off | — | F: drive high only from RAM-aware code, only on rev D, only after the link has moved to SPI1. Harmless on rev C (open pad) |
| 4 | **DSP LED / BLINK pads move** | BLINK_LED = PA_12 (lead 35), BLINK (shared with the other DSP, U3.58, U8.48) = PA_13 (36) | BLINK_LED = **PA_14** (37), BLINK = **PA_15** (40); PA_12/PA_13 are now SPI1 MOSI/SS **wired through 22R to the CM4's SPI MOSI and DSP CS** | **no — hazard** | **The shipping DSP image drives PA_12 (diag.asm LED codes). On rev D that pin is the CM4's MOSI**: every LED transition fights the shared SPI bus (both DSPs' boot, CPLD, codec, 595 chain). The current image must not run on a rev D card (finding S173-1). F: drive PA_14 always (open pad on rev C), PA_12 only once the board is known to be rev C |
| 5 | **SPI_RDY pull** (MOD C) | R22/R34 10K to **GND** (idle = low) | to **+3V3** (idle = high: a dead SHARC looks busy) | no | Host tools: RDY idle polarity per rev (dsp4_boot.py treats boot RDY active-low and the runtime tools active-high today, `dma_config.c` FCPL note). F: the SPI2/SPI1 FCPL setting follows. fw.csv `RdyDspA/B` notes say pull-down: defs follow-up |
| 6 | **LOGIC CPLD pin-out** (L8d/L8e/L8k): ni[0], test[0], test[2], fsi[1..3], bcki[1], o_dspb[0..3] move | `dsp4_logic.qsf` | `dsp4_logic_revd.qsf` (S173): image `dsp4_logic_revd.ac2352077621`, design ID `0x52077621` | **yes, given the right image** — lane indices, slot map and DSP graph are unchanged | A: flash the image that matches the card (detector U/K), never the other: **a rev C image on rev D drives FSI1-3/BCKI1 into DSPB's O0-O3 outputs, TEST1 into the NET input NI0 and TEST3 into PI_TX2** (check_pins: 11 mismatches). Rev C image stays `dsp4_logic.99616cc44dc4` (byte-identical) |
| 7 | **BOARD_REV0** strap U3.81 | single-pin net L1 (weak pull-up reads 1) | tied to GND | — | A: K detector, and the rev D CPLD image's self-check (`cfg[11:10] = 01` = rev D image on rev C copper → refuse and reflash) |
| 8 | **DSP SYS_RESOUT → CPLD** (MOD 12) | N/C | DSPA → U3.77, DSPB → U3.85 | yes | Not read by any image yet (reserved inputs). Available for a later "DSP alive" bit in the knock |
| 9 | **U7 / H1S1 MCU** (MOD 5) | STM32U575RIT6, firmware `MW/D24/FW/H1S1` | **STM32G0B1RET6**, different pin-out (`review/stage2b-u7-pinmap.md`), **no firmware exists** | **no** | A: H1S1 image chosen by U7 chip ID (U). `loadfw`: same STM32 USART bootloader protocol on USART1 PA9/PA10, but the G0B1 needs option bit **nBOOT_SEL = 0** programmed at first load or BOOT0 (S1, driven by MH1) is ignored on a programmed part; G0 flash pages are 2 KB vs the U575's 8 KB — check the app's erase step. **Until the G0B1 port exists the rev D card has no RST_C driver: U7 is the ONLY driver of RST_C** (converter + 595 chain reset, 30-odd analog-board loads) — no audio I/O on rev D without it (finding S173-3) |
| 10 | **Codec select !CS_C** (CS6 ruling) | driven by H1S1 PA15; CM4 reaches the AK4619 only through H1S1 (`Sys001Test001/002`, `codec4619.py`) | **CM4 CS6 = GPIO17 drives !CS_C directly**; H1S1 is off the net | **no** | A: codec path per rev: rev C via the H1S1 bus cells; rev D via the CM4's own SPI with CS6. `StartAK4619` (codec init) moves into the app on rev D. The H1S1 codec cells are dead on rev D |
| 11 | **!RST_D** (DSP reset) | U7 PA13 and CM4 GPIO16, both push-pull, no pull-up | **open-drain wired-OR**, R86 10K pull-up; also J7 pin 10 (JTAG TARGET_RESET) | partly | A/host tools: GPIO16 must be **open-drain** on rev D (drive low / release to input), never driven high. Releasing to input also works on rev C only if U7 holds RST_D high — keep push-pull on rev C |
| 12 | **DSP JTAG** (MOD D, J7) | none | 10-pin 1.27 mm ADI header, both DSPs chained | yes | Development only; nothing for the app |
| 13 | **PSU monitor** | PAD0-PAD11 on U7 analog pins (H1S1 never read them) | removed (stage 3d), J3/J4 87-98 N/C | yes | No feature lost; do not add one |
| 14 | **J6 (40-pin Pi header) and J5 (5-pin header)** | fitted (bring-up Pi mount) | removed | yes | Bench only; the CM4 is the only host |
| 15 | **MEMS stub** U3.137 | LOGIC_MEMS stub to J1/J2.26 (dead) | removed | yes | Nothing (the mic is on PIN_121 on both) |
| 16 | **M MCU_S4 pull-down** R85 (MOD 3 OPEN) | none | 10K to GND | yes | Nothing |
| 17 | **Clocks** (MOD A/B) | 49.152 MHz XO → CPLD ÷2 → 1K/330R divider (fitted on the proto) | same, in copper | yes | Nothing |
| 18 | **DSP boot** | SPI2 slave boot, BMODE 010 | same, through U12/U13 (switch closed while XSPI_EN is low) | yes | Nothing for `dsp4_boot.py` except the RDY polarity (item 5) |

## 2. DSP firmware: one image or one per revision — recommendation

**One image, run-time revision, with a safe common subset.** Reasons:

- D-arch "ONE DSP4 firmware + product config" stands, and the difference is
  small and pin-level: the link port (SPI2 vs SPI1), the LED pad, XSPI_EN and
  the RAM.
- **The safe common subset exists and is most of the image:** link on SPI2,
  XSPI_EN low (never touched), LED on PA_14 only, no RAM. On rev C that is today's
  behaviour minus the PA_12 LED; on rev D, with XSPI_EN low, the bus switch
  connects SPI2 to the CM4 exactly as on rev C. PA_14, PA_15, PB_00 and PB_04 are
  open pads on rev C (mx26 netlist: single-pin nets), so driving them there is
  harmless.
- What needs the revision is only: PA_12 (LED on rev C, CM4 MOSI on rev D) and the
  RAM/SPI1 switch-over (rev D only).

**How the image learns the revision:** the CM4 states it in the product config
(`dsp4_config.py`; the CM4 knows it from detector R/U), which is the first host
transaction and still travels over SPI2 on both cards. An early guard is
available too: the SPI_RDY pull flips between revisions (item 5), so PB_05 read
as an input at reset reads low on rev C and high on rev D; this needs a bench
proof before it is trusted. Until the config says rev C the image never drives
PA_12; until it says rev D (and the probe passes) it never raises XSPI_EN. A
mismatch between the strap and the config stays in the common subset.

Per-revision images would be simpler to write but double the package, put the
choice in the flasher (where a wrong choice on the LED pad is a bus fight), and
contradict D-arch. Not recommended.

## 3. What stays the same (the app does not need to care)

TDM slot map and lane indices (the CPLD absorbs the pin moves), the DSP address
map and every DSP cell, the 595 mic-gain chain (CM4 CS5 → !CS_M on both: proto
wire on rev C, copper on rev D), the CPLD design-ID knock protocol, the CM4 PCM
link, the boot protocol, the panel / MH1 bus wiring.
