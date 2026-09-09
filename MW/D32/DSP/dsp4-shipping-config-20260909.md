provenance: AI-drafted 2026-09-09 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# One shipping configuration — the block loop must fit the block

The build that ships was not the build that was measured, in **three
independent parameters at once**, and nothing on the bench could see it
because every instrument was reading the same wrong build. This is the
session that ends that: one configuration, named in one file, built,
measured and staged as one artifact — and the image now says what it is.

## 1. What was wrong, in three parts

| | what every measurement assumed | what the shipping image actually was |
|---|---|---|
| block size | **16** (PW ruling 2026-09-03) | **8** — the committed tree has never been generated at anything else |
| kernels | **`DSP4_BLOCK_KERNELS=1`** | **0**, one call per node per sample |
| core clock | **983.040 MHz** (U5/U6 read as `ADSP-21564KSWZ10`, 2026-08-24) | **491.52 MHz**, the CGU reset divisors |

None of these was a regression. The block-16 ruling was applied only
inside the measurement scripts, which generate a scratch tree with
`DSP4_GEN_BLOCK` set and build it with `DSP_SRC_DIR`; `dsp_codegen.py`
carried `BLOCK = 8` as a literal from 2026-08-28 until today, so the
repo tree — and therefore `./build.sh` — was never anything but block 8.
Block kernels and the core clock are the same story in the build flags:
defaults that the measurement scripts override and the shipping build
does not.

**The core clock is the one that had never been noticed at all.** It was
read off the running window pair before anything was changed:

    chip 1: 0x3108D000 = 0x00002800      CGU0_CTL
    chip 2: 0x3108D000 = 0x00002800
    chip 1: 0x3108D00C = 0x05144281      CGU0_DIV
    chip 2: 0x3108D00C = 0x05144281

`0x00002800` / `0x05144281` is exactly the "today" row of the table in
`src/cgu_init.asm` — MSEL 40, CCLK 491.520 MHz. The 983.040 row is
`0x00005000`. So the block-8 shipping image was over a **81,920**-cycle
budget, not the 163,830 findings S8-2 scored it against: **4.03x on
chip 1 and 3.50x on chip 2**, not 2.02x and 1.75x.

## 2. The fix: one file, and an image that says what it is

`MW/D32/DSP/SHARC/shipping.config` is the only place the shipping build
parameters are named. `build.sh` sources it; `tools/dsp/dsp_codegen.py`
reads `DSP4_GEN_BLOCK` from it through `tools/dsp/build_config.py`; the
repo tree is regenerated at block 16, so `./build.sh` with no overrides
**is** the shipping configuration. An environment variable still
overrides any line — that is how the control arms in this document were
built — but the override is then explicit and lands in the image.

`build.sh` refuses outright to compile a source tree whose generated
`dsp_block.h` disagrees with `DSP4_GEN_BLOCK`. That is the specific
mistake that produced this whole class of defect and it is now an error,
not a possibility.

**`DIAG_BUILD_CFG` (0xE0EA)** is a compile-time word carrying the block
size, the block-kernel and phase-fix switches, the channel mask, the
scope gate, both float switches, the block mask, the core-clock target,
and the three switches that must never be set in a shipping image
(`DSP4_BISECT`, `DSP4_TXPROBE`, `DSP4_PROFILE_SIGNAL`), under a `0xCF`
signature so a dropped read cannot be mistaken for a configuration. One
transaction, not the two-transaction peek window, and readable at
BOOT_STAGE 1 before the graph or the audio clocks exist.
`tools/pi/dsp4_buildcfg.py` decodes it; `--expect-shipping` fails on a
part that is not carrying the shipping build; `dsp4_diag.py` prints the
decode in every dump and `dsp4_checkchip.py` after every boot.

**It earned itself on the first read.** The part said `DSP4_BQ_GUARD` was
0 where `shipping.config` said 1. The part was right — `dsp_block.h`
forces the guard off in a float build, because the float cascades are
guard-free — and the config file was describing an image that cannot
exist. `check_shipping_config.sh` now fails if the file and its bench-side
mirror disagree, and prints the word a shipping image must read back:
**`0xCF45FF10`**.

## 3. The block loop fits the block

Both chips configured for **d24**, D24 mask (`0x00FFFFFF` / `0x000000FF`),
budget **327,680** cycles/block (983.040 MHz x 16 / 48,000):

| | chip 1 | chip 2 |
|---|---|---|
| `_proc_cyc` | **234,594** | **303,894** |
| % of budget | **71.6 %** | **92.7 %** |
| `DIAG_BLK_OVERRUN` over 600 s | **0** | **0** |
| FRAME_COUNT over 600 s | +1,800,007 (3,000.0/s) | +1,800,007 (3,000.0/s) |

**Zero missed blocks on both chips over ten minutes.** Against the block-8
shipping image's 75.1 % and 70.9 % missed, that is the whole point of the
session.

Chip 2 at 92.7 % is a fit with 7.3 % of margin and it is the tighter part
by a wide margin. **The D32 all-ones mask does NOT fit**: with all 32
strips and 12 aux buses, chip 2 missed **11.3 %** of blocks in a loaded
run. D32 at block 16 is not a shipping configuration on this firmware.

## 4. What is still wrong on the wire, and it is not the block loop (S9-2)

Zero blocks are missed and the transmit path is still not exact.

The block loop meets the BLOCK deadline. The **first frame of each DMA
half has an earlier deadline than the block does**: the whole gather runs
at the END of the block period, after the node graph has spent 92.7 % of
it, and the DDE clocks frame 0 of the half out first. Those frames lose
the race and go out carrying what that half held TWO BLOCKS earlier.

Measured on the wire with the transmit stamp (`DSP4_TXPROBE=1`, the
frame-locked `_maincap` bitstream `d903ae1ac4a9`, 192,000 frames):

| arm (same bench, block 16, D24) | stamp order | late frames per block |
|---|---|---|
| node graph out of the way (`DSP4_BLOCK_MASK=5`) | **100.0000 %** | 0 |
| load cut to one strip and one aux | **100.0000 %** | 0 |
| full D24 graph | 87.4999 % | 1 (`-31` / `+33`, 12,000 each) |
| full D24 graph, gather reordered | **100.0000 %** | 0 |
| full D24 graph + the Pi playback input | 81.2499 % | 2 (`-7`, `-15`, `+17`) |

**The count of late frames tracks the LOAD, not the block.** That is what
makes it a race rather than an indexing error, and the two 100 % rows are
what makes the 2026-09-09 ping/pong phase fix (`DSP4_BLK_LATCH`) still
correct: with the load out of the way the same image is exact at block 16
exactly as it was at block 8.

`DSP4_GATHER_FIRST=1` moves the gather to the head of the loop body, in
front of `_scope_record` and the parameter-link poll, neither of which the
gather depends on. It is worth about one frame of margin — 87.4999 % ->
100.0000 % without the Pi input — and at the heavier load both orders
measure 81.2499 %, repeatably. **It is margin, not a fix**, and it is kept
on those terms.

**The next lever, named.** The gather needs a whole block period of slack
between the write and the read. Either write block N-1's outputs at the
top of period N, or give the TX region a third buffer. Both cost one more
block of output latency — 16 samples, **0.333 ms** — and both are
architecture decisions that need PW. Reducing chip 2's 92.7 % is the other
half of the same lever and is the existing capacity work.

## 5. The staircase, and why it could not be read as 100 %

The staircase through the whole chip-2 graph is **not** 100 % exact. Two
things had to be fixed before it could be read at all, and both are worth
recording because they cost this session an hour each.

**The Pi playback input is off by default.** `C2_PI_IN` is an `AUX_INPUT`
with `on=0` and `level_db=-6.0` in `dsp.csv`. The stimulus crosses the
fabric intact — `_blk_C2_XR_PI_L` reads `0x04000000` for a `0x20000000`
stimulus, the documented 8x round-trip attenuation — and the node
publishes zero, so nothing downstream can see it. Writing `0x0744 = 1`
and `0x0743 = 1.0f` turns it on.

**The loop is not bit-transparent.** The rest of the chip-2 graph sums a
constant into MAIN, so an exact-value test scores 0 % on a capture that is
perfectly ordered. Scored against the step index with that DC removed, on
the same capture that carries the stamp:

    STAMP : +1 on 155,999 of 191,999 (81.2499 %)
    AUDIO : exact 79,052 / 96,000 = 82.3458 %

**The audio and the stamp agree**, twice, to a tenth of a percent — which
is the result that matters: the disorder the staircase sees IS the
transmit-path disorder, measured two ways on one capture, and not
something else in the graph.

## 6. Bars

Host-side, on the block-16 tree:

| bar | verdict |
|---|---|
| `golden_harness.py` | **59/59** |
| `dsp_validate.py` | **OK**, 666 nodes, the four known chip-2 process-order notes |
| `test_geq_splice.py` | **5/5** |
| `test_dsp_validate.py` | **13/13** |
| `check-contract-drift.sh` | **clean** at `defs-v2026.09.08.4` (D24 generation `3d41d5850df3`, 4,985 rows; D32 `0d8f3f642a19`, 6,999 rows; 361 families) |

### famverify: the contract arm holds, the AUDIO arm moves down, and BLOCK KERNELS are the reason

Three arms, one variable changed at a time, all on this bench today, same
contract, same instrument, same `landed-d24.json` (3,737 cells, sha256
`4aa3c343cedf`, pin `defs-v2026.09.08.4`):

| arm | BLOCK | kernels | CCLK | contract | audio LIVE |
|---|---|---|---|---|---|
| the `.4` configuration, rebuilt | 8 | 0 | 491.52 | every rw cell answers | **17 of 20** |
| **the discriminator** | 8 | **1** | 491.52 | every rw cell answers | **8 of 20** |
| **shipping** | **16** | 1 | **983.04** | every rw cell answers | **8 of 20** |

**The block-8 per-sample control reproduces the `.4` line exactly** — 17
of 20 LIVE, AUX_INPUT `NO_STIMULUS_PATH`, DCA and METER `NO_PROBE`,
COMPRESSOR / FADER_PAN / GATE / TUBE_SAT numeric BIT_EXACT — so the move
is not the bench and not the day. **And block 8 WITH block kernels gives
the same 8 of 20 as block 16, family for family and verdict for verdict**,
so it is not the block size and not the core clock either. It is
`DSP4_BLOCK_KERNELS`, and nothing else.

The eight families that change are all chip-1 strip-chain nodes witnessed
at `_buf_C1_*`: COMPRESSOR, DELAY, EQ_BIQUAD, FADER_PAN, GATE and HPF_LPF
go INERT, ROUTING and TUBE_SAT go SILENT, and COMPRESSOR's numeric arm
goes BIT_EXACT -> FAILED. Every chip-2 family witnessed with an impulse
(GEQ, CROSSOVER, ANTI_FB, FX_ENGINE, LIMITER, MONITOR) is unaffected, and
so is every family's contract arm: GEQ 31/31, CROSSOVER 8/8, ROUTING
42/42, COMPRESSOR 17/17, 0 failed in all three arms.

**Whether that is an audio defect or a witness that does not hold in the
block-kernel arm is NOT settled, and this document does not pretend
otherwise.** What can be said:

* The mechanism that would explain it with no audio being wrong:
  `_scope_record` runs in the GATHER loop, after `_chipN_process_all` has
  already processed the whole block, so the per-sample scalar
  `_buf_<node>` holds only the LAST sample of the block by the time the
  scope samples it — and the recorded window is then the same word
  repeated. A step stimulus settles, so a parameter change that alters the
  waveform but not its settled value produces no movement and reads INERT.
  That is consistent with which families moved and which did not.
* Against a wholesale audio regression: `c2gold.sh`'s standing D80 record
  is that the block-kernel arm is bit-exact against the per-sample arm
  everywhere except the meters.
* **What settles it** is a block-aware witness — record `_blk_<node>` where
  the class publishes one, or move `_scope_record` inside the kernel — and
  re-running the same three arms. That is the next session's first job.

**The wider point is the one worth keeping: block kernels have been in
every capacity measurement since 2026-09-01 and had never once been
through famverify.** Making them the shipping configuration is what
exposed that, which is the whole argument for this session.

## 7. Bench state at the end

* **`~/dspboot` holds five pairs and NONE of the four that were there was
  replaced or reordered.** `chip1.ldr` `093c609f622cf805e7f675f1e2497a19`
  / `chip2.ldr` `2ba0e464e9679bd2e1b1c3c2a6f08744` are byte-identical to
  as-found; `conf_*` `602a0feb` / `b1325022`, `ship_*` `3f0e479a` /
  `ab43c75b` and `tx_*` `21f9fdc1` / `de14981f` untouched. This session's
  result is staged beside them as **`blk_chip1.ldr`
  `ac65ad386fb910b7bed7736872abae43`** / **`blk_chip2.ldr`
  `e5dce9e43c2c72290c115726ca31976c`**.
* Every image of this session ran from a separate staging path
  (`~/s9blk`, `~/s9txp`, `~/s9txp5`, `~/s9gf`). The window pair was copied
  aside before the bars that overwrite it and restored byte-identical
  afterwards, verified by md5.
* Bench back on the shipping bitstream **`dsp4_logic.a1f6672af6c3`**,
  verified four ways: IDCODE `0x020a30dd`, the ID knock SILENT (which is
  that bitstream's positive identification), PCM_CLK and PCM_FS both
  toggling, and `config.txt` diffing clean against
  `config.txt.asfound-20260909-s9` — the `dsp4-pcm-slave` overlay, as
  found. `dsp4_logic_maincap.d903ae1ac4a9` was flashed for the loop
  measurements and the duplex overlay used for them; both restored.
* Both DSPs booted from `~/dspboot`, CHIP_ID verified 1 and 2,
  `matrix-app` active. Rev A never touched.

## 8. What this session did NOT do

* **Through-DSP latency was not re-measured.** The 72 samples / 1.500 ms
  figure on record is a BLOCK=8 measurement and block 16 is a pipeline of
  twice the block length, so it is expected to roughly double — but that
  is arithmetic, not a measurement, and it is labelled as such. It needs
  the `_maincap` bitstream and the duplex overlay again.
* **`sigprofile2`, `busgold`, `bqeverify`, `fxverify`, `afbverify`,
  `geqverify` and `xoververify` were not re-run** on this pair. The
  capacity number quoted in §3 is a direct `_proc_cyc` read on the
  shipping image in the shipping configuration, which is the number the
  product actually runs at; the `.4` figures (chip 1 202,786 / chip 2
  226,442) were taken through `sigprofile2`, which decimates and injects
  a profiling stimulus, and the two are not the same instrument. They are
  NOT claimed to reproduce, because they were not tested.
* **`_proc_cyc_max` was not read.** §3 quotes `_proc_cyc`, the LAST pass.
  The worst-case pass is the number that decides a fit and it should be
  read before the margin in §3 is relied on.
