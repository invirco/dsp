#!/usr/bin/env python3
"""gen_input_patch.py — the host input patch, generated from `defs/products/<p>/inputs.csv`.

Per CONTRACT-PROPOSAL-S58 §4. `defs/products/<p>/inputs.csv` (schema:
`defs/common/schema/inputs.md`) is the mic XLR <-> converter slot <-> console
strip declaration a product's DSP host input patch is generated from. This
reads it, resolves each row's `rx_cell` to its PACKED RX INDEX the same way
`tools/dsp/dsp_codegen.py::gen_block_io` assigns one -- INPUT_TDM nodes off
the shared `MW/D32/DSP/SHARC/dsp.csv`, sorted by `(sport_id, slot_start)`,
enumerated -- and emits `MW/<P>/DSP/input_patch.json`.

NO "8 * AD + slot" ASSUMPTION SURVIVES HERE. The old hand-typed
`D24_INPUT_PATCH` (and this generator's own first draft) could re-derive the
packed index from `sport_id`/`tdm_slot` arithmetic, but that only holds
because every INPUT_TDM node today has `slot_count=1`. The block_io sort is
the one true order; this module reads it off the graph rather than assuming
its shape.

A product with no `defs/products/<p>/inputs.csv` gets no file: D32/D16/D12
today have no netlist walk, so their host patch stays identity (the packed
RX index IS the slot var index), as it always has.

NO-FALLBACK POLICY: a row that fails any check below stops the generator.
This file is a consumer of `defs/`; it never repairs or silently drops a bad
row.

Usage:
    gen_input_patch.py --product d24                # write MW/D24/DSP/input_patch.json
    gen_input_patch.py --product d24 --check PATCH   # compare to a landed tuple (46 ints, comma-sep)
    gen_input_patch.py --all                         # every product with an inputs.csv
"""

import argparse
import csv
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFS_DIR = os.path.join(ROOT, 'defs')
DSP_CSV = os.path.join(ROOT, 'MW/D32/DSP/SHARC/dsp.csv')

INPUTS_COLUMNS = ['panel', 'xlr', 'preamp_595', 'chain_index', 'send_pos', 'adc',
                  'sport_id', 'ain', 'tdm_slot', 'rx_cell', 'strip']

PRODUCTS = ('d12', 'd16', 'd24', 'd32')


def _parse_params(s):
    out = {}
    for pair in (s or '').split(';'):
        pair = pair.strip()
        if '=' in pair:
            k, v = pair.split('=', 1)
            out[k] = v
    return out


def rx_index_map():
    """node id -> packed RX index: INPUT_TDM nodes off the shared dsp.csv,
    sorted (sport_id, slot_start) and enumerated -- the exact order
    dsp_codegen.py::gen_block_io assigns `rx_index` in."""
    with open(DSP_CSV, newline='', encoding='utf-8') as f:
        nodes = [row for row in csv.DictReader(f) if row.get('type') == 'INPUT_TDM']
    for n in nodes:
        p = _parse_params(n['params'])
        n['_sport_id'] = int(p.get('sport_id', '0'))
        n['_slot_start'] = int(p.get('slot_start', '0'))
    nodes.sort(key=lambda n: (n['_sport_id'], n['_slot_start']))
    return {n['id']: i for i, n in enumerate(nodes)}, {n['id']: n for n in nodes}


def _read_inputs_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        rows = [r for r in reader if r and not r[0].startswith('#')]
    header, body = rows[0], rows[1:]
    if header != INPUTS_COLUMNS:
        sys.exit(f'ERROR: {path}: column order is part of the contract; got {header}, '
                 f'want {INPUTS_COLUMNS}')
    return [dict(zip(header, r)) for r in body]


def _product_channels(product):
    path = os.path.join(DEFS_DIR, 'products', product, f'{product}.csv')
    with open(path, newline='', encoding='utf-8') as f:
        for row in csv.reader(f):
            if row and row[0] == 'ch':
                return int(row[1])
    sys.exit(f'ERROR: {path}: no ch row -- cannot bound strip range')


def build_patch(product):
    """(patch tuple, rows) for `product`, or (None, None) if it has no
    inputs.csv -- identity, as D32/D16/D12 have always been."""
    inputs_csv = os.path.join(DEFS_DIR, 'products', product, 'inputs.csv')
    if not os.path.isfile(inputs_csv):
        return None, None

    rx_of, node_by_id = rx_index_map()
    ch = _product_channels(product)
    rows = _read_inputs_csv(inputs_csv)

    patch = list(range(len(rx_of)))   # identity default
    seen_strip, seen_rx_cell, seen_xlr, seen_chain = {}, {}, {}, {}

    for r in rows:
        xlr = r['xlr']

        def fail(msg):
            sys.exit(f'ERROR: {inputs_csv}: {xlr}: {msg}')

        rx_cell = r['rx_cell']
        node = node_by_id.get(rx_cell)
        if node is None:
            fail(f"rx_cell '{rx_cell}' is not an INPUT_TDM node in {DSP_CSV}")

        sport_id, tdm_slot = int(r['sport_id']), int(r['tdm_slot'])
        if (node['_sport_id'], node['_slot_start']) != (sport_id, tdm_slot):
            fail(f"rx_cell '{rx_cell}' is (sport_id={node['_sport_id']}, "
                f"slot_start={node['_slot_start']}) in the graph, row says "
                f"(sport_id={sport_id}, tdm_slot={tdm_slot})")

        ain = int(r['ain'])
        if tdm_slot != ain - 1:
            fail(f'tdm_slot={tdm_slot} != ain-1={ain - 1}')

        chain_index, send_pos = int(r['chain_index']), int(r['send_pos'])
        if send_pos != 24 - chain_index:
            fail(f'send_pos={send_pos} != 24-chain_index={24 - chain_index}')

        strip = int(r['strip'])
        if not 1 <= strip <= ch:
            fail(f'strip={strip} outside 1..{ch}')

        for seen, key, label in ((seen_strip, strip, 'strip'),
                                 (seen_rx_cell, rx_cell, 'rx_cell'),
                                 (seen_xlr, xlr, 'xlr'),
                                 (seen_chain, chain_index, 'chain_index')):
            if key in seen:
                fail(f'duplicate {label}={key} (also row for {seen[key]})')
            seen[key] = xlr

        patch[rx_of[rx_cell]] = strip - 1

    # The result must be a permutation over the analog entries this
    # product's rows touch -- a row that maps two XLRs onto one packed RX
    # index (impossible given the rx_cell uniqueness check above, but the
    # patch is the artefact that matters) would silently steal a channel.
    touched = sorted(rx_of[r['rx_cell']] for r in rows)
    targets = sorted(patch[i] for i in touched)
    if targets != touched:
        sys.exit(f'ERROR: {inputs_csv}: the patch over the touched RX indices '
                 f'{touched} is not a permutation of itself: {targets}')

    return tuple(patch), rows


def write_patch(product):
    patch, rows = build_patch(product)
    out_path = os.path.join(ROOT, 'MW', product.upper(), 'DSP', 'input_patch.json')
    if patch is None:
        print(f'{product}: no defs/products/{product}/inputs.csv -- identity patch, no file written')
        return None
    contract = open(os.path.join(ROOT, 'defs.lock')).read()
    contract_version = next(l.split('=', 1)[1].strip() for l in contract.splitlines()
                            if l.startswith('CONTRACT_VERSION='))
    doc = {
        'contract': contract_version,
        'source': f'defs/products/{product}/inputs.csv',
        'patch': list(patch),
        'rows': rows,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=2)
        f.write('\n')
    print(f'{product}: wrote {out_path} ({len(patch)} entries, {len(rows)} rows)')
    return patch


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--product', choices=PRODUCTS)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--check', metavar='CSV_INTS',
                    help='compare the generated patch to a landed tuple (comma-separated ints)')
    args = ap.parse_args()

    if args.check:
        if not args.product:
            sys.exit('ERROR: --check needs --product')
        patch, _ = build_patch(args.product)
        want = tuple(int(x) for x in args.check.split(','))
        if patch != want:
            sys.exit(f'ERROR: generated patch != landed\n  generated: {patch}\n  landed:    {want}')
        print(f'{args.product}: generated patch matches landed, {len(want)} entries')
        return

    products = PRODUCTS if args.all else (args.product,) if args.product else None
    if not products:
        sys.exit('usage: gen_input_patch.py --product <p> | --all [--check CSV_INTS]')
    for p in products:
        write_patch(p)


if __name__ == '__main__':
    main()
