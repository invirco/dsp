provenance: AI-drafted 2026-09-19 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S71 — the codec-return lanes named from the measured map, and the talkback fed from the slot that carries it

Desk only, 2026-09-19. No unit was touched: no boot, no flash, no config, no rails.
Everything below is the generator, the assembler, the linker and the netlist.

S70 measured which TDM slot the talkback XLR arrives on. This session writes that
answer into the graph.

## 1. The map

Four rows, and only one of them is a measurement. The other three are the netlist,
marked as such, because a netlist walk that has been confirmed once on the part is
worth more than a name someone guessed and nobody checked — which is exactly what
the three lane labels replaced here were.

| TDM slot | AK4619 channel | pins | what is on the pins | cell | evidence |
|---|---|---|---|---|---|
| 0 | ADC1 Lch | `IN1P` / `IN1N` | mini-jack **TIP** — aux in L | `C1_XIN_CODEC_01` | **NETLIST** |
| 1 | ADC1 Rch | `IN2P` / `IN2N` | mini-jack **RING** — aux in R | *(no cell — not received)* | **NETLIST** |
| 2 | ADC2 Lch | `IN3P` / `IN3N` | **nothing — both are one-pin nets** | `C1_XIN_CODEC_03` | **NETLIST** |
| 3 | ADC2 Rch | `IN4N` / `IN4P` | **talkback XLR J1**, hot on the N leg | `C1_XIN_CODEC_04` | **MEASURED** (S70-1) |

Three independent things have to agree for that table to mean anything, and they do.

**The part's slot order is fixed and is not a setting.** The AK4619 puts its ADC pair
on `SDOUT1` as ADC1 Lch, ADC1 Rch, ADC2 Lch, ADC2 Rch — datasheet Table 2 mode 10
(TDM256, I²S compatible, `TDM`=1 `DCF`=010) and the `SDOUT1` row of Figure 19. There
is no register that permutes it.

**The register image in use does not re-point any channel.** The image H1S1's
`StartAK4619()` writes (S69, `tools/pi/codec4619.py` `INIT_IMAGE`) decodes as
`01H = 0xAC` → TDM=1 DCF=2 → TDM256 I²S compatible, 32-bit slots; `02H = 0x10` →
slot-length basis; and **`0BH = 0x00` → all four of AD1L/AD1R/AD2L/AD2R differential**,
i.e. every ADC channel reads its own pin pair. So channel *n* is pin pair *n* and slot
order is channel order.

**The netlist fixes the pins.** From mx26 `docs/d24-analog-paths.csv`, by path id:

- `P0397` `analog:U3 IN1P` ← `minijack:J1 TIP` through `analog C17`; `P0396` `IN1N` —
  "nothing else on the start net" (grounded through `C16`).
- `P0395` `analog:U3 IN2P` ← `minijack:J1 RING` through `analog C15`; `P0394` `IN2N` —
  nothing else on the net.
- `P0392` / `P0393` `IN3N` / `IN3P` — **"net ends here: #00694 has no other pin"** and
  the same for `#00693`. IN3 is not connected on rev C.
- `P0001` `analog:J1 HOT` (XLR pin 2) → `analog:U3 IN4N` through `C4`;
  `P0002` `analog:J1 COLD` (pin 3) → `IN4P` through `C11`.

Note the two different J1s: `minijack:J1` is the stereo mini-jack, `analog:J1` is the
talkback XLR. They are different connectors on different sheets and the collision is
a good part of how the original labels went wrong.

**And slot 3 is the one that was measured.** S70 closed PW's AUX 1 → J1 loop and drove
it over 40 dB: slot 3 followed the oscillator at **+41.75 dB constant to 0.003 dB**
while slots 0 and 2 did not move at all across the whole sweep. The rails witness said
the same thing on its own — raising AN_EN lifted slot 3's tone-off floor from −83.06 to
−69.19 dBFS and left slots 0 and 2 exactly where they were.

### Why slot 1 is not received, and why that is not a SPORT setting

`cs_mask` on this lane is `0x000D` = slots 0, 2, 3. Nothing configures that number
directly. `lane_layout()` in `tools/dsp/dsp_codegen.py` builds each lane's channel-select
mask **from the slots of the nodes declared on it**:

```
for slot, _ in slots:
    cs |= (1 << slot)
```

There are three codec INPUT_TDM nodes in the graph — slots 0, 2 and 3 — so the mask is
1 + 4 + 8 = 13. Slot 1 is absent because there has never been a `C1_XIN_CODEC_02` row
in `superset_c1`, not because a SPORT register was set to exclude it. Adding the lane is
one line in `gen_dsp_csv.py`; whether to add it is S71-3 below.

## 2. What changed in the graph

`tools/dsp/gen_dsp_csv.py`, and nothing else decides this:

| | before | after |
|---|---|---|
| `C1_XIN_CODEC_01` label | `Codec ADC 1 (TB XLR)` | `Codec ADC 1 (Aux In L / mini-jack tip)` |
| `C1_XIN_CODEC_03` label | `Codec ADC 3 (Aux In L)` | `Codec ADC 3 (ADC2 L / not connected)` |
| `C1_XIN_CODEC_04` label | `Codec ADC 4 (Aux In R)` | `Codec ADC 4 (TB XLR)` |
| `C1_TALK_01` input | `C1_XIN_CODEC_01` | **`C1_XIN_CODEC_04`** |
| `XFER_CODEC_AUX_L` source | `C1_XIN_CODEC_03` | `C1_XIN_CODEC_01` |
| `XFER_CODEC_AUX_R` source | `C1_XIN_CODEC_04` | `C1_XIN_CODEC_03` *(placeholder — see S71-3)* |
| `C1_TALK_02` input | `C1_XIN_MEMS` | `C1_XIN_MEMS` — **unchanged, stated** |

A clean three-way rotation. No node added, none removed, no allocation order disturbed.

**The cell names do not move.** `Talk[1-4]Gain[1-1]`, `CodecAux…` and every other cell
in the contract is exactly where it was; only the internal lane labels and the wiring
between nodes changed. That is the invariant the hub holds and this session did not
touch it.

`C1_TALK_02` stays on the MEMS mic. The graph always had that one right: the MEMS is
its own lane on sport 7 slot 5 and has nothing to do with the codec.

## 3. The polarity option — a branch, not a decision

The talkback arrives **inverted by wiring**: J1 pin 2 (hot) lands on the codec's `IN4N`
and pin 3 (cold) on `IN4P`. The netlist said so, S70-6 T5 measured it (+181.56° at DC,
extrapolated from a 21-point unwrapped phase scan), and the AK4619 has no polarity bit
to undo it with. So the fix is a sign in the DSP or a board mod, and that is PW's call.

`DSP4_TALK_INVERT` makes it a one-line flip. **Default 0. Not turned on.**

**It costs nothing — zero cycles and zero words, measured.** The node already converts
its ramped float gain to Q4.28 by multiplying by 2²⁸ before the `fix`:

```
    r2 = 0x4D800000;      /*  2^28 */
    f2 = r2;
    f1 = f1 * f2;
    r1 = fix f1;
    r0 = dm(_buf_C1_XIN_CODEC_04);
    mrf = r0 * r1 (ssi);
```

With the flag set, the *same instruction* loads `0xCD800000` = −2²⁸ instead. Negating
the gain negates the sample. The proof is the image:

| build | chip1.ldr md5 | bytes | chip2.ldr md5 |
|---|---|---|---|
| `DSP4_TALK_INVERT=0` (shipping) | `abd2bea9fb0da81722861c52e3b06af8` | 452,008 | `3a9c950d3551b6c5d7ff58925a47ec81` |
| `DSP4_TALK_INVERT=1` | `1e00eacdb19f144be3d1ca2fab6da4e6` | 452,008 | `3a9c950d3551b6c5d7ff58925a47ec81` |

`cmp -l` between the two chip-1 images reports **exactly one differing byte**, at offset
290336: `0115` → `0315` octal, i.e. `0x4D` → `0xCD`. Same size, same everything else.

The flag is scoped by a node param, `invert_opt=DSP4_TALK_INVERT`, which
`gen_dsp_csv.py` puts on `C1_TALK_01` only. `C1_TALK_02` emits no `#if` at all and its
constant is the plain `0x4D800000` — the MEMS mic is not inverted and must not move when
PW rules.

It is wired through `MW/D32/DSP/SHARC/build.sh` and named in `shipping.config` as 0.
Without that it would have been a flag that silently did nothing, which is the S11-1
trap: the first `DSP4_TALK_INVERT=1 ./build.sh` here produced a byte-identical image
because `build.sh` forwards only the defines it names.

## 4. The proof, without the unit

**The TALKBACK reads the lane S70 measured — read off the linked image, not the source.**
`elfdump -ns sec_swco_ovf build/chip1.dxe`, at `_C1_TALK_01_process`:

```
.tk_go_C1_TALK_01:
0018b2a4   0f02 4d80 0000   r2=0x4d800000;
0018b2a7   703f 013f        r2=r2;
0018b2a9   cf12             f1=f1*f2;
0018b2aa   018c 9110        r1=fix f1;
0018b2ac   1000 0009 5b05   r0=dm (_buf_C1_XIN_CODEC_04);
```

The operand encoded in that load is `0x95b05`. `build/chip1.sym.json` gives
`_buf_C1_XIN_CODEC_04 = 0x95b05` — and `_buf_C1_XIN_CODEC_01 = 0x95add`,
`_buf_C1_XIN_CODEC_03 = 0x95af1`, which is what it used to be. `C1_XIN_CODEC_04` is
`CODEC_RET_4`, sport 4 slot 3, which is `TEST_MEAS_LANE_CODES` **MeasChan 53** — the
code every row of the S70 capture set (`MW/D24/DSP/s70/data/`) was taken on. The
talkback node now reads the buffer whose tap S70 watched move.

`C1_TALK_02`, a few instructions further on, reads `0x95b19` = `_buf_C1_XIN_MEMS`, unchanged.

**The MeasChan codes themselves did not move.** 51/52/53/54 are the wire contract the
S70 data was captured against; renumbering them would make that data unreadable. Only
their comments changed, which said "talkback XLR J1" against code 51 and were wrong in
the same way the labels were.

**The inter-chip gather follows.** `_c1_ic_tx_ptrs[43]` in `src/chip1/block_io.asm` is
indexed by global mix slot; slot 25 (`XFER_CODEC_AUX_L`) now holds
`_buf_C1_XIN_CODEC_01` and slot 26 (`XFER_CODEC_AUX_R`) holds `_buf_C1_XIN_CODEC_03`.

**Nothing in the contract moved.** After `./regenerate-dsp-contract.sh`, `git status`
lists twelve files and **not one of them is an address artefact**:

- `MW/D32/DSP/dsp_address_map.md` — **unchanged**, all 5,827 rows.
- `MW/{D12,D16,D24,D32}/MX/_matrix.csv` — **unchanged**, byte for byte. D32 5,780/5,780
  and D24 3,989/3,989 mapped cells still carry an address.
- `MW/D32/DSP/ghost_cells.h`, `src/chip*/dsp_params.asm` — **unchanged**.
- `dsp.csv`: 700 nodes before and after, chip 1 441 / chip 2 259 before and after, and
  `c1_alloc` still ends at page 1 addr 4983 / chip 2 page 1 addr 2175. **0 addresses
  moved.** The only changed columns on the six changed rows are `label`, `inputs`,
  `outputs` and — on `C1_TALK_01` alone — the added `invert_opt` param.

`./check-contract-drift.sh` → "SHARC codegen drift check passed (tree == generator
output)", and the tree it leaves holds no diff beyond the twelve files above.

**The pair.** Built at `defs-v2026.09.16.5` with a plain `./build.sh`:

| | md5 | bytes |
|---|---|---|
| `chip1.ldr` | `abd2bea9fb0da81722861c52e3b06af8` | 452,008 |
| `chip2.ldr` | `3a9c950d3551b6c5d7ff58925a47ec81` | 307,980 |

Chip 2 is **byte-identical to the shipping chip 2** on record since S67 — the whole
change is chip 1's, as a chip-1 input rewiring should be. Chip 1 moves from `87126eb6`
(the S70 shipping image) to `abd2bea9`. **NOT DEPLOYED.** The unit was not touched this
session and the S70 shipping restore stands.

## 5. Findings

**S71-1. The three codec-return lane labels were all wrong, and in a way that put the
talkback into the main mix.** `C1_XIN_CODEC_01` "Codec ADC 1 (TB XLR)" is slot 0, the
mini-jack tip. `C1_XIN_CODEC_04` "Codec ADC 4 (Aux In R)" is slot 3, the talkback XLR —
and it was the one wired to `XFER_CODEC_AUX_R`, so the talkback mic went to
`C2_CODEC_AUX_IN` and into MAIN, while `C1_TALK_01` read a mini-jack that is usually
unplugged. Renamed and rewired from the table in §1.

**S71-2. The talkback is inverted by wiring and the option to undo it is in, off, and
free.** `DSP4_TALK_INVERT`, default 0, on `C1_TALK_01` only, one byte of image
difference and no size change. PW's ruling is between this and swapping `C4`/`C11` at
IN4 on rev D; nothing here assumes either.

**S71-3. 🔴 THE AUX-IN RIGHT LEG HAS NO LANE, AND THIS SESSION DID NOT INVENT ONE.**
The mini-jack ring is slot 1 and slot 1 is not received. So `XFER_CODEC_AUX_R` is
parked on slot 2, which is IN3, which is **not connected on rev C** — it carries the
converter's own floor and nothing else. That is a placeholder chosen because it is the
only option that changes no behaviour it does not have to: it stops the talkback
reaching MAIN, which is the defect, without deciding what aux R should be. The question
is in the dispatch block for the hub.

**S71-4. `DSP4_TALK_INVERT` cannot be read back off the part, and by `diag.h`'s own rule
it should be able to be.** The rule is stated there in as many words — "a switch that
changes cost or audio and cannot be read back is a gap the next session pays for" — and
this flag changes audio. There is no bit for it: `DIAG_BUILD_CFG` has 31..24 signature,
23..8 allocated and 7..0 = `DSP4_BLOCK_SIZE`; `DIAG_BUILD_CFG2` has 23..0 allocated
(S18 spent the last two) and its signature already narrowed from eight bits to seven so
S49 could have bit 24 for `DSP4_TEST_NODES`. Finding a bit means narrowing that
signature again — breaking every seven-bit decoder — or a third word. Hub's call; left
as a gap, named, in `build.sh` beside the flag.

**S71-5. `shared/dsp4-logic/slot-map.csv` carries the same wrong names and was
deliberately NOT edited here.** Rows `A_I4,0..3` say "AK4916 ADC ch1 (talkback XLR)",
"…ch3 (aux in L)", "…ch4 (aux in R)" — three errors and the wrong part number (the
board has an AK4619; mx26's `d24-tdm-map.csv` already flags the AK4916/AK4619 mix-up
against this row). A note-only edit is not free: `gen_slot_map.py` hashes the two source
CSVs into the generated Verilog header, so changing a comment moves
`source_hash` from `sha256:2c53de21…` to `sha256:d778a1ac…` — measured in a scratch
copy, where the diff against the committed `dsp4_slot_map.vh` is **that one line and
nothing else**. The HDL is identical and the bitstream would be identical, but the
stamp would read as a CPLD source change. Handed to the hub in §6 so it lands with
whatever re-stamp it wants.

## 6. Hand-off

### 6a. `defs` — `common/topology/diagram-master.csv`

The `io.codecaux` and `tb` entries carry the old reading. The hub lands these; this
repo is a consumer and does not edit `defs/`.

- `io.codecaux` — its source description must become **aux in L = codec slot 0
  (ADC1 Lch, IN1P, mini-jack tip); aux in R = mini-jack ring on slot 1, NOT RECEIVED
  today**, not slots 2/3.
- `tb` instance 1 — source is **codec slot 3 (ADC2 Rch, IN4, talkback XLR J1)**, not
  codec ADC channel 1. Instance 2 (MEMS) is correct and unchanged.
- Either entry may also want the polarity note: the talkback path is inverted at the
  connector until `DSP4_TALK_INVERT` or a rev D mod says otherwise.

### 6b. mx26 — `docs/d24-tdm-map.csv`, row `I4`

Column `carries`, currently:

```
CODEC_RET_1..4 (talkback XLR; aux in L/R)
```

should read:

```
CODEC_RET_1 = aux in L (mini-jack tip); CODEC_RET_2 = aux in R (mini-jack ring, NOT RECEIVED); CODEC_RET_3 = ADC2 L (IN3, not connected); CODEC_RET_4 = talkback XLR J1 (inverted at the connector) — slot order MEASURED S70/S71
```

The same string appears twice in `docs/d24-signals-index.md` — line 139 (the
`DSPA DAI1 pin01 | I4 | CODEC_ADC` row) and line 219 (the `**carries**` bullet) — and
both want the same replacement. Line 820 of that file says the stereo aux input
"probably … lands on CODEC_RET_3/4"; it lands on CODEC_RET_1/2, and it is no longer a
probably.

While that row is open: it names the part **AK4916**. The board has an **AK4619**
(`analog U3`), which `docs/d24-analog-paths.md` and the datasheet this session read both
confirm. The row's own note already says the codec is on the analog board; the part
number is the remaining half of that correction.

### 6c. This repo — `shared/dsp4-logic/slot-map.csv`, rows 34–37

```
A_I4,0,CODEC_RET_1,BOTH,AK4619 ADC1 Lch (aux in L, mini-jack tip) - NETLIST
A_I4,1,CODEC_RET_2,BOTH,AK4619 ADC1 Rch (aux in R, mini-jack ring) - NOT RECEIVED, no DSP node
A_I4,2,CODEC_RET_3,BOTH,AK4619 ADC2 Lch (IN3) - not connected on rev C
A_I4,3,CODEC_RET_4,BOTH,AK4619 ADC2 Rch (IN4) - talkback XLR J1, inverted at the connector - MEASURED S70
```

and rows 80–81, whose notes still say `codec aux in L = CODEC_RET_3` /
`codec aux in R = CODEC_RET_4`; they are now `CODEC_RET_1` and (pending S71-3)
`CODEC_RET_3` as a placeholder. Not landed here for the reason in S71-5.

### 6d. The bench measurement still owed

One thing in §1 is netlist and not measurement: which of the mini-jack's two conductors
lands where. The netlist is unambiguous (tip → IN1P → slot 0, ring → IN2P → slot 1) but
it has never been seen move.

> **Bench note, next unit session.** Put a cable in the mini-jack and drive the tip and
> the ring separately with a known tone. Watch MeasChan 51 (slot 0) and 52 (slot 2)
> with `TEST_MEAS`, as S70 did for the XLR. Expect: **tip moves 51 and nothing else;
> ring moves NOTHING**, because slot 1 has no lane and slot 2 has no pins. A ring that
> moves 51 means the two are summed somewhere the netlist does not show; a ring that
> moves 52 means IN3 is connected on this board after all and the rev C netlist is
> wrong about it. Either result changes §1 and both are worth ten minutes.
>
> Watch the level. The mini-jack goes into MIC GAIN AMP 1, and the init image comes up
> with `04H = 0xBB` — **MGN1L and MGN1R both at +27 dB**. A line-level source there
> will clip hard. Wind `04H` down to `0x22` (0 dB both) before driving it, or drive it
> at about −40 dBu and read the level rather than the clipping.
