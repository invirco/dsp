provenance: AI-drafted 2026-09-21 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S89 — the shipping DSP pair folds its DAC output

Session 89, 2026-09-21, unit MW-D24-2 rev C. Hub dispatch `tasks.md` 2026-09-21
13:34Z. **IN PROGRESS** — root cause found and localised; the switch bisect is
built but not yet run on the part (paused for a hub interrupt, the TRS jack set).

## Headline

The fold is **not** in the output packing, the sign handling, or an unsaturated
overflow in chip 2's output stage, which is where the dispatch expected it. It is
in the **inter-chip transfer**: chip 2 receives every inter-chip word with **bit 31
forced to zero**.

    received = sent & 0x7FFFFFFF

A negative Q4.28 sample of −0.211 arrives as **+7.789**. The waveform's negative
half is folded up to just under the +8.0 rail, which is exactly the wrap-around
PW's scope saw, at the right fundamental level once the large DC term is lost in
the AC-coupled XLR output.

## S89-1 — the inter-chip link loses the sign bit (root cause, localised)

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

**Still open:** which build switch (or which tree change since the s51 image of
2026-08-12) makes the difference, given identical SPORT configuration. Five arms
are built and staged for the bisect — `DSP4_SIMD_DYN=0`, `DSP4_STRIP_FUSED=0`,
`DSP4_DYN_LUT=0`, `DSP4_GATE_LINTHR=0`, and an all-off control — none yet run on
the part.

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

- `MW/D24/DSP/s89/readings.csv` — every jack reading, timestamped.
- `tools/pi/s89_blk.py` — one block of a per-sample node array as Q4.28, with the fold metric.
- `tools/pi/s89_dma.py` — one block of one lane straight out of a DMA ring, using the part's own off/stride tables.
- `tools/pi/s89_icsurvey.py` — bit-31 census across a whole inter-chip ring.
- `tools/pi/s89_sport.py` — SPORT CTL/MCTL/CS0 for a chip's inter-chip half (reads only).
