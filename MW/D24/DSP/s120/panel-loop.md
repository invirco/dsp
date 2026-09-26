provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S120 — the panel loop: a fast press → indicator round trip for the two switch panels

**The loop is built, and it needed no firmware change and no new wire.** Both
halves of the round trip are already in the shipping panel firmware and both are
one matrix cell: writing `Sys001Skin001` lights exactly one indicator, and a
press arrives on the same cell carrying the pressed button's index. The machine
part of press → indicator is **under 10 ms** against PW's 50 ms bar, measured on
the part. Stations 1 and 2, which S117 left with all fifty rows *not tested*, now
grade **44 of the 50**; the other six are named, row by row, with the reason.

What is NOT done: nobody pressed a button. The session has no hands at the
bench, so the loop is proven from both ends — the runner side against a scripted
key stream through the real glass protocol, and the bus side against the real
copper with the writes acknowledged — but the finger is PW's. The exact steps
are §7, and the block carries them as a 🔴 note.

---

## 1. The chain, end to end

### 1.1 The copper

    [button]  switch board (STM32F030R8)
                 |  MCU_TX  = digital MRX = dsp 'M MCU_P48'  (G2703)
                 v
              M MCU U8.14        <- also LOGIC U3.71, S MCU U7.42
                 |  M MCU U8.29  = PI_GPIO15 = CM4 J24.51 (UART0 RX)
                 v
              CM4 /dev/serial0
                 |  CM4 J24.55 (UART0 TX) = PI_GPIO14 = M MCU U8.32
                 v
              M MCU
                 |  M MCU_P47 = digital SRX = switch board MCU_RX  (G2702)
                 v
    [light]   switch board

plus one shared flow-control line, `LOGIC_BUSY` / `BUSY` / `MCU_BUSY` (G2632),
which a slave holds low while it is decoding.

**The CM4 is not on the panel bus, and that settles option (a) before it is
tried.** `SRX` and `MRX` appear at `digital:J17.47/.48` — the DSP card
connector — and at no `J24` pin at all. `J24` is the CM4 socket, and the only
`J24` pins on this path are `J24.55`/`J24.51`, the host UART to the M MCU. A
runner on the CM4 that wanted to talk the panel bus directly would need a wire
that does not exist on this hardware, and it would then be contending with the M
MCU for a line the M MCU drives. Read off `docs/d24-netlist-global.csv` G2632 /
G2702 / G2703, not assumed.

### 1.2 The protocol

Written down in full, as the errata item asked, in
[`panel-bus-protocol.md`](panel-bus-protocol.md) — a **candidate for `defs`**.
The three things that decide this design:

* **A press already carries its own identity.** `RdRadioSwitch()` puts the
  pressed button's radio index into `Sys001Skin001`'s transmit value and raises
  its flag; the master relays it to the host verbatim. There are fourteen
  distinct indices on the right board and six on the left.
* **An indicator already follows the host, and only the host.** `WrRadioLed()`
  lights the one indicator whose index equals the cell's RECEIVED value and
  turns the other thirteen off. A press does not move an indicator. So "light
  the next button" is one cell write, and the lit indicator stays lit until the
  tester moves it.
* **The slave handshake is hardware, not a timer.** A slave pulls its
  data-ready line low, the master raises that slave's data-request line and the
  slave transmits. Nothing polls on a clock, which is why the numbers below are
  what they are.

### 1.3 The latency of each hop, measured

All on MW-D24-2, 2026-09-26, `tools/pi/d24_panel.py --mode rtt` and
`s120/logs/rtt.txt`:

| hop | how it was timed | result |
|---|---|---|
| host → indicator | the cell line out, to the master's `+` ack. `CheckHost()` forwards the line to the bus, waits for its own transmitter to go idle and only THEN writes `+`, so the ack is stamped after the last byte reached both boards | **1.74 … 1.85 ms** mean over three runs of ten; 1.72 ms fastest, 2.47 ms slowest single write |
| press → host | not directly observable without a finger. Bounded by the only panel → host traffic a session can provoke: `&`, and the time to each identity line | **≈ 3 ms per slave** of the master's sweep (S MCU 3.2 ms, panel 6.0 ms, second panel 9.8 ms, cumulative) |
| host → slave → host | one complete cell out and a cell back, through a slave | **3.07 ms** mean of 10 (2.92 … 3.39) |
| the slave's own loop | the gap between two slaves' identity lines, less the 1.5 ms the 17-character string takes on the wire | **under 2 ms** |
| the master's heartbeat | `:`/`.` edges over 3.0 s | 250 ms — it does not gate anything here |

Adding the hops a press actually takes — the board notices it inside its own
loop (< 2 ms), the master relays it (≈ 3 ms), the runner decides (a dictionary
lookup), the write reaches the board (1.8 ms), the board applies it inside its
next loop (< 2 ms) — gives **under 10 ms** of machine time. Against a 50 ms
target, with the product's firmware untouched.

One number is deliberately outside that: **the glass redraws on the app's own
2 s tick** (`TestSkinStore.RunAll.cs`, `PollRunAll`). That does not slow the
loop, because **the indicator is the instruction**: the operator's eye is on the
panel, the next indicator lights 1.8 ms after the last press, and the dialog
text is a caption that catches up. It is the reason the loop is worth building
around the panel's own indicators rather than around the screen.

---

## 2. The options, ranked

| | option | press → indicator | firmware | risk | verdict |
|---|---|---|---|---|---|
| **c** | **the product's own cell path** | **under 10 ms, measured** | **none** | **none** | **CHOSEN** |
| b | a test mode in the M MCU or a panel that forwards key events and accepts indicator commands | the same — it would ride the same handshake | a new build and a reflash of a panel or the master on the only bench unit | a bricked slave on the only D24; a second firmware to keep in step with the matrix generation | rejected: it buys no latency, and the one thing it WOULD buy (panel identity, §4) is better bought in `defs` |
| a | the runner on the CM4 talks the panel bus directly | — | none | — | **impossible on this hardware**: no `J24` pin reaches `SRX`, `MRX` or `BUSY` (§1.1), and the line the runner would drive is the M MCU's output |

The bar was PW's: simplest, fastest, least code. Option (c) is one host tool and
no change to any part of the product.

---

## 3. The station, as built

One station per panel, TESTER-LED MODE, inside RUN ALL's existing manual phase.

**The loop.** The tester lights the indicator of the next button to press. The
operator presses the button under it. The key code that comes back grades the
switch row AND the indicator row together, and the next indicator lights. The
only judgement asked of the operator is the one a press cannot make: a button
whose indicator stayed dark. There is one button on the glass, NOT LIT.

**The order is a sweep**, and it is the catalog's own `order` column — the walk
S113 took off the workbook — so the hand crosses the panel once: FX MUTE, HOME,
MENU, +48, FEEDBACK, MUTE, SCENE, L, C, CH ASSIGN, R, MONITOR, REC/PLY, STUDIO
CTL on the right; MONO AUX, STEREO AUX, FX, EQ, AUX ON FADERS, OVERVIEW on the
left.

**What each outcome lands**, all seven proven (§6):

| what happens | switch row | indicator row |
|---|---|---|
| the right key code comes back | PASS, with the time it took | PASS — "it lit, and the operator pressed the button under it" |
| a DIFFERENT key code comes back | FAIL, naming both the button that was lit and the button that answered | NO DATA — not reached |
| nothing comes back inside the timeout | NO DATA — "no key code arrived within 30 s" | NO DATA — "the button sent nothing" |
| the operator presses NOT LIT, then presses the button | PASS | FAIL — "the ring did not light when the tester lit it" |
| the operator presses SKIP or IGNORE | SKIPPED / IGNORED | the same |

**Rows outside the sweep**, still in the station:

* **the two always-lit rings** (rows 60 and 86). `MainInit()` drives PB11 and
  PF1 high and leaves them; no write can move them. One question grades both:
  *"Two indicators are lit whenever the unit is on … are both lit?"*
* **the encoder** (row 90). One detent clockwise and one anticlockwise; the ring
  position is read off the bus each time and the row passes only when it has
  stepped BOTH ways. A ring that turns one way and not the other lands FAIL
  naming which way.
* **the encoder's eight indicators** (row 91). The tester steps them round
  twice and asks the operator whether all eight lit in turn.

**Rows the station reaches and still cannot grade** — six, each with its own
words on the report's human page, replacing S117's two blanket sentences:

| row | why |
|---|---|
| 55 | the red indicator is driven by the processor boot pin, not by the processor, so nothing the host writes can light it |
| 58 | the pedal path through this panel needs the pedal and its lead, which is the foot pedal station |
| 78 | no indicator is declared for this designator: the firmware table gives the C button one indicator pair and the loop grades it on row 77 |
| 92 | the talkback switch and its two indicators pass through the panel processor with no matrix cell bound |
| 93 | the mini-jack sense passes through the panel processor with no matrix cell bound |
| 94 | the temperature, blower and fan lines pass through the panel processor with no matrix cell bound |

**No test runs twice.** A button whose two rows have both already passed is not
lit again on a later pass; the sweep keeps its order, so the hand still crosses
the panel once.

**Cost.** 14 buttons and three extra questions on the right, 6 buttons on the
left. The machine time is under 10 ms per button; the wall time is the
operator's hand.

### How it is wired into RUN ALL

`d24_runall.py` gains one branch in `run_manual()`: a station in
`PANEL_STATIONS` is handed to `panel_station()` as a whole rather than walked
one dialog per row. Three small pieces support it:

* `Glass.ask()` is split into `Glass.post()` + `Glass.poll()` + `Glass.taken()`.
  A blocking `ask` cannot hear the panel; the loop posts the dialog and then
  asks the glass and the bus alternately, so a press ON THE UNIT ends the step.
  `ask()` is now `post` + wait and behaves exactly as before.
* `manual_step()` stops returning a blanket "no per-control read" for every
  panel row: rows the loop grades become `kind = LOOP`, the six it cannot reach
  keep BLOCKED with their own reason.
* two new options, `--panel-timeout` and `--inject-keys`.

**The app needs no change to work.** Its six dialog slots take their labels from
the prompt, and an id it does not recognise is upper-cased, so NOT LIT reads as
`NOTLIT` on the glass today. The one-line label is in mx26
(`TestSkinStore.RunAll.cs`, `SlotLabel["notlit"] = "NOT LIT"`); **the app was not
rebuilt or redeployed this session**, so until the next app deploy the glass says
NOTLIT.

---

## 4. 🔴 S120-1 — the two panels share one cell AND one index space

`Sys001Skin001` is the cell for **both** boards, and the left board's six
indices are 1…6, which the right board also uses for HOME … FX MUTE. Read off
the two `matrix.cs` files, which are otherwise the same file with different
tables, and off `matrix.h`, which gives both boards address 5412.

Two consequences, and the first is a product defect, not a test problem:

* **In the product, a press on the left panel moves the skin as if a right-panel
  button had been pressed.** Pressing MONO AUX sends index 1, which is HOME.
  Nothing in the firmware distinguishes them.
* **For the test**, writing an index of 6 or less lights an indicator on BOTH
  panels, and a key code of 6 or less does not say which panel it came from.

What the loop does about it: the two stations are separate, the operator is told
which panel they are at, and the report says plainly that a press on the other
panel's button of the same index would be scored as correct. Everything else the
station grades — a dead switch, a dead indicator, a switch wired to the wrong
index within one panel — is caught exactly.

**The fix is a cell of the left panel's own, which is a `defs` change and not a
change here** (this repo is a consumer). It is one row in `fw.csv` and one
address; the left board's `matrix.cs` then names that cell in its `rsw[]` and
`wled[]` tables instead of `Sys001Skin001`, which is a two-line firmware change
that also fixes the product. **Question for PW in §7.**

---

## 5. Three more findings from the same reading

**🔴 S120-2 — the panel firmware in Dropbox is a DIFFERENT matrix generation
from the panel firmware on the unit, and a rebuild from it would put the
2026-08-19 skin corruption straight back.** `main.c` and `matrix.cs` are
byte-identical between `_mx/MW/D24/FW/H1S3/` and `/home/app/fwbuild/H1S3/`.
`matrix.h` is not:

| artifact | base-id (`defs/tools/matrix_gen_id.py`) | `Sys001Skin001` |
|---|---|---|
| `_mx/MW/D24/FW/H1S3/Core/Inc/matrix.h` (Dropbox source) | `459349c04128` | **17553** |
| `/home/app/fwbuild/H1S3/Core/Inc/matrix.h` (what built the flashed image) | `e80ccab5d6d8` | **5412** |
| `MW/D24/MX/_matrix.csv` (this repo's contract, from `defs`) | `67d01aeb49f8` | **4698** |

That is the exact failure `matrix_gen_id.py` was written for, still live in the
canonical source tree. The corrected header exists only on the bench unit.

**🟢 S120-3 — the flashed panel images are the app's generation, read off the
binary.** Both `/home/app/firmware/H1S3.shex` and `H1S4.shex` contain
`MATRIX[] = {0, 5232, 5412, 5414, 5415}` as five little-endian words, and
neither contains the Dropbox generation. So the addresses this loop writes and
reads are the addresses in the firmware, checked against the part rather than
assumed. (This repo's own contract is a third generation and would write to a
cell no slave decodes — a tool that took the address from `_matrix.csv` would
light nothing and would look like dead hardware.)

**🟡 S120-4 — the two flash packs on the unit are addressed to each other's
slot, deliberately.** `/home/app/firmware/H1S3.shex` is 59956 bytes of
right-panel content (its identity string is `// H1S3 SW Right`) and its
extended-address record names slave **H1S4**; `H1S4.shex` is the mirror. They
are byte-identical to `fwbuild/right-slot4-H1S3content.shex` and
`left-slot3-H1S4content.shex`, whose names say why: on this unit the RIGHT panel
is in slave slot 4 and the LEFT panel in slot 3. The straight pair,
`H1S3.new.shex` / `H1S4.new.shex`, is the pre-swap build and would flash each
panel with the other's firmware. **Identity follows the content, not the slot** —
anything that ever keys on the slave slot to tell the panels apart will be wrong
on this unit. The loop does not: it never asks which panel answered (§4).

**🟡 S120-5 — the right panel's MONITOR indicator is driven high on every
transmit.** `Poll()` uses `PC0` as a scratch pin while it waits for the master
to drop data-request: it reconfigures the pin as an output and drives it high,
then puts it back to input. `PC0` is `wled[]` index 12, the MONITOR ring
(`fw.csv` `LED,Monitor,C0,P5,LD12;LD13`). So every key report and every identity
string flickers that one indicator. It is brief and nothing in the product reads
it, but it is a real defect in the panel firmware and it is the one indicator a
tester should not trust to be off. The loop is unaffected — it only ever asks
whether an indicator is ON.

---

## 6. What was proved, and how

**The runner side, against a scripted key stream through the REAL glass
protocol** (`prompt.json` out, `answer.json` in, answered by a stand-in for the
wizard) — `s120/logs/station-injected.txt`:

* **right panel, clean walk: 32 rows, all PASS.** 14 switch rows, 14 indicator
  rows, the two always-lit rings and the encoder's two.
* **right panel, faults: 32 rows, every fault class landed correctly** — NOT LIT
  then a press (switch PASS, indicator FAIL); a dead switch (both rows NO DATA,
  naming the timeout); a wrong key code (*"the tester lit +48 and the key code
  that came back was 9 (L)"*); an always-lit ring reported dark (FAIL); an
  encoder that turns one way only (*"the ring only stepped clockwise"*); the
  ring indicators reported dark (FAIL).
* **left panel, clean walk: 12 rows, all PASS.**

**The bus side, on the real copper with no finger** — `s120/logs/station-real-
bus.txt`. The same station driven against `/dev/serial0` on MW-D24-2 with a 3 s
per-button timeout: **32 rows in 48.6 s**, every indicator write sent and
acknowledged by the master, and **every row NO DATA naming the press that never
came**. Two things that matters for: the write path is live on the copper, and
**not one phantom key code** was parsed out of 48 s of heartbeat traffic —
which is also what a separate 20 s idle watch showed (`--mode watch`, zero
events).

**The cell addresses**, read off the flashed images rather than a header
(S120-3).

**The catalog**, before and after:

    before S120   50 of 50 panel rows  not tested
    after  S120   44 of 50 graded by the loop, 6 not run with their own reason

---

## 7. 🔴 For PW

**Q1 — the finger.** Nothing has been pressed. To walk a full loop on
MW-D24-2, at the bench:

    ssh app@192.168.1.219
    sudo systemctl stop matrix-app          # it owns /dev/serial0
    cd /home/app/selftest
    python3 d24_panel.py --mode loop --panel right    # then --panel left
    # the tester lights one indicator at a time; press the lit button.
    # type `notlit` + Enter for a button whose indicator stayed dark,
    # `skip` + Enter to pass one over. JSON verdicts land on stdout.
    sudo systemctl start matrix-app         # put it back

or through the glass, which is the real thing: START ALL, then station 1 and
station 2 as they come up. Expect the next indicator to light the instant the
last button is pressed; the dialog text is up to 2 s behind it and that is the
app's tick, not the loop.

**Q2 — S120-1, the shared cell.** Does the left panel get a cell of its own?
It is a `defs` change (one `fw.csv` row and one address), plus two lines in the
left board's `matrix.cs`, and it fixes a product defect as well as the test's
one blind spot. The alternatives are (b) leave it, and accept that a press on
the wrong panel's button of the same index scores as correct, or (c) give the
left board's six switches indices 15…20 in the existing cell, which needs no
new address but changes what the app receives. **Not decided here.**

**Q3 — S120-2, the Dropbox panel source.** The corrected `matrix.h` exists only
on the bench unit. Should the canonical tree be repaired from it, and should
`matrix_gen_id.py --compare` be made a gate on any panel build? Nothing was
written to Dropbox this session.

---

## 8. What was deployed

`/home/app/selftest/` on MW-D24-2:

| file | md5 | rollback |
|---|---|---|
| `d24_panel.py` | `c0bb5e5438b2afbcdbb3deac6b0761e3` | new file |
| `d24_runall.py` | `5536b590b7926a935c534b27b34b9550` | `.bak-s120-pre` = `f2cb40e76d22399c3972a1586d99dd58` (S119's) |

Nothing else was touched: no catalog, no app, no firmware, no CPLD, no
`pair.conf`. `defs.lock` is unmoved and **no contract bump is owed** — this
dispatch changed no definition and no generated artifact.

**Unit as left:** `matrix-app` inactive and `d24-testui` active, as S119 handed
it back; `Sys001Skin001` and `Sys001Enc001` both written back to 0, so no panel
indicator is selected — which is where a fresh panel boot leaves them. The DSPs,
the 595 chain, AN_EN and CS_M were never touched by anything in this dispatch:
the only device this session spoke to is the panel bus.
