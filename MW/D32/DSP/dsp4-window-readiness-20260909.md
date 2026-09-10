provenance: AI-drafted 2026-09-09 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# DSP readiness for the rev C reconciliation window

The window deploys the DSP firmware, the panel MCU headers (H1S3/H1S4),
the app and the matrix to the rev C unit TOGETHER. This is the DSP leg,
made ready and proven ahead of it so the window is a deploy and not a
debug. **It is PW-gated; nothing here was deployed.**

## 0-S23. THE COMPLETENESS LEG DOES NOT CHANGE THE CONFIGURATION, AND IT COSTS CHIP 2 (added 2026-09-10, S23)

**`shipping.config.s21` is unchanged and the proposal in §0 stands.** What
changed is the GRAPH: the FX returns now reach the main mix and the twelve
aux buses, the matrix is witnessed, and `Chan*CompMtr` is published. All of
it is behind the same configuration file; nothing here is a switch PW has to
sign.

**Two things in §0 above are superseded as statements of fact:**

1. **`Fx<n>On` HAS A READER NOW.** §0's "a user who switches an engine off
   still hears it and still pays for it" was true and is not any more: the
   cell parks the whole node, and parking is measured at **3.86 points of
   chip 2 cheaper than the bypass Type** the FX ladder used as its baseline.
2. **The six FX returns were INAUDIBLE and now are not.** That is not in §0
   at all — it was found after it was written (S22-2) — and it is the most
   product-visible thing this window carries: no image this tree had ever
   built put an FX return on any bus.

**The resource line PW should see**: chip 1's code pool is at **90.7 %**
with 24,274 bytes free and was already at 90.0 % before this session, so the
next feature built on chip 1 should expect the LDF rebalanced. Chip 2 has
98,670 bytes of code and 67,732 of DM free. The capacity rows are in
`MW/D32/DSP/dsp4-s23-20260910.md` §5.

**Seven definition questions are open and none of them was guessed at** —
they are listed in that write-up §6, and three of S22's are still open
beside them.
## 0. THE CONFIGURATION TO SHIP IS `shipping.config.s21`, AND THE PLUGIN HEADROOM IS MEASURED (added 2026-09-10, S21)

**Read this first. It supersedes §0b below on two points and nothing else:
S20's two open items — the FX engines' driven cost and chip 1's 380 free
bytes — are both closed here.**

### The proposal, and what changed since S20

**`MW/D32/DSP/SHARC/shipping.config.s21`** — `shipping.config.s20` plus
**one line**, `DSP4_SHARED_KERNELS=3` (COMPRESSOR + TUBE_SAT share one body
per class instead of 32 copies each). `shipping.config` and
`shipping.config.s20` are both **unchanged**. Write-up
`MW/D32/DSP/dsp4-s21-20260910.md`.

**Staged pair `s21_*` `81f799f9` / `11366344`**, with symbol maps beside it.
`DIAG_BUILD_CFG 0xCF45FF10` (unchanged from s20) and
`DIAG_BUILD_CFG2 0xC2019E6F` against s20's `0xC2011E4F` — bit 5 and bit 15,
the two shared classes, and nothing else.

### Chip 1's 380 free bytes are now 40,572

The one cost of `shipping.config.s20` that is not cycles, measured on the
linker map of each build:

| arm | chip 1 code, Blocks 3+2 | free | code in the CONTENDED DM/DMA block |
|---|--:|--:|--:|
| `shipping.config` (the default) | 235,064 / 262,144 | 27,080 | none |
| `shipping.config.s20` | 261,764 / 262,144 | **380** | **1,692** |
| **`shipping.config.s21`** | **221,572 / 262,144** | **40,572** | **none** |

`build.sh` refused `DSP4_SHARED_KERNELS` with `DSP4_SIMD_DYN` from S18 until
this session, and S20-3 carried that refusal to PW as the reason the lever
was unavailable. **The refusal was a guard and not a finding** — the pair
drivers reach a shared class through that node's own two-instruction stub,
which loads the strip's record base, so the two switches act on different
code. It is replaced by a per-build check with two negative controls
(S21-2), and what actually did not build was `SHARED_KERNELS` with
`DYN_LUT`, three faults deep, all fixed (S21-3).

**Cost, driven, with six reverbs running:** chip 1 +0.62 points at D32 and
−0.14 at D24 (inside the boot spread), chip 2 nothing. `dsp_memreport.py`
reports all pools below 90 % for the first time on any arm that fits both
products.

**Audio: the same twenty verdicts.** `famdiff.py` puts the `s21_*` famverify
report **0 of 20 families** from the `s20_*` one, and `shkstrip.sh` — the
bar famverify structurally cannot be, because famverify drives strip 1 —
writes six different compressor thresholds to six strips and reads each
strip's own converted word back out of its own record, identically on the
shared arm and on the inlined control.

### The plugin load, measured driven

Every driven figure in S20's table was taken with the six FX engines fed
silence: `--mode load` left every `Chan<nn>FxSend` at 0.0, so the FX buses
carried nothing and the engines ran their algorithm over zeros. `--mode
loadfx` opens all six sends on all 32 strips and puts the engines on, all wet,
at a named Type, and a **ladder takes one row per algorithm on one boot** so
the FX cost is a within-boot difference.

| | chip 1 | chip 2 | headroom on chip 2 | overruns |
|---|--:|--:|--:|---|
| D24, `s20_*`, FX fed silence (S20's row) | 53.8 | 59.0 | 41.0 % | zero |
| **D24, six reverbs fed and wet** | **56.8 / 56.4** | **74.2 / 74.1** | **25.8 %** | **zero** |
| D32, `s20_*`, FX fed silence (S20's row) | 71.6 | 72.6 | 27.4 % | zero |
| **D32, six reverbs fed and wet** | **74.6 / 74.6** | **87.1 / 87.1** | **12.9 %** | **zero** |
| **D24, `s21_*`, six reverbs** | **56.5** | **74.1** | **25.9 %** | **zero** |
| **D32, `s21_*`, six reverbs** | **75.2** | **87.1** | **12.9 %** | **zero** |

**The reverbs are 16.3 points of chip 2 at D32 and 16.4 at D24**, against a
Type-4 rung where the engines are parked in the dispatch's bypass. The other
algorithms are cheap: Echo +1.3, Doubling +0.9. The six engines are fixed
instances and do not scale with the channel count, which is why both products
pay the same for them. Two boots per product, every rung on one boot, zero
missed blocks on every row.

**PW's headroom rule is met at both products with the worst plugin load the
product can be asked for.** What is NOT headroom-limited is chip 1: opening
the six FX sends on 32 strips costs it ~3 points of crosspoint accumulate and
the engines themselves cost it nothing, because they are chip 2's.

### Three things PW should know about the FX engines themselves

Measured while pricing them, not defects introduced:

1. **`Fx<n>On` does not bypass an engine.** `_fx_on_<nid>` is written by the
   SPI dispatch table and read by no instruction in any kernel: the
   FX_ENGINE body has no on/off branch. A user who switches FX 1 off still
   hears it and still pays for it.
2. **Eleven more host-writable FX cells reach no arithmetic**, and three more
   are dispatched to address 0. Five cells work: `Type`, `Mix`, `Damp`,
   `Feedback`, `DelayTime`. `Decay`, `PreDelay`, the three EQ bands, the five
   HPF coefficients, `ModRate`, `ModLevel`, `LfoShape`, `StereoWidth`,
   `Balance`, `DuckOn` and `DuckSens` do not. The reverb is a Freeverb whose
   room size and decay do nothing.
3. **Four of the seven Types are not implemented for the class the graph
   declares.** All six engines are the `reverb` class, which implements Echo
   (0), Doubling (2) and Reverb (3); PingPong, Chorus, Flanger and Phaser
   park the Type in `_fx_bypassed_<nid>` and pass the input through dry.

None of this changes the fit. All of it will be visible on the FX pages of
the app, and it is PW's call whether the window ships with the controls
present.

### And one objection to `DSP4_SIMD_DYN` that is new and has a measurement behind it

**On any image with `DSP4_SIMD_DYN` on, the ODD strip of every gate pair has
four FROZEN per-node state words** — envelope, gain, target and hold count,
unchanging over twelve seconds with nothing driving the strip — while the
partner strip of the same pair has a hold counter that decrements on every
sample. Found by fixing `goldnode` (S21-5), bisected to that one switch (each
of the other four turned off in turn leaves it), and corroborated at the
source: `_DYNCOMP_nn_mm_process` ends with an epilogue that copies the pair's
gain display back into each node's own word and `_DYNGATE_nn_mm_process` has
no write-back at all. Finding **S21-7**; the instrument is
`tools/pi/dsp4_gate_latch.py`.

**Whether the audio differs is NOT established.** Every sample-level bar
passes on this configuration — famverify GATE LIVE and 0 of 20 families
between `s21_*` and `s20_*`, `busgold` bit-exact against the 2026-08-30
golden with the two declared deviations off, `golden_harness` 59/59. Against
that, the per-sample gate body reads `_gate_gain_<nid>` as its starting state
and the pair driver calls that body for sample 0 of every block.

It is **one session's work to settle** — give the four gate words the
treatment `_comp_gain_` already gets, then re-run goldnode's GATE arm on the
SIMD image and require 64 of 64, which the bar can now score. It is on this
page rather than left off it because `DSP4_SIMD_DYN` is one of the five
switches being signed, and because S12-5 was cited against that switch for
two sessions on grounds that had already been closed.

### What PW is being asked to rule

The same two numeric-spec deviations as in S20, and no new ones:
**`DSP4_DYN_LUT`** (0.0950 dB worst case over the documented sweep;
0.00518 dB and 0.03934 dB measured on the part) and **`DSP4_GATE_LINTHR`**
(≤0.0002 dB threshold shift). **`DSP4_SHARED_KERNELS` adds no deviation** —
the shared body is the same emitter's instructions as the inline arm,
rewritten from absolute per-node addresses to record offsets, entered per
strip through a stub the build checks.

### One correction to every capacity table in this note

**The "worst block the budget has to cover" column has been over-reporting
by exactly one diag tick — 983,040 cycles, 300 % of a block-16 budget — on
about one row in six**, and the "config ladder transient" that has been
printed beside it since S13 does not exist. The mechanism is a two-instruction
race in `main.asm` between the `tcount` read and the `_diag_ticks` read that
close each block pass. Corrected, the true worst block on this configuration
is **about half a point above the average**. Averages, overrun counts and
every fit conclusion in this note are unaffected; the fix to `main.asm` is
four instructions and is deliberately not in the images S20 staged. See S21-6.

---

## 0b. S20's PROPOSAL, superseded on two points by §0 above (added 2026-09-10, S20)

**Read this first; §0a below is S19's warning and it still applies to every
percentage further down.**

S19 measured, under load, that **the configuration `shipping.config` names
fits neither product**: D24 118.9 % / 119.2 % of budget with one block in six
dropped, D32 158.2 % / 142.8 % with one in three. S20 built the successor as
ONE named configuration file, proved the part reads it back to the bit, took
every audio bar the tree has on that image, and re-measured driven capacity on
both chips and both products.

### The proposal

**`MW/D32/DSP/SHARC/shipping.config.s20`** — `shipping.config` plus five
switches and nothing else: `DSP4_STRIP_FUSED=1` (S11), `DSP4_SIMD_DYN=1`
(S12), `DSP4_C2_BQ_GRAPH=1` (S13-1), `DSP4_GATE_LINTHR=1` (S15-7),
`DSP4_DYN_LUT=1` (S15/S16-6). `shipping.config` itself is **unchanged**; the
proposal is PW's to adopt. Write-up `MW/D32/DSP/dsp4-s20-20260910.md`.

**Staged pair: `s20_*` `32dc1ea1` / `29d00a5e`**, with symbol maps beside it.
Both chips read back `DIAG_BUILD_CFG 0xCF45FF10` and
`DIAG_BUILD_CFG2 0xC2011E4F`, matching the file to the bit (`cfgverify.sh`).
`s20f_*` `20f04ffe` / `7802f1f2` is the same file plus `DSP4_BQ_SIMD_PIPE=2`.

### It fits both products under load, with margin

Driven, two boots, both chips, every regime snapshot proven,
`DIAG_BLK_OVERRUN` the arbiter:

| pair | D24 chip 1 / chip 2 | D32 chip 1 / chip 2 | overruns |
|---|--:|--:|---|
| the shipping default (`blk_*`) | 118.9 / 119.2 | 158.2 / 142.8 | **one block in six, one in three** |
| `s16_*` | 82.4 / 94.6 | 109.5 / 115.8 | zero at D24; **8.7 % / 13.3 % at D32** |
| **`s20_*`** | **53.8 / 59.0** | **71.6 / 72.6** | **ZERO on every row of both boots of both products** |
| `s20f_*` | 52.4 / 55.0 | 69.8 / 66.7 | zero |

**Latency MEASURED on `s20_*`: 80 / 83 samples through-DSP** against a
LOGIC-only reference re-taken the same session (14,433, 100.0 % coherent).
**The contract figure stands at 82 samples / 1.708 ms.** Option A stays chip 2
only.

### Audio: one verdict of twenty moves, and it is the one that has to

`famverify` 20 families both chips against the shipping pair: **1 of 20
verdicts differs — COMPRESSOR's numeric arm, at 0.00518 dB** against the
table's 0.0950 dB bound and PW's 0.1 dB ruling. 17/20 audio LIVE, contract
20/20 answering, FADER_PAN and TUBE_SAT BIT_EXACT. `bqeverify` **0 ULP over
36,864 words**. `geqverify` and `afbverify` deliver +12.000 dB and −18.000 dB
through the PAIRED chip-2 GEQ and AFB to within 0.003 dB — the two families
S12-5 found inert. `golden_harness` 59/59. `busgold` is not bit-exact **and
cannot be** (its harness leaves the compressor wet and the table is what
replaces its gain computer): **0.03934 dB worst word**, and with
`DSP4_DYN_LUT`/`DSP4_GATE_LINTHR` off, the same image reproduces the
2026-08-30 golden **bit for bit** — so fusion, SIMD and the chip-2 pairing move
no bus word at all.

### What PW is being asked to rule

Two of the five switches are numeric-spec deviations and need sign-off:
**`DSP4_DYN_LUT`** (0.0950 dB worst case over the documented sweep; 0.00518 dB
and 0.03934 dB measured on the part) and **`DSP4_GATE_LINTHR`** (≤0.0002 dB
threshold shift). The other three carry no deviation to sign off.

### What is left open, and one resource number

* ~~**The FX engines' driven cost is NOT measured.**~~ **CLOSED by S21 —
  see §0.** It is 16.3 points of chip 2 at D32 and 16.4 at D24 for six
  reverbs, leaving 12.9 % and 25.8 % of chip 2 free with zero missed blocks.
  Every driven figure in the rest of THIS section is still taken with the FX
  buses silent.
* ~~**Chip 1's code pool has 380 bytes free on `s20_*`** ... S18's
  −38,634-byte lever cannot be combined with this configuration.~~ **CLOSED
  by S21 — see §0.** The refusal was a guard and not a finding; the lever
  applies, and `shipping.config.s21` has **40,572 bytes free with no code in
  the contended block**, for 0.62 points of chip 1 at D32.
* Nothing rebuilds against this: no contract change, no address moves, defs
  pin `defs-v2026.09.08.4` throughout. Rollback is `blk_*`, untouched.

---

## 0a. EVERY CAPACITY FIGURE BELOW THIS LINE IS A SILENCE FIGURE (added 2026-09-10, S19)

**Read this before any percentage in this note.** Every capacity number in
sections 1 onward — and every capacity number the window has been shown to
date — was taken on a bench with no signal on the converters, and the graph
is 30 to 57 points cheaper in that state than it is with its dynamics
engaged. They are not wrong about the arm they describe; they are
answering a question the product does not ask. Treat each of them as
carrying an implicit **(silence)**.

The driven measurement is `MW/D32/DSP/dsp4-driven-20260910.md`. The
instrument is a LOGIC bitstream that broadcasts the CM4's playback onto
every DSPA input lane, so the DSP executes no instruction on the
stimulus's behalf (its residue is 0.28 points on chip 1 and 0.53 on
chip 2, measured); the regime — every dynamics envelope live — is proved
on both chips before a row is taken.

**The numbers the window should carry, D24 mask, clock measured, two boots,
`DIAG_BLK_OVERRUN` the arbiter:**

| pair | chip 1 driven | chip 2 driven | fits? |
|---|--:|--:|---|
| the shipping default (`blk_*`) | **118.9 %**, 15.8 % of blocks missed | **119.2 %**, 16.0 % missed | **NO** |
| `s16_*` (COMP/LIMITER on the LUT, linear-threshold GATE) | **82.4 %** | **94.6 %** | **YES, zero overruns** |
| `s16f_*` (the same + six-slot biquad) | 82.2 % | 94.6 % | YES, zero overruns |
| `s18_*` (shared COMP/TUBE kernels) | 119.6 %, 16.4 % missed | 119.3 %, 16.1 % missed | NO — a bytes lever, not a cycles one |

**At D32 all-ones nothing that was staged before today fits.** The
shipping default is 158.2 % / 142.8 % driven; `s16_*` is 109.5 % / 115.5 %
and misses blocks at silence as well, so D32's shortfall is static cost
rather than dynamics. The only configuration measured that fits D32 under
load is `s16_*` plus `DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1` — **71.3 % /
93.9 %, zero overruns** — which is blocked on the audio findings S12-5 and
S12-7, not on capacity.

Two consequences for what this note says further down:

* **§7's "D32 fits with STRIP_FUSED + SIMD_DYN at 82.0 % of budget" is a
  silence figure.** Driven, that configuration reads 93.9 % on chip 2. It
  still fits; the margin is 6 points, not 18.
* **The chip-1 margins quoted throughout are silence margins.** Chip 1's
  cost is signal-DEPENDENT — S18 said otherwise and S19 measured it — so
  a chip-1 margin taken silent is not a margin.

Latency, the contract's 82 samples at block 16, is unchanged: nothing in
S19 touches the transmit path.

---

## 1. The artifacts the window deploys

| | |
|---|---|
| contract | **`defs-v2026.09.08.4`** (defs `48745eae5418`), D24 matrix generation `3d41d5850df3`, 4,985 cells |
| dsp.csv commit | proposed **`54f2924`**, landed by the hub as `.4` **byte-identical** (row bytes diffed) |
| chip 1 image | `build/chip1.ldr` **md5 `093c609f622cf805e7f675f1e2497a19`**, 344,112 bytes |
| chip 2 image | `build/chip2.ldr` **md5 `2ba0e464e9679bd2e1b1c3c2a6f08744`**, 210,368 bytes |
| build | `MW/D32/DSP/SHARC/build.sh` with no overrides — the shipping float configuration (`DSP4_BQ_FLOAT=1`, `DSP4_GAIN_FLOAT=1`, `DSP4_GEQ_DESIGN=1`, `DSP4_XOVER_DESIGN=1`, `DSP4_AFB_DESIGN=1`, `DSP4_BISECT=0`) and now `DSP4_CHAN_MASK=1` |
| **build, as of 2026-09-09 09:xx** | `MW/D32/DSP/SHARC/build.sh` with no overrides still, but the defaults now come from **`MW/D32/DSP/SHARC/shipping.config`** and include `DSP4_GEN_BLOCK=16`, `DSP4_BLOCK_KERNELS=1`, `DSP4_CCLK_TARGET=983`, `DSP4_BLK_LATCH=1`, `DSP4_GATHER_FIRST=1`. The three pairs named below PREDATE that and are none of them the measured configuration |
| CPLD | unchanged — `dsp4_logic.a1f6672af6c3`, flashed twice for the mask captures and restored, IDCODE `0x020a30dd` re-read |
| staged on the bench | `app@192.168.1.219:~/dspboot/chip1.ldr` and `chip2.ldr` hold exactly these two images; the 09-09 00:xx pair `602a0feb` / `b1325022` is kept alongside as `conf_chip1.ldr` / `conf_chip2.ldr`, and the 09-09 06:xx ORDER-DEFECT pair as `tx_chip1.ldr` / `tx_chip2.ldr` |

**A FOURTH PAIR IS STAGED AND IT IS THE FIRST ONE WHOSE BLOCK LOOP FITS THE BLOCK (2026-09-09 09:xx).** `~/dspboot/blk_chip1.ldr` **`ac65ad386fb910b7bed7736872abae43`** (421,768 bytes) / `blk_chip2.ldr` **`e5dce9e43c2c72290c115726ca31976c`** (280,284 bytes). This is **THE SHIPPING CONFIGURATION**: `BLOCK=16`, `DSP4_BLOCK_KERNELS=1`, `DSP4_CCLK_TARGET=983`, the phase fix and the channel mask, all named in one file — `MW/D32/DSP/SHARC/shipping.config` — and produced by a plain `./build.sh` from the current tree. The image reads back `DIAG_BUILD_CFG = 0xCF45FF10`, which is what a shipping image must read; `tools/pi/dsp4_buildcfg.py --expect-shipping` fails on anything else.

**The three pairs above are all BLOCK=8, per-sample, and running at 491.52 MHz, and none of them fits.** Every capacity number the window has ever been shown — the `.4` figures included — was taken on a BLOCK=16, block-kernel, 983.04 MHz build that no `.ldr` in `~/dspboot` carried. Read off the running window pair before this session changed anything: `CGU0_CTL 0x00002800` on both chips, the CGU reset row, not the 983.04 row. So the window pair's real budget is 81,920 cycles/block and it is over it by **4.03x on chip 1 and 3.50x on chip 2**, missing 75.1 % and 70.9 % of blocks. `MW/D32/DSP/dsp4-shipping-config-20260909.md` is the measurement; findings S9-1.

On `blk_*`, D24 mask, both chips configured, budget 327,680 cycles/block: **chip 1 234,594 (71.6 %), chip 2 303,894 (92.7 %), `DIAG_BLK_OVERRUN` ZERO on both over ten minutes** at 3,000.0 blocks/s.

**WHAT THE WINDOW MUST KNOW BEFORE DEPLOYING `blk_*`.**

* **THE PANEL MCU MOVES WITH IT.** A ramp-engine frame is one audio block, so block 16 halves every ramp frame count. `MW/D32/DSP/ghost_cells.h` and the panel MCU's own copy under `MW/D32/FW/H1S1/` are regenerated in this commit, and **H1S3/H1S4 must be rebuilt from them or every ramp runs at half speed.**
* **THROUGH-DSP LATENCY DOUBLES.** The 72 samples / 1.500 ms figure is a block-8 measurement. Block 16 is a nine-block pipeline of twice the length.
* **D32 DOES NOT FIT.** With the all-ones mask, chip 2 missed **11.3 %** of blocks. `blk_*` is a D24 shipping configuration; D32 at block 16 needs more chip-2 capacity work (findings S9-3).
* **ONE FRAME PER BLOCK IS STILL LATE (findings S9-2, OPEN).** With zero blocks missed, the first frame of each DMA half still loses a race against the DDE and goes out two blocks stale — 1 late frame per 16 at the D24 default, 2 with the Pi playback input also on. It is a race whose count tracks the LOAD, not an indexing error, and the fix is structural: one more block of output latency, or a third TX buffer. **`blk_*` is a large improvement on the three pairs above and is not yet correct.**

**A THIRD PAIR IS STAGED AND THE HUB CHOOSES (2026-09-09 06:xx).** `~/dspboot/tx_chip1.ldr` **`21f9fdc1ebd3afe4709869f5884da1f5`** / `tx_chip2.ldr` **`de14981fe9165e3047e45dd60a00bb6b`** is the pair above plus `DSP4_BLK_LATCH=1`, which is a plain `./build.sh` from the current tree. It fixes THE ORDER DEFECT: the core was writing the ping/pong half the DMA was clocking onto the wire, so every transmitted 8-sample window on every chip-2 output lane was assembled from up to three consecutive blocks. Proven on the part at **100.0000 %** ordered, 191,999 of 191,999 transitions, one entry in the delta histogram; `DSP4_BLK_LATCH=0` rebuilds `093c609f` / `2ba0e464` byte for byte. It costs two DM words and one call per block, famverify is unmoved at the `.4` line, and the through-DSP latency is unmoved at 72 samples. `MW/D32/DSP/dsp4-order-defect-20260909.md` is the measurement.

**It does not make the unit correct on its own, and the window should know that.** A second, independent defect is open underneath it (findings S8-2): the block loop does not fit the block period in the shipping BLOCK=8 per-sample configuration — chip 1 misses 75.1 % of blocks and chip 2 70.9 % — so the halves carry stale whole blocks whichever pair is deployed. Both pairs above have that defect equally; the `tx_*` pair removes the intra-window splice on top of it. Deploying `tx_*` is strictly better than deploying `chip*.ldr`; deploying either still ships an output that is two-thirds stale until S8-2 is fixed.

**THE IMAGES CHANGED ON 2026-09-09 AND THIS IS WHY.** The pair this note
first named — `602a0feb` / `b1325022` — stored `CFG_CHAN_MASK` and
`CFG_AUX_MASK` and read neither, so **the rev C unit, which is a D24, ran
all 32 channel strips and all 12 aux buses.** Its main output sat at
positive full scale with nothing playing, driven by eight strips the
product does not have and cannot silence from its own contract. The pair
above is the same build with those two words given readers; a masked
strip or aux is SKIPPED. `MW/D32/DSP/dsp4-chan-mask-20260909.md` is the
measurement, and `DSP4_CHAN_MASK=0` rebuilds `602a0feb` / `b1325022` byte
for byte, which is what makes the two comparable.

The window's other artifacts are unchanged: same contract, same address
map, same panel-MCU and app requirement. Nothing in §2 moves.

The images were built twice: once from `proposals/defs/products/` before
the hub gate and once from `defs/products/` after `.4` landed. **Both
builds produced the same two md5s**, which is the proof that "built from
the proposal" and "built from the tag" are the same firmware. That
argument is unaffected by the channel-mask fix: the fix touches the
firmware, not the contract, and `DSP4_CHAN_MASK=0` reproduces the images
those two builds agreed on.

### What the unit does before and after

On the bench, D24 config, nothing playing, `C2_MAIN_ST_OUT` over 48,000
frames: **`0x7FFFFF88` on every frame before, `0x00000000` on every frame
after.** Under a D32 config the fixed image reads `0x7FFFFF80` on every
frame — unchanged from before, because all 32 strips are live and this
board has nothing driving 25-32. The mask is the only difference and the
product config is the only thing that selects it.

### What it is worth

Block 16, 983.04 MHz, budget 327,680 cycles/block, two boots, minimum,
both arms measured in one session on one instrument:

| | control | masked | margin |
|---|---:|---:|---|
| chip 1 | 262,033 | **202,786** | 20.03 % → **38.11 %** |
| chip 2 | 261,856 | **226,442** | 20.09 % → **30.90 %** |
| chip 2, six reverbs | 310,185 (09-08) | **275,035** | 5.34 % → **16.07 %** |

The six-reverb worst case is the number the product ships against, and it
was inside the 10 % bar only because the part was running four aux chains
and eight strips a D24 does not have.

## 2. What the panel MCU and the app must be built against

**`defs-v2026.09.08.4`, and nothing earlier will work.** The 31-band GEQ
re-lays chip 2: 1,192 D24 (1,460 D32) addresses move, chip 1 moves not at
all. A host holding `.2`'s or `.3`'s chip-2 map writes an aux limiter
threshold into an anti-feedback notch — silently, because every one of
those addresses answers. There is no shim and there should not be one;
the maps are told apart by the contract version.

Regenerate, do not hand-edit:

* `MW/D32/FW/H1S1/Core/Inc/ghost_cells.h` + `Core/Src/ghost_cells.c` —
  5,449 cells (both products merged)
* `MW/D32/FW/H1S1/Core/Inc/mx_dsp_map.h` — **5,409 entries, equal to
  D32's `dsp.csv` row count**, which is the check that the 09-08
  dispatch-map defect (2,064 cells missing by spelling) has not
  recurred. Every one of D32's 5,409 and D24's 3,737 addressed cells is
  present in `ghost_cells.c` by name.

## 3. Rollback

The previous shipping images are on the bench and untouched:
`~/dspboot/ship_chip1.ldr` md5 `3f0e479aee61219e18108ce27384295d`,
`~/dspboot/ship_chip2.ldr` md5 `ab43c75b56706341ba85268c217ce1dc`.
**Rollback is unchanged by the channel-mask fix.** There is also an
intermediate step now: `~/dspboot/conf_chip1.ldr` / `conf_chip2.ldr`
(`602a0feb` / `b1325022`) is the same firmware WITHOUT the mask readers,
on the same `.4` address map, so a problem traced to the mask can be
backed out without also rolling the contract back.

To reflash: `sudo systemctl stop matrix-app`,
`sudo pinctrl set 6,24 op dh; sudo pinctrl set 8,12 ip; sudo pinctrl set
7,9,10,11,22,23,25 a0` (NOT one `a0` line over all eleven pins — that is
the S8-3 defect and it boots chip 2 with chip 1's firmware), copy the two `ship_*`
files over `chip1.ldr`/`chip2.ldr`, then `python3 dsp4_boot.py --dir .`
and `dsp4_config.py --product d24 --chip 1|2` — **twice**, the config
commit desyncs the parameter link on the first cycle every time. Verify
the restore through `matrix-app`'s log (all three MCUs), not through
`dsp4_diag`: the shipping graph is over the per-block budget at block 8
and starves the main-loop poll, which reads like a fault and is not one.
Rolling the firmware back also rolls the address map back, so the panel
MCU and app must go back to `.2` with it.

## 4. The one-line acceptance to run on the unit after the window

```
cd MW/D32/DSP/SHARC && BUILD=0 ./famverify.sh && \
  python3 ../../../../tools/dsp/hw_coverage.py goldens/famverify-*.json
```

Pass is **17 of 20 families / 3,619 of 3,737 addressed cells**, GEQ at
**31/31** and CROSSOVER at **8/8**, with the report's `pin` reading
`defs-v2026.09.08.4`. Anything less means the host and the firmware are
not on the same map. **Re-run on the masked image 2026-09-09 and it is
that line to the cell**, 0 FAILED — the mask removes strips 25-32, which
a D24 has no cells for, so nothing the walk addresses moved.

Worth running with it, since it is one line and it is the thing that went
wrong:

```
python3 tools/pi/dsp4_mask_witness.py --no-silence
```

with the duplex overlay and a capture-path bitstream. `_chan_mask_live`
must read `0x00FFFFFF` and `_aux_mask_live` `0x000000FF` on BOTH chips —
the STAGED words read back fine even when nothing consumes them, which is
exactly how this went unnoticed.

## 5. What the DSP is NOT bringing to the window

* **AUX_INPUT (8 cells)** — addresses answer, no stimulus path exists on
  this bench to move them. Not a firmware gap.
* **DCA (16 cells)** — host-managed by the 2026-08-30 ruling. The DSP
  applies no DCA gain and there is nothing on the part to probe.
* **METER (94 cells)** — no audio probe; `mtrverify.sh` is this family's
  bar and was not re-run in this session.
* The **fixed/shootout arms of `bqeverify`** do not link: chip 1's
  `sec_swco` overflows by 604 words under `DSP4_BQ_SHOOTOUT=1
  DSP4_BQE_VERIFY=1`. **Pre-existing** — the same arm at the previous
  commit (`e278667`) overflows by 386 — and it does not touch the
  shipping image, which links with 85,330 words of code free on chip 1.
  This session's work accounts for 218 of the 604.

---

## 6. Addendum, 2026-09-09 later — S9-5 closed, and the two numbers that changed

**The shipping pair `blk_chip1.ldr` `ac65ad386fb910b7bed7736872abae43` /
`blk_chip2.ldr` `e5dce9e43c2c72290c115726ca31976c` is unchanged and is
still the artifact. Nothing in this addendum changes an image.** Every
change of the session is behind `DSP4_SCOPE_BLK_TAP` (default 0) and a
default `./build.sh` reproduces both md5s byte for byte.

**S9-5 is CLOSED and the answer is that block kernels are not an audio
defect.** famverify's audio arm reads **17 of 20 LIVE on the shipping
configuration** and agrees with the block-8 per-sample control on all
twenty families, verdict for verdict; the contract arm is identical on
every family (GEQ 31/31, CROSSOVER 8/8, ROUTING 42/42, COMPRESSOR 17/17,
ANTI_FB 20/20, 0 FAILED) and the numeric arm is BIT_EXACT on COMPRESSOR,
FADER_PAN and TUBE_SAT. The 8-of-20 that blocked the window was the bench
witness reading a variable the block kernels never write, and the bench
stimulus being written into a slot nothing reads — both on chip 1, both in
the instrument. `MW/D32/DSP/dsp4-block-witness-20260909.md`, findings
S10-1..S10-5. **So the DSP's readiness line for the window is 17 of 20
families LIVE and 3,737 of 3,737 addressed cells answering, measured on the
pair that ships.**

**Two capacity numbers the window was carrying are wrong and the corrected
ones are in `MW/D32/DSP/dsp4-capacity-20260909.md`:**

1. **Chip 1's D24 margin is 15.2 %, not 28.5 %.** Margins have been quoted
   off `_proc_cyc`, the last block pass; chip 1's *worst* block is
   consistently 18 % higher (234,267 → 277,752 = 84.8 % of budget). Chip 2
   is flat to 0.4 % and is unaffected. Findings S10-8.
2. **"Chip 1 sits at 71.6 %" is a D24 statement and was being read as a
   D32 one.** At D32 all-ones chip 1 is at **93.5 % average, 110.3 %
   worst**. There is no spare chip 1 to move D32 work onto.

**D24 still fits and D32 still does not**, both now measured on the pair
that ships rather than on the profile instrument: D24 **zero missed blocks
on both chips over 270,000 blocks**; D32 chip 2 at **112.7 % of budget,
missing 11.26 %** of blocks, which reproduces S9-3's 11.3 % and closes
arithmetically against the cycle count to four decimal places. The levers
that would close it are costed in §6 of the capacity note; **block 32 is
the recommended first try** because it costs neither product scope nor
sound, and one build plus one boot settles it.

**S9-2 is costed for a ruling** in `MW/D32/DSP/dsp4-s92-options-20260909.md`
— both structural options cost the same 0.333 ms of output latency, Option
A costs 0.20 % of budget and stays inside the DMA topology, Option B costs
nothing and re-opens the ping/pong phase. Recommendation: **Option A**.
What ships until PW rules is `DSP4_GATHER_FIRST=1`, which is one frame of
margin and not a fix. **If either option lands, the published through-DSP
latency grows by 16 samples / 0.333 ms and this note and the alignment
contract must be reissued with it.**

**Still not restated on the shipping pair, and the window should know:**
through-DSP latency at block 16 (the 72-sample figure is a block-8 number),
`busgold`, `bqeverify`, `fxverify`, `afbverify`, `geqverify`,
`xoververify`.

## 7. Addendum, 2026-09-09 latest — S11: one instrument, two rulings with numbers, and a lever nobody had costed

**Four things in §6 are now wrong or superseded. They are listed first.**

1. **"Block 32 is the recommended first try" — it is answered and the
   answer is no.** It links and boots; D32 chip 2 goes from 112.7 % to
   **117.51 %** of budget and from 11.26 % to **14.86 %** of blocks missed,
   because chip 2's per-sample cost RISES 4.2 % while chip 1's falls 7.7 %.
   Its latency price is **+65 samples / 1.354 ms**, not 0.333 ms.
2. **The through-DSP latency at block 16 is measured: 66 samples /
   1.375 ms**, against the CPLD loop reference, 20 reps. The 72-sample
   figure this note has been carrying is a **block-8** number from an image
   missing 70 % of its blocks; it is superseded, not corrected.
3. **S9-2 Option A is BUILT and PROVEN at 100.0000 % ordered on the part**,
   and it costs **zero cycles and zero DM**, not the 640 cycles and 320
   words it was costed at. Its latency cost is **+16 samples per chip**, and
   the switch is a per-chip mask so the ruling can buy one block or two.
4. **The capacity record's instrument was a different, faster build.**
   Every `sigprofile2` / `fxcost` chip-2 figure — the `.4` record included —
   was taken with `DSP4_STRIP_FUSED=1` and `DSP4_SIMD_DYN=1`, which are not
   in `shipping.config` and default to 0. `DSP4_BLOCK_DECIMATE` was
   innocent.

**And that fourth item is a capacity lever nobody had costed.** Those two
switches together take D32 chip 2 from 112.7 % to **82.0 % of budget, worst
block 86.75 %, ZERO missed blocks over 270,082**. **D32 fits.** The catch:
`DSP4_STRIP_FUSED` alone is worth 1.1 % and is proven verdict-for-verdict
against the shipping image on all twenty families; **the other 29.6 % is
`DSP4_SIMD_DYN`, whose audio arm does not pass and whose certifying witness
does not currently fit in the image alongside it** (chip 1 `sec_swco`
overflow). That is the next session, and it is now the shortest path to a
D32 that fits with no PCB change — PW's stated first priority.

### The two rulings, as a decision table

**S9-2 — the late first frame of each DMA half.** Instrument: transmit
stamp, full D24 graph, Pi staircase, 192,000 frames.

| option | ordered | cycles | DM | through-DSP latency | residual risk |
|---|---|--:|--:|--:|---|
| do nothing (`DSP4_GATHER_FIRST=1` only) | 87.4999 % | — | — | 66 samples | one frame in sixteen carries a two-block-old sample on every converter lane |
| **`DSP4_TX_EARLY=2`** (chip 2) | **100.0000 %** | **0** | **0** | 82 samples, **+0.333 ms** | chip 1's inter-chip TX keeps the defect; this bench cannot witness it |
| **`DSP4_TX_EARLY=3`** (both) | **100.0000 %** | **0** | **0** | 99 samples, **+0.667 ms** | none known |
| Option B, third TX buffer | not built | ~0 | +1 half | the same | re-derives the ping/pong phase, desynchronises RX from TX |

Recommendation **`=3`**; `=2` if 0.333 ms is the whole budget.
`DSP4_GATHER_FIRST` stays on either way — measured, not assumed.

**D32 capacity — chip 2 must lose 41,744 cycles/block.**

| lever | chip 2 at D32 | overrun | latency | sound / scope | proven? |
|---|--:|--:|--:|---|---|
| nothing | 112.7 % | 11.26 % | 66 | — | — |
| **BLOCK 32** | **117.51 %** | 14.86 % | 131 (**+1.354 ms**) | ramp counts halve again; H1S3/H1S4 rebuild | **built, booted, measured — it does not work** |
| `DSP4_STRIP_FUSED` | 111.66 % | 10.32 % | 66 | none | **yes** — famverify identical to shipping |
| **`+ DSP4_SIMD_DYN`** | **82.03 %**, worst **86.75 %** | **0** | 66 | none expected | **NO** — 4 families NO_CAPTURE, and the witness will not link with it |
| GEQ bands 31→28 / →21 | −1.5 % / −5.0 % (estimate) | — | 66 | product scope, second address relayout | not measured this session |
| half-rate reverb tail | −7.5 % (estimate) | — | 66 | **changes what the product sounds like** | not measured |

### What the window's artifacts are now

`~/dspboot/blk_chip1.ldr` `ac65ad38…` / `blk_chip2.ldr` `e5dce9e4…` are
**unchanged and remain the artifacts**, and all ten staged `.ldr` files were
verified byte-identical at the end of the session. **But the tree no longer
reproduces them**: `DIAG_BUILD_CFG2` had to be added, because three images
81,299 cycles/block apart all read the same `DIAG_BUILD_CFG` and the bench
could not tell the shipping image from the instrument that had been standing
in for it. `./build.sh` now produces `a95fd8eb…` / `fb1eee67…`.

**Adopting that successor is a decision, not a formality**: it needs the
design bars re-run on it, and it is the natural pair to carry whatever PW
rules on `DSP4_TX_EARLY`. Until then the window deploys `blk_*` and the
tree is one word ahead of it.

### Bars restated this session

`golden_harness` **59/59**, `dsp_validate` **OK**, `check-contract-drift.sh`
clean at `defs-v2026.09.08.4` leaving no diff, `check_shipping_config.sh`
consistent (`DIAG_BUILD_CFG` 0xCF45FF10, `DIAG_BUILD_CFG2` 0xC2010044),
`famverify` **17/20 LIVE, contract 20/20 on all twenty families, 0 FAILED,
three numeric arms BIT_EXACT** on the shipping configuration.

**Not run, and the window should still know**: `busgold`, `bqeverify`,
`fxverify`, `afbverify`, `geqverify`, `xoververify`. They build and scp over
`~/dspboot/chip[12].ldr` and have no `STAGE`; `famverify.sh` has one and was
the only family bar run from a staged path this session.

## 8. Addendum, 2026-09-09 latest — S12: the 29.6 % lever settled, Option A adopted, and what the candidate is

**Three things in §7 are now answered or superseded.**

1. **"The other 29.6 % is `DSP4_SIMD_DYN`, whose audio arm does not pass" —
   it does pass.** The four families that read NO_CAPTURE, the GATE that
   read INERT and the three numeric arms that read NO_STIMULUS were
   **three separate defects in the INSTRUMENT**, not in the audio
   (findings S12-2, S12-3, S12-4). With them fixed, `DSP4_STRIP_FUSED=1
   DSP4_SIMD_DYN=1 DSP4_C2_BQ_GRAPH=0` reads **17 of 20 families LIVE,
   contract 20/20 with 0 FAILED, COMPRESSOR / FADER_PAN / TUBE_SAT
   BIT_EXACT** — verdict for verdict what the shipping pair reads, GATE's
   numeric NO_STIMULUS included.
2. **"The certifying witness does not fit alongside it" — it does now.**
   `ADSP-21564.ldf` gains a second code overflow region into Block 1's
   leftover (S12-1). The default pair is byte-identical across that change;
   it is inert unless code actually overflows Blocks 3 and 2.
3. **S9-2 Option A is RULED AND ADOPTED on chip 2** (PW, 14:3x).
   `DSP4_TX_EARLY=2` is in `shipping.config` unconditionally,
   `DSP4_GATHER_FIRST` stays on beside it, block 16 is ruled the shipping
   block size, and **the through-DSP contract figure is 82 samples /
   1.708 ms**. §7's 66 samples was the `TX_EARLY=0` figure and is
   superseded by the ruling, not by a new measurement.

**And there is one thing §7 did not know: the lever splits, and only half
of it can ship.**

`DSP4_C2_BQ_GRAPH` — chip 2's paired AUX and MAIN biquads, derived from
`DSP4_SIMD_DYN` — **loses parameter changes** (S12-5). A band gain written
into a paired AUX GEQ and a notch gain written into a paired AUX AFB never
become coefficients at all: `geqverify` and `afbverify` both read the
node's own live bank still at **identity** after the host wrote the
parameters, with a modelled response error equal to the whole designed
filter (−12.00000 dB and +18.00000 dB), against **1–3 ulp** on the same
image with the switch off. `bqeverify` passes on the paired cascade kernel
over 36,864 words, so the SIMD arithmetic is right — the fault is
coefficient DELIVERY. It is off in `shipping.config` and PW's ruling on it
is not needed to ship; settling it is one arm's work and it is worth 20 %
of chip 2's budget.

### The decision table

| | shipping `blk_*` | **candidate** (`cand_*`) |
|---|---|---|
| chip 1 / chip 2 md5 | `ac65ad38…` / `e5dce9e4…` | **`fcebc2e1…` / `86662b92…`** |
| switches beyond the file | none | `DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1` |
| `DIAG_BUILD_CFG` / `CFG2` | `0xCF45FF10` / **no second word** — `blk_*` predates it (S11) | `0xCF45FF10` / `0xC201024F`, read back on the part |
| **D24 chip 1** | 71.5 % avg, 84.8 % worst | **59.1 – 59.3 % avg, 72.4 – 72.5 % worst** |
| **D24 chip 2** | 92.7 % avg | **83.2 – 83.5 % avg**, zero overruns |
| **D32 verdict** | DOES NOT FIT (chip 2 112.7 %, 11.26 % missed) | **STILL DOES NOT FIT** — chip 2 102.5 – 102.7 %, 2.37 % missed on both boots |
| through-DSP latency | 82 samples / 1.708 ms (Option A, ruled) | 82 samples / 1.708 ms |
| family walk | 17/20 LIVE, 20/20 contract, 3 BIT_EXACT | **17/20 LIVE, 20/20 contract, 3 BIT_EXACT** |
| `fxverify` / `busgold` / `bqeverify` | OK / BIT-EXACT / PASS | **OK / BIT-EXACT / PASS** |
| `afbverify` / `geqverify` live tone | FAIL, unattributed (S12-9) | identical, to every digit |
| `xoververify` | stalls (S12-8/S12-2 class) | stalls, identically |

**What H1S3/H1S4 and the app must rebuild against: NOTHING NEW.** The
contract is still `defs-v2026.09.08.4`, the address map is unchanged, block
16 is unchanged, and no cell moved. §2 stands exactly as written. The only
host-visible change is the alignment figure, which moves to **82 samples /
1.708 ms** with Option A — and that moves for the SHIPPING pair too,
because the ruling applies to `shipping.config`, not to the candidate.

**Rollback is unchanged** — §3 stands. `~/dspboot/ship_*` and `blk_*` are
untouched and byte-identical; the candidate is staged BESIDE them as
`cand_chip1.ldr` / `cand_chip2.ldr` and nothing boots it unless asked.

**What adopting the candidate buys and costs.** It buys D24 margin — chip 1
from 84.8 % to 72.4 % on the worst block, chip 2 from 92.7 % to 83–87 % —
for no contract change, no PCB change and no host rebuild. It does not buy
D32 on its own: that needs `DSP4_C2_BQ_GRAPH`, and that switch is not
audio-correct yet.

---

## 9. Addendum, 2026-09-10 — S17: the open correctness items closed, and two carried numbers corrected

Write-up `MW/D32/DSP/dsp4-s17-20260910.md`; findings S17-1..S17-6.
**Contract `defs-v2026.09.08.4`, unchanged. No cell moved. §2 stands
exactly as written and the app and H1S3/H1S4 rebuild against nothing.**

**The default build moves by FOUR BYTES per chip**, and that is the whole of
this session's effect on any image. `chip1.ldr` `302d6142701b00e6…`
(421,836 B) and `chip2.ldr` `3b3a6f8e1bb94851…` (280,396 B) against S16's
`20588957…` (421,832 B) / `a1509a2a…` (280,392 B) — one extra store in
`DIAG_CLEAR`. The S16 baseline was rebuilt and reproduces byte for byte, so
the delta is attributed and not inferred.

### What was open, and what it is now

| item | going in | now |
|---|---|---|
| `dyn_state_bound` §3 | FAIL at HEAD, H = 4 reachable | **PASS.** A real overflow in the FIXED arm, reachable by a plain 255 Hz tone (205 wraps at 0 dBFS, 28 at −12); fixed by a contract-worst `H = 4` in the generated initialiser at **+0 bytes, +0 instructions**; proved on the part by `bqguard.sh` (part sizes H = 4, 127 inversions unguarded against 127 predicted, 0 guarded, stream hashes match). **No shipping image was ever exposed** — `DSP4_BQ_FLOAT` forces the guard off. |
| D80 | open, not root-caused, 0.44–0.90 % | **CLOSED as an instrument artefact.** At a settled dwell the two builds are **bit-identical on all 24 readable chip-2 meters, at every capture time**. The 0.44–0.90 % was a meter read 12 s into a curve whose wall-clock constants are stretched 32× by the decimation. `c2gold.sh`'s dwell now derives from `DEC` (214 s, not 12). |
| D79 | open, "chip 2 wants a `gainfix.py`" | **CLOSED.** Same defect as **D71**, already fixed in `build.sh` since 2026-08-31. Address `0x0000` is a live parameter on both chips, which is the whole of the "two faces". 48 chip-boots, 0 corrupt, `_spi_partial_fix` = 0 on every one. **Chip 2's sighting was a mis-phased READ**, not a corrupt parameter. |
| S12-10 | latency instrument nulls on every image | **FIXED**, and it was a one-device-name bug plus a swallowed `aplay` failure, not the overlay. **No reboot was needed and none was taken.** |
| S16-9 | ~30 scripts on the shared scratch slot | **DONE**, 57 files, `check_bench_pins.sh` still canonical. |
| S13-2 | `_proc_cyc_max` latches a config transient | **FIXED** in `DIAG_CLEAR`, both figures printed. |

### The latency row is MEASURED now, not carried

`_maincap` loaded for the runs and `dsp4_logic.a1f6672af6c3` restored
afterwards, IDCODE `0x020a30dd` re-read. 20 reps per boot, **coherent
fraction 100.0 % on every rep of every arm** (against 0.0 % in S12).

| arm | median offset | through-DSP latency |
|---|---|---|
| LOGIC-only reference (`_pisel`) | 14433 | — |
| `DSP4_TX_EARLY=0` (`cap_lat16`) | 14500 | **67 samples** — S11 recorded 66 |
| `DSP4_TX_EARLY=2` (`cap_lat16e2`) | 14515 | **82 samples / 1.708 ms** — S11 recorded 82 |
| S17 tree, shipping defaults, 2 boots | 14516 / 14515 | **83 / 82** |
| **`s16_*`, the recommended pair, 2 boots** | 14517 / 14514 | **84 / 81** |

**The 82 samples / 1.708 ms the window carries is confirmed on the
recommended pair to within the ±2-sample boot-to-boot spread.** §2's
alignment figure is unchanged.

### Two carried capacity numbers corrected

**Chip 1's D24 margin is 28.0 – 28.3 %, not 15.2 %.** §6 cut it to 15.2 % on
S10-8's finding that "chip 1's worst block is consistently 18 % higher than
`_proc_cyc`". That 18 % was the **configuration ladder**, latched in
`_proc_cyc_max` because nothing reset it. Over the dwell alone, three boots:
worst block **71.71 – 71.97 %** of budget, 0.1–0.3 % above `_proc_cyc`, zero
overruns over 135,056 blocks each. The raw latch reproduces S10-8's 277,752
to the digit (277,743), which is what identifies it.

~~**Chip 2's D24 cost is boot-dependent by ten points and is filed, not
explained** (S17-6).~~ **EXPLAINED AND SUPERSEDED, 2026-09-10 (S18-1).**
It is not boot dependence: chip 2's MAIN and SUB dynamics have a cheap
branch below threshold and an expensive one above it, and how many are
above it is what the bench happened to be carrying. Across six boots,
fifteen of 347 chip-2 words differ and every one is a dynamics envelope —
5 live limiters → 92.67–92.84 % with zero overruns, 6 lim + 5 comp →
95.84 %, 7 lim + 7 comp + 1 gate → **103.14 % with 2.999 % of blocks
missed**. Driven deliberately, three boots, reproducible to 0.03 points:
**chip 2 reads 112.3 % of budget and misses 10.9 % of blocks.**

**THE D24 CHIP-2 FIGURE IN THIS NOTE IS A SILENCE FIGURE, AND SO IS EVERY
OTHER `capacity.sh` NUMBER IN THE TREE.** The number a budget has to cover
is the loaded one, and on that number **D24 does not fit on the shipping
default**. Chip 1 is unaffected — its cost is signal-independent, measured
on the same boots. The lever is S16-6's LIMITER on `DSP4_DYN_LUT`
(253.3 → 92.1 c/sample-pair) against chip 2's 18 limiters and 10
compressors; it is PW's call and it is now the most urgent item in this
note. Write-up `MW/D32/DSP/dsp4-s18-20260910.md` §1.

### Decision table, refreshed

| | shipping `blk_*` | **recommended `s16_*`** |
|---|---|---|
| chip 1 / chip 2 md5 | `ac65ad38…` / `e5dce9e4…` | **`a874db96…` / `1403fbcc…`** |
| through-DSP latency | 82 samples / 1.708 ms (ruled, S12) | **82, MEASURED 2026-09-10 (84 / 81 over two boots)** |
| `dyn_state_bound` §3 | not exposed (float arm; guard compiled out) | not exposed; §3 PASSes at HEAD |
| D80 | closed — instrument artefact, not a property of either pair | same |
| D79 | closed — fixed in firmware since 2026-08-31; both pairs carry the fix | same |
| D24 chip 1 worst block | — | **71.7 – 72.0 % measured on the S17 default; `s16_*`'s own row is S16's 60.3 %** |
| symbol map staged beside the pair | yes (`blk_*` predates the practice) | **no** — stage `chipN.sym.json` beside every prefixed pair from now on |
| **D24 chip 2 UNDER LOAD** | **112.3 %, 10.9 % of blocks missed** (S18-1) — the silent 92.7 % is the cheap branch | same; neither pair changes chip 2 |
| chip 1 code pool | 235,064 / 262,144, 27,080 free (388 on the candidate arm) | **`DSP4_SHARED_KERNELS=3` returns 38,634 bytes for +0.69 points of D24 chip 1** — staged `s18_*` `37ce203c…` / `ffbf0ab6…`, default OFF (S18-2) |

**Rollback is unchanged; §3 stands.** `~/dspboot/ship_*` and `blk_*` are
untouched and byte-identical, all 221 staged files intact (223 with S18's
`s18_*`), and the bench was left booted on `blk_*` — `BOOT_STAGE 7` on both
chips, `CHIP_ID` 1 and 2 verified, **zero overruns on both chips over a
30 s dwell after `DIAG_CLEAR`**, `matrix-app` active, CPLD
`dsp4_logic.a1f6672af6c3`.
