#!/usr/bin/env python3
"""regime_verdict.py — was the graph actually on its expensive branch?

The verdict a driven capacity row stands or falls on, recomputed OFF the
part from the regime snapshots `dsp4_c2regime.py` writes, so every row in a
session is judged by one rule whatever version of the bench tool took it.

A dynamics envelope that reads zero means one of two things and they are
not the same:

  * the node RAN and its input was below threshold — the regime failed,
    and the capacity row beside it is a silence row wearing a driven
    label;
  * the node never ran, because the product's channel or aux mask skips
    it. On a D24 that is strips 25-32 (sixteen chip-1 envelopes) and aux
    9-12 (four chip-2 ones), and it is the product being a D24.

The masks are read from the snapshot's own `_chan_mask_live` /
`_aux_mask_live` — the words the graph gates on — and not from the
product name.

    python3 tools/dsp/regime_verdict.py MW/D32/DSP/SHARC/goldens/*regime*.json
"""
import argparse
import glob
import json
import os
import re
import sys

FAMS = ('_comp_envelope', '_gate_envelope', '_lim_envelope')
NODE_SUF = re.compile(r'_C\d_[A-Z0-9_]+$')
IDX = re.compile(r'_(\d+)$')


def masked(name, chan_mask, aux_mask):
    m = IDX.search(name)
    if not m:
        return False
    n = int(m.group(1))
    if '_AUX_' in name:
        return aux_mask is not None and not (aux_mask >> (n - 1)) & 1
    if re.search(r'_C1_(GATE|COMP)_\d+$', name):
        return chan_mask is not None and not (chan_mask >> (n - 1)) & 1
    return False


def verdict(path):
    d = json.load(open(path))
    w = d['words']
    chan = w.get('_chan_mask_live')
    aux = w.get('_aux_mask_live')
    live, dead, skip = [], [], []
    for k, v in sorted(w.items()):
        if NODE_SUF.sub('', k) not in FAMS:
            continue
        if v:
            live.append(k)
        elif masked(k, chan, aux):
            skip.append(k)
        else:
            dead.append(k)
    return {
        'file': os.path.basename(path), 'chip': d.get('chip'),
        'tag': d.get('tag'), 'live': len(live), 'dead': dead,
        'masked': len(skip),
        'chan_mask': chan, 'aux_mask': aux,
        'proven': not dead and bool(live),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='+')
    a = ap.parse_args()
    paths = []
    for p in a.paths:
        paths += sorted(glob.glob(p)) if any(c in p for c in '*?[') else [p]

    bad = 0
    for p in paths:
        try:
            v = verdict(p)
        except (OSError, ValueError, KeyError) as e:
            print('%-46s UNREADABLE (%s)' % (os.path.basename(p), e))
            bad += 1
            continue
        print('%-46s chip %s  %3d live  %2d masked  %s'
              % (v['file'], v['chip'], v['live'], v['masked'],
                 'PROVEN' if v['proven']
                 else 'NOT PROVEN: %d silent (%s%s)'
                      % (len(v['dead']), ', '.join(v['dead'][:4]),
                         ' …' if len(v['dead']) > 4 else '')))
        if not v['proven']:
            bad += 1
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
