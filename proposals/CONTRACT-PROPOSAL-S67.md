provenance: AI-drafted 2026-09-19 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Contract proposal S67 — `MeasChan` / `XtalkSrc` / `XtalkDst` also name the chip-1 buses and the codec-return lanes (range 33 → 56)

**Status: PROPOSED, not landed.** No cell is added and no address moves. The
range of three existing Test cells widens, and their descriptions change to
match. The firmware already implements it in `DSP4_TEST_NODES` builds (S67
buses, `tools/dsp/dsp_codegen.py` `TEST_MEAS_BUS_CODES`; S69/S73 codec-return
lanes, `TEST_MEAS_LANE_CODES`); shipping images are unchanged by it. Evidence:
`findings.md` S67-1, S69-3, S73-1.

## 1. What changes

| cell | SPI addr | hex | range today | proposed range | proposed description |
|---|---|---|---|---|---|
| `Test[1-1]MeasChan[1-1]` | 4967 | `0x1367` | 33 (0 = off, 1–32 strip) | 56 | Measurement point: 0 off, 1–32 strip post-fader, 33/34 main L/R bus, 35–46 aux 1–12 bus, 47–50 group 1–4 bus, 51–55 codec-return lane |
| `Test[1-1]XtalkSrc[1-1]` | 4971 | `0x136B` | 33 | 56 | Crosstalk source: same numbering as MeasChan |
| `Test[1-1]XtalkDst[1-1]` | 4972 | `0x136C` | 33 | 56 | Crosstalk destination: same numbering as MeasChan |

`CaptureArm` (S56 proposal) follows `MeasChan` and needs no change beyond its
description ("Capture MeasChan samples (count)"; drop "post-fader").

## 2. Why

S67 had to verify fader, pan, bus assign and the bus sum on the part. Those
operations end at the chip-1 bus accumulators, and a strip's post-fader tap
cannot see them: pan legs and assigns are folded into the ROUTING crosspoint
coefficients. The bus blocks (`_buf_C1_BUS_*`) are not shared pool slots, so
the same `_test_meas_tap` reads them right after each bus node with no copy.
The coherent fit, RMS, THD+N, crosstalk and the capture arm then work on a
bus exactly as they do on a strip. The idle cost is about ten instructions
per bus per block in TEST_NODES builds only.

S69 had to verify the talkback path, which has no post-fader tap at all: it
terminates in `C1_TALK_01`, a scalar the chain writes once per block and
nothing downstream reads, so MeasChan 1–50 (strips, buses) cannot see it
either. The same `_test_meas_tap` mechanism reaches back one more step, to
each codec-return INPUT_TDM lane's own `_buf_<nid>` block, which is what
lets the standard test set stand on the converter's own output — the last
point where the signal is still exactly what the ADC made. S73 added the
one lane (`C1_XIN_CODEC_02`, slot 1) that S69 left uncovered when it was
declared a session later (S72): codes only, no new cell, no new address,
same `#if DSP4_BLOCK_KERNELS && DSP4_TEST_NODES` guard.

## 3. Numbering

33 = main L, 34 = main R, 35–46 = aux 1–12, 47–50 = group 1–4, 51 = codec
ADC1 Lch (slot 0, `C1_XIN_CODEC_01`, mini-jack tip), 52 = codec ADC2 Lch
(slot 2, `C1_XIN_CODEC_03`, IN3 not connected), 53 = codec ADC2 Rch (slot 3,
`C1_XIN_CODEC_04`, talkback XLR J1), 54 = MEMS talkback mic
(`C1_XIN_MEMS`), 55 = codec ADC1 Rch (slot 1, `C1_XIN_CODEC_02`, mini-jack
ring). Sub, FX and matrix buses are not tapped. A value above 55 names
nothing, the same as 0.
