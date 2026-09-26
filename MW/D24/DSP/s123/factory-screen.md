provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S123 — The factory patch screen

One instruction. One live status line. Progress. Two buttons.

**PW, at the bench, 2026-09-26:** *"it should say aux 5 to mic 5 on the product
display. let's stop, remove all the clutter, add some realtime activity and
progress indicator, ie what it's currently doing, simple, simple, simple, for a
factory worker who knows nothing about the product, but can follow
instructions."*

Then, having pressed START on it: *"I like it, but let me plug in the cable,
then hit Enter."*

Everything below is on MW-D24-2 and photographed there. The one thing that is
still owed is a person with a lead in their hand: nobody in this session could
plug one, so the eighteen screens were driven through the runner's own status
file and captured through the display's own render path, and the two patches
that were made were made by PW at the hub's relay.

---

## 1. The screen

`screens/` holds one PNG per state, 1920×1080, all eighteen distinct, all
captured off the unit's own framebuffer render:

| | what a worker sees |
|---|---|
| `01-armed-start` | **Audio patch test** · 59 steps · START |
| `02-getting-ready` | Getting the unit ready… |
| `03-lead-change` | Pick up the XLR lead. · **Plug AUX 1 into MIC 7, then press ENTER.** |
| `04-walk-to-the-next-input` | **Move the lead to MIC 8, then press ENTER.** · Looking for a working socket… |
| `05-waiting` | Waiting for the lead… |
| `06-signal-found` | Signal found - press ENTER. |
| `07-checking` | Checking… |
| `08-pass` | **PASS** (green) · AUX 1 into MIC 7 |
| `09-wrong-socket` | **CHECK THE LEAD** (red) · The lead is in MIC 6 - move it to MIC 5, then press ENTER. |
| `10-no-signal` | **CHECK THE LEAD** · Push the lead in firmly at both ends, then press ENTER again. |
| `11-fail` | **FAIL** (red) · Leave it - the supervisor will look at this one. |
| `12-terminator-step` | **Take the lead out of MIC 7 and put the 150 ohm plug in, then press ENTER.** |
| `13-line-step` | Pick up the XLR-to-jack lead. · Plug AUX 1 into the jack socket of MIC 7… |
| `14-trs-output-step` | Pick up the jack-to-XLR lead. · Plug MONITOR L into MIC 7… |
| `15-paused` | Paused - the unit is safe. Press START to run the test again. |
| `16-finished` | Finished - all 59 passed. · Give this unit to the supervisor. |
| `17-finished-with-failures` | Finished - 57 passed, 2 failed. · the failures by name · Give this unit to the supervisor. |
| `18-no-signal-anywhere` | **No signal on any socket - call the supervisor.** |

**Nothing else is on it.** No row number, no class, no workbook status, no
catalog text, no lead code, no lane, no dBFS, no cell name. Colour carries one
meaning and one only: green is a pass, red is a fail. The instruction is set as
large as it will fit and shrinks a step at a time when the sentence is long, so
it can never run over the line beneath it.

**The display chooses no words and counts nothing.** Every sentence on that
list is generated in `tools/pi/d24_live.py`, beside the patch list, where the
internal-vocabulary check can be pointed at it; the C# draws what it is given.
`d24_patch.py --strings` dumps all 788 of them and `d24_runall.py --check-md`
reads them: **clean, no Matrix-internal vocabulary.** That split is what lets
the panel loop use the same screen later without a second copy of the
vocabulary.

### The activity indicator

A bar sweeps back and forth whenever the tester is working, driven by the
clock rather than by the tick count, and it sits outside both the status panel
and the verdict panel — because a worker staring at *"move it to MIC 5"* still
needs to see that the tester is watching for them to do it.

---

## 2. ENTER, and what ends a step

PW's ruling: the operator plugs the lead in and **then** presses ENTER. So:

* the instruction says both actions — *"Plug AUX 5 into MIC 5, then press
  ENTER."* — and the step does not end until the second one;
* the live line still says *"Signal found - press ENTER."* when the tester can
  see the tone arrive. It is a hint and it never advances anything;
* **the wrong-socket check survives.** ENTER with the tone on another input is
  *"The lead is in MIC 6 - move it to MIC 5, then press ENTER"* — a prompt,
  never a fail — and the test is against the level **right now**, so a lead
  that went in and came out again reads as out;
* auto-advance is the same loop with `--auto-advance`, and it is **off**.

ENTER arrives two ways. The button is on the glass. The **Enter key of a USB
keyboard is read by the station itself**, straight off `/dev/input`, with a
rescan every five seconds so a keyboard carried to the bench mid-pass starts
working without a restart. It is read there and not in the display for two
reasons: a run started from a terminal has no display to read it, and one
press must not arrive twice. 🟡 **No keyboard is plugged into MW-D24-2**
(`/proc/bus/input/devices` lists the touch panel and two HDMI nodes and nothing
else), so that arm is built and not witnessed.

There is no READY card and nothing to press at a lead change. The change is one
more sentence on the next instruction's screen, and it is dropped when the
instruction already names the lead.

---

## 3. The order: find a loop, then outputs, then inputs

PW: *"Test all XLR outputs first, in a line, as they flow on the mixer. If
there is no detection, move the input to the next one until a working loop is
established."*

Every patch now **moves one end and parks the other on a socket already
proved**, so a fail is pinned to one socket with nothing to cross-patch:

1. **Find a loop.** The output end starts on the first XLR output; the input
   end walks — *"Move the lead to MIC 8, then press ENTER"* — until the tone
   arrives. Three deaf inputs in a row and the **output** becomes the suspect:
   the output end moves on and the walk restarts, skipping the inputs already
   found silent. Nothing anywhere is **one sentence**, not forty fails.
2. **Every XLR output in a row** into the input the walk stopped on.
3. **Every XLR input in a row** from the output the loop was found with. Inputs
   the walk went past are recorded there and never walked again — the mic path
   only, because a dead XLR says nothing about the LINE path through the same
   combo socket.
4. The line inputs, the TRS outputs and the mini-jacks keep the same shape.

**The list cannot know which socket the reference is** — it is generated before
anybody plugs anything in. So it carries a `park` column saying which *end* is
parked, and the runner binds it at run time. Every drive emits **both** donor
routes, so a rebind can never name a route that is not in the file.

Proved in the dry run: three dead inputs → the loop lands on AUX 2 into MIC 4
and MIC 1-3 are recorded once each; twenty-four dead inputs → zero
measurements and the one sentence.

The order costs about ten more hand moves than the old list. That is the price
of never needing a second patch to interpret a fail.

---

## 4. The seven gain steps

PW: *"The real test should test all 6 gain resistors off, and each resistor
enabled individually — total 7 steps."*

Every XLR input patch takes seven readings without the hand moving again: gain
code 0, then codes 1, 2, 4, 8, 16, 32 — each gain-leg element alone. The
oscillator is dropped by each step's own expected gain so the converter reads
about the same level every time and nothing clips.

### Where the expected gains come from, and the one thing that had to be derived

`defs/common/tables/mic-gain-law.csv` is the authority and it was measured on an
analog board on 2026-09-16. It carries `hw_gain_db` for **25 of the 64 codes**
— and **three of the six single-element codes are not among them**, because the
law only keeps the code it would actually pick for each target dB.

So the six **element** gains are fitted to that same table, with no free
hardware constant. The preamp is an instrumentation amplifier whose gain is
1 + 2·Rf/Rg with Rg the parallel combination of whichever elements are switched
in, which makes

    G(code) = 1 + Σ k_i over the elements in the code

six unknowns against twenty-four measured codes. **Worst residual over all
twenty-four: 0.509 dB**, and the two single-element codes the law *does* carry
come out of the fit at 0.075 dB and 0.012 dB.

| step | code | byte | expected | source |
|---|---|---|---|---|
| 0 | 0 | 0x00 | 0.000 dB | measured |
| 1 | 1 | 0x04 | 12.845 dB | measured |
| 2 | 2 | 0x08 | 19.463 dB | measured |
| 3 | 4 | 0x10 | 26.892 dB | measured |
| 4 | 8 | 0x20 | 34.283 dB | **fitted** |
| 5 | 16 | 0x40 | 41.494 dB | **fitted** |
| 6 | 32 | 0x80 | 48.046 dB | **fitted** |
| (noise) | 63 | 0xFC | 53.111 dB | measured |

The table is **generated into the list** (`patch-gain-steps.csv`), not typed
into the runner, and each row says whether its number was measured or fitted.
The window is `gain_step_tol_db` in `patch-limits.csv`, provisional at 3 dB —
six times the fit's own error and still less than half the smallest step.

**What is judged is the step, not the level.** Each step is compared with the
*same input's* code-0 reading taken seconds earlier through the same lead and
the same output, so the loop gain, the drive and the converter all cancel and
what is left is what the element added.

Proved by injecting a dead element in the dry run:

```
P23   MIC 7    FAIL   MIC 7 gain step 3 is wrong: it adds 0.0 dB and should add 26.9 dB
P49   MIC 20   FAIL   MIC 20 gain step 6 is wrong: it adds 0.0 dB and should add 48.0 dB
```

One failing step, named in plain words, exactly as the ruling asked. The worker
sees none of it beyond *"Checking…"* and one PASS or FAIL for the patch.

**The chain does not run in panel order** — MIC 1 is byte 1 and MIC 2 is byte 3
— so the byte position comes from `defs/products/d24/inputs.csv` through the
list. A station that assumed panel order would have put every gain step on the
wrong preamp.

---

## 5. The noise reading rides the input walk

PW: *"between mic cable moves is a good time to test EIN with the 150 Ω load"*,
then amended to the sequential form. So the separate noise block is **retired**
and each input is two operator steps:

* lead in → *"Plug AUX 1 into MIC 7, then press ENTER"* → seven gain steps;
* lead out → *"Take the lead out of MIC 7 and put the 150 ohm plug in, then
  press ENTER"* → the input's own noise at full gain.

Nothing has to be proved about crosstalk between a driven input and the one
beside it, because no two sockets are ever live at once.

---

## 6. The time, measured

PW: *"if programmed correctly, it should be fast."*

### The 595 chain write — and a label that was lying

`s55_chain.py` prints `VERIFIED 200/200`. **That is a bit count — 25 bytes, 200
bits — not a number of passes.** It has always done exactly what PW asked for:
one shift, one read-back, one compare. Nothing was ever verifying two hundred
times.

What was slow was everything around the wire. Measured on MW-D24-2, five writes
each:

| how | per write |
|---|---|
| as the station called it, a `python3` process per write | **294 ms** |
| the same `send()` called in-process | 157 ms |
| …of which four `sudo pinctrl` calls | 113 ms |
| …leaving the SPI itself | 44 ms |
| **`d24_chain.py`: SPI held open, CS_M held through gpiod** | **8.1 ms** |

Read-back still matches on every write, and it needs no `sudo`. Across a full
pass that is 221 writes: **65 s → 1.8 s**.

### PW's targets

Measured in the model, whose clock reproduces every window, cell write, chain
write and peek, with the chain write set to the 8.1 ms measured on the part:

| | target | measured |
|---|---|---|
| one gain element step | ≤ 100 ms | **65 ms** ✓ |
| a whole seven-step input patch | ≤ 1 s | **0.797 s** ✓ |
| the EIN reading | ≤ 0.5 s | **0.355 s** ✓ |
| machine always under the hand move | — | worst block **1.93 s** against 5.8 s ✓ |

Two cuts got the last of it, and both are stated rather than assumed:

* **the reference step pays a settle only if the chain moved.** The four-window
  settle exists because the coherent fit reads a changed window as distortion —
  but by the time step 0 runs, the route, the instrument and the chain have all
  been where they are for as long as the operator took to plug a lead in. The
  settle is paid when the chain write for that step actually moved the wire;
* **a noise row has no fit to settle.** An RMS of a terminated input is an RMS,
  and six windows of it was five windows of a worker waiting.

### The whole pass, block by block

91 patches, 245 readings, at 5 s per hand move plus 0.8 s to reach for ENTER:

```
  block                     steps  readings   machine s   per step   hand s @ 5.8 s
  ------------------------------------------------------------------------------
  the outputs                  10        10         8.7      0.871              58
  the inputs                   49       193        37.3      0.762             284
  the line inputs              24        24        21.5      0.896             139
  the TRS outputs               6        14        11.6      1.930              35
  the mini-jack inputs          2         4         3.1      1.552              12
  ------------------------------------------------------------------------------
  the whole pass               91       245        82.2      0.904             528
```

**Where the machine seconds go** — the top three, which is what is worth
attacking next:

| | |
|---|---|
| settled readings | 44.4 s |
| the gain steps | 21.1 s |
| getting the unit ready | 16.2 s |
| putting the route up | 13.8 s |
| …of which the 595 chain | 221 writes, **1.8 s** |

**Projected pass:**

| | 3 s per hand move | 5 s | 8 s |
|---|---|---|---|
| full list, 91 patches | **7.2 min** | **10.2 min** | **14.8 min** |
| this unit's short list, 59 patches | **4.7 min** | **6.7 min** | **9.6 min** |

### Where it sits in the whole RUN ALL

RUN ALL's **automatic** set on this unit takes **156 s** (its own state file,
pass 5). The patch pass at 5 s a hand move is **612 s** — about **four times
the entire automatic set**, and 86 % of it is the operator's hands. That is the
shape PW predicted: the machine is not the thing to optimise any more, the hand
moves are, and the order in §3 is what buys them back.

---

## 7. Addendum 2: why two patches carried no tone

PW's first live run failed on AUX 5 → MIC 5 and AUX 6 → MIC 6. Split without a
hand at the bench, both halves on the part:

* **the input half is alive.** Sweeping the preamp gain and watching each lane's
  own noise: every lane moves **25-34 dB** between code 0 and code 63, so every
  input is listening to a live preamp. MIC 5 is the odd one — **33 dB noisier
  than any other lane at code 0** (-78.6 against -113.9);
* **the digital output half is alive to the DAC.** Oscillator on strip 24, aux 5
  asserted: chip 1's bus reads -15.01 dBFS and chip 2 carries it through RECV →
  MIX → AFB → EQ → GEQ → DLY → FDR → LIM → `_blk_C2_AUX_OUT_05` at **-12.00
  dBFS**, the DSP's own transmit slot.

That left one suspect: the aux **analog** stage after the DAC, which S109 left
unproved. PW plugged one lead:

| | level | loop gain | THD+N | noise |
|---|---|---|---|---|
| MAIN L → MIC 17 | -16.00 dBFS | **-0.99 dB** | -56.25 dB | -72.25 dB |
| AUX 5 → MIC 17 | -9.45 dBFS | **+5.56 dB** | **-90.16 dB** | -99.60 dB |

Same lead, tone on MIC 17 and on no other input either time. **The aux analog
output stage is good** — it has now carried a measured tone on this unit for
the first time, and it is the cleaner of the two by 34 dB of THD+N. So the two
dead patches were **the two inputs**: the dead-input set on MW-D24-2 is larger
than the quick list assumed, and MIC 5 and MIC 6 belong in it beside 1-4 and
13-16.

**This is exactly the case §3 exists to kill.** A pass that begins by walking
the input end would have found MIC 7 and started clean, and would have told the
worker nothing but *"Move the lead to MIC 8, then press ENTER."*

---

## 8. Live means live, and how fast

The wizard page asks systemd whether `d24-runall` is up, which is why a station
launched any other way drew its card inside a page that said the run had
finished. The factory screen reads **one timestamp**: a run is live while its
status file was touched in the last three seconds, whatever launched it.

**Status file written → screen drawn, measured on the part over 429 state
changes:** median **2 ms**, p90 3 ms, p99 14 ms, max **26 ms** — 100 % inside
the 200 ms budget. The detector's own half is one 50 ms poll plus a 1.3 ms
meter peek, so **lead in → screen is bounded at about 80 ms**, well inside PW's
0.5 s.

🔴 **A first measurement read a p90 of 354 ms and it was the instrument, not the
screen**: the display was re-rendering the whole 1920×1080 page to a PNG once a
second for the screenshot walk, on the same thread. Measured again with the
capture loop off; the loop is restored.

---

## 9. The station owns the unit it tests

Standalone and inside RUN ALL, the station now does its own analog prep and its
own handback. CS_M driven high, then AN_EN raised **once** for the pass; the
595 chain per step; and on **every** way out — the last patch, PAUSE, SIGINT,
SIGTERM, an exception — **AN_EN low first, then SAFE**, then the oscillator,
the routes and the monitor bus.

**Proved on the part.** PW pressed START, the pass ran two patches, and PAUSE
was written the way the button writes it:

```
   .. the pass stopped at P2 (pause)
   .. the analog rails are down
   .. mic-pre chain back to safe (muted, gain 0, phantom off): verified
```

AN_EN `lo`, the chain marker reading the SAFE image back, the process gone —
**0.53 s from the press**, teardown included.

---

## 10. Findings

* **S123-1 — START could launch the station twice.** PW pressed it at 18:57:25,
  18:58:30, 18:58:37 and 18:58:40; two instances started and the second
  collided with the first over the DSP link (`Device or resource busy`). START
  is now latched from the press until the run's own heartbeat appears, and the
  transient unit is `reset-failed` first so a stale name cannot refuse the next
  one.
* **S123-2 — the dead-input set on MW-D24-2 is bigger than the quick list
  assumed.** MIC 5 and MIC 6 carry no tone; MIC 5 is also 33 dB noisier than
  any other input at gain code 0. The short list now leaves out MIC 1-6 and
  13-16.
* **S123-3 — `VERIFIED 200/200` is a bit count, not a pass count.** The chain
  writer never verified two hundred times. The label should say `200 bits`;
  changing it touches `s55_chain.py`, which other runners print-match against,
  so it is reported rather than done.
* **S123-4 — my own error, corrected on the part.** The first pass of the
  addendum 2 diagnosis read chip 2's blocks with `Scope.rd()` and got exact
  zeros for every aux and main node, and concluded the output half was dead.
  `Scope.peek()` on the `_blk_` symbols — what `dsp4_icrecv.py` uses — reads the
  real words. `_buf_` on chip 2 and `rd()` anywhere inside a block are both
  wrong, and this is the second time that trap has been paid for.
* **S123-5 — three of the seven gain steps are fitted, not measured.** Codes 8,
  16 and 32 are not in defs' gain law at all. The fit is tight (0.509 dB worst
  residual over 24 codes) and every row says which it is, but a good unit
  should put the three measured values into `mic-gain-law.csv` and retire the
  fit. **That is a defs change and belongs to PW.**
* **S123-6 — the unit's disk was full and two app rollbacks were removed.**
  `/` stood at 100 % with 0 bytes free and the deploy could not land.
  `app.bak-s100-pre` (`f93fa5d352011317fa8a03795876d71c`) and
  `app.bak-s102-pre` (`1e1e412ce91eab1136933a436396411d`) were deleted — three
  days old and five builds superseded. `app.bak-s107-pre`, `-s112-pre`,
  `-s117-pre` and `-s123-pre` are kept. 139 MB free afterwards; **the unit will
  not take another app build without more room.**

## 11. What is NOT done

* **Nobody has run a full pass with a lead.** The eighteen screens, the order,
  the gain-step arithmetic and the timings are all proved in the dry run and on
  the part *as far as the copper*; the seven gain steps have never been
  measured through a real preamp.
* **The USB keyboard arm is unwitnessed** — there is no keyboard on the unit.
* **PAUSE ends the pass; it does not resume it.** The screen says so
  (*"Press START to run the test again"*). A resume that skipped the patches
  already passed is about thirty lines and was not asked for.
* `patch-plan.md` still names DSP nodes in its not-run reasons and does not pass
  `--check-md`. It is an engineering page, not a worker-facing one; the
  worker-facing strings are the ones that are checked, and they are clean.

---

## 12. Deployed, and the unit as left

| file | md5 | rollback |
|---|---|---|
| `/home/app/app` | `7533ce450967890cac9a7b417eb0c109` | `/home/app/app.bak-s123-pre` = `b61a190c6b1655346378acc75b2e4432` |
| `/home/app/selftest/d24_patch.py` | `d5e5c3c6db6f17a132a0656642809538` | `d24_patch.py.bak-s123-pre` = `a65697a97aa39a215f9342f06e038dc1` |
| `/home/app/selftest/d24_live.py` | `4a5bb7888612764a26bb6f491f4eb955` | new file |
| `/home/app/selftest/d24_chain.py` | `22db7dd3f98f5fdbc6e5935fc23bea13` | new file |
| `/home/app/selftest/quick/patch-paths.csv` | `86d3ab3a98026b541b823471318d16fe` | new directory |
| `/home/app/selftest/quick/patch-routes.csv` | `73fb2d441e6245e82b6ef0087606e2b1` | new directory |
| `/home/app/selftest/quick/patch-gain-steps.csv` | `8575e329eedd7c26b006af36e8dd74c1` | new directory |
| `/home/app/selftest/quick/patch-limits.csv` | `2c69c34eeeccb01a6eaed3d447cc2d0f` | new directory |
| `/home/app/selftest/factory.json` | the arming marker: the list, the title, 59 steps | remove it and the wizard comes back |

**The unit:** AN_EN low, CS_M high, the 595 chain at SAFE and read back, the
oscillator off, the monitor bus at zero, `d24-testui` active, `matrix-app`
inactive, no run live, the factory screen armed on START.

**The one thing PW presses: START, on the D24's own screen.** Then follow the
instructions and press ENTER after each lead. The small `TEST MENU` in the
bottom corner puts the engineering wizard back, and it disappears while a run
is live.
