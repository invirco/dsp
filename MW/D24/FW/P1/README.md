provenance: AI-drafted 2026-10-03 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# P1 — foot pedal MCU

STM32C031K4U6 (UFQFPN32, 16 KB flash) on the P1 pedal board (rev B, serial-program mod: USART1 PA9/PA10 to the J8 LVDS pairs; SW2 on pin 17). Application: LEDs/display, two footswitches, identity reply, ENTER-BOOTLOADER command.

- Source: this folder (was `MW/D24/DSP/s167/p1-fw`, derived from the stub in `~/build-p1`). Headless `Makefile`; CMSIS headers only (no HAL): `make CUBE=~/build-p1` (`Drivers/CMSIS`). Needs **STM32Cube FW_C0 V1.4.0** (CubeMX 6.14.1) for `Drivers/CMSIS`. arm-none-eabi-gcc 14.2.1 20241119, `-Os`.
- Builds (rebuilt in S168, both byte-identical to the S167 files):
  - `P1.bin` — common-anode display (the BOM part): md5 `baf55b3bfc63f30230a252de696307d4`, 2264 B text. `make P1.bin`.
  - `P1-cc.bin` — common-cathode (rev B interim, pedals built with FJ8102AY; Q3 out, DIM0 to GND), `-DSEG_CC=1`, version string `1.0-s167-cc`: md5 `793aa3f5a83e7184b1711f73beabbf9d`, 2636 B text. `make P1-cc.bin`.
- Image on the bench pedal (plugged into MW-D24-2 J8): **`P1-cc.bin`**, flashed 2026-10-03, OPTR `0xFFFFFEAA`.
- **How flashed:** over the cable only. Host `d24_pedal.py` (opens the H1S4 relay) → `!BOOT` → relay at 8E1 → ROM bootloader (AN2606): 0x7F sync, Get ID `0x453`, mass erase, write, verify, Go; first program on a blank part works the same (ROM entered on empty flash). Procedure in the S167 report ("update procedure"); power-cut mid-write proven recoverable. No SWD needed. Rev D requirement: see `../README.md`.
