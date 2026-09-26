provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S125 — the seven gain steps could not have worked, and 46 s off the automated set

Unit: MW-D24-2. Everything below was measured on the part unless it says
otherwise. The desk review this session was dispatched against is
`hub-speed-review-2026-09-26.md`, copied into this directory.

**Headline.** The review asked whether the gain steps could see a faulty
resistor. They could not, and not for the reason the review gave. There were
**three independent faults in series**, each of which on its own would have
made the seven gain steps meaningless, and none of which had ever been
measured:

1. **every gain step wrote the wrong byte of the 595 image** and drove some
   other input's preamp, or none at all;
2. **the strip meter it read cannot report a level 50 ms after a change** — it
   latches peaks and decays at 6.52 dB/s;
3. **the measurement node's level reading saturates above about −24 dBFS**, and
   the steps were driven at −12, where an element short by 6.552 dB reads
   1.649 dB low and passes.

All three are fixed and proved on the part: every one of the six elements,
killed in turn, now FAILs with the plain sentence, and a good input reads every
element to within 0.05 dB. **A step costs 223 ms.**

Separately, the automated set lost **46.7 s of test time** (229.3 → 182.6 s;
wall clock 265 → 207 s) with **identical verdicts** — 35 PASS / 1 FAIL /
15 NO DATA, twice before and three times after — and RUN ALL's dialogs went from a
2 s tick to a **9.5 ms median**.

---

## 1. The gain steps (dispatch item 1)

### S125-1 🔴 Every gain step addressed the wrong preamp

`defs/products/d24/inputs.csv` carries **two** position columns for each input
and they are different orders:

| | | |
|---|---|---|
| `chain_index` | the preamp's position along the physical daisy chain | MIC 5 → 9 |
| `send_pos` | its byte in the transmitted 25-byte image, zero-based | MIC 5 → 15 |

`tools/accept/gen_patch_paths.py` read `chain_index` and
`Analog.step_image()` used it to index the image that goes out of the shift
register. The tx byte is what the hardware sees.

**Measured** (`s125_map.py`): one position unmuted at gain 63 at a time, every
other channel muted, and the converter lane whose own preamp noise rose is the
answer — 53 dB of gain lifts an open mic input about 33 dB over this unit's
converter floor, so the map needs no lead and no oscillator.

```
position  1 -> lane 24  +34.55 dB   (next best 21  +1.72)
position  2 -> lane 12  +34.43 dB   (next best  8  +1.27)
...
position 16 -> lane  5  +34.46 dB   (next best 10  +1.52)
position 17..24 -> nothing above +2.5 dB
```

Sixteen positions light exactly one lane each; the other eight light nothing.
**That is the known depopulation and it is an independent check on the map**:
`MW/D24/HW/hardware-map.md:160` records MW-D24-2's missing front end as *panel
mics 1-4 and 13-16*, measured in S86 at −0.21 to +0.08 dB against 31.8-40.4 dB
for the other sixteen. The unlit lanes here are **1-4 and 13-16** and the lit
ones rise 31.7-34.7 dB. So lane number = panel MIC number, and the map is
right.

Against that map:

| | `send_pos + 1` | `chain_index` |
|---|---|---|
| matches the measurement | **16 of 16** | **0 of 16** |

And in the generated list, **14 of 14 gain-step inputs addressed a byte that
does not drive their lane** — six drove another input's preamp (MIC 7's step
wrote MIC 18's byte and vice versa; likewise 8↔17, 9↔20, …) and eight
addressed the bytes of the mics this unit has no front end for, so they moved
nothing at all. That is why the first seven-step run on the part read the
converter floor at every gain code.

**Fixed** in the generator (`load_send_pos()`, with a check that `send_pos` is
a 0..23 permutation) and in `step_image()`. Both lists regenerated; the quick
list now matches the measurement 14 of 14.

### S125-2 🔴 The strip meter cannot judge a gain step

Three measurements, none of which needs a lead, because all three are
properties of the meter:

**Its decay is 6.52 dB/s** (`s125_meter.py --decay`; 178 points, fitted from
−6.00 dBFS). S121 estimated 6.

**It holds the transient.** The step writes the chain (gain up) and lowers the
drive 10.6 ms later, then peeks at 50 ms. Driving the same two writes with a
12.845 dB step:

| | reading |
|---|---|
| settled — one write straight to the target | **−18.00 dBFS** (spread 0.00, n 5) |
| the coded order — up, then down | **−5.51 dBFS** (spread 0.01, n 5) |

**12.49 dB of a 12.845 dB transient is still standing at the peek**, which is
exactly 0.35 dB of decay at 6.52 dB/s over 54 ms.

**It cannot see a dead element.** Live at −18.00 dBFS; the stimulus then
removed entirely — which is what an open or shorted element looks like to the
lane — and 50 ms later the meter still reads **−18.39** while the measurement
node reads −23.8 and falling. **0.39 dB is not a test.** The tolerance is 3 dB.

**And with no lead it reads its own tail as a gain law.** The seven steps on
MIC 7, rails up, chain verified at every code:

```
code   0      1      2      4      8     16     32     63
    -62.2  -64.2  -66.3  -68.6  -70.8  -72.9  -75.1  -77.5   dBFS
```

A clean 2.2 dB per step — which is 6.52 dB/s times the 0.34 s a step took.
Nothing in that ladder is the preamp.

### S125-3 🔴 The node's level reading saturates, and the steps were driven into it

Moving the reading to the measurement node is necessary and was not
sufficient. Commanding the oscillator down in 6 dB steps and reading all three
instruments together:

| commanded | node RMS | node coherent | strip meter |
|---|---|---|---|
| −6.0 | −18.65 | −15.63 | −6.00 |
| −12.0 | −20.14 | −17.13 | −12.00 |
| −18.0 | −21.64 | −18.63 | −18.00 |
| −24.0 | −27.01 | −24.00 | −24.00 |
| −30.0 | −33.01 | −30.00 | −30.00 |
| … exact 1:1 to −96.0 | | | |

**The meter is exact everywhere; the node's level is exact only below about
−24 dBFS.** (The node RMS is peak − 3.01 dB, correct for a sine.) The gain
steps were driven so the converter saw −12 dBFS at every step, 12 dB inside
the compression.

What that costs, measured at the step's own window — a tone stepped DOWN by
each element's size, which is what a dead element does to the lane:

| element short by | read at −12 dBFS | read at −24 / −30 / −36 dBFS |
|---|---|---|
| 6.552 dB | **1.649 dB** (error −4.90) | **6.554 dB** (error +0.002) |
| 6.618 dB | 1.656 dB | 6.620 dB |
| 7.211 dB | 2.080 dB | 7.213 dB |
| 7.391 dB | 2.268 dB | 7.393 dB |
| 7.429 dB | 2.307 dB | 7.431 dB |
| 12.845 dB | 7.722 dB (error −5.12) | 12.847 dB |

The error is **constant against settle length** — swept out to 12 settle
windows (1.111 s) and it does not move — so it is not a settling problem and no
amount of waiting fixes it.

At −12 dBFS, four of the six elements could die and the step would pass.

**Fixed:** `GAIN_TONE_DBFS = -30.0` in the generator, used by the gain rows and
by nothing else. Six decibels below the knee; the tone is still 84 dB over this
unit's measured converter floor where the station only asks for 40; the lowest
drive it produces is −78.05 dBFS and the oscillator and node are exact 1:1 down
to −96 dBFS.

### The window the step now uses, and what it cost

Cost and live-against-dead separation at each window, five reps each:

| settle, windows | cost | live | dead | separation |
|---|---|---|---|---|
| 0, 1 | 0.034 s | −61.02 (the window BEFORE the change) | −25.44 | wrong |
| 1, 1 | 0.078 s | −26.78 ±3.49 | −23.68 ±2.22 | **−3.10 dB** |
| **2, 1** | **0.167 s** | **−21.64 ±0.02** | **−116.28 ±0.46** | **94.64 dB** |
| 2, 2 | 0.245 s | −21.64 ±0.01 | −116.33 ±0.30 | 94.68 dB |
| 4, 2 | 0.422 s | −21.64 ±0.01 | −116.23 ±0.45 | 94.58 dB |

Two settle windows is where the node stops reporting the window the change
happened in; one read window after that is already exact to 0.02 dB and
nothing past it buys anything.

### The proof, on the part, through the station's own code

`s125_gainproof.py` runs the real `Analog.step_image`, the real
`Station.gain_step` and the real `Scorer`. The 595 write is real and read back
at every step; the reading is real; the verdict is real. Only the preamp is
arithmetic, because only the preamp needs a lead: a working element puts back
exactly what the drive took away, a dead one does not.

**A good input** (MIC 7, `send_pos` 11):

```
code   0  PASS  0.438 s  node -33.01  meter -12.04  the tone arrived on MIC 7 and nowhere else
code   1  PASS  0.181 s  node -33.00  meter -14.89  gain element 1 adds 12.8 dB, -0.0 dB from expected
code   2  PASS  0.186 s  node -33.01  meter -16.07  gain element 2 adds 19.5 dB, -0.0 dB from expected
code   4  PASS  0.145 s  node -33.00  meter -17.31  gain element 3 adds 26.9 dB,  0.0 dB from expected
code   8  PASS  0.188 s  node -33.00  meter -18.25  gain element 4 adds 34.3 dB, -0.0 dB from expected
code  16  PASS  0.189 s  node -33.01  meter -19.46  gain element 5 adds 41.5 dB, -0.0 dB from expected
code  32  PASS  0.235 s  node -33.02  meter -20.71  gain element 6 adds 48.0 dB, -0.0 dB from expected
```

The node reads −33.01 at every step — exactly −30 dBFS peak less 3.01 — and
every element to within 0.05 dB. **The meter column beside it is the artefact,
decaying 8.7 dB across the seven steps while the lane never moved.**

**Each element dead in turn**, by writing the wrong bit:

```
code   1  FAIL  node -45.85  MIC 7 gain step 1 is wrong: it adds 0.0 dB and should add 12.8 dB
code   2  FAIL  node -52.47  MIC 7 gain step 2 is wrong: it adds 0.0 dB and should add 19.5 dB
code   4  FAIL  node -59.90  MIC 7 gain step 3 is wrong: it adds 0.0 dB and should add 26.9 dB
code   8  FAIL  node -67.30  MIC 7 gain step 4 is wrong: it adds -0.0 dB and should add 34.3 dB
code  16  FAIL  node -74.50  MIC 7 gain step 5 is wrong: it adds 0.0 dB and should add 41.5 dB
code  32  FAIL  node -81.06  MIC 7 gain step 6 is wrong: it adds 0.0 dB and should add 48.0 dB
```

Six for six, with the plain sentence, naming the element and both numbers.

In the dry run the whole 59-patch quick list is **151 PASS / 0 FAIL**, and an
injected dead element — `--fault "gain:MIC 7:3"` — comes back **FAIL 1,
PASS 150**.

### The real per-step time

**223 ms a step, 1.56 s for an input** (median of the seven, on the part). The
review's target was 100 ms. Correctness wins, as the dispatch ruled: the 100 ms
version could not tell a working element from an open one at all.

Over a 24-input pass that is about 18 s more machine time than the old peek,
and the dry run's projected pass is **6.6 min** (342 s hands, 52 s machine).

### What the dispatch asked that the answer is "no" to

*"Read the seven steps against the lane's own noise."* **They cannot be, and
here is the measurement.** With nothing plugged in, the seven chain images on
MIC 7, read at the longest window tried (settle 8, windows 4, 0.967 s a step,
three reps):

| code | expected | node | rise over code 0 |
|---|---|---|---|
| 0 | — | −114.2 | — |
| 1 | +12.845 | −113.0 | +1.2 |
| 2 | +19.463 | −107.7 | +6.5 |
| 4 | +26.892 | −105.3 | +8.9 |
| 8 | +34.283 | −113.7 | +0.5 |
| 16 | +41.494 | −91.2 | +23.0 |
| 32 | +48.046 | −84.8 | +29.4 |
| 63 | +53.111 | −81.0 | +33.2 |

The preamp's own noise only clears the converter's floor past about 40 dB of
gain; below that the lane reads the floor whatever the chain says. Above it the
*increments* do track the law (code 16 → 32 is +6.4 dB measured against +6.55
expected), but four of the seven steps are unreadable. **The seven steps still
need a lead**, and that is on PW's bench list where S124 left it.

---

## 2. The automated set (dispatch items 2, 3 and the S124 follow-ups)

Two full `--section A,B,C` runs before and two after, same unit, same bench.

| | before | after |
|---|---|---|
| wall clock | 253 s, 265 s | **208, 208, 207 s** |
| tests alone | 229.3 s | **183.5, 183.4, 182.6 s** |
| verdicts | 35 PASS / 1 FAIL / 15 NO DATA | 35 PASS / 1 FAIL / 15 NO DATA |

**46.7 s of test time**, against the review's desk estimate of 43 s. (Three
after-runs rather than two: the third carries DR1's last change. The spread of
the total across them is 0.9 s.)

| test | before | after | saved | what changed |
|---|---|---|---|---|
| DY1-RDY1 | 13.9 | 0.0 | **13.9** | folded into DR1 and DR2 — one pair boot fewer |
| AS-CPLD | 17.9 | 5.4 | **12.5** | overrun window runs from the last boot, not a `sleep(10)` |
| AS-DAC | 5.4 | 0.0 | **5.4** | retired (S124-4, below) |
| ML-P2 | 5.4 | 0.3 | **5.1** | one `stest` probe for all three |
| ML-P1 | 5.3 | 0.2 | **5.1** | " |
| AS-DSPA | 4.9 | 3.4 | 1.5 | heartbeat from diag samples already taken |
| AS-DSPB | 3.1 | 1.6 | 1.5 | " |
| AL1 | 11.9 | 10.4 | 1.5 | codec init once a session; link-alive once an epoch |
| DR1 | 6.3 | 5.5 | 0.8 | the "was it advancing" pair off the post-boot sample |
| HD0-1 | 2.6 | 0.9 | 1.7 | nothing — bench variance in `edid-decode` |
| NW2 | 31.2 | 32.3 | −1.1 | nothing — it is a fixed 30 s idle window |
| DR2 | 14.1 | 15.8 | −1.7 | it now takes DY1's reading and opens the overrun window |

Every verdict line is unchanged except AS-DAC's, which is the point of
retiring it. DY1 still reports the same triple — *running hi, in reset lo,
after boot hi, BOOT_STAGE 7* — taken from DR1's own pulse and DR2's own boot
instead of a third reset and a third boot of its own.

Two evidence strings were understating what they now measure and were
corrected: AS-CPLD's said "over 10 s" for a window that is now the whole of
group C, and AS-DSPA/B printed a raw counter difference as a "delta" when the
interval was never one second. The heartbeat figure is now stated as blocks per
second, which is what the criterion always meant.

### Item 2 — the rails go up once

They went up twice per RUN ALL: the self-test lowered AN_EN at its handback and
the patch station raised it again, against PW's "raised once, after the last
DSP boot". RUN ALL now passes `--al1-keep-rails` to the auto set **when an
analog station is still owed in that pass**, and the patch station takes
ownership of the handback (`--own-rails`). A pass with no patching left, or one
stopped after the auto set, still lowers them where it always did. PAUSE and a
crash are unaffected: `Analog.down()` runs on every way out and now lowers the
rails whoever raised them.

### Item 4 — settle from the event, not the call

`measure()` counted its settle windows from the moment it was called. The
route for a patch is written *before the prompt goes up*, and the operator then
takes seconds to fit a lead, so by the time the reading is taken the wire has
been still for tens of windows and the run was paying six of them anyway.

The unit now remembers when anything last changed — a cell write whose value
actually differs, a chain image that actually moved, and the detector seeing
the lead go in — and `settle_owed()` returns what is *still* owed, counted from
that event. A reading that arrives early still pays the remainder, so
auto-advance cannot read a window with a half-seated connector in it.

The last written value of every cell is kept so that a write landing on the
value already there is not counted as a change; `matrix-app` is down for the
whole session and the station is the only writer.

### Item 5 — RUN ALL's dialogs

The file half of `PollRunAll` is split out and runs on a **100 ms tick plus a
FileSystemWatcher**, the same shape S123 gave the patch screen; the expensive
half (`systemctl is-active`) stays on the 2 s tick where it belongs. The
runner's own answer poll went from 300 ms to 50 ms.

**Measured on the part**, ten prompts written the way the runner writes them
(rename into place), latency read out of the app's own log:

```
28, 53, 357, 5, 12, 404, 4, 5, 7, 6 ms      median 9.5 ms, worst 404
```

Before this the dialog waited for a `DispatcherTimer` of 2 s — 0 to 2000 ms,
1000 ms mean. That figure is a code fact, not a measurement: the old binary has
no log line to measure with, which is why the new one records its own latency.

### Item 6 — one card for both switch panels

`CARD_GROUPS` lets adjacent stations share a card; the two switch panels do.
The operator sees **four station cards instead of five**, with the checks
counted across both panels, and the same presses after it. Skipping the card
skips both panels, because that is what the operator said. 789 patch-station
strings and the whole RUN ALL dialog dump are clean under `--check-md`.

---

## 3. The S124 follow-ups

### S125-4 🔴 NW3 has never been able to report PASS (this is S124-5)

```python
'0% loss, max RTT < 5 ms (worst of %d passes)' % r.a.nw3_runs
```

`% l` is a valid conversion — space flag, `l` length modifier — and `o` makes
it octal. It eats `nw3_runs`, and the `%d` that follows has nothing left:
`TypeError: not enough arguments for format string`. Reproduced in one line.

**The line is on the PASS branch and nowhere else.** NW3 could report FAIL and
NO DATA; it crashed the runner the moment the network was actually clean. S124
recorded the traceback and guessed it fired "unless the network is actually
losing packets" — it is the exact opposite, and the ambient loss on this bench
is why it has been so rare.

Fixed (`0%%`). The whole `tools/` tree was scanned by AST for the same shape —
a `%`-formatted literal whose prose accidentally parses as a conversion — and
this was the only one. The two neighbouring branches had the mirror-image
defect, `0 %%` in a string that is *not* `%`-formatted, so they printed two
percent signs; corrected too.

### S125-5 🟡 AL1's calibration fit has a silent escape hatch (found while doing S124-2)

`al1_fit()` excludes points that were not measuring a tone, and if that leaves
fewer than two it falls back to the whole grid. Correct — but silently, and the
table it then writes says *"n fitted, 0 excluded as not measuring a tone"*,
which is exactly backwards. S124's calibration fitted all fifteen points this
way, through a THD+N reading that had become a constant 0.00 dB, and nothing
said a word. The fallback now prints, and the stored `runs` line says the fit
fell back and to treat the table as provisional.

### S124-2 — AL1's THD+N line, and the thing the ruling did not mention

The node's THD+N line and the `thdn_abs_db` / `thdn_margin_db` limits are gone,
as ruled.

**But two live code paths were reading that number**, and removing the line
alone would have broken them. `al1_tone_present()` — the NO SOUND gate — and
the calibration's own quality filter both tested it, and with the node's THD+N
pinned at 0.00 dB the gate had already fallen through to **SNR alone**. That is
precisely the failure S111 proved: a working loop scored NO SOUND because the
room had come up 10 dB. Both now read the **coherent capture's** THD+N, which
measures the same quantity off the same tap, host-side, and is a real number.
AL1 still PASSes on the part: `base −46.8, tone −29.8, SNR 17.1 dB, THD −25.5 dB
= 5.31 %`, unchanged from S124.

### S124-4 — AS-DAC, retired, and why not re-pointed

It captured `_tx_out_slot_C2_SPKR_OUT` — a **TX slot**, the words the DSP hands
its output port — and called a varying slot a working DAC. **Nothing on this
unit reads an AK4458 output back.** The eight-channel DACs on DA0 and DA3 drive
the line-out sockets and there is no return path, so that reading could never
separate a working converter from a dead one, with or without the stimulus it
reported as its prerequisite. Since S122 the slot it read is exact zero by
design as well.

Re-pointing it was considered and there is nowhere to point it:

* the sixteen line outputs are proved by the **patch pass**, through a lead,
  end to end, one verdict each;
* the codec DAC is proved by **AL1**, acoustically, with no hands;
* the Centre/LF and headphone sockets are proved by neither, and this test
  cannot reach them for the same reason the patch list cannot — they are on
  converter lanes this product has no cell for.

So the row stays NO DATA with the true reason and the 5.4 s capture is gone.
The test **id** is kept rather than deleted so the workbook row keeps a
verdict and the hub's key cross-check still resolves; it no longer pretends to
measure anything.

### S124-3 — the image gate

Untouched and still in force. `_check_factory_image()` reads the `.ldr` md5s as
well as the build-cfg triple, and every change here went through it.

---

## 4. S125-6 🟡 MIC 5 and MIC 6: the preamps are fine

S123 excluded MIC 5 and MIC 6 from the quick list as dead inputs — they carried
no tone through a lead. Their **preamps respond normally**: at gain code 63
lane 5 rises **+34.98 dB** and lane 6 **+32.93 dB** over their own floor, in
the middle of the population's 31.7-34.7 dB. So whatever is dead on those two
is between the XLR socket and the preamp input, not the preamp and not the
converter. Recorded, not chased.

---

## 5. 🔴 For PW: the rest of the station is still measured at −12 dBFS

S125-3 was scoped to the gain steps, because the gain steps are what this
dispatch put in hand. **The same compressed instrument takes every other level
reading the station makes**, and they are all driven at `TONE_DBFS = -12`:

* the patch's **balanced reference** (`h_db`, stored per lane by the `ref`
  row) — 5.13 dB compressed at −12 dBFS;
* the **single-ended comparison** that judges every TRS jack against it
  (`single_ended_db`, window `level_tol_db` = 3.0 dB). The two readings sit
  6 dB apart on a curve that is bending, so the compression does **not**
  cancel in the difference;
* the **null** sub-test, which is a ratio of two of those.

Moving `TONE_DBFS` to −30 would fix all of them in one number and the
measurements above say it is the right number. It is not built, because the
station's stimulus level is the ruled test's and re-levelling it changes every
reading and every window PW has tuned. **Recommendation: yes, as one change,
with the output and TRS windows re-taken on a good unit afterwards.**

---

## 6. What is not done, and why

* **No pass with a lead.** Everything above about the *instrument* is proved on
  the part; what still needs a hand is the preamp between the byte and the
  reading. The corrected byte map, the −30 dBFS drive and the node window are
  all in place for it.
* **The `factory-test-v2` → v3 items** (instant ramps, the 21 ms window,
  standing state at boot) are PW's and were not built.
* **Overlap, footswitch, parked kit, pre-arm, rear sockets, the combined
  socket stop** — all with PW, not built.
* **The two NW rows that do not pass on this bench** are the bench, not the
  unit: NW3 sees 5-6 % loss to the driving host at .211 and 0 % to the
  gateway, and NW4 reads 94 Mbit/s because this host's `ens9` negotiated
  100 Mb/s. Both were the same before and after.

---

## 7. Deployed, and the unit as left

| file | md5 | rollback |
|---|---|---|
| `/home/app/app` | `f1de9b537636e333e7fbec2de765834d` | `app.bak-s125-pre` = `7533ce450967890cac9a7b417eb0c109` |
| `/home/app/selftest/d24_selftest.py` | `c50dccf95df80561a32c5c4bebcedd7b` | `.bak-s125-pre` |
| `/home/app/selftest/d24_patch.py` | `e95281c4af998fe49ad9f7227e840090` | `.bak-s125-pre` |
| `/home/app/selftest/d24_runall.py` | `24957308a73e0a1f24ef94c26998c776` | `.bak-s125-pre` |
| `/home/app/selftest/quick/patch-paths.csv` | regenerated | |
| `/home/app/selftest/quick/patch-gain-steps.csv` | regenerated (drive −30.00 … −78.05) | |
| `/home/app/selftest/quick/patch-routes.csv` | regenerated | |

All three Python files are byte-identical to the repo. The app is the
`linux-arm64` self-contained single-file publish of mx26 at the commit this
session made; `d24-testui` was restarted once to pick it up and came back with
the factory screen armed.

`defs.lock` is **UNMOVED** and `dsp.csv` untouched — the `send_pos` fix is a
change to this repo's *consumer* of `defs/products/d24/inputs.csv`, not to the
definition, which was correct all along. **No contract bump is owed.**

**The unit as left:** AN_EN **lo**, CS_M driven **hi**, the 595 chain **SAFE**
and read back, the oscillator **off**, `matrix-app` **inactive**,
`d24-testui` **active**, no live status file, no `runall/prompt.json`, and the
**factory screen ARMED** with the 59-patch quick list. The one thing PW presses
is still START.

---

## Addendum 1 — the product app is not wrong (hub, 2026-09-26)

**Asked:** does the app put each MIC's gain byte where the hardware reads it?
**Answer: yes, on all twenty-four, on both of the layouts it can use. There is
no product bug.** 🟢

This was not settled by reading the app. `MW/D24/DSP/s125/chaincheck/` loads
the built `app.dll` by reflection and runs the app's **own**
`AnalogControlChain.BuildImage` and `ToWire`: for each panel channel in turn it
builds an image in which that channel alone carries an unmistakable gain code
(21 = `0b010101`), converts it to wire order exactly as the app does before it
clocks anything, and reports which transmit byte the marked value landed in.

| MIC | `chain_index` | defs `send_pos` | app tx byte (compiled fallback) | app tx byte (defs layout) | measured on the part | |
|---|---|---|---|---|---|---|
| 1 | 1 | 23 | 23 | 23 | depopulated | OK |
| 2 | 3 | 21 | 21 | 21 | depopulated | OK |
| 3 | 5 | 19 | 19 | 19 | depopulated | OK |
| 4 | 7 | 17 | 17 | 17 | depopulated | OK |
| 5 | 9 | 15 | 15 | 15 | 15 | OK |
| 6 | 11 | 13 | 13 | 13 | 13 | OK |
| 7 | 13 | 11 | 11 | 11 | 11 | OK |
| 8 | 15 | 9 | 9 | 9 | 9 | OK |
| 9 | 17 | 7 | 7 | 7 | 7 | OK |
| 10 | 19 | 5 | 5 | 5 | 5 | OK |
| 11 | 21 | 3 | 3 | 3 | 3 | OK |
| 12 | 23 | 1 | 1 | 1 | 1 | OK |
| 13 | 2 | 22 | 22 | 22 | depopulated | OK |
| 14 | 4 | 20 | 20 | 20 | depopulated | OK |
| 15 | 6 | 18 | 18 | 18 | depopulated | OK |
| 16 | 8 | 16 | 16 | 16 | depopulated | OK |
| 17 | 10 | 14 | 14 | 14 | 14 | OK |
| 18 | 12 | 12 | 12 | 12 | 12 | OK |
| 19 | 14 | 10 | 10 | 10 | 10 | OK |
| 20 | 16 | 8 | 8 | 8 | 8 | OK |
| 21 | 18 | 6 | 6 | 6 | 6 | OK |
| 22 | 20 | 4 | 4 | 4 | 4 | OK |
| 23 | 22 | 2 | 2 | 2 | 2 | OK |
| 24 | 24 | 0 | 0 | 0 | 0 | OK |

**16 populated inputs checked against the part, 0 disagree.** The eight
"depopulated" rows are panel mics 1-4 and 13-16, which have no front end on
MW-D24-2, so the part cannot confirm them; the app still agrees with defs on
all eight.

**Both layouts, because the app has two.** With a defs checkout reachable it
builds images from `defs/products/d24/inputs.csv`; on a deployed unit
`DefsFile.Find` returns nothing and it falls back to a compiled table. The
probe exercises both explicitly and they are byte-for-byte the same. (The
`Default` property resolved to the fallback in this run, which is why the
defs path had to be forced rather than assumed.)

### Why the app got it right and the station did not

The app never uses `chain_index` as a wire index. It uses it to order a
**logical** image — index 0 is U34/SHIFT at the head, 1..24 are the chain
positions — and then reverses the whole array exactly once, in `ToWire()`,
because the chain clocks the first byte sent to the far end. That single
reversal turns chain index *c* into transmit byte 24 − *c*, which is
`send_pos`. The class comment claims that reversal is "the only place byte
order changes"; grepping every other file for `image[`, `ToWire`, `FromWire`,
`ChannelOrder`, `ChainIndex`, `SendPos` and `PositionOf` confirms it — the two
other `ToWire` calls are in the CLI's printer, turning a readback back into
wire order for display.

The station had no such reversal. It built the transmit array directly and
indexed it with `chain_index` — **the same number the app uses for the logical
image**, used as a wire index. That is the whole of S125-1, and it is a
one-sided defect: the station's array is already in wire order, so it needed
`send_pos` and nothing else.

There is also a guard on the app's side that the station did not have:
`InputMap.TryParse` **refuses** a defs file in which `send_pos != 24 −
chain_index`, so the two columns cannot drift apart under it. The generator
now has its own check (`send_pos` must be a 0..23 permutation), which catches a
different failure — a duplicated or missing byte — and the two together cover
the file.

**Nothing for the hub to fix in the app.**
