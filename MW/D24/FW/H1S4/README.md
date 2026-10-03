provenance: AI-drafted 2026-10-03 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# H1S4 — left switch / panel MCU + pedal relay

STM32F030R8T6 on the left switch board. Peer behind MH1; since S167 also the host's relay to the P1 pedal (USART2 PA2 PDL_TX / PA3 PDL_RX → U36/U37 → J8 → P1). Wire protocol: header of `Core/Inc/pedal_relay.cs`.

- Source: this folder = base **S139** (unit `fwbuild/H1S4` + `MW/D24/DSP/s139/gen/H1S4/matrix.cs` + `s139/gen/matrix.h`) **plus the S167 relay** (`pedal_relay.cs`, hooks in `stm32f0xx_it.c`, `matrix.cs`; `relay-vs-f54848b0.patch` is the delta).
- Needs **STM32Cube FW_F0 V1.11.5** for `Drivers/`.
- Build: `../build-mcu.sh <MCU> <path-to-Drivers>` (arm-none-eabi-gcc 14.2.1 20241119, Debian `15:14.2.rel1-1`; CubeIDE used 13.3.rel1 — the image is identical). Drivers/ is not stored here.
- **Proof (S168, rebuilt from clean):** base tree → `image/H1S4.base-f54848b0.shex` md5 `f54848b0d63751fb8cf3fbb17dc17ebe` = the S139 image, byte-for-byte. This folder (relay) → `image/H1S4.shex` md5 `ff79052ef96b09976173bb842a11382a` byte-for-byte (hex `65113a26…`). The base is reconstructible by reverting the three relay files with the patch.
- Image on MW-D24-2: `ff79052e` (relay), flashed 2026-10-03 14:05Z. Rollback: `/home/app/firmware/H1S4.shex.bak-s167-pre` = `f54848b0`, then `sreset.py` + `app cli loadfw H1S4`.
- **How flashed** (on the unit, `matrix-app` and the runner NOT using the bus): put the `.shex` in `/home/app/firmware/<MCU>.shex`; if `loadfw` fails at its MH1 loopback probe (MH1 in run mode) run `python3 sreset.py` (S_RESET, `*\n` on `/dev/serial0`, here in `FW/`) first; then `app cli loadfw <MCU>` (`OK: <MCU>` in ~22 s). Keep the previous image as `<MCU>.shex.bak-*` for rollback. The .shex header id is a socket id and is CROSSED for the left/right switch MCUs (S135): the file named `H1S3.shex` carries id `H1S4` and `H1S4.shex` carries id `H1S3`; `hex2shex.py` and `build-mcu.sh` already do this.
- Pedal path: relay commands `/%O<N|E>[baud]`, `/%T<hex>`, `/%X`, `/%I` via `tools/pi/d24_pedal.py`. Read S167 report (`MW/D24/DSP/s167/s167-report.md`) before using: ROM auto-baud rule, relay left open at 8N1.
