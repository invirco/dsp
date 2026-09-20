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
     FOUR words select a product inside it: `CFG_PRODUCT_ID` (the
     product-SCOPE gate), `CFG_CHAN_MASK`, `CFG_AUX_MASK` and — since
     S79 — `CFG_MTX_MASK`. So "the D16 graph" is not a different graph
     — it is the same 698 nodes with a different set of them gated off,
     and this file resolves the gates with the SAME rules the generator
     emits them with (`dsp_codegen.STRIP_NODE_RE`, `STRIP_MTR_RE`,
     `aux_owner`, `mtx_owner`, and the
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
the two SCOPE classes, the MATRIX buses since S79, and nothing else. A
D12 defines two groups, four FX engines, no matrix and no centre
cluster; the firmware runs four groups and six FX engines whatever is
booted, because no word says otherwise. THE MATRIX SENTENCE USED TO BE
IN THAT LIST AND IS NOT ANY MORE: CFG_MTX_MASK (0xF006) is the fourth
word, a D12 and a D16 boot with it at 0 and all four matrix chains --
twelve node instances -- are skipped at block level, and a D24 boots
with 0x3 and skips six.
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

THE MEASURED ROWS LIVE IN A FILE AND THE CSV CANNOT BE REGENERATED
WITHOUT IT (S32). `--csv` on its own rewrites every measured product row
as the CONSTRUCTION, silently. S28's measured JSON was never committed;
`MW/D32/DSP/fit-measured.json` is it, recovered from the table it
produced, so the canonical regeneration is

    python3 tools/dsp/product_fit.py \
        --measured MW/D32/DSP/fit-measured.json \
        --csv MW/D32/DSP/fit-table.csv
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
                         mtx_owner, BLOCK, SAMPLE_RATE_HZ)

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
# RE-ANCHORED at hub ruling S81-Q1(a), 2026-09-20 (dispatch "S81 — hub
# answers to S80"; question and options at
# `MW/D24/DSP/s80/cfg3-rows-dark.md` §7). The construction was a two-point
# (D24, D32) interpolation of S27's driven anchors
# (`MW/D32/DSP/dsp4-s27-20260910.md` §2.1/§2.2); against S80's rows on the
# fixed instrument (CFG3 landed, the pre-fix MFD-2 bit-shift closed) those
# anchors were out by +43 to +85 points (S80 report §5, §7; reproduced
# below by `score_measured`). Ruling: re-anchor A and B on S80's silent
# rows across all four products; predict C from D16/D24/D32 only, since
# D12's driven regime never proved (22 of 24 chip-2 envelopes, both boots
# of both arms — S80 report §4.2, §4.4) and is NOT a measurement of D12;
# every rewritten prediction carries its anchor session/date (`ROW_ANCHOR`,
# `is_extrapolated`, and the `source` column `write_csv` emits).
#
# A_silent_default / B_silent_load: S80 report §4.2, all four products,
# `MW/D32/DSP/fit-measured.json`. Arms `s80d12b1`/`s80d16b1`/`s80s28d24`/
# `s80s28d32`, ONE byte-identical pair (chip1 `e364c522…`, chip2
# `63b40b85…`), `DSP4_AUXIN_BYPASS=1` (shipping), REPS=2, 45 s dwell,
# 983.01-983.08 MHz, block 16.
#
# C_driven_load: same session, same arms, D16/D24/D32 only — D12's row is
# DELIBERATELY ABSENT from `fit-measured.json` (see its own `_NOTE`) and
# is excluded here too; D12's construction is therefore an EXTRAPOLATION,
# flagged by `is_extrapolated()`, not an interpolation.
#
# D_driven_fxoff: UNCHANGED, still S27, still D24/D32 only, and STALE.
# `capacity.sh --driven` takes three rows, not four
# (`fit-measured.json`'s own `_NOTE`: "There is no D row (driven, FX
# off)"), so S80 supplies nothing to re-anchor it with. It is printed
# with its stale S27 date so a reader can tell it apart from the rows
# S80 touched.
#
# Each entry is (chip-1 avg %, chip-2 avg %). `worst` carries the
# S21-6-corrected worst block of the same rows.
# ---------------------------------------------------------------------------
# S82: THE D24 ROWS ARE ON THE SIGNED CONFIGURATION AND THE OTHERS ARE NOT.
# ---------------------------------------------------------------------------
# PW signed DSP4_SIMD_DYN + DSP4_STRIP_FUSED + DSP4_DYN_LUT + DSP4_GATE_LINTHR
# on 2026-09-20. S82 re-measured the D24 on it, two boots, regime proven on
# both (48 of 48 chip-1 envelopes, 28 of 32 -- 28 of 28 -- on chip 2), and the
# driven row went from 123.57/127.50 with 21.5 % of blocks missed to
# 57.54/84.34 with NONE. D16, D32 and D12 have NOT been re-measured on it.
#
# SO THE TABLE NOW MIXES TWO CONFIGURATIONS AND SAYS SO, rather than either
# pretending it does not or throwing away the one product that has been
# measured. S81 5.1 is the precedent and the warning: the FX-engine correction
# term was retired precisely because it mixed an S80 C row with a stale S27 D
# row "from a different session and a different bitstream". The same caution
# applies here with more force, because the configuration difference is worth
# 43 points of chip 2 on the row that decides whether a product fits.
#
# WHAT THAT MEANS FOR A READER: the D24 rows are the product, on the
# configuration that ships. Every other product's row is the PRE-S82
# configuration and is an upper bound on what it will read once re-measured --
# the signing only ever removed cycles. The cross-product interpolation that
# `predict()` builds from these anchors is therefore NOT like-for-like until
# D16/D32/D12 are re-taken, and `source` says which configuration each row
# came from.
MEASURED_PRE_S82_SUPERSEDED = {
    # The D24 rows this file carried until S82, on DIAG_BUILD_CFG2 0xE2018264
    # (S80's arms, the pre-signing shipping configuration). Kept so the
    # improvement the signing bought stays auditable from this file.
    'A_silent_default': {'d24': (56.04, 88.33)},
    'B_silent_load':    {'d24': (80.71, 98.28)},
    'C_driven_load':    {'d24': (123.57, 127.50)},
}
MEASURED = {
    # row key: {product: (chip1_avg, chip2_avg)}
    # d24: S82, the SIGNED configuration, DIAG_BUILD_CFG2 0xE2018E6F.
    # d12/d16/d32: S80, the PRE-S82 configuration, 0xE2018264.
    'A_silent_default': {'d12': (32.44, 71.07), 'd16': (40.32, 79.47),
                          'd24': (43.22, 77.41), 'd32': (72.05, 105.62)},
    'B_silent_load':    {'d12': (43.67, 76.03), 'd16': (55.88, 87.73),
                          'd24': (57.50, 84.27), 'd32': (106.70, 118.90)},
    'D_driven_fxoff':   {'d24': (59.91, 64.38), 'd32': (79.02, 80.67)},
    'C_driven_load':    {'d16': (84.59, 113.00),
                          'd24': (57.54, 84.34), 'd32': (164.32, 151.57)},
}
MEASURED_WORST = {
    'A_silent_default': {'d12': (32.54, 71.33), 'd16': (40.49, 79.78),
                          'd24': (56.22, 88.57), 'd32': (72.39, 106.04)},
    'B_silent_load':    {'d12': (43.98, 76.33), 'd16': (56.12, 88.08),
                          'd24': (80.94, 98.50), 'd32': (107.19, 119.25)},
    'D_driven_fxoff':   {'d24': (60.27, 64.61), 'd32': (79.78, 81.00)},
    'C_driven_load':    {'d16': (84.95, 113.46),
                          'd24': (124.10, 128.02), 'd32': (164.70, 152.39)},
}

# S27's original A/B/C anchors, SUPERSEDED, kept only so the delta this
# ruling reproduces (S80 report: "+43 points (D24) and +51 to +85 (D32)")
# stays auditable without digging up dsp4-s27-20260910.md. Not read by any
# code path below — `git log`/dsp4-s27-20260910.md §2.1/§2.2 remain the
# citable source, this is a convenience copy.
MEASURED_S27_SUPERSEDED = {
    'A_silent_default': {'d24': (50.72, 63.02), 'd32': (65.38, 76.09)},
    'B_silent_load':    {'d24': (59.97, 84.64), 'd32': (79.07, 100.88)},
    'C_driven_load':    {'d24': (59.82, 84.37), 'd32': (79.16, 100.81)},
}
ROW_LABEL = {
    'A_silent_default': 'silent, the config the product boots with',
    'B_silent_load':    'silent, every assign/send open, dynamics at -60 dB',
    'D_driven_fxoff':   'driven, the FX engines OFF  (plain)',
    'C_driven_load':    'driven, every FX engine live at Type 3  (the load)',
}
ROW_ORDER = ('A_silent_default', 'B_silent_load',
             'D_driven_fxoff', 'C_driven_load')

# ---------------------------------------------------------------------------
# S33: WINDOW CANDIDATE B, WHICH IS A CANDIDATE AND NOT A PRODUCT ROW
# ---------------------------------------------------------------------------
# A row family for the SECOND window candidate: the same products, the same
# cells and the same masks as the rows above, built from
# `shipping.config.s32` — `shipping.config.s26` plus one effective line,
# `DSP4_AUXIN_BYPASS=1` (chip1 `6396187c`, *the same bytes as candidate A*,
# chip2 `df5cc181`). It is a SEPARATE FAMILY so that nothing in the table
# above is replaced by a figure taken on an image the window has not signed,
# and so that the two candidates can be read side by side.
#
# `DSP4_AUXIN_BYPASS=1`: a chip-2 AUX_INPUT whose `on` cell is 0 publishes one
# block of silence and is then not CALLED until the cell goes back to 1.
# Twelve such nodes exist on chip 2, all twelve boot off, and no capacity row
# this programme has taken turns one of them on.
#
# MEASURED, not constructed. Bench rev C, 2026-09-11, BOTH candidates driven
# on the same night with one instrument and one bitstream, **two boots a row
# an arm**, DWELL 45, `SETUP_MODE=loadfx FXTYPE=3 FXTYPES="off"`,
# `DSP_LANDED_DIR=proposals/defs/products`.
#
# SUPERSEDES S32's FOUR `@s32-lead` ROWS. They were the same image on the
# same bench, two products and two rows; these are four products and four
# rows, and carrying both would put two numbers against one row. S32's
# originals are in `MW/D32/DSP/dsp4-s32-20260911.md` §3.2/§3.4.
#
# ROWS C AND D CARRY A LABEL AND IT IS NOT COSMETIC: the `driveall` LOGIC
# bitstream could not be loaded (the analog board may be attached and the
# dispatch forbids reflashing the CPLD), so the rows taken with the stimulus
# playing ran a PARTIAL regime — identically in both arms, which is what
# makes their delta a measurement, but they are not the fully driven rows the
# product rows above quote. Rows A and B are stimulus-stopped and ARE
# directly comparable; row B is the row that decides D32's fit.
LEAD_FAMILY = 's32'
LEAD_ROWS = {
    ('d12', 'A_silent_default'):    (29.84, 51.88),
    ('d12', 'B_silent_load'):       (33.12, 64.97),
    ('d12', 'D_driven_fxoff'):      (33.17, 51.83),
    ('d12', 'C_driven_load'):       (33.28, 64.93),
    ('d16', 'A_silent_default'):    (36.92, 56.62),
    ('d16', 'B_silent_load'):       (41.64, 71.37),
    ('d16', 'D_driven_fxoff'):      (41.61, 58.10),
    ('d16', 'C_driven_load'):       (41.70, 71.35),
    ('d24', 'A_silent_default'):    (50.96, 61.41),
    ('d24', 'B_silent_load'):       (59.96, 82.82),
    ('d24', 'D_driven_fxoff'):      (60.02, 62.77),
    ('d24', 'C_driven_load'):       (60.15, 82.81),
    ('d32', 'A_silent_default'):    (65.44, 70.96),
    ('d32', 'B_silent_load'):       (79.15, 95.84),
    ('d32', 'D_driven_fxoff'):      (79.18, 75.55),
    ('d32', 'C_driven_load'):       (79.28, 95.59),
}
LEAD_WORST = {
    ('d12', 'A_silent_default'):    (30.03, 52.22),
    ('d12', 'B_silent_load'):       (33.37, 65.22),
    ('d12', 'D_driven_fxoff'):      (33.37, 51.93),
    ('d12', 'C_driven_load'):       (33.40, 64.93),
    ('d16', 'A_silent_default'):    (37.15, 56.73),
    ('d16', 'B_silent_load'):       (41.72, 71.60),
    ('d16', 'D_driven_fxoff'):      (41.94, 58.39),
    ('d16', 'C_driven_load'):       (41.70, 71.45),
    ('d24', 'A_silent_default'):    (51.06, 61.69),
    ('d24', 'B_silent_load'):       (60.16, 82.97),
    ('d24', 'D_driven_fxoff'):      (60.27, 62.87),
    ('d24', 'C_driven_load'):       (60.27, 82.98),
    ('d32', 'A_silent_default'):    (65.68, 71.29),
    ('d32', 'B_silent_load'):       (79.34, 95.97),
    ('d32', 'D_driven_fxoff'):      (79.51, 75.88),
    ('d32', 'C_driven_load'):       (79.50, 96.00),
}
# S82: which products' measured rows are on the SIGNED configuration. Every
# other product's row is the pre-signing one and is an UPPER BOUND on what it
# will read once re-measured, because the signing only ever removed cycles.
SIGNED_CONFIG_ROWS = {'d24'}

# ZERO missed blocks on every row of every product of candidate B (S33).
LEAD_OVR = {}

_B_D32 = ('window candidate B (DSP4_AUXIN_BYPASS=1): the twelve switched-off '
          'chip-2 AUX_INPUT nodes not called; chip 2 -4.96/-5.35 pts, '
          'worst-use rung 95.69 % with ZERO missed (candidate A 100.86 %, '
          '1900 of 270096) -- the twelfth aux fits')
_B_SMALL = ('window candidate B (DSP4_AUXIN_BYPASS=1): FOUR switched-off '
            'AUX_INPUT nodes not called (the snake eight are scope-gated off '
            'below D32); chip 2 -1.5 to -1.8 pts, headroom not a rescue')
_B_PARTIAL = ('  [PARTIAL REGIME: the driveall bitstream could not be loaded '
              '- the CPLD was not reflashed - so this row ran 0 of 64 chip-1 '
              'and 27 of 32 chip-2 envelopes, IDENTICALLY IN BOTH ARMS. Rows '
              'A and B are stimulus-stopped and are the comparable ones.]')
LEAD_NOTE = {}
for _p in ('d12', 'd16', 'd24', 'd32'):
    for _r in ROW_ORDER:
        LEAD_NOTE[(_p, _r)] = ((_B_D32 if _p == 'd32' else _B_SMALL)
                               + (_B_PARTIAL if _r in ('C_driven_load',
                                                       'D_driven_fxoff')
                                  else ''))

# Per-row anchor set, re-derived at S81-Q1(a) (see "The measured anchors"
# above). Replaces the old fixed `ANCHOR_LO, ANCHOR_HI = 'd24', 'd32'` pair
# — every row now names its own anchor products, and A/B/C carry a
# different set than the still-stale D.
ROW_ANCHOR = {
    'A_silent_default': {'products': ('d12', 'd16', 'd24', 'd32'),
                         'session': 'S80', 'date': '2026-09-20'},
    'B_silent_load':    {'products': ('d12', 'd16', 'd24', 'd32'),
                         'session': 'S80', 'date': '2026-09-20'},
    'C_driven_load':    {'products': ('d16', 'd24', 'd32'),
                         'session': 'S80', 'date': '2026-09-20'},
    'D_driven_fxoff':   {'products': ('d24', 'd32'),
                         'session': 'S27', 'date': '2026-09-10'},
}

# The measured code pool and DM, S26/S27. ONE firmware: these are the same
# bytes on every product in the range, because every product boots the same
# image. Recorded here so the fit table can say so with a number.
CODE_POOL_BYTES = 262144
CODE_USED_C1 = 180954          # `shipping.config.s26`, S28's own map file
CODE_USED_C2 = 164168          # (S27 §1.1 read 181,350 on its link: 396 apart)
DM_NOTE = ('A SMALLER PRODUCT BUYS CYCLES, NOT MEMORY. One image boots on '
           'every product in the range, so the code pool and the DM are the '
           'same bytes on all of them: every strip, aux chain, group and FX '
           'engine the superset carries is LINKED whatever the masks say, '
           'and the masks decide only which of them are CALLED.')


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


# The firmware carries four matrix chains: C2_RECV_MTX/_MTX_FDR/_MTX_OUT_01..04.
MTX_CHAINS = 4


def matrix_bus_cells(product):
    """How many distinct `Matrix0NN` buses `defs/products/<p>/dsp.csv`
    addresses. Reachability is a CELL question, so it is answered from the
    cells and not from a size key."""
    path = os.path.join(DEFS_PRODUCTS, product, 'dsp.csv')
    if not os.path.isfile(path):
        raise SystemExit(f'product_fit: {path} is missing — this product has '
                         f'no landed dsp.csv in the defs submodule. '
                         f'(No fallback.)')
    seen = set()
    for line in open(path, encoding='utf-8'):
        m = re.match(r'^Matrix(\d+)', line)
        if m:
            seen.add(int(m.group(1)))
    return len(seen)


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
    """('chan', n) | ('aux', n) | ('mtx', n) | None — the SAME rule the
    generator's chain emitter uses to decide which gate a node sits behind.

    The third key arrived at S79 with CFG_MTX_MASK, and with it the twelve
    `C2_MIX_AUX_nn` the aux rule had never matched. Both are imported from
    `dsp_codegen` rather than restated here, for the reason the module
    docstring gives: a second opinion about which node belongs to which
    gate is how a scoreboard comes to disagree with the firmware."""
    nid = node['id']
    m = STRIP_NODE_RE.match(nid) or STRIP_MTR_RE.match(nid)
    if m:
        return ('chan', int(m.group(m.lastindex)))
    label = 'chip1' if node['chip'] == '1' else 'chip2'
    a = aux_owner(label, nid)
    if a is not None:
        return ('aux', a)
    x = mtx_owner(label, nid)
    if x is not None:
        return ('mtx', x)
    return None


def census(nodes, nch, naux, scope_id, nmtx=None):
    """Per (chip, type): how many nodes the image carries, how many this
    product's FOUR config words leave RUNNING, and how many they gate off.

    `nmtx` is CFG_MTX_MASK's population count (S79). It defaults to None,
    which means "this caller has not been taught about the fourth word" and
    is scored as the pre-S79 firmware behaved: every matrix chain runs."""
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
        if own[0] == 'mtx' and nmtx is None:
            rec['run'] += 1
            continue
        rec['gateable'] += 1
        limit = {'chan': nch, 'aux': naux, 'mtx': nmtx}[own[0]]
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


def lsq_line(points):
    """slope, intercept of the least-squares line through 2+ (x, y) points.

    Generalises `line()` to `ROW_ANCHOR` sets of more than two products
    (S81-Q1(a): A/B anchor on four, C on three). With exactly two points
    this reduces algebraically to `line()`'s exact interpolation -- it is
    not a different model for the rows that still have two anchors (D),
    only for the rows that now have more.
    """
    n = len(points)
    if n < 2:
        raise SystemExit('product_fit: fewer than two anchor points for '
                         'this row -- there is no line to fit.')
    sx = sum(x for x, _ in points)
    sy = sum(y for _, y in points)
    sxx = sum(x * x for x, _ in points)
    sxy = sum(x * y for x, y in points)
    denom = n * sxx - sx * sx
    if denom == 0:
        raise SystemExit('product_fit: the anchor products all have the '
                         'same size on this axis -- there is no line '
                         'through them.')
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    return slope, intercept


def is_extrapolated(row, product, sizes):
    """True if `product` sits outside the (ch, aux) range `ROW_ANCHOR[row]`
    was fit on -- the construction is EXTRAPOLATING past its own data, not
    interpolating inside it. D12's `C_driven_load` is the one case in this
    table (S81-Q1(a): D12 has no quotable driven row, S80 report §4.2/§4.4,
    so it is excluded from C's anchor set and its C prediction is the line
    read below the smallest product actually on it)."""
    anchors = ROW_ANCHOR[row]['products']
    if product in anchors:
        return False
    chs = [sizes[a]['ch'] for a in anchors]
    auxs = [sizes[a]['aux'] for a in anchors]
    return not (min(chs) <= sizes[product]['ch'] <= max(chs)
                and min(auxs) <= sizes[product]['aux'] <= max(auxs))


# RETIRED at S81-Q1(a), 2026-09-20 -- kept for the record, NOT called by
# `predict()` below. It existed to attribute a loaded row's chip-2 cost to
# live FX engines because the old two anchors (D24, D32) both defined all
# six and the construction could show the effect no other way. Calling it
# now would mix S80's `C_driven_load` anchors with `D_driven_fxoff`'s
# untouched S27 ones -- a different session, and for C specifically the
# very bitstream bug S80 was taken to fix (S80 report §4.3: every S28/S27
# driven row ran the MFD-2 stimulus at 2 LSB). It is also no longer needed:
# every row's new anchor set spans real FX-engine counts directly on
# MEASURED data (D12/D16 define four engines, D24/D32 six), so the per-aux
# fit already carries whatever the engine count costs. See `predict()`.
FX_LOADED_ROWS = ('B_silent_load', 'C_driven_load')
FX_ANCHOR_ENGINES = 6


def _fx_slope_RETIRED(table):
    """Points of chip 2 per live reverb engine, from the D24/D32 anchors
    alone. RETIRED — see the comment above. Left only so the S27-era
    number (`+3.344` pts/engine, still printed in old reports) can be
    reproduced by hand if it is ever needed again."""
    vals = []
    for p in ('d24', 'd32'):
        c = table['C_driven_load'][p][1]
        d = table['D_driven_fxoff'][p][1]
        vals.append((c - d) / FX_ANCHOR_ENGINES)
    return sum(vals) / len(vals)


def predict(sizes, table):
    """{row: {product: (chip1, chip2)}} by least-squares fit on each row's
    OWN anchor set (`ROW_ANCHOR`), re-derived at S81-Q1(a) from S80's
    measured rows (S80 report §7, hub ruling 2026-09-20).

    chip 1 is taken as a function of the CHANNEL count and chip 2 of the
    AUX count: chip 1 carries the 32 channel strips and chip 2 carries the
    twelve aux chains, and those are the two things the config words move.
    The anchors move both together, so the split between them is an
    ATTRIBUTION, not a measurement -- see "what the prediction cannot see"
    at the top of this module.

    A_silent_default and B_silent_load fit all four products S80 measured
    silent. C_driven_load fits D16/D24/D32 only -- D12's driven row never
    proved (S80 report §4.2/§4.4) and is excluded from the fit; D12's own
    C prediction is therefore an EXTRAPOLATION below the smallest anchor,
    and `is_extrapolated()`/`write_csv` mark it so rather than passing it
    off as an interpolation. D_driven_fxoff keeps its original two S27
    anchors (D24, D32) -- S80 took three rows, not four, so there is
    nothing to re-anchor it with; it is printed with its S27 date so a
    reader can tell it apart from the rows this ruling touched.

    With exactly two anchor products (D_driven_fxoff, and any row where a
    caller narrows `ROW_ANCHOR`) the fit is `line()`'s exact interpolation.
    With three or four it is `lsq_line()`'s least-squares line, which is
    NOT exact at any single anchor -- the residual at an anchor is itself
    useful (it is the S81-Q1 sanity check: the S80 report's flat
    per-segment slopes, §4.5, predict small residuals, and `score_measured`
    below shows whether they are).

    THE FX-ENGINE CORRECTION TERM IS GONE. See the comment above
    `_fx_slope_RETIRED`: it would mix a S80 C-row anchor with a stale S27
    D-row one, and it is no longer needed because every anchor set below
    now spans real FX-engine counts on real measured data.
    """
    out = {}
    for row, per_product in table.items():
        ra = ROW_ANCHOR[row]['products']
        anchor_products = [p for p in ra if p in per_product]
        pts1 = [(sizes[p]['ch'], per_product[p][0]) for p in anchor_products]
        pts2 = [(sizes[p]['aux'], per_product[p][1]) for p in anchor_products]
        k1, b1 = lsq_line(pts1)
        k2, b2 = lsq_line(pts2)
        out[row] = {'slope': (k1, k2), 'intercept': (b1, b2),
                    'kfx': 0.0, 'anchor_products': tuple(anchor_products),
                    'p': {}}
        for p, s in sizes.items():
            out[row]['p'][p] = (b1 + k1 * s['ch'], b2 + k2 * s['aux'])
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
            # CFG_MTX_MASK (S79). The firmware builds FOUR matrix chains, so
            # the mask is what the product's own cells reach, capped at four.
            # Both defs sources agree once capped: the `mtx` key above
            # (d24 2, d16/d12 absent) and the Matrix0NN cells in
            # `defs/products/<p>/dsp.csv` (d32 four, d24 two, d16/d12 none).
            # They agree for every product EXCEPT in what D32's key claims:
            # it says twelve, and four are built and four addressed. That is
            # recorded, not resolved -- see S79-9 and S78-Q2, both PW's.
            'mtx_run': min(matrix_bus_cells(p), MTX_CHAINS),
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
        cens[p] = census(nodes, nch, naux, SCOPE_ID[p],
                         nmtx=sizes[p]['mtx_run'])
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
    print('  anchors, re-anchored S81-Q1(a) 2026-09-20:')
    for row in ROW_ORDER:
        ra = ROW_ANCHOR[row]
        stale = ('  — STALE, no S80 data' if ra['session'] != 'S80' else '')
        print(f'    {row}: ' + ', '.join(p.upper() for p in ra['products'])
              + f" ({ra['session']}, {ra['date']}){stale}")
    print(f'  code pool: chip 1 {CODE_USED_C1:,} of {CODE_POOL_BYTES:,} bytes '
          f'({100.0 * CODE_USED_C1 / CODE_POOL_BYTES:.1f} %), chip 2 '
          f'{CODE_USED_C2:,} — THE SAME ON EVERY PRODUCT BELOW.')
    for ln in textwrap.wrap(DM_NOTE, 72):
        print(f'    {ln}')
    print()

    hdr = f'{"":26}' + ''.join(f'{p.upper():>12}' for p in products)
    print(hdr)
    print('-' * len(hdr))
    rows = [
        ('channels (ch)',      lambda p: sizes[p]['ch']),
        ('aux buses (aux)',    lambda p: sizes[p]['aux']),
        ('groups defined',     lambda p: sizes[p]['grp']),
        ('FX engines defined', lambda p: sizes[p]['fx']),
        # THE SIZE KEY AND THE CELLS DISAGREE ON ONE PRODUCT. `min(.., 4)`
        # was here before S79 because the D32 def's `mtx` key says TWELVE
        # and the firmware builds four; `mtx_run` counts the Matrix0NN
        # buses the product's own dsp.csv addresses, which is four on D32,
        # two on D24 and none on D16/D12 -- the reachability question
        # CFG_MTX_MASK is the answer to. Both rows are printed so the
        # disagreement is on the table rather than inside a min() (S79-9).
        ('matrix buses in the def', lambda p: sizes[p]['mtx']),
        ('matrix outs defined', lambda p: sizes[p]['mtx_run']),
        ('CFG_PRODUCT_ID',     lambda p: f'{sizes[p]["product_id"]} '
                                          f'({SCOPE_NAME[sizes[p]["product_id"]]})'),
        ('CFG_CHAN_MASK',      lambda p: f'0x{sizes[p]["chan_mask"]:08X}'),
        ('CFG_AUX_MASK',       lambda p: f'0x{sizes[p]["aux_mask"]:08X}'),
        ('CFG_MTX_MASK',       lambda p: '0x%08X'
                                         % ((1 << sizes[p]['mtx_run']) - 1)),
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
    print('NODE CENSUS — the superset graph, and what each product\'s four '
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
    """The measured driven rows: {product: {row: {'1': [avg, worst, ovr, n],
    '2': [...]}}}, as a session's capacity JSONs summarise to.

    KEYS BEGINNING `_` ARE DROPPED, so the file can carry its own provenance.
    Until S80 it could not: `score_measured` sorts the products with
    `int(p[1:])` and any non-product key raised ValueError, so the one thing
    that says WHICH arms these rows came from had to live outside the file
    holding them. That is how S28's measured rows came to be uncommitted and
    later reconstructed from the table they had produced (the note at the head
    of this module). A data file that cannot state its own provenance gets
    separated from it.
    """
    if not path:
        return {}
    return {k: v for k, v in json.load(open(path)).items()
            if not k.startswith('_')}


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
        'chip{1,2}_built_pct is the CONSTRUCTION: chip 1 fit against the',
        'channel count, chip 2 against the aux count, on EACH ROW\'S OWN',
        'anchor set (`ROW_ANCHOR` in product_fit.py). RE-ANCHORED at hub',
        'ruling S81-Q1(a), 2026-09-20 (MW/D24/DSP/s80/cfg3-rows-dark.md §7):',
        'rows A and B now fit ALL FOUR products\' S80 silent rows; row C',
        'fits D16/D24/D32 only (D12\'s driven regime never proved, S80',
        'report §4.2/§4.4, so D12\'s C is an EXTRAPOLATION below the',
        'smallest anchor, flagged in `source`); row D (driven, FX off) has',
        'no S80 measurement at all and keeps its original S27 anchors',
        '(d24/d32, 2026-09-10) -- STALE, and `source` says so. The old',
        'FX-engine correction term is retired (see `_fx_slope_RETIRED` in',
        'product_fit.py): every re-anchored row now spans real FX-engine',
        'counts on real measured data, so a separate term would double it.',
        '`source` on every row names which session/date it was built or',
        'measured against. chip{1,2}_avg_pct and _worst_pct are MEASURED',
        'where source says so. `fits` is against the WORST BLOCK.',
        '',
        'row A silent/default | B silent/load | D driven, FX off |',
        'C driven, the product\'s FX load. C is the row a product ships',
        'against.',
        '',
        'REGENERATE WITH THE MEASURED ROWS, or they are lost (S32): the',
        'measured product rows come from --measured, and running this script',
        'without it silently replaces them with the construction. S28 passed',
        'a JSON that was never committed; it is committed now, recovered',
        'from this table, so the file regenerates from the repo alone:',
        '  python3 tools/dsp/product_fit.py \\',
        '      --measured MW/D32/DSP/fit-measured.json \\',
        '      --csv MW/D32/DSP/fit-table.csv',
        '',
        f'Rows tagged @{LEAD_FAMILY} are WINDOW CANDIDATE B: the same',
        'products, cells and masks, built from shipping.config.s32 —',
        'shipping.config.s26 plus one effective line, DSP4_AUXIN_BYPASS=1',
        '(chip1 6396187c, the SAME BYTES as candidate A; chip2 df5cc181).',
        'A separate family so that no product row above is replaced by a',
        'figure taken on an image the window has not signed. Measured',
        '2026-09-11, both candidates on one night, two boots a row an arm.',
        'The C and D rows of candidate B ran a PARTIAL driven regime —',
        'identically in both arms — because the driveall bitstream needs a',
        'CPLD reflash that session was forbidden; rows A and B are',
        'stimulus-stopped and are the comparable ones, and row B is the row',
        "that decides D32's fit. Supersedes S32's four @s32-lead rows.",
        'See MW/D32/DSP/dsp4-s33-20260911.md and window-candidate.md §5.',
        '',
        'THE FOURTH WORD (S79, CFG_MTX_MASK) POSTDATES SOME ROWS AND NOT',
        'OTHERS, and that line moved at S81-Q1(a): rows A/B/C are S80',
        '(2026-09-20), taken AFTER S79 landed CFG_MTX_MASK, so their',
        'nodes_run / nodes_gated_off match the percentages they sit beside.',
        'Row D (driven, FX off) is still S27 (2026-09-10, pre-S79) and IS',
        'pessimistic by the unmeasured margin the old note described: 10',
        'more node instances on a D24, 18 on a D16, 20 on a D12, none on a',
        'D32, all called but on their cheap branch. The @s32-lead rows',
        'below are S32 (2026-09-11), also pre-S79, same caveat. S79\'s own',
        'driven rows are in MW/D24/DSP/s79/bypass.md and are deliberately',
        'NOT merged here: they were taken on the S78-fixed driveall',
        'bitstream and a row taken on one stimulus is not comparable with',
        'a row taken on another (see loadlogic.sh).',
        '',
        'NOT IN THIS TABLE, and why — a fit table that lists four of the',
        "range's nine product folders without saying so is a table that",
        'looks complete and is not:',
    ] + [f'  {p.upper()}: {why}' for p, why in EXCLUDED.items()] + ['']
    cols = ['product', 'row', 'source', 'ch', 'aux', 'fx', 'product_id',
            'chan_mask', 'aux_mask', 'mtx_mask',
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
                ra = ROW_ANCHOR[row]
                stale = ' STALE' if ra['session'] != 'S80' else ''
                extrap = (', EXTRAPOLATED' if is_extrapolated(row, p, sizes)
                          else '')
                src = (f"construction ({ra['session']} anchors "
                       f"{ra['date']}{stale}{extrap})")
                ovr = ''
                if p in measured and row in measured[p]:
                    m = measured[p][row]
                    c1, w1 = m['1'][0], m['1'][1]
                    c2, w2 = m['2'][0], m['2'][1]
                    ovr = m['1'][2] + m['2'][2]
                    src = 'measured'
                    if p in ra['products']:
                        src += f" (anchor, {ra['session']} {ra['date']})"
                    # S82: THE D24 IS ON THE SIGNED CONFIGURATION AND THE
                    # OTHERS ARE NOT, so the row says which it is and the
                    # anchor label -- which still names the session the FIT
                    # was built from -- stops being read as the session the
                    # NUMBER came from. Without this the D24 rows read
                    # "ANCHOR (S80) — control, passes by construction" while
                    # carrying S82 measurements and a 44-point residual,
                    # which is the S28 mislabelling one column to the left.
                    if p in SIGNED_CONFIG_ROWS:
                        src += ' [S82 SIGNED CONFIG 0xE2018E6F; the'
                        src += ' construction is anchored on the PRE-S82'
                        src += ' rows, so the residual is the signing]'
                    else:
                        src += ' [pre-S82 config 0xE2018264 — upper bound]'
                elif p in MEASURED[row]:
                    c1, c2 = MEASURED[row][p]
                    w1, w2 = MEASURED_WORST[row][p]
                    src = f"measured (anchor, {ra['session']} {ra['date']}{stale})"
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
                    'mtx_mask': '0x%08X' % ((1 << sizes[p]['mtx_run']) - 1),
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
        # THE LEAD ROWS (S32), appended, never substituted. Same columns,
        # same census, a row key that carries the family so no reader can
        # mistake one for the product row it sits under.
        for (p, row), (c1, c2) in sorted(LEAD_ROWS.items()):
            if p not in products:
                continue
            w1, w2 = LEAD_WORST[(p, row)]
            ovr = LEAD_OVR.get((p, row), 0)
            n = cens[p]
            bb1, bb2 = pred[row]['p'][p]
            w.writerow({
                'product': p, 'row': f'{row}@{LEAD_FAMILY}',
                'source': f'measured ({LEAD_FAMILY})',
                'ch': sizes[p]['ch'], 'aux': sizes[p]['aux'],
                'fx': sizes[p]['fx'],
                'product_id': sizes[p]['product_id'],
                'chip1_built_pct': f'{bb1:.2f}',
                'chip2_built_pct': f'{bb2:.2f}',
                'chan_mask': f'0x{sizes[p]["chan_mask"]:08X}',
                'aux_mask': f'0x{sizes[p]["aux_mask"]:08X}',
                'mtx_mask': '0x%08X' % ((1 << sizes[p]['mtx_run']) - 1),
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
                'note': LEAD_NOTE.get((p, row), '')
                        + (f'; {ovr} missed blocks' if ovr else ''),
            })
    print(f'wrote {path}')


def score_measured(got, pred, pred_worst):
    """Gate 2: the delta between construction and measurement, per row.

    For an ANCHOR (a product `ROW_ANCHOR[row]` names) this is a control,
    not a test: the construction is FIT ON this row's own measurement, so
    a non-zero delta there is the fit disagreeing with the data it was
    built from. Before S81-Q1(a) the D24/D32 anchors were S27 numbers
    scored against S80 measurements — two different sessions — which is
    why they failed as controls (S80 report §5/§7, +43 to +85 points).
    Re-anchored, an anchor row's delta is small by construction (near
    zero with two anchors, a small least-squares residual with three or
    four) — which is WEAKER evidence than a control that passes on data
    it was not fit on. Said here, not just implied by a small number.
    """
    print()
    print('CONSTRUCTION vs MEASUREMENT  (delta = measured - built)')
    print(f'{"product":8}{"row":20}{"c1 built":>10}{"c1 meas":>9}{"Δ":>8}'
          f'{"c2 built":>11}{"c2 meas":>9}{"Δ":>8}  ovr  anchor?')
    for p in sorted(got, key=lambda q: int(q[1:])):
        for row in ROW_ORDER:
            if row not in got[p]:
                continue
            b1, b2 = pred[row]['p'][p]
            m = got[p][row]
            m1, m2 = m['1'][0], m['2'][0]
            ovr = m['1'][2] + m['2'][2]
            ra = ROW_ANCHOR[row]
            tag = (f"ANCHOR ({ra['session']} {ra['date']}) — control, "
                   f"passes by construction" if p in ra['products'] else '')
            print(f'{p:8}{row:20}{b1:>10.2f}{m1:>9.2f}{m1 - b1:>+8.2f}'
                  f'{b2:>11.2f}{m2:>9.2f}{m2 - b2:>+8.2f}  {ovr!s:<4} {tag}')


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
    all_anchors = sorted({p for ra in ROW_ANCHOR.values()
                          for p in ra['products']})
    missing = [p for p in all_anchors if p not in sizes]
    if missing:
        _, sizes_all, _, _ = collect(sorted(set(products) | set(missing)))
        sizes.update({p: sizes_all[p] for p in missing})
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
