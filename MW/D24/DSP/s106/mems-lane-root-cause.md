provenance: AI-drafted 2026-09-24 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S106 — the MEMS lane is not a mic fault. The CPLD reads the wrong pin and never clocks the bridge.

> **`i_dspa[7]` — the lane `MM1` scores — is assigned to CPLD pin 137,
> `LOGIC_MEMS`, a net that dies at `digital J18 P26` with no load on the far
> side. The panel mic's data arrives on pin 121. And pins 119/120, the bit
> clock and frame sync the PDM bridge runs on, are left as reserved inputs,
> so `digital U13` has never been clocked in any bitstream this bench has
> carried.**
>
> `0xFFFFFFFF` is not a reading of a microphone. It is the reading of an
> unconnected CPLD input, and two other lanes on this unit return the same
> constant for the same reason.

None of the four candidates S103 listed — the panel ribbon, the LVDS pair, the
PDM clock, the mic — has been exonerated or convicted, because **nothing on
this unit has ever asked any of them a question.** `MM1` has never passed
anywhere (S103-3) because the lane was never wired up in the design.

No rails were raised. No bitstream was flashed. Nothing on the unit was
changed.

---

## 1. The copper, from the netlist

`mx26 docs/d24-netlist-global-pins.csv`, joined per net. `digital U13` is the
8-ball PDM-to-serial bridge (`mx26 src/hw/d24-hw-ics.csv:12`):

| U13 ball | net | goes to |
|---|---|---|
| `B2` | `M_BCK` (`G2674`) | **CPLD `U3` pin 119** via `digital J18.61` |
| `C2` | `M_FS` (`G2675`) | **CPLD `U3` pin 120** via `J18.62` |
| `B1` | `M_I2S` (`G2676`) | **CPLD `U3` pin 121** via `J18.59` |
| `A2` | `MEMS_CLK` (`G2746`) | `R94` → `U30` (SN65LVDS1 driver) → `CLK0/CLK1` → ribbon `J13.2/3` = `lswitch J1.2/3` → `lswitch U2` → the mic |
| `A1` | `MEMS_D` (`G2748`) | `R93` ← `U31` (SN65LVDS2 receiver) ← `D0/D1` ← ribbon `J13.4/5` ← `lswitch U1` ← the mic |
| `D1`/`C1` | `+3V3` / `GND` | digital `PSU_DIG_EN` buck (S103 §3.3) |

On `M_BCK` and `M_FS` the only active device pins are `U3.119` and `U3.120`;
every other member is a connector pin or `U13`'s own input. **U3 is the sole
driver of both.**

And the net actually *named* `MEMS` is a different thing entirely — `G2637`,
`U3.137` → `J1.26`/`J2.26` → `digital J18.26`, four connector pins and nothing
else. `mx26 docs/d24-netlist-global.md:468-472` says so in words, dated
2026-09-11:

> `LOGIC_MEMS` is the one to watch: the panel-mic path does exist, but it runs
> on `M_I2S`/`M_BCK`/`M_FS` (the PLL7 group) to `digital U13`. The net actually
> named `MEMS` is vestigial.

S103-4 flagged that as a trap for the next reader. It had already caught the
RTL.

## 2. The pin map, from the project and from the fitter

`shared/dsp4-logic/quartus/dsp4_logic.qsf:107`:

```
set_location_assignment PIN_137 -to mems
```

and `rtl/dsp4_logic_top.v:783`, `assign i_dspa[7] = mems;` — a plain wire from
that pin to DSPA's I7 input.

Pins 119, 120 and 121 appear in the qsf only inside a comment listing what is
left unassigned: *"PLL1-4 groups (89-108 X-logic), PLL5_3-PLL7_3 (112-122
X-logic)."* The fitter's own pin report agrees, and it is the authority the
S34 trap note says to trust over the qsf text:

```
RESERVED_INPUT_WITH_WEAK_PULLUP : 119   <- M_BCK, U13's bit clock
RESERVED_INPUT_WITH_WEAK_PULLUP : 120   <- M_FS,  U13's frame sync
RESERVED_INPUT_WITH_WEAK_PULLUP : 121   <- M_I2S, U13's serial output
mems                            : 137 : input : 3.3-V LVTTL : Y
```

So, in every bitstream: `U13` receives no bit clock and no frame sync, its
output is read by nothing, and the lane the DSP scores comes off a dead stub.
`PIN_137 -to mems` entered the tree in `3b48f468` (2026-07-31, the first real
pin set, read off the schematic sheet) and **has never been changed since** —
`git log -S` returns that one commit, and the qsf has had no commit since
2026-09-15. The netlist trace that found the stub is dated 2026-09-11. Nobody
went back.

**The part is carrying that bitstream.** Read off it this session, no flash:

```
$ python3 dsp4_logic_id.py --expect 83b3cc22
design_id: 32'h83b3cc22   cfg_bits: 16'h0010   SHIPPING
  MATCHES --expect 83b3cc22
```

which is `dsp4_logic.d02d83b3cc22`, the adopted shipping label.

## 3. The measurement, and its controls

Fresh, this session, 32 reps, on the signed pair (`candidate-s82`) with the
shipping bitstream identified above — `MW/D24/DSP/s106/data/rxscan-shipping-chip1.txt`:

```
  control MUST MOVE      FRAME_COUNT +4856  [ok]
  control MUST NOT MOVE  _rx_slot_C1_IN_01   1 distinct, 0x00000000  [ok]
  control MUST NOT MOVE  _buf_C1_IN_01       1 distinct, 0x00000000  [ok]
```

| DSPA lane | CPLD source | pin | fitted driver? | reading |
|---|---|---|---|---|
| 0,1,2 | `ad[0..2]` | 139/138/134 | AK5558 ×3, **yes** | CARRYING, 20+ distinct, −113…−118 dBFS |
| **3** | `ni[3]` (NET) | 3 | option slot 1 **empty** | **`ffffffff` STATIC −186.64** |
| 4 | `cdc_o` | 123 | AK4619 codec, **yes** | CARRYING, 32 distinct |
| **5** | `snake_in` | 109 | D32 snake, **not fitted** | **`ffffffff` STATIC −186.64** |
| 6 | `pcm_tdm` | — | CPLD drives it | `00000000` STATIC −336.00 |
| **7** | `mems` | **137, dead stub** | **nothing** | **`ffffffff` STATIC −186.64** |

`−186.64 dBFS` is `20·log10(1/2^31)`: the word is `−1`, every bit set.

**Three lanes whose CPLD input pin has no driver return the identical
constant; every lane that has a driver returns something else.** `IN_25..32`
and `XIN_SNK_01..08` are not microphones and nobody has ever proposed that
they are. `XIN_MEMS` sits in the same column for the same reason. The archived
S86 handback scan (`MW/D24/DSP/s86/data/rx-handback.txt`, a different session,
a different symbol map, an earlier pair) shows the same three groups at the
same value — this is not a reading that moves.

## 4. The dispatch's five steps, answered

### 1 — is there a cheaper read already flashed? No, and there could not be.

- **The CPLD's existing witnesses cannot see the MEMS group.** `cdc_o` has one
  (S81); `ad[0..2]` have six banks (S84/S85), built into every configuration
  including shipping. The knock's selector is `ad_sel[1:0]` over three lanes
  plus an edge bit — `AD_BANKS = 6`, and bank 6 does not exist. There is no
  MEMS bank. Bench note 31 is correct.
- **And a MEMS bank would have been useless**, which is the part worth saying.
  A counter on `mems` counts pin 137. It would have returned "stuck high, zero
  toggles" and been read as the mic being dead.
- **`digital U30`/`U31` have no status pin to read.** `SN65LVDS1` (driver) and
  `SN65LVDS2` (receiver) are 5-pin parts and the netlist accounts for all five
  on each: `1 = VCC`, `2 = GND`, `3`/`4` = the differential pair, `5` = the
  single-ended side. No LOCK, no fault flag, nothing to wire anywhere. Checked,
  found nothing.
- **Nothing else on the CM4 or the CPLD touches this path.** The CPLD test
  points land on a DNP header (`digital J15`), and the four `test[3:0]` pins
  are driven by the heartbeat logic, not by anything MEMS.

So: there was no cheaper read, and a real instrument *was* required — but the
instrument turned out to be the netlist, not the bench.

### 2 — is a CPLD counter genuinely required? No. A pin map fix is.

The counter was meant to separate "no PDM clock reaching the mic" from "mic
dead with the clock present". Both halves are already answered: **there is no
PDM clock, because there is no bit clock into the bridge that generates it**,
and the mic's state is unknown and unasked. A counter would add nothing.

What is required is the bring-up the design never had. Scoped, and
**feasibility-built in a scratch copy — nothing in the tree was modified and
nothing was flashed:**

```verilog
`ifdef DSP4_MEMS_PROBE
    output wire mems_bck,     // PIN_119, M_BCK -> U13.B2
    output wire mems_fs,      // PIN_120, M_FS  -> U13.C2
    input  wire mems_i2s,     // PIN_121, M_I2S <- U13.B1
`endif
...
    assign mems_bck  = bck8;
    assign mems_fs   = fs8;
    assign i_dspa[7] = mems_i2s;   // instead of `mems` (pin 137)
```

**No new counter: the DSP's own RX DMA is the instrument.** If `U13` is alive,
lane 7 stops reading `0xFFFFFFFF` in `dsp4_rxscan.py` — the tool used above,
already proven, needing nothing new.

| | |
|---|---|
| synthesis / fit / STA | successful, **timing met** |
| logic elements | **882 / 1,270 (69 %)** — the same count as shipping |
| pins | 72 / 114, was 69 |
| Fmax | **67.43 MHz** (shipping 66.58), against a 49.152 MHz sysclk |
| bus-fight check | `U3.119`/`U3.120` are the **only** active pins on `M_BCK`/`M_FS`; driving them fights nothing. Pin 137 falls back to the global unused-pin reservation and its net reaches no load. |

Evidence: `data/memsprobe-fit.summary`, `data/memsprobe-pins.txt`.

**It was not built into the tree, and that is deliberate — two rulings are
owed first.** See 🔴 S106-1 and 🔴 S106-2 below.

### 3 — the acoustic check on the mic: not tried, and here is why it could not have shown anything

Tapping the panel or holding a phone speaker to the capsule would have been
measured through `i_dspa[7]`, which is wired to an unconnected pin. No acoustic
stimulus can move a constant that comes from an undriven input — and with no
bit clock into `U13` there is no PDM clock at the mic either, so the capsule
is not converting in the first place. Running it would have produced a
confident negative about a microphone nobody has asked anything. It becomes a
real test the moment the probe bitstream is on the part, and it is the right
*second* test then.

### 4 — rails: not raised, and not needed

`AN_EN` (GPIO26) read `26: op -- pd | lo` at the start of this session and
`lo` at the end; it was never written. S103 §3.3 established there is no
AN_EN-gated rail anywhere in the MEMS chain, and this session reads a CPLD pin
map. Raising the rails would have been theatre. `CS_M` was `27: ip pu`
throughout, as S103 left it.

### 5 — the speaker-by-ear check: prepared, not run, needs PW at the bench

The dispatch says coordinate the moment rather than run it unannounced, and a
dispatched session cannot open a question. So the recipe is here, ready, and
it is a 🔴 for PW rather than something done behind his back.

It needs the `DSP4_TEST_NODES=1` pair — `/home/app/loopthd/s103` is still
staged and md5-matched — because `TEST_OSC`'s injection hook is inside that
guard. The pair booted right now is `candidate-s82`, the signed one, which
cannot be driven. So:

```bash
# 1. boot the test-node pair (twice, per boot_pair; SAFE 595 first)
cd /home/app/loopthd/s103
pinctrl set 7,9,10,11,22,23,25 a0 ; pinctrl set 6,24 op dh
python3 dsp4_boot.py --dir .
python3 dsp4_config.py --product d24 --chip 1
python3 dsp4_config.py --product d24 --chip 2
#    ... repeat the three lines above once more; stage 7 lands on cycle 2

# 2. assert the proven route (S102/S103), all of it checked on the text
python3 s89_set.py . $(for s in $(seq -w 1 32); do [ "$s" = 020 ] || echo Chan${s}MainOn001=0; done)
python3 s89_set.py . Chan020MainOn001=1 Chan020Mute001=0 Chan020Level001=f1.0:4 \
    Chan020Pan001=f0.5:4 Chan020CompOn001=0 Chan020GateOn001=0 \
    Chan020TubeOn001=0 Chan020EqOn001=0 Main001Level001=f1.0:4 Main001Mute001=0 \
    Mon001Level001=f1.0:4 Mon001Level002=f1.0:4

# 3. PW listens at the panel speaker while this runs
python3 dsp4_s49_osc.py --strip 20 --freq 1000 --level -20 --symdir .
#    ... and off again
python3 dsp4_s49_osc.py --off --symdir .
```

S103 measured that exact injection back at `−23.01 dBFS` RMS, `0.00016 %`
THD+N — the DSP half of the chain is proven. What is untested is
`analog U3.22 → C23 → SPKR → analog J59.12 = digital J42.12 → C82 → TS482
(digital U32) → SPKR0/SPKR1 → lswitch J1.6/7 → J2.1/2`, and one ear answers
it. **It does not close `SP1`** — `SP1`'s automated instrument is still `MM1`'s
microphone — but it is a real, independent data point on the analog output
stage, and it is free.

## 5. What this means for the two catalog rows

Not changed here — the runner and the catalog were not touched, and moving a
verdict on a row is the hub's call.

- **`MM1` FAIL is describing the design, not MW-D24-2.** S103-3 suspected it;
  this is the mechanism. The remedial line on the glass sends a technician to
  the panel ribbon first, which on the evidence available then was the right
  instruction and is now known to be a wasted trip. That text wants revising
  once the probe answers.
- **`SP1` NO DATA remains correct** and for a sharper reason than S103 had: its
  only instrument reads a pin that is not connected to anything.
- Nothing about either row should be read as a fault on this unit until the
  lane is brought up and re-measured.

## 6. Findings for the hub

### 🔴 S106-1 — implementing the fix renames the shipping bitstream label, and that is the hub's call

`build.sh`'s `SRC_HASH` covers `rtl/*.v` and `quartus/dsp4_logic.qsf`. Any
probe implementation — even one behind an `ifdef` that the shipping build
compiles out — changes both files, so the next shipping build comes out under a
**new label** while the part carries `d02d83b3cc22`. That is exactly the "two
bitstreams, one story about what is on the part" failure the flash log and the
hash-labelling doctrine exist to prevent, so it is not something to do quietly
in a dispatched session. The tree was left untouched; the change is a
~15-line diff, and it is ready when the hub says the word.

### 🔴 S106-2 — what part is `digital U13`, and what framing does it emit? The tree says two different things.

| source | says |
|---|---|
| `mx26 src/hw/d24-hw-ics.csv:12` | **ADAU7002**, "strap: TDM8 slot 5" |
| `shared/dsp4-logic/tdm-lines.csv:9` | **ADAU7302**, "strap 47K = TDM8 slot 5 (0R = I2S alt mode not used)" |
| `shared/dsp4-logic/slot-map.csv:54` | `A_I7,5,MEMS_TB` — **ADAU7302** TDM8 slot 5 |
| `rtl/dsp4_logic_top.v:88` | `// ADAU7302 TDM8 (slot 5)` |

Those are not the same device. The ball-out the netlist gives —
`VDD, GND, BCLK, LRCLK, SDATA, PDM_CLK, PDM_DAT` plus one strap on `R42` — is
an 8-ball WLCSP PDM bridge, and **whether it can place its output in TDM8 slot
5 at all, or only emit stereo I2S, decides the rest of the fix**:

- if it slots: `bck8`/`fs8` on pins 119/120 is the whole change and
  `i_dspa[7] = mems_i2s` lands in slot 5 as the slot map already claims;
- if it is stereo-only: LOGIC has to re-frame it, exactly as
  `dsp4_pcm_reframe.v` already re-frames the Pi I2S link into slots 0/1 of
  `A_I6` — and `slot-map.csv:54` is wrong and owes a contract bump.

**This session could not settle it**: analog.com blocks `curl` and `WebFetch`
from this machine (standing bench fact), and there is no datasheet for either
part in the Dropbox `_Matrix` store. It wants either a datasheet, or `R42`'s
fitted value read off the board, or PW's word on which part is actually
placed. The probe build above is framing-agnostic — it answers "does `U13`
emit anything when clocked" either way — so it does **not** have to wait for
this. The product fix does.

### 🔴 S106-3 — `strap_d32` reads HIGH on a D24, and the snake lane is the witness

`rtl/dsp4_logic_top.v:781` is `assign i_dspa[5] = strap_d32 ? snake_in : 1'b0;`.
On a D24 that should be a hard `0`, and lane 5 should read `0x00000000` the way
the Pi lane 6 does. **It reads `0xFFFFFFFF`** — which is `snake_in` (PIN_109,
the one pin carrying an explicit `WEAK_PULL_UP`), so `strap_d32` (PIN_70, the
S-MCU's `S4` personality line, documented PROVISIONAL and driven by firmware
that does not yet define it) is sitting high.

The consequence is not in the audio lane. It is that `snake_out` (PIN_110) and
`dac_main` (PIN_111) are **driven** rather than high-Z, and the S36 comment
beside them says the D24 case is exactly that they must be high-Z so that a
card fitted to option slot 2 owns its own lanes. Slot 2 is empty on this unit,
so nothing is fighting today. Fit a card and something will.

Not investigated further and not fixed — noted because the reading is in this
session's scan and would otherwise go past unread again.

### 🟡 S106-4 — the stale-symbol-map trap fired again, on purpose, and is worth one line

Run with `--symdir /home/app/loopthd/s103` against the booted `candidate-s82`
image, `dsp4_rxscan.py` prints **all three controls `[ok]`** and then a full
table of `0x00000000 STATIC` with `?` in the node column. The controls do not
catch a wrong map. The `?` names do, and they are the only thing that does —
worth a line in the tool's header the next time it is touched.

## 7. Unit as handed back

Nothing was changed. Every tool run this session was read-only.

| | |
|---|---|
| role | `d24-testui` **active**, `matrix-app` **inactive** — test mode, as found |
| `AN_EN` (GPIO26) | **never written**; `26: op -- pd \| lo` at start and at handback |
| `CS_M` (GPIO27) | `27: ip pu` throughout, never written |
| 595 chain | **not written** — the chain was left exactly as S103's SAFE handback left it |
| CPLD | **not flashed**; `d02d83b3cc22` confirmed on the part by design-ID read-back and left there |
| DSP pair | **not booted**; `candidate-s82` was already running and was only peeked |
| staged pairs | untouched; `/home/app/loopthd/s103` still present for the speaker check |
| runner / app / catalog / skin | not touched |
| `defs.lock` | unmoved at `defs-v2026.09.19.3`; no generated artifact changed, **no contract bump owed** |

## 8. What changed in the repo

| file | change |
|---|---|
| `MW/D24/DSP/s106/mems-lane-root-cause.md` | this report |
| `MW/D24/DSP/s106/data/rxscan-shipping-chip1.txt` | the full 47-lane scan, 32 reps, shipping bitstream + signed pair |
| `MW/D24/DSP/s106/data/memsprobe-fit.summary`, `memsprobe-pins.txt` | the scratch feasibility build's fitter output |
| `tasks.md` | dispatch block status |

No source, generator, def or bitstream was modified.
