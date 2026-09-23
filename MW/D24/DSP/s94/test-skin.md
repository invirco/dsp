provenance: AI-drafted 2026-09-23 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S94 — the D24 test skin, first working version, live on MW-D24-2

**It is on the unit now and it is the boot screen.** `matrix-app` comes up
showing a 25×10 grid of 250 numbered buttons, one per row of the connector
workbook, coloured by that row's live verdict. Touch a number and it opens that
test's detail page. Where a runner exists, **Start Test really runs it and the
colour really changes**; where one does not, the button says
`NOT YET AUTOMATED` and does nothing at all.

Design: `~/mx26/docs/spec-d24-test-skin.md` (written first, as gate 0 asked).
Preview of the grid as it stands: `grid-preview.png` beside this file — a render
of the same `skin.csv` with the same colour rule, **not a screenshot** (see §6).
The two detail pages that were opened live are transcribed in
`detail-pages-as-shown.txt`.

---

## 1. What PW can go and press right now

The unit is at `app@192.168.1.219`, `matrix-app` is active, the test skin is the
boot skin. On the screen:

- **250 buttons**, 204 real and 46 reserved (the reserved ones are dark and
  inert — room for the list to grow, not errors).
- **19 green, 5 amber, 0 red, 180 slate** as of 10:56 today. Green is PASS,
  red FAIL, amber PARTIAL, slate UNTESTED, blue while a test is running.
- The coloured ones are **103, 104, 111, 112, 113, 128, 140, 141, 142, 144,
  145, 152, 194, 195, 196, 199, 200, 202, 204** (green) and **102, 126, 127,
  129, 203** (amber). Everything else has no result yet and says so rather than
  guessing.
- Below the grid: the counts, the legend, a **touch self-check tile**, an
  **EXIT TO MIXER** button (back to `H_1_24_V2_Ben`) and **REFRESH**.
- Touching a number opens its detail page: what the test is, when it passes,
  what evidence it wants, the last recorded result, and Start Test.

**To put the unit back to the mixer for good**: `/home/app/app cli settings-set
skin H_1_24_V2_Ben` then restart the service. One line, and the backups
`settings.mxe.bak-s94` / `settings.csv.bak-s94` / `app.bak-s94-pre` are beside
the originals.

---

## 2. What was actually pressed, and what happened

Three presses, all real, all through `/dev/uinput` as an ordinary absolute touch
device that libinput opened and Avalonia delivered — **not** through the panel's
own ILITEK controller (see §6 for why that distinction matters and what it does
and does not prove).

**Press 1 — a row already confirmed good.** Cell **128**, the HDMI0 → TFT
display link, at (219, 456).

```
TESTSKIN: press TESTCELL 'HDMI FPC (rev B)|Display link HDMI0 → TFT' at 183,426
TESTSKIN: selected #128 HDMI FPC (rev B)|Display link HDMI0 → TFT status=PASS
DrmMainView.LoadSkin: Loading /home/app/skins/D24TESTD.mxs
```

The detail page opened on `STATUSBIG PASS`, `KEY HDMI FPC (rev B) | Display link
HDMI0 → TFT`, `scripted today: HD0-1,HD0-2 (runner section A)`, the two tests'
methods and PASS criteria scraped out of the spec, and
`last: HD0-2 PASS at 2026-09-22T21:01:44Z — connected on 61 of 61 samples over
3600 s, drm hotplug uevents 0`. Full transcript in
`detail-pages-as-shown.txt`.

**Press 2 — a row that ran live and changed colour.** Cell **129**, Ethernet
(RJ45), which was **red** (NW3 had failed at 2 % loss on 22 Sep). Opened its
detail page, pressed **START TEST** at (1640, 1002):

```
TESTSKIN: press TESTCELL 'Digital|Ethernet (RJ45)' at 257,426
TESTSKIN: selected #129 Digital|Ethernet (RJ45) status=FAIL
TESTSKIN: press TESTACT 'START' at 1400,960
TestSkinStore: started NW1,NW2,NW3,NW4 at 10:50:38 — setsid python3
  '/home/app/selftest/d24_selftest.py' --local --no-soak-wait
  --csv '/home/app/selftest/item-status.csv' --section A --only NW1,NW2,NW3,NW4
TestSkinStore: Digital|Ethernet (RJ45) finished, exit 0        [10:56:06]
```

and the run itself, on the unit, five and a half minutes later:

```
NW1  PASS     Link detected: yes, Speed: 1000Mb/s, Duplex: Full, carrier=1
NW3  NO DATA  bench host 192.168.1.211: worst 100.0% loss over 3 passes
NW4  NO DATA  unit rx 9164 Mbit/s, unit tx 6005 Mbit/s -- but the driving
              host's lo negotiates 0 Mb/s, so this is not the wire
NW2  PASS     deltas over NW3+NW4: rx_errors 0, rx_dropped 0, ... all zero
```

Four rows appended to the results CSV, the app reloaded it, and **the cell went
from red to amber** — FAIL superseded by two PASS and two NO DATA is PARTIAL by
the workbook's own merge rule. That is the whole loop working: press → run →
verdict → colour, with nobody at the bench.

**🔴 And it surfaced a real finding — §4.2.**

**Press 3 — the touch self-check.** The tile at (1520, 846).

```
TESTSKIN: press TESTTOUCH '' at 1200,776
```

It reads `TOUCH CONTROLLER PRESENT`, with `N: Name="ILITEK ILITEK-TP"` from
`/proc/bus/input/devices` as its evidence, and a "last touch N s ago" line that
ticks. That second half is the one that would catch the cable working loose
after boot, which is the case this unit has already produced once.

---

## 3. What works

- **The grid generates.** `~/mx26/tools/d24/build-d24-test-skin.py` reads
  `build-d24-connector-status.py --export-keys` (204 rows), the self-test spec,
  and the dsp runner's own `ITEMS`/`SECTION` tables — it **imports** the runner
  rather than copying it, so the two cannot drift — and emits the two skins and
  a `test-catalog.csv`. Nothing about the row list is hand-maintained.
- **Position and identity are separate**, and that was got right before any UI
  was written. A cell's `DefStr` is `board|item` verbatim; the number is drawn
  text. Everything in the store is keyed on `board|item`. A resort of the
  canonical list moves numbers and moves nothing else.
- **The roll-up is the workbook's, not a second opinion**: newest stamp per
  (board, item, test), then FAIL beats NO DATA beats PASS. The skin and the
  spreadsheet cannot disagree about a row's colour.
- **It extends the skin system rather than forking it.** Three `SubType` values
  on the existing `Type=SW` control (`TESTCELL`, `TESTINFO`, `TESTACT`, plus
  `TESTRSVD`/`TESTTOUCH`), a branch in `DrawSW` and a branch in the press
  handler, one new file (`Core/TestSkinStore.cs`). No schema column added, no
  second renderer, no matrix cells invented — a test cell binds to `Cell=null`,
  `MxAdd=0`, exactly like the page-navigation buttons every shipped skin
  already has. Navigation to the detail page and back is the **existing**
  `SkinLink` path; the test code only sets the selection before it runs.
- **Cells draw themselves**, so 250 buttons cost zero PNGs and the colour is a
  property of the data rather than of the asset set — which is what lets it
  change while the page is open.
- **The detail text is real.** All 204 rows resolve to spec prose: 150 to a
  specific test's table row, 24 to their subsection's stated method (4c's "the
  23 remaining headers" names its rows in prose, not in a cell), and 30 to an
  explicit "out of scope on PW's ruling" — the PSU-ADC rows, which have no test
  and are not given borrowed prose.

---

## 4. What does not work yet — named, not glossed

### 4.1 Only 5 of the 36 scripted rows can run without taking the display away

The runner drives sections B and C by **stopping `matrix-app`** — B to reach
H1S1 over the matrix bus, C to boot the DSP pair. `matrix-app` is the process
drawing this skin. So the 36 items split:

| | items | Start Test does |
|---|---|---|
| section A — read from the CM4 | **5** | runs in place; the app stays up, the colour changes under PW's finger |
| section B — through H1S1 | **19** | would stop the app for the run and restart it afterwards |
| section C — from the DSPs | **12** | same |

The five that run live are: the HDMI0 → TFT display link, the TFT display,
`Link 'hdmi-pwr'`, Ethernet (RJ45), and the CM4 compute module.

**The B/C path is built but was NOT tried live.** The code is there — the run is
`setsid`, so it outlives the app it stops, and the detail page demands a second
press with "STOPS THIS APP" on the button before it will start — but taking the
display away on a remote unit to prove it was not worth the risk today with no
one in the room, so **it is untested and must be treated as untested**. That is
the single biggest thing for the next dispatch, and it is a half-hour job with
PW at the bench.

### 4.2 🔴 A section-A test run *from the unit* is not always the same test

This came out of press 2 and it is worth more than the press was. `NW3` pings
the bench host and `NW4` runs `iperf3` against it. Under `--local` the "driving
host" is the unit itself, so:

- **NW3 read 100 % loss to 192.168.1.211** and reported **NO DATA**, not FAIL.
- **NW4 measured 9164 / 6005 Mbit/s** — over loopback — noticed that "the
  driving host's `lo` negotiates 0 Mb/s", and reported **NO DATA** rather than
  printing a nine-gigabit Ethernet result.

**The runner caught both and refused to lie**, which is exactly the discipline
S90 built into it. But the consequence is real: **pressing Start Test on the
unit re-took row 129 and replaced a genuine FAIL with two NO DATAs**, moving it
from red to amber. The bench-host-relative half of that row cannot be taken from
the unit at all. Two of the five live rows (NW3, NW4) are therefore *weaker*
from the button than from the bench host, and the detail page does not yet say
so. **Fix for the next dispatch**: mark host-relative tests in the catalog and
have the detail page say "this half needs the bench host" rather than letting a
press quietly downgrade a row.

### 4.3 The other 168 rows

Specified, not built (S92 sections 2–4). Their detail pages are complete and
correct — method, PASS criterion, evidence, the provisional limits, the blockers
— and their Start Test button reads `NOT YET AUTOMATED` and is inert. **No row
was faked, no press silently no-ops.** 47 of them still hang on the `AN_EN`
ruling (S92, PW-1), which this build does not touch and does not pretend to.

### 4.4 Smaller ones

- **Row 149, `Link 'hdmi-fpc'`**, is automation `1` but is not in the runner's
  `ITEMS` table (it is S92-C1, a classification correction not yet reflected in
  the runner). It shows as not-yet-automated, which is the honest reading of the
  runner as it stands, but it is a loose end.
- **The touch self-check is not a workbook row.** There are none — the S93
  correction left "find and declare the real touch path" open. It is an
  app-side live read and deliberately writes nothing to `item-status.csv`, since
  an unknown key would (correctly) trip the generator's fail-loud check. When
  the path is declared and gets a row, the tile should become an ordinary grid
  cell and the special case should be deleted.
- **`ResolveSkinNum: 'D24TEST' not found in skinRegistryReverse`** appears in the
  trace on every load. Benign — the skins resolve by file existence and the
  press path uses `LoadSkin` directly — but `skin_registry.csv` was deliberately
  left alone rather than renumbered under the existing entries.
- **The unit's results CSV and the repo's are two files.** The four new NW rows
  were pulled back into `MW/D24/DSP/accept/item-status.csv` by hand, as the spec
  says. Nothing merges automatically, on purpose.

---

## 5. Two things that cost time and will cost the next session time if unwritten

- **`ProcessStartInfo.Arguments` is parsed with Windows quoting rules on Linux.**
  The first Start Test press logged fine and started nothing: `-c 'setsid python3
  …'` was split on its spaces and bash never saw the pipeline, so there was not
  even a `run.log` to look at. `ArgumentList` passes argv through untouched and
  is the fix.
- **Avalonia's DRM backend enumerates input devices once, at startup, and does
  not watch for hotplug.** A `uinput` device created after `matrix-app` started
  is invisible to it however correct the device is — the kernel logs the new
  input and the app never sees a press, which reads exactly like a broken
  injector. `tools/pi/d24_touch_inject.py --serve <fifo>` exists for that:
  create the device, restart `matrix-app` with it already present, then tap
  through the FIFO.

---

## 6. 🔴 There is no screenshot, and what was proved instead

**The unit's display cannot be captured from a dispatched session.** The app
renders through DRM; `/dev/fb0` is the fbdev emulation plane and still carries
the boot splash (grabbed and decoded — it is the M&W logo, not the app).
`ffmpeg`, `modetest`, `grim` and `fbgrab` are all absent from the unit, and the
app holds DRM master. `card0-Writeback-1` exists and would be the way in, but
that is a libdrm program, not a shell line.

So what is in `grid-preview.png` is **a render of the generated `skin.csv`,
coloured from the unit's own live `item-status.csv` by the same roll-up rule the
app applies** — produced by `~/mx26/tools/d24/preview-d24-test-skin.py`,
independently of the app. It is faithful to the layout and the colours. It is
not evidence that the panel is showing it.

What *is* evidence that the panel is showing it, and that presses land:

- `DrmMainView.LoadDefaultSkin: skinName=D24TEST, resolved=/home/app/skins/D24TEST.mxs`
  and `Skin loaded successfully, controls=257` (250 grid cells + 7);
- `TestSkinStore: catalog 204 rows from /home/app/selftest/test-catalog.csv`;
- three `TESTSKIN: press …` lines naming the control and its position, each
  followed by the navigation or the run it caused;
- a test that actually ran on the unit and wrote four rows.

And the honest limit on all of it: **the presses went in through a virtual
uinput device, not through the ILITEK controller.** They prove the skin, the
hit-testing, the store, the navigation and the runner. They prove nothing about
the touch panel, the cable, or the controller — that is PW's finger, and it is
one of the three things worth doing first at the bench.

---

## 7. What the next dispatch should do

1. **PW presses it** — the one thing no dispatched session can do. Does the
   ILITEK path hit the right cells, is 72 × 60 px a big enough target, is the
   number legible across the room.
2. **Try a section-B row live** (§4.1) — the app-stopping path is built and
   untested. `ML-M` or `DC1-CS1` with PW watching, once.
3. **Fix §4.2** — mark host-relative tests so a press cannot quietly downgrade a
   row, and consider having the runner refuse `NW3`/`NW4` under `--local`
   instead of taking a weaker reading.
4. **Wire more of section 2** once the `AN_EN` ruling (S92 PW-1) is settled —
   that is 47 rows in one decision and is still the largest single move
   available.
5. **Give the touch check a real workbook row** when the S93-correction
   follow-up lands the declared hardware path.

---

## 8. The unit as it was handed back

| | |
|---|---|
| `matrix-app` | active, boot skin **D24TEST** (deliberately; §1 says how to revert) |
| app binary | `f893bd12eb9f0b782ee02291b67766cc`, md5-matched against the local publish; previous binary kept at `/home/app/app.bak-s94-pre` |
| AN_EN (GPIO26) | `op -- pd \| lo` — **as found, never raised** |
| CS_M (GPIO27) | `ip pu \| hi` — as found |
| CPLD | untouched; no flash, no DSP boot, no 595 write this session |
| `/home/app/selftest/` | new: catalog, results CSV, the runner, `d24_touch_inject.py`, `run.log`, raw reads |
| `/home/app/skins/` | new: `D24TEST.mxs`, `D24TESTD.mxs`; no existing skin altered |
| injected touch device | destroyed, FIFO removed, `/dev/input/` back to its five real devices |
| `defs.lock` | unmoved; no generated DSP artifact touched, so no contract note is due |
