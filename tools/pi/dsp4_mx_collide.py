#!/usr/bin/env python3
"""S31 gate 4 -- name the lost announce.  Replays the app's S_RESET x2 / S_RUN
sequence with matrix-app stopped and dumps the RAW bytes of the announce burst,
so a lost announce can be told apart from a garbled one."""
import os, termios, time, select, argparse, re

def open_raw(dev):
    fd = os.open(dev, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    cc = list(termios.tcgetattr(fd)[6]); cc[termios.VMIN] = 0; cc[termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW,
        [0, 0, termios.CS8 | termios.CREAD | termios.CLOCAL, 0,
         termios.B115200, termios.B115200, cc])
    termios.tcflush(fd, termios.TCIOFLUSH); return fd

p = argparse.ArgumentParser()
p.add_argument('--defer', type=float, default=1.0)
p.add_argument('--gap', type=float, default=3.47)
p.add_argument('--trials', type=int, default=24)
a = p.parse_args()

ok = bad = 0
for t in range(1, a.trials + 1):
    fd = open_raw('/dev/ttyAMA0')
    os.write(fd, b'*\n'); os.write(fd, b'*\n')
    time.sleep(a.gap)
    os.write(fd, b'+\n')
    time.sleep(a.defer)
    buf = bytearray(); end = time.time() + 8.0
    while time.time() < end:
        if select.select([fd], [], [], 0.05)[0]:
            try: buf += os.read(fd, 65536)
            except BlockingIOError: pass
    os.close(fd)
    txt = buf.decode('latin-1')
    got = [m for m in ('H1S1', 'H1S3', 'H1S4') if m in txt]
    if len(got) == 3:
        ok += 1; print(f"  trial {t:2d}: 3 of 3   rx={len(buf)}B", flush=True)
    else:
        bad += 1
        print(f"  trial {t:2d}: {len(got)} of 3 {got}   rx={len(buf)}B   RAW ANNOUNCE BURST:", flush=True)
        # isolate from '// resuming' to the last '//' line
        i = txt.find('// resuming')
        seg = buf[i if i >= 0 else 0:][:200]
        for off in range(0, len(seg), 16):
            chunk = seg[off:off+16]
            hexs = ' '.join(f'{b:02x}' for b in chunk)
            asc = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            print(f"      {off:04x}  {hexs:<47}  |{asc}|", flush=True)
    time.sleep(0.8)
print(f"### defer={a.defer}s  {ok} clean / {bad} garbled of {a.trials}", flush=True)
