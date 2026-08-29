#!/usr/bin/env python3
"""dsp4_conform_report.py — score a conformance run and print its table.

Runs on the workstation, off the JSON the bench half produced. Kept apart
from the harness so that the verdict rule is one reviewable place and a
stored result can be re-scored when the rule changes -- a scorer inside
the measuring tool can only ever score the run it just took.

THE BAR (what makes a run a PASS):

  1. every address's live verdict agrees with what the DISPATCH TABLE in
     the tree predicts. A mapped address that answers UNMAPPED, or an
     unmapped one that echoes, is drift between source and image.
  2. every DECLARED-unit check passes, unless it is a known and RECORDED
     mismatch, which is listed by name rather than tolerated by class.
  3. the negative controls did what they must: the corrupted-unit run
     FAILED its cell, and the no-readback run produced UNVERIFIED and
     not PASS.
  4. the part was healthy at exit and no address wedged it.

Anything short of that prints as a failure with the cells named. A run
that could not fail is reported as such and does not count.
"""

import argparse
import collections
import json
import os
import sys

# Mismatches already recorded in review-dsp-20260828.md. They are named
# ONE BY ONE and each carries its finding id: a class-level exemption
# would silently absorb the next mismatch of the same shape, which is the
# failure mode this whole harness exists to remove.
KNOWN_MISMATCH = {
    'ChanGateAtt': 'D41 — ms vs one-pole alpha, no conversion in this repo',
    'ChanGateRel': 'D41 — ms vs one-pole alpha, no conversion in this repo',
    'ChanCompAtt': 'D41 — ms vs one-pole alpha, no conversion in this repo',
    'ChanCompRel': 'D41 — ms vs one-pole alpha, no conversion in this repo',
    'ChanGateHold': 'D41 — ms vs raw samples, no conversion in this repo',
    'ChanDelay': 'D41 — ms vs raw samples, no conversion in this repo',
}


def load(paths):
    runs = []
    for p in paths:
        with open(p) as fh:
            r = json.load(fh)
        r['_file'] = os.path.basename(p)
        runs.append(r)
    return runs


def score(runs, plan):
    pred = {(e['chip'], e['addr']): e for e in plan['entries']} if plan else {}
    report = {'presence': collections.Counter(), 'drift': [], 'effect': [],
              'inert': [], 'negctl': [], 'wedged': [], 'unverified': 0,
              'runs': []}
    for r in runs:
        report['runs'].append(
            {'file': r['_file'], 'chip': r['chip'], 'phase': r['phase'],
             'verify': r.get('verify', True),
             'negctl_unit': r.get('negctl_unit'),
             'planned': r.get('addresses_planned'),
             'run': r.get('addresses_run'),
             'dropped': r.get('addresses_dropped', 0),
             'seconds': r.get('presence_seconds'),
             'final_health': r.get('final_health')})

        for rec in r.get('presence', []):
            v = rec['verdict']
            if not r.get('verify', True):
                # THE NO-READBACK CONTROL. Every cell it touched must come
                # out UNVERIFIED. A single PASS here means the harness
                # believes a write it never checked.
                report['unverified'] += 1
                if v != 'UNVERIFIED':
                    report['negctl'].append(
                        {'control': 'no-verify', 'addr': rec['addr'],
                         'verdict': v, 'result': 'BROKEN — not UNVERIFIED'})
                continue
            report['presence'][v] += 1
            if rec.get('wedged_after'):
                report['wedged'].append(
                    {'chip': r['chip'], 'addr': rec['addr'],
                     'cells': rec['cells']})
            p = pred.get((r['chip'], rec['addr']))
            if p is None:
                continue
            # The live mapped/unmapped answer comes from the part's own
            # SPI error counter, not from the read-back — see the note in
            # dsp4_conform.presence. An address the link could not
            # classify (a dropped write mid-batch) is INDETERMINATE and is
            # not scored as drift; it is counted and shown.
            live = rec.get('live_mapped')
            if live is None:
                continue
            if live != p['mapped']:
                report['drift'].append(
                    {'chip': r['chip'], 'addr': rec['addr'],
                     'cells': rec['cells'], 'tree': 'mapped' if p['mapped']
                     else 'unmapped', 'part': v})

        for rec in r.get('effect', []):
            rec = dict(rec, chip=r['chip'], run=r['_file'],
                       negctl_run=r.get('negctl_unit'))
            report['effect'].append(rec)
        for rec in r.get('inert', []):
            report['inert'].append(dict(rec, chip=r['chip']))
    return report


def verdict(report):
    fails = []
    by_check = collections.defaultdict(list)
    for e in report['effect']:
        by_check[(e.get('check'), bool(e.get('negctl')))].append(e)

    for (check, is_negctl), rows in sorted(by_check.items(),
                                           key=lambda kv: str(kv[0])):
        bad = [r for r in rows if r['verdict'] != 'PASS']
        if is_negctl:
            # THE CORRUPTED-UNIT CONTROL: it must FAIL.
            if not bad:
                fails.append(f'negative control {check}: the deliberately '
                             f'wrong unit PASSED — the check is not testing '
                             f'the unit')
                report['negctl'].append({'control': 'wrong-unit',
                                         'check': check,
                                         'result': 'BROKEN — passed anyway'})
            else:
                report['negctl'].append({'control': 'wrong-unit',
                                         'check': check,
                                         'result': f'FAILED as required '
                                                   f'({len(bad)} of {len(rows)})'})
            continue
        if bad and check not in KNOWN_MISMATCH:
            fails.append(f'{check}: {len(bad)} of {len(rows)} documented '
                         f'values give the wrong coefficient')

    if report['drift']:
        fails.append(f'{len(report["drift"])} addresses answer differently '
                     f'from what the dispatch table in the tree predicts')
    if report['wedged']:
        fails.append(f'{len(report["wedged"])} addresses wedged the part')
    for r in report['runs']:
        if r['final_health'] is False:
            fails.append(f'{r["file"]}: part not healthy at exit')
        # A no-readback CONTROL is a deliberate 64-address exercise, not a
        # truncated sweep; only a real measuring run that dropped addresses
        # is a partial run.
        if r['dropped'] and r['verify']:
            fails.append(f'{r["file"]}: {r["dropped"]} addresses not run '
                         f'(--limit) — this is a partial run')
    # THE INERT PROBE IS AN AUXILIARY, AND AN UNAVAILABLE AUXILIARY IS NOT
    # A CONTRACT FAILURE — but an inert verdict reported without a working
    # positive control IS, because that is the probe claiming a result it
    # cannot have measured. The harness withholds the verdicts itself; this
    # is the belt to that brace.
    ctl_ok = any(e.get('class') == 'POSITIVE CONTROL' and e.get('moved')
                 for e in report['inert'])
    confirmed = [e for e in report['inert']
                 if e.get('verdict') == 'INERT CONFIRMED']
    if confirmed and not ctl_ok:
        fails.append(f'{len(confirmed)} inert verdicts reported with no '
                     f'working positive control — they do not count')
    ctl = [c for c in report['negctl'] if 'BROKEN' in c.get('result', '')]
    if ctl:
        fails.append(f'{len(ctl)} negative controls did not fire — this run '
                     f'could not have failed and does not count')
    return fails


def markdown(report, fails, out):
    L = []
    L.append('# conformance run\n')
    L.append('| run | chip | phase | addresses | verified | seconds | '
             'healthy at exit |')
    L.append('|---|---|---|---|---|---|---|')
    for r in report['runs']:
        L.append(f'| `{r["file"]}` | {r["chip"]} | {r["phase"]} | '
                 f'{r["run"]}/{r["planned"]} | {r["verify"]} | '
                 f'{r["seconds"]} | {r["final_health"]} |')

    L.append('\n## presence — every address, written and read back\n')
    L.append('| verdict | addresses |')
    L.append('|---|---|')
    for v, n in report['presence'].most_common():
        L.append(f'| {v} | {n} |')

    L.append('\n## declared units — the documented value, the documented '
             'consequence\n')
    L.append('| check | wrote | expected | observed | verdict | note |')
    L.append('|---|---|---|---|---|---|')
    for e in report['effect']:
        if e.get('negctl'):
            continue
        exp = e.get('expected')
        obs = e.get('observed')
        note = KNOWN_MISMATCH.get(e.get('check', ''), '')
        L.append(f'| {e.get("check")} | {e.get("wrote")} | '
                 f'{"0x%08X" % exp if isinstance(exp, int) else exp} | '
                 f'{"0x%08X" % obs if isinstance(obs, int) else obs} | '
                 f'{e.get("verdict")} | {note} |')

    if report['inert']:
        L.append('\n## inert probe — a write that changes nothing '
                 'kernel-visible\n')
        L.append('| addr | cells | class | words moved | verdict |')
        L.append('|---|---|---|---|---|')
        for e in report['inert']:
            a = '—' if e.get('addr') is None else '0x%04X' % e['addr']
            L.append(f'| {a} | {", ".join(e.get("cells", []))} '
                     f'| {e.get("class","")} | {e.get("words_moved", "—")} '
                     f'| {e["verdict"]} |')

    L.append('\n## negative controls\n')
    if not report['negctl']:
        L.append('NONE RUN — this run could not have failed.')
    else:
        L.append('| control | subject | result |')
        L.append('|---|---|---|')
        for c in report['negctl']:
            L.append(f'| {c["control"]} | {c.get("check") or hex(c.get("addr",0))} '
                     f'| {c["result"]} |')
    if report['unverified']:
        L.append(f'\nno-readback control: {report["unverified"]} addresses '
                 f'came out UNVERIFIED, as required.')

    if report['drift']:
        L.append('\n## DRIFT — the part does not answer as the tree predicts\n')
        L.append('| chip | addr | cells | tree | part |')
        L.append('|---|---|---|---|---|')
        for d in report['drift'][:100]:
            L.append(f'| {d["chip"]} | 0x{d["addr"]:04X} | '
                     f'{", ".join(d["cells"])} | {d["tree"]} | {d["part"]} |')
        if len(report['drift']) > 100:
            L.append(f'\n...and {len(report["drift"]) - 100} more.')

    L.append('\n## verdict\n')
    L.append('PASS' if not fails else 'FAIL')
    for f in fails:
        L.append(f'- {f}')
    with open(out, 'w') as fh:
        fh.write('\n'.join(L) + '\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('results', nargs='+')
    ap.add_argument('--plan')
    ap.add_argument('--markdown')
    ap.add_argument('--csv',
                    help='per-address verdicts, one row each — the compact '
                         'form a future run is diffed against')
    args = ap.parse_args()

    plan = json.load(open(args.plan)) if args.plan else None
    runs = load(args.results)
    report = score(runs, plan)
    fails = verdict(report)

    for r in report['runs']:
        print(f'  {r["file"]}: chip {r["chip"]} {r["phase"]} '
              f'{r["run"]}/{r["planned"]} addresses, healthy={r["final_health"]}')
    print('  presence:', dict(report['presence']))
    ok = sum(1 for e in report['effect']
             if e['verdict'] == 'PASS' and not e.get('negctl'))
    bad = sum(1 for e in report['effect']
              if e['verdict'] != 'PASS' and not e.get('negctl'))
    print(f'  declared-unit checks: {ok} pass, {bad} fail')
    for c in report['negctl']:
        print(f'  negative control {c["control"]}: {c["result"]}')
    if report['drift']:
        print(f'  DRIFT: {len(report["drift"])} addresses')
    print('  VERDICT:', 'PASS' if not fails else 'FAIL')
    for f in fails:
        print('   -', f)

    if args.markdown:
        markdown(report, fails, args.markdown)
    if args.csv:
        # THE COMMITTED BASELINE IS THIS, not the raw result file. The
        # full JSON carries every probe word and runs to megabytes; what a
        # later run needs to be compared against is the verdict per
        # address, which diffs line by line and is readable in a review.
        import csv as _csv
        with open(args.csv, 'w', newline='') as fh:
            w = _csv.writer(fh)
            w.writerow(['chip', 'addr', 'hex', 'verdict', 'role',
                        'predicted_mapped', 'live_mapped', 'err_delta',
                        'unit', 'cells'])
            for r in runs:
                if not r.get('verify', True):
                    continue
                for rec in r.get('presence', []):
                    w.writerow([r['chip'], rec['addr'], '0x%04X' % rec['addr'],
                                rec['verdict'], rec['role'],
                                rec['predicted_mapped'],
                                rec.get('live_mapped'),
                                rec.get('err_delta'), rec['unit'],
                                ' '.join(rec['cells'])])
        print(f'  wrote {args.csv}')
    return 0 if not fails else 5


if __name__ == '__main__':
    sys.exit(main())
