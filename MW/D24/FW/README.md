provenance: AI-drafted 2026-10-03 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# D24 MCU firmware

Firmware sources for the D24's five small MCUs, one folder each (PW ruling 2026-10-03, S168; they sat outside any Matrix repo until then). ST `Drivers/` are not stored — each README names the pack. Build any of the four U5/F0/G0 images with `./build-mcu.sh <MCU> <Drivers dir>`; P1 has its own `Makefile`. Toolchain: arm-none-eabi-gcc 14.2.1 (Debian `15:14.2.rel1-1`). Never commit CCES/Quartus/licence material.

| MCU | part | role | source | image on MW-D24-2 (2026-10-03) | reproduces? | how flashed |
|---|---|---|---|---|---|---|
| MH1 | STM32G031C4T6 | panel hub, flash router, PANEL_DIM | `MH1/` (08-19 tree + `mh1-dimset.diff`) | dimset: hex `1110c60a…`, bin `bf21f762…` | YES, byte-for-byte (hex+bin) | SWD only (openocd, mux ch 3) — not by `loadfw` |
| H1S1 | STM32U575RIT6 | codec/595/power-word interface | `H1S1/` (= `~/build-h1s1`) | `H1S1.shex` `19a5492d…` | YES, byte-for-byte | `app cli loadfw H1S1` (after `sreset.py` if needed) |
| H1S3 | STM32F030R8T6 | right switch panel (talkback variant B) | `H1S3/` (= unit `s131fw/H1S3-B`) | `H1S3.shex` `43efd43f…` (id H1S4) | YES, byte-for-byte | `app cli loadfw H1S3` |
| H1S4 | STM32F030R8T6 | left switch panel + pedal relay | `H1S4/` (S139 base + S167 relay) | `H1S4.shex` `ff79052e…` (id H1S3) | YES: base `f54848b0` and relay `ff79052e`, both byte-for-byte | `app cli loadfw H1S4` |
| P1 | STM32C031K4U6 | foot pedal | `P1/` | `P1-cc.bin` `793aa3f5…` (bench pedal, OPTR `0xFFFFFEAA`) | YES, `P1.bin` `baf55b3b…` and `P1-cc.bin` byte-for-byte | over the J8 cable: relay + ROM bootloader (8E1) |

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

Tools here: `hex2shex.py` (Intel hex → shex, MCU id as arg), `sreset.py` (S_RESET before `loadfw`; runs on the unit's CM4).
