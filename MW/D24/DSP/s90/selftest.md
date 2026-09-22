provenance: AI-drafted 2026-09-22 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S90 — D24 self-test, section 1: built, run on the rev C unit, landed

`~/mx26/docs/spec-d24-selftest.md` tests A–C built as one runner, run on
MW-D24-2 as found, results appended to `MW/D24/DSP/accept/item-status.csv` in the
shape the hub's workbook generator ingests. PW's brief: *"we need everything
testable, on the sheet."*

The instrument is `tools/pi/d24_selftest.py`, with `tools/pi/d24_bus_probe.py`
for the two matrix-bus reads no existing tool did. It runs on the dsp machine and
drives the unit's CM4 over SSH. The read-path inventory it was built from is
`readpaths.md`, committed before a line of the runner was written.

## 1. The verdicts

**19 PASS / 1 FAIL / 16 NO DATA over the 36 workbook rows** — 58 tests, one row
per test per item, all 36 rows covered. Nothing was skipped and nothing was
softened: every NO DATA names the prerequisite that would close it.

Verdict roll-up is per workbook item and takes the WORST verdict across that
item's tests — a FAIL is not cancelled by a PASS on another test of the same row.

### A — from the CM4

| test | verdict | measured |
|---|---|---|
| HD0-1 | **PASS** | HDMI-A-1 `connected`; EDID parses — manufacturer `RTK`, product code `10811`, display name `RTK FHD`, serial `J257M96B00FL`; native mode `1920x1080` and it is the active CRTC mode |
| HD0-2 | **PASS** | `connected` on 61 of 61 samples over **3600 s**, **0 DRM hotplug uevents**. (The first attempt read the same thing over 3540 s and reported itself short — see below) |
| HD-PWR | **PASS** | inferred from HD0-1, and said to be inferred rather than measured |
| NW1 | **PASS** | `Link detected: yes`, `Speed: 1000Mb/s`, `Duplex: Full`, `carrier=1` |
| NW2 | **FAIL** | `rx_dropped` +2 across NW3+NW4; every other counter 0. Idle control, 30 s with nothing driving the link: all zero |
| NW3 | **FAIL** | worst of 3 passes each: bench host 1.0 % loss `[0.0, 1.0, 1.0]`, max RTT 0.703 ms; gateway 1.5 % loss `[0.0, 0.0, 1.5]`, max RTT 13.398 ms |
| NW4 | **NO DATA** | unit rx 94 Mbit/s, unit tx 94 Mbit/s — the driving host's `ens9` negotiates **100 Mb/s**, so the number is the path's, not the unit's |
| AS-CM4 | **PASS** | `throttled=0x0`, `temp=56.9'C`, `volt=0.9200V`, `Raspberry Pi Compute Module 4 Rev 1.1`, `matrix-app` active |
| USB-HUB | **PASS** (no workbook row) | the CM4 hub enumerates; a device on a port is section 2 |

### B — through H1S1 over the matrix bus

| test | verdict | measured |
|---|---|---|
| ML1 | **PASS** | `Sys001Test001` (5414) × 3 → `0x00, 0x00, 0x00` at 111.1 / 110.4 / 110.4 ms — three identical, well-formed answers |
| ML2 | **NO DATA** | no version cell in H1S1; host side `H1S1.shex` md5 `5dc7acdea662f9153b09b816f9ae76b2` |
| ML-M | **PASS** | ML1 answered, so MH1 dispatched it; S_TEST returns `// H1S1 DSP`, `// H1S3 SW Right`, `// H1S4 SW Left` |
| ML-P1 | **PASS** | `// H1S3 SW Right` on S_TEST, and in `matrix-app`'s own `MCU verified:` lines |
| ML-P2 | **PASS** | `// H1S4 SW Left`, likewise |
| ML-B0 | **NO DATA** | no BOOT0/NRST drive exists on H1S1 (prereq 6) |
| DC1 CS1 | **PASS** | CS1 asserted (GPIO6): `CHIP_ID 1`, `BUILD_ID 0x20260812` |
| DC1 CS2 | **PASS** | CS2 asserted (GPIO24): `CHIP_ID 2`, `BUILD_ID 0x20260812` |
| DC1 CS3/CS4 | **NO DATA** | not chip selects — SPI_RDY inputs; levels read `GPIO8 ip pu hi`, `GPIO12 ip pd hi` |
| DC1 CS5–CS8 | **NO DATA** | no part behind them on DSP4 |
| DC2 CS1 | **PASS** | `CHIP_ID 1`, `BUILD_ID 0x20260812`, build-cfg triple `0xCF45FF10 / 0xE2018E6F / 0xC47C0F26` — the S82-signed pair |
| DC2 CS2 | **PASS** | `CHIP_ID 2`, same triple |
| DC2 CS3–CS8 | **NO DATA** | as DC1 |
| DR1 | **PASS** | `FRAME_COUNT 8747 → 13198` advancing; after `!RST_D` (GPIO16) low 50 ms the part does not answer at all |
| DR2 | **PASS** | boot+config ×2: `BOOT_STAGE 7/7`, `BUILD_ID 0x20260812` both chips, 29 lanes CARRYING |
| MC1 | **PASS** | wrote `05 09 0D … 5D 61 00`, read back `VERIFIED 200/200` identical |
| MC2 | **PASS** | wrote SAFE `01 ×24 + 00`, read back `VERIFIED 200/200` identical |
| MC3 | **PASS** | MC1's read-back is not all-zeros, so the guard was not invoked; CS_M `GPIO27 ip pu hi` |
| CC1 | **PASS** | `05H = 0xBB` — exactly the `StartAK4619()` image, MGN2L/MGN2R both +27 dB |
| CC2 | **PASS** | `05H 0xBB → MGN2R 5 → 0xB5 → restored 0xBB` |

### C — from the DSPs

| test | verdict | measured |
|---|---|---|
| AS-DSPA | **PASS** | `CHIP_ID 1`, `BUILD_ID 0x20260812`, `BOOT_STAGE 7`, `FRAME_COUNT 11142 → 15573` (Δ 4431 in 1 s), 28/47 RX entries CARRYING |
| AS-DSPB | **PASS** | `CHIP_ID 2`, `BOOT_STAGE 7`, `FRAME_COUNT 23949 → 28785` (Δ 4836) |
| AS-CPLD | **NO DATA** | design id unreadable under the `dsp4-pcm-slave` overlay; `BLK_OVERRUN` delta over 10 s = **0 on both chips** |
| AS-ADC | **PASS** | lane 0 (U15) 8/8 CARRYING, −117.7…−115.0 dBFS; lane 1 (U39) 8/8, −119.2…−114.6; lane 2 (U60) 8/8, −119.5…−113.8; lane 3 (strips 25-32, NET-only) 0/8, −186.6 |
| AS-DAC | **NO DATA** | `_tx_out_slot_C2_MON_OUT` captured coherently, 256 contiguous samples, all non-zero — but no stimulus exists on a shipping image |
| AS-PWR | **NO DATA** | no reader for the power MCU's published words; AN_EN (GPIO26) `lo` |
| MM1 | **NO DATA** | the one MEMS lane is STATIC `0xFFFFFFFF` with AN_EN `lo` |
| SP1 | **NO DATA** | no TEST_OSC → SPKR route exists in the topology |

**HD0-2 took two goes, and the first shortfall was the runner's, not the unit's.**
The sampler took 60 samples at 60 s, which SPANS 3540 s, and the harvest reported
itself 60 s short rather than rounding up — the right behaviour from the wrong
code. Fixed: the sampler takes one extra sample so the span is the window that
was asked for, and the duration is read off the log's own timestamps rather than
multiplied out of a sample count, which is the kind of assumption a soak exists
to avoid. The re-take is the landed row — **61 of 61 samples `connected` over a
full 3600 s with the DRM hotplug count unmoved** — and it supersedes the short
one in the CSV by stamp, the way the results contract intends. Both readings are
kept. The row is owed a 24 h run for a shipping proof either way; that is the
spec's own bar, not a shortcoming of this one.

Every section-C reading was taken through a boot whose inter-chip link gate
(`s89_signbit.py`) read **CLEAN on both lanes** — lane 0 sent bit31 42/64 and
received 32/64, lane 1 sent 29/64 and received 31/64. That gate matters: the
framing folds on about one boot in seven and nothing in the SPORT registers shows
it (S89-1), so an ungated reading is 10–20 % likely to be silently wrong.

## 2. What the run cost the unit, and what it did not

Every bench rule the dispatch carries is enforced by the runner rather than
remembered by whoever runs it, which is the only version that survives the second
session:

- **The shipping CPLD `d02d83b3cc22` stays in flash.** Nothing in section 1
  flashes a bitstream. That has a price, paid in AS-CPLD.
- **`~/dspboot/candidate-s82` is never booted from** — the images are copied to
  `/home/app/s90` and booted there; the candidate's md5s are unmoved.
- **AN_EN is never written.** GPIO26 was `lo` at the start and is `lo` at the
  end; the runner reads it and records it, because raising it is the hub's
  (bench note 19 / S49-15).
- **The 595 chain goes back to SAFE LAST**, after the final DSP boot.
- **The loop cable was not moved or assumed.** No section-1 test needs it.

## 3. Six findings

### 3.1 The chip-select and reset prerequisites are not missing features — they are features that must not be built

The spec's prerequisites 2 and 3 ask for an H1S1 command to assert CS1–CS8 and
one to pulse `!RST_D`. Both would put a second driver on a bus the CM4 owns.

`~/build-h1s1/Core/Src/main.c:362-381` configures all eight CS pins as
`GPIO_MODE_INPUT`, under a comment that is not ambiguous:

> ALL EIGHT CS pins (CS1-CS8) are OWNED BY THE CM4 — this MCU must never drive
> them. The CM4 masters the DSP SPI/boot bus directly; H1S1 only monitors. […]
> The commented-out DspTx(…CS1-CS8…) calls in stm32u5xx_it.c must stay commented
> for the same reason.

That is DSP4 architecture decision D1 written into the firmware. `!RST_D` is
worse: the net was traced end to end on 2026-08-21 (`hardware-map.md:305-324`) —
**six places, no series resistor anywhere, two potential masters and no
arbitration**. U7 PA13 is unconfigured and has never driven it, so today there is
exactly one driver. Building the spec's command would add a second push-pull
driver to an unisolated reset net, to duplicate something the CM4 already does.

**Neither test needed the firmware.** DC1, DC2 and DR1 all ran in this session
from the CM4, on `dsp4_boot.py`'s own map (CS1 = GPIO6, CS2 = GPIO24,
`!RST_D` = GPIO16). DR1's reading is sharper than the spec asked for: after the
pulse the part does not answer the parameter link at all, which is a stronger
witness than a frozen counter.

### 3.2 Six of the eight chip-select rows can never answer on this board

`hardware-map.md:410-411`: *"CS1-8 DSP chip-select provision (8-DSP scaling —
only CS1/CS2 live on DSP4; CS3/CS4 wired as DSP1/2 SPI_RDY)"*. CS3 and CS4 are
**inputs** carrying SPI_RDY back from the two parts, and CS5–CS8 reach no fitted
part. An assert-one-read-one test on those six is not a NO DATA waiting on a
prerequisite — it is a test with no possible subject, and it will sit in the
section-1 count forever unless the workbook reclassifies the rows.

Smaller and related: `fw.csv` `Dsp1`..`Dsp8` declare a pin and a net, **not a
part number**, so DC2's "id matches the declared part" has nothing to match
against. What CS1/CS2 can prove — and did — is CHIP_ID, BUILD_ID and the signed
build triple `0xCF45FF10 / 0xE2018E6F / 0xC47C0F26`.

### 3.3 The panels are peers on the bus, and enumerating them was already free

The spec routes ML-P1/ML-P2 through "the panel UART mux" on H1S1. There is no
such mux, and H1S1 has one UART, used solely for the matrix bus. H1S3 (SW_RIGHT)
and H1S4 (SW_LEFT) are peer MCUs on MH1's bus — `defs/products/d24/fw.csv:26,66` —
each holding its own `testMessage[]`, and `S_TEST` makes all three answer at
once. `matrix-app` has been logging exactly that on every boot all along:

```
MCU verified: // H1S1 DSP
MCU verified: // H1S4 SW Left
MCU verified: // H1S3 SW Right
```

So enumeration costs nothing and is proved. Only the VERSION is missing, from all
three.

### 3.4 ML2 cannot be closed by a version cell alone — the other side of the comparison is stale by construction

The spec wants the H1S1 version cell compared against *"the version in
`/home/app/firmware/H1S1.shex`'s manifest"*. There is no version cell (prereq 1),
but the manifest side does not work either, and that is the part nobody had
noticed:

```
deploy-manifest.txt (generatedUtc=2026-08-18):  779c5665f9992fbf814eeed2043d9280  95552B  firmware/H1S1.shex
the file on the unit today:                     5dc7acdea662f9153b09b816f9ae76b2  100216B  dated 2026-09-20 10:41
```

The manifest is the **deploy-time** record and does not track firmware flashed by
hand afterwards — which is exactly what S69 and S81 did through
`app cli loadfw H1S1`. So the app is reporting an md5 for an H1S1 pack that has
not been on the unit since 2026-09-20, and would go on reporting it whatever got
flashed next. Landing a version cell without fixing this leaves ML2 comparing a
live value against a stale one, which is worse than comparing nothing.

### 3.5 The unit drops about 1 % of a 5 Hz ping, and it is matrix-app, not the Ethernet

NW3 failed, and the first instinct — blame the cabling to the driving host — is
wrong. Two controls settle it.

**Control 1, the target.** The unit's own default gateway is one switch hop away
and shares none of the driving host's cabling. Loss appears toward BOTH:
worst-of-3 1.0 % to the bench host, 1.5 % to the gateway. So it is not the path
to this machine.

**Control 2, the load.** With `matrix-app` stopped, **6 of 6 passes read 0.0 %
loss** — three to the gateway, three to the bench host — and the max RTT to the
bench host fell from 0.703 ms to 0.624 ms. Load average goes from ~1.0 with the
app running to 0.04 with it stopped, on a four-core CM4.

So the ICMP loss tracks the application, not the link. Everything else about the
Ethernet is clean: NW1 reads 1000Mb/s Full, the interface's own error counters
are zero, and NW4 reaches 94 Mbit/s each way, which is line rate for the 100 Mb/s
path it was measured over.

The landed verdict is still **FAIL**, because the criterion is about the unit as
it ships and the unit as it ships loses packets. But the row should be read as
"the CM4 drops ICMP under matrix-app's load", not "the RJ45 is bad", and it wants
someone to look at what that thread is doing rather than at a cable.

**NW3 also taught the runner something.** Five consecutive one-shot passes early
in the session read 2.0 %, 0.5 %, 0.0 %, 0.0 % and 0.5 % on the same path. A
single 200-packet run does not settle a 0 % bar here, and re-running until it
passes is not a measurement — so NW3 now takes three passes per target and scores
the **worst**, which makes the reading reproducible in the only sense that counts:
it does not improve if you run it again. The same restraint applies to NW2's
FAIL, which was NOT re-taken for a better number: `rx_dropped` +2 across the test
window against 0 in the idle control is the reading, and the likeliest benign
explanation — packets arriving with nothing to deliver them to, during the
`iperf3` teardown — is plausible and unproven, so the verdict stands as the
criterion gives it.

### 3.6 U15's lanes are alive; it is the front end that is absent

AS-ADC's per-converter grouping puts a number on what S86 concluded: **all eight
of U15's lanes carry a real dithered noise floor at −117.7…−115.0 dBFS, the same
as U39's and U60's.** The converter is converting. What MW-D24-2 has not got is
the front end for those eight channels — panel mics 1-4 and 13-16, XLRs J15-J22,
preamps U17-U31. The lane-level test cannot see a missing preamp and should not
be asked to; it says the converter and its link are fine, which is exactly the
question AS-ADC and `Link 'dig-analog-adc'` ask.

Lane 3's eight entries read a STATIC `0xFFFFFFFF` and that is also not a fault:
input strips 25-32 have **no analog source on a D24 at all** — they are NET-only
(`hardware-map.md`, D2 slot map).
## 4. The runner

`tools/pi/d24_selftest.py` — one leg, run on the dsp machine, driving the unit's
CM4 over SSH. `tools/pi/d24_bus_probe.py` runs on the CM4 and supplies the two
matrix-bus reads no existing tool did.

### 4.1 What is new, and why it is not a wrapper

Nine of the twenty-nine tests are compositions of existing instruments and the
runner adds nothing to them but a verdict rule. The parts that ARE new are the
parts where the obvious implementation would have produced a plausible wrong
answer, and each earned its code the hard way — by producing that wrong answer
first, in rehearsal:

- **ML1's read.** The spec asks for one H1S1-local cell read three times. No tool
  did that: `codec4619.py --read` issues a codec SPI transaction, which would
  have conflated ML1 with CC1 and put unasked SPI on the copper the CM4 boots the
  SHARCs over. `d24_bus_probe.py --mode cell` uses `CodecPoll()`'s `0xFB`
  sentinel — hand back the guard byte — which touches no SPI at all and answers
  on the ADDRESS cell, never on the trigger cell. Three round trips, 110.4 /
  110.4 / 111.1 ms, identical values.
- **NW4's direction.** The spec's `iperf3 -c <bench host>` needs an inbound port
  on the driving machine; this one runs `ufw` with `deny (incoming)` and only
  22/tcp. The first rehearsal reported "no receiver line" — the honest output of
  a blocked port and an indistinguishable one from a dead NIC. The server now
  runs on the unit. **And `pkill -f "iperf3 -s"` matched the shell running that
  very command**, so the launcher killed itself before launching anything and the
  test read as a network failure; it is `pkill -x iperf3` now.
- **NW4's and NW3's path gates.** See §3.4 — the bar is about the unit only if
  the path can reach it.
- **HD0-2's hotplug count.** `udevadm monitor`'s banner's second line begins
  `UDEV - the event which udev sends out…`, so `grep -c "^UDEV"` counts the
  banner as a hotplug and reports a dropout on a display that never moved. The
  match hangs on the bracketed timestamp of a real event line.
- **NW2's idle control.** The first rehearsal read `rx_dropped +1` across the run
  and would have failed the Ethernet row on ambient multicast. The test now takes
  an idle window of the same shape with nothing driving the link.
- **MC1's known image.** "A known 200-bit image" is 25 bytes of the mic-preamp
  chain, and the byte is `(gain & 63) << 2 | phantom << 1 | mute`. The image
  written is 24 distinct gains with **phantom OFF and mute ON on every position**
  — as safe as SAFE, and distinguishable from SAFE, from all-ones and from
  all-zeros, which is what MC3's guard needs. `micGainFull` (`0xFC` × 24, gain 63
  phantom off UNMUTED) is what an S_RESET actually leaves behind and is never
  written here.

### 4.2 The bench rules are in the code, not in the operator

Every rule the dispatch carries is enforced by the runner: `/home/app/dspboot` is
copied from and never booted from; AN_EN is read and never written; the pin
handback is the correct one (**not** `pinctrl set 6,…,24,… a0`, whose GPIO24
ALT0 is `SD0_DAT2` and leaves chip 2's select asserted so chip 2 boots
`chip1.ldr`); boot+config runs twice because the config commit desyncs the link
on the first pass; the 595 chain is returned to SAFE **after** the last boot; and
the MCU verdict is read from the whole of `/home/app/logs/log` because the app
rewrites that file on start.

The handback's own evidence shows why the ordering matters. The SAFE write's
first pass read back what the chain was holding at that moment:

```
pass1  00 E0 FE 00 00 00 00 00 00 E0 04 20 00 00 00 00 00 E0 FE 00 00 00 00 00 00
```

That is boot-stream residue — half a megabyte of `.ldr` clocked past the chain —
and it is exactly what S70-7 predicted. A SAFE image written before the last boot
would have been overwritten by it.

### 4.3 Two runner defects found and fixed in this session

Both were found by reading the artifacts rather than the summaries, which is the
W0 rule applied to the runner itself:

1. `s89_signbit.py` takes the symbol directory as `argv[1]`; the first version
   called it bare, so the inter-chip link gate raised `IndexError` before it read
   the part and **scored nothing while appearing to run**. Fixed, and the gate
   was re-taken on the second pass.
2. `ROOT` was computed one directory too shallow, so the first run wrote its CSV
   and raw-read logs under `tools/MW/D24/...` instead of the repo's
   `MW/D24/...`. Fixed; the first run's artifacts were moved to the contract
   path.
## 4a. The prerequisite table

The spec's eight, as they stand after the inventory (`readpaths.md` has the
evidence and the file:line citations).

| # | prerequisite | verdict | disposition |
|---|---|---|---|
| 1a | H1S1 firmware-version cell (ML2) | **ABSENT** | S90-P1 — land it as a sentinel, and fix the stale manifest it is compared against |
| 1b | panel enumerate / version via the UART mux (ML-P1/2) | **enumerate EXISTS, version ABSENT; the mux does not exist** | S90-P2 — extend the S_TEST string; enumeration already passes |
| 2 | H1S1 chip-select test command (DC1/DC2) | **ABSENT — and must stay absent** | S90-P3 — withdraw; DC1/DC2 ran from the CM4 and passed |
| 3 | H1S1 `!RST_D` pulse (DR1) | **ABSENT — and not needed** | S90-P4 — withdraw; DR1 ran from CM4 GPIO16 and passed |
| 4 | S81 codec read arm (CC1/CC2) | **EXISTS** | nothing owed — CC1 and CC2 both passed on it |
| 5 | speaker feed routing (SP1) | **ABSENT** | S90-P6 — a def item, and entangled with S89-2's half-wired codec slots |
| 6 | BOOT0/NRST drive from H1S1 (ML-B0) | **ABSENT, and not closable in firmware** | S90-P5 — no pin exists; rev-D wiring or out of section 1. PW's ruling wanted |
| 7 | `iperf3` on the CM4, `edid-decode`/`xxd` | **CLOSED IN-SESSION** | installed; `ethtool` was present but off `app`'s PATH at `/usr/sbin/ethtool` |
| 8 | results CSV writer | **CLOSED IN-SESSION** | `tools/pi/d24_selftest.py`, verified against the hub's own generator |

Two more that the spec does not list and the run turned up:

| prerequisite | verdict | disposition |
|---|---|---|
| a reader for the power MCU over MHRX (AS-PWR) | **ABSENT** | S90-P7 — needs `d24-pwr-mcu-def.csv` somewhere this spoke can read |
| the DUPLEX PCM overlay for the CPLD design-id knock (AS-CPLD) | **ABSENT in the as-found state** | a `config.txt` line plus a reboot; the overrun half of the test ran without it |

## 5. 🔴 For PW — the H1S1 firmware proposals, as a set

No H1S1 firmware was modified in this dispatch. These are the changes that would
close the prerequisites, with the exact command or cell shape each would take, so
they can be ruled on together. **Three of the spec's five firmware prerequisites
are proposals to WITHDRAW rather than to land**, and that is the substantive
finding of the inventory: they ask H1S1 to drive nets it is explicitly forbidden
to drive.

### S90-P1 — H1S1 version cell (spec prereq 1, test ML2). PROPOSE: land it, as a sentinel, not a cell.

A version is longer than one byte and the matrix bus carries one byte per cell,
so the obvious form — a new `Sys001Ver001` cell — either truncates the version or
costs four cells. The S81 arm already has the right shape for this and costs
**zero new cells**: another sentinel in the ADDRESS cell, with the byte INDEX in
the data cell, answering on the address cell exactly as `0xFB` does.

```c
/* matrix.cs, inside CodecPoll()'s sentinel ladder */
else if (reg == 0xF9)                       /* hand back byte `val` of the version */
{
    matrix[pSys001Test001][TXD] = (val < sizeof(fwVersion) - 1) ? fwVersion[val] : 0x00;
    matrix[pSys001Test001][TXF] = 1;
}
```
with, at the top of `matrix.cs`:
```c
const char fwVersion[] = "H1S1 2026-09-20 s81";   /* bumped with every flash */
```

Host side: `d24_bus_probe.py --mode version` walks the index until it reads 0x00.
The comparison ML2 actually wants is against the manifest the app already logs
for `/home/app/firmware/H1S1.shex`, so **the same string must be written into the
shex pack** at `hex2shex.py` time or the two sides have nothing to compare.

*Name it `CodecPoll` no longer.* The function is now the H1S1 command dispatcher
and only one of its five sentinels is about the codec; a rename to `TestPoll()`
would stop the next reader assuming a codec SPI transaction happens on every
branch. Cosmetic, and PW's call.

### S90-P2 — panel version (spec prereq 1, tests ML-P1/ML-P2). PROPOSE: land it, and it costs nothing.

**The spec's premise is wrong and the correction makes this free.** There is no
H1S1 UART mux: H1S3 and H1S4 are peer MCUs on MH1's matrix bus
(`defs/products/d24/fw.csv:26,66`), they already answer S_TEST with their own
identity strings, and `matrix-app` already logs all three. So enumeration needs
nothing. Only the VERSION is missing, and the cheapest place to put it is the
string that is already being transmitted:

```c
/* in each panel's own firmware, the same line H1S1 has at matrix.cs:46 */
char testMessage[100] = "// H1S3 SW Right 2026-xx-xx <build>\n";
```

No new cell, no new protocol, no change to MH1 or to the app — the app's
`MCU verified: // H1S3 SW Right` line simply grows a version, and `d24_selftest.py`
already captures that line verbatim. If PW prefers, the same `0xF9` sentinel as
S90-P1 could be added to each panel instead, at the cost of a cell pair per panel.

### S90-P3 — H1S1 chip-select test command (spec prereq 2, tests DC1/DC2). PROPOSE: WITHDRAW.

It should not be built. `~/build-h1s1/Core/Src/main.c:362-381` configures all
eight CS pins as `GPIO_MODE_INPUT` under an explicit comment — *"ALL EIGHT CS
pins (CS1-CS8) are OWNED BY THE CM4 — this MCU must never drive them. The CM4
masters the DSP SPI/boot bus directly; H1S1 only monitors"* — which is DSP4
architecture decision D1 written into the firmware. Adding an assert-one-read-one
command would put a second master on the boot bus the CM4 uses, and the bus
already has one unarbitrated second master (U7's housekeeping SPI,
`hardware-map.md`).

The test does not need it. **DC1/DC2 run from the CM4 today** and did in this
session: `dsp4_diag.py --chip N --cs-gpio 6|24 --rdy-gpio 8|12`. What the spec
should change instead is the METHOD and the SCOPE — see the spec corrections below.

### S90-P4 — H1S1 `!RST_D` pulse command (spec prereq 3, test DR1). PROPOSE: WITHDRAW.

Also should not be built, and for a sharper reason than P3. The `!RST_D` net was
traced end to end on 2026-08-21 (`hardware-map.md:305-324`): **six places, no
series resistor anywhere, and two potential masters with no arbitration** — CM4
GPIO16 and U7 PA13. PA13 is unconfigured in the H1S1 firmware and sits in the
STM32U5 reset default (SWDIO, ~40 kΩ internal pull-up), so today there is exactly
one driver. Implementing the spec's command would create a second push-pull
driver on a reset net with no isolation, to duplicate a capability the CM4
already has and that DR1 used in this session.

### S90-P5 — BOOT0/NRST drive from H1S1 (spec prereq 6, test ML-B0). NOT A FIRMWARE ITEM — PW's ruling wanted.

This one cannot be closed in firmware at all. H1S1's entire GPIO set is `CS1-8`,
`RST_C`, `CS_M`, `CS_C`, `BLINK`, `BUSY`, `S2`, `S3` (`Core/Inc/main.h:59-91`,
read in full) — there is no pin on the panel BOOT0 or NRST nets to configure. So
ML-B0 is one of:

  a) a **rev-D wiring item** — route the panel BOOT0 (Digital S13 right / S9
     left) and NRST lines to spare H1S1 pins, then the firmware command is small;
  b) **out of section 1 permanently** — the STM32 ROM-bootloader sync is a
     manufacturing/recovery path, and proving it needs the drive that only a
     programmer has; or
  c) folded into the panels' own firmware as a self-reported "I can see my BOOT0
     pin" read, which proves the pin but not the drive.

Recommendation: (b) for this unit and (a) on the rev-D list. It is PW's call and
nothing was done.

### S90-P6 — speaker route (spec prereq 5, test SP1). A DEF ITEM, as the spec anticipated.

There is no node or cell named for the speaker anywhere: zero hits for
`spkr`/`speaker` in `defs/products/d24/dsp.csv` and `MW/D24/MX/_matrix.csv`.
SPKR0/SPKR1 exist only as connector pins (`d24-hw-inventory.csv:1075` Left Switch
J2, `:278` Analog J59). The path is `DSPB O2 = PLL8_1 = CDC_I` → AK4619 codec DAC
→ **TS482 analog amplifier on the Digital board** → panels
(`hardware-map.md:157,439`). So the DSP can reach the speaker only by writing the
codec's aux/talkback DAC slots, and the def question is which node owns them.

That question is already open on the same slots: **S89-2** found `C2_MON_OUT` and
`C2_CODEC_AUX_OUT` each declare `slot_count=2` but get one gather entry, so codec
TDM slots 1 and 3 are written by nobody. SP1 should be held until that is
resolved rather than adding a speaker node beside a half-wired pair.

### S90-P7 — power MCU read (test AS-PWR). Proposal, not a prerequisite the spec listed.

AS-PWR has no read path at all in this repo and needs one to ever leave NO DATA.
The power MCU publishes over MHRX per `src/fw/d24-pwr-mcu-def.csv`, which lives in
mx26 and not here. The smallest closing move is a host-side reader in `tools/pi/`
against that def, not a firmware change — but it needs the def carried into a
place this spoke can read, which is a hub decision about where that CSV belongs.
Noting it so the row is not silently permanent.

## 6. Proposed spec corrections

Each is a place the unit disagreed with `docs/spec-d24-selftest.md`. None was
worked around silently.

1. **DC1/DC2 (rows 103-110) — the method and the scope are both wrong.**
   Method: the selects are the CM4's, not H1S1's (S90-P3). Scope: only CS1 and
   CS2 are live on DSP4; **CS3/CS4 are wired to DSPA/DSPB SPI_RDY and are INPUTS**,
   and **CS5-CS8 reach no fitted part** — `hardware-map.md:410-411`, *"CS1-8 DSP
   chip-select provision (8-DSP scaling — only CS1/CS2 live on DSP4; CS3/CS4 wired
   as DSP1/2 SPI_RDY)"*. Six of the eight rows can never answer on this board, and
   a section-1 test that can never answer is not a NO DATA waiting on a
   prerequisite — it is a row that belongs in a different class. Proposed: DC1/DC2
   cover CS1/CS2 with the CM4 method; rows 105-110 get an "n/a on DSP4" status
   rather than sitting in the section-1 count forever.
   Note also that **fw.csv `Dsp1`..`Dsp8` declare a pin and a net, not a part
   number**, so DC2's "id matches the declared part" has nothing declared to match
   against; what CS1/CS2 can prove is CHIP_ID, BUILD_ID and the signed build
   triple, which is what was recorded.
2. **ML-P1/ML-P2 — there is no panel UART mux.** The panels are peers on MH1's
   bus (S90-P2). The method should be S_TEST plus the app's own `MCU verified`
   lines, both of which already work.
3. **ML2 — the two sides of the comparison do not exist yet, and one of them is
   actively wrong.** The spec asks for a version cell equal to "the version in
   `/home/app/firmware/H1S1.shex`'s manifest". The manifest side is an md5 and a
   size, not a version string — and it is **stale by construction**: the app logs
   `779c5665…/95552 B` from a `deploy-manifest.txt` generated 2026-08-18, while
   the file on the unit is `5dc7acde…/100216 B` dated 2026-09-20, the S81 pack
   flashed by hand through `app cli loadfw H1S1`. A deploy manifest does not
   track hand-flashed firmware and never will. So landing a version cell alone
   would have ML2 compare a live value against one that has been wrong for two
   days — worse than comparing nothing. S90-P1 proposes writing the same literal
   into the shex pack at `hex2shex.py` time so both sides move together.
4. **NW4 — the driving host is part of the instrument.** The spec's
   `iperf3 -c <bench host>` needs an inbound port open on the driving machine;
   this one runs `ufw` with `deny (incoming)` and only 22/tcp allowed, so the
   spec's form times out and reports nothing. The runner drives it the other way
   (server on the unit, client on the dsp machine, `-R` for the second direction),
   which measures the same link and needs nothing opened. **And the bar needs a
   stated precondition**: a ≥ 900 Mbit/s verdict is only about the unit if the
   whole path is gigabit. It is not here — see the result — so the runner reads
   the driving host's link speed first and returns NO DATA naming it rather than
   scoring the bench's cabling as a unit fault.
5. **NW2 — `rx_dropped` is not a wire error.** Linux counts host-side software
   drops there (unsubscribed multicast, unknown protocol), and this LAN carries
   plenty; the first rehearsal read `rx_dropped +1` across the run and would have
   reported FAIL on ambient traffic. The criterion is kept as the spec wrote it,
   but the test now takes an **idle control window** of the same shape with nothing
   driving the link, so a counter that climbs on its own is visible in the evidence
   instead of being attributed to the test. Proposed spec text: name the control.
6. **AS-CPLD — the design-id half has an undocumented prerequisite.**
   `dsp4_logic_id.py` knocks over the CM4's PCM link and **needs the DUPLEX
   overlay**; under `dsp4-pcm-slave`, which is what `config.txt` selects on this
   unit, it answers "no reply" for every bitstream, so its silence carries no
   information (bench note 12). Flipping the overlay is a `config.txt` edit plus a
   reboot — not "the unit as found" — so the id half is NO DATA and the
   `BLK_OVERRUN` half ran. Proposed: the spec should either name the overlay as a
   prerequisite or split AS-CPLD into an id test and a clock test.
7. **AS-DAC — the criterion depends on a build the shipping image is not.**
   "TX slots non-constant while TEST_OSC runs" needs `DSP4_TEST_NODES=1`, and the
   pair under test is the shipping pair. Proposed: either make AS-DAC a
   stimulus-free structural test (the slots exist and the gather writes them) and
   move the driven form to section 2, or state that section 1's DAC row is taken
   on a TEST_NODES build.
8. **The rails are a precondition on every converter row.** AN_EN is CM4 GPIO26,
   it is `lo`, and a dispatched session may not raise it (bench note 19 / S49-15).
   AS-ADC and MM1 therefore cannot reach PASS unattended in the unit's as-found
   state. Proposed: the spec should say whether section 1 runs rails-up (which
   needs someone with the authority to raise AN_EN, or an app config change) or
   whether the converter rows move to section 2. As written they are section-1
   rows that no unattended run can ever pass.
9. **USB-HUB has no workbook item.** The spec files it under "feeds section-2 UA1"
   and the coverage list does not include it, so it produces evidence and no CSV
   row. Worth saying explicitly in the results contract, since a reader counting
   tests against rows will otherwise be one out.
10. **HD0-2's soak length is a scheduling fact, not a criterion.** A run shorter
    than the spec's 1 h is NO DATA naming its own length; the runner does not
    round a short window up into a soak, and it takes the duration off the log's
    own timestamps rather than multiplying a sample count by an interval that
    may not have been honoured. Note that 1 h is the section-1 bar and the spec
    already says a shipping proof wants 24 h, so this row is owed a long run
    whatever today's reads.
11. **NW3 needs more than one pass, and the spec should say so.** Five
    consecutive 200-packet runs on this bench read 2.0 %, 0.5 %, 0.0 %, 0.0 %
    and 0.5 %. A one-shot 0 % bar is settled by the scheduler, not by the unit,
    and "run it again" is how such a bar gets met. The runner takes three passes
    per target and scores the worst. **And the criterion should name its
    subject**: as §3.5 shows, what this test actually caught on MW-D24-2 is
    `matrix-app`'s CPU load, not the RJ45 — the same 5 Hz ping is 0 % on 6 of 6
    passes with the app stopped. A row that says "Ethernet (RJ45): FAIL" without
    that sentence next to it will send someone to look at a cable.

## 7. Artefacts and the unit as found

**Landed**
- `tools/pi/d24_selftest.py` — the runner (sections A/B/C, `--only`, `--keys`,
  `--no-append`).
- `tools/pi/d24_bus_probe.py` — the two matrix-bus reads, run on the CM4.
- `MW/D24/DSP/accept/item-status.csv` — the results contract,
  `board,item,test,verdict,measured,limit,evidence,stamp`. Verified against the
  hub's own generator: `build-d24-connector-status.py --status <csv>` accepts
  every key, which is the check that matters because the generator errors on an
  unknown one.
- `MW/D24/DSP/s90/readpaths.md` — gate 1's inventory, committed before the runner.
- `MW/D24/DSP/s90/logs/<stamp>/<test>.txt` — the raw read behind every row, whole
  and untrimmed. The CSV's `evidence` column is the same text clipped to 400
  characters.

**Closed in-session, no firmware**: `iperf3`, `edid-decode` and `xxd` installed
on the CM4 (prereq 7); `iperf3` on this machine. `ethtool` was already installed
but is not on `app`'s PATH — it is `/usr/sbin/ethtool` and the runner calls it by
absolute path.

**Unit as found.** No CPLD flashed — shipping `d02d83b3cc22` untouched.
`~/dspboot/candidate-s82` untouched; the pair was booted from `/home/app/s90`,
copied from it. S87's four uncommitted files untouched. The 595 chain carries the
SAFE image, written after the last boot and `VERIFIED 200/200`. CS_M
(GPIO27) `ip pu`. **AN_EN (GPIO26) `lo` — never written by this session.**
`matrix-app` active, **3 of 3 MCUs verified** (`H1S1`, `H1S3`, `H1S4`) read from
the whole of `/home/app/logs/log`. The DSP pair is left booted and configured
from the last section-C run, its inter-chip link gated CLEAN. The loop cable was
not touched.

**One difference, stated not glossed**: the CM4 has four packages installed that
it did not have this morning (`iperf3`, `edid-decode`, `xxd`, and their two
dependency libs), and `/home/app/s90` now exists as a stage directory. The
dispatch asked for exactly the first of those; the rest are its consequences.
`/home/app/dspboot` was not written to — the tools this leg needs that live only
in this repo were `scp`'d into `/home/app/s90` **after** the symlink loop and only
for names the loop had not linked, because an `scp` onto a symlink writes through
it into `/home/app/dspboot` (S83-2's second trap).

`check-contract-drift.sh` is clean, `defs.lock` is unmoved and no generated
artifact moved; this dispatch touches no contract input or output, so no contract
note is due under `release-notes-contract-convention.md`.
