provenance: AI-drafted 2026-09-09 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The ORDER DEFECT: a ping/pong half out of phase, and the loop that cannot keep up

Bench: rev C unit MW-D24-2, `app@192.168.1.219`. Rev A not touched.
Contract `defs-v2026.09.08.4`, unchanged. Every image named here was
built from this tree tonight and run from a staging path of its own
(`~/s33` … `~/s40`); `~/dspboot` was read, never overwritten, and its
window pair is byte-identical to as-found at the end.

## 1. What was open

Session 33 measured, but could not explain, this: any stimulus whose
period divides 8 comes back through the DSP loop EXACT, and anything
longer is scrambled — every sample at the right position inside its
8-sample block, from the wrong block, about a third of blocks in place
and the rest from roughly the last 225. The CM4 path, the CPLD capture
and the chip-2 node graph were each excluded by measurement (S7-5), which
left the chip-2 transmit path and three candidates inside it: the DMA
ring indexing, the block hand-off, and the TX slot tables.

## 2. The instrument

Guessing between those three is not necessary, because chip 2 has a spare
slot on the wire. TX lane 3 is a full-window lane (`mcpde = 0`, cs_mask
`0x0003`): the DDE moves all eight window words per frame and the SPORT
drives slots 0 AND 1. Slot 0 is `C2_MAIN_ST_OUT` — the audio. Slot 1 is
driven and written by no node, so it leaves the part as zero.

`SHARC/src/tx_probe.asm` (`DSP4_TXPROBE=1`, chip 2 only, assembles to
nothing otherwise) writes into slot 1 of the same frame, immediately
after `_gather_chip2` has written slot 0 for that sample:

    bits 31..8   block counter, incremented once per block
    bit  4       0 = the active TX half is ping, 1 = pong
    bits 2..0    sample index inside the block

The `_maincap` LOGIC build presents slot 0 as the Pi capture's LEFT
channel and slot 1 as its RIGHT, latched together from ONE DSP frame
since S7-1, so a recorded stereo frame is a coherent (audio, stamp)
pair. The stamp is in order by construction. What comes back off the wire
therefore answers the question with no appeal to the audio at all:
monotonic stamps mean the buffer-to-wire path is in order and the
scramble is upstream; scrambled stamps mean the transmit path, and the
displacement is then read directly in blocks.

`tools/pi/dsp4_tx_order.py` plays the 1,500-step staircase, records both
channels, and decodes them.

## 3. The answer: the phase, off by one half

With the node graph out of the way (`DSP4_BLOCK_MASK=5`) so that ZERO
blocks were missed, the stamp still came back scrambled — and scrambled
in a perfectly periodic way. 192,000 frames, and the delta between
consecutive stamps took exactly three values:

| delta | count | meaning |
|---|---|---|
| `+1` | 143,999 | in order |
| `-15` | 24,000 | back two blocks |
| `+17` | 24,000 | forward two blocks |

24,000 is the number of 8-sample windows in the capture, so there is
exactly one of each jump per window, at a fixed sample. The sample-index
field is 24,000 of each of 0–7. The position inside the window was never
wrong; the block was.

That is not an indexing bug and not a slot-table bug. `_set_tx_bufs`
started the core on the PING half and `_sport_dma_work` toggled it at
each block interrupt — but the DDE also starts each region on its ping
row and moves to pong at the first row boundary, which is the same edge
that raises that interrupt. The core was writing the half the channel was
clocking onto the wire. Slots the DDE had not reached yet went out
carrying the block just gathered; slots it had already passed went out
carrying what that half held two blocks earlier.

Two changes, both in `src/sport_init.asm`, both under `DSP4_BLK_LATCH`
(default 1; `0` rebuilds `093c609f` / `2ba0e464` byte for byte):

1. **The pointer stops moving under the loop's feet.** The generated
   `_scatter_chipN` / `_gather_chipN` reload the active-buffer pointer
   from DM on every sample, and the ISR used to retarget that same word
   mid-block. The ISR now advances a pending pair and `_blk_latch_bufs`
   moves them into the active pair once per block. On the part this alone
   changed nothing — the same three-value histogram — so it is a hazard
   closed, not the defect.
2. **The core starts on PONG.** It then fills the row the DDE has just
   finished with, and that row goes out on the next block.

Result, same build, same bench, same capture length:

    STAMP ORDER: +1 on 191,999 of 191,999 transitions (100.0000 %)
    stamp delta histogram: [(1, 191999)]

One entry. The transmit path is exact.

## 4. What that means for the converter lanes

The lane the instrument measured is not a measurement lane: `o_dspb[3]`
is the CPLD's `dac_main`, and slot 0 of it is `C2_MAIN_ST_OUT` — a
product output. `_gather_chip2` writes all twenty chip-2 outputs from the
same half in the same loop through the one pointer, so AUX_OUT 01–12,
MAIN_OUT 01–04, MON_OUT, CODEC_AUX_OUT and SUB_OUT carried the identical
splice and are fixed by the identical pointer. They cannot be witnessed
directly on this bench: LOGIC captures only `o_dspb[3]` and no analogue
loopback is wired. What would settle them is a `_maincap`-style build
capturing a slot of `o_dspb[0..2]`. Chip 1's inter-chip TX and both
chips' RX regions carry the same off-by-one-half and take the same fix.

## 5. The defect underneath: the loop does not fit the block

With the phase fixed, the staircase through the full D24 graph is still
only 33 % exact — because the core is not writing most blocks at all.

| | chip 1 | chip 2 |
|---|---|---|
| blocks missed, 8 s | **75.1 %** | **70.9 %** |
| `_proc_cyc`, shipping per-sample BLOCK=8 | 330,389 | 286,757 |
| `_proc_cyc`, `DSP4_BLOCK_KERNELS=1` | 134,325 | 170,622 |
| `_proc_cyc`, plumbing only | — | 13,964 |
| budget, BLOCK=8 at 982.98 MHz | 163,830 | 163,830 |

`DIAG_BLK_OVERRUN` against `FRAME_COUNT` says chip 2 misses 71.4 % of
blocks; the block counter on the wire advances at 28.7 % of the frame
rate. Two independent instruments, agreeing to a tenth of a percent. A
half that is not rewritten is transmitted again, so the wire carries
stale whole blocks — the ±225-block tail of S7-5.

Every capacity number on record was taken in a configuration that does
not ship: the `.4` record (chip 1 202,786 / chip 2 226,442 against
327,680) is a BLOCK=16 `DSP4_BLOCK_KERNELS=1` build, and the shipping
default is BLOCK=8 per-sample. Block kernels alone do not close it —
chip 2 reads 170,622 against 163,830 and misses 51.9 %, because a pass
that takes 1.04 block periods misses every second block, not four
percent of them: `_block_ready` is a flag, not a queue.

The causal chain closes when the load is reduced until the loop nearly
fits. Block kernels + the phase fix + the runtime masks poked down to one
strip and one aux: chip 1 misses 0.0 %, chip 2 misses 30.3 %, and the
staircase through the whole chip-2 graph goes from **32.87 % to 91.92 %
exact** over 96,000 frames. The residual is the residual overrun.

CCLK is not the reason (982.98 MHz measured against the 983.04 target,
block rate 5,999.9/s against 6,000). This needs its own dispatch: which
block size the product runs at, and whether block kernels ship, are
architecture decisions.

## 6. A bench-procedure defect found on the way

`sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0` — the line every run
script executes after an OpenOCD flash — puts GPIO24 into ALT0, which on
this part is `SD0_DAT2`, not a deasserted chip select. Chip 2's CS then
sits asserted while chip 1's boot stream is clocked out, chip 2 loads
`chip1.ldr`, and the card comes up as two chip 1s. Six consecutive boots
did this. Holding GPIO 6 and 24 as outputs driven HIGH and giving only
7, 9, 10, 11, 22, 23, 25 to `a0` booted chip 2 correctly first time,
every time after. `dsp4_scope.check_chip` is the only thing that catches
it; through `dsp4_diag.py` alone the card looks healthy with a wrong
CHIP_ID.

## 7. Bars and state at the end

* `famverify` on the fixed pair, pin `defs-v2026.09.08.4`, both chips
  healthy: 3,737 cells, 17 of 20 families LIVE (AUX_INPUT
  NO_STIMULUS_PATH, DCA and METER NO_PROBE), GEQ 31/31, CROSSOVER 8/8,
  0 FAILED — the `.4` line, not moved down.
* golden harness 59/59; `dsp_validate` OK; `test_geq_splice` 5/5;
  `test_dsp_validate` 13/13; `check-contract-drift.sh` clean.
* Through-DSP latency re-measured, 10 reps x 2 boots: min 14,508 /
  14,509, spread 13 and 15, worst margin x16.8 — against 14,504 pre-fix,
  i.e. inside the instrument's own spread. 72 samples / 1.500 ms stands.
* New pair staged BESIDE the window pair: `~/dspboot/tx_chip1.ldr`
  `21f9fdc1ebd3afe4709869f5884da1f5`, `tx_chip2.ldr`
  `de14981fe9165e3047e45dd60a00bb6b`. The window pair `093c609f` /
  `2ba0e464`, `conf_*` and `ship_*` are byte-identical to as-found.
* Bench restored: shipping bitstream `a1f6672af6c3` (IDCODE
  `0x020a30dd`, ID knock silent, which is its positive identification),
  `dtoverlay=dsp4-pcm-slave` byte-identical to as-found, PCM_CLK and
  PCM_FS toggling, matrix-app active, both DSPs booted from `~/dspboot`.
