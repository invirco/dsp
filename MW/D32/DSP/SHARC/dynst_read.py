"""Read the paired-dynamics self-test verdict off the part.

argv: <cclk_hz>   (the tick is 1 ms of CCLK whatever the target, so cycles
                   per tick is just cclk/1000)
Symbols come from chip1.sym.json, staged beside the images -- they move on
every build and hand-copied addresses go stale.
"""
import json, sys
# BLOCK comes from the GENERATED dsp4_block.py staged beside the images, so
# a verdict can never be scored against a block size the image was not
# built with. It used to be a literal 32 in two places here -- the diff
# count and the cycles-per-sample divisor -- and at BLOCK=8 that reported
# every paired figure four times too cheap.
from dsp4_block import BLOCK
CCLK = float(sys.argv[1]) if len(sys.argv) > 1 else 983040000.0
sys.argv = ['p']
import dsp4_diag as D
link = D.SpiLink('0.0', 1000000, 6, rdy_gpio=8)
diag = D.DiagLink(link); diag.resync()
sym = json.load(open('chip1.sym.json'))

def peek(a):
    # Only trust a value the link agrees with on two independent reads.
    last = None
    for _ in range(30):
        try:
            if diag.read(0xE000) != 0xD5B40001:
                continue
            v = diag.peek(a)
            if v == last:
                return v
            last = v
        except IOError:
            last = None
    return None

def sg(v):
    return None if v is None else (v - (1 << 32) if v & 0x80000000 else v)

def rd(name, off=0):
    return peek(sym[name] + off)

print('done      =', rd('_dst_done'))
print('iters     =', rd('_dst_iters'))
NCMP = 4 * BLOCK      # two blocks x two channels
print('--- bit-exactness: scalar vs paired, %d samples, 2 channels ---'
      % NCMP)
for tag, pfx in (('COMP', 'c'), ('GATE', 'g'), ('BQ4 ', 'b')):
    if ('_dst_%sndiff' % pfx) not in sym:
        continue
    n = rd('_dst_%sndiff' % pfx)
    m = rd('_dst_%smaxdiff' % pfx)
    f = sg(rd('_dst_%sfirst' % pfx))
    print('%s  ndiff=%s of %d   maxdiff=%s   first=%s'
          % (tag, n, NCMP, m, f))

print('--- timing: one %d-sample block, TWO channels, per iteration ---'
      % BLOCK)
nt = 18 if '_dst_bndiff' in sym else 10
t = [rd('_dst_tick', i) for i in range(nt)] + [None] * (18 - nt)
it = rd('_dst_iters')
names = [('COMP scalar', 0, 1), ('COMP paired', 2, 3),
         ('GATE scalar', 4, 5), ('GATE paired', 6, 7), ('null loop', 8, 9),
         ('BQ4 scalar', 10, 11), ('BQ4 paired', 12, 13),
         ('BQ2 scalar', 14, 15), ('BQ2 paired', 16, 17)]
res = {}
for nm, a, b in names:
    if t[a] is None or t[b] is None or it in (None, 0):
        print('%-12s unreadable' % nm); continue
    ticks = t[b] - t[a]
    cyc = ticks * CCLK / 1000.0
    per_samp = cyc / (it * BLOCK * 2)   # BLOCK samples x 2 channels
    res[nm] = (ticks, per_samp)
    print('%-12s %6d ticks  %8.1f cycles/sample/channel' % (nm, ticks, per_samp))
for a, b in (('COMP scalar', 'COMP paired'), ('GATE scalar', 'GATE paired'),
             ('BQ4 scalar', 'BQ4 paired'), ('BQ2 scalar', 'BQ2 paired')):
    if a in res and b in res and res[b][1] > 0:
        print('%s -> %s : %.2fx' % (a, b, res[a][1] / res[b][1]))
