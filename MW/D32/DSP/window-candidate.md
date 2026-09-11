provenance: AI-drafted 2026-09-10 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The window candidate, in one place

**What this is.** The DSP configuration proposed for the rev C reconciliation
window, every bar run on it, and the numeric deviations PW is being asked to
sign — in one document, rather than spread across
`dsp4-window-readiness-20260909.md`'s eight addenda. Every figure was
measured on the rev C bench in session S27 (2026-09-10/11) unless a line says
otherwise.

**THERE ARE NOW TWO CANDIDATES, AND THE SIGN-OFF IS ONE WORD (added
2026-09-11, S33).** §1–§4 are **candidate A**, `shipping.config.s26`. **§5 is
candidate B**, `shipping.config.s32` — candidate A plus one effective line —
which seats D32's twelfth aux and carries the same evidence set, with two
gaps named in §5.5. Both are proposals; neither is deployed. The two words
are **"sign off s26"** and **"sign off s32"**, and §5.6 says what each
commits to.

**CORRECTED 2026-09-11 (S36-2). The paragraph below was wrong about two
bars, and they are two of the headline ones.** The latency figure and every
DRIVEN capacity row were NOT measured with `a1f6672af6c3` on the part — they
could not have been. The part carried it before and after those sessions, not
during:

* **the 82-sample latency figure (S29, n=3)** was measured on
  `dsp4_logic_maincap.d903ae1ac4a9` against a `dsp4_logic_pisel` reference.
  `maincap` carries `3152e2b1`'s RTL — **all 404 logic elements**, rebuilt and
  confirmed. On `a1f6672af6c3` `pcm_din` is tied to `1'b0` and there is no
  capture path at all, so that arm cannot run on the shipping bitstream; that
  is why `loadlogic.sh` exists.
* **every driven capacity row** — §2.1, the `100.82 %` D32 worst-use figure,
  the S28/S31 product rows — was measured on
  `dsp4_logic_driveall.e13b5dec84e0`.

**Neither figure moves, and the latency one is still sound**: `dsp4_clkgen.v`
is byte-identical between `a4ee3d1f` and `main`, the Pi → DSPA transmit path
is cycle-for-cycle identical in the shipping configuration, and S29's
differential cancels the Pi-side framing exactly (both arms are the same
commit with `CAP_EXTRA_DELAY = 0`). So the DSP's contribution is what was
measured and it transfers to the shipping part. The claim that has to change
is "measured with `a1f6672af6c3` on the part", not the number. Proof:
`MW/D24/DSP/dsp4-s36-20260911.md` §2.

**Everything else in this document genuinely was taken with `a1f6672af6c3` on
the part** — `famverify`, `busgold`, `goldnode`, the numeric arms, the gate-4
flip, the silent capacity rows — and none of it is affected.

**THE BITSTREAM EVERY FIGURE HERE ASSUMES (added 2026-09-11, S35).** All of
it — both candidates, every bar, the 82-sample latency figure — was measured
with the LOGIC CPLD carrying `dsp4_logic.a1f6672af6c3`, and **that is still
what is on the unit**: S35 was dispatched to flash the converter-clock fix
and did not, because the flash interlock (`AN_EN` low) is not meetable while
`matrix-app` runs — the app asserts AN_EN at every boot (finding S35-1).

Two things follow for these candidates. First, **nothing in this document
moves**; the bench is on the same bitstream it has always been on. Second,
when the fix is flashed it should be flashed as `dsp4_logic.138dba7274d6` —
the shipping design plus the pin change and nothing else, 157 → 157 logic
elements — and **not** as the branch, because the branch also carries main's
404 LEs against the part's 157 and would change the logic under these figures
by far more than the fix does (finding S35-3). Working:
`MW/D24/DSP/dsp4-s35-20260911.md`.

**What it is not.** It is not a deploy. `shipping.config` is unchanged and
stays unchanged until PW rules.

---

## 1. The candidate

| | |
|---|---|
| configuration | **`MW/D32/DSP/SHARC/shipping.config.s26`** |
| differs from `shipping.config.s21` in | **one line**: `DSP4_SHARED_KERNELS` 3 → 15 |
| differs from `shipping.config` (today's) in | the six switches s21 names, plus that one |
| `chip1.ldr` | **`6396187c`** (425,668 bytes; the control is 483,740) |
| `chip2.ldr` | **`9222c2ee`** — byte-identical to the s21, s24 and s25 pairs |
| staged on the bench as | **`s26_chip1.ldr` / `s26_chip2.ldr`** |
| rollback pair | `s21_*` = `81f799f9` / `11366344`, staged and untouched |

**What the one line does.** `DSP4_SHARED_KERNELS` is a class mask: each named
class's 32 per-strip node bodies become a two-instruction stub that puts that
strip's record base in `i7` and jumps to ONE shared body. Mask 3 is COMP and
TUBE (S18/S21); mask 15 adds GATE and FILT (S26). It changes the code
LAYOUT of chip 1 and nothing else — not the graph, not an address, not a
coefficient, not a cell.

**What it buys.** Chip 1's code pool goes from **239,422 of 262,144 bytes
(91.3 %, 22,722 free) to 181,350 (69.2 %, 80,794 free)** — 58,072 bytes
recovered, the pool's over-90 % warning gone, and R6–R11 (the matrix as
composite rows, the FX topology) given somewhere to land. The 22,722 bytes
s21 left is about twenty-one GATE instances' worth of code for all of the
remaining topology.

**What it costs.** Nothing measurable. §2's ladder priced it driven, on both
products, both chips, two boots, with and without the plugin load.

**ADDED 2026-09-11 (S28). This candidate now carries the whole range, and the
other two products fit with room.** The same image — `6396187c` / `9222c2ee`,
rebuilt byte for byte — was driven as a **D16** and a **D12** on the rev C
unit, two boots each, four rows each, the regime proved on every driven row:

| product | driven with the load, chip 1 | chip 2 | missed blocks |
|---|--:|--:|--:|
| D12 | 33.26 % | 66.59 % | **0** |
| D16 | 41.69 % | 73.02 % | **0** |
| D24 | 60.05 % | 84.64 % | **0** |
| D32 | 79.16 % | **100.82 %** | **1,943 of 270,000** |

D16 and D12 need no firmware, no address and no cell of their own: their cell
sets are strict subsets of D24's and every cell lands at the address the
shared map already gives it. They are the same image and two different config
words. Full working, and the three D32 variants that have no definition to
generate from, in `MW/D32/DSP/dsp4-s28-20260911.md`; the machine-readable
table is `MW/D32/DSP/fit-table.csv`. **D32 chip 2's row is unchanged — it is
still the one that does not fit at worst use, and §2.1's numbers reproduced
to the block on a second night.**

---

## 2. Every bar, run this session

| bar | where | result |
|---|---|---|
| golden harness | desk | **59 / 59 passed**, no golden moved |
| `dsp_validate` | desk | **OK on 698 nodes**, the same four pre-existing process-order notes |
| `shared_kernel_check` record layout | build | **COMP / FILT / GATE / TUBE all OK** — every field at base + the emitted offset |
| `shared_kernel_check --entries` | build | **256 stubs, each loading its own record base, OK** |
| `cfgverify.sh` | part, both chips | `0xCF45FF10,0xC2019E6F` — **the part matches `shipping.config.s26` to the bit** (and see §3.4) |
| `busgold` | part | **sha256 `4126c00730a31f5f`** — the same 256 main-bus words as the s21 control, twice, on two boots |
| `goldnode` GATE | part | **impulse 64 of 64 bit-exact**, negative control fires on exactly the 2 predicted vectors |
| `goldnode` TUBE | part | **96 of 96 bit-exact** on both stimuli, both negative controls firing as predicted |
| `famverify` D24 | part, proposal map | **0 of 25 families differ** against S25's D24 report — verdict for verdict |
| `famverify` D32 | part, proposal map | 25 families, contract N/N on every one; one verdict moves against the PRE-R5 D32 golden and it is R5's (§3.3) |
| capacity, D32 and D24 | part | §2.1 |
| latency | part | **NOT MEASURED** — see below |

**The latency bar did not produce a number, and it is the one gap in this
set.** It was attempted properly: the bench was flipped to the duplex PCM
overlay, the `maincap` bitstream was flashed, and both were positively
identified on the part (`dsp4_logic_id.py` read `pi_maincap` / `ae1ac4a9`
through that capture path). The arm still returns **0.0 % coherent on every
rep** — S11-6's and S12-10's signature — and `dsp4_dsp_latency.py` refuses
the verdict rather than reporting the flat field as a latency. The DSP's own
main chain reads a constant `0xfffffffc` from MIX through ST_OUT, so nothing
is reaching its input: the break is upstream of the DSP on the playback side
of the loop, and it is a bench bring-up of unknown shape.
**The through-DSP contract figure therefore stands where S20 measured it, 82
samples / 1.708 ms at block 16.** This candidate cannot have moved it —
latency is set by the block size and `DSP4_TX_EARLY`, and `cfgverify` read
both off the part (`BLOCK 16`, `DSP4_TX_EARLY 2`), identical to the control —
but that is an argument, not a measurement, and it is offered as one.

Two bars fail on the candidate and **both fail identically on the s21 control
measured in the same tree, to the digit**: COMPRESSOR's numeric arm (the
reference model is the polynomial path, the part is the LUT — 0.00518 dB) and
FADER_PAN's (S25-6, the stale pan model). `MW/D32/DSP/dsp4-s27-20260910.md`
§2.1 has the evidence for both.

### 2.1 Capacity, driven, with and without the plugin load

`capacity.sh --driven` on the `driveall` LOGIC bitstream with the CM4
playing, `DSP_LANDED_DIR=proposals/defs/products`, two boots per product,
four rows per boot, the regime PROVED on both chips before every driven row
(64 of 64 chip-1 envelopes live, 32 of 32 chip-2, 6 of 6 FX engines at Type 3
with 6 of 6 comb lines carrying signal). Figures are % of the per-block
budget at the MEASURED clock (983.04 MHz, read off the part on every row).

**D32** — average % of budget, and the worst block (S21-6 corrected), mean of two boots; Δ against the control.

| row | arm | chip 1 avg | chip 1 worst | chip 2 avg | chip 2 worst |
|---|---|--:|--:|--:|--:|
| A silent, default | control (COMP, TUBE) | 65.14 | 65.38 | 76.00 | 76.22 |
|  | + GATE | — | — | — | — |
|  | + FILT | — | — | — | — |
|  | **+ GATE, FILT** | 65.38 (+0.23) | 65.46 (+0.08) | 76.09 (+0.09) | 76.38 (+0.15) |
| B silent, load | control (COMP, TUBE) | 78.96 | 79.16 | 100.77 **OVR 1914** | 101.06 |
|  | + GATE | — | — | — | — |
|  | + FILT | — | — | — | — |
|  | **+ GATE, FILT** | 79.07 (+0.11) | 79.26 (+0.10) | 100.88 (+0.11) **OVR 1914** | 101.14 (+0.08) |
| D driven, FX off | control (COMP, TUBE) | 79.23 | 79.52 | 80.56 | 80.90 |
|  | + GATE | — | — | — | — |
|  | + FILT | — | — | — | — |
|  | **+ GATE, FILT** | 79.02 (-0.21) | 79.78 (+0.26) | 80.67 (+0.11) | 81.00 (+0.09) |
| C driven, six reverbs | control (COMP, TUBE) | 78.98 | 79.34 | 100.75 **OVR 1943** | 101.25 |
|  | + GATE | — | — | — | — |
|  | + FILT | — | — | — | — |
|  | **+ GATE, FILT** | 79.16 (+0.18) | 79.50 (+0.16) | 100.81 (+0.06) **OVR 1944** | 101.14 (-0.11) |

**D24** — average % of budget, and the worst block (S21-6 corrected), mean of two boots; Δ against the control.

| row | arm | chip 1 avg | chip 1 worst | chip 2 avg | chip 2 worst |
|---|---|--:|--:|--:|--:|
| A silent, default | control (COMP, TUBE) | 50.63 | 50.83 | 63.16 | 63.41 |
|  | + GATE | — | — | — | — |
|  | + FILT | — | — | — | — |
|  | **+ GATE, FILT** | 50.72 (+0.08) | 50.97 (+0.14) | 63.02 (-0.14) | 63.37 (-0.04) |
| B silent, load | control (COMP, TUBE) | 59.78 | 60.16 | 84.63 | 84.63 |
|  | + GATE | — | — | — | — |
|  | + FILT | — | — | — | — |
|  | **+ GATE, FILT** | 59.97 (+0.18) | 60.12 (-0.03) | 84.64 (+0.01) | 84.81 (+0.17) |
| D driven, FX off | control (COMP, TUBE) | 59.72 | 60.05 | 64.54 | 64.75 |
|  | + GATE | — | — | — | — |
|  | + FILT | — | — | — | — |
|  | **+ GATE, FILT** | 59.91 (+0.19) | 60.27 (+0.22) | 64.38 (-0.16) | 64.61 (-0.14) |
| C driven, six reverbs | control (COMP, TUBE) | 59.91 | 60.29 | 84.47 | 84.66 |
|  | + GATE | — | — | — | — |
|  | + FILT | — | — | — | — |
|  | **+ GATE, FILT** | 59.82 (-0.09) | 60.18 (-0.11) | 84.37 (-0.11) | 84.73 (+0.07) |

**The candidate costs nothing.** Every delta on both products, all four rows,
both chips is within ±0.26 points, which is the size of the instrument's own
resolution — measured, not asserted: `chip2.ldr` is byte-identical in the two
arms, so its deltas are the same binary compared with itself.
`MW/D32/DSP/dsp4-s27-20260910.md` §1 has the four-arm ladder that prices GATE
and FILT separately, with the same answer for each.

**The control reproduces the record**, which is what says the instrument has
not drifted: D32 driven with the load reads 78.98 / 100.75 against S25's
78.97 / 100.75, and D24 59.91 / 84.47 against S25's 59.74 / 84.49.

**One row is over budget and it is not this candidate's doing.** On D32,
chip 2 reads 100.75–100.88 % with 0.72 % of blocks missed on rows B and C —
on the CONTROL as much as on the candidate, which drop 1,943 and 1,944 blocks
respectively out of 270,000. This is S24's finding: *D32 chip 2 does not fit
at worst use*, and worst use is what `--mode load` writes — every bus assign
and every send on every family open at once, which is not the product's
operating point. S24 priced the cause: 9.77 points for one FX return opened
into all twelve aux buses, because an aux bus with a live send loses its
block-level bypass. **How many aux buses D32 can afford is a product
question and it is still open.** D24 has sixteen points of margin on the same
rows.

**The plugin load is twenty points of chip 2** (D32 80.6 % → 100.8 %,
D24 64.5 % → 84.4 %), unchanged by this candidate.

---

## 3. The deviations PW must sign

Three, and only the first two are audio. None of them is new in this
candidate — they are s21's, and they are listed here because this is the
document PW signs from.

### 3.1 The dynamics table: 0.0950 dB against a 0.1 dB bound

`DSP4_DYN_LUT` bakes the compressor's and limiter's whole static curve —
threshold, ratio, knee, ceiling — into a per-node table, so the per-sample
gain computer is an index, two words and an interpolation instead of a
polynomial log2, the knee arithmetic and a polynomial exp2. Worst-case
accuracy over the whole documented parameter sweep is **0.0950 dB** against
PW's ruling of 2026-09-09 that 0.1 dB is the bound.
`tools/dsp/dyn_lut_design.py` produces that number rather than remembering
it. It costs 337 words of DM per COMPRESSOR and LIMITER node at the shipped
K = 4.

**This is the switch that makes the product fit under load.** Driven minus
silent on the shipping default is +42.5 points on chip 1 and +29.3 on chip 2
at D24; with this switch on it is +1.0 and 0.0.

**To sign:** the compressor and limiter are within 0.0950 dB of their
specified curve, not exact.

### 3.2 The gate's threshold: 0.0002 dB

`DSP4_GATE_LINTHR` compares the gate's threshold in the LINEAR domain instead
of log2, which deletes a `_log2q_fx` call per sample and 54 % of the gate
body. It shifts the gate's effective threshold by **at most 0.0002 dB**.

**To sign:** the gate opens and closes within 0.0002 dB of its set threshold.

### 3.3 What S26's rounding floors add: NOTHING PRODUCT-VISIBLE

S26 swept every float→fixed conversion in the tree and found 42 of 48 sites
exposed by one LSB below an exactness floor. Two of those floors sit inside
ORDINARY operating ranges rather than in a corner, which is why S26 named
them — and the question this document has to answer is whether either is
visible in the product. **Neither is**, and the arithmetic says so:

| floor | where it bites | the error one LSB actually is |
|---|---|---|
| Q6.25 log2, floor 0.25 log2 units = **1.505 dB** | any threshold or knee set within ±1.5 dB of zero | 2⁻²⁵ log2 units = **1.8 × 10⁻⁷ dB** |
| soft-knee half, effective scale 2,786,635.25, floor **3.01 dB** | every soft-knee width below 3.01 dB, i.e. every ordinary one — it is rounded three times, not once | 1 / 2,786,635.25 dB = **3.6 × 10⁻⁷ dB** per rounding, so **≤ 1.1 × 10⁻⁶ dB** for all three |

**The floor names the range where rounding HAPPENS, not the size of the
error.** A threshold set at −0.5 dB is below the floor and does round; what
it rounds by is under a ten-millionth of a decibel — five orders of magnitude
below the dynamics table's own 0.0950 dB deviation in §3.1, and six below
anything a specification in this product states. The **±1.5 dB
threshold/knee floor is NOT product-visible** and does not need a ruling.

**Nothing else S26 added is a deviation at all.** The shared kernels are the
same emitter's output rewritten from absolute per-node addresses to record
offsets, and the audio is bit-identical on the part: `busgold` reads the same
sha256 from different chip-1 code, and `goldnode`'s GATE arm is 64 of 64
bit-exact.

### 3.4 One thing to know that is not a deviation: the part cannot name this configuration

`DIAG_BUILD_CFG2` has room for two bits of `DSP4_SHARED_KERNELS` (bit 0 =
COMP at word bit 5, bit 1 = TUBE at word bit 15) and the mask now has four.
**`shipping.config.s21` (mask 3) and `shipping.config.s26` (mask 15) produce
the SAME two config words**, so `cfgverify`'s "the part matches
shipping.config.s26 to the bit" is true and does not distinguish the
candidate from the control. Both `tools/dsp/cfg_words.py` and the bench
decoder now print that caveat beside the pass. **Until the word is widened,
a shared-kernel arm is identified by its image md5** — `6396187c` is the
candidate and `c9d0e07b` is the control. Widening it moves
`DIAG_BUILD_CFG2` on every image, including every md5 quoted here, so it was
deliberately not done inside the window.

**CORRECTED 2026-09-11 (S28-5).** This paragraph used to end *"Free bits
exist (word 2 bits 24 and 26–29)"*. They do not: those are the zero bits of
the word's own `0xC2` SIGNATURE, and bit 24 is exactly what would tell a
`0xC2` word from a `0xC3` one. Every one of `DIAG_BUILD_CFG2`'s 32 bits has
an owner. The fix is therefore a THIRD word, `DIAG_BUILD_CFG3` — designed,
with the bit map and the four-edit apply step, in
`MW/D32/DSP/dsp4-s28-20260911.md` §3, and computable today with
`cfg_words.py --design-cfg3`: this candidate would read **`0xC3000FFA`**
where the s21 control reads **`0xC30003FA`**. Still not applied, and for the
same reason: the word has to exist in the image to be read out of it, so
every md5 quoted in this document moves on the first rebuild after it
lands.

---

## 4. What changes for the app, H1S3 and H1S4

**Nothing.** They rebuild against nothing new.

* `defs` and `defs.lock` are unchanged; the pin is still `defs-v2026.09.08.4`.
* No cell is added, removed or renamed. `MW/D32/MX/_matrix.csv` and
  `MW/D24/MX/_matrix.csv` are unchanged.
* **Not one landed SPI address moves.** The address map is generated from the
  contract, not from the link map, and this candidate changes only which
  chip-1 code bodies exist.
* `ghost_cells.h`, `mx_dsp_map.h` and the panel MCU headers are unchanged
  from the s21 candidate the window already plans to deploy.
* `chip2.ldr` is byte-identical to the s21 pair's, so chip 2 is not
  redeployed at all.

The window's artifact list is therefore exactly what it was for s21, with
`chip1.ldr` reading `6396187c` instead of `81f799f9`.

---

## 4a. ADDED 2026-09-11 (S29) — what D32's worst-use row is actually paying for

**The 100.8 % is the snake, and the snake is the product.** S28 found that
D32's extra cost over D24 is not its strips or its aux buses but **scope
class 0** — the 32 nodes only a D32 boots. S29 weighed the class on the part,
on THIS candidate, as one config word on one image:

| | chip 1 | chip 2 |
|---|--:|--:|
| scope class 0 costs | **0.22–0.61 points** | **3.43–3.69 points** |

Flat across six regimes (silent, loaded, driven FX-off, driven with six
reverbs, every crosspoint closed, every crosspoint open), two boots an arm,
against an instrument resolution of ±0.27 points. **Every D32 row that
overruns with the class on runs with ZERO missed blocks without it** —
1,912 / 1,943 / 1,943 become 0 / 0 / 0.

**PW is not being offered a switch.** Scope class 0 is the D32R stage-box
digital snake: `io.snake,1` in the product definition, a lane in the CPLD
(`A_I5`, selected by `strap_d32`), and **sixteen cells on the gated
contract** — `Snk[1-8]On[1-1]` and `Snk[1-8]Level[1-1]`, mode `rw`, eight
channels of snake return into the main bus with their own level and on/off.
A D32 without it is a D32 without its stage box. **So the worst-use finding
stands exactly as §2 states it: 100.81 % with 1,943 of 270,000 blocks missed
(0.72 %) at twelve auxes fed.**

**What this changes is where to look next, not what to sign.** Chip 2 misses
fitting by 0.81 points and the snake costs 3.43 — and the expensive half is
eight `AUX_INPUT` nodes that are SWITCHED OFF (`on=0`) while they cost it,
because the price is being CALLED, not doing work. That is S23-5/S24's
block-level-bypass finding one node class down, and skipping an AUX_INPUT
whose `on` is 0 is the obvious lever. **It is not taken inside the window**:
it changes the shipping image. See `MW/D32/DSP/dsp4-s29-20260911.md` §2.5.

**The latency figure in §2 is now MEASURED on this candidate.** S29 found the
through-DSP latency arm's seven-session null (S12-10, S27-7) and it was the
duplex PCM overlay, not the DSP — the playback chain is live end to end under
the standing slave overlay, proved stage by stage. On `maincap`, three boots
× twenty reps, **100.0 % coherent on all 60 reps**, against the `pisel`
CPLD-loop reference: **82 / 82 / 81 samples, 1.708 / 1.708 / 1.688 ms.** The
82-sample contract figure was S20's and carried on an argument; it is this
candidate's own number now.

**Nothing else moved.** No cell, no address, no config word, no `defs` pin,
no staged pair, and `shipping.config`/`.s21`/`.s26` are unchanged.

## 4b. ADDED 2026-09-11 (S32) — the lead of §4a, measured: the twelfth aux fits

**§4a left a lever and S32 weighed it. Bypassing the aux inputs that are
switched OFF returns 4.8–5.2 points of chip 2, and every D32 row that
overruns runs clean without them.** One build flag
(`DSP4_AUXIN_BYPASS`), one non-shipping pair (`s32_*`), both arms measured
on the same night with the same instrument:

| row | the candidate (s26) | + the bypass (s32) | missed blocks |
|---|--:|--:|---|
| B silent, loaded | **100.84 %** | **95.64 %** | **949 → 0** |
| use 6:32, WORST USE | **100.85 %** | **95.69 %** | **950 → 0** |
| A silent, default | 75.92 % | 71.08 % | 0 → 0 |

Chip 1 does not move: it has no node of the class, and its image is
byte-identical in both arms (`6396187c`).

**It is TWELVE nodes, not the eight §4a named** — `C2_SNK_IN_01..08` plus the
codec, Pi, USB and BT feeds. None of them is scoped to a product, all of them
boot `on = 0`, and no capacity row this programme has taken turns any of them
on. The price was being CALLED, and it is 0.4 points a node.

**What PW is being asked, and what is NOT being asked.** Nothing about the
snake moves: the sixteen `Snk[1-8]On/Level` cells are written and read
exactly as before, and a snake return that is switched ON costs what it costs
today — S32 gate 4 flipped four of them on the part and they pass their input
at unity on the block their cell lands, and publish exact silence when it
goes back. What changes is that a switched-OFF aux input stops being called.

**It is not in this candidate — it is now candidate B (§5).** S33 took the
lead through candidate A's whole discipline and it is a signed-off-able
configuration of its own. `shipping.config.s26` does not carry the
flag; `shipping.config`, `.s21` and `.s26` are unchanged, no staged pair was
replaced, and the arm is `~/dspboot/s32_*`. Taking it into the window is PW's
call and it needs the audio bar this candidate carries (famverify and the
numeric arms), which S32 did not re-run — its audio evidence is the gate-4
flip and the fact that the park writes the same zeros the body would.

**One thing to know before it ships**: the park leaves `_auxin_q_` holding
its last coefficient while the node is off (S32-3). It is inert — the sample
path never runs with a stale `q` — and the fix is one instruction, named in
the finding and deliberately not made in the session that measured the image.

**Read S32's rows with this caveat**: the `driveall` bitstream was NOT loaded
(the session was told not to reflash the CPLD with the analog board possibly
attached), so both arms ran with the CM4's playback on one lane. Rows A and B
are stimulus-stopped rows and are directly comparable to §4a's; the rows with
the stimulus on are a partial regime in BOTH arms and are labelled as such in
`MW/D32/DSP/dsp4-s32-20260911.md`.

## 5. Candidate B — `shipping.config.s32`, prepared 2026-09-11 (S33)

**Read §1–§4b first. Everything in them is true of candidate B as well**,
because candidate B *is* candidate A plus one line — and that is the point of
this section: PW is not being asked to compare a signed-off candidate with a
lead, but to choose between **two candidates carrying the same evidence**.

### 5.1 The candidate

| | |
|---|---|
| configuration | **`MW/D32/DSP/SHARC/shipping.config.s32`** |
| differs from `shipping.config.s26` in | **one effective line**: `DSP4_AUXIN_BYPASS` 0 → 1 |
| differs from `shipping.config` (today's) in | the six switches s21 names, s26's one, and that one |
| `chip1.ldr` | **`6396187c`** — *byte-identical to candidate A's* |
| `chip2.ldr` | **`df5cc181`** (408,976 bytes; A's is 407,584) |
| staged on the bench as | **`s32_chip1.ldr` / `s32_chip2.ldr`**, unchanged since S32 |
| rollback pair | `s26_*` = `6396187c` / `9222c2ee`, and `s21_*` below that |
| reproducibility | **byte for byte across two clean builds**, plus a third by the capacity instrument |

**What the one line does.** A chip-2 `AUX_INPUT` node whose `on` cell is 0
publishes one block of silence, sets a flag, and is then **not called** until
the cell goes back to 1. Twelve nodes are in the class — `C2_SNK_IN_01..08`,
`C2_CODEC_AUX_IN`, `C2_PI_IN`, `C2_USB_IN`, `C2_BT_IN` — all twelve boot off,
and no capacity row this programme has ever taken turns one of them on. It is
two mechanisms and not one, and §4b says why; the gate's first test is the
host's own cell, so a 0 → 1 flip takes effect on its own block.

**What it changes for the graph: nothing.** Not a cell, not an address, not a
coefficient, not a config word, not the `defs` pin. The same sixteen
`Snk[n]On/Level` cells are written and read exactly as they are today, and a
snake return that is switched ON costs exactly what it costs today.

### 5.2 What it buys

**The capacity table PW asked for, chip 2, every product, both candidates,
two boots each, measured on one night with one instrument** (average % of
budget / worst block; `ovr` = missed blocks of 270,096):

| product, row | candidate A (s26) | **candidate B (s32)** | Δ | ovr A → B |
|---|--:|--:|--:|---|
| **D32, worst use** (12 aux, 6 reverbs) † | 100.86 / 101.01 | **95.69 / 96.03** | **-5.17** | 1,900 → **0** |
| **D32, silent + loaded** | 100.86 / 101.16 | **95.84 / 95.97** | **-5.02** | 1,900 → **0** |
| D32, driven with the load † | 100.94 / 101.15 | **95.59 / 96.00** | **-5.35** | 1,900 → **0** |
| D24, driven with the load † | 84.45 / 84.50 | **82.81 / 82.98** | **-1.64** | 0 → **0** |
| D16, driven with the load † | 73.18 / 73.19 | **71.35 / 71.45** | **-1.83** | 0 → **0** |
| D12, driven with the load † | 66.69 / 66.69 | **64.93 / 64.93** | **-1.76** | 0 → **0** |

† the `driveall` bitstream could not be loaded (no CPLD reflash — see §5.5),
so the rows taken with the stimulus playing ran a partial regime, **in both
arms identically**. The stimulus-stopped rows are the directly comparable
ones, and **D32 silent + loaded is the row that overruns**.

**THE TWELFTH AUX FITS, BY 4.31 POINTS.** Chip 2 reads **95.69 %** at D32
worst use with **zero missed blocks**, against 100.86 % and 1,900 of 270,096
on candidate A. Every row that overruns on A runs clean on B.

**Chip 1 does not move and cannot** — its image is byte-identical in the two
candidates — and across six D32 rows it wandered at most 0.16 points, inside
the instrument's ±0.27.

**Every other product gains 1.5–1.8 points it did not need**: four
switched-off aux inputs instead of twelve, at the same price a node (0.41
points), on four products with four different mask pairs. And the four
controls reproduce S28's rows on a second night.

**S29's scope-class lever becomes worth nothing (0.15 points instead of 3.5),
and the two savings DO NOT ADD** — they are the same five points, because
S29's 3.5 points were eight of these twelve nodes being called. Signing
candidate B is not also banking §4a's number. Full matrix in
`MW/D32/DSP/dsp4-s33-20260911.md` §3.5.

**The flip, on the final bytes** (S32 gate 4, repeated): a node the chain had
not called since boot passes full-scale audio at unity on the block its cell
goes to 1, and publishes exact silence when it goes back — 25 of 30 checks
pass and the five that fail are the inert `_auxin_q_` staleness of §5.4.

### 5.3 Every bar candidate A carries, on candidate B

| bar | candidate A | **candidate B** |
|---|---|---|
| byte-for-byte reproducibility | two clean builds | **two clean builds, plus a third by the capacity instrument** |
| `fix` sweep (S26) | 48 sites, 11 classes, 0 unresolved | **identical — the gate adds no float→fixed conversion** |
| `fix_sweep --check` (host vs part) | agrees on every class | **agrees on every class** |
| golden harness | 59 / 59 | **59 / 59** |
| `dsp_validate` | OK on 698 nodes, 4 standing notes | **OK on 698 nodes, the same 4** |
| `shared_kernel_check` + `--entries` | OK / 256 stubs OK | **OK / 256 stubs OK** |
| code pool, chip 1 | 181,350 / 262,144 (69.2 %) | **identical — same bytes** |
| code pool, chip 2 | 164,498 (62.8 %), 97,646 free | **165,890 (63.3 %), 96,254 free** |
| DM | no pool above 90 % | **no pool above 90 %**; +48 B of sections |
| capacity, D24 / D32 / D16 / D12 driven | S28, two boots each | **§5.2, two boots each, both arms re-measured on one night** |
| the D32 use ladder (worst use) | S29 | **§5.2** |
| the scope-class rows | S29 | **taken on both candidates** |
| the flip on the part | — | **S32 gate 4, repeated on the final bytes** |
| latency | **82 samples / 1.708 ms** (S29, n=3) | **NOT MEASURED** — see §5.5 |
| `famverify`, `busgold`, `goldnode`, the numeric arms | S27 | **not re-run** — see §5.5 |

### 5.4 The deviations PW must sign — §3's three, plus one, plus a corner

**Candidate B inherits §3.1, §3.2 and §3.3 unchanged and word for word**, and
it cannot help inheriting them: chip 1 is the same bytes, and the `fix` sweep
comes back identical because the gate converts nothing.

**Fourth: `_auxin_q_` is left stale while a node is off (S32-3).** After a node
goes back off, its Q4.28 coefficient word still holds `0x10000000` instead of
returning to 0. **It cannot reach the audio** — the sample path runs only on
blocks where the node is called and not parked, and sample 0 of every such
block recomputes the coefficient before the first MAC — and the published
block is exact zero either way, measured on all sixteen words of five nodes.
The fix is **one instruction**; it is deliberately not made, so that A and B
differ in one flag and nothing else.

**To sign:** a switched-off aux input leaves one parameter word holding its
last value. No kernel and no cell reads it.

**And a corner, not a deviation (S33-3).** Resuming from the park clears a
pending level ramp, so a level written while the node was OFF lands at its
target on the block the node comes back rather than finishing the ramp. That
reproduces the ungated **steady state** — in candidate A the ramp advances
while the node is off and has long since arrived — and the two differ only
if the `on` flip happens *inside* the ramp window (tens of milliseconds).
`on` is an `InstantCtl` cell in both builds, so the step at the flip is the
cell's in both.

### 5.5 What candidate B does NOT carry, and it is two things

1. **No latency measurement of its own.** S29's method needs the `maincap`
   and `pisel` bitstreams; S32 and S33 were both told not to reflash the CPLD
   with the analog board possibly attached, and both obeyed. The contract
   figure of **82 samples / 1.708 ms stands on candidate A**, and the
   argument that candidate B cannot have moved it — same block size, same
   `DSP4_TX_EARLY`, byte-identical chip 1 — is an argument, offered as one.
2. **The audio bars were not re-run** (`famverify`, `busgold`, `goldnode`,
   the numeric arms). Its audio evidence is the gate-4 flip on the part and
   the fact that the park writes exactly the zeros the body would.

**Both gaps close in one bench session that is allowed to flash the CPLD** —
which would also give the four fully driven product rows no session has been
able to take since S28. That is a bench-access ruling, not engineering.

### 5.6 The one-word sign-off

**"sign off s26"** — candidate A. Everything in §1–§3, the latency figure
measured on it, and the standing ruling that **a D32 ships eleven of its
twelve aux buses**. Deploys `chip1.ldr 6396187c` and `chip2.ldr 9222c2ee`.

**"sign off s32"** — candidate B. The same, plus the twelfth aux, plus
1.5–1.8 points of headroom on every other product in the range. Deploys the
**same `chip1.ldr`** and `chip2.ldr df5cc181` — one changed artifact against
the s21 plan instead of none. Costs one more deviation to sign (§5.4,
inert, one instruction to remove) and accepts the two gaps in §5.5.

**Neither word deploys anything on its own.** `shipping.config` is unchanged
and stays unchanged until PW rules, `shipping.config.s26` and
`shipping.config.s32` are both proposals, and both pairs are staged on the
bench with the `s21_*` rollback below them.

---

## 6. What these candidates do NOT bring to the window

* **R6–R11** — the matrix as composite rows and the FX topology — are held
  pending the team's block diagram. This candidate exists to make room for
  them, not to contain them.
* **The talkback and noise fan-outs.** Blocked on definitions, not on
  engineering: the cell master names a COUNT and no destination, its two
  halves disagree on their own encoding, and PW's 2026-09-06 ruling retires
  `Rtg` so the noise assign needs a NEW master function. S26 §3 has the
  detail; nothing was invented in its place.
* **Anti-clip, RTA, and the R6–R11 block-diagram rows** — all definition-
  blocked in the same way.
* **`Sys[1]LcrLaw[1]`** is dispatched and named out-of-product-scope until
  the hub lands the cell (S25).
* **A rewritten `fixed_ref` pan model** (S25-6) and a `goldnode` FILT arm
  (S26 §6.6). Both are instrument debt, both are carried, and neither is a
  reason to hold the candidate: FILT is covered by `busgold`, which is a
  whole-chain capture with FILT in it, and by its record-layout and entry
  checks.
