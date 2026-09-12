#!/usr/bin/env python3
"""s39_rxalign.py — is the RX word alignment wrong on EVERY lane?

Signature of a one-bit-late capture: the sample's sign bit lands in
bit 30 instead of bit 31 and a 0 is shifted in above it, so a small
NEGATIVE sample (0xFFFFxxxx) is received as 0x7FFFxxxx and a small
positive one is unchanged. The tell is that no received word ever falls
in the middle of the range: every word is either just under 0x80000000
or just over 0x00000000, the low bits are always clear, and the
"just under 0x80000000" population is about half.

A converter running normally on a quiet input gives words clustered
around 0x00000000 and 0xFFFFFFFF instead -- i.e. the TOP of the range is
populated, not the middle-high.

Per lane this prints: how many words land in each quarter of the range,
the count with the low 7 bits set, and the rms under both readings.
"""
import sys, time, math
_argv = list(sys.argv); sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR = _argv[1] if len(_argv) > 1 else '/home/app/s39'
N = int(_argv[2]) if len(_argv) > 2 else 24
sc = S.Scope(1, symfile='%s/chip1.sym.json' % SYMDIR); sc.d.resync(); sc.check_chip()

ents = sc.sym['_c1_rx_node_entry']; offs = sc.sym['_c1_rx_off']
strds = sc.sym['_c1_rx_stride']

def sgn(w):
    return w - (1 << 32) if w & 0x80000000 else w

print('lane  Q0(0..3FFF) Q1(4000..7FFF) Q2(8000..BFFF) Q3(C000..FFFF)  '
      'lo7set  rms as-is   rms <<1')
tot = [0, 0, 0, 0]
for strip in range(1, 13):
    try:
        e = sc.peek(ents + strip - 1)
        off = sc.peek(offs + e); strd = sc.peek(strds + e)
    except IOError:
        print(' %2d   table unreadable' % strip); continue
    w = []
    for i in range(N):
        try:
            b = sc.peek(sc.sym['_rx_active_buf'])
            w.append(sc.peek(b + off + (i % 16) * strd))
        except IOError:
            pass
    if not w:
        print(' %2d   lane unreadable' % strip); continue
    q = [0, 0, 0, 0]
    for x in w:
        q[(x >> 30) & 3] += 1
    for i in range(4):
        tot[i] += q[i]
    lo7 = sum(1 for x in w if x & 0x7F)
    a = math.sqrt(sum((sgn(x) / 2.0**31) ** 2 for x in w) / len(w))
    s1 = math.sqrt(sum((sgn((x << 1) & 0xFFFFFFFF) / 2.0**31) ** 2 for x in w) / len(w))
    print(' %2d      %3d          %3d            %3d            %3d        %2d   '
          '%.6f   %.6f' % (strip, q[0], q[1], q[2], q[3], lo7, a, s1))
print('\n total   %3d          %3d            %3d            %3d' % tuple(tot))
print('\n A correctly aligned quiet lane populates Q0 (small +) and Q3')
print(' (small -). A one-bit-late capture populates Q0 and Q1 and leaves')
print(' Q2/Q3 EMPTY, because the shifted-in zero clears bit 31.')
