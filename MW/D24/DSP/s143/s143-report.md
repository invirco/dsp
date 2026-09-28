provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S143 — the stereo main bus, the desk proofs, and where the aux matrix stops

Session 143, 2026-09-28, desk only. Hub dispatch `tasks.md` 2026-09-28 12:29Z.
Nothing flashed, no DSP image loaded onto MW-D24-2, no app deploy, **no bench
contact of any kind** — the unit was not connected to this session.

---

## 0. Outcome

| dispatch item | state |
|---|---|
| 1. Main R as a coefficient follower, per S142 §3.1 | 🟢 built, built clean, proved |
| 2. the desk proofs the tree did not have | 🟢 built, three of them, each with a negative control |
| 3a. `CFG_MTX_MASK` 0x3 → 0 on D24 | 🟢 landed, with the drift check that would have caught it |
| 3b. group → aux crosspoints (32 of the 60) | 🟢 built; proposal owed to the hub |
| 3c. aux → aux crosspoints (28 of the 60) | 🔴 **NOT BUILT — S143-2, below** |

**S142-1 is closed.** The chip-2 main bus is stereo from the master fader
to every output: `C2_MAIN_OUT_02` (the MainR XLR, DAC_11 J57) reads the
right bus and nothing else, and a hard-panned strip reads EXACTLY zero at
every one-sided sink on the desk model. It took twelve nodes, no cell, no
SPI address, no dispatch change and **no contract bump**: zero of the 714
existing addresses moved, and `dsp_params.asm`, `spi_handler.asm`,
`ghost_cells.h`, `dsp_address_map.md` and every `MW/*/MX/_matrix.csv` are
byte-identical.

🔴 **S143-2 — THE AUX → AUX MATRIX CANNOT BE BUILT THE WAY S142 §3.4
DESIGNS IT, AND THE REASON IS NOT A DETAIL.** A crosspoint from aux *i*
into aux *j* for every *i* < *j* makes every aux bus reachable from every
lower one, so **no two aux chains can ever be SIMD-paired** — not by
reordering, not by re-pairing. Proved, not argued: §4. It costs 24 pair
drivers, and under `DSP4_C2_BQ_GRAPH=1` that is about three quarters of
the 17-point lever S142's whole capacity case rests on. The group half
(48 crosspoints on the superset, 32 of them D24 cells) has none of this
and is built. §4 gives the two placements that would work and what each
one does to the audio; the choice is PW's.

---

## 1. Item 1 — the stereo main bus

### 1.1 The mechanism

`follows=<master>` in a row's `params` makes that row a **second instance**
of its master's kernel running its master's parameter set: the coefficient
symbols by `.extern`, its own state, its own buffers, its own delay line.
It takes no cell and no SPI address — dsp_codegen and dsp_validate both
refuse one that carries an address — so there is nothing new for a host to
write and nothing for the contract to name. That is D5's "TWO DSP instances
(Main L, Main R) sharing ONE parameter set", built as the general mechanism
rather than as a special case.

Twelve nodes, all chip 2, none with an address:

| node | follows | what it closes |
|---|---|---|
| `C2_MAIN_FDR_R` | `C2_MAIN_FDR` | the master fader was mono |
| `C2_MAIN_GEQ_R` | `C2_MAIN_GEQ` | |
| `C2_MAIN_COMP_R` | `C2_MAIN_COMP` | linked, see §1.2 |
| `C2_MAIN_LIM_R` | `C2_MAIN_LIM` | linked |
| `C2_MAIN_DLY_R` | `C2_MAIN_DLY` | +48,000 bytes of delay line |
| `C2_MAIN_XOVER_R` | `C2_MAIN_XOVER` | feeds `C2_MAIN_OEQ_02` |
| `C2_MON_R` | `C2_MON` (leg R) | `Mon Level[2]` had **no reader at all** |
| `C2_MON_DLY_R` | `C2_MON_DLY` | |
| `C2_CODEC_AUX_IN_R` | `C2_CODEC_AUX_IN` | its R receive was never MAC-ed |
| `C2_PI_IN_R` | `C2_PI_IN` | same |
| `C2_MAIN_ST_OUT_R` | — (own node) | DAC_MAIN_R was never WRITTEN |
| `C2_CODEC_AUX_OUT_R` | — (own node) | CODEC_OUT_4 was never written |

The last two are not followers. They are the other halves of two OUTPUT_TDM
nodes that declared `slot_count=2` off one input — and an OUTPUT_TDM node
writes exactly **one** `_tx_out_slot_` word per sample (the gather copies
`off[i] + sample*stride[i]`, one word per node per frame). The second slot
of each pair had its chip-select bit widened for it and was never written
at all, so DAC MAIN R carried whatever the TX buffer last held. One node is
one slot now.

### 1.2 The three hazards S142 §3.1 wrote down

**1 — crossfade lockstep.** The report specified a latched copy of the
master's bank select, because a follower running after the master would read
`_active_`/`_xfade_alpha_` *after* the master's own body had advanced them.
What is built removes the shared word instead: the follower owns
`_active_`, `_xfade_alpha_`, `_xfade_step_` and `_swap_pending_`, and the
master **kicks** the follower's `_swap_pending_` at the point it commits to
a fade. Both then run the same alpha ramp by the same step over the same
samples from the same state and flip on the same sample. There is no race
because there is nothing shared to race on, and the banks the two select
are the same arrays. Proved and negatively controlled in
`follow_lockstep_check.py` — with a shared `_active_` the follower is 16
samples (one whole block) on the wrong bank.

**2 — linked, not duplicated, dynamics.** The report had the follower read
the master's gain word. That word is per SAMPLE and the two nodes run a
whole block apart, so reading it would have meant a gain BLOCK and a walking
pointer. What is built is exact and needs neither: `link_in=` names the
other leg, **both** legs detect on max(|L|,|R|), and from one parameter set
and one initial envelope they compute the same envelope and the same gain
sample for sample. One gain, two instances, nothing shared per sample.

That costs the two cross-chain SIMD pairs. `_comp_pair_blk` reads one input
block per channel and has no second detector input, so a stereo-linked node
cannot be paired; `MSUB_COMP` and `MSUB_LIM` do not form and all four nodes
(`C2_MAIN_COMP/LIM`, `C2_SUB_COMP/LIM`) fall back to their scalar bodies —
the same path `.c2s_<tag>` already takes when either member is switched off.
The generator says so on stderr, by name and with the reason. It is due to
dissolve anyway: S142 §3.2 deletes `C2_SUB_COMP`, which leaves
`C2_MAIN_COMP` with no partner regardless.

**3 — the pairing groups.** Followers are inserted in ROW order beside
their masters (S23-3's precedent). `c2_pair_groups` accepts the run with no
reorder, and the emitted chain is L, R at every stage:
`MIX_MAIN_L, MIX_MAIN_R, FDR, FDR_R, GEQ, GEQ_R, COMP, COMP_R, LIM, LIM_R,
DLY, DLY_R, XOVER, XOVER_R`.

### 1.3 The gate that would have caught S142-1

`_INPUT_ARITY` states how many of its `inputs` each node type's generator
reads (1 unless the type consumes the list; 2 on a `link_in`-carrying
COMPRESSOR or LIMITER). A row that declares more is a **build error** naming
the defect and the two ways out. And `ch_count` stops being comment text:
on a single-input type it must equal 1 + the number of followers. Both live
in `dsp_codegen.py` and are mirrored in `dsp_validate.py`, with seven
negative controls in `test_dsp_validate.py` (20/20).

The gate found two more instances of S142-1 while it was being landed —
`C2_CODEC_AUX_IN` and `C2_PI_IN`, whose right interchip receives were
received over the fabric, staged into a buffer and MAC-ed by nothing. Both
are fixed here.

**Recorded, not fixed:** `C2_USB_IN` and `C2_BT_IN` are ONE host-written
word each and feed both mix legs, so their `ch_count` is 1 now. A stereo USB
or BT return needs a second host word and a second node, which is a wire
question and not a graph tidy-up. The six FX engines are mono end to end
(the return's own note has said so since S23 gate 2), so theirs is 1 too.

---

## 2. Item 2 — the desk proofs

S142 stopped rather than build Main R for two stated reasons: no desk-side
click-free or ramp prover, and nothing that could tell whether the emitted
code reads what the graph declares. Three tools, each with a negative
control, because a gate nobody has seen fail is not a gate.

### 2.1 `tools/dsp/stereo_split_check.py`

- **gate A** — every declared input must be read by the assembly emitted for
  that node. Run against the tree at `ce3a9d4b` it names S142-1 in its
  first line; against HEAD it passes. One exemption, checked rather than
  assumed: a chip-1 MIX_BUS's 32 per-strip sources are gathered by pointer
  through `rtg_fabric`, and the fabric's own strip count is verified against
  the graph's.
- **gate A2** — every emitted read must be declared on the row. This is what
  licenses gate B: reachability is computed on `dsp.csv`, and that is a
  statement about the IMAGE only if the bodies read exactly what the rows
  say. In-strip pick-off taps (`Chan*AuxPick`) are a named class and must be
  in-strip.
- **gate B** — 55 chip-2 sinks, each against a DECLARED expectation with a
  reason; a sink missing from the table fails. A `link_in=` edge is excluded
  from the cone and reported separately: it modulates a gain and adds no
  sample, so `dry × gain(max(|L|,|R|))` is exactly zero whenever the dry leg
  is.
- `--negative-control` takes one read away and requires gate A to fire.

### 2.2 `dsp_simulate.py --stereo-proof`

The numeric half, and the reason it could not be run before: **the two chips
were not connected in this model at all.** An INTERCHIP_RECV node has no
`inputs`, so every chip-2 node in the simulator read silence. They are
linked now by the mix fabric's own `global_slot` (one block of latency not
modelled, and stated).

Two more corrections the proof needed, both toward the firmware:

- the fader's output is post-fader **mono** and the pan is the BUS
  CROSSPOINT coefficient (the 2026-08-25 fold). The model applied the pan a
  second time once the crosspoints existed, which put a hard-panned strip at
  6e-17 on its LIVE side and hid a zero behind a rounding error;
- a bus sums its sources through the crosspoints its ROUTING row declares,
  not all at unity. At unity every strip reached all twenty-nine buses, so
  the six FX returns fed the main mix a second, unpanned copy of the whole
  desk and a hard-panned strip came back on the far side at 0.74.

With those, the reading the dispatch asked for:

```
  hard LEFT:      C2_MAIN_OUT_02 / _ST_OUT_R / _CODEC_AUX_OUT_R / MON_DLY_R
                  peak = 0, 0 of 16 non-zero samples
  hard RIGHT:     C2_MAIN_OUT_01 / _ST_OUT / _CODEC_AUX_OUT / MON_DLY
                  peak = 0, 0 of 16 non-zero samples
  CENTRE control: MainL 0.221459456, MainR 0.221459456, delta 2.8e-17
```

Zero, not small. The centre control is there because "zero on the far side"
is also satisfied by a graph that has stopped passing audio.

### 2.3 `tools/dsp/follow_lockstep_check.py`

The ramp/click prover, 10/10:

1. the state machine, **block at a time in chain order** (modelling it
   sample-interleaved would understate the hazard by a factor of BLOCK), in
   lockstep at every sample across a coefficient change. The negative
   control is the hazard itself.
2. the audio, on `fixed_ref`'s own biquad through a real 12 dB coefficient
   swap: the two legs bit-identical, and the worst sample-to-sample step
   inside the 576-sample fade (0.1274) below the boosted filter's own worst
   step (0.1299) — no discontinuity. Plus a check that the fade actually
   happened.
3. the emitted code IS that state machine: the master's kick is present, the
   follower owns all four transient words and both state banks and
   `.extern`s — does not redeclare — the coefficient banks.

**What none of this proves**, so the bench list is right: that the SHARC
executes it. Part 3 checks emitted text; the arithmetic is the fixed
reference's. §6 queues the readings that close it.

### 2.4 Found by the new gate, recorded, not fixed

🔴 **S143-1 — all 32 chip-1 channel meters declare a second input that
reaches no instruction.** `C1_MTR_nn` declares
`inputs = C1_GAIN_nn;C1_FDR_nn` and `taps = post_trim;post_fader;gate_gr;
comp_gr`, and `gen_meter_fixed` reads `inputs_str` — `C1_GAIN_nn`,
post-TRIM — and nothing else. The `post_fader` tap is not a second source at
all: it maps to meter word +1 (`Chan[1-32]Mtr002`, `gen_dsp.py`'s tap
table), which is the true RMS of the **same post-trim word**. So the
fader's own meter cell does not follow the fader. Whether `Mtr002` is meant
to be post-fader is a contract question (the master's Notes), and a meter
that changes what it measures is a bench reading; it is chip 1 and not this
dispatch's build. Carried in `_KNOWN_UNREAD` by (consumer, producer) with
the finding that owns it, so the gate is green and the defect stays visible.

---

## 3. Item 3a/3b — what was built

**`CFG_MTX_MASK` 0x3 → 0 on D24.** Verified before changing it: zero
`Matrix*`/`Chan*Matrix*` rows in `MW/D24/MX/_matrix.csv`, in
`defs/products/d24/dsp.csv` and in its `dsp-unmapped.csv` (D16 and D12 zero
too, D32 four). A D24 was calling six chip-2 instances for cells that no
longer exist — `C2_RECV_MTX_01/02`, `C2_MTX_FDR_01/02`, `C2_MTX_OUT_01/02`,
about 840 c/blk by S142's pricing.

The literal lives in `tools/pi/dsp4_config.py`, which runs on the Pi where
the defs submodule is not present, so it cannot notice that the contract
moved — and it did not: the mask sat at 2 for the whole day the cells were
already gone. `product_fit.py --check-masks` now cross-checks all four
products' masks against the matrix buses their own landed `dsp.csv`
addresses, and it was negatively controlled (the stale 0x3 put back → D24
MISMATCH, exit 1).

**The group → aux crosspoints.** `Grp[1-4]AuxSend[1-12]` and
`Grp[1-4]AuxOn[1-12]`: 48 crosspoints on the superset, 32 of them reaching a
D24 cell, which is where the dispatch's count comes from. Not a new fabric —
four more sources of the kind `C2_MIX_AUX_nn` has carried since S23 gate 3,
each an on/off flag and a ramped level folded into one Q4.28 coefficient at
block rate.

- **Addresses:** a SECOND block per node (`xp_page`/`xp_addr`/`xp_map`),
  allocated after every other chip-2 allocation, so the crosspoints ADD 96
  words and MOVE NONE. Same mechanism and the same reason as ROUTING's
  `mtx_page`/`mtx_addr` and OUTPUT_TDM's `mo_page`/`mo_addr`.
- **Order:** the whole GRP chain is spliced ahead of the aux sums, as one
  run. `repair_process_order` would otherwise move each `C2_GRP_COMP_g` on
  its own, splitting the GRP pair family; this is the FX splice again, for
  the same reason.
- **`Grp*AuxPick*` is NOT built and NOT dispatched.** It selects which tap
  of the group strip the send comes from (PreEQ/PostEQ/PreFdr/PostFdr),
  which is a pointer select and not a coefficient. Giving it an address it
  had no reader for is S21-4's shape, so it stays unmapped with its reason
  and the send is taken from the group's OUTPUT.
- **Owed to the hub:** `gen_dsp.py --propose` has written the four products'
  `proposals/defs/products/*/dsp.csv` and `dsp-unmapped.csv` (D24 +64 cells
  mapped, D32 +96, D16 +48, D12 +16). Until the hub lands them and the pin
  advances, `gen_dsp.py` without `--propose` refuses — deliberately, and it
  says why. That is the S139 → S140 shape and it is the only correct path:
  the defs are authoritative and this repo is a consumer.

---

## 4. 🔴 S143-2 — the aux → aux matrix against the aux SIMD pairing

**The claim.** S142 §3.4 says the aux matrix "is not a new fabric… more
sources on `C2_MIX_AUX_nn`", and that "the aux chains already run 1..12 in
row order, so `repair_process_order` has nothing to move and S23-3's pairing
hazard does not arise". The first half is right. The second is not, and the
reason is structural rather than a matter of ordering.

**What the generator says.** Built exactly as designed — the i<j sources
added to `C2_MIX_AUX_j` — `dsp_codegen.py` refuses:

```
ValueError: chip 2 pair family AUX: its 84 nodes are not a contiguous run
of the chain (82..176), so the pair order cannot be built by reordering
that run
```

`C2_MIX_AUX_j` sits before every aux chain (the S23 splice, which is there
so the FX returns publish first), and making it read `C2_AUX_DLY_i` drags
each aux chain forward into the middle of the family.

**And relaxing that check would not help**, which is the part that matters.
Computed over the experiment graph, in both directions, for every pair the
family would form:

| class | pairs the family forms | pairs where one member is reachable from the other |
|---|--:|--:|
| `LIM` | 6 | **6** |
| `EQ` | 6 | **6** |
| `GEQ` | 6 | **6** |
| `AFB` | 6 | **6** |

Two nodes can be SIMD-paired only if neither is reachable from the other —
otherwise one has to run before the other and there is no instant at which
both inputs are ready. With a crosspoint from every aux into every higher
aux, the twelve aux buses are a **total order**, so *every* aux is reachable
from *every* lower one. No pairing of any two aux chains is possible, by
any placement or any re-pairing.

**The price.** In the shipping build (`DSP4_C2_BQ_GRAPH=0`) that is the six
aux LIMITER pairs. Under `DSP4_C2_BQ_GRAPH=1` — the lever S142's whole
capacity case rests on, worth ~17.4 points of chip 2 — it is also the
eighteen biquad pairs, and the aux family is **492 of the 648 paired
cascade stages on chip 2** (aux: 12 × (EQ 4 + GEQ 31 + AFB 6); grp: 4 × (EQ
4 + GEQ 31); mout: 4 × OEQ 4). Three quarters of the lever, or about 13
points, against the 2.16 % the aux matrix was priced at.

**Two placements that would work, and what each does to the audio.** Both
put the matrix sum in a NEW class of the AUX family, `C2_AUX_MTX_j`, so the
aux chains stay pairable and the family run stays contiguous:

| placement | source the crosspoint takes | consequence |
|---|---|---|
| between `LIM` and `DLY` | `C2_AUX_MTX_i`, i.e. aux *i* post-limiter, pre-delay | the matrix contribution gets aux *j*'s DELAY but **not its limiter** — an amp-protection gap; and the cascade is pre-delay, so a matrix feed does not inherit the source aux's own output alignment |
| between `FDR` and `EQ` | would have to be `C2_AUX_MTX_i` near the START of chain *i* | the contribution gets aux *j*'s EQ, GEQ, AFB, limiter and delay — the safe one — but the SOURCE is then aux *i*'s pre-EQ mix, not its output, which is not what `Aux{i}AuxSend{j}` means |

Both checked against `_C2_PAIR_FAMILIES`' two contiguity rules: `MTX` after
`LIM` or before `EQ` leaves the paired class spans `{EQ,GEQ,AFB}` and
`{EQ,GEQ,AFB,LIM}` intact; between `AFB` and `LIM` it does not.

**A third option, named so it is not re-invented:** keep the sources on
`C2_MIX_AUX_j` and read aux *i*'s output ONE BLOCK OLD. That is not the
"snapshot" S142 §3.4 rejected — the rejection was of the full square with a
snapshot, where a loop with round-trip gain ≥ 1 still diverges; with the
i<j order there is no loop to begin with and the delay is bounded. It costs
nothing and it keeps every pair. What it costs is 333 µs on the matrix feed,
which comb-filters against any direct path at about a 3 kHz spacing — real,
and a PW question rather than a desk one.

**Not built, deliberately.** Choosing between three placements that each
change where a matrix feed sits relative to a limiter is a ruling, not an
implementation, and the alternative — building one and finding out on the
part — is the failure mode this repo's rules exist to stop. The 28 D24
aux→aux crosspoints are the only part of this dispatch not delivered.

---

## 5. Capacity

Measured on the part? No — desk only, and the driven row is a bench item.
What is measured here is the linker's own report, on the same
`shipping.config` build as S142's baseline.

| chip 2 pool | S142 baseline | S143 item 1 | S143 item 3 | limit |
|---|--:|--:|--:|--:|
| code (VISA SW) | 58.5 % | 60.0 % | **61.6 %** | 262,144 B |
| DM data + stack | 77.1 % | 77.9 % | **78.2 %** | 375,264 B |
| delay lines | 81.7 % | 86.4 % | **86.4 %** | 2,072,576 B |

Both builds are clean two-chip builds (CCES 3.0.3, `shipping.config`,
exit 0), each into a scratch directory outside the tree.

The delay pool moves once and only once: **+96,000 bytes**, the two new
250 ms mono lines (`C2_MAIN_DLY_R`, `C2_MON_DLY_R`), leaving 282,464 bytes
free. S142 priced one line at +48,000; the monitor's second leg is the other
one, and it is spent on a chain that today reaches no connector (S122) and
that S142 §3.3 item 2 gives an output to.

Chip-2 SPI words: 2,183 → 2,281. **98 added, 0 moved** — two for the
right-hand stereo outputs and 96 for the group → aux crosspoints.

**Cycles.** The group crosspoints are priced by construction, not by the
pricing document's 5.29 c/MAC bus-major rate — that rate is for a fabric
that was not built, because §3.4's own text says "more sources on
`C2_MIX_AUX_nn`" and that is what was built:

- **always**, whatever the desk is doing: the block-rate send fold grows
  from 6 to 10 iterations on each of twelve nodes. The emitted loop body is
  23 instructions, so 4 × 23 × 12 = **1,104 c/blk = 0.34 %** of chip 2's
  327,680 at BLOCK 16 / 983.04 MHz.
- **proportional to use**: with every group send off — the shipping default
  — the aux sum still takes the S23 bypass (the OR of every switched
  coefficient is zero, the one plain gain is exactly 1.0f, the node copies
  its input block and returns), so the four new sources cost nothing else
  at all. A desk that opens a group send on an aux puts THAT aux's sum on
  the full path for the block. S23-5 measured the full path at 7 sources;
  at 11 it has not been measured and is a bench row.
- `CFG_MTX_MASK` 0x3 → 0 gives **−840 c/blk** back on a D24.

So on the Echo default the whole of item 3 as built is about
**+0.34 % − 0.26 % ≈ +0.08 %** of chip 2, and item 1 is S142's priced
+2.69 % (constructed, not measured). The driven row on the part is queued.

### 5.1 Priced both ways

`DSP4_C2_BQ_GRAPH` was NOT touched — it is a PW signature and it is asked
separately. Both arms:

**With it at 0 (the shipping config, what everything above is measured on):**
item 1 is S142's priced +2.69 %, item 3 as built is +0.34 % − 0.26 %, and
the two cross-chain dynamics pairs that no longer form come off the top.

**With it at 1:** the lever is worth ~17.4 points, and S142's note that
*"the two main GEQs and the two crossovers become exactly the adjacent pair
that lever pairs"* is **not true of what is built, and is worth correcting
before someone prices against it.** A follower cannot be SIMD-paired today,
its master included: `gen_bq_pairs_c2` and `_c2_dyn_driver` gather
`_<pfx>_coeffs_A_<node>` and `_<pfx>_attq_<node>` per member, and a
follower has no such symbol — it `.extern`s its master's. So `C2_MAIN_GEQ`
+ `C2_MAIN_GEQ_R` and `C2_MAIN_XOVER` + `C2_MAIN_XOVER_R` run as four
scalar nodes in both arms.

That is a **not taught yet**, not an impossibility, and it is the most
attractive pairing on the chip: a master and its follower are one
coefficient set and two states, which is precisely the shape the native
interleave wants — no per-block coefficient gather at all, because the two
channels' coefficients are the same words. Closing it needs the drivers to
resolve a follower's coefficient symbol to its master's (the `cid` the node
generator already uses) plus a `MAIN` entry in `_C2_PAIR_FAMILIES`. Out of
this dispatch's scope; the exclusion says so where it is made
(`_c2_pair_excluded`).

And the aux matrix's price in the `=1` arm is §4's: about 13 of the 17.4
points, which is the number the ruling should be taken against.

---

## 6. What the bench must prove

Queued, not run. Nothing was flashed and the unit was not contacted.

1. **The L/R capture.** A tone into a strip panned hard left; meters on J56
   (`DAC_12`, MainL) and J57 (`DAC_11`, MainR). The desk says J57 reads
   digital zero and J56 reads the tone, and that the two swap with the pan.
   The desk has been wrong about this hardware before — `DAC_13` was "Main
   Out 1" for months and is connected to nothing — so this is a reading.
2. **The monitor pair**, same shape, on whichever connector the monitor bus
   lands on once S142 §3.3 item 2 gives it one.
3. **The click check on a live crossover change.** Write `Main
   CrossoverFreq` while a tone runs and capture both MAIN XLRs across the
   576-sample fade: no step, and the two legs' fades coincident. This is the
   one thing `follow_lockstep_check.py` cannot do — it checks the emitted
   text and the reference arithmetic, not the part.
4. **The capacity row on the part**, driven, at the signed pairing
   configuration: item 1's +2.69 % and item 3's +0.08 % against S86's
   measured 84.47 %, and the two cross-chain pairs that no longer form.
5. **A group send opened**, one aux at a time, to measure what leaving the
   S23 bypass costs at 11 sources.

---

## 7. State left behind

`main` carries four commits: item 1 (the stereo main bus), item 2 (the desk
proofs), item 3 (the matrix mask and the group crosspoints), and this
report. `defs.lock` is untouched. `proposals/defs/products/*/` carry the
group → aux mapping and are **owed to the hub**; until they land,
`gen_dsp.py` without `--propose` refuses and `MW/*/MX/_matrix.csv` stays at
its previous backfill — the S139 → S140 shape, deliberately and with the
generator saying so.

No flashing, no app deploy, no bench contact.
