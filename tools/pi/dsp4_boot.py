#!/usr/bin/env python3
"""dsp4_boot.py — Pi/CM4 slave-boot loader for the DSP4 card's two SHARCs.

Pushes the .ldr boot streams built by MW/D32/DSP/SHARC/build.sh into the
ADSP-21564s over Pi-mastered SPI. The card has NO boot flash: decision D1
(Pi masters boot) plus D8 (boot-relay fallback deleted) make this the only
way either DSP ever runs code.

Hardware facts this implements, all from the rev C schematic + the
ADSP-2156x HRM chapter 40 (Boot Modes):

  * SYS_BMODE[2:0] = 0b010 -> SPI slave boot through the SPI2 peripheral
    (BMODE2 = GND p82, BMODE1 = VDD_EXT p106, BMODE0 = GND p105).
  * The host drives SCK/MOSI/MISO shared to both parts (33R split into
    CK1_[0..2] / CK2_[0..2]); per-chip selection is CS1 -> DSPA/chip1,
    CS2 -> DSPB/chip2.
  * The clock mode during slave boot is the boot kernel's, not ours:
    ch.40, "In SPI slave boot mode, the boot kernel sets the
    SPI_CTL.CPHA bit and clears the SPI_CTL.CPOL bit ... the [MOSI] pin
    is latched on the falling edge". CPHA=1 + CPOL=0 is SPI MODE 1 (the
    HRM uses the Motorola numbering -- ch.15: "mode-0 (CPHA=CPOL=0) and
    mode-3 (CPHA=CPOL=1)"). See SPI_MODE below; the RUNTIME link is a
    different question and stays mode 0, because dma_config.c's
    spi2_init() leaves CPOL and CPHA clear.
  * CS3/CS4 come BACK from the card as DSPA/DSPB SPI_RDY. They are
    inputs. During slave boot the polarity is the boot kernel's and the
    HRM fixes it ACTIVE-LOW (ch.40: "The boot code requires the SPIx_RDY
    signal function as active-low"), so asserted = 0. SPI2_RDY carries a
    10K pulldown to GND on each DSP (R34 on DSPA, R22 on DSPB), which
    rests the line ASSERTED -- the opposite of the pull-up the HRM's
    in-reset hold-off assumes. So the wait cannot prove a part is alive;
    it only catches a part actively holding the host off. See
    wait_ready() for the full note and the 2026-08-20 correction.
  * !RST_D resets BOTH DSPs together (there is no per-chip reset), so a
    reset means re-booting both. That is why --chip defaults to "both".
  * CS1..CS8 are plain Pi GPIOs, not the hardware CE lines -- same
    reasoning as dsp4_config.py, so the SPI device is opened with no_cs
    and the select is driven with gpiod.

Default GPIO map, read off the DSP4 PI header J6 (page 7/10) against the
standard Pi 40-way numbering:

  SCK   GPIO11   MOSI  GPIO10   MISO  GPIO9
  CS1   GPIO6    CS2   GPIO24    (chip selects, active low)
  CS3   GPIO8    CS4   GPIO12    (SPI_RDY back from chip 1 / chip 2)
  !RST_D GPIO16  (header pin 36, resets both DSPs, active low)

Protocol, per HRM Figure 40-7 (host-side program flow, single-bit):
  reset low -> wait SPI_RDY asserted -> assert SS -> for each chunk:
  wait SPI_RDY asserted, send -> deassert SS. The stream is padded to a
  multiple of 1024 bytes because the HRM requires slave-boot hosts to
  send whole 1024-byte units (internal DMA buffer sizing).

Auto-retry: re-booting a part that is already RUNNING (or hung in one of
the bisect parks) fails its FIRST attempt on a SPI_RDY timeout and
succeeds on the immediate retry — reproduced three times on rev C,
2026-08-19/20. Each chip therefore gets BOOT_ATTEMPTS tries and both
attempts are logged, so the retry never hides a genuinely dead part. The
retry restarts that chip's stream from byte 0 and does NOT re-pulse
!RST_D: one reset line serves both DSPs, so a mid-run reset would take
the other part down with it.

Usage:
  dsp4_boot.py --dir ../../MW/D32/DSP/SHARC/build          # both chips
  dsp4_boot.py --chip 1 --ldr build/chip1.ldr
  dsp4_boot.py --dir build --no-reset                      # keep running
  dsp4_boot.py --dir build --dry-run                       # off-target

Requires python3-spidev + python3-libgpiod on the Pi; --dry-run works
anywhere and is the only mode that runs on this workstation.
"""

import argparse
import os
import sys
import time

# BCM GPIO numbers, DSP4 J6 (see module docstring).
CS_GPIO = {1: 6, 2: 24}
RDY_GPIO = {1: 8, 2: 12}
RST_GPIO = 16

BOOT_UNIT = 1024        # HRM: slave-boot hosts send multiples of 1024 B
CHUNK = 4096            # spidev-friendly; a multiple of BOOT_UNIT
RESET_LOW_S = 0.050     # !RST_D pulse width

# Settle time between releasing !RST_D and the first clocked byte.
#
# The HRM's host flow (Fig. 40-7) does not use a timer here: it waits for
# SPI_RDY to go DEASSERTED and then ASSERTED again, which is the boot
# kernel saying "SPI2 is enabled, start sending". That handshake does not
# exist on this card, because the 10K pulls are pull-DOWNS and rest the
# line asserted (see wait_ready). Without it the host would start clocking
# microseconds after reset release, while the part is still in pre-boot
# (CGU config, DMC config, memory init, fault/cache init -- HRM ch.40
# "Preboot Operations"). Bytes clocked before SPI2 is enabled are simply
# lost, and the kernel then starts reading mid-stream, so no block header
# ever lines up and boot never completes.
POST_RESET_S = 0.500    # --post-reset-delay overrides
RDY_TIMEOUT_S = 2.0
BOOT_ATTEMPTS = 2       # 1 automatic retry — see "Auto-retry" above
RETRY_SETTLE_S = 0.20   # let the part's boot kernel re-arm SPI_RDY

# SPI_RDY polarity during SLAVE BOOT is not ours to choose: the on-chip
# boot kernel fixes it. HRM ch.40 "SPI Slave Boot Mode": "The SPIx_RDY
# output is used for back pressure and requires a pulling resistor. The
# boot code requires the SPIx_RDY signal function as active-low." So
# asserted (host may send) = 0. See RDY_ASSERTED below.
RDY_ACTIVE_LOW = True   # boot kernel's fixed polarity; --rdy-active-high overrides

# The SPI clock mode during slave boot is likewise not ours to choose.
# HRM ch.40 "SPI Slave Boot Mode": "the boot kernel sets the SPI_CTL.CPHA
# bit and clears the SPI_CTL.CPOL bit". CPHA=1, CPOL=0 -> SPI mode 1:
# MOSI is driven on the rising edge of SPI_CLK and latched by the DSP on
# the falling edge. A host in mode 0 changes MOSI on exactly the edge the
# boot kernel samples, so the kernel clocks in shifted garbage, no block
# header ever passes its 0xAD signature / XOR check, the boot never
# completes and the application never runs -- while the host still sees a
# stream that was "accepted" from end to end, because the pull-downs rest
# SPI_RDY in the asserted state (see wait_ready).
SPI_MODE = 1            # CPOL=0, CPHA=1; --spi-mode overrides


def pad(stream):
    """Pad to the 1024-byte unit the boot kernel's DMA expects."""
    short = len(stream) % BOOT_UNIT
    return stream if short == 0 else stream + b'\x00' * (BOOT_UNIT - short)


class _Line:
    """gpiod v2 per-line wrapper exposing the v1-style get/set surface."""
    def __init__(self, req, num, Value):
        self._req, self._num, self._V = req, num, Value
    def release(self):
        self._req.release()
    def get_value(self):
        return 1 if self._req.get_value(self._num) == self._V.ACTIVE else 0
    def set_value(self, v):
        self._req.set_value(self._num, self._V.ACTIVE if v else self._V.INACTIVE)


class Gpio:
    """Thin gpiod (v2 API) wrapper; outputs default to inactive (high =
    deasserted for the active-low CS and reset lines)."""

    def __init__(self, gpiochip="/dev/gpiochip0"):
        import gpiod
        from gpiod.line import Direction, Value
        self._gpiod, self._D, self._V = gpiod, Direction, Value
        self._path = gpiochip
        self.lines = {}

    def _claim(self, num, settings):
        # A retry re-claims CS/RDY, and the kernel refuses a second request
        # for a line this process still holds — drop the old one first.
        held = self.lines.pop(num, None)
        if held is not None:
            held.release()
        req = self._gpiod.request_lines(self._path, consumer="dsp4_boot",
                                        config={num: settings})
        line = _Line(req, num, self._V)
        self.lines[num] = line
        return line

    def out(self, num, initial=1):
        return self._claim(num, self._gpiod.LineSettings(
            direction=self._D.OUTPUT,
            output_value=self._V.ACTIVE if initial else self._V.INACTIVE))

    def inp(self, num):
        return self._claim(num,
                           self._gpiod.LineSettings(direction=self._D.INPUT))


def wait_ready(line, what, timeout=RDY_TIMEOUT_S, active_low=RDY_ACTIVE_LOW):
    """Block until SPI_RDY is asserted.

    CORRECTED 2026-08-20 (was: wait for HIGH). During slave boot the
    polarity is the boot kernel's, and the HRM fixes it ACTIVE-LOW
    (ch.40, "In SPI slave boot mode, SPIx_RDY functionality is
    critical ... The boot code requires the SPIx_RDY signal function as
    active-low"). Asserted = 0.

    The card's 10K pulls (R34 on DSPA, R22 on DSPB) are pull-DOWNS, i.e.
    they rest the line in the ASSERTED state. That defeats the HRM's
    in-reset hold-off ("allows the processor to hold off the host while
    the processor is in reset"), so this wait can NOT prove a part is
    alive -- a dead or held-in-reset part reads asserted too. Back
    pressure mid-stream still works, because the DSP drives the pin
    push-pull to deassert. Making the hold-off real needs the pulls
    changed to pull-UPS (rev-D hardware item, logged in tasks.md).

    Why the old HIGH-wait appeared to work until 2026-08-20: CS3/CS4 are
    shared nets (Pi RDY inputs AND H1S1's SPI_RDY monitors, hardware-map
    §3a). H1S1 drove CS1-6 push-pull HIGH until the 2026-08-20 reflash
    made them inputs, so the Pi always read 1 and every wait passed
    vacuously -- boots ran with no real flow control at all.
    """
    want = 0 if active_low else 1
    deadline = time.monotonic() + timeout
    while line.get_value() != want:
        if time.monotonic() > deadline:
            raise TimeoutError(
                f'{what}: SPI_RDY never asserted (expected '
                f'{"LOW" if active_low else "HIGH"}) within {timeout:.1f}s. '
                f'With the 10K pull-downs fitted the line rests asserted, so '
                f'reading it deasserted this long means something is HOLDING '
                f'it off: the part is mid-boot-kernel, or another device on '
                f'the shared CS3/CS4 nets is driving them (H1S1 did until '
                f'2026-08-20). Also check 3V3/1V8, that LOGIC is programmed '
                f'(it sources DSP_CLK -- an unprogrammed CPLD means no clock '
                f'into either DSP), and that !RST_D is released.')
    return True


def boot_chip(spi, gpio, chip, stream, verbose=True, attempt=1,
              attempts=BOOT_ATTEMPTS, active_low=RDY_ACTIVE_LOW):
    cs = gpio.out(CS_GPIO[chip], initial=1)
    rdy = gpio.inp(RDY_GPIO[chip])

    wait_ready(rdy, f'chip {chip} (pre-select)', active_low=active_low)
    cs.set_value(0)
    try:
        sent = 0
        for off in range(0, len(stream), CHUNK):
            wait_ready(rdy, f'chip {chip} (at byte {off})',
                       active_low=active_low)
            spi.xfer2(list(stream[off:off + CHUNK]))
            sent += len(stream[off:off + CHUNK])
    finally:
        cs.set_value(1)
    if verbose:
        print(f'  chip {chip}: attempt {attempt}/{attempts} OK — {sent} bytes '
              f'sent on CS{chip} (GPIO{CS_GPIO[chip]}), RDY on '
              f'GPIO{RDY_GPIO[chip]}')
    return sent


def boot_chip_retrying(spi, gpio, chip, stream, verbose=True,
                       attempts=BOOT_ATTEMPTS, active_low=RDY_ACTIVE_LOW):
    """boot_chip with the documented one-shot retry. Every attempt is
    logged — a part that needs the retry every time is still telling us
    something, so the retry must stay visible rather than silent."""
    last = None
    for attempt in range(1, attempts + 1):
        try:
            return boot_chip(spi, gpio, chip, stream, verbose=verbose,
                             attempt=attempt, attempts=attempts,
                             active_low=active_low)
        except TimeoutError as exc:
            last = exc
            print(f'  chip {chip}: attempt {attempt}/{attempts} FAILED — '
                  f'{exc}', file=sys.stderr)
            if attempt < attempts:
                print(f'  chip {chip}: retrying from byte 0 in '
                      f'{RETRY_SETTLE_S:.2f}s (!RST_D NOT re-pulsed — it '
                      f'would reset the other DSP too)', file=sys.stderr)
                time.sleep(RETRY_SETTLE_S)
    raise last


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--dir', help='build dir holding chip1.ldr / chip2.ldr')
    ap.add_argument('--ldr', help='explicit .ldr (needs --chip)')
    ap.add_argument('--chip', type=int, choices=(1, 2),
                    help='boot one chip only (default: both)')
    ap.add_argument('--dev', default='0.0',
                    help='spidev bus.device (default 0.0)')
    ap.add_argument('--speed', type=int, default=1_000_000,
                    help='SPI clock Hz (default 1 MHz for bring-up)')
    ap.add_argument('--no-reset', action='store_true',
                    help='skip the !RST_D pulse (only valid if the parts '
                         'are already sitting in the boot kernel)')
    ap.add_argument('--attempts', type=int, default=BOOT_ATTEMPTS,
                    help=f'boot attempts per chip (default {BOOT_ATTEMPTS}: '
                         f'one automatic retry; 1 disables the retry)')
    ap.add_argument('--rdy-active-high', action='store_true',
                    help='treat SPI_RDY as active-HIGH. The boot kernel '
                         'fixes it active-low (HRM ch.40), so this is an '
                         'escape hatch for a board that inverts the line, '
                         'not a normal option.')
    ap.add_argument('--spi-mode', type=int, choices=(0, 1, 2, 3),
                    default=SPI_MODE,
                    help=f'SPI clock mode (default {SPI_MODE} = CPOL 0, '
                         f'CPHA 1, which is what the boot kernel fixes per '
                         f'HRM ch.40). An escape hatch for experiments, not '
                         f'a normal option.')
    ap.add_argument('--post-reset-delay', type=float, default=POST_RESET_S,
                    help=f'seconds to wait after releasing !RST_D before '
                         f'clocking the first byte (default {POST_RESET_S}). '
                         f'Stands in for the SPI_RDY deassert/assert '
                         f'handshake the pull-downs make unreadable.')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    if args.ldr:
        if not args.chip:
            ap.error('--ldr needs --chip')
        targets = [(args.chip, args.ldr)]
    elif args.dir:
        chips = [args.chip] if args.chip else [1, 2]
        targets = [(c, os.path.join(args.dir, f'chip{c}.ldr')) for c in chips]
    else:
        ap.error('need --dir or --ldr')

    streams = []
    for chip, path in targets:
        if not os.path.isfile(path):
            sys.exit(f'missing {path} — run MW/D32/DSP/SHARC/build.sh first')
        raw = open(path, 'rb').read()
        streams.append((chip, path, pad(raw), len(raw)))

    marker = os.path.join(args.dir or os.path.dirname(args.ldr),
                          'COMPAT-BUILD.txt')
    if os.path.exists(marker):
        sys.exit(f'refusing to boot: {marker} present — these are fit-proxy '
                 f'images built for a different part, not 21564 images.')

    if args.dry_run:
        for chip, path, s, raw_len in streams:
            print(f'  chip {chip}: {path} {raw_len} B -> {len(s)} B padded '
                  f'({len(s) // BOOT_UNIT} × {BOOT_UNIT}), '
                  f'CS GPIO{CS_GPIO[chip]}, RDY GPIO{RDY_GPIO[chip]}')
        print(f'reset: {"skipped" if args.no_reset else f"GPIO{RST_GPIO} pulsed low, "
                        f"{args.post_reset_delay:.3f}s settle"}')
        print(f'({len(streams)} chip(s), {args.speed} Hz, SPI mode '
              f'{args.spi_mode}, {args.attempts} attempt(s) per chip)')
        return

    import spidev
    bus, dev = (int(x) for x in args.dev.split('.'))
    spi = spidev.SpiDev()
    spi.open(bus, dev)
    spi.max_speed_hz = args.speed
    spi.mode = args.spi_mode      # 1 = CPOL 0 / CPHA 1; see SPI_MODE
    spi.no_cs = True
    if args.spi_mode != SPI_MODE:
        print(f'WARNING: SPI mode {args.spi_mode} overrides the boot '
              f'kernel\'s fixed mode {SPI_MODE} (HRM ch.40)', file=sys.stderr)

    gpio = Gpio()
    if not args.no_reset:
        # One reset line for both parts: whatever we reset, we must boot.
        if len(streams) != 2:
            print('WARNING: !RST_D resets BOTH DSPs, but only '
                  f'{len(streams)} image(s) given — the other part will sit '
                  'in its boot kernel with no image.', file=sys.stderr)
        rst = gpio.out(RST_GPIO, initial=1)
        rst.set_value(0)
        time.sleep(RESET_LOW_S)
        rst.set_value(1)
        time.sleep(args.post_reset_delay)
        print(f'!RST_D pulsed (GPIO{RST_GPIO}), '
              f'{args.post_reset_delay:.3f}s settle')

    for chip, path, s, raw_len in streams:
        boot_chip_retrying(spi, gpio, chip, s, attempts=args.attempts,
                           active_low=not args.rdy_active_high)
    print(f'booted {len(streams)} chip(s) at {args.speed} Hz, SPI mode '
          f'{args.spi_mode}')


if __name__ == '__main__':
    main()
