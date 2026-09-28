provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S142 — what the four block-audit rulings cost, before any of them is built

Session 142, 2026-09-28, desk only. Hub dispatch `tasks.md` 2026-09-28 11:52Z.
Nothing here is built yet; this is the gate the dispatch puts in front of the
build — *"price all four FIRST, before building any… If the four together do
not fit, STOP at the pricing and report the options — do not trade a ruled
feature away yourself."*

---

## 0. The answer, on one line

**The four items fit chip 2 — at 91.6 % of budget against today's 84.5 %, with
the shipping FX default — and they do NOT fit with six reverbs live. Neither
does today's graph.** The reverb case is already at 99.4 % before a line of
this work is written, so the thing that decides whether these four ship is not
these four: it is `DSP4_C2_BQ_GRAPH`, worth about 17 points of chip 2, already
written, already built, already witnessed, and still at 0 in
`shipping.config`. Nothing here asks for a feature to be given up.

| arm | chip 1 | chip 2 | fits |
|---|--:|--:|---|
| today, signed config, driven, six Echoes (S86 measured) | 57.55 % | **84.47 %** | yes, 0 missed blocks |
| today, six Reverbs (S21 measured ladder applied) | 57.6 % | **99.4 %** | on the line |
| **+ the four items, six Echoes** | **57.7 %** | **91.6 %** | **yes** |
| **+ the four items, six Reverbs** | 57.7 % | **106.6 %** | **NO** |
| + the four items, six Echoes, `DSP4_C2_BQ_GRAPH=1` | 57.7 % | **74.6 %** | yes |
| + the four items, six Reverbs, `DSP4_C2_BQ_GRAPH=1` | 57.7 % | **89.5 %** | yes |

---

## 1. The budget, and where the baseline comes from

Budget is **327,680 cycles/block** — block 16, 983.04 MHz, 3,000 blocks/s.

The baseline is the SIGNED pairing configuration, `DIAG_BUILD_CFG2
0xE2018E6F` (S82, `MW/D24/DSP/s82/signed.md`), re-taken by S86 on the fixed
bitstream (`MW/D24/DSP/s86/rx-path.md:360-368`):

| row | chip 1 | chip 2 | missed blocks |
|---|--:|--:|---|
| A — silent, default | 43.13 % | 77.50 % | 0 |
| B — silent, loaded | 57.61 % | 84.41 % | 0 |
| **C — DRIVEN, six FX live** | **57.55 %** | **84.47 %** | **0** |

So the headroom this work is spending is **15.53 % of chip 2 = 50,890
cycles/block**, and 42.45 % of chip 1 = 139,100 cycles/block. Chip 2 is the
only chip that is in question; every one of the four items is chip-2 work
except the aux-send pan coefficients, which are chip 1's and are free at block
rate.

**The boot spread is stated rather than averaged away.** Chip 2's row C has
been taken three times — 84.34, 84.35, 84.47 — a total span of 0.13 points,
with a within-session two-boot spread of 0.53. Treat every figure below as
±0.5 points, which is why 91.6 % is reported as a number that fits and not as
a comfortable one.

## 2. The rates, and what they were measured on

Everything below is priced from **measured** rows, not from instruction
counts. The rates, with citations:

| rate | value | source |
|---|--:|---|
| new 31-band GEQ instance, mono (node + 31 stages) | **3,566 c/blk** | `dsp4-function-costs.csv:787-789` (`FULLCFG_GEQ_STAGE_NEWNODE`: 17,828 / 5 new nodes) |
| new 31-band GEQ instance, 2 ch, one node | **6,044 c/blk** | `dsp4-function-costs.csv` `FULLCFG_C2_WITH_MONITOR` (measured directly, +1.84 %) |
| biquad stage added to an EXISTING cascade | **91.5 c/blk** | `FULLCFG_GEQ_BAND_EXISTING` (4,940 / 54 stages) |
| new biquad-cascade NODE overhead | **729 c/blk** | `FULLCFG_GEQ_STAGE_NEWNODE` note (3,645 / 5 nodes) |
| ANTI_FB, 6 notches, existing instance | 331 c/blk | `C2_AFB` 3,967 / 12 instances, block 16 |
| LIMITER, mono instance | **257 c/blk** | `C2_LIM` 4,621 / 18 instances, block 16 |
| DELAY, one channel | **109 c/blk** | `C2_DLY` 1,639 / 15 instances, block 16 |
| CROSSOVER, per channel | **3,140 c/blk** | `C2_XOVER` 6,279 for the one `ch_count=2` instance |
| EQ_BIQUAD, FADER_PAN, MIX_BUS, METER, OUTPUT_TDM | **210 c/blk** each | `C2_OUT` 13.1 c/sample × 16; `C2_FDR`/`C2_EQ` read BELOW INSTRUMENT RESOLUTION, so 210 is used as a floor charge rather than their negative readings |
| **one crosspoint MAC, bus-major fabric** | **5.29 c/MAC → 84.6 c/blk** | `FRONTIER_RTG_RESIDUAL` (5,417 c/blk for 1,024 MACs), and `DSP4_RTG_FABRIC=1` is in `shipping.config` |
| one crosspoint MAC, per-strip accumulate | 15.78 c/MAC → 252 c/blk | `FRONTIER_RTG_ACCUMULATE` (16,155 c/blk for 1,024 MACs) — the rate this work must NOT pay |
| six FX engines, Echo (the shipping `.var` default) | +1.53 pts over bypass | `FX_C2_D24_TYPE0_ECHO` |
| six FX engines, Reverb (worst Type the product has) | **+16.44 pts over bypass** | `FX_C2_D24_TYPE3_REVERB` |

**Two honesty notes on the rates.**

1. The per-class chip-2 rows (`C2_GEQ`, `C2_AFB`, `C2_LIM`, `C2_DLY`,
   `C2_XOVER`, `C2_EQ`, `C2_FDR`, `C2_OUT`) were measured 2026-09-01/02 on a
   D32-shaped, 28-band, pre-signing graph. They are the closest measured cost
   model that exists; they are not the signed configuration. Where a session-26
   full-market-config figure exists for the same thing (the GEQ rates above),
   that is used instead, because those arms are a *paired* measurement on one
   instrument in one session against a shipping baseline.
2. **There is no per-class breakdown of the signed 84.47 % anywhere in the
   tree.** Every driven row taken on the signed configuration is a single
   whole-graph number. So the additions below are priced against measured
   *marginal* rates and added to a measured whole-graph baseline; they are not
   a re-derivation of the baseline. The check on the arithmetic is the on-part
   re-take listed in §8, not this document.

## 3. Item 1 — Centre/LF (D6, + D5)

**What the block requires.** The Ctr Channel Bus (every channel's Ctr assign)
feeds a Centre strip; a Woof strip is fed by a source select from the Main L/R
sum or one aux; a Centre/Sub-Woof source switch picks which one reaches the
single C/LF XLR through **one** mute, meter, delay and DAC. D5: the crossover
is TWO instances (Main L, Main R) on ONE parameter set, LF summed to the mono
Sub.

**What the graph has today, and why it is wrong.** `MainCtr` and `MainSub` are
the *third and fourth legs of the main crossover* (`C2_MAIN_OEQ_03/04` →
`OCOMP_03/04` → `OLIM_03/04` → `OUT_03/04`), landing on `DAC_15`/`DAC_16`,
which are the rear **Monitor** jacks (S121-6). The Centre/LF XLR (`DAC_14`) is
fed from aux bus 12, which a D24 does not declare (S121-5), so no cell reaches
it. Meanwhile the real centre bus already exists and is called something else:
`C1_BUS_SUB` carries every channel's `Chan*CtrOn` send — *"on this product the
sub bus IS the centre bus"* (PW ruling R5, quoted verbatim in
`dsp_codegen.py:14953`) — and the `C2_SUB_*` chain it feeds has been marked
retired-not-deleted since S1.

So this item is a re-patch of the output stage, not new bus fabric: the centre
bus is already there and already paid for.

| node | change | c/blk |
|---|---|--:|
| `C2_CTR_GEQ` — GEQ 31, mono (`MainCtr Geq[1-31]`) | NEW | +3,566 |
| `C2_WOOF_SRC` — source select, 1-of-9 (`MainSub Src`) | NEW | +250 |
| `C2_WOOF_XOVER` — LPF leg when `Main CrossoverLink = 0` (UNLINK) | NEW | +3,140 |
| `C2_WOOF_FDR` — master fader (`MainSub Level`, `Main Out3Link`) | NEW | +210 |
| `C2_WOOF_EQ` — 2-band EQ (`MainSub Eq*`, 2 bands declared) | NEW | +912 |
| `C2_WOOF_LIM` — limiter (`MainSub Limiter*`) | NEW | +257 |
| `C2_XOVER_LFSUM` — LF L+R → mono | NEW | +210 |
| `C2_OUT3_SEL` — 1-of-2 (`Main Out3Mode`) | NEW | +250 |
| `C2_OUT3_OUT` — OUTPUT_TDM → `DAC_14` (`Main Out3Mute`) | NEW | +210 |
| `C2_MTR_OUT3` — meter (`Main Out3Mtr`) | NEW | +210 |
| `C2_SUB_DLY` → `C2_OUT3_DLY` (`Main Out3Delay`) | RENAME | 0 |
| `C2_SUB_FDR/EQ/LIM` → the Centre strip | RE-USE | 0 |
| `C2_SUB_COMP` — no compressor on the block's Centre strip | REMOVE | −878 |
| `C2_MAIN_OEQ_03/04` | REMOVE | −224 |
| `C2_MAIN_OCOMP_03/04` — every `Main* Comp*` cell was dropped by the audit | REMOVE | −1,756 |
| `C2_MAIN_OLIM_03/04` | REMOVE | −514 |
| `C2_MAIN_OUT_03/04`, `C2_MTR_MAIN_03/04` | REMOVE | −840 |
| **net** | | **+5,003 = +1.53 %** |

The crossover parameter set is the one that already exists
(`MainSub001CrossoverFreq/Slope001` already resolve to `C2_MAIN_XOVER`); D5
adds `Main CrossoverOn/Link` onto the same node. `C2_WOOF_XOVER` is the
**UNLINK** case only — with `Main CrossoverLink = 1` the Woof takes the
crossover's own LP legs and costs nothing. It is priced at its worst case.

## 4. Item 2 — the phones pair (D7) and the monitor pick-off (D8)

The monitor chain today dead-ends: `C2_MON → C2_MON_DLY → nothing`. It reaches
**no converter output on a D24 at all** — that is S122-5, raised for PW and
still open. This item closes it as a by-product, because item 1 frees
`DAC_15/16` (the rear Monitor jacks) and item 1's re-patch frees `DAC_09/10`
(Phones) from aux 9/10, which a D24 does not declare either.

| node | change | c/blk |
|---|---|--:|
| `C2_MON_PICK` — 2 ch, 1-of-N tap select (`Mon PickOff`, L/R/C × pre/post-processing/post-fader) | NEW | +250 |
| `C2_PHN` — phones level, 2 ch (`Mon PhonesLevel`), MONITOR kernel | NEW | +880 |
| `C2_PHN_DLY` — 2 ch (`Mon PhonesDelay`) | NEW | +218 |
| `C2_PHN_OUT` — OUTPUT_TDM 2 ch → `DAC_09/10` | NEW | +210 |
| `C2_MON_OUT` — OUTPUT_TDM 2 ch → `DAC_15/16` (closes S122-5) | NEW | +210 |
| talkback S1 injection into the phones leg | NEW | +169 |
| **total** | | **+1,937 = +0.59 %** |

`Mon CueOn` costs nothing: it is already classed `control-plane` — the host
folds it and the cue state into the one word `Mon InputSel`, by PW ruling D8.
The three pick-off taps cost nothing to publish: under `DSP4_BLOCK_KERNELS`
every chip-2 node already publishes its block, so the tap is a pointer
select resolved at control rate.

## 5. Item 3 — the aux matrix and the pairing (D3 + the 09:07 ruling)

**Every matrix output is an aux output.** All `Matrix*` and `Chan*Matrix*`
cells are **gone** from D24's generation `46109e9fb812` — verified: zero rows
in `MW/D24/MX/_matrix.csv`, zero in `defs/products/d24/dsp.csv`, zero in
`dsp-unmapped.csv`. So `C1_BUS_MTX_01..04`, `C2_RECV_MTX_*`, `C2_MTX_FDR_*`
and `C2_MTX_OUT_*` reach no D24 cell, and D24's `CFG_MTX_MASK` drops from
`0x3` to `0`, which skips all four matrix chains at block level and gives
about 840 c/blk of chip 2 back.

### 5.1 How a loop is made impossible

Not by a runtime check, and not by a convention. **The evaluation order is
aux 1 … aux 8, and a crosspoint (source aux *i* → destination aux *j*) exists
in the graph only for *i* < *j*.** A strict total order has no cycles, so
there is no loop to detect: the lower triangle and the diagonal are not
crosspoints the generator emits, so no host write can create one. The cells
are all declared (the grid is square, and the skins draw a square grid); the
ones below the diagonal resolve to a coefficient the generator ties to zero,
which is exactly what the cell's own note already says — *"a self-feed or a
feed that would close a loop is inert"*.

This is the answer to the dispatch's "state the order and how a loop is made
impossible, not just unlikely". The alternative — letting every crosspoint
exist and reading a one-block-old snapshot of the aux outputs — is rejected
here and named so it is not re-invented: a delayed loop with round-trip gain
at or above unity still diverges, it just takes 333 µs a lap to do it.

### 5.2 The crosspoint count

| destination | sources | crosspoints |
|---|---|--:|
| aux 1–8 | aux 1–8, upper triangle only | 28 |
| aux 1–8 | Grp 1–4 (`Grp AuxSend/AuxOn/AuxPick`) | 32 |
| aux 1–8 | Main L, Main R, Centre (`MainL/MainR/MainCtr AuxSend/AuxOn`) | 24 |
| | **total** | **84** |

| item | c/blk |
|---|--:|
| 84 crosspoints × 16 samples × 5.29 c/MAC (bus-major fabric) | +7,110 |
| per-destination control-rate prep, 8 × ~100 | +800 |
| `CFG_MTX_MASK` 0x3 → 0 on D24 | −840 |
| **total** | **+7,070 = +2.16 %** |

Built as a **per-strip accumulate** instead of a bus-major fabric it would be
84 × 252 = 21,168 c/blk = 6.46 %, three times the price for the same
arithmetic. `DSP4_RTG_FABRIC=1` is already in `shipping.config` and chip 1
already runs this pattern; chip 2 gets the same one.

### 5.3 The stereo/mono switch costs no cycles, and that is the design

`Aux Link` is carried on the odd aux of each pair, 0 = dual mono, 1 = stereo,
switchable per pair in realtime. **Neither mode changes the number of MACs.**
A channel that feeds a pair feeds both members in either mode; what changes is
the pair of coefficients — `send` and `send` in dual mono, `send·gL` and
`send·gR` in stereo, with `gL/gR` read out of the one pan table
(`tools/dsp/pan_table.py`, PW ruling R5) at the index `Chan AuxPan` gives.

So:

- **both modes are always available** — nothing is allocated or freed at
  switch time, because the fabric's shape does not depend on `Aux Link`;
- **the switch is click-free** because the only thing that moves is a
  coefficient, and send coefficients already ride the `GainFast` ramp;
- **the aux-matrix feeds and the aux anti-feedback follow the pairing** for
  free, for the same reason: they read the same per-aux coefficient column.

The cost is control-rate only, on chip 1, and only while a switch is ramping:
24 strips × 2 coefficients per pair, bounded at roughly 1,000 c/blk for the
~30 ms the ramp lasts = **+0.3 % of chip 1 transiently, 0 steady**.

## 6. Item 4 — anti-feedback on Main and Centre (D9)

The block draws, on Main, Centre and every aux: a 6-band automatic notch
filter, a feedback GAIN ("auto increases master volume to create feedback",
auto/manual), and a feedback LIMITER. `ANTI_FB` with `notch_count=6` already
exists on all twelve aux buses; what is missing is the two new instances and
the gain/limiter words.

### 6.1 The algorithm, proposed

**The DSP owns the filterbank, the ring metric and the notches. The host owns
the decision.** One **shared** 1/3-octave detector instance, time-multiplexed
across the armed bus, rather than one per protected point:

- the detector is the filterbank `tools/dsp/rta_design.py` already designs and
  `rta.asm` already implements (31 Butterworth bandpasses, `DSP4_RTA=0` in
  `shipping.config` today — built, not enabled);
- it is pointed at ONE bus at a time. Ring-out is a soundcheck operation, and
  in auto mode a slow tracker; nothing needs eleven simultaneous analysers;
- per band it publishes a magnitude and a persistence metric (a band whose
  level stays within a few dB of its own peak for longer than music does is a
  ring, not a note). The host's existing Antifeedback skin reads that vector,
  picks the band, and writes `AntiFbNotchFreq/Gain/Q`;
- `AntiFbGain` walks the master up while `AntiFbCtrlOn = 1`; the feedback
  **limiter** is what makes provoking feedback safe, and it is the existing
  limiter primitive with its own threshold, placed inside the AFB node.

**Cycle cost: 3,566 c/blk for one detector instead of 39,226 for eleven.**

**Failure modes, stated.** (a) A sustained held note at a band centre reads as
a ring — mitigated by the persistence metric and by the notch's own depth
limit, not eliminated; the operator has manual mode. (b) 1/3-octave resolution
places a notch within about ±6 % of the true feedback frequency, so the notch
Q must be broad enough to catch it, which costs more programme material than a
fine notch would; a second-stage interpolation across the two neighbouring
bands narrows this and is the obvious later refinement. (c) Six notches is six
modes; a room with more will chase its own tail — the gain walk must stop when
the sixth notch is placed, and that stop is the host's. (d) The detector sees
one bus at a time, so a system ringing on an aux while Main is armed is not
found; the arming is the operator's, via the skin.

**🔴 Recorded for PW, not asked (no dialogs):** the detector's *decision* is
placed on the host. If PW wants the ring-out to run with no host in the loop —
the desk finding and notching on its own with the screen off — the decision
logic moves to the DSP and this item costs more. The cell set does not change
either way, so the build below is correct under both rulings; only where the
peak-picking runs would move.

### 6.2 The bill

| node | c/blk |
|---|--:|
| `C2_MAIN_AFB` — ANTI_FB, 2 ch, 6 notches (`Main AntiFb*`) | +1,827 |
| `C2_CTR_AFB` — ANTI_FB, 1 ch, 6 notches (`MainCtr AntiFb*`) | +1,278 |
| feedback limiters: Main 2 ch + Centre 1 + aux 8 = 11 × 257 | +2,827 |
| `C2_AFB_DET` — one shared 31-band 1/3-octave detector | +3,566 |
| `Aux/Main/MainCtr AntiFbGain` — a coefficient on an existing path | 0 |
| **total** | **+9,498 = +2.90 %** |

## 7. The capacity table

| | chip 1 c/blk | chip 1 % | chip 2 c/blk | chip 2 % |
|---|--:|--:|--:|--:|
| **baseline (S86 driven, signed, six Echoes)** | 188,580 | **57.55** | 276,750 | **84.47** |
| item 1 — Centre/LF | 0 | 0.00 | +5,003 | +1.53 |
| item 2 — phones pair + pick-off | 0 | 0.00 | +1,937 | +0.59 |
| item 3 — aux matrix + pairing | +1,000 (transient) | +0.31 | +7,070 | +2.16 |
| item 4 — anti-feedback | 0 | 0.00 | +9,498 | +2.90 |
| **total added** | +1,000 | +0.31 | **+23,508** | **+7.17** |
| **after** | 189,580 | **57.86** | **300,258** | **91.64** |
| margin | | 42.14 % | 27,422 | **8.36 %** |

Memory, against the freshly built baseline of this session
(`dsp_memreport.py`, both chips, `shipping.config`, this tree at HEAD):

| chip 2 pool | now | after (estimate) | limit |
|---|--:|--:|--:|
| code (VISA SW) | 153,242 / 262,144 = 58.5 % | ~178,000 = 68 % | 90 % warn |
| DM data + stack | 289,260 / 375,264 = 77.1 % | ~319,000 = 85 % | 90 % warn |
| **delay lines** | 1,694,112 / 2,072,576 = **81.7 %** | **1,790,112 = 86.4 %** | 90 % warn |

The delay-line pool is the binding memory constraint, and the only new claim
on it is the phones pair: 2 channels × 250 ms × 48 kHz × 4 bytes = 96,000
bytes. `Main Out3Delay` costs nothing new because it re-uses `C2_SUB_DLY`'s
line. **After this work there is room for about five more 250 ms mono delay
channels on chip 2 and no more** — the next feature that wants a delay line is
the one that runs out, and it should be priced against this line, not against
the cycle budget.

## 8. What the bench must prove, per item

Nothing in this session is flashed. Queued, with the pass criterion:

1. **All four, together** — `ARM=s142 PRODUCT=d24 ./capacity.sh --driven` on
   the signed configuration, both boots, `build_cfg2` read off the part during
   the measurement. Pass: chip 2 within ±1.0 point of **91.6 %**, **zero
   missed blocks on every chip-row of every boot**. This is the one
   measurement that scores this whole document; if it lands outside that band
   the model above is wrong and the arithmetic, not the graph, is what to fix
   first.
2. **The FX rung** — the same row with all six engines at Type 3. Expect
   ~106 %, i.e. a FAIL, and take it anyway: it is the measurement that turns
   §0's reverb row from an applied ladder into a reading.
3. **Item 1** — the Centre/LF XLR (`DAC_14`, J55) carries the Centre strip
   with `Main Out3Mode = 0` and the Woof with `= 1`, one delay/mute/meter
   either way; `DAC_15/16` carry the monitor bus and no longer the crossover
   legs (this is the S121-6 defect, re-tested); the crossover splits at the
   corner `Main CrossoverFreq` names, LF summed to the Woof, and `UNLINK`
   moves the Woof LPF independently.
4. **Item 2** — the phones jack (`DAC_09/10`, J10) carries the monitor source
   at `Mon PhonesLevel`, independent of `Mon Level`; `Mon PhonesDelay` and
   `Mon Delay` move independently; `Mon PickOff` moves the tap between
   pre-processing, post-processing and post-fader, provable by muting the main
   fader and hearing the pre-fader tap survive; talkback reaches the phones.
   Closes S121-5 and S122-5.
5. **Item 3** — each aux output carries each declared source at the level
   `AuxSend` names, and *no* lower-triangle crosspoint can be made to pass
   signal by any host write (the negative control, and it is the one that
   matters); a pair switched between dual mono and stereo **while a tone is
   running** shows no discontinuity above the noise floor on a coherent
   capture — the ramp test, run on the part because the desk has no
   click-free prover (§9).
6. **Item 4** — a notch written at a measured feedback frequency removes it;
   `AntiFbGain` walks the master and the feedback limiter holds the ceiling;
   the detector's band vector agrees with `rta_design.py` on a known tone.

## 9. Two gaps this pricing does not close, named rather than routed around

- **There is no desk-side click-free prover in this tree.**
  `dsp_validate.py` checks only that a `ramp_profile` name is recognised;
  `dsp_simulate.py` parses the field and never applies it; nothing anywhere
  models a ramped parameter step or its audio consequence. The click-free
  requirement on the pairing switch is therefore proved by *construction*
  desk-side (the switch moves a coefficient that already rides a ramp, and
  changes nothing else) and by *capture* on the bench. It is worth building
  the prover; it is not in this dispatch.
- **There is no per-class breakdown of the signed 84.47 %.** Every marginal
  rate used here comes from an earlier campaign, most of them D32-shaped and
  pre-signing. The rates are the best measured ones in the tree and each is
  cited; the arithmetic that stacks them on a whole-graph baseline is checked
  only by §8 item 1.

## 10. ADDENDUM — S142-1: there is no Main R on chip 2, and three of the four items need one

Written after §1–§10, during the item-1 build. It changes the totals; §7's
table is superseded by the one at the end of this section.

**`_blk_C2_MIX_MAIN_R` is computed every block and read by nothing.** The full
evidence is in `findings.md` under S142-1; the mechanism is one line —
`dsp_codegen.py:19408` sets `inputs_str = inputs[0]`, `ch_count` generates
nothing, and every chip-2 node past `C2_MAIN_FDR` therefore runs on the left
bus alone. Both MAIN XLRs, both DAC MAIN slots, the codec aux out and the
monitor all carry left.

It is in the way of three of the four ruled items:

- **D5** rules the crossover as *"TWO DSP instances (Main L, Main R) sharing
  ONE parameter set"*. There is one instance.
- **D6** feeds the Woof from the *"Main L/R sum"*. There is no R to sum.
- **D7** gives the phones a pair off the same source select as the monitor, and
  `Mon Level` already declares L and R cells that both drive one block.
- **D3** lists Main L and Main R as separate aux-matrix sources
  (`MainL AuxSend`, `MainR AuxSend`, eight each). One of the two would be a
  copy of the other.

Only item 4's Centre anti-feedback is untouched by it, because the centre bus
genuinely is mono.

### What closing it costs

The mechanism D5 asks for — two instances, one parameter set — is the general
answer and is needed anyway. Each R instance keeps its **own filter and
envelope state** and reads the **master's coefficient words** by `.extern`,
selected by a `follows=<master node id>` param. No new SPI word, no new cell,
no address moved. The bus dynamics link rather than duplicate: one detector
over max(|L|,|R|), one gain applied to both, which is what a stereo bus
limiter has to do regardless or the image walks under compression.

| node | change | c/blk |
|---|---|--:|
| `C2_MAIN_FDR_R` — FADER_PAN, follows `C2_MAIN_FDR` | NEW | +210 |
| `C2_MAIN_GEQ_R` — GEQ 31, follows | NEW | +3,566 |
| `C2_MAIN_COMP_R` — COMPRESSOR, detector linked | NEW | +878 |
| `C2_MAIN_LIM_R` — LIMITER, detector linked | NEW | +257 |
| `C2_MAIN_DLY_R` — DELAY (+48,000 B of L2) | NEW | +109 |
| `C2_MAIN_XOVER_R` — CROSSOVER, follows (this IS D5's second instance) | NEW | +3,140 |
| second TX slot walk on `C2_MAIN_ST_OUT` and `C2_CODEC_AUX_OUT` | CHANGE | +210 |
| `C2_MON` reading a second block | CHANGE | +440 |
| **total** | | **+8,810 = +2.69 %** |

With `DSP4_C2_BQ_GRAPH=1` the two main GEQs and the two crossovers become
exactly the adjacent pair that lever pairs, so most of the 6,706 cycles those
four nodes cost comes back — the lever is worth more after this change than
before it.

### The capacity table, superseding §7

| | chip 2 c/blk | chip 2 % |
|---|--:|--:|
| baseline (S86 driven, signed, six Echoes) | 276,750 | **84.47** |
| **S142-1 — stereo main path (prerequisite)** | **+8,810** | **+2.69** |
| item 1 — Centre/LF | +5,003 | +1.53 |
| item 2 — phones pair + pick-off | +1,937 | +0.59 |
| item 3 — aux matrix + pairing | +7,070 | +2.16 |
| item 4 — anti-feedback | +9,498 | +2.90 |
| **after** | **309,068** | **94.32** |
| margin | 18,612 | **5.68 %** |

Chip 1 is unmoved: the R bus already exists there and already costs what it
costs.

**5.68 % of margin, on a row whose boot-to-boot spread is 0.53 points, is not
a margin — it is a hope.** The four items still fit on the shipping FX default
and still do not fit with six reverbs (109.2 %). What this addendum changes is
the strength of §11's recommendation, not its direction: with
`DSP4_C2_BQ_GRAPH=1` the whole set lands at about 77 % with the Echo default
and about 92 % in the reverb case, and that is the configuration this should
ship on.

### Memory, superseding §7

One more 250 ms mono delay line for `C2_MAIN_DLY_R` (+48,000 bytes), so chip 2's
delay pool goes to 1,838,112 / 2,072,576 = **88.7 %** — inside the 90 % warn
line and with about four mono 250 ms channels left. That pool, not the cycle
budget, is now the first thing the next feature runs out of.

### 🔴 What this means for the build order

Every one of the four items depends on this, so it is built first, as its own
commit, ahead of item 1. It is not scope this session invented: it is the
implementation of D5's own words, and without it there is nothing for D6's
"Main L/R sum" to sum.

## 11. The recommendation

Build all four. They fit.

Then put `DSP4_C2_BQ_GRAPH` in front of PW — **as a signature, not as work**.
It is worth about 17 points of chip 2 (`dsp4-capacity-decision-20260913.md`:
the `s16sd` arm is `s20` minus this one switch and read 76.42 % against
58.99 %), it has been written and built since 2026-09-02, the defect that once
held it at 0 was root-caused and fixed the next day (S12-5 → S13-1, CLOSED),
and it has been witnessed since at 1–4 ulp worst coefficient, ≤0.00014 dB
worst modelled response, and **0 ulp over 36,864 words** on `bqeverify`. With
it, the four items land at 74.6 %, and the reverb case — which does not fit
today, before any of this work — lands at 89.5 %.

Without it the four items still ship, on the shipping FX default, at 91.6 %.
What does not ship either way, and did not before this session, is six
reverbs.
