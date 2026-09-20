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

**Gate 1 is done and it is the session's result: `DIAG_BUILD_CFG3` carries
the switches the two full words cannot, and two images that differ in any
of them can no longer read back the same triple.** The shipping triple is
**`0xCF45FF10` / `0xE2018264` / `0xC47C0F26`**, and the third word is
physically present exactly once in each boot stream built from this tree.
S27-3 and S79's park-gate hole are both closed in it, and the word's DM cell
is no longer compiled out — which was the price, paid once. Two real defects
in the machinery fell out of the change and both are of the class it exists
for: `DIAG_BUILD_CFG2` has carried `DSP4_TEST_NODES` since S49 and the
repo-side computation of that word never knew, and `build_defaults()` was
silently dropping every switch whose default references another switch.
**Gate 3 is done**: the card's `s70lib.py` is the repo's, and the oscillator
ceiling read back off the card is the derived −14.89 dBFS and not the old
−12.00 constant that sat above the codec's pin rating.

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
