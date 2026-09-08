#!/usr/bin/env python3
"""gen_dsp.py — §17 canonical build tool for D32 DSP.

Reads:
  - SHARC/dsp.csv       — packed SPI address assignments from gen_dsp_csv.py
  - ../MX/_matrix.csv   — existing cell definitions for backfill

Produces:
  1. ../MX/_matrix.csv backfill  — DspSpi, DspPage, DspAdd, DspAddHex, ramp metadata
  2. ghost_cells.h               — C struct array for H1S1 MCU firmware
  3. SHARC/src/dsp_params.asm    — SPI dispatch tables + .EXTERN declarations
  4. dsp_address_map.md          — human-readable address map

Usage:
    python3 gen_dsp.py [--dry-run] [--force]
"""

import argparse
import csv
import os
import re
import sys
from collections import OrderedDict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT  = os.path.join(SCRIPT_DIR, '..', '..', '..')

# THE AUDIO BLOCK SIZE IS NOT A CONSTANT OF THIS FILE. The ramp engine
# advances once per BLOCK, so a ramp profile's frame count is
# ms / (BLOCK / 48000). This file used to divide by a hardcoded 0.667 ms
# -- the frame period at BLOCK=32 -- and so baked ramp_up_frames /
# ramp_down_frames into ghost_cells.c four times too SHORT at the ruled
# BLOCK=8 operating point (review finding D10). BLOCK lives in
# tools/dsp/dsp_codegen.py and nowhere else; import it rather than
# restate it, and fail loudly if the import breaks -- a silently wrong
# ramp table is exactly what this finding was.
sys.path.insert(0, os.path.join(REPO_ROOT, 'tools', 'dsp'))
try:
    from dsp_codegen import BLOCK as DSP_BLOCK, FRAME_MS, ms_to_frames
    import master_names
except ImportError as exc:                       # no-fallback policy
    raise SystemExit(
        f'gen_dsp.py: cannot import the audio block size from '
        f'tools/dsp/dsp_codegen.py ({exc}). The ramp frame counts in '
        f'ghost_cells.c are derived from it; refusing to generate with a '
        f'guessed block size.')
DSP_CSV    = os.path.join(SCRIPT_DIR, 'SHARC', 'dsp.csv')
MATRIX_CSV = os.path.join(SCRIPT_DIR, '..', 'MX', '_matrix.csv')
MCU_ONLY_PREFIXES_FILE = os.path.join(REPO_ROOT, 'mcu-only-prefixes.txt')
DEFS_LOCK = os.path.join(REPO_ROOT, 'defs.lock')


def _contract_pin():
    """The contract version defs.lock pins, for the messages that depend on
    it. The Rtg alias table below is a statement about this pin."""
    for line in open(DEFS_LOCK, encoding='utf-8'):
        if line.startswith('CONTRACT_VERSION='):
            return line.split('=', 1)[1].strip()
    raise SystemExit('gen_dsp.py: defs.lock carries no CONTRACT_VERSION')


CONTRACT_PIN = _contract_pin()


def load_mcu_only_prefixes():
    with open(MCU_ONLY_PREFIXES_FILE, encoding='utf-8') as f:
        return tuple(line.split('#', 1)[0].strip() for line in f
                     if line.split('#', 1)[0].strip())

NODES_DIR_C1       = os.path.join(SCRIPT_DIR, 'SHARC', 'src', 'chip1', 'nodes')
NODES_DIR_C2       = os.path.join(SCRIPT_DIR, 'SHARC', 'src', 'chip2', 'nodes')
OUT_PARAMS_C1      = os.path.join(SCRIPT_DIR, 'SHARC', 'src', 'chip1', 'dsp_params.asm')
OUT_PARAMS_C2      = os.path.join(SCRIPT_DIR, 'SHARC', 'src', 'chip2', 'dsp_params.asm')
OUT_GHOST_H        = os.path.join(SCRIPT_DIR, 'ghost_cells.h')
OUT_GHOST_H_H1S1   = os.path.join(SCRIPT_DIR, '..', 'FW', 'H1S1', 'Core', 'Inc', 'ghost_cells.h')
OUT_GHOST_C_H1S1   = os.path.join(SCRIPT_DIR, '..', 'FW', 'H1S1', 'Core', 'Src', 'ghost_cells.c')
OUT_MX_DSP_MAP_H   = os.path.join(SCRIPT_DIR, '..', 'FW', 'H1S1', 'Core', 'Inc', 'mx_dsp_map.h')
OUT_ADDR_MAP       = os.path.join(SCRIPT_DIR, 'dsp_address_map.md')

# Guarded compatibility path for future Group GEQ rollout.
# Default remains off to preserve current behavior.

# ---------------------------------------------------------------------------
# §3b Ramp profile presets
# ---------------------------------------------------------------------------
RAMP_PROFILES = {
    '':           {'mode': 'Instant',      'up_ms':  0, 'down_ms':  0, 'curve': 'Linear', 'scope': 'Scalar',          'id': 0},
    'InstantCtl': {'mode': 'Instant',      'up_ms':  0, 'down_ms':  0, 'curve': 'Linear', 'scope': 'Scalar',          'id': 0},
    'GainFast':   {'mode': 'Slew',         'up_ms':  3, 'down_ms':  8, 'curve': 'Exp',    'scope': 'Scalar',          'id': 1},
    'GainSafe':   {'mode': 'Slew',         'up_ms': 10, 'down_ms': 30, 'curve': 'Exp',    'scope': 'Scalar',          'id': 2},
    'EqSafe':     {'mode': 'LinearFrames', 'up_ms': 12, 'down_ms': 12, 'curve': 'Linear', 'scope': 'CoeffSetAtomic', 'id': 3},
    'DynSafe':    {'mode': 'LinearFrames', 'up_ms':  6, 'down_ms': 20, 'curve': 'Exp',    'scope': 'Scalar',          'id': 4},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def cn(cat, inst, suffix, fun):
    """Build _Cell name, e.g. Chan001EqFreq002."""
    return f'{cat}{inst:03d}{suffix}{fun:03d}'


# ---------------------------------------------------------------------------
# Names come from the masters, and only from the masters
# ---------------------------------------------------------------------------
# Until defs-v2026.09.08 this file carried a rename table: the pinned
# `_matrix.csv` spelled the routing cells `Chan001RtgMute001` and the
# meters `AaChan001Mtr001`, while the masters had moved to
# `Chan001Mute001` and `Chan001Mtr001`, so every lookup tried two names.
# The pin has advanced past the rename and the table is GONE -- a
# generated cell now resolves against the matrix by its own name or not
# at all, and a name this generator emits that the masters do not carry
# is reported by validate() rather than aliased into one that fits.

_CELL_SPLIT = master_names.CELL_RE


def _matrix_key(cell_name, matrix_names):
    """The _matrix.csv row for a generated cell, or None if it has none."""
    return cell_name if cell_name in matrix_names else None


# Cell families the HOST owns outright: the DSP is given no address for
# them and no line of the kernel reads them. Collected from the
# `host_cells=` param on the nodes that used to carry them, so dsp.csv is
# the single source and this file only reports what it found.
host_managed = {}          # family suffix -> set of node ids that declared it


def read_dsp_csv():
    """Read dsp.csv and return list of dicts."""
    with open(DSP_CSV, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def read_matrix_csv():
    """Read _matrix.csv and return (header, list of OrderedDict rows)."""
    with open(MATRIX_CSV, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header = [h for h in reader.fieldnames if h and h.strip()]
        rows = [OrderedDict(r) for r in reader]
    return header, rows


def parse_params(cell):
    """Parse semicolon-separated key=value node params from dsp.csv."""
    cell = (cell or '').strip().strip('"')
    if not cell:
        return {}
    params = {}
    for pair in cell.split(';'):
        pair = pair.strip()
        if '=' in pair:
            k, v = pair.split('=', 1)
            params[k.strip()] = v.strip()
    return params


# ---------------------------------------------------------------------------
# Cell + Dispatch data collectors
# ---------------------------------------------------------------------------
# cell_map:  cell_name -> {chip, spi_page, spi_addr, table, ramp_profile, notes}
cell_map = {}

# dispatch:  (chip, spi_addr) -> (asm_symbol, comment)
dispatch = {}

# extern set: all unique ASM symbols needed in dsp_params.asm
externs = set()


# Graph nodes that reach no master cell category at all:
#   id -> (node type, reason)
# They still get dispatch entries (the SPI handler must answer for every
# address the graph builds), but they emit no cells.
#
# A NODE THAT HOLDS AN SPI ADDRESS AND REACHES NO CELL MUST SAY WHY. The
# S1 session could only report eight such nodes as a count and a list; the
# dispatch that produced this file asks for the reason next to each one,
# and the way to keep a reason honest is to make the generator refuse to
# run without it. `_UNREACHED_REASONS` is matched in order against the
# node id; the first hit wins; no hit is an error, not a blank cell.
uncatalogued_nodes = {}

_UNREACHED_REASONS = [
    # RETIRED BY RULING (PW confirmed 2026-09-08, S1-1). The sub is a
    # post-crossover OUTPUT strip of the main mix and there is no separate
    # sub mix bus, so the whole C2_SUB_* chain -- fed from BUS_SUB, out on
    # NET_OUT_01 -- is the old model. The nodes stay in the graph and keep
    # their addresses this session; each says what replaces it.
    (re.compile(r'^C2_SUB_FDR$'),
     'retired by ruling (S1-1): sub bus fader. Chain 4 has NO fader node, '
     'so MainSub001Level001/Mute001 reach no address — open question Q1.'),
    (re.compile(r'^C2_SUB_EQ$'),
     'retired by ruling (S1-1): replaced by C2_MAIN_OEQ_04.'),
    (re.compile(r'^C2_SUB_COMP$'),
     'retired by ruling (S1-1): replaced by C2_MAIN_OCOMP_04.'),
    (re.compile(r'^C2_SUB_LIM$'),
     'retired by ruling (S1-1): replaced by C2_MAIN_OLIM_04.'),
    (re.compile(r'^C2_SUB_DLY$'),
     'retired by ruling (S1-1): sub bus delay. Chain 4 has NO delay node, '
     'so MainSub001Delay001 reaches no address — open question Q1.'),
    (re.compile(r'^C2_MTR_SUB$'),
     'retired by ruling (S1-1): replaced by C2_MTR_MAIN_04.'),
    # OLD MODEL, not named by the ruling but the same change. The masters
    # give `Main[1-1]` no dynamics at all: `main.comp` and `main.lim` gate
    # Comp/Limiter on the four OUTPUT strips (defs/tools/def_master.py
    # FUNC_GATES["main"]), which the per-output chains serve.
    (re.compile(r'^C2_MAIN_COMP$'),
     'old model: dynamics on the stereo mix bus; replaced by '
     'C2_MAIN_OCOMP_01..04, one per output strip.'),
    (re.compile(r'^C2_MAIN_LIM$'),
     'old model: dynamics on the stereo mix bus; replaced by '
     'C2_MAIN_OLIM_01..04, one per output strip.'),
]


def unreached_reason(nid):
    """Why this node holds an address no master cell reaches. No-fallback."""
    for pattern, reason in _UNREACHED_REASONS:
        if pattern.match(nid):
            return reason
    sys.exit(f'ERROR: node {nid!r} holds an SPI address and reaches no '
             f'master cell, and _UNREACHED_REASONS in gen_dsp.py does not '
             f'say why. Add the reason (or map the node to a strip).')


# The node currently being expanded, so add_cell() can record WHICH graph
# node owns a cell's address without threading it through sixty call
# sites. dsp.csv is a proposal the hub lands into defs; a row that cannot
# say where its address came from cannot be checked against the graph.
_current_node = {'id': '', 'type': ''}


def add_cell(cell_name, chip, spi_page, spi_addr, table='', ramp_profile='', notes=''):
    # A node with no master category is expanded with an empty category, so
    # cn() hands us `000CompAtt001` -- not a cell, but the graph reaching
    # past the product definition. Drop it here rather than let it into
    # cell_map, ghost_cells.c and the address map, where it would read as a
    # real address the host can write. validate() names the nodes.
    if not _CELL_SPLIT.match(cell_name):
        return
    cell_map[cell_name] = {
        'chip': int(chip),
        'spi_page': int(spi_page),
        'spi_addr': int(spi_addr),
        'table': table,
        'ramp_profile': ramp_profile,
        'notes': notes,
        'node': _current_node['id'],
        'node_type': _current_node['type'],
    }


def add_dispatch(chip, spi_addr, asm_symbol, comment=''):
    """Register a dispatch table entry. asm_symbol=None for MCU-only or unused."""
    dispatch[(int(chip), int(spi_addr))] = (asm_symbol, comment)
    if asm_symbol:
        # Extract the base symbol (before any + offset)
        base = asm_symbol.split('+')[0].strip().lstrip('_')
        externs.add('_' + base if not asm_symbol.startswith('_') else asm_symbol.split('+')[0].strip())


def add_dispatch_block(chip, base_addr, asm_array_sym, count, comment_prefix=''):
    """Register dispatch for a contiguous block of words (e.g. coefficient array)."""
    for i in range(count):
        sym = f'{asm_array_sym} + {i}' if i > 0 else asm_array_sym
        add_dispatch(chip, base_addr + i, sym, f'{comment_prefix}[{i}]' if comment_prefix else '')


# ---------------------------------------------------------------------------
# Per-node-type expansion functions
#
# Each function takes (node_dict, category, instance) and populates
# cell_map and dispatch.
# ---------------------------------------------------------------------------

def _parse_node(node):
    chip = int(node['chip'])
    spi_page = int(node['spi_page'])
    spi_addr = int(node['spi_addr'])
    nid = node['id']
    ramp = node.get('ramp_profile', '')
    return chip, spi_page, spi_addr, nid, ramp


# ── GAIN ──────────────────────────────────────────────────────────────────
def expand_gain(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 4 SPI words: gain_coeff, polarity, phantom, input_sel
    add_cell(cn(cat, inst, 'Gain', 1), chip, pg, base,
             '0=0/127=60/[Lin]', 'GainFast')
    add_dispatch(chip, base, f'_gain_coeff_{nid}', f'{nid} gain coeff')

    add_cell(cn(cat, inst, 'Pol', 1), chip, pg, base + 1, '', 'InstantCtl')
    add_dispatch(chip, base + 1, f'_polarity_{nid}', f'{nid} polarity')

    add_cell(cn(cat, inst, 'Phantom', 1), chip, pg, base + 2, '', 'InstantCtl',
             notes='MCU hardware control')
    add_dispatch(chip, base + 2, None, 'phantom (MCU-only)')

    add_cell(cn(cat, inst, 'InputSel', 1), chip, pg, base + 3, '', 'InstantCtl',
             notes='MCU hardware control')
    add_dispatch(chip, base + 3, None, 'input_sel (MCU-only)')


# ── HPF_LPF ──────────────────────────────────────────────────────────────
def expand_hpf_lpf(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 12 SPI words: HPF biquad[5] + swap_pending + LPF biquad[5] + swap_pending
    add_cell(cn(cat, inst, 'EqHpf', 1), chip, pg, base,
             '0=20/64=1000/[Log]', 'EqSafe', notes='HPF biquad coeff base')
    add_dispatch_block(chip, base, f'_hpf_coeffs_next_{nid}', 5, f'{nid} HPF coeff')
    add_dispatch(chip, base + 5, f'_hpf_swap_pending_{nid}', f'{nid} HPF swap trigger')

    add_cell(cn(cat, inst, 'EqLpf', 1), chip, pg, base + 6,
             '0=1000/127=20000/[Log]', 'EqSafe', notes='LPF biquad coeff base')
    add_dispatch_block(chip, base + 6, f'_lpf_coeffs_next_{nid}', 5, f'{nid} LPF coeff')
    add_dispatch(chip, base + 11, f'_lpf_swap_pending_{nid}', f'{nid} LPF swap trigger')

    # MCU-only cells (no SPI address — slope determines coefficients)
    add_cell(cn(cat, inst, 'EqHpfSlope', 1), chip, pg, base,
             '', 'InstantCtl', notes='MCU-only; shares base addr with EqHpf')


# ── EQ_BIQUAD ────────────────────────────────────────────────────────────
def expand_eq_biquad(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 24 SPI words: coeffs_next[20] + swap_pending + EqOn + spare×2
    bands = 4

    # Per-band cells all point to band's coefficient base
    for b in range(1, bands + 1):
        band_base = base + (b - 1) * 5
        tbl_freq = {1: '0=20/254=200/[Log]', 2: '0=100/254=1000/[Log]',
                    3: '0=800/254=5000/[Log]', 4: '0=3000/254=20000/[Log]'}
        add_cell(cn(cat, inst, 'EqFreq', b), chip, pg, band_base,
                 tbl_freq.get(b, ''), 'EqSafe', notes=f'Band {b} coeff base')
        add_cell(cn(cat, inst, 'EqGain', b), chip, pg, band_base,
                 '0=-15/60=15/[Lin]', 'EqSafe', notes=f'Band {b} (same base)')
        add_cell(cn(cat, inst, 'EqQ', b), chip, pg, band_base,
                 '0=0.1/14=10/[Log]', 'EqSafe', notes=f'Band {b} (same base)')

    # HPF cell — for non-channel contexts (Aux/Grp/Sub/Main) where there's
    # no separate HPF_LPF node, HPF is band-1 of the EQ biquad.
    # Main output zones allow any band as HPF (fun 1-4); others only band 1.
    if cat not in ('Chan', ''):
        if cat == 'Main':
            for b in range(1, bands + 1):
                band_base = base + (b - 1) * 5
                add_cell(cn(cat, inst, 'EqHpf', b), chip, pg, band_base,
                         '0=20/64=1000/[Log]', 'EqSafe',
                         notes=f'HPF via EQ band {b}')
        else:
            add_cell(cn(cat, inst, 'EqHpf', 1), chip, pg, base,
                     '0=20/64=1000/[Log]', 'EqSafe', notes='HPF via EQ band 1')

    # Shelf cells (band 1 and 4)
    add_cell(cn(cat, inst, 'EqShelf', 1), chip, pg, base, '', 'InstantCtl',
             notes='Shelf mode band 1')
    add_cell(cn(cat, inst, 'EqShelf', 2), chip, pg, base + 15, '', 'InstantCtl',
             notes='Shelf mode band 4')

    # EqOn
    add_cell(cn(cat, inst, 'EqOn', 1), chip, pg, base + 21, '', 'InstantCtl')

    # Dispatch: coefficients staging buffer
    add_dispatch_block(chip, base, f'_eq_coeffs_next_{nid}', 20, f'{nid} EQ coeff')
    add_dispatch(chip, base + 20, f'_eq_swap_pending_{nid}', f'{nid} EQ swap trigger')
    # EqOn dispatch — if the node has an _eq_on var, use it; else null
    add_dispatch(chip, base + 21, None, f'{nid} EqOn (MCU-managed)')
    add_dispatch(chip, base + 22, None, f'{nid} spare')
    add_dispatch(chip, base + 23, None, f'{nid} spare')


# ── GATE ──────────────────────────────────────────────────────────────────
def expand_gate(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 16 SPI words
    params = [
        ('GateOn',        0,  '',                        'InstantCtl', f'_gate_on_{nid}'),
        ('GateThr',       1,  '0=-80/127=0/[Lin]',      'DynSafe',   f'_gate_threshold_{nid}'),
        ('GateAtt',       2,  '0=0.1/127=250/[Log]',    'DynSafe',   f'_gate_attack_{nid}'),
        ('GateHold',      3,  '0=0/127=2000/[Log]',     'DynSafe',   f'_gate_hold_{nid}'),
        ('GateRel',       4,  '0=50/127=5000/[Log]',    'DynSafe',   f'_gate_release_{nid}'),
        ('GateRng',       5,  '0=0/127=60/[Lin]',       'DynSafe',   f'_gate_range_{nid}'),
        ('GateKey',       6,  '',                        'InstantCtl', f'_gate_key_src_{nid}'),
        ('GateDetSrc',    7,  '',                        'InstantCtl', f'_gate_det_src_{nid}'),
        ('GateFilterOn',  8,  '',                        'InstantCtl', f'_gate_filter_on_{nid}'),
    ]
    for suffix, off, tbl, rp, asm in params:
        add_cell(cn(cat, inst, suffix, 1), chip, pg, base + off, tbl, rp)
        add_dispatch(chip, base + off, asm, f'{nid} {suffix}')

    # Sidechain filter coefficients: HPF[5] + LPF[5] = 10 words at offsets 9-13, 14-..
    # But only 16 - 9 = 7 words left. Actually: filter HPF freq/LPF freq/Q are MCU-computed.
    # Gate filter uses direct biquad storage, not staging buffer.
    add_cell(cn(cat, inst, 'GateFilterHpf', 1), chip, pg, base + 9,
             '0=20/64=1000/[Log]', 'InstantCtl', notes='Sidechain HPF')
    add_dispatch_block(chip, base + 9, f'_gate_filter_hpf_{nid}', 5, f'{nid} GateFilter HPF')

    add_cell(cn(cat, inst, 'GateFilterLpf', 1), chip, pg, base + 14,
             '0=500/127=20000/[Log]', 'InstantCtl', notes='Sidechain LPF coeff base')
    add_dispatch(chip, base + 14, f'_gate_filter_lpf_{nid}', f'{nid} GateFilter LPF[0]')
    add_dispatch(chip, base + 15, f'_gate_filter_lpf_{nid} + 1', f'{nid} GateFilter LPF[1]')
    # Note: only 2 of 5 LPF coefficients fit in 16 words.
    # The Q cell is MCU-side (computes coefficients):
    add_cell(cn(cat, inst, 'GateFilterQ', 1), chip, pg, base + 9,
             '0=0.1/14=10/[Log]', 'InstantCtl', notes='MCU-computed, shares HPF base')


# ── COMPRESSOR ────────────────────────────────────────────────────────────
def expand_compressor(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 20 SPI words
    params = [
        ('CompOn',        0,  '',                        'InstantCtl', f'_comp_on_{nid}'),
        ('CompThr',       1,  '0=-60/140=10/[Lin]',     'DynSafe',   f'_comp_threshold_{nid}'),
        ('CompRat',       2,  '0=1/127=30/[Log]',       'DynSafe',   f'_comp_ratio_{nid}'),
        ('CompAtt',       3,  '0=0/254=250/[Log]',      'DynSafe',   f'_comp_attack_{nid}'),
        ('CompRel',       4,  '0=5/254=5000/[Log]',     'DynSafe',   f'_comp_release_{nid}'),
        ('CompMake',      5,  '0=0/127=20/[Lin]',       'GainFast',  f'_comp_makeup_{nid}'),
        ('CompKnee',      6,  '',                        'InstantCtl', f'_comp_knee_{nid}'),
        ('CompPar',       7,  '0=0/127=100/[Lin]',      'GainFast',  f'_comp_parallel_{nid}'),
        ('CompType',      8,  '',                        'InstantCtl', f'_comp_type_{nid}'),
        ('CompKey',       9,  '',                        'InstantCtl', f'_comp_key_src_{nid}'),
        ('CompDetSrc',   10,  '',                        'InstantCtl', f'_comp_det_src_{nid}'),
        ('CompLimMode',  11,  '',                        'InstantCtl', f'_comp_lim_mode_{nid}'),
        ('CompEqPos',    12,  '',                        'InstantCtl', f'_comp_eq_pos_{nid}'),
        ('CompFilterOn', 13,  '',                        'InstantCtl', f'_comp_filter_on_{nid}'),
    ]
    for suffix, off, tbl, rp, asm in params:
        add_cell(cn(cat, inst, suffix, 1), chip, pg, base + off, tbl, rp)
        add_dispatch(chip, base + off, asm, f'{nid} {suffix}')

    # Sidechain filter coefficients: HPF[5]+LPF[5] at offsets 14-18, 19 only 1 left
    add_cell(cn(cat, inst, 'CompFilterHpf', 1), chip, pg, base + 14,
             '0=20/64=1000/[Log]', 'InstantCtl')
    add_dispatch_block(chip, base + 14, f'_comp_filter_coeffs_{nid}', 5, f'{nid} CompFilter HPF')
    add_dispatch(chip, base + 19, f'_comp_filter_coeffs_{nid} + 5', f'{nid} CompFilter LPF[0]')

    add_cell(cn(cat, inst, 'CompFilterLpf', 1), chip, pg, base + 14,
             '0=500/127=20000/[Log]', 'InstantCtl', notes='MCU-computed, shares filter base')
    add_cell(cn(cat, inst, 'CompFilterQ', 1), chip, pg, base + 14,
             '0=0.1/14=10/[Log]', 'InstantCtl', notes='MCU-computed')


# ── TUBE_SAT (placeholder for future channel plugins) ─────────────────────
def expand_tube_sat(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 2 SPI words: on + saturation
    add_cell(cn(cat, inst, 'TubeOn', 1), chip, pg, base, '', 'InstantCtl')
    add_dispatch(chip, base, f'_tube_on_{nid}', f'{nid} on')

    add_cell(cn(cat, inst, 'TubeSat', 1), chip, pg, base + 1,
             '0=0/127=100/[Lin]', 'GainFast')
    add_dispatch(chip, base + 1, f'_tube_sat_{nid}', f'{nid} saturation')


# ── DELAY ─────────────────────────────────────────────────────────────────
def expand_delay(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    params = parse_params(node.get('params', ''))
    max_ms = params.get('max_ms', '250')
    # 2 SPI words: delay_ms + pool_slot
    add_cell(cn(cat, inst, 'Delay', 1), chip, pg, base,
             f'0=0/127={max_ms}/[Log]', 'InstantCtl')
    add_dispatch(chip, base, f'_dly_read_offset_{nid}', f'{nid} delay offset')
    add_dispatch(chip, base + 1, f'_dly_pool_slot_{nid}', f'{nid} pool_slot')


# ── FADER_PAN ─────────────────────────────────────────────────────────────
def expand_fader_pan(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 4 SPI words: level + pan + mute + reserved (see below)

    # Level/Pan/Mute, the master spelling since the 2026-08-25 Rtg
    # retirement and the only one this generator has ever emitted.
    level_suffix = 'Level'
    pan_suffix = 'Pan'
    mute_suffix = 'Mute'

    add_cell(cn(cat, inst, level_suffix, 1), chip, pg, base,
             'dB:Off:-50@31:-30@63:-10@127:10', 'GainFast')
    add_dispatch(chip, base, f'_fdr_level_{nid}', f'{nid} level')

    if cat in ('Chan', 'Aux'):
        add_cell(cn(cat, inst, pan_suffix, 1), chip, pg, base + 1,
                 'Pan:dB:0:Off', 'GainFast')
        add_dispatch(chip, base + 1, f'_fdr_pan_{nid}', f'{nid} pan')
    else:
        add_dispatch(chip, base + 1, f'_fdr_pan_{nid}', f'{nid} pan (unused)')

    add_cell(cn(cat, inst, mute_suffix, 1), chip, pg, base + 2, '', 'InstantCtl')
    add_dispatch(chip, base + 2, f'_fdr_mute_{nid}', f'{nid} mute')

    # Dca and DcaOn are HOST-MANAGED (PW ruling 2026-08-30, Q2 closed).
    # The CM4 control daemon owns the DCA fold -- effective fader = fader
    # dB + DCA dB, mutes OR-ed -- and writes the RESULT through the fader
    # level target this node already ramps. The DSP is therefore given no
    # address for either cell and no line of the kernel reads them: D57's
    # `_fdr_dca_sel_` store and the `_fdr_dca_gain_` multiply are both
    # GONE rather than left dormant, which is what the ruling says.
    #
    # The word is RESERVED, not reclaimed. Compacting it would move every
    # address after it in a 144-word channel block -- the whole map, the
    # MCU's ghost table and every stored golden -- to save one word of a
    # page that is nowhere near full.
    for fam in parse_params(node.get('params', '')).get('host_cells', '').split(','):
        if fam.strip():
            host_managed.setdefault(fam.strip(), set()).add(nid)
    add_dispatch(chip, base + 3, None, f'{nid} reserved (Dca host-managed)')


# ── ROUTING (channel strip fan-out) ──────────────────────────────────────
def expand_routing(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 60 SPI words: main_on + sub_on + grp_on×4 + aux_on×12 + aux_send×12
    # + aux_pick×12 + fx_on×6 + fx_send×6 + fx_pick×6
    off = 0
    add_cell(cn(cat, inst, 'MainOn', 1), chip, pg, base + off, '', 'InstantCtl')
    add_dispatch(chip, base + off, f'_rtg_main_on_{nid}', f'{nid} MainOn')
    off += 1

    add_cell(cn(cat, inst, 'CtrOn', 1), chip, pg, base + off, '', 'InstantCtl')
    add_dispatch(chip, base + off, f'_rtg_sub_on_{nid}', f'{nid} SubOn')
    off += 1

    for g in range(1, 5):
        add_cell(cn(cat, inst, 'GrpOn', g), chip, pg, base + off, '', 'InstantCtl')
        add_dispatch(chip, base + off, f'_rtg_grp_on_{nid} + {g-1}', f'{nid} GrpOn[{g}]')
        off += 1

    for a in range(1, 13):
        add_cell(cn(cat, inst, 'AuxOn', a), chip, pg, base + off, '', 'InstantCtl')
        add_dispatch(chip, base + off, f'_rtg_aux_on_{nid} + {a-1}', f'{nid} AuxOn[{a}]')
        off += 1

    for a in range(1, 13):
        add_cell(cn(cat, inst, 'AuxSend', a), chip, pg, base + off,
                 'dB:Off:-50@31:-30@63:-10@127:0', 'GainFast')
        add_dispatch(chip, base + off, f'_rtg_aux_send_{nid} + {a-1}', f'{nid} AuxSend[{a}]')
        off += 1

    for a in range(1, 13):
        add_cell(cn(cat, inst, 'AuxPick', a), chip, pg, base + off,
                 '', 'InstantCtl', notes='Pickoff: 0=PreEQ 1=PostEQ 2=PreFdr 3=PostFdr')
        add_dispatch(chip, base + off, f'_rtg_aux_pick_{nid} + {a-1}', f'{nid} AuxPick[{a}]')
        off += 1

    for x in range(1, 7):
        add_cell(cn(cat, inst, 'FxOn', x), chip, pg, base + off, '', 'InstantCtl')
        add_dispatch(chip, base + off, f'_rtg_fx_on_{nid} + {x-1}', f'{nid} FxOn[{x}]')
        off += 1

    for x in range(1, 7):
        add_cell(cn(cat, inst, 'FxSend', x), chip, pg, base + off,
                 'dB:Off:-50@31:-30@63:-10@127:0', 'GainFast')
        add_dispatch(chip, base + off, f'_rtg_fx_send_{nid} + {x-1}', f'{nid} FxSend[{x}]')
        off += 1

    for x in range(1, 7):
        add_cell(cn(cat, inst, 'FxPick', x), chip, pg, base + off,
                 '', 'InstantCtl', notes='Pickoff: 0=PreEQ 1=PostEQ 2=PreFdr 3=PostFdr')
        add_dispatch(chip, base + off, f'_rtg_fx_pick_{nid} + {x-1}', f'{nid} FxPick[{x}]')
        off += 1


# ── GEQ ──────────────────────────────────────────────────────────────────
def expand_geq(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 28 SPI words: gains[28] staging buffer → crossfade swap
    for b in range(1, 29):
        add_cell(cn(cat, inst, 'Geq', b), chip, pg, base + (b - 1),
                 '0=-12/127=12/[Lin]', 'EqSafe')

    add_dispatch_block(chip, base, f'_geq_coeffs_next_{nid}', 28, f'{nid} GEQ coeff')


# ── ANTI_FB ──────────────────────────────────────────────────────────────
def expand_anti_fb(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 24 SPI words: on(1) + ctrl_on(1) + notch_freq[6] + notch_gain[6] + notch_q[6] + coeffs staging
    off = 0
    add_cell(cn(cat, inst, 'AntiFbOn', 1), chip, pg, base + off, '', 'InstantCtl')
    add_dispatch(chip, base + off, f'_afb_on_{nid}', f'{nid} AntiFbOn')
    off += 1

    add_cell(cn(cat, inst, 'AntiFbCtrlOn', 1), chip, pg, base + off, '', 'InstantCtl')
    add_dispatch(chip, base + off, f'_afb_ctrl_on_{nid}', f'{nid} AntiFbCtrlOn')
    off += 1

    for n in range(1, 7):
        add_cell(cn(cat, inst, 'AntiFbNotchFreq', n), chip, pg, base + off,
                 '0=40/127=12000/[Log]', 'InstantCtl')
        add_dispatch(chip, base + off, f'_afb_notch_freq_{nid} + {n-1}', f'{nid} NotchFreq[{n}]')
        off += 1

    for n in range(1, 7):
        add_cell(cn(cat, inst, 'AntiFbNotchGain', n), chip, pg, base + off,
                 '0=-18/127=0/[Lin]', 'InstantCtl')
        add_dispatch(chip, base + off, f'_afb_notch_gain_{nid} + {n-1}', f'{nid} NotchGain[{n}]')
        off += 1

    for n in range(1, 7):
        add_cell(cn(cat, inst, 'AntiFbNotchQ', n), chip, pg, base + off,
                 '0=1/127=20/[Log]', 'InstantCtl')
        add_dispatch(chip, base + off, f'_afb_notch_q_{nid} + {n-1}', f'{nid} NotchQ[{n}]')
        off += 1

    # Remaining words → coefficient staging
    while off < 24:
        add_dispatch(chip, base + off, None, f'{nid} spare coeff [{off}]')
        off += 1


# ── LIMITER ──────────────────────────────────────────────────────────────
def expand_limiter(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 4 SPI words: on + threshold + attack + release
    params = [
        ('LimiterOn',   0, '',                     'InstantCtl', f'_lim_on_{nid}'),
        ('LimiterThr',  1, '0=-30/127=0/[Lin]',    'DynSafe',   f'_lim_threshold_{nid}'),
        ('LimiterAtt',  2, '0=0.1/127=100/[Log]',  'DynSafe',   f'_lim_attack_{nid}'),
        ('LimiterRel',  3, '0=5/127=2000/[Log]',   'DynSafe',   f'_lim_release_{nid}'),
    ]
    for suffix, off, tbl, rp, asm in params:
        add_cell(cn(cat, inst, suffix, 1), chip, pg, base + off, tbl, rp)
        add_dispatch(chip, base + off, asm, f'{nid} {suffix}')


# ── METER (read-only, DSP writes, host polls) ────────────────────────────
# WHAT A METER NODE ACTUALLY WRITES, which is not what `taps=` used to be
# read as. Every meter node meters ONE tap point and lays three float words
# at its base address (tools/dsp/dsp_codegen.py::gen_meter_fixed, and the
# node ASM's own comment "the host reaches the rest by offset"):
#
#     +0  _mtr_peak_<nid>   linear peak, the host contract
#     +1  _mtr_rms_<nid>    linear TRUE rms
#     +2  _mtr_gr_<nid>     gain reduction -- DECLARED AND NEVER WRITTEN
#     +3  _mtr_st_<nid>[4]  the meter's OWN state (pk_lo pk_hi ms_lo ms_hi)
#
# So `taps=` names METER WORDS, not tap points, and the two facts that
# follow are the reason this expander is a vocabulary rather than a pair of
# `in` tests:
#
#   * `taps=L;R` on the four post-crossover main-output meters claimed a
#     stereo pair. The nodes are ch_count=1 mono outputs and the masters
#     give MainL/MainR/MainCtr/MainSub one `Mtr[1-1]` each; the second
#     cell was the RMS word wearing an `R` label, and it is one of the 23
#     generated cells S1 found with no matrix row.
#   * `comp_gr` has NO WORD. The channel meter's fourth cell was being
#     given base+3, which is `_mtr_st[0]` -- the meter's internal peak-hold
#     state, not a compressor's gain reduction. A cell pointed at another
#     variable's scratch is not "reaching a DSP address"; CompMtr is
#     reported as unbacked instead, next to the gate_gr word that IS
#     declared and still is not written (recorded defect 4).
#
# The map is (cell suffix, fun, word offset, asm symbol suffix, note).
#
#   offset None    the word does not exist -- the tap is reported unbacked.
#   suffix None    the word EXISTS and is dispatched, and no product cell
#                  names it. This is the same shape FADER_PAN already uses
#                  for the pan word on a non-Chan/Aux strip: an address the
#                  SPI handler answers on with nothing in the masters
#                  pointing at it. Dropping the dispatch instead would take
#                  a real measurement away from the host to fix a labelling
#                  mistake, which is the wrong trade.
_METER_TAPS = {
    'peak':        ('Mtr',     1,    0, '_mtr_peak_', 'meter word +0: linear peak'),
    'post_trim':   ('Mtr',     1,    0, '_mtr_peak_', 'meter word +0: linear peak'),
    'post_fader':  ('Mtr',     2,    1, '_mtr_rms_',  'meter word +1: linear true RMS'),
    'rms':         (None,   None,    1, '_mtr_rms_',  'meter word +1: linear true RMS — dispatched; no cell names it'),
    'gate_gr':     ('GateMtr', 1,    2, '_mtr_gr_',   'meter word +2: gain reduction — declared, never written (defect 4)'),
    'comp_gr':     ('CompMtr', 1, None, None,         'no meter word exists; base+3 is the meter\'s own state array'),
}

# Meter taps a node declares that reach no DSP word: cell name -> reason.
unbacked_meter_cells = {}


def _parse_taps(raw):
    """The tap names a METER node declares.

    NOT parse_params(): `;` separates the taps as well as the key=value
    pairs, so parse_params('taps=post_trim;post_fader;gate_gr;comp_gr')
    returns {'taps': 'post_trim'} and three of the four words vanish
    without a word being said. The tap list runs to the end of the params
    or to the next `key=` token, whichever comes first.
    """
    raw = (raw or '').strip().strip('"')
    if 'taps=' not in raw:
        return []
    names = []
    for tok in raw.split('taps=', 1)[1].split(';'):
        tok = tok.strip()
        if not tok:
            continue
        if '=' in tok:              # the next key ends the tap list
            break
        names.append(tok)
    return names


def expand_meter(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # The layout is what dsp.csv's `taps=` declares, and ONLY that. This
    # used to test `cat == 'AaChan'`; the Aa sort prefix is gone from the
    # masters and a channel meter's cells now sit in `Chan`, which the
    # strip nodes also use -- so the category can no longer tell a
    # multi-word channel meter from a one-word bus meter, and the node's
    # own declaration always could. A METER that declares nothing is an
    # error rather than a guessed one-word default.
    names = _parse_taps(node.get('params', ''))
    if not names:
        sys.exit(f'ERROR: METER node {nid} declares no `taps=` — say which '
                 f'meter words it exposes (see _METER_TAPS in gen_dsp.py); '
                 f'refusing to guess a layout.')

    for tap in names:
        if tap not in _METER_TAPS:
            sys.exit(f'ERROR: METER node {nid} declares tap {tap!r}, which '
                     f'is not in _METER_TAPS — add it with the word it '
                     f'names, or fix the declaration.')
        suffix, fun, off, sym, note = _METER_TAPS[tap]
        if off is None:
            name = cn(cat, inst, suffix, fun)
            if _CELL_SPLIT.match(name):
                unbacked_meter_cells[name] = f'{nid} declares tap {tap!r}: {note}'
            continue
        if suffix is not None:
            add_cell(cn(cat, inst, suffix, fun), chip, pg, base + off,
                     '', '', notes=note)
        add_dispatch(chip, base + off, f'{sym}{nid}' if sym else None,
                     f'{nid} {tap}')


# ── TALKBACK ─────────────────────────────────────────────────────────────
def expand_talkback(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 4 words per talkback: on + gain + hpf_on + route[3]
    # (base is shared for both talk instances; each gets 4 words)
    off = 0
    add_cell(cn(cat, inst, 'On', 1), chip, pg, base + off, '', 'InstantCtl')
    add_dispatch(chip, base + off, f'_talk_on_{nid}', f'{nid} on')
    off += 1

    add_cell(cn(cat, inst, 'Gain', 1), chip, pg, base + off,
             '0=0/127=40/[Lin]', 'GainFast')
    add_dispatch(chip, base + off, f'_talk_gain_{nid}', f'{nid} gain')
    off += 1

    add_cell(cn(cat, inst, 'Hpf', 1), chip, pg, base + off, '', 'InstantCtl')
    add_dispatch(chip, base + off, f'_talk_hpf_on_{nid}', f'{nid} HPF on')
    off += 1

    for r in range(1, 4):
        if off < 4:
            add_cell(cn(cat, inst, 'Dest', r), chip, pg, base + off, '', 'InstantCtl')
            add_dispatch(chip, base + off, f'_talk_route_{nid} + {r-1}', f'{nid} route[{r}]')
            off += 1


# ── NOISE_GEN ────────────────────────────────────────────────────────────
def expand_noise_gen(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 4 words: on + level + hpf_on + route
    add_cell(cn(cat, inst, 'On', 1), chip, pg, base, '', 'InstantCtl')
    add_dispatch(chip, base, f'_noise_on_{nid}', f'{nid} on')

    add_cell(cn(cat, inst, 'Level', 1), chip, pg, base + 1,
             '0=-40/127=0/[Lin]', 'GainFast')
    add_dispatch(chip, base + 1, f'_noise_level_{nid}', f'{nid} level')

    add_cell(cn(cat, inst, 'Hpf', 1), chip, pg, base + 2, '', 'InstantCtl')
    add_dispatch(chip, base + 2, f'_noise_hpf_on_{nid}', f'{nid} HPF')

    add_dispatch(chip, base + 3, None, f'{nid} route bitmask')


# ── FX_ENGINE ────────────────────────────────────────────────────────────
def expand_fx_engine(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 24 SPI words: all FX parameters
    params = [
        ('On',          0,  '',                      'InstantCtl', f'_fx_on_{nid}'),
        ('Type',        1,  '',                      'InstantCtl', f'_fx_type_{nid}'),
        ('Decay',       2,  '0=0.1/127=10/[Log]',   'GainSafe',  f'_fx_decay_{nid}'),
        ('PreDelay',    3,  '0=0/127=100/[Lin]',     'InstantCtl', f'_fx_predelay_{nid}'),
        ('DelayTime',   4,  '0=1/127=1000/[Log]',   'InstantCtl', f'_fx_delay_ms_{nid}'),
        ('Feedback',    5,  '0=0/127=100/[Lin]',     'GainSafe',  f'_fx_feedback_{nid}'),
        ('Balance',     6,  '0=0/127=100/[Lin]',     'GainSafe',  None),
        ('Damp',        7,  '0=0/127=100/[Lin]',     'GainSafe',  f'_fx_damp_{nid}'),
        ('EqLo',        8,  '0=-6/127=6/[Lin]',     'EqSafe',    f'_fx_eq_lo_{nid}'),
        ('EqMid',       9,  '0=-6/127=6/[Lin]',     'EqSafe',    f'_fx_eq_mid_{nid}'),
        ('EqPresence', 10,  '0=-6/127=6/[Lin]',     'EqSafe',    f'_fx_eq_hi_{nid}'),
    ]
    for suffix, off, tbl, rp, asm in params:
        add_cell(cn(cat, inst, suffix, 1), chip, pg, base + off, tbl, rp)
        add_dispatch(chip, base + off, asm, f'{nid} {suffix}')

    # HPF coefficients [5] at offset 11-15
    add_cell(cn(cat, inst, 'EqHpf', 1), chip, pg, base + 11,
             '0=80/127=300/[Log]', 'EqSafe')
    add_dispatch_block(chip, base + 11, f'_fx_hpf_coeffs_{nid}', 5, f'{nid} FX HPF')

    # Modulation params
    more = [
        ('ModRate',     16, '0=0.1/127=10/[Log]',   'InstantCtl', f'_fx_mod_rate_{nid}'),
        ('ModLevel',    17, '0=0/127=100/[Lin]',     'GainSafe',  f'_fx_mod_level_{nid}'),
        ('LfoShape',    18, '',                      'InstantCtl', f'_fx_lfo_shape_{nid}'),
        ('StereoWidth', 19, '0=0/127=100/[Lin]',     'GainSafe',  f'_fx_width_{nid}'),
        ('Mix',         20, '0=0/127=100/[Lin]',     'GainSafe',  f'_fx_mix_{nid}'),
        ('DuckOn',      21, '',                      'InstantCtl', None),
        ('DuckSens',    22, '0=-30/127=0/[Lin]',     'DynSafe',   None),
    ]
    for suffix, off, tbl, rp, asm in more:
        add_cell(cn(cat, inst, suffix, 1), chip, pg, base + off, tbl, rp)
        add_dispatch(chip, base + off, asm, f'{nid} {suffix}')

    # Remaining slots spare
    add_dispatch(chip, base + 23, None, f'{nid} spare')


# ── CROSSOVER ────────────────────────────────────────────────────────────
def expand_crossover(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # From LDF: crossover has LP+HP biquad pairs with crossfade
    # Cells: CrossoverFreq, CrossoverSlope
    #
    # ONE crossover word, THREE documented cells. The graph has a single
    # crossover node in front of the main outputs; the masters give
    # MainL/MainR/MainSub a CrossoverFreq and CrossoverSlope each. Both are
    # true, so all three pairs resolve to this node's address rather than
    # one strip getting the cell and the other two reading as gaps. Many
    # cells to one address is the normal shape here (see wire_contract.py).
    for scat, sinst in _XOVER_STRIPS:
        add_cell(cn(scat, sinst, 'CrossoverFreq', 1), chip, pg, base,
                 '0=50/127=500/[Log]', 'EqSafe',
                 notes='shared crossover word')
        add_cell(cn(scat, sinst, 'CrossoverSlope', 1), chip, pg, base,
                 '0=6/3=24/[Lin]', 'InstantCtl',
                 notes='MCU-computed, shares base; shared crossover word')

    # Dispatch: coefficient staging (20 words for LP+HP biquads)
    add_dispatch_block(chip, base, f'_xover_coeffs_next_{nid}', 20, f'{nid} XOVER coeff')
    # swap_pending and crossfade control
    # Remaining words...
    for off in range(20, 24):
        key = (chip, base + off)
        if key not in dispatch:
            add_dispatch(chip, base + off, None, f'{nid} spare')


# ── MONITOR ──────────────────────────────────────────────────────────────
def expand_monitor(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 6 words: source + level_l + level_r + ...
    add_cell(cn(cat, inst, 'InputSel', 1), chip, pg, base, '', 'InstantCtl')
    add_dispatch(chip, base, f'_mon_source_{nid}', f'{nid} source')

    add_cell(cn(cat, inst, 'Level', 1), chip, pg, base + 1,
             'dB:Off:-50@31:-30@63:-10@127:10', 'GainFast', notes='L')
    add_dispatch(chip, base + 1, f'_mon_level_l_{nid}', f'{nid} level L')

    add_cell(cn(cat, inst, 'Level', 2), chip, pg, base + 2,
             'dB:Off:-50@31:-30@63:-10@127:10', 'GainFast', notes='R')
    add_dispatch(chip, base + 2, f'_mon_level_r_{nid}', f'{nid} level R')

    for off in range(3, 6):
        add_dispatch(chip, base + off, None, f'{nid} spare')


# ── AUX_INPUT (USB/BT) ──────────────────────────────────────────────────
def expand_aux_input(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 2 words: level + on
    add_cell(cn(cat, inst, 'Level', 1), chip, pg, base,
             '0=-20/127=6/[Lin]', 'GainFast')
    add_dispatch(chip, base, f'_auxin_level_{nid}', f'{nid} level')

    add_cell(cn(cat, inst, 'On', 1), chip, pg, base + 1, '', 'InstantCtl')
    add_dispatch(chip, base + 1, f'_auxin_on_{nid}', f'{nid} on')


# ── DCA ──────────────────────────────────────────────────────────────────
def expand_dca(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 2 words per DCA: level + mute
    add_cell(cn(cat, inst, 'Level', 1), chip, pg, base,
             'dB:Off:-50@31:-30@63:-10@127:10', 'GainFast')
    add_dispatch(chip, base, f'_dca_level_{nid}', f'{nid} level')

    add_cell(cn(cat, inst, 'Mute', 1), chip, pg, base + 1, '', 'InstantCtl')
    add_dispatch(chip, base + 1, f'_dca_mute_{nid}', f'{nid} mute')


# ── MIX_BUS (bus pre-sum, mostly internal) ───────────────────────────────
def expand_mix_bus(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    if base < 0:
        return
    # 2 words: bus_id + source_count (internal, no _Cell)
    add_dispatch(chip, base, None, f'{nid} bus_id')
    add_dispatch(chip, base + 1, None, f'{nid} source_count')


# ── Nodes that don't produce cells (INPUT/OUTPUT/RECV/SEND) ─────────────
def expand_noop(node, cat, inst):
    pass


# ---------------------------------------------------------------------------
# Node type → expander dispatch
# ---------------------------------------------------------------------------
NODE_EXPANDERS = {
    'GAIN':           expand_gain,
    'HPF_LPF':        expand_hpf_lpf,
    'EQ_BIQUAD':      expand_eq_biquad,
    'GATE':           expand_gate,
    'COMPRESSOR':     expand_compressor,
    'TUBE_SAT':       expand_tube_sat,
    'DELAY':          expand_delay,
    'FADER_PAN':      expand_fader_pan,
    'ROUTING':        expand_routing,
    'GEQ':            expand_geq,
    'ANTI_FB':        expand_anti_fb,
    'LIMITER':        expand_limiter,
    'METER':          expand_meter,
    'TALKBACK':       expand_talkback,
    'NOISE_GEN':      expand_noise_gen,
    'FX_ENGINE':      expand_fx_engine,
    'CROSSOVER':      expand_crossover,
    'MONITOR':        expand_monitor,
    'AUX_INPUT':      expand_aux_input,
    'DCA':            expand_dca,
    'MIX_BUS':        expand_mix_bus,
    'INPUT_TDM':      expand_noop,
    'OUTPUT_TDM':     expand_noop,
    'INTERCHIP_SEND': expand_noop,
    'INTERCHIP_RECV': expand_noop,
}

# ---------------------------------------------------------------------------
# Node ID → (category, instance) extraction
# ---------------------------------------------------------------------------
_CHAN_TYPES = r'GAIN|FILT|EQ|GATE|COMP|TUBE|DLY|FDR|RTG'
_AUX_TYPES  = r'FDR|EQ|GEQ|AFB|LIM|DLY'
_GRP_TYPES  = r'FDR|EQ|GEQ|GATE|COMP'

# THE MAIN SECTION, per PW ruling 2026-08-25 ("main section model") as the
# hub relayed it on 2026-09-08. `Main[1-1]` is the STEREO MIX BUS strip --
# fader, mute, 28-band GEQ, delay, cue -- and L / R / Ctr / Sub are each a
# POST-CROSSOVER OUTPUT STRIP. So the four chains the graph builds off
# C2_MAIN_XOVER are the four output strips, in DAC order (DAC_13..DAC_16),
# and there is no separate sub mix bus.
#
# THIS IS A WORKING ASSUMPTION AWAITING PW'S CONFIRMATION, and it is not
# only the hub's word: `defs/tools/def_master.py` says the same thing
# independently. Its PREFIX_RULES gate `MainL`/`MainR` on the `main`
# scope, `MainCtr` on `main` + `main.ctr`, and `MainSub` on `sub`; its
# FUNC_GATES put Comp on `main.comp`, Limiter on `main.lim` and Crossover
# on `sub.xover` for every one of those strips; and the D24-only cell
# `Main001Out3Mode001` is gated on `main.ctr` -- an OUT 3 MODE cell that
# exists exactly when the centre output does. Output 3 is the centre.
#
# The superset graph is expanded ONCE and each product's dsp.csv is the
# intersection of that expansion with its own masters (decision D3: ONE
# stable DSP address map shared by both products). So MainCtr is emitted
# here unconditionally: D24's def carries `main.ctr,1` and reaches it,
# D32's does not and lists it as out of product scope -- at the SAME
# address. `None` means exactly what it means everywhere else in this
# table -- the node reaches no cell -- and get_node_context() still
# refuses ids no pattern names at all.
_MAIN_OUT_STRIP = {1: ('MainL', 1), 2: ('MainR', 1),
                   3: ('MainCtr', 1), 4: ('MainSub', 1)}

# Every strip the crossover feeds, in master spelling. One crossover node
# exists in the graph and the masters document Freq/Slope on each output
# strip, so the four cell pairs share the one address.
_XOVER_STRIPS = (('MainL', 1), ('MainR', 1), ('MainCtr', 1), ('MainSub', 1))


def _main_out_strip(n):
    """The master strip for post-crossover main output `n`, or None.

    No-fallback: an output the table has never been asked about is an
    error, not a silent 'no cells' -- that is the difference this whole
    table exists to keep.
    """
    if n not in _MAIN_OUT_STRIP:
        sys.exit(f'ERROR: main output {n} has no entry in _MAIN_OUT_STRIP — '
                 f'say which master strip it is (or None) in gen_dsp.py')
    return _MAIN_OUT_STRIP[n]

_NODE_PATTERNS = [
    # Channel strip (Chip 1)
    (re.compile(r'^C1_IN_(\d+)$'),                     lambda m: None),  # TDM input, no cells
    (re.compile(rf'^C1_(?:{_CHAN_TYPES})_(\d+)$'),     lambda m: ('Chan', int(m.group(1)))),
    (re.compile(r'^C1_MTR_(\d+)$'),                    lambda m: ('Chan', int(m.group(1)))),
    (re.compile(r'^C1_TALK_(\d+)$'),                   lambda m: ('Talk', int(m.group(1)))),
    (re.compile(r'^C1_NOISE$'),                        lambda m: ('Noise', 1)),
    (re.compile(r'^C1_BUS_'),                          lambda m: None),  # skip bus cells
    # Aux (Chip 2)
    (re.compile(rf'^C2_AUX_(?:{_AUX_TYPES})_(\d+)$'), lambda m: ('Aux', int(m.group(1)))),
    (re.compile(r'^C2_AUX_OUT_(\d+)$'),               lambda m: None),
    # Group (Chip 2)
    (re.compile(rf'^C2_GRP_(?:{_GRP_TYPES})_(\d+)$'), lambda m: ('Grp', int(m.group(1)))),
    # Subwoofer strip (Chip 2) -- THE OLD MODEL. Under the 08-25 main
    # section model the sub is a post-crossover OUTPUT (chain 4 below) and
    # there is no separate sub mix bus, so this whole chain -- fed from
    # BUS_SUB and landing on NET_OUT_01 -- reaches no master cell. It is
    # FLAGGED FOR RETIREMENT AND NOT DELETED: the nodes stay in the graph,
    # keep their addresses, and are listed by validate() with that reason.
    (re.compile(r'^C2_SUB_(?:FDR|EQ|COMP|LIM|DLY)$'), lambda m: None),
    (re.compile(r'^C2_SUB_OUT$'),                      lambda m: None),
    # Main bus (Chip 2) -- the stereo mix-bus strip: fader, mute, 28-band
    # GEQ, delay. The masters give `Main[1-1]` exactly CueSel, Dca, DcaOn,
    # Delay, Geq[1-28], Level, Mute, Name (plus Out3Mode on D24) and no
    # dynamics at all, so the bus-level comp and limiter are the old model
    # too: `main.comp` and `main.lim` gate Comp/Limiter on the four OUTPUT
    # strips, which C2_MAIN_O{COMP,LIM}_0[1-4] serve. Same treatment as
    # C2_SUB_*: reported, not deleted.
    (re.compile(r'^C2_MAIN_(?:FDR|GEQ|DLY)$'),          lambda m: ('Main', 1)),
    (re.compile(r'^C2_MAIN_(?:COMP|LIM)$'),             lambda m: None),
    (re.compile(r'^C2_MAIN_XOVER$'),                    lambda m: ('Main', 1)),
    # Main output strips (Chip 2): the four post-crossover chains ARE
    # MainL / MainR / MainCtr / MainSub, in DAC_13..DAC_16 order.
    (re.compile(r'^C2_MAIN_O(?:EQ|COMP|LIM)_(\d+)$'),
     lambda m: _main_out_strip(int(m.group(1)))),
    (re.compile(r'^C2_MAIN_OUT_(\d+)$'),                       lambda m: None),
    (re.compile(r'^C2_MIX_'),                                  lambda m: None),
    # FX (Chip 2)
    (re.compile(r'^C2_FX_(?:ENG|FDR)_(\d+)$'),        lambda m: ('Fx', int(m.group(1)))),
    # Monitor
    (re.compile(r'^C2_MON(?:_DLY)?$'),                 lambda m: ('Mon', 1)),
    (re.compile(r'^C2_MON_OUT$'),                      lambda m: None),
    # USB / BT
    (re.compile(r'^C2_USB_IN$'),                       lambda m: ('Usb', 1)),
    (re.compile(r'^C2_BT_IN$'),                        lambda m: ('Bt', 1)),
    # Superset aux inputs (codec aux in, Pi playback, D32 snake returns)
    (re.compile(r'^C2_CODEC_AUX_IN$'),                 lambda m: ('CodecAux', 1)),
    (re.compile(r'^C2_PI_IN$'),                        lambda m: ('Pi', 1)),
    (re.compile(r'^C2_SNK_IN_(\d+)$'),                 lambda m: ('Snk', int(m.group(1)))),
    # Superset I/O plumbing (no cells)
    (re.compile(r'^C1_XIN_'),                          lambda m: None),
    (re.compile(r'^C1_XS_'),                           lambda m: None),
    (re.compile(r'^C2_XR_'),                           lambda m: None),
    (re.compile(r'^C2_MAIN_ST_OUT$'),                  lambda m: None),
    (re.compile(r'^C2_CODEC_AUX_OUT$'),                lambda m: None),
    # DCA
    (re.compile(r'^C2_DCA_(\d+)$'),                    lambda m: ('Dca', int(m.group(1)))),
    # Output meters. The `Aa` sort prefix is gone from the masters, so a
    # meter's cells now sit in the strip's own category: Aux001Mtr001, not
    # AaAux001Mtr001. Nothing collides -- a strip's own expander emits no
    # Mtr/GateMtr/CompMtr cell.
    (re.compile(r'^C2_MTR_AUX_(\d+)$'),                lambda m: ('Aux', int(m.group(1)))),
    (re.compile(r'^C2_MTR_MAIN_(\d+)$'),
     lambda m: _main_out_strip(int(m.group(1)))),
    (re.compile(r'^C2_MTR_GRP_(\d+)$'),                lambda m: ('Grp', int(m.group(1)))),
    # The sub BUS meter goes with the sub bus strip -- retired, not deleted.
    # MainSub's meter is C2_MTR_MAIN_04 on output chain 4.
    (re.compile(r'^C2_MTR_SUB$'),                      lambda m: None),
    (re.compile(r'^C2_MTR_FX_(\d+)$'),                 lambda m: ('Fx', int(m.group(1)))),
    # Recv/Send (no cells)
    (re.compile(r'^C2_RECV_'),                         lambda m: None),
]


def get_node_context(node_id):
    """Return (category, instance) or None if node doesn't map to cells."""
    for pattern, extractor in _NODE_PATTERNS:
        m = pattern.match(node_id)
        if m:
            return extractor(m)
    # No-fallback policy: every node id must be classified explicitly
    # (a pattern mapping to None means "no cells", which is different
    # from an id nobody has thought about).
    sys.exit(f'ERROR: node id {node_id!r} matches no _NODE_PATTERNS entry — '
             f'add an explicit pattern (or a None mapping) in gen_dsp.py')


# ---------------------------------------------------------------------------
# Main expansion — process every node in dsp.csv
# ---------------------------------------------------------------------------
def expand_all_nodes(nodes):
    for node in nodes:
        nid = node['id']
        ntype = node['type']
        spi_addr = int(node['spi_addr'])

        # Skip nodes with no SPI address (inputs, sends, recvs)
        ctx = get_node_context(nid)
        _current_node['id'], _current_node['type'] = nid, ntype

        expander = NODE_EXPANDERS.get(ntype)
        if expander is None:
            print(f'  WARNING: no expander for node type {ntype} ({nid})', file=sys.stderr)
            continue

        if ctx is None:
            # Node doesn't map to cells — may still need dispatch (e.g. MIX_BUS)
            if spi_addr >= 0 and expander is not expand_noop:
                if expander is not expand_mix_bus:
                    uncatalogued_nodes[nid] = (ntype, unreached_reason(nid))
                expander(node, '', 0)
            continue

        cat, inst = ctx
        if spi_addr >= 0:
            expander(node, cat, inst)


# ---------------------------------------------------------------------------
# Output: _matrix.csv backfill
# ---------------------------------------------------------------------------
def backfill_matrix(header, rows, *, force=False):
    """Match cell_map entries against _matrix.csv rows and fill in DSP columns."""
    # Ensure ramp columns exist in header
    ramp_cols = ['RampProfile', 'RampMode', 'RampUpMs', 'RampDownMs', 'RampCurve', 'RampScope']
    for col in ramp_cols:
        if col not in header:
            header.append(col)

    matrix_names = {r.get('_Cell', '') for r in rows}
    # matrix _Cell -> the name this generator emits for it, resolved
    # current-spelling-first. A generated cell the matrix carries under
    # NEITHER spelling is not an error by itself -- this tree has always
    # generated some cells the masters do not have, and validate() lists
    # them.
    resolved = {}
    for gen_name in cell_map:
        key = _matrix_key(gen_name, matrix_names)
        if key is not None:
            resolved[key] = gen_name

    # THE GUARD THE RENAME TABLE USED TO NEED, kept because the failure it
    # catches has nothing to do with renames. A whole cell FAMILY that
    # reaches no matrix row means this generator and the masters disagree
    # about a name, and `--force` would then CLEAR the DSP columns of every
    # row it merely failed to find -- a wrecked contract file from a run
    # that printed no warning. A family with a handful of misses is
    # ordinary (the graph is wider than the product in places) and is
    # reported by validate(); a family with NO hits at all is not.
    emitted_by_family = {}
    for c in cell_map:
        m = _CELL_SPLIT.match(c)
        if m:
            emitted_by_family.setdefault((m.group(1), m.group(3)), []).append(c)
    orphan_families = sorted(
        fam for fam, cells in emitted_by_family.items()
        if not any(_matrix_key(c, matrix_names) for c in cells))
    if orphan_families:
        print(f'  WARNING: {len(orphan_families)} generated cell families reach '
              f'NO row of _matrix.csv:')
        for cat_, suf in orphan_families:
            n = len(emitted_by_family[(cat_, suf)])
            print(f'    - {cat_}*{suf}* ({n} cells)')

    matched = 0
    cleared = 0
    for row in rows:
        row_name = row.get('_Cell', '')
        cell_name = resolved.get(row_name, row_name)
        if cell_name not in cell_map:
            # On --force, clear stale DSP columns for rows no longer in cell_map
            if force and any(row.get(c) for c in ('DspSpi', 'DspPage', 'DspAdd', 'DspAddHex')):
                for c in ('DspSpi', 'DspPage', 'DspAdd', 'DspAddHex',
                          'RampProfile', 'RampMode', 'RampUpMs', 'RampDownMs', 'RampCurve', 'RampScope'):
                    row[c] = ''
                cleared += 1
            continue

        cm = cell_map[cell_name]
        matched += 1

        # Backfill DspSpi, DspPage, DspAdd, DspAddHex
        if force or not row.get('DspSpi'):
            row['DspSpi'] = str(cm['chip'])
        if force or not row.get('DspPage'):
            row['DspPage'] = str(cm['spi_page'])
        if force or not row.get('DspAdd'):
            row['DspAdd'] = str(cm['spi_addr'])
        if force or not row.get('DspAddHex'):
            row['DspAddHex'] = f'0x{cm["spi_addr"]:04X}'

        # Backfill Table if we have one and it's empty
        if cm['table'] and (force or not row.get('Table')):
            row['Table'] = cm['table']

        # Backfill ramp metadata
        rp_name = cm['ramp_profile']
        rp = RAMP_PROFILES.get(rp_name, RAMP_PROFILES[''])
        if force or not row.get('RampProfile'):
            row['RampProfile'] = rp_name
        if force or not row.get('RampMode'):
            row['RampMode'] = rp['mode']
        if force or not row.get('RampUpMs'):
            row['RampUpMs'] = str(rp['up_ms'])
        if force or not row.get('RampDownMs'):
            row['RampDownMs'] = str(rp['down_ms'])
        if force or not row.get('RampCurve'):
            row['RampCurve'] = rp['curve']
        if force or not row.get('RampScope'):
            row['RampScope'] = rp['scope']

    return matched, cleared


# ---------------------------------------------------------------------------
# Output: dsp_params.asm (per-chip split)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Ramp stride map
#
# A ramped parameter carries three companion words -- target, step and frames
# -- that _ramp_set_target fills in. For a SCALAR parameter the node emits
# them immediately after the value, so they sit at +1/+2/+3. For an ARRAY
# parameter (the routing sends) the node emits four parallel arrays instead:
#
#     _rtg_aux_send        [12]   <- the dispatch table points in here
#     _rtg_aux_send_target [12]
#     _rtg_aux_send_step   [12]
#     _rtg_aux_send_frames [12]
#
# so element i's companions are at +12/+24/+36, not +1/+2/+3. One STRIDE per
# dispatch entry covers both shapes: target = p + s, step = p + 2s,
# frames = p + 3s, with s = 1 for scalars. Entries with no ramp state get 0,
# which the handler reads as "direct write only".
#
# The map is derived by SCANNING THE EMITTED NODE ASM rather than by
# annotating each add_dispatch() call site. The node generator
# (tools/dsp/dsp_codegen.py) decides which parameters get ramp state and how
# wide it is; restating that here by hand is the same duplicated-assumption
# bug this table exists to fix, and it would drift silently. Reading the
# artifact cannot drift: if a node stops ramping a parameter, its
# _target_ declaration goes with it and the stride follows.
#
# HOW THE VALUE SYMBOL IS FOUND, and why it is not derived from the target's
# NAME (measured on the part 2026-08-27).
#
# The first version matched `^\.var (_X)_target_(nid)` and paired it with the
# symbol `_X_nid`. That got 610 of the ramped parameters and silently missed
# every other one, for TWO independent reasons:
#
#   1. The pattern was anchored at column 0. Node generators that emit their
#      `.var` lines INDENTED -- FADER_PAN among them -- matched nothing at
#      all, so fader level, pan and DCA all came out stride 0.
#   2. Where it did match, it assumed the value symbol is the target's name
#      with `_target` removed. GAIN's value is `_gain_coeff_<nid>` while its
#      target is `_gain_target_<nid>`, so the derived name did not exist and
#      the entry came out stride 0 as well.
#
# Stride 0 means "plain word, direct write", so those parameters were written
# straight into the value word -- and the node's own block-rate code then does
# `if frames <= 0: value = target` and clobbers it from a target nothing ever
# set. Net effect on the part: EVERY GAIN and FADER_PAN ramped parameter was
# unsettable over SPI, reading back its initialiser forever. The table's
# existing "fail if no ramped params were found" guard passed the whole time,
# because ROUTING, TUBE_SAT and TALKBACK do emit at column 0 and supplied 610
# entries between them.
#
# So the pairing now uses LAYOUT, not names: `_ramp_set_target` writes at
# +s/+2s/+3s from the VALUE address, and the node emits the value immediately
# before its target -- that adjacency IS the contract, and it is what this
# reads. The quad must be complete and consistently sized, and a node file
# that declares a target but yields no stride is an error rather than a
# silent zero.
# ---------------------------------------------------------------------------
_VAR_RE = re.compile(r'^\s*\.var\s+(_\w+)\s*(?:\[\s*(\d+)\s*\])?\s*[;=]')
_SUFFIXES = ('_target_', '_step_', '_frames_')


def _split_suffix(sym):
    """('_fdr_level_target_C1_FDR_01', '_target_') -> '_fdr_level_C1_FDR_01'."""
    for suf in _SUFFIXES:
        i = sym.find(suf)
        if i > 0:
            return suf, sym[:i] + '_' + sym[i + len(suf):]
    return None, None


def build_ramp_stride_map(nodes_dir):
    """Map a ramped value symbol -> stride to its target/step/frames words.

    Pairs each `_target_` declaration with the `.var` DECLARED IMMEDIATELY
    BEFORE it, because that adjacency is the runtime contract
    (_ramp_set_target writes at +s/+2s/+3s from the value address). Names are
    not assumed: `_gain_coeff_<nid>` is the value for `_gain_target_<nid>`.
    """
    if not os.path.isdir(nodes_dir):
        raise FileNotFoundError(
            f"node ASM directory not found: {nodes_dir}. The ramp stride "
            f"table is derived from the emitted node ASM, so dsp_codegen.py "
            f"must run before gen_dsp.py (see regenerate-dsp-contract.sh).")
    strides = {}
    for name in sorted(os.listdir(nodes_dir)):
        if not name.endswith('.asm'):
            continue
        path = os.path.join(nodes_dir, name)
        with open(path, encoding='utf-8') as f:
            lines = f.read().splitlines()

        decls = []                       # [(symbol, width)] in emission order
        for ln in lines:
            m = _VAR_RE.match(ln)
            if m:
                decls.append((m.group(1), int(m.group(2)) if m.group(2) else 1))

        # A ramp quad is VALUE, _target_, _step_, _frames_ in consecutive
        # .var declarations with the same family stem and the same width.
        # Names alone are not enough to spot one: C1_GATE carries
        # _gate_gain_target_q and C1_EQ carries _eq_xfade_step, neither of
        # which is a ramp. _frames_ is the unmistakable marker -- every real
        # quad has exactly one -- so the count of quads recognised must equal
        # the count of _frames_ declarations, and a mismatch is an error
        # rather than a silent zero.
        n_frames = sum(1 for sym, _ in decls if _split_suffix(sym)[0] == '_frames_')
        found_here = 0
        for i, (sym, width) in enumerate(decls):
            suf, stem = _split_suffix(sym)
            if suf != '_target_' or i == 0 or i + 2 >= len(decls):
                continue
            comps = decls[i + 1:i + 3]
            if [_split_suffix(c[0])[0] for c in comps] != ['_step_', '_frames_']:
                continue
            if [_split_suffix(c[0])[1] for c in comps] != [stem, stem]:
                continue
            value_sym, value_width = decls[i - 1]
            if value_width != width or any(c[1] != width for c in comps):
                raise ValueError(
                    f"{name}: ramp quad for {value_sym} has inconsistent "
                    f"widths -- value[{value_width}], {sym}[{width}], "
                    f"{comps[0][0]}[{comps[0][1]}], {comps[1][0]}[{comps[1][1]}]. "
                    f"_ramp_set_target addresses the companions at +s/+2s/+3s "
                    f"from the value, so one stride must describe all four.")
            found_here += 1
            prev = strides.get(value_sym)
            if prev is not None and prev != width:
                raise ValueError(
                    f"conflicting ramp stride for {value_sym}: {prev} vs "
                    f"{width} (in {name})")
            strides[value_sym] = width

        if found_here != n_frames:
            raise ValueError(
                f"{name}: {n_frames} ramp-frame declarations but "
                f"{found_here} complete quads recognised. The stride table is "
                f"read out of the emitted .var layout; if this node's "
                f"generator changed that layout the scan must be updated, "
                f"because the fallback is a zero stride and a zero stride "
                f"silently turns a ramped parameter into an unsettable one.")

    if not strides:
        raise ValueError(
            f"no ramped parameters found under {nodes_dir}; the node ASM is "
            f"missing or stale, and emitting an all-zero stride table would "
            f"silently disable every ramp.")
    return strides


def _entry_stride(sym, strides):
    """Stride for one dispatch entry symbol ('_sym' or '_sym + 3')."""
    if not sym:
        return 0
    return strides.get(sym.split('+')[0].strip(), 0)


def _build_chip_params(chip_num, table_name, out_path, strides=None):
    """Build dsp_params.asm content for one chip."""
    chip_entries = {a: v for (c, a), v in dispatch.items() if c == chip_num}
    if not chip_entries:
        return None, 0
    strides = strides or {}

    max_addr = max(chip_entries.keys())
    size = ((max_addr + 4) // 4) * 4  # align to 4

    # Collect extern symbols for this chip only
    extern_syms = set()
    for addr, (sym, comment) in chip_entries.items():
        if sym:
            base = sym.split('+')[0].strip()
            extern_syms.add(base)

    lines = []
    lines.append('/*======================================================================')
    lines.append(f' * dsp_params.asm — SPI dispatch table for Chip {chip_num}')
    lines.append(' *')
    lines.append(' * AUTO-GENERATED by gen_dsp.py — do not edit directly.')
    lines.append(' *')
    lines.append(' * Each entry maps an SPI address to the DM address of the target')
    lines.append(' * variable in the corresponding node ASM file.  The SPI handler')
    lines.append(' * indexes this table to route parameter writes directly to node')
    lines.append(' * coefficient variables.')
    lines.append(' *')
    lines.append(f' * {size} entries (SPI addresses 0x0000–0x{max_addr:04X})')
    lines.append(' *======================================================================*/')
    lines.append('')
    lines.append('.section/dm seg_dmda;')
    lines.append('')
    lines.append('/* ---- Extern declarations for node variables ---- */')
    for sym in sorted(extern_syms):
        lines.append(f'.extern {sym};')
    lines.append('')

    lines.append(f'/* ---- Table size for the SPI handler bounds check ---- */')
    lines.append(f'.global {table_name}_size;')
    lines.append(f'.var {table_name}_size = {size};')
    lines.append('')
    lines.append(f'/* ---- Chip {chip_num} SPI dispatch table ({size} entries) ---- */')
    lines.append(f'.global {table_name};')
    lines.append(f'.var {table_name}[{size}] =')
    for addr in range(size):
        entry = chip_entries.get(addr)
        if entry and entry[0]:
            sym, comment = entry
            comma = ',' if addr < size - 1 else ';'
            lines.append(f'    {sym}{comma}    /* 0x{addr:04X}: {comment} */')
        else:
            comment = entry[1] if entry else ''
            comma = ',' if addr < size - 1 else ';'
            cmt = f'  /* 0x{addr:04X}: {comment} */' if comment else f'  /* 0x{addr:04X} */'
            lines.append(f'    0{comma}{cmt}')
    lines.append('')

    # ---- Parallel ramp-stride table ----
    # Same length and indexing as the dispatch table. 0 = plain scalar with no
    # ramp state (direct write only); s >= 1 = ramped, with target at +s,
    # step at +2s and frames at +3s. See build_ramp_stride_map().
    stride_vals = []
    for addr in range(size):
        entry = chip_entries.get(addr)
        stride_vals.append(_entry_stride(entry[0] if entry else None, strides))

    hist = {}
    for v in stride_vals:
        if v:
            hist[v] = hist.get(v, 0) + 1
    ramped_n = sum(hist.values())

    lines.append(f'/* ---- Chip {chip_num} ramp-stride table ({size} entries) ---- */')
    lines.append('/*')
    lines.append(' * Companion to the dispatch table above, same indexing.')
    lines.append(' *   0      -- no ramp state; the SPI handler writes the word directly')
    lines.append(' *   s >= 1 -- ramped: target at +s, step at +2s, frames at +3s')
    lines.append(' *')
    lines.append(' * Scalars are stride 1 (target/step/frames follow the value). The')
    lines.append(' * routing sends are parallel ARRAYS, so their stride is the array')
    lines.append(' * length -- 12 for AuxSend, 6 for FxSend. Writing those at +1/+2/+3')
    lines.append(" * lands on the NEIGHBOURING crosspoint's level instead.")
    lines.append(' *')
    lines.append(f' * {ramped_n} ramped entries; strides ' +
                 '{' + ', '.join(f'{k}: {v}' for k, v in sorted(hist.items())) + '}')
    lines.append(' */')
    lines.append(f'.global {table_name}_stride;')
    lines.append(f'.var {table_name}_stride[{size}] =')
    for addr in range(size):
        entry = chip_entries.get(addr)
        comment = entry[1] if entry else ''
        comma = ',' if addr < size - 1 else ';'
        v = stride_vals[addr]
        cmt = f'  /* 0x{addr:04X}: {comment} */' if comment else f'  /* 0x{addr:04X} */'
        lines.append(f'    {v}{comma}{cmt}')
    lines.append('')

    content = '\n'.join(lines) + '\n'
    return content, len(lines)


def write_dsp_params_asm(dry_run=False):
    """Generate per-chip SPI dispatch tables."""
    for chip_num, table_name, out_path, nodes_dir in [
        (1, '_spi_dispatch_c1', OUT_PARAMS_C1, NODES_DIR_C1),
        (2, '_spi_dispatch_c2', OUT_PARAMS_C2, NODES_DIR_C2),
    ]:
        strides = build_ramp_stride_map(nodes_dir)
        content, line_count = _build_chip_params(chip_num, table_name, out_path,
                                                 strides)
        if content is None:
            continue
        if dry_run:
            print(f'[DRY-RUN] Would write {out_path} ({line_count} lines)')
        else:
            os.makedirs(os.path.dirname(out_path), exist_ok=True)
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f'  Wrote {out_path} ({line_count} lines)')


# ---------------------------------------------------------------------------
# Output: ghost_cells.h
# ---------------------------------------------------------------------------
def write_ghost_cells_h(dry_run=False):
    """Generate ghost_cells.h (declaration only) + ghost_cells.c (definition).

    Using extern const so the 4893-entry array lives in exactly one translation
    unit (ghost_cells.c) instead of being duplicated across every TU that
    includes the header.
    """
    ramp_mode_map  = {'Instant': 0, 'Slew': 1, 'LinearFrames': 2}
    ramp_scope_map = {'Scalar': 0, 'CoeffSetAtomic': 1}
    # Frame period = BLOCK samples / 48 kHz, imported from dsp_codegen
    # (D10). At BLOCK=8 that is 0.1667 ms, not the 0.667 ms this used to
    # hardcode.

    sorted_cells = sorted(cell_map.items())
    n = len(sorted_cells)

    # --- ghost_cells.h — struct typedef + extern declaration only ---
    h_lines = []
    h_lines.append('/*')
    h_lines.append(' * ghost_cells.h — DSP cell definitions for H1S1 MCU firmware')
    h_lines.append(' *')
    h_lines.append(' * AUTO-GENERATED by gen_dsp.py — do not edit directly.')
    h_lines.append(' *')
    h_lines.append(' * The actual array is defined in ghost_cells.c (one translation unit).')
    h_lines.append(' *')
    h_lines.append(f' * ramp_up_frames / ramp_down_frames are RAMP-ENGINE FRAMES, and a')
    h_lines.append(f' * frame is one audio BLOCK. Generated for DSP4_BLOCK_SIZE ='
                   f' {DSP_BLOCK}')
    h_lines.append(f' * ({FRAME_MS:.4f} ms/frame at 48 kHz). Change the block size in')
    h_lines.append(f' * tools/dsp/dsp_codegen.py and REGENERATE: these counts move with it.')
    h_lines.append(' */')
    h_lines.append('#ifndef GHOST_CELLS_H')
    h_lines.append('#define GHOST_CELLS_H')
    h_lines.append('')
    h_lines.append('#include <stdint.h>')
    h_lines.append('')
    h_lines.append('typedef struct {')
    h_lines.append('    const char *name;')
    h_lines.append('    uint8_t     chip;')
    h_lines.append('    uint8_t     spi_page;')
    h_lines.append('    uint16_t    addr;')
    h_lines.append('    const char *table;')
    h_lines.append('    uint8_t     ramp_mode;    /* 0=Instant,1=Slew,2=LinearFrames */')
    h_lines.append('    uint16_t    ramp_up_frames;')
    h_lines.append('    uint16_t    ramp_down_frames;')
    h_lines.append('    uint8_t     ramp_scope;   /* 0=Scalar,1=CoeffSetAtomic */')
    h_lines.append('} CellDef;')
    h_lines.append('')
    h_lines.append(f'#define GHOST_CELLS_COUNT {n}')
    h_lines.append('')
    h_lines.append(f'extern const CellDef ghost_cells[{n}];')
    h_lines.append('')
    h_lines.append('#endif /* GHOST_CELLS_H */')
    h_lines.append('')
    h_content = '\n'.join(h_lines)

    # --- ghost_cells.c — single definition ---
    c_lines = []
    c_lines.append('/*')
    c_lines.append(' * ghost_cells.c — DSP cell table definition')
    c_lines.append(' *')
    c_lines.append(' * AUTO-GENERATED by gen_dsp.py — do not edit directly.')
    c_lines.append(' *')
    c_lines.append(f' * Ramp frame counts generated for DSP4_BLOCK_SIZE = {DSP_BLOCK}')
    c_lines.append(f' * ({FRAME_MS:.4f} ms/frame at 48 kHz).')
    c_lines.append(' */')
    c_lines.append('#include "ghost_cells.h"')
    c_lines.append('')
    c_lines.append(f'const CellDef ghost_cells[{n}] = {{')

    for i, (name, cm) in enumerate(sorted_cells):
        rp         = RAMP_PROFILES.get(cm['ramp_profile'], RAMP_PROFILES[''])
        mode_int   = ramp_mode_map.get(rp['mode'], 0)
        scope_int  = ramp_scope_map.get(rp['scope'], 0)
        up_frames  = ms_to_frames(rp['up_ms'])
        down_frames= ms_to_frames(rp['down_ms'])
        tbl        = cm['table'].replace('"', '\\"') if cm['table'] else ''
        comma      = ',' if i < n - 1 else ''
        c_lines.append(f'    {{ "{name}", {cm["chip"]}, {cm["chip"]}, '
                       f'{cm["spi_addr"]}, "{tbl}", {mode_int}, '
                       f'{up_frames}, {down_frames}, {scope_int} }}{comma}')

    c_lines.append('};')
    c_lines.append('')
    c_content = '\n'.join(c_lines)

    # Also write a standalone DSP-dir copy of the header for reference (no .c needed there)
    dsp_h_lines = h_lines[:]  # identical
    dsp_h_content = '\n'.join(dsp_h_lines)

    if dry_run:
        print(f'[DRY-RUN] Would write {OUT_GHOST_H} ({n} cells, header only)')
        print(f'[DRY-RUN] Would write {OUT_GHOST_H_H1S1} ({n} cells, header only)')
        print(f'[DRY-RUN] Would write {OUT_GHOST_C_H1S1} ({n} cells, definition)')
    else:
        os.makedirs(os.path.dirname(OUT_GHOST_H), exist_ok=True)
        with open(OUT_GHOST_H, 'w', encoding='utf-8') as f:
            f.write(dsp_h_content)
        print(f'  Wrote {OUT_GHOST_H} ({n} cells, header)')
        os.makedirs(os.path.dirname(OUT_GHOST_H_H1S1), exist_ok=True)
        with open(OUT_GHOST_H_H1S1, 'w', encoding='utf-8') as f:
            f.write(h_content)
        print(f'  Wrote {OUT_GHOST_H_H1S1} ({n} cells, header)')
        os.makedirs(os.path.dirname(OUT_GHOST_C_H1S1), exist_ok=True)
        with open(OUT_GHOST_C_H1S1, 'w', encoding='utf-8') as f:
            f.write(c_content)
        print(f'  Wrote {OUT_GHOST_C_H1S1} ({n} cells, definition)')


# ---------------------------------------------------------------------------
# Output: mx_dsp_map.h  (matrix bus address → ghost_cells[] index)
# ---------------------------------------------------------------------------
def write_mx_dsp_map_h(matrix_rows, dry_run=False):
    """Generate MxAdd → ghost_cells[] index lookup table for mx_dsp_dispatch.c.

    Reads MxAdd from each _matrix.csv row that has a DspSpi value (i.e. is
    DSP-mapped).  Produces a sorted array of { mx_addr, cell_idx } pairs so
    mx_dsp_dispatch.c can binary-search by matrix bus address.
    """
    # Build name→index map using the same sort order as write_ghost_cells_h
    sorted_names = [name for name, _ in sorted(cell_map.items())]
    name_to_idx  = {name: i for i, name in enumerate(sorted_names)}

    # Collect entries: (mx_addr:int, cell_idx:int)
    entries = []
    for row in matrix_rows:
        cell_name = row.get('_Cell', '').strip()
        mx_add    = row.get('MxAdd', '').strip()
        dsp_spi   = row.get('DspSpi', '').strip()
        if not (mx_add and dsp_spi and cell_name in name_to_idx):
            continue
        try:
            entries.append((int(mx_add), name_to_idx[cell_name]))
        except ValueError:
            pass

    entries.sort()  # sort by mx_addr for binary search

    lines = []
    lines.append('/*')
    lines.append(' * mx_dsp_map.h — Matrix bus address → ghost_cells[] index')
    lines.append(' *')
    lines.append(' * AUTO-GENERATED by gen_dsp.py — do not edit directly.')
    lines.append(' *')
    lines.append(' * Used by mx_dsp_dispatch.c: DspDispatch(uint32_t mx_addr, uint8_t raw)')
    lines.append(' * performs a binary search on mx_dsp_map[] to find the CellDef, then')
    lines.append(' * calls TableEval() → DspCellWrite().')
    lines.append(' */')
    lines.append('#ifndef MX_DSP_MAP_H')
    lines.append('#define MX_DSP_MAP_H')
    lines.append('')
    lines.append('#include <stdint.h>')
    lines.append('')
    lines.append('typedef struct { uint16_t mx_addr; uint16_t cell_idx; } MxDspEntry;')
    lines.append('')
    lines.append(f'static const MxDspEntry mx_dsp_map[{len(entries)}] = {{')
    for i, (mx_addr, cell_idx) in enumerate(entries):
        comma = ',' if i < len(entries) - 1 else ''
        lines.append(f'    {{ {mx_addr:5d}, {cell_idx:5d} }}{comma}')
    lines.append('};')
    lines.append('')
    lines.append(f'#define MX_DSP_MAP_COUNT {len(entries)}')
    lines.append('')
    lines.append('#endif /* MX_DSP_MAP_H */')
    lines.append('')

    content = '\n'.join(lines)

    if dry_run:
        print(f'[DRY-RUN] Would write {OUT_MX_DSP_MAP_H} ({len(entries)} entries)')
    else:
        os.makedirs(os.path.dirname(OUT_MX_DSP_MAP_H), exist_ok=True)
        with open(OUT_MX_DSP_MAP_H, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'  Wrote {OUT_MX_DSP_MAP_H} ({len(entries)} entries)')


# ---------------------------------------------------------------------------
# Output: dsp_address_map.md
# ---------------------------------------------------------------------------
def write_address_map(dry_run=False):
    """Generate human-readable address map for design review."""
    lines = []
    lines.append('# DSP Address Map')
    lines.append('')
    lines.append('> AUTO-GENERATED by `gen_dsp.py` — do not edit directly.')
    lines.append('')

    for chip_num in (1, 2):
        chip_cells = [(n, c) for n, c in sorted(cell_map.items()) if c['chip'] == chip_num]
        if not chip_cells:
            continue

        lines.append(f'## Chip {chip_num}')
        lines.append('')
        lines.append('| SPI Addr | Hex | _Cell | Table | RampProfile |')
        lines.append('|----------|-----|-------|-------|-------------|')

        for name, cm in sorted(chip_cells, key=lambda x: x[1]['spi_addr']):
            addr = cm['spi_addr']
            hexaddr = f'0x{addr:04X}'
            tbl = cm['table'][:30] if cm['table'] else ''
            rp = cm['ramp_profile']
            lines.append(f'| {addr} | {hexaddr} | `{name}` | {tbl} | {rp} |')

        lines.append('')
        lines.append(f'**Total Chip {chip_num} cells:** {len(chip_cells)}')
        lines.append('')

    content = '\n'.join(lines) + '\n'

    if dry_run:
        print(f'[DRY-RUN] Would write {OUT_ADDR_MAP}')
    else:
        os.makedirs(os.path.dirname(OUT_ADDR_MAP), exist_ok=True)
        with open(OUT_ADDR_MAP, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'  Wrote {OUT_ADDR_MAP}')


# ---------------------------------------------------------------------------
# Output: the proposed `dsp.csv` per product  (PW ruling 2026-09-08 #5)
# ---------------------------------------------------------------------------
# THIS REPO PROPOSES, THE HUB LANDS. The DSP address file is a DEFINITION --
# it belongs in `defs/products/<p>/dsp.csv` next to the product def that
# decides which cells exist -- but it can only be DERIVED here, from the
# graph this tree owns. So it is written to `proposals/defs/products/<p>/`
# and the hub copies it in at the gate.
#
# ONE ADDRESS MAP, TWO PRODUCTS (decision D3). The superset graph is
# expanded ONCE and each product's file is the intersection of that
# expansion with its own `_matrix.csv`. A cell that both products carry
# gets the SAME chip, page and address in both files by construction --
# there is no per-product allocation step that could drift.
#
# COVERAGE IS AN INVARIANT, NOT A HOPE. For each product,
#
#     rows(dsp.csv) + rows(dsp-unmapped.csv) == cells(_matrix.csv)
#
# is asserted before either file is written. Every cell the product
# defines either reaches a DSP address or is named with the reason it does
# not, and there is no third bucket for the ones nobody looked at.

PROPOSAL_ROOT = os.path.join(REPO_ROOT, 'proposals', 'defs', 'products')
PROPOSAL_PRODUCTS = (
    ('d32', os.path.join(REPO_ROOT, 'MW', 'D32', 'MX', '_matrix.csv')),
    ('d24', os.path.join(REPO_ROOT, 'MW', 'D24', 'MX', '_matrix.csv')),
)

# Column semantics. `defs/common/schema/` declares no dsp.csv schema at
# defs-v2026.09.08, so this is the proposal for one, restated in the file
# header the hub lands.
DSP_CSV_COLUMNS = [
    ('_Cell',       'cell name, as spelled by defs/gen/matrix/<p>-mx-master.csv'),
    ('Node',        'graph node that owns the address (MW/D32/DSP/SHARC/dsp.csv id)'),
    ('NodeType',    'that node\'s type'),
    ('DspSpi',      'DSP the cell lives on: 1 = DSPA (chip 1), 2 = DSPB (chip 2)'),
    ('DspPage',     'SPI page'),
    ('DspAdd',      'SPI word address within the page, decimal'),
    ('DspAddHex',   'the same address, 0xNNNN'),
    ('Access',      'rw = host writes it | ro = DSP writes it, host polls | '
                    'mcu = the word carries no DSP symbol (MCU/host hardware control)'),
    ('RampProfile', 'named ramp preset, or empty for an un-ramped word'),
    ('RampMode',    'Instant | Slew | LinearFrames'),
    ('RampUpMs',    'ramp-up time, ms'),
    ('RampDownMs',  'ramp-down time, ms'),
    ('RampCurve',   'Linear | Exp'),
    ('RampScope',   'Scalar = one word ramps on its own | CoeffSetAtomic = '
                    'the whole coefficient set swaps together'),
    ('Table',       'host scaling table for the control range, where one applies'),
    ('Notes',       'what the word is'),
]

UNMAPPED_CSV_COLUMNS = ['_Cell', 'Class', 'Reason']

# ---------------------------------------------------------------------------
# Why a defined cell reaches no DSP address.
#
# NO-FALLBACK: a cell family that is in neither the address map nor this
# table stops the generator. "Unmapped" without a reason is the state S1
# reported 1,011 cells in, and it is indistinguishable from "nobody looked".
#
# Classes:
#   host-managed        PW ruling: the host owns the value outright.
#   mcu-only            matches mcu-only-prefixes.txt.
#   label               text the host stores; no DSP parameter.
#   surface-state       console surface state; no audio parameter.
#   hardware-control    the MCU drives hardware, not a DSP word.
#   control-plane       a real audio effect the HOST folds onto DSP words
#                       it already has (mute groups, tap tempo).
#   no-graph-node       a DSP function the product defines and the graph
#                       does NOT build. These are the ones that cost work.
#   unbacked-meter      a meter tap the kernel writes no word for.
#   s1-2-no-behaviour   S1-2 families that became definitions again at
#                       defs-v2026.09.08 with no DSP behaviour yet.
# ---------------------------------------------------------------------------
_MAIN_OUT = ('MainL', 'MainR', 'MainCtr', 'MainSub')

_UNMAPPED_REASONS = {
    ('*', 'Name'): ('label', 'text label; the host stores it, the DSP has no word for it'),
    ('Aux', 'PickOff'): ('no-graph-node',
        'aux-master send pickoff; the DSP pickoff is per crosspoint '
        '(Chan*AuxPick*) and there is no aux-master word — open question Q4'),
    ('Bt', 'Src'): ('hardware-control', 'Bluetooth receiver source select — MCU hardware control'),
    ('Card', 'Type'): ('hardware-control', 'option-card type, reported by the MCU'),
    ('Chan', 'AntiClip'): ('no-graph-node', 'per-channel anti-clip; no node in the graph implements it'),
    ('Chan', 'Color'): ('surface-state', 'strip colour on the surface'),
    ('Chan', 'CompMtr'): ('unbacked-meter',
        'the channel meter declares a comp_gr tap and the kernel writes no '
        'word for it; base+3 is the meter\'s own state array (defect 4)'),
    ('Chan', 'CueSel'): ('control-plane',
        'PFL/cue select; the DSP has one monitor source word '
        '(Mon001InputSel001) that the host writes — open question Q5'),
    ('Chan', 'InsertOn'): ('hardware-control', 'analogue insert relay'),
    ('Chan', 'Instr'): ('hardware-control', 'instrument / Hi-Z input mode'),
    ('Chan', 'LcrOn'): ('no-graph-node',
        'LCR pan law; the router has MainOn and CtrOn and no LCR divergence '
        '— open question Q6'),
    ('Chan', 'Link'): ('surface-state', 'stereo link of adjacent strips; the host writes both strips'),
    ('Chan', 'MatrixOn'): ('no-graph-node', 'matrix mixer (def key mtx); the graph builds no matrix node'),
    ('Chan', 'MatrixSend'): ('no-graph-node', 'matrix mixer (def key mtx); the graph builds no matrix node'),
    ('Chan', 'MuteGrp'): ('control-plane',
        'mute-group membership; folded by the host onto the strip mute, the '
        'same shape as Dca (PW ruling 2026-08-30)'),
    ('Chan', 'PadOn'): ('hardware-control', 'input pad relay'),
    ('Fx', 'AuxOn'): ('no-graph-node',
        'FX return to aux sends; the return strip C2_FX_FDR_* has no ROUTING node'),
    ('Fx', 'AuxSend'): ('no-graph-node',
        'FX return to aux sends; the return strip C2_FX_FDR_* has no ROUTING node'),
    ('Fx', 'DuckThr'): ('s1-2-no-behaviour',
        'S1-2: FxDuckThr is a definition again at defs-v2026.09.08. The FX '
        'engine has DuckOn and DuckSens words and no threshold word — Q7'),
    ('Fx', 'MuteAll'): ('control-plane', 'mute all FX returns; host fold onto the six return mutes'),
    ('Fx', 'MuteGrp'): ('control-plane', 'mute-group membership; host fold onto the return mute'),
    ('Fx', 'PedAssign'): ('surface-state', 'footswitch assignment'),
    ('Fx', 'PingPongStart'): ('no-graph-node', 'ping-pong start side; the FX engine has no such word'),
    ('Fx', 'ReturnWetLock'): ('surface-state', 'UI lock on the return wet control'),
    ('Fx', 'Tap'): ('control-plane', 'tap tempo; the host computes and writes Fx*DelayTime*'),
    ('Main', 'CueSel'): ('control-plane', 'cue select; see Q5'),
    ('Main', 'Out3Mode'): ('no-graph-node',
        'D24 centre-output mode (def key main.ctr); C2_MAIN_XOVER feeds all '
        'four outputs unconditionally and no word selects output 3\'s source '
        '— open question Q2'),
    ('Matrix', 'Level'): ('no-graph-node', 'matrix mixer output (def key mtx); no matrix node in the graph'),
    ('Matrix', 'Mute'): ('no-graph-node', 'matrix mixer output (def key mtx); no matrix node in the graph'),
    ('Noise', 'Dest'): ('no-graph-node',
        'generator destination; the NOISE_GEN node reserves base+3 as a route '
        'bitmask with no symbol behind it'),
    ('Phones', 'Level'): ('hardware-control', 'headphone amplifier'),
    ('Phones', 'Src'): ('hardware-control', 'headphone source select'),
    ('Rta', 'On'): ('no-graph-node', 'RTA analyser; no node in the graph'),
    ('Rta', 'Src'): ('no-graph-node', 'RTA analyser; no node in the graph'),
    ('Talk', 'Dest'): ('no-graph-node',
        'talkback destinations 2 and 3; the TALKBACK node has four SPI words '
        '(On, Gain, Hpf, Dest1) and the graph gives it no more'),
}
for _s in _MAIN_OUT:
    _q1 = ('no-graph-node',
           'post-crossover output chain {} has EQ + COMP + LIM and no '
           'FADER_PAN or DELAY node, so the strip\'s own level, mute and '
           'delay reach no word — open question Q1'.format(_s))
    _UNMAPPED_REASONS[(_s, 'Level')] = _q1
    _UNMAPPED_REASONS[(_s, 'Mute')] = _q1
    _UNMAPPED_REASONS[(_s, 'Delay')] = _q1
    _UNMAPPED_REASONS[(_s, 'LimiterRng')] = ('no-graph-node',
        'limiter range; the LIMITER node carries On, Thr, Att and Rel and no '
        'range word')
    _UNMAPPED_REASONS[(_s, 'EqHpf')] = ('no-graph-node',
        'HPF on EQ bands 2-4; the generator gives a non-Main strip one HPF '
        '(band 1) and the masters give the output strips four — open '
        'question Q8')
    _UNMAPPED_REASONS[(_s, 'PeqGain')] = ('s1-2-no-behaviour',
        'S1-2: PeqGain is a definition again at defs-v2026.09.08 (def key '
        'main.geq); no node carries a parametric gain bank — Q7')


def _unmapped_reason(cell, mcu_prefixes):
    """(class, reason) for a defined cell with no DSP address. No-fallback."""
    if cell in unbacked_meter_cells:
        return ('unbacked-meter', unbacked_meter_cells[cell])
    m = _CELL_SPLIT.match(cell)
    if m is None:
        return ('label', 'not a cell-shaped name; carries no DSP parameter')
    cat, fam = m.group(1), m.group(3)
    if fam in host_managed:
        return ('host-managed',
                'the host owns the value outright — no DSP address, no kernel '
                'read (PW ruling 2026-08-30)')
    for key in ((cat, fam), ('*', fam)):
        if key in _UNMAPPED_REASONS:
            return _UNMAPPED_REASONS[key]
    if any(cell.startswith(p) for p in mcu_prefixes):
        return ('mcu-only',
                'MCU-only cell family (mcu-only-prefixes.txt); no DSP address '
                'expected')
    sys.exit(f'ERROR: cell {cell!r} ({cat}/{fam}) reaches no DSP address and '
             f'_UNMAPPED_REASONS in gen_dsp.py does not say why. Give the '
             f'family a reason, or map it to a graph node.')


def _dsp_csv_row(name, cm):
    rp = RAMP_PROFILES.get(cm['ramp_profile'], RAMP_PROFILES[''])
    sym = dispatch.get((cm['chip'], cm['spi_addr']), (None, ''))[0]
    if cm['node_type'] == 'METER':
        access = 'ro'
    elif sym is None:
        access = 'mcu'
    else:
        access = 'rw'
    return {
        '_Cell': name,
        'Node': cm['node'],
        'NodeType': cm['node_type'],
        'DspSpi': str(cm['chip']),
        'DspPage': str(cm['spi_page']),
        'DspAdd': str(cm['spi_addr']),
        'DspAddHex': f'0x{cm["spi_addr"]:04X}',
        'Access': access,
        'RampProfile': cm['ramp_profile'],
        'RampMode': rp['mode'],
        'RampUpMs': str(rp['up_ms']),
        'RampDownMs': str(rp['down_ms']),
        'RampCurve': rp['curve'],
        'RampScope': rp['scope'],
        'Table': cm['table'],
        'Notes': cm['notes'],
    }


def _write_csv(path, header, rows, preamble):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', newline='', encoding='utf-8') as f:
        for line in preamble:
            f.write(f'# {line}\n' if line else '#\n')
        w = csv.DictWriter(f, fieldnames=header, extrasaction='raise')
        w.writeheader()
        w.writerows(rows)


def write_proposals(dry_run=False):
    """Write the proposed dsp.csv + its unmapped companion, per product."""
    mcu_prefixes = load_mcu_only_prefixes()
    cols = [c for c, _ in DSP_CSV_COLUMNS]
    summary = []

    for product, matrix_path in PROPOSAL_PRODUCTS:
        with open(matrix_path, newline='', encoding='utf-8') as f:
            defined = [r['_Cell'] for r in csv.DictReader(f) if r.get('_Cell')]
        defined_set = set(defined)

        mapped = [n for n in defined if n in cell_map]
        unmapped = [n for n in defined if n not in cell_map]
        # The invariant, checked before anything is written.
        if len(mapped) + len(unmapped) != len(defined):
            sys.exit(f'ERROR: {product} coverage split does not add up')

        rows = [_dsp_csv_row(n, cell_map[n]) for n in sorted(mapped)]
        un_rows = []
        for n in sorted(unmapped):
            klass, reason = _unmapped_reason(n, mcu_prefixes)
            un_rows.append({'_Cell': n, 'Class': klass, 'Reason': reason})

        # Cells the superset graph builds that this product does not define.
        # Not a gap: the address is reserved in the one shared map and the
        # other product reaches it (decision D3).
        out_of_scope = sorted(set(cell_map) - defined_set)

        pin = f'defs-v* pin: {CONTRACT_PIN}'
        head = [
            f'{product}/dsp.csv — PROPOSED DSP address map for {product.upper()}.',
            '',
            'GENERATED by MW/D32/DSP/gen_dsp.py in the invirco/dsp repo from the',
            'DSP4 node graph (MW/D32/DSP/SHARC/dsp.csv). Do not hand-edit: an',
            'address typed here is an address no kernel answers on.',
            '',
            'Proposed by dsp, landed by the hub at the gate (PW ruling',
            f'2026-09-08 #5). {pin}.',
            '',
            'ONE ADDRESS MAP FOR BOTH PRODUCTS (decision D3): the superset graph',
            'is expanded once and this file is the intersection of that',
            "expansion with this product's cell set, so a cell both products",
            'carry has the same chip, page and address in both files.',
            '',
            f'{len(rows)} of {len(defined)} defined cells reach a DSP address.',
            f'The other {len(un_rows)} are named in dsp-unmapped.csv with the',
            'reason — every defined cell is in exactly one of the two files.',
            '',
            'Columns:',
        ]
        head += [f'  {c:<12} {d}' for c, d in DSP_CSV_COLUMNS]

        un_head = [
            f'{product}/dsp-unmapped.csv — defined cells with NO DSP address.',
            '',
            'GENERATED alongside dsp.csv by MW/D32/DSP/gen_dsp.py. The companion',
            'to it: dsp.csv says where a cell lives, this says why it lives',
            'nowhere. A family in neither file stops the generator.',
            '',
            'Class:  host-managed | mcu-only | label | surface-state |',
            '        hardware-control | control-plane | no-graph-node |',
            '        unbacked-meter | s1-2-no-behaviour',
            '',
            'no-graph-node is the list that costs work: a DSP function this',
            'product defines and the graph does not build.',
            '',
        ]

        out_dir = os.path.join(PROPOSAL_ROOT, product)
        dsp_path = os.path.join(out_dir, 'dsp.csv')
        un_path = os.path.join(out_dir, 'dsp-unmapped.csv')

        if dry_run:
            print(f'[DRY-RUN] Would write {dsp_path} ({len(rows)} cells)')
            print(f'[DRY-RUN] Would write {un_path} ({len(un_rows)} cells)')
        else:
            _write_csv(dsp_path, cols, rows, head)
            _write_csv(un_path, UNMAPPED_CSV_COLUMNS, un_rows, un_head)
            print(f'  Wrote {dsp_path} ({len(rows)} cells)')
            print(f'  Wrote {un_path} ({len(un_rows)} cells)')
            verify_proposal_roundtrip(dsp_path, mapped)

        summary.append((product, len(defined), len(rows), len(un_rows),
                        len(out_of_scope), un_rows, out_of_scope))
    return summary


def verify_proposal_roundtrip(path, expected_cells):
    """Read the written file back and prove it carries the address map.

    The point of the file is that the hub can land it in defs and everything
    downstream reads THAT rather than this generator. A file that cannot be
    read back into the same table is a report, not a definition.
    """
    with open(path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(
            line for line in f if not line.startswith('#')))
    got = {r['_Cell']: (int(r['DspSpi']), int(r['DspPage']), int(r['DspAdd']),
                        r['RampProfile'], r['Table'], r['Notes'])
           for r in rows}
    want = {n: (cell_map[n]['chip'], cell_map[n]['spi_page'],
                cell_map[n]['spi_addr'], cell_map[n]['ramp_profile'],
                cell_map[n]['table'], cell_map[n]['notes'])
            for n in expected_cells}
    if got != want:
        diff = sorted(set(got) ^ set(want)) or \
            sorted(k for k in want if got.get(k) != want[k])
        sys.exit(f'ERROR: {path} does not read back as the address map it '
                 f'was written from; first differences: {diff[:5]}')
    print(f'    round-trip OK — {len(got)} rows read back identical')


# ---------------------------------------------------------------------------
# Consuming the LANDED contract  (defs/products/<p>/{dsp.csv,dsp-unmapped.csv})
# ---------------------------------------------------------------------------
# This repo PROPOSES dsp.csv from the graph; the hub LANDS it into defs at
# the gate (PW ruling 2026-09-08 #5). Past that point the graph is no longer
# what generation reads: `cell_map` above stays the source of the facts a
# NEW proposal would carry (and the input to the drift check below), but
# _matrix.csv backfill, ghost_cells.h, dsp_params.asm, mx_dsp_map.h and
# dsp_address_map.md all read the LANDED file, same as any other consumer of
# defs. `check_proposal()` is what keeps that safe: if the graph and the
# landed file ever disagree, that is the "proposal drifted from the
# contract" signal, and the fix is a new proposal to the hub gate, never a
# local edit to defs/products/<p>/dsp.csv or a silent re-derive from here.
DEFS_PRODUCTS_DIR = os.path.join(REPO_ROOT, 'defs', 'products')


def landed_dsp_csv_path(product):
    return os.path.join(DEFS_PRODUCTS_DIR, product, 'dsp.csv')


def landed_unmapped_csv_path(product):
    return os.path.join(DEFS_PRODUCTS_DIR, product, 'dsp-unmapped.csv')


def _read_landed_csv(path):
    if not os.path.isfile(path):
        sys.exit(f'ERROR: {path} is missing — the defs pin does not carry '
                 f'the landed DSP address map this repo consumes.')
    with open(path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(
            line for line in f if not line.startswith('#')))
    return {r['_Cell']: r for r in rows}


def build_proposal_rows(product, matrix_path, mcu_prefixes):
    """The dsp.csv / dsp-unmapped.csv rows the graph proposes for `product`,
    keyed by cell, without writing anything. Shared by write_proposals()
    (which lands them on disk) and check_proposal() (which only compares)."""
    with open(matrix_path, newline='', encoding='utf-8') as f:
        defined = [r['_Cell'] for r in csv.DictReader(f) if r.get('_Cell')]
    mapped = [n for n in defined if n in cell_map]
    unmapped = [n for n in defined if n not in cell_map]
    if len(mapped) + len(unmapped) != len(defined):
        sys.exit(f'ERROR: {product} coverage split does not add up')
    rows = {n: _dsp_csv_row(n, cell_map[n]) for n in mapped}
    un_rows = {}
    for n in unmapped:
        klass, reason = _unmapped_reason(n, mcu_prefixes)
        un_rows[n] = {'_Cell': n, 'Class': klass, 'Reason': reason}
    return rows, un_rows


def check_proposal():
    """Prove the graph reproduces the LANDED dsp.csv/dsp-unmapped.csv for
    both products, row for row (every column dsp.csv declares — the header
    comment's pin stamp is proposal-authoring metadata and not compared).
    Fails loudly and exits nonzero on any drift."""
    mcu_prefixes = load_mcu_only_prefixes()
    ok = True
    for product, matrix_path in PROPOSAL_PRODUCTS:
        rows, un_rows = build_proposal_rows(product, matrix_path, mcu_prefixes)
        landed_rows = _read_landed_csv(landed_dsp_csv_path(product))
        landed_un = _read_landed_csv(landed_unmapped_csv_path(product))

        for label, got, want in (
            ('dsp.csv', rows, landed_rows),
            ('dsp-unmapped.csv', un_rows, landed_un),
        ):
            if set(got) != set(want):
                missing = sorted(set(got) - set(want))
                extra = sorted(set(want) - set(got))
                print(f'ERROR: {product}/{label} cell set disagrees with the '
                      f'graph — {len(missing)} the graph proposes and the '
                      f'landed file lacks, {len(extra)} the landed file has '
                      f'and the graph does not propose.', file=sys.stderr)
                for c in (missing + extra)[:10]:
                    print(f'    - {c}', file=sys.stderr)
                ok = False
                continue
            mismatched = [c for c in got if got[c] != want[c]]
            if mismatched:
                print(f'ERROR: {product}/{label} disagrees with the graph on '
                      f'{len(mismatched)} cells (first 5 shown):', file=sys.stderr)
                for c in mismatched[:5]:
                    print(f'    - {c}: graph={got[c]} landed={want[c]}', file=sys.stderr)
                ok = False

    if not ok:
        sys.exit('ERROR: the graph has drifted from the landed dsp.csv / '
                 'dsp-unmapped.csv contract in defs/products/<p>/. Fix: '
                 'propose a new dsp.csv to the hub gate — never hand-edit '
                 'the landed file, and never let generation quietly fall '
                 'back to the graph when it disagrees with what is landed.')
    print('  check-proposal OK — the graph reproduces the landed dsp.csv / '
          'dsp-unmapped.csv exactly for both products')


def load_landed_address_map():
    """The DSP cell address map as LANDED in defs/products/<p>/dsp.csv,
    merged across both products (decision D3: one shared address map, so a
    cell either product carries has the same chip/page/address in both
    files — checked here, not just assumed). This, not the graph's
    `cell_map`, is what _matrix.csv backfill and every generated firmware
    artifact reads once check_proposal() has proven the two agree."""
    merged = {}
    for product, _ in PROPOSAL_PRODUCTS:
        for cell, r in _read_landed_csv(landed_dsp_csv_path(product)).items():
            entry = {
                'chip': int(r['DspSpi']),
                'spi_page': int(r['DspPage']),
                'spi_addr': int(r['DspAdd']),
                'table': r['Table'],
                'ramp_profile': r['RampProfile'],
                'notes': r['Notes'],
                'node': r['Node'],
                'node_type': r['NodeType'],
            }
            prior = merged.get(cell)
            if prior is not None and prior != entry:
                sys.exit(f'ERROR: {cell!r} disagrees between the landed '
                         f'products/<p>/dsp.csv files — decision D3 requires '
                         f'one shared address map. {prior} vs {entry} '
                         f'({product})')
            merged[cell] = entry
    return merged


# ---------------------------------------------------------------------------
# Cross-reference validation
# ---------------------------------------------------------------------------
def validate(matrix_rows):
    """Warn on cells present in one source but not the other."""
    matrix_names = {r['_Cell'] for r in matrix_rows if r.get('_Cell')}

    mcu_only_prefixes = load_mcu_only_prefixes()
    # One spelling, the master's. The pin is past the 2026-08-25 rename, so
    # a generated name either IS a matrix row or is a divergence to report.
    reached = {c for c in cell_map if _matrix_key(c, matrix_names)}
    in_map_not_matrix = set(cell_map) - reached
    # The matrix rows the HOST owns: no DSP address by ruling, listed as
    # that rather than swept into "no DSP mapping (MCU-only or unmapped)",
    # which is where an unexplained gap belongs.
    host_rows = set()
    in_matrix_no_dsp = set()
    for name in matrix_names:
        m = _CELL_SPLIT.match(name)
        if m and m.group(3) in host_managed:
            host_rows.add(name)
            continue
        # Skip known MCU-only prefixes
        if any(name.startswith(p) for p in mcu_only_prefixes):
            continue
        if name not in reached:
            in_matrix_no_dsp.add(name)

    if uncatalogued_nodes:
        print(f'  WARNING: {len(uncatalogued_nodes)} graph nodes have SPI '
              f'addresses but reach NO master cell category — the DSP will '
              f'answer on those addresses and nothing in the product '
              f'definition names them:')
        for nid, (ntype, reason) in sorted(uncatalogued_nodes.items()):
            print(f'    - {nid} ({ntype}): {reason}')

    if host_managed:
        for fam, nodes in sorted(host_managed.items()):
            n = len([c for c in host_rows
                     if _CELL_SPLIT.match(c).group(3) == fam])
            print(f'  INFO: cell family {fam!r} is HOST-MANAGED on '
                  f'{len(nodes)} nodes -- no DSP address, no kernel read '
                  f'(PW ruling 2026-08-30); {n} rows in _matrix.csv')

    if in_map_not_matrix:
        print(f'  INFO: {len(in_map_not_matrix)} DSP cells not in _matrix.csv '
              f'(may need adding)')
        for name in sorted(in_map_not_matrix)[:10]:
            print(f'    - {name}')
        if len(in_map_not_matrix) > 10:
            print(f'    ... and {len(in_map_not_matrix) - 10} more')

    if in_matrix_no_dsp:
        print(f'  INFO: {len(in_matrix_no_dsp)} _matrix.csv cells have no DSP mapping '
              f'(MCU-only or unmapped)')
        for name in sorted(in_matrix_no_dsp)[:10]:
            print(f'    - {name}')
        if len(in_matrix_no_dsp) > 10:
            print(f'    ... and {len(in_matrix_no_dsp) - 10} more')


def report_proposals(summary):
    """Per-product coverage of the proposed dsp.csv, said out loud."""
    from collections import Counter
    for product, defined, mapped, unmapped, oos, un_rows, oos_cells in summary:
        print(f'  {product}: {mapped}/{defined} defined cells reach a DSP '
              f'address; {unmapped} named as unmapped')
        by_class = Counter(r['Class'] for r in un_rows)
        for klass, n in sorted(by_class.items(), key=lambda kv: -kv[1]):
            print(f'      {n:5d}  {klass}')
        if oos:
            fams = sorted({_CELL_SPLIT.match(c).group(1) for c in oos_cells
                           if _CELL_SPLIT.match(c)})
            print(f'      {oos:5d}  out-of-product-scope: the graph builds '
                  f'them, {product} does not define them ({", ".join(fams)})')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='§17 build tool for D32 DSP')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print planned assignments without writing files')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite existing non-empty fields in _matrix.csv')
    parser.add_argument('--check-proposal', action='store_true',
                        help='Only check the graph reproduces the landed '
                             'defs/products/<p>/dsp.csv + dsp-unmapped.csv '
                             'exactly; generate nothing.')
    parser.add_argument('--propose', action='store_true',
                        help='Also write a fresh proposal to proposals/ for '
                             'the hub gate (only needed when the graph has '
                             'changed and a new dsp.csv must be proposed).')
    args = parser.parse_args()

    print('gen_dsp.py — §17 D32 DSP build tool')
    print()

    # 1. Read dsp.csv (the graph)
    print('Reading dsp.csv...')
    nodes = read_dsp_csv()
    print(f'  {len(nodes)} nodes')

    # 2. Expand all nodes -- cell_map here is the graph's PROPOSAL. It is
    # used ONLY to check for drift against the landed contract (and, with
    # --propose, to author a new one) -- never directly to generate.
    print('Expanding node parameters...')
    expand_all_nodes(nodes)
    print(f'  {len(cell_map)} cell mappings (graph)')
    print(f'  {len(dispatch)} dispatch entries')

    # 3. The graph must reproduce the landed contract byte-for-byte, or
    # everything downstream would be generating from a second source of
    # truth again (the exact failure defs S1 retired). No-fallback: this
    # exits nonzero on any disagreement.
    print()
    print('Checking graph against landed defs/products/<p>/dsp.csv...')
    check_proposal()

    if args.check_proposal:
        print()
        print('Done (--check-proposal: nothing generated).')
        return

    if args.propose:
        print()
        print('Proposing dsp.csv...')
        proposals = write_proposals(dry_run=args.dry_run)
        report_proposals(proposals)

    # 4. From here on, generation reads the LANDED address map -- the
    # contract everything but a new proposal consumes -- not the graph.
    address_map = load_landed_address_map()
    cell_map.clear()
    cell_map.update(address_map)
    print(f'  {len(cell_map)} cell mappings (landed, both products merged)')

    # 5. Read _matrix.csv
    print('Reading _matrix.csv...')
    header, matrix_rows = read_matrix_csv()
    print(f'  {len(matrix_rows)} rows')

    # 6. Backfill _matrix.csv
    print('Backfilling _matrix.csv...')
    matched, cleared = backfill_matrix(header, matrix_rows, force=args.force)
    print(f'  {matched} cells matched and backfilled')
    if cleared:
        print(f'  {cleared} stale DSP column entries cleared')

    # 7. Write outputs
    print('Writing outputs...')

    if not args.dry_run:
        with open(MATRIX_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=header, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(matrix_rows)
        print(f'  Wrote {MATRIX_CSV}')

    write_dsp_params_asm(dry_run=args.dry_run)
    write_ghost_cells_h(dry_run=args.dry_run)
    write_mx_dsp_map_h(matrix_rows, dry_run=args.dry_run)
    write_address_map(dry_run=args.dry_run)

    # 8. Validation
    print()
    print('Validation:')
    validate(matrix_rows)

    print()
    print('Done.')


if __name__ == '__main__':
    main()
