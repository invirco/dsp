provenance: AI-drafted 2026-08-12 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# DSP4 bring-up diagnostics — LED fault codes and the SPI readback block

Status: implemented 2026-08-12, **never run on hardware**.
Scope: rev-C DSP4 card, both SHARCs, D24 and D32 (one firmware, D3).
Source: `SHARC/src/diag.asm`, `SHARC/src/diag.h`, `tools/pi/dsp4_diag.py`.

## Why

Rev C has no emulator access to either SHARC. `JTG_TCK/TMS/TDI/TDO` and
`JTG_TRST` carry sheet-local stubs only and the ROOT DSPA/DSPB blocks
expose no JTAG ports, so nothing leaves the sheet (analysis in
`tasks.md`, 2026-08-11 addendum). The JTAG that does reach the Pi header
is the CPLD's.

That leaves exactly two channels into a running DSP: the host SPI link
and one green LED per chip. Both now carry state, which is most of what
an emulator would have been used for.

## LED fault codes

One green LED per chip, on `PA_12` — LD3 off DSPA/U6 (R37), LD2 off
DSPB/U5 (R4). Same pin and polarity as the standalone `blink` image.
`PA_13` is the shared `!BLINK` net and is never driven.

The LED is driven by the **core timer**, armed in `_diag_init` before any
peripheral bring-up runs. It does not depend on the SEC, the SPORTs, the
DMA, or the audio clock — so it keeps flashing through a failure in any
of them. That is the whole point: a heartbeat driven from the audio block
ISR goes dark exactly when the board is most interesting.

| Flashes | Stage | Meaning |
|---|---|---|
| 1 | `DIAG_STAGE_INIT` | core + timer alive; stuck in `_sru_init` |
| 2 | `DIAG_STAGE_SRU` | SRU routed; stuck in `_sport_cfg_init` |
| 3 | `DIAG_STAGE_SPORT` | half-SPORTs configured; stuck in `_dma_cfg_init` |
| 4 | `DIAG_STAGE_DMA` | DMA rings + SEC + SPI2 up; stuck enabling interrupts |
| 5 | `DIAG_STAGE_WAITCFG` | waiting for host product config — no `CONFIG_COMMIT` |
| 6 | `DIAG_STAGE_CONFIGED` | configured; waiting for the first audio block |
| — | `DIAG_STAGE_RUNNING` | **steady 1 Hz square** — audio blocks are flowing |

A stage means "this step completed", so N flashes reads as "stuck in step
N+1". Healthy is a 1 Hz 50% square, not a 7-flash burst, so "running"
cannot be miscounted as a fault code.

**No LED at all** means the boot stream never landed, or the part has no
clock, or it is held in reset — none of which this firmware can report
on. That is what `./build.sh blink` and `dsp4_boot.py` are for.

Stage 5 and stage 6 are the two failures this whole exercise is aimed at,
because they look identical from outside: the board is powered, the LED
is on, and nothing happens. Stage 5 says the SPI link never delivered a
config. Stage 6 says the link works and the audio clock does not — which
on this card usually means the LOGIC CPLD is unprogrammed, since it
sources `DSP_CLK` and every frame sync.

`--led on` / `--led off` overrides the pattern, which is how you tell two
identical cards, or the two chips on one card, apart.

## The readback block

Read-only registers at `0xE000`, over the SPI parameter link that already
exists. Full map in `SHARC/src/diag.h`; `tools/pi/dsp4_diag.py` mirrors it.

```
dsp4_diag.py --chip 1 --cs-gpio 6 --rdy-gpio 8      # dump + flag issues
dsp4_diag.py --chip 1 --watch                       # live at 1 Hz
dsp4_diag.py --chip 1 --peek 0x31030040             # any MMR
dsp4_diag.py --chip 1 --rate 2.0                    # measure CCLK and Fs
dsp4_diag.py --chip 1 --clear                       # zero the counters
```

The tool prints an ISSUES section, so it answers "what is wrong" rather
than only "what are the values".

Registers worth knowing by name:

- `MAGIC` (`0xD5B40001`) and `BUILD_ID` — the link works, and this is the
  firmware you think it is.
- `CHIP_ID` — which part answered this chip select. Chip identity is
  compile-time (`-DCHIP_ID`), so this is the check that CS1 reaches DSPA
  and CS2 reaches DSPB rather than the other way round.
- `BOOT_STAGE` — the LED code, in a register.
- `FRAME_COUNT` / `TICKS` — the two free-running rates. `--clear` does
  not reset them, deliberately.
- `LAST_CSID`, `SEC_COUNT`, `UNK_CSID`, `UNK_COUNT` — SEC routing.
  `SEC_COUNT` stuck at 0 means nothing peripheral reaches the core at all.
- `BLK_OVERRUN` — blocks the main loop failed to finish in time. Audio was
  dropped; without this counter that is silent.
- `SPI_STAT_STK` — sticky OR of `SPI2_STAT`, sampled inside the ISR before
  the FIFO is drained. `ROR`/`TUR`/`MF`/`TC` clear themselves too fast for
  a host poll to ever catch them otherwise.
- `SPI_CTL` / `SPI_RXCTL` / `SPI_TXCTL` — the live configuration
  registers. These exist so the bench can confirm the part *took* the
  configuration, instead of inferring it from source. Three separate SPI
  bugs on 2026-08-12 were all of the form "the source says X, the silicon
  does not do X".
- `SPORT0_ERR_A`, `DMA0_STAT` — the block-clock lane's error latches.
- `PEEK_ADDR` / `PEEK_DATA` — write an address, read its contents. This is
  the emulator substitute: any MMR on a running DSP, including ones
  nobody thought to name here. Unchecked by design; peeking a bad address
  will fault the part.

### Read protocol

A read is a normal two-word transaction with bit 13 set in word 0. The
answer cannot come back in the same transaction: the RX watermark
interrupt only fires once both words have arrived, by which point the
master has already shifted MISO. So the DSP queues **two** words —
an echo of the request, then the value — and the master collects them on
its next transaction:

```
  transaction 1:  MOSI {addr|READ, 0}   MISO: previous / undefined
  transaction 2:  MOSI {DIAG_NOP, 0}    MISO: {echo, value}
```

`SPI_TFIFO` is exactly 2 words deep at 32-bit word size, which is exactly
one response. A response is queued only into an empty FIFO; otherwise it
is dropped and `RESP_DROP` counts it, because a dropped answer is
recoverable and a FIFO overflow silently misaligns every answer after it.

The echo is what makes the readings trustworthy on a bench. `dsp4_diag.py`
checks every one, so a chip that is not answering (MISO idle) reports an
error instead of a plausible-looking zero.

## Bench order

1. **Flash the CPLD first** — `shared/dsp4-logic/bitstream/*.pof` over the
   Pi's JTAG. It sources `DSP_CLK`; an unprogrammed CPLD means neither
   DSP has a clock. Confirm LD1 (CPLD, pin 59) at ~1.5 Hz and TEST1-4 on
   the scope.
2. **Blink images** — `./build.sh blink`, then `dsp4_boot.py` with
   `blink1.ldr` / `blink2.ldr`. Chip 1 ~1 Hz, chip 2 ~2 Hz. This proves
   power, clock, reset release, the SPI slave-boot path and the core,
   with no plumbing involved. **Write the measured rate down** — it is a
   free core-clock measurement.
3. **Real images** — `./build.sh all`, then `dsp4_boot.py` with
   `chip1.ldr` / `chip2.ldr`. Expect the LED to settle on **5 flashes**:
   booted, initialised, waiting for the host product config.
4. **Talk to it** — `dsp4_diag.py --chip 1`. `MAGIC` and `CHIP_ID` are the
   first two things that have ever proved the host-to-DSP link works in
   both directions.
5. **Configure** — `dsp4_config.py --product d24 --chip 1 --cs-gpio 6`.
   The LED should go to **6 flashes** on `CONFIG_COMMIT`.
6. **Audio** — if the LOGIC frame syncs are running, the LED goes to a
   steady 1 Hz square and `FRAME_COUNT` climbs. `--rate 2.0` then gives
   measured CCLK and measured Fs in one shot.

## Still unproven

Most of it. As of 2026-08-21 the firmware runs its whole init sequence
on both chips — SRU, SPORT, DMA rings, SEC and SPI2 — and sits in the
`.wait_boot` host handshake (bisect rung 21 fires on chip 1 and chip 2).
What has NOT been shown is anything downstream of that: the SPI
parameter link still answers all-zero to `dsp4_diag.py`, so no register
in this document has been read off a running part yet. In particular:

- `DIAG_TPERIOD` is now 491520 — one tick is 1.000 ms at the MEASURED
  CCLK of 491.52 MHz (2026-08-21, `src/blink/clkprobe.asm`), so the LED
  intervals mean what they say. The old 400 MHz assumption is gone.
- The `SPI_RDY` polarity in `dsp4_config.py` (`FCPL=1`, ready = high) is
  derived from the board's 10K pulldown and HRM Figure 40-7, not from a
  scope. `--rdy-active-low` is the one-flag fix if it is inverted.
- The `RUWM = full` watermark choice assumes one protocol transaction is
  exactly one full RFIFO (2 words at 32-bit). That follows from the HRM,
  but it has never been clocked.
