provenance: AI-drafted 2026-09-19 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S72 — the aux-in right leg gets its lane, and the talkback polarity gets a bit

Desk only, 2026-09-19. No unit was touched: no boot, no flash, no config, no rails.
Everything below is the generator, the assembler, the linker and the two images they
produced.

S71 found that the mini-jack's ring is codec TDM slot 1, that slot 1 was not received,
and that `XFER_CODEC_AUX_R` had therefore been parked on slot 2 — an unconnected
converter input — as a placeholder. It asked the hub what should feed aux R (S71-3).
The hub ruled: **option 1, declare the lane.** This session does that, and closes the
second thing S71 left open (S71-4, the talkback polarity flag with no way to read it
back off the part).

## 1. The lane, declared

One row added to `superset_c1` in `tools/dsp/gen_dsp_csv.py`, and one edge moved:

```
C1_XIN_CODEC_02,1,INPUT_TDM,Codec ADC 2 (Aux In R / mini-jack ring),1,,
  C1_XS_XFER_CODEC_AUX_R,-1,-1,
  sport_id=4;slot_start=1;slot_count=1;sport_slots=8;signal=CODEC_RET_2,
```

`XFER_CODEC_AUX_R` now reads `C1_XIN_CODEC_02` instead of `C1_XIN_CODEC_03`. The aux
input is stereo, which is what the netlist always said the hardware is.

`C1_XIN_CODEC_03` stays declared, with its S71 label `(ADC2 L / not connected)`, and
now **feeds nothing** — its `outputs` column is empty. That is deliberate: the lane map
stays complete (all four of the codec's ADC channels are named and in slot order) while
the not-connected one reaches no audio path. `dsp_validate.py` accepts it: 701 nodes,
no errors, and the same four pre-existing chip-2 process-order notes as before.

**`cs_mask` moved 0x000D → 0x000F, and nothing set it by hand.** `lane_layout()` in
`dsp_codegen.py` derives each lane's mask from the slots of the nodes declared on it.
Read off the generated artefact, `src/chip1/lane_config.c`:

```
-    4, 0x000D, 3, 512,   /* MFD 2 */
+    4, 0x000F, 4, 512,   /* MFD 2 */
```

No SPORT register is written anywhere in this change.

### Scope: one table, both products

`superset_c1` carries a `scope` field, and the codec-return rows do not use it — the
snake rows next to them carry `'D32'` and these four carry `None`. So this is **one
table for both D24 and D32**, as the single-firmware decision requires
(`dsp4-architecture-decisions.md`), and D32 gets the `C1_XIN_CODEC_02` lane too.

That is harmless, and the reason is that it was already the case one lane along. On
D32 the aux-R leg reaches `C2_CODEC_AUX_IN`, which is `on=0` by default in `dsp.csv`;
before this change that leg was fed by `CODEC_RET_3`, which is also not connected. So
D32 goes from a dead lane to a dead lane, renumbered to the slot D24 measured. No D32
branch was added and none was needed.

## 2. Zero addresses moved

`./regenerate-dsp-contract.sh`, then `./check-contract-drift.sh` (passed: "differ from
the committed tree: 0", "tree == generator output").

**The eight address artefacts are byte-identical to `HEAD`**, compared with `cmp`
against `git show HEAD:<path>`:

| artefact | result |
|---|---|
| `MW/D32/DSP/dsp_address_map.md` | IDENTICAL (5,827 rows, md5 `2918ed21f9491b13085a9774ced6def1`) |
| `MW/D32/DSP/ghost_cells.h` | IDENTICAL (md5 `bf45dfc06ffb1fe78cc18c180e5c126e`) |
| `MW/D12/MX/_matrix.csv` | IDENTICAL |
| `MW/D16/MX/_matrix.csv` | IDENTICAL |
| `MW/D24/MX/_matrix.csv` | IDENTICAL |
| `MW/D32/MX/_matrix.csv` | IDENTICAL |
| `MW/D32/DSP/SHARC/src/chip1/dsp_params.asm` | IDENTICAL |
| `MW/D32/DSP/SHARC/src/chip2/dsp_params.asm` | IDENTICAL |

The SPI allocation ends where it ended: chip 1 page 1 addr 4983, chip 2 page 1 addr
2175 — the same two numbers S71 recorded. The new node has `spi_page=-1`,
`spi_addr=-1`: an `INPUT_TDM` lane allocates nothing. **Cell names unchanged.**

### Every file that changed, and why none of them is an address artefact

Twenty-one modified, one added. In four groups:

**The source of the graph (2).**
`tools/dsp/gen_dsp_csv.py` — the added `superset_c1` row, the `xfer_map` edge, and one
mechanical change: `xin_consumer[nid]` became `xin_consumer.get(nid, '')` so a declared
lane with no consumer is legal rather than a `KeyError`.
`MW/D32/DSP/SHARC/dsp.csv` — its output. Three rows: the new `C1_XIN_CODEC_02`,
`C1_XIN_CODEC_03` losing its `outputs` value, and `C1_XS_XFER_CODEC_AUX_R` changing
its `inputs` value. 701 nodes (was 700); chip 1 442 (was 441); chip 2 259, unchanged.

**The RX plumbing the new lane lands in (2).**
`src/chip1/lane_config.c` — lane 4's mask and slot count, and the region offsets of
lanes 5/6/7 shifting by 16 words each; `c1_rx_region_words` 736 → 752.
`src/chip1/block_io.asm` — the RX tables grow from 46 to 47 entries, the new lane's
offset 515 is inserted after 514, and the `_c1_ic_tx_ptrs` entry that sources
`XFER_CODEC_AUX_R` changes from `_buf_C1_XIN_CODEC_03` to `_buf_C1_XIN_CODEC_02`.

**The nodes that sit after the insertion point in the packed RX order (12).**
`C1_XIN_CODEC_03/04`, `C1_XIN_SNK_01..08`, `C1_XIN_PI_L/R`, `C1_XIN_MEMS`. Every one
of these is a **one-line** diff: the constant `r3 = N`, that node's index into
`_c1_rx_node_entry`, incremented by one. `C1_XIN_CODEC_01` is at index 32, before the
new lane, and did not change. Plus `C1_XS_XFER_CODEC_AUX_R.asm`, whose `.extern` and
per-sample read now name `_buf_C1_XIN_CODEC_02`, and `process_chain.asm`.

`process_chain.asm` is 660 changed lines and only eighteen of them are new: the new
node's three `.extern`s and its call plus scope-tap/inject block in each of the three
paired-graph arms. The other ~642 are `#if (DSP4_NODE_LIMIT == 0 || N < ...)` guards
with `N` incremented by one after the insertion point, and the aux-entry comments that
carry the same indices. `HEAD`'s copy was checked to be self-consistent first (HEAD's
`dsp.csv` regenerated into a scratch tree reproduces HEAD's `process_chain.asm`
exactly), so none of that churn is pre-existing drift.

**The new file (1).** `src/chip1/nodes/C1_XIN_CODEC_02.asm` — a standard `INPUT_TDM`
kernel, generated, identical in shape to its three siblings.

**`MW/D24/DSP/input_patch.json` (1), which is not an address artefact.** It is the host
DMA input permutation, generated from `defs/products/d24/inputs.csv`. Its `patch` array
is one entry per packed RX node, identity except for the 24 analog XLRs. It goes from
46 to 47 entries and **the only change is a `46` appended to the tail**: the permuted
entries are indices 0..31 and the new lane lands at index 33, inside a stretch that was
already identity (`[32, 33, … 45]` → `[32, 33, … 46]`). No XLR moved. `d24_inputs.py`'s
`PRE_S58_PATCH` is a frozen historical table and is correctly left alone;
`dsp4_config.py` loads the live patch from the JSON, so it picks up the new length
without a hand-edited mirror.

### The codegen cost delta

`dsp_codegen.py`'s own report, diffed HEAD vs now, moves in exactly three places:

```
- chip1/process_chain.asm: block-aware scope tap on 334 nodes
+ chip1/process_chain.asm: block-aware scope tap on 335 nodes
- Generated 731 files    -> + Generated 732 files
-   Chip 1: 441 nodes    -> +   Chip 1: 442 nodes
-   (none): 242 nodes    -> +   (none): 243 nodes
```

Chip 2 is untouched in the report and in the tree.

**Cycles: it is one more whole copy kernel, not one load, and the report does not
count cycles — so this is counted off the emitted instructions rather than measured.**
The dispatch expected "0 or one load"; that is not what an `INPUT_TDM` lane costs. The
generated `C1_XIN_CODEC_02_process` is the same kernel as `C1_XIN_CODEC_01`'s: about
20 setup instructions, then a 16-iteration loop of four (`dm` read, `ashift` by -3,
`dm` write, `nop`) — on the order of **85 core cycles per block on chip 1**, one call
per block, at block 16. Against a chip-1 block budget in the tens of thousands of
cycles that is not a capacity question, but it is not zero and should not be recorded
as zero.

**Memory: +49 words of chip-1 DM.** `c1_rx_buf_ping` grows by 32 (16 ping + 16 pong,
the RX region going 736 → 752 words), `_buf_C1_XIN_CODEC_02[16]` is 16, and
`_rx_slot_C1_XIN_CODEC_02` is 1. One more DMA channel-lane per block, which is the
"one more lane word per block" the S71-3 option-1 estimate named, times the block.

**Image: +380 bytes on chip 1, zero on chip 2** — see §5.

## 3. `DSP4_TALK_INVERT` is readable off the part: `DIAG_BUILD_CFG2` bit 29

S71-4 recorded that the talkback polarity flag changes audio and could not be read back,
which `diag.h` states in as many words is a gap. It also recorded that both config words
are full. Both are true, so the bit had to come from somewhere, and it came from the
signature — the move `diag.h` already made once, for `DSP4_TEST_NODES` at bit 24 (S49).

**Bit 29, and not bit 25, and the difference matters.** `DIAG_BUILD_CFG2`'s signature
is `0b1100001` in bits 31..25. Narrowing it again at the bottom — bits 31..26 =
`0b110000`, flag at 25 — would make the **shipping** word `0xC0…` (rejected by every
existing decoder) and the **inverted-talkback** word `0xC2…`, which every existing
decoder accepts and reports as a shipping image. The dangerous arm would be the silent
one, which is precisely the failure this word exists to prevent.

S49 got the direction right because the signature's low bit is a 1: with
`DSP4_TEST_NODES=0` the word is still exactly `0xC2000000`. So this flag takes a
**zero** bit of the signature instead. The signature becomes `0b11 0001` in bits 31..30
and 28..25 — six bits, not contiguous — and:

| arm | `DIAG_BUILD_CFG` | `DIAG_BUILD_CFG2` | a decoder masking `0xFF`/`0xFE000000` |
|---|---|---|---|
| shipping (`=0`) | `0xCF45FF10` | `0xC2010244` | accepts, decodes correctly — unchanged |
| inverted (`=1`) | `0xCF45FF10` | `0xE2010244` | **rejects**: "not a `DIAG_BUILD_CFG2` word" |

Both words above were read **out of the linked images**, at `_diag_build_cfg2`
(`0x964ff` in `chip1.sym.json`), not computed:

```
shipping : 000964fc: d5b4000100 2026081200 cf45ff1000 c201024400
inverted : 000964fc: d5b4000100 2026081200 cf45ff1000 e201024400
```

and `tools/dsp/cfg_words.py` independently predicts `0xC2010244` / `0xE2010244` for the
two arms. The shipping word is **the same value `HEAD`'s `cfg_words.py` predicts**, so
no existing record of a shipping image's config word is invalidated.

Changed for it: `src/diag.h` (the layout comment, the `DIAG_CFG2_TALK_INVERT` guard and
the `DIAG_BUILD_CFG2_VALUE` term), `tools/pi/dsp4_buildcfg.py` (`SIGMASK2 = 0xDE000000`,
the flag in `FLAGS2`, `SHIPPING2['DSP4_TALK_INVERT'] = 0`), `tools/dsp/cfg_words.py`
(the `WORD2` list and the `w2` term), and the note in `build.sh` beside the flag, which
said "known gap" and now says where the bit is. `check_shipping_config.sh` passes:
"shipping config: consistent".

**Default is still 0.** Nothing here turns the polarity flip on; PW's ruling between
the sign in the node and the rev D board mod (swap `C4`/`C11` at IN4) is untouched.

**Written down in `diag.h` for whoever comes next:** the signature is now six bits and
bits 23..0 are full. The next flag of this kind needs the third word
(`DIAG_BUILD_CFG3`, already designed in `MW/D32/DSP/dsp4-s28-20260911.md` §3 and
printed by `cfg_words.py --design-cfg3`), not a seventh narrowing.

## 4. `shared/dsp4-logic/slot-map.csv`

Landed, per the dispatch. Rows 34–37 and 80–81:

```
A_I4,0,CODEC_RET_1,BOTH,AK4619 ADC1 Lch (aux in L; mini-jack tip) - NETLIST
A_I4,1,CODEC_RET_2,BOTH,AK4619 ADC1 Rch (aux in R; mini-jack ring) - RECEIVED S72
A_I4,2,CODEC_RET_3,BOTH,AK4619 ADC2 Lch (IN3) - not connected on rev C; no consumer
A_I4,3,CODEC_RET_4,BOTH,AK4619 ADC2 Rch (IN4) - talkback XLR J1; inverted at the connector - MEASURED S70
MIX_1,9,XFER_CODEC_AUX_L,BOTH,superset input pass-through chip1->chip2 (codec aux in L = CODEC_RET_1)
MIX_1,10,XFER_CODEC_AUX_R,BOTH,codec aux in R = CODEC_RET_2
```

This corrects three wrong lane names **and the wrong part number** — the rows said
AK4916; the board carries an AK4619.

S71-5's reason for not landing it was the hash stamp, and it behaved exactly as S71
measured. `gen_slot_map.py` re-run: `source_hash` moves
`sha256:2c53de21b8c80973…` → `sha256:c4a3ca82f956b9c5…`, and the diff against the
committed `generated/dsp4_slot_map.vh` is **that one comment line and nothing else**.
The HDL is identical, so no bitstream needs rebuilding and none was. `sport_map.json`
moves the same hash plus the eight `note` strings; `dsp.csv` regenerates
**byte-identically** from the new `sport_map.json`, confirmed by `cmp` — the notes are
not build inputs.

🔴 **One consequence needs the hub, and it is not a reason to have withheld the edit.**
The shipping CPLD manifest `bitstream/dsp4_logic.ed70d3214c29.manifest` records
`slot_map: sha256:2c53de21…`, which no longer matches the committed slot map. **That
manifest was deliberately not touched**: it records what the bitstream was actually
built from, and rewriting it would falsify provenance to tidy a stamp. The bitstream is
still correct — the HDL never changed — but the hub should decide how the move is
recorded (a contract-note line, or a re-stamp on the next CPLD build). See §6.

## 5. Proof without the unit

The pair was built here with a plain `./build.sh` at `defs-v2026.09.16.5`, and **NOT
DEPLOYED**. The unit was not touched this session; the S70 shipping restore stands.

| build | chip1.ldr md5 | bytes | chip2.ldr md5 | bytes |
|---|---|---|---|---|
| **S72 shipping** (`DSP4_TALK_INVERT=0`) | `7d1ab146447a1f9d7c010ce9fa104e56` | 452,388 | `3a9c950d3551b6c5d7ff58925a47ec81` | 307,980 |
| S72 `DSP4_TALK_INVERT=1` | `10a413005e0647f5c66476f6a0b4ab60` | 452,388 | `e88a7a4302950d088a6c023c949c916e` | 307,980 |
| S71 shipping, for reference | `abd2bea9fb0da81722861c52e3b06af8` | 452,008 | `3a9c950d3551b6c5d7ff58925a47ec81` | 307,980 |

Chip 1 grows **380 bytes** — the new node's kernel and tables. **Chip 2's shipping image
is byte-identical to S71's and to the shipping chip 2 on record since S67**: the whole
change is chip 1's, as a chip-1 input rewiring should be. The shipping arm was built
twice, second time after the inverted arm, and reproduced both md5s exactly.

**Between the two arms, three bytes differ in total**, each one accounted for:

```
chip1: 2 bytes   114892  302 -> 342   (0xC2 -> 0xE2, the DIAG_BUILD_CFG2 signature bit)
                 290584  115 -> 315   (0x4D -> 0xCD, the sign of the Q4.28 scale constant)
chip2: 1 byte    134588  302 -> 342   (0xC2 -> 0xE2, the same config word)
```

So the polarity flip still costs zero cycles and zero words (S71-2 stands), and the new
diag bit costs zero cycles and zero words as well. **Chip 2 now differs between the two
arms**, which it did not in S71 — the config word is per-image and both chips carry it.
That is correct: an image says what it was built with. The **shipping** chip 2 does not
move.

### `XFER_CODEC_AUX_R` reads `_buf_C1_XIN_CODEC_02` — read off the linked image

Under `DSP4_BLOCK_KERNELS` the XFER node's own kernel is an `rts`; `_gather_chip1`
walks a pointer table that `gen_block_io` points straight at the source buffer. So the
table is where the proof is. From `build/chip1.map.xml`:

```
_buf_C1_XIN_CODEC_01  0x95ae5
_buf_C1_XIN_CODEC_02  0x95af9
_buf_C1_XIN_CODEC_03  0x95b0d
_buf_C1_XIN_CODEC_04  0x95b21
_c1_ic_tx_ptrs        0x9030d
```

`XFER_CODEC_AUX_R` is entry **26** of `_c1_ic_tx_ptrs` (25 bus sends, then
`XFER_CODEC_AUX_L` at 25), so its slot is word `0x9030d + 26 = 0x90327`.
`elfdump -nxs sec_dmda build/chip1.dxe`:

```
00090324: 00090e6c00 00090e8c00 00095ae500 00095af900
                                 ^0x90326     ^0x90327
```

`0x90326` = `0x95ae5` = `_buf_C1_XIN_CODEC_01` (aux L, slot 0, the mini-jack tip) and
`0x90327` = `0x95af9` = **`_buf_C1_XIN_CODEC_02`** (aux R, slot 1, the mini-jack ring).
`_buf_C1_XIN_CODEC_03`'s address `0x95b0d` appears **zero** times anywhere in that
table: the not-connected lane feeds nothing, as intended.

### S71's fix is still in place

Checked in the same image, because a rewiring session should prove it did not undo the
last one. `elfdump -ns sec_swco_ovf build/chip1.dxe`:

```
.tk_go_C1_TALK_01:
0018b2ac   1000 0009 5b21   r0=dm (_buf_C1_XIN_CODEC_04);
.tk_go_C1_TALK_02:
0018b30a   1000 0009 5b35   r0=dm (_buf_C1_XIN_MEMS);
```

`0x95b21` = `_buf_C1_XIN_CODEC_04` = slot 3 = the talkback XLR J1, which is what S70
measured. `C1_TALK_02` still reads the MEMS mic. The scale constant loaded two
instructions earlier is `0x4d800000` — **positive**, i.e. this is the polarity-OFF
image, as the default requires.

### The `MeasChan` codes did not move

`TEST_MEAS_LANE_CODES` in `dsp_codegen.py` is a dict keyed by node id, so adding a node
cannot renumber it: 51 = `C1_XIN_CODEC_01`, 52 = `C1_XIN_CODEC_03`, 53 =
`C1_XIN_CODEC_04`, 54 = `C1_XIN_MEMS`, exactly as the S70 capture set
(`MW/D24/DSP/s70/data/`) was taken against. **The new lane has no code** — see §6.

## 6. 🔴 Notes for the hub

**S72-a. The new lane cannot be measured, and the S71 §6d bench note is now wrong.**
`C1_XIN_CODEC_02` has no `TEST_MEAS_LANE_CODES` entry, so nothing can watch slot 1 on
the part. Allocating one (55 is free) is a **wire-contract** allocation — S71 recorded
those four codes as "the wire contract the S70 capture data was taken against" — and no
gate of this dispatch covers it, so it was not done. It is cheap when the hub wants it:
codes only, no cell, no address, every emitted line inside `#if DSP4_TEST_NODES`.

It matters because S71 §6d's owed bench measurement now expects the wrong thing. That
note reads "tip moves 51 and nothing else; **ring moves NOTHING**, because slot 1 has no
lane". Slot 1 now has a lane. Replacement text, for whoever takes the next unit session:

> **Bench note, next unit session (supersedes S71 §6d).** Put a cable in the mini-jack
> and drive tip and ring separately with a known tone. With a code allocated for
> `C1_XIN_CODEC_02`, watch it and 51 and 52 under `TEST_MEAS`: expect **tip moves 51
> only, ring moves the new code only**, and 52 (IN3) moves on neither. Without a code
> for the new lane, slot 1 can still only be reached indirectly — drive the ring and
> watch `C2_CODEC_AUX_IN`'s right leg with `C2_CODEC_AUX_IN` turned on, which measures
> the whole path rather than the converter lane. Tip moving 51 *and* the ring path
> together means the two are summed somewhere the netlist does not show; the ring
> moving 52 means IN3 is connected on this board and the rev C netlist is wrong.
>
> Watch the level: the mini-jack goes into MIC GAIN AMP 1 and the init image comes up
> with `04H = 0xBB` — MGN1L and MGN1R both at **+27 dB**. Wind `04H` down to `0x22`
> (0 dB) before driving it, or drive at about −40 dBu.

**S72-b. The CPLD slot-map stamp move needs recording somewhere.** §4: the committed
slot map now hashes `c4a3ca82…` while the shipping bitstream's manifest records
`2c53de21…`. The HDL and the bitstream are unchanged and the manifest was left
truthful. The hub's call is whether that goes in the contract release note, or waits
for the next CPLD build to re-stamp.

**S72-c. The hand-off rows S71 §6a/§6b listed are still owed and now have one more
row.** `defs` `common/topology/diagram-master.csv` (`io.codecaux`, `tb`) and mx26
`docs/d24-tdm-map.csv` row I4 / `docs/d24-signals-index.md` lines 139/219/820 still
carry the old reading, and the I4 row should now also say that `CODEC_RET_2` is
received. This repo is a consumer of `defs` and does not edit it.
