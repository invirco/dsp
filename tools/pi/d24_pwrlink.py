#!/usr/bin/env python3
"""d24_pwrlink.py -- the CM4's link to the power MCU U34 (2026-10-15).

Runs ON the unit's CM4. Wire: AN_EN (GPIO26, host -> U34 PA10) carries
pulse-width-coded frames, PI_SD (U34 PA5 -> GPIO4) carries the replies; the
format is MW/D24/FW/PWR/link.h and the commands MW/D24/FW/PWR/proto.h (keep
the constants below in step with both). Same nets on rev C and rev D.

    d24_pwrlink.py ping                  mode, version, state, rails, pedal
    d24_pwrlink.py alive                 pedal heartbeat (rev D)
    d24_pwrlink.py hold --secs 60        UPDATE HOLD: pedal supply held, heartbeat check off
    d24_pwrlink.py release               end the hold
    d24_pwrlink.py cycle --off-ms 1000   pedal power-cycle (clamp, wait, re-probe)
    d24_pwrlink.py enter-boot            app -> bootloader (needs AN_EN low: analog off)
    d24_pwrlink.py check                 bootloader: app valid? length, CRC
    d24_pwrlink.py update --img pwr-mcu.img   option 2: the whole app update
    d24_pwrlink.py go                    bootloader: start the app
    d24_pwrlink.py --selftest            off-target: encoder/decoder, jitter, stretch

PREREQUISITES ON THE UNIT. matrix-app's shutdown watch (gpiomon on GPIO4)
holds PI_SD, so stop matrix-app first and start it again after. AN_EN keeps
the level it had (read with pinctrl): frames are excursions from it, and the
power MCU only acts on AN_EN held for 20 ms, so a frame never moves the
analog rails. `update` needs AN_EN LOW (the app refuses ENTER_BOOT while the
converter clocks run) and the rocker ON throughout: in the bootloader the
rails follow the rocker with no orderly save. An interrupted update leaves
the bootloader listening (triple blink), rails per the rocker; run `update`
again.
"""
import argparse
import os
import struct
import subprocess
import sys
import time
import zlib

AN_EN, PI_SD = 26, 4

# link.h
W_GLITCH, W_SPLIT01, W_SPLIT1S, W_LEVEL, W_END = 60, 400, 900, 2000, 3000
T_ZERO, T_ONE, T_START, T_GAP = 200, 600, 1400, 200
MAX_PAYLOAD = 68

# proto.h
CMD_PING, CMD_P1_ALIVE, CMD_P1_HOLD, CMD_P1_RELEASE, CMD_P1_CYCLE = 0x01, 0x10, 0x11, 0x12, 0x13
CMD_ENTER_BOOT, CMD_ERASE, CMD_WRITE, CMD_READ, CMD_CHECK, CMD_GO = 0x20, 0x30, 0x31, 0x32, 0x33, 0x34
STATUS = {0: 'OK', 1: 'UNKNOWN', 2: 'BAD_ARG', 3: 'FLASH', 4: 'VERIFY', 5: 'REFUSED', 6: 'INVALID'}
STATES = {0: 'STANDBY', 1: 'BOOT', 2: 'ON', 3: 'SHUTDOWN'}
P1_STATES = {0: 'off', 1: 'discharge', 2: 'measure', 3: 'ON', 4: 'cycle-off'}
P1_WHY = {0: '-', 1: 'no signature', 2: 'heartbeat lost', 3: 'rails down', 4: 'host cycle'}
APP_MAX = 12 * 1024
APP_MAGIC = 0x4D583236


def log(msg):
    print('%s %s' % (time.strftime('%H:%M:%S'), msg), flush=True)


class LinkError(Exception):
    pass


def crc16(data):
    c = 0xFFFF
    for b in data:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c


def frame(cmd, payload=b''):
    if len(payload) > MAX_PAYLOAD:
        raise LinkError('payload %d > %d' % (len(payload), MAX_PAYLOAD))
    body = bytes([cmd, len(payload)]) + bytes(payload)
    return body + struct.pack('>H', crc16(body))


def encode(data):
    """Frame bytes -> pulse widths in us (START first), MSB first."""
    w = [T_START]
    for b in data:
        for k in range(7, -1, -1):
            w.append(T_ONE if b >> k & 1 else T_ZERO)
    return w


def decode_runs(runs, idle=0):
    """[(level, us), ...] -> list of complete, CRC-good frames (bytes).
    The same classifier as link.c, on measured run lengths."""
    frames, bits, in_frame = [], [], False

    def close():
        if in_frame and len(bits) % 8 == 0 and len(bits) >= 32:
            d = bytes(int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8))
            if len(d) == d[1] + 4 and crc16(d[:-2]) == struct.unpack('>H', d[-2:])[0]:
                frames.append(d)

    for lev, us in runs:
        if lev == idle:
            if in_frame and us >= W_END:
                close()
                in_frame, bits = False, []
            continue
        if us < W_GLITCH:
            continue
        if us < W_SPLIT01:
            bits.append(0)
        elif us < W_SPLIT1S:
            bits.append(1)
        elif us < W_LEVEL:
            in_frame, bits = True, []
        else:                       # a level change, not a pulse
            in_frame, bits = False, []
    close()
    return frames


def pinctrl_level(gpio):
    """Current output level of a GPIO without touching it (pinctrl get)."""
    out = subprocess.run(['pinctrl', 'get', str(gpio)], capture_output=True, text=True).stdout
    return 1 if ' hi' in out else 0


class Wire(object):
    """gpiod v2: AN_EN out (kept at its present level), PI_SD in with edges."""

    def __init__(self):
        import gpiod
        from gpiod.line import Direction, Edge, Value
        self.V = Value
        self.idle = pinctrl_level(AN_EN)
        try:
            self.req = gpiod.request_lines(
                '/dev/gpiochip0', consumer='d24_pwrlink',
                config={AN_EN: gpiod.LineSettings(
                            direction=Direction.OUTPUT,
                            output_value=Value.ACTIVE if self.idle else Value.INACTIVE),
                        PI_SD: gpiod.LineSettings(direction=Direction.INPUT, edge_detection=Edge.BOTH)})
        except OSError as e:
            raise LinkError('cannot claim GPIO%d/GPIO%d (%s): stop matrix-app first '
                            '(its shutdown watch holds GPIO4)' % (AN_EN, PI_SD, e))
        try:
            os.sched_setaffinity(0, {3})
            os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(50))
        except (OSError, AttributeError):
            pass                    # timing still good on an idle CM4; CRC catches the rest

    def close(self):
        self.req.release()

    def _set(self, lev):
        self.req.set_value(AN_EN, self.V.ACTIVE if lev else self.V.INACTIVE)

    def send(self, data):
        while self.req.wait_edge_events(0):
            self.req.read_edge_events()          # stale reply edges
        busy = time.perf_counter_ns
        t = busy()
        for w in encode(data):
            self._set(1 - self.idle)
            end = t + w * 1000
            while busy() < end:
                pass
            self._set(self.idle)
            t = busy()
            end = t + T_GAP * 1000
            while busy() < end:
                pass
            t = busy()

    def recv(self, timeout):
        """Edges on PI_SD until a frame closes or timeout; returns frames."""
        runs, level, t_prev = [], 0, None
        t_end = time.monotonic() + timeout
        while True:
            left = t_end - time.monotonic()
            quiet = W_END / 1e6 * 2 if t_prev is not None else left
            if left <= 0:
                break
            if not self.req.wait_edge_events(min(left, quiet)):
                if t_prev is not None:
                    runs.append((level, W_END * 2))
                    f = decode_runs(runs)
                    if f:
                        return f
                    runs, t_prev = [], None
                continue
            for ev in self.req.read_edge_events():
                t = ev.timestamp_ns / 1000.0
                if t_prev is not None:
                    runs.append((level, t - t_prev))
                t_prev = t
                level = 1 if ev.event_type == ev.Type.RISING_EDGE else 0
        return []


class Pwr(object):
    def __init__(self, wire, retries=3):
        self.w = wire
        self.retries = retries

    def call(self, cmd, payload=b'', timeout=0.5):
        data = frame(cmd, payload)
        for attempt in range(self.retries):
            self.w.send(data)
            for f in self.w.recv(timeout):
                if f[0] == cmd | 0x80:
                    return f[2], f[3:-2]
            log('  no reply to 0x%02X (try %d of %d)' % (cmd, attempt + 1, self.retries))
        raise LinkError('no reply to command 0x%02X' % cmd)

    def ok(self, cmd, payload=b'', timeout=0.5):
        st, rest = self.call(cmd, payload, timeout)
        if st != 0:
            raise LinkError('command 0x%02X: %s' % (cmd, STATUS.get(st, st)))
        return rest

    def ping(self):
        rest = self.ok(CMD_PING)
        if rest[:1] == b'B':
            return {'mode': 'bootloader', 'boot_version': rest[1],
                    'reason': {1: 'requested', 2: 'no valid app'}.get(rest[2], rest[2]),
                    'app_valid': bool(rest[3]), 'rocker_on': bool(rest[4])}
        fl = rest[4]
        return {'mode': 'app', 'version': '%d.%d' % (rest[1], rest[2]),
                'state': STATES.get(rest[3], rest[3]),
                'rocker_on': bool(fl & 1), 'v12_ok': bool(fl & 2), 'an_en': bool(fl & 4),
                'clocks': bool(fl & 8), 'ups_en': bool(fl & 16), 'dig_en': bool(fl & 32),
                'p1': P1_STATES.get(rest[5], rest[5]), 'p1_why': P1_WHY.get(rest[6], rest[6]),
                'hold_s': rest[7], 'p1_early': rest[8] << 8 | rest[9], 'p1_late': rest[10] << 8 | rest[11],
                'p1_probes': rest[12], 'p1_enables': rest[13], 'p1_reclamps': rest[14],
                'resets': rest[15]}

    def wait_mode(self, mode, secs=5.0):
        t_end = time.time() + secs
        while time.time() < t_end:
            try:
                p = self.ping()
                if p['mode'] == mode:
                    return p
            except LinkError:
                pass
            time.sleep(0.2)
        raise LinkError('power MCU never answered as %s' % mode)

    def update(self, img):
        if len(img) > APP_MAX or struct.unpack_from('<I', img, 0x10)[0] != APP_MAGIC:
            raise LinkError('not a pwr-mcu app image')
        ln = struct.unpack_from('<I', img, 0x14)[0]
        crc = struct.unpack_from('<I', img, ln)[0]
        if ln != len(img) - 4 or zlib.crc32(img[:ln]) & 0xFFFFFFFF != crc:
            raise LinkError('image header/CRC inconsistent (run mkimage.py)')
        p = self.ping()
        log('found: %s' % p)
        if p['mode'] == 'app':
            if p['clocks']:
                raise LinkError('analog clocks running: take AN_EN low first')
            self.ok(CMD_ENTER_BOOT, b'BOOT')
            p = self.wait_mode('bootloader')
            log('bootloader: %s' % p)
        t0 = time.time()
        self.ok(CMD_ERASE, b'ERAS', timeout=2.0)
        log('erased 12 pages (%.1f s)' % (time.time() - t0))
        for off in range(0, len(img), 64):
            self.ok(CMD_WRITE, struct.pack('>H', off) + img[off:off + 64])
        log('wrote %d B (%.1f s)' % (len(img), time.time() - t0))
        rest = self.ok(CMD_CHECK)
        got_len, got_crc = struct.unpack('>II', rest[1:9])
        if not rest[0] or got_len != ln or got_crc != crc:
            raise LinkError('CHECK failed: valid=%d len=0x%X crc=0x%08X' % (rest[0], got_len, got_crc))
        log('CHECK: valid, len 0x%X, crc 0x%08x' % (got_len, got_crc))
        self.ok(CMD_GO)
        p = self.wait_mode('app')
        log('running: %s (%.1f s total)' % (p, time.time() - t0))
        return p


def selftest():
    import random
    rnd = random.Random(7)
    bad = 0
    for i in range(2000):
        pl = bytes(rnd.randrange(256) for _ in range(rnd.randrange(MAX_PAYLOAD + 1)))
        d = frame(rnd.randrange(256), pl)
        runs = []
        for w in encode(d):
            runs.append((1, w + rnd.uniform(-30, 120)))     # gpiod call overhead, jitter
            runs.append((0, T_GAP + rnd.uniform(0, 150)))
        runs.append((0, W_END + 1))
        if decode_runs(runs) != [d]:
            bad += 1
    wrong = 0
    for i in range(2000):
        d = frame(0x31, bytes(rnd.randrange(256) for _ in range(8)))
        runs = []
        k = rnd.randrange(len(d) * 8 + 1)
        for j, w in enumerate(encode(d)):
            runs.append((1, w + (rnd.uniform(150, 3000) if j == k else 0)))
            runs.append((0, T_GAP))
        runs.append((0, W_END + 1))
        f = decode_runs(runs)
        wrong += bool(f and f != [d])
    print('python codec: %d of 2000 jittered frames lost, %d wrong frames from 2000 stretched' % (bad, wrong))
    ok = bad == 0 and wrong == 0
    print('PWRLINK SELFTEST %s' % ('PASSED' if ok else 'FAILED'))
    return 0 if ok else 1


def runs_from_file(path):
    return [(int(a), float(b)) for a, b in (ln.split() for ln in open(path) if ln.strip())]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('cmd', nargs='?', choices=['ping', 'alive', 'hold', 'release', 'cycle',
                                               'enter-boot', 'check', 'update', 'go'])
    ap.add_argument('--secs', type=int, default=60)
    ap.add_argument('--off-ms', type=int, default=1000)
    ap.add_argument('--img')
    ap.add_argument('--selftest', action='store_true')
    ap.add_argument('--emit-line', metavar='FILE', help='off-target: write a test frame as (level us) runs')
    ap.add_argument('--decode-line', metavar='FILE', help='off-target: decode (level us) runs')
    a = ap.parse_args()

    if a.selftest:
        return selftest()
    if a.emit_line:
        with open(a.emit_line, 'w') as f:
            f.write('0 1000\n')
            for w in encode(frame(0x31, bytes(i * 17 & 0xFF for i in range(16)))):
                f.write('1 %d\n0 %d\n' % (w, T_GAP))
            f.write('0 5000\n')
        return 0
    if a.decode_line:
        fr = decode_runs(runs_from_file(a.decode_line))
        print(' '.join('%02x' % b for b in fr[0][:1] + fr[0][2:-2]) if fr else 'none')
        return 0 if fr else 1
    if not a.cmd:
        ap.error('a command is required')

    w = Wire()
    try:
        p = Pwr(w)
        if a.cmd == 'ping':
            for k, v in p.ping().items():
                print('%-12s %s' % (k, v))
        elif a.cmd == 'alive':
            st, _ = p.call(CMD_P1_ALIVE)
            print(STATUS.get(st, st), '(REFUSED = pedal supply not on)' if st == 5 else '')
        elif a.cmd == 'hold':
            p.ok(CMD_P1_HOLD, bytes([a.secs]))
            print('hold %d s' % a.secs)
        elif a.cmd == 'release':
            p.ok(CMD_P1_RELEASE)
        elif a.cmd == 'cycle':
            p.ok(CMD_P1_CYCLE, struct.pack('>H', a.off_ms))
        elif a.cmd == 'enter-boot':
            p.ok(CMD_ENTER_BOOT, b'BOOT')
            print(p.wait_mode('bootloader'))
        elif a.cmd == 'check':
            rest = p.ok(CMD_CHECK)
            print('valid=%d len=0x%X crc=0x%08X' % ((rest[0],) + struct.unpack('>II', rest[1:9])))
        elif a.cmd == 'go':
            p.ok(CMD_GO)
            print(p.wait_mode('app'))
        elif a.cmd == 'update':
            p.update(open(a.img, 'rb').read())
    finally:
        w.close()
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except LinkError as e:
        log('ERROR: %s' % e)
        sys.exit(2)
