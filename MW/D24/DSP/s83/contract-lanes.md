provenance: AI-drafted 2026-09-20 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S83 — the three answers landed, the latency contract re-taken, and the mic lanes named as dark

**Session:** S83, 2026-09-20 afternoon. **Dispatch:** hub answers to S82's three
questions; the mic ADC lanes; `latency.sh`'s boot and the 82-sample row; the
talkback T1/T3 re-take.

## 0. The one-line outcome

| gate | result |
|---|---|
| 1 — the three answers | 🟢 landed in `numeric-spec.md`, `limits.csv`, the accept manifest and the proposal. **`FADER_PAN` numeric closes on the part: `BIT_EXACT`.** **`GATE` closes too, for the first time — it had no verdict at all before.** Conformance re-run: **PASS**, 22/12, no new failures. The COMPRESSOR witness was NOT re-measured and the reason is now a reading, not a guess. |
| 2 — the mic ADC lanes | 🟡 **the slot-map hypothesis is DISPROVEN at the desk and the lanes are measured DARK at the bench.** All 32 `_buf_C1_IN_*` static zero with the rails UP and the 595 chain unmuted at gain 63 (VERIFIED 200/200), both instrument controls satisfied, while all four codec lanes move. No EIN row is takeable. Probe list in §3.4. |
| 3 — latency | 🟢 **the boot is fixed and the row is taken: 80 samples through the DSP at block 16**, 100.0 % coherent on 20 of 20 reps against a LOGIC-only reference re-taken in the same session. The 82-sample contract number does not move. |
| 4 — talkback T1/T3 | 🔴 **stopped as the dispatch instructs: the AUX 1 → J1 loop is not carrying the tone.** The lane sits at its own noise floor across a 20 dB drive change. |
| 5 — scoreboard, report | 🟢 `fit-table.csv` regenerates byte-identical; the witness values are beside the bounds in `limits.csv` and the manifest. |

---

## 1. Gate 1 — the three answers, and what the part said back

### 1.1 Where each ruling landed

| ruling | landed in |
|---|---|
| **Q1** the COMPRESSOR term is `DSP4_DYN_LUT`'s **design bound, ≤ 0.0950 dB**; the famverify figure is a **witness** | `tools/accept/limits.csv` (`comp_numeric_max_db` 0.00518 → **0.0950**, and a new `comp_numeric_witness_db` 0.02509 carrying the measured value and its instability); `shared/numeric-spec.md` §deviations; `proposals/CONTRACT-PROPOSAL-S82.md` §2.0; `MW/D24/DSP/accept/manifest.json`, which now separates `numeric_bounds_db` from `numeric_witnesses_db` |
| **Q2** below `GateThr = −60 dB` the bound **IS one Q4.28 LSB**, 0.00035 dB, stated as the LSB | `limits.csv` `gate_linthr_lowthr_max_db` source column rewritten to say so; `numeric-spec.md`; the proposal's §2 table |
| **Q3** the wire's own grid is the contract; the **model** quantises | `fixed_ref.fdr_pan_legs` / `fdr_pan_grid` (new, delegating to `tools/dsp/pan_table.py`); `dsp4_node_verify._fdr_setup` drives table position 40; `numeric-spec.md`'s FADER_PAN clause |

**A bound and a witness are now different things in the manifest.** They were one
dictionary, and that is exactly how `comp_numeric_max_db` came to hold S20's
measurement as though it were a limit. `gen_accept_fixtures.py` now reads any
`*_witness_db` key into its own field.

### 1.2 FADER_PAN closes, and the part was right all along

`Pan` is an **index**. Under `DSP4_PAN_TABLE` — the shipping default
(`src/dsp_block.h:148-151`) — the kernel computes `fix(pan × 126.0)` in
float32, clamps to `0..126` and reads the resident table
(`src/chip1/pan_law.asm`). So the cell has **127 positions**, `fix` rounds to
nearest with ties to even, and a host float between two positions lands on one.

S82 drove `Pan = 0.317`, which is 0.058 of a step off position 40. The part
answered position 40's legs. `fixed_ref.fdr_coeffs` — which models the *pre-R5*
arithmetic — answered the unquantised value, and the bar called that a mismatch:

| leg | the part | the old model | `pan_table.read_legs(0, 40, 0)` |
|---|---|---|---|
| LEFT | `183217856` = 86/126 | `183341408` | **`183217856`** |
| RIGHT | `85217608` = 40/126 | `85094040` | **`85217608`** |

The new model reproduces the part **to the word** at the desk, before any bench
run, and the bench then confirmed it:

```
cvt fdr level coefficient                                    99321120 /     99321120  ok
cvt fdr LEFT pan leg (table index 40; D42 open)             183217856 /    183217856  ok
cvt fdr RIGHT pan leg (table index 40)                       85217608 /     85217608  ok
step     amp 0x02741F14  model 64 of 64 bit-exact   negative control differs in 64 of 64 (predicted 64)
impulse  amp 0x02741F14  model 64 of 64 bit-exact   negative control differs in  1 of 64 (predicted  1)
```

`FADER_PAN numeric: FAILED → BIT_EXACT`. **Nothing about the part changed.**

The law itself is not duplicated anywhere: `fixed_ref` imports `pan_table`,
which is "the LAW ITSELF — the single place the numbers come from" by its own
header, and the generator emits the resident tables from the same functions.

### 1.3 S83-1 — why four of five famverify runs could not read a node's state

**It was never the link, and it was never a "dead scalar".** `read_params`
**votes**: it returns a word only after seeing the same value twice in eight
asks. That is right for a PARAMETER — every one of COMPRESSOR's six converted
words read first time, including the two that are genuinely zero, so the zero
sentinel was armed and working. It is wrong for **STATE**.
`_comp_envelope_` and `_gate_envelope_` are written on **every sample**; an
eight-ask vote over a word the part is still moving can only agree by accident.
It is the same defect `dsp4_scope.rd_counter` was written for.

And the state read happens immediately after a STEP capture, i.e. at the moment
the envelope is furthest from rest. COMPRESSOR got **one** attempt by
construction; GATE broke out of its own three-attempt rest-watcher on
`st is None` before ever reaching it. Both died on the first try, every time.

The fix waits for the state and **says how long it took**, the rule the gate's
rest-watcher has followed since S21-5:

```
state settled 0.5 s after the capture (it was still moving when the capture ended)
state at rest: [523]
```

**The consequence is a verdict that did not exist before.** `GATE` was
`NO_STIMULUS` in every S82 run; it is now:

```
GATE  cvt gate range floor / threshold (LINTHR) / attack alpha   all ok
      phase profile 0:61 … 15:64   (scoring phase 15 = end of block)
      impulse amp 0x0D3A17B5  model 64 of 64 bit-exact
                              negative control differs in 2 of 64 (predicted 2)
GATE  numeric BIT_EXACT
```

That is the **signed** `DSP4_GATE_LINTHR` arm scoring bit-exact against the
linear-threshold model on the part, which no session had obtained.

**A second reporting defect was fixed with it.** `run_node` returns `(0, 0, 0)`
both when a stimulus separated nothing and when it never ran one, and
`numeric_phase` scored both as `NO_STIMULUS` — so "the bar could not read the
node" was recorded as "no stimulus moved it". There is now a `NO_VERDICT`
verdict with a `reason`.

### 1.4 The COMPRESSOR witness was NOT re-measured, and that is now a reading

With the state readable, COMPRESSOR reaches the next stage and stops there:

```
state at rest: [523]
state before this capture: [468] (at rest it read [523])
state before this capture: [511] (at rest it read [523])
step amp 0x0D3A17B5: repeat capture DIFFERS in 54 of 64 words — not at rest,
                     trying another amplitude; state before them [468] then [511]
… [548]/[508] … [538]/[485] …
COMPRESSOR numeric NO_VERDICT
  reason: the node does not arrive at the same state twice, so no repeat can be the noise floor
```

**The envelope never returns to the same word.** Six arrivals at rest across one
run read 468, 511, 548, 508, 538, 485; GATE's read 91, 220, 135, 90, 152, 153.
The bar requires two runs of the same stimulus from the same rest to be
identical — correctly — and the second run has never started from the same
place. For GATE the envelope LSB is a don't-care (the ladder is driven by the
target and the range floor), which is why GATE passes and COMPRESSOR does not.

An intermediate version of the fix **demanded** equality with the rest state.
It refused every capture and took GATE's verdict with it; that was measured and
reverted the same session. What is required is what the comparison actually
needs, and what is *reported* is the pair of states, so the next session reads a
number instead of inferring a cause.

**So the witness stands at S82's 0.02509 dB**, recorded as such, inside the
0.0950 dB design bound the hub ruled. Nothing is outside a contract term.

### 1.5 The conformance harness, re-run

`NEGCTL=1 TAG=s83 ./conform.sh`, both chips, full sweep:

```
conform_s83_c1.json: chip 1 all 4984/4984 addresses, healthy=True
conform_s83_c2.json: chip 2 all 2176/2176 addresses, healthy=True
declared-unit checks: 22 pass, 12 fail
negative control wrong-unit: FAILED as required (4 of 4)
VERDICT: PASS
```

Identical to S82's baseline. The twelve are all the **D41 ms-vs-samples class**
and nothing else: `ChanCompAtt` ×3, `ChanCompRel` ×3, `ChanGateAtt` ×3,
`ChanGateRel` ×3 — every one `want 0x000xxxxx got 0xFFFFFFFF` or the 0.1/0.5 ms
end of the same law. No new failure, none dropped.

---

## 2. S83-2 — `latency.sh`'s boot, root-caused and fixed, and the class behind it

### 2.1 The cause, reproduced by hand before anything was changed

`dsp4_config.py` reads the input patch from a file beside **itself** and
`sys.exit`s at **import** when it is not there (`dsp4_config.py:96-100`). A
staged arm links `/home/app/dspboot/*.py` into its stage directory, so the tool
is a symlink but `__file__` is the **link** — the lookup lands in `$STAGE` and
finds nothing. `latency_run.sh` sent the config tool's whole output to
`/dev/null`.

Reproduced on the bench, in S82's own stage directory, before any edit:

```
$ cd /home/app/cap_s82lat && python3 dsp4_config.py --product d24 --chip 1
ERROR: no input_patch.json for d24 (staged next to dsp4_config.py, or at
MW/D24/DSP/input_patch.json in the repo tree) -- run
`tools/dsp/gen_input_patch.py --product d24`
```

So the chips booted and were **never configured**: both sat at BOOT_STAGE 5 on
all four of S82's boots, and the 0.0 % coherent fraction the bar reported was a
correct reading of an unconfigured part. `s82.sh` links the file explicitly,
which is the whole of why the same pair reached stage 7 under it.

### 2.2 It is a class, and it was proved to be one within the hour

The first S83 famverify run, staged to a fresh directory, died the same way —
`chip 1 not ready after 8 attempts: BOOT_STAGE below 6` — and **wrote a full
27-family table of dashes and exited 0**. S82's famverify only worked because
its `STAGE` defaulted to `~/dspboot`, which happens to hold the file.

**46 occurrences of the staging block in 44 scripts** carried the same gap.
All are fixed at the source, and `latency.sh`'s link is deliberately **outside**
its `BUILD=1` guard, because `BUILD=0 STAGE=…` — the documented way to
re-measure a staged pair — is exactly the arm that skipped the staging block.

Two bars that reported confidently off an unbooted part now refuse:

* `latency_run.sh` retries the whole boot, checks **MAGIC before it believes
  BOOT_STAGE**, prints the config tool's error instead of discarding it, and
  exits non-zero with *"LATENCY: NO MEASUREMENT … Fix the boot, not the capture
  path."*
* `dsp4_family_verify.main` returns 4 when any chip was not ready.

### 2.3 The row

`maincap` flashed and identified on the part (`design_id 32'heb00a4e8
cfg_bits 16'h0004 pi_maincap`), the **signed pair** (`e3e25a79` / `41a6b913`)
booted from `/home/app/ship_s82`:

```
boot: chip1 stage=7 chip2 stage=7
rep  0 … rep 19:  coherent 100.0%  runner-up 0.0%  peak width 3
offset  min 14510  median 14515  max 14529  spread 19
```

and the LOGIC-only reference **re-taken in the same session** on `pisel`
(`design_id 32'h56926e3e cfg_bits 16'h0002 pi_selftest`):

```
offset  min 14427  median 14435  max 14436  spread 9
coherent fraction  min 100.0%  max 100.0%
```

| | offset (samples) | coherent |
|---|---|---|
| through-DSP, signed pair, block 16 | 14515 (14510 … 14529) | 100.0 % on 20/20 |
| LOGIC-only reference, same session | 14435 (14427 … 14436) | 100.0 % on 20/20 |
| **through-DSP latency** | **80** | |

**THE 82-SAMPLE CONTRACT NUMBER DOES NOT MOVE.** 80 is the difference of the
two medians; the through-DSP arm alone spans 19 samples, so ±10 around its own
median, and 82 is inside that. S20 measured 80/83 on the two chips against a
reference of 14,433 — this session's reference reproduces that to **2 samples**.
The reading is *consistent with 82* and does not replace it; a session that
wants to move the contract number needs an arm whose spread is smaller than the
change it is claiming.

---

## 3. Gate 2 — the mic ADC lanes

### 3.1 The slot-map hypothesis is disproven, at the desk

The dispatch's first step was to diff the slot map the two bitstreams generate
against S58's input patch. **They do not differ where it matters.**
`git diff a4ee3d1f HEAD -- shared/dsp4-logic/slot-map.csv` and the same on
`tdm-lines.csv` return **nothing** for any `A_I0` / `A_I1` / `A_I2` row: those
rows were added once at `8439b189` (2026-07-31) and never touched. The overall
slot-map hash moved (codec part number, matrix-bus and CM4 rows) but the
AK5558 portion is byte-identical.

So MIC 5 — `defs/products/d24/inputs.csv`: J25 → U39 (AD 1) → AIN 8 → slot 7 —
lands in **`_buf_C1_IN_16` on both bitstreams, zero lanes of movement**. There
is no live lane for S58's patch to be missing. The RTL agrees: `net_sel` is
`4'b1000` in both branches (`dsp4_logic_top.v:312`), so `i_dspa[0..2]` take
`ad[0..2]` — the converters — and only lane 3 takes the network.

### 3.2 The bench half assumed nothing about which lane is which

One tone was driven into the loop and **every** lane was read, tone off then on,
by a new probe (`MW/D24/DSP/s83/tools/s83_lanescan.py`) carrying the two
controls `dsp4_inscan.py` established: FRAME_COUNT must move, and
`_rx_slot_C1_IN_01` — a symbol nothing writes under `DSP4_BLOCK_KERNELS` — must
not. Both satisfied on every pass.

The route was proved **digitally first**, because the donor strip is part of the
instrument and is not transparent out of `dsp4_config.py` (S70-2/3):

```
oscillator ceiling -14.89 dBFS (derived, S79)
AUX 1 bus carries the tone: -43.017 dBFS at oscillator -40.0    (expected -43.01)
```

### 3.3 The reading, with the rails up and the preamps unmuted at gain 63

The first pass ran with the 595 SAFE image on the chain, i.e. every preamp
shunted — a confound. It was re-taken with `0xFC` (unmuted, gain 63, phantom
off) **VERIFIED 200/200**, AN_EN read back `hi`:

```
FRAME_COUNT +38670, dead-symbol distinct 1          (both controls ok)
MOVING       4: XIN_CODEC_01 (16 distinct, -68.6 dBFS)
                XIN_CODEC_02 (16 distinct, -69.5 dBFS)
                XIN_CODEC_03 (16 distinct, -91.6 dBFS)
                XIN_CODEC_04 (14 distinct, -101.8 dBFS)
STATIC ZERO 42: IN_01 … IN_32, XIN_PI_L, XIN_PI_R, XIN_SNK_01 … 08
STATIC other 1: XIN_MEMS (ffffffff)
```

And with the tone on at the capped −14.89 dBFS, **not one `_buf_C1_IN_*` lane
moves by a thousandth of a dB**: 32 of 32 read exact digital zero, tone on and
tone off alike, while the four codec lanes carry their own dithered noise floor
in the same pass.

**So: the AK5558s are not converting, the AK4619 is, and the difference is not
the slot map and not the patch.** Nothing here is an EIN row — S54's −127.2 dBu
cannot be met or missed by a lane that produces no samples.

### 3.4 What is readable, and the probe list

The dispatch asked for the CPLD's AD0–AD2 frame counters. **They do not
exist.** The CPLD's witness counter (`cdc_ones`, `cdc_tog`, `cdc_frames`,
`dsp4_logic_top.v:185-230`) counts ones and toggles on **`cdc_o` only** — the
codec lane. There is no equivalent on `ad[0..2]`, so the CPLD cannot say
whether those pins toggle at all. The 595 chain **is** readable and answers
perfectly: two 200-bit passes, `0xFC` then `0x01`, both VERIFIED 200/200.

The probe list, most informative first:

1. **Add a lane witness for `ad[0..2]` to the LOGIC.** The `cdc_*` counter
   already exists for one lane; replicating it for three costs a handful of LEs
   and settles "is anything arriving at the CPLD pin" without a scope. This is
   the cheapest next measurement by a wide margin and it needs no bench visit.
2. **`conv_bck` (U3 pin 142) and `conv_fs` (pin 141) at the AK5558s.** The CPLD
   drives them (`dsp4_logic_top.v:446-447`, outside the one `ifdef`) and S41's
   manifest recorded 12.288 MHz / 48 kHz at U3. Nothing on this bench can read
   them back; a scope at R111/R112 and at the ADC FPC J41 can.
3. **The AK5558 register image.** Nothing in this tree writes an AK5558
   register — H1S1's `StartAK4619()` writes the codec only (S81 §3.6, which
   this session re-checked and could not contradict). If the parts need a
   register image they have never had one.
4. **The rev B analog board's isolation links.** S46-4 recorded them **open** on
   2026-09-14 with the ADC lanes reading two distinct values. An open link
   disconnects SDOUT from the CPLD and exact zero is then the correct reading.
5. **A dated CPLD flash log.** A sub-investigation this session found that
   `loadlogic.sh`'s `shipping` label was hardcoded to the pre-fix
   `a1f6672af6c3` from S37 until S82 changed it, so any session that handed the
   bench back with `loadlogic.sh shipping` between S42 and S81 silently
   reflashed a bitstream that drives no converter clock — and none of those
   bitstreams could identify itself. **Which bitstream S54 measured its real
   preamp noise on is therefore not determinable from the repo**, and S54's
   data is unambiguously live converter data. That conflict is real and is §5's
   hub item.

---

## 4. Gate 4 — the talkback loop is not carrying the tone

The dispatch: *"a tone out of AUX 1 seen on the talkback lane IS the
confirmation; if the lane reads silence the cable is absent — report and stop
that gate."*

The rig proved the AUX 1 bus (`-43.008 dBFS` at oscillator −40.0), raised the
rails, and read the talkback lane. It does not follow the oscillator:

```
level independence at MGN 0 dB (code 2), three drives:
   osc  -21.25 dBFS -> lane  -105.773 dBFS
   osc  -31.25 dBFS -> lane  -105.609 dBFS
   osc  -41.25 dBFS -> lane  -105.676 dBFS
```

**A 20 dB change in drive moves the lane by 0.16 dB.** What *does* move it is
MGN2R, the codec's own gain — −106.7 dBFS at code 0 rising monotonically to
−87.8 dBFS at code 11 — which is the front end amplifying its own noise floor.
At code 11 S70 measured a loop gain of **+41.75 dB** with the lane at −6.5 dBFS;
today the same code puts the lane at **−87.8 dBFS**, about **81 dB** below it.

Gate 1 of the S70 sheet (the 27 dB MGN2R drop) reads `25.558 dB [FAIL]` and the
T1 ladder's steps scatter by ±12 dB, both of which are what a noise floor does
when you change the gain in front of it. **No T1 or T3 number from this run is a
measurement of the talkback path, and none is quoted as one.** The gate stops
here, as instructed.

Note that gates 2 and 4 fail the same way: the AUX 1 bus carries the tone
digitally, and **nothing analog comes back into the unit on any path**. That is
one observation, not two.

---

## 5. The unit, as it was left

1. **LOGIC**: `maincap` and `pisel` flashed for the latency arms, each FLASH OK
   on attempt 1 with IDCODE `0x020a30dd` read before and after, each identified
   on the part by its design-ID; **`dsp4_logic.7a6a4529f29c` — shipping —
   restored last and read back: `design_id 32'h4529f29c cfg_bits 16'h0010
   SHIPPING`.**
2. **DSP pair**: the **as-found** pair `84c7951333e982204a38fe65e49d3fd6` /
   `bb2a7c6ea9e5d0caa419bc0b15a97f7c` booted from `/home/app/s78restore` and
   configured twice — `MAGIC 0xD5B40001`, `CHIP_ID` 1 and 2, **BOOT_STAGE 7
   both chips, SPI_ERR_COUNT 0 both chips**, FRAME_COUNT running. **Nothing was
   deployed**; `~/dspboot/ldr/manifest.txt` untouched.
3. **595 chain**: the **SAFE image `[0x01]×24 + [0x00]` VERIFIED 200/200,
   written AFTER the last DSP boot** (S70-7).
4. **AN_EN (GPIO 26)**: raised for gates 2 and 4 under this dispatch's
   authority, read back `hi` each time, and **`op pd | lo` at handback, read
   back not assumed.**
5. **CS_M (GPIO 27)**: `ip pu | hi`, as found.
6. **matrix-app**: active, **3 of 3 MCUs verified on the FIRST restart** —
   `MCU boot verified: H1S1 / H1S3 / H1S4`, read from the whole of
   `/home/app/logs/log`.
7. **H1S1 source hash-check (S81-Q4)**: `Core/Inc/matrix.cs`
   `f2fceaebc4b0fc4861dfed5784352147` in the build tree, in the Dropbox copy
   (`_mx/MW/D24/FW/H1S1/Core/Inc/matrix.cs`) and in this repo's S81 snapshot —
   **three ways identical, unchanged, nothing flashed.**

## 6. For the hub

🔴 **S83-Q1 — the AK5558s need a bench visit with a scope, or one bitstream
change.** Everything a desk or a link can ask has been asked. The cheapest
decisive step is probe 1 of §3.4: a `cdc_*`-style ones/toggles/frames counter on
`ad[0..2]` in the LOGIC, which turns "is the pin moving" into a knock. It is a
bitstream change, so it is the hub's to authorise.

🔴 **S83-Q2 — the loop cable.** Neither gate 2's path (AUX 1 → J25) nor gate 4's
(AUX 1 → J1) carries the tone, while the AUX 1 bus does. No desk instrument can
tell an absent cable from a dead output stage. If PW can confirm what is
patched, gate 4 is unblocked immediately; if the cable *is* in J1, the DAC
output stage becomes the suspect and that is a different investigation.

🔴 **S83-Q3 — the bench's CPLD history between S42 and S81 is not on record**
(§3.4 item 5), and S54's live converter data cannot be reconciled with the
"one month on `a1f6672af6c3`" narrative S81/S82 assumed. Worth correcting the
record rather than leaving two incompatible accounts in it.

🟡 **S83-N1 — COMPRESSOR's numeric arm needs a stimulus that does not depend on
the envelope arriving twice at the same word** (§1.4). The reading is now
precise enough to design against; it was not before.
