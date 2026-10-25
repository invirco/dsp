provenance: AI-drafted 2026-10-25 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# H1S1G0 — H1S1 on the DSP card rev D (U7 = STM32G0B1RET6)

The rev C H1S1 (`../H1S1/`, STM32U575) ported to the rev D card's G0B1 (DSPC MOD 5). S174, desk only: built, never run — no rev D card exists yet and nothing was flashed.

Pins: invirco/dspcard `review/stage2b-u7-pinmap.md` (stage 3d, PSU monitor removed) and `review/l11-report.md` (REV_ID straps), read at dspcard `8a85549`. Names follow the rev C `main.h` wherever the net is the same.

## What it does (rev C feature set, minus what rev D took away)

| | rev C H1S1 (U575) | this port (G0B1) |
|---|---|---|
| panel bus to MH1 | USART1 PA9/PA10 115200 8N1, TX open-drain, S2 ready / S3 request / BUSY, per-character vector table | **same protocol**, same pins (PA9/PA10 are also the G0B1 ROM bootloader's USART1, AN2606). Receive is a non-blocking FIFO drain with the error flags cleared before the HAL handler — the MH1 2026-08-19 fix; rev C still uses a blocking read in the ISR |
| RST_C (converters + 595 chain) | PA11, 100 ms low pulse at boot | **same** (PA11, pin 43). U7 is the **only** RST_C driver on rev D (S173-3) |
| RST_O (option cards, J3/J4.75) | not driven | **driven with RST_C** (PA12, pin 44), per the S174 dispatch |
| LED (S MCU_LED0) | PB6, ':' / '.' | same |
| CM4 chip selects, RDY lines | inputs, never driven | same (CS8 is PF0: the G0B1 has no PH0; CS6 is off U7 on rev D) |
| AK4619 init + codec cells `Sys001Test001/002` | yes (H1S1 SPI1 + CS_C) | **gone**: !CS_C is the CM4's CS6 on rev D; the app owns the codec (PW S173 Q5 (a)) |
| 595 mic-gain write at boot (`TestMicPres`) | yes | **gone**: !CS_M is the CM4's CS5; U7 only sees it as an input. The app sets the chain |
| SPI1 | master, shared copper with the CM4's boot bus | **never configured** (PB3/PB4/PB5 left at reset, analog). H1S1 cannot put traffic on the DSP boot wire |
| PSU monitor | pins present, never read | removed from the card (stage 3d); pins left at reset |
| board revision | none (PW L11 Q4) | REV_ID0-2 = PC1-PC3, pulls off, read once at boot (`Core/Inc/dsp_card_rev.h`, from S173) |
| announcement | `// H1S1 DSP` | `// H1S1 DSP G0B1 rev <code>` — the app matches `Contains("H1S1")`; `tools/pi/dspcard_id.py` reads it as positive card identification |
| `Sys001DspCardRev001` cell | — | coded (`RevCellPoll`, S173 proposal ruled Q1 (a)): value = strap code, reported once at boot, `0xFF` written = send again. **Built only when matrix.h defines the cell** — it is not in defs yet, so today's image does not carry it |
| option bytes | n/a | first run clears **nBOOT_SEL** (and keeps nBOOT1 = 1) so MH1's BOOT0 (S1) works on every later load (S173-6); one option-byte reload = one reset; RDP untouched |
| UCPD dead-battery | n/a | both strobes set in `HAL_MspInit`, so PA8 (SWD_EN0), PD0 (!CS_L), PD2 (STRX1) never carry the 5.1K Rd |

Clock: HSI16 → PLL → 64 MHz (rev C ran 160 MHz; nothing in the protocol is timed off the core clock).

## Build

```
./fetch-drivers.sh <dir>                    # ST repos at pinned tags -> <dir>/Drivers
../build-mcu.sh H1S1G0 <dir>/Drivers        # -> ../build-out/H1S1G0/H1S1G0.{elf,hex,bin,shex}
```

- Drivers: `stm32g0xx_hal_driver` v1.4.7 (`a0cf8a8b`), `cmsis_device_g0` v1.4.5 (`f576c24e`), `cmsis_core` v5.9.0_20250520 (`b7487de1`), all from github.com/STMicroelectronics, checked by commit in the script. Startup and `system_stm32g0xx.c` are cmsis_device_g0's templates; `stm32g0xx_hal_conf.h` is the v1.4.7 template with the unused modules off. Not stored in git (same rule as every MCU here).
- `matrix.h` is NOT copied here: it is the generated cell table, and the one copy is `../H1S1/Core/Inc/matrix.h` (generation `46109e9fb812`); `build-mcu.sh` exports its directory as `MATRIX_INC`.
- `Debug/makefile.linux` is hand-written (no CubeMX project yet); arm-none-eabi-gcc 14.2.1 20241119, `-O0 -g3` like the rev C CubeIDE Debug build. **0 warnings.**

S174 image (`image/`): `H1S1G0.hex` md5 `9d5eebd98e195e38f0e8e2490edfe917`, `H1S1G0.shex` (header id `H1S1`) `59707ab6c9b031ddc7a030d638115758`, 20 776 B image (text 20 136, data 640, bss 1 816; 512 KB flash, 144 KB RAM); `.bin` `5a0bc140…`. The hex is identical across rebuilds (the elf differs only in debug paths). The cell path compiles clean too, with a placeholder address (`EXTRA_CFLAGS=-DSys001DspCardRev001=0x7FF0`; not an image, not kept).

Flash only through `tools/pi/h1s1_flash.sh` (card guard first). The shex is named `H1S1G0.shex` on purpose; the guard stages it as the unit's `H1S1.shex` only after the card says rev D.

## Not testable without a rev D card (bench list)

1. The part boots at all: clock, SysTick, USART1 at 115200 with MH1, S2/S3/BUSY handshake timing at 64 MHz.
2. `// H1S1 DSP G0B1 rev 1` arrives through MH1 on `d24_bus_probe.py --mode stest`, and the app's MCU verification accepts it.
3. REV_ID reads code 1 (R90 up, R91/R92 down); a reading at 0 would mean the pads were still in analog mode.
4. RST_C / RST_O: levels and the 100 ms pulse on the copper; converters and the 595 chain come out of reset; RST_O's polarity on the option-card side (nothing on the card pulls it).
5. First load through MH1's `loadfw`: a blank G0B1 enters its ROM loader by the empty check; MH1's mass erase (`0x44` + `0xFFFF`) and 16-byte writes on the G0B1 loader; MH1's 100 ms loader-start wait. **Open question for the bench:** whether the G0B1 re-evaluates the empty flag on the NRST reset that ends the load, or only at power-on — if only at power-on, the first boot after a first load needs a power cycle.
6. nBOOT_SEL: the first run clears it and resets once; after that, S1 high + S0 pulse enters the loader (the second `loadfw` is the proof). Also that BOOT0/PA14 reads low in normal running (MH1 drives S1).
7. UCPD strobes: PA8/PD0/PD2 not pulled down after boot.
8. The cell, once defs carries it and the pack regenerates `matrix.h`: report at boot, `0xFF` re-send, no self-retrigger on the multi-drop bus.
