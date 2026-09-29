provenance: AI-drafted 2026-09-29 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S149 — the capacity levers PW approved, built and priced

Session 149, 2026-09-29, desk only. Hub dispatch `tasks.md` 2026-09-29 11:00Z.
Nothing flashed, no DSP image loaded, no app deployed, the unit not contacted
at all — scratch builds and reads of this tree only.

PW's rulings on S148, verbatim: *"Yes, both"* (L1 the fabric, L2 the follower
pairing) and *"cap reverbs to 3"*.

---

## 0. What this session did, in one table

| | | |
|---|---|---|
| **L1** | chip 2's mix buses on the live-crosspoint fabric | built, proved bit-exact desk-side, **9.29 points** in the in-use regimes plus **1.59 points unconditionally** |
| **L2** | the pair drivers taught about followers | see §4 |
| **cap** | at most three Type Reverb engines at once | see §5 |

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
