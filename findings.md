provenance: AI-drafted 2026-09-08 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# findings — dsp spoke

Numbered findings D1–D8x are recorded in `review-dsp-20260828.md` and in the
dispatch blocks of `tasks.md`. This file carries findings raised by dispatched
sessions after that review, newest first.

## THE ORDER DEFECT: root-caused in the transmit path and fixed, and a capacity defect underneath it (2026-09-09, session 34)

Session: the chip-2 transmit path instrumented with a block counter on
the wire, the ORDER DEFECT root-caused to a ping/pong PHASE error and
fixed (100.0000 % ordered on the part), and a second, independent defect
uncovered by the same instrument — the block loop does not fit its
budget. Write-up `MW/D32/DSP/dsp4-order-defect-20260909.md`. Contract
`defs-v2026.09.08.4`, unchanged. New pair staged BESIDE the window pair
as `~/dspboot/tx_chip1.ldr` `21f9fdc1` / `tx_chip2.ldr` `de14981f`; the
window pair `093c609f` / `2ba0e464` is byte-identical to as-found and
`DSP4_BLK_LATCH=0` rebuilds it exactly. Bench restored to the shipping
bitstream `a1f6672af6c3` and the `dsp4-pcm-slave` overlay.

### S8-1 — the ORDER DEFECT is a ping/pong PHASE error, and it is FIXED

**Severity: MAJOR (firmware, every chip-2 output lane). Status: FIXED and
proven on the part.**

S7-5 localised the defect to the chip-2 transmit path and left three
candidates: the DMA ring indexing, the block hand-off, and the TX slot
tables. The hand-off is the one, and the mechanism is not an indexing
bug — it is the PHASE of the ping/pong itself.

`_set_tx_bufs` started the core on the PING half and `_sport_dma_work`
toggled it at each block interrupt. The DDE also starts each region on
its ping row and moves to pong at the first row boundary — the same edge
that raises that interrupt. So the core was always writing the half the
channel was clocking onto the wire. The slots the DDE had not reached
yet went out carrying the block the gather had just written; the slots
it had already passed went out carrying whatever that half held from two
blocks earlier. Every transmitted 8-sample window was assembled from up
to three consecutive blocks, split at a fixed sample.

**The instrument, not an inference.** `SHARC/src/tx_probe.asm`
(`DSP4_TXPROBE=1`) stamps chip 2's TX lane 3 slot 1 — driven onto the
wire, written by no node — with `(block counter << 8) | (half << 4) |
sample index`, immediately after the gather has written slot 0 of the
same frame. `_maincap` presents slot 0 as the Pi capture's LEFT channel
and slot 1 as its RIGHT, latched from ONE DSP frame (S7-1), so a recorded
stereo frame is a coherent (audio, stamp) pair. The stamp is in order by
construction, so what comes back off the wire settles it without any
appeal to the audio. Decoded, with the node graph out of the way
(`DSP4_BLOCK_MASK=5`) so that ZERO blocks were missed:

| build | blocks missed | stamp transitions +1 |
|---|---|---|
| pre-fix | 0.0 % | 143,999 of 191,999 = **75.0000 %** |
| pointer latched only | 0.0 % | 143,999 of 191,999 = 75.0000 % |
| phase corrected | 0.0 % | 191,999 of 191,999 = **100.0000 %** |

The pre-fix delta histogram has exactly three entries — `+1` ×143,999,
`-15` ×24,000, `+17` ×24,000 — one of each jump per 8-sample window over
24,000 windows, which is what "a fixed split point" means quantitatively.
The fixed histogram has ONE entry. The sample-index field is 24,000 of
each of 0–7 in every build, so the position inside the window was never
in doubt; only the block was.

The fix is `DSP4_BLK_LATCH=1` (default), in `src/sport_init.asm`:

* the block ISR advances a PENDING pair of half-pointers and
  `_blk_latch_bufs` moves them into the active pair once per block,
  before the sample loop — the generated `_scatter_chipN`/`_gather_chipN`
  reload the active pointer on EVERY sample, so the ISR used to retarget
  them mid-block. On the part this alone changed nothing (row 2 above);
  it is a real hazard closed, not the defect;
* the core starts on PONG, so it fills the row the DDE has just finished
  with and that row goes out on the next block. That is the defect, and
  row 3 is the fix.

`DSP4_BLK_LATCH=0` rebuilds `093c609f` / `2ba0e464` byte for byte, so the
control column is measured rather than quoted.

**It is not one lane.** The lane the instrument measured, `o_dspb[3]`, is
the CPLD's `dac_main` — a converter lane, not a measurement lane, and
slot 0 of it is `C2_MAIN_ST_OUT`. `_gather_chip2` writes all twenty
chip-2 outputs from the same half in the same loop through one pointer,
so the other four output lanes (AUX_OUT 01–12, MAIN_OUT 01–04, MON_OUT,
CODEC_AUX_OUT, SUB_OUT) carried the identical splice and are fixed by the
identical pointer. They cannot be witnessed directly on this bench —
LOGIC captures only `o_dspb[3]` and no analogue loopback is wired — and
what would settle them is a `_maincap`-style build capturing a slot of
`o_dspb[0..2]`. Chip 1's inter-chip TX and both chips' RX regions carry
the same off-by-one-half and get the same fix; the RX side is not
separately witnessed, because the only observable that could witness it
is the audio through the loop, and that is dominated by S8-2.

Cost: two DM words and one call per block. On-part `_proc_cyc` reads
286,757 before and 282,308 after on chip 2 — the instrument reports the
LAST pass and its pass-to-pass spread is wider than the change.

### S8-2 — underneath it: the block loop does not fit the block, and misses three blocks in four

**Severity: MAJOR (firmware/capacity, open). Status: measured, NOT fixed
— needs its own dispatch.**

The same instrument found a second defect that the first was hiding. With
the phase fixed, the staircase is still only 33 % exact through the full
D24 graph, because the core is not writing most of the blocks at all:

| what | chip 1 | chip 2 |
|---|---|---|
| blocks missed (`DIAG_BLK_OVERRUN` / `FRAME_COUNT`, 8 s) | **75.1 %** | **70.9 %** |
| `_proc_cyc`, shipping per-sample build | 330,389 | 286,757 |
| `_proc_cyc`, `DSP4_BLOCK_KERNELS=1` | 134,325 | 170,622 |
| `_proc_cyc`, plumbing only (`DSP4_BLOCK_MASK=5`) | — | 13,964 |
| budget, BLOCK=8 at 982.98 MHz | 163,830 | 163,830 |

The two instruments agree to a tenth of a percent: chip 2 misses 71.4 %
of blocks and the block counter on the wire advances at 28.7 % of the
frame rate. A half that is not rewritten is transmitted again, so the
wire carries stale whole blocks — which is the ±225-block tail S7-5
measured, and it is why the staircase does not come back exact even with
the transmit path proven in order.

**Every capacity number on record was taken in a configuration that does
not ship.** The `.4` record (chip 1 202,786 / chip 2 226,442 against
327,680) is a BLOCK=16 `DSP4_BLOCK_KERNELS=1` build. The shipping default
is BLOCK=8 per-sample, and that costs 2.0x (chip 1) and 1.75x (chip 2) of
the block-8 budget. Block kernels alone do not close it: chip 2 still
reads 170,622 against 163,830 and misses 51.9 % of blocks — and a loop
that takes 1.04 block periods misses every second block, not 4 % of them,
because `_block_ready` is a flag and not a queue.

The causal chain is closed by reducing the load until the loop nearly
fits. With `DSP4_BLOCK_KERNELS=1`, the phase fix, and the runtime masks
poked down to one strip and one aux, chip 1 misses 0.0 % and chip 2 misses
30.3 %, and the staircase through the whole chip-2 graph goes from
**32.87 % to 91.92 % exact** over 96,000 frames. The residual is the
residual overrun; nothing else moved.

CCLK is not the reason: 982.98 MHz measured against the 983.04 target, and
the block rate is 5,999.9/s against 6,000.

### S8-3 — the bench recipe was booting chip 2 with chip 1's firmware

**Severity: MAJOR (bench procedure, invalidates measurements). Status:
FIXED in the session's own scripts; the shared run scripts still carry
it.**

`sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0` — the line every run
script executes after an OpenOCD flash, to hand the JTAG pins back — puts
GPIO24 into ALT0, which on this part is `SD0_DAT2`, not a deasserted chip
select. Chip 2's CS then sits asserted while chip 1's boot stream is
clocked out, chip 2 loads `chip1.ldr`, and the card comes up as two chip
1s. Six consecutive boots did this before the pins were read back;
holding GPIO 6 and 24 as outputs driven HIGH (`pinctrl set 6,24 op dh`)
and giving only 7, 9, 10, 11, 22, 23, 25 to `a0` booted chip 2 correctly
first time, every time after.

`dsp4_scope.check_chip` catches it — "link answers as CHIP 1, expected 2"
— and that is the only reason it was ever caught; `dsp4_diag.py` reports
it as a healthy part with a wrong CHIP_ID, and any measurement taken
through the diag link alone would have been fiction. `lat_run.sh`,
`famverify_run.sh` and `profile_run.sh` retry the boot until
`dsp4_diag.py --chip 2` answers 2, which recovers from it by accident;
they should hold the CS lines instead.

Two smaller traps found with it: `dsp4_diag.py --help` documents chip 2's
CS as GPIO 7 while the code (and `dsp4_scope.CS_GPIO`) uses 24; and
`dsp4_diag.py --chip 2` without `--rdy-gpio 12` uses chip 1's ready line
and cannot phase the link at all.

### S8-4 — the through-DSP latency did not move

**Severity: n/a (result). Status: measured.**

Re-measured on the fixed pair with the same instrument
(`dsp4_dsp_latency.py`, 10 reps x 2 boots): minimum 14,508 and 14,509,
medians 14,512 / 14,517, spread 13 and 15, worst margin over the runner-up
x16.8. The pre-fix session read a minimum of 14,504 on both boots. The
+4 samples is inside the instrument's own spread on either arm, so the
72-sample / 1.500 ms figure of S7-6 stands, and the boot-to-boot part is
again zero (14,508 against 14,509, one sample).

Coherent fraction 33.1–33.7 %, which is S8-2 and not the transmit path.

## The capture path made frame-locked, and the design given an ID (2026-09-09, session 33)

Session: a frame-locked CM4 capture and a readable design-ID register in
one bitstream, and the through-DSP arm re-diagnosed from measurement
rather than from the symptom. Write-up:
`MW/D32/DSP/dsp4-loop-latency-20260909.md` §7. Contract
`defs-v2026.09.08.4`, unchanged. Images unchanged: the window pair
chip1 `093c609f` / chip2 `2ba0e464`, run from a separate staging path
(`~/s32`) so `~/dspboot` was not touched. New bitstream
`dsp4_logic_maincap.d903ae1ac4a9`, design ID `32'hae1ac4a9`, 404/1270 LE,
Fmax 68.66 MHz.

### S7-1 — the CM4 capture spliced every word out of TWO DSP frames

**Severity: MAJOR (LOGIC, shipping path). Status: FIXED and proven on the part.**

`cap_flat` is rewritten slot by slot as the DSP frame arrives — slot `s`
completes at `frame_pos = (s+1)*128` — while the Pi's read-out of one
32-bit word spans nearly the whole frame (bit 31 launches around
`frame_pos` 32, bit 0 around 536). The read-out was walking the LIVE
register file, so for most `CAP_SLOT` choices the register was
overwritten part-way through and **the word the CM4 recorded was spliced
from two consecutive DSP frames at a fixed bit position**.

Measured, not inferred. With the DSP alternating two known words
A = `0x12345670` and B = `0x7BCDEF80` every frame, the old bitstream
(`dsp4_logic_maincap.1216e35175cb`) returned, over 100,000 settled
frames, exactly two values: `0x03F7CA48` and `0x1786C9A8` — **neither of
them A or B**. The new bitstream on the same stimulus returns
`0x17F7CA48` and `0x0386C9A8`, also two values, 50,000 each.

The two are related by the splice model exactly, in both phases:

```
old[n] = { true[n-1][31:25], true[n][24:0] }
  {0x1786C9A8[31:25], 0x03F7CA48[24:0]} = 0x17F7CA48   <- new, phase 1
  {0x03F7CA48[31:25], 0x1786C9A8[24:0]} = 0x0386C9A8   <- new, phase 2
```

Bit 25 is where the arithmetic says it should be: slot 0 completes at
`frame_pos` 128, which is `out_word_pos` 6, which is bit 25. The same
arithmetic puts the SHIPPING return (slot 2, complete at `frame_pos`
384) at **bit 9** — so the product's CM4 return had the defect too, three
bits into the audio, and would have shipped with it.

Fixed by reading a snapshot instead of the live file: both presented
slots are latched together one Pi word before the left read-out starts,
so a recorded stereo frame is a coherent pair from ONE DSP frame. Cost:
one extra frame of constant latency, 64 flip-flops. `PI_SELFTEST` is
bit-identical before and after — its source words are written outside the
read-out window — which is what makes the fix testable: `_pisel` must not
move, and it does not.

### S7-2 — and the period decode was one BCK early, hidden by a constant that cancelled it

**Severity: major (LOGIC). Status: FIXED.**

`in_period = frame_pos[9:2] - 8'd1` named the incoming bit by the period
BEFORE the one in which it is sampled. Period indices name the SAMPLING
period on the transmit side (`out_period` adds 1 because the launch is
one period earlier); MFD=1 puts slot 0 bit 31 on the rising edge after
the one that reads FS high, and FS is high through period 255, so slot 0
bit 31 is sampled at period 0. No offset belongs there.

The consequence was that `cap_flat[s]` held `{slot_s[30:0], slot_s+1[31]}`
— every word one bit left, with the NEXT slot's MSB in its LSB. That is
precisely the symptom recorded on 2026-08-23 ("the expected words shifted
LEFT exactly one bit, 100% stable over 96,000 frames"), and it was
answered by adding `CAP_EXTRA_DELAY = 1` to the read-out, which slid the
read back over the error. **The two errors cancelled in every bit except
the top one, which came from the other slot** — invisible on every word
the bench ever sent, because all of them had bit 31 clear.

Both are now correct on their own terms: `in_period = frame_pos[9:2]`,
`CAP_EXTRA_DELAY = 0`, plain Philips I2S on the link. Proven on the part
by the ID readback, which recovers a 32-bit constant exactly — 2,175
reply frames, ONE distinct reply word.

### S7-3 — nothing had ever simulated the capture direction

**Severity: moderate (process). Status: FIXED.**

`sim/tb_pcm_reframe.v` instantiates the re-framer with `tdm_in` and
`bck8_sample` **dangling** — it tests the Pi → DSP direction only. The
sim gate was therefore green through both defects above, and both are of
the kind a testbench catches on the first run.

Added `sim/tb_pcm_capture.v` with two new models
(`model_tdm_tx.v`, `model_pi_i2s_rx.v`). The DSP transmits a different
word in every slot on every frame, so a read-out that walks a live
register file cannot pass: the check is not "the value looks plausible"
but "L and R are both exactly the words of ONE frame, the same frame, at
a constant lag", over both slot configurations (0/1 and the shipping
2/3). It fails on the old RTL and passes on the new. The sim gate is now
4 testbenches.

Writing it also cost two model bugs worth recording, because both are
traps for the next person: an I2S receiver that resets its bit counter on
the WS edge loses the last bit of every word (the word runs ACROSS the
boundary), and a TDM transmitter that samples FS on the same falling edge
it launches data on races the clkgen's own NBA update and starts its
frame one BCK early. FS is sampled on the rising edge, data launched on
the falling one, in the model as on the part.

### S7-4 — S5-9 closed: the design carries an ID, and it is readable with no hands

**Severity: minor (verifiability). Status: DONE, proven on the part.**

`build.sh` derives `DSP4_DESIGN_ID` as the low 32 bits of the artifact
hash and `DSP4_CFG_BITS` as a five-bit configuration field (loopback,
pi_selftest, pi_maincap, pi_tdm8, shipping) and passes both in as Verilog
macros. They are GENERATED, never typed, and they do not feed the hash —
so "read the register, compare to the manifest" is a real check.

MAX V has no configuration readback over SVF, the DSPs have no link into
this CPLD, and the TEST pins land on a DNP header, so the one path off
the part that needs no hands is the CM4's PCM capture. The register is
therefore read by KNOCKING: the Pi plays `{L = 0xD5D51D1D,
R = 0x2A2AE2E2}` (R the exact bit-inverse of L) and LOGIC answers
`{L = design_id, R = 0xD594<cfg_bits>}` for 128 frames. Reader:
`tools/pi/dsp4_logic_id.py`.

On the part, after the flash:

```
design_id: 32'hae1ac4a9   cfg_bits: 16'h0004   pi_maincap
  reply frames 2175 of 144000 captured, 1 distinct reply word
  MATCHES --expect ae1ac4a9
```

It is built in EVERY configuration, which is the point: every future
flash answers "what are you?" in one `aplay` plus one `arecord`. It is
shipping-safe by scope — a false trigger needs a specific 64-bit pair and
costs 128 frames (2.7 ms) of the CM4's own return stream, and touches
nothing on the DSP-facing side, the DAC lanes, the NET lanes or the
panel.

### S7-5 — the through-DSP arm is NOT a capture problem: whole 8-sample BLOCKS arrive from the wrong place

**Severity: MAJOR (firmware, open). Status: mechanism measured and localised, NOT fixed.**

S6-4 named the `_maincap` capture path as the thing that "scrambles the
order". That was the wrong suspect, and the frame-lock fix (S7-1) — which
is a real defect and a real fix — does not change this result by one
percent: the staircase scores 32.87 % exact before the fix and 32.87 %
after it.

What the arm actually does, measured with a two-level stimulus at
different periods (`steptest.py`, 90,000 settled frames each):

| stimulus period | runs observed | runs if clean | verdict |
|---|---|---|---|
| 2 frames (HOLD 1) | 90,000 | 90,001 | **exact** |
| 4 frames (HOLD 2) | 45,001 | 45,001 | **exact** |
| 8 frames (HOLD 4) | 22,500 | 22,501 | **exact** |
| 16 frames (HOLD 8) | 40,211 | 11,251 | scrambled |
| 32 frames (HOLD 16) | 42,396 | 5,626 | scrambled |
| 128 frames (HOLD 64) | 42,867 | 1,407 | scrambled |

**Any pattern whose period divides 8 survives exactly; anything longer is
scrambled.** So the displacement is a non-zero multiple of 8: every
sample arrives at the RIGHT position inside its 8-sample block, from the
WRONG block. `BLOCK = 8` on these images.

Two more measurements pin it down. The chain is **bit-transparent** —
across every one of those runs the capture contained ONLY the two exact
stimulus values and zero, never an intermediate, so nothing is filtering
and nothing is arithmetically wrong. And the displacement histogram is
**independent of signal magnitude** (mean −10.1 steps in every one of six
250-step buckets from index 0 to 1500, min −28 max +1 in all of them),
so it is a time offset and not a gain or rounding error. About a third of
blocks are in the right place; the rest are drawn from roughly the last
225 blocks (≈1,800 frames, ≈37 ms).

Where it is NOT: the CM4 (`_pisel` returns 96,000 of 96,000 exact on the
identical staircase through the identical ALSA path, 100.00 %); the CPLD
capture (`cap_flat` is one frame deep and cannot deliver a sample from
1,800 frames ago, and is now proven coherent by S7-1); the chip-2 node
graph (`_buf_C2_PI_IN`, `_buf_C2_MIX_MAIN_L`, `_buf_C2_MAIN_FDR`,
`_buf_C2_MAIN_DLY`, `_buf_C2_MAIN_ST_OUT` read non-decreasing on 36 of 38
consecutive samples while the staircase plays, advancing at 48,000
frames/s — a ±1,800-frame scramble on the compute side could not do
that).

That leaves the chip-2 transmit path — the SPORT3 TX DMA and whatever
fills its buffer — as where a block-granular buffer is being read at an
index that is not locked to the frame. **That is the next dispatch**, and
it is not cosmetic: if the same machinery serves the converter lanes,
two-thirds of every output block is coming from a random point in the
last 37 ms.

Also retired by this: the 2026-09-09 note that a constant returns
"bit-exact" and a staircase does not, offered as evidence about the
capture. Both are explained by the block model — a constant is
period-1 — and neither says anything about the capture path.

### S7-6 — the through-DSP loop latency, measured, with the DSP block term visible

**Severity: n/a (result). Status: measured.**

A per-word offset vote cannot be used on this arm — with a third of the
words coherent it finds spurious modes, which is exactly how the
2026-09-08 figure of 14,550 was produced. `tools/pi/dsp4_dsp_latency.py`
scores every candidate offset by the fraction of frames carrying the
exact expected value and reports the answer only with its margin over the
runner-up two plateaus away. The coherent third puts a sharp peak at the
true offset; a spurious mode has no peak.

See `MW/D32/DSP/dsp4-loop-latency-20260909.md` §7 for the table. The
margin was never below x16 on any rep, so the figure is quotable in a way
the 2026-09-08 one was not.

## The channel and aux masks get readers (2026-09-09, session 32)

Session: `CFG_CHAN_MASK` / `CFG_AUX_MASK` given readers, D24 capacity
restated on the masked image, the through-DSP arm attempted again.
Write-up: `MW/D32/DSP/dsp4-chan-mask-20260909.md`. Contract
`defs-v2026.09.08.4`, unchanged. New images: chip1
`093c609f622cf805e7f675f1e2497a19` / chip2
`2ba0e464e9679bd2e1b1c3c2a6f08744`; `DSP4_CHAN_MASK=0` rebuilds the
previous pair `602a0feb` / `b1325022` byte for byte.

### S6-1 — S5-7 fixed: the masks are read, and a masked strip is SKIPPED

**Severity: MAJOR (firmware, window item). Status: FIXED and measured.**

`_chan_mask` and `_aux_mask` are latched into `_chan_mask_live` /
`_aux_mask_live` at CONFIG_COMMIT and read by the process chain, which
skips a masked strip's or aux's nodes rather than running and silencing
them. Gating is per RUN (one compare, one branch) on the pattern
`_product_id`'s scope gate already set; a SIMD pair runs if either half
is live, and the masked half is made inaudible by its own ROUTING gate
and a zeroed crosspoint column instead.

Measured on the part, one bitstream (`_maincap`), one night, nothing
playing, `C2_MAIN_ST_OUT` over 48,000 frames:

| image | config | result |
|---|---|---|
| `602a0feb`/`b1325022` (= `DSP4_CHAN_MASK=0`) | D24 | `0x7FFFFF88` on 48,000 of 48,000 |
| `093c609f`/`2ba0e464` | D24 | **`0x00000000` on 48,000 of 48,000** |
| `093c609f`/`2ba0e464` | D32 | `0x7FFFFF80` on 48,000 of 48,000 |

The D24 row holds with NOTHING silenced and with all 48 silenceable D24
cells written. The D32 row is the positive control: D32 behaviour is
unchanged. `famverify` on the fixed image is the `.4` line unmoved —
17/20 families, 3,619 of 3,737 cells, GEQ 31/31, CROSSOVER 8/8, 0 FAILED.

`tools/pi/dsp4_silence_2532.py`, the workaround that silenced strips
25-32 through D32's rows, is deleted per its own docstring.

### S6-2 — the D24 aux mask the host sent was wrong, and inertly so

**Severity: minor (host). Status: FIXED.**

`dsp4_config.py` sent D24 `CFG_AUX_MASK = 0x0FFF` — twelve aux buses.
`defs/products/d24/dsp.csv` addresses `Aux001`–`Aux008`; D32's addresses
`Aux001`–`Aux012`. Harmless while nothing read the word; four live aux
chains the moment something did. Now `0x000000FF`. **A word no reader
consumes is not checked by anything**, which is the general form of both
this and S5-7.

### S6-3 — the D24 load was never a D24 load, and the reverb margin was never 5.34 %

**Severity: MAJOR (capacity). Status: measured.**

Block 16, 983.04 MHz, budget 327,680, two boots, minimum, both arms in
one session on one instrument:

| arm | cycles/block | margin |
|---|---:|---:|
| chip 1 control / **masked** | 262,033 / **202,786** | 20.03 % / **38.11 %** |
| chip 2 control / **masked** | 261,856 / **226,442** | 20.09 % / **30.90 %** |
| chip 2 masked, six reverbs | **275,035** | **16.07 %** |

The controls reproduce the `.4` record to 8 cycles (chip 2) and 154
(chip 1), so the differences are the fix and not the day. **Chip 1 — the
tighter chip — gains 18.08 % of its budget**, because it carries the
strips. Chip 2 gains 10.81 % from four aux chains.

The consequence for the product: the six-reverb worst case, which the
2026-09-08 record put at 94.66 % / **5.34 % margin** and which was
written up as a product decision inside the 10 % bar, is **83.93 % /
16.07 %**. It was 5.34 % because the part was running four aux chains and
eight strips the product does not have. The reverb's own cost did not
change (+49,187 here against +49,096 on 09-08).

### S6-4 — S5-10 narrowed: the DSP carries the audio, the CAPTURE PATH loses the order

**Severity: major (instrument, CPLD-side). Status: mechanism named, not fixed.**

The through-DSP arm still does not close and **no latency figure is
quoted**, but the mask was not the reason and the symptom is now named.

A CONSTANT through Pi → CPLD → DSPA → fabric → DSPB → CPLD → Pi returns
**bit-exact** (`0x00123400` on 143,400 of 144,000 frames played). A
STAIRCASE (1,500 values, 64 frames a step, `tools/pi/dsp4_order_stair.py`)
returns every value — index range 1..1500 complete, 96,040 non-zero words
for 96,000 played — as **82,042 runs where a clean loop gives 1,500**:
86 % of runs are one frame long and only 8,141 of 81,351 transitions are
+1. Interleaved values sit within a window of hundreds to thousands of
steps and the window width is not fixed.

That is a capture path not frame-locked to the CM4 capture DMA. It is a
property of the `_maincap` instrument (`o_dspb[3]` slot 0), not of the
DSP: `_pisel` closes the same loop inside LOGIC and returns 48,000 of
48,000 counter words at ONE offset. `dsp4_loop_latency.py`'s
14,494–14,509 for this arm has **5.67 % counter agreement** across ~2,780
distinct offsets with the impulse never found — a spurious mode, recorded
so it is not mistaken for a measurement.

Closing it needs a frame-locked capture: a CPLD-side change to the
`_maincap` re-framer, or a DSP-side capture buffer read over the
parameter link, which sidesteps ALSA. Neither blocks the window.

### S6-5 — the first cut of the fix did not fit chip 1

**Severity: major (program memory). Status: FIXED.**

Gating every run exactly, with `_mask_apply` unrolled per strip and per
aux, overflowed chip 1's `sec_swco` by **622 words** in the block-16
paired build — the configuration every capacity number is taken in. The
shipping per-sample image linked either way, so the window was never
blocked, but a fix that does not fit the operating point is not a fix.

Brought to about 230 words by three changes, none of which alters what is
skipped for any mask a product sends: `_mask_apply` made table-driven
(one loop over strips, one over a (pointer, bit) table for the aux
buffers); the chain's gate reduced from four instructions to three by
resolving one word per gate group into `_mask_on[]` at commit; and
adjacent runs merged where neither side has to be gated exactly, with
standalone METER runs — which emit nothing under block kernels — not
gated there at all. Chip 1: **124 gates to 61**.

**Chip 1's program memory is the binding constraint on this chip**, and
it is the third time it has bitten (S5-6's `bqeverify` arms, the
`dyn_selftest` in every paired build, this). Worth a dispatch of its own
before the next feature lands in the chain.

## The CM4 loop at 48 kHz, and the product-config word nothing reads (2026-09-09, session 31)

Session: PI_TDM8 bitstream from the current slot map, flashed via JTAG,
the CPLD duplex loop's latency at 48 kHz. Write-up:
`MW/D32/DSP/dsp4-loop-latency-20260909.md`. Contract
`defs-v2026.09.08.4`. Images unchanged: chip1 `602a0feb` / chip2
`b1325022`. Bitstreams built tonight from slot map
`sha256:4ecc4aa221a0787e…`.

### S5-7 — `CFG_CHAN_MASK` is stored and never read, so a D24 runs 32 strips

**Severity: MAJOR (firmware, window item). Status: FIXED 2026-09-09 — see S6-1.**

`tools/pi/dsp4_config.py` sends D24 `CFG_CHAN_MASK = 0x00FFFFFF`
("strips 25-32 NET-only"). `product_config.asm:121` stores it in
`_chan_mask`. Nothing reads `_chan_mask` — four references in the whole
tree: `.global`, the `.var` initialiser, `.extern`, and that one write.
All 32 strips therefore run on D24 and all 32 sum into `C2_RECV_MAIN_L`.

Measured on the part, block 8, conformance images. With everything the
D24 contract can silence silenced (32 strips attempted, the four groups,
USB, BT, CodecAux) AND the Pi input off, `C2_MAIN_ST_OUT` sits at
positive full scale `0x7FFFFFE0` for 48,000 frames of 48,000, with
nothing playing. Writing `MainOn=0`/`Mute=1` to exactly strips 25–32 —
through D32's rows for the same cells, the address map being shared per
decision D3 — takes it to `0x00000000` for 48,000 of 48,000.

The contract is NOT at fault: D24 is a 24-channel product, its matrix
has zero `Chan025` cells and `d24/dsp.csv` correctly carries none. The
firmware is running eight strips the product does not have.

This is what made every previous attempt at the loop measurement
unusable, including the 2026-09-08 note that "the loop still carries a
DC pedestal until the main chain is set to unity" — it is not a pedestal
and it is not the main chain.

`_aux_mask` has the identical shape (`product_config.asm:124`, no
reader). `_out_mux` likewise, and that one is already acknowledged in
the host tool. Of the four product-config words only `_product_id` has a
reader.

### S5-8 — the artifact hash covered every macro; the artifact NAME did not

**Severity: moderate (build hygiene). Status: FIXED this session.**

The 2026-09-08 fix put every macro into the bitstream hash and the
manifest's `config:` line, which stopped two different builds colliding
on one filename. It left the label wrong: a `PI_TDM8=1` build still came
out named `dsp4_logic.<hash>` — indistinguishable at a glance from a
shipping artifact — with `SHIPPING: yes` in its manifest, even though
`build.sh`'s own comments call PI_TDM8 non-shipping. The one line a
human reads at the bench said the opposite of the truth.

`build.sh` now folds every non-shipping switch into BOTH the artifact
name and the `SHIPPING:` line, each with its reason. Proof it changed
the label and not the bits: `build.sh` is not an input to `SRC_HASH`
(slot map + config line + RTL + qsf + sdc are), the rebuild produced the
same hash `83778a06f954`, and two consecutive builds gave the identical
pof md5 `1c556d38ed76c1cdd1190513c5447de4`.

### S5-9 — the LOGIC design has no ID register, so "which bitstream is running" costs a measurement

**Severity: minor (verifiability). Status: recommendation, not done.**

Gate 2 asked for the running hash off the part. There is nothing in
`rtl/` to read back and MAX V configuration readback is not available
over the SVF path, so identity had to be established behaviourally:
`a1f6672af6c3` captures all zeros (`pcm_din` tied to `1'b0`), `_pisel`
returns the Pi's own playback bit-exact, `_maincap` tracks
`MAIN_ST_OUT` under mute and level. That is sound but indirect and costs
a capture per flash. A few bits of design ID on the TEST pins or over
the parameter link would replace it with one read. Not done tonight:
adding it changes the RTL and therefore every bitstream hash.

### S5-10 — the Pi → DSP → Pi pass-through does not deliver a coherent stream

**Severity: major (open). Status: narrowed further 2026-09-09 — see S6-4. The
mask (S5-7) was NOT the reason; the capture path is.**

With S5-7 worked around and the main bus proven silent, the through-DSP
arm still returns mostly zeros with sparse out-of-order counter indices
(5, 5, 16, 18, 35 over 40 consecutive frames). **No latency figure is
quoted for it.** The harness's 14,550-sample offset for this arm is a
spurious mode — 2,878 of 48,014 candidate words agreeing, across 44
distinct offsets, impulse never found — and is recorded only so it is
not mistaken later for a measurement.

Excluded so far: the capture path (it tracks `MAIN_ST_OUT` under mute
and level); the graph being stopped (`_dly_write_ptr_C2_MAIN_DLY`
advances, `FRAME_COUNT` 5,999/s against 6,000/s expected for block 8,
`BOOT_STAGE 7`, `SPORT0_ERR_A 0`); the new slot map (chip 1 RX lane 6 is
still `CS 0x0003`/2 words, chip 2 TX lane 3 still `CS 0x0003`); and the
main bus not being silent. `dsp4_audio_verdict.py` cannot settle whether
the block loop keeps up because `_proc_passes` is absent from these
images — "no pass rate available" — which is the next thing to fix, since
it is the one instrument that would answer it directly.

### S5-12 — the order soak reported a pass criterion it had quietly missed

**Severity: minor (instrument). Status: FIXED this session.**

`dsp4_order_soak.py`'s stimulus generator paced itself at
`RATE // CHUNK` chunks per nominal second. `48000 // 4096` truncates to
11, so it delivered 45,056 samples per second: a 630 s request ran 591 s
while every line of the report still said 630. Zero defects either way,
but a ten-minute gate would have been missed by nine seconds and the
output would not have said so. Fixed to count in samples, and the pass
criterion now checks the word count against the requested total.

### S5-11 — the current slot map adds ten slots and moves none, and the DSP never sees them

**Severity: informational (contract question answered). Status: closed.**

Gate 1 asked whether a TDM8 build from the current slot map is a contract
change. It is not. Against the previous map the 2026-08-23 CM4
allocation adds `A_I6` slots 2–7 and `B_O3` slots 4–7, all previously
unassigned, and every pre-existing (line, slot) → signal pair is
byte-identical. The generated lane tables confirm the DSP side is
untouched: masks come from where nodes exist, and only `PI_PCM_L/R` and
`PI_RET_L/R` have them. The panel MCU is an SPI parameter host and does
not see TDM slots at all.

## The 31-band GEQ, the crossover slope, and the chip-2 re-layout (2026-09-09, session 30)

Session: confirming the DSP code against the latest known matrix. Write-ups:
`MW/D32/DSP/dsp4-geq31-relayout-20260909.md` and
`MW/D32/DSP/dsp4-window-readiness-20260909.md`. Contract
`defs-v2026.09.08.4`. Images: shipping float configuration, chip1
`602a0feb` / chip2 `b1325022`.

### S5-1 — the 31-band GEQ moves 1,192 D24 / 1,460 D32 addresses, and every host cache with it

**Severity: major (contract). Status: landed as `defs-v2026.09.08.4`.**

A GEQ node's SPI block is exactly its band count and chip 2's allocator
packs blocks end to end, so the three bands `.3` added to seventeen nodes
are +51 words and every chip-2 block above the first GEQ slides. Chip 1
does not move. This is the first time this contract has MOVED an address
rather than added one, and a host on the old map writes an aux limiter
threshold into an anti-feedback notch with every address answering. The
panel MCU headers and the app must be rebuilt against `.4` in the same
window as the firmware.

### S5-2 — `gen_dsp.py` kept the GEQ band count as a hand-maintained constant

**Severity: major (generator). Status: fixed — `resolve_geq_bands()`.**

`MW/D32/DSP/gen_dsp.py` carried `GEQ_BANDS = 28` beside a graph whose
nodes said `bands=28`, and the two agreed because someone remembered. The
band count is a market parameter (`gen_dsp_csv.py --geq-bands`), so the
moment the graph moved to 31 the constant would have addressed 28 words
of a 31-word block and the three bands past the end would have been
silently unmapped. It is now READ OFF THE GRAPH, and a graph whose GEQ
nodes disagree with each other stops the generator.

### S5-3 — `gen_dsp.py --propose` was unreachable in the one case it exists for

**Severity: major (process). Status: fixed.**

The fatal drift check sat ABOVE the `--propose` branch in `main()`, so
every run that had a new `dsp.csv` to propose — which is exactly a run
where the graph disagrees with the landed file — died before reaching the
flag. The propose path now authors first and takes the drift verdict as a
value, generating nothing while the graph is ahead.

### S5-4 — the LR2 crossover does not sum flat without inverting the highpass

**Severity: major (design). Status: fixed in `xover_ref.py` and
`xover_design_fx.asm`, verified on the part.**

The 09-08 proposal specified slope 12 as "the same five offset formulas
with 1/(2Q) at 1.0 and the second stage written as the identity". That
designs a correct pair of 2nd-order sections, each 6.02 dB down at the
corner — and their sum NULLS there, measured at −242 dB on the model,
because at 2nd order the two paths are 180 degrees apart. Every 2nd-order
Linkwitz-Riley is specified with one path reversed. The highpass is now
inverted at slope 12, which in the offset encoding is a sign flip on `b0`
alone (`n1` and `n2` are zero and stay zero). `xover_ref.check()` scores
the corner and sum properties at BOTH slopes now; scoring only 24 is what
let this through.

### S5-5 — `dsp4_geq_verify.py` hard-coded 28 bands and scored 28 of 31 as a pass

**Severity: minor (instrument). Status: fixed — the band count is
counted in the landed map, and a hole in the numbering stops the run.**

The first run against the 31-band contract reported `GEQ_DESIGN_OK` with
`bands: 28` in its report. Bands 29–31 were addressed, answering, and
never written.

### S5-6 — `bqeverify`'s fixed/shootout arms do not link, and it pre-dates this session

**Severity: minor (instrument). Status: filed, not fixed.**

Under `DSP4_BQ_SHOOTOUT=1 DSP4_BQE_VERIFY=1` chip 1's `sec_swco`
overflows by 604 words. Rebuilt at the previous commit (`e278667`) the
same arm overflows by 386, so it was already broken; this session's
crossover work accounts for the 218-word difference. The shipping image
is unaffected and links with 85,330 words of chip-1 code free. The FLOAT
arm — the shipping cascade — builds and passes at 0 ULP.

## FX engine and anti-feedback (2026-09-08, session 29)

Session: the queued FX/ANTI_FB block. Write-up:
`MW/D32/DSP/dsp4-fx-afb-20260908.md`. Images: shipping float
configuration, chip1 `85af9dce` / chip2 `bcdbe1f0`; the block-16
measurement tree is chip1 `160d8863` / chip2 `02e38fa8`.

### S4-1 — chip 2's margin with the FX reverb running is 5.98 %, measured

**Severity: major (capacity, PW's #1 priority). Status: measured, and it
replaces the projection.**

`fxcost.sh`, whole chip-2 graph, block 16, two boots, minimum, paired on
one boot with a restore-and-re-read control:

| arm | cycles/block | % of 327,680 |
|---|---:|---:|
| six engines at the landed default (Type 0, unimplemented, dry) | 249,231 | 76.06 % |
| six engines at Type 3 = Reverb | 308,076 | **94.02 %** |
| difference | **+58,845** | +17.96 % |

Control (restore − default): **+93** and **+10** cycles on the two
boots, against a delta of 58,845. The 09-08 projection was ≈ +56,300 and
≈ 93.6 %: **sound and 4.5 % optimistic.** On the FIXED tree, where the
default is a real Echo, the same measurement is **305,259 = 93.16 %,
margin 6.84 %** — see S4-6. **Either way it is under ten per cent, which
is the sentence the dispatch asked for.**

### S4-2 — the FX engine destroyed its own dry input, in every algorithm

**Severity: major. Status: FIXED and verified on the part.**

`f15` holds the dry sample; every algorithm advanced its delay-line
cursor with `r15 = 1; r1 = r1 + r15`, and `r15` IS `f15`. The saved dry
signal became the integer 1 — as float32, 1.4e-45 — so the mix
epilogue's `f1 = f15 * f8` multiplied the dry path by zero, and the
reverb's comb loop fed the input to the FIRST comb and denormal noise to
the other seven.

**It looked like a working pass-through** because Type 0, the landed
default, fell through to `.fx_passthru_` — the one path in the node that
touches no integer scratch, so the dry survived there and nowhere else.
Every increment is `r1 = r1 + 1` now: one instruction instead of two,
and it does not alias a float.

### S4-3 — and its write pointer, with the sample it had just read

**Severity: critical (it wedges the part). Status: FIXED and verified.**

`f1 = dm(_fx_feedback_)` in ECHO / PING-PONG / FLANGER, and
`f1 = dm(i0, 0)` in the reverb's comb and allpass loops, both overwrite
`r1` — the write pointer — with a float.

* In ECHO the pointer became the feedback coefficient's bits. At the
  landed feedback of 0.0 that is `0x00000000`, so **every sample was
  written to `buf[0]`, the cursor stuck at 1, and the tap read a part of
  the line nothing had ever written**. Measured: Type 0, Mix 1.0, delay
  240 — peak **0.000000** over 1024 samples.
* In the REVERB the clobbering value is AUDIO. A float32 sample's bits
  are about 1e9, and the loop stores that back into
  `_fx_rv_comb_wptrs` and uses it as an offset next block: **every comb
  wrote at `comb_buf + 1e9` and the SPI link stopped answering.**

**S4-2 HID IT.** While the dry input was being destroyed the comb lines
held only zeros, whose bits are `0x00000000` — a pointer of zero, in
range, every block. **The reverb could not crash because it could not
carry a sample.** Fixing S4-2 made it carry one and it wedged the bench
on the first capture. The delayed sample lives in `f9` now, and the bar
reads all eight write pointers off the part and checks they are inside
their own lines.

### S4-4 — three more FX defects, all in the generator

**Severity: major. Status: all FIXED.**

1. **No L register.** `_C2_FX_ENG_NN_process` used `modify(i0, m0)` on
   four buffers and post-modify on four table walks and set no length
   register — alone among every kernel in this tree. It survived only
   because `C_RUNTIME_INIT` zeroes `l0..l15` and nothing on chip 2
   writes one; the chip-1 DLY nodes DO, D70 measured the boot kernel
   leaving `l6 = l7 = 0x2FF`, and both ISRs run on the secondary DAG.
2. **Doubling read 720 samples out of an eight-word buffer** with a wrap
   of 8 — 711 words before the array. The line is 12,000 words (250 ms)
   now and the Echo delay is CLAMPED into it: the contract's 1000 ms is
   48,000 samples, six engines of that is 1.15 MB, and 364 kB were free.
   **It costs nothing net** — `_fx_comb_buf_R` and `_fx_allpass_buf_R`
   were allocated at full size (12,587 words an engine, 75,522 across
   the six) and **no emitted instruction read or wrote either**. The
   delay pool goes 1,708,216 → **1,694,112 bytes**.
3. **`_buf_L` carried float32 while `_buf_` carried Q4.28** — the store
   ran before the fixed-point conversion. Nothing reads either (checked
   across all 724 assembly files); both now carry the published word.

### S4-5 — the landed default was not an algorithm, and the fall-through was silent

**Severity: major. Status: FIXED and verified.**

`_fx_type` boots at 0 = Echo and the reverb class emitted no Echo case,
so the default fell through dry — **which is the state every capacity
number since 09-03 was measured in**. Echo is implemented; Types 1, 4, 5
and 6 now take an EXPLICIT bypass that parks the Type in
`_fx_bypassed_<nid>`, because a silent fall-through is
indistinguishable on a capture from an engine that ran and had nothing
to do, and that is how this went four sessions unnoticed.

The node header has always printed `/* Default type: Reverb */` — the
graph declares `type=Reverb` — while the `.var` was hardcoded to 0.
`DSP4_FX_TYPE_DECLARED=1` boots at the declared Type. **It is a flag and
not the default because of what it costs (S4-1), and which Type ships is
a capacity decision.**

### S4-6 — what each FX algorithm costs at block 16

**Severity: informational (capacity). Status: measured.**

Same instrument, on the fixed tree, against the explicit bypass:

| six engines at | cycles/block | % of 327,680 | over the bypass |
|---|---:|---:|---:|
| explicit bypass | 251,322 | 76.70 % | — |
| Echo (the landed default) | 256,359 | 78.23 % | +5,037 |
| Doubling | 254,833 | 77.77 % | +3,511 |
| Reverb | 305,259 | **93.16 %** | +53,937 |

**Making the engine honest costs the shipping image +7,128 cycles/block,
2.18 % of budget** — 76.06 % → 78.23 %, margin 23.94 % → 21.77 %. About
5,000 of that is Echo running and about 2,100 is the L-register
initialisation and the bypass book-keeping.

### S4-7 — a 32-sample window cannot see a reverb, and that is half of "peak zero"

**Severity: minor (instrument). Status: fixed in the bar.**

The Freeverb comb lengths are 1116–1617 samples and there is no direct
path from input to output — the wet signal IS the comb read — so the
first reverberant sample arrives 1116 samples after the impulse. The
2026-09-08 family walk scored `FX_ENGINE` over a **32-sample** window
and the scope buffer is 1024. **A window thirty-five times too short
cannot see a reverb even when the reverb is perfect.** `fxverify.sh`
drives a step and arms twice a handshake apart, fetching only the second
window: the fetch is the slow part, and half a second of rest is 24,000
samples, by which time a comb with 0.6 of feedback has been round its
line fifteen times.

### S4-8 — ANTI_FB: the parameters landed, the switch was unread, nothing designed

**Severity: major (it was the family walk's only FAIL). Status: FIXED
and verified on the part.**

The GEQ's disease on a third node. Eighteen parameter addresses always
dispatched to the right symbols — 1000.0 Hz, −18.0 dB and Q 4.0 read
back off the part — and nothing turned them into coefficients;
`_afb_on` took its write and was read by no emitted line.

The design is on the DSP (`src/lib/afb_design_fx.asm`, modelled by
`tools/dsp/afb_ref.py`), because eighteen addresses cannot also carry
thirty coefficient words and a swap trigger. **A notch here is RBJ
PEAKING at negative gain**: `AntiFbNotchGain`'s domain is
`0=-18/127=0`, so the depth IS the parameter, and a textbook notch has
no depth parameter. Nothing is a per-notch constant — frequency and Q
both move — so `sin w0` and `1 − cos w0` are computed on the part over
x ∈ [0.00524, π/2], the versine from its own degree-5 fit in x² because
at 40 Hz `1 − cos x` is 1.4e-5 against a cosine of 0.9999863.

`afbverify.sh`: worst **4 ulp** over five parameter vectors, response
worst **0.00009 dB** against a 0.05 bar, 1 kHz Q 8 at −18 dB measured
**−18.000 dB** against a model of −18.000, and both negative controls —
`AntiFbOn = 0` with six real notches written, and On with every gain at
0 dB — **64/64 samples equal to the input**. **`ANTI_FB` moves from the
family walk's only FAIL to PASS.**

**`AntiFbCtrlOn` is still read by nothing, deliberately.** It enables an
automatic feedback detector and no detector exists in this firmware;
wiring it to the design would make an empty switch look implemented. It
is not in the recompute run, and the kernel and the write-up both say
so.

### S4-12 — the family walk's own stimulus stops reaching its own captures

**Severity: major (it is the coverage instrument). Status: OPEN, with a
named next step.**

`famverify.sh` on this image reads `audio SILENT` for `GEQ`,
`CROSSOVER`, `ANTI_FB`, `FX_ENGINE`, `ROUTING`, `LIMITER` and
`TUBE_SAT`. Scored by `hw_coverage.py` with the four dedicated bars
given as external verdicts, the previous session's golden is **17 of 20
families / 3,580 of 3,698 cells** and this session is **7 of 20 / 753**.

**It is reproducible and it is not the graph.** Two independent runs,
each with its own boot and config ladder, produced family-for-family
identical verdicts. On the SAME image: `afbverify.sh` drives the SAME
injection symbol (`_rx_ic_slot_C2_RECV_AUX_01`) into the SAME aux chain
and reads 64/64 samples equal to the input plus a −18.000 dB notch;
`fxverify.sh` reads a 0.500000 impulse through the FX chain; `busgold.sh`
is **bit-exact over 256 bus words**. A capture that carries no stimulus
is not a verdict about a node, so **this session's family count is not
restated as progress and is not usable as a regression either.**

Next step: diff the walk's inject/arm/capture ordering and its setup
writes against `dsp4_afb_verify.py`, which reaches the same nodes
through the same symbol on the same image and does not go silent. The
strip-1 `CFG_COMMIT` repair (`gainfix.py`) is the first suspect — a
chain whose input gain is 0 is silent all the way down, and `busgold.sh`
logged strip 1 at `0x00000000` and repaired it in this same session.

### S4-9 — the CROSSOVER node's dispatch block overlaps the EQ that follows it

**Severity: minor, and it is what makes the slope proposal free. Status:
recorded, not changed.**

`expand_crossover` claims `base+0 .. base+23` — twenty-four words — but
`C2_MAIN_XOVER` sits at 1397 and `C2_MAIN_OEQ_01` at **1401**. Because
`expand_eq_biquad` runs later and `add_dispatch` is a dict assignment,
the EQ silently wins from `base+4` on. The crossover actually owns
**four** words, of which 0x0576–0x0578 dispatch to nothing.

Nothing is broken by it today — a write to an unmapped address raises an
SPI error, which is the correct answer — and it is what lets
`CrossoverSlope` take 0x0576 with no address anywhere moving. It is
recorded because a node whose expander claims six times the space it has
is a trap for the next person who adds a parameter to it.

### S4-10 — `defs-v2026.09.08.3` cannot be consumed: the cells landed without their unmapped rows

**Severity: major (it blocks the 31-band GEQ). Status: OPEN, and it is
the hub's.**

The tag lands `Geq[1-31]` in the cell master (D24 4,946 → 4,985,
fingerprint `3d41d5850df3`) and **touches `products/<p>/` not at all**.
The pin was advanced here and reverted, for two errors in sequence:

```
ERROR: cell 'Aux001Geq029' (Aux/Geq) reaches no DSP address and
       _UNMAPPED_REASONS in gen_dsp.py does not say why.
ERROR: d24/dsp-unmapped.csv cell set disagrees with the graph —
       39 the graph proposes and the landed file lacks
```

**The first is this repo's and is fixed here**: `GEQ_BANDS` is one
constant that both the expander and the reason read, and the reason
matches on the BAND NUMBER rather than the family, so a band inside
1–28 that ever stopped reaching an address would still stop the
generator — which a family-wide `('Aux', 'Geq')` entry would have
hidden.

**The second is not.** `products/<p>/dsp-unmapped.csv` is a landed file;
39 D24 cells (51 on D32) were added to the master without the rows that
account for them, and this repo cannot write them — `check_proposal()`
runs BEFORE `--propose`, so once the graph and the landed file disagree
the generator will not emit the proposal that would close the gap
either. **`defs-v2026.09.08.3` needs `products/{d24,d32}/
dsp-unmapped.csv` regenerated and landed with it.** Until then the pin
stays at `.2` and `Aux001Geq029..031` cannot be proved on the part
because they have no address to write.

### S4-11 — `CrossoverSlope` has an address to go to, and it is free

**Severity: major (a product control that does nothing). Status:
PROPOSED; prototyped and reverted at the contract boundary.**

Eight cells resolve to 0x0575. The proposal is **0x0576** — a word the
crossover node already owns and nothing dispatches to (S4-9) — so **no
address in either product moves and no row count changes**. **ONE shared
slope word, not one per strip**: there is a single `CROSSOVER` node
feeding all four main outputs from one LP/HP split, which is why the
four `CrossoverFreq` cells already share one word.

The DSP side is specified with it rather than after it: **12 (LR2) and
24 (LR4) are honoured** — the same five offset expressions with `1/(2Q)`
at 1.0 instead of 0.70711 and the second stage of each path written as
the compiled identity — and **6 and 18 are ignored, not clamped**,
because a 1st-order pair is 3 dB down at the corner rather than 6 and a
3rd-order pair does not sum flat, so neither is a Linkwitz-Riley
alignment this node can hold. `xover_ref.py` carries and checks both
(each path 6.0206 dB down at either slope).

It was implemented and then reverted **because `check_proposal()`
refused it**, which is the propose/land boundary working exactly as
designed: the address and the design land together, at a gate.

## the four inert families (2026-09-08, later)

Session: the queued INERT-families block. Write-up:
`MW/D32/DSP/dsp4-inert-families-20260908.md`. Images: shipping float
configuration, chip1 `a6db2a8b` / chip2 `8e42f2b0`.

### S3-1 — GEQ: the 28 band cells were dispatched to a coefficient array, and nothing designed them

**Severity: major (PW's market bar). Status: FIXED and verified on the
part.**

`defs/products/d24/dsp.csv` gives a GEQ node one address per band
carrying a gain in dB (`Aux001Geq001..028`, Table `0=-12/127=12/[Lin]`).
`gen_dsp.py:579` pointed those 28 addresses at `_geq_coeffs_next` — a
140-word staging array, one word per band, with no swap trigger. The
comment on the same loop has said `gains[28]` since it was written.
`_geq_gains_<nid>[]` was declared, written by nothing and read by
nothing.

Measured 2026-09-08: writing ±12 dB to all 28 cells moved
`_geq_coeffs_next[0..4]` to `41400000 C1400000 41400000 …` — 12.0f and
−12.0f as raw dB floats — while `_geq_coeffs_A/B` stayed at the compiled
identity `3F800000 40000000 BF800000 40000000 3F800000` and
`_geq_swap_pending` stayed 0. Every graphic EQ in the product passed its
input through: 32 of 32 captured words equal to the upstream node.

**28 addresses cannot carry 140 coefficients plus a trigger**, so the
design belongs on the DSP. `tools/dsp/geq_ref.py` is the normative model
(ISO R.40 third-octave centres, exact constant-Q 4.3185, RBJ peaking,
checked against `bq_float_ref.rbj_peak` to 2.2e-16);
`src/lib/geq_design_fx.asm` is the kernel; `src/geq_tables.asm` is
generated from the model; `_spi_dispatch_cN_dirty[]` is the trigger the
contract has no address for.

On the part: coefficients within **3 ulp** of the model over five gain
vectors, response within **0.00014 dB** of it, and band 17 at +12 dB
measures **+11.997 dB** at 1 kHz against a model of +12.000. A flat GEQ
designs the compiled identity and passes 64/64 samples unchanged.

### S3-2 — the offset coefficients cannot be designed the readable way

**Severity: major (would have shipped a wrong filter). Status: avoided by
construction; recorded because the wrong route is the obvious one.**

The natural implementation designs `b0..a2` and then converts:
`c1 = 2 + a1`. At 20 Hz `a1` is −1.99999 and `c1` is 6.8e-6, so forming
`a1` in float32 first carries about 1.2e-7 of absolute error into a
subtraction of two near-equal numbers — `c1` comes out about two percent
wrong. **That is exactly the error the offset encoding exists to remove,
thrown away in the step that computes it.**

Both new design kernels compute the offset words directly from
cancellation-free expressions, with the small quantity held as a
generation-time constant: `k2 = 2(1 − cos ω₀)` for the GEQ, and a series
for `1 − cos x` in the crossover (over 50–500 Hz `cos x` is
0.9979–0.99998). `geq_ref.check()` and `xover_ref.check()` both assert
the rearrangement is the same filter.

### S3-3 — a SHARC register alias produced a perfect coefficient set in the wrong bank

**Severity: major. Status: FIXED. Recorded because the symptom names none
of the cause.**

`_geq_design_N` held the band counter in `r12` and the reciprocal in
`f12`. On SHARC those are the same register, so after the first band the
count became the float bits of `1/(1+ia)` — about 1.07e9 — and the loop
walked past the end of `_geq_coeffs_next`, writing designed coefficients
into whatever followed until a band read out of the tables produced a
negative `inv` and `if gt` fell through.

**It did not look like corruption.** All 140 designed words were correct
to 1–3 ulp and the part stayed up, because everything the overrun touched
is rewritten every block — **except `_geq_active`**, which is not. That
word took `n1 = 2.0f`; `pass` reads any non-zero as bank B; the design
had been staged into A. The bench read `+0.000 dB` at every probe
frequency with every coefficient correct in memory.

The rule that follows: in a routine that mixes integer bookkeeping with
float arithmetic on SHARC, the bookkeeping goes in a register whose float
twin the routine never touches. Both new kernels state their clobber list
including that, and both keep `r13-r15` clear of floats.

### S3-4 — CROSSOVER: one address carries two parameters, in the landed contract

**Severity: major, and it is a `defs` defect this repo cannot fix.
Status: worked around; the ask is one row.**

`MainCtr001`, `MainL001`, `MainR001` and `MainSub001` each carry a
`CrossoverFreq001` AND a `CrossoverSlope001`, and **all eight resolve to
address 0x0575** — the contract's own Notes column says "shared crossover
word". Measured on the part: writing 500.0 then a slope left
`0x00000018` (the integer 24) in `_xover_coeffs_next[0]`.

The crossover design (S3-5) therefore **IGNORES a word outside the
frequency table's 50–500 Hz rather than clamping it**. Clamping a slope
into the frequency would move the crossover to 50 Hz every time the host
set a slope; ignoring it leaves the split where the last legal frequency
put it. The bar carries the negative control: writing slope 24 and then 3
leaves the staged set unmoved word for word.

**Until the row is split, the slope is not settable and the split is
LR4** — 24 dB/octave, the top of the slope cell's own table.

### S3-5 — CROSSOVER: a real LR4 split, made real

**Severity: major. Status: FIXED and verified on the part.**

Same defect shape as S3-1: a real pair of two-stage cascades, the landed
cell dispatched to `_xover_coeffs_next[0]`, no trigger, both banks at the
compiled identity, the node copying its input to all four main outputs.

`tools/dsp/xover_ref.py` (normative: Linkwitz-Riley 4, checked against
RBJ written out and against the two properties that make it a crossover
— each path 6.02 dB down at the corner, the two summing flat) and
`src/lib/xover_design_fx.asm`. On the part at 50/80/120/250/500 Hz:
staged coefficients within **3 ulp**, the live bank equal to the staged
one word for word, every corner reading **LP −6.021 dB / HP −6.021 dB**,
and LP+HP summing flat to **0.00013 dB** over ±4 octaves. Audio at
f0 = 120 Hz: LP −0.04 / −6.02 / −48.24 dB at 30 / 120 / 480 Hz against a
model of −0.03 / −6.02 / −48.21.

### S3-6 — ANTI_FB: the parameters land, the kernel is real, nothing joins them

**Severity: major. Status: DIAGNOSED, not implemented (the dispatch
scoped this family to diagnose and cost).**

`_afb_notch_freq/gain/q` take the write correctly — measured 1000.0,
−18.0 and 4.0 at their landed addresses — and are read by no emitted
line. `_afb_on` and `_afb_ctrl_on` are read by nothing either, so the On
switch does nothing. `_afb_coeffs_next` never moves and both banks hold
the compiled identity. The cascade underneath is real: six stages, its
own crossfade, the same `_fx_cascade_node` idiom the GEQ uses.

The work is a `_afb_design_N` beside `_geq_design_N` — RBJ from (freq,
gain, Q), the same dirty flag, the same swap — plus a product decision
about whether `AntiFbCtrlOn` implies an automatic detector.

### S3-7 — FX_ENGINE: the default algorithm is not implemented, and the reverb path takes the sample with it

**Severity: major. Status: DIAGNOSED, not implemented.**

Every FX parameter reaches the kernel; `_fx_type` selects the algorithm
and **defaults to 0 = Echo**, which the dispatch does not implement —
only 2 (Doubling) and 3 (Reverb) have cases and everything else falls
through to a dry pass-through. `_fx_on` is written 1 and read by nothing.

Three defects underneath:

1. The Doubling path reads a 15 ms (720-sample) delay out of
   `_fx_echo_buf[8]`, an **eight-word** buffer, with a wrap constant of
   8. It cannot work as written.
2. **`_C2_FX_ENG_01_process` sets no L register** and then uses
   `modify(i0, m0)` four times on its comb and delay buffers — every
   other kernel in this tree guards that with `l0 = 0`. Setting
   `Type = 3` in the family walk turned the FX chain from carrying the
   impulse to **peak zero on both arms**: the reverb path does not merely
   fail to reverberate, it takes the sample with it. This is the first
   thing to check, and it is why the family-walk spec was left at the
   default `Type`.
3. `Fx001Mix001`'s Table domain is `0=0/127=100` (percent) and the kernel
   uses the word directly as a 0..1 blend coefficient, so the documented
   100 gives `100·wet − 99·dry`. `wire-units.csv` carries no row for any
   FX cell.

Its cost is measured and it is large — see S3-9.

### S3-8 — the capacity numbers already carried the cascade families, and now that is tested rather than argued

**Severity: informational, and it answers the hub's question. Status:
measured.**

`_bq_fx_cascade_blk` issues the same instruction stream whatever its
coefficients hold. Until the GEQ design landed that could not be tested,
because no GEQ had ever held a coefficient other than the identity.
Paired on one boot, chip 2, block 8:

| arm | cycles/block |
|---|---:|
| every GEQ flat | 330,658 |
| every GEQ non-flat (364 band cells at ±12 dB) | 331,250 |
| difference | **+592, 0.18 %** |

Like-for-like at the operating point the fit numbers were taken at —
`sigprofile2.sh`, whole chip-2 graph, block 16, two boots, minimum:
**250,480 cycles/block (76.44 % of 327,680)** against the 09-03 record of
**249,737 (76.21 %)**. +743 cycles, 0.23 % of budget, against two boots
of this run that are 1,516 cycles apart. **The 09-03 fit numbers stand
and the designs cost nothing measurable.**

### S3-9 — the FX reverb has never been in a capacity number, and it is worth 17 % of chip 2

**Severity: major (capacity). Status: measured at block 8; projected to
block 16.**

`FX_ENGINE` is the one family whose instruction stream depends on its
parameters, and its `Type` has always defaulted to the unimplemented
Echo. Chip 2, block 8, paired on one boot:

| arm | cycles/block |
|---|---:|
| Type 0 on all six engines (the default) | 330,635 |
| Type 3 = Reverb on all six | 358,806 |
| difference | **+28,171** |

Reproduced over three boots: +27,861 / +27,867 / +28,171. That is 3,521
cycles per sample across six engines, **587 per sample per engine**.
Scaled to block 16 the same per-sample cost is **≈ +56,300 cycles/block,
17.2 % of chip 2's budget** — 76.4 % → ≈ 93.6 %, margin 23.6 % → ≈ 6.4 %.
**That is a projection from a measured per-sample cost, not a measurement
at block 16**, and it is the largest uncosted item in the capacity
picture. One arm of `sigprofile2` would settle it.

### S3-10 — the sample-order result was taken through unidentified logic, and is withdrawn

**Severity: major (it invalidates a recorded finding). Status: the cause
is fixed; the measurement must be re-taken.**

The recorded "the loop does not preserve sample order — 40.4 % of
transitions monotonic, dominant step −576 Pi frames" cannot be
interpreted, for three independently measured reasons.

**The Pi link runs at 48 kHz whatever ALSA is told.** Measured on the
bench, `arecord -d 5` on `hw:dsp4pcm,0`: 48,000 → 5.01 s wall; 96,000 →
10.01 s; 192,000 → **20.15 s**. Effective frame rate 47,917 / 47,955 /
47,645 Hz. LOGIC masters BCK and LRCLK, the Pi is a slave, and
`invirco,dsp4-pcm-dummy` declares `SNDRV_PCM_RATE_8000_192000` so it does
not refuse a rate the link cannot honour. The loop test ran at 192,000,
so **every frame count in that result is four times the truth**.

**The flashed bitstream predates the regrouping it was blamed on.** The
bench runs `dsp4_logic.a1f6672af6c3`, built 2026-08-21. `PI_TDM8` first
appears in `rtl/dsp4_pcm_reframe.v` on 2026-08-23 (`2bb0b49`).

**That bitstream has no Pi capture path at all**: in the RTL as of the
commit that shipped it, `assign pcm_din = 1'b0; // capture path to the
Pi: future work`. Confirmed on the bench today — with the DSP booted,
configured and in the documented pass-through state, a played counter
returned **0 carrying frames** at both 48 kHz and 192 kHz.

So the loop measurements were taken on a **different, unrecorded**
bitstream and the bench was then left on one that cannot loop. See S3-11
for why nothing recorded which.

### S3-11 — a bitstream could not name its own configuration

**Severity: major (it is the root cause of S3-10). Status: FIXED.**

`shared/dsp4-logic/build.sh` derived the artifact name from a hash over
the slot-map hash, `loopback=`, the RTL, the QSF and the SDC — and
**nothing else**. `PI_TDM8`, `PI_SELFTEST` and `PI_MAINCAP` are Verilog
macros passed to `quartus_map`; none of them entered the hash and none
was recorded in the manifest. A build that regroups four Pi frames per
DSP frame and one that does not therefore produced **the same filename
and an identical manifest**.

The flashed bitstream's recorded `slot_map` hash (`efd8d555…`) is also
two generations stale against the current `slot-map.csv` (`4ecc4aa2…`),
whose A_I6 rows declare the regrouping PW decided on 2026-08-23.

Fixed: every macro now enters the hash and the manifest records both the
config line and a plain-English `pi_link:` description of what the Pi
side does. Re-taking the order test needs a `PI_TDM8` bitstream built
from the current slot map with the fixed script, flashed at the bench.
**Not done here**: with the defect unfixed there was no way to be sure
which existing artifact is the TDM8 build, and flashing shared hardware
on a guess is not a measurement.

### S3-12 — the GEQ family probe was blind to a working graphic EQ

**Severity: medium (instrument). Status: FIXED.**

`dsp4_family_verify.py` probed `GEQ` with `Aux001Geq001` — band 1 of the
ISO third-octave set, **19.95 Hz**. Its impulse response takes 2,400
samples to ring once, so over the 32-sample capture window a +12 dB boost
moves `b0` by about 4e-4 and the family would read INERT for a graphic EQ
working perfectly. The probe is now band 18 (1 kHz), which the window
resolves. The numeric verdict lives in `geqverify.sh`, which scores the
whole band set against the model rather than one band against a window.

## hardware families through the landed contract (2026-09-08)

Session: the queued VIRTUAL AUDIO block, steps 2–4 — every D24 kernel family
exercised on the part with its parameters addressed out of the LANDED
`defs/products/d24/dsp.csv`. Write-up:
`MW/D32/DSP/dsp4-hw-families-20260908.md`. Image: the shipping FLOAT
configuration at defs-v2026.09.08.2, chip1 `906a70f7` / chip2 `3a2d930c`,
byte for byte the session's starting baseline.

### S2-1 — `ChanGateHold` reaches the kernel unconverted, and a gate that has opened never closes again

**Severity: major. Status: FIXED the same day — see S2-8 for the fix, which
is generic over `wire-units.csv` rather than a patch for this cell.**

`_gate_hold_<nid>` is an integer SAMPLE COUNT — the generator's own
initialiser is `2400`, which is 50 ms at 48 kHz — and the SPI dispatch
stores the host's IEEE-754 float32 word into it with no conversion. A host
writing the documented 1.0 ms therefore lands `0x3F800000` =
**1,065,353,216 samples, about 6.2 hours of hold**.

Measured on the part 2026-09-08. With hold written as `f32(1.0)` and the
gate threshold raised to 0 dBFS over a −6 dBFS step,
`_gate_gain_target_q_C1_GATE_01` stayed at unity (268,435,456) and
`_buf_C1_GATE_01` stayed at `0x07FFFF07` — the gate did not shut. Writing
the same cell as a RAW `48` (1 ms as the variable actually means it)
restores the behaviour completely:

| threshold | `_gate_gain_target_q` | capture peak |
|---|---|---|
| −80 dB | 268435456 (unity) | `0x07FFFF07` |
| 0 dB | 2684355 (the range floor) | `0x00147BDB` |

**The ladder is not the fault.** `dsp4_node_verify` scores GATE bit-exact
against `fixed_ref` on this same image, converted parameters and all, and
the threshold conversion is exact (`_gate_thrq` = −222,930,816 for −40 dB,
which is `fixed_ref.gate_thr_q(-40.0)` to the word). The missing conversion
is the whole defect.

`defs/common/wire/wire-units.csv` already carries the row — `ChanGateHold,
ms, hold samples — conversion to declare` — so the gap was known. This is
the first measurement of what it costs, and the cost is that the gate stops
gating after its first signal.

### S2-2 — a parameter that genuinely holds ZERO reads as unreadable, and it cost COMPRESSOR its verdict twice

**Severity: medium (instrument). Status: fixed in
`tools/pi/dsp4_family_verify.py`.**

`dsp4_node_verify.vpeek()` will only accept a value of 0 when a known
non-zero register still reads correctly — a dropped answer on this link
always reads as zero, so zero has to out-vote its own absence. That
corroborating register lives in `dsp4_node_verify.SENTINEL`, and `SENTINEL`
is populated in `dsp4_node_verify.main()`. **Any tool that calls
`run_node()` directly leaves it empty**, and every genuinely-zero parameter
word then returns `None`.

The compressor's hard-knee words `_comp_cgp_+2` and `_comp_cgp_+3` are zero
by default, so COMPRESSOR reported `parameters unreadable — no verdict` on
two consecutive bench runs while every other node passed. The other six
words read fine, which is exactly why it looked like a link fault:

```
_comp_attq   4294968        _comp_cgp_+0  4183501888
_comp_relq   4294968        _comp_cgp_+1  1610612736
_comp_mkq    367756576      _comp_cgp_+2  None      <- genuinely 0
_comp_parq   2147483647     _comp_cgp_+3  None      <- genuinely 0
```

`numeric_phase()` now arms the sentinel from `_scope_len` before the first
node and says so in the log when it cannot.

### S2-3 — BQCVT is the FIXED arm's converter and reports a false FAILURE on the shipping float image

**Severity: medium (instrument). Status: fixed.**

`run_bqcvt` compares the node's stored coefficients against
`fixed_ref.biquad_coeffs_q`, which is Q4.28. Under `DSP4_BQ_FLOAT` — the
shipping default — the node stores IEEE float32, so every set mismatches
and the run prints `MISMATCH b1 control fires` for all of them:

```
part  (1065353216, ...)   = 0x3F800000, float 1.0
model (268435456,  ...)   = Q4.28 1.0
```

That is the harness quoting the wrong model for the arm it was pointed at,
not a firmware defect. `shared/numeric-spec.md` is explicit: the SHARC float
cascade's bit-exact reference is `bq_float_ref` and its bar is
`bqeverify.sh float`. `dsp4_family_verify.py` now takes `--bq-arm` from the
build and skips BQCVT on a float image with the reason in the log.

### S2-4 — a DC step cannot see a filter whose gain at DC does not move

**Severity: medium (method). Status: fixed — the frequency-shaped families
are probed with an impulse.**

`dsp4_conform.bus_capture()` drives a STEP and reads a window at sample 900.
For a gain, a delay or a dynamics stage that is the right stimulus. For a
filter it is DC, and a peaking section has unity gain at DC — so a 28-band
GEQ's band 1 (near 25 Hz), an anti-feedback notch and a crossover all change
nothing that a step can show. The second run of this bar duly reported GEQ,
ANTI_FB and CROSSOVER as INERT, which would have been a wrong answer about
the firmware drawn from a property of the instrument.

An impulse response is frequency-complete. `dsp4_family_verify.capture()`
takes the stimulus mode per family, and the biquad-shaped families are armed
with an impulse read from sample 0.

### S2-5 — `ChanGain` and `TalkGain` are applied as LINEAR coefficients while the masters declare dB

**Severity: medium. Status: open — an mx26 unit call, corroborated on the
part.**

`docs/contract/wire-units-proposals.md` lists both families as unit
UNDECLARED with the Table domain proposed as the wire unit
(`ChanGain 0=0/127=60/[Lin]`, `TalkGain 0=0/127=40/[Lin]` — both dB).
Measured on the part, the kernel takes them as linear:

| cell | written | input peak | output peak | linear reading | dB reading |
|---|---|---|---|---|---|
| `Chan001Gain001` | 4.0 | `0x08000000` (0.5) | `0x20000000` (2.0) | ×4 ✓ | ×1.585 ✗ |
| `Talk001Gain001` | 4.0 | `0x08000000` (0.5) | `0x20000000` (2.0) | ×4 ✓ | ×1.585 ✗ |

The proposal as written ("declare the Table domain as the wire unit") cannot
be adopted without a dB→linear conversion appearing in the kernel; adopting
it as-is would silence the strip at the documented 0 dB, exactly as review
finding D57's `RtgDca` did.

### S2-6 — four families answer every landed address and reach no sample

**Severity: major. Status: reported — WIRE-vs-RESERVE is PW's call, and two
of the four were not on the list that was supposed to hold them.**

`ANTI_FB`, `GEQ`, `CROSSOVER` and `FX_ENGINE` — **646 of the 3,698 addressed
D24 cells** — take every write at their landed address, raise no SPI error,
and change nothing. Measured the strongest way available: walk the chain
with an IMPULSE (frequency-complete, unlike the step) and diff consecutive
node buffers word for word.

```
aux 1, GEQ bands driven +12/-12 dB, notch armed 1 kHz Q4 at -18 dB
  _buf_C2_AUX_FDR_01   0x08000000 0 0 0
  _buf_C2_AUX_EQ_01    0 of 32 samples differ from the previous node
  _buf_C2_AUX_GEQ_01   0 of 32
  _buf_C2_AUX_AFB_01   0 of 32
  _buf_C2_AUX_LIM_01   0 of 32

main, crossover frequency written 500 Hz
  _buf_C2_MAIN_DLY     0x08000000 0 0 0
  _buf_C2_MAIN_XOVER   0 of 32      <- the crossover does not split
  _buf_C2_MAIN_OEQ_01  0 of 32
  _buf_C2_MAIN_OEQ_02  0 of 32

FX 1, On=1, Mix=100, Decay=2.0
  _buf_C2_FX_ENG_01    0x08000000 0 0 0
  _buf_C2_FX_FDR_01    0 of 32
```

`ANTI_FB` and `FX_ENGINE` are **corroborated by the D38 static list** —
`docs/contract/inert-cells-d38.md` already names every notch cell and every
FX parameter as unreferenced by any emitted line — so this is the live
confirmation that list was waiting for, on families session 6's sampled
probe did not reach.

**`GEQ` and `CROSSOVER` are NOT on that list, and that is the new part.**
372 addressed cells that static analysis believed something reads, and the
part says nothing does. Either the generator emits a reference the kernel
never acts on, or `wire_contract.py`'s "reachable by offset" class is
hiding them; either way the D38 count of 896 is low by at least these.

### S2-7 — the CM4 duplex loop is up: one PCM device, S32_LE, 192 kHz

**Severity: medium. Status: CLOSED at the ALSA layer.** The recorded
blocker was that `dsp4-pcm-slave.dts` exposes TWO PCM devices sharing one
`bcm2835-i2s` CPU DAI (playback-only `spdif-dit`, capture-only
`spdif-dir`), so opening both re-programs the same block twice and the
counter comes back scrambled. Its stated fix direction — ONE dai-link with
a codec declaring both directions — is right, and the obstacle was that no
codec in the Pi tree fits this link. Four were measured on the bench
2026-09-08 before one was written:

| codec | result |
|---|---|
| `linux,spdif-dit` + `linux,spdif-dir`, two links | the overlay being replaced. Right rate, right format, one direction each. |
| the same two as multi-codec on ONE link | instantiates **capture only** (`00-01 bcm2835-i2s-dir-hifi … capture 1`) — the playback-only codec loses. |
| `asahi-kasei,ak4554` | ONE dai-link and a REAL duplex device (`00-00 … playback 1 : capture 1`) — this is what proved the shape is right — but its DAI declares **S16_LE only** (`arecord -f S32_LE` → "Available formats: - S16_LE"). |
| `google,voicehat` | both directions, **S32_LE** — and **48 kHz only**. With the hub's pin ruling it probes and the card comes up; then ALSA clamps 192 kHz to 48 kHz, the capture overruns by ~1.6 s, and a known word played as `0x00001000` / `0x00010000` / `0x00100000` comes back as the same unrelated constant. |

**THE HUB'S PIN RULING WAS APPLIED AND IT WORKED.** CM4 GPIO17 = CS6 as
`sdmode-gpios` (mx26 `src/hw/d24-hw-pins.csv`) cleared voicehat's
mandatory-GPIO probe failure exactly as ruled — `voicehat-codec
dsp4-duplex-codec: property 'voicehat_sdmode_delay' found delay= 5 mS` and
the card instantiated. It is voicehat's RATE, not its pin, that
disqualifies it. **The rate is not negotiable**:
`shared/dsp4-logic/slot-map.csv` lane A_I6 says LOGIC "regroups 4 Pi frames
per DSP frame", so the Pi frame is 2 slots × 32 bits at **192 kHz**.

**THE FIX IS FORTY LINES OF DAI DECLARATION**, `invirco,dsp4-pcm-dummy`
(`shared/dsp4-logic/pi/dsp4-pcm-dummy/`): playback and capture,
`SNDRV_PCM_RATE_8000_192000`, `SNDRV_PCM_FMTBIT_S32_LE`, no registers, no
control bus, no clocks, no GPIO — so CS6 stays free and the pin ruling is
recorded rather than consumed. Measured after it:

```
/proc/asound/pcm
00-00: bcm2835-i2s-dsp4-dummy-hifi dsp4-dummy-hifi-0 : ... : playback 1 : capture 1
arecord -D hw:dsp4pcm,0 -f S32_LE -c 2 -r 192000
    Recording raw data : Signed 32 bit Little Endian, Rate 192000 Hz, Stereo
```

One device, both directions, no rate clamp, and no over/underrun reported
by either `aplay` or `arecord` across a 96,000-word duplex run.

**FOR `cm4-setup-pi.sh`, UNDER A BENCH FLAG — the exact lines** (this repo
did not edit that script, per the dispatch):

```sh
# 1. the codec module (needs linux-headers; present on the bench image)
cd shared/dsp4-logic/pi/dsp4-pcm-dummy && make
sudo install -D -m 644 dsp4-pcm-dummy.ko \
     /lib/modules/$(uname -r)/kernel/sound/soc/codecs/dsp4-pcm-dummy.ko
sudo depmod -a

# 2. the overlay
dtc -@ -H epapr -O dtb -o dsp4-pcm-duplex.dtbo \
    -Wno-unit_address_vs_reg shared/dsp4-logic/pi/dsp4-pcm-duplex.dts
sudo cp dsp4-pcm-duplex.dtbo /boot/firmware/overlays/

# 3. /boot/firmware/config.txt — one line changes
-dtoverlay=dsp4-pcm-slave
+dtoverlay=dsp4-pcm-duplex
```

Nothing else in `config.txt` changes. The bench was left on the SHIPPING
`dsp4-pcm-slave` line with a backup at `config.txt.pre-duplex-20260908`;
both `.dtbo`s and the module are installed, so the flag is a one-line flip.

**WHAT IS STILL NOT A MEASUREMENT CHANNEL, and it is no longer the
overlay.** With the loop up, a known word played through it comes back
riding a large DC pedestal (~`0x11E7E000`, about 0.28 in Q4.28) and moving
only slightly with the input, so the path is not yet unity: the main chain
(`MIX_MAIN_L → MAIN_FDR → GEQ → COMP → LIM → DLY → ST_OUT`) sums seventeen
sources and none of its nodes was set to bypass. That is step 1 of the
queued block — "pass-through strip, all nodes unity/bypass" — and it is now
the only thing between here and a latency figure.

### S2-8 — `ChanGateHold` and `ChanDelay` FIXED: a wire-unit conversion at the SPI boundary

**Severity: major. Status: FIXED and verified on the part.**

S2-1 recorded the defect; this is the fix, and it is deliberately not a fix
for `Hold`. `defs/common/wire/wire-units.csv` is the LANDED declaration of
what each family carries on the wire and what its kernel word expects, and
`gen_dsp.py` now builds a conversion table from it: any family whose
declared unit differs from its kernel word gets a conversion id, and every
SPI address that family reaches carries it. `_spi_dispatch_cN_convert[]`
sits beside the dispatch and stride tables with the same indexing, and
`spi_handler.asm` applies it. Written as a one-off for Hold, `ChanDelay`
would have stayed broken in exactly the same way — which is how it was
found:

```
  wire-unit conversions applied at the SPI boundary:
    ChanDelay          ms -> samples    32 addresses
    ChanGateHold       ms -> samples    32 addresses
```

**AT THE WIRE, NOT IN THE NODE'S CONTROL-RATE PREP**, and the reason is the
ramp engine: it reads the CURRENT word and interpolates towards the new
one, so a current word in samples and an incoming one in milliseconds makes
every value the ramp passes through meaningless — and the handler's own
up/down test compares the two as floats before that. A unit change belongs
at the boundary where the unit changes.

**BOTH DIRECTIONS.** The read path converts back, so a host reads the unit
it wrote. Without that, save-and-restore — what every probe on this bench
does around a write — would read samples and write them back as
milliseconds. Measured on the part, 2026-09-08:

| cell | written | kernel word | read back |
|---|---|---|---|
| `Chan001GateHold001` | 1.0 ms | `_gate_hold` = **48** | 1.0000 ms |
| `Chan001GateHold001` | 50.0 ms | `_gate_hold` = **2400** | 50.0000 ms |
| `Chan001GateHold001` | 0.0 ms | `_gate_hold` = 0 | 0.0000 ms |
| `Chan001Delay001` | 20.0 ms | `_dly_read_offset` = **960** | 20.0000 ms |
| `Chan001Delay001` | 0.0 ms | `_dly_read_offset` = 0 | 0.0000 ms |

2400 is the generator's own initialiser for `_gate_hold_<nid>` (50 ms at
48 kHz), so the conversion reproduces the value the kernel was written
around. The samples-per-millisecond constant is GENERATED from
`dsp_codegen.SAMPLE_RATE_HZ` into `_spi_dispatch_cN_spms` rather than typed
into the assembler — a conversion that names the sample rate twice can
disagree with itself.

**WHAT IS DECLARED-BUT-NOT-CONVERTED IS REPORTED, NOT SKIPPED**, every
generation:

```
  wire-unit mismatches DECLARED but NOT converted
  (the contract states the mismatch, not the conversion):
    ChanCompAtt   wire 'ms (log table)' -> kernel 'alpha coefficient — needs conversion declared'
    ChanCompRel   ...    ChanGateAtt    ...    ChanGateRel   ...
    ChanMute      wire 'bool 0/1'  -> kernel 'coefficient fold to exact 0'
    ChanPol       wire 'bool 0/1'  -> kernel 'coefficient sign fold'
    Chan_Mtr      wire 'dBFS readback' -> kernel 'Q4.28 fixed via float mirror'
    ChanName      wire 'text' -> kernel 'n/a — host-side only'
    MainComp      wire 'mixed — see per-cell rows' -> kernel 'per-parameter'
```

The four ms→alpha rows say "needs conversion declared" in as many words:
the contract states the mismatch and not the conversion, and inventing one
here would be this spoke declaring cell semantics it does not own. **They
are the next thing the hub can land**, and the mechanism is now waiting for
them — a row plus a rule, no per-cell code. `ChanGateRng` (dB→linear, D39)
and `ChanCompPar` (percent→fraction, D40) are excluded deliberately: the
node's control-rate prep already converts them, and a second conversion at
the wire would apply it twice.

**AUX AND GROUP DELAYS ARE NOT COVERED, and that is the contract's gap
rather than the mechanism's.** `AuxDelay`, `GrpGateHold` and the rest reach
the same class of kernel word and have no row in `wire-units.csv`, so
nothing here converts them. Landing those rows is all it takes.

### S2-9 — the float cascade IS `bq_float_ref` on the part, 0 ULP

**Severity: none — this is the bar the numeric target names, run.**

`shared/numeric-spec.md` states the float arm's bit-exact bar as "SHARC
float cascade ≡ `bq_float_ref`, proved on the part by `bqeverify.sh
float`". It was run on this tree (block 8, image chip1 `adeb3f0c` / chip2
`3c48d892`):

```
ARM A  _bq_fx_cascade_simd  hash 0x7136AFED sum 0xD1246B11
       vs bq_float_ref offset wire 0x7136AFED/0xD1246B11   MATCH
ARM B  _bqfd_cascade_simd   hash 0x3E4B7636 sum 0xD11DDA0E
       vs bq_float_ref direct wire 0x3E4B7636/0xD11DDA0E   MATCH
A vs B: 14810 of 18432 words differ, first at 3, max |d| 22784
        model predicts 14810, first at 3, max |d| 22784     MATCH
        divergence bitmap: part 566 of 576 cells, model 566 MATCH

BQE_VERIFY PASS — 0 ULP over the whole vector set, and the offset
reconstruction is live
```

192 cascades x 4 stages x 3 drive levels x 4 blocks = 18,432 output words
per arm. The bar is two-sided by construction: a one-sided "assert zero
differences" would pass on a rig that never drove anything hard enough to
saturate, so the divergence bitmap is checked cell by cell and the two arms
have to disagree on exactly the 566 cells the model names.

So `EQ_BIQUAD`, `HPF_LPF`, `GEQ`, `CROSSOVER` and `ANTI_FB` have their
KERNEL verified against its normative reference — separately from whether
the graph node runs it, which for the last three it does not (S2-6).

### S2-10 — METER is bit-exact; the family walk's own verdict on it was wrong

**Severity: medium (instrument). Status: fixed, and the earlier verdict
retracted.**

`mtrverify.sh` reads **METER_BIT_EXACT**: the 64-bit meter state reproduces
`fixed_ref.meter_block` exactly, the float readback is peak 0.5 / rms 0.5
at 0.000e+00 relative error, the BLOCK=32 negative control is correctly
rejected and the wide-word control rejects the narrow model.

`dsp4_family_verify.py` had reported `DISAGREES` for METER: `_mtr_peak_
C1_MTR_01` read `0x40E1AFA1` (7.05 as float32) against a captured
post-trim peak of exactly 0.5. **A peak HOLD carries state**, and the
contract sweep that runs immediately before it writes `1.0f` into every rw
cell of the node under probe, which drives the strip close to full scale;
the hold had not decayed by the time the meter was read. 7.05 sitting just
below the Q8.24 ceiling of 8.0 was the tell, and it was not followed.

The lesson is the one this bench keeps relearning in new clothes: a
stateful readback is not a measurement unless the state is controlled.
`meter_phase()` now reports `NO_VERDICT` with the reason and names the
family's real bar rather than scoring a number it cannot interpret, and
`hw_coverage.py` scores a family by a dedicated bar's verdict — with the
bar and the image recorded — where one has been run.

### S2-11 — the loop is a PASS-THROUGH with no pedestal, and it does not preserve sample order

**Severity: major (bring-up). Status: the pedestal is CLOSED, the ordering
is OPEN and characterised.**

Step 1 asks for a pass-through that is bit-exact end to end. Three of its
four parts are now measured; the fourth says the loop cannot carry a
latency figure yet.

**THE PASS-THROUGH, from the contract.** Seventeen sources sum into
`C2_MIX_MAIN_L` — `C2_RECV_MAIN_L` (chip 1's whole 24-strip bus), the four
`C2_GRP_COMP_*`, `C2_USB_IN`, `C2_BT_IN`, `C2_CODEC_AUX_IN`, `C2_PI_IN` and
the eight `C2_SNK_IN_*`. `passthru_setup.py` silences sixteen of them by
CELL NAME out of the landed map: 24 strips taken off the main bus AND muted
(48 cells, two independent ways, because one inert cell would otherwise
leave the bus live and look like a pedestal), `Usb001On001` /
`Bt001On001` / `CodecAux001On001` cleared, the four `Grp*Mute001` set, the
main fader at unity and `Main001Delay001` zero. **Every one of those 60
cells is in the contract** — the run reports which are not, and none were.
The eight snake returns have NO cell in the landed map at all and could not
be silenced from the contract; on this bench nothing is connected to them,
and the measurement below shows they contribute nothing.

**NO PEDESTAL.** With the setup applied and nothing played, the whole main
chain reads zero at the scope — `_buf_C2_MIX_MAIN_L`, `_buf_C2_MAIN_FDR`,
`_buf_C2_MAIN_DLY` and `_buf_C2_MAIN_ST_OUT` all `0x00000000` — and the
captured measurement channel idles at **8 LSB, about −168 dBFS**, which is
the residue on the TDM slot nothing drives. The `0x11E7E000` pedestal
(0.28 in Q4.28) that made the earlier capture unreadable is gone.

**THE ×2 WAS A LEVEL, NOT A SHIFT.** At `Pi001Level001 = 1.0` a known word
returned doubled, which reads like a one-bit scatter/gather asymmetry. It
is not: at **0.5** the loop returns unity, and `_auxin_q_C2_PI_IN` reads
`0x08000000` — Q4.28 0.5 exactly, target matched, frames 0, so the
coefficient is settled and exact. The node carries a factor of two the cell
value does not describe. Same class as S2-5 and a question for the unit
rows, not a defect in the path.

| played | returned | ratio |
|---|---|---|
| `0x00001000` | `0x00001000` | **1.0000**, `in << 0` |
| `0x00010000` | `0x0000FFF8` | 0.9999 |
| `0x00100000` | `0x000FFF88` | 0.9999 |

So the loop is amplitude-accurate to about 1.2e-4 (−78 dB) and **not
bit-exact**; the residual is not the Pi coefficient and is not yet
attributed.

**NO L+R SUMMING, AND THE RETURN IS MONO.** Played into L only the word
returns; into R only, nothing returns; into both, the same as L alone. That
settles a question the ×2 had made ambiguous. It also confirms on the part
the standing note that `C2_MAIN_ST_OUT` drives TDM slot 0 only.

**THE CAPTURED CHANNEL IS NOT FIXED.** The same stimulus came back on L in
one capture and on R in the next: the Pi is an I2S slave and LOGIC regroups
four Pi frames into one DSP frame, so the word a stream starts on is not
determined. `dsp4_loopcal.py` phases every capture before reading it and
reports which channel carried the return. Reading a fixed channel is what
made one run print `ratio 0.0000` for a loop that was working.

**AND THE LOOP DOES NOT PRESERVE SAMPLE ORDER — so no latency is quoted.**
A counter whose every value was held for **64 Pi frames (16 DSP frames)**
still comes back with only **40.4 % of transitions monotonic** (59,498
carrying frames), the dominant index step being about **−9 values ≈ 576 Pi
frames** backwards. Holding each value for 4 frames — the regrouping ratio —
is not enough either. DC returns perfectly and a ramp does not, which is
the signature of a reader sampling the wrong one of the four regrouped Pi
frames and periodically re-reading a stale region, rather than of a gain or
a clock error.

**A latency measured through a path that reorders is not a latency**, so
none is recorded. What the loop supports today is amplitude measurement on
slowly-varying or DC stimuli; a per-sample vector set needs the ordering
closed first. The next probe is the CPLD reframe (`rtl/dsp4_pcm_reframe.v`)
against the DSP's Pi-input DMA, not the ALSA layer — that part is now known
good.

### S2-12 — busgold: the graph is bit-exact across the wire-unit conversion

**Severity: none — a bar owed and paid.**

The audio image changed this session (S2-8), so the standing "the image is
byte-identical, therefore the capture cannot have moved" argument that had
covered `busgold` no longer applied. Run on the part:

```
strip 1 driven, 2 muted: 256/256 non-zero, sha256 ba3f52ecb83f9a60
postD59 vs cur: 0 of 256 words differ
GRAPH BIT-EXACT
```

`ba3f52ec` is the stored golden's own hash, so the capture reproduces
`goldens/busgraph-postD59-20260830.json` word for word. That is the
predicted result and it is now a measurement: `dsp4_pairgraph.py` writes
`DlyOff` as a raw `0`, which the new conversion maps to 0 ms → 0 samples,
and it never writes `GateHold` at all — so the conversion is audio-neutral
for this harness by construction, and the bar confirms it rather than
assuming it. The harness's two standing caveats still apply and are printed
by it: the biquads are in bypass and the gain is unity, so this comparison
says nothing about paired biquads or about GAIN's rounding.

## dsp.csv proposal (2026-09-08)

Session: propose `defs/products/{d24,d32}/dsp.csv` against `defs-v2026.09.08`.
Write-up: `MW/D32/DSP/dsp4-dspcsv-proposal-20260908.md`.

### S1-1 — CLOSED by ruling; four outputs, four strips

PW confirmed the 2026-08-25 main section model mid-session: `Main[1-1]` is the
stereo mix-bus strip and L / R / Ctr / Sub are each a post-crossover OUTPUT
strip. The four chains off `C2_MAIN_XOVER` map to `MainL` / `MainR` /
`MainCtr` / `MainSub` in DAC_13..16 order, `C2_SUB_*` is retired, and the
eight graph nodes that S1 could only report as unnamed now either reach a
strip or say what replaces them. `defs/tools/def_master.py` corroborates the
ruling independently: `MainCtr` is gated on `main.ctr` and the D24-only cell
`Main001Out3Mode001` — an OUT 3 MODE cell — is gated on the same key.

`MainCtr` is emitted for BOTH products at one address; D24 reaches it and D32
lists it out of product scope. That is decision D3's one shared address map
made structural rather than promised: 3,658 cells appear in both proposals
with **zero** address disagreements.

### S1-4 — the meter `taps=` declaration was wrong about what the DSP writes

**Severity: major. Status: fixed.**

A meter node meters ONE tap point and lays `peak` at +0, `rms` at +1, `gr` at
+2 and its own state array at +3. `taps=` therefore names meter WORDS, and
reading it as tap points produced two wrong cells:

- `taps=L;R` on the four mono main-output meters made the RMS word into an
  `R` channel, giving each output strip an `Mtr002` no master defines (two of
  the 23 orphans S1 found). The word keeps its dispatch entry — the host can
  still read it — and loses only the cell.
- `Chan*CompMtr001` (32 cells) was addressed at base+3, which is
  `_mtr_st[0]`, the meter's internal peak-hold state. A cell pointed at
  another variable's scratch is not reaching a DSP address; CompMtr is now
  listed as `unbacked-meter`. This is the read side of recorded defect 4:
  `gate_gr` is declared and never written, `comp_gr` has no word at all.

### S1-5 — `_parse_taps`: `parse_params()` splits on the tap separator

**Severity: major (would have been silent). Status: fixed in the same change.**

The first rewrite of `expand_meter` read the declaration with
`parse_params()`, which splits on `;` — the character that also separates the
taps. `taps=post_trim;post_fader;gate_gr;comp_gr` came back as
`{'taps': 'post_trim'}` and three of the four channel-meter words vanished
without a warning. Caught by the cell counts, not by a test. `_parse_taps()`
reads to the end of the params or the next `key=`.

### S1-6 — the post-crossover output strips have no fader, mute or delay

**Severity: major. Owner: PW / capacity. Status: open (Q1).**

All four output strips define `Level`, `Mute` and `Delay`; chain N in the
graph is EQ + COMP + LIM only. Twelve cells across the four strips reach no
word. Retiring `C2_SUB_*` makes this visible on `MainSub`, which had those
addresses through the sub bus strip; `MainL`, `MainR` and `MainCtr` never had
them. Closing it is four `FADER_PAN` and four `DELAY` nodes on chip 2, which
is the tighter part at 83.16% — a capacity decision, not a desk one.

### S1-7 — `CtrOn` and the retired sub bus cannot both be right

**Severity: major. Owner: PW. Status: open (Q3).**

Every channel defines `CtrOn[1-1]` — on D32 too, which has no `MainCtr` — and
its DSP word is `_rtg_sub_on_<nid>`, a per-channel assign to the `BUS_SUB`
mix bus that feeds the strip the ruling retires. If there is no centre/sub
mix bus, `CtrOn` has no destination; if `CtrOn` is real, that bus is real and
outputs 3 and 4 are not simply crossover taps. The cell keeps its address in
the proposal; one of the two has to give.

### S1-8 — D24's legacy SHARC graph is not a second address map

**Severity: minor (a trap avoided). Status: recorded.**

`MW/D24/DSP/SHARC/dsp.csv` is 201 nodes with no faders, routing, aux, groups,
meters or crossover. Deriving D24's addresses from it would have produced
exactly the second address map D3 forbids. D24's proposal is derived from the
superset DSP4 graph and filtered by D24's own cell set. The legacy file's
three `dsp_validate` parameter errors were fixed in place
(`source_gains` → `source_count`, `wet`/`dry`/`width` → `mix`); both product
files now validate clean.

## defs S1 (2026-09-08)

Session: adopt the `invirco/defs` submodule at `defs-v2026.09.08`, retire the
dsp-side expander and back-fill. Write-up:
`MW/D32/DSP/dsp4-defs-s1-20260908.md`.

### S1-1 — the graph has four main outputs and the product definition has three

**Severity: major. Owner: dsp.csv (the next dispatch). Status: open, now loud.**

This is review finding **D52** and S1 makes it visible instead of resolving it.
`defs-v2026.09.08` models the main section as one L/R bus strip (`Main001`:
fader, mute, DCA, 250 ms delay, 28-band GEQ, cue) plus **three** post-crossover
output strips — `MainL001`, `MainR001`, `MainSub001`, each with its own EQ,
compressor, limiter, delay, fader, mute and meter. `MW/D32/DSP/SHARC/dsp.csv`
builds **four** post-crossover chains off `C2_MAIN_XOVER` (DAC_13..16) plus a
separate sub-bus strip `C2_SUB_*` out to NET_OUT_01.

The consumer-side mapping now says exactly what it can defend and reports the
rest:

- `C2_SUB_*` → `MainSub001`. The master row notes came across verbatim
  ("Subwoofer compressor attack", "Subwoofer output level meter"), so the
  standalone `Sub` category was folded into the main section, not deleted.
- `C2_MAIN_O{EQ,COMP,LIM}_01/02`, `C2_MTR_MAIN_01/02` → `MainL001`, `MainR001`.
- `C2_MAIN_O{EQ,COMP,LIM}_{03,04}`, `C2_MTR_MAIN_{03,04}` → **nothing**. Eight
  graph nodes hold SPI addresses the DSP will answer on and no cell in the
  product definition names them. `gen_dsp.py` lists all eight by id and type.
- `C2_MAIN_COMP` and `C2_MAIN_LIM` (the main BUS dynamics) emit 21 cells the
  masters no longer carry: output dynamics moved onto the per-output strips.
  With `MainL001Mtr002`/`MainR001Mtr002` — the L;R meter taps on what is now a
  mono output strip — that is the 23 cells `validate()` reports as not in
  `_matrix.csv`.
- `MainL001Level001`, `MainL001Mute001`, `MainL001Delay001` and their `MainR`
  and `MainSub` twins are documented and unimplemented: the graph has one main
  delay and one main fader, not one per output strip.

**Why it was not fixed here:** the S1 dispatch bounds the session out of
dsp.csv authoring ("that is the next dispatch: dsp proposes `dsp.csv`, hub
lands it at the gate"). Choosing three chains over four, or giving each output
strip its own fader and delay, is a product decision with a cycle cost, not a
naming fix.

### S1-2 — two families the prune step called aliases are definitions again

**Severity: minor. Owner: hub (defs). Status: open, reported.**

`alias-retire-families.txt` deleted eight families from every expansion up to
`defs-v2026.08.20`, on the reading that they were compatibility aliases.
`defs-v2026.09.08` carries two of them:

| formerly pruned | D32 rows now | alongside |
|---|---:|---|
| `FxDuckThr` | 6 | `FxDuckSens` (6) |
| `PeqGain` | 12 on `MainL`, 12 on `MainR` | `Main001Geq[1-28]` |

Neither reaches a DSP address. They may be intentional (a per-side output PEQ
is a real feature; a duck threshold and a duck sensitivity are not obviously
the same control) or they may be the alias the July prune thought they were.
`defs` is the source of truth either way, so this repo carries them and says
so rather than deleting them again — deleting rows from the expansion and
renumbering `MxAdd` behind them is what made this repo a second source of
truth in the first place. Tracked in `alias-audit.md`.

### S1-3 — the H1S1 dispatch map was missing 2,064 cells and nothing said so

**Severity: major, and closed by this session. Owner: dsp. Status: fixed.**

`mx_dsp_map.h` keys matrix rows to `ghost_cells[]` indices **by cell name**.
Under the old pin the ghost table spelled the current master names
(`Chan001Mute001`) while `_matrix.csv` spelled the pinned ones
(`Chan001RtgMute001`), so those rows silently produced no map entry: the map
held 3,417 entries against 5,481 ghost cells, and `DspDispatch()` could not
reach a routing cell at all. `gen_dsp.py` reported the split as an INFO line
about legacy-spelling hits, which is a true statement that does not read as
"the MCU cannot dispatch to a third of the table".

One spelling closes it: the map now carries **5,393** entries. Nothing in the
DSP image changes (the dispatch tables key on `dsp.csv` node ids, not on cell
names, and all four W0 witnesses rebuild byte for byte), and **H1S1 was not
rebuilt in this session** — the fix is proven in the generated header, not on
an MCU.

### S9-1 — the build that shipped was not the build that was measured, in three parameters

**Severity: MAJOR (shipping configuration). Status: FIXED.**

Block size, block kernels and the core clock were all set one way in the
measurement scripts and another way in the build the images come from,
and no instrument could see it because every instrument was reading the
same wrong build.

* **BLOCK.** PW ruled 2026-09-03 that block 16 is the configuration that
  fits both chips. The ruling was applied only inside the measurement
  scripts, which generate a scratch tree with `DSP4_GEN_BLOCK` and build
  it through `DSP_SRC_DIR`. `dsp_codegen.py` carried `BLOCK = 8` as a
  literal from 2026-08-28 until 2026-09-09, so the committed tree — and
  therefore `./build.sh` — was never generated at anything but 8. Nothing
  drifted back; the ruling never reached the tree.
* **BLOCK KERNELS.** Every capacity figure since 2026-09-01, the `.4`
  record included, is a `DSP4_BLOCK_KERNELS=1` build. The default was 0.
* **CORE CLOCK, and this one had never been noticed at all.** Every cycle
  budget since 2026-08-24 is quoted at 983.040 MHz on the strength of
  PW's U5/U6 reading (`ADSP-21564KSWZ10`). `DSP4_CCLK_TARGET` defaulted
  to 0, which leaves the CGU on its reset divisors at 491.52 MHz. Read
  off the running window pair: `CGU0_CTL 0x00002800`, `CGU0_DIV
  0x05144281` on BOTH chips — exactly the "today" row of
  `src/cgu_init.asm`, not the 983.040 row (`0x00005000`). So the
  block-8 shipping image was over an 81,920-cycle budget, and its
  overrun was **4.03x on chip 1 and 3.50x on chip 2**, not the 2.02x and
  1.75x S8-2 scored against a clock the image did not have.

Fixed by naming the configuration in one file — `MW/D32/DSP/SHARC/
shipping.config`, sourced by `build.sh` and read by `dsp_codegen.py`
through `tools/dsp/build_config.py` — regenerating the tree at block 16
so `./build.sh` with no overrides IS the shipping configuration, and
making `build.sh` refuse a tree whose `dsp_block.h` disagrees with
`DSP4_GEN_BLOCK`. The image carries `DIAG_BUILD_CFG` (0xE0EA) so a
mismeasured configuration can never be silent again; the shipping word is
`0xCF45FF10`. On the fixed configuration, D24 mask: chip 1 234,594
cycles/block (71.6 % of 327,680), chip 2 303,894 (92.7 %),
`DIAG_BLK_OVERRUN` 0 on both over 600 s.

### S9-2 — the first frame of each DMA half has an earlier deadline than the block does

**Severity: MAJOR (product audio). Status: OPEN — mechanism named and
measured, margin improved, structural fix needs PW.**

With the block loop fitting the block and `DIAG_BLK_OVERRUN` at zero, the
chip-2 transmit path is still not exact at the D24 mask. The whole gather
runs at the END of the block period, after the node graph has spent
92.7 % of it, and the DDE clocks frame 0 of the half out FIRST. Those
frames lose the race and leave the part carrying what that half held TWO
BLOCKS earlier.

The count of late frames per block tracks the LOAD, not the block, which
is what makes it a race and not an indexing error. Transmit stamp,
192,000 frames, `_maincap` `d903ae1ac4a9`:

| arm | stamp order | late frames/block |
|---|---|---|
| node graph out of the way (`DSP4_BLOCK_MASK=5`) | 100.0000 % | 0 |
| load cut to one strip and one aux | 100.0000 % | 0 |
| full D24 graph | 87.4999 % | 1 |
| full D24 graph, `DSP4_GATHER_FIRST=1` | 100.0000 % | 0 |
| full D24 graph + the Pi playback input | 81.2499 % | 2 |

The two 100 % rows are also what confirms the 2026-09-09 ping/pong phase
fix (`DSP4_BLK_LATCH`) still holds at block 16.

`DSP4_GATHER_FIRST=1` moves the gather to the head of the loop body, in
front of `_scope_record` and the parameter-link poll, neither of which it
depends on. Worth about one frame of margin; at the heavier load both
orders measure 81.2499 % repeatably. **Margin, not a fix.**

The lever: give the gather a whole block period of slack — write block
N-1's outputs at the top of period N, or a third TX buffer. Both cost one
more block of output latency (16 samples, 0.333 ms) and both are
architecture decisions. Reducing chip 2's 92.7 % is the other half of the
same lever.

### S9-5 — famverify's audio arm moves 17/20 -> 8/20, and BLOCK KERNELS are the reason

**Severity: MAJOR (bar, and possibly product audio). Status: OPEN —
attributed, not explained.**

Three arms, one variable at a time, same bench, same contract
(`landed-d24.json`, 3,737 cells, sha256 `4aa3c343cedf`, pin
`defs-v2026.09.08.4`), same day:

| arm | BLOCK | kernels | CCLK | audio LIVE |
|---|---|---|---|---|
| the `.4` configuration, rebuilt | 8 | 0 | 491.52 | **17 of 20** |
| the discriminator | 8 | **1** | 491.52 | **8 of 20** |
| shipping | 16 | 1 | 983.04 | **8 of 20** |

The block-8 per-sample arm reproduces the `.4` line exactly, so the move
is not the bench or the day; block 8 WITH kernels gives the same 8 of 20
as block 16, family for family, so it is not the block size or the clock
either. **It is `DSP4_BLOCK_KERNELS`.**

The eight families that move are all chip-1 strip-chain nodes witnessed
at `_buf_C1_*` — COMPRESSOR, DELAY, EQ_BIQUAD, FADER_PAN, GATE and
HPF_LPF go INERT, ROUTING and TUBE_SAT go SILENT, COMPRESSOR's numeric
arm goes BIT_EXACT -> FAILED. The chip-2 families witnessed with an
impulse are unaffected, and **every family's contract arm is unmoved in
all three arms**: GEQ 31/31, CROSSOVER 8/8, ROUTING 42/42, COMPRESSOR
17/17, 0 failed.

Not settled: whether this is an audio defect or a witness that does not
hold in the block-kernel arm. The mechanism that would explain it with no
audio wrong is that `_scope_record` runs in the GATHER loop, after
`_chipN_process_all` has processed the whole block, so `_buf_<node>`
holds only the last sample of the block when the scope samples it and the
recorded window is one word repeated; a step settles, so a parameter
change that alters the waveform but not its settled value reads INERT.
Against a real regression: `c2gold.sh`'s D80 record has the block-kernel
arm bit-exact against per-sample except in the meters.

Settled by a block-aware witness — record `_blk_<node>` where the class
publishes one, or move `_scope_record` inside the kernel — and re-running
the three arms. **Block kernels have been in every capacity measurement
since 2026-09-01 and had never been through famverify once**; making them
the shipping configuration is what exposed that.

### S9-3 — D32's all-ones mask does not fit at block 16

**Severity: MAJOR (product scope). Status: OPEN.**

The same shipping configuration that fits D24 with 7.3 % of margin does
NOT fit D32: with all 32 strips and 12 aux buses active, chip 2 missed
**11.3 %** of blocks in a loaded run (1,552 overruns in 13,773 blocks).
D24 in the same script and the same session missed zero. D32 at block 16
is not a shipping configuration on this firmware, and the capacity work
that would make it one is chip 2's, not chip 1's — chip 1 sits at 71.6 %.

### S9-4 — the Pi playback input is off by default, and the loop is not bit-transparent

**Severity: MINOR (bench procedure). Status: RECORDED.**

Two things have to be done before the through-DSP staircase measures
anything, and neither is in any script:

1. `C2_PI_IN` is an `AUX_INPUT` with `on=0` and `level_db=-6.0` in
   `dsp.csv`. The stimulus crosses the fabric intact — `_blk_C2_XR_PI_L`
   reads `0x04000000` for a `0x20000000` stimulus, the documented 8x
   round-trip attenuation — and the node publishes zero, so the capture
   is a constant and every scorer reports 0 % exact on a loop that may be
   perfectly ordered. Write `0x0744 = 1` and `0x0743 = 1.0f` on chip 2.
2. The rest of the chip-2 graph sums a constant into MAIN, so the loop
   carries the staircase PLUS a DC offset. `dsp4_order_stair.py` and
   `dsp4_tx_order.py` both test for the exact stimulus value and score
   0 % on a capture that only differs by that constant. Score against the
   step index with the DC removed.

With both done, the audio and the transmit stamp agree to a tenth of a
percent on the same capture (82.3458 % against 81.2499 %), which is what
establishes that the staircase's disorder IS the transmit-path disorder.

### S10-1 — S9-5 SETTLED: block kernels are NOT an audio defect; the witness and the stimulus were

**Severity: MAJOR (closes S9-5). Status: CLOSED.**

S9-5's 17/20 → 8/20 was **entirely the bench instrument**, and it was two
independent defects on chip 1, not one. With both fixed, the shipping
configuration — block 16, block kernels, 983.04 MHz — reads **17 of 20
LIVE and agrees with the block-8 per-sample control on all twenty
families, verdict for verdict**; the contract arm is identical on every
family and the numeric arm is BIT_EXACT on COMPRESSOR, FADER_PAN and
TUBE_SAT.

**Defect one — the witness read a variable the kernel never writes.**
Under block kernels a chip-1 strip node writes a *shared pool slot*
(`blk_pool.h`), and `_buf_<node>` survives as a one-word `.var` that
nothing writes. `_scope_record`'s `#if DSP4_BLOCK_KERNELS` arm reads
`_scope_src + _sample_idx` — right for chip 2, whose kernels really do
publish `_blk_<node>[BLOCK]`, and on chip 1 a sixteen-word walk off a
one-word variable into the next node's parameters. Named in the link map:
`_buf_C1_GAIN_01 + 4 = _gain_coeff_C1_GAIN_02` (read back as 1.0f),
`_buf_C1_EQ_01 + 3 = _eq_coeffs_A_C1_EQ_02` (4.0f), `_buf_C1_DLY_01 + 6 =
_dly_max_C1_DLY_02` (12000). So GAIN and TALKBACK's arm-B "LIVE" was the
witness watching the parameter class the test was stepping. For the nodes
whose `_buf_` *is* written once per block, `moved` was exactly `N/BLOCK`.

**Defect two — the stimulus went into a slot with no reader.**
`_scope_inject_blk` fills `BLOCK` words at the RX-slot symbol the host
names. On chip 2, `_rx_ic_slot_<node>[BLOCK]` is a real array the chain
reads. On chip 1, `INPUT_TDM`'s kernel reads DMA straight into a pool slot
and `_rx_slot_<node>` is a one-word variable nothing reads — so the
stimulus went nowhere **and** fifteen words landed past the end of it.

The two are separable and were separated: fixing the witness alone
(arm C) leaves 9/20, with the peaks now honest (`0`, `1`, `4` — real
Q4.28 magnitudes) and the verdict SILENT. Both halves were needed.

**The witness proved itself first.** NOISE_GEN generates its own signal;
in arm C it read peak **268,365,104** against the per-sample control's
**267,776,416** while every stimulus-driven family correctly read silence.

**Consequence for the record: every block-kernel famverify run since
2026-09-01 was measuring its own instrument on chip 1**, and no chip-1
audio conclusion from those runs should be quoted.

Instrument: `DSP4_SCOPE_BLK_TAP` (default 0, never ships — a default
`./build.sh` reproduces `ac65ad38`/`e5dce9e4` byte for byte after every
change in this session). Write-up
`MW/D32/DSP/dsp4-block-witness-20260909.md`.

### S10-2 — a pooled buffer cannot be witnessed after the block, and the table that fixes it

**Severity: MINOR (method). Status: RECORDED.**

The pool is reused: strip N's `BLK_CHAIN_B` is strip N+1's the moment
strip N+1's GAIN runs, and by the end of a block every slot holds the last
strip that touched it. **There is no later point at which a given node's
block still exists**, so no witness that runs in the gather loop can ever
be correct for a pooled node — this is not a bug in `_scope_record`'s
timing, it is a property of the pool.

The tap therefore runs *at* the node, from the generated chain, and is
handed the address by the generator. Which slot each strip class publishes
into lives in `_STRIP_BLK_OUT` (`tools/dsp/dsp_codegen.py`), the same kind
of table as `_METER_SRC_BLOCK` and under the same rule: `_blk_out_of()`
**checks the table against the body it just generated** and fails the run
if a kernel has moved onto a different slot. A table of facts about
generated code that nothing checks is a table of facts about code that
used to exist.

### S10-3 — `_scope_inject_blk` overruns `_rx_slot_C1_IN_01` by fifteen words in the SHIPPING image

**Severity: MINOR (latent; bench-triggered only). Status: OPEN — needs PW.**

The overrun described in S10-1 is in the shipping image too, not only in
the instrument: `_scope_inject_blk` is compiled under `DSP4_BLOCK_KERNELS`,
not under the tap flag. It is inert in the field — `_scope_inj` is 0 until
a host arms the scope and nothing in the product does — but it is a real
out-of-bounds write and it should not stay. **Not fixed here**, because
fixing it changes `ac65ad38`/`e5dce9e4` and a new pair is a window
decision.

### S10-4 — GATE's NUMERIC arm reads NO_STIMULUS in a block build

**Severity: MINOR (bar coverage). Status: OPEN.**

With the block-aware witness, GATE's **audio** arm is LIVE and its
contract arm is 12/12, but its NUMERIC arm reads `NO_STIMULUS` where the
block-8 per-sample control reads `BIT_EXACT`: `dsp4_node_verify`'s own
stimulus search found no usable point in a block build. COMPRESSOR,
FADER_PAN and TUBE_SAT are BIT_EXACT in both arms, so this is specific to
GATE and to the second instrument, not to the family.

### S10-5 — `DIAG_BUILD_CFG` has no spare bit, so an instrument build can still be silent

**Severity: MINOR (method). Status: OPEN.**

Bits 8..23 of `DIAG_BUILD_CFG` are all allocated and 31..24 is the 0xCF
signature, so `DSP4_SCOPE_BLK_TAP` could not be added to the word that
exists to stop exactly this. The tap build is identified by its build
banner and by `_scope_tap` in its map — neither of which the *part* can be
asked. Widening the word means moving the signature and every check built
on `0xCF45FF10`, which is not a thing to do on the last day before a
window.

Partial mitigation landed: `dsp4_family_verify.py` now records
`build_cfg` per chip in its JSON. Five famverify reports were taken on
2026-09-09 in five different configurations and not one recorded which, so
telling the control from the arm meant trusting a filename.

### S10-6 — the capacity record's instrument and the shipping image disagree, and chip 2's gap is unexplained

**Severity: MAJOR (the capacity record). Status: PART OPEN.**

`sigprofile.sh` / `sigprofile2.sh` / `fxcost.sh` build an INSTRUMENT:
`DSP4_PROFILE_SIGNAL=1` (so the dynamics cannot be measured on their cheap
branch) and `DSP4_BLOCK_DECIMATE=32` (so a graph that does not fit still
completes). Right for attributing cost to a class; not the image that has
to fit. Measured both ways in one session, block 16, 983.04 MHz read back:

| | the record's instrument | the shipping pair | gap |
|---|--:|--:|--:|
| chip 1, D24 | 408,939 (124.8 %) | 234,267 (71.5 %) | +174,672 |
| chip 2, D24 | 225,646 (68.9 %) | 303,891 (92.7 %) | **−78,245** |
| chip 2, D32 | 261,093 (79.7 %) | 369,424 (112.7 %) | **−108,331** |

Chip 1's is EXPLAINED: `DSP4_PROFILE_SIGNAL` + `TUBEON=1` put all 32 strips
on their expensive branch, so 408,939 is the honest signal-present worst
case and 234,267 is the same graph on a silent bench.

Chip 2's is NOT. It is 24 % of budget at D24 and 33 % at D32, in the
direction the signal/silence split cannot produce. `DSP4_BLOCK_DECIMATE=32`
is the remaining candidate — it gives the graph thirty-two block periods,
so nothing in the block loop ever contends. **Until this is resolved a
chip-2 margin quoted from `sigprofile2`/`fxcost` is a margin for the
instrument.** The same disagreement shows up in the D24 mask's value:
35,447 cycles on the instrument, 65,533 on the shipping pair.

`tools/pi/dsp4_capacity.py` reads the shipping pair directly and is the
arbiter: `_proc_cyc`, `_proc_cyc_max`, `DIAG_BLK_OVERRUN`, and the CGU
words so the budget comes from the clock the part is running.

### S10-7 — a measurement bar could destroy the artifact the product ships

**Severity: MINOR (bench procedure). Status: PART FIXED.**

`famverify.sh`, `sigprofile.sh`, `sigprofile2.sh` and `fxcost.sh` all
`scp build/chip1.ldr build/chip2.ldr` into `/home/app/dspboot/` — which is
where `chip1.ldr` / `chip2.ldr`, two of the staged pairs the window rolls
back to, live. Running a bar overwrites them.

`famverify.sh` now takes `STAGE` (default `/home/app/dspboot`, so nothing
that calls it changes) and symlinks the shared bench helpers into it, so a
run can be staged anywhere. The three profile scripts still do not, and
this session protected the window pair by copying it to
`~/dspboot/.window/` and restoring it. Extending `STAGE` to the profile
scripts is the durable fix.

### S10-8 — the margin was being quoted off an average, and only on chip 1

**Severity: MAJOR (every chip-1 margin on record). Status: RECORDED.**

`_proc_cyc` is the last block pass; `_proc_cyc_max` is the worst since
reset. On the shipping pair, block 16, two boots per arm:

| | mean | worst | worst/mean |
|---|--:|--:|--:|
| chip 1, D24 | 234,267 | 277,752 | **1.186** |
| chip 1, D32 | 306,190 | 361,246 | **1.180** |
| chip 2, D24 | 303,891 | 304,874 | 1.003 |
| chip 2, D32 | 369,424 | 370,832 | 1.004 |

**Chip 2's block cost is flat to 0.4 %; chip 1's worst block is 18 % above
its mean at both masks on every boot** — stable enough to be structural,
not jitter. Chip 1 carries the 38 METER nodes and the ramp engine, and the
meter fold is an explicit per-block gate (`_mtr_block_tick`).

So **chip 1's D24 margin is 15.2 %, not 28.5 %**, and every chip-1 margin
ever quoted on this project is 18 % of its own value too generous.

Two riders. **OVERRUN 0 does not mean every block fitted** — chip 1 at D32
exceeds budget on its worst block (110.3 %) and still reports zero
overruns, because `_block_ready` is a flag and a long block is absorbed by
the next block's slack. And **`_proc_cyc_max` is never reset**, so it
catches the one-time work in the first pass after CONFIG_COMMIT: one boot
read 1,351,877 (412.6 %) against 370,832 on its twin. It needs a reset
before it can be a production margin figure.

### S10-9 — a stale `chipN.sym.json` gives well-formed wrong cycle counts

**Severity: MAJOR (bench procedure). Status: FIXED in dsp4_capacity.py.**

The symbol map moves on every build. A bench tool that reads
`/home/app/dspboot/chipN.sym.json` while booting an image staged elsewhere
peeks `_proc_cyc`'s address **in a different build**, and whatever lives
there answers. On 2026-09-09 that returned values increasing by three per
read (it was `_proc_passes`) and, on one run, a number that matched the
expected `_proc_cyc` closely enough to be believed.

Two "fixes" tried on the way made it worse and are recorded so they are not
tried again: reading the peek DATA half with the paced voted reader `rd()`
returned DIAG_FRAME_COUNT's value (it fires twelve pipelined asks of its
own into a two-transaction handshake), and wrapping the handshake in a
24-try agreement loop returned `_proc_passes`. **The peek window tolerates
exactly one handshake at a time under load.**

`dsp4_capacity.py` now prefers the map staged beside the `.ldr` that was
booted. Every bench tool that peeks by symbol has the same exposure.

### S11-1 — S10-6 SETTLED: the capacity record's instrument was a DIFFERENT, FASTER BUILD, and it was not decimation

**Severity: MAJOR (the capacity record). Status: CLOSED.**

`sigprofile2.sh` / `fxcost.sh` read chip 2 78,245 cycles/block low at D24
and 108,331 low at D32 against the shipping image — 24 % and 33 % of budget
— in the direction the signal/silence split cannot produce.
`DSP4_BLOCK_DECIMATE=32` was the standing candidate. **It is not the cause:
decimation is worth 554 cycles on chip 1 and −920 on chip 2, both inside
the pass-to-pass spread** (`capacity.sh`, one variable, D24 mask).

The cause is **two build switches that `shipping.config` does not name and
`build.sh` defaults to 0, and that both profile scripts have always forced
to 1**: `DSP4_STRIP_FUSED` and `DSP4_SIMD_DYN`. With them on, chip 2 reads
222,314 at D24 against the instrument's 225,646, and 268,790 at D32 against
261,093 — 1.0 % and 2.3 % of budget apart, i.e. the whole disagreement plus
what `DSP4_PROFILE_SIGNAL` accounts for.

**This is S8-2's shape a third time: a number quoted for a build that is
not the one running.** `DSP4_PROFILE_SIGNAL` was declared; these two were
declared nowhere. Every `.4` / 09-03 / 09-08 chip-2 capacity row is
re-annotated in `MW/D32/DSP/dsp4-capacity-s11-20260909.md` §5 as an
instrument figure. The profile scripts are **retired for capacity claims
about the shipping image** and remain valid for attributing cost to a class
inside their own arm.

### S11-2 — `DIAG_BUILD_CFG` could not tell three images 81,299 cycles apart from each other (S10-5 came true)

**Severity: MAJOR. Status: CLOSED by a second word.**

S10-5 recorded that `DIAG_BUILD_CFG` has no spare bit — 31..24 signature,
23..8 all allocated — so "an instrument build can still be silent to the
part". On 2026-09-09 three arms were measured in one session: shipping,
shipping + `DSP4_BLOCK_DECIMATE=32`, and shipping + `DSP4_STRIP_FUSED=1` +
`DSP4_SIMD_DYN=1`, which differ by **81,299 cycles/block on chip 2**. **All
three read `DIAG_BUILD_CFG 0xCF45FF10.**

`DIAG_BUILD_CFG2` (0xE0EB) is added: signature `0xC2`, `DSP4_BLOCK_DECIMATE`
in 23..16, `DSP4_TX_EARLY`'s per-chip mask in 9..8, and the cost switches in
the low byte. Shipping reads **`0xC2010044`**, the fused/SIMD arm
**`0xC201004F`**. `dsp4_buildcfg.py` decodes it and `--expect-shipping`
scores it; `dsp4_diag.py`, `dsp4_checkchip.py` and `dsp4_capacity.py` print
it on every dump, boot and capacity row; `check_shipping_config.sh` computes
both words and **reads `build.sh`'s own defaults** for the switches
`shipping.config` does not name, so the mirror is not a third copy.

**Consequence, stated rather than buried: the tree no longer builds
`ac65ad38…` / `e5dce9e4…`.** It builds `a95fd8eb…` / `fb1eee67…`. The staged
window pair is untouched; adopting the successor is PW's call, and it needs
the design bars re-run on it.

### S11-3 — Lever 1 (BLOCK 32) is answered and it is NO: D32 gets worse, and the latency price is 4× the estimate

**Severity: n/a (a ruling input). Status: CLOSED.**

It links (`chip1.ldr` 444,704 B, `chip2.ldr` 313,268 B) and it boots.

| D32 all-ones | chip 1 | chip 2 |
|---|--:|--:|
| block 16 | 93.4 %, worst 110.3 %, OVERRUN 0 | 112.7 %, worst 113.2 %, **11.26 %** |
| block 32 | **86.22 %**, worst 94.63 %, OVERRUN 0 | **117.51 %**, worst 121.7 %, **14.86 %** |

Per sample, chip 2 goes from 23,089 to 24,067 cycles (**+4.2 %**) while
chip 1 goes from 19,137 to 17,658 (**−7.7 %**). **The 2026-09-01 trend that
predicted 5–10 % was a chip-1 and per-class trend and does not transfer to
chip 2's graph** — chip 2 carries the six FX engines, and doubling the block
doubles every kernel's working set.

The price is also four times what was assumed: measured through-DSP latency
is **66 samples at block 16 and 131 at block 32**, i.e. **+65 samples /
1.354 ms**, not +16 / 0.333 ms. The signal crosses four block-buffered
stages, not one.

D24 *improves* at block 32 (chip 1 worst 84.8 % → 72.7 %, chip 2 93.0 % →
89.0 %), so the lever is not worthless — it is not a D32 lever.

### S11-4 — the lever that DOES close D32 is `DSP4_SIMD_DYN`, and it is the half that is not proven

**Severity: MAJOR (it is the D32 decision). Status: OPEN — needs a session.**

| D32 all-ones | chip 1 worst | chip 2 `_proc_cyc` | chip 2 worst | OVERRUN |
|---|--:|--:|--:|--:|
| shipping | 361,246 110.3 % | 369,424 112.7 % | 370,832 113.2 % | 11.26 % |
| `DSP4_STRIP_FUSED=1` | 354,816 108.28 % | 365,882 111.66 % | 366,699 111.91 % | 10.32 % |
| + `DSP4_SIMD_DYN=1` | **307,247 93.76 %** | **268,790 82.03 %** | **284,249 86.75 %** | **0** |

**D32 FITS with both on — zero missed blocks on both chips over 270,082
blocks.** The target was 41,744 cycles on chip 2; this delivers 100,634.
But `DSP4_STRIP_FUSED` alone is worth only 3,542 cycles (1.08 %) and does
NOT close it: **97,092 cycles/block, 29.6 % of budget, is `DSP4_SIMD_DYN`
alone.**

`famverify.sh` with the block-aware witness, one variable per arm:

* **shipping**: 17/20 LIVE, contract 20/20 with 0 FAILED, COMPRESSOR /
  FADER_PAN / TUBE_SAT numeric **BIT_EXACT**
* **`DSP4_STRIP_FUSED=1`**: **verdict for verdict identical** to shipping —
  proven, and worth 1.1 %
* **`DSP4_SIMD_DYN=1`**: contract still 20/20, **0 FAILED**, but ANTI_FB /
  CROSSOVER / GEQ / LIMITER read **NO_CAPTURE**, GATE reads INERT, and the
  three numeric arms lose their stimulus
* **both**: **DOES NOT LINK** — chip 1 overflows `sec_swco` with the witness
  in the image

**This is NOT recorded as an audio defect.** It is the shape of S9-5: the
paired graph adds a pool slot and reorders the chain into pairs, so where a
node's block lives moves and the witness reads a symbol chosen before it
moved (S10-2). What makes it a session rather than a re-run is the link
wall: **the witness and the paired kernels do not currently fit on chip 1 at
the same time**, so the arm that would certify the lever cannot presently be
built. Getting round that (tap chip 2 only, tap a subset of the chain, or
shrink the paired path) is the first gate.

### S11-5 — the family bar was scoring the SHIPPING image eight families below the record

**Severity: MAJOR (a bar that does not bar). Status: CLOSED.**

S10 settled S9-5 with `DSP4_SCOPE_BLK_TAP=1` and recorded the shipping
configuration at **17 of 20 families LIVE** with three numeric arms
BIT_EXACT. `famverify.sh` never set the switch. Measured both ways this
session on the same tree, one variable:

| `DSP4_SCOPE_BLK_TAP` | audio LIVE | COMPRESSOR numeric |
|---|--:|---|
| 0 (what the script did) | **9/20** | **FAILED** |
| 1 | **17/20** | **BIT_EXACT** |

A bar that reads the image it certifies at 9/20 and calls a BIT_EXACT
family FAILED is not a bar. `famverify.sh` now defaults the tap ON, with
`DSP4_SCOPE_BLK_TAP=0` as the control that reproduces the old reading, and
records why the paired-kernel arm cannot have it.

### S11-6 — a latency arm without the pass-through setup reports a confident wrong offset

**Severity: medium (instrument). Status: CLOSED.**

The first through-DSP latency arm of the session returned offset **14,779
on all 20 reps, spread 0** — and a **coherent fraction of 0.0 %** with a
peak width of 400. Seventeen sources sum into `C2_MIX_MAIN_L` and the main
chain comes up at its landed values, so the Pi's stimulus never comes back;
`dsp4_dsp_latency.py` reports the best of a flat field. **An offset with a
zero coherent fraction is not a latency**, and the summary line prints the
offset first. `latency_run.sh` now runs `dsp4_passthru_setup.py` before the
probe and says why. Every arm quoted in S11 reads 100.0 % coherent.

### S11-7 — the transmit-stamp arm needs a bitstream AND an overlay the bench does not live on

**Severity: low (procedure). Status: RECORDED.**

The bench lives on the shipping CPLD `a1f6672af6c3` with the
`dsp4-pcm-slave` overlay. `dsp4_tx_order.py` needs **both** the `_maincap`
bitstream and the `dsp4-pcm-duplex` overlay: on the shipping bitstream
`arecord` returns "Input/output error" and zero frames, and on the slave
overlay the duplex device does not exist. The tool reports both as "NO
STAMP: the right channel is all zero", which reads as a firmware result and
is not one.

`SHARC/loadlogic.sh` is added — `maincap` / `pisel` / `shipping` / `--id`,
with the canonical pin hand-back after every load, because openocd's
linuxgpiod leaves its GPIOs claimed and that looks exactly like a bricked
card. The overlay is still a `config.txt` line and a reboot; it was flipped
and restored byte-identically this session (`config.txt.s11bak`), and the
bench ends on `dsp4-pcm-slave`, the shipping bitstream and matrix-app
active.

**The bench's own `restore_bench.sh` still carries the WRONG pin sequence**
(`pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0`, the S8-3 line that boots the
card as two chip 1s). It is not in this tree, so `check_bench_pins.sh`
cannot see it. Left as found and recorded.

## Session 13 — 2026-09-09

Write-up `MW/D32/DSP/dsp4-geq-floor-20260909.md`. Contract
`defs-v2026.09.08.4`, unchanged. `blk_*` and `cand_*` byte-identical at the
end of the session; the audio-correct paired pair staged BESIDE them as
`~/dspboot/geq_chip1.ldr` `df6b847d` / `geq_chip2.ldr` `cb9bc58e`.

### S13-1 — the paired chip-2 biquad graph dropped the write UPSTREAM of the latch, not at it

**Severity: high (audio). Status: CLOSED.**

`DSP4_C2_BQ_GRAPH=1` lost every GEQ, ANTI_FB and crossover parameter
change because the pair driver's steady test never read the pending-DESIGN
flag. The generator's own note asserted that "every write to the
coefficients goes through `_<pfx>_coeffs_next_` and
`_<pfx>_swap_pending_`", which holds only for the classes the host writes
COEFFICIENTS to. A GEQ takes 31 band gains, an AFB six notches, a
crossover a corner frequency: the host writes those and sets
`_<pfx>_dirty_`, and the design that turns them into coefficients — and
only then raises `swap_pending` — runs at the top of the NODE BODY, which
is the body the latch exists to skip. Latched, the design never ran, so
`swap_pending` never rose, so the latch never came down, and the pair ran
the `.var` bypass initialisers for ever.

18 of the 24 chip-2 pairs were affected (12 GEQ, 6 AFB); the 6 EQ/OEQ
pairs and the whole of chip 1's `DSP4_BQ_GRAPH` were always correct,
because chip 1 has no design-driven class at all. That is why the S12
candidate read clean and only the arm that fits D32 did not.

FIX: the steady test reads `_<pfx>_dirty_` for any class that has one,
guarded on that class's `DSP4_<CLS>_DESIGN` macro (a DESIGN=0 build has
nothing that clears dirty). Two DM reads and an OR per pair per block, in
`tools/dsp/dsp_codegen.py::gen_bq_pairs_c2`.

WITNESS: geqverify and afbverify design AND live-bank arms at 1–4 ulp with
the switch ON, against IDENTITY and 50.9 M / 83.9 M ulp before; famverify
GEQ and ANTI_FB both LIVE paired, moved 64/64; bqeverify PASS, 0 ulp over
36,864 words. famverify 17/20 LIVE, contract 20/20, three BIT_EXACT.

### S13-2 — D32 fits on an audio-correct image, with 17.5 % of chip 2 spare

**Severity: n/a (measurement). Status: CLOSED.**

`capacity.sh`, two boots per arm, ~135,040 blocks each, `cfg2 0xC201024F`
read back on the part. D32 all-ones on the audio-correct paired pair: chip
2 **82.06 / 82.49 %**, chip 1 76.73 / 76.96 %, **zero overruns**. D24 mask:
chip 1 59.2 %, chip 2 67.6–67.9 %, zero overruns. Against S12's candidate
at D32 chip 2 102.5–102.7 % with 2.37 % of blocks missed.

`_proc_cyc_max` IS NOT TRUSTWORTHY ACROSS BOOTS and its definition says
why: "the worst block pass seen since reset", and nothing resets it after
the boot and config ladder, so it latches a one-off configuration-block
transient. The same image read 71.29 % on one boot and 367.58 % on the
next with zero overruns on both. `DIAG_BLK_OVERRUN` is the arbiter.
Resetting the counter after config would make the column mean what its
name says; not done.

### S13-3 — S12-9 was the instrument: `mode 1` was an impulse TRAIN on every block-kernel image

**Severity: high (instrument). Status: CLOSED.**

afbverify's −18 dB notch measured −4.799 dB and geqverify's +12 dB band
+8.451 dB on EVERY block-kernel image, scalar and paired alike, where the
same bars read −17.99989 dB on the per-sample block-8 image of 2026-09-08.

`_scope_inject_blk` runs once per BLOCK and drove the amplitude into
sample 0 every time it ran, so `mode 1` was not an impulse but an impulse
TRAIN at one per block — 3 kHz at block 16 — and the audio arms measured
that train's periodic steady state. The raw capture shows exactly 64
non-zero words in 1024, at indices 0, 16, 32, … Modelling the train
through the same designed cascade reproduces all three of geqverify's
points to three decimals: +0.219 / +8.451 / −0.305 measured, +0.219 /
+8.451 / −0.305 modelled. **The audio was never in question.**

The per-sample injector has always had the gate (`_scope_go == 0` is the
first sample of the run). The block injector cannot borrow it: under block
kernels BOTH injectors run in every block and the per-sample one raises
`_scope_go` first, so gating on it silences the block injector completely
(measured — an all-zero capture). It gets `_scope_fired`, cleared by the
same arm write.

AFTER: geqverify **+11.997 dB** against a +12.000 model and afbverify
**−18.000** against −18.000 — GEQ_DESIGN_OK and AFB_DESIGN_OK on the
shipping configuration AND on the paired arm. famverify unchanged.

OPEN, recorded not fixed: geqverify's flat negative control prints
"64/64 samples equal to the input" when both captures are all zeros. It
did not mislead (the verdict also requires `peak > 0`), but the line is
not evidence on its own.

### S13-4 — S12-8: the crossover's LP/HP legs were registered with no witness

**Severity: medium (instrument). Status: CLOSED for the stall; the audio arm is declared NOT SCORABLE.**

`_buf_lp_<nid>` and `_buf_hp_<nid>` are ONE-WORD variables — under block
kernels the crossover runs its per-sample body BLOCK times through them
and there is no `_blk_lp_` array — and nothing registered them with the
block-aware witness, so xoververify armed on an address no tap answered
for and waited for a buffer that never filled. They now get
`_scope_tap1`, the one-word-per-block witness TALKBACK and NOISE_GEN use.

The bar reaches a verdict and its design arms pass: 1–4 ulp staged, live
== staged, LP and HP both −6.021 dB at the corner, response error
≤ 0.00013 dB, LP+HP flat to 0.00013 dB, across BOTH LR alignments and all
five corners, with the non-LR slopes correctly leaving the coefficients
unmoved.

Its AUDIO arm is declared NOT SCORABLE rather than scored wrong: a
one-word-per-block witness samples at 3000 Hz and a single impulse falls
in the fifteen samples of sixteen it does not keep, so the reference reads
zero. Scoring it needs a `_blk_lp_`/`_blk_hp_` array in the crossover's
block kernel — a change to the SHIPPING image for a bench instrument, not
taken.

### S13-5 — the GEQ primitive's floor is reachable by SCHEDULING ONE cascade, not by interleaving two

**Severity: n/a (design). Status: OPEN — analysed, not built, not measured.**

The float SIMD inner loop is 8 instructions per sample per stage for 2
channels, carrying 11 operations: 5 multiplies, 4 ALU, one load, one
store. `easm21k -proc ADSP-21564` accepts `mult + ALU + one memory move`
in ONE instruction (verified by assembling the four candidate forms, with
a two-move negative control correctly rejected), so the per-instruction
budget is 1 multiply + 1 ALU + 1 move and the floor for one cascade is
`max(5, 4, 2) = 5` instructions per sample per stage = **2.5
c/band-sample** in the inner loop, against 5.94 measured today.

**The dispatch's plan — two independent cascades interleaved, four
channels in flight — does not fit and is not needed.** One cascade needs 5
coefficients + 2 state + ~5 products + a temp live at once; two is upwards
of 22 registers against the 16 a PE has, and the alternate register file
is a MODE1 write with latency, not a per-instruction resource. The
recurrence does not bound a 5-instruction schedule either: the
loop-carried chain is y → a1·y → w1′ → y, three dependent operations
against five instructions of slack. A steady-state software pipeline over
ONE cascade, offset by one sample, covers it — the schedule is in
`MW/D32/DSP/dsp4-geq-floor-20260909.md` §5. What is left is the register
allocation and prologue/epilogue, then the shootout rig for bit-exactness
against `bq_float_ref` and the measurement. Nothing about the pair latch,
the gather or the chip-2 interleaved arrays has to move.

### S13-6 — RIG B not reached

**Severity: n/a. Status: OPEN.**

The 2156x IIR accelerator was not brought up. The precision test that
decides it is unchanged: band 1 (19.95 Hz, Q 4.3185) and band 2 at ±12 dB
in the accelerator's float32 against `bq_float_ref`, inside the 0.01 dB
bar or not.

## Session 12 — 2026-09-09

### S12-1 — the certifying witness now links beside the paired kernels, in a second code overflow region

**Severity: medium (instrument). Status: CLOSED.**

`DSP4_SCOPE_BLK_TAP=1` with `DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1` would not
link: chip 1's code fills Block 3 to within **2 bytes** and Block 2 to
within **0x134c**, and the witness costs **+2,976 words** in the generated
chain plus **+155** in `scope.asm`, leaving **0x63e words unmapped** — the
linker reports the same remainder once for `sec_swco` and once for
`sec_swco_ovf`, so the real shortfall is **799 words / 1,598 bytes**.

Read out of the link map rather than guessed: at the point of failure Block
1 had **0x193f8 bytes free** and nothing was allowed to reach it, because
the LDF gave code exactly two regions. `ADSP-21564.ldf` gains
`sec_swco_ovf2 > mem_block1_bw`, declared **after** `sec_dmda_ovf`,
`sec_dmda_c_bw_ovf` and `sec_dma`, so the DM overflow and the DMA
ping-pong buffers take what they need first and code gets only the
leftover. The chip-1 candidate places **0x31f words** there; chip 2 never
reaches it.

Inert when not needed, and checked rather than asserted: the default pair
rebuilt across the change is byte-identical — `a95fd8eb…` / `fb1eee67…`,
the same pair the tree built before it. The cost is stated where it lands:
instruction fetch from Block 1 runs against DDE traffic, which is a TIMING
price on an instrument build. **No capacity number in this session is taken
from a build that reaches `sec_swco_ovf2`.**

### S12-2 — the scope tap found pair drivers with a regex, and chip 2's pairs are not called what chip 1's are

**Severity: HIGH (instrument). Status: CLOSED.**

The tap pass matched
`_(DYNGATE|DYNCOMP|BQPFILT|BQPEQ)_nn_mm_process` — chip 1's four driver
names. Chip 2's drivers are `_C2PAIR_AUX_LIM_01_02_process`,
`_C2BQP_MOUT_OEQ_01_02_process`, `_C2PAIR_MSUB_LIM_process` and their
kind, so **the pass matched none of them** and every chip-2 node run by a
pair went untapped: in the `DSP4_C2_BQ_PAIRED_GRAPH` chain the tap count
was **124** against the scalar chain's **200**.

Measured on the part: the paired candidate read **ANTI_FB, CROSSOVER, GEQ
and LIMITER as NO_CAPTURE** — the scope was armed on a node with no tap in
that chain, so the capture never completed and the read timed out — while
every *unpaired* chip-2 family (FX_ENGINE, MONITOR) on the same image read
LIVE. That is S9-5's shape a third time: an instrument silent about
exactly the thing it was built to watch.

The fix is not a better regex. `pair_members` is now filled in by the four
call emitters themselves, so a driver that is called is a driver the
witness knows the members of, whatever it is named, and adding a fifth
kind of pair cannot silently drop off. With it, the same image reads 204
taps in the paired chain and the four families capture.

### S12-3 — a pair driver does not always publish where its class's scalar kernel does

**Severity: HIGH (instrument). Status: CLOSED.**

`_STRIP_BLK_OUT` is a fact about the SCALAR body, and the tap was using it
for paired call sites too. The chip-1 pair drivers are squared up to one
convention — channel A out in `BLK_CHAIN_B_P1`, channel B out in
`BLK_CHAIN_B`. For COMP, FILT and EQ that is the same slot the scalar
kernel uses, so the difference was invisible. **GATE is the exception:**
its scalar kernel publishes into `BLK_CHAIN_A` (`A_P1` on the odd strip)
and `_DYNGATE_nn_mm_process` publishes into `B_P1`/`B`.

On the part the GATE family therefore read **INERT on the paired
candidate — moved 0 of 64, peak exactly the injected `0x08000000` both
sides of the step**, because the tap was copying the block the gate had
READ, while COMPRESSOR, HPF_LPF and EQ_BIQUAD read LIVE on the same image.
A `_PAIR_BLK_OUT` table now answers for paired call sites, and the tap
raises rather than guesses if a paired node is witnessed at something that
is not a pool slot. GATE reads **LIVE** with it.

### S12-4 — the numeric arm injected into the pool the odd strip does not read

**Severity: HIGH (instrument). Status: CLOSED.**

`dsp4_node_verify.inject_addr()` returns `_blk_pool` for any block build.
A paired build gives the ODD strip of each pair a whole second pool
(`_blk_pool1`, blk_pool.h) because both strips of a pair must hold live
chain blocks at once — and the bar drives **strip 1**, which is odd. So
every stimulus the numeric arm injected on the paired candidate went into
a slot that strip never reads: `_buf_C1_IN_01` through `_buf_C1_FDR_01`
all captured **peak 0x00000001**, and COMPRESSOR, FADER_PAN and TUBE_SAT
reported **NO_STIMULUS** on an image whose audio arm read every one of
them LIVE. S9-5's second half, restated for the paired graph.

`inject_addr` resolves `_blk_pool1` for an odd strip when the symbol
exists; it only exists in a paired build, so an unpaired image resolves
exactly as it always did. With it the three families read **BIT_EXACT**.

### S12-5 — SIMD_DYN is audio-correct; `DSP4_C2_BQ_GRAPH` is not

**Severity: HIGH (audio). Status: OPEN — the chip-2 aux biquad pair.**

With the three instrument defects above fixed, `DSP4_STRIP_FUSED=1
DSP4_SIMD_DYN=1 DSP4_C2_BQ_GRAPH=0` reads **verdict-for-verdict identical
to the shipping configuration**: 17 of 20 families LIVE, contract 20/20
with 0 FAILED, COMPRESSOR / FADER_PAN / TUBE_SAT **BIT_EXACT**, GATE's
numeric arm NO_STIMULUS exactly as the shipping arm reports it. The
paired dynamics, the pair-ordered chain, the odd pool, chip 1's paired
biquads and chip 2's paired *dynamics* are all clean.

**`DSP4_C2_BQ_PAIRED_GRAPH` — chip 2's paired AUX biquads — is not.** With
it on, on the same image, in the same session, on the same bench:

| family | witness | C2 biquads PAIRED | C2 biquads SCALAR |
|---|---|---|---|
| GEQ | `_buf_C2_AUX_GEQ_01` | peak `0x08000000` -> `0x08000000`, **moved 0/64** — INERT | peak `0x08000000` -> `0x082DE520`, moved 64/64 — LIVE |
| ANTI_FB | `_buf_C2_AUX_AFB_01` | peak `0x08000000` -> `0x08000000`, **moved 0/64** — INERT | peak `0x08000000` -> `0x07FB92D0`, moved 64/64 — LIVE |
| CROSSOVER | `_buf_C2_MAIN_OEQ_01` | peak `0x07E960D0` -> `0x074AF178`, moved 64/64 — LIVE | LIVE, identical numbers |

It is not the witness: the address is the node's own `_blk_<nid>` array in
both arms, the unpaired arm proves that address is right, and
`_C2BQP_MOUT_OEQ_01_02` moves its block on the same image.

**THE MECHANISM IS NAMED, by two independent bars that read the
COEFFICIENT BANK rather than the audio.** On candA, `geqverify` and
`afbverify` both report the node's own live bank still at IDENTITY after
the host has written the parameters:

| bar | live bank | worst coefficient error | modelled response error | live tone |
|---|---|---|---|---|
| `geqverify` | `_geq_coeffs_A_C2_AUX_GEQ_01` | 50,965,640 ulp (word 89) | **-12.00000 dB** — the whole designed band gain | +0.000 dB at every point |
| `afbverify` | `_afb_coeffs_A_C2_AUX_AFB_01` | 83,887,018 ulp (word 1) | **+18.00000 dB** — the whole designed notch | +0.000 dB at every point |

The same two bars on the same image with `DSP4_C2_BQ_GRAPH=0` read those
banks correct to **1-3 ulp**. So on a paired chip-2 build **a GEQ band gain
and an AFB notch gain never become coefficients at all**; the node is
called, it runs, and it has nothing to apply. That rules out the
alternative this finding first left open — that the node is simply not in
the paired chain — and it locates the fault in the parameter-to-coefficient
path under `DSP4_C2_BQ_PAIRED_GRAPH`, not in the pair kernel's arithmetic.
Which side of the latch drops the write (the node's own design step never
running, or running into the interleaved copy) is the one thing still to
settle, and it is now a one-arm question.

### S12-6 — two chip-2 nodes are not called at all in the dynamics-only paired chain

**Severity: medium (audio, control arm). Status: OPEN.**

`_C2_CODEC_AUX_OUT_process` and `_C2_MAIN_ST_OUT_process` are called in the
scalar chip-2 chain and in the `DSP4_C2_BQ_PAIRED_GRAPH` chain, and **not
at all** in the `DSP4_PAIRED_GRAPH`-only chain (`c2grun`) — 198 tapped
nodes there against 200 in the other two. That arm is the one the
240,681-cycle chip-2 figure was measured on, so the figure is missing two
nodes of work as well as being an arm nothing ships. Found by counting
taps per chain variant, not by a bench run; not chased this session.

### S12-7 — `DIAG_BUILD_CFG2` does not carry the graph switches, and two images that differ in AUDIO read the same word

**Severity: medium (record). Status: OPEN.**

`DIAG_BUILD_CFG2` carries the decimation factor, `DSP4_STRIP_FUSED`,
`DSP4_SIMD_DYN`, `DSP4_SIMD_GRAPH`, `DSP4_SIMD_STRIPS`,
`DSP4_SCOPE_BLK_TAP`, `DSP4_TX_EARLY`, `DSP4_GATHER_FIRST` and
`DSP4_FX_TYPE_DECLARED`. It does **not** carry `DSP4_BQ_GRAPH` or
`DSP4_C2_BQ_GRAPH`.

So the two candidate images of this session — one of which loses parameter
changes on chip 2's aux biquads (S12-5) and one of which does not — both
read back **`0xC201004F`**, and a bench holding one of them cannot tell
which it has. That is S8-2's shape in the word that was added to end
S8-2's shape. Bits 5 and 10 of the second word are free.

Not fixed here: adding them changes the value a shipping image reads back
and therefore the default pair's bytes for the third time this week, and
the two switches are named in `shipping.config` in the meantime.

### S12-8 — four of the six design bars were reading a block-kernel image through the pre-block witness

**Severity: HIGH (instrument). Status: CLOSED for the bars run here, OPEN as a default.**

`fxverify.sh`, `afbverify.sh`, `geqverify.sh` and `xoververify.sh` arm the
scope on `_buf_<node>` and none of them sets `DSP4_SCOPE_BLK_TAP`. S11-5
found and fixed exactly this in `famverify.sh` and the fix was not carried
to the others.

Measured this session, same configuration, one variable: on the staged
shipping pair `ac65ad38…`/`e5dce9e4…` — no tap — `fxverify` reports

    input at _buf_C2_RECV_FX_01: peak 0.000000 at sample -1
    INPUT SILENT — no verdict is possible from this run

and exits 1. On the same configuration rebuilt with the tap
(`25f0a532…`/`9d713603…`) the same bar runs to **FX_VERIFY_OK**, every
sub-check PASS. The bar was not failing; it was reading a one-word `.var`
the chip-2 block kernels never write, and reporting that as silence.

All six bars in this session were run on tap-enabled images, and the four
scripts now **default the tap ON**, the way `famverify.sh` has since S11-5:
`export DSP4_SCOPE_BLK_TAP="${DSP4_SCOPE_BLK_TAP:-1}"`, with
`DSP4_SCOPE_BLK_TAP=0` left as the control that reproduces the old reading.
Leaving a default that is known to produce a confident wrong answer is the
thing this session spent most of its time undoing.

It does NOT rescue `xoververify`, which stalls for a different reason — it
arms on `_buf_lp_<nid>`, an address the tap does not cover at all (S12-2's
class, in a bar). That one is still open.

### S12-9 — `afbverify`'s live tone arm fails on the pair that ships, and it passed on 2026-09-08

**Severity: HIGH if it is the audio, medium if it is the capture. Status: OPEN, not attributed.**

Run on the staged shipping pair (`blk_*`, rebuilt with the tap), the
anti-feedback bar's DESIGN arms all pass — five parameter sets, worst
4 ulp on the coefficients, worst response error 0.00009 dB against a
0.050 dB bar. Its LIVE tone arm does not:

| point | 2026-09-08 | this session, `blk_*` | model |
|---|---|---|---|
| 250 Hz, two below | −0.0374 dB | −0.1927 dB | −0.0374 |
| **1 kHz, notch centre** | **−17.99989 dB** | **−4.7987 dB** | **−18.000** |
| 4 kHz, two above | −0.0358 dB | +0.2386 dB | −0.0358 |

`AFB_DESIGN_OK` then, `AFB_DESIGN_FAIL` now, same bar, same node, same
contract pin. The 09-08 image is a PER-SAMPLE, block-8, 491.52 MHz build;
`blk_*` is the block-kernel, block-16, 983.04 MHz pair. Nothing between
them was an AFB change.

Two readings fit and this session did not separate them:

* **The audio.** The notch is genuinely reaching about a quarter of its
  designed depth in the pair that ships.
* **The capture.** The 1024-sample window is assembled from 64 consecutive
  `_scope_tap` block copies. If those copies are not consecutive IN TIME,
  the tone's phase jumps between blocks, which spreads energy and raises
  the measured level at the notch — and would also account for the
  0.15–0.27 dB error at the two passband points, which no filter change
  explains.

The passband drift is the tell and it points at the capture, but "points
at" is not a measurement. **Separating them is one arm**: the same bar on
the same image with a stimulus that is coherent block-to-block, or a
capture that verifies its own block continuity. It is not
candidate-specific — it is the shipping pair.

### S12-10 — the latency tool's margin guard has a hole, and it swallowed a whole arm

**Severity: HIGH (instrument). Status: CLOSED.**

`dsp4_dsp_latency.py` warns when the winning offset's margin over the
runner-up is under 2x. When the runner-up is **0.0** the margin computes as
**infinite**, so `worst < 2.0` is false and a run in which NOTHING
correlated with the stimulus prints a clean-looking summary. S11-6 fixed
the CAUSE of that signature — the missing `dsp4_passthru_setup.py` — and
left the reporting hole open.

It returned on 2026-09-09. Both candidate arms, with and without
`DSP4_TX_EARLY=2`, read **offset 14779 on all 20 reps of both boots,
spread 0, coherent fraction 0.0 %** — S11-6's signature exactly, with the
pass-through setup demonstrably running (`chip2: 12 cells written, all
present in the contract`, main-bus sources at `0x0`).

**The control is what settles it: the same arm on the staged shipping pair
`blk_*` reads the identical 14779 / 0.0 %.** The instrument is at fault and
the candidate is uninvolved — so no latency figure was taken this session
and S11's 66 samples / 1.375 ms at block 16 is not overwritten with a null.

Cause, from the bench state: the through-DSP arm needs the `_maincap`
bitstream AND a duplex PCM overlay. The bench lives on `dsp4-pcm-slave`,
where the capture device exists and returns audio that is not the DSP's
output — a well-formed capture with nothing in it. S11 measured
successfully because it flipped to the duplex overlay and restored
afterwards (`config.txt.s11bak`); that flip is a `config.txt` line and a
REBOOT and was not taken here.

`dsp4_dsp_latency.py` now refuses the verdict when the coherent fraction is
0.0 % on every rep, exits 2, and names the capture-path requirement in the
message.
