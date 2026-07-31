#!/usr/bin/env python3
"""gen_slot_map.py — DSP4 TDM slot-map generator (decision D2).

Single source: tdm-lines.csv (physical TDM line inventory) + slot-map.csv
(per-slot signal assignments). Emits BOTH consumers' views:

  generated/sport_map.json   — SPORT config consumed by tools/dsp/gen_dsp_csv.py
  generated/dsp4_slot_map.vh — Verilog constants for the LOGIC CPLD (MAX V)

Hand-editing either output is drift (same rule as all generated files in this
repo). Outputs are stamped with the SHA-256 of the two source CSVs; a CPLD
change is behaviourally a contract bump — pin this hash per
release-notes-contract-convention.md.

SPORT convention: sport_id = DAI port index (I0..I7 / O0..O7); I ports are
RX and O ports are TX on each chip. Chip 1 = DSPA (input engine), chip 2 =
DSPB (output engine). The MIX_* lines are the inter-chip fabric: DSPA O<n>
drives DSPB I<n> (8x TDM16 = 128 mix slots; global mix slot = 16*line + slot).
"""

import csv
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LINES_CSV = os.path.join(HERE, 'tdm-lines.csv')
SLOTS_CSV = os.path.join(HERE, 'slot-map.csv')
OUT_DIR = os.path.join(HERE, 'generated')

FORMATS = {'TDM8': 0, 'TDM16': 1, 'I2S': 2}
SCOPES = ('BOTH', 'D24', 'D32')


def fail(msg):
    sys.stderr.write(f'ERROR: {msg}\n')
    sys.exit(1)


def read_csv(path):
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def source_hash():
    h = hashlib.sha256()
    for path in (LINES_CSV, SLOTS_CSV):
        with open(path, 'rb') as f:
            h.update(f.read())
    return h.hexdigest()


def validate(lines, slots):
    by_id = {}
    for ln in lines:
        lid = ln['line_id']
        if lid in by_id:
            fail(f'duplicate line_id {lid}')
        if ln['format'] not in FORMATS:
            fail(f'{lid}: unknown format {ln["format"]}')
        if ln['scope'] not in SCOPES:
            fail(f'{lid}: bad scope {ln["scope"]}')
        a, b = ln['dspa_port'], ln['dspb_port']
        if lid.startswith('MIX_'):
            if not (a and b):
                fail(f'{lid}: MIX lines need both dspa_port and dspb_port')
            if a[0] != 'O' or b[0] != 'I' or a[1] != b[1]:
                fail(f'{lid}: MIX must be DSPA O<n> -> DSPB I<n> (got {a}/{b})')
        else:
            if bool(a) == bool(b):
                fail(f'{lid}: non-MIX lines need exactly one DSP port')
        by_id[lid] = ln

    seen_slot = {}   # (line, slot) -> set of scopes
    seen_sig = set() # (signal, scope)
    for row in slots:
        lid, sig, scope = row['line_id'], row['signal'], row['scope']
        if lid not in by_id:
            fail(f'slot row references unknown line {lid}')
        if scope not in SCOPES:
            fail(f'{lid}/{sig}: bad scope {scope}')
        slot = int(row['slot'])
        if not 0 <= slot < int(by_id[lid]['slot_count']):
            fail(f'{lid} slot {slot} out of range (slot_count '
                 f'{by_id[lid]["slot_count"]})')
        scopes = seen_slot.setdefault((lid, slot), set())
        if 'BOTH' in scopes or (scopes and scope == 'BOTH') or scope in scopes:
            fail(f'{lid} slot {slot}: overlapping scope assignment ({sig})')
        scopes.add(scope)
        if (sig, scope) in seen_sig:
            fail(f'duplicate signal {sig} (scope {scope})')
        seen_sig.add((sig, scope))
    return by_id


def line_entry(ln, slots, port):
    entry = {
        'line': ln['line_id'],
        'port': port,
        'sport_id': int(port[1]),
        'format': ln['format'],
        'slot_count': int(ln['slot_count']),
        'status': ln['status'],
    }
    if ln['external_net']:
        entry['external_net'] = ln['external_net']
    cp = ln['clock_pair_dspa'] if port == ln['dspa_port'] else ln['clock_pair_dspb']
    if cp:
        entry['clock_pair'] = cp
    entry['slots'] = [
        {k: v for k, v in
         (('slot', int(s['slot'])), ('signal', s['signal']),
          ('scope', s['scope']), ('note', s['note']))
         if v != ''}
        for s in slots if s['line_id'] == ln['line_id']
    ]
    return entry


def emit_json(lines, slots, src_hash):
    chips = {'1': {'rx': [], 'tx': []}, '2': {'rx': [], 'tx': []}}
    for ln in lines:
        if ln['dspa_port']:
            side = 'rx' if ln['dspa_port'][0] == 'I' else 'tx'
            chips['1'][side].append(line_entry(ln, slots, ln['dspa_port']))
        if ln['dspb_port']:
            side = 'rx' if ln['dspb_port'][0] == 'I' else 'tx'
            chips['2'][side].append(line_entry(ln, slots, ln['dspb_port']))
    for chip in chips.values():
        for side in chip.values():
            side.sort(key=lambda e: e['sport_id'])

    mix_lines = [ln for ln in lines if ln['line_id'].startswith('MIX_')]
    buses = []
    for ln in mix_lines:
        idx = int(ln['line_id'].split('_')[1])
        for s in slots:
            if s['line_id'] == ln['line_id']:
                buses.append({'signal': s['signal'],
                              'global_slot': 16 * idx + int(s['slot']),
                              'line': ln['line_id'],
                              'slot': int(s['slot'])})
    buses.sort(key=lambda b: b['global_slot'])

    doc = {
        'generated_by': 'shared/dsp4-logic/gen_slot_map.py',
        'source_hash': src_hash,
        'sport_convention': ('sport_id = DAI port index; I ports are RX, '
                             'O ports are TX; chip1=DSPA, chip2=DSPB'),
        'mix_fabric': {
            'lines': len(mix_lines),
            'slots_per_line': 16,
            'total_slots': 16 * len(mix_lines),
            'buses': buses,
        },
        'chips': chips,
    }
    path = os.path.join(OUT_DIR, 'sport_map.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(doc, f, indent=2)
        f.write('\n')
    return path


def vh_ident(s):
    return re.sub(r'[^A-Za-z0-9_]', '_', s)


def emit_vh(lines, slots, src_hash):
    mix_lines = [ln for ln in lines if ln['line_id'].startswith('MIX_')]
    out = []
    out.append('// dsp4_slot_map.vh — AUTO-GENERATED by '
               'shared/dsp4-logic/gen_slot_map.py — DO NOT EDIT')
    out.append(f'// source_hash: sha256:{src_hash}')
    out.append('// Source: tdm-lines.csv + slot-map.csv (decision D2: '
               'single-sourced TDM slot map)')
    out.append('')
    out.append('// TDM formats')
    out.append('localparam [1:0] FMT_TDM8  = 2\'d0;')
    out.append('localparam [1:0] FMT_TDM16 = 2\'d1;')
    out.append('localparam [1:0] FMT_I2S   = 2\'d2;')
    out.append('')
    out.append('// Inter-chip mix fabric geometry')
    out.append(f'localparam integer NUM_MIX_LINES     = {len(mix_lines)};')
    out.append('localparam integer MIX_SLOTS_PER_LINE = 16;')
    out.append(f'localparam integer NUM_MIX_SLOTS     = {16 * len(mix_lines)};')
    out.append('')
    out.append('// Per-line DSP-facing format')
    for ln in lines:
        out.append(f'localparam [1:0] FMT_{vh_ident(ln["line_id"])} = '
                   f'FMT_{ln["format"]};'
                   + (f'  // {ln["status"]}' if ln['status'] != 'ok' else ''))
    out.append('')
    out.append('// DSPB output line -> DA lane routing (from schematic review:')
    out.append('// B_O1 drives DA3, NOT DA1 — DA1 dead-ends at Digital J18)')
    for ln in lines:
        m = re.fullmatch(r'DA(\d)', ln['external_net'])
        if m:
            out.append(f'localparam integer DA_LANE_{vh_ident(ln["line_id"])} '
                       f'= {m.group(1)};')
    out.append('')
    out.append('// Global mix slot indices (16*line + slot); '
               'unlisted slots reserved')
    for ln in mix_lines:
        idx = int(ln['line_id'].split('_')[1])
        for s in slots:
            if s['line_id'] == ln['line_id']:
                out.append(f'localparam integer MIXSLOT_{vh_ident(s["signal"])} '
                           f'= {16 * idx + int(s["slot"])};')
    out.append('')
    path = os.path.join(OUT_DIR, 'dsp4_slot_map.vh')
    with open(path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    return path


def main():
    lines = read_csv(LINES_CSV)
    slots = read_csv(SLOTS_CSV)
    validate(lines, slots)
    os.makedirs(OUT_DIR, exist_ok=True)
    src_hash = source_hash()
    jp = emit_json(lines, slots, src_hash)
    vp = emit_vh(lines, slots, src_hash)
    n_mix = sum(1 for s in slots if s['line_id'].startswith('MIX_'))
    print(f'source_hash sha256:{src_hash[:16]}…')
    print(f'  {len(lines)} TDM lines, {len(slots)} slot assignments '
          f'({n_mix} mix buses of 128)')
    print(f'  wrote {os.path.relpath(jp, HERE)}')
    print(f'  wrote {os.path.relpath(vp, HERE)}')


if __name__ == '__main__':
    main()
