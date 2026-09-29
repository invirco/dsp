provenance: AI-drafted 2026-09-28, updated 2026-09-29 (S147, S148) — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

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

**UPDATED S150 (2026-09-29): NOT ONE OF THE FOUR MD5s MOVED.** S150 built
the aux matrix — PW's team model, its one-block alignment and its
no-feedback guard — and its switch `DSP4_C2_AUX_MTX` defaults **OFF**,
because the 360 crosspoint words it needs are PROPOSED and not yet landed at
the hub gate. All four arms therefore rebuild the images S149 recorded
**byte for byte on both chips**, which is the whole of S150's blast radius
on this window: none. There is a fifth arm, **arm M**, built and md5-gated
in `build-images.sh M` — the matrix turned on, built out of a scratch tree
with the GRAPH's own dispatch tables because the landed ones cannot address
a crosspoint that has not been gated. It is a DESK image: do not stage it,
do not sign it. `MW/D24/DSP/s150/s150-report.md` is the case.

**Superseded framing (S149, 2026-09-29): EVERY ARM'S CHIP-2 IMAGE MOVED;
every arm's CHIP-1 IMAGE DID NOT.** Three chip-2 items landed between S148 and this
revision, all PW-ruled and all defaulting ON in `shipping.config`: the
live-crosspoint mix fabric (`DSP4_C2_MIX_FABRIC`, S148 lever L1), the
follower pairing (L2) and the reverb cap (`DSP4_FX_REVERB_CAP=3`). They are
chip-2 only by construction — `mix_fabric.asm` and `fx_cap.asm` live in
`src/chip2/`, and chip 1 has neither a chip-2 mix bus nor an FX engine — and
four independent builds confirm it: **all four arms' `chip1.ldr` md5s are
unchanged.** Every chip-2 md5 in this document is re-recorded, the capacity
table in §2.3 is re-read off the new maps, and the superseded values are
kept visible. **The shipping TRIPLE does not move** (§2.2): none of the three
switches is carried by a config word, so all three ride DIAG_BUILD_CFG3's
instrument bit and read 0 at their shipping values.

**UPDATED S147 (PW, 2026-09-29, "sign BQ_GRAPH"): arm B ships, not arm A.**
PW signed `DSP4_C2_BQ_GRAPH=1` into `shipping.config` itself between S146 and
this window, so arm B — priced below, never re-argued — is now what
`shipping.config` builds unadorned, and arm A needs an explicit
`DSP4_C2_BQ_GRAPH=0` override to reproduce. The images, their md5s and
everything §2.2–2.3 measured about them are UNCHANGED — only which one ships
and which one is the fallback moved. `MW/D24/DSP/s146/build-images.sh` carries
the swapped override so `./build-images.sh B` still means "build the arm this
window loads."

All four from the same tree, same toolchain (CCES 3.0.3, `ADSP-21564`,
`easm21k`/`cc21k`/`linker`/`elfloader`), each a full `./build.sh all` into its
own directory. ~2 min 09 s per arm. (At S146, all four came from the same
`shipping.config`; as of S147 that is no longer quite true for C and D — see
the note below the table.)

| arm | build | what it is | in this window? |
|---|---|---|---|
| A | `build_s146_bq0` | `DSP4_C2_BQ_GRAPH=0` (needs the explicit override now — the shipping default moved under it) | **NO. Fallback/rollback arm for the new graph — still staged, built, and gated; not this window's image.** |
| **B** | `build_s146_bq1` | `shipping.config` as it stands, `DSP4_C2_BQ_GRAPH=1` — **signed S147** | **YES — this is the window's image** |
| **C** | `build_s146_tn` | `DSP4_TEST_NODES=1` on top of whatever `shipping.config` defaults to | **NO.** The factory-test-v3 candidate — see §8.2 |
| **D** | `build_s146_rta` | `DSP4_RTA=1 DSP4_CUE=1` on top of whatever `shipping.config` defaults to | **NO.** Bench instrument for row 11 only — see §7 |

`DSP4_RTA=1` alone does not build: `dsp_block.h` stops it with *"DSP4_RTA
reads the cue bus since S65: build with DSP4_CUE=1"*. Both are needed, and
that is the pair S144 used.

**CLOSED S148 (PW, 2026-09-29): C and D rebuilt and re-priced against the
signed `DSP4_C2_BQ_GRAPH=1` default.** S147-1 flagged the gap; S148 closes
the rebuild/re-price half of it. Each arm was built twice under the new
default and reproduced byte for byte both times; `build-images.sh`'s C and D
rows now carry these md5s, and §2.2/§2.3 below are updated to match.
Adopting arm C as factory-test-v3 (editing the signed `accept/manifest.json`
and `d24_selftest.py`) is still PW's call per §9 item 2 and is **not** done
here — only the rebuild and re-price.

- arm C: chip1 `c031613ac9a0a02e4c1d493bea19765d` (433,508 B), chip2
  **`0b63f4e044e00e4a7cbe7b2ff345c0b6`** (460,720 B) — S149
- arm D: chip1 `c9bf6659fd888626465932c3814adb5f` (435,432 B), chip2
  **`c1d9f5db83bad18b78c000178a49191b`** (459,648 B) — S149

Superseded chip-2 values (S148, before S149's three items): C
`8674f98fdf2975b974c8fc83430c4240` (451,568 B), D
`edbdb100e7fb60b14e0e5285b156471c` (450,496 B).

Superseded (pre-S147 default, `DSP4_C2_BQ_GRAPH=0`, priced at S146): arm C
chip1 `7f226919a5d181410c3804d92678da19` / chip2
`d97645bfb800290b8f998924d939361c`; arm D chip1
`a026897ff6fd33654733f85c077599d6` / chip2
`ebf2fea4cca2f740cd560b1155134cc3`.

### 2.2 The artefacts, and their provenance

Tree: `main` at **`00663c581c75e8090c36ea70c21659d3b59d1315`** (S149; was
`24cb19ff2944f8a63de2d7104d1951656aa08f6d` at S146–S148), working tree
clean (`git status --porcelain` empty but for the untracked build
directories). Source tree fingerprint:

```
find MW/D32/DSP/SHARC/src -type f | LC_ALL=C sort | xargs sha256sum | sha256sum
  567b5e8a22f7b4555059f2f3a0b77c15f87d1ece2d992ff4183f8c732fb7f075   (S149)
  b0ebdd705406c6819aeb1c923a223eea89fbc68d4605e55d28219bc3a81dee29   (S146-S148, superseded)
```

`./check-sharc-codegen-drift.sh`: **759 generated / 0 differ / 0 absent /
53 hand-written** (757 at S146–S148; `chip2/mix_fabric.asm` and
`chip2/fx_cap.asm` are the two new generated files) — the tree IS its generator's output, so the images are
the contract's own images and not a tree that has drifted away from it.

**The build is byte-deterministic.** Arm A was built **four** times this
session (two separate directories, then twice more through
`build-images.sh`) and every `.ldr` came out md5-identical; arms B, C and D
were each built twice with the same result. `build-images.sh` re-ran all
four end to end and reported *"every arm built reproduces its recorded
image byte for byte"*.

**It no longer reproduces factory-test-v2 (S148 — this identity is now
BROKEN, confirmed by measurement, not assumed).** At S146, arm C's
`chip1.ldr` was `7f226919a5d181410c3804d92678da19` — byte-for-byte the
chip-1 image of factory-test-v2 staged at `/home/app/loopthd/s122`. S147
signed `DSP4_C2_BQ_GRAPH=1` into `shipping.config`, arm C's build line never
named that flag so it now inherits the new default, and S148's rebuild reads
back chip1 `c031613ac9a0a02e4c1d493bea19765d` — **different** from
`7f226919…`. The build-config word stamped into every image moved, same as
it does between arms A and B (§2.2 below); the S131 stale-source trap is
still answered (the toolchain reproduces byte for byte across two S148 runs
each), but arm C's chip 1 is no longer the same bytes as the staged
factory-test-v2 image. See §8.2.

| arm | file | bytes | md5 |
|---|---|--:|---|
| **A** | `chip1.ldr` | 426,464 | `1be74e042cff134c7085dfb08dade517` |
| **A** | `chip2.ldr` | 413,168 | **`e2de920d22edbbe76c1210a737abf6b7`** |
| **A** | `chip1.sym.json` | 216,923 | (re-generated; see the note below) |
| **A** | `chip2.sym.json` | 160,885 | (re-generated; see the note below) |
| A | `chip1.dxe` | 894,932 | (not gated) |
| A | `chip2.dxe` | 767,648 | (not gated) |
| B | `chip1.ldr` | 426,464 | `6d7b86ec69778900ce63b9eb79c144ea` |
| **B** | `chip2.ldr` | 459,152 | **`0a460926f8a2c9088bc0bc509f30769e`** |
| B | `chip2.sym.json` | 164,344 | (re-generated; see the note below) |
| **C (S149)** | `chip1.ldr` | 433,508 | `c031613ac9a0a02e4c1d493bea19765d` |
| **C (S149)** | `chip2.ldr` | 460,720 | **`0b63f4e044e00e4a7cbe7b2ff345c0b6`** |
| **C (S149)** | `chip2.sym.json` | 164,859 | (re-generated; not md5-gated) |
| **D (S149)** | `chip1.ldr` | 435,432 | `c9bf6659fd888626465932c3814adb5f` |
| **D (S149)** | `chip2.ldr` | 459,648 | **`c1d9f5db83bad18b78c000178a49191b`** |
| D (S149) | `chip2.sym.json` | 164,418 | (re-generated; not md5-gated) |

Superseded chip-2 `.ldr` md5s (S146–S148, kept for history — do not build
against them): A `2bddaa05367887eb2a349cde7b3d5055` (408,412 B), B
`e76d2dc8463292a2ba2f6b9172cb6be5` (450,008 B), C
`8674f98fdf2975b974c8fc83430c4240` (451,568 B), D
`edbdb100e7fb60b14e0e5285b156471c` (450,496 B).

🔴 **THE `.sym.json` MD5s ARE NOT REPRODUCIBLE AND NEVER WERE — S149-7.**
Arm A's `chip1.ldr` reproduces byte for byte at S149, and its
`chip1.sym.json` does **not**: `8896ddff…` against the `bc796228…` recorded
at S146. Compared key by key against the symbol map of a chip-1 image known
to be byte-identical, **6,398 symbols both ways, zero differing addresses** —
the only difference is the numbering of the compiler's own internal
`___ADI_AGL_CRT_SW_BRANCHRETURN_nnnnn` labels, which moves when the *other*
chip's compilation-unit count changes. So the symbol map is materially the
same map and its md5 is not a provenance check. **Nothing gates on it**
(`build-images.sh` gates `.ldr` only) and nothing should start: gate the
`.ldr`, regenerate the `.sym.json`. Recorded because this table used to
present those md5s beside the `.ldr` ones as though they carried the same
weight.

Superseded (pre-S147 default, `DSP4_C2_BQ_GRAPH=0`, priced at S146 — kept for
history, do not build against these):

| arm | file | bytes | md5 |
|---|---|--:|---|
| C (S146, superseded) | `chip1.ldr` | 433,508 | `7f226919a5d181410c3804d92678da19` |
| C (S146, superseded) | `chip2.ldr` | 409,972 | `d97645bfb800290b8f998924d939361c` |
| C (S146, superseded) | `chip2.sym.json` | 160,511 | `d101bec222b46c93aaf23245cbdb0379` |
| D (S146, superseded) | `chip1.ldr` | 435,432 | `a026897ff6fd33654733f85c077599d6` |
| D (S146, superseded) | `chip2.ldr` | 408,900 | `ebf2fea4cca2f740cd560b1155134cc3` |

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
| A | `0xCF45FF10` | `0xE2018E6F` | `0xC47C0FA6` |
| **B (ships, S147)** | `0xCF45FF10` | **`0xE2019E6F`** | `0xC47C0FA6` |

One bit apart, in word 2 bit 12. That is the only thing on the wire that
tells arm A from arm B, so §6 reads it. `check_shipping_config.sh
--expect-shipping` computes `0xCF45FF10 / 0xE2019E6F / 0xC47C0FA6` from
today's `shipping.config` — arm B's triple, confirmed on this tree
2026-09-29.

### 2.3 Capacity and delay memory, re-priced for these exact images

**Memory is exact** — read out of these images' own linker map files by
`tools/dsp/dsp_memreport.py`, not carried from a prediction:

**UNCHANGED AT S150** — the aux matrix's switch defaults off, so every
figure below is the one S149 measured and every arm still reproduces its
image byte for byte. **Arm M**, the matrix arm, is the one that moves, and
it moves the number this table is closest to its limit on:

| pool | chip 2, arm B (ships) | chip 2, **arm M (matrix, desk only)** | limit |
|---|--:|--:|--:|
| code (VISA SW) | 189,838 — 72.4 % | **177,958 — 67.9 %** | 262,144 B |
| DM data + stack | 333,956 — 89.0 % | **346,732 — 92.4 %  ← OVER THE WARN LINE** | 375,264 B |
| delay lines | 1,886,112 — 91.0 % | **1,886,112 — 91.0 %** | 2,072,576 B |

Code goes DOWN by 11,880 bytes, which is not a typo: the matrix arm of a
chip-2 aux sum is fabric-only, so the twelve sums' generic per-sample
wrappers — unreachable under `DSP4_C2_MIX_FABRIC=1` and assembled anyway
since S149 — stop being emitted. DM goes UP by 12,776 and crosses
`dsp_memreport`'s 90 % warn line, which S149-5 said the next chip-2 feature
of this size would do. See S150-1.

**UPDATED S149: every chip-2 column below is re-read off the S149 rebuild's
own map files.** L1 (the mix fabric), L2 (the follower pairing) and the
reverb cap all land on chip 2 and all default ON, so all four arms' chip-2
figures moved; **no chip-1 figure moved at all.** Chip 2's "arm A" column is
the FALLBACK figure and the "arm B" column is what ships.

| pool | chip 1, arms A/B | chip 1, **C** | chip 1, **D** | chip 2, arm A (fallback) | chip 2, **arm B (ships)** | chip 2, **C** | chip 2, **D** | limit |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| code (VISA SW) | 181,490 — 69.2 % | 187,142 — **71.4 %** | 184,378 — **70.3 %** | **175,492 — 66.9 %** | **189,838 — 72.4 %** | **191,316 — 73.0 %** | **189,910 — 72.4 %** | 262,144 B |
| DM data + stack | 309,612 — 82.5 % | 311,004 — **82.9 %** | 315,692 — **84.1 %** | **302,316 — 80.6 %** | **333,956 — 89.0 %** | **334,044 — 89.0 %** | **334,380 — 89.1 %** | 375,264 B |
| delay lines | 506,880 — 24.5 % | 572,416 — **27.6 %** | 506,880 — **24.5 %** | 1,886,112 — 91.0 % | **1,886,112 — 91.0 %** | 1,886,112 — **91.0 %** | 1,886,112 — **91.0 %** | 2,072,576 B |
| IVT (NW code) | 128 — 49.2 % | 128 — 49.2 % | 128 — 49.2 % | 128 — 49.2 % | — | — | — | 260 B (fixed) |

Superseded chip-2 figures (S146–S148, before S149's three items): arm A
173,168 code / 299,884 DM; **arm B 186,382 — 71.1 % code / 328,268 — 87.5 %
DM**; C 187,862 / 328,348; D 186,454 / 328,684. Delay was 1,886,112 on every
arm then and is 1,886,112 on every arm now — **S149's three items do not
move one byte of delay pool.**

**What S149 cost chip 2, itemised from these maps:** L1 +2,098 code /
+2,352 DM (the shared gather scratch, 23 sources × 16 words, plus fifteen
source-pointer tables); L2 +1,134 code / +3,256 DM (the GEQ pair's
interleaved arrays are 683 words, the AFB pair's 133); the reverb cap +224
code / +80 DM. **The chip-2 DM pool is now at 89.0 %, one point under
`dsp_memreport`'s 90 % warn line, 41,308 bytes free** — recorded as S149-5,
because a third chip-2 cascade pair of GEQ size would cross it.

(Arm B's own chip-1 figures are identical to arm A's — the flag is chip-2
only — so "arms A/B" is one column for chip 1, per §2.2's build-cfg-word
note.)

Arm D is the only arm that moves **chip 1** off the A/B figure: code
181,490 → 184,378 (69.2 → 70.3 %) and DM 309,612 → 315,692 (82.5 →
**84.1 %**), because the 1/3-octave filterbank and the ring metric live
there. This is unchanged by S148 — D's chip 1 does not carry
`DSP4_C2_BQ_GRAPH` either way. It still fits, and it reproduces S144's own
RTA figures exactly. **Arm C's chip 1 moves too, and S146 did not say so** —
`DSP4_TEST_NODES=1` puts the TEST_OSC/TEST_MEAS nodes on chip 1 and nothing
on chip 2 (`shipping.config` says so at the point of definition), so arm C's
chip 1 cannot be arm A's, and S146's table nevertheless grouped "chip 1,
arms A/B/C" at one figure of 181,490. Measured at S148 it is **187,142 code
(71.4 %) / 311,004 DM (82.9 %) / 572,416 delay (27.6 %)** — +5,652 bytes of
code, +1,392 of DM and +65,536 of delay line over the A/B column. Recorded
as **S148-6**: S146's chip-1 arm-C figure was the A/B figure wearing arm C's
label, and this is the measurement that replaces it.

Chip 2's delay pool is at **91.0 %, 186,464 bytes free, on every arm** —
A, B, C and D all read exactly 1,886,112 of 2,072,576 bytes, over
`dsp_memreport`'s own 90 % warn line, and the tool says so on every run.
This reproduces S144's table to the byte. `DSP4_C2_BQ_GRAPH` and
`DSP4_TEST_NODES` buy code and DM, never delay — confirmed again at S148 on
C and D's re-priced figures. It is the first image that asks for 1,886,112
of 2,072,576 bytes and that is bench row 12.

**Taking arm B over arm A costs chip 2 +14,346 bytes of code (66.9 →
72.4 %) and +31,640 bytes of DM (80.6 → 89.0 %), and this window takes it**
— S147 signed `DSP4_C2_BQ_GRAPH`. It fits, with 41,308 DM bytes to spare.
(Before S149 the same delta read +13,214 code / +28,384 DM; L2's interleaved
arrays are inside `DSP4_C2_BQ_PAIRED_GRAPH`, so part of S149's cost lands on
arm B and not on arm A, which is why the A→B delta grew.)

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

**UPDATED S149 — the constructed landing moves DOWN, and by more than the
levers alone.** Three things changed the arithmetic: L1 (the chip-2 mix
fabric) is worth **1.59 points unconditionally** and 9.29 more once the desk
is in use; L2 (the follower pairing) **1.27 points**; and S149-3 found that
S148's in-use column priced the generic wrapper at an AVERAGE rate as though
it were a MARGINAL one, which made every "as built" in-use figure **3.30
points** too expensive. Recomputed on S148's own measured baselines
(`MW/D24/DSP/s149/s149-report.md` §3): **arm B idles at ≈74.8 % and the worst
regime the product can be put into — three reverbs, PW's cap, with the desk
fully in use — lands at ≈87.4 %**, against S148's 110.27 % for the uncapped
equivalent. **It is still a construction and still bench row 3.**

**Cycles are NOT re-measured here and cannot be.** The percentages in
S142/S143/S144 are constructed — counted from emitted instructions — and
**arm A's** landing figure is **≈ 91.7 % of chip 2's 327,680 cycles/block**
at block 16, 983.04 MHz, driven, six Echoes, from S86's measured 84.47 %
baseline plus S143 (+2.69 % stereo main bus, +0.08 % group crosspoints) and
S144 (+2.26 % Centre/Woof, +1.04 % phones, +1.19 % anti-feedback). **Arm B
— this window's image — lands lower still: ≈17 points under arm A**, taken
from the pairing's own ~17.4-point buyback (below, the reverb-regime case)
rather than re-derived for the Echo default; it is CONSTRUCTED the
same way and no more measured than arm A's figure. **Nothing has ever
measured either on a part.** That is bench row 3, on arm B now, and it is
the row that decides whether this graph ships.

Two cautions that belong next to that number:

- **The six-reverb regime is no longer a regime — PW capped it at three
  (S149).** `DSP4_FX_REVERB_CAP=3` is in the image this window loads, and the
  guard holds a fourth Reverb rather than loading it, so six engines at
  Type 3 cannot be reached however the host is driven. Six FX engines at
  Type 3 was +16.44 measured points over the Echo default's +1.53 — ≈106.6 %
  on arm A — and arm B bought ~17.4 points of that back; the cap removes the
  top half of the case outright. **A consequence for the bench, recorded as
  S149-4: the six-reverb capacity row can no longer be BUILT on a
  shipping-configured tree** (it now produces three reverbs and three
  Echoes). Take that row with `DSP4_FX_REVERB_CAP=0`.
- **`tools/dsp/product_fit.py`'s own percentages are not this graph's.**
  Its anchors are S27/S80 measured rows, all from before S142, and its
  `CODE_USED_C1` / `CODE_USED_C2` constants (180,954 / 164,168) are 536 and
  9,000 bytes behind the images this tree now builds. Use it for the census
  and the masks; do not read its capacity table as a prediction for the new
  graph. Recorded as S146-1.

### 2.4 The dry run

**UPDATED S147 — re-run against `build_s146_bq1` (arm B), the arm this
window now loads; the original S146 run below was arm A's `build_s146_bq0`.**
Off-target, desk-side, nothing loaded to any part:

```
python3 tools/pi/dsp4_boot.py --dir MW/D32/DSP/SHARC/build_s146_bq1 --dry-run
  chip 1: chip1.ldr 426464 B -> 427008 B padded (417 x 1024), CS GPIO6,  RDY GPIO8
  chip 2: chip2.ldr 459152 B -> 459776 B padded (449 x 1024), CS GPIO24, RDY GPIO12
  reset: GPIO16 pulsed low, 0.500s settle
  (2 chip(s), 10000000 Hz, SPI mode 1, 2 attempt(s) per chip)
```

(Re-run at S149 on the rebuilt arm B. Before S149 chip 2 was 450,008 B
padding to 440 blocks; the three chip-2 items take it to 459,152 B and 449.)

Both streams also passed `tools/dsp/ldr_stream.py check` on this tree —
*"8 blocks, no mid-stream fill blocks"* on each — and the loader's entry
address was verified at `0x90004` (the RSTI vector) from the elfloader log.
Chip 1 pads identically to arm A (unaffected, as everywhere else); chip 2
pads to 449 blocks instead of 399, the pairing's and S149's extra code and
DM. Both `ldr_stream.py check` runs are green again at S149 — *"8 blocks, no
mid-stream fill blocks"* on each.

Contract gates re-run this session (S146) and again at S147 on the arm swap,
all green on the tree the images came from — none of these four are
per-arm, so the swap does not move them:

| gate | result |
|---|---|
| `check-sharc-codegen-drift.sh` | **759** generated, **0 differ** (S149; 757 before) |
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
`B=MW/D32/DSP/SHARC/build_s146_bq1` throughout — **arm B, updated S147**;
S146 built and staged from `build_s146_bq0` (arm A), now the fallback (§2.1).

### Step 1 — Build the images (hub machine, nothing on the unit)

```
./MW/D24/DSP/s146/build-images.sh B
```

That is the whole step: it builds arm B, writes both symbol maps, and
**refuses** the arm if either `.ldr` md5 is not the one this document
priced. By hand it is:

```
cd MW/D32/DSP/SHARC && DSP_BUILD_DIR=$PWD/build_s146_bq1 ./build.sh all && cd -
python3 tools/dsp/map_syms.py $B/chip1.map.xml > $B/chip1.sym.json
python3 tools/dsp/map_syms.py $B/chip2.map.xml > $B/chip2.sym.json
md5sum $B/chip1.ldr $B/chip2.ldr
```

**GATE:** the two md5s must be `6d7b86ec69778900ce63b9eb79c144ea` and
`0a460926f8a2c9088bc0bc509f30769e` (S149; the chip-2 value was
`e76d2dc8463292a2ba2f6b9172cb6be5` before S149's three items). If either differs, the tree is not the
tree this document priced — stop, do not "fix it forward". Confirm
`git rev-parse HEAD` and the tree clean, and re-run
`./check-sharc-codegen-drift.sh`.

Do NOT pass `DSP4_C2_BQ_GRAPH`, `DSP4_C2_MIX_FABRIC`, `DSP4_FX_REVERB_CAP`,
`DSP4_RTA`, `DSP4_CUE` or `DSP4_TEST_NODES` on this command line. Arm B is `shipping.config` untouched, as of S147 —
`DSP4_C2_BQ_GRAPH=1` is now the signed default, not an override.

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
2. **The part is carrying arm B and can prove it.** (Updated S147 — arm B
   ships, not arm A.)
   `python3 dsp4_buildcfg.py --expect-shipping` on **both** chips. It must
   read `0xCF45FF10 / 0xE2019E6F / 0xC47C0FA6` and exit 0. A part answering
   `0xE2018E6F` in word 2 is arm A — the fallback image, wrong for this
   window; a part answering `0x00000000` at `0xE0EC` is a pre-S80 image
   entirely.
3. **The staged image is the image that was built.**
   `md5sum /home/app/ship_s146/chip1.ldr /home/app/ship_s146/chip2.ldr` →
   `6d7b86ec…` / `0a460926…`. The triple alone cannot do this job — and
   since S149 it is the ONLY thing that can, because all three of S149's
   switches ride the instrument bit and the shipping triple is unmoved: S124
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

Standing preconditions for all of them: arm B booted and verified per §6
(updated S147 — arm B ships, not arm A); AN_EN raised once, after the last
boot of the session, and held; the CPLD in its shipping personality
`d02d83b3cc22` (a loopback personality is for digital-only work and will not
carry these).

**ADDED S150 — three more, and they go AFTER S149's three and BEFORE the
twelve. Every one of them needs arm M, which is a desk image until the hub
lands the crosspoint addresses; none of them can be taken on the shipping
arm, because on the shipping arm the matrix is compiled out.**

**0d. The aux→aux path exists and goes the right way.** Open
`Aux001AuxSend002` (aux 1 into aux 2) at unity with `Aux001AuxOn002` = 1,
drive aux 1 only, and capture aux 2's output. *PASS: aux 2 carries aux 1's
PROCESSED output — it must follow aux 1's own EQ, limiter and delay, which
is what distinguishes PW's team model from a pre-strip tap. Then close it
and confirm aux 2 reads exactly zero of aux 1.*

**0e. The alignment, MEASURED, and it is the row that checks PW's ceiling.**
With every matrix crosspoint closed, measure the aux through-DSP latency on
arm M and on arm B (`DSP4_C2_AUX_MTX=0`). *PASS: arm M is EXACTLY 16 samples
later, 98 samples against 82, and not 32. The main, monitor and phones paths
must not move at all. A second block anywhere here is a 🔴 stop, not a
trade: 0.33 ms is the whole budget PW signed.*

**0f. The guard refusing a loop, on the part.** Open aux 1 → aux 2, then ask
for aux 2 → aux 1. *PASS: the second send is inert — aux 1 carries exactly
zero of aux 2 — `Aux002AuxOn001` still READS BACK 1 (the host's word is
never written), and the desk does not howl. Then close aux 1 → aux 2 and
confirm aux 2 → aux 1 becomes live within one block with no further
traffic.* Then the longest loop the guard has to see: 1→2, 2→3, 3→1.

**ADDED S149 — three rows that go in FRONT of these twelve, in the order
that makes each next number worth taking.** They are capacity rows, they
need no analog path, and each one turns a construction this tree is now
several sessions deep in into a measurement.

**0a. The BYPASS row — the term the whole in-use column is built on, and it
has never been measured.** With the pair booted and idle, read the driven
chip-2 figure with every `Fx*AuxOn` at its default of 0 (the S23 bypass
firing on all eight aux buses), then open ONE FX return into ONE aux and
read it again. *PASS criterion: none — this row exists to produce a number.*
It measures S148-1's 2,112 c/blk per node directly, and with it S149's whole
per-crosspoint rate table (`MW/D24/DSP/s149/s149-report.md` §1.3) stops being
an instruction count and becomes a calibration. **Take this before row 3**:
row 3 measures the regime the levers help least, and on its own it cannot
tell a good in-use construction from a bad one.

**0b. The FABRIC's own before/after, on one driven row.** Same measurement
as 0a with every aux fully patched, taken on arm B and then on an arm built
`DSP4_C2_MIX_FABRIC=0` (the control, which reproduces the pre-S149 image on
chip 2 byte for byte). *PASS:* the two agree on the audio (they are
bit-exact by construction — `tools/dsp/c2_mix_fabric_ref.py` — so a
difference is a defect, not a tolerance) and the fabric arm is lower by
about the counted 8,696 instructions a block. **This is the only row that
prices L1 rather than modelling it.**

**0c. The reverb cap, at the cap.** Put four engines on Type Reverb over
SPI, read back `Fx*Type` (must be what was written — the guard never
rewrites it) and the live type (`_fx_type_live_*`, by symbol). *PASS:* three
engines run Reverb, the fourth runs whatever it was running, chip-2 capacity
sits at the three-reverb figure and not the four-reverb one, and moving one
of the three off Reverb grants the held one **within one block**. Then the
same with six requested. **Note S149-4: the six-reverb capacity row itself
now needs `DSP4_FX_REVERB_CAP=0`** — on a shipping arm it will quietly
measure three.

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
`MW/D32/DSP/SHARC/capacity.sh` with `--driven`, on **arm B** (updated S147 —
arm B ships, not arm A), the shipping configuration, on the part.
*PASS:* chip 2 average below 100 % of 327,680 cycles/block with a real
margin, `DIAG_BLK_OVERRUN` 0 and `_proc_passes` matching `DIAG_FRAME_COUNT`.
*Expect ≈ 17 points under arm A's ≈ 91.7 % on the Echo default — i.e.
constructed ≈ 74.7 %* (§2.3): taken from the pairing's own buyback figure,
not independently re-derived, and no more measured than arm A's number was.
The boot-to-boot spread on arm A's row was 0.53 points; nothing says arm B's
is the same, and this row is what finds out. **Six Reverbs at Type 3, which
did NOT fit on arm A (≈ 106.6 %), is arm B's case to make** — constructed at
≈ 89 % on the same arithmetic, still unmeasured, and still not this row's
job to prove (see the Echo default first).
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

**11. The ring metric, on a real ring. — NEEDS ARM D, NOT ARM B.**
**RUNNABLE — arm D rebuilt and re-priced at S148.** S147-1 flagged that
`build_s146_rta` (`DSP4_RTA=1 DSP4_CUE=1`) never named `DSP4_C2_BQ_GRAPH`
and had gone stale against the signed default; S148 rebuilt it (twice,
byte-identical both times) and re-priced it off its own map files. Use the
CURRENT pair, chip1 `c9bf6659fd888626465932c3814adb5f` / chip2
**`c1d9f5db83bad18b78c000178a49191b`** (§2.2, re-recorded at S149) — NOT the
superseded `edbdb100…` (S148) or `a026897f…` / `ebf2fea4…` (S146) pairs this
row was written against.
Assign the cue to Main, provoke a deliberate acoustic ring through the
monitor speaker, read `_rta_ring` back.
*PASS:* the saturating count pegs on the ringing band (cap 2,047 blocks =
682 ms) and stays near zero on the others while programme material plays.
**This is a bench-instrument image, and taking it costs two boots.** Lower
AN_EN first (`pinctrl set 26 op dl`) — `boot_pair()` refuses a rails-up
boot, and that applies to swapping arms as much as to the first one — stage
arm D beside arm B, boot it, run the row, then **boot arm B again before
any other row** and raise the rails once more. Note also that the strip
meter latches peaks and decays 6.52 dB/s: read the metric, not the meter.

**12. The delay pool at 91.0 %.** A boot and a soak on **arm B** (updated
S147 — arm B ships, not arm A; the delay figure is unchanged, S2.3) with
every delay line allocated — the first image ever to ask for **1,886,112 of
2,072,576 bytes** on chip 2, 186,464 free.
*PASS:* the pair boots to `BOOT_STAGE 7` repeatedly, the soak runs with
`DIAG_BLK_OVERRUN` 0, and no delay line reads another's content. *Run this
before, not after, the audio rows — if the pool does not survive a boot,
nothing below it means anything.*

---

## 8. Risks, gates, abort criteria

### 8.1 Capacity — the only real one

**UPDATED S150: this window's numbers do not move, because the aux matrix
is not in this window's image.** Arm M's worst reachable regime is a
constructed **90.28 %** (three reverbs, the desk in use, and the maximal
legal matrix the guard will allow), against arm B's 87.36 % and the same
~97 % abort line. The matrix costs 1.54 points unconditionally and 2.91 in
that worst patch. It is 6.7 points inside the line and it is still a
construction on S86's driven row, like everything else in this chain.

**UPDATED S149.** Arm A landed at a **constructed** ≈ 91.7 % against a
boot-to-boot spread of 0.53 points; arm B — this window's image — is
constructed **≈ 74.8 % on the Echo default** after S149's two levers and its
correction to S148's in-use arithmetic (§2.3, and
`MW/D24/DSP/s149/s149-report.md` §3). **No cycle figure for either arm has
ever been measured on a part**, and that has not changed: every number in
that chain is a construction on S86's driven row.

If bench row 3 comes back above ~97 % on the Echo default, or shows any
missed block, **abort the window** (§5) and take it back to the desk. Do not
reach for arm A at the bench to dodge a capacity problem:
`DSP4_C2_BQ_GRAPH` is a signed default, not a rescue lever, and an abort
here is a desk decision, not a bench one.

**Two things to know before reading row 3's number.** (a) Row 3 measures the
Echo default with nothing switched on, which is the regime the levers help
LEAST in — L1's 9.29 points are all in the in-use column and only its 1.59
unconditional points show on an idle desk. **A row-3 number close to the
construction does not validate the in-use column**; the bypass row (§7's new
first row) is what does. (b) The three S149 switches are **not carried by any
config word**, so a part cannot tell you whether it is running them — the
shipping triple is identical either way. The `.ldr` md5 (§6 gate 3) is the
only check that can.

### 8.2 The automated factory self-test set stops working on this pair

`d24_selftest.py::_check_factory_image()` asserts that every DSP-touching
press is running **factory-test-v2** — the triple AND both `.ldr` md5s. Arm
B is neither. So after the switch **every DSP-dependent row of the automated
set reports NO DATA "wrong image loaded"**, by design, not by accident.

This is a consequence, not a defect, and it has a clean handling:

- Run the automated set **before** the switch, on the pair that is staged
  today. It is valid there and nothing in this window changes that.
- After the switch, the verification is §6 plus PW's twelve rows, on the
  shipping pair.
- Arm C (`build_s146_tn`) was the factory-test-v3 candidate at S146, priced
  with chip1 `7f226919…` — **then byte-identical to factory-test-v2's chip
  1** — and chip2 `d97645bf…`. **That identity is CONFIRMED BROKEN, measured
  at S148, not just flagged (S147-1 closed for the rebuild/re-price half):**
  S148 rebuilt arm C (twice, byte-identical both times) against today's
  signed `shipping.config` and read back chip1
  `c031613ac9a0a02e4c1d493bea19765d` / chip2
  `8674f98fdf2975b974c8fc83430c4240`, re-recorded at S149 as chip2
  **`0b63f4e044e00e4a7cbe7b2ff345c0b6`** with chip 1 still unmoved — chip 1
  is confirmed **NOT**
  `7f226919…` any more; the build-config word stamp moved with
  `DSP4_C2_BQ_GRAPH`, same mechanism as arms A/B. Re-establishing v3 needs
  `FACTORY_TEST_*` in `d24_selftest.py` and `factory_test_image` in
  `MW/D24/DSP/accept/manifest.json` updated to these new md5s.
  **Not done here** — the record is signed and moving it is PW's, not a
  side-effect of a switch window (or this rebuild task). §9.

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

### 8.7 The signed triple in the accept manifest — CLOSED at S147

**S146-3 is fixed, not just recorded, as of S147.**
`MW/D24/DSP/accept/manifest.json`'s `dsp.build_cfg` and
`tools/pi/d24_selftest.py`'s `SIGNED_TRIPLE` used to record
`0xCF45FF10 / 0xE2018E6F / 0xC47C0F26` — stale even at S146, because word 3
bit 7 (`DSP4_TX_DEFER`, 0 → 2 for the DAC fold fix) had already moved. S147's
own signature (word 2 bit 12, `DSP4_C2_BQ_GRAPH`) would have opened a second
gap on top of the first, so both moved together: both files now read
`0xCF45FF10 / 0xE2019E6F / 0xC47C0FA6`, hand-edited (the manifest's
`dsp.build_cfg` is a generated field, but `gen_accept_fixtures.py`'s
generation also advances the fixture set to the current `defs` pin — a
separate, larger change this window does not make — so the triple was
corrected in place instead of by a full regeneration).

**Proved by the existing image-check path, desk-side, no unit touched:**
`tools/dsp/cfg_words.py` computes `0xCF45FF10 / 0xE2019E6F / 0xC47C0FA6`
from `shipping.config` independently of either file, and now matches both
`manifest.json`'s `dsp.build_cfg` and `d24_selftest.py`'s `SIGNED_TRIPLE`
byte for byte — checked by hand this session, not assumed. `§6 gate 2`
(`dsp4_buildcfg.py --expect-shipping`) is the on-part half of the same
check and reads the identical triple.

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

1. **CLOSED S147 (PW, 2026-09-29, "sign BQ_GRAPH"): `DSP4_C2_BQ_GRAPH=1` is
   signed into `shipping.config` itself.** Arm B ships this window, not
   arm A (chip 2: code 66.1 → 71.1 %, DM 79.9 → 87.5 %, delay unchanged;
   worth ~17.4 points of capacity) and tells itself apart on the part by
   `DIAG_BUILD_CFG2 0xE2019E6F`. The accept manifest's and `d24_selftest.py`'s
   signed triple were updated to match (§8.7); nothing here is still open.
2. **factory-test-v3: arm C is rebuilt and re-priced (S148), adoption still
   open.** Arm C was built and priced at S146, but never named
   `DSP4_C2_BQ_GRAPH` on its own build line, so it inherited the old default
   then and inherits the new signed one now — its S146 md5s (including
   chip 1, previously byte-identical to factory-test-v2) no longer
   reproduce (S147-1). S148 (2026-09-29) rebuilt arm C twice against today's
   signed `shipping.config` (byte-identical both times: chip1
   `c031613ac9a0a02e4c1d493bea19765d`, chip2
   `8674f98fdf2975b974c8fc83430c4240`; S149's three chip-2 items then moved
   chip 2 again, to `0b63f4e044e00e4a7cbe7b2ff345c0b6`, with chip 1 still
   unmoved) and re-priced it off its own map
   files (§2.3) — confirming, not just flagging, that chip 1 no longer
   matches factory-test-v2's `7f226919…`. `build-images.sh` and this runbook
   now carry the new md5s. Adopting v3 still means editing a signed record
   (`accept/manifest.json`'s `factory_test_image`) and `d24_selftest.py`'s
   pinned md5s to these S148 values; that edit is PW's call and was not made
   here — S148 only rebuilt and re-priced, it did not adopt.
3. **Republishing `_matrix.mxc` is a separate window.** It would hand the
   app's `DspApply` 3,800 DSP addresses for the first time and add six
   `Ramp*` columns the deployed pack does not carry. Neither is needed for
   the graph; both change app behaviour. Recommend: after the graph is
   proven at the bench, pack and `dspWriteEnable` together, with their own
   verification.
4. **The aux→aux matrix (S143-2) is still not built** and still needs the
   placement ruling — post-limiter/pre-delay, pre-EQ, or a block-old read.
   It is not in this image and the window does not change that.
5. **`Main Out3Link`'s two readings (S144-3)** and **where the anti-feedback
   ring-out decision should live (S144-5)** are both still open. Rows 6 and
   10 record what was set rather than assuming.
