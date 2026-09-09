provenance: AI-drafted 2026-09-09 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Capacity, restated on the shipping pair — and the instrument that was not measuring it

**This table replaces the capacity record.** Everything below is at
`BLOCK=16` and the budget is derived from **the clock the part was
running**, read back on every point: `CGU0_CTL 0x00005000`,
`CGU0_DIV 0x451442C1` → **983.040 MHz**, budget **327,680 cycles/block**
(983.04 MHz × 16 / 48,000). `DIAG_BUILD_CFG` read **0xCF45FF10** on both
chips on every boot and `dsp4_buildcfg.py --expect-shipping` passed before
any number was taken.

The clock drift of S9-1 **is fixed in this pair**: the old window pair read
the CGU reset row `0x00002800`; `blk_chip1.ldr` `ac65ad38…` /
`blk_chip2.ldr` `e5dce9e4…` read `0x00005000`.

Instrument: `tools/pi/dsp4_capacity.py`, reading the shipping pair
directly. Two boots per arm, 45 s and ~135,040 blocks per boot at
2,999.9–3,001.0 blocks/s.

## 0. The headline

| | chip 1 `_proc_cyc` | chip 1 worst block | chip 1 OVERRUN | chip 2 `_proc_cyc` | chip 2 worst block | chip 2 OVERRUN |
|---|--:|--:|--:|--:|--:|--:|
| **D24 mask** | 234,267–235,216 **71.5–71.8 %** | 277,752–278,111 **84.8 %** | **0** | 303,891–304,245 **92.7–92.9 %** | 304,874 **93.0 %** | **0** |
| **D32 all-ones** | 306,190–306,512 **93.4–93.5 %** | 361,246–361,377 **110.3 %** | **0** | 369,411–369,424 **112.7 %** | 370,832 **113.2 %** | **15,212–15,213 = 11.26 %** |

* **D24 FITS.** Zero missed blocks on both chips, both boots, 270,000
  blocks total.
* **D32 DOES NOT FIT**, and the failure is chip 2's: it is at **112.7 % of
  budget** and misses **11.26 %** of blocks.

**The cycle count and the overrun rate are the same fact, and they close
to four decimal places.** A pass that takes 1.1274 block periods completes
one block per 1.1274 periods, so it loses 0.1274 / 1.1274 = **11.30 %** of
blocks. Measured: **11.261 % and 11.264 %**. The two instruments — a cycle
counter and a missed-block counter — share no arithmetic and agree.

**S9-3's 11.3 % reproduces** (11.261 % / 11.264 % here against 11.3 %,
1,552 of 13,773, then) on a different day at ten times the dwell.

**And chip 2's D24 figure reproduces S9's to three cycles**: 303,891 here
against 303,894 then.

**S9-3 understated chip 1, though.** It recorded "chip 1 sits at 71.6 %",
which is the **D24** number. At D32 all-ones chip 1 is at **93.5 % average
and 110.3 % on its worst block**. Chip 1 has about six points of average
margin at D32, not twenty-eight. **Any D32 capacity plan that assumes chip
1 is idle is wrong.**

## 1. `_proc_cyc_max` — and it is a chip-1 story, not a general one

`_proc_cyc` is the LAST block pass; `_proc_cyc_max` is the WORST since
reset. The budget has to cover the worst one, and the two chips behave
completely differently:

| | mean | worst | worst / mean |
|---|--:|--:|--:|
| chip 1, D24 | 234,267 | 277,752 | **1.186** |
| chip 1, D32 | 306,190 | 361,246 | **1.180** |
| chip 2, D24 | 303,891 | 304,874 | **1.003** |
| chip 2, D32 | 369,424 | 370,832 | **1.004** |

**Chip 2's block cost is flat to 0.4 %. Chip 1's worst block is 18 % above
its mean, at both masks, on every boot.** That is a periodic expensive
block on chip 1 and it is stable enough to be structural rather than
jitter — chip 1 carries the 38 METER nodes and the ramp engine, and the
meter fold is explicitly a per-block gate (`_mtr_block_tick`).

The consequence for the record: **chip 1's D24 margin is 15.2 %, not
28.5 %.** Every chip-1 margin ever quoted on this project came off
`_proc_cyc` and is 18 % of its own value too generous.

**OVERRUN 0 does not mean every block fitted.** Chip 1 at D32 exceeds the
budget on its worst block (110.3 %) and still reports zero overruns:
`_block_ready` is a flag, so a block that runs 10 % long is absorbed by the
next block's slack, and only a *sustained* overrun is counted. Chip 1 at
D32 is therefore running with no headroom for a second consecutive
expensive block, which nothing currently measures.

One reading was discarded and is recorded rather than dropped silently:
chip 2's `_proc_cyc_max` on the D32 rep-1 boot read **1,351,877 (412.6 %)**
against 370,832 on rep 2. It is a startup transient — the max is
never-reset and the first pass after CONFIG_COMMIT does one-time work —
and it is the reason `_proc_cyc_max` needs a reset before it can be a
production margin figure. Filed as an instrument limitation, not a result.

## 2. The record's instrument was not measuring the shipping image (S10-6)

`sigprofile.sh` / `sigprofile2.sh` / `fxcost.sh` build an **instrument**:
`DSP4_PROFILE_SIGNAL=1` (the input kernels synthesise a ±0.5 square so the
dynamics cannot be measured on their cheap branch) and
`DSP4_BLOCK_DECIMATE=32` (the graph runs on one block in thirty-two, so a
graph that does not fit still completes). Those are right for attributing
cost to a class. They are **not** the image that has to fit, and the gap is
large and **not a constant offset**:

| block 16 | the record's instrument | the shipping pair | gap |
|---|--:|--:|--:|
| chip 1, D24 | **408,939** (124.8 %) | 234,267 (71.5 %) | +174,672 |
| chip 2, D24 | **225,646** (68.9 %) | 303,891 (92.7 %) | **−78,245** |
| chip 2, D32 | **261,093** (79.7 %) | 369,424 (112.7 %) | **−108,331** |

Chip 1's instrument number is *higher* because `DSP4_PROFILE_SIGNAL` and
`TUBEON=1` put all 32 strips on their expensive branch, which a silent
bench does not — that is the documented signal/silence split, and it means
**408,939 is the honest signal-present worst case for chip 1's graph.**

Chip 2's is *lower* by 78,245 cycles at D24 and 108,331 at D32 — 24 % and
33 % of budget — and the signal/silence split would push it the *other*
way. `DSP4_BLOCK_DECIMATE=32` is the remaining candidate: it gives the
graph thirty-two block periods to run in, so nothing in the block loop ever
contends, and whatever chip 2 is paying for contention is invisible to it.
**Not resolved this session**; until it is, a chip-2 margin quoted from
`sigprofile2`/`fxcost` is a margin for the instrument.

## 3. Chip 2, the record's instrument, both masks, both FX arms

`fxcost.sh`, block 16, two boots each, minimum taken, with the
restore-and-re-read control on every boot (drift +0 to +24 cycles, so the
deltas are real).

| chip 2, `fxcost.sh` | default (Type 0 = Echo) | six reverbs (Type 3) | delta | margin loaded |
|---|--:|--:|--:|--:|
| **D24 mask** | **225,646** (68.86 %) | **274,547** (83.79 %) | +48,901 | **16.21 %** |
| **D32 all-ones** | **261,093** (79.68 %) | **310,006** (94.61 %) | +48,913 | **5.39 %** |

**The `.4` record reproduces.** The 2026-09-08 `.4` session measured
261,848 default and 310,185 loaded (94.66 %, margin 5.34 %); this session
reads 261,093 and 310,006 (94.61 %, margin 5.39 %) — 755 and 179 cycles
apart on a different day. The `.4` figures were an **all-ones**
measurement, which is now explicit; they were not annotated as such.

**The six-reverb worst case costs +48,901 cycles/block and is
mask-independent to twelve cycles**, as it must be — the FX engines are not
masked by CHAN/AUX.

**On this instrument the D24 mask is worth 35,447 cycles/block (10.8 % of
budget). On the shipping pair it is worth 65,533 (20.0 %.)** Both are
paired measurements taken in one session; they disagree by a factor of 1.85
for the same runtime mask, which is §2's problem in one line.

## 4. Against every prior record, annotated with what it was actually taken at

The dispatch asked for this explicitly, because until 2026-09-09 no
capacity row on this project recorded its own block size or clock.

| date | figure | BLOCK | CCLK | mask | instrument | still valid? |
|---|--:|---|---|---|---|---|
| 09-03 `.3` | chip 2 256,919 | 16 | 983.04 *assumed* | all-ones | sigprofile2 | as an **instrument** number only |
| 09-08 `.4` | chip 2 261,848 / 310,185 | 16 | 983.04 *assumed* | all-ones | fxcost | **reproduces** (§3), instrument number |
| 09-09 mask | chip 2 −35 k for D24 | 16 | 983.04 *assumed* | both | fxcost | **reproduces** (§3), and see §3's last line |
| 09-09 S9 | chip 1 234,594 / chip 2 303,894 | 16 | 983.04 read | D24 | shipping image | **reproduces** (234,267 / 303,891) |
| 09-09 S9 | D32 chip 2 misses 11.3 % | 16 | 983.04 read | all-ones | shipping image | **reproduces** (11.26 %) |
| 09-09 S9-3 | "chip 1 sits at 71.6 %" | 16 | 983.04 | — | — | **true at D24, wrong as a D32 statement** (§0) |
| pre-09-09 window pair | anything | **8** | **491.52** | — | — | **void** (S9-1) |

"983.04 *assumed*" means the build set `DSP4_CCLK_TARGET=983` and nobody
read the CGU back. Every row from 2026-09-09 onward reads it.

## 5. What is NOT measured here

* **Through-DSP latency at block 16.** Not re-measured. The 72-sample /
  1.500 ms figure on record is a **block-8** number and block 16 should
  roughly double it — that is arithmetic, not a measurement, and the
  alignment contract still carries an unrestated figure.
* **`busgold`, `bqeverify`, `fxverify`, `afbverify`, `geqverify`,
  `xoververify`** on the shipping pair. Not re-run.
* **A fresh per-kernel ladder at all-ones.** §6 is a plan built on the
  2026-09-01 class table plus this session's totals, not a new ladder.

## 6. D32's 11.3 %, decomposed — a plan, not a rewrite

### The target, exactly

Chip 2 at D32 all-ones costs **369,424 cycles/block against a budget of
327,680**. It must lose **41,744 cycles/block — 12.74 % of budget** to
fit, and a further margin on top of that to be worth shipping.

For scale: the D24 mask is worth **65,533** cycles on this same instrument,
so **the eight extra strips and four extra aux buses are the whole
problem** — D32 is not failing on something exotic, it is failing because
the graph is a third bigger and there was never 20 % of margin to spend.

### GEQ is the wall

From the 2026-09-01 chip-2 class profile: 17 GEQ instances at 28 bands is
476 biquad stages per sample, **16,171 cycles/sample = 776 MHz of a 983.04
MHz part**, and `.4` took GEQ to **31 bands = 527 stages** for a measured
**+4,929 cycles/block**. The fusion is not the problem: GEQ measures 37.2
cycles per band-sample against chip 1's fused EQ at 40.5 — the same
`_bq_fx_cascade_blk` performing consistently on both chips. **There is no
obvious inefficiency left inside the cascade to reclaim.**

Three levers, each with an estimated saving and its cost. **PW rules.**

#### Lever 1 — block 32. Estimated saving 5–10 % of budget (16k–33k cycles)

The 09-01 class table is a **measured trend across three block sizes on
this exact graph**, not an extrapolation. Going 16 → 32, cycles per sample
fall: **GEQ 983.4 → 951.2 (−3.3 %)**, **COMP 548.5 → 510.6 (−6.9 %)**,
**AFB 247.9 → 211.2 (−14.8 %)**, **LIM 288.8 → 283.6 (−1.8 %)**. Weighted
by the instance counts that carry chip 2's budget that is 5–10 %, which is
of the same order as the 12.74 % gap and **might close it, or might fall
just short.**

* **Latency:** +16 samples, **0.333 ms**, on top of whatever S9-2's ruling
  adds.
* **DM:** the pool doubles (8 slots × 32 words, plus the odd pool) and both
  DMA halves double. Block 32 is what overflowed DM on 2026-08-24 — but
  that was *before* `blk_pool.h` existed, when every node had its own
  buffer. The pool is the reason to think it fits now. It has not been
  built at 32 since, so **this is the first thing to try and the first
  thing that could fail.**
* **Panel MCU:** every ramp frame count halves **again**
  (`ghost_cells.h` is generated from the block size), so H1S3/H1S4 rebuild
  in the same window as the firmware — exactly as block 16 already
  requires.
* **Risk: low to moderate.** It is a generator parameter, the tree is
  regenerated from `DSP4_GEN_BLOCK`, and `build.sh` refuses a tree that
  disagrees with the configuration. **One build tells you whether it
  links; one boot with `dsp4_capacity.py` tells you whether it fits.**

#### Lever 2 — fewer GEQ bands on D32. Saving 1,643 cycles/block per band

Measured, not modelled: +3 bands on 17 instances cost **+4,929
cycles/block** at `.4`, i.e. **1,643 cycles/block per band across the
graph**. 31 → 28 bands recovers 4,929 (1.5 % of budget); 31 → 21 recovers
about 16,400 (5.0 %). **On its own it does not close 12.74 %** unless the
band count comes down a long way.

* **Cost:** a **product** decision. 31-band GEQ is the market bar the `.4`
  contract was cut for, and taking it back on D32 while D24 keeps it is a
  two-product contract divergence in a repo whose architecture is one
  firmware and one address map.
* **Risk:** contract churn. Every chip-2 address moves again, as it did at
  `.4`, and the panel MCU and app rebuild with it.

#### Lever 3 — run the FX reverb tail at half rate. Saving up to 24,450 cycles/block

The six-reverb worst case is **+48,901 cycles/block, 14.9 % of budget** —
the largest identified block of chip-2 cost after GEQ. Half-rate with
interpolation halves it, which **would close the gap on its own**.

* **Cost:** an audible change to the reverb, and a real DSP design task
  rather than a build flag. Not window-scale work.
* **Risk: high** — it changes what the product sounds like, which none of
  the other levers do.

#### What is NOT a lever

* **The float path.** Already landed, and `DSP4_BQ_GUARD` is *derived* 0 in
  a float build, so the guard's cost is already gone. No headroom left
  there.
* **Chip 1.** §0 — chip 1 is at 93.5 % average and 110.3 % worst at D32.
  There is nothing to move onto it.

### The recommendation to put to PW

**Try lever 1 alone, first, and measure it with `dsp4_capacity.py` on a
shipping-configuration image.** It is the only lever that costs neither
product scope nor sound; its saving is estimated from a measured trend
across three block sizes on this exact graph; and one build plus one boot
settles it. If block 32 links and closes the gap, D32 ships at block 32
with 0.333 ms more latency and nothing else changes.

If it does not, the remaining choice is genuinely between **product scope**
(lever 2) and **sound** (lever 3) — and that is PW's to make, not the
DSP's.
