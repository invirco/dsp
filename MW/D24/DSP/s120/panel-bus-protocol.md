provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The D24 panel bus, written down

The errata item "the panel wire protocol exists only in firmware" (dsp `tasks.md`,
S120 §1). This is that protocol, read off the firmware that is flashed on
MW-D24-2 and checked against the netlist and against the part. It is a
**candidate for `defs`**: nothing here was invented, and nothing here is a
decision — it is a description of what the three firmwares already do.

Sources, all read rather than recalled:

| what | where |
|---|---|
| the token set and the boot sequence | `_mx/MW/D24/FW/MH1/Core/Inc/Project.h:79-108` |
| the master's loop, slave polling and host relay | `_mx/MW/D24/FW/MH1/Core/Src/main.c` (`CheckS`, `CheckHost`, `Blink`, `TxS`, `WaitForNotBusy`) |
| the slave's loop, message decode and cell store | `_mx/MW/D24/FW/H1S3/Core/Inc/matrix.cs` (`Poll`, `Eol`, `Rx_Fun[]`, `RdRadioSwitch`, `WrRadioLed`) — H1S4 and H1S1 are the same file with different tables |
| the copper | mx26 `docs/d24-signals-index.md:1518-1558`, `docs/d24-netlist-global.csv` G2632/G2702/G2703 |

---

## 1. The wires

There is ONE bus. It is two UART lines and one flow-control line, shared by the
master and every slave, and the CM4 is not on it.

| name on the DSP board | on the digital board | on a switch board | direction | what it is |
|---|---|---|---|---|
| `M MCU_P47` (G2702) | `SRX` | `MCU_RX` | master → slaves | every slave receives this |
| `M MCU_P48` (G2703) | `MRX` | `MCU_TX` | slaves → master | every slave transmits on this |
| `LOGIC_BUSY` (G2632) | `BUSY` | `MCU_BUSY` | slaves → master | wired-low "I am busy", open when idle |

Both UART lines run at **115200 8N1**, and the slaves' `USART1` is configured
exactly there (`MX_USART1_UART_Init`). The master's link to the host is a
SECOND, separate UART:

| net | direction | pins |
|---|---|---|
| `M MCU_P17` (G2691) = `PI_GPIO14` | host → master | CM4 `J24.55` (UART0 TX) → M MCU `U8.32` |
| `M MCU_P18` (G2692) = `PI_GPIO15` | master → host | M MCU `U8.29` → CM4 `J24.51` (UART0 RX) |

**The CM4 touches neither `SRX` nor `MRX` nor `BUSY`.** G2702 and G2703 land on
`digital:J17.47/.48`, which is the DSP card connector, not `J24`, which is the
CM4 socket; the only `J24` pins on this path are the two host UART pins above.
So a host cannot listen to the panel bus, and cannot speak on it, without a wire
that does not exist on this hardware.

Besides the two panels the bus carries the S MCU (`U7.42` = MRX, `U7.43` = SRX)
and the LOGIC CPLD (`U3.71/.72`), which sit on it as peers.

Each slave also has a PRIVATE pair of handshake lines to the master — not a bus,
one pair per slave slot:

* **data ready**, slave output, driven **LOW** when the slave has something to
  send (`S2_Pin` in the slave's own names).
* **data request**, master output, driven **HIGH** to tell that one slave to
  transmit now (`S3_Pin` in the slave's names).

The master owns eight such pairs, `S2/S3`, `S6/S7`, `S10/S11` … `S30/S31`
(`CheckS()`); slot 1 is the S MCU, slot 3 and slot 4 are the two switch boards.
`S2S_Pin` flips the bus transceiver between master-to-slave and slave-to-master.

---

## 2. The message

Every message is a line of ASCII terminated by `\n` (0x0A). There is no length,
no checksum and no address field beyond the characters themselves: the ALPHABET
says what each character is.

* **address nibble** — `h i j k l m n o p q r s t u v w` = 0x0 … 0xF
  (`A_00` … `A_0F`: `a = (a << 4) + nibble`)
* **data nibble** — `0`-`9` and `A`-`F`, upper or lower case
  (`D_00` … `D_0F`: `d = (d << 4) + nibble`)
* **`\n`** — `Eol()`: commit. The accumulated address is looked up in the
  slave's own `MATRIX[]`; if it is there, the accumulated data is stored as that
  cell's RECEIVED value and its receive flag is raised. Then the address and the
  data are cleared.

So `Sys001Skin001` (address 5412 = 0x1524) carrying the value 7 is the seven
bytes `imjl7\n`, and the same cell carrying 0x0C is `imjlC\n`.

A slave emits only the nibbles a value needs: `Poll()` writes an address nibble
only while `MATRIX[ptr]` still has bits at or below it, and a data nibble only
while the value does. **A cell whose value is zero arrives as the bare address
with no digits at all**, which is a real answer of zero and not a truncated
line.

### Control characters

These are single characters followed by `\n`, and they are not cells. The
master relays them both ways; a slave executes them out of `Rx_Fun[]`.

| char | name | what it does on a slave |
|---|---|---|
| `&` | `S_TEST` | arm the identity string; the next transmit sends `testMessage[]` (`// H1S3 SW Right\n`) |
| `:` | `S_BLINK_ON` | blink phase on — the master emits this every 250 ms |
| `.` | `S_BLINK_OFF` | blink phase off |
| `?` | `S_HELP_ON` | help mode: received cell data is DISCARDED, not stored |
| `;` | `S_HELP_OFF` | help mode off |
| `/` | `S_COMMENT` | ignore this line's data (a log line, not a cell) |
| `~` | `S_FILL_START` | matrix fill: `Eol` INCREMENTS the address instead of clearing it |
| `\|` | `S_FILL_STOP` | matrix fill off |
| `-` | `S_TICK` | 100 ms tick, unused on the panels |
| `+` | `S_RUN` | to the master: leave the flash dispatcher and run. FROM the master to the host: "I have forwarded your line, send the next one" |
| `$` | `S_SCAN` | master only: reset every slave and enumerate |
| `#` | `S_FLASH` | master only: enter the firmware update dispatcher |
| `*` | `S_RESET` | reset the hardware |
| `@` | `S_ECHO` | master only: transparent echo to the S MCU |

`?` is a trap worth naming: while help mode is on the panels still TRANSMIT key
events but silently drop everything written to them, so indicators freeze while
presses keep arriving.

---

## 3. Who speaks when

The master's whole main loop is four calls with a `BUSY` wait between each:

    WaitForNotBusy(); Blink();      // the 250 ms bus heartbeat
    WaitForNotBusy(); CheckS();     // every slave that has raised data-ready
    WaitForNotBusy(); CheckHost();  // one line from the host, if one is waiting
    WaitForNotBusy(); CheckDebug();

`WaitForNotBusy()` spins while any slave holds `BUSY` low. A slave drives `BUSY`
low for the whole of `Eol()` — the address lookup and the store — and releases
it at the end, so `BUSY` means "a slave is mid-decode, put nothing else on the
wire".

**Slave to master** (`CheckS`):

1. the slave finds a cell with its transmit flag raised (a press) or its
   identity armed, and pulls its data-ready line LOW;
2. the master sees data-ready low, waits for `BUSY`, raises that slave's
   data-request line;
3. the slave, inside its own `Poll()`, sees data-request high and transmits ONE
   message, then raises data-ready again;
4. the master drops data-request and waits for `BUSY`. The slave spins until
   data-request is low again before returning, which is what keeps two slaves
   off the wire at once.

It is a hardware handshake, not a timed poll: nothing waits on a clock.

**Host to slave** (`CheckHost`): the master forwards the host's line to the bus
byte for byte, waits for its own transmitter to go idle, and only then writes
`+\n` back to the host. **That `+` is the acknowledgement that the line has
reached the slaves**, and the host must wait for it before sending the next one.

**Master to host**: whatever a slave sent is relayed verbatim (`TxSmessage`),
interleaved with the `:`/`.` heartbeat. The heartbeat is NOT newline-aligned
with cell traffic, so a reply arrives as `.:imjl7` at least as often as on a line
of its own — parse the stream for the cell, never for a line.

---

## 4. Panel controls, as cells

A switch board holds four cells: `Sys001Enc001`, `Sys001Skin001`,
`Sys001Test001`, `Sys001Test002`. Two of them carry every switch and every
indicator on the board.

**Switches are a RADIO GROUP.** `rsw[]` gives each switch a port, a pin and a
`radioData` index. `RdRadioSwitch()` fires when the pin reads low AND the cell's
transmit value is not already that index; it then sets the transmit value to the
index and raises the flag. So a press sends **the pressed button's index**, and
pressing the same button twice running sends once.

**Indicators follow the RECEIVED value, not the switch.** `WrRadioLed()` lights
the one indicator whose `radioData` equals the cell's received value and turns
every other one off. A press does not move an indicator; only a write from the
host does. Writing 0 lights none.

The indicator drive is unusual and worth writing down: ON is the pin
reconfigured as push-pull output and driven high, OFF is the pin reconfigured as
an INPUT — a dim state through the pull-up rather than a hard off.

### Right switch board (H1S3), `Sys001Skin001`

| index | button | indicator |
|---|---|---|
| 1 | HOME | white ring |
| 2 | MENU | white ring |
| 3 | +48 | white ring |
| 4 | FEEDBACK | white ring |
| 5 | CH ASSIGN | white ring |
| 6 | FX MUTE | **red** ring (the white ring is always on) |
| 7 | MUTE | white ring |
| 8 | SCENE | white ring |
| 9 | L | white ring |
| 10 | C | white ring |
| 11 | R | white ring |
| 12 | MONITOR | white ring |
| 13 | REC/PLY | **red** ring (the white ring is always on) |
| 14 | STUDIO CTL | white ring |

`Sys001Enc001` carries the encoder: a detent sends the ring's new position
1…8 (wrapping both ways), and the eight ring indicators follow the received
value as their own radio group.

Two indicators are outside the radio group entirely. `MainInit()` drives PB11
and PF1 high and leaves them there, so the white ring around FX MUTE and the
white ring around REC/PLY are lit whenever the board is powered and no write can
move them.

The talkback switch and its two indicators, the mini-jack sense, and the
temperature, blower and fan lines are wired to this processor and have **no cell
bound**, so they are not reachable from the host at all.

### Left switch board (H1S4), `Sys001Skin001`

| index | button | indicator |
|---|---|---|
| 1 | MONO AUX | white pair |
| 2 | STEREO AUX | white pair |
| 3 | FX | white pair |
| 4 | EQ | white pair |
| 5 | AUX ON FADERS | white pair |
| 6 | OVERVIEW | white pair |

**The left board uses the SAME CELL and the SAME INDICES 1…6 as the right
board's HOME…FX MUTE.** Writing 3 lights FX on the left board and +48 on the
right; a press of either arrives at the host identically. See S120-1.

---

## 5. Timings, measured on MW-D24-2 (2026-09-26)

| hop | what was timed | result |
|---|---|---|
| host → indicator | the cell line out, to the master's `+` ack | **1.74 … 1.85 ms** mean over three runs of ten; 1.72 fastest, 2.47 slowest |
| host → slave → host | one full cell round trip (an S MCU guard fetch) | **3.07 ms** mean of 10 (2.92 … 3.39) |
| panel → host relay | `&` out, to each identity line arriving | S MCU 3.2 ms, one panel 6.0 ms, the second panel 9.8 ms — about **3 ms per slave** of the master's sweep |
| master heartbeat | `:`/`.` edges over 3.0 s | **250 ms** |
| slave loop period | bounded by the gap between two slaves' identity lines less the 1.5 ms the string takes on the wire | **under 2 ms** |

---

## 6. What this does not say

* The firmware update dispatcher (`S_FLASH`, `UpdateFirmware`, the per-record
  ACK) is a separate protocol on the same wires and is not described here.
* `Sys001Test001` / `Sys001Test002` are declared on all three slaves and are used
  by the S MCU alone, as the codec register address and data pair. Writing the
  DATA cell triggers SPI on the converter board. A panel test mode must not use
  that cell (`tools/pi/codec4619.py` has the full note).
* The blink group (`ledFollowSw = 0`) is a second indicator mode that nothing in
  the product currently enters.
