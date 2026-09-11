#!/usr/bin/env python3
"""dsp4_s32_flip.py — THE AUX_INPUT BYPASS, FLIPPED ON THE PART (S32 gate 4).

DSP4_AUXIN_BYPASS stops the chain CALLING a chip-2 AUX_INPUT whose `on`
cell is 0.  That is a state machine, and a state machine in the audio path
has to be shown to come back: the question this tool answers is whether a
node the chain has been skipping for minutes is correct again on the block
its cell flips, and whether one that stops being called leaves silence
behind it rather than the last block it happened to publish.

WHAT IS READ, per node, at every step:

  `_auxin_on_<nid>`    the cell the host wrote (and the gate's first test)
  `_auxin_byp_<nid>`   the park's flag -- 1 = "my block is silence, skip me"
                       (ABSENT in an image built without the bypass, which
                       is how this tool identifies the arm it is on)
  `_auxin_q_<nid>`     the Q4.28 coefficient, `on` already folded in:
                       0x10000000 at unity, 0x00000000 while off
  `_blk_<nid>[0..B-1]` the block the main mix bus reads

THE SNAKE INPUTS HAVE NO SIGNAL ON THIS BENCH and the tool says so rather
than scoring silence as a pass: A_I5 is the D32 snake lane, the rev C unit
is a D24 (`strap_d32` low, `i_dspa[5]` tied to 0), so `C2_XR_SNAKE_nn` is
zero whatever the CPLD carries.  For the snake nodes this is a STATE
witness -- the gate engages, disengages, and the block is clean -- and the
AUDIO witness is taken on `C2_PI_IN`, which is the same class, the same
generated body and the same gate, with the CM4's playback live in front of
it (S29 gate 4 proved that path stage by stage).

Usage:
  dsp4_s32_flip.py --landed landed-d32.json
  dsp4_s32_flip.py --landed landed-d32.json --nodes C2_PI_IN,C2_SNK_IN_01
"""
import argparse
import json
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

BLOCK = 16
DEFAULT = ['C2_PI_IN', 'C2_SNK_IN_01', 'C2_SNK_IN_02',
           'C2_SNK_IN_03', 'C2_SNK_IN_04']
# The node each one reads.  dsp.csv `inputs`, first channel.
SRC = {
    'C2_PI_IN': 'C2_XR_PI_L',
    'C2_CODEC_AUX_IN': 'C2_XR_CODEC_AUX_L',
    'C2_USB_IN': None,
    'C2_BT_IN': None,
}
for _i in range(1, 9):
    SRC['C2_SNK_IN_%02d' % _i] = 'C2_XR_SNAKE_%02d' % _i


def blk(sc, sym, n=BLOCK):
    if sym not in sc.sym:
        return None
    base = sc.sym[sym]
    return [sc.peek(base + k) for k in range(n)]


def word(sc, sym):
    return sc.peek(sc.sym[sym]) if sym in sc.sym else None


def fmt(vals):
    if vals is None:
        return 'ABSENT'
    if all(v == 0 for v in vals):
        return 'ALL ZERO'
    uniq = len(set(vals))
    return '%d distinct, e.g. %s' % (
        uniq, ' '.join('0x%08x' % v for v in vals[:3]))


def state(sc, nid):
    return {
        'on': word(sc, '_auxin_on_%s' % nid),
        'byp': word(sc, '_auxin_byp_%s' % nid),
        'q': word(sc, '_auxin_q_%s' % nid),
        'lvl': word(sc, '_auxin_level_%s' % nid),
        'blk': blk(sc, '_blk_%s' % nid),
        'src': blk(sc, '_blk_%s' % SRC[nid]) if SRC.get(nid) else None,
    }


def show(tag, st):
    print('    %-14s on=%s byp=%s q=%s' % (
        tag,
        'None' if st['on'] is None else '0x%08x' % st['on'],
        'ABSENT' if st['byp'] is None else st['byp'],
        'None' if st['q'] is None else '0x%08x' % st['q']))
    print('    %-14s blk %s' % ('', fmt(st['blk'])))
    if st['src'] is not None:
        print('    %-14s src %s' % ('', fmt(st['src'])))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--landed', default='landed-d32.json')
    ap.add_argument('--nodes', default=','.join(DEFAULT))
    ap.add_argument('--settle', type=float, default=0.4,
                    help='seconds between the write and the read-back')
    ap.add_argument('--json')
    a = ap.parse_args()

    cells = json.load(open(a.landed))['cells']
    on_cell = {}
    for name, v in cells.items():
        if v[4] == 'AUX_INPUT' and name.endswith('On001'):
            on_cell[v[3]] = (name, v[2])

    sc = S.Scope(2)
    sc.d.resync()
    sc.check_chip()
    armed = any(k.startswith('_auxin_byp_') for k in sc.sym)
    print('  image: %s' % ('DSP4_AUXIN_BYPASS=1 (_auxin_byp_ symbols present)'
                           if armed else
                           'no bypass in this image (_auxin_byp_ ABSENT)'))

    out, fails = {}, 0
    for nid in a.nodes.split(','):
        nid = nid.strip()
        if nid not in on_cell:
            print('  %s: no On cell in the landed map -- skipped' % nid)
            continue
        cell, addr = on_cell[nid]
        print('  %s  (%s at 0x%04X)' % (nid, cell, addr))
        rec = {}
        rec['off0'] = state(sc, nid); show('off (start)', rec['off0'])
        sc.wr(addr, 1); time.sleep(a.settle)
        rec['on'] = state(sc, nid); show('ON', rec['on'])
        sc.wr(addr, 0); time.sleep(a.settle)
        rec['off1'] = state(sc, nid); show('off (again)', rec['off1'])

        v = []
        if armed:
            v.append(('byp set while off', rec['off0']['byp'] == 1
                      and rec['off1']['byp'] == 1))
            v.append(('byp cleared when on', rec['on']['byp'] == 0))
        v.append(('q zero while off', rec['off0']['q'] == 0
                  and rec['off1']['q'] == 0))
        v.append(('q unity when on', rec['on']['q'] == 0x10000000))
        v.append(('block silent while off',
                  all(x == 0 for x in rec['off0']['blk'])
                  and all(x == 0 for x in rec['off1']['blk'])))
        if rec['on']['src'] is not None and any(rec['on']['src']):
            v.append(('block carries audio when on',
                      any(x != 0 for x in rec['on']['blk'])))
        else:
            print('    (no signal at this node\'s input on this bench -- '
                  'STATE witness only)')
        for what, ok in v:
            print('      %-28s %s' % (what, 'PASS' if ok else 'FAIL'))
            if not ok:
                fails += 1
        rec['verdict'] = {w: bool(o) for w, o in v}
        out[nid] = rec

    if a.json:
        json.dump({'armed': armed, 'nodes': out}, open(a.json, 'w'), indent=1)
    print('  %d check(s) FAILED' % fails if fails else '  all checks PASS')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
