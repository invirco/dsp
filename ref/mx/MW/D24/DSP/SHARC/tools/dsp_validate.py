#!/usr/bin/env python3
"""dsp_validate.py — Validates dsp.csv signal graph for the ADSP-21564 mixer DSP.

Usage: python3 dsp_validate.py [path/to/dsp.csv]
       Default: dsp.csv in the same directory as this script's parent.

Exit code 0 = valid, 1 = errors found.
"""

import csv
import sys
import os
from collections import defaultdict

VALID_TYPES = {
    'INPUT_TDM', 'OUTPUT_TDM', 'GAIN', 'EQ_BIQUAD', 'EQ_MASTER', 'FIR',
    'COMPRESSOR', 'GATE', 'LIMITER', 'MIX_BUS', 'DELAY', 'ROUTER',
    'REVERB', 'ASRC', 'INTERCHIP_SEND', 'INTERCHIP_RECV',
}

SOURCE_TYPES = {'INPUT_TDM', 'INTERCHIP_RECV'}
SINK_TYPES = {'OUTPUT_TDM', 'INTERCHIP_SEND'}

REQUIRED_PARAMS = {
    'INPUT_TDM': ['sport_id', 'slot_start', 'slot_count'],
    'OUTPUT_TDM': ['sport_id', 'slot_start', 'slot_count'],
    'INTERCHIP_SEND': ['sport_id', 'slot'],
    'INTERCHIP_RECV': ['sport_id', 'slot'],
    'MIX_BUS': ['bus_id'],
}


def parse_id_list(cell):
    """Parse a semicolon-separated list of IDs from a CSV cell."""
    cell = cell.strip().strip('"')
    if not cell:
        return []
    return [x.strip() for x in cell.split(';') if x.strip()]


def parse_params(cell):
    """Parse key=value params from a semicolon-separated cell."""
    cell = cell.strip().strip('"')
    if not cell:
        return {}
    params = {}
    for pair in cell.split(';'):
        pair = pair.strip()
        if '=' in pair:
            k, v = pair.split('=', 1)
            params[k.strip()] = v.strip()
    return params


def validate(csv_path):
    errors = []
    warnings = []

    if not os.path.isfile(csv_path):
        print(f"ERROR: File not found: {csv_path}", file=sys.stderr)
        return 1

    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("ERROR: dsp.csv is empty", file=sys.stderr)
        return 1

    nodes = {}
    for i, row in enumerate(rows, start=2):  # line 1 = header
        nid = row.get('id', '').strip()
        if not nid:
            errors.append(f"Line {i}: missing 'id'")
            continue
        if nid in nodes:
            errors.append(f"Line {i}: duplicate id '{nid}' (first seen at line {nodes[nid]['line']})")
            continue
        nodes[nid] = {
            'line': i,
            'chip': row.get('chip', '').strip(),
            'type': row.get('type', '').strip(),
            'label': row.get('label', '').strip(),
            'ch_count': row.get('ch_count', '').strip(),
            'inputs': parse_id_list(row.get('inputs', '')),
            'outputs': parse_id_list(row.get('outputs', '')),
            'spi_page': row.get('spi_page', '-1').strip(),
            'spi_addr': row.get('spi_addr', '-1').strip(),
            'params': parse_params(row.get('params', '')),
        }

    # --- Validation rules ---

    spi_addrs_chip = defaultdict(list)

    for nid, n in nodes.items():
        line = n['line']

        # Rule 2: valid chip
        if n['chip'] not in ('1', '2'):
            errors.append(f"Line {line} [{nid}]: invalid chip '{n['chip']}' (must be 1 or 2)")

        # Rule 3: valid type
        if n['type'] not in VALID_TYPES:
            errors.append(f"Line {line} [{nid}]: unknown type '{n['type']}'")

        # Rule 5: ch_count must be a positive int
        try:
            ch = int(n['ch_count'])
            if ch < 1:
                raise ValueError
        except ValueError:
            errors.append(f"Line {line} [{nid}]: invalid ch_count '{n['ch_count']}'")

        # Rule 4: input references exist
        for ref in n['inputs']:
            if ref not in nodes:
                errors.append(f"Line {line} [{nid}]: input '{ref}' does not exist")

        # Rule 4: output references exist
        for ref in n['outputs']:
            if ref not in nodes:
                errors.append(f"Line {line} [{nid}]: output '{ref}' does not exist")

        # Rule 7: source nodes must have empty inputs
        if n['type'] in SOURCE_TYPES and n['inputs']:
            errors.append(f"Line {line} [{nid}]: {n['type']} must have empty inputs (has {n['inputs']})")

        # Rule 8: sink nodes must have empty outputs
        if n['type'] in SINK_TYPES and n['outputs']:
            errors.append(f"Line {line} [{nid}]: {n['type']} must have empty outputs (has {n['outputs']})")

        # Rule 13: no orphan nodes
        if not n['inputs'] and not n['outputs']:
            errors.append(f"Line {line} [{nid}]: orphan node — no inputs or outputs")

        # Rule 12: required params
        if n['type'] in REQUIRED_PARAMS:
            for rp in REQUIRED_PARAMS[n['type']]:
                if rp not in n['params']:
                    errors.append(f"Line {line} [{nid}]: missing required param '{rp}' for type {n['type']}")

        # Rule 14: no cross-chip audio links (except INTERCHIP)
        if n['type'] not in ('INTERCHIP_SEND', 'INTERCHIP_RECV'):
            for ref in n['inputs']:
                if ref in nodes and nodes[ref]['chip'] != n['chip']:
                    if nodes[ref]['type'] not in ('INTERCHIP_SEND', 'INTERCHIP_RECV'):
                        errors.append(f"Line {line} [{nid}]: cross-chip audio link to '{ref}' (use INTERCHIP nodes)")
            for ref in n['outputs']:
                if ref in nodes and nodes[ref]['chip'] != n['chip']:
                    if nodes[ref]['type'] not in ('INTERCHIP_SEND', 'INTERCHIP_RECV'):
                        errors.append(f"Line {line} [{nid}]: cross-chip audio link to '{ref}' (use INTERCHIP nodes)")

        # Collect SPI addresses for uniqueness check
        try:
            sp = int(n['spi_page'])
            sa = int(n['spi_addr'])
            if sp >= 0 and sa >= 0:
                spi_addrs_chip[(n['chip'], sp, sa)].append(nid)
        except ValueError:
            pass

    # Rule 6: bidirectional link check
    for nid, n in nodes.items():
        for ref in n['outputs']:
            if ref in nodes and nid not in nodes[ref]['inputs']:
                warnings.append(f"[{nid}] lists '{ref}' as output, but '{ref}' does not list '{nid}' as input")
        for ref in n['inputs']:
            if ref in nodes and nid not in nodes[ref]['outputs']:
                warnings.append(f"[{nid}] lists '{ref}' as input, but '{ref}' does not list '{nid}' as output")

    # Rule 10: INTERCHIP pairs
    sends = {nid: n for nid, n in nodes.items() if n['type'] == 'INTERCHIP_SEND'}
    recvs = {nid: n for nid, n in nodes.items() if n['type'] == 'INTERCHIP_RECV'}

    send_slots = {}
    for nid, n in sends.items():
        slot = n['params'].get('slot')
        sport = n['params'].get('sport_id')
        if slot is not None and sport is not None:
            key = (sport, slot)
            send_slots[key] = nid

    recv_slots = {}
    for nid, n in recvs.items():
        slot = n['params'].get('slot')
        sport = n['params'].get('sport_id')
        if slot is not None and sport is not None:
            key = (sport, slot)
            recv_slots[key] = nid

    for key, sid in send_slots.items():
        if key not in recv_slots:
            errors.append(f"[{sid}]: INTERCHIP_SEND sport={key[0]} slot={key[1]} has no matching INTERCHIP_RECV")

    for key, rid in recv_slots.items():
        if key not in send_slots:
            errors.append(f"[{rid}]: INTERCHIP_RECV sport={key[0]} slot={key[1]} has no matching INTERCHIP_SEND")

    # Rule 11: SPI address uniqueness
    for (chip, page, addr), nids in spi_addrs_chip.items():
        if len(nids) > 1:
            errors.append(f"Chip {chip}: duplicate SPI address page={page} addr={addr} used by: {', '.join(nids)}")

    # --- Output ---
    for w in warnings:
        print(f"WARNING: {w}")
    for e in errors:
        print(f"ERROR: {e}")

    total_nodes = len(nodes)
    chip1 = sum(1 for n in nodes.values() if n['chip'] == '1')
    chip2 = sum(1 for n in nodes.values() if n['chip'] == '2')

    print(f"\n--- Summary ---")
    print(f"Total nodes: {total_nodes} (Chip 1: {chip1}, Chip 2: {chip2})")
    print(f"Errors: {len(errors)}")
    print(f"Warnings: {len(warnings)}")

    if errors:
        print("\nVALIDATION FAILED")
        return 1
    else:
        print("\nVALIDATION PASSED")
        return 0


if __name__ == '__main__':
    if len(sys.argv) > 1:
        path = sys.argv[1]
    else:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(script_dir, '..', 'dsp.csv')
    sys.exit(validate(path))
