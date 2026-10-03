provenance: AI-drafted 2026-10-03 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S167 — the P1 pedal over its cable: relay, firmware, ROM bootloader

MW-D24-2 (rev C digital, interim R107 = 300R → 5.0 V at J8), one P1 rev B pedal
with PW's serial-program mod. Everything below was run on the unit on
2026-10-03; logs are in this folder.

## Status A–F

- **A, see the pedal: DONE.** The path is CM4 `/dev/serial0` → MH1 → slave bus →
  H1S4 USART2 (PA2 TX pin 16 = P44 = PDL_TX, PA3 RX pin 17 = P45 = PDL_RX) →
  U36/U37 → J8 → P1. The shipping H1S4 (`f54848b0`) only ever SENT to the pedal
  (`:`/`.` on every MH1 blink, every 254 ms). It never read PA3, so no
  reply could reach the host. That was the one gap in the chain.
- **B, relay: DONE, flashed under PW's GO.** H1S4 `ff79052e` (S139 image +
  `pedal_relay.cs`). Host ↔ pedal bytes are carried as `/%` comment lines
  through MH1, which is UNCHANGED. Tool: `tools/pi/d24_pedal.py`.
- **C, P1 firmware: DONE.** `p1-fw/`, register level, -Os. `P1.bin` (common-anode
  display) 2264 B, `P1-cc.bin` (common-cathode, this pedal) 2644 B, of 16 384.
  The pedal runs `P1-cc` (`1.0-s167-cc`).
- **D, first program: SOLVED, no probe needed.** A factory-fresh C031 enters its ROM
  from the empty-flash check at power-up. The first program went over the cable
  (below). The J5 jumper route cannot work: factory nBOOT_SEL = 1.
- **E, ROM proof: DONE.** First program, update from the running app, and a
  power cut mid-write with retry, all over the cable.
- **F, this write-up.**

## Unit state after S167

| device | image | change |
|---|---|---|
| H1S4 | `ff79052ef96b09976173bb842a11382a` | FLASHED (relay). Rollback `/home/app/firmware/H1S4.shex.bak-s167-pre` = `f54848b0` |
| H1S1 | `19a5492d` | not flashed; restarted by the loadfw S_RESET/S_RUN |
| H1S3 | `43efd43f` | as H1S1 |
| MH1 | not flashed (`MH1.elf 0fe9717a` on disk) | reset by S_RESET only |
| P1 | `P1-cc.bin` `793aa3f5…`, OPTR `0xFFFFFEAA` | new (was blank) |

After the flash the runner's own restore was re-run: S_RUN + codec reinit, 595
chain SAFE `VERIFIED 200/200`, ensure-pair "nothing written". Its state files
were byte-identical before and after. The relay is left OPEN at 8N1, which
stops blink forwarding so the pedal holds its lamps; `/%X` closes it.

## The relay (H1S4 `pedal_relay.cs`)

Host lines, all starting `/%`, which every panel MCU ignores as comments:
`/%O<N|E>[baud]` open, `/%T<hex>` send ≤ 48 bytes, `/%X` close, `/%I` identity.
Pedal bytes come back as `/%r<hex>` (flushed after 2 ms idle or 40 bytes)
through the normal S2/S3 handshake. With the relay closed, behaviour is exactly
S139.

**MH1 flow control is mandatory:** MH1 has ONE 100-byte host-line buffer and
answers `+` once it has forwarded a line to the bus. A second line sent before
that `+` overwrites the first in flight. This lost a 48-byte write packet on
the first attempt. `d24_pedal.py` waits for `+` after every line.

**Speed ceiling:** the pedal leg (H1S4 USART2) accepts 1200–115200 baud, 8N1 or
8E1. 115200 is also the top of the C031 ROM's auto-baud range in practice and
what was proven. The host leg and the bus are fixed at 115200 8N1 (MH1
`HOST_BAUD`/`SYSTEM_BAUD`), with hex doubling and one line per `+`. Measured:
64-byte ROM writes at ~1.3 KB/s (2648 B written in 2.0 s, read back in 1.3 s).
Round trip host → pedal → host: 5–10 ms. The ROM protocol is request/ACK with
no inter-byte timeout, so line framing is transparent to it. H1S4 regenerates
the timing at the pedal end, so the ROM auto-bauds on H1S4's clock.

## The P1 application (`p1-fw/main.c`)

USART1 PA9/PA10 AF1 115200 8N1; PC14/PA1 (old TX/RX, still on the nets) are
inputs; SW1 PC15 and SW2 **PB2 (pin 17)** with pull-ups. Commands: `:` all on,
`.` all off (the stub's behaviour), `V` → `P1 <ver> uid=<96 bit> optr=<OPTR>`,
`S` → `S<sw1><sw2>` (also sent on every debounced change), `L<4 hex>` lamp
bitmap, `D0..D9` brightness, `!BOOT\n` enter the ROM. A 300 ms lamp test runs
at power-up. The stub never lit anything: it never started TIM3, so neither
DIM rail was ever switched on.

**Option bytes.** Factory `0xFFFFFEAA` (RDP 0xAA level 0, nBOOT_SEL 1, nBOOT1 1,
nBOOT0 1). `!BOOT` writes `0xFBFFFEAA` (nBOOT0 = 0) and relaunches the option
bytes, so the part restarts in the ROM. After the ROM's Go, the NEW app sees
nBOOT0 = 0 with nBOOT_SEL = 1, writes `0xFFFFFEAA` and relaunches. The pedal
then reports `optr=FFFFFEAA` itself. The host never writes option bytes.

## Step E record

| case | result | log |
|---|---|---|
| first contact, blank part | relay opened at 8E1 BEFORE re-plug; `7F` → `79`; Get v3.1, 11 cmds; Get ID **0x453**; Get Version 3.1 | tasks.md 15:11 |
| first program | erase 0.04 s, write 1.7 s, verify 1.05 s, Go; 2.8 s total (2216 B). The first try was lost to the MH1 `+` rule; `rom-recover` cleaned up the ROM without a re-plug | `flash-2.log` |
| update from the running app | `!BOOT` acked in 10 ms; relay to 8E1 19 ms later; ROM OPTR `0xFBFFFEAA`; 2644 B in 3.34 s; app `optr=FFFFFEAA` 2.6 s after Go | `update-1.log` |
| power cut mid-write | cut at block 11 (16:33:13; PW pulled ~16:33:15). ROM ACK 6.1 s later with no extra re-plug; OPTR still nBOOT0 = 0, so the part boots the ROM, not the broken image; 704 B intact; full retry 3.36 s; app `optr=FFFFFEAA` | `powercut-1.log` |

**Rule found by the hub:** a ROM that must auto-baud takes the FIRST byte after
power-up. With the relay closed, H1S4's `:`/`.` forwarding trains it wrongly,
and it stays deaf until the next power-up. So the relay must be open (at 8E1)
BEFORE the pedal powers up, and the first byte must be 0x7F.

## The update procedure as the D24 app would run it

1. Stop all other bus users. `/%ON115200`; `V` → record version and `optr`.
2. Send `!BOOT\n`, wait for the echo, then immediately `/%OE115200`. Blink
   forwarding stays off, so the ROM's first byte will be ours.
3. Send `7F` → `79`. Get ID must be `0x453`. Read OPTR: nBOOT0 must be 0.
4. Extended Erase (mass), write in 64-byte blocks, read back and compare, then
   Go 0x08000000.
5. `/%ON115200`, `V` → new version, `optr` nBOOT0 = 1. Done.
6. On ANY failure from step 3 on, keep the relay at 8E1. Send `7F` once a second
   until `79` (a power-cycle of the pedal is needed if the ROM was trained
   wrongly), then repeat from step 3. The part cannot be bricked by an
   interrupted write.
   Remaining unguarded window: the few ms of each option-byte reload.

## Step D: getting firmware into a pedal the first time

- **Recommended: no probe at all.** Every new P1 is a blank C031. Open the relay
  at 8E1, power the pedal (plug it in), and program it over the cable as above.
  This is the factory path and it is proven.
- ST-Link at J5 is only needed to recover a pedal whose app cannot run `!BOOT` and
  whose nBOOT0 is 1 (a bad image that boots). A J5 mass erase (`STM32_Programmer_CLI
  -c port=SWD -e all`) makes it blank again, and the cable path works again.
- J5 pin 2 → pin 1 (BOOT0 high) does NOTHING on this part: the factory OPTR has
  nBOOT_SEL = 1, so the BOOT0 pin is ignored.
- Keep RDP at level 0. Level 1 blocks the ROM's Read (and so verify).

## Hardware findings for the next P1 rev

1. **Display fitted is an FJ8102AY = common CATHODE** (Zhihao "A" suffix; the
   design wants common anode, e.g. Kingbright SA08-11YWA or FJ8102**B**Y). It
   can never light on the DIM0 high side. Pinout verified on the part by a
   lamp walk: commons 3/5/11/16, a=1 b=14 c=12 d=10 e=4 f=2 g=13, left dot 6,
   right dot 9. Interim on this pedal: **Q3 removed, DIM0 to GND, `P1-cc`**
   (segments driven high through 470 Ω, ≈2.8 mA each, software dimming).
   Working; P1 regulator input 4.95 V with everything lit.
2. **Q3/Q4 (2N4403) are inverted, on the schematic and on copper:** emitter on
   the DIM rail, collector on +3V3 (PW meter: emitters follow the rails, 3.3 V
   on / 0 V off). They work only in inverse mode at low gain. Fix: emitter to
   +3V3, or a logic-level P-MOSFET per rail.
3. **Schematic symbol errors on U2 (STM32C031K4U6):** pin 17 is PB2, not PB15;
   pins 26–29 are PA15/PB3/PB4/PB5, not PD0–PD3. The SA08 symbol's pin 6 has
   no chip on the SA08-11YWA.
4. **The mod becomes the design:** USART1 on PA9 (pin 19) / PA10 (pin 21), the
   ROM bootloader's pins on the UFQFPN32 (AN2606: the PA11/PA12 remap applies
   to TSSOP20/UFQFN28 only). SW2 moves to PB2. Keep the 10K pull-up on the TX
   net: the SN65LVDS1 input has a pull-down, so an undriven line reads as a
   break.
5. BOM note: "common anode display only; no A-suffix substitutes".

## Rev D / power MCU (CHANGE 6)

The ROM sends no heartbeat. If the power MCU drops the pedal supply on heartbeat
loss, an update or a recovery would be cut every time. The power MCU needs an
**update hold**: a host command that suspends the heartbeat check for a bounded
time (e.g. 60 s, re-armable), with the supply held on. With rev D's switched
pedal supply, the D24 can also do what PW's hand did today: cut and restore pedal
power with the relay open at 8E1. That gives automatic recovery of a mis-trained
or wedged ROM and removes the last hand step.

## Hub items

- 🔴 **defs fw.csv:** `PedalTx` P44 = H1S4 **PA2, pin 16, USART2_TX**; `PedalRx`
  P45 = **PA3, pin 17, USART2_RX** (D24 Left Switch schematic p2). The verify=1
  flags can be cleared.
- 🔴 **Where the firmware lives** (P1 and the panel MCUs are in no Matrix
  repo; the H1S1 truth is `~/build-h1s1` on one machine). Recommendation:
  **`MW/D24/FW/<MCU>/` in this repo** (CLAUDE.md already allows `FW/` in a
  product tree): `P1/` (today's `s167/p1-fw`), `H1S1/`, `H1S3/`, `H1S4/`
  (S139 base + relay), `MH1/`. Commit Core sources, linker scripts, makefiles and
  the flashed `.shex`/`.bin` with md5. Leave ST `Drivers/` out and record the
  CubeMX pack version. Alternative: one `invirco/panel-fw` repo shared by D24
  and D32, if the panels are to be shared across products. Until ruled, S167's
  sources stay under `MW/D24/DSP/s167/`.
- Runner: still PID 11543. It went past ENTER at some point after 14:33 and is
  waiting at **P13 (WRONG_SOCKET: tone on MIC 1, not MIC 2)** for the operator,
  rails UP, last log write 16:28. Its patch station uses SPI only, so it did not
  share `/dev/serial0` with this session.
