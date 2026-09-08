#!/usr/bin/env python3
"""dsp4_fx_cost.py — FX_ENGINE's whole-graph cost, PAIRED on one boot.

The 2026-09-08 inert-families pass measured Type 3 on six engines at
+28,171 cycles/block AT BLOCK 8 and SCALED it to block 16 (~ +56,300,
chip 2 at ~ 93.6 %).  A projection from a measured per-sample cost is
still a projection, and chip-2 margin is the number PW's capacity-fit
decision rests on, so it gets measured at the operating point the fit
numbers were taken at.

WHAT MAKES THIS A MEASUREMENT RATHER THAN TWO NUMBERS. Both arms are
read on ONE boot of ONE image: the graph is profiled at the engines'
landed Type, then the six `FxNNNType001` cells are written over SPI and
the same register is read again, then they are written back and read a
third time. The third read is the CONTROL -- if the graph does not come
back to the first number the delta is not the algorithm's cost, it is
drift, and the run says so rather than publishing the difference.

The engines' Type is a LANDED CELL, so this drives the contract's own
address (resolved by name out of `defs/products/<p>/dsp.csv` through
landed_map.py) and not a symbol.

Run through fxcost.sh, which builds the block-16 tree, stages it, boots
and configures both chips.
"""

import argparse
import json
import sys
import time

sys.path.insert(0, '/home/app/dspboot')

from dsp4_conform import Part, SPI_ERR_COUNT

PROC_CYC = '_proc_cyc'
PROC_PASSES = '_proc_passes'

FX_NODES = ['C2_FX_ENG_%02d' % i for i in range(1, 7)]
FX_TYPE_CELLS = ['Fx%03dType001' % i for i in range(1, 7)]


class Landed:
    def __init__(self, path):
        with open(path) as fh:
            d = json.load(fh)
        self.product = d['product']
        self.pin = d.get('pin', '')
        self.sha256 = d.get('sha256', '')
        self.cells = d['cells']

    def has(self, cell):
        return cell in self.cells

    def addr(self, cell):
        return self.cells[cell][2]


def peekn(part, name, n):
    if name not in part.sc.sym:
        return None
    base = part.sc.sym[name]
    out = []
    for k in range(n):
        try:
            out.append(part.sc.peek(base + k))
        except IOError:
            out.append(None)
    return out


def proc_cycles(part, dwell=6.0, reps=3):
    """Whole-graph cycles per block, MINIMUM over `reps` reads.

    _proc_cyc is the block loop's own TCOUNT delta, republished every
    pass; one read is one block, and a block can be long for reasons
    that are nothing to do with the graph (an SPI burst being serviced,
    the diag link answering). Minimum over spaced reads is the steady
    cost. Same helper, same rule, as dsp4_inert_diag.py.
    """
    if PROC_CYC not in part.sc.sym:
        return None, None
    best, passes = None, None
    for _ in range(reps):
        time.sleep(dwell / reps)
        try:
            c = part.sc.peek(part.sc.sym[PROC_CYC])
            p = part.sc.peek(part.sc.sym[PROC_PASSES])
        except IOError:
            continue
        if not c or not p:
            continue
        if best is None or c < best:
            best = c
        passes = p
    return best, passes


def witness(part):
    """The stimulus is REACHING the FX chain, or the arms mean nothing.

    A silent FX bus costs the same at every Type for the trivial reason
    that there is nothing in it -- and the family walk already read the
    FX chain at peak zero once. The recv node's published BLOCK is the
    input to every engine, so that is what gets read, sample 0 against
    sample 1: the profile stimulus is a square, so the alternation is
    the witness a stuck or bypassed path cannot fake.
    """
    for tag in ('_blk_C2_RECV_FX_01', '_buf_C2_RECV_FX_01'):
        if tag not in part.sc.sym:
            continue
        base = part.sc.sym[tag]
        try:
            v0 = part.sc.peek(base)
            v1 = part.sc.peek(base + 1) if tag.startswith('_blk') else None
        except IOError:
            continue
        if v1 is not None:
            if v0 and v1 == ((-v0) & 0xFFFFFFFF):
                return True, '%s=0x%08X/0x%08X' % (tag, v0, v1)
            return False, '%s=0x%08X/0x%08X (not alternating)' % (
                tag, v0, v1 or 0)
        return bool(v0), '%s=0x%08X' % (tag, v0)
    return False, 'no FX recv symbol in the map'


def set_type(part, L, value):
    wrote = []
    for cell in FX_TYPE_CELLS:
        if L.has(cell):
            part.write(L.addr(cell), value, 0)
            wrote.append(cell)
    time.sleep(0.5)
    return wrote


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--landed', default='landed-d24.json')
    ap.add_argument('--type', type=int, default=3,
                    help='FX algorithm for the loaded arm')
    ap.add_argument('--budget', type=int, default=327680,
                    help='cycles per block at the built block size')
    ap.add_argument('--dwell', type=float, default=6.0)
    ap.add_argument('--json', default='')
    args = ap.parse_args()

    L = Landed(args.landed)
    part = Part(2)
    part.sc.check_chip()

    out = {'contract': {'pin': L.pin, 'sha256': L.sha256,
                        'product': L.product},
           'budget': args.budget, 'type': args.type}

    ok, note = witness(part)
    out['witness'] = note
    out['witness_ok'] = ok
    print('witness: %s  %s' % ('LIVE' if ok else 'SILENT', note))

    e0 = part.read(SPI_ERR_COUNT)

    t_landed = peekn(part, '_fx_type_%s' % FX_NODES[0], 1)
    out['type_landed'] = t_landed
    c_a, p_a = proc_cycles(part, args.dwell)
    out['arm_default'] = {'cycles': c_a, 'passes': p_a,
                          'fx_type': t_landed[0] if t_landed else None}
    print('arm A  engines at the landed default (Type %s)   %s cycles/block'
          % (t_landed[0] if t_landed else '?', c_a))

    wrote = set_type(part, L, args.type)
    rb = [peekn(part, '_fx_type_%s' % n, 1)[0] for n in FX_NODES]
    out['forced_cells'] = wrote
    out['type_readback'] = rb
    if any(v != args.type for v in rb):
        print('  TYPE DID NOT LAND on every engine: %r' % rb)
    c_b, p_b = proc_cycles(part, args.dwell)
    out['arm_loaded'] = {'cycles': c_b, 'passes': p_b, 'fx_type': rb}
    print('arm B  Type %d on %d engines                      %s cycles/block'
          % (args.type, len(wrote), c_b))

    set_type(part, L, 0)
    rb0 = [peekn(part, '_fx_type_%s' % n, 1)[0] for n in FX_NODES]
    c_c, p_c = proc_cycles(part, args.dwell)
    out['arm_restored'] = {'cycles': c_c, 'passes': p_c, 'fx_type': rb0}
    print('arm C  restored to Type 0 (the CONTROL)          %s cycles/block'
          % c_c)

    e1 = part.read(SPI_ERR_COUNT)
    out['spi_err'] = [e0, e1]

    if c_a and c_b and c_c:
        d = c_b - c_a
        drift = c_c - c_a
        out['delta'] = d
        out['drift'] = drift
        out['pct_default'] = 100.0 * c_a / args.budget
        out['pct_loaded'] = 100.0 * c_b / args.budget
        print('')
        print('delta  Type %d - default                        %+d cycles/block'
              % (args.type, d))
        print('drift  control - default                        %+d cycles/block'
              % drift)
        print('budget %d cycles/block: default %.2f %%  loaded %.2f %%  '
              'margin %.2f %%'
              % (args.budget, out['pct_default'], out['pct_loaded'],
                 100.0 - out['pct_loaded']))
        if abs(drift) > abs(d) * 0.1:
            print('DRIFT IS NOT SMALL AGAINST THE DELTA — this pair is not '
                  'a measurement')

    if args.json:
        with open(args.json, 'w') as fh:
            json.dump(out, fh, indent=1)
        print('wrote %s' % args.json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
