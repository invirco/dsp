provenance: AI-drafted 2026-09-20 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S80 — the third word filled, and the converters diagnosed as far as the instruments go

**Session 80, 2026-09-20, rev C unit + desk.** Hub dispatch `tasks.md`
2026-09-20 06:02Z. Four gates: `DIAG_BUILD_CFG3` landed at S75's
address and signature (hub ruling S75-13), the rows the bypass owes
(D16/D12 with and without it, and S78-Q4's S28/S29 re-take), the bench
copy of `s70lib` re-staged (S79-Q5), and the dark converters diagnosed
with no hands on the unit (S79-Q1's no-hands half).

---

## 0. Outcome in one paragraph

**Gate 1 is done: `DIAG_BUILD_CFG3` carries the switches the two full words
cannot, and the proof is on files that already existed** — `shipping.config`'s
`.s21`, `.s26` and `.s32` all read back `0xC2019E6F`, three images and one
word, and now read three different third words, which closes S27-3 and S79's
park-gate hole. The shipping triple is **`0xCF45FF10` / `0xE2018264` /
`0xC47C0F26`**; the word is in both boot streams at a known offset, and **the
part answered it** — `raw3 0xC47C0F26` on both chips of a `DSP4_AUXIN_BYPASS=1`
arm and `0xC47C0F24` on a `=0` arm, which is the negative control taken on the
DSP rather than on a file. Four defects in the surrounding machinery fell out of
the change, all of the class it exists for, the worst being that the one bench
tool which decodes what an image was built with was never deployed by the bench
lock and would have reported the new word as *"== the shipping configuration"*
having read almost none of it.

**Gate 2 is done and it is the session's most consequential result: on the
fixed instrument, not one product in the range fits driven.** D16 is **13 points
over budget on chip 2**, D24 **27.5**, D32 **64.3 on chip 1**; D12's driven row
will not prove its regime and is therefore not quoted. These are +40 to +51
points against S28's rows, which is exactly what S78-Q4 predicted — every S28
driven row was taken at 2 LSB on the pre-fix bitstream and was a silence row
wearing a driven label — and they agree with S79's independent D24 reading to
**a fifth of a point**. Every product does fit **silent, loaded**, worst
98.28 % on a D24's chip 2, except D32, which is over at its own boot
configuration before anything is opened. **The D16/D12 single-chip question gets
a no**, and not a marginal one. Six of the eight arms ran on **one
byte-identical pair**, differing by config words alone.

**Gate 3 is done**: the card's `s70lib.py` is the repo's, and the oscillator
ceiling read back off the card is the derived −14.89 dBFS, not the −12.00
constant that sat above the codec's pin rating.

**Gate 4's no-hands half is done and it bisects S79-Q1: the DSP side is
clear.** Four of the six readings the dispatch named have **no instrument on
this unit** — the codec's SPI path is write-only in both halves of H1S1, the
LOGIC CPLD has no host interface at all, nothing on a D24 reports a rail, and
the MEMS-against-codec idle comparison cannot be sharpened. The 595 chain *is*
readable and is **ruled out**. What settled it needed no probe and no rails:
under the `driveall` bitstream the CPLD drives the codec return lane, and all
four of its slots carry the stimulus at **exactly −6.02 dBFS** — so the SHARC's
receive path, SPORT, DMA and graph buffers are good end to end and **the fault
is upstream of the CPLD**. Two instruments were found to be lying while doing
it, including one the standing bench recipe recommends for this very question.

---

## 1. Gate 1 — `DIAG_BUILD_CFG3`, landed

### 1.1 The ruling, and what it decided

The hub ruled **S75-13**: S75's layout stands. Two designs for a word of
this name existed and could not both be right —

* **S75's**, implemented and in the firmware since 2026-09-19: address
  `0xE0EC`, signature `0xC4`, bit 0 `DSP4_EXTRAM`, bits 23..1 stated as free.
* **S28 gate 3's**, written into `tools/dsp/cfg_words.py` as
  `design_cfg3()` and never applied: signature `0xC3`, every one of bits
  23..0 allocated to a strip cut, the whole shared-kernel mask, six other
  switches and an instrument bit.

The ruling keeps S75's **address, signature and bit 0** — a landed signature
is not renegotiable, and 0xC3 against 0xC4 was the only thing that made the
collision survivable rather than dangerous. The S28 design is deleted, with
the reason in the commit. **Its field set is not deleted**: the switches it
named are carried at S75's signature, moved up out of the way of bit 0.

### 1.2 The layout as it now ships

```
 31..24  0xC4      signature
 23      INSTRUMENT            1 if ANY switch none of the three words
                               carries a field for is off its shipping
                               value. A shipping image reads 0.
 22      DSP4_RTG_FABRIC
 21      DSP4_GAIN_SIMD
 20      DSP4_DLY_SPLIT
 19      DSP4_C2_XPAIR
 18..17  DSP4_DYN_INLINE       0..3
 16      DSP4_DYN_TABLES
 15..8   DSP4_SHARED_KERNELS   THE WHOLE EIGHT-CLASS MASK
  7..6   reserved zero, and stated as free
  5      DSP4_SPI_PARTIAL_FIX2
  4      DSP4_RTA
  3      DSP4_CUE
  2      MTX_GATE              capability: this image resolves CFG_MTX_MASK
  1      DSP4_AUXIN_BYPASS     the off-aux park gate
  0      DSP4_EXTRAM           S75, unmoved
```

**`DIAG_BUILD_CFG2` is not re-laid out.** Its two legacy `SHARED_KERNELS`
bits stay exactly where they are, so its VALUE does not change for any image
and every decoder that reads it keeps working. CFG3 is what tells mask 3
from mask 15.

**Bits 7..6 are left free on purpose.** CFG2 was allocated to its last bit
and then needed a seventh narrowing of its own signature; a word with no
room is a word whose next flag becomes somebody's emergency.

### 1.3 The three holes it closes, each of which had cost something

| hole | who paid | closed by |
|---|---|---|
| the off-aux park gate is in NEITHER word, so the park-gate image and the pre-S79 one both read `0xE2018264` | S79 had to say "identify the arm by its image md5" in `shipping.config` itself | bit 1 |
| `DSP4_SHARED_KERNELS` mask 3 and mask 15 read back the same CFG2 | S27-3, open since S26; S77 spent the end of a bench session on the consequence | bits 15..8 |
| a pre-S79 image and an S79 image behave differently on `CFG_MTX_MASK` and answer identically | nothing yet, and that is the point — a host sending the fourth product word to a pre-S79 image writes to a cell with no reader | bit 2 |

### 1.4 The bit that is not a switch, and why it is in a build-config word

**`MTX_GATE` is a CAPABILITY.** S79's product-driven bypass is deliberately
not a build switch — *one image boots every product (D8), so a node no cell
on the BOOTED product can reach must cost zero, and a build switch would be
a second image*. The behaviour is therefore unconditional in the firmware,
and unconditional behaviour is exactly what no config word can see: an image
from before S79 and an image from after it read back the same two words and
do different things with the host's fourth product word. One bit, set from
the source tree rather than from any file, ends that. It is 1 here and 0 on
every image built before S79.

`INSTRUMENT` is the same shape, generalised: it is the truth value of "any
switch none of the three words carries a field for is off its shipping
value". **Fifty-six switches, and it does not say which one** — that is a
deliberate trade, fifty-six bits do not exist, and it is stated in
`src/diag.h`, in `cfg_words.unrepresented()` and in the bench decoder rather
than left to be discovered.

### 1.5 The word stopped being compiled out, and that was the cost

S75 put the `_diag_build_cfg3` DM cell behind `#if DSP4_EXTRAM` for a good
reason: a word of DM moves every address behind it, and that would have cost
S75 the one proof it most wanted to state — that the L2 arm rebuilds the
shipping pair byte-identical. The price was that **`0xE0EC` read plain 0 on
every shipping image**, which is precisely the silence the word exists to
end. It is unconditional now. **Every image's md5 moves once, here**, and
after that two images differing in anything the word carries differ in the
triple the part answers. A part that still answers `0x00000000` at `0xE0EC`
is a pre-S80 image, and the decoder says so in those words rather than
reporting a dead link.

### 1.6 `cfg_words.py` owns the field list for all three words

The dispatch's requirement, and it is what makes the mirrors checkable
rather than remembered. `WORD1`, `WORD2`, `WORD3` and `CFG3_CAPS` are the
denominator of `check_shipping_config.sh`'s completeness gate, which now:

1. derives `want3` **from `cfg_words.WORD3`** instead of listing it, so a
   field added to the word reaches the check without anybody remembering to;
2. runs the gate **in both directions** — a field the bench decoder reads
   that `cfg_words.py` does not declare is drift too, and would have made
   the check compare a key the part can never answer and pass on it for ever;
3. **cross-checks the two independent computations of the triple** — the
   bench mirror's dicts against `cfg_words.triple()` — and fails on a
   disagreement. This is the check that would have caught S77's `0xE2010244`
   without needing a part on a bench to notice;
4. proves `src/diag.h`'s instrument-bit literals are **the same list and the
   same values** `cfg_words.uncarried()` derives from `build.sh` and
   `shipping.config`, in both directions and on the values.

Point 4 matters because the change introduces a duplication: the instrument
bit has to be computed at assembly time from literals, because the cell that
carries the word is assembled, not compiled. A default in two places is
findings S8-2 waiting to happen — so the second copy is **proved on every
regeneration run**, not trusted.

### 1.7 Two defects the change turned up

**S80-2. `DIAG_BUILD_CFG2` has carried `DSP4_TEST_NODES` since S49 and the
repo side never knew.** `src/diag.h` sets bit 24 from `DIAG_CFG2_TEST_NODES`
and `tools/pi/dsp4_buildcfg.py` has decoded it since S49 — but
`cfg_words.WORD2` did not list it and `check_shipping_config.sh`'s `want2`
did not either, so `cfg_words.words()` computed a CFG2 **`0x01000000` short**
for any `DSP4_TEST_NODES=1` arm. Nothing had failed, because the switch is 0
in `shipping.config` and nobody had scored a self-test arm with this tool —
and the one arm it would have got wrong is the one arm a tool like this
exists to score. Found by pointing the completeness gate at a third word,
which is the gate working as designed rather than a lucky read.

**S80-3. `build_defaults()` silently dropped every switch whose `build.sh`
default REFERENCES another switch.** `${KEY:-$OTHER}` and
`${KEY:-${OTHER:-N}}` — `DSP4_NODE_LIMIT2` and `DSP4_DYN_SELFTEST` — matched
no pattern the function read, so they were absent from its dict. Harmless
while nothing asked about them; fatal for an instrument bit that has to know
the shipping value of every switch no word carries, because a switch whose
default this function cannot read is a switch the bit is **silently blind
to**. Both resolve now, through the reference chain.

**S80-4. `build.sh` defined four switches for the compiler and not for the
assembler** — `DSP4_DMA_AUTOBUF`, `DSP4_FCWM`, `DSP4_PATTERN`,
`DSP4_RX0_L2`, the only four of its ninety-six that were not in `ASMFLAGS`.
No assembly source reads any of them, so nothing was wrong until the
instrument bit needed to see them: an undefined identifier evaluates to 0 in
a preprocessor `#if`, so a `DSP4_PATTERN=1` build would have stamped itself
"this is the product". They are defined for both now.

### 1.8 The proofs

**The shipping triple, computed two independent ways and agreeing:**

```
shipping config: consistent; the part must read DIAG_BUILD_CFG 0xCF45FF10,
                 DIAG_BUILD_CFG2 0xE2018264, DIAG_BUILD_CFG3 0xC47C0F26
  on the bench:  dsp4_buildcfg.py --expect-shipping
  by hand:       dsp4_buildcfg.py --expect-shipping --word 0xCF45FF10,0xE2018264,0xC47C0F26
  a part answering 0x00000000 at 0xE0EC is a PRE-S80 image: it has no
  DIAG_BUILD_CFG3 cell at all
```

**The word is in the image, not only in the tool.** `0xC47C0F26` appears
exactly once in each boot stream built from this tree, little-endian:

| stream | md5 | offset |
|---|---|---|
| `build/chip1.ldr` | `e364c522d3747296c39a2b4a2d912b11` | `0x1c0c4` |
| `build/chip2.ldr` | `63b40b85a3cd18054ad3639832d78d6a` | `0x20e0c` |

**THE PROOF THAT MATTERS MOST, because it is taken on files that exist
rather than on an invented arm.** Four named configurations live in this tree
beside `shipping.config`, and **three of them are indistinguishable in both
full words**:

| configuration | DIAG_BUILD_CFG | DIAG_BUILD_CFG2 | DIAG_BUILD_CFG3 |
|---|---|---|---|
| `shipping.config` | `0xCF45FF10` | `0xE2018264` | **`0xC47C0F26`** |
| `shipping.config.s20` | `0xCF45FF10` | `0xC2011E4F` | **`0xC47C0024`** |
| `shipping.config.s21` | `0xCF45FF10` | `0xC2019E6F` | **`0xC47C0324`** |
| `shipping.config.s26` | `0xCF45FF10` | `0xC2019E6F` | **`0xC47C0F24`** |
| `shipping.config.s32` | `0xCF45FF10` | `0xC2019E6F` | **`0xC47C0F26`** |

`.s21`, `.s26` and `.s32` all read `0xC2019E6F` — **the same word, for three
different images**. `.s21` against `.s26` is S27-3, shared-kernel mask 3
against mask 15, open since S26 and now `0x0324` against `0x0F24`. `.s26`
against `.s32` is S79's hole, `DSP4_AUXIN_BYPASS` alone, and now `0x0F24`
against `0x0F26` — one bit, bit 1. **Three configurations that no image could
tell apart in either full word now answer three different third words**, and
nothing about `DIAG_BUILD_CFG` or `DIAG_BUILD_CFG2` moved for any of them.

**The negative controls — five, of which the last is on the artifact:**

| control | result |
|---|---|
| `DSP4_CUE` 0 → 1 in `shipping.config` | `SHIPPING CONFIG DRIFT: DSP4_CUE: the build says 1, dsp4_buildcfg.SHIPPING3 says 0`, exit **1** |
| `DSP4_PATTERN=1` added to `shipping.config` | `src/diag.h's DIAG_CFG3_INSTR_SUM compares against 0, the shipping value is 1`, exit **1** |
| `DSP4_PATTERN=1` in the ENVIRONMENT | triple becomes `0xC4FC0F26`; `cfg_words.py --check` against the shipping triple reports `differ 0x00800000`, exit **4** |
| `DSP4_AUXIN_BYPASS=0` | triple becomes `0xC47C0F24`, `differ 0x00000002`, exit **4** |
| a FULL BUILD with `DSP4_PATTERN=1` | both boot streams carry `0xC4FC0F26` and **neither carries `0xC47C0F26`** |

The last row is the one that matters, because it is the only one taken on
the thing that ships. `DSP4_PATTERN` was chosen for it deliberately: it is a
switch **no** config word carries a field for, so it exercises the
instrument bit, the fifty-six-switch list, the two-place mirror check and
the new `ASMFLAGS` line at once.

**Nothing else moved.** `validate-matrix-contract.py` passes on all four
products, `check-sharc-codegen-drift.sh` reads *tree == generator output*
(734 files, 0 differ), and `check-contract-drift.sh` completes with no
matrix or address change — which is the right outcome, because
`DIAG_BUILD_CFG3` is a diag register and not part of the matrix contract.
`proposals/CONTRACT-PROPOSAL-S75.md` carries the filled layout, since that
is where the contract record keeps the `0xE0xx` space.

---

## 2. Gate 3 — the bench copy re-staged (S79-Q5)

S79 derived the oscillator ceiling instead of declaring it, because the old
`OSC_MAX = -12 dBFS` rested on 6 dB of pad that does not exist and in fact
sat about 1 dB **above** the codec's analog pin rating. The fix was in the
repo and not on the card, and nothing in this tree deploys that file.

| | md5 | `osc_ceiling()` |
|---|---|---|
| card, before | `6f9d322725b311e228978424c6060a95` | (no such function) |
| repo | `b31c1af0325e7285e596939d7a4e8590` | derived |
| **card, after** | **`b31c1af0325e7285e596939d7a4e8590`** | **−14.89 dBFS** |

Read back off the card's own import: `osc_ceiling() -14.889999999999999`,
`OSC_MAX -12.0` (kept only as a ceiling on the ceiling), `AK4619_FS_DBU
8.24`, `osc_for(11) -48.25`. The stale bytecode was removed with it.

**It was the only copy of the old cap on the machine** — an inventory of
every `*.py` under `/home/app` carrying `OSC_MAX` returns exactly
`/home/app/s70/s70lib.py`, and `/home/app/s69/s69lib.py` has no such symbol
at all. `~/dspboot` and `ldr/manifest.txt` were not touched; no DSP was
booted and no GPIO was written to do this.

---

## 3. Gate 4 — the dark converters, with no hands on the unit

The dispatch named six things to read that "a probe would otherwise settle".
**Four of the six have no instrument on this unit at all**, and finding that
out is most of this gate's result: S79-Q1 has been waiting for a probe partly
because the readings it was told to try do not exist to be taken. Each is
answered from the source that would have to contain them, not from a failed
attempt.

### 3.1 "Read a register that `StartAK4619` wrote and compare" — NOT POSSIBLE

The only master on the codec's SPI is H1S1 (PW's ruling 2026-09-19: *"use
h1s1 to get the test spec, and we'll add a dedicated CS6 wire later"*), and
**H1S1's codec path is write-only in both halves**:

* `CodecPoll()` assembles `{0xC3, 0x00, reg, val}` — command `0xC3` is the
  AK4619's **write** command (datasheet 9.12 Table 27). There is no `0xC1`
  read arm and no second cell to return a byte in;
* `SpiTx()` itself never reads MISO — it transmits a byte array and returns
  `void`.

So no host on this bench can read an AK4619 register. **This is the single
most useful thing a probe-free diagnosis would want and it needs an H1S1
firmware change**, not a bench technique: a read command in `CodecPoll()` and
one matrix cell to carry the answer back. Scoped in §7.

### 3.2 "The CPLD's clock/frame counters for `CDC_O` and each converter lane" — DO NOT EXIST

The LOGIC CPLD has **no host interface of any kind**. Its port list
(`shared/dsp4-logic/rtl/dsp4_logic_top.v`) is clocks, the eight DSPA input
lines, the eight DSPB output lines, the converter and NET lanes, the PCM
link, one LED and four TEST pins — *"There is NO reset input: MAX V registers
power up cleared"* — and there is no register file, no SPI, no I²C and
nothing to count with. A counter on `CDC_O` would be an HDL change plus a way
to get it out, and the only ways out are the four TEST pins or a DSPA lane.

### 3.3 "The 595 chain readback — is a converter reset/power bit in the safe image?" — READABLE, AND THE ANSWER IS NO

This one **does** have an instrument: the chain is 25 bytes shifted at CS_M
in two passes and pass 2's MISO is the image that was in it
(`MW/D24/DSP/s55/tools/s55_chain.py`), so it reads as well as writes. The bit
map is one byte per mic-preamp position:

```
byte = (gain & 63) << 2 | (phantom & 1) << 1 | (mute & 1)
```

**There is no converter reset or power bit in it, in the safe image or in any
other.** `!RST_C` is a direct STM32 GPIO (`GPIOA, RST_C_Pin`), pulsed in
`MainInit()` — S79 already exercised it. So no 595 state can be making the
converters dark, and the chain is ruled out as a cause rather than left open.

**It did turn up something else, and it is a correction to S79.** S79's
handback recorded *"The chain was left as `MainInit` leaves it, not as S70's
SAFE image; both are benign (gain 0, phantom off)"*, on the strength of
`codec4619.py`'s own docstring saying `--reset` *"CLEARS THE 595 CHAIN"*.
Decoded against the bit map above, that is wrong in the unsafe direction:

| image | source | gain | phantom | mute |
|---|---|--:|--:|--:|
| `micGainFull` — the ONLY image `TestMicPres()` still sends, and `MainInit()` ends by calling it | H1S1 `matrix.cs` | **63** | 0 | **0** |
| `micGainMin` — commented out | H1S1 `matrix.cs` | 0 | 0 | 0 |
| **the SAFE image**, `0x01`×24 + `0x00` | `s70_handback.py` | 0 | 0 | **1** |

So `codec4619.py --reset` leaves **every mic preamp unmuted at maximum
gain**, and the unit has been in that state since S79's handback. Phantom is
off, so nothing is at risk of damage — but it is not the safe image, and any
EIN or noise figure taken on this bench now is taken at full gain. The tool's
docstring is corrected in this commit. **The state is INFERRED from the H1S1
source and is deliberately not verified on the part**, because verifying it
means shifting the chain, and shifting the chain drives CS_M — which this
dispatch's standing handback says to leave untouched. One line fixes it and
it is a 🔴 note in §7 rather than something this session did unasked.

### 3.4 "The power MCU's rail status words, every rail it reports" — NOTHING REPORTS A RAIL

`S_TEST` on the MX bus returns, twice in a row, identically:

```
S_TEST  -> b'+\n// H1S1 DSP\n// H1S4 SW Left\n// H1S3 SW Right\n:\n.\n:\n. ...'
```

Three MCU identity announcements and MH1's idle heartbeat. **None of the
three is a power MCU and none of them reports a voltage**, and a grep of the
D24 contract (`MW/D24/MX/_matrix.csv`, 5,002 cells) for a rail, voltage,
supply or temperature reading returns only the 24 `Chan[n]Phantom001`
controls — which are writes, not readings. There is no rail telemetry on this
product to diff against S70's boot.

### 3.5 The MEMS lane's idle level — read, and NOT decisive

S79 read `_buf_C1_XIN_MEMS` at a stuck `0xFFFFFFFF` while the codec lanes sat
at a stuck `0x00000000`, and took the two different idle levels as evidence
that the SPORT is sampling real pin states. That inference is sound, but it
**cannot be pushed further to say the codec is driving**, and this session
checked whether it could and it cannot: the two lanes are different nets on
different boards. `shared/dsp4-logic/tdm-lines.csv` puts the codec on
`A_I4` / `CDC_O` and the MEMS on `A_I7` / `MEMS`, each with its own pull
behaviour.

The obvious sharpening — compare the codec's four populated TDM slots against
the four unpopulated ones on the *same* wire — is also unavailable: chip 1
receives that line as **stride 4**, not 8 (`src/chip1/block_io.asm`:
`_c1_rx_off` 512..515 with `_c1_rx_stride` 4), so the unpopulated slots are
not in the RX buffer to be read.

### 3.6 What IS decisive, needs no probe, and costs nothing

The one measurement that bisects S79-Q1's three candidates is already part of
this session's gate 2. Under the `driveall` bitstream the CPLD assigns

```verilog
assign i_dspa[5:0] = {6{pcm_drive}};     // dsp4_logic_top.v
```

— the CM4's playback is broadcast onto every DSPA input lane **including
lane 4, the codec return**, and on the shipping bitstream that same lane is
`assign i_dspa[4] = cdc_o;`, a direct wire with no mux and no gating. So:

* **codec lanes MOVE under `driveall`** ⇒ the SHARC's I4 pin, its SPORT, its
  DMA, the slot mapping and the graph buffers are all good end to end, and
  the fault is strictly upstream of the CPLD — the `cdc_o` net, the J41/J42
  flat-flex, the codec or its clock. The probe list narrows to two items.
* **codec lanes still read zero under `driveall`** ⇒ the fault is on the DSP
  side and **no probe at J41 is needed at all**.

Either answer is worth a session of somebody's time, and it is taken on a
bitstream this bench already flashes for every driven capacity row.

### 3.7 The bisection, taken — and it clears the DSP

Under `driveall`, with the CM4 playing, chip 1's input buffers read (40 peeks
each, 13.7 ms apart, deliberately not a rational multiple of the 2.5 ms drive
period — a first pass at 20 ms aliased and reported `CODEC_04` falsely STATIC):

| buffer | | words |
|---|---|---|
| `_buf_C1_XIN_CODEC_01` | MOVING, 2 distinct/40 | `0x08000000` / `0xF8000000` |
| `_buf_C1_XIN_CODEC_02` | MOVING, 2 distinct/40 | the same |
| `_buf_C1_XIN_CODEC_03` | MOVING, 2 distinct/40 | the same |
| `_buf_C1_XIN_CODEC_04` | MOVING, 2 distinct/40 | the same |
| `_buf_C1_XIN_MEMS` | MOVING, 2 distinct/40 | the same |
| `_buf_C1_XIN_PI_L` / `_PI_R` | MOVING, 2 distinct/40 | the same |

**The amplitude is exactly right, and that is worth more than the movement.**
`0x08000000` in **Q4.28** is `+0.5` and `0xF8000000` is `−0.5`, i.e.
**−6.02 dBFS** — and −6.02 dBFS is precisely the documented `driveall`
amplitude at the part (`peak 0x40000000`, the raw Q1.31 TDM word, which
`C1_IN_nn`'s block kernel right-shifts by 3 into Q4.28: `0x40000000 >> 3 =
0x08000000`). So the codec return lane carries the stimulus at full, correct,
un-shifted amplitude. The S78-3 one-bit fix is holding on this lane too.

**Verdict: the DSP side is clear.** The SHARC's I4 pin, its SPORT, its RX DMA,
the slot mapping and the graph's input buffers are good end to end. Everything
`0xE0EC`'s bitstream can reach works. **The fault is upstream of the CPLD** —
the `cdc_o` net, the J41/J42 flat-flex, the codec itself or its clock — which
is where S79-Q1's probe should go, and it removes one of that question's three
candidates by removing the possibility that the DSP was the problem all along.

**Two things about that read that must not be quoted without their caveats:**

1. **`dsp4_inscan.py` reads MOVING 0 / STATIC 32 under this stimulus and the
   reading means nothing.** Its whole method peeks the `_rx_slot_C1_IN_nn`
   scalars, and under `DSP4_BLOCK_KERNELS` those are **dead symbols** — the
   node source says so at the point of declaration: *"Under block kernels this
   kernel reads the DMA buffer directly, so the slot var is unreferenced —
   kept as a scalar purely so block_io.asm's tables still resolve."* So in
   any block-kernels build — which is every build that ships — `dsp4_inscan.py`
   reports STATIC zero whether the path is alive or dead. S79 quoted it
   (*"`dsp4_inscan.py` reads MOVING 0 / STATIC 24 on chip 1"*) as part of the
   case that the converters are dark, and that part of the case is void. The
   conclusion was right for other reasons; the instrument was not.
2. **`_buf_C1_IN_01` reads STATIC `0x00000000` under the same stimulus, and
   that is the same dead-symbol trap, not a second fault.** Lane 0 *is* in the
   broadcast (`i_dspa[5:0] = {6{pcm_drive}}`), so a live `_buf_C1_IN_01` would
   have moved. It is a plain `.var` in **both** arms of
   `C1_IN_01.asm`'s `#if DSP4_BLOCK_KERNELS`, written only on the per-sample
   path (`dm(_buf_C1_IN_01) = r0`), while the block path writes
   `BLK_CHAIN_A_P1`. `_buf_C1_XIN_CODEC_01` by contrast is
   `.var [DSP4_BLOCK_SIZE]` under block kernels and is written. So the only
   buffers that *could* move are the ones that did.

### 3.8 The rails, raised once more, and the null repeated

The dispatch authorised the AN_EN raise for this gate. It was taken on the
**S80 image** (`e364c522` / `63b40b85`, the shipping build of this tree, booted
and configured for D24 twice per the standing recipe, chip 1 `BOOT_STAGE 7`
`FRAME_COUNT 51,897` and chip 2 `BOOT_STAGE 7` before anything was read) on the
**shipping** bitstream:

| GPIO 26 | `_buf_C1_XIN_CODEC_01` | `_02` | `_03` | `_04` |
|---|---|---|---|---|
| `lo` (control) | STATIC `0x00000000` | STATIC `0` | STATIC `0` | STATIC `0` |
| **`hi`, 300 ms** | **STATIC `0x00000000`** | STATIC `0` | STATIC `0` | STATIC `0` |

40 reads per buffer per state. Chip 1 with the rails up: `MAGIC 0xD5B40001`,
`BOOT_STAGE 7`, `FRAME_COUNT 127,661`, `SPORT0_ERR_A 0x00000000`,
`DMA0_STAT 0x00006200`. **`op dl` after, verified `lo`.** Analog last up, first
down.

So S79-2's null reproduces a day later **on a different image**, which is worth
having: it rules out the S80 build as a factor and says the state is stable
rather than intermittent. `_buf_C1_XIN_MEMS` returned UNREADABLE on both rail
states in this run (the fifth symbol in both sequences — a link fault in the
peek, not a reading); S79's `0xFFFFFFFF` for it stands as the last good value
and this session did not reproduce it.

**Why the rails were not pushed further.** Every other reading the raise was
meant to serve turns out not to exist (§3.1–3.4), and the one decisive
measurement (§3.7) needs no rails at all. Raising them again to re-read the
same four buffers is the whole of what the rails could still buy, and that was
taken.

---

## 4. Gate 2 — the rows the bypass owes

### 4.1 What the arms are, and the one thing that makes them comparable

Eight arms, `./capacity.sh --driven` on `loadlogic.sh driveall`
(`c49f4128a083`, FLASH OK attempt 1), REPS=2, 45 s dwell, 983.01–983.08 MHz
measured on every row against a decoded 983.040, block 16. Each arm's
definition is its **command**, because `shipping.config` moved in this session
and an arm whose definition lives in a file that can move under it is not an
arm (S11-1's shape):

| arm | command | chip 1 | chip 2 |
|---|---|---|---|
| `s80d16b0` | `ARM=s80d16b0 PRODUCT=d16 DSP4_AUXIN_BYPASS=0` | `a91d41f7` | `18db062e` |
| `s80d16b1` | `ARM=s80d16b1 PRODUCT=d16 DSP4_AUXIN_BYPASS=1` | `e364c522` | `63b40b85` |
| `s80d12b0` | `ARM=s80d12b0 PRODUCT=d12 DSP4_AUXIN_BYPASS=0` | `a91d41f7` | `18db062e` |
| `s80d12b1` | `ARM=s80d12b1 PRODUCT=d12 DSP4_AUXIN_BYPASS=1` | `e364c522` | `63b40b85` |
| `s80s28d24` | `ARM=s80s28d24 PRODUCT=d24 DSP4_AUXIN_BYPASS=1` | `e364c522` | `63b40b85` |
| `s80s28d32` | `ARM=s80s28d32 PRODUCT=d32 DSP4_AUXIN_BYPASS=1` | `e364c522` | `63b40b85` |
| `s80s29ctl` | `ARM=s80s29ctl PRODUCT=d32 DSP4_AUXIN_BYPASS=1` | `e364c522` | `63b40b85` |
| `s80s29ns` | `SCOPE_ID=1 ARM=s80s29ns PRODUCT=d32 DSP4_AUXIN_BYPASS=1` | `e364c522` | `63b40b85` |

**Six of the eight arms ran on ONE byte-identical pair**, and it is this tree's
shipping build — the same `e364c522d3747296c39a2b4a2d912b11` /
`63b40b85a3cd18054ad3639832d78d6a` that §1.8 found `0xC47C0F26` inside.
D12, D16, D24 and D32 differ by **config words only**, which is decision D3/D8
holding at four products and a measurement rather than a claim. The two
`DSP4_AUXIN_BYPASS=0` arms are a different image, as they must be: that one is
a build switch.

**And the part answered the new word.** On `s80probe` (D24,
`DSP4_AUXIN_BYPASS=1`), both chips: `raw3 0xC47C0F26`, with
`DSP4_SHARED_KERNELS 15 (COMP, TUBE, GATE, FILT)` and
`on3: DSP4_AUXIN_BYPASS, MTX_GATE, DSP4_SPI_PARTIAL_FIX2, DSP4_C2_XPAIR,
DSP4_DLY_SPLIT, DSP4_GAIN_SIMD, DSP4_RTG_FABRIC`. On `s80d16b0`
(`DSP4_AUXIN_BYPASS=0`), both chips: `raw3 0xC47C0F24`, and the tool printed
`NOT THE SHIPPING CONFIGURATION IN THE THIRD WORD: DSP4_AUXIN_BYPASS = 0,
shipping is 1`. **That is gate 1's negative control taken on the part**, and it
closes the chain: the repo tool computes the word, the byte is in the boot
stream at a known offset, and the DSP answers it at `0xE0EC`.

### 4.2 The rows

`DSP4_AUXIN_BYPASS=1` — the shipping position. avg % / worst-block % of
budget, mean of two boots for the average, and a boot whose worst-block latch
needed no S21-6 tick correction for the worst, so no corrected figure is quoted
as a measurement.

| row | | D12 | D16 | D24 | D32 |
|---|---|--:|--:|--:|--:|
| A silent/default | chip 1 | 32.44 / 32.54 | 40.32 / 40.49 | 56.04 / 56.22 | 72.05 / 72.39 |
| | chip 2 | 71.07 / 71.33 | 79.47 / 79.78 | 88.33 / 88.57 | **105.62 / 106.04** |
| B silent/loaded | chip 1 | 43.67 / 43.98 | 55.88 / 56.12 | 80.71 / 80.94 | **106.70 / 107.19** |
| | chip 2 | 76.03 / 76.33 | 87.73 / 88.08 | 98.28 / 98.50 | **118.90 / 119.25** |
| **C driven/loaded** | chip 1 | *(65.41 / 65.64)* | **84.59 / 84.95** | **123.57 / 124.10** | **164.32 / 164.70** |
| | chip 2 | *(96.30 / 96.59)* | **113.00 / 113.46** | **127.50 / 128.02** | **151.57 / 152.39** |

Missed blocks, driven/loaded: D16 chip 2 **15,510 of 135,000 (11.49 %)**; D24
**25,713 chip 1 (19.04 %) and 29,016 chip 2 (21.49 %)**; D32 **52,704 chip 1
(39.03 %) and 45,959 chip 2 (34.03 %)**. D32's silent rows miss too: 7,228
(5.35 %) on chip 2 at A, and 8,527 / 21,382 at B.

**D12's driven row is in brackets because it is not a measurement of D12.** The
driven regime did **not** prove on chip 2 on either boot of either D12 arm — 22
of 24 envelopes engaged, identically with and without the park gate — so by the
rule this instrument runs under, that row is not a driven number. It is printed
for the record and it is **deliberately absent from
`MW/D32/DSP/fit-measured.json`**, where its row falls back to the construction
and says `construction` in the source column.

### 4.3 The comparison that matters: these replace S28's rows

S28's rows are kept, marked SILENCE, in
`MW/D32/DSP/fit-measured-s28-SILENCE.json`. The delta, chip 2, driven/loaded:

| product | S28 (SILENCE) | S80 | Δ |
|---|--:|--:|--:|
| D12 | 66.59 | *(96.30)* | *(+29.7)* |
| D16 | 73.02 | **113.00** | **+39.98** |
| D24 | 84.64 | **127.50** | **+42.86** |
| D32 | 100.82 | **151.57** | **+50.75** |

**This is exactly what S78-Q4 predicted and it is the reason the re-take was
ordered**: every S28 driven row was taken on the pre-fix bitstream, where the
MFD-2 lanes carried the stimulus one bit right-shifted and therefore at 2 LSB,
so the dynamics never left their cheap branch and a "driven" row was a silent
row with a driven label. S18 had already priced that difference on chip 2 at
D32 — 92.7 % below threshold against 112.3 % engaged, same image — so a forty-
to fifty-point correction is the documented size of this error, not a surprise.

**The new rows are corroborated by S79, independently and to a fifth of a
point.** S79 measured the D24 chip-2 driven row with both levers on at
**127.69 / 127.37 %** of budget; this session reads **127.49 / 127.50 %** on a
different build of a different tree. The silent/loaded row likewise: S79
**99.75 / 99.76 %**, S80 **98.28 / 98.50 %**. So the jump against S28 happened
before this session and S79 already recorded it; S80's job was to put it in the
scoreboard, and the numbers agree across two sessions.

### 4.4 The park gate on D16 and D12 — and what these arms do NOT measure

`b1 − b0`, chip 2, the same tree with one build switch:

| row | D16 | D12 |
|---|--:|--:|
| A silent/default | **−1.81 pts** | **−1.55 pts** |
| B silent/loaded | **−1.68 pts** | **−1.67 pts** |
| C driven/loaded | **−1.77 pts** | *(−1.75 pts)* |

Chip 1 across the same six comparisons is the instrument talking to itself,
because the two images differ on chip 2 only — and it spans **−0.09 to +0.14
points on five of the six rows and +1.09 on the sixth**. The sixth is D12's
driven row, and the reason is visible in the boots behind it: the `b0` arm read
chip 1 at **65.31 then 63.32** on two boots of one arm, a two-point spread
inside a single arm, against `b1`'s 65.40 / 65.41. **That is the same row whose
chip-2 regime will not prove** (§4.2), so D12's driven row is unstable on both
chips and unusable on both. On the five rows that are measurements the floor is
about a seventh of a point, and every chip-2 figure above clears it by more
than ten times.

**So the park gate is worth about 1.5–1.9 points of chip 2 on a D16 or a D12,
which is LESS than the D24's 2.4–2.5 and much less than the D32's 4.9–5.7 —
and that is the right answer, not an anomaly.** `DSP4_AUXIN_BYPASS` gates the
twelve chip-2 `AUX_INPUT` nodes whose `on` cell is 0, and **twelve is twelve
whatever the product is**: the smaller products do not have more of them, they
have the same ones, minus the eight snake returns that are already scope-gated
off below D32 (which is precisely why D32 gains most).

**S79-Q3's "a D16 skips 18 instances and a D12 skips 20" is a different lever
and these arms cannot measure it.** That is the product-driven bypass —
`CFG_MTX_MASK` and `C2_MIX_AUX_nn` joining the aux gate — and it is **not a
build switch** by design (one image boots every product, D8), so it is present
and active in *both* arms of every pair above. Pricing it on D16/D12 needs a
pre-S79 reference image as its control, the way S79 priced it on D24 and D32
against `s79ref`. That measurement is still owed and this session did not take
it.

### 4.5 The D32 scope-class arm (S29 re-taken)

`s80s29ns` (D32 masks, D24's scope word, snake nodes gated off the ordinary
way) against `s80s29ctl` (D32's own scope word), driven/loaded:

| | chip 1 | chip 2 |
|---|--:|--:|
| `s29ctl` (D32 scope class) | 164.11 / 164.15 | 151.70 / 151.65 |
| `s29ns` (D24 scope class) | 163.75 / 163.69 | 153.31 / 151.47 |
| Δ (means) | **−0.41 pts** | **+0.71 pts** |

The chip-2 figure is **inside its own noise and not a number**: `s29ns`'s two
boots read 153.31 and 151.47, a 1.84-point spread within one arm, against a
0.14-point spread across the four boots of the deliberate repeat (§4.6). Only
the chip-1 −0.41 is a measurement, and it is small.

**The scope class is worth almost nothing measurable on the driven row**, and
that matters because S28's two-anchor construction carried the D32 scope class
as the explanation for its "dear last segment" (S28 §2.3: *"D32 is the only
product that boots scope class 0, which runs 32 snake nodes every other product
gates off, and the two-anchor line carries that step as if it were per-unit
cost"*). On the fixed instrument the step is not there to explain: the
per-segment slopes over the four products are now **flat** — chip 1
+1.97 / +1.96 / +2.00 points per strip and chip 2 +4.20 / +4.43 / +4.32 points
per aux bus across D12→D16, D16→D24 and D24→D32 on the silent/default row,
against S28's chip-2 +2.32 / +2.39 / **+3.29**. The mechanism is not isolated
here and should not be asserted; what can be said is that the range's cost is
now linear in its size and S28's step is gone.

### 4.6 The instrument's own spread, from the deliberate repeat

`s80s28d32` and `s80s29ctl` are the same configuration run as two independent
arms — separate builds, separate staging, separate boots — so this is the
session's own spread rather than a quoted one. Driven/loaded **average** % of
budget over the four boots: chip 1 163.99 / 164.64 / 164.11 / 164.15 — a span of
**0.65 points**; chip 2 151.56 / 151.58 / 151.70 / 151.65 — a span of
**0.14 points**. Both are at or inside the floor this instrument is documented
to have (S79 used ±0.27 points on D32 chip 2, S28 ±0.30), so **re-running an
identical configuration as a fresh arm reproduces it cleanly**, and every
chip-2 difference in §4.4 clears that floor by an order of magnitude.

**The worst-block column does NOT behave as well, and most of that is not the
part.** Eleven of the forty-two rows taken this session latched a worst block
three to four hundred per cent of budget, which is the S21-6 tick artifact: the
timer ISR landing between the `tcount` and `_diag_ticks` reads that close a
pass. Where the tool subtracted `TPERIOD` the corrected figure lands within half
a point of that row's own average and the arbiter counted zero extra missed
blocks; where it did not, the raw latch is quoted as raw. **No corrected figure
is used as a measurement anywhere in §4.2** — the worst-block column there is
drawn only from boots that needed no correction. The fix is four instructions in
`main.asm` and was not made here.

### 4.7 The 32-in-one goal line, answered honestly for the first time

PW's ruling 2026-08-28: *32 channels is the MINIMUM, not the goal — the
deliverable is cycles/percent REMAINING at 32 channels, and a fit with no
headroom is not a fit.* PW 2026-09-11: *D16 and D12 run on ONE 21564 each.*

**On the fixed instrument, and driven, not one product in the range fits the
two chips it has:**

| product | chip 1 driven | chip 2 driven | worst chip | margin at its own size |
|---|--:|--:|---|--:|
| D12 | *(65.41)* | *(96.30)* | *(chip 2)* | *(+3.7, regime unproven)* |
| D16 | 84.59 | **113.00** | chip 2 | **−13.0** |
| D24 | 123.57 | **127.50** | chip 2 | **−27.5** |
| D32 | **164.32** | 151.57 | chip 1 | **−64.3** |

**The D16/D12 single-chip question does not get a positive answer from these
rows, and the reason is not marginal.** A D16 today uses two 21564s and its
chip 2 is 13 points over budget with 11.5 % of blocks missed; folding chip 1's
84.6 % onto the same part is not a question of headroom. **Margin at 32 is
−64.3 points on chip 1 of a two-chip D32**; 32-in-one is not a number this
firmware has, driven, and the last session that said so (2026-08-24, measured
ceiling ten channels a chip) is not contradicted by anything here.

**What the silent rows say, because they are the ones a product spends most of
its life in:** D12, D16 and D24 all fit both chips silent, loaded, with the
worst reading **98.28 / 98.50 %** on a D24's chip 2 — under budget, zero missed
blocks, and 1.7 points of that came from the park gate this session put in
`shipping.config`. **D32 does not fit even silent**: 105.62 % on chip 2 at its
own boot configuration, before anything is opened.

### 4.8 What was observed and not explained

Reported rather than smoothed, because each is a reason to distrust a number:

1. **D16's driven/loaded row misses 0 blocks on boot 1 and 15,510 (11.49 %) on
   boot 2, at 113.00 % of budget on both.** A row above budget that misses
   nothing is internally inconsistent, so one of the two counters is wrong on
   one of the two boots. The same shape appears on the `b0` arm (0, then
   17,253). Whichever way it resolves, the avg % is the figure to trust here
   and the missed-block count is not.
2. **Chip 1's load-config write reports 0–6 FAILED per boot on D24 and D32 and
   0 on D16 and D12, non-deterministically and independently of
   `DSP4_AUXIN_BYPASS`.** No arm's regime failed to prove because of it, but an
   intermittent failed parameter write on the larger products is not a thing to
   leave unrecorded.
3. **D12's chip-2 driven regime reaches 22 of 24 envelopes and no more**, on
   both boots of both arms. Two envelopes that never engage under this stimulus
   is a specific, reproducible fact and it is what blocks D12 having a driven
   number at all.

---

## 5. The scoreboard, republished

`MW/D32/DSP/fit-measured.json` now holds S80's rows; S28's are kept beside it
in `MW/D32/DSP/fit-measured-s28-SILENCE.json` with the reason at the head of
the file. `MW/D32/DSP/fit-table.csv` is regenerated from them and marks the
fit column **NO** on every driven row and on both of D32's silent rows.

`tools/dsp/product_fit.py::load_measured` now drops keys beginning `_`, so the
measured file can carry its own provenance. Until this session it could not —
`score_measured` sorts the products with `int(p[1:])` and any non-product key
raised `ValueError` — which is how S28's measured rows came to be uncommitted
and later reconstructed from the table they had produced. **A data file that
cannot state its own provenance gets separated from it.**

**THE CONSTRUCTION IS NOW STALE AND THE TABLE SAYS SO RATHER THAN HIDING IT.**
`product_fit.py`'s prediction is a two-point interpolation of S27's anchors, and
against S80's rows those anchors are out by **+43 points (D24) and +51 to +85
(D32)** on the driven row. The delta column shows it, and the D24/D32 rows are
labelled *(ANCHOR — this is a control)* while failing as controls. **This
session did not re-anchor it**, deliberately: re-anchoring rewrites every
prediction for every product, D12 has no driven row to anchor against, and it
is a decision rather than a regeneration. It is §7's first hub item.

---

## 6. The unit, as it was left

1. **LOGIC**: `dsp4_logic_driveall.c49f4128a083` flashed for the ladders
   (FLASH OK on attempt 1, IDCODE `0x020a30dd` before and after), and
   `dsp4_logic.a1f6672af6c3` — the shipping bitstream, the state the bench
   lives in — restored at the end, FLASH OK on attempt 1, IDCODE checked
   both sides.
2. **DSP pair**: the pair this session found, `84c79513…` / `bb2a7c6e…`, booted
   from `/home/app/s78restore` and configured for D24, twice, at handback.
   `dsp4_spiphase.py` read chip 1 `MAGIC=0xD5B40001 CHIP_ID=1 BOOT_STAGE=7`
   and chip 2 `MAGIC 0xD5B40001 BOOT_STAGE 7 FRAME_COUNT 4453
   SPORT0_ERR_A 0x00000000`. **The S80 pair was NOT deployed** — the tree
   builds a different image now (the third config word) and deploying it was
   not asked for, the same position S76 through S79 took.
3. **`GPIO 26` (AN_EN)**: raised once under this dispatch's authority for
   gate 4 (`op dh`, 300 ms, read, `op dl`), and **`op dl | lo` at handback —
   read back, not assumed**, four times over the session's last three steps.
4. **`GPIO 27` (CS_M)**: `ip pu | hi`, as found, and **never written**. The 595
   SAFE image was therefore NOT restored — see §3.3 and S80-10; it is a hub
   note with a one-line fix rather than something done unasked.
5. **The codec's register image** is as S79's `--reset` left it. It was not
   re-run, deliberately: re-running it re-asserts full mic gain (§3.3).
6. **`/home/app/dspboot` was NOT overwritten** and `ldr/manifest.txt` is
   untouched. Every arm ran from its own staging directory under
   `/home/app/dspcap/`; the AN_EN A/B ran from `/home/app/dspcap/s80probe`
   and the handback from `/home/app/s78restore`.
7. **`matrix-app`** active, **3 of 3 MCUs verified** (`H1S1`, `H1S3`, `H1S4`)
   on the second restart, read from the whole of `/home/app/logs/log` per the
   standing bench note. The first restart verified 1 of 3 — the known race,
   recorded rather than smoothed.

**No contract note is due for this session** and the absence is deliberate:
`release-notes-contract-convention.md` is scoped to matrix definition contract
inputs and generated contract outputs, `defs.lock` and the submodule did not
move, and `check-contract-drift.sh` completes with no matrix or address change.
`DIAG_BUILD_CFG3` is a diag register; its record lives in
`proposals/CONTRACT-PROPOSAL-S75.md`, which now carries the filled layout.

---

## 7. 🔴 For the hub

**S80-Q1 — `product_fit.py`'s CONSTRUCTION NEEDS RE-ANCHORING AND THAT IS A
DECISION, NOT A REGENERATION.** The prediction interpolates S27's two measured
anchors; against S80's rows those anchors are out by +43 points on D24 and up to
+85 on D32, and the two rows labelled *(ANCHOR — this is a control)* now fail as
controls. Re-anchoring on S80's rows rewrites every published prediction for
every product, and **D12 has no driven row to anchor against** (§4.2). Options:
(a) re-anchor A and B on S80's silent rows and leave C predicted from D16/D24/
D32 only; (b) re-anchor all three rows and accept D12's C row as extrapolated
rather than interpolated; (c) leave the construction as S27's and treat the
measured column as the only live number, which is what the table does today.
**Recommendation: (a)** — the silent rows are the ones every product spends its
life in, they are proven on all four products, and the slopes are flat enough
over three segments (§4.5) to carry the interpolation honestly.

**S80-Q2 — NOTHING IN THE RANGE FITS DRIVEN, AND THE GOAL LINE NEEDS RESTATING
AGAIN.** §4.7. D16 is 13 points over on chip 2, D24 27.5, D32 64.3 on chip 1;
D12's row will not prove. Every product fits **silent, loaded** except D32,
which is over at its own boot configuration. Is the driven/loaded row (every FX
engine live at Type 3, every send open, full-scale stimulus on all 46 inputs at
once) the row the product must fit — or is it, as its own definition suggests, a
deliberate worst case above anything a desk will do, with the silent/loaded row
as the product bar? **This changes what the optimisation programme is for and no
session should pick the answer.** Note that S24/S27/S28 already accepted D32
chip 2 missing 1,914 of 270,000 blocks on rows B and C, so the bar has not been
"zero missed blocks on every row" for some time.

**S80-Q3 — THE D16/D12 SINGLE-CHIP QUESTION (PW 09-11) GETS A NO FROM THESE
ROWS.** §4.7. A D16's chip 2 alone is 113 % of budget driven and 87.7 % silent/
loaded; there is no version of folding chip 1's 84.6 % onto it. If the intent
was *silent/loaded* rather than driven, a D16 at 55.9 + 87.7 = 143.6 points of
one chip is still not close. **Should the D16/D12 platform question move to the
FPGA engine, or should it be restated against a defined smaller graph** (fewer
FX engines, fewer aux buses) rather than the superset image every product boots
today?

**S80-Q4 — THE 595 SAFE IMAGE IS NOT ON THE UNIT AND ONE LINE PUTS IT THERE.**
S80-10. `codec4619.py --reset` leaves all 24 mic preamps unmuted at gain 63, and
S79's handback ran it. Phantom is off so nothing is at risk of damage, but it is
not the safe image and any EIN or noise figure taken on this bench now is taken
at full gain. The fix writes the chain and therefore drives CS_M, which this
dispatch's standing handback said to leave untouched — so it is asked for rather
than done:

```
sudo python3 -c "import sys; sys.path.insert(0,'/home/app/s55'); \
import s55_chain as CH; ok,got=CH.send([0x01]*24+[0x00]); \
print('before:', ' '.join('%02X'%b for b in got[0])); \
print('VERIFIED 200/200' if ok else 'MISMATCH')"
sudo pinctrl set 27 ip pu
```

The `before:` line is also the answer to *"what was actually in the chain"*,
which §3.3 could only infer from the H1S1 source.

**S80-Q5 — READING AN AK4619 REGISTER NEEDS AN H1S1 CHANGE, AND IT IS THE
CHEAPEST THING LEFT ON S79-Q1.** S80-6. A read arm in `CodecPoll()` (command
`0xC1` beside the existing `0xC3`), a `SpiTx` variant that returns MISO, and one
matrix cell to carry the byte back — then "does the codec answer on SPI at all"
becomes a one-line bench question instead of a probe. Beside it, S80-7: a frame
counter on `CDC_O` in the LOGIC would settle the clock half, and the only ways
out of that CPLD are its four TEST pins or a DSPA lane. Both are small pieces of
firmware/HDL work that would retire a probe each, and neither is this repo's to
schedule.

**S80-Q6 — `dsp4_inscan.py` IS VOID ON EVERY BUILD THAT SHIPS AND IS STILL IN
THE RECIPE.** §3.7 note 1. It peeks `_rx_slot_C1_IN_nn`, which are dead symbols
under `DSP4_BLOCK_KERNELS`, so it answers STATIC zero whether the lanes are
alive or dead — and the standing bench note (item 18) recommends it for exactly
the question it cannot answer. It wants either a rewrite onto the `_buf_`/block
symbols or removal from the recipe. S79 quoted it as evidence and that part of
S79-2's case is void, though its conclusion stands on other grounds.
