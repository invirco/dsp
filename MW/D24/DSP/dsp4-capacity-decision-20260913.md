provenance: AI-drafted 2026-09-13 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# D24 capacity — the decision, on one page

For PW. Nothing in this sheet changes the configuration or the generator; S42
was told not to and did not. It restates what the part measured, says what the
number is made of, and prices the levers that are already built and already
proved.

---

## The number

**On the shipping configuration, a D24 does not fit either chip, and it has not
since the configuration was named.**

| | chip 1 | chip 2 | blocks missed |
|---|--:|--:|---|
| S39-3, on the part, 2026-09-12, map-anchored pair | **114.9 %** | **103.1 %** | 12.9 % / 3.0 % |
| S19, on the part, 2026-09-10, driven, same configuration | 118.89 / 118.92 % | 119.24 / 119.25 % | 15.9 % / 16.1 % |

Budget is 327,680 cycles per block (block 16, 983.04 MHz). The clock is
anchored, not assumed: the diag tick reads 1000.03 Hz on chip 1 and 1000.00 Hz
on chip 2, so the core is on its target.

A block that is missed is not a glitch you can hear once. The half that was not
rewritten is transmitted again, so the wire carries a stale whole block.

---

## S39-3 is not new, and that is the important part

The fit tables say a D24 runs at **59.8 % / 84.4 %** driven (S27/S28). The part
says 114.9 % / 103.1 %. The gap is not a measurement problem and it is not the
graph. **The fit tables price a different configuration**, and the part says so
in its own register:

| | `DIAG_BUILD_CFG2` |
|---|---|
| `shipping.config` — what is on the bench | `0xC2010244` (S39 read exactly this off both chips) |
| `shipping.config.s26` — what every fit table since S20 was measured on | `0xC2019E6F` |

Six switches differ, and all six are capacity levers:

| switch | shipping | the fit tables |
|---|--:|--:|
| `DSP4_STRIP_FUSED` | 0 | 1 |
| `DSP4_SIMD_DYN` (and derived `SIMD_STRIPS`) | 0 | 1 |
| `DSP4_C2_BQ_GRAPH` | 0 | 1 |
| `DSP4_GATE_LINTHR` | 0 | 1 |
| `DSP4_DYN_LUT` | 0 | 1 |
| `DSP4_SHARED_KERNELS` | 0 | 15 |

So the answer to "what does the shipping configuration contain that the fit
tables did not price" is **nothing**. It is the other way round: the fit tables
price five cycle levers and one memory lever that the shipping configuration
does not have. S19 said this on 2026-09-10 in one sentence — *"the
configuration `shipping.config` names does not fit either product"* — and
`shipping.config.s20` has existed as the proposal ever since.

The graph itself is not the surprise. GEQ at 31 bands on twelve aux buses, four
groups and the main bus; twelve aux chains; the 24-strip mask; block 16 — all
of that is in the fit tables at 59.8 % / 84.4 % and all of it is in the shipping
build too. What is absent is the pairing.

---

## The three cheapest levers

Prices are measured on the part, D24 mask, driven, block 16, 983.04 MHz. Every
one of them is already written, already built and already witnessed; none is a
piece of work waiting to be done.

### 1. `DSP4_C2_BQ_GRAPH` — about **17 points of chip 2**

Chip 2's aux and main biquads run two channels in one instruction stream.
S19's `s16sd` arm is `s20` minus this one switch and read 76.42 % against
`s20`'s 58.99 % at D24.

*Audio consequence:* none measured. The defect that held it at 0 (S12-5: band
gains written into a paired GEQ never becoming coefficients) was root-caused
and fixed the next day (S13-1, CLOSED). Witnessed since by `geqverify` and
`afbverify` at 1–4 ulp worst coefficient and ≤0.00014 dB worst modelled
response, live tone +11.997 dB against +12.000 modelled; `bqeverify` **0 ulp
over 36,864 words**.

*Cost to prove:* it is proved. What is left is a signature.

### 2. `DSP4_SIMD_DYN` + `DSP4_STRIP_FUSED` — the chip-1 lever, ~65 points

These two ship together and are most of chip 1's 118.9 % → 53.8 %. On chip 2 at
D32 they are worth 30.7 points together (97,092 cycles for SIMD_DYN, 3,542 for
STRIP_FUSED).

*Audio consequence:* `famverify` across 20 families, both chips — **1 of 20
verdicts differs from the shipping pair: COMPRESSOR, numeric, at 0.00518 dB.**
17/20 LIVE, contract 20/20 answering, FADER_PAN and TUBE_SAT BIT_EXACT.
STRIP_FUSED on its own is verdict-for-verdict identical with three arms
BIT_EXACT.

*Cost to prove:* proved. 0.00518 dB on one family is the whole of what PW is
being asked to accept.

### 3. `DSP4_GATE_LINTHR` — 54 % of the gate body, for ≤0.0002 dB

The gate's threshold comparison in the linear domain instead of the log domain.

*Audio consequence:* a threshold shift bounded at **0.0002 dB**.

*Cost to prove:* proved (S15-7).

**The fourth, named because it is the one with a real audio consequence:**
`DSP4_DYN_LUT` — the level→gain table. It is what makes the signal free: on the
s20 configuration, driven minus silent-loaded is +0.05 / −0.29 points; on the
shipping configuration the same column is **+42.5 and +29.3**. Its bound is
**0.0950 dB**, which is two and a half orders of magnitude larger than the
other three, and it is the one that should be signed off on its own terms.

**Together these are `shipping.config.s20`, which measured D24 at
53.8 % / 59.0 % with zero overruns on every row of every boot, and D32 at
71.6 % / 72.6 %.** The decision is not "which levers" — it is whether to adopt
the configuration that already exists.

The one thing it costs that is not cycles: chip 1's code pool goes from
235,064 / 262,144 bytes (89.7 %, 27,080 free) to 261,764 (99.9 %, **380 free**).
That is the real constraint on the s20 configuration and it is why
`DSP4_SHARED_KERNELS=15` is in it.

---

## Read this number again after S40's first ten minutes

**The 114.9 % was measured with every input at full scale, by accident.**
S39-4's one-bit capture error turned each converter's noise floor into a
near-full-scale artefact, which pinned the meters at −0.00 dBFS peak in every
arm including a muted one — so every gate and every compressor on chip 1 was
fully engaged for the whole measurement.

On the shipping configuration (`DSP4_DYN_LUT=0`), driven costs **+42.5 points
on chip 1 and +29.3 on chip 2** over silent-loaded. S42 fixed the capture
(S42-1), so the inputs go back to a −65…−85 dBFS noise floor.

**Prediction, to be taken in S40's first ten minutes and worth more than any
argument on this page:** chip 1 falls from 114.9 % toward ~76 %, chip 2 from
103.1 % toward ~90 %. If it does, then on the shipping configuration a quiet
D24 fits chip 1 and does not fit chip 2, and the first time anybody speaks into
a microphone it stops fitting either. If it does not fall, the load is
somewhere the record does not have it and that is a new finding.

Either way the decision above is unchanged — a mixer is not specified at idle —
but the number PW is deciding against should be the honest one. Re-take it
with `tools/pi/dsp4_s39_cost.py` on both chips before anything else is
concluded from a percentage.

---

## What is being asked

1. Adopt `shipping.config.s20` (or its successor `.s26`), or name which of the
   six switches stay at 0 and accept that a D24 misses blocks.
2. Sign off `DSP4_DYN_LUT`'s 0.0950 dB separately from the other three, whose
   worst measured consequence is 0.00518 dB.
3. Nothing else. The graph does not need to shrink, the GEQ does not need
   fewer bands, and no product function has to be given up to make a D24 fit.
