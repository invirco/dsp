provenance: AI-drafted 2026-10-03 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# H1S3 — right switch / panel MCU

STM32F030R8T6 on the right switch board (talkback LEDs, radio-group LEDs, encoder rings). Peer behind MH1. Shipped as "variant B" (`WrTalkbackLeds()` + `RdTalkbackSwitch()`).

- Source: this folder = the unit's `/home/app/s131fw/H1S3-B` (S131's rebuild of S135 variant B at pack generation `46109e9fb812`). NOT `/home/app/fwbuild/H1S3` and NOT `s139/gen/H1S3` — both build a different image (`8eeafb4f…`, s139 generation).
- Needs **STM32Cube FW_F0 V1.11.5** (CubeMX 6.14.1) for `Drivers/`.
- Build: `../build-mcu.sh <MCU> <path-to-Drivers>` (arm-none-eabi-gcc 14.2.1 20241119, Debian `15:14.2.rel1-1`; CubeIDE used 13.3.rel1 — the image is identical). Drivers/ is not stored here.
- Image on MW-D24-2: `image/H1S3.shex` md5 `43efd43f100dc9396fa1f351cbdd0ba6` (header id `H1S4`, see below). **Reproduces byte-for-byte** with `build-mcu.sh H1S3` (hex md5 `7144af6d…`, equal to `MW/D24/DSP/s131/H1S3-B/H1S3.hex`). Provenance: `MW/D24/DSP/s131/s131-report.md`.
- **How flashed** (on the unit, `matrix-app` and the runner NOT using the bus): put the `.shex` in `/home/app/firmware/<MCU>.shex`; if `loadfw` fails at its MH1 loopback probe (MH1 in run mode) run `python3 sreset.py` (S_RESET, `*\n` on `/dev/serial0`, here in `FW/`) first; then `app cli loadfw <MCU>` (`OK: <MCU>` in ~22 s). Keep the previous image as `<MCU>.shex.bak-*` for rollback. The .shex header id is a socket id and is CROSSED for the left/right switch MCUs (S135): the file named `H1S3.shex` carries id `H1S4` and `H1S4.shex` carries id `H1S3`; `hex2shex.py` and `build-mcu.sh` already do this.
