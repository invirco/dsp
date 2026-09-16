"""s52_lanes.py [lanes...] — read chip-1 lanes (RMS/peak dBFS, 32 peeks) + the RX entry feeding each."""
import sys
A = sys.argv[1:]
import s52lib as X
c1 = X.Chip(1)
ls = [int(a) for a in A] or list(range(1, 25))
for n in ls:
    e, r, p = X.lane(c1, n)
    print('lane %2d  <- rx entry %2d  rms %8.2f  peak %8.2f dBFS' % (n, e, r, p))
