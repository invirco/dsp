provenance: AI-drafted 2026-09-22 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S90 gate 1 — read-path inventory for the D24 section-1 self-test

What exists to read each section-1 test WITH, before a line of the runner is
written. Bounded search of: this repo, `~/build-h1s1` (the H1S1 firmware source),
`~/mx26` (read-only), and the unit itself (`app@192.168.1.219`). Every EXISTS
line names the cell, command or tool; every ABSENT line names what would have to
land. Method is the spec's (`~/mx26/docs/spec-d24-selftest.md`), and where the
unit disagrees with the spec that is recorded here rather than worked around.

## 1. The eight prerequisites the spec lists

| # | prerequisite (spec §Prerequisites) | verdict | what was found |
|---|---|---|---|
| 1a | **H1S1 firmware-version cell** (ML2) | **ABSENT** | H1S1's entire local cell table is four entries — `Sys001Enc001` (5232), `Sys001Skin001` (5412), `Sys001Test001` (5414), `Sys001Test002` (5415) — `~/build-h1s1/Core/Inc/matrix.cs:11-18`. No `*Ver*`/`*Version*`/`*Build*` cell exists in `matrix.h` (5415 lines). The only identity H1S1 publishes is the S_TEST string `"// H1S1 DSP"` (`matrix.cs:46`, sent by `TestMessage()` at `matrix.cs:324-328`) — an identity, not a version. |
| 1b | **panel enumerate/version through the UART mux** (ML-P1/2) | **EXISTS as identity, ABSENT as version — and the spec's topology is wrong** | There is no H1S1 UART mux. H1S3 (SW_RIGHT, STM32F030R8) and H1S4 (SW_LEFT) are PEER MCUs on MH1's matrix bus, exactly like H1S1 — `defs/products/d24/fw.csv:26,66`. They answer S_TEST with their own identity strings, and `matrix-app` logs all three on every boot: `MCU verified: // H1S1 DSP` / `// H1S3 SW Right` / `// H1S4 SW Left` in `/home/app/logs/log` (read on the unit 2026-09-22, 17:21:18). So enumeration EXISTS with no firmware change; a version does not. |
| 2 | **H1S1 chip-select test command** (DC1/DC2) | **ABSENT — and must stay absent** | `~/build-h1s1/Core/Src/main.c:362-381` configures all eight CS pins as `GPIO_MODE_INPUT` under an explicit comment: *"ALL EIGHT CS pins (CS1-CS8) are OWNED BY THE CM4 — this MCU must never drive them."* The CM4 masters the DSP SPI directly (DSP4 architecture decision D1). Read path EXISTS on the CM4 instead: `tools/pi/dsp4_boot.py:83-86` — CS1 = GPIO6 → chip 1, CS2 = GPIO24 → chip 2, CS3 = GPIO8 / CS4 = GPIO12 are SPI_RDY INPUTS, `!RST_D` = GPIO16. |
| 3 | **H1S1 `!RST_D` pulse command** (DR1) | **ABSENT — and not needed** | `RST_D_Pin`/`RST_D_GPIO_Port` are undefined in `main.h`, PA13 is absent from `H1S1.ioc`, and the only two references in `main.c:124-126` are commented out. `MW/D24/HW/hardware-map.md:316-324` traced the net end to end: six places, one of which is CM4 GPIO16, and *"the schematic annotation '!RST_D (Reset DSPs)' on U7 p47 describes an intent the firmware has never implemented."* `dsp4_boot.py` already pulses it (`RST_GPIO = 16`, `RESET_LOW_S = 0.050`). |
| 4 | **S81 codec read arm** (CC1/CC2) | **EXISTS** | `CodecPoll()` at `~/build-h1s1/Core/Inc/matrix.cs:212-242`, byte-identical to the flashed snapshot `MW/D24/DSP/s81/h1s1-matrix.cs.s81` (`diff` clean). Sentinels in the ADDRESS cell: `0xFE` read register, `0xFB` fetch guard, `0xFD` set read command code (default `0x43`, `matrix.cs:68`), `0xFF` re-run `StartAK4619()`. Host side: `tools/pi/codec4619.py --read 05` / `--read-all`, staged on the unit. |
| 5 | **Speaker feed routing** (SP1) | **ABSENT — a def item, not a fixture** | Zero hits for `spkr`/`speaker` in `defs/products/d24/dsp.csv`, `MW/D24/MX/_matrix.csv` or the address map. SPKR0/SPKR1 exist only as connector pins (`d24-hw-inventory.csv:1075`, Left Switch J2; `:278`, Analog J59). The real path is `DSPB O2 = PLL8_1 = CDC_I` → AK4916 codec DAC → TS482 amp on the Digital board → panels (`hardware-map.md:157,439`), so the speaker is downstream of an ANALOG amplifier fed by a codec DAC and there is no routable DSP node named for it. |
| 6 | **BOOT0/NRST drive from H1S1** (ML-B0) | **ABSENT** | No `BOOT0`, `NRST`, `S9` or `S13` anywhere in the H1S1 firmware. H1S1's whole GPIO set is `CS1-8`, `RST_C`, `CS_M`, `CS_C`, `BLINK`, `BUSY`, `S2`, `S3` (`main.h:59-91`, read in full). No panel-reset capability of any kind. |
| 7 | **`iperf3` on the CM4 + `edid-decode`/`xxd`** (NW4, HD0-1) | **CLOSED IN-SESSION** | Installed on the unit 2026-09-22: `iperf3` 3.18-2+deb13u2, `edid-decode` 0.1~git20241119, `xxd` 9.1.1230-2. `ethtool` 1:6.14.2-1 was already installed but is **not on `app`'s PATH** — it lives at `/usr/sbin/ethtool` and must be called by absolute path. `iperf3` also installed on this machine (192.168.1.211) to serve NW4. |
| 8 | **Results CSV writer** | **ABSENT — this dispatch builds it** | `item-status.csv` does not exist anywhere in the repo; `tools/pi/d24_selftest.py` does not exist. `MW/D24/DSP/accept/` holds `manifest.json` + 38 fixture JSONs from `tools/accept/gen_accept_fixtures.py` — a different contract (audio-layer fixtures), not this one. |

## 2. Per-test read paths

`EXISTS` = there is a command that answers today. `ABSENT` = no read path; the
test reports `NO DATA` naming the prerequisite.

### A. From the CM4

| test | read path | verdict |
|---|---|---|
| HD0-1 | `/sys/class/drm/card0-HDMI-A-1/{status,edid,modes}`; `edid-decode`; `kmsprint` | **EXISTS.** Connector present and `connected` as of 2026-09-22 19:33. `modetest` is absent; `kmsprint` is installed and serves the same purpose. |
| HD0-2 | same `status` + the connector's `uevent`/hotplug count, re-read on a timer | **EXISTS.** The spec asks ≥ 1 h (24 h for a shipping proof); a shorter window is a shorter window and the runner records the duration rather than claiming the soak. |
| HD-PWR | inferred from HD0-1 | **EXISTS** (inference, so stated as such in `evidence`). |
| NW1 | `/usr/sbin/ethtool eth0`; `/sys/class/net/eth0/carrier` | **EXISTS.** Reads `1000Mb/s` / `Full` / `yes` / `1`. |
| NW2 | `ip -s link show eth0` before/after | **EXISTS.** |
| NW3 | `ping -c 200 -i 0.2 192.168.1.211` | **EXISTS.** |
| NW4 | `iperf3 -c 192.168.1.211 -t 10` and `-R`, server on this machine | **EXISTS** as of today (prerequisite 7). |
| AS-CM4 | `uptime`, `vcgencmd get_throttled/measure_temp/measure_volts core`, `/proc/device-tree/model`, `systemctl is-active matrix-app` | **EXISTS.** |
| USB-HUB | `lsusb -t` | **EXISTS** — but it maps to NO workbook item (the spec itself says it "feeds section-2 UA1"), so it yields evidence and no CSV row. |

### B. Through H1S1 over the matrix bus

Transport: `/dev/serial0` at 115200 through `termios` (pyserial is not installed
on the bench), newline-terminated tokens, MH1's `.`/`:` idle heartbeat interleaved
— `tools/pi/codec4619.py` `Bus`/`cell_line`/`cell_prefix`/`parse_reply`
(`codec4619.py:102-162,193-243`). **`matrix-app` owns the port**, so every B test
needs the app stopped and restarted afterwards.

| test | read path | verdict |
|---|---|---|
| ML1 | three `0xFB` guard fetches on `Sys001Test001` (5414) — each sets `TXD := codecReadGuard`, `TXF := 1` and is answered on the ADDRESS cell; no SPI is issued | **EXISTS.** This is the round trip the spec asks for: host → MH1 → H1S1 → MH1 → host, three times. |
| ML2 | H1S1 version cell | **ABSENT** (prereq 1a). The `/home/app/firmware/H1S1.shex` side exists — md5 `779c5665f9992fbf814eeed2043d9280`, 95552 B, logged by the app — so only the MCU half is missing. |
| ML-M | any ML1 read proves MH1's dispatch; MH1's own version | **PARTIAL.** The path EXISTS (ML1 cannot answer unless MH1 dispatched it). MH1 firmware is not in `~/build-h1s1`, so whether it publishes a version is UNKNOWN; its S_TEST line is the available identity. |
| ML-P1 / ML-P2 | S_TEST (`&`) identity line from H1S3 / H1S4, and `matrix-app`'s own `MCU verified:` lines in `/home/app/logs/log` | **EXISTS as identity.** Version ABSENT (prereq 1b). Note the app's MCU verify is a known race on ~1 restart in 4 (bench note 7) — read the WHOLE log file, and a 1-of-3 is the race, not a dead panel. |
| ML-B0 | BOOT0 + NRST drive, `0x7F` → `0x79` ROM sync | **ABSENT** (prereq 6). |
| DC1 | assert one CS, clock a read | **EXISTS for CS1/CS2, FROM THE CM4, not H1S1** (prereq 2). `dsp4_diag.py --chip N --cs-gpio 6\|24 --rdy-gpio 8\|12` reads `CHIP_ID`/`BUILD_ID` behind the addressed select; `dsp4_checkchip.py --chip N` is the identity gate that catches the two-chip-1s state. **CS3/CS4 are SPI_RDY inputs, not selects. CS5–CS8 have no part behind them on DSP4** — `hardware-map.md:410-411`: *"CS1-8 DSP chip-select provision (8-DSP scaling — only CS1/CS2 live on DSP4)"*. |
| DC2 | identity of the part behind the select | **EXISTS** for CS1/CS2 via `dsp4_buildcfg.py` (`DIAG_BUILD_CFG` 0xE0EA / `CFG2` 0xE0EB / `CFG3`) and `dsp4_logic_id.py` for the CPLD. |
| DR1 | pulse `!RST_D`, watch the heartbeat stop | **EXISTS from the CM4** (prereq 3): GPIO16, with `FRAME_COUNT` (0xE004) as the heartbeat. |
| DR2 | boot+config recipe, ids + lane reads | **EXISTS**: `dsp4_boot.py --dir <stage>` + `dsp4_config.py --product d24 --chip N`, twice (the config commit desyncs the link on the first pass — bench note 2), then `dsp4_boot_verify.sh`. |
| MC1 | write a known 200-bit image to the 74HC595 chain, read the MISO shift-back | **EXISTS**: `MW/D24/DSP/s55/tools/s55_chain.py` — 25 bytes, two transfers, CS_M = CM4 GPIO27, prints `VERIFIED 200/200 <hex>` or `MISMATCH`. Byte = `(gain&63)<<2 | (phantom&1)<<1 | (mute&1)`. |
| MC2 | write the SAFE image, read back | **EXISTS**: SAFE = `[0x01]×24 + [0x00]` (gain 0, phantom off, MUTED). **S_RESET does NOT produce SAFE** — `MainInit()` ends in `TestMicPres()`, whose only image is `micGainFull` = `0xFC`×24 = gain 63, phantom OFF, UNMUTED. |
| MC3 | all-zeros guard: read CS_M's level before reporting | **PARTIAL.** CS_M's level at the analog board is not readable through H1S1 (no such command); what IS readable is the CM4 end — `pinctrl get 27`, and the S86 lesson that GPIO27 in pull-DOWN holds CS_M low and gates the U2 MISO buffer. That is the guard the runner can actually apply. |
| CC1 | read 05H after `StartAK4619` | **EXISTS** (prereq 4): `codec4619.py --read 05`. Note the guard byte alone does not prove the part is answering — `val == reg` is the echo signature (`codec4619.py::verdict`). |
| CC2 | write MGN2R to another code, read back, restore | **EXISTS**: `codec4619.py --mgn2r N` then `--read 05`, restore after. |

### C. From the DSPs

All of C needs the pair booted and configured, which needs `matrix-app` stopped
and the pin handback of bench note 1 (**not** the `pinctrl set 6,…,24,… a0` every
old run script still uses — GPIO24's ALT0 is `SD0_DAT2`, so chip 2's CS sits
asserted and chip 2 comes up running `chip1.ldr`).

| test | read path | verdict |
|---|---|---|
| AS-DSPA / AS-DSPB | `BUILD_ID` 0xE017, `FRAME_COUNT` 0xE004 delta, `BOOT_STAGE` 0xE002 via `dsp4_diag.py`; `dsp4_buildcfg.py` for the signed triple; lanes via `dsp4_rxscan.py` | **EXISTS.** |
| AS-CPLD | `dsp4_logic_id.py` (PCM knock, no SPI, no app stop needed) + `dsp4_blk30.py <chip> <s>` for the `BLK_OVERRUN` delta | **PARTIAL — and this is a real trap.** `dsp4_logic_id.py` **needs the DUPLEX PCM overlay**; on `dsp4-pcm-slave` it answers "no reply" for EVERY bitstream, so silence means nothing (bench note 12). Flipping the overlay is a `config.txt` edit plus a reboot, which is not "the unit as found". The overrun half EXISTS unconditionally. |
| AS-ADC | `dsp4_rxscan.py --symdir <stage>` — verdict is on DISTINCT values, not non-zero; a stuck `0xFFFFFFFF` is as dead as a stuck zero | **EXISTS**, with a standing caveat: `DSPA I0 = AD0 = U15` has no front end fitted on MW-D24-2 (eight channels, measured S86), so U15's lanes are expected dead and that is the unit, not the test. |
| AS-DAC | `_tx_out_slot_*` read **contiguously** — `tools/pi/s89_slotcap.py <symdir> <chip> _tx_out_slot_<node> <N>`, which arms `_scope_record` | **EXISTS for the read. The STIMULUS does not.** The spec's method is "non-constant while TEST_OSC runs into an output", and TEST_OSC needs `DSP4_TEST_NODES=1`; the shipping pair is `TEST_NODES=0`. `dsp4_s49_osc.py` refuses a shipping image by symbol check rather than printing four zeros. So AS-DAC can be read without a stimulus but not driven with one on the image under test. |
| AS-PWR | power MCU state/PWR_FAIL/AN_EN over MHRX | **ABSENT.** No tool in this repo reads the power MCU's published words; `d24-pwr-mcu-def.csv` is not in this tree. AN_EN is not an MCU word at all — it is CM4 GPIO26, `pinctrl get 26`. |
| MM1 | the MEMS lane (`DSPA I7`, `_buf_C1_XIN_MEMS`) through `dsp4_rxscan.py` | **EXISTS for the read.** Whether it can PASS depends on the rails — see §3. |
| SP1 | TEST_OSC → SPKR0/1, read the MEMS lane | **ABSENT twice over**: no speaker node in the topology (prereq 5) and no TEST_OSC on a shipping image. |

## 3. Two standing bench facts that decide verdicts, not just methods

- **AN_EN (CM4 GPIO26) is `lo` and a dispatched session may not raise it.**
  Bench note 19 (S49-15) is explicit: *"Restoring it is `sudo pinctrl set 26 op dh`
  and it is the HUB's to run — AN_EN is never written by a dispatched session."*
  With the rails down the mic front ends are not converting, so a dark lane is the
  TEST STATE, not a converter fault. Any lane test that reads dark with AN_EN low
  is therefore `NO DATA` naming the rails, never `FAIL` — the spec's own rule that
  a read path answering nothing is never a silent PASS cuts the same way against a
  silent FAIL.
- **Never measure through an unverified boot** (bench note 32 / S89-1): the
  inter-chip SPORT receive framing locks one bit period out on ~1 boot in 7 and
  every inter-chip word then arrives with bit 31 zeroed. `s89_signbit.py` and
  `dsp4_boot_linked.sh` are the gate, and **neither is staged on the unit** — both
  live only in this repo (`ls /home/app/dspboot` 2026-09-22: MISSING). They must be
  `scp`'d explicitly; the stage-directory symlink loop only walks files already at
  `/home/app/dspboot`, which is S83-2's trap and how the S89e leg silently measured
  the wrong configuration and reported PASS.

## 4. Key list

`board` and `item` come from
`python3 ~/mx26/tools/d24/build-d24-connector-status.py --export-keys` — 204 keys.
The spec's row numbers are that file's line numbers minus one (the header). All 36
section-1 rows were resolved against it and every one matched; the mapping is in
the runner's `ITEMS` table so an unknown key fails loudly rather than being skipped,
which is what the hub's generator does on its side too.

**mx26's `defs/` submodule is not initialised on this machine and cannot be**
(`git submodule update --init defs` → `could not read Username for
'https://github.com'`; the gh token is dead). The key export was run against this
repo's `defs/` (`defs-v2026.09.19.3`) through a scratch symlink root. The rows the
export reads from defs are the inter-board links and the remaining headers; all 36
section-1 keys were checked by eye against the spec's own item names.
