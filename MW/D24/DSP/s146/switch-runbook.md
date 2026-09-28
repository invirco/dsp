provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S146 runbook — putting the S142–S145 DSP graph on MW-D24-2

**Desk only. Nothing in this document was executed against the unit.** S146
built the images, priced them against their own map files, dry-ran the boot
path off-target and read the unit READ-ONLY (md5s, versions, configs, GPIO
state). No flash, no DSP load, no app deploy, no write of any kind reached
MW-D24-2; AN_EN (GPIO26) was `op pd | lo` before and after, CS_M (GPIO27)
`ip pd | lo`, `matrix-app` active, `d24-testui` inactive — all exactly as
S145 left them.

**The window itself is a later session, with PW.** Read this whole document
before starting it.

This is the S131-shaped document one subsystem along. S131 switched the
MATRIX GENERATION (the app's pack and the three panel MCUs); this switches
the DSP GRAPH (the two SHARC images and the host-side DSP contract). They
are independent: the generation does not move here, which is what makes
this window small.

---

## 0. The state this assumes

MW-D24-2, read live 2026-09-28 20:3x BST, read-only:

| what | value | how it was read |
|---|---|---|
| app | `e62eec885f692e891a88085e510449c6` (mx26 `e62eec88`) | `md5sum /home/app/app` |
| pack `_matrix.mxc` | md5 `011636d0b1442c528561009fd3c5d13d`, sha256 `44cb57a8946d3dbc…` | `md5sum`, then unpacked desk-side |
| matrix generation | `46109e9fb812` — 5,767 cells, **every `MxAdd` byte-identical to this repo's `MW/D24/MX/_matrix.csv`** | unpacked the pack, diffed all 5,767 rows |
| H1S1 / H1S3 / H1S4 | on disk at `/home/app/firmware/`, S131's set | `ls -la` |
| MH1 | the hub's PANEL_DIM build (`MH1-dimset`) | S145 record, not re-read |
| DSP pair, staged | `/home/app/loopthd/s122` — **factory-test-v2**, chip1 `7f226919a5d181410c3804d92678da19`, chip2 `9e8a1a9edf19a90ce7ac3df1586c00f6`, build-cfg `0xCF45FF10 / 0xE3018E6F / 0xC47C0FA6` (`DSP4_TEST_NODES=1`) | `md5sum`; the triple from `MW/D24/DSP/accept/manifest.json`, NOT re-read off the part (that needs SPI, which this dispatch forbids) |
| `pair.conf` | `/home/app/loopthd/s122` | `cat /home/app/selftest/pair.conf` |
| last DSP boot | 2026-09-28 11:41:51Z, from `/home/app/s90` (a byte-identical copy of the same factory-test-v2 pair) | newest `dsp4_boot.py` row across every `bootlog.csv` on the unit |
| CM4 booted | 2026-09-28 15:20:57 local (= 14:20Z) — **after** that last DSP boot | `uptime -s`, cross-checked against `uptime`'s "up 5:11" at 20:32 local. `who -b` says 13:54 and is not believed: it disagrees with both by 1 h 26 m and is a stale `utmp` line |
| `dspWriteEnable` | **false** | the app's own boot log: `Boot.RunDspApply() - dspWriteEnable=false: DSP parameter link not opened, no node state written` |

Two consequences of that table, and they set the shape of the whole window:

1. **The pair on the unit is not a shipping image at all — it is the
   FACTORY-TEST image.** It is the `DSP4_TEST_NODES=1` pair the whole
   automated self-test set has run on since the S116 ruling. So "the
   pre-S142 image" is factory-test-v2, and the switch replaces a test
   image with a shipping one. §8 says what that costs.
2. **The SHARCs have no boot flash.** They are SPI slave-booted by the Pi
   every session (`dsp4_boot.py`, decision D1). **There is no "flash" to
   roll back** — a DSP rollback is re-pointing `pair.conf` and booting
   again, which is why this window's riskiest steps are the host-side
   files, not the images.
   *What the parts are actually holding right now was not established:*
   no `dsp4_boot.py` has run since the CM4 rebooted at 15:20:57, and
   whether the pair survived that reboot needs an SPI read, which this
   dispatch forbids. It does not matter for the window — step 6 boots
   them either way — but do not assume the pair is up when the window
   opens.

---

## 1. What moves in the window, exactly

### 1.1 Moves

| # | file | from → to | why |
|---|---|---|---|
| 1 | `chip1.ldr` | new stage `/home/app/ship_s146/` | the new graph (chip 1 is unchanged by S142–S145, but the shipping arm differs from the staged test arm — see §2.2) |
| 2 | `chip2.ldr` | new stage | the new graph: stereo main bus, Centre/Woof, phones + monitor, anti-feedback, group→aux crosspoints |
| 3 | `chip1.sym.json` | new stage | symbol map for image 1. A stale map does not error — it peeks as plausible zeros |
| 4 | `chip2.sym.json` | new stage | symbol map for image 2 |
| 5 | `/home/app/dspboot/landed-d24.json` | **overwritten in place** | the cell → DSP SPI address map every bench tool resolves by name. The unit's copy is pinned `defs-v2026.09.19.3`; the new one is `.28.4` |
| 6 | `/home/app/dspboot/dsp4_config.py` | **overwritten in place** | `CFG_MTX_MASK` for D24 goes `0x3` → `0x0` (S143 item 3a). Nothing else in the file changed |
| 7 | `/home/app/dspboot/input_patch.json` | **overwritten in place** | contract tag only: `defs-v2026.09.24.2` → `defs-v2026.09.28.4`. The patch itself is byte-identical |
| 8 | `/home/app/selftest/pair.conf` | **overwritten in place** | repoint from `/home/app/loopthd/s122` to `/home/app/ship_s146` |
| 9 | `/home/app/app` | hub builds and deploys | mx26 `main` HEAD `1d22bae`+ — it labels the patch loop's NO SIGNAL button (S145). Same generation, no DSP consequence |

Files 1–4 go into a **new** directory. Nothing overwrites the existing
staged pair, so the old pair survives the window untouched and rollback
costs one `pair.conf` line and one boot.

### 1.2 Does NOT move, and why

**The matrix pack `_matrix.mxc` does not move.** This is the question the
dispatch asked to settle, and it settles in the pack's favour — but not for
the reason S45 gave, because the app has grown a DSP writer since.

- The app's ONLY source of DSP addresses is the published matrix's
  `DspSpi` / `DspPage` / `DspAdd` / `DspAddHex` columns
  (mx26 `src/sw/app/Services/Dsp/DspAddressMap.cs`, in as many words:
  *"This is deliberately the app's ONLY source of DSP addresses… the app
  never reads dsp.csv, never computes a stride of its own, and never
  carries a second copy"*). `DspApply` then writes each addressed cell as
  it changes.
- **On the unit's pack every one of those columns is empty — 0 of 5,767
  rows carries a DSP address.** Verified desk-side by unpacking the unit's
  own `_matrix.mxc`. This repo's `MW/D24/MX/_matrix.csv` carries 3,800.
- And `DspApply` is not armed anyway: `dspWriteEnable=false`, the default,
  witnessed in the unit's boot log.

So the pack is not a prerequisite for the new graph: the bench tools reach
the DSP through `landed-d24.json`, not through the pack, and the app reaches
it not at all. **Republishing the pack is a separate decision with its own
consequences** — it would hand `DspApply` 3,800 addresses for the first time
AND add six `Ramp*` columns the deployed pack does not have (this repo's
header is 38 columns, the unit's 32). Arming a writer and changing ramp
metadata in the same window as a new audio graph is three changes wearing
one coat. §9 records it for PW rather than doing it here.

**The panel MCUs H1S1 / H1S3 / H1S4 do not move.** They carry `matrix.h`,
which is `#define <CellName> <MxAdd>` and nothing else. The generation is
`46109e9fb812` on both sides and every one of the 5,767 `MxAdd` values in
the unit's pack is byte-identical to this repo's `_matrix.csv` — checked
row by row, 0 differences. No panel MCU has any knowledge of a DSP address,
a DSP node or a TDM slot.

**MH1 does not move.** It is the flash router: it takes a `.shex`, reads the
socket id out of the header record and drives `S_Boot[]`. It is not in the
DSP path at all.

**The LOGIC CPLD does not move.** The shipping bitstream is `d02d83b3cc22`.
The new graph writes DAC_09, DAC_10, DAC_11, DAC_12, DAC_14, DAC_15 and
DAC_16 — **every one of them already exists in `shared/dsp4-logic/slot-map.csv`
at `scope=BOTH`, on line `B_O1` slots 0–7**, and that file has not changed
since S109 (2026-09-25), before S142. The CPLD carries a fixed TDM slot map;
the graph changed which node writes an existing slot, which the CPLD cannot
see.

---

## 2. The images

### 2.1 Four arms were built; ONE of them ships

All four from the same tree, same toolchain (CCES 3.0.3, `ADSP-21564`,
`easm21k`/`cc21k`/`linker`/`elfloader`), same `shipping.config`, each a full
`./build.sh all` into its own directory. ~2 min 09 s per arm.

| arm | build | what it is | in this window? |
|---|---|---|---|
| **A** | `build_s146_bq0` | `shipping.config` as it stands, `DSP4_C2_BQ_GRAPH=0` | **YES — this is the window's image** |
| **B** | `build_s146_bq1` | A + `DSP4_C2_BQ_GRAPH=1` | **NO. NOT FOR THIS WINDOW.** Built now so PW's signature costs no rebuild |
| **C** | `build_s146_tn` | A + `DSP4_TEST_NODES=1` | **NO.** The factory-test-v3 candidate — see §8.2 |
| **D** | `build_s146_rta` | A + `DSP4_RTA=1 DSP4_CUE=1` | **NO.** Bench instrument for row 11 only — see §7 |

`DSP4_RTA=1` alone does not build: `dsp_block.h` stops it with *"DSP4_RTA
reads the cue bus since S65: build with DSP4_CUE=1"*. Both are needed, and
that is the pair S144 used.

### 2.2 The artefacts, and their provenance

Tree: `main` at **`24cb19ff2944f8a63de2d7104d1951656aa08f6d`**, working tree
clean (`git status --porcelain` empty but for the untracked build
directories). Source tree fingerprint:

```
find MW/D32/DSP/SHARC/src -type f | LC_ALL=C sort | xargs sha256sum | sha256sum
  b0ebdd705406c6819aeb1c923a223eea89fbc68d4605e55d28219bc3a81dee29
```

`./check-sharc-codegen-drift.sh`: **757 generated / 0 differ / 0 absent /
53 hand-written** — the tree IS its generator's output, so the images are
the contract's own images and not a tree that has drifted away from it.

**The build is byte-deterministic.** Arm A was built **four** times this
session (two separate directories, then twice more through
`build-images.sh`) and every `.ldr` came out md5-identical; arms B, C and D
were each built twice with the same result. `build-images.sh` re-ran all
four end to end and reported *"every arm built reproduces its recorded
image byte for byte"*.

**And it reproduces an image that is already on the unit.** Arm C's
`chip1.ldr` is **`7f226919a5d181410c3804d92678da19`** — byte-for-byte the
chip-1 image of factory-test-v2 staged at `/home/app/loopthd/s122`, built
weeks ago on a different tree state. That is the S131 stale-source trap
answered before it can be sprung: the toolchain reproduces, and chip 1 is
untouched by the whole of S142–S145 (every one of those sessions is chip 2).

| arm | file | bytes | md5 |
|---|---|--:|---|
| **A** | `chip1.ldr` | 426,464 | `1be74e042cff134c7085dfb08dade517` |
| **A** | `chip2.ldr` | 408,412 | `2bddaa05367887eb2a349cde7b3d5055` |
| **A** | `chip1.sym.json` | 216,923 | `bc796228028f595636020b51d454590c` |
| **A** | `chip2.sym.json` | 159,996 | `bf7f48d105a094738138a3f7375415cd` |
| A | `chip1.dxe` | 894,932 | `d7fe6e162963583911d50ecbcb8b5465` |
| A | `chip2.dxe` | 760,684 | `7c9b9581c22133552a2a6504707f94c3` |
| B | `chip1.ldr` | 426,464 | `6d7b86ec69778900ce63b9eb79c144ea` |
| B | `chip2.ldr` | 450,008 | `e76d2dc8463292a2ba2f6b9172cb6be5` |
| B | `chip2.sym.json` | 163,185 | `353a294505418f605a16bac3fd16e796` |
| C | `chip1.ldr` | 433,508 | `7f226919a5d181410c3804d92678da19` |
| C | `chip2.ldr` | 409,972 | `d97645bfb800290b8f998924d939361c` |
| C | `chip2.sym.json` | 160,511 | `d101bec222b46c93aaf23245cbdb0379` |
| D | `chip1.ldr` | 435,432 | `a026897ff6fd33654733f85c077599d6` |
| D | `chip2.ldr` | 408,900 | `ebf2fea4cca2f740cd560b1155134cc3` |

Arm B's chip 1 differs from arm A's although `DSP4_C2_BQ_GRAPH` is a chip-2
switch: the build-configuration word is compiled into BOTH images so the
part can say which arm it is carrying, and that word moves. Expected, and
it is the mechanism §6 uses to tell the arms apart on the part.

**`.ldr` files are not committed.** Nothing in this repo has ever tracked a
`.dxe`/`.ldr`/`.doj`, and this does not start. The images are reproduced at
execution time by the recipe in §4 step 1 and gated on the md5s above; the
tree hash and the drift gate are what make that safe.

**The build-configuration triple each arm must read back on the part**
(`tools/dsp/cfg_words.py`, which computes it from the config file and
`build.sh`'s own defaults rather than from a second copy of the field list):

| arm | `DIAG_BUILD_CFG` | `DIAG_BUILD_CFG2` | `DIAG_BUILD_CFG3` |
|---|---|---|---|
| **A (ships)** | `0xCF45FF10` | `0xE2018E6F` | `0xC47C0FA6` |
| B | `0xCF45FF10` | **`0xE2019E6F`** | `0xC47C0FA6` |

One bit apart, in word 2 bit 12. That is the only thing on the wire that
tells arm A from arm B, so §6 reads it.

### 2.3 Capacity and delay memory, re-priced for these exact images

**Memory is exact** — read out of these images' own linker map files by
`tools/dsp/dsp_memreport.py`, not carried from a prediction:

| pool | chip 1, **arms A/B/C** | chip 2, **arm A (ships)** | chip 2, arm B | chip 2, arm C | chip 2, arm D | limit |
|---|--:|--:|--:|--:|--:|--:|
| code (VISA SW) | 181,490 — **69.2 %** | 173,168 — **66.1 %** | 186,382 — 71.1 % | 174,650 — 66.6 % | 173,240 — 66.1 % | 262,144 B |
| DM data + stack | 309,612 — **82.5 %** | 299,884 — **79.9 %** | 328,268 — 87.5 % | 299,964 — 79.9 % | 300,300 — 80.0 % | 375,264 B |
| delay lines | 506,880 — **24.5 %** | 1,886,112 — **91.0 %** | 1,886,112 — 91.0 % | 1,886,112 — 91.0 % | 1,886,112 — 91.0 % | 2,072,576 B |
| IVT (NW code) | 128 — 49.2 % | 128 — 49.2 % | — | — | — | 260 B (fixed) |

Arm D is the only arm that moves **chip 1**: code 181,490 → 184,378
(69.2 → 70.3 %) and DM 309,612 → 315,692 (82.5 → **84.1 %**), because the
1/3-octave filterbank and the ring metric live there. It still fits, and it
reproduces S144's own RTA figures exactly.

Chip 2's delay pool is at **91.0 %, 186,464 bytes free**, over
`dsp_memreport`'s own 90 % warn line, and the tool says so on every run.
This reproduces S144's table to the byte. It is the same on all three arms
— `DSP4_C2_BQ_GRAPH` and `DSP4_TEST_NODES` buy code and DM, never delay.
It is the first image that asks for 1,886,112 of 2,072,576 bytes and that
is bench row 12.

Taking arm B in a later window costs chip 2 **+13,214 bytes of code
(66.1 → 71.1 %) and +28,384 bytes of DM (79.9 → 87.5 %)**. It fits, with
46,996 DM bytes to spare, but it is not free and the number is here so the
signature is made against it.

**SPI surface, exact**, from the landed map the window installs:

| | unit today (`.19.3`) | after (`.28.4`) |
|---|--:|--:|
| addressed cells, chip 1 | 2,594 | **2,498** |
| addressed cells, chip 2 | 1,395 | **1,302** |
| distinct SPI words, chip 1 | 2,258 | **2,162** |
| distinct SPI words, chip 2 | 1,184 | **1,114** |
| distinct nodes addressed, chip 1 / chip 2 | — | **245 / 142** |

Node census for D24 after the four config words gate the superset
(`tools/dsp/product_fit.py --census`): **544 nodes run, 180 gated off**, of
724 in the graph.

**Cycles are NOT re-measured here and cannot be.** The percentages in
S142/S143/S144 are constructed — counted from emitted instructions — and
the landing figure is **≈ 91.7 % of chip 2's 327,680 cycles/block** at block
16, 983.04 MHz, driven, six Echoes, from S86's measured 84.47 % baseline
plus S143 (+2.69 % stereo main bus, +0.08 % group crosspoints) and S144
(+2.26 % Centre/Woof, +1.04 % phones, +1.19 % anti-feedback). **Nothing has
ever measured it on a part.** That is bench row 3 and it is the row that
decides whether this graph ships.

Two cautions that belong next to that number:

- **The reverb regime does not fit and is not expected to.** Six FX engines
  at Type 3 is +16.44 measured points over the Echo default's +1.53, which
  puts chip 2 at ≈ 106.6 %. Arm B is what buys that back (~17.4 points), and
  that is the case for the signature, not for this window.
- **`tools/dsp/product_fit.py`'s own percentages are not this graph's.**
  Its anchors are S27/S80 measured rows, all from before S142, and its
  `CODE_USED_C1` / `CODE_USED_C2` constants (180,954 / 164,168) are 536 and
  9,000 bytes behind the images this tree now builds. Use it for the census
  and the masks; do not read its capacity table as a prediction for the new
  graph. Recorded as S146-1.

### 2.4 The dry run

Off-target, desk-side, nothing loaded to any part:

```
python3 tools/pi/dsp4_boot.py --dir MW/D32/DSP/SHARC/build_s146_bq0 --dry-run
  chip 1: chip1.ldr 426464 B -> 427008 B padded (417 x 1024), CS GPIO6,  RDY GPIO8
  chip 2: chip2.ldr 408412 B -> 408576 B padded (399 x 1024), CS GPIO24, RDY GPIO12
  reset: GPIO16 pulsed low, 0.500s settle
  (2 chip(s), 10000000 Hz, SPI mode 1, 2 attempt(s) per chip)
```

Both streams also passed `tools/dsp/ldr_stream.py check` inside the build —
*"8 blocks, no mid-stream fill blocks"* on each — and the loader's entry
address was verified at `0x90004` (the RSTI vector) from the elfloader log.

Contract gates re-run this session, all green on the tree the images came
from:

| gate | result |
|---|---|
| `check-sharc-codegen-drift.sh` | 757 generated, **0 differ** |
| `tools/dsp/product_fit.py --check-masks` | every product's `CFG_MTX_MASK` equals the population of the matrix buses its own cells address — D24 `0x00000000` **OK** |
| `landed-d24.json` vs `MW/D24/MX/_matrix.csv` | **3,800 cells checked, 0 mismatches** on `DspSpi`/`DspPage`/`DspAdd`/`DspAddHex` |
| `landed_map.py --json` determinism | same md5 on two runs |

---

## 3. Backups — take ALL of these before touching anything

| what | path on unit | back up as | value read 2026-09-28 |
|---|---|---|---|
| DSP address map | `/home/app/dspboot/landed-d24.json` | `…json.bak-s146-pre` | md5 `c5ec5357488e3c24e1520542dbf37a83`, pin `defs-v2026.09.19.3`, 3,989 cells |
| boot config | `/home/app/dspboot/dsp4_config.py` | `…py.bak-s146-pre` | md5 `d92ac7b97dfa6a46c7271ce6f4a44bdc` |
| input patch | `/home/app/dspboot/input_patch.json` | `…json.bak-s146-pre` | md5 `b95cd6834fa4639a18e2e3b533652884` |
| pair pointer | `/home/app/selftest/pair.conf` | `…conf.bak-s146-pre` | one line: `/home/app/loopthd/s122` |
| app binary | `/home/app/app` | `/home/app/app.bak-s146-pre` | md5 `e62eec885f692e891a88085e510449c6` |

Take all five in one go, up front, before step 1 — not each one as its step
arrives. Stop `matrix-app` first (§4's preconditions): these are the first
writes of the window and they should land on a quiet unit.

```
ssh app@192.168.1.219 'set -e
  cd /home/app/dspboot
  for f in landed-d24.json dsp4_config.py input_patch.json; do cp -p "$f" "$f.bak-s146-pre"; done
  cp -p /home/app/selftest/pair.conf /home/app/selftest/pair.conf.bak-s146-pre
  cp -p /home/app/app /home/app/app.bak-s146-pre
  md5sum /home/app/dspboot/*.bak-s146-pre /home/app/app.bak-s146-pre
  cat /home/app/selftest/pair.conf.bak-s146-pre
  md5sum /home/app/loopthd/s122/chip1.ldr /home/app/loopthd/s122/chip2.ldr'
```

**GATE:** every md5 must match the table above, and the old pair must still
read `7f226919…` / `9e8a1a9e…`. Four files, one app binary and two image
checks — under a minute, and it is the whole rollback.

**The old DSP pair needs no backup and must not be moved.** It stays at
`/home/app/loopthd/s122` because the new pair goes to a NEW directory. A
byte-identical second copy is at `/home/app/s90` if the first is ever in
doubt.

Steps 4, 5 and 7 below assume these copies exist and do not re-take them.

---

## 4. Ordered steps

Preconditions, all of them, before step 1:

- `matrix-app` **stopped** for the whole window (`sudo systemctl stop matrix-app`).
- **AN_EN (GPIO26) LOW.** `boot_pair()` refuses outright to boot with the
  rails up, and it is right to: analog last up, first down (PW 09-10).
  `pinctrl set 26 op dl` if it is not. Note that stopping `matrix-app` drops
  AN_EN by itself; check anyway, do not assume.
- No `d24_runall.py` / `d24_selftest.py` running.
- §3's backups taken and verified.

Every command below is run **from the repo root** unless it says otherwise.
`B=MW/D32/DSP/SHARC/build_s146_bq0` throughout.

### Step 1 — Build the images (hub machine, nothing on the unit)

```
./MW/D24/DSP/s146/build-images.sh A
```

That is the whole step: it builds arm A, writes both symbol maps, and
**refuses** the arm if either `.ldr` md5 is not the one this document
priced. By hand it is:

```
cd MW/D32/DSP/SHARC && DSP_BUILD_DIR=$PWD/build_s146_bq0 ./build.sh all && cd -
python3 tools/dsp/map_syms.py $B/chip1.map.xml > $B/chip1.sym.json
python3 tools/dsp/map_syms.py $B/chip2.map.xml > $B/chip2.sym.json
md5sum $B/chip1.ldr $B/chip2.ldr
```

**GATE:** the two md5s must be `1be74e042cff134c7085dfb08dade517` and
`2bddaa05367887eb2a349cde7b3d5055`. If either differs, the tree is not the
tree this document priced — stop, do not "fix it forward". Confirm
`git rev-parse HEAD` is `24cb19ff…` and the tree clean, and re-run
`./check-sharc-codegen-drift.sh`.

Do NOT pass `DSP4_C2_BQ_GRAPH`, `DSP4_RTA`, `DSP4_CUE` or `DSP4_TEST_NODES`
on this command line. Arm A is `shipping.config` untouched.

**Rollback:** N/A — nothing has left the hub.
**Time:** 2 min 09 s measured, plus a few seconds for the symbol maps.

### Step 2 — Regenerate the DSP address map (hub machine)

```
python3 tools/dsp/landed_map.py --product d24 --json /tmp/landed-d24.json
md5sum /tmp/landed-d24.json
```

**GATE:** it must print `3800 cells  sha256 37d6e3038c1a  pin
defs-v2026.09.28.4`, and the file's md5 must be
`5467629309de53d296b5155c29207fd6`.

**Rollback:** N/A.
**Time:** seconds.

### Step 3 — Stage the pair (first thing that touches the unit)

```
ssh app@192.168.1.219 'mkdir -p /home/app/ship_s146 && \
    for f in /home/app/dspboot/*.py; do ln -sfn "$f" /home/app/ship_s146/$(basename "$f"); done && \
    ln -sfn /home/app/dspboot/landed-d24.json  /home/app/ship_s146/landed-d24.json && \
    ln -sfn /home/app/dspboot/input_patch.json /home/app/ship_s146/input_patch.json'
scp $B/chip1.ldr $B/chip2.ldr $B/chip1.sym.json $B/chip2.sym.json \
    app@192.168.1.219:/home/app/ship_s146/
ssh app@192.168.1.219 'md5sum /home/app/ship_s146/chip1.ldr /home/app/ship_s146/chip2.ldr'
```

This is the `s82.sh` pattern verbatim: a session-named stage, never
`~/dspboot` itself. The `.py` symlink loop is how every stage gets the
bench tools, and `landed-d24.json` / `input_patch.json` are **symlinks into
`/home/app/dspboot`, not copies** — which is why step 4's overwrite reaches
this stage automatically and why there is only ever one of each on the unit
to keep straight.

`s82.sh` also `scp`s `dsp4_boot.py` and `dsp4_checkchip.py` into the stage
at this point. **Do not**: both are already md5-identical on the unit
(`7611db7e…` and `dfa4d0e3…`, checked this session) and both are already
symlinked in by the loop above — an `scp` onto a symlink writes THROUGH it
and would silently rewrite `/home/app/dspboot`'s copy. Harmless while the
content matches; a trap the first time it does not.

**GATE:** the md5s read back off the unit must equal step 1's. Read the
unit's own `md5sum`, never the copy tool's word.

**Rollback:** `rm -rf /home/app/ship_s146`. Nothing else has moved and the
old pair is still staged and still pointed at.
**Time:** ~1.2 MB over the bench link; seconds.

### Step 4 — The DSP address map and the boot config (overwrites in place)

(§3's backups are already taken; do not re-take them here — a second `cp`
after the overwrite would back up the NEW file over the old one.)

```
scp /tmp/landed-d24.json          app@192.168.1.219:/home/app/dspboot/landed-d24.json
scp tools/pi/dsp4_config.py       app@192.168.1.219:/home/app/dspboot/dsp4_config.py
scp MW/D24/DSP/input_patch.json   app@192.168.1.219:/home/app/dspboot/input_patch.json
ssh app@192.168.1.219 'md5sum /home/app/dspboot/{landed-d24.json,dsp4_config.py,input_patch.json}'
```

**GATE:** `5467629309de53d296b5155c29207fd6`,
`90b54da64fb7b09d66f9952fcd52a921`, `8134172680c3a9fa52a4ecc80d7a770a`.

This is the step with real consequences and it is worth being plain about
what each file does:

- `landed-d24.json` moves from `defs-v2026.09.19.3` to `.28.4`: **168 cells
  added, 357 removed, 40 moved.** Every one of the 40 is chip 2 and every
  one is the ruled D6/R5 outcome — `MainCtr*`/`MainSub*` leaving the generic
  output strips for the dedicated nodes (`C2_MAIN_OEQ_03→C2_CTR_EQ` 19,
  `OEQ_04→C2_WOOF_EQ` 9, `OLIM_03→C2_CTR_LIM` 4, `OLIM_04→C2_WOOF_LIM` 4,
  `XOVER→C2_WOOF_XOVER` 2, `OUT_03→C2_CTR_FDR` 1, `OUT_04→C2_WOOF_FDR` 1).
  The 357 removed are the `.28.1` block-audit drops (96 chip-1 `Chan*Matrix*`
  on `C1_RTG_*`, 261 chip-2 group/matrix surface) and they are removed on
  the unit's side too — **the unit's map is 5 contract tags stale, not one.**
- `dsp4_config.py` changes exactly one value: D24's `CFG_MTX_MASK`
  `0x00000003 → 0x00000000`. Everything else in the diff is the comment
  explaining it. `product_fit.py --check-masks` confirms 0 is the population
  of the matrix buses D24's own cells address.
- `input_patch.json` changes only its `contract` string. The patch tuple is
  byte-identical, so no input moves.

**Rollback:** `cp -p <file>.bak-s146-pre <file>` for all three. Instant.
**Time:** under a minute.

### Step 5 — Repoint `pair.conf`

```
ssh app@192.168.1.219 'echo /home/app/ship_s146 > /home/app/selftest/pair.conf && \
  cat /home/app/selftest/pair.conf /home/app/selftest/pair.conf.bak-s146-pre'
```

**Rollback:** restore the `.bak-s146-pre` copy — one line, instant.
**Time:** seconds.

### Step 6 — Boot the pair

The pins first, then boot and configure **twice**. The second cycle is not
belt-and-braces: the config commit desyncs the parameter link on the first
pass every time, on every image, and the pair reaches `BOOT_STAGE 7` on the
second.

```
# pin handback — NOT `pinctrl set 6,...,24,... a0`
pinctrl set 7,9,10,11,22,23,25 a0
pinctrl set 6,24 op dh          # CS1/CS2 deasserted
pinctrl set 27 op dh            # CS_M DRIVEN high — a pull is not enough
pinctrl set 8,12 ip pd          # SPI_RDY

cd /home/app/ship_s146
for cycle in 1 2; do
    python3 dsp4_boot.py --dir .
    pinctrl set 6,24 op dh
    python3 dsp4_config.py --product d24 --chip 1
    python3 dsp4_config.py --product d24 --chip 2
done
python3 s89_signbit.py /home/app/ship_s146      # inter-chip link gate
```

**CS_M must be DRIVEN high, not pulled.** A cold CM4 leaves GPIO27 an input
pulled down — which is exactly what it reads right now — and a LOW CS_M
gates the U2 buffer onto the shared MISO, so every read comes back as
plausible zeros while every write still lands. That is the S111 failure and
it looks like a dead part. `ip pu` stopped working on 2026-09-25; `op dh`
is the fix.

`pinctrl set 6,24 op dh` is repeated after each boot deliberately:
`dsp4_boot.py` leaves the selects where the stream left them.

**GATE:** `dsp4_boot.py` must verify `CHIP_ID` on both parts. If chip 2 comes
up reporting `CHIP_ID 1`, both parts loaded `chip1.ldr` — the classic
symptom of GPIO24 handed back to ALT0 (SD0_DAT2) instead of driven high.
Re-check the handback, do not re-boot into the same mistake.

**Rollback:** restore `pair.conf` (step 5) and re-run this step from
`/home/app/loopthd/s122`. The old pair is untouched on disk.
**Time:** a boot pair is ~40 s (the stream itself is ~0.6 s chip 1 /
~0.5 s chip 2 per cycle, measured in the unit's own `bootlog.csv`; the rest
is reset settle and the four config commits).

### Step 7 — The app (hub builds and deploys)

Only if the hub is taking the new app in this window; it is independent of
everything above and can be skipped without affecting the DSP graph.

Build mx26 `main` HEAD (`1d22bae` or later) as
`dotnet publish src/sw/app/app.csproj -c Release -r linux-arm64
--self-contained -p:PublishSingleFile=true`, copy to `/home/app/appUpdate`,
then `sudo systemctl restart matrix-app` — the unit's own `ExecStartPre`
does the atomic rename and runs `validate-app.sh`.

**`matrix-app` starting will raise AN_EN.** Do this AFTER step 6, never
before: a boot with the rails up is the ordering violation `boot_pair()`
refuses, and the analog rails are last up and first down.

**Leave `dspWriteEnable` false.** The app has a DSP writer now and the pack
it will load still carries no DSP addresses, so arming it would do nothing
useful and one thing harmful: it would make the app a second writer to a
link the bench tools are driving. §9.

**Rollback:** `cp /home/app/app.bak-s146-pre /home/app/app && sudo systemctl
restart matrix-app`.
**Time:** the publish is minutes on the hub's own machine; the restart and
validate under 10 s on the unit.

### Step 8 — Verify (§6), then the bench rows (§7)

---

## 5. One-command whole-set rollback

Any step, any time. Nothing in this window is irreversible and nothing
needs a reflash.

```
ssh app@192.168.1.219 'set -e
  cd /home/app/dspboot
  for f in landed-d24.json dsp4_config.py input_patch.json; do
      if [ -f "$f.bak-s146-pre" ]; then cp -p "$f.bak-s146-pre" "$f"; fi
  done
  cp -p /home/app/selftest/pair.conf.bak-s146-pre /home/app/selftest/pair.conf
  if [ -f /home/app/app.bak-s146-pre ]; then cp -p /home/app/app.bak-s146-pre /home/app/app; fi
  md5sum /home/app/dspboot/landed-d24.json /home/app/dspboot/dsp4_config.py \
         /home/app/dspboot/input_patch.json /home/app/app
  cat /home/app/selftest/pair.conf'
```

(`if` blocks rather than `[ -f … ] && cp`: under `set -e` a false test is a
non-zero exit and the restore would stop halfway, which is the one thing a
rollback must never do.)

Then re-boot the OLD pair: step 6's pin handback and boot loop, run from
`/home/app/loopthd/s122`. Then `sudo systemctl restart matrix-app` if the
app was replaced.

**Restore all of it or none of it** — never piecemeal. A `landed-d24.json`
from one contract with an image from another is a tool resolving names to
addresses that image does not have, and it will not error: it will read
plausible zeros. The whole-set restore is the only safe shape.

`/home/app/ship_s146/` can be left in place after a rollback; nothing reads
it once `pair.conf` points elsewhere.

**Expected md5s after a complete rollback:** `c5ec5357488e3c24e1520542dbf37a83`,
`d92ac7b97dfa6a46c7271ce6f4a44bdc`, `b95cd6834fa4639a18e2e3b533652884`,
app `e62eec885f692e891a88085e510449c6`, `pair.conf` =
`/home/app/loopthd/s122`, and the staged pair `7f226919…` / `9e8a1a9e…`.

---

## 6. Post-switch verification, before any audio row

Run all of it before touching a cable. Each line is a gate, not a note.

1. **Both parts are alive and are the right parts.**
   `python3 dsp4_diag.py --chip 1` and `--chip 2` → `MAGIC` starts `0xD5B4`,
   `BOOT_STAGE ≥ 7`, `CHIP_ID` 1 and 2 respectively. A `CHIP_ID 1` on CS2
   means both parts loaded `chip1.ldr` — go back to step 6's handback.
2. **The part is carrying arm A and can prove it.**
   `python3 dsp4_buildcfg.py --expect-shipping` on **both** chips. It must
   read `0xCF45FF10 / 0xE2018E6F / 0xC47C0FA6` and exit 0. A part answering
   `0xE2019E6F` in word 2 is arm B — the wrong image for this window; a
   part answering `0x00000000` at `0xE0EC` is a pre-S80 image entirely.
3. **The staged image is the image that was built.**
   `md5sum /home/app/ship_s146/chip1.ldr /home/app/ship_s146/chip2.ldr` →
   `1be74e04…` / `2bddaa05…`. The triple alone cannot do this job: S124
   proved two graphs can share one set of flags, which is why the md5 is
   the check that matters.
4. **The address map on the unit is the one the images were generated
   from.** `md5sum /home/app/dspboot/landed-d24.json` → `5467629309de…`,
   and its `pin` field reads `defs-v2026.09.28.4`.
5. **The inter-chip link.** `s89_signbit.py /home/app/ship_s146` — exit 0.
6. **The new nodes answer at all.** Read back a handful of cells that did
   not exist or did not have these addresses before, by NAME, with
   `dsp4_apply_strip.py` / `d24_bus_probe.py` (never a literal address):

   | cell (panel name) | chip / page / word |
   |---|---|
   | `Main001Out3Mode001` (Main Out3Mode) | 2 / 1 / 2400 |
   | `MainSub001Src001` (MainSub Src) | 2 / 1 / 2360 |
   | `Mon001PickOff001` (Mon PickOff) | 2 / 1 / 2404 |
   | `Mon001PhonesLevel001` (Mon PhonesLevel) | 2 / 1 / 2409 |
   | `Main001AntiFbLimOn001` (Main AntiFbLimOn) | 2 / 1 / 2357 |
   | `MainCtr001Geq016` (MainCtr Geq 16) | 2 / 1 / 2296 |
   | `MainCtr001EqGain001` (MainCtr EqGain 1) | 2 / 1 / **1324** — was 1530 |

   The last one is the moved-address check: a tool that still resolves it to
   1530 is reading the backed-up map, not the new one.
7. **Nothing on chip 1 moved.** Spot-read `Chan001Gain001` (1/1/0),
   `Chan001Level001` (1/1/80), `Chan001Pan001` (1/1/81). Chip 1's addresses
   are untouched by this window; if one has moved, the wrong map is
   installed.
8. **Record on the gate line:** both `.ldr` md5s, the build-cfg triple off
   each part, `landed-d24.json`'s md5 and pin, the app's md5, and the
   `pair.conf` contents.

Any failure here → §5's whole-set rollback. Do not debug in the window.

---

## 7. The bench rows, in PW's order

Queued, none ever run. Every percentage and every audio claim S142–S145
made is constructed; **not one of them has been measured on a part.** These
twelve are S144 §7 in its own order, which already folds S143's four in at
the front. Panel names are given as PW will use them, with the cell and its
new DSP address beside it so a tool can be pointed at the right word.

Standing preconditions for all of them: arm A booted and verified per §6;
AN_EN raised once, after the last boot of the session, and held; the CPLD
in its shipping personality `d02d83b3cc22` (a loopback personality is for
digital-only work and will not carry these).

**1. The MAIN L/R split.** Tone into one strip, `Chan{n}Pan` hard left, then
hard right, capture both MAIN XLRs — **J57 = MAIN R = DAC_11
(`C2_MAIN_OUT_02`), J56 = MAIN L = DAC_12 (`C2_MAIN_OUT_01`)**. Then pan
centred.
*PASS:* the hard-panned tone appears on one XLR and is at the noise floor on
the other, and the two swap when the pan swaps; centred, both legs within
0.5 dB of each other. Pan is an INDEX, not a fraction — 127 table positions,
`fix(pan*126)` — so 0.0 is hard LEFT, not centre.
*This is the row that closes S142-1: until S143 the main bus was mono and
DAC MAIN R carried stale TX-buffer content.*

**2. The crossover click check.** Live write of `Main CrossoverFreq`
(`Main001CrossoverFreq001`, 2/1/1436) while capturing both MAIN XLRs
through the 576-sample (12 ms) block-rate fade.
*PASS:* no sample-level discontinuity; nothing above the programme's own
peak. **`Main CrossoverOn` (2/1/1438) defaults to 0** (bypass/identity), so
write the on/link switch explicitly first or the split never engages and the
row measures nothing (S144-8).

**3. The driven capacity row — the row that decides the graph.**
`MW/D32/DSP/SHARC/capacity.sh` with `--driven`, on arm A, the shipping
configuration, on the part.
*PASS:* chip 2 average below 100 % of 327,680 cycles/block with a real
margin, `DIAG_BLK_OVERRUN` 0 and `_proc_passes` matching `DIAG_FRAME_COUNT`.
*Expect ≈ 91.7 % on the Echo default* — constructed, never measured, and the
boot-to-boot spread on this row is 0.53 points, so 91.7 % leaves about five
points. **Six Reverbs at Type 3 will NOT fit (≈ 106.6 %) and that is
expected**; it is the case for `DSP4_C2_BQ_GRAPH=1`, not a fault of this
image.
*ABORT if:* chip 2 misses blocks on the Echo default. See §8.1.

**4. The group-send cost.** One group send opened per aux, 11 sources live.
*PASS:* the measured cost of leaving the S23 bypass is inside the +0.34 %
block-rate fold the crosspoints were priced at, less the −0.26 %
`CFG_MTX_MASK` gives back.

**5. The C/LF XLR carries something at all.** Tone into a strip with its
`Chan{n}CtrOn` up; meter **J55 (DAC_14, `C2_OUT3_OUT`)**.
*PASS:* the tone is there. *This is a hardware claim, not a software one* —
the desk says DAC_14, and the desk has been wrong about this hardware
before (`DAC_13` was "Main Out 1" for months and is connected to nothing).
Until now J55 was fed from an aux bus D24 does not declare, so this row has
never passed on any image.

**6. `Main Out3Mode` switches C/LF, click-free.** J55 captured across a live
`Main Out3Mode` (`Main001Out3Mode001`, 2/1/2400) `0 → 1`, with the Centre
bus and the Woof carrying **different** tones so the crossfade is visible.
Then the same for `Mon PickOff` (`Mon001PickOff001`, 2/1/2404) `2 → 0` on
the monitor jacks.
*PASS:* the source changes; the crossfade is monotonic over the 576 samples;
no click on either. `Main Out3Link` (2/1/2401) has two readings and is
unruled (S144-3) — leave it where it is for this row and record what it was.

**7. The monitor jacks carry the monitor; the phone jack carries the
phones.** Four captures: **J53/J54 = DAC_15/16 (`C2_MON_OUT_L/R`)** and
**J10 = DAC_09/10 (`C2_PHN_OUT_L/R`)**, moving `Mon Level1`
(`Mon001Level001`, 2/1/1789), `Mon Level2` (`Mon001Level002`, 2/1/1790) and
`Mon PhonesLevel` (`Mon001PhonesLevel001`, 2/1/2409) independently.
*PASS:* each pair follows its own level and neither follows the other's.
*Neither pair reached a converter before S144, and `Mon Level2` had no
reader at all before S143 — so all four captures are firsts.*

**8. `Main CrossoverOn` engages and disengages the split.** Sweep through the
corner on J56 with `Main001CrossoverOn001` (2/1/1438) at 0, then at 1.
*PASS:* at 0 the HP leg is flat to the bottom of the sweep; at 1 the corner
is where `Main CrossoverFreq` says, at the slope `Main CrossoverSlope`
(2/1/1437) says.

**9. The Woof LPF is the ONLY low-pass in the LF path.** Sweep J55 with
`Main Out3Mode = 1`, `MainSub Src = 0` (2/1/2360), `Main CrossoverLink = 1`
(2/1/1439).
*PASS:* **6 dB down at the corner, not 12**, and LP + HP sum flat against
J56/J57. *This is S144-2's correction under test: taking the main
crossover's LP legs as well as the Woof's own LPF would double-filter, and
12 dB at the corner is the failure signature.*

**10. The anti-feedback notches and the feedback limiter.**
`Main AntiFbNotchFreq/Gain/Q 1–6` (2/1/2338–2343, 2344–2349, 2350–2355)
written and swept on J56/J57. Then `Main AntiFbGain` (2/1/2356) walked up
with `Main AntiFbLimOn` (2/1/2357) at 0 and at 1.
*PASS:* the notch lands where it was written, **both legs identical through
a pan swap** (they are a follower pair, `C2_MAIN_AFB` / `C2_MAIN_AFB_R`),
and with the limiter on, the XLR ceiling holds at **−6 dBFS**
(`fb_lim_db=-6.0`). Repeat on the Centre leg (`MainCtr AntiFb*`,
2/1/2314–2331, node `C2_CTR_AFB`) on J55.
*Whether the ring-out arm/decision logic should live in the DSP rather than
the host is unruled (S144-5); this row measures the DSP half either way.*

**11. The ring metric, on a real ring. — NEEDS ARM D, NOT ARM A.**
Boot `build_s146_rta` (`DSP4_RTA=1 DSP4_CUE=1`), assign the cue to Main,
provoke a deliberate acoustic ring through the monitor speaker, read
`_rta_ring` back.
*PASS:* the saturating count pegs on the ringing band (cap 2,047 blocks =
682 ms) and stays near zero on the others while programme material plays.
**This is a bench-instrument image, and taking it costs two boots.** Lower
AN_EN first (`pinctrl set 26 op dl`) — `boot_pair()` refuses a rails-up
boot, and that applies to swapping arms as much as to the first one — stage
arm D beside arm A, boot it, run the row, then **boot arm A again before
any other row** and raise the rails once more. Note also that the strip
meter latches peaks and decays 6.52 dB/s: read the metric, not the meter.

**12. The delay pool at 91.0 %.** A boot and a soak on arm A with every
delay line allocated — the first image ever to ask for **1,886,112 of
2,072,576 bytes** on chip 2, 186,464 free.
*PASS:* the pair boots to `BOOT_STAGE 7` repeatedly, the soak runs with
`DIAG_BLK_OVERRUN` 0, and no delay line reads another's content. *Run this
before, not after, the audio rows — if the pool does not survive a boot,
nothing below it means anything.*

---

## 8. Risks, gates, abort criteria

### 8.1 Capacity — the only real one

Chip 2 lands at a **constructed** ≈ 91.7 % against a boot-to-boot spread of
0.53 points, on a graph where no cycle figure has ever been measured. If
bench row 3 comes back above ~97 % on the Echo default, or shows any missed
block, **abort the window** (§5) and take it back to the desk. Do not reach
for `DSP4_C2_BQ_GRAPH=1` at the bench to make it fit: that is a signature
PW has not given, and arm B is built and waiting precisely so that the
signature can be a decision rather than a rescue.

### 8.2 The automated factory self-test set stops working on this pair

`d24_selftest.py::_check_factory_image()` asserts that every DSP-touching
press is running **factory-test-v2** — the triple AND both `.ldr` md5s. Arm
A is neither. So after the switch **every DSP-dependent row of the automated
set reports NO DATA "wrong image loaded"**, by design, not by accident.

This is a consequence, not a defect, and it has a clean handling:

- Run the automated set **before** the switch, on the pair that is staged
  today. It is valid there and nothing in this window changes that.
- After the switch, the verification is §6 plus PW's twelve rows, on the
  shipping pair.
- Arm C (`build_s146_tn`, chip1 `7f226919…` — **byte-identical to
  factory-test-v2's chip 1** — chip2 `d97645bf…`) is the factory-test-v3
  candidate: exactly the shape of the v1→v2 move, chip 1 unchanged, chip 2
  carrying the new graph. Adopting it needs `FACTORY_TEST_*` in
  `d24_selftest.py` and `factory_test_image` in `MW/D24/DSP/accept/manifest.json`
  updated together. **Not done here** — the record is signed and moving it
  is PW's, not a side-effect of a switch window. §9.

### 8.3 The unit's DSP contract is five tags stale, not one

`landed-d24.json` on the unit is pinned `defs-v2026.09.19.3`. Anything run
against it today resolves 357 cells that no longer exist and 40 that have
moved — silently, because a `landed-d24.json` lookup that succeeds is
indistinguishable from one that is right. Any bench reading taken on this
unit between 2026-09-19 and this window, through a cell in those two sets,
is suspect. Recorded as **S146-2**.

### 8.4 The delay pool is over its own warn line

91.0 % against a 90 % threshold, with 186,464 bytes free. The tool warns on
every build. This is not a blocker — it is the reason bench row 12 exists
and the reason it runs first. **No further delay line fits on chip 2**
without an LDF rebalance: room for about five more 250 ms mono channels was
the S142 figure and S144 spent four of them.

### 8.5 The stale-source trap

S131 flashed an H1S1 built from a stale tree and regressed the DSP boot. The
answer here is in §2.2 and it is stronger than a warning: the source tree
has a fingerprint, the codegen drift gate says the tree IS its generator's
output, every arm reproduces byte for byte across repeated builds, and arm C
reproduces an image already on the unit. **Step 1's md5 gate
is what enforces it at execution time.** If the md5s do not match, the tree
is not this tree, and no amount of "it built cleanly" substitutes.

### 8.6 Two writers on one link

The app now has a DSP writer (`DspApply`, `SpiDevDspLink`) behind
`dspWriteEnable`, default false and false on this unit. Leave it false for
this window. If it were armed while the bench tools were driving the same
parameter link, both would write the same words with no arbitration, and the
failure would look like parameters that will not stay where they are put.

### 8.7 The signed triple in the accept manifest is stale — but nothing in
this window reads it

`MW/D24/DSP/accept/manifest.json`'s `dsp.build_cfg` and
`tools/pi/d24_selftest.py`'s `SIGNED_TRIPLE` both record
`0xCF45FF10 / 0xE2018E6F / 0xC47C0F26`. Today's `shipping.config` computes
`… / 0xC47C0FA6` — word 3 bit 7 is `DSP4_TX_DEFER`, which went 0 → 2 when
the DAC fold was fixed. So the signed record names a shipping build this
tree no longer produces.

**§6 gate 2 is unaffected and will pass**: `dsp4_buildcfg.py
--expect-shipping` compares against the mirror inside the tool itself, and
`check_shipping_config.sh` confirms that mirror is current (`0xC47C0FA6`).
The unit's copy of `dsp4_buildcfg.py` is md5-identical to this repo's. And
nothing gates on `SIGNED_TRIPLE` — `_check_factory_image()` compares the
factory-test triple instead. So this is a record to correct, not a hazard
to the window. Recorded as **S146-3**; do not "fix" it at the bench by
editing a signed file.

### 8.8 Abort criteria, in one list

Abort and roll back (§5) on any of:

- step 1's `.ldr` md5s do not match §2.2;
- any §6 gate fails — wrong triple, wrong md5, wrong pin, `BOOT_STAGE < 7`,
  `CHIP_ID` wrong on either part, `s89_signbit` non-zero;
- bench row 12: the pair will not boot repeatedly with the pool at 91 %;
- bench row 3: chip 2 misses blocks on the Echo default;
- bench row 1: the MAIN legs do not separate, or do not swap with the pan.

Roll back whole, then take it to the desk. Nothing in this window is worth
debugging live.

---

## 9. Recorded for PW — decisions, not questions

Per the no-dialogs mandate these are recorded here and in `findings.md`,
not asked.

1. **`DSP4_C2_BQ_GRAPH` stays 0 for this window.** Arm B is built, priced
   (chip 2: code 66.1 → 71.1 %, DM 79.9 → 87.5 %, delay unchanged; worth
   ~17.4 points of capacity) and tells itself apart on the part by
   `DIAG_BUILD_CFG2 0xE2019E6F`. It is a signature, and the signature now
   costs no rebuild.
2. **Republishing `_matrix.mxc` is a separate window.** It would hand the
   app's `DspApply` 3,800 DSP addresses for the first time and add six
   `Ramp*` columns the deployed pack does not carry. Neither is needed for
   the graph; both change app behaviour. Recommend: after the graph is
   proven at the bench, pack and `dspWriteEnable` together, with their own
   verification.
3. **factory-test-v3.** Arm C is built and is the right shape. Adopting it
   means editing a signed record (`accept/manifest.json`) and
   `d24_selftest.py`'s pinned md5s; that is PW's call and it should not ride
   along on a switch window.
4. **The aux→aux matrix (S143-2) is still not built** and still needs the
   placement ruling — post-limiter/pre-delay, pre-EQ, or a block-old read.
   It is not in this image and the window does not change that.
5. **`Main Out3Link`'s two readings (S144-3)** and **where the anti-feedback
   ring-out decision should live (S144-5)** are both still open. Rows 6 and
   10 record what was set rather than assuming.
