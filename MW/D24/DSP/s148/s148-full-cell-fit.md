provenance: AI-drafted 2026-09-29 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S148 — will two ADSP-21564s carry every D24 cell?

Session 148, 2026-09-29, desk only. Hub dispatch `tasks.md` 2026-09-29 09:38Z.
Nothing flashed, no DSP image loaded, no app deployed, no unit contacted —
scratch builds and reads of this tree only.

PW's question, verbatim: *"i need to know if the 2 x adsp21564 chips will
handle all cell requirements"*.

---

## 0. The verdict

**FITS WITH CONDITIONS — on rev C, with no HyperRAM, and with the signed
`DSP4_C2_BQ_GRAPH=1` arm.** The 890 cells the graph does not yet build cost
**chip 1 +1.36 %** and **chip 2 +2.99 %** at the shipping default, and every
one of them fits in today's memory. What decides the answer is not the cells —
it is what happens when the desk *uses* them at the same time as six reverbs.

| regime | chip 1 | chip 2 (arm B, ships) | fits |
|---|--:|--:|---|
| R1 — Echo default, nothing switched on | 58.9 % | **77.7 %** | yes |
| R2 — six Type-3 reverbs | 58.9 % | **92.6 %** | yes |
| R3 — Echo default, desk IN USE (every legal crosspoint live), **as built** | 58.9 % | **95.4 %** | not with a margin |
| R4 — six reverbs AND the desk in use, **as built** | 58.9 % | **110.3 %** | **NO** |
| **R3 with lever L1** (§8) | 58.9 % | **82.9 %** | **yes** |
| **R4 with lever L1** | 58.9 % | **97.8 %** | on the line |
| **R4 with levers L1 + L2** | 58.9 % | **95.7 %** | yes, by 1.3 points |

**The three conditions:**

1. **`DSP4_C2_BQ_GRAPH=1` must stay signed.** On arm A every one of these
   regimes is over: R1 lands at 94.7 % and R4 at 127.3 %. PW signed it on
   2026-09-29 (S147); this work is priced against that signature and cannot
   be built on the fallback arm.
2. **Lever L1 must be taken before the aux matrix ships, and measured on its
   own** — put chip 2's aux mixes on the **bus-major live-crosspoint fabric
   chip 1 has run since S27** (`DSP4_RTG_FABRIC=1`, already in
   `shipping.config`). Chip 2's mixes instead take the generic block wrapper,
   which stages every *declared* source on every sample whether its
   coefficient is zero or not. It is worth **12.47 points of chip 2** at the
   measured 5.29 c/MAC, it changes no audio and no address, and without it
   neither R3 nor R4 has a margin. S142 §5.2 recommended exactly this and the
   group half was built the other way in S143; the aux matrix would inherit
   that shape.
3. **Chip 1 must NOT also carry the RTA in a shipping image without a
   re-price.** `Rta On` alone is +10.99 % of chip 1 (measured, S64-3/S65-2).
   Chip 1 still fits with it (69.9 %), but it is by far the largest single
   item in the 890 and it is the one that should be ruled on separately.

**Rev D (HyperRAM, DSP MOD 1) is NOT required for any of the 890.** Not one
of the 890 cells asks for a delay line. The delay pool stays at 91.0 % — the
same 1,886,112 of 2,072,576 bytes S144 measured — and the only thing that
moves it is the *next* feature that wants a 250 ms line, of which there is
room for about three and a half.

**Chip 1 is not in question.** It absorbs its 509 cells for 1.36 % and lands
at 58.9 % against a 42.45-point margin — and 69.9 % if `Rta On`, its 510th,
is ruled in. Every number below that decides anything is chip 2's.

---

## 1. The baseline, and what is measured against what is constructed

Budget is **327,680 cycles/block** on each chip — block 16, 983.04 MHz,
3,000 blocks/s.

The last figure measured **on the part** is S86's driven row on the signed
pairing configuration (`MW/D24/DSP/s86/rx-path.md:360-368`):

| row | chip 1 | chip 2 | missed blocks |
|---|--:|--:|---|
| C — DRIVEN, six FX live, six Echoes | **57.55 %** | **84.47 %** | **0** |

Everything since is **constructed**, and this report does not pretend
otherwise:

- S142–S144's graph work adds ≈ 7.2 points of chip 2, landing at **≈ 91.7 %**
  on arm A. That is a construction, and it is bench row 3 of the S146 window.
- `DSP4_C2_BQ_GRAPH=1` — the arm that now ships — is worth **≈ 17 points**
  (`dsp4-capacity-decision-20260913.md`, the `s16sd`/`s20` pair). S146 and
  S147 both carried it as constructed and neither re-measured it.
- So the chip-2 baseline this report prices against is **≈ 74.7 %**, and the
  arm-A column is carried beside it throughout.

**Two honesty notes carried forward, and one new one.**

1. **There is still no per-class breakdown of either chip's driven row**
   (S142 §9). Every marginal rate below comes from an earlier measured
   campaign and is cited; the arithmetic that stacks them on a whole-graph
   baseline is not itself measured. §7 builds the best chip-1 breakdown the
   tree allows and states its confidence.
2. **Boot-to-boot spread is 0.53 points** within a session. Read every
   figure as ±0.5.
3. 🔴 **NEW, and it changes how the baseline should be read: the signed
   84.47 % is a desk with every chip-2 aux bus on the S23 bypass.** S23-5's
   fix means an aux summing node with no live *switched* send is a block
   copy — about 38 instructions — and one with a single live switched send
   pays the full sum over all its sources. S86's driven row was taken with
   `Fx*AuxOn` at its shipping default of 0, so every one of the twelve aux
   sums was on the bypass. The moment an operator opens one FX return into
   one aux, that node costs **2,112 c/blk (0.64 %)** more; with all eight D24
   aux buses off the bypass it is **16,896 c/blk (5.16 %)** — before any of
   this work. This is recorded as **S148-1**. It is not a defect; it is a
   regime the record has never measured, and the aux matrix makes it the
   normal case rather than the exceptional one, because *using* the matrix is
   exactly what takes an aux off the bypass.

### 1.1 The rates, and where each one comes from

| rate | value | source |
|---|--:|---|
| one crosspoint MAC, bus-major fabric (chip 1) | **5.29 c/MAC** | `FRONTIER_RTG_RESIDUAL` — 5,417 c/blk for 1,024 MACs; `DSP4_RTG_FABRIC=1` is in `shipping.config` |
| one switched source on a chip-2 mix node, **block-rate fold** | **23 c/blk** | S143 §5, counted from the emitted loop body |
| one source on a chip-2 aux mix node, **off bypass, as built** | **192 c/blk** | S23-5: *"about 63 instructions a sample a node before a single MAC"* at 7 sources = 9 instr/sample/source pre-MAC (of which 6 are the generic wrapper's `_buf_` staging), + ~3 for the MAC itself, × 16 samples. Cross-checks against S23's own *"1,008 instructions a block"*: 7 × 9 × 16 = 1,008 exactly |
| biquad stage added to an existing cascade | 91.5 c/blk | `FULLCFG_GEQ_BAND_EXISTING` |
| new biquad-cascade node overhead | 729 c/blk | `FULLCFG_GEQ_STAGE_NEWNODE` |
| 31-band GEQ instance, mono, new node | 3,566 c/blk | `FULLCFG_GEQ_STAGE_NEWNODE` |
| LIMITER, mono instance | 257 c/blk | `C2_LIM` |
| DELAY, one channel | 109 c/blk | `C2_DLY` |
| floor charge, simple block node | 210 c/blk | `C2_OUT` 13.1 c/sample × 16 |
| six FX at Type 0 Echo (shipping default) | +1.53 pts | `FX_C2_D24_TYPE0_ECHO` |
| six FX at Type 3 Reverb (worst Type) | +16.44 pts | `FX_C2_D24_TYPE3_REVERB` |
| the RTA filterbank, either chip | **+34,400 c/blk = +10.5 pts** | S64-3 / S65-2, measured on the part, product- and configuration-independent |
| the cue bus | +0.4–0.6 pts | S65-2 |
| SIMD pair factor, in-graph | 1.72–1.82× | `COMP_PAIR` / `GATE_PAIR` |
| one meter accumulate tap | 64 c/blk (4 instr/sample) | **constructed** |

Three rates below are **constructed, not measured**, and each is labelled
where it is used: the meter tap, the AntiClip detector, and the insert.

---

## 2. The 890, family by family

Grouped by what unblocks them. Every row states its chip, the node it needs,
the cycles at the shipping default, and the memory it claims.

### 2.1 Free — cells that need a table entry and not a line of DSP

| family | cells | chip | what it actually is | c/blk |
|---|--:|---|---|--:|
| `Fx DuckThr` | 6 | 2 | the master's own note says *"legacy alias of DuckSens"*, and `Fx001DuckSens001` **is mapped**, at page 1 / 1642. This is a compat-alias table entry (`audit-compat-aliases.py`, `alias-audit.md`) — not a graph item at all | **0** |
| `MainL Delay`, `MainR Delay` | 2 | 2 | `Main001Delay001` is mapped at page 1 / 1434 and **both delay lines already exist** (`C2_MAIN_DLY` + `C2_MAIN_DLY_R`, 250 ms each, already allocated). Per-leg delay costs stopping `C2_MAIN_DLY_R` following its master for the delay word only. 2 SPI words, no new delay bytes | **0** |
| `Chan Trim` | 24 | 1 | ±20 dB digital trim after the ADC. `C1_GAIN_nn` already carries gain/mute/polarity as one folded coefficient; the trim is one more factor in the same fold, at control rate | **0** |
| `Grp Trim` | 4 | 2 | same fold, into `C2_GRP_FDR_nn` | **0** |
| `Aux/Main* LimiterRng` | 4 | 2 | range/depth is a `DSP4_DYN_LUT` **design** parameter — it changes the baked table, which is a control-rate step that already runs when any limiter parameter moves | **0** |
| **subtotal** | **40** | | | **0** |

Forty of the 890 cost nothing. `Fx DuckThr` in particular should not be
counted as owed work at all; it is an alias audit item. **This list cuts
across §2.2–§2.7 rather than sitting beside them** — each of these forty is
also counted once, at zero, in its own chip's table below.

### 2.2 Chip 1 — the channel strip and the two generators

| family | cells | node | c/blk | % chip 1 | basis |
|---|--:|---|--:|--:|---|
| `Chan Trim` | 24 | `C1_GAIN_nn` coefficient fold | 0 | 0.00 | §2.1 |
| `Chan Mtr003` (preamp meter) | 24 | third tap on `C1_MTR_nn`, read at `C1_IN_nn` (post-ADC, pre-gain) | 1,536 | 0.47 | **constructed** — 4 instr/sample accumulate |
| `Chan AntiClip` | 24 | block-rate peak test + gain walk on the same trim coefficient | 480 | 0.15 | **constructed** — ~20 instr/strip/block |
| `Chan AuxPan` | 192 | the `C1_RTG_nn` crosspoint coefficient pair | 0 | 0.00 | S142 §5.3 — see §5 |
| `Chan AuxPanMode` | 192 | the same coefficient, different law | 0 | 0.00 | S142 §5.3 |
| `Talk Dest` | 18 | 2 × `C1_TALK_nn` into up to 9 chip-1 buses each | 1,524 | 0.47 | 18 live fabric crosspoints × 16 × 5.29 |
| `Noise Dest` | 11 | `C1_NOISE` into 11 chip-1 buses | 931 | 0.28 | 11 × 16 × 5.29 |
| `Chan InsertPos` | 24 | **BLOCKED** — §9 | — | — | |
| **subtotal (steady)** | **509** | | **4,471** | **1.36** | |
| `Rta On` — chip 1 too, priced separately in §2.7 | 1 | | 36,000 | +10.99 | S64-3 / S65-2 |
| transient, while an aux pan ramps | | | ≤1,000 | +0.31 | S142 §5.3 |

**`Talk Dest` is NOT blocked, and S144-4 can be narrowed.** S144 recorded
talkback injection as blocked because "reaching the chip-2 phones needs a
mix-fabric slot, and that map is single-sourced in `shared/dsp4-logic/`".
That is true of the *phones* destination and of nothing else. Talkback into
an aux or into main is a chip-1 crosspoint into buses that already exist and
already have their own interchip slots — `C1_BUS_AUX_01..12`,
`C1_BUS_MAIN_L/R`, `C1_BUS_SUB`. Nine destinations is exactly the shape of
`Talk[1-2]Dest[2-10]`.

And even the slot question has an answer on a D24: **`shared/dsp4-logic/
slot-map.csv` line `MIX_2` allocates slots 0–8 and carries 16**, so seven
slots are unallocated; and on a D24 four more (`BUS_MTX_01..04`, slots 5–8)
are dead, because `CFG_MTX_MASK` went to 0 in S143. **Eleven free
chip-1→chip-2 lanes on a D24** — recorded as **S148-2**, because S144-4 reads
as though there were none.

`Chan Mtr003` is also the right moment to settle **S143-1**: `Chan*Mtr002`
is documented as the post-fader tap and is in fact the true-RMS of the same
post-trim word. Adding a third tap means touching that table; fixing the
second one there costs nothing extra.

### 2.3 Chip 2 — the aux matrix (176 cells)

`Aux AuxSend/AuxOn` 128 + `Main{L,R,Ctr} AuxSend/AuxOn` 48. Priced in full in
§3; the totals it contributes here are:

| | c/blk | % chip 2 |
|---|--:|--:|
| always (the block-rate fold, 8 nodes × 10 new sources × 23) | 1,840 | 0.56 |
| the one-block alignment copies (8 × 16) | 128 | 0.04 |
| **shipping default** | **1,968** | **0.60** |
| every aux carrying a live matrix feed, off bypass, **as built** | +15,360 | +4.69 |
| the same, **on the fabric (lever L1)** | +4,232 | +1.29 |

### 2.4 Chip 2 — the group surface (84 cells)

| family | cells | what it needs | c/blk default | c/blk in use |
|---|--:|---|--:|--:|
| `Grp AuxPick` | 32 | four crosspoints per (group, aux) — the four taps — with exactly one carrying a non-zero coefficient, so the pick is a **coefficient crossfade** and is click-free for free (S144 §1.4's argument) | 2,208 | +18,432 as built, **0 on the fabric** |
| `Grp FxSend` / `Grp FxOn` | 48 | **six new chip-2 `MIX_BUS` nodes** — see below | 1,812 | +5,760 as built, +2,031 on the fabric |
| `Grp MainOn` | 4 | four main-mix sources become switched | 184 | 0 |
| `Grp Trim` | 4 | fader coefficient fold | 0 | 0 |
| `Grp InsertOn` | 4 | **BLOCKED** with `Chan InsertPos` — §9 | — | — |

**`Grp FxSend` looked structural and is not.** The FX *buses* are chip-1
nodes (`C1_BUS_FX_01..06`) and the groups are chip-2 nodes, and there is no
chip-2 → chip-1 audio path in this graph — every `INTERCHIP_SEND` runs one
way. But the FX **engines** are on chip 2 (`C2_FX_ENG_nn`, fed by
`C2_RECV_FX_nn`), so the group's contribution can be summed on chip 2, in
front of the engine: a new `C2_MIX_FX_nn` taking `C2_RECV_FX_nn` plus the
four group sends. Six nodes, no new wire, no slot, no interchip change.

Its **ordering** constraint is real and is the S23/S143 splice for the third
time: the GRP chain must publish before the FX pre-mixes, which must publish
before the FX engines, which must publish before the aux and main sums. The
GRP family carries EQ/GEQ SIMD pairs and `_C2_PAIR_FAMILIES` requires each
family's nodes to be a contiguous run, so this must be spliced as one run and
not left to `repair_process_order`. No cycle is created: nothing feeds a
group on chip 2 except `C2_RECV_GRP_nn`.

**`Grp AuxPick` is the expensive one, and only on the current wrapper.**
Carrying four taps per (group, aux) as four static sources puts twelve extra
sources on every aux mix node, and the generic wrapper stages every one of
them through its scalar `_buf_` word on every sample whether its coefficient
is zero or not. That is the whole of the 5.62 points in the in-use column,
and **lever L1 removes all of it** (§8): on a live-crosspoint fabric three of
the four taps are zero coefficients and are not walked at all, so `AuxPick`
becomes free.

### 2.5 Chip 2 — the limiter sidechains (64 cells)

`Aux Limiter{DetSrc,FilterHpf,FilterLpf,FilterOn,FilterQ}` 40 +
`Main{L,R,Ctr,Sub} Limiter{DetSrc,FilterHpf,FilterLpf,FilterOn,FilterQ,Rng}`
24.

Twelve limiter instances (8 aux + MainL + MainR + MainCtr + MainSub) each
gain **one biquad on the detector path only** — not in the audio path, which
is why it is cheap and why a `DetSrc` change is a gain transient rather than
a signal discontinuity.

| | c/blk | % chip 2 |
|---|--:|--:|
| `FilterOn = 0` (the declared default): the S23/S24 unity-bypass compare, 12 × 20 | 240 | 0.07 |
| every sidechain filter engaged: 12 × (91.5 + ~50 detector plumbing) | 1,698 | 0.52 |
| `DetSrc` — a control-rate pointer plus a short gain ramp | 0 | 0.00 |
| `LimiterRng` — a `DSP4_DYN_LUT` design parameter | 0 | 0.00 |

DM: 12 × ~19 words (two coefficient banks, state, design words) ≈ **912
bytes**. Under `DSP4_C2_BQ_GRAPH=1` the eight aux sidechain biquads pair with
their partners like every other aux cascade stage, so the engaged figure is
an over-estimate on the shipping arm.

### 2.6 Chip 2 — the FX returns and the recorder (44 cells)

| family | cells | what it needs | c/blk | % |
|---|--:|---|--:|--:|
| `Fx Trim` | 6 | one MAC/sample ahead of the engine | 96 | 0.03 |
| `Fx Pan` + `Fx MainOn` | 12 | the FX→main crosspoint stops being a plain 1.0 and becomes a switched, panned pair — the 2026-08-25 pan fold, which is where a pan already lives | 276 | 0.08 |
| `Fx Mtr002` (input meter) | 6 | one more accumulate tap | 384 | 0.12 |
| `Fx DuckThr` | 6 | alias — §2.1 | 0 | 0.00 |
| `Fx PingPongStart` | 6 | see below | 1,644 | 0.50 |
| `Rec Mtr` | 2 | two taps on the record feed (`C2_CODEC_AUX_OUT`/`_R`) | 128 | 0.04 |

🔴 **`Fx PingPongStart` is the one family in the 890 whose price depends on a
ruling, and the two answers are 0.50 % and 16.4 %.** The six FX engines are
**mono end to end** — the reverb's `_R` buffers were deleted 2026-09-08
because nothing read them, and S23 gate 2's note has said so since. A
ping-pong echo does not need a stereo engine: it needs the engine's existing
delay line read at **two taps** and the return fader to have a second leg.
That is the 1,644 c/blk above (six follower faders at the 210 floor plus the
second tap), and it is what this report prices. If what PW means is a
**stereo FX engine** — a second independent reverb/echo instance per slot —
the price is the measured one: six more Type-3 engines is **+16.44 points**,
and it does not fit in any regime. Recorded for PW, not asked.

`Rec Mtr` is worth one sentence: the rest of the `Rec` family is `mcu-only`
or `control-plane` (the Pi owns USB recording), so two DSP meter taps are the
only part of the recorder the DSP is asked for. If the record feed is taken
host-side instead, these two cells belong with the rest of the family and
cost zero.

### 2.7 Chip 1 — the RTA (1 cell)

`Rta001On001`, one cell, **+34,400 cycles a block plus the cue bus it
requires**, measured on the part and product-independent (S64-3, S65-2).
That is **+10.99 % of chip 1** — more than eight times everything else in
§2.2 put together.

The filterbank exists (`src/chip1/rta.asm`, 31 × 1/3-octave × 3 biquads × 2
channels, plus S144's ring metric) and is off in `shipping.config`
(`DSP4_RTA=0`, `DSP4_CUE=0`). Turning it on also costs chip 1 code
181,490 → 184,378 B and DM 309,612 → 315,692 B, measured on arm D's own
linker map.

**Chip 1 fits with it — 69.9 % — and this report recommends it be ruled on
its own**, not carried in as one line of an 890-cell backlog.

### 2.8 Chip 2 — `Aux Link` (8 cells)

Priced in §5. The cycle cost is not in the switch; it is in what a
stereo-linked pair does to the SIMD pairing: **860 c/blk (0.26 %)**.

---

## 3. The aux matrix — pricing the team's model

**The team's model, as relayed (PW, 2026-09-29):** *"each aux maintains its
own processing block, no extra: if aux1 is assigned to aux2, aux1's signal
uses aux1's processing, and aux2's processing runs on the mixed matrix"*.

Read into the graph, that is unambiguous: the crosspoint takes aux *i*'s
**finished output** — after `FDR → EQ → GEQ → AFB → LIM → DLY`, i.e.
`_blk_C2_AUX_DLY_i` — and adds it to aux *j*'s **bus**, `C2_MIX_AUX_j`,
*before* aux *j*'s own strip. Aux *j*'s processing then runs on the mixed
sum. It is aux-into-aux, not an output mixer. The same shape carries
`MainL`, `MainR` and `MainCtr` into any aux.

That is exactly the placement S142 §5.2 designed and S143 §4 could not build.

### 3.1 Why it could not be built, in one paragraph

A crosspoint from `C2_AUX_DLY_i` into `C2_MIX_AUX_j` makes aux *j*
**reachable** from aux *i*. Two nodes can be SIMD-paired only if neither is
reachable from the other. With the crosspoints present in the same block,
every aux is reachable from every lower one, so **no two aux chains can be
paired at all** — S143 §4 proved it over the experiment graph in both
directions: 6 of 6 `LIM` pairs, 6 of 6 `EQ`, 6 of 6 `GEQ`, 6 of 6 `AFB`. The
aux family is **492 of the 648 paired cascade stages on chip 2**, so under
`DSP4_C2_BQ_GRAPH=1` that is about **three quarters of the 17-point lever**.

### 3.2 The decision table

| | (i) STRICT ORDER, same block | (ii) ONE-BLOCK-LATE READ + alignment **(recommended)** |
|---|---|---|
| what the crosspoint reads | aux *i*'s output, this block | aux *i*'s output, **last** block |
| order constraint | *i* < *j*, fixed forever | none — any *i*, *j* |
| SIMD pairs kept | **none of the aux family** | **every one** |
| pairing forfeit, arm B | **≈ 13 points** (S143 §4) | 0 |
| always cost (fold, 8 nodes × 10 sources × 23) | 1,840 c/blk = 0.56 % | 1,840 c/blk = 0.56 % |
| alignment delay | none needed | one block on aux *j*'s direct sum |
| delay/DM cost of the alignment | 0 | 8 × 16 words = **512 bytes** of DM (not the delay pool) |
| cycles for the alignment | 0 | 8 × 16 = **128 c/blk = 0.04 %** |
| added aux output latency | 0 | **+16 samples = +333 µs** |
| off-bypass cost, every aux live | +4.69 % as built / +1.29 % on the fabric | the same |
| comb filtering against a direct path | none | **none — that is what the alignment is for** |
| feedback guard needed | no (a total order has no cycles) | **yes** — §4 |
| **net against arm B** | **+13.6 points** | **+0.60 points** |

**(ii) wins by thirteen points and the hub's recommendation is right.**

### 3.3 The alignment delay, and why it should be unconditional

Without the alignment, aux *j*'s output carries the direct contribution at
block *n* and the matrix contribution from block *n−1*. Where the same source
reaches aux *j* both ways, the two copies are 333 µs apart and comb — the
first notch at **1/(2 × 333 µs) ≈ 1.5 kHz**, which is squarely in the
intelligibility band and is not acceptable on a monitor send.

The fix is to delay aux *j*'s **own** direct sum by one block so both copies
arrive together. Two ways to arm it:

| | (a) **unconditional** *(recommended)* | (b) engaged when a matrix source goes live |
|---|---|---|
| cost | 8 block buffers = 512 B, 128 c/blk | the same, plus the switch |
| aux latency | +333 µs always | +333 µs only while the matrix is in use |
| the switch itself | **there isn't one** | a crossfade between the dry block and the same block 16 samples late |
| click-free? | trivially — nothing ever changes | **no, not cleanly.** Crossfading a signal against a 333 µs-delayed copy of itself *is* a sweeping comb for the length of the fade. A 576-sample fade makes it a 12 ms artefact on that aux |

**Recommend (a).** The switching problem in (b) has no clean answer: the
thing being faded between is the signal and its own echo, so any fade length
is audible on programme material. Paying 333 µs on every aux, permanently,
buys the question away. The contract number moves: the through-DSP figure for
an **aux** output becomes 82 + 16 = **98 samples = 2.042 ms** at block 16
(main, monitor and phones are unchanged). That is a contract change and it is
PW's to sign.

If (b) is ruled anyway, the least-bad form is to engage the alignment while
the aux is **muted or below a threshold**, or at the moment the operator
opens the first matrix send on that aux and before its coefficient ramps up —
i.e. arm the delay first, ramp the send second. That is click-free because
nothing is audible through the crosspoint yet. It is stated here so it is not
re-invented; it needs the host to sequence two writes.

### 3.4 Why `i < j` should NOT be kept "so a late read cannot form a loop"

The dispatch asks to keep *i* < *j* under (ii) as a belt-and-braces. **A
one-block-late loop still diverges** — S142 §5.1 rejected the delayed-snapshot
design for exactly that reason, and it is right: a loop with round-trip gain
≥ 1 diverges whether the lap takes one sample or one block; it just takes
333 µs a lap to do it. So the late read does not make a loop safe, and *i* <
*j* is not a safety measure that can be dropped or kept casually — it is
either the whole guard or it is nothing.

PW's ruling 2b (§4) replaces it with a real guard, and once there is a real
guard the fixed order costs freedom for nothing. §4 compares them.

### 3.5 Where the cycles actually are

The number that matters is **not** the fold. It is what happens when an aux
leaves the S23 bypass.

| | sources on a D24 aux mix node | c/blk per node | 8 nodes |
|---|--:|--:|--:|
| on the bypass (block copy) | — | ~38 | ~304 |
| off bypass, today (recv + 6 FX + 4 GRP) | 11 | 2,112 | 16,896 = **5.16 %** |
| off bypass, + the matrix (+ 3 masters + 7 aux) | 21 | 4,032 | 32,256 = **9.84 %** |
| off bypass, + the matrix + `AuxPick`'s four taps | 33 | 6,336 | 50,688 = **15.47 %** |
| **the same work on the bus-major fabric** (20 live crosspoints) | 21 | 1,693 | **13,542 = 4.13 %** |

**Enabling one matrix crosspoint on one aux takes that whole node off the
bypass.** That is the real price of the feature, and the last row is why
lever L1 is a *condition of the verdict* rather than an optimisation.

The generic wrapper charges per **declared source**, on every sample,
whether that source's coefficient is zero or not — six of the nine
pre-MAC instructions are it staging a block into a scalar word. Chip 1's
`rtg_fabric` charges per **live crosspoint** and does no staging at all, at
a measured **5.29 c/MAC**. Three quarters of the work in the third row is
therefore work on coefficients that are zero: `AuxPick`'s four taps are one
live crosspoint and three zeros, and a desk with four of its eight aux buses
patched is four live nodes and four bypassed ones.

**S142 §5.2 said exactly this and was right**: *"Built as a per-strip
accumulate instead of a bus-major fabric it would be … three times the price
for the same arithmetic. `DSP4_RTG_FABRIC=1` is already in `shipping.config`
and chip 1 already runs this pattern; chip 2 gets the same one."* S143 built
the group half the other way — *"more sources on `C2_MIX_AUX_nn`"* — which
is the per-strip-accumulate shape, and the aux matrix would inherit it.

---

## 4. 🔴 PW ruling 2b — no feedback path, ever; the skins grey out

**PW, 2026-09-29:** *"matrix mixing should disallow all potential feedback
paths, and grey out skin controls to help user; more cells can be added if
required to facilitate."*

### 4.1 The graph that can contain a cycle is exactly 8 × 8

Worth stating, because it bounds the whole problem. On a D24:

- **aux → aux** is the only edge class that can close a cycle. Eight nodes,
  56 possible edges (no self-feed).
- **MainL / MainR / MainCtr → aux** can never close one: nothing on chip 2
  feeds the main or centre bus from an aux. **Computed, not asserted** — the
  reverse cone of `C2_MIX_MAIN_L`, `C2_MIX_MAIN_R`, `C2_CTR_FDR` and
  `C2_WOOF_MIX` over `dsp.csv` is 65 / 65 / 1 / 84 nodes and contains **zero**
  `C2_AUX_*` or `C2_MIX_AUX_*` nodes. `C2_MIX_MAIN_L/R` read the interchip
  main bus, the four group compressors, the six FX returns and the
  USB/BT/codec/Pi/snake inputs; `C2_CTR_FDR` reads `C2_RECV_SUB` and nothing
  else.
- **groups are sinks for this purpose**: `C2_GRP_FDR_nn` reads
  `C2_RECV_GRP_nn` and nothing else, so `Grp FxSend` (§2.4) — group → FX
  pre-mix → engine → return → aux/main — adds no cycle either, because
  nothing on chip 2 feeds a group.
- **aux → Woof** exists (`C2_WOOF_SRC` takes `C2_AUX_DLY_01..08`), but the
  Woof has no `AuxSend` family on any product, so it is a sink.

So the guard is a reachability test on an 8-node digraph. On the D32 superset
it is 12 nodes. **Warshall on 12 nodes is 1,728 bit operations** — a control-
rate nothing, run once per enable.

### 4.2 Fixed order versus dynamic rule

| | fixed `i < j` | **dynamic (recommended)** |
|---|---|---|
| edges a user can ever have | 28 of 56 | any acyclic subset of 56 |
| **worst-case live edges** | 28 | **28** — a DAG on 8 nodes has at most 28 edges, so the compute worst case is *identical* |
| worst-case cycles | 9.84 % as built / 4.13 % on the fabric | **the same** |
| crosspoint coefficient slots to allocate | 28 | 56 (+ 224 bytes of DM) |
| skin | 36 of 64 cells greyed **permanently** | greyed only when that send would close a cycle |
| guard needed | no | yes: host + DSP, §4.3 |
| can aux 5 feed aux 2? | never | yes, as long as aux 2 does not reach aux 5 |

**The dynamic rule costs nothing in worst-case cycles and 224 bytes of DM,
and it is what the ruling asks for.** The fixed order's only advantage — no
guard — is not an advantage once the ruling requires a guard anyway to stop a
bad write.

### 4.3 Enforcement, in two layers

**Layer 1 — the host (the single writer).** `DspApply` is already the app's
only DSP writer and `DspAddressMap` is already *"deliberately the app's ONLY
source of DSP addresses"*. It holds the 8 × 8 adjacency of enabled sends,
and:

- on a request to set `Aux{i}AuxOn{j} = 1`, it computes whether *i* is
  reachable from *j* in the current graph. If it is, the write is **refused**
  and not sent.
- it **publishes** the availability of every crosspoint so skins can grey,
  as cells (below).
- availability is recomputed after every accepted enable *and* every
  disable — turning a send off makes other sends legal again, and a skin that
  does not re-enable them is as wrong as one that does not grey.

**Layer 2 — the DSP (so a bad write can never howl).** The chip-2 control-rate
pass keeps its own adjacency from the `AuxOn` words it already receives, runs
the same reachability test on every enable, and holds a loop-closing
crosspoint's coefficient at **exactly zero**. That is not a new concept and
it needs no new cell: the master's own note already says *"a self-feed or a
feed that would close a loop is inert"*. The DSP guard is the one that must
be right, because it is the only one that holds when the host is wrong, a
bench tool writes directly through `landed-d24.json`, or two writers race.

Cost: an 8 × 8 bit matrix (8 words), a transitive closure on enable (~1,700
bit ops, control rate, not per block), and one AND into the existing
coefficient fold. **0 c/blk steady, ~32 bytes of DM.**

### 4.4 The proposed cells — names are forever, so these are PROPOSED only

Two shapes. Neither is added in this tree; both go to PW and to `defs`.

**Shape A — one availability mask per destination aux (RECOMMENDED).**

```
Aux[1-12]AuxAvail[1-1]     Class: host-managed
```
One cell per aux. Its value is a bitmask, bit *i* set = *"aux i may be sent
into this aux right now"*. Twelve cells on the superset, **eight on a D24**.
The host computes and writes it; no DSP address, no kernel read — the same
class as `Aux Dca`, where *"the host owns the value outright"*.

Notes text, proposed:

> Aux matrix source availability, one bit per source aux (bit N-1 = Aux N):
> 1 = that source may be enabled into this aux, 0 = enabling it would close
> a feedback loop and the write will be refused. Host-computed and
> host-published; skins grey the crosspoint when the bit is 0. Recomputed on
> every AuxOn change. (PW ruling 2026-09-29: no feedback path, ever.)

**Shape B — one availability cell per crosspoint.**

```
Aux[1-12]AuxAvail[1-12]    144 cells on the superset, 64 on a D24
```
Uniform with `AuxSend`/`AuxOn`, and a skin binds it with no bit arithmetic.
It costs 144 cells against 12 for the same information.

**Recommendation: Shape A.** Cells are forever and Shape B adds 144 of them
to carry twelve words of derived state. The bit arithmetic is one `&` in the
skin.

**No `MainL/MainR/MainCtr AuxAvail` cells are proposed**, and the reason is
in §4.1: an L/C/R → aux send can never close a cycle, so its availability is
the constant 1 and a cell for it is a cell with one value. If skin uniformity
demands it, the cheap answer is for the skin to treat a missing availability
cell as "always available".

### 4.5 What the guard does NOT cover, stated

The DSP guard bounds *digital* loops inside the aux matrix. It says nothing
about an **acoustic** loop — a wedge into a mic into the same wedge — which
is what the anti-feedback work (S144 item 4) is for, and nothing about a
loop closed **outside the desk** through an insert or an external processor.
Those are different problems with different answers and this ruling should
not be read as covering them.

---

## 5. Stereo aux pairing — `Aux Link`, `Chan AuxPan`, `Chan AuxPanMode`

**The switch costs no cycles and that is the design** (S142 §5.3, restated
because it is still true and it is what makes the realtime switch possible):

- a channel that feeds a pair feeds **both** members in either mode, so the
  number of MACs does not depend on `Aux Link`;
- what changes is the coefficient pair — `send, send` in dual mono,
  `send·gL, send·gR` in stereo, with `gL/gR` read from the one pan table
  (`tools/dsp/pan_table.py`, PW ruling R5) at the index `Chan AuxPan` gives;
- the send coefficients already ride the `GainFast` ramp, so **the switch is
  click-free because the only thing that moves is a coefficient**;
- nothing is allocated or freed at switch time, so **both modes are always
  available** and the switch is realtime by construction.

`Chan AuxPan` is an **index, not a gain** — 127 table positions,
`fix(pan*126)`, `Neutral = 63` (dead centre), which is exactly what the cell
declares. `Chan AuxPanMode` selects which law is read out of the table; its
enumeration is *"provisional until the skin audit"* and this report does not
invent one.

**Steady-state cost: 0 on both chips. Transient: ≤1,000 c/blk on chip 1
(+0.31 %) for the ~30 ms a ramp lasts** — 24 strips × 2 coefficients, and
`C1_RTG`'s block-rate prep only runs at all when the strip's control epoch
has moved (D22).

🔴 **The one real cost is on chip 2 and S142 did not price it: a
stereo-linked aux pair cannot SIMD-pair its LIMITER.** A stereo bus limiter
must detect on max(|L|,|R|) and apply one gain to both legs, or the image
walks under limiting — that is the same argument S143 §1.2 made for the main
bus, and it had the same consequence there: `_comp_pair_blk` reads one input
block per channel and has no second detector input, so a stereo-linked node
falls back to its scalar body. Four D24 aux pairs, all linked:

| | c/blk |
|---|--:|
| a paired aux LIMITER pair (2 × 257 / 1.72) | 299 |
| two scalar aux LIMITERs | 514 |
| **forfeit per linked pair** | **215** |
| **four pairs** | **860 = 0.26 %** |

It is small, it is bounded, and it is paid only for pairs the operator
actually links. The EQ, GEQ and AFB pairs are **unaffected** — those are
per-channel filters and nothing links them.

---

## 6. The totals

### 6.1 Chip 2 — the bill, at the shipping default

| item | cells | c/blk | % of chip 2 |
|---|--:|--:|--:|
| aux matrix — fold + alignment (§3) | 176 | 1,968 | 0.60 |
| `Grp AuxPick`, naive build (§2.4) | 32 | 2,208 | 0.67 |
| `Grp FxSend`/`FxOn` — six chip-2 FX pre-mixes (§2.4) | 48 | 1,812 | 0.55 |
| limiter sidechains, `FilterOn = 0` (§2.5) | 64 | 240 | 0.07 |
| `Aux Link` — four LIMITER pairs forfeited (§5) | 8 | 860 | 0.26 |
| `Grp Trim` + `Grp MainOn` (§2.4) | 8 | 184 | 0.06 |
| `Fx Trim` (§2.6) | 6 | 96 | 0.03 |
| `Fx Pan` + `Fx MainOn` (§2.6) | 12 | 276 | 0.08 |
| `Fx Mtr002` (§2.6) | 6 | 384 | 0.12 |
| `Fx PingPongStart` — two-tap echo reading (§2.6) | 6 | 1,644 | 0.50 |
| `Rec Mtr` (§2.6) | 2 | 128 | 0.04 |
| `Fx DuckThr` (alias), `MainL/R Delay` (§2.1) | 8 | 0 | 0.00 |
| `Grp InsertOn` — BLOCKED (§9) | 4 | — | — |
| **chip-2 total** | **380** | **9,800** | **2.99** |

**The 890 split: 510 chip 1 (§2.2 509 + `Rta On`), 380 chip 2.** `Aux Link`
is counted once, here, for its chip-2 consequence — its chip-1 half is the
send coefficient pair, which costs nothing (§5). `LimiterRng` is counted
inside the sidechain row and `Grp Trim` inside its own row, both at zero.

### 6.2 Chip 2 — what the desk adds when it is IN USE

| | as built | % | on the fabric (L1) | % |
|---|--:|--:|--:|--:|
| every aux leaves the S23 bypass at all (S148-1 — **pre-existing**) | 16,896 | 5.16 | | |
| the matrix's own sources, off bypass | 15,360 | 4.69 | | |
| `Grp AuxPick`'s four taps, off bypass | 18,432 | 5.62 | **0** | **0.00** |
| — the three aux rows above, on the fabric: 8 × 20 live × 16 × 5.29 | | | **13,542** | **4.13** |
| every group FX send open (six `C2_MIX_FX` nodes) | 5,760 | 1.76 | 2,031 | 0.62 |
| every limiter sidechain engaged | 1,458 | 0.44 | 1,458 | 0.44 |
| **added over the shipping default** | **57,906** | **17.67** | **17,031** | **5.20** |

**Lever L1 is worth 40,875 c/blk = 12.47 points in this column**, and it is
the single largest number anywhere in this report.

### 6.3 The regimes, both chips, both arms

| regime | chip 1 | chip 2, arm B **(ships)** | chip 2, arm A (fallback) |
|---|--:|--:|--:|
| baseline after S142–S145 | 57.55 % | ≈ 74.7 % | ≈ 91.7 % |
| **R1** — Echo default, all 890 built, nothing switched on | **58.91 %** | **77.69 %** | 94.69 % |
| **R2** — six Type-3 reverbs | 58.91 % | **92.60 %** | 109.60 % |
| **R3** — Echo default, desk IN USE, **as built** | 58.91 % | **95.36 %** | 112.36 % |
| **R4** — six reverbs AND desk in use, **as built** | 58.91 % | **110.27 %** | 127.27 % |
| **R3 + lever L1** (the fabric) | 58.91 % | **82.89 %** | 99.89 % |
| **R4 + lever L1** | 58.91 % | **97.80 %** | 114.80 % |
| **R4 + levers L1 + L2** | 58.91 % | **95.71 %** | 112.71 % |
| chip 1 with `Rta On` as well | **69.90 %** | — | — |

Abort line: **~97 %, or any missed block on any chip-row of any boot.**

**R4 is a synthetic maximum, not a desk** — six simultaneous Type-3 reverbs
*and* all eight aux buses carrying matrix feeds *and* every group FX send
open *and* every group aux pick off its default *and* every limiter sidechain
engaged. It is reported because "any missed block" is the abort criterion and
a synthetic maximum is what that criterion is measured against.

**Read the table this way.** R3 — the realistic heavy case, a working desk
with the whole matrix patched on the shipping FX default — **fits at 82.9 %
once L1 is taken, and does NOT fit as built (95.4 %, four points of margin
against a 0.53-point boot spread, which is not a margin).** R4 fits at
95.71 % with L1 and L2 together, with **1.29 points of margin** — inside the
abort line and close enough to it that it is a *measurement*, not a
conclusion, and it is queued as §10 item 1.

**R2 and R4 did not fit before this work either.** S142 measured today's
graph at 99.4 % in the reverb regime on arm A. What `DSP4_C2_BQ_GRAPH=1`
bought is R2: six reverbs now fit, at 92.6 %, *with* the whole 890 built.

### 6.4 Memory, both chips — measured from the shipping images' own linker maps

Chip figures are S146's, re-read from arm B's map (`switch-runbook.md` §2.3),
not carried from a prediction. The "after" column is this report's
construction.

| pool | chip 1 now | chip 1 after | chip 2 now (arm B) | chip 2 after | limit |
|---|--:|--:|--:|--:|--:|
| code (VISA SW) | 181,490 — 69.2 % | ~183,500 — 70.0 % | 186,382 — 71.1 % | ~188,400 — 71.9 % | 262,144 B |
| DM data + stack | 309,612 — 82.5 % | ~312,300 — 83.2 % | 328,268 — **87.5 %** | ~333,800 — **88.9 %** | 375,264 B |
| delay lines | 506,880 — 24.5 % | **506,880 — 24.5 %** | 1,886,112 — **91.0 %** | **1,886,112 — 91.0 %** | 2,072,576 B |

**Not one byte of delay pool moves.** The DM claims, itemised:

| chip | claim | bytes |
|---|---|--:|
| 2 | aux matrix crosspoint coefficients + cells (176 cells, ~336 words) | ~1,344 |
| 2 | one-block alignment buffers, 8 × 16 words | 512 |
| 2 | `AuxPick`'s four taps per (group, aux), 128 coefficient words | 512 |
| 2 | six `C2_MIX_FX` nodes (block buffer + coefficients + state) | ~720 |
| 2 | twelve limiter sidechain biquads | ~912 |
| 2 | ping-pong second return leg | ~576 |
| 2 | the reachability guard's adjacency + closure | ~32 |
| 2 | the remaining chip-2 cells' SPI words | ~900 |
| | **chip 2 total, against 46,996 bytes free** | **≈ 5,500** |
| 1 | 384 `AuxPan`/`AuxPanMode` words | 1,536 |
| 1 | `Trim`/`Mtr003`/`AntiClip` words + per-strip state | ~1,150 |
| 1 | `Talk Dest`/`Noise Dest` crosspoint columns | ~120 |
| | **chip 1 total, against 65,652 bytes free** | **≈ 2,800** |
| 1 | `Rta On` as well (measured, arm D) | +6,080 |

**Memory is not what decides this.** Chip 2's DM goes 87.5 → 88.9 %, still
inside the 90 % warn line and with ~41,500 bytes spare; the delay pool does
not move at all. The delay pool remains the thing the *next* feature runs out
of, and §8's lever L4 is the only one that gives any of it back.

---

## 7. Chip 1 — the per-class breakdown, and what it is worth

**A correction first.** The dispatch names *"chip 1 … its signed 84.47 %"*.
84.47 % is **chip 2's** signed driven row (S86 row C); chip 1's is **57.55 %**
on the same row of the same measurement. S142 §9's gap — *"there is no
per-class breakdown of the signed 84.47 % anywhere in the tree"* — is real
and applies to **both** chips; nothing in the tree decomposes either driven
number.

### 7.1 The best breakdown the tree allows

Built by apportioning the **measured** whole-chip total across classes using
the **measured** per-class profile, adjusted for the two switches that landed
after that profile was taken. It is a decomposition of a measured total, not
a re-derivation of it.

Sources: `MW/D32/DSP/dsp4-function-costs.csv` `*_FP` rows (block 8, fused +
paired, per channel, measured 2026-08-29/30); `DSP4_DYN_LUT`'s measured
74.9 % cut to the COMPRESSOR/LIMITER gain computer (284.3 → 123.1 c/sample-
pair, per `shipping.config`); `DSP4_GATE_LINTHR`'s one deleted `_log2q_fx`
call per sample.

| class | share of the strip | share of chip 1 | c/blk apportioned |
|---|--:|--:|--:|
| EQ, 4 band | 24.3 % | 21.4 % | 40,386 |
| GATE | 20.8 % | 18.3 % | 34,526 |
| COMPRESSOR | 15.3 % | 13.5 % | 25,446 |
| HPF/LPF (`FILT`) | 12.3 % | 10.8 % | 20,349 |
| DELAY | 9.1 % | 8.0 % | 15,149 |
| ROUTING / crosspoints | 7.0 % | 6.1 % | 11,537 |
| GAIN + METER | 6.4 % | 5.6 % | 10,602 |
| FADER | 4.2 % | 3.7 % | 6,897 |
| TUBE (bypassed) | 0.6 % | 0.6 % | 1,059 |
| buses, interchip sends, inputs, talkback, noise, test | — | 12.0 % | 22,630 |
| **total (measured)** | | **100 %** | **188,580** |

### 7.2 Its confidence, stated

- **The total is exact** — 57.55 % of 327,680, measured driven on the part
  with zero missed blocks (S86 row C).
- **The shares are ±25 %, and the non-strip 12 % is the weakest row.** It is
  a node-census construction (442 chip-1 nodes, 264 of them strip nodes on a
  D24), not a measurement.
- **The profile is two toolchain generations behind the image.** Summed
  forward naively, the per-class rows predict ~256,000 c/blk for 24 strips at
  block 16 against a measured whole-chip 188,580. The gap is
  `DSP4_SHARED_KERNELS=15`, `DSP4_DYN_INLINE=2` and the inlining rows
  (`DYN_PAIR_INLINED_TOTAL` 315.0 → 247.5 c/sample/channel, worth ~25,900
  c/blk on 24 strips), none of which are in those rows. **This is why the
  table is presented as shares of a measured total and not as absolute
  costs.**
- **Closing it is one bench row**, and it is queued in §10: a per-class
  `sigprofile.sh` sweep on the *signed* configuration at block 16, both
  chips. Until then any per-class chip-1 number in this tree — including this
  table — is an apportionment.

### 7.3 The chip-1 items priced against it

| item | c/blk | class it lands in | % chip 1 |
|---|--:|---|--:|
| `Chan Mtr003` | 1,536 | GAIN + METER (10,602) — a 14 % addition to that class | 0.47 |
| `Chan AntiClip` | 480 | GAIN + METER | 0.15 |
| `Chan Trim` | 0 | folds into GAIN's existing coefficient | 0.00 |
| `Chan AuxPan`/`AuxPanMode` | 0 steady | ROUTING (11,537), control-rate half only | 0.00 |
| `Talk Dest` | 1,524 | the bus fabric (inside the 22,630 non-strip row) | 0.47 |
| `Noise Dest` | 931 | same | 0.28 |
| `Chan InsertPos` | BLOCKED | — | — |
| **total** | **4,471** | | **1.36** |
| `Rta On`, if ruled in | 36,000 | a class of its own, after the chain | **10.99** |

**Chip 1 lands at 58.91 %, or 69.90 % with the RTA.** Against a 42.45-point
margin and a 0.53-point boot spread, chip 1 is not close to anything.

---

## 8. The levers, each with its price

| | lever | worth | what it costs | audio |
|---|---|--:|---|---|
| **L1** | **Put the chip-2 aux mixes on the bus-major live-crosspoint fabric chip 1 already runs.** `DSP4_RTG_FABRIC=1` has been in `shipping.config` since before S142 and chip 1 has run this pattern since S27: each producer publishes a coefficient column, one shared pass loads each bus accumulator once per sample and MACs **only the crosspoints that are live**. Chip 2's aux mixes instead take the generic block wrapper, which stages **every declared source** through its scalar `_buf_` word on **every sample** whether its coefficient is zero or not (S23-5; S144-7 found the same term on `SOURCE_SEL`) | **12.47 points** in the in-use regimes — off-bypass work **56,448 → 15,574 c/blk** at the **measured** 5.29 c/MAC (`FRONTIER_RTG_RESIDUAL`), plus S144-7's own ~1.0 % if `SOURCE_SEL` leaves `_C2_WRAP_TYPES` with it | one generator change. No cell, no address, no delay byte, no wire change. Chip 1's own fabric is the reference implementation | **none** — same MACs, same order, same arithmetic. Chip 1's move to it was bit-exact |
| **L2** | **Teach the pair drivers about followers** (S143 §5.1, S144 §4.4). `gen_bq_pairs_c2` and `_c2_dyn_driver` gather a per-member coefficient symbol a follower does not have — it `.extern`s its master's. A master + follower is the *cheapest possible pair*: one coefficient set, two states, **no per-block gather at all** | **≈ 2.09 points** — `C2_MAIN_GEQ`+`_R` (3,057), `C2_MAIN_XOVER`+`_R` (2,691), `C2_MAIN_AFB`+`_R` (1,095) at the measured 1.72–1.82× in-graph factor | resolve a follower's coefficient symbol to its master's `cid`, plus a `MAIN` entry in `_C2_PAIR_FAMILIES` | none — the pair kernel is bus-word-identical (S20-6) |
| **L3** | Build `Grp AuxPick` as four crosspoints with one live coefficient | **5.62 points** in the in-use regime — but this is **L1 applied**, not a second lever, and it is already inside L1's 12.47; counted once | — | none |
| **L4** | **Product-scope the delay-line allocation.** A D24 runs 8 of the 12 aux `DELAY` nodes (`product_fit.py --census`), but *"a smaller product buys cycles, not memory"* — all twelve 250 ms lines are linked. Allocating the pool at boot from `CFG_AUX_MASK` (`src/mem_pool.asm` is where it would live) returns **4 × 48,000 = 192,000 bytes** | delay pool **91.0 % → 81.7 %**, i.e. four more 250 ms mono lines | boot-time pool allocation; the one-image rule survives because the allocation, not the image, becomes product-aware | none |
| **L5** | `DSP4_TEST_NODES=0` stays 0 in a shipping image | 0.2 % idle / 0.46 % in use (S49) | already the shipping value | — |

**Order of use: L1 first, alone, and before the aux matrix ships — not after
it.** It is worth six times L2, it changes no audio, it is the difference
between R3 at 95.4 % and R3 at 82.9 %, and it is the reason R4 is 97.8 %
rather than 110.3 %. It should be landed and measured on its own, on today's
graph, where its effect is a clean before/after on one driven row; folding it
in alongside the matrix would mean two changes and one number. L2 then takes
R4 to 95.7 %.

**Nothing here requires a feature cut, and GEQ is not touched.** R4 lands
inside the abort line with L1 and L2 and 1.29 points of margin, which is
about two and a half boot spreads. If PW wants more than that, the cheapest
remaining trades are, in order: (a) **cap the simultaneously-live matrix
crosspoints** — the host already computes the reachability graph for §4 and
therefore already knows the count, so a cap costs nothing new and the skin
can say why; (b) rule that six simultaneous Type-3 reverbs and a fully
patched matrix are not a supported combination, and have the host refuse the
sixth reverb while the matrix is heavily patched; (c) take `Fx
PingPongStart` as the two-tap reading rather than as stereo engines (§2.6).
All three are PW's rulings and none is proposed here as a decision.

---

## 9. 🔴 Blocked, and recorded rather than guessed past

**S148-3 — `Chan InsertPos` (24) and `Grp InsertOn` (4) cannot be built, and
the contradiction is in the definitions, not in the graph.**

`Chan001InsertOn001` is classed **`hardware-control`, reason "analogue insert
relay"** — the insert is an analogue break in the mic-pre path, switched by a
relay, and the DSP never sees it. `Chan001InsertPos001` then says *"Channel
insert position: ONE insert with a selectable tap 0=pre-EQ 1=post-EQ
2=post-dynamics 3=pre-fader"* — and every one of those four taps is a point
**inside the DSP strip**, downstream of the ADC.

An analogue relay has exactly one possible position: ahead of the converter.
For `InsertPos` to mean anything the insert must be a **digital** loop — the
strip tapped at the chosen point, sent out a converter, and returned through
another. A D24 does not have that hardware: `shared/dsp4-logic/slot-map.csv`
gives it 16 DAC lanes (every one of which is now assigned) and 24 mic inputs,
and a 24-channel digital insert needs 24 sends and 24 returns.

**Priced anyway, so the number exists:** as a digital loop it is one
`SOURCE_SEL` per strip for the tap (4 sources, ~948 c/blk each by S144's
counted rate) plus an `OUTPUT_TDM` and an `INPUT_TDM` per strip —
**24 × ~1,370 = 32,880 c/blk = 10.0 % of chip 1**, plus 48 converter lanes
that do not exist. That is a hardware question, not a capacity one.

**Two readings for PW:** (a) `InsertPos` describes a *future* product with a
digital insert and is inert on a D24 — in which case it should be classed
`s1-2-no-behaviour` or `hardware-control` alongside `InsertOn`, not
`no-graph-node`; or (b) the D24's insert really is meant to move, in which
case it is a hardware change and the 10 % above is its DSP price. Recorded,
not asked.

**S148-4 — `Fx PingPongStart` has two readings and they are 33 times apart.**
§2.6. Priced at the cheap reading (a two-tap echo, 0.50 %); the expensive
reading (stereo FX engines) is +16.44 points and fits in no regime.

**S148-5 — `Rec Mtr` may belong with the rest of its family.** Every other
`Rec` cell is `mcu-only` or `control-plane`; two DSP meter taps are the only
DSP claim the recorder makes. If the record feed is metered host-side these
two cells cost zero and should be reclassified.

**S148-1 and S148-2** are in §1 and §2.2. All five are in `findings.md`.

---

## 10. What the bench must prove

Queued, not run. Nothing was flashed and the unit was not contacted this
session. In the order that makes each next number worth taking:

1. **The S146 window's own bench row 3** — the driven capacity row on the
   signed arm B, both boots, `build_cfg2` read off the part during the
   measurement. Everything in this report is stacked on a constructed
   ≈ 74.7 %; this is the reading that makes it a number. Pass: within ±1.0
   point, zero missed blocks on every chip-row of every boot.
2. **The bypass row, and it is new (S148-1).** The same driven row with one
   `Fx*AuxOn` opened on one aux, then on all eight. Expect +0.64 % per aux
   and +5.16 % for all eight. This is the measurement that turns §1's
   bypass-exit story from an arithmetic claim into a rate — and it is the
   term the whole in-use column is built on. **Take it before lever L1**, so
   L1 has a before to be an after of.
3. **The per-class chip-1 profile on the signed configuration** — a
   `sigprofile.sh` sweep at block 16, both chips. It closes S142 §9 and
   replaces §7's apportionment with a measurement.
4. **The matrix feed, aligned.** One aux fed into another with the same
   source reaching the destination both ways, swept: with the alignment
   delay the response is flat; without it there is a notch at ≈ 1.5 kHz.
   That is the measurement that proves the alignment is doing what §3.3 says.
5. **The feedback guard, negatively controlled.** Every loop-closing write
   attempted through the bench tools (which go round the host, via
   `landed-d24.json`) and **no signal on the aux**, on every one of the 56
   edges. A guard nobody has seen refuse is not a guard.
6. **The aux pair switched between dual mono and stereo while a tone runs**,
   on a coherent capture — no discontinuity above the noise floor (§5).
7. **The delay pool at 91.0 %** — S144's bench row 12, still owed; the first
   image that asks for 1,886,112 of 2,072,576 bytes.
8. **`Rta On` driven, on chip 1, on the signed configuration.** S65 measured
   +34.4 k on a different lever set; if it is to be ruled in, it should be
   re-measured on the arm that ships.

---

## 11. State left behind

No graph change, no contract change, no `defs.lock` move, no proposal
written. This session prices; it does not build. `proposals/` is untouched
and the cell names in §4.4 are **PROPOSED to PW and to `defs`** and are not
added anywhere in this tree.

The one thing that changed in the tree is the S147-1 rebuild of image arms C
and D under the newly signed default — §12.

---

## 12. S147-1 closed — arms C and D rebuilt and re-priced under the signed default

S147 set `DSP4_C2_BQ_GRAPH=1` in `shipping.config`. Arms C
(`DSP4_TEST_NODES=1`, the factory-test-v3 candidate) and D (`DSP4_RTA=1
DSP4_CUE=1`, bench row 11) never named that switch on their own build lines,
so both inherited the default and both stopped reproducing their S146 md5s.
Rebuilt here and re-priced from their own linker maps.

**Provenance:** HEAD `8c66feea141cf3543d3f094b4566ced042f859e3`, tree clean,
`./check-sharc-codegen-drift.sh` **757 generated / 0 differ / 0 absent /
53 hand-written**.

**Both arms reproduce themselves byte for byte** — each built twice, md5s
identical across the two runs — and **both match the md5s S147 reported**, so
S147-1's numbers are confirmed rather than merely carried forward:

| arm | flags | chip 1 | chip 2 |
|---|---|---|---|
| C | `DSP4_TEST_NODES=1` | `c031613ac9a0a02e4c1d493bea19765d` (433,508 B) | `8674f98fdf2975b974c8fc83430c4240` (451,568 B) |
| C | *superseded, pre-S147 default* | `7f226919a5d181410c3804d92678da19` | `d97645bfb800290b8f998924d939361c` |
| D | `DSP4_RTA=1 DSP4_CUE=1` | `c9bf6659fd888626465932c3814adb5f` (435,432 B) | `edbdb100e7fb60b14e0e5285b156471c` (450,496 B) |
| D | *superseded, pre-S147 default* | `a026897ff6fd33654733f85c077599d6` | `ebf2fea4cca2f740cd560b1155134cc3` |

🔴 **Arm C's chip-1 identity to the staged factory-test-v2 image is BROKEN,
and it is measured rather than assumed.** S146 recorded arm C's `chip1.ldr`
as reproducing the factory-test-v2 chip-1 image already staged on the unit
(`7f226919a5d181410c3804d92678da19`) byte for byte. It no longer does:
today's arm C chip 1 is `c031613a…`. Adopting arm C as factory-test-v3 is
therefore a chip-1 change as well as a chip-2 one, which it was not at S146.

**Capacity, re-priced from each arm's own map** (`tools/dsp/dsp_memreport.py`;
the arm-C chip-2 column re-read independently by this session against
`build_s146_tn/chip2.map.xml`):

| pool | C chip 1 | C chip 2 | D chip 1 | D chip 2 | limit |
|---|--:|--:|--:|--:|--:|
| code (VISA SW) | 187,142 — 71.4 % | 187,862 — 71.7 % | 184,378 — 70.3 % | 186,454 — 71.1 % | 262,144 B |
| DM data + stack | 311,004 — 82.9 % | 328,348 — **87.5 %** | 315,692 — **84.1 %** | 328,684 — **87.6 %** | 375,264 B |
| delay lines | 572,416 — 27.6 % | 1,886,112 — **91.0 %** | 506,880 — 24.5 % | 1,886,112 — **91.0 %** | 2,072,576 B |

The delay pool does not move on any arm — `DSP4_C2_BQ_GRAPH`,
`DSP4_TEST_NODES` and `DSP4_RTA` buy code and DM and never delay, the same
result S146 recorded. Arm C is now the heaviest arm on both chips for code;
arm D is still the only arm that moves chip 1's DM, because the filterbank
and S144's ring metric live there.

`MW/D24/DSP/s146/build-images.sh` carries the new C and D constants (the A
and B rows are untouched) and **all four arms now gate green**: *"every arm
built reproduces its recorded image byte for byte"*, exit 0.
`MW/D24/DSP/s146/switch-runbook.md` is updated at §2.1, §2.2, §2.3, §7
row 11, §8.2 and §9, with the superseded md5s kept visible rather than
deleted.

🔴 **S148-6, and the re-price is what found it: S146's chip-1 figure for arm
C was arm A's figure wearing arm C's label.** `DSP4_TEST_NODES=1` puts the
`TEST_OSC`/`TEST_MEAS` nodes on **chip 1** and not one instruction on chip 2
— `shipping.config` says so at the point of definition — so arm C's chip 1
cannot be arm A's, and §2.3 of the runbook nevertheless grouped *"chip 1,
arms A/B/C"* at one figure of 181,490. Measured off arm C's own map it is
**187,142 / 311,004 / 572,416**: +5,652 bytes of code, +1,392 of DM and
+65,536 of delay line. Nothing gated on it, every arm still fits, and the
record is corrected in place.
