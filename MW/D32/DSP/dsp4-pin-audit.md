provenance: AI-drafted 2026-08-22 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# DSP4 rev C — SHARC pin audit against the data sheet

Every ADSP-21564 pin the firmware touches or depends on, checked against
the **ADSP-21560/21561/21564/21568 data sheet Rev. A, February 2026** and
against the rev-C schematic (`TransferOnly/D24 schematics/D24 DSP.pdf`,
DSPA page 5/10 = U6, DSPB page 4/10 = U5).

Commissioned 2026-08-22 after `spi2_init()` was found to have configured
SPI2 correctly and left it connected to no pads — the firmware had never
written a `PORT*_FER` or `PORT*_MUX` bit. The question this answers is
"what else was assumed and never checked".

## Method

Four axes per pin, because those are the four that have actually bitten:

| axis | source | the fault it catches |
|---|---|---|
| power domain | Table 13 (Designer Quick Reference), Table 17 | D10 — 3.3 V into a VDD_INT pin |
| mux function / input tap | Tables 10, 11 | the SPI2 pin routing, 2026-08-22 |
| reset state and termination | Table 13 | pins floating before firmware claims them |
| frequency limits | Table 14 | out-of-range clocks, headroom |

Board side read off the schematic sheets directly. **A pin drawn with a
terminal circle and a wire is connected; a bare stub with no circle is
not brought out at all.** That distinction is what makes the N/C findings
below verifiable rather than inferred.

## Verdict

**No second D10.** Only two signal pins on the whole part sit in the
VDD_INT domain — `SYS_CLKIN0` and `SYS_XTAL0` — and both are already
accounted for. Every other pin the board drives is VDD_EXT (3.3 V), which
is what the board supplies. The clock-input fault was a one-off, not an
instance of a pattern.

**The pin-mux omission was confined to SPI2.** The DAI/SPORT path needs
no FER or MUX at all — DAI pins are dedicated, not port-multiplexed — so
the audio path never had the bug the host link had.

Four new items, none blocking, listed below.

## 1. The pins the firmware drives or depends on

Mux function from Tables 10/11; "required" is what SPI2/GPIO needs,
"set" is what the firmware now writes and what was read back off the
running part on 2026-08-22.

| pin | net (via) | function | mux required | mux set | domain | verdict |
|---|---|---|---|---|---|---|
| PA_00 | SPI2_MISO (R50 22R) | SPI2 MISO | 0 | 0 | VDD_EXT | ✅ |
| PA_01 | SPI2_MOSI (R51 22R) | SPI2 MOSI | 0 | 0 | VDD_EXT | ✅ |
| PA_04 | SPI2_CLK (R52 22R) | SPI2 CLK | 0 | 0 | VDD_EXT | ✅ |
| PA_05 | SPI2_SS (R53 22R) | SPI2_SEL1, **SPI2_SS on the input tap** | 0 | 0 | VDD_EXT | ✅ |
| PA_12 | BLINK_LED → R37 1K → LD3 → GND | GPIO out | n/a (FER=0) | FER=0 | VDD_EXT | ✅ |
| PB_05 | SPI2_RDY (R38 22R); R34 10K to GND | SPI2_RDY | **1** | 1 | VDD_EXT | ✅ |
| SYS_CLKIN0 | DSP_CLK (R65, bodged to 1k/330R) | clock in | n/a | n/a | **VDD_INT** | ⚠ see D10 |

`PA_05` is worth its own line. In slave mode the SPI block takes its
select from `SPI_SS`, which Table 10 lists as the **input tap** on PA_05
rather than as a numbered mux function — enabling FER with mux 0 is
correct and does not turn the pin into a driven `SEL1` output fighting
the host's chip select. The board agrees: the Pi's CS reaches PA_05
through R53.

## 2. DAI pins — the pin-19/20 swap is real, and the firmware has it right

`sru_config.c`'s header comment claims a DAI0/DAI1 asymmetry on pins 19
and 20. The schematic confirms it exactly:

| | pin 09 | pin 10 | pin 19 | pin 20 |
|---|---|---|---|---|
| DAI0 (U6) | FS0 | BCK0 | **BCK1** | **FS1** |
| DAI1 (U6) | FS2 | BCK2 | **FS3** | **BCK3** |

Data pins are the plain alternating pattern on both: odd = input
(I0…I7), even = output (O0…O7), each through a 22R series resistor.
This matches `sru_config.c` write for write.

**No FER or MUX is needed for any of these.** DAI pins are dedicated
`DAI0_PINnn` / `DAI1_PINnn` and do not appear in the port multiplexing
tables at all; routing is the SRU's job and direction is `DAI*_PBEN*`,
which `sru_init()` sets. This is the reason the audio path was never
affected by the fault that disabled the host link.

## 3. Straps, and what the board does not bring out

Read off both sheets; DSPA and DSPB are identical apart from reference
designators.

| pin | signal | board | data sheet requirement | verdict |
|---|---|---|---|---|
| 105 | SYS_BMODE0 | **GND** | "cannot be left unconnected", no internal termination | ✅ |
| 106 | SYS_BMODE1 | **VDD_EXT** | "cannot be left unconnected", no internal termination | ✅ |
| 82 | SYS_BMODE2 | **GND** | internal pull-down, no note | ✅ (explicit anyway) |
| 104 | SYS_HWRST | net `RST` | "cannot be left unconnected" | ✅ |
| 6 | SYS_XTAL0 | not brought out | "leave unconnected if an oscillator provides SYS_CLKIN0" | ✅ |
| 107 | SYS_RESOUT | not brought out | no notes | ✅ (see item C) |
| 102 | SYS_FAULT | not brought out | **"external pull-up required to keep signal in deasserted state"** | ⚠ item B |
| 10 | SYS_CLKOUT | **not brought out** | no notes | ⚠ item C |
| 99–103 | JTG_TDO/TMS/TCK/TDI/TRST | not brought out | internal pull-ups on TCK/TDI/TMS, **internal pull-down on TRST** | ✅ item A |

`SYS_BMODE[2:0]` = `0b010` = **SPI2 slave/target boot**, which is exactly
what `dsp4_boot.py` and D14 assume. All three are explicitly strapped, so
the two that must not float do not.

## New findings

### A. Floating JTAG is safe — confirmed, and the suspicion can be dropped

`JTG_TRST` carries an **internal pull-down** that is present both during
and after reset (Table 13). With the pin unconnected the TAP is held in
reset, which is the safe state, and `JTG_TCK`/`TDI`/`TMS` have internal
pull-ups. Nothing about the missing JTAG connection can put the part into
an odd state. This closes a standing suspicion rather than opening one —
the cost of no JTAG is only that we have no emulator, which we already
knew and have worked around with the GPIO pulse instruments.

### B. `SYS_FAULT` should have an external pull-up and has none

Table 13 is explicit: *"External pull-up required to keep signal in
deasserted state."* On rev C pin 102 is not brought out at all. It is an
active-low `InOut`, so a floating pad is unlikely to do harm as long as
nothing drives it and the part never samples it — but this is the one
place in the audit where the board contradicts a stated data sheet
requirement. **Low severity, but it is a requirement, not a preference.**
Rev-D item: bring `SYS_FAULT` out with a pull-up to VDD_EXT, or record a
deliberate decision not to.

### C. `SYS_CLKOUT` is not brought out — D14's "free liveness probe" is not available on this board

D14's bring-up corollary recommends `SYS_CLKOUT` (pin 10) as a
zero-code liveness signal: with BMODE non-zero it outputs SYS_CLKIN as
soon as reset deasserts, so power, clock and reset state can be read at
one probe point with no firmware and no JTAG. **Pin 10 has no terminal on
either rev-C sheet.** The advice is sound and should stand, but on this
card it is a rev-D request, not a technique anyone can use today.
`SYS_RESOUT` (pin 107) is in the same position and would be the natural
companion.

Rev-D item: bring both to test points. Given how much of this campaign
was spent proving whether a part was executing at all, these two pads
would have paid for themselves many times over.

### D. Every port and DAI pin is high-Z from reset until firmware claims it

Table 13 gives every `PA_*`, `PB_*` and `DAI*_PIN*` pin *Internal
Termination* = "programmable pull-up/pull-down", *Reset Termination* =
**None**, *Reset Drive* = **None**, and footnote 1 adds that the
programmable pulls are **disabled by default**. Footnote 2 adds that even
when enabled they hold only the *internal* path — *"to pull up or pull
down the external pads to the expected logic levels, use external
resistors."*

Three consequences, none of them faults, all of them worth knowing:

- **PA_00/MISO floats from reset until `spi2_init()` runs.** Any host
  read in that window returns whatever the bus settles to. This is
  exactly what the all-zero readbacks were, and it is why they were
  indistinguishable from a dead part.
- **The DAI output pins O0–O7 float for the whole boot window** — about
  350 ms at 10 MHz for chip 1 — until `sru_init()` sets `PBEN`. Whatever
  sinks those lanes (DAC8s, the network path) sees a floating input for
  that time. Worth a thought when audio finally runs; it may want a
  mute-until-configured story, and it is cheap to check on a scope once
  there is something to look at.
- **`SPI2_RDY` is defined at reset only by R34/R22**, the 10K pulldown —
  which is the whole of the boot-versus-runtime polarity conflict already
  recorded in `dma_config.c`. The audit does not resolve that conflict,
  it just confirms the pulldown is the only thing holding the line.

## Frequency headroom against Table 14

Using the clock tree measured 2026-08-22 (CCLK 491.52, SYSCLK 245.76,
SCLK0 61.44, SCLK1 122.88 MHz):

| parameter | limit | this board | headroom |
|---|---|---|---|
| fCCLK | 400–1000 MHz | 491.52 | ✅ |
| fSYSCLK | 200–500 MHz, fCCLK = 2 × fSYSCLK | 245.76, ratio exactly 2 | ✅ |
| fSCLK0 | 30–125 MHz, **fSYSCLK = N × fSCLK0, N = 2…6** | 61.44, N = 4 | ✅ |
| fSCLK1 | ≤ fSYSCLK, ≤ 333.3 MHz | 122.88 | ✅ |
| fCKIN | 20–30 MHz | 24.576 | ✅ (post-bodge) |
| fSPICLKEXT (slave) | ≤ 50 MHz | 1–11 MHz in use | ✅ |
| **fSPTCLKEXT transmitting** | **≤ 31.25 MHz** and ≤ fSCLK0 | TDM16 BCK = 24.576 | ✅ 27 % headroom |
| fSPTCLKEXT receiving | ≤ 62.5 MHz and ≤ fSCLK0 | 24.576 | ✅ |

Two things fall out of that table.

**The N = 2…6 constraint on fSCLK0 is a real trap for anyone retuning the
CGU.** The reset defaults happen to give N = 4. A future divider change
that lands on N = 1 or N > 6 is out of spec even if every individual
frequency looks fine.

**The 31.25 MHz external-SPORT-transmit limit is a hard number behind
D6's platform split.** At 48 kHz, TDM16 BCK is 24.576 MHz and passes. At
96 kHz it would be 49.152 MHz, which exceeds the limit outright — so
"SHARC up to 32 ch at 48 kHz, FPGA above" is not just an engineering
preference, it is where the part's external SPORT clock runs out. Worth
carrying into D6 as supporting evidence.

## Supplies

All three rails confirmed against the operating conditions table and
against PW's measurements of 2026-08-21:

| rail | data sheet | board | measured |
|---|---|---|---|
| VDD_INT | 0.855 / 0.900 / 0.945 V | +0.9 V from the motherboard | in spec |
| VDD_EXT | 3.13 / 3.30 / 3.47 V | +3V3 from the motherboard | in spec |
| VDD_REF | 1.71 / 1.80 / 1.89 V | +1V8 from U2 (AMS1117-1.8) | in spec |

## What this audit did not cover

- **Anything outside the two DSP sheets.** The CPLD, converters and
  motherboard connectors were not examined; this is a part-level audit
  against one data sheet, not a board net review.
- **PCB layout, impedance and length matching.** The 11 MHz SPI boot
  ceiling observed on the bench is far below the 50 MHz the part allows,
  so whatever imposes it is a board or signal-integrity property, not a
  device limit. That remains unexplained and is not a data sheet
  question. (Table 14 also qualifies fSPICLKEXT with "≤ fCDU_CLKO0",
  which has not been evaluated on this board and might be relevant.)
- **PA_02/PA_03 and the unused port pins.** They carry terminals on the
  sheet but no wires, and nothing in the firmware touches them.

## Actions

| # | item | where |
|---|---|---|
| B | `SYS_FAULT` needs an external pull-up or a recorded decision | rev-D mod list |
| C | bring `SYS_CLKOUT` and `SYS_RESOUT` to test points | rev-D mod list |
| D | decide whether floating DAI outputs during boot need a mute story | when audio runs |
| — | carry the 31.25 MHz fSPTCLKEXT limit into D6 as supporting evidence | `dsp4-architecture-decisions.md` |
