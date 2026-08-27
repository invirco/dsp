#!/usr/bin/env python3
"""dsp_validate.py — Validate dsp.csv for the D32 SHARC+ DSP project.

Usage: python3 dsp_validate.py [path/to/dsp.csv]
       Default: ../dsp.csv (relative to this script)

Exit codes:
  0  — no errors
  1  — validation errors found

Checks:
  1. All required columns are present
  2. Node IDs are unique and non-empty
  3. chip is '1' or '2'
  4. type is a known node type
  5. ramp_profile is a known profile or empty
  6. ch_count is a positive integer
  7. spi_page/spi_addr are integers; INPUT_TDM and TDM outputs may use -1
  8. SPI (chip, page, addr) tuples are unique among nodes with valid addresses
  9. inputs and outputs reference valid node IDs
 10. Required params are present for each node type
"""

import csv
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csv_fields import parse_id_list, parse_params

# ---------------------------------------------------------------------------
REQUIRED_COLUMNS = {'id', 'chip', 'type', 'ch_count', 'inputs', 'outputs',
                    'spi_page', 'spi_addr', 'params', 'ramp_profile'}

VALID_TYPES = {
    'ANTI_FB', 'AUX_INPUT', 'COMPRESSOR', 'CROSSOVER', 'DCA', 'DELAY',
    'EQ_BIQUAD', 'FADER_PAN', 'FX_ENGINE', 'GAIN', 'GATE', 'GEQ',
    'HPF_LPF', 'INPUT_TDM', 'INTERCHIP_RECV', 'INTERCHIP_SEND', 'LIMITER',
    'METER', 'MIX_BUS', 'MONITOR', 'NOISE_GEN', 'OUTPUT_TDM', 'ROUTING',
    'TALKBACK', 'TUBE_SAT',
}

VALID_RAMP_PROFILES = {'', 'DynSafe', 'EqSafe', 'GainFast', 'GainSafe', 'InstantCtl'}

# Minimum required param keys per node type
REQUIRED_PARAMS = {
    'INPUT_TDM':      {'sport_id', 'slot_start', 'slot_count'},
    'OUTPUT_TDM':     {'sport_id', 'slot_start', 'slot_count'},
    'INTERCHIP_RECV': {'sport_id', 'slot'},
    'INTERCHIP_SEND': {'sport_id', 'slot'},
    'GAIN':           {'gain_db', 'mute', 'polarity'},
    'HPF_LPF':        {'hpf_freq', 'hpf_slope', 'lpf_freq'},
    'EQ_BIQUAD':      {'bands'},
    'GATE':           {'threshold_db', 'attack_ms', 'release_ms', 'hold_ms', 'range_db'},
    'COMPRESSOR':     {'threshold_db', 'ratio', 'attack_ms', 'release_ms', 'knee_db', 'makeup_db'},
    'DELAY':          {'delay_ms', 'max_ms'},
    'FADER_PAN':      {'level_db', 'mute'},       # pan is optional (absent on mono bus faders)
    'ROUTING':        {'aux_on', 'grp_on', 'main_on', 'sub_on'},
    'MIX_BUS':        {'bus_id'},                 # source_count is informational, not always set
    'GEQ':            {'bands'},
    'ANTI_FB':        {'notch_count'},
    'FX_ENGINE':      {'type'},
    'LIMITER':        {'threshold_db', 'attack_ms', 'release_ms'},
    'CROSSOVER':      {'freq', 'slope'},
    'TUBE_SAT':       {'saturation'},
    'TALKBACK':       {'gain_db', 'route'},
    'METER':          set(),                      # taps is optional (only L/R main meters set it)
    'DCA':            {'level_db', 'mute'},
    'NOISE_GEN':      {'level_db', 'on'},
    'MONITOR':        {'source'},
}

# Types that legitimately have no SPI address
NO_SPI_TYPES = {'INPUT_TDM', 'OUTPUT_TDM', 'INTERCHIP_RECV', 'INTERCHIP_SEND',
                'METER', 'TALKBACK', 'NOISE_GEN'}

# Optional param keys seen in practice, beyond REQUIRED_PARAMS, per node type.
# Anything outside REQUIRED_PARAMS | EXTRA_PARAMS for a type is flagged as an
# unrecognized param key rather than passed through silently.
EXTRA_PARAMS = {
    'AUX_INPUT':      {'level_db', 'on', 'scope'},
    'COMPRESSOR':     {'det_src', 'eq_pos', 'filter_hpf', 'filter_lpf',
                        'filter_on', 'filter_q', 'key', 'lim_mode',
                        'parallel', 'type'},
    'DELAY':          {'local_ms', 'pool_slot'},
    'EQ_BIQUAD':      {'coeffs'},
    'FADER_PAN':      {'pan'},
    'FX_ENGINE':      {'balance', 'damping', 'decay', 'delay_ms', 'duck_on',
                        'duck_sens', 'eq_hi', 'eq_lo', 'eq_mid', 'feedback',
                        'hpf', 'mix', 'mod_level', 'mod_rate',
                        'predelay_ms', 'room_size'},
    'GATE':           {'det_src', 'filter_hpf', 'filter_lpf', 'filter_on',
                        'filter_q', 'key'},
    'INPUT_TDM':      {'scope', 'signal', 'sport_slots'},
    'INTERCHIP_RECV': {'global_slot', 'scope', 'signal', 'sport_slots'},
    'INTERCHIP_SEND': {'global_slot', 'scope', 'signal', 'sport_slots'},
    'METER':          {'taps'},
    'MIX_BUS':        {'source_count'},
    'MONITOR':        {'level_l_db', 'level_r_db'},
    'NOISE_GEN':      {'hpf_on'},
    'OUTPUT_TDM':     {'scope', 'signal', 'sport_slots'},
    'ROUTING':        {'fx_on'},
    'TALKBACK':       {'hpf_on'},
    'TUBE_SAT':       {'on'},
}

ALLOWED_PARAMS = {t: REQUIRED_PARAMS.get(t, set()) | EXTRA_PARAMS.get(t, set())
                   for t in VALID_TYPES}


def validate(csv_path):
    errors = []
    warnings = []

    def err(row_num, node_id, msg):
        errors.append(f"  Row {row_num} [{node_id}]: {msg}")

    def warn(row_num, node_id, msg):
        warnings.append(f"  Row {row_num} [{node_id}]: {msg}")

    # ── Read file ────────────────────────────────────────────────────────────
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            print("ERROR: CSV file is empty or unreadable")
            return 1
        columns = set(reader.fieldnames)
        rows = list(reader)

    # ── Check 1: Required columns ────────────────────────────────────────────
    missing_cols = REQUIRED_COLUMNS - columns
    if missing_cols:
        print(f"FATAL: Missing required columns: {sorted(missing_cols)}")
        return 1

    # ── Parse all rows ───────────────────────────────────────────────────────
    all_ids = set()
    spi_addresses = {}  # (chip, page, addr) → node_id
    duplicate_rows = set()  # row_num of rows rejected as duplicate IDs

    for row_num, row in enumerate(rows, start=2):  # row 1 = header
        nid = row['id'].strip()
        chip = row['chip'].strip()
        ntype = row['type'].strip()
        ramp = row['ramp_profile'].strip()
        ch_count_str = row['ch_count'].strip()
        spi_page_str = row['spi_page'].strip()
        spi_addr_str = row['spi_addr'].strip()
        params = parse_params(row.get('params', ''))
        inputs = parse_id_list(row.get('inputs', ''))
        outputs = parse_id_list(row.get('outputs', ''))

        # ── Check 2: ID non-empty and unique ────────────────────────────────
        if not nid:
            err(row_num, '(empty)', 'Node ID is empty')
            continue
        if nid in all_ids:
            err(row_num, nid, f'Duplicate node ID')
            duplicate_rows.add(row_num)
            continue
        all_ids.add(nid)

        # ── Check 3: chip ───────────────────────────────────────────────────
        if chip not in ('1', '2'):
            err(row_num, nid, f'Invalid chip value "{chip}" (must be 1 or 2)')

        # ── Check 4: type ───────────────────────────────────────────────────
        if ntype not in VALID_TYPES:
            err(row_num, nid, f'Unknown node type "{ntype}"')

        # ── Check 5: ramp_profile ───────────────────────────────────────────
        if ramp not in VALID_RAMP_PROFILES:
            err(row_num, nid, f'Unknown ramp_profile "{ramp}"')

        # ── Check 6: ch_count ───────────────────────────────────────────────
        try:
            ch_count = int(ch_count_str)
            if ch_count < 1:
                err(row_num, nid, f'ch_count must be >= 1 (got {ch_count})')
        except ValueError:
            err(row_num, nid, f'ch_count is not an integer: "{ch_count_str}"')

        # ── Check 7: spi_page / spi_addr ────────────────────────────────────
        try:
            spi_page = int(spi_page_str)
        except ValueError:
            err(row_num, nid, f'spi_page is not an integer: "{spi_page_str}"')
            spi_page = None
        try:
            spi_addr = int(spi_addr_str)
        except ValueError:
            err(row_num, nid, f'spi_addr is not an integer: "{spi_addr_str}"')
            spi_addr = None

        has_valid_spi = spi_page is not None and spi_addr is not None and spi_page >= 0 and spi_addr >= 0

        if not has_valid_spi and ntype not in NO_SPI_TYPES:
            warn(row_num, nid, f'No SPI address (page={spi_page_str}, addr={spi_addr_str}) for type {ntype}')

        # ── Check 8: SPI address uniqueness ─────────────────────────────────
        if has_valid_spi and chip in ('1', '2'):
            key = (chip, spi_page, spi_addr)
            if key in spi_addresses:
                err(row_num, nid,
                    f'SPI address collision: chip={chip} page={spi_page} addr={spi_addr} '
                    f'already used by {spi_addresses[key]}')
            else:
                spi_addresses[key] = nid

        # ── Check 10: Required + recognized params ──────────────────────────
        required = REQUIRED_PARAMS.get(ntype, set())
        missing_params = required - set(params.keys())
        if missing_params:
            err(row_num, nid, f'Missing required params for {ntype}: {sorted(missing_params)}')
        allowed = ALLOWED_PARAMS.get(ntype, required)
        unknown_params = set(params.keys()) - allowed
        if unknown_params:
            err(row_num, nid, f'Unrecognized params for {ntype}: {sorted(unknown_params)}')

    # ── Check 9: input/output references ────────────────────────────────────
    # Re-iterate to validate references (all IDs now known)
    for row_num, row in enumerate(rows, start=2):
        if row_num in duplicate_rows:
            continue
        nid = row['id'].strip()
        inputs = parse_id_list(row.get('inputs', ''))
        outputs = parse_id_list(row.get('outputs', ''))
        for ref in inputs:
            if ref not in all_ids:
                err(row_num, nid, f'Input reference "{ref}" does not exist')
        for ref in outputs:
            if ref not in all_ids:
                err(row_num, nid, f'Output reference "{ref}" does not exist')

    # ── Report ───────────────────────────────────────────────────────────────
    print(f"Validated {len(rows)} nodes in {os.path.basename(csv_path)}")

    if warnings:
        print(f"\n  {len(warnings)} warning(s):")
        for w in warnings:
            print(w)

    if errors:
        print(f"\n  {len(errors)} error(s):")
        for e in errors:
            print(e)
        return 1

    print(f"  OK — no errors{f', {len(warnings)} warning(s)' if warnings else ''}")
    return 0


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(script_dir, '..', 'dsp.csv')
    sys.exit(validate(csv_path))
