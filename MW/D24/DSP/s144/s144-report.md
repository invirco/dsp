provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S144 — the Centre/LF output, the phones pair and the anti-feedback

Session 144, 2026-09-28, desk only. Hub dispatch `tasks.md` 2026-09-28
13:40Z: items 1, 2 and 4 of S142, on top of S143's stereo main bus.

**Nothing was flashed, no DSP image was loaded onto MW-D24-2, no app was
deployed, and the unit was not contacted at all this session.**

---

## 0. Outcome

All three items are built. The three rear sockets that have been an open
question on the D24 board since S121 are answered, two of them were
carrying the wrong signal, and one of those two was carrying the OPPOSITE
of what it is labelled for.

| item | what it is | state |
|---|---|---|
| 1 | Centre strip, Woof strip, ONE C/LF XLR (D6 + D5) | 🟢 built |
| 2 | phones pair, monitor jacks, `Mon PickOff` (D7 + D8) | 🟢 built, minus talkback (S144-4) |
| 4 | anti-feedback on Main + Centre, ring-out gain, feedback limiter, the detector's ring metric (D9) | 🟢 built |

**Where the sockets go, and what they used to carry:**

| lane | connector | carried | now carries |
|---|---|---|---|
| DAC_14 | J55, rear "Center/LF" XLR | aux bus 12, which D24 does not declare (S121-5) | the ONE C/LF output, through one mute, meter, delay and DAC |
| DAC_15/16 | J53/J54, rear "Monitor" jacks | main outputs 3 and 4 — the crossover's centre and **high-pass** legs (S121-6, and S144-1) | the MONITOR bus |
| DAC_09/10 | J10, headphone jack | aux 9/10, which D24 does not declare (S121-5) | the PHONES pair, own level and delay |

**Eight findings, three of them PW-level and recorded rather than asked**
(no dialogs): `findings.md`, S144-1 … S144-8. The three for PW are S144-3
(`Main Out3Link`'s two readings), S144-4 (talkback injection needs a
fabric slot) and S144-5 (the ring-out decision stays on the host).

**Desk bars, on the tree at HEAD:** `dsp_validate.py` OK on **724 nodes**
with the same four pre-existing process-order notes, `golden_harness.py`
**59/59**, `test_dsp_validate.py` **20/20**, `follow_lockstep_check.py`
**11/11** (it picks the new `C2_MAIN_AFB_R` pair up on its own),
`stereo_split_check.py` passed, `dsp_simulate.py --stereo-proof` passed
with the five new sinks, `product_fit.py --check-masks` OK, SHARC codegen
drift **0 of 757**, and **three clean two-chip CCES 3.0.3 builds** — one
per item on the shipping arm, plus one with `DSP4_RTA=1 DSP4_CUE=1`, which
is the build that found the one real bug in the session (§6).

---

## 1. Item 1 — the Centre strip, the Woof strip and one C/LF XLR

### 1.1 The sub-bus chain was the Centre strip all along

`C1_BUS_SUB` carries every channel's `Chan*CtrOn` send. On this product
the sub bus IS the centre bus (PW ruling R5), so the chain it feeds has
always been the Centre strip; it has been marked retired-not-deleted since
S1 for want of a cell to reach. The 24 Sep master block gives it the whole
`MainCtr` family, so item 1 is a **re-patch, not new fabric**, and that is
why it costs no address move outside the two strips the ruling rebuilds.

Every surviving node is a rename and keeps its SPI words to the word —
the shape S122 used when `C2_MON_OUT` became `C2_SPKR_OUT`:

| was | is | words | cells it now reaches |
|---|---|--:|---|
| `C2_SUB_FDR` | `C2_CTR_FDR` | 4 @1320 | `MainCtr Level/Mute/Dca/DcaOn` |
| `C2_SUB_EQ` | `C2_CTR_EQ` | 24 @1324 | `MainCtr Eq*`, `MainCtr PeqGain*` |
| `C2_SUB_COMP` | **reserved** | 16 @1348 | — |
| `C2_SUB_LIM` | `C2_CTR_LIM` | 4 @1364 | `MainCtr Limiter*` |
| `C2_SUB_DLY` | `C2_OUT3_DLY` | 2 @1368 | `Main Out3Delay` |
| `C2_SUB_OUT` | `C2_OUT3_OUT` | 1 @1370 | `Main Out3Mute`, lane NET_OUT_01 → DAC_14 |
| `C2_MTR_SUB` | `C2_MTR_OUT3` | 1 | `Main Out3Mtr` |

`C2_SUB_COMP` goes because the master block draws no compressor on the
Centre strip and D24's generation `46109e9fb812` dropped every `Main*Comp*`
cell to match. Its sixteen words are **held, not reclaimed**, so nothing
below them moves. Same for main outputs 3 and 4 (24 + 16 + 4 + 1 words
each, plus their `mo_page` pairs and their two meter word-pairs).

### 1.2 The crossover is the HPF half, and the Woof strip has the LPF

This is a **correction to S142 §3.2** and it is finding S144-2. That design
fed the Woof from the two main crossovers' LP legs; the two cell families
say where each filter is:

- `Main CrossoverFreq` — "Main L/R **HPF** crossover frequency: ONE
  parameter set driving the two DSP crossover instances (Main L and Main
  R); LF summed …"
- `MainSub CrossoverFreq` — "**Woof LPF** crossover frequency: applies when
  Main CrossoverLink = 0 (UNLINK); linked it follows Main CrossoverFreq"
- `MainSub Src` — "0 = Main L/R **sum** / 1-16 = Aux N (D24: aux 1-8)"

Two filters, one corner when linked: a Linkwitz-Riley pair with the
low-pass placed in the strip whose cells describe it. Taking the LP leg as
well low-passes the LF path twice at the same corner whenever `Src` is 0
and `Link` is 1 — LR4 then LR4, 12 dB down at the corner instead of 6, and
LP + HP no longer summing flat. So `C2_WOOF_MIX` sums `C2_MAIN_DLY` and
`C2_MAIN_DLY_R`, which is what "Main L/R sum" says, and the Woof's own LPF
is the only one in the LF path.

### 1.3 The graph, as built

```
C1_BUS_SUB → C2_RECV_SUB → C2_CTR_FDR → C2_CTR_EQ(4) → C2_CTR_GEQ(31)
                                      → C2_CTR_AFB(6) → C2_CTR_LIM ─┐
                                                                     ├→ C2_OUT3_SEL
C2_MAIN_DLY + C2_MAIN_DLY_R → C2_WOOF_MIX → C2_WOOF_SRC(13) →       │
    C2_WOOF_XOVER(LPF) → C2_WOOF_FDR → C2_WOOF_EQ(2) → C2_WOOF_LIM ─┘
                                                                     │
C2_OUT3_SEL → C2_OUT3_DLY → C2_OUT3_OUT (DAC_14, J55) → C2_MTR_OUT3
```

`MainCtr Geq[1-31]` is built **unconditionally**, not behind
`--geq-outputs`: it is a landed contract cell, and an option that can
switch a landed cell off is a cell with no reader half the time. The `sub`
GEQ class is gone from that option with the chain it named.

### 1.4 `SOURCE_SEL` — a select that is a coefficient, not a branch

One new node type, used four times (twice here, twice in item 2). Three of
PW's rulings need a switch in the audio path that a host writes and an
operator hears nothing of: `MainSub Src`, `Main Out3Mode`, `Mon PickOff`.

A select that jumps between two source words clicks — the two signals are
uncorrelated and the step between them lands on an arbitrary sample. So
the node is a small mix bus whose gains the BLOCK-RATE half owns: exactly
one source at 1.0 in the steady state, and a change crossfades the
outgoing source to 0 and the incoming to 1 over 12 ms (576 samples, the
same length the biquad banks fade over) at block rate. **There is no
branch in the sample loop at all**, nothing is allocated or freed at
switch time, and both directions cost the same. The whole gain vector is
laid in one branch-free walk — `from` gets 1 − alpha, `cur` gets alpha,
everything else exactly zero, and the Q4.28 conversion rides the same loop
— so in the steady state the sum IS the selected source bit for bit, since
(x·2²⁸ + 2²⁷) >> 28 = x.

A new target arriving during a fade is neither dropped nor mixed in: the
node finishes the fade it is running and re-reads the select word, which
it does every block, so a host that writes A, B, C inside one fade lands
on C with one more fade.

`Mon PickOff` needs the same tap on both legs of a stereo pair, so
SOURCE_SEL takes followers: the master lays the gain vector and the
follower MACs its own sources against that same vector later in the same
block. **Lockstep by construction with no shared transient word** — a
select's transient IS its coefficients, so it needs no kick either.

### 1.5 `Main CrossoverOn` and `Main CrossoverLink` cost no allocation

Both take words `C2_MAIN_XOVER` already owned: base+2 and base+3, which
were dispatched only as staging coefficients the contract does not name
and no host writes.

- **On = 0** designs the compiled identity — (1, 2, −1, 2, 1) in the wire's
  offset encoding, the same five words `xover_design_fx.asm` writes for an
  LR2 second stage — into all four stages, through the node's own
  dual-instance crossfade. So switching the crossover in or out is
  click-free for free. It is finding S144-8 that the default is 0, so a
  host that writes a corner must also write the switch.
- **Link = 1** makes `C2_WOOF_XOVER` design at the master's corner and
  slope instead of its own. That is a new `link_from=` mechanism and it is
  **not** `follows=`: the Woof crossover has its own two cells, its own
  address, its own filter state and its own banks, and only borrows the
  master's two design words. The master KICKS the dependent's dirty flag
  on every redesign, because a write to `Main CrossoverFreq` raises the
  master's flag and nothing else — without the kick a linked Woof would
  keep its old corner until someone wrote one of its own cells.

### 1.6 Two tables that were emitting cells no product defines

`_XOVER_STRIPS` aliased `MainL`, `MainR`, `MainCtr` and `MainSub`
`CrossoverFreq/Slope` onto the one crossover word. The 28 Sep generation
gives `Main Crossover{Freq,Slope,On,Link}` and `MainSub
Crossover{Freq,Slope}` and **no `MainCtr` crossover cell on any of the four
products**, so two of those four aliases were generated cells with no
matrix row. The table is now per node: `C2_MAIN_XOVER` carries `Main` plus
the `MainL`/`MainR` aliases that D12, D16 and D32 still declare, and
`C2_WOOF_XOVER` carries `MainSub`.

`_MAIN_OUT_STRIP` drops to `{1: MainL, 2: MainR}`.

---

## 2. Item 2 — the phones pair, the monitor's jacks and the pick-off

### 2.1 The monitor reaches a converter again

`C2_MON_DLY` has published a block nothing reads since S122, on a product
whose rear panel has a pair of jacks labelled Monitor. Those jacks carried
main outputs 3 and 4. Both facts are now gone: two one-slot `OUTPUT_TDM`
nodes (`C2_MON_OUT_L/R`) take DAC_15/16. No `mo_page`: the masters give the
monitor a Level and a Delay and no Mute, so there is no strip cell for
those nodes to carry and they emit none.

### 2.2 The phones are their own pair, off the monitor's source select

```
C2_MIX_MAIN_*   (0 pre-processing)   ┐
C2_MAIN_DLY*    (1 post-processing)  ├→ C2_MON_PICK (+_R)  `Mon PickOff`
C2_MAIN_FDR*    (2 post-fader)       ┘         │
                                               ├→ C2_MON (+_R) → C2_MON_DLY(+_R) → DAC_15/16
                                               └→ C2_PHN (+_R) → C2_PHN_DLY(+_R) → DAC_09/10
```

`Mon PickOff` powers up at 2 — post-fader, the tap `C2_MON` has always
read — so the shipping default is what it was.

The phones run the MONITOR kernel with two new declarations:

- **`source_from=C2_MON`** — this instance runs the monitor's own source
  select and has no source word of its own, which is PW ruling D7's "off
  the same Cue / Main L-R source select as the monitor output". One
  `Mon InputSel` word, both destinations; a second would be a second answer
  to one question. The word is still dispatched at the phones' base+0, with
  nothing behind it, so the address answers rather than answering with
  another node's select.
- **`mon_cells=Level1`** — which of the kernel's three words carry cells is
  declared rather than fixed by type, so the phones emit no `InputSel` or
  `Level[2]` cell that no product defines. `Mon PhonesLevel` is ONE cell for
  both legs (`follow_leg=l` on both), which is the difference from the
  monitor, whose two legs are two different cells.

`Mon CueOn` reaches no address and that is the ruling, not a gap: the host
folds it and the cue state into the one `Mon InputSel` word (D8, and the
cell's own note says so). The cue bus itself has been built since S65 and
the monitor reads it at `InputSel = 1`.

### 2.3 What is NOT built

Talkback injection — S144-4, and it is a wire question. The talkback mics
are chip-1 nodes with empty `outputs` columns that reach no bus at all
(the `Talk Dest` gap, diagnosed S25, declined S26), so there is nothing on
chip 2 to inject; reaching the chip-2 phones needs a mix-fabric slot, and
that map is single-sourced in `shared/dsp4-logic/`. `Talk Dest`'s own note
also makes the destination ORDER provisional until the skin audit (D13).

---

## 3. Item 4 — anti-feedback

### 3.1 Two new instances, one parameter set

`C2_MAIN_AFB` + `C2_MAIN_AFB_R` between the main GEQ and the bus
compressor; `C2_CTR_AFB` between the Centre GEQ and its limiter. That is
the aux chain's own order (`FDR → EQ → GEQ → AFB → LIM`) and the right one:
a notch placed after the limiter is a notch the limiter has already pumped
against.

The main pair is D5 applied to the anti-feedback the way S143 applied it
to the GEQ. Without it the two legs would notch at slightly different
times and the image would shift as each notch went in. The follower
`.extern`s the master's notch set, its design and its ring-out gain, and
owns its filter state, its crossfade and its limiter **envelope** — an
envelope is per channel or it is not an envelope.

### 3.2 The ring-out gain and the feedback limiter

`AntiFbGain` and `AntiFbLimOn` have had spare words in the ANTI_FB block
since S23 and no arithmetic. They are what makes ringing a room out safe:
walk the gain up until the room rings, the limiter stops the ring taking
the system with it, notch, repeat.

They go on the notch node's OUTPUT, not on a node of their own — a
per-protected-point gain node would be fourteen more chain entries,
fourteen more block buffers and fourteen more call/rts for a feature off in
every shipping image. It is one guarded post-pass over the block the
cascade has just filled, and **the shipping default costs one compare**:
0 dB is exactly 2²⁸ and the limiter is off, and unity AND off is the bypass
test. Same discipline as S23's switched-send bypass and S24's unity-level
bypass.

The limiter is the limiter, not a hard clip: `_envq_fx` for the envelope
and `_compgain_fx` off a brick-wall parameter block, the same two library
routines and the same `_fx_dyn_block_cvt` conversion `gen_limiter_fixed`
runs, one prefix along. A clip would generate the harmonics the notches are
trying to find. Its threshold is a NODE parameter (`fb_lim_db=-6.0`, stated
in `dsp.csv`) because the contract gives the family no cell for it.

EQ's and GEQ's emitted text is **byte-identical**: the four insertion
points in the shared cascade template are empty for every family but
ANTI_FB, and the drift gate says so.

### 3.3 The detector, and the half of it that did not exist

S142 proposed ONE shared 1/3-octave filterbank time-multiplexed onto the
armed bus rather than one per protected point — 3,566 c/blk instead of
39,226. **That filterbank has been built since S64**: `rta.asm`, 31
Butterworth bandpasses per channel, publishing each band's mean square,
with runtime-writable source POINTERS (`_rta_src_l/_rta_src_r`) and pointed
at the cue bus, which `Cue Src` can already assign to main, any aux or any
group. So "time-multiplexed onto the armed bus" is already how it works,
and the arming is two words the host already has.

What did not exist is the **ring metric** — the answer to "is this band
ringing, or is it a note?". S142's distinction is persistence: a band that
stays within a few dB of its own slowly-decaying peak for longer than
programme material does is a ring, because feedback holds indefinitely and
a held note decays. Built here, per band: a peak with a 2 s decay
(0.999833 per 0.3333 ms block) and a saturating count of consecutive
blocks within 3 dB of it (a power ratio of 0.501187), capped at 2,047
blocks = 682 ms. Published as `_rta_ring[62]` on the same PROPOSED SPI
footing as the magnitudes beside it (`Rta001Ring{L,R}NNN`; these names are
not in the contract).

It is a SECOND PASS over `_rta_out`, not an addition to the band loop —
that loop has all sixteen F registers live across its sample kernel and
r15 as the accumulator, so there is no register left in it.

Everything in it is inside `#if DSP4_RTA`, which is 0 in
`shipping.config`, so chip 1 is byte-identical in the shipping arm. The
`DSP4_RTA=1 DSP4_CUE=1` arm was built to prove it assembles and links.

### 3.4 The failure modes, restated because they are still the failure modes

Unchanged from `s142-pricing.md` §6.1, and now with the metric that
mitigates the first one built:

1. A sustained held note at a band centre reads as a ring. Mitigated by
   the persistence count and by the notch's own depth limit, not
   eliminated; the operator has manual mode.
2. 1/3-octave resolution places a notch within about ±6 % of the true
   frequency, so the Q must be broad enough to catch it. A two-band
   interpolation is the obvious later refinement.
3. Six notches is six modes; a room with more will chase its own tail. The
   gain walk must stop when the sixth is placed, and that stop is the
   host's.
4. The detector sees one bus at a time, so a system ringing on an aux while
   Main is armed is not found. The arming is the operator's.

---

## 4. Capacity

### 4.1 Memory — the linker's own report

Three clean two-chip builds, CCES 3.0.3, `shipping.config`, exit 0, each
into a scratch directory outside the tree.

| chip 2 pool | S143 | item 1 | item 2 | item 4 | limit |
|---|--:|--:|--:|--:|--:|
| code (VISA SW) | 61.6 % | 61.5 % | 62.6 % | **66.1 %** | 262,144 B |
| DM data + stack | 78.2 % | 78.5 % | 78.9 % | **79.9 %** | 375,264 B |
| delay lines | 86.4 % | 86.4 % | **91.0 %** | 91.0 % | 2,072,576 B |

**The delay pool is the binding constraint and it moved once: +96,000
bytes, the two new 250 ms mono phones lines**, leaving **186,464 bytes
free**. It is over the `dsp_memreport` warning line (90 %) and inside the
pool. Item 1 adds no delay line (the C/LF tail re-uses `C2_SUB_DLY`'s) and
item 4 adds none.

Chip 1, shipping arm: code 69.2 %, DM 82.5 %, delay 24.5 % —
**unchanged**, because the ring metric is inside `DSP4_RTA`. With
`DSP4_RTA=1 DSP4_CUE=1`: code 70.3 %, DM 84.1 %.

Chip-2 SPI words: 2,281 → **2,418. 137 added, 0 moved.**

### 4.2 Cycles — constructed, and the driven row is queued

There is still no per-class breakdown of the signed 84.47 % anywhere in
the tree (S142 §9), so this is measured marginal rates added to a measured
whole-graph baseline, exactly as S142's was. The SOURCE_SEL class has no
measured rate at all — it is new — so it is priced by **counting the
emitted instructions** at the repo's own measured ≈1 instruction/cycle, and
that method is stated where the number is used.

Chip 2 is 327,680 cycles a block at BLOCK 16 / 983.04 MHz.

**Item 1**

| node | c/blk | rate |
|---|--:|---|
| `C2_CTR_GEQ` — 31-band mono GEQ, new node | +3,566 | `FULLCFG_GEQ_STAGE_NEWNODE` |
| `C2_WOOF_XOVER` — CROSSOVER, 1 ch | +3,140 | `C2_XOVER` per channel |
| `C2_WOOF_SRC` — SOURCE_SEL, 13 sources | +2,469 | counted (§4.3) |
| `C2_OUT3_SEL` — SOURCE_SEL, 2 sources | +948 | counted |
| `C2_WOOF_EQ` — EQ_BIQUAD, 2 bands, new cascade | +912 | 729 + 2 × 91.5 |
| `C2_WOOF_LIM` — LIMITER | +257 | `C2_LIM` |
| `C2_WOOF_MIX`, `C2_WOOF_FDR` | +420 | 210 floor each |
| **removed**: `C2_SUB_COMP`, `OEQ_03/04`, `OCOMP_03/04`, `OLIM_03/04`, `OUT_03/04`, `MTR_MAIN_03/04` | **−4,315** | see below |
| **net** | **+7,397 = +2.26 %** | |

The removals are charged at floor rates and are therefore UNDERSTATED: no
measured chip-2 COMPRESSOR rate exists, so the three compressors that go
are charged at the LIMITER's 257 each, and a compressor is heavier than a
limiter. The true net is lower than +2.26 %.

**Item 2**

| node | c/blk |
|---|--:|
| `C2_MON_PICK` — SOURCE_SEL, 3 sources | +999 |
| `C2_MON_PICK_R` — its follower | +944 |
| `C2_PHN`, `C2_PHN_R` — MONITOR master + follower | +420 |
| `C2_PHN_DLY`, `C2_PHN_DLY_R` — DELAY | +218 |
| `C2_MON_OUT_L/R`, `C2_PHN_OUT_L/R` — OUTPUT_TDM | +840 |
| **net** | **+3,421 = +1.04 %** |

**Item 4**, at the shipping default

| node | c/blk |
|---|--:|
| `C2_MAIN_AFB`, `C2_MAIN_AFB_R`, `C2_CTR_AFB` — ANTI_FB, 6 notches, new nodes | +3,834 |
| the ring-out gain + feedback limiter, BYPASSED on 15 AFB nodes | +60 |
| the ring metric (chip 1, inside `DSP4_RTA` = 0) | 0 |
| **net** | **+3,894 = +1.19 %** |

Engaged, the post-pass costs about **+1,984 c/blk on the one node that is
armed** (`_afl_one_` is ≈124 instructions a sample once the limiter is on:
two rounds, an envelope and a gain computer). Ringing out one bus is a
soundcheck operation on one bus at a time, which is the whole reason the
detector is shared.

**Total, and where it lands**

| | chip 2 |
|---|--:|
| S86's measured driven baseline (signed config, Echo default) | 84.47 % |
| S143 (stereo main bus +2.69 %, group crosspoints +0.08 %) | 87.24 % |
| S144 item 1 | +2.26 % |
| S144 item 2 | +1.04 % |
| S144 item 4 | +1.19 % |
| **landing at** | **≈ 91.7 %** |

S142 predicted 91.6 % for **all four** items. This is three of the four —
item 3, the aux matrix, was handed back as S143-2 and is priced at
+2.16 % — so the comparable prediction is ≈89.4 % and the outturn is about
**2.3 points over it**. §4.3 is where those 2.3 points are.

The reverb regime is unchanged and still does not fit: six engines at Type
3 are +16.44 points measured (`FX_C2_D24_TYPE3_REVERB`) against the Echo
default's +1.53, so that regime is now ≈106.6 %. It did not fit before this
work either (S142 measured today's graph at 99.4 % there), and the lever is
still a signature and not work: `DSP4_C2_BQ_GRAPH` is at 0 in
`shipping.config`, is worth ≈17.4 points, and was NOT touched here.

### 4.3 Where the 2.3 points went, and that it is removable

Finding S144-7. `blk_wrap_body` stages every declared input into the scalar
`_buf_` word the per-sample body reads, and that staging is six
instructions per input per sample. On the 13-source Woof select it is
**1,248 instructions a block for staging alone**, against 992 for the
arithmetic it stages. The four SOURCE_SEL nodes cost 5,360 instructions a
block between them — **1.64 % of chip 2**, and more than half of it
staging.

S142 priced a select as "a per-sample body reading the selected `_buf_`",
and the measured class rates it used (210 c/blk for MIX_BUS and friends)
are floor charges taken on nodes with few inputs. Neither carries the term.

It is removable: a SOURCE_SEL does not need the generic wrapper. Its own
block kernel could walk the source BLOCKS directly — thirteen `dm(i, 1)`
reads against thirteen coefficients inside a hardware loop, no scalar round
trip — which is what `MIX_BUS` already does in its fast path and what
`_bq_fx_cascade_blk` does for the cascades. Taking the class out of
`_C2_WRAP_TYPES` is worth about **1.0 % of chip 2** on the four instances
built here. Out of this dispatch's scope; recorded with the number.

### 4.4 The follower pairing lesson, and it now bites one more pair

S143 corrected S142: a follower cannot be SIMD-paired today, because the
pair drivers gather a per-member coefficient symbol a follower does not
have (it `.extern`s its master's). That now applies to `C2_MAIN_AFB` +
`C2_MAIN_AFB_R` as well, so the new anti-feedback pair runs as two scalar
nodes in both `DSP4_C2_BQ_GRAPH` arms — exactly as the two main GEQs and
the two main crossovers do. It remains the most attractive pairing on the
chip (one coefficient set, two states, no per-block gather) and remains a
not-taught-yet rather than an impossibility; the exclusion says so where it
is made (`_c2_pair_excluded`).

The two cross-chain dynamics pairs are now formally retired.
`_C2_CROSS_PAIRS` is empty: S143 stopped them FORMING (both main members
are stereo-linked and the pair kernel has no second detector input) and
S144 removed the PARTNERS (`C2_SUB_COMP` is deleted; `C2_SUB_LIM` is
`C2_CTR_LIM` at the end of a chain that also feeds the Out3 select). The
mechanism and its reachability argument are kept, with what refilling the
table would take.

---

## 5. Two tools this session had to build to finish

**`gen_dsp.py --params-dir DIR`.** `dsp_params.asm` is generated from the
LANDED contract, and the landed contract lags the graph for as long as a
proposal is in flight at the hub gate — the normal state of this repo
between a graph change and a defs tag. S143 could still build the tree in
that window because it only ADDED nodes: the stale dispatch table named
nothing that had gone away, so it linked. **S144 removes nodes, and a stale
table then references thirty-odd `.var`s that no longer exist.** So "does
the graph assemble and link" stopped being answerable, and it is the
question a desk session most needs answered before handing work to the hub.
`--params-dir` writes the graph's own tables into a directory OUTSIDE the
tree, for a build out of a scratch copy of `src/`. It deliberately does not
touch `SHARC/src/chip*/dsp_params.asm`, which tracks the landed contract.

**`dsp_codegen.py` deletes the node ASM of a node that left the graph.**
The generator only ever WROTE files, so a `dsp.csv` that drops a node left
the old `<id>.asm` in the tree — still assembled by the build's wildcard,
still declaring that node's `.var`s and its `_<id>_process` entry, called by
nothing. S144 drops seventeen. The drift gate would catch it (a stale file
falls out of the generated set into the hand-written list, and that list is
checked) but catching it is a failed build, and this is the fix. Narrow on
purpose: only `chip*/nodes/*.asm`, only basenames that are not a node id of
that chip.

---

## 6. The one real bug, and what found it

`C2_PHN_R` externed `_mon_source_C2_PHN`, which does not exist: a MONITOR
follower whose master carries `source_from=` has to resolve the same source
word the master does, and the block wrapper resolved it one level short.
Fixed by resolving through the master's params.

**It is invisible in the shipping arm.** The only code that reads
`_mon_source_` is inside `#if DSP4_CUE`, and `DSP4_CUE` is 0 by default, so
the shipping build linked clean with the wrong symbol in the file. The
`DSP4_RTA=1 DSP4_CUE=1` build is what failed, and it was only run because
item 4 touched `rta.asm`. Worth saying out loud: **a guarded arm that
nothing builds is an arm that does not compile**, and this tree has several.

---

## 7. What the bench must prove

Queued, not run. Nothing was flashed, no image was loaded onto MW-D24-2, no
app was deployed, and the unit was not contacted this session.

Carried forward from S143, still owed:

1. The L/R capture on the MAIN XLRs J56/J57 with a hard-panned strip and
   the pan swapped, then the same with the pan centred.
2. The click check on a live `Main CrossoverFreq` change, captured across
   both XLRs through the 576-sample fade.
3. The driven capacity row on the part, on the signed configuration.
4. One group send opened per aux, to measure what leaving the S23 bypass
   costs at 11 sources.

New with S144:

5. **The C/LF XLR carries something at all.** A tone into a strip with its
   `Chan*CtrOn` up, meter on J55 (DAC_14). The desk says DAC_14; the desk
   has been wrong about this hardware before (`DAC_13` was "Main Out 1" for
   months and is not connected to anything), and until now J55 was fed from
   an aux bus D24 does not declare.
6. **`Main Out3Mode` switches it, click-free.** J55 captured across a live
   0 → 1 write, with the Centre bus and the Woof carrying different tones
   so the crossfade is visible. Then the same for `Mon PickOff` 2 → 0 on
   the monitor jacks.
7. **The monitor jacks carry the monitor and the phone jack carries the
   phones.** J53/J54 (DAC_15/16) and J10 (DAC_09/10), four captures, with
   `Mon Level[1-2]` and `Mon PhonesLevel` moved independently — the second
   monitor level had no reader at all before S143 and neither pair reached
   a converter before S144.
8. **`Main CrossoverOn` engages and disengages the split.** Sweep through
   the corner on J56 with the switch at 0 and at 1; at 0 the HP leg must be
   flat to the bottom of the sweep.
9. **The Woof LPF is the only low-pass in the LF path.** Sweep on J55 with
   `Out3Mode = 1`, `Src = 0`, `Link = 1`: 6 dB down at the corner, not 12,
   and LP + HP summing flat against J56/J57.
10. **The anti-feedback notches and the feedback limiter.** `Main
    AntiFbNotchFreq/Gain/Q` written and swept on J56/J57, both legs
    identical through the swap; then `AntiFbGain` walked up with
    `AntiFbLimOn` at 0 and at 1, and the limiter's −6 dBFS ceiling read on
    the XLR.
11. **The ring metric, on a real ring.** A `DSP4_RTA=1 DSP4_CUE=1` image,
    the cue assigned to Main, a deliberate acoustic ring provoked through
    the monitor speaker, and `_rta_ring` read back — the count must
    saturate on the ringing band and stay near zero on the others while
    programme material plays.
12. **The delay pool at 91.0 %.** A boot and a soak on the part with every
    delay line allocated, which is the first image that asks for 1,886,112
    of the 2,072,576 bytes.

---

## 8. State left behind

Three commits on `main`, one per item, plus this report and the findings.

**The proposals are in flight and the generated contract artefacts stay at
the landed map, deliberately** — the same state S143 left, for the same
reason. `gen_dsp.py --propose` regenerated `proposals/defs/products/*/` for
all four products; `gen_dsp.py` without `--propose` refuses, because the
graph is ahead of `defs/products/*/dsp.csv`, so `MW/*/MX/_matrix.csv`,
`dsp_params.asm`, `ghost_cells.h` and `dsp_address_map.md` are unchanged
from S140's backfill. **Owed to the hub: land the proposals, advance the
defs pin, then run `./regenerate-dsp-contract.sh`.**

What the proposals move, and it is the smallest footprint the ruling
allows:

| product | changed address | new | gone |
|---|--:|--:|--:|
| d24 | 40 (`MainCtr*`, `MainSub*`) | 104 | 0 |
| d32 | 24 (`MainSub*`) | 32 | 18 |
| d16 | 24 (`MainSub*`) | 20 | 18 |
| d12 | 24 (`MainSub*`) | 16 | 18 |

Only the two strips the ruling rebuilds change address. The 18 that go on
the other three products are `MainSub Comp*` and `MainSub Mtr`, declared
from the superseded post-crossover model — D24's own generation dropped
them, and those three products' masters have not caught up. Recorded for
the hub as stale upstream rather than built back.

D24 mapped cells: **3,632 → 3,800** of 5,767 (1,967 unmapped, each with a
reason).

`defs.lock` is untouched at `defs-v2026.09.28.2`. `DSP4_C2_BQ_GRAPH` is
untouched at 0. No contract bump is owed by this repo; the bump is the
hub's, on the proposals.
