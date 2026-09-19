provenance: AI-drafted 2026-09-19 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S70 — the talkback mic input: the AK4619 gain law and the standard test set, on the closed loop

Unit MW-D24-2 (rev C, 192.168.1.219), 2026-09-19. The bench run S69 stopped short of: the
analog rails raised in this session under the dispatch's own authority, PW's AUX 1 → J1
loop cable in place, and the standard test set (mx26 `docs/spec-audio-test-set.md`) run on
the talkback input with the AK4619's mic-amp gain driven through H1S1.

Everything S69 built was used unchanged — the S69 pair, `CodecPoll()` in H1S1,
`tools/pi/codec4619.py`, `s69lib` — and nothing it built was rebuilt.

## The headline

**S69-1 is settled, and the netlist walk was right.** With the loop closed and the rails
up, the tone arrives on **MeasChan 53 = `_buf_C1_XIN_CODEC_04` = TDM slot 3 = ADC2 Rch**,
at +41.757 dB, and on neither of the other two received codec lanes — they stay at their
tone-off floors across 40 dB of drive. The graph calls slot 3 *"Codec ADC 4 (Aux In R)"*
and routes it to the codec-aux-in path into the main mix; the node it calls
*"Codec ADC 1 (TB XLR)"* is slot 0 and carries nothing from J1. See S70-1.

**The gain lever works and the law is textbook.** Twelve MGN2R codes, −6 … +27 dB: every
step 3.00 dB to within 0.019 dB, monotonic, and the whole law within 0.017 dB of nominal.

**Two things had to be found before any of that could be measured**, and both of them made
the loop look broken or the analog look bad when neither was: the donor strip was not
routed to AUX 1 at all (S70-2), and once it was, the donor strip's own **compressor** was
squashing the stimulus above −18 dBFS and reading as an analog overload knee that does not
exist (S70-3).

## Bring-up, and the rails

The dispatch's sequence, in its order, with the found state recorded at every step.

| step | found | after |
|---|---|---|
| `matrix-app` | active | stopped |
| GPIO 26 (AN_EN) | `op pd \| lo` | `op pd \| hi` |
| GPIO 27 (CS_M) | `ip pu \| hi` | `op pu \| hi` (driven by the chain write) |
| GPIO 6 / 24 (DSP CS) | `op dh` both | `op dh` both |
| DSPs | booted on the S69 pair | re-booted + configured **twice**, BOOT_STAGE 7, CHIP_ID 1 / 2 verified |
| 595 chain | see below | SAFE image, **VERIFIED 200/200** |

The pair is S69's, unchanged: chip 1 `a8dc45eb847cf82bf5367a8c6c442877`, chip 2
`251ce3b2eb758aecae22b7550facf789`, staged `/home/app/s69`. Boot + config ran twice per the
standing recipe; both chips came up `BOOT_STAGE 7`, `SPORT0_ERR_A 0`, `SPI_ERR_COUNT 0`,
`RESP_DROP 0`.

**The 595 chain was not found in a safe state, and that is S70-7.** Pass-1 MISO — which
returns what was in the chain *before* the shift — read

```
00 E0 FE 00 00 00 00 00 00 E0 EB 20 00 00 00 00 00 E0 FE 00 00 00 00 00 00
```

That is not an image anyone wrote: it is DSP SPI traffic latched into the chain, the S48-7
mechanism. Three of those bytes (`0xFE`) decode as *unmuted, phantom ON, gain 63*. The SAFE
image (`[0x01] × 24 + [0x00]`: every input muted at gain 0, phantom off, INSTR off) went in
next and verified 200/200, and the session left it there rather than restoring the garbage
— see "State the unit was left in".

**AN_EN.** `sudo pinctrl set 26 op dh`, 150 ms, then gate 0. The rails moved something
immediately and measurably: slot 3's tone-off floor rose from **−83.06 dBFS** (S69, rails
off) to **−69.19 dBFS**, while slot 0 (−76.2) and slot 2 (−98.7) did not move at all. That
is the talkback front end coming alive at +27 dB of gain and nothing else — a rails witness
that costs nothing and names the channel at the same time.

## Gate 0 — the loop, and why it read open the first time

With the rails up, gate 0 STILL read flat: every codec lane within 0.4 dB across 30 dB of
oscillator drive, while the donor strip tracked the oscillator exactly (−83.017 / −73.017 /
−63.008 / −53.008 dBFS for −80 / −70 / −60 / −50 dBFS, the −3.01 mean-square convention to
three decimals).

The donor strip is not the DAC. Reading the S67 bus taps instead:

```
MeasChan  6   strip 6 post-fader    -23.008 dBFS
MeasChan 33   MAIN L                -29.028
MeasChan 34   MAIN R                -29.028
MeasChan 35   AUX 1                -336.124      <- exact digital zero
```

`Chan006AuxOn001` = 0 and `Chan006AuxSend001` = 0.0. **The AUX 1 bus was exactly zero, so
the DAC had nothing to send and the loop was open inside the DSP** (S70-2). S69's gate 0
attributed the same flat reading to the rails being off; the rails were off, but this was
underneath it.

With the route asserted and proved on MeasChan 35, the loop closes:

| oscillator | slot 0 (51) | slot 2 (52) | **slot 3 (53)** | loop gain, slot 3 |
|---|---|---|---|---|
| off | −75.949 | −98.872 | −68.377 | — |
| −80 dBFS | −75.821 | −98.650 | **−41.245** | **+41.753 dB** |
| −70 | −75.842 | −98.979 | **−31.264** | **+41.750** |
| −60 | −75.966 | −98.651 | **−21.253** | **+41.750** |
| −50 | −75.839 | −98.547 | **−11.253** | **+41.751** |

Forty decibels of drive, the loop gain constant to 0.003 dB, and only one of the three
received codec lanes moving. **GATE 0 PASS**, and S69-1 answered in the same four rows.

**The loop gain sets the ceiling for the whole session.** +41.757 dB at MGN +27 dB puts the
ADC's full scale at the talkback XLR at **−18.63 dBu**, and at MGN 0 dB at **+8.36 dBu** =
2.02 V RMS. The AK4619's own full scale at MGN 0 dB is 2.83 Vpp (datasheet note *13), which
read as a differential swing is +2.2 dBu, so **there is about 6 dB of loss between J1 and
the codec's input pins** — 12 dB if that 2.83 Vpp is per pin rather than differential,
which the datasheet's "±2.83 Vpp" notation does not settle. Either way the sign is the same
and the margin below is taken on the smaller (6 dB) reading. The part's
analog pins take 3.3 Vpp each (datasheet §2050) with an absolute maximum of the lower of
AVDD+0.3 V and 4.3 V, so every tool in `s70lib` refuses an oscillator level above **−12
dBFS** and the refusal is asserted in code, not left to the operator.

## Gate 1 — the lever on analog

The dispatch's own witness, `05H := 0xB2` (MGN2L unchanged at +27 dB, MGN2R to 0 dB), at a
fixed oscillator level of −48.25 dBFS:

| | RmsResult | coherent fit |
|---|---|---|
| MGN2R +27 dB | −9.499 dBFS | +41.754 dB |
| MGN2R 0 dB | −36.493 dBFS | +14.771 dB |
| **drop** | **26.994 dB** | **26.984 dB** |

**PASS** (27.0 ± 0.2). All twelve codes at that one level, nothing rescaled between points:

| code | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| nominal | −6 | −3 | 0 | +3 | +6 | +9 | +12 | +15 | +18 | +21 | +24 | +27 |
| loop, dB | 8.753 | 11.751 | 14.770 | 17.770 | 20.768 | 23.768 | 26.765 | 29.765 | 32.765 | 35.759 | 38.752 | 41.754 |
| step | — | 2.998 | 3.019 | 3.000 | 2.998 | 2.999 | 2.997 | 3.001 | 3.000 | 2.994 | 2.993 | 3.002 |

Monotonic, every step within 0.019 dB of 3.00. **GATE 1 PASS.**

## S70-3 — the donor strip's compressor, and why T1 had to be run twice

The first T1 pass chose a non-clipping oscillator level *per code*, which is what the test
set asks for. Codes 0 and 1 came back **2.7 dB and 0.45 dB below the law**, with THD+N
jumping from −86 dB to −55.70 dB — and those two codes are the only ones whose level needs
the oscillator above −18 dBFS. It looked exactly like an analog overload: a sharp knee, the
lane pinning, the level rising 0.5 dB for every 2 dB of extra drive.

The discriminator is free, because the loop has a digital side. The same ladder read at
three points at once:

| oscillator | strip 6 post-fader | AUX 1 bus | talkback lane |
|---|---|---|---|
| −45 dBFS | −0.007 | +0.002 | −0.003 |
| −21 | −0.007 | +0.002 | −0.003 |
| −19 | −0.007 | +0.002 | −0.003 |
| **−17** | **−1.391** | **−1.381** | **−1.387** |
| **−15** | **−2.891** | **−2.881** | **−2.887** |
| **−13** | **−4.391** | **−4.381** | **−4.387** |
| **−12** | **−5.141** | **−5.131** | **−5.137** |

(deviation from the small-signal law, dB). **The strip's own post-fader block is already
down by the full amount** — the three columns agree to 0.01 dB — so nothing analog is
involved. `Chan006CompOn001` reads **1** out of boot + config, with a threshold near
−22 dBFS. `Chan006GateOn001` and `Chan006TubeOn001` are 0.

With `Chan006CompOn001` cleared, the same ladder is flat to **+0.007 dB** from −45 to
−12 dBFS. Every number in this report is from the bypassed stimulus; the compressed pass is
kept in `data/t3_knee.json` as the control.

Nothing in `s54lib`, `s69lib` or the test-set document bypasses the donor strip. S70's
`Rig.route()` now clears all three dynamics cells and refuses to run if they do not clear.

## T1 — the gain law

1 kHz, oscillator chosen per code so the lane peaks at −6.5 dBFS, donor dynamics bypassed.
"dev" is the departure from a perfect 3 dB ladder anchored at code 0.

| code | MGN, dB | osc, dBFS | lane, dBFS | peak, dBFS | loop gain, dB | dev, dB | step, dB | THD+N, dB | ADC FS at J1, dBu |
|---|---|---|---|---|---|---|---|---|---|
| 0 | −6 | −15.25 | −9.496 | −6.486 | **+8.757** | +0.000 | — | −67.54 | **+14.37** |
| 1 | −3 | −18.25 | −9.509 | −6.499 | +11.754 | −0.003 | +2.997 | −86.40 | +11.38 |
| 2 | 0 | −21.25 | −9.491 | −6.481 | +14.774 | +0.017 | +3.019 | −85.75 | +8.36 |
| 3 | +3 | −24.25 | −9.491 | −6.481 | +17.773 | +0.016 | +3.000 | −83.73 | +5.36 |
| 4 | +6 | −27.25 | −9.493 | −6.483 | +20.772 | +0.015 | +2.998 | −81.11 | +2.36 |
| 5 | +9 | −30.25 | −9.483 | −6.473 | +23.770 | +0.013 | +2.999 | −78.75 | −0.64 |
| 6 | +12 | −33.25 | −9.496 | −6.486 | +26.767 | +0.011 | +2.997 | −75.61 | −3.64 |
| 7 | +15 | −36.25 | −9.496 | −6.486 | +29.768 | +0.011 | +3.001 | −73.10 | −6.64 |
| 8 | +18 | −39.25 | −9.485 | −6.475 | +32.768 | +0.012 | +3.000 | −70.02 | −9.64 |
| 9 | +21 | −42.25 | −9.501 | −6.491 | +35.762 | +0.005 | +2.994 | −67.00 | −12.63 |
| 10 | +24 | −45.25 | −9.509 | −6.499 | +38.755 | −0.002 | +2.993 | −64.01 | −15.62 |
| 11 | +27 | −48.25 | −9.507 | −6.497 | **+41.757** | +0.000 | +3.002 | −61.07 | **−18.63** |

Largest step error **+0.019 dB**, largest departure from nominal **0.017 dB**, span
**33.000 dB** over eleven steps, monotonic. THD+N falls monotonically with gain because the
figure is loop-limited — at +27 dB the lane sits 33 dB above the source's own noise, not
above the preamp's.

**Level independence** (test-set T1), MGN 0 dB, three drives 20 dB apart: +14.7707 /
+14.7710 / +14.7710 dB — **spread 0.0003 dB**.

**ADC FS at the talkback XLR** is the T1 column above, derived as `DAC FS − loop gain at
that code` (S57-R; the loop gain is never subtracted twice). The DAC's +23.13 dBu is PW's
DMM reading of 2026-09-16 and is inherited, not re-measured.

### ADC2 Rch digital volume (09H), spot-checked

| nominal | code | measured | error |
|---|---|---|---|
| +6.0 dB | `0x24` | +6.021 dB | **+0.021** |
| −6.0 dB | `0x3C` | −6.021 dB | **−0.021** |
| −20.0 dB | `0x58` | −20.062 dB | **−0.062** |
| restore 0.0 dB | `0x30` | −0.000 dB | 0.000 |

Exact, as expected of a digital volume, and the sign convention of Tables 11/14 (higher
code = quieter) is confirmed a third independent way.

## T2 — frequency response, re 1 kHz

Lane held at about −20 dBFS, at minimum and maximum gain. This is the **loop's** response —
the AUX 1 DAC and output stage, PW's cable and the talkback input together — not the
talkback input alone.

| Hz | 20 | 50 | 100 | 200 | 500 | 1 k | 2 k | 5 k | 10 k | 15 k | 20 k |
|---|---|---|---|---|---|---|---|---|---|---|---|
| MGN −6 dB | **−0.67** | −0.10 | −0.01 | +0.02 | +0.02 | 0.00 | −0.00 | −0.00 | +0.08 | +0.01 | −0.06 |
| MGN +27 dB | **−0.92** | −0.10 | −0.01 | +0.02 | +0.02 | 0.00 | −0.00 | −0.00 | +0.07 | 0.00 | −0.08 |

Flat within **±0.10 dB from 50 Hz to 20 kHz** at both gains. **20 Hz is flagged**: −0.67 dB
at minimum gain and −0.92 dB at maximum, outside the ±0.5 dB path limit. The test set
accepts up to 2.5 dB down at 20 Hz at maximum gain, so the maximum-gain point is inside its
allowance and the minimum-gain point is the one outside the rule as written. The 0.25 dB
difference between the two gains is the only gain-dependent term anywhere in the response,
which points at the codec's input coupling working against a gain-dependent input impedance
rather than at anything in the loop; **both ADC HPFs are off** in the init image (`0DH`
bit 2 / bit 1 = 0), so none of this is the codec's digital filter.

## T3 — THD+N vs level

| MGN | lane, dBFS | input, dBu | THD+N, dB | THD+N, % | NoiseResult, dBFS |
|---|---|---|---|---|---|
| 0 dB | −22.979 | −14.62 | −73.97 | 0.0200 | −96.944 |
| 0 dB | −12.991 | −4.63 | −82.43 | 0.0076 | −95.423 |
| 0 dB | −8.990 | −0.63 | −86.00 | 0.0050 | −94.992 |
| 0 dB | −5.980 | +2.38 | **−87.89** | **0.0040** | −93.870 |
| +27 dB | −22.974 | −41.60 | −23.68 | 6.5494 | −46.650 |
| +27 dB | −13.006 | −31.63 | −50.21 | 0.3088 | −63.214 |
| +27 dB | −9.006 | −27.63 | −60.94 | 0.0898 | −69.944 |
| +27 dB | −5.996 | −24.62 | **−64.42** | **0.0601** | −70.413 |

The minimum-gain row is a genuine path figure: **−87.89 dB = 0.0040 %** at −3 dBFS.

The maximum-gain rows are **loop-limited and are not the path's distortion** — exactly the
case the test set already rules on. At +27 dB the source has to be dropped to −44.75 dBFS
at the DAC, so the AUX 1 output stage's own noise arrives through 42 dB of gain and sets
the figure; T4 below shows the input-referred noise is flat at −84 dBu across all twelve
codes, which is the same statement. The real maximum-gain figure needs the harness's
switchable pad or a low-noise external generator, and until then the maximum-gain row is
quoted as loop-limited.

## T4 — noise floor per MGN2R code

Tone off. Taken twice: once with the loop cable still on J1, where the talkback XLR is
terminated by the AUX 1 output stage, and once with **PW's 150 Ω shunt across J1**, which
arrived during the session. Noise converts as lane dBFS + 3.01 + the ADC full scale at that
code (S57-O).

| code | MGN, dB | loop, dB | ADC FS, dBu | lane, dBFS (loop) | input-ref, dBu (loop) | lane, dBFS (**150 Ω**) | input-ref, dBu (**150 Ω**) |
|---|---|---|---|---|---|---|---|
| 0 | −6 | +8.757 | +14.37 | −100.185 | −82.80 | **−106.897** | **−89.51** |
| 1 | −3 | +11.754 | +11.38 | −97.999 | −83.61 | −106.233 | −91.85 |
| 2 | 0 | +14.774 | +8.36 | −95.218 | −83.85 | −105.807 | −94.44 |
| 3 | +3 | +17.773 | +5.36 | −92.159 | −83.79 | −104.880 | −96.51 |
| 4 | +6 | +20.772 | +2.36 | −89.575 | −84.21 | −103.966 | −98.60 |
| 5 | +9 | +23.770 | −0.64 | −86.421 | −84.05 | −102.238 | −99.87 |
| 6 | +12 | +26.767 | −3.64 | −83.628 | −84.26 | −100.357 | −100.98 |
| 7 | +15 | +29.768 | −6.64 | −80.195 | −83.82 | −98.240 | −101.87 |
| 8 | +18 | +32.768 | −9.64 | −77.886 | −84.51 | −95.695 | −102.32 |
| 9 | +21 | +35.762 | −12.63 | −74.159 | −83.78 | −92.921 | −102.54 |
| 10 | +24 | +38.755 | −15.62 | −71.571 | −84.19 | −90.483 | −103.10 |
| 11 | +27 | +41.757 | −18.63 | −68.656 | −84.27 | **−87.766** | **−103.38** |

**The two columns say two different things, and the difference is the whole point of the
shunt.** With the cable on, the input-referred figure is *flat at −84 dBu across all twelve
codes* — no trend, spread 1.7 dB — which is the signature of a measurement limited by its
source and not by the preamp. It is confirmed from outside this instrument: PW's external
meter read the AUX 1 **output** at −84.55 dBu 20 Hz–20 kHz (test-set reference table,
2026-09-16). With the 150 Ω on, the figure *falls monotonically* from −89.51 to
−103.38 dBu and converges: the last three steps are 0.56, 0.28 dB. That convergence is the
preamp's own noise arriving, and it means **−103.4 dBu is the talkback preamp's EIN, not
just an upper bound** — the ADC's contribution is still visible at the bottom codes and has
essentially stopped mattering at the top.

The shunt announced itself exactly as expected: the lane floor at +27 dB dropped from
−68.559 to −87.526 dBFS, 19 dB, in one ten-second watcher tick.

## T4b — EIN, both weightings, from the capture

16,384 samples off the S62 bulk path, tone off, analysed 20 Hz–20 kHz unweighted and IEC
A-weighted with the node's raw DC–24 kHz figure beside them. **Source: 150 Ω across J1.**

| | MGN **+27 dB** (ADC FS −18.63 dBu) | MGN −6 dB (ADC FS +14.37 dBu) |
|---|---|---|
| total, DC–24 kHz | −87.64 dBFS → −103.26 dBu | −107.02 dBFS → −89.64 dBu |
| **20 Hz–20 kHz unweighted** | −88.30 dBFS → **−103.92 dBu** | −108.02 dBFS → −90.64 dBu |
| **20 Hz–20 kHz A-weighted** | −90.40 dBFS → **−106.02 dBu** | −110.26 dBFS → −92.88 dBu |

> **EIN of the talkback input, 150 Ω source, maximum gain (+27 dB):
> −103.92 dBu unweighted (20 Hz–20 kHz), −106.02 dBu A-weighted.**

For scale, the same measurement on a D24 mic preamp (MIC 5, S60/S61) is −127.2 dBu /
−130.5 dBu(A). **The talkback input is about 23 dB noisier than a mic channel**, which is
what a codec's on-chip mic amp is, not a defect — but it is a number the product needs to
know before anyone specifies a talkback mic for it. Flagged, not interpreted further.

The same battery with the loop cable as the source is kept in `data/t4_loop.json` and is
the reference figure the test set allows when no shunt exists: −84.93 dBu unweighted /
−87.27 dBu(A) at +27 dB, agreeing with PW's meter on the AUX 1 output to 0.4 dB and 0.3 dB.

## T5 — polarity, and T8 — latency

Both come out of one scan, because a single frequency cannot separate them: the loop is
milliseconds long and its phase has turned through whole revolutions by 1 kHz. Stepping
50 Hz at a time from 500 to 1500 Hz keeps every step under 180° for any loop shorter than
10 ms, so the phase unwraps and the line can be fitted.

* slope **−0.817023 °/Hz**, maximum residual **0.19°** over 21 points
* **T8 latency = 2.2695 ms = 108.94 samples at 48 kHz** — the whole loop: TEST_OSC → strip
  6 → AUX 1 bus → chip 1 → chip 2 fabric → SPORT TX → DAC → the cable → the talkback input
  → ADC → SPORT RX → the tap. It is not the talkback input's own latency.
* phase extrapolated to DC = **+181.56°** → **T5 POLARITY: INVERTED**

**Inverted is the expected answer and it is a design finding, not a fault of this unit.**
J1 pin 2 goes through C4 to the AK4619's IN4**N** and pin 3 through C11 to IN4**P**, on
record since 2026-09-11. The 1.56° residual over a 2.27 ms loop is the fit's own error.
There is **no polarity bit anywhere in the AK4619** for the ADC path, so the fix is either
the TALKBACK node (a sign in the DSP) or a board mod — hub/PW call, not this session's.

## The register image in use

`StartAK4619()`'s image, unchanged all session except MGN2R and the 09H spot-check, both
restored:

```
00H 37   01H AC   02H 10   03H 00   04H BB   05H BB   06H..09H 30
0AH 00   0BH 00   0DH 00   0EH..11H 18   12H 04   13H 05   14H 0A
```

TDM256 I2S compatible, 32-bit slots, BICK 256 fs, all four ADC inputs differential, both
ADC HPFs **off**, all four mic amps at **+27 dB**. S69's decode stands; this session adds
that the format is not merely self-consistent but correct in the loop, since a 41.757 dB
loop gain measured to 0.003 dB over 40 dB of drive cannot come through a mis-framed SPORT.

## Findings

**S70-1 🟢 The talkback XLR is ADC2 Rch = TDM slot 3 = `C1_XIN_CODEC_04`, and the graph's
`C1_XIN_CODEC_01` "Codec ADC 1 (TB XLR)" is misnamed.** S69 proved the codec-channel → slot
mapping; this proves which XLR feeds which codec channel, which was the open half. With the
loop cable on J1 and the rails up, slot 3 follows the oscillator over 40 dB at +41.75 dB
constant to 0.003 dB, and slots 0 and 2 do not move at all. The netlist walk (mx26
`docs/d24-analog-paths.md`, `docs/d24-signals-index.md` I4: J1 → IN4 → MIC Gain Amp 2 Rch →
ADC2 Rch) is therefore right and the `dsp.csv` naming is wrong. **Consequences, all for the
hub's defs pass and none taken here:** the talkback mic currently lands on the
codec-aux-in path into the main mix (`C1_XS_XFER_CODEC_AUX_R`); `C1_TALK_01` is fed from
slot 0, which is ADC1 Lch and carries the aux input; and `Talk[1-1]Gain[1-1]` reaches a DSP
multiply in a node that is not in the talkback signal path. Slot 1 (ADC1 Rch) is still not
received at all — `cs_mask 0x000D` — so one of the four codec ADC channels never reaches
the DSP whatever the naming is fixed to.

**S70-2 🔴 A fresh boot + config leaves the donor strip unrouted, and the standard test set
has no gate that catches it.** `Chan006AuxOn001` = 0 and `Chan006AuxSend001` = 0.0 after
`dsp4_config.py --product d24`, so the AUX 1 bus block is **exact digital zero** and the
DAC sends nothing. Every reading downstream is then a perfectly plausible tone-off floor:
S69's gate 0 read the same flatness and attributed it to the rails. The rails were indeed
off, but this was underneath and would have survived raising them — as it did, for the
first gate 0 of this session. **Fix applied here:** `s70lib.Rig.route()` asserts the route
and `prove_route()` requires the AUX 1 bus to read the oscillator level within 0.2 dB
before anything else runs. Proposed for the test set: *the stimulus path is proved on a
digital tap before any analog measurement is taken.*

**S70-3 🔴 The donor strip's COMPRESSOR is on out of boot + config and silently compresses
the stimulus above about −22 dBFS.** `Chan006CompOn001` = 1 (`GateOn` and `TubeOn` are 0).
Above the threshold the loop reads as a hard analog overload — a sharp knee at oscillator
−18 dBFS, the lane pinning, THD+N leaping to a level-independent −55.70 dB, and the two
lowest gain codes 2.7 dB and 0.45 dB off their law. It is not analog: strip 6's own
post-fader block, the AUX 1 bus and the talkback lane are down by −1.391 / −1.381 / −1.387
dB at the same drive, agreeing to 0.01 dB, so the loss is entirely upstream of the DAC.
With the compressor cleared the same ladder is flat to +0.007 dB over 33 dB. **Nothing in
`s54lib`, `s55_run`, `s63lib`, `s69lib` or the test-set document bypasses the donor
strip's dynamics**, so every measurement any of them took at an oscillator level above
about −20 dBFS is suspect and should be re-read against this. Proposed for the test set:
*the donor strip is part of the instrument; its gate, compressor and tube are bypassed and
the bypass is verified, not assumed.*

**S70-4 🟢 The AK4619 mic-amp gain law is exact.** Twelve MGN2R codes, −6 … +27 dB: steps
2.993 … 3.019 dB, largest error from 3.000 dB **0.019 dB**, largest departure from the
nominal ladder **0.017 dB**, monotonic, 33.000 dB total span, level-independent to
**0.0003 dB** over 20 dB of drive. The ADC digital volume (09H) is exact to 0.021 dB at
±6 dB and 0.062 dB at −20 dB. Both levers are good enough that a combined 0.5 dB law needs
no per-unit correction table — unlike the 595 mic pres, whose trim table exists precisely
because their steps are not this good.

**S70-5 🟡 The talkback input's EIN is −103.9 dBu, about 23 dB noisier than a D24 mic
channel, and the loop cable cannot measure it at all.** With the 150 Ω shunt: −103.92 dBu
20 Hz–20 kHz unweighted / −106.02 dBu A-weighted at +27 dB, converging (the last three
codes move 0.56 and 0.28 dB), against −127.2 / −130.5 dBu for MIC 5. That is what an
on-chip codec mic amp is and it is not a defect, but it is the number that decides what
talkback mic the product can carry, and it should reach the product spec rather than being
discovered later. **The same measurement through the loop cable reads −84.93 dBu and is
19 dB wrong**, flat across all twelve gain codes because it is measuring the AUX 1 output
stage's own noise — confirmed against PW's external meter on that output (−84.55 dBu) to
0.4 dB. Any input EIN taken on this bench without the shunt is a measurement of the source.
The same limit sets T3's maximum-gain row, which is still loop-limited because it needs a
tone and therefore the cable.

**S70-6 🟢 T5 confirms the talkback input is INVERTED, by the wiring, as designed-in.**
Phase extrapolated to DC over a 21-point unwrapped scan = +181.56°, against a fitted loop
latency of 2.2695 ms (108.94 samples, maximum residual 0.19°). J1 pin 2 → C4 → IN4N, pin 3
→ C11 → IN4P. **There is no polarity bit in the AK4619's ADC path**, so this cannot be
fixed in the codec: it is a sign in the TALKBACK node or a board mod. Hub/PW call.

**S70-7 🟡 The 595 chain was found carrying latched DSP SPI traffic again, with phantom
power set on three registers.** Pass-1 MISO read `00 E0 FE 00 …` — `0xFE` decodes as
unmuted, phantom **ON**, gain 63. This is the S48-7 mechanism (every DSP transaction shifts
through the chain; a CS_M rising edge latches whatever is in it) and it means the chain's
state after any session that clocked the DSP link and then touched CS_M is **undefined, and
undefined includes phantom on at full gain**. The session wrote the SAFE image and left it
there rather than restoring what it found; see below. Worth a standing rule: *the chain is
asserted after the last DSP boot of a session, not before it.*

## Implications for `Talk[1-1]Gain[1-1]` — a proposal for the hub's defs pass

The cell is still the placeholder S69 described: `0=0/127=40/[Lin]`, MxDatS 65, ramp
`GainFast`, reaching `_talk_gain_C1_TALK_01`. Two things are now measured that were not.

**First, the hardware law, and it is good.** The analog stage is MGN2R[3:0]: twelve steps,
−6 … +27 dB, measured 3.00 dB apart to 0.019 dB. The digital trim is VOLAD2R[7:0]:
+24.0 … −103.0 dB in 0.5 dB steps plus mute at `0xFF`, measured exact to 0.021 dB at ±6 dB.
The test set's ruled mic-gain shape — hardware steps at or **below** the target plus a trim
that is always positive, so the analog stage never carries more gain than asked for —
applies directly:

> `MGN2R` = largest 3 dB step ≤ target; `VOLAD2R` = target − MGN2R, 0 … +2.5 dB in 0.5 dB.

Measured accuracy of that combined law over −6 … +27 dB is about **±0.1 dB** with no
per-unit table, because both levers are within 0.02 dB of nominal and the errors do not
accumulate (the analog step is re-chosen at every target).

**Second, the range that is worth publishing.** Only MGN2R is ahead of the ADC, so only
MGN2R buys headroom or improves the noise; VOLAD2R's positive range (up to +24 dB) adds
gain *after* the converter and buys nothing but a smaller number on the meter. The cell
should publish **−6 … +27 dB** (the analog span) in 0.5 dB, not the placeholder's 0 … 40.
If a "gain" above +27 dB is wanted for the operator, it belongs in the DSP node where
`_talk_gain_` already is, and should be labelled as such.

**Third, and this is the part that is not a law question at all: S70-1 says the cell is on
the wrong node.** `Talk[1-1]Gain[1-1]` reaches `C1_TALK_01`, which is fed from slot 0 =
ADC1 Lch — not the talkback. Whatever law lands, the cell has to address the codec channel
the talkback mic is actually on, and the `dsp.csv` naming has to be fixed first. Sequence
proposed to the hub: fix the `C1_XIN_CODEC_0n` names and the TALKBACK feed → then decide
whether `Talk Gain` addresses MGN2R, VOLAD2R or the combined law → then the DSP
`_talk_gain_` becomes a trim or goes away. None of it is done here.

## What is still open

**Nothing from the dispatch's gate list.** The 150 Ω arrived during the session and the
noise set was taken twice, so T4/T4b are the real figures and not the reference ones.

**T6, T6b and T7 were not in this dispatch** and are not run: T6 needs the DSP strip mute
on a talkback strip that does not yet exist as such, T6b is a mic-input phantom test and
the talkback is not on the 595 chain at all, and T7 needs a second talkback-adjacent
channel to measure against.

**The maximum-gain THD+N row** stays loop-limited until the harness pad or a low-noise
generator exists — the standing test-set position, unchanged.

## State the unit was left in

AN_EN went **LOW FIRST** (`sudo pinctrl set 26 op dl`, verified `lo`) before anything else
was touched, per the mandate. Then, in this order:

* **The codec** back to its init image: MGN2R → code 11 (+27 dB, the value
  `StartAK4619()` leaves), then `codec4619.py --reinit` (register `0xFF` → `StartAK4619()`),
  both acknowledged. The three received codec lanes were read back afterwards to confirm
  the restore, and **that reading was lost to output truncation** — it cannot be retaken,
  because the shipping pair carries no measurement tap. S69 proved `--reinit` restores all
  three slots to within 0.05 dB; this session exercised only `05H` and `09H` and set both
  back explicitly before the re-init, so the risk is small, but the verification is a
  claim from S69's evidence rather than this session's and is flagged as such.
* **The SHIPPING pair restored**: chip 1 `87126eb6d05c8acbda900b3b51338f3f`, chip 2
  `3a9c950d3551b6c5d7ff58925a47ec81` — the S67 shipping hashes, rebuilt here from `main`
  at `d09df2a2` with a plain `./build.sh` and verified byte-identical on both the desk and
  the unit. Staged at `/home/app/s70ship` (it was not on the unit at all before this
  session; S69 left the S69 test pair booted). Booted and configured twice, both chips
  `BOOT_STAGE 7`, `CHIP_ID` 1 / 2 verified. Every bench change this session made to the
  graph — the AUX 1 route, the donor strip's dynamics bypass — went with it.
* **The 595 SAFE image written LAST**, after the final DSP boot rather than before it, per
  S70-7: `[0x01] × 24 + [0x00]`, **VERIFIED 200/200**. Pass-1 MISO read back the same
  latched DSP traffic it did at entry (`00 E0 FE 00 …`), which is the S48-7 mechanism doing
  it again across this session's boots and is the reason the SAFE image, and not the found
  bytes, is what the unit was left holding. **This is a deliberate departure from
  "as found"**: the found bytes decode as phantom ON at gain 63 on three registers, which
  is not a state to restore.
* **GPIO 27 (CS_M)** back to `ip pu | hi`, exactly as found (the chain write leaves it
  `op dh`).
* **GPIO 26 (AN_EN)** `op pd | lo`, as found.
* **TEST_OSC** off, MeasChan 0 — and then replaced wholesale by the shipping pair anyway.
* **`matrix-app` active, all three MCUs verified** — `MCU boot verified: H1S1 / H1S3 /
  H1S4`, read from the whole of `/home/app/logs/log` (the app rewrites that file on every
  start, so "lines since a mark" is empty and misleading).

**The MCU verify race is worse than the record says, and this session measured it.** Six
restarts were needed to land on 3 of 3, and the sequence was **1, 1, 3, 3, 0, 3** — so
`0 of 3` happens, which findings' "~1 restart in 4 verifies 1 of 3" does not cover, and
H1S3 is **not** always the survivor (it failed alongside the other two on the 0-of-3
restart). Nothing was flashed and nothing was changed between restarts; this is the
standing app defect (mx26 B13), quantified a little further.

## Appendix — what was run

`MW/D24/DSP/s70/tools/`, all staged at `/home/app/s70` on the unit:

| tool | what it is |
|---|---|
| `s70lib.py` | the rig: the measured lane, the asserted route with the donor's dynamics bypassed, the oscillator ceiling, the dBFS ↔ dBu conversions |
| `s70_gate0.py` | gate 0, the three codec return lanes against the oscillator |
| `s70_txdiag.py` | the transmit-side walk that found S70-2 |
| `s70_route.py` | the route asserted, then gate 0 again |
| `s70_g1_t1.py` | gate 1, the first T1, level independence, the digital-volume spot check |
| `s70_t3.py` | the knee ladder and T3 (the compressed pass, kept as the control) |
| `s70_kneesrc.py` | the three-tap read that proved S70-3 digital |
| `s70_set.py` | T1, T2, T3, T5, T8 on the bypassed stimulus — the report's numbers |
| `s70_t4.py` | T4 and T4b; takes the source as its argument (`loop` / `150r`) |
| `s70_watch.py` | waits for the lane floor to drop when the 150 Ω is fitted |
| `s70_handback.py` | the hand-back, in the mandate's order |

**One tool bug, found by its own output.** `s70_t4.py` takes the source as `sys.argv[1]`,
and `sys.argv` does not survive the `s52lib` → `dsp4_scope` import (that module parses it
at import time — the same trap `dsp4_apply_strip.py` carries, findings S48-3). So the
150 Ω run wrote itself out as `t4_loop.json` and overwrote the cable run's file on the
unit. Both data sets survive because the cable run had already been copied to the repo;
the 150 Ω file is relabelled by hand in `data/t4_150r.json` with a note saying so. The
pattern any new bench tool must use is `_argv = list(sys.argv)` **before** the imports,
as `dsp4_s42_align.py` and `s63lib` already do.

`MW/D24/DSP/s70/data/`: `gate0.json` (rails up, route still off), `gate0b.json` (the loop
closed), `g1_t1.json` (gate 1 + the compressed first T1), `t3_knee.json` (the knee, the
control), `set.json` (T1/T2/T3/T5/T8, the report's numbers), `t4_loop.json` and
`t4_150r.json` (the two noise sets), `cap_loop_code0/11.json` and `cap_150r_code0/11.json`
(the four 16 k captures behind T4b), `shunt_seen.json` (the watcher's record of the floor
dropping when the 150 Ω went on), `s70.jsonl` (every codec write, in order).
