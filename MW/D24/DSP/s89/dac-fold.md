provenance: AI-drafted 2026-09-21 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S89 — the shipping DSP pair folds its DAC output

Session 89, 2026-09-21, unit MW-D24-2 rev C. Hub dispatch `tasks.md` 2026-09-21
13:34Z.

## Headline

**S88-1's fold is named: it needs `DSP4_SIMD_DYN` and `DSP4_DYN_LUT` ON TOGETHER,
and neither one alone.** The bisect is clean in both directions — see S89-3, which
is the answer to the dispatch's gate 2 and the reason the S82-signed configuration
is not shippable as it stands. The *mechanism* is not yet named: every digital
probe on the part is clean, so the corruption is on the converter-transmit/analog
side of the Monitor and AUX outputs and is owed to the next session.

Two further defects were found on the way and are independent of it: **S89-1**, an
intermittent inter-chip sign-bit loss that hits roughly one boot in seven on every
build measured, now gated and mitigated; and **S89-2**, two codec output slots that
no gather entry ever writes.

## S89-1 — the inter-chip link loses the sign bit on about one boot in seven

**This is NOT S88-1's cause** (see S89-3) — it is a second, independent defect found
while chasing it, and it is build-independent. On an affected boot chip 2 receives
every inter-chip word with **bit 31 forced to zero**.

    received = sent & 0x7FFFFFFF

A negative Q4.28 sample of −0.211 arrives as **+7.789**. The waveform's negative
half is folded up to just under the +8.0 rail, which is exactly the wrap-around
PW's scope saw, at the right fundamental level once the large DC term is lost in
the AC-coupled XLR output.

### The measurement

Measured on the shipping-kernel pair (`0xCF45FF10 / 0xE3018E6F`, the S82-signed
switches plus `DSP4_TEST_NODES=1` for the instrument), 1 kHz TEST_OSC at
−13.50 dBFS into strip 5, routed at unity to AUX 1, all strip dynamics cleared:

| tap | reading | fold metric |
|---|---|---|
| strip 5 post-fader (TEST_MEAS) | −16.51 dBFS, THD 0.00037 % | clean |
| chip 1 AUX 1 bus block `_buf_C1_BUS_AUX_01` | −13.50 dBFS, smooth sine | **−0.17 dB** |
| chip 1 inter-chip TX DMA ring, entry 7 | 7 of 16 words carry bit 31 | correct |
| chip 2 raw IC RX slot `_rx_ic_slot_C2_RECV_AUX_01` | 0 of 16 words carry bit 31 | **+17.63 dB** |
| chip 2 `_blk_C2_MIX_AUX_01` | sine + 8.0 offset, wrapping the rail | **+17.63 dB** |
| chip 2 `_tx_out_slot_C2_AUX_OUT_01` | pinned at the limiter ceiling, −0.47 dBFS | **+17.63 dB** |

Word-for-word: `0xFC9E50A0` leaves chip 1 and arrives as `0x7C9E50A0`;
`0xFD513434` → `0x7D513434`; `0xFF1FF0F1` → `0x7F1FF0F1`. Positive words
(`0x00E00F0F`, `0x014B47CA`, `0x02AECAD4`) arrive **unchanged**, so it is an
`AND 0x7FFFFFFF`, not a shift and not an XOR — S39-4's one-bit-early capture
(`sample >>> 1`) is ruled out arithmetically, and so is offset-binary conversion.

### The fold metric

A 1 kHz tone at 48 kHz moves at most `2*pi*1000/48000 = 0.1309` of its own peak
between adjacent samples, so

    fold = 20*log10( max|x[n]-x[n-1]| / (0.1309 * max|x|) )

reads about 0 dB on a clean tone and positive on anything that jumps further than
the tone can. Clean ≤ 1 dB, folded ≥ 10 dB, per the dispatch. Tool:
`tools/pi/s89_blk.py` (staged; see Files).

### The control

The same measurement on the diagnostic pair `s51_119ea9d9`
(`0xCF45FF10 / 0xC3010244`) is clean end to end: chip 1's bus block fold
**−0.17 dB**, chip 2's raw IC RX slot fold **−0.02 dB** with the negatives intact
(`FCE03664 FCBBD030 FCA5B8AC ...`), chip 2's AUX 1 TX slot identical to it.

### What it is not

The inter-chip SPORT registers were read off both parts and are **byte-identical**:

    chip 1 IC TX (half B)  CTL 0xC20031F1  MCTL 0x00000F15  CS0 0xFFFF/0xFFFF/0x01FF
    chip 2 IC RX (half A)  CTL 0x000031F1  MCTL 0x00000F15  CS0 0xFFFF/0xFFFF/0x01FF

So it is not `SLEN` (31 = 32-bit words on both), not `MFD` (1 on every
inter-chip lane on both), not the channel-select masks, and not `MCPDE`/`WSIZE`.
It is also not the CPLD: both pairs ran on the same flashed shipping bitstream
`83b3cc22` in the same session.

### It is a per-boot race, not a build difference

Booting the SAME image repeatedly settles it. On the shipping-kernel pair,
**2 of 10 boots came up folded**; across every boot taken today, **5 of 34**. The
diagnostic pair `s51_119ea9d9` folds too — **1 of 10** — so no build is immune and
the S82-signed switches are not implicated in this one. When it folds, **all three
inter-chip lanes fold together**, not one.

A folded boot was then caught deliberately and its SPORT registers read on that very
boot: **identical to a clean boot**. (The single difference, chip-1 SPORT1 `CTL`
`0x820031F1` against `0xC20031F1` on its neighbours, is bit 30 — read-only FIFO
status — and it appeared on a lane that folded *alongside* SPORT0, which read
normal.) So the configuration is right and the *lock* is wrong: the receive framing
settles one bit period out at enable time and stays there until the next boot.

`dma_config.c::enable_region` sets `SPENPRI` on each half in turn, with the CPLD's
BCLK and FS already free-running and nothing synchronising the enable to a frame
boundary. That is the line the fix has to address, and a firmware fix there touches
clock discipline, so it is design-grade work for its own dispatch.

### The mitigation, proved

`tools/pi/s89_signbit.py` scores the link with **no stimulus, no routing and no
strip setup** — the codec return lanes and the MAIN L/R lanes are live from
converter noise and mic-lane noise on any booted pair, and noise crosses zero, so a
healthy link shows about half the words negative and a folded one shows none. Its
**exit code is the gate** (0 clean, 1 folded, 2 nothing to judge on).

`tools/pi/dsp4_boot_linked.sh` boots and refuses to hand the pair back until that
gate passes. **Proved over 20 runs: 20/20 verified clean, with the retry firing
twice and recovering on the second attempt both times.** Nothing in the SPORT
registers differs on a bad boot, so looking at the data is the only way to know —
an unchecked boot is a 10–20 % chance of silently folded audio.

## S89-2 — two-channel codec outputs drive only their left slot

Found while setting up the Monitor jack measurement. The chip-2 gather table has
one entry per output node, but `C2_MON_OUT` and `C2_CODEC_AUX_OUT` each declare
`slot_count=2`. `_c2_tx_off` steps 256 → 258, so **codec TDM slots 1 and 3 are
gathered by nobody**. Read off the TX DMA ring:

    codec slot 0  MON L        FAEC2A98 FE57F4E8 FC1A99C0 ...  distinct 8
    codec slot 1  MON R        00000000 00000000 00000000 ...  distinct 1
    codec slot 2  CODEC_AUX L  FAEC2A98 FE57F4E8 FC1A99C0 ...  distinct 8
    codec slot 3  CODEC_AUX R  00000000 00000000 00000000 ...  distinct 1

Today's tree has the same `_c2_tx_ptrs[24]` and the same `r7 = 24` loop count, so
this is live in the shipping build, not an artefact of the old diagnostic pair.
**Monitor R and Codec Aux R are not driven at all** — a silent reading at either
pin is untestable, not dead.

## S89-3 — THE FOLD: `DSP4_SIMD_DYN` + `DSP4_DYN_LUT`, necessary and sufficient

The dispatch's gate 2, answered in both directions. Metric is the cable-loop THD
row (below): oscillator into strip 20 at −12.00 dBFS, out through MAIN → Monitor L
→ the loop cable → MIC 6, read coherently at strip 6's post-fader tap. Every arm is
a `DSP4_TEST_NODES=1` build of this tree, booted through the S89-1 link gate so a
folded link cannot be mistaken for this defect, and every arm returned the **same
level** (−41.8 to −42.0 dBFS), so the loop was live and identical throughout.

| arm | SIMD_DYN | DYN_LUT | loop THD+N | |
|---|---|---|---|---|
| shipping switches | 1 | 1 | **59.74 %** | folded |
| `DSP4_SIMD_DYN=0` | 0 | 1 | 0.354 % | **cured** |
| `DSP4_STRIP_FUSED=0` | 1 | 1 | 58.11 % | not cured |
| `DSP4_DYN_LUT=0` | 1 | 0 | 0.359 % | **cured** |
| `DSP4_GATE_LINTHR=0` | 1 | 1 | 69.64 % | not cured |
| all four off (control) | 0 | 0 | 0.360 % | clean |

And the converse, from the all-off base:

| arm | SIMD_DYN | DYN_LUT | loop THD+N | |
|---|---|---|---|---|
| base + SIMD_DYN only | 1 | 0 | 0.364 % | clean |
| base + DYN_LUT only | 0 | 1 | 0.352 % | clean |
| **base + both** | **1** | **1** | **58.16 %** | **folded** |

**Necessary and sufficient, and only in combination.** 0.36 % against 58–70 % is a
44 dB separation, so nothing here is marginal. This reproduces S88-1 exactly: the
shipping pair carries both switches and folded at the AUX 1 XLR; the `s51`
diagnostic pair carries neither and was clean at the same XLR.

The code path the pair names is the SIMD dynamics kernel's table branch —
`LUTGAIN_SIMD` in `src/lib/dyn_lut.h`, reached from `dyn_simd_fx.asm`'s
`.cpb_lut_lp` loop (and from `lib2/lim_simd_fx.asm`), which exists only when both
switches are set. Worth noting for whoever picks this up: `COMPGAIN_SIMD`'s inlined
text is checked against the called routine by
`tools/dsp/dyn_simd_inline_check.py`; **`LUTGAIN_SIMD` has no equivalent check**,
and its register contract ("clobbers r0–r5, r7, i0, i1", preserving r6 and r8–r15)
is asserted in a comment and nowhere verified.

### What the mechanism is NOT — every digital probe came back clean

This is the part that is owed, and these are the arms already eliminated, so the
next session does not repeat them:

- **The compressor kernel is not distorting.** Injected digitally into strip 20 with
  `CompOn=1` and measured at that strip's own post-fader tap, the folding arm and
  the clean arm agree to three decimal places: 0.15985 % against 0.15952 % at
  −12 dBFS, and 0.00008 % / 0.00009 % / 0.00020 % against 0.00008 % / 0.00007 % /
  0.00023 % at −30, −42 and −54 dBFS. No level shows a difference.
- **It is not a dropped-block or load problem.** Both arms run the full 3000
  blocks/s with a **zero** `BLK_OVERRUN` delta on both chips with the loop live.
- **It is not S89-1.** Every arm was booted through the link gate and verified.
- **It is not the digital signal reaching the DAC.** `_tx_out_slot_C2_MON_OUT`
  carries the right level on the folding arm, and on a clean-link boot reads a
  textbook smooth sine (fold metric −0.16 dB).
- **It is not the instrument's strip pairing.** Moving the injector from strip 5
  (the return strip's SIMD pair) to strip 20 (a different pair) changes nothing:
  59.74 % against 59.64 %.

So the corruption is downstream of the digital output slot and upstream of the
return strip's tap — the converter-transmit path, the codec, or the receive lane —
and it is switched deterministically by two kernel flags that have no business
reaching it. That contradiction is the next session's thread, and it wants a scope
on the codec's own pins rather than another host-side probe. The spectrum is the
clue: harmonics 2, 4, 5, 7, 8 and 10 all sit at −11 to −12.6 dBc while 3, 6 and 9
are absent at −79 dBc, with spurs at 11, 13, 14 and 16 kHz — a 1 kHz comb with the
3 kHz multiples missing, which is block-rate structure (BLOCK 16 at 48 kHz is
exactly 3 kHz, exactly 3× the tone).

## The cable-loop THD row (dispatch gate 5)

`tools/pi/dsp4_loop_thd.sh` is the acceptance leg: verified boot, assert the loop
route, one coherent THD reading, repeatable N times. It is what every arm above was
scored on, so it is proved by use rather than asserted. Run it through
`tools/pi/dsp4_boot_linked.sh` so a folded link (S89-1) can never be read as a
folded output (S89-3).

**Today it runs on Monitor L → MIC 6, not AUX 1 → MIC 6**, because PW moved the loop
cable for the TRS jack set mid-session and the hub held it there. The leg is written
against the loop named in `tools/accept/units.csv` (`loop_aux`, `loop_out_xlr`) and
should be re-taken on AUX 1 when the cable goes back, so the shipping proof carries
the row on the output the product actually ships on.

## TRS jack set (hub interrupt)

Loop cable Monitor L out → MIC 6 in, dScope disconnected, unit its own reference.
Generator is TEST_OSC into strip 20 at −20.00 dBFS; because each reading brackets
the digital tap either side of the lane read, S88-2's oscillator drift is caught
rather than assumed away.

**Cue is not selectable on this pair, proved on the image**: `Mon001InputSel001`
is `_mon_source_C2_MON`, read in exactly one place in `C2_MON.asm` and that place
is inside `#if DSP4_CUE`; the booted pair carries zero CUE symbols on either chip
and `landed-d24.json` has no `Pfl`/`Cue` cell to feed it with. Monitor source is
MAIN. The reading does not rest on the deferred MAIN graph (S88-4) because the
digital word at the Monitor output slot is read directly and paired with the
analog return, so the MAIN chain's gain cancels.

    implied jack FS (dBu) = [ return rms dBFS + MIC 6 ADC FS ] - [ Monitor slot dBFS ]

| jack | drive at slot | return rms | loop gain | implied FS | THD+N | verdict |
|---|---|---|---|---|---|---|
| Monitor L | −26.02 dBFS pk / −29.03 rms | −49.30 dBFS | −20.27 dB | **−2.72 dBu** | 0.066–0.088 % | **ALIVE, clean** |
| Monitor R | — | — | — | — | — | pending (needs the S89-2 poke) |

Cross-check: the hub's formula on the peak reading gives
`−46.29 + 7.91 + 23.13 = −15.25 dBu`; the AUX 1 reference row was driven at
−13.49 dBFS against this row's −26.02 dBFS, and adding that 12.53 dB of drive
difference gives **−2.72 dBu** — the same number, to 0.00 dB.

**Monitor L is ~20 dB below the +17.13 dBu unbalanced expectation and that is not
a fault.** `C2_MON_OUT` is `sport_id=2, slots 0-1, signal CODEC_OUT_1` — the
**AK4619 codec DAC** — where AUX 1 is `sport_id=0 slot 7 = DAC_08` on an AK4458.
The +23.13/+17.13 expectation is the AK4458 full scale and does not apply here.
The codec's *output* full scale had never been measured; **−2.7 dBu (≈0.57 Vrms)
is the first figure for it**, and it is what a single-ended codec line out looks
like.

MIC 6's ADC full scale is taken as **+17.55 dBu**, derived from S88's own AUX 1
reference row (loop gain there was −7.91 − (−13.49) = +5.58 dB, and
23.13 − 5.58 = 17.55) rather than from MIC 6's single-point +17.94, which is a
+0.39 dB outlier. Using +17.94 instead moves the row to −2.33 dBu, so read it as
**−2.7 ± 0.4 dBu**.

## Files

- `MW/D24/DSP/s89/readings.csv` — every jack reading and every bisect arm, timestamped.
- `tools/pi/s89_signbit.py` — the inter-chip sign-bit gate; exit code IS the verdict.
- `tools/pi/dsp4_boot_linked.sh` — boot that refuses to hand back a folded link.
- `tools/pi/dsp4_loop_thd.sh` — the cable-loop THD acceptance leg.
- `tools/pi/s89_bootloop.sh` — boot N times and score the link each time.
- `tools/pi/s89_blk.py` — one block of a per-sample node array as Q4.28, with the fold metric.
- `tools/pi/s89_dma.py` — one block of one lane straight out of a DMA ring, using the part's own off/stride tables.
- `tools/pi/s89_icsurvey.py` — bit-31 census across a whole inter-chip ring.
- `tools/pi/s89_sport.py` — SPORT CTL/MCTL/CS0 for a chip's inter-chip half (reads only).
