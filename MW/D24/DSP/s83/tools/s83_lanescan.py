#!/usr/bin/env python3
"""s83_lanescan.py — WHERE DOES THE TONE LAND? Every chip-1 input lane, read
the same way, with the stimulus off and then on.

S82 left the AK5558 mic lanes reading exact digital zero on the fixed
bitstream while the codec return lanes moved in the same pass, and the hub
asked whether S58's input patch is reading the wrong lanes. The desk half of
that is answered and says NO -- the AD0-AD2 rows of `shared/dsp4-logic/
slot-map.csv` are byte-identical between the retired bitstream's commit and
HEAD, so `MIC 5 -> _buf_C1_IN_16` holds on both. This is the bench half, and
it assumes nothing about which lane is which: it drives ONE tone into the
loop and reads EVERY lane, so the tone names its own lane.

TWO CONTROLS, both of which must come out right or no per-lane verdict is
printed -- the same discipline dsp4_inscan.py carries:

  MUST MOVE     FRAME_COUNT advances, i.e. the block ISR is turning.
  MUST NOT MOVE `_rx_slot_C1_IN_01`, a symbol nothing writes under
                DSP4_BLOCK_KERNELS, reads constant. If a dead symbol varies
                the peek path is returning garbage and MOVING means nothing.

The interval is deliberately not a multiple of the 3000/s block rate
(S80: a 20 ms peek aliased a 2.5 ms drive to a false STATIC).

    python3 s83_lanescan.py --symdir . --tag off
    python3 s83_lanescan.py --symdir . --tag on --json lanes-on.json
"""
import argparse
import json
import math
import os
import sys
import time

_argv = list(sys.argv)                 # BEFORE the import: dsp4_scope parses argv
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_diag as D                                                # noqa: E402

FRAME_COUNT = 0xE004
MAGIC = 0xD5B40001
INTERVAL = 0.0137


def s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def dbfs(v):
    """Q4.28 word -> dBFS against 1.0 = 2^28."""
    a = abs(v) / float(1 << 28)
    return -336.0 if a <= 0 else 20.0 * math.log10(a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chip', type=int, default=1)
    ap.add_argument('--symdir', default='.')
    ap.add_argument('--reps', type=int, default=24)
    ap.add_argument('--tag', default='')
    ap.add_argument('--json', default=None)
    a = ap.parse_args(_argv[1:])

    sp = os.path.join(a.symdir, 'chip%d.sym.json' % a.chip)
    syms = json.load(open(sp))
    print('symbol map: %s  (%d symbols)' % (os.path.abspath(sp), len(syms)))

    link = D.SpiLink('0.0', 1000000, 6 if a.chip == 1 else 24,
                     rdy_gpio=8 if a.chip == 1 else 12)
    diag = D.DiagLink(link)
    diag.resync()

    def peek(addr, patience=25):
        """One MAGIC-bracketed peek. 0xFFFFFFFF inside good brackets is the
        LANE's value, not a dropped answer -- dsp4_inscan.py's rule."""
        bracketed_ff = False
        for _ in range(patience):
            try:
                if diag.read(0xE000) != MAGIC:
                    continue
                v = diag.peek(addr)
                if diag.read(0xE000) != MAGIC:
                    continue
                if v == 0xFFFFFFFF:
                    bracketed_ff = True
                    continue
                return v
            except IOError:
                continue
        return 0xFFFFFFFF if bracketed_ff else None

    def sample(addr, reps):
        out = []
        for _ in range(reps):
            v = peek(addr)
            if v is not None:
                out.append(s32(v))
            time.sleep(INTERVAL)
        return out

    pre = '_buf_C%d_' % a.chip
    names = sorted(k for k in syms
                   if k.startswith(pre) and ('_IN_' in k
                                             or k.startswith(pre + 'XIN')))
    if not names:
        raise SystemExit('s83_lanescan: no `%s*IN*` symbols in this map — '
                         'either it does not match the booted image or the '
                         'image has no block kernels. NOTHING SCANNED.' % pre)

    fc0 = diag.read(FRAME_COUNT)
    dead = '_rx_slot_C%d_IN_01' % a.chip
    dead_vals = sample(syms[dead], 4) if dead in syms else None

    rows = []
    for name in names:
        v = sample(int(syms[name]), a.reps)
        if not v:
            rows.append({'sym': name, 'lane': name[len(pre):], 'read': 0})
            continue
        rows.append({'sym': name, 'lane': name[len(pre):], 'read': len(v),
                     'distinct': len(set(v)), 'min': min(v), 'max': max(v),
                     'peak_dbfs': round(max(dbfs(min(v)), dbfs(max(v))), 3),
                     'words': ['%08x' % (w & 0xFFFFFFFF) for w in v[:6]]})
    fc1 = diag.read(FRAME_COUNT)

    moved = (fc1 - fc0) & 0xFFFFFFFF
    nd = len(set(dead_vals)) if dead_vals else None
    print('  control MUST MOVE      FRAME_COUNT +%d  [%s]'
          % (moved, 'ok' if moved else 'FAILED — the block loop is not turning'))
    print('  control MUST NOT MOVE  %s -> %s distinct  [%s]'
          % (dead, nd, 'ok' if nd == 1 else 'absent from this map'
             if nd is None else 'FAILED — the peek path is noisy'))
    if not moved:
        raise SystemExit('no per-lane verdict: the block loop is not turning')

    print()
    print('%-14s %8s %8s %13s %13s %11s  %s'
          % ('lane', 'read', 'distinct', 'min', 'max', 'peak dBFS', 'verdict'))
    for r in rows:
        if not r.get('read'):
            print('%-14s %8s' % (r['lane'], 'UNREAD'))
            continue
        print('%-14s %8d %8d %13d %13d %11.3f  %s'
              % (r['lane'], r['read'], r['distinct'], r['min'], r['max'],
                 r['peak_dbfs'],
                 'MOVING' if r['distinct'] > 1 else
                 'STATIC ZERO' if r['min'] == 0 else
                 'STATIC 0x%08X' % (r['min'] & 0xFFFFFFFF)))
    out = {'tag': a.tag, 'chip': a.chip, 'symdir': os.path.abspath(a.symdir),
           'frame_count_delta': moved, 'dead_symbol_distinct': nd,
           'lanes': rows}
    if a.json:
        json.dump(out, open(a.json, 'w'), indent=1)
        print('\nwrote %s' % a.json)


if __name__ == '__main__':
    main()
