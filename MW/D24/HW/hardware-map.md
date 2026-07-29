# D24 DSP hardware map (from schematics)

Status: derived 2026-07-29 from `MW/D24/HW/schematics/`
Sources: `D24 DSP.pdf` (DSP4 card, "MW DSP4 rev C", 01/03/2026) and
`D24 Digital.pdf` (D24 Digital PCBA rev C, 08/04/2026).
Purpose: ground truth for `MW/D24/DSP/SHARC/dsp.csv` regeneration and node
codegen. Where this conflicts with `dsp.plan.md`, this file wins (schematic
is newer).

## 1. DSP4 card overview

Shared MW card used by both D24 and D32 (labels on DSPB O2: "D24 CODEC |
D32 SNAKE"). Fitted parts:

| Ref | Part | Role |
|---|---|---|
| U6 (DSPA) | ADSP-21564 | Input DSP: 32-ch input strips + matrix mix → 128 mix buses |
| U5 (DSPB) | ADSP-21564 | Output DSP: consumes 128 mix buses → DAC/codec/network outs |
| U3 (LOGIC) | 5M1270ZT144C4N (Intel MAX V CPLD) | TDM routing/mux between DSPs, converters, network, Pi |
| U7 (S MCU) | STM32U575RIT6 | DSP/option/converter resets, CS + SPI_RDY monitoring, matrix comms (SRX/MRX) |
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
- **Resets:** S MCU drives IRST_D (both DSPs), IRST_O (option cards),
  IRST_C (converters).
- **DSP_CLK:** distributed to both DSPs' SYS_CLKIN0 from LOGIC sheet.

## 4. D24 Digital board (host) — audio-relevant items

- **Pi CM4 carrier** (page 2): PCM[0..3] (PCM_CLK/DOUT/DIN/FS on GPIO18-21)
  → DSP card LOGIC (DSPA I6 path). SPI0/1/2 + CS[1..8] to DSP card.
- **ADC/DAC boards** via FPC J41 (ADC) / J42 (DAC): AD0..3 / DA0..3 TDM
  lines, PLL3-6 clock groups, converter SPI (SPI0 + CS_C converter CS,
  CS_M mic-gain CS, RST_C).
- **AK4916 codec** on DSP card PLL8 group (CDC_O/CDC_I).
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
