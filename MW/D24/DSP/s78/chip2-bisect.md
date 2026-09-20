provenance: AI-drafted 2026-09-20 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S78 — chip 2's ten points bisected, and the one-bit shift run to ground

Bench session on the rev C unit. No hands, no rails, no hardware change.
983.04 MHz throughout; the shipping config word is `0xE2018264`; the unit is
left as found.

---

## 0. Outcome in one paragraph

**Chip 2's ten points are not where the record looked for them, and the one-bit
shift is not what the record thought it was.** The dispatch named S71's
codec-return lanes and S74's talkback polarity as the suspects; the generator
output rules both out before a boot — *neither commit changes one instruction
chip 2 executes*, and the chip-2 image is byte-identical across both. The
growth is at the OTHER end of the range, on 2026-09-10 itself: **S22's matrix
mixer and S23's aux-mix buses**, twenty-four new unconditional chip-2 nodes
that run every block on every product whether or not anything is patched to
them. The ladder is eight driven D24 boot pairs with both ends reproducing
their references byte for byte. **And the `<< 1`: it is per-lane MFD, it is the
instrument's alone, and it is now fixed and proved bit-exact in simulation and
on the part.** The CM4 link is I2S on both sides and the CPLD de-frames it
exactly; what `DRIVE_ALL` did was broadcast *the Pi lane's framing* onto seven
lanes whose SPORT halves are configured `MFD = 2` for the pin-strapped AKM
converters. Measured on the part, one boot, one bitstream, one stimulus, five
lanes at once: **lane 6 bit-exact, every MFD-2 lane exactly ×2**. No converter
lane in a shipping build is touched by this. The one gate that did not land is
the no-hands loop measurement — **the analog rails are down and this session is
not authorised to raise them**; what could be measured without them is below,
and the question is in §6.

---

## 1. Gate 2(a) — where the one-bit shift comes from, read out of the source

The hub asked for option 3: read `shared/dsp4-logic/`, and say whether the CM4
PCM link is I2S and the CPLD's `drive_all` path left-justified, or the reverse.
**It is neither. Both sides of the CM4 link are I2S and agree; the shift is one
level down, in the DSP's own per-lane frame delay.**

### 1.1 The CM4 link is I2S on both sides, and the part already says so

The Pi is declared I2S by the overlay the bench stands on
(`shared/dsp4-logic/pi/dsp4-pcm-slave.dts:62`):

```
            simple-audio-card,dai-link@0 {
                reg = <0>;
                format = "i2s";
```

and the CPLD's re-framer is parameterised to match
(`shared/dsp4-logic/rtl/dsp4_pcm_reframe.v:55`):

```
    parameter integer PCM_DATA_DELAY = 1,    // 1 = I2S, 0 = left-justified
```

with the word boundaries derived from it
(`rtl/dsp4_pcm_reframe.v`, the de-frame block):

```
    localparam [5:0] LEFT_DONE  = PCM_DATA_DELAY[5:0] + 6'd32;
    localparam [5:0] RIGHT_DONE = PCM_DATA_DELAY[5:0];
```

**That they agree is not an argument, it is a measurement that has already been
taken**: the design-ID knock compares the de-framed words against a 64-bit magic
pair *inside* the CPLD —

```
    wire knock_hit = pi_sample
                     && (pi_word_pos == (PCM_DATA_DELAY[5:0] + 6'd1))
                     && (pw_flat[31:0]  == KNOCK_L)
                     && (pw_flat[63:32] == KNOCK_R);
```

— and S77 read `design_id 0x62d98a4d` back off the part. A de-framer one bit out
could not have matched `0xD5D51D1D` / `0x2A2AE2E2`. **So `pw_flat` is exact, and
whatever shifts the stimulus is downstream of it.**

### 1.2 It is MFD, and it is per lane

`DRIVE_ALL` puts one broadcast copy on every DSPA input lane
(`rtl/dsp4_logic_top.v:252`, as it was at the start of this session):

```
    assign i_dspa = {8{pcm_drive}};
```

and chip 1's RX halves **do not share one frame delay**
(`MW/D32/DSP/SHARC/src/chip1/lane_config.c:26`, generated):

```
const int c1_rx_lanes_mfd[8] = { 2, 2, 2, 2, 2, 2, 1, 2 };
```

Why they differ is stated in the firmware that consumes the table
(`MW/D32/DSP/SHARC/src/sport_config.c:21-37`):

> MFD IS NOT LOCKED AND IS NOT UNIFORM (S42-1). … The I2S variant puts one BCK
> between the frame edge and the MSB, on top of the one BCK LOGIC already
> leaves by asserting FS in the period before slot 0. So a converter half needs
> MFD = 2, while the two halves the CPLD's own re-framer serves (the Pi PCM
> lane in and the Pi return lane out) are built for MFD = 1 and stay there. The
> measured consequence of getting it wrong is S39-4: every received word
> arrived as (sample >>> 1), sign bit never set, on all twelve chip-1 lanes.

`lane_mfd()` in `tools/dsp/dsp_codegen.py:7062` derives it from the peer, and
`CPLD_FRAMED_SIGNALS = ('PI_PCM', 'PI_RET', 'DAC_MAIN')` is the whole list of
signals LOGIC frames itself.

**S39-4 is the same law with the sign the other way round.** MFD one too LOW
reads `sample >> 1`; MFD one too HIGH reads `sample << 1`. `drive_all` delivers
an MFD-1-framed stream to seven MFD-2 halves, so those seven read `<< 1` — and
lane 6, the one lane LOGIC really does frame in a shipping build, reads exactly.

---

## 2. Gate 2(b) — the same thing, measured on the part

**One boot, one bitstream (`driveall 14df62d98a4d`), four stimulus words, five
lanes read at the same instant.** Every chip-1 input node applies the same
`ashift by -3` wire-form scaling, so the lanes are directly comparable and a
ratio of exactly 2 is the shift and nothing else.

| CM4 plays (L) | lane 6 slot 0 `C1_XIN_PI_L` **MFD 1** | lane 4 slot 0 `C1_XIN_CODEC_01` **MFD 2** | lane 7 `C1_XIN_MEMS` **MFD 2** |
|---|---|---|---|
| `0x40000000` | `0x08000000`  = played >> 3, **exact** | `0xF0000000`  **×2** (wrapped) | `0xF0000000`  **×2** |
| `0x10000000` | `0x02000000`  **exact** | `0x04000000`  **×2** | `0xFC000000`  **×2** (slot 1 = R) |
| `0x00100000` | `0x00020000`  **exact** | `0x00040000`  **×2** | `0xFFFC0000`  **×2** |
| `0x00000020` | `0x00000004`  **exact** | `0x00000008`  **×2** | `0xFFFFFFF8`  **×2** |

**Lane 6 is bit-exact on every word and on both its slots. Every MFD-2 lane is
exactly one bit left on every word.** The first row is S77-3's wrap seen from
the inside: `0x40000000 << 1` is `0x80000000`, which is negative, so the
`>> 3` lands on `0xF0000000` — the same arithmetic that turned a full-scale
square into 2 LSB.

This also identifies the bitstream behaviourally, which matters because the
design-ID readback did not answer tonight (§7, S78-8): a part on which **all
eight** DSPA lanes carry the CM4's playback is running `drive_all` and nothing
else.

### 2.1 What this says about the product, and what it does not

**It says the shift is the instrument's.** `DRIVE_ALL` is the only thing that
ever puts a LOGIC-framed stream on a converter half. In a shipping build
`i_dspa[0..3]` are the AK5558 lanes as plain wires, `i_dspa[4]` is the AK4619
codec, `i_dspa[7]` is the MEMS bridge, and all of them are framed by the
converter, received on MFD-2 halves, and were proved that way by measurement in
S39-4. Lane 6 is the only LOGIC-framed lane in the product and it is MFD 1 and
bit-exact above.

**It does not, by itself, close the absolute-level question S70 left open.**
S70 derived the ADC's full scale at the talkback XLR as `+8.36 dBu` at MGN 0 dB
against the AK4619's own `2.83 Vpp` (`+2.2 dBu` differential) and attributed the
**6.16 dB** between them to "about 6 dB of loss between J1 and the codec's input
pins". Six decibels is also what one bit is worth, and nothing in tonight's work
touches that number — the codec lane is MFD 2 like every other converter lane,
so the class of fault found here cannot produce it, but the gap itself is still
an attribution resting on a loss nobody has measured. That is what gate 2(b)'s
loop was for.

### 2.2 The loop could not be measured, and why

The AUX 1 → talkback loop was run exactly as S70 ran it (`s70_route.py` on the
S69 `DSP4_TEST_NODES` pair, `chip1 a8dc45eb` / `chip2 251ce3b2`, the same image
S70 measured on), five drive levels:

```
osc -80  chan 35  AUX 1 bus        rms  -83.017  loop  -0.000 dB
osc -70  chan 35  AUX 1 bus        rms  -73.017  loop  +0.000 dB
osc -60  chan 35  AUX 1 bus        rms  -63.017  loop  -0.000 dB
osc -50  chan 35  AUX 1 bus        rms  -53.008  loop  +0.000 dB
osc -40  chan 35  AUX 1 bus        rms  -43.008  loop  +0.000 dB

osc anything  chan 51 / 52 / 53  (the three received codec lanes)  rms -336.124
```

**The DSP half of the loop is perfect** — the route is asserted and proved, the
AUX 1 bus tracks the oscillator to 0.000 dB at every level, so the DAC is being
fed. **The analog half returns exact digital zero**: `-336.124 dBFS` is the
arithmetic floor, not a noise floor, on all three codec return lanes including
with the oscillator off. S70 read `-75.9 / -98.9 / -68.4` on the same three
lanes with the oscillator off **and the rails up**.

`GPIO 26 (AN_EN)` reads `op pd | lo`, before and after stopping `matrix-app`,
and was left that way. The converters are not converting, which is the state
S49-15 named and S70 raised the rails to get out of. **Raising AN_EN is the
hub's to authorise and this dispatch does not authorise it**; S70's dispatch
said "AN_EN raise authorised in-spec" in as many words, and S78's says the loop
is "cabled and live", which it is on the DSP side and is not on the analog side
with the rails down. The question is in §8 as S78-Q1.

---

## 3. Gate 2(c) — the instrument fixed

### 3.1 The RTL

The broadcast copy is now framed for the halves it is actually aimed at, and
the one lane that is framed differently keeps its own stream.
`rtl/dsp4_pcm_reframe.v` gains a `DRIVE_MFD` parameter (default 2) and launches
the drive copy from its own period:

```
    wire [7:0] drive_period = frame_pos[9:2] + 8'd2 - DRIVE_MFD[7:0];
    wire [2:0] drive_slot   = drive_period[7:5];
    wire [4:0] drive_bit    = 5'd31 - drive_period[4:0];
    wire [7:0] drive_idx    = {2'b00, drive_slot[0], drive_bit};
```

`DRIVE_MFD = 1` reproduces the pre-S78 framing exactly, which is what the
negative control below stands on. `rtl/dsp4_logic_top.v` stops broadcasting
onto lane 6:

```
    assign i_dspa[5:0] = {6{pcm_drive}};
    assign i_dspa[6]   = pcm_tdm;
    assign i_dspa[7]   = pcm_drive;
```

Lane 6's `cs_mask` is `0x0003` — only slots 0/1 are received, and they are
exactly what `pcm_tdm` carries — so `C1_XIN_PI_L/R` still get the stimulus and
nothing is lost.

### 3.2 The simulation gate that could not see this, and now can

`sim/model_tdm_rx.v` had **one hard-wired MFD**, and its header said so:
"TDM_SAMPLE_EDGE_RISING=1, TDM_MFD=1". Every testbench in the suite
instantiated that one receiver, so a transmitter aimed at MFD 1 and received by
an MFD 2 half — `DRIVE_ALL` on seven lanes out of eight — read PASS here and
arrived on the part one bit left. **This is the same shape as the capture-side
hole the file's own `CAP_EXTRA_DELAY` comment records** ("Nothing had ever
simulated this direction").

The model now takes `MFD` as a parameter, and taking it forced a second defect
out: resetting the bit counter at every frame sync is only correct at MFD = 1.
A TDM8 frame is 256 BCK and the wire is continuous, so a frame delay does not
shorten the frame, it rotates where FS falls inside the stream — at MFD = 2 the
last two bits of slot 7 arrive *after* the next FS. The model now keeps a
free-running bit index that FS **checks** rather than resets.

`sim/tb_pcm_drive.v` now instantiates the receivers the lanes really have, and
carries the defect as a negative control: a **second reframer at
`DRIVE_MFD(1)`** — the pre-S78 framing — read by an MFD-2 half, which must come
out `(word << 1)` with the next slot's MSB in the LSB.

```
== tb_clkgen: PASS
== tb_pcm_reframe: PASS
== tb_pcm_drive: PASS
== tb_pcm_capture: PASS
== tb_logic_top: PASS
SIM GATE: OK (5 testbench(es))
```

**S77-3 is now reproduced in simulation and fails the suite if it comes back.**

### 3.3 The bitstream, and the A/B on the part

Built from a clean tree with the sim gate green, and beside it the **same tree
without the change**, so the artifact under test is one change away from its own
control rather than from whatever is on the part:

| artifact | tree | LE | pins | fmax | what |
|---|---|---|---|--:|---|
| `dsp4_logic_driveall.14df62d98a4d` | built 2026-09-11 | — | — | 67.02 MHz | **what was on the CPLD for every capacity row in this report** |
| `dsp4_logic_driveall.1ee6b5056fb7` | `main` unmodified | 400 | 69 | — | the control: `main` today, pre-change |
| `dsp4_logic_driveall.c49f4128a083` | `main` + this change | **416** | **69** | 66.19 MHz | the fixed stimulus |

**The change costs 16 logic elements and no pins**, measured between the two
builds this session made from the same tree. (LE/pin figures are not recorded in
the manifests, so the bench artifact's are left blank rather than quoted from
`loadlogic.sh`'s S37-era note.)

**The bench artifact `14df62d98a4d` is NOT reproducible from `main`** — the
slot-map source hash moved at S72 (`2c53de21…` → `c4a3ca82…`). So `1ee6b5056fb7`
is the honest control, and the A/B below is between those two: one change apart,
same slot map, same tree.


---

## 4. Gate 1 — the bisect

### 4.1 The candidates, listed from the generator before anything was booted

The dispatch named two suspects. **The generated code rules both out.**

* **S71 (`b361bdb0`), the codec-return lanes** — touches `chip1/block_io.asm`,
  `chip1/nodes/C1_TALK_01.asm`, `C1_XIN_CODEC_01/03/04.asm`,
  `C1_XS_XFER_CODEC_AUX_L/R.asm`. Every one is chip 1. The only shared file is
  `dsp_block.h`, and the change there is the `DSP4_TALK_INVERT` macro.
  **Zero chip-2 files.**
* **S74 (`bc22a1cc`), `DSP4_TALK_INVERT` ON** — `build.sh`,
  `check_shipping_config.sh`, `shipping.config`, `src/diag.h`,
  `src/dsp_block.h`, plus tools. **No `chip2/` file at all**; chip 2's image
  differs from the previous arm's by the config stamp, which is what S77
  recorded as "two stamp bytes".

What the diff of chip 2's generated graph across the two ends actually shows is
**24 new node instances and 15,464 inserted lines**, and the image sizes name
the landings without a boot:

| arm | commit | chip 2 image | size | Δ |
|---|---|---|--:|--:|
| `s78b19` | `a096c585` S19 | `3b3a6f8e` | 280,396 | — |
| `s78b21` | `06d31b25` S21 | `3b3a6f8e` | 280,396 | **byte-identical** |
| `s78b22` | `9ffdb4ee` S22 | `38be7126` | 285,916 | **+5,520** |
| `s78b23` | `4fdfe5ed` S23 | `6b13cab3` | 306,676 | **+20,760** |
| `s78b24` | `86f972a3` S24 | `363d94ab` | 307,892 | +1,216 |
| `s78b32` | `97c91c33` S32 | `363d94ab` | 307,892 | **byte-identical** |
| `s78b42` | `8f4a9d17` S42 | `7b1311e8` | 307,980 | +88 |
| `s78b65` | `0871f099` S65 | `3a9c950d` | 307,980 | 0 (different bytes) |
| `s78b74c` | `c5210a86` S74c | `e88a7a43` | 307,980 | 0 (different bytes) |

`s78b21` and `s78b32` are byte-identical on **both** chips to the arm before
them, so they were not booted and cannot differ; that is stated rather than
measured, which is the cheaper and the stronger claim.

### 4.2 The ladder, and its two end controls

Each arm is a full build **from its own tree's own `shipping.config`**, out of a
git worktree at that commit, with no overrides — so the arm is the tree, not a
switch. Run with **today's** instrument (the S77 repairs), driven, D24, two
boots each, regime proved on both chips on every boot.

**Both ends reproduce their references, which is what makes the ladder worth
anything:**

* `s78b74c` builds `chip1 10a41300` / `chip2 e88a7a43` — **byte-identical to
  S77's `s77shk0` pair and to S74c's**, and reads 401,460 / 401,631 and
  425,440 / 425,801 against S77's 401,759 / 401,471 and 425,326 / 425,296.
  **Within 300 cycles on chip 1 and 500 on chip 2, across two sessions.**
* `s78b19` reads chip 2 **390,725 / 390,468** against `cap-s19blk`'s
  **390,712** of 2026-09-10 — **13 cycles on the first boot**, across nine days
  and three instrument repairs.

### 4.3 The rows

| arm | commit | | chip 1 | chip 2 |
|---|---|---|--:|--:|
| `s78b19` | S19 | r1 / r2 | 390,817 / 390,636 | 390,725 / 390,468 |
| `s78b22` | S22 | r1 / r2 | 396,539 / 396,757 | 403,544 / 396,815 |
| `s78b23` | S23 | r1 / r2 | 399,851 / 399,839 | 425,499 / 425,182 |
| `s78b74c` | S74c | r1 / r2 | 401,460 / 401,631 | 425,440 / 425,801 |

### 4.4 The attribution

Step deltas, mean of the two boots, against the 327,674-cycle budget:

| step | chip 1 | chip 2 |
|---|--:|--:|
| S19 → **S22**, the matrix mixer | +5,922 (**+1.81 pts**) | +9,583 (**+2.92 pts**) |
| S22 → **S23**, the aux mix buses + FX returns | +3,197 (**+0.98 pts**) | +25,161 (**+7.68 pts**) |
| S23 → S74c, *everything else in the range* | +1,700 (+0.52) | **+280 (+0.09)** |
| **end to end** | **+10,819 (+3.30)** | **+35,024 (+10.69)** |

against S77's independently measured +11,797…+12,181 (+3.60…+3.71) and
+34,560…+34,614 (+10.54…+10.56) for the same two ends.

**S22 and S23 own 10.60 of chip 2's 10.69 points.** By S23 chip 2 is already at
its final number — its two boots there read 425,499 / 425,182 against S74c's
425,440 / 425,801 — so **everything that landed between 2026-09-11 and
2026-09-19, the two suspects the dispatch named included, costs chip 2 0.09
points, which is a twentieth of the instrument's own chip-2 spread.**

**The honest uncertainty is on the split between the two, not on the pair.**
`s78b22`'s chip-2 boots differ by 6,729 cycles (2.05 points) where every other
arm's agree to a few hundred; S77 put chip 2's boot-to-boot spread at about two
points and this is it. So S22 is +2.9 points ±1 and S23 is +7.7 ∓1; the sum is
firm and the boundary between them is not.

**And the nine days were never nine days.** The old-end rows were taken at S19
and S22/S23 landed the same day, 2026-09-10 — so the growth the record has been
calling "nine days of graph growth since 2026-09-10" happened *within hours of
the reference rows being taken*, and the eight days after it are flat.
**Flashed and measured both ways, same pair, same boot procedure, same four
stimulus words, one change apart:**

| bitstream | MFD-2 lane readings vs the MFD-1 lane | verdict |
|---|---|---|
| `1ee6b5056fb7` — `main`, pre-change | exact **0** / ×2 **12** / other 0 | `MFD 2 LANES SHIFTED ONE BIT LEFT` |
| `c49f4128a083` — `main` + the fix | exact **12** / ×2 **0** / other 0 | `BIT-EXACT ON EVERY LANE` |

On the fixed bitstream every lane reads exactly `played >> 3`, lane 6 included,
so nothing was traded away to get the other seven right — and lane 6 still
carries the stimulus, because it is fed from `tdm_out` rather than left silent.

### 3.4 The amplitude is now a property of the bitstream, and says so

With the shift gone, the same level at the part needs a different played word,
and the two must never be mismatched silently — that is the whole shape of
S77-3. `drive_audio.sh` now derives what it plays from **the peak the PART
sees**:

```
PART_PEAK="${PART_PEAK:-1073741824}"     # 0x40000000, -6.02 dBFS
LANE_SHIFT="${LANE_SHIFT:-0}"            # 0 = driveall, 1 = driveall-pre78
AMP = PART_PEAK >> LANE_SHIFT
```

`LANE_SHIFT=1` yields `536870912` — **the exact word S77 and every arm of this
session's bisect played**, so an old row stays reproducible to the bit, which a
dB figure would not have given (−6 dBFS rounds to a different integer). The
stream announces the derivation every time it starts, and `loadlogic.sh
driveall` now names the fixed artifact while `driveall-pre78` keeps the retired
one, so the two defaults agree by construction and the old behaviour has to be
asked for in both places.

**Still due, and listed rather than done:** the S28/S29 rows that quoted an
amplitude — `cap-s28-{d12,d16,d16oldprover,d24,d32}`, `cap-s29ctl-d32`,
`cap-s29ns-d32`, seven arms — were all taken with the full-scale square on the
pre-fix bitstream, so on every MFD-2 lane they were driven at **2 LSB**. They
are silence rows wearing a driven label and want re-taking on `driveall` at
`PART_PEAK` 0x40000000. The night went on the bisect; this is S78-Q4.

## 5. What runs for nothing, and the bypass

The dispatch asks, for each landing that owns points: **use-proportional or
unconditional, and if a node runs for nothing, propose the block-level bypass
and price it.** Both landings are unconditional — no build switch and no product
gate stands between `process_chain.asm` and any of the twenty-four new nodes —
and both carry instances that **no cell in `defs` can ever reach**.

### 5.1 The counts, from `defs` and from the built tree

| | cells the product declares | chip-2 node instances built | instances no cell can reach |
|---|--:|--:|--:|
| aux mix, D24 | `Chan001AuxOn/Send001..008` → **8** | `C2_MIX_AUX_01..12` → **12** | **4** |
| aux mix, D32 | `…001..012` → **12** | 12 | 0 |
| matrix output, D24 | `Matrix001/002 Level+Mute` → **2** | `C2_MTX_FDR/OUT/RECV_MTX_01..04` → **4** each | **2** (no output cell) |
| matrix output, D32 | `Matrix001..004 Level+Mute+Name` → **4** | 4 each | 0 (by output cell) |
| matrix **send**, both products | `Chan001MatrixOn/Send001..002` → **2** | 4 chains | **2 more, on BOTH products** |

Two facts fall out that are worth separating:

* **A D24 runs four `C2_MIX_AUX_*` instances for which no `AuxOn`/`AuxSend`
  cell exists.** That is the S23 bypass class exactly, one product along.
* **Matrix buses 3 and 4 have no channel send cell on EITHER product.**
  `Chan001MatrixOn/Send` stops at `002` in `defs/products/d24/dsp.csv` and in
  `defs/products/d32/dsp.csv` alike, while D32's master declares
  `Matrix003/004 Level+Mute+Name` and D24's declares neither. So on D32 two
  matrix buses have an output level, a mute and a name and **nothing that can
  be routed into them**; on D24 those two chains have no cell at either end.
  That is a **defs question, not a firmware one** — S78-Q2.

### 5.2 The two bypass patterns already in the tree, and which one to copy

`DSP4_AUXIN_BYPASS` (S32) is **caller-side and two-word**
(`src/chip2/process_chain.asm:1030-1039`):

```
r2 = dm(_auxin_on_C2_SNK_IN_01); r2 = pass r2; if ne jump (pc, .c2brunabC2_SNK_IN_01_run);
r2 = dm(_auxin_byp_C2_SNK_IN_01); r2 = pass r2; if ne jump (pc, .c2brunabC2_SNK_IN_01_end);
.c2brunabC2_SNK_IN_01_run:
    call _C2_SNK_IN_01_process;
.c2brunabC2_SNK_IN_01_end:
```

Four block-rate instructions, and on the second and every later parked block the
**call does not happen at all**. The second word is not decoration: without it
the node's last block would be summed for ever by whatever reads it, which is
what the S32 commit message says in as many words.

`C2_FX_ENG_0N`'s park gate (S23) is **callee-side**
(`src/chip2/nodes/C2_FX_ENG_01.asm:169-178`): the chain calls unconditionally
and the node returns early after zeroing its block. It still pays call, return
and a 16-word zero fill every block. **For nodes whose whole body is a 16-word
copy — `C2_RECV_MTX_*` and `C2_MTX_OUT_*` — that pattern saves nothing.** The
caller-side pattern is the one to copy.

### 5.3 The proposal

1. **`DSP4_AUX_BUS_LIMIT`, from the product's own aux count.** The generator
   already knows how many `AuxOn/Send` cells the product declares; emit the
   caller-side gate for every `C2_MIX_AUX_NN` above that count, permanently
   parked, so a D24 stops calling four of them. No new host word, no runtime
   state, and the parked instance publishes silence once.
2. **The same gate, runtime-keyed, for the rest.** `C2_MIX_AUX_NN` already
   carries an all-off fast path inside the node
   (`C2_MIX_AUX_01.asm:129-152`: when every `_mix_on_*` is 0 and the fixed feed
   is unity it degenerates to a block copy) — but it reaches that test only
   **after** an unconditional 6-iteration ramp/fold prologue and a call. A
   caller-side gate on the same condition skips the call too.
3. **The two unreachable matrix chains, at the caller.** `C2_MTX_FDR_03/04`,
   `C2_MTX_OUT_03/04`, `C2_RECV_MTX_03/04` — six instances on **both**
   products until the defs question in S78-Q2 is answered. `C2_MTX_OUT_*`
   writes a physical TX slot, so it must publish silence once and then be
   skipped, exactly as `DSP4_AUXIN_BYPASS` does.

**Three things would make this wrong, and all three are already visible in the
tree**: `C2_MTX_OUT_*` drives a SPORT TX slot by DMA, so a skipped call must
leave silence behind rather than a stale block; a ramp in flight when the gate
closes must have its pending frame count cleared, the way `C2_SNK_IN_01.asm:189`
does, or a level written while parked plays out late on resume; and
`C2_MTX_FDR_*` publishes `_fdr_busy_*` for the ROUTING crosspoint, which a
bypass has to keep answering.

**One thing to fix before any of it is priced against "today":** the committed
`shipping.config` has **no `DSP4_AUXIN_BYPASS` line at all** — `build.sh:258`
defaults it to 0 — although `shipping.config.s32` set it to 1. The S32 bypass is
**off in the configuration that ships**. That is a separate landing's worth of
points sitting switched off, and it is S78-Q3.

---

## 6. The unit, as it was left

1. **LOGIC**: `dsp4_logic.a1f6672af6c3` — the shipping bitstream, the state the
   bench lives in. `FLASH OK on attempt 1`. (Three flashes preceded it this
   session: `driveall 14df62d98a4d` for the bisect, then `driveall-base
   1ee6b5056fb7` and `driveall c49f4128a083` for the A/B, each `OK on attempt 1`.)
2. **DSP pair**: the shipping configuration,
   `84c7951333e982204a38fe65e49d3fd6` / `bb2a7c6ea9e5d0caa419bc0b15a97f7c` —
   **rebuilt from `shipping.config` at HEAD this session and byte-identical to
   S77's pair** — booted and configured for D24, `chip check OK` on both.
3. **The configuration the part reads back**: `DIAG_BUILD_CFG 0xCF45FF10`,
   `DIAG_BUILD_CFG2` **`0xE2018264`** on both chips, `CFG3` unmapped.
   `DSP4_TALK_INVERT` on. The same word S77 left.
4. **`matrix-app`**: `active`, and **3 of 3 MCUs verified** on this restart
   (`MCU boot verified: H1S1 / H1S3 / H1S4`).
5. **`GPIO 26 (AN_EN)`**: `op pd | lo` — **as found on arrival**, and not
   written by this session. `GPIO 27 (CS_M)`: `ip pu | hi`, as found.
6. **`/home/app/dspboot` was NOT overwritten** — `chip1.ldr`/`chip2.ldr` still
   dated 2026-09-10 18:36. `ldr/manifest.txt` untouched. Every arm ran from its
   own staging directory under `/home/app/dspcap/`.
7. **The talkback family reads `cells 8 · contract 4/4 · audio INERT`**, where
   S77 recorded `audio LIVE`. The contract half is identical; the audio half is
   INERT **because the rails are down** — the same fact as §2.2 and S78-5, not a
   regression. AN_EN was already `lo` when this session arrived.
8. **The codec's register image was not touched.** The loop run wrote DSP cells
   only (`Chan006CompOn/GateOn/TubeOn/AuxOn/AuxSend`), and those were wiped by
   the reboots that followed. No `codec_reg`/`volad2r` write was made.

## 7. Findings

**S78-1. 🔴 CHIP 2's TEN POINTS ARE S22 AND S23, AND BOTH LANDED ON
2026-09-10 — THE SAME DAY AS THE ROWS THEY ARE MEASURED AGAINST.** Eight driven
D24 arms, two boots each, both ends reproducing their references (`s78b74c`
byte-identical to S77's `s77shk0` and reading within 300/500 cycles of it;
`s78b19` reading chip 2 within **13 cycles** of `cap-s19blk` across nine days).
**S22's matrix mixer costs chip 2 +9,583 cycles/block (+2.92 pts) and S23's aux
mix buses + FX returns cost +25,161 (+7.68 pts); the two together are +10.60 of
the +10.69 measured end to end.** Everything else in the range — S24, S32, S42,
S65, S66…S74c — costs chip 2 **+0.09 points**, a twentieth of the instrument's
own chip-2 spread. Chip 1 over the same range: S22 +1.81, S23 +0.98, S32 +0.43,
rest ≤0.16, total +3.30 against S77's +3.60…+3.71. **The record's phrase "nine
days of graph growth since 2026-09-10" is wrong in its premise: the growth
happened within hours of the 2026-09-10 rows and the eight days after are
flat.** The one soft edge is the split between S22 and S23 — `s78b22`'s chip-2
boots differ by 6,729 cycles (2.05 pts) where every other arm's agree to a few
hundred — so S22 is +2.9 ±1 and S23 is +7.7 ∓1; the sum is firm.

**S78-2. 🔴 THE DISPATCH'S TWO NAMED SUSPECTS CHANGE NOT ONE CHIP-2
INSTRUCTION.** S71 (`b361bdb0`, the codec-return lanes) touches only
`chip1/block_io.asm`, `chip1/nodes/C1_TALK_01.asm`, `C1_XIN_CODEC_01/03/04.asm`
and `C1_XS_XFER_CODEC_AUX_L/R.asm` — all chip 1 — plus the `DSP4_TALK_INVERT`
macro in `dsp_block.h`. S74 (`bc22a1cc`) touches no `chip2/` file at all; chip
2's image differs from the arm before it by the config stamp, which is S77's
"two stamp bytes". Both were ruled out **from the generator output before
anything was booted**, and the rows then confirmed it. Two arms (`s78b21`,
`s78b32`) were not booted at all because their images are byte-identical on both
chips to the arm before them — a stronger claim than a measurement.

**S78-3. 🔴 THE ONE-BIT LEFT SHIFT IS PER-LANE MFD, NOT JUSTIFICATION, AND IT IS
THE INSTRUMENT'S ALONE.** Both sides of the CM4 link are I2S and agree
(`pi/dsp4-pcm-slave.dts:62` `format = "i2s"`; `rtl/dsp4_pcm_reframe.v:55`
`PCM_DATA_DELAY = 1`), and the design-ID knock had already proved the de-framer
exact by matching a 64-bit magic word through it. What `DSP4_DRIVE_ALL` did was
broadcast **one** framing onto lanes that do not share one frame delay:
`c1_rx_lanes_mfd[8] = { 2,2,2,2,2,2,1,2 }` (`chip1/lane_config.c:26`) — lane 6
is MFD 1 because LOGIC frames it, the other seven are MFD 2 because a
pin-strapped AKM converter does (`sport_config.c:21-37`, S42-1). MFD one too low
reads `>> 1` (S39-4, measured); one too high reads `<< 1`. **Measured: one boot,
one bitstream, four words, five lanes at once — lane 6 bit-exact on both slots
and every word, lanes 4 and 7 exactly ×2 on every word.** No converter lane in a
shipping build is affected; `DRIVE_ALL` is the only thing that ever puts a
LOGIC-framed stream on a converter half.

**S78-4. THE STIMULUS IS NOW BIT-EXACT ON EVERY LANE, PROVED A/B ON THE PART,
AND THE SIM GATE CAN SEE THE DEFECT.** `rtl/dsp4_pcm_reframe.v` gains
`DRIVE_MFD` (default 2) and launches the broadcast copy one BCK later;
`rtl/dsp4_logic_top.v` leaves lane 6 on `tdm_out`, which is already right for
it, so all eight lanes are exact rather than seven, and lane 6 keeps its
stimulus (its `cs_mask` is `0x0003` and `tdm_out` carries exactly those two
slots). A/B on the part, one change apart: `1ee6b5056fb7` reads **0 exact /
12 ×2**, `c49f4128a083` reads **12 exact / 0 ×2**. Cost: **+16 logic elements,
no pin change**, timing met at 66.19 MHz. `sim/model_tdm_rx.v` had ONE
hard-wired MFD — every testbench instantiated an MFD 1 receiver, which is why a
transmitter aimed at MFD 1 and received by an MFD 2 half read PASS in
simulation and arrived one bit left on the part. Parameterising it forced out a
second model defect: resetting the bit counter at every FS is only correct at
MFD 1, because a TDM8 frame is 256 BCK and the wire is continuous, so at MFD 2
the tail of slot 7 arrives after the next FS. `sim/tb_pcm_drive.v` now carries
the defect as a negative control — a second reframer at `DRIVE_MFD(1)` read by
an MFD 2 half, which must come out `(word << 1)`. **S77-3 fails the suite if it
returns.**

**S78-5. 🔴 THE NO-HANDS LOOP MEASUREMENT COULD NOT BE TAKEN: THE ANALOG RAILS
ARE DOWN AND THIS SESSION IS NOT AUTHORISED TO RAISE THEM.** `GPIO 26 (AN_EN)`
reads `op pd | lo` before and after stopping `matrix-app`, and was left there.
The AUX 1 → talkback loop was run exactly as S70 ran it, on S70's own image
(`chip1 a8dc45eb` / `chip2 251ce3b2`): **the DSP half is perfect** — the route
asserts and proves and the AUX 1 bus tracks the oscillator to `0.000 dB` at five
levels from −80 to −40 dBFS — and **all three received codec lanes read
`-336.124 dBFS`, exact digital zero, at every level including oscillator off.**
S70 read `-75.9 / -98.9 / -68.4` on the same three lanes with the oscillator off
and the rails UP. S70's dispatch said "AN_EN raise authorised in-spec"; S78's
does not. See S78-Q1.

**S78-6. 🔴 MATRIX BUSES 3 AND 4 CANNOT BE ROUTED INTO ON EITHER PRODUCT, AND A
D24 RUNS FOUR AUX MIXES FOR WHICH NO CELL EXISTS.** `Chan001MatrixOn/Send` stops
at `002` in `defs/products/d24/dsp.csv` **and** in `defs/products/d32/dsp.csv`,
while D32's master declares `Matrix003/004 Level+Mute+Name` and D24's declares
neither. So on D32 two matrix buses have an output level, a mute and a name and
nothing that can feed them; on D24 the same two chains have no cell at either
end. Separately, D24 declares `Chan001AuxOn/Send001..008` — eight aux buses —
and the firmware builds twelve `C2_MIX_AUX_*`, so **four run every block on
every D24 for something no cell can turn on**. That is the S23 bypass class
exactly. Both are questions for defs, not for the firmware: S78-Q2.

**S78-7. 🔴 `DSP4_AUXIN_BYPASS` IS OFF IN THE CONFIGURATION THAT SHIPS, AND HAS
NEVER BEEN IN IT.** `build.sh:258` defaults it to 0; `shipping.config.s32:319`
set it to 1; the committed `shipping.config` has no such line, and
`git log -S AUXIN_BYPASS -- shipping.config` returns nothing at all. S32 built
and measured the lever and it was never switched on for the shipping arm. See
S78-Q3.

**S78-8. `dsp4_logic_id.py` DID NOT ANSWER TONIGHT ON THE SAME OVERLAY S77
REPORTED IT WORKING ON.** Two invocations, immediately after a clean
`FLASH OK on attempt 1`: "no reply: nothing in the capture carried the 0xD594
marker." S77-4 recorded the tool fixed and quoted `design_id 0x62d98a4d` read
off this part, on this `dsp4-pcm-slave` overlay, which the standing bench note
says makes the tool useless. **So the one command that identifies a bitstream
from the part is not dependable.** Identity in this session rests on the named
SVF, its md5, the JTAG IDCODE either side — and, better, on behaviour: a part on
which all eight DSPA lanes carry the CM4's playback is running `drive_all`, and
the A/B in §3.3 identifies which `drive_all` it is by what the MFD-2 lanes read.

**S78-9. THE CAPACITY INSTRUMENT REPRODUCES ACROSS SESSIONS AND ACROSS NINE
DAYS.** `s78b74c` against S77's `s77shk0`, byte-identical images: 401,460 /
401,631 against 401,759 / 401,471 on chip 1 and 425,440 / 425,801 against
425,326 / 425,296 on chip 2. `s78b19` against `cap-s19blk` of 2026-09-10:
chip 2 390,725 against 390,712. **After three sessions of repairs the bar is
stable to a few hundred cycles**, which is what makes a step of +9,583 or
+25,161 an attribution rather than a guess.

## 8. 🔴 For the hub

**S78-Q1 — the no-hands loop needs AN_EN, and this dispatch does not authorise
raising it.** The gate asked for the AUX 1 → talkback loop to be played and
read with no hands, on the ground that the loop is "cabled and live". It is
cabled, and it is live on the DSP side — the AUX 1 bus tracks the oscillator to
0.000 dB at five levels — but `GPIO 26` reads `lo`, all three codec return
lanes read exact digital zero, and the converters are not converting. S70 took
this measurement with an explicit "AN_EN raise authorised in-spec" in its
dispatch; the standing bench rule is that a dispatched session never writes
AN_EN. Options:

1. **Authorise the raise in a re-dispatch** (`sudo pinctrl set 26 op dh`, 150 ms,
   measure, `op dl` before handback, exactly as S70 did). ~20 minutes of bench
   time; everything else is staged and the S69/S70 tooling is on the card.
2. **Have the hub or PW raise it** and leave it up for a window a dispatched
   session can measure inside.
3. **Treat §1 and §2 as sufficient** — the shift is located to `DRIVE_ALL` by
   source and by measurement, and no converter lane can see it — and close
   S77-Q1 without the analog check. **This does NOT close the other question the
   loop would have answered**: S70's 6.16 dB between the AK4619's own full scale
   and the ADC full scale it derived at J1 is still attributed to an unmeasured
   loss between J1 and the codec pins, and six decibels is also what one bit is
   worth. Tonight's work makes the MFD class of fault impossible there (the
   codec lane is MFD 2 like every other converter lane) but does not measure the
   loss.

**Recommendation: option 1.** It is cheap, it is the only one that retires the
6.16 dB, and a mic input that is 6 dB hot is not a thing to leave attributed.

**S78-Q2 — two defs questions the bisect turned up, both about cells that do not
exist.** (a) `Chan001MatrixOn/Send` stops at `002` on **both** products while
D32's master declares four matrix buses and D24's declares two — so matrix 3 and
4 are output-only on D32 and absent at both ends on D24, and the firmware builds
four of each matrix node on both. Is that a real product limit (two matrix sends
per channel) or missing rows? (b) D24 declares eight aux buses and the firmware
builds twelve `C2_MIX_AUX_*`, so four run for nothing on every D24. Both are
`defs` changes if they are changes at all; this repo is a consumer and has
invented nothing.

**S78-Q3 — `DSP4_AUXIN_BYPASS` has never been in `shipping.config`.** S32 built
the lever, measured it, and it went into `shipping.config.s32` and no further;
`build.sh` defaults it to 0 and `git log -S` over the shipping file returns
nothing. Is that deliberate, or did the S32 landing simply not carry through to
the configuration that ships? It is points sitting switched off.

**S78-Q4 — the S28/S29 rows are due for re-taking and were not done tonight.**
`cap-s28-{d12,d16,d16oldprover,d24,d32}`, `cap-s29ctl-d32`, `cap-s29ns-d32` —
seven arms — were taken with the full-scale square on the pre-fix bitstream, so
on every MFD-2 lane they were driven at 2 LSB and are silence rows wearing a
driven label. The instrument is now fixed and the recipe is one line per arm
(`ARM=… PRODUCT=… ./capacity.sh --driven` on `loadlogic.sh driveall`). The
night went on the bisect; this is a short session of its own, and the D12/D16
arms will need their own products staged.

**S78-Q5 — what to do with the ten points, now that they are attributed.** S22
and S23 are both architecture rather than options: the matrix mixer and the aux
mix buses are product-defined functions and they have to exist. What is
available is the bypass class in §5 — four `C2_MIX_AUX_*` and six matrix-chain
instances that no cell on a D24 can reach, plus the runtime all-off case — and
it is the same lever S32 built and S78-Q3 says was never switched on. **None of
it is worth designing until Q2 and Q3 are answered**, because both change what
"runs for nothing" means.
