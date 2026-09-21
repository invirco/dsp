#!/usr/bin/env python3
"""s89_stamps.py <raw.s32> -- decode tx_probe stamps out of a maincap capture.

The _maincap LOGIC build latches B_O3 slot 0 into the Pi's LEFT channel and
slot 1 into the RIGHT, from ONE DSP frame, so a recorded stereo frame is a
coherent pair. tx_probe.asm writes slot 1 (driven, written by no node) with

    bits 31..8  block counter        bit 4  0 = ping, 1 = pong
    bits  3..0  sample index within the block

The stamp is in order BY CONSTRUCTION, so the capture decides it: monotonic
stamps mean the buffer->wire path is in order; displaced stamps give the
displacement directly in BLOCKS instead of inferring it from audio.
"""
import struct, sys, collections
raw = open(sys.argv[1], 'rb').read()
n = len(raw) // 8
fr = struct.unpack('<%di' % (n * 2), raw[:n * 8])
L = fr[0::2]; R = fr[1::2]
st = [w & 0xFFFFFFFF for w in R]
# find the region where stamps look live (block counter advancing)
def blk(w): return (w >> 8) & 0xFFFFFF
def idx(w): return w & 0xF
def half(w): return (w >> 4) & 1
live = [w for w in st if w != 0]
print('frames %d, non-zero stamps %d' % (n, len(live)))
if len(live) < 64:
    print('NOT ENOUGH STAMPS -- slot 1 is not reaching the capture'); sys.exit(2)
s = live[:20000]
# expected: idx runs 0..15, blk increments when idx wraps, half alternates per block
bad_seq = 0; bad_blk = 0; total = 0
disp = collections.Counter()
prev = None
for w in s:
    if prev is not None:
        pi, pb = idx(prev), blk(prev)
        ei = (pi + 1) & 0xF
        eb = pb + 1 if ei == 0 else pb
        total += 1
        if idx(w) != ei:
            bad_seq += 1
        if blk(w) != eb:
            bad_blk += 1
            disp[blk(w) - eb] += 1
    prev = w
print('transitions %d' % total)
print('  sample-index out of sequence : %d  (%.4f %%)' % (bad_seq, 100.0*bad_seq/max(total,1)))
print('  block counter not as expected: %d  (%.4f %%)' % (bad_blk, 100.0*bad_blk/max(total,1)))
if disp:
    print('  block displacement histogram (blocks early(-)/late(+)):')
    for d, c in sorted(disp.items(), key=lambda kv: -kv[1])[:8]:
        print('     %+4d blocks : %d' % (d, c))
print('  ping/pong per block: %s' % ('alternating' if len({half(w) for w in s[:32]}) == 2 else 'STUCK'))
# per-position error census: which sample index within the block goes wrong
pos = collections.Counter()
prev = None
for w in s:
    if prev is not None and blk(w) != (blk(prev) + 1 if idx(w) == 0 else blk(prev)):
        pos[idx(w)] += 1
    prev = w
if pos:
    print('  displaced frames by sample index within the block:')
    print('     ' + '  '.join('%d:%d' % (k, pos[k]) for k in sorted(pos)))
print('VERDICT: %s' % ('IN ORDER' if bad_seq == 0 and bad_blk == 0 else 'DISPLACED'))
