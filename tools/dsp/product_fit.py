#!/usr/bin/env python3
"""product_fit.py — does a product of the range fit the silicon, BY
CONSTRUCTION, and what does the part have to be asked to prove it?

S28 gate 1. Seven sessions priced D24 and D32 driven to the tenth of a
point; the range has more products in the master than two, and the
scoreboard's "does it fit" table had two rows. This is the third input to
that table and it is a script, not a judgement:

  1. THE CELL COUNT comes from the product's own definition — the
     `defs` mx-master expanded by `defs/tools/expand_matrix.py` into
     `MW/<P>/MX/_matrix.csv` (sync-defs.sh), intersected with the ONE
     superset graph by `MW/D32/DSP/gen_dsp.py --propose`. Nothing here
     counts cells a second way.

  2. THE NODE CENSUS comes from the superset graph and the product's
     CONFIG WORDS. There is one firmware (decision D3) and exactly
     THREE words select a product inside it: `CFG_PRODUCT_ID` (the
     product-SCOPE gate), `CFG_CHAN_MASK` and `CFG_AUX_MASK`. So "the
     D16 graph" is not a different graph — it is the same 698 nodes
     with a different set of them gated off, and this file resolves the
     gates with the SAME rules the generator emits them with
     (`dsp_codegen.STRIP_NODE_RE`, `STRIP_MTR_RE`, `aux_owner`, and the
     `scope=` param the chain's scope runs are built from) rather than
     a second opinion about which node belongs to which strip.

  3. THE CAPACITY PREDICTION is a two-point interpolation of measured
     DRIVEN rows. D24 and D32 were measured on ONE image, one boot pair,
     four regimes each (S27 §2.1/§2.2, `shipping.config.s26`); they
     differ in exactly the two words above; so each regime's row gives a
     per-strip slope for chip 1 and a per-aux slope for chip 2, and a
     product's prediction is its own (ch, aux) on that line.

WHAT THE PREDICTION CANNOT SEE, stated here because a table that hides
it is worse than no table. The config words gate STRIPS, AUX BUSES and
the two SCOPE classes, and nothing else. A D12 defines two groups, four
FX engines, no matrix and no centre cluster; the firmware runs four
groups, six FX engines and four matrix buses whatever is booted,
because no word says otherwise.
Those nodes are on their cheap branch — nothing feeds them, the
product's cells do not exist to open them — but they are CALLED, and the
difference between "called on the cheap branch" and "not called" is
exactly what the chan/aux masks were worth when they got readers
(2026-09-09: 18.08 % of chip 1's budget). So the construction below is
an interpolation between two measured products and NOT a claim that a
D12's unused groups are free. `--census` prints what each product pays
for and does not define; gate 2 measures the difference.

Usage:
    python3 tools/dsp/product_fit.py                    # the fit table
    python3 tools/dsp/product_fit.py --census           # + the node census
    python3 tools/dsp/product_fit.py --csv MW/D32/DSP/fit-table.csv
    python3 tools/dsp/product_fit.py --measured f.json  # score gate 2
"""

import argparse
import csv
import json
import os
import re
import sys
import textwrap

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, SCRIPT_DIR)

from dsp_codegen import (STRIP_NODE_RE, STRIP_MTR_RE, aux_owner,   # noqa: E402
                         BLOCK, SAMPLE_RATE_HZ)

GRAPH_CSV = os.path.join(REPO_ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'dsp.csv')
PROPOSAL_ROOT = os.path.join(REPO_ROOT, 'proposals', 'defs', 'products')
DEFS_PRODUCTS = os.path.join(REPO_ROOT, 'defs', 'products')

# The products with a matrix expanded into this tree, smallest first. Keep
# in step with PRODUCTS in sync-defs.sh.
PRODUCTS = ('d12', 'd16', 'd24', 'd32')

# THE PRODUCTS THAT ARE NOT IN THE TABLE, AND WHY. A fit table that quietly
# lists four of the range's nine product folders is a table that looks
# complete and is not, so the other five are named here with the reason
# each is absent. Two different reasons, and only one of them is this
# repo's to fix.
EXCLUDED = {
    'd32rack': ('no definition yet — `defs/products/d32rack/` carries only an '
                'intake report, whose first line is "no generated master cell '
                'list — run the def pipeline first". There is no d32rack.csv '
                'and no gen/matrix/d32rack-mx-master.csv, so there is no cell '
                'count to generate and no fit to predict. HUB ITEM.'),
    'd32c':    ('no definition yet — same as d32rack: intake report only, '
                '"no generated master cell list". HUB ITEM.'),
    'd32r':    ('no definition yet — same as d32rack: intake report only, '
                '"no generated master cell list". HUB ITEM.'),
    'd64':     ('above the platform line. 64 channels and 16 aux: decision D6 '
                'puts the SHARC DSP4 card at up to 32 ch @ 48 kHz and '
                'everything above it on the single-chip FPGA engine. The '
                'graph could not carry it either — NUM_CH is 32 and '
                'CFG_CHAN_MASK is one 32-bit word — so this is not a number '
                'this firmware has.'),
    'd128':    ('above the platform line, as d64: 128 channels, 32 aux, LCR '
                'main. FPGA engine (see fpga/), not DSP4.'),
}

# CFG_PRODUCT_ID is a SCOPE CLASS, not a product identity, and S28 is where
# that stops being a distinction without a difference. The graph carries
# exactly two scopes -- `D32` (the eight snake returns and their transfers,
# 32 nodes) and `D24` (`C2_MON_OUT` and `C2_CODEC_AUX_OUT`) -- and
# `_scope_gates_apply` keeps the run whose id EQUALS the booted one.
#
# D16 and D12 define `mon,1` and no snake, so the scope class they want is
# the one id 1 selects: monitor out kept, snake gated off. They therefore
# boot PRODUCT_ID 1 as well, and the part cannot tell a D16 from a D24 by
# that word alone -- it tells them apart by CHAN_MASK/AUX_MASK, which it
# reads back live. That conflation is S28-4 and it is what the CFG2
# widening of gate 3 gives the bits to fix.
SCOPE_ID = {'d32': 0, 'd24': 1, 'd16': 1, 'd12': 1}
SCOPE_NAME = {0: 'D32', 1: 'D24'}

# ---------------------------------------------------------------------------
# The measured anchors
# ---------------------------------------------------------------------------
# S27 §2.1/§2.2, `MW/D32/DSP/dsp4-s27-20260910.md`. ONE image
# (`shipping.config.s26`, chip1 `6396187c` / chip2 `9222c2ee`, staged as
# `s26_*`), `DSP_LANDED_DIR=proposals/defs/products`, `driveall` LOGIC with
# the CM4 playing, block 16, 983.04 MHz measured every row, REPS=2 and the
# mean of the two boots quoted. The regime was PROVED on every driven row:
# 64/64 chip-1 dynamics envelopes live, 32/32 chip-2 (28/28 at D24), 6/6
# engines at Type 3 with 6/6 comb lines carrying signal.
#
# Each entry is (chip-1 avg %, chip-2 avg %). `worst` carries the
# S21-6-corrected worst block of the same rows.
MEASURED = {
    # row key: {product: (chip1_avg, chip2_avg)}
    'A_silent_default': {'d24': (50.72, 63.02), 'd32': (65.38, 76.09)},
    'B_silent_load':    {'d24': (59.97, 84.64), 'd32': (79.07, 100.88)},
    'D_driven_fxoff':   {'d24': (59.91, 64.38), 'd32': (79.02, 80.67)},
    'C_driven_load':    {'d24': (59.82, 84.37), 'd32': (79.16, 100.81)},
}
MEASURED_WORST = {
    'A_silent_default': {'d24': (50.97, 63.37), 'd32': (65.46, 76.38)},
    'B_silent_load':    {'d24': (60.12, 84.81), 'd32': (79.26, 101.14)},
    'D_driven_fxoff':   {'d24': (60.27, 64.61), 'd32': (79.78, 81.00)},
    'C_driven_load':    {'d24': (60.18, 84.73), 'd32': (79.50, 101.14)},
}
ROW_LABEL = {
    'A_silent_default': 'silent, the config the product boots with',
    'B_silent_load':    'silent, every assign/send open, dynamics at -60 dB',
    'D_driven_fxoff':   'driven, the FX engines OFF  (plain)',
    'C_driven_load':    'driven, every FX engine live at Type 3  (the load)',
}
ROW_ORDER = ('A_silent_default', 'B_silent_load',
             'D_driven_fxoff', 'C_driven_load')

# The two products the anchors were measured on, low then high.
ANCHOR_LO, ANCHOR_HI = 'd24', 'd32'

# The measured code pool and DM, S26/S27. ONE firmware: these are the same
# bytes on every product in the range, because every product boots the same
# image. Recorded here so the fit table can say so with a number.
CODE_POOL_BYTES = 262144
CODE_USED_C1 = 181350          # `shipping.config.s26`, S27 §1.1 mask 15
DM_NOTE = ('chip 2 code and both chips\' DM are identical across the range '
           'by construction: one image, selected by two config words')


def budget_cycles(cclk_hz=983.04e6):
    """Cycles per block at the shipped operating point."""
    return cclk_hz / (SAMPLE_RATE_HZ / BLOCK)


# ---------------------------------------------------------------------------
# The definitions
# ---------------------------------------------------------------------------
def product_def(product):
    """`defs/products/<p>/<p>.csv` as a dict. The definition, not a guess."""
    path = os.path.join(DEFS_PRODUCTS, product, f'{product}.csv')
    if not os.path.isfile(path):
        raise SystemExit(f'product_fit: {path} is missing — this product has '
                         f'no definition in the defs submodule, so it has no '
                         f'cell count and no fit. (No fallback.)')
    out = {}
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('key,'):
            continue
        k, _, v = line.partition(',')
        out[k] = v
    return out


def matrix_cells(product):
    path = os.path.join(REPO_ROOT, 'MW', product.upper(), 'MX', '_matrix.csv')
    if not os.path.isfile(path):
        raise SystemExit(f'product_fit: {path} is missing — run ./sync-defs.sh')
    with open(path, newline='', encoding='utf-8') as f:
        return [r['_Cell'] for r in csv.DictReader(f) if r.get('_Cell')]


def proposal_rows(product, name='dsp.csv'):
    path = os.path.join(PROPOSAL_ROOT, product, name)
    if not os.path.isfile(path):
        raise SystemExit(
            f'product_fit: {path} is missing — run\n'
            f'  DSP_LANDED_DIR=proposals/defs/products python3 '
            f'MW/D32/DSP/gen_dsp.py --force --propose')
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(l for l in f if not l.startswith('#')))


# ---------------------------------------------------------------------------
# The graph, and what each product's config words gate off it
# ---------------------------------------------------------------------------
def graph_nodes():
    with open(GRAPH_CSV, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(l for l in f if not l.startswith('#')))


def scope_of(node):
    """The scope class a node is gated by, or None. Same `scope=` param the
    chain emitter's scope runs are built from."""
    for kv in node['params'].split(';'):
        k, _, v = kv.partition('=')
        if k == 'scope':
            return v
    return None


def mask_owner(node):
    """('chan', n) | ('aux', n) | None — the SAME rule the generator's chain
    emitter uses to decide which gate a node sits behind."""
    nid = node['id']
    m = STRIP_NODE_RE.match(nid) or STRIP_MTR_RE.match(nid)
    if m:
        return ('chan', int(m.group(m.lastindex)))
    label = 'chip1' if node['chip'] == '1' else 'chip2'
    a = aux_owner(label, nid)
    if a is not None:
        return ('aux', a)
    return None


def census(nodes, nch, naux, scope_id):
    """Per (chip, type): how many nodes the image carries, how many this
    product's three config words leave RUNNING, and how many they gate off."""
    out = {}
    for n in nodes:
        key = (n['chip'], n['type'])
        rec = out.setdefault(key, {'total': 0, 'run': 0, 'gated_off': 0,
                                   'gateable': 0, 'scoped_off': 0})
        rec['total'] += 1
        sc = scope_of(n)
        if sc is not None:
            rec['gateable'] += 1
            if sc == SCOPE_NAME.get(scope_id):
                rec['run'] += 1
            else:
                rec['gated_off'] += 1
                rec['scoped_off'] += 1
            continue
        own = mask_owner(n)
        if own is None:
            rec['run'] += 1
            continue
        rec['gateable'] += 1
        limit = nch if own[0] == 'chan' else naux
        if own[1] <= limit:
            rec['run'] += 1
        else:
            rec['gated_off'] += 1
    return out


# ---------------------------------------------------------------------------
# The construction
# ---------------------------------------------------------------------------
def line(lo_x, lo_y, hi_x, hi_y):
    """slope, intercept through two measured points."""
    if hi_x == lo_x:
        raise SystemExit('product_fit: the two anchors have the same size — '
                         'there is no line through them.')
    slope = (hi_y - lo_y) / (hi_x - lo_x)
    return slope, lo_y - slope * lo_x


# Rows whose chip-2 figure includes the PLUGIN LOAD — every FX engine the
# product defines, live at Type 3. Both anchors define six, so a product
# that defines four is two engines lighter on these rows and on no other.
FX_LOADED_ROWS = ('B_silent_load', 'C_driven_load')
FX_ANCHOR_ENGINES = 6


def fx_slope(table):
    """Points of chip 2 per live reverb engine, from the anchors alone.

    The loaded row minus the FX-off row, over the six engines both anchors
    carry. It is a per-ENGINE figure and the product defs name an engine
    count, so it belongs in the construction -- and it was NOT in the first
    cut of this table (S28-3), which predicted every product's loaded rows
    as if it had six.
    """
    vals = []
    for p in (ANCHOR_LO, ANCHOR_HI):
        c = table['C_driven_load'][p][1]
        d = table['D_driven_fxoff'][p][1]
        vals.append((c - d) / FX_ANCHOR_ENGINES)
    return sum(vals) / len(vals)


def predict(sizes, table):
    """{row: {product: (chip1, chip2)}} by interpolation on the anchors.

    chip 1 is taken as a function of the CHANNEL count and chip 2 of the
    AUX count: chip 1 carries the 32 channel strips and chip 2 carries the
    twelve aux chains, and those are the two things the config words move.
    The two anchors move both together, so the split between them is an
    ATTRIBUTION, not a measurement -- see "what the prediction cannot see".

    Chip 2's LOADED rows get a third term: the product's own FX engine
    count against the six both anchors carry, at the per-engine slope the
    anchors themselves give. Chip 1 gets no such term because the FX load
    costs chip 1 nothing -- the anchors put C minus D at -0.09 and +0.14
    points, which is the instrument's own resolution.
    """
    kfx = fx_slope(table)
    out = {}
    for row, per_product in table.items():
        lo, hi = per_product[ANCHOR_LO], per_product[ANCHOR_HI]
        k1, b1 = line(sizes[ANCHOR_LO]['ch'], lo[0],
                      sizes[ANCHOR_HI]['ch'], hi[0])
        k2, b2 = line(sizes[ANCHOR_LO]['aux'], lo[1],
                      sizes[ANCHOR_HI]['aux'], hi[1])
        loaded = row in FX_LOADED_ROWS
        out[row] = {'slope': (k1, k2), 'intercept': (b1, b2),
                    'kfx': kfx if loaded else 0.0, 'p': {}}
        for p, s in sizes.items():
            c2 = b2 + k2 * s['aux']
            if loaded:
                c2 += kfx * (min(s['fx'], FX_ANCHOR_ENGINES)
                             - FX_ANCHOR_ENGINES)
            out[row]['p'][p] = (b1 + k1 * s['ch'], c2)
    return out


def collect(products):
    nodes = graph_nodes()
    sizes, cells, cens = {}, {}, {}
    for p in products:
        d = product_def(p)
        nch, naux = int(d['ch']), int(d['aux'])
        sizes[p] = {
            'ch': nch, 'aux': naux,
            'grp': int(d.get('grp', 0)), 'fx': int(d.get('fx', 0)),
            'mtx': int(d.get('mtx', 0)), 'dca': int(d.get('dca', 0)),
            'chan_mask': (1 << nch) - 1, 'aux_mask': (1 << naux) - 1,
            'product_id': SCOPE_ID[p],
        }
        defined = matrix_cells(p)
        addressed = proposal_rows(p)
        unmapped = proposal_rows(p, 'dsp-unmapped.csv')
        assert len(addressed) + len(unmapped) == len(defined), p
        cells[p] = {
            'defined': len(defined),
            'addressed': len(addressed),
            'unmapped': len(unmapped),
            'chip1': sum(1 for r in addressed if r['DspSpi'] == '1'),
            'chip2': sum(1 for r in addressed if r['DspSpi'] == '2'),
        }
        cens[p] = census(nodes, nch, naux, SCOPE_ID[p])
    return nodes, sizes, cells, cens


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_table(products, sizes, cells, cens, pred, pred_worst):
    nodes = graph_nodes()
    total_nodes = len(nodes)
    print('PRODUCT FIT, BY CONSTRUCTION — S28 gate 1')
    print(f'  graph: {GRAPH_CSV.replace(REPO_ROOT + os.sep, "")} '
          f'({total_nodes} nodes, one firmware, decision D3)')
    print(f'  budget: {budget_cycles():,.0f} cycles/block at block {BLOCK}, '
          f'983.04 MHz')
    print(f'  anchors: {ANCHOR_LO} and {ANCHOR_HI}, measured driven on one '
          f'image (S27)')
    print()

    hdr = f'{"":26}' + ''.join(f'{p.upper():>12}' for p in products)
    print(hdr)
    print('-' * len(hdr))
    rows = [
        ('channels (ch)',      lambda p: sizes[p]['ch']),
        ('aux buses (aux)',    lambda p: sizes[p]['aux']),
        ('groups defined',     lambda p: sizes[p]['grp']),
        ('FX engines defined', lambda p: sizes[p]['fx']),
        ('matrix outs defined', lambda p: min(sizes[p]['mtx'], 4)),
        ('CFG_PRODUCT_ID',     lambda p: f'{sizes[p]["product_id"]} '
                                          f'({SCOPE_NAME[sizes[p]["product_id"]]})'),
        ('CFG_CHAN_MASK',      lambda p: f'0x{sizes[p]["chan_mask"]:08X}'),
        ('CFG_AUX_MASK',       lambda p: f'0x{sizes[p]["aux_mask"]:08X}'),
        ('cells defined',      lambda p: cells[p]['defined']),
        ('cells addressed',    lambda p: cells[p]['addressed']),
        ('  ... on chip 1',    lambda p: cells[p]['chip1']),
        ('  ... on chip 2',    lambda p: cells[p]['chip2']),
        ('cells unmapped',     lambda p: cells[p]['unmapped']),
        ('nodes run',          lambda p: sum(v['run'] for v in cens[p].values())),
        ('nodes gated off',    lambda p: sum(v['gated_off'] for v in cens[p].values())),
    ]
    for label, fn in rows:
        print(f'{label:26}' + ''.join(f'{fn(p)!s:>12}' for p in products))
    print()

    for row in ROW_ORDER:
        k1, k2 = pred[row]['slope']
        print(f'{row}  — {ROW_LABEL[row]}')
        print(f'{"":26}' + ''.join(f'{p.upper():>12}' for p in products))
        for chip, idx, slope, unit in ((1, 0, k1, 'strip'), (2, 1, k2, 'aux')):
            cells_ = ''.join(
                f'{pred[row]["p"][p][idx]:>12.2f}' for p in products)
            star = ''.join(
                '' for _ in products)
            print(f'  chip {chip} avg % of budget'.ljust(26) + cells_ + star)
        kfx = pred[row]['kfx']
        print(f'  (slope: {k1:+.3f} pts/strip on chip 1, '
              f'{k2:+.3f} pts/aux bus on chip 2'
              + (f', {kfx:+.3f} pts/FX engine on chip 2)' if kfx else ')'))
        wk1, wk2 = pred_worst[row]['slope']
        for chip, idx in ((1, 0), (2, 1)):
            print(f'  chip {chip} worst block'.ljust(26) + ''.join(
                f'{pred_worst[row]["p"][p][idx]:>12.2f}' for p in products))
        print()

    # The headline: the closest to the edge on the row the product ships
    # against, which is the driven row WITH the load.
    row = 'C_driven_load'
    worst = []
    for p in products:
        c1, c2 = pred_worst[row]['p'][p]
        worst.append((max(c1, c2), p, c1, c2))
    worst.sort(reverse=True)
    top = worst[0]
    print(f'closest to the edge on {row} (worst block): '
          f'{top[1].upper()} at {top[0]:.2f} %')


def print_census(products, sizes, cens):
    print()
    print('NODE CENSUS — the superset graph, and what each product\'s two '
          'config words leave running')
    types = sorted({t for p in products for (_, t) in cens[p]})
    for chip in ('1', '2'):
        print(f'\n  chip {chip}')
        print(f'    {"type":22}' + ''.join(f'{p.upper():>14}' for p in products))
        for t in types:
            if not any((chip, t) in cens[p] for p in products):
                continue
            cellsv = []
            for p in products:
                r = cens[p].get((chip, t), {'total': 0, 'run': 0})
                cellsv.append(f'{r["run"]}/{r["total"]}')
            print(f'    {t:22}' + ''.join(f'{v:>14}' for v in cellsv))


def print_excluded():
    print()
    print('NOT IN THE TABLE, AND WHY')
    for p, why in EXCLUDED.items():
        print(f'  {p.upper()}:')
        for ln in textwrap.wrap(why, 68):
            print('    ' + ln)


def print_unmasked(products, sizes):
    print()
    print('WHAT EACH PRODUCT PAYS FOR AND DOES NOT DEFINE')
    print('  (the firmware has exactly three product words — CFG_PRODUCT_ID,')
    print('   CFG_CHAN_MASK and CFG_AUX_MASK — and the first is a two-valued')
    print('   SCOPE class, so everything below runs at the superset size)')
    fixed = {'groups': 4, 'FX engines': 6, 'matrix buses': 4, 'DCAs': 8}
    key = {'groups': 'grp', 'FX engines': 'fx', 'matrix buses': 'mtx',
           'DCAs': 'dca'}
    print(f'    {"":22}' + ''.join(f'{p.upper():>14}' for p in products))
    for what, built in fixed.items():
        vals = []
        for p in products:
            have = min(sizes[p][key[what]], built)
            vals.append(f'{have} of {built}' + (' ' if have == built else '*'))
        print(f'    {what:22}' + ''.join(f'{v:>14}' for v in vals))
    print('    * runs anyway, on its cheap branch: no config word gates it')


def load_measured(path):
    """S28's own driven rows: {product: {row: {'1': [avg, worst, ovr, n],
    '2': [...]}}}, as the session's capacity JSONs summarise to."""
    if not path:
        return {}
    return json.load(open(path))


def write_csv(path, products, sizes, cells, cens, pred, pred_worst,
              measured=None):
    """MW/D32/DSP/fit-table.csv — the scoreboard's fit-table source."""
    head = [
        'fit-table.csv — does each product of the range fit the silicon.',
        '',
        'GENERATED by tools/dsp/product_fit.py (S28 gate 1). Do not hand-edit.',
        '',
        'ONE FIRMWARE, THREE WORDS (decision D3). Every row below is the SAME',
        'image — the superset graph of MW/D32/DSP/SHARC/dsp.csv, built from',
        'shipping.config.s26 as chip1 6396187c / chip2 9222c2ee — with a',
        'different CFG_PRODUCT_ID, CFG_CHAN_MASK and CFG_AUX_MASK. `cells_*`',
        "come from the product's own mx-master, expanded by",
        'defs/tools/expand_matrix.py and intersected with the graph by',
        'MW/D32/DSP/gen_dsp.py --propose.',
        '',
        'chip{1,2}_built_pct is the CONSTRUCTION (S28 gate 1): a two-point',
        'interpolation of the driven rows measured on d24 and d32, chip 1',
        'against the channel count, chip 2 against the aux count plus the',
        "product's own FX engine count. chip{1,2}_avg_pct and _worst_pct are",
        'MEASURED where source says so. `fits` is against the WORST BLOCK.',
        '',
        'row A silent/default | B silent/load | D driven, FX off |',
        'C driven, the product\'s FX load. C is the row a product ships',
        'against.',
        '',
        'NOT IN THIS TABLE, and why — a fit table that lists four of the',
        "range's nine product folders without saying so is a table that",
        'looks complete and is not:',
    ] + [f'  {p.upper()}: {why}' for p, why in EXCLUDED.items()] + ['']
    cols = ['product', 'row', 'source', 'ch', 'aux', 'fx', 'product_id',
            'chan_mask', 'aux_mask',
            'cells_defined', 'cells_addressed', 'cells_unmapped',
            'nodes_run', 'nodes_gated_off',
            'chip1_built_pct', 'chip1_avg_pct', 'chip1_worst_pct',
            'chip2_built_pct', 'chip2_avg_pct', 'chip2_worst_pct',
            'fits', 'note']
    with open(path, 'w', newline='', encoding='utf-8') as f:
        for h in head:
            f.write(f'# {h}\n' if h else '#\n')
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        measured = measured or {}
        for p in products:
            for row in ROW_ORDER:
                c1, c2 = pred[row]['p'][p]
                w1, w2 = pred_worst[row]['p'][p]
                src = 'construction'
                ovr = ''
                if p in measured and row in measured[p]:
                    m = measured[p][row]
                    c1, w1 = m['1'][0], m['1'][1]
                    c2, w2 = m['2'][0], m['2'][1]
                    ovr = m['1'][2] + m['2'][2]
                    src = 'measured'
                elif p in MEASURED[row]:
                    c1, c2 = MEASURED[row][p]
                    w1, w2 = MEASURED_WORST[row][p]
                    src = 'measured (S27 anchor)'
                n = cens[p]
                bb1, bb2 = pred[row]['p'][p]
                w.writerow({
                    'product': p, 'row': row,
                    'source': src,
                    'ch': sizes[p]['ch'], 'aux': sizes[p]['aux'],
                    'fx': sizes[p]['fx'],
                    'product_id': sizes[p]['product_id'],
                    'chip1_built_pct': f'{bb1:.2f}',
                    'chip2_built_pct': f'{bb2:.2f}',
                    'chan_mask': f'0x{sizes[p]["chan_mask"]:08X}',
                    'aux_mask': f'0x{sizes[p]["aux_mask"]:08X}',
                    'cells_defined': cells[p]['defined'],
                    'cells_addressed': cells[p]['addressed'],
                    'cells_unmapped': cells[p]['unmapped'],
                    'nodes_run': sum(v['run'] for v in n.values()),
                    'nodes_gated_off': sum(v['gated_off'] for v in n.values()),
                    'chip1_avg_pct': f'{c1:.2f}',
                    'chip1_worst_pct': f'{w1:.2f}',
                    'chip2_avg_pct': f'{c2:.2f}',
                    'chip2_worst_pct': f'{w2:.2f}',
                    'fits': 'yes' if max(w1, w2) < 100.0 else 'NO',
                    'note': (ROW_LABEL[row]
                             + (f'; {ovr} missed blocks' if ovr else '')),
                })
    print(f'wrote {path}')


def score_measured(got, pred, pred_worst):
    """Gate 2: the delta between construction and measurement, per product.

    For the ANCHORS this is a control, not a test: the construction IS their
    measurement, so a non-zero delta there is the instrument disagreeing with
    itself across sessions and is the scale every other delta is read
    against.
    """
    print()
    print('CONSTRUCTION vs MEASUREMENT  (delta = measured - built)')
    print(f'{"product":8}{"row":20}{"c1 built":>10}{"c1 meas":>9}{"Δ":>8}'
          f'{"c2 built":>11}{"c2 meas":>9}{"Δ":>8}  ovr')
    for p in sorted(got, key=lambda q: int(q[1:])):
        anchor = ' (ANCHOR — this is a control)' if p in (ANCHOR_LO,
                                                          ANCHOR_HI) else ''
        for row in ROW_ORDER:
            if row not in got[p]:
                continue
            b1, b2 = pred[row]['p'][p]
            m = got[p][row]
            m1, m2 = m['1'][0], m['2'][0]
            ovr = m['1'][2] + m['2'][2]
            print(f'{p:8}{row:20}{b1:>10.2f}{m1:>9.2f}{m1 - b1:>+8.2f}'
                  f'{b2:>11.2f}{m2:>9.2f}{m2 - b2:>+8.2f}  {ovr}')
        if anchor:
            print(f'{"":8}{anchor}')


def print_segments(got, sizes):
    """The per-unit slope of each ADJACENT pair of measured products.

    Two anchors that differ in more than one thing cannot separate those
    things, and the D24/D32 pair differs in three: channels, aux buses and
    the SCOPE CLASS (D32 is the only product that boots class 0, which runs
    the eight snake returns and their 24 transfer/receive/input nodes that
    every other product gates off). Printing the segments rather than one
    averaged slope is what makes that step visible -- S28-6.
    """
    have = [p for p in sorted(sizes, key=lambda q: sizes[q]['ch'])
            if p in got]
    if len(have) < 3:
        return
    print()
    print('PER-SEGMENT SLOPES, from the measured products')
    for row in ROW_ORDER:
        seg = [p for p in have if row in got[p]]
        if len(seg) < 3:
            continue
        print(f'  {row}')
        print(f'    {"segment":16}{"chip 1 pts/strip":>20}{"chip 2 pts/aux":>18}')
        for a, b in zip(seg, seg[1:]):
            dch = sizes[b]['ch'] - sizes[a]['ch']
            dax = sizes[b]['aux'] - sizes[a]['aux']
            k1 = (got[b][row]['1'][0] - got[a][row]['1'][0]) / dch
            k2 = (got[b][row]['2'][0] - got[a][row]['2'][0]) / dax
            print(f'    {a.upper() + " -> " + b.upper():16}'
                  f'{k1:>+20.2f}{k2:>+18.2f}')


def print_fx_cost(got, sizes):
    """Points of chip 2 per live FX engine, per measured product (S28-3)."""
    have = [p for p in sorted(sizes, key=lambda q: sizes[q]['ch'])
            if p in got and 'C_driven_load' in got[p]
            and 'D_driven_fxoff' in got[p]]
    if not have:
        return
    print()
    print('THE PLUGIN LOAD, per engine')
    print(f'    {"product":10}{"engines":>9}{"chip2 C-D":>12}{"per engine":>13}'
          f'{"chip1 C-D":>12}')
    for p in have:
        c = got[p]['C_driven_load']
        d = got[p]['D_driven_fxoff']
        n = min(sizes[p]['fx'], FX_ANCHOR_ENGINES)
        d2 = c['2'][0] - d['2'][0]
        d1 = c['1'][0] - d['1'][0]
        print(f'    {p.upper():10}{n:>9}{d2:>12.2f}{d2 / n:>13.2f}{d1:>+12.2f}')


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--products', default=','.join(PRODUCTS))
    ap.add_argument('--census', action='store_true',
                    help='also print the per-class node census')
    ap.add_argument('--csv', default=None, help='write the fit table here')
    ap.add_argument('--measured', default=None,
                    help='JSON {product: {row: [chip1, chip2]}} to score the '
                         'construction against')
    a = ap.parse_args()

    products = [p.strip() for p in a.products.split(',') if p.strip()]
    nodes, sizes, cells, cens = collect(products)
    for anchor in (ANCHOR_LO, ANCHOR_HI):
        if anchor not in sizes:
            _, sizes_all, _, _ = collect(sorted(set(products) | {anchor}))
            sizes.update({anchor: sizes_all[anchor]})
    pred = predict(sizes, MEASURED)
    pred_worst = predict(sizes, MEASURED_WORST)

    print_table(products, sizes, cells, cens, pred, pred_worst)
    print_unmasked(products, sizes)
    print_excluded()
    if a.census:
        print_census(products, sizes, cens)
    got = load_measured(a.measured)
    if a.csv:
        write_csv(a.csv, products, sizes, cells, cens, pred, pred_worst, got)
    if got:
        score_measured(got, pred, pred_worst)
        print_fx_cost(got, sizes)
        print_segments(got, sizes)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
