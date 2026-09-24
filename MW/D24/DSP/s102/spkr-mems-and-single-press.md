provenance: AI-drafted 2026-09-24 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S102 — the speaker route was never missing, it was never named; and one press runs a test

Three things, and the first two turned out to be one. `SP1` had been a permanent
`NO DATA` reading *"no TEST_OSC → SPKR route in the topology"* since S90. That
sentence is wrong, and this session proves it wrong on the unit: the route is
there, it has always been there, and every hop of it has a contract cell. What
was missing was a **name** — the speaker's output slot is called `Monitor Out`,
after a pair of rear-panel jacks it does not drive.

## 1. Where the speaker actually is

Three independent sources, none of them new, agree:

| source | what it says |
|---|---|
| `mx26 tools/netlist/parts.csv:67` | `AK4619 … out:22=AOUT1L,23=AOUT1R,24=AOUT2L,25=AOUT2R` — and *"On the D24 only AOUT1L (pin 22, via C23) is fitted; C20/C21/C22 on AOUT1R/AOUT2L/AOUT2R are DNP"* |
| `mx26 docs/d24-netlist-global-pins.csv` | net `G0209` has exactly two pins, `analog U3.22` and `analog C23.+`; net `G3461` (`SPKR`) is `analog C23.-` + `analog J59.12`; then `digital J42.12` → `C82` → TS482 (`digital U32`) → `SPKR0`/`SPKR1` (`G3462`/`G3463`) → `lswitch J1.6/7` → `J2.1/2` |
| `mx26 docs/d24-signals.csv:85` | the `CODEC_DAC` lane carries *"`CODEC_OUT_1..CODEC_OUT_4` (talkback speaker; aux out L/R)"* — `CODEC_OUT_1` **is** the speaker |

And the node graph already said which slot that is:

```
C2_MON_OUT,2,OUTPUT_TDM,Monitor Out,2,C2_MON_DLY,,1,1796,
    sport_id=2;slot_start=0;slot_count=2;sport_slots=8;signal=CODEC_OUT_1;scope=D24
```

**So the D24 panel speaker is codec TDM slot 0 = `C2_MON_OUT`'s LEFT slot.**
A search of the topology for `spkr`/`speaker` returned zero hits at S90 for the
same reason a search for a person returns nothing when you spell their name
wrong. The signal path, end to end:

```
C1_TEST_OSC ──inject at C1_IN_20──▶ strip 20 ──▶ C1_RTG_20 (main_on)
   ──▶ C1_BUS_MAIN_L/R ──interchip──▶ C2_MIX_MAIN_L/R ──▶ C2_MAIN_FDR
   ──▶ C2_MON ──▶ C2_MON_DLY ──▶ C2_MON_OUT slot 0
   ──▶ AK4619 AOUT1L (analog U3.22) ──▶ C23 ──▶ SPKR ──▶ analog J59.12
   = digital J42.12 ──▶ C82 ──▶ TS482 (digital U32) ──▶ SPKR0/SPKR1
   ──▶ lswitch J1.6/7 ──▶ J2.1/2 ──▶ the panel speaker
```

Every DSP hop has a host-writable cell: `Chan020MainOn001`, `Chan020Level001`,
`Chan020Pan001`, `Chan020Mute001`, `Main001Level001`, `Main001Mute001`,
`Mon001Level001`/`Mon001Level002`. None of them needed inventing.

### 1.1 The S89-2 hold is released

S90-P6 held `SP1` behind S89-2 — two codec output slots that no gather entry
writes — on the reasoning that adding a speaker node beside a half-wired pair
would be premature. That reasoning does not survive the pin map. `AOUT1R`,
`AOUT2L` and `AOUT2R` are the **three DNP outputs**, and they are exactly
`C2_MON_OUT` slot 1 and both `C2_CODEC_AUX_OUT` slots. The undriven slots reach
no fitted part on a D24, so they cannot hold `SP1` up, and the ONE slot that
matters — slot 0 — is driven, and S89 measured it clean to −110 dBc.

## 2. What was added, and where

The route needed no new node and no new cell. What it needed was a declaration,
and the tier that owns DSP signal routing is the node graph this repo owns,
`MW/D32/DSP/SHARC/dsp.csv`. The existing pattern that fits is a node param —
the same shape as `TALKBACK`'s `invert_opt` (S71), which records that one
input's *wiring* is not a property of its type:

| file | change |
|---|---|
| `MW/D32/DSP/SHARC/dsp.csv` | `sink=SPKR` on `C2_MON_OUT`; `sink=DNP` on `C2_CODEC_AUX_OUT` |
| `tools/dsp/dsp_validate.py` | `sink` added to `OUTPUT_TDM`'s `EXTRA_PARAMS`, with the reason in the source |

`dsp_validate.py` refuses an unrecognised param key rather than passing it
through, which is why the allowlist had to move first — the no-fallback policy
working as intended.

**The declaration is byte-neutral on every generated artefact.**
`./regenerate-dsp-contract.sh` ran clean and left exactly two modified files,
the two above: no cell moved, no address moved, no matrix row moved, no SHARC
source moved, `defs.lock` unmoved at `defs-v2026.09.19.3`. Nothing was written
into `defs/` — this spoke is a consumer, and a param on the node graph is not a
product def. **No contract version bump is owed**, because no generated output
changed.

```
Regenerate summary
  Contract: defs-v2026.09.19.3
  defs commit: 6fd91594315912e856b2e092d9b259f0d02da016
  D24 matrix rows: 5002 (generation 54c7eafc8811)   D24 matrix DSP addresses: 3989
  Generated: 776 SHARC sources from MW/D32/DSP/SHARC/dsp.csv
$ git status --short
 M MW/D32/DSP/SHARC/dsp.csv
 M tools/dsp/dsp_validate.py
```

## 3. The combined test: one sequence, two rows

**Decision: ONE runner sequence, TWO catalog rows, with the dependency stated.**

One sequence, because they are one measurement. `SP1` plays a tone out the
speaker and the only thing that can hear it is `MM1`'s MEMS mic on the same
Left Switch board; `MM1`'s idle floor **is** `SP1`'s reference level. Two
separately-triggered tests scanning the lane at two different moments would be
able to disagree about the same lane.

Two rows, because they are two **parts**. The workbook is an inventory-coverage
sheet — 56 is the mic, 57 is the speaker — and S101 established that the item
names are the acceptance keys. A unit with a live mic and a dead speaker has to
land on 57 and not on 56, and merging the rows would leave one part with no row
at all.

Mechanically: `_spkr_capture(r)` runs the whole sequence once and caches it on
the rig; `t_mm1` takes the idle half, `t_sp1` takes the tone half. Running
either alone still runs the sequence, because `SP1` needs the floor anyway.

### 3.1 The sequence

1. `dsp4_rxscan.py` — the MEMS lane at idle. rms dBFS and CARRYING/STATIC.
2. Is this a pair that can be driven at all? `_osc_blk_q_C1_TEST_OSC` in
   `chip1.sym.json` — the symbol exists only inside `#if DSP4_TEST_NODES`.
3. **Assert the route and read it back.** Every other strip off MAIN, then the
   donor strip, the main fader and the monitor level, through `s89_set.py` —
   SPI parameter writes through the image's own dispatch table, followed by a
   read of the same words back. This runs whatever the rails are doing.
4. `dsp4_s49_osc.py --strip 20 --freq 1000 --level -20`, then rescan.
5. `--off`, then rescan again.

PASS when the tone is ≥ 20 dB above the idle floor **and** the floor returns to
within 3 dB with the tone off.

### 3.2 Two traps closed on the way

- **`s89_set.py` and `dsp4_s49_osc.py` are not in `/home/app/dspboot`.** The
  stage directory's symlink loop cannot find them, which is the exact trap that
  made `loopthd.sh`'s first run measure the default configuration and report
  PASS on a route it had never asserted (S89e). Both are now in
  `stage_setup`'s explicit copy list. Confirmed on the unit: `ls` of both paths
  under `/home/app/dspboot` returns "No such file or directory".
- **`s89_set.py` exits 0 whatever it printed.** The exit code alone does not
  say the route was asserted, so the check is on the text: a `Traceback` in
  either write, or `NOT IN CONTRACT` in the route write, fails the test loudly.
  `NOT IN CONTRACT` is *expected* on the close write and only there — it walks
  strips 1–32 and a D24 has 24.

The first live run of the session proved the check earns its place: the pair
had not come up (the parameter link would not phase), every write raised
`IOError: cannot phase the parameter link`, and `SP1` reported
**"the route write failed — nothing downstream would be measured"** instead of
a reading.

## 4. On the unit: the distinction that was the point

`--section C --only MM1,SP1` against MW-D24-2, pair booted through the standard
`boot_pair` recipe, `s89_signbit` gate CLEAN on both lanes.

| | before (S90) | after |
|---|---|---|
| `SP1` | `NO DATA` — *"no TEST_OSC → SPKR route in the topology"* | `NO DATA` — **"route asserted and read back; waiting on the analog rails … and a DSP4_TEST_NODES=1 pair"** |
| `MM1` | `NO DATA` — the MEMS lane STATIC with `AN_EN lo` | unchanged: `1 MEMS lanes all STATIC with AN_EN 26: op -- pd \| lo` |

The evidence `SP1` now records, verbatim from
`MW/D24/DSP/s90/logs/2026-09-24T094213Z/SP1.txt`:

```
--- the route ---
Chan020MainOn001           chip1 addr 2820   0x00000001  0.000000
Chan020Mute001             chip1 addr 2818   0x00000000  0.000000
Chan020Level001            chip1 addr 2816   0x3F800000  1.000000
Chan020Pan001              chip1 addr 2817   0x3F000000  0.500000
Main001Level001            chip2 addr 1379   0x3F800000  1.000000
Main001Mute001             chip2 addr 1381   0x00000000  0.000000
Mon001Level001             chip2 addr 1789   0x3F800000  1.000000
Mon001Level002             chip2 addr 1790   0x3F800000  1.000000
--- read back through the image's own dispatch table ---
Mon001Level001             chip2 addr 1789   0x3F800000  1.000000
Mon001Level002             chip2 addr 1790   0x3F800000  1.000000
Main001Level001            chip2 addr 1379   0x3F800000  1.000000
Chan020MainOn001           chip1 addr 2820   0x00000001  0.000000
--- MEMS lane, idle ---
XIN_MEMS   46  736  7  0  16  1  -186.64  -186.64  ffffffff ffffffff ffffffff  STATIC
```

`Mon001Level001` at chip 2 address 1789 is the speaker's own level word. It
took a write and gave it back. **That is the proof the definition work is
real**: the route is not a prerequisite any more, it is a reading.

### 4.1 And on the glass, through the wizard's own button

The same reading was then taken on the unit, by one press of `START` on row 57:

| capture | what it shows |
|---|---|
| `live-57-before.png` | `#57 Left Switch PCBA \| Speaker`, last result `SP1 NO DATA 2026-09-23T12:31:23Z — no TEST_OSC -> SPKR route in the topology` |
| `live-57-after-one-press.png` | `SP1 NO DATA 2026-09-24T09:53:47Z — route asserted and read back; waiting on the analog rails (AN_EN = …`, and `#57 finished at 10:53:47` |

`matrix-app` stayed `inactive` throughout (`--no-app-restart` in the
test-display role) and `d24-testui` stayed `active`, so the display never left
the technician.

Deployed for it, all md5-matched against the local artefacts:

| artefact | md5 | rollback |
|---|---|---|
| `/home/app/app` | `998a12bfe5daaca4dd924f9dc8673397` | `/home/app/app.bak-s102-pre` (`1e1e412c…`, the S100 build) |
| `/home/app/selftest/test-catalog.csv` | `eebeeb3f5db35f5ef3a06f3796f210ba` | `…csv.bak-s102-pre` (`059d8730…`) |
| `/home/app/selftest/d24_selftest.py` | `4e359f9b566756eed15fec62d2791340` | `…py.bak-s102-pre` (`bc8c4936…`) |
| `/home/app/selftest/s89_set.py` | `bead35c7522632d659ff9a5a9abf2cea` | new file |
| `/home/app/selftest/dsp4_s49_osc.py` | `d63c1ec40a206625b497b5271967dfe3` | new file |
| `/home/app/skins/D24TEST.mxs` | `f517539d6a7c2b3ac72a65d35267f8da` | **regenerated byte-identical — not redeployed** |

## 5. What is left for a PW-present session

Two prerequisites, neither of them a def, and neither of them workable from a
dispatched session.

1. **The analog rails.** `AN_EN` is CM4 GPIO26 and it is `lo`. A dispatched
   session never writes it (bench note 19 / S49-15) and this one did not: it
   read `lo` at the start of every run and `lo` at every handback. Without the
   rails the MEMS lane sits at `0xFFFFFFFF` and the TS482 has no supply, so
   **neither** half can read.
2. **A `DSP4_TEST_NODES=1` pair.** `TEST_OSC`'s injection hook is inside that
   build guard; the staged pair is the shipping pair, which carries the
   oscillator's sixteen words and nothing that reads them. This is the same
   prerequisite `AS-DAC` already carries.

### The sequence to run, once the rails are up

```bash
# 1. build and stage a TEST_NODES pair (the loopthd arm already does exactly this)
cd ~/dsp/MW/D32/DSP/SHARC && ARM=s102 DSP4_TEST_NODES=1 ./loopthd.sh   # builds + stages

# 2. raise the rails.  PW ONLY.
ssh app@192.168.1.219 'sudo pinctrl set 26 op dh'

# 3. one press on row 57 of the wizard, or from the bench host:
cd ~/dsp && python3 tools/pi/d24_selftest.py --section C --only MM1,SP1
```

Expect: `MM1` PASS (the lane CARRYING with a real floor) and `SP1` PASS with a
measured line of the shape `idle −xx.xx dBFS, tone −yy.yy dBFS (+zz.zz dB),
back −xx.xx dBFS`. **It is an acoustic test** — the speaker has to be fitted in
`lswitch J2` and the panel assembled, and the room has to be quiet enough for a
20 dB margin. A FAIL is now meaningful and the wizard carries a remedial line
for it that walks the analog half from `U3.22` to the J2 lead.

## 6. Single-press START

The two-press confirm is gone. Pressing `START` on a bus-exclusive row runs it
immediately, like any other row.

| file | change |
|---|---|
| `mx26 src/sw/app/Core/TestSkinStore.cs` | `_armedKey` field and both resets removed; the arming branch removed from `StartSelected()`; the `"CONFIRM — STOPS THE APP"` branch removed from `StartLabel()`; `"PRESS START AGAIN TO CONFIRM."` removed from both `RunNote()` branches; the method's doc comment rewritten to say why |
| `mx26 src/sw/app.Tests/TestSkinLayoutTests.cs` | the `"CONFIRM — STOPS THE APP"` layout case dropped — the label no longer exists |
| `mx26 tools/d24/build-d24-test-skin.py` | `SHORT_RUNNER_STOPS`: "press START TEST twice" → "press START TEST" |
| `mx26 tools/d24/preview-d24-test-skin.py` | the same `RunNote` text, so the offline preview still mirrors the app |

**The instructional text stays.** The detail page still says the run needs the
matrix bus to itself and stops the mixer; that is worth knowing. What went is
the forced second press, whose whole justification — the display going dark —
S97 removed when it split the wizard into its own process. In a factory flow an
accidental press re-runs one test a moment later. That is not a hazard.

**Tests: 163/163 green** (164 − the one layout case for a label that is gone).

### 6.1 Witnessed

| capture | what it shows |
|---|---|
| `live-56-before-press.png` | `#56 Panel MEMS mic (talkback)` — a **section C, bus-exclusive** row. The instruction line reads *"No action needed — **press START TEST**"* (was "press START TEST twice"), and the run note ends *"…this display is a separate process and stays up throughout"* with no `PRESS START AGAIN TO CONFIRM` |
| `live-56-one-press-running.png` | taken 3 s after **one** tap on `START`: the status tile reads `RUNNING`, the button reads `RUNNING…`, and the page prints `started MM1 at 10:52:21 in d24-selftest.service — Running as unit: d24-selftest.service; invocation ID: 7584716c8fd146dcaf9c84745d610152` |

`systemctl is-active d24-selftest` read **active** after that single press, and
again after the single press on row 57 (invocation `4b528f959ad047b994ec1c6d8b79f82a`).
There is no second press anywhere in either sequence.

Presses went in through `d24_touch_inject.py` on `/dev/uinput`: **they prove the
skin, the store and the catalog, and nothing about the ILITEK panel or its
cable.** That is still PW's finger.

## 7. Findings for the hub

### 🔴 S102-1 — S89's "Monitor L" jack was not `C2_MON_OUT`

S89's TRS-jack leg loop-cabled *"Monitor L out → MIC 6 in"* and attributed the
reading to `C2_MON_OUT` slot 0, explaining a level ~20 dB below expectation as
*"it is a codec DAC, where AUX 1 is an AK4458"*. The netlist does not allow
that attribution: `C2_MON_OUT` slot 0 is `AOUT1L`, whose net has **exactly two
pins** — `analog U3.22` and `analog C23.+` — and continues to the speaker
amplifier and nowhere else. **There is no jack on that path.** The rear panel's
`Monitor Out L`/`Monitor Out R` TRS jacks (`d24-io.csv`) are therefore fed by
some other node, and this session did not establish which. Two consequences:
the −2.72 dBu figure belongs to a different output than the one it is filed
under, and its "not a fault" explanation rests on the wrong converter. Wants a
bench re-take with the cable identified, or a hub ruling on where the row sits.

### 🔴 S102-2 — `C2_CODEC_AUX_OUT` reaches no fitted part on a D24

Its two TDM slots are `AOUT2L` and `AOUT2R`, both DNP, as is `C2_MON_OUT`'s
slot 1 (`AOUT1R`). The node, its gather entries and its two TX slots are dead
weight on a D24, and `mx26 docs/d24-signals.csv` still describes the codec lane
as carrying "aux out L/R" as though those outputs exist. Recorded here as
`sink=DNP` and nothing else, because removing the node moves the chip-2 TX
gather and that is a contract change, not a declaration. Hub's call: remove it
from the D24 scope, or correct the signals doc and leave it.

### 🔴 S102-3 — `MM1` cannot separate "lane stuck" from "no PDM clock"

Carried forward unchanged from S90 and restated because the combined test does
not close it: the CPLD's lane witness counts `cdc_o` only, there is no counter
on the MEMS group (bench note 31), so with the rails up a static lane could be
either. `MM1`'s criterion today is only CARRYING-vs-STATIC.

## 8. Files

| repo | file | change |
|---|---|---|
| dsp | `MW/D32/DSP/SHARC/dsp.csv` | `sink=SPKR` on `C2_MON_OUT`, `sink=DNP` on `C2_CODEC_AUX_OUT` |
| dsp | `tools/dsp/dsp_validate.py` | `sink` allowed on `OUTPUT_TDM`, with the reason |
| dsp | `tools/pi/d24_selftest.py` | the combined `_spkr_capture` sequence behind `t_mm1`/`t_sp1`; the route write and its read-back; `s89_set.py` and `dsp4_s49_osc.py` added to `stage_setup`'s copy list |
| dsp | `MW/D24/DSP/accept/item-status.csv` | the live `MM1`/`SP1` rows |
| dsp | `MW/D24/DSP/s102/` | this report |
| mx26 | `src/sw/app/Core/TestSkinStore.cs` | single-press START |
| mx26 | `src/sw/app.Tests/TestSkinLayoutTests.cs` | the retired label case |
| mx26 | `tools/d24/build-d24-test-skin.py` | `SP1` out of `NO_FAIL_TESTS`, its remedial line, the single-press short line |
| mx26 | `tools/d24/preview-d24-test-skin.py` | the `RunNote` mirror |
| unit | `/home/app/selftest/{d24_selftest.py,s89_set.py,dsp4_s49_osc.py}`, `/home/app/app`, `/home/app/selftest/test-catalog.csv` | deployed, md5-matched, rollbacks at `*.bak-s102-pre` |
| mx26 | `docs/spec-d24-selftest.md` | `MM1`/`SP1` rows, prerequisite 5 withdrawn, the gating table |
| mx26 | `docs/spec-d24-test-skin.md` | single press, `NO_FAIL_TESTS` down to eight, row 57 off the permanently-amber list |

## 9. Unit as found

| | |
|---|---|
| role | `d24-testui` **active**, `matrix-app` inactive — test mode, as S100 left it |
| `AN_EN` (GPIO26) | **never written.** `op -- pd \| lo` at every read, including the final one |
| `CS_M` (GPIO27) | `ip pu \| hi` |
| CPLD | not flashed; `candidate-s82` untouched. The pair boots from the runner's own copy in `/home/app/s90`, as it always does |
| instrumentation | capture drop-in removed and `systemctl show d24-testui -p Environment` back to the two shipped variables, checked against the running process's own `/proc/…/environ` (0 `MX_DRM*` vars); injector killed, `/tmp/tap` and every `s102-*` file removed |
| 595 chain | the runner's own handback wrote its SAFE image, `VERIFIED 200/200`. That is `d24_selftest.py`'s existing behaviour, not a change of this session's; it supersedes the gain code 0 S89e left |
| one thing not ours | `/home/app/logs/testui.png`, zero bytes, dated 2026-09-23 20:39 — a capture-path leftover from an earlier session. Left alone |
