#!/usr/bin/env python3
"""NAMM-D24-6 desk check: the board test, with no unit.

  * every profile cuts the unit's real catalog without error, and every
    catalog row is in at least one profile
  * a board pass reads its session from board.conf, keeps its verdicts under
    the board's ID, and leaves the whole-unit state alone
  * a board with nothing runnable (the pedal) writes its report and stops
    before the pair is booted
  * a bad board.conf stops the runner; no board.conf is the whole-unit pass,
    unchanged (all 202 rows, no board block)
  * the setup pages ask only for what the board's rows use
  * the analog station in a board scope walks only that board's patches
    (right panel: the two mini-jack patches; phone jack: the jack patches)
  * the desk's result file has one line per profile row
"""
import contextlib
import csv
import io
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..', 's159'))
sys.argv = [sys.argv[0]]
import rerun_ein_check as R          # noqa: E402
RA, PT = R.RA, R.PT
check = R.check
sys.path.insert(0, os.path.join(ROOT, 'tools', 'accept'))
import d24_boards as BB              # noqa: E402
import board_test as BT              # noqa: E402

CATALOG = os.path.join(ROOT, 'MW', 'D24', 'DSP', 's164', 'data',
                       'test-catalog-unit.csv')
ID = BB.make_id('NAMM246')
RA.LIST_DIR = R.LIST_DIR


def catalog():
    rows, md5 = RA.load_catalog(CATALOG)
    RA.classify(rows)
    return rows, md5


def run_main(argv):
    out = io.StringIO()
    rc = None
    with contextlib.redirect_stdout(out):
        try:
            rc = RA.main(argv)
        except SystemExit as e:
            rc = ('exit', str(e))
    return rc, out.getvalue()


def bench(tmp, conf=None):
    d = os.path.join(tmp, 'selftest')
    os.makedirs(os.path.join(d, 'runall'), exist_ok=True)
    shutil.copy(CATALOG, os.path.join(d, 'test-catalog.csv'))
    cpath = os.path.join(d, 'board.conf')
    if conf is not None:
        with open(cpath, 'w') as fh:
            fh.write(conf)
    return d, cpath


def newest(d, ext):
    fs = sorted(f for f in os.listdir(d) if f.endswith(ext))
    return os.path.join(d, fs[-1]) if fs else None


# -- 1. the profiles against the catalog ----------------------------------
rows, md5 = catalog()
for k in BB.ORDER:
    try:
        got = BB.scope(rows, k)
        check('profile %s cuts the catalog (%d rows)' % (k, len(got)),
              len(got) == len(BB.PROFILES[k]['rows']))
    except ValueError as e:
        check('profile %s cuts the catalog' % k, False, e)
left_out = BB.unassigned(rows)
check('every catalog row is in at least one profile',
      not left_out, [r.num for r in left_out])

# -- 2. a board pass from board.conf, report only ---------------------------
tmp = tempfile.mkdtemp(prefix='namm-d24-6-')
d, cpath = bench(tmp, BB.conf_text('dsp', BB.show_id(ID).lower(), rev='C'))
unit_state = os.path.join(d, 'runall', 'state.json')
with open(unit_state, 'w') as fh:
    json.dump({'serial': 'UNIT-1', 'rows': {'1': {'verdict': 'PASS'}},
               'passes': 4, 'current': None}, fh)
before = open(unit_state).read()
rc, out = run_main(['--dir', d, '--board-conf', cpath, '--serial', 'UNIT-1',
                    '--report-only'])
rep_dir = os.path.join(d, 'reports', 'boards')
js = newest(rep_dir, '.json') if os.path.isdir(rep_dir) else None
check('board pass: the report is written under reports/boards', js, out)
rep = json.load(open(js)) if js else {}
check('... named for the board ID', js and os.path.basename(js)
      .startswith(ID + '-'), js)
check('... carries exactly the DSP card profile\'s rows',
      sorted(r['num'] for r in rep.get('rows', []))
      == sorted(BB.PROFILES['dsp']['rows']))
b = rep.get('board') or {}
check('... and the board block (id, profile, rev, harness unit, roles)',
      (b.get('id'), b.get('profile'), b.get('rev'), b.get('harness_unit'))
      == (ID, 'dsp', 'C', 'UNIT-1') and len(b.get('roles', {})) == 45, b)
md = open(js[:-5] + '.md').read() if js else ''
check('the human page heads with the board, its label and the unit',
      md.startswith('# D24 board test report')
      and BB.show_id(ID) in md and 'tested in unit UNIT-1' in md)
check('the human page passes the internal-vocabulary grep',
      RA.check_md(js[:-5] + '.md') == 0 if js else False)
check('the whole-unit state is untouched', open(unit_state).read() == before)
check('the console line names the board test', 'D24 BOARD TEST' in out, out)

# -- 3. --board on the command line, and a refused ID ----------------------
rc, out = run_main(['--dir', d, '--board-conf', '/nonexistent',
                    '--board', 'left', '--board-id', BB.show_id(ID),
                    '--serial', 'UNIT-1', '--report-only'])
js2 = newest(rep_dir, '.json')
check('--board left on the command line: 17 rows',
      len(json.load(open(js2))['rows']) == 17)
rc, out = run_main(['--dir', d, '--board', 'left', '--board-id', 'ABCD-EFGH',
                    '--serial', 'UNIT-1', '--report-only'])
check('a mistyped ID is refused before anything runs',
      isinstance(rc, tuple) and 'mistyped' in rc[1], rc)
with open(cpath, 'w') as fh:
    fh.write('profile=nonesuch\nid=%s\n' % ID)
rc, out = run_main(['--dir', d, '--board-conf', cpath, '--serial', 'UNIT-1',
                    '--report-only'])
check('a board.conf naming no profile stops the runner (never a whole-unit '
      'pass by accident)', isinstance(rc, tuple) and 'nonesuch' in rc[1], rc)

# -- 4. the pedal: nothing runnable, nothing booted --------------------------
with open(cpath, 'w') as fh:
    fh.write(BB.conf_text('p1', ID))
booted = []
real_pair = RA.ensure_pair
RA.ensure_pair = lambda *a, **k: booted.append(1)
try:
    rc, out = run_main(['--dir', d, '--board-conf', cpath, '--serial',
                        'UNIT-1', '--stdin', '--no-power-check'])
finally:
    RA.ensure_pair = real_pair
check('pedal board: returns 3 and boots nothing', rc == 3 and not booted,
      (rc, booted, out[-300:]))
js3 = newest(rep_dir, '.json')
r3 = json.load(open(js3))
check('... its report lists all 7 rows NOT TESTED with a reason each',
      len(r3['rows']) == 7 and all(r['verdict'] == 'NOT TESTED' and
                                   r.get('reason') for r in r3['rows']),
      [(r['num'], r['verdict']) for r in r3['rows']])
check('... and the run lock is released',
      not os.path.exists(os.path.join(d, 'runall', 'runner.lock')))

# -- 5. no board.conf: the whole-unit pass, unchanged -----------------------
os.remove(cpath)
rc, out = run_main(['--dir', d, '--board-conf', cpath, '--serial', 'UNIT-1',
                    '--report-only'])
js4 = newest(os.path.join(d, 'reports'), '.json')
r4 = json.load(open(js4))
check('no board.conf: whole-unit report, 202 rows, no board block',
      len(r4['rows']) == 202 and 'board' not in r4 and
      os.path.basename(js4).startswith('UNIT-1-'))

# -- 6. setup pages ----------------------------------------------------------
pages = [dict(key='network'), dict(key='usb-pair'), dict(key='kit-bench')]


def keys(k, patch):
    return [p['key'] for p in RA.board_pages(pages, BB.scope(rows, k), patch)]


check('DSP card: no setup page at all', keys('dsp', False) == [])
check('Digital: network lead and USB sticks, no lead kit',
      keys('digital', False) == ['network', 'usb-pair'])
check('Analog: USB sticks and the lead kit',
      keys('analog', True) == ['usb-pair', 'kit-bench'])
check('Left panel: nothing to set up', keys('left', False) == [])

# -- 7. the analog station in a board scope ---------------------------------
def station_walk(profile):
    t = tempfile.mkdtemp(prefix='namm-d24-6-st-')
    sc = BB.scope(rows, profile)
    st = RA.State(os.path.join(t, 'state.json'), ID, md5)
    st.runnable = set(r.num for r in sc if r.category != 'not-run')
    unit, hands, glass, live, screens = R.rig(t)
    a = R.A()
    a.board = dict(profile=profile)
    RA.patch_station(a, 'M4', sc, st, set(), glass, 1, live=live,
                     keys=PT.KeyWatch(enabled=False))
    walked = []
    for p in R.walked(hands):
        if p not in walked:
            walked.append(p)
    return walked, st, sc


plist = PT.PatchList(R.LIST_DIR)


def patches_for(nums):
    out = set()
    for pid, rr in plist.patches:
        if {int(x) for r in rr for x in str(r.get('rows') or '').split()} & nums:
            out.add(pid)
    return out


w, st, sc = station_walk('right')
want = patches_for({95, 96})
check('right panel: the station walks only the mini-jack patches (%d)'
      % len(want), set(w) == want, (w, sorted(want)))
check('... and grades the jack-sense row 93 from them',
      st.verdict(93) in (RA.PASS, RA.FAIL, RA.NODATA), st.row(93))
w, st, sc = station_walk('phonejack')
want = patches_for({39, 40, 41, 42, 97})
check('phone jack board: the station walks only the jack patches (%d)'
      % len(want), set(w) == want, (w, sorted(want)))
check('... every jack row gets a verdict', all(
    st.verdict(n) for n in (39, 40, 41, 42, 97)),
    [(n, st.verdict(n)) for n in (39, 40, 41, 42, 97)])

# -- 8. the desk result file -------------------------------------------------
path, tally = BT.write_result(rep, os.path.join(tmp, 'results'))
lines = list(csv.DictReader(open(path)))
check('result file: one line per profile row, keyed by board ID',
      len(lines) == 45 and all(x['board_id'] == ID for x in lines)
      and os.path.basename(path).startswith(ID + '-dsp-'))
check('... every line has a verdict and a role',
      all(x['verdict'] and x['role'] for x in lines))
try:
    BT.write_result(r4, tmp)
    check('a whole-unit report is refused as a board result', False)
except SystemExit:
    check('a whole-unit report is refused as a board result', True)

shutil.rmtree(tmp, ignore_errors=True)
print('%s -- no unit, no bus, no write, no rails'
      % ('all checks passed' if not R.FAILS else
         '%d check(s) FAILED' % len(R.FAILS)))
sys.exit(1 if R.FAILS else 0)
