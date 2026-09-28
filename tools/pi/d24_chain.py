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

AND BIT 0 IS NOT A MUTE. See `byte()`.
"""
import time

CS_M_GPIO = 27
CHAIN_BYTES = 25
SPI_SPEED_HZ = 100000

# ---------------------------------------------------------------------------
# Q0 IS THE PHANTOM SHUNT (PW ruling 2026-09-16)
# ---------------------------------------------------------------------------
# PRIMARY SOURCE, read rather than relayed (S138-1): mx26
# `docs/ref-d24-analog-attach.md` §"Phantom switching -- the shunt-first
# sequence (PW 2026-09-16)", and `docs/d24-analog-xlr-map.md` ("bits 2-7 =
# gain code. Phantom is never switched without the shunt").
#
#   "Q0 is the phantom shunt: it grounds that channel's mic-pre input
#    coupling caps. It is not a mute and not a pad. Its job is to be engaged
#    whenever phantom moves -- for the click/pop into the outputs and for the
#    preamp's own protection against the 48 V step through the coupling caps."
#
# THE CHANNEL MUTE IS DIGITAL, in the DSP strip, and has never been on this
# wire. `s55_chain.py` called Q0 the mute because that is what it was called
# before PW's ruling, and every tool in this tree inherited the name from it
# -- which is how S138 came to record "no shunt bit exists anywhere in this
# tree's 595 chain encoding" (finding S138-3). The bit was there all along,
# under the wrong name, which is worse than absent: a reader looking for the
# shunt could not find it and a reader looking at the mute found something
# that is not one.
#
# THE WIRE ENCODING IS UNCHANGED BY THE RENAME and must stay so -- 25 bytes,
# Q0 shunt, Q1 phantom, Q2-Q7 gain code, images built in TRANSMIT order (byte
# 0 reaches chain index 24; see `d24_patch.Analog.step_image` and the wire-
# order note in the map). `shunt_check.py` asserts all 256 encodings are
# byte-identical to the pre-rename arithmetic.
#
# The app's own bench CLI made the same rename first and kept the old name as
# a deprecated alias (`chain-set ... mute=` prints a note and means `shunt=`);
# this module follows it, so a script written against either name writes the
# same byte.
SHUNT_BIT = 0x01
PHANTOM_BIT = 0x02
GAIN_SHIFT = 2

# The shunt-first sequence's two waits, in SECONDS here because that is what
# `time.sleep` takes; they are the same two numbers as the app's
# `PhantomSequence.cs` `ShuntSettleMs` (50) and `PhantomSettleMs` (300).
#
# BOTH ARE PROVISIONAL, and the primary source says so in as many words: they
# "are placeholders until they are calculated from the 48 V feed and the
# coupling-cap RC (the 2x6K8 feed into the 33 uF input electrolytics) and
# measured on the bench. Change them there and nowhere else." That bench
# measurement is exactly what the click/shunt trials (gaps doc 1.2(b)) exist
# to feed, so this module carries the app's numbers and does not invent its
# own -- and a caller may override both.
SHUNT_SETTLE_S = 0.050
PHANTOM_SETTLE_S = 0.300


def byte(shunt=None, phantom=0, gain=0, mute=None):
    """One channel's byte: Q0 shunt, Q1 phantom, Q2-Q7 gain code.

    `mute=` is the DEPRECATED name of `shunt=` (see the note above): Q0 was
    called the mute before PW's ruling of 2026-09-16 and it is the phantom
    shunt. Accepted so that no caller breaks, and it writes the same bit.
    Passing both, differing, is a bug in the caller and says so.
    """
    if mute is not None:
        if shunt is not None and bool(shunt) != bool(mute):
            raise AssertionError('byte(): shunt=%r and its deprecated alias '
                                 'mute=%r disagree; they are one bit (Q0, the '
                                 'phantom shunt)' % (shunt, mute))
        shunt = mute
    return ((gain & 63) << GAIN_SHIFT | (phantom & 1) << 1
            | (1 if shunt else 0))


def split(b):
    """One channel's byte, back into (shunt, phantom, gain). The inverse of
    `byte()`, so a read-back can be printed in the names the ruling uses."""
    return (b & SHUNT_BIT and 1 or 0, (b >> 1) & 1, (b >> GAIN_SHIFT) & 63)


def with_shunt(image, channels, on):
    """`image` with the shunt bit set or cleared on `channels` (transmit
    positions, zero-based), everything else -- phantom, gain, the trailing
    U34 byte -- left exactly as it was.

    THE TRAILING BYTE IS NEVER TOUCHED. Byte 24 of a transmit-order image is
    U34's, whose Q0 is INSTR1 and not a shunt at all; a channel index is
    range-checked against the twenty-four preamps so a caller cannot reach it.
    """
    out = list(image)
    for i in channels:
        i = int(i)
        if not 0 <= i < CHAIN_BYTES - 1:
            raise AssertionError('transmit position %r is not one of the 24 '
                                 'preamps' % i)
        out[i] = (out[i] | SHUNT_BIT) if on else (out[i] & ~SHUNT_BIT)
    return out


def with_phantom(image, channels, on):
    """`image` with the phantom bit set or cleared on `channels`. Same rules.

    NEVER CALL THIS ON ITS OWN TO MOVE PHANTOM. "Phantom is therefore never
    switched by one image" (PW 2026-09-16): a phantom change goes out as the
    five-step shunt-first sequence, which is `phantom_sequence()` below and,
    on the real wire with verified loads, `d24_patch.Analog.phantom()`.
    """
    out = list(image)
    for i in channels:
        i = int(i)
        if not 0 <= i < CHAIN_BYTES - 1:
            raise AssertionError('transmit position %r is not one of the 24 '
                                 'preamps' % i)
        out[i] = (out[i] | PHANTOM_BIT) if on else (out[i] & ~PHANTOM_BIT)
    return out


def phantom_sequence(image, channels, on):
    """The five images PW's shunt-first sequence sends, in order.

    ARITHMETIC ONLY -- no wire, no waits, no verify. It is here so that the
    sequence can be asserted image by image off the bench (the proof
    `MW/D24/DSP/s138b/shunt_sequence_check.py`) and so that the station and
    any later tool cannot each grow their own version of it.

    PW 2026-09-16, verbatim from `ref-d24-analog-attach.md`:

        1. shunt ON on every channel whose phantom is about to change
           -- verified load;
        2. wait t1;
        3. phantom toggled, shunt still on -- verified load;
        4. wait t2;
        5. shunt RESTORED to whatever it was before (normally off)
           -- verified load.

    Returns a list of (image, what, wait_after) triples: three images and the
    two waits between them. Step 5 restores the shunt PER CHANNEL to whatever
    that channel's own bit was in `image`, which is what "to whatever it was
    before" means -- not "off", and not "all the same".
    """
    chans = [int(c) for c in channels]
    s1 = with_shunt(image, chans, True)
    s3 = with_phantom(s1, chans, on)
    # per channel, back to its own incoming shunt state
    s5 = list(s3)
    for c in chans:
        s5 = with_shunt(s5, [c], bool(image[c] & SHUNT_BIT))
    return [(s1, 'the phantom shunt engaged, before phantom moves',
             SHUNT_SETTLE_S),
            (s3, 'phantom %s, shunt still engaged' % ('on' if on else 'off'),
             PHANTOM_SETTLE_S),
            (s5, 'the phantom shunt restored to what it was', 0.0)]


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
    # The default is the SAFE image: shunt engaged on all 24, phantom off,
    # gain 0, INSTR1/INSTR2 off in U34's trailing byte.
    img = [int(x, 0) for x in sys.argv[1:]] or [0x01] * 24 + [0x00]
    c = Chain()
    try:
        r = timed(c, img)
        print('%s: %.1f ms a write (min %.1f, max %.1f), read-back %s'
              % ('gpiod' if r['fast'] else 'pinctrl fallback', r['mean_ms'],
                 r['min_ms'], r['max_ms'], 'MATCHES' if r['ok'] else 'MISMATCH'))
    finally:
        c.close()
