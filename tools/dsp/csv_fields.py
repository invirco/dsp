#!/usr/bin/env python3
"""csv_fields.py — shared dsp.csv cell parsing for dsp_validate.py and
dsp_simulate.py (both parse the same ';'-delimited id-list and
key=value param cells; kept in one place so they can't drift apart).
"""


def parse_id_list(cell):
    cell = cell.strip().strip('"')
    if not cell:
        return []
    return [x.strip() for x in cell.split(';') if x.strip()]


def parse_params(cell):
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
