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
