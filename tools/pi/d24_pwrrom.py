#!/usr/bin/env python3
"""d24_pwrrom.py -- option 4: program a BLANK power MCU (U34, STM32F030F4)
through its ST ROM bootloader on USART1 PA9 (TX) / PA10 (RX), 8E1 (2026-10-15).

    d24_pwrrom.py id      --port /dev/ttyAMA3          sync, Get, Get ID (0x444)
    d24_pwrrom.py program --port /dev/ttyAMA3 --boot boot.bin --img pwr-mcu.img [--wrp]
    d24_pwrrom.py --selftest                           off-target, against a ROM model

program = mass erase, bootloader at 0x08000000, app image at 0x08001000, read
back both, then either Write Protect sector 0 (--wrp: pages 0-3, the ROM
resets the part and it boots the new bootloader) or Go 0x08000000.

HARDWARE PREREQUISITES — NOT MET BY THE NETS AS KNOWN (report-2026-10-15.md):
  1. BOOT0 high through a reset. The F030x4 has NO empty-flash check (RM0360:
     only F070x6/F030xC have one), so a blank U34 with BOOT0 low never
     reaches the ROM. U34 BOOT0 = BUS_BOOT with R103 10K to GND, and NRST
     reaches only J32 — neither is driven by the CM4.
  2. A CM4 UART on PA9/PA10. PA10 is AN_EN (CM4 GPIO26, not a UART TX pin)
     and PA9 is PWR_FAIL (CM4 WL_nDisable/BT_nDisable, not readable as a
     UART RX). The ROM needs both directions (ACK after every step).
Until the rev D copper is confirmed to provide both, a blank U34 is
programmed over SWD (ch1 / fifth channel), as ruled 2026-10-14; option 2
(d24_pwrlink.py) updates a part that already has this bootloader.
The protocol layer is d24_pedal.Rom (AN3155), proven on the P1 C031 (S167).
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from d24_pedal import Rom, RomError, RomModel   # noqa: E402

FLASH = 0x08000000
APP = 0x08001000
F030X4_PID = 0x444


def log(msg):
    print('%s %s' % (time.strftime('%H:%M:%S'), msg), flush=True)


class Tty(object):
    """Raw termios link at 8E1 (the ROM auto-bauds on the 0x7F)."""

    def __init__(self, port, baud=115200):
        import termios
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY)
        a = termios.tcgetattr(self.fd)
        a[0] = a[1] = a[3] = 0
        a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL | termios.PARENB
        speed = getattr(termios, 'B%d' % baud)
        a[4] = a[5] = speed
        termios.tcsetattr(self.fd, termios.TCSANOW, a)
        termios.tcflush(self.fd, termios.TCIOFLUSH)

    def send(self, data):
        os.write(self.fd, data)

    def recv(self, n, timeout):
        import select
        out = b''
        t_end = time.time() + timeout
        while len(out) < n:
            left = t_end - time.time()
            if left <= 0 or not select.select([self.fd], [], [], left)[0]:
                break
            out += os.read(self.fd, n - len(out))
        return out

    def drain(self, secs=0.05):
        return self.recv(4096, secs)


class F030Rom(Rom):
    """AN3155 for the F030x4: legacy Erase (0x43) when the ROM lists no
    Extended Erase, and Write Protect of sector 0."""

    def erase_all(self, cmds):
        if 0x44 in cmds:
            return self.mass_erase()
        self._cmd(0x43, 'Erase')
        self.l.send(b'\xff\x00')
        self._ack('Global erase', timeout=10.0)

    def write_protect_sector0(self):
        self._cmd(0x63, 'Write Protect')
        self.l.send(bytes([0, 0, 0]))            # N-1 = 0, sector 0, checksum
        self._ack('WRP sector 0', timeout=5.0)   # the ROM then resets the part

    def write_image(self, base, data, block=64):
        data = data + b'\xff' * (-len(data) % 4)
        for off in range(0, len(data), block):
            self.write(base + off, data[off:off + block])
        back = self.read(base, len(data))
        if back != data:
            bad = next(i for i in range(len(data)) if back[i] != data[i])
            raise RomError('VERIFY FAILED at 0x%08X' % (base + bad))
        return len(data)


def program(rom, boot, img, wrp):
    if len(boot) > 4096 or len(img) > 12 * 1024:
        raise RomError('boot %d B / app %d B exceed 4 KB / 12 KB' % (len(boot), len(img)))
    log('sync: %s' % rom.sync())
    ver, cmds = rom.get()
    pid = rom.get_id()
    log('ROM v%d.%d, PID 0x%03X, commands %s' % (ver >> 4, ver & 15, pid, ' '.join('%02X' % c for c in cmds)))
    if pid != F030X4_PID:
        raise RomError('PID 0x%03X is not an STM32F030x4 (0x444)' % pid)
    rom.erase_all(cmds)
    log('erased; boot %d B verified' % rom.write_image(FLASH, boot))
    log('app %d B verified' % rom.write_image(APP, img))
    if wrp:
        rom.write_protect_sector0()
        log('WRP set on pages 0-3; the ROM resets the part into the new bootloader')
    else:
        rom.go(FLASH)
        log('Go 0x08000000')


def selftest():
    m = RomModel()

    def get_id():                               # the model is a C031: answer as an F030x4
        return F030X4_PID
    r = F030Rom(m)
    r.get_id = get_id
    boot = bytes((i * 5 + 1) & 0xFF for i in range(2624))
    img = bytes((i * 3 + 7) & 0xFF for i in range(3868))
    program(r, boot, img, wrp=False)
    assert bytes(m.flash[:len(boot)]) == boot and bytes(m.flash[4096:4096 + len(img)]) == img
    assert m.went == FLASH
    try:
        program(F030Rom(RomModel()), boot, img, wrp=False)   # a C031 PID must be refused
        raise AssertionError('wrong PID accepted')
    except RomError as e:
        assert 'not an STM32F030x4' in str(e)
    print('PWRROM SELFTEST PASSED: mass erase, boot @0x08000000 + app @0x08001000 written and '
          'read back, Go; a non-F030x4 PID refused')
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', nargs='?', choices=['id', 'program'])
    ap.add_argument('--port')
    ap.add_argument('--boot')
    ap.add_argument('--img')
    ap.add_argument('--wrp', action='store_true')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if not a.cmd or not a.port:
        ap.error('a command and --port are required')
    rom = F030Rom(Tty(a.port))
    if a.cmd == 'id':
        log('sync: %s' % rom.sync())
        ver, cmds = rom.get()
        log('ROM v%d.%d PID 0x%03X commands %s' % (ver >> 4, ver & 15, rom.get_id(),
                                                   ' '.join('%02X' % c for c in cmds)))
    else:
        program(rom, open(a.boot, 'rb').read(), open(a.img, 'rb').read(), a.wrp)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except RomError as e:
        log('ERROR: %s' % e)
        sys.exit(2)
