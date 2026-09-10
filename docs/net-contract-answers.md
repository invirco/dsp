provenance: AI-drafted 2026-09-10 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The three answers the DSP spoke owes the MW-Net wire declaration

For the net spoke's N4/N6 questions, filed against the `defs` wire sets
(discovery v0, align v1, hoplat v1) that land as a tagged step after the net
bench day. `MWN_AUDIO_PAYLOAD_OFF` is the field one of these answers moves,
and it is cheap now and expensive after the declaration lands.

**CORRECTED 2026-09-10 (S25 gate 1). The alignment answer was 8 bytes and
it is 4.** The correction is a MEASUREMENT, not a re-reading: see §2.4. It
does not move `MWN_AUDIO_PAYLOAD_OFF`, which stays at 40 either way — but
it **retires the caveat in §2.3 entirely**, and that caveat was the only
thing in this document the net spoke had to act on.

**One-line answer.** 96 k through-DSP = **82 samples / 854 µs, BY
CONSTRUCTION** (the DSP cannot be clocked at 96 kHz on this platform and
three independent things stop it); the block interface needs **4-byte
alignment — one 32-bit word — set by the DMA**, and neither the core nor
the framework asks for more, so **`MWN_AUDIO_PAYLOAD_OFF` STAYS AT 40**;
in-place = **yes** for the read, because a DSP node already reads its
samples straight out of the DMA receive ring every block with no staging
copy — but on the DSP product the question does not arise at all, because
the MW-Net endpoint is the RT1180 option card and what crosses the option
slot is **TDM8, not packets**.

**And the 802.1Q caveat is GONE.** With an 8-byte requirement, one VLAN tag
inserted by a customer switch moved the header 4 bytes and FLIPPED the
alignment; with a 4-byte requirement a 4-byte shift preserves it. Any
Ethernet frame whose payload starts on a word boundary satisfies the DSP,
tagged or not.

---

## 1. Through-DSP latency at 96 kHz — 82 samples, BY CONSTRUCTION

### 1.1 It is not measured, and here is exactly what blocks it

The 48 kHz figure was measured differentially: the same counter stimulus and
identical ALSA settings against two bitstreams, one looping inside the CPLD
(`dsp4_logic_pisel.bd9c100db7c2`) and one going through the DSP
(`dsp4_logic_maincap`), so the ALSA start skew cancels in the difference
(`dsp4-s17-20260910.md` §4). **That method cannot be run at 96 kHz on this
bench, and not because of the instrument.** Three separate things stop it,
and the first is the part:

1. **The part's own SPORT limit.** Data sheet Rev. A Table 14 caps
   `fSPTCLKEXT` at **31.25 MHz when transmitting data or frame sync**. A
   TDM16 lane needs 24.576 MHz BCK at 48 kHz — 27 % of headroom — and
   **49.152 MHz at 96 kHz, which exceeds the limit outright**. The
   inter-chip mix fabric is TDM16 on every one of `MIX_0..MIX_7`
   (`shared/dsp4-logic/tdm-lines.csv`), so this is not an edge lane that
   could be re-cut: it is the path between the two chips. Recorded since the
   2026-08-22 pin audit and it is one of the supporting facts under D6.

2. **The CPLD cannot generate the clocks.** `rtl/dsp4_clkgen.v` derives
   every clock role from one 49.152 MHz XO with a **1024-sysclk frame**,
   which is 48 kHz exactly: TDM8 is 8×32 = 256 BCK8 and TDM16 is 16×32 =
   512 BCK16, and one 1024-cycle counter serves both. At 96 kHz the frame is
   512 sysclk; BCK8 becomes sysclk/2 (producible) but **BCK16 becomes the
   sysclk itself**, which this design cannot emit as a registered divided
   clock and against which a MAX V cannot launch data on a falling edge.
   There is no 96 kHz bitstream and there cannot be one from this XO.

3. **The cycle budget is already spent and the clock is already maxed.**
   CCLK is **983.040 MHz**, which `src/cgu_init.asm` documents as the
   ADSP-21564**KSWZ10**-only row (fCCLK spec 400–1000 MHz) — there is no
   headroom to clock up and absorb the rate. Utilisation scales with sample
   rate at any block size: hold BLOCK and the block period halves while the
   work per block does not change; double BLOCK and the budget per block
   holds while the work doubles. Either way it is **×2**. S23's worst
   driven row, D32 chip 2 at **90.95 %**, becomes roughly **182 %** at
   96 kHz. That is D6's platform split measured rather than asserted.

So the figure below is BY CONSTRUCTION and is labelled as such wherever it
is quoted. It is a figure for a build that does not exist and would not fit.

### 1.2 The construction, and it reproduces every measured 48 kHz row

Every term in the through-DSP path is quantised in **samples**, not in time:
DMA half periods and TDM frame boundaries. Fitting the four measured rows on
record gives one model with a residual of at most one sample.

    L = (4 + n_tx_early) × BLOCK + 2 samples

where `n_tx_early` is the number of chips carrying `DSP4_TX_EARLY` (the
switch is a per-chip mask, and S9-2 measured its cost as **+16 samples per
chip** at BLOCK=16 — one block).

| BLOCK | `TX_EARLY` | model | measured | source |
|--:|--:|--:|--:|---|
| 16 | 0 (`n`=0) | 66 | **66 / 67** | S11 / `dsp4-s17` §4 |
| 16 | 2 (`n`=1) | **82** | **82**, and 82/83 on the tree | `dsp4-s17` §4 |
| 16 | 3 (`n`=2) | 98 | **99** | `dsp4-capacity-s11` |
| 32 | 0 (`n`=0) | 130 | **131** | `dsp4-capacity-s11` |

The two terms are the pipeline the plumbing note describes, counted
properly: **four block periods** — DSPA's RX DMA half, DSPA process→gather
into the inter-chip TX half, DSPB's RX half, DSPB process→gather into the
converter TX half — plus **2 samples** of TDM framing, one at each of the
two frame boundaries the difference against the CPLD-loop reference does not
cancel. `TX_EARLY` adds one whole block per chip because the core writes the
half the DDE is *not* clocking, which is a full period ahead.

**One figure on record does not fit this model and it is not smoothed
over.** `dsp4-plumbing.md` records 93 samples at BLOCK=32 — 2.9 block
periods, against the 4.03 the S11 row gives at the same block size. That
measurement predates `GATHER_FIRST` and was taken on the `DSP4_STRIPS=1`
graph, not the full one; it is the older number and the model is fitted to
the four rows above, not to it.

### 1.3 The answer

The shipping operating point is BLOCK=16 with `DSP4_TX_EARLY=2` (chip 2
only), which is the 82-sample contract figure at 48 kHz.

| | 48 kHz (measured) | 96 kHz (by construction) |
|---|--:|--:|
| through-DSP, samples | **82** | **82** |
| through-DSP, time | 1.708 ms | **854.2 µs** |
| block period (BLOCK=16) | 333.3 µs | 166.7 µs |
| through-DSP in block periods | 5.125 | 5.125 |

**In samples the figure does not move**, because every term is a block or a
frame; **in time it halves**, to 854 µs. If a future build held the 48 kHz
*time* budget instead, BLOCK=32 at 96 kHz gives 162 samples = 1.6875 ms —
but that build does not fit either, for the reason in §1.1 item 3.

---

## 2. The alignment the block interface requires — 4 bytes, set by the DMA

The question is put as three candidates — the SHARC core, its DMA, or the
framework's block buffers. They give three different numbers and the
binding one is the DMA's. §2.1 and §2.2 are the argument as it stood on
2026-09-10; **§2.4 is the experiment that overturned §2.2's half of it**,
and it is left in that order deliberately, because the reasoning that was
wrong is worth reading beside the measurement that settled it.

### 2.1 The DMA needs 4 bytes

The audio rings are DDE descriptor-list channels configured
`ENUM_DMA_CFG_MSIZE04 | ENUM_DMA_CFG_PSIZE04` with `XMOD = 4` bytes
(`src/dma_config.c`) — a 32-bit memory transfer size, whose `ADDRSTART` must
be aligned to that transfer size and to nothing wider. Nothing in the audio
path asks the DDE for a burst wider than a word. **4 bytes.**

### 2.2 The framework asks for nothing, and the core was argued to ask for 8 — WRONG, see §2.4

The framework's block buffers are the two `_blk_pool` slot pools
(`src/blk_pool.h`), addressed as `pool + n × BLOCK` words. The pool declares
no alignment and **the linker does not supply one**: of 5,452 DM symbols in
the chip-1 map of the S23 pair, **2,204 sit at ODD word addresses**, so a
`.var` gets word alignment and no more.

That the *scalar* path is content with 4 bytes is already measured on the
part, every block, on the shipping image: `_c1_rx_off` holds the RX lane
offsets `0, 1, 2, … 7, 128, 129, …` and each `C1_IN_nn_process` reads its
lane with `dm(i0, m0)` at the lane stride straight out of the ring. **Odd
word offsets into the ring are read on every block of every image this tree
has shipped**, and those channels are bit-exact under `goldnode`.

The **SIMD dual-data access is what raises it to 8.** The block kernels open
a `PEYEN` region (`_gsimd_enter`) and read the pool with `dm(i0, 2)`, one
access feeding both processing elements from two consecutive words — which
requires the address to be **even, i.e. 8-byte aligned**. In the S23 pair
both pool bases are even (`_blk_pool` 590640, `_blk_pool1` 590784) and every
slot is therefore even, because `BLOCK` is 16. **They are even by luck, not
by declaration** — the linker was free to place either pool one word along —
and that is a latent build fragility worth its own line in the findings
independent of the net question.

**So the argument was: 8 bytes, set by the SHARC CORE's SIMD dual-data
access.** 40 is a multiple of 8, so `MWN_AUDIO_PAYLOAD_OFF` stays at 40 and
the payload does not move to 48 — the right answer to the question the net
spoke asked, reached through a claim about the core that §2.4 shows is
false.

### 2.3 The sentence the net spoke should act on, and its caveat — RETIRED by §2.4

**This whole subsection describes a consequence of the 8-byte requirement
and the requirement is 4 bytes. It is kept because it is what the net
spoke was told on 2026-09-10 and it must be visibly withdrawn rather than
quietly deleted. The sentence to act on is now §2.4's.**

> Keep `MWN_AUDIO_PAYLOAD_OFF` at 40: the binding DSP-side requirement is
> 8-byte alignment and 40 satisfies it — but the requirement is on the
> ABSOLUTE address of sample 0, so a receiver that wants in-place
> consumption must place the MW-Net header on an 8-byte boundary, and one
> 802.1Q tag inserted by a customer switch shifts the header by 4 bytes and
> breaks that, whereas it never breaks a 4-byte requirement.

Concretely: with the header at frame offset 14, sample 0 is at frame offset
54 and needs the frame placed at `≡ 2 (mod 8)`; with a VLAN tag the header
is at 18, sample 0 at 58, and the frame must be at `≡ 6 (mod 8)`. A
receiver that reserves a fixed 2-byte pad — the usual arrangement — gets one
of those right and the other wrong. **The field offsets are untouched by
this** (the header is located by EtherType scan, exactly as the message
table intends); what is touched is only the ability to read the payload
without copying it.

Moving `MWN_AUDIO_PAYLOAD_OFF` to 48 does **not** fix that, because it
changes the offset and not the base. The two ways to fix it are to declare
the placement requirement on the receiver, or to accept a copy on any frame
that arrives tagged.

### 2.4 THE MEASUREMENT: the pools were moved, and nothing moved with them

§2.2 called the pools' even placement "even by luck, not by declaration"
and filed it as a latent build fragility. It is neither: **the alignment
was never required.**

`DSP4_POOL_PAD` emits N words of `.var` immediately in front of
`_blk_pool`, in the same section and the same object, so an odd N puts the
pool — and every slot in it, since a slot is `base + n × BLOCK` and BLOCK
is even — on an ODD word address. The generator emits it; `bus_accumulators.asm`
carries it; 0 is the byte-for-byte control and the shipping image does not
name it.

Built at `DSP4_POOL_PAD=1` on `shipping.config.s21`, both chips:

| | control | pad arm |
|---|---|---|
| chip 1 `_blk_pool` / `_blk_pool1` | `0x90330` / `0x903C0` — both EVEN | `0x90331` / `0x903C1` — both **ODD** |
| chip 2 `_blk_pool` / `_blk_pool1` | `0x91E74` / `0x91F04` — both EVEN | `0x91E75` / `0x91F05` — both **ODD** |

Every bar, run on the part on the same bench session:

| bar | control | pad arm |
|---|---|---|
| `busgold` bus capture, 256 words | sha256 `4126c00730a31f5f` | sha256 `4126c00730a31f5f` — **identical** |
| `goldnode` (GATE / COMP / TUBE / FDR) | — | **word-for-word identical to the control**, including the COMP arm's pre-existing 0.00518 dB LUT deviation |
| `famverify` D32, 26 families | 21 LIVE, 3 numeric BIT_EXACT | **verdict-for-verdict and value-for-value identical**, the only difference in the whole report being one free-running live METER word |
| golden harness | 59/59 | 59/59 |
| `dsp_validate` | OK, 698 nodes | OK, 698 nodes |

**And the mechanism agrees with the measurement.** SIMD dual-data access
on this core reads *the addressed word and the next one*, which is what
`src/lib/dyn_simd_fx.asm` says in its own header — it places no
requirement on the base. The access class that WOULD require an even
address is the long word, and **this tree contains none: `LW(` appears
zero times in every `.asm` in the source tree.** Nor is there a single
`.align` directive anywhere, which is consistent — nothing has ever needed
one.

**The sentence the net spoke should act on:**

> The DSP block interface requires **4-byte (one 32-bit word) alignment**
> of sample 0, set by the DDE's `MSIZE04`/`XMOD 4` audio rings. Keep
> `MWN_AUDIO_PAYLOAD_OFF` at 40. There is **no 802.1Q hazard**: a VLAN tag
> shifts the header by 4 bytes and a 4-byte requirement survives that, so
> in-place consumption is available on tagged and untagged frames alike,
> and no receiver-side placement rule is needed.

---

## 3. In-place consumption — yes for the read, and on this product the
   question is answered one boundary out

### 3.1 On the DSP product, no packet reaches the DSP

The DSP product's MW-Net endpoint is the **RT1180 option card**, and the DSP
never sees an Ethernet frame, a receive buffer or a byte of MW-Net header.
What crosses the option slot is TDM, generated and consumed by the LOGIC
CPLD (`shared/dsp4-logic/`):

| direction | CPLD port | lines | format | channels | clock role |
|---|---|---|---|--:|---|
| DSP → card | `no[3:0]` | `B_O4..B_O7` | TDM8 | 32 (`NET_OUT_01..32`) | CG3 |
| card → DSP | `ni[3:0]` | muxed onto `A_I0..A_I3` | TDM8 | up to 32 | CG0 |

Both at 48 kHz, both 32 bits per slot, both from the same 49.152 MHz XO as
every other lane on the card. Note that the *shipping* bitstream selects
only lane 3 as NET (`net_sel = 4'b1000` in `dsp4_logic_top.v`, the same on
both product straps), so 8 NET input channels are live today —
`IN_25..IN_32` — against 32 output channels. The other three input lanes are
wired and muxable, not selected.

**So the question "can a DSP node consume samples in place from a network
buffer" has no DSP-side subject on this product.** The alignment,
byte-order and zero-copy properties of the MW-Net payload are the RT1180's
to satisfy on its own eDMA when it deserializes a packet into a TDM
transmitter, and they are not the SHARC's.

### 3.2 The in-place question that does exist, answered on the part

If MW-Net ever did terminate on a SHARC, the mechanism it would need already
exists and runs on every block of the shipping image. `C1_IN_nn_process`
sets `i0` to the active DMA ring base plus the lane's word offset and reads
`dm(i0, m0)` at the lane stride directly into the block pool. **There is no
staging copy anywhere between the DMA ring and the first arithmetic node.**

Three things follow, and the third is the one that would need work:

1. **The stride is already a per-channel runtime constant** (`_c1_rx_stride`,
   looked up rather than compiled in, so the boot-time input patch still
   applies). The MW-Net audio payload is declared **tick-major
   `[tick][chan]`**, which `mwnet-wire-v0-messages.csv` states *is* the
   layout of a TDM32 DMA block; the reader would want stride =
   `chan_count` words and offset = the channel index, which is the
   mechanism unchanged.
2. **Alignment**, per §2: fine at 4 bytes for this scalar read, 8 for a SIMD
   kernel reading the same buffer.
3. **Format is a transform, not a copy, and the claim must say so.** MW-Net
   `fmt` 1 is S32LE, i.e. Q1.31; this graph's arithmetic format is **Q4.28**
   (D5). The existing reader already pays for that — `r2 = ashift r2 by -3`
   — one instruction folded into the same loop as the load, with no second
   buffer. "In place" is therefore true in the sense that matters (no copy,
   no staging buffer, one pass) and false in the sense of "the DSP reads the
   wire word unmodified".

**Answer: in-place = yes, because the node reads the DMA buffer directly
with no staging copy and the payload's tick-major layout is the DMA block
layout — subject to the 8-byte placement of §2.3, and with the Q1.31→Q4.28
shift folded into the load rather than avoided.**

---

## 4. What this does NOT answer

- Whether the RT1180's own eDMA or its TDM transmitter imposes a wider
  alignment than the SHARC's 4 bytes. That is the net spoke's measurement on
  its own part; nothing here constrains it.
- The net spoke's M7-on-EVK latency figures are **not inheritable** by the
  DSP product, and nothing above should be read as validating them.
- ~~Whether the SIMD dual access on this part actually faults or silently
  force-aligns at an odd word address.~~ **ANSWERED 2026-09-10, §2.4: it
  does neither, because it never required an even address.** Both pools
  were moved onto odd word addresses on both chips and every audio bar
  reproduced bit for bit.
