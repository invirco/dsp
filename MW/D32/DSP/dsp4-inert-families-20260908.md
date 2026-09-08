provenance: AI-drafted 2026-09-08 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The four inert families: two made real, two diagnosed, and one capacity question answered

**Session 28, 2026-09-08.** The graphic EQ and the main crossover now
process. Anti-feedback and the FX engine are diagnosed to a named cause
each. The capacity question the hub asked — whether the 09-03 fit numbers
were measured with dead nodes in the graph — is answered by measurement
and the answer is that they were not, except for one family where it
matters a great deal.

---

## 0. The answer

**FOUR FAMILIES ANSWERED EVERY LANDED ADDRESS AND CHANGED NO SAMPLE, AND
THEY HAD FOUR DIFFERENT DISEASES.** Calling them all "inert" hid that.

| family | entered? | bypassed? | tables? | writes? | fix class | state now |
|---|---|---|---|---|---|---|
| `GEQ` | yes | no bypass flag exists | ACTIVE bank was the compiled identity; the 28 band cells landed in `_geq_coeffs_next[0..27]` as raw dB floats; `_geq_gains[]` written by nothing, read by nothing; no swap trigger | yes | **generator + missing design step** | **FIXED — passes on the part** |
| `CROSSOVER` | yes | none | `CrossoverFreq` and `CrossoverSlope` share address 0x0575 and both landed in `_xover_coeffs_next[0]`; active banks identity | yes | **generator + missing design step**; the shared address is a `defs` defect | **FIXED — passes on the part; slope still not settable** |
| `ANTI_FB` | yes | `_afb_on` / `_afb_ctrl_on` exist, take the write, and are read by NOTHING | notch freq/gain/Q land correctly and nothing reads them; `coeffs_next` unmoved; active identity | yes | **missing design step** — the GEQ's fix applied to a notch bank | diagnosed; not implemented (dispatch says diagnose + cost only) |
| `FX_ENGINE` | yes — proved by cycles | `_fx_on` is written 1 and read by NOTHING | every parameter lands in its own variable and the reverb reads them | yes | **unimplemented default**: `_fx_type` = 0 = Echo, and only 2 (Doubling) and 3 (Reverb) have cases | diagnosed; not implemented |

"Entered?" and "writes?" are answered mechanically, not from the source.
Each node COPIES its input block into its own buffer before filtering, so
a routine that never ran would leave `_buf_<nid>` holding nothing. Every
one of the four read **32 of 32 words equal to its upstream node at peak
0x08000000** — the copy happened, the cascade ran, and the output was the
input. For `FX_ENGINE` the proof is the cycle count instead: setting
`Type` from 0 to 3 on the six engines moves the whole-graph cost by
**+28,171 cycles/block**, reproduced over three boots (+27,861 / +27,867 /
+28,171).

---

## 1. GEQ — 31-band graphic EQ, made real

**The kernel was never the problem.** `C2_AUX_GEQ_01` has always called
`_bq_fx_cascade_blk` with 28 stages, every block, unconditionally. What
never existed was the step between the contract and it.

`defs/products/d24/dsp.csv` gives a GEQ node **one address per band**
(`Aux001Geq001..028`, Table `0=-12/127=12/[Lin]`) — a gain in dB. The
dispatch pointed those 28 addresses at `_geq_coeffs_next`, a 140-word
staging array, one word per band. `gen_dsp.py`'s own comment on that loop
has said `gains[28]` since it was written; the dispatch line beside it
said something else. Measured on the part:

```
_geq_gains_C2_AUX_GEQ_01         unmoved  00000000 ...
_geq_coeffs_next_C2_AUX_GEQ_01   MOVED    41400000 C1400000 41400000 ...   <- 12.0f, -12.0f
_geq_coeffs_A_C2_AUX_GEQ_01      unmoved  3F800000 40000000 BF800000 ...   <- compiled identity
_geq_swap_pending_C2_AUX_GEQ_01  00000000
```

**28 addresses cannot carry 140 coefficients plus a trigger.** EQ_BIQUAD
solves the same problem the other way — its Freq/Gain/Q cells ALIAS a
five-word coefficient base and the host computes the biquad — but a GEQ
node would need 141 addresses to do that, and seventeen of them would not
fit the map. So the design belongs on the DSP.

### What was built

| | |
|---|---|
| `tools/dsp/geq_ref.py` | NORMATIVE. ISO R.40 third-octave centres anchored at 1 kHz (`f_i = 1000·10^((i−17)/10)`, so 31 bands are 19.95 Hz – 19,953 Hz — PW's market bar), exact constant-Q `1/(2^(1/6) − 2^(−1/6)) = 4.3185`, RBJ peaking per band. Checked band by band against `bq_float_ref.rbj_peak`: worst relative 2.2e-16. |
| `src/lib/geq_design_fx.asm` | the kernel. Two per-band constants, one reciprocal, one polynomial. |
| `src/geq_tables.asm` | GENERATED from `geq_ref` by `dsp_codegen.py`: the polynomial and `(alpha, k2)` per band, for every band count the graph instantiates. |
| `_spi_dispatch_cN_dirty[]` | GENERATED. The trigger the contract has no address for. |

### The two things that had to be right

**The offset coefficients are computed in a form that never cancels.**
The readable route — design `b0..a2`, then `c1 = 2 + a1` — is wrong on
the part and would not look it. At 20 Hz `a1` is −1.99999 and `c1` is
6.8e-6; forming `a1` in float32 first carries ~1.2e-7 of absolute error
into a subtraction of two near-equal numbers, so `c1` would come out two
percent wrong. That is precisely the error the offset encoding exists to
remove, thrown away in the step that computes it. Instead, with
`k2 = 2(1 − cos ω₀)` as a per-band constant computed in double at
generation time:

```
aA = α·A     ia = α/A     inv = 1/(1 + ia)
b0 = (1 + aA)·inv    n1 = (k2 + 2aA)·inv    n2 = −2aA·inv
c1 = (k2 + 2ia)·inv  c2 = 2ia·inv
```

**A flat band designs the TRIVIAL identity, not the cancelling one.** At
0 dB the expression above gives `b == a` — a true identity, but built
from a pole and a zero on top of each other near the unit circle.
Twenty-eight of those in series on seventeen nodes is recursion noise
bought for nothing, and it would also mean a GEQ nobody has touched no
longer passes its input word for word. `|g| < 1/256 dB` designs
`(1, 2, −1, 2, 1)`, which is the set every bank is compiled with. The
response step that introduces is under 0.004 dB, an order below the
0.046 dB bar the harness scores biquads against.

`A = 10^(g/40) = 2^(g·log2(10)/40)`, and over ±12 dB the exponent stays
inside ±0.9966 — so ONE degree-8 polynomial on [−1, 1] covers the whole
domain with no range reduction, no table and no branch, and `2^-u` comes
from the same polynomial rather than a second reciprocal. Worst relative
error 2.1e-9, seventeen times finer than a float32 ulp.

### On the part

`geqverify.sh`, image chip1 `5747b84b` / chip2 `1084d3d7` (later
`a6db2a8b` / `8e42f2b0` with the crossover, re-run and identical):

| bar | result |
|---|---|
| coefficients vs `geq_ref.kernel_set` | worst **3 ulp** over five gain vectors (one band ±12, alternating ±12, all +12, a −12…+12 ramp) |
| response of what the part designed | worst **0.00014 dB** against a bar of 0.01 dB (0.05 below 50 Hz) |
| audio, band 17 at +12 dB | 1 kHz measured **+11.997 dB** against a model of +12.000; 250 Hz +0.060 vs +0.061; 4 kHz +0.058 vs +0.058 |
| flat control | designs the compiled identity; live bank identity; **64/64 captured samples equal to the input** |
| SPI errors | 0 |

### A register alias, and why it is in this document

The band counter was in `r12` and the reciprocal in `f12`, which on SHARC
is the same register. The count became the float bits of `1/(1+ia)` —
about 1.07e9 — and the loop walked off the end of the array.

**It did not look like memory corruption.** The 140 designed words were
perfect (1–3 ulp against the model, response inside 0.0002 dB) and the
part stayed up, because everything the overrun touched is rewritten every
block — **except `_geq_active`**, which is not. That word took `n1 = 2.0f`,
`pass` read it as non-zero, and the cascade ran the bank the design had
NOT gone into. A correct coefficient set sitting in the wrong bank is
indistinguishable from no design at all, and the first bench round read
+0.000 dB at every probe frequency with every coefficient correct in
memory.

---

## 2. CROSSOVER — a real LR4 split, and a contract defect underneath it

Same shape, same fix. The node is a real pair of two-stage cascades with
their own state and their own crossfade; the landed cell wrote into
`_xover_coeffs_next[0]`, one word of twenty, nothing raised the swap, and
both banks held the compiled identity while the node copied its input to
all four main outputs.

**Linkwitz-Riley 4th order** is what two LP stages and two HP stages
already committed to — two cascaded Butterworth sections (Q = 1/√2) at
the same corner, so both stages of a path are the same five words.
`1 − cos x` comes from its OWN series, never by subtracting: over
50–500 Hz `cos x` is 0.9979–0.99998 and forming `1 − cos x` in float32
would keep four significant digits of the quantity the whole pole
placement rests on. `n2` is exactly zero on both paths and `n1` exactly
zero on the highpass — identities of the RBJ forms, written rather than
computed.

`xoververify.sh`, image chip1 `a6db2a8b` / chip2 `8e42f2b0`:

| corner | staged vs model | live == staged | LP at corner | HP at corner | response err | LP+HP sum |
|---:|---:|---|---:|---:|---:|---:|
| 50 Hz | 1 ulp | yes | −6.021 dB | −6.021 dB | 0.00013 dB | 0.00013 dB |
| 80 Hz | 3 ulp | yes | −6.021 dB | −6.021 dB | 0.00009 dB | 0.00008 dB |
| 120 Hz | 3 ulp | yes | −6.021 dB | −6.021 dB | 0.00003 dB | 0.00003 dB |
| 250 Hz | 3 ulp | yes | −6.021 dB | −6.021 dB | 0.00003 dB | 0.00002 dB |
| 500 Hz | 2 ulp | yes | −6.021 dB | −6.021 dB | 0.00001 dB | 0.00001 dB |

Audio, impulse response through the node's own LP and HP buffers:

```
f0 120 Hz   30 Hz   LP  -0.04 (model  -0.03)   HP -47.94 (model -48.20)
           120 Hz   LP  -6.02 (model  -6.02)   HP  -6.02 (model  -6.02)
           480 Hz   LP -48.24 (model -48.21)   HP  -0.03 (model  -0.03)
f0 400 Hz  100 Hz   LP  -0.03 (model  -0.03)   HP -48.21 (model -48.21)
           400 Hz   LP  -6.02 (model  -6.02)   HP  -6.02 (model  -6.02)
          1600 Hz   LP -48.32 (model -48.32)   HP  -0.03 (model  -0.03)
```

### THE SLOPE IS NOT SETTABLE, AND THAT IS A `defs` DEFECT

`MainCtr`, `MainL`, `MainR` and `MainSub` each carry a `CrossoverFreq`
AND a `CrossoverSlope`, and **all eight resolve to address 0x0575** —
eight cells, one word, the contract's own note says "shared crossover
word". Measured before the fix: writing 500 Hz then a slope left
`0x00000018` (the integer 24) sitting in coefficient 0.

So a word outside the frequency table's 50–500 Hz is **IGNORED, not
clamped**. Clamping a slope into the frequency would move the crossover
to 50 Hz every time the host set one; ignoring it leaves the split where
the last legal frequency put it. The negative control is in the bar:
writing slope 24 and then 3 leaves the staged coefficient set unmoved
**word for word**.

**Until that row is split in `defs` the slope is fixed at LR4** —
24 dB/octave, which is the top of the slope cell's own table. This repo
cannot fix it; the ask is one row.

---

## 3. Capacity truth

The hub's worry was that every capacity number since 09-03 was measured
with dead nodes in the graph. **It was not, and now that can be shown
rather than argued.**

### The cascade families were always fully costed

`_bq_fx_cascade_blk` issues the same instruction stream whatever its
coefficients hold — there is no early-out on an On flag and no
coefficient-dependent branch. That was always the argument; until the
design landed it could not be TESTED, because no GEQ had ever held a
coefficient other than the identity. Now it can, paired on one boot:

| arm (chip 2, block 8, one boot, minimum of three reads) | cycles/block |
|---|---|
| every GEQ flat (as the product boots) | 330,658 |
| **every GEQ non-flat — 364 band cells written ±12 dB** | **331,250** |
| difference | **+592 (0.18 %)** |

**The graphic EQ's cost has been in every capacity number all along.**
`ANTI_FB` and `CROSSOVER` run the same kernel from the same generator
with the same unconditional stage count, so the same holds for them.

### Like-for-like against the 09-03 record

`sigprofile2.sh`, whole chip-2 graph, **block 16**, two boots, minimum
taken — the same instrument and the same operating point the fit numbers
were taken at:

| | cycles/block | % of 327,680 |
|---|---:|---:|
| 09-03 record, shipping graph | 249,737 | 76.21 % |
| **this tree, with the GEQ and crossover designs landed** | **250,480** | **76.44 %** |

**+743 cycles, 0.23 % of budget, against two boots of this run that are
1,516 cycles apart.** The designs cost nothing measurable at the
whole-graph level — which is what a control-rate step that runs only on
the block a parameter changed is supposed to cost. **The 09-03 fit
numbers stand.**

### The one family where it does matter

`FX_ENGINE`'s instruction stream DOES depend on its parameters, and its
`Type` has always defaulted to 0 = Echo, which the dispatch does not
implement. So the reverb has never been in any capacity measurement:

| arm (chip 2, block 8) | cycles/block | delta |
|---|---:|---:|
| Type 0 on all six engines (the default) | 330,635 | — |
| **Type 3 = Reverb on all six** | **358,806** | **+28,171** |

Reproduced over three boots: +27,861 / +27,867 / +28,171. That is
**3,521 cycles per sample across six engines, 587 per sample per
engine**. Scaled to the block-16 operating point the same per-sample cost
is **≈ +56,300 cycles/block, 17.2 % of chip 2's budget**, which would
take chip 2 from 76.4 % to **≈ 93.6 %** and cut its margin from 23.6 % to
about 6.4 %. **That is a projection from a measured per-sample cost, not
a measurement at block 16, and it is the single largest uncosted item in
the capacity picture.** Measuring it at block 16 is a one-arm job for
whoever next runs `sigprofile2`.

### A caveat on the block-8 absolutes

The block-8 numbers above are **paired deltas on one boot** and that is
all they are used for. Their absolute value — ~330,000 cycles against a
163,840-cycle budget — is not comparable to the 09-02 record of 171,918
for the same chip at the same block size, and the difference is not
explained here. The likely cause is that a graph running at ~200 % of the
block period takes at least one DMA and one SPI interrupt inside every
measured window, and `_proc_cyc` counts them; the block-16 arm, at 76 %,
mostly does not. **Every absolute claim in this section is the block-16
number.**

---

## 4. Family coverage, rescored

`famverify.sh` on this tree, and the previous session's golden rescored
by the SAME instrument so the two are comparable:

| | families passing | addressed cells | strict (numeric) | failing |
|---|---:|---:|---:|---:|
| 2026-09-08, before this session | 13 of 20 (65 %) | 2,934 of 3,698 (79 %) | 4 (1,046, 28 %) | 5 |
| **this session** | **15 of 20 (75 %)** | **3,306 of 3,698 (89 %)** | 4 (1,046, 28 %) | **1** |

`GEQ` (+364 cells) and `CROSSOVER` (+8) move to PASS. `METER` and
`FX_ENGINE` move from FAIL to NOT EXERCISED — the meter because
`mtrverify.sh` is its bar and the family walk now says `NO_VERDICT`
rather than scoring a peak-hold it cannot interpret, the FX engine
because its capture window carried no signal in this run and a silent
window is not a verdict. **`ANTI_FB` is the only remaining FAIL.**

The strict count does not move, and the previous DISPATCH BLOCK's
headline of "82 %, seven strict" does not reproduce under this scorer —
which is why both rows above are the scorer's own output on the two
JSONs rather than a number carried forward.

**One probe changed and it is worth naming.** `GEQ`'s family-walk probe
was `Aux001Geq001` — band 1 of the ISO set, **19.95 Hz**. Its impulse
response takes 2,400 samples to ring once, so over a 32-sample capture a
+12 dB boost moves `b0` by 4e-4 and the family would read INERT for a
graphic EQ working perfectly. The probe is now band 18 (1 kHz), which the
window resolves; the numeric verdict lives in `geqverify.sh`, which
scores the whole band set against the model.

---

## 5. Sample order and latency — the question was unanswerable, and why

The dispatch asked why a counter held 64 Pi frames per value returns only
40.4 % of its transitions monotonic, and named three suspects:
scatter/gather stride, the TDM slot map, or the CPLD's reframing
contract. **It is none of them. The measurement could not have meant
anything, and three independent facts say so.**

**1. The Pi link runs at 48 kHz whatever ALSA is told.** Measured today
on the bench, `arecord -d 5` on `hw:dsp4pcm,0`:

| rate requested | frames delivered | wall time | effective rate |
|---:|---:|---:|---:|
| 48,000 | 240,000 | 5.01 s | 47,917 Hz |
| 96,000 | 480,000 | 10.01 s | 47,955 Hz |
| 192,000 | 960,000 | 20.15 s | 47,645 Hz |

LOGIC masters BCK and LRCLK and the Pi is a slave; the codec
(`invirco,dsp4-pcm-dummy`) declares `SNDRV_PCM_RATE_8000_192000` and
therefore does not refuse a rate the link cannot honour. The loop test
was driven at 192,000. **Every frame count in that result — the 64 Pi
frames per value, the "16 DSP frames", the "−576 Pi frames backwards" —
is four times the truth.**

**2. The flashed bitstream predates the 4:1 regrouping entirely.** The
bench is running `dsp4_logic.a1f6672af6c3`, built **2026-08-21**.
`PI_TDM8` — the parameter that makes four Pi frames tile one DSP frame —
first appears in `rtl/dsp4_pcm_reframe.v` on **2026-08-23** (commit
`2bb0b49`). A bitstream cannot carry a parameter that did not exist when
it was built. The regrouping the reordering was attributed to is not in
the logic on the bench.

**3. That bitstream has no Pi capture path at all.** In the RTL as of the
commit that shipped it:

```verilog
output wire pcm_din,      // LOGIC -> Pi (capture, tied off)
...
assign pcm_din = 1'b0;    // capture path to the Pi: future work
```

`pcm_din` is tied to zero. Nothing can return to the Pi through this
logic, at any rate, on any overlay — confirmed on the bench today: with
the DSP booted, configured and put in the documented pass-through state,
a played counter returned **0 carrying frames** at both 48 kHz and
192 kHz.

**So the loop measurements of 2026-09-08 were taken on a DIFFERENT
bitstream, and the bench was then left on one that cannot loop.** Which
bitstream they were taken on is not recorded anywhere, and that is the
root cause rather than a detail:

**`shared/dsp4-logic/build.sh` hashed `loopback=` and nothing else.** A
`PI_TDM8=1` build and a plain build of the same RTL produced the **same
filename** and a manifest that recorded **neither**. Two functionally
different bitstreams were indistinguishable once flashed. The flashed
one's recorded `slot_map` hash (`efd8d555…`) is also two generations
stale against the current `slot-map.csv` (`4ecc4aa2…`), whose A_I6 rows
declare the regrouping PW decided on 2026-08-23.

**Fixed here**: the artifact hash now covers `PI_TDM8`, `PI_SELFTEST`,
`PI_MAINCAP` and `LOOPBACK`, and the manifest records the config line and
a plain-English `pi_link:` description of what the Pi side actually does.
A bitstream now names its own configuration.

**No latency figure, and no order verdict.** The recorded 40.4 % is
withdrawn rather than explained: it was taken through unidentified logic
with a stimulus scaled by four. **The next step is specific**: build a
`PI_TDM8` bitstream from the current slot map with the fixed `build.sh`,
flash it, and re-take the order test — at which point a latency figure
follows immediately. That needs Quartus and a JTAG session at the bench,
and it was deliberately not done here: with the manifest defect unfixed
there was no way to be sure which of the existing artifacts is the TDM8
build, and flashing shared hardware on a guess is not a measurement.

---

## 6. ANTI_FB and FX_ENGINE — diagnosed, and what each needs

**`ANTI_FB` is the GEQ's fix applied to a notch bank.** The parameters
land correctly (measured: 1000.0 Hz, −18.0 dB, Q 4.0 at their landed
addresses), the cascade is real, and nothing converts one to the other.
`_afb_on` and `_afb_ctrl_on` are read by no emitted line either, so the
On switch does nothing. The work is a `_afb_design_N` beside
`_geq_design_N` — RBJ notch/peaking from (freq, gain, Q), the same dirty
flag, the same swap — plus deciding whether `AntiFbCtrlOn` means an
automatic detector, which is a product question and not a firmware one.

**`FX_ENGINE` needs a `Type` default and two missing algorithms**, and it
has a defect underneath that:

- `_fx_type` defaults to **0 = Echo**, and the dispatch has cases only
  for 2 (Doubling) and 3 (Reverb). Types 0, 1, 4, 5 and 6 fall through to
  a dry pass-through.
- The Doubling path reads a 15 ms (720-sample) delay out of
  `_fx_echo_buf[8]` — an **eight-word** buffer — with a wrap constant of
  8. That path cannot work as written.
- **`_C2_FX_ENG_01_process` sets no L register** and then uses
  `modify(i0, m0)` four times on its comb and delay buffers. Every other
  kernel in this tree guards that with `l0 = 0`. Setting `Type = 3` in
  the family walk turned the FX chain from carrying the impulse to
  reading **peak zero on both arms** — the reverb path does not merely
  fail to reverberate, it takes the sample with it. That is the first
  thing to check and it is why the family-walk spec was left at the
  default `Type` rather than driving the reverb from a bar that runs
  against the whole graph.

Its cost, if it is fixed, is measured and it is large: see §3.

---

## 7. What this session did NOT do

- **No 31-band GEQ on the part.** The design is band-count-generic and is
  checked at all 31 ISO bands in the model, but
  `defs/products/d24/dsp.csv` carries **28** cells per GEQ node, so the
  top three bands have no address to write. The market bar needs three
  more rows per GEQ node in `defs`; this repo is a consumer and cannot
  add them.
- **No crossover slope.** One `defs` row, above.
- **No ANTI_FB or FX_ENGINE implementation** — diagnose and cost only,
  as the dispatch scoped it.
- **No latency figure** — §5, and the reason is now a fixable one.
- **No block-16 measurement of the FX reverb cost** — the 17.2 % figure
  is a projection from a measured per-sample cost.
- **The GEQ design is not bit-exact against the model and is not claimed
  to be.** The SHARC computes in 40-bit registers and stores float32; the
  bar is 4 ulps and the measurement is 3.

## 8. Bars

| bar | result |
|---|---|
| `golden_harness.py` | **59/59** |
| `dsp_validate.py` | **OK**, no errors |
| `busgold.sh` | **GRAPH BIT-EXACT**, 0 of 256 words differ |
| `bqeverify.sh float` | **BQE_VERIFY PASS**, 0 ULP over 18,432 words/arm, bitmap 566 of 576 |
| `geqverify.sh` | **GEQ_DESIGN_OK** |
| `xoververify.sh` | **XOVER_DESIGN_OK** |
| `geq_ref.check()` | 2.2e-16 vs `rbj_peak`; polynomial 2.1e-9; kernel expression 2.1e-9 |
| `xover_ref.check()` | 2.1e-16 vs RBJ; each path −6.02 dB at the corner to 8.7e-8; LP+HP sum flat to 2.4e-10 |
| `famverify.sh` | 15 of 20 families, 3,306 of 3,698 cells |

Images: shipping float configuration, chip1 `a6db2a8b` / chip2 `8e42f2b0`.

**Bench left as found**: `matrix-app` active, `dtoverlay=dsp4-pcm-slave`
untouched, bitstream NOT reflashed (`dsp4_logic.a1f6672af6c3` as the
previous session left it), scratch probes removed.
