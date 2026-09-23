#!/usr/bin/env python3
"""S97 gate 1 witness: what is on the D24's CRTC, and who owns it.

Samples /sys/kernel/debug/dri/0/state (the vc4 display card) and
/sys/kernel/debug/dri/0/clients at ~20 Hz. It prints one line per CHANGE, so
the record is the transitions rather than thousands of identical rows -- and a
HEARTBEAT line every few seconds, so "nothing changed" is positively recorded
instead of being indistinguishable from "the witness died".

  scanout=<fb id>  the framebuffer the active plane is scanning out
  owner=<comm>     which process allocated it ("app" = matrix-app)
  master=<comm>    the DRM master, if any

A plane with crtc=(null) or fb=0 means NOTHING is being scanned out -- that is
a dark screen. A scanout fb whose owner has exited means the last frame is
still on the glass.
"""
import re, subprocess, sys, time

STATE = '/sys/kernel/debug/dri/0/state'
CLIENTS = '/sys/kernel/debug/dri/0/clients'


def read(p):
    try:
        with open(p) as fh:
            return fh.read()
    except Exception as e:
        return 'ERR %s' % e


def sample():
    st = read(STATE)
    scan = []
    for blk in re.split(r'\n(?=plane\[)', st):
        m = re.match(r'plane\[(\d+)\]: (\S+)', blk)
        if not m:
            continue
        crtc = re.search(r'\n\tcrtc=(\S+)', blk)
        fb = re.search(r'\n\tfb=(\d+)', blk)
        if not crtc or not fb:
            continue
        if crtc.group(1) == '(null)' or fb.group(1) == '0':
            continue
        own = re.search(r'allocated by = (\S+)', blk)
        size = re.search(r'\n\t\tsize=(\S+)', blk)
        scan.append('%s@%s fb=%s owner=%s size=%s' % (
            m.group(2), crtc.group(1), fb.group(1),
            own.group(1) if own else '?', size.group(1) if size else '?'))
    masters = []
    for ln in read(CLIENTS).splitlines()[1:]:
        f = ln.split()
        if len(f) >= 5 and f[3] == 'y':
            masters.append('%s/%s' % (f[0], f[1]))
    return ('DARK' if not scan else ' + '.join(scan)), ('none' if not masters else ','.join(masters))


def main():
    dur = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    beat = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    t0 = time.time()
    last = None
    nextbeat = 0.0
    changes = 0
    while True:
        el = time.time() - t0
        if el >= dur:
            break
        s = sample()
        tag = None
        if s != last:
            tag = 'change   '
            changes += 1
            last = s
            nextbeat = el + beat
        elif el >= nextbeat:
            tag = 'heartbeat'
            nextbeat = el + beat
        if tag:
            print('%7.3f  %s  scanout: %-62s master: %s'
                  % (el, tag, s[0], s[1]), flush=True)
        time.sleep(0.05)
    print('%7.3f  (end, %d changes)' % (time.time() - t0, changes), flush=True)


main()
