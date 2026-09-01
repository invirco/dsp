provenance: AI-drafted 2026-09-01 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The biquad cascade at market rate — attribution, rewrite, and what the numeric contract costs

Session 18, 2026-09-01. Follows the D16 gate report
(`dsp4-chip2-blockkernels-20260901.md`) and PW's ruling of the same day:
*GEQ stays; the biquad primitive gets fixed instead.*

The shipping image does not move this session: `chip1.ldr 23c1e662` /
`chip2.ldr e45bb82a`, 301,764 / 182,092 bytes, reproduced from a clean
tree before the first line was written and again after the last.

---

## 1. Where the 37.2 goes — the attribution, before the rewrite

The dispatch asked for the 37.2 cycles/band-sample to be accounted for
before anything was rewritten, because the attribution decides the rewrite
shape. It does, and the answer is blunt: **nothing is hiding.**

`_bq_fx_cascade_blk` at BLOCK = 8, counted instruction by instruction from
the source (one SHARC instruction per line in this kernel):

| | instructions | per band-sample | share |
|---|--:|--:|--:|
| coefficient MACs (12) | 12 × 8 | 12.00 | 33.4% |
| error-feedback MAC | 1 × 8 | 1.00 | 2.8% |
| 64-bit extract, round, saturate | 11 × 8 | 11.00 | 30.6% |
| x1/x2/y1/y2 history moves | 4 × 8 | 4.00 | 11.1% |
| rounding-half add + carry | 2 × 8 | 2.00 | 5.6% |
| signal load + store | 2 × 8 | 2.00 | 5.6% |
| per-stage coefficient + state traffic | 30 | 3.75 | 10.4% |
| call/rts + the node wrapper's copy-in | ~24 + ~20 | 0.20 | 0.6% |
| **predicted** | | **35.95** | |
| **measured on the graph (session 17)** | | **37.2** | |

The prediction closes to **3.5%**, and that residual is the whole stall
budget: issue stalls, MAC result latency, memory contention, everything.

So the four things the dispatch listed as suspects are all NOT the answer,
and each is ruled out by the count rather than by argument:

* **loop overhead** — 0.6%, including the call/rts pair the ladder measures
  at 15.04 cycles;
* **coefficient fetch conflicts (DM vs PM)** — the residual above is 3.5%
  in total, so a systematic fetch conflict is not in this number;
* **branch cost** — zero. D21 already made the saturation a conditional
  move; there is no taken branch in the sample loop;
* **no SIMD** — true, and it is worth 2× at the paired site, but it does
  not explain the scalar cost.

**A biquad is five MACs. This kernel issues thirty-six instructions.** The
attribution says exactly where the other thirty-one went:

* **eight redundant MACs**, spent expressing the offset form term by term
  (`b0*(x - 2x1 + x2)` as four MACs, the halved `n1` as two, the unity
  terms `2*y1 - y2` as three);
* **eleven instructions of round / saturate / 64-bit extract**, which is
  what "Q4.28 out of an exact 80-bit accumulator, saturated" costs;
* **four register moves** shuffling the sample history;
* **3.75 of per-stage state and coefficient traffic**, amortised over
  eight samples.

That decides the rewrite: eight of the twelve MACs are redundant, the four
history moves are an artefact of not unrolling, two of the rounding
instructions are an artefact of where the rounding half lives, and the
eleven extraction instructions are the numeric contract itself.

---

## 2. The rewrite

Four changes. Every one of them is bit-exact, and every one is verified on
the part rather than argued.

### 2.1 Twelve MACs to six — the regrouping is an integer identity

The normative offset form (`fixed_ref.biquad`) is

```
acc = efb + b0*x + b0*x2 - b0*x1 - b0*x1
          + nh*x1 + nh*x1 + n2*x2 - c1*y1 + c2*y2
          + y1*2^29 - y2*2^28
```

and the kernel issued one MAC per written term. The 80-bit MAC accumulator
is exact, so collecting the terms by the variable they multiply cannot
change the sum by one bit:

```
g1h = nh - b0            (MACed TWICE, exactly as nh is)
g2  = n2 + b0
g3  = 2^29 - c1
g4  = c2 - 2^28
acc = efb + b0*x + g1h*x1 + g1h*x1 + g2*x2 + g3*y1 + g4*y2
```

**Six MACs.** The four derived words are computed from the STORED offset
words with five plain 32-bit integer adds in the stage prologue, so:

* the coefficient QUANTISATION is byte for byte what the offset encoding
  produced — the offset form's entire benefit, which is a coefficient
  representation and not an arithmetic ordering, survives untouched;
* nothing changes in the stored coefficient block, in
  `_bq_fx_convert_N`, in the SPI parameter path, in `fixed_ref.py`, or in
  any host tool that reads coefficients.

**Why `g1h` is carried halved rather than as `g1 = 2*(nh - b0)`.** `g1` is
`b1` in Q4.28, and `b1` is not bounded by 8: the worst set in this
product's own design space is a 20 Hz high shelf at +15 dB and Q = 3.16,
where |b1| = 11.2 and a Q4.28 word would wrap. Derived halved it is 0.7025
of int32 full scale. This is the same corner, one step further along, that
the halved-`n1` ruling of 2026-08-29 exists for.

That is not an argument, it is a script: `tools/dsp/bound_direct.py`
sweeps all **869,627** coefficient sets the DEFS ranges reach, reports the
worst magnitude of each derived word, and separately checks the regrouping
identity against the normative expression on 20,000 random
coefficient/state sets.

```
worst |g1h| = 1508603093 = 0.7025 of int32 full scale   (hshelf 20 Hz +15 dB Q 3.16)
worst |g2|  = 1508220185 = 0.7023 of int32 full scale
worst |g3|  =  536865502 = 0.2500 of int32 full scale
worst |g4|  =  268431051 = 0.1250 of int32 full scale
sets where a derived word leaves int32: 0
regrouping identity, 20000 random coefficient/state sets: OK
VERDICT: SAFE
```

### 2.2 The rounding half rides in the accumulator

`y = rns(acc,28) = (acc + 2^27) >> 28` and `efb = acc - (y << 28)`, so the
old kernel added 2^27 to the EXTRACTED pair every sample — two
instructions — purely to keep MRF holding the UNROUNDED accumulator that
the error feedback is. Carry `ACC = acc + 2^27` in MRF instead:

```
ACC' = acc' + 2^27 = (ACC - 2^27 - y*2^28) + products + 2^27
     = ACC - y*2^28 + products
```

The half cancels from sample to sample. It is added once when the stage
loads `efb` and taken back out once when the stage stores it, and `y`
becomes a plain arithmetic shift of ACC. **Two instructions per sample per
stage, gone.**

### 2.3 The sample loop is unrolled by two and the history registers rotate

`x1`/`x2` and `y1`/`y2` exchange roles on every sample, so a two-sample
body needs no history moves at all: the incoming sample is loaded straight
into the register whose `x2` the MAC on the same instruction is consuming,
and the outgoing `y` is written into the register whose `y2` has just been
used. **Four register moves per sample, gone.** After an even number of
samples the roles are back where the stage epilogue expects them, which is
why the kernel now `#error`s on an odd BLOCK.

### 2.4 Multifunction: the signal load and store ride on MACs

```
mrf = mrf + r6 * r10 (ssi), r10 = dm(i2, 0);   /* g2*x2, and x lands in r10 */
r12 = pass r1,              dm(i2, 1) = r1;    /* y becomes y1, and is stored */
```

Both forms were checked against the assembler before use, and the first
one — a compute reading the register the parallel load writes — is
confirmed by the bit-exactness bar on the part, which is the only place
that question can be settled.

### The result

**Nineteen instructions per sample per stage against thirty-two.** The
stage prologue and epilogue grow from 30 instructions to 39 — five for the
derivation, four for adding and removing the rounding half once — and that
is paid once per stage instead of once per sample. Per band-sample at
BLOCK = 8:

| | old | new |
|---|--:|--:|
| inner loop | 32.00 | 19.00 |
| per-stage traffic (30 → 39, over 8 samples) | 3.75 | 4.88 |
| call + wrapper | 0.20 | 0.20 |
| **predicted instructions** | **35.95** | **24.08** |

**1.49× on the scalar site, and it applies to every biquad on both chips
with no graph change at all.**

---

## 3. Verification — four bars, three with negative controls

| bar | what it asks | verdict |
|---|---|---|
| `bqst.sh` | is the rewritten FUSED cascade bit-exact against the untouched per-sample reference `_bq_fx_cascade_N`, ON THE PART, over two stages with different coefficients across a block boundary? | **0 of 16 differ** |
| `bqst.sh` (model arm) | and against `fixed_ref` itself, which is the ruled arithmetic? | **ref vs MODEL 0 of 16; blk vs MODEL 0 of 16** |
| `bqst.sh` (negative control) | does the diff fire when it should? | **15 of 16 differ, maxdiff 7,071,221** |
| `bqgraph.sh` | is the rewritten SIMD twin bit-exact against the rewritten scalar IN THE GRAPH, with REAL filter coefficients loaded into both strips of a pair? | **GRAPH BIT-EXACT, 0 of 64 words** |
| `bqgraph.sh` (negative control) | the pair fed one channel twice must differ | **56 of 64 differ** |
| `bound_direct.py` | do the derived words fit int32 across the whole design space, and is the regrouping an identity? | **869,627 sets, 0 wrapped; identity OK** |
| `golden_harness.py` | the whole numeric model, including the biquad response bars and the halved-n1 headroom | **59/59** |

`_bq_fx_cascade_N`, the per-sample reference the first bar diffs against,
was **not touched**. That is deliberate: a bar whose reference moved with
the thing under test is not a bar.

---

## 4. What the numeric contract costs, and the honest answer to "2-3"

PW's target is 2-3 cycles per band-sample, from the arithmetic that
contemporary mixers run 31-band GEQ on every output on one or two SHARCs,
and from ADI's SIMD `iircas` reference at ~1-2.

**That is a FLOAT number, and the gap is the numeric contract — not the
kernel.** Here is the whole paired inner loop, with the part of it that a
float cascade does not pay marked:

| | instructions/sample (2 channels) | per band-sample | float pays? |
|---|--:|--:|---|
| direct-form MACs | 5 | 2.50 | yes |
| the extra MAC for the halved `g1h` | 1 | 0.50 | no |
| error-feedback MAC | 1 | 0.50 | no |
| 64-bit extract of `y` from the accumulator | 5 | 2.50 | no |
| saturate to 32 bits, branch-free | 6 | 3.00 | no |
| signal load and store | 0 (folded) | 0.00 | — |
| per-stage coefficient + state traffic | 39/8 | 2.44 | yes |
| **total** | | **11.94** | |

**Eleven of the nineteen inner-loop instructions are the contract, not the
filter.** They are what "Q4.28 out of an exact 80-bit accumulator,
saturated, with the rounding remainder fed back into the next sample"
costs, and D5 bought them for measured reasons: plain DF1 fixed point has
12.8 dB of response error at 20 Hz, today's FP32 firmware has 0.4 dB
there, and the error feedback takes the LF noise floor from -107 dBFS to
below -130.

Three statements follow, and each is arithmetic on the table above.

1. **2-3 is not reachable in fixed point at all with this state layout,
   even if extraction and saturation were free.** Seven MACs for two
   channels is 3.5 per band-sample; the per-stage state traffic at
   BLOCK = 8 is another 2.44. The floor with a *zero-cost* round and
   saturate is **5.94**, and that is a floor no code can go under.
2. **Dropping the saturation alone** — the largest single block, six
   instructions — would give 8.94 paired. It is not free of numeric
   consequence and it is not proposed here; it is priced so the option is
   on the table with a number attached.
3. **2-3 is what a FLOAT cascade at a larger block costs**: five MACs, no
   extraction, no saturation, no error feedback, and the per-stage traffic
   amortised over 32 samples instead of 8. That is a return to exactly the
   arithmetic D5 replaced, and it is a product decision about LF accuracy
   and noise floor, not an optimisation one.

The corollary is the useful one: **at BLOCK = 32 this same kernel predicts
10.11 cycles/band-sample paired**, because the per-stage traffic amortises
four times further. The block size is a latency ruling, not a capacity one
— but it is worth knowing that the biquad, unlike the rest of chip 2, does
respond to it.

---

## 5. Measured on the graph — the chip-2 ladder re-run at block 8

Same instrument as session 17 (`sigprofile2.sh`, `DSP4_NODE_LIMIT2` prefix
cut, chip 1 running WHOLE with stimulus on, DEC = 32), same ladder
positions, same day, same card.

| limit2 | adds | session 17 | session 18 |
|--:|---|--:|--:|
| 47 | the input side (no biquads) | 17,241 / 17,258 | **17,253** |
| 48 | + `C2_AUX_FDR_01` | | 17,444 |
| 49 | + `C2_AUX_EQ_01` | | 18,345 |
| 50 | + `C2_AUX_GEQ_01` | | 24,014 |
| 51 | + `C2_AUX_AFB_01` | | 25,303 |
| 0 | **the whole chip-2 graph** | **342,090** | **281,364** |

**The 47 point is the control and it reproduced to 0.07%** — 17,253
against session 17's 17,241 and 17,258. Nothing before the first cascade
moved, which is what makes the rest of the column attributable.

| class | stages | session 17 | session 18 | c/band-sample |
|---|--:|--:|--:|---|
| GEQ | 28 | 8,343 | **5,669** | **37.25 → 25.31 (1.47×)** |
| AFB | 6 | 2,159 | **1,289** | **44.98 → 26.85 (1.68×)** |
| FDR + EQ | 4 | 1,477 | **1,092** | −26.1% together |

FDR and EQ are reported together because session 17 already flagged that
ladder boundary as unstable across boots — FDR read 721 there and 191
here, EQ 756 and 901, and the pair is the only figure the instrument
resolves at that position.

**The prediction and the measurement agree.** The count in §1 and §2
predicts 35.95 → 24.08 instructions per band-sample; the graph measures
37.25 → 25.31 cycles, a 5.1% residual against the old kernel's 3.5%. And
the parts predict the whole with no shared arithmetic: 642 biquad stages
per sample × 11.94 cycles saved × 8 samples = **61,325 cycles/block
predicted**, against **60,726 measured — 1.0% apart.**

### The headline

| | session 17 | session 18 |
|---|--:|--:|
| chip-2 whole graph, block 8 | 342,090 | **281,364** |
| of the 163,840-cycle budget @ 983.04 MHz | 208.8% | **171.7%** |
| of the 131,072-cycle budget @ 786.432 MHz | 261.0% | **214.7%** |

**−60,726 cycles/block, −17.8%, from one kernel, with no graph change, no
feature change and no pairing.**

### Chip 1, measured too

The rewrite is a shared kernel, so chip 1 gets it as well. `captable.sh`
at the shipping configuration — 32 strips, block 8, 983.04 MHz, fused,
dynamics-paired and biquad-paired:

| | cycles/block | % of the 163,840-cycle budget |
|---|--:|--:|
| session 12 | 198,072 | 120.89% |
| **session 18** | **189,602** | **115.72%** |

**−8,470, −4.3%**, and the parts predict the whole here too. Chip 1's
biquads are PAIRED, so the 11.94 cycles/band-sample the instruction count
saves is halved to 5.97 per band-sample of graph: 32 strips × 6 stages ×
8 samples × 5.97 = **9,170 predicted against 8,470 measured, 7.6%
apart.** Chip 1 at block 8 remains over budget, which it already was;
block 32 is where it fits, and that point was not re-measured.

### And the biquad is no longer the wall

This is the part that changes the ranking, and it is arithmetic on the two
measurements above.

At 48 kHz the whole chip-2 graph is now **1,688 MHz** (was 2,053). The
cascade classes, scaled by the measured GEQ ratio, are **730 MHz** (were
1,075; the stage-count cross-check gives 780, the same 6.6% spread session
17 recorded). So:

> **Everything on chip 2 that is NOT a biquad cascade measures 958 MHz —
> 97.4% of a 983.04 MHz part, on its own.**

Session 17's break-even for the cascade was 11.0 cycles/band-sample,
because the biquad was 52% of the graph. It is now 43%, and the same
arithmetic gives a break-even of **0.10 cycles/band-sample** — that is,
**the biquad can no longer close chip 2's gap at ANY rate, including PW's
2-3.** Not because the primitive is slow; because it is no longer the
thing that is slow.

The levers, re-priced against this measurement rather than against the
gate report's:

| | MHz | % of 983.04 |
|---|--:|--:|
| chip-2 whole graph, as measured today | 1,688 | 171.7% |
| − dynamics pairing (555 → 321, chip 1's graph-measured factors) | 1,454 | 147.9% |
| − biquad pairing, NATIVE interleave (730 → 362, §6) | 1,086 | 110.5% |
| − hoisted kernels for LIM/COMP/GATE/DLY/XOVER (~90) | 996 | **101.3%** |

**Chip 2 goes from 208.8% at the gate to about 101% with every lever now
identified and priced.** That is arithmetic on measured parts, not a
measurement, and it is stated as such — but it is a different answer from
the gate report's *"the shortfall is structural; the options are
product-level"*. With the primitive fixed, chip 2 is within about one
percent of fitting, and the remaining work is engineering rather than a
feature decision.

---

## 6. The next lever, and why it is not "wire the existing pairing onto chip 2"

Session 17 ranked cross-channel SIMD pairing first, on the evidence that
`_bq_fx_cascade_simd` measures 1.43-1.54× at the kernel and that chip 2 has
none of it. That ranking still holds, but the SHAPE of the work has to
change, and the arithmetic says why.

`_bq_pair_blk` gathers the two channels into an interleaved scratch,
runs the SIMD cascade, and scatters back. Per stage per pair that is
5 coefficient words in, 6 state words in and 6 state words out, each of
them a load and a store — **68 instructions per stage per pair, over 2
channels × 8 samples = 16 band-samples, so 4.25 cycles per band-sample,
and the figure does not depend on the stage count.** The signal
interleave adds about 1 more on a short cascade and is negligible on a
long one.

Against a paired inner loop that saves 9.5 per band-sample, a 4.25 gather
is not a detail: it turns a 2× lever into about 1.5×. It is the same thing
the session-17 record already measured from the other end —
`LEVER_BQPAIR_BLK8` came in at −8.3% against a −13% prediction, with the
note *"the driver's gather/scatter overhead is real"*.

**The fix is to stop gathering.** Both halves can be hoisted out of the
per-block path entirely:

* **coefficients** are written by `_bq_fx_convert_N` at coefficient-swap
  time, not per block. Emitting them INTERLEAVED at conversion is free —
  it is a stride, not a copy;
* **state** belongs to the cascade and to nothing else. If the pair OWNS
  one interleaved state array, it is never gathered at all. The cost is
  that the crossfade transient path must walk the same array at stride 2,
  which means the per-sample reference cascade needs a stride parameter
  in an M register — a change with no cycle cost in either mode.

With both hoisted, the only per-block interleave left is the signal: 8
words per channel in and out, **0.14 cycles per band-sample on a 28-band
GEQ**. That is the difference between a 1.5× lever and a 2× one on the
largest class on the part.

**It also unblocks chip 2 for free.** Chip-1 pairing needed a second block
pool because the strip pool is reused strip by strip and two channels
could never be live at once. Chip 2 has no such problem: every chip-2 node
owns its own persistent `_blk_<nid>` buffer, so both channels of a pair
are already live. What chip 2 needs is only that the two members of a pair
have both had their INPUTS computed before the pair driver runs — i.e. the
per-aux and per-group chains interleaved pairwise, exactly the
head/dynamics/tail split chip 1 already generates, but with no pool
aliasing to arrange. That reordering is also what the DYNAMICS pairing
needs, and the two should land together.

---

## 7. The regression bars, and one defect found in a bar

| bar | verdict |
|---|---|
| `busgold.sh` — chip 1's main bus against the stored session-6 golden | **GRAPH BIT-EXACT, 0 of 256 words** |
| `conform.sh` — the contract conformance harness, both chips | **VERDICT: PASS**, presence 6032/388/117/56/159 on chip 1 identical to every prior clean session, chip 2 answering its OWN map 1701/24/21/175/31, negative control 4 of 4, the 16 declared-unit fails the pre-existing named D41 mismatches |
| `golden_harness.py` | **59/59** |
| `dsp_validate.py` | **OK** |
| `bqst.sh`, `bqgraph.sh` | §3 |
| `c2gold.sh` | set probes **37 of 37 clean**; meters differ on 19 of 24 — **D80**, see below |
| W0 | `chip1.ldr 23c1e662` / `chip2.ldr e45bb82a`, 301,764 / 182,092 bytes, reproduced before and after |

### D81 — c2gold's D79 exclusion had never fired, and this is the run that needed it

`c2gold.sh` is supposed to exclude a chain whose fader head took a stray
config word (D79) and NAME it, *"because what it produces is a function of
which word that boot dropped, not of the conversion"*. It never did. The
exclusion keyed the health map on `probe.split('_', 2)[2]`, which for
`_mtr_peak_C2_MTR_AUX_01` is `peak_C2_MTR_AUX_01` — a string the health map
cannot contain, because that map is keyed by meter id. `ha.get(mid, 'ok')`
therefore took its default on every probe and every chain was always
"healthy".

Session 17's run had no corrupt chain, so nothing showed. This run did:
aux 01's fader head read `level=0xE0FE0000 gq=0xFFFFFFFF` in one arm and
`0x00000000/0x00000000` in the other — D79 exactly, in both arms, with
different garbage — and the bar reported that chain's two meters **and all
six of its node-output probes** as a conversion failure.

Fixed, and the fix goes further than the original intent: the SET probes
were never covered at all, and a corrupt chain poisons every node in it,
not only its meter. Both probe families now map to a common chain tag and
are excluded together. Re-run against this session's own stored captures:

```
EXCLUDED (chain unhealthy in at least one arm -- stray config word, D79):
  C2_MTR_AUX_01   arm0=level=0xE0FE0000 gq=0xFFFFFFFF  arm1=level=0x00000000 gq=0x00000000
EXCLUDED (set probes on an unhealthy chain): C2_AUX_AFB_01, C2_AUX_DLY_01,
  C2_AUX_EQ_01, C2_AUX_FDR_01, C2_AUX_GEQ_01, C2_AUX_LIM_01, C2_AUX_OUT_01
SET PROBES: 37 node outputs, 0 produced a word the per-sample reference never does
NEGCTL: 24 of 24 differ under a deliberately wrong pairing (PASSED)
```

**37 of 37 raw node outputs clean**, which is session 17's result
reproduced.

### The meter arm is D80, and the cascade cannot be in it

What is left is 19 of 24 meter probes differing, and it is D80's signature
exactly: **all 8 peaks LOW in the block arm, 12 of 13 RMS HIGH**, opposite
directions so not a gain error, magnitudes 0.577% to 0.896%.

**The worst is 0.896%, which is outside the 0.7% bound the dispatch
names, and that is stated rather than rounded away.** It is inside session
17's own recorded CROSS-BUILD worst of 1.249%, and D80's magnitude is a
function of the dynamics envelope state at capture, which is boot-dependent
— but 0.896% > 0.7% and the bound was not met.

The cascade rewrite is nonetheless not in this number, and the reason is
constructive rather than statistical. **Nothing configures chip 2's filter
coefficients** — `dsp4_config.py` writes none — so both arms run the
cascades on the `.var` bypass initialisers the generator emits,
`b0 = 0x10000000, nh = 0x10000000, n2 = 0xF0000000, c1 = 0x20000000,
c2 = 0x10000000`. At those values every derived word is **exactly zero**:

```
g1h = nh - b0        = 0x10000000 - 0x10000000 = 0
g2  = n2 + b0        = 0xF0000000 + 0x10000000 = 0
g3  = 2^29 - c1      = 0x20000000 - 0x20000000 = 0
g4  = c2 - 2^28      = 0x10000000 - 0x10000000 = 0
```

so the new kernel computes `acc = efb + b0*x` with `efb` identically zero,
i.e. `y = x`; and the old kernel's twelve terms cancel to the same thing.
Checked rather than asserted: 200,000 samples at the bypass set give
**0 differences, error feedback non-zero on 0 samples, y == x on all
200,000**, and 300 real coefficient sets × 400 samples give a worst
`|old - new|` of **0**.

**The cascade is the identity in both arms of this bar, so it cannot
contribute one bit to the difference.** D80 remains open, unrooted, and
its own item.

---

## 8. Item 3 — dynamics pairing on chip 2

Chip 1 pairs the dynamics of two channel STRIPS. Chip 2 has no strips: its
dynamics are `C2_GRP_GATE_01`, `C2_MAIN_OCOMP_03` and friends, in four
parallel group chains and four parallel main-output chains. The KERNELS
(`_gate_pair_blk`, `_comp_pair_blk`) do not care — they take two parameter
blocks, two state blocks and two signal blocks — and the per-node variable
layout they require was already being emitted on chip 2, because the
declaration order is guarded on `DSP4_PAIRED_GRAPH` and not on the chip.

**Twelve nodes now run as six paired driver calls**: four `C2_GRP_GATE`,
four `C2_GRP_COMP`, four `C2_MAIN_OCOMP`. `C2_SUB_COMP` and
`C2_MAIN_COMP` are single instances in different chains and are not
paired.

Two things are easier here than on chip 1 and one is harder.

* **No second pool.** Chip 1 needed `BLK_*_P1` because the strip block pool
  is reused strip by strip, so two channels could never be live at once.
  Every chip-2 node owns a persistent `_blk_<id>` buffer, so both channels
  of a pair are already live and always were.
* **The scalar fallback is just the two nodes.** Chip 1's has to square the
  pool ping-pong up; a chip-2 node reads its producer's buffer and writes
  its own on either path.
* **Harder:** the paired kernel runs IN PLACE on one buffer per channel and
  a chip-2 node's input and output buffers are DIFFERENT, so the driver
  copies each channel's input block into its own output block first. BLOCK
  words per channel per class, against a class costing 300-500 cycles per
  sample.

Which nodes pair is an EXPLICIT TABLE (`_C2_PAIR_FAMILIES`), adopted the way
matrix cell families are, and the structure each family claims is CHECKED:
a family whose run is not a contiguous block of the chain, or whose paired
classes are not contiguous within it, raises rather than quietly pairing
something else. Each family's run is reordered IN PLACE, which is what keeps
every ladder position before it — the whole aux side, where §5's GEQ/EQ/AFB
costs were taken — the same number in both builds.

### Two defects, and the bar found both

**D82 — a meter riding on a paired node was never called.** Under block
kernels a meter is called immediately after its source, not at its own chain
index, and that emit lives in `emit_chain`'s node branch. The pair branch
`continue`d straight past it. `C2_MTR_GRP_01` taps `C2_GRP_COMP_01`; once
that node was inside a pair entry its meter was never called at all and read
its `.var` initialiser. `c2dyngold.sh` caught it as **two group meters
reading exactly `0x00000000` in the paired arm** while every other meter was
live.

**D83 — the paired driver did not publish the meter's wide word.** The
generic per-block wrapper walks `_mtr_wide_<id>` out into
`_mtr_wblk_<id>[i]` one sample at a time; the pair kernel does not, and the
driver replaces the wrapper. After D82 was fixed the meters were called and
still folded an untouched array. The driver now walks the block out itself
(`Q4.28 -> Q8.24`, the same shift the scalar body does).

A third repair rides with them and was not a caught defect: on chip 2
`_buf_<id>` IS what a host peek reads, and the paired path only writes it
for sample 0, so the driver republishes it off the last sample of the block
— the same repair the GEQ block kernel already makes for the same reason.

### Measured — 2.3x per class, and it beats chip 1's own factors

`sigprofile2.sh`, block 8, 983.04 MHz, the same ladder either side of the
`DSP4_SIMD_DYN` switch.

| | unpaired | paired | |
|---|--:|--:|--:|
| GATE, two channels | 2 x 2,746 = 5,492 | **2,376** | **2.31x** |
| COMP, two channels | 2 x 4,214 = 8,428 | **3,697** | **2.28x** |

Against chip 1's graph-measured 1.82x (GATE) and 1.72x (COMP), and the
reason chip 2 does better is worth naming rather than enjoying: **chip 2's
scalar path is the GENERIC per-block wrapper**, which session 17 measured at
about 15% over a hoisted kernel, and the pair driver replaces the wrapper
outright. Chip-2 pairing collects the pairing win and the wrapper win at
once.

### The headline

| | cycles/block | % of the 163,840-cycle budget |
|---|--:|--:|
| the D16 gate (session 17) | 342,090 | 208.8% |
| + the cascade rewrite (§5) | 281,364 | 171.7% |
| **+ chip-2 dynamics pairing** | **257,936** | **157.4%** |

**−23,848 cycles/block, −8.5%**, and **−24.6% cumulative** over the two
pieces of work. At 786.432 MHz: 196.8%, from 261.0% at the gate.

Two checks on the number, neither sharing arithmetic with it:

* **the unpaired control reproduced.** Measured fresh this session at
  281,784 against §5's 281,364 — **0.15% apart**, on a different boot;
* **the parts predict the whole.** Four GATE and eight COMP instances
  becoming six pair calls predicts 25,156 cycles/block saved against
  **23,848 measured, 5.2% apart** (the residual is `C2_MAIN_OCOMP` being
  priced at `C2_GRP_COMP`'s per-instance cost, which is an assumption and
  not a measurement).

### Verification — what the bar proves, and what it does not

New bar `SHARC/c2dyngold.sh`: one tree built twice, differing only in
`DSP4_SIMD_DYN`, driven with the identical `DSP4_PROFILE_SIGNAL` stimulus.

**All 47 probed node OUTPUT BLOCKS are bit-exact**, including the paired
nodes themselves, their channel-B partners, and everything downstream.

The verdict is the output blocks and not the meters, and that was learned
the hard way: the first cut scored the meters and they differed on 19 of 24
probes by a few percent in both directions — **including on aux chains that
contain no paired node at all**. The meters are per-BLOCK IIRs whose 300 ms
RMS window is about **56 seconds of wall clock under DEC=32**, against a 12
second dwell, so they read a point on a convergence curve and the paired arm
reaches a different point *because it runs faster*. That is a bar measuring
its own speedup. A node's whole output block has neither problem: it is
recomputed from scratch every pass, and sorting it makes it independent of
which phase of the stimulus square the block starts on.

**THE GAP, NAMED.** The `DSP4_SIMD_NEGCTL` control — which makes the pair
kernel take channel B's parameters, state and signal from channel A, so it
computes one channel twice — **changes nothing**, and that is not a bug in
the control. Every chip-2 chain on this bench carries the same stimulus at
the same unity gain with the same compiled default dynamics settings, so
channel A and channel B of a pair are numerically the SAME CHANNEL. The
pairs are demonstrably RUNNING — the bar witnesses `_cmp_gn` live,
`_dsim_n = BLOCK-1`, and every eligibility word on the paired path, and the
cost table above is not what a scalar fallback produces. So the bit-exact
result proves the PLUMBING: the chain order, the sample-0 handoff, the block
copy, the meter block, the `_buf_` republish. **It does not prove CHANNEL
SEPARATION.** Closing that needs distinct per-channel dynamics settings
written over the SPI parameter plane before the dwell — exactly what
`bqgraph.sh --bq` does for the biquads, and the same trap that record names:
*"a comparison taken at bypass passes whatever the pairing does"*.

**Containment.** Chip 1's generated files are byte-identical across this
change — the diff is `chip2/dyn_pairs.asm` and `chip2/process_chain.asm`,
insertions only. W0 unmoved: `23c1e662` / `e45bb82a`, 301,764 / 182,092
bytes.

---

## 9. What this session did not do

* **Item 2's target of <= 11.0 cycles/band-sample measured on the graph is
  NOT met.** The scalar site measures 25.31 against 37.25 — 1.47×, against
  the 3.4× the gate report's break-even asked for. The other half of it is
  cross-channel SIMD pairing, and that is not wired on chip 2.
* **Item 3 landed (§8) but its bar has a named gap**: channel separation is
  not proven, because both channels of every chip-2 pair carry identical
  signal and identical settings on this bench. That needs distinct
  per-channel dynamics settings over the SPI plane.
* **`C2_SUB_COMP` and `C2_MAIN_COMP` are not paired** — two of the ten
  compressors. They are single instances in different chains and pairing
  them across chains needs a DAG argument this session did not make.
* **LIM is not paired at all** — 18 instances, ~316 cycles/sample each, and
  there is no `_lim_pair_blk`. It is the largest remaining dynamics lever.
* **Chip 1 was re-measured at block 8 only.** `MARGIN32_BLK8` is now
  189,602 (115.72%); the BLOCK-32 point, which is the one where chip 1
  actually fits, was not re-run and still dates from session 12.
* **A `gainfix.py` equivalent for chip 2 (D79) was not built** — it is
  explicitly out of scope for this dispatch, and it cost this session a
  c2gold chain.
