#!/usr/bin/env python3
"""S97 gate 1: can a second process take DRM master on the D24's display card?

Opens /dev/dri/card0 and reports (a) whether the open itself made us master --
the kernel grants master on open only when the card has none -- and (b) what
DRM_IOCTL_SET_MASTER says when it does not.

No mode is set and no framebuffer is touched: this only asks who is allowed to
be master. Safe to run with the app up.
"""
import ctypes, fcntl, os, sys

DRM_IOCTL_SET_MASTER = 0x641e
DRM_IOCTL_DROP_MASTER = 0x641f
CARD = '/dev/dri/card0'


def masters():
    out = []
    with open('/sys/kernel/debug/dri/0/clients') as fh:
        for ln in fh.read().splitlines()[1:]:
            f = ln.split()
            if len(f) >= 5 and f[3] == 'y':
                out.append('%s/%s' % (f[0], f[1]))
    return out or ['none']


print('uid=%d  euid=%d' % (os.getuid(), os.geteuid()))
print('masters before open : %s' % ','.join(masters()))
fd = os.open(CARD, os.O_RDWR)
print('opened %s as fd %d' % (CARD, fd))
print('masters after  open : %s   (this pid is %d)' % (','.join(masters()), os.getpid()))
try:
    fcntl.ioctl(fd, DRM_IOCTL_SET_MASTER, 0)
    print('SET_MASTER: OK')
    print('masters after  set  : %s' % ','.join(masters()))
    fcntl.ioctl(fd, DRM_IOCTL_DROP_MASTER, 0)
    print('DROP_MASTER: OK (put back)')
except OSError as e:
    print('SET_MASTER: FAILED errno=%d %s' % (e.errno, os.strerror(e.errno)))
os.close(fd)
print('masters after  close: %s' % ','.join(masters()))
