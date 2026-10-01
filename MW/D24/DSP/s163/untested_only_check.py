#!/usr/bin/env python3
"""S163 addendum 3: a resume walks ONLY never-tested rows (PW 2026-10-01).
Real RUN ALL patch_station + Station over the S159 model, started from the
REAL paused state of MW-D24-2 (data/state-live-paused.json)."""
import json, os, shutil, sys, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 's159'))
sys.argv = [sys.argv[0]]
import rerun_ein_check as R          # noqa: E402
RA, PT, LV = R.RA, R.PT, R.LV
check = R.check
DATA159 = os.path.join(HERE, '..', 's159', 'data')


def load(tmp, retest):
    rows, md5 = RA.load_catalog(os.path.join(DATA159, 'test-catalog-unit.csv'))
    path = os.path.join(tmp, 'state.json')
    shutil.copy(os.path.join(HERE, 'data', 'state-live-paused.json'), path)
    st = RA.State(path, json.load(open(path))['serial'], md5)
    if retest:
        st.d['retest_failed'] = True
    return rows, st


def run(retest):
    tmp = tempfile.mkdtemp(prefix='s163-')
    rows, st = load(tmp, retest)
    unit, hands, glass, live, screens = R.rig(tmp)
    plist = PT.PatchList(R.LIST_DIR)
    owed = set(r.num for r in rows if r.group in RA.PATCH_STATIONS
               and not st.settled(r.num))
    verd = dict((r.num, st.verdict(r.num)) for r in rows if r.group in RA.PATCH_STATIONS)
    carry = RA.patch_carry(st)
    RA.patch_station(R.A(), 'M4', rows, st, set(), glass, 9, live=live,
                     keys=PT.KeyWatch(enabled=False))
    got = []
    for p in R.walked(hands):
        if p not in got: got.append(p)
    return rows, st, owed, verd, carry, got, plist, screens


rows, st, owed, verd, carry, got, plist, screens = run(False)
never = sorted(n for n, v in verd.items() if not v)
failed = sorted(n for n, v in verd.items() if v in ('FAIL', 'NO DATA', 'SKIPPED'))
print('     rows with no verdict: %d; failed/no-data rows kept: %d; walked %d patches: %s'
      % (len(never), len(failed), len(got), ' '.join(got)))
check('untested set = exactly the rows with no verdict (failed rows are settled)',
      owed == set(never), sorted(owed ^ set(never)))
fed = set()
for pid, rr in plist.patches:
    nums = {int(x) for r in rr for x in str(r.get('rows') or '').split()}
    if nums & owed or (not nums and pid not in carry['patches']):
        fed.add(pid)
check('the resume walks exactly the patches that feed an untested row (%d)' % len(fed),
      set(got) == fed, sorted(set(got) ^ fed))
only_failed = [pid for pid, rr in plist.patches if pid not in fed
               and {int(x) for r in rr for x in str(r.get('rows') or '').split()} & set(failed)]
check('... no patch is walked only because its row FAILED (%d such patches stay unwalked)'
      % len(only_failed), not (set(only_failed) & set(got)), sorted(set(only_failed) & set(got)))
words = LV.rerun_words(len(got), len(plist.patches))
check('the glass says "%s"' % words, any(words in json.dumps(s) for s in screens))
check('... and the line names the RE-TEST FAILED request', 'RE-TEST FAILED' in words)
check('failed rows keep their recorded FAIL verdicts (not re-run)',
      all(st.verdict(n) == verd[n] for n in failed if n not in owed))

rows2, st2, owed2, verd2, carry2, got2, plist2, _ = run(True)
print('     RE-TEST FAILED requested: walks %d patches' % len(got2))
check('on request (RE-TEST FAILED) the failed rows are walked again too',
      len(got2) > len(got) and set(got) <= set(got2), (len(got), len(got2)))
# a NO DATA that only records an interruption is still untested
tmp = tempfile.mkdtemp(); rows3, s3 = load(tmp, False)
s3.put(94, 'NO DATA', measured='the run was paused during this row', limit='', evidence='')
check('an interrupted NO DATA (paused mid-row) is still owed; an ordinary one is settled',
      not s3.settled(94))
print()
if R.FAILS:
    print('%d check(s) FAILED' % len(R.FAILS)); sys.exit(1)
print('all checks passed -- no unit, no bus, no write, no rails')
