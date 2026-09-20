provenance: AI-drafted 2026-09-20 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S85 — the capture launch phase for the converter lanes, measured

Unit MW-D24-2, 2026-09-20. Dispatch: HUB DISPATCH 2026-09-20 13:57Z.

**The launch phase is not the fault, and the mic lanes are not reading any pin
this CPLD drives.** Both halves are measured, not argued.

`ad[0..2]` were counted on `bck8_launch` and on `bck8_sample` simultaneously —
two banks of the same counters in one bitstream, on the same 256 bit periods
of the same 48 kHz frames — and the two banks return the same numbers, rails
down and rails up alike. The data is stable across the whole 40.69 ns between
the two sampling points, so neither is sitting on a data transition and
S84-6's hypothesis is disproved rather than argued away.

Gate 2 then had no edge to move the capture to, so it removed the last three
things inside the CPLD that could differ between a lane that works and a lane
that reads zero — a retiming register, the codec's own live data, and finally
`driveall`'s assumption that the pins are mapped the way this design believes.
The last of those is where the fault was hiding. **With every one of the eight
DSPA input pins carrying a distinct stream that names its own pin and slot,
six buffers on chip 1 decoded their own pin and slot correctly — three
different pins across six slots — and all thirty-two mic buffers read
`00000000` — no marker, nothing from any pin at all.** The
fault is chip 1's RX path for sport 0, 1 and 2, on the DSP side, and no LOGIC
change can reach it.

---

## GATE 1 — the phase, measured

`dsp4_logic_adwit` extends the S84 witness from three counter banks to six:
the same three lanes, counted on both bck8 edges at once. The knock's low
three bits select what is answered about — bits 1:0 the lane, **bit 2 the
edge** — and S84's three knock words have bit 2 clear, so they still ask
exactly what they asked then and the S84 readings need no correction to be
compared with these.

Both banks count the same pass. That is the whole design of the instrument:
the comparison is between two readings of ONE frame sequence, not between two
runs, so a difference cannot be drift, a different bitstream or a different
rail state.

### S85-1 — the two edges agree, on every lane, in both rail states

Median of the reply frames; `ones` and `toggles` are per 48 kHz frame out of
256 TDM8 bit periods.

**Rails DOWN, 595 as found** (design ID `32'h3d97f578` read back and MATCHED
before any reading):

| lane | sample: ones / tog / max | launch: ones / tog / max | Δ ones | Δ tog |
|---|---|---|---|---|
| `ad[0]` | 95 / 26 / 188 | 97 / 26 / 188 | +2 | 0 |
| `ad[1]` | 96 / 26 / 256 | 96 / 26 / 256 | 0 | 0 |
| `ad[2]` | 98 / 26 / 256 | 97 / 26 / 256 | −1 | 0 |

**Rails UP, 595 unmuted at gain 63 (`0xFC`, VERIFIED 200/200), three knocks
per bank:**

| lane | sample: ones / tog / max | launch: ones / tog / max | Δ ones | Δ tog |
|---|---|---|---|---|
| `ad[0]` | 98 / 26 / 188 | 96 / 26 / 188 | −2 | 0 |
| `ad[1]` | 96 / **50** / 256 | 96 / **50** / 256 | 0 | 0 |
| `ad[2]` | 95 / **48** / 256 | 94 / **48** / 256 | −1 | 0 |

Every arm's frame counter advanced between knocks, on all seven arms in both
runs, so no number here is reported on a stalled witness. The `cdc_o` control
arm answered CARRYING DATA in the same runs.

**The toggle counts are IDENTICAL on the two edges — not close, identical —
in all six lane/rail combinations.** A lane sampled on top of its own data
transition cannot do that: half its bit periods would resolve arbitrarily and
the transition count could not come back the same number twice. The data is
stable across the whole 40.69 ns window between the two sampling points.

**`ones` is corroboration and not the verdict, and S85 learned that the hard
way.** The two banks COUNT concurrently but are READ by separate knocks
seconds apart, so `ones` — which is simply what the converter was emitting —
drifts with the content between the two readings. On the re-take (below) it
drifted by 5 counts on `ad[0]` while `toggles` stayed at 26 on both edges in
every one of six knocks, and the reader's first verdict rule — last knock,
±4 on either statistic — called that a phase difference. It is not one. The
rule now takes the median across knocks and rests the verdict on `toggles`,
with a large `ones` difference reported as content drift rather than as
evidence. The conclusion is unchanged; the reasoning behind it is now the
right one.

### S85-2 — the generator's own ratio holds

The witness also carries a sticky ratio check: `bck_ratio_ok` is 1 while every
`conv_fs` frame since power-up has held exactly 256 `bck8` periods. It stayed
set through both runs, so every `ones` and `toggles` number above is a count
out of a true 256 and not out of a frame that had lost or gained a bit.

This is still not a witness that the clock pair ARRIVES at the AK5558s.
`conv_bck` and `conv_fs` are outputs of this part, U3.142 and U3.141 are the
only drivers on those nets, and nothing in a MAX V can see the far end of a
net it drives. It witnesses the generator, which is the only half of that
question this part is entitled to answer — and it is the half that would have
made every count above a lie if it had failed.

### S85-3 — S84-4 reproduced, and it is signal content, not a sampling artifact

S84 found the toggle count on `ad[1]` and `ad[2]` roughly DOUBLING when the
analog rails come up while `ad[0]` stayed put, and recorded it as a fact it
had not yet diagnosed. It reproduces exactly — 26 → 50 on `ad[1]`, 26 → 48 on
`ad[2]`, 26 → 26 on `ad[0]` — and the second bank settles what one bank could
not: **the doubling appears identically on both edges.** A sampling artifact
would not; a change in what the converter is emitting does. So this is the
analog front end reaching converting ADCs and adding LSB activity, measured
from inside the CPLD.

`ad[0]`'s indifference is still not diagnosed, and one new fact narrows it:
`ad[0]`'s `ones` high-water mark is 188 in every run while `ad[1]` and
`ad[2]` both reach 256 (a frame in which the lane was high in all 256 bit
periods). The three lanes are three different AK5558s — `ad[0]` is U15
(mics 1–4 and 13–16), `ad[1]` is U39 (5–8, 17–20), `ad[2]` is U60 (9–12,
21–24) — so U15 is converting and framing but its eight channels are not
picking up what the other two ADCs' channels are. It remains a thing to look
at, not a thing to conclude from.

### S85-4 — the round trip, from the netlist

The path the S84-6 hypothesis was about, established from the netlist and the
hardware map rather than assumed:

`conv_bck` leaves U3.142 onto board net `C1`, which fans out through **five
33R taps** — R111 to the ADC/DAC FPC, R65/R66/R67 to the three option slots'
`BCK_1..3`, R61 to the D32 header J33. `conv_fs` (U3.141, net `L0`) has the
same shape through R112/R62/R63/R64/R60. U3.142 and U3.141 are the only
active drivers on either net. Across the FPC the pair is **re-buffered on the
Analog board** by single-gate buffers U97/U98 before it fans out locally to
the three AK5558s — a delay term nothing in this repo had previously counted.
The return lanes AD0..2 come back over the same FPC to U3 pins 139/138/134,
one converter per pin.

No stage of that loop is constrained in the CPLD's own `dsp4_logic.sdc` —
there is no `set_input_delay` on `ad[]` at all — so whatever margin exists
was never designed, only inherited. A bare order-of-magnitude budget (CPLD
output delay, flight out, U97/U98, AK5558 SDOUT delay, flight back, CPLD
input delay) lands in the tens of nanoseconds against a 40.69 ns half period,
which is why the hypothesis was worth a build. The measurement is what
settles it, and the measurement says the data is stable on both edges.

---

## GATE 2 — the fix that was not one, and the two that followed

The dispatch's gate 2 asked for the lanes to be captured "on the edge the data
is valid on". Gate 1 leaves no such edge to move to: the data is valid on both.
So gate 2 became three builds that each removed one of the last things in the
CPLD that could differ between a lane that works and a lane that reads zero.
Every one of them was flashed FLASH-OK on attempt 1, its design ID read back
and MATCHED before any reading, and every reading below is a two-sided one —
the pins and the buffers in the SAME pass, on the SAME bitstream, rails up,
595 at `0xFC` VERIFIED 200/200, both chips at BOOT_STAGE 7.

### S85-5 — a retiming register does not fix it

`dsp4_logic_adrt_adwit.43ec02c13e1a` (design_id `32'h02c13e1a`, 885/1270 LE,
Fmax 68.61 MHz, sim gate PASS) stops `ad[0..2]` being a wire through this part.
They are captured on `bck8_launch` and handed to the DSP as a register output
with the full half bit period of setup — which is exactly the arrangement
`driveall` uses, and `driveall` works. It costs one BCK period of latency and
the comment in the RTL says so rather than hiding it.

| side | reading |
|---|---|
| the PINS, both banks | **CARRYING DATA** — ones 95–98, toggles 26/50/48, all six frame counters advancing |
| the BUFFERS `_buf_C1_IN_*` | **0 of 32 moving**, exact digital zero |
| the codec buffers `XIN_CODEC_*` | **4 of 4 moving**, same pass |
| controls | `FRAME_COUNT +36939`, dead symbol 1 distinct |

The launch bank counts the very bits the retiming register captures — same
strobe, same data — so this is not "the pins are alive and the buffers are
not". It is **the register is loaded with live converter data and the DSP
reads exact zero out of it.**

### S85-6 — nor does handing the mic lanes the codec's own data

`dsp4_logic_adcdc_adwit.3490d03fcc18` (design_id `32'hd03fcc18`, 882/1270 LE,
Fmax 63.0 MHz) feeds `i_dspa[0]`, `[1]` and `[2]` from `cdc_o` — a converter
lane on the same Analog board, off the same `conv_bck`/`conv_fs` pair, crossing
this part the same combinational way, and one the DSP reads correctly in the
same pass. All three from one source deliberately: three lanes reading one
identical stream is the reading no per-lane accident explains.

`FRAME_COUNT +39339`, dead symbol 1 distinct. **Mic lanes 0 of 32 moving.
Codec lanes 4 of 4 moving** — the same bits, at the same instant, read
correctly through `i_dspa[4]` and not at all through `i_dspa[0..2]`.

### S85-7 — the hole in `driveall`'s proof, and what is in it

Four sessions have leaned on `driveall` to place the fault downstream of the
CPLD: every chip-1 input buffer carries the stimulus, therefore pin → SPORT →
RX DMA → slot map → buffer is good for lanes 0–5. **That is not what the test
shows.** `driveall` sets `i_dspa[5:0] = {6{pcm_drive}}` — six pins, ONE signal.
A receiver reading any of those six sees identical bits, so the test cannot
tell a correct lane mapping from a permuted one, and cannot tell either from a
receiver that is reading a pin this design believes is somewhere else. It
proves the pins reach the DSP. It never proved WHICH pin reaches which SPORT
half, and nothing else in the record does either.

`dsp4_logic_laneid_adwit.12f4fd1cbfc1` (design_id `32'hfd1cbfc1`, 866/1270 LE,
Fmax 67.76 MHz) closes it. Every one of the eight DSPA input lanes carries a
DIFFERENT stream, and each stream names its own pin and its own slot:

    word[31:16] = {8'hA5, pin[3:0], tick, slot[2:0]}      word[15:0] = 0

**The instrument proves itself before it accuses anything.** Three lanes
decode, in the same pass, to exactly the pin and slot the design assigns them
— and two of those three are facts no coincidence produces:

| buffer | word read | decodes to | the design says |
|---|---|---|---|
| `XIN_CODEC_01..04` | `f4a80000` `f4a82000` `f4a84000` `f4a86000` | **pin 4, slots 0,1,2,3** | `i_dspa[4] = cdc_o`, codec on slots 0–3 |
| `XIN_MEMS` | `f4aea000` | **pin 7, slot 5** | `i_dspa[7] = mems`; the ADAU7302 is strapped 47K = **TDM8 slot 5** |
| `XIN_PI_L` | `0a560000` | **pin 6, slot 0** | `i_dspa[6] = pcm_tdm` |

Two details of HOW they decode are worth stating, because they are what
makes the decode a measurement rather than a pattern match.

The marker sits at bit 3 of the codec and MEMS words and at **bit 4 of the
Pi's** — the one-bit offset lane 6 must carry, because it is the MFD 1 half of
`c1_rx_lanes_mfd = {2,2,2,2,2,2,1,2}` and this build frames for MFD 2. The
instrument reproduces the slot-5 strap and the S78-3 framing difference
without being told either, which is a stronger self-check than any assertion
in this report.

The uniform three-bit offset on the other two is NOT diagnosed here and is
not claimed to be. It is either a −18 dB input trim in the graph (the codec
and MEMS words read back sign-extended, `f4a8…`, which is what an arithmetic
shift of a negative sample looks like, and lane 6's window starting one bit
later makes its word positive so the same shift brings in zeros — `0a56…`) or
a three-bit framing offset on the RX side. **This reading cannot separate
them and does not need to**: the marker, the pin field and the slot field are
intact in every case, so the question asked — which pin does each buffer read
— is answered either way.

**And every one of `IN_01` … `IN_32` reads `00000000`. No marker. Nothing
from any pin at all**, while pins 0, 1 and 2 were carrying `0xA50X0000`,
`0xA51X0000` and `0xA52X0000` throughout.

### S85-8 — the verdict, and it is not in this repo's CPLD

Six buffers on one chip, in one image, in one pass, decoded their own pin
and slot correctly — three different pins across six different slots.
Thirty-two read nothing at all. The CPLD delivered distinct, identified,
non-zero data on all eight of its DSPA input pins and chip 1's mic RX halves
took none of it.

**The fault is chip 1's RX path for the mic lanes — SPORT/SRU configuration,
lane binding or RX DMA for sport 0, 1 and 2 — on the DSP side. It is not the
converters, not the analog board, not the clock pair, not the launch phase,
not the CPLD's lane path in any of the three forms it was built in today, and
no LOGIC change can fix it.** Ten sessions of converter diagnosis end here.

---

## GATE 3 — the EIN row: NOT TAKEN, and why

The dispatch asks for MIC 5 at 150 Ω against −127.2 dBu with MIC 14 as the
second witness. **It is not takeable and was not faked.** The EIN row is read
off the mic lane's own samples — MIC 5 is `C1_IN_16` and MIC 14 is
`C1_IN_05` — and both of those buffers read exact digital zero all evening, on
every one of the four bitstreams flashed today. A noise figure computed from a
buffer that is not receiving is not a measurement of a preamp; it is a
measurement of nothing, reported in dBu.

The row is owed the moment the mic lanes carry samples, and nothing else about
it has changed: the S54 recipe, the 150 Ω across J25 and the −127.2 dBu
reference all stand. The tone into MIC 5's buffer that gate 2 asks for is in
the same position, and S83-Q2 (the AUX 1 → J1 cable) does not gate it either
way — a lane that reads zero with the rails up reads zero with a tone on it.

---

## GATE 4 — shipping adopts the new label

### S85-9 — the witness is in every bitstream now, and it costs 361 LEs

Hub ruling S84-N1 is implemented: `DSP4_AD_WITNESS` is gone as a switch and
the ad[0..2] witness is built into every configuration, shipping included,
exactly like the `cdc_o` witness it copies. `cfg_bits` bit 6 is retired with
it — a bit that is always set says nothing — and the bit is left reserved
rather than reused.

The ruling asked for the area cost to be stated. Measured on this part, same
tree, same fitter, back to back:

| build | logic elements | registers | Fmax |
|---|--:|--:|--:|
| shipping WITHOUT the witness | 521 / 1,270 (41 %) | 373 | 68.56 MHz |
| shipping WITH it (six banks) | 882 / 1,270 (69 %) | 662 | 67.44 MHz |

**+361 LEs, 28 points of the device.** Both clear the 49.152 MHz sysclk by a
wide margin, so this is an area decision and not a timing one. It is worth
saying that the S84 form of the witness — three lanes, one edge — was +174,
and that S85 doubled it by adding the second bank whose question is now
answered. See S85-N1.

### S85-10 — the labels that moved, and the one that moved twice

| build | before S85 | at S85 HEAD |
|---|---|---|
| shipping | `7a6a4529f29c` (`32'h4529f29c`) | **`d02d83b3cc22`** (`32'h83b3cc22`) |
| driveall | `c49f4128a083` | **`943f27966c28`** (`32'h27966c28`) |

`loadlogic.sh` now names both, with `shipping-s82` and `driveall-pre85`
kept so the S82-era records still resolve to the artifacts they were taken on.

### S85-13 — the S82 D24 driven row, re-taken on the new bitstream

Gate 4's check, and the reason it is worth taking at all: the label moved, so
the question "did anything move with it" has to be answered by measurement
rather than by the observation that the lane path is byte-identical. Taken the
way S82 took it — `ARM=s85d24 PRODUCT=d24 ./capacity.sh --driven`, no override
on the command line, on the matching new `driveall` build
(`943f27966c28`, design ID read back and MATCHED), both boots, 135,000 blocks
a row — with `build_cfg2` read off the part **during** the measurement so the
number and the configuration are one reading:

| row | chip 1 (S85 / S82) | chip 2 (S85 / S82) | missed blocks |
|---|---|---|---|
| A — silent, default | 43.13 / 43.22 (**−0.09**) | 77.54 / 77.41 (**+0.13**) | 0 / 0 |
| B — silent, loaded | 57.50 / 57.50 (**+0.00**) | 84.36 / 84.27 (**+0.09**) | 0 / 0 |
| **C — DRIVEN, six FX live** | 57.62 / 57.54 (**+0.09**) | **84.35 / 84.34 (+0.01)** | **0 / 0** |

`build_cfg2 0xE2018E6F` on every row — the same word S82 quoted. The driven
regime was proven on both boots, not asserted: `48 of 48 dynamics envelopes
live on chip 1` and `28 of 28 on chip 2`, twice, which is the check that
separates a driven row from the silence-row-wearing-a-driven-label that voided
every S28 row.

**84.34 % holds. The re-taken row is 84.35 %, a delta of +0.01 points**, an
order of magnitude inside the ~0.33-point boot spread S82 documented for this
very row (its own boot 1 read 84.50 % against its two-boot mean). Not one
block was missed in any of the twelve chip-rows, 135,000 blocks each. Adopting
the label costs nothing measurable, which is what the byte-identical lane path
predicted and is now a measurement rather than a prediction.

### S85-11 — build.sh had the same hole one level up, and it is closed

`SRC_HASH` covers `rtl/*.v`, the qsf, the sdc, the slot-map hash and
`CFG_LINE`. It does not cover `build.sh` — and `CFG_BITS` is computed BY
`build.sh`. Adding bit 7 for the `AD_RETIME` switch therefore changed what a
part answers to the ID knock while leaving the label it is filed under
identical: two functionally different bitstreams sharing one label, the exact
failure the `CFG_LINE` paragraph exists to prevent, one level up from where it
was looking. Caught in the session, on the first artifact it affected, before
anything was measured on it.

The fix is to put the computed word itself into `CFG_LINE`, so any future
change to the derivation renames every artifact it changes. That is why the
plain witness build rebuilt as `d78c5c279587` after having been
`f2f33d97f578`: same RTL, same macros, different hash input. The gate 1
numbers above were taken on `f2f33d97f578` and re-taken on the adopted
shipping label — see below — so nothing rests on an artifact that no longer
rebuilds from HEAD.

### S85-12 — a label's bitstream is reproducible, its file md5 is not

Checked because the S82/S84 discipline compares md5s. Two builds of
`d02d83b3cc22` from the same tree differ in exactly ONE line — the
`!Device #1: … <date>` comment `quartus_cpf` stamps into the .svf — and are
byte-identical everywhere else. So the programmed content IS reproducible and
the file md5 is not, and identity has to rest on the design ID read off the
part rather than on a file hash. That is already what the standing read-back
rule uses; this is recorded so nobody reads a changed md5 as a changed
bitstream.

---

## What was changed in the tree

| file | change |
|---|---|
| `shared/dsp4-logic/rtl/dsp4_logic_top.v` | the witness doubled to six banks (both bck8 edges) and made UNCONDITIONAL per hub ruling S84-N1, with the area cost stated in the source; the `bck_ratio_ok` generator check; three diagnostic arms — `DSP4_AD_RETIME`, `DSP4_AD_FROM_CDC`, `DSP4_LANE_ID` |
| `shared/dsp4-logic/rtl/dsp4_pcm_reframe.v` | the third knock's selector widened to three bits (lane + edge), with S84's three words left meaning what they meant; `ad_edge` out |
| `shared/dsp4-logic/build.sh` | `AD_WITNESS` retired as a switch; `AD_RETIME`/`AD_FROM_CDC`/`LANE_ID` added; **`CFG_BITS` moved above `CFG_LINE` and INTO the hash** (S85-11); cfg bit 6 retired, 7/8/9 assigned |
| `shared/dsp4-logic/sim/tb_pcm_capture.v` | the knock-3 arm now walks all six (lane, edge) pairs, checks BOTH echoes, checks the counter word actually comes from the selected bank, and takes the lane-3 negative control on both edges |
| `tools/pi/dsp4_ad_witness.py` | the edge selector, the edge echo check, the `bck_ratio_ok` refusal, and the per-lane edge comparison with its verdict |
| `MW/D32/DSP/SHARC/loadlogic.sh` | `shipping` → `d02d83b3cc22`, `driveall` → `943f27966c28`; `shipping-s82` and `driveall-pre85` keep the older records resolvable |
| `MW/D24/DSP/s85/tools/` | `s85_gate1.sh` (both edges, both rail states), `s85_gate2.sh` (the two-sided reading, parameterised by bitstream) |

### The bitstreams built and flashed today

Every one flashed FLASH-OK on attempt 1 with its design ID read back and
MATCHED before any reading was taken.

| artifact | design ID | LE | Fmax | what it was for |
|---|---|--:|--:|---|
| `dsp4_logic_adwit.f2f33d97f578` | `3d97f578` | 882 | 62.76 | gate 1, both edges, both rail states |
| `dsp4_logic_adrt_adwit.43ec02c13e1a` | `02c13e1a` | 885 | 68.61 | S85-5, the retimed lanes |
| `dsp4_logic_adcdc_adwit.3490d03fcc18` | `d03fcc18` | 882 | 63.00 | S85-6, the mic lanes fed from the codec |
| `dsp4_logic_laneid_adwit.12f4fd1cbfc1` | `fd1cbfc1` | 866 | 67.76 | S85-7, every pin names itself |
| `dsp4_logic_driveall.943f27966c28` | `27966c28` | 888 | 70.63 | the S82 capacity row, re-taken |
| `dsp4_logic.d02d83b3cc22` | `83b3cc22` | 882 | 67.44 | **the adopted shipping label** |

`f2f33d97f578` is the one artifact of the six that is NOT in the tree, and
that is said here rather than left to be noticed. It was built before S85-11
moved `CFG_BITS` into the hash and before the witness went unconditional, so
it does not rebuild from HEAD at all — neither switch it was built with still
exists — and it was removed rather than kept as a file nothing can reproduce.
**The gate 1 reading is therefore re-taken on the adopted shipping label**,
which can carry it precisely because the witness now ships, and those numbers
are the ones the record rests on. The `f2f33d97f578` run is kept as raw
output in `data/edges-rails-down.txt` and `data/edges-rails-up.txt` and agrees
with the re-take.

The other three diagnostics do not rebuild from HEAD either, for the same
reason, and each says so in its own manifest with what it was for and which
reading was taken on it. Their function IS reproducible at HEAD from their
remaining switch alone (`AD_RETIME=1`, `AD_FROM_CDC=1`, `LANE_ID=1`), because
the witness they also carried is now in every build.

---

## Handback — the unit as found

**GATE 1, RE-TAKEN ON THE ADOPTED SHIPPING BITSTREAM**, rails up and the 595
at `0xFC`, three knocks a bank, every one of the seven frame counters
advancing across all three:

| lane | sample: ones / toggles | launch: ones / toggles | Δ toggles |
|---|---|---|---|
| `ad[0]` | 100 / 26 | 96 / 26 | **0** |
| `ad[1]` | 96 / 50 | 96 / 50 | **0** |
| `ad[2]` | 95 / 48 | 95 / 48 | **0** |

(medians across the three knocks; `ad[0]`'s `ones` scattered 96–101 on the
sample bank against a flat 96 on the launch bank, which is the content drift
S85-1 describes — `toggles` did not move by one count on any lane.) The
shipping bitstream carries the witness, which is what made this re-take
possible at all, and it reproduces gate 1 on the artifact the bench is left
holding.

The unit is as found:

- **the adopted shipping bitstream on the part, read back after the last
  flash**: `design_id 32'h83b3cc22  cfg_bits 16'h0010  SHIPPING`
- 595 SAFE image `0x01` restored and **VERIFIED 200/200** after the last
  reading
- AN_EN (GPIO26) `lo`, CS_M (GPIO27) `ip pu` — both read back, not assumed
- `matrix-app` restarted and **active**
- `defs.lock` unmoved, no matrix regenerated (`check-contract-drift.sh`
  clean), `check_bench_pins.sh` **canonical everywhere**
- one DSP image built — the `s85d24` capacity arm, in its own staging path,
  never `~/dspboot` — and its rows are in `MW/D32/DSP/SHARC/goldens/`

---

## 🟡 Notes for the hub

**S85-N1 — the witness ships at +361 LEs, and half of that is now answerable
by a re-flash.** The ruling that made it unconditional was taken when the
witness was three lanes on one edge (+174 LEs). S85 doubled it to six banks to
measure the launch phase, and that question is now answered — the two edges
agree, in both rail states, on all three lanes. Shipping the second bank for
ever costs the other ~187 LEs and 28 points of a 1,270-LE part in total. The
hub may want the shipping form to be the three sample-edge banks with the
launch bank behind a switch; S85 has implemented the ruling as written and
raises the choice rather than taking it quietly.

**S85-N2 — the next session is a DSP-side session, not a LOGIC one.** S85-8
puts the fault in chip 1's RX path for sport 0/1/2 and the CPLD is out of it.
The `_laneid` bitstream is the instrument that session wants on the part: with
every pin naming itself, any change to the SPORT/SRU/lane binding is read back
as "IN_01 now says pin 0 slot 0" or it is not read back at all. It costs 866
LEs and is built from `LANE_ID=1`.

**S85-N3 — S84's findings were never copied into `findings.md`.** They are in
`MW/D24/DSP/s84/mic-lanes.md` and nowhere else. Said here because the file's
own header says it carries the findings of dispatched sessions and a reader
searching it for S84-4 will not find it.
---
