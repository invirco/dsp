provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S118 — the chip-1 → chip-2 MAIN receive: the path traced, the state hunted, and the gate that will catch it next time

Hub dispatch `tasks.md` 2026-09-26 14:22Z. Bench: MW-D24-2 as S117 handed it
back. Report for finding S115-2 (`_buf_C2_RECV_MAIN_L` pinned at Q4.28
saturation while chip 1 sent silence) and its S117-3 consequence (a later RUN
ALL pass cannot clear it and carries a fictional acoustic verdict).

**The one-line outcome.** The path is traced end to end and the desk work
RULES OUT the whole family of explanations that were on the table — the fault
cannot be a slot rotation inside the fabric, and it cannot be a lost Q-format
conversion on the link, because the link has no conversion in it and every
signal on it was silent. The state did NOT recur in this session and was not
reproducible by any of the five deliberate perturbations tried, each of which
is reported with its measurement. What is delivered whatever the cause is a
**0.7-second gate that compares the two ends of the fabric** — `IC1`, built on
a new `dsp4_icrecv.py` — wired into `ensure_pair()` so that a press which
finds the unit in this state **boots the pair and says so**, which is the
S117-3 structural fix at the cheapest correct price. Every arm of it (PASS,
FAIL on each of its two rules, NO DATA on a dead pair, and the forced boot)
is proven on the part, not asserted.

---

## S1. The path, on the desk

### S1.1 What the fabric physically is

`shared/dsp4-logic/tdm-lines.csv`: three TDM16 lines, `MIX_0`/`MIX_1`/`MIX_2`,
DSPA `O0..O2` → DSPB `I0..I2`, clocked `CG1`→`CG0`. The LOGIC CPLD masters
every clock and every frame sync; **nothing on the card feeds chip 2's
receive except chip 1's transmit**, and no line in the table routes chip 2's
own output back to chip 2. A feedback loop through the CPLD — the one
mechanism that would explain a self-sustaining saturation with no source —
does not exist in the shipping bitstream.

### S1.2 The five stages, named

| # | stage | code |
|---|---|---|
| 1 | chip 1's bus block | `_buf_C1_BUS_MAIN_L[16]`, written by the MAIN bus accumulator |
| 2 | chip 1 puts it on the wire | `_gather_chip1`, `chip1/block_io.asm:980` — reads `_c1_ic_tx_ptrs[i] + sample`, writes `_ic_tx_active_buf + off + sample*stride` |
| 3 | the DDE clocks it across | `dma_config.c` `arm_region()`, row = one block, `c1_ic_lanes` / `c2_ic_lanes` |
| 4 | chip 2 lifts it out | `_scatter_chip2`, `chip2/block_io.asm:482` — reads `_ic_rx_active_buf + off + sample*stride`, writes `_rx_ic_slot_C2_RECV_MAIN_L[sample]` |
| 5 | the node copies it | `C2_RECV_MAIN_L.asm` — `_rx_ic_slot_…` → `_blk_C2_RECV_MAIN_L`, read by `C2_MIX_MAIN_L`'s kernel |

Under `DSP4_BLOCK_KERNELS` the `*_SEND` node bodies are empty
(`C1_BUS_MAIN_L_SEND.asm`, review finding D25): the gather's pointer table
points straight at `_buf_C1_BUS_MAIN_L`, so stage 1 and stage 2 read the same
words and there is no staging copy between them to go stale.

### S1.3 THE LINK HAS NO GAIN AND NO CONVERSION IN IT

This is the finding the whole desk pass turns on, and it is worth stating
plainly because two of the dispatch's candidate mechanisms die on it.

`_scatter_chip1` (`chip1/block_io.asm:943`) converts the CONVERTER lanes
`Q1.31 -> Q4.28` with `ashift by -3`, and `_gather_chip2`
(`chip2/block_io.asm:529`) converts back `Q4.28 -> Q1.31` with saturation on
the way to the DACs. **Neither the inter-chip gather nor the inter-chip
scatter converts anything**: `_gather_chip1` writes the Q4.28 word straight
into the DMA half and `_scatter_chip2` reads it straight out. The fabric is
Q4.28 end to end.

So a *missing* shift cannot be the fault — there is no shift on this path to
lose. And the ×8 that `+18.06 dBFS` invites (8.0 in Q4.28 is exactly the
`>> 3` between the two formats, and the observed word `0x7FFFFEE0` is
`0x0FFFFFDC << 3`, i.e. a 0 dBFS Q4.28 word shifted into Q1.31 territory)
cannot be produced by this code path reading the region it is pointed at.
That arithmetic coincidence is the strongest single clue in S115-2's numbers,
and what it points at is **memory outside the IC RX region being read as if it
were inside it** — see S2.

### S1.4 What survives a config commit and what does not

`dsp4_config.py` writes `0xF000..0xF010` and commits. It does not touch a DMA
descriptor, a SPORT register, a buffer pointer or a buffer. The state that a
commit cannot clear and a boot can is therefore, exhaustively:

* the DDE's ring position and its descriptors (`arm_region`, re-armed only at
  boot);
* the SPORT framing and `MCTL.MFD` (`sport_config.c`, set only at boot);
* the four ping/pong pointer words `_rx_ping_w` / `_rx_pong_w` /
  `_ic_rx_active_buf` / `_rx_pend_buf` (`sport_init.asm:162`, set only by
  `_set_rx_bufs` at boot; thereafter toggled between those two values by
  `_sport_dma_work`, `sport_init.asm:320`, which is self-correcting —
  it compares against `_rx_ping_w` and lands on ping or pong, so it cannot
  drift to a third value on its own);
* the CONTENTS of `c2_ic_buf_ping[2 * 656]` (`chip2/lane_config.c:50-52`),
  which a boot zero-initialises (the LDF's `-NoFillBlock` note in
  `dma_config.c` — zero-initialised bytes really are clocked in) and nothing
  else ever writes;
* the L2 delay lines, cleared by `l2_clear()` at boot only.

### S1.5 The DM map, and why it matters

Read off the part (`s118_probe.py`), chip 2:

```
_rx_ping_w = 0xB4770   _rx_pong_w = 0xB4A00   (+656 words, = c2_ic_region_words)
_tx_ping_w = 0xB4C90   _tx_pong_w = 0xB4F10   (+640 words, = c2_tx_region_words)
```

**The four DMA halves are contiguous, and the two TX halves sit immediately
above the two IC RX halves.** The TX halves hold `_gather_chip2`'s output:
Q1.31 words, saturated at `0x7FFFFFFF` by the conversion at
`chip2/block_io.asm:529`. A read that strays out of the IC RX region by one
region lands in Q1.31 audio and reports it as Q4.28 — **×8, saturating,
sustained, chip 1 silent, cleared by a boot and not by a commit**. That is
S115-2's signature, arrived at from the memory map rather than from the
symptom. It is hypothesis H1 below. Nothing in the generated tables can reach
there — the largest address the scatter can form is `off 520 + 15*9 = 655`,
inside 656 — so H1 needs `_ic_rx_active_buf` itself to be wrong, and the
toggle that maintains it cannot make it wrong by itself.

---

## S2. Every mechanism that could put a constant near-full-scale word in
## chip 2's MAIN receive — ranked, with the experiment that decides each

The observations any candidate must satisfy: `_buf_C2_RECV_MAIN_L` peak
`+18.06 dBFS` with words at `0x7FFFFEE0`; `_buf_C2_MIX_MAIN_L` 1.3 dB HIGHER;
`_buf_C2_GRP_COMP_01` at −12 dBFS (so chip 2's group path was carrying
something too); `_buf_C1_BUS_MAIN_L` at −117.8 dBFS; every `MainOn` 0; the
chain SAFE; a commit does not clear it; a boot does.

**H1 — the scatter's base pointer is outside the IC RX region, and what it
reads is chip 2's own Q1.31 TX half.** Fits every observation including the
exact ×8 and the near-`0x7FFFFFFF` word, fits "several chip-2 paths hot at
different levels", fits commit-vs-boot exactly. Needs a mechanism that
corrupts one DM word (`_ic_rx_active_buf`, 0xB4726, in a cluster of eight
pointer words at 0xB4724-0xB472D) — a stray DAG write, a delay-line index, or
the ramp engine. *Decided by:* reading `_ic_rx_active_buf`,
`_rx_ping_w`, `_rx_pong_w` and `_rx_pend_buf` while the state is present.
`s118_probe.py` prints all four; if the active pointer is not one of the two
half addresses, H1 is the answer and the remaining question is who wrote it.

**H2 — the IC RX DDE has stopped and the buffer is frozen with old contents.**
Fits commit-vs-boot and "sustained". Does NOT explain saturation: nothing chip
1 sends reaches ±8.0, so a frozen half can only replay something quieter. Also
testable against the block clock: chip 2's block interrupt IS the mix-fabric
lane 0 DMA (`dma_config.c:13`), so a stopped IC RX DDE stops `FRAME_COUNT` and
the whole graph with it — and the meters were updating. *Decided by:*
`FRAME_COUNT` advancing on chip 2 while the state is present (the gate reads
it every run). **Largely ruled out already** by that argument.

**H3 — a slot rotation: chip 2's ring is offset by d words against chip 1's
frame, so `MAIN_L` reads a different fabric slot.** This is the dispatch's own
leading candidate and the desk work DEMOTES it hard: every one of the 41
fabric slots carries a chip-1 bus or forwarded input, and with chip 1's graph
quiet they are all quiet. A rotation can only substitute one silence for
another. It becomes a live candidate only if some OTHER chip-1 slot was hot at
the time — which S115 did not measure, because it read `_buf_C1_BUS_MAIN_L`
alone. *Decided by:* the full-fabric survey (`s118_probe.py --survey`), which
prints all 41 slots at both ends side by side; a rotation shows as the same
magnitude appearing under the wrong name. **This session added that instrument
precisely because S115 could not answer the question.**

**H4 — a framing/`MFD` slip, so the receive samples on the wrong edge or the
wrong bit boundary.** Same objection as H3 with the same force: a bit slip on
a stream of zeros is still zeros. Would additionally have to survive a commit,
which it can (MFD is boot-only). *Decided by:* the survey plus the raw words —
a one-bit slip shows as every slot's word doubled or halved against chip 1's.

**H5 — the reading was an artefact of WHERE S115 read.** Under block kernels
`_buf_C2_RECV_MAIN_L` is a SCALAR staging word, not a block (the node file
says so in as many words); the 16 words S115 read from it span the scalar,
three words of padding and the NEXT node's `_rx_ic_slot`. That does not
dissolve the finding — the words it caught are still fabric-delivered MAIN_R
data — but it means the +18.06 dBFS peak may belong to MAIN_R rather than
MAIN_L. *Decided by:* reading `_blk_C2_RECV_MAIN_L`, which is the real block.
**This session's tools read `_blk_`, not `_buf_`, for exactly this reason.**

**H6 — a positive-feedback loop somewhere in chip 2 that latches at
saturation.** Would explain "needs a kick, then stays", "not reproducible on
demand", and commit-vs-boot (a boot zeroes the buffers and the delay lines).
It cannot write `_rx_ic_slot_C2_RECV_MAIN_L`, which is a pure copy of the DMA
half, so it can only be the answer in combination with H1. *Decided by:*
driving the bus with a tone and removing it — **done this session, negative**
(S3.1).

---

## S3. Reproduction: five deliberate attempts, all negative, each measured

Every attempt ended with the same two instruments: `dsp4_icrecv.py` (the two
ends of MAIN compared) and `s118_probe.py --survey` (all 41 slots at both
ends). The unit was found with the pair alive since S117's 13:33 boot.

**As found, 15:25 BST** — every stage of the chain exactly zero: chip 1's
`_buf_C1_BUS_MAIN_L`, both chip-2 DMA halves at the MAIN offsets,
`_rx_ic_slot_C2_RECV_MAIN_L`, `_blk_C2_RECV_MAIN_L` and `_buf_C2_MIX_MAIN_L`
all `0/16` non-zero; `MainL001Mtr001` and `MainR001Mtr001` read `0.000000`
three times over. `_ic_rx_active_buf` = `_rx_ping_w`, `_rx_pend_buf` =
`_rx_pong_w` — the correct one-half-behind phase. The state was NOT present.

**S3.1 — a tone on, then off (H6, the latch test).** `dsp4_s49_osc.py` at
997 Hz, −6 dBFS into strip 5, strip 5 open on MAIN at unity, monitor bus
written to 0 so nothing was audible. Chip 1 send and chip 2 receive tracked to
**0.03-0.08 dB** through all five stages (−21.7 dBFS at each). The oscillator
ramped off: both ends fell to −114 to −119 dBFS together. **No latch.** A
positive-feedback loop on this bus, if one exists, was not armed by a −6 dBFS
kick.

**S3.2 — config commits on a running pair.** `dsp4_config.py --chip 2` then
`--chip 1` with audio flowing; a `CONFIG_COMMIT` restarts block processing, so
this is the cheapest way to re-arm one chip against a running other one. The
link came back aligned and quiet. (The commit also desynced the parameter
link, which is the known first-pass behaviour, and the following read had to
re-phase.) **Negative.**

**S3.3 — the two chips booted 10 seconds apart.** `!RST_D` resets BOTH parts
together — there is no per-chip reset (`dsp4_boot.py:34-35`) — so the
staggered case is: pulse reset, stream and configure chip 1 only, let it
transmit for 10 s into a chip 2 that is not there, then stream and configure
chip 2 while chip 1 is already running. Both ends aligned slot for slot
afterwards, MAIN within 7.6 dB at −104 dBFS (dither). **Negative, and
informative:** the frame sync is CPLD-mastered and the DDE arms on a row
boundary, so a large boot-order skew does not offset the ring.

**S3.4 — a CM4 reboot with the pair left running.** The literal condition in
S115's history. `systemctl reboot`; the pair kept running through it
(`FRAME_COUNT` continued to climb). Two pin traps had to be cleared first and
both are already known: GPIO27 (`CS_M`) came back `ip pd | lo`, which gates
the U2 buffer onto MISO and makes the link unphaseable, and GPIO6/GPIO24 came
back in ALT, so both chip selects sat asserted and the link answered as
"CHIP 3". With `7,9,10,11,22,23,25 a0`, `6,24 op dh`, `27 op dh` restored,
**the fabric was still a wire** — MAIN within 1.2-1.9 dB at −100 dBFS.
**Negative.**

**S3.5 — a full automatic pass, then three later passes that do NOT boot.**
The run that preceded both occurrences, and then the exact S117-3 condition.
One `--section A,B,C` (51 rows, 34 PASS / 2 FAIL / 15 NO DATA; the two FAILs
are NW2/NW3, the known network rows), with `IC1` now inside it:
`IC1 PASS`, and **`AL1 PASS base -60.2 tone -35.0 SNR 25.2 dB THD -31.8 dB
2.58 %`** — a healthy acoustic loop, i.e. the opposite of S117's reading.
Then **five** further `--section C --only AL1` presses, every one of them with
`ensure_pair end (booted=False)` — the pair carried across all of them with no
reset, which is precisely how S117 met the fault — and every one of them
`AL1 PASS` (SNR 12.9 / 27.0 / 33.1 / 29.3 / 30.5 dB) with `IC1 PASS` and both
ends at exact digital zero between presses. **Negative.** Logs:
`s118/logs/s118d.log`, `s118/logs/s118d-gate1.log`.

**The bounded effort is spent, and the honest statement is this:** the state
was not present on the unit this session and did not appear under a tone, a
commit, a staggered boot, a host reboot or six self-test passes. No root cause
is claimed. What S118 leaves behind instead is an instrument that will answer
the question in one 0.7-second read the next time it happens, and a guard that
stops a run being scored in that state.

---

## S4. What is delivered: `IC1`, and the rule that a pass cannot skip

### S4.1 The reading is a COMPARISON, not a threshold

The dispatch asked for "MAIN receive at digital silence with every `MainOn` 0
— a few reads, no audio". Built instead, and deliberately, is the strictly
stronger question that needs no setup at all:

> what chip 2 RECEIVES on MAIN L/R == what chip 1 SENDS on MAIN L/R

The fabric has no gain, no conversion and no state in it (S1.3), so that
invariant is true at digital silence, true under a tone and true with the
rails up. A "MAIN must be quiet" rule would have to own a setup — close every
strip, put them back afterwards — and would still be wrong the moment a press
legitimately opens one. **This row writes nothing, asserts nothing, and has
nothing to put back.**

`tools/pi/dsp4_icrecv.py` reads `_buf_C1_BUS_MAIN_L` and
`_blk_C2_RECV_MAIN_L` (and the R pair), 16 words each, twice, and calls a
fault only when both read sets agree — a peek walk spans ~15 audio blocks
(S115), so a single disagreement between two ends read at different instants
is not evidence. The limits:

| rule | value | why |
|---|---|---|
| `--gain-tol` | chip 2 no more than **+12 dB** over chip 1 | the healthy part measured **0.03-0.08 dB** under a tone and 1.2-1.9 dB in the dither; the fault was a **133 dB** step |
| `--floor` | only applied above **−40 dBFS** | below that both ends are in the dither and a dB difference means nothing; the fault was +15 to +18 dBFS |
| `--ceiling` | never above **0 dBFS** | a main mix bus over full scale is a fault whatever chip 1 is doing |

**Cost: 0.706 s**, timed on the part.

### S4.2 The guard: `ensure_pair()` now asks whether the pair is WELL, not just alive

This is the S117-3 decision the dispatch asked to be taken here, and the
cheapest correct place for it turned out not to be RUN ALL at all.

`link_alive()` asks `MAGIC` and `BOOT_STAGE`. A pair whose MAIN receive is
pinned at saturation answers both perfectly, which is exactly why S117's
second pass did not boot and carried a NO SOUND verdict that a reset+boot
cleared on the spot. `ensure_pair()` now asks the second half of the question
— **is the fabric still a wire** — and a `no` is a reason to boot, like a dead
link. Nothing in `d24_runall.py` changed, no catalog changed, and the cost
profile is exactly the one the dispatch asked for: **0.7 s when the answer is
yes, and the 40-second boot only when the state is actually there.**

An unreadable gate returns `None`, not `False`: it can neither force a boot on
a pair that is fine nor bless one that is not.

### S4.3 A forced boot is still a FAIL

A boot repairs the unit before `IC1` gets to read it, so without care the
guard would turn a real defect into a clean report. `Rig.ic_forced_boot`
carries the as-found evidence forward and `t_ic1` reports **FAIL** — "the
fabric was NOT A WIRE when this run found the unit; the run booted the pair
and it reads clean now" — with both readings in the evidence.

### S4.4 Every arm proven on the part

| arm | how it was proven | result |
|---|---|---|
| PASS | the unit as it stands | `IC1 PASS MAIN_L c1 −21.7 → c2 −21.7 dBFS` |
| FAIL, ceiling rule | `--ceiling -30` against a live −21.7 dBFS tone | `IC1 FAIL … the fabric is not a wire (S115-2)` |
| FAIL, comparison rule | `--gain-tol -1 --floor -60` against a live +0.03 dB delta | `IC1 FAIL …` |
| NO DATA | `!RST_D` pulsed, pair held down | `IC1 NO DATA the pair did not answer: SPI_RDY never asserted` |
| the forced boot | `--ic1-ceiling -110` through the runner | `ensure_pair end (booted=True)`, then `IC1 FAIL the fabric was NOT A WIRE when this run found the unit` |

The limits are moved onto a healthy part's own reading rather than a fault
being faked, so what is proven is the decision path on real data.
`--ic1-ceiling` is a real flag (`d24_selftest.py`) and is also how the limits
get re-calibrated at the bench.

### S4.5 Why `IC1` has no workbook row (and the one line that would give it one)

`ITEMS['IC1'] = []`, the `USB-HUB` precedent. The workbook has no item for
"the audio that crosses dig-dsp-a/b is the audio chip 1 sent": rows 139/140
are the LINKS and already belong to `AS-DSPA`/`AS-DSPB`, and taking them would
let an `IC1` PASS overwrite an `AS-DSPB` FAIL on the same row. Nothing was
invented in this tree; per S117-1 the catalog is mx26's.

🟡 **For the hub, one line in mx26's generator:** a new `Inter-board links`
item — *Inter-chip mix fabric (dig-dsp-a → dig-dsp-b audio)* — appended, so
its number is above every existing one and **nothing renumbers**, with
`tests = IC1`, `automation = 1`, `group = A4` (the pair-read group: no new
state, no rails). `ITEMS['IC1']` then names it and the row appears in the
report and in RUN ALL's denominator. Until then the gate is fully effective —
it runs inside `ensure_pair()` on every press that touches the pair — and its
verdict lives in the run log rather than in the results CSV.

---

## S5. Findings

**S118-1 🟢 THE INTER-CHIP FABRIC HAS NO GAIN AND NO CONVERSION IN IT, SO THE
TWO MECHANISMS MOST OFTEN PROPOSED FOR S115-2 ARE RULED OUT.** `_gather_chip1`
writes Q4.28 straight to the DMA half and `_scatter_chip2` reads it straight
out; the `Q1.31 <-> Q4.28` shifts live only on the CONVERTER lanes
(`chip1/block_io.asm:943`, `chip2/block_io.asm:529`). A lost conversion cannot
be the fault because there is no conversion on this path to lose. A slot
rotation cannot be the fault on its own either: all 41 fabric slots carry
chip-1 buses or forwarded inputs, and with chip 1's graph quiet a rotation
substitutes one silence for another. Measured healthy behaviour, both ends,
under a −6 dBFS tone: **0.03 to 0.08 dB apart at every slot**.

**S118-2 🔴 THE FOUR DMA HALVES ARE CONTIGUOUS AND CHIP 2's Q1.31 TRANSMIT
HALVES SIT DIRECTLY ABOVE ITS INTER-CHIP RECEIVE HALVES.** Read off the part:
IC RX ping `0xB4770`, IC RX pong `0xB4A00`, TX ping `0xB4C90`, TX pong
`0xB4F10`. A receive-side read that strays one region high lands in
`_gather_chip2`'s output — Q1.31, saturated at `0x7FFFFFFF` — and reports it
as Q4.28: **×8, saturating, sustained, with chip 1 silent, surviving a config
commit and cleared by a boot.** That is S115-2's signature including the
factor of 8 hiding in `+18.06 dBFS` and in the word `0x7FFFFEE0`
(= `0x0FFFFFDC << 3`, a 0 dBFS Q4.28 word in Q1.31 position). The generated
tables cannot reach there (max address `655` of `656`), so this needs
`_ic_rx_active_buf` itself to be wrong, and the ISR toggle that maintains it
is self-correcting. **No root cause is claimed** — but this is the first
hypothesis that accounts for the arithmetic rather than only the symptom, and
the one read that decides it is now in `s118_probe.py`, which prints all four
pointer words on every run.

**S118-3 🟡 S115-2's `_buf_C2_RECV_MAIN_L` READ SPANNED THREE DIFFERENT
VARIABLES.** Under `DSP4_BLOCK_KERNELS` that symbol is a SCALAR staging word
(the node file says so); the block is `_blk_C2_RECV_MAIN_L`. The 16 consecutive
words S115 read covered the scalar, three words of padding and 12 words of the
NEXT node's `_rx_ic_slot`. The finding stands — those words are still
fabric-delivered MAIN data — but the `+18.06 dBFS` peak may belong to MAIN_R,
not MAIN_L. Every tool written in this session reads `_blk_`.

**S118-4 🟡 A CM4 REBOOT LEAVES THREE PIN TRAPS BETWEEN THE HOST AND THE DSP
LINK, AND TWO OF THEM ARE NOT THE KNOWN ONE.** After `systemctl reboot`,
measured: GPIO27 `ip pd | lo` (the known `CS_M` / U2 trap — the link cannot
phase), AND GPIO6/GPIO24 in ALT so both chip selects sit asserted and the
parameter link answers as **"CHIP 3"**. `pin_handback()` fixes all of them and
every runner press calls it; a hand-driven tool after a reboot must do the
same three `pinctrl` writes or it will report a dead pair that is perfectly
alive. **The pair itself survived the reboot** — `FRAME_COUNT` climbed
straight through it and the fabric was still a wire afterwards.

**S118-5 🟢 THE GATE IS IN `ensure_pair()`, NOT IN RUN ALL, AND IT COSTS
ABOUT A SECOND.** S117-3 flagged the structural problem — a later RUN ALL pass
does not boot the pair when the link is alive, so a unit in this state carries
a fictional acoustic verdict through every later pass — and left the fix to
this dispatch. The cheapest correct place is the function that decides whether
to boot, because `link_alive()` was asking the wrong question: MAGIC and
BOOT_STAGE are answered perfectly by a pair whose MAIN receive is pinned. It
now also asks whether the fabric is a wire and boots on a `no`. Measured on
the part: an `--only AL1` press is **41 s with the gate against 39-41 s on the
S118-pre rollback**, i.e. the gate is inside the run-to-run spread; the gate
itself times at **0.706 s** and is asked once per press (cached on the `Rig`,
invalidated by a boot). `d24_runall.py` is unchanged and no catalog row
moved.

---

## S6. Files, deployment and the unit as left

### Deployed on MW-D24-2 (`/home/app/selftest/`)

| file | md5 | rollback |
|---|---|---|
| `d24_selftest.py` | `bfcafe0f97866963de2bf446bd3734c3` | `d24_selftest.py.bak-s118-pre` = `34de17cbda23b731fdd718947792a807` (S117's) |
| `dsp4_icrecv.py` | `21581bca121c3734fa47f2bc52f6236c` | new file |
| `s118_probe.py` | `72d464f992711d174aef6bf3aac95335` | new file (session instrument, not staged by the runner) |

`dsp4_icrecv.py` is in `STAGE_TOOLS`, so the runner refreshes it into the
stage dir md5-gated like the other seven. The catalog, the app, the CPLD, the
H1S1 firmware and `pair.conf` were NOT touched. `defs.lock` unmoved — no def
CSV, slot map, wire table or generated artifact changed, so **no contract bump
is owed**.

### In the repo

| file | what |
|---|---|
| `tools/pi/dsp4_icrecv.py` | new — the gate; the two ends of MAIN compared |
| `tools/pi/s118_probe.py` | new — the session instrument: all five stages of the chain, the four pointer words, and `--survey` for all 41 fabric slots at both ends |
| `tools/pi/d24_selftest.py` | `IC1` (section C, no workbook item), `_ic_gate()`/`_ic_cmd()`, the `ensure_pair()` guard, `Rig.ic_forced_boot` / `Rig.ic_gate`, `--ic1-ceiling`, `dsp4_icrecv.py` in `STAGE_TOOLS` |
| `MW/D24/DSP/s118/` | this report and the run logs |

### The unit as left

`matrix-app` **inactive**, `d24-testui` **active**, `AN_EN` (GPIO26) **lo**,
`CS_M` (GPIO27) **op dh — DRIVEN**, 595 chain **SAFE** (verified 200/200 by
the last press's own handback), `Mon001Level001/002` = **0**, every `MainOn`
**0**, `MainL001Mtr001` **0.000000**, `IC1 PASS` with both ends at exact
digital zero. `pair.conf` unchanged (`/home/app/loopthd/s109`, the
`factory-test-v1` pair; `chip1.ldr` `7f226919…`, `chip2.ldr` `6f11a1dd…`).
Session scratch removed from `/tmp` on the unit; every press in this session
wrote to a `/tmp` CSV, so `item-status.csv` was not appended to.

### How to use the instruments next time the state appears

```
# the verdict, 0.7 s
python3 dsp4_icrecv.py --symdir /home/app/loopthd/s109

# WHERE the signal enters: all five stages plus the four pointer words.
# If _ic_rx_active_buf is not _rx_ping_w or _rx_pong_w, hypothesis H1 (S118-2)
# is the answer and the question becomes who wrote it.
python3 s118_probe.py --symdir /home/app/loopthd/s109

# all 41 fabric slots, chip 1 send against chip 2 receive: a rotation shows as
# the same magnitude under the wrong name, a scale fault as a fixed dB step
python3 s118_probe.py --symdir /home/app/loopthd/s109 --survey --quiet
```

**Read `_blk_C2_RECV_MAIN_L`, never `_buf_C2_RECV_MAIN_L`** (S118-3), and
after a CM4 reboot do the three `pinctrl` writes first (S118-4) or a healthy
pair will read as dead.
