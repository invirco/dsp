provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S113 — test order for a batched self-test setup (desk study)

Hub dispatch `HUB DISPATCH 2026-09-26 10:18Z`, item (d) of the 09-26 self-test
speed plan. Desk only: nothing was run, nothing was touched on MW-D24-2. The
numbers below come from the runner's source and from the record stamps left by
runs that are already in the tree.

**Headline.** The automated set costs **1025 s (17.1 min) in 34 presses** today
and **435 s (7.2 min) in one press** in the order proposed here — a saving of
**590 s (9.8 min, 58 %)**. Of the 435 s that remain, **246 s is NW3 alone**.
The manual set costs roughly **119 min** in catalog order and **91 min**
grouped, and cuts station changeovers from **39 to 13** — but that estimate
rests on assumed per-row operator times and should be read as a shape, not a
measurement.

---

## 1. Method

### 1.1 What a press actually is

One START press launches exactly one runner process
(`~/mx26 src/sw/app/Core/TestSkinStore.cs:1067-1074`):

```
python3 /home/app/selftest/d24_selftest.py --local --no-soak-wait --no-app-restart \
        --csv <status.csv> --section <row.runner_section> --only <row.tests>
```

So **every press pays the whole prologue and epilogue of a run** for whatever
one row asked for. `--section` and `--only` come straight off the catalog row,
and a row with no `tests` string has START disabled
(`TestSkinStore.cs:1038-1041`), which is why only **34 of the 202 catalog rows
are pressable at all**. The remaining 168 are operator work.

### 1.2 Where the setup lives

Reading `tools/pi/d24_selftest.py:2272-2455` (`main`), the per-press fixed cost
is:

| block | when it runs | code |
|---|---|---|
| python3 start, argparse, `Rig` | every press | `:2272-2348` |
| `app_stop()` — `systemctl stop matrix-app`, `time.sleep(2)` | section B or C | `:2106-2112`, called `:2377` |
| `stage_setup()` — copy the pair, symlink `/home/app/dspboot/*.py`, scp five tools, `md5sum` | section B or C | `:1922-1949`, called `:2384` |
| `boot_pair()` — 2 × (`dsp4_boot.py` + 2 × `dsp4_config.py`) + `s89_signbit.py` | **unconditionally on any section-B press** `:2399`; on any section-C press that is not `--only AL1` `:2421` | `:2005-2026` |
| `ensure_pair()` — MAGIC/BOOT_STAGE first, boot only if it does not answer | `--only AL1` only | `:2048-2065`, called `:2418` |
| `handback()` — 595 SAFE image, `CS_M op dh`, AN_EN restore | section B or C, in a `finally` | `:2114-2157`, called `:2433` |

The line that matters most is **`:2399`**. It is not inside an `r.run()`, so a
press for `ML1` — a cell read over the H1S1 UART that never touches the DSP
link — still boots both SHARCs twice and configures them four times.

### 1.3 The cost model, and where each number comes from

Measured, from the record stamps in
`MW/D24/DSP/s90/logs/2026-09-22T185954Z/*.txt` (a full `--section A,B,C` run;
`Rig.record()` stamps at the end of each test, `:1978`→`:212`, so consecutive
stamps bound each test):

| test | Δ, s | note |
|---|---|---|
| HD0-1 | 2 | from the run's own directory stamp |
| AS-CM4, USB-HUB, NW1 | ≤1 each | |
| NW3 | 41 | **one** `ping -c 200 -i 0.2` pass; the gateway target and `--nw3-runs` came later |
| NW4 | 25 | 2 × 10 s iperf3 |
| NW2 | 30 | its own 30 s idle control, `:439-442` |
| ML1 … MC3 | 0–5 each | |
| boot_pair + DR1 | 15 | DR1's own sleeps are 2.55 s plus four `dsp4_diag` round trips ⇒ boot_pair ≈ 9 s |
| DR2 | 12 | boot_pair + 2 diags + rxscan(47 lanes) |
| AS-DSPA | 4 | diag + 1 s heartbeat wait + buildcfg + rxscan ⇒ **rxscan ≈ 1 s** |
| AS-DSPB | 3 | no rxscan for chip 2, `:1081` |
| AS-CPLD | 25 | two serial 10 s `dsp4_blk30.py` windows + `dsp4_logic_id.py` |
| AS-ADC | 2 | rxscan only |
| AS-DAC | 4 | `s89_slotcap.py` 256 samples |
| AS-PWR | 0 | static NO DATA, one `pinctrl get` |

Cross-check on the derived prologue: `MW/D24/DSP/s90/logs/2026-09-24T075046Z`
is a `DY1` run (directory stamp 07:50:46, both rows recorded 07:51:15 = **29 s**)
and contains `app_stop + stage_setup + boot_pair(:2399) + _rdy_cycle(which
itself calls boot_pair, :836)`. With boot_pair = 9 s and `_rdy_cycle`'s other
work ≈ 3 s that leaves **≈ 8 s for app_stop + stage_setup**, which is the split
used below (3 s + 5 s).

Anchored, not derived: **one AL1 press = 23 s** (S111,
`s110/acoustic-loop-test.md` §11.5, stopwatched on the glass through the
wizard's own START). The model reproduces it exactly:
`1 (python) + 3 (app_stop) + 5 (stage) + 2 (link_alive) + 10 (AL1 body) + 2 (handback) = 23`.
AL1's body is therefore **fitted to the stopwatch**, not estimated
independently.

Adjusted for today's code: **NW3 = 246 s**, because `--nw3-runs` defaults to 3
(`:2295-2297`) and the test now walks two targets (`:489-491`) — 6 passes × 41 s.
Nothing in the tree has ever run that number; it is arithmetic on a measured
single pass, and it is the single biggest cost in the set.

### 1.4 What is estimated rather than measured

Stated plainly, because four of these carry the headline:

- **`stage_setup` = 5 s** and **`app_stop` = 3 s** — derived from the 29 s DY1
  boundary above, not instrumented separately.
- **`boot_pair` = 9 s** — derived from the 15 s MC3→DR1 boundary minus DR1's
  own sleeps and diags.
- **`handback` = 2 s** under `--no-app-restart`. `_chain()` was measured under
  1 s (MC1 and MC2 share a record second on 09-22). **Without**
  `--no-app-restart` handback costs **27 s**, because of `time.sleep(25)` at
  `:2147`; the wizard always passes the flag, so 2 s is the right number here.
- **NW3 = 246 s** — arithmetic on one measured pass, as above.
- **Every manual row's operator time** — assumed flat per class (press 10 s,
  eye 10 s, encoder/control 20 s, meter 30 s, an analog loopback channel 60 s)
  and every fixture changeover assumed (left/right panel 60 s, pedal 120 s,
  meter and lid 180 s, the H1 harness 300 s). **No manual row has ever been
  stopwatched.** The manual totals are a shape; the changeover COUNT (39 → 13)
  is not an estimate and is the part worth quoting.

---

## 2. The setup table, summarised

`setup-state.csv` carries one row per pressable catalog row (34), with a code
citation in every `evidence` cell. `setup-state-no-runner.csv` carries the
other 168 with `runner = no runner`.

Counted over the **41 distinct test ids** the 34 rows drive:

| state | tests that need it |
|---|---|
| matrix-app stopped (`requires_app = d24-testui`) | 32 of 41 — everything in B and C |
| the pair booted (`requires_pair_boot`) | 13 — DR1, DR2, DY1×2, DC1/DC2-CS1/CS2, AS-DSPA/B, AS-CPLD, AS-ADC, AS-DAC, AL1 |
| `CS_M` driven high | 16 — the 13 above plus MC1/MC2/MC3 |
| AN_EN high | **2** — AS-ADC and AL1 |
| `codec_init()` | **1** — AL1 |
| the 595 chain armed (KNOWN image) | **1** — MC1 |
| the 595 chain SAFE | 3 — MC2, MC3, and AL1 by way of handback |
| a `DSP4_TEST_NODES=1` pair | **2** — AL1 and AS-DAC |
| no hardware access at all (static verdict) | 8 — ML-B0, AS-PWR, DC1/DC2-CS6/7/8 |
| a fixture, a press or a meter | **0** — section 1 is by definition hands-off |

Two things fall out of that table.

**The expensive states are rare.** Only two tests need the rails and only one
needs the codec image, so the rails go up once, at the very end, and come down
once at handback. Only two tests need the test-node pair, and since the
verdicts of everything else are image-agnostic (see §4), the pair never has to
be swapped mid-session.

**Eight tests cost nothing and can sit anywhere.** `DC1/DC2-CS6/7/8` are a
dictionary lookup (`:733-774`), `ML-B0` and `AS-PWR` are static NO DATA
strings. They are placed with their siblings for the operator's sake, not the
clock's.

---

## 3. The groups

`run-order.csv` has all 202 rows, in order, exactly once. Catalog numbering is
untouched (S107: the number is the operator's handle).

### Automated — five groups, one press

| group | name | shared state raised at the start | rows | test time |
|---|---|---|---|---|
| **A1** | CM4 reads — the app stays up | nothing stopped, no DSP link, AN_EN as found | 127, 203, 193, 128, 151 | 307 s |
| **A2** | Matrix bus exclusive — mixer stopped, pair not needed | `app_stop` + `stage_setup` | 102, 202, 201, 125, 143, 126, 144, 112, 199, 111 | 24 s |
| **A3** | The DSP pair — reset, boot, chip selects | A2 + one `boot_pair` | 110, 105, 106, 103, 104, 107, 108, 109 | 36 s |
| **A4** | The pair, read — no new state | A3's exit state (pair at BOOT_STAGE 7) | 194, 139, 195, 140, 196, 200 | 32 s |
| **A5** | Rails up — analog lanes and the acoustic loop | A4 + `AN_EN op dh` + `codec_init()` | 198, 141, 197, 142, 56 | 16 s |

### Manual — eight stations, one visit each

| group | name | what the operator has in hand | rows |
|---|---|---|---|
| **M1** | Left switch panel | a finger and an eye | 43–55, 58 (14) |
| **M2** | Right switch panel | a finger and an eye | 59–94 (36) |
| **M3** | P1 pedal | the pedal, its lead, the RJ45 | 98–101, 129, 145 (6) |
| **M4** | Analog loopback | the H1 self-cable harness, XLR/mini-jack/phones leads | 1–42, 95–97, 146–148 (48) |
| **M5** | Rear plugs | a USB stick, an HDMI sink, the mains lead | 130–134 (5) |
| **M6** | Slot-1 / net card | a card that does not exist — BLOCKED | 135–138, 149, 150, 152 (7) |
| **M7** | A meter | a DMM and the lid off | 153, 163–175, 177–184, 186, 187 (24) |
| **M8** | No bench time | nothing: out of scope or no test declared | 113–124, 154–162, 176, 185, 188–192 (28) |

### Why these boundaries

- **A1 before everything** because it is the only group that does not stop the
  mixer. All 29 `stops_app = 1` rows are in A2–A5, so the mixer goes down once
  and comes back once (and under `d24-testui` the display never goes down at
  all — `TestSkinStore.cs:1016-1022`).
- **A1's internal order is already right** in `main()` (`:2366-2374`,
  `:2443-2445`) and needs no change: HD0-1 first because HD-PWR is *inferred*
  from `r.results['HD0-1']` (`:383-389`); NW2's before-sample taken before NW3
  (`:2371`); HD0-2 and HD-PWR harvested last.
- **A2 needs no boot.** Every test in it is either an H1S1 UART transaction
  (`d24_bus_probe.py`, `codec4619.py`) or the 595 chain — none reads the DSP
  link. Today `:2399` boots anyway. Making that boot conditional on a
  DR/DY/DC test being selected is the one code change A2 requires.
- **A3 is a forced order and already correct**: DR1 needs an advancing
  heartbeat and then stops it; DR2 boots the pair back (`:940`); DY1 dips
  `!RST_D` itself and boots back (`:836`), and one dip serves both chips, with
  the result cached on the rig (`:825-827`) so DY1-RDY2 is free; the DC selects
  need the pair up again.
- **A3 → A4 is a non-transition.** A3 ends with the pair at BOOT_STAGE 7,
  which is exactly A4's requirement. A separate section-C press pays a fresh
  `boot_pair` for this today (`:2421`) and does not need to.
- **A5 exists because of one conflict, and it is resolved once.** AS-ADC and
  AL1 need AN_EN high; nothing else does, and the runner's standing rule is
  that the rails come back down. So the rails are raised once at the head of
  A5 and lowered once in handback. **AS-ADC is MOVED here** out of the
  dark-rail block: run in A4 it can only return NO DATA with the prerequisite
  note (`:1199-1205`); run in A5 it can actually score. This is the one row
  whose group is chosen by a state requirement rather than by its number.
- **AS-DAC is placed in A5 next to AL1 on purpose.** Its criterion is "slots
  non-constant *while TEST_OSC runs into an output*" (`:1222-1229`) and AL1 is
  the only thing in the set that runs TEST_OSC. Today AS-DAC is NO DATA
  wherever it sits; put beside AL1 it becomes a free upgrade for RUN ALL —
  take the slot capture during AL1's 0.6 s tone and the row gets a verdict for
  nothing. Not proposed here as a code change, only as an order that permits it.
- **No group re-enters a state it has left.** The one place the order is
  forced to move backwards and forwards is *inside* A3, where DR1 must kill a
  running pair and DR2/DY1 must bring it back — that is the measurement, not
  the setup, and it is already paid once.

---

## 4. The one conflicting requirement: which image the session runs

AL1 and AS-DAC need a `DSP4_TEST_NODES=1` pair (`:1482-1484`, `:1222-1229`);
the rest of the set has always run the signed shipping pair. Swapping images
mid-session would cost a re-stage and a re-boot.

It does not have to be swapped. **Every other verdict in the set is
image-agnostic**: AS-DSPA/B score CHIP_ID + heartbeat + BOOT_STAGE (`:1085`),
the DC selects score CHIP_ID (`:880`, `:906`). The only casualty is a line of
**evidence**, not a verdict: `t_dc2` reports whether the S82-signed build
triple is present (`:907-908`), and on a test-node pair it will read
`S82-signed: False`.

So: **run the whole session on the test-node pair** (`pair.conf`, which is how
the unit is already configured — S111's logs show
`/home/app/loopthd/s109`), and take the signed-triple check on its own
shipping-pair pass. That is one transition avoided, and it is the placement the
order above assumes. See 🔴 Q3.

---

## 5. The arithmetic

### 5.1 BEFORE — catalog order, one press per row, setup paid per row

34 presses. Setup per press is `python + app_stop + stage + boot_or_link +
handback` per §1.2; run is the sum of that row's tests.

```
section A rows (127, 128, 151, 193, 203): setup = 1 s each
section B rows (14 rows):                 setup = 1+3+5+9+2 = 20 s each
section C rows, not AL1 (10 rows):        setup = 1+3+5+9+2 = 20 s each
row 56 (AL1, --only AL1):                 setup = 1+3+5+2+2 = 13 s
```

| | seconds |
|---|---|
| setup, summed over 34 presses | **578** |
| test bodies, summed over 34 presses | **447** |
| **BEFORE total** | **1025 s = 17.1 min** |

The per-press detail is the `est_setup_s` + `est_run_s` columns of
`setup-state.csv`. Worth pulling out: **row 128 alone is 303 s** (NW1–NW4),
**row 196 is 45 s** (AS-CPLD's two 10 s windows on top of a 20 s setup), and
**thirteen rows cost 20–25 s to deliver 0–5 s of measurement** — rows 106, 107,
108, 109 and 200 pay 20 s of setup for a test that reads nothing at all.

Note also that 447 s of "test bodies" is more than the 417 s the same tests
cost once each: nine pairs of catalog rows are driven by the *same* test id
(127/203, 102/202, 125/143, 126/144, 112/199, 139/194, 140/195, 141/198,
142/197), so pressing both members runs the test twice.

### 5.2 AFTER — the grouped order, one press

One process, `--section A,B,C`, tests in the A1…A5 order above.

| block | seconds |
|---|---|
| python3 start | 1 |
| **A1** tests (HD0-1 2, AS-CM4 1, USB-HUB 1, NW1 1, NW3 246, NW4 25, NW2 30, HD0-2 1, HD-PWR 0) | **307** |
| A1 → A2 transition: `app_stop` 3 + `stage_setup` 5 | 8 |
| **A2** tests (ML1 3, ML2 1, ML-M 5, ML-P1 5, ML-P2 5, ML-B0 0, CC1 1, CC2 2, MC1 1, MC2 0, MC3 1) | **24** |
| A2 → A3 transition: one `boot_pair` | 9 |
| **A3** tests (DR1 7, DR2 12, DY1-RDY1 12, DY1-RDY2 0, DC1/DC2-CS1/CS2 5, the six static CS rows 0) | **36** |
| A3 → A4 transition: none | 0 |
| **A4** tests (AS-DSPA 4, AS-DSPB 3, AS-CPLD 25, AS-PWR 0) | **32** |
| A4 → A5 transition: AN_EN + 1 s settle + `codec_init` — already inside `_al1_prereq` | 0 |
| **A5** tests (AS-ADC 2, AS-DAC 4, AL1 10) | **16** |
| handback | 2 |
| **AFTER total** | **435 s = 7.2 min** |

```
1025 s  −  435 s  =  590 s saved  (9.8 min, 58 %)
    setup: 578 s → 20 s   (one prologue and one epilogue instead of 34)
    run:   447 s → 417 s  (each test runs once, not once per row that names it)
```

### 5.3 The manual set

Stated assumptions only (§1.4). Setup is charged once per **visit** to a
station; catalog order visits some stations several times, the grouped order
visits each once.

| group | rows | operator time | visits, catalog order | visits, grouped | before | after |
|---|---|---|---|---|---|---|
| M1 left panel | 14 | 150 s | 2 | 1 | 270 s | 210 s |
| M2 right panel | 36 | 400 s | 1 | 1 | 460 s | 460 s |
| M3 pedal | 6 | 100 s | 3 | 1 | 460 s | 220 s |
| M4 analog loopback | 48 | 2790 s | 3 | 1 | 3690 s | 3090 s |
| M5 rear plugs | 5 | 140 s | 1 | 1 | 200 s | 200 s |
| M6 slot-1 card | 7 | 240 s | 3 | 1 | 600 s | 360 s |
| M7 meter | 24 | 720 s | 4 | 1 | 1440 s | 900 s |
| M8 no bench time | 28 | 0 s | 5 | 1 | 0 s | 0 s |
| **total** | 168 | | **39** | **13** | **7120 s = 119 min** | **5440 s = 91 min** |

The honest reading: **the catalog is already nearly fixture-ordered**, so
regrouping the manual rows buys about 28 minutes on assumed numbers, and most
of that is M4 and M7. The countable result is the changeover column: **39
station changes become 13**. The real manual saving will come from ruling the
blocked classes (PL-8 the analog-output class, PL-5, PL-7, PL-11) and from
building the H1 harness, not from reordering.

---

## 6. What S114 should remove first, ranked

### 6.1 Across the whole automated run (the 435 s of §5.2)

| rank | what | seconds | how |
|---|---|---|---|
| 1 | **NW3's six ping passes** | **246 of 435 (57 %)** | `ping -c 200 -i 0.2` = 40 s, × `--nw3-runs` 3 (`:2295-2297`) × 2 targets (`:489-491`). `-i 0.1` keeps all 200 packets and halves it (−123 s); two targets in parallel halves it again; 1 pass per target is −164 s. **Needs a PW ruling — see 🔴 Q1**, because the 3 passes exist on purpose (`:472-479`). |
| 2 | **NW2's 30 s idle control** | up to 30 | `:439-442`. Keep the control, but take it during the A1→A2 transition instead of blocking on it. |
| 3 | **AS-CPLD's two serial 10 s windows** | 10 | `:1104-1105` runs `dsp4_blk30.py 1 10` then `2 10`. Run them concurrently. |
| 4 | **NW4's two 10 s iperf runs** | 10 | `:545-550`. 5 s each still saturates a gigabit link. |
| 5 | duplicate presses of the nine shared-test row pairs | already gone | folded into the 590 s of §5.2 |

Everything below rank 4 is under 5 s and not worth a code change.

### 6.2 Inside AL1 — the actual S114 subject

A press is **23 s for a 0.6 s beep** (S110 §1: 0.55–0.62 s of oscillator-on
time). 22.4 s of it is setup. Ranked by seconds removable from a **repeat**
press, without weakening any criterion:

| rank | what | s/press | why it is safe to skip, and the test |
|---|---|---|---|
| 1 | **`stage_setup()`** | **5** | `:1922-1949` re-copies both `.ldr` and both `.sym.json` and re-scps five tools every press. Compare the staged md5s against the pair's and skip when they match — the run already computes them (`:1948`). |
| 2 | **`app_stop()`** | **3** | `:2106-2112` issues `systemctl stop matrix-app` and then sleeps 2 s unconditionally. In a `d24-testui` session matrix-app is `Conflicts=` and never running. Gate on `systemctl is-active`; keep the stop as the safety belt, skip the sleep when nothing was stopped. |
| 3 | **the route write** | **2** | `:1494-1501` writes a 31-cell CLOSE list and a 12-cell route, then reads four cells back. On a repeat press the route is still asserted. Read the four probe cells **first** and re-write only on a mismatch — and keep the probe either way, it is the evidence that caught the original "measured the default configuration" trap. |
| 4 | **handback's SAFE chain write** | **2** | `:2119` writes and verifies 200 reads every press. AL1 never arms the chain, so an AL1-only press re-writes an image that is already there. Track the last image written this session and skip a no-op. |
| 5 | **`rxscan`** | **1** | `:1487` is a MEMS-lane presence check. Once per session is enough; a lane that was carrying 20 s ago has not vanished. |
| — | `codec_init()` | 2 | **Do not remove.** Unconditional by design (`:2085-2089`): the read arm that could answer "is it already initialised" returns NO REPLY on a cold unit while writes land. |
| — | `link_alive()` | 2 | **Do not remove.** Already the S111 cheap path, and it is what makes a cold press work at all. |
| — | the second baseline | ~2 | **Do not remove.** `:1524-1534` — "tone off again" is what says the floor came back and the reading was the tone rather than the room. |

**Removable: 13 s. A repeat AL1 press goes 23 s → about 10 s**, of which 0.6 s
is still the beep.

### 6.3 One defect found while reading, which RUN ALL must not inherit

`main()` wipes and restarts the HD0-2 soak sampler on **every press that names
HD0-2** (`:2350-2364`, `rm -f /tmp/d24_hdsoak.log`), and the wizard always
passes `--no-soak-wait` (`TestSkinStore.cs:1070`). So pressing row 127 or row
203 destroys whatever soak had accumulated and then harvests a log with one
sample — the row can only ever return *"no soak samples"* or *"window short of
the spec"*. RUN ALL must start the sampler once at the head of A1 and harvest
it at the tail, which is what a full `--section A` run already does and what a
per-row press cannot. See 🔴 Q2.

---

## 7. What has to change in code for this order to be real

Nothing in this study touches code; S114 and the RUN ALL item (b) do. For the
record, the order above needs exactly four changes:

1. **`:2399` — make the pre-DR1 `boot_pair()` conditional** on a DR/DY/DC test
   being in the selection. Saves 9 s on every A2-only press and is the
   precondition for A2 existing as a group.
2. **`:2421` — let a section-C selection use `ensure_pair()`** the way
   `--only AL1` already does, so A4 inherits A3's booted pair instead of
   re-booting. Saves 9 s.
3. **Move AS-ADC after the rails go up** — a runner-order change inside
   `main()`'s section-C block, plus the rails being raised for it. Turns a
   permanent NO DATA into a verdict; costs nothing.
4. **Start the HD0-2 sampler once per session**, not once per press (§6.3).

The app side needs only to read the two new catalog columns, named exactly
**`group`** and **`order`** in `MW/D24/DSP/s113/test-catalog.csv`.

---

## 8. Deliverables

| file | what |
|---|---|
| `setup-state.csv` | 34 pressable rows; the state each needs, its handback, `est_setup_s`/`est_run_s`, and a `file:line` citation per test in `evidence` |
| `setup-state-no-runner.csv` | the other 168, `runner = no runner`, with the fixture/press/meter each will need |
| `run-order.csv` | all 202 rows, grouped and ordered, with `transition_note` on every group boundary |
| `test-catalog.csv` | the s110 catalog with **two appended columns, `group` and `order`** — verified: same 202 rows, same 17 original columns byte-for-byte, no renumbering |
| `test-order.md` | this report |

---

## 9. 🔴 Open questions for PW

**🔴 Q1 — NW3 is 57 % of the whole automated run.** 246 s of 435 s, because it
takes `--nw3-runs` 3 passes against 2 targets at 40 s a pass. The 3 passes are
deliberate (`:472-479`: five consecutive runs on this bench read 2.0 %, 0.5 %,
0.0 %, 0.0 %, so a one-shot verdict is whichever one the scheduler handed it).
Which way?
 (a) leave it — 246 s;
 (b) `-i 0.1`, same 200 packets per pass, half the wall clock — **123 s**;
 (c) 3 passes to the bench host but 1 to the gateway control — **164 s**;
 (d) 1 pass per target — **82 s**, and the reproducibility argument is given up;
 (e) run the two targets concurrently — **123 s**, same packets, same passes.
Recommendation: (e) plus (b) → ~62 s, no reduction in packets or passes.

**🔴 Q2 — what does RUN ALL do about the HD0-2 soak?** The spec wants ≥ 3600 s
and a shorter window is correctly NO DATA (`:377-379`). Options:
 (a) start the sampler at the head of the run, harvest at the end, and accept
 NO DATA on any session shorter than an hour;
 (b) hold the session open for the hour;
 (c) take HD0-2 out of RUN ALL and give it its own long row the operator starts
 at the beginning of the shift and reads at the end.
Recommendation: (c), with (a) as the fallback.

**🔴 Q3 — confirm the session runs on the test-node pair throughout.** AL1 and
AS-DAC need `DSP4_TEST_NODES=1`; every other verdict is image-agnostic (§4).
The only loss is `t_dc2`'s `S82-signed: True` evidence line on rows 103/104. Is
that acceptable, with the signed-triple check taken on its own shipping-pair
pass — or should RUN ALL swap images mid-session (one re-stage + one re-boot,
about 14 s) to keep it?

**🔴 Q4 — may the rails be up for AS-ADC?** PW lifted the "a dispatched session
never raises AN_EN" bar on 2026-09-24 for AL1. Moving AS-ADC into A5 extends
that to the ADC lane scan, which is the only way rows 198 and 141 can score
rather than return NO DATA. Confirm.

**🔴 Q5 — nine pairs of catalog rows are driven by the same test id** (127/203,
102/202, 125/143, 126/144, 112/199, 139/194, 140/195, 141/198, 142/197). In
RUN ALL the test runs once and `record()` already writes a result row for every
item it covers (`:293-298`). Should the wizard's **per-row** START be
de-duplicated the same way — press 127 and row 203 gets the verdict stamped
too — or does each row keep its own press and its own 20 s of setup?
