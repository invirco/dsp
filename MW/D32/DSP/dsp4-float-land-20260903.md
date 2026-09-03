provenance: AI-drafted 2026-09-03 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Float lands: the offset wire, the on-part bar, and GAIN

**PW ruled on 2026-09-03 that the SHARC DSP is 40-bit float.** Session 24
produced the decision number and named three things it had not done: the
float kernels' numerics were modelled and not validated on the part; the
0.0042 dB offset-wire result was the most decision-relevant figure in the
session and no instruction had been written for it; and GAIN had been
priced and not converted. This session does all three and makes float the
default, and it corrects one of session 24's own numbers in the process.

---

## The headline

**Float is the shipping cascade on both chips: chip 2 at 76.22% of budget
and chip 1 at 88.56%, guard-free, with a worst-case response error of
0.0080 dB against a 0.046 dB bar — three times better than the fixed
contract it replaces — and the kernel is now proved to compute its
model's words on the part rather than assumed to.**

The fixed round-once path and its ‖h‖₁ guard stay in the tree behind
`DSP4_BQ_FLOAT=0`. They are the reference model a future FPGA fixed
engine follows, and the bar that proves them intact is that all three
recorded W0 witnesses still rebuild **byte for byte** after every change
in this session.

---

## 1. The offset wire, built — and it is not the number that was modelled

The coefficient block now carries five float32 words a stage in **D5's
own offset encoding**:

    b0,   n1 = b1 + 2·b0,   n2 = b2 − b0,   c1 = 2 + a1,   c2 = 1 − a2

`_bq_fx_convert_N` stays a copy — the wire word IS the stored word — and
the kernel reconstructs the direct coefficients in **registers**, in its
per-stage prologue: five arithmetic instructions and two constant reads,
once per stage per BLOCK, not per sample.

| coefficient wire | worst response error, DEFS set |
|---|---|
| float32 DIRECT (session 24's arm) | 0.3715 dB |
| Q4.28 offset — the fixed contract | 0.0265 dB |
| **float32 OFFSET — built, this session** | **0.0080 dB** |
| golden bar | 0.046 dB |

**It is 0.0080 dB, not the 0.0042 dB session 24 modelled, and the
difference is a real defect in the old model rather than a
disappointment.** `offset_wire_coeffs` reconstructed the direct
coefficients in `numpy.longdouble` — 64 significand bits — and the part
reconstructs them in the register file, which has 32. `c1 − 2.0` is exact
only while c1's lowest set bit is at or above 2⁻³¹, and for a 20 Hz
biquad it is not, so the reconstruction rounds once. The model now rounds
where the part rounds and the two agree to the bit (§3).

**The way to avoid the rounding is priced and was not taken.** Running
the offset form THROUGH the recursion — `w1' = 2·w1 + w2 + n1·x − c1·y`,
`w2' = n2·x − w1 + c2·y` — never forms a1 or b1 at all and would read
about 0.003 dB. It is seven ALU ops against four pairable multiplies, so
one more instruction per sample per stage, about 3% of chip 2. **0.0080
is already 5.75× under the bar and 3.3× better than the shipping fixed
contract**, and 3% of chip 2 is most of what float just won. Stated so
the option is on the record rather than lost.

### And the model was wrong about the signal path too

`bq_float_ref` carried the state's crossing of a block boundary and not
the signal's crossing between stages. `_bq_fx_cascade_blk` runs
stage-outer / sample-inner, so **a stage writes its whole block of y to
the block buffer and the next stage reads it back: the forward path is
32-bit float even in the 40-bit arm**, and so is the entry pass's `FLOAT
Rx BY -28`, which quantises a 32-significant-bit Q4.28 word to 24 bits on
the way in. What stays at 40 bits is the RECURSION — w1/w2 in registers
across the block, and the full-precision y that feeds them, not the
truncated copy handed on. That is where a high-Q LF biquad's state error
lives, so the 40 bits keep what they were bought for.

**Measured, both ways: the forward path's 32 bits are worth nothing on
the response table — 0.0080 dB either way.** The finding is not that it
matters; it is that a normative model was claiming a precision the kernel
has not got, and it went unnoticed until the on-part bar existed.

---

## 2. Nothing generated moved, except the thing that had to

The offset block is still five words a stage, so no generated array
changes size and no node's state layout moves. **The bypass initialiser
had to change, and this time for a sharper reason than session 24's.**

Under the offset encoding the identity filter is
`(1.0, 2.0, −1.0, 2.0, 1.0)`. **Five zeros after b0 reconstruct to
a1 = −2, a2 = 1 — a double pole at z = 1. That is not silence, it is an
integrator squared.** So every bypass initialiser AND every host-wire
staging buffer in the tree now carries the offset words under
`DSP4_BQ_FLOAT`, including the ones the fixed arm leaves uninitialised:
a swap that carried an unwritten EQ band would otherwise have handed a
strip a ramp.

**One pre-existing defect fell out of doing this.** `_filt_lpf_A/B` had
no float arm at all — it was emitted as Q4.28 unconditionally — so under
session 24's float build every strip FILT's low-pass stage held
`0x10000000` read as a float, which is 2.5e−29, and was **silent**. It
did not show in a cycle measurement, because the instruction count is the
same either way. It is fixed (`_bq_plain_var`), and it is the reason a
capacity arm and an audio arm are not the same bar.

---

## 3. The on-part bar: `bqeverify.sh float`

The gap session 24 named in as many words — "the float kernels' numerics
are modelled, not validated on the part" — is closed, and the vehicle is
the fixed bar's own shape.

    arm A   _bq_fx_cascade_simd    the shipping kernel, float32 OFFSET wire
    arm B   _bqfd_cascade_simd     the same kernel WITHOUT the offset
                                   reconstruction, direct-form wire

Both streams are hashed on-chip and scored against `bq_float_ref` on the
host, over 192 four-stage cascades × 3 drive levels × 4 consecutive
blocks.

| | words/arm | arm A | arm B | A vs B | cells |
|---|---|---|---|---|---|
| block 8 | 18,432 | MATCH | MATCH | 14,810 predicted, 14,810 seen | 566 of 576 |
| block 16 | 36,864 | MATCH | MATCH | 30,910 predicted, 30,910 seen | 567 of 576 |

**0 ULP, both blocks, first run.** That single result validates the whole
chain at once: the reconstruction at 32 significand bits, the DM signal
buffer between stages, the 40-bit recursion, the block-boundary
truncation of the state, the `CLIP` bound and the `FIX` rounding mode. Any
one of them modelled wrongly would have moved the hash.

**The divergence bitmap is what makes it two-sided, and it is not
degenerate.** The BYPASS cascades agree to the bit — offset unity and
direct unity are the same filter and the reconstruction of it is exact —
and every cascade with a pole away from the origin differs. A
reconstruction that quietly did nothing would show as universal
agreement; one that corrupted the identity would show in the first cell.

**One bug in the harness, worth recording because it is the same bug
twice.** The bitmap reader threw away `0xFFFFFFFF` as a dropped SPI
transaction. In the fixed arm 29 of 576 cells diverge and no bitmap word
is ever all-ones; in the float arm 566 of 576 do, so **most words are
legitimately 0xFFFFFFFF** and a healthy part read as a dead link. The
file's own header already warned about exactly this for `_bqev_first`.

---

## 4. GAIN: landed, measured, and smaller than the estimate

`_gsimd_gain_blk` is the block kernel all 32 metered GAIN nodes run, so
the change is one kernel. Its AUDIO word becomes one `FLOAT`, one
multiply, one `CLIP` and one `FIX` in place of the 64-bit extract and the
branch-free saturate: **eighteen instructions per two samples become
eleven.**

**The METER stays fixed, and that is not a compromise.** A meter wants
the PRE-CLIP wide word and an exact sum of squares: `mrb = x·g (ssi)`
gives the full Q8.24 over-range a 32-bit store cannot hold, and MRF
accumulates 80 bits with no rounding and no saturation — which is
order-independent, and is what makes the SIMD split exact. Float would
make both approximate to buy back two instructions. The gain the audio
applies is FLOATed from the same Q4.28 word the meter's MAC uses, so the
two cannot disagree about what gain was applied.

**Measured whole-graph on chip 1: 291,606 → 290,193, i.e. 1,413
cycles/block, 0.43% of budget, 2.76 cycles/sample/strip.** The estimate
carried since RIG C said ~6 c/strip; it was a per-sample figure and the
shipping path is SIMD, which had already halved it. **The dispatch's
instruction to record honestly that the saving is the round-once
contract rather than the format is upheld and sharpened: it is neither.
It is mostly the SIMD path that was already there.**

**And 1.28 of the 2.76 is the INTERLEAVE, not the deletion.**
`FLOAT → multiply → CLIP → FIX` is a four-deep serial dependency. Written
as four consecutive instructions the loop returned only **1.49** of the
3.5 cycles/sample/strip its instruction count had deleted; threading the
meter's `max`, `min` and `mr1b` read — which have no dependence on the
audio word — between the float ops recovers the rest. **The instruction
count is not the cycle count, and a float kernel is more exposed to that
than a fixed one, because float ops have result latency and the fixed
extract-and-saturate had ILP to spare.**

**The D20 mic-pre tap stays, as ruled, and float does not interact with
it.** The tap store is the ROUTER's, not the meter's — pickoff 0,
post-trim — and under float it publishes the post-clip Q4.28 word in the
same place, in the same block, as the same word. What D20's
−17 c/s/strip is blocked on is still the GAIN→FILT coefficient fold, and
float neither helps nor hinders that.

---

## 5. Capacity, whole graph, both chips

Block 16, two boots a point, minimum taken, witnesses clean on every
point. **The instrument reproduces itself to 0.007% on chip 2 and exactly
on chip 1**, both against session 24 and on the arm the whole comparison
hangs off.

| arm | chip 2 | % of 327,680 | chip 1 | % |
|---|---|---|---|---|
| contract, per-stage saturate | 306,939 † | 93.67% | 304,363 † | 92.88% |
| fixed round-once + guard | 264,683 | 80.77% | 292,863 | 89.38% |
| float, direct wire (session 24) | 246,534 † | 75.24% | 290,861 † | 88.76% |
| float, offset wire, fixed GAIN | — | — | 291,606 | 88.99% |
| **float, offset wire + float GAIN** | **249,751** | **76.22%** | **290,193** | **88.56%** |

† carried from sessions 22–24, same scripts on the same bench.

**Chip 2 frees 14,932 cycles/block against the guarded fixed arm — 4.56%
of budget — and 57,188 against the contract, 17.45%. Chip 1 frees 2,670,
0.81%.** Chip 1's smaller win is arithmetic and was predicted: 256 biquad
stages against chip 2's 632, in a graph dominated by GAIN, its meter and
the dynamics.

**The offset reconstruction is the one thing float gives back, and it is
now measured rather than assumed: 3,217 cycles/block on chip 2, 0.98% of
budget** — 5.1 cycles a stage over 632 stages. That is the price of the
46× accuracy improvement, and it is the whole price.

The float image is also **smaller** than the fixed shipping one —
301,580/181,908 bytes against 312,196/191,476 — because the sizer, the
header handling and the whole Q4.28 conversion go with the guard.

---

## 6. Bars

| bar | result |
|---|---|
| `golden_harness.py` | **59/59** |
| `dsp_validate.py` | **OK**, 666 nodes |
| `busgold.sh`, fixed arm | **GRAPH BIT-EXACT**, 0 of 256, sha256 `ba3f52ec` |
| `busgold.sh`, float arm | **GRAPH BIT-EXACT**, 0 of 256, same sha256 |
| `bqeverify.sh float`, block 8 | **PASS**, 0 ULP, bitmap exact |
| `bqeverify.sh float`, block 16 | **PASS**, 0 ULP, bitmap exact |
| `bqeverify.sh` fixed, RO=0 | **PASS**, 848 words / 29 cells, exactly as predicted |
| `bqeverify.sh` fixed, RO=1 | **PASS**, 0 of 18,432 words differ |
| W0 `DSP4_BQ_FLOAT=0` | `4e89e062` / `4d1d314c` **byte for byte** |
| W0 `DSP4_BQ_ROUNDONCE=0` | `23c1e662` / `e45bb82a` **byte for byte** |
| W0 `DSP4_BQ_GUARD=0` | `2249afea` / `3173acb3` **byte for byte** |

**The float graph reproduces the FIXED bus golden word for word**, which
is a stronger result than it first reads and a weaker one than it first
reads, and the script's own warnings say which. The capture is taken with
BYPASS biquads and UNITY gain, so it says nothing about a loaded cascade
or about GAIN's rounding — **but that is precisely the coverage
`bqeverify.sh float` supplies**, 0 ULP over 192 loaded cascades at three
drive levels. What busgold proves is that everything AROUND the changed
kernels — the routing, the dynamics, the delays, the bus, the parameter
plane, the crossfades — is untouched, and that bypass and unity are still
exactly transparent through the float path. The two bars together cover
what neither covers alone.

No contract file was touched and no contract version moved.

---

## Still open, named rather than glossed

1. **The crossfade path is not bit-identical to steady state under
   float and cannot be.** `_bq_fx_cascade_N` holds the cascade value in a
   register across stages while the block kernel passes it through a
   32-bit DM word. Carried from session 24; it is a property of the loop
   shape.
2. **The gate/talkback SIDECHAIN filters are still unsized**, and float
   does not change that — it removes the need. They reach ‖h‖₁ = 150.7 at
   HPF 8k / LPF 8k / Q 10 in the fixed arm; in float the exponent absorbs
   it and the header word they carry for shape is inert. The open item is
   now only against `DSP4_BQ_FLOAT=0`.
3. **The offset form IN the recursion** — ~0.003 dB for ~3% of chip 2
   (§1). Priced, not taken.
4. **A PM-resident 40-bit state** — ~12 dB on the LF shelf, nothing on
   the response table, ~2.7% of chip 2 in DM and no cycles in PM, which
   chip 1 has not got. Priced, not built.
5. **The float arm has never been run with a real coefficient swap on a
   configured chip 2.** Chip 2 is not configured on this bench, so its
   cascades run at bypass; the on-part numeric proof comes from
   `bqeverify`'s loaded vectors, which is a different vehicle to a live
   graph. Same caveat the guard session carried.
