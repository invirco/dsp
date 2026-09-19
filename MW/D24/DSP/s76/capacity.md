provenance: AI-drafted 2026-09-19 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S76 — the code-pool wall taken down, and the ceiling as the record actually holds it

Desk session, read-only. The unit was not booted, flashed, configured or
powered, and **no new measurement was taken on the part**. Everything below is
either built here, read off a linker map, read out of a disassembly, or read
out of a recorded capacity golden — and every number says which.

## 0. Outcome in one paragraph

**Gate 1 is met with room to spare.** `DSP4_SHARED_KERNELS=15` is named in
`shipping.config` and the shipping pair is rebuilt: chip 1's code pool goes
from 253,238 of 262,144 bytes (96.6 %, **8,906 free**) to 157,590 (60.1 %,
**104,554 free**), and the `DSP4_EXTRAM=1` arm — the one S75-5 left with 946
bytes of air — links with **96,594 free**. 95,648 bytes reclaimed, accounted
to the byte, nothing removed. The audio is proved bit-exact on the MACHINE
CODE: a new tool disassembles both arms and requires all 128 nodes of the four
shared classes to issue the same instruction sequence touching the same
absolute addresses, and it is shown to be able to fail. **Gate 2 could not be
measured** — a driven capacity run needs a boot, a logic load and a config
burst, and this session had none of them — so §3 gives the ceiling as the
recorded driven rows actually hold it, which turns out to be the more
important answer: **the configuration that ships does not fit either product
and has not been re-measured since 2026-09-10**, while the configuration with
the pairing rung in the graph runs **32 channels on chip 1 with 22.0 points of
margin at 983.04 MHz and 32.8 channels at 786.432 MHz**. **Gate 3: the rung is
LANDED**, the `_bq_fx_cascade_simd` hang was root-caused and closed in D44, and
it still builds clean on today's tree with 80,726 bytes of chip-1 code to
spare. What is not landed is the ruling to ship it.

---

## 1. Gate 1 — chip 1's program memory

### 1.1 The map, before

`tools/dsp/dsp_memreport.py` on the S74c pair (`chip1.ldr`
`10a413005e0647f5c66476f6a0b4ab60`):

| pool | chip 1 | chip 2 |
|---|---|---|
| code (VISA SW) | 253,238 / 262,144 — **96.6 %, 8,906 free** | 134,000 — 51.1 % |
| &nbsp;&nbsp;tier 1 `sec_swco` (Block 3) | 131,070 / 131,072 — 100.0 % | 130,776 — 99.8 % |
| &nbsp;&nbsp;tier 2 `sec_swco_ovf` (Block 2) | 122,168 / 131,072 — **93.2 %, LAST TIER** | 3,224 — 2.5 % |
| DM data + stack | 263,780 — 70.3 % | 238,596 — 63.6 % |
| delay lines | 506,880 — 24.5 % | 1,694,112 — 81.7 % |

Tier 2 is the last tier: there is no region behind it. `dsp_memreport.py`
raised its WARN on this arm.

`tools/dsp/dsp_codepool.py --by class` says what was in it. Nine per-strip
classes, 32 copies each, are 89 % of the pool:

| class | bytes | each | | class | bytes | each |
|---|--:|--:|---|---|--:|--:|
| RTG | 54,400 | 1,700 | | FDR | 15,040 | 470 |
| GATE | 32,896 | 1,028 | | TUBE | 12,480 | 390 |
| COMP | 32,000 | 1,000 | | GAIN | 6,336 | 198 |
| FILT | 30,976 | 968 | | IN | 4,032 | 126 |
| EQ | 21,248 | 664 | | DLY | 16,384 | 512 |

### 1.2 The lever, and why it was available

Four of those classes already have a shared form in the tree — the generator
emits both arms of each node under `#if (DSP4_SHARED_KERNELS & <bit>)` and the
one body under the same test in `src/chip1/shared_kernels.asm`. COMP and TUBE
landed in S18, GATE and FILT in S26, and `shipping.config.s20/.s21/.s26/.s32`
have all carried the switch since. **`shipping.config` itself never named it.**
It sat at `build.sh`'s default of 0 while every fit table since S20 priced it
at 15 — which is the exact shape of findings S8-2/S9-1, in the one file that
exists so that shape cannot recur (finding S76-2).

Nothing was invented here. The switch was turned on, in the file that decides
the shipping configuration, and the consequences were measured.

### 1.3 The map, after

| arm | chip 1 code | free | chip 2 code |
|---|--:|--:|--:|
| shipping, `SHARED_KERNELS=0` (the control) | 253,238 — 96.6 % | 8,906 | 134,000 — 51.1 % |
| **shipping, `=15` (LANDED)** | **157,590 — 60.1 %** | **104,554** | 134,000 — 51.1 % |
| `EXTRAM=1`, `=0` (S75's arm) | 261,198 — 99.6 % | 946 | 135,082 — 51.5 % |
| **`EXTRAM=1`, `=15`** | **165,550 — 63.2 %** | **96,594** | 135,082 — 51.5 % |

Tier 2 falls from 93.2 % to **20.2 %** on the shipping arm. `dsp_memreport.py`
now exits clean — "all pools below 90 %" — for the first time in this record.

The gate asked for ≥ 8 KB free on the shipping pair with the EXTRAM arm still
linking. The shipping pair has **102.1 KB** free and the EXTRAM arm links with
**94.3 KB** free, so the gate is met on either reading of it.

DM data and the delay lines do not move.

### 1.4 Every byte accounted

`dsp_codepool.py --diff`, shipping arm, mask 0 → mask 15:

| class | before | after | each before → after | delta |
|---|--:|--:|:--|--:|
| GATE | 32,896 | 2,304 | 1,028 → 72 | **−30,592** |
| COMP | 32,000 | 2,304 | 1,000 → 72 | **−29,696** |
| FILT | 30,976 | 2,624 | 968 → 82 | **−28,352** |
| TUBE | 12,480 | 2,304 | 390 → 72 | **−10,176** |
| `shared_kernels` | 0 | 3,168 | the four bodies, once each | **+3,168** |
| | | | **total** | **−95,648** |

−30,592 − 29,696 − 28,352 − 10,176 + 3,168 = −95,648, and 253,238 − 95,648 =
157,590, which is what the linker says. No other object changes size by one
byte; `cgu_init`'s 180 bytes, `diag`'s 1,356 and the other 49 rows are
identical in both maps.

**Nothing is removed.** Thirty-two copies of a kernel become one copy plus
thirty-two stubs; every node keeps its own entry point, its own record and its
own place in the chain. S22 completeness is untouched, and no
product-defined function loses an instruction.

### 1.5 Chip 2: two bytes

Chip 2 has no strip COMP, TUBE, GATE or FILT and carries not one instruction
of `shared_kernels.asm`. Its `.ldr` is the same length as S74c's (307,980 B)
and differs from it in **exactly two bytes**:

```
byte 134585   0x44 -> 0x64      (bit 5)
byte 134586   0x02 -> 0x82      (bit 15)
```

Those are bits 5 and 15 of chip 2's own `DIAG_BUILD_CFG2` word — the two
legacy `DSP4_SHARED_KERNELS` bits — i.e. the image saying the switch is on.
Nothing else in chip 2 moved.

### 1.6 The images

| arm | chip 1 | chip 2 |
|---|---|---|
| shipping, mask 0 (control, rebuilt here) | `10a413005e0647f5c66476f6a0b4ab60` 452,388 B | `e88a7a4302950d088a6c023c949c916e` 307,980 B |
| **shipping, mask 15 (LANDED)** | `84c7951333e982204a38fe65e49d3fd6` 356,740 B | `bb2a7c6ea9e5d0caa419bc0b15a97f7c` 307,980 B |
| `EXTRAM=1`, mask 0 | `52865949b546aa1757c26b6bb73f22ba` | `1198f18ec1759b0ff09ae7346a569f75` |
| `EXTRAM=1`, mask 15 | `fd5094e63f529b18a5e83ac7abc4e8ed` 365,404 B | `50b3dec4174f6f7388e84d5763483b03` 309,132 B |

Two things to read off that table. The mask-0 control, built from the same
tree with one environment override, **rebuilds byte for byte to S74c's pair** —
so the `shipping.config` line is the only change this session makes to the
image. And the `EXTRAM=1` mask-0 arm reproduces S75's md5s to the digit, which
says this desk's toolchain and S75's are the same toolchain.

`./check-sharc-codegen-drift.sh`: **734 generated files, 0 differ, 0 absent**.

### 1.7 The audio proof, on the machine code

The change is not a placement change, so byte-identity is not available on
chip 1 and something had to prove the audio. What existed were two checks on
the generator's INPUTS — the rewrite refuses anything it cannot rewrite, and
`shared_kernel_check.py` asserts the record layout and the stub entries on the
linker map — and an argument that the shared body is the same emitter's output.
Neither reads the instructions that end up in the image, and a shared kernel
that addresses the wrong word does not fail to link, does not change the byte
count and does not look wrong in a listing.

So `tools/dsp/shk_equiv.py` was written for this session. It disassembles both
images (`elfdump -ns` over `sec_swco`, `sec_swco_ovf`, `sec_pmco`) and, for
every node of every shared class, compares

```
    canon(inline body)  ==  canon(stub minus its jump) ++ canon(shared body)
```

with `canon` resolving **every memory operand to an absolute word address**:
the inline arm's `dm (_comp_cgp_C1_COMP_01)` through the linker's symbol
table, the shared arm's `dm (0x25,i7)` through what that node's own stub
loaded into i7. The generator's two expansions are folded back before
comparing — `i0 = i7; modify(i0,0x25);` is one pointer load, not two
instructions — because the question is which WORD is touched, not how many
instructions it took.

Result, on both arms:

```
  COMP  OK    32 nodes, instruction for instruction and address for address
  TUBE  OK    32 nodes, ...
  GATE  OK    32 nodes, ...
  FILT  OK    32 nodes, ...
  shk_equiv: 128 nodes equivalent on chip 1
```

**The harness can fail.** `--mutate C1_COMP_17` shifts that one node's record
base by a single word before comparing — the precise fault the whole mechanism
risks — and the run reports 48 divergences on that node and none on any other,
then exits 0 only because the mutation was caught. A check that cannot fail is
not a proof, and this one was made to fail on purpose before it was believed.

**The one difference it allows is named and bounded.** FILT's inline body sets
`l3/l4/i3/i4` a few instructions in, behind `if eq jump .fkb_ss`, i.e. only on
the crossfade path. A stub runs before the body and has nowhere conditional to
put them, so the generator hoists those four instructions into the stub and
the shared arm executes them on every block. `shk_equiv` accepts that only
when the hoisted instructions appear verbatim as one contiguous run in the
inline stream AND nothing the shared arm can execute before that run's inline
position reads a register the hoist writes. Both hold: the four instructions
are exactly `l3=0; l4=0; i3=@00090348; i4=@00090348;`, the hoist sits at inline
index 7, and the two later reads of those registers are both after it. The
cost is four register writes per FILT node per block on blocks that would not
have made them.

### 1.8 What the lever costs in cycles

Not measured this session. What the record holds:

**Measured, driven, on the shipping configuration** — `cap-s19blk` (mask 0,
`DIAG_BUILD_CFG2 0xC2010244`) against `cap-s19s18` (mask 3, `0xC2018264`), the
same S19 session, both products, two runs. These two arms differ in exactly
the two SHARED_KERNELS bits and in nothing else the word records:

| | chip 1 mask 0 | chip 1 mask 3 | delta |
|---|--:|--:|--:|
| D24 r1 | 389,578 | 392,037 | **+2,459** (+0.75 pts) |
| D24 r2 | 389,674 | 392,135 | **+2,461** (+0.75 pts) |
| D32 r1 | 518,339 | 521,853 | **+3,514** (+1.08 pts) |
| D32 r2 | 518,146 | 522,539 | **+4,393** (+1.34 pts) |

Chip 2 over the same pair reads +60, −484, +4,853 and −4,517 cycles/block — it
carries none of the shared classes, so that column is the instrument's own
noise and is quoted to show what the noise is.

**Mask 3 → mask 15 (GATE and FILT on top)** was swept driven in S27 on the
s26 configuration: `shk3`, `shk7`, `shk11`, `shk15` sit within 0–1,706
cycles/block of each other on chip 1 with no consistent ranking across the
eight product/chip/run cells, against a run-to-run spread on the same arm of
up to 1,922 cycles/block. That is S27's own verdict — GATE and FILT cost
0.0 points driven — reproduced here from the goldens.

**Static count**, from the images built here: the stub adds 5 instructions per
node per block for COMP, TUBE and GATE (four register loads and one taken
unconditional jump) and 11 for FILT (the hoisted prologue). At 32 strips that
is 128 jumps at the measured 6.02 cycles each (D66) plus 704 register loads —
about **1,475 cycles/block, 0.45 % of budget**. The measured figure is two to
three times the static one, which is what a jump into a body the fetch unit
has not been running usually costs; the measured figure is the one to quote.

**Not measured: mask 15, driven, on the shipping configuration.** It needs the
part. See §5.

---

## 2. What the switch changed in the record

`tools/dsp/cfg_words.py` on the new `shipping.config`:

```
  DIAG_BUILD_CFG   must read 0xCF45FF10      (unchanged)
  DIAG_BUILD_CFG2  must read 0xE2018264      (was 0xE2010244)
```

and it prints its own caveat, which now applies to a SHIPPING image rather
than to a proposal:

> `DSP4_SHARED_KERNELS=15` — bits 2 (GATE) and 3 (FILT) are NOT in
> `DIAG_BUILD_CFG2`; an image built with mask 15 reads back the same two
> words as one built with mask 3, so this check does not distinguish them
> (S27-3). Identify the arm by its image md5.

A bench read WILL now show the switch is on (mask 0 → 15 moves bits 5 and 15).
What it cannot show is 3 against 15. That was tolerable while mask 15 lived
only in a proposal; it is less so now, and it is blocked behind S75-13 — S28
designed `DIAG_BUILD_CFG3` with signature 0xC3 carrying the whole mask in bits
15..8, S75 landed a `DIAG_BUILD_CFG3` with signature 0xC4 carrying EXTRAM, and
neither layout has a free bit for the other. Finding S76-10.

---

## 3. Gate 2 — the ceiling, as the record holds it

**This gate was not met as written and could not be.** S19's driven instrument
takes three rows on one boot: it builds an arm, boots both chips, loads the
`driveall` LOGIC bitstream, plays the CM4 stimulus and writes a loaded
configuration. This session was desk-only and read-only — no boot, no flash,
no config, no rails — so no row was taken. What follows is arithmetic on rows
that were taken, and each one says which file it came from.

### 3.1 The configuration that ships

`cap-s19blk-*`, driven, 2026-09-10, `DIAG_BUILD_CFG2 0xC2010244` — the
shipping switch positions:

| | chip 1 | chip 2 | blocks missed |
|---|--:|--:|--:|
| D24 r1 | 389,578 — **118.89 %** | 390,712 — **119.24 %** | 15.85 % / 16.05 % |
| D24 r2 | 389,674 — **118.92 %** | 390,736 — **119.25 %** | 15.85 % / 16.05 % |
| D32 r1 | 518,339 — **158.18 %** | 467,906 — **142.80 %** | 36.79 % / 30.00 % |
| D32 r2 | 518,146 — **158.13 %** | 472,408 — **144.16 %** | 36.79 % / 29.96 % |

The two products differ by eight strips on chip 1, so the slope is measured
rather than modelled: **16,059–16,095 cycles/block per strip = 1,004–1,006
cycles/sample**, with 3,295–4,258 cycles/block of everything else.

| chip 1, shipping configuration | at 983.04 MHz | at 786.432 MHz |
|---|--:|--:|
| budget, block 16 | 327,680 cyc/block | 262,144 cyc/block |
| 32 channels | 158.13–158.18 % | 197.66–197.73 % |
| **margin remaining at 32** | **−58.2 points** | **−97.7 points** |
| channels that fit | **20.1–20.2** | **16.1** |

### 3.2 The configuration with the pairing rung in the graph

`cap-shk15-*`, driven, 2026-09-11, `DIAG_BUILD_CFG2 0xC2019E6F` —
`STRIP_FUSED`, `SIMD_DYN`, `SIMD_GRAPH`, `SIMD_STRIPS`, `C2_BQ_GRAPH`,
`GATE_LINTHR`, `DYN_LUT` and `SHARED_KERNELS=15`:

| | chip 1 | chip 2 | blocks missed |
|---|--:|--:|--:|
| D24 r1 | 193,646 — **59.10 %** | 255,645 — **78.02 %** | 0 / 0 |
| D24 r2 | 194,154 — **59.25 %** | 255,730 — **78.04 %** | 0 / 0 |
| D32 r1 | 255,591 — **78.00 %** | 298,221 — **91.01 %** | 0 / 0 |
| D32 r2 | 255,030 — **77.83 %** | 298,511 — **91.10 %** | 0 / 0 |

Slope: **7,610–7,743 cycles/block per strip = 476–484 cycles/sample**, with
7,811–11,526 cycles/block of everything else.

| chip 1, pairing configuration | at 983.04 MHz | at 786.432 MHz |
|---|--:|--:|
| 32 channels | 77.83–78.00 % | 97.29–97.50 % |
| **margin remaining at 32** | **+22.0 / +22.2 points** | **+2.50 / +2.71 points** |
| channels that fit | **41.3–41.5** | **32.8–32.9** |

| chip 2, pairing configuration, D32 | at 983.04 MHz | at 786.432 MHz |
|---|--:|--:|
| measured | 91.01–91.10 % | **113.76–113.87 %** |
| margin remaining | +8.90 / +8.99 points | **−13.8 points** |

**PW's question, answered from measured rows: 32 basic strips real-time in one
ADSP-21564 is MET — 22.0 points of margin at 983.04 MHz and 2.5 points at
786.432 MHz — on chip 1, with the pairing rung in the graph.** The strip is
476–484 cycles/sample against the 535 the projection carried, so the rung came
in better than projected. **It is not met on the configuration that ships**,
where the same chip is 58 points over at 32 and misses a sixth of its blocks
at 24.

**Two caveats, both load-bearing.** First, the 786.432 MHz column is
arithmetic: the same measured cycles/block against a 262,144-cycle budget. No
capacity row in the whole record was ever taken at 786.432 MHz — all 1,120
chip-rows in `goldens/` read between 982.99 and 983.10 MHz — so that column
assumes cycles/block do not change with the core clock. That is true for
core-bound code and false for anything waiting on memory or a DDE, and the
delay lines, the DMA rings and the inter-chip fabric all wait on something.
The column is a projection labelled as one (finding S76-7). Second, chip 2 at
786.432 MHz does not fit at D32 on any configuration measured (finding S76-6).

### 3.3 The delta against the last measured table

The gate asked what the cue bus, the RTA, the codec lanes and the memory pool
have cost since S19's table. For three of the four the answer is exactly zero
and it is proved rather than argued:

| | switch | in the shipping image |
|---|---|---|
| cue bus (S65) | `DSP4_CUE=0` | not one byte; S65 witnessed byte-identity |
| RTA filterbank (S64/S65) | `DSP4_RTA=0` | not one byte; S65 witnessed byte-identity |
| memory pool (S75) | `DSP4_EXTRAM=0` | not one byte; S75 witnessed byte-identity, and **the mask-0 control built this session rebuilds to S74c's md5s on both chips**, which re-proves it |

The codec lanes are not behind a switch: `C1_XIN_CODEC_01..04` are four
unconditional graph nodes at 126 bytes each, 504 bytes of chip-1 code, and
they are in the image.

**And that is as far as the answer goes, because the cycle side of it has not
been measured.** The last driven run on the shipping configuration was
2026-09-10. Everything that has landed since — S42's capture fix, the S49
self-test hooks (gated, but the dispatch table is not), S54/S55/S63 the
recorded captures were taken against, S65's chain, S71's codec-return lanes,
S74's talkback polarity, S75's pool call site — is unpriced against it. Nine
days of graph growth stand between PW's priority-one number and the last time
anybody measured it (finding S76-4).

---

## 4. Gate 3 — the SIMD graph-wiring rung

**Landed. Measured. Not ruled.**

**The hang is closed, and was closed before this session.** `_bq_fx_cascade_simd`
does not hang and has not since D44 (commit `2fadf39`). The root cause is on
the record in `review-dsp-20260828.md`: `_bq_pair_blk` carried its scatter-back
pointers in registers across `_bq_fx_cascade_simd`, which writes r0–r15, so the
scatter ran on the cascade's leftovers and the state loop took
`lcntr = 0x10000000` — 268 million iterations per call, scribbling, with the
diag ISR still answering, which is why it read as a hang rather than as a
crash. The fix is five words of DM at block rate. There is a negative control:
`DSP4_BQP_NOSAVE=1` reproduces the session-2 symptom verbatim.

**The rung has been in every measured arm since `s21fx`.** `DIAG_BUILD_CFG2`
`0xC2019E6F` has `DSP4_SIMD_DYN` (bit 1), `DSP4_SIMD_GRAPH` (bit 2) and
`DSP4_SIMD_STRIPS` (bit 3) all set, and that word covers `s21fx`, `s23`,
`s23x`, `s24*`, `s25*`, `s28`, `s29*`, `s32*`, `s33*` and the whole `shk`
sweep — thirty-odd recorded driven arms.

**It still builds on today's tree**, which is the part that needed checking
after S65, S71, S74 and S75 all moved chip 1. Built here with the five s26
levers on top of the new `shipping.config`:

```
  chip 1  code 181,418 / 262,144  = 69.2 %,  80,726 free
  chip 2  code 164,554 / 262,144  = 62.8 %,  97,590 free
  chip1.ldr 723d1c9c2a8a79289d028aa2f1eb1b55  426,376 B
  chip2.ldr e52d4f51c857aefe6a77e4cf7f39022d  407,672 B
```

Not deployed. Note the headroom: S26 measured this configuration at 221,572
bytes of chip-1 code with 40,572 free, and `shipping.config.s20` — the same
configuration without the shared kernels — had **380 bytes free**. Today it
has 80,726, so `DSP4_CUE`, `DSP4_RTA`, `DSP4_TEST_NODES` and `DSP4_EXTRAM` are
no longer blocked by memory on top of it — and that is not an extrapolation,
because the arm with **all four of them on at once, on top of all five
capacity levers**, was built here too:

```
  five levers + CUE + RTA + TEST_NODES + EXTRAM + SHARED_KERNELS=15
  chip 1  code 197,796 / 262,144  = 75.5 %,  64,348 free
  chip 2  code 167,130 / 262,144  = 63.8 %,  95,014 free
  chip1.ldr 5e34129c9d6057c8668726266d67e268
  chip2.ldr 43d58019c12951446f60d5d3434bd8be
```

Every switch this project is holding open can be on at the same time and chip
1 still has 62.8 KB of code pool free. Not deployed, and none of those four is
ruled — the point is only that memory is no longer the reason to say no to any
of them (finding S76-8).

**The number PW asked to be told the moment it is measured is §3.2's:
+22.0 points of margin at 32 channels on chip 1, driven, 983.04 MHz; 41.3
channels fit; 32.8 at 786.432 MHz.** It was measured on 2026-09-11 and it has
been in `goldens/cap-shk15-*` since; this session found it there rather than
taking it.

**What is not landed is the ruling.** The rung is `DSP4_SIMD_DYN` +
`DSP4_STRIP_FUSED`, and those carry the one audio consequence PW has been
asked to accept: across 20 families on both chips, one verdict differs from
the shipping pair — COMPRESSOR, numeric, **0.00518 dB**. `STRIP_FUSED` on its
own is verdict-for-verdict identical with three arms bit-exact. Bundled with
them in `shipping.config.s26` are `DSP4_DYN_LUT` (bound 0.0950 dB, the one
that should be signed on its own terms), `DSP4_GATE_LINTHR` (0.0002 dB) and
`DSP4_C2_BQ_GRAPH` (no audio consequence measured; the defect that held it at
0 was closed in S13-1).

With S76's landing, `shipping.config` now differs from `shipping.config.s26`
in **five switches**, all of them cycle levers with a stated audio bound:

| switch | shipping | s26 | worth |
|---|--:|--:|---|
| `DSP4_STRIP_FUSED` | 0 | 1 | part of chip 1's 118.9 → 53.8 |
| `DSP4_SIMD_DYN` | 0 | 1 | the rest of it; 30.7 pts of chip 2 at D32 |
| `DSP4_C2_BQ_GRAPH` | 0 | 1 | ~17 pts of chip 2 |
| `DSP4_GATE_LINTHR` | 0 | 1 | 54 % of the gate body |
| `DSP4_DYN_LUT` | 0 | 1 | makes the signal free (+42.5/+29.3 pts without it) |

`DSP4_SHARED_KERNELS` was the sixth and is now aligned.

---

## 5. Findings

**S76-1 THE CODE-POOL WALL IS DOWN. S75-5 CLOSED.** 95,648 bytes reclaimed on
chip 1; the `DSP4_EXTRAM=1` arm goes from 946 bytes free to 96,594. Code
reclamation was named in S75-5 as the prerequisite for ever arming the
external RAM, and it is no longer one. The two hardware blockers (S75-1 pin
conflict, S75-2 part voltage) still stand and are still the hub's.

**S76-2 `DSP4_SHARED_KERNELS` WAS NOT NAMED IN `shipping.config`.** It sat at
`build.sh`'s default of 0 while every fit table since S20 priced it at 15. The
file exists because in September 2026 the build that shipped was not the build
that was measured, in three parameters at once (S8-2, S9-1); this is a fourth,
and it is now a line in the file with its numbers beside it.

**S76-3 THE SHARED-KERNEL AUDIO PROOF IS NOW ON THE MACHINE CODE.**
`tools/dsp/shk_equiv.py`, 128/128 nodes on both arms, instruction for
instruction and absolute address for absolute address, with a mutation control
that the harness must catch and does. The FILT prologue hoist is the one
allowed difference and it is bounded rather than waved through. Worth running
on every future shared class before it ships.

**S76-4 🔴 THE SHIPPING CONFIGURATION DOES NOT FIT EITHER PRODUCT, DRIVEN, AND
NOBODY HAS RE-MEASURED IT FOR NINE DAYS.** Last measured 2026-09-10: D24
118.89–118.92 % / 119.24–119.25 %, one block in six missed; D32
158.13–158.18 % / 142.80–144.16 %, three in ten missed. Margin remaining at 32
channels on chip 1: **−58.2 points**. Twenty channels fit, not thirty-two.
This is not new — S19 said the shipping configuration fits neither product on
2026-09-10 and `shipping.config.s20` has been the proposal ever since — but it
is PW's standing priority one, and the number has aged nine days while the
graph grew.

**S76-5 WITH THE PAIRING RUNG THE 32-STRIP MINIMUM IS MET AT BOTH CLOCKS ON
CHIP 1.** +22.0 points of margin at 32 channels at 983.04 MHz, +2.5 at
786.432; 41.3 channels fit at 983.04 and 32.8 at 786.432. The strip is 476–484
cycles/sample against the 535 the projection carried.

**S76-6 🔴 CHIP 2 DOES NOT FIT AT 786.432 MHz.** D32, driven, best measured
configuration: 298,221 cycles/block against a 262,144-cycle budget = **113.8 %**,
−13.8 points. Chip 1 fits at that clock with 2.5 points to spare; chip 2 does
not fit at all. If 786.432 MHz is a real option for the product then chip 2
needs a lever that has not been found yet, or the clock is 983.04 and the
1 GHz part grade is not optional.

**S76-7 NO CAPACITY ROW WAS EVER TAKEN AT 786.432 MHz.** All 1,120 chip-rows in
`goldens/` measure between 982,988,768 and 983,100,764 Hz. Every 786.432 MHz
figure in this report and in the record is the measured cycle count against a
smaller budget, which assumes cycles/block are clock-invariant. That holds for
core-bound code and not for anything that waits on memory. A real 786.432 MHz
row needs `DSP4_CCLK_TARGET=786` to exist as a build arm and a boot to take it.

**S76-8 THE FULL CAPACITY CONFIGURATION NOW HAS 80,726 BYTES OF CHIP-1 CODE
FREE, AND WITH EVERY PENDING SWITCH ON IT STILL HAS 64,348.** It had 380 at
`shipping.config.s20` and 40,572 when S26 measured it. The five capacity
levers plus `DSP4_CUE`, `DSP4_RTA`, `DSP4_TEST_NODES` and `DSP4_EXTRAM` all on
together build and link at 75.5 % of the chip-1 pool. **This is the first time
in this record that the code pool is not the binding resource on chip 1**, and
it means none of those four can be refused on memory grounds any more. S75-5
said arming the external RAM needed code reclamation first; it now has 64 KB
of company.

**S76-9 THE `_bq_fx_cascade_simd` HANG WAS ALREADY CLOSED.** D44, commit
`2fadf39`: the scatter-back pointers were live in registers across a routine
that writes r0–r15, the state loop took `lcntr = 0x10000000`, and the diag ISR
kept answering, which is why it read as a hang. Fixed with five words of DM at
block rate, with `DSP4_BQP_NOSAVE=1` as the negative control. The dispatch
carried it as an open item; it is not one.

**S76-10 CFG2 STILL CANNOT TELL MASK 3 FROM MASK 15, AND NOW THAT MATTERS TO A
SHIPPING IMAGE.** `cfg_words.py` prints the caveat beside its own pass. The fix
is `DIAG_BUILD_CFG3`, and there are two incompatible designs for that word —
S28's (signature 0xC3, the whole mask in bits 15..8) and S75's landed one
(signature 0xC4, EXTRAM in bit 0) — with no free bit in either for the other.
S75-13 asked PW which lands; it is now on the shipping path rather than beside
it.

**S76-11 THE CONTROL ARM REBUILDS BYTE-IDENTICAL TO S74c.** `DSP4_SHARED_KERNELS=0`
from this tree gives `10a413005e0647f5c66476f6a0b4ab60` /
`e88a7a4302950d088a6c023c949c916e`, so the `shipping.config` line is provably
the only thing S76 changes about the image. The `DSP4_EXTRAM=1` mask-0 arm
likewise reproduces S75's two md5s exactly.

---

## 6. 🔴 For the hub

**S76-Q1 — a bench window for the driven ceiling.** Gates 2 and 3 asked for a
driven measurement on the current shipping pair, and S76 was dispatched
desk-only and read-only. A driven row cannot be taken without a boot, a
`loadlogic driveall` and a loaded configuration. The numbers in §3 are the
recorded rows and arithmetic on them; they are nine days old on the shipping
configuration and eight on the pairing one, and neither carries anything that
landed after 2026-09-11.

What a bench session would settle, in one boot pair each:

1. the shipping configuration **at mask 15**, driven, both products — the
   landing this session made, priced;
2. the shipping configuration **today**, driven, both products — how much the
   graph growth since 2026-09-10 actually costs (§3.3's unmeasured half);
3. the pairing configuration **today**, driven, both products — whether
   +22.0 points at 32 still holds after S65/S71/S74/S75;
4. a `DSP4_CCLK_TARGET=786` arm on any of the above, so the 786.432 MHz column
   stops being arithmetic (S76-7).

**S76-Q2 — is 786.432 MHz a live option?** If it is, S76-6 is a blocking
finding and chip 2 needs a lever nobody has. If the 1 GHz part grade at U5/U6
is settled, the 786 column can come out of the scoreboard and stop implying a
choice that is not there.

---

## 7. What this session did NOT do

- No measurement on the part. No boot, no flash, no config, no rails, no logic
  load. The unit was pinged once to confirm it was on the network and nothing
  else.
- No change to `defs`, `defs.lock`, any `_matrix.csv`, `dsp.csv`, or any
  generated file. `check-sharc-codegen-drift.sh` passes 734/734.
- No change to any node body, library routine or generator. The only source
  change is one line and its comment in `shipping.config`, plus one new tool.
- The reclaimed images are **not deployed**. `ldr/manifest.txt` is untouched.
