provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# D24 factory test: speed review

2026-09-26 19:57 BST. Read-only desk review. Sources: dsp `tasks.md` S113-S123 (S123 addenda 1-6), `MW/D24/DSP/s113…s123/`, `tools/pi/d24_selftest.py`, `d24_runall.py`, `d24_patch.py` (S123 working tree, uncommitted), `d24_panel.py`, mx26 `pipeline.md`. Nothing on the unit was touched.

**Headline.** The complete test is about **12.8 min** for a trained worker (3 s per hand move) and **16.8 min** for a typical one (5 s). The top items take it to about **7.1 min** and **10.8 min**. The biggest single item is structural: the worker stands idle for the whole 210 s automated set, and the machine is idle while the worker patches. Overlapping them is worth 170-210 s per unit on its own.

Conventions: "M" = measured, with the source. "E" = estimate, with the basis. Hand moves at 3 s / 5 s as asked. A panel press on a lit button is lighter than a lead move: 1.5 s / 2.5 s (E, nobody has pressed one yet, S120 🔴). ENTER reach 0.8 s (S123's own model, `d24_patch.py:2276`).

---

## 1. Where the time goes now

### 1a. The whole test, START to report

| # | block | count | who | 3 s | 5 s | basis |
|---|---|---|---|---|---|---|
| 1 | Automated set (one `d24_selftest.py` run) | 39 tests | machine; worker idle | 210 | 210 | M: `s116/rulings-applied.md:246` (real 3m30.4s); S117 `run-all.md` §4.1 (210 s through the glass) |
| 2 | Glass lag on RUN ALL dialogs (app polls `runall/` every 2 s) | ~12 dialogs | wait | 12 | 12 | E: avg 1 s of a 2 s tick (`TestSkinStore.RunAll.cs:85,263`); S123 fixed this for the patch screen only |
| 3 | Station cards (left panel, right panel, pedal, rear sockets, analog) | 5 | hand | 15 | 25 | E: one read + press each |
| 4 | Panel loops (right 14 buttons, left 6; always-lit rings, encoder turn, encoder ring) | 20 presses + 4 prompts | hand | 42 | 70 | E: 20 × 1.5/2.5 s + 4 × 3/5 s; machine <10 ms per press (M, `s120/panel-loop.md:9`) |
| 5 | Foot pedal station (fixture not built: visited to skip) | 3 dialogs | hand | 6 | 9 | E |
| 6 | Rear sockets (USB stick left, then right, Done each; "is the mains lead home?") | 2 moves + 3 presses | hand | 8 | 12 | E |
| 7 | Patch station setup (rails, standing write 567 cells, floors 27 lanes, chain) | 1 | machine, worker waits | 12.5 | 12.5 | M primitives: 5.4 s write, 27 × 256 ms floors (`s121/patch-loop.md:134-135`) |
| 8 | Patch pass: hand moves | 91 | hand | 273 | 455 | M/E: S123 status line (91-patch order) |
| 9 | Patch pass: ENTER presses | 91 | hand | 73 | 73 | E: S123 model, 0.8 s a press |
| 10 | Patch pass: machine after each ENTER | 91 patches | machine, worker waits | 89 | 89 | M: S123 87 s from measured primitives; +2 s E for gain steps as coded (§1c) |
| 11 | Lead changes (put one lead down, pick the next up, both ends) | 4 | hand | 24 | 40 | E: 2 moves each; **not in S123's model** |
| 12 | Handback + report | 1 | machine | 2 | 2 | E: rails/SAFE are ms; report write not timed |
| | **Total** | | | **767 s = 12.8 min** | **1010 s = 16.8 min** | |
| | machine share | | | 326 s (42 %) | 326 s (32 %) | |

Not in the table: power-up and CM4 boot to the test screen (never measured), and plugging mains and network before START.

### 1b. The automated set, by test

M: stamp deltas in `s116/logs/full-run-2026-09-26T130813Z.csv` (one-second stamps, sum 210 s). IC1 (S118) came later: +0.7 s (M).

| group | test | s | what the time is | source |
|---|---|---|---|---|
| A | screen link, CM4, USB hub, network link | <1 | reads | csv |
| A | NW3 ping, 3 passes × 2 targets | 63 | 3 × 200 pings at 0.1 s | `d24_selftest.py:535` |
| A | NW4 throughput | 23 | 2 × 10 s iperf3 + 3.5 s of sleeps | `:614-625` |
| A | NW2 counters | 30 | a **30 s idle sleep** (control window) | `:488-491` |
| B | stop app, stage, codec init, ML1/ML2 | 4 | | csv |
| B | ML-M, ML-P1, ML-P2 | 15 | **the same 3 s `stest` probe run three times**; each run returns all three identities | raw `ML-M.txt`, `ML-P1.txt` (`window_ms` 3016 each); `:740-778` |
| B | CC1/CC2, MC1-3 | 2 | | csv |
| B | prep boot + DR1 | 11 | boot #1 (two boot+config cycles) + 2.5 s of sleeps | `:985-1008`, `:3117-3121` |
| B | DR2 | 9 | boot #2 + lane scan | `:1011-1023` |
| B | DY1 (both rows) | 7 | reset dip + **boot #3** | `:891-916` |
| B | DC1/DC2 (10 rows) | 2 | | csv |
| C | AS-DSPA / AS-DSPB | 6 | 1 s heartbeat sleep each; lane scan **repeats DR2's** | `:1147-1174` |
| C | AS-CPLD | 15 | a **10 s** overrun window + logic id | `:1196-1258` |
| C | rails up, AS-ADC, AS-DAC, AS-PWR | 6 | | csv |
| C | AL1 (acoustic loop) + stand-down | 17 | ~10 s is the route/close write after a boot (7.1 s warm, M `s114/runners-timing.csv`) | csv |

Every `boot_pair()` runs two boot+config cycles because the first config commit desyncs the link (`:2584-2626`). So one RUN ALL boots the pair **six times**. No CPLD reboot and no app restart happen inside RUN ALL.

### 1c. The patch pass, by block

Per-patch machine seconds are M from `s121/patch-loop.md` §7. Hand and ENTER are the model. S123 addenda 4 and 5 (gain steps, EIN in the walk) are not built yet, so block 2 and 3 machine figures will move. Addendum 6 will replace this with measured figures.

| # | block | patches | hand 3 s | hand 5 s | ENTER | machine | parked end |
|---|---|---|---|---|---|---|---|
| 0 | find a good loop (good unit) | 1 | in block 1 | | | | |
| 1 | XLR outputs into the reference input | 10 | 30 | 50 | 8 | 8.3 | input end |
| 2 | XLR inputs from the reference output, 7 gain steps each, + talkback | 25 | 75 | 125 | 20 | ~23 | output end |
| 3 | EIN, 150 Ω plug, in the input walk | 24 | 72 | 120 | 19 | 12-18 | none |
| 4 | line inputs (XLR-to-jack lead) | 24 | 72 | 120 | 19 | 19.9 | output end |
| 5 | TRS outputs (jack-to-XLR lead) | 6 | 18 | 30 | 5 | 11.2 | input end |
| 6 | mini-jacks | 2 | 6 | 10 | 2 | 3.0 | output end |
| | **total** | **91** | **273** | **455** | **73** | **~87** | |

Setup before block 0: 12.5 s (row 7 above). Handback: under 1 s.

---

## 2. Speed-up opportunities, ranked

Ranked by seconds saved per unit at 5 s per move, each counted **after the items above it are done**. The 3 s figure is in the same cell. "S123" = whether the running S123 dispatch already covers it.

| rank | what changes | saved 3 s / 5 s | effort | coverage risk | who | S123 |
|---|---|---|---|---|---|---|
| 1 | **Overlap the automated set with the worker's hands** (§2.1) | **169 / 210** | M | low | dsp spoke + app + **PW ruling** | no |
| 2 | **ENTER on a USB footswitch** (§2.2) | **55 / 55** | S | none | **PW (kit)**; no code | partly (keyboard Enter already read) |
| 3 | **Park all five leads before the first patch; zero lead changes** (§2.3) | **24 / 40** | S | none | dsp spoke (generator + screen text) + PW nod | no |
| 4 | **Start the reading when the tone arrives, not on ENTER; settle from the insertion** (§2.4) | **29 / 29** | S-M | low | dsp spoke + PW nod | partly (addendum 6) |
| 5 | **Rear sockets and pedal: sticks in at setup, mains question dropped, pedal station hidden until its fixture exists** (§2.5) | 17 / 26 standalone; ~3 / 26 after #1 | S | none | dsp spoke + hub (catalog) + PW | no |
| 6 | **Cut the automated set's machine time** (§2.6) | 41 / 0 after #1 (43 standalone) | S each | none-low | dsp spoke | no |
| 7 | Serpentine walks: each block starts where the last ended (§2.7) | 6 / 10 | S | none | dsp spoke (generator) | no |
| 8 | Live status for every RUN ALL dialog, not just the patch screen | 5 / 5 after #5 (12 standalone) | S | none | app + dsp spoke | no (patch screen only) |
| 9 | Floors off the meter sweep; standing state as the image's boot default | 0 / 0 after #1 (11 standalone) | S / M | low | dsp spoke / image | no |
| 10 | Network tests shorter (NW2 control over B+C, NW4 `--bidir` or 3 s runs) | 0 / 0 after #1 (43 standalone) | S | low | dsp spoke | no |
| 11 | Rails raised once for the whole RUN ALL | ~0 | S | none | dsp spoke | no (station raises again) |
| 12 | 200-pass chain verifies outside MC1/MC2 | <1 | S | none | dsp spoke | yes (addendum 4) |
| 13 | Report generation | ~0 | — | — | — | — |

### 2.1 Overlap the automated set with the worker's hands

Today the worker waits 210 s for the automated set, then the machine waits while the worker patches.

**Can the hardware do both? Honestly, partly:**

| pair | overlap? | why |
|---|---|---|
| network tests (group A) + patch pass | **yes** | Ethernet and CPU only. The patch loop uses the DSP link, GPIO and the screen. One thing to measure: NW4 at 900 Mbit/s with the patch loop running (iperf3 loads a core). |
| network tests + panel loops | **yes** | Ethernet vs the panel UART. |
| panel loops + DSP tests (DR/DY/DC/AS) | **yes** | panel UART vs the DSP link. |
| panel loops + ML/CC/codec init | **no** | all share `/dev/serial0` (`d24_bus_probe.py:25`, `codec4619.py:90`, `d24_panel.py:5`). Run ML/CC and codec init first (~10 s after the fixes in §2.6). |
| panel loops + AL1 tone window | **only with a pause** | the panel mic hears button clicks. Hold the next LED for ~1 s while AL1's tone plays (oscillator on 0.76 s, M `s115` log). |
| patch pass + DSP tests (B, C) | **no** | DR1/DR2/DY1 reset and boot the pair, which kills the oscillator and the meter node. Rails must be down through every boot (PW 09-10, S116 Q4). AS-DAC and AL1 use the same oscillator. |

**New order:**
1. START. Machine: group B (ML/CC first, then DR/DY/DC), then group C, rails up, patch setup. Worker: park the kit (§2.3), plug the two USB sticks, then the panel loops.
2. Patch pass. Machine, in the background: group A network tests plus the two USB ports.
3. Report, once both are done.

**Arithmetic.** B+C today = 50 + 44 + 0.7 = 95 s. Add 12.5 s patch setup = 107 s of machine before the first patch. Worker before the first patch = 8 moves + panel loops = 24 + 42 = 66 s (3 s) or 40 + 70 = 110 s (5 s). Group A (116 s) sits under a patch pass of 358 s or more.
- Saving at 5 s = 210 − max(0, 107 − 110) = **210 s**.
- Saving at 3 s = 210 − max(0, 107 − 66) = **169 s**. With §2.6 done it rises to 210 s.

This changes PW's "automated, then manual, then one report" ruling in order only. It still has one START and one report.

### 2.2 ENTER on a USB footswitch

The worker's hand stays on the connector. The foot confirms while the hand lets go. The station already reads a USB keyboard's Enter (`d24_patch.py:1117` KeyWatch), and an off-the-shelf USB footswitch types Enter.

Arithmetic: 91 presses × (0.8 − 0.2) s = **55 s**. The 0.2 s left is E (the tap overlaps the hand's release). ENTER stays the worker's confirmation, as ruled.

### 2.3 Park the kit; zero lead changes

Each lead has one end that never moves in its block:

| lead | parked end |
|---|---|
| XLR lead | output end on the first XLR output |
| XLR-to-jack lead | a second XLR output |
| jack-to-XLR lead | a second XLR input, not the reference input |
| XLR-to-mini-jack lead | a third XLR output |
| 150 Ω plug | on the bench, in reach |

All five go on during step 1 of §2.1, under machine time. A "lead change" then becomes "pick up the lead hanging from AUX 3". It is one move, not two, with no separate screen. Only the active route carries tone. The isolation check already asks whether a lane *rose*, so parked leads read nothing.

Arithmetic: 4 changes × 2 moves = 8 moves (24 / 40 s). Parking costs 5 moves, but they are hidden in step 1. If the first XLR output proves dead in block 1, one instruction moves the jack lead's parked end.

### 2.4 Start the reading when the tone arrives

The reading starts on ENTER today. The lead must stay in until it ends, so machine time after ENTER is always on the worker's path. PW's "machine under the hand move" target cannot hide it while it starts on ENTER.

- **Settle from the event.** `measure()` counts its settle windows from the call (`d24_patch.py:381`), not from the change. The route is set before the prompt, and the lead went in at least 0.8 s before ENTER, which is about 9 windows. Only the 2 read windows are needed (171 ms), not 4-6 + 2 (436 ms M, S121). Arithmetic: ~55 tone measurements outside the gain steps × ~0.27 s = **~16 s**.
- **Pre-arm.** Take the reading as soon as the detector sees the tone rise ("Signal found"). At ENTER, one meter peek confirms nothing moved (within 0.5 dB), and the verdict shows at once. ENTER still gates the verdict and the advance. Arithmetic after a footswitch: 67 tone patches × 0.2 s = **~13 s**. Without a footswitch it is worth ~40 s (24 × 0.8 + 43 × 0.5).
- Total **~29 s**.
- Risk (low): a half-seated connector read mid-insertion. The stability check and the re-peek at ENTER cover it.

### 2.5 Rear sockets and foot pedal

- **USB ports 3/4:** the worker plugs two sticks during step 1 and the machine reads `lsusb` in the background. This removes a card, two Done presses and a mid-test walk to the rear.
- **"Is the mains lead fully home, and is the unit running from it?":** the unit running the test answers it. Retire the question.
- **Foot pedal station:** all six rows are fixture-not-built or blocked. Record them NOT RUN automatically until the fixture exists, with no visit.
- **Panels:** one card for both panels, not two.

Arithmetic standalone: 2 × 0.8 + mains 3/5 + pedal 6/9 + 2 cards 6/10 = 17 / 26 s. After §2.1 the 5 s worker is the critical path, so all 26 s count. The 3 s worker is balanced against the machine, so only ~3 s counts.

### 2.6 The automated set's machine time

After §2.1 these matter only when B+C is longer than the worker's pre-patch time (trained workers). Machine seconds:

| change | saved | basis | risk |
|---|---|---|---|
| One `stest` probe for ML-M, ML-P1 and ML-P2; end the window when all three identities are in | 10 | M: 5 s each, identical output | none |
| AS-CPLD overrun window = last boot → end of group C, not a dedicated 10 s | 10 | M: `:1206` sleep(10) | none; the window is longer |
| AL1 route/close write through one open DSP link (as the patch station does, 9.6 ms a cell) or dropped by S122's haptic node | 10 | M: 17 s after a boot vs 7.1 s warm | none |
| Fold DY1 into DR1/DR2: boot (DR2 verdict + SPI_RDY high), one dip (DR1 heartbeat stop + SPI_RDY low), final boot | 7 | M: DY1 row 7 s | none; the same two reads |
| Heartbeat deltas from snapshots already taken (DR1 2.5 s of sleeps, AS-DSPA/B 1 s each) | 3 | code | none |
| Link-alive asked once per boot, not twice in group C | 2 | E: "a couple of seconds" (`:2632`) | low |
| Codec init once per session, not before CC and again in AL1 | 1 | E: "about a second" (`:2739`) | low |
| **total** | **43** | | |

Bigger, and real risk until root-caused: fix the first-cycle config desync so `boot_pair()` does one cycle. With the DY1 fold that is 6 pair boots → 2, about 7 s more (E: half of a ~7 s boot_pair × 2).

Group B+C falls from ~95 s to ~52 s. Add 12.5 s setup and the machine's pre-patch time is 64 s, just under a trained worker's 66 s. Saving at 3 s = 107 − 66 = **41 s**. At 5 s: 0.

### 2.7 Serpentine walks

- Park the output end for the input walk on the **last** output of the output walk (it has just passed), not back on the first.
- Start the input walk at the reference input, where the input end already is.
- Run the line walk from the end the hand is at (MIC 24 → MIC 1).

About 2 moves saved: 6 / 10 s (E). No new sockets; each is still judged alone.

### Things checked that are not worth doing

- **Report generation:** not timed, clearly under a second. Nothing to win.
- **App restarts:** none. RUN ALL runs with `--no-app-restart`, and `app_stop()` skips its 2 s sleep when the mixer is already down (S114).
- **CPLD reboots:** none in the sequence.
- **Assembler-covered tests in the automated set:** AS-PWR, DC CS6-8 and HD-PWR are static reads worth 0 s. The rows that re-prove copper the patch pass proves (AS-ADC, AS-DAC, MC1-2, CC1-2) cost ~8 s together, and that time is hidden after §2.1. They are worth keeping because they point at the converter or chain rather than the socket.
- **Screen latency on the patch screen:** already 2 ms median (M, S123).

---

## 3. Target timeline

Items 1-8 done. Items 9 and 10 need no action once item 1 lands.

| phase | machine | worker | 3 s | 5 s |
|---|---|---|---|---|
| START → first patch | groups B+C (~52 s) + patch setup 12.5 s = 64 s | park 5 leads + 2 USB sticks (8 moves) + panel loops + 1 s AL1 hold | max(64, 67) = **67** | max(64, 111) = **111** |
| patch pass | readings 89 − 16 = 73 s; network tests (116 s) in the background | 89 moves (91 − 2 serpentine) + 91 footswitch taps × 0.2 s | 267 + 18 + 73 = **358** | 445 + 18 + 73 = **536** |
| handback + report | | | **2** | **2** |
| **total** | | | **427 s = 7.1 min** | **649 s = 10.8 min** |
| vs now | | | −340 s (−44 %) | −361 s (−36 %) |

With PW decisions 5 and 7 as well (§4): about **6.4 min** at 3 s and **9.8 min** at 5 s. That is −29/−48 s for the combined socket stop, plus the pre-arm gain already counted.

**The largest hand block left is EIN**: 24 plug swaps + 24 ENTERs ≈ 77 / 125 s. It is ruled and stays. The footswitch and the in-place swap are the levers inside the ruling.

---

## 4. Decisions only PW can make

| # | decision | recommendation |
|---|---|---|
| 1 | **Overlap:** DSP tests + panel loops first, then the patch pass with the network tests running underneath; one report at the end. This amends "automated, then manual, then report" in order only. | **Yes.** Worth 170-210 s a unit. First proof: one NW4 reading with the patch loop running. |
| 2 | **A USB footswitch in the kit** as the ENTER key (a sixth item). The worker still confirms every patch. | **Yes.** 55 s a unit, no code. |
| 3 | **Kit parked on the unit before the first patch;** no lead-change screens. | **Yes.** 24-40 s, no coverage change. |
| 4 | **The reading may start when the tone arrives;** ENTER still gates the verdict and the advance, with a re-check at ENTER. | **Yes.** ~29 s. |
| 5 | **`factory-test-v2` image:** instant parameter ramps, a 1024-sample (21 ms) measurement window or a runtime choice, S122's haptic node, and the station's standing state as the boot default. Asserted by the existing image check. | **Yes, as one revision.** It is the only honest way to a ≤100 ms gain step (see flag A). It removes AL1's route write and the 5.4 s standing write. |
| 6 | **Retire the mains-inlet question; hide the pedal station until its fixture exists; USB sticks plugged at setup.** | **Yes.** |
| 7 | **Combined socket stop:** at each input do the XLR lead (7 gain steps), then the plug (EIN), then the jack lead (line), with the jack lead parked on a second output. It changes the block order but still moves one end per patch. | **Stopwatch 6 inputs both ways first.** E: 24 traverse moves become in-place swaps, 29 / 48 s, if a swap is ~60 % of a traverse. Juggling three ends could erase it. |

---

## 5. Coverage flags found on the way

**A. Gain steps read off the strip meter can miss a low step (S123 working tree, `d24_patch.py:1424-1468`).**
- The meter latches peaks and decays about 6 dB/s (M, `s121/patch-loop.md:182-188`; `d24_patch.py:335`).
- The step writes the chain (gain up 6-13 dB), then lowers the drive, then peeks 50 ms later. The transient between the two writes is latched, so the peek reads high by roughly the step size.
- If the order is reversed, a step that is wrong-low reads the previous step's peak (0.3 dB of decay in 50 ms) and passes.
- For S123 to check on the part: seven steps on a good input, meter against node.
- Honest options:
  - the node reading on today's image, 2 windows ≈ 171 ms a step, ~1.5-2 s an input;
  - a peak reset between steps;
  - decision 5's 21 ms window, which gives ≈60-70 ms a step.

**B. Rails go up twice per RUN ALL.** The self-test lowers AN_EN at its handback, and the patch station raises it again. This is against "raised once, after the last DSP boot". Fix: RUN ALL keeps the rails up (`--al1-keep-rails`) and the patch station hands back at the end. It costs 0 s.

**C. The network tests need a peer host on the factory bench.** Today that is the dsp machine at .211 (`BENCH_HOST_SELF`), with a gigabit path for NW4. It is not a speed item, but §2.1 assumes the network lead is in at START.
