provenance: AI-drafted 2026-09-10 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The window candidate, in one place

**What this is.** The DSP configuration proposed for the rev C reconciliation
window, every bar run on it, and the numeric deviations PW is being asked to
sign — in one document, rather than spread across
`dsp4-window-readiness-20260909.md`'s eight addenda. Every figure was
measured on the rev C bench in session S27 (2026-09-10/11) unless a line says
otherwise.

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
deliberately not done inside the window. Free bits exist (word 2 bits 24 and
26–29).

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

## 5. What this candidate does NOT bring to the window

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
