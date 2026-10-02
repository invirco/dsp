provenance: AI-drafted 2026-10-02 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S165 — option slot 3 by code alone: desk check

Desk only. No hardware, no flash, no CPLD programming, MW-D24-2 untouched, no
RTL or firmware written, no new fitter run (every figure below is from a
report already in the tree). A figure I could not find is written "not found";
a figure I derived by hand is written "ESTIMATE" with its basis.

Sources: mx26 `docs/d24-signals-index.md` (opt3 rows 90–119),
`docs/d24-cpld-fanout.csv` (rows 104–111), `docs/d24-tdm-map.md` + `.csv`,
`docs/study-d24-dante-card.md`, `src/hw/d24-hw-connectors.csv` (opt3 rows
30–34); dsp `MW/D24/DSP/dsp4-s34-20260911.md` (S34, which already fitted slot 3
in Quartus), `shared/dsp4-logic/quartus/dsp4_logic.qsf`,
`quartus/dsp4_logic.sdc`, `quartus/output_files/dsp4_logic.{fit,sta}.rpt`
(fitter run 2026-09-25 13:18, Quartus 21.1.1, MAX V 5M1270ZT144C4),
`rtl/dsp4_clkgen.v`, `rtl/dsp4_logic_top.v`.

## Headline

1. **Slot 3 as a clock FOLLOWER of the D24 (the D24 leads) is code-only on the
   CPLD side** — and the board is already wired for it. Slot-3 data lanes are
   plain wires through U3 (about 1 LE per lane; S34 measured it).
2. **Slot 3 as the clock LEADER (the card drives BCK/FS, the CPLD follows) is
   NOT code-only in any cheap sense.** Tri-stating U3.141/142 is easy; making
   the fabric and the SHARCs follow is not (no PLL in this part, everything
   derives from the 49.152 MHz XO). Design-grade — **needs opus-tier
   judgement, not guessed here.** 🔴 note for PW below.
3. **Both 32×32 cards live does not fit at TDM8 on the SHARC lanes**
   (64 in needed vs 32 available even after packing) and **the TDM8↔TDM16
   re-framing inside the CPLD does not fit the CPLD** (881/1270 LEs already).
   The cheap route is to run the OPTION SLOT lanes at TDM16 natively: 2+2
   lanes per card, pass-through in the CPLD, and a SECOND clock pair for the
   slots from two spare U3 pins (85/81). That needs a copper change (rev-C
   wire mod: 2 lifts + 2 wires per slot; rev D: layout) — so "code alone" is
   true only for the TDM8 / 32-in-total case.

## 1. Clock pin direction

**Netlist (evidence):**

| signal | slot pin | board path | U3 pin |
|---|---|---|---|
| FS_3 | J3 A4 | R64 (33R) → net `L0` | 141 |
| BCK_3 | J3 A5 | R67 (33R) → net `C1` | 142 |

`d24-signals-index.md:93-94`, `d24-netlist-global` G2604 (FS_3) / G2442
(BCK_3); S34 §1.3 table: `C1` = U3.142 with taps R111 (converter BCK), R65/R66/R67
(BCK_1/2/3), R61 (BCK_4); `L0` = U3.141 with R112, R62/R63/R64, R60. One active
driver pin per net, no inversion, **no buffer anywhere in the path — only the
33R series taps.** The same two nets also feed the ADC/DAC FPC (R111/R112), so
anything that changes who drives C1/L0 changes it for the converters too.
There is no MCLK, enable or ID line on slot 3 reaching U3: A1 `RST_O` goes to
J17 P75 (the M MCU, not U3; no RST_O row in `d24-cpld-fanout.csv`), A2/A3 are
the slot UART to the S MCU, A14/A15 SWD, B1–B3 "carry NO NET on rev C"
(`d24-hw-connectors.csv:34`). BCLK is the converters' MCLK
(`study-d24-dante-card.md:40-52`), so no MCLK pin is wanted.

**Pin direction today:** `conv_bck` PIN_142 and `conv_fs` PIN_141 are
**outputs**, 3.3-V LVTTL, 16 mA, Column I/O, Global = no
(`dsp4_logic.fit.rpt:239-240, 435-436`; `rtl/dsp4_logic_top.v:67-68,
853-854`: `conv_bck = bck8`, `conv_fs = fs8`). They are ordinary I/O, so tri-state
or bidirectional use is possible (MAX V I/O has an output-enable; the repo
holds no datasheet for this — family knowledge, not a file citation).

**Clock-capable input?** The fitter shows the only global clock is
`sysclk` PIN_88 = GCLK3, "Clock pins 2/4" used (`fit.rpt:175,592`). Pins 141/142
are listed Global = no. **Which pins are the four dedicated clock inputs: not
found** (not in the fit report, `.pin` file or any doc in the tree). It would be
settled by the 5M1270ZT144 pinout table (Altera MAX V device handbook) or by one
trial fit with `conv_bck` as an input driving a register clock (desk-possible,
but that is RTL — not done here).

**Verdicts**

| role | verdict | evidence / what settles it |
|---|---|---|
| D24 leads, slot 3 card follows (Dante as follower of the D24; MW-Net) | **code-only / zero change** | pins are already outputs carrying bck8/fs8; the slot-3 taps already see them |
| Card leads, U3 follows | **unknown → design-grade (opus)** | below |

Why "card leads" is not just a tri-state. U3 would have to tri-state 141/142
(code-only, ≈ a few LEs: the `assign` becomes `bidir` with an OE). But the
fabric is `dsp4_clkgen`: a free-running counter on the 49.152 MHz XO makes
bck8/bck16/fs8/fs16, drives both SHARCs' clocks, `dsp_clk` for their CLKIN
(pin 140 = sysclk/2), and the converters' clock. If the card's BCK/FS become the
converters' clock while the SHARCs stay on the XO, the converter frame and the
DSP frame are different clocks: the wire-through lanes (`i_dspa[n] = ad[n]`,
S34 §4.1) slip, nothing resamples them in the CPLD (no RAM blocks, no PLL: the
fit report has no PLL section; `UFM 0/1`). Making everything follow means
clocking the fabric from the card BCK (12.288 MHz, no multiplier to get back to
49.152 MHz or the 24.576 MHz TDM16 pair) or adding ASRC somewhere. That is an
architecture decision about the clock tree (and whether `dsp_clk` can follow),
not a desk-checkable edit — **escalate to opus; not guessed.** The Dante study
itself says the leader/follower choice is "a policy call" (`study:182-186`) and
the mechanism it cites (tri-state) covers only the CPLD side.

## 2. CPLD capacity

**Device / utilisation, shipping build (fit 2026-09-25 13:18,
`dsp4_logic.fit.summary`, `fit.rpt:165-185`):**

| resource | used | of | % |
|---|---|---|---|
| logic elements | 881 | 1,270 | 69 |
| registers | 663 | 1,270 | 52 |
| LABs | 107 | 127 | 84 |
| I/O pins | 68 | 114 | 60 |
| global clocks | 1 | 4 | 25 |
| clock pins | 2 | 4 | 50 |
| UFM | 0 | 1 | 0 |

Timing: sysclk (49.152 MHz, 20.345 ns) setup slack **+5.517 ns**, hold +1.118,
Fmax 67.44 MHz (`sta.summary`, `sta.rpt:107-111`). **No set_input_delay /
set_output_delay is in `dsp4_logic.sdc`, so slot-pin I/O timing is not
analysed: not found.**

Context: the S34 baseline was 404 LEs (32 %); today's 881 is +477. I have not
attributed the growth (it carries the cdc/ad witness instruments, per the RTL
comments at lines 188–800). That growth is also the lever if room is needed.

**Added logic**

| item | LE cost | basis |
|---|---|---|
| (a) slot-3 4-in/4-out lane routing, own lane map | **≈ 1 LE per lane, ~8 LEs; pins +8** | MEASURED by S34: `s34a_slot3` 402 LEs vs 404 shipping (−2, "noise"), pins 71→79. Re-measure on today's RTL to confirm. |
| (a′) same with the TDM16 scheme: 2 in + 2 out | ≈ 4 LEs; pins +4 | scaled from (a), ESTIMATE |
| (b) clock source mux, D24-leads only | **0** | the pair already exists; the slot gets its own pair on 2 new output pins (see §6) |
| (b′) clock-source mux with card-leads / glitch-safe switchover | **not found, not estimated** | depends on the §1 architecture decision |
| (c) TDM8 ↔ TDM16 packing of a card's lanes, inside U3 | **ESTIMATE ≈ 400–500 LEs for 4+4 TDM8 lanes → 2+2 TDM16 lanes, one card; ≈ 800–1000 for two cards** | hand derivation, not fitted: a TDM8 lane word arrives at half the TDM16 bit rate, so each in-lane needs a ~32-bit shift + hold (≈ 64 flops), each out-lane ~32 flops, per S34's own note ("a full frame of delay: 32 flops per lane"); no RAM in the part, so each is registers |

**Verdict:** (a) and the clock pair **fit with a wide margin** (~380 LEs free;
84 % LAB use is the thing to watch, so re-fit to confirm). (c) **does not fit**
(one card 881 + ~450 ≈ 1330 > 1270; two cards much worse), unless the
instrument logic is shed first — measurement needed. The clean answer is to not
need (c): carry the option lanes at TDM16 on the slot copper (§6).

Pins: 68/114 today; slot 3 at 4+4 data lanes = 76; at 2+2 = 72; plus 2 for the
second clock pair = 74 (65 %).

## 3. Lane budget into the SHARCs

Today (`d24-tdm-map.md` §2 and csv): DSPA in 8 lanes TDM8: I0–I2 ADC, I3 slot-1
NI3 (8 ch only), I4 codec, I5 FREE (old D32 snake, retired by D11), I6 Pi PCM,
I7 MEMS talkback. DSPB out 8 lanes TDM8: O0/O1 DAC, O2 codec, O3 parked + Pi
return, O4–O7 slot 1 (32 out). Note the in direction today gives slot 1 only
**8** channels in (I3), not 32.

Need with slot 1 (usbcard 32×32) AND slot 3 (32×32 Dante, or MW-Net up to its
declared count): **64 in + 64 out.**

| scheme | in | out | verdict |
|---|---|---|---|
| TDM8 as today | I5 only → 8 ch | 0 free | does not carry both |
| TDM8 + pack codec/Pi/MEMS onto one lane (S34c, +15 LEs measured) | frees I6, I7: I3, I5, I6, I7 = 32 ch in | O3 + O4–O7 = 40 ch out | **32 in total, 40 out: not both at 32×32** |
| **TDM16 on the option lanes + pack codec/Pi/MEMS onto I4** | I3, I5, I6, I7 = 4 TDM16 lanes = **64** ✓ | O4–O7 = 4 TDM16 lanes = **64** ✓ (O3 spare, packing on the out side optional) | **cheapest that carries both** (as `d24-tdm-map.md` §3) |

Allocation: slot 1 = I3 + I5 in, O4 + O5 out; slot 3 = I6 + I7 in, O6 + O7 out
(or the reverse; the map is a CSV choice). Packing the input side is
mandatory in this scheme (it is the only way I6/I7 become free).

**Changes in the SHARCs (from S34 §1.1–1.2; I re-verified none of the SRU codes
— the HRM has no core chapter, per memory):**

- DSPA chip 1: the four RX halves SPORT3A / 5A / 6A / 7A take the TDM16 pair
  instead of the TDM8 pair — two SRU lines per lane in `sru_config.c`
  (S34 gives the I3 and I5 lines: `DAI0_PB19_O→SPT3_ACLK_I`, `DAI0_PB20_O→SPT3_AFS_I`;
  I5: `DAI1_PB20_O→SPT5_ACLK_I`, `DAI1_PB19_O→SPT5_AFS_I`, note the DAI0/DAI1 19/20
  swap). **I6/I7 not analysed in S34 — same pattern expected, not checked.**
  Halves do not share a clock (HRM §21 per S34), so mixing TDM8 and TDM16 on
  the same SPORT top is legal.
- DSPB chip 2: **O4–O7 TX moves from the DAI1-out TDM8 pair (BCK7/FS7) to a
  TDM16 pair: not analysed anywhere in the tree** — S34 only covered the
  receive side. Needs the same SRU read before it is trusted.
- `sport_config.c::cfg_region()` takes `wsize`/`mcpde` per region, not per lane;
  the mixed-format region means moving those two fields into the per-lane tuple
  that `dsp_codegen.py::gen_block_io` emits, `CS0_A` becomes a 16-bit mask, the
  packed DMA buffer doubles for those lanes (S34 §1.2).
- `shared/dsp4-logic/tdm-lines.csv`: the four RX and four TX lines carry
  `TDM16` / `slot_count=16`; `slot-map.csv` rows re-slotted (163 rows,
  hash-pinned into the CPLD label).
- defs `products/d24/tdm-map.csv`: **does not exist in `defs/` at
  defs-v2026.09.28.4** (no file in `defs/products/d24/`; the mx26 CSV is a
  DRAFT awaiting PW review, `d24-tdm-map.md` header). It has to be created
  there, with a schema in `defs/common/schema/`, and a new `defs-v*` tag; this
  repo only consumes it (CLAUDE.md hard rule).

## 4. Exclusive operation

Dante and MW-Net never run together, one slot-3 card at a time (PW 09-27).
**Nothing in the RTL needs to know which card is present** — as long as both
cards are clock FOLLOWERS (D24 leads) and both use the same lane format. There
is no ID or strap line from slot 3 to U3 (§1: only the 8 lane pins and the two
clock pins reach it; B1–B3 carry no net on rev C). The card identity can reach
the S MCU/CM over the slot UART (A2/A3 → S MCU).
Where something would need to know:
(i) the card-leads case of §1 (a role bit for the clock mux); (ii) a different
lane format per card (e.g. MW-Net at a different count than 32). Both would
need either a build-time constant per product config (consistent with
"ONE DSP4 firmware + product config") or the S34 SPI-listener register
(+48 LEs measured, shares the DSP boot bus with no arbitration, so writes only
outside a boot window — S34 §2.3).

## 5. Work list

Sizes are ESTIMATES (my judgement, not measured), in working days of one
person; "bench" = needs hands on the unit/board.

| # | change | where | size | bench? |
|---|---|---|---|---|
| 0 | PW rulings (🔴 below): follower-only?; TDM16-on-slot-copper vs TDM8; one card or both | hub | — | no |
| 1 | `defs/products/d24/tdm-map.csv` + schema, land mx26 draft, new `defs-v*` tag | defs | 0.5–1 | no |
| 2 | `slot-map.csv` / `tdm-lines.csv` rows for slot 3 (and re-slotted slot 1), `gen_slot_map.py` regen | dsp `shared/dsp4-logic` | 0.5 | no |
| 3 | CPLD RTL: slot-3 (and slot-1 widening) lane pass-through; `fs16/bck16` second pair to pins 85/81; input-side pack of codec/Pi/MEMS (S34c +15 LEs measured); remove ad hoc park pins 109/110/111 from slot-2 lanes (S34 §4.3, if still true) | `dsp4_logic_top.v`, `.qsf` | 2–3 | sim only |
| 4 | Re-fit + timing on today's RTL (confirm margin, LAB use; add I/O constraints) | quartus | 0.5 | no |
| 5 | SHARC: DSPA SRU I3/I5/I6/I7, **DSPB TX SRU for O4–O7 (needs its own read)**, per-lane `wsize/mcpde`, codegen tuple, buffers | `sru_config.c`, `sport_config.c`, `dsp_codegen.py` | 3–5 | build only until flashed |
| 6 | Copper: rev-C wire mod = lift R67 (BCK_3) and R64 (FS_3) from C1/L0, wire to U3.85 / U3.81 (S34 §1.3 numbers; slot 1 likewise R66/R63); rev D = route from C2/L1 | board | 0.5 bench | **yes** |
| 7 | Bench: scope the new pair (24.576 MHz / 48 kHz) on the slot pins, then card bring-up; loopback CPLD for audio per the bench recipe | unit | 1–2 | **yes** |
| 8 | If card-leads is required: clock-tree design (opus), then RTL | — | not estimated | yes |

## 6. WIDER OPTION LANES (hub addendum, PW)

PW: 4 TDM8 lanes per card today; 2 TDM16 or 1 TDM32 might be more efficient.

### 6a. CPLD side

**Clock source.** TDM16 (BCLK 24.576 MHz, 48 kHz FS) is already generated:
`bck16 <= ~cnt[0]` (sysclk/2) and `fs16`, with the same 1024-sysclk frame
counter as TDM8 (`dsp4_clkgen.v`); they already go out to the SHARCs
(`bcki[1]`/`fsi[1]`, S34 §1.3), and `dsp_clk` already leaves the part at the same
24.576 MHz (`fit.rpt:245`; `dsp_clk` min-pulse-width slack 37.401 ns,
`sta.summary`). So **TDM16 for the slots costs no new logic**, only two output
pins and, on rev C, copper (C1/L0 are shared with the converters, which stay
TDM8 — S34 §1.3). Spare pins: U3.85 (`C2`), 81 (`L1`), 87 (`C0`) are single-pin
nets reaching nothing (S34 §1; qsf comment; the fit shows 81 and 85 as
RESERVED_INPUT_WITH_WEAK_PULLUP, `fit.rpt:379-382`).

**TDM32 (49.152 MHz BCLK)** would need BCK = sysclk itself (a register toggle
tops out at sysclk/2). MAX V has no PLL (none in the fit report) and I have no
DDR I/O to cite, so the output would be a pass-through of the sysclk pin with
data launched on one sysclk edge per bit. Setup slack is +5.517 ns on a
20.345 ns period, so the internal data path would be ~14.8 ns deep at that rate;
the clock-to-pin delay of slot pins: **not found** (not constrained). Not
recommended; see 6c.

**Fmax / I/O timing:** internal Fmax 67.44 MHz (>49.152, so internal logic would
clear TDM32 on paper); **slot-pin I/O timing: not found** — `dsp4_logic.sdc` has
no input/output delay constraints. The first thing step 4 adds.

**Re-framing cost:** TDM16 slot lanes with the TDM16 pair = pass-through, ≈ 1 LE
per lane (S34 `s34a_slot3`). Re-framing TDM8↔TDM16 inside U3 (card stays on the
TDM8 pair) = ESTIMATE ≈ 400–500 LEs per card — does not fit (§2). TDM32
re-framing: not estimated (no use case).

**Slot pins freed (CPLD side, per slot):** today 4 + 4 data pins; TDM16 = 2 + 2
(frees 2 in + 2 out = 4 pins per slot); TDM32 = 1 + 1 (frees 6 per slot). Counting
the second clock pair (+2 pins, shared by slots), net per scheme for ONE slot-3
card: 4×TDM8 = +8 pins; 2×TDM16 = +4 +2 = +6; 1×TDM32 = +2 +2 = +4.

### 6b. SHARC side and lane budget

Yes. The fabric and the SHARC lane budget are TDM16 already (mix fabric
O/I lanes). **A TDM16 option lane is a wire through U3 into a SPORT half whose
other half is TDM16 or idle** (S34 §1.1–1.2). That avoids the ~400-LE re-framing,
and is the item-3 scheme above: it is what makes "both cards at 32×32" fit
(64 in / 64 out = 4 TDM16 lanes each way) where 4×TDM8 per card does not (8
lanes per card per direction). With 1×TDM32 per card: 2 lanes each way for both
cards, which would free more lanes still, but see 6c.

### 6c. Card side and margin

Hub fact (taken as given, not re-derived): RT118x SAI minimum BCLK cycle 40 ns =
25 MHz (IMXRT1180EC Rev 8 §4.6.2).

- **TDM16, CPLD side:** the period is 1/24.576 MHz = 40.690 ns → **margin 0.690
  ns = 1.7 %** against 40 ns. The CPLD source is a registered toggle off the XO,
  so duty is the XO's (min-pulse-width slack 9.956 ns on sysclk). The hub's
  "~2 %" is this number. Setup/hold over the slot connector (33R + trace + the
  other taps still loading the net on rev C) is **not found** and is not
  analysed; the 33R series and the extra taps on C1 are the things that cost
  edge time. This is the tightest element of the scheme and must be judged with
  a scope at the slot pin before a card is built to it.
- **TDM32:** 49.152 MHz (20.345 ns) is below the RT118x's 40 ns minimum — does
  not fit. Worth keeping open for a non-RT118x card? The Dante module (Brooklyn 3)
  limit: **not found** — the public datasheet omits "slots per line, bit-clock
  rates" (`study-d24-dante-card.md:107`), and Audinate's OEM docs are not in the
  tree. Also not found: the SHARC SPORT/DAI maximum bit clock (no HRM core
  chapter, per memory). **Recommendation: do not design for TDM32.** The CPLD has
  no way to generate it cleanly, the RT118x cannot take it, and TDM16 already
  carries both cards.
- **One more card-side point, flagged not resolved:** the Dante study's channel-fit
  row says the 32×32 module maps 1:1 at TDM8 with "no TDM16"
  (`study-d24-dante-card.md:36`). That is a statement about the card's own
  interface; it does not account for the SHARC lane budget in item 3. A card
  built for 4×TDM8 would need the CPLD re-framing that does not fit. So the card
  carrier must be built to the format chosen here — a decision that has to
  precede the carrier layout.

### 6d. Verdict table (per slot, one card, 32×32)

| scheme | fits CPLD? | fits card? | pins (data + clock) | logic delta | risk |
|---|---|---|---|---|---|
| 4×TDM8 each way, as today | yes, ~8 LEs (S34 measured) | yes (RT118x/Brooklyn native) | 8 data, uses existing pair | ~8 LEs | **does not carry two cards**: SHARC lanes run out (§3) |
| **2×TDM16 each way** (second clock pair from U3.85/81) | **yes**, ~4 LEs + 0 clock | RT118x yes on paper at 1.7 % margin; Brooklyn 3 **not found** | 4 data + 2 shared clock | ~4 LEs | needs **copper** (rev-C wire mod / rev D); 1.7 % margin; DSPB TX SRU not yet analysed |
| 2×TDM16 each way by re-framing in U3 (card keeps TDM8) | **no** (~+450 LEs; 881 → ~1330 of 1270) | yes | 8 data, 0 extra clock | ~+450 LEs ESTIMATE | does not fit |
| 1×TDM32 each way | not recommended: no clean 49.152 MHz BCK in this part, slot I/O timing not found | **no for RT118x** (20.3 ns < 40 ns); Brooklyn not found | 2 data + 2 clock | not estimated | rejected |

## 🔴 Notes for PW (answers by re-dispatch or steer)

1. **Follower or leader?** Is the Dante card ever allowed to LEAD the clock
   (D24 follows)? Options: (A) never — the D24 always leads, the Brooklyn runs in
   external-word-clock mode, zero CPLD change, the Dante domain follows the D24
   (the "D24 leader" case in the study); (B) yes — then the clock tree needs an
   opus-tier design (§1), not a tri-state. Recommend A.
2. **TDM16 slot copper:** accept the slot pair moving to a second U3 clock pair
   (rev-C wire mod: R67/R64 for slot 3, R66/R63 for slot 1 if the usbcard also goes
   TDM16; rev D layout) — or stay TDM8 and accept 32 ch in total (and 40 out)
   for both slots together. The code-only path is only the second.
3. **Card carrier format** (Dante and MW-Net): should be specified as 2×TDM16
   in/out, not 4×TDM8, if (2) is a yes. The Brooklyn 3 TDM16 capability needs
   Audinate OEM documentation (not found).
4. Not analysed, not written: DSPB (chip 2) TX SRU for TDM16 on O4–O7;
   I6/I7 SRU lines; slot-pin I/O timing (no I/O constraints in the `.sdc`).
