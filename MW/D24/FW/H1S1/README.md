provenance: AI-drafted 2026-10-03 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# H1S1 — DSP/codec interface MCU

STM32U575RIT6 on the D24 digital board; the CM4's route to the AK4619 codec (CodecPoll), the 595 chain and the power-MCU words. Panel-bus peer behind MH1. Header id `H1S1`.

- Source: this folder = `~/build-h1s1` on the dev box (the ONLY source; never the unit's `/home/app/fwbuild/H1S1`, which carried the stale S139 generation). It is not a git repo upstream; this is its first commit.
- Needs ST pack **STM32Cube FW_U5 V1.7.0** (CubeMX 6.14.1) for `Drivers/` — take `STM32U5xx_HAL_Driver` + `CMSIS` from that pack (STM32CubeU5 on GitHub / CubeMX package manager).
- Build: `../build-mcu.sh <MCU> <path-to-Drivers>` (arm-none-eabi-gcc 14.2.1 20241119, Debian `15:14.2.rel1-1`; CubeIDE used 13.3.rel1 — the image is identical). Drivers/ is not stored here.
- Image on MW-D24-2 (2026-10-03): `image/H1S1.shex` md5 `19a5492d76e0f2faeda6059a045b3f2a` (36 421 B image). **Reproduces byte-for-byte** from this tree: the shex, via `build-mcu.sh H1S1` (hex md5 `68ea5cce…`, hex built by the original tree on 2026-09-28 is the same bytes through hex2shex). `Core/Inc/matrix.{h,cs}` is the generated cell table at pack generation `46109e9fb812`; regenerate it from defs only through the app's pack tool, never by hand.
- **How flashed** (on the unit, `matrix-app` and the runner NOT using the bus): put the `.shex` in `/home/app/firmware/<MCU>.shex`; if `loadfw` fails at its MH1 loopback probe (MH1 in run mode) run `python3 sreset.py` (S_RESET, `*\n` on `/dev/serial0`, here in `FW/`) first; then `app cli loadfw <MCU>` (`OK: <MCU>` in ~22 s). Keep the previous image as `<MCU>.shex.bak-*` for rollback. The .shex header id is a socket id and is CROSSED for the left/right switch MCUs (S135): the file named `H1S3.shex` carries id `H1S4` and `H1S4.shex` carries id `H1S3`; `hex2shex.py` and `build-mcu.sh` already do this.
