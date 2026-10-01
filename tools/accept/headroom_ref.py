#!/usr/bin/env python3
"""The input-headroom reference: one pass's 1 % THD levels, averaged (S164).

PW 2026-10-01: "work out the values from this pass, then AVERAGE them to use as
the reference". The station records each input's headroom (the level at which
THD+N reaches 1 % = -40 dB, gain code 0, dBu at the connector) on its gain-walk
patch; RUN ALL keeps it in state.json under `patches[Pnn].hr`. This reads them,
leaves out and NAMES any input more than `headroom_exclude_db` from the median
(PW's ruling), and writes into patch-limits.csv:

    headroom_ref_dbu        the average, with the pass, the unit and what was
                            left out in its `source`
    headroom_micNN_dbu      each input's own value, for the record

An input whose ramp never reached 1 % (`hr_reached` false) has no level to
average and is named as left out. Nothing is graded while the reference reads `nan`; once it is
written; from then on the station fails an input more than `headroom_tol_db`
(PROVISIONAL) under it.

    headroom_ref.py --state runall/state.json            # print, write nothing
    headroom_ref.py --state runall/state.json --write    # into the list's limits
"""
import argparse
import csv
import io
import json
import os
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
LIMITS_DEFAULT = os.path.join(ROOT, 'MW', 'D24', 'DSP', 's121',
                              'patch-limits.csv')
REF_KEY = 'headroom_ref_dbu'
PER_INPUT = 'headroom_mic%02d_dbu'


def readings(state, pass_no=None):
    """[(input, dbu, pass_no, patch)] for every recorded headroom, newest pass
    only unless `pass_no` names one; and the inputs with no level."""
    got, none = {}, []
    for pid, e in sorted((state.get('patches') or {}).items()):
        hr = e.get('hr')
        if not hr:
            continue
        p = hr.get('pass_no')
        if pass_no is not None and p != pass_no:
            continue
        name = hr.get('input') or pid
        dbu = hr.get('hr_dbu')
        if not hr.get('hr_reached') or dbu in (None, ''):
            none.append((name, p, hr.get('why') or 'no level'))
            continue
        got[name] = (name, float(dbu), p, pid)
    return sorted(got.values(), key=lambda x: mic_no(x[0])), none


def mic_no(name):
    try:
        return int(str(name).split()[-1])
    except ValueError:
        return 999


def reference(vals, exclude_db):
    """(average, median, kept, left_out) -- left_out as [(input, dbu, why)]."""
    if not vals:
        raise SystemExit('no headroom readings to average')
    med = statistics.median(v[1] for v in vals)
    kept = [v for v in vals if abs(v[1] - med) <= exclude_db]
    out = [(v[0], v[1], '%+.1f dB from the %.1f dBu median'
            % (v[1] - med, med)) for v in vals if abs(v[1] - med) > exclude_db]
    if not kept:
        raise SystemExit('every reading is more than %.1f dB from the median'
                         % exclude_db)
    return sum(v[1] for v in kept) / len(kept), med, kept, out


def load_limits(path):
    with open(path, newline='') as fh:
        text = fh.read()
    rows = list(csv.DictReader(l for l in text.splitlines()
                               if not l.startswith('#')))
    return text, rows


def line(key, value, unit, source):
    buf = io.StringIO()
    csv.writer(buf, lineterminator='').writerow([key, value, unit, source])
    return buf.getvalue()


def write_limits(path, text, ref_line, per_input):
    """Line-level: the reference line replaced, the per-input lines rewritten
    whole right under it, every other line of the hand-tuned file untouched."""
    out, done = [], False
    for l in text.split('\n'):
        if l.startswith('headroom_mic'):
            continue
        if l.startswith(REF_KEY + ','):
            out.append(ref_line)
            out += per_input
            done = True
            continue
        out.append(l)
    if not done:
        raise SystemExit('%s declares no %s' % (path, REF_KEY))
    with open(path, 'w', newline='') as fh:
        fh.write('\n'.join(out))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--state', required=True, help="RUN ALL's state.json")
    ap.add_argument('--limits', default=LIMITS_DEFAULT)
    ap.add_argument('--pass', dest='pass_no', type=int,
                    help='take this pass only (default: every recorded value, '
                         'newest per input)')
    ap.add_argument('--write', action='store_true')
    a = ap.parse_args(argv)
    with open(a.state) as fh:
        state = json.load(fh)
    text, rows = load_limits(a.limits)
    lim = dict((r['key'], r['value']) for r in rows)
    excl = float(lim['headroom_exclude_db'])
    vals, none = readings(state, a.pass_no)
    avg, med, kept, out = reference(vals, excl)
    passes = sorted({v[2] for v in kept if v[2] is not None})
    for name, dbu, p, pid in vals:
        mark = '' if any(o[0] == name for o in out) else '*'
        print('  %-7s %6.2f dBu  pass %s  %s %s' % (name, dbu, p, pid, mark))
    for name, p, why in none:
        print('  %-7s   --       pass %s  no level: %s' % (name, p, why))
    left = ['%s %.1f dBu (%s)' % o for o in out] + \
        ['%s (no 1 %% level: %s)' % (n, w) for n, _p, w in none]
    print('median %.2f dBu; average of %d inputs (*) = %.2f dBu; left out: %s'
          % (med, len(kept), avg, '; '.join(left) or 'none'))
    if not a.write:
        print('(nothing written: --write puts it in %s)'
              % os.path.relpath(a.limits, ROOT))
        return 0
    src = ('the average of %d inputs\' 1 %% THD level at gain code 0, unit %s, '
           'pass %s (state.json, written by tools/accept/headroom_ref.py); '
           'median %.2f dBu; left out (more than %.1f dB from the median, or no '
           'level): %s' % (len(kept), state.get('serial', '?'),
                           ','.join(str(p) for p in passes), med, excl,
                           '; '.join(left) or 'none'))
    unit = dict((r['key'], r['unit']) for r in rows).get(REF_KEY, 'dBu')
    per = [line(PER_INPUT % mic_no(name), '%.2f' % dbu, 'dBu',
                '%s, pass %s (%s)%s' % (name, p, pid,
                                        '; LEFT OUT of the average'
                                        if any(o[0] == name for o in out)
                                        else ''))
           for name, dbu, p, pid in vals]
    write_limits(a.limits, text, line(REF_KEY, '%.2f' % avg, unit, src), per)
    print('wrote %s = %.2f dBu into %s' % (REF_KEY, avg,
                                           os.path.relpath(a.limits, ROOT)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
