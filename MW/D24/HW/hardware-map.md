# D24 DSP hardware map (from schematics)

Status: derived 2026-07-29 from `MW/D24/HW/schematics/`
Sources: `D24 DSP.pdf` (DSP4 card, "MW DSP4 rev C", 01/03/2026) and
`D24 Digital.pdf` (D24 Digital PCBA rev C, 08/04/2026).
Purpose: ground truth for `MW/D24/DSP/SHARC/dsp.csv` regeneration and node
codegen. Where this conflicts with `dsp.plan.md`, this file wins (schematic
is newer).
Canonical board material (schematic PDF + DipTrace `.pdsprj`, BOM, CADCAM
gerbers, renders) for all 9 D24 PCBAs now lives in the mx26-owned Dropbox
store `_Matrix/Products/D24/hw/<board> PCBA/` (2026-08-06 — see
`matrix-shared-store.md`). The PDFs in `MW/D24/HW/schematics/` are
byte-identical copies kept in-repo for derivation.
Hardware MOD LISTS still live in Dropbox `TransferOnly/PCB mods/`
(cross-repo convention, 2026-08-05 — see its README); `TransferOnly/D24
schematics/` is the older transfer copy, superseded by the `_Matrix` store.
This map and other derived/versioned docs stay in-repo.

## 1. DSP4 card overview

Shared MW card used by both D24 and D32 (labels on DSPB O2: "D24 CODEC |
D32 SNAKE"). Fitted parts:

| Ref | Part | Role |
|---|---|---|
| U6 (DSPA) | ADSP-21564 | Input DSP: 32-ch input strips + matrix mix → 128 mix buses |
| U5 (DSPB) | ADSP-21564 | Output DSP: consumes 128 mix buses → DAC/codec/network outs |
| U3 (LOGIC) | 5M1270ZT144C4N (Intel MAX V CPLD) | TDM routing/mux between DSPs, converters, network, Pi |
| U7 (S MCU) | STM32U575RIT6 | DSP/option/converter resets, CS + SPI_RDY monitoring, matrix comms (SRX/MRX) — full pin inventory in §3a (added 2026-08-05 for rev D / D8) |
| U8 (M MCU) | STM32G031C8T6 | Board manager: PSU monitor, ext-MCU S[0..31] lines, H1S2 harness |
| Y1 | CB3LV 49.152 MHz XO | Master audio clock into LOGIC (SYSCLK) |

Note: the ROOT sheet labels the DSP blocks "ADSP21560"; the detail sheets
(U5/U6) say ADSP-21564 — 21564 is correct (matches D32 toolchain).

## 2. Audio topology (ROOT sheet)

### DSPA (chip 1) — input engine

Inputs (per-DSP ports I0–I7, driven by LOGIC):

| Port | Signal | Content |
|---|---|---|
| I0 | ADC/NET 1-8 | TDM8, mic/line ADC or network return (LOGIC-muxed) |
| I1 | ADC/NET 9-16 | TDM8 |
| I2 | ADC/NET 17-24 | TDM8 |
| I3 | ADC/NET 25-32 | TDM8 |
| I4 | CODEC (prov.) | AK4916 codec return |
| I5 | SNAKE (prov.) | D32 snake (D32 build only) |
| I6 | PI (prov.) | Pi PCM/I2S playback via LOGIC |
| I7 | MEMS (prov.) | Talkback MEMS mic (ADAU7302 PDM bridge, TDM8 slot 5 or I2S) |

("prov." = schematic marks these with `?` — provisional assignments.)

Outputs: **8 × TDM16 mix buses = 128 mixes**:
O0=MIX_1_16, O1=MIX_17_32, O2=MIX_33_48, O3=MIX_49_64, O4=MIX_65_80,
O5=MIX_81_96, O6=MIX_97_112, O7=MIX_113_128.

### DSPB (chip 2) — output engine

Inputs I0–I7 = MIX_1_16 … MIX_113_128 (the 128 buses from DSPA).

Outputs:

| Port | Signal |
|---|---|
| O0 | DAC 1-8 |
| O1 | DAC 9-16 |
| O2 | D24 CODEC / D32 SNAKE |
| O3 | DAC MAIN |
| O4–O7 | NET 1-8 / 9-16 / 17-24 / 25-32 (muxed onto network by LOGIC) |

### DAI pin map (identical on both DSPs)

| DAI0 pin | Net | DAI1 pin | Net |
|---|---|---|---|
| 01 | I0 | 01 | I4 |
| 02 | O0 | 02 | O4 |
| 03 | I1 | 03 | I5 |
| 04 | O1 | 04 | O5 |
| 05 | I2 | 05 | I6 |
| 06 | O2 | 06 | O6 |
| 07 | I3 | 07 | I7 |
| 08 | O3 | 08 | O7 |
| 09 | FS0 | 09 | FS2 |
| 10 | BCK0 | 10 | BCK2 |
| 19 | BCK1 | 19 | FS3 |
| 20 | FS1 | 20 | BCK3 |

All DAI data/clock lines go through 22R series resistors. Four BCK/FS
clock-domain pairs per DSP, all generated/driven by LOGIC (DSP SPORTs are
clock slaves). LOGIC bus-role note on ROOT sheet:
`0 AUX1 IP (D32C only), 1 BUS/I0 (Mixer/Hub), 2 IP0 (ADC/Network),
3 IP1 (ADC/Network), 4 AUX2 (D32C only), 5 BUS/I1 (Mixer/Hub),
6 IP2 (ADC/Network), 7 IP3 (ADC/Network)`.

### Clock formats

LOGIC format-config straps: IC0=TDM16, IC1=TDM8, IC2=I2S; IL0=FS, IL1=WC.
At 48 kHz / 32-bit slots: TDM8 → 12.288 MHz BCLK, TDM16 → 24.576 MHz BCLK,
both divided from the 49.152 MHz XO.

### Review-note addendum: analog I/O → DSP4 digital nets

The analog side of the D24 hardware does not terminate on direct DSP4 analog pins.
The analog connector subassemblies feed the D24 Digital board, which presents
converter-side TDM streams to the DSP4 card. The DSP4 review markup should call
out these handoffs as digital nets inside the DSP4 topology:

| Analog/connector side | Physical path | DSP4 digital net / role |
|---|---|---|
| ADC inputs | D24 analog input path → ADC FPC J41 → AD0..3 TDM lanes | DSPA input ports I0–I3, carrying ADC/NET 1–32 as TDM8 streams |
| DAC outputs | DAC FPC J42 → DA0..3 TDM lanes | DSPB output ports O0/O1/O3, carrying DAC 1–8 / DAC 9–16 / DAC MAIN |
| Codec / phone path | D24 codec/phone interface on the digital/analog boards | DSP4 sees this as the codec return/input path on I4 and the codec output path on O2 (D24 CODEC / D32 SNAKE) |

Practical reading of the review markup: the analog I/O is resolved to DSP4 as
TDM/DAI traffic on the DSP card, not as a separate analog net inside the DSP4
schematic. This is the key point to preserve on any rev-D markup update.

#### Verified detail (2026-07-30, cross-checked against D24 Analog rev B + D24 Digital rev C)

Marked-up schematic: `schematics/D24 DSP rev C - review markup 2026-07-30.pdf`.
The table above holds at DSP-port level; the exact lane/source mapping is:

| DSP port | DSP4 net | Resolves to |
|---|---|---|
| DSPA I0 | AD0 | Mic/line ch 1-4 & 13-16 — ADC8 #1 (Analog bd, TDM8 via FPC J41/J58) |
| DSPA I1 | AD1 | Mic/line ch 5-8 & 17-20 — ADC8 #2 |
| DSPA I2 | AD2 | Mic/line ch 9-12 & 21-24 — ADC8 #3 |
| DSPA I3 | AD3 | **No D24 ADC** — driven only via D32_COMPAT J33 / LOGIC NET mux |
| DSPA I4 | PLL8_0 = CDC_O | AK4916 CODEC4 ADC (talkback XLR + aux in), Analog bd |
| DSPA I7 | MEMS (PLL7 grp: M_BCK/M_FS/M_I2S) | Surface MEMS mics → LVDS J12/J13 → ADAU7302 (Digital bd) |
| DSPB O0 | DA0 | DAC8 OUT_1-8 → line outs 1-8 (FPC J42/J59) |
| DSPB O1 | **DA3, not DA1** | DAC8 OUT_9-16 → line outs 9-16; DA1 dead-ends at Digital J18 (spare) |
| DSPB O2 | PLL8_1 = CDC_I | AK4916 codec DAC: talkback SPKR (TS482 on Digital → panels) + aux out |
| DSPB O3 | — | "DAC MAIN": **no D24 sink by design** (resolved 2026-07-31: D24 main outs are line outs on the Analog PCBA — the OUT_1-8/OUT_9-16 DAC8s via DA0/DA3; the Analog ROOT carries no third audio DAC and J58/J59 no spare TDM lane). Lane reserved for D32/future |

Digital-only paths (no analog resolution): I5 snake, I6 Pi PCM, O4-O7 NET
(option cards), DA2 (D32_COMPAT J33 only). Phones PCBA is analog-only
(differential feeds from the DAC8 outputs; no DSP4 digital link).

Clocking: converters run on C1 (TDM8 BCK 12.288 MHz) + L0 (FS 48 kHz),
LOGIC-generated, 33R series on Digital (R111/R112), re-buffered by
LVC1G17 (U97/U98) on Analog. Open check: Digital labels PLL3-6 clock
groups toward the FPCs but Analog rev B J58/J59 name only C1/L0 —
confirm FPC pin alignment (PLL3-6 possibly unused on D24).

Impact on `dsp.csv` regen (D2 slot map): D24 input strips 25-32 have no
analog source (NET only); the LOGIC slot map must route DSPB O1 → DA3.

## 3. Control plane

- **SPI (params + boot):** Pi (CM4 on D24 Digital board) is SPI master.
  `!SPI0/1/2` (SCK/MOSI/MISO) split through 33R into two branches:
  `CK1_[0..2]` → DSPA SPI[0..2], `CK2_[0..2]` → DSPB SPI[0..2].
  Chip selects from the Pi header: CS1 → DSPA SPI_CS, CS2 → DSPB SPI_CS.
  CS3/CS4 are wired to DSPA/DSPB SPI_RDY (flow control, monitored at
  S MCU: "DSP 1/2 chip SPI_RDY"). Pi header carries SPI_CS[1..8] — up to 8
  DSPs addressable in bigger builds (S MCU also has CS5/CS7/CS8 pins).
- **No link port / no inter-DSP control path** — each DSP is parameterised
  directly over its own SPI CS.
- **Resets — `!RST_D` net, traced end to end 2026-08-21 (ROOT sheet p1/10).**
  The DSPA and DSPB hierarchy blocks each take `!RST_D` into a port named
  `RST`, and on the DSPA sheet (p5) that sheet-local `RST` lands on **U6
  pin 104, SYS_HWRST** — likewise DSPB/U5. One net, six places:
  **CM4 GPIO16 · U7 PA13 (p47) · J6 pin 36 · DIL100 P13 · U5 p104 ·
  U6 p104.** No series resistor anywhere on it, and `SYS_RESOUT` (p107) is
  N/C on both parts. Two masters, no arbitration.
  - Careful with the sub-sheet names: `RST` on the M MCU sheet (p6) is a
    *different* net — U8's own NRST, shared with the J5 SWD header, C204
    and DIL100 P84. It has nothing to do with the DSPs.
  - **U7 PA13 does not drive it.** In the current H1S1 firmware
    (`~/build-h1s1`) PA13 is not configured at all: absent from the `.ioc`
    pin list, `RST_D_Pin`/`RST_D_GPIO_Port` undefined in `main.h`, and the
    only two references in `main.c` commented out. It sits in the STM32U5
    reset default — SWDIO alternate function with the ~40 kOhm internal
    pull-up. That pull-up is what `dsp4_netprobe.py` reads as "held high by
    something stronger than the Pi pull" (the Pi's internal pull is
    ~50 kOhm); it cannot fight a push-pull output, and the Pi's GPIO16
    drives the net to a clean 0 at its own pad. So the schematic
    annotation "!RST_D (Reset DSPs)" on U7 p47 describes an intent the
    firmware has never implemented.
  - S MCU also drives IRST_O (option cards) and IRST_C (converters).
- **DSP_CLK:** distributed to both DSPs' SYS_CLKIN0 (pin 5) from the
  LOGIC sheet — CPLD U3 pin 140 → **R65 22R → DSPA U6 p5** and
  **R33 22R → DSPB U5 p5**; SYS_XTAL0 (p6) unconnected on both, correct
  for an oscillator source. **Two rev-C faults on this net (see D10):**
  the CPLD passed the raw 49.152 MHz XO to a pin specified at
  fCKIN = 20-30 MHz (fixed in RTL 2026-08-21, `dsp_clk` = sysclk/2 =
  24.576 MHz), and `SYS_CLKIN0` is a **VDD_INT-domain** pin (abs max
  = VDD_INT ≈ 0.9 V, VIHCLKIN 0.68 V…VDD_INT, VILCLKIN ≤ 0.12 V) being
  driven at 3.3 V. **Both corrected on the bench card 2026-08-21:** the ÷2
  bitstream, and a divider fitted at the 22 R pads (1 k in place of
  R65/R33 + 330 R from each DSP-side pad to GND), scope-verified at
  0.70–0.82 V / 24.576 MHz. The boot retest on that verified clock is
  still flat on both chips, so the clock was not the sole cause — see
  `TransferOnly/PCB mods/dsp4-revC-liveness-checklist.md`.
- **DSP decoupling: none in the schematic.** The DSPA (p5) and DSPB (p4)
  sheets each instantiate a `CAPS` sub-sheet with VDD_INT/VDD_EXT/VDD_REF
  ports, and both of those sheets (PDF pages 9/10) are blank — no
  components, and no C-designators anywhere on either DSP sheet, while
  every other device on the card is decoupled (CPLD C8-C21, U2 C3/C4/C6/C7,
  Y1 C2/C5, M MCU C202-C205). Unverified against the layout/BOM; if it is
  real it is a rev-C fault and a candidate root cause (rev-D mod 14).
- **DSP supplies:** VDD_INT ← **+0.9 V** and VDD_EXT ← **+3V3**, both from
  the motherboard over the J1/J2 DIL100 stack (J1 P1/P3/P5 = +0.9 V,
  P7/P9/P11 = +3V3); VDD_REF (pins 7/79, the PLL and OTP supply) ←
  **+1V8**, generated on-card by U2 (AMS1117-1.8) off +3V3, which also
  feeds the CPLD core. None of the three has ever been measured.
- **DSP JTAG: not connected at all.** `JTG_TDI/TMS/TCK/TDO/TRST`
  (pins 99-103) are terminals inside the DSPA/DSPB sheets and are not
  ports on those hierarchy blocks — they reach neither each other, nor
  the CPLD's TAP chain, nor any header. `SYS_RESOUT` (p107) and
  `SYS_FAULT` (p102) are likewise N/C. `SYS_HWRST` is p104, net `RST`.

## 3a. S MCU (U7) pin inventory — rev D / D8 supervisor scoping

Read 2026-08-05 from the S MCU sheet (p3/10, 300 DPI). U7's scope is
much larger than the §1 one-liner; grouped by role:

- **Matrix protocol endpoint** ("matrix comms"): strobed handshake
  S0 = `Matrix iRSTn`, S1 = `iBOOTp`, S2 = `oDATA_IS_READYp`,
  S3 = `iSEND_DATAp`, BUSY = `bBUSYn`; serial lines SRX
  (`Matrix S MCU RX`) and MRX (`Matrix M MCU RX`). S/BUSY/SRX/MRX
  nets are SHARED with U8 (M MCU) and enter LOGIC (U3) — this is
  what the CPLD `TODO(uart-passthrough)` routing matrix carries; the
  harness (J3/J4 "EXT MCUs" section on the M MCU sheet) takes them
  off-card to the matrix system. U9 (74LVC1G157, M MCU sheet) muxes
  the SRX source.
- **Option-card UART hub**: TRX0/TRX1 = TX2/RX-pair option card 1
  (USB/DAW); TRX2/TRX3 = TX4/RX4 option card 3 (DANTE);
  TRX4/TRX5 = TX6/RX6 option card 2 (USB SSD recording);
  STRX0/STRX1 = TX5/RX5 (S MCU's own pair).
- **Housekeeping SPI master**: !SPI0/1/2 with !CS_L (LOGIC chip
  select — the "discovered S-MCU SPI provision" for runtime net_sel),
  !CS_C (CONVERTER chip select), !CS_M (MIC gain chip select).
- **PSU ADC monitoring**: PAD0-11 — per-8-channel-bank analog PSU
  reads (IP 25-32 ×2 on PAD6/7; OP 1-8/9-16/17-24/25-32 on
  PAD8-11; PAD0-5 on the bottom edge).
- **Resets/supervision**: !RST_D (DSPs), !RST_O (option cards),
  !RST_C (converters); LEN (LOGIC JTAG enable); OEN1-3 (option card
  signal-input/JTAG enables); CS1-8 DSP chip-select provision
  (8-DSP scaling — only CS1/CS2 live on DSP4; CS3/CS4 wired as
  DSP1/2 SPI_RDY), BLINK LED.

Rev-D disposition (per D8): every role above is G0-class in compute;
the sizing driver is SERIAL COUNT (matrix + 3 option cards + own
pair ≈ 5-6 U(S)ARTs) and pin count (~45 signals). STM32G0B1RET6
(LQFP-64, 512K, 6 USART + 2 LPUART, ~$3.5-4) covers the full role
set as a rev-D relayout; merging into U8 is NOT recommended (U8
owns the H1S2 harness + ext-MCU S-lines; combined pin demand
exceeds one LQFP-64, and the matrix nets are deliberately
multi-drop across both MCUs). Near-term zero-effort option stays
the U535RET6 drop-in. The matrix endpoint and option-card control
plane STAY on the supervisor — they are exactly the always-on,
Pi-independent functions D8 keeps off the CM4.

## 4. D24 Digital board (host) — audio-relevant items

- **Pi CM4 carrier** (page 2): PCM[0..3] (PCM_CLK/DOUT/DIN/FS on GPIO18-21)
  → DSP card LOGIC (DSPA I6 path). SPI0/1/2 + CS[1..8] to DSP card.
- **ADC/DAC boards** via FPC J41 (ADC) / J42 (DAC): AD0..3 / DA0..3 TDM
  lines, PLL3-6 clock groups, converter SPI (SPI0 + CS_C converter CS,
  CS_M mic-gain CS, RST_C).
- **AK4916 codec ("CODEC4")** — on the D24 **Analog** PCBA (AUX_IO block:
  talkback XLR, aux in, SPKR out), NOT on the DSP card (corrected
  2026-07-30). Reached via PLL8-group nets CDC_O (→ J41 FPC) / CDC_I
  (→ J42 FPC).
- **MEMS talkback mic** (page 6): ADAU7302 PDM→TDM bridge (U13), config
  47K = TDM8 slot 5 / 0R = I2S; LVDS (SN65LVDS) drive to remote mic pods;
  TS482 speaker amp for talkback monitor (SPKR0/1).
- **Option cards 1-3** (J1/J2/J3, PCIR254-30-P38): carry NI0-15/NO0-11
  network TDM in/out, FS_1..4/BCK_1..4, UART TX/RX, MIDI in/out, SWD —
  this is where Dante/USB/network I/O plugs in.
- **D32_COMPAT / D32 Check** (J33): PLL1/PLL2/PLL8 groups + DA2/AD3 for
  D32 interop testing.
- **Switch panels** J12/J13 (SW LEFT/RIGHT): surface controls, talkback
  switch/LEDs, no audio to DSP.

## 5. Deltas vs existing `MW/D24/DSP/SHARC/dsp.plan.md` / `dsp.csv`

1. **Inter-chip fabric**: plan says "1× SPORT TDM32, 32 ch chip1→chip2".
   Hardware has **8× TDM16 = 128 mix buses** DSPA→DSPB. Mix summing
   therefore lives on **chip 1** (it emits per-bus mixes); chip 2 is bus
   processing + output routing. `dsp.csv` chip-link and chip-2 summing
   topology need regenerating to match.
2. **Control**: plan's "Link Port LP0" inter-chip control path does not
   exist in hardware. All params arrive per-chip over Pi-mastered SPI.
3. **chip 1 input side**: `dsp.csv` sport_id 0-3 / TDM8 × 8 slots matches
   the ADC/NET 1-32 wiring. Sources I4-I7 (codec return, snake, Pi, MEMS)
   are absent from `dsp.csv` and need INPUT nodes when adopted.
4. **chip 2 outputs**: DAC 1-16 + DAC MAIN + CODEC + NET 1-32 — richer
   than the plan's "DAC TDM 32 ch out"; output router nodes should target
   the real port map above.
5. Part number confirmed ADSP-21564 (ROOT "21560" labels are stale).

Change path per repo rules: edit `tools/dsp/gen_dsp_csv.py` (D24 config) →
regen `dsp.csv` → `tools/dsp/dsp_codegen.py` → node ASM. Do not hand-edit
generated files.
