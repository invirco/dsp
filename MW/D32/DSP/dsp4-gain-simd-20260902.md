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
| 22.9 → 1–2 c/s | **NOT REACHED, AND NOT REACHABLE.** The class lands at 26.75 c/s at block 16, from 34.56. See §2 and §6. |

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
the same three operations in two instructions. A second is saved by riding the
block load on the meter's MAC, which has no dependence on the word it loads.

### The whole kernel is SHARED, and the measurement is what made that right

PW's ruling of 2026-09-02 was to buy the program memory back even at a cycle
price. Taking it turned out to cost nothing and pay on both axes, and the reason
is §6's two-point fit: **nothing in the sample loop is per-node.** The pool
addresses arrive in `i0`/`i1`/`i4` and the meter's accumulator base in `r0`; the
loop touches no node symbol at all. So the body lives once, in
`lib/meter_fx.asm` as `_gsimd_gain_blk`, and a gain node is now **thirteen
instructions**: set three index registers, name its meter, call, and read the
block's last sample back for the linkage scalars.

That collapses **two** call/rts pairs per node per block — one to open the PEYEN
region and one to close it — into **one**, and `_gsimd_gain_blk` falls through
into `_mtr_flush` rather than jumping to it, so the node pays only the call it
was already paying for the meter.

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
| **the control is PROVED, not assumed** | `DSP4_GAIN_SIMD=0` on the new tree rebuilds the PREVIOUS tree byte for byte — `chip1.ldr e95cdfe8` / `chip2.ldr 56037cf9` — at `DSP4_BLOCK_KERNELS=1 DSP4_SIMD_DYN=1 DSP4_BQ_GRAPH=1 DSP4_STRIP_FUSED=1`, and re-checked after **each** of the three reworks. So the cost difference in §6 is the kernel and nothing else. |
| **`busgold.sh`** | **GRAPH BIT-EXACT, 0 of 256**, sha256 `ba3f52ec` — the stored golden's own digest — re-run on the final shared-kernel form. (And see §4: this bar cannot see the kernel's rounding.) |
| **`busgold.sh` negative control** | `DSP4_GAIN_SIMD_NEGCTL=1` — **245 of 256 differ, and 128 of 256 words non-zero.** Exactly half the samples silenced, first difference at word 1: the odd-sample signature, which is direct evidence PEYEN is up and the second unit is computing them. |
| **`gainsimd.sh`** (new) | at a NON-ROUND gain, `simd vs scalar` **0 of 256 — BIT-EXACT**, capture digest `8f46bd9a` (different from the unity capture, so the gain reached the audio); `simd vs neg` **239 of 256 differ**, 128/256 non-zero. Run on all three forms the kernel took this session — inlined, shared prologue, shared kernel — and bit-exact on each. |
| **`mtrverify.sh`** | **METER_BIT_EXACT.** `ms64`, `pk_lo` and `pk_hi` all EXACT against `fixed_ref.meter_block`; its BLOCK=32-coefficient negative control correctly rejected. Its wide-word control drives GAIN at **0.4970** — Q4.28 `0x07F3B648`, a non-round word — and the part matches the WIDE model and correctly rejects the NARROW one. **This is the bar that certifies the split-and-recombine sum of squares**, and it does it with rounding live. |
| **`golden_harness.py`** | **59/59**, and **59/59 again at `DSP4_GEN_BLOCK=16`**. |
| **`numverify.sh`** | **NUMERIC BOUNDARY BIT-EXACT, 57 of 57**, and its negative control passes two-sidedly (31 of 31 boundary vectors detected, 26 of 26 others untouched). It builds the plain per-sample image, so it is evidence about the shared primitives rather than about this kernel — recorded because the dispatch names it. |
| **`dsp_validate.py`** | **OK — no errors.** No contract file touched; no contract version moves. |
| **pool parity** | witnessed `even` at every ladder point, both arms. The SIMD load takes PEy's word at address+1, and every block slot is `_blk_pool + n*BLOCK`, so the pool's base parity is the whole question; `gainprof.sh` prints it rather than trusting it. |

## 5. Program memory — priced, ruled on, and the ruling paid for itself

The first cut of this kernel spent **1,486 bytes** of chip 1's program memory —
45% of what was left — because the PEYEN prologue, the sample loop and the meter
recombination were emitted in each of 32 gain nodes. It broke the instrumented
profiling image outright: `DSP4_PROFILE_SIGNAL=1` at `DSP4_NODE_LIMIT=0`
overflowed `sec_swco` by 736 words in the SIMD arm while the scalar arm linked.

**PW ruled: take the code space back. That ruling paid for itself twice over,
and the reason is §6's fit rather than anything about program memory.** Nothing
in the sample loop is per-node, so the whole kernel became one shared routine —
which removed a call as well as 32 copies of a body.

| build | chip-1 PM free | note |
|---|---|---|
| `DSP4_GAIN_SIMD=0` (scalar control) | 3,328 bytes | the kernel this replaces |
| SIMD, everything inlined (first cut) | 1,842 bytes | profiling image would not link |
| SIMD, shared PEYEN prologue | 3,580 bytes | already back above the control |
| **SIMD, whole kernel shared (shipped)** | **7,850 bytes** | **+4,522 against the scalar control** |

**The SIMD kernel now leaves chip 1 with more code space than the scalar kernel
it replaces, not less**, and the instrumented profiling image links again —
which is why §6's whole-graph figure could be taken signal-present and compared
directly against the capacity table.

## 6. Cost, measured

Instrument: `SHARC/gainprof.sh` — sigprofile.sh's ladder (TCOUNT/`_proc_cyc`,
`DSP4_NODE_LIMIT` prefix cut, DEC=32, the GAIN-coefficient witness) built from a
`DSP4_GEN_BLOCK` scratch tree, sweeping `DSP4_GAIN_SIMD`, two boots a point,
minimum taken. Pool parity witnessed `even` at every point.

**THE INSTRUMENT IS CALIBRATED THREE WAYS BEFORE ANY VERDICT IS READ OFF IT.**

1. **Against the capacity table, from an unrelated session**: the scalar
   whole-graph point reads 308,030 cycles/block against the 307,866 the
   2026-09-02 capacity measurement recorded for chip 1 at block 16 — **0.05%
   apart**.
2. **Against itself across boots**: class-ladder points reproduce to a few
   cycles on a ~17,000-cycle baseline.
3. **Across the two arms at a point they must share**: limit 1 runs no GAIN node
   at all, so both arms must read the same number — 16,522 against 16,524.

### The class, and the split that reframes the problem

| arm | block 8 | block 16 | per-sample | fixed |
|---|---|---|---|---|
| `DSP4_GAIN_SIMD=0` | 393 c/block | 553 c/block | **20.00 c** | **233 c/block** |
| `DSP4_GAIN_SIMD=1` | 352 c/block | 428 c/block | **9.50 c** | **276 c/block** |

**THE PER-SAMPLE PATH IS 20.00 → 9.50 CYCLES, A FACTOR OF 2.11** — more than the
2× the pairing is worth on its own, because the two extraction shifts fold into
one instruction and the block load rides on the meter's MAC.

**BUT THE PER-SAMPLE PATH IS NO LONGER WHERE THE MONEY IS, AND THAT IS THE MOST
USEFUL THING THE FIT SAYS.** At block 16 the fixed per-block half is 17.25 c/s
against the loop's 9.50 — **it dominates two to one**. The SIMD arm's fixed cost
is *higher* than the scalar arm's (276 against 233): that is what the pairing
buys its 10.5 cycles/sample with. Anyone sizing the next lever off the sample
loop will be sizing the smaller half.

At block 16 the class lands at **34.56 → 26.75 c/s, a factor of 1.29.**

### GAIN alone, with the meter taken out

The class figure bundles the strip's **meter node**, which takes its source's
ladder position and so falls inside the same consecutive difference. `DSP4_MTR_OFF=1`
removes the meter (and selects the unmetered kernel body, so this is "GAIN with
no meter" rather than "the metered kernel minus the meter node"):

| arm | block 16 | c/s |
|---|---|---|
| scalar (fused) | 330 c/block | 20.63 |
| **SIMD** | **225 c/block** | **14.06** |

**So of the 26.75 c/s the class costs, 12.7 is metering** — the inline wide-word
accumulation plus the meter node's own fold — **and 14.06 is GAIN.**

### The whole graph — 32 gain nodes of signal instead of one

Signal present, block 16, 32 strips, two boots each:

| arm | whole graph | % of the 327,680-cycle budget |
|---|---|---|
| `DSP4_GAIN_SIMD=0` | 308,030 | 94.0% |
| `DSP4_GAIN_SIMD=1` | 304,110 | **92.8%** |

**3,920 cycles/block off chip 1 = 1.20% of the budget.** And the two instruments
now agree: the class ladder scaled by 32 strips predicts 4,000 against the 3,920
measured, **2% apart**, sharing no arithmetic.

### Where it lands against 1–2 c/s

| | c/s at block 16 |
|---|---|
| the dispatch's target | **1–2** |
| GAIN class before | 34.56 |
| **GAIN class now** | **26.75** |
| GAIN now, meter removed entirely | **14.06** |
| of which: the per-sample numeric contract and the two stores | **9.50** |

**Even with the meter deleted — which no ruling permits — GAIN is 14 c/s, and
9.5 of that is the per-sample path alone.** To reach 1–2 the per-sample path
would have to fall by a further factor of five to nine, and it consists of one
gain MAC, one rounding MAC, ten instructions of Q4.28 extract-and-saturate, and
two block stores. The target is not a distance the kernel can close; it is the
price of the D5 numeric contract, the D20 tap and the 2026-08-29 meter, all of
which are standing rulings. **The dispatch's 2–3%-of-chip-1 expectation was
sized off the same rejected row; measured is 1.20%.**

## 7. What was not done, and what it would cost

* **The control-rate gate was priced and REJECTED, with arithmetic rather than
  with caution.** The previous write-up called it "worth ~1.5 c/s"; that estimate
  did not price the gate itself. `_ctl_strip_prep_needed` is ~20 instructions
  behind a call/rts — about 35 cycles — and GAIN's *entire* ramp/convert
  prologue, including its taken branch, is ~28. **The gate costs more than the
  work it skips.** An inline gate without the call would net perhaps 0.5 c/s and
  cost eight instructions a node; not taken.
* **Software-pipelining the loop was priced and not taken.** It would reach 16
  instructions per two samples against today's 18, but the fit says the loop is
  already running at 9.50 cycles for ~9 instructions/sample — **essentially at
  its instruction-count floor** — so the win is ~0.6 c/s, and it needs a peeled
  first iteration and a carry register. Named and priced rather than attempted
  at the end of a session.
* **The remaining fixed 276 cycles/block is the honest next target**, and about
  half of it is the meter node, which is a different class under a different
  ruling. GAIN's own share is roughly the chain dispatch call, the ramp/convert
  prologue, the shared kernel's call, and the 96-bit meter recombination.
* **`gainsimd.sh` and `mtrverify` run at block 8** (the repo tree's size). The
  kernel's correctness is block-size-independent by construction — the loop
  counts `DSP4_BLOCK_HALF` — but no bit-exactness bar was run at block 16 this
  session.
* **`check-contract-drift.sh` FAILS ON A CLEAN TREE, ON DRIFT IT CREATES
  ITSELF.** Reported, not fixed. Run against a pristine checkout it exits 1 with
  `D24_DEF_SHA256 expected 8c5c9ea1... actual 39758827...` — and running it
  **leaves the working tree dirty**: both `_matrix.csv` and both
  `*-mx-master.csv` are rewritten, and **`main.ctr,1` is APPENDED to
  `MW/D24/DEFS/d24.csv`**, a synced contract file that `CLAUDE.md`'s first hard
  rule says is never hand-edited. The hash it then complains about is the hash of
  the line it just added. Confirmed by reverting to clean, running the checker
  alone, and finding the same five files modified again;
  `regenerate-dsp-contract.sh` does the same. Left alone deliberately — taking
  the new hash would launder whatever real drift is underneath — and its churn
  was reverted rather than committed. **This change touches no contract file**;
  `dsp_validate.py` is OK and no contract version moves.
* **Two bars in the tree were unrunnable and are now fixed.** `busgold.sh` and
  `conform.sh` both referenced `$ROOT` on the line building `BLOCKPY` and
  assigned `ROOT=` two lines LATER, so under `set -u` both aborted with
  `ROOT: unbound variable`. As committed before this session, neither could run.
