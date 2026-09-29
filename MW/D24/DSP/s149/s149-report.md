provenance: AI-drafted 2026-09-29 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S149 — the capacity levers PW approved, built and priced

Session 149, 2026-09-29, desk only. Hub dispatch `tasks.md` 2026-09-29 11:00Z.
Nothing flashed, no DSP image loaded, no app deployed, the unit not contacted
at all — scratch builds and reads of this tree only.

PW's rulings on S148, verbatim: *"Yes, both"* (L1 the fabric, L2 the follower
pairing) and *"cap reverbs to 3"*.

---

## 0. What this session did, in one table

| | what | worth | where |
|---|---|--:|---|
| **L1** | chip 2's mix buses on the live-crosspoint fabric | **9.29 points** in use, **+1.59 always** | §1 |
| **L2** | the pair drivers taught about followers | **1.27 points** | §2 |
| **cap** | at most three Type Reverb engines at once | **7.45 points** | §4 |

**The worst regime the product can now be put into is 87.37 %** — three
reverbs with the desk fully in use — against a ~97 % abort line, where S148
had the uncapped equivalent at 110.27 %. Each item was built, measured and
committed **on its own**; chip 1's image is byte-identical to the signed one
on every arm in this report.

**And a correction to S148, which moves every "as built" figure in its
capacity table down by 3.30 points** — see §3.4. S148 priced the generic
wrapper at 192 cycles/block per declared source, which is the **average** at
eleven sources and not the **marginal**; applied to a thirty-three-source aux
bus it over-prices the baseline by 29 %. L1 is therefore worth less than
S148 said (9.29 points, not 12.47) **and the thing it is measured against was
never as expensive as S148 thought.** Both halves are in §3.4's table.

---

## 1. L1 — chip 2's mixes on the live-crosspoint fabric

### 1.1 What was built

`DSP4_C2_MIX_FABRIC`, defaulting to 1 in `shipping.config` with PW's approval
recorded beside it. One new generated file, `src/chip2/mix_fabric.asm`, and
one new arm inside `gen_mix_bus_fixed`'s chip-2 body.

The pass is three steps and it is chip 1's `rtg_fabric.asm` argument one chip
along:

1. **Compact.** Walk the bus's coefficient row — `_mix_gq_<nid>`, which the
   node already folds at block rate — beside a new source-pointer table
   `_mixsp_<nid>` of link-time addresses. A crosspoint whose coefficient is
   **exactly zero** is dropped here and costs nothing downstream. That is the
   whole lever.
2. **Gather.** Copy each surviving source's block into `_c2mix_src`, so the
   accumulate reads one contiguous array at a fixed stride. Chip 1 pays the
   same price for the same reason (`_rtg_src`): a pointer table walked per
   sample costs six instructions a MAC, a strided array three.
3. **Accumulate, bus-major.** `mrf = 0` once a sample, two loads and a MAC per
   live crosspoint, and `_mrf_rns28`'s arithmetic inlined — with its early
   `rts` turned into a conditional move, because a shared routine's return
   cannot live inside a hardware loop.

**The scratch is SHARED by all fifteen chip-2 mix buses and that is what keeps
the memory bill small.** `_c2mix_src` / `_c2mix_gq` are filled and consumed
inside one call with no node boundary between, so one copy sized for the
widest bus in the graph (23 sources) serves every bus. A per-node buffer would
have cost ~12 KB of chip 2's 46,996 free DM bytes and pushed the pool over its
90 % warn line; the shared one costs 2,352 bytes measured (§1.4).

**It covers every chip-2 MIX_BUS, not only the twelve aux sums.** `C2_MIX_MAIN_L`,
`C2_MIX_MAIN_R` and `C2_WOOF_MIX` take the same wrapper and the same
per-sample staging, and they have **no bypass to fall into** — their sources
are fixed feeds, always live. So they pay the wrapper's full price on every
block of every regime, and the fabric's saving on them is **unconditional**.
S148 did not price that; §3.3 does.

### 1.2 The proof that it is exact, and it is two proofs

**(a) The control arm rebuilds the signed image BYTE FOR BYTE, on both chips.**
With `DSP4_C2_MIX_FABRIC=0` the whole change is inside `#if` blocks and the
image must be the one S147 signed. It is:

| arm | chip 1 | chip 2 |
|---|---|---|
| S146/S147 arm B — **the signed shipping image** | `6d7b86ec69778900ce63b9eb79c144ea` | `e76d2dc8463292a2ba2f6b9172cb6be5` |
| this tree, `DSP4_C2_MIX_FABRIC=0` | `6d7b86ec69778900ce63b9eb79c144ea` | `e76d2dc8463292a2ba2f6b9172cb6be5` |
| this tree, shipping (`=1`), build 1 | `6d7b86ec69778900ce63b9eb79c144ea` | `ca01e24543b8867fb8ee4529b7ea52d6` |
| this tree, shipping (`=1`), build 2 | `6d7b86ec69778900ce63b9eb79c144ea` | `ca01e24543b8867fb8ee4529b7ea52d6` |

so every byte that differs in the fabric arm is a byte this flag put there —
and **chip 1's image does not move at all**, on either arm, which is the
strongest single statement available about the lever's blast radius. The two
shipping builds were run end to end independently and are byte-identical, so
the image is deterministic as well as reproducible.

*One qualification, stated because it is the kind of thing that gets quietly
elided.* That control build was taken with one line removed from
`src/diag.h`'s `DIAG_CFG3_INSTR_SUM` — the new `(DSP4_C2_MIX_FABRIC != 1)`
term. The term is **correct and is in the committed tree**: a build with the
flag moved off 1 is an instrument and DIAG_BUILD_CFG3 bit 23 must say so. But
it is a *label*, not code, and leaving it in makes the control image differ
from the signed one in exactly one constant, on both chips, which would have
hidden the very identity the arm exists to demonstrate. The line was removed,
the arm built, the md5s taken, and the line restored — and with it restored
the **shipping** triple is unmoved (§1.5).

**(b) The arithmetic is fuzzed against the reference model.**
`tools/dsp/c2_mix_fabric_ref.py` transliterates BOTH paths out of the emitted
assembly — the 80-bit MRF, `_mrf_rns28` and the inlined copy, register by
register — and runs them against each other and against `fixed_ref.mix_sum`:

```
c2 mix fabric: 4000 vectors, 64000 block words
  wrapper path vs fabric path      : OK
  wrapper vs fixed_ref.mix_sum     : 63995 words inside the 64-bit domain
  outside it (S149-1, pre-existing): 5 words — wrapper and fabric still agree
  negative control (|coeff| <= 16) : fires — OK
```

The negative control runs on every invocation and skips crosspoints whose
coefficient is merely *small* rather than zero — the plausible-looking mistake
this lever could have shipped. It fires. A proof that cannot fail is not a
proof.

**Why skipping a zero coefficient is exact, in one line:** the term it removes
is `x * 0`, which changes no bit of an 80-bit integer accumulator, and the
order of the surviving terms is unchanged.

### 1.3 What it costs and what it saves — counted, not assumed

Cycles cannot be measured desk-side, so `tools/dsp/c2_mix_cost.py` counts the
**instructions each path executes**, straight out of the generated assembly,
for a stated number of live crosspoints. It reads the files the generator
wrote, so nothing here is written down twice.

**The instrument calibrates against S148's own measurement, and it agrees to
0.3 %.** S148 §6.2 prices `C2_MIX_AUX_01` off the S23 bypass at 2,112
cycles/block (S23-5's measured 192 c/blk × 11 declared sources). This counts
**2,394 instructions** on the same node and the same path. One cycle per 1.134
instructions — i.e. **0.882 cycles per instruction** — and that ratio is what
every cycle figure below is carried at.

| | instructions/block | cycles/block at 0.882 |
|---|--:|--:|
| wrapper, fixed per node | ~700 | 617 |
| wrapper, per **declared** switched source | 150 | 132 |
| wrapper, per **declared** plain source | 195 | 172 |
| fabric, fixed per node | 106 | 93 |
| fabric, per **LIVE** crosspoint | **84** | **74** |
| fabric, per **DEAD** crosspoint | **6** | **5** |

**The fabric's live-crosspoint rate is S148's assumption, met.** S148 priced it
at 5.29 c/MAC (`FRONTIER_RTG_RESIDUAL`, measured on chip 1) = 84.6 cycles/block
per crosspoint at BLOCK=16. Built, it is 74 — **13 % better than the
assumption**, because the pass carries no bus-accumulator triple to load and
store (one bus, one pass, the MRF cleared once a sample).

The dead-crosspoint rate is the other half and it has no S148 counterpart: a
declared crosspoint nobody has switched on costs **five cycles a block**
against the wrapper's hundred and thirty-two.

Per bus, counted:

| node | declared | live | wrapper | fabric | saved |
|---|--:|--:|--:|--:|--:|
| `C2_MIX_AUX_nn` | 11 | 2 (one FX return open) | 2,394 | 551 | 1,843 |
| `C2_MIX_AUX_nn` | 11 | 11 (everything patched) | 2,394 | 1,307 | 1,087 |
| `C2_MIX_MAIN_L/R` | 23 | 23 (always) | 5,202 | 2,387 | 2,815 |
| `C2_WOOF_MIX` | 2 | 2 (always) | 771 | 497 | 274 |

(instructions per block; the aux rows are off the S23 bypass, which is where
S148-1 says one open crosspoint puts them.)

### 1.4 Memory and image, re-priced from the built images' own linker maps

| pool | chip 1 before | chip 1 after | chip 2 before (arm B) | chip 2 after | limit |
|---|--:|--:|--:|--:|--:|
| code (VISA SW) | 181,490 — 69.2 % | **181,490 — 69.2 %** | 186,382 — 71.1 % | **188,480 — 71.9 %** | 262,144 B |
| DM data + stack | 309,612 — 82.5 % | **309,612 — 82.5 %** | 328,268 — 87.5 % | **330,620 — 88.1 %** | 375,264 B |
| delay lines | 506,880 — 24.5 % | **506,880 — 24.5 %** | 1,886,112 — 91.0 % | **1,886,112 — 91.0 %** | 2,072,576 B |

**Chip 1 is untouched — the image is byte-identical to the signed one**
(`6d7b86ec69778900ce63b9eb79c144ea`, the same md5 the control arm and arm B
produce). The lever is chip-2-only by construction: `mix_fabric.asm` lives in
`src/chip2/` and chip 1 has no chip-2 mix buses.

Chip 2 costs **+2,098 bytes of code and +2,352 bytes of DM**, and **not one
byte of delay pool**. The DM is accounted for to the word: `_c2mix_src[23×16]`
368 words + `_c2mix_gq[23]` 23 + two parking words = 393, plus the fifteen
`_mixsp_` tables at 180 words = 573 words = 2,292 bytes, and the linker's
alignment makes it 2,352.

The chip-2 DM pool goes 87.5 → **88.1 %**, still inside the 90 % warn line,
with 44,644 bytes free.

### 1.5 The config words do not move

There is no free bit in any of the three DIAG_BUILD_CFG words —
`cfg_words.py` enumerates them and says so at word 2 and word 3 — so
`DSP4_C2_MIX_FABRIC` is carried by the **instrument bit**, DIAG_BUILD_CFG3 bit
23, like the other fifty-seven switches no word carries. At its shipping value
of 1 the bit reads 0 and:

```
shipping config: consistent; the part must read
  DIAG_BUILD_CFG 0xCF45FF10, DIAG_BUILD_CFG2 0xE2019E6F, DIAG_BUILD_CFG3 0xC47C0FA6
```

— **exactly the triple S147 signed**. Nothing in `accept/manifest.json` or
`d24_selftest.py`'s `SIGNED_TRIPLE` needs to change. A build with the flag off
reads bit 23 = 1 and calls itself an instrument, which is what it is.

### 1.6 Gates

| gate | result |
|---|---|
| `check-sharc-codegen-drift.sh` | **758 generated / 0 differ**, 0 absent |
| `golden_harness.py` | 59/59 |
| `dsp_validate.py` (724 nodes) | OK — the same four pre-existing process-order notes as S144/S147 |
| `test_dsp_validate.py` | 20/20 |
| `stereo_split_check.py` | passed — 779 declared input edges read, 928 fabric-gathered |
| `follow_lockstep_check.py` | 11/11 |
| `product_fit.py --check-masks` | all four products OK |
| `check_shipping_config.sh` | consistent, triple unmoved |
| `c2_mix_fabric_ref.py` | 64,000 block words, 0 disagreements, negative control fires |

**One limitation, stated rather than left to be found.** `stereo_split_check.py`
reads the emitted assembly as text, and a chip-2 mix node's file now carries
BOTH arms — so its "declared input edges read by the emitted code" gate is
satisfied by the wrapper arm whether or not the fabric arm names the same
sources. It does name the same sources, and it cannot do otherwise: `_mixsp_`
and the wrapper's staging are generated from the same `node['inputs']` list in
the same order. But the gate did not prove that, and saying it did would be
the kind of claim this tree exists to avoid.

---

*(§2 L2, §3 the regimes, §4 the reverb cap and §5 the bench rows follow.)*

---

## 2. L2 — the pair drivers taught about followers

### 2.1 What S143 refused, and what it takes to stop refusing

`_c2_pair_excluded` has said since S143 that a follower *"runs that node's
parameters"* and cannot be SIMD-paired, with the reason spelled out in the
code: the drivers gather `_<pfx>_coeffs_A_<node>` **per member**, and a
follower has no such symbol — it `.extern`s its master's. The same comment
said what it would take: *"resolving a follower's coefficient symbol to its
master's — the `cid` the node generator already uses — plus a MAIN entry in
`_C2_PAIR_FAMILIES`."* That is what this is.

**A master and its follower are the cheapest pair that exists.** One
coefficient set, two states — which is exactly the shape
`gen_bq_pairs_c2`'s native interleave wants — so the pair costs one gather at
engage and nothing per block afterwards.

Three changes and no new mechanism:

1. `_c2_bq_sel` takes a `cid`: **coefficients** (and the pending-design
   flag, and the headroom word under `DSP4_BQ_GUARD`) come from the master,
   **state, active instance, swap-pending and crossfade** stay per node. The
   follower's own `active` word still chooses which of the master's two banks
   is live for that leg, exactly as the follower's node body does it.
2. `_c2_pair_excluded` now refuses only a follower of a node **outside the
   family**. A follower paired with its own master is fine; a follower of a
   stranger still is not, because the driver would gather a third node's
   parameters for a pair that node is not in.
3. `_C2_PAIR_FAMILIES` grows a sixth field — the **instance map** — because
   this family's two members are not `01` and `02` but `C2_MAIN_GEQ` and
   `C2_MAIN_GEQ_R`, and a family that states its instances outright is the
   same discipline the table already follows for its classes.

The three existing families are unaffected: for every non-follower `cid` is
the node itself.

### 2.2 What got paired, and what did NOT

| pair | stages | paired? | S148's price |
|---|--:|---|--:|
| `C2_MAIN_GEQ` + `_R` | 31 | **yes** | 3,057 c/blk |
| `C2_MAIN_AFB` + `_R` | 6 | **yes** | 1,095 c/blk |
| `C2_MAIN_XOVER` + `_R` | — | **no — see S149-2** | 2,691 c/blk |
| `C2_MAIN_COMP`/`_LIM` + `_R` | — | no, and correctly: stereo **LINKED** (S143 §1.2) | — |

🔴 **S149-2 — `C2_MAIN_XOVER` cannot be paired by this lever, and S148's L2
price is 2,691 c/blk (0.82 points) too high because of it.** The native
interleave needs a node whose cascade is ONE `_<pfx>_coeffs_A_<nid>` /
`_<pfx>_state_A_<nid>` pair of a stated length. A crossover is not that
shape: `gen_crossover_fixed` emits an LP leg and an HP leg and calls
`_bq_fx_cascade_N` **eight times** per instance, and there is no single
coefficient array to interleave. Pairing it is a new driver, not a follower
fix, and `_C2_BQ_STAGES` has no entry for the class for exactly that reason
(the table's own rule: *a cascade whose length this table cannot state is
left scalar rather than paired at a guessed length*). **L2 as built is
therefore worth 4,152 c/blk = 1.27 points, not S148's 2.09.**

`C2_MAIN_COMP` and `C2_MAIN_LIM` were never L2's to take — S143 refused them
for the *other* reason, that `_comp_pair_blk` has no second detector input
and pairing a stereo-linked node would give the two legs independent
detectors. That refusal stands, unchanged, and this lever does not touch it.

**Why COMP, LIM and DLY are not in the MAIN family at all.** An excluded node
takes its whole INSTANCE out of a family, so putting the linked compressor
and limiter in the same family as the GEQ would have taken the GEQ and AFB
pairs out with them. The family stops at AFB, which leaves the run either
side of the linked pair contiguous — which is what the reorder rests on.

### 2.3 Cost, and the one number worth watching

Built on top of L1, chip 2 only (chip 1's image is `6d7b86ec…` on every arm
in this report):

| pool | after L1 | after L1 + L2 | limit |
|---|--:|--:|--:|
| code (VISA SW) | 188,480 — 71.9 % | **189,614 — 72.3 %** | 262,144 B |
| DM data + stack | 330,620 — 88.1 % | **333,876 — 89.0 %** | 375,264 B |
| delay lines | 1,886,112 — 91.0 % | **1,886,112 — 91.0 %** | 2,072,576 B |

**The DM is the number worth watching and it is accounted for to the word.**
+3,256 bytes = 814 words, and the two interleaved arrays are 816: the GEQ
pair's `_bqi_c[10 × 31]` + `_bqi_s[12 × 31]` + latch = 683, the AFB pair's
`_bqi_c[60]` + `_bqi_s[72]` + latch = 133. Chip 2's DM pool is now at
**89.0 %**, one point under `dsp_memreport`'s 90 % warn line, with 41,388
bytes free. **A third chip-2 cascade pair of GEQ size would cross it**; that
is not a reason to refuse one, it is a reason for the next session to say so
out loud and rebalance the LDF rather than discover it at link time.


---

## 3. The regimes, recomputed

### 3.1 How to read this table

Everything here is a **construction on S148's measured baselines**, not a new
measurement. No cycle figure in this session was taken on the part, because
this dispatch forbids touching it — so what changes against S148 is what the
built levers are worth and what the baseline they are measured against
actually costs, both counted off the emitted code. The bench row that
settles it is §6's first.

Chip 2's budget is 327,680 cycles/block (983.04 MHz, 3,000 blocks/s), so one
point is 3,276.8 cycles/block. Every figure is **arm B**, which S147 made the
shipping arm.

### 3.2 The terms

| term | c/blk | points | where it comes from |
|---|--:|--:|---|
| **B** — R1, Echo default, all 890 built | — | **77.69** | S148 §6.3, measured baseline + its bill |
| **ΔREV** per engine moved Echo → Reverb | 8,143 | 2.485 | S148 §6.3's R2 − R1 (14.91) ÷ 6 |
| **ΔUSE**, as built — S148's figure | 57,906 | 17.67 | S148 §6.2 |
| **ΔUSE**, as built — **corrected (§3.4)** | 47,084 | **14.37** | the wrapper's marginal, counted |
| **ΔUSE**, on the fabric (L1) | 16,641 | **5.08** | counted |
| **U1** — L1's unconditional saving | 5,207 | **1.59** | the main and woof mixes, every block |
| **U2** — L2's saving | 4,152 | **1.27** | S148's pairing factor, GEQ + AFB only |

### 3.3 The table

| regime | S148 as built | **corrected as built** | **+ L1** | **+ L1 + L2** |
|---|--:|--:|--:|--:|
| **R1** Echo default, nothing switched on | 77.69 % | 77.69 % | **76.10 %** | **74.83 %** |
| **R2** six Type-3 reverbs | 92.60 % | 92.60 % | 91.01 % | 89.74 % |
| **R2′** *three* reverbs + three Echo — **PW's cap** | — | **85.15 %** | **83.56 %** | **82.29 %** |
| **R3** Echo default, desk IN USE | 95.36 % | **92.06 %** | **81.18 %** | **79.91 %** |
| **R4** six reverbs AND desk in use | 110.27 % | **106.97 %** | 96.09 % | 94.82 % |
| **R4′** *three* reverbs + in use — **PW's cap** | — | **99.52 %** | **88.64 %** | **87.37 %** |

Abort line: **~97 %, or any missed block on any chip-row of any boot.**

**With the cap in the image, R2 and R4 are not reachable states.** A build
carrying `DSP4_FX_REVERB_CAP=3` cannot put six engines on Reverb however the
host is driven — that is what the guard is for — so the worst case the
product can be put into is **R4′, and it lands at 87.37 % with both levers,
9.6 points inside the abort line.** R2 and R4 are kept in the table because
they are what the `DSP4_FX_REVERB_CAP=0` control arm measures, and because
the six-reverb capacity row can only be taken on that arm.

**The cap alone would not have been enough and neither would the levers
alone.** As built, three reverbs with the desk in use is 99.52 % — over the
line. With L1 it is 88.64 %. The cap buys 7.45 points, L1 buys 10.88 (9.29
in use plus 1.59 always), L2 buys 1.27; the worst case needs the first two
and is comfortable with all three.

**Arm A (`DSP4_C2_BQ_GRAPH=0`, the rollback arm) still busts every in-use
regime** — it is ~17 points above arm B throughout — and nothing here changes
that. It remains the rollback image and not a capacity option.

### 3.4 🔴 S149-3 — the correction to S148, and it goes the *helpful* way

**S148 priced the generic wrapper at 192 cycles/block per declared source.
That number is an AVERAGE at eleven sources, not a MARGINAL, and S148 applied
it to a thirty-three-source bus.**

Where 192 comes from is not in doubt and is not wrong: S23-5 measured twelve
aux sums with the wrapper costing 13.59 points of chip 2 at eleven declared
sources each, which is 2,112 cycles/block a node, which is 192 a source. What
it contains is the node's **fixed** cost — the ramp fold, the wrapper's
prologue, the per-sample call and return, the MRF clear and the readout —
spread across eleven sources. Counted off the emitted code
(`tools/dsp/c2_mix_cost.py`), a chip-2 mix bus is:

```
  ~700 instructions fixed  +  150 per declared switched source
                           +  195 per declared plain source
```

which reproduces `C2_MIX_AUX_01` to 1 instruction in 2,394 and
`C2_MIX_MAIN_L` to 17 in 5,202. At eleven sources the average IS 192 cycles.
At S148's thirty-three it is **not**: the fixed term is spread three times
thinner, and the wrapper costs 39,866 cycles/block across eight aux buses
where S148 has 50,688.

**So S148's "as built" in-use column is 10,822 cycles/block — 3.30 points —
too expensive**, and with it R3 (95.36 → 92.06 %) and R4 (110.27 → 106.97 %).
The fabric side of S148's table needs no correction worth having: its 15,574
against this session's 15,183 is 0.12 points apart, because the fabric's
per-crosspoint rate really is the 5.29 c/MAC S148 assumed (74 counted against
84.6 assumed — better, not worse).

**This does not change S148's verdict and it does change one of its
sentences.** *"R3 … does NOT fit as built (95.4 %, four points of margin
against a 0.53-point boot spread, which is not a margin)"* becomes 92.06 %,
which is seven points of margin — still not a margin anybody should ship on,
and still the reason to take L1, but not the same sentence. And **L1 is worth
9.29 points where S148 said 12.47**, for the same reason read the other way:
most of the missing 3.18 points was never there to save.


---

## 4. PW's reverb cap — the DSP-side guard

### 4.1 The ruling, and what it is worth

PW, 2026-09-29: *"cap reverbs to 3"*. At most THREE of the six FX engines may
be on Type Reverb at once.

It is the cheapest of the trades S148 §8 listed and it is worth **7.45
points** (three engines × 2.485). It costs **224 bytes of code, 80 bytes of
DM and about 176 cycles a block — 0.054 % of chip 2** — and it does not touch
the per-sample path at all.

### 4.2 What was built

`DSP4_FX_REVERB_CAP`, default 3 in `shipping.config`, 0 = the control.
One new generated file, `src/chip2/fx_cap.asm`, one call at the head of the
chip-2 chain immediately before the first FX engine, and two read sites
inside `gen_fx_engine` moved from the request word to the live one.

**A fourth Reverb is HELD, and the split is the whole design.**
`_fx_type_<nid>` stays **exactly what the host wrote** — the guard only ever
reads it — and `_fx_type_live_<nid>` is what the engine dispatches on. So:

- the fourth Reverb is **never loaded**: the algorithm is not selected, no
  reverb state is set up, and the engine costs whatever its live type costs;
- a host read-back of `Fx*Type` still says what the panel says, because
  nothing rewrote it;
- the held request is **granted the moment a slot frees**, with no further
  host traffic;
- **swapping takes one block**, because every release is granted before any
  grant — moving Reverb from engine 2 to engine 5 in one host transaction
  lands in one block, not two;
- **an engine already running Reverb keeps its slot** whatever its index. A
  newcomer never evicts a reverb that is audibly running; among engines
  *newly* asking, the lowest index wins. Deterministic either way, so two
  units given the same writes are in the same state.

Three software loops over six engines at block rate. It is placed
immediately before the first engine because that is the only window in which
every host write of the block has landed and no engine has yet read a type,
and it is outside every `DSP4_NODE_LIMIT` guard for the same reason the
chip-1 fabric is: a prefix cut that keeps any engine must keep the cap.

### 4.3 The proof

`tools/dsp/fx_reverb_cap_ref.py` transliterates the three passes and checks
the properties the *ruling* asks for, not the ones the code happens to have:

```
reverb cap: 20000 random (request, state) pairs
  every property                   : OK
  exhaustive over Echo/Reverb      : 2688 pairs
  swap Reverb 1 -> 5 in ONE block  : OK
  held, then granted when freed    : OK
  negative control (grant only)    : fires — OK
```

The properties are: the cap is never exceeded from any state under any
sequence of writes; the request word is never modified; the guard settles in
one block from any state; an incumbent is never evicted; nothing is held
while there is room; and among new requests the lowest index wins. The
exhaustive arm runs every request over {Echo, Reverb}⁶ against every
reachable live state. The negative control drops the release pass — the
plausible mistake, a grant-only guard — and the one-block swap then fails,
which is what a proof that can fail looks like.

### 4.4 🔴 S149-4 — the six-reverb capacity row can no longer be built on a
shipping-configured tree

`DSP4_FX_TYPE_DECLARED=1` plus six engines declared `type=Reverb` is how
S148's R2 and R4 rows were reached. With the cap in the image that
configuration now produces **three** reverbs and three Echoes, because the
guard grants on the first block and the live word boots at Echo. That is the
cap working, and it means the six-reverb row is a `DSP4_FX_REVERB_CAP=0`
measurement from now on. It is recorded here and in the bench list (§6) so
the next capacity row is taken on the arm that can produce it, rather than
being taken on the shipping arm and quietly measuring three.

---

## 5. The proposed host-side cells — PROPOSED ONLY, added nowhere here

Same two-layer pattern as S148 §2b: the host is the single writer, computes
what is available and publishes it so skins can grey the selection out; the
DSP keeps its own guard underneath so a write the host should not have made
can never cost a missed block. Names are forever, so these go to PW and to
`defs` and are added in **no** file of this tree.

**RECOMMENDED — one availability mask per engine.**

```
Fx[1-8]TypeAvail[1-1]      Class: host-managed
```

One cell per FX engine, eight on the superset, **six on a D24**. Its value is
a bitmask, bit *N* set = *"Type N may be selected on this engine right
now"*. Host-computed and host-published; no DSP address, no kernel read — the
same class as `Aux[1-12]AuxAvail[1-1]`.

Notes text, proposed:

> FX type availability, one bit per Type (bit N = Type N; 0=Echo 1=PingPong
> 2=Doubling 3=Reverb 4=Chorus 5=Flanger 6=Phaser): 1 = that Type may be
> selected on this engine, 0 = selecting it would exceed a capacity cap and
> the DSP will hold the request. Host-computed and host-published; skins grey
> the entry when the bit is 0. Recomputed on every Fx*Type change. (PW ruling
> 2026-09-29: at most three engines on Type Reverb at once.)

**Why a bitmask and not `Fx[1-8]ReverbAvail[1-1]`.** The cap is a capacity
rule, and Reverb is the only Type that has one *today*. A per-Type boolean
would need a second cell family the first time a second Type is capped —
S148 already flags `Fx PingPongStart` as a reading that could cost 16.44
points if it were taken as stereo engines — and cells are forever. One
bitmask carries the whole answer and costs six cells on a D24.

**The bit for an engine's OWN current Type is always set**, so a skin never
greys out what the engine is already on and the user can always see where
they are.

**NOT proposed, and the reason is stated rather than left open.** A
`Fx[1-8]TypeLive[1-1]` read-back of what the engine is actually running would
let a skin show a *held* state. It is not proposed because with `TypeAvail`
published correctly a held state cannot be reached through the UI at all —
the selection is greyed before it can be made — so the cell would exist for a
race the two layers are there to prevent. If PW wants the held state visible
anyway, the DSP word already exists (`_fx_type_live_<nid>`) and it is one
address, not a redesign.


---

## 6. The images, and what moved in the S146 window

All four S146 arms were rebuilt with `MW/D24/DSP/s146/build-images.sh` and
the whole set re-priced off its own linker maps.

| arm | chip 1 | chip 2 (S149) | chip 2 (S148, superseded) |
|---|---|---|---|
| A — `DSP4_C2_BQ_GRAPH=0`, the fallback | `1be74e042cff134c7085dfb08dade517` | **`e2de920d22edbbe76c1210a737abf6b7`** | `2bddaa05367887eb2a349cde7b3d5055` |
| **B — ships** | `6d7b86ec69778900ce63b9eb79c144ea` | **`0a460926f8a2c9088bc0bc509f30769e`** | `e76d2dc8463292a2ba2f6b9172cb6be5` |
| C — `DSP4_TEST_NODES=1` | `c031613ac9a0a02e4c1d493bea19765d` | **`0b63f4e044e00e4a7cbe7b2ff345c0b6`** | `8674f98fdf2975b974c8fc83430c4240` |
| D — `DSP4_RTA=1 DSP4_CUE=1` | `c9bf6659fd888626465932c3814adb5f` | **`c1d9f5db83bad18b78c000178a49191b`** | `edbdb100e7fb60b14e0e5285b156471c` |

**Every arm's chip-1 md5 is unchanged, and that is the cheapest available
proof that the blast radius is what this report says.** All three items are
chip-2 only by construction — `mix_fabric.asm` and `fx_cap.asm` live in
`src/chip2/`, and chip 1 has neither a chip-2 mix bus nor an FX engine — and
four independent builds agree.

The shipping arm's chip-2 image was produced **three** times in this session
from separate build runs (`build_s149_cap`, and twice through
`build-images.sh`) and came out byte-identical every time.

| pool | chip 2, arm A | chip 2, **arm B (ships)** | chip 2, C | chip 2, D | limit |
|---|--:|--:|--:|--:|--:|
| code (VISA SW) | 175,492 — 66.9 % | **189,838 — 72.4 %** | 191,316 — 73.0 % | 189,910 — 72.4 % | 262,144 B |
| DM data + stack | 302,316 — 80.6 % | **333,956 — 89.0 %** | 334,044 — 89.0 % | 334,380 — 89.1 % | 375,264 B |
| delay lines | 1,886,112 — 91.0 % | **1,886,112 — 91.0 %** | 1,886,112 — 91.0 % | 1,886,112 — 91.0 % | 2,072,576 B |

Chip 1: 181,490 — 69.2 % code / 309,612 — 82.5 % DM / 506,880 — 24.5 % delay
on arms A and B, unmoved.

**Not one byte of delay pool moves**, on any arm, for any of the three items.
The pool stays at 91.0 % and stays the thing the *next* feature runs out of.

`MW/D24/DSP/s146/build-images.sh` carries the new md5s and gates on them;
`MW/D24/DSP/s146/switch-runbook.md` is re-pointed at §2.1, §2.2, §2.3, §2.4,
§4 step 1, §6 gate 3, §7, §8.1, §8.2 and §9, with every superseded value kept
visible.

🔴 **S149-7, found while re-recording the runbook's artefact table: the
`.sym.json` md5s are not reproducible and never were.** Arm A's `chip1.ldr`
reproduces byte for byte and its `chip1.sym.json` does not — `8896ddff…`
against S146's `bc796228…`. Compared key by key against the map of a chip-1
image known to be byte-identical: **6,398 symbols both ways, zero differing
addresses.** The only difference is the numbering of the compiler's own
`___ADI_AGL_CRT_SW_BRANCHRETURN_nnnnn` labels, which moves when the *other*
chip's compilation-unit count changes. Nothing gates on those md5s
(`build-images.sh` gates `.ldr` only) and nothing should start; the runbook
now says so instead of listing them beside the `.ldr` md5s as though they
carried the same weight.

---

## 7. What the bench must prove, and in what order

Three rows go in FRONT of the twelve already queued in the S146 runbook §7,
and the order is the one that makes each next number worth taking. They are
capacity rows, they need no analog path, and each turns a construction this
tree is several sessions deep in into a measurement.

**0a. The BYPASS row — the term the whole in-use column is built on, and it
has never been measured.** Driven chip-2 figure with every `Fx*AuxOn` at its
default of 0, then with ONE FX return open into ONE aux. It measures
S148-1's 2,112 c/blk directly, and with it S149 §1.3's whole per-crosspoint
rate table stops being an instruction count and becomes a calibration.
**Before row 3**, because row 3 measures the regime the levers help least
and on its own cannot tell a good in-use construction from a bad one.

**0b. The fabric's own before/after on one driven row.** Everything patched,
arm B against a `DSP4_C2_MIX_FABRIC=0` arm. The audio must be identical (it
is bit-exact by construction, so a difference is a defect and not a
tolerance) and the fabric arm lower by about the counted 8,696
instructions/block. **The only row that prices L1 rather than modelling it.**

**0c. The reverb cap, at the cap.** Four engines requested on Reverb: three
run it, the fourth keeps what it had, `Fx*Type` reads back what was written,
capacity sits at the three-reverb figure, and freeing a slot grants the held
one within one block. Then six. **S149-4: the six-reverb capacity row itself
now needs `DSP4_FX_REVERB_CAP=0`.**

Then the runbook's own twelve, unchanged, with row 3 still the row that
decides whether this graph ships.

**Also owed, and not a bench row:** S149-1's 80-bit readout is PW's ruling
(it is an audio change), and S149-2's crossover pairing is a session of its
own worth 0.82 points.

---

## 8. State left behind

- **Nothing was flashed, no DSP image was loaded, no app was deployed, and
  MW-D24-2 was not contacted at all** — not one read, not one GPIO, no SPI,
  no rails. This session touched scratch builds and this tree only.
- `defs.lock` untouched, `proposals/` untouched, `MW/D24/MX/_matrix.csv`
  untouched: **no contract change, no cell added, no DSP address moved.** The
  proposed `Fx[1-8]TypeAvail[1-1]` cell is in §5 of this report and nowhere
  else.
- Three commits, one per item, each with its own build and its own numbers.
- `shipping.config` gains two lines with PW's rulings recorded beside them,
  in the same form as the S82 pairing signature and the S147 BQ_GRAPH one.
- **The shipping config triple does not move**: `0xCF45FF10 / 0xE2019E6F /
  0xC47C0FA6`. `MW/D24/DSP/accept/manifest.json` and `d24_selftest.py`'s
  `SIGNED_TRIPLE` need no change, and neither was touched.
- New tools: `tools/dsp/c2_mix_fabric_ref.py`, `tools/dsp/c2_mix_cost.py`,
  `tools/dsp/fx_reverb_cap_ref.py`. All three run desk-side, in seconds, with
  negative controls that fire.
- Findings S149-1 … S149-7 are in `findings.md`.
