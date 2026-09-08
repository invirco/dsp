#!/usr/bin/env python3
"""landed_map.py — read the LANDED DSP address map, `defs/products/<p>/dsp.csv`.

This is the only thing in this repo that turns a cell name into an SPI
address for a HOST tool. It reads the file the hub landed at the gate; it
never reads the DSP4 node graph, and it never computes an address from a
stride. `MW/D32/DSP/gen_dsp.py --check-proposal` is what keeps the graph
and the landed file in agreement, so a tool that reads this module is
reading the contract rather than a second opinion about it.

Two consumers, one file:

  * desk tools import `LandedMap` straight from the submodule;
  * bench tools cannot -- the Pi has no `defs` checkout -- so `--json`
    writes a flat {cell: [chip, page, addr, node, nodetype, access]} that
    gets staged next to the images. The JSON carries the source tag and
    the sha256 of the CSV it came from, and `LandedJson.check()` refuses
    a file whose pin does not match what the caller expects, so a bench
    run can never quietly score against last week's contract.

Usage:
    python3 tools/dsp/landed_map.py --product d24 --families
    python3 tools/dsp/landed_map.py --product d24 --json /tmp/landed-d24.json
    python3 tools/dsp/landed_map.py --product d24 --cell Chan001GateThr001
"""

import argparse
import csv
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFS = os.path.join(ROOT, 'defs')


def _lockpin():
    """The defs-v* tag defs.lock pins, or '' if the lock cannot be read."""
    path = os.path.join(ROOT, 'defs.lock')
    try:
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith('CONTRACT_VERSION'):
                    return line.split('=', 1)[1].strip()
    except OSError:
        pass
    return ''


class LandedMap:
    """`defs/products/<product>/dsp.csv`, indexed by cell name."""

    def __init__(self, product, path=None):
        self.product = product
        self.path = path or os.path.join(DEFS, 'products', product, 'dsp.csv')
        with open(self.path, 'rb') as fh:
            raw = fh.read()
        self.sha256 = hashlib.sha256(raw).hexdigest()
        text = raw.decode('utf-8')
        body = [ln for ln in text.splitlines() if not ln.startswith('#')]
        self.rows = list(csv.DictReader(body))
        self.by_cell = {r['_Cell']: r for r in self.rows}
        if len(self.by_cell) != len(self.rows):
            raise SystemExit('%s: duplicate cell names in the landed map'
                             % self.path)
        self.pin = _lockpin()

    # -- lookups ---------------------------------------------------------
    def row(self, cell):
        try:
            return self.by_cell[cell]
        except KeyError:
            raise KeyError('%s: no cell %r in the landed map for %s'
                           % (os.path.basename(self.path), cell, self.product))

    def addr(self, cell):
        """SPI word address, decimal. The landed DspAdd already carries the
        per-instance stride -- Chan002Gain001 is 144, not 0 -- so a caller
        must never add one of its own."""
        return int(self.row(cell)['DspAdd'])

    def chip(self, cell):
        return int(self.row(cell)['DspSpi'])

    def page(self, cell):
        return int(self.row(cell)['DspPage'])

    def node(self, cell):
        return self.row(cell)['Node']

    def nodetype(self, cell):
        return self.row(cell)['NodeType']

    def access(self, cell):
        return self.row(cell)['Access']

    def ramp(self, cell):
        r = self.row(cell)
        return (r['RampProfile'], r['RampMode'],
                r['RampUpMs'], r['RampDownMs'])

    # -- groupings -------------------------------------------------------
    def families(self):
        """{NodeType: cell count} over every addressed cell."""
        out = {}
        for r in self.rows:
            out[r['NodeType']] = out.get(r['NodeType'], 0) + 1
        return out

    def nodes_of(self, nodetype):
        seen = []
        for r in self.rows:
            if r['NodeType'] == nodetype and r['Node'] not in seen:
                seen.append(r['Node'])
        return seen

    def cells_of_node(self, node):
        return [r['_Cell'] for r in self.rows if r['Node'] == node]

    # -- staging ---------------------------------------------------------
    def as_json(self):
        return {
            'product': self.product,
            'pin': self.pin,
            'source': 'defs/products/%s/dsp.csv' % self.product,
            'sha256': self.sha256,
            'cells': {r['_Cell']: [int(r['DspSpi']), int(r['DspPage']),
                                   int(r['DspAdd']), r['Node'],
                                   r['NodeType'], r['Access']]
                      for r in self.rows},
        }

    def dump(self, path):
        with open(path, 'w') as fh:
            json.dump(self.as_json(), fh, separators=(',', ':'), sort_keys=True)
        return path


class LandedJson:
    """The staged form, for hosts with no `defs` checkout (the bench Pi)."""

    def __init__(self, path):
        with open(path) as fh:
            d = json.load(fh)
        self.product = d['product']
        self.pin = d.get('pin', '')
        self.sha256 = d.get('sha256', '')
        self.cells = d['cells']

    def check(self, product=None, sha256=None):
        if product and self.product != product:
            raise SystemExit('landed map is for %s, expected %s'
                             % (self.product, product))
        if sha256 and self.sha256 != sha256:
            raise SystemExit('landed map sha256 %s != expected %s — the '
                             'staged contract is not the one being scored'
                             % (self.sha256[:12], sha256[:12]))

    def has(self, cell):
        return cell in self.cells

    def addr(self, cell):
        return self._e(cell)[2]

    def chip(self, cell):
        return self._e(cell)[0]

    def page(self, cell):
        return self._e(cell)[1]

    def node(self, cell):
        return self._e(cell)[3]

    def nodetype(self, cell):
        return self._e(cell)[4]

    def access(self, cell):
        return self._e(cell)[5]

    def families(self):
        out = {}
        for e in self.cells.values():
            out[e[4]] = out.get(e[4], 0) + 1
        return out

    def cells_of_node(self, node):
        return sorted(c for c, e in self.cells.items() if e[3] == node)

    def nodes_of(self, nodetype):
        return sorted({e[3] for e in self.cells.values() if e[4] == nodetype})

    def _e(self, cell):
        try:
            return self.cells[cell]
        except KeyError:
            raise KeyError('no cell %r in the staged landed map (%s)'
                           % (cell, self.product))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--product', default='d24')
    ap.add_argument('--path', default=None)
    ap.add_argument('--json', default=None, help='write the staging JSON here')
    ap.add_argument('--families', action='store_true')
    ap.add_argument('--cell', default=None)
    ap.add_argument('--node', default=None)
    a = ap.parse_args()

    m = LandedMap(a.product, a.path)
    if a.json:
        m.dump(a.json)
        print('%s  %d cells  sha256 %s  pin %s'
              % (a.json, len(m.rows), m.sha256[:12], m.pin or '?'))
    if a.families:
        fam = m.families()
        print('%-14s %6s %6s' % ('family', 'cells', 'nodes'))
        for k in sorted(fam, key=lambda k: -fam[k]):
            print('%-14s %6d %6d' % (k, fam[k], len(m.nodes_of(k))))
        print('%-14s %6d %6d' % ('TOTAL', sum(fam.values()),
                                 len({r['Node'] for r in m.rows})))
    if a.cell:
        r = m.row(a.cell)
        print(json.dumps(r, indent=2))
    if a.node:
        for c in m.cells_of_node(a.node):
            print('%-32s 0x%04X  %s' % (c, m.addr(c), m.access(c)))
    if not (a.json or a.families or a.cell or a.node):
        print('%s: %d cells, %d families, sha256 %s'
              % (m.path, len(m.rows), len(m.families()), m.sha256[:12]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
