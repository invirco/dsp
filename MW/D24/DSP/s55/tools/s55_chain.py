"""s55_chain.py — the 25-byte 595 image by spidev (the wire protocol of `app cli chain-set`: MSB first, send position
p = 0 first, two passes, CS_M = GPIO 27 low for the shift and high to latch, pass-2 MISO must equal the image).
Needed because chain-set cannot put a gain on send position 0 (J42's register, printed there as SHIFT).
spidev mode/speed/no_cs are restored afterwards: the DSP link shares /dev/spidev0.0 (mode 1)."""
import subprocess, sys
import spidev


def gpio(spec):
    subprocess.run(['sudo', 'pinctrl', 'set'] + spec.split(), check=True)


def send(image, speed=100000):
    assert len(image) == 25
    spi = spidev.SpiDev(); spi.open(0, 0)
    old = (spi.mode, spi.max_speed_hz, spi.no_cs)
    try:
        spi.no_cs = True; spi.mode = 0; spi.max_speed_hz = speed
        got = []
        for _ in range(2):
            gpio('27 op dl')
            got.append(spi.xfer2(list(image)))
            gpio('27 op dh')
        ok = got[1] == list(image)
    finally:
        spi.mode, spi.max_speed_hz, spi.no_cs = old
        spi.close()
        gpio('6,24 op dh')
    return ok, got


def byte(mute=0, phantom=0, gain=0):
    return (gain & 63) << 2 | (phantom & 1) << 1 | (mute & 1)


if __name__ == '__main__':
    img = [int(x, 0) for x in sys.argv[1:]]
    ok, got = send(img)
    print('VERIFIED 200/200' if ok else 'MISMATCH', ' '.join('%02X' % b for b in got[1]), '| pass1', ' '.join('%02X' % b for b in got[0]))
