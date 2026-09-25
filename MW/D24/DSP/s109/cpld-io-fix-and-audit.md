provenance: AI-drafted 2026-09-25 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S109 — the LOGIC CPLD's I/O, fixed and audited pin by pin

> **Three I/O faults fixed, built, flashed and read back off the part; all 144
> pins audited against the netlist; one of the three proved alive on the bench
> the same session.**
>
> `dsp4_logic.90e24de0dd4a` (`design_id 32'h4de0dd4a`, SHIPPING, `cfg_bits
> 16'h0010`) is on `MW-D24-2`, read back off the part after the flash. The
> MEMS lane went from `ffffffff` STATIC to **31 distinct words in 32 reads,
> −64.76 dBFS RMS** — two scans twenty minutes apart on the same DSP pair and
> the same symbol map, all three rxscan controls `[ok]` in both, one variable
> between them.
>
> And the thing that could not be proved from the desk before: the words
> arrive with the ADAU7002's 20-bit payload sitting **exactly** in the top 20
> bits and the CPLD's own weak pull-up filling the low 12 (`fffb7fff`,
> `fffc67ff`, `fff067ff`). A frame that was one bit out could not produce that
> boundary. The framing is right, in both of the bridge's slots, on two
> separately built DSP images.

## 0. What PW ruled mid-session, and what it settled

**PW, 2026-09-25: D32 is REMOVED from requirements. D24 only.** Recorded in
the dispatch block. It turns the dispatch's one open decision into a closed
one — there is no ruling owed on whether the one-bitstream-for-D24-and-D32
rule survives, because there is no D32. So `strap_d32` is not defaulted or
strapped or worked around; **it is gone**, along with the snake lanes and the
X-logic parking they justified. `cdc_i = o_dspb[2]`, unconditional.

## 1. The three fixes

### 1.1 MEMS — the CPLD read a dead stub and never clocked the bridge

S106 found it and could not finish it, because two questions were open: which
part `digital U13` actually is, and whether it can place its output in a TDM8
slot at all. **Both are answered, from the datasheet, and S106-2 is closed.**

| | |
|---|---|
| the part | **ADAU7002**, not ADAU7302. `mx26 src/hw/d24-hw-ics.csv:12` was right and `tdm-lines.csv` was wrong; the CSV is corrected here |
| how it was settled | the datasheet's 8-ball WLCSP ball-out matches the netlist ball for ball: `A1 PDM_DAT`=`MEMS_D`, `A2 PDM_CLK`=`MEMS_CLK`, `B1 SDATA`=`M_I2S`, `B2 BCLK`=`M_BCK`, `C1 GND`, `C2 LRCLK`=`M_FS`, `D1 IOVDD`=`+3V3`, `D2 CONFIG`=`MEMS_CONFIG` |
| datasheet | ADAU7002 Rev. A, `https://www.farnell.com/datasheets/2177408.pdf`, **HTTP 200 with plain `curl`** (analog.com itself is blocked from this box, as S106 recorded — farnell mirrors it) |
| does it slot? | **yes.** Table 6: `CONFIG` tied to IOVDD **through 47 kΩ** = "TDM Slot 5 to Slot 6 Used/Driven, 32-Bit Slots". `R42` ties `MEMS_CONFIG` to digital `+3V3`, and `tdm-lines.csv` already recorded the 47 kΩ value |
| clock ratio | it needs BCLK ≥ 64× LRCLK and lists 64/128/192/256/384/512×. **12.288 MHz / 48 kHz = 256×**, on the list, auto-detected. It makes its own PDM_CLK at 64× LRCLK = 3.072 MHz, inside its 256 kHz–6.144 MHz range. Nothing to configure |

So no re-framing is needed and `dsp4_pcm_reframe.v` is not touched. What IS
needed, and is the part S106 could not have guessed:

**THE FRAME SYNC HAS TO BE DELAYED BY ONE BCK PERIOD.** The ADAU7002 is the
only TDM device on this frame that is *not* I2S-justified. Its Figure 13 draws
both cases on one page: in TDM mode slot 1's MSB is launched on the **same
BCLK falling edge LRCLK moved on**, while the separate "I2S justified" trace
waits a bit. Every other device on this frame — three AK5558s and the AK4619
in TDM256 **I2S** mode (`01H = 0xAC`) — is the justified kind, and the DSP's
per-lane frame delay (`lane_config.c c1_rx_lanes_mfd`, 2 on the converter and
codec lanes) is set for them. Handed the raw `fs8`, U13 would place its slots
one bck period ahead of the codec's and every MEMS word would arrive shifted
by a bit.

One register fixes it — `mems_fs` is `fs8` delayed by exactly one bck8 period
— and it puts the ADAU7002's slot boundaries exactly where the AK4619's
already are, which is the one alignment on this board proven by measurement.
The MEMS lane therefore keeps the same MFD as the rest; **nothing changes on
the DSP side but the slot number.** The testbench gates it (§4).

**And the slot number was wrong by one.** `slot-map.csv` had
`A_I7,5,MEMS_TB` "ADAU7302 TDM8 slot 5 per 47K strap" — but the datasheet's
Table 6 counts slots from **1**, so the 47 kΩ strap gives 1-based slots 5 and
6 = **0-based slots 4 and 5**. Corrected to slot 4, the LEFT channel: the panel
mic is `lswitch U3`, an **IMP34DT05**, and the netlist has its `LR` pad tied to
`GND`. Its DS12725 Table 6 says L/R = GND means DOUT is "Data valid" while CLK
is low and "High impedance" while CLK is high — the channel the ADAU7002
latches on the rising edge and puts in the **first** of its two slots.

| | before | after |
|---|---|---|
| `i_dspa[7]` | `mems`, **PIN_137** (`LOGIC_MEMS`) — a stub: `J1.26/J2.26/J18.26` and no load | `mems_i2s`, **PIN_121** (`M_I2S` ← `U13.B1`) |
| `M_BCK` (119) | reserved input | **output**, `bck8` |
| `M_FS` (120) | reserved input | **output**, `fs8` delayed one bck8 period |
| PIN_137 | assigned input on a dead net | unassigned → global reservation |
| slot | `A_I7` 0-based slot **5** | 0-based slot **4** |

`PIN_121` also gets an explicit `WEAK_PULL_UP_RESISTOR`. The ADAU7002
tri-states SDATA outside the two slots it owns (Figures 15–18) — six of eight
slots, plus the low 12 bits of its own two, because it emits 20 bits into a
32-bit slot — and `M_I2S` has no pull resistor on the board. Without it the
pin floats for most of every frame. The datasheet's Figure 11 asks for a
pull-*down*; MAX V cannot do that (🔴 S109-3).

### 1.2 The codec DAC — `cdc_i` is no longer strapped

`rtl:792` was `assign cdc_i = strap_d32 ? 1'b0 : o_dspb[2];`. It is now
`assign cdc_i = o_dspb[2];`, `strap_d32` is not a port, and `PIN_70` is
unassigned.

**A NEW FACT, MEASURED THIS SESSION, THAT CHANGES THE SHAPE OF S108-3.** The
baseline scan was taken on the *shipping* bitstream, 20 minutes before the
flash, and `XIN_SNK_01` (lane 5) read **`0x00000000`**, not the `0xFFFFFFFF`
S106 and S108 both measured. `rtl:781` in that bitstream is
`i_dspa[5] = strap_d32 ? snake_in : 1'b0`, so:

> **`strap_d32` was LOW today and HIGH in the two previous sessions. The strap
> is not stuck — it is undefined, and it has changed state between sessions.**

Which means the codec DAC was *intermittently* connected, not permanently
muted, and a bench test of the speaker path could have passed or failed
depending on what MH1 had left `U8.11` doing. That is worse than S108
described and it is exactly what S108-3 warned might be true. Removing the
strap removes the whole class.

### 1.3 The codec aux outputs — one byte, verified against the datasheet

`12H` is `0 0 0 0 DAC2SEL[1:0] DAC1SEL[1:0]`, default `0x04`. Table 18 gives
`DAC2SEL` `01` = SDIN2 (the default) and `00` = SDIN1. SDIN2 is `U3.2`, N/C on
this board (`G3619`), and datasheet 9.3 says SDIN2 is ignored in TDM mode
anyway — so `AOUT2L/R` = `CODEC_OUT_3/4` = the aux outputs were fed from
nothing and would have stayed silent even after the strap fix. `0x00` puts
DAC2 on SDIN1, whose slots 2/3 in TDM256 `SLOT=1` are exactly where
`C2_CODEC_AUX_OUT` sends `CODEC_OUT_3/4` (`dsp.csv`: `slot_start=2`,
`slot_count=2`). DAC1 is unchanged. **S108-2 confirms; applied.**

Applied to `~/build-h1s1/Core/Inc/matrix.cs`, `ak4619[]` index 21,
`0x04 → 0x00`, with the reasoning in a comment beside it. That file is H1S1
firmware and is not in this repo, so **it is not in this commit and it needs a
flash to take effect** — see 🔴 S109-1.

**It could not be re-verified live this session and here is why, plainly.**
The codec read arm answers through `matrix-app`, which is inactive on this
bench today; `s108_codec4619.py --read-all` returned `NO REPLY` on all 21
registers. Starting `matrix-app` asserts `AN_EN` unconditionally in
`Boot.Init()`, and a dispatched session may not raise the analog rails (bench
note 19 / S49-15). So the verification available is the datasheet plus S108's
own round-trip on this part (`12H` `0x04 → 0x0A → 0x04`, each step confirmed
by readback), which already proved the write path. Nothing here rests on a
reading that was not taken.

## 2. The bench result

Both scans: `MW-D24-2`, the `s103` `DSP4_TEST_NODES=1` pair, `chip1.sym.json`
from the same directory (no `?` in the node column), 32 reps, `AN_EN` low and
never written, all three controls `[ok]`.

```
BEFORE  dsp4_logic.d02d83b3cc22  design_id 32'h83b3cc22  (read off the part)
XIN_MEMS   entry 46  off 736  lane 7   32 reads, 1 distinct   ffffffff   STATIC   -186.64 dBFS

AFTER   dsp4_logic.90e24de0dd4a  design_id 32'h4de0dd4a  (read off the part)
XIN_MEMS   entry 46  off 736  lane 7   32 reads, 31 distinct  fffb7fff fffc67ff fff067ff
                                       CARRYING   rms -64.76  peak -56.60 dBFS
```

`-186.64 dBFS` is `20·log10(1/2^31)` — the word `-1`, every bit set, which is
what an undriven CPLD input reads. It is gone.

**The word shape is the second, independent result.** Every word ends
`...FFF`: the low 12 bits are the CPLD's weak pull-up during the ADAU7002's
tri-state tail, exactly as §1.1 predicted. The top 20 bits are small
two's-complement values near zero (`0xFFFB7` = −73, `0xFFFC6` = −58,
`0xFFF06` = −250 of ±2^19) — a quiet mic in a quiet room. A frame one bit out
would smear that boundary across the word. It does not.

**Both of U13's slots were then read, on two images.** The `s103` arm predates
today and its lane-7 channel mask is `0x0020` = 0-based slot 5 — the
ADAU7002's **right** channel. A second pair was built from the regenerated
tree (`lane_config.c` lane 7 mask `0x0010`, `C1_XIN_MEMS.asm` "Read from
SPORT7 TDM slot 4"), staged to `/home/app/loopthd/s109` with the boot streams'
md5 confirmed on the bench (`chip1.ldr 7f226919a5d181410c3804d92678da19`),
booted the same way, and scanned:

```
slot 5 (right, s103 image)   32 reads, 31 distinct   rms -64.76  peak -56.60   fffb7fff fffc67ff fff067ff
slot 4 (left,  s109 image)   32 reads, 32 distinct   rms -71.51  peak -65.62   fff5dfff 00001fff fff727ff
```

**Both carry, both with the same clean 20-bit-plus-`FFF` word shape**, which
is a second, independent confirmation that the bit alignment is right: a frame
one bit out could not produce that boundary in *either* slot.

Which one is the microphone is not settled by these two numbers, and the
netlist says why not: the mic's `DOUT` goes through a series `R3` into the
LVDS driver `lswitch U1.5` and **there is no pull resistor to a rail anywhere
on that net** (`G2460` is `U3.DO` + `R3.1`, and that is all of it). So during
the half-period the mic tri-states, `U1`'s input floats and its differential
output is indeterminate — the other channel decodes something that moves,
rather than the constant a pulled net would give. The datasheet argument is
unchanged and the tree follows it (slot 4 = left = the L/R-tied-to-GND
channel), and the left slot being the quieter of the two is what a smeared
copy on the floating half would predict. **Settling it needs a sound at the
panel, which needs someone at the bench** — 🔴 S109-4.

**Every other lane is exact zero in both scans**, and that is the test state,
not a regression: `AN_EN` is low, `matrix-app` has not run since the Pi
rebooted at 11:32, so the AK5558s and the AK4619 have never been initialised
this session. The before/after pair is therefore a clean single-variable
comparison on the one lane whose devices are on the digital board and are not
AN_EN-gated.

## 3. The full pin audit — all 144 pins

`data/cpld-pin-audit.csv`: every pin of `U3`, joined from the FITTER's own pin
report (the authority the S34 trap note names) against `mx26
docs/d24-cpld-fanout.csv` and `d24-netlist-global-pins.csv`, with 33 Ω series
taps resolved to the device on the far side. The generator is
`data/`-adjacent in this report and reproducible from those two files alone.

### 3.1 The dispatch's four named suspects

**1. "All 32 mic lanes (`ad[0..2]`) read exact digital zero (S80–S85) — say
plainly whether that is still open."** **It is closed, and it was never a
lane fault.** It was the `_buf_` symbol trap: under `DSP4_BLOCK_KERNELS` a
chain-head node's `_buf_<nid>` is a scalar in a zero-initialised section that
nothing writes, so five sessions read a symbol nobody fills and diagnosed a
converter, a bitstream, a launch phase and a SPORT. S86 wrote `dsp4_rxscan.py`
to read the RX DMA region instead and the lanes came up; S106's scan has
`ad[0..2]` carrying 20+ distinct values at −113…−118 dBFS with the rails up.
The pins themselves audit clean: 139/138/134 → `analog U15.36 / U39.36 /
U60.36`, the three AK5558s, through `R53`/`R686`/`R1273`. **Nothing to fix and
nothing still open.** (Today's scan shows them at zero because `AN_EN` is low
and the analog board was never initialised — §2.)

**2. "Lanes 3 and 5 reading `0xFFFFFFFF` is EXPECTED — confirm, and stop the
scan tooling scoring them as faults."** **Confirmed, and done.** Lane 3 is
`ni[3]` on PIN_3, whose net reaches `opt1 SLOT.A10` and nothing else — option
slot 1 is empty and there is no AD3 converter on this board. Lane 5 was
`snake_in` on PIN_109 (`opt2 SLOT.A12`), and after this change it is a hard
zero inside the CPLD. `tools/pi/dsp4_rxscan.py` now carries a `NO_SOURCE`
table: those entries print `static, NO SOURCE — expected`, they are excluded
from the "n of m CARRYING" tally, and a lane in that table that *starts*
moving is called out rather than passed. The scan's last lines now read:

```
1 of 30 SCORED RX entries CARRYING SAMPLES
17 further entries have NO FITTED SOURCE and are not scored:
   IN_25 .. IN_32: A_I3 is the NET lane (ni[3], pin 3) and option slot 1 is empty …
   XIN_CODEC_03: AK4619 ADC2 Lch (IN3) is not connected on rev C and has no consumer
   XIN_SNK_01 .. XIN_SNK_08: D32 snake return. D32 is out of requirements …
```

`XIN_CODEC_03` was found by the audit and added for the same reason — it has
been scored as a dead lane and it is `slot-map.csv`'s own "not connected on
rev C; no consumer".

**3. "Every other pin in the fitter's `RESERVED_INPUT_WITH_WEAK_PULLUP` list
that the netlist says is a REAL net — S106 found 119/120/121 this way, there
may be more."** **There are none.** 47 pins were reserved in the shipping
build. Fourteen of them have an active device on the net, and every one is a
line this part must *receive*, not drive:

| pin | net | who else is on it | verdict |
|---|---|---|---|
| 58 | `BLINK` | `U5.36`, `U6.36` (both SHARCs), `U8.48` (M MCU) | input — correct |
| 60 | `SPI0` | `U7.21` (S MCU), both SHARCs' `SPI2_CLK` via `R73`/`R76` | input — correct |
| 61 | `SPI1` | `U7.23`, both SHARCs' `SPI2_MOSI`, `analog U34.14` (the 595 chain) | input — correct |
| 62 | `CS_L` | `U7.55` | input — correct |
| 66 | `LOGIC_BUSY` | `U7.59`, `U8.1`, `rswitch U1.59`, `lswitch U4.59`, pulled up by `R72` | input — correct |
| 67/68/69 | `M MCU_S7/S6/S5` | `U8.16/15/12` | input — correct |
| **70** | `M MCU_S4` | `U8.11` | **was `strap_d32`; now reserved (§1.2)** |
| 71/72 | `M MCU_P48/P47` | `U7`, `U8`, `U9`, both panel MCUs | UART pass-through, TODO — input for now, correct |
| 73 | `M MCU_P18` | `U8.29` | input — correct |
| 75/76 | `STRX1/STRX0` | `U7.54/53` | input — correct |

The other 33 reserved pins reach nothing at all, or reach only an empty option
slot or the `J33` D32-compat header. **119/120/121 were the whole of the
unfinished business, and they are now assigned.**

**4. "Output direction check on every driven pin against what else is on that
net (S36 tri-state rule; option slots)."** One fault, and it was worse than
S36 described:

- `no[0..3]` (pins 2/1/144/143) drive `opt1 SLOT.A8/A9/A6/A7`, which the
  digital board labels `NI2/NI3/NI0/NI1` — the option **card's inputs**.
  Direction correct.
- `ni[0..3]` (pins 6/5/4/3) read `opt1 SLOT.A13/A12/A11/A10` = `NO3..NO0`, the
  card's **outputs**. Direction correct.
- **`snake_out` (110) and `dac_main` (111) were OUTPUTS on `opt2 SLOT.A13`
  and `SLOT.A10`, which the board labels `NO7` and `NO4` — the option card's
  OUTPUTS.** Driving them was driving into a fitted card's output, not merely
  "a lane a card might want". And the strap that was meant to hold them
  high-Z read HIGH in two prior sessions, so on this bench they were *driven*
  the whole time. Both ports are removed; the pins now fall to the global
  reservation (input, tri-stated, weak pull-up), which is the state the
  explicit pull-ups used to buy, minus a strap that could undo it.
- `snake_in` (109) was an input on `NO6` — direction-correct, and now
  sourceless, so it goes with them.

### 3.2 What else the audit turned up

- **`da[1]` (131)** reaches `digital J18.48` and stops. No tap, no device.
  `assign da[1] = 1'b0` is harmless and pointless; left as it is, now
  documented.
- **`da[2]` (130)** goes through `R116` to **`digital J33.13` and nothing
  else.** `J33` is the D32-compat header. With D32 out of requirements this
  lane has no sink on any product that exists. Left driven to `1'b0`; a
  header with nothing in it cannot be fought over. Named here so the next
  reader does not re-derive it.
- **Pins 89, 95 and 125** (`LOGIC_PLL1_0`, `PLL2_0`, `PLL8_2`) are the only
  other pins with 33 Ω taps on them, and all three land on `J33` too
  (`J33.2`, `J33.7`, `J33.14`). Dead on a D24. Reserved inputs, correct.
- **`ad[3]` (133)** → `J18.46` + `J33.15`. No converter. `A_I3` is NET-only,
  as `tdm-lines.csv` says.
- **`conv_bck` (142) / `conv_fs` (141)** → `analog U97.2 / U98.2`
  (`SN74LVC1G17` buffers) through the FPC, plus four 33 Ω taps each to the
  option slots. U3 is the only driver. Correct, and unchanged.
- **`cdc_i` (124)** → `R115` → `analog U3.1` = the AK4619's **SDIN1**. This
  confirms S108's trace end to end and is the pin the whole DAC story hangs
  on.
- **`cdc_o` (123)** → `R19` → `analog U3.31` = SDOUT1.
- **`mhrx` (74)** carries its S41 exception intact: reserved as an input with
  the weak pull-up explicitly OFF. Verified in this build's fitter report.
- The global reservation is still `As input tri-stated with weak pull-up` in
  `dsp4_logic.fit.rpt` — the 2026-08-19 trap has not come back.

## 4. Build, gates and cost

```
artifact   dsp4_logic.90e24de0dd4a.{pof,svf,manifest}
design_id  32'h4de0dd4a        cfg_bits 16'h0010     SHIPPING: yes
slot_map   sha256:265b4e1b312ec227b7a4a07c1a5076d35607484a869d6235bf1278048e88338b
sim_gate   PASS (5 testbenches)        STA gate PASS
```

| | shipping `d02d83b3cc22` | this build | delta |
|---|---|---|---|
| logic elements | 882 / 1,270 (69 %) | **881 / 1,270 (69 %)** | **−1** |
| registers | 662 | **663** | +1 (the `mems_fs` delay flop) |
| pins | 69 / 114 | **67 / 114** | −2 (five removed, three added) |
| Fmax | 66.58 MHz | **65.78 MHz** | −0.80 MHz; 1.34× the 49.152 MHz sysclk |

The area cost of the whole change is **one logic element, downwards**: the
strap mux on three lanes paid for the frame-sync flop and change. The Fmax
move is inside the fitter-placement spread the shipping manifest already
documents (50.67 → 55.88 MHz on the 570Z for no design change), and the STA
gate — not a remembered percentage — is what passed.

**The baseline was reproduced before anything was changed.** A clean build of
the unmodified tree produced `bitstream/dsp4_logic.d02d83b3cc22.pof`
**byte-identical** to the committed one (the `.svf` differs only in the
converter's date comment, as that manifest records). So the toolchain on this
box is the one that made what is on the part.

**New simulation gate.** `tb_logic_top` now checks the MEMS clocks every
sysclk edge: `mems_bck` must *be* `bcki[0]`, and `mems_fs` must be `fs8`
delayed by exactly one bck8 period. The delay is checked in sysclk cycles, not
in simulation time — `SYS_HALF` (10.1725 ns) is not representable on the 1 ps
timescale and a `$realtime` comparison fails on rounding rather than on the
design. The strap and snake checks are gone with the ports; the codec check is
now unconditional.

## 5. A generated file had been hand-edited, and this session's regenerate
   would have deleted it silently

Regenerating `dsp.csv` for the MEMS slot removed `sink=SPKR` from
`C2_MON_OUT` and `sink=DNP` from `C2_CODEC_AUX_OUT`. Neither has ever been
emitted by `tools/dsp/gen_dsp_csv.py`: `git log -S` puts both in `19d948b9`
("S102: the speaker route was never missing, it was never named"), written
straight into the generated file. The next regenerate was always going to take
them out, and the session that ran it would have had no reason to notice.

Fixed in the generator, not in the artifact: `output_params()` takes a `sink`
argument and the two call sites pass it. `dsp.csv` now regenerates with those
fields intact, and the only line that differs from the committed file is the
MEMS slot.

## 6. Contract

`defs.lock` is **unmoved** at `defs-v2026.09.24.2` — the definitions did not
change and no `defs` tag is involved. What changed is this repo's own slot
map, which `gen_slot_map.py` calls a contract bump behaviourally:

```
slot map source_hash  c4a3ca82f956b9c5… -> 265b4e1b312ec227…
dsp.csv               C1_XIN_MEMS slot_start=5 -> 4      (one line)
lane_config.c         lane 7 channel mask 0x0020 -> 0x0010
C1_XIN_MEMS.asm       "Read from SPORT7 TDM slot 5" -> "slot 4"
```

`./regenerate-dsp-contract.sh` ran clean. **No address moved**: D32
5780/5780 and D24 3989/3989 mapped cells still carry an address, and the SPI
allocator lands on the same page/addr as before. Change class: **mapping**.

## 6a. The speaker check — prepared for PW, not run

No audio was played this session and `AN_EN` was never written. The dispatch
asks for the recipe rather than the run, and it is worth more now than when
S106 wrote it: until today `cdc_i` was decided by an undefined strap, so a
negative result would have meant nothing. On `90e24de0dd4a` the codec's SDIN1
carries `B_O2` unconditionally, so **this test now has a defined meaning
either way.**

It needs PW at the bench, because it raises the analog rails and makes sound.

```bash
# 0. PREREQUISITES PW OWNS: the analog rails (AN_EN / GPIO26) must be up, and
#    matrix-app must have run MainInit() at least once so H1S1 has written the
#    AK4619's init image and the 595 chain. A dispatched session may do
#    neither. Confirm the CPLD first -- it must be the fix, not the old one:
cd /home/app/loopthd/s109
python3 dsp4_logic_id.py --expect 4de0dd4a        # 32'h4de0dd4a, cfg_bits 0x0010

# 1. boot the test-node pair (twice; stage 7 lands on cycle 2)
pinctrl set 27 op dh                               # CS_M -- driven, not pulled (S109-5)
pinctrl set 7,9,10,11,22,23,25 a0 ; pinctrl set 8,12 ip
for i in 1 2; do
  pinctrl set 6,24 op dh ; python3 dsp4_boot.py --dir .
  pinctrl set 6,24 op dh ; python3 dsp4_config.py --product d24 --chip 1
  pinctrl set 6,24 op dh ; python3 dsp4_config.py --product d24 --chip 2
done
python3 dsp4_diag.py --chip 1 --rdy-gpio 8 | head -5     # BOOT_STAGE 7 / BOOT_CFG 1

# 2. the proven route (S102/S103): strip 20 -> main -> monitor -> codec DAC1
python3 s89_set.py . $(for s in $(seq -w 1 32); do [ "$s" = 020 ] || echo Chan${s}MainOn001=0; done)
python3 s89_set.py . Chan020MainOn001=1 Chan020Mute001=0 Chan020Level001=f1.0:4     Chan020Pan001=f0.5:4 Chan020CompOn001=0 Chan020GateOn001=0     Chan020TubeOn001=0 Chan020EqOn001=0 Main001Level001=f1.0:4 Main001Mute001=0     Mon001Level001=f1.0:4 Mon001Level002=f1.0:4

# 3. PW listens at the panel speaker. START AT -40 dBFS, not -20.
python3 dsp4_s49_osc.py --strip 20 --freq 1000 --level -40 --symdir .
python3 dsp4_s49_osc.py --off --symdir .
```

S103 measured that injection back at −23.01 dBFS RMS, 0.00016 % THD+N, so the
DSP half is proven and what is under test is
`analog U3.22 → C23 → SPKR → analog J59.12 = digital J42.12 → C82 → TS482
(digital U32) → SPKR0/SPKR1 → lswitch J1.6/7 → J2.1/2`. **Start at −40 dBFS**
— S106's recipe says −20, which was written when the lane was known to be
silent; it no longer is, and the TS482 drives a panel speaker.

**The thirty-second version, if a scope is to hand and PW would rather not
make a noise:** `analog U3.1` (`CDC_I`/SDIN1) now carries TDM data instead of
sitting flat at logic 0 while LRCK and BICK run. That single reading confirms
the strap fix on the analog side without the rails, without the tone, and
without the speaker.

## 6b. The two catalog rows are NOT moved here

`MW/D24/DSP/accept/item-status.csv` is untouched: moving a verdict is the
hub's call, as S108 recorded. What can be said is that both rows' text is now
wrong in a way worth fixing when someone does move them.

- **`MM1` FAIL** sends a technician to the panel ribbon. The lane was never
  wired up; it is wired up now and it carries. The row needs re-running, not
  re-reading, and the honest re-run is 🔴 S109-4's tap-the-panel test.
- **`SP1` NO DATA** was correct because its only instrument was `MM1`. That
  reason has gone away.

## 7. 🔴 Items for the hub

### 🔴 S109-1 — the aux-output fix needs an H1S1 flash, which this session cannot do

`~/build-h1s1/Core/Inc/matrix.cs` now has `ak4619[]` index 21 = `0x00`. That
directory is not a git repository and is not part of this spoke, so the change
is on disk and in no commit. Until H1S1 is rebuilt and flashed, `12H` on the
part stays `0x04` and `AOUT2L/R` stay dead. Nothing else in this session
depends on it.

### 🔴 S109-2 — `M MCU_S4` is a live, undefined line and PIN_70 is now free

The strap is out of the CPLD, but the finding underneath it stands and is
sharper than S108 could make it: **the net changed state between sessions**
(§1.2). It has no pull resistor, and its only two pins are `U3.70` and the M
MCU's `U8.11`. Nothing in this repo can see what MH1 does with it. Two things
worth a ruling: (a) does `S4` belong to the M MCU's S0–S31 signalling bus, in
which case it is *supposed* to move and the CPLD was reading a message; (b)
`PIN_70` is now an unassigned input with a weak pull-up, which is safe but is
also a CPLD pull-up sitting on an MCU line — if `S4` is signalling, someone
should say whether that pull-up is wanted. No pull-down is available on MAX V.

### 🔴 S109-3 — `M_I2S` should have a pull-down, and only an ECO can give it one

The ADAU7002 tri-states SDATA for roughly 78 % of every frame and its own
Figure 11 asks for a pull-down on that net. The board has none: `U3.121`,
`J18.59` and `U13.B1` are the whole net. This build puts the CPLD's weak
pull-**up** on the pin, which defines the level and costs the lane nothing
(the floating bits are the low 12 of a 32-bit word, 2^−19 of full scale, and
they are visible as the `...FFF` tail in §2). It is not what the vendor asks
for. A pull-down on `M_I2S` is a one-resistor ECO and belongs on the rev-D
list if there is one.

### 🔴 S109-4 — which of U13's two slots is the mic needs one sound at the panel

§2. Both slots carry. The datasheet argument says slot 4 (left) and the tree
is built that way, but the mic's PDM line has no pull resistor, so the half it
tri-states decodes to something that moves too and the two cannot be told
apart from the desk. **The test is thirty seconds with someone at the bench:**
boot `/home/app/loopthd/s109` (slot 4) and `/home/app/loopthd/s103` (slot 5) in
turn, run
`python3 dsp4_rxscan.py --symdir . --reps 32` while talking at or tapping the
left panel near the mic, and see which `XIN_MEMS` moves with the sound. No
rails, no speaker, no audio played — it reads a microphone. If it is slot 5,
the fix is one character in `slot-map.csv` (`A_I7,4,MEMS_TB` -> `A_I7,5`) plus
a regenerate; the CPLD does not change either way.

### 🟡 S109-5 — `pinctrl set 27 ip pu` is no longer enough after a Pi reboot

The standing recipe for `CS_M` is `pinctrl set 27 ip pu`, and today the pin
read `ip pu | hi` and the parameter link still would not phase — "MAGIC never
came back in either arrangement", with both SHARCs booting cleanly and
`FRAME_COUNT` running behind it. **`pinctrl set 27 op dh` fixed it first
try**, and the link answered `0xD5B40001` immediately. So something is now
sinking `CS_M` harder than the CM4's weak pull-up can hold, and the recipe
needs the pin *driven*, not pulled. Recorded here because it cost this session
four failed boots and it will cost the next one the same.

## 8. Unit as handed back

| | |
|---|---|
| CPLD | **FLASHED.** `dsp4_logic.90e24de0dd4a` (`design_id 32'h4de0dd4a`, `cfg_bits 16'h0010`, SHIPPING) is on the part, read back by `dsp4_logic_id.py --expect 4de0dd4a` after the flash. It replaces `d02d83b3cc22`, which was confirmed on the part by read-back at the start of the session before anything was written |
| flash gate | `AN_EN` read `26: op -- pd \| lo` by `logic_flash.sh`'s own interlock; FLASH-OK on attempt 1; IDCODE `0x020a30dd` before and after; rollback `d02d83b3cc22.svf` staged and md5-checked first |
| `AN_EN` (GPIO26) | **never written** — `op -- pd \| lo` at the start and at handback |
| `CS_M` (GPIO27) | **written**, and it had to be: `ip pd \| lo` after the Pi's 11:32 reboot, set to `op dh` (see 🔴 S109-5). Left `op -- pu \| hi` |
| DSP pair | **BOOTED.** The `s103` `DSP4_TEST_NODES=1` pair, double boot+config per the post-flash runbook rule, `BOOT_STAGE 7 running`, `BOOT_CFG 1`, both `CHIP_ID` verified |
| 595 chain | **not written** — no `--reset`, no `--reinit`, `MainInit()` did not run |
| codec registers | **not written.** The read arm answers through `matrix-app`, which is inactive; all 21 reads returned `NO REPLY` and nothing was sent |
| services | `d24-testui` active, `matrix-app` inactive — as found |
| staged | `/home/app/loopthd/s103/dsp4_rxscan.py` replaced with this session's version; `/home/app/s109_rx_before.json`, `s109_rx_after.json`, `s109_rx_slot4.json` added; **`/home/app/loopthd/s109/` added** — the slot-4 pair (`chip1.ldr` md5 `7f226919a5d181410c3804d92678da19`, `chip2.ldr` `6f11a1ddc6efd45ec30f536cef295292`, both verified on the bench after the copy), its symbol maps, `input_patch.json`, the boot/config/diag/scan tools, and `s89_set.py` + `dsp4_s49_osc.py` copied from `s103` so §6a's recipe runs as written. **`/home/app/loopthd/s103`'s image, symbol maps and other tools untouched** (its `chip1.ldr` md5 re-read after staging, unchanged) |
| `defs.lock` | unmoved at `defs-v2026.09.24.2` |

## 9. Artifacts

| file | what |
|---|---|
| `data/cpld-pin-audit.csv` | all 144 pins: RTL name, fitter direction, net, boards, active devices besides U3 (33 Ω taps resolved), connector pins |
| `data/rxscan-before-shipping-83b3cc22.txt` | the 47-entry scan on the shipping bitstream, 32 reps, controls `[ok]` |
| `data/rxscan-after-90e24de0dd4a.txt` | the same scan after the flash and the double boot+config |
| `data/rxscan-slot4-image.txt` | the same scan on the regenerated slot-4 pair (`/home/app/loopthd/s109`) |
| `data/fitter-pins-90e24de0dd4a.txt` | this build's fitter pin report — the authority on every pin's direction and reservation |
| `data/cpld_pin_audit.py` | the join that produced the audit CSV, from the fitter pin report + the two mx26 netlist files |

## 10. Follow-ups (S109-1, -2, -4, -5), 2026-09-25 afternoon

PW's ruling that morning was "continue with steps 1-4" on §7. S109-3 (the
`M_I2S` pull-down ECO) is the hub's, in the mods PDF. The session ran into a
**HUB HOLD** partway through — PW went to the bench for the §6a speaker tone
test — so everything needing the unit after that point is queued, and this
section says exactly which.

### S109-1 — CLOSED, and the readback the dispatch expected to be impossible was taken

`~/build-h1s1` is not a git repository, so the edit is now captured in this
repo first: `h1s1/matrix.cs` is the file as flashed and `h1s1/matrix.cs.patch`
is the S109 change alone — the twelve-line comment block plus `ak4619[]`
index 21 `0x04` → `0x00`, reconstructed against a pre-S109 copy rather than
against the last on-disk backup, which predates S81's read arm and would have
carried that in too.

**The build was reproduced before it was changed.** `Debug/` held S81's
artifacts (2026-09-20, `H1S1.bin` md5 `5b6041d8472ade8c5a2bb11a87e87b61`);
rebuilding the *pre-S109* source with `Debug/fw.sh` produced that file
**byte-identically**, and the bench's `fwbuild/H1S1-s81b.hex` md5
`cd1da041449bb8c50cdacc0bef54563f` is the same hex this box makes, so the
toolchain here is the one that made what was on the part.

**The disassembly verification is as strong as it gets: the change is ONE
BYTE in the whole image.**

| | pre-S109 | S109 |
|---|---|---|
| text / data / bss | 35760 / 661 / 1944 | **35760 / 661 / 1944** |
| `objdump -d` of the ELF | — | **byte-identical** (only the filename line differs) |
| `H1S1.bin` bytes differing | — | **1**, at file offset `0x8C39`, `0x04` → `0x00` |
| that offset | — | `.data` LMA `0x08008BB0` + `ak4619`@`0x74` + 21 = `0x8C39` exactly |
| pack | — | `H1S1-s109.shex`, 2279 records (unchanged), **one record differs**: `:108C30…04050A…` → `…00050A…` |

Rollback kept twice, named, md5 `5dc7acdea662f9153b09b816f9ae76b2`:
`/home/app/fwbuild/H1S1-pre-s109-2026-09-25.shex` and
`/home/app/firmware/H1S1.shex.bak-2026-09-25-pre-s109`.

**BOARD ACTION — H1S1 FLASHED on MW-D24-2.** `MH1` was wedged in its flash
dispatcher, as in S69-4, so `reset run` was not used: `SYSRESETREQ` by hand
over SWD ch3 (`pinctrl set 5 op dl` / `13 op dh`, `openocd … mww 0xE000ED0C
0x05FA0004`, pins back to `ip`), OpenOCD logging `target was in unknown state
when halt was requested`, then `./app cli loadfw H1S1` → **`OK: H1S1`**, first
try. `matrix-app` was never started. **`AN_EN` read `26: op -- pd | lo` before
the SWD step, after it, and after the flash — never written.**

**VERIFIED ON THE PART, WITH NO RAILS.** The dispatch expected the `12H`
readback to be impossible without `matrix-app` and asked for the one-line
check to be left for PW. It is not impossible and it has been taken:
`codec4619.py` drives MH1's bus **directly** through `termios`, and what S109
read as "NO REPLY on all 21 registers" was MH1 sitting in its flash dispatcher
— **`--run` (S_RUN) is the missing step**, and the tool's own help says so.
After it:

* `S_RUN` → `// H1S1 DSP`, `// H1S4 SW Left`, `// H1S3 SW Right` — **3 of 3
  MCUs announce**, so the flashed firmware is running and on the bus;
* **`12H -> 0x00   guard 0x43   ANSWERED`** — `DAC2SEL=0 DAC1SEL=0`, both DACs
  on SDIN1. The guard is the command code as documented, and the data byte is
  not the register number, so this is a live read and not a MOSI echo;
* `--read-all`: all 21 registers `ANSWERED`, byte for byte the init image
  **except** `12H`. `04H`/`05H` `0xBB`, `0EH..11H` `0x18`, `14H` `0x0A` — the
  decode no longer prints the S108-2 `SDIN2 <-- DEAD SOURCE IN TDM MODE` flag,
  because there is no longer a DAC pointed at SDIN2.

So `AOUT2L/R` = `CODEC_OUT_3/4` are now fed from SDIN1 slots 2/3, where
`C2_CODEC_AUX_OUT` sends them. **Nothing about the aux outputs is left
unverified on the digital side.** What is still unproved is the same thing
S108 left unproved for DAC1 — that the aux output *analog* stage works — and
that is PW's probe on `U3.24/25` (`AOUT2L/R`), not a register read.

**The reflash re-ran `MainInit()`, so the 595 chain was rewritten to
`micGainFull`** (24 × `0xFC` = gain 63, phantom off, unmuted) — the S80
correction, not "cleared". `AN_EN` was low throughout so nothing was powered,
but the chain was not left that way: the SAFE image was written and read back
**`VERIFIED 200/200 01×24 00`** (gain 0, phantom off, MUTED), and `CS_M` put
back to `op dh`. Anyone reflashing an MCU on this board must do the same.

### S109-2 — ANSWERED FROM THE CODE, and it is not a strap at all

**(a) `S4` belongs to the M MCU's S0–S31 bus, it is meant to move, and it is a
RESET line.** The MH1 source is not on this machine but the canonical copy is
in Dropbox (`_mx/MW/D24/FW/MH1/`, `main.c` 2026-08-19). The bus is **eight
slave slots × four lines**, and S4 opens slot 2:

| line | CPLD pin | role | evidence |
|---|---|---|---|
| S4 | 70 | **reset** | `main.c:962` `//S4_Pin = 1; // S2 reset = 1` |
| S5 | 69 | boot0 | `SB2()` holds it high across the S4 pulse, `main.c:396` |
| S6 | 68 | ready (input at U8) | GPIO init configures S6 `GPIO_MODE_INPUT` |
| S7 | 67 | send-data | `GPIO_MODE_OUTPUT_PP` with S4/S5 |

`main.h:79` `#define S4_Pin GPIO_PIN_0`, one of a uniform `S0_Pin`…`S31_Pin`
array; `main.c:1432` configures it `GPIO_MODE_OUTPUT_PP`, `GPIO_NOPULL` — a
**push-pull output**, never an input. The netlist agrees that the whole quad is
one block: `G2737..G2740` = `M MCU_S4..S7` = `U8.11/12/15/16` → `U3.70/69/68/67`,
four consecutive pins at each end, where slot 1's quad (`S0..S3`) goes to the
S MCU `U7` instead. And the M MCU's own inventory names the slot:
`pcbName[1]` = `"PCB1: MW D24 DSP4 LOGIC   MCU H"`.

**The message it carries is not data — it is reset assert/de-assert plus
bootloader select, addressed to a slave that cannot answer**, because the CPLD
implements none of that protocol. Levels, measured against the code:

* `ResetAllSlaves()` (`main.c:461`) drives **S4 LOW** — called at startup
  before the M MCU waits for the host, and on every `S_SCAN`;
* `StartAllSlaves()` (`main.c:964`), on the host's **`S_RUN`**, drives **S4
  HIGH**, and nothing revisits it afterwards;
* `SB2()` pulses it LOW→HIGH for 1 ms with S5 high, to put slot 2 into its
  bootloader, then waits for a UART ack the CPLD will never send.

**That closes S109/§1.2's "the strap CHANGED STATE between sessions" as a
mystery.** It was not a floating net being read twice. S106 and S108 measured
HIGH because `matrix-app` had issued `S_RUN`; S109 measured LOW because
`matrix-app` was inactive and the M MCU was parked with its slaves in reset.
**The old `strap_d32` was reading whether MH1 had been told to run** — and
that is a far worse basis for a codec mute than "undefined", because it is
*repeatable in the wrong direction*.

**(b) The pull-up is HARMLESS but WRONG, and it is fixed in the qsf without a
flash.** It cannot fight U8 — a push-pull CMOS driver wins in both directions
— and it costs about 130 µA while S4 is asserted. So it is not risky and it is
**not worth a flash on its own**; it rides the next CPLD build. But it is the
same objection `mhrx` was taken out of the global reservation for (S41): a
CPLD pull-up has no business on a line another part drives and this part does
not read, and if a future bitstream ever *does* read the quad it should read
U8 rather than a resistor. `PIN_70` now comes out by name, exactly as `mhrx`
does:

```
set_location_assignment PIN_70 -to m_mcu_s4
set_instance_assignment -name RESERVE_PIN "AS INPUT TRI-STATED" -to m_mcu_s4
set_instance_assignment -name WEAK_PULL_UP_RESISTOR OFF -to m_mcu_s4
```

**BUILT AND GATED, NOT FLASHED.** `dsp4_logic.99616cc44dc4`
(`design_id 32'h6cc44dc4`, `cfg_bits 16'h0010`, SHIPPING): sim gate PASS,
worst-case setup slack **+5.517**, **Fmax 67.44 MHz** (was 65.78), logic
elements **881/1270 unchanged**, registers 663, pins 67 → **68/114** (a
reserved-by-name pin counts as a pin, as `mhrx` does). The fitter confirms it
rather than the qsf: `m_mcu_s4 : 70 : input : 3.3-V LVTTL` with the weak
pull-up column **`Off`**, identical to `mhrx`; pins 67/68/69 still read
`RESERVED_INPUT_WITH_WEAK_PULLUP`, so the change is confined to PIN_70; and
"Reserve all unused pins = As input tri-stated with weak pull-up" is intact in
`fit.rpt`, so the 2026-08-19 trap's fix is untouched. **The part is still on
`90e24de0dd4a` and the shipping label has NOT moved** — `logic_flash.sh`'s
`ROLLBACK` default and its header are unchanged.

**🔴 S109-2b, found while answering it: S5 and S7 have the same defect and are
NOT fixed here.** They are push-pull outputs of U8 exactly like S4, so the same
argument applies; they were left alone because the finding asked about PIN_70
and a three-pin change is a wider un-benched delta than the finding covers.
**S6 must keep its pull-up** — it is an *input* at the M MCU end, so this end's
pull-up is the only thing defining that net. Fold S5/S7 in with any other qsf
work.

**Nothing here needs a probe of U3.70.** The dispatch offered that as the
fallback if the code did not settle it; the code settles it, and a probe would
only show the level at one instant of the M MCU's handshake.

### S109-4 — the test is now one command, written and desk-proven; the bench half is queued

`mems-slot-test.sh` (this directory). One command, no bench dialogue:

```
ssh app@192.168.1.219
cd /home/app && ./mems-slot-test.sh
```

It checks `dsp4_logic_id.py --expect 4de0dd4a` and stops with the DUPLEX-overlay
trap spelled out if the knock says "no reply"; reads and reports `AN_EN`
without ever writing it; drives `CS_M op dh`; releases the boot pins with the
**corrected** sequence (`7,9,10,11,22,23,25 a0` + `6,24 op dh` + `8,12 ip`,
never the `…24 a0` form that boots two chip-1s), re-driving `6,24 op dh` before
every tool call; runs the **double** boot+config per slot and checks
`BOOT_STAGE`; takes a **QUIET BASELINE first** and only then asks for a sound;
and prints the answer in three lines.

Two design points that matter more than the plumbing:

* **it is best-of-N repeated scans, not one scan.** A `--reps 32` rxscan is
  ~1–3 s, so a single scan would probably miss the tap; the script scans
  continuously across a 15 s window and takes the best rms/peak, against the
  best of the quiet window. That also makes the threshold safe: a tap is tens
  of dB, and 3 dB on a best-of-N is well outside the quiet spread.
* **it refuses rather than guesses.** No verdict if rxscan's own three controls
  fail, `NO DATA` if a window produced no `XIN_MEMS` row, `INCOMPLETE` unless
  both slots have both windows, and a named diagnosis for "both moved" and for
  "neither moved" instead of picking a winner.

**Desk-proven, six cases, on synthetic scans in rxscan's real JSON shape**
(`--reduce-only`): slot-4-moved, slot-5-moved, both-moved, neither-moved,
controls-failed, and a missing-window case — each printing the right verdict,
including the three refusals. `--dry-run` walks the whole flow and executes
nothing. `bash -n` clean. Node name `XIN_MEMS` checked against S109's own
`data/rxscan-slot4-image.txt`.

**🟡 QUEUED FOR AFTER THE HOLD (nothing else in this section is outstanding):**

1. `scp MW/D24/DSP/s109/mems-slot-test.sh app@192.168.1.219:/home/app/` and
   `chmod +x`;
2. run it once with nobody tapping, to prove the quiet-baseline half on the
   unit — the tap half is PW's and this session must not run it;
3. redeploy `MW/D24/DSP/s105/test-catalog.csv` to the unit's glass (below).

### S109-5 — every live CS_M recipe now DRIVES the pin

`pinctrl set 27 op dh`, with the reason in a comment at each site. Live sites,
all fixed:

| file | what it was |
|---|---|
| `tools/pi/d24_selftest.py` | **the one actually-executed defect** — `handback()` re-armed `ip pu` on every dispatched session's handback. Now `op dh`, plus the docstring bullet that describes it |
| `tools/pi/codec4619.py` | the "put CS_M back to `ip pu`" instruction after a chain write |
| `tools/pi/s89_signbit.py` | the remedial line it *prints* when it cannot read the part, and the comment above it |
| `MW/D24/DSP/s105/test-catalog.csv` | MC1 and MC3 remedial text — **this is the unit's glass**, so it needs a redeploy (queued above) |
| `MW/D24/HW/hardware-map.md` | the standing "Fix: GPIO27 as an input with a pull-UP" line, and the "Rev-D line" below it, which predicted this and is now overtaken by events |
| `docs/d24-bench-logic-flash-log.md` | the triage order's `op pu\|hi` expectation (which was already garbled) |

**The runbook line, as asked:** the pull no longer holds the pin against
whatever sinks it, so `ip pu` can read `hi` and the link still not phase — the
pin has to be **driven**. `ip pu|hi` → `op dh` creates no edge, so it does not
clock the 595 latch.

Deliberately **left alone**: `tasks.md`'s ~96 and `findings.md`'s ~49 hits are
all inside dated dispatch blocks and numbered findings — they record what was
true then. So are the per-session gate scripts under `s83/`–`s86/tools/`
(each session writes its own, none is referenced later, all superseded by
`d24_selftest.py` from S90). `MW/D32/DSP/SHARC/s83_run.sh` only *reads* the
pin with no asserted value, and `d24_selftest.py::t_mc3` likewise, so both stay
correct. `check_bench_pins.sh` and `bench_lock.sh` never touch GPIO27.

**mx26, read only as instructed.** `scripts/cm4-setup-pi.sh` has **no GPIO27
line at all** — zero matches for `27`/`CS_M`/`ip pu` in 945 lines. Its
`/boot/config.txt` baseline covers GPIO4 (`PI_SD`), GPIO26 (`AN_EN op,dl`),
GPIO2/3 (SWD), GPIO13 and a comment about CS1/CS2. So **CS_M has no boot-time
baseline on the CM4 at all** and comes up as whatever the pinmux default is,
which is exactly why a bare reboot can land it somewhere a weak pull-up cannot
hold. `cm4-starter.sh` and the other `scripts/*.sh` are clean too.

**🔴 S109-5a, for the hub — two items in mx26 this spoke must not edit.**
(i) `docs/spec-d24-test-skin.md` and `tools/d24/build-d24-test-skin.py` carry
the same `pinctrl set 27 ip pu` remedial wording the catalog was drafted from,
so **a fix confined to this repo's CSV will be undone the next time the
catalog is regenerated upstream**. (ii) The real fix for CS_M is a **boot-time
baseline** in `cm4-setup-pi.sh` (`gpio=27=op,dh`, or the equivalent in
`config.txt`), so the link is not dead on every fresh boot until someone runs
a command. Both are mx26's call.
