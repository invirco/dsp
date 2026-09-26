provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S122 — the haptic speaker path: the panel speaker leaves every mixer signal path

**PW ruling 2026-09-26:** *"the spkr feed is for screen button haptics only, and
should be completely separate from all mixer signal paths."*

**What this session did:** gave the D24 panel speaker its own source in the DSP
graph, took the monitor bus off it, and made the generator refuse to build a
graph in which anything else reaches it. The stimulus for the acoustic self-test
moved onto the new source with it. **Everything here is desk work, built and
gated; NOTHING IS PROVED ON THE PART** — the bench was PW's from part-way
through the session (hub hold, 2026-09-26 evening) and the six bench items are
listed with their recipes in §9.

---

## 1. The map: what reaches the speaker, and what shares its lane

Read off the graph, the netlist and the codec's own register image. Every row
is sourced; nothing is inferred from a name.

```
  C2_HPT_01  (HAPTIC, chip 2, no inputs)
      |  _blk_C2_HPT_01, Q4.28
      v
  C2_SPKR_OUT  (OUTPUT_TDM, sink=SPKR, sport 2 slot 0, slot_count 1)
      |  _tx_out_slot_C2_SPKR_OUT -> _gather_chip2 -> TX DMA -> B_O2
      v
  CDC_I  ->  AK4619 (analog U3)  ->  AOUT1L = U3 pin 22
      |  net G0209 — EXACTLY TWO PINS: U3.22 and C23.+
      v
  C23  ->  net SPKR (G3461)  ->  analog J59.12 = digital J42.12  ->  C82
      v
  TS482 (digital U32, unity, BRIDGED, on the DIGITAL board's 5 V — always on
         while the unit is powered, independent of AN_EN)
      v
  SPKR0 / SPKR1 (G3462/G3463)  ->  lswitch J1.6/7  ->  J2.1/2  ->  panel speaker
```

### 1.1 The four codec DAC slots, and which are fitted

The DSPB→codec lane is SPORT 2, 8 slots. Four of them are the AK4619's DAC
channels, `CODEC_OUT_1..4`:

| signal | slot | codec pin | fitted? | who writes it now | who wrote it before S122 |
|---|---|---|---|---|---|
| `CODEC_OUT_1` | 0 | `AOUT1L` (U3.22) | **YES — the panel speaker** | `C2_SPKR_OUT` ← `C2_HPT_01` | `C2_MON_OUT` ← the monitor bus |
| `CODEC_OUT_2` | 1 | `AOUT1R` | no — `C20` is DNP | **nobody** | `C2_MON_OUT` (its second slot) |
| `CODEC_OUT_3` | 2 | `AOUT2L` | no — `C21` is DNP | `C2_CODEC_AUX_OUT` ← `C2_MAIN_DLY` | same |
| `CODEC_OUT_4` | 3 | `AOUT2R` | no — `C22` is DNP | `C2_CODEC_AUX_OUT` | same |

Sources: the DNP list is `mx26 tools/netlist/parts.csv:67`; the two-pin net is
`mx26 docs/d24-netlist-global-pins.csv` G0209; the slot map is
`MW/D32/DSP/SHARC/dsp.csv` (`sport_id=2;slot_start=…`) and S102.

**Slot 1 is now unwritten and that is visible in the generated lane table.**
`C2_MON_OUT` was `slot_count=2` and claimed slots 0 and 1; `C2_SPKR_OUT` is
`slot_count=1`. The chip-2 TX lane's chip-select mask moves `0x000F → 0x000D`
in `src/chip2/lane_config.c` — the codec is no longer clocked data for a
channel whose output capacitor is not fitted.

**`C2_CODEC_AUX_OUT` still writes slots 2 and 3, and that is left alone
deliberately.** Those are `AOUT2L/R`, both DNP, and S108-2 records that
`DAC2SEL` selects `SDIN2` — ignored in TDM mode — so the main mix reaches two
codec channels that reach no fitted part and are fed from a source the part
ignores. It is not the speaker and PW's ruling does not reach it. It is
already an open hub question (S102-2: "`C2_CODEC_AUX_OUT` reaches no fitted
part on a D24 — hub's call"), and S122 adds one fact to it: the aux-out lane is
now the ONLY mixer path left on the codec, so retiring it would take the mixer
off the AK4619 entirely.

### 1.2 What `C2_MON_OUT` was, and why it was a trap

S102 named the speaker route correctly and the name is what hid it: the node
that drove the panel speaker was labelled **"Monitor Out"**, after a pair of
rear-panel TRS jacks it does not drive. So:

- `Mon001Level001/002` **were** the speaker's level cells, and `defs` declares
  `C2_MON` at `level_l_db=0.0` — **unity**. There was no resting value in the
  graph that was silent.
- Every boot's config commit therefore left the speaker wide open, whether a
  test asked for it or not (S115 says so in as many words).
- Every AL1 press asserted `Mon001Level001/002 = 1.0` and, until S115, nothing
  ever put them back. PW heard a short tone and then a long hiss on every
  press, and then continuous noise with the rails down (the dispatch's own
  "today's conflict").
- S115's fix was a teardown: zero the two cells on the way out, and prove it.
  That is a correct fix for a defect that should not be possible, and it is
  what S122 removes the need for.

---

## 2. The disconnect, and how it is enforced

### 2.1 The graph

Three rows of `MW/D32/DSP/SHARC/dsp.csv` changed; the whole diff is:

```
- C2_MON_DLY,2,DELAY,Monitor Delay,2,C2_MON,C2_MON_OUT,1,1794,…
- C2_MON_OUT,2,OUTPUT_TDM,Monitor Out,2,C2_MON_DLY,,1,1796,sport_id=2;slot_start=0;slot_count=2;…;sink=SPKR,
+ C2_MON_DLY,2,DELAY,Monitor Delay,2,C2_MON,,1,1794,…
+ C2_HPT_01,2,HAPTIC,Panel Haptic,1,,C2_SPKR_OUT,1,2175,trig=0;sample=1;level=1.0;test_on=0;test_level=0.0;click_hz=2500:3000:1500;click_tau_ms=2.5:1.8:3.0;click_peak=0.94;click_end_db=-60.0;tone_hz=1000.0;scope=D24,InstantCtl
+ C2_SPKR_OUT,2,OUTPUT_TDM,Panel Speaker Out,1,C2_HPT_01,,1,1796,sport_id=2;slot_start=0;slot_count=1;…;sink=SPKR,
```

`C2_MON_OUT` is renamed, not deleted, and keeps SPI word 1796, so **no address
moves**: `dsp_address_map.md`, all four `MW/*/MX/_matrix.csv` and
`ghost_cells.h` come out of `./regenerate-dsp-contract.sh` **byte-identical**,
and `chip1/dsp_params.asm` with them. The only generated contract artefact that
changes is `chip2/dsp_params.asm`, which gains six dispatch entries and two
spares at `0x087F..0x0886` and grows the table from 2,176 to 2,184.

The monitor chain — `C2_MON` → `C2_MON_DLY` — is unchanged, keeps its addresses
and its cells (`Mon001InputSel001`, `Mon001Level001/002`, `Mon001Delay001`), and
now ends on a block nothing reads. **Writing those cells can no longer make a
sound.**

### 2.2 The guard — a build that routes a mixer node to the speaker FAILS

Two instruments, one declaration. The declaration is `sink=SPKR`, which S102
added for exactly this reason; neither guard has the slot number typed into it,
so moving the speaker to another slot moves both checks with it.

**`dsp_validate.py::check_speaker_slot`** — on `dsp.csv`, reports every
violation in one run rather than the first:

```
  [speaker slot] C2_SPKR_OUT is fed by C2_MON_DLY, a DELAY node. PW ruling
  2026-09-26: the panel speaker carries HAPTICS ONLY and is separate from every
  mixer signal path -- only a HAPTIC node may reach a sink=SPKR output. Give the
  speaker its own source, or send C2_MON_DLY to an output that is not the speaker.
  [speaker slot] C2_MON reaches the speaker through C2_MON_DLY. The speaker
  source takes NO input -- that is what makes the separation checkable in one hop.
```

**`dsp_codegen.py::_speaker_slot_guard`** — called from `gen_block_io()` on the
node set that becomes the chip-2 TX lane table, i.e. the thing that decides what
goes on the wire. It raises and the build stops:

```
  ValueError: THE PANEL SPEAKER IS NOT A MIXER OUTPUT. C2_SPKR_OUT (sink=SPKR,
  SPORT2 slot [0]) is fed by C2_MON_DLY, a DELAY node. …
```

It checks three things:

1. the `sink=SPKR` output's inputs are all `HAPTIC` nodes (and it has at least
   one);
2. the haptic source itself takes **no** input — so "separate from every mixer
   path" is decidable in one hop and cannot be defeated by feeding the haptic
   node;
3. no other `OUTPUT_TDM` node writes any slot the speaker output writes.

**A THIRD CHECK, in `gen_dsp_csv.py`, for the case neither of those can
catch.** Both guards above are silent on a graph with no `sink=SPKR` node at
all — they have to be, because they are run on fragments and on graphs that are
not a D24's (`dsp_validate.py`'s own control test is a one-row CSV; the chip-1
half of every codegen run has no speaker in it). So "the speaker did not quietly
stop being declared" is checked in the one place that knows it is building the
shipping graph: at the bottom of `gen_dsp_csv.py`, exactly one `sink=SPKR`
output must exist and it must be fed only by `HAPTIC` nodes.

**All four arms were fired, on purpose** (negative controls, scratch copies,
none committed):

| mutation | caught by | how |
|---|---|---|
| `C2_SPKR_OUT` fed by `C2_MON_DLY` (a mixer node on the speaker) | `dsp_validate.py` 2 errors, exit 1 | `dsp_codegen.py` `ValueError`, build stops |
| `C2_HPT_01` given `C2_MON_DLY` as an input (the mixer one hop further out) | `dsp_validate.py` 1 error, exit 1 | `dsp_codegen.py` `ValueError`, build stops |
| `C2_CODEC_AUX_OUT` moved to `slot_start=0` (a second writer on the slot) | `dsp_validate.py` 1 error, exit 1 | `dsp_codegen.py` `ValueError`, build stops |
| `sink='SPKR'` changed to `sink='DNP'` (the declaration itself removed) | `gen_dsp_csv.py`, exit 1 | *"0 OUTPUT_TDM nodes declare sink=SPKR and the graph must have exactly one"* |

### 2.3 Where the monitor bus goes instead — **it does not go anywhere**

Stated plainly, as the dispatch asks, and **no routing is invented**.

On a D24 the monitor bus now reaches **no converter output at all**. The three
rear sockets that might have carried it are already spoken for, and S121 read
each one off the copper from the other end:

- the rear **Monitor Out L/R** TRS jacks are `DAC_15`/`DAC_16` = `MainCtr` and
  `MainSub`, the main crossover's centre and sub legs (S121-6, measured — S121
  tests Monitor R at 100 Hz for that reason);
- the **Centre/LF XLR** is `DAC_14`, fed from aux bus 12;
- the **headphone jack** is `DAC_09/10`, fed from aux buses 9 and 10;
- D24 declares aux buses **1–8**, so no cell reaches any of aux 9–12 (S121-5).

Those three sockets are **ONE open PW question already on the board** and this
session does not re-ask it. What S122 adds to it is one line: **the monitor bus
is now a fourth item in the same question.** It has cells, it has a fader, a
delay and a source selector, and it has nowhere to come out. Three ways to
close it, for whoever answers:

1. give the monitor bus the rear Monitor jacks and move `MainCtr`/`MainSub`
   elsewhere (that is what the jacks are silk-screened for);
2. give it the headphone jack (`DAC_09/10`, which have no DSP source today);
3. rule that a D24 has no monitor output, and retire `C2_MON`/`C2_MON_DLY` the
   way S1-1 retired the sub chain — nodes kept, addresses kept, reason recorded.

Until one of those, the monitor chain runs and publishes a block nobody reads:
about 1,100 cycles a block on chip 2 for a `MONITOR` and a `DELAY` at
`ch_count=2`, which is 0.3 % of budget and is the honest cost of leaving a
question open rather than guessing at it.

---

## 3. The haptic node

`C2_HPT_01`, type `HAPTIC`, chip 2, `scope=D24`, eight SPI words at page 1
addresses **2175–2182** (`0x087F..0x0886`).

### 3.1 What it does

| state | what the node writes |
|---|---|
| idle | digital zero — **latched**, so the block buffer is written once on the way into silence and not again |
| a click was triggered | the selected stored click, scaled by `level`, one block at a time, ending exactly on its last sample with the rest of that block zeroed |
| test tone on, no click | one stored 1 kHz period on a circular buffer, scaled by `test_level`, phase continuous across blocks |

A click **wins** over the test tone. A trigger during a click restarts it. The
kernel consumes the trigger word itself, so the host never writes it back and
never polls; `busy` is the read-back.

### 3.2 The stored clicks are PW's own audition, modelled

The dispatch described the audition as "gated 2.5 kHz full-scale bursts
(4/8/15 ms)". **The files say otherwise, and the files win.** PW's six
candidates are on the bench unit at `/home/app/*.wav` (48 kHz, 32-bit, 330 ms,
one burst at 150 ms, peak 0.94); this session copied them to the shared store at
`_Matrix/Products/D24/dsp/audition-20260925/` with a README, because a bench
unit's home directory is not a place to keep the only copy of a design decision.

Every tonal candidate is an **exponentially decaying sine**, not a gated burst.
A log-linear fit to each file's own per-half-cycle peaks gives round numbers:

| file | fit | max \|model − file\| |
|---|---|---|
| `1_click_1k5` | 1500 Hz, τ = 3.000 ms | 0.0001 |
| `2_click_2k5` | 2500 Hz, τ = 2.500 ms | 0.0054 |
| `3_click_4k` | 4000 Hz, τ = 2.000 ms | 0.0001 |
| `6_release_3k` | 3000 Hz, τ = 1.800 ms | 0.0001 |
| `4_tick_noise` | noise — not a tone, not modelled | — |
| `5_thump_plus_click` | 217 Hz + modulation — not modelled | — |

So the node stores that waveform, generated from its own four numbers
(`click_hz`, `click_tau_ms`, `click_peak`, `click_end_db`) and never typed:

| `sample` | model | stored | words |
|---|---|---|---|
| 1 | 2500 Hz, τ 2.5 ms | 17.27 ms | 829 |
| 2 | 3000 Hz, τ 1.8 ms | 12.44 ms | 597 |
| 3 | 1500 Hz, τ 3.0 ms | 20.73 ms | 995 |

Each is truncated where the envelope passes −60 dB and faded to **exactly zero**
with a raised cosine over its last millisecond, so the last stored sample is 0
whatever the decay is and the amplifier is never handed a step. Each is
normalised to its own peak of 0.94, the way the audition files were.

**`MW/D24/DSP/s122/check_click_model.py` proves the claim rather than asserting
it**: it reads the Q4.28 words out of the GENERATED assembly (not out of the
generator, which would only prove the generator agrees with itself) and compares
them sample for sample with the WAVs.

```
  sample 1  2500 Hz, tau 2.5 ms  (press)     829 words  peak 0.9400 (file 0.9400)  max|diff| 0.00098  rms 0.000107  OK
  sample 2  3000 Hz, tau 1.8 ms  (release)   597 words  peak 0.9400 (file 0.9400)  max|diff| 0.00100  rms 0.000138  OK
  sample 3  1500 Hz, tau 3.0 ms  (spare)     995 words  peak 0.9400 (file 0.9400)  max|diff| 0.00094  rms 0.000095  OK
  test tone  48 samples = exactly 1000 Hz at 48 kHz   max|err| 1.863e-09
  MATCH
```

Max deviation 0.00098 of full scale is −60 dB. **These are the clicks PW
approved**, not clicks like them.

**Which is press and which is release is PW's ruling**, not this generator's.
The mapping above follows the file names and this dispatch's own text; changing
it is four numbers in `dsp.csv`, no address and no cell.

### 3.3 The test tone is 1 kHz, on purpose

One stored period of 1 kHz at 48 kHz is exactly 48 samples, so it loops
seamlessly for the cost of a circular buffer and there is no seam for the
measurement to fit. It is 1 kHz and not 2.5 kHz because **AL1's entire
calibration** — the level law, the bandpass-THD ceiling, the S115 MEMS
measurement — was taken at 1 kHz through this loop, and changing the frequency
would have thrown away the only acoustic reference this unit has.

### 3.4 Cycles

Static counts, off the generator's own emitted text. **Not measured on the
part** — that is a bench item (§9).

| path | instructions |
|---|---|
| idle block (the overwhelmingly common case) | **15** — three loop-length clears and four two-instruction tests, each ending in a branch |
| a click block | 15 setup + **15 × BLOCK** in the loop + 10 bookkeeping ≈ 265 |
| a test-tone block | ≈ 265, the same loop |
| the first silent block after a sound | 15 + BLOCK + 4 ≈ 35 |

At BLOCK = 16 and 983.04 MHz, chip 2's budget is **327,680 cycles/block** and
the standing figure since PW signed the SIMD configuration is **84.34 %**
driven, 0 missed blocks in 135,000 (S82, reproduced by S86 at 84.47 % and S91 at
84.38 %). Against that:

- **idle: ~15 cycles = 0.005 % of budget.** Below anything any instrument in
  this project can resolve — the cross-boot spread on code that did not change
  at all is about 2,000 cycles/block.
- **sounding: ~265 cycles = 0.08 %**, and only for the 12–21 ms a click lasts.

The node it replaces did not cost nothing either: `C2_MON_OUT` was an
`OUTPUT_TDM` with `ch_count=2`, so the net change to a silent D24 is close to
zero and is certainly inside the instrument's own noise. **A capacity run is
owed and is a bench item, not a claim made here.**

### 3.5 Memory

Measured off the two link maps (`dsp_memreport.py`, chip 2, shipping
configuration):

| pool | before | after | delta |
|---|---|---|---|
| code (VISA SW) | 152,578 / 262,144 — 58.2 % | 153,242 — **58.5 %** | **+664 B** |
| DM data + stack | 279,116 / 375,264 — 74.4 % | 289,260 — **77.1 %** | **+10,144 B** |
| delay lines | 1,694,112 / 2,072,576 — 81.7 % | unchanged | 0 |
| IVT | 128 / 260 | unchanged | 0 |

86,004 bytes stay free in the DM pool and 108,902 in the code pool; nothing is
near the 90 % line `dsp_memreport.py` warns at.

The DM is almost all table: 2,421 click words + 48 tone words + 6 index words +
8 contract words + 4 state words + a 16-word block buffer + `_buf_` = 2,504
words = 10,016 bytes, and the measured 10,144 is that plus the output node's
own arrays moving. The 664 bytes of code are the kernel.

### 3.6 How it shares the future drum-sample engine

Two parts of this node generalise and one deliberately does not.

- **The trigger discipline generalises.** Host writes 1, the kernel consumes it
  on its own block, sets `busy`, and there is no handshake. It costs two
  instructions on an idle block and it cannot wedge: there is no state the host
  has to clear.
- **The table layout generalises.** One `_hpt_off_`/`_hpt_len_` index pair over
  one flat sample pool, all generated from a parameter list. Adding a sample is
  data, not code, and the same shape carries a drum kit.
- **Writing one TDM slot directly does not generalise**, and it must not. This
  node has no inputs and no bus, which is exactly what makes the speaker's
  separation checkable in one hop by `_speaker_slot_guard`. A drum engine sums
  into a bus like every other source, so it is a different node class that
  borrows the player — not this node grown up. Saying so now is cheaper than
  discovering it when someone adds a bus output to the speaker's source.

### 3.7 Latency, from the cell write to sound

**Not measured.** The bench was PW's. What can be stated from the code and the
configuration, as a bound rather than a figure:

| stage | bound | source |
|---|---|---|
| host SPI write lands | **owed — bench item** | the parameter link's own write time |
| the kernel sees `trig` | 0 to 1 block = **0 to 333 µs** (mean 167 µs) | the node reads it once per block at BLOCK = 16 |
| the block reaches the TX DMA row | fixed, immediately after the block interrupt | `DSP4_TX_DEFER=2` (S89e) — the gather no longer moves with the load |
| the row goes on the wire | ≤ 1 block, and a half early | `DSP4_TX_EARLY=2` (S9-2) |
| AK4619 DAC group delay | **owed — the datasheet figure belongs here** | not read in this session |
| TS482 + speaker + air | ~1 ms/m of bench, negligible on the panel | — |

So the DSP's own contribution is bounded at about **1 ms** and is dominated by
the host write, which is the part nobody has measured. §9 gives the recipe.

---

## 4. What AL1 looks like now

The acoustic loop (catalog rows 56/57, `--only AL1`) drove the speaker through
a mixer route: `TEST_OSC` → strip 20 → MAIN → `C2_MAIN_FDR` → `C2_MON` →
`C2_MON_DLY` → `C2_MON_OUT` slot 0. That route no longer exists. AL1 now drives
the haptic node's test tone and measures the same MEMS lane with the same
instrument.

| | before (S115) | after (S122) |
|---|---|---|
| stimulus | `C1_TEST_OSC` into strip 20 | `C2_HPT_01` test tone |
| cells written to set it up | **43** on a cold press (31-strip CLOSE list + 12 route cells), **4** on a repeat | **0** |
| reads to prove the state | 12-cell route probe | 2 words |
| cells written to tear it down | 4 (`Mon001Level001/002`, `Chan020MainOn001`, `Chan020Mute001`) | 2 (`TestOn`, `TestLevel`) |
| standing state left on the unit | the whole standing route, plus a marker file (`.al1_route_standing`) tracking it | **none** |
| can a press that dies half way leave the speaker live? | **yes, until S115's teardown; and a BOOT could do it with no test at all** | **no** — the graph has no resting value that sounds |
| projected setup time per press | ~1.5 s repeat, ~10 s cold (S115's measured per-cell cost) | ~0.8 s, both |
| the strip-20 donor problem (S121-2) | strip 20 is the loudest lane on the unit for the whole pass | gone — no strip is involved |

Everything the verdict is computed from is unchanged: MeasChan 54, the
4,096-sample window, the S115 coherent capture of `_buf_C1_XIN_MEMS` and the
bandpass-THD ceiling. **The calibration constants are therefore still
meaningful but are no longer calibrated**: the level law was fitted with a
converter, a strip and two bus faders in the path that are no longer in it.
`--al1-calibrate` MUST be re-run on the part before an AL1 verdict is trusted,
and that is a bench item (§9), not something a desk can do.

### 4.1 The code that changed

- **`tools/pi/dsp4_s49_osc.py`** gains `--haptic` (and `--haptic-base`): the
  stimulus becomes the chip-2 haptic test tone instead of the chip-1 oscillator
  on a strip. It opens a chip-2 scope, refuses an image whose map has no
  `_hpt_test_on_C2_HPT_01`, writes `TestLevel`/`TestOn` with **ramp 0** and
  reads each back, walks the level in the same 24 equal-dB steps
  (`--ramp-ms`), and stops the tone in the same session (`--then-off`). It
  also writes `OscOn 0` and `OscChan 0` explicitly, so "the chip-1 oscillator
  is not the stimulus" is a write and not an assumption. The measurement half —
  MeasChan, the window wait, the coherent capture, the JSON — is untouched, and
  the JSON now records `"stimulus": "haptic"`.
- **`tools/pi/s89_set.py`** gains a `cN@ADDR` name form (`c2@2175=1`), so the
  haptic block can be written through the image's own dispatch table while its
  cells are unnamed. It is the same path a cell write takes — still never a
  peek — and it is deliberately ugly to type.
- **`tools/pi/d24_selftest.py`**: the route write, the CLOSE list, the standing
  marker, the two target tables and the probe helpers are **deleted** (about
  190 lines net). `al1_silence()` stays, because the read-back is still the only
  evidence that the stop landed, and it now writes two words instead of four.
  The AS-DAC slot capture follows the node rename to
  `_tx_out_slot_C2_SPKR_OUT`.

---

## 5. Why there is no `DSP4_HAPTIC` build flag

The dispatch says "build against the proposal behind a flag". The **names** are
what the proposal is about, and nothing in the image depends on them: no cell is
emitted, the eight words are dispatched-but-uncelled, and the host reaches them
by address. So there is nothing for a flag to gate.

Adding one anyway would cost more than it buys, in two ways this tree has
already paid for once:

- **`shipping.config`'s own rule (S82)** is that every `DSP4_*` switch must
  either have a field in `DIAG_BUILD_CFG{,2,3}` or appear in
  `DIAG_CFG3_INSTR_SUM`, and `check_shipping_config.sh` enforces the mirror in
  both directions. A new switch is a `shipping.config` line, a `diag.h` bit
  (CFG3 bit 24 is free) and a mirror entry — three places, for a flag with no
  measurement behind it.
- **A default-off flag would leave the speaker dead**, because after S122
  nothing else writes its slot. AL1 could not run, and the "off" arm would be a
  configuration no product wants and no test can use.

If PW wants the switch anyway it is CFG3 bit 24, one `shipping.config` line and
one `DIAG_BUILD_CFG3_VALUE` term; say so and it is twenty minutes.

---

## 6. What was regenerated, and what did not move

`./regenerate-dsp-contract.sh`, clean:

- **byte-identical**: `MW/D32/DSP/dsp_address_map.md` (5,827 rows), all four
  `MW/*/MX/_matrix.csv`, `MW/D32/DSP/ghost_cells.h`,
  `src/chip1/dsp_params.asm`.
- **changed**: `dsp.csv` (3 rows), `src/chip2/dsp_params.asm` (+8 dispatch
  entries, table 2,176 → 2,184), `src/chip2/block_io.asm` and
  `src/chip2/lane_config.c` (the node rename and the CS mask `0x000F → 0x000D`),
  `src/chip2/process_chain.asm` (one more node, so the `DSP4_NODE_LIMIT2`
  indices above it renumber), `src/chip2/nodes/C2_HPT_01.asm` (new),
  `src/chip2/nodes/C2_SPKR_OUT.asm` (new), `src/chip2/nodes/C2_MON_OUT.asm`
  (deleted).
- `./check-sharc-codegen-drift.sh`: **passed** (tree == generator output, 735
  files, 0 differ).
- `check-matrix-addresses.py`: D32 5,780/5,780 and D24 3,989/3,989 mapped cells
  carry an address, unchanged.
- `defs.lock` **unmoved** at `defs-v2026.09.24.2`; nothing written into `defs/`.
- **No contract bump is owed**: no cell, no address and no matrix row moved.

## 7. Build

Shipping configuration (`shipping.config` as committed, no overrides), both
arms built from a clean tree:

| | before | after |
|---|---|---|
| `chip1.ldr` | 426,464 B, `1be74e042cff134c7085dfb08dade517` | 426,464 B, `1be74e042cff134c7085dfb08dade517` — **byte-identical** |
| `chip2.ldr` | 367,056 B, `9da000f0f95ea0165f5fab43ba96e06e` | **377,864 B, `a4eb1f1ab9288dd8cbd28566ad6ea79d`** |

The "before" pair is this session's own baseline build: `git archive HEAD` of
`MW/D32/DSP/SHARC/src` into a scratch tree, built with the same `build.sh` and
the same `shipping.config`, so the two differ in the change and in nothing
else.

**Chip 1 rebuilding byte for byte is the check, not a coincidence**: this change
is entirely chip 2's, and a chip-1 image that moved would say something had
reached further than it was meant to.

The `DSP4_TEST_NODES=1` pair — the one AL1 needs, because `TEST_MEAS` lives
inside that guard — also builds clean: `chip1.ldr` 433,508 B
`7f226919a5d181410c3804d92678da19`, `chip2.ldr` 379,424 B
`9e8a1a9edf19a90ce7ac3df1586c00f6`. **Built, not deployed** — the unit is PW's.

The hand-written SHARC assembly assembled and linked first time in both
configurations.

## 8. Findings

- **S122-1** — the auditioned clicks are **exponentially decaying tones**, not
  gated bursts. The dispatch (and the pipeline note behind it) described them as
  "gated 2.5 kHz bursts, 4/8/15 ms"; the files are `A·exp(−n/τ)·sin(2πfn/fs)`
  with τ between 1.8 and 3.0 ms and a total length of 12–21 ms. Building the
  dispatch's description would have produced a click PW has not heard.
  Recorded so the hub's own note can be corrected at the source.
- **S122-2** — the six audition WAVs existed **only** on the bench unit's home
  directory (`/home/app/*.wav`). They are the record of a design decision PW
  signed off by ear and nothing else captures them. Copied to
  `_Matrix/Products/D24/dsp/audition-20260925/` with a README and a fit table.
- **S122-3** — the haptic words are `InstantCtl` and have **no ramp
  companions**, so a RAMPED SPI write to any of them walks the three words above
  it — and above `Level` sits `TestOn`. Every writer in this change passes ramp
  0 and says why. If PW wants a ramped haptic level, the node grows the
  companion words first; it is not a host-side choice.
- **S122-4 🟡 (not caused here, one fact added)** — `C2_CODEC_AUX_OUT` is now
  the ONLY mixer path left on the AK4619. It writes `AOUT2L/R`, both DNP, from
  `C2_MAIN_DLY`, and S108-2 says `DAC2SEL` selects `SDIN2`, which TDM mode
  ignores. Retiring it would take the mixer off the codec entirely. Already
  S102-2 and still the hub's call.
- **S122-5 🔴 (for PW, and NOT a re-ask)** — the monitor bus now reaches no
  converter output on a D24. It is a fourth item in the open question about the
  rear Monitor jacks, the Centre/LF XLR and the headphone jack (S121-5/-6), and
  §2.3 lists the three ways to close it. No routing was invented.

## 9. What is owed on the part — every bench item, with its recipe

**None of the following was done: the hub put MW-D24-2 on hold for a PW patch
pass part-way through this session.** The only bench contact this session made
was before the hold and was read-only: `hostname`/`uptime`/`systemctl
is-active`, a directory listing, and an `scp` of the six audition WAVs. No
write, no pin, no DSP link, no deploy.

1. **Nothing — the builds are done.** Both configurations were rebuilt from a
   clean tree after two concurrent builds raced for
   `MW/D32/DSP/SHARC/build/` mid-session; §7 quotes the clean run. Stated
   because the race happened and a reader should not have to wonder.
2. **Deploy and boot.** Stage the `DSP4_TEST_NODES=1` pair the S102 way
   (`ARM=s122 DSP4_TEST_NODES=1 ./loopthd.sh`), deploy `d24_selftest.py`,
   `s89_set.py` and `dsp4_s49_osc.py`, boot + config commit twice (bench recipe).
3. **The speaker slot reads EXACT ZERO with every mixer bus driven hard.** The
   headline proof of the whole dispatch: set a strip to full scale on MAIN,
   `Main001Level001 = 1.0`, `Mon001Level001/002 = 1.0` — the exact state that
   used to make the speaker hiss — then
   `python3 s89_slotcap.py <symdir> 2 _tx_out_slot_C2_SPKR_OUT 256`. Every word
   must be `0x00000000`. Take the same capture with a click playing as the
   positive control, so a zero is a measurement and not a dead instrument.
4. **A click is audible on trigger.** `s89_set.py <symdir> c2@2176=1 c2@2175=1`,
   with the MEMS lane captured (`_buf_C1_XIN_MEMS` through `_scope_record`). PW
   should also hear it.
5. **Latency from the cell write to sound.** Time the `link.write` on the host
   (`perf_counter` either side), and take the acoustic onset from a coherent
   MEMS capture armed immediately before the trigger. Report the host write, the
   DSP bound from §3.7 and the measured total separately — the interesting
   number is the host write, which nothing has measured.
6. **AL1 through the new path, then `--al1-calibrate`.** `d24_selftest.py
   --only AL1` for a reading, then the calibration run: the old level law was
   fitted through a strip and two bus faders that are no longer in the path, so
   the existing `AL1_CAL` line is stale by construction. Record the old and new
   tables side by side, as S110/S115 did.
7. **A capacity row.** `ARM=s122 PRODUCT=d24 ./capacity.sh --driven` against the
   84.34 % standing figure, to put a measured number under §3.4's static counts.
8. **Leave the unit as found**, and state it exactly: the S121 hand-back
   discipline, plus the new one — the speaker's two words at zero, proved by
   read-back.
