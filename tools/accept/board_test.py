#!/usr/bin/env python3
"""board_test.py -- the D24 board test, from the desk (NAMM-D24-6).

A new rev C board is swapped into the harness unit (MW-D24-2, every other
board known-good) and tested by the factory runner on the rows that exercise
it. This script is the desk half: it opens the board session on the unit,
says what the operator does next, and brings the result home.

    board_test.py profiles                       # the boards and their rows
    board_test.py check-id 7KQ3-M9X0             # is this a board label?
    board_test.py start dsp 7KQ3-M9X0 [--rev C]  # open the session on the unit
        ... then START on the unit's glass; PAUSE / START resumes ...
    board_test.py status                         # which board, is a run going
    board_test.py fetch                          # result -> tools/accept/results/
    board_test.py end                            # close the session

`start` writes /home/app/selftest/board.conf and nothing else: no flash, no
reboot, no runner started. While it exists the glass START tests that board;
`end` removes it and the unit is a whole-unit factory station again. `start`
refuses while another board's session is open or a run is going.

`fetch` copies the board's newest report pair off the unit into
tools/accept/results/<ID>/ and writes the result file beside it,
`<ID>-<profile>-<stamp>.csv`: one line per row in the board's profile,
PASS / FAIL / NO DATA / NOT TESTED / SKIPPED / IGNORED, with the reading,
the limit, who judged it and the row's role on this board. `--from-json`
writes the same file from a report already on this machine (no unit).
"""
import argparse
import csv
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'pi'))
import d24_boards as BB                                  # noqa: E402

BENCH = os.environ.get('BENCH', 'app@192.168.1.219')
SELFTEST = '/home/app/selftest'
REPORTS = SELFTEST + '/reports/boards'
RESULTS = os.path.join(HERE, 'results')
RUNNERS = 'd24_runall.py|d24_patch.py --run|d24_selftest.py'

COLS = ['board_id', 'board', 'profile', 'rev', 'harness_unit', 'stamp',
        'pass', 'num', 'item', 'role', 'verdict', 'measured', 'limit',
        'judged', 'verdict_pass', 'reason']


def ssh(cmd, check=True):
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8',
                        BENCH, cmd], capture_output=True, text=True)
    if check and r.returncode != 0:
        raise SystemExit('ssh %s failed (%d): %s'
                         % (BENCH, r.returncode, r.stderr.strip()))
    return r


def remote_conf():
    r = ssh('cat %s 2>/dev/null' % BB.BOARD_CONF, check=False)
    if r.returncode != 0 or not r.stdout.strip():
        return None
    tmp = os.path.join(RESULTS, '.board.conf')
    os.makedirs(RESULTS, exist_ok=True)
    with open(tmp, 'w') as fh:
        fh.write(r.stdout)
    try:
        return BB.read_conf(tmp)
    finally:
        os.unlink(tmp)


def running():
    r = ssh("pgrep -af '%s' | grep -v pgrep" % RUNNERS, check=False)
    return r.stdout.strip()


def cmd_profiles(_a):
    for k in BB.ORDER:
        p = BB.PROFILES[k]
        roles = {}
        for v in p['rows'].values():
            roles[v] = roles.get(v, 0) + 1
        print('%-10s %-20s %3d rows (%s)\n           %s'
              % (k, p['name'], len(p['rows']),
                 ', '.join('%d %s' % (roles[x], x) for x in sorted(roles)),
                 p['note']))
    return 0


def cmd_check_id(a):
    try:
        print('board label %s' % BB.show_id(BB.normalise_id(a.id)))
        return 0
    except ValueError as e:
        print('NOT a board label: %s' % e)
        return 1


def cmd_start(a):
    try:
        text = BB.conf_text(a.profile, a.id, rev=a.rev, operator=a.operator)
        bid = BB.normalise_id(a.id)
    except ValueError as e:
        raise SystemExit(str(e))
    if a.dry_run:
        sys.stdout.write(text)
        return 0
    cur = remote_conf()
    if cur and (cur['id'], cur['profile']) != (bid, a.profile):
        raise SystemExit('a session for %s %s is open on %s: fetch its result '
                         'and `end` it first'
                         % (BB.PROFILES[cur['profile']]['name'],
                            BB.show_id(cur['id']), BENCH))
    busy = running()
    if busy:
        raise SystemExit('a run is going on %s; wait for it or PAUSE it:\n%s'
                         % (BENCH, busy))
    r = subprocess.run(['ssh', '-o', 'BatchMode=yes', BENCH,
                        'cat > %s.tmp && mv %s.tmp %s' % ((BB.BOARD_CONF,) * 3)],
                       input=text, text=True, capture_output=True)
    if r.returncode != 0:
        raise SystemExit('could not write %s: %s' % (BB.BOARD_CONF,
                                                     r.stderr.strip()))
    p = BB.PROFILES[a.profile]
    print('board session open on %s: %s %s'
          % (BENCH, p['name'], BB.show_id(bid)))
    print('  %s' % p['note'])
    print('  Press START on the unit\'s screen. PAUSE stops; the next START '
          'resumes this board\'s untested rows only.')
    print('  When it is finished: board_test.py fetch, then board_test.py end.')
    return 0


def cmd_status(_a):
    cur = remote_conf()
    if not cur:
        print('no board session on %s: START is a whole-unit factory pass'
              % BENCH)
    else:
        print('board session on %s: %s %s%s'
              % (BENCH, BB.PROFILES[cur['profile']]['name'],
                 BB.show_id(cur['id']),
                 (' rev %s' % cur['rev']) if cur.get('rev') else ''))
    busy = running()
    print('a run is going:\n%s' % busy if busy else 'no run is going')
    return 0


def result_rows(rep):
    b = rep.get('board') or {}
    out = []
    for r in rep['rows']:
        out.append(dict(
            board_id=b.get('id', rep.get('serial', '')),
            board=b.get('name', ''), profile=b.get('profile', ''),
            rev=b.get('rev', ''), harness_unit=b.get('harness_unit', ''),
            stamp=rep.get('stamp', ''), **{'pass': rep.get('passes', '')},
            num=r['num'], item=r['item'],
            role=(b.get('roles') or {}).get(str(r['num']), ''),
            verdict=r.get('verdict') or 'NOT TESTED',
            measured=r.get('measured', ''), limit=r.get('limit', ''),
            judged=r.get('judged', ''), verdict_pass=r.get('pass_no', ''),
            reason=r.get('reason', '')))
    return out


def write_result(rep, out_dir=None):
    b = rep.get('board')
    if not b:
        raise SystemExit('this report is a whole-unit pass, not a board test')
    out_dir = out_dir or os.path.join(RESULTS, b['id'])
    os.makedirs(out_dir, exist_ok=True)
    st = rep.get('stamp', '').replace(':', '').replace('-', '')
    path = os.path.join(out_dir, '%s-%s-%s.csv' % (b['id'], b['profile'], st))
    rows = result_rows(rep)
    with open(path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    tally = {}
    for r in rows:
        tally[r['verdict']] = tally.get(r['verdict'], 0) + 1
    return path, tally


def cmd_fetch(a):
    if a.from_json:
        with open(a.from_json) as fh:
            rep = json.load(fh)
        path, tally = write_result(rep, a.out)
    else:
        cur = remote_conf()
        bid = BB.normalise_id(a.id) if a.id else (cur or {}).get('id')
        if not bid:
            raise SystemExit('no board session is open: name the board, '
                             'fetch <ID>')
        r = ssh('ls -1t %s/%s-*.json 2>/dev/null | head -1' % (REPORTS, bid),
                check=False)
        js = r.stdout.strip()
        if not js:
            raise SystemExit('no report for %s on %s yet' % (BB.show_id(bid),
                                                             BENCH))
        out_dir = a.out or os.path.join(RESULTS, bid)
        os.makedirs(out_dir, exist_ok=True)
        for src in (js, js[:-5] + '.md'):
            subprocess.run(['scp', '-q', '-o', 'BatchMode=yes',
                            '%s:%s' % (BENCH, src), out_dir], check=True)
        with open(os.path.join(out_dir, os.path.basename(js))) as fh:
            rep = json.load(fh)
        path, tally = write_result(rep, out_dir)
    print('result: %s' % path)
    print('  %s' % ', '.join('%d %s' % (tally[k], k) for k in sorted(tally)))
    return 1 if tally.get('FAIL') else 0


def cmd_end(_a):
    busy = running()
    if busy:
        raise SystemExit('a run is going on %s; PAUSE it first:\n%s'
                         % (BENCH, busy))
    cur = remote_conf()
    ssh('rm -f %s' % BB.BOARD_CONF)
    print('board session closed%s: START on %s is a whole-unit factory pass '
          'again' % ((' (%s %s)' % (BB.PROFILES[cur['profile']]['name'],
                                    BB.show_id(cur['id']))) if cur else '',
                     BENCH))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('profiles').set_defaults(fn=cmd_profiles)
    p = sub.add_parser('check-id')
    p.add_argument('id')
    p.set_defaults(fn=cmd_check_id)
    p = sub.add_parser('start')
    p.add_argument('profile', choices=BB.ORDER)
    p.add_argument('id')
    p.add_argument('--rev', default='')
    p.add_argument('--operator', default='')
    p.add_argument('--dry-run', action='store_true',
                   help='print the session file; touch nothing')
    p.set_defaults(fn=cmd_start)
    sub.add_parser('status').set_defaults(fn=cmd_status)
    p = sub.add_parser('fetch')
    p.add_argument('id', nargs='?')
    p.add_argument('--from-json', help='a report already on this machine')
    p.add_argument('--out', help='directory (default results/<ID>)')
    p.set_defaults(fn=cmd_fetch)
    sub.add_parser('end').set_defaults(fn=cmd_end)
    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == '__main__':
    sys.exit(main())
