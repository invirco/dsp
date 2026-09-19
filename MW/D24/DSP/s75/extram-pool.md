provenance: AI-drafted 2026-09-19 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S75 — the delay/reverb memory pool, coded for HyperRAM now, running without it

**PW ruling, 2026-09-19 evening:** *"dsp ram is required, but needs to work
without it until dsp board modified — code it in place."*

Desk session, read-only: the unit was not booted, flashed, configured or
powered. Everything below is either read off a datasheet, computed, built, or
proved against a simulated part, and each claim says which.

## 0. Outcome in one paragraph

The pool is in the tree with both backends. Built the way the product ships
(`DSP4_EXTRAM=0`) the two images are **byte for byte S74c's**:
`chip1.ldr 10a413005e0647f5c66476f6a0b4ab60` (452,388 B),
`chip2.ldr e88a7a4302950d088a6c023c949c916e` (307,980 B). Built with the pool
in (`DSP4_EXTRAM=1`) the tree assembles and links clean on both chips —
`52865949b546aa1757c26b6bb73f22ba` (461,052 B) and
`1198f18ec1759b0ff09ae7346a569f75` (309,132 B), neither deployed. The EXTRAM
backend is proved bit-exact against a simulated HyperRAM over 420,404 compared
samples, 9/9 checks. **Added audio latency: zero samples.** Two hardware
questions stand in the way of ever arming it and both are for the hub, not for
this tree: the pin conflict (S75-1) and the part voltage (S75-2).

---

## 1. The design

### 1.1 The one idea

**EXTRAM extends the L2 line; it does not replace it.**

Every delay line keeps the L2 ring it has today — `H` samples, the *head
window*. The external store holds the same history, and a read is served out
of L2 whenever the requested offset is inside the head:

```
    off <  H   ->  L2 head ring         (the instruction sequence that ships)
    off >= H   ->  a 2-block staging buffer, prefetched by MDMA
```

`H` is 960 samples (20 ms) on the channel delays — exactly today's per-channel
allocation. Three things follow, and they are the whole reason for this shape:

1. **Zero added latency.** The dispatch asked for the added latency "in a whole
   number of blocks". It is zero blocks and zero samples. Nothing in the audio
   path ever waits on the bus, because every offset short enough to be waited
   on is served out of L2, and every offset served from the external store is
   at least `H` = 960 samples old — sixty blocks — so its prefetch was issued
   fifty-eight blocks before it is read.
2. **No coherency hazard.** The write-behind for block *n* and the read-ahead
   for block *n+2* are separated by at least `H − 2·BLOCK` samples of history.
   They cannot touch the same words. There is no forwarding case, no "is it in
   the staging buffer yet" test, and no per-sample decision of any kind.
3. **The fallback is not a second implementation.** With no RAM the backend
   word is 0, no offset ever reaches the second branch, and what executes is
   the code that ships — which is why the L2 arm can be proved *byte-identical*
   rather than merely equivalent.

### 1.2 The external layout

The history store is indexed **by block, not by line**:

```
    hist[slot][line][BLOCK]     slot = 0..749, line = 0..31, BLOCK = 16
```

Absolute sample *a* of line *L* lives at `hist[(a/BLOCK) % SLOTS][L][a % BLOCK]`.

That layout is chosen so the **write-behind is a single transfer**: all
`LINES*BLOCK` words a block produces are adjacent, so one 1D MDMA flushes every
line at once. Per-line rings would have needed one transfer per line in each
direction and roughly doubled the arming cost.

The **read-ahead** is one armed transfer per line whose offset reaches the tail.
A `BLOCK`-sample window at an arbitrary offset straddles two slots, so the fetch
is 2D — `XCNT = BLOCK`, `YCNT = 2`, `YMOD` = the slot stride — landing `2*BLOCK`
words in the line's staging buffer, of which the kernel reads a `BLOCK`-long
span starting at a phase that is constant for the whole block. The one case 2D
cannot express is the slot ring wrapping between the two rows; that happens to
one line once every `SLOTS` blocks (once per 250 ms) and is issued as two 1D
transfers instead.

Store size, chip 1: `750 × 32 × 16 × 4 B` = **1,536,000 B (1.46 MB)**. One
64 Mbit (8 MB) part carries that with room for a 1 s spec and for chip 2's
lines when they follow.

### 1.3 The transport, and why it is not the xSPI's own DMA

The xSPI controller (Cadence xSPI/OSPI IP at `0x31070000`) exposes the device
three ways: STIG command registers, its own SDMA, and the **DAC** — a direct
memory-mapped access window. Datasheet **Table 5** maps SPI1/SPI2/xSPI0 memory
at byte address `0x60000000–0x6FFFFFFF`, so once the controller is in
DAC/HyperBus mode the RAM is ordinary system memory to every requester on the
fabric, the MDMA channels included.

So the staging is **plain MDMA** — the same DDE this firmware already drives
for the SPORT rings — and not a second, unfamiliar DMA engine. **MDMA0 (DMA8
src / DMA9 dst, `0x310A7000`) is free**: `dma_config.c` uses DMA0..7 and
DMA10..17 for the SPORTs and nothing else claims an MDMA pair. MDMA1 (DMA18/19)
is free as well if a second channel is ever wanted.

**Register-based arming, not descriptor lists.** `dma_config.c` records at
length that descriptor-list arming has never worked on this part — `ERRC = 3`
the moment CFG is written, for lists this firmware built *and* for a
self-referencing descriptor built word by word in the probe — and that the
SPORT rings are armed in autobuffer flow instead. This module obeys the same
finding: every transfer is programmed straight into the channel registers in
STOP flow. That costs six MMR writes for a 1D transfer and nine for a 2D one,
and buys a path that is known to work on this silicon. (Finding S75-7.)

### 1.4 DMA scheduling, per block

All of it runs in `_pool_block_end`, called from `main.asm` **after** the node
graph and inside the cycle measurement:

1. Poll MDMA0. If it is still busy, count a stall and **skip this block's
   transfers** — never spin inside the block.
2. **Write-behind:** one 1D MDMA, `_pool_wstage[phase]` (`LINES*BLOCK` = 512
   words) → `hist[slot_n]`. The staging is filled by the DLY kernel, one extra
   linear store per sample per line, which is cheaper than a second gather pass
   over 32 wrapping rings.
3. **Read-ahead for block n+2:** for each line with `off >= H`, one 2D MDMA
   (`XCNT = 16`, `YCNT = 2`) from `hist[start_slot][line]` into that line's
   `2*BLOCK` staging half. `start_slot = (slot_n + 2 − q − [ph≠0]) mod SLOTS`
   with `q = off/BLOCK`, `ph = off%BLOCK`.
4. Advance the phase and the slot cursor.

The prefetch is issued at the **end** of block *n* and read by block *n+2*, so
it has the whole of block *n+1* (333.33 µs) to complete, and the half it fills
is the one block *n* has just finished reading — which is why two staging
halves suffice rather than three.

**What degrades, and how.** A stall loses one prefetch, re-issued next block.
Audio is unaffected for the block in hand: its staging was fetched two blocks
ago and is intact. The failure mode of a bus that cannot keep up is therefore a
**rising stall count** — visible at `DIAG_EXTRAM_STALLS`, bounded, and audible
only as a repeated block on a line at full tail depth — and never a stalled
core.

---

## 2. The numbers gate 1 asked for

### 2.1 The xSPI maximum clock — the datasheet **does** state it

The dispatch allowed for the datasheet not stating it. It does.
**ADSP-21560/21561/21564/21568 Rev. A (February 2026), Table 14, "Clock
Operating Conditions":**

| parameter | condition | max |
|---|---|---|
| `fxSPICLKPROG` | with data training, **without** DQS | 125 MHz |
| `fxSPICLKPROG` | with data training, **with** DQS | **166.66 MHz** |

with footnote 5: *"With offline PHY training methodology, the maximum
programmed xSPI clock, which can be used without DQS and with DQS, is 80 MHz
and 125 MHz respectively."* HyperBus drives RWDS as the read strobe, which is
the DQS case, so **the silicon allows 166.66 MHz, or 125 MHz with offline PHY
training**.

**The RAM is the binding limit, not the DSP.** Table 13 gives `VDD_EXT` as
3.13–3.47 V with no 1.8 V option anywhere on the part, so the RAM must be a
3.0 V HyperRAM — and the 3.0 V members of both candidate families are the
**100 MHz** grades. So the design clock is **100 MHz octal DDR = 200 MB/s
raw**, and the reason is the part, not a habit or a fallback. (See S75-2 for
the part-number problem this exposes.)

Effective rate after HyperBus overhead: a transaction costs ~3 clocks of
command/address plus up to 12 of initial latency plus CS setup/hold, call it
20 clocks, against 4 clocks per 32-bit word. A 128-byte read is therefore
`20 + 32×4 = 148`… no: 32 words × 4 clocks = 128 clocks of data on 20 of
overhead, **86.5 % efficient**, ≈ 173 MB/s. A 64-word write is 256 data clocks
on 20, 92.8 %.

### 2.2 Worst-case bandwidth

Worst case as the dispatch framed it — every line at the full 250 ms:

| | words/block | bytes/block |
|---|---|---|
| write-behind, 1 transfer | `32 × 16` = 512 | 2,048 |
| read-ahead, 32 transfers of `2 × 16` | 1,024 | 4,096 |
| **total, chip 1** | **1,536** | **6,144** |

At BLOCK = 16 and 48 kHz a block is 333.33 µs, so **18.4 MB/s**, and in xSPI
clocks at 100 MHz: 2,068 clocks for the write flush and 5,376 for the 32
two-row reads = **7,444 of the 33,333 clocks a block affords = 22.3 % of the
bus**. That figure is not an estimate — it is the worst-block busy fraction the
simulated part reports (`tools/dsp/extram_bitexact.py` check 5, 0.2233), and
the harness fails if it exceeds 0.35, so it cannot drift silently.

Chip 2 is zero today (§5) and would be 21 lines = 1,008 words = 4,032 B/block
= 12.1 MB/s when its lines follow. Both chips on one part each; they do not
share a bus.

**The reverbs contribute nothing, and that is a design decision, not an
omission.** Freeverb's comb and allpass buffers are read and written in the
*same sample* through a feedback path, so no amount of prefetch can stage them
— and they do not need it. Six mono engines are 295 KB of L2 and the reason the
reverb went mono in the first place was the L2 the delay lines were taking.
Moving the delay lines out is what pays the reverb back.

### 2.3 Added latency

**Zero samples.** Stated in full in §1.1. The dispatch's "must be a whole
number of blocks" is satisfied trivially — the whole number is zero — and the
reason is the head window, not a trick.

### 2.4 Cycle cost of the staging

Computed, **not measured** — the part has no RAM to measure against.

| | per block |
|---|---|
| 33 MDMA arms (1 write + 32 reads) × ~8 posted MMR writes | ~264 writes |
| write-staging stores, `32 lines × 16 samples` | 512 |
| per-line planning arithmetic in `_pool_block_end` | ~20 × 32 = 640 |
| **chip 1 total** | **≈ 1,400 cycles/block** |

Against a 327,680-cycle block at 983.04 MHz that is **0.43 % of budget**. Chip
1 currently runs at 98.1 % of budget with zero missed blocks (S12 record), so
it is affordable on paper — and "on paper" is the correct weight to give it
until the bench measures it. The call site is deliberately *inside* the cycle
measurement, so the first driven capacity run on a modded card scores it
honestly rather than excluding it.

### 2.5 Memory, measured off the linker maps

`tools/dsp/dsp_memreport.py`, both arms, both chips:

| pool | chip | L2 arm | EXTRAM arm | delta |
|---|---|---|---|---|
| code (VISA SW) | 1 | 253,238 / 262,144 (96.6 %) | **261,198 (99.6 %), 946 B free** | **+7,960** |
| code (VISA SW) | 2 | 134,000 (51.1 %) | 135,082 (51.5 %) | +1,082 |
| DM data + stack | 1 | 263,780 (70.3 %) | 264,484 (70.5 %) | +704 |
| DM data + stack | 2 | 238,596 (63.6 %) | 238,676 (63.6 %) | +80 |
| delay lines | 1 | 506,880 (24.5 %) | 519,168 (25.0 %) | +12,288 |
| delay lines | 2 | 1,694,112 (81.7 %) | 1,694,112 (81.7 %) | 0 |

The +12,288 B of L2 is exactly the staging and nothing else: write staging
`2 × 32 × 16` = 1,024 words plus read staging `32 × 2 × 32` = 2,048 words,
3,072 words × 4 B = 12,288 B. It is worth noting that the computed figure and
the linker's figure agree to the byte, which is the cheapest check available
that the layout in the code is the layout in the design.

**The +7,960 bytes of chip-1 program memory is the session's real constraint.**
See finding S75-5.

---

## 3. The API

### 3.1 The firmware side

| entry point | file | when |
|---|---|---|
| `_pool_init(r0 = force_l2)` | `src/mem_pool.asm` | once, from `main.asm`, immediately after `_product_config_commit` |
| `_pool_block_end()` | `src/mem_pool.asm` | once per block, from `main.asm`, after the node graph |
| `_extram_init` / `_extram_probe` | `src/extram.asm` | called by `_pool_init` only |
| `_extram_mdma_1d` / `_extram_mdma_2d_src` / `_extram_mdma_busy` | `src/extram.asm` | called by `_pool_block_end` only |

State the rest of the firmware may read:

| symbol | meaning |
|---|---|
| `_pool_backend` | 0 = L2, 1 = EXTRAM. **The one word every generated kernel tests.** |
| `_extram_present` | a device answered the probe and passed the pattern test |
| `_extram_fail` | why not: 0 none, 1 controller init, 2 STIG timeout, 3 ID floated, 4 pattern, 5 forced off |
| `_pool_line_off[LINES]` | each line's offset for this block, published by the kernels |
| `_pool_stalls` | blocks whose staging was skipped |

### 3.2 The generated side

`tools/dsp/dsp_codegen.py::pool_lines()` reads the **graph** for which buffers
are pool lines and in what order; `pool_build_index()` turns that into the line
index before a single node is generated. Nothing derives a line index from a
node's name. Two artefacts follow:

* `chipN/pool_table.asm` — `_pool_head_base[]`, `_pool_head_len[]`,
  `_pool_max_len[]`, with the line list in the header comment.
* `dsp_block.h` — `DSP4_POOL_LINES` (per chip, via `CHIP_ID`) and
  `DSP4_POOL_SLOTS`.

`src/mem_pool.asm` lives in `src/` and **not** `src/lib/` for one reason:
`src/lib` is assembled once with no `-DCHIP_ID`, and `DSP4_POOL_LINES` is per
chip. A pool in `lib/` would compile against chip 2's line count and link into
chip 1 — a mismatch that assembles, links, and is wrong.

### 3.3 The host side

`CFG_EXTRAM` = `0xF005`, written before `CFG_COMMIT`; `DIAG_BUILD_CFG3`
`0xE0EC`; `DIAG_EXTRAM_STAT` `0xE0ED`; `DIAG_EXTRAM_ID0/ID1` `0xE0EE/EF`;
`DIAG_EXTRAM_XFERS` `0xE0F2`; `DIAG_EXTRAM_STALLS` `0xE0F3`. Decoder:
`tools/pi/dsp4_extram.py`. Full definitions: `proposals/CONTRACT-PROPOSAL-S75.md`.

---

## 4. Detection at boot

`_extram_probe` runs **two** tests and the pool's decision hangs on the second.

**(a) The ID registers.** HyperBus register space words 0 and 1 carry the
Manufacturer / Device ID, read by a STIG command with `CA[47]=1` (read),
`CA[46]=1` (register space), `CA[45]=1` (linear). This is the test the dispatch
asked for and it is the one that **identifies** the part — but the ID encoding
differs between the two candidate families, so accepting a specific value would
reject the other vendor's part. What is checked here is only that the bus did
not float: all-ones or all-zeros is no device. The raw words are published at
`DIAG_EXTRAM_ID0/ID1` so the bench can say *which* part is fitted.

**(b) A write / read-back pattern at two widely separated array addresses.**
This is the vendor-independent gate. It also catches what the ID test cannot: a
device that answers register space and has no working array — unconfigured
latency, untrained PHY, a half-soldered data lane. The two addresses are read
back **in the opposite order to the writes**, so a write buffer cannot satisfy
a read-back and prove nothing.

**Every wait is bounded.** `XSPI_STIG_LIMIT` and `XSPI_INIT_LIMIT` are
1,048,576 iterations of a four-instruction poll — ~8 ms at 491.52 MHz, four
orders of magnitude above any legitimate completion, so an expiry is never a
false alarm; it means nothing answered. There is no unbounded spin anywhere in
`extram.asm`, which is the property the whole fallback depends on.

**A product may forbid it outright.** `dsp.extram = 0` reaches `_pool_init` as
`r0 ≠ 0` and the bus is never touched at all — not even probed.

---

## 5. What the RAM buys: the spec the tiering cut

Read off the tree, not off the plan. Today's L2 (linker maps, §2.5):

| | chip 1 | chip 2 |
|---|---|---|
| channel delays, 32 × 960 | 120 KB | — |
| shared long-delay pool, 8 × 12,000 | 375 KB | — |
| aux output delays, 12 × 12,000 | — | 562.5 KB |
| sub / main / monitor delays, 3 × 12,000 | — | 140.6 KB |
| FX echo lines, 6 × 12,000 | — | 281.2 KB |
| Freeverb combs, 6 × 11,024 (**mono**) | — | 258.4 KB |
| Freeverb allpass, 6 × 1,563 (**mono**) | — | 36.6 KB |
| **total** | **495 KB (24.5 %)** | **1,654 KB (81.7 %)** |

### 5.1 The four things the tiering actually cut

1. **250 ms on all 32 channels became 20 ms on all 32 plus eight 250 ms
   slots.** `dsp-def.md` §1d: fixed 250 ms × 32 is 1,536 KB; the tier is
   474 KB. Saving −1,062 KB. **Cost: only eight channels can exceed 20 ms at
   once**, and which eight is a scene-load decision the MCU has to manage.
2. **The reverb became mono.** `dsp_codegen.py`, 2026-09-08:
   `_fx_comb_buf_R` and `_fx_allpass_buf_R` were allocated at full size —
   12,587 words an engine, 75,522 across the six, **295 KB** — and not one
   emitted instruction read or wrote either. Removing them paid for the
   12,000-word echo line. **Cost: six mono reverbs where the spec said six
   stereo Freeverbs.**
3. **The FX echo is clamped to 250 ms where the contract's law says up to
   1,000 ms.** `Fx001DelayTime001`'s table domain is 1..1000 ms = 48,000
   samples; six engines at the top would be 1.15 MB against 364 kB free, so the
   buffer was bounded at 12,000 words and the kernel clamps. **Cost: a host
   asking for 800 ms gets 250.**
4. **The main output delays are one, not four.** `dsp-def.md` budgets
   4 × 250 ms (192 KB); the graph carries one main delay plus sub and monitor.

### 5.2 What S75's arm restores, and what it does not

**Restored now, on a card with the RAM:** item 1's user-visible limit. With the
EXTRAM backend any of the 32 channels can request up to 250 ms **at the same
time** — the tail path serves any offset from 960 to 11,999 samples regardless
of whether the channel holds one of the eight pool slots. The eight-slot tier
becomes redundant rather than removed; deleting `_dly_pool_buf_00..07` and
recovering its 375 KB is a separate, authorised shipping-image change and is
deliberately **not** made here.

**Not restored by this session:** items 2, 3 and 4, all of which live on
chip 2, and all of which need chip 2's delay lines in the pool. That needs
those lines to have **block kernels** first — see S75-8 — and when they do, the
arithmetic is: chip 2's 21 pool lines move 984 KB of ring out of L2, leaving
~670 KB used of 2,048 KB, which pays for stereo reverb (+295 KB) with roughly
1 MB still spare. That is the follow-on, with its own byte-identical gate, and
it is where the reverb's other half comes back from.

---

## 6. The proofs

### 6.1 Gate 3(a) — the L2 arm is byte-identical

Built twice from the committed tree with `./build.sh` at the shipping
configuration:

| | md5 | bytes | HEAD (S74c) |
|---|---|---|---|
| `chip1.ldr` | `10a413005e0647f5c66476f6a0b4ab60` | 452,388 | identical |
| `chip2.ldr` | `e88a7a4302950d088a6c023c949c916e` | 307,980 | identical |

Not "equivalent" — the same bytes. That is what the design in §1.1 was chosen
to make provable, and it is why `DIAG_BUILD_CFG3` is itself gated behind
`DSP4_EXTRAM` (a `.var` in `diag.asm` is a word of DM, and a word of DM moves
every address behind it — see S75-9).

Re-verified after `mem_pool.asm` and `extram.asm` moved from `src/lib/` to
`src/`, because a file moving between link groups is exactly the kind of change
that can shift addresses without changing a line of code.

`./check-sharc-codegen-drift.sh`: **passed** — 734 generated files, 0 differ, 0
missing, 53 hand-written and declared.

### 6.2 The EXTRAM arm builds

`DSP4_EXTRAM=1 ./build.sh`: **0 assembler errors, 0 linker errors**, both
chips. `chip1.ldr 52865949b546aa1757c26b6bb73f22ba` (461,052 B),
`chip2.ldr 1198f18ec1759b0ff09ae7346a569f75` (309,132 B). Neither deployed;
the unit was not touched.

### 6.3 Gate 3(b) — bit-exact against a simulated part

`tools/dsp/extram_model.py` is a host model of both backends plus a HyperRAM
that honours block timing (transfer cost `20 + 4n` xSPI clocks, per-block busy
fraction, overrun assertion). `tools/dsp/extram_bitexact.py` is the harness.
**9/9 pass, 420,404 samples compared:**

| check | result |
|---|---|
| head-range: L2 vs EXTRAM identical at offsets {0,1,15,16,17,100,959} | 0 LSB over 204,800 samples |
| tail-range: EXTRAM vs an infinite-precision reference, offsets {960,961,1000,1024,4799,6000,11999} | 0 LSB over 111,776 samples |
| tail-range: **L2 must NOT match** the reference (it clamps) | 111,377 mismatches — the comparison is real |
| ring-wrap: exact across >2 revolutions of the 750-slot history | 0 LSB over 51,136 samples |
| offset change 960 → 11,999 → 16 → 5,000 | head exact immediately, tail exact from the 3rd block |
| bandwidth, 32 lines at 11,999, 100 MHz | worst-block busy fraction **0.2233** (limit 0.35) |
| negative control: corrupt one RAM word, the tail check must fail | detected |

Two of those checks exist only to stop the harness passing vacuously — the
"L2 must not match" arm and the corrupted-word arm. Without them a harness that
compared something against itself would report the same nine passes.

The model was written independently of the assembly, from a written
specification of the semantics, and two differences of interpretation surfaced
and were resolved: the model issues the two-slot prefetch as two separate reads
where the firmware issues one 2D transfer (bus-equivalent, and the model's
0.2233 is the *conservative* count), and the model applies the two-block arming
transient on any offset change within the tail range rather than only on a
head→tail transition — which is the stricter and safer reading.

### 6.4 Gate 3(c) — the bench check, for the next unit session

**Not run. The unit was read-only.** What to run, in order:

1. **`tools/pi/dsp4_extram.py --expect-rev-c` on the SHIPPING image.** CFG3
   reads 0 and the EXTRAM registers read 0. This proves the new diag addresses
   are inert on the image that ships — a five-second check that costs nothing
   and closes the "did S75 change the shipping image" question from the part's
   own mouth rather than from an md5.
2. **Build `DSP4_EXTRAM=1`, boot it on an UNMODIFIED rev C card, and run
   `--expect-rev-c` again.** The required reading on chip 1 is
   `CFG3 = 0xC4000001`, `STAT = 0x00200030`: 32 lines, backend **L2**,
   present 0, **fail = 3 (ID floated)**. This is the fallback proof on real
   silicon and it is the single most important thing the next unit session can
   do with this work. Two specific wrong answers to watch for:
   * `fail = 0` with `present = 0` means the probe did not run at all.
   * `fail = 4` (pattern) means something answered the ID read on a board with
     no RAM fitted — that is a wiring or bus fault, not an absent part.
3. **Confirm the card still answers its parameter link afterwards.** On an
   unmodified card `_pool_init` moves Port A to the xSPI0 mux function and
   SPI2 — the parameter link — goes with it. It is bounded and the card should
   come back, but this is the step where finding S75-1 becomes real, and it is
   why step 2 must be done with the card in reach of a reset.
4. **Only on a modified card:** check `DIAG_EXTRAM_ID0/ID1` against the fitted
   part's datasheet, then `DIAG_EXTRAM_XFERS` rising and
   `DIAG_EXTRAM_STALLS` flat, then a driven capacity run to turn §2.4's
   computed 1,400 cycles/block into a measured one.
5. **The first thing to distrust on real hardware is the 2D `YMOD`
   convention** (`mem_pool.asm`, the `.pe_line` fetch). It is written as
   `ROW_BYTES − (BLOCK−1)×4` on the reading that `YMOD` is applied *after* the
   last element of a row, which has already taken `XMOD` — and nothing on this
   bench can check it. An off-by-one there fetches a window `BLOCK−1` words
   adrift: audible as a delay that is right to within a third of a millisecond
   and wrong. Verify it with a single known pattern before trusting any audio.

---

## 7. Findings

**S75-1 🔴 OCTAL xSPI0 TAKES THE PARAMETER LINK *AND* THE BOOT PORT, AND D8'S
STATED RESOLUTION DOES NOT WORK.** Datasheet Table 10: `PA_00/01/04/05` are
SPI2 at mux function 0 and xSPI0 at function 1; `PA_06..PA_09` are **SPI0** at
function 0 and xSPI0 at function 2. HyperBus needs all eight data lanes, so
xSPI0 consumes `PA_00..PA_09` (leads 14–27) plus the dedicated `xSPI_RWDS`
(lead 9) — which matches the mod sheet exactly and is now cross-checked against
the 120-lead assignment table. **Both SPI2 and SPI0 die.** Today the Pi's
parameter link *and* the slave-boot port are SPI2 (`dma_config.c`: `PA_00`
MISO, `PA_01` MOSI, `PA_04` CLK, `PA_05` SEL1; `dsp4_busmon.py` agrees at the
connector). D8 says "the Pi RUNTIME param link moves to SPI0/SPI1" — but
**SPI0 *is* xSPI0's D4..D7**. The only SPI that survives an octal xSPI0 on this
part is **SPI1 (`PA_10..PA_15`, function 1)**, and `PA_12` is currently the
diagnostic LED. **Question for the hub:** does the board mod also move the Pi
parameter link to SPI1 (and give up or move the LED), and does boot still
happen on SPI2 before the firmware re-muxes Port A? Without an answer the mod
as drawn takes the control link away the moment the RAM is enabled. Nothing in
this tree can decide it.

**S75-2 🔴 BOTH NAMED PARTS READ AS THE 1.8 V VARIANTS AND THE PROCESSOR HAS NO
1.8 V I/O.** Datasheet Table 13: `VDD_EXT` is 3.13–3.47 V, nominal 3.30, with
no lower option anywhere on the ADSP-21560/61/64/68 — so the RAM must be a
3.0 V HyperRAM, exactly as D8 concluded in August ("3.3 V VDD_EXT only → 1.8 V
octal excluded; 3.0 V octal-xSPI HyperRAM S27KL-class preferred"). The dispatch
names `S27KS0642GABHI020` and `IS66WVH8M8DBLL-100B1LI`. On the vendors' own
family naming the `S27KS` prefix is the 1.8 V Infineon part (`S27KL` is the
3.0 V one) and `IS66WVH` is ISSI's 1.8 V part (`IS67WVH` is the 3.0 V one).
**The processor side of this is datasheet-proven; the part-family half is from
naming convention, because vendor datasheets could not be fetched from this
machine.** Either way the two statements cannot both be right. **Question for
the hub:** confirm the exact orderable part numbers, or confirm that a level
translator is in the mod. Note the consequence for §2.1: the 3.0 V grades are
the 100 MHz ones, so the design clock stays 100 MHz either way.

**S75-3 THE DATASHEET STATES THE xSPI CLOCK CEILING; D8'S "exact 21564 OSPI
clock ceiling" OPEN ITEM CAN CLOSE.** Table 14: 166.66 MHz with DQS, 125 MHz
without, 125/80 with offline PHY training. See §2.1.

**S75-4 THE ADSP-2156x DATASHEET IS NOW IN THE DROPBOX DOC FOLDER.** The
working note carried "datasheet still missing";
`_mx/_temp/adsp-2156x-docs/adsp-21560-21561-21564-21568.pdf` (Rev. A, February
2026, 81 pages) is present and is the source for every datasheet citation
above. It has the clock table, the pin multiplexing tables, the 120-lead
assignment, the supply conditions and the I/O memory map — i.e. most of what
the missing-core-chapter HRM could not answer.

**S75-5 🔴 CHIP 1'S CODE POOL HAS 946 BYTES FREE IN THE EXTRAM ARM.** The pool
costs chip 1 **+7,960 bytes** of program memory (253,238 → 261,198 of 262,144,
96.6 % → 99.6 %). It links, but there is no room behind it: `DSP4_CUE`,
`DSP4_RTA` and `DSP4_TEST_NODES` are all still 0 and all want chip-1 code, and
any two of them plus this will not fit. **Arming the external RAM on chip 1
requires code reclamation first** — the obvious candidates are the dead
float-era `lib/delay.asm` bodies (already gated out of block-kernel builds but
still linked) and the per-sample DLY body. This is not a defect in the pool; it
is the wall that was already there, reached. It is a blocking item for ever
setting `DSP4_EXTRAM=1` in `shipping.config`, and it is cheap to fix.

**S75-6 THE BACKEND DECISION HAD TO MOVE AHEAD OF THE L2 CLAMP, AND DID.**
Found and fixed inside this session. The DLY block kernel clamps the requested
offset into the *active L2 storage* (960 samples on a channel with no pool
slot) before doing anything else. The first cut of the EXTRAM arm took the
head-versus-tail decision *after* that clamp — against a number that can never
exceed the head — so the tail would never have been reached and a host asking
for 200 ms would have silently got 20, on an image that built, linked, ran and
reported EXTRAM in force. It now decides on the offset the host actually wrote
and jumps over the L2 clamp, clamping against the full 12,000-sample spec
instead. The simulated-part harness reproduces the fault if the fix is reverted
(check 2 fails); that is what the harness is for.

**S75-7 THE STAGING ARMS REGISTERS, NOT DESCRIPTOR LISTS, BECAUSE THIS PART
CANNOT DO DESCRIPTOR LISTS.** `dma_config.c` records `ERRC = 3` on every
descriptor-list arm ever tried on this silicon, including a self-referencing
descriptor built word by word in the probe, and the SPORT rings run in
autobuffer flow because of it. The obvious implementation of a per-block
staging queue — a pre-built descriptor chain with two patched fields — is
therefore not available, and `extram.asm` programs the channel registers
directly. Recorded here because the next person to look at the arming cost
will otherwise "improve" it straight back into the known-broken path.

**S75-8 CHIP 2'S DELAY LINES ARE PER-SAMPLE NODES AND CANNOT BE STAGED UNTIL
THEY ARE NOT.** `gen_delay`'s non-pooled branch emits no block kernel, and the
aux/sub/main/monitor delays and the FX echo lines all take that branch (they
have no `pool_slot` parameter). Staging is a per-block operation by
construction. This is why `DSP4_POOL_LINES` is 32 on chip 1 and **0** on
chip 2, and why §5.2's items 2–4 are the follow-on rather than this session.
Chip 2's lines do not need the RAM for *capacity* — they already carry the full
250 ms in L2 — they need it so their L2 can go to the reverb.

**S75-9 `DIAG_BUILD_CFG3` EXISTS, AND IS GATED, AND THE GATE IS A LIMITATION
WITH A DATE ON IT.** `diag.h`'s own note (added with `DSP4_TALK_INVERT` in S72,
reaffirmed S74) says the next flag of that class needs a third word rather than
a seventh narrowing of CFG2's signature. `DSP4_EXTRAM` is that flag and CFG3 is
that word, signature `0xC4`. It is behind `#if DSP4_EXTRAM` **only** because a
`.var` is a word of DM and a word of DM would have cost §6.1's byte-identical
proof. It should become unconditional at the next authorised shipping-image
change. Until then `0xE0EC` reading 0 means "this image has no CFG3, therefore
no external-RAM pool" — less informative than it will be, but not ambiguous.

**S75-13 🔴 TWO DIFFERENT `DIAG_BUILD_CFG3` DESIGNS NOW EXIST IN THIS REPO AND
ONLY ONE CAN SURVIVE.** `tools/dsp/cfg_words.py` has carried an unapplied
design for a third build-config word since S28 gate 3 — signature `0xC3`, every
one of bits 23..0 allocated to a strip cut, the full shared-kernel mask and six
other switches. It was never implemented and nothing in the firmware produces
it. S75 has now implemented a word of that name at `0xE0EC` with signature
`0xC4` and one bit. **Neither layout has a free bit for the other.** They are
at least distinguishable — a decoder reading the wrong one rejects the
signature rather than decoding nonsense, which is the property these words
carry signatures for — and both files now say so at the point of definition.
Which design lands is PW's call. What must not happen is either going in on top
of the other without one: an image answering `0xE0EC` with S28's `0xC3` word,
read by a host built against S75's, would report "the external RAM pool is
compiled in" when what it read was `DSP4_DYN_TABLES`.

**S75-14 `check_shipping_config.sh` CHECKS THE NEW FLAG FROM THE START.** S74's
finding was that this script had never checked `DSP4_TALK_INVERT`, so
`shipping.config` could silently disagree with the bench mirror on it.
`DSP4_EXTRAM` is in the script's `want3` and in `dsp4_buildcfg.SHIPPING3` on
the day it was added. The printed line states plainly that at `DSP4_EXTRAM=0`
the part reads an unmapped `0x00000000` at `0xE0EC` and **not** `0xC4000000`,
so a bench operator is never told to expect a word the image does not carry.

**S75-10 THE 2D `YMOD` CONVENTION IS THE ONE PIECE OF THIS THAT NOTHING ON THIS
BENCH CAN CHECK.** See §6.4 step 5. It is written down at the call site, with
the reasoning, precisely so it is the first thing looked at rather than the
last.

---

## 8. What changed in the tree

| file | what |
|---|---|
| `MW/D32/DSP/SHARC/src/extram.asm` | **new.** xSPI0/HyperBus: pads, controller, PHY, STIG ID probe, pattern test, MDMA arm/poll. All behind `DSP4_EXTRAM`. |
| `MW/D32/DSP/SHARC/src/mem_pool.asm` | **new.** The pool: backend choice, the external layout, the per-block staging. |
| `MW/D32/DSP/SHARC/src/chip{1,2}/pool_table.asm` | **new, generated.** The line registration read off the graph. |
| `tools/dsp/dsp_codegen.py` | `pool_lines()` / `pool_build_index()` / `gen_pool_table()`; the pool geometry in `dsp_block.h`; the EXTRAM arm in the DLY block kernel. |
| `MW/D32/DSP/SHARC/src/main.asm` | `_pool_init` after the config commit; `_pool_block_end` after each chip's graph. |
| `MW/D32/DSP/SHARC/src/diag.{h,asm}` | `DIAG_BUILD_CFG3` and the five runtime words, with their dispatch. |
| `MW/D32/DSP/SHARC/src/product_config.asm` | `CFG_EXTRAM` `0xF005` → `_cfg_extram_off`. |
| `MW/D32/DSP/SHARC/build.sh` | `DSP4_EXTRAM`, default 0. |
| `MW/D32/DSP/SHARC/shipping.config` | `DSP4_EXTRAM=0`, stated rather than implicit. |
| `check-sharc-codegen-drift.sh` | the two new hand-written sources declared. |
| `tools/dsp/extram_model.py`, `tools/dsp/extram_bitexact.py` | **new.** The simulated part and the proof. |
| `tools/pi/dsp4_extram.py` | **new.** The bench decoder. |
| `tools/pi/dsp4_buildcfg.py`, `check_shipping_config.sh` | `SHIPPING3` / `want3`, so `DSP4_EXTRAM` is gated from the day it was added (S75-14). |
| `tools/dsp/cfg_words.py` | the S28 `DIAG_BUILD_CFG3` design block now names the collision (S75-13). |
| `proposals/CONTRACT-PROPOSAL-S75.md` | **new.** `dsp.extram` and the diag words. |

Every generated file in the tree matches the generator (`check-sharc-codegen-drift.sh`
passes). No matrix, no def, no `defs.lock` and no address was touched.
