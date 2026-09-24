provenance: AI-drafted 2026-09-24 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S108 — the AK4619's DAC is configured correctly and fed nothing. The CPLD ties its SDIN1 to zero.

> **`rtl/dsp4_logic_top.v:792` is `assign cdc_i = strap_d32 ? 1'b0 : o_dspb[2];`
> — and `strap_d32` reads HIGH on this D24, measured again this session. So the
> codec's serial data input is held at a constant logic 0 by the CPLD, in every
> bitstream this unit has ever carried. The DAC receives digital silence, and
> `U3.22 (AOUT1L)` sits at its DC bias with nothing on it. That is the whole of
> the symptom, and the codec is not at fault: all twenty-one registers read back
> live off the part, and every DAC-relevant bit is correct.**

The datasheet was found (§1). The register readback is complete and clean (§2).
The TDM slot alignment for DAC1 is correct (§3) — and a second, genuinely
separate bug in the init image was found while checking it, which would have
kept the *aux outputs* silent even after the strap is fixed (§3.3). §4 is the
root cause. §6 is what PW can measure next, including a two-line register
recipe, verified on the part this session, that proves the DAC and its analog
output stage with the DSP, the CPLD and SDIN1 removed from the path entirely.

## 1. The datasheet — found, in two places, and one of them is a live URL

Dispatch §1 asked for it plainly, so plainly: **it exists and it was never
missing.**

| | |
|---|---|
| document | AK4619 English Datasheet, **200900082-E-00, 2021/06**, Asahi Kasei Microdevices, 73 pages |
| already on this machine | `~/Stonepower Dropbox/Peter Watts/_mx/_0/tools/PCBA/ConsoleApp1/bin/Debug/net6.0/PCBA/Datasheets/Codec AK4619.pdf` |
| fetched fresh | `https://www.akm.com/content/dam/documents/products/audio/audio-codec/ak4619vn/ak4619vn-en-datasheet.pdf` → **HTTP 200**, 1,559,506 bytes |
| identical? | yes — `md5 57b8e7a0c41cdffe4b1336b4bf92e6d2` on both |

**akm.com is NOT blocked from this box.** That is worth saying on its own,
because S106 was blocked on a datasheet and recorded "analog.com blocks curl
AND WebFetch from this machine" — true, and it does not generalise. `curl` to
akm.com returns 301 → 200 and hands over the PDF. (`alldatasheet.com` and
`digikey.com` both return 403 behind a Cloudflare challenge; `mouser.com`
times out. The vendor's own site is the one that works.)

**The local copy's `file` output says "3 page(s)" and is a trap** — the PDF is
RC4-encrypted for copy-protection and `file` reads the wrong object. `pdfinfo`
says 73 pages and `pdftotext` extracts the whole thing. A future session
looking for this file should not discard it on the `file` line.

Not copied into this repo (CLAUDE.md: bulky reference material belongs in
`_Matrix`, not here) and not filed into `_Matrix/Products/D24/hw/` either,
because `hw/README-boards-moved.txt` records PW's 2026-09-06 ruling moving D24
board packages out to the Design Control app and this session is not the place
to decide where vendor datasheets now live. The URL above is the durable
answer: one `curl` re-fetches it.

## 2. The live register readback — all twenty-one, and every DAC bit is right

`MW/D24/DSP/s108/data/codec-register-readall.txt`, read off the part this
session through the S81 read arm (`tools/pi/codec4619.py --read-all`), no
reflash, no reset, guard byte `0x43` on every one and `ANSWERED` on every one:

```
00H 37   01H AC   02H 10   03H 00   04H BB   05H BB   06H 30   07H 30
08H 30   09H 30   0AH 00   0BH 00   0CH 00   0DH 00   0EH 18   0FH 18
10H 18   11H 18   12H 04   13H 05   14H 0A
```

**This is byte-for-byte the init image** `StartAK4619()` writes
(`~/build-h1s1/Core/Inc/matrix.cs:70`, `ak4619[24]` less its three-byte SPI
header). Nothing drifted, nothing failed to take, no register the init left
untouched holds a surprise. The dispatch asked for the difference between "a
write that took" and "a register that drifted" — there is no difference here,
because there is no drift.

Decoded against the datasheet (the decoder in `tools/pi/codec4619.py` was
extended this session, §7):

| reg | live | meaning | correct? |
|---|---|---|---|
| 00H | `37` | PMAD2=1 PMAD1=1 **PMDA2=1 PMDA1=1** RSTN=1 | **yes** — both DACs powered, reset released |
| 01H | `AC` | TDM=1, DCF=010, DSL=11 → **Mode 10, TDM256 I2S compatible, 32-bit slot**; BCKP=0 | yes (Table 2) |
| 02H | `10` | **SLOT=1** (slot-length basis), DIDL=24-bit, DODL=24-bit | yes — Table 3 *requires* SLOT=1 in TDM |
| 03H | `00` | FS=000: MCLK 256fs, BICK 32–256fs, 8 k ≤ fs ≤ 48 k | yes — see below |
| 0EH–11H | `18 18 18 18` | **DAC1 L/R, DAC2 L/R digital volume = 0.0 dB** | yes |
| 12H | `04` | DAC1SEL=00 → **SDIN1**; DAC2SEL=01 → SDIN2 | **DAC1 yes; DAC2 NO** (§3.3) |
| 13H | `05` | de-emphasis DEM1=DEM2=01 = OFF | yes |
| 14H | `0A` | ATSPDA=0, **DA1MUTE=0, DA2MUTE=0**, DA1SD/DA2SD=1 (short-delay filter) | **yes — not muted** |

**The DAC volume law is not the ADC's, and the difference matters.** Table 19:
`0x00` = +12.0 dB, **`0x18` = 0.0 dB (default)**, `0xFF` = mute. The ADC's zero
is `0x30`. `0x18` read against the ADC table would look like +12 dB of gain and
against a `0xFF`-is-0 dB convention would look like near-total attenuation; it
is neither. It is unity. The tool decoded DAC volumes with no dB value at all
until this session precisely because the law was unknown — that is fixed.

**03H = 0x00 is right, and the board is why.** `U3.7 (BICK)` and `U3.8 (MCLK)`
are the same net — `G0206` on the analog PCBA, both fed through `R18` from net
`C1`. TDM256 makes BICK 256fs, so MCLK is 256fs too, and FS=000 is exactly the
"MCLK 256fs, BICK 256fs, fs ≤ 48 kHz" row of Table 1. `U3.6 (LRCK)` comes
through `R17` from net `L0`. Both nets are the analog board's distributed clock
pair, shared with the five AK5558 ADC groups (`R54/R55`, `R687/R688`,
`R1274/R1275`, `R1861/R1862`, `R1996/R1997`) — all of which are converting.

**And Table 8 settles the power state without a probe.** Power-down and
standby both leave the analog outputs **Hi-Z**; reset leaves them at
**AVDD/2**; only normal operation gives signal. With PDN high (proved by the
registers reading non-default at all), PMDA1/2 = 1 and RSTN = 1, this part is
in **Normal operation**. So `AOUT1L` should idle at AVDD/2 ≈ **1.65 V**, and
that is a measurement (§6.1).

### 2.1 — one correction to the dispatch's pin list

The dispatch says "the full pin list confirms no separate analog supply pin."
The datasheet says otherwise, and the board is still right:

| pin | datasheet | net on this board |
|---|---|---|
| 3 | **TVDD** — digital I/F & LDO supply, 1.7–3.6 V | `+3V3` (G2408) |
| 18 | **AVDD** — *analog* supply, 3.0–3.6 V | `+3V3` (G2408) |
| 21 | **VREFH** — "must be connected externally to AVDD" | `+3V3` (G2408) |
| 4 / 19 / 20 | VSS2 / VSS1 / VREFL ("must be connected externally to VSS1") | `GND` (G2607) |

There *is* a separate analog supply pin; it is simply tied to the same `+3V3`
rail, which is what the datasheet asks for. **The dispatch's conclusion holds —
this is not a rail problem and `AN_EN` is not in it — but the reasoning was
wrong and the next reader should not inherit it.**

**Two pins the dispatch's list omits entirely, and both are mandatory
external components:**

- `U3.5` = **AVDRV**, the internal 1.2 V LDO output, "should be connected to
  VSS2 through a 2.2 µF capacitor" and to nothing else. Netlist: `G0202` =
  `U3.5` + **`C18.1`**. Fitted.
- `U3.17` = **VCOM**, the common-voltage output (½ × AVDD), same 2.2 µF rule.
  Netlist: `G0211` = `U3.17` + **`C19.1`**. Fitted.

Both are two-pin nets with the cap and nothing else, exactly as specified, so
neither is a candidate — but they are the two pins that would kill every analog
output at once, and they were not on the list that had been checked.

## 3. The TDM slot check — DAC1's slot is right; DAC2's *source* is not

### 3.1 What the part reads

Figure 19 (Mode 10, TDM256, I2S compatible) lays SDIN1 out as four 32-bit
slots of data followed by four don't-cares:

```
SDIN1 (32-bit)   "L" | DAC1 Lch | DAC1 Rch | DAC2 Lch | DAC2 Rch | don't care ... | next
                       slot 0     slot 1     slot 2     slot 3
```

**Slot 0 of the codec's SDIN1 is DAC1 Lch is `AOUT1L` is `U3.22`.** The slot
assignment is fixed by the mode, not by a register — there is no slot-select
bit to get wrong.

### 3.2 What the DSP sends there

`shared/dsp4-logic/slot-map.csv` puts `CODEC_OUT_1` on `B_O2` slot 0, and
`tdm-lines.csv` maps `B_O2` to DSPB port `O2` → external `CDC_I`. The netlist
agrees end to end: `DSPB U5.48 (DAI0 pin06) → R10 → LOGIC U3.50`, and out of
the CPLD `U3.124 → J18.56 → R115 → J42.6 = analog J59.6 → AK4619 U3.1 (SDIN1)`
(`G0192`/`G2538`/`G2679`/`G3233`, board net `CDC_I`).

**So the slot map's DAC-side entry is correct** — checked against the part's
own mode table, not taken from the doc. S106-2's contradiction does not repeat
here. `C2_MON_OUT` → `CODEC_OUT_1` → `B_O2` slot 0 → DAC1 Lch → pin 22 is a
sound chain, and it is the right one.

### 3.3 🔴 S108-2 — but DAC2 is pointed at a pin that carries nothing

`12H = 0x04` is the reset default, and the init image writes the default back
rather than setting it. That default is **DAC1SEL = 00 (SDIN1), DAC2SEL = 01
(SDIN2)** (Tables 17/18). Two facts collide with it:

- Datasheet 9.3: *"When AK4619 is functioning in TDM mode, only the SDIN1 pin
  and SDOUT1 pin are supported… **input data on the SDIN2 pin is ignored**."*
- Netlist: `G3619` = **`N/C:U3.2`** — SDIN2 is not connected to anything. (The
  datasheet's own "Handling of Unused Pins" says an unused SDIN "Connect to
  VSS2"; it is left open instead. Separate, minor, and worth an ECO note.)

**DAC2 is therefore fed from a source that is ignored by the mode and
unconnected on the board.** DAC2 is `AOUT2L`/`AOUT2R` = `U3.24`/`U3.25` =
`CODEC_OUT_3`/`CODEC_OUT_4` = **aux out L/R**. Those two outputs cannot work as
the part is configured, and they would still not work after §4 is fixed.

The fix is one byte in the init image: `matrix.cs` `ak4619[]` index 21
(register 12H) **`0x04` → `0x00`** (DAC1SEL = DAC2SEL = SDIN1). It is *not*
made here — it is H1S1 firmware, it needs a flash, and this is the DAC1
session. It is filed so the aux outputs are not the next mystery.

## 4. The root cause — `cdc_i` is tied to zero, and it always has been

### 4.1 The line

`shared/dsp4-logic/rtl/dsp4_logic_top.v:792`, unconditional, outside every
build-flag `ifdef`:

```verilog
assign cdc_i = strap_d32 ? 1'b0 : o_dspb[2];    // D24 codec DAC
```

The intent is plain and is documented all over the tree: on a **D32**, `B_O2`
is the snake send, so the codec lane is muted and the same data leaves on
`snake_out` instead (`rtl:823`, `assign snake_out = strap_d32 ? o_dspb[2] :
1'bz`). On a **D24**, `strap_d32` is meant to be low and the codec gets the
data. `git log -S "cdc_i = strap_d32"` returns exactly one commit — `e9b0f7da`,
the original routing top — so this has been the wiring in **every bitstream
this bench has ever carried**, which is why the DAC side has never worked and
why nothing before today noticed: nothing before today asked.

### 4.2 The measurement — `strap_d32` is HIGH on this D24

`MW/D24/DSP/s108/data/rxscan-strap-evidence.txt`, fresh this session, correct
symbol map (no `?` in the node column), all three rxscan controls `[ok]`,
32 reps, on the part carrying the shipping bitstream
(`design_id 32'h83b3cc22 cfg_bits 16'h0010 SHIPPING`, read off it, no flash):

```
XIN_SNK_01   lane 5   32 reads, 1 distinct, ffffffff   STATIC  -186.64 dBFS
XIN_PI_L     lane 6   32 reads, 1 distinct, 00000000   STATIC  -336.00 dBFS
XIN_CODEC_01 lane 4   32 reads, 32 distinct            CARRYING  -77.33 dBFS
```

`rtl:781` is `assign i_dspa[5] = strap_d32 ? snake_in : 1'b0;`.

- If `strap_d32` were **0**, lane 5 would be a hard `0x00000000` — which is
  what a CPLD-driven constant reads as, and lane 6 is the control that shows it.
- Lane 5 instead reads `0xFFFFFFFF`, which is `snake_in` — PIN_109, the pin
  carrying an explicit `WEAK_PULL_UP_RESISTOR`, floating high with option slot 2
  empty.

**The mux took the `snake_in` branch. `strap_d32` = 1.** This reproduces
S106-3 independently, on a fresh boot of the scan, and it is the same reading
S86's archived handback scan shows.

With `strap_d32` = 1, line 792 evaluates to `assign cdc_i = 1'b0`. **The
AK4619's SDIN1 is held at logic low by the CPLD.** Every DAC slot in every
frame is zero. The DAC converts it faithfully to a constant, and `AOUT1L` sits
at VCOM with no AC content.

### 4.3 Why the ADC works and the DAC does not

`assign i_dspa[4] = cdc_o;` (`rtl:780`) — a plain wire, no strap. The codec's
**return** path was never gated, which is why every prior session found the
part alive, clocked, converting and answering, and why lane 4 carries 32
distinct values in the scan above. The strap gates the **send** path only. Every
test this board has ever passed on this codec was an ADC test; the one thing
the strap breaks is the one thing that had never been asked.

### 4.4 Where the strap comes from — and it has no defined level

`qsf:46` is `set_location_assignment PIN_70 -to strap_d32`, commented
`S4: product personality (PROV.)`. The netlist gives that net **two pins and no
more**:

```
G2737, dsp, "M MCU_S4", U3.70   (LOGIC CPLD)
G2737, dsp, "M MCU_S4", U8.11   (M MCU, STM32G031C8T6 on the DSP card)
```

- **No pull resistor anywhere on the net.**
- **No `WEAK_PULL_UP`/`WEAK_PULL_DOWN` on PIN_70** in the qsf — only
  `snake_in`, `snake_out` and `dac_main` got those, and the global
  `RESERVE_ALL_UNUSED_PINS` does not cover an assigned pin.
- MAX V I/O offers **weak pull-UP only**, so the CPLD cannot supply a
  pull-down even if one were added.

So the D24/D32 personality strap is defined **entirely** by whether MH1 drives
`U8.11` low, and the measurement says it is not being driven low. Two readings
fit and this session cannot separate them: the pin is left as a floating input
(a MAX V input with no pull settling high), or MH1 drives it high. The net name
is the worry — the M MCU's documented job is "S0–S31 matrix signalling
blink/dim comms", and if `S4` is a live signalling line rather than a spare
pin, then `strap_d32` is not merely stuck wrong, it may be **changing at
runtime**, chattering `cdc_i` between `0` and `o_dspb[2]`. That is §6.4.

### 4.5 One cause, three symptoms

| symptom | where | status |
|---|---|---|
| codec DAC dead — nothing at `U3.22`, nothing at `C23` | `cdc_i = 1'b0` | **this session** |
| lane 5 reads `0xFFFFFFFF` instead of a hard zero | `i_dspa[5]` | S106-3, cosmetic |
| `snake_out` (PIN_110) and `dac_main` (PIN_111) **driven** on a D24 instead of high-Z | `rtl:823/824` | S106-3 / S36-4 — **latent hazard**: slot 2 is empty today; fit a card and two drivers fight |

The third is the one to weigh when scheduling the fix. S36's comment says
tri-stating on a D24 is precisely so "a card fitted to slot 2 owns its own
lanes"; with the strap high, that protection is off.

## 5. What this does and does not explain

**Explains**, with no further assumption: no signal at `U3.22 (AOUT1L)`, no
signal at `C23`, nothing on net `SPKR`, and `SP1` never having produced data.
S103's `TEST_OSC`/`TEST_MEAS` proof is not contradicted by any of it — that
measured the DSP's own node `C2_MON_OUT` and its internal routing, which are
correct, and the signal is genuinely computed and genuinely handed to `O2`.
It leaves the CPLD on pin 110 instead of pin 124.

**Does not explain, and is not claimed to**: the aux outputs (§3.3 is a second,
independent cause standing in front of them), or anything about the talkback
mic / MEMS lane (S106).

**Not yet proved by measurement at the pin**: that the DAC and its analog
output stage are themselves healthy. Everything above is registers, RTL and
netlist. §6 is how to close that, and it is a probe job.

## 6. For PW at the bench — what to measure, in this order

### 6.1 Two multimeter readings, unit as it stands, thirty seconds

| point | expect | what a miss means |
|---|---|---|
| `U3.22` (**AOUT1L**) DC to GND | **≈ 1.65 V** (AVDD/2) | Table 8: normal operation and reset both give AVDD/2; **Hi-Z / ~0 V means the part is in standby or power-down despite the registers**, and that would overturn §2 |
| `U3.17` (**VCOM**) DC to GND | **≈ 1.65 V** | no VCOM = no output bias = every AOUT dead, and `C19` is the suspect |
| `U3.5` (**AVDRV**) DC to GND | **≈ 1.2 V** | the internal analog LDO is down; `C18` is the suspect |

If AOUT1L is at 1.65 V DC with no AC, §4 is confirmed from the analog side too
and the part is healthy and simply fed zeros.

### 6.2 The decisive test — prove the DAC with the DSP, the CPLD and SDIN1 removed

The AK4619 has a 4:1 mux in front of each DAC (Figure 29, Table 17). Setting
`DAC1SEL = 10` routes **the codec's own ADC output straight into DAC1 inside
the chip**, so `AOUT1L` carries analog audio with `SDIN1` — and therefore the
whole strap problem — completely out of the path.

**Verified on the part this session** (written, read back, restored, read back
again; the unit is back at `12H = 0x04` exactly as found):

```
$ python3 codec4619.py --reg 12 --val 0A      # DAC1SEL=10 (SDOUT1), DAC2SEL=10
12H := 0x0A
$ python3 codec4619.py --read 12
12H -> 0x0A   guard 0x43   ANSWERED
$ python3 codec4619.py --reg 12 --val 04      # restore
12H := 0x04
$ python3 codec4619.py --read 12
12H -> 0x04   guard 0x43   ANSWERED
```

With `12H = 0x0A`, feed the **aux-in mini-jack** (ADC1 Lch = `CODEC_RET_1`) and
scope `U3.22`. Note `04H = 0xBB` puts **+27 dB** of mic-amp gain in front of
ADC1 Lch, so start with a small source or drop `MGN1L` first
(`codec4619.py --reg 04 --val 2B` gives MGN1L 0 dB, MGN1R +27 dB).

- **Signal at pin 22** → the DAC, the output stage, `C23` and the part are all
  good; the only thing ever missing was data on SDIN1, and §4 is the complete
  answer.
- **Nothing at pin 22** → §4 is still true but is not the *only* thing wrong,
  and the question becomes the part or its pads. That is the point at which
  this stops being a register question, exactly as dispatch §4 asks.

Restore `12H := 0x04` afterwards.

### 6.3 One scope reading that shows the strap directly

`U3.1` (**SDIN1**, net `CDC_I`) should be **flat at logic 0** — no TDM data at
all — while `U3.6`/`U3.7` (LRCK/BICK) are running normally. That is the
signature of `cdc_i = 1'b0`, and it distinguishes it from a broken link, which
would show noise, a stuck high, or a partially-formed frame. The same data
should be visible on `LOGIC U3.110` (`snake_out`, → `digital J18.74`), where
the strap is sending it instead.

### 6.4 🔴 S108-3 — for whoever owns MH1

Is `U8.11` (net `M MCU_S4`) driven at all, and is it part of the S0–S31
signalling bus? If it is a live signalling line, `strap_d32` may be toggling
and the fix is not "drive it low", it is "move the strap off the signalling
bus". MH1's source is not on this machine.

## 7. Fix options — named, not taken

`AN_EN` untouched, no CPLD flash, no MCU flash, no RTL committed. The
S106-1 hash-labelling problem applies to anything touching `rtl/*.v` or the
qsf: `build.sh`'s `SRC_HASH` covers both, so even a compiled-out `ifdef`
renames the shipping bitstream while the part carries `d02d83b3cc22`.

| | fix | cost | notes |
|---|---|---|---|
| **A** | **MH1 drives `U8.11` LOW** early in init | firmware only — **no CPLD flash, no board change, no new bitstream label** | cheapest and correct; fixes all three symptoms of §4.5 at once. Blocked on §6.4 |
| B | fit a pull-down on net `M MCU_S4` | board rework / ECO | belt and braces for A; the net has no pull today and probably should |
| C | `WEAK_PULL_DOWN` on PIN_70 in the qsf | — | **not available.** MAX V I/O offers weak pull-*up* only |
| D | invert the strap sense in the RTL | new bitstream | wrong — it just breaks D32 instead |

**A is the recommendation**, with B alongside it. Both are outside a DSP
session's remit and neither was taken.

Separately and independently, §3.3: `matrix.cs` `ak4619[]` index 21,
`0x04 → 0x00`, for the aux outputs. H1S1 firmware, one byte, needs a flash.

## 8. Tool change made here

`tools/pi/codec4619.py` — the decoder could not read the DAC half of the image
before this session because the datasheet was not in hand:

- **`voldac_db()` added** (Table 19/22): `0x00` = +12.0 dB, `0x18` = 0.0 dB
  default, `0xFF` = mute. Deliberately a second function beside `voladc_db()`
  rather than a shared one — the two laws are offset by `0x18` and reading a
  DAC image against the ADC table calls the part's own default "+12 dB".
- **12H now names its sources** and flags the §3.3 trap directly: with TDM=1,
  a `SEL` of `01` prints `SDIN2  <-- DEAD SOURCE IN TDM MODE`.

Shared tool, no per-product copy, no contract surface touched.

## 9. Unit as handed back

**Restored to exactly the state it was found in**, and the one write made was
round-tripped and verified by readback:

- `AN_EN` **never written** — `26: op -- pd | lo` at start and at handback.
- `CS_M` **never written** — `27: ip pu | hi` throughout.
- **No CPLD flash.** Design ID read off the part twice, both
  `32'h83b3cc22 cfg_bits 16'h0010 SHIPPING`.
- **No DSP boot** — the pair booted before this session was peeked, not
  reloaded; `/home/app/loopthd/s103` untouched.
- **595 mic-pre chain not written** — left as S103's SAFE handback left it. No
  `--reset` and no `--reinit` was ever sent, so `MainInit()` did not re-run and
  did not rewrite the chain to `micGainFull`.
- **Codec registers: one write, reverted.** `12H` 0x04 → 0x0A → 0x04, each step
  confirmed by readback. The final `--read-all` in
  `data/codec-register-readall.txt` is the as-handed-back image and equals the
  init image.
- Test mode as found: `d24-testui` active, `matrix-app` inactive.
- `s108_codec4619.py` staged at `/home/app/` (a copy of the repo tool, md5
  `447cf0d2531fa3c8df7bfcb662e4593f` as staged, before the §8 change). Nothing
  else added to the bench.
- `defs.lock` unmoved at `defs-v2026.09.19.3` — **no contract bump owed**; no
  generated artifact, def CSV, slot map or wire table was changed.

## 10. Artifacts

| file | what |
|---|---|
| `data/codec-register-readall.txt` | all 21 registers read live off the part, with the decode; the as-handed-back image |
| `data/rxscan-strap-evidence.txt` | design-ID read-back + the 47-lane scan, 32 reps, with lane 5 vs lane 6 as the strap evidence |
