# DSP4 SPORT/DMA plumbing design (TODO(dsp4-plumbing) execution plan)

Status: designed 2026-07-31 against ADSP-2156x HRM rev 1.0 + CCES
`def21564.h`/`sru21564.h`. Implementation slices at the bottom.
Facts below are header/HRM-verified unless marked PROVISIONAL.

## Ground rules

- All SPORT halves are **clock/FS slaves** (LOGIC generates every BCK/FS).
- sport_id = DAI port index; **half A = RX (I ports), half B = TX (O
  ports)**; SPORT0-3 sit on DAI0, SPORT4-7 on DAI1 — matching the card's
  DAI pin map exactly.
- DMA channel map (HRM Table 27-2 / Table 23-6) — **not contiguous, and
  the two blocks are not adjacent in the MMR map**: SPORT0-3 are
  DMA0-DMA7 (`2n`/`2n+1`) based at 0x31022000, stride 0x80; DMA8/DMA9
  are MDMA0 SRC/DST on a different SCB node; SPORT4-7 are DMA10-DMA17
  based at **0x31023000**, stride 0x80. Extending `2n`/`2n+1` past
  SPORT3 lands on 0x31022400+, which is unpopulated MMR space — the SCB
  access never completes and the core stalls on its next MMR access
  (this was the P2.2 `dma_cfg_init` wedge, found 2026-08-20). SPORT MMRs
  themselves ARE regular: `REG_SPORT0_CTL_A` = 0x31002000, 0x100 per
  SPORT, +0x80 for half B.
- SEC interrupt sources: `INTR_SPORTn_A_DMA` = 37 + 4n, `_B_` = 39 + 4n
  (from ADSP-21564.h).
- The register addresses currently #defined in sport_init.asm and
  spi_handler.asm (0x0800xxxx) are INVENTED placeholders — replace all
  register access with `#include <def21564.h>` symbols.
- **The host link is SPI2, not SPI1** (corrected 2026-08-11). The rev-C
  card wires the Pi to each DSP's SPI2 port (PA_00/01/04/05, SPI_RDY on
  PB_05 with a 10K pulldown), which is the same port `BMODE[2:0]=0b010`
  boots from — boot and runtime share it until D8's rev-D SPI0/SPI1
  remap. `dma_config.c` and both `spi_handler.asm` now use SPI2
  (0x31030000, SEC source 71) and enable RDY flow control with FCPL=1,
  which is what the pulldown means per HRM Figure 40-7.

## Multichannel configuration per half-SPORT

CTL (per half): SPENPRI=1 (only lanes in use), SLEN=31, ICLK=0, IFS=0,
FSR=1, CKRE=1 (LOCKED 2026-07-31 via the slot-map timing conventions:
sample rising / launch falling), OPMODE=0 (standard/multichannel), SPTRAN=1 for TX
halves / 0 for RX halves.

MCTL: MCE=1, WOFFSET=0, MFD=1 (LOCKED via the slot-map timing
conventions in shared/dsp4-logic), WSIZE =
slots-1 (7 for TDM8 lanes, 15 for TDM16 lanes).

**MCPDE (DMA packing)** — the key layout decision (HRM §23 window
examples):
- RX lanes + inter-chip lanes: MCPDE=1 → DMA transfers ONLY CS-selected
  slots, packed. Buffer per lane = packed_count × 32 samples.
- Chip-2 TX output lanes: MCPDE=0 → DMA covers the full window (8
  words/frame), CS selects which slots actually drive; matches the
  frame-indexed gather.

**CS masks are generated, not hardcoded**: the mask must equal the slots
that actually have nodes (e.g. codec return lane = 0x0D — slots 0,2,3;
CODEC_RET_2 has no node). block_io.asm emission must include a per-lane
table {sport, dir, cs_mask, slot_count(packed or window), buf_offset,
stride} that sport_init consumes.

## Lane tables (from dsp.csv today — regenerate whenever it changes)

Chip 1 RX (half A, MCPDE=1, WSIZE=7): s0-s3 CS 0xFF (8 each), s4 CS 0x0D
(3), s5 CS 0xFF (8, D32 sources), s6 CS 0x03 (2), s7 CS 0x20 (1) →
46 packed channels, lane-major.
Chip 1 TX = mix fabric (half B, MCPDE=1, WSIZE=15): s0 CS 0xFFFF (16),
s1 CS 0xFFFF (16), s2 CS 0x001F (5) → 37; s3-s7 not enabled (reserved).
Chip 2 RX = mix fabric (half A): mirror of chip-1 TX.
Chip 2 TX (half B, MCPDE=0, WSIZE=7, 8 words/lane): s0 CS 0xFF, s1 CS
0xFF, s2 CS 0x0F, s3 CS 0x03, s4 CS 0x01; s5-s7 not enabled.

## Buffer layout (lane-major; replaces the single flat buffers)

Each DMA stream is per-lane, so region layout = concatenated lane
buffers: `region[lane_off + sample*lane_stride + idx]`, idx = packed
index (MCPDE=1) or window slot (MCPDE=0). block_io scatter/gather must
emit per-node {word_offset = lane_off + idx, stride = lane_stride}
tables and compute `base + off + sample*stride` (replaces the single
`sample*stride + slot` addressing). Ping/pong = two regions; the four
active-buf base pointers stay as today.

## DMA (DDE) per active lane

Ping-pong via 2-descriptor ring in list flow (FLOW=DSCL, NDSIZE loading
{DSCPTR_NXT, ADDRSTART, CFG, XCNT, XMOD}), descriptors point at each
other; XCNT = lane words/block, XMOD=4 (bytes), MSIZE/PSIZE = 4 bytes,
WNR=1 for RX lanes, INT on descriptor completion for the block-clock
lane only. Alternative if list mode fights us: STOP mode re-armed from
the ISR (simpler, slightly more ISR work).

## Interrupts (SEC)

One lane per chip is the block clock (chip 1: SPORT0_A DMA, source 37;
chip 2: SPORT0_A DMA = mix lane 0). SEC init: SEC_GCTL.EN, SEC_CCTL0.EN,
SEC_SCTL(src).SEN|IEN routed to core; ISR reads SEC_CSID, writes
SEC_END. All lanes share FS so one interrupt per block toggles all four
region base pointers (as today). ivt.asm vector wiring to the SEC core
IRQ id needs checking against the core-interrupt table when
implementing.

## SRU routes (per chip; both chips identical wiring, roles differ)

Data (pin buffer → SPORT or SPORT → pin buffer + PBEN high):
- DAI0: PB01→SPT0_AD0_I, SPT0_BD0_O→PB02, PB03→SPT1_AD0_I,
  SPT1_BD0_O→PB04, PB05→SPT2_AD0_I, SPT2_BD0_O→PB06, PB07→SPT3_AD0_I,
  SPT3_BD0_O→PB08.
- DAI1: PB01→SPT4_AD0_I, SPT4_BD0_O→PB02, PB03→SPT5_AD0_I,
  SPT5_BD0_O→PB04, PB05→SPT6_AD0_I, SPT6_BD0_O→PB06, PB07→SPT7_AD0_I,
  SPT7_BD0_O→PB08.

Clocks (note DAI0/DAI1 pin 19/20 swap per the schematic):
- DAI0 pin 9 = FS0 → SPT0-3_AFS_I; pin 10 = BCK0 → SPT0-3_ACLK_I;
  pin 19 = BCK1 → SPT0-3_BCLK_I; pin 20 = FS1 → SPT0-3_BFS_I.
- DAI1 pin 9 = FS2 → SPT4-7_AFS_I; pin 10 = BCK2 → SPT4-7_ACLK_I;
  pin 19 = FS3 → SPT4-7_BFS_I; pin 20 = BCK3 → SPT4-7_BCLK_I.

PBEN: output-high for pins 2,4,6,8 on both DAIs; input for 1,3,5,7 and
all clock pins. Use `SRU(...)` macros from `sru21564.h`.

## Implementation slices (each keeps the build green)

1. **block_io lane-major rework** (dsp_codegen.py): per-lane tables +
   {off, stride} node addressing; emit lane config table for sport_init;
   resize sport_init buffer constants to the generated totals.
2. **sport_init rewrite**: def21564.h/sru21564.h includes, SRU routing,
   half-SPORT CTL/MCTL/CS from the generated lane table.
3. **DDE descriptors + SEC**: ping-pong rings, block-clock ISR, ivt
   wiring.
4. Bring-up on hardware (needs the rev C card; the CCES licence side is
   done — real 21564 images build since 2026-08-10, and since
   2026-08-11 the build also emits bootable `.ldr` streams with
   `tools/pi/dsp4_boot.py` as the host side).
   CKRE/MFD are LOCKED in the slot-map conventions (2026-07-31) and
   both sides derive from them; verify on the wire regardless.
   Start with `./build.sh blink` (LED only, no plumbing) — if that
   blinks and the full image does not, the fault is in slices 1-3, not
   in boot. Since 2026-08-12 the full image narrows that further by
   itself: LED fault codes say which bring-up step it stopped at, and
   `tools/pi/dsp4_diag.py` reads the state out over SPI. Procedure and
   register map: `diagnostics.md`.

## CM4 stereo send and return — the USB 2-track path (2026-08-23)

The CM4 has a **stereo send and a stereo return** to the DSP. This pair is
the source and sink for **USB 2-track audio play/record** through the CM4:
the Pi plays a 2-track into the console and records a 2-track out of it.

| direction | line | slots | signal | USB role |
|---|---|---|---|---|
| Pi → DSP (send) | `A_I6` (DSPA I6) | 0, 1 | `PI_PCM_L` / `PI_PCM_R` | 2-track **PLAY** sink |
| DSP → Pi (return) | `B_O3` (DSPB O3) | **2, 3** | `PI_RET_L` / `PI_RET_R` | 2-track **REC** source |

Both are TDM8 slots on lines that already exist, and both ends land on the
CM4's single I2S port via `rtl/dsp4_pcm_reframe.v`, which re-frames I2S
↔ TDM8 in both directions. The CM4 is the I2S **slave**; LOGIC masters
`pcm_clk` (3.072 MHz) and `pcm_fs` (48 kHz).

**Status: HUB-ACCEPTED 2026-08-23, PW TO RATIFY.** PW required a stereo
send and return and said "you can choose most convenient slots"; the
specific choice of `B_O3` slots 2/3 is therefore mine and the hub's, not
PW's, and is recorded as provisional until ratified.

**Why B_O3 slots 2/3 for the return**

- `B_O3` is the emptiest TDM8 output lane: only slots 0/1 were allocated
  (`DAC_MAIN_L/R`, both marked provisional, no D24 sink), leaving 2–7 free.
- Slots 2/3 stay clear of `DAC_MAIN` on slots 0/1, so on D32 — where this
  lane becomes the real main DAC — the return does not collide.
- **No PCB change and no new pin.** `B_O3` is an existing DSPB output
  already routed to LOGIC as `dac_main`; LOGIC taps it internally and
  drives `pcm_din`, an existing net to CM4 GPIO20. Nothing is added to the
  rev-D mod list for this.
- Slots 4–7 on the lane remain spare.

**Scope note.** This is a 48 kHz DSP4 feature. Per the D7 decision there is
no onboard recording or USB UAC audio on the 96 kHz products, so this path
does not carry forward to those.

**Cost, measured.** Adding the return to the shipping CPLD build takes it
from 156 to **312 / 1270 LE (25%)** and Fmax from 70.21 to **66.18 MHz** —
still 35% margin over the 49.152 MHz requirement on the 5M1270Z. On the
smaller 5M570Z the same design is **312 / 570 LE (55%) and FAILS timing at
−0.198 ns slack**, which it met (+0.842 ns) before the return was added.

**Still open — what the return carries.** The slots are allocated and the
CPLD de-frames them, but no node writes them yet, so the return is
currently silent. Deciding what feeds `PI_RET_L/R` is a matrix/definition
question: a dedicated stereo bus (independently routable, like an aux
send — recommended, since a USB recording usually wants its own mix) or a
copy of the main mix. That needs node definitions from the mx26 matrix.

### Bluetooth play from the CM4 — cannot have its own slots, and why

**TDM8 on the CM4 PCM pins IS supported** — measured, not assumed. The card
probes cleanly with `dai-tdm-slot-num = <8>`, `dai-tdm-slot-width = <32>`
(a 256-bit frame) and explicit two-bit slot masks, with zero ASoC errors.

**But TDM8 does not buy more channels.** `bcm2835-i2s` is hard-limited to
two, in two independent places:

```c
/* The driver is limited to 2-channel setups.
   Check that exactly 2 bits are set in the masks. */
if (hweight_long(rx_mask) != 2 || hweight_long(tx_mask) != 2)
        return -EINVAL;
```

plus `channels_min = channels_max = 2` in the DAI driver. Confirmed on the
running card: an 8-slot frame still reports `CHANNELS: 2`. TDM8 lets the Pi
choose **which two slots** it occupies in a longer frame; it never gives it
more than two.

(An earlier attempt at `slots = 4` failed with `-EINVAL` at
`snd_soc_dai_set_tdm_slot()`. That was **not** because four slots are
illegal — it was the default mask having four bits set. Worth recording so
nobody re-derives the wrong limit from that symptom.)

**Consequence.** The CM4's two channels each way are the entire audio
budget of that port, and both directions are already committed to the USB
2-track path. **Bluetooth cannot be assigned its own DSP input pair.**

| option | cost | console behaviour |
|---|---|---|
| **BT shares the stereo send**, mixed on the CM4 (PipeWire/Pulse) | none — no slot, no hardware | DSP sees one "CM4 stereo in"; USB vs BT chosen on the Pi |
| BT gets independent console control | second physical stereo link; the CM4 has only one PCM block, so a USB audio interface or equivalent | separate faders/routing for USB and BT |

The first is recommended unless BT genuinely needs its own fader and
routing on the surface, in which case it is a rev-D hardware question and
not a slot assignment.

**Aside worth keeping.** Because TDM8 works, the Pi could sit *directly* in
the DSP's native TDM8 frame at mask-selected slots, instead of LOGIC
re-framing 2-slot I2S ↔ TDM8 in `dsp4_pcm_reframe.v`. The clkgen already
produces TDM8 BCK/FS. That is a genuine simplification available for rev-D
— not required, and not done here.

### TDM8 on the CM4/DSP interface — 8 slots, but only 2 channels. And how to get 8 anyway.

**Answer: TDM8 gives the CM4 eight SLOTS but only ONE bidirectional stereo
pair of DATA.** Three independent sources agree, so this is settled:

1. **Broadcom peripherals datasheet, §8 PCM/Audio:** *"Frames can contain 1
   or 2 audio/data channels in each direction. Each channel can be between
   8 and 32 bits wide and can be positioned anywhere within the frame as
   long as the two channels don't overlap."*
2. **`bcm2835_i2s_hw_params()` never calls `params_channels()`.** It writes
   `RXC_A`/`TXC_A` with `CH1_POS`/`CH2_POS` only. Tell it eight channels
   and it sets `FLEN = 256` — a TDM8-shaped frame — then still places data
   in exactly two slots. The other six are neither driven nor sampled.
3. **Measured on the bench:** an 8-slot frame with 32-bit slots reports
   `CHANNELS: 2`.

So `dai-tdm-slot-num = <8>` buys slot *placement* — the Pi can sit on any
two slots of a TDM8 frame — not slot *count*.

#### But 8 channels of audio ARE reachable — the limit is channels per frame, not bandwidth

**Route A — 2 channels at 192 kHz. Recommended.** The PCM block moves
2 × 32 bits per frame; run the frame at 4× and that is
`2 × 32 × 192 kHz = 12.288 MHz` — **the same bit rate as TDM8 at 48 kHz**.
LOGIC gives the Pi a 64-clock frame with a 192 kHz sync and re-frames into
the DSP's 48 kHz TDM8, which is what `dsp4_pcm_reframe.v` already does, now
with a 4× frame sync. The Pi interleaves eight logical 48 kHz channels into
the 192 kHz stereo stream in software.

- **No kernel module.** This is the big advantage over the alternatives.
- **Measured:** the card accepts `-c 2 -r 192000` (`RATE: [8000 768000]`).
- **Gives:** 8 × 48 kHz channels each way, full 32-bit.
- **Costs:** a de-interleave step on the Pi, and a 192 kHz frame sync for
  the Pi in the CPLD. `dsp4_clkgen.v` already generates the 12.288 MHz.

**Route B — 16-bit frame-packed.** `FTXP`/`FRXP` pack two channels per
32-bit word when the data is ≤16 bits. Four channels each way, 16-bit only.
A real option but a quality compromise on a mix path; not recommended.

**Route C — an Octo-style machine driver.** `audioinjector-octo-soundcard.c`
raises `channels_max` to 8 at stream start and that card genuinely runs 8
channels. But `hw_params` still only programs CH1/CH2, so **the mechanism
is not explained by the code read so far** — recorded as an open question,
not a plan. Worth investigating only if Route A fails.

#### PROVEN ON HARDWARE 2026-08-23 — 8 of 8 channels

Route A measured end to end. The `DSP4_PATTERN` firmware puts a word
naming its own position in every TDM8 slot; the evaluation bitstream taps
DSPB lane 0, whose eight slots are all driven; the CM4 captured at
192 kHz stereo:

    0x5A5A0000 .. 0x5A5A0007   96000 words each, 12.5% each
    distinct pattern SLOTS seen: [0, 1, 2, 3, 4, 5, 6, 7]
    RESULT: 8 of 8 slots reached the Pi

Exactly one eighth per slot, so nothing is dropped or duplicated. At
48 kHz this capture could only ever have shown two of the eight — that is
what makes it a proof rather than a plausibility check.

Artefacts: `dsp4_logic_loopback.e1530dc70431` (PI_TDM8 evaluation),
firmware `DSP4_PATTERN=1 DSP4_BLOCK_MASK=0`.

#### DUPLEX PROVEN 2026-08-23 — both directions, simultaneously

`aplay` and `arecord` running together, per-word counter stimulus so every
word carries its own index:

    counter range 1..192000 over 192000 words
    consecutive +1 steps: 191999/191999 = 100.00%
    aplay stderr: (none)   arecord stderr: (none)

Every one of 192,000 words arrived in order with no gap, repeat or
reorder. Because each run of eight consecutive words is one 48 kHz frame
across slots 0-7, a clean climb proves **all eight slots in both
directions at once** — de-framing inbound and re-framing outbound — and
proves them bit-exact on all 32 bits.

This is the Pi↔LOGIC loop (`PI_SELFTEST`), which is the part that was
unproven; the DSP→Pi direction was measured separately at 8 of 8 slots.

Two things worth recording from getting there:

- The first duplex run read 50% and looked like every value duplicated. It
  was not: the raw words incremented by `0x80` where the stimulus
  incremented by `0x100` — the capture was the stimulus **shifted right
  one bit**, and a `>>8` decode disguised that as repeats. `CAP_EXTRA_DELAY`
  compensates the *DSP* transmitter's framing; in the self-test the words
  never cross the DSP, so applying it shifted the result. Now conditional.
- **The earlier 48 kHz duplex scrambling does not reproduce here.** Same
  two-dai-link overlay, both streams running, 100% clean. So the duplex
  fault previously blamed on the overlay is not reproducible in this
  configuration, and the planned `google,voicehat` single-link change may
  be unnecessary. It should not be made on the strength of the old
  evidence alone.

#### The CM4 side needs NO device-tree change

Worth stating plainly because it is the cheapest part of the answer: Route
A runs the Pi at **2 channels, 192 kHz** — still two channels, just a
higher rate. `dsp4-pcm-slave.dts` is unchanged, the card is unchanged, and
`RATE: [8000 768000]` already covers it. Every bit of the eight-channel
work is in the CPLD.

#### Why LOGIC bridges it, and why the CM4 and DSP cannot just talk directly

**It is not codecing.** No sample-format conversion happens — the 32-bit
words pass through untouched, as the bit-exact result shows. What LOGIC
does is *frame regrouping*: it gathers four consecutive 2-channel Pi
frames into one 8-slot DSP frame, and splits the other way.

**The two devices want structurally different frames, and neither can
adopt the other's:**

- The CM4 cannot adopt the DSP's. Its PCM block places **two channels per
  frame** (Broadcom §8; `bcm2835_i2s_hw_params` only ever writes
  `CH1_POS`/`CH2_POS`). Put it on the DSP's 8-slot 48 kHz frame and it
  occupies two slots — measured, `CHANNELS: 2`. Eight channels *require*
  four Pi frames per DSP frame.
- The DSP could in principle adopt the CM4's — a SPORT can run 2 slots at
  192 kHz — but then that lane's framing differs from every other lane in
  the system (all TDM8/48 kHz), and the 4:1 regrouping moves into DSP
  software. The DSP is currently **6.6× over its per-block cycle budget**
  (`dsp4-cycle-budget.md`), so spending core cycles to save CPLD registers
  is the wrong trade today.

So something has to bridge, and LOGIC is the cheapest place: it already
masters every clock in the system and the work is pure registers.

**Cost, measured:** the 8-channel re-framing takes the CPLD from 312 to
**738 / 1270 LE (58%)**, Fmax 62.18 MHz against the 49.152 MHz
requirement. That is ~426 LE for 8×32 capture plus 8×32 playback registers
and their muxes.

**Part consequence:** 738 LE **cannot fit the 5M570Z at all** (570 LE).
If the 8-channel CM4 link is adopted, the 5M1270Z is mandatory — which
reinforces, on a second independent ground, the timing failure already
recorded for the 570Z.

#### What this means for the ask


USB 2-track + Bluetooth + margin needs 4–6 channels; Route A supplies 8
with no kernel work. The Pi's wire is deliberately *not* the DSP's TDM8
frame — LOGIC bridges the two, as it already does today.

