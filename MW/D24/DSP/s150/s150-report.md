provenance: AI-drafted 2026-09-29 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S150 — the aux matrix, built as ruled

Session 150, 2026-09-29, desk only. Hub dispatch `tasks.md` 2026-09-29
13:05Z. Nothing flashed, no DSP image loaded, no app deployed, **MW-D24-2
not contacted at all** — not one read, no GPIO, no SPI, no rails. Scratch
builds and reads of this tree only.

PW's rulings, all 2026-09-29: the **team model** (aux i's FINISHED output
feeds aux j's BUS, before aux j's strip, and each aux keeps its own
processing); *"matrix mixing should disallow all potential feedback paths,
and grey out skin controls to help user, more cells can be added if
required"*; *"0.33 ms latency is ok, but no more"*; and
`Aux[1-12]AuxAvail[1-1]` approved as a host-managed bitmask the DSP never
reads.

---

## 0. What this session did, in one table

| | what | where |
|---|---|---|
| **the matrix** | 15 crosspoints on every aux sum — three masters and twelve auxes — on S149's live-crosspoint fabric | §1 |
| **the alignment** | every aux sum reads its WHOLE input set one block late; +16 samples, 98-sample aux contract | §2 |
| **the guard** | the 12×12 closure, a loop-closing coefficient held at exactly zero, proved and fuzzed | §3 |
| **the price** | 1.54 points always, 2.91 in the worst legal patch; worst reachable regime **90.28 %** | §4 |
| **the images** | **all four S146 arms byte-identical to S149's**, plus arm M | §5 |
| **the host half** | the contract the app must implement, written out for the hub | §6 |

**The one thing to read if you read nothing else.** The matrix is built,
proved and priced, and **its switch ships OFF**, because the 360 crosspoint
words it needs are proposed to the hub gate and not yet landed. That is not
a hedge about the design — it is that on the landed defs pin no host can
write a crosspoint, so turning it on would buy +16 samples of aux latency
and 1.54 points for a feature nothing can reach (S150-3). Land the proposal,
advance the pin, regenerate, flip one line.

---

## 1. What was built

### 1.1 The graph

Each of the twelve `C2_MIX_AUX_j` nodes gains fifteen sources, appended in
this order and no other:

```
  C2_MAIN_DLY     MainL[1-1]AuxSend/AuxOn[1-12]
  C2_MAIN_DLY_R   MainR[1-1]AuxSend/AuxOn[1-12]
  C2_CTR_LIM      MainCtr[1-1]AuxSend/AuxOn[1-12]
  C2_AUX_DLY_01..12   Aux[1-16]AuxSend/AuxOn[1-12]
```

**The cells are the ones the master already declares** — every one of them
landed as UNMAPPED, with the aux-to-aux family's own note already saying
*"a self-feed or a feed that would close a loop is inert"*. Nothing was
added to `defs` and nothing to `defs/proposals`; what S150 adds is a reader
and, through `gen_dsp.py --propose`, an address for each (§5.3).

**The source is `C2_AUX_DLY_i` and that is PW's team model read literally**:
the last node of aux i's strip, after its fader, EQ, GEQ, anti-feedback,
limiter and delay. The destination is `C2_MIX_AUX_j`, the bus, before aux
j's own strip. Aux j therefore processes what aux i finished, which is what
"each aux keeps its own processing" means.

**ORDER IS LOAD-BEARING: masters first, auxes last.** An L/C/R master can
never close a cycle — the reverse cone of the main and centre buses contains
no `C2_AUX_*` node, which `tools/dsp/aux_matrix_ref.py` recomputes from
`dsp.csv` on every run rather than taking from S148 — so the three masters
are never gated, and putting them ahead of the aux feeds is what lets the
coefficient fold gate a CONTIGUOUS TAIL instead of a hole in the middle of
its loop.

### 1.2 The kernel

The fifteen are ordinary switched crosspoints of the kind S23 gate 3 built
and S143 extended: an on/off flag and a ramped send level folded into ONE
Q4.28 coefficient at block rate, summed by S149's live-crosspoint fabric.
**No new arithmetic, and that is the point** — a dead crosspoint costs the
fabric six instructions and is never gathered, which is what makes a
144-crosspoint matrix affordable at all.

Three things are new in the emitted code:

1. **The fold runs as TWO loops**, not one. The last twelve crosspoints are
   the aux feeds, and each carries a GATE word the no-feedback guard owns;
   the loop over them ANDs the gate into the host's own `on` bit before the
   coefficient is stored. The other thirteen keep the loop they had, to the
   instruction. Paying a load and an AND for the FX and group sends, which
   can never close a cycle, would be 156 instructions a block for nothing.

2. **A chip-2 aux sum is emitted in TWO ARMS**, `#if DSP4_C2_AUX_MTX` /
   `#else`, because a source list is not something the preprocessor can cut
   down and the control arm has to rebuild the pre-matrix node byte for
   byte. It does: §5.1.

3. **The matrix arm is FABRIC-ONLY.** `DSP4_C2_AUX_MTX` implies
   `DSP4_C2_MIX_FABRIC` (dsp_block.h forces it), the fabric call is a tail
   jump, and nothing can fall past it — so the generic per-sample wrapper is
   not emitted in that arm. It was being assembled and never executed, and
   at twenty-six sources it is **11,880 bytes of chip-2 code**. Removing it
   is why the matrix arm's code pool goes DOWN.

---

## 2. The alignment, and PW's ceiling

### 2.1 What it is

**Every source of every aux sum is read exactly one block old.** Two
different mechanisms, one result:

* the **fifteen matrix sources** need no mechanism at all — they run LATER
  in the chip-2 chain than the sums that read them, so `_blk_C2_AUX_DLY_i`
  holds the previous block's output at the moment the sum reads it;

* **everything else** — the aux's own interchip receive, the six FX returns,
  the four group sends — is read from `_auxal_<src>`, a snapshot
  `_c2_aux_mtx_pre` takes at the HEAD of the chain, before any of those
  nodes has published this block.

Without the second half the matrix leg would arrive a block after the direct
leg and the two would comb, first notch at about 1.5 kHz.

**It is not engaged per aux, and that is S148's finding rather than a
preference.** What a crossfade would be fading is a signal against its own
333 µs echo, which is a sweeping comb on programme material at any fade
length. So it is always on.

### 2.2 The contract, and the ceiling PW signed

| path | before | after |
|---|--:|--:|
| main, monitor, phones | 82 samples / 1.708 ms | **unchanged** |
| **aux** | 82 samples / 1.708 ms | **98 samples / 2.042 ms** |

The added latency is **exactly one block: 16 samples = 0.3333 ms at
48 kHz**. PW: *"0.33 ms latency is ok, but no more."* That is the whole
budget, spent once.

**It is checked and not asserted.** `aux_matrix_ref.py` reads
`DSP4_BLOCK_SIZE` out of the emitted header, computes the added
milliseconds and FAILS above 0.3334; `mtx_order_violations()` in
`dsp_codegen.py` fails the BUILD if any matrix source ever stops running
later than the sum that reads it, because that is the thing that would
silently make the alignment wrong; and the ref model checks that no aux sum
is itself snapshotted, which is the thing that would make it two blocks.
**Any number above one block here is a 🔴 stop and not a trade**, and the
tree now refuses rather than reports.

The desk model carries it too: `tools/pi/dsp4_buildcfg.py`, which has held
the 82-sample figure since S9-2, now states the aux path beside it.

---

## 3. The no-feedback guard

### 3.1 The two layers

PW: *"matrix mixing should disallow all potential feedback paths, and grey
out skin controls to help user."*

**Layer 1 is the HOST** (§6): single writer, refuses a loop-closing write,
publishes `Aux[1-12]AuxAvail[1-1]` so skins grey the cell out before it can
be touched.

**Layer 2 is the DSP**, and it is here so that a write the host should not
have made can never cost a howl or a missed block. It is the shape the
reverb cap established at S149: the guard only ever READS the host's word.

### 3.2 What it does

`_c2_aux_mtx_pre` (`src/chip2/aux_matrix.asm`), once per block, at the head
of the chain, outside every prefix cut:

1. the alignment snapshot (§2);
2. build one request bitmask per destination bus out of the host's `on`
   words;
3. compare with last block's — **if nothing changed it returns**, which is
   what keeps a closure a control-rate computation;
4. otherwise rebuild the closure **from nothing**, in a fixed order
   (destination ascending, then source ascending): `reach[j]` starts as
   `{j}` and an edge i→j is granted unless j already reaches i;
5. publish one gate word per crosspoint — all-ones for granted, **exactly
   zero** for held.

**A self-feed is the i == j case** and the same test refuses it, with no
special case: `reach[j]` contains `j` from the start.

**Rebuilding rather than patching is the design decision.** It makes the
granted set a pure function of the request: two units given the same writes
are in the same state, no sequence of writes can leave a legal patch held,
and a held edge is released the instant the request changes so the loop
cannot close.

### 3.3 The proof

`tools/dsp/aux_matrix_ref.py`, desk-side, in seconds:

```
aux matrix, no-feedback guard
  graph: 724 nodes, 12 aux sums carrying a matrix block
  OK    with the matrix edges removed, no aux sum depends on any aux node (0 found)
  OK    no master source ['C2_CTR_LIM', 'C2_MAIN_DLY', 'C2_MAIN_DLY_R'] depends on any aux node — so an L/C/R feed can never close a cycle and is never gated
  OK    the emitted guard is sized for 12 buses, the graph has 12
  OK    every bus's crosspoint row is where the graph puts it (offset 13 in a 25-crosspoint list)
  OK    the granted gate is all-ones, not 1 — the fold ANDs it into the host's own on word
  OK    the request pass READS the host's on words and never stores through that pointer — `_mix_on_` is the host's word and a read-back still says what the panel says
  OK    the alignment snapshot covers exactly the 22 non-matrix sources of the aux sums, in graph order
  OK    every matrix source runs LATER in the emitted chain than the sum that reads it — the read is one block late (0 bad)
  OK    every non-matrix source is read from the alignment snapshot, so the whole input set is the same age (0 bad)
  OK    every sum reads the gate row the guard writes for it (row j at +12*j, destination bus j+1) — []
  OK    the snapshot and the guard run before the first aux sum
  OK    the alignment adds ONE block = 16 samples = 0.3333 ms — PW's ceiling is 0.33 ms and this is the whole of it
  OK    aux through-DSP contract: 82 + 16 = 98 samples = 2.042 ms (main/monitor/phones unchanged at 82 / 1.708 ms)
  OK    no aux sum is itself snapshotted — a sum feeding a sum through the alignment history would be a second block of delay
  OK    no cycle in the granted graph  (20000/20000)
  OK    a legal (acyclic) request is granted in FULL  (20000/20000)
  OK    the grant is a function of the request alone  (20000/20000)
  OK    a self-feed is always held  (20000/20000)
  OK    a held edge is granted once the loop cannot close  (20000/20000)
  OK    the request word is never modified  (20000/20000)
  OK    exhaustive over every request on a 4x4 matrix (65536 of them): never a cycle, every acyclic request granted
  OK    negative control (test the reverse EDGE, not reachability) lets a cycle through — it fires

```

The properties are the ones the RULING asks for, not the ones the code
happens to have, and the judge is written the other way round from the
guard: the guard maintains reachability incrementally, the judge walks the
finished graph with a depth-first search. The exhaustive arm runs **every
one of the 65,536 possible requests** on a 4×4 matrix.

**The negative control is the guard somebody writes when they are thinking
about a two-node loop and not about a graph**: test the reverse EDGE instead
of reachability. It lets a cycle through, and it must.

### 3.4 What it costs

| | instructions/block | points |
|---|--:|--:|
| the alignment snapshot (22 blocks) | 932 | 0.25 |
| the request bitmask | 720 | 0.19 |
| "did it change?" | 135 | 0.04 |
| **steady state** | **1,787** | **0.48** |
| a block in which it DID change | 9,983 | 2.69, once, bounded |

The worst block is bounded by construction: a DAG on twelve nodes has at
most sixty-six edges, so the reach update runs at most sixty-six times. A
2.69-point spike on one block of a control change, on a graph whose worst
steady regime is 90.3 %, is not a risk anybody has to track.

---

## 4. The price

Counted off the emitted code with S149's method, at the tree's own
calibration (S148 §6.2 prices `C2_MIX_AUX_01` off the S23 bypass at 2,112
cycles/block where `c2_mix_cost.py` counts 2,394 instructions — 0.882
cycles per instruction).

```

  one aux sum, instructions per block:
    prologue, S23 bypass taken         364 ->    856   (+492)
    prologue, full path                376 ->    868   (+492)

  _c2_aux_mtx_pre, instructions per block:
    alignment snapshot (22 blocks)     932
    the request bitmask                720
    "did it change?"                   135
    STEADY STATE                      1787   = 0.48 points
    a block in which it DID change    9983   = 2.69 points, bounded

  D24 chip-2 aux bill, 8 buses:
    regime                                           before    after   points
    idle, every aux on the S23 bypass                  2912     8635    +1.54
    desk in use (worst legal patch with the matrix)    13464    24275    +2.91

  the regimes, arm B (constructions on S149 §3.3, not new
  measurements — no cycle figure here was taken on a part):
    regime                                                     S149     S150
    R1  Echo default, nothing switched on                    74.83%   76.37%
    R2' three reverbs (PW's cap), nothing switched on        82.28%   83.83%
    R3  Echo default, desk IN USE                            79.91%   82.82%
    R4' three reverbs AND the desk in use                    87.36%   90.28%

  ABORT LINE ~97 %. The worst regime the product can be put
  into is the last row, and the no-feedback guard is what
  makes it a WORST case rather than an open-ended one.
```

**The in-use row is the worst patch the guard will allow, not an average.**
Every FX return and every group send open on every aux (S148's in-use
definition), plus the MAXIMAL legal matrix: a DAG on eight aux buses has at
most 8·7/2 = 28 edges — bus j taking a feed from every lower-numbered bus —
plus all three masters into all eight. Fifty-two more live crosspoints, and
**the no-feedback guard is what makes that a worst case rather than an
open-ended one.** Without the guard the host could ask for all 64 aux→aux
crosspoints; with it, 28 is the ceiling, and it is a ceiling in the image
rather than in a convention.

**The worst regime the product can be put into is 90.28 %**, against a ~97 %
abort line — 6.7 points of margin, where S149 left 9.6. Every figure here is
a construction on S148's measured baselines; **no cycle figure in this
session was taken on a part.**

**What the matrix does NOT cost when idle is the fabric.** With every
switched coefficient zero the S23 bypass still fires and an aux sum is still
a block copy — the +1.54 unconditional points are the fold walking
twenty-five crosspoints instead of ten, and `_c2_aux_mtx_pre`.

---

## 5. The images

### 5.1 The four arms do not move, byte for byte, on both chips

```
=== arm A  (bq0)  DSP4_C2_BQ_GRAPH=0
  OK  chip1 1be74e042cff134c7085dfb08dade517  chip2 e2de920d22edbbe76c1210a737abf6b7
=== arm B  (bq1)
  OK  chip1 6d7b86ec69778900ce63b9eb79c144ea  chip2 0a460926f8a2c9088bc0bc509f30769e
=== arm C  (tn)  DSP4_TEST_NODES=1
  OK  chip1 c031613ac9a0a02e4c1d493bea19765d  chip2 0b63f4e044e00e4a7cbe7b2ff345c0b6
=== arm D  (rta)  DSP4_RTA=1 DSP4_CUE=1
  OK  chip1 c9bf6659fd888626465932c3814adb5f  chip2 c1d9f5db83bad18b78c000178a49191b

every arm built reproduces its recorded image byte for byte
```

**Every one of those eight md5s is S149's.** The switch defaults off, the
whole of the matrix is inside its `#if`, and `build-images.sh` gates it.
This is the strongest available statement about the blast radius, and it is
stronger than S149's: S149 moved every chip-2 image and held chip 1; S150
moves neither.

*One qualification, stated because it is the kind of thing that gets quietly
elided.* The `DSP4_C2_AUX_MTX` term in `DIAG_CFG3_INSTR_SUM` is written
`!= 0`, not `!= 1`, precisely so that the SHIPPING value contributes nothing
and the arms above are the signed ones. A build with the matrix ON therefore
reads DIAG_BUILD_CFG3 bit 23 = 1 and calls itself an instrument, **which it
is** until the pin carries the addresses. When PW adopts it the term flips
to `!= 1` with the default, in the same commit, and the triple is re-scored.

### 5.2 Arm M — the matrix arm

```
=== arm M  (the aux matrix, DSP4_C2_AUX_MTX=1, GRAPH provenance)
  OK  chip1 e549e1fad764c790d272337f8b8a0f85  chip2 a317906713e9a11f193d98db94295f0c
  (desk image: the crosspoint addresses are PROPOSED, not landed)
```

`MW/D24/DSP/s146/build-images.sh M` builds and gates it. It is built out of
a SCRATCH copy of `src/` with the GRAPH's own dispatch tables dropped in
(`gen_dsp.py --params-dir`), because the landed tables correctly have no
address for a crosspoint the hub has not gated. Same bytes, different
provenance: nothing has gated those rows and the defs pin does not describe
this image.

**Chip 1's image differs from arm B's in exactly one constant**, the
instrument bit. The matrix is chip-2 code and chip 1 has no aux sum.

| pool | chip 2, arm B | chip 2, **arm M** | limit |
|---|--:|--:|--:|
| code (VISA SW) | 189,838 — 72.4 % | **177,958 — 67.9 %** | 262,144 B |
| DM data + stack | 333,956 — 89.0 % | **346,732 — 92.4 %** 🔴 | 375,264 B |
| delay lines | 1,886,112 — 91.0 % | **1,886,112 — 91.0 %** | 2,072,576 B |

**Not one byte of delay pool moves.** Code goes down by 11,880 (§1.2). DM
goes up by 12,776 and crosses the 90 % warn line — S149-5 predicted exactly
this and **S150-1 is the finding, with the LDF rebalance recommended and not
taken**.

### 5.3 The contract handoff

`gen_dsp.py --propose` has written the address proposal for all four
products: **336 cells on D32, 176 on D24**, 96 on D16, 48 on D12, each
moving from `dsp-unmapped.csv` to `dsp.csv`, and **nothing else in those
files changes**. The 360 chip-2 words are allocated AFTER every existing
allocation — after `resolve_late_c2()` and after the Out3 mute — so **not
one existing address moves**, the same discipline `xp_page`, `mo_page` and
`mtx_page` were added under.

`defs/` itself is untouched. `defs.lock` is untouched. No cell was added
anywhere; the master already declares every one of them.

### 5.4 Gates

| gate | result |
|---|---|
| `check-sharc-codegen-drift.sh` | **760 generated / 0 differ**, 0 absent |
| `build-images.sh` (A–D) | **all four green, exit 0, every md5 unmoved** |
| `build-images.sh M` | green |
| `golden_harness.py` | 59/59 |
| `dsp_validate.py` (724 nodes) | OK — the same four pre-existing process-order notes as S144/S147/S149 |
| `test_dsp_validate.py` | 20/20 |
| `stereo_split_check.py` | passed — 959 declared input edges read, 180 matrix crosspoints excluded by name |
| `follow_lockstep_check.py` | 11/11 |
| `dsp_simulate.py --stereo-proof` | passed — every one-sided sink reads EXACTLY zero on the far side |
| `product_fit.py --check-masks` | all four products OK |
| `check_shipping_config.sh` | consistent, **triple unmoved** `0xCF45FF10 / 0xE2019E6F / 0xC47C0FA6` |
| `aux_matrix_ref.py` | every check passed, negative control fires |
| `gen_dsp.py --check-proposal` | the graph is AHEAD of the landed contract — S150-3, by design |
| `check-contract-drift.sh` | **RED, and deliberately so** — see below |

🔴 **`check-contract-drift.sh` and `regenerate-dsp-contract.sh` do not pass
on this tree and will not until the hub lands the proposal.** Both run
`gen_dsp.py`, which refuses to generate anything while the graph proposes
cells the landed `defs/products/<p>/dsp.csv` does not carry — 336 on D32,
176 on D24, every one of them a matrix crosspoint. That refusal is the
no-fallback policy working: the alternative is generation quietly falling
back to the graph and producing an address map the defs pin does not
describe. It is the same window S143 and S144 sat in between a graph change
and a defs tag, and the same one `--propose` / `--params-dir` /
`DSP_LANDED_DIR` exist to make workable. **It clears in one step: land the
proposal, advance the pin.** Nothing else in this tree is left red, and the
drift check leaves no diff behind (checked).

---

## 6. The HOST half — the contract, for the hub (mx26 app)

This is the app's work, not this repo's. It is written precisely because
layer 2 is a guard and not a user interface: the DSP makes a bad write
harmless, the host is what makes it impossible.

**6.1 Single writer.** Every `Aux*AuxOn`, `Aux*AuxSend`, `MainL/R/Ctr
*AuxOn/*AuxSend` write goes through the one writer that already owns
`DspApply`/`DspAddressMap`. No second path.

**6.2 The rule.** Maintain the directed graph whose nodes are the product's
aux buses and whose edges are the aux→aux crosspoints currently ON. Before
granting a request to turn ON `Aux<i>AuxOn<j>`, test whether `j` can already
reach `i`; if it can — or if `i == j` — **refuse the write** and do not send
it. The master↔aux crosspoints (`MainL/MainR/MainCtr`) are never refused:
they cannot close a cycle.

**6.3 Publish availability, on EVERY enable and on EVERY disable.**
`Aux[1-12]AuxAvail[1-1]`, one host-managed bitmask per DESTINATION aux, bit
N−1 set = source Aux N may be selected into this aux right now. It is
recomputed and republished after every change in either direction —
**disable is the half that is easy to forget and it is the half that makes
a greyed cell come back.** The DSP never reads it.

**6.4 The skin greys the cell.** A crosspoint whose availability bit is 0 is
drawn unavailable and cannot be touched, which is what PW asked for. The
diagonal (a self-feed) is always unavailable. **An aux's own bit in its own
mask is always clear; every other bit is set unless the edge would close a
loop.**

**6.5 Read-back is the truth.** The DSP never writes `_mix_on_`, so
`Aux*AuxOn` reads back exactly what was written. If the host and the DSP
ever disagree about what is live, the host is wrong, not the DSP — and the
DSP's own granted set is one word per bus at `_auxmtx_live` for a bench tool
to read.

**6.6 What the host must NOT do.** Do not rely on the DSP guard as the rule
— it is the backstop, and an edge it holds is silent with no UI to say so.
Do not send a loop-closing write "because the DSP will handle it".

**6.7 Not proposed, and the reason is stated.** An `Aux[1-12]AuxLive[1-1]`
read-back of what the DSP actually granted is NOT proposed: with
`AuxAvail` published correctly a held state cannot be reached through the UI
at all, so the cell would exist for a race the two layers are there to
prevent. The same argument S149 §5 made for `Fx TypeLive`, and the same
answer if PW wants it anyway: the DSP word already exists.

---

## 7. What the bench must prove

Three rows, added to the S146 runbook §7 AFTER S149's three and BEFORE the
twelve. **Every one of them needs arm M**, and none can be taken on the
shipping arm, where the matrix is compiled out.

**0d. The aux→aux path exists and goes the right way** — aux 2 must carry
aux 1's PROCESSED output, after aux 1's own EQ, limiter and delay. That is
what distinguishes PW's team model from a pre-strip tap, and no desk check
can tell them apart.

**0e. The alignment, measured, and it is PW's ceiling** — arm M's aux path
EXACTLY 16 samples later than arm B's, 98 against 82, and not 32. Main,
monitor and phones must not move. **A second block is a 🔴 stop.**

**0f. The guard refusing a loop, on the part** — open 1→2, ask for 2→1: the
second must be inert, must still read back 1, and the desk must not howl.
Then close 1→2 and confirm 2→1 goes live within one block with no further
traffic. Then the three-node loop, 1→2→3→1, which is the one a direct-edge
guard would miss.

---

## 8. State left behind

- **Nothing was flashed, no DSP image was loaded, no app was deployed, and
  MW-D24-2 was not contacted at all.** Scratch builds and this tree only.
- **`defs/` and `defs.lock` untouched. No cell added anywhere.**
  `proposals/defs/products/*` carries the address proposal — 336 cells on
  D32, 176 on D24 — and that is the whole of the contract change this
  session asks for (S150-3).
- **`MW/<P>/MX/_matrix.csv` untouched**, and every generated DSP artefact
  still tracks the LANDED pin, because `gen_dsp.py` refuses to generate
  while the graph is ahead of it. That refusal is correct and it is why the
  switch ships off.
- **The shipping config triple does not move**: `0xCF45FF10 / 0xE2019E6F /
  0xC47C0FA6`. `accept/manifest.json` and `d24_selftest.py`'s
  `SIGNED_TRIPLE` need no change and were not touched.
- New tool: `tools/dsp/aux_matrix_ref.py`. Extended:
  `tools/dsp/c2_mix_cost.py --matrix`.
- New generated file: `MW/D32/DSP/SHARC/src/chip2/aux_matrix.asm`.
- Findings S150-1 … S150-6 are in `findings.md`. **S149-1 is answered in
  S150-4, with a recommendation and no build: it is an audio change and it
  stays PW's.**
