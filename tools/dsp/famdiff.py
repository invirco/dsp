#!/usr/bin/env python3
"""famdiff.py — two famverify reports, verdict for verdict.

Every session since S11 has compared a candidate's family walk against the
shipping pair's by reading two tables side by side and saying "identical".
That is the right comparison and the wrong instrument: twenty families, an
audio verdict, a numeric verdict, a moved-word count and 160-odd contract
cells each, and the interesting result is always the ONE that moved.

So the comparison is mechanical here. Report A is the expectation, report B
the candidate; the exit code is 0 when nothing moved and 1 when something did,
and what moved is printed with both values.

  famdiff.py A.json B.json
  famdiff.py A.json B.json --allow COMPRESSOR:numeric,LIMITER:numeric

`--allow FAMILY:arm` names a verdict that is EXPECTED to differ -- S16's
LUT arm moves COMPRESSOR's numeric verdict off BIT_EXACT by construction, and
a diff that cannot say "that one, and only that one" is not a bar either.
"""
import argparse
import json
import sys


def load(p):
    with open(p) as fh:
        return json.load(fh)


def rows(rep):
    """{(family, arm): verdict} for every verdict a report carries."""
    out = {}
    for fam, v in (rep.get('families') or {}).items():
        for arm in ('audio', 'numeric'):
            d = v.get(arm) or {}
            if d.get('verdict') is not None:
                out[(fam, arm)] = d['verdict']
        a = v.get('audio') or {}
        if a.get('moved') is not None:
            out[(fam, 'moved')] = a['moved']
        # A contract cell that stops answering is the same class of event as a
        # family going inert, and it is per family here so the diff points at
        # the family rather than at a count.
        bad = sorted(c['cell'] for c in (v.get('contract') or [])
                     if c.get('verdict') not in ('ANSWERS', None))
        out[(fam, 'contract_not_answering')] = ','.join(bad) or '-'
    cc = rep.get('cross_check') or {}
    if 'disagreements' in cc:
        out[('(cross_check)', 'disagreements')] = cc['disagreements']
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('expected')
    ap.add_argument('candidate')
    ap.add_argument('--allow', default='',
                    help='FAMILY:arm,... verdicts expected to differ')
    args = ap.parse_args()

    allow = {tuple(x.split(':', 1)) for x in args.allow.split(',') if x}
    A, B = load(args.expected), load(args.candidate)
    ra, rb = rows(A), rows(B)

    print('expected  %s  cfg %s' % (args.expected,
          (A.get('chips', {}).get('1', {}) or {}).get('build_cfg')))
    print('candidate %s  cfg %s' % (args.candidate,
          (B.get('chips', {}).get('1', {}) or {}).get('build_cfg')))

    diffs, expected_diffs = [], []
    for k in sorted(set(ra) | set(rb)):
        va, vb = ra.get(k, '(absent)'), rb.get(k, '(absent)')
        if va == vb:
            continue
        line = '%-14s %-24s %s -> %s' % (k[0], k[1], va, vb)
        (expected_diffs if k in allow else diffs).append(line)

    for line in expected_diffs:
        print('  EXPECTED DIFFERENCE  ' + line)
    for line in diffs:
        print('  DIFFERS              ' + line)

    moved_fams = sorted({l.split()[0] for l in diffs})
    print('%d of %d families differ%s'
          % (len(moved_fams), len(B.get('families') or {}),
             ': ' + ', '.join(moved_fams) if moved_fams else ''))
    return 1 if diffs else 0


if __name__ == '__main__':
    sys.exit(main())
