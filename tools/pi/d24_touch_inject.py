#!/usr/bin/env python3
"""d24_touch_inject.py -- press a point on the D24's screen from a shell.

Runs ON THE UNIT. Creates a single-touch absolute pointing device through
`/dev/uinput` and taps the given display coordinates, so a dispatched session
with no hands at the bench can exercise a touch-driven skin and read the result
out of the app's own log.

    sudo python3 d24_touch_inject.py 1234 567           # one tap
    sudo python3 d24_touch_inject.py 1234 567 --hold 0.4

    sudo python3 d24_touch_inject.py --serve /tmp/tap &   # hold the device open
    echo "1234 567" > /tmp/tap                           # ... and tap into it

AVALONIA'S DRM BACKEND ENUMERATES INPUT DEVICES ONCE, AT STARTUP, AND DOES NOT
WATCH FOR HOTPLUG. A device created after `matrix-app` started is therefore
invisible to it, however correct the device is -- which is exactly what a first
attempt looks like: the kernel logs the new input, and the app never sees a
press. `--serve` exists for that: create the device, restart `matrix-app` with it
already present, then tap through the FIFO for as long as the server runs.

WHAT THIS IS AND IS NOT. It is a real input device: udev announces it, libinput
opens it, and Avalonia's DRM backend delivers the press to the control under the
point exactly as it delivers one from the panel's own ILITEK controller. It is
NOT a test of the ILITEK controller, the touch cable, or the panel -- a tap that
lands here proves the skin and the app, and proves nothing at all about the
hardware path PW's finger uses. Say which one was exercised when reporting a
result.

The device is created, used and destroyed in one run, so nothing is left behind
for the next boot to find.
"""
import argparse
import ctypes
import fcntl
import os
import struct
import sys
import time

UINPUT = '/dev/uinput'

EV_SYN, EV_KEY, EV_ABS = 0x00, 0x01, 0x03
SYN_REPORT = 0
ABS_X, ABS_Y = 0x00, 0x01
BTN_TOUCH = 0x14a
INPUT_PROP_DIRECT = 0x01

ABS_CNT = 64

# _IO/_IOW on this ABI: dir<<30 | size<<16 | 'U'<<8 | nr
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502


def _iow(nr, size):
    return (1 << 30) | (size << 16) | (ord('U') << 8) | nr


UI_SET_EVBIT = _iow(100, 4)
UI_SET_KEYBIT = _iow(101, 4)
UI_SET_ABSBIT = _iow(103, 4)
UI_SET_PROPBIT = _iow(110, 4)


def uinput_user_dev(name, maxx, maxy):
    """The pre-UI_DEV_SETUP device description: 80-byte name, input_id, an
    ff_effects_max, then absmax/absmin/absfuzz/absflat arrays of ABS_CNT."""
    buf = bytearray()
    buf += name.encode()[:79].ljust(80, b'\0')
    buf += struct.pack('HHHH', 0x03, 0x2222, 0x0002, 1)   # bustype USB, ours
    buf += struct.pack('I', 0)                            # ff_effects_max
    absmax = [0] * ABS_CNT
    absmin = [0] * ABS_CNT
    absmax[ABS_X], absmax[ABS_Y] = maxx, maxy
    for arr in (absmax, absmin, [0] * ABS_CNT, [0] * ABS_CNT):
        buf += struct.pack('%di' % ABS_CNT, *arr)
    return bytes(buf)


def ev(fd, etype, code, value):
    # struct input_event on 64-bit: two longs of timeval, then u16,u16,s32
    os.write(fd, struct.pack('llHHi', 0, 0, etype, code, value))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('x', type=int, nargs='?')
    ap.add_argument('y', type=int, nargs='?')
    ap.add_argument('--serve', metavar='FIFO',
                    help='create the device and keep it open, tapping each "x y '
                         '[hold]" line written to this FIFO until the FIFO is '
                         'removed or the process is killed')
    ap.add_argument('--width', type=int, default=1920)
    ap.add_argument('--height', type=int, default=1080)
    ap.add_argument('--hold', type=float, default=0.15,
                    help='seconds between press and release (default 0.15)')
    ap.add_argument('--settle', type=float, default=1.0,
                    help='seconds to wait after creating the device so udev and '
                         'libinput have opened it (default 1.0)')
    a = ap.parse_args()

    if not os.path.exists(UINPUT):
        sys.exit('no %s -- the uinput module is not loaded' % UINPUT)

    try:
        fd = os.open(UINPUT, os.O_WRONLY | os.O_NONBLOCK)
    except PermissionError:
        sys.exit('cannot open %s -- run with sudo' % UINPUT)

    try:
        fcntl.ioctl(fd, UI_SET_PROPBIT, INPUT_PROP_DIRECT)   # a touchSCREEN
        fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
        fcntl.ioctl(fd, UI_SET_KEYBIT, BTN_TOUCH)
        fcntl.ioctl(fd, UI_SET_EVBIT, EV_ABS)
        fcntl.ioctl(fd, UI_SET_ABSBIT, ABS_X)
        fcntl.ioctl(fd, UI_SET_ABSBIT, ABS_Y)
        os.write(fd, uinput_user_dev('d24-touch-inject',
                                     a.width - 1, a.height - 1))
        fcntl.ioctl(fd, UI_DEV_CREATE)

        # libinput opens the device on a udev event, not on our schedule.
        time.sleep(a.settle)

        def tap(x, y, hold):
            ev(fd, EV_ABS, ABS_X, x)
            ev(fd, EV_ABS, ABS_Y, y)
            ev(fd, EV_KEY, BTN_TOUCH, 1)
            ev(fd, EV_SYN, SYN_REPORT, 0)
            time.sleep(hold)
            ev(fd, EV_KEY, BTN_TOUCH, 0)
            ev(fd, EV_SYN, SYN_REPORT, 0)
            time.sleep(0.2)

        if a.serve:
            if not os.path.exists(a.serve):
                os.mkfifo(a.serve, 0o666)
                os.chmod(a.serve, 0o666)
            print('serving taps on %s (device is open; restart matrix-app now)'
                  % a.serve, flush=True)
            while os.path.exists(a.serve):
                with open(a.serve) as fifo:
                    for line in fifo:
                        parts = line.split()
                        if not parts:
                            continue
                        if parts[0] in ('quit', 'stop'):
                            return
                        try:
                            x, y = int(parts[0]), int(parts[1])
                            hold = float(parts[2]) if len(parts) > 2 else a.hold
                        except (IndexError, ValueError):
                            print('bad tap line: %r' % line.strip(), flush=True)
                            continue
                        tap(x, y, hold)
                        print('tapped %d,%d (hold %.2f s)' % (x, y, hold),
                              flush=True)
            return

        if a.x is None or a.y is None:
            sys.exit('give x and y, or --serve FIFO')
        tap(a.x, a.y, a.hold)
        print('tapped %d,%d (hold %.2f s)' % (a.x, a.y, a.hold))
    finally:
        try:
            fcntl.ioctl(fd, UI_DEV_DESTROY)
        except OSError:
            pass
        os.close(fd)


if __name__ == '__main__':
    main()
