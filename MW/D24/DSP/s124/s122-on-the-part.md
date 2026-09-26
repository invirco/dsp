provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S124 — S122's haptic path, proved on the part with no hands; and 1.76 GB back on the unit's disk

MW-D24-2, 2026-09-26 evening. PW had left the bench, so nothing here needed a
hand or an ear: every verdict below is the part's own — the words in the
speaker's transmit slot, the words on the MEMS lane, the host link's own
clock, and chip 2's own cycle counter.

**Headline.** The panel speaker's slot reads **exact digital zero, 256 words of
256, with every mixer bus open and the monitor chain clipping into the +8.0
Q4.28 rail** — the exact state that used to make the speaker hiss. All three of
PW's stored clicks play on trigger at the right frequency and the right length,
and the panel MEMS microphone **hears them in the air**. A cell write is heard
**1.67 ms later**, median, end to end. AL1 runs through the new path and
**PASSES** after recalibration. The factory-test image is bumped to
**`factory-test-v2`** and deployed, and the automated set came back **35 PASS /
0 FAIL** on it.

**And S122 shipped three defects that only running it could find** — the AL1
calibration table was deleted outright, so no AL1 press could ever have
succeeded; and the image assertion that is supposed to stop a substituted pair
cannot tell v1 from v2, because the two carry the same build flags.

---

## 1. What was owed on the part, and what it came back as

S122 §9 listed eight items. Seven are done; the eighth (a *driven* capacity
row) needs a CPLD reflash and is not done, for the reason in §6.

| S122 §9 | item | outcome |
|---|---|---|
| 1 | the builds | rebuilt from this tree, **md5-identical to S122's** (§2) |
| 2 | deploy and boot | staged `/home/app/loopthd/s122`, gated boot CLEAN (§2) |
| 3 | the speaker slot reads exact zero with the mixer driven hard | **PROVED** (§3) |
| 4 | a click is audible on trigger | **PROVED, acoustically** (§4) |
| 5 | latency from the cell write to sound | **MEASURED** (§5) |
| 6 | AL1 through the new path, then `--al1-calibrate` | **PASS after recalibration** (§7) |
| 7 | a capacity row | **the node's own cost measured within one boot** (§6); the *driven* row is not taken |
| 8 | leave the unit as found | done and stated exactly (§10) |

---

## 2. The build, and the deploy

`DSP4_TEST_NODES=1` rebuilt from this tree with `build.sh`:

| | md5 | size |
|---|---|---|
| `chip1.ldr` | `7f226919a5d181410c3804d92678da19` | 433,508 B |
| `chip2.ldr` | `9e8a1a9edf19a90ce7ac3df1586c00f6` | 379,424 B |

Both are **byte-identical to the pair S122 reported without deploying**, which
is the reproducibility check. And `chip1.ldr` is **byte-identical to the pair
already staged at `/home/app/loopthd/s109`** — so the whole S122 change is one
file, chip 2, `6f11a1dd…` → `9e8a1a9e…`. Nothing reached past chip 2.

Staged to `/home/app/loopthd/s122` (a new directory; `s109` is on the dispatch's
never-touch list and was not modified). Booted with
`tools/pi/dsp4_boot_linked.sh`, whose sign-bit scorer is the gate (S89-1): three
gated boots over the session, **CLEAN on both lanes every time**, one retry
fired on the second. `BOOT_STAGE 7` on both chips, `CHIP_ID` 1 and 2,
`SPORT0_ERR_A 0`.

The build-cfg triple on the part is `0xCF45FF10 / 0xE3018E6F / 0xC47C0FA6` —
**the same triple `factory-test-v1` carries.** The graph moved; no build flag
did. That fact is the whole of finding S124-3.

---

## 3. S124-A — the speaker slot is exact zero with the mixer driven hard

The headline proof of S122, taken the way its §9 asked and then some.

**The drive.** `dsp4_driven_setup.py --mode load --off Comp,Gate,Limiter` on
both chips: every strip's assign to every bus open, every send at unity, every
dynamics node off its expensive branch so nothing quietly attenuates. Strip 20
injected with the self-test oscillator at **0 dBFS peak** (`RmsResult −3.01
dBFS`, i.e. a full-scale sine, THD+N −114.95 dB). `Main001Level001 = 1.0`,
`Main001Mute001 = 0`, `Mon001Level001 = Mon001Level002 = 1.0`,
`Mon001InputSel001 = 0`.

**The readings** — coherent captures, 256 contiguous samples each, through
`_scope_record` (not peeks; see `[[dsp4-peek-is-not-a-block]]`):

| node | non-zero words | first sample, Q4.28 |
|---|---|---|
| `_tx_out_slot_C2_MAIN_OUT_01` (MAIN, on the wire) | **256 / 256** | −0.17471 |
| `_blk_C2_MON` (the monitor bus) | **256 / 256** | −2.73944 |
| `_blk_C2_MON_DLY` (what used to feed the speaker) | **256 / 256** | −2.73945, peaking to −4.50 |
| `_blk_C2_HPT_01` (the haptic node) | **0 / 256** | +0.00000 |
| `_blk_C2_SPKR_OUT` | **0 / 256** | +0.00000 |
| **`_tx_out_slot_C2_SPKR_OUT`** (the word on the wire) | **0 / 256** | **+0.00000** |

The monitor chain is running at ±4.5 in Q4.28 — twenty-four strips summed at
unity, most of the way to the +8.0 rail. It is as loud as this graph can make
it. **The slot it used to drive is exact zero, every word.**

**The positive control, so a zero is a measurement and not a dead instrument.**
The same capture with the haptic node's test tone on: **981 / 1024 non-zero,
peak exactly 0.50000** (the level written), and the 43 exact zeros are the
sine's own zero crossings — one stored period of 1 kHz is exactly 48 samples at
48 kHz, so 1024 samples contain 21.3 periods and 43 samples land exactly on
zero. Turn the tone off and the slot goes back to **0 / 1024**.

`tools/pi/s89_slotcap.py`, captures in `data/cap__*.json`.

### The guard, on the tree that built the deployed image

`dsp_validate.py` on this tree's `dsp.csv`: **OK — no errors**. The same
validator on a scratch mutant that gives `C2_SPKR_OUT` its old `C2_MON_DLY`
source: **two named errors, exit 1** —

```
  [speaker slot] C2_SPKR_OUT is fed by C2_MON_DLY, a DELAY node. …only a
  HAPTIC node may reach a sink=SPKR output.
  [speaker slot] C2_MON reaches the speaker through C2_MON_DLY. The speaker
  source takes NO input…
```

so the guard is live in the generator that produced the bytes now on the part,
not only in the tree S122 wrote it in.

---

## 4. S124-B — a triggered click reaches the slot, and the air

### The trigger word is consumed, and `busy` is the read-back

Write `trig = 1`: the first read of `busy` comes back **1**, the trigger word
itself reads back **0** (the kernel consumed it, exactly as designed — the host
never clears it), and 200 ms later `busy` is **0** again.

### All three stored clicks, caught in the slot

The scope's own `arm()` takes tens of milliseconds and a click is 17 — by the
time `arm()` returns the click is over. So the scope's source and mode
registers are set up and verified **once**, and the only two writes between the
trigger and the start of the capture are the trigger and `ARM = 1`: **0.41 ms**
of host link, measured either side.

| sample | model (from `dsp.csv`) | measured Hz | non-zero length | stored length | peak |
|---|---|---|---|---|---|
| 1 | 2500 Hz, τ 2.5 ms | **2504** | 813 samples = 16.94 ms | 829 = 17.27 ms | 0.804 |
| 2 | 3000 Hz, τ 1.8 ms | **3008** | 580 samples = 12.08 ms | 597 = 12.44 ms | 0.781 |
| 3 | 1500 Hz, τ 3.0 ms | **1500** | 978 samples = 20.38 ms | 995 = 20.73 ms | 0.841 |

Each click plays to its end and the slot returns to exact zero. The captured
length is short of the stored length by the ~0.4 ms the capture takes to open
plus the raised-cosine fade's last samples, which round to zero in Q4.28 — i.e.
**the fade to exactly zero that S122 built is visible in the measurement**: the
amplifier is never handed a step.

The peaks read below the stored 0.94 for the same reason, and that turns out to
be a second clock — see §5.

### The MEMS microphone hears them

`_buf_C1_XIN_MEMS`, coherent capture, the panel's own microphone:

| state | RMS | peak |
|---|---|---|
| speaker silent | **−47.60 dBFS** | 0.00437 |
| clicks playing | **−38.63 dBFS** | 0.07119, at **2563 Hz** |
| silent again | −47.06 dBFS | 0.00462 |

**24 dB of peak over the room's floor, at the frequency of the click that was
triggered.** That is "a click is audible on trigger", judged by the part, with
nobody in the room. Repeated at the very end of the session with `d24-testui`
active and `matrix-app` stopped — the state the unit is being left in — and it
still reads −38.68 dBFS at 2555 Hz, so the codec survives the service switch
that `[[d24-cold-boot-codec-uninitialised]]` warns about.

---

## 5. S124-C — cell write to sound, measured

The number S122 §3.7 said nobody had.

### The host's own half

`link.write` of one parameter word, `perf_counter` either side, n = 60:

| | min | median | p95 | max |
|---|---|---|---|---|
| one SPI parameter write | 0.200 ms | **0.335 ms** | 0.343 | 0.345 |

### Trigger to the word on the transmit slot

**The click is its own clock.** Its envelope is `exp(−n/τ)` with τ known from
the generator, so the peak the capture opens on says how long the click had
already been running when the capture started. n = 20:

| | min | median | mean | sd | max |
|---|---|---|---|---|---|
| host `link.write` | 0.185 | 0.339 | 0.320 | 0.068 | 0.418 ms |
| trigger write → capture opens | 0.407 | 0.666 | 0.627 | 0.096 | 0.741 ms |
| click's age when the capture opened | 0.229 | 0.229 | 0.229 | **0.000** | 0.229 ms |
| **host write → the word on the slot** | 0.178 | **0.436** | 0.398 | 0.096 | **0.512 ms** |

The click's age at the capture is **identical to the sample on all twenty
runs** — the trigger and the arm are taken in the same block, so the click and
the capture start on the same block boundary every time. (The 0.229 ms itself
carries a systematic bias: half-cycle peaks are sampled at 19.2 samples a
period, so the fitted intercept is a few samples early. It is a constant, and
it cancels out of the run-to-run spread, which is what the table is for.)

So: **the DSP's own contribution is under half a millisecond and is dominated
by the host's SPI write**, exactly as S122's bound predicted and now with a
number under it.

### Host write to sound in the air

Same trigger, read on the MEMS lane, n = 6:

| run | onset after the capture opened | total, host write → MEMS |
|---|---|---|
| 0, 2, 3 | 46 samples = 0.96 ms | 1.33–1.34 ms |
| 1, 4, 5 | 62 samples = 1.29 ms | 1.66–1.68 ms |

**Median 1.67 ms, min 1.33, max 1.68.** The onset quantises to exactly 46 or
62 samples — a difference of **16 samples, which is `BLOCK`**. The jitter in a
touch-to-click is one audio block and nothing else.

That is the whole chain: host SPI write (0.34 ms) → kernel and TX slot (≈0.1 ms
more) → AK4619 DAC → TS482 → panel speaker → air → MEMS ADC → chip 1's block.
**A screen press is heard in about 1.7 ms.**

---

## 6. S124-D — what the haptic node costs chip 2, measured

S122 §3.4 counted the emitted instructions statically: **15 on an idle block,
about 265 while sounding.** Both are now measured on the part, as a
**within-boot** difference — which is the only instrument that can see them,
because the cross-boot spread on code that did not change at all is about 2,000
cycles a block.

Reading `_proc_cyc` on chip 2, budget 327,680 cycles/block at BLOCK = 16 and
983.04 MHz:

| state | median cycles/block | % of budget |
|---|---|---|
| idle (pooled over three separate readings) | 266,608 | 81.36 % |
| test tone sounding | 266,859 | 81.44 % |
| clicks sounding | 266,907 | 81.45 % |

and, **interleaved tone-off / tone-on, 40 paired readings**, so the ~300-cycle
drift between one reading block and the next cancels instead of swamping the
answer:

> **median +255 cycles/block** (IQR +206…+286, mean +235, sd 342)
> = **0.0778 % of budget**, against the static count of 265 = 0.0809 %.

**The static count is confirmed to about 4 %.** The idle cost is below anything
this instrument can resolve, which is also what S122 predicted.

### The driven capacity row is NOT taken, and why

S122 asked for a row against the **84.34 %** standing figure. That figure is
**driven**, and a driven row needs the `dsp4_logic_driveall` LOGIC bitstream
flashed and the shipping one flashed back afterwards — two CPLD writes on a
unit that has to be left exactly as found, with nobody at the bench. A failed
restore is the one failure tonight that would need a hand. **Not done, stated
rather than fudged**, and on the PW bench list (§9). The 81.36 % above is the
*silent, loaded* graph and is not comparable to 84.34 %.

---

## 7. S124-E — AL1 through the haptic path

### 🔴 S124-1 — S122 DELETED THE AL1 CALIBRATION TABLE, AND NO AL1 PRESS COULD HAVE WORKED

The first AL1 press on the new code came back **NO DATA, runner error**:

```
RUNNER ERROR: NameError("name 'AL1_CAL' is not defined")
```

`42d09d1b` removed the ~190 lines of route-write code AL1 no longer needs and
took three things out with them that it very much does need: the whole
**`AL1_CAL` window table**, **`AL1_CAL_KEYS_NUMERIC`**, and the helpers
**`pct_of_db()`** and **`_mems_row()`**. Every one of them is inside the
deleted hunk. The file imports and `--help`s perfectly; it fails the moment AL1
actually runs, which is why a desk-only dispatch could not see it.

All four are restored, with a comment at the table saying what happened. A
whole-file static pass for undefined names now comes back clean (only
`__file__`).

**The lesson is not "be careful with big deletions".** It is that a 434-line
diff to the one file that carries the factory verdicts went out with nothing
run against it, and the thing it broke was not the thing it changed.

### AL1 on the restored table: FAIL, exactly as S122 predicted

```
AL1  FAIL  CLIP base -46.9 tone -29.7 SNR 17.2 dB THD -25.5 dB 5.32%
```

The old level law predicts −35.8 dBFS at the −6 dBFS drive; the part read
−29.7. The new path is **6 dB louder at the microphone** — no strip fader, no
MAIN fader, no monitor fader between the oscillator and the slot any more — so
the speaker is driven harder and the acoustic THD is genuinely higher. "Stale
by construction", measured.

### `--al1-calibrate`: 15 runs, 3 levels, 5 reps, and the table rewritten

| drive | tone (mean) | spread | baseline | SNR | THD |
|---|---|---|---|---|---|
| −12.0 dBFS | −35.53 dBFS | **0.05 dB** | −47.15 | 11.62 dB | −32.05 dB = 2.50 % |
| −6.0 dBFS | −29.74 dBFS | **0.03 dB** | −46.77 | 17.03 dB | −25.50 dB = 5.31 % |
| −3.0 dBFS | −27.02 dBFS | **0.03 dB** | −46.52 | 19.50 dB | −22.31 dB = 7.67 % |

The **spread is 0.03–0.05 dB**, against S110's 0.52 dB through the old route.
Taking three faders and a strip out of the loop made the acoustic measurement
an order of magnitude more repeatable.

| `AL1_CAL` | old (v1 path) | new (haptic path) |
|---|---|---|
| `slope_db_per_db` | 1.029 | **0.948** |
| `intercept_dbfs` | −29.650 | **−24.130** |
| `snr_min_db` | 15.400 | **13.700** |
| `floor_max_dbfs` | −48.300 | **−40.300** |
| `thd_abs_db` | −28.500 | **−22.500** |
| `thdn_abs_db` | −16.700 | **3.000** ← see S124-2 |
| `thdn_margin_db` | 10.800 | **22.800** ← see S124-2 |
| `level_tol_db`, `level_hi_tol_db`, `thd_margin_db` | unchanged | unchanged |

### AL1 on the new table

```
AL1  PASS  base -47.1 tone -29.8 SNR 17.3 dB THD -25.4 dB 5.38%
```

tone −29.75 dBFS against a predicted −29.82 — **0.07 dB** — and bandpass THD
−25.38 dB under the −22.50 ceiling. It passed again inside the full automated
set twenty minutes later (−29.8, 5.28 %).

### 🟡 S124-2 — the node's THD+N reading is now meaningless, and the calibration fitted a limit to it

Every one of the 15 calibration runs and every AL1 press since reads
`ThdResult 0.00 dB = 100.000 %` from the on-part TEST_MEAS engine, with
`NoiseResult` equal to `RmsResult`. The node's fitter has no fundamental to
subtract: its reference came from the chip-1 oscillator's own frequency word,
and the haptic stimulus does not write one. The verdict is unaffected — since
S115 it is on **bandpass THD**, computed host-side off the coherent capture,
and that reads a healthy −25.4 dB — but:

* the informational "THD+N (node)" line in every AL1 evidence block is now
  junk, and
* `--al1-calibrate` dutifully **fitted a limit to the junk**: `thdn_abs_db`
  came out at **+3.0 dB = 187 %**, a ceiling nothing can ever exceed.

Nothing scores on it today, so this is 🟡 and not 🔴. The fix is one of: give
the haptic stimulus a way to tell TEST_MEAS its frequency, or drop the node
THD+N line from AL1 and stop carrying two numbers where one is real. Left for
PW/the hub to rule, not guessed at here.

---

## 8. The factory image: **yes, S122 bumps it** — `factory-test-v2`

The dispatch asked this directly. The answer is yes, and the bump is deployed:

| | v1 | **v2** |
|---|---|---|
| name | `factory-test-v1` | **`factory-test-v2`** |
| pair dir | `/home/app/loopthd/s109` | **`/home/app/loopthd/s122`** |
| `chip1.ldr` | `7f226919a5d181410c3804d92678da19` | **unchanged** |
| `chip2.ldr` | `6f11a1ddc6efd45ec30f536cef295292` | **`9e8a1a9edf19a90ce7ac3df1586c00f6`** |
| build-cfg triple | `0xCF45FF10 / 0xE3018E6F / 0xC47C0FA6` | **identical** |

Recorded in `tools/pi/d24_selftest.py`, `tools/pi/d24_patch.py`,
`tools/pi/d24_runall.py` and `MW/D24/DSP/accept/manifest.json` (v1 kept there
under `supersedes`), and `/home/app/selftest/pair.conf` now names `s122`.

### 🔴 S124-3 — the image assertion could not tell v1 from v2, and now can

`_check_factory_image()` is the gate that turns "a substituted pair answered"
into NO DATA rather than a silent wrong verdict. It compared the **build-cfg
triple and nothing else** — and v1 and v2 carry the **identical triple**,
because S122 moved the graph and moved no build flag. So the gate would have
accepted either pair, on either day, silently. The `.ldr` md5s have been in the
record since S116 and in the accept manifest, and **nothing read them.**

They are read now, off the staged pair, and the check fires three ways:

| staged pair | verdict |
|---|---|
| v2 (`9e8a1a9e…`) | **ACCEPTED** |
| v1 (`6f11a1dd…`), identical triple | **refused** — "wrong image loaded: chip2.ldr … The build-cfg triple matched — two graphs can share one set of flags, which is why the md5 is checked." |
| no `.ldr` in the stage directory at all | **refused** |

Proved live on the part for the accept case (every DSP-touching press in the
full set ran without a "wrong image loaded"), and against all three inputs as a
direct call.

---

## 9. The deploy gate: does the factory screen and RUN ALL still pass on it?

The dispatch's condition for deploying at all. Run after the bump:

**The automated set, `--section A,B,C`, on v2:**

```
rows:  35 PASS / 0 FAIL / 16 NO DATA  (51 rows)
items: 22 PASS / 0 FAIL / 12 NO DATA  (34 of 36 workbook rows covered)
```

**No FAILs.** `AL1 PASS`. Every NO DATA is one of the standing prerequisite
gaps (AS-CPLD wants the duplex PCM overlay; AS-PWR wants a power-MCU reader;
ML-B0/ML2 want H1S1 cells that do not exist; DC1/DC2-CS6/7/8 and NW4 as
before), each already carrying its written reason. None is new.

**The patch station's dry run** walks all 59 patches of the quick list with no
unit and reaches every outcome: 59 steps, 151 readings, **53.5 s machine**,
worst block 1.93 s a step against 5.8 s of hand — the same figures S123
reported, unmoved by the bump.

**The operator strings**: 789 dumped, **clean — no Matrix-internal vocabulary**.

**The screen itself** was not re-walked. S123 photographed all 18 states an
hour earlier; nothing in this session touches `d24_live.py` or the app, and the
only change to `d24_patch.py` is one constant (the pair directory) and its
docstring. Driving the glass through `--screens` at night risks leaving it on a
state other than ARMED, which the dispatch forbids, for no information.

**Verdict: the condition is met and the deploy stands.**

### 🟡 S124-4 — AS-DAC now reads the one slot that must be zero

`AS-DAC` ("DAC AK4458 ×2" / link `dig-analog-dac`) takes its capture from
`_tx_out_slot_C2_SPKR_OUT`. Since S122 that slot is the haptic node's and is
**zero by design**, so the test is now structurally NO DATA and its stated
reason ("no stimulus on this image") is wrong — the image has TEST_OSC, and the
evidence block says so two lines above. It was NO DATA before S122 as well, so
this is **not a regression**, but the reason is now misleading and the
instrument is pointed at the wrong converter: the AK4458s are the *analog*
board's DACs, and the speaker slot is the AK4619 codec. Reported, not fixed —
repointing a factory verdict is PW's call, and the fix is the same shape as
AL1's (drive the aux or main output with TEST_OSC and read *that* slot).

### 🟡 S124-5 — NW3 can crash the runner, and the runner now says where

One `--section A,B,C` press recorded `NW3 NO DATA, runner error,
TypeError('not enough arguments for format string')` and nothing else. The
`t_nw3` function is **byte-identical to its pre-S122 version** (checked by AST
comparison against `4a1f4933`), so this is pre-existing and nothing to do with
the haptic path; it is also data-dependent — a later `--only NW3` reached a
real verdict (FAIL, 1 % loss to both targets, which is the ambient loss S116
already flagged). A one-line repr is not enough to find such a thing, so the
runner-error handler now records the **full traceback** alongside the repr.
That change immediately earned itself: the very next runner error came back
with its stack, and it was the rails guard refusing a boot with AN_EN high —
which is the guard working, and would otherwise have been another blind
`RuntimeError(...)`.

---

## 10. The disk (dispatch §2)

Target ≥ 1.5 GB free, nothing lost. **138 MB → 1.76 GB.**

| | KB | MB |
|---|---|---|
| free before | 141,276 | 138 |
| free after | **1,840,208** | **1,797** |
| recovered | 1,698,932 | **1,660** |

### The ledger

Everything was **copied to this machine first**, at
`~/d24-unit-archive/2026-09-26/`, with a per-file `md5sum` manifest taken **on
the unit** and checked against the extracted copy here. **28 archives, 6,953 files, 0 md5 mismatches,
0 missing** — re-verified in one pass at the end of the session. Only then was anything removed.

| what | KB freed | archive | why it is safe |
|---|---|---|---|
| `.net/app/` — **10 stale .NET bundle-extraction caches** | **1,021,604** | `net-app-*.tar` | `/home/app/app` is a single-file .NET app; each start extracts to `~/.net/app/<bundle-id>/`. The id is per app BUILD, so every app deploy since 09-24 left a 102 MB directory behind. The live one (`6Ik6eMqCKDm3`, read off `/proc/<pid>/maps` of the running `d24-testui`, re-checked immediately before deleting) is kept; the other ten belong to app binaries that no longer exist. A cache: any of them regenerates on the next start of the matching binary. |
| `dspcap/` | 194,388 | `dspcap.tar` | capture/scratch from finished dispatches |
| `app.bak-s107-pre`, `app.bak-s112-pre` | 226,368 | 2 tars | app backups older than the newest two (`s123`, `s117` kept) |
| `s63/` | 117,628 | `s63.tar` | finished-dispatch stage + 114 MB of `data/` |
| `logic-flash.log` | 68,556 | `logic-flash.log.tar` | **archived then truncated to 0**, not deleted — `logic_flash.sh:216` appends to it |
| `_temp/` | 57,664 | `_temp.tar` | MH1/H1S3/H1S4 scratch build trees |
| `cap_*` (12 directories) | 14,668 | 12 tars | named capture scratch from S12/S16/S17/S82 and the TX-early arms |
| **total** | **1,700,876** | | matches the 1,698,932 KB the filesystem gave back, to within the metadata |

### The grep evidence

Every path was grepped, before removal, across everything the dispatch names as
untouchable — `selftest/`, `dspboot/`, `loopthd/`, `software/`, `firmware/`,
`skins/`, `config/` and every `/home/app/*.sh` — **and through the app binary
itself** (`grep -ac` on all 115 MB of `/home/app/app`).

| pattern | hits in the deployed tools | hits in the app binary |
|---|---|---|
| `dspcap` | 2, both defaults in **retired** run scripts: `s20restore_run.sh:5` (`SCRATCH`), `s33flip_run.sh:14` (`STAGE`) | **0** |
| `/home/app/cap_` | 0 (the `cap_` hits in `d24_selftest.py` are variable names — `cap_rms_dbfs`, `cap_quarters`) | **0** |
| `/home/app/s63` | **0** | **0** |
| `/home/app/_temp` | 0 (the `_temp` hits are `measure_temp` and catalog prose) | **0** |
| `logic-flash.log` | 1: `logic_flash.sh:216 LOG=./logic-flash.log` — **appends**, hence truncate not delete | **0** |
| `app.bak-s107` / `app.bak-s112` | **0** | **0** |
| `.net/app` | 0 (the two `.net` hits are `args.nets`) | **0** |

### What was deliberately NOT removed

* **`fwbuild/`** (118 MB). Its two biggest items are `H1S3/` (21.9 MB) and
  `H1S4/` (17.9 MB), which are MCU **build trees**, not artefacts; the `.hex`
  and `.shex` images are 100 KB each. The target was already met without them,
  and deleting build trees to save 40 MB is a bad trade.
* **the ~100 small `sNN`/`s89*` stage directories** (~280 MB at ~2.8 MB each).
  Cheap to archive but each needs its own grep, and the target was met.
* Anything in the never-touch list: `selftest/`, `dspboot/`,
  `loopthd/` (including `s109`), `firmware/`, `software/`, the current app and
  `app.bak-s123-pre`.

After the clean-up the running app never restarted (same PID 21243 before and
after), `/home/app/app` still md5s `7533ce45…`, and the factory screen is still
armed.

---

## 11. The PW bench list — what still needs a hand or an ear

Short, in plain words, with what PW should see or hear and how long it takes.

1. **Listen to the clicks. (2 minutes.)** From a terminal on the unit:
   `cd /home/app/loopthd/s122 && python3 s89_set.py . c2@2176=1 c2@2175=1`
   plays click 1 (2500 Hz); `c2@2176=2` then `c2@2175=1` plays click 2
   (3000 Hz), `=3` the spare (1500 Hz). **PW should hear three distinct short
   ticks from the panel speaker, no thump before or after.** The part says all
   three play at the right frequency, the right length and end at exactly zero;
   what nobody can judge without ears is **which one should be the press and
   which the release** — that is PW's ruling and the proposal deliberately does
   not land it (`proposals/CONTRACT-PROPOSAL-S122.md`).
2. **Is 1.7 ms fast enough? (1 minute, with a finger.)** Measured end to end, a
   cell write is audible in 1.67 ms with one block of jitter. Nobody has
   pressed a button and felt it. PW to say whether the touch event reaches the
   cell write quickly enough for the whole thing to feel instant — the DSP's
   half is now known and is not the problem.
3. **The click level.** Stored at PW's own audition peak of 0.94 and played at
   `level = 1.0`. Whether that is the right loudness in a room is an ear
   judgement. One cell (`c2@2177`) moves it.
4. **The driven capacity row (needs a CPLD reflash, 15 minutes).**
   `./loadlogic.sh driveall`, then `ARM=s122 PRODUCT=d24 BUILD=0
   STAGE=/home/app/loopthd/s122 ./capacity.sh --driven`, then
   `./loadlogic.sh shipping`. Not done tonight because a failed restore is the
   one failure that would have needed a hand.
5. **A full factory patch pass with a lead** (S123's standing item, unchanged):
   the seven gain steps per input have still never been measured through a real
   preamp, and the USB-keyboard ENTER arm is still unwitnessed.
6. **Two rulings wanted** — S124-2 (AL1's node THD+N line is now meaningless:
   fix the fitter or drop the line) and S124-4 (AS-DAC is pointed at the one
   slot that must be zero).

---

## 12. Deployed, and the unit as left

### Deployed this session (every md5 re-read off the unit after the copy)

| file | md5 | rollback |
|---|---|---|
| `/home/app/loopthd/s122/chip1.ldr` | `7f226919a5d181410c3804d92678da19` | `s109` pair untouched |
| `/home/app/loopthd/s122/chip2.ldr` | `9e8a1a9edf19a90ce7ac3df1586c00f6` | `s109` pair untouched |
| `/home/app/selftest/d24_selftest.py` | `8b2c14e244a0886f0389e80123f0e380` | `.bak-s124-pre` = `bfcafe0f97866963de2bf446bd3734c3` |
| `/home/app/selftest/d24_patch.py` | `5bfe6dd9428bdc9242355efdf754e89a` | `.bak-s124-pre` = `d5e5c3c6db6f17a132a0656642809538` |
| `/home/app/selftest/d24_runall.py` | `4e59aea8f3ddd37abf89388dd37aa209` | `.bak-s124-pre` = `fc5f3a68b8e451672dbab639b4336c83` |
| `/home/app/selftest/pair.conf` | `/home/app/loopthd/s122` | `.bak-s124-pre` = `/home/app/loopthd/s109` |

All three tool md5s equal the repo's. Unchanged and not redeployed:
`d24_live.py` `4a5bb788…`, `d24_chain.py` `22db7dd3…`, the app
`7533ce450967890cac9a7b417eb0c109`, the catalog, the CPLD, H1S1.

**Rolling back is four `cp` of the `.bak-s124-pre` files** plus
`echo /home/app/loopthd/s109 > /home/app/selftest/pair.conf`; the v1 pair is
still staged and untouched.

### The unit, stated exactly

* `AN_EN` (GPIO26) **lo** — rails down. Raised four times by the runner's own
  rails-once discipline and lowered by its handback each time.
* `CS_M` (GPIO27) **op / hi**, driven.
* 595 mic-pre chain **SAFE**, `24 × 0x01 + 0x00`, **`VERIFIED 200/200`**.
* DSP pair **booted at `/home/app/loopthd/s122`**, gated CLEAN on both lanes,
  `BOOT_STAGE 7` both chips.
* The haptic block at rest, read back: `trig 0`, `sample 1`, `level 1.0`,
  `test_on 0`, `test_level 0.0`, `busy 0`.
* **`_tx_out_slot_C2_SPKR_OUT` re-read as the last measurement of the session:
  0 of 256 words non-zero.** The speaker is digitally silent.
* Oscillator off; `Mon001Level001/002 = 0.0`.
* `matrix-app` **inactive**, `d24-testui` **active**.
* The factory screen **ARMED** — `factory.json` intact, the 59-patch quick list
  in `/home/app/selftest/quick/`, no live status file, no `runall/prompt.json`,
  no run live. **The one thing PW presses is still START.**
* **1.76 GB free.**

### Contract

`defs.lock` **unmoved** at `defs-v2026.09.24.2`. No def CSV, matrix, slot map,
wire table or generated DSP artefact changed; `dsp.csv` is S122's, untouched.
**No contract bump owed.** The accept manifest moves only its
`factory_test_image` record.

---

## 13. Findings

* **🔴 S124-1** — S122's commit deleted `AL1_CAL`, `AL1_CAL_KEYS_NUMERIC`,
  `pct_of_db()` and `_mems_row()` along with the route-write code. **No AL1
  press could have succeeded on it**; the file imports and `--help`s fine and
  raises `NameError` only when the test runs. Restored, with the reason at the
  table. §7.
* **🔴 S124-3** — `_check_factory_image()` compared the build-cfg triple only,
  and `factory-test-v1` and `-v2` carry the **identical triple**, so the gate
  that exists to catch a substituted pair could not catch this one. It now also
  checks the staged `.ldr` md5s, which have been in the record since S116 and
  were read by nothing. Fires three ways. §8.
* **🟡 S124-2** — AL1's on-part THD+N reads `0.00 dB = 100 %` on every run
  through the haptic path (the node's fitter has no stimulus frequency), and
  `--al1-calibrate` fitted a `thdn_abs_db` of **+3.0 dB**, a limit nothing can
  exceed. The verdict is on bandpass THD and is unaffected. Ruling wanted. §7.
* **🟡 S124-4** — `AS-DAC` captures the speaker slot, which since S122 is zero
  by design; its NO DATA reason is now wrong and the instrument is pointed at
  the codec rather than at the AK4458s it names. Pre-existing NO DATA, not a
  regression. §9.
* **🟡 S124-5** — `NW3` can crash the runner with a `TypeError` on some data
  shapes; `t_nw3` is byte-identical to its pre-S122 self, so it is pre-existing
  and intermittent. Runner errors now record the **full traceback**. §9.
* **🟢 S124-6** — the disk: 138 MB → **1.76 GB**, nothing lost, everything
  archived and md5-checked both ends. The single biggest item was one nobody
  had looked at: **1 GB of stale .NET single-file bundle extractions**, one per
  app build since 09-24, in `~/.net/app/`. Every future app deploy leaves
  another 102 MB there. §10.

---

## 14. Files

* this report — `MW/D24/DSP/s124/s122-on-the-part.md`
* the bench instruments written for it — `MW/D24/DSP/s124/s124_{haptic,click,lat,cap,cap2}.py`
* the readings — `MW/D24/DSP/s124/data/*.json` (captures, latency runs, cycle pairs)
* the self-test's own raw reads — `MW/D24/DSP/s90/logs/2026-09-26T19*`
* the unit archive — `~/d24-unit-archive/2026-09-26/` (tars, manifests, extracted tree, `MANIFEST.md`) — **on this machine, not in the repo**
