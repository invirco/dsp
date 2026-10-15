provenance: AI-drafted 2026-10-15 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# PWR — D24 power MCU (U34)

STM32F030F4P6 (TSSOP20, 16 KB flash, 4 KB SRAM) on the D24 digital board: rails, rocker, LED, save-and-shutdown handshake, analog converter clocks and, on rev D, the J8 pedal supply. One image for rev C and rev D (no revision detection). Moved here from mx26 `src/fw/pwr-mcu/` on 2026-10-15 (firmware home ruling, PW 2026-10-03); the mx26 folder keeps a pointer. Definition: mx26 `src/fw/d24-pwr-mcu-def.csv`; prose: mx26 `docs/ref-d24-pwr-mcu-overview.md`. Work record: `report-2026-10-15.md`.

## Layout

| file | what |
|---|---|
| `boot.c`, `bootcmd.c/.h`, `boot.ld` | 4 KB WRP bootloader @ 0x08000000: rails first (staggered after power-on), mailbox, app CRC check, update mode (option 2) |
| `main.c`, `p1.c/.h`, `pwr-mcu.ld` | 12 KB app @ 0x08001000: state machine, stagger, duty ramps, host link commands, J8 pedal supply |
| `link.c/.h`, `proto.h` | host link on AN_EN / PI_SD (pulse-width frames, CRC-16) and its commands — shared by both images |
| `config.h`, `board.h` | timings/thresholds; registers and pin roles |
| `mkimage.py`, `tools/gate.py` | app header length + CRC32; size/CRC gate |
| `flash-boot.sh`, `flash-app.sh`, `flash.sh` | SWD from the CM4, HOT-ATTACH ONLY (halt → write_image erase → verify → SYSRESETREQ; never `reset halt`) |
| `tests/` | off-target: link round trips, bootloader update against a RAM flash, pedal decisions against an RC model, host tool ↔ firmware cross-check |
| `image/` | the images this tree builds (below) |
| `baseline/` | the mx26 tree's images, reproduced byte-for-byte before any change |

Host side (on the CM4): `tools/pi/d24_pwrlink.py` (link commands, option 2 update), `tools/pi/d24_pwrrom.py` (option 4, ROM bootloader — hardware prerequisites not met, see the report).

## Build

`make` (arm-none-eabi-gcc 14.2.1, Debian `15:14.2.rel1-1`), `make check` = size/CRC gate + all off-target tests. Deterministic: two clean builds give the same bytes.

| image | bytes | md5 | state |
|---|---|---|---|
| `image/boot.bin` | 2 624 of 4 096 | `9b3a57f20865c570124c378e8229d053` | desk only, never flashed |
| `image/pwr-mcu.img` | 3 868 of 12 288 (len 0x0F18, CRC `0x78d6371a`) | `49a38c158a816fb79fff727aaffae190` | desk only, never flashed |
| `image/pwr-mcu-safe.img` | 3 856 (len 0x0F0C, CRC `0x31a855eb`) | `90c0f9907e695cdb2c7de38924db23be` | desk only (BENCH_SAFE) |
| `baseline/pwr-mcu.img` | 1 820 | `a4e15bbba28a16a13ba49c63820513e6` | mx26 f6c146c; never flashed; the md5 mx26 `d24-firmware.csv` declares today |
| `baseline/boot.bin` | 296 | `848f71d8786a96a17002a7bf5e128a7b` | mx26 ab03552 rocker-gate boot; never flashed |
| `baseline/pwr-mcu-safe.img` | 1 796 | `5708a885622f5bd627dea9dee350a227` | |

On MW-D24-2 (from the records, not re-read): app = mx26 0215bc4 (len 0x6A0, read back 09-15; rebuilds to `b3ca023a…`), bootloader = the 08-18 one that never touches the rail pins (rebuilds to `43bedeb0…`).

## Flash order (bench)

1. `flash-boot.sh image/boot.bin` with WRP lifted, then WRP back on — bootloader FIRST (incident 2026-09-15, lesson b).
2. `flash-app.sh image/pwr-mcu.img` (SWD), or afterwards over the link: `d24_pwrlink.py update --img pwr-mcu.img` (matrix-app stopped, AN_EN low, rocker ON).

Prereqs as before: +12 V present (mux gate drive), +5V5 ≥ 4.85 V measured before any halt.
