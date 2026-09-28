provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S142 — the four block-audit rulings: priced, and stopped on a prerequisite

Session 142, 2026-09-28, desk only. Hub dispatch `tasks.md` 2026-09-28 11:52Z.
Nothing flashed, no DSP image loaded onto MW-D24-2, no app deploy, no bench
contact of any kind this session.

---

## 0. Outcome

**The pricing gate passed and the build stopped one step in front of item 1, on
something the dispatch did not know about.**

- **All four items were priced against the signed driven budget** and they fit:
  +7.17 % of chip 2 over S86's measured 84.47 %, landing at 91.6 % with the
  shipping FX default. `MW/D24/DSP/s142/s142-pricing.md`.
- **The reverb case does not fit, and did not before this work either.** Six
  engines at Type 3 cost +16.44 points measured (`FX_C2_D24_TYPE3_REVERB`), so
  today's graph is already at 99.4 % in that regime. That is a pre-existing
  condition this session found while pricing, not one it created.
- **No feature is traded.** `DSP4_C2_BQ_GRAPH` — worth about 17 points of chip
  2, written since 2026-09-02, built, and witnessed at 0 ulp over 36,864 words
  on `bqeverify` — is at 0 in `shipping.config`. With it the four items land at
  74.6 %, and the reverb case at 89.5 %. It is a signature, not work.
- 🔴 **S142-1: the chip-2 main bus is mono from the master fader onward.**
  `_blk_C2_MIX_MAIN_R` is computed every block and read by nothing. Both MAIN
  XLRs, both DAC MAIN slots, the codec aux out and the monitor all carry the
  left bus. Recorded in `findings.md`, priced in the pricing addendum
  (+2.69 % of chip 2), and **it blocks three of the four ruled items**.
- **The build stopped there rather than half-migrating the output stage.** §3
  below is the design for the prerequisite and for all four items, at the level
  where the next dispatch is execution and not discovery.

Desk bars taken this session, all on the tree at HEAD before any change:
`golden_harness.py` **59/59**, `dsp_validate.py` **OK, 702 nodes** with the
same four pre-existing process-order notes, and a **clean two-chip SHARC
build** (CCES 3.0.3, `shipping.config`, exit 0) whose memory report is the
baseline §2 of the pricing document quotes.

---

## 1. Why the build stopped

`dsp_codegen.py:19408` is one line:

```python
node['inputs_str'] = node['inputs'][0] if node['inputs'] else node['id']
```

and every single-input generator interpolates `_buf_{inputs_str}` /
`_blk_{inputs_str}`. `ch_count` exists in the generator only as comment text.
So `C2_MAIN_FDR`, which declares `inputs = C2_MIX_MAIN_L;C2_MIX_MAIN_R` and
`ch_count=2`, reads the left mix and says so in the file it emits:

```
i0 = _blk_C2_MIX_MAIN_L;    /* input  */
i1 = _blk_C2_MAIN_FDR;      /* mono   */
```

A grep over the whole generated tree finds `_blk_C2_MIX_MAIN_R` /
`_buf_C2_MIX_MAIN_R` in exactly two files: the node's own, and
`process_chain.asm`, which calls it and publishes its block. Nothing consumes
it.

This is in the way of three of the four rulings, in their own words:

| ruling | what it asks for | what the graph has |
|---|---|---|
| D5 | "TWO DSP instances (Main L, Main R) sharing ONE parameter set" | one instance |
| D6 | the Woof fed from the "Main L/R sum" | no R to sum |
| D7 | a phones pair off the same source select as a monitor whose `Mon Level` declares L and R | one block behind two level cells |
| D3 | `MainL AuxSend` and `MainR AuxSend`, eight each, as separate matrix sources | one of them would be a copy |

Only item 4's Centre anti-feedback is untouched, because the centre bus
genuinely is mono.

**Why it was not pushed through.** Closing it is a chip-2 topology change
across seven audio generators with a dual-bank crossfade lockstep hazard (§3.1),
and **this tree has no desk-side way to prove it**: there is no click-free or
ramp prover, and no bit-exactness harness for a new chip-2 topology — the only
real check is a capacity row and an audio capture on the part. Landing an
unverifiable half-migration of the output stage on `main`, where the next
session regenerates 726 ASM files from it and builds an image, is the failure
mode this repo's rules exist to stop. It is design-grade work of a shape the
dispatch did not scope, so it is recorded and handed back rather than
improvised.

---

## 2. What the next dispatch should be

**S143 — NO FLASH: give chip 2 a Main R.** The prerequisite, on its own, with
its own capacity row on the part. Then S144 takes the four items in the
dispatched order on top of it. §3.1 is the design; §3.2–§3.5 are the four
items, unchanged from the pricing document but with the graph-level detail
worked out.

One item can be brought forward if the hub wants build progress in parallel:
**item 3's aux→aux and group→aux crosspoints, 60 of its 84**, are entirely
independent of Main R and of the Centre strip, and they extend a mechanism that
already exists and is already proved on the part (§3.4). The 24 Main→aux
crosspoints are additive and move no address when they arrive.

---

## 3. The design

### 3.1 The prerequisite: two instances, one parameter set

The mechanism D5 asks for by name is the general answer, and it needs **no SPI
change, no dispatch change, no new cell and no new address**. A follower node
carries `follows=<master node id>` in its `params` and:

- **reads the master's coefficient and parameter symbols** by `.extern` —
  `_fdr_q_`, `_geq_coeffs_A/B_`, `_geq_gains_`, `_xover_lp_A/B_`,
  `_{pfx}_active_`, `_{pfx}_xfade_alpha_`, `_dly_ms_`, the limiter and
  compressor threshold/attack/release words;
- **keeps its own state** — `_{pfx}_state_A/B_`, the envelope registers, its
  own delay line, its own `_buf_`/`_blk_`;
- emits **no** `.var` for anything it follows, and **no** design hook (the
  master designs once; the follower uses the result);
- maps to **no cell** (`_NODE_PATTERNS` → `None`) and takes `spi_page/addr` of
  the master's, with an `_UNREACHED_REASONS` entry saying why.

The nodes to add, all chip 2, all `follows=` their L counterpart:
`C2_MAIN_FDR_R`, `C2_MAIN_GEQ_R`, `C2_MAIN_COMP_R`, `C2_MAIN_LIM_R`,
`C2_MAIN_DLY_R`, `C2_MAIN_XOVER_R`. `C2_MAIN_OEQ_02` / `OCOMP_02` / `OLIM_02`
(the MainR leg) then take `C2_MAIN_XOVER_R` as their input instead of
`C2_MAIN_XOVER`, which is the one-line fix that makes the two MAIN XLRs carry
different signals. `C2_MAIN_ST_OUT` and `C2_CODEC_AUX_OUT` grow a second TX
slot walk; `C2_MON` reads a second block.

**Three hazards, found in the reading and stated so they are not re-found on
the bench:**

1. **Crossfade lockstep.** `_fx_cascade_node` clears `_{pfx}_swap_pending_` and
   advances `_{pfx}_xfade_alpha_` / flips `_{pfx}_active_` inside the body. A
   follower that runs *after* the master and reads those words sees the
   post-update values and will use the wrong bank for its own block — silently,
   and only during a coefficient change. The follower must therefore read a
   **latched** copy the master writes at the top of its own block, not the live
   words; one extra DM word per followed cascade, written before the master
   uses it.
2. **Linked dynamics, not duplicated.** A stereo bus compressor and limiter
   must detect on max(|L|,|R|) and apply **one** gain to both, or the image
   walks under compression. So `C2_MAIN_COMP_R` / `C2_MAIN_LIM_R` do not run a
   second detector: they read the master's gain word and apply it. This is
   cheaper than duplicating and is the only correct behaviour.
3. **The pairing groups.** S23-3 is the precedent: `repair_process_order` moves
   producers ahead of consumers and `c2_pair_groups` refuses a chain whose
   nodes are not a contiguous run. Insert the R nodes in **row order** beside
   their masters, as S23 did for the aux sums, and check `c2_pair_groups`
   accepts the result before building.

Price: **+8,810 c/blk = +2.69 % of chip 2**, and one more 250 ms mono delay
line (+48,000 bytes, taking the delay pool to 88.7 %). With
`DSP4_C2_BQ_GRAPH=1` the two GEQs and the two crossovers become exactly the
adjacent pair that lever pairs, so most of it comes back.

### 3.2 Item 1 — Centre/LF (D6 + D5)

The centre bus already exists and is already paid for: `C1_BUS_SUB` carries
every channel's `Chan*CtrOn` send — *"on this product the sub bus IS the centre
bus"*, PW ruling R5 — and the `C2_SUB_*` chain it feeds has been marked
retired-not-deleted since S1. So this item is a re-patch of the output stage,
not new bus fabric.

**The Centre strip** (re-use, rename `C2_SUB_*` → `C2_CTR_*`):

```
C2_RECV_SUB → C2_CTR_FDR (FADER_PAN, 4w)   MainCtr Level/Mute
            → C2_CTR_EQ  (EQ_BIQUAD 4-band, 24w)  MainCtr Eq*
            → C2_CTR_GEQ (GEQ 31, 31w)      MainCtr Geq[1-31]      NEW
            → C2_CTR_AFB (ANTI_FB 6, 24w)   MainCtr AntiFb*        NEW (item 4)
            → C2_CTR_LIM (LIMITER, 4w)      MainCtr Limiter*
            → C2_OUT3_SEL
```

`C2_SUB_COMP` goes: the block draws no compressor on the Centre strip and the
audit dropped every `Main* Comp*` cell from the generation.

**The Woof strip** (new):

```
C2_MAIN_XOVER(LP) + C2_MAIN_XOVER_R(LP) → C2_WOOF_MIX (MIX_BUS, LF sum)
C2_WOOF_MIX + C2_AUX_DLY_01..08 → C2_WOOF_SRC (SOURCE_SEL, 9 in)  MainSub Src
  → C2_WOOF_XOVER (CROSSOVER LPF)   MainSub Crossover*, Main CrossoverLink
  → C2_WOOF_FDR   (FADER_PAN)       MainSub Level/Mute
  → C2_WOOF_EQ    (EQ_BIQUAD bands=2)  MainSub Eq*
  → C2_WOOF_LIM   (LIMITER)         MainSub Limiter*
  → C2_OUT3_SEL
```

**The shared tail** — the block's "one C/LF XLR through one mute, meter, delay
and DAC":

```
C2_OUT3_SEL (SOURCE_SEL, 2 in)  Main Out3Mode, Main Out3Link
  → C2_OUT3_DLY (DELAY)         Main Out3Delay   (re-uses C2_SUB_DLY's line)
  → C2_OUT3_OUT (OUTPUT_TDM → DAC_14, J55)  Main Out3Mute
  → C2_MTR_OUT3 (METER)         Main Out3Mtr
```

`C2_MAIN_OEQ_03/04`, `OCOMP_03/04`, `OLIM_03/04`, `OUT_03/04` and
`C2_MTR_MAIN_03/04` are removed: they are the wrong shape by ruling, and
removing them frees `DAC_15/16` for the monitor (item 2). The main output loop
becomes `range(1, 3)`.

**`Main CrossoverOn` and `Main CrossoverLink` cost no new allocation**:
`C2_MAIN_XOVER` holds four words at base 1436, of which base+2 and base+3 are
today dispatched only as staging-array coefficients nothing writes. Add
`('Main', 1)` to `_XOVER_STRIPS` for the Freq/Slope pair.

**One new node type, `SOURCE_SEL`**, used three times (here twice, once in item
2). Per-sample body reading the selected `_buf_`, generic chip-2 block wrapper
(`_C2_WRAP_TYPES`), 4 SPI words (sel, link, 2 spare), ramped crossfade on a
change so the switch is click-free. Needs: `gen_source_sel` +
`gen_source_sel_fixed`, entries in `GENERATORS`/`FIXED_GENERATORS`,
`_C2_WRAP_TYPES`, `dsp_validate.py`'s known-type and required-param tables, a
`dsp_simulate.py` branch, `NODE_EXPANDERS` and `_NODE_PATTERNS`.

**`Main Out3*` cells need a suffix prefix.** The expanders build cell names as
`cn(cat, inst, suffix, fun)`; these are category `Main` with suffixes
`Out3Delay`, `Out3Mute`, `Out3Mtr`, `Out3Mode`, `Out3Link`. Add a
`cell_prefix=Out3` param honoured by `expand_delay`, `expand_output_tdm`,
`expand_meter` and the new `expand_source_sel` — a contained change, and the
mechanism is reusable.

### 3.3 Item 2 — phones pair (D7) and pick-off (D8)

Freed by item 1: `DAC_15/16` (rear Monitor jacks) and `DAC_09/10` (phones,
today fed from aux 9/10, which a D24 does not declare).

```
C2_MAIN_FDR / C2_MAIN_LIM / C2_MIX_MAIN_* (+ their R) and C2_CTR_*
  → C2_MON_PICK (SOURCE_SEL, 2 ch)   Mon PickOff        NEW
  → C2_MON  (existing)               Mon InputSel, Mon Level[1-2]
      → C2_MON_DLY (existing)        Mon Delay
          → C2_MON_OUT (OUTPUT_TDM → DAC_15/16)          NEW — closes S122-5
  → C2_PHN  (MONITOR kernel, 2 ch)   Mon PhonesLevel     NEW
      → C2_PHN_DLY (DELAY, 2 ch)     Mon PhonesDelay     NEW
          → C2_PHN_OUT (OUTPUT_TDM → DAC_09/10)          NEW
```

Talkback S1 injects into the phones leg only, per the block. `Mon CueOn` costs
nothing — it is already classed `control-plane`, the host folding it and the cue
state into the one `Mon InputSel` word by ruling D8. The three pick-off taps
cost nothing to publish: under `DSP4_BLOCK_KERNELS` every chip-2 node already
publishes its block, so the tap is a pointer select at control rate.

### 3.4 Item 3 — aux matrix and pairing (D3 + the 09:07 ruling)

**It is not a new fabric. It is more sources on a node that already exists.**
`C2_MIX_AUX_nn` was built by S23 gate 3 with a switched-send half — per-source
on/off plus a ramped level folded into one Q4.28 coefficient at block rate —
and proved on the part (unity return, both negative controls exactly zero, and
the aux sum reproducing `_buf_C2_RECV_AUX_01` in 32 of 32 words with every send
off). The aux matrix adds sources to the same node with the same mechanism, and
`c2_alloc` allocates them after every earlier chip-2 address, so **it adds rows
and moves none**.

Sources added to `C2_MIX_AUX_j`:

| source | cells | count |
|---|---|--:|
| `C2_AUX_DLY_i` for **i < j** only | `Aux{i}AuxSend{j}` / `AuxOn{j}` | 28 |
| `C2_GRP_COMP_g`, g = 1..4 | `Grp{g}AuxSend{j}` / `AuxOn{j}` / `AuxPick{j}` | 32 |
| `C2_MAIN_DLY`, `C2_MAIN_DLY_R`, `C2_CTR_LIM` | `MainL/MainR/MainCtr AuxSend{j}` / `AuxOn{j}` | 24 |

**How a loop is made impossible: by the order, not by a check.** Evaluation is
aux 1 … aux 8 and a crosspoint (i → j) exists in the graph only for i < j. A
strict total order has no cycles, so there is nothing to detect at runtime: the
lower triangle and the diagonal are not crosspoints the generator emits, and no
host write can create one. The cells are all declared — the grid is square and
the skins draw a square grid — and the ones at or below the diagonal resolve to
a coefficient the generator ties to zero, which is what the cell's own note
already says: *"a self-feed or a feed that would close a loop is inert"*. The
aux chains already run 1..12 in row order, so `repair_process_order` has
nothing to move and S23-3's pairing hazard does not arise.

The rejected alternative, named so it is not re-invented: letting every
crosspoint exist and reading a one-block-old snapshot of the aux outputs. A
delayed loop with round-trip gain at or above unity still diverges; it just
takes 333 µs a lap.

**The stereo/mono switch costs no cycles, and that is the design.** `Aux Link`
is carried on the odd aux of each pair. Neither mode changes the number of
MACs — a channel that feeds a pair feeds both members either way. What changes
is the coefficient pair: `send`/`send` in dual mono, `send·gL`/`send·gR` in
stereo, with `gL/gR` read from the one pan table (`tools/dsp/pan_table.py`, PW
ruling R5) at the index `Chan AuxPan` gives. So both modes are always
available (the fabric's shape does not depend on `Aux Link`, nothing is
allocated or freed at switch time), the switch is click-free (the only thing
that moves is a coefficient, and send coefficients already ride the `GainFast`
ramp), and the aux-matrix feeds and aux anti-feedback follow the pairing for
free because they read the same per-aux coefficient column.

`Grp AuxPick` and `Aux PickOff` are pointer selects resolved at control rate
from blocks that already exist.

D24's `CFG_MTX_MASK` drops from `0x3` to `0`: all `Matrix*` and `Chan*Matrix*`
cells are gone from generation `46109e9fb812` (verified: zero rows in the
matrix, in `dsp.csv` and in `dsp-unmapped.csv`), so the four matrix chains
reach no D24 cell and are skipped at block level. About 840 c/blk back.

### 3.5 Item 4 — anti-feedback (D9)

`C2_MAIN_AFB` (2 ch, follows the L instance's coefficients per §3.1) and
`C2_CTR_AFB` (mono), both `notch_count=6`, spliced with
`geq_splice.relink_and_insert` so no address moves. `AntiFbGain` is a
coefficient on an existing path and costs nothing. The feedback limiter is the
existing limiter primitive with its own threshold, inside the AFB node, on
Main (2), Centre (1) and the eight D24 aux buses.

**The detector: one shared 1/3-octave filterbank, time-multiplexed onto the
armed bus**, not one per protected point — 3,566 c/blk instead of 39,226. The
filterbank is the one `tools/dsp/rta_design.py` already designs and `rta.asm`
already implements (`DSP4_RTA=0` today: built, not enabled). The DSP owns the
filterbank, the ring metric (a band that stays within a few dB of its own peak
for longer than music does) and the notch biquads; the host's existing
Antifeedback skin picks the band and writes `AntiFbNotchFreq/Gain/Q`.

Failure modes, stated: a sustained held note at a band centre reads as a ring
(mitigated by the persistence metric and the notch depth limit, not eliminated
— manual mode exists); 1/3-octave resolution places a notch within about ±6 %
of the true frequency, so the Q must be broad enough to catch it, and a
two-band interpolation is the obvious later refinement; six notches is six
modes and the gain walk must stop when the sixth is placed; the detector sees
one bus at a time, so the arming is the operator's.

🔴 **For PW, recorded and not asked:** the detector's *decision* is placed on
the host. If the ring-out must run with no host in the loop, the peak-picking
moves to the DSP and this item costs more. The cell set is the same either way,
so the build above is correct under both rulings.

---

## 4. What the bench must prove

Unchanged from `s142-pricing.md` §8, plus one reading that now comes first:

0. **S142-1, one patch.** A tone into a strip panned hard left, meters on J56
   (`DAC_12`, Main L) and J57 (`DAC_11`, Main R). The desk says they will read
   the same. The desk has been wrong about this hardware before — `DAC_13` was
   "Main Out 1" for months and is not connected to anything — so this is a
   reading, not a formality.

---

## 5. State left behind

`main` carries three commits: the pricing, the S142-1 finding with the
re-priced capacity table, and this report. **No generated artefact was
touched** — `dsp.csv`, `SHARC/src/`, `defs/`, `defs.lock`, `proposals/` and
every `MW/*/MX/_matrix.csv` are as they were at `a96f9037`; `git status` is
clean apart from these three documents. No contract bump is owed. The only
build performed was into a scratch directory outside the tree, for the memory
baseline, and it was not installed.

The unit was not contacted.
