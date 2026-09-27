provenance: AI-drafted 2026-09-27 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S129 — PW's bench findings and rulings

Unit MW-D24-2, serial `10000000830b03af`. Dispatch `HUB DISPATCH 2026-09-27
16:17Z` plus hub addenda 1–7.

Everything below is either a measurement taken on this unit on 2026-09-27 or a
trace through a declaration file, and each one says which. Where a thing is not
proved, it says that too.

---

## 0. What is done, what is blocked, and on what

| # | item | state |
|---|---|---|
| 1 | gain-step settle = PW's option (a) | **built**; the proof on the part needs one lead (HANDS 4) |
| 2 | end-of-pass summary screen | **built**, runner and app; needs the app deployed to be seen on the glass |
| 3 | left panel's own cell | **defs tagged** `defs-v2026.09.27.1`, host side **built**; H1S4 reflash outstanding |
| 4 | the panel indicators must light | **root cause NOT found**, and S128's was wrong. One look settles it (HANDS 1) |
| 5 | line input: reject an XLR | **built** — the discriminator is the polarity, proved 11 times over in PW's own pass |
| 5b | line LEVEL window (addendum 1) | **not built**: no number exists for the jack path's pad. HANDS 3 |
| 6 | every jack patch reads inverted | **root-caused from the netlist, all 22 sockets**; one alternative left to kill (HANDS 2) |
| 7 | MIC 7 | hardware **cleared by four measurements**; the remaining cause is the instruction, and that is fixed |
| 8 | NW2 / NW3 / NW4 (addendum 2) | NW2 and NW4 **built**; NW3 already targets the wired address, evidence hardened |
| A4 | hands-off steps take control | **built** for the one step that needs it (AL1), no app change needed — §10 |
| A5 | gain step ±0.25 dB | window **set**; the instrument is proved 20× better than it needs to be; the EXPECTED table is not |
| A7 | AL1 hands-off / talkback cell | AL1's cause **found and fixed** (§10.1); the talkback cell's **defs half is tagged**, its firmware half hits §3.2's wall |
| A2b | touch-panel row | **test built and PASSING**; the catalog row is upstream |

---

## 1. The gain step's settle — PW's option (a), and what the part says

### 1.1 What was measured first, because the ruling is about a number nobody had

`MW/D24/DSP/s129/tools/settle_probe.py` and the linearity sweep in
`floor_probe.py`, both on the internal path (the oscillator into the donor
strip, the measurement node on the same strip), so no rails, no lead and no
preamp:

* **the measurement node is exactly linear.** 31 levels from −96 to −6 dBFS: the
  node's RMS is the commanded level minus **3.01 dB at every single one** — the
  sine's own RMS factor and nothing else — and the coherent |H| reads
  **0.00 dB** at all 31. There is no knee at −24 dBFS or anywhere else in that
  range. (The "saturates above about −24 dBFS" note in
  `patch-gain-steps.csv` is about the ANALOG path, not the node.)
* **the node follows a 48 dB drive step inside one or two windows.** −30.00 →
  −78.05 dBFS, three repeats: settled to within 0.1 dB of final after 2, 2 and
  1 windows (111, 103 and 95 ms).
* **the node's repeatability is 0.011 dB.** Eight reads of the same level: spread
  0.011 dB at one read window, 0.006 at two, **0.000 at three and at six**.

So neither the instrument nor the oscillator is slow, and neither is the reason
a step reads high.

### 1.2 What is left, and it is the right shape

The readings that failed failed HIGH, and by more the bigger the element:
MIC 9 element 1 **+3.4 dB**, MIC 10 element 3 **+4.3 dB**, MIC 9 element 6
**+6.9 dB** — all at lane levels around −24 dBFS, all against a code-0
reference taken seconds earlier through the same lead, and all on a unit whose
same steps passed earlier the same afternoon. What is inside the loop and not
inside the instrument is the preamp and its coupling: a gain change steps the
preamp's operating point, and the settling of that step inside an 85 ms RMS
window reads HIGH and reads higher the bigger the step. The code-0 reference
never sees it, because it pays its settle **from the change**.

### 1.3 The change

`Analog.gain_step`'s non-zero branch paid a FIXED `GAIN_SETTLE_WINDOWS` (2) from
the `measure` CALL. It now pays `settle_owed(SETTLE_WINDOWS)` from the DRIVE
CHANGE, which is what the code-0 reference does.

**The budget is the reference's own, deliberately.** Counting
`GAIN_SETTLE_WINDOWS` from the change would pay LESS than the code did before,
not more — `watch()` is one SPI peek, so the change is only milliseconds old
when `measure` is entered — and it could not fix a reading that is short of its
settle. "As the code-0 reference does" is therefore read as the reference's own
constant. Cost: at worst two extra windows on six steps of thirteen sockets,
about **13 s** on a whole pass.

The per-step log line is kept and extended: it now says what was actually
**paid**, of what, so a step that read short of its settle says so itself rather
than being inferred from a constant.

### 1.4 What is still owed

**One lead.** The re-read of MIC 9 element 6 and the seven steps on MIC 9 and
MIC 10 cannot be taken without a physical patch. HANDS 4 in the dispatch block.

---

## 2. The end-of-pass summary (PW's ruling 2, refined by addendum 3)

> "after test completes, a complete grid of all tests should be shown, and
> remain until user exits, otherwise, no time to review anything."

**Built, both halves.**

* the runner (`d24_runall.summary_items` / `summary_pages` / `summary_screen`)
  takes the same state the report was built from — so the two cannot disagree —
  and writes ONE PAGE at a time into `live.json` as `summary`, a list of
  `[short name, verdict]` pairs, already ordered, already shortened. The order is
  the report's reading order: FAIL first, then what could not answer, then what
  was set aside, then the passes, then what was never run, and inside each band
  by catalog number so a row can be found.
* the app (`FactoryView`, mx26 `5cf57b2`) draws it as a grid and colours the
  verdict. PASS green, FAIL red, "could not answer" amber, NOT TESTED grey —
  amber and grey are kept apart on purpose.
* **the one button is EXIT**, in the primary place, with no timeout anywhere on
  that screen, and START is deliberately not offered while it is up, so no
  second pass can begin under a screen somebody is reading. EXIT on the last
  page leaves the armed START page rather than a second end screen.

**THE COUNT THAT FITS, as PW asked.** Measured against the panel the screen is
laid out for — 1920×1080, 80 px side margins, 50 px top and bottom, and 190 px
of buttons that have to stay visible — the grid has **1760 × 790 px**. At 24 px
type on a 28 px line that is 28 rows, and 440 px is a column wide enough for
`num  name  VERDICT`, so four columns: **112 tests a page**. The D24 catalog is
202 rows, so a whole pass is **two pages**, and the page number is the ordinary
n-of-N. Halving the type would fit it on one page and nobody at a bench would
read it. `--summary-rows` is the setting; 8 or fewer also writes the page as
plain text into a field the screen has always drawn, so a summary appears even
on an app that does not carry the grid.

**FOR THE HUB:** mx26 `5cf57b2` (on `main`, built clean here with
`dotnet build -c Release`) is what needs deploying. Until it is, a pass ends on
the summary's heading and page count but not its grid.

---

## 3. The left switch panel's own cell — S120-1, PW's ruling (a)

**`Sys001SwLeft001`**, landed in `invirco/defs` and tagged
**`defs-v2026.09.27.1`** (commit `3afe8d9`; the cell itself is in
`defs-v2026.09.27`, commit `238efed`).

* `common/cells/mx_master.csv`: **APPENDED**, never inserted. Row order is the
  address layout, so appending is the only safe place. Verified by expanding the
  D24 master before and after: 5004 → 5005 rows, one added line,
  `Sys001Skin001` still 4698, **`Sys001SwLeft001` = 5005, Shex `ikpu`**. D24
  matrix generation `67d01aeb49f8` → `6d3ff8fbb5bc`.
* `products/d24/fw.csv`: the six SW rows and six LED rows of the `SW_LEFT`
  section (H1S4) name the new cell and carry their radio index 1–6 in `Notes`,
  exactly as the `SW_RIGHT` section does. The `MxAdd` column mirrors the right
  board's 1195; that column is a legacy skin-group field and **not** a cell
  address — every right-panel row carries 1195 whatever its cell,
  `Sys001Enc001` included.
* `products/*/dsp-unmapped.csv`: one row per product, class `mcu-only`, taken
  verbatim from `gen_dsp.py --propose`. The generator refused to run until it
  was there, which is the no-fallback policy working.
* the new family `SysSwLeft` was adopted **deliberately** with
  `validate-matrix-contract.py --update-allowlist`; it failed loudly first.

**Host side built.** `d24_panel.py` knows the cell, polls it beside
`Sys001Skin001`, and lights the left board on it. Because the address has to be
in H1S4's own `MATRIX[]` before it means anything, the transition is handled
rather than assumed: while the board is unidentified the loop writes **both**
cells and the first press says which one that board runs; from then on the other
cell is not written again, and **a press arriving on the other board's cell
during a step is a FAIL that names the board**. That is the aliasing gone:
before it, a right-board press of index 3 and a left-board press of index 3 were
the same bytes.

### 3.1 Did right-board presses satisfy left steps in PW's pass? No — and here is what did happen

The dispatch asked this directly. Read off PW's third pass
(`factory.log:3644-3727`, report `…T161356Z.json` rows 43–54):

* the left loop ran, all six steps, and **six key codes came back — 1, 2, 3, 4,
  5, 6 in 4099, 927, 969, 738, 760 and 759 ms.** All six left switch rows are
  PASS. So PW did press all six left buttons; nothing on that board lit, so he
  did not experience it as a left-board test. That is item 4, not item 3.
* on the **right** board the same cause put two FAILs on rows that are not
  faults: the loop lit FX MUTE and **no key code arrived in 30 s**; it then lit
  HOME and got code **7 (MUTE)**, lit MENU and got **8 (SCENE)** — and codes 7
  and 8 arrived AGAIN, correctly, when MUTE and SCENE were asked for. That is an
  operator hunting a dark panel with the button's name on the glass, pressing
  them in the order he finds them.

**Which is why the screen must stop naming the button** — see §4.3.

### 3.2 🔴 STILL OWED, AND IT IS BLOCKED — the firmware cannot carry this address yet

This is finding S120-2 coming due, and it is now concrete rather than a
worry.

**The panel firmware's address table is generated from the UNIT'S OWN APP PACK,
not from defs.** `H1S4/Core/Inc/matrix.h` opens:

```
// matrix.h - GENERATED on-unit from config/_matrix.mxc (app build 260714102659)
// 2026-08-19: aligns panel fw addresses with the RUNNING app generation.
// Do not confuse with the Dropbox MX/matrix.h (newer generation, drifted).
```

and it was rewritten at 15:55:38 on 2026-08-19, **one to two seconds before the
flashed `.elf` was linked** at 15:55:40. So the flashed panels and the running
app agree with each other on `Sys001Skin001` = 5412, and it is this repo's
contract (4698) and the Dropbox copy (17553) that are the other two generations.

**The new cell exists in none of the app's pack, so there is no app-generation
address to use — and its defs address is already taken in that generation:**

```
H1S4/Core/Inc/matrix.h:4936:  #define Main004EqGain001 5005
```

Baking 5005 into H1S4 would make an **EQ gain change light a left-panel
indicator** as soon as `matrix-app` is running. That is harmless during a
factory pass — `matrix-app` is stopped for the whole of one and `d24_panel.py`
is the only writer — and it is not harmless in a product.

**So the order is fixed, and it is the hub's:**

1. rebuild the app's `config/_matrix.mxc` from `defs-v2026.09.27.1`, so the app
   and defs are ONE generation;
2. regenerate `matrix.h` on the unit from that pack (there is no script for it
   on the unit — the 2026-08-19 header says it was done by hand, so whoever
   owns the pack owns this step);
3. add the cell to H1S4's `MATRIX[]` **and** its parallel `enum` — they are two
   independent lists with no compiler-enforced link, so appending to one and
   not the other silently misaligns every index after it — and repoint H1S4's
   `rsw[]`/`wled[]` at the new pointer;
4. flash **both** boards against it in one go, because step 1 also moves
   `Sys001Skin001` from 5412 to 4698 and the currently flashed firmware would
   stop decoding it.

**The build half of that is proved ready.** Both boards' flashed images are
**byte-reproducible** from the source on the unit with the toolchain on the
unit: `arm-none-eabi-gcc 14.2.1` (against a recorded 13.3.rel1), one line fixed
per board in `Debug/makefile` — a `C:\dropbox\...` Windows linker-script path
replaced by `../STM32F030R8TX_FLASH.ld` — and no source change at all gives
`objcopy -O binary` md5 `f06639b6…` / 21 784 bytes for H1S3 and `97c4dfea…` /
14 744 bytes for H1S4, `cmp -l` reporting **0 differing bytes on both**. Built
in a copy under `/home/app/s129fw/`; nothing under `/home/app/fwbuild/` or
`/home/app/firmware/` was touched. Full log: `data/panel-build-repro.md`.

So when the generation question is answered, the firmware change is a
few lines and a build that is known to reproduce.

---

## 4. The panel indicators — and S128's root cause is wrong

### 4.1 What the flashed firmware actually is, proved

`/home/app/firmware/H1S3.shex` decodes **byte-identical** to
`/home/app/fwbuild/H1S3/Debug/H1S3.elf` of **2026-08-19 15:55** (21 784 bytes of
image, the shex's 8 bytes of 0xFF padding aside), and the same for H1S4
(14 744 bytes). So the image on the part is the Debug build of the source that is
on the unit, and that source is reproducible.

**In that image `WrRadioLed()` does NOT write an ODR bit on an input pin.** It
reconfigures the pin to `GPIO_MODE_OUTPUT_PP` and then drives it high:

```c
    if (matrix[s.matrixAdd][RXD] == s.radioData)
    {
        GPIO_InitStruct.Pin = s.pin;
        GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
        HAL_GPIO_Init(s.port, &GPIO_InitStruct);
        HAL_GPIO_WritePin(s.port, s.pin, GPIO_PIN_SET);
    }
```

and the Dec-2025 `Release` build's disassembly confirms two `HAL_GPIO_Init`
calls inside `WrRadioLed`. **So the commented-out `MainInit()` block is not the
reason the panel is dark, and S128's conclusion — repeated in
`d24_panel.py`'s own comment — is wrong.** That comment is left standing in the
tree only until the real cause is known; §4.4 says what will replace it.

### 4.2 The drive path, from the netlist, and why HIGH should mean ON

* the two indicators PW **does** see lit are wired **straight from the MCU pin
  through a resistor**: `rswitch:R47.1` and `R48.1` land on `rswitch:U1.30`,
  port **P25 = PB11**, the FX MUTE white; `PF1`/P4 is the REC/PLY white. Both
  are driven high in `MainInit()` and left there, and **neither is in
  `wled[]`** (both rows are commented out and replaced by `PB10` and `PC15`, the
  two RED rings), so nothing ever floats them again.
* every indicator in the radio group goes through a **dual-FET high-side pair**
  — HOME/P21 through `Q13`, FX MUTE red/P24 through `Q18`, and so on for
  `Q12`, `Q14`, `Q15`, `Q17`, `Q19` — whose N-half gate is the MCU pin and whose
  P-half source is `+3V3`. So **high still means on**, and there is a permanent
  faint feed as well (`R16`, `R17`, … direct from `+3V3` to the same anode).
* every cathode returns through a brightness rail — `rswitch:DIM0..DIM4`,
  8 LEDs each, and `lswitch:CONTROLS_DIM0/1` — and all of those rails are the
  drains of MOSFETs whose gates are **one net**, `PANEL_DIM` / `M MCU_DIM`
  (netlist `G2689`), driven by the panel master at `dsp:U8.47` and carried to
  both switch boards and the analog board. MH1 PWMs it from `TIM16->CCR1`
  (`DIM[] = {2560, 1434, 803, 450, 252, 141, 79, 43, 25}`), and **the host
  cannot change the brightness: the `'>'`/`'<'` handlers are commented out.**
* the two lit whites are on `DIM1` and `DIM4`, so at least those two rails
  conduct.

### 4.3 What is left, and why it needs one look

The fault is between the host's write and `matrix[pSys001Skin001][RXD]`, and
**the unit cannot tell me which side of it**: neither board's firmware ever
reports LED state — there is no readback of any kind — and MH1's `+` ack only
says MH1 forwarded the line. I checked for an indirect readback and there is
none: `rsw[]` and `wled[]` share no pin, `RdRadioSwitch` compares against `TXD`
and not `RXD`, `TestEnc` keeps its own counter, and `Poll()` transmits `TXD`.

So **HANDS 1**: light them one at a time while PW watches. "None of them" is a
complete answer and is the one I expect.

### 4.4 The answer to "how is an indicator graded with one button"

**It is operator-observed. There is no readback and there can be none without a
firmware change.** So the dispatch's own preferred option does not exist, and
the honest design inside PW's one-button rule is this, which needs no new
button:

> **Stop naming the button, and light them in a random order.** The instruction
> becomes "Press the button whose indicator is lit." A correct key code then
> proves BOTH rows at once, because the only way the operator could know which
> button to press is by seeing the light. Nothing lit → they cannot know → the
> step times out or they press PAUSE, and the row is a fail with a reason. A
> random order (seed recorded in the report) is what stops a learned sweep
> defeating it.

That also removes the failure PW's own pass produced: the two right-board FAILs
in §3.1 exist **because** the screen named the button, so a worker hunting a
dark panel pressed them out of order.

**NOT BUILT YET, on purpose:** it is a change to how an operator is graded and
it depends on the indicators actually lighting, which is unresolved. It is
written here as the design so PW can rule on it in one line.

---

## 5 and 6. The line input, the jack, and the XLR — one cause, one fix

### 6.1 The netlist answer: every combo socket wires the jack tip to the cold leg

Traced in `docs/d24-netlist-global.csv` (mx26), MIC 12 in full:

| from | net | through | to | which is also |
|---|---|---|---|---|
| `analog:J41.T` (TIP) | `MIC_9-12_21-24_MIC_IN_12_L1` | `R1715` | `…_M1` | `analog:J41.3` — **XLR pin 3, the COLD leg** |
| `analog:J41.R` (RING) | `…_L0` | `R1714` | `…_M0` | `analog:J41.2` — XLR pin 2, the HOT leg |

**Every combo socket from MIC 3 to MIC 24 is wired the same way round through
its own pair of resistors, without exception** (MIC 1–2 are XLR-only and have no
jack). The full 22-row trace is reproducible from the netlist in a few lines and
is quoted in `tools/accept/gen_patch_paths.py::block_k4`.

So a standard TRS lead — tip to pin 2, which is exactly how kit lead **K4** is
described — presents the signal on the preamp's cold leg, and the channel reads
inverted. **That is a PCB erratum and a red mod is owed.** The mod is the same
two parts on every channel, and it is robust to the one uncertainty in the
trace: if the connector symbol's `T`/`R` pins are themselves mislabelled, the
fix is still to cross the two resistors' inner ends so the tip reaches `M0` and
the ring reaches `M1`. Per channel the pair is
(`R353`/`R352`), (`R495`/`R494`), (`R702`/`R701`), (`R844`/`R843`),
(`R986`/`R985`), (`R1128`/`R1127`), (`R1289`/`R1288`), (`R1431`/`R1430`),
(`R1573`/`R1572`), (`R1715`/`R1714`) for MIC 3–12 and
(`R140`/`R139`), (`R282`/`R281`), (`R424`/`R423`), (`R566`/`R565`),
(`R773`/`R772`), (`R915`/`R914`), (`R1057`/`R1056`), (`R1199`/`R1198`),
(`R1360`/`R1359`), (`R1502`/`R1501`), (`R1644`/`R1643`), (`R1786`/`R1785`) for
MIC 13–24, tip resistor first.

**🔴 ONE ALTERNATIVE LEFT TO KILL, and it is cheap:** a miswired K4 lead would
explain all 22 readings and owe no mod at all. HANDS 2 is a continuity check on
that lead.

### 5.1 PW's own pass already proves the discriminator, eleven times

PW used the XLR lead for the MIC 7, 9, 10 and 11 "line" patches and they
**passed**; he used the real jack lead for MIC 12 and 17–22 and all seven came
back **inverted**. Same run, same code, same expectation. Eleven readings, no
exceptions. Combined with the netlist that is a sound discriminator:

* **jack centre → inverted. XLR → normal.**

### 5.2 The change

The K4 line rows now expect `polarity=inverted`, which is what this board does,
and the scorer says which mistake was made rather than reporting a polarity
fault:

* reads inverted → PASS of the SOCKET, with an `ERRATUM` note in every pass so
  the red mod is not forgotten;
* reads normal → **FAIL: "the lead is in the XLR socket, not the 6.35 mm jack
  centre of MIC n"**.

The simulator is taught the same thing, or every dry run of the line block would
read as the operator putting the lead in the wrong socket. Dry run: **151 of 151
PASS**; with the change and the old simulator, 14 FAILs, all of them the new
sentence, which is the fix demonstrating itself.

**AFTER THE MOD LANDS the polarity stops discriminating** (both sockets would
then read normal), which is why §5.3 matters.

### 5.3 The level window PW asked for (addendum 1.1) — not built, and why

> "it's still not checking correct line level, aux send probably needs to
> increase."

PW is right that it checks no level: the K4 rows are `level_ref=info`, so the
level is reported and not judged, and the drive is **−12 dBFS with the preamp at
gain 0**. What a window needs is one number nobody has: **how much the jack path
pads relative to the same socket's XLR.** The netlist says there is a pad — one
series resistor per leg that the XLR pins do not have — and says nothing about
its size, and no pass has ever recorded the two levels for one socket.

Two things are in place for it:

* every line patch now records its loop gain **against the same socket's own
  XLR reference** — the jack path's pad, measured per unit, on every pass;
* **HANDS 3** is the capture that sets the window: the K1 reference on MIC 8's
  XLR, then the K4 lead in MIC 8's jack with the drive swept −30 → −3 dBFS, then
  the same on MIC 12. Three lead moves, and they also say whether a hotter send
  clips anything.

I will not invent a window without those numbers.

---

## 7. MIC 7 — the hardware is innocent, and the instruction is not

Four measurements, none of which needed a lead:

1. **its 595 byte drives its own preamp and no other.** Byte 11 (MIC 7's
   `send_pos`, `24 − chain_index`) at gain 63 with every other preamp muted
   raised lane 7's own noise by **+32.8 dB** and every other lane by under
   1.3 dB. **All 16 populated inputs mapped correctly**
   (`data/s129_chainmap.json`).
2. **its lane floor is normal.** −113.94 dBFS, against −113.46 to −114.57 on the
   other eleven inputs with a front end; the ten with no front end read −116
   (`data/s129_floors.json`).
3. **its meter node is alive.** It reads a −20 dBFS oscillator as −20.00, like
   all 24, and its symbol is present.
4. **the measurement node is exactly linear** (§1.1).

So the `-21.8 dB over its own floor` in PW's report is **not** a high floor: it
is the coherent level of a window with no tone in it, which is what a silent
lane reads. And nothing about MIC 7's preamp, gain control, converter, lane or
meter is wrong.

**What MIC 7 does fail is one patch, three attempts, in both completed passes:
P11 — and it is the only patch in the whole pass where the previous block left
the lead IN MIC 7 and the only end that has to move is the other one**, from
AUX 3 to AUX 1. "Plug AUX 1 into MIC 7" reads as already done to somebody
looking at a lead in MIC 7. The seven output rows that also read "no tone
reached MIC 7" (rows 34, 36, 37, 39–42) are the same failure once: MIC 7 is
their return path.

**Fixed:** where only one end moves, the instruction now says which —
*"Move the OTHER end of the lead to AUX 1 - this end stays in MIC 7."* It fires
wherever that is true, which includes the whole output walk, and the
219-of-219 ENTER check passes with the new wording in it.

**It is not proved.** The proof is one patch with a lead in it, and it is in
HANDS 4. If MIC 7 fails again with an unambiguous instruction, the next
suspect is the XLR socket's own contacts, and `docs/d24-pcb-supplier-notes.md`
is where it would go.

---

## 8. The network rows (addendum 2)

* **NW2 grades only what the wire and the MAC say**: `rx_errors`, `rx_missed`,
  `tx_errors`, `tx_carrier`, `tx_collsns`, all still required to be zero.
  `rx_dropped` and `tx_dropped` are the KERNEL discarding frames it did
  receive, they were the only counter that ever failed this row on this bench,
  and they are now recorded in the reading and in the evidence and never grade
  it. **No hardware bar is lowered.**
* **NW3 keeps 0 %** and already targets the wired address. Measured on the
  driving host while writing this: `ip route get 192.168.1.219` →
  `dev ens9 src 192.168.1.211`, so **the target and the reply path are both
  wired** today. The host does also hold `192.168.1.133` on `wlp4s0` on the same
  subnet, which is why the address is pinned in one constant and not discovered.
  No capture is requested by the runner during the network window — the only
  writer of `capture.request` is bench tooling, never a pass.
* **NW4 is NOT TESTED**, decided before anything is run, reason **"no gigabit
  peer on this bench"**. The peer is one config value, `NW4_PEER`, with the
  factory-bench requirement written beside it: one wired-only PC on the unit's
  switch, link negotiated at 1000 Mb/s full duplex, `iperf3` available, nothing
  else saturating it. It also stops spending 23 s of a factory pass measuring
  the bench.
* **Can peters-mbp's ens9 do 1000 Mb/s?** The silicon can — it is a Broadcom
  **BCM57786 Gigabit** controller — but **the link negotiates 100 Mb/s full
  duplex today** (`/sys/class/net/ens9/speed` = 100). So the cable or the
  switch port is the 100 Mb element, not the PC. Fix that and NW4 becomes a
  real pass/fail against this host.

---

## 9. PW's ±0.25 dB, and what it needs (addenda 5 and 6)

`gain_step_tol_db` is now **0.25**, source PW 2026-09-27.

**The instrument holds it with 20× to spare.** §1.1: 0.011 dB of spread at one
read window, 0.000 at three. So the measurement is not what will be failing.

**The EXPECTED table is not good enough for it yet, and the numbers say so
before any unit is measured.** `patch-gain-steps.csv` takes its expected value
from defs' own measured mic gain law where the law carries the code, and from a
six-element fit of that same law where it does not — and **the fit's worst
residual is 0.51 dB, twice PW's window.** Codes 8, 16, 32 and the 63 EIN step
are fitted, not measured. So on four of the seven steps the expected value
cannot be judged against 0.25 dB whatever the preamp does.

Also, as the hub notes: a 1 % resistor is **±0.09 dB** on its own, a third of
the budget before any FET is considered.

**What is owed, and it needs the lead:** each element's measured gain on MIC 9–12
and 17–24 against the table, so that (a) the table can be corrected where it is
wrong, (b) an error that GROWS with gain can be separated from one that does
not — growing points at the 2N7002DW `Rds(on)` across the LTP tail, flat points
at resistor tolerance, and that is what decides whether 0.1 % resistors alone
meet ±0.25 dB at rev D. **HANDS 4.**

---

## 10. Hands off, and which steps actually need it (addendum 4)

> "If any of the tests require touch display silence then notify user and take
> control for those tests, with active progress."

**Every candidate, with its duration, and whether it needs the window.** The
durations are the runner's own measured cost model (`d24_runall.COST`, taken
from S116's full run).

| step | what it is | s | needs hands off? |
|---|---|---|---|
| **AL1** | speaker → panel MEMS microphone loop | **17** | **YES** — the microphone that has to hear the speaker is inches from the finger pressing panel buttons |
| NW3 | network packet loss | 63 | no — see below |
| NW2 | network error counters | 30 | no |
| NW4 | network throughput | 23 | no (and it is now NOT TESTED, so 0 s) |
| AS-CPLD | logic device identity | 15 | no — SPI only, nothing acoustic, nothing on the panel bus |
| DR1 / DR2 | audio processor reset / released | 11 / 9 | no |
| ML1, ML-M, ML-P1, ML-P2 | control and panel processor links | 4–5 each | no, and it is measured: all four PASSED in all three of PW's passes **while the operator was pressing panel buttons**, so the key traffic does not perturb them |
| the analog station's settle and read windows | 85–340 ms each | <0.35 | no — they are already hands-off by construction: the operator plugs the lead in and then presses ENTER, and the reading is taken after the press |

**Why the network window is not one of them, with the measurement.** What
perturbed NW3 was not a hand: it was **47 on-demand screen captures**, several
of them inside NW3's own window, which is bench tooling and is never part of a
pass — and the same window re-measured with the capture armed and idle read
**0.0 % loss** (S128). A touch is not a screenshot. Blocking a worker for 116 s
to protect a ping test would also undo S126's ruling, which put the network
under the patch pass on purpose.

### 10.1 What was built, and it needed no app change

`quiet_window` on the self-test side already raises a flag around AL1's tone and
`quiet_hold` on the runner side makes the panel loop wait — but **it gave up
after 8 s and AL1 takes 17**, so the loop lit the next button while the speaker
was still sounding. That is why AL1 read NO DATA, "no settled window for: base,
tone, back", on PW's passes having passed on 09-25 and 09-26 when nothing ran
under it.

* `QUIET_MAX_S` is **30 s** — longer than the step, still a cap and not a wait
  for ever;
* while the flag is up the glass goes to a new state, `handsoff`, carrying
  **"Hands off - the unit is testing itself (the speaker and the panel
  microphone, about 17 s)"** and **"Do not touch the screen or the front panel
  until this clears."**;
* **active progress**: `n`/`total` count the seconds, which drives both the
  "n of N" and the progress bar, and `busy` is true so the activity indicator
  keeps sweeping;
* **the screen has NO BUTTON AT ALL** in that state (`buttons: []`,
  `can_pause: false`), which the app already honours — `PrimaryBorder` and
  `PauseBorder` are both hidden, and a tap on the body of the screen has no
  handler. So a touch is ignored rather than queued;
* and the runner **drains** `live.command()` and the keyboard for the whole
  window and throws away what it finds, so a press cannot be spent on the step
  after — which is the same class of fault one layer up;
* when the flag clears the screen is put back exactly as the loop left it.

Verified on the desk: `state=handsoff` → `buttons=[]`, `busy=True`,
`can_pause=False`; `state=summary` → `buttons=['exit']`; and a return to
`waiting` restores `['enter','pause']` and clears the summary.

**Not proved on the part.** AL1 passing again from the glass needs a pass, which
needs the operator. It is in the proof pass.

---

## 11. Not built, and honestly named

* **addendum 7's talkback cell** — the DEFS HALF IS DONE and tagged
  **`defs-v2026.09.27.3`**: `Sys001SwTalk001` = 5006 (Shex `ikpv`), and the three
  `CON` rows in `fw.csv`'s `SW_RIGHT` section become `SW` and `LED` and name it.
  The encoding is stated rather than assumed: WRITE is the two-indicator mask
  (bit0 = `TB_LED0`, bit1 = `TB_LED1`, so 0 both dark and 3 both lit) and READ is
  the switch, 1 while held and 0 on release, both edges reported — write and read
  carrying different meanings on one cell exactly as `Sys001Skin001` does. What
  is NOT done is the H1S3 firmware, and it hits exactly the same wall as §3.2:
  no panel firmware should take a defs-generation address until the app's pack is
  rebuilt. It belongs in the same single reflash of both boards, not a second
  one.
* **addendum 2's touch-panel row** — THE TEST IS DONE AND PASSES ON THE PART:
  `USB-TP`, *"the touch panel is on hub port 2 with usbhid bound"*, 0.1 s. It
  grades three facts the unit reads for itself — `222a:0001` (ILI Multi-Touch
  Screen) present, on the internal Microchip hub and not straight on the root
  port, on PORT 2 where the operator's sticks are 3 and 4, and `usbhid` bound,
  because a panel that enumerates and does not bind is a panel nobody can touch.
  What is NOT done is the catalog ROW, because the catalog is generated upstream:
  the row the hub should add is written out in `ITEMS` beside the test (board
  `Digital`, item `Touch panel (rear USB socket, hub port 2)`, class `USB-A`,
  tests `USB-TP`, group `A1`).
* **item 4's real cause**, on which the panel firmware change depends.
* **§4.4's grading design** — stop naming the button, randomise the order —
  which wants one line from PW because it changes how an operator is graded.
* **the proof pass**, which is every remaining item at once.

---

## 11a. Two small things found by using the tools

* **`--reset-state` resets AND THEN RUNS A WHOLE PASS.** Running is what the
  tool does with no other flag, so `d24_runall.py --reset-state` on its own is a
  full factory pass. It bit this session. Fixed by naming it: the flag's help
  now says so, and **`--reset-only`** resets and stops, which is what the old one
  looks like it does.
* **the per-run `patch-results-<stamp>.csv` files that S127 introduced are not
  on the unit** for any of PW's three passes — only the 13:00 `patch-results.csv`
  is. So the per-row notes for those passes (the loop gains, the phase figures,
  the settle) exist only in the reports' `limit` fields and in `factory.log`,
  which is why some of the numbers in §5.3 had to be described as absent rather
  than quoted. Worth a look, and it is not this session's change.

---

## 12. The unit, as this report is written

`matrix-app` inactive, `d24-testui` active, **AN_EN low** (read back after every
probe that raised it), **CS_M driven high**, the 595 chain **SAFE and re-verified
at handback**, the DSP pair still the factory test pair at
`/home/app/loopthd/s122`, no firmware flashed, no CPLD touched, still on v2. No
runner holds the lock and the screen file is cleared, so the glass is on its own
armed page with START.

**The cumulative pass state is RESET**, so PW's next START is a FIRST pass and
walks everything — which is what every outstanding proof needs, and which also
answers "exited after a few button clicks": that was the loop declining to
re-test ten rows that had already passed. The old state is kept at
`runall/state.json.bak-s129-pre`, and PW's three completed passes are preserved
in `reports/`. One spurious report, `…T181637Z`, was written when the reset
command's own pass was stopped on the way out; it records nothing and can be
deleted.

The tools and the short patch list on the unit match this tree.
`d24_patch.py.bak-s129-pre` and friends are the rollback.

---

## 13. Files

* `tools/settle_probe.py` — the drive-step settle, on the part.
* `tools/floor_probe.py` — every lane's floor, and the instrument's own spread.
* `tools/chainmap_probe.py` — which 595 byte drives which lane's preamp.
* `panel-fw/H1S3`, `panel-fw/H1S4` — the panel firmware source, captured off the
  unit into this tree, which is where it has never been.
* `data/` — the factory-log digest, the firmware recon, the two probe JSONs and
  the 151-of-151 dry run.
