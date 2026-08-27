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
DSP_CSV    = os.path.join(SCRIPT_DIR, 'SHARC', 'dsp.csv')
MATRIX_CSV = os.path.join(SCRIPT_DIR, '..', 'MX', '_matrix.csv')

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


def add_cell(cell_name, chip, spi_page, spi_addr, table='', ramp_profile='', notes=''):
    cell_map[cell_name] = {
        'chip': int(chip),
        'spi_page': int(spi_page),
        'spi_addr': int(spi_addr),
        'table': table,
        'ramp_profile': ramp_profile,
        'notes': notes,
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
    # 4 SPI words: level + pan + mute + dca_coeff

    # Level cell naming varies by context
    level_suffix = 'RtgLevel'
    pan_suffix = 'RtgPan' if cat == 'Chan' else 'Pan'
    mute_suffix = 'RtgMute'

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

    add_cell(cn(cat, inst, 'RtgDca', 1), chip, pg, base + 3, '', 'InstantCtl',
             notes='DCA assignment')
    add_dispatch(chip, base + 3, f'_fdr_dca_gain_{nid}', f'{nid} DCA gain')


# ── ROUTING (channel strip fan-out) ──────────────────────────────────────
def expand_routing(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # 60 SPI words: main_on + sub_on + grp_on×4 + aux_on×12 + aux_send×12
    # + aux_pick×12 + fx_on×6 + fx_send×6 + fx_pick×6
    off = 0
    add_cell(cn(cat, inst, 'RtgMainOn', 1), chip, pg, base + off, '', 'InstantCtl')
    add_dispatch(chip, base + off, f'_rtg_main_on_{nid}', f'{nid} MainOn')
    off += 1

    add_cell(cn(cat, inst, 'RtgCtrOn', 1), chip, pg, base + off, '', 'InstantCtl')
    add_dispatch(chip, base + off, f'_rtg_sub_on_{nid}', f'{nid} SubOn')
    off += 1

    for g in range(1, 5):
        add_cell(cn(cat, inst, 'RtgGrpOn', g), chip, pg, base + off, '', 'InstantCtl')
        add_dispatch(chip, base + off, f'_rtg_grp_on_{nid} + {g-1}', f'{nid} GrpOn[{g}]')
        off += 1

    for a in range(1, 13):
        add_cell(cn(cat, inst, 'RtgAuxOn', a), chip, pg, base + off, '', 'InstantCtl')
        add_dispatch(chip, base + off, f'_rtg_aux_on_{nid} + {a-1}', f'{nid} AuxOn[{a}]')
        off += 1

    for a in range(1, 13):
        add_cell(cn(cat, inst, 'RtgAuxSend', a), chip, pg, base + off,
                 'dB:Off:-50@31:-30@63:-10@127:0', 'GainFast')
        add_dispatch(chip, base + off, f'_rtg_aux_send_{nid} + {a-1}', f'{nid} AuxSend[{a}]')
        off += 1

    for a in range(1, 13):
        add_cell(cn(cat, inst, 'RtgAuxPick', a), chip, pg, base + off,
                 '', 'InstantCtl', notes='Pickoff: 0=PreEQ 1=PostEQ 2=PreFdr 3=PostFdr')
        add_dispatch(chip, base + off, f'_rtg_aux_pick_{nid} + {a-1}', f'{nid} AuxPick[{a}]')
        off += 1

    for x in range(1, 7):
        add_cell(cn(cat, inst, 'RtgFx', x), chip, pg, base + off, '', 'InstantCtl')
        add_dispatch(chip, base + off, f'_rtg_fx_on_{nid} + {x-1}', f'{nid} FxOn[{x}]')
        off += 1

    for x in range(1, 7):
        add_cell(cn(cat, inst, 'RtgFxSend', x), chip, pg, base + off,
                 'dB:Off:-50@31:-30@63:-10@127:0', 'GainFast')
        add_dispatch(chip, base + off, f'_rtg_fx_send_{nid} + {x-1}', f'{nid} FxSend[{x}]')
        off += 1

    for x in range(1, 7):
        add_cell(cn(cat, inst, 'RtgFxPick', x), chip, pg, base + off,
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
def expand_meter(node, cat, inst):
    chip, pg, base, nid, ramp = _parse_node(node)
    # Meter layout depends on context
    if cat == 'AaChan':
        # 4 words per channel: post_trim, post_fader, gate_gr, comp_gr
        add_cell(cn(cat, inst, 'Mtr', 1), chip, pg, base, '', '', notes='Post trim level')
        add_cell(cn(cat, inst, 'Mtr', 2), chip, pg, base + 1, '', '', notes='Post fader level')
        add_cell(cn(cat, inst, 'GateMtr', 1), chip, pg, base + 2, '', '', notes='Gate GR')
        add_cell(cn(cat, inst, 'CompMtr', 1), chip, pg, base + 3, '', '', notes='Comp GR')
        add_dispatch(chip, base, f'_mtr_peak_{nid}', f'{nid} post_trim')
        add_dispatch(chip, base + 1, f'_mtr_rms_{nid}', f'{nid} post_fader')
        add_dispatch(chip, base + 2, f'_mtr_gr_{nid}', f'{nid} gate_gr')
        add_dispatch(chip, base + 3, None, f'{nid} comp_gr')
    else:
        # Bus/output meters: 1-2 words
        taps = node.get('params', '')
        if 'taps=L;R' in taps:
            add_cell(cn(cat, inst, 'Mtr', 1), chip, pg, base, '', '', notes='L')
            add_cell(cn(cat, inst, 'Mtr', 2), chip, pg, base + 1, '', '', notes='R')
            add_dispatch(chip, base, f'_mtr_peak_{nid}', f'{nid} L')
            add_dispatch(chip, base + 1, f'_mtr_rms_{nid}', f'{nid} R')
        else:
            add_cell(cn(cat, inst, 'Mtr', 1), chip, pg, base, '', '')
            add_dispatch(chip, base, f'_mtr_peak_{nid}', f'{nid}')


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
            add_cell(cn(cat, inst, 'Rtg', r), chip, pg, base + off, '', 'InstantCtl')
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
    add_cell(cn(cat, inst, 'CrossoverFreq', 1), chip, pg, base,
             '0=50/127=500/[Log]', 'EqSafe')
    add_cell(cn(cat, inst, 'CrossoverSlope', 1), chip, pg, base,
             '0=6/3=24/[Lin]', 'InstantCtl', notes='MCU-computed, shares base')

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

_NODE_PATTERNS = [
    # Channel strip (Chip 1)
    (re.compile(r'^C1_IN_(\d+)$'),                     lambda m: None),  # TDM input, no cells
    (re.compile(rf'^C1_(?:{_CHAN_TYPES})_(\d+)$'),     lambda m: ('Chan', int(m.group(1)))),
    (re.compile(r'^C1_MTR_(\d+)$'),                    lambda m: ('AaChan', int(m.group(1)))),
    (re.compile(r'^C1_TALK_(\d+)$'),                   lambda m: ('Talk', int(m.group(1)))),
    (re.compile(r'^C1_NOISE$'),                        lambda m: ('Noise', 1)),
    (re.compile(r'^C1_BUS_'),                          lambda m: None),  # skip bus cells
    # Aux (Chip 2)
    (re.compile(rf'^C2_AUX_(?:{_AUX_TYPES})_(\d+)$'), lambda m: ('Aux', int(m.group(1)))),
    (re.compile(r'^C2_AUX_OUT_(\d+)$'),               lambda m: None),
    # Group (Chip 2)
    (re.compile(rf'^C2_GRP_(?:{_GRP_TYPES})_(\d+)$'), lambda m: ('Grp', int(m.group(1)))),
    # Sub (Chip 2)
    (re.compile(r'^C2_SUB_(?:FDR|EQ|COMP|LIM|DLY)$'), lambda m: ('Sub', 1)),
    (re.compile(r'^C2_SUB_OUT$'),                      lambda m: None),
    # Main (Chip 2)
    (re.compile(r'^C2_MAIN_(?:FDR|GEQ|COMP|LIM|DLY|XOVER)$'), lambda m: ('Main', 1)),
    (re.compile(r'^C2_MAIN_O(?:EQ|COMP|LIM)_(\d+)$'),         lambda m: ('Main', int(m.group(1)))),
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
    # Output meters
    (re.compile(r'^C2_MTR_AUX_(\d+)$'),                lambda m: ('AaAux', int(m.group(1)))),
    (re.compile(r'^C2_MTR_MAIN_(\d+)$'),               lambda m: ('AaMain', int(m.group(1)))),
    (re.compile(r'^C2_MTR_GRP_(\d+)$'),                lambda m: ('AaGrp', int(m.group(1)))),
    (re.compile(r'^C2_MTR_SUB$'),                      lambda m: ('AaSub', 1)),
    (re.compile(r'^C2_MTR_FX_(\d+)$'),                 lambda m: ('AaFx', int(m.group(1)))),
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

        expander = NODE_EXPANDERS.get(ntype)
        if expander is None:
            print(f'  WARNING: no expander for node type {ntype} ({nid})', file=sys.stderr)
            continue

        if ctx is None:
            # Node doesn't map to cells — may still need dispatch (e.g. MIX_BUS)
            if spi_addr >= 0 and expander is not expand_noop:
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

    matched = 0
    cleared = 0
    for row in rows:
        cell_name = row.get('_Cell', '')
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
# ---------------------------------------------------------------------------
_RAMP_TARGET_RE = re.compile(
    r'^\.var\s+(_\w+?)_target_(\w+?)(?:\[(\d+)\])?\s*[;=]', re.M)


def build_ramp_stride_map(nodes_dir):
    """Map a ramped value symbol -> stride to its target/step/frames words."""
    if not os.path.isdir(nodes_dir):
        raise FileNotFoundError(
            f"node ASM directory not found: {nodes_dir}. The ramp stride "
            f"table is derived from the emitted node ASM, so dsp_codegen.py "
            f"must run before gen_dsp.py (see regenerate-dsp-contract.sh).")
    strides = {}
    for name in sorted(os.listdir(nodes_dir)):
        if not name.endswith('.asm'):
            continue
        with open(os.path.join(nodes_dir, name), encoding='utf-8') as f:
            text = f.read()
        for base, nid, count in _RAMP_TARGET_RE.findall(text):
            value_sym = f'{base}_{nid}'
            stride = int(count) if count else 1
            prev = strides.get(value_sym)
            if prev is not None and prev != stride:
                raise ValueError(
                    f"conflicting ramp stride for {value_sym}: {prev} vs "
                    f"{stride} (in {name})")
            strides[value_sym] = stride
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
    frame_667us    = 0.667  # ms per frame at 48 kHz / 32 samples

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
    c_lines.append(' */')
    c_lines.append('#include "ghost_cells.h"')
    c_lines.append('')
    c_lines.append(f'const CellDef ghost_cells[{n}] = {{')

    for i, (name, cm) in enumerate(sorted_cells):
        rp         = RAMP_PROFILES.get(cm['ramp_profile'], RAMP_PROFILES[''])
        mode_int   = ramp_mode_map.get(rp['mode'], 0)
        scope_int  = ramp_scope_map.get(rp['scope'], 0)
        up_frames  = round(rp['up_ms']   / frame_667us) if rp['up_ms']   > 0 else 0
        down_frames= round(rp['down_ms'] / frame_667us) if rp['down_ms'] > 0 else 0
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
        with open(OUT_ADDR_MAP, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'  Wrote {OUT_ADDR_MAP}')


# ---------------------------------------------------------------------------
# Cross-reference validation
# ---------------------------------------------------------------------------
def validate(matrix_rows):
    """Warn on cells present in one source but not the other."""
    matrix_names = {r['_Cell'] for r in matrix_rows if r.get('_Cell')}

    in_map_not_matrix = set(cell_map.keys()) - matrix_names
    in_matrix_no_dsp = set()
    for name in matrix_names:
        # Skip known MCU-only prefixes
        if any(name.startswith(p) for p in ('Sys', 'Fdr', 'Zz', 'Another', 'Mute', 'Rec')):
            continue
        if name not in cell_map:
            in_matrix_no_dsp.add(name)

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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='§17 build tool for D32 DSP')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print planned assignments without writing files')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite existing non-empty fields in _matrix.csv')
    args = parser.parse_args()

    print('gen_dsp.py — §17 D32 DSP build tool')
    print()

    # 1. Read dsp.csv
    print('Reading dsp.csv...')
    nodes = read_dsp_csv()
    print(f'  {len(nodes)} nodes')

    # 2. Expand all nodes
    print('Expanding node parameters...')
    expand_all_nodes(nodes)
    print(f'  {len(cell_map)} cell mappings')
    print(f'  {len(dispatch)} dispatch entries')

    # 3. Read _matrix.csv
    print('Reading _matrix.csv...')
    header, matrix_rows = read_matrix_csv()
    print(f'  {len(matrix_rows)} rows')

    # 4. Backfill _matrix.csv
    print('Backfilling _matrix.csv...')
    matched, cleared = backfill_matrix(header, matrix_rows, force=args.force)
    print(f'  {matched} cells matched and backfilled')
    if cleared:
        print(f'  {cleared} stale DSP column entries cleared')

    # 5. Write outputs
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

    # 6. Validation
    print()
    print('Validation:')
    validate(matrix_rows)

    print()
    print('Done.')


if __name__ == '__main__':
    main()
