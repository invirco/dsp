provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S121 — The audio patch loop

One list of signal paths, walked by hand, with nobody pressing Enter.

**81 patches, 91 measurements, five standard leads, four lead changes.** The
machine spends **78 s** of a whole pass; the rest is the operator's hands.
Projected end to end: **5.4 minutes at 3 s per hand move, 8.1 at 5 s, 12.1 at
8 s.** It replaces the analog station's forty-eight dialogs, every one of which
said the fixture was not built, and grades **45 of those 48 rows**.

Nothing has been patched yet. Everything below the copper is proved on
MW-D24-2; the copper needs a hand and this session had none. §8 says exactly
what is owed.

---

## 1. The shape

PW, 2026-09-26: *"tester will prompt the operator to patch a single cable then
press enter, the signal path will be tested with pass/fail, then the next patch
will be prompted, until all signal paths are tested"*, and then, later the same
day, that the manual loop is the **production** path and the figure of merit is
**operator seconds**.

So the loop is built around the hands, and the Enter went away:

* **The prompt goes up with the tone already running**, and the runner watches
  the input that patch is meant to reach. The step ends the moment the lead
  goes in. Measured on the part: the detector polls a lane in **1.3 ms** and
  fires **1 ms** after a tone starts.
* **The noise rows auto-advance too.** A 150 Ω terminator makes no tone — but
  fitting it *drops* the lane's noise, because an open mic input is noisier
  than a terminated one. That drop is the insertion.
* **Scoring is pipelined.** The next patch is prepared and prompted before the
  last one is scored, so the operator waits only for the reading itself.
* **A wrong patch is a prompt, never a fail.** The runner names the socket the
  lead actually went into — *"the tone came back on MIC 6, not MIC 5"* — and
  offers the same patch again, twice, before recording anything.
* Enter stays on the glass as a fallback, and PAUSE, SKIP and IGNORE are on
  every dialog as they are everywhere else.

## 2. The kit and the plan

| lead | what it is | how it is wired | patches |
|---|---|---|---|
| K1 | XLR-F to XLR-M | straight balanced | 25 |
| K5 | 150 Ω XLR-M terminator | 150 Ω across pins 2–3 | 24 |
| K4 | XLR-F to 6.35 mm TRS | pin 2 → tip, pin 3 → ring | 24 |
| K2 | 6.35 mm TRS to XLR-M | tip → pin 2, ring → pin 3 | 6 |
| K3 | XLR-F to 3.5 mm TRS | pin 2 → tip, pin 3 → ring | 2 |

One of each, all off the shelf. The blocks run in that order, so the lead type
changes four times and never goes back to a lead already put down. Inside every
block but the first, **one end stays put**: the output end sits on AUX 1 for
the 24 line patches and the 2 mini-jack patches, the input end sits in MIC 1
for the 6 TRS-output patches, and the terminator moves on its own. Only the
first block moves both ends, and only for its first ten patches — one per XLR
output, proving each output socket in its own right before AUX 1 is parked for
the remaining fifteen.

The full table, the coverage and the not-run list are generated:
`patch-plan.md`, from `patch-paths.csv` and `patch-routes.csv`.

## 3. The stereo rule, as PW ruled it

Every stereo TRS jack, input or output, is **one patch** through **one**
standard lead, and the channels are separated by driving them separately.

**A stereo TRS output** (the four "Aux Out A" jacks) reaches the XLR input as
tip minus ring, so the patch is three sub-tests: **L alone** — tone present,
normal polarity; **R alone** — tone present, inverted, at the same level; and
**both in phase** — a null. The null is what proves the two channels match and
are not crossed. The polarity of the L-alone reading is what proves tip and
ring are not swapped: a swap makes L arrive inverted, and the loop says so in
those words.

**A stereo TRS input** (the two mini-jacks) is driven from one balanced XLR
output, whose pin 2 becomes L and pin 3 becomes R, so one stimulus reads both
lanes at once — L normal, R inverted, equal level. An inverted LEFT is a
channel swap and is scored as a swap, not as two failures.

**Monitor L and Monitor R** are one channel each and read as an ordinary
balanced signal through the same K2 lead: the harness revision's port table has
them as tip → hot with ring and sleeve → cold, so the lead works either way.
(`defs/products/d24/d24-io.csv` calls them UNBALANCED and the 2026-09-26
ruling calls them balanced tip-hot/ring-cold. The station does not care —
🟡 S121-6 below.)

## 4. What is measured, and with what

The stimulus is the DSP's own oscillator; the instrument is its measurement
node. Both need a `DSP4_TEST_NODES=1` image, which is what the factory already
runs — PW's S116 Q3 ruling names `factory-test-v1`. **The station refuses
anything else**, and that refusal is not politeness: those sixteen words exist
and take writes in a shipping image too, and a run against one would print
zeros that look exactly like a measurement of a dead unit.

| what | how |
|---|---|
| level | the coherent loop gain. The measurement node fits the lane against the oscillator's own sine and cosine every window and leaves the **signed** in-phase and quadrature amplitudes behind; the magnitude of those two is a level that noise cannot inflate |
| polarity | the argument of the same complex number — and it is **relative**. A 1 kHz tone through this unit arrives with 91.4 samples of latency rotated into its phase, which is 1.9 cycles, so an absolute sign means nothing. The first block **measures** each input's balanced reference phase and every later reading on that lane is judged against it |
| presence | the strip meters, peeked. One word per strip, no settling window, **32 ms for all twenty-four** — which is what the auto-advance watches and what the wrong-socket sweep reads |
| THD, noise | off the same windows, in dB **and** in percent |

A reading that lands on the polarity decision boundary is reported as
**uncalled**, with how far from the boundary it was. It is not quietly passed.

## 5. Windows — all provisional, and each says what it rests on

`patch-limits.csv` is the only place a number lives; the runner carries none.

The **balanced reference is measured, not predicted**: the first block patches
an XLR output into an XLR input, the one configuration whose level and polarity
are definitionally right, and every single-ended reading afterwards is a ratio
against it. That is what lets the windows survive a change of drive level, a
gain-law revision, or a different unit.

The single-ended window is **−6.02 dB** against that reference, ±3 dB. That is
a ratio, not a measurement: a balanced XLR output drives both legs in
anti-phase and a TRS tip drives one, so the differential is twice one leg — and
it holds only if the single-ended driver swings the same volts as one leg of
the balanced one, which this repo does not record. **🔴 S121-4** below.

## 6. What was proved on MW-D24-2

`logs/bench-probe-2026-09-26.txt`. Bench lock taken, `matrix-app` inactive,
`d24-testui` active, nothing else driving the card.

| | result |
|---|---|
| the image guard | refused a shipping symbol map by name; accepted the factory pair |
| **the standing write** | **567 cells, 5.4 s, 9.6 ms each, 0 failed to read back** — every cell name the generated list uses is real and every write landed |
| the floors | all **27 lanes**, 256 ms each, including the three codec return lanes nothing else can reach — the talkback XLR at −87.9 dBFS and the two mini-jack legs at −76.0 |
| **the routes** | every one reaches its bus at **−15.01 dBFS** with THD+N at the digital floor (−115 dB). A hard-panned main reads an exact digital zero on the other side, so the pan lands |
| the detector | fired **1 ms** after the tone, on a −105 → −12 dBFS step |
| the seconds | settled reading **436 ms**, route assert **112 ms**, 24-lane sweep **32 ms**, detector poll **1.3 ms** |
| the copper | **nothing is cabled on the bench**: every aux driven in turn lit no mic lane. What looked lit was the previous test's own meter tail, and the measurement said so — loop gain −137 dB, THD+N 100 %, random phase |

The desk half: the dry run walks all 81 patches on a virtual clock and reaches
**every** outcome — a clean pass, a lead in the wrong socket, a dead path, a
swapped stereo pair, a null that does not null, and a phase too near the
boundary to call (`logs/dry-run-faults.txt`). Every operator-facing string the
loop can produce is clean under the internal-vocabulary check.

### Three defects the bench found and the desk could not

**🔴 S121-1. Every strip under test has to be opened, not just the donor.** The
instrument taps a strip **post-fader**, so a muted strip reads an exact zero
however healthy its converter lane is — which is indistinguishable from a dead
input. MIC 20 read **−336 dBFS** against every other lane's −116, because the
acoustic-loop test's own teardown mutes strip 20 and nothing had ever put it
back. The standing write now opens and bypasses all twenty-four. *(This is also
a standing fact about MW-D24-2 worth knowing: an acoustic-loop run leaves one
input muted.)*

**🔴 S121-2. The donor strip is the loudest lane on the unit, always.** The
oscillator *replaces* a strip's input, so the donor's meter sits at the drive
level for the whole pass whatever is plugged in: it read **−12.0 dBFS** while a
real path reads about −15. Left in the isolation check it would have made every
single patch report the tone as being on the donor. It is now skipped there and
in the wrong-socket search, and the dry-run model reproduces it so the desk
would catch it next time.

**🔴 S121-3. Two settling windows is not enough, and it looks like distortion.**
The fit subtracts the previous window's fitted sine sample by sample, so a
window in which anything moved is scored as distortion. Sweeping the settle
over the same three routes:

| settle | aux 1 | aux 2 | main L |
|---|---|---|---|
| 2 | −19.21 dB | −24.74 dB | **−3.75 dB** |
| 4 | −116.16 | −115.50 | −115.51 |
| 6 | −115.51 | −115.50 | −116.16 |
| 12 | −116.16 | −116.16 | −115.51 |

The **level read −15.01 dBFS in every one of those**, settle 2 included. It was
never the level that was wrong. Four is the floor now, six after a route
change.

And one hazard the bench exposed without failing on it: **the strip meters
decay slowly**, about 6 dB per second, so a lane driven hard by one patch is
still tens of decibels above its floor during the next. Judging "is anything
else lit" on the absolute reading would have called that a mis-patch on a
healthy unit. A mis-patch lights a lane that was dark; a meter tail is a lane
going out — so the check now asks whether a lane **rose** during this patch,
against a baseline swept when the prompt went up.

## 7. Seconds

Measured on the part, projected over the list:

| lead | patches | checks | machine s | per patch |
|---|---|---|---|---|
| K1 | 25 | 25 | 20.7 | 0.83 |
| K5 | 24 | 24 | 17.9 | 0.75 |
| K4 | 24 | 24 | 19.8 | 0.83 |
| K2 | 6 | 14 | 11.2 | 1.87 |
| K3 | 2 | 4 | 3.0 | 1.52 |
| **all** | **81** | **91** | **78** | **0.90** |

| hand move | hands | machine | pass |
|---|---|---|---|
| 3 s | 243 s | 78 s | **5.4 min** |
| 5 s | 405 s | 78 s | **8.1 min** |
| 8 s | 648 s | 78 s | **12.1 min** |

The machine is **13 %** of the pass at 5 s per move. There is little left to
win there and a great deal in the hand time, which is why the parked ends and
the lead ordering matter more than anything in the code. `pw-bench-script.md`
is the one-page script for timing a real pass.

## 8. Open items

**🔴 S121-4 — the single-ended level window is a ratio, not a measurement.**
−6.02 dB follows from the topology, but an older note
(`s110/test-catalog.csv`) claims the TRS pair and its XLR agree within ±1.0 dB,
which would make it 0 dB. The two have never been reconciled and PW's own
instruction is *"derive the exact window from the output stage, don't assume"*.
One patch on a good unit settles it: AUX 1 → MIC 1 through K1, then AUX A 1-2
→ MIC 1 through K2, and read the difference. Until then ±3 dB is wide enough
to pass either and narrow enough to catch a dead or halved path.

**🔴 S121-5 — three rear sockets have no host-reachable source on a D24, and
the station says so rather than failing them.** The Centre/LF XLR is `DAC_14`,
which the firmware feeds from aux bus 12; the headphone jack is `DAC_09/10`,
fed from aux buses 9 and 10. D24 declares aux buses 1–8 and no more, so no cell
exists to open any of them. The lane-by-lane netlist walk in
`docs/d24-dac-lane-xlr-candidate-20260913.md` says the same in its own §148–154.
Catalog rows 35 and 97 are therefore NOT RUN with that reason. **This is a
product question, not a test one**: either those sockets are meant to be driven
and the graph is missing a source, or they are not fitted on a D24 and the
catalog should say so. *(PW asked whether the headphone jack has a level pot:
no potentiometer appears anywhere in the analog board's inventory, and the
stage is a pair of summing op-amps. The pot is not the problem; the source is.)*

**🟡 S121-6 — the rear Monitor jacks are the crossover's centre and sub legs.**
They are `DAC_15/16` = `C2_MAIN_OUT_03/04`, whose cells are named `MainCtr` and
`MainSub`, so the monitor outputs are fed by the main crossover and not by the
monitor bus at all. Two consequences the list carries: the crossover is set
wide and shallow for the station, and **Monitor R — the sub leg — is tested at
100 Hz**, because a crossover is precisely what stops 1 kHz reaching it. The
lane-map document already flags the mapping as undecided; this station is now a
second reason to decide it.

**🟡 S121-7 — the two mini-jacks share one codec lane.** The codec has one
stereo aux input and the analog board carries two identical connectors for the
two panel jacks, so the station proves each jack's copper one at a time and
cannot tell which jack a signal arrived through. The prompt says to leave the
other one empty.

**🟡 S121-8 — nothing in this repo says how the combo jacks' line path is
selected.** `Chan<n>InputSel001` is declared `mcu` — MCU hardware control — so
it is not a write this runner can make, and nothing in defs, the DSP graph or
the 595 image says what else selects it. On a combo jack the TRS centre is
normally switched mechanically by the plug, in which case there is nothing to
set and the block just works. The 24 line patches therefore set no selection
cell, judge tone presence, and **report** the level rather than judging it.

**🟡 S121-9 — catalog housekeeping for the hub.** Row 148 (`Link 'hdmi-fpc'`)
sits in the analog group and is declared AUTO; it is a screen link and not an
audio path, and the classifier already warns about it. Rows 146 and 147 (the
links to the headphone-jack and mini-jack boards) are stamped by the paths that
cross them, the way S117 established. Row 97 is S121-5.

**No contract bump is owed.** `defs.lock` is unmoved and nothing generated from
defs changed.

## 9. What is still owed

The loop has never had a lead put into it. Everything up to the connector is
proved; the connector is not. `pw-bench-script.md` is a one-page script for a
real pass — and the first two patches of it also settle S121-4.
