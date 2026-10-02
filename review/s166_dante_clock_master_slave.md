provenance: AI-drafted 2026-10-02 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S166 — D24 clock tree as master or slave to Dante: desk design study

Desk only. No hardware, no flash, no CPLD programming, MW-D24-2 untouched, no
RTL or firmware landed. Trial fits and one simulation were run in a scratch copy
of `shared/dsp4-logic` (Quartus Prime Lite 21.1.1, 5M1270ZT144C4, iverilog);
the trial module is reproduced in the appendix so the numbers can be re-made. A
figure I could not find is written "not found"; a figure I derived by judgement
is written "ESTIMATE" with its basis.

PW ruling 2026-10-02: "D24 clocks need to be master or slave to Dante" — both
roles, selectable. Standing intent (PW 09-17): jitter cleaning lives on the
Dante carrier, no VCXO on the D24, changeover may mute.

Sources: S165 (`review/s165_slot3_desk_check.md`), mx26
`docs/study-d24-dante-card.md`, `docs/d24-cpld-fanout.csv`,
`docs/d24-netlist-global.md` §(b)/(e), `src/hw/d24-hw-connectors.csv`,
`docs/d24-signals-index.md`; dsp `shared/dsp4-logic/rtl/*.v`,
`quartus/dsp4_logic.{qsf,sdc}`, `quartus/output_files/dsp4_logic.fit.rpt`;
`MW/D32/DSP/SHARC/src/{sport_config.c,cgu_init.asm,diag.asm,main.asm}`;
AKM AK4458 datasheet 014011794-E-02 (2017/07) and AK5558 datasheet
015099850-E-02 (2022/02), fetched from akm.com 2026-10-02.

## Headline

1. **D24 as master is zero change on the D24**, as S165 said: U3 already drives
   BCK_3/FS_3 (12.288 MHz / 48 kHz, 3.3 V LVTTL) to slot pins A5/A4. The
   carrier takes both; the Dante module syncs to them.
2. **D24 as slave — recommended: option C, with one rule added.** The carrier
   sends a **49.152 MHz reference clock (REFCLK) locked to Dante** on slot pin
   **B1**. Inside U3 a **glitch-free clock switch** picks the XO or REFCLK as the
   fabric clock. Everything downstream of the switch is unchanged RTL: same
   1024-tick frame counter, same bck8/bck16/fs8/fs16, same converter clock.
   The added rule: **the D24 drives slot BCK/FS in both roles.** The module's
   TDM port is always a slave, so no slot pin ever changes direction, and C1/L0
   (and so the converters) never see a second driver.
3. **The SHARC CLKIN does not change source.** The `dsp_clk` toggle flop moves
   onto the raw XO (one RTL line). SPORTs are all externally clocked slaves
   (`sport_config.c:10`, ICLK=0/IFS=0) and the audio is paced by SPORT DMA
   interrupts, not a timer (the core timer drives only the diag LED,
   `diag.asm:19`). So there is no PLL relock, no reboot and no SPORT restart.
   **No dsp firmware change is needed for the switch itself.**
4. **The board already has the copper for most of this.** U3's four dedicated
   clock pins are **18, 20, 89 and 91** (trial fit: GCLK0, GCLK1, GCLK2,
   GCLK3). 18 and 20 are in use as outputs. **89 (`LOGIC_PLL1_0`) and 91
   (`LOGIC_PLL1_1`) are free, and they already cross J18 to the Digital board**,
   where they end at the dead D32 header J33 (pins 2 and 3). So does
   `LOGIC_PLL1_2/1_3` (U3.93/94, J33.4/.5). The rev-C wire mod is **three wires
   on the Digital board only** (J3.B1/B2/B3 → J33.3/.4/.5): no lifted parts and
   **no DSP card change**.
5. **Trial fit (option C, REFCLK on U3.91): 946 / 1,270 LEs (+65 on the 881
   shipping baseline, which re-fits to exactly 881 in scratch)**, LABs 109/127
   (86 %), global clocks 3/4, pins 71/114. Setup slack is +4.238 ns on both
   clocks (shipping: +5.778 ns), hold +1.119 ns. The switch plus a clock
   activity detector costs +20 LEs. The frequency qualifier costs the other +45.
6. **Simulation of the switch** (XO and REFCLK 100 ppm apart, four changeovers,
   one REFCLK death). No runt pulse: the narrowest fabric clock high or low is
   10.172 ns, which is the nominal half-period. The worst planned-switch stall
   is a single 45.2 ns low phase. A dead REFCLK falls back to the XO after a
   **0.70 µs** low phase. The AK4458 enters reset only if MCLK stops for more
   than 10 µs (datasheet p.66), so neither event should reset the DACs. That is
   simulated, not measured.
7. **Options A and B are rejected.** A (12.288 MHz in) cannot make the 24.576 MHz
   TDM16 mix fabric between the SHARCs without a multiplier. B (24.576 MHz in)
   is possible, but it re-times the whole fabric. It needs the same carrier PLL
   as C and costs much more RTL and risk. D (the module's own MCLK output):
   **not found**. No Audinate OEM data is in the tree. Under C it would simply
   be one possible reference for the carrier's PLL.

One correction to the dispatch's established facts: `sysclk` on PIN_88 is **not
on a dedicated clock pin**. The shipping fit reports `Info (186228): Pin
"sysclk" drives global clock, but is not placed in a dedicated clock pin
position` (`dsp4_logic.fit.rpt:775`), and the XO reaches GCLK3 through internal
routing. Pin 91 is the dedicated GCLK3 input. This matters for REFCLK placement
(§3.4) and is a rev-D jitter question (🔴 6).

## 1. What exists today (clock tree)

```
Y1 49.152 MHz XO ── U3.88 (ordinary I/O → internal route → global)
   └─ sysclk (one domain; every register in U3 is posedge sysclk)
        ├─ cnt[9:0] 1024-tick frame (48 kHz)
        ├─ bck8 = sysclk/4 (12.288) ─┬─ U3.142 = C1 ─ 33R taps: R111 converters (BICK = MCLK),
        │                            │                          R65/R66/R67/R61 BCK_1..4
        │                            └─ bcki[0,2,5,7] → SHARC TDM8 pairs; mems_bck
        ├─ fs8 ──────────────────────┬─ U3.141 = L0 ─ 33R taps: R112, R62/R63/R64/R60 FS_1..4
        │                            └─ fsi[...]
        ├─ bck16 = sysclk/2 (24.576), fs16 → bcki/fsi[1,3,4,6] → SHARC TDM16 mix fabric
        ├─ pcm_clk = sysclk/16 (Pi I2S)
        └─ dsp_clk_q toggle = sysclk/2 (24.576) → U3.140 → both SYS_CLKIN0
```

Every U3 data mover launches and samples on sysclk ticks picked by strobes
(`bck8_launch`, `bck8_sample`, …), four ticks per BCK8 bit. The S85 two-edge AD
witness depends on that 4× oversampling (`dsp4_logic_top.v:332-441`).

## 2. D24 as master (the Dante module follows the D24)

**Zero change on the D24, confirmed.** The clocks are already outputs on the
slot, with no buffer and no strap (S165 §1):

| slot 3 pin | signal | source | level / drive | form |
|---|---|---|---|---|
| A5 | BCK_3 | U3.142 (C1) → R67 33R | 3.3 V LVTTL, 16 mA | 12.288 MHz (TDM8, 256 fs); 24.576 MHz if the S165 TDM16 pair is adopted |
| A4 | FS_3 | U3.141 (L0) → R64 33R | 3.3 V LVTTL, 16 mA | 48 kHz, **one BCK wide**, asserted one BCK before slot 0 (MFD=1, frame-sync early); data launched on BCK falling, sampled on rising, 32-bit slots |

What the carrier must receive: **BCK and FS, both.** The module's TDM port
needs both to run as a slave. For the module's media-clock sync input, whether
it wants a word clock (48 kHz), BCK or an MCLK is **not found**, because the
public Brooklyn 3 datasheet omits it (`study-d24-dante-card.md:107`). FS_3 is a
one-bit-wide pulse, not a 50 % word clock. If the module's sync input needs a
square word clock, the carrier makes one from BCK and FS (a ÷256 counter phased
by FS, carrier-side logic). The D24 changes nothing either way.

In this role U3 runs on the XO, and REFCLK and CLK_REQ (below) are ignored.

## 3. D24 as slave (everything in the D24 follows Dante)

### 3.1 Option A — card supplies BCK 12.288 MHz + FS, U3 clocks its fabric from it

What breaks without a 2×/4× clock:

| item | needs | from 12.288 MHz alone |
|---|---|---|
| bck16/fs16, the TDM16 mix fabric between DSPA and DSPB (bcki/fsi 1,3,4,6) | 24.576 MHz | **impossible.** No PLL in MAX V, and a register toggle tops out at fclk/2. The only other route, an XOR delay-line doubler, has uncontrolled duty, and the TDM16 margin is already 1.7 % (S165 §6c). |
| `dsp_clk` (SHARC CLKIN, 20–30 MHz) | 24.576 MHz | 12.288 MHz is below the 20 MHz minimum (`dsp4_logic.sdc` note, datasheet Table 23). It would have to stay on the XO, which is fine (§3.5). |
| U3 data movers (4 ticks per BCK8 bit) | 49.152 MHz | Strobes vanish. Every module needs a rewrite to dual-edge logic (negedge flops are legal in MAX V), including the S85 two-edge AD witness, the cdc witness, the PCM re-framer and MEMS. |
| who drives C1 | — | The card's BCK on A5 lands on C1 through R67, but C1 is driven by U3.142 (an output, not a clock pin) and feeds the converters plus four other taps. U3 would have to tri-state 142/141 and take its fabric clock from a non-dedicated pin, while the card drives five 33R taps and the converter FPC. |

**Can it be made to work?** Only by (i) dropping the inter-SHARC fabric from
TDM16 to TDM8, which halves mix-fabric capacity and is contrary to the DSP4
architecture, or (ii) keeping the fabric on the XO and adding ASRC on the Dante
lanes. U3 has no RAM and no room for ASRC, and DSP-side ASRC is not estimated.
**Verdict: not workable.**

### 3.2 Option B — card supplies 24.576 MHz BCK + FS

Can the whole tree run from it with no multiplier? **On paper, yes; in
practice, a rewrite.**

- bck16 = the input clock, **forwarded** (pin-to-pin, combinational), because a
  register cannot make fclk itself. Its delay then differs from the registered
  fs16 and data, so the launch-on-falling convention needs negedge registers for
  fs16. bck8 = ÷2 registered, fs8/fs16 from a 512-tick counter. The Pi I2S clock
  = ÷8 and the PI_TDM8 rate = ÷2 both work.
- `dsp_clk`: stays on the XO (§3.5). Forwarding the 24.576 MHz would be in
  range, but it would change SHARC CLKIN source on every changeover.
- The fabric period doubles (40.69 ns), so timing is easy. But every `frame_pos`
  user (1024 → 512 ticks: clkgen, the cdc/ad witnesses, `lid_period`, TEST
  outputs) and every strobe-based mover is re-timed from 4 to 2 ticks per BCK8
  bit. Either XO mode also runs at 24.576 MHz, which needs an XO/2 ripple clock
  promoted to a global, or the design carries two timing regimes. **ESTIMATE
  3–5 days of RTL plus re-verifying every S81–S85 witness** (basis: the size of
  `dsp4_logic_top.v`, 940 lines, almost all frame-position logic).
- **Pin.** The 24.576 MHz must not arrive on C1/A5: C1 is the converters' BICK
  and MCLK at 256 fs, and must stay 12.288 MHz. So B needs a new slot pin, and
  it should arrive on a dedicated clock pin: **U3.89 or U3.91** (GCLK2/GCLK3,
  trial fit §3.4). A non-dedicated pin can reach a global by internal routing,
  as the XO does today on pin 88, but with extra delay and no dedicated input
  buffer.
- **Effect on S165's U3.85/81 pair.** S165's second pair is an *output* pair
  (U3 → slots) on 85/81. Those are ordinary I/O on single-pin nets that never
  leave the DSP card, so S165's mod wires a Digital-board resistor pad to a
  0.5 mm TQFP pin on the other board. Under B the TDM16 BCK becomes an *input*
  in slave mode, so the pair must move to 89/91 and become **bidirectional by
  role**. Dedicated clock pins can be outputs: 18 and 20 ship as `fsi[3]` and
  `bcki[0]`. U3 would drive the pair in master mode and the card in slave mode,
  which means a contention window at every changeover, on the same net that
  feeds the slot-1 usbcard.

**Verdict:** workable but dominated by C. It needs the same carrier PLL (a
Dante-locked 24.576 MHz instead of 49.152), a fabric rewrite instead of none,
and a pin that flips direction.

### 3.3 Option C — carrier supplies 49.152 MHz REFCLK on a spare slot pin (recommended)

The carrier's PLL/jitter cleaner, locked to the Dante module, outputs
49.152 MHz = 1024 fs. U3 switches its fabric clock between the XO and REFCLK.
Because REFCLK has the XO's nominal frequency, **nothing downstream of the
switch changes**.

**The added rule:** the D24 keeps driving slot BCK_3/FS_3 (and the TDM16 pair,
if adopted) in both roles, and the module's TDM port is a slave in both roles.
In slave mode the loop is: module media clock → carrier PLL → REFCLK → U3
fabric → BCK_3/FS_3 → module TDM port. The module sees TDM clocks
frequency-locked to its own media clock at a fixed but arbitrary phase. Its
receive buffering (the datasheet quotes up to 2,000 samples per channel)
absorbs a fixed phase. **Whether Brooklyn 3 allows a slave TDM port while it is
a Dante follower: not found** (needs Audinate OEM docs, 🔴 7). If it does not,
the fallback is for the carrier to also send the module's FS on a spare pin,
and U3 jams its frame counter to it once during the mute (ESTIMATE ≈ 10 LEs).
But then the module's data is clocked by the module's BCK and sampled on the
D24's, a phase relationship set by carrier PLL and U3 path delays. That is
fragile, so it is a fallback only.

**Copper.**

| board | rev C (wire mod) | rev D |
|---|---|---|
| Digital | 3 wires, 0 lifts: J3.B1 → J33.3 (`PLL1_1` → U3.91 REFCLK); J3.B2 → J33.4 (`PLL1_2` → U3.93 CLK_REQ); J3.B3 → J33.5 (`PLL1_3` → U3.94 CLK_ACT). Minimum 2 (REFCLK + CLK_REQ); CLK_ACT is status only. The location and accessibility of the J33 and J3 pads were **not found**. A 49.152 MHz clock on a flying wire is bench-grade only. | Route B1/B2/B3 to `PLL1_1/1_2/1_3`; REFCLK as a ground-referenced trace kept away from the TDM lanes and from `PLL1_0` (§3.4); series 33R placed at the slot end |
| DSP card | **none**: `LOGIC_PLL1_1/1_2/1_3` already run U3 → J1/J2 pins 98/95/96 | none |

**CPLD logic** (trial, appendix): a classic cross-coupled glitch-free 2:1
clock switch (each side's enable registered on its own clock's falling edge and
interlocked through the other side), driving a global from logic. Added to it:

- an activity detector: REFCLK/8 synchronised into the XO domain; no edge for
  32 XO cycles (0.65 µs) means dead, and the REFCLK-side enable is cleared
  asynchronously, so a dead clock cannot hang the switch;
- a frequency qualifier: 256 ± 2 edges per 1024 XO cycles (±0.78 %), sixteen
  good windows in a row (≈ 0.33 ms) before REFCLK may be selected;
- the `dsp_clk` flop moved to the raw XO.

| trial build | LEs | LABs | globals | slack setup (XO / REFCLK) |
|---|---|---|---|---|
| shipping RTL re-fit in scratch (baseline) | 881 | 102 | 1/4 | +5.778 (sysclk) |
| switch + activity only, REFCLK on U3.89 | 901 (+20) | 108 | 3/4 | not run |
| full trial, REFCLK on U3.89 | 943 (+62) | 108 | 3/4 | +4.645 / +5.532 |
| **full trial, REFCLK on U3.91 (recommended pin)** | **946 (+65)** | **109 (86 %)** | **3/4** | **+4.238 / +4.238**; hold +1.119 |

The first fit without a `GLOBAL_SIGNAL OFF` on the activity flag promoted it to
the fourth global (4/4). The assignment keeps one global spare. LAB use (86 %)
is the figure to watch, as S165 said. The sdc in the trial is minimal (two
clocks, asynchronous groups); a landing version needs I/O constraints too.

### 3.4 Which clock pin

Trial fit with four forced global clocks and no location constraints: the fitter
placed them on **18 (GCLK0), 20 (GCLK1), 89 (GCLK2), 91 (GCLK3)**. A clock on
pin 88 gets Info 186228, "not placed in a dedicated clock pin position". On the
board:

| U3 pin | GCLK | net | today | reaches |
|---|---|---|---|---|
| 18 | 0 | FSI3 | output `fsi[3]` | DSPA |
| 20 | 1 | BCKI0 | output `bcki[0]` | DSPA |
| 89 | 2 | `LOGIC_PLL1_0` | spare (reserved input) | J18.97 → R118 33R → J33.2 |
| 91 | 3 | `LOGIC_PLL1_1` | spare (reserved input) | J18.98 → J33.3 |
| 88 | — | `LOGIC_SYSCLK` | XO in | Y1.3 |

**REFCLK goes on 91, not 89.** Pin 89 is directly beside the XO pin 88. Two
asynchronous clocks within ~100 ppm of each other on adjacent pins can couple
and beat at |f_XO − f_REF|, about 2.5 kHz at 50 ppm, which would be in-band
jitter sidebands on the converter clock. Pin 90 (VCCINT) sits between 88 and 91.
This is reasoning, not measurement; it goes on the bench list. In slave mode the
XO keeps running (it clocks `dsp_clk`), so this beat risk exists in some form
anyway (the bench list again).

### 3.5 Option D and other alternatives

- **The module's own MCLK output: not found.** The tree holds no Audinate module
  data beyond the public datasheet summary. Under C the D24 does not care: the
  carrier PLL takes whatever reference the module offers (MCLK, BCLK or FS) and
  makes REFCLK. D is therefore a carrier design input, not a D24 option.
- **"D24 always drives slot BCK/FS"** is the improvement over the study's
  original follower mechanism (tri-state the CPLD and slave to the module's
  BCK/FS, `study-d24-dante-card.md:42-45`). That mechanism is option A. It
  fails on bck16, and it puts a second driver on C1/L0, the converters' clock
  nets.
- **An external clock switch on the DSP card** (rev D only), feeding U3.88 from
  a mux of Y1 and REFCLK. Hold this in reserve in case the bench shows the U3
  logic switch adds jitter (§5). It costs DSP card copper and a part, and it
  buys a pin-driven global in both modes.

### 3.6 Comparison

| | A: BCK 12.288 in | B: BCK 24.576 in | **C: REFCLK 49.152 on B1** | D: module MCLK |
|---|---|---|---|---|
| copper, rev C | card drives C1 via R67; U3 tri-states 141/142 | new slot pin → U3.89/91 (J33 wire) + S165 pair moved to 89/91, bidirectional | **3 wires on the Digital board, 0 lifts, DSP card none** | not found |
| copper, rev D | — | route + bidirectional pair | B1–B3 → `PLL1_1/2/3` | — |
| CPLD | dual-edge rewrite; **no bck16 possible** | fabric re-time 1024→512, forwarded bck16, OE logic; ESTIMATE 3–5 days | **+65 LEs (trial), rest unchanged** | — |
| SHARC CLKIN | must stay on XO | stays on XO | **stays on XO** (1 RTL line) | — |
| dsp firmware | fabric capacity halved | none for clocks | **none** | — |
| slot pin directions | flip on changeover | flip on changeover | **never flip** | — |
| converters | card drives MCLK directly | unchanged (C1 = ÷2) | **unchanged; one 45 ns stall per switch** | — |
| carrier | BCK/FS out, contention care | Dante-locked 24.576 MHz + contention care | **Dante-locked 49.152 MHz + 2 logic lines** | reference choice for C |
| verdict | **not workable** | workable, dominated by C | **recommended** | not found / folds into C |

## 4. The clock-source switch (for C)

**Glitch-free switch in a PLL-less CPLD.** This is the trial design in the
appendix. Sim results (`tb_mux.v`, XO 49.152 MHz, REFCLK +100 ppm with an
offset phase):

| event | result |
|---|---|
| request REFCLK at 2 µs | switched at 312.6 µs (qualifier), no runt pulse |
| release at 602 µs | back on the XO at +64 ns |
| re-request at 652 µs | switched at +90 ns (qualifier still satisfied) |
| narrowest fabric clock high / low, all switches | 10.172 ns / 10.172 ns (the nominal half-period) |
| longest low phase, planned switches | 45.2 ns (one stretched cycle, ≈ 2 fabric ticks lost) |
| REFCLK stops while selected | fabric clock low for 0.70 µs, then on the XO |

**SHARCs.** CLKIN stays on the XO, so there is nothing to relock (the PW
question "what the SHARCs need when CLKIN changes source" does not arise). What
they do see is one stretched bit on every SPORT (TDM8 bit ≈ 81 → ≈ 116 ns;
TDM16 bit ≈ 41 → ≈ 76 ns). FS stays on its count, so frame sync is not lost
on paper. The SPORT error latches are already in the diag readback (`diag.asm`
item 1) and are the bench witness. Whether a SPORT flags anything on one long
bit: **not measured**. No SPORT restart is planned. The ppm step (Dante versus
XO) is absorbed by interrupt-paced block processing.

**Converters.** AK5558 (slave mode): "MCLK must be synchronized with BICK and
LRCK but the phase is not important", and it "integrates a phase detection
circuit for LRCK… reset automatically and the phase is resynchronized" if it
falls out of sync (p.31). MCLK, BICK and LRCK all come from one counter that
keeps counting through the switch, so no resync is expected. AK4458: an MCLK
stop of more than 10 µs puts it in reset with Hi-Z outputs and a click within
3–4 LRCK of restart (p.66, Fig. 69). Planned switches stall for 45 ns and the
dead-REFCLK escape for 0.70 µs, both under 10 µs, so no reset is expected. Both
are sim results, **not measured**. A changeover still carries a one-sample
disturbance and the Dante audio re-acquires lock, so it mutes (PW: changeover
may mute).

**Loss of Dante.** It is handled at three levels:
1. *Network lost, carrier alive:* the carrier PLL goes to holdover (REFCLK keeps
   running) and drops CLK_REQ, so U3 makes a planned, glitch-free switch back to
   the XO.
2. *REFCLK off-frequency:* the qualifier fails within one 20.8 µs window, and U3
   makes a planned switch back (REFCLK still running).
3. *Card pulled or powered down:* the activity detector fires after 0.65 µs and
   the asynchronous escape returns U3 to the XO after a 0.70 µs stall.

The policy alternative, staying on the carrier's holdover instead of the XO, is
🔴 4.

**Who commands the role.** This needs a desk setting (a defs cell, e.g. clock
source Internal / Dante, plus read-only status cells: active source, Dante
lock). The CM4 configures the module's Dante role over the slot UART (A2/A3)
and the carrier raises CLK_REQ only when follower mode is set and its PLL is
locked. U3 then applies its own qualification and reports CLK_ACT on B3, which
the carrier relays over the UART. **No M MCU logic, no strap, and no host write
path into U3** (the S34 SPI listener stays unbuilt). The CM sequence: mute →
set the module role → wait for CLK_ACT and module lock → settle (ESTIMATE
100 ms) → unmute. On an unplanned fallback the CM learns of it from the carrier,
or from the slot UART going silent if the card died. The fallback itself needs
no CM action. Which existing cell gives a global output mute: not checked.

**Jitter.** In slave mode the converter MCLK path is: carrier PLL output →
slot J3.B1 → Digital board → J33.3 → J18.98 → B2B → DSP card →
U3.91 (dedicated GCLK3 input) → switch LUT → logic-driven global (trial:
`fclk` placed at LC_X12_Y3_N8 → GCLK2) → `bck8` register → U3.142 → C1
(five 33R taps) → R111 → FPC → AK5558/AK4458. Today's XO path is Y1 → U3.88 →
internal route to a global → `bck8` → U3.142 → the same. What limits it, in
likely order (none measured):
1. the carrier PLL's output phase noise (specified in §7);
2. the 49.152 MHz trip across the slot connector, the Digital board and the
   J18/J1–J2 B2B, past live TDM lanes;
3. U3 internals: the logic-generated global (the switch output) adds LUT and
   routing delay and supply-coupled jitter. **This applies in master mode too**,
   because the XO also passes through the switch once it is built. MAX V clock
   jitter figures: not found;
4. the U3 output register and the five-tap C1 net, unchanged from today;
5. XO/REFCLK beat coupling (§3.4).

The bench measurement in §6 step 9 decides whether rev D needs the external
switch of §3.5.

## 5. Interaction with the other slots

- **Slot 1 usbcard** (always a clock slave of the D24): unaffected in master
  mode. In slave mode it follows Dante transitively through BCK_2/FS_2 (or the
  TDM16 pair). It sees the ppm step and one stretched bit per changeover. USB
  audio feedback is asynchronous, so the host follows the ppm. It needs nothing
  of its own: mute covers the step. Its B1–B3 pins stay unconnected.
- **MW-Net in slot 3. Assumption: the D24 leads**, and MW-Net follows the D24's
  BCK/FS like the usbcard. That is zero change. If MW-Net ever has to lead
  (networked consoles sharing a clock), the same B1/B2/B3 contract serves it
  with no new D24 copper or RTL: any slot-3 card may offer a 1024 fs REFCLK.
  **🔴 3 for PW.**
- **Dante and MW-Net never together** (PW 09-27), so one REFCLK input is enough.
- **The S165 TDM16 second pair is unaffected by C.** But this study turned up
  cheaper pins for it: `LOGIC_PLL2_1/2_2` (U3.96/97) already reach J33.8/.9 on
  the Digital board. That makes the rev-C mod Digital-board-only (lift
  R67/R64, and R66/R63 for slot 1, then wire from J33.8/.9) instead of wiring
  to TQFP pins 85/81 on the DSP card. **🔴 5.**

## 6. Ordered work list

Sizes are ESTIMATES in working days of one person. "bench" = needs the unit.

| # | change | where | size | bench? |
|---|---|---|---|---|
| 0 | PW rulings 🔴 1–7 | hub | — | no |
| 1 | Audinate OEM docs: TDM slave while Dante follower; what reference the module outputs; external-sync input form | PW / Audinate | — | no |
| 2 | Rev-C wire mod: J3.B1→J33.3, J3.B2→J33.4, J3.B3→J33.5 (Digital board only) | Digital board | 0.5 | **yes** |
| 3 | RTL: `dsp4_clkmux` (from the appendix: switch, activity, qualifier), `dsp_clk` flop onto the raw XO, ports `refclk`/`clk_req`/`clk_act`, qsf PIN_91/93/94, `GLOBAL_SIGNAL OFF` on the activity flag | `shared/dsp4-logic/rtl`, `.qsf` | 1 | sim only |
| 4 | sdc: XO + REFCLK clocks, asynchronous groups, the switch's negedge/async paths, I/O delays on the slot pins | `dsp4_logic.sdc` | 0.5 | no |
| 5 | Sim gate: switch testbench (glitch, stall, escape) into `sim/run.sh`; check the frame counter is continuous across a switch | `sim/` | 0.5 | no |
| 6 | Re-fit on the landing RTL; confirm about +65 LEs, LAB use and slack | quartus | 0.25 | no |
| 7 | defs: clock-source setting cell and status cells (active source, Dante lock); schema; new `defs-v*` tag. This repo only consumes it. | invirco/defs | 0.5 | no |
| 8 | CM4/app: role sequence (mute → module role over UART → wait CLK_ACT + lock → unmute); fallback reporting | app | 1–2 | yes |
| 9 | Bench, master mode: jitter/phase noise of conv_bck at R111, shipping bitstream vs switch bitstream on the XO (does the switch cost jitter?); spur search at the XO–REFCLK beat | unit | 1 | **yes** |
| 10 | Bench, slave mode (signal generator as REFCLK first, carrier later): switchover clicks at the DAC outputs, AK4458 not resetting, SHARC SPORT error latches clear, usbcard and Pi survive, pull-REFCLK fallback | unit | 1–2 | **yes** |
| 11 | Rev D: route B1–B3; decide on the external switch (§3.5) from item 9; consider moving Y1 to a dedicated clock pin (🔴 6) | layout | — | — |
| 12 | Carrier design to §7 | PCB team | — | — |

No dsp firmware item: the switch needs none. Lane-format work (S165 items
1–5) is independent and still owed.

## 7. Carrier requirements (for the PCB team)

The host is a mixing console. The carrier plugs into the host's option-slot
connector and hosts an Audinate 32×32 Dante module. These requirements are
written to be lifted as they stand.

**Clock roles.** The product must run in either of two roles, chosen by the host
at run time:
- **Host leads:** the host's clock is the reference. The module syncs its media
  clock to the host and acts as the Dante clock leader on the network.
- **Network leads:** the Dante network's clock is the reference. The module is a
  Dante clock follower, and the carrier hands the host a reference clock locked
  to it.

**Signals on the option-slot connector** (3.3 V LVCMOS, 5 V-tolerant not
required):

| pin | name | direction | function |
|---|---|---|---|
| A5 | BCK | host → carrier | TDM bit clock: 12.288 MHz (8 slots × 32 bit) or 24.576 MHz (16 slots × 32 bit), per the lane format agreed separately |
| A4 | FS | host → carrier | 48 kHz frame sync: high for one BCK period, the period *before* slot 0's first bit |
| A6–A13 | TDM data | both | per the agreed lane format; data launched on BCK falling edge, sampled on rising edge, MSB first, 32-bit slots |
| **B1** | **REFCLK** | carrier → host | **49.152 MHz (1024 × 48 kHz)**, phase-locked to the module's media clock, in network-leads mode |
| **B2** | **CLK_REQ** | carrier → host | high = "use REFCLK" |
| **B3** | **CLK_ACT** | host → carrier | high = the host is running on REFCLK |
| A2/A3 | UART | both | control: role selection, status |
| A1 | RST | host → carrier | reset |

**Requirements.**
1. **The host drives BCK and FS in both roles.** The module's TDM port must run
   as a slave in both roles. No module clock output may connect to the slot's
   BCK or FS pins.
2. **Host leads:** the carrier derives the module's sync reference from the
   slot's BCK/FS. If the module's sync input needs a 50 % duty word clock, the
   carrier generates it (FS is a one-bit-wide pulse). CLK_REQ is held low.
   REFCLK may run or be off; the host ignores it.
3. **Network leads:** the carrier generates REFCLK with a jitter-cleaning PLL
   locked to whatever reference the module provides (MCLK, bit clock or word
   clock). Targets, all ESTIMATES to be confirmed against host bench data:
   frequency 49.152 MHz within ±100 ppm of nominal while locked (the host
   refuses anything outside ±0.78 %); duty 40–60 %; RMS phase jitter
   ≤ 10 ps (12 kHz–20 MHz); a series-terminated (≈ 33 Ω) point-to-point output
   driving one host load.
4. **CLK_REQ goes high only when** network-leads mode is selected *and* REFCLK
   is locked and has been stable for at least 10 ms (ESTIMATE). The host then
   qualifies REFCLK for a further ~0.33 ms before switching.
5. **On loss of network lock** the carrier keeps REFCLK running (PLL holdover)
   and drops CLK_REQ, and keeps REFCLK running for at least 1 ms after
   CLK_REQ falls (ESTIMATE). The host then switches back cleanly. If REFCLK
   stops without warning, the host falls back on its own within about 1 µs,
   with an audible disturbance.
6. **CLK_ACT** shows which clock the host is running on. The carrier reports it
   and the module's lock state over the UART.
7. At reset and power-up CLK_REQ is low.
8. REFCLK is routed away from the TDM data and BCK/FS lines on the carrier, with
   a ground return beside it at the connector.
9. Role changes may mute the audio. The host mutes; the carrier does not need
   to make changeovers seamless.

## 🔴 Notes for PW (answer by re-dispatch or steer)

1. **Architecture:** accept C. REFCLK 49.152 MHz on slot B1 → U3.91 (GCLK3), a
   glitch-free switch in U3 (+65 LEs trial), SHARC CLKIN kept on the XO, and the
   D24 driving slot BCK/FS in both roles. A rejected, B dominated.
2. **Slot B1–B3 assignment** (no net today): B1 REFCLK in, B2 CLK_REQ in,
   B3 CLK_ACT out, made a slot-wide contract (slot 1 leaves them unconnected).
   Minimum is B1 + B2 if CLK_ACT is not wanted.
3. **MW-Net in slot 3 leads or follows?** Assumed to follow the D24. The B1–B3
   contract would let it lead later with no new D24 work.
4. **Loss-of-Dante policy:** fall back to the D24 XO (recommended: the D24
   becomes the leader and the Dante side re-syncs to it), or stay on the
   carrier's holdover clock.
5. **S165 second TDM16 pair:** move it from U3.85/81 (DSP card only, wire to a
   TQFP pin) to `LOGIC_PLL2_1/2_2` (U3.96/97, already at J33.8/.9), making the
   rev-C mod Digital-board-only. Rev D can route either.
6. **Rev D: the XO is not on a dedicated clock pin** (U3.88; Info 186228 in the
   shipping fit). Move Y1 to a GCLK pin on rev D (18 or 20, freeing them from
   `fsi[3]`/`bcki[0]`), or keep it there. Decide after bench item 9.
7. **Audinate OEM documentation needed** before the carrier is laid out: can the
   TDM port be a slave while the module is a Dante follower; what clock
   reference the module outputs; what form its external-sync input takes. If
   the TDM port cannot be a slave in follower mode, the fallback is a frame
   re-jam in U3 plus the module's FS on a fourth pin (fragile, §3.3).

## Appendix — trial module (scratch only, not landed)

As fitted and simulated. The landing version belongs in
`shared/dsp4-logic/rtl/` under work-list item 3. In the trial, `dsp4_logic_top`
renamed the `sysclk` port to `xo`, declared `wire sysclk` driven by `fclk`, and
moved `dsp_clk_q` to `posedge xo`. Nothing else changed.

```verilog
module dsp4_clkmux (
    input  wire xo,        // 49.152 MHz on-board XO
    input  wire dclk,      // 49.152 MHz REFCLK from the slot-3 carrier
    input  wire sel_req,   // carrier CLK_REQ
    output wire fclk,      // fabric clock (promoted to a global)
    output wire on_dclk    // CLK_ACT
);
    reg [2:0] dv;                                  // dv[2]: an edge every 4 dclk
    always @(posedge dclk) dv <= dv + 3'd1;
    reg [2:0] ts;
    always @(posedge xo) ts <= {ts[1:0], dv[2]};
    wire tedge = ts[2] ^ ts[1];
    reg [4:0] idle; reg alive;                     // dead after 32 XO with no edge
    always @(posedge xo) begin
        if (tedge) idle <= 5'd0; else if (idle != 5'd31) idle <= idle + 5'd1;
        alive <= (idle != 5'd31);
    end
    reg [9:0] win; reg [8:0] ecnt; reg freq_ok; reg [3:0] good;
    always @(posedge xo) begin                     // 256 +/- 2 edges per 1024 XO
        win <= win + 10'd1;
        if (win == 10'd1023) begin
            freq_ok <= (ecnt >= 9'd254) && (ecnt <= 9'd258);
            ecnt    <= {8'd0, tedge};
            if ((ecnt >= 9'd254) && (ecnt <= 9'd258)) begin
                if (good != 4'hF) good <= good + 4'd1;
            end else good <= 4'd0;
        end else if (tedge) ecnt <= ecnt + 9'd1;
    end
    reg [1:0] rq;
    always @(posedge xo) rq <= {rq[0], sel_req};
    wire want_d = rq[1] & alive & freq_ok & (good == 4'hF);
    reg x0, x1, d0, d1;
    always @(negedge xo) begin x0 <= ~want_d & ~d1; x1 <= x0; end
    always @(negedge dclk or negedge alive)        // escape from a dead dclk
        if (!alive) begin d0 <= 1'b0; d1 <= 1'b0; end
        else begin d0 <= want_d & ~x1; d1 <= d0; end
    assign fclk    = (xo & x1) | (dclk & d1);
    assign on_dclk = d1;
endmodule
```

Trial qsf additions: `PIN_91 -to dclk`, `PIN_93 -to clk_sel`, `PIN_94 -to
clk_act`, `GLOBAL_SIGNAL OFF -to "dsp4_clkmux:u_clkmux|alive"`. Trial sdc:
`create_clock` 20.345 ns on `xo` and `dclk`, `set_clock_groups -asynchronous`,
`derive_clock_uncertainty`.
