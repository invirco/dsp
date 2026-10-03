provenance: AI-drafted 2026-10-03 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# P1 — foot pedal MCU

STM32C031K4U6 (UFQFPN32, 16 KB flash) on the P1 pedal board (rev B, serial-program mod: USART1 PA9/PA10 to the J8 LVDS pairs; SW2 on pin 17). Application: LEDs/display, two footswitches, identity reply, ENTER-BOOTLOADER command, display polarity (S169).

- Source: this folder (was `MW/D24/DSP/s167/p1-fw`, derived from the stub in `~/build-p1`). Headless `Makefile`; CMSIS headers only (no HAL): `make CUBE=~/build-p1` (`Drivers/CMSIS`). Needs **STM32Cube FW_C0 V1.4.0** (CubeMX 6.14.1) for `Drivers/CMSIS`. arm-none-eabi-gcc 14.2.1 20241119, `-Os`.
- **Build (S169): ONE image, `P1.bin`, for both display polarities** — version `1.1-s169`, md5 `f0fd3cff8642e0547669b8cd003ee7dd` (`P1.hex` `565dc320…`), 4188 B text + 8 B data of the 14 336 B the linker may use (page 7 is the settings page). `make`.
- Retired builds (in git history, commit before S169): `P1.bin` 1.0-s167 common-anode `baf55b3b…`; `P1-cc.bin` 1.0-s167-cc `793aa3f5…`.
- Image on the bench pedal (plugged into MW-D24-2 J8): **`P1.bin` 1.1-s169 `f0fd3cff…`**, updated over the cable 2026-10-03 18:01 BST, OPTR `0xFFFFFEAA`; setting `auto`, decided `CC` by the probe. Logs: `bench-s169/`.
- **How flashed:** over the cable only. `tools/pi/d24_pedal.py update --bin P1.bin` on the unit's CM4 (opens the H1S4 relay, reads `V`, sends `!BOOT`, re-opens the relay at 8E1, ROM bootloader (AN2606): 0x7F sync, Get ID `0x453`, OPTR check, **page erase 0..n-1**, write, verify, Go, reads `V` again). First program on a blank part: `rom-id` + `rom-flash` after a re-plug with the relay open at 8E1 (S167 report, "update procedure"). Power-cut mid-write proven recoverable (S167). No SWD needed. Rev D requirement: see `../README.md`.

## Commands

115200 8N1. `:` all on, `.` all off, `S` switches (also sent on change), `L<4 hex>` lamp bitmap, `D0..D9` brightness, `!BOOT\n` enter the ROM — as S167. New:

- `V` → `P1 1.1-s169 uid=<24 hex> optr=<8 hex> disp=<CA|CC> by=<stored|probe|default> set=<auto|CA|CC> probe=<CA|CC|none|odd> adc=<ccA>,<ccF>,<caA>,<caF>`
- `PA` / `PC` store common anode / common cathode, `PU` store auto (probes again at once), `P?` read. Reply `P disp=.. by=.. set=..` (`P ERR` if the flash write failed). Applied at once; written only if it changed.

## Display polarity (S169, PW ruling 2026-10-03)

**Which polarity, in order:** a stored `CA`/`CC` setting wins; with `auto` (blank flash) the start-up probe decides; if the probe has no answer, **CA** (the BOM part, SA08-11YWA). Why CA as the fallback: it matches the design. On every board where the rail follows the firmware (the next rev, and rev B with Q3), a wrong guess is a dark display and nothing more. The one board where it is not dark is the rev B interim, and there the probe has answered every time (below).

**Where it is stored, and how it survives an update:** flash page 7 (`0x08003800`; the linker stops the image at 14 KB). It is an append-only log of 64-bit records (`0x503100vv`, `~`) and the last valid record wins, so a write cut by a power loss leaves the previous value in force. The page holds 256 records before it is erased and restarted. `d24_pedal.py rom-flash`/`update` now erase **only the pages the image covers** (ROM Extended Erase with a page list; S167 used a mass erase) and refuse an image that reaches page 7, so the setting survives an update. Proven on the bench: `PC` stored, update, `set=CC by=stored` after (`bench-s169/update-2.log`). As a second line of defence, `update` reads `set=` before the update and re-applies it if the new app reports it lost (that happens after a `--mass-erase` or a J5 erase). The re-apply path is exercised only off-target. A first program on a blank part starts at `auto`.

**The DIM0 rail.** The firmware drives every variant's rail at once. On each board, the drive that is not wired goes nowhere:
- next rev: PA4–PA7 (pins 11–14, tied to DIM0). ODR is set by one BSRR write and the four are switched to outputs by one MODER write, so they are never at different levels; HIGH for CA, LOW for CC.
- rev B with Q1/Q3: PB1 (DIM_0, TIM3_CH4) at 100 % for CA, 0 % for CC.
- rev B interim (bench pedal): DIM0 is GND, PA4–PA7 are not connected, PB1 drives only Q1's base (R23 takes 3.3 mA when it is high; harmless).
The rail never moves for brightness. A segment is lit at the level opposite the rail and dark at the rail's level, and `D` is software PWM on the segment pins (100 Hz, ten steps, `D9` = fully on) in both polarities. Until the polarity is decided, the segment pins are inputs.

**Wrong polarity, every combination** (display VR max 5 V, IR ≤ 10 µA at 5 V: Kingbright SC08-12SYKWA datasheet in `_mx/MW/D24/HW/All D24 PCBA rev A/MW_P1/`, the same family as the SA08; the SA08-11YWA sheet itself was not to hand):

| board | display | firmware | result |
|---|---|---|---|
| next rev | CA | CC | rail LOW on the anodes; lit cathodes HIGH = 3.3 V reverse, unlit 0 V: **dark** |
| next rev | CC | CA | rail HIGH on the cathodes; lit anodes LOW = 3.3 V reverse: **dark** |
| rev B, Q3 fitted | CA | CC | PB1 low, Q3 off, DIM0 floats; two segments through the common are always back to back: **dark** |
| rev B, Q3 fitted | CC | CA | Q3 on, DIM0 ≈ 3 V on the cathodes; lit anodes LOW = reverse: **dark** (with CC set it is also dark: Q3 cannot sink, the fault the interim fixed) |
| rev B interim (DIM0 = GND) | CC | CA | unlit segments driven HIGH into a grounded cathode: **inverted display at the normal 470R current (≈2.8 mA a segment)**. Not damage, but not dark either. The PW ruling's premise is true only where the rail follows the firmware |

No combination exceeds a pin or display rating. A third case to keep away from: a board where PA4–PA7 are wired to DIM0 *and* DIM0 is still grounded (a half-done rework). CA would then drive four pins high into GND. Each would be well past 20 mA, limited only by the pin itself. Do not combine the two reworks.

**Currents, next rev, everything lit** (STM32C031 datasheet DS13867 Rev 3: Table 22 absolute maxima IIO(PIN) ±20 mA, ΣI(PIN) 80 mA sunk / 80 mA sourced, IVDD 100 mA, IVSS 100 mA; §5.3.13 "Output driving current" ±6 mA at full VOL/VOH, ±15 mA relaxed; Table 51 VOH ≥ VDD−0.4 V at 8 mA, VDD−1.3 V at 20 mA. The datasheet gives **no per-port limit**, only per pin and the two sums):
- segment pin: (3.3 − ~1.9 V Vf at 3 mA) / 470 ≤ 3.0 mA (S167 estimate 2.8 mA), 9 segments (7 + two dots) ≤ 27 mA.
- rail pins: ≤ 27 mA shared by four pins = ≤ 6.8 mA each if equal. That is under the 8 mA point of Table 51, so the rail droops ≤ 0.4 V, which only lowers the segment current. If three of the four joints were open, one pin would carry it alone. That pin's own drop (≈65 Ω at 20 mA) against the LEDs self-limits at ≈ 12 mA: inside ±15 mA relaxed and ±20 mA absolute.
- LD1–LD4: two blue/white LEDs a pin, < 1 mA each at 470R, ≤ 2 mA a pin, ≤ 8 mA sunk. Their supply is DIM1 via Q4, not an MCU pin. PB0 base drive via R20 1k ≈ 2.6 mA sourced.
- CA: sourced = rail 27 + PB0 2.6 + TX ≈ 30 mA; sunk = segments 27 + LD 8 = 35 mA. CC: the same totals with segments and rail swapped. ΣI(PIN) ≤ 35 of 80 mA. IVDD ≈ 30 + core ≤ 3 (Table 28: ≤ 1.2 mA at 16 MHz, 25 °C, plus HSI48) ≈ 33 of 100 mA; IVSS ≈ 38 of 100 mA.

**Auto-detect (the default).** At start-up, before the lamp test:
- Every segment pin floats.
- Segment A (PA11 = ADC_IN11) and F (PA12 = ADC_IN12) are the only segment pins with an ADC input (DS13867 Table 12). They are probed on their 40 kΩ weak pulls (25–55 kΩ):
  - **CC probe:** rail LOW, pull-UP. A conducting CC segment sits at its Vf at ~40 µA, about 0.5 VDD. Open reads VDD.
  - **CA probe:** rail HIGH, pull-DOWN. A conducting CA segment sits at about rail − Vf. Open reads 0.
- **A digital read is not enough.** ~0.5 VDD sits between VIL 0.3 VDD and VIH 0.7 VDD (Table 50), so the IDR bit is a coin toss. Hence the ADC (12-bit, 160.5-cycle sampling, mean of 4).
- **Decision:** both segments must agree. Path windows: 1200–3300 counts (CC), 800–2900 (CA). Open: > 3700 (CC), < 400 (CA). Anything else is `odd` and falls back to the stored setting or CA.
- **During the probe** the current is ≈ 40 µA in at most two segments, for 2 ms per direction. A display of the other polarity is only reverse-biased, so nothing lights in the wrong sense.
- **By variant:**
  - next-rev CA → CA; next-rev CC → CC.
  - interim → CC (the CA probe's rail drive goes nowhere; DIM0 is GND).
  - rev B with Q3 and CA → CA (Q3 lifts DIM0).
  - rev B with Q3 and CC → `none`: DIM0 floats when Q3 is off, and that board cannot light in either sense anyway.
  - no display → `none` (pull wins both ways).
- **Measured on the bench pedal (interim, FJ8102AY CC):** `probe=CC`, adc `885,884,002,001`, then `888,887,004,004` and `886,885,002,001` on two later starts. The CC path reads 2181/4095 = 0.53 VDD ≈ 1.76 V, in the middle of its window. The CA probe reads open at ≤ 4 counts.
- **One caveat:** the ADC reads the pad with the pin in input mode, because the weak pull is needed. RM0490 asks for analog mode for ADC inputs, and analog mode disconnects the pull. It works on this part (the readings above), but it is outside the documented use. If it ever failed, the result would be `odd` or `none`, never a wrong answer, and the stored setting covers it.

**Bench proof, 2026-10-03 (MW-D24-2 J8, interim pedal, logs in `bench-s169/`):**
- Update from 1.0-s167-cc over the cable: pages 0–2 erased in 0.08 s, 4200 B written in 3.2 s, verified in 2.0 s, Go; `V` 1 s later reports `optr=FFFFFEAA` (nBOOT0 restored).
- `P?`/`PA`/`PC`/`PU`: all answered. The second update kept `set=CC`.
- Lamp walk: all 13 lamps one at a time, `D9`..`D0`, then all on: every command acked (`walk-1.log`). Visual confirmation: PW, 🔴 in tasks.md.
- `S` → `S00`.

**Not proven until a next-rev or re-worked pedal exists:**
- the CA drive (PA4–PA7 as the rail, and PB1 lifting Q3) lighting a CA display;
- the CA probe's *path* reading (only its open reading, ≤ 4 counts, is measured);
- the CC probe with the rail driven by PA4–PA7 rather than a hard GND;
- the four-pin rail sharing and the rail droop;
- the `none` result with no display fitted;
- that a power cycle (not a reset) keeps the setting. It is flash, and the two resets through the ROM and the option-byte reload kept it.
