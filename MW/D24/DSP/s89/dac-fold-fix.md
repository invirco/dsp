provenance: AI-drafted 2026-09-22 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S89e — the DAC fold, fixed: the gather's position in the block period was a function of the graph's speed

**The one-line answer.** Neither signed audio switch is wrong. `DSP4_SIMD_DYN`
+ `DSP4_DYN_LUT` made chip 2 fast enough to cross a boundary the design never
named: the block gather ran at the END of the block period, so *where in the
period the core wrote the transmit row* — and therefore how far it sat from the
DMA's own read position — was set by the node graph's cycle count and by
nothing else. The fix moves the gather to a **fixed point** in the period. It
costs zero cycles, zero DM and zero latency, and it is on the part.

| | cable-loop THD, drive −12.0 dBFS | drive −22.0 dBFS |
|---|---|---|
| the signed build as it stands (`DSP4_TX_DEFER=0`) | **57.33 / 57.40 / 57.43 %** | 57.30 / 57.37 / 57.43 % |
| the same build with the fix (`DSP4_TX_DEFER=2`) | **0.3212 / 0.3213 / 0.3213 %** | 0.0187 / 0.0196 / 0.0373 % |

Three gated boots each, same cable, same route, same drive; the return level
agrees to 0.01 dB across every arm in this report (−22.21…−22.25 dBFS at −12
drive), so the loop is the same loop throughout. 0.32 % is the **analog loop's
own floor** — six independently built clean arms read it to four significant
figures — not a residue of the defect.

---

## Gate 1 — the falsifiable prediction, and it held

S89d's prediction: *slowing the folding arm should cure the fold without
touching either switch.* `DSP4_GDELAY` burns N core cycles on chip 2
immediately **before** the block gather — the one place that reproduces the
contrast the clean arms actually have, because a delay in the gather's *tail*
runs after the writes it is meant to postpone. `chip1.ldr` is byte-identical
across every delay arm (`90daae5b`), which is the control: the knob is chip-2
only, as designed.

Budget is 327,680 cycles/block at BLOCK=16 and 983.04 MHz.

| arm | delay | gather lands at | loop THD, −12 dBFS drive | |
|---|--:|--:|--:|---|
| `g0` signed, no delay | 0 | 78.81 % | **57.40 %** | folded |
| `d06` | 6,000 | ~80.6 % | 41.28 % | folded |
| `d13` | 13,000 | ~82.8 % | 41.34 % | folded |
| `d20` | 20,000 | ~84.9 % | 57.34 % | folded |
| `g1` | 26,000 | ~86.7 % | **0.3213 %** | **clean** |
| `g2` | 47,000 | ~93.1 % | **0.3217 %** | **clean** |

**The mechanism is confirmed on the fix path.** The threshold is between 20,000
and 26,000 cycles — the gather crossing back through about 85 % of the period —
and S89c independently measured the two clean switch-arms at **86.84 %** and
**93.07 %** of budget against the folding arm's **78.81 %**. The cure threshold
and the clean arms' own positions are the same number, arrived at two different
ways.

## The mechanism, stated so it can be argued with

The chip-2 transmit ring is a **two-row 2D autobuffer** (`dma_config.c`,
`YCNT = 2`): the DDE reads one row while the core fills the other, and
`DSP4_TX_EARLY` picks which row the core gets. The block interrupt comes from
the block-clock RX lane, once per row boundary.

Until now the gather ran at the end of the block period, after
`_chip2_process_all`. So the instant the core wrote the row was
`interrupt + (whatever the graph cost)`. **That is the defect.** Which row is
safe depends on where the core's write falls relative to the DDE's read
position, and the core's write position was a free variable that every capacity
change moved.

The history is the proof:

- **S9-2 (2026-09-09)** measured the safe row at that day's load and adopted
  `DSP4_TX_EARLY=2`: 100.0000 % of frames ordered, against 81.2499 % without.
- **S82 (2026-09-20)** signed `DSP4_SIMD_DYN` + `DSP4_DYN_LUT`, worth 29.6 % +
  the table lookup's 74.9 % of the gain computer. Chip 2 went from about 93 %
  of budget to **78.81 %** — the gather moved roughly 14 % of a period earlier,
  across the boundary, onto the wrong side of the DDE.
- **S88-1 / S89** found 57–60 % THD at the XLR with every digital probe clean.
- **S89d**'s transmit stamp measured it exactly: **12.5006 %** of block
  transitions wrong, one frame per 16-sample block, frame 15, carrying **+2
  blocks** — the content the core wrote for the next time round that row.
- **S89e gate 1** closes it: slow the core by 7.9 % of budget, touch no switch,
  and the fold goes.

Two further measurements on the part nail the geometry, and both are in this
session's data:

- `DSP4_TX_EARLY=0` on the signed switches, no delay, is **clean** (0.3215 % /
  0.0192 %). Flipping the row cures it exactly as delaying the write does,
  because both move the write to the other side of the DDE's read.
- With the gather deferred, `DSP4_TX_EARLY=0` **folds again** (57.43 %) while
  `DSP4_TX_EARLY=2` is clean. The deferred write is half a period from where it
  was, so the safe row flips back. That is the complementary control: this is a
  geometry, not a margin.

**Which is exactly why `DSP4_TX_EARLY=0` is not the fix.** It is the same
load-dependent coin, landing the other way up. The next capacity change turns
it over again, and nothing in the tree would say so.

## Gate 2 — the fix: `DSP4_TX_DEFER`

**The invariant restored: the moment the core writes the transmit row must not
depend on how long the node graph took.**

The gather moves out of the end of the block loop and into a fixed point —
`src/main.asm`, immediately after the block interrupt has been taken and
**before** `_blk_latch_bufs` advances the row. At that instant `_tx_active_buf`
still names the row the *previous* block was gathered for, and the node output
slots still hold that block's samples, because this block's graph has not run
yet. Nothing else changes.

    src/main.asm     the deferred gather loop + DSP4_TX_DEFER_HERE and its
                     three compile-time guards; the end-of-block gather and
                     its transmit stamp suppressed under the switch; the
                     _proc_cyc window opened early on a deferred build
    build.sh         DSP4_TX_DEFER, per-chip mask, default 0
    shipping.config  DSP4_TX_DEFER=2
    src/diag.h       DIAG_BUILD_CFG3 bits 7..6; DSP4_GDELAY into the
                     instrument sum
    tools/dsp/cfg_words.py, tools/pi/dsp4_buildcfg.py,
    check_shipping_config.sh   the field in all three mirrors

**What it costs: nothing.** The gather runs once per block either way — the
same 24 outputs × 16 samples, the same instructions, moved. No staging buffer,
no copy, no third row, no change to the DMA topology or to the
one-interrupt-one-row mapping the phase fix and the diagnostics rest on. It
adds no output latency: the row written is the same row, written before the DDE
returns to it, so the contract figure of 82 samples / 1.708 ms is unmoved.

**It is chip 2 only (mask 2).** Chip 1's inter-chip gather has the same shape
and the same latent defect — S9-2 recorded that and noted the transmit stamp
cannot see it — and is deliberately not deferred here, so chip 1's code does
not move on this dispatch. Proved rather than asserted: with the switch off the
pair rebuilds **byte for byte** as the S82 signed images
(`chip1.ldr e3e25a79…`, `chip2.ldr 41a6b913…`), and with it on **chip 1's image
differs in exactly ONE BYTE**, which is its own `DIAG_BUILD_CFG3` stamp
(0x26 → 0xA6).

### Why the dispatch's option (1) was not used

S89d recommended gating the gather's final frame on the SPORT transmit FIFO
draining (`SPORT_CTL.DXS`). **That cannot be made to hold, and not because the
poll is expensive.** The chip-2 SPORT transmits continuously at 48 kHz: its
transmit FIFO is *never* empty while audio is flowing, so a poll for "drained"
either never returns or returns a status that says nothing about the row the
core is about to write. The dispatch named triple-buffering (option 3) as the
fallback; the deferred gather reaches the same invariant for none of its price
— no extra block of DM, no extra block of latency, and no change to the DMA
topology — so it was taken instead. Triple-buffering remains the answer if the
fixed point ever proves not to be far enough from the DDE on some other
product's timing; this one is measured at three different graph speeds below.

### The proof it is load-independent, which is the actual root cause

The unfixed build is clean at some graph speeds and folds at others. The fixed
build was measured at **three** speeds — the signed graph and the same graph
slowed by 26,000 and 47,000 cycles, i.e. 78.8 %, 86.7 % and 93.1 % of budget:

| arm | `TX_DEFER` | `TX_EARLY` | delay | loop THD −12 dBFS | |
|---|--:|--:|--:|--:|---|
| `cap_ctl` / `g0` | 0 | 2 | 0 | 57.33…57.43 % | **folded** |
| `t0` | 0 | 0 | 0 | 0.3215 % | clean |
| `g1` | 0 | 2 | 26,000 | 0.3213 % | clean |
| `g2` | 0 | 2 | 47,000 | 0.3217 % | clean |
| **`x2` (the fix)** | **2** | **2** | 0 | **0.3212…0.3213 %** | **clean** |
| `x2d26` | 2 | 2 | 26,000 | 0.3212 % | clean |
| `x2d47` | 2 | 2 | 47,000 | 0.3215 % | clean |
| `x0` | 2 | 0 | 0 | 57.43 % | folded |

Three speeds, one verdict. That is the property the design lacked.

### The cycle window had to move with the gather

`_proc_cyc` is the number every capacity table is scored against, and it is
taken between `_proc_t0`/`_proc_c0` and the close after the node graph. The
deferred gather runs before that point, so leaving the window where it was
would have dropped the whole gather — about 6,000 cycles, 1.8 % of budget — out
of the measurement while the part still paid for it, and **the fixed build
would have read cheaper than the folding one for no reason but where a
timestamp sits.** That is a capacity figure taken on a different build, which is
the fault `shipping.config` exists for. On a deferred build the window opens
before the gather and closes where it always did; a build without the switch
keeps the original placement byte for byte, so every control arm and every
number already on record stays comparable.

## Gate 3 — the triple, and the re-price

**The signed triple moves in the third word only:**

    DIAG_BUILD_CFG   0xCF45FF10    unchanged
    DIAG_BUILD_CFG2  0xE2018E6F    unchanged
    DIAG_BUILD_CFG3  0xC47C0F26 -> 0xC47C0FA6

The named change is `DSP4_TX_DEFER=2`, bits 7..6 of `DIAG_BUILD_CFG3` — two of
the three bits S80 left unallocated in that word. `check_shipping_config.sh`
computes it from `build.sh` + `shipping.config` and from the bench mirror
independently and the two agree.

### The re-price, and the part of gate 3 that this dispatch's own bench rules forbid

**The driven row could not be taken.** `capacity.sh --driven` needs the
`driveall` LOGIC bitstream on the part — the stimulus belongs in the CPLD so
that the silent and driven arms are the same image, the same boot and the same
clock — and this dispatch's bench rules say *"shipping CPLD `d02d83b3cc22`
stays in flash — no CPLD flash in this dispatch"*. The 84.47 % bar is a driven
number (S86, D24, chip 1). This is S89b-Q1 unanswered, and it is a 🔴 note
below, not a silent omission.

What was taken instead is the **silent row, both products, both chips, two
boots each** — sixteen chip-rows, `tag: silence`, 135,000 blocks a row, **zero
missed blocks in every one**. The fix adds no instructions and does not touch
the node graph, so the silent delta bounds the driven delta; that is an
argument, and it is stated as one.

| product | chip | control `DSP4_TX_DEFER=0` | fix `DSP4_TX_DEFER=2` | Δ |
|---|--:|--:|--:|--:|
| D24 | 1 | 43.13 / 43.13 % | 42.94 / 43.13 % | **−0.09** |
| D24 | 2 | 77.50 / 77.52 % | 77.60 / 77.41 % | **0.00** |
| D32 | 1 | 54.96 / 55.11 % | 55.22 / 54.78 % | **−0.04** |
| D32 | 2 | 92.43 / 92.71 % | 92.71 / 92.69 % | **+0.13** |

Worst block after clear, the number a budget has to cover:

| product | chip | control | fix | Δ |
|---|--:|--:|--:|--:|
| D24 | 1 | 43.33 / 43.35 % | 43.25 / 43.13 % | −0.15 |
| D24 | 2 | 77.62 / 77.80 % | 77.75 / 77.92 % | +0.13 |
| D32 | 1 | 55.24 / 55.14 % | 55.03 / 55.04 % | −0.16 |
| D32 | 2 | 92.75 / 92.75 % | 92.85 / 92.96 % | +0.16 |

**Chip 1 is the null arm and it is what makes those deltas a measurement.**
Chip 1's code is byte-identical between the two builds — the images differ in
one byte and that byte is its config stamp — so its four deltas are the
instrument against itself, and they swing **−0.16 to +0.10 points**. Chip 2's
largest delta is +0.16. The fix is inside the resolution of the instrument
measuring it, at the point where the measurement window has also just grown to
cover `_blk_latch_bufs` and the decimate test.

`_proc_cyc_max` before the clear reads 355–377 % on some rows; that is S21-6's
diag-tick artefact and the boot-and-config transient, which is why
`proc_cyc_max_after_clear` is the column above. **It appears on both arms**
(control D24 chip 2 and D32 chip 1, fix D32 chip 1), so it is not a difference
between them.

Reports: `MW/D32/DSP/SHARC/goldens/cap-s89e_{ctl,fix}-d24-r{1,2}.json` and
`cap-s89e_{ctl32,fix32}-d32-r{1,2}.json`.

## Gate 4 — the acceptance leg

`tools/pi/dsp4_loop_thd.sh` is rewritten from a printer into a leg with a
**verdict and an exit code** (0 PASS / 1 FAIL / 2 INCONCLUSIVE), and
`MW/D32/DSP/SHARC/loopthd.sh` is the build-and-stage half that runs it on any
named configuration the way `capacity.sh` runs a capacity row. `T3L` is in
`tools/accept/battery.csv` with three limits in `tools/accept/limits.csv`, and
the measured references are written into `docs/acceptance-audio-layer.md` —
this repo's equivalent of mx26's `docs/spec-audio-test-set.md`.

The limit is **1 %**, and it is the loop's own floor plus margin, not a product
specification: six independent clean arms read 0.321…0.360 % and the defect
reads 57.3…59.7 %, so 1 % fails the defect by 35 dB and passes the floor by
10 dB with nothing in between.

**Both directions, on the part, same cable, same levels** — because a check
that cannot fail proves nothing, and this bench has produced two of those:

    ARM=s89e ./loopthd.sh                      -22.23 dBFS,  0.3216 %  PASS  exit 0
    ARM=ctl DSP4_TX_DEFER=0 ./loopthd.sh       -22.23 dBFS, 57.4803 %  FAIL  exit 1

Three traps are now enforced by the leg rather than remembered:

- **A pinned lane reads a plausible THD.** This session's first readings were
  taken with the 595 preamp chain wherever `matrix-app` had left it, and the
  loop returned **−0.7 dBFS at every drive from −12 to −42 dBFS** — 30 dB of
  stimulus moving the reading 0.9 dB — with a *clean* build reading 39 % THD.
  The return-level window makes that INCONCLUSIVE instead of a fail. The chain
  was written to gain code 0 (all-zero 25-byte image, VERIFIED 200/200) and
  every number in this report is from after that.
- **A folded inter-chip link looks exactly like a folded DAC** (S89-1: ~56 %,
  right level). The leg boots only through `dsp4_boot_linked.sh`.
- **A route that was never asserted reads as a pass.** The first run of the new
  `loopthd.sh` staged everything except `s89_set.py` — which lives in this repo
  and not in `/home/app/dspboot`, so the stage directory's symlink loop never
  picked it up — and the leg wrote its route with stderr discarded. It measured
  the *default* configuration, where the donor strip's own compressor is ON with
  a threshold near −22 dBFS (S70-3): 10 dB of drive moved the return 4.9 dB and
  the leg said PASS at 0.238 %. The leg now checks the route write's exit status
  and **requires the return to track the drive within 2 dB**, which catches a
  compressing, limiting or railing path — including the pinned-chain case above,
  which the level window alone did not.

**The lane is Monitor L → MIC 6**, where PW left the cable during S89's TRS
set. It is alive and it reads: no cable move was asked for. `OSC_STRIP` /
`MEAS_STRIP` name the two ends, so moving the cable back to AUX 1 → MIC 6 is an
environment variable and not an edit.

## What a `candidate-s89` would contain

`~/dspboot/candidate-s82` is **untouched** and its md5s are unmoved. A
`candidate-s89` would be:

    chip1.ldr  5b0629f0b39ed6e7c93e629b2d593803
    chip2.ldr  9da000f0f95ea0165f5fab43ba96e06e

built from `shipping.config` at `DSP4_TX_DEFER=2` with nothing else moved
(`DSP4_TEST_NODES=0`, so this is the shipping image and not the arm the loop
row measured). It must read back

    DIAG_BUILD_CFG 0xCF45FF10  DIAG_BUILD_CFG2 0xE2018E6F  DIAG_BUILD_CFG3 0xC47C0FA6

The control it replaces, `DSP4_TX_DEFER=0`, rebuilds the S82 pair byte for byte
(`e3e25a79…` / `41a6b913…`), so the *only* difference between the staged
candidate and what is signed today is this switch. Chip 1 differs from the S82
image in one byte and that byte is its own config stamp.

Staging it is PW's call and was not done.

## Unit as found

Shipping CPLD `d02d83b3cc22` untouched — **no CPLD was flashed in this
session**. `~/dspboot/candidate-s82` untouched. S87's four uncommitted files
untouched. GPIO27 `ip pu` throughout (it was found `ip pd` after a Pi reboot,
which is the CS_M defect and presents as "cannot phase the link").

Two deliberate differences, both needed for the measurement and both the hub's
to restore:

- **AN_EN (GPIO26) was raised** `op dh` and `matrix-app` stopped. Stopping the
  app drops AN_EN and the app will not raise it again (S49-15).
- **The 595 preamp chain is LEFT at gain code 0** (all-zero 25-byte image,
  VERIFIED 200/200). It had to be written: `matrix-app` had left it at a gain
  that pinned the loop return at −0.7 dBFS at every drive. **Restarting
  `matrix-app` does not demonstrably put it back** — its log records only
  `Boot.Init() - AN_EN gated … bring-up runs after S_RUN` and no chain write —
  so this is a real difference from as-found and not a claim that it was
  restored. Code 0 is the S88 reference state (minimum gain, phantom off,
  unmuted), so it is benign. What the chain held before, as pass 1 of the write
  shifted it out, was

      00 13 6E 20 00 00 00 00 00 E0 FE 00 00 00 00 00 00 E0 FE 00 00 00 00 00 00

  recorded here for whoever wants it back. Send position 0 is first.

`matrix-app` is active and **3 of 3 MCUs verified** (H1S1, H1S3, H1S4), read
from the whole of `/home/app/logs/log` — the app rewrites that file on start,
so "lines since a mark" is empty on every restart but the first (S49-7).
