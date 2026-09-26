#!/usr/bin/env python3
"""d24_chain.py -- the 595 mic-preamp chain, written fast enough to test with.

PW 2026-09-26: "it doesn't need 200 read verifies per setting."

FIRST, THE LABEL IS WRONG AND THE BEHAVIOUR IS NOT. `s55_chain.py` prints
`VERIFIED 200/200` and that is a BIT count -- 25 bytes, 200 bits -- not a
number of passes. It already does exactly what PW asked for: one shift, one
read-back, one compare. Nothing was ever verifying two hundred times.

WHAT IS ACTUALLY SLOW is everything around the wire. Measured on MW-D24-2,
2026-09-26, five writes each:

    as the station called it (a python3 process per write)   294 ms
    the same send() called in-process                        157 ms
        ... of which four `sudo pinctrl` calls               113 ms
        ... leaving the SPI itself                            44 ms

So the cost is a process start and four more processes to toggle one pin.
This module keeps the SPI device open and holds CS_M through gpiod, which is
what the DSP link's own tools already use, and pays neither.

THE GAIN STEPS ARE WHY IT MATTERS. Seven steps on each of twenty-four inputs
is 168 chain writes in a pass; at 294 ms that is 49 s of a factory worker's
time, and it is time they spend watching a screen that says "Checking...".
"""
import time

CS_M_GPIO = 27
CHAIN_BYTES = 25
SPI_SPEED_HZ = 100000


def byte(mute=0, phantom=0, gain=0):
    """One channel's byte, the same arithmetic s55_chain.py uses."""
    return (gain & 63) << 2 | (phantom & 1) << 1 | (mute & 1)


class Chain:
    """One open SPI device and one held CS_M line, for the life of a pass.

    `send()` is two passes because the chain IS two passes: the first shifts
    the image in and the second shifts it back out past the MISO tap, so the
    read-back is the image the registers actually hold. That is the verify,
    and there is one of it.
    """

    def __init__(self):
        import spidev
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self._req = None
        self._cs = None
        try:
            import gpiod
            from gpiod.line import Direction, Value
            self._req = gpiod.request_lines(
                '/dev/gpiochip0', consumer='d24_chain',
                config={CS_M_GPIO: gpiod.LineSettings(
                    direction=Direction.OUTPUT, output_value=Value.ACTIVE)})
            self._hi, self._lo = Value.ACTIVE, Value.INACTIVE
        except Exception:
            # No gpiod, or the line is held elsewhere: fall back to the slow
            # pin, and say so rather than silently taking 113 ms a write.
            self._req = None

    # -- the pin -----------------------------------------------------------
    @property
    def fast(self):
        return self._req is not None

    def cs(self, high):
        if self._req is not None:
            self._req.set_value(CS_M_GPIO, self._hi if high else self._lo)
            return
        import subprocess
        subprocess.run(['sudo', '-n', 'pinctrl', 'set', str(CS_M_GPIO),
                        'op', 'dh' if high else 'dl'], check=False)

    # -- the wire ----------------------------------------------------------
    def send(self, image):
        """Shift the image in, shift it back out, compare. Returns (ok, read)."""
        if len(image) != CHAIN_BYTES:
            raise AssertionError('the chain is %d bytes, not %d'
                                 % (CHAIN_BYTES, len(image)))
        old = (self.spi.mode, self.spi.max_speed_hz, self.spi.no_cs)
        try:
            self.spi.no_cs = True
            self.spi.mode = 0
            self.spi.max_speed_hz = SPI_SPEED_HZ
            got = []
            for _ in range(2):
                self.cs(False)
                got.append(self.spi.xfer2(list(image)))
                self.cs(True)
        finally:
            self.spi.mode, self.spi.max_speed_hz, self.spi.no_cs = old
        return got[1] == list(image), got[1]

    def close(self):
        try:
            self.cs(True)
        finally:
            try:
                self.spi.close()
            except Exception:
                pass
            if self._req is not None:
                try:
                    self._req.release()
                except Exception:
                    pass
                self._req = None


def timed(chain, image, reps=5):
    """What one write costs, for the record."""
    out = []
    for _ in range(reps):
        t0 = time.time()
        ok, _got = chain.send(image)
        out.append((time.time() - t0, ok))
    secs = [t for t, _ in out]
    return dict(mean_ms=1000.0 * sum(secs) / len(secs),
                min_ms=1000.0 * min(secs), max_ms=1000.0 * max(secs),
                ok=all(ok for _t, ok in out), fast=chain.fast)


if __name__ == '__main__':
    import sys
    img = [int(x, 0) for x in sys.argv[1:]] or [0x01] * 24 + [0x00]
    c = Chain()
    try:
        r = timed(c, img)
        print('%s: %.1f ms a write (min %.1f, max %.1f), read-back %s'
              % ('gpiod' if r['fast'] else 'pinctrl fallback', r['mean_ms'],
                 r['min_ms'], r['max_ms'], 'MATCHES' if r['ok'] else 'MISMATCH'))
    finally:
        c.close()
