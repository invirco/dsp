#!/usr/bin/env python3
"""dsp4_config.py — Pi/CM4 boot-time product configuration for the DSP4 card.

Implements the host side of MW/D32/DSP/product-config.md (decision D1:
the Pi masters each DSP directly over SPI; CS1 -> DSPA/chip1, CS2 ->
DSPB/chip2).

SPI parameter protocol (spi_handler.asm): two 32-bit words MSB-first per
transaction:
  word0 [31:16] = address, [13] = READ, [11:8] = ramp profile id
  word1 [31:0]  = value
Config registers live at 0xF000+ and are written with ramp id 0.

Chip select: the D24 Digital board drives CS1..CS8 from Pi GPIOs (not
the hardware CE lines), so this tool takes --cs-gpio and drives it via
gpiod around each transfer. Read off the DSP4 PI header J6 (page 7/10):
CS1 = GPIO6 -> chip 1, CS2 = GPIO7 -> chip 2. (GPIO5 is CS7, not CS1 —
the examples here said 5/6 until 2026-08-11.) SPI_RDY flow control
(CS3 = GPIO8 for chip 1, CS4 = GPIO12 for chip 2, back from the card)
is honoured when --rdy-gpio is given; see SpiLink.

For reading registers back off a running DSP, use dsp4_diag.py — it
implements the two-transaction read protocol on top of this SpiLink.

Usage examples:
  dsp4_config.py --product d24 --chip 1 --cs-gpio 6      # config chip 1
  dsp4_config.py --product d24 --chip 2 --cs-gpio 7
  dsp4_config.py --poke 0xF000 1 --chip 1 --cs-gpio 6    # raw register
  dsp4_config.py --product d24 --chip 1 --cs-gpio 6 --rdy-gpio 8
  dsp4_config.py --product d24 --dry-run                 # print writes

Requires: python3-spidev, python3-libgpiod on the Pi (only for real
writes; --dry-run works anywhere).
"""

import argparse
import sys

CFG_PRODUCT_ID = 0xF000
CFG_CHAN_MASK = 0xF001
CFG_AUX_MASK = 0xF002
CFG_OUT_MUX = 0xF003
CFG_COMMIT = 0xF004
CFG_PATCH_BASE = 0xF010

PRODUCT_IDS = {'d32': 0, 'd24': 1}

# D24 console-channel interleave (product-config.md): packed RX DMA
# channel i is delivered to the slot var of default index PATCH[i].
# AD0 carries ch 1-4 & 13-16, AD1 ch 5-8 & 17-20, AD2 ch 9-12 & 21-24.
D24_INPUT_PATCH = (
    [0, 1, 2, 3, 12, 13, 14, 15]        # AD0 slots 0-7
    + [4, 5, 6, 7, 16, 17, 18, 19]      # AD1
    + [8, 9, 10, 11, 20, 21, 22, 23]    # AD2
    + list(range(24, 32))               # AD3 lane: NET returns, identity
    + list(range(32, 46))               # superset sources, identity
)

PRODUCT_CONFIG = {
    'd32': {
        CFG_PRODUCT_ID: 0,
        CFG_CHAN_MASK: 0xFFFFFFFF,
        CFG_AUX_MASK: 0x0FFF,
        CFG_OUT_MUX: 1,          # B_O2 = snake (stored; gather TBD)
        # identity input patch — no patch writes needed
    },
    'd24': {
        CFG_PRODUCT_ID: 1,
        CFG_CHAN_MASK: 0x00FFFFFF,   # strips 25-32 NET-only
        CFG_AUX_MASK: 0x0FFF,
        CFG_OUT_MUX: 0,          # B_O2 = codec
        'input_patch': D24_INPUT_PATCH,   # chip 1 only
    },
}


def transactions(product, chip):
    """Yield (addr, value) writes for a product/chip, COMMIT last."""
    cfg = PRODUCT_CONFIG[product]
    for addr in (CFG_PRODUCT_ID, CFG_CHAN_MASK, CFG_AUX_MASK, CFG_OUT_MUX):
        yield addr, cfg[addr]
    if chip == 1 and 'input_patch' in cfg:
        for i, v in enumerate(cfg['input_patch']):
            yield CFG_PATCH_BASE + i, v
    yield CFG_COMMIT, 1


def frame(addr, value, ramp_id=0, read=False):
    w0 = ((addr & 0xFFFF) << 16) | ((ramp_id & 0xF) << 8) | (0x2000 if read else 0)
    return w0.to_bytes(4, 'big') + (value & 0xFFFFFFFF).to_bytes(4, 'big')


class SpiLink:
    """One host->DSP SPI link, with optional GPIO chip select and SPI_RDY.

    SPI_RDY (--rdy-gpio; CS3 = GPIO8 for chip 1, CS4 = GPIO12 for chip 2)
    is the DSP's flow-control output. The DSP enables it in dma_config.c
    with FCPL=1, so the line reads HIGH when the part is ready and LOW
    when its receive FIFO is backed up — and also low while the part is
    held in reset, because SPI2_RDY carries a 10K pulldown (R34/R22).
    Polling it therefore does double duty: it paces the link, and a line
    that never goes high says the DSP is dead or in reset before a single
    transaction has been attempted.

    PROVISIONAL: the polarity above is derived from the board (pulldown
    => FCPL=1, HRM Figure 40-7) and has not been seen on a scope. If
    bring-up shows it inverted, --rdy-active-low is the one-flag fix.
    """

    def __init__(self, dev, speed_hz, cs_gpio=None, gpiochip='gpiochip0',
                 rdy_gpio=None, rdy_active_low=False, rdy_timeout=0.5):
        import spidev
        bus, cs = (int(x) for x in dev.split('.'))
        self.spi = spidev.SpiDev()
        self.spi.open(bus, cs)
        self.spi.max_speed_hz = speed_hz
        self.spi.mode = 0
        self.spi.no_cs = cs_gpio is not None
        self.line = None
        self.rdy = None
        self.rdy_ready = 0 if rdy_active_low else 1
        self.rdy_timeout = rdy_timeout
        if cs_gpio is not None or rdy_gpio is not None:
            import gpiod
            from gpiod.line import Direction, Value
            self._V = Value
            chippath = (gpiochip if gpiochip.startswith('/dev/')
                        else '/dev/' + gpiochip)

            class _L:
                def __init__(s, req, num, V): s.req, s.num, s.V = req, num, V
                def set_value(s, v): s.req.set_value(s.num, s.V.ACTIVE if v else s.V.INACTIVE)
                def get_value(s): return 1 if s.req.get_value(s.num) == s.V.ACTIVE else 0

            # Each line is claimed only if it was actually asked for.
            # Requesting RDY unconditionally passed None to gpiod and
            # raised "argument 1 must be str, not None" before any
            # transaction could happen — which is what made dsp4_diag.py
            # unusable (tasks.md, 2026-08-21).
            if cs_gpio is not None:
                self._req_cs = gpiod.request_lines(
                    chippath, consumer='dsp4_config',
                    config={cs_gpio: gpiod.LineSettings(
                        direction=Direction.OUTPUT,
                        output_value=Value.ACTIVE)})
                self._cs_num = cs_gpio
                self.line = _L(self._req_cs, cs_gpio, Value)
            if rdy_gpio is not None:
                self._req_rdy = gpiod.request_lines(
                    chippath, consumer='dsp4_config_rdy',
                    config={rdy_gpio: gpiod.LineSettings(
                        direction=Direction.INPUT)})
                self.rdy = _L(self._req_rdy, rdy_gpio, Value)

    def wait_ready(self):
        if self.rdy is None:
            return
        import time
        deadline = time.monotonic() + self.rdy_timeout
        while self.rdy.get_value() != self.rdy_ready:
            if time.monotonic() > deadline:
                raise TimeoutError(
                    'SPI_RDY never asserted — DSP held in reset, not booted, '
                    'or the RDY polarity is inverted (try --rdy-active-low)')

    def xfer(self, addr, value, ramp_id=0, read=False):
        """One two-word transaction. Returns the 8 bytes clocked in on MISO."""
        self.wait_ready()
        buf = list(frame(addr, value, ramp_id, read))
        if self.line:
            self.line.set_value(0)
        try:
            rx = self.spi.xfer2(buf)
        finally:
            if self.line:
                self.line.set_value(1)
        return bytes(rx)

    def write(self, addr, value, ramp_id=0):
        self.xfer(addr, value, ramp_id)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--product', choices=sorted(PRODUCT_IDS))
    ap.add_argument('--chip', type=int, choices=(1, 2), default=1)
    ap.add_argument('--dev', default='0.0',
                    help='spidev bus.device (default 0.0)')
    ap.add_argument('--speed', type=int, default=1_000_000,
                    help='SPI clock Hz (default 1 MHz for bring-up)')
    ap.add_argument('--cs-gpio', type=int,
                    help='BCM GPIO driving this chip\'s CS line '
                         '(chip 1 = 6, chip 2 = 7)')
    ap.add_argument('--rdy-gpio', type=int,
                    help='BCM GPIO carrying this chip\'s SPI_RDY '
                         '(chip 1 = 8, chip 2 = 12)')
    ap.add_argument('--rdy-active-low', action='store_true',
                    help='invert SPI_RDY sense (see SpiLink; provisional)')
    ap.add_argument('--poke', nargs=2, metavar=('ADDR', 'VALUE'),
                    help='single register write (hex or dec)')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    if args.poke:
        writes = [(int(args.poke[0], 0), int(args.poke[1], 0))]
    elif args.product:
        writes = list(transactions(args.product, args.chip))
    else:
        ap.error('need --product or --poke')

    if args.dry_run:
        for addr, value in writes:
            print(f'  0x{addr:04X} <= 0x{value:08X}')
        print(f'({len(writes)} writes, chip {args.chip})')
        return

    link = SpiLink(args.dev, args.speed, args.cs_gpio,
                   rdy_gpio=args.rdy_gpio,
                   rdy_active_low=args.rdy_active_low)
    for addr, value in writes:
        link.write(addr, value)
    print(f'wrote {len(writes)} registers to chip {args.chip}')


if __name__ == '__main__':
    main()
