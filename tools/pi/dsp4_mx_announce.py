#!/usr/bin/env python3
"""S31 gate 2 -- the MX bus announce as seen on the wire.

Opens /dev/ttyAMA0 raw 8N1 at the app's rate (115200, from Boot.cs) and
either listens passively or replays the app's own opening sequence:
S_RESET '*' twice, then S_RUN '+' after the app's measured 3.47 s gap.
Every byte is timestamped on arrival. Touches nothing but the UART.
"""
import os, sys, termios, time, select, argparse

BAUD = {115200: termios.B115200, 57600: termios.B57600, 9600: termios.B9600}

def open_raw(dev, baud):
    fd = os.open(dev, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    a = termios.tcgetattr(fd)
    iflag, oflag, cflag, lflag, ispeed, ospeed, cc = a
    iflag = 0
    oflag = 0
    cflag = termios.CS8 | termios.CREAD | termios.CLOCAL
    lflag = 0
    cc = list(cc); cc[termios.VMIN] = 0; cc[termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW,
                      [iflag, oflag, cflag, lflag, BAUD[baud], BAUD[baud], cc])
    termios.tcflush(fd, termios.TCIOFLUSH)
    return fd

def pump(fd, until, t0, lines, partial):
    while time.time() < until:
        r, _, _ = select.select([fd], [], [], 0.05)
        if not r:
            continue
        try:
            data = os.read(fd, 4096)
        except BlockingIOError:
            continue
        now = time.time() - t0
        for b in data:
            if b in (10, 13):
                if partial:
                    lines.append((now, bytes(partial).decode('ascii', 'replace')))
                    partial.clear()
            else:
                partial.append(b)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dev', default='/dev/ttyAMA0')
    p.add_argument('--baud', type=int, default=115200)
    p.add_argument('--mode', choices=['listen', 'appseq'], default='appseq')
    p.add_argument('--listen-secs', type=float, default=60.0)
    p.add_argument('--run-gap', type=float, default=3.47)  # app's S_RESET->S_RUN
    p.add_argument('--post-run', type=float, default=12.0)
    p.add_argument('--trials', type=int, default=1)
    a = p.parse_args()

    for trial in range(1, a.trials + 1):
        fd = open_raw(a.dev, a.baud)
        t0 = time.time()
        lines, partial = [], bytearray()
        print(f"=== TRIAL {trial}  mode={a.mode}  {time.strftime('%H:%M:%SZ', time.gmtime())} ===",
              flush=True)
        if a.mode == 'listen':
            print(f"-- passive listen {a.listen_secs:.0f}s on a fresh open, nothing sent")
            pump(fd, t0 + a.listen_secs, t0, lines, partial)
        else:
            os.write(fd, b'*\n'); os.write(fd, b'*\n')
            print(f"-- t=0.000  TX S_RESET '*' x2")
            pump(fd, t0 + a.run_gap, t0, lines, partial)
            trun = time.time() - t0
            os.write(fd, b'+\n')
            print(f"-- t={trun:.3f}  TX S_RUN '+'")
            pump(fd, time.time() + a.post_run, t0, lines, partial)
        if partial:
            lines.append((time.time() - t0, bytes(partial).decode('ascii', 'replace')))
        os.close(fd)

        base = trun if a.mode == 'appseq' else 0.0
        seen = {}
        for t, ln in lines:
            print(f"   {t:8.3f}  ({t-base:+8.3f} vs S_RUN)  {ln!r}")
            for m in ('H1S1', 'H1S3', 'H1S4', 'MH1'):
                if m in ln and m not in seen:
                    seen[m] = t - base
        got = [m for m in ('H1S1', 'H1S3', 'H1S4') if m in seen]
        print(f"-- VERDICT trial {trial}: {len(got)} of 3  announced={got} "
              f"latency={{{', '.join(f'{m}:{seen[m]:.3f}s' for m in got)}}} "
              f"lines={len(lines)}", flush=True)
        print()

main()
