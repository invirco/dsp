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
import struct
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
    from dsp_codegen import (BLOCK as DSP_BLOCK, FRAME_MS, ms_to_frames,
                             SAMPLE_RATE_HZ)
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


_MCU_ONLY_PREFIXES_CACHE = None


def load_mcu_only_prefixes():
    """Single registration point for the MCU-only prefix list.

    Parsed from disk once per process and cached; every call site shares
    the same tuple instead of re-reading mcu-only-prefixes.txt."""
    global _MCU_ONLY_PREFIXES_CACHE
    if _MCU_ONLY_PREFIXES_CACHE is None:
        with open(MCU_ONLY_PREFIXES_FILE, encoding='utf-8') as f:
            _MCU_ONLY_PREFIXES_CACHE = tuple(
                line.split('#', 1)[0].strip() for line in f
                if line.split('#', 1)[0].strip())
    return _MCU_ONLY_PREFIXES_CACHE

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
        nodes = list(csv.DictReader(f))
    resolve_geq_bands(nodes)
    return nodes


def resolve_geq_bands(nodes):
    """Set GEQ_BANDS from the GRAPH, not from a constant kept by hand.

    Until 2026-09-08 this file carried `GEQ_BANDS = 28` and dsp.csv carried
    `bands=28`, and the two agreed because someone remembered. The band
    count is a market parameter (`gen_dsp_csv.py --geq-bands`), so the
    moment it moved the constant here would have gone on addressing 28
    words of a 31-word block and the three bands past the end would have
    been silently unmapped -- which is exactly the failure this session
    was dispatched to close. Read it off the graph, and refuse a graph
    whose GEQ nodes do not agree with each other.
    """
    global GEQ_BANDS
    counts = {}
    for node in nodes:
        if node.get('type') != 'GEQ':
            continue
        params = parse_params(node.get('params'))
        if 'bands' not in params:
            sys.exit(f"ERROR: GEQ node {node['id']} carries no bands= param; "
                     f"the address block length is not guessable.")
        counts.setdefault(int(params['bands']), []).append(node['id'])
    if not counts:
        return
    if len(counts) > 1:
        detail = '; '.join(f'{n} bands: {len(ids)} nodes ({ids[0]}...)'
                           for n, ids in sorted(counts.items()))
        sys.exit(f'ERROR: dsp.csv GEQ nodes disagree on band count -- '
                 f'{detail}. One address map, one band count.')
    GEQ_BANDS = next(iter(counts))


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

# dirty:  (chip, spi_addr) -> asm symbol of a flag the SPI handler raises
# when this address is written. See add_dirty_block().
dirty = {}

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


def add_dirty_block(chip, base_addr, count, flag_sym):
    """Mark a run of addresses as needing a kernel-side RECOMPUTE.

    Some families carry a DESIGN PARAMETER on the wire rather than a
    coefficient -- a GEQ band's gain in dB is one number that stands for
    five coefficient words -- and the kernel has to be told the word
    arrived. EQ_BIQUAD solves this with a swap-trigger cell of its own;
    a GEQ node has no address to spare for one, because the contract
    spends all of them on bands.

    So the flag is raised by the SPI handler, off a table with the same
    length and indexing as the dispatch table: a write to any of these
    addresses stores 1 at `flag_sym`, and the node clears it when it has
    redesigned. Nothing polls, and an address with no entry costs the
    handler one load and one compare.
    """
    for i in range(count):
        dirty[(int(chip), base_addr + i)] = flag_sym
    externs.add(flag_sym)


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
    #
    # S24: THE MAIN OUTPUT STRIPS ARE MAIN OUTPUT ZONES AND THIS TEST DID
    # NOT SAY SO. `cat == 'Main'` is the main BUS strip (C2_MAIN_FDR/GEQ/DLY
    # /XOVER); the four POST-CROSSOVER output EQs carry cat MainL / MainR /
    # MainCtr / MainSub (see _MAIN_OUT_STRIP), so they took the `else` and
    # got one HPF each while the masters declare `Main{L,R,Ctr,Sub}[1-1]
    # EqHpf[1-4]` -- which is exactly the "any band as HPF" this comment
    # already claims. Bands 2-4 therefore appeared in dsp-unmapped.csv as
    # no-graph-node when the graph already had the node and the words.
    #
    # It costs NO ARITHMETIC AND NO ADDRESS: every EqHpf cell aliases the
    # band's own coefficient base, exactly as band 1 always did, so the
    # design step that turns a frequency into biquad coefficients is the one
    # already there and the only thing that changes is that three more cells
    # can reach it.
    #
    # THE BAND COUNT IS THE MASTER'S, NOT THIS LOOP'S. add_cell() emits only
    # what the product's cell set actually defines, so `MainSub[1-1]
    # EqHpf[1-1]` gets ONE and `MainL[1-1]EqHpf[1-4]` gets four off the same
    # four iterations -- which is also why this survives PW ruling R2 either
    # way it lands. R2 says the mains carry the aux EQ complement and lists
    # `EqHpf` without a multiplicity; if the hub lands that as `EqHpf[1-1]`
    # on the mains, bands 2-4 simply stop being defined and stop being
    # emitted, with no change here. R2's multiplicity is worth confirming
    # rather than reading off a list.
    if cat not in ('Chan', ''):
        if cat == 'Main' or cat in _MAIN_OUT:
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

    # ── THE MATRIX SENDS, IN A BLOCK OF THEIR OWN (S22 gate 1) ──────────
    #
    # `mtx_page`/`mtx_addr` are allocated by gen_dsp_csv.py AFTER every other
    # chip-1 address, so adopting the matrix ADDS rows to dsp.csv and moves
    # none: growing the 60-word routing block to 64 would have moved every
    # chip-1 address above channel 1's routing node -- the whole map, the
    # MCU's ghost table and every stored golden -- for four words.
    #
    # There is NO MatrixPick cell in the master (Chan*AuxPick and Chan*FxPick
    # exist; Chan*MatrixPick does not), so the pickoff is post-fader and is
    # not host-settable. The kernel keeps a pick array defaulting to PostFdr
    # so the send-ramp helper is the same for all three kinds; nothing is
    # dispatched to it, because no product names a cell for it.
    prm = parse_params(node.get('params', ''))
    n_mtx = int(prm.get('mtx_sends', 0) or 0)
    if n_mtx:
        if 'mtx_page' not in prm or 'mtx_addr' not in prm:
            sys.exit(f'ERROR: {nid} declares mtx_sends={n_mtx} but no '
                     f'mtx_page/mtx_addr — gen_dsp_csv.py allocates that '
                     f'block; refusing to guess an address.')
        m_pg = int(prm['mtx_page'])
        m_base = int(prm['mtx_addr'])
        m_off = 0
        for k in range(1, n_mtx + 1):
            add_cell(cn(cat, inst, 'MatrixOn', k), chip, m_pg, m_base + m_off,
                     '', 'InstantCtl')
            add_dispatch(chip, m_base + m_off,
                         f'_rtg_mtx_on_{nid} + {k-1}', f'{nid} MatrixOn[{k}]')
            m_off += 1
        for k in range(1, n_mtx + 1):
            add_cell(cn(cat, inst, 'MatrixSend', k), chip, m_pg,
                     m_base + m_off,
                     'dB:Off:-50@31:-30@63:-10@127:0', 'GainFast')
            add_dispatch(chip, m_base + m_off,
                         f'_rtg_mtx_send_{nid} + {k-1}',
                         f'{nid} MatrixSend[{k}]')
            m_off += 1


# ── GEQ ──────────────────────────────────────────────────────────────────
# HOW MANY BANDS THE ADDRESS MAP CARRIES -- READ OFF THE GRAPH by
# resolve_geq_bands(), never set here. This value is only the fallback for
# a graph with no GEQ node at all; every real run overwrites it from
# dsp.csv's `bands=` param. defs-v2026.09.08.3 lands `Geq[1-31]` in the
# cell master and the graph was regenerated at `--geq-bands 31` to match,
# which re-laid chip 2 (+51 words) -- see
# MW/D32/DSP/dsp4-dspcsv-proposal-20260908.md §B and
# MW/D32/DSP/dsp4-geq31-relayout-20260909.md.
GEQ_BANDS = 28


def expand_geq(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # GEQ_BANDS SPI words: ONE GAIN IN dB PER BAND.
    #
    # These used to be dispatched to `_geq_coeffs_next_<nid>` -- 28 words
    # of a 140-word coefficient array, one fifth of a five-word stage
    # each, with no trigger to swap them in. The comment on this loop has
    # said "gains[28]" since it was written; the dispatch line said
    # something else, and the part settled it on 2026-09-08: writing
    # +/-12 dB to all 28 landed as raw dB floats in coeffs_next[0..27],
    # the active bank stayed at its compiled identity, and every graphic
    # EQ in the product passed its input through untouched.
    #
    # The band gains cannot carry the cascade's coefficients plus a
    # trigger, so the
    # design belongs on the DSP (src/lib/geq_design_fx.asm, modelled by
    # tools/dsp/geq_ref.py) and these cells carry what the contract says
    # they carry.
    for b in range(1, GEQ_BANDS + 1):
        add_cell(cn(cat, inst, 'Geq', b), chip, pg, base + (b - 1),
                 '0=-12/127=12/[Lin]', 'EqSafe')

    add_dispatch_block(chip, base, f'_geq_gains_{nid}', GEQ_BANDS,
                       f'{nid} GEQ band gain')
    add_dirty_block(chip, base, GEQ_BANDS, f'_geq_dirty_{nid}')


# ── ANTI_FB ──────────────────────────────────────────────────────────────
def expand_anti_fb(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 24 SPI words: on(1) + ctrl_on(1) + notch_freq[6] + notch_gain[6] + notch_q[6] + coeffs staging
    off = 0
    add_cell(cn(cat, inst, 'AntiFbOn', 1), chip, pg, base + off, '', 'InstantCtl')
    add_dispatch(chip, base + off, f'_afb_on_{nid}', f'{nid} AntiFbOn')
    # THE ON SWITCH RAISES THE DESIGN, because it is what the design
    # reads: off writes the compiled identity into every stage, so a node
    # the host has not switched on passes its input word for word. Before
    # 2026-09-08 this address took its write and was read by NO emitted
    # line anywhere in the tree.
    add_dirty_block(chip, base + off, 1, f'_afb_dirty_{nid}')
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

    # THE EIGHTEEN DESIGN PARAMETERS RAISE THE RECOMPUTE FLAG. They have
    # always dispatched to the right symbols -- the 2026-09-08 family walk
    # read 1000.0 Hz, -18.0 dB and Q 4.0 back off the part at these very
    # addresses -- and nothing turned one into a coefficient, because
    # eighteen addresses cannot also carry thirty coefficient words and a
    # swap trigger. The design is on the DSP (src/lib/afb_design_fx.asm,
    # modelled by tools/dsp/afb_ref.py) and this is what tells it a word
    # arrived. The GEQ's arrangement, for the GEQ's reason.
    #
    # `AntiFbCtrlOn` (base + 1) IS DELIBERATELY NOT IN THIS RUN. It
    # enables an AUTOMATIC feedback detector, and no detector exists in
    # this firmware; wiring it to the notch design would make an empty
    # switch look implemented. It lands at its address, unread, and both
    # the kernel and the write-up say so.
    add_dirty_block(chip, base + 2, 18, f'_afb_dirty_{nid}')

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
    # S23 gate 4: BOUND AT SPI base+3, WHICH WAS DISPATCHED TO NOTHING.
    # The note this replaces was half right and the wrong half was
    # load-bearing: base+3 is not "the meter's own state array" -- the
    # STATE array is at DM offset +3, and SPI offset +3 of the four-word
    # meter block had no dispatch entry at all. So the cell gets an
    # address and NOT ONE existing address moves; what would have moved
    # every meter on both chips is inserting the word at DM offset +3,
    # which is the mistake dsp_codegen.py::_mtr_comp_gr() is written not
    # to make. The word is dB of gain reduction, clamped to [-80, 0]
    # (PW ruling R3, 2026-09-10; S23 built it at [-40, 0]).
    'comp_gr':     ('CompMtr', 1,    3, '_mtr_cgr_', 'meter word +3: compressor gain reduction, dB, clamped to [-80, 0] (PW R3)'),
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
                 notes='shared crossover frequency word')
        add_cell(cn(scat, sinst, 'CrossoverSlope', 1), chip, pg, base + 1,
                 '0=6/3=24/[Lin]', 'InstantCtl',
                 notes='shared crossover slope word')

    # THE SLOPE GETS ITS OWN WORD, base + 1, AND IT IS STILL ONE WORD FOR
    # ALL FOUR STRIPS. Until 2026-09-09 all EIGHT crossover cells resolved
    # to `base`, so writing a slope put the integer 24 where a frequency
    # belongs; the design ignored it (an out-of-domain word is not
    # clamped) and the slope was not settable at all. Measured on the part
    # 2026-09-08. It stays ONE shared word because there is ONE
    # `C2_MAIN_XOVER` node feeding all four main outputs from a single
    # LP/HP split -- a per-strip slope would ask one filter pair to have
    # two orders at once, which is why the four frequency cells already
    # alias one word.
    #
    # base + 1 was `_xover_coeffs_next[1]`: one word of a twenty-word
    # staging array that nothing in the contract names and no host writes,
    # and which the design overwrites in full whenever a legal frequency
    # or slope arrives. Taking it costs nothing and moves no other
    # address.

    # THE FIRST WORD IS THE CORNER FREQUENCY, NOT COEFFICIENT 0.
    #
    # It used to be dispatched to `_xover_coeffs_next[0]` -- one word of a
    # twenty-word staging array, with no trigger to swap it in -- so the
    # main crossover took the write and copied its input to all four
    # outputs. Measured on the part 2026-09-08: writing 500 Hz then a
    # slope left 0x00000018 sitting in coefficient 0 and both banks at
    # their compiled identity.
    #
    # The remaining nineteen words stay pointed at the staging array.
    # Nothing in the contract names them, nothing swaps them in, and
    # unmapping them would turn a write nobody makes into an SPI error;
    # the design overwrites all twenty whenever a legal frequency
    # arrives.
    add_dispatch(chip, base, f'_xover_freq_{nid}', f'{nid} crossover frequency')
    add_dirty_block(chip, base, 1, f'_xover_dirty_{nid}')
    add_dispatch(chip, base + 1, f'_xover_slope_{nid}', f'{nid} crossover slope')
    add_dirty_block(chip, base + 1, 1, f'_xover_dirty_{nid}')
    for i in range(2, 20):
        add_dispatch(chip, base + i, f'_xover_coeffs_next_{nid} + {i}',
                     f'{nid} XOVER coeff[{i}]')
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


# ── OUTPUT_TDM ──────────────────────────────────────────────────────────
def expand_output_tdm(node, cat, inst):
    """The output strip's own level and mute (S24).

    Only the nodes that carry an `mo_page`/`mo_addr` param have them --
    gen_dsp_csv.py puts that pair on the four post-crossover main outputs
    and on nothing else, so every other OUTPUT_TDM node in the graph is
    still a no-op and its rows are untouched.

    The pair is a SECOND SPI block, allocated after every other chip-2
    address, so these two cells move nothing. `Delay` is deliberately NOT
    emitted: the master defines it, the node has no delay line, and giving
    it one is an L2 commitment rather than a cell -- it stays in
    dsp-unmapped.csv with its own reason.
    """
    chip, pg, base, nid, ramp = _parse_node(node)
    prm = parse_params(node.get('params', ''))
    if 'mo_page' not in prm:
        return
    mo_pg = int(prm['mo_page'])
    mo_base = int(prm['mo_addr'])

    # The dB table is the master's own for these four strips
    # (`dB:Off:-50@31:-30@63:-10@127:10`), the same one every other output
    # level in this generator carries.
    add_cell(cn(cat, inst, 'Level', 1), chip, mo_pg, mo_base,
             'dB:Off:-50@31:-30@63:-10@127:10', 'GainFast')
    add_dispatch(chip, mo_base, f'_out_level_{nid}', f'{nid} output level')

    add_cell(cn(cat, inst, 'Mute', 1), chip, mo_pg, mo_base + 1,
             '', 'InstantCtl')
    add_dispatch(chip, mo_base + 1, f'_out_mute_{nid}', f'{nid} output mute')


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
    prm = parse_params(node.get('params', ''))
    n_send = int(prm.get('fx_sends', 0) or 0)
    if n_send:
        # ── THE FX RETURNS' AUX SENDS (S23 gate 3) ──────────────────────
        #
        # `Fx[1-8]AuxOn[1-12]` and `Fx[1-8]AuxSend[1-12]`. This node sums
        # ONE aux bus, so it carries one column of that 6 x 12 grid: the
        # six returns' On flags then the six returns' Send levels, 12
        # words, and the cell's `fun` index is the AUX number while the
        # instance is the FX number.
        #
        # THE CELLS ARE NOT THIS NODE'S OWN CATEGORY, which is why they are
        # named explicitly rather than through `cat`: C2_MIX_* maps to no
        # master category (_NODE_PATTERNS returns None for it and always
        # has), and the cells belong to `Fx`. Same shape as expand_crossover,
        # which writes MainL/MainR/MainSub cells off one node.
        aux = int(prm.get('aux', 0) or 0)
        if not aux:
            sys.exit(f'ERROR: {nid} declares fx_sends={n_send} and no '
                     f'`aux=` param, so there is no aux number to index the '
                     f'Fx*AuxOn/AuxSend cells by. gen_dsp_csv.py writes it; '
                     f'refusing to guess which bus this node sums.')
        for x in range(1, n_send + 1):
            add_cell(cn('Fx', x, 'AuxOn', aux), chip, pg, base + (x - 1),
                     '', 'InstantCtl')
            add_dispatch(chip, base + (x - 1),
                         f'_mix_on_{nid} + {x-1}' if x > 1 else f'_mix_on_{nid}',
                         f'{nid} Fx{x} AuxOn')
        for x in range(1, n_send + 1):
            off = n_send + (x - 1)
            add_cell(cn('Fx', x, 'AuxSend', aux), chip, pg, base + off,
                     'dB:Off:-50@31:-30@63:-10@127:0', 'GainFast')
            add_dispatch(chip, base + off,
                         f'_mix_send_{nid} + {x-1}' if x > 1 else f'_mix_send_{nid}',
                         f'{nid} Fx{x} AuxSend')
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
    'OUTPUT_TDM':     expand_output_tdm,
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
# The four post-crossover output strips in master spelling. Declared HERE,
# above every use of it: the EQ expansion needs it (S24, EqHpf bands 2-4)
# and that runs long before the unmapped-reason table this used to sit in.
_MAIN_OUT = ('MainL', 'MainR', 'MainCtr', 'MainSub')

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
    # S24: THE OUTPUT NODE REACHES CELLS NOW. It used to be `None` because
    # the post-crossover chain had no word for the strip's own Level/Mute
    # (the Q1 reason in _UNMAPPED_REASONS); the OUTPUT_TDM node carries them
    # itself since S24, in a second SPI block allocated after every other
    # chip-2 address (`mo_page`/`mo_addr`), so it maps to the same master
    # strip its EQ/COMP/LIM already do.
    (re.compile(r'^C2_MAIN_OUT_(\d+)$'),
     lambda m: _main_out_strip(int(m.group(1)))),
    (re.compile(r'^C2_MIX_'),                                  lambda m: None),
    # Matrix outputs (Chip 2). The master gives Matrix[1-4] exactly Level,
    # Mute and Name -- no EQ, no delay, no limiter, no meter -- so the strip
    # is a FADER_PAN and an OUTPUT_TDM and nothing else. D24's def carries
    # `mtx,2` and reaches the first two; D32's reaches all four, at the same
    # addresses (decision D3: ONE address map).
    (re.compile(r'^C2_MTX_FDR_(\d+)$'),               lambda m: ('Matrix', int(m.group(1)))),
    (re.compile(r'^C2_MTX_OUT_(\d+)$'),               lambda m: None),
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
            #
            # OUTPUT_TDM is a NO-OP EXCEPT ON THE FOUR MAIN OUTPUTS (S24).
            # It stopped being expand_noop when the main outputs got their
            # own Level/Mute, and without this the aux/matrix/monitor/codec
            # output nodes -- which map to no master cell and never did --
            # would all start demanding an _UNREACHED_REASONS entry for a
            # state that has not changed. The marker is the same one the
            # expander itself keys on, so the two cannot drift: no
            # `mo_page`, no cells, nothing to explain.
            _out_noop = (expander is expand_output_tdm
                         and 'mo_page' not in parse_params(
                             node.get('params', '')))
            if spi_addr >= 0 and expander is not expand_noop and not _out_noop:
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
# Wire-unit conversions at the SPI boundary
#
# THE DEFECT THIS EXISTS FOR, measured on the part 2026-09-08:
# `_gate_hold_<nid>` is an integer SAMPLE COUNT (its initialiser is 2400 =
# 50 ms at 48 kHz) and the SPI handler stored the host's IEEE-754 float32
# word into it unconverted, so a host writing the documented 1.0 ms landed
# 0x3F800000 = 1,065,353,216 samples -- about six hours -- and the gate
# never closed again after its first signal. `_dly_read_offset_<nid>` has
# the same shape: 250.0 ms lands 0x437A0000 and is clamped to the buffer
# length, so every delay setting above about 1 ms saturates.
#
# IT IS NOT FIXED FOR HOLD. `defs/common/wire/wire-units.csv` is the LANDED
# declaration of what each family carries on the wire and what the kernel
# word expects, and this builds the conversion table FROM it: a family whose
# declared unit differs from the kernel word gets a conversion id, and every
# SPI address that family reaches carries it. A one-off for Hold would have
# left `ChanDelay` broken in exactly the same way, which is how it was found.
#
# WHAT IS NOT CONVERTED, AND WHY, is reported rather than skipped:
#   * the ms -> alpha rows (ChanCompAtt/Rel, ChanGateAtt/Rel) declare
#     "needs conversion declared" -- the contract states the mismatch and
#     not the conversion, and inventing one here would be this spoke
#     declaring cell semantics it does not own;
#   * ChanGateRng (dB -> linear, review D39) and ChanCompPar (percent ->
#     fraction, D40) are ALREADY converted in the node's control-rate prep,
#     so a second conversion at the wire would apply it twice;
#   * the bool folds and the readback rows are not wire conversions at all.
# ---------------------------------------------------------------------------

WIRE_CVT_NONE = 0
WIRE_CVT_MS_SAMPLES = 1

# (id, name, predicate over the wire-units row). Add a rule here and every
# address of every family the rule matches picks it up.
_WIRE_CVT_RULES = [
    (WIRE_CVT_MS_SAMPLES, 'ms -> samples',
     lambda unit, kernel: unit.strip().lower().startswith('ms')
     and 'samples' in kernel.lower()),
]

# Families whose declared mismatch the kernel already resolves in its
# control-rate prep. Converting at the wire as well would apply it twice.
_WIRE_CVT_ALREADY_IN_KERNEL = {'ChanGateRng', 'ChanCompPar'}


def _wire_units_rows():
    """The landed wire-units declaration, or {} if it cannot be read."""
    try:
        import wire_contract
        return wire_contract.load_units()
    except Exception as exc:                      # noqa: BLE001
        print(f'  WARNING: wire-units.csv unreadable ({exc}) — no wire-unit '
              f'conversions will be generated')
        return {}


def _family_keys(cell):
    """The keys wire-units.csv may be holding this cell under."""
    return [re.sub(r'\d+', '', cell)]            # Chan001GateHold001 -> ChanGateHold


def build_wire_convert_map():
    """{(chip, addr): conversion_id} plus a report of what was NOT converted.

    Driven entirely by the landed wire-units.csv and the landed address map;
    nothing about a specific cell is typed here.
    """
    units = _wire_units_rows()
    convert = {}
    applied = {}
    unresolved = []
    for family, row in sorted(units.items()):
        unit = (row.get('unit') or '').strip()
        kernel = (row.get('kernel_expects') or '').strip()
        if not unit or not kernel or unit == kernel:
            continue
        cvt = WIRE_CVT_NONE
        name = None
        for cid, cname, pred in _WIRE_CVT_RULES:
            if pred(unit, kernel):
                cvt, name = cid, cname
                break
        if cvt == WIRE_CVT_NONE:
            if family not in _WIRE_CVT_ALREADY_IN_KERNEL:
                unresolved.append((family, unit, kernel))
            continue
        hits = 0
        for cell, entry in cell_map.items():
            if family in _family_keys(cell):
                convert[(entry['chip'], entry['spi_addr'])] = cvt
                hits += 1
        applied[family] = (name, hits)
    return convert, applied, unresolved


def report_wire_conversions(applied, unresolved):
    if applied:
        print('  wire-unit conversions applied at the SPI boundary:')
        for family, (name, hits) in sorted(applied.items()):
            print(f'    {family:<18} {name:<16} {hits} addresses')
    if unresolved:
        print('  wire-unit mismatches DECLARED but NOT converted '
              '(the contract states the mismatch, not the conversion):')
        for family, unit, kernel in unresolved:
            print(f'    {family:<18} wire {unit!r} -> kernel {kernel!r}')


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


def _build_chip_params(chip_num, table_name, out_path, strides=None,
                       convert=None):
    """Build dsp_params.asm content for one chip."""
    chip_entries = {a: v for (c, a), v in dispatch.items() if c == chip_num}
    if not chip_entries:
        return None, 0
    strides = strides or {}
    convert = convert or {}

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

    # ---- Parallel wire-unit conversion table ----
    cvt_vals = [convert.get((chip_num, addr), WIRE_CVT_NONE)
                for addr in range(size)]
    cvt_n = sum(1 for v in cvt_vals if v)
    lines.append(f'/* ---- Chip {chip_num} wire-unit conversion table '
                 f'({size} entries) ---- */')
    lines.append('/*')
    lines.append(' * Companion to the dispatch table above, same indexing.')
    lines.append(' * The SPI handler applies this to the incoming word BEFORE')
    lines.append(' * the ramp/instant dispatch, because it is a UNIT change on')
    lines.append(' * the wire and everything downstream -- the ramp engine')
    lines.append(' * included -- has to see the word in the kernel\'s own unit.')
    lines.append(' *')
    lines.append(f'   *   {WIRE_CVT_NONE} -- no conversion')
    lines.append(f'   *   {WIRE_CVT_MS_SAMPLES} -- milliseconds (float32) -> '
                 'samples (integer, floored at 0)')
    lines.append(' *')
    lines.append(' * Generated from defs/common/wire/wire-units.csv, which is')
    lines.append(' * the landed declaration of what each family carries on the')
    lines.append(' * wire and what its kernel word expects. Nothing here names')
    lines.append(' * a cell: a family whose declared unit differs from its')
    lines.append(' * kernel word gets a conversion, and every address that')
    lines.append(' * family reaches carries it.')
    lines.append(' *')
    lines.append(f' * {cvt_n} of {size} addresses carry a conversion.')
    lines.append(' */')
    lines.append(f'.global {table_name}_convert;')
    lines.append(f'.var {table_name}_convert[{size}] =')
    for addr in range(size):
        entry = chip_entries.get(addr)
        comment = entry[1] if entry else ''
        comma = ',' if addr < size - 1 else ';'
        cmt = f'  /* 0x{addr:04X}: {comment} */' if comment else f'  /* 0x{addr:04X} */'
        lines.append(f'    {cvt_vals[addr]}{comma}{cmt}')
    lines.append('')

    # ---- Parallel RECOMPUTE (dirty) table ----
    dirty_vals = [dirty.get((chip_num, addr), 0) for addr in range(size)]
    dirty_n = sum(1 for v in dirty_vals if v)
    dirty_syms = sorted({v for v in dirty_vals if v})
    lines.append(f'/* ---- Chip {chip_num} recompute (dirty) table '
                 f'({size} entries) ---- */')
    lines.append('/*')
    lines.append(' * Companion to the dispatch table above, same indexing.')
    lines.append(' *   0   -- the written word IS the kernel word; nothing more')
    lines.append(' *          to do')
    lines.append(' *   sym -- the word is a DESIGN PARAMETER: the handler stores')
    lines.append(' *          1 at `sym` and the node recomputes on its next')
    lines.append(' *          block, then clears it')
    lines.append(' *')
    lines.append(' * A GEQ band gain is one number standing for five coefficient')
    lines.append(' * words, and a GEQ node has no address left for a swap trigger')
    lines.append(' * of the kind EQ_BIQUAD carries -- the contract spends all 28')
    lines.append(' * of its addresses on bands. This is how the kernel is told a')
    lines.append(' * gain arrived, instead of comparing every band against a')
    lines.append(' * shadow on every block of every node.')
    lines.append(' *')
    lines.append(f' * {dirty_n} of {size} addresses raise a flag; '
                 f'{len(dirty_syms)} distinct flags.')
    lines.append(' */')
    lines.append(f'.global {table_name}_dirty;')
    lines.append(f'.var {table_name}_dirty[{size}] =')
    for addr in range(size):
        entry = chip_entries.get(addr)
        comment = entry[1] if entry else ''
        comma = ',' if addr < size - 1 else ';'
        v = dirty_vals[addr] or '0'
        cmt = f'  /* 0x{addr:04X}: {comment} */' if comment else f'  /* 0x{addr:04X} */'
        lines.append(f'    {v}{comma}{cmt}')
    lines.append('')

    # The samples-per-millisecond constant the handler multiplies by, as
    # IEEE-754 float32 bits. GENERATED, not typed into the assembler: the
    # sample rate is a property of the build, and a conversion that quotes
    # it from two places is a conversion that can disagree with itself.
    spms = struct.unpack('<I', struct.pack('<f', SAMPLE_RATE_HZ / 1000.0))[0]
    lines.append('/* Samples per millisecond, IEEE-754 float32 bits '
                 f'({SAMPLE_RATE_HZ / 1000.0:g} at {SAMPLE_RATE_HZ:g} Hz). */')
    lines.append(f'.global {table_name}_spms;')
    lines.append(f'.var {table_name}_spms = 0x{spms:08X};')
    lines.append('')

    content = '\n'.join(lines) + '\n'
    return content, len(lines)


def write_dsp_params_asm(dry_run=False):
    """Generate per-chip SPI dispatch tables."""
    convert, applied, unresolved = build_wire_convert_map()
    report_wire_conversions(applied, unresolved)
    for chip_num, table_name, out_path, nodes_dir in [
        (1, '_spi_dispatch_c1', OUT_PARAMS_C1, NODES_DIR_C1),
        (2, '_spi_dispatch_c2', OUT_PARAMS_C2, NODES_DIR_C2),
    ]:
        strides = build_ramp_stride_map(nodes_dir)
        content, line_count = _build_chip_params(chip_num, table_name, out_path,
                                                 strides, convert)
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
    h_lines.append(f' * MW/D32/DSP/SHARC/shipping.config and REGENERATE: these counts')
    h_lines.append(f' * move with it, and so does the panel MCU copy of this file.')
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
_UNMAPPED_REASONS = {
    ('*', 'Name'): ('label', 'text label; the host stores it, the DSP has no word for it'),
    # PW RULING R4 (2026-09-10) — this is NOT a missing DSP function.
    # `Chan*AuxPick*` (four positions: PreEQ / PostEQ / PreFdr / PostFdr) is
    # the ONLY DSP truth and every channel is independent; `Aux*PickOff` is
    # an APP BATCH BUTTON that writes all channels for that aux, with no
    # word of its own and nothing for a kernel to read. So it stops being a
    # DSP function the graph has failed to build and becomes what it is.
    ('Aux', 'PickOff'): ('host-managed',
        'app batch control, not a DSP word: it writes every channel\'s '
        'Chan*AuxPick* for that aux, which is the only DSP truth '
        '(PW ruling R4, 2026-09-10 — was open question Q4)'),
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
    # PW RULING R5 (2026-09-10) — SPECIFIED, NOT BUILT, and the reason is
    # named rather than left as "no node". ONE pan table for the mixer:
    # 127 positions x (gL, gC, gR) in DM, `Sys[1-1]LcrLaw[1-1]` (a new defs
    # cell the hub lands) selects which law is loaded, every channel's Pan
    # is an INDEX into it, and `Chan*CtrOn` still gates the centre leg.
    ('Chan', 'LcrOn'): ('no-graph-node',
        'LCR per channel. The LAW is ruled (PW R5: one 127 x (gL,gC,gR) '
        'table, Sys[1]LcrLaw[1] selects it, Pan indexes it) and the cell '
        'that selects it has not landed in defs yet. Not built in S24 for '
        'a second reason worth stating: R5 amended puts NON-LCR channels on '
        'the same table too, so it changes the pan law of every strip on a '
        'chip whose code pool is at 90.7% — it needs its own gate and a '
        'pan-law witness, not a tail-end addition (S24)'),
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
    # PW RULING R1 (2026-09-10) — the cell is REAL and its meaning is
    # settled: ducking is a sidechain compressor on the return keyed from
    # the dry signal, `DuckThr` is the dry level in dB above which the
    # return is pulled down (-60..0) and `DuckSens` is the DEPTH of that
    # pull (0..-40), with attack/release fixed constants (~10 ms / 300 ms)
    # and no cells. Not built in S24: it is a new sidechain per return on
    # the chip whose worst-use row already overruns, so it is priced and
    # gated like any other chip-2 addition, not appended.
    ('Fx', 'DuckThr'): ('no-graph-node',
        'FX ducker threshold — the dry level in dB above which the return '
        'is pulled down, -60..0 (PW ruling R1, 2026-09-10; was Q7). The FX '
        'engine has DuckOn and DuckSens and no threshold word, and the '
        'ducking sidechain itself is unbuilt (S24)'),
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
    # S24: Level and Mute ARE built now -- the OUTPUT_TDM node carries them
    # in a second SPI block (expand_output_tdm), so they are no longer
    # unmapped and their Q1 entries are gone. DELAY is not, and its reason
    # is now the honest one: it is not a missing cell, it is a missing
    # delay LINE.
    _UNMAPPED_REASONS[(_s, 'Delay')] = ('no-graph-node',
        'post-crossover output chain {} has EQ + COMP + LIM + OUTPUT_TDM '
        'and no delay line. Level and Mute are built (S24); Delay is not, '
        'and the reason is memory rather than cells: the master asks for '
        '250 ms, which is 12,000 words = 48,000 bytes of chip-2 L2 per '
        'output, 192,000 for all four against 378,464 free on the S24 '
        'candidate (51%). It FITS and it is still PW\'s call, because it '
        'is half the delay headroom left on a chip whose worst-use row '
        'already overruns — measured, S24'.format(_s))
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


_GEQ_BAND_CELL = re.compile(r'^[A-Za-z]+\d+Geq(\d+)$')


def _unmapped_reason(cell, mcu_prefixes):
    """(class, reason) for a defined cell with no DSP address. No-fallback."""
    if cell in unbacked_meter_cells:
        return ('unbacked-meter', unbacked_meter_cells[cell])
    # A GEQ BAND ABOVE THE ADDRESS BLOCK, AND ONLY THOSE. The test is on
    # the band NUMBER, not on the family, so a band inside 1..GEQ_BANDS
    # that stopped reaching an address would still stop the generator --
    # which a family-wide ('Aux', 'Geq') entry would have hidden.
    gm = _GEQ_BAND_CELL.match(cell)
    if gm is not None and int(gm.group(1)) > GEQ_BANDS:
        return ('geq-band-beyond-block',
                f'GEQ band {int(gm.group(1))}: the cell master defines it and '
                f'the DSP address block is {GEQ_BANDS} words, packed end to '
                f'end against the node that follows it. Closing this needs '
                f'the graph regenerated at gen_dsp_csv.py --geq-bands N, '
                f'which re-lays every chip-2 address above the first GEQ '
                f'node; the sequence is in '
                f'MW/D32/DSP/dsp4-dspcsv-proposal-20260908.md section B')
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

# BUILDING FROM THE PROPOSAL, BEFORE THE HUB HAS LANDED IT. The gate is a
# handoff between two repos, and the dsp side of a release window cannot
# always wait on the far side of it: `DSP_LANDED_DIR=proposals/defs/products`
# points generation at the pair this repo just proposed instead of the pair
# defs carries. SAME BYTES, DIFFERENT PROVENANCE, and the difference is
# real -- nothing has gated these rows and the defs pin does not describe
# the image that comes out. So it says so, loudly, on every run, and the
# session that uses it says so in its status line. It is NOT a fallback:
# unset, generation reads defs and only defs, and the drift check is fatal
# exactly as before.
_LANDED_DIR_OVERRIDE = os.environ.get('DSP_LANDED_DIR')
if _LANDED_DIR_OVERRIDE:
    DEFS_PRODUCTS_DIR = os.path.abspath(
        os.path.join(REPO_ROOT, _LANDED_DIR_OVERRIDE))
    print('*' * 74)
    print('*  DSP_LANDED_DIR IS SET. The address map being generated from is')
    print(f'*  {DEFS_PRODUCTS_DIR}')
    print('*  -- NOT defs/products/. These rows have not passed the hub gate')
    print('*  and the defs pin in defs.lock does not describe this build.')
    print('*' * 74)


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


def check_proposal(fatal=True):
    """Prove the graph reproduces the LANDED dsp.csv/dsp-unmapped.csv for
    both products, row for row (every column dsp.csv declares — the header
    comment's pin stamp is proposal-authoring metadata and not compared).
    Fails loudly and exits nonzero on any drift.

    `fatal=False` returns the verdict instead of exiting, for the ONE
    caller entitled to a No: `--propose`, where the graph being ahead of
    the landed file is the whole reason a proposal is being written. Every
    other path keeps the no-fallback exit."""
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
        if not fatal:
            return False
        sys.exit('ERROR: the graph has drifted from the landed dsp.csv / '
                 'dsp-unmapped.csv contract in defs/products/<p>/. Fix: '
                 'propose a new dsp.csv to the hub gate — never hand-edit '
                 'the landed file, and never let generation quietly fall '
                 'back to the graph when it disagrees with what is landed.')
    print('  check-proposal OK — the graph reproduces the landed dsp.csv / '
          'dsp-unmapped.csv exactly for both products')
    return True


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

    # 3. AUTHOR THE PROPOSAL BEFORE JUDGING THE DRIFT, and only under
    # --propose. A proposal is written precisely when the graph is AHEAD
    # of the landed contract, so ordering the fatal drift check first made
    # --propose unreachable in the one situation it exists for: the flag
    # was added with the check above it and every run that needed it died
    # before reaching it. The propose path therefore takes the verdict as
    # a value and stops cleanly when the graph is ahead — it generates
    # NOTHING, because generation reads the landed file and the landed
    # file is the thing that has not caught up yet.
    if args.propose:
        print()
        print('Proposing dsp.csv...')
        proposals = write_proposals(dry_run=args.dry_run)
        report_proposals(proposals)
        print()
        print('Checking graph against landed defs/products/<p>/dsp.csv...')
        if not check_proposal(fatal=False):
            print()
            print('The graph is AHEAD of the landed contract — that is what '
                  'the proposal above is for.')
            print('Nothing generated: generation reads the LANDED '
                  'defs/products/<p>/dsp.csv, not the graph. Land the '
                  'proposal at the hub gate, advance the defs pin, then '
                  'run without --propose.')
            return
        print()
        print('The proposal matches what is already landed; nothing to gate.')
    else:
        # The graph must reproduce the landed contract byte-for-byte, or
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
        matrix_csv_dir = os.path.dirname(MATRIX_CSV)
        if matrix_csv_dir:
            os.makedirs(matrix_csv_dir, exist_ok=True)
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
