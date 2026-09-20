provenance: AI-drafted 2026-09-20 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S79 — what runs for nothing, switched off; and the 6.16 dB retired

**Session 79, 2026-09-20, rev C unit + desk.** Hub dispatch
`tasks.md` 2026-09-20 03:20Z, answering S78's five questions. Four gates:
the AUX 1 → talkback loop with the analog rails authorised, `DSP4_AUXIN_BYPASS`
carried into `shipping.config`, the product-driven bypass for chip-2 nodes no
cell on the booted product can reach, and the S28/S29 re-take last.

---

## 0. Outcome in one paragraph

**Gate 3 is done and it is the session's result: `CFG_MTX_MASK` is the fourth
product word, `C2_MIX_AUX_nn` joined the aux gate it had never been behind, and
between them a D24 stops calling ten chip-2 node instances that no cell on a
D24 can address** — four aux mixers and two whole matrix chains — worth
**0.73–0.85 points of chip 2**, with **D32 unchanged within ±0.27 points** and a
D16 or a D12 skipping 18 and 20 instances. **Gate 2 is done: the S32 off-aux
park gate now ships**, re-measured at **1.55–2.12 points of chip 2 on a D24 and
4.86–5.41 on a D32** (S32 said 4.84–5.22, nine days ago, on a different
instrument). **Together, chip 2 is 2.4–2.5 points better on a D24 and 4.9–5.7
on a D32**, and the D24 silent/loaded row crosses back under budget
(100.64 % → 99.75 %). The shipping word does not move, because neither diag
word carries the park-gate switch — which is itself now printed on every
`check_shipping_config.sh` pass rather than remembered.

**The goal line needs restating and S79-Q2 asks the hub to restate it.** The
dispatch asked for "chip 2's ten points back on D24". S78's ten points are 24
unconditional nodes, and **fourteen of them are aux buses and matrix buses a
D24 actually has** — product functions that have to run. Ten instances is what
no cell can reach, and ten instances is 0.73–0.85 points. The park gate brings
the session's total to 2.4–2.5; the remaining seven and a half are not
available by bypassing anything.
**Gate 1's loop could not be measured and the reason is a result: with AN_EN
HIGH, `!RST_C` pulsed and `StartAK4619()` re-run, every converter lane on chip 1
still reads exact digital zero** — so S78's attribution of the dark loop to the
rails is disproved, and what is wrong is upstream of anything a dispatched
session can reach. **The 6.16 dB is retired anyway, without the loop**: it is
neither a loss nor a bit. It is the datasheet's own `±2.83 Vpp` read as a
differential swing when it is per pin; read per pin, the codec's differential
full scale is +8.24 dBu against the +8.36 dBu S70 derived from the loop — a
0.12 dB agreement — and S70 raised exactly this alternative and dismissed it on
a sign error. **The talkback input is not 6 dB hot. The bench's own oscillator
cap was**, and that is fixed here.

---

## 1. Gate 1 — the 6.16 dB, retired

### 1.1 What the number is

S70 derived the ADC's full scale at the talkback XLR from the loop:

```
ADC FS at J1 = DAC FS - loop gain = +23.13 dBu - 14.774 dB = +8.356 dBu   (MGN2R code 2, 0 dB)
```

and set against it the AK4619's own full scale, `2.83 Vpp`, *read as a
differential swing*: `2.83/(2*sqrt(2)) = 1.0006 Vrms = +2.218 dBu`. The gap is
**6.138 dB**, quoted as 6.16 in S78. S70 attributed it to "about 6 dB of loss
between J1 and the codec's input pins" and added "12 dB if that 2.83 Vpp is per
pin rather than differential".

**The dispatch asks for it one way or the other: a measured loss, or a bit.
It is neither, and the third answer was in S70's own sentence.**

### 1.2 It is not a loss, because there is nothing on the path to lose in

mx26's netlist walk of the D24 analog board gives the whole chain from the XLR
to the codec pins, and it is two components:

```
docs/d24-analog-paths.md:130  | analog J1 XLR pin 2 (hot)  | AK4619 IN4N (pin 9)  | C4,  one cap |
docs/d24-analog-paths.md:131  | analog J1 XLR pin 3 (cold) | AK4619 IN4P (pin 10) | C11, one cap |
```

The same statement appears independently in `MW/D24/DSP/s71/codec-lanes.md:47-48`
and `MW/D24/DSP/dsp4-s34-20260911.md:333`. **One series coupling capacitor per
leg, no divider, no pad, no resistor** — and a series capacitor has no passband
loss. There is no component for 6 dB of attenuation to live in. (The D24's *mic*
inputs do go through a discrete gain network, `d24-analog-paths.md:166-168`;
the talkback XLR does not go through the mic pre at all.)

### 1.3 It is not a bit either, and S70's own T3 ladder proves it

A bit in the direction that would explain the gap is a one-bit RIGHT shift
somewhere after the ADC: the lane would then read 6.02 dB below what the ADC
actually produced, the derived loop gain would be 6 dB low, and the derived
ADC FS at J1 would be 6 dB high — exactly the observed sign.

**If that were true, S70's T3 ladder would have been measuring a clipped ADC.**
At MGN2R 0 dB, T3's hottest row reads the lane at **−5.980 dBFS RMS with THD+N
−87.89 dB (0.0040 %)**. Under the shift hypothesis the ADC's own output at that
point is `−5.980 + 6.021 = +0.041 dBFS RMS`, i.e. 3.05 dB past full-scale peak —
a hard-clipped sine, whose THD+N is percent, not four thousandths of one. And
the ladder runs the wrong way for an overload: THD+N **improves** monotonically
with level, −73.97 → −82.43 → −86.00 → −87.89 dB as the lane goes −22.98 →
−12.99 → −8.99 → −5.98 dBFS. A path approaching clipping does the opposite.
Those rows were taken with the donor strip's compressor bypassed (S70-3), so
the knee they do not show is a real absence.

**So the lane is not 6 dB below the ADC.** S78 had already shown there is no
lane-specific shift on the DSP side — `C1_XIN_CODEC_01` applies the same
`ashift by -3` wire form as the bit-exact reference lane, and the MFD-2
doubling is common to every converter lane (S78 §2). T3 closes the remaining
places a bit could hide, because it does not matter WHERE a 6 dB right shift
is: any of them would have clipped that ladder.

### 1.4 What it is: the datasheet's notation, per pin

Read `±2.83 Vpp` as the swing on EACH of `IN4P`/`IN4N` — which is how a
differential input is specified — and the differential full scale is:

```
5.66 Vpp differential = 5.66/(2*sqrt(2)) = 2.0011 Vrms = +8.239 dBu
```

against the loop-derived **+8.356 dBu**. **The gap closes to 0.117 dB**, inside
the uncertainty of the one inherited number in the chain: `DAC_FS_DBU =
+23.13 dBu`, a single DMM reading of 2026-09-16.

S70's own alternative was this one, and it was dismissed with "12 dB if that
2.83 Vpp is per pin". That is a sign error: reading the figure per pin makes
the codec's differential full scale **larger** by 6 dB, so it closes the gap
rather than doubling it. One sentence, one sign, and an unexplained 6 dB stood
for a day with "a mic input 6 dB hot" as a live possibility behind it.

**Honesty about what this is.** §1.2 and §1.3 are a measured elimination of the
two hypotheses the dispatch named; §1.4 is arithmetic against the part's own
datasheet, not a measurement. The measurement that would close it directly is
the ADC's overload knee — drive the loop up at a fixed MGN code and find the
lane level at which linearity breaks; **0 dBFS means no shift and no pad**,
−6.02 dBFS means a bit. It needs the converters converting, which §2 is about.
The recipe is in §6.1.

### 1.5 The consequence, and it runs the other way from the reassuring one

**The product is fine. The bench instrument was not.** `s70lib`'s oscillator
ceiling was derived from the 6 dB pad that does not exist:

> "The measured loop gain puts the ADC's full scale at the talkback XLR at
> −18.6 dBu at MGN +27 dB, i.e. about 6 dB of loss between J1 and the pins, so
> the oscillator must never go above about −7 dBFS whatever the gain code.
> Everything here is capped at OSC_MAX = −12 dBFS, 5 dB below that."

With no pad, the pins see J1. At `OSC_MAX = −12 dBFS` the DAC puts
**+11.13 dBu** across J1 — 7.9 Vpp differential, about **3.95 Vpp on each pin**
— against the 3.3 Vpp the pins are specified for and an absolute maximum of
`min(AVDD+0.3, 4.3) = 3.6 V`. **The cap was believed to sit 5 dB below the
ceiling and in fact sat about 1 dB above it**, and S70's knee ladder (the run
that found the donor's compressor) reached it with the rails up.

Fixed in `MW/D24/DSP/s70/tools/s70lib.py`: `OSC_MAX` is no longer the
authority. `osc_ceiling()` derives the cap from the codec's own differential
full scale with no pad term — `AK4619_FS_DBU − DAC_FS_DBU = −14.89 dBFS` today
— every `osc()` call is asserted against it, and the refusal now prints the J1
level and the codec's full scale so the arithmetic is in the error message. The
margin is deliberately **zero** and the reason is stated in the file: at full
scale the ADC is already clipping, so a dB above it buys no measurement and
spends the 1.34 dB that is the pins' only remaining headroom — and a positive
margin would clamp T1's own low-gain points (MGN code 0 needs −15.26 dBFS to
put the lane at −6.5). **Every level S70 actually published stayed below the
new cap**; only the knee ladder exceeded it.

**The published S70 figures do not move.** Every level, EIN and headroom number
in `talkback.md` is derived from the measured loop gain, which is unchanged.
What changes is one sentence of attribution and one safety constant.

---

## 2. Gate 1 — the loop, and why it could not be measured

The dispatch authorised the rails: *"`sudo pinctrl set 26 op dh`, 150 ms settle,
measure, `op dl` before handback"*. That was done, exactly, and it did not help.

| step | GPIO 26 | chan 51 | chan 52 | chan 53 (talkback) |
|---|---|---|---|---|
| S69, rails off (recorded) | lo | — | — | **−83.06 dBFS** |
| S70, rails up (recorded) | hi | −75.9 | −98.9 | **−69.19 dBFS** |
| S78, rails off (recorded) | lo | −336.124 | −336.124 | −336.124 |
| **S79, rails off** | lo | **−336.124** | **−336.124** | **−336.124** |
| **S79, rails UP, 150 ms** | hi | **−336.124** | **−336.124** | **−336.124** |
| **S79, rails up + `StartAK4619()` re-run** | hi | **−336.124** | **−336.124** | **−336.124** |
| **S79, rails up + S_RESET (MainInit: RST_C pulsed, codec image reloaded)** | hi | **−336.124** | **−336.124** | **−336.124** |

`−336.124 dBFS` is the arithmetic floor, not a noise floor. **S78 attributed
this to AN_EN being low. It is not the rails**: they were raised, under the
hub's authority, and nothing moved by a thousandth of a dB — where S70's rails
witness moved slot 3 by 13.9 dB the moment GPIO 26 went high.

**The DSP half of the loop is perfect on the same boot.** `s70_route.py`, five
drive levels: the AUX 1 bus tracks the oscillator to **0.000 dB** at every
level (−83.017 / −73.006 / −63.006 / −53.006 / −43.017 dBFS for −80 … −40),
the route asserted and proved on MeasChan 35 before anything analog is read.
The DAC is being fed and the graph is running.

**It is the whole converter front end, not the codec.** Every chip-1 input
buffer, read directly through the symbol map on a boot with
`FRAME_COUNT 5678`, `SPORT0_ERR_A 0` and `BOOT_STAGE 7`:

```
_buf_C1_XIN_CODEC_01  STATIC  0x00000000 ...   _buf_C1_XIN_MEMS  STATIC  0xFFFFFFFF ...
_buf_C1_XIN_CODEC_03  STATIC  0x00000000 ...   _buf_C1_XIN_PI_L  STATIC  0x00000000 ...
_buf_C1_XIN_CODEC_04  STATIC  0x00000000 ...   _buf_C1_IN_01     STATIC  0x00000000 ...
```

`dsp4_inscan.py` reads **MOVING 0 / STATIC 24** on chip 1, and
`dsp4_s39_rxraw.py` reads the RX DMA words themselves as all zeros across its
five arms. The MEMS bridge on the DIGITAL board sits at a stuck `0xFFFFFFFF`
while the codec lanes on the ANALOG board sit at a stuck `0x00000000` — two
different idle levels, which says the SPORT is sampling real pin states and the
converters are simply not converting. The AK5558 lanes reading dead is the known
S34-1/S38-6 state and is not news; the AK4619 lanes reading dead is new since
S70 and is what breaks the loop.

**S79-2 is the 🔴 for the hub** (§7), because everything a dispatched session
can reach has been tried: AN_EN raised and verified `hi`; `!RST_C` pulsed via
H1S1's `MainInit`; `StartAK4619()` re-run; the MX bus answering on all three
MCUs; the DSP pair re-booted twice with the rails already up. What is left is
the FPC (J41), the PLL8 `CDC_O` clock group, or a rail that AN_EN does not gate
— and all three want a probe.

### 2.1 One observation, recorded and deliberately not attributed

The pair booted with AN_EN LOW came up with **`FRAME_COUNT 0`** — no audio block
had ever arrived, which is the reading an unprogrammed CPLD gives. The same pair
re-booted with AN_EN HIGH reached `FRAME_COUNT 5678` immediately. That is one
A/B with one variable and it would say AN_EN gates the frame clock — but S78 ran
this same pair on this same shipping bitstream with the rails down and had a
working graph, so the more likely reading is the known config-commit desync
race, and this session did not spend a boot separating them. Recorded as S79-3
so the next session is not surprised by a `FRAME_COUNT 0` first boot.

---

## 3. Gate 3 — the product-driven bypass

The dispatch's rule, and it is the whole design: **one image boots every
product (S28/D8), so a node no cell on the BOOTED product can reach must cost
zero.** Not a build switch — a build switch would be a second image, which D8
forbids — a word the host sends at boot.

### 3.1 The mechanism already existed and two families were outside it

`CFG_CHAN_MASK` and `CFG_AUX_MASK` have had readers since 2026-09-09:
`_mask_apply` (generated `chipN/mask_gates.asm`) resolves one `_mask_on[k]`
word per gate group at CONFIG_COMMIT, the chain's gate is three instructions,
and buffers a skipped node would leave stale are zeroed once. Chip 2 carried
**18 groups: twelve aux chains and six aux pairs.**

Two families sat outside every one of them:

| family | instances | gated before S79 | why it mattered |
|---|--:|---|---|
| `C2_MIX_AUX_01..12` | 12 | **no** | the D24 product config has masked auxes 9–12 off since S28, so four mixers ran for buses whose whole chain was already being skipped |
| `C2_RECV_MTX/MTX_FDR/MTX_OUT_01..04` | 12 | **no** | no word said otherwise — `product_fit.py`'s own docstring said so in as many words |

`C2_MIX_AUX_nn` was outside it for a plain reason: `AUX_OWNER_RE['chip2']`
matched `RECV_AUX`, `MTR_AUX` and `AUX_*`, and `MIX_AUX` is none of those. It is
the sum that FEEDS aux bus nn — its fixed feed is `_buf_C2_RECV_AUX_nn`, its
only reader is `C2_AUX_FDR_nn`, and the same rule already put both of those
behind aux nn's gate. Leaving it out did not make it safe; it made it
unconditional.

### 3.2 What changed

1. **`MIX_AUX` joins the aux rule** (`tools/dsp/dsp_codegen.py`,
   `AUX_OWNER_RE['chip2']`). No new word, no new cell, no new def row: the
   mask the host has been sending since S28 is the product statement.
2. **`CFG_MTX_MASK` (0xF006) is the fourth product word.** `_mtx_mask` /
   `_mtx_mask_live` beside the other two, defaulting to all-ones so a part
   between reset and the first commit runs the whole graph; `_mask_grp_word`
   grows a third value (`0 = chan, 1 = aux, 2 = matrix`); `_mask_apply` latches
   and resolves it in the same branch-free loop; `_tx_out_slot_C2_MTX_OUT_nn`
   joins the zero list, because it is a physical TX slot the DMA clocks out
   whether or not the chain that fills it ran.
3. **The host sends it** (`tools/pi/dsp4_config.py`), per product, from
   `defs/products/<p>/dsp.csv` and nothing else: **d32 `0xF`, d24 `0x3`,
   d16 `0x0`, d12 `0x0`**.
4. **The scoreboard learned the fourth word** (`tools/dsp/product_fit.py`),
   importing `mtx_owner` from the generator rather than forming a second
   opinion about which node sits behind which gate.

### 3.3 What it must not break, and what was done about each

S78 §5.3 named three ways this could be wrong. All three are handled and one of
them turned out to be a trap in the machinery rather than in the design:

* **`C2_MTX_OUT_*` drives a SPORT TX slot by DMA**, so a skipped call must leave
  silence rather than a stale block. `_tx_out_slot_C2_MTX_OUT_01..04` are in the
  new `_mask_zero_mtx_ptrs` table and are zeroed at commit for every masked
  matrix — the same mechanism, the same buffer shape, as
  `_tx_out_slot_C2_AUX_OUT_nn`.
* **`C2_MTX_FDR_*` publishes `_fdr_busy_*`.** On chip 2 nothing reads it:
  `src/ctl_epoch.asm` externs `_fdr_busy_C1_FDR_01..32` and no chip-2 fader.
  The host's `_fdr_level/_fdr_mute/_fdr_pan` cells keep taking writes; the node
  simply is not called.
* **A ramp in flight when the gate closes.** The gate closes once, at
  CONFIG_COMMIT, from a word that is a property of the product and does not
  change in service — unlike `DSP4_AUXIN_BYPASS`, whose gate opens and closes
  on the host's own `on` cell and needs the park to publish silence first.
* **S79-5, the one that would have been a memory corruption.** `gen_mask_gates`
  derives its zero list from `aux_owner` plus a type table with
  `MIX_BUS -> '_buf_'`, so the moment `MIX_AUX` matched the aux rule,
  `_buf_C2_MIX_AUX_nn` would have joined the zero list — and under block
  kernels that loop writes `DSP4_BLOCK_SIZE` words at the pointer. **Chip 1's
  `_buf_C1_BUS_AUX_nn` IS the block array; chip 2's `_buf_C2_MIX_AUX_nn` is a
  SCALAR in every build** (the chip-2 block wrapper puts the block in `_blk_`),
  so sixteen words would have gone off the end of it into whatever the linker
  placed next. Chip-2 `MIX_BUS` is now excluded explicitly, with the criterion
  written down: **zero what something OUTSIDE the gate reads** — the DMA reads
  `_tx_out_slot_*`, and the only reader of a MIX_AUX block is behind the same
  bit.

### 3.4 The one-instruction detour worth recording

The three-way select wants `r4 == 2`. `r4 = r4 - 2;` assembles as
`[Error ea1227] Semantic Error in type 2 instruction` — the SHARC's type-2
compute takes no immediate. The 2 lives in `r7`, loaded once before the loop.
Recorded because the error message does not say "no immediate here"; it says
the instruction is semantically wrong, which reads like the wrong opcode.

---

## 4. Gate 2 — `DSP4_AUXIN_BYPASS` into shipping

The hub's ruling: carry it through, once its proofs are re-taken on today's
pair. Landed at the foot of `MW/D32/DSP/SHARC/shipping.config`.

**What it is.** Twelve chip-2 `AUX_INPUT` nodes — `C2_SNK_IN_01..08`,
`C2_CODEC_AUX_IN`, `C2_PI_IN`, `C2_USB_IN`, `C2_BT_IN` — come up with `on = 0`
in `dsp.csv` and are CALLED on every block regardless, at about 1,130 cycles
each. With the switch on, a node whose `on` cell is 0 publishes one block of
silence, raises `_auxin_byp_<nid>`, and the chain then skips the call
altogether; a `0 -> 1` flip takes effect on its own block, because the gate's
first test is the host's own cell. Six instructions per node per block against
the ~1,130 a call costs.

**Why it was off.** `shipping.config.s32` set it to 1 as window candidate B and
`shipping.config` never named it, so `build.sh:258` has defaulted it to 0 since
2026-09-11. **That is the third time in this directory** — S8-2/S9-1 for BLOCK,
block kernels and the core clock, `DSP4_SHARED_KERNELS` at S76, and now this —
and each time the switch every table quoted was not the switch that shipped.

### 4.1 The shipping word does not move, and that is the finding

`DSP4_AUXIN_BYPASS` is in **neither** `DIAG_BUILD_CFG` nor `DIAG_BUILD_CFG2`.
Both words are full — `src/diag.h` says so at the point of definition, which is
why S75 designed a third word that is still unlanded (S75-13, PW's call) — so
**an image with the park gate on and one with it off read back the same
`0xE2018264`**. The standing instruction to update the mirrors if the switches
change the word therefore has nothing to update: `check_shipping_config.sh`
still announces `DIAG_BUILD_CFG 0xCF45FF10 / DIAG_BUILD_CFG2 0xE2018264`.

That is S12-7's shape, and this project treats it as a defect in the instrument
rather than a footnote, so it is closed the way S77-11 closed the mirror drift —
**structurally**. `cfg_words.py` now resolves the switch (a switch the tool does
not read is a switch it cannot warn about, which is exactly how it came to ship
at a default for nine days) and names it in `unrepresented()`; and
`check_shipping_config.sh` prints that list on **every pass**, not only on
failure:

```
shipping config: consistent; DIAG_BUILD_CFG must read 0xCF45FF10, DIAG_BUILD_CFG2 0xE2018264, ...
  NOT IN EITHER WORD: DSP4_AUXIN_BYPASS=1 — ... an image with the chip-2 off-aux park gate
    on reads back the same two words as one without it (S12-7's shape, S79). Identify the
    arm by its image md5 until DIAG_BUILD_CFG3 lands (S75-13).
  NOT IN EITHER WORD: DSP4_SHARED_KERNELS=15 — bits 2 (GATE) and 3 (FILT) are NOT in
    DIAG_BUILD_CFG2 ... (S27-3)
```

A check that is silent about its own blind spot reads as a check that has none.

---

## 5. The proofs

### 5.1 The reference reproduces the published record on the fixed instrument

Every row in this report was taken on `dsp4_logic_driveall.c49f4128a083` — the
S78-fixed stimulus, bit-exact on every lane (`LANE_SHIFT=0`, peak
`0x40000000` = −6.02 dBFS at the part). **A row taken on it is not comparable
with a row taken on `14df62d98a4d` at the same `AMP`**, which is every driven
row up to and including S78's bisect. So the first thing the session did was
re-take the shipping reference, and it lands on the record:

| arm | product | chip | S79 measured (two boots) | the record it reproduces |
|---|---|--:|---|---|
| `s79ref` | D32 | 1 | **163.99 / 164.01 %** | S77 G1: 164.10–164.58 % |
| `s79ref` | D32 | 2 | **157.36 / 156.66 %** | S77 G1: 156.71 / 156.89 % |
| `s79ref` | D24 | 1 | **124.06 / 123.56 %** | S76-4: 118.9 / 119.2 % |
| `s79ref` | D24 | 2 | **130.09 / 129.81 %** | — |

**The one-bit fix did not move the driven capacity number**: chip 1 at D32 lands
inside a tenth of a point of S77's figure and chip 2 inside three quarters, on
a stimulus that was 6 dB hot and wrapping before. That is a second, independent
confirmation of S77's own control (a 6 dB stimulus change moves cycles by
−0.09..+0.08 points) and it is worth having, because the alternative — that
every driven row in the record needed re-taking for its *level* — is now ruled
out for the capacity bar by measurement rather than by argument.

**The instrument's own resolution, from these rows**: the two boots of an arm
agree to 1,665 cycles on chip 1 and 904 on chip 2 at D24 (0.51 and 0.28 points),
83 and 2,310 at D32 (0.03 and 0.70 points). **Nothing below about 0.7 points is
quoted as a difference.**

### 5.2 `DSP4_CHAN_MASK=0` rebuilds BYTE-IDENTICAL across the whole change

`chip2/mask_gates.asm`'s header claims `DSP4_CHAN_MASK=0` is the byte-for-byte
control — "the whole file is inside this guard, and so are the live words and
the commit-time call in product_config.asm, so a control build is the pre-fix
image, the same md5, not merely the same behaviour". S79 adds a word to two
HAND-MAINTAINED files, so that claim had to be re-earned rather than assumed.
Built from the pre-S79 tree (`git archive HEAD`) and from this one, same flags:

| tree | `DSP4_CHAN_MASK` | chip 1 | chip 2 |
|---|--:|---|---|
| pre-S79 (HEAD) | 0 | `0f0868228159910e5ea3b498a9e76e6a` | `a4806ebfc18326bea8826d400ee86825` |
| **S79** | 0 | **`0f0868228159910e5ea3b498a9e76e6a`** | **`a4806ebfc18326bea8826d400ee86825`** |

**It did not pass first time, and the failure is the finding.** The first cut
put `_mtx_mask` in `sport_init.asm` and the `CFG_MTX_MASK` dispatch arm in
`product_config.asm` OUTSIDE the guard — alongside `_chan_mask` and `_aux_mask`,
which are outside it — and the control pair came out `9af75d1c` / `bef20e28`
against the pre-S79 `0f086822` / `a4806ebf`. A control that quietly stops being
a control is worth less than no control, so the word and its dispatch arm are
now inside `#if DSP4_CHAN_MASK` with the measurement written beside them. The
arm images are unaffected (`ce2630da` / `84f25fdb` before and after the guard
went on), because at `DSP4_CHAN_MASK=1` the two forms emit the same code.

### 5.3 The gate ownership rule, tested on the names that must NOT match

`aux_owner`/`mtx_owner` are anchored and name-based, and the comment on the aux
rule already says why (`C2_CODEC_AUX_IN` and `C2_XR_CODEC_AUX_L` are aux-shaped
names that are not aux buses). Checked against the new rule:

```
MIX_AUX_09       aux=9     mtx=None       MIX_MAIN_L       aux=None  mtx=None
AUX_FDR_09       aux=9     mtx=None       CODEC_AUX_IN     aux=None  mtx=None
RECV_AUX_09      aux=9     mtx=None       XR_CODEC_AUX_L   aux=None  mtx=None
MTX_OUT_03       aux=None  mtx=3
```

The chain emits **180 aux gates and 12 matrix gates** across its three orders
(per-sample, block, paired), one per contiguous run of one bus's nodes; the
three nodes of a matrix chain share a single gate because they share a key.

### 5.4 What each product stops calling

From the graph and the four config words, with no second opinion about which
node sits behind which gate — `product_fit.py` imports the generator's own
rules:

| product | `CFG_AUX_MASK` | `CFG_MTX_MASK` | `C2_MIX_AUX_*` newly skipped | matrix instances newly skipped | total |
|---|---|---|---|--:|--:|
| D32 | `0x00000FFF` | `0x0000000F` | — | — | **0** |
| D24 | `0x000000FF` | `0x00000003` | 09,10,11,12 | 03,04 (3 nodes each) | **10** |
| D16 | `0x0000003F` | `0x00000000` | 07…12 | 01…04 | **18** |
| D12 | `0x0000000F` | `0x00000000` | 05…12 | 01…04 | **20** |

**D32 is zero by construction, not by measurement** — its masks are all-ones
over both families, so every gate falls through — and the D32 driven rows below
are the negative control that says the gates themselves cost nothing.

---

## 6. Gate 4 — S28/S29, and the loop's missing measurement

### 6.1 The overload knee, when the converters convert again

The measurement that would close §1.4 directly, written down so it is one
session's work rather than a re-derivation:

1. Shipping LOGIC, the S69 `DSP4_TEST_NODES` pair (`a8dc45eb` / `251ce3b2`,
   staged `/home/app/s69`), boot + config twice, AN_EN up per the S70 recipe.
2. `s70lib.Rig()` — it asserts the route and the donor's dynamics, and its
   oscillator cap is now derived (§1.5), so the ladder cannot reach the pins'
   rating by accident.
3. MGN2R code 2 (0 dB). Sweep the oscillator from −25 dBFS to the cap in
   0.5 dB steps; at each point record the lane's RMS and THD+N.
4. **The answer is the lane level at which THD+N breaks upward.** −3.01 dBFS
   RMS (0 dBFS peak) means no shift and no pad, and §1.4 is confirmed on the
   part. −9.03 dBFS RMS means a one-bit right shift after the ADC, and a
   talkback input that reads 6 dB low.

S70's T3 ladder already argues for the first answer (§1.3) and this would
measure it.

### 6.2 S28/S29 — seven arms, still due, and now with a reason to be careful

`cap-s28-{d12,d16,d16oldprover,d24,d32}`, `cap-s29ctl-d32`, `cap-s29ns-d32`.
The morning went on gates 1–3 and these were not re-taken. They remain due,
one line each:

```
ARM=s28d12 PRODUCT=d12 ./capacity.sh --driven      # and d16, d24, d32
SCOPE_ID=1 ARM=s29ns PRODUCT=d32 ./capacity.sh --driven
```

on `./loadlogic.sh driveall`, restoring `shipping` afterwards.

**S79 changes what they measure, and that is an argument for doing them now
rather than later.** Every S28 row was taken before `CFG_MTX_MASK` existed, so
a D12 row was a row for a product running four matrix chains and eight aux
mixers it has no cells for — **twenty node instances**, the largest share in
the range. The S28 table's own caveat said so ("the firmware runs four groups,
six FX engines and four matrix buses whatever is booted, because no word says
otherwise"); one third of that sentence is now false, and the D12/D16 rows are
the ones that move most.

---

## 7. The unit, as it was left

1. **LOGIC**: `dsp4_logic_driveall.c49f4128a083` was flashed for the driven
   ladders (`FLASH OK on attempt 1`), and `dsp4_logic.a1f6672af6c3` — the
   shipping bitstream, the state the bench lives in — restored at the end.
2. **DSP pair**: the pair this session found, `84c7951333e982204a38fe65e49d3fd6`
   / `bb2a7c6ea9e5d0caa419bc0b15a97f7c`, re-booted and configured for D24.
   **The S79 shipping pair was NOT deployed**: the tree now builds a different
   image (the park gate and the two masks) and deploying it was not asked for,
   the same position S76, S77 and S78 took.
3. **`GPIO 26` (AN_EN)**: raised under this dispatch's authority
   (`op dh`, 150 ms, measured, `op dl`), and **`op pd | lo` at handback** —
   verified, not assumed. Analog last up, first down. `GPIO 27` (CS_M)
   `ip pu | hi`, as found and never written.
4. **The codec's register image was re-loaded** — `codec4619.py --reinit`, then
   `--reset`, which re-runs H1S1's `MainInit` and so pulses `!RST_C`, reloads
   the AK4619 init image **and clears the 595 mic-gain chain**. The chain was
   left as `MainInit` leaves it, not as S70's SAFE image; both are benign
   (gain 0, phantom off) and the difference is recorded here rather than
   silently restored.
5. **`/home/app/dspboot` was NOT overwritten** and `ldr/manifest.txt` is
   untouched. Every arm ran from its own staging directory under
   `/home/app/dspcap/`.
6. **`matrix-app`** restarted and its MCU verify read from the whole of
   `/home/app/logs/log`, per the standing bench note.

---

## 8. Findings

**S79-1. 🟢 THE 6.16 dB IS NEITHER A LOSS NOR A BIT — IT IS THE DATASHEET'S
NOTATION, AND S70 RAISED THE RIGHT ANSWER AND DISMISSED IT ON A SIGN ERROR.**
The loss is ruled out by the netlist: J1 pin 2 → C4 → IN4N and pin 3 → C11 →
IN4P, one coupling capacitor per leg and no divider, pad or resistor
(`d24-analog-paths.md:130-131`, and independently `s71/codec-lanes.md:47-48`
and `dsp4-s34-20260911.md:333`). A one-bit right shift is ruled out by S70's own
T3 ladder: at MGN2R 0 dB the lane reads −5.980 dBFS RMS at **THD+N −87.89 dB
(0.0040 %)**, where the shift hypothesis puts the ADC 3.05 dB past full-scale
peak, and THD+N *improves* monotonically with level (−73.97 → −87.89 dB over
17 dB) where an approaching overload does the opposite. What fits is the third
reading: `±2.83 Vpp` is PER PIN, the differential full scale is 5.66 Vpp =
2.0011 Vrms = **+8.239 dBu**, and S70's loop-derived **+8.356 dBu** agrees with
it to **0.117 dB** — inside the uncertainty of `DAC_FS_DBU`, a single DMM
reading. S70 wrote "12 dB if that 2.83 Vpp is per pin rather than
differential"; per pin makes the codec's differential full scale LARGER by
6 dB, so it closes the gap rather than doubling it. **No mic input is 6 dB
hot, no published S70 figure moves, and S77-Q1 is closed.**

**S79-2. 🔴 WITH AN_EN HIGH, EVERY CONVERTER LANE ON CHIP 1 STILL READS EXACT
DIGITAL ZERO — S78's ATTRIBUTION TO THE RAILS IS DISPROVED AND THIS NEEDS
HANDS.** Raised per the recipe and verified `hi`; `!RST_C` pulsed and the
AK4619 init image re-loaded through H1S1's `MainInit`; the MX bus answering on
all three MCUs; the pair booted twice with the rails already up
(`BOOT_STAGE 7`, `FRAME_COUNT 5678`, `SPORT0_ERR_A 0`). All three codec return
lanes read `−336.124 dBFS` — the arithmetic floor — before, during and after,
where S70's rails witness moved slot 3 by **13.9 dB** the instant GPIO 26 went
high. The DSP half of the loop is perfect on the same boot (AUX 1 tracks the
oscillator to 0.000 dB at five levels). `dsp4_inscan.py` reads MOVING 0 /
STATIC 24 and the RX DMA words are zeros; the MEMS bridge on the DIGITAL board
sits at a stuck `0xFFFFFFFF` while the codec lanes on the ANALOG board sit at
`0x00000000`, so the SPORT is sampling real pin states and the converters are
not converting. Everything reachable from a dispatched session has been tried.
**What is left is the FPC (J41), the PLL8 `CDC_O` group, or a rail AN_EN does
not gate** — see S79-Q1.

**S79-3. 🟡 A FIRST BOOT WITH `FRAME_COUNT 0`, RECORDED AND NOT ATTRIBUTED.**
The S69 pair booted (twice, per the standing recipe) with AN_EN low came up
with `FRAME_COUNT 0` and `SEC_COUNT 0` — the reading an unprogrammed CPLD gives
— and the same pair re-booted with AN_EN high reached `FRAME_COUNT 5678`
immediately. One A/B with one variable, which would say AN_EN gates the frame
clock; but S78 ran this pair on this bitstream with the rails down and had a
live graph, so the likelier reading is the known config-commit desync. Not
separated here. A session that sees `FRAME_COUNT 0` on a first boot should
re-boot before concluding anything.

**S79-4. 🔴 `s70lib`'s OSCILLATOR CAP WAS DERIVED FROM THE PAD THAT DOES NOT
EXIST, AND SAT ABOVE THE CODEC'S PIN RATING RATHER THAN 5 dB BELOW IT.** The
file's own reasoning: "about 6 dB of loss between J1 and the pins, so the
oscillator must never go above about −7 dBFS… capped at OSC_MAX = −12 dBFS,
5 dB below that". With no pad the pins see J1, and at −12 dBFS the DAC puts
**+11.13 dBu** across J1 = 7.9 Vpp differential = about **3.95 Vpp per pin**,
against a 3.3 Vpp specification and an absolute maximum of
`min(AVDD+0.3, 4.3) = 3.6 V`. S70's knee ladder reached that level with the
rails up. Fixed: `osc_ceiling()` derives the cap from the codec's own
differential full scale with no pad term (`−14.89 dBFS` today), every `osc()`
call is asserted against it, and the refusal prints the J1 level and the
codec's full scale. **Every level S70 published stayed below the new cap**;
only the knee ladder exceeded it. The bench copy at `/home/app/s70` must be
re-staged before the next loop session.

**S79-5. 🔴 THE AUX RULE'S ZERO LIST WOULD HAVE WRITTEN SIXTEEN WORDS PAST A
SCALAR.** `gen_mask_gates` derives what to silence from `aux_owner` plus a type
table with `MIX_BUS -> '_buf_'`, so the moment `C2_MIX_AUX_nn` matched the aux
rule it joined the zero list — and under block kernels that loop writes
`DSP4_BLOCK_SIZE` words at the pointer. **Chip 1's `_buf_C1_BUS_AUX_nn` IS the
block array; chip 2's `_buf_C2_MIX_AUX_nn` is a SCALAR in every build**, because
the chip-2 block wrapper puts the block in `_blk_`. Sixteen words would have
gone off the end of it into whatever the linker placed next, at CONFIG_COMMIT,
on every masked aux of every D24 — a corruption with no symptom at the point
it happened. Chip-2 `MIX_BUS` is excluded explicitly and the criterion is now
written down at the exclusion: **zero what something OUTSIDE the gate reads.**
The DMA reads `_tx_out_slot_*`; the only reader of a MIX_AUX block is behind
the same bit.

**S79-6. 🔴 `DSP4_AUXIN_BYPASS` SHIPPED AT `build.sh`'s DEFAULT FOR NINE DAYS,
AND NEITHER DIAG WORD CAN SAY WHICH IMAGE YOU HAVE.** S78-Q3, confirmed and
closed: `shipping.config.s32` set it to 1, `shipping.config` never named it,
`build.sh:258` defaulted it to 0. It is now named in the shipping file. The
second half is structural: the switch is in NEITHER `DIAG_BUILD_CFG` nor
`DIAG_BUILD_CFG2` — both are full, which is why S75 designed a third word that
is still unlanded (S75-13) — so the park-gate image and the pre-S79 one read
back the same `0xE2018264`. That is S12-7's shape on a SHIPPING path.
`cfg_words.py` now resolves the switch and names it in `unrepresented()`, and
`check_shipping_config.sh` prints that list on **every pass**, not only on
failure. A check silent about its own blind spot reads as a check that has
none. **The shipping word is unchanged at `0xE2018264`; no mirror needed
updating, and that is the defect rather than the good news.**

**S79-7. 🔴 THE `DSP4_CHAN_MASK=0` CONTROL BROKE AND WAS CAUGHT BY BUILDING
IT.** `chip2/mask_gates.asm`'s header claims that switch rebuilds the pre-fix
pair byte for byte. The first cut of `CFG_MTX_MASK` put `_mtx_mask` and its
dispatch arm outside the guard — where `_chan_mask` and `_aux_mask` live — and
the control pair came out `9af75d1c` / `bef20e28` against the pre-S79
`0f086822` / `a4806ebf`. Both are now inside the guard and the control is
byte-identical again on both chips. A stated invariant that nobody rebuilds is
a comment, not an invariant.

**S79-8. 🟢 THE FIXED STIMULUS DID NOT MOVE THE DRIVEN CAPACITY NUMBER.** The
shipping reference re-taken on `driveall c49f4128a083` reads D32 chip 1
**163.99 / 164.01 %** against S77's 164.10–164.58 % and chip 2 **157.36 /
156.66 %** against 156.71 / 156.89 %. S77's own 6 dB stimulus control said this
would be so (−0.09..+0.08 points); this is the same statement across the actual
fix, and it means the record's driven rows do not need re-taking for their
LEVEL. They do need re-taking to be comparable arm-to-arm, which is a different
thing and is §6.2.

**S79-9. 🟡 D32's PRODUCT DEFINITION SAYS TWELVE MATRIX BUSES; THE FIRMWARE
BUILDS FOUR AND `defs/products/d32/dsp.csv` ADDRESSES FOUR.** `mtx,12` in
`defs/products/d32/d32.csv`, against `Matrix001..004` in its own `dsp.csv` and
four `C2_RECV_MTX/MTX_FDR/MTX_OUT` instances in the graph. Every other product
agrees between its size key and its cells (d24 `mtx,2` and `Matrix001/002`;
d16 and d12 no key and no cells). `product_fit.py` had a bare `min(…, 4)`
hiding it; both numbers are now separate rows of the fit table so the
disagreement is on the table instead of inside a `min()`. **This is a defs
question and this repo has invented nothing** — it sits beside S78-Q2, which is
already with PW.

**S79-11. 🟢 THE PARK GATE'S S32 FIGURE REPRODUCES NINE DAYS LATER ON A
DIFFERENT INSTRUMENT, AND THE D24 FIGURE IS NEW.** D32 chip 2 **−4.86 to
−5.41 points** against S32's 4.84–5.22; D24 chip 2 **−1.55 to −2.12**, never
quoted driven before. The two arms carry the SAME chip-1 bytes (`ce2630da`),
so that column is the instrument talking to itself and it spans −0.10 to +0.46
points — the floor under every claim in this report. Gate 2's proofs are
re-taken on today's pair, which is what the hub's ruling asked for.

**S79-12. 🟢 THE PRODUCT-DRIVEN BYPASS IS WORTH 0.73–0.85 POINTS OF CHIP 2 ON A
D24 AND NOTHING ON A D32, AND THE GATES WERE READ BACK OFF THE PART.** Ten node
instances — `C2_MIX_AUX_09..12` and the `RECV_MTX`/`MTX_FDR`/`MTX_OUT` of matrix
3 and 4. The A-row measurement is the tightest in this report: the two boots of
each arm agree to **6 and 9 cycles** against a difference of **2,400**. D32's
every delta is between −0.27 and +0.26 points against a 0.70-point boot spread.
And the gates are witnessed rather than assumed: `_mask_on[22]` reads **22 RUN /
0 SKIP** on a D32 and **14 RUN / 8 SKIP** on a D24, with `_mtx_mask_live`
`0x0000000F` and `0x00000003`.

**S79-13. 🟡 A MASK WRITE TO A RUNNING PART REPORTS SUCCESS AND DOES NOT
LAND.** `dsp4_config.py --product d24 --chip 2` at a part already running as a
D32 printed `wrote 6 registers` and left `_chan_mask_live`, `_aux_mask_live` and
`_mtx_mask_live` at their D32 values; a full boot + config twice moved them.
The known config-commit desync, and it applies to all three mask words — so a
single write that "succeeds" is not a witness that a mask landed. The firmware
supports a mid-life mask change (`product_config.asm` says so and bounds its
atomicity); this is the HOST side of it and it is not proven.

**S79-10. 🟡 `product_fit.py` COULD NOT RUN AT ALL AND HAD NOT BEEN ABLE TO
SINCE THE S56 CELLS LANDED.** `assert len(addressed) + len(unmapped) ==
len(defined)` fired on every product, short by exactly two:
`Test001CaptureArm001` and `Test001CaptureReady001`, present in every
`MW/<P>/MX/_matrix.csv` and in neither half of the stale proposal tree. The
scoreboard is generated from that tree, so it could not be republished by
anyone. Fixed by the documented regeneration
(`DSP_LANDED_DIR=proposals/defs/products … gen_dsp.py --force --propose`), which
is a proposal tree and not a landed def. The table is republished below.

---

## 9. 🔴 For the hub

**S79-Q1 — THE CONVERTERS ARE DARK AND IT IS NOT THE RAILS. THIS NEEDS
HANDS.** S79-2 in full. AN_EN raised under this dispatch's authority and
verified `hi`; `!RST_C` pulsed and the AK4619 init image re-loaded; the MX bus
answering on all three MCUs; the pair booted twice with the rails up and the
graph running; and all three codec return lanes still read the arithmetic floor,
`−336.124 dBFS`, with the AUX 1 bus tracking the oscillator to 0.000 dB on the
same boot. The state S77 recorded as *audio LIVE* and S78 as *audio INERT*
therefore changed between S77 and S78, and *not* because of GPIO 26. Three
places are left and none is reachable from a dispatched session:

1. **the ADC FPC, J41** — the codec is on the D24 **Analog** PCBA and is
   reached over the J41/J42 flat-flex; a seated-but-not-contacting connector
   looks exactly like this;
2. **the PLL8 `CDC_O` clock group** — the converter clock for that lane;
3. **a rail AN_EN does not gate.**

**One probe settles which**: `CDC_O` at J41, or the AK4619's `SDOUT` at the
part. Until then every talkback, EIN, gain-law and loop measurement on this
bench is blocked, and the §6.1 knee — the one measurement that would confirm
§1.4 on the part rather than on the datasheet — cannot be taken.

**S79-Q2 — TEN NODE INSTANCES IS NOT TEN POINTS, AND THE GOAL LINE NEEDS
RESTATING.** The dispatch's goal was "chip 2's ten points back on D24". S78's
ten points are the cost of **24 unconditional chip-2 nodes** — S22's matrix
mixer and S23's aux mix buses and FX returns — and **fourteen of those
twenty-four are aux buses and matrix buses a D24 actually has**. They are
product functions and they have to run. What can be made free is what no cell
can reach, and that is **ten instances worth 0.73–0.85 points of chip 2**
(§10). The rest of the ten points is not available by bypassing anything; it is
available only by making the nodes themselves cheaper, or by not defining them.
**Is that the answer the hub wants recorded against S78-Q5, or should a
follow-up price the 24-node class itself?**

**S79-Q3 — WHERE THIS LEVER ACTUALLY PAYS IS D16 AND D12, AND NOBODY HAS
MEASURED THEM SINCE IT EXISTED.** A D24 skips ten instances; a **D16 skips 18
and a D12 skips 20** — all four matrix chains and six or eight aux mixers —
which is the largest share in the range and exactly the products the fit table
calls comfortable. Those rows are S28's, they were taken on the pre-fix
stimulus, and they now also predate `CFG_MTX_MASK`. **S78-Q4's re-take is
worth more than it was**, and the D12/D16 arms need their products staged.

**S79-Q4 — D32's DEFINITION SAYS TWELVE MATRIX BUSES AND FOUR EXIST.**
S79-9. `defs/products/d32/d32.csv` has `mtx,12`; its own `dsp.csv` addresses
`Matrix001..004` and the graph builds four. Every other product agrees with
itself. This sits beside S78-Q2 (a) — which asked whether `Chan001MatrixOn/Send`
stopping at `002` on both products is a real limit or missing rows — and both
are `defs` questions. **This repo has invented nothing**; `CFG_MTX_MASK` is
derived from the `Matrix0NN` cells each product's own `dsp.csv` addresses,
capped at the four chains the firmware builds, which agrees with the `mtx` size
key for every product except D32's twelve.

**S79-Q5 — `/home/app/s70` HOLDS THE OLD OSCILLATOR CAP.** S79-4's fix is in
this repo; the bench copy is not. The next session that runs a loop measurement
must re-stage `MW/D24/DSP/s70/tools/s70lib.py` before it drives anything, or it
will run with a ceiling that sits above the codec's pin rating. There is no
script in this tree that deploys `s70lib.py` — the S77-1 shape, one file along.

---

## 10. The rows

Every row a recorded capacity row: `capacity.sh --driven`, two boots an arm,
three rows a boot (silent/default, silent/loaded, driven/loaded), 45 s dwell,
the regime proved on both chips before the driven row is quoted, a fresh
`chipN.sym.json` staged with every arm, each arm in its own staging directory
under `/home/app/dspcap/`. Stimulus: `dsp4_logic_driveall.c49f4128a083`,
`LANE_SHIFT=0`, peak `0x40000000` = **−6.02 dBFS at the part**. 983.04 MHz
measured on every row.

**The arms, and their definitions** — the definition is the COMMAND, because
`shipping.config` changed during this session and an arm whose definition lives
in a file that can move under it is not an arm (S11-1's shape). Every arm names
`DSP4_AUXIN_BYPASS` explicitly, including the ones that want it off:

| arm | tree | `DSP4_AUXIN_BYPASS` | chip 1 | chip 2 |
|---|---|--:|---|---|
| `s79ref` | pre-S79 (`git archive HEAD`) | 0 (file default) | `84c79513` | `bb2a7c6e` |
| `s79byp` | S79 | **0**, named | `ce2630da` | `84f25fdb` |
| `s79bab` | S79 | **1**, named | *(below)* | *(below)* |

`s79ref`'s pair is byte-identical to the pair on the unit and to S77's and
S78's, so the reference is the shipping image and not a rebuild of it.

### 10.1 The bypass, D24 — the goal line

`s79byp` − `s79ref`, per row, both boots:

| row | chip 1 | chip 2 |
|---|---|---|
| A silent/default | −0.00 / −0.11 pts | **−0.74 / −0.73 pts** |
| B silent/loaded | −0.11 / +0.00 pts | **−0.44 / −0.79 pts** |
| C DRIVEN/loaded | −0.52 / −0.02 pts | **−0.85 / −0.32 pts** |

**Chip 2 gains 0.73–0.85 points on a D24 and chip 1 is inside its own noise**,
which is what a chip-2-only change should read. The A row is the tightest
measurement in this report: the two boots of `s79ref` agree to **6 cycles** and
the two of `s79byp` to **9**, against a difference of **2,400**.

**One row crosses a line.** D24 silent/loaded on chip 2 reads **100.64 /
100.65 %** of budget on the reference and **100.20 / 99.86 %** with the bypass —
the row was over budget and is now at it.

### 10.2 D32, the negative control

`s79byp` − `s79ref` at D32, where both masks are all-ones and every gate must
fall through:

| row | chip 1 | chip 2 |
|---|---|---|
| A silent/default | −0.19 pts | +0.26 pts |
| B silent/loaded | −0.16 pts | −0.07 pts |
| C DRIVEN/loaded | +0.01 pts | −0.27 pts |

**Every delta is between −0.27 and +0.26 points**, against an instrument whose
two D32 boots differ by up to 0.70 points on chip 2 on an unchanged image.
**The gates themselves cost nothing measurable**, and D32's behaviour is
unchanged by construction as well as by measurement: with `_aux_mask = 0xFFF`
and `_mtx_mask = 0xF` every one of the 22 `_mask_on[]` words is non-zero, so no
gate branches and the call sequence is the reference's exactly.

### 10.3 The park gate, priced on today's pair — gate 2's proof re-taken

`s79bab` − `s79byp`: the same tree, the same chip-1 image (`ce2630da` in both
arms), one switch.

| product | row | chip 1 (identical image) | chip 2 |
|---|---|---|---|
| D24 | A silent/default | −0.00 / −0.01 | **−1.67 / −1.78 pts** |
| D24 | B silent/loaded | +0.20 / −0.00 | **−2.01 / −1.67 pts** |
| D24 | C DRIVEN/loaded | +0.16 / +0.00 | **−1.55 / −2.12 pts** |
| D32 | A silent/default | +0.19 / +0.00 | **−5.19 / −5.12 pts** |
| D32 | B silent/loaded | −0.10 / +0.11 | **−4.86 / −5.01 pts** |
| D32 | C DRIVEN/loaded | +0.12 / +0.46 | **−5.41 / −5.15 pts** |

**S32's figure reproduces nine days later on a different instrument**: S32
measured 4.84–5.22 points of chip 2 at D32 and this reads **4.86–5.41**. The
D24 figure — 1.55–2.12 points — has never been quoted driven before; S32's
`@s32` lead rows put the silent D24 A row at −1.6, which is the same number.

**The chip-1 column is a within-report noise witness and should be read as
one**: those two arms carry the SAME chip-1 bytes, so every figure in that
column is the instrument talking to itself. It spans **−0.10 to +0.46 points**,
which is the floor under every claim in this report.

### 10.4 Both levers together, against the image on the unit

`s79bab` − `s79ref`, chip 2:

| product | A silent/default | B silent/loaded | C DRIVEN/loaded |
|---|---|---|---|
| **D24** | **−2.40 / −2.51 pts** | **−2.45 / −2.46 pts** | **−2.40 / −2.45 pts** |
| **D32** | **−4.93 / −4.97 pts** | **−4.92 / −5.14 pts** | **−5.69 / −5.07 pts** |

**Chip 2 on a D24 is 2.4–2.5 points better in every regime, and on a D32
4.9–5.7**, for no audio change on either product that any cell can address.
The D24 driven row moves from **130.09 / 129.81 %** of budget to **127.69 /
127.37 %**, and the silent/loaded row from **100.64 / 100.65 %** to **99.75 /
99.76 %** — under budget on both boots.

### 10.5 The gates, resolved on the part

Not "the mask was sent" but "the mask was applied" — the S38-5 distinction, one
level up. `_mask_on[22]` read back over the parameter link after
CONFIG_COMMIT, on the `s79bab` pair:

```
d32:  _chan_mask_live 0xFFFFFFFF  _aux_mask_live 0x00000FFF  _mtx_mask_live 0x0000000F
      22 RUN / 0 SKIP      — every gate falls through, the call sequence is the reference's

d24:  _chan_mask_live 0x00FFFFFF  _aux_mask_live 0x000000FF  _mtx_mask_live 0x00000003
      14 RUN / 8 SKIP      — aux 9,10,11,12 SKIP; aux 9+10 and 11+12 SKIP;
                             matrix 3 and 4 SKIP; matrix 1, 2 and aux 1..8 RUN
```

**One trap found taking it.** Writing `dsp4_config.py --product d24 --chip 2`
at a part already running as a D32 reported `wrote 6 registers` and left all
three live words at their D32 values. A full boot + config, twice, per the
standing recipe, moved them. That is the known config-commit desync and it
applies to all three mask words, not only the new one: **a mask change in
service needs the cycle, and a single write that "succeeds" is not a witness
that it landed.**

---
