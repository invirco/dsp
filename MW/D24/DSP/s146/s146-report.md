provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S146 — preparing the whole-switch window for the S142–S145 DSP graph

**Desk only.** Nothing was flashed, no DSP image was loaded, no app was
deployed, and not one byte was written to MW-D24-2. The unit was read
READ-ONLY: `md5sum`, `ls`, `cat` of config files, `pinctrl get`,
`systemctl is-active`, and four files copied OFF the unit for desk-side
inspection. No SPI, no bus, no rails, no phantom, no GPIO write.

**Witnessed before and after, unchanged either side:** GPIO26 (AN_EN)
`op pd | lo`, GPIO27 (CS_M) `ip pd | lo`, `matrix-app` active,
`d24-testui` inactive — exactly as S145 left them.

Deliverables: `MW/D24/DSP/s146/switch-runbook.md` (the window),
`MW/D24/DSP/s146/build-images.sh` (the md5-gated rebuild), findings
S146-1 … S146-5.

---

## 1. What the window moves — the question the dispatch asked, settled

Nine files, and the list is short because the MATRIX GENERATION does not
move: `46109e9fb812` on both sides, and every one of the unit's 5,767
`MxAdd` values is byte-identical to this repo's `MW/D24/MX/_matrix.csv`
(checked row by row after unpacking the unit's own `_matrix.mxc`; 0
differences).

**Moves:** `chip1.ldr`, `chip2.ldr`, `chip1.sym.json`, `chip2.sym.json`
(to a new stage, `/home/app/ship_s146/`); `landed-d24.json`,
`dsp4_config.py`, `input_patch.json` (overwritten in `/home/app/dspboot/`);
`pair.conf`; and the app, which the hub builds.

**Does not move:** the pack, the three panel MCUs, MH1, the LOGIC CPLD.

### 1.1 The pack carries the DSP addresses — and still does not need to move

This is the half of the question that had moved since it was last answered.
S45 recorded that the app *reads* `DspSpi`/`DspPage`/`DspAdd`/`DspAddHex`
for display only and has no DSP writer. **It has one now.**
`mx26 src/sw/app/Services/Dsp/{DspAddressMap,DspApply,SpiDevDspLink}.cs`,
and `DspAddressMap`'s own header says it plainly: *"This is deliberately the
app's ONLY source of DSP addresses… the app never reads dsp.csv, never
computes a stride of its own, and never carries a second copy."*

So the pack IS the app's DSP contract. It still does not move, for two
reasons read off the unit rather than assumed:

1. **Every Dsp\* column in the unit's deployed pack is empty — 0 of 5,767
   rows.** Unpacked with `defs/tools/mxc_pack.py` and counted. This repo's
   `_matrix.csv` carries 3,800. So today the app has no DSP addresses at
   all, and the switch does not make that worse.
2. **`dspWriteEnable` is false**, the default, witnessed in the unit's own
   boot log: `Boot.RunDspApply() - dspWriteEnable=false: DSP parameter link
   not opened, no node state written`.

The bench tools reach the DSP through `landed-d24.json`, not the pack. So
the graph runs without the pack moving, and republishing it would be three
changes at once — arming a writer, handing it 3,800 addresses for the first
time, and adding six `Ramp*` columns the deployed pack does not carry (this
repo's header is 38 columns, the unit's 32). Recorded for PW as a separate
window (S146-4), not done here.

### 1.2 Why the panel MCUs, MH1 and the CPLD are untouched

- **Panel MCUs** carry `matrix.h`, which is `#define <CellName> <MxAdd>`
  and nothing else. The generation has not moved and no `MxAdd` has moved.
  No panel MCU has any knowledge of a DSP address, node or TDM slot.
- **MH1** is the flash router: it reads the socket id out of a `.shex`
  header record and drives `S_Boot[]`. It is not in the DSP path.
- **The LOGIC CPLD** (shipping `d02d83b3cc22`) carries a fixed TDM slot map.
  The new graph writes DAC_09/10/11/12/14/15/16 — **every one already in
  `shared/dsp4-logic/slot-map.csv` at `scope=BOTH`, line `B_O1` slots 0–7**,
  a file unchanged since S109, before S142. The graph changed which node
  writes an existing slot, which the CPLD cannot see.

### 1.3 The host-side files that DO move, and exactly what changes in each

| file | change |
|---|---|
| `landed-d24.json` | pin `defs-v2026.09.19.3` → `.28.4`; 3,989 → 3,800 cells: **+168, −357, 40 moved**. All 40 moved are chip 2 and all 40 are the ruled D6/R5 outcome (`C2_MAIN_OEQ_03→C2_CTR_EQ` 19, `OEQ_04→C2_WOOF_EQ` 9, `OLIM_03→C2_CTR_LIM` 4, `OLIM_04→C2_WOOF_LIM` 4, `XOVER→C2_WOOF_XOVER` 2, `OUT_03→C2_CTR_FDR` 1, `OUT_04→C2_WOOF_FDR` 1). The 357 removed are the `.28.1` block-audit drops (96 chip-1 `Chan*Matrix*` on `C1_RTG_*`, 261 chip-2 group/matrix surface) |
| `dsp4_config.py` | one value: D24 `CFG_MTX_MASK` `0x00000003` → `0x00000000` (S143 item 3a). The rest of the diff is the comment explaining it |
| `input_patch.json` | the `contract` string only, `defs-v2026.09.24.2` → `.28.4`. The patch tuple is byte-identical — no input moves |
| `pair.conf` | `/home/app/loopthd/s122` → `/home/app/ship_s146` |

`dsp4_boot.py`, `dsp4_buildcfg.py` and `dsp4_checkchip.py` on the unit are
already md5-identical to this repo's and do not move.

---

## 2. The images

Four arms, one tree, one toolchain (CCES 3.0.3, `ADSP-21564`), each a full
`./build.sh all`, ~2 min 09 s each.

| arm | flags over `shipping.config` | in the window? |
|---|---|---|
| **A** `build_s146_bq0` | none | **YES** |
| B `build_s146_bq1` | `DSP4_C2_BQ_GRAPH=1` | **NO — staged for PW's signature** |
| C `build_s146_tn` | `DSP4_TEST_NODES=1` | **NO — factory-test-v3 candidate** |
| D `build_s146_rta` | `DSP4_RTA=1 DSP4_CUE=1` | **NO — bench row 11 only** |

`DSP4_RTA=1` alone does not build (`dsp_block.h`: *"DSP4_RTA reads the cue
bus since S65: build with DSP4_CUE=1"*), which is why arm D carries both —
the same pair S144 used, and the arm that caught S144-6.

### 2.1 Provenance, four ways

1. `main` at `24cb19ff2944f8a63de2d7104d1951656aa08f6d`, working tree clean.
2. Source fingerprint
   `b0ebdd705406c6819aeb1c923a223eea89fbc68d4605e55d28219bc3a81dee29`
   (sha256 over every file under `MW/D32/DSP/SHARC/src`, sorted).
3. `./check-sharc-codegen-drift.sh`: **757 generated, 0 differ, 0 absent** —
   the tree IS its generator's output.
4. **The build is byte-deterministic, and it reproduces an image already on
   the unit.** Arm A was built **four** times this session and arms B, C
   and D twice each; every `.ldr` came out md5-identical, and
   `build-images.sh` re-ran all four end to end reporting *"every arm built
   reproduces its recorded image byte for byte"*. And arm C's `chip1.ldr` is
   **`7f226919a5d181410c3804d92678da19`** — byte-for-byte the chip-1 image
   of factory-test-v2 staged at `/home/app/loopthd/s122`, built weeks ago
   from a different tree state.

That fourth point is S131's stale-source trap answered before it can spring,
and it carries a second fact for free: **chip 1 is untouched by the whole of
S142–S145.** Every one of those sessions is chip 2, and the reproduction
proves it against the part's own image rather than against a diff.

### 2.2 Artefacts

| arm | file | bytes | md5 |
|---|---|--:|---|
| **A** | `chip1.ldr` | 426,464 | `1be74e042cff134c7085dfb08dade517` |
| **A** | `chip2.ldr` | 408,412 | `2bddaa05367887eb2a349cde7b3d5055` |
| **A** | `chip1.sym.json` | 216,923 | `bc796228028f595636020b51d454590c` |
| **A** | `chip2.sym.json` | 159,996 | `bf7f48d105a094738138a3f7375415cd` |
| B | `chip1.ldr` / `chip2.ldr` | 426,464 / 450,008 | `6d7b86ec…` / `e76d2dc8…` |
| C | `chip1.ldr` / `chip2.ldr` | 433,508 / 409,972 | `7f226919…` / `d97645bf…` |
| D | `chip1.ldr` / `chip2.ldr` | 435,432 / 408,900 | `a026897f…` / `ebf2fea4…` |

Build-configuration triples, from `tools/dsp/cfg_words.py`:

| arm | `DIAG_BUILD_CFG` | `DIAG_BUILD_CFG2` | `DIAG_BUILD_CFG3` |
|---|---|---|---|
| **A** | `0xCF45FF10` | `0xE2018E6F` | `0xC47C0FA6` |
| B | `0xCF45FF10` | **`0xE2019E6F`** | `0xC47C0FA6` |

One bit apart, word 2 bit 12 — the only thing on the wire that tells arm A
from arm B, and the runbook's §6 reads it. Arm B's **chip 1** differs from
arm A's too, although the switch is a chip-2 switch: the configuration word
is compiled into both images so the part can say what it is carrying.

`.ldr` files are not committed — nothing in this repo has ever tracked a
`.dxe`/`.ldr`/`.doj`. `MW/D24/DSP/s146/build-images.sh` rebuilds any arm and
**refuses** an arm whose md5 is not the one priced here; run with no
argument it rebuilt and gated all four, and reported *"every arm built
reproduces its recorded image byte for byte"*.

### 2.3 Capacity and delay memory, re-priced for these exact images

Memory is exact, read out of these images' own linker maps:

| pool | chip 1 (A/B/C) | chip 2 **A** | chip 2 B | chip 2 C | chip 2 D | limit |
|---|--:|--:|--:|--:|--:|--:|
| code | 181,490 — 69.2 % | 173,168 — **66.1 %** | 186,382 — 71.1 % | 174,650 — 66.6 % | 173,240 — 66.1 % | 262,144 B |
| DM + stack | 309,612 — 82.5 % | 299,884 — **79.9 %** | 328,268 — 87.5 % | 299,964 — 79.9 % | 300,300 — 80.0 % | 375,264 B |
| delay lines | 506,880 — 24.5 % | 1,886,112 — **91.0 %** | 1,886,112 | 1,886,112 | 1,886,112 | 2,072,576 B |

Chip 2's delay pool is **91.0 %, 186,464 bytes free**, over
`dsp_memreport`'s 90 % warn line, and identical on every arm —
`DSP4_C2_BQ_GRAPH` and `DSP4_TEST_NODES` buy code and DM, never delay. This
reproduces S144's table to the byte from the images rather than from a
prediction. Arm D is the only arm that moves chip 1 (code 70.3 %, DM
84.1 %), also reproducing S144's RTA figures exactly.

**Taking arm B later costs chip 2 +13,214 bytes of code and +28,384 bytes of
DM**, leaving 46,996 DM bytes free. It fits. The number is recorded so the
signature is made against it.

SPI surface, exact, from the map the window installs:

| | unit today (`.19.3`) | after (`.28.4`) |
|---|--:|--:|
| addressed cells, chip 1 / chip 2 | 2,594 / 1,395 | **2,498 / 1,302** |
| distinct SPI words, chip 1 / chip 2 | 2,258 / 1,184 | **2,162 / 1,114** |
| distinct nodes addressed, chip 1 / chip 2 | — | **245 / 142** |

Node census after the four config words gate the superset: **544 of 724
nodes run, 180 gated off.**

**Cycles are not re-measured and cannot be desk-side.** The landing figure
stays S142–S144's construction — **≈ 91.7 % of chip 2's 327,680
cycles/block**, block 16, 983.04 MHz, driven, six Echoes — built from S86's
measured 84.47 % baseline plus +2.69 / +0.08 / +2.26 / +1.04 / +1.19. **It
has never been measured on a part**, the boot-to-boot spread on that row is
0.53 points, and it is bench row 3.

### 2.4 The dry run

Off-target, desk-side, nothing loaded:

```
dsp4_boot.py --dir build_s146_bq0 --dry-run
  chip 1: chip1.ldr 426464 B -> 427008 B padded (417 x 1024), CS GPIO6,  RDY GPIO8
  chip 2: chip2.ldr 408412 B -> 408576 B padded (399 x 1024), CS GPIO24, RDY GPIO12
  reset: GPIO16 pulsed low, 0.500s settle
```

Both streams passed `ldr_stream.py check` inside the build (*"8 blocks, no
mid-stream fill blocks"*) and the elfloader entry was verified at `0x90004`.

Gates re-run on the tree the images came from, all green:

| gate | result |
|---|---|
| `check-sharc-codegen-drift.sh` | 757 / **0 differ** |
| `product_fit.py --check-masks` | D24 `CFG_MTX_MASK 0x00000000` **OK**, all four products OK |
| `landed-d24.json` vs `MW/D24/MX/_matrix.csv` | **3,800 cells, 0 mismatches** on all four Dsp columns |
| `landed_map.py --json` determinism | same md5 on two runs |
| `build-images.sh` (all four arms rebuilt and md5-gated) | **every arm reproduces byte for byte** |

---

## 3. What the runbook says, in one paragraph

Stop `matrix-app`, AN_EN low, take five backups. Build arm A on the hub and
gate it on md5. Regenerate `landed-d24.json` and gate it on md5 and pin.
Stage the four image files into a NEW directory `/home/app/ship_s146` — the
old pair is never overwritten, which is what makes rollback one line.
Overwrite `landed-d24.json`, `dsp4_config.py` and `input_patch.json` in
`/home/app/dspboot` (backups first). Repoint `pair.conf`. Pin handback —
including **CS_M GPIO27 DRIVEN high**, not pulled — then boot and configure
**twice**. Verify eight things before any cable moves. Then the app, if the
hub is taking it, AFTER the boot, because starting `matrix-app` raises
AN_EN and a boot with the rails up is the ordering violation `boot_pair()`
refuses.

**Rollback is whole-set and cheap.** The SHARCs have no boot flash — they
are SPI slave-booted every session — so there is no flash to undo. Restore
four files from their `.bak-s146-pre` copies, point `pair.conf` back at
`/home/app/loopthd/s122`, boot again. Never piecemeal: a `landed-d24.json`
from one contract with an image from another does not error, it reads
plausible zeros.

Twelve bench rows are queued in PW's order (S144 §7, which already folds
S143's four in at the front), each with its pass criterion, the panel name
PW will use and the cell's new DSP address.

---

## 4. Findings

**🔴 S146-1 — `product_fit.py`'s capacity table is not this graph's, and its
code-pool line is measurably stale.** Its anchors are S27/S80 measured rows,
all from before S142, and `CODE_USED_C1`/`CODE_USED_C2` are hardcoded at
180,954 / 164,168 from S26/S27 — **536 and 9,000 bytes behind the images
this tree now builds** (181,490 / 173,168). The census and `--check-masks`
halves are correct and were used; the percentage table must not be read as a
prediction for the new graph. This is the S8-2 shape one instrument along:
a tool agreeing with itself while describing last month's build.

**🔴 S146-2 — the unit's DSP address map is five contract tags stale, and a
stale one cannot announce itself.** `/home/app/dspboot/landed-d24.json` is
pinned `defs-v2026.09.19.3` (3,989 cells) against the repo's `.28.4` (3,800).
357 cells it still resolves no longer exist and 40 have moved. A
`landed-d24.json` lookup that succeeds is indistinguishable from one that is
right, so **any bench reading taken on MW-D24-2 since 2026-09-19 through a
cell in those two sets is suspect** — in particular anything touching
`MainCtr*`/`MainSub*` (the 40 that moved) or `Chan*Matrix*`/group surface
(the 357 that went). The window fixes it; the readings already taken are not
retroactively fixed and should be re-taken if they mattered.

**🔴 S146-3 — the accept manifest's signed shipping triple predates
`DSP4_TX_DEFER=2`.** `MW/D24/DSP/accept/manifest.json` `dsp.build_cfg` and
`tools/pi/d24_selftest.py`'s `SIGNED_TRIPLE` both record
`0xCF45FF10 / 0xE2018E6F / 0xC47C0F26`, but today's `shipping.config`
computes `…/0xC47C0FA6` — word 3 bit 7, which is `DSP4_TX_DEFER` (0 → 2, the
S-era DAC-fold fix). `SIGNED_TRIPLE` is only a reference constant today
(nothing gates on it, `_check_factory_image` compares against the
factory-test triple instead), so nothing is broken — but the signed record
says the shipping build is a build this tree no longer produces, and the
next thing to read it will be wrong. Owed: a re-signature, or the record
brought forward with the reason.

**🔴 S146-4 — republishing the pack is a THREE-part change and must be its
own window.** The app's `DspApply` reads DSP addresses only from the
published matrix; the unit's pack carries **zero** of them (0 of 5,767) and
`dspWriteEnable` is false. Republishing from this repo's `_matrix.csv` would
hand it 3,800 addresses for the first time AND add six `Ramp*` columns the
deployed pack does not have (38 columns against 32). None of it is needed
for the graph. Recommend: after the graph is proven at the bench, pack +
`dspWriteEnable` together, with their own verification.

**🔴 S146-5 — the automated factory self-test set will report NO DATA on
every DSP-touching row after the switch, by design.**
`d24_selftest.py::_check_factory_image()` asserts the factory-test-v2 triple
AND both `.ldr` md5s on every DSP-dependent press; arm A is neither. Handling
is in the runbook (§8.2): run the automated set BEFORE the switch, verify
after it with §6 plus PW's rows, and adopt arm C as factory-test-v3 in its
own change — chip 1 byte-identical to v2, chip 2 carrying the new graph,
exactly the shape of the v1→v2 move. Adopting it edits a signed record and
`d24_selftest.py`'s pinned md5s together, which is PW's call, not a
side-effect of a switch window.

---

## 5. State left behind

`main`, one commit: this report, the runbook, the rebuild script, the
findings and the tasks.md status. The four build directories are untracked
and stay that way.

**Nothing is queued on the unit and nothing on it was changed.** The window
itself, and all twelve bench rows, are for PW.

Closing witness, read at the end of the session and identical to the
opening one in every value:

```
26: op -- pd | lo          GPIO26 (AN_EN)  — output, low
27: ip    pd | lo          GPIO27 (CS_M)   — input, low, exactly as found
matrix-app active          d24-testui inactive
/home/app/app                          e62eec885f692e891a88085e510449c6
/home/app/dspboot/landed-d24.json      c5ec5357488e3c24e1520542dbf37a83
/home/app/dspboot/dsp4_config.py       d92ac7b97dfa6a46c7271ce6f4a44bdc
/home/app/config/_matrix.mxc           011636d0b1442c528561009fd3c5d13d
/home/app/selftest/pair.conf           /home/app/loopthd/s122
/home/app/loopthd/s122/chip1.ldr       7f226919a5d181410c3804d92678da19
/home/app/loopthd/s122/chip2.ldr       9e8a1a9edf19a90ce7ac3df1586c00f6
/home/app/ship_s146                    does not exist
```
