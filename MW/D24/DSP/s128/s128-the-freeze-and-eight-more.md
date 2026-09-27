provenance: AI-drafted 2026-09-27 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S128 — PW's first real pass froze at the analog station

**Unit:** MW-D24-2, serial `10000000830b03af`. **Bench:** the dsp machine on
`192.168.1.211` (Ethernet `ens9`, 100 Mb/s) and `192.168.1.133` (Wi-Fi
`wlp4s0`); gateway `192.168.1.254`.

**One sentence:** the freeze was the analog station's card going up as a DIALOG
in the one stretch of a pass that had no factory screen, and eight of the nine
other items were real — including NW3's packet loss, which is **the unit's own
display app** and not the bench.

---

## 1. The timeline

| time (BST) | what happened |
|---|---|
| 14:24:52 | PW pressed START. The serial-bus phase ran under the six setup pages. |
| 14:30:05 | the DSP phase started in the background; the panel loops began |
| 14:32:35 | the left panel loop graded 12 rows, the right 32 |
| 14:32:46 | `prompt.json` kind `station`, "Station 3 - Analog paths" — **and no `live.json` from that moment on.** The net phase started under it and ran its 116 s. |
| ~14:33 | PW read "press enter to start audio test", pressed ENTER, and nothing moved |
| 14:36 | the hub stopped the run |

`evidence-1436/` is in `data/` here, byte for byte as the hub took it.

---

## 2. Item 1 — THE FREEZE. Root cause, and it is one line

`d24_runall.one_pass()` called the analog station's walk with **no screen**:

```python
timing['manual'] = run_manual(a, rows, state, ignored, glass, passno,
                              only=PATCH_STATIONS,
                              t0=timing.pop('_manual_t0', None))
#                             ^ no live=, no keys=
```

`_walk()` posts the station card before the station runs. With `live is None`
`station_card()` falls through to `glass.ask(...)`, which writes `prompt.json`
— **and the armed factory display draws no dialogs at all.** So the card went up
where nothing could draw it and nothing could answer it.

There were three screens in a pass, not one:

* `setup_screen()` built one for the setup pages and the panel loops;
* `overlapped()`'s `finally` **took it down** (`live.clear()`), with a comment
  saying the analog station builds its own;
* `patch_station()` built the third — but only *after* `_walk` had already
  posted the card.

Between the second and the third there was a stretch with no `live.json`, and
the card is posted in exactly that stretch. That is the whole fault. It is the
same shape as S127's: a card posted as a dialog where the glass draws none.
S127 fixed it for the panel stations by passing `live` down; the analog station
was the one call site left.

**Why the glass said "starting..."**: `FactoryView._primaryPressed` latches
`true` on a START press and is only cleared when a status file arrives asking
for ENTER. With no `live.json` the view fell back to `DrawIdle(armed)`, which
draws the armed page — and the latch made its button read `STARTING...`. The
screen was telling the truth: START had been pressed and nothing had come back.

### The fix

**ONE screen belongs to the whole pass.** `pass_screen(a, glass)` builds the
`Live` and the `KeyWatch` once, caches them on `a`, and hands the same pair to
every station; `drop_screen(a, words)` is the only thing that takes it down.
`overlapped()` no longer clears it, `one_pass()` passes it to the analog walk,
`patch_station()` uses what it is given, and `_walk()` asks for it itself if a
caller forgot — that last one is the backstop for the whole class of bug.

### Proved on the part

Driven through the app's own touch stack (`/dev/uinput` → libinput → Avalonia →
`FactoryView.OnPrimaryPressed` → `command.json` → the runner), so the press goes
in where a worker's finger goes in. Run 1, 15:33:02:

```
15:33:02 pressing the armed START
15:33:04 SCREEN [waiting] Station 1 of 3 :: Next: front panel switches. ...
15:33:08 SCREEN [waiting] Right switch panel :: On the RIGHT switch board, ...
15:35:45 SCREEN [waiting] Station 3 of 3 :: Next: analog paths. ... Press ENTER
15:35:59 SCREEN [waiting] 1/59 :: Plug AUX 1 into MIC 7, then press ENTER.
...      the 59-patch walk, answered on the glass
15:37:00 report written, rails down
```

`screens/08-...png` is the screen PW could not get past, now with an ENTER
button on it. The whole pass, START to report, on the glass.

---

## 3. Item 2 — the network tests did NOT block the station

The hub read `factory.log` as the net set running in the foreground in front of
the ENTER. It did not. The station card was posted at 13:32:46Z and the net
phase's first test is stamped 13:32:46Z as well: they were up together, which is
ruling (a) working.

What made the log read the other way is real and is fixed. `run_auto()` streamed
the **subprocess's** stdout straight through, unprefixed, while only its own
progress lines carried the `[net]` tag. So a background phase wrote 40
unmarked lines into the same log as the foreground. Every line of a background
phase is now tagged with its phase, so the evidence says which half of the pass
wrote it.

**The station did block, but on item 1, not on the network.**

---

## 4. Item 3 — SIGTERM and SIGINT

`d24_runall.main()` turned both signals into a bare `SystemExit`. That released
the run lock through `atexit` and did nothing else: no report, nothing on the
glass, and the rails wherever the last `finally` left them.
`d24_patch.py --patch-only` has had a proper handler since S127; the factory
START goes through `cmd_factory_run` → `RA.main()`, which did not.

Now a `Stopped(BaseException)` is raised — BaseException so nothing in the file
catches it by accident, and the `finally` blocks that lower the rails and tear
the station down still run on the way past. `main` catches it and does the four
things: rails down (again, idempotently), the report written with **"This pass
did not finish"** at the top of it, the lock released, and one plain sentence on
the glass with START under it.

---

## 5. Item 4 — the display crash. SOLVED, from two cores

Two SIGSEGVs on PW's day, both with **no managed stack trace** — the fault is in
native code, and a managed trace is all the app's own trace file can give:

| time | CPU consumed before it died |
|---|---|
| 12:52:47 | 27 min 30 s |
| 14:26:28 | 9 min 43.6 s |

(The 36 SIGABRTs that followed the second one are a different fault — the
`FactoryView.SetBar` width, which the hub has already fixed and deployed,
`611d9b2`, md5 `c18d2c00…`. It has not recurred.)

### It reproduced, twice, and it left a core both times

Core dumps went on the service first (`LimitCORE=infinity` plus a real
`kernel.core_pattern`; both files in `unit-config/`). It then crashed twice
during this session's own proof runs, at **1 min 30 s** and **2 min 18 s** of
CPU — far short of PW's 9 and 27 minutes, because these runs drove the screen
hard. Both cores have the SAME stack, to the same offsets:

```
Program terminated with signal SIGSEGV, Segmentation fault.
#0  0x…ca9c in ?? () from libSkiaSharp.so
#1  0x…b920 in ?? () from libSkiaSharp.so
 …
#10 0x…8f1c in sk_image_encode () from libSkiaSharp.so
#11 0x… in ?? ()                      <- managed, no symbols
```

**`sk_image_encode` is the PNG writer.** The only thing in this app that encodes
an image is `App.TryScheduleSingleViewCapture`'s `bitmap.Save(capturePath)`.
The crash is the screen capture.

### What the capture is

`/etc/systemd/system/d24-testui.service.d/s105-capture.conf` set
`MX_DRM_CAPTURE_PATH` and `MX_DRM_CAPTURE_MS=1000`, which puts
`TryScheduleSingleViewCapture` into a `while (true)` loop: render the whole
1920×1080 visual tree into a **new, never-disposed** `RenderTargetBitmap` on the
UI thread, then PNG-encode it to the SD card. For ever. It is an S105
diagnostic, and it was still on a unit being handed to a factory worker.

### What it costs, measured

| reading | capture ON (as deployed) | capture OFF (same binary) |
|---|---|---|
| CPU, steady state | **42.7 % of a core** | **5.3 %** |
| RSS over 6 min | 241.8 → 248.4 MB, plateaus | 225.0 → 230.5 MB, plateaus |
| ICMP loss to two hosts | 2.7 – 10 % | **0.0 %** |
| UI-thread stall | ~180 ms every 3.02 s | none measurable |
| SIGSEGV | twice in 25 min of driven use | none since |

RSS and `CmaFree` are both stable, so it is not a leak that exhausts memory —
it is a native fault in the encoder on a surface the UI thread is also drawing
into, made likely by doing it several hundred times an hour for no reason.

### Done on the unit

The drop-in is **removed** (kept at `/home/app/s128/s105-capture.conf.removed`).
`s123-latency.conf` is left: one CSV line per screen change costs nothing.
Core dumps stay enabled, so the next one of any kind is catchable.

### What the app fix needs, in mx26 `src/sw/app`

1. **`App.axaml.cs`, `TryScheduleSingleViewCapture`: the `RenderTargetBitmap` is
   never disposed**, in either the one-shot or the loop. It is `IDisposable` and
   holds a native Skia surface of 8.3 MB at this panel size. Wrap both in
   `using`, and allocate ONE bitmap outside the loop and re-render into it.
2. **The periodic capture must not exist as a `while (true)`.** A session that
   wants a witness wants ONE capture when it asks for one: a trigger file, or a
   request the runner can make. Until it is on demand, the drop-in stays off the
   unit — and a dispatched session loses its screenshots, which is the price.
3. **`FactoryView`: `_primaryPressed` must not latch for ever.** If no status
   file arrives within a few seconds of START, the button should go back to
   START. A worker who sees `STARTING...` and nothing else has no move left —
   that is what PW was looking at for four minutes (§2).
4. **`FactoryView`: the instruction row is 320 px and the font is 104/118, which
   is TWO LINES.** A longer instruction is drawn straight through the status
   line under it — witnessed, `screens/run1-08-station3-card-overflowing.png`.
   Either shrink to fit or clip; the runner now keeps its own budget (§8) but
   the view should not draw a page that cannot be read.

## 6. Item 5 — the USB page named the wrong sockets

PW: *"there are 2 usb sockets on top (analog board), back (digital board) socket
is currently occupied with touch panel."*

The page said *"the left socket of the double USB pair on the rear panel"* —
wrong panel, wrong board, and it sent the worker at the one socket they must not
touch. The catalog has had rows 130 and 131 against the **Analog** board all
along; "rear" was invented in `d24_runall.NAMES`.

The unit's own topology, read off it:

```
Port 001: Dev 002, Class=Hub (SMSC/Microchip USB2514)
    Port 002: ILI Technology Multi-Touch Screen   <- the touch panel, rear
    Port 003: Chipsbank CBM2199 Flash Drive       <- top panel
    Port 004: Chipsbank CBM2199 Flash Drive       <- top panel
```

Changed:

* **one setup page instead of two**: *"Put a USB memory stick into each of the
  TWO USB sockets on the top panel, then press ENTER."* Which of the two is hub
  port 3 and which is port 4 is not asserted — asserting it wrongly is how the
  rear-panel sentence happened — and the new `usb_pair:3,4` reading names the
  empty one if there is one. Rows 130 and 131 are still graded one port at a
  time under the patch pass, unchanged.
* the report name is now **"top-panel USB socket (hub port N)"**.
* a sentence the vocabulary check can see: *"The USB socket on the back panel is
  the touch screen's. Leave it alone."*

### Is the touch panel graded, and how?

**Yes, twice, and neither is a new test.**

1. **It enumerates.** The ILITEK controller is on hub port 2 and `lsusb` sees
   it. Its catalog row is 169 (Digital J4), which S119 moved to `QC` as a
   board-level test at the assembler; that ruling is not reopened here.
2. **Every ENTER in the pass is a touch that worked.** The factory screen has
   one button and the only way to press it is the touch panel. A pass that gets
   past its first setup page has a working touch panel by construction, and a
   pass that cannot get past it has proved the opposite. That is the strongest
   grade available and it costs nothing.

What neither proves is the panel's *edges* or its accuracy — nothing on the
bench does, and nothing claims to.

---

## 7. Item 6 — the encoder step showed the wrong page

`panel_station` wrote ONE standing page for the whole loop and never touched the
instruction again, so a step that asked for something else left the wrong
sentence on the glass. PW's pass sat on *"Press the button on the front panel
that is lit."* for 30 s while the runner waited for a detent.

Every step now writes its own instruction: the sweep's named button, the retry
after an indicator stayed dark, and the encoder.
`screens/07-...png` is the encoder page on the glass.

---

## 8. Item 7 and HUB ADDENDUM 1 — every switch on both boards

PW: *"led test was only one switch board, and didn't cover all switches."*

### Coverage, reconciled against `defs`

`data/panel-coverage.md`, generated by `panel_coverage.py` from
`defs/products/d24/fw.csv` — which is sectioned by `MCU` rows, so the board of
every control is the definitions' own answer and not the loop's. It reconciles
BOTH ways and `--check` fails if anything is unaccounted for.

**Switches: 20 of 20 walked** — 6 on the left board (MONO AUX, STEREO AUX, FX,
EQ, AUX ON FADERS, OVERVIEW) and 14 on the right. **Indicators: 20 of 32
graded**, and each of the 12 is named with its reason: the 8 encoder-ring LEDs
and the 2 always-lit white rings need a yes/no question this one-button screen
cannot ask, and the 2 boot LEDs are driven by the processor's boot pin, which
nothing the host writes can light. The pass-throughs (talkback, mini-jack sense,
temperature/blower/fan) have no matrix cell bound in the definitions, so the
host can neither read nor light them.

So no step was missing. **What was missing was the worker being told which
board they were at**, and that is enough to produce exactly what PW saw.

### Why

Both boards decode the SAME cell `Sys001Skin001` with the SAME indices 1…6
(finding S120-1, still open — PW's Q2 was never answered). For the first six
steps of either loop an indicator lights on BOTH boards and the key code that
comes back does not say which board sent it. S120 shipped that with one
mitigation: *"the two stations are separate, the operator is told which panel
they are at."*

Then **S125 gave the two stations one card** (they are the same piece of front
panel and the operator is already standing there) and **S127 gave the loop one
standing page** reading *"Press the button on the front panel that is lit."*
Between them the one place a worker was ever told which of the two boards to
work had gone. A worker who stays on the board they started on presses that
board for all twenty steps: the six shared indices score, and the other fourteen
do not. PW's pass reads exactly like that — the left board's six all PASS on
codes 1…6, and the right board's indices 12, 13 and 14 (MONITOR, REC/PLY, STUDIO
CTL) each timed out at 30 s with no key code at all.

### Fixed

The board is named in the step's own words and in the status line, on every
step, with no extra press:

```
RIGHT switch board: press the lit button, FX MUTE. The RED ring should be lit.
LEFT switch board: the white pair did not light. Press AUX ON FADERS anyway.
Work the RIGHT switch board. Press the button on it that is lit.
```

### What still cannot be told apart, and it is not this repo's to fix

A press on the OTHER board's button of the same index 1…6 still scores as
correct. That is S120-1 and the fix is a cell of the left panel's own, which is
a `defs` change and two lines in the left board's `matrix.cs` — and it fixes a
product defect as well, because in the product a press on the left panel moves
the skin as if a right-panel button had been pressed. **PW's Q2 from S120 is
still owed** (see §12).

### The two-line budget

`FactoryView` draws the instruction at 104 px with a 118 px line height in a
320 px row: **two lines, about 100 characters.** The analog station's card was
253 characters and came out five lines deep with "Station 3 of 3" printed
through the middle of it — the first time it had ever been drawn on the glass,
because until S128 it was a dialog. `d24_live.GLASS_MAX_CHARS` is that budget,
`Live.set()` says so in the log when an instruction exceeds it, and the card now
puts the kit list in the grey second line where there is room.

---

## 9. Item 8 — NW3: it is the UNIT, and the bar does not move

The hub asked whether 3–6 % loss to `192.168.1.211` is the bench (two interfaces
on one host) or the unit. **It is the unit, and it is the display app.**

### The reading that says so

PW's raw log, three passes, two targets, run concurrently:

| pass | bench host `.211` | gateway `.254` |
|---|---|---|
| 1 | 194/200 received, 3 % | 194/200 received, 3 % |
| 2 | 188/200, 6 % | 188/200, 6 % |
| 3 | 192/200, 4 % | 192/200, 4 % |

Identical counts towards two different hosts. No path can do that.

Re-measured with `ping -D`: the losses are **two packets every 3.02 s**, at the
same instants towards both targets — a ~180 ms window in which the unit answers
nothing. At `-i 0.05` it is four packets every 3.04 s; at `-i 0.02`, eight. The
window is fixed; only the number of packets in it changes.

**The loopback is clean**: 0.0 % to `127.0.0.1` over 200 packets. So nothing
reaches the socket, the cable or the switch.

### A/B on the same unit, same bench, same binary

| | bench host | gateway |
|---|---|---|
| `d24-testui` running | 6.7 %, 7.3 %, 8.7 % | 7.3 %, 4.7 %, 5.3 % |
| `d24-testui` stopped | **0 %, 0 %, 0 %** | **0 %, 0 %, 0 %** |
| restarted | 2.7 %, 6.7 % | 6.0 %, 10.0 % |

Narrowed to the one environment variable: the same binary, started with
`MX_DRM_CAPTURE_PATH`/`MX_DRM_CAPTURE_MS` **absent**, measured **0 %, 0 %, 0 %**
on three runs of 150 packets. That is §5's periodic screen capture: the UI
thread stalls for ~180 ms every 3 s while it renders and encodes a 1920×1080
PNG, and the echo replies that arrive in that window are lost. **The same
diagnostic is what SIGSEGVs the display**, which is why items 4 and 8 have one
fix between them.

### What changed in the test — and the bar did not

`--nw3-runs`, the two targets and the 0 % / 5 ms bar are all unchanged. NW3 now
also takes a **loopback control** and reports **when** the losses happened, so a
FAIL says which of the four possible things it is instead of leaving a reader to
guess. When the losses are evenly spaced toward every target at once and the
loopback is clean, the evidence says so in as many words.

### A good unit passes on this bench

With the drop-in removed, on the same unit and the same bench, **NW3 PASS**:
0.0 % loss on three passes to each target, max RTT 0.867 ms, and 0.0 % on the
loopback control. Six runs of 200 packets, not one lost.
`data/nw3-pass-capture-off.txt`.

### And the two interfaces on one host

Real, and worth knowing, but not this. The dsp machine holds `.211` on `ens9`
(Ethernet) and `.133` on `wlp4s0` (Wi-Fi), both on `192.168.1.0/24`. It did not
produce the loss measured here — the gateway, which shares none of that, lost
the same packets at the same instants.

---

## 10. Item 9 — NW4's verdict now says why

It said *"the driving host's lo negotiates 0 Mb/s, so this is the path, not the
unit."* True, and it tells a reader nothing: `lo` is the LOOPBACK. Run with
`--local` the driving host IS the unit, `ip route get 192.168.1.219` is
`dev lo`, and the traffic never leaves the box.

Two different facts, now said differently:

* **loopback**: *"this ran from the unit to itself, so nothing was measured
  about its network socket"*, with the evidence explaining that a throughput
  test needs a second machine.
* **slow driving host**: *"the driving host's network card is only 100 Mb/s, so
  the bar cannot be reached whatever the unit does."* This bench's `ens9` is
  100 Mb/s, so **NW4 cannot be graded here even driven remotely.** That is a
  bench fact and is named as one.

---

## 11. A tenth defect, found by running it: the review screen hangs the pass

The first full pass driven from the glass finished, wrote its report — and then
`review()` posted `prompt.json` kind `review` and sat on it. The glass read
*"Finished"* with a START button; the runner held the run lock; pressing START
came back *"The test is already running."* The unit was stuck with no way out
but a terminal.

Same fault as PW's freeze, at the other end of the pass: **a pass that has a
factory screen has no dialogs**, because while `live.json` is beating the app
draws the factory screen and nothing else. The review screen is an engineering
screen and belongs to the wizard, which does draw dialogs.

Fixed at both ends: `cmd_factory_run` passes `--no-review`, and RUN ALL refuses
to open one on its own account whenever the pass built a screen, saying so in
the log. `end_screen()` now leaves the pass's own tally and a START on the
glass for every way a pass can end, not only the analog station's.

---

## 12. Open, and owed to PW

* **S120-1 / PW's Q2, still unanswered.** Does the left switch panel get a
  matrix cell of its own? Until it does, a press on the other board's button of
  the same index 1…6 scores as correct, and in the PRODUCT a press on the left
  panel moves the skin as if a right-panel button had been pressed. It is one
  `fw.csv` row plus two lines in the left board's `matrix.cs`. See §12 of
  `s120/panel-loop.md` for the three options.
* **The two yes/no judgements** (the always-lit rings, the encoder ring) stay
  NO DATA with the plain sentence. PW has not ruled. No YES/NO page was built.
* **MONITOR, REC/PLY and STUDIO CTL** (right board, indices 12–14) sent no key
  code in PW's pass. With the board now named on every step, the next pass says
  whether that was the worker at the wrong board or three real faults.

---

## 13. Proof, run by run

Every press below went in through `/dev/uinput` → libinput → Avalonia →
`FactoryView.OnPrimaryPressed` → `command.json` → the runner: the app's own
button, on the app's own screen. It does NOT exercise the ILITEK controller or
the touch cable — only PW's finger does that — and §6 says what that leaves.

### Run 1, 15:33 — the freeze, gone

A resumed pass, straight to the owed work. START on the glass → the front-panel
card on the glass → the right board's sweep, each step naming the board → the
encoder page → **the Station 3 card on the glass with an ENTER under it** → the
59-patch walk answered on the glass → report → rails down. Screens in
`screens/`; the driver's log in `data/`.

### Run 2, 15:42 — a whole pass from START, and the stop

START → six setup pages (one USB page, not two) → the panel loops with the DSP
phase under them → **the display restarted mid-run at 15:46:58 and the run
carried on** (next screen drawn at 15:47:14, taps still landing) → the Station 3
card → the first patch page with the rails LIVE. Then `systemctl stop
d24-factory`:

| | before | after |
|---|---|---|
| AN_EN (GPIO26) | `hi` — rails LIVE | **`lo`** |
| CS_M (GPIO27) | — | `hi`, chain back to SAFE, verified |
| `runner.lock` | present | **gone** |
| report | — | **written**, headed *"This pass did not finish: it was stopped."* |
| glass | the patch page | *"The test stopped before it finished - it was stopped. The unit is safe. Press START to run the test again."* with START |

The log also shows item 2's fix: every background line is now `[serial]` or
`[net]`, and the setup pages' own lines are not.

### Run 3, 15:50 — START again after the stop, to the end

START resumed the pass where the stop left it, walked the right board and the
analog station, and **ended**: pass 2 written in 230 s, 50 PASS / 0 FAIL / 26 NO
DATA / 88 not tested of 202 rows; rails down; chain SAFE; `runner.lock` gone;
`d24-factory` inactive; and the glass on *"No signal on any socket - call the
supervisor. / Give this unit to the supervisor."* with START under it. **No
review dialog** — §11. The report also carries the new name: *"top-panel USB
socket (hub port 3)"*.

The display SIGSEGV'd once during run 1 and once during run 3 (§5) and **the
run carried on through both**, which is the mid-run display restart proved twice
over without anyone arranging it.

### FAIL, SKIP and PAUSE

Forced through the same `Station.run()` the bench uses, with
`d24_patch.py --simulate --fault` (`data/sim-fail-and-skip.csv`,
`data/sim-pause.csv`):

| forced | result |
|---|---|
| a wrong gain step on MIC 5 | **1 FAIL**, and the walk carried on — 194 PASS after it, all 57 patches and 203 checks recorded |
| SKIP on MIC 6 | **8 SKIPPED** rows with the operator's reason, walk carried on |
| PAUSE on MIC 7 | the pass **stopped** at 50 of 203 checks, and what had been measured was written |

That is S127's rule — only PAUSE ends a pass — still holding under everything
S128 changed.

### What is NOT proved, and it needs PW's hands

**No patch was completed with a lead in it.** Nothing is plugged into MW-D24-2,
so the analog station's pre-arm found no socket with signal and the walk
recorded NO DATA, correctly, and stopped saying so. The station, its card, its
ENTER, its 59 pages and its teardown are all proved; **what a real patch reads
is not.** That is the one thing on the dispatch's proof list that hands do and
a driver cannot, and it is the HANDS line in the dispatch block.

Also not proved: **the touch panel itself.** Every press this session went in
through `/dev/uinput`, which is the app's input path but not the ILITEK
controller's. PW's finger is the only thing that tests that, and §6 says how it
is graded when they use it.

---

## 14. Deployed, and the unit as left

| file | md5 | rollback |
|---|---|---|
| `/home/app/selftest/d24_runall.py` | `57c49545a83605061d63f2d589f5b5f9` | `.bak-s128-pre` |
| `/home/app/selftest/d24_live.py` | `46369eb14cbbde421a4a2b6b6edecaaa` | `.bak-s128-pre` |
| `/home/app/selftest/d24_patch.py` | `aff9c4be993503ec83e22f60d197d9f4` | `.bak-s128-pre` |
| `/home/app/selftest/d24_selftest.py` | `77d57d9a063552318a9de24b659e154e` | `.bak-s128-pre` |
| `/etc/systemd/system/d24-testui.service.d/s128-cores.conf` | new | delete it |
| `/etc/sysctl.d/90-d24-cores.conf` | new | delete it |
| `…/d24-testui.service.d/s105-capture.conf` | **REMOVED** | `/home/app/s128/s105-capture.conf.removed` |

All four tools byte-identical to this repo. Nothing else touched: no catalog, no
app, no firmware, no CPLD, no `pair.conf`, and **`defs.lock` is unmoved — no
contract bump is owed.**

**The unit, every line read back at 15:58:**

* AN_EN **lo**, CS_M driven **hi**;
* `d24_patch.py --guard`: *"no run and no screen: nothing to do"*;
* the staged pair unchanged and unflashed — `chip1.ldr`
  `7f226919a5d181410c3804d92678da19`, `chip2.ldr`
  `9e8a1a9edf19a90ce7ac3df1586c00f6`, byte for byte what S126 left (**v2**);
* `matrix-app` inactive, `d24-factory` inactive, **`d24-testui` active with
  0 restarts**;
* `runall/` holds only `patch-results.csv`, `progress.txt` and `state.json` —
  **no live file, no prompt, no lock**, so START draws the armed page and runs
  a whole pass from the top;
* the factory screen **ARMED** (`quick`, 59 patches);
* the injected touch device destroyed and its FIFO gone;
* 969 MB free (the two 330 MB cores were read and deleted).

---

# PART TWO — the hotfix, and what PW saw on the right board

HUB ADDENDUM 2, after PW's second pass (16:04–16:14, stopped at patch 17 of 59).
The app of §5 is fixed and deployed: mx26 `ae8a545`, md5 `311994f5`, with the
bitmap disposed, the capture moved to an on-demand `capture.request` trigger,
the START latch timed out and the instruction row made to fit.

## 15. The missing ENTER

**The glass said "press ENTER" with only a PAUSE button on it.** The unit's own
artifact, `evidence-live-p13-161130.json`, patch 13 of 59:

```json
{"state": "verdict", "instruction": "Plug AUX 1 into MIC 9, then press ENTER.",
 "status": "Signal found - press ENTER.", "banner": "PASS",
 "banner_line": "MIC 7, terminated", "buttons": ["pause"]}
```

### Why

`buttons` is chosen from the STATE (`d24_live.buttons_for`), and
`buttons_for('verdict')` is `['pause']`. The pipeline is what leaves the screen
in that state, and it does it on purpose:

```python
nxt = self.next_patch(seq, bi, pi)
if nxt is not None:
    self.announce(nxt[0], nrows)                # state WAITING + next instruction
self.record(self.score_patch(rows, prep, raw))  # state VERDICT + last banner
```

The next patch's instruction goes up first so the operator never waits for the
scoring; the last patch's verdict is then written over the top of it. The two
together are the screen PW reviewed — "PASS / MIC 7, terminated" above "Plug
AUX 1 into MIC 9". What nobody noticed is that the second write also takes the
ENTER button off it.

**One path climbed back out, which is why it looked intermittent.** When the
lead went in, `detect()` re-set WAITING — but only for `prearm_ok` rows, and
`prearm_ok` is true only for a **tone row with no gain code**. So plain tone
patches recovered their button and **gain steps, the EIN plug and every no-tone
row did not.** The hint at the bottom of the same loop changed `status` and
nothing else, so it could not put the buttons back either.

The same artifact shows a second, smaller fault: `"status": "Signal found -
press ENTER."` on a patch with nothing in its socket. `_hinted` is an instance
attribute and was never reset per step, so a patch that followed one where the
tone was seen started with the hint already on.

### Fixed, in three places and one rule

**The state is what the screen is doing, and it must be said by whoever makes it
true.**

1. `Station.detect()` puts the screen into WAITING **once, at the top**, for
   every path into it — that is the fix, because every path into that loop is
   the unit waiting for a person. It also resets `_hinted`, which kills the
   stale "Signal found".
2. `Station.waiting()` carries `banner` / `banner_line` / `action` across, so
   WAITING keeps the reviewed pipeline screen. The app draws the banner off
   `banner` alone (`FactoryView.Draw`: `verdict = s.Banner.Length > 0`), never
   off the state, so it is the same picture with the right buttons under it.
   A screen that already offers ENTER is left alone — `CHECKLEAD` is one, red,
   with its own action line.
3. `Station.record(..., prompted=True)` keeps the state WAITING when the next
   patch is already on the screen, so the bad state is never written at all.
   With no prompt up — at a block boundary, where a lead change is not prepared
   across — it stays VERDICT and **clears the instruction**, because a verdict
   banner over the instruction of the patch just measured tells a worker to do
   again what they have just done.
4. The hint uses `waiting()` too.

### Proved: every screen that asks for ENTER has one

`glass_buttons_check.py` runs the dry run with a real `live.json` behind it,
hooks `Live._flush` so it sees **every** screen the pass writes rather than
polling for a sample, and checks one rule: *an instruction that asks for ENTER,
on a screen where the unit is not itself working, must come with `enter` in
`buttons`.*

| run | screens | asked for ENTER | had one |
|---|---|---|---|
| whole list | 362 | 219 | **219** |
| K1 — XLR tone, XLR gain step, EIN plug | 202 | 126 | **126** |
| K2 — TRS jack | 33 | 17 | **17** |
| K3 — mini-jack | 13 | 5 | **5** |
| K4 — line (jack-to-XLR) | 123 | 71 | **71** |
| K2 + `--fault mispatch:MIC 2` — wrong socket | 44 | 28 | **28** (6 `checklead`) |
| K3 + `--fault dead:MINI-JACK 2` — no signal | 14 | 8 | **8** (2 `checklead`) |

Every row type the hub listed, and `verdict` no longer appears as a resting
state at all. Before the fix the same check found **30** screens asking for
ENTER without one.

## 16. The right board: nothing on either switch board can light

PW, twice: *"right board switch test didn't illuminate buttons, and exited after
a few button clicks"*, and *"the bottom 3 buttons never illuminated"*. They are
two different faults and the second one is much bigger than three buttons.

### "Exited after a few button clicks" — it had finished what it owed

Pass 2's right-board loop lit four buttons: FX MUTE, MONITOR, REC/PLY, STUDIO
CTL. The other ten had PASSED in pass 1 at 14:24, and `d24_panel.loop` skips a
button whose two rows have both already passed — PW's own rule of 09-26, *no
test runs twice for the same proof*. It had not exited early; it had walked
everything a **re-test** owes.

Not a fault, and nothing on the glass said so. The panel loop's page now carries
*"24 of the 36 checks on this board passed on an earlier run and are not
repeated"*, and the progress line says the same. A fresh unit walks all 14.

### "Never illuminated" — read off the shipping firmware, and it is all of them

`/home/app/fwbuild/H1S3/Core/Src/main.c` and `.../Core/Inc/matrix.cs`, which
S120 established are byte-identical to what is flashed:

* `MX_GPIO_Init()` configures **every** panel pin `GPIO_MODE_INPUT` with a
  pull-up — the indicator pins included.
* the block in `MainInit()` that made the indicator pins outputs is
  **commented out**. On H1S3 *and* on H1S4.
* H1S3 then makes exactly **two** pins outputs and drives them permanently
  high: `PB11` and `PF1`, each commented *"always on white led next to red
  led"*. **H1S4 makes none.**

`WrRadioLed()` runs on every sweep and writes ODR bits on pins that are still
inputs, which moves nothing. So:

**No indicator on either switch board can be lit by the host. The only lit
indicators on the whole front panel are the right board's two always-on
whites** — beside FX MUTE and beside REC/PLY.

That is the whole of PW's report. The loop lit 6, 12, 13 and 14; FX MUTE has an
always-on white next to it so it looked lit, and MONITOR, REC/PLY and STUDIO CTL
have nothing beside them — *"the bottom 3 buttons never illuminated"*.

It also settles the hub's question: **it is not the board-naming change and it
is not the shared-index aliasing.** Indices 12–14 exist only on the right board,
so nothing can alias them; and `d24_panel.py`'s `ALWAYS_ON` entry for rows 60
and 86 has been describing this firmware state since S120 without anyone
noticing it was the general case rather than an exception for two pins.

Measured on the part, this pass: the panel acknowledges every indicator write in
about 2 ms (`light 3 (FX) - the panel acked the write in 2.0 ms`), so the host
side and MH1's relay are not in question. The ack is now printed for every
step, because it is what separates *the write never arrived* from *the write
arrived and nothing lit*.

### What the test was claiming, and no longer does

The loop grades TWO rows from one press — the switch, and the indicator above
it, *"the white ring lit, and the operator pressed the button under it"*. That
inference is only sound if an operator who saw nothing light had a way to say
so. On the dialog they do: NOT LIT is one of the buttons. **On the armed factory
screen there are two buttons, ENTER and PAUSE, and no way to report a dark
indicator at all** — and the instruction NAMES the button, so a worker who can
read will press it whether or not anything lit.

So every indicator PASS this station has ever recorded on the glass is an
inference from a press, not a reading. From this session the indicator row is
**NO DATA** where the operator could not have said otherwise, with the reason in
the verdict: *"the screen named the button, and it has no way to say an
indicator stayed dark, so the press proves the switch and nothing about the
indicator"*. The switch row is unchanged — a key code is a reading.

The dialog path keeps the old behaviour, because there NOT LIT exists.

### Owed

* **FIRMWARE, both panel boards:** restore the output init in `MainInit()` (or
  fold it into `MX_GPIO_Init`) so `WrRadioLed()` can drive the indicator pins.
  Until that lands, no front-panel indicator can be graded by any test.
* **THE FACTORY SCREEN NEEDS A "NOT LIT" BUTTON**, or the two-button question
  this screen has never been able to ask. It is the same missing thing as the
  always-lit rings and the encoder ring (§12). With it, 20 of the 32 indicators
  become gradeable the moment the firmware is fixed; without it, none do.
* **The switch side of indices 12, 13 and 14 is still unproven.** They are in
  `rsw[]` (PC1, PF0, PC14) and they returned no key code in pass 1 — but nothing
  was lit to press, so that says nothing. Three presses would settle it.

## 17. Proof — one whole pass from the app's own START, 16:30–16:43

Unit reset first (`--reset-state`), so every switch on both boards was owed and
the walk was a FIRST pass, not a re-test. Every press went in through
`/dev/uinput` → libinput → Avalonia → `FactoryView.OnPrimaryPressed` →
`command.json` → the runner: the app's own button, on the app's own screen.

| | |
|---|---|
| START on the glass | 16:30:08 |
| six setup pages | one USB page, ENTER on each |
| **left switch board** | **14 checks, all 6 buttons lit and walked**, each page naming the board |
| **right switch board** | **36 checks, all 14 buttons lit and walked**, bottom three included |
| the encoder | its own page |
| Station 3 card | on the glass, entered by ENTER |
| the analog station | 13 pages, each with ENTER, each advanced by a tap on the app's ENTER |
| the network phase | under the station, `[net]`-tagged |
| end | report at 16:43:23, 790 s, rails down, chain SAFE, lock gone, FINISHED + START on the glass |

**All 14 right-board switches, with MH1's ack for each write** — the reading the
hub asked for, and it is the same 1.7–2.0 ms for the three that never light as
for the eleven that do not either:

```
light 12 (MONITOR)    - the panel acked the write in 1.8 ms
light 13 (REC/PLY)    - the panel acked the write in 1.9 ms
light 14 (STUDIO CTL) - the panel acked the write in 1.8 ms
```

The host side and MH1's relay are not in question. The write arrives; the pin
is an input.

### The one FAIL in this pass is the screenshots, and it is not a unit fault

NW3 read 3–4 %. The **on-demand** capture was armed for this run and the witness
harness requested 47 of them, several inside NW3's 128 s window — each one a
full-screen render and PNG encode. Re-measured immediately afterwards with the
capture armed and **no request made: NW3 PASS, 0.0 % on three passes to each
target, max RTT 0.607 ms.**

So the new drop-in costs nothing between requests and can stay on the unit: a
future session gets screenshots for free, as long as it does not take them
while it is measuring the network.

### What this pass does NOT prove

**No patch was completed with a lead in it**, so no patch was scored, so the
PIPELINE screen — last patch's verdict banner over the next patch's instruction
— never appeared on the glass. That is the exact screen §15 fixes. It is proved
over all 219 ENTER-asking screens of a full dry run, in every row type and in
the wrong-socket and no-signal cases, and it is NOT yet witnessed on the glass.
One lead in one socket closes it; that is the HANDS line.

## 18. Deployed, and the unit as left at 15:50Z (16:50 BST)

| file | md5 | rollback |
|---|---|---|
| `/home/app/selftest/d24_patch.py` | `94fae1b6e2d2d4af5ab26a3a20cb08cf` | `.bak-s128-pre` |
| `/home/app/selftest/d24_panel.py` | `108cdaa6c10202dfd8ff9ff29acf9e69` | `.bak-s126-pre` |
| `/home/app/selftest/d24_runall.py` | `bb8603209370258e3aa0fd6bb36f730c` | `.bak-s128-pre` |
| `/home/app/selftest/d24_live.py` | `90b2fc9548493be0b58a604928a35fd1` | `.bak-s128-pre` |
| `/home/app/selftest/d24_selftest.py` | `77d57d9a063552318a9de24b659e154e` | `.bak-s128-pre` |
| `…/d24-testui.service.d/s128-capture.conf` | new, and free when idle (§17) | delete it |
| `…/d24-testui.service.d/s128-cores.conf`, `/etc/sysctl.d/90-d24-cores.conf` | as PART ONE | delete them |
| `/home/app/app` | `311994f5e55760ed8547d906188014e4` (mx26 `ae8a545`, hub-deployed) | `app.bak-pre-ae8a545` |

All five tools byte-identical to this repo. No catalog, no firmware, no CPLD, no
`pair.conf`; **`defs.lock` unmoved, no contract bump owed.**

**Every line read back:**

* AN_EN **lo**, CS_M driven **hi**; `--guard`: *"no run and no screen: nothing
  to do"*;
* the staged pair unchanged and unflashed — `7f226919a5d1…` / `9e8a1a9edf19…`,
  what S126 left (**v2**);
* `matrix-app` inactive, `d24-factory` inactive, **`d24-testui` active with
  0 restarts** and no core since the capture went on demand;
* `runall/` holds only `patch-results.csv` and `progress.txt` — **no state
  file**, so PW's START is a FIRST pass and walks every switch on both boards;
* the factory screen **ARMED** (`quick`, 59 patches);
* the injected touch device destroyed and its FIFO gone;
* 757 MB free.

---

# PART THREE — the gain-step "regression", read-only

The hub asked, with PW mid-pass and the unit off limits: AUX 1 into MIC 9 and
MIC 10 now FAIL gain element 6 at 54.9 dB against an expected 48.0, where the
16:04 run passed the same steps at 48.5. Only change between them: the §15
hotfix.

**It is not the hotfix, and the readings are not shifted.**

## 19. Three readings of the evidence

### The whole hotfix diff is screen writes

`git diff 3dee36a0..HEAD -- tools/pi/d24_patch.py`, every non-comment line: a
new `waiting()` that calls `live.set`; `detect()` gaining a `status=` argument,
`self._hinted = False`, and one `waiting()` call; two `live.set` → `waiting()`
substitutions; `record(prompted=)` choosing WAITING over VERDICT and clearing
three display fields; `find_loop` passing `status=LOOKING`.

`gain_step`, `acquire`, `watch`, `_score_gain_step`, `Analog.chain`,
`Unit.osc`, `measure`, `SETTLE_WINDOWS`, `GAIN_SETTLE_WINDOWS`,
`GAIN_READ_WINDOWS` and `limits.csv` are **untouched**. Nothing in the diff
runs between a chain write and a reading.

### The readings are not shifted — eight of them are dead flat

Element 6, this run, in walk order:

| patch | socket | measured | from expected |
|---|---|---|---|
| P13 | MIC 9 | **54.9** | **+6.9 FAIL** |
| P15 | MIC 10 | 49.4 | +1.4 |
| P17 | MIC 11 | 48.1 | +0.1 |
| P19 | MIC 12 | 48.2 | +0.2 |
| P21 | MIC 17 | 48.2 | +0.2 |
| P23 | MIC 18 | 48.3 | +0.3 |
| P25 | MIC 19 | 48.2 | +0.2 |
| P27 | MIC 20 | 48.2 | +0.2 |
| P29 | MIC 21 | 48.3 | +0.2 |
| P31 | MIC 22 | 48.2 | +0.2 |

54.9 → 49.4 → 48.1 → flat. A regression in the shared gain path moves all ten
by the same amount; this is a transient on the first two patches of the block.

### The 16:04 run only ever measured those two positions

It was stopped at patch 17, so its whole sample is P13 and P15 — exactly the
two that are elevated now — and it has no later readings to compare against.
Everything before P13 is identical in the two runs: the same standing write
(567 cells), the same floors (15 lanes, −114.7 to −88.1 dBFS), and the same
P1–P12 verdicts.

One thing that reads confusingly and is worth knowing: **the pipeline prints a
verdict AFTER the next patch's prompt**, so the socket named in the line above
a verdict is the next patch, not the one being scored. The FAIL text names its
own socket (`row['in']`) and the PASS text does not — which is why 2888 looks
like MIC 10's verdict and is MIC 9's.

## 20. What actually changed, and the leading hypothesis

The app. The hub deployed `ae8a545` between the two runs, and with it §5's
capture went from a `while (true)` costing **42.7 % of a core with a ~180 ms
UI-thread stall every 3 s** to idle. The CM4 is materially faster and less
jittery during a reading than it was at 16:04.

`gain_step` changes **two** things and then reads:

```python
self.an.chain(self.an.step_image(r['send_pos'], code), ...)   # the GAIN, up
if self.an.wrote: self.u.mark_moved()
if drive is not None: self.u.osc(level_dbfs=drive)            # the DRIVE, down
...
self.u.measure(..., windows=GAIN_READ_WINDOWS,
               settle=GAIN_SETTLE_WINDOWS)                    # FIXED, 2 windows
```

The **code-0 reference** pays `settle_owed(SETTLE_WINDOWS)` — up to four
windows, 341 ms, counted from the change itself. Every **other** element pays a
fixed **two windows, 171 ms**, and `u.osc()` does not mark the wire moved at
all. Element 6 is the largest drive move of the seven, about 48 dB. If 171 ms
is not enough for it, the reading keeps part of the old, higher drive and reads
**high** — the right direction, the right element, and something that would
only start to bite once the host stopped being stalled into arriving late.

**That is a hypothesis, not a result.** It cannot be settled from the log,
because the numbers that would settle it were never in the log.

## 21. Prepared, not staged: the scorer says its numbers out loud

The per-step `notes` have always existed and have always gone only to the
results CSV, written at the end of a pass. So a reading of 54.9 dB in the
middle of a walk left nothing in `factory.log` but one verdict sentence.

Each gain step now logs, as it is taken:

```
gain element 6: measured +48.05 dB, expected +48.05 dB (fitted),
  drive -78.0 dBFS, lane -33.00 dBFS, reference -33.00 dBFS,
  settle 2 windows, 259 ms after the drive change
  (the meter, which is not what this is judged on, read -33.00)
```

`reference`, `settle windows` and `ms after the drive change` are new, and they
are the three the hypothesis needs.

**No scoring rule changed and no verdict moved.** The dry run against the
committed pre-hotfix baseline (`data/sim-fail-and-skip.csv`) is identical row
for row: **194 PASS / 1 FAIL / 8 SKIPPED of 203**, the same patches and the
same subs, with the same injected gain fault and skips. The ENTER check of §15
is still clean.

**Nothing is deployed.** The unit is PW's and the tools on it are unchanged
from §18.

## 22. Owed

* **PW's ruling before any measurement rule moves.** If the next run's log
  shows element 6 read short of its settle, the fix is one of: (a) count the
  gain step's settle from the DRIVE change, as the code-0 reference already
  counts its own — no constant changes, no cost; (b) raise
  `GAIN_SETTLE_WINDOWS` from 2 to 4 for the largest element only, about 4 s
  over a pass; (c) re-read an out-of-tolerance step and keep both readings.
  (a) is the one that follows a rule already in this file.
* **MIC 9 element 6 has no verdict worth trusting.** One re-read of that socket
  when the unit is free says whether 54.9 was a transient or a preamp element
  6.9 dB out.
