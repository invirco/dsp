provenance: AI-drafted 2026-09-09 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S13 — the half that fits D32 made audio-correct, and the audio arms' stimulus

Bench: rev C unit, shipping CPLD `a1f6672af6c3`, `dsp4-pcm-slave`,
contract `defs-v2026.09.08.4`. Every image from its own staging path.
`blk_*` and `cand_*` byte-identical at the end of the session.

## 1. S12-5 settled — `DSP4_C2_BQ_GRAPH` IS audio-correct now

**It wasn't, because the pair's steady test never read the pending-DESIGN
flag, and the write was dropped UPSTREAM of the latch rather than at it.**

Chip 2's paired biquad drivers latch the interleaved coefficient and state
arrays and skip the two node bodies while both channels are steady. The
generator's own note claimed the latch was safe because "every write to the
coefficients goes through `_<pfx>_coeffs_next_` and `_<pfx>_swap_pending_`,
and swap_pending is one of the two words the steady test reads."

That is true for the classes the host writes COEFFICIENTS to — `eq`, and
the OEQ/GRP cascades that share its prefix. It is false for every class the
host writes PARAMETERS to. A GEQ takes 31 band gains, an AFB takes six
(freq, gain, Q) notches, a crossover takes corner frequencies. The host
writes those and sets `_<pfx>_dirty_`; the DESIGN that turns them into
coefficients runs at the top of the node body —

    r4 = dm(_geq_dirty_C2_AUX_GEQ_01);
    r4 = pass r4;
    if ne call _geq_redesign_C2_AUX_GEQ_01;

— which is the body the latch exists to skip. Latched, the design never
ran, so `swap_pending` never rose, so the steady test never fired, so the
latch never came down. The pair ran the `.var` bypass initialisers for
ever and the whole designed filter was lost. `bqeverify` passed all along
because the SIMD arithmetic was never the problem.

18 of the 24 chip-2 pairs are affected: 12 GEQ and 6 AFB. The 6 EQ/OEQ
pairs were always correct, and so is chip 1's `DSP4_BQ_GRAPH` — chip 1 has
no design-driven class at all (no `_dirty_` flag exists on chip 1), which
is why the S12 candidate read clean.

**The fix** (`tools/dsp/dsp_codegen.py::gen_bq_pairs_c2`): the steady test
reads `_<pfx>_dirty_` for any class that has one, guarded on that class's
`DSP4_<CLS>_DESIGN` macro — a DESIGN=0 build has nothing that clears
dirty, and an uncleared dirty would pin the pair to the scalar path for
ever. Two DM reads and an OR per pair per block. A dirty node now takes
the pair down to the scalar path, the design runs, the crossfade runs, and
the pair re-engages on the NEW active bank.

### Proven three ways, one image, `DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1 DSP4_C2_BQ_GRAPH=1`

| arm | before | after |
|---|---|---|
| geqverify coefficients, live bank | IDENTITY, 50,965,640 ulp | **1–3 ulp** |
| geqverify modelled response | −12.00000 dB (the whole filter) | **≤ 0.00014 dB** |
| afbverify coefficients, live bank | IDENTITY, 83,887,018 ulp | **2–4 ulp** |
| afbverify modelled response | +18.00000 dB | **≤ 0.00009 dB** |
| famverify GEQ | INERT paired (moved 0/64) | **LIVE, moved 64/64**, peak 0x08000000→0x082DE520 |
| famverify ANTI_FB | INERT paired (moved 0/64) | **LIVE, moved 64/64**, peak →0x07FB92D0 |
| bqeverify (float arm) | PASS | **PASS**, 0 ulp over 36,864 words, 567/576 divergence cells as modelled |

famverify on the paired arm: **17 of 20 families LIVE, contract 20/20 with
0 FAILED, COMPRESSOR / FADER_PAN / TUBE_SAT BIT_EXACT** — verdict for
verdict what the shipping pair reads. The three non-LIVE are
AUX_INPUT NO_STIMULUS_PATH, DCA NO_PROBE and METER NO_PROBE, all
structural.

## 2. D32 FITS on an audio-correct image

`capacity.sh`, block 16, CCLK 983.04 MHz, budget 327,680 cycles/block,
`cfg2 0xC201024F` (Option A, tx_early 2, gather_first 1) read back on the
part. Two boots per arm, ~135,040 blocks each.

| arm | chip | avg boot 1 | avg boot 2 | overruns |
|---|---|--:|--:|--:|
| **D32 all-ones, `C2_BQ_GRAPH=1`** | 1 | 76.73 % | 76.96 % | **0** |
| | 2 | **82.06 %** | **82.49 %** | **0** |
| **D24 mask, `C2_BQ_GRAPH=1`** | 1 | 59.16 % | 59.13 % | **0** |
| | 2 | 67.91 % | 67.57 % | **0** |

Worst-block: chip 1 72.53 / 72.42 % and chip 2 71.29 % at D24, chip 1
93.76 % at D32 boot 1. **`_proc_cyc_max` is not trustworthy across boots
and the reason is in its definition** — it is "the worst block pass seen
since reset" and nothing resets it after the boot and config ladder, so it
latches a one-off configuration-block transient. The same image read
71.29 % on one boot and 367.58 % on the next with zero overruns on both.
`DIAG_BLK_OVERRUN` is the arbiter and it is 0 everywhere above, over
540,000 blocks. The max column should be read as "a boot transient or the
steady worst, and the counter cannot tell you which" until it is reset
after config.

### The decision table

| | `blk_*` (ships) | `cand_*` (S12) | `geq_*` (S13) |
|---|---|---|---|
| switches | all off | FUSED+SIMD_DYN | FUSED+SIMD_DYN+C2_BQ_GRAPH |
| D24 chip 1 avg / worst | 71.5 / 84.8 % | 72.4 % worst | **59.2 / 72.5 %** |
| D24 chip 2 avg | 92.7 % | 83.2–83.5 % | **67.6–67.9 %** |
| **D32 chip 2 avg** | — | **102.5–102.7 %, 2.37 % blocks missed** | **82.1–82.5 %, ZERO missed** |
| parameter changes | correct | correct | **correct (S13-1)** |
| famverify | 17/20 LIVE | 17/20 LIVE | **17/20 LIVE** |
| chip1 / chip2 md5 | `ac65ad38…` / `e5dce9e4…` | `fcebc2e1…` / `86662b92…` | `df6b847d…` / `cb9bc58e…` |

**D32 fits on an audio-correct image with 17.5 % of chip 2's budget spare.**
Nothing is proposed for adoption here; that is PW's call.

## 3. S12-9 attributed — it was the instrument, and the audio was never in question

On the pair that SHIPS, afbverify's −18 dB notch measured −4.799 dB and
geqverify's +12 dB band +8.451 dB, where the same bars read −17.99989 dB
on the per-sample block-8 image of 2026-09-08. Identical to every digit on
every block-kernel image, scalar and paired.

**`_scope_inject_blk` runs once per BLOCK and drove the amplitude into
sample 0 every time it ran.** `mode 1` on a block-kernel image was
therefore not an impulse but an IMPULSE TRAIN at one per block — 3 kHz at
block 16 — and the audio arms measured that train's periodic steady state.
The raw capture says so directly: the flat run holds exactly 64 non-zero
words in 1024, at indices 0, 16, 32, …

Modelling the train through the same designed cascade reproduces the bar's
three points to three decimals:

| probe | measured on the part | impulse train, modelled | true impulse |
|---|--:|--:|--:|
| quarter, 250 Hz | +0.219 dB | **+0.219 dB** | +0.060 dB |
| centre, 1000 Hz | +8.451 dB | **+8.451 dB** | +11.997 dB |
| four ×, 4000 Hz | −0.305 dB | **−0.305 dB** | +0.058 dB |

The per-sample injector `_scope_inject` has always had the gate
(`_scope_go == 0` is the first sample of the run). The block injector was
written without one — and it cannot borrow `_scope_go`, because under
block kernels BOTH injectors run in every block and the per-sample one
raises `_scope_go` first, so gating on it silences the block injector
completely (measured: an all-zero capture). It gets `_scope_fired`,
cleared by the same arm write.

After the fix, on the shipping configuration AND on the paired arm:

| bar | centre | model | verdict |
|---|--:|--:|---|
| geqverify +12 dB band | **+11.997 dB** | +12.000 | **GEQ_DESIGN_OK** |
| afbverify −18 dB notch | **−18.000 dB** | −18.000 | **AFB_DESIGN_OK** |

famverify is unchanged by the fix at 17/20 LIVE, contract 20/20.

**A second, smaller instrument defect, recorded not fixed:** geqverify's
flat negative control prints "64/64 samples equal to the input" when both
captures are all zeros, because zero equals zero. It did not mislead — the
verdict also requires `peak > 0` and correctly failed — but the printed
line is not evidence on its own.

## 4. S12-8 — xoververify no longer stalls

`_buf_lp_<nid>` and `_buf_hp_<nid>` are ONE-WORD variables. Under block
kernels the crossover runs its per-sample body BLOCK times through them,
so each holds the last sample of the block and there is no `_blk_lp_`
array; nothing registered them with the block-aware witness, so the bar
armed on an address no tap answered for and waited for a buffer that never
filled. The chain now registers both with `_scope_tap1`, the same
one-word-per-block witness TALKBACK and NOISE_GEN use.

The bar runs to a verdict and its design arms pass: **1–4 ulp staged,
live == staged, LP and HP both −6.021 dB at the corner, response error
≤ 0.00013 dB, LP+HP flat to 0.00013 dB, across BOTH LR alignments (12 and
24 dB/oct) and all five corner frequencies**, with the non-LR slopes
correctly leaving the coefficients unmoved.

**Its AUDIO arm is declared NOT SCORABLE rather than scored wrong.** A
one-word-per-block witness samples at 3000 Hz, and a single impulse falls
in the fifteen samples out of sixteen the witness does not keep, so the
reference reads zero. The bar now says that per probe point instead of
printing `nan`, and drops any point above the block-rate Nyquist. Scoring
this arm needs a `_blk_lp_`/`_blk_hp_` array in the crossover's block
kernel — a change to the SHIPPING image for a bench instrument, not taken.

## 5. The GEQ primitive — the floor is reachable by SCHEDULING ONE cascade

Not built, not measured. What was established, and what it changes about
the plan:

The float SIMD inner loop `.bqfl_ssamp` is **8 instructions per sample per
stage for 2 channels**, carrying 11 operations — 5 multiplies (b0·x, b1·x,
b2·x, a1·y, a2·y), 4 ALU, one load, one store. Measured 5.94
c/band-sample including the per-stage preamble and the two domain
crossings.

**The assembler is the authority on packing, and it accepts
`mult + ALU + one memory move` in one instruction** — verified by
assembling all four candidate forms against `easm21k -proc ADSP-21564`,
with a negative control (two memory moves) correctly rejected. So the
per-instruction budget is 1 multiply + 1 ALU + 1 move, and the floor for
one cascade is `max(5 mult, 4 ALU, 2 moves) = 5 instructions per sample
per stage` = **2.5 c/band-sample** in the inner loop.

**The dispatch's plan — two independent cascades interleaved, four
channels in flight — is not the way to get there, and does not fit.** One
cascade already needs 5 coefficients + 2 state + ~5 products + a temp live
at once; two cascades is upwards of 22 registers against the 16 a PE has,
and the alternate register file is a MODE1 write with latency, not a
per-instruction resource.

It does not need to. The recurrence does not bound a 5-instruction
schedule: the loop-carried chain is y → a1·y → w1′ → y, three
dependent operations against five instructions of slack. A steady-state
software pipeline over ONE cascade, offset by one sample, covers it:

    I1:  p2  = x·b2       | w2' = p2ᵖ − q2ᵖ    | load x(n+1)
    I2:  p1  = x·b1       | y   = w1ᵖ + p0     | store y(n−1)
    I3:  q1  = y·a1       | t   = w2ᵖ + p1
    I4:  q2  = y·a2       | w1  = t − q1
    I5:  p0ⁿ = x(n+1)·b0  |

5 multiplies, 4 ALU ops, 2 moves, five instructions, every dependence
one instruction deep or more. Superscripts mark the value carried from the
previous sample.

**What is left is the register allocation and the prologue/epilogue, then
the shootout rig for bit-exactness against `bq_float_ref` and the
measurement.** Nothing about the pair latch, the gather or the chip-2
interleaved arrays has to move, which is the other reason to prefer this
over the four-channel plan.

## 6. RIG B — not reached

The 2156x IIR accelerator was not brought up. The precision test that
decides it is unchanged and still the first thing to run: band 1
(19.95 Hz, Q 4.3185) and band 2 at ±12 dB in the accelerator's float32
against `bq_float_ref`, inside the 0.01 dB bar or not.

## Bars

golden 59/59, dsp_validate OK, test_geq_splice 5/5, test_dsp_validate
13/13, check-contract-drift clean at `defs-v2026.09.08.4`,
check_shipping_config consistent. `shipping.config` is unchanged: the
three cost switches stay at 0 and `DSP4_TX_EARLY=2` stays named.
