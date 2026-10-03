#!/usr/bin/env python3
"""d24_pedal.py -- talk to the P1 foot pedal over its cable (S167).

Runs ON the unit's CM4 (it wants /dev/serial0). `matrix-app` owns that port in
normal operation, so stop it first and put it back, as `d24_bus_probe.py`
requires. The bus is single-user: never run this beside the factory runner.

THE PATH: /dev/serial0 -> MH1 (run mode) -> slave bus -> H1S4, the left switch
MCU, running the S167 relay (`MW/D24/FW/H1S4`) -> USART2 PA2/PA3
-> U36/U37 -> J8 -> P1. Host and H1S4 exchange "/%" comment lines, which
every other panel MCU ignores (see pedal_relay.cs for the wire protocol):
    /%O<N|E>[baud]  open at 8N1 (P1 app) or 8E1 (ROM bootloader)
    /%T<hex>        bytes to the pedal, at most 48 a line
    /%X             close (blink forwarding to the pedal resumes)
    /%I             identity and counters
and pedal bytes come back as /%r<hex> lines.

THE ROM SESSION RULE: a blank or bootloader-bound C031 auto-bauds on the FIRST
byte it receives after power-up. With the relay closed H1S4 forwards ':'/'.'
to the pedal every 254 ms, which trains the ROM wrongly and leaves it deaf
until the next power-up. So: open the relay at 8E1 BEFORE the pedal powers
up (re-plug, or the app's ENTER-BOOTLOADER which resets it), then 0x7F first.

    d24_pedal.py info                         relay identity and counters
    d24_pedal.py open --fmt E|N / close
    d24_pedal.py app --send ':'               send text to the P1 app, print replies
    d24_pedal.py rom-id                       0x7F sync (if needed), Get, Get ID, Get Version
    d24_pedal.py rom-read --addr 0x1FFF7800 --len 16
    d24_pedal.py rom-flash --bin P1.bin [--no-go] [--mass-erase]   erase, write, verify, Go
    d24_pedal.py enter-boot                   the app's "!BOOT", relay re-opened at 8E1 first
    d24_pedal.py update --bin P1.bin          the whole app update (S169): V, !BOOT, ROM
                                              flash, Go, V; the polarity setting is kept
    d24_pedal.py polarity --set A|C|U|?       P1 display polarity: anode, cathode, auto, read
    d24_pedal.py walk [--secs 3]              light each lamp alone, then D9..D0 on all, end all on
    d24_pedal.py --selftest                   off-target: the ROM client against a model

THE SETTINGS PAGE (S169): P1 keeps its settings (display polarity) in flash
page 7 (0x08003800), outside the 14 KB the image may use. rom-flash erases
only the pages the image needs, so the setting survives an update; a first
program on a blank part, or --mass-erase, leaves it blank (= auto). `update`
also reads the setting from `V` before and re-applies it after if it was lost.
"""
import argparse
import os
import sys
import time

PORT = '/dev/serial0'
ACK, NACK = 0x79, 0x1F
FLASH_BASE = 0x08000000
OPTR_ADDR = 0x1FFF7800
PAGE = 2048
SETTINGS_PAGE = 7                      # P1 settings; the image must stay below it


def log(msg):
    print('%s %s' % (time.strftime('%H:%M:%S'), msg), flush=True)


class Relay(object):
    """The /%-line tunnel through MH1 and H1S4."""

    def __init__(self, port=PORT):
        import termios
        self.fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        a = termios.tcgetattr(self.fd)
        a[0] = 0
        a[1] = 0
        a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
        a[3] = 0
        a[4] = a[5] = termios.B115200
        termios.tcsetattr(self.fd, termios.TCSANOW, a)
        termios.tcflush(self.fd, termios.TCIOFLUSH)
        self.partial = b''
        self.rx = bytearray()          # pedal bytes not yet consumed
        self.lines = []                # other /% replies
        self.plus = 0                  # MH1's "+" = ready for the next host line

    def close(self):
        os.close(self.fd)

    def _pump(self, secs):
        t0 = time.time()
        while True:
            try:
                b = os.read(self.fd, 1024)
            except BlockingIOError:
                b = b''
            if b:
                self.partial += b
                while b'\n' in self.partial:
                    line, self.partial = self.partial.split(b'\n', 1)
                    if line.strip() == b'+':
                        self.plus += 1
                        continue
                    i = line.find(b'/%')
                    if i < 0:
                        continue           # MH1 heartbeat, panel traffic
                    body = line[i + 2:].decode('ascii', 'replace')
                    if body.startswith('r'):
                        self.rx += bytes.fromhex(body[1:])
                    else:
                        self.lines.append(body)
            if time.time() - t0 >= secs:
                return
            time.sleep(0.001)

    def _line(self, text):
        """One host line. MH1 holds ONE 100-byte host buffer and answers '+'
        once it has forwarded it to the bus: a second line sent before that
        '+' overwrites the first mid-forward (S167, lost a 48-byte write)."""
        p0 = self.plus
        os.write(self.fd, ('/%' + text + '\n').encode())
        t0 = time.time()
        while self.plus == p0 and time.time() - t0 < 0.3:
            self._pump(0.001)
        if self.plus == p0:
            raise RuntimeError("MH1 did not ask for the next line ('+') within 0.3 s")

    def cmd(self, text, secs=0.5, want=None):
        self._line(text)
        t0 = time.time()
        while time.time() - t0 < secs:
            self._pump(0.005)
            for i, l in enumerate(self.lines):
                if want is None or l.startswith(want):
                    return self.lines.pop(i)
        return None

    def info(self):
        return self.cmd('I', want='i')

    def open(self, fmt='E', baud=115200):
        return self.cmd('O%s%d' % (fmt, baud), want='o')

    def shut(self):
        return self.cmd('X', want='x')

    def send(self, data):
        for i in range(0, len(data), 48):
            self._line('T' + data[i:i + 48].hex().upper())

    def recv(self, n, timeout):
        t0 = time.time()
        while len(self.rx) < n and time.time() - t0 < timeout:
            self._pump(0.002)
        out = bytes(self.rx[:n])
        del self.rx[:n]
        return out

    def drain(self, secs=0.05):
        self._pump(secs)
        out = bytes(self.rx)
        self.rx.clear()
        return out


class RomError(Exception):
    pass


class Rom(object):
    """AN3155 USART bootloader protocol over any object with send/recv/drain."""

    def __init__(self, link, verbose=True):
        self.l = link
        self.verbose = verbose

    def _ack(self, what, timeout=1.0):
        b = self.l.recv(1, timeout)
        if b != bytes([ACK]):
            raise RomError('%s: %s' % (what, 'NACK' if b == bytes([NACK])
                                       else ('no reply' if not b else 'got %s' % b.hex())))

    def _cmd(self, c, what):
        self.l.send(bytes([c, c ^ 0xFF]))
        self._ack(what)

    def sync(self):
        self.l.drain()
        self.l.send(b'\x7f')
        b = self.l.recv(1, 1.0)
        if b == bytes([ACK]):
            return 'ACK'
        if b == bytes([NACK]):
            return 'NACK (already synced)'      # a second 0x7F is a bad command
        raise RomError('sync: %s' % ('no reply' if not b else b.hex()))

    def get(self):
        self._cmd(0x00, 'Get')
        n = self.l.recv(1, 1.0)[0]
        body = self.l.recv(n + 1, 1.0)
        self._ack('Get end')
        return body[0], list(body[1:])

    def get_id(self):
        self._cmd(0x02, 'Get ID')
        n = self.l.recv(1, 1.0)[0]
        pid = self.l.recv(n + 1, 1.0)
        self._ack('Get ID end')
        return int.from_bytes(pid, 'big')

    def _addr(self, addr, what):
        a = addr.to_bytes(4, 'big')
        self.l.send(a + bytes([a[0] ^ a[1] ^ a[2] ^ a[3]]))
        self._ack(what)

    def read(self, addr, n):
        out = b''
        while n:
            k = min(n, 256)
            self._cmd(0x11, 'Read')
            self._addr(addr, 'Read addr 0x%08X' % addr)
            self.l.send(bytes([k - 1, (k - 1) ^ 0xFF]))
            self._ack('Read len')
            got = self.l.recv(k, 2.0)
            if len(got) != k:
                raise RomError('Read 0x%08X: %d of %d bytes' % (addr, len(got), k))
            out += got
            addr += k
            n -= k
        return out

    def recover(self, limit=300):
        """Finish a half-received command: clock 0xFF until the ROM answers."""
        self.l.drain()
        for i in range(limit):
            self.l.send(b'\xff')
            b = self.l.recv(1, 0.05)
            if b:
                return i + 1, b.hex()
        return limit, None

    def mass_erase(self):
        self._cmd(0x44, 'Extended Erase')
        self.l.send(b'\xff\xff\x00')
        self._ack('Mass erase', timeout=10.0)

    def page_erase(self, pages):
        """Extended Erase of a page list (N-1, then 2-byte page numbers, XOR)."""
        self._cmd(0x44, 'Extended Erase')
        body = (len(pages) - 1).to_bytes(2, 'big') + b''.join(p.to_bytes(2, 'big') for p in pages)
        cs = 0
        for b in body:
            cs ^= b
        self.l.send(body + bytes([cs]))
        self._ack('Erase pages %s' % pages, timeout=10.0)

    def write(self, addr, data):
        if len(data) % 4 or not 0 < len(data) <= 256:
            raise RomError('write block must be 4..256 bytes, a multiple of 4')
        self._cmd(0x31, 'Write')
        self._addr(addr, 'Write addr 0x%08X' % addr)
        cs = len(data) - 1
        for b in data:
            cs ^= b
        self.l.send(bytes([len(data) - 1]) + data + bytes([cs]))
        self._ack('Write data 0x%08X' % addr, timeout=2.0)

    def go(self, addr=FLASH_BASE):
        self._cmd(0x21, 'Go')
        self._addr(addr, 'Go addr')

    def flash(self, image, block=64, go=True, mass=False):
        """Erase, write, verify, Go. Returns a timing record. Erases only the
        pages the image covers unless mass=True: page 7 holds P1's settings."""
        t = {}
        t0 = time.time()
        pad = (-len(image)) % 8                 # the C031 programs double words
        image = image + b'\xff' * pad
        npages = (len(image) + PAGE - 1) // PAGE
        if npages > SETTINGS_PAGE:
            raise RomError('image of %d B reaches the settings page %d' % (len(image), SETTINGS_PAGE))
        if mass:
            self.mass_erase()
        else:
            self.page_erase(list(range(npages)))
        t['erased'] = 'mass' if mass else 'pages 0-%d' % (npages - 1)
        t['erase_s'] = round(time.time() - t0, 2)
        t1 = time.time()
        for off in range(0, len(image), block):
            self.write(FLASH_BASE + off, image[off:off + block])
        t['write_s'] = round(time.time() - t1, 2)
        t2 = time.time()
        back = self.read(FLASH_BASE, len(image))
        t['verify_s'] = round(time.time() - t2, 2)
        if back != image:
            bad = next(i for i in range(len(image)) if back[i] != image[i])
            raise RomError('VERIFY FAILED at 0x%08X' % (FLASH_BASE + bad))
        t['verified_bytes'] = len(image)
        if go:
            self.go()
            t['go'] = True
        t['total_s'] = round(time.time() - t0, 2)
        return t


def optr_text(optr):
    return ('OPTR=0x%08X RDP=0x%02X nBOOT_SEL=%d nBOOT1=%d nBOOT0=%d NRST_MODE=%d'
            % (optr, optr & 0xFF, optr >> 24 & 1, optr >> 25 & 1, optr >> 26 & 1, optr >> 27 & 3))


# ---- off-target model ------------------------------------------------------

class RomModel(object):
    """A C031 ROM bootloader good enough to exercise Rom(): sync, Get, Get ID,
    Read, Extended (mass) Erase, Write, Go."""

    def __init__(self):
        self.flash = bytearray(b'\xff' * 16384)
        self.opt = bytearray(b'\xff' * 128)
        self.opt[0:4] = (0xFFFFFEAA).to_bytes(4, 'little')
        self.out = bytearray()
        self.went = None
        self.need = 0
        self.got = bytearray()
        self.co = self._rom()
        self.need = next(self.co)

    def send(self, data):
        for byte in data:
            self.got.append(byte)
            if len(self.got) == self.need:
                d = bytes(self.got)
                self.got.clear()
                self.need = self.co.send(d)

    def recv(self, n, timeout):
        o = bytes(self.out[:n])
        del self.out[:n]
        return o

    def drain(self, secs=0):
        o = bytes(self.out)
        self.out.clear()
        return o

    def _mem(self, addr):
        if FLASH_BASE <= addr < FLASH_BASE + len(self.flash):
            return self.flash, addr - FLASH_BASE
        if OPTR_ADDR <= addr < OPTR_ADDR + len(self.opt):
            return self.opt, addr - OPTR_ADDR
        raise KeyError(addr)

    def _rom(self):
        while (yield 1) != b'\x7f':
            pass
        self.out.append(ACK)
        while True:
            c, x = (yield 2)
            if c ^ x != 0xFF:
                self.out.append(NACK)
                continue
            if c == 0x00:
                cmds = [0x00, 0x01, 0x02, 0x11, 0x21, 0x31, 0x44, 0x63, 0x73, 0x82, 0x92]
                self.out += bytes([ACK, len(cmds), 0x31] + cmds + [ACK])
            elif c == 0x02:
                self.out += bytes([ACK, 1, 0x04, 0x53, ACK])
            elif c in (0x11, 0x31, 0x21):
                self.out.append(ACK)
                addr = int.from_bytes((yield 5)[:4], 'big')
                self.out.append(ACK)
                if c == 0x21:
                    self.went = addr
                elif c == 0x11:
                    n = (yield 2)[0]
                    self.out.append(ACK)
                    mem, off = self._mem(addr)
                    self.out += mem[off:off + n + 1]
                else:
                    n = (yield 1)[0]
                    data = (yield n + 2)[:-1]
                    mem, off = self._mem(addr)
                    mem[off:off + n + 1] = data
                    self.out.append(ACK)
            elif c == 0x44:
                self.out.append(ACK)
                head = yield 2
                n = int.from_bytes(head, 'big')
                if n == 0xFFFF:
                    yield 1
                    self.flash[:] = b'\xff' * len(self.flash)
                else:
                    body = yield 2 * (n + 1) + 1
                    cs = 0
                    for b in head + body[:-1]:
                        cs ^= b
                    if cs != body[-1]:
                        self.out.append(NACK)
                        continue
                    for i in range(n + 1):
                        pg = int.from_bytes(body[2 * i:2 * i + 2], 'big')
                        self.flash[pg * PAGE:(pg + 1) * PAGE] = b'\xff' * PAGE
                self.out.append(ACK)
            else:
                self.out.append(NACK)


def selftest():
    m = RomModel()
    r = Rom(m)
    assert r.sync() == 'ACK'
    ver, cmds = r.get()
    assert ver == 0x31 and 0x44 in cmds
    assert r.get_id() == 0x453
    optr = int.from_bytes(r.read(OPTR_ADDR, 4), 'little')
    assert optr == 0xFFFFFEAA, hex(optr)
    img = bytes((i * 7 + 3) & 0xFF for i in range(2216))
    t = r.flash(img)
    assert bytes(m.flash[:len(img)]) == img and m.went == FLASH_BASE, t
    m.flash[100] ^= 1
    try:
        r.flash(img, go=False)
    except RomError:
        raise AssertionError('a clean re-flash must pass')
    m2 = RomModel()
    r2 = Rom(m2)
    r2.sync()
    real_read = r2.read

    def read_after_flip(addr, n):           # a bit flips in flash after programming
        m2.flash[40] ^= 0x10
        return real_read(addr, n)
    r2.read = read_after_flip
    try:
        r2.flash(img, go=False)
        raise AssertionError('verify must catch a flipped bit')
    except RomError as e:
        assert 'VERIFY FAILED' in str(e)
    # S169: the settings page survives a page-erase update, not a mass erase
    m3 = RomModel()
    rec = (0x50310002).to_bytes(4, 'little') + (0x50310002 ^ 0xFFFFFFFF).to_bytes(4, 'little')
    m3.flash[SETTINGS_PAGE * PAGE:SETTINGS_PAGE * PAGE + 8] = rec
    m3.flash[3000] = 0x00                       # old image content beyond the new one
    r3 = Rom(m3)
    r3.sync()
    t = r3.flash(bytes(4196), go=False)
    assert t['erased'] == 'pages 0-2', t
    assert bytes(m3.flash[SETTINGS_PAGE * PAGE:SETTINGS_PAGE * PAGE + 8]) == rec
    assert m3.flash[5000] == 0xFF               # page 2 was erased with the rest
    r3.flash(bytes(4196), go=False, mass=True)
    assert m3.flash[SETTINGS_PAGE * PAGE] == 0xFF
    try:
        r3.flash(bytes(SETTINGS_PAGE * PAGE + 8), go=False)
        raise AssertionError('an image reaching page 7 must be refused')
    except RomError as e:
        assert 'settings page' in str(e)
    for line, want in (('P1 1.1-s169 uid=0 optr=FFFFFEAA disp=CC by=probe set=auto probe=CC adc=1,2,3,4', 'auto'),
                       ('P1 1.1-s169 uid=0 optr=FFFFFEAA disp=CC by=stored set=CC probe=CC adc=1,2,3,4', 'CC'),
                       ('P1 1.0-s167-cc uid=0 optr=FFFFFEAA', None)):
        assert v_field(line, 'set') == want, line
    print('selftest: OK -- sync, Get, Get ID 0x453, OPTR read, erase/write/verify/Go '
          '(%d B), a flipped bit is caught by verify; page erase keeps the settings page, '
          'mass erase clears it, an image reaching page 7 is refused, V fields parse' % len(img))
    return 0


def v_field(line, key):
    for tok in (line or '').split():
        if tok.startswith(key + '='):
            return tok[len(key) + 1:]
    return None


def app_line(rl, text, want, secs=1.0):
    """Send to the P1 app and return the first reply line starting with want."""
    rl.drain(0.02)
    rl.send(text.encode())
    buf = b''
    t0 = time.time()
    while time.time() - t0 < secs:
        buf += rl.recv(1, 0.05)
        for line in buf.split(b'\n')[:-1]:
            if line.startswith(want.encode()):
                return line.decode('ascii', 'replace')
    return None


WALK = ['LD1', 'LD2', 'LD3', 'LD4', 'seg a', 'seg b', 'seg c', 'seg d', 'seg e', 'seg f',
        'seg g', 'left dot', 'right dot']


def walk(rl, secs):
    """One lamp at a time (bit order of the P1 'L' command), then the
    brightness steps on everything, then everything on at full."""
    for i, name in enumerate(WALK):
        log('%-9s %s' % (name, app_line(rl, 'L%04X' % (1 << i), 'L')))
        time.sleep(secs)
    log('all      %s' % app_line(rl, 'L1FFF', 'L'))
    for d in '9876543210':
        log('bright %s %s' % (d, app_line(rl, 'D' + d, 'D')))
        time.sleep(secs / 2)
    log('end      %s %s' % (app_line(rl, 'D9', 'D'), app_line(rl, 'L1FFF', 'L')))


def update(rl, path):
    """The app update as the D24 app would run it (S167 procedure, S169 setting)."""
    img = open(path, 'rb').read()
    log('image %s: %d B' % (path, len(img)))
    log(rl.open('N'))
    before = app_line(rl, 'V', 'P1 ')
    log('before: %s' % before)
    if before is None:
        raise RuntimeError('the P1 app does not answer V: use rom-id/rom-flash by hand')
    keep = v_field(before, 'set')
    rl.send(b'!BOOT\n')
    log('reply: %r' % rl.recv(6, 1.0))
    log(rl.open('E'))
    rom = Rom(rl)
    log('sync: %s' % rom.sync())
    pid = rom.get_id()
    if pid != 0x453:
        raise RomError('Get ID 0x%03X, not 0x453' % pid)
    optr = int.from_bytes(rom.read(OPTR_ADDR, 4), 'little')
    log(optr_text(optr))
    if optr >> 26 & 1:
        raise RomError('nBOOT0 is 1 in the ROM session: stop')
    log('FLASHED: %s' % rom.flash(img))
    log(rl.open('N'))
    after = None
    for _ in range(10):
        time.sleep(0.5)
        after = app_line(rl, 'V', 'P1 ')
        if after:
            break
    log('after: %s' % after)
    if after is None:
        raise RuntimeError('the new app does not answer V')
    now = v_field(after, 'set')
    if keep in ('CA', 'CC') and now != keep:
        log('setting %s was lost: re-applied: %s' % (keep, app_line(rl, 'P' + keep[1], 'P ', 2.0)))
        log('after: %s' % app_line(rl, 'V', 'P1 '))
    return after


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('action', nargs='?', default='info',
                    choices=['info', 'open', 'close', 'app', 'rom-id', 'rom-read',
                             'rom-flash', 'rom-recover', 'enter-boot', 'update', 'polarity',
                             'walk'])
    ap.add_argument('--fmt', default='E', choices=['E', 'N'])
    ap.add_argument('--send', default=':')
    ap.add_argument('--secs', type=float, default=1.0)
    ap.add_argument('--addr', type=lambda s: int(s, 0), default=OPTR_ADDR)
    ap.add_argument('--len', type=int, default=16)
    ap.add_argument('--bin')
    ap.add_argument('--no-go', action='store_true')
    ap.add_argument('--mass-erase', action='store_true',
                    help='rom-flash: erase everything, the settings page too')
    ap.add_argument('--set', default='?', choices=['A', 'C', 'U', '?'])
    ap.add_argument('--no-sync', action='store_true',
                    help='the ROM session is already trained: skip 0x7F')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    rl = Relay()
    try:
        if a.action == 'info':
            log(rl.info())
        elif a.action == 'open':
            log(rl.open(a.fmt))
        elif a.action == 'close':
            log(rl.shut())
        elif a.action == 'app':
            log(rl.info())
            rl.send(a.send.encode().decode('unicode_escape').encode('latin-1'))
            time.sleep(a.secs)
            log('reply: %r' % rl.drain(0.05))
        elif a.action == 'update':
            update(rl, a.bin)
        elif a.action == 'walk':
            log(rl.open('N'))
            walk(rl, a.secs if a.secs != 1.0 else 3.0)
        elif a.action == 'polarity':
            log(rl.open('N'))
            log(app_line(rl, 'P' + a.set, 'P ', 2.0))
        elif a.action == 'enter-boot':
            log(rl.open('N'))
            rl.send(b'!BOOT\n')
            log('reply: %r' % rl.recv(6, 1.0))
            log(rl.open('E'))           # forwarding stays stopped across the reset
            log('relay at 8E1; the next byte the pedal sees is the 0x7F of rom-id')
        else:
            rom = Rom(rl)
            if not a.no_sync:
                log('sync: %s' % rom.sync())
            if a.action == 'rom-id':
                ver, cmds = rom.get()
                log('Get: bootloader v%d.%d, commands %s' % (ver >> 4, ver & 15,
                                                             ' '.join('%02X' % c for c in cmds)))
                log('Get ID: 0x%03X' % rom.get_id())
                optr = int.from_bytes(rom.read(OPTR_ADDR, 4), 'little')
                log(optr_text(optr))
            elif a.action == 'rom-recover':
                n, b = rom.recover()
                log('recover: %d filler bytes, ROM answered %s' % (n, b))
                ver, cmds = rom.get()
                log('Get after recover: v%d.%d' % (ver >> 4, ver & 15))
            elif a.action == 'rom-read':
                log(rom.read(a.addr, a.len).hex())
            elif a.action == 'rom-flash':
                img = open(a.bin, 'rb').read()
                log('image %s: %d B' % (a.bin, len(img)))
                t = rom.flash(img, go=not a.no_go, mass=a.mass_erase)
                log('FLASHED: %s' % t)
        log(rl.info())
    finally:
        rl.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
