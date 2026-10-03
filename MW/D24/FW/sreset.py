#!/usr/bin/env python3
# Send S_RESET (*) on /dev/serial0 at 115200 8N1 — MH1 slave-hold before loadfw.
import os, time, termios, sys
fd = os.open("/dev/serial0", os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
a = termios.tcgetattr(fd)
a[0] = 0; a[1] = 0
a[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
a[3] = 0
a[4] = a[5] = termios.B115200
termios.tcsetattr(fd, termios.TCSANOW, a)
termios.tcflush(fd, termios.TCIFLUSH)
os.write(fd, b"*\n")
time.sleep(0.3)
os.close(fd)
print("S_RESET sent")
