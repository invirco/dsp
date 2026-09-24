provenance: AI-drafted 2026-09-24 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S103 — the rails went up, and the MEMS lane did not move

Both of S102's prerequisites were cleared: a `DSP4_TEST_NODES=1` pair was built
and staged, and `AN_EN` was raised under PW's ruling of this morning. The
oscillator ran for real. **`MM1` is FAIL and `SP1` is NO DATA**, and the reason
for both is one fact that the rails themselves disproved:

> **The panel MEMS lane reads the same row, byte for byte, with `AN_EN` high as
> with it low. The analog rails were never what was holding `MM1` up.**

| | with `AN_EN` lo (S102, 09:52Z) | with `AN_EN` hi (S103, 10:12Z / 10:17Z) |
|---|---|---|
| `XIN_MEMS` | `46 736 7 0 16 1 -186.64 -186.64 ffffffff ffffffff ffffffff STATIC` | `46 736 7 0 16 1 -186.64 -186.64 ffffffff ffffffff ffffffff STATIC` |
| `MM1` | NO DATA — "STATIC with `AN_EN` lo", a prerequisite | **FAIL** — "1 MEMS lanes all STATIC with `AN_EN` up" |

That is a real result and a fine outcome for this dispatch. It is also the
answer to a question nobody had asked directly, and §3 shows why the answer was
inevitable from the schematic.

---

## 1. The rails: exactly what was done

PW's ruling (`mx26 docs/decision-mx26-mandates.md:871`) lifts one constraint and
nothing else. The two gating conditions of the standing AN_EN ruling
(`:379`, PW 2026-09-10) were satisfied **before** the pin was written, and every
other discipline was kept.

| step | command | reading |
|---|---|---|
| gate (1), digital clocks stable | `dsp4_diag.py --chip 1\|2` | `CHIP_ID 1/2`, **`BOOT_STAGE 7 running`**, `FRAME_COUNT 240189 / 239538` — the pair booted and streaming from the s103 stage |
| gate (2), 595 chain loaded and read back with a safe image | `s55_chain.py 0x01 ×24 0x00` | `VERIFIED 200/200` — gain 0, phantom off, **MUTED** |
| **raise** | `sudo -n pinctrl set 26 op dh` | before `26: op -- pd \| lo` → after **`26: op -- pd \| hi`** |
| … four runs over ~6 minutes … | | `AN_EN` read `hi` at the start and at the handback of every one |
| **lower** | `sudo -n pinctrl set 26 op dl` | before `hi` → after **`26: op -- pd \| lo`** |
| final witness | `s55_chain.py` SAFE, then `pinctrl set 27 ip pu` | `VERIFIED 200/200`, read-back `01 ×24 00`; `CS_M 27: ip pu`; `AN_EN 26: … lo` |

The rails were high from ≈10:11Z to ≈10:18Z. **They were restored**, confirmed
by a direct read, and the unit was left in the state §6 tabulates. No CPLD was
flashed; the shipping pair in flash was not touched.

Nothing untoward happened while they were up. The one thing worth recording for
the next session: `boot_pair` resets and reboots both SHARCs **with the rails
live**, which no session had done before. Four boots, no audible or measurable
consequence, and the 595 chain held SAFE throughout — but it is new ground and
it is named here rather than left to be rediscovered.

## 2. The TEST_NODES pair, and the gap that stood between staging it and using it

```
cd ~/dsp/MW/D32/DSP/SHARC && ARM=s103 DSP4_TEST_NODES=1 ./loopthd.sh
```

built and staged cleanly, exit 0:

| | |
|---|---|
| `chip1.ldr` | `0d4a4416dde80fd3f3bfc5b924b9fe5a` |
| `chip2.ldr` | `6f11a1ddc6efd45ec30f536cef295292` |
| staged at | `/home/app/loopthd/s103`, md5-matched on the unit |
| `_osc_blk_q_C1_TEST_OSC` in `chip1.sym.json` | **True** (6452 symbols) |
| the leg's own THD verdict | **INCONCLUSIVE** — `level -116.09 dBFS` at both drives, "LOOP LEVEL OUT OF WINDOW … the cable is off this lane". That is 🔴 S102-1 (the loop cable was filed against a net that has no jack on it), not a build fault, and not this dispatch's question |

**The dispatch's sequence could not have worked as written, and this is worth
naming rather than papering over.** `loopthd.sh` stages to
`/home/app/loopthd/<ARM>`; `d24_selftest.py`'s `stage_setup` copied the pair it
boots from a hard-coded `/home/app/dspboot/candidate-s82`. Staging a TEST_NODES
pair and then running the self-test would have booted the signed candidate and
reported `waiting on a DSP4_TEST_NODES=1 pair` — a prerequisite message that
was, by then, false.

So the runner gained a way to be pointed at a pair, with the trap that creates
closed by construction:

| mechanism | for |
|---|---|
| `--pair DIR` | a run driven from a bench host |
| `/home/app/selftest/pair.conf` (one line, a directory) | a run launched by **the wizard's own START button**, which passes no arguments — the only way the glass can reach a test-node pair |
| default | `/home/app/dspboot/candidate-s82`, the signed candidate, unchanged |

A pointer to a directory that does not hold all four files (`chip1.ldr`,
`chip2.ldr`, and both `.sym.json`) is a hard **ERROR**, not a silent fall back
to the default — a run that quietly booted the shipping image after being asked
for a test-node one would report a prerequisite rather than the mistake it is.
The resolved directory and *why* it was chosen are printed in the banner
(`pair: /home/app/loopthd/s103 (--pair)`) and carried in `SP1`'s evidence
(`pair booted: …`), so no reading can be mistaken for the shipping pair's.
`pair.conf` is a bench artefact: it was written for the glass press and
**removed at handback** (§6).

## 3. The result, and why it was always going to be this

### 3.1 The oscillator ran — the DSP half of the speaker chain is proven

`TEST_OSC` injected 1 kHz at −20.00 dBFS peak on strip 20 and `TEST_MEAS` read
it back, settling in three windows, on both the bench-host run and the run the
glass started:

```
  SETTLED (seq 3):
    RmsResult      -23.01 dBFS
    ThdResult     -116.12 dB   = 0.00016 %
    NoiseResult   -139.12 dBFS

    injected peak -20.00 dBFS -> a sine of that peak has RMS -23.01 dBFS
    measured RMS is +0.00 dB from it
```

−23.01 dBFS is the exact RMS of a −20 dBFS-peak sine, at 0.00016 % THD+N. The
route S102 named — `C1_TEST_OSC` → `C1_IN_20` → strip → MAIN → `C2_MAIN_FDR` →
`C2_MON` → `C2_MON_DLY` → `C2_MON_OUT` slot 0 — was asserted, read back through
the image's own dispatch table (`Mon001Level001` chip2 addr 1789 `0x3F800000`,
`Main001Level001` 1379, `Chan020MainOn001` chip1 2820 `0x1`), and **driven**.
S102 proved the route could be written. This proves it can be driven.

### 3.2 The microphone did not answer, in any leg

```
--- MEMS lane, idle ---     XIN_MEMS … -186.64 … ffffffff ffffffff ffffffff  STATIC
--- MEMS lane, tone on ---  XIN_MEMS … -186.64 … ffffffff ffffffff ffffffff  STATIC
--- MEMS lane, tone off --- XIN_MEMS … -186.64 … ffffffff ffffffff ffffffff  STATIC
```

Identical in all three, and identical to the reading with the rails down.

### 3.3 The schematic says the rails were never in that path

Traced from the netlist after the measurement, not before it:

```
mic lswitch U3 (IMP34DT05, LR->GND = left)   <- +3V3.00039
   +3V3.00039  <- lswitch U5 (3-pin LDO, pin 2 out)
   U5 pin 3 in <- +5V  <- lswitch J1.1/.14  =  digital J13.1/.14
   +5V is a PSU_DIG_EN digital buck
converter digital U13 (ADAU7002, TDM8 slot 5 strap)  <- +3V3 (digital), pin D1
   +3V3 is a PSU_DIG_EN digital buck
```

| claim | source |
|---|---|
| `digital U13` is the ADAU7002, PDM-to-TDM bridge, strapped to TDM8 slot 5 | `mx26 src/hw/d24-hw-ics.csv:12` |
| `lswitch U3` is the IMP34DT05 MEMS mic | `mx26 src/hw/d24-hw-ics.csv:57` |
| U13's supply pin is on digital `+3V3` | `mx26 docs/d24-netlist-global-pins.csv:8048` (`G2409,digital,+3V3,U13,D1`) |
| the mic's supply is the lswitch-local `+3V3.00039`, shared with the two LVDS parts | `…:8086` and the `G2411` net (24 pins, all on-board) |
| that net is made on the panel board by `lswitch U5` from `+5V` arriving on `J1.1/.14` | `G2411` / `G2418` net members |
| **`AN_EN` gates `PSU_12_CLK` (±15 V) and `PSU_48_CLK` (+45 V phantom) only**; `PSU_DIG_EN` is a separate pin gating the `+5V/+3V3/+0.9V` digital bucks | `mx26 src/fw/pwr-mcu/board.h:6-16`, `mx26 src/fw/d24-pwr-mcu-def.csv:22-23` |

**There is no AN_EN-gated rail anywhere in the MEMS mic's supply chain.** The
measurement and the schematic agree. `MM1`'s blocker is what bench note 31
already said it could not see: the PDM clock, the LVDS pair, the panel ribbon,
or the mic — and nothing on the CM4 reads the clock to tell them apart.

**No unit, on any build, rails up or down, has ever read this lane as anything
but `0xFFFFFFFF`** — S79-2, S86-2, S90, S102 and S103 all record the same. The
only time `XIN_MEMS` ever carried a distinguishable value was S85's CPLD-injected
`_laneid` marker (`f4aea000` → pin 7, slot 5), which proves the lane binding and
says nothing about the microphone.

### 3.4 `SP1` is NO DATA, and that is a decision, not a dodge

`SP1`'s only instrument is `MM1`'s microphone. With the lane STATIC in all three
legs, scoring the speaker FAIL would blame the speaker for a dead mic — a defect
invented by the harness, which is precisely what this runner's own three-word
verdict doctrine forbids. So `SP1` now returns **NO DATA** when *every* leg reads
STATIC, naming the missing read path:

> the MEMS lane is STATIC in all three legs (idle −186.64 dBFS, tone −186.64 dBFS
> (+0.00 dB), back −186.64 dBFS (+0.00 dB)) — nothing was measured

**A lane that carries and does not rise is still a real `SP1` FAIL**, which is
why the test is on the three legs and not on `MM1`'s verdict. S102's remedial
line walking the analog half from `U3.22` to the J2 lead is untouched and will
show the day the mic answers.

### 3.5 A bug that could only be found today

The first run with both prerequisites met came back `RUNNER ERROR:
TypeError('not all arguments converted during string formatting')`. S102's
PASS/FAIL line had five placeholders and six arguments (`ret` passed twice, and
`back`/`ret` transposed) — and it had never executed, because every run until
now stopped at a prerequisite above it. Fixed, and the comment at that line says
why it survived so long. **This is the case for clearing prerequisites even when
the answer is expected to be negative**: the untested path was only reachable
once they were gone.

## 4. On the glass

Presses went in through `d24_touch_inject.py` on `/dev/uinput`: **they prove the
skin, the store and the runner, and nothing about the ILITEK panel or its
cable.** That is still PW's finger.

| capture | what it shows |
|---|---|
| `live-57-before.png` | `#57 Left Switch PCBA \| Speaker`, `SP1 NO DATA 2026-09-24T09:53:47Z — route asserted and read back; waiting on the analog rails (AN_EN = …` — S102's reading |
| `live-57-after-one-press.png` | after **one** press of `START`: `SP1 NO DATA 2026-09-24T10:16:29Z — the MEMS lane is STATIC in all three legs (idle -186.64 dBFS, tone …`, `#57 finished at 11:16:30` |
| `live-56-before.png` | `#56 Panel MEMS mic (talkback)`, `MM1 NO DATA 2026-09-24T09:52:33Z — 1 MEMS lanes all STATIC with AN_EN 26: op -- pd \| lo` |
| `live-56-after-one-press.png` | after **one** press: status tile **`FAIL`** in red, `MM1 FAIL 2026-09-24T10:17:39Z — 1 MEMS lanes all STATIC with AN_EN up`, the score line moving `4 FAIL · 177 not resolved` → **`5 FAIL · 176 not resolved`**, and the authored remedial paragraph appearing: *"A FAIL needs AN_EN up and the lane still static, which is the PDM clock or the mic … Check the panel ribbon first — it is the same one ML-P1/ML-P2 use."* |

Both runs were real section-C runs launched by the wizard's own transient unit
(`systemd-run --collect --unit=d24-selftest`, invocations `10cc22c7…` and
`ea309bce…`), each resolving the pair through `pair.conf`
(`pair: /home/app/loopthd/s103 (/home/app/selftest/pair.conf)`), booting the
pair, running the oscillator and handing back `SAFE image: VERIFIED 200/200`.
`matrix-app` stayed `inactive` and `d24-testui` `active` throughout — the
display never left the technician. **One press each; there is no second press
anywhere in either sequence.**

The remedial line the glass now prints is the right instruction, arrived at
independently of §3.3 and agreeing with it.

## 5. Findings for the hub

### 🔴 S103-1 — the inter-chip link gate reports FOLDED about a quarter of the time, and nothing acts on it

`s89_signbit` is called "the inter-chip link gate" and it **does not gate**. It
exits 0 whatever it prints — 17 calls in the unit's run log, **17 exit 0s**,
including every FOLDED one (and one call that printed no verdict at all) — and
`boot_pair` appends its output to a log nobody checks. So a section-B or section-C reading can be taken across a folded
inter-chip link and neither the row's verdict, nor its evidence, nor its
`measured` string will say so.

The unit's own history, which is not a small sample:

| | boots | CLEAN | FOLDED |
|---|---|---|---|
| all runs in `/home/app/selftest/run.log` | 16 | 12 | **4** |
| today's four TEST_NODES boots (2 host-side, 2 from the glass) | 4 | 2 | **2** |

**It is not the TEST_NODES image.** Two of the four FOLDED boots predate this
session and were on the signed candidate — `2026-09-24T08:25:30Z` (section B)
and `2026-09-24T09:53:26Z`, which is **S102's own row-57 `SP1` run**, the one
behind its `live-57-after-one-press.png` capture. S102 reported the gate CLEAN
for its bench-host run, which it was; the glass run that produced the capture
was FOLDED, and nothing surfaced that.

The signature is unambiguous: `received bit31 0/64 (distinct 64)` — 64 distinct
values come back and not one of them is negative. The MAIN bus that carries the
speaker route crosses that lane, so a folded boot half-wave-rectifies anything
sent to `C2_MON_OUT`. It did not change today's verdicts (the tone was measured
chip-1 side, and `SP1` was NO DATA for a different reason), but it will change
somebody's.

Wants its own dispatch: enough boots to get a real rate, on both images, and
then either a retry-on-FOLDED in `boot_pair` or the gate's verdict carried into
every row's evidence. Not fixed here — it moves reported verdicts, which is the
hub's call.

### 🔴 S103-2 — `MM1` FAIL cannot name which of four things is broken

Unchanged from S102-3 and now urgent, because the row is FAIL rather than NO
DATA. The candidates are the panel ribbon, the LVDS pair (`lswitch U1`/`U2`,
`digital U30`/`U31`), the PDM clock out of `digital U13`, and the mic
(`lswitch U3`) itself. The CPLD's lane witness counts `cdc_o` only — there is no
counter on the MEMS group (bench note 31) — so "lane stuck" and "no PDM clock"
are not separated by any read path that exists on this unit. The remedial line
sends a technician to the ribbon first, which is the right first move and not a
diagnosis.

Cheapest next step, and it needs no new hardware. `lswitch J1` carries the two
MEMS LVDS pairs (`CLK0`/`CLK1` on pins 2/3, `D0`/`D1` on 4/5) **and** the left
panel MCU link (`MCU_RX`/`MCU_TX` on 11/13, `MCU_S0-S3` on 15-18, `MCU_BUSY` on
19) on one connector — and **`ML-P2` (`dig-panel-b`, the left panel MCU link)
PASSes**. So the ribbon is seated and its MCU pins are good; what that does
*not* prove is pins 2-5, which are the only ones the mic uses. That narrows it
to the LVDS pair, the clock, or the mic — and a CPLD counter on the MEMS group
would split the last two. (The glass's remedial line names `ML-P1`/`ML-P2`
together; `ML-P1` is `dig-panel-a`, the **right** panel, and is not on this
ribbon. Worth a one-word fix in the spec next time that text is touched.)

### 🔴 S103-3 — `MM1` has never passed anywhere, so "FAIL" may be describing the design

No unit, no build, no rail state has ever produced a non-static read on this
lane (§3.3). A row that has only ever been one value is not yet distinguishing a
broken unit from a path that was never brought up. Worth the hub knowing before
the FAIL is read as a fault on MW-D24-2 specifically.

### 🔴 S103-4 — `+5V` reaches the panel through `digital J13`, and the workbook may be counting the wrong connector

Noted while tracing §3.3, not investigated: `digital J13` carries both the panel
`+5V` and the MEMS LVDS pairs, and the connector-status generator names `J13`
for the MEMS path. There is also a separate net literally called `MEMS` (CPLD
pin 137 → `J18` P26) documented as vestigial with no digital-side load
(`mx26 docs/d24-netlist-global.md:468-472`). Anyone grepping for `MEMS` will
find the dead one first. Flagged so the next reader does not lose an hour to it.

## 6. Unit as handed back

| | |
|---|---|
| role | `d24-testui` **active**, `matrix-app` **inactive** — test mode, as found |
| **`AN_EN` (GPIO26)** | **raised to `hi` at ≈10:11Z, lowered to `lo` at ≈10:18Z, confirmed `26: op -- pd \| lo` by a direct read at handback.** Named here as the ruling requires |
| `CS_M` (GPIO27) | `27: ip pu` |
| 595 chain | SAFE `VERIFIED 200/200`, read-back exactly `01 ×24 00` — written last, after the final DSP boot |
| CPLD | not flashed; shipping `d02d83b3cc22` untouched |
| DSP pair | booted four times by the runs' own `boot_pair`, handed back each time |
| `pair.conf` | **removed** — `/home/app/selftest/pair.conf` does not exist |
| capture drop-in | removed and `daemon-reload`ed; `d24-testui` **restarted** and its running process checked through `/proc/<pid>/environ` — **0** `MX_DRM*` variables, back to the two shipped ones |
| touch injector | `d24-touchinj` stopped, `/tmp/tap` removed, `/home/app/logs/s103.png` removed |
| runner | `/home/app/selftest/d24_selftest.py` `0e221063f79b7d93a8f02fd7aa451b5f`, md5-matched against the local file; rollback `d24_selftest.py.bak-s103-pre` (`4e359f9b…`, the S102 build) |
| app binary / catalog / skin | **not touched** — no rebuild was needed |
| `defs.lock` | unmoved at `defs-v2026.09.19.3`; no generated DSP artifact changed, so **no contract bump is owed** |

## 7. What changed

| repo | file | change |
|---|---|---|
| dsp | `tools/pi/d24_selftest.py` | `--pair` / `PAIR_CONF` pair selection with a hard error on a bad pointer; the `SP1` format bug fixed; `SP1` returns NO DATA when the MEMS lane is STATIC in all three legs; the pair and its provenance added to `SP1`'s evidence; every "a dispatched session may not raise `AN_EN`" sentence replaced with what is now true |
| dsp | `MW/D24/DSP/accept/item-status.csv` | 5 rows appended — the `RUNNER ERROR` row is left in place as the honest record of what happened |
| dsp | `MW/D24/DSP/s103/` | this report, four captures, the two on-unit evidence logs, the results file as handed back |
| dsp | `MW/D24/DSP/s90/logs/2026-09-24T1011*Z/` | the two bench-host runs' raw reads |
| mx26 | `docs/spec-d24-selftest.md` | **🔴 PW-1 closed** — the spec still said a dispatched session may not raise `AN_EN` and that all 47 section-2B rows were gated on an unanswered ruling. Marked ✅ ruled (option (a), PW 2026-09-24); 2B is now gated on the H1 harness only. What survives of S49-15 is kept and sharpened: it is a **sequencing fact, not a permission** — the first `matrix-app` restart after a hand-raised `AN_EN` drops the rails again. The `SP1`/`MM1` prerequisite paragraph rewritten to today's result |
