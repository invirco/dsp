provenance: AI-drafted 2026-09-17 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Contract proposal S67 — `MeasChan` / `XtalkSrc` / `XtalkDst` also name the chip-1 buses (range 33 → 51)

**Status: PROPOSED, not landed.** No cell is added and no address moves. The
range of three existing Test cells widens, and their descriptions change to
match. The firmware already implements it in `DSP4_TEST_NODES` builds (S67,
`tools/dsp/dsp_codegen.py` `TEST_MEAS_BUS_CODES`); shipping images are
unchanged by it. Evidence: `findings.md` S67-1.

## 1. What changes

| cell | SPI addr | hex | range today | proposed range | proposed description |
|---|---|---|---|---|---|
| `Test[1-1]MeasChan[1-1]` | 4967 | `0x1367` | 33 (0 = off, 1–32 strip) | 51 | Measurement point: 0 off, 1–32 strip post-fader, 33/34 main L/R bus, 35–46 aux 1–12 bus, 47–50 group 1–4 bus |
| `Test[1-1]XtalkSrc[1-1]` | 4971 | `0x136B` | 33 | 51 | Crosstalk source: same numbering as MeasChan |
| `Test[1-1]XtalkDst[1-1]` | 4972 | `0x136C` | 33 | 51 | Crosstalk destination: same numbering as MeasChan |

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

## 3. Numbering

33 = main L, 34 = main R, 35–46 = aux 1–12, 47–50 = group 1–4. Sub, FX and
matrix buses are not tapped. A value above 50 names nothing, the same as 0.
