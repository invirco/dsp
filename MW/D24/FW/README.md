provenance: AI-drafted 2026-10-03 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# D24 MCU firmware

Firmware sources for the D24's small MCUs (five since S168; the power MCU joined 2026-10-15), one folder each (PW ruling 2026-10-03, S168; they sat outside any Matrix repo until then). ST `Drivers/` are not stored — each README names the pack. Build any of the U5/F0/G0 images with `./build-mcu.sh <MCU> <Drivers dir>` (H1S1G0: Drivers from `H1S1G0/fetch-drivers.sh`); P1 has its own `Makefile`. Toolchain: arm-none-eabi-gcc 14.2.1 (Debian `15:14.2.rel1-1`). Never commit CCES/Quartus/licence material.

| MCU | part | role | source | image on MW-D24-2 (2026-10-03) | reproduces? | how flashed |
|---|---|---|---|---|---|---|
| MH1 | STM32G031C4T6 | panel hub, flash router, PANEL_DIM | `MH1/` (08-19 tree + `mh1-dimset.diff`) | dimset: hex `1110c60a…`, bin `bf21f762…` | YES, byte-for-byte (hex+bin) | SWD only (openocd, mux ch 3) — not by `loadfw` |
| H1S1 | STM32U575RIT6 | codec/595/power-word interface | `H1S1/` (= `~/build-h1s1`) | `H1S1.shex` `19a5492d…` | YES, byte-for-byte | `app cli loadfw H1S1` (after `sreset.py` if needed) |
| H1S1 (rev D card) | STM32G0B1RET6 | same socket on the DSP card rev D: RST_C/RST_O, panel bus, revision straps (no codec, no 595, no SPI) | `H1S1G0/` (S174 port, no .ioc) | none — no rev D card exists yet | builds clean, desk only; hex reproduces across builds | `tools/pi/h1s1_flash.sh` (card guard, then `app cli loadfw H1S1`) |
| H1S3 | STM32F030R8T6 | right switch panel (talkback variant B) | `H1S3/` (= unit `s131fw/H1S3-B`) | `H1S3.shex` `43efd43f…` (id H1S4) | YES, byte-for-byte | `app cli loadfw H1S3` |
| H1S4 | STM32F030R8T6 | left switch panel + pedal relay | `H1S4/` (S139 base + S167 relay) | `H1S4.shex` `ff79052e…` (id H1S3) | YES: base `f54848b0` and relay `ff79052e`, both byte-for-byte | `app cli loadfw H1S4` |
| P1 | STM32C031K4U6 | foot pedal | `P1/` | `P1.bin` 1.1-s169 `f0fd3cff…` (bench pedal, OPTR `0xFFFFFEAA`; S169: one image for both display polarities, replaces `P1-cc.bin` `793aa3f5…`) | YES, byte-for-byte (S169 build) | over the J8 cable: relay + ROM bootloader (8E1), `d24_pedal.py update` |
| PWR | STM32F030F4P6 | power MCU U34: rails, rocker, shutdown, converter clocks, rev D pedal supply | `PWR/` (from mx26 `src/fw/pwr-mcu`, 2026-10-15) | app mx26 0215bc4 (len 0x6A0) + 08-18 bootloader, per the records | YES: the mx26 tree's three images byte-for-byte (`PWR/baseline/`); new one-image build in `PWR/image/`, desk only | SWD hot-attach from the CM4 (`flash-*.sh`); after the 2026-10-15 bootloader, also `tools/pi/d24_pwrlink.py update` |

Full md5s are in each folder's README. Pitfalls found while reproducing:
- The unit's `/home/app/fwbuild/{H1S3,MH1}` are NOT the flashed sources: H1S3's flashed image is variant B from `s131fw/H1S3-B`; MH1's flashed image is the dimset build, while `fwbuild/MH1/Debug/MH1.elf` (`0fe9717a`) is the unpatched 08-19 build. `fwbuild/H1S1` carries a stale generation; use `~/build-h1s1`.
- `loadfw` header ids for the two switch MCUs are crossed (see the READMEs).
- The CubeIDE-generated `makefile.linux` needs `-fcyclomatic-complexity` stripped; `build-mcu.sh` does it in a scratch copy.
- MH1's flashed identity was not re-read from the chip in S168 (the unit was not to be touched); it rests on the S131 SWD `verify_image` and the `s131fw/MH1-dimset.bin` file.

Not byte-for-byte: nothing. No MCU needs an opus-tier follow-up.

## Rev D requirement — UPDATE HOLD (PW ruling 2026-10-03)

The power MCU must provide, for P1 firmware updates over the cable:
1. A host command that **suspends the pedal heartbeat check for a bounded, re-armable time (60 s)** with the pedal supply held ON. Each re-arm restarts the 60 s; expiry returns to the normal check.
2. A host-commanded **pedal power-cycle with the relay open** (so the P1 ROM can auto-baud on the host's first byte).

Reason: CHANGE 6 drops the pedal supply on heartbeat loss, and the P1 ROM bootloader sends no heartbeat (S167). Text only; no firmware change made. Belongs in the power-MCU def (`defs`, hub item) when rev D is specified.

**Flash guard (S174, PW S173 Q4 (a)).** No H1S1 and no CPLD flash without positive identification of the DSP card: `tools/pi/h1s1_flash.sh` (H1S1, either image), `tools/pi/logic_flash.sh` and `MW/D32/DSP/SHARC/loadlogic.sh` (CPLD) all run `tools/pi/dspcard_id.py` on the bench first and refuse on anything but a match. The H1S1 image's own initial stack pointer says which U7 it is for (U575 `0x200C0000` = rev C, G0B1 `0x20024000` = rev D).

Tools here: `hex2shex.py` (Intel hex → shex, MCU id as arg), `sreset.py` (S_RESET before `loadfw`; runs on the unit's CM4).

## In the D24 package (S171)

Every image here — plus the CPLD bitstream (`shared/dsp4-logic/bitstream/`), the DSP pair (`MW/D32/DSP/SHARC/build_<arm>/chip{1,2}.ldr` + `.sym.json`) and the power MCU image (mx26 `src/fw/pwr-mcu/pwr-mcu.img`) — is declared in mx26 `src/sw/app/Resources/firmware/d24-firmware.csv` with its md5. The package builder takes the files from this repo (`$DSP_REPO`, else `~/dsp`) and refuses a package if one is missing or no longer matches; after rebuilding an image here, record it with mx26 `scripts/sync-d24-firmware.sh` (and change its version label in the CSV).
