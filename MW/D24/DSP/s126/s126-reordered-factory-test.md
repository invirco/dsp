provenance: AI-drafted 2026-09-27 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S126 — PW's seven speed rulings, built; and the one of them that cannot pay

MW-D24-2, 2026-09-27. Six of the seven rulings and the hub's addendum are
built, deployed and proved on the part. The seventh, `factory-test-v3`, is
**not built** and is reported as such, with its whole design and the reason.

**Headline.** The whole test goes from **11.6 min to 9.2 min** for a trained
worker and **15.5 min to 12.6 min** for a typical one, measured machine parts
and modelled hands. That is 143 and 178 seconds a unit, 21 % and 19 %. It is
**1.6 and 1.3 minutes short of the dispatch's amended prediction**, and the
shortfall is one measured thing: splitting the automatic set into three phases
pays its stop-the-mixer, stage and boot overhead three times instead of once,
so the machine's time before the first patch is **113 s and not the review's
67 s**.

And ruling (c) does not pay at all. **Every socket a lead can usefully be
parked on is a socket some walk has to visit**, so parking cannot save the
review's 24-40 s of lead changes. What it can do, and now does, is remove the
lead-change screen: the walk that needs the socket says "take the XLR-to-jack
lead off AUX 2 first" on the page it was already showing, and the kit is set up
once at START on the D24's own screen. §3 has the arithmetic and three options
for PW.

---

## 1. What was asked, and what came back

| ruling | built | proved on the part |
|---|---|---|
| (a) OVERLAP | 🟢 | 🟢 the three phases measured; NW4 under the patch loop; §2 |
| (b) FOOTSWITCH — deferred | 🟢 nothing built, as ruled | — |
| (c) PARK THE KIT | 🟢 | 🟡 the screens; the isolation proof needs hands (§3) |
| (d) PRE-ARM | 🟢 | 🟢 42 of 43 patches armed and confirmed, 0 re-read |
| (e) `factory-test-v3` | 🔴 **not built** | — (§7 is the design and the reason) |
| (f) REAR SOCKETS / PEDAL | 🟢 | 🟢 the sockets read live; two stations gone |
| (g) BOTH INPUT ORDERS | 🟢 | — a stopwatch decides it, not a model (§6) |
| ADDENDUM 1 — setup pages | 🟢 | 🟢 22 screens photographed, 7 pages on the glass |

---

## 2. Ruling (a): the overlap, and the number it actually buys

### The three phases, and why the split is where it is

The automatic set is now three phases, and **the membership is derived from the
self-test's own tables rather than restated**, so a test added there cannot
land in the wrong one — and a test in neither table raises rather than being
quietly dropped:

| phase | what is in it | why it cannot share |
|---|---|---|
| serial | the panel-processor and codec checks | they are bus transactions on the same serial device the panel loop reads key reports from |
| dsp | the reset, ready and chip-select checks, and the whole of the third group | the audio-processor link and the GPIOs; the panel loop touches neither |
| net | the network checks and the socket reads | Ethernet and the processor |

The new order, one START and one report:

1. START. The serial phase runs while the operator is walked through the bench
   setup, which needs no unit resource at all.
2. The dsp phase runs in the background while the operator does the panel
   loops. It ends with the rails up for the analog station.
3. The net phase runs in the background under the analog station.

**A fail in a background phase cannot abort the operator's work.** The phase
runs on a thread that owns no screen, cannot raise into the main one, and
reports an exception with its phase name; its verdicts are stamped by the same
function from the same results file the foreground path uses, so a row's
verdict does not depend on which order its test ran in.

**The panel loop holds its next indicator while the speaker sounds.** The panel
microphone hears button clicks. The self-test raises a flag around its own
tone (`--quiet-flag`) and the loop waits on it before lighting. It is a hint in
both directions: a run with no flag behaves exactly as it did, and a loop that
finds the flag stuck lights the next button anyway after 8 s.

### Measured, on MW-D24-2, 2026-09-27

| phase | test seconds | wall seconds | overhead |
|---|---|---|---|
| serial | 8.3 | 39.3 | 31.0 — stop the mixer, stage, codec init |
| dsp | 26.8 | 74.0 | 47.2 — stage again, and two pair boots |
| net | 116.5 | 116.9 | 0.4 — it stops nothing and stages nothing |
| **the three** | **151.6** | **230.2** | **78.6** |
| **the same set, ONE invocation, today** | **152.7** | **164.3** | **11.6** |

**🔴 S126-4: THE SPLIT PAYS ITS OVERHEAD THREE TIMES, AND IT COSTS 66 s.**
Three invocations: 230.2 s of wall for 151.6 s of tests. One invocation of the
same set, measured on the same unit an hour later: **164.3 s of wall for 152.7 s
of tests**. The tests are the same length; the difference is 66 s of
stop-the-mixer, stage and open-the-links, paid three times.

Most of it is hidden under the operator — that is the whole point of the
overlap — but **not in phase 2**, where the machine is the critical path for a
trained worker: 74 s of machine against 48 s of panel loop. So about 26 s of
the split's overhead is real wall time at 3 s a move, and none of it at 5 s.

The fix is not to unsplit it. It is that the three phases are three
*invocations* of a runner that stops the mixer, stages and opens its links each
time. One long-lived runner told to run a phase at a time would pay that once.
That is a session's work and the measured prize is named here rather than
guessed at: **66 s of machine time, of which about 26 s is wall**.

### The automatic set's own verdicts

Run whole, today: **33 PASS / 2 FAIL / 16 NO DATA** over 51 rows. S125 left it
at 35 / 1 / 15. The two rows that moved are **both network rows** — the packet
loss check and the counter check — and both moved because of this bench's
ambient network, not because of anything in this session: the counter check
PASSED in the phase run at 10:43 and FAILED in the whole-set run at 11:55, an
hour apart, with no code between them. Nothing in S126 touches a test's logic;
the only self-test change is the speaker flag, which writes a file and removes
it.

One row worth naming because it will look like a regression and is not: the
idle-graph check reads the graph **as it stands**, before anything in the set
drives it. It PASSED in the whole-set run and FAILED in the phase-only run,
because in the phase-only run the mixer had been live minutes earlier and its
own routes were still asserted. That is the check doing its job.

### The first proof: NW4 with the patch loop running

The dispatch asked for one throughput reading with the patch loop running, and
for a number rather than a lowered threshold if it did not make its bar. Both
answers are below, and **neither is the one the dispatch expected**, for two
reasons that are properties of this bench and of the runner, not of the unit.

**🔴 S126-2: AS RUN ALL RUNS IT, NW4 MEASURES THE LOOPBACK AND NOT THE LINK.**
Under `--local` — which is how the unit runs its own test, and how RUN ALL
always runs it — the throughput client and the server are both on the unit and
the client targets the unit's own address, so the traffic never leaves the
processor. The runner is not fooled: it reads the driving interface's
negotiated speed first, finds the loopback device negotiating nothing, and
scores **NO DATA naming the reason**. Nothing false passes. But the factory
gets no throughput number at all, which is not what the row is for. The fix is
that under `--local` the client must target the bench peer, which means the
peer runs the server — the thing the code deliberately swapped away from to
avoid a firewall on the driving host. That swap is right for a bench host and
wrong for the unit, and it needs to be conditional.

**🔴 S126-3: THIS BENCH CANNOT TEST THE 900 Mbit/s BAR AT ALL.** Driven
properly, from the dsp machine over the real link, the reading is **94 Mbit/s
each way** — and the runner says why: `the driving host's ens9 negotiates
100 Mb/s`. The bench host's link is 100 Mb/s. The review's flag C assumed a
gigabit path; this is that flag, measured. Until the factory bench has a
gigabit path, NW4 is a NO DATA row wherever it runs.

**So the contention question was answered on the instrument that could answer
it.** Loopback throughput is purely processor-bound, which makes it the most
sensitive test of the thing the review was worried about — that the throughput
test loads a core the patch loop needs:

| | unit receiving | unit sending |
|---|---|---|
| no patch loop | 5983 Mbit/s | 11973 Mbit/s |
| **with the patch loop running** | **5327 Mbit/s** | **5549 Mbit/s** |
| over the real link, both cases | 94 Mbit/s | 94 Mbit/s |

The patch loop costs the send direction 54 % of its processor-bound throughput
and the receive direction 11 %. **And it still leaves 5327 Mbit/s**, which is
5.9 times the 900 Mbit/s the row asks for. The gigabit bar is not in danger
from the patch loop; it is in danger from the bench's own 100 Mb/s link. Over
the real link the reading is identical with and without the loop, because at
94 Mbit/s the link and not the processor is the limit.

**And the error counters agree**: the counter check ran under the patch loop
and PASSED, with zero receive errors, zero drops, zero missed and zero transmit
errors over the whole of the throughput and ping tests.

Logs: `logs/phase-*.txt`, `logs/nw4-*.txt`, `logs/nw-under-patchloop.txt`.

---

## 3. Ruling (c): the parked kit — and why it cannot pay 24-40 s

### What is built

`patch-kit.csv` is generated beside the paths: one row per kit item, which end
is parked, and the panel socket it goes on. The three ends that hang on XLR
outputs take the first three working outputs; the jack-to-XLR lead parks in the
second working input — **not the reference one**, as ruled; the terminator is
on the bench. Every block's route, prompt and record now follow its own lead's
parked socket instead of homing everything on the first output, and the TRS
block follows the input walk rather than the line block, so the lead comes out
of its socket for that input's gain steps and goes straight back into it.

The runtime keeps the socket the list names — it has its own patch in the
output walk and has been proved — and moves it for exactly two reasons: the
XLR lead's own socket follows the reference output if the loop had to be found
somewhere else, and **a parking output that FAILED gets the ruling's one
re-park instruction**, to the first output the walk proved.

### 🔴 S126-1: the parking cannot be free, and here is why

Every one of the ten XLR outputs gets a patch of its own in the output walk.
Every one of the twenty-four XLR inputs gets seven gain steps and a noise
reading in the input walk. A socket holds one plug. So **a lead parked on a
socket the walk has to visit must come off for that patch** — there is no
ordering that avoids it, because there is no useful socket that no walk visits.

The review's arithmetic (4 changes × 2 moves = 24 / 40 s) assumed the parked
end never moves. It moves.

What the generator CAN do, and does:

* each walk is ordered so the socket carrying a parked lead is the **last** one
  it visits — the two parked outputs are patches 9 and 10 of the output walk,
  and the parked input is the last input of the input walk;
* the unpark is **one folded sentence on the page that was already asking for
  that socket** — "Take the XLR-to-jack lead off AUX 2 first" — with no card,
  no change screen and no extra press;
* and because the unpark happens at the end of the walk, the lead is in the
  operator's hand at the boundary rather than on the bench.

Net hand moves: **unchanged**. What changes is that there is no lead-change
screen, the kit is set up once at START under machine time, and every change is
one instruction. That is what the ruling's own words asked for
("a lead change becomes one instruction... with no change screen"); the 24-40 s
in the review's table is not available.

**Three options for PW, in order of what they cost:**

1. **Accept it.** No saving, no change screen, one instruction per change. This
   is what is built and it is the honest version of the ruling.
2. **Prove two outputs through the parked leads' own blocks.** Skip AUX 2 and
   AUX 3 in the output walk and let the jack block and the mini-jack block
   prove them. Saves two moves. Costs coverage: those two outputs' verdicts
   stop being a level against a balanced reference on a proved input and become
   tone-presence on a socket whose own level is not judged. **Not recommended.**
3. **A second XLR lead in the kit.** Does not help: the XLR-to-jack and
   XLR-to-mini-jack leads need XLR *outputs*, and the walk visits all ten
   whatever else is in the kit.

### 🟡 What still needs hands

The dispatch asked for a full pass with all five parked against the S123
baseline verdicts, to prove that parked, undriven leads do not upset the
isolation check. **That needs leads in sockets and nobody was at the bench.**
The electrical argument is unchanged and is in the review — only the active
route carries tone, and the check asks whether a lane *rose* — but it is an
argument and not a measurement. It is on the bench script (§8) as the first
thing to watch on PW's pass.

---

## 4. Ruling (d): pre-arm — 42 of 43, none re-read

On a tone row that is not a gain step, the reading is taken **the instant the
detector sees the tone arrive**. At ENTER one strip-meter peek — which needs no
settling window — must agree within 0.5 dB with the same peek taken when the
armed reading finished, and the verdict shows at once.

**ENTER still gates the verdict AND the advance.** Nothing is recorded, nothing
is shown and nothing advances before it. Gain steps, the noise rows and the
no-tone rows are unchanged, exactly as ruled.

**Three ways an armed reading is refused, and all three are measurements:**

* its own windows disagreed by more than 0.5 dB — a connector still moving
  while the reading was taken. `fold()` now carries that spread;
* the lane moved by more than 0.5 dB between the reading and ENTER — a lead
  pushed home, or one that came out;
* the lane has no level to peek at.

Refused means read again. **The patch loses the saving, not the correctness.**

**Measured, dry run over the full 91-patch list:** 42 patches armed and
confirmed, **0 re-read**, and the machine seconds on the operator's path go
**82.3 → 64.8 s**. The whole patch pass goes 7.1 → 6.8 min at 3 s a move and
10.2 → 9.9 min at 5 s.

**The saving is 17.5 s, not the 40 s the dispatch estimated, and the reason is
S125.** That estimate assumed the post-ENTER reading cost about 0.5 s a patch.
S125's settle-from-the-event had already taken the settle off — by the time
ENTER arrives the wire has been still for tens of windows and nothing is owed —
so what was left to move was about 0.24 s a patch on the single-reading blocks,
and about 1.3 s on the three-reading TRS patches. Pre-arming also *pays* a
settle the post-ENTER reading did not: the lead going in is a change on the
wire, so an immediate reading owes the remainder of the route window. That is
correct and it is why the armed readings cost 39.7 s of machine time to save
17.5 s of operator time.

**The half-seated connector was NOT demonstrated on the part.** It needs a hand
to half-insert a connector. The window-spread guard is in and exercised by the
dry run's arithmetic; the deliberate half-insert is on the bench script.

---

## 5. Ruling (f): two stations gone, three rows read while the test runs

* **The two USB sockets and the mains inlet are BACKGROUND rows**: no card, no
  Done press, read under the patch pass. The sticks go in during the setup
  pages at START.
* **The mains question is retired.** A D24 has no battery and no second supply,
  so the unit running the test answers it, and the evidence is the unit's own
  uptime rather than an opinion about something the operator cannot see from
  the front.
* **The pedal station is hidden.** Its six rows are recorded NOT RUN with their
  own reasons. One name switches it back on when the fixture exists
  (`PEDAL_STATION`, or `--pedal-station`).
* **And the rear-socket station went with it**: every row it had is now either
  read by the machine or blocked, so there is nothing left for a person to do
  there. **The manual set is two cards** — the front panel and the analog
  paths — where the review counted five.

A manual group that is no longer a station is classified explicitly rather than
falling through the station walk into silence, which is the one thing §1 of the
run-all shape forbids.

Proved on the part: the socket reads ran under the patch loop and the hub read
PASS.

---

## 6. Ruling (g): both orders, and a stopwatch to choose

`--input-order three-walks` (the default, as ruled) and `--input-order
one-stop` both generate. The same patches, the same readings, the same rows —
only the order changes.

**The dry run cannot tell them apart, and that is the finding.** It charges the
same seconds for a hand move whether the hand travels to the next socket or
swaps a lead in the socket it is already at: both orders come out at 6.8 min at
3 s and 9.9 min at 5 s, to the second. A model that cannot see the difference
cannot choose, which is exactly why the ruling said stopwatch first.

The card is at **`~/hub-staging/s126-stopwatch-card.md`**: six good inputs
(MIC 7-12), both orders, run A-B-B-A so that getting better at the job does not
land on whichever went second. It carries bench commands, so it is not clean
under the operator-vocabulary check and is not meant to be — it is for PW, not
for the line.

---

## 7. 🔴 Ruling (e): `factory-test-v3` is NOT built

**What is done:** the build path is proved. `DSP4_TEST_NODES=1 ./build.sh all`
on this machine rebuilds the deployed v2 pair **byte for byte** —
`chip1.ldr` `7f226919a5d181410c3804d92678da19` (433,508 B) and `chip2.ldr`
`9e8a1a9edf19a90ce7ac3df1586c00f6` (379,424 B), both md5- and size-identical to
what S124 deployed. So v3 is a matter of making four changes and building, not
of getting a toolchain working.

**What is not done, and why.** v3 is four independent firmware changes plus a
new build-cfg identity, each of which touches generated code that the whole
tree is regenerated from, and each of which has to be proved against the part
before the image can replace the one the factory screen is armed with. This
session spent its length on the six rulings that move 186-220 s a unit;
`factory-test-v3` moves about 10 s a unit (the gain step, 223 ms to roughly
120 ms over 98 steps) plus the 5.4 s standing write. **Flashing a half-proved
image to the pair the armed factory screen measures through would have been the
wrong trade**, so nothing was flashed and the unit is still on v2.

**The design, read out of the source rather than guessed, so the next session
starts from facts. Four of them are not what this dispatch assumed:**

1. **The runtime-selectable window is the one that delivers the ≤100 ms gain
   step, and it is the smallest of the four.** The accumulate loop closes its
   window on a compile-time block count and scales every published result by a
   compile-time `log2(N)` loaded as a constant
   (`tools/dsp/dsp_codegen.py:6690` and `:6718`). Make both runtime by
   selecting between **two** pairs of constants — 256 blocks with log2(4096)
   for the long window, 64 blocks with log2(1024) for the short one — on a new
   measurement-block word. Two choices and not an arbitrary N, so no logarithm
   is ever computed on the part.

2. **🔴 The reserved word is NOT reachable from the host, and the design has to
   start there.** The measurement block declares `_meas_rsvd_` "so the dispatch
   table has a symbol for it rather than a hole"
   (`tools/dsp/dsp_codegen.py:6453`) — but nothing ever dispatches it:
   `MW/D32/DSP/gen_dsp.py:1163-1200` lands exactly eight addresses for this
   node and none of them is that word. The host's `SpiLink.write(addr, value)`
   (`tools/pi/dsp4_config.py:314`, which is what `s89_set.py`'s `cN@ADDR=v`
   form reaches) writes a **dispatched SPI address**, not an arbitrary data
   word, so an undispatched symbol cannot be written at all.
   **The fix needs no contract change and there is precedent for it in the same
   function**: the window-serial word at `base+7` is dispatched with no cell
   behind it. One more `add_dispatch()` in `expand_test_meas` gives the new
   window word an address the bench can write, and the definitions are not
   touched — which matters, because this repo is a consumer of those.

3. **🔴 The third build-configuration word is FULL, so the "distinct build-cfg
   identity" the ruling asks for needs a FOURTH word.** Every bit 0 to 23 of
   `DIAG_BUILD_CFG3` is assigned (`MW/D32/DSP/SHARC/src/diag.h:766-781`; the
   mirror is `tools/pi/dsp4_buildcfg.py:118-131`) — six flags, a 2-bit defer
   field, the 8-bit shared-kernel mask, a 2-bit inline field, four more flags
   and the instrument bit — and 31 to 24 are the signature byte the decoder
   masks whole (`dsp4_buildcfg.py:360`). There is **nowhere to put a new flag**.
   That word's own note already prescribes the answer: the next flag of its
   class takes a new word rather than a seventh narrowing of a signature.
   **In the meantime the gate is not blind**: S124 added the pair's `.ldr` md5
   to the image assertion precisely because the triple could not tell v1 from
   v2, and that md5 tells v3 from both. So v3 can be gated today; the
   build-cfg identity is the second half and it is a fourth word.

4. **Instant ramps are a generator change, not a table edit.** No build flag
   makes every ramp instant. Only one profile already is; the others carry 3 to
   30 ms and are baked into a static table at generation time
   (`tools/dsp/dsp_codegen.py:863-882`, `:7442-7480`). The ramp engine takes
   the instant path only when its caller passes mode 0
   (`MW/D32/DSP/SHARC/src/ramp_engine.asm:29-37`, `:84`). The smallest honest
   change is a flag-guarded block at the top of the emitted `_ramp_set_target`
   that forces mode and frames to zero — in `gen_ramp_engine()`, not in the
   shared `RAMP_PROFILES` table, which every product reads.

5. **The standing state as a boot default is in this repo, and that is the good
   news.** The dispatch table carries no values at all
   (`MW/D32/DSP/gen_dsp.py:2138-2312`); a cell's boot value is the `.var`
   initializer in its own node file, generated from the `params` column of
   `MW/D32/DSP/SHARC/dsp.csv`, which is itself generated by
   `tools/dsp/gen_dsp_csv.py` from literals **in this tree**. So the 567
   standing cells can be given factory defaults behind a build flag without the
   definitions submodule being touched at all.

**What the next session owes:** the four changes, a contract regeneration that
proves no address moved, a build, a gated boot, and then S125's own proofs
repeated on v3 — every gain element killed in turn still failing with its plain
sentence, the noise figures unchanged within tolerance, and the per-step time
against PW's 100 ms target. Plus the flashed hashes.

---

## 8. Addendum 1: the setup pages

Eight pages on a full list, seven on this unit's short one, on the D24's own
screen: one big instruction, `n of N`, ENTER and PAUSE, nothing else. The
network lead, the two USB sticks, then each kit lead onto its socket in the
order the operator meets it.

**Where the machine can see it, the page says so** and still waits for ENTER —
the tick is information, not an advance, for the same reason "Signal found" is.
The network link and the two sticks are re-read about once a second so the tick
appears when the stick actually goes in. **Nothing on the unit can see a parked
lead's far end on an undriven output, and no page claims otherwise.**

**There is no pre-START page.** The only thing that has to be in before START
is the mains lead, and a unit showing this screen is running from it. The
network lead is not a pre-START item any more: ruling (a) moved the network
tests under the patch pass, minutes after START.

**Photographed on the glass**: 22 screens through the runner's own status file,
in front of the real display, captured by the display's own capture path — so
what PW sees is what a worker would see and not a mock-up.
`~/hub-staging/s126-screens/`, and the two that matter most are
`03-setup-network.png` and `07-take-the-parked-lead-off.png`.

---

## 9. The whole test, before and after

Machine parts measured on MW-D24-2 today; hand parts modelled at 3 s and 5 s a
move with 0.8 s to reach ENTER, which is the review's own model.

| | 3 s worker | 5 s worker |
|---|---|---|
| before — the test as S125 left it, with today's measured automatic set | **693 s = 11.6 min** | **931 s = 15.5 min** |
| after | **550 s = 9.2 min** | **753 s = 12.6 min** |
| saved | **143 s (21 %)** | **178 s (19 %)** |
| the dispatch's amended prediction | 7.6 min | 11.3 min |
| short by | 1.6 min | 1.3 min |

After, by phase — each is the slower of the machine and the worker, which is
what the overlap makes it:

| phase | machine | worker (3 s / 5 s) | the phase costs |
|---|---|---|---|
| the setup pages | 39.3 s | 30.4 / 46.4 s | **39.3 / 46.4 s** |
| the panel loops | 74.0 s | 48.0 / 80.0 s | **74.0 / 80.0 s** |
| the patch pass, network underneath | 116.9 s | 435.1 / 625.1 s | **435.1 / 625.1 s** |

At 3 s a move the machine is the critical path for the first two phases and the
worker for the third. At 5 s the worker is the critical path throughout, which
is why the saving is larger there: **every second of the automatic set
disappears for a typical worker, and about 113 s of it survives for a trained
one.**

**The shortfall is S126-4 and the footswitch.** The review's §3 put the
machine's pre-patch time at 67 s by counting test seconds; measured, as three
phases, it is 113 s of wall. Fixing the three-invocations overhead is worth
about 26 s of wall at 3 s a move, which takes the trained figure to about
8.8 min. The rest of the gap to 7.6 min is the review's §2.6 trims, which S125
banked where they existed — its note that the acoustic test's 10 s route write
"was not available" applies to the others too — and the 0.6 s a patch that the
deferred footswitch would have taken off 91 ENTER presses.

---

## 10. What is deployed, and the unit as left

| file | md5 | rollback |
|---|---|---|
| `/home/app/selftest/d24_patch.py` | `4b3784614bffe286deb0c39181733eb5` | `.bak-s126-pre` |
| `/home/app/selftest/d24_runall.py` | `b51f8916b1a3a141015c35cdad5bb92c` | `.bak-s126-pre` |
| `/home/app/selftest/d24_selftest.py` | `be05fe4b74af0a65c661383ba9486174` | `.bak-s126-pre` |
| `/home/app/selftest/d24_live.py` | `df9e0dff7c833a7586a1403f64729137` | `.bak-s126-pre` |
| `/home/app/selftest/d24_panel.py` | `2165c135374705876e8a06762458c5e6` | `.bak-s126-pre` |
| `/home/app/selftest/quick/patch-paths.csv` | `2d0f8327b92e3fa95c9750fff1a99187` | `quick.bak-s126-pre/` |
| `/home/app/selftest/quick/patch-kit.csv` | `7ba24b070ed1569d103f0b945937e2bd` | (new file) |

All five tools are byte-identical to the repo. The quick list regenerates to
**59 patches and 151 measurements**, the same shape S125 left armed.

**No DSP image was flashed. No CPLD bitstream was touched.** `defs.lock`
unmoved, `dsp.csv` untouched, **no contract bump owed**.

Operator strings: **1,322 CLEAN** under the internal-vocabulary check, up from
789; the whole dialog dump clean as well.

The unit's state as left is in §11 of the handback, below.

---

## 11. Handback

**AN_EN** lo (rails down), **CS_M** driven hi, the 595 chain **SAFE**, the
oscillator off, `matrix-app` **inactive**, `d24-testui` **active**, and the
factory screen **ARMED with the 59-patch quick list** — the one thing PW
presses is still START.

**No DSP image was flashed and no CPLD bitstream was touched**, so the
persistent-bitstream rule has nothing owed against it: the shipping bitstream
is in flash exactly as S125 left it and no design-ID readback was disturbed.
The DSP pair is the same `factory-test-v2` pair, at `/home/app/loopthd/s122`.

**One thing the session changed and put back.** Running the self-test directly
restarted the mixer, and the test display refuses to share the screen with it,
so the display service went down. Both were put back: the mixer stopped, the
test display started, confirmed active.

**And one guard fired, correctly, and is now handled.** The automatic set
refuses to boot the audio-processor pair with the analog rails up — PW's rule,
analog last up and first down. Running the audio-processor phase on its own
leaves them up *for* the analog station, so a second automatic run in the same
session hit that guard and stopped. That is the guard doing its job, but it
also means an overlapped pass STOPPED in the panel loops would leave a unit on
the bench live. **The overlapped pass now lowers the rails whenever it is
stopped before the analog station**, using the station's own teardown so there
is not a second piece of code that knows PW's order.

---

## 12. What is owed next

| | |
|---|---|
| 🔴 **S126-1**, for PW | the parked kit cannot save 24-40 s. §3 has the three options; option 1 is what is built |
| 🔴 **S126-2** | the throughput test measures the loopback when the unit runs itself. One conditional |
| 🔴 **S126-3**, for the factory | the bench host's link is 100 Mb/s; the 900 Mbit/s row cannot be graded anywhere until that is gigabit |
| 🔴 **S126-4** | three phases, three lots of stop-app/stage/boot. One long-lived runner pays it once: 47 s of machine, about 26 s of wall |
| 🔴 **ruling (e)** | `factory-test-v3`, whole. §7 is the design, and two of its four parts are not what the dispatch assumed |
| 🟡 **on PW's bench** | the parked-kit isolation pass, the deliberate half-insert, and the six-input stopwatch |
| 🟡 **for PW** | the rest of the analog station is still driven at −12 dBFS through the instrument S125 found compressed there. One number, `TONE_DBFS`, and the output and jack windows re-taken on a good unit |
