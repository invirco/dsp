provenance: AI-drafted 2026-09-26 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Runner interface — the harness as a patch back end

PW 2026-09-26: the audio test is **one list of signal paths**. Each entry is a
single D24 output going to a single D24 input, given by panel name, with its
measurement windows. The unit's runner owns the list and generates it from
defs. Two **patching back ends** sit behind one interface:

* **MANUAL** — the fallback, and the one that exists first. The runner prompts
  *"patch AUX 1 to MIC 1, then press Enter"*, measures, shows PASS or FAIL,
  and moves on to the next entry.
* **HARNESS** — the runner asks the harness to make the same connection, then
  measures it the same way. No operator is involved.

One `connect` makes exactly one path from the list. The harness holds no test
logic, and it is cable-equivalent: 0 dB, non-inverting, and balanced where the
cable would be balanced. The same windows therefore apply to both back ends.

## The interface (both back ends)

| call | HARNESS (USB CDC line) | MANUAL |
|---|---|---|
| `identify()` | `IDENT` | returns `manual` |
| `selftest()` | `SELFTEST` | no-op |
| `status()` | `STATUS` | the patch last prompted |
| `connect(out, in)` | `CONNECT "<out>" "<in>"` | *"Patch `<out>` to `<in>`, then press Enter"*. **No prompt if the list's `patch` id is unchanged**, e.g. the second conductor of a stereo lead |
| `clear()` | `CLEAR` | *"Remove the lead"*, only when the next patch needs the socket, and at the end |
| `terminate(in)` | `TERMINATE "<in>"` | *"Fit the 150 Ω terminator in `<in>`"*, or UNSUPPORTED (README Q14) |
| `phantom_sense(in)` | `PHANTOM "<in>"` | UNSUPPORTED, recorded as NOT RUN (a phantom-checker plug and a judge prompt is possible) |
| *optional* `fanout(out, [in…])` | `FANOUT "<out>" "<in>" …` | not offered. The runner falls back to one `connect` per path |
| *optional* `add(out, in)` | `ADD "<out>" "<in>"` | not offered |

**Selecting a back end:** the runner sends `IDENT` to every `/dev/ttyACM*`. If
a harness answers, the runner uses HARNESS. Otherwise it uses MANUAL. Nothing
else changes.

## Port names

Port names are the D24 panel names, compared case-insensitively and always in
double quotes on the wire:

* **inputs:** `MIC 1` … `MIC 24`, `TALKBACK`, `MINI-JACK 1 L`, `MINI-JACK 1 R`, `MINI-JACK 2 L`, `MINI-JACK 2 R`
* **outputs:** `AUX 1` … `AUX 8`, `MAIN L`, `MAIN R`, `C/LF`, `MONITOR L`, `MONITOR R`, `PHONES L`, `PHONES R`, `AUX A 1-2 L`, `AUX A 1-2 R` … `AUX A 7-8 R`

A stereo jack has two ports: L is the tip and R is the ring. The
machine-readable table, including catalog rows and where each port lands on
the harness, is `export/d24-harness-ports.csv`. `MAP` returns the same table.
The runner never sends a chain bit, a module number or a matrix address.

## Wire protocol (HARNESS)

USB CDC-ACM from the RP2040 (product string `M&W D24 test harness`). The
protocol is ASCII, with one command per line terminated by LF. A reply is zero
or more data lines followed by exactly one final line, either `OK …` or
`ERR <code> <text>`.

Every command that changes state is **atomic**. The harness computes the whole
image from scratch, shifts it, latches it, reads it back on CHAIN_RET,
compares it with what it sent, and waits **50 ms** for the gates to settle
(100 MΩ × 100 pF). Only then does it reply `OK`.

| command | effect / reply |
|---|---|
| `IDENT` | `OK harness=d24 fw=<ver> hw=A1 chain=24 map=<md5 of d24-harness-ports.csv>` |
| `SELFTEST` | Walks a 1 through the chain and expects 24 bytes, reads back the idle image, checks +15 V on ADC2, and checks PH_SENSE ≈ 0 with every mux off. Replies `OK chain=24 p15=<V> ph_idle=<V>` or `ERR` |
| `CLEAR` | The idle state: every input TERMINATED, no output on the bus, buffers off, pads at 0 dB, sense muxes off |
| `CONNECT "<out>" "<in>"` | Clears, then makes this one path. `OK LOOP` if `<out>` is `<in>`'s loop partner, otherwise `OK BUS`: `<out>` on the shared bus, the buffer of `<in>`'s board on with its pad at 0 dB, and `<in>` on BROADCAST. Every other input stays terminated |
| `ADD "<out>" "<in>"` *(optional)* | Like CONNECT but without clearing. `ERR BUSY` if the path needs the bus while another output holds it |
| `FANOUT "<out>" "<in>" …` *(optional)* | One output to many inputs over the bus |
| `TERMINATE "<in>"` \| `TERMINATE ALL` | Breaks that input's path and fits its 150 Ω, the idle state. `ALL` is the same as `CLEAR` |
| `SHORT "TALKBACK"` *(optional)* | Both talkback legs to ground: a 0 Ω source |
| `PAD 0\|40\|60` *(optional, harness-only)* | Sets the pad on the board or boards feeding the current bus path. The shared list never uses it |
| `PHANTOM "<in>"` \| `PHANTOM ALL` | One line per input, `PH "<in>" <volts> ON\|OFF\|HALF\|LOW`, then `OK` (see below) |
| `STATUS` | One line per live path (`PATH "<out>" "<in>" LOOP\|BUS`), then `OK` |
| `MAP`, `IMAGE <hex>`, `READ` | Diagnostics: the port table, a raw image, the image read back |

Error codes:

* `ERR PORT` — unknown name.
* `ERR ROUTE` — the path cannot be made, or the port is the wrong direction.
* `ERR BUSY` — the bus is already in use.
* `ERR CHAIN <byte>` — a readback mismatch. **This is a harness fault, not a DUT fail.** The runner stops the station.
* `ERR RAIL` — +15 V is missing.

`PHANTOM` reports the equivalent phantom voltage, assuming both legs are fed
(node × 17.2):

* **ON** — 40 to 54 V.
* **OFF** — below 5 V.
* **HALF** — the node reads the level one leg alone would give (a leg open).
* **LOW** — anything else.

The node filter settles in 6 ms and the harness samples 30 ms after it selects
the mux. The runner allows for the D24's own phantom ramp before it asks.

## Detecting a wrong connection

This check is the same for both back ends.

For every path, the runner drives **only `<out>`**, at 1 kHz, with every other
output at digital silence, and reads **every** input lane. The path passes
only when both of these hold:

1. the `<in>` lane rises ≥ 40 dB above its idle floor and lands inside the path's level window, and
2. every other input lane stays ≥ 40 dB below the `<in>` lane.

The results are read like this:

* **The tone appears on a different input** (for example on MIC 7 when MIC 5 was expected) → `MISPATCH`.
  * MANUAL: re-prompt the same patch.
  * HARNESS: the harness has already verified its routing by readback and `SELFTEST`, so a tone in the wrong place is a DUT wiring fault and the path FAILs with the lane named.
* **A tip/ring swap** shows up the same way: the tone lands on the partner lane of the stereo pair.
* **No tone anywhere** → the lead is not in `<out>`, or the path is dead.
  * MANUAL: prompt once to check the lead, then FAIL.
  * HARNESS: FAIL.
* **Optional:** giving each output a distinct frequency identifies *which* output a manual lead is actually in.

The same test is also the harness's own self-check on every path. A harness
that routed to the wrong input would fail condition 2 on the very first path.

Test at 1 kHz. A single switch pair isolates about −99 dB there (estimated),
which falls by about 20 dB per decade.

## The analogue station, start to finish

Both back ends use this order, and it keeps PW's rails rule (09-10: analog
last up, first down):

1. **Before the card**, read the mini-jack insertion sense `MJ_SW` with both jacks empty (rows 93/147).
2. **Station card**, with the analogue rails DOWN. HARNESS: *"Connect the tester: the three MIC looms, the three output looms, the talkback/mini-jack loom and its USB lead into a rear USB-A socket. Press Done."* MANUAL: *"Get the patch lead kit"* (see README). **One operator step.**
3. `IDENT`, then `SELFTEST`, then `CLEAR`. Read `MJ_SW` again: the harness plugs are now in, so it should show the plugged state.
4. **Raise the analogue rails once.**
5. **Phantom** (HARNESS only): `PHANTOM ALL` with every phantom off, expecting all OFF. Then set `Chan<strip>Phantom001` on all 24 and expect all ON. Then off, expecting all OFF. A 5-pattern binary walk proves each channel's control reaches its own input.
6. **Noise**: `TERMINATE ALL`, then read the noise on every input against a gross window.
7. **The path list** in order. The seed plan runs AUX 1–4 over LOOP first, so the outputs that later feed bus paths have already passed.
8. `CLEAR`, all phantom off, **lower the analogue rails**. Final card: *"Unplug the tester."*

The runner sets the DUT through cell names, never through matrix addresses:

* `Chan<strip>Phantom001` and `Chan<strip>Gain001`
* `Test001OscChan001`, `…OscLevel001`, `…OscFreq001` and `…OscOn001`
* `Test001MeasChan001`, then `Test001RmsResult001`, `…ThdResult001` and `…NoiseResult001`
* `Talk001Gain001`, `CodecAux001On001` and `CodecAux001Level001`
* `Mon001Level001` and `Mon001Level002`

The runner's own XLR → strip map (`d24_inputs.py`) turns a panel name into a
strip number. The harness never knows strips.
