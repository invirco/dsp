provenance: AI-drafted 2026-09-02 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# GAIN kernel rewrite — what it cost, what it bought, and why 1–2 c/s is not reachable

Dispatch: *"GAIN kernel rewrite — fold polarity/mute to control-rate, block+SIMD,
mic-pre tap kept, 22.9 → 1-2 c/s"*, 2026-09-02 12:38Z, under the D20 ruling that
GAIN stays a separate node because its output is the clean mic-pre recording tap.

## 1. The headline, said plainly

**Two of the four things the dispatch asks for were already in the tree, one
landed, and the target number cannot be reached without reversing a ruling.**

| the dispatch asks for | state |
|---|---|
| ONE effective gain word at control rate — polarity as sign, mute as 0.0 | **already there** since the 2026-08-25 crosspoint-coefficient mandate (`gen_gain_fixed`, the `.cvt_` section). Zero per-sample cost for either, today and before this session. |
| block kernel with a hardware loop | **already there** since the 2026-08-28 block-kernel conversion. |
| SIMD pairing | **LANDED** — but across two adjacent SAMPLES of one channel, not across two channels. See §3. |
| both stores kept, tap placement bit-identical | **held**, and checked two ways. |
| no contract change | **held** — `dsp_validate.py` OK, no contract file touched. |
| 22.9 → 1–2 c/s | **NOT REACHED, AND NOT REACHABLE.** See §2. |

## 2. Why 1–2 c/s was never a number this node could hit

The 1–2 comes from `review-dsp-20260828.md`'s cost table, and that row states its
own condition: **"1–2 (under the GAIN=1MAC fold)"**. The fold was GAIN's gain
scaled into FILT's `[b0, n1, n2]` at control rate, which deletes GAIN's sample
path entirely — one MAC, folded into a filter that was going to run anyway.

**PW's D20 ruling of 2026-09-02 REJECTED that fold**, for a product reason: GAIN's
output is the clean mic-pre tap, so it must stay its own node with its own output.
The number and the design that produced it were rejected in the same ruling, and
the dispatch carried the number forward without it.

What GAIN actually is, per sample, once polarity and mute are already folded:

| | instructions | ruled by |
|---|---|---|
| the gain multiply | 1 | this is the "one MAC" |
| the rounding half | 1 | D5 numeric contract (`rns`, round half toward +inf) |
| Q4.28 extract + saturate | 10 | D5 numeric contract |
| chain-slot store | 1 | feeds FILT |
| mic-pre tap store | 1 | **the D20 product feature** |
| wide-word meter | 4 | PW ruling 2026-08-29 |
| **total** | **18** | |

**Exactly one of those eighteen is the multiply.** Reaching 1–2 c/s means deleting
the other seventeen: the numeric contract (D5), one of the two stores (D20), and
the meter (2026-08-29). Each is a standing decision, not an optimisation that has
not been done yet. The honest statement is that **GAIN's floor under the rulings
that presently apply is around ten instructions per sample, not one**, and this
session took it most of the way there.

## 3. The design, and where it departs from the dispatch

The dispatch specifies *"SIMD pairing across channels"*, which is what the paired
biquads and the paired dynamics do. **This pairs two adjacent samples of ONE
channel instead, and the difference is the whole reason it is worth doing.**

Channel pairing needs its operands interleaved. `_bq_pair_blk` gets them by
gathering two strips into a scratch buffer and scattering back — about
4 cycles/sample/strip, which a 2-stage cascade costing ~51 can afford. GAIN's
entire body is under twenty instructions. An interleave costing four of them
would eat most of what the pairing wins.

It does not need one. **A gain is memoryless** — `y[n] = sat(rns(x[n]·g))` has no
dependence on `y[n-1]` — so the two samples PEx and PEy need are already adjacent
in the block the previous node wrote. `dm(i0, 2)` hands `x[n]` to PEx and `x[n+1]`
to PEy with no gather, no scratch and no scatter. Channel pairing would have
delivered the same factor and charged for the privilege.

Everything else follows the tree's established SIMD idiom: MODE1 saved and
restored whole rather than bit-toggled; interrupts **not** masked (the ISRs clear
PEYEN after `push sts`, which is what the paired dynamics already rely on, and
masking a whole block loop is what hung the part on 2026-08-28); saturation as a
per-PE conditional move rather than a branch, because a jump would use PEx's
condition for both units.

One instruction is genuinely new arithmetic rather than the scalar body widened:
the two extraction shifts and their `or` fold into `r0 = r0 or lshift r2 by 4`,
the same three operations in two instructions.

### Bit-exact by construction

* **The audio path is per-sample independent** — same instructions, same order
  within a sample, one rounding — so which compute unit runs a given sample
  cannot change its value.
* **The meter's sum of squares splits across the two units and is added back
  exactly.** MRF is an 80-bit integer accumulator with no rounding and no
  saturation; a 16-sample block of `x·x` tops out near 2^66, so nothing can
  overflow, and integer addition is associative. The peak and trough are max and
  min, which are too. `_gsimd_flush` does that recombination as a 96-bit
  carry-propagated add and then falls through into `_mtr_flush`.
* **The tap keeps its placement** — post-gain, pre-filter, same block, same
  words.

## 4. A defect found by reading, and the bar that could not see it

**The first cut of this kernel was wrong, `busgold` returned 0 of 256 anyway, and
that is the most useful thing in this write-up.**

`_GAIN_BLK_COMMON` loads the rounding half (`r6`, `r7`) and the saturation mask
(`r10`) with PEYEN still **down**, which writes PEx's copy of those registers and
leaves PEy's at whatever it held — zero out of reset. PEy would therefore have
**truncated** its samples instead of rounding them, and saturated them against a
mask of zero.

Neither fault is visible to `busgold`:

* Its stimulus is a ±0.5 square wave through a strip whose GAIN is pinned at
  **unity** by `gainfix`. The Q4.28 word for 1.0 is exactly 2^28, so every
  product's low 28 bits are already zero and truncation gives the same answer as
  rounding, on every sample.
* |x| = 0.5 and the largest Q4.28 gain is under 8, so the product never leaves
  range and the saturation fix-up is never taken at all.

The fix is three instructions per block — the constants reloaded inside the PEYEN
region — and the scalar body keeps its own copies untouched, so
`DSP4_GAIN_SIMD=0` is still byte for byte the old kernel.

**The bar was then rebuilt so it could see this class of fault.** `gainsimd.sh`
sets a non-round GAIN (0.70710678, Q4.28 `0x0B504F33`) before capturing, so every
product carries 28 bits under the round; `dsp4_pairgraph.py` gained a `--gain`
argument for it, and its `--compare` now **prints a warning when both captures
were taken at unity**, because a verdict from a blind instrument should say so on
its own rather than wait to be caught.

## 4b. Bars

| bar | result |
|---|---|
| **W0** | `chip1.ldr 23c1e662` / `chip2.ldr e45bb82a`, 301,764 / 182,092 bytes — **BYTE-IDENTICAL**, reproduced before and after. The shipping default build is `DSP4_BLOCK_KERNELS=0`, the per-sample path, and nothing this session touched reaches it: every new `.var`, every extern and both kernel bodies are behind `#if DSP4_BLOCK_KERNELS`. |
| **the control is PROVED, not assumed** | `DSP4_GAIN_SIMD=0` on the new tree rebuilds the PREVIOUS tree byte for byte — `chip1.ldr e95cdfe8` / `chip2.ldr 56037cf9` — at `DSP4_BLOCK_KERNELS=1 DSP4_SIMD_DYN=1 DSP4_BQ_GRAPH=1 DSP4_STRIP_FUSED=1`. So the cost difference in §6 is the kernel and nothing else. |
| **`busgold.sh`** | **GRAPH BIT-EXACT, 0 of 256**, sha256 `ba3f52ec` — the stored golden's own digest. (And see §4: this bar cannot see the kernel's rounding.) |
| **`busgold.sh` negative control** | `DSP4_GAIN_SIMD_NEGCTL=1` — **245 of 256 differ, and 128 of 256 words non-zero.** Exactly half the samples silenced, first difference at word 1: the odd-sample signature, which is direct evidence PEYEN is up and the second unit is computing them. |
| **`gainsimd.sh`** (new) | at a NON-ROUND gain, `simd vs scalar` **0 of 256 — BIT-EXACT**, capture digest `8f46bd9a` (different from the unity capture, so the gain reached the audio); `simd vs neg` **239 of 256 differ**, 128/256 non-zero. |
| **`mtrverify.sh`** | **METER_BIT_EXACT.** `ms64`, `pk_lo` and `pk_hi` all EXACT against `fixed_ref.meter_block`; its BLOCK=32-coefficient negative control correctly rejected. Its wide-word control drives GAIN at **0.4970** — Q4.28 `0x07F3B648`, a non-round word — and the part matches the WIDE model and correctly rejects the NARROW one. **This is the bar that certifies the split-and-recombine sum of squares**, and it does it with rounding live. |
| **`golden_harness.py`** | **59/59**, and **59/59 again at `DSP4_GEN_BLOCK=16`**. |
| **`numverify.sh`** | **NUMERIC BOUNDARY BIT-EXACT, 57 of 57**, and its negative control passes two-sidedly (31 of 31 boundary vectors detected, 26 of 26 others untouched). It builds the plain per-sample image, so it is evidence about the shared primitives rather than about this kernel — recorded because the dispatch names it. |
| **`dsp_validate.py`** | **OK — no errors.** No contract file touched; no contract version moves. |
| **pool parity** | witnessed `even` at every ladder point, both arms. The SIMD load takes PEy's word at address+1, and every block slot is `_blk_pool + n*BLOCK`, so the pool's base parity is the whole question; `gainprof.sh` prints it rather than trusting it. |

## 5. Program memory — the price nobody had priced, and it is the binding one

**THE SIMD KERNEL COSTS 1,486 BYTES OF CHIP 1'S PROGRAM MEMORY, WHICH IS 45% OF
WHAT WAS LEFT.** Measured on the block-16, 32-strip, paired, block-kernel build
(`words_unused` summed over chip 1's blocks, excluding the empty block 1):

| arm | chip-1 PM free |
|---|---|
| `DSP4_GAIN_SIMD=0` | **3,328 bytes** |
| `DSP4_GAIN_SIMD=1` | **1,842 bytes** |

**AND IT ALREADY BROKE SOMETHING: the instrumented profiling image no longer
links.** `DSP4_PROFILE_SIGNAL=1` at `DSP4_NODE_LIMIT=0` overflows `sec_swco` by
736 words in the SIMD arm and links in the scalar arm. That is why §6's
whole-graph figure is taken on the SILENCE graph — it is not a preference, it is
what fits. The class ladder is unaffected (a prefix cut removes chain calls, so
those images are smaller) and is taken signal-present as the record requires.

512 of those bytes were already recovered during the session: the first cut
emitted the rounding half and the saturation mask twice per node, once outside
the PEYEN region and once inside. The scalar body keeps `_GAIN_BLK_COMMON`
verbatim — which is why `DSP4_GAIN_SIMD=0` is still byte for byte the old
kernel — and the SIMD body now carries its own setup with the constants loaded
once, inside the region where both units see them.

**A FURTHER ~900 BYTES IS AVAILABLE AND WAS NOT TAKEN, because it is not free
and the choice is not an optimisation decision.** The eight-instruction PEYEN
prologue could become a shared routine the way `_gsimd_flush` already is. That
costs one more call/rts per node per block — 15.04 cycles at the measured price,
0.94 c/s at block 16 — which is **13% of the whole cycle win** spent to buy back
half the program memory. Chip 1 is at 94.0% of its cycle budget and at 1,842
bytes of code space; which of those two is the scarcer resource is a product
question, so it is put here rather than decided here.

## 6. Cost, measured

Instrument: `SHARC/gainprof.sh` — sigprofile.sh's ladder (TCOUNT/`_proc_cyc`,
`DSP4_NODE_LIMIT` prefix cut, DEC=32, the GAIN-coefficient witness) built from a
`DSP4_GEN_BLOCK=16` scratch tree, sweeping `DSP4_GAIN_SIMD`, two boots a point,
minimum taken. Pool parity witnessed `even` at every point.

**THE INSTRUMENT IS CALIBRATED THREE WAYS BEFORE ANY VERDICT IS READ OFF IT.**

1. **Against the capacity table, from an unrelated session**: the scalar
   whole-graph point reads 308,174 cycles/block against the 307,866 the
   2026-09-02 capacity measurement recorded for chip 1 at block 16 — **0.1%
   apart**.
2. **Against itself across boots**: the class-ladder points reproduce to 7 cycles
   on a ~17,000-cycle baseline (0.04%), and the whole-graph point to 258 (0.08%).
3. **Across the two arms at a point they must share**: limit 1 runs no GAIN node
   at all, so both arms must read the same number, and they do — 16,522 against
   16,526, **4 cycles apart**. A systematic difference between the arms would
   have shown there first.

### The class

`DSP4_NODE_LIMIT` 1 → 2 under the paired graph is A.IN → A.IN + A.GAIN, so the
consecutive difference is one GAIN node. Signal present, block 16, two boots,
minimum:

| arm | limit 1 | limit 2 | GAIN class | c/s |
|---|---|---|---|---|
| `DSP4_GAIN_SIMD=0` | 16,521 | 17,073 | **552 cycles/block** | **34.5** |
| `DSP4_GAIN_SIMD=1` | 16,521 | 16,967 | **446 cycles/block** | **27.9** |

**106 cycles/block/strip, 6.6 c/s, a factor of 1.24.** The two arms' limit-1
points are the SAME NUMBER — 16,521 and 16,521 — which is the check that matters
most, because limit 1 runs no GAIN node and any systematic offset between the
arms would appear there.

Both figures **include the strip's METER NODE**, which takes its source's ladder
position and so falls inside the same consecutive difference. It is identical in
both arms, so it cancels out of the 106 and inflates both absolute numbers.

### The whole graph — 32 gain nodes of signal instead of one

Silence graph (the signal-present image does not link in the SIMD arm, §5), block
16, 32 strips, two boots each:

| arm | boot 1 | boot 2 | min |
|---|---|---|---|
| `DSP4_GAIN_SIMD=0` | 296,150 | 297,013 | **296,150** |
| `DSP4_GAIN_SIMD=1` | 292,303 | 293,350 | **292,303** |

**3,847 cycles/block off chip 1** (min against min; boot-1 against boot-1 gives
the same 3,847 and boot-2 against boot-2 gives 3,663, against a within-arm spread
of 863 and 1,047 — so the result is comfortably above the instrument's
resolution).

**THE TWO INSTRUMENTS AGREE TO ABOUT 10% AND BOTH ARE REPORTED.** The class
ladder scaled by 32 strips predicts 3,392 cycles; the whole graph measures
3,663–3,847. They share no arithmetic — one is a difference of prefix cuts on a
one-strip chain, the other a difference of whole-graph totals — and the gap is
stated rather than averaged into a single figure.

### What that is worth, against what the dispatch expected

| | |
|---|---|
| **dispatch's expectation** | ~2–3% of chip 1 back as plugin headroom |
| **measured** | **3,663–3,847 cycles/block = 1.12–1.17% of the 327,680-cycle block-16 budget** |

**It is about half of what the dispatch priced, and that is said rather than
rounded up.** The reason is §2: the 2–3% was sized off the same 22.9 → 1–2 row,
i.e. off the rejected fold. Against the floor that the standing rulings actually
permit, this lands most of the available win.

## 7. What was not done, and what it would cost

* **The whole-graph figure is taken on the SILENCE graph**, because the
  signal-present image does not link (§5). GAIN's own cost is
  signal-independent — its kernel has no data-dependent branch — so the
  arm-to-arm difference is sound; the absolute whole-graph number is a silence
  number and is not comparable to the capacity table's.
* **One instruction of multifunction packing is available in the loop and was
  not taken.** `mrf = mrf + r12*r12 (ssi), r0 = dm(i0, 2)` assembles, which folds
  the block load into the meter's MAC: 1 of 19 instructions, about 5% of the
  loop. It was left out because landing it after the bars had run would have made
  every measurement in this document stale for a 5% change. `r13 = max(r13, r12),
  r0 = dm(i0, 2)` also assembles; the shifter-plus-store form does not.
* **The control-rate gate was not extended to GAIN.** `ctl_gate()` exists and
  RTG uses it; GAIN's ramp/convert prologue runs every block, and at block 16 its
  two branches alone are ~17 cycles. The gate would net perhaps 1.5 c/s — and
  getting its "busy" condition wrong FREEZES A FADER MOVE, which is a
  ramp-timing fault that `conform.sh` is the bar for. Not worth 1.5 c/s taken
  blind at the end of a session.
* **`gainsimd.sh` runs at block 8** (the repo tree's size). The kernel's
  correctness is block-size-independent by construction — the loop counts
  `DSP4_BLOCK_HALF` — and the block-16 arm is covered for the audio path by the
  class ladder booting and witnessing clean at every point, but no
  bit-exactness bar has been run at block 16 in this session.
* **The GAIN class figure includes its METER NODE**, as the existing
  `dsp4-function-costs.csv` row does: a meter takes its source's ladder
  position, so the consecutive difference at limit 2 contains both. The meter
  node is identical in both arms, so the difference between arms is the GAIN
  kernel alone.
* **`check-contract-drift.sh` FAILS ON A CLEAN TREE, AND IT FAILS ON DRIFT IT
  CREATES ITSELF.** Reported, not fixed. Run against a pristine checkout it
  exits 1 with `D24_DEF_SHA256 expected 8c5c9ea1... actual 39758827...` — and
  running it **leaves the working tree dirty**: `MW/D24/MX/_matrix.csv`,
  `MW/D32/MX/_matrix.csv` and both `*-mx-master.csv` are rewritten, and
  **`main.ctr,1` is APPENDED to `MW/D24/DEFS/d24.csv`**, which is a synced
  contract file that `CLAUDE.md`'s first hard rule says is never hand-edited.
  The hash it then complains about is the hash of the line it just added.
  Confirmed by reverting to a clean tree, running the checker alone, and
  finding the same five files modified again. `regenerate-dsp-contract.sh`
  does the same thing and stops at the same hash.

  It is left alone deliberately: a drift checker that dirties `DEFS/` is a
  sync/contract matter for the hub, and "fixing" it by taking the new hash
  would launder whatever real drift is underneath. **This change touches no
  contract file** — `dsp_validate.py` is OK and no contract version moves —
  and the churn those two scripts produced was reverted rather than
  committed.
* **Two bars in the tree were unrunnable and are now fixed.** `busgold.sh` and
  `conform.sh` both referenced `$ROOT` on the line that builds `BLOCKPY` and
  assigned `ROOT=` two lines LATER, so under `set -u` both aborted immediately
  with `ROOT: unbound variable`. The assignment is moved above its first use in
  both. As committed before this session, neither bar could run.
