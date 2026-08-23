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
