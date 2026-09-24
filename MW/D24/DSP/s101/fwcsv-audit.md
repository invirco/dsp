provenance: AI-drafted 2026-09-24 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S101 — `defs/products/d24/fw.csv` audited and corrected

**Outcome in one line: `defs-v2026.09.24` is tagged and pushed. 31 of `fw.csv`'s 88 rows touched — 20 corrected
in place (2 of them renamed), 2 renamed and moved out of the DSP chip-select block, 9 added — and the audit found the CM4 GPIO numbers for SWD_EN1/EN3 that S100 recorded as
missing, which closes one of S100's two open questions.**

PW's two rulings were applied as given. Of the seven items on the known-gap list, four are now declared, two are
resolved as *not fw.csv gaps at all* (with the reason, and with where they are declared instead), and one — the
ILITEK touch controller — is traced to a named connector for the first time, one physical confirmation short of
closed. Nothing was guessed: every row's notes carry the source, and where a source says it is unsure, the row
says so too.

---

## 1. What changed in `fw.csv`

`fw.csv` is CRLF and stays CRLF: the edit was made in binary, split and joined on the file's own `\r\n`, with a
field-count assertion on every line and a guard that refuses any field containing a comma or a quote (the file's
own convention — the `BootLed` rows landed in `defs-v2026.09.22` use `;`, `:` and `-` and no commas). The diff is
53 lines in a 90-line file and touches nothing else; `git diff` shows no whitespace churn.

### 1a. The eight CS rows — PW's ruling 1 and 2

| row before | row after | why |
|---|---|---|
| `DSP,Dsp1,,B12,CS1` | `Dsp1` + notes | name is right; nothing recorded that **the CM4 asserts it on GPIO6** and H1S1 is `GPIO_Input` on all eight |
| `DSP,Dsp2,,C14,CS2` | `Dsp2` + notes | same, CM4 **GPIO24** |
| `DSP,Dsp3,,B14,CS3` | **`DSP,RdyDspA`** | **PW's ruling 1.** Not a select: DSPA's `SPI2_RDY` (`PB_05`) arriving as an input, working end CM4 **GPIO8**, 10K pulldown R34 on the card |
| `DSP,Dsp4,,B13,CS4` | **`DSP,RdyDspB`** | as above, CM4 **GPIO12**, pulldown R22 |
| `DSP,Dsp5,,C13,CS5` | `Dsp5` + notes | rev-A leftover, no part fitted; on this unit a proto wire carries CM4 CS5 (GPIO27) to the `CS_M` pad, so **driving it moves mic gain** |
| `DSP,Dsp6,,B15,CS6` | `Dsp6` + notes | the one genuinely idle select |
| `DSP,Dsp7,,C15,CS7` | **`SWD,SwdEn1`**, moved | **PW's ruling 2.** CM4-owned SWD channel select, CM4 **GPIO5** |
| `DSP,Dsp8,,H0,CS8` | **`SWD,SwdEn3`**, moved | CM4 **GPIO13** |

**Where CS7/CS8 went.** `fw.csv` has exactly one organising principle: it is a set of per-MCU pin maps, each
opened by an `MCU` row (`H1S1`, `H1S3`, `H1S4`). C15 and H0 *are* H1S1 pins, so the rows cannot leave the file
without deleting real pin declarations — what had to leave was the `Dsp1..Dsp8` chip-select block. They now sit in
their own two-row block at the end of the H1S1 section, after the ADC rows, under a new `Type` of **`SWD`**.

**The Type taxonomy, read before extending it.** The existing values are `MCU`, `SW`, `SWx`, `LED`, `LEDx`, `ENC`,
`END`, `DSP`, `MIC`, `CODEC`, `AD`. Inside an MCU section, `Type` names *the domain the pin talks to* — `DSP`,
`MIC` (the gain chain), `CODEC`, `AD` (this MCU's ADC). Nothing in that set covers a CM4 debug-mux control, so
`SWD` is the consistent extension rather than a new idea. Three things make it safe: every consumer whitelists
`MCU`/`SW`/`LED`/`LEDx`/`ENC`/`END` and skips the rest (`FwCsvHelper.GetMcuIds`, `FwCsvBackfill`,
`FwCsvMxAddSync`, `ProjectBuilder.Matrix`), so a new value creates no behaviour; `common/schema/fw.md` now
documents every value; and because nothing branches on it, a later rename by PW costs one `sed`.

### 1b. A correction S100 could not make, from the schematic mods log

S100's 🔴 S100-2 said a real test for CS7/CS8 "needs the CM4 GPIO numbers for SWD_EN1/EN3 recorded somewhere and
an SWD transaction the runner can issue, **neither of which exists today**". The first half is wrong — they were
recorded, in a place nobody had looked: `mx26 src/hw/d24-schematic-reference.md:186`, inside the `d24 digital
mods.pdf` re-hash log.

> "sheet 11 red note extended with the CS-repurpose proposal — wire spare stack **CS7/GPIO5 → SWD_EN1 +
> CS8/GPIO13 → SWD_EN3** so the CM4 owns SWD channel select (jumper-free MH1/ch3 flashing; GPIOs idle hi-Z
> preserve defaults; **PW confirmed CS5-8 are rev-A leftovers unused on rev C**)" — converted red → blue
> 2026-08-19, i.e. fitted.

And from the same log's `D24 DSP mods.pdf` entry: *"Blue on p3 (S MCU): box around **U7 pins 4/5 (PC15=CS7,
PH0=CS8)** … U7 fw must not drive PC15/PH0"*, with a same-day correction that **the proto wires were fitted on the
DSP board, not Digital**. That independently confirms `fw.csv`'s own `C15`/`H0` against the schematic, dates the
wires, and gives the rev-D proposal (route the ENs in Digital-board copper). All of it is now in the two rows'
notes. So of S100-2's three blockers only the SWD transaction remains — the GPIO numbers are no longer missing.

The archive supplies the hazard's mechanism, which the notes also carry: H1S1's `MX_GPIO_Init` once drove PC15/PH0
as **push-pull outputs HIGH**, and with the proto wires fitted *"that forces ch3 permanently selected and breaks
the CM4's SWD channel-select"* (`archive/tasks-archive-2026-08-20.md:363-371`; fixed 2026-08-19, and *"any future
firmware that drives them is a bug"*).

### 1c. Two more rows that carry a two-master hazard

Not on the gap list, but the arc found both on the unit and the rows said nothing:

- **`Reset`** — `!RST_D` is **one net in six places with no series resistor and no arbitration**
  (`MW/D24/HW/hardware-map.md:305-324`); the CM4 pulses it on GPIO16. A second push-pull driver on it is a
  hardware fault, and S90 withdrew a spec prerequisite that would have added one.
- **`MicGain`** — the CM4 also reaches the 595 latch pad through the CS5 proto wire on GPIO27 (D8 amendment), so
  **two masters exist on rev C**.

### 1d. `Psu1`–`Psu12` — named honestly, not named

The gap list asked for rail names "if the schematic/inventory makes it unambiguous". It does not, for any of the
twelve, and the correct fix turned out to be the opposite of naming them. Three independent findings:

1. **No source has the map.** PAD0–PAD11 → rail is absent from `fw.csv`, `d24-hw-inventory.csv`, `d24-io.csv`,
   `hardware-map.md`, `d24-signals*`, `d24-hw-pins.csv`, `d24-pwr-mcu-def.csv` and both repos' docs. The H1S1
   firmware build at `~/build-h1s1` configures 26 pins in `H1S1.ioc` and **not one of PA0/PA1/PA4/PB0/PB1/PB2/
   PC0–PC5 is among them**; no ADC peripheral is configured at all and `main.h` defines no `PAD*` macro.
2. **mx26's own generator already says so** — `build-d24-connector-status.py` printed *"which rail each channel
   measures is not declared in fw.csv"* on all twelve rows, with the outstanding action *"declare the rail per
   channel in fw.csv Notes"*.
3. **The sense lines are not connected.** `mx26 docs/d24-netlist-global.md:391-398`: `dig-dsp-a P[87-98] =
   PAD[0-11]`, labelled PSU-monitor sense on the DSP-side schematic, **all twelve N/C on the Digital board** —
   *"There is no PSU monitor path on rev C."* Netlist-confirmed 2026-09-11 in
   `docs/backlog-d24-schematic-errata.md:113-122`.

The one near-miss is `hardware-map.md:405-407`, which gives *sheet positions* ("IP 25-32 ×2 on PAD6/7; OP 1-8/
9-16/17-24/25-32 on PAD8-11; PAD0-5 on the bottom edge") — channel banks, not rails, and written before the N/C
finding. It cannot be turned into a rail map.

PW has already ruled on this exact temptation (`tasks.md:286`, S90's dispatch): *"the PSU-monitor ADC channels
PAD0–11 are NOT connected on this unit — do not test them; **do not infer rails from them**."* So all twelve rows
now carry the honest declaration — rail UNDECLARED, PAD0–11 N/C on rev C, no PSU monitor path, and the ruling —
which turns twelve silently-plausible rows into twelve that cannot mislead. That is the correction; a rail map is
a schematic job on rev D.

### 1e. Nine rows added

**Right panel MCU (`H1S3`) — the seven console signals on `digital J12 = rswitch J1` pins 2–8.** The gap list
called them "TB/MJ/TEMP pass-throughs"; the word pass-through describes the *connector* routing, not the
termination — every one lands on a real pin of the `SW_RIGHT` MCU already declared in `fw.csv`:

| row | pin | net | J1 pin |
|---|---|---|---|
| `CON,Talkback` | A13 | `TB_SW` | 2 |
| `CON,TalkbackLed0` | F6 | `TB_LED0` | 3 |
| `CON,TalkbackLed1` | F7 | `TB_LED1` | 4 |
| `CON,MiniJackDet` | C10 | `MJ_SW` | 5 |
| `AD,Temp` | A1 | `TEMP` | 6 |
| `CON,Blower` | A8 | `BLOWER` | 7 |
| `CON,Fan` | C9 | `FAN` | 8 |

Source: `mx26 src/hw/d24-hw-pins.csv:77` (`verify=0`) for the MCU pins, `src/hw/d24-hw-connectors.csv:102-103`
for the connector pins, `docs/d24-signals-index.md:2585-2636` per net. Corroboration that the MCU is the reader,
not a bystander: `docs/spec-d24-selftest.md:235-236` already specifies *"read MJ_SW **through the right panel
MCU**"* and *"read TEMP **through the right panel MCU** over the panel UART"*. `TEMP` comes from a sensor at
digital `U17.2`, so it is typed **`AD`** — the existing type for an analog input on this file — not a new one.
`TB_LED1` is silkscreened `TD_LED1` on the rswitch board (a typo, one net either way) and the row records that.
`d24-hw-connectors.csv:103` is flagged `verify=1` for `MJ_SW`/`TEMP`/`BLOWER`/`FAN` while `d24-hw-pins.csv:77` is
`verify=0`; those four rows carry the disagreement in their notes rather than picking a side.

Two of the seven — `BLOWER` and `FAN` — are not named in the gap list. They are the same `hw-pins` row, the same
connector group and the same two remaining pins of J1 2–8, so declaring five and leaving two would have left the
group half-mapped for no reason. Flagged here because it is a small widening of the brief.

**Left panel MCU (`H1S4`) — the P1 pedal UART.** `UART,PedalTx` on port `P44` (net `PDL_TX`) and `UART,PedalRx`
on `P45` (`PDL_RX`). The path is solid and multiply cited — `docs/d24-signals-index.md:1680-1702` (*"the pedal
UART is driven by the **LEFT SWITCH board's MCU**, not by the DSP card"*), through digital `U36`/`U37` LVDS to
`J8` (RJ45) pins 1/2 and 3/6, to `p1 J1`; `src/hw/d24-hw-connectors.csv:117-120`. **The `Mcu` field is left empty
on both rows on purpose**: `d24-hw-pins.csv:86` says *"exact MCU pins ambiguous"* and is flagged `verify=1`, so
the silicon pin behind P44/P45 is not resolved anywhere. The notes say exactly that. A row that records the net,
the direction, the connector and the hole is worth more than no row; inventing `PA2`/`PA3` would not be.

Three candidates the evidence ruled out, so nobody re-treads them: the **M MCU** (STM32G031) owns the panel UART
mux and the three option-slot UARTs, not the pedal; **H1S1** is not the pedal's UART (the "option UARTs" line in
mx26's workbook is a misattribution); and the **CM4** appears nowhere in the pedal chain. The pedal board's own
`STM32C031K4U6` belongs to P1, not to D24, and is out of this file.

New types `CON` (a console signal on this MCU's GPIO with no matrix cell) and `UART` (a serial link to another
board) were added for these, documented alongside `SWD`.

**Why none of these can be `SW` or `LED`.** `Talkback`/`MiniJackDet` are buttons and `TalkbackLed0/1` are
indicators, so `SW`/`LED` look right — and would break the app. `ProjectBuilder.Matrix.cs:507` raises a
**critical** on `SW` with an empty `Cell`, and `:535` on `LED` with neither a cell nor an `ENC` context. Binding
cells to these is the placeholder-cell question this dispatch put out of scope, so the rows must sit outside the
skin-control types until PW names cells. That is not a workaround: `Type` here means the domain, and `CON` says
the truth — a console signal on this MCU's GPIO that no cell is bound to yet.

---

## 2. Two gap-list items that are not `fw.csv` gaps

Both were on the list as "no row exists at all". Correct — and a row should not exist, because **neither path
touches an MCU pin anywhere**, and `fw.csv` is nothing but per-MCU pin maps. Both *are* already declared, in
`defs`, in the file that holds parts and connectors.

**The panel MEMS mic (U3).** `U3 IMP34DT05` is on the **Left Switch PCBA**, already in
`defs/products/d24/d24-hw-inventory.csv:1126` and `mx26 src/hw/d24-hw-ics.csv:57`. The chain is
`U3 → U1 SN65LVDS1 / U2 SN65LVDS2 → CLK0/CLK1 + D0/D1 → lswitch J1 = digital J13 pins 2/3 and 4/5 →
U30/U31 → U13 ADAU7002 → TDM8 slot 5 → DSPA DAI1 pin07`. The ADAU7002's slot select is a **resistor strap**
(`MEMS_CONFIG` via digital R42), not a driven line; `d24-hw-buses.csv:33` gives the bus endpoints as the bridge
chip and the mic. `grep -niE "MEMS|SPKR" src/hw/d24-hw-pins.csv` returns nothing, and neither panel MCU section
in `fw.csv` has a row on the path. There is no MCU pin to declare. (Do not confuse the live path with the
vestigial net also called `MEMS` — CPLD `U3.137 → digital J18 P26`, *"no digital-side load"*,
`d24-netlist-global.md:468-472`.)

**The speaker header (J2).** `J2` (JST `BM02B-ASRS-TF`, 4-pin) is on the same Left Switch PCBA, already in
`d24-hw-inventory.csv:1075` with nets `GND;SPKR0;SPKR1`. It is fed from digital `U32 TS482` (`d24-hw-ics.csv:17`)
over `digital J13 pins 6/7` (`d24-hw-connectors.csv:111`), whose input is a line-level feed from the AK4619 on
the analog board. The amp is 8-pin in its minimal BTL wiring with **no enable, shutdown or gain pin routed**, and
no MCU pin appears anywhere on the chain.

So the honest resolution is: leave `fw.csv` alone on both, and treat the hw inventory as their declaration. If PW
wants them in `fw.csv` regardless, that needs a non-MCU section — a structural change to the file, and his call,
not something to slip in under an MCU heading. Noted as 🔴 S101-1 below.

---

## 3. The ILITEK touch controller — a connector, named for the first time

S93 first reported *"NOT FOUND: no touch controller, touch-panel connector, or touch-USB path anywhere in the D24
design"*, then retracted it after PW found **the touch cable half-seated**; reseated, `lsusb` shows
`222a:0001 ILI Technology Corp. Multi-Touch Screen`. The hub left the real question open: *"either it missed the
touch cable's actual connector/board or misread what it had; find and declare the real path"*
(`tasks.md:212`, `mx26 docs/spec-d24-selftest.md:397-424`).

**It missed a connector.** S93 checked J28 (the TFT/HDMI FPC) and J27 (the EXT HDMI breakout) and the hub's
declared downstream ports. It never looked at **J10 on the D24 Digital PCBA**, which two independent sources
describe:

- `mx26 src/hw/d24-schematic-reference.md:186`, in the mods-log re-hash of 2026-08-15 — *"red note on sheet 1 —
  **J10 Molex 522710469 touch-USB connector**: find replacement."* Five weeks before S93.
- `defs/products/d24/d24-hw-inventory.csv:900`, netlist-derived and independent of that annotation —
  `D24 Digital PCBA rev C PCBA,J10,connector,6,GND;PI_HD1_N~P1;PI_HD1_P~P1;PI_VBUS` — VBUS, a D+/D− pair and
  GND, i.e. exactly a USB header, on the CM4's HD1 lines.

J28 is not it, confirmed twice: `d24-hw-connectors.csv:126` describes it as a transparent HDMI0 pass-through, and
`d24-hw-inventory.csv:917` lists only `HDMI0_*`/`PI_HDMI0_*` nets on it. Nothing suggests display and touch share
one flex; they are two connectors.

**What is still missing, precisely.** No session — including this one — has confirmed that **the cable PW reseated
is the one in J10**. That link is circumstantial here: a part label plus a matching pinout, not an inspection
anybody recorded. And `d24-hw-inventory.csv`'s `nets` column is capped at twelve entries per row, so the 100-pin
CM4 sockets J24/J25 cannot tell us where `PI_HD1_N/P` land on the CM4 side. Two sentences of work on the unit
would close both: look at J10, and follow its pair.

**No `fw.csv` row either way** — a CM4 USB port touches no MCU pin. When the path is confirmed, J10's home is the
hw CSVs (where it already sits) and a connector-status row, not this file. Also recorded and *not* a hardware
declaration: `mx26 docs/ref-d24-revA-os-baseline.txt:42-43` carries a udev rule naming *"ILITEK ILITEK-TP Mouse"*,
so the OS baseline has expected this device all along. The display and touch-panel part numbers are named nowhere
in either repo.

---

## 4. The tag, and what it contains

**`defs-v2026.09.24`**, commit `404669d`, pushed to `invirco/defs` `main` with the tag. `defs.toml [tags] current`
was bumped **before** the references were regenerated, as the reference records the declaration and not
`git describe`.

| file | change |
|---|---|
| `products/d24/fw.csv` | 20 rows corrected in place, 2 renamed and moved, 9 added — 31 of 88; CRLF and the 50-field padding preserved |
| `common/schema/fw.md` | new section documenting every `Type` value and the empty-`Mcu` convention |
| `defs.toml` | `current = "defs-v2026.09.24"` |
| `gen/matrix/d24-reference.md` | the new `fw.csv` sha256 and the tag |
| `gen/matrix/{d12,d16,d32,d64,d128}-reference.md` | regenerated; they were stale — `--check --all` reported five DRIFT before this run and six "up to date" after |

**No cell, address, matrix or master change.** `common/cells/mx_master.csv`, every product master and every
expansion are byte-identical; `d24-reference.md`'s only diffs are the `fw.csv` hash and the tag string. The five
catch-up references differ only by the tag string, except `d32-reference.md`, which also catches up on the
already-committed `gen/matrix/d32-wire-table.csv` sha and the wire-law columns that follow from it — that CSV is
**unchanged** by this session (`git diff --name-only | grep -c wire-table` → 0); its reference had simply not been
regenerated when it landed.

**`_Matrix` was not republished.** `tools/defs-publish.sh` writes the shared store and the dispatch did not ask
for it; whether `defs-v2026.09.24` should be published is PW's call.

**This spoke's pin did not move.** `dsp`'s `defs.lock` stays at `defs-v2026.09.19.3` and the submodule is back on
that commit, tree clean. Advancing it would pull in `defs-v2026.09.20`'s cell-master append (`Usb[1-1]HostSync`)
and require a full `regenerate-dsp-contract.sh` with matrix and DSP-address-map churn — a separate contract bump,
not part of this audit. The consequence to know: **the corrected `fw.csv` is live in `defs` and in `mx26`, and is
not yet visible to this repo's own tooling.**

`mx26` is pinned to the new tag (`a401198`), with `CLAUDE.md:33`'s pin text bumped.

---

## 5. The workbook reproduces, and it disagrees with the glass

`build-d24-connector-status.py` was updated so the H1S1 chip-select and PSU-monitor rows say what each net
actually is, and rebuilt. **The item names were deliberately left alone.** They are the acceptance keys —
`item-status.csv` is merged on `(board, item)` and an unknown key is a hard `sys.exit` — so renaming
`DSP chip-select CS3 (fw.csv Dsp3)` to match the new declaration would orphan the `DY1-RDY1` PASS S100 landed
against it. That is the same failure S100 fixed one level down, and it is not worth re-creating to make a label
prettier. The declaration appears in the **Board ref** column instead, where it is free.

Verified rather than asserted:

| check | result |
|---|---|
| `--export-keys` before vs after | **204 keys, byte-identical** |
| rebuild with the spoke's `item-status.csv` | `merged 60 tests over 36 items`, `rows: 204`, no key errors |
| status distribution before vs after | **identical** — 19 PASS / 3 FAIL / 5 BENCH FAULT / 26 PARTIAL / 143 UNTESTED-no-fixture / 8 UNTESTED-dead-section |

So the change is text-only and moves no verdict. (`openpyxl` was not installed on this machine and was installed
into `~/.local` to run the build; `~/Desktop/d24-connector-status.xlsx` does not exist here — the shipped workbook
is built on the hub, and this run wrote to a scratch path.)

**The finding that came out of rebuilding it**, which predates this session and is not caused by it: rows **105
and 106 read `PARTIAL` in the workbook while the unit's own glass reads `PASS`.** Both builds — with and without
this session's edit — give `(PARTIAL, 1 PASS, 0 FAIL, 2 NO DATA)` for each. The cause is exactly what S100 fixed
elsewhere: this generator has **no retired-test filter**, so `DC1-CS3`/`DC2-CS3`'s two superseded NO DATAs still
roll into the row's status, where `TestSkinStore.Entry.Covers` and `preview-d24-test-skin.py` now exclude them.
The app and the workbook disagree about the same two rows. See 🔴 S101-2.

---

## 6. Left open, flagged not guessed

**🔴 S101-1 — the MEMS mic and the speaker header have no MCU pin, so `fw.csv` has no home for them.** They are
declared in `d24-hw-inventory.csv` and the mx26 hw CSVs, which is where a part-and-connector declaration belongs.
Options, PW's call: (a) accept that as their declaration and strike them from the `fw.csv` gap list — what §2's
evidence supports; (b) add a non-MCU section to `fw.csv` for board hardware that no MCU drives, which changes the
file's shape; (c) something else. Nothing was added to `fw.csv` for either.

**🔴 S101-2 — the connector-status workbook rolls retired results into a row's status, so it disagrees with the
console.** Rows 105/106 read `PARTIAL` there and `PASS` on the glass. The fix is S100's `Covers` rule ported into
`build-d24-connector-status.py`, which needs a per-row list of the tests that still cover it — the catalog has a
`tests` column, this generator has nothing. Whose change that is, and whether the workbook should read the catalog
or be handed a retired-test set, is the hub's call. Not touched here: it moves reported verdicts.

**🔴 S101-3 — the ILITEK path is one physical check short.** §3 names J10 on two independent sources; nobody has
confirmed the reseated cable is in it, and the CM4 end of `PI_HD1_N/P` cannot be read from this repo because the
inventory truncates J24/J25's nets at twelve. Needs eyes on the unit, not more grepping.

**🔴 S101-4 — three new `Type` values are a taxonomy extension, and names are PW's.** `SWD`, `CON` and `UART`.
No consumer branches on any of them, so a rename is a `sed` in one file plus `common/schema/fw.md`.

**🔴 S101-5 — the silicon pin behind pedal ports P44/P45 is unresolved.** `d24-hw-pins.csv:86` says so and is
flagged `verify=1`. The two rows carry the net and the whole path with `Mcu` empty. Closing it means reading the
Proteus netlist or the lswitch schematic.

**Also open, no decision needed, just not in this session's scope:** `products/d32/fw.csv` carries the same eight
`Dsp1..Dsp8` rows and the same twelve unnamed `Psu1..Psu12` rows. The DSP4 card is shared, so `CS3`/`CS4` and
`CS7`/`CS8` are very likely the same signals there — but D32's Digital board and panel are not D24's, no D32
evidence was gathered, and guessing across a product boundary is how this repo got into trouble before. It wants
its own pass.

**Untouched as instructed:** the right/left panel placeholder-cell binding (`Sys001Skin001`/1195) is exactly as
found.

## 7. Files

| repo | file | change |
|---|---|---|
| defs | `products/d24/fw.csv` | the audit — 20 rows corrected in place, 2 renamed and moved, 9 added |
| defs | `common/schema/fw.md` | the `Type` glossary and the empty-`Mcu` convention |
| defs | `defs.toml` | `current = "defs-v2026.09.24"` |
| defs | `gen/matrix/*-reference.md` | all six regenerated; `--check --all` green |
| mx26 | `defs` submodule, `CLAUDE.md` | pin → `defs-v2026.09.24` |
| mx26 | `tools/d24/build-d24-connector-status.py` | H1S1 CS and PSU row text follows the corrected declarations; item keys unchanged; STAMP bumped |
| dsp | `MW/D24/DSP/s101/fwcsv-audit.md` | this report |
| dsp | `tasks.md` | the dispatch block's outcome |
