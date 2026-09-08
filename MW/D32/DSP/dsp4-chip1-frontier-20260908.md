provenance: AI-drafted 2026-09-08 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Chip-1 capacity frontier — the routing fabric and the delay's two passes

**Session 27, 2026-09-08. Chip 1 goes 88.40% → 79.87% of the part at
block 16 with the full market config active, and it stops being the
tighter of the two chips.** 27,947 cycles/block back, 8.53% of the
budget, from two changes that are bit-exact by construction and prove it
on the part. The margin goes from 11.60% to **20.13%** — 65,962 cycles a
block clear.

Both levers are generated-code efficiency. No numeric ruling was needed
for either, no contract file was touched, no D5 change, and the shipping
per-sample image and all three recorded W0 witnesses rebuild byte for
byte.

---

## 1. The headline

Whole graph, chip 1, block 16, 983.04 MHz, **the full market config**
(31-band GEQ on every program output — the graph session 26 measured),
32 strips fused + paired, two boots a point, minimum taken, every point
witnessed before its number was accepted.

| arm | cycles/block | % of 327,680 | Δ vs control | margin |
|---|---|---|---|---|
| control — both levers off | 289,676 | 88.40% | — | 11.60% |
| bus-major routing fabric only | 278,938 | 85.13% | −10,738 (−3.28%) | 14.87% |
| delay two-pass split only | 272,819 | 83.26% | −16,857 (−5.14%) | 16.74% |
| **both — the new default** | **261,729** | **79.87%** | **−27,947 (−8.53%)** | **20.13%** |

The last row is the **landed** image — the one with the C-ABI fix of §7
in it. The same arm before that fix read 261,718, eleven cycles away
(0.003%), which is what says a register rename of identical instruction
count cost nothing.

**The two levers are additive to within the instrument's own noise**:
10,738 + 16,857 = 27,595 against 27,947 measured, a 352-cycle
discrepancy (0.11% of budget) where the control's own two boots are 809
cycles apart. They touch different nodes and different memories, and the
measurement says so rather than assuming it.

**The instrument reproduced itself before any difference was believed.**
The control arm re-measured session 26's chip-1 market-config figure at
289,676 against 289,847 — **0.06%**, and 0.008% against the first
single-boot control taken hours earlier this session (289,825). Every
number above is a difference between two points taken on one bench in
one session, on a graph generated from one csv.

**Chip 1 is no longer the tight part.** It was 88.46% against chip 2's
83.16% — tighter by 5.3 points. It is now **79.87% against chip 2's
83.14%** (re-measured this session, §8), looser by 3.3 points, and the
next capacity question is chip 2's again.

---

## 2. D22 — what the routing floor actually is, measured

The review's D22 said RTG was 15–29× over floor and called it the
largest gap in the strip. The control-rate epoch counter closed the
*prep* half of that in session 4. What was left is the **accumulate**,
and this session priced it rather than estimating it.

`DSP4_RTG_NOACC=1` deletes the per-strip crosspoint accumulate and
nothing else — the ramps, the pickoff resolution, the list build and the
control gate all stay exactly where they are — so the whole-graph
difference is that accumulate and only that accumulate.

**289,676 − 273,521 = 16,155 cycles/block, 4.93% of the part's budget,
for 64 live crosspoints × 16 samples = 1,024 MACs. That is 15.78 cycles
per MAC against a floor of about one.** D22's headline number is
therefore confirmed on the part at the bottom of its stated range, and
it is confirmed *for the accumulate*, which the finding had attributed
to the prep.

### The gap is the accumulator's address, not the arithmetic

The per-strip form is **crosspoint-major**: for each of a strip's live
crosspoints it walks the block, and for every sample it loads the bus's
whole 80-bit `[lo, hi, ex]` triple into MRF, does one MAC, and writes
all three words back (`_acc64_mac_blk`, eleven instructions plus the
loop and the call). Eleven instructions to move one number into a sum.

**Bus-major amortises that.** A bus accumulator is loaded once per
sample, every strip that feeds it MACs into the live MRF, and it is
stored once. The per-sample cost stops being 16 × (crosspoints) and
becomes (fixed) + (per-strip) × (live span) **per live bus** — bounded
by the number of buses rather than by how densely the console is
patched, which is the property that matters for a real mix rather than
for this bench's two-crosspoint default.

Measured: **the fabric returns 10,738 of the 16,155.** What remains is
5,417 cycles/block for the same 1,024 MACs plus the parking copy and the
column publish — **5.29 cycles per MAC, down from 15.78, a 2.98×
improvement on the accumulate path.** Still ~5× over a one-cycle floor,
and the remaining gap is named in §6 rather than hidden.

### Reordering the sum is exact, not approximate

The accumulator is an 80-bit MRF integer accumulate with no rounding
until `_acc64_rns28` at readout (review finding D1). Partial sums cannot
round, so the sum is order-independent and the bus-major order produces
the same bits as the crosspoint-major one. **`busgold.sh` is what proves
that, not this paragraph** — see §5.

### Three things the fabric has to get right

* **The pool.** A strip's post-fader block lives in the shared 8-slot
  pool and is dead the moment the next strip runs, so a pass that runs
  after all 32 strips cannot read it. Each ROUTING node parks its own
  block in `_rtg_src[strip]` on the way past — BLOCK words, two
  instructions each, ~1,024 cycles/block at BLOCK=16 against the 16,155
  being bought. That copy is the whole price of deferring.
* **What stays sparse.** A send with a non-default pickoff reads a tap
  (post-trim, post-EQ, pre-fader) that is *not* parked. Those
  crosspoints keep their entry in `_rtg_list` and their old
  `_acc64_mac_blk` call, and the dense matrix carries a zero for them.
  In the shipping default every pickoff is PostFdr and the list is
  empty — but the path is **correct rather than merely unused**, and
  that is what licenses the dense half to assume one source per strip.
* **Ownership.** `_xpc` is bus-major, `_xpc[bus * 32 + strip]`, and each
  ROUTING node writes only its own **column** — 25 words at stride 32,
  in the order of `_bus_acc_all_ptrs`. Two strips can never race. A
  strip outside `DSP4_STRIPS` never writes and keeps the zeros the file
  initialises, and zero times whatever `_rtg_src` holds is exactly zero,
  so an unwritten source block cannot contribute.

`_xp_lo` / `_xp_hi` hold the first and last strip with a live
coefficient on each bus, so a bus fed by four adjacent strips costs four
MACs and not thirty-two. They are rebuilt only when a ROUTING node has
re-prepped (`_xp_dirty`), which the control-rate gate already makes
rare, and they initialise **empty** (lo > hi) so the first block
accumulates nothing rather than something.

---

## 3. D25's delay remainder — the bigger lever, and it was the memory

D25 named "DLY's per-sample address regeneration" and marked the L2
latency share **needs measurement**. Session 4 took the addressing half
(circular DAG addressing, 17 → 5 instructions/sample). The record still
carried DLY at 63 cycles/sample of which only 8.4 was address
arithmetic. This session measured the rest.

`DSP4_DLY_NOMEM=1` deletes the delay line's **read** from the
interleaved control loop and keeps everything else. **289,676 − 268,249
= 21,427 cycles/block, 6.54% of budget, 41.85 cycles per sample per
strip.** So the record's "63 minus 8.4" was memory, and now it is
measured instead of inferred.

The block kernel alternated a **write** into the delay line with a
**read** from a different address in it, per sample, and the delay lines
live in L2. Writing the whole block and then reading the whole block is
the same arithmetic in two sequential bursts, and it costs one loop
instead of one turnaround per sample.

**Measured: the split recovers 16,857 of the 21,427 — 79% of the entire
L2 read cost — without deleting a single read.** That is the largest
single lever this session found, and it is bigger than the routing one
the dispatch led with.

### Why it is bit-exact, written out rather than asserted

Sample *k* writes index `w + k` and reads index `w − off + k`.

* A read that lands inside **this** block's writes is one with `k ≥ off`,
  and the sample it wants was written at `j = k − off`, which is
  strictly earlier than `k`. It has therefore already been written in
  the interleaved order too, so writing the whole block first cannot
  change what any read sees.
* Reads with `k < off` see the previous block, untouched either way.
* `off = 0` is the same argument with `j = k`, and there the interleaved
  loop also writes before it reads.

Both cursors still advance by one per sample with the same `L`, so the
DAG wrap and the write pointer handed back are unchanged.

**The stored bus golden cannot test the interesting case.** It is taken
at DlyOff = 0, which is the one offset where the read index equals the
write index. The case that separates the two forms is `0 < off < BLOCK`,
where a block's reads land *partially* inside its own writes — so
`busgold.sh` gained a `DLYOFF` knob and `dsp4_pairgraph.py` a `--dly`
argument, and the two forms were captured at DlyOff = 7 and compared
against **each other**, in one session. §5 has the result.

---

## 4. D20's remaining fold prices at zero

What is left of D20 after PW's tap ruling is deleting GAIN's store into
the chain ping-pong: the round and the saturate feed the post-trim tap,
which the router reads as pickoff 0 and which PW ruled stays.

`DSP4_GAIN_NOCHAIN=1` replaces that store with a `nop` — the same
instruction count the fold would reach, without building the fold — so
the whole-graph difference is the fold's **ceiling**, measured rather
than counted. FILT then reads a stale block, which costs the same cycles
(a biquad's cost is data-independent) and is wrong by design: a price
tag, not a mode.

**261,718 → 261,743. The difference is −25 cycles, 0.008% of budget, and
it has the wrong sign.** The fold's ceiling is zero.

That is a result, not a failure to find one. The store sits in the
shadow of the float GAIN kernel's serial dependency chain — session 25's
lesson, that the instruction count is not the cycle count, in the other
direction. **D20 should be closed as priced-at-zero**: the remaining
half of it would buy nothing on the part and would cost a numeric-spec
amendment (folding g into stage 1's b0/n1/n2) and an on-demand
materialisation of the post-trim tap. Not worth doing, and now that is a
measurement rather than an opinion.

---

## 5. Bars

| bar | result |
|---|---|
| `golden_harness.py` | **59/59** |
| `dsp_validate.py`, shipping csv | **OK**, 666 nodes |
| `dsp_validate.py`, market-config csv | **OK** |
| shipping `src/` regenerated from shipping `dsp.csv` | **file-for-file identical** |
| `busgold.sh`, fabric ON + split ON, vs the stored golden | **GRAPH BIT-EXACT**, 0 of 256 words differ |
| `busgold.sh` at **DlyOff = 7**, split vs interleaved, paired in one session | **GRAPH BIT-EXACT**, 0 of 256 |
| the same two captures vs the DlyOff = 0 golden | **256 of 256 differ** — the positive control that `DLYOFF` reaches the part |
| W0 `DSP4_BQ_FLOAT=0` | `4e89e062` / `4d1d314c`, 312,196 / 191,476 — **byte for byte** |
| W0 `DSP4_BQ_FLOAT=0 DSP4_BQ_ROUNDONCE=0` | `23c1e662` / `e45bb82a`, 301,764 / 182,092 — **byte for byte** |
| W0 `DSP4_BQ_FLOAT=0 DSP4_BQ_GUARD=0` | `2249afea` / `3173acb3`, 301,732 / 182,060 — **byte for byte** |
| float default `./build.sh` | `906a70f7` / `3a2d930c`, 301,580 / 181,908 — the sizes session 25 recorded |
| block-16 profiling image, **both flags off**, vs the same build from HEAD | `fb182054` / `13b3254f` — **byte for byte, both chips** |
| chip-2 image, every arm | `13b3254f` — **byte-identical throughout** |

**The stored-golden bar is the one that matters for D22**, and it is
worth saying exactly what it does and does not cover. It proves that
reordering the crosspoint sum from crosspoint-major to bus-major changes
nothing at the bus, that the parking copy delivers the same block the
old path read, and that the delay's two passes produce the same samples
at DlyOff = 0. The script's own warnings say what it cannot cover: the
capture is taken with bypass biquads and unity gain, so it says nothing
about GAIN's rounding or a loaded cascade — neither of which either
change touches.

**The DlyOff = 7 pair is a bar this tree did not have before.** The
stored golden is taken at delay zero, which is the single offset where
the read index equals the write index; the interesting case for a
two-pass delay is `0 < off < BLOCK`. The two arms were built from one
tree, flashed and captured in one bench session, and compared against
each other rather than against a stored file — so the comparison carries
no stale-golden risk at all.

**The flags-off block-kernel image being byte-identical to HEAD's is
what makes every arm above a paired measurement.** All the new code is
inside `#if` arms; with the flags off the assembler emits the previous
image to the byte, on both chips. The control arm is therefore literally
the old firmware, not a rebuild of something like it.

---

## 6. What this does NOT say

* **No audio.** Chip 2 is not audio-configured on this bench and every
  cascade runs at bypass, which is cost-identical. This is a cycle
  result, not a listening one. What the bit-exactness bars cover is the
  *bus sums and the graph*, which is exactly where both changes live.
* **The fabric is still ~5× over a one-cycle MAC floor.** The remaining
  gap is the inner accumulate's load-use interlock — `r4 = dm(i1, 1)`
  is read by the MAC in the next instruction — plus the 80-bit triple's
  load and store per bus per sample. A software-pipelined inner loop
  that hoists the coefficient fetch one iteration ahead is the next
  step, and it is worth roughly the residual 5,417 minus the parking
  copy. Not taken this session; the padding word in `_rtg_src` is
  already there for it.
* **The bench patch is two crosspoints a strip.** The fabric's advantage
  *grows* with patch density (its cost is bounded by buses, the old
  form's by crosspoints), so 10,738 is the saving on the sparsest
  realistic console, not the best case. A densely patched mix would save
  more, and that has not been measured.
* **The delay split was measured at DlyOff = 0 for cycles** (the
  shipping default on this bench). The two-pass form's cost is
  offset-independent by construction — same two loops, same counts —
  but the *cycle* figure is a DlyOff = 0 figure.
* **The market config is still a generator parameter, not the shipping
  graph.** Nothing in `MW/D32/DSP/SHARC/dsp.csv` changed. Adopting the
  market bar remains a PW contract decision.

---

## 7. One real defect found by landing it

**The crosspoint publish was using `i7`, `l7` and `m7` as scratch, and
all three are C-ABI registers.** `c_abi.h`'s `C_RUNTIME_INIT` sets
`m7 = -1` exactly once at boot, and every `CCALL` and `C_RETURN` in the
tree reads it without setting it; `i7` is the C stack pointer itself. No
node in the tree had ever written `i7` before this pass — it is set once,
in the runtime init, and never again.

It is survivable today only because nothing after boot uses the C stack:
the three C functions (`_sru_init`, `_sport_cfg_init`, `_dma_cfg_init`)
are all called from the init path, before any routing node has run, and
the whole run loop including `_spi_poll` is assembly with `call`/`rts`
on the hardware PC stack. **That makes it a trap for whoever adds the
first C call or C ISR to the run loop, not a bug anyone would see** —
the class of defect that is found by reading the register allocation, or
by a crash three sessions later.

Moved to `i1` / `m4`: `m4` is ordinary node scratch (91 sites in the
tree set it before use) and `i1` is free in that section. Same
instruction count, same image size (405,304 bytes both ways), so the
cycle figures above are unaffected — and the headline arm was
**re-measured on the fixed image** rather than carried.

---

## 8. Cost and where the code went

| | control | with both levers |
|---|---|---|
| chip-1 code (VISA SW) | 256,402 words, 97.8% | 256,566 words, 97.9% |
| chip-1 DM objects added | — | **1,379 words** (`rtg_fabric.doj`) |
| chip-1 block-16 image | 399,620 bytes | 405,304 bytes |
| chip-2 image | 307,280 bytes | **307,280 bytes — byte-identical** |

The 1,379 DM words are `_rtg_src` (33 × BLOCK), `_xpc` (25 × 32),
`_xp_lo`/`_xp_hi` and the dirty flag, read straight off the link map per
object. `dsp_memreport.py`'s pool total moves by more (+5,520) because
the primary DM block is full and the new objects land in the overflow
region with its placement padding; the object figure is the honest one.

**Chip 2 is byte-identical on every arm**, which is a stronger statement
than a re-measurement: the fabric is `CHIP_ID == 1` only and the delay
split is inside the chip-1 block kernel, so chip 2's cycles cannot have
moved. **It was re-measured anyway, whole chain, market config, two
boots: 272,421 c/blk = 83.14%, against session 26's 272,505 = 83.16%.
0.03% apart — unmoved, as the identical image requires.**

That run also carries an incidental confirmation worth recording: chip
2's inter-chip RX witness reads `MAIN_L = 0x08000000`, `AUX_01` and
`GRP_01` likewise. **The buses are carrying signal with the bus-major
fabric doing the accumulate** — a fabric that had quietly left the
accumulators at zero would show as a silent witness and a cheaper chip
2, and it shows as neither.

---

## 9. Flags

| flag | default | what it is |
|---|---|---|
| `DSP4_RTG_FABRIC` | **1** | the bus-major crosspoint fabric. `=0` is the control and rebuilds the per-strip accumulate byte for byte. Forced off without block kernels — there is no per-sample form, since the whole point is amortising a per-block accumulator load |
| `DSP4_DLY_SPLIT` | **1** | the delay line's two passes. `=0` is the control and rebuilds the interleaved loop byte for byte |
| `DSP4_RTG_NOACC` | 0 | measurement arm: deletes the crosspoint accumulate. Buses stay at zero — silence by construction |
| `DSP4_DLY_NOMEM` | 0 | measurement arm: deletes the delay line's read from the control loop. Audio wrong by design |
| `DSP4_GAIN_NOCHAIN` | 0 | measurement arm: replaces GAIN's chain store with a nop, to price D20's fold without building it |

`captable.sh` gained **`XFLAGS`**, which carries an arm's build flags
into the build *and into the build directory's name* — srckey's and
CSVTAG's reason one level down: two arms measured in one session must
not share a build directory, or the second point boots the first one's
image and reports the first one's number as a difference. An empty
`XFLAGS` names exactly the directory every earlier session used.
