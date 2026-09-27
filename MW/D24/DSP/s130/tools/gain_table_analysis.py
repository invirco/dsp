#!/usr/bin/env python3
"""gain_table_analysis.py -- S130 item 7: per-element gain-table check for
HANDS 4 (MIC 9-12, 17-24 walked with a real lead).

Takes measured per-element, per-code loop gain and, against the reference
64-code table (defs/common/tables/mic-gain-codes.csv once the hub advances
the pin, HUB ADDENDUM 2 -- falling back to the staged
proposals/defs/common/tables/mic-gain-codes.csv copy until then, same as
tools/accept/gen_patch_paths.py's load_gain_codes()), reports per element:
  - measured gain vs. the table, at every code walked;
  - whether the element's error GROWS with gain (points at the 2N7002DW FET's
    Rds(on) in the LTP tail -- HUB ADDENDUM 6) or is FLAT (points at the
    table itself, or the gain-setting resistor);
  - a proposed corrected per-element table (the reference table plus that
    element's own fitted correction).

Input measured CSV is the same shape as MW/D24/DSP/s55/law.csv:
    channel,code,loop_gain_db
one row per (element, code walked); code 0 MUST be present for each element
so its own hw_gain_db can be referenced the same way the table is (gain re
that channel's own code 0). Pass --hw-gain if the input is already hw_gain_db
(pre-normalized, no code-0 row needed).

Classification: fit error(code) = measured_hw_db - table_hw_db(code) against
table_hw_db(code) (a proxy for gain) by least squares. GROWING if the fitted
slope's contribution across the walked codes' gain span exceeds
GROW_THRESHOLD_DB and the fit explains more of the error than a flat mean
would (relative residual improvement over FLAT_R2_MARGIN); otherwise FLAT.

Run with --selftest for the synthetic-data proof (no bench needed); ready to
run against real HANDS 4 data with --measured/--table.
"""
import argparse
import csv
import os
import random
import statistics as st
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
S130 = os.path.dirname(HERE)
ROOT = os.path.abspath(os.path.join(S130, '..', '..', '..', '..'))
DEFS_TABLE = os.path.join(ROOT, 'defs', 'common', 'tables', 'mic-gain-codes.csv')
PROPOSED_TABLE = os.path.join(ROOT, 'proposals', 'defs', 'common', 'tables',
                              'mic-gain-codes.csv')
DEFAULT_TABLE = DEFS_TABLE if os.path.exists(DEFS_TABLE) else PROPOSED_TABLE

GROW_THRESHOLD_DB = 0.10   # slope * gain-span must exceed this to call it "growing"
FLAT_R2_MARGIN = 0.30      # the linear fit must cut residual variance by this fraction
                            # over a flat (mean-only) fit to be called "growing" rather than noise


def load_table(path):
    table = {}
    with open(path) as f:
        rows = [r for r in csv.reader(f) if r and not r[0].startswith('#')]
    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    for r in rows[1:]:
        table[int(r[idx['code']])] = float(r[idx['step_db']])
    return table


def load_measured(path, hw_gain):
    raw = defaultdict(dict)
    with open(path) as f:
        rows = [r for r in csv.reader(f) if r and not r[0].startswith('#')]
    header = rows[0]
    idx = {name: i for i, name in enumerate(header)}
    for r in rows[1:]:
        ch = r[idx['channel']]
        code = int(r[idx['code']])
        val = float(r[idx['loop_gain_db']])
        raw[ch][code] = val
    if hw_gain:
        return raw
    out = {}
    for ch, codes in raw.items():
        if 0 not in codes:
            raise SystemExit('element %s has no code-0 row to reference against '
                              '(pass --hw-gain if input is already hw_gain_db)' % ch)
        ref = codes[0]
        out[ch] = {c: v - ref for c, v in codes.items()}
    return out


def linfit(xs, ys):
    """least squares slope/intercept; returns (slope, intercept, r2)."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        return 0.0, my, 0.0
    slope = sxy / sxx
    intercept = my - slope * mx
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    ss_tot = sum((y - my) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    return slope, intercept, r2


def analyse_element(channel, measured, table):
    """measured: {code: hw_gain_db}. table: {code: hw_gain_db}. Returns a dict report."""
    codes = sorted(c for c in measured if c in table)
    if len(codes) < 2:
        return {'channel': channel, 'error': 'need >=2 codes in common with the table (got %d)' % len(codes)}
    err = {c: measured[c] - table[c] for c in codes}
    gain = [table[c] for c in codes]
    errs = [err[c] for c in codes]
    slope, intercept, r2 = linfit(gain, errs)
    span = max(gain) - min(gain)
    grow_contribution = abs(slope) * span
    mean_err = sum(errs) / len(errs)
    flat_resid = sum((e - mean_err) ** 2 for e in errs)
    fit_resid = sum((e - (slope * g + intercept)) ** 2 for g, e in zip(gain, errs))
    improvement = (flat_resid - fit_resid) / flat_resid if flat_resid > 0 else 0.0
    growing = grow_contribution > GROW_THRESHOLD_DB and improvement > FLAT_R2_MARGIN
    verdict = 'GROWING (FET Rds(on))' if growing else 'FLAT (table/resistor)'
    corrected = {c: table[c] + (slope * table[c] + intercept if growing else mean_err) for c in table}
    return {
        'channel': channel,
        'codes': codes,
        'error_db': err,
        'mean_error_db': mean_err,
        'worst_error_db': max(errs, key=abs),
        'slope_db_per_db': slope,
        'grow_contribution_db': grow_contribution,
        'r2_improvement': improvement,
        'verdict': verdict,
        'growing': growing,
        'corrected_table': corrected,
    }


def report(results, out_csv=None, out_md=None):
    lines_md = ['# S130 item 7 -- gain-table analysis', '']
    lines_md.append('| element | codes | mean err (dB) | worst err (dB) | slope (dB/dB) | verdict |')
    lines_md.append('|---|---:|---:|---:|---:|---|')
    csv_rows = []
    for r in results:
        if 'error' in r:
            lines_md.append('| %s | -- | -- | -- | -- | %s |' % (r['channel'], r['error']))
            continue
        lines_md.append('| %s | %d | %+.3f | %+.3f | %+.4f | %s |' % (
            r['channel'], len(r['codes']), r['mean_error_db'], r['worst_error_db'],
            r['slope_db_per_db'], r['verdict']))
        for c in r['codes']:
            csv_rows.append([r['channel'], c, '%.3f' % r['error_db'][c], r['verdict']])
    md = '\n'.join(lines_md) + '\n'
    if out_md:
        with open(out_md, 'w') as f:
            f.write(md)
    if out_csv:
        with open(out_csv, 'w', newline='') as f:
            w = csv.writer(f)
            w.writerow(['channel', 'code', 'error_db', 'verdict'])
            w.writerows(csv_rows)
    return md


# --------------------------------------------------------------------- selftest

def _synth_table():
    # a small synthetic reference table, monotonic like the real one
    return {c: c * 0.85 for c in range(0, 64, 4)}


def _synth_measured(table, seed):
    rng = random.Random(seed)
    rows = []
    # element A: FLAT offset error (a resistor/table issue) -- same offset at every code
    offset = 0.30
    for c, g in table.items():
        rows.append(('MIC_FLAT', c, g + offset + rng.gauss(0, 0.01)))
    # element B: GROWING error with gain (an FET Rds(on) issue) -- error scales with gain
    for c, g in table.items():
        rows.append(('MIC_GROW', c, g + 0.02 * g + rng.gauss(0, 0.01)))
    # element C: clean, within noise, no real error either way
    for c, g in table.items():
        rows.append(('MIC_CLEAN', c, g + rng.gauss(0, 0.01)))
    return rows


def selftest():
    table = _synth_table()
    rows = _synth_measured(table, seed=1)
    measured = defaultdict(dict)
    for ch, code, val in rows:
        measured[ch][code] = val  # already hw_gain_db re a synthetic code 0 of 0.0
    results = [analyse_element(ch, measured[ch], table) for ch in measured]
    ok = True
    by_ch = {r['channel']: r for r in results}
    if by_ch['MIC_FLAT']['growing']:
        print('FAIL: MIC_FLAT classified as growing, expected flat'); ok = False
    elif abs(by_ch['MIC_FLAT']['mean_error_db'] - 0.30) > 0.05:
        print('FAIL: MIC_FLAT mean error %.3f, expected ~0.30' % by_ch['MIC_FLAT']['mean_error_db']); ok = False
    else:
        print('PASS: MIC_FLAT -> %s, mean error %+.3f dB (expected ~+0.300)' % (
            by_ch['MIC_FLAT']['verdict'], by_ch['MIC_FLAT']['mean_error_db']))
    if not by_ch['MIC_GROW']['growing']:
        print('FAIL: MIC_GROW classified as flat, expected growing'); ok = False
    else:
        print('PASS: MIC_GROW -> %s, slope %+.4f dB/dB (expected ~+0.0200)' % (
            by_ch['MIC_GROW']['verdict'], by_ch['MIC_GROW']['slope_db_per_db']))
    if by_ch['MIC_CLEAN']['growing'] or abs(by_ch['MIC_CLEAN']['mean_error_db']) > 0.05:
        print('FAIL: MIC_CLEAN not classified as clean/flat-near-zero'); ok = False
    else:
        print('PASS: MIC_CLEAN -> %s, mean error %+.3f dB (expected ~0)' % (
            by_ch['MIC_CLEAN']['verdict'], by_ch['MIC_CLEAN']['mean_error_db']))
    # corrected-table check: after correction, residual error should collapse
    for ch in ('MIC_FLAT', 'MIC_GROW'):
        r = by_ch[ch]
        resid = [measured[ch][c] - r['corrected_table'][c] for c in r['codes']]
        worst = max(abs(x) for x in resid)
        if worst > 0.05:
            print('FAIL: %s corrected-table residual %.3f dB too large' % (ch, worst)); ok = False
        else:
            print('PASS: %s corrected-table worst residual %.3f dB' % (ch, worst))
    print()
    print('SELFTEST', 'PASS' if ok else 'FAIL')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--measured', help='per-element measured CSV, law.csv shape (channel,code,loop_gain_db)')
    ap.add_argument('--table', default=DEFAULT_TABLE, help='reference 64-code table (default: S130 median table)')
    ap.add_argument('--hw-gain', action='store_true', help='measured CSV is already hw_gain_db, no code-0 normalization')
    ap.add_argument('--out-csv')
    ap.add_argument('--out-md')
    ap.add_argument('--selftest', action='store_true', help='run the synthetic-data proof and exit')
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest())

    if not args.measured:
        ap.error('--measured is required (or use --selftest)')

    table = load_table(args.table)
    measured = load_measured(args.measured, args.hw_gain)
    results = [analyse_element(ch, measured[ch], table) for ch in measured]
    md = report(results, args.out_csv, args.out_md)
    print(md)


if __name__ == '__main__':
    main()
