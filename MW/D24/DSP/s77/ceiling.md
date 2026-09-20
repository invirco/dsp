provenance: AI-drafted 2026-09-19 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S77 — the driven ceiling, measured on the rev C unit

Bench session. The unit was booted, flashed, configured and driven; no hands,
no rails, no hardware change. The hub's rulings were taken as given:
**786.432 MHz is not a live option** (PW 2026-08-24, KSWZ10 confirmed), so
every figure below is against the 983.04 MHz budget, S76-6 is not a blocking
finding, and the 786 column comes out of the published scoreboard. Arm 4 of
S76 §6 was not run.

---

## 0. Outcome in one paragraph

**PW's standing question is answered YES with more headroom than it had, and
the configuration that ships is further from fitting than the record said.**
With the pairing rung in the graph, chip 1 at 32 channels reads **76.00 /
76.02 % of budget — margin +24.0 points**, zero missed blocks, strip cost
**469–472 cycles/sample**, **42.4 channels fit**; chip 2 reads 85.79 / 85.90 %
for **+14.1 points**. S76 quoted +22.0 from the 2026-09-11 rows, so nine days
of S65/S71/S74/S75 did not eat the margin — it grew. The shipping
configuration, on the same boots and the same stimulus, is **164.10–164.58 %
at 32 channels, −64.1/−64.6 points, 19.3 channels, two blocks in five missed**
— six points worse than the record's −58.2. **The S76 code-pool landing costs
1.1–2.0 points of chip 1 driven**, which is the first time mask 15 has been
priced on the part, and **nine days of graph growth cost chip 1 3.6–4.6 points
and chip 2 10.5 points at D24, the two boots agreeing to 54 cycles.** Getting
any of that took repairing the instrument first: **four bench-state
assumptions and a lost mirror field**, one of which had the part being driven
at 2 LSB while the script believed it was at full scale. Every row here is
driven with the regime proved on both chips, the bitstream identified from the
part, the stimulus level measured rather than assumed, and the 786.432 MHz
column gone.

---

## 1. The instrument was broken, and fixing it was most of the night

**Every driven row taken in the first three hours came back with the regime
NOT PROVEN, and the reason was two bits.** This section is first because it
is the part of the session that transfers: the bar the whole capacity record
stands on had three independent faults in it, all three of them the same
shape — a bench-state assumption baked into a script — and none of them was
visible from the desk.

### 1.1 `input_patch.json` was deployed by nothing (S77-1)

The first driven arm of the session died at its first boot:

```
ERROR: no input_patch.json for d24 (staged next to dsp4_config.py, or at
MW/D24/DSP/input_patch.json in the repo tree)
```

`dsp4_config.py` loads the input patch — which strip takes which RX cell —
from a file beside itself. **Not one script in this tree has ever deployed
that file.** Every arm ran on whatever copy happened to be sitting in
`/home/app/dspboot`, and on 2026-09-19 there was none at all. That is the
benign end of it. The other end is that the patch has been GENERATED from
`defs/products/d24/inputs.csv` since S59 and has changed twice since (S72,
S74c), so a bench that did hold a copy was applying an input patch nobody
could name — the S10-9 stale-symbol-map trap, one file along, in a data file
instead of a map.

Fixed in two places: `capacity.sh` stages it into the arm's own directory
beside `dsp4_config.py` (it is part of the arm's definition), and
`bench_lock.sh`'s `bench_deploy_link_tools` — which every bench script in
the tree already sources — refreshes the `/home/app/dspboot` copy, which is
where every other script will find it.

### 1.2 The stimulus device was addressed by card INDEX (S77-2)

With the patch staged, the first driven row died differently:

```
drive_audio: aplay REFUSED hw:0,1
  aplay: main:850: audio open error: No such file or directory
```

`drive_audio.sh` had `DEV=hw:0,1` written into it since S17. The CM4 had come
up with its two `vc4-hdmi` cards at 0 and 2 and `dsp4pcm` at 1, so `hw:0,1`
addressed an HDMI card's nonexistent second device. Nothing about the card,
the overlay, the bitstream or the DSP had changed: **ALSA card order is not
stable across boots.** `tools/pi/dsp4_knownword.py` already carried this
exact lesson in a comment — "BY CARD NAME, NOT INDEX. The card index moves
with what else probed first" — and the capacity instrument had not learned
it. Now `DEV=hw:CARD=dsp4pcm,DEV=1`, and the index never appears.

### 1.3 The stimulus was full scale into a path that multiplies by two (S77-3)

With the stream playing, every driven row still read the cheap branch:

```
DRIVEN REGIME: 15 of 48 dynamics envelopes live on chip 1
REGIME NOT PROVEN
```

and chip 1 came in at 90.3 % of budget at D24 where the record says 118.9 %.
Fifteen "live" envelopes were reading 0.000003. The dynamics were on their
cheap branch and the row was a silence row wearing a driven label — which is
precisely the fault S19 built this instrument to prevent, one layer below
where the instrument was looking.

**Measured, on the part, rather than reasoned about.** Four DC words played
into the CM4's playback device, chip 1's SPORT RX DMA buffer read straight
back off the part:

| played by the CM4 | read at chip 1's RX DMA buffer | |
|---|---|---|
| `0x40000000` | `0x80000000` | `<< 1` |
| `0x10000000` | `0x20000000` | `<< 1` |
| `0x00100000` | `0x00200000` | `<< 1` |
| `0x00000004` | `0x00000008` | `<< 1` |

**The DSPA lane path carries what the CM4 plays, exactly, shifted one bit
left.** `drive_audio.sh` played a square at `(1<<31)-1`, so every sample
wrapped: `0x7FFFFFFF << 1` is `0xFFFFFFFE` and `-0x7FFFFFFF << 1` is
`0x00000002`. The part was being driven at **2 LSB**, which is silence.

Three things were ruled out on the way, each with a measurement, and they are
worth keeping because they are the checks the next session will want:

* **The CPLD is the one it says it is.** Played `{0xD5D51D1D, 0x2A2AE2E2}`
  and captured the design-ID reply: `design_id 0x62d98a4d`, `cfg 0x0020`
  (`drive_all`). That is `dsp4_logic_driveall.14df62d98a4d` answering from
  the part.
* **The CM4 → CPLD link is bit-exact.** `dsp4_knownword.py` on the `pisel`
  bitstream: `in 0x00001000 -> out 0x00001000 ... = in << 0`, all three
  words, 86,342 of 86,342 frames. **A `pisel` loop cannot see a shift on the
  outbound leg** — the return leg applies the inverse — but the design-ID
  readback can, and does: the CPLD matched a 64-bit magic word bit for bit,
  so the outbound leg is exact too.
* **It is not the bitstream base.** Both `driveall` (`14df62d98a4d`, post
  S34/S36) and `driveall-s36` (`907492a607bd`, the pre-merge equivalent of
  the retired `e13b5dec84e0`) show the same shift and the same 2-LSB wrap.

**Where the `<< 1` comes from is NOT settled by this session** and it is
logged as an open question below. What it is not: a bitstream regression, a
link fault, or anything the DSP firmware can see — the DSP receives a clean,
exactly-scaled copy of what is played, one bit high.

The fix taken tonight is the stimulus amplitude: a quarter of full scale
(`0x20000000`, −12 dBFS at the CM4, **−6 dBFS at the part** after the shift),
which is the level `dsp4_dyn_witness.py` already predicts its compressor
reading from. The witness on the repaired instrument:

```
strip  gate_env      gate_gain            comp_env      comp_gain
    1   0.000000  0x10000000 OPEN   0.500000  0x04C8FBF4 -10.48 dB GR
    ...
gate OPEN 8 / SHUT 0, comp ACTIVE 8 / unity 0, unreadable 0
SIGNAL PRESENT ON ALL 8 STRIPS — dynamics on the real path
```

`comp_env` reads **0.500000** — exactly −6 dBFS, the shift confirmed a third
time — and the gain reduction is **−10.48 dB** against the −10.5 dB the tool
predicts from the shipping compressor's own constants. The polynomial pair
ran and produced the arithmetically correct answer.

**What this costs in comparability.** Every dynamics node in the driven
configuration sits at a −60 dB threshold, so 18 dB of stimulus either way
does not change which BRANCH the graph is on, and the branch is what the row
measures. It does change the compressor's gain-reduction arithmetic, so rows
taken at −6 dBFS and rows taken at 0 dBFS are not interchangeable to the
cycle. Every row in this report is at −6 dBFS at the part and says so.

### 1.4 What the instrument now is

One command per arm, and the command is the arm's definition:

```
ARM=<name> PRODUCT=<d24|d32> ./capacity.sh --driven
```

with the LOGIC bitstream `dsp4_logic_driveall.14df62d98a4d` on the CPLD
(`./loadlogic.sh driveall`), identified from the part by its design-ID
readback, and the CM4 playing a 400 Hz square at `0x20000000` peak. Three
rows per boot, two boots per arm and product:

* **A — silent, default config.** The configuration the product boots with,
  no signal. Comparable with every figure in the record from before S19.
* **B — silent, loaded config.** Every bus assign and send open, every
  dynamics node on at a −60 dB threshold, no signal. **B − A is what the
  CONFIGURATION costs.**
* **C — DRIVEN, loaded config.** The same, with the stimulus on and the
  regime proved on both chips before the row is taken. **This is the
  product number.**

Everything is read off the part: the budget comes from the CGU words and the
measured core clock on that boot, the build configuration from the image's
own `DIAG_BUILD_CFG`/`CFG2`, and a fresh symbol map is staged with every arm.

---

## 2. The arms

Three configurations, one image each, both products, two boots each. The
third is the one PW asked to be told the moment it is measured.

| arm | what it is | `DIAG_BUILD_CFG2` on the part |
|---|---|---|
| `s77ship` | **the shipping configuration TODAY** — `shipping.config` at HEAD, i.e. the S76 landing at `DSP4_SHARED_KERNELS=15` | `0xE2018264` |
| `s77shk0` | the same tree with `DSP4_SHARED_KERNELS=0` — the **mask-0 control**, switch for switch what `cap-s19blk-*` was on 2026-09-10 but for `DSP4_TALK_INVERT` | `0xE2010244` |
| `s77pair` | **the pairing configuration TODAY** — `STRIP_FUSED`, `SIMD_DYN`, `SIMD_GRAPH`, `SIMD_STRIPS`, `C2_BQ_GRAPH`, `GATE_LINTHR`, `DYN_LUT`, `SHARED_KERNELS=15` | `0xE2019E6F` |
| `s77ship36` | `s77ship`'s image again, on the **pre-S34/S36 `driveall`** bitstream — the bitstream control | `0xE2018264` |

The decomposition the two deltas give:

* `s77ship − s77shk0` is **what the S76 code-pool landing costs in cycles**,
  on today's tree, driven, with nothing else different (gate 1);
* `s77shk0 − cap-s19blk` is **nine days of graph growth**, switch for switch,
  with the code-pool lever held at the value the 2026-09-10 rows were taken
  at (gate 2);
* `s77pair` against `cap-shk15` is **whether +22.0 points at 32 still holds**
  after S65/S71/S74/S75 (gate 3).

**`DIAG_BUILD_CFG2` can tell mask 0 from mask 15 and cannot tell mask 3 from
mask 15** — the word carries bits 0 and 1 of a four-bit field (S27-3) — so
the two shipping arms here are distinguishable from the part, and the
image md5 is still what identifies an arm in general. S75-13 stands.

---

## 3. Gate 1 — the shipping configuration at mask 15, driven

`s77ship`, `DIAG_BUILD_CFG2 0xE2018264`, images `84c79513…` (356,740 B) /
`bb2a7c6e…` — byte for byte the pair S76 built, rebuilt tonight and matching
its md5s. Every row driven, regime PROVEN on both chips on all four boots
(chip 1 48 live / 16 masked at D24 and 64 / 0 at D32; chip 2 28 / 4 and
32 / 0).

| | chip 1 | chip 2 | blocks missed |
|---|--:|--:|--:|
| D24 r1 | 405,337 — **123.70 %** | 425,242 — **129.77 %** | 19.04 % / 22.94 % |
| D24 r2 | 405,240 — **123.67 %** | 425,493 — **129.85 %** | 19.04 % / 22.94 % |
| D32 r1 | 539,302 — **164.58 %** | 513,519 — **156.71 %** | 39.03 % / 36.13 % |
| D32 r2 | 537,731 — **164.10 %** | 514,096 — **156.89 %** | 39.03 % / 36.13 % |

The two products differ by eight strips on chip 1, so the slope is measured
rather than modelled: **16,561–16,746 cycles/block per strip = 1,035–1,047
cycles/sample**, with 3,442–7,767 cycles/block of everything else.

| chip 1, the configuration that ships | at 983.04 MHz |
|---|--:|
| budget, block 16 | 327,680 cyc/block |
| 32 channels | 164.10–164.58 % |
| **margin remaining at 32** | **−64.1 / −64.6 points** |
| channels that fit | **19.3–19.4** |

| chip 2, the configuration that ships, D32 | at 983.04 MHz |
|---|--:|
| measured | 156.71–156.89 % |
| **margin remaining** | **−56.7 / −56.9 points** |

**The shipping configuration does not fit either product, and it is further
over than the record said.** At D24 — the product this unit is — chip 1 misses
**one block in five** and chip 2 nearly one in four. At D32 chip 1 misses two
in five.

### 3.1 What the S76 landing costs, driven, on the part

`s77ship − s77shk0`: the same tree, the same boot ladder, the same stimulus,
one switch different. Chip 2 carries no strip COMP, TUBE, GATE or FILT, so its
column is the instrument's own noise and is quoted for that reason.

| | chip 1 | chip 2 |
|---|--:|--:|
| D24 r1 | **+3,578 cyc/block (+1.10 pts)** | −84 (−0.03) |
| D24 r2 | **+3,769 (+1.15)** | +197 (+0.06) |
| D32 r1 | **+6,451 (+1.97)** | −6,669 (−2.04) |
| D32 r2 | **+4,653 (+1.42)** | +1,032 (+0.31) |

**Mask 15 costs chip 1 between 1.1 and 2.0 points of budget, driven.** That is
the measured price of 95,648 bytes of reclaimed program memory, and it is the
first time it has been measured at mask 15 rather than mask 3 — S76 could only
price mask 3 (+0.75 to +1.34 points, `cap-s19blk` against `cap-s19s18`) and
recorded masks 3→15 as inside run-to-run noise. Tonight's figure is consistent
with that: mask 15's price and mask 3's price overlap. **Chip 2's spread
(−2.04 to +0.31 points on an image that differs in two stamp bytes) is the
instrument's resolution**, and nothing below is quoted tighter than it.

## 4. Gate 2 — the shipping configuration today, against 2026-09-10

`s77shk0` is the mask-0 control: `DIAG_BUILD_CFG2 0xE2010244`, images
`10a41300…` / `e88a7a43…` — **byte-identical to S74c's pair**, rebuilt tonight
and matching its md5s, and switch for switch what `cap-s19blk-*` was on
2026-09-10. So the difference between them is nine days of graph growth and
nothing else in the build. All eight regime snapshots PROVEN.

| | chip 1 | chip 2 | blocks missed |
|---|--:|--:|--:|
| D24 r1 | 401,759 — **122.60 %** | 425,326 — **129.80 %** | 18.36 % / 22.94 % |
| D24 r2 | 401,471 — **122.52 %** | 425,296 — **129.79 %** | 18.36 % / 22.94 % |
| D32 r1 | 532,851 — **162.61 %** | 520,188 — **158.75 %** | 38.51 % / 36.85 % |
| D32 r2 | 533,078 — **162.68 %** | 513,064 — **156.58 %** | 38.51 % / 36.13 % |

### 4.1 Nine days, measured

`s77shk0 − cap-s19blk`, same switches, same instrument, same regime:

| | chip 1 | chip 2 |
|---|--:|--:|
| D24 r1 | **+12,181 cyc/block (+3.71 pts)** | **+34,614 (+10.56)** |
| D24 r2 | **+11,797 (+3.60)** | **+34,560 (+10.54)** |
| D32 r1 | **+14,512 (+4.43)** | **+52,282 (+15.95)** |
| D32 r2 | **+14,932 (+4.55)** | **+40,656 (+12.42)** |

**The growth is chip 2's.** Chip 1 took 3.6–4.6 points in nine days; chip 2
took **10.5 points at D24 with the two boots agreeing to 54 cycles**, and
12.4–16.0 at D32 where its own run-to-run spread is wider. S76 proved from the
images that the cue bus, the RTA and the memory pool cost the shipping image
**zero bytes** — they are all behind switches at 0 — and that the codec lanes
are four unconditional nodes at 504 bytes. **That accounting was right about
bytes and says nothing about cycles**, and the cycles are real: something
landed on chip 2 between 2026-09-10 and 2026-09-19 that costs it a tenth of
its budget at D24. S71's codec-return lanes and S74's talkback polarity are
both chip-2-side and both unconditional. **This session measured the total and
did not decompose it**; the decomposition is a bisect over nine days of
commits with one driven D24 boot pair each, which is a session of its own.

### 4.2 The stimulus level is not what the delta is made of

The 2026-09-10 rows were taken with `drive_audio.sh` playing a full-scale
square and tonight's are at a quarter of that, so the two sets are 6 dB apart
at the part. (**If the one-bit shift had been present on 2026-09-10, those
rows would have been driven at 2 LSB and their regime could not have proved
— it did prove, 48 of 48** — so the shift appeared after 2026-09-11.)

**So the sensitivity was measured rather than argued away.** The same image
— `s77shk0`, the mask-0 control — the same boot ladder, the stimulus 6 dB
lower again (`AMP=268435456`, −12 dBFS at the CM4, −12 dBFS at the part after
the shift). Regime PROVEN, 48 of 48 and 28 of 28:

| D24, driven | chip 1 | chip 2 |
|---|--:|--:|
| −6 dBFS at the part (r1 / r2) | 401,759 / 401,471 | 425,326 / 425,296 |
| −12 dBFS at the part | 401,439 | 425,577 |
| **difference** | **−320 / −32 cyc/block (−0.09 / −0.01 pts)** | **+251 / +281 (+0.07 / +0.08 pts)** |

**Six decibels of stimulus is worth a tenth of a point, which is less than
the instrument's own boot-to-boot spread.** The graph is on the same branch
at both levels and the branch is what costs. So §4.1's +3.6 to +4.6 points on
chip 1 and +10.5 on chip 2 are the firmware's, and so is §5.1's improvement
on the pairing arm. Neither is an artefact of the level this session had to
drive at.

## 5. Gate 3 — the pairing configuration today

**This is the number PW asked to be told the moment it is measured, and it is
better than it was.** `s77pair`, `DIAG_BUILD_CFG2 0xE2019E6F`, images
`723d1c9c…` (426,376 B) / `e52d4f51…` (407,672 B). Both boots, regime PROVEN
64 of 64 on chip 1 and 32 of 32 on chip 2, **zero missed blocks on either
chip on either boot**.

| | chip 1 | chip 2 | blocks missed |
|---|--:|--:|--:|
| r1 | 249,026 — **76.00 %** | 281,463 — **85.90 %** | 0 / 0 |
| r2 | 249,094 — **76.02 %** | 281,121 — **85.79 %** | 0 / 0 |

Slope, measured from the eight-strip difference on chip 1: **7,504–7,555
cycles/block per strip = 469–472 cycles/sample**, with 7,326–8,906
cycles/block of everything else.

| chip 1, the pairing configuration | at 983.04 MHz |
|---|--:|
| 32 channels | 76.00 / 76.02 % |
| **margin remaining at 32** | **+24.0 points** |
| channels that fit | **42.4–42.5** |
| strip cost | **469–472 cycles/sample** |

| chip 2, the pairing configuration, D32 | at 983.04 MHz |
|---|--:|
| measured | 85.79 / 85.90 % |
| **margin remaining** | **+14.1 / +14.2 points** |

**The strip came in under the projection again and under S76's own figure**:
535 was the projection, S76 measured 476–484, tonight it is **469–472**.

**PW's standing question — 32 basic strips real-time in one ADSP-21564, with
headroom — is MET, and the headroom grew.** S76 quoted +22.0 points from the
2026-09-11 rows; tonight, after S65, S71, S74 and S75 have all landed, the
same switch positions read **+24.0**. Chip 2 went from +8.9/+9.0 to
+14.1/+14.2.

### 5.1 The pairing arm got FASTER while the shipping arm got slower

`s77pair − cap-shk15` (2026-09-11), the same switches:

| | chip 1 | chip 2 |
|---|--:|--:|
| D32 r1 | **−6,565 cyc/block (−2.00 pts)** | **−16,758 (−5.11)** |
| D32 r2 | **−5,936 (−1.81)** | **−17,390 (−5.31)** |

Set beside §4.1 — the shipping path **+14,512 to +14,932 on chip 1** and
**+40,656 to +52,282 on chip 2** over the same nine days — these two cannot
both be "what the graph grew by". **The two paths differ in how the dynamics
are computed**: the shipping arm runs the scalar compressor and gate, whose
cost depends on the signal, and the pairing arm runs `SIMD_DYN` with
`DYN_LUT`, which is table-driven and should not care. The level control
below is what separates them.

## 6. The bitstream control — S36-2 closed for the capacity bar

`loadlogic.sh`'s own warning is that the three instrument bitstreams moved
base at S37 and "no bar taken on them transfers until it is re-taken once".
Every row above is on `dsp4_logic_driveall.14df62d98a4d`; every row they are
compared against was taken on the retired `e13b5dec84e0`. So the **same
image** — `s77ship`, staged again under a second arm name, the md5s printed
to prove it — was re-taken on `driveall-s36` (`907492a607bd`), the pre-merge
equivalent of the retired one. Both boots, regime PROVEN 64/64 and 32/32.

| D32 | chip 1, old base → new | chip 2, old base → new |
|---|--:|--:|
| r1 | 537,850 → 539,302 — **−0.44 pts** | 512,813 → 513,519 — **−0.21 pts** |
| r2 | 537,495 → 537,731 — **−0.07 pts** | 513,345 → 514,096 — **−0.22 pts** |

**The S34/S36 logic rebase costs the capacity number nothing measurable** —
every difference is smaller than the instrument's own run-to-run spread
(§3.1 puts that at about 2 points on chip 2). So the nine-day delta in §4.1
is the firmware's, not the bitstream's, and the driven capacity bar now
carries a row taken on the current artifacts. **S36-2 is closed for this
bar**; the 82-sample latency bar still has to be re-taken on its own.

**And the shift is not the rebase either.** The one-bit left shift of S77-3
is present on both bases, measured directly, so whatever introduced it is
not in the difference between these two bitstreams.

## 7. Gate 4 — the HyperRAM probe on an unmodified rev C card

The optional gate, S75 §6.4. **Step 1 passes and step 2 does not run on this
card, which is itself the answer to S75's third bench question.**

### 7.1 Step 1 — PASS, from the part's own mouth

`dsp4_extram.py --expect-rev-c` on the shipping image (`84c79513…` /
`bb2a7c6e…`), both chips:

```
chip 1: raw CFG3  0x00000000   raw STAT  0x00000000
        backend L2 · present no · fail code 0 (none) · pool lines 0
        ID0/ID1 0x00000000 · XFERS 0 · STALLS 0
        PASS: case A (built DSP4_EXTRAM=0): CFG3 and EXTRAM_STAT both read 0
              -- unmapped, exactly as expected for today's shipping image
chip 2: ... PASS, identical
```

**The S75 diagnostic addresses are inert on the image that ships, proved on
the part rather than from an md5.** That is the check S75 §6.4 step 1 asked
for, and it closes the "did S75 change the shipping image" question from the
part rather than from an argument.

### 7.2 Step 2 — the `DSP4_EXTRAM=1` image does not bring the link up

The EXTRAM arm (`fd5094e6…` / `50b3dec4…`, built clean this session, 0 errors)
was staged and booted **six times across two runs**. Every attempt:

```
CHIP CHECK FAILED: link answers as CHIP no answer ([Errno 16] Device or
resource busy), expected 1
ERROR: could not read the S75 registers over SPI (SPI_RDY never asserted --
DSP held in reset, not booted, or the RDY polarity is inverted)
```

**Six failures on the EXTRAM image against zero on the shipping image, in the
same script, in the same session, minutes apart.** The host-side symptom is
`dsp4_boot.py` not completing and keeping `/dev/spidev0.0` open, which is what
a DSP that never asserts SPI_RDY looks like from the CM4.

**What this is and is not.** It is consistent — to the point of being the
textbook symptom — with **S75-1**: `_pool_init` moves Port A to the xSPI0 mux
function, SPI2 is the parameter link *and* the slave-boot port, and both go
with it. S75 §6.4 step 3 says in as many words that "this is the step where
finding S75-1 becomes real". **It is not proof**: a host-side "device busy"
is one layer above the link, this session did not put a scope on SPI_RDY, and
the first of the six failures had a leftover process of its own that could
have started the cascade. What can be said without stretching is that **the
EXTRAM image would not boot to a usable parameter link on this card, six
times out of six, and the shipping image did first time.**

**The card recovered.** The restore in §10 booted the shipping pair and
configured both chips on the first attempt afterwards, so nothing was left
stuck and the failure is in the EXTRAM image's own bring-up, not in the card.

**For the next session:** this wants a scope or a logic analyser on SPI_RDY
and Port A during an EXTRAM boot, not another software retry. If S75-1 is
what this is, the fix is the hardware question already with the hub, and no
amount of bench retrying will move it.

---

## 7a. The record

Every row this session took is a recorded capacity row in
`MW/D32/DSP/SHARC/goldens/`, written by `tools/pi/dsp4_capacity.py`, carrying
the measured core clock, the budget derived from the CGU words on that boot,
the image's own `DIAG_BUILD_CFG`/`CFG2` and the block/overrun counts. Regime
snapshots sit beside each one and are scored by `tools/dsp/regime_verdict.py`.

| arm | images (md5, first 8) | what it is | rows |
|---|---|---|---|
| `cap-s77ship-*` | `84c79513` / `bb2a7c6e` | the shipping configuration today, mask 15 | d24 r1/r2, d32 r1/r2 |
| `cap-s77shk0-*` | `10a41300` / `e88a7a43` | the mask-0 control (byte-identical to S74c) | d24 r1/r2, d32 r1/r2 |
| `cap-s77pair-*` | `723d1c9c` / `e52d4f51` | the pairing configuration today | d24 r1/r2, d32 r1/r2 |
| `cap-s77ship36-*` | `84c79513` / `bb2a7c6e` | the shipping image on the pre-S34/S36 `driveall` | d32 r1/r2 |
| `cap-s77lvl-*` | `10a41300` / `e88a7a43` | the mask-0 control 6 dB lower | d24 r1 |

Three rows per boot (A silent-default, B silent-loaded, C driven); the tables
above quote row C. **Every regime snapshot of every boot reads PROVEN** — 48
live / 16 masked on chip 1 at D24, 64 / 0 at D32, 28 / 4 and 32 / 0 on chip 2.

**One leg had to be re-taken and the reason is worth recording**: `s77pair`'s
D24 leg died with `NCH:/home/app/dspcap/s77pair/: No such file or directory`,
which is `capacity.sh` being **edited while a background invocation was
executing it** — bash reads a script by byte offset, so a file that grows
under a running shell puts it in the middle of a word. The image had already
built; the leg was re-run from it unchanged. **Do not edit a bench script
while an arm is running.**

---

## 8. Findings

**S77-1. `input_patch.json` is deployed by nothing, and has been generated
from `defs` since S59.** `dsp4_config.py` reads the input patch — which strip
takes which RX cell — from a file beside itself, and no script in this tree
staged it. The bench had no copy at all on 2026-09-19, so the first driven arm
could not configure. The dangerous half is the other one: the file has changed
at S72 and S74c, so any bench that DID hold a copy was applying an input patch
nobody could name. Fixed in `capacity.sh` (staged with the arm, because it is
part of the arm's definition) and in `bench_lock.sh`'s
`bench_deploy_link_tools`, which every bench script already sources.

**S77-2. The stimulus device was addressed by ALSA card index.**
`drive_audio.sh` carried `DEV=hw:0,1` from S17. The CM4 enumerated its two
`vc4-hdmi` cards at 0 and 2 with `dsp4pcm` at 1, so `aplay` addressed an HDMI
card's nonexistent second device and the driven ladder exited 4. Nothing about
the card, overlay, bitstream or DSP had changed. `tools/pi/dsp4_knownword.py`
already carried this exact lesson in a comment. Now
`hw:CARD=dsp4pcm,DEV=1`.

**S77-3. 🔴 THE DSPA LANE PATH SHIFTS THE STIMULUS ONE BIT LEFT, AND A
FULL-SCALE STIMULUS WRAPPED TO 2 LSB.** Measured on the part with four DC
words: `0x40000000 → 0x80000000`, `0x10000000 → 0x20000000`,
`0x00100000 → 0x00200000`, `0x00000004 → 0x00000008`. `drive_audio.sh` played
`(1<<31)−1`, which wraps to `0x00000002` / `0xFFFFFFFE` — so every driven row
taken before this was found was a **silence row wearing a driven label**, the
exact fault S19 built the instrument to prevent. The regime proof caught it
every time (NOT PROVEN, 15 of 48 envelopes "live" at 3e-6); what nobody had
was a reason. Worked around by dropping the stimulus to a quarter of full
scale (−6 dBFS at the part). **Where the `<< 1` comes from is NOT settled**:
it is present on `driveall` `14df62d98a4d` AND on the pre-S34/S36
`907492a607bd`, and absent from the CPLD-internal `pisel` loop, which returns
`in << 0` on all three test words. It is a question for the LOGIC side, and it
is below: S77-Q1.

**S77-4. `dsp4_logic_id.py` played and recorded on the same ALSA device**,
which is correct under `dsp4-pcm-duplex` (one device, both directions) and
impossible under `dsp4-pcm-slave`, which this bench stands on: device 0 is
capture-only. So `loadlogic.sh --id` reported "no reply: nothing in the
capture carried the 0xD594 marker" against a CPLD that answers its design ID
perfectly — the one tool that can identify a bitstream from the part gave the
same answer for "wrong bitstream" and "wrong device". Fixed by resolving both
devices from what ALSA exposes. With it, the CPLD identified itself:
`design_id 0x62d98a4d`, `cfg 0x0020` (`drive_all`).

**S77-5. 🔴 THE SHIPPING-CONFIG MIRROR HAD LOST A FIELD, AND THE CHECK THAT
EXISTS TO CATCH THAT PASSED.** `check_shipping_config.sh` announced
`DIAG_BUILD_CFG2 0xE2010244` for an image the part reads back as
`0xE2018264`. S76 landed `DSP4_SHARED_KERNELS=15` in `shipping.config` and did
not mirror it in `tools/pi/dsp4_buildcfg.py`, so `--expect-shipping` would
have scored the **actual shipping image** as a mismatch. Four more CFG2 fields
(`DYN_LUT`, `GATE_LINTHR`, `C2_BQ_GRAPH`, `BQ_SIMD_PIPE`) were missing the
same way; they are all 0 today, which is the only reason they never showed.
The check passed because a key present in only one of the two copies was
allowed — the same hole as S11-1 and S74-2, for the third time. **Closed
structurally**: `tools/dsp/cfg_words.py` owns the list of fields each word
carries, and a field the word carries which the mirrors do not is now drift.
Negative control: deleting the key again exits 1 with both messages.
`check_shipping_config.sh` now announces `0xE2018264`, which is what the part
reads.

**S77-6. 🔴 THE SHIPPING CONFIGURATION IS SIX POINTS FURTHER FROM FITTING
THAN THE RECORD SAID, AND THE GROWTH IS CHIP 2'S.** Driven, regime proved,
today: chip 1 at 32 channels **164.10–164.58 %, margin −64.1/−64.6 points,
19.3 channels fit**, two blocks in five missed at D32 and one in five at D24.
S76 quoted −58.2 from the 2026-09-10 rows. Decomposed against the mask-0
control: **the S76 code-pool landing costs 1.1–2.0 points** and **nine days of
graph growth costs chip 1 3.6–4.6 points and chip 2 10.5 points at D24** (the
two boots agreeing to 54 cycles) **and 12.4–16.0 at D32**. The stimulus level
is not what it is made of — 6 dB is worth a tenth of a point, measured.

**S77-7. THE 32-STRIP MINIMUM IS MET WITH MORE HEADROOM THAN BEFORE.** The
pairing configuration today: chip 1 **76.00 / 76.02 % at 32 channels, +24.0
points, 42.4–42.5 channels fit, 469–472 cycles/sample, zero missed blocks**;
chip 2 **85.79 / 85.90 %, +14.1/+14.2**. S76 read +22.0 and +8.9/+9.0 from
2026-09-11. **The rung got cheaper, not dearer, across S65/S71/S74/S75** —
−1.8 to −2.0 points on chip 1 and −5.1 to −5.3 on chip 2 — while the shipping
path got dearer over exactly the same nine days. The two paths differ in how
the dynamics are computed (scalar against `SIMD_DYN`+`DYN_LUT`), and the level
control rules out the stimulus as the explanation. **Why one improved while
the other regressed is not explained by this session** and is the first thing
a bisect should answer.

**S77-8. The S34/S36 logic rebase costs the capacity number nothing.** The
same image on `driveall` `14df62d98a4d` and on the pre-merge `907492a607bd`:
**−0.07 to −0.44 points**, inside the instrument's own spread. **S36-2 is
closed for the driven capacity bar** — it now carries a row taken on the
current artifacts. The 82-sample latency bar still has to be re-taken on its
own.

**S77-9. Six decibels of stimulus is worth a tenth of a point.** The mask-0
image, the same ladder, −6 dBFS against −12 dBFS at the part: chip 1
**−0.09 / −0.01 points**, chip 2 **+0.07 / +0.08**. The driven regime is a
BRANCH and the branch is what costs; the level within it does not. This is
what makes every comparison in §4 and §5 legitimate across the amplitude
change S77-3 forced.

**S77-10. 🔴 THE `DSP4_EXTRAM=1` IMAGE WOULD NOT BOOT TO A USABLE PARAMETER
LINK, SIX TIMES OUT OF SIX** — against zero failures on the shipping image in
the same script, the same session, minutes apart. Consistent with S75-1
(`_pool_init` takes Port A, and SPI2 is both the parameter link and the
slave-boot port) but **not proved**: the symptom is host-side. See §7.2 for
what the next session should put a scope on. The shipping image booted and
configured first time afterwards, so the card is fine.

**S77-11. `dsp4_buildcfg.py --expect-shipping` rejected every shipping image,
for a second reason.** With the mirror fixed (S77-5) the word matches, but the
decoder still compared the **two bits `DIAG_BUILD_CFG2` carries** against the
mirror's **15** — and 15 can never be read back, so the check reported "NOT
THE SHIPPING KERNEL CONFIGURATION" on the shipping pair with the part reading
the correct word. Found at the end of this session, on the restored unit.
Fixed: only the two bits the word carries are compared, and the message says
which two and that the image md5 identifies the rest. Negative control: a
mask-0 word still exits 4.

**S77-12. The hub's gate 6 quotes the pre-S76 word.** The dispatch asks for the
unit to be left with "DSP4_TALK_INVERT on (the D24 config word 0xE2010244)".
That word is `shipping.config` with `DSP4_SHARED_KERNELS` at 0. Today's
shipping image reads **`0xE2018264`**, and the difference is exactly the two
bits S76 landed. The unit was left on `0xE2018264` — talkback polarity is on
in both, in bit 29.

## 9. 🔴 For the hub

**S77-Q1 — where does the one-bit left shift on the DSPA lane path come
from, and is it in the product path or only in the instrument's?** The CM4's
playback arrives at chip 1's SPORT RX DMA buffer exactly and shifted one bit
left; it is on both `driveall` bitstream bases and absent from the
CPLD-internal `pisel` loop. The obvious candidate is justification — I2S puts
the MSB one bit clock after frame sync and left-justified does not, so a link
written as one and read as the other is off by exactly this much — and if
that is what it is, it is a property of the `drive_all` injection path and the
converters never see it. **That is a hypothesis and this session did not test
it.** The test is cheap and needs the analog side: put a known level in an
XLR, read the same RX word, and compare the scaling with the CM4 path. Until
somebody does, every driven capacity row in this record is taken on a
stimulus whose amplitude at the part is 6 dB away from where the script
thinks it is, and NO row taken before tonight says what amplitude it had.

Options, as the hub would want them:

1. **Take it as the instrument's own.** Land the amplitude as it now is,
   document the shift in `drive_audio.sh` (done), and re-take the S28/S29
   bars that quoted an amplitude. Cheapest; leaves the product question open.
2. **Test it against the analog path** on a session with hands at the bench —
   one XLR, one known level, one peek. Settles whether a D24's microphone
   inputs are 6 dB hot in the shipping image, which is not a question this
   record should leave open.
3. **Chase it in the HDL.** `shared/dsp4-logic/` single-sources the TDM slot
   map; if the justification is stated there, this is a read rather than a
   measurement.

**S77-Q2 — chip 2 grew by a tenth of its budget in nine days and nothing in
the record says what did it.** +10.5 points at D24 with the two boots
agreeing to 54 cycles, +12.4 to +16.0 at D32, on an image that is byte-for-byte
S74c's. S76's byte accounting was right and is not in contradiction: the cue
bus, the RTA and the pool are all behind switches at 0 and cost **zero
bytes**. Bytes were never the question for cycles. What is on chip 2 and
unconditional across those nine days is **S71's codec-return lanes** and
**S74's talkback polarity**; neither has been priced. **This is a bisect**,
about a dozen driven D24 boot pairs over 2026-09-10..19, and it is the
cheapest large number on the table — ten points of chip 2 is worth more than
any remaining code-pool lever.

**S77-Q3 — the pairing configuration is still unsigned, and it is now worth
88.7 points.** −64.6 against +24.0 at 32 channels, both measured on the same
night, on the same silicon, with the same stimulus. The three deviations to
sign are unchanged and all bounded: `DYN_LUT` at 0.0950 dB against a 0.1 dB
spec line, `GATE_LINTHR` at 0.0002 dB, and one verdict of twenty moving —
COMPRESSOR, numeric, 0.00518 dB. `STRIP_FUSED` alone is verdict-for-verdict
identical with three arms bit-exact. **Nothing this session found weakens the
case; the rung got cheaper.**

## 10. The unit, as it was left

1. **LOGIC**: `dsp4_logic.a1f6672af6c3` — the shipping bitstream, the state
   the bench lives in. `FLASH OK on attempt 1`.
2. **DSP pair**: the shipping configuration, `84c7951333e982204a38fe65e49d3fd6`
   / `bb2a7c6ea9e5d0caa419bc0b15a97f7c` — booted and configured for D24 on the
   first attempt, which is also what says the card was not left stuck by §7.2.
3. **The configuration the part reads back**: `DIAG_BUILD_CFG 0xCF45FF10`,
   `DIAG_BUILD_CFG2` **`0xE2018264`** on both chips, `CFG3` unmapped (normal
   for `DSP4_EXTRAM=0`). `DSP4_TALK_INVERT` is on, in bit 29. **The dispatch
   asked for `0xE2010244`, which is the pre-S76 word** — see S77-6.
4. **Audio on the talkback loop**: `dsp4_family_verify.py --families TALKBACK`
   — **`TALKBACK cells 8 · contract 4/4 · audio LIVE`**. The polarity flip is
   what the talkback work was about and the path passes audio with it on.
5. **`matrix-app`**: `active`, which is how the unit was found.
6. **`/home/app/dspboot` was NOT overwritten.** S76 deliberately did not
   deploy the reclaimed pair and `ldr/manifest.txt` is untouched; deploying it
   here would be a deployment decision this session was not asked to make. The
   pair the bench holds on disk is exactly the one it held at 22:43.

**One thing the record should carry about `ldr/manifest.txt`**: it names
`chip1.b4090de01d5d` / `chip2.bb2b24db8617` and then WITHDRAWS them — both are
unbootable, and it says in as many words that no replacement artifact has been
recorded. So "the shipping pair from `ldr/manifest.txt`" cannot be flashed;
what was flashed is the pair `shipping.config` at HEAD produces, which is the
S76 landing and the arm every gate-1 row here was taken on.
