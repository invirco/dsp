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
  * CS3/CS4 come BACK from the card as DSPA/DSPB SPI_RDY. They are
    inputs. SPI2_RDY carries a 10K pulldown to GND on each DSP (R34 on
    DSPA, R22 on DSPB), so per the HRM's slave-boot figure the asserted
    state is HIGH -- and a part held in reset reads "not ready", which is
    what makes the wait below safe rather than a race.
  * !RST_D resets BOTH DSPs together (there is no per-chip reset), so a
    reset means re-booting both. That is why --chip defaults to "both".
  * CS1..CS8 are plain Pi GPIOs, not the hardware CE lines -- same
    reasoning as dsp4_config.py, so the SPI device is opened with no_cs
    and the select is driven with gpiod.

Default GPIO map, read off the DSP4 PI header J6 (page 7/10) against the
standard Pi 40-way numbering:

  SCK   GPIO11   MOSI  GPIO10   MISO  GPIO9
  CS1   GPIO6    CS2   GPIO7     (chip selects, active low)
  CS3   GPIO8    CS4   GPIO12    (SPI_RDY back from chip 1 / chip 2)
  !RST_D GPIO16  (header pin 36, resets both DSPs, active low)

Protocol, per HRM Figure 40-7 (host-side program flow, single-bit):
  reset low -> wait SPI_RDY asserted -> assert SS -> for each chunk:
  wait SPI_RDY asserted, send -> deassert SS. The stream is padded to a
  multiple of 1024 bytes because the HRM requires slave-boot hosts to
  send whole 1024-byte units (internal DMA buffer sizing).

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
CS_GPIO = {1: 6, 2: 7}
RDY_GPIO = {1: 8, 2: 12}
RST_GPIO = 16

BOOT_UNIT = 1024        # HRM: slave-boot hosts send multiples of 1024 B
CHUNK = 4096            # spidev-friendly; a multiple of BOOT_UNIT
RESET_LOW_S = 0.001     # !RST_D pulse width
RDY_TIMEOUT_S = 2.0


def pad(stream):
    """Pad to the 1024-byte unit the boot kernel's DMA expects."""
    short = len(stream) % BOOT_UNIT
    return stream if short == 0 else stream + b'\x00' * (BOOT_UNIT - short)


class Gpio:
    """Thin gpiod wrapper; outputs default to inactive (high = deasserted
    for the active-low CS and reset lines)."""

    def __init__(self, gpiochip='gpiochip0'):
        import gpiod
        self._gpiod = gpiod
        self.chip = gpiod.Chip(gpiochip)
        self.lines = {}

    def out(self, num, initial=1):
        line = self.chip.get_line(num)
        line.request(consumer='dsp4_boot',
                     type=self._gpiod.LINE_REQ_DIR_OUT, default_val=initial)
        self.lines[num] = line
        return line

    def inp(self, num):
        line = self.chip.get_line(num)
        line.request(consumer='dsp4_boot',
                     type=self._gpiod.LINE_REQ_DIR_IN)
        self.lines[num] = line
        return line


def wait_ready(line, what, timeout=RDY_TIMEOUT_S):
    """Block until SPI_RDY is asserted. Asserted is HIGH: the board pulls
    the line DOWN, so 'not ready' is also what a dead or held-in-reset
    part reads as -- do not invert this without changing R34/R22."""
    deadline = time.monotonic() + timeout
    while line.get_value() != 1:
        if time.monotonic() > deadline:
            raise TimeoutError(
                f'{what}: SPI_RDY never asserted within {timeout:.1f}s. '
                f'Check 3V3/1V8, that LOGIC is programmed (it sources '
                f'DSP_CLK -- an unprogrammed CPLD means no clock into '
                f'either DSP), and that !RST_D is released.')
    return True


def boot_chip(spi, gpio, chip, stream, verbose=True):
    cs = gpio.out(CS_GPIO[chip], initial=1)
    rdy = gpio.inp(RDY_GPIO[chip])

    wait_ready(rdy, f'chip {chip} (pre-select)')
    cs.set_value(0)
    try:
        sent = 0
        for off in range(0, len(stream), CHUNK):
            wait_ready(rdy, f'chip {chip} (at byte {off})')
            spi.xfer2(list(stream[off:off + CHUNK]))
            sent += len(stream[off:off + CHUNK])
    finally:
        cs.set_value(1)
    if verbose:
        print(f'  chip {chip}: {sent} bytes sent on CS{chip} '
              f'(GPIO{CS_GPIO[chip]}), RDY on GPIO{RDY_GPIO[chip]}')
    return sent


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
        print(f'reset: {"skipped" if args.no_reset else f"GPIO{RST_GPIO} pulsed low"}')
        print(f'({len(streams)} chip(s), {args.speed} Hz)')
        return

    import spidev
    bus, dev = (int(x) for x in args.dev.split('.'))
    spi = spidev.SpiDev()
    spi.open(bus, dev)
    spi.max_speed_hz = args.speed
    spi.mode = 0
    spi.no_cs = True

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
        print(f'!RST_D pulsed (GPIO{RST_GPIO})')

    for chip, path, s, raw_len in streams:
        boot_chip(spi, gpio, chip, s)
    print(f'booted {len(streams)} chip(s) at {args.speed} Hz')


if __name__ == '__main__':
    main()
