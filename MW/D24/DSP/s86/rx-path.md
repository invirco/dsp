provenance: AI-drafted 2026-09-20 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S86 — chip 1's RX path, read where the samples are

Unit MW-D24-2, 2026-09-20. Dispatch: HUB DISPATCH 2026-09-20 15:05Z.

**There is no fault in chip 1's receive path. There never was.** All 47 RX
entries on chip 1 carry samples, all eight DSPA pins deliver to the SPORT half
and TDM slot the design assigns them, and sixteen of the twenty-four D24
preamps answer a gain change with 32–40 dB of noise. The reading that has
driven five sessions — `_buf_C1_IN_01..32` at exact digital zero — is a
reading of a symbol that **no build with the block kernels on has ever
written** — which is every build that ships and every TEST_NODES pair. (The
per-sample build, `DSP4_BLOCK_KERNELS=0`, does write it — and the pair every
reading below was taken on is not one: its `_buf_C1_XIN_*` carry block data
while its `_buf_C1_IN_*` carry nothing, which is the block-kernel signature.)

No bisect was run, and the reason is stated before anything else: a bisect
looks for the commit that broke something, and the thing it would have
bisected is not broken. What follows is the measurement that establishes
that, taken before any firmware was touched.

Two things are owed and are not here: the EIN row needs a 150 Ω fixture on
J25 that is not fitted (§ GATE 3), and the dispatch's second witness, MIC 14,
sits in this unit's known dead analog section — which is eight channels and
not the four the record says (S86-6).

---

## S86-1 — `_buf_C1_IN_nn` is not a buffer, and no block-kernel build writes it

Under `DSP4_BLOCK_KERNELS` — which every shipping and every TEST_NODES pair is
built with — a node whose output is consumed by the next node of its own strip
writes the shared **block pool**, not a buffer of its own.
`src/chip1/nodes/C1_IN_16.asm` says so in its own header and in its code:

```
    i1 = BLK_CHAIN_A;
    ...
        r2 = dm(i0, m0);          /* the RX DMA word   */
        r2 = ashift r2 by -3;     /* Q1.31 -> Q4.28    */
        dm(i1, 1) = r2;           /* into the POOL     */
```

and beside it

```
    .global _buf_C1_IN_16;
    .var _buf_C1_IN_16;           /* ONE word, and nothing writes it */
```

The only other appearance of that symbol in a block build is
`process_chain.asm`, where it is loaded into `r0` as an **identity token** —
the value `_scope_tap` compares against `_scope_src` to decide whether this
call site is the watched one. It is never a destination.

The split is not between pins that work and pins that do not. It is between
nodes that own a buffer and nodes that do not:

| chip-1 nodes | `_buf_<nid>` | who writes it |
|---|---|---|
| 29 bus nodes + 15 `XIN_*` lanes | `[DSP4_BLOCK_SIZE]` | their own block kernel |
| the other 398, every strip node included | one word | **nobody** |

`_buf_C1_XIN_CODEC_01` is in the first row. `_buf_C1_IN_01` is in the second.
That is the whole of the reading S82–S85 rested on: four codec buffers moving,
thirty-two mic buffers at exact digital zero, in the same pass, on the same
bitstream — because four of them are buffers and thirty-two are linkage.

`tools/pi/dsp4_s39_chain.py` has carried the warning since S39 —
*"Under DSP4_BLOCK_KERNELS the strip does NOT run through `_buf_C1_IN_01` …
Reading `_buf_C1_IN_01` and calling the chain dead … measures a variable no
block kernel reads"* — and `dsp4_s48_audio.py` and `dsp4_node_verify.py` each
carry their own version of it. The lane scanners never got it. S81's rewrite
of `dsp4_inscan.py` moved the scan off `_rx_slot_C1_IN_nn`, correctly calling
it a symbol nothing writes, and onto `_buf_C1_IN_nn` — the other symbol
nothing writes — while keeping the first as its "must not move" control. Both
controls have been passing ever since, on a tool reading a dead symbol.

---

## GATE 1 — the receive path, measured in the only place it exists

`MW/D24/DSP/s86/tools/s86_rxscan.py` (landed as `tools/pi/dsp4_rxscan.py`)
reads `_rx_active_buf + off + k*stride`, with `off` and `stride` taken from
the part's own `_c1_rx_off` / `_c1_rx_stride` tables and the node names from
`_c1_rx_slot_ptrs`, which is the PATCHED pointer — so the name printed is the
node that consumes the lane on the booted product. Nothing in the tool is
hardcoded from the tree. That read is the one `s52lib.lane()` has carried
since S52.

**Three controls run in every pass and all three came out right in every run
below**: `FRAME_COUNT` advancing, and `_rx_slot_C1_IN_01` *and*
`_buf_C1_IN_01` each constant at `0x00000000`. The second dead symbol is in
the control list deliberately: it is read in the same pass, through the same
peek path, as the lanes printed beside it, so the trap is demonstrated rather
than described.

Shipping bitstream `dsp4_logic.d02d83b3cc22` on the part, design ID
`32'h83b3cc22` read back and MATCHED before the run; TEST_NODES pair
`/home/app/s83tn`, both chips BOOT_STAGE 7; 16 reads a lane.

### S86-2 — every mic lane carries samples, rails down

`FRAME_COUNT +5947`. All twenty-four of the D24's mic entries carry the
converters' own dither — 12 to 15 distinct words in 16 reads, RMS −112.6 to
−119.9 dBFS — while `_buf_C1_IN_01` and `_buf_C1_IN_16` sat at exact zero in
the same pass.

The eight entries at DSPA pin 3 (the D32's fourth AK5558, which a D24 does not
have), the eight snake lanes at pin 5 and the MEMS lane at pin 7 read a
constant `0xFFFFFFFF`; the two Pi lanes read a constant `0`. A stuck value is
as dead as a stuck zero and they are reported as STATIC, which is correct for
a card with nothing on those pins.

### S86-3 — and they answer the analog rails, converter by converter

Rails up, 595 unmuted at gain 63 (`0xFC`, VERIFIED 200/200), same boot, same
bitstream, same pass structure. `FRAME_COUNT +5945`.

| DSPA pin | AK5558 | entries | rails DOWN, RMS dBFS | rails UP, RMS dBFS |
|---|---|---|---|---|
| 0 | U15 | 8 (panel mics 1–4, 13–16) | −112.6 … −119.5 | −114.5 … −121.1 — **unchanged** |
| 1 | U39 | 8 (panel mics 5–8, 17–20) | −113.0 … −119.9 | **−69.3 … −83.3** |
| 2 | U60 | 8 (panel mics 9–12, 21–24) | −113.8 … −118.1 | **−64.6 … −83.4** |

Sixteen lanes move by 30–50 dB when the analog front end comes up. That is
live preamp noise arriving through the AK5558s, read out of the DSP's own RX
DMA region, on the shipping bitstream — the thing ten sessions have been
looking for. Pin 0's eight do not move at all; see S86-6.

### S86-4 — and every lane names its own pin and slot

The `_laneid` bitstream `dsp4_logic_laneid_adwit.12f4fd1cbfc1` (design ID
`32'hfd1cbfc1`, read back and MATCHED) streams
`{8'hA5, pin[3:0], tick, slot[2:0]}` on every DSPA input pin. Read out of the
DMA region there is no Q1.31→Q4.28 shift to undo — that shift is the node
kernel's `ashift by -3`, and it is where S85-7's uniform three-bit offset came
from — so the marker lands raw:

| entries | what the DMA carried | what the design says |
|---|---|---|
| 0–7 | `a5000000 a5010000 … a5070000` → **pin 0, slots 0–7** | `i_dspa[0]`, SPORT0 half A, 8 slots |
| 8–15 | `a510…a517` → **pin 1, slots 0–7** | SPORT1 |
| 16–23 | `a520…a527` → **pin 2, slots 0–7** | SPORT2 |
| 24–31 | `a530…a537` → **pin 3, slots 0–7** | SPORT3 |
| 32–35 | `a540…a543` → **pin 4, slots 0–3** | the codec |
| 36–43 | `a550…a557` → **pin 5, slots 0–7** | the snake |
| 44–45 | **pin 6, slots 0–1, at a one-bit offset** | `c1_rx_lanes_mfd[6] = 1` against an MFD-2 build |
| 46 | `a575…` → **pin 7, slot 5** | the ADAU7302's 47K strap |

**47 of 47 entries decode to exactly the pin and slot the generated lane table
assigns them**, at bit offset 0, with the Pi's two lanes reproducing their
MFD-1 framing difference without being told about it. This closes S85-7's hole
in `driveall`'s proof — the hole was real, and the answer through it is that
the binding is correct on all eight pins, SPORT 0/1/2/3 included.

### S86-5 — so what S85 concluded is void, and by how much

S85-8 reads *"the fault is chip 1's RX path for the mic lanes — SPORT/SRU
configuration, lane binding or RX DMA for sport 0, 1 and 2 — on the DSP side"*.
Every clause of that is disproved above, on the same unit, the same firmware
and (for S86-2/3) the same bitstream S85 measured on. S85's own measurements
stand: the pins do carry data, the retiming register does hold it, the launch
phase is not the fault, `driveall` did not prove the lane binding. Only the
inference from `_buf_C1_IN_*` does not.

The same correction applies upstream: S81-8, S82's converter re-take, S83's
"the mic lanes named dark", S84 and S85 all rest on this symbol. The findings
they took about the CPLD, the codec, the clock pair and the bitstream are
measurements and stand on their own; the "the mic lanes read exact zero"
clause in each of them is void.

One naming error travelled with it and is corrected here. S82–S85 record
*"MIC 5's own `_buf_C1_IN_16`"*. Under the landed S58 input patch J25 (panel
MIC 5) is **strip 5, node `C1_IN_05`**, RX entry 15, DSPA pin 1 TDM slot 7 —
which is what `d24_inputs.py` says, what `_rx_patch_regs` says on the part,
what S54's own `MIC5_STRIP` has always used, and what the gain response in
S86-6 confirms physically. `C1_IN_16` is the identity mapping of that DMA
position, i.e. the pre-S58 answer.

---

## GATE 2 — the fix, and what it is not

**No firmware change restores anything, because nothing is broken.** The RX
plumbing is also, on inspection, untouched since the S54–S58 reference point:
`git diff aac62831..HEAD` is EMPTY for `sru_config.c`, `sport_config.c` and
`dma_config.c`; in `chip1/lane_config.c` it adds lanes 4–7's S71/S72 slots and
does not touch lanes 0–3; and `sport_init.asm`'s only hunk is S79's
`_mtx_mask`. The bisect the dispatch asks for has no interval to run in.

**The signed configuration's triple does not move.** No DSP image was built
for a fix and none needed to be: the change below is a generated comment and
two host tools.

What is fixed is the instrument, at the point where the mistake was made five
times:

| file | change |
|---|---|
| `tools/pi/dsp4_rxscan.py` | **new** — the standing RX-lane instrument. Reads the DMA region, resolves geometry and node names off the part, carries `_buf_C<chip>_IN_01` as a must-not-move control, decodes the `_laneid` marker |
| `tools/pi/dsp4_inscan.py` | scans `_buf_C<chip>_XIN_*` only — the buffers that exist — and reads `_buf_C<chip>_IN_01` as a second dead-symbol control with the pointer to `dsp4_rxscan.py`; the docstring's "which the block kernels actually write" corrected; the stale shipping design ID updated |
| `tools/dsp/dsp_codegen.py` | every generated strip-input node now opens its block-kernel arm with *"`_buf_<nid>` IS NOT A BUFFER IN THIS BUILD"* and the one-line instruction for asking the real question. Comment only — the emitted code and data are unchanged |
| `tools/pi/logic_flash.sh` | takes the bench lock (S86-12) |
| `MW/D32/DSP/SHARC/bench_lock.sh` | deploys `dsp4_rxscan.py` with the link tools |
| `MW/D24/DSP/s86/tools/` | `s86_rxscan.py`, `s86_gate1.sh`, `s86_gate3.py`, `s86_gate3.sh`, `s86_survey.py`, `s86_handback.sh` |

### S86-12 — the one tool that reprograms the CPLD took no bench lock

S80-12 put the bench lock into seven bench drivers and S82 put it into
`loadlogic.sh`, whose own comment explains why a flash in particular must not
race another runner. **`tools/pi/logic_flash.sh` — the script that actually
writes the bitstream and stops `matrix-app` — had none**, so a capacity arm or
a measurement bar landing on the card mid-flash was the S10 contention failure
with a flash in the middle of it. It now takes the same lock the same way, and
`--self-test` (which drives no bench) does not. Nothing in the tree invokes
the script, so there is no caller that could deadlock behind it; proved with
`--dry-run`, which passed every gate and wrote nothing.

---

## GATE 3 — the EIN row: what was taken, and what is still owed

### S86-6 — the dead analog section is eight channels, not four, and it is ad[0]

The full 24-channel survey, every register under test alone open, phantom off,
INSTR byte `0x00`, TEST_MEAS on that channel's own strip, rails up
(`MW/D24/DSP/s86/data/survey.txt`):

| AK5558 | channels | NoiseResult at code 63 | rise, code 0 → 63 |
|---|---|---|---|
| U39 (ad[1]) | panel 5–8, 17–20 | −75.2 … −81.9 dBFS | **32.5 … 36.9 dB** |
| U60 (ad[2]) | panel 9–12, 21–24 | −73.3 … −82.0 dBFS | **31.8 … 40.4 dB** |
| **U15 (ad[0])** | **panel 1–4, 13–16** | −116.0 … −116.2 dBFS | **−0.21 … +0.08 dB** |

Sixteen preamps answer 63 codes of gain with 32–40 dB of noise. **U15's eight
do not answer at all** — their lanes sit on the converter's own dither in both
rail states and at both gain codes.

**This is the bench unit's known dead analog section, and the new part is its
extent.** S48 (2026-09-15) recorded "lanes 1–4 are the MIC 1–4 section the
bench state records as DEAD" at −114…−118 dBFS, "what an unpopulated front end
reads", and S55 wrote on its own channel table that "J15–J22 (U15, strips
1–4/13–16 under S58) have no rails today: not tested". So the section has been
known since before the sessions that went looking for dark converters. What
was not established is how far it reaches: S48 could name four lanes because
it was reading twelve. **It is eight — the whole of `ad[0]`'s converter, XLRs
J15–J22, panel mics 1–4 AND 13–16, preamps U17–U31** — and the floor measured
tonight, −116.0 to −116.2 dBFS, is S48's −114…−118 dBFS band.

That also closes S85-3, which recorded `ad[0]`'s indifference to the analog
rails as "a thing to look at, not a thing to conclude from": `ad[0]` is the
dead section's converter, so it is converting and framing with nothing in
front of it — which is exactly what its `ones` high-water of 188 against 256
said. Two independent instruments, the CPLD's toggle counter and the DSP's own
TEST_MEAS, now agree on it.

Nothing here is a fault to chase in software. What the hub may want is the
record corrected from four channels to eight, and whether this unit's section
is ever to be populated: 🔴 S86-N1.

One channel inside that group behaves differently again: **J15 (panel MIC 1,
strip 1) reads exact digital zero, −336.12 dBFS, at both gain codes**, while
its RX lane (entry 7) carries dither in the same session and the other seven
U15 channels read −116. That is a strip-1 measurement-path observation, not a
lane observation, and it is recorded rather than diagnosed.

### S86-7 — the EIN row is owed on a fixture, and the number says so

The fixture was checked before any row was labelled, not assumed. S54's loop
check — 1 kHz at −20 dBFS into AUX 1 with the preamp at code 0 — arrives at
−14.42 dBFS coherent peak with the loop cable on J25. It measured
**−142.81 dBFS**: nothing arrives, the loop cable is off.

What is across J25 pins 2–3 instead is nothing at all, and the noise figure is
what says so:

| J25 (panel MIC 5, strip 5) | RmsResult | NoiseResult | EIN |
|---|---|---|---|
| code 63 | −77.31 dBFS | −77.31 dBFS | **−109.89 dBu** at the input |
| code 0 | −114.36 dBFS | −114.36 dBFS | −93.80 dBu |

(EIN = P + 3.01 + 23.13 − G_loop, the S55/S57-R convention, with MIC 5's own
loop gain from S54's 64-code T1 sweep: 58.717 dB at code 63, 5.578 at code 0.)

**−109.89 dBu against S55's −127.2 dBu at 150 Ω is 17.3 dB high**, and the
rms spread across eight windows is 4.59 dB against 0.28–0.80 dB on every other
row taken tonight. Both are what an **unterminated** preamp input does. So the
row the dispatch asks for is not takeable: it needs 150 Ω across J25 pins 2–3,
and the number above is the open-input noise row, which is a real measurement
of something else.

**MIC 14 (J18) cannot be the second witness on this unit.** It reads −116.05
dBFS at code 63 and −116.10 at code 0 because it is one of the dead section's
eight (S86-6) — there is no preamp behind it to measure. Its dBu column is not
printed: it has no loop gain of its own on record either, and borrowing MIC 5's
would turn a converter floor into a preamp figure. A second EIN witness has to
come from the sixteen channels that work (J26–J32, J35–J42), and needs a loop
cable on that XLR for its own T1 loop gain.

**The preamp survey's typical figure cannot be re-stated in dBu either**, for
the same reason and for a second one: the dBu column needs each channel's own
loop gain and only MIC 5's is on record. What the survey re-states on the fixed
pair is the thing that needs neither — **the gain response**: a median 35.16 dB
(U39) and 33.53 dB (U60) of noise rise across 63 codes, on sixteen of sixteen
live channels, at an open-input floor of −73.3 to −82.0 dBFS at code 63. S55's
−126.5 … −127.2 dBu at 150 Ω stands as the last real EIN figures for this unit
and nothing tonight moves them.

The talkback T1/T3 re-take is owed on the same cable: with the AUX 1 loop off
the J25 path carries nothing to measure.

---

## GATE 2 (continued) — the bar, and the proof the image did not move

### S86-10 — the generator change is provably image-neutral

Built twice from the same tree with the same command — `./build.sh all`,
`shipping.config`, no overrides — once before the `dsp_codegen.py` change and
the regeneration, once after:

| | chip1.ldr | chip2.ldr |
|---|---|---|
| before | `e3e25a79c4619d1a44305258f99fac7d` | `41a6b913e5f77bac698e136abd9aac65` |
| after  | `e3e25a79c4619d1a44305258f99fac7d` | `41a6b913e5f77bac698e136abd9aac65` |

**Byte-identical**, and both equal the image the capacity arm below built and
ran (`chip1.ldr e3e25a79  chip2.ldr 41a6b913`). So the comment in 32 generated
node files costs nothing in the artifact and **the signed configuration's
triple does not move** — no switch was the fix, because nothing needed fixing.

`./regenerate-dsp-contract.sh` ran clean (defs-v2026.09.19.3, defs commit
`6fd91594`, 776 SHARC sources, D24 3989/3989 and D32 5780/5780 mapped cells
carrying an address) and `./check-contract-drift.sh` leaves nothing behind
but those 32 comment-only files. `defs.lock` did not move, so no contract
note is due.

### S86-11 — the audio bar, unmoved

| bar | command | result | S82 |
|---|---|---|---|
| golden harness | `tools/dsp/golden_harness.py -v` | **59/59 passed** | 59/59 |
| contract shape | `tools/dsp/dsp_validate.py MW/D32/DSP/SHARC/dsp.csv` | **OK — no errors**, 701 nodes, the same 4 process-order notes the generator repairs | same |
| accept dry-run | `tools/accept/dryrun_d24.sh` | **187 of 187 comparisons agree within tolerance** (0 DIFF, 0 MISSING) | 187/187 |

Three for three against S82, which is what a byte-identical image has to give.

---

## GATE 4 — the S82 D24 driven row, re-taken

`ARM=s86d24 PRODUCT=d24 ./capacity.sh --driven`, no override on the command
line, on the `driveall` bitstream `943f27966c28` (design ID `32'h27966c28`
read back and MATCHED before the run, shipping restored after it). Both boots
in the one invocation, 135,049–135,054 blocks a row, `build_cfg2` read off the
part **during** the measurement.

| row | chip 1 (S86 / S82) | chip 2 (S86 / S82) | missed blocks |
|---|---|---|---|
| A — silent, default | 43.13 / 43.22 (**−0.09**) | 77.50 / 77.41 (**+0.09**) | 0 / 0 |
| B — silent, loaded | 57.61 / 57.50 (**+0.11**) | 84.41 / 84.27 (**+0.14**) | 0 / 0 |
| **C — DRIVEN, six FX live** | 57.55 / 57.54 (**+0.02**) | **84.47 / 84.34 (+0.12)** | **0 / 0** |

(two-boot means of `_proc_cyc`, the field S82 and S85 quote, read by
`s85_caprows.py`. `build_cfg2 0xE2018E6F` on every row, both chips, both
boots — the same word S82 and S85 quoted.)

**84.34 % holds: the re-taken row is 84.47 %, +0.12.** The driven regime was
proved on both boots, not asserted — `48 of 48 dynamics envelopes live on
chip 1` and `28 of 28 on chip 2`, twice — and not one block was missed in any
of the twelve chip-rows.

**The boot spread is stated rather than averaged away.** Chip 2's row C read
84.20 % on boot 1 and 84.73 % on boot 2, a spread of 0.53 points against the
~0.33 S82 documented for this row. Both boots bracket S82's 84.34 %, the two
boots' A rows agree to 0.00 and their B rows to 0.13, and the mean is +0.12 —
so this is boot-to-boot variation of the usual kind on a row whose mean has
now been taken three times (84.34, 84.35, 84.47) with a total span of
0.13 points.

**The dispatch's premise for this gate does not apply, and it is worth saying
why.** It asks whether "the mic lanes now carrying real data may cost cycles
the silent lanes did not". They always carried data — rows A and B are taken
with the rails down, where the lanes carry the converters' dither (S86-2), and
row C is taken on `driveall`, which broadcasts a stimulus onto every DSPA lane
by construction. What changed tonight is what is known about them, not what
the part receives. The per-lane cost is a read, a shift and a store whatever
the sample value; the only data-dependent cost is the dynamics branch, and
that is exactly what the 48/48 and 28/28 regime proof pins.

The deploy candidate is unchanged and stays STAGED: the pair the deploy holds
is byte-identical to what HEAD builds (S86-10), so there is nothing to update.

---

## Handback — the unit as found

Taken with `tools/pi/dsp4_rxscan.py` — the instrument this session landed,
run from `/home/app/dspboot` rather than from a session-local copy, so what
goes into the record is the artifact the next session will run. Rails up, 595
at `0xFC` VERIFIED 200/200, both chips BOOT_STAGE 7, `FRAME_COUNT +4787`,
both dead-symbol controls constant at `0x00000000`:

**28 of 47 RX entries CARRYING SAMPLES** — the 24 D24 mic lanes and the four
codec returns, with `ad[0]`'s eight at −114 … −121 dBFS (the dead section) and
`ad[1]`/`ad[2]`'s sixteen at −64.6 … −83.6 dBFS. The nineteen STATIC entries
are the D32's fourth converter, the snake and the Pi lanes, which nothing on
this card drives.

The unit is as found:

- **shipping bitstream on the part, read back after the last flash**:
  `design_id 32'h83b3cc22  cfg_bits 16'h0010  SHIPPING`
- 595 SAFE image `0x01` restored and **VERIFIED 200/200**, written last (S70-7)
- AN_EN (GPIO26) `lo`, CS_M (GPIO27) `ip pu` — both read back, not assumed
- `matrix-app` restarted and **active**
- four CPLD flashes, all FLASH-OK on attempt 1 with the design ID read back
  and MATCHED, tabled in `docs/d24-bench-logic-flash-log.md`
- `defs.lock` unmoved, `check-contract-drift.sh` clean,
  `check_bench_pins.sh` **canonical everywhere**
- one DSP image built — the `s86d24` capacity arm, in its own staging path,
  never `~/dspboot` — and its rows are in `MW/D32/DSP/SHARC/goldens/`

---

## 🔴 Notes for the hub

**S86-N1 — the bench unit's dead analog section is EIGHT channels, and the
record says four.** S48 called it "the MIC 1–4 section", S55 called it "J15–J22
… no rails today", and `dsp4_s42_align.py` is still owed a depopulated-section
guard (S48 §8.4, S49) that would need the right count. Measured tonight across
all 24 XLRs at gain codes 63 and 0: **J15–J22 — panel mics 1–4 and 13–16,
preamps U17–U31, the whole of converter U15 / `ad[0]` — show a gain response of
−0.21 to +0.08 dB**, against 31.8–40.4 dB on the other sixteen. Two independent
instruments agree (this survey and S85-3's CPLD toggle counts). **Options for
the hub:** (a) record the section as eight channels wherever the bench state is
written down, and size the depopulated-section guard to eight; (b) if the
section is meant to be populated on this unit, dispatch a hardware look — but
nothing in the software gates blocks on it; (c) leave the record as it is and
accept that every preamp row on this unit covers sixteen channels. **What a
spoke should not do is keep re-discovering it**: it has now been found
independently at S48, S55, S85-3 and S86.

**S86-N2 — the EIN row needs a 150 Ω fixture fitted on J25, and the talkback
row needs the AUX 1 loop cable.** Both are physical and neither is a refusal:
the lane is proved live and the instrument is proved working, so the row is one
component away. **Options:** (a) PW fits 150 Ω across J25 pins 2–3 (and, for a
second witness with a calibration of its own, the loop cable on a second XLR so
its T1 loop gain can be taken); (b) the row is taken on a channel that already
has a fixture, if one is on the unit; (c) the open-input figure above is
accepted as the session's number, labelled as open-input and not as EIN.

**S86-N3 — five sessions of record carry a void clause and the hub may want it
retracted centrally.** S81-8, S82, S83, S84 and S85 each state that the mic
lanes read exact digital zero. The statement is true of the symbol and false of
the lanes. This report corrects it for S86's own purposes; whether the earlier
dispatch blocks in `tasks.md` are annotated, and by whom, is the hub's call.
