provenance: AI-drafted 2026-09-09 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# DSP readiness for the rev C reconciliation window

The window deploys the DSP firmware, the panel MCU headers (H1S3/H1S4),
the app and the matrix to the rev C unit TOGETHER. This is the DSP leg,
made ready and proven ahead of it so the window is a deploy and not a
debug. **It is PW-gated; nothing here was deployed.**

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
