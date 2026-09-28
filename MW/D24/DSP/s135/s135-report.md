provenance: AI-drafted 2026-09-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S135 — the H1S3 talkback image, built and diffed at the desk (nothing flashed)

Hub ruling on S134 §7: S131 ships `Sys001SwTalk001` **declared but unbound**
(option 2), and option 1 is prepared here as a separate, optional H1S3 image
that PW can decide on at the bench tomorrow.

Two `.shex` images were built:

| variant | what it is | `.shex` md5 | text / data / bss |
|---|---|---|---|
| **A** | the runbook's step-5 mechanical build — `Sys001SwTalk001` in `MATRIX[]`/enum, nothing bound | `f21480b56744f4b2a4ca775d0ebd92fb` | 20576 / 1212 / 2068 |
| **B** | A **+ the talkback logic** | `f0bacb7bfb91f036e50b8f5987daf255` | 20932 / 1216 / 2080 |

Both are in `gen/H1S3-A/` and `gen/H1S3-B/` with their `matrix.cs` and `.hex`.
The A→B source diff is `gen/matrix.cs.A-to-B.diff` (one file, `Core/Inc/matrix.cs`).

**Nothing was flashed, deployed, written or configured.** Everything on the unit
was read-only: an `rsync`/`scp` of `/home/app/fwbuild/H1S3/`, `hex2shex.py`, the
`MH1` source and the flash logs down to this machine, and `pinctrl get`. Both
builds ran here, with `arm-none-eabi-gcc (15:14.2.rel1-1) 14.2.1` — the same
version S129 and S134 used on the unit. Unit state at the end, unchanged from
S134: `app` `b05e9fd55e15289e6529f66c72778e33`, GPIO26 (AN_EN) `lo`, GPIO27
(CS_M) `hi`, `matrix-app` inactive, `d24-testui` active, no scratch tree left
behind.

---

## 1. The build environment is proven, not assumed

Before either variant, the **unmodified** source was rebuilt here from scratch
(all `.o`/`.elf` removed, only S129's one-line Windows linker-path fix applied
to `Debug/makefile`):

```
text 20572  data 1212  bss 2068          <- identical to the flashed image
H1S3.hex md5 e6cfb316a51e8523f09e7c8af945569f
```

`e6cfb316…` is byte-for-byte the `Debug/H1S3.hex` that sits beside the
currently-flashed `H1S3.elf` (md5 `73d0937d150e0cf7f747619c411c8ce4`, the value
S129 recorded). So this machine reproduces the running image exactly.

Variant A then came out at `text` 20576 (+4) with `.shex` payload **identical**
to S134's own dry-run variant A (`ef89709f…`; the only difference is the header
record, see §4). Two independent machines, same bytes.

---

## 2. What the talkback logic does

`Sys001SwTalk001` = 5006, bus address `ikpv`, cell note from
`MW/D24/MX/_matrix.csv` (defs `defs-v2026.09.27.3`):

> WRITE is the two-indicator mask: bit0 = TB_LED0, bit1 = TB_LED1, so 0 = both
> dark, 3 = both lit. READ is the switch: 1 while it is held, 0 when it is
> released, and both edges are reported.

Pins from `defs/products/d24/fw.csv` (`SW_RIGHT`): `TB_SW` = **PA13**,
`TB_LED0` = **PF6**, `TB_LED1` = **PF7**, all three through this panel
processor. All three already exist as `#define`s in `Core/Inc/main.h` and are
already brought up by `MX_GPIO_Init()`; no `.ioc` change was needed.

Neither half fits `rsw[]`/`wled[]`, which is exactly what S134 §7 said:
`WrRadioLed()` lights on **equality** (one-hot, can never light both) and
`RdRadioSwitch()` only acts on press and never returns `TXD` to 0 on release.
So the three pins are deliberately **kept out of those tables** and two new
functions handle them:

**`WrTalkbackLeds()`** — reads `matrix[pSys001SwTalk001][RXD] & 0x03` and drives
the two pins **bitwise**: bit0 → PF6, bit1 → PF7, `SET` = lit. HIGH = ON is the
polarity every other indicator on this board uses (`WrRadioLed()`/`WrEncLed()`
both drive `GPIO_PIN_SET` for the bright state). The pins are configured
`OUTPUT_PP` once in `MainInit()` and left that way — unlike the radio LEDs they
are never reconfigured at scan time — and the function only touches them when
the mask actually changes. `0` drives both **low**, i.e. dark, not the
"convert to input for dim led" state the radio LEDs use for unselected, because
the cell note says *dark*.

**`RdTalkbackSwitch()`** — samples PA13 (LOW = held, the same sense as every
`rsw[]` entry, which is what the `GPIO_PULLUP` boot config gives), debounces
with a **20 ms** stable-level window off `HAL_GetTick()`, and on each settled
edge — press *and* release — writes the new level into `TXD` and raises `TXF`
so `Poll()` sends it. An edge is handed to the cell only once the previous one
has drained (`TXF == 0`); a later edge replaces a waiting one. That costs a
possible intermediate state on an impossibly fast double-tap and buys the
property that matters on a talkback key: the host can never be left believing
the switch is still held.

`Eol()` needed **no** change — its generic address scan already stores the
host's write into `RXD` once the cell is in `MATRIX[]`.

Two deliberate choices, both documented in the source:

* **the indicators do not follow the switch and do not blink.** They sit
  outside the `ledFollowSw` branch and are absent from both blink lists, so
  they are host-driven at all times.
* **a talkback press does not set `ledFollowSw`.** Every `rsw[]` press does,
  which would end blink mode for the whole panel — a side effect on *other*
  indicators, which the dispatch's "byte-for-byte unchanged in its effect"
  rules out.

### the release message carries no data character

This is protocol behaviour, not a quirk of this change, but it is worth knowing
before reading a bus log: `Poll()` only emits a data nibble when `TXD` is
non-zero, so the release arrives on the wire as `ikpv\n`, with the press as
`ikpv1\n`. The host reads it as 0 — `Boot.Protocol.cs`'s `Eol()` resets
`rxDataByte` to 0 after every line and writes that value when no data nibble
was parsed. Every other cell's zero behaves the same way.

---

## 3. B differs from A only in the talkback code — proved at the map level

`gen/matrix.cs.A-to-B.diff` is the whole source difference: one file, six
hunks, all additive. No existing line is modified or deleted.

Symbol-level (`data/symbol-compare-A-vs-B.txt`, produced by `data/fncmp.py`,
which disassembles both images and rewrites every literal and branch target
back to a symbol name so the comparison survives the address shift):

```
functions in both: 150; differing: 2 -> ['MainInit', 'MainLoop']
only in B: ['RdTalkbackSwitch', 'WrTalkbackLeds']
only in A: []
```

So of 150 functions, **148 are instruction-identical including every symbol
they reference** — `RdRadioSwitch`, `RdRadioSwitches`, `WrRadioLed`,
`WrRadioLeds`, `WrEncLed`, `WrEncLeds`, `TestEnc`, `Poll`, `Eol`, `Uart1_Int`,
`MX_GPIO_Init` and the rest. The two that differ are the two the diff touches.

The size accounts for itself exactly:

| | bytes |
|---|---|
| `RdTalkbackSwitch` (new) | 184 |
| `WrTalkbackLeds` (new) | 104 |
| `MainInit` 148 → 208 (the indicator pin init) | +60 |
| `MainLoop` 208 → 216 (the two new calls) | +8 |
| **total** | **+356 = `text` 20576 → 20932** |

`data` +4 is `tbLedMask` (initialised non-zero); `bss` +12 is the other five
variables plus alignment. No symbol was removed and no other symbol changed
size. Both variants compile with exactly **one** warning, the pre-existing
`-Wpointer-sign` in `UART1_Read()` at `Core/Src/main.c:71` — B adds none.

---

## 4. 🔴 FOUND WHILE BUILDING, AND IT AFFECTS TOMORROW'S WINDOW: the `.shex` MCU id is crossed, and it picks the socket

The header record of a `.shex` is not decoration. `MH1` parses it:

```c
myHS = GetCharHexByte(myRXstring[4], myRXstring[6]);   // ':02H1S4...' -> 0x14
...
S_Boot[(myHS & 0xf) - 1]();                            // -> S_Boot[3] = SB4
```

**It selects which slave socket gets reset, erased and written.** And the images
running on the unit right now are crossed:

```
/home/app/firmware/H1S1.shex     :02H1S1040800CS
/home/app/firmware/H1S3.shex     :02H1S4040800CS      <-- right panel, socket 4
/home/app/firmware/H1S4.shex     :02H1S3040800CS      <-- left  panel, socket 3
```

Each file holds the payload its **filename** says — proved by rebuilding both
from `/home/app/fwbuild/H1S3/` and `/home/app/fwbuild/H1S4/` here: each rebuilt
`.shex` differs from the deployed one **on line 1 only**. So the source-tree
names `H1S3`/`H1S4` do not match the hardware slave sockets, and the working
images compensate in the header. The 2026-08-19 session that produced them shows
it directly (`data/shex-mcu-id-evidence.txt`): one combined stream, records
1–1363 under id `H1S4`, records 1364–2286 under id `H1S3`, 2287 records total.

**The runbook's step 7 as S134 wrote it would get this wrong.**
`python3 hex2shex.py H1S3.hex H1S3 H1S3.new.shex` stamps id `H1S3`, which sends
the right-panel firmware to socket 3 — the left panel — and the left panel's to
socket 4. Both panels would come back wrong from a flash that reports success.
S134's own archived dry-run images under `MW/D24/DSP/s134/gen/` carry the same
wrong ids; they were never flashed, so nothing came of it.

Step 7 in `s131-runbook.md` is corrected accordingly, and **both H1S3 images in
`gen/` here are stamped `H1S4`**, matching the image that is working on the unit
today. Their payloads are unaffected: A's payload is identical to S134's.

`gen/H1S4/H1S4.shex` (md5 `8540b6ad39530d6696763ef14c656a40`) is added for the
same reason — S134's step-4 payload, unchanged, restamped with id `H1S3` so the
left panel's own image does not carry the hazard either. S134's `H1S1.shex` id
was already right and is left alone.

---

## 4a. 🔴 Also found, also not fixed here: the bench tools carry the old addresses

`tools/pi/d24_panel.py` hard-codes `SKIN = 0x1524` (5412) and `ENC = 0x1470`
(5232). After the switch-over those are **4698** (`0x125A`) and **4514**
(`0x11A2`); `SW_LEFT` = 5005 is the only one that survives. The file's own
comments anticipate the move and the constants were never made to follow it, so
from the moment step 8 completes the tool writes and reads addresses no panel
answers on — and that tool is step 10's panel check and the self-test's entire
panel station, step 5b's talkback check included.

Not changed here: outside this dispatch, and the choice between hard-coding the
new literals and having the tool read them from the pack is the hub's, has to
go out through `deploy-bench-tools.sh`, and has to be proved on the part.
Recorded in the runbook as §6a, to be done **before** step 10. `Sys001SwTalk001`
= 5006 (`0x138E`, `ikpv`) needs adding at the same time if step 5b is taken.

## 5. What is left for PW

Step 5b of `MW/D24/DSP/s131-runbook.md` has the bench check and the rollback.
In one line: flash variant B instead of A, press and hold talkback and watch the
host see 1 then 0 on release, write 1 / 2 / 3 to `Sys001SwTalk001` and watch
LED0 / LED1 / both, and if anything is off, flash variant A — which is the
unbound image the window ships by default — or the `.bak-s131-pregen` image.

Not proved here, and it cannot be from the desk: that PA13 really does read LOW
when the button is held, and that PF6/PF7 really do light their own indicator
rather than each other's. Both come straight from `fw.csv` and the netlist, both
are one bench press to confirm, and both are exactly why this is an optional
image and not part of the mandatory path.
