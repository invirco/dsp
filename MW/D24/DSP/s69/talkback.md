provenance: AI-drafted 2026-09-19 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S69 — the talkback mic input: the codec gain lever, and where the talkback actually lands

Unit MW-D24-2 (rev C, 192.168.1.219), 2026-09-19. Dispatch: run the standard test set
(mx26 `docs/spec-audio-test-set.md`) on the talkback path with the AK4619's gain driven
through H1S1, per PW's ruling of the same morning — *"use h1s1 to get the test spec, and
we'll add a dedicated CS6 wire later"*.

**T1–T8 WERE NOT RUN.** The loop cable (AUX 1 out J45 → talkback XLR J1) was never fitted
and AN_EN stayed low; PW elected to dispatch the bench run separately. What this session
did instead is everything that does not need a hand at the bench — and that turned out to
include the gain lever itself, proved quantitatively without any analog stimulus, plus two
findings that change what the bench run should measure.

## The headline

**The talkback mic does not arrive on the lane the graph calls the talkback.** Measured
twice, two independent ways: the AK4619's ADC2 Rch — the channel the netlist walk puts the
talkback XLR on — is TDM **slot 3**, which the graph names `C1_XIN_CODEC_04`, *"Codec ADC 4
(Aux In R)"*, and routes to the codec-aux-in path into the main mix. `C1_XIN_CODEC_01`,
*"Codec ADC 1 (TB XLR)"*, is slot 0, and slot 0 is ADC1 **Lch**. See S69-1.

## What was done

| | |
|---|---|
| H1S1 | `CodecPoll()` added; built, verified in the disassembly, flashed, all three MCUs verify |
| DSP | TEST_MEAS tap added on the converter-return lanes (MeasChan 51–54); pair built, staged, booted |
| Tools | `tools/pi/codec4619.py` (the lever), `MW/D24/DSP/s69/tools/s69lib.py` (the rig) |
| Gate 0 | run, rails off — the loop is open, as expected with no cable |
| Gate 1 | **done** |
| Gate 2 | **done**, by a route that needs no cable |
| Gates 3/4 | **not run** — need AN_EN high and the loop cable |

## Gate 1 — the H1S1 firmware

`~/build-h1s1/Core/Inc/matrix.cs`, three hunks, backup beside it as
`matrix.cs.bak-2026-09-19-pre-s69`. The hub applies the same three to the canonical Dropbox
copy `_mx/MW/D24/FW/H1S1/Core/Inc/matrix.cs`; both copies must end identical.

| hunk | at | change |
|---|---|---|
| 1 | line 73–76 (`@@ -73,6 +73,7 @@`) | `void CodecPoll(void);` added to the forward declarations, between `StartAK4619` and `TestMicPres` |
| 2 | before `void MainInit()` (`@@ -112,6 +113,52 @@`) | the `CodecPoll()` body + its comment block, 46 lines |
| 3 | in `MainLoop()` (`@@ -156,6 +203,7 @@`) | `CodecPoll();` inserted between `Poll();` and `TimeSplice();` |

The body:

```c
void CodecPoll(void)
{
    if (matrix[pSys001Test002][RXF])
    {
        unsigned char reg = matrix[pSys001Test001][RXD];
        unsigned char val = matrix[pSys001Test002][RXD];
        if (reg == 0xFF) { StartAK4619(); }
        else
        {
            unsigned char w[4] = { 0xC3, 0x00, reg, val };
            SpiTx(GPIOA, CS_C_Pin, 4, w);
        }
        matrix[pSys001Test002][RXF] = 0;
    }
}
```

Called from `MainLoop`, **not** from `Eol` — `Eol` runs in the UART interrupt and `SpiTx`
blocks for up to a second; a codec write must not sit inside the bus receive path.

**The write form is confirmed against the datasheet** (9.12 Table 27, 9.13): the command
code's MSB is the R/W flag and the low seven bits are the access area, so `0xC3` is write
and `0x43` read; the frame is command + 16-bit address + N data bytes, the address
auto-incrementing. `{0xC3, 0x00, reg, val}` is therefore the single-register write, and
`StartAK4619()`'s 24-byte block is the same command with N = 21. Proved on the part below.

**Verified in the disassembly, not from the source edit** (the 2026-08-21 rule):

| | before | after |
|---|---|---|
| `SpiTx` call sites | 3 | **4** (the new one at `0x8000a08`, inside `CodecPoll`) |
| `DspTx` callers | 0 | **0** |
| `bl` in `TimeSplice` | none | **none** |
| functions added | — | `CodecPoll` only |
| functions whose body changed | — | `MainLoop` only (the added `bl CodecPoll`) |
| text / data / bss | 33504 / 657 / 1940 | 33600 / 657 / 1940 |

The operand decode confirms the addressing rather than assuming it: the matrix base is
`0x200002b0`, and `CodecPoll` reads offsets 19, 14 and 18 — `matrix[4][3]`, `matrix[3][2]`
and `matrix[4][2]`, i.e. `pSys001Test002[RXF]`, `pSys001Test001[RXD]`, `pSys001Test002[RXD]`
with `MATRIX_Y` = 4. `r1 = 0x8000` is `CS_C_Pin` (GPIO_PIN_15) and `r0 = 0x42020000` is
GPIOA.

**Flash.** Packed with `hex2shex.py H1S1-s69.hex H1S1 H1S1-s69.shex` → 2144 records,
34,257 B image, md5 `2b377d1509aefa257bb64674c5cf17a8`. Previous pack kept as
`/home/app/fwbuild/H1S1-pre-s69-2026-09-19.shex` (md5 `a6c3911c81efc46178ec2b08df57a858`)
and as `/home/app/firmware/H1S1.shex.bak-2026-09-19-pre-s69`. Flashed with
`./app cli loadfw H1S1` → `OK: H1S1`, TX record 2144 ACKed, `// flash end of firmware
record`. After an app restart: `MCU verified: // H1S1 DSP`, and `MCU boot verified` for
H1S1 / H1S3 / H1S4 — 3 of 3, no `MCU not verified` warning.

**It took an MH1 SWD reset to get there, and that is S69-4.** The first `loadfw` failed
with `ERROR: MH1 loopback probe: no '// MH1 UART1 loopback OK' within 30s`, and a raw probe
of `/dev/serial0` confirmed it: MH1 answered nothing at all. `reset run` through
`/home/app/mh1-swd.cfg` does **not** work — OpenOCD aborts the `reset-start` event with
`Translation from khz to adapter speed not implemented`, because the `linuxgpiod` adapter
has no settable speed. Writing `SYSRESETREQ` by hand does:

```
sudo pinctrl set 5 op dl; sudo pinctrl set 13 op dh          # SWD mux ch3
sudo openocd -f /home/app/mh1-swd.cfg -c "init; halt; mww 0xE000ED0C 0x05FA0004; shutdown"
sudo pinctrl set 5,13 ip
```

OpenOCD logged `target was in unknown state when halt was requested` — MH1 was genuinely
wedged, not merely quiet — and the next `loadfw` succeeded first try.

## Gate 0 — the loop, rails off

TEST_OSC 1 kHz on donor strip 6 (→ AUX 1 → J45), MeasChan 51 on the talkback lane:

| oscillator | lane, dBFS |
|---|---|
| off | −76.192 |
| −60 dBFS | −76.049 |
| −20 dBFS | −76.056 |
| −6 dBFS | −76.000 |

Flat across 54 dB of drive: **the loop is open.** The lane is not dead, though — the block
reads as moving converter noise (`00017260 00001420 0000FE60 FFFFF9E0 FFFF6340 …`), not a
stuck word, so the codec is converting and framing correctly. The donor strip read −63.017
dBFS against a −60 dBFS oscillator, which is the −3.01 dB mean-square convention exactly, so
the graph and the oscillator were both live throughout.

## Gate 2 — the lever, proved without a cable

The dispatch's witness for gate 2 was the tone through the loop. Without the cable there is
a better one: the codec's own registers move the lane's noise floor, and by an amount the
datasheet states.

**The write path lands.** `00H := 0x00` (RSTN low, every ADC and DAC powered down) drives
the lane to **exact digital zero** — every word `0x00000000`, RmsResult −336.1 dBFS. `00H :=
0x37` brings it back to −75.99. That single result proves the whole chain at once: matrix
bus line → MH1 → H1S1 `Uart1_Int`/`Eol` → `CodecPoll` → `SpiTx` → AK4619 register → SDOUT →
CPLD `i_dspa[4]` → SPORT4 → the tap.

**And it lands quantitatively.** ADC digital volume `0x00` is **+24.0 dB** (Tables 11/14 —
the column is *attenuation*, so a higher code is quieter; `0xFF` is mute and `0x30` is
0.0 dB). Writing `0x00` to each ADC volume register, tone off, watching every received slot:

| register | slot 0 | slot 2 | slot 3 |
|---|---|---|---|
| baseline (all `0x30`) | −75.868 | −98.761 | −83.059 |
| `06H` VOLAD1L := `0x00` | **−51.934** (+23.93) | −98.670 | −82.887 |
| `07H` VOLAD1R := `0x00` | −76.022 | −98.744 | −82.864 |
| `08H` VOLAD2L := `0x00` | −75.858 | **−74.589** (+24.17) | −82.764 |
| `09H` VOLAD2R := `0x00` | −76.050 | −98.745 | **−58.868** (+24.19) |
| restored | −75.918 | −98.767 | −82.897 |

Each register moves exactly one slot, by +24.0 dB nominal / +23.9 to +24.2 dB measured, and
nothing else. `07H` (ADC1 Rch) moves nothing because **slot 1 is not received at all**:
SPORT4's channel-select mask is `0x000D` = slots 0, 2, 3 (`chip1/lane_config.c`).

**The gain register works too.** `05H` MGN2R stepped through all twelve codes, tone off,
every received slot watched. Slot 3 tracks it over the whole range; slots 0 and 2 do not
move:

| MGN2R | nominal | slot 0 | slot 2 | slot 3 |
|---|---|---|---|---|
| 0 | −6 dB | −75.902 | −98.617 | −106.389 |
| 1 | −3 | −76.064 | −98.474 | −105.647 |
| 2 | 0 | −75.943 | −98.847 | −104.842 |
| 3 | +3 | −75.973 | −98.675 | −103.426 |
| 4 | +6 | −75.965 | −98.656 | −101.407 |
| 5 | +9 | −76.084 | −98.773 | −99.425 |
| 6 | +12 | −75.851 | −98.823 | −97.203 |
| 7 | +15 | −75.909 | −98.735 | −94.316 |
| 8 | +18 | −75.982 | −98.577 | −91.475 |
| 9 | +21 | −75.949 | −98.549 | −88.659 |
| 10 | +24 | −76.029 | −98.677 | −85.877 |
| 11 | +27 | −75.858 | −98.655 | −82.989 |
| restore 11 | +27 | −75.851 | −98.547 | −83.004 |

This is **not** T1 — it is the noise floor, not the gain law, and it is floor-limited at the
bottom where the ADC's own noise (−106.4 dBFS) swamps the preamp's. In the top half, where
the preamp dominates, the steps approach the nominal 3 dB (2.89, 2.78, 2.82, 2.84, 2.89 dB
for the 12→27 dB codes). What it does prove is that `05H` writes land, that MGN2R does what
Table 9 says, and — with the volume table above — **which slot ADC2 Rch is**.

`--reinit` (register `0xFF` → `StartAK4619()`) restored all three slots to their baseline
within 0.05 dB, so the re-init lever is proved as well.

## The codec's register image, decoded

`StartAK4619()` writes `{0xC3, 0x00, 0x00}` + 21 bytes = registers `00H`–`14H`.
`tools/pi/codec4619.py --decode` prints this without a part attached:

```
00H 37  Power: PMAD2=1 PMAD1=1 PMDA2=1 PMDA1=1 RSTN=1
01H AC  Audio I/F: TDM=1 DCF=2 -> TDM256 I2S compatible; DSL=3 (32-bit slot) BCKP=0 (BICK falling edge) SDOPH=0
02H 10  Audio I/F: SLOT=1 (slot-length basis) DIDL=0 (SDIN 24-bit) DODL=0 (SDOUT 24-bit)
03H 00  System clock: FS=0
04H BB  MIC gain: MGN1L=B (27.0 dB)  MGN1R=B (27.0 dB)
05H BB  MIC gain: MGN2L=B (27.0 dB)  MGN2R=B (27.0 dB)
06H..09H 30  ADC digital volumes, all +0.0 dB
0AH 00  ADC digital filter: all defaults
0BH 00  ADC analog input: AD1L/AD1R/AD2L/AD2R all differential
0DH 00  ADC mute/HPF: nothing muted, both HPFs off (AD1HPFN=AD2HPFN=0)
0EH..11H 18  DAC digital volumes
12H 04  DAC input select: DAC2SEL=1 DAC1SEL=0
13H 05  DAC de-emphasis: DEM2=1 DEM1=1
14H 0A  DAC mute/filter: DA2SD=1 DA1SD=1
```

**The format matches what DSPA I4 expects.** Table 2 is indexed by TDM *and* DCF together —
the same DCF code names a different format in each half of the table — and (TDM=1, DCF=010,
SLOT=1, DSL=11) is row 10: **TDM256 mode, I2S compatible, 32-bit slots, BICK = 256 fs**.
That is 12.288 MHz at 48 kHz, which is the BCK2 the codec is clocked from, and it is the
same AKM I2S variant the AK5558/AK4458 are pin-strapped into. `sport_config.c` sets SLEN=31,
external clock and FS, CKRE=1; the generated lane table gives SPORT4 `cs_mask 0x000D`, 3
words per sample, **MFD 2** — the converter value, which is what the I2S variant needs (one
BCK for the variant on top of the one LOGIC already leaves). No mismatch: the init image is
not the reason the loop reads open. It was left unchanged, as instructed.

Two things in the image are worth the hub's eye even so: **all four mic amps come up at
+27 dB** (`04H`/`05H` = `0xBB`), which is a 3.3 Vpp analog ceiling on every codec input
until something lowers them; and **both ADC HPFs are off** (`0DH` bit 2 / bit 1 = 0), so
there is no DC blocking in the codec on the talkback path.

## Findings

**S69-1 🔴 THE TALKBACK LANE IN THE GRAPH IS NOT THE TALKBACK MIC'S CONVERTER CHANNEL —
hub/PW call, not this session's.**
Measured mapping, codec ADC channel → SPORT4 TDM slot, by two independent levers (ADC
digital volume `06H`/`08H`/`09H`, and mic amp gain `05H`):

| codec channel | TDM slot | graph node | graph's name | goes to |
|---|---|---|---|---|
| ADC1 Lch | 0 | `C1_XIN_CODEC_01` | "Codec ADC 1 (TB XLR)" | `C1_TALK_01` |
| ADC1 Rch | 1 | — | — | **not received** (`cs_mask 0x000D`) |
| ADC2 Lch | 2 | `C1_XIN_CODEC_03` | "Codec ADC 3 (Aux In L)" | `C1_XS_XFER_CODEC_AUX_L` |
| ADC2 Rch | 3 | `C1_XIN_CODEC_04` | "Codec ADC 4 (Aux In R)" | `C1_XS_XFER_CODEC_AUX_R` |

The dispatch's netlist walk (mx26 `docs/d24-analog-paths.md` "Talkback and aux";
`docs/d24-signals-index.md` I4) puts the talkback XLR J1 on IN4 → **MIC Gain Amp 2 Rch →
ADC2 Rch**, which this session measures as **slot 3**. The graph feeds `C1_TALK_01` from
slot 0. If the netlist walk is right, the talkback mic is arriving on the codec-aux-in path
into the main mix, and the TALKBACK node is fed from a different converter channel
altogether.

This session has **not** proved which way it goes: it proved the codec-channel → slot
mapping, not which XLR feeds which codec channel. One measurement settles it, and it is the
first thing the bench run should do — with the loop cable on, inject the tone and read
MeasChan 51, 52 and 53; whichever carries it is the talkback's lane. Until then, treat
either the `dsp.csv` row or the netlist walk as wrong, not both as right.

Note that slot 1 being unreceived means one of the four codec ADC channels never reaches the
DSP at all, whatever the answer.

**S69-2 🟢 The AK4619 can be driven from the matrix bus, and the write form is the
single-register one.** `{0xC3, 0x00, reg, val}` confirmed against 9.12/9.13 and proved on
the part (`00H := 0x00` → exact digital zero on the lane; +24.0 dB volume steps landing to
within 0.2 dB; MGN2R monotonic over twelve codes). Register `0xFF` as a re-init lever
restores the init image exactly. `tools/pi/codec4619.py` is the lever; `s69lib.Rig.mgn2r()`
is the measured-context wrapper that shuts the DSP link for the duration, because H1S1's SPI
master and the CM4's SPI0 are the same SCK/MOSI copper.

**S69-3 🔴 The talkback path had no measurement tap, and the standard test set could not
have been run on it as dispatched.** `C1_XIN_CODEC_01` feeds only `C1_TALK_01`, whose
`_buf_` is a **scalar** written once per block (the one-word-per-block witness shape) and
which nothing downstream reads — the empty TALKBACK fan-out `dsp-unmapped.csv` records
against `Talk001Dest002/3`. So MeasChan 1–32 (strips) and 33–50 (buses, S67) all miss the
path. Fixed here by extending the S67 bus-tap pattern to the converter-return lanes:
`TEST_MEAS_LANE_CODES` in `tools/dsp/dsp_codegen.py` adds **MeasChan 51 = CODEC_RET_1, 52 =
CODEC_RET_3, 53 = CODEC_RET_4, 54 = MEMS_TB**, reading each lane's own
`_buf_<nid>[DSP4_BLOCK_SIZE]` at full rate. Codes only — no new cell, no new address, every
emitted line inside `#if DSP4_TEST_NODES`. Chip 1 grew 64 bytes (four hooks × four
instructions); **chip 2's `.ldr` is byte-identical to S67's** (`251ce3b2…`), which is the
control. Proposed to the hub as a MeasChan description change, the same shape S67's bus
codes were proposed under.

**S69-4 🟡 `reset run` in `/home/app/mh1-swd.cfg` does not reset MH1.** OpenOCD's
`reset-start` event calls `adapter speed`, the `linuxgpiod` driver has none, and the event
aborts — so the documented recovery silently does nothing. `init; halt; mww 0xE000ED0C
0x05FA0004; shutdown` (SYSRESETREQ by hand) works. Worth folding into the cfg's own
`reset-start` handler or the runbook.

**S69-5 🟡 MH1 wedges, and the app is the only thing that notices.** With `matrix-app`
stopped, MH1 answered neither the app's loopback probe nor a raw `/dev/serial0` probe;
OpenOCD found the core "in unknown state". After the SWD reset and the flash it relayed
normally. Two practical notes for anyone driving the bus by hand: the bus tokens are
**newline-terminated** (`Boot.cs` uses `serialPort1.WriteLine`) — a bare `&` gets nothing and
looks exactly like a dead bus; and MH1 emits a steady `.`/`:` heartbeat when idle, so
"something arrived" is not evidence that the bus is working.

**S69-6 🟡 The AK4619's analog section is live with AN_EN low.** MGN2R moved the lane's
noise floor over a 23.4 dB range while GPIO26 read `lo` throughout, so whatever AN_EN gates
on the analog board, it is not the codec's own supply. Anything that has been reading "AN_EN
low ⇒ no converter is converting" should be re-checked; it is true of the AK5558 mic lanes
(S49-15 measured MOVING 0 / STATIC 24) and is **not** true of the codec.

## T4, partial — noise floor per MGN2R code (open input)

The twelve-code table above **is** a T4 row set on slot 3, taken tone-off, and it is the
only row of the standard set this session can supply. Two caveats make it a reference and
not the spec figure: the input is **open**, not the 150 Ω the test set requires (an open mic
input reads high), and there is no loop gain yet, so it cannot be converted to dBu or
input-referred — T4b/EIN needs T1's gain at each code. Quoted in dBFS only, deliberately.

## Implications for `Talk[1-1]Gain[1-1]` — a proposal, not a def edit

Today the cell is a placeholder: `0=0/127=40/[Lin]`, MxDatS 65, ramp `GainFast`, and it
reaches `_talk_gain_C1_TALK_01`, a float multiply inside the TALKBACK node — a **DSP** gain,
with no connection to the hardware that actually sets the talkback's gain.

What the hardware offers on the codec's mic amp path is:

* **MGN2R[3:0]** — twelve analog steps, −6 … +27 dB, exactly 3 dB apart (Table 9), which is
  the only gain that is ahead of the ADC and therefore the only one that buys headroom or
  noise;
* **VOLAD2R[7:0]** — 256 digital steps, +24.0 … −103.0 dB in 0.5 dB, plus mute at `0xFF`
  (Tables 11/14), after the ADC, with a soft transition (4/fs a step at ATSPAD=0).

That is the same shape as the mic-pre law the test set already rules for this product
(spec-audio-test-set.md, "Mic gain law"): hardware steps plus a digital trim, the trim
always positive, the hardware combination chosen at or **below** the target so the analog
stage never carries more gain than asked for. Applied here it gives a clean 0.5 dB law over
−6 … +27 dB:

> target → `MGN2R` = largest 3 dB step ≤ target; `VOLAD2R` = target − MGN2R, 0 … +2.5 dB,
> rounded to 0.5 dB and always ≥ 0.

Proposed for the hub's defs pass, and explicitly **not** made here: the range the cell
should publish, whether `Talk Gain` addresses the analog steps, the digital trim or a single
composite law, and what happens to `_talk_gain_` in the node, are contract questions. They
also depend on S69-1 — if the talkback is on slot 3 then the cell that needs the codec gain
is not the one on the TALKBACK node at all.

## State the unit was left in

* `matrix-app` **running**, all three MCUs verified (`H1S1 / H1S3 / H1S4`), no
  `MCU not verified` warning.
* H1S1 on the **new** image (`2b377d15…`); previous pack kept on the unit twice over.
* AN_EN (GPIO26) **low — untouched**, exactly as found; a dispatched session never writes
  it, and the app logs `AN_EN STAYS LOW` on every start.
* Codec restored by `--reinit` and verified: all three received slots back within 0.05 dB of
  their entry values. MGN2R back at the init `+27 dB`. The 595 mic-pre chain was **never
  touched** — no `S_RESET` was sent from this session, so nothing cleared it.
* TEST_OSC **off**, MeasChan 0.
* **Two deliberate departures, stated rather than left silent.** The DSPs were **not booted**
  at session start (`SPI_RDY never asserted`) and are now running the S69 pair
  (chip1 `a8dc45eb847cf82bf5367a8c6c442877`, chip2 `251ce3b2eb758aecae22b7550facf789`,
  staged at `/home/app/s69`) — left booted because the bench run needs exactly that pair.
  GPIO27 was set `ip pu` (the CS_M / U2 MISO-buffer fix) and left there, because the DSP
  link needs it; it read `ip pd` at session start.

## What the bench run needs

1. `sudo pinctrl set 26 op dh` — AN_EN. Hub's or PW's to run.
2. The loop: AUX 1 output (rear XLR J45) → talkback XLR J1.
3. **First measurement, before anything else:** tone on, read MeasChan 51, 52 and 53. That
   settles S69-1 and decides which lane the rest of the battery is run on.
4. Then T1 over the twelve MGN2R codes (`s69lib.Rig.mgn2r`), T2 at −6 and +27, T3, T5
   (expect **inverted** — J1 pin 2 → IN4N, pin 3 → IN4P), T8; then the 150 Ω on J1 for T4
   and T4b.

Everything those steps need is staged at `/home/app/s69`: the pair, `s69lib.py`,
`codec4619.py`, and the S67 tool set beside them.
