#!/usr/bin/env python3
"""s164_check.py -- S164 end to end on the model, from the unit's REAL state.

    python3 s164_check.py

  1. THE LIST. AUX A single-ended rows name `trs_aux_out_db`; the front phones
     jack has its patch (L normal / R inverted / null, by the donor's pan) on
     row 97; every gain-walk patch carries one headroom sub-test on no catalog
     row; `Mon PhonesLevel` is opened at unity; the -20 dB pad lead is in the
     plan's owed fixtures.
  2. THE LIMITS. trs_aux_out_db 0.00 (derived), phones_out_db and
     headroom_ref_dbu `nan` = recorded, not judged; a key the list names and
     the limits do not declare stops the station.
  3. THE SCORER. AUX A at the unit's measured -1.42 dB PASSES (the old
     -6.02 expectation failed it +4.6 dB); a dead-halved leg still FAILS; the
     phones level is recorded, its polarity and the null are judged.
  4. THE RESUME, from MW-D24-2's paused state (data/state-live-paused.json,
     fetched read-only after the PAUSE) and the unit's catalog: P63 stays
     untested and is walked; row 97's catalog NOT TESTED no longer blocks its
     new patch; the 24 gain-walk patches are walked for their headroom
     sub-test ALONE (no gain step re-measured, rows 1-24 unchanged); every
     headroom is recorded in state.json with dBu/dBFS/THD.
  5. THE REFERENCE. headroom_ref.py averages the pass, leaves out and names an
     input more than 3 dB from the median, writes the limits; the next pass
     grades against it (1.0 dB PROVISIONAL window).

The hardware is the model (S157/S159's), with the phones jack added and a
converter that reaches 1 % THD at -0.3 dBFS on the lane.
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..', 's159'))
sys.argv = [sys.argv[0]]
import rerun_ein_check as R          # noqa: E402
RA, PT, LV, TD, DR = R.RA, R.PT, R.LV, R.TD, R.DR
check = R.check
LIST_DIR = R.LIST_DIR
DATA = os.path.join(HERE, 'data')
GEN = os.path.join(ROOT, 'tools', 'accept', 'gen_patch_paths.py')
REF = os.path.join(ROOT, 'tools', 'accept', 'headroom_ref.py')

PHONES_DB = -6.02          # the model's phones leg: the design figure
CLIP_DBFS = -0.3           # the converter's 1 % point on the lane
# per-input clip offsets: MIC 5 4 dB early (the exclusion), MIC 9 1.5 dB late
HR_FAULTS = ('hr:MIC 5:-4.0', 'hr:MIC 9:1.5')


class PhonesUnit(TD.TrsUnit):
    """S159's TRS model plus the front phones jack: its tip is the main bus's
    LEFT leg and its ring the RIGHT, so the donor's pan picks the leg."""
    def _jack(self, lane):
        drv = set(self.driven())
        for d, lanes, _in, _lead in self.plugs:
            if lane in lanes and d == 'jack:PHONES':
                legs = self.main_legs() if 'main' in drv else []
                return ('L' in legs, 'R' in legs)
        return TD.TrsUnit._jack(self, lane)

    def tone_db(self, lane):
        j = self._jack(lane) if self.osc_on and lane != self.osc_chan else None
        plugged = any(d == 'jack:PHONES' for d, _l, _i, _k in self.plugs)
        if j is not None and plugged and (j[0] != j[1]):
            return (self.osc_level - DR.TONE_LOSS_DB + PHONES_DB
                    + self.w.preamp_db(lane))
        return TD.TrsUnit.tone_db(self, lane)


class Hands(R.AnyHands):
    """AnyHands, with the TRS lead's jack end going into PHONES for the
    phones patch, and every prompt's sub-tests recorded."""
    def __init__(self, *a, **k):
        R.AnyHands.__init__(self, *a, **k)
        self.subs = {}

    def connect(self, patch, rows, glass):
        self.subs.setdefault(patch, []).append([r.get('sub') for r in rows])
        if rows[0]['out'] == 'PHONES' and patch not in self.plan:
            self.plan[patch] = [(0.0, 'clear', None),
                                (2.0, 'plugjack', 'PHONES'),
                                (60.0, 'press', 'nosignal')]
        return R.AnyHands.connect(self, patch, rows, glass)


def rig(tmp):
    unit, hands, glass, live, screens = R.rig(tmp)
    world = unit.w
    world.HR_CLIP_DBFS = CLIP_DBFS
    world.faults.update(HR_FAULTS)
    pu = PhonesUnit(world, TD.LABELLED)
    hh = Hands(glass, pu, glass.lines.append)
    RA.PT.Unit = lambda *a, **k: pu
    RA.PT.pick_patcher = lambda *a, **k: hh
    return pu, hh, glass, live, screens


def paused_state(tmp):
    rows, md5 = RA.load_catalog(os.path.join(DATA, 'test-catalog-unit.csv'))
    path = os.path.join(tmp, 'state.json')
    shutil.copy(os.path.join(DATA, 'state-live-paused.json'), path)
    RA.classify(rows)                 # as the runner does before the State
    st = RA.State(path, json.load(open(path))['serial'], md5)
    st.runnable = set(r.num for r in rows if r.category != 'not-run')
    return rows, st


def read_csv(path):
    with open(path, newline='') as fh:
        return list(csv.DictReader(l for l in fh if not l.startswith('#')))


# ---------------------------------------------------------------------------
def case_list():
    plist = PT.PatchList(LIST_DIR)
    by = dict(plist.patches)
    trs = [r for p in ('P63', 'P64', 'P65', 'P66') for r in by[p]
           if r['level_ref'] == 'single']
    check('AUX A: 8 single-ended rows, every one on trs_aux_out_db',
          len(trs) == 8 and {r['level_key'] for r in trs} == {'trs_aux_out_db'},
          [(r['patch'], r['sub'], r['level_key']) for r in trs])
    ph = by.get('P67') or []
    check('P67 is the front PHONES jack on row 97: L main:L normal, R main:R '
          'inverted, null main:C, all on MIC 1 with the K2 lead',
          [(r['out'], r['sub'], r['drive'], r['polarity'], r['rows'], r['in'],
            r['lead']) for r in ph] ==
          [('PHONES', 'L', 'main:L', 'normal', '1 97', 'MIC 1', 'K2'),
           ('PHONES', 'R', 'main:R', 'inverted', '1 97', 'MIC 1', 'K2'),
           ('PHONES', 'null', 'main:C', '-', '1 97', 'MIC 1', 'K2')],
          [(r['out'], r['sub'], r['drive'], r['polarity'], r['rows']) for r in ph])
    check('... its single rows name phones_out_db',
          {r['level_key'] for r in ph if r['level_ref'] == 'single'}
          == {'phones_out_db'})
    hr = [r for r in plist.paths if r['sub'] == 'hr']
    walks = [pid for pid, rr in plist.patches
             if any(r.get('gain_code') == '1' for r in rr)]
    check('one headroom sub-test per gain-walk patch (24), last in the patch, '
          'gain code 0, on no catalog row',
          len(hr) == 24 == len(walks)
          and all(dict(plist.patches)[r['patch']][-1] is r for r in hr)
          and all(r['gain_code'] == '0' and r['rows'] == ''
                  and r['expect'] == 'headroom' for r in hr),
          (len(hr), len(walks)))
    check('... MIC 1..24, each on its own lane',
          sorted(int(r['lane']) for r in hr) == list(range(1, 25)))
    masters = plist.routes['_standing_masters']
    check('Mon PhonesLevel opened at unity in the standing write',
          'Mon001PhonesLevel001=f1.0' in masters)
    check('the phones null pans the donor to the middle (index 63)',
          'Chan024Pan001=f0.5' in plist.routes['mainC@24']
          and 'Chan024MainOn001=1' in plist.routes['mainC@24'])
    plan = open(os.path.join(LIST_DIR, 'patch-plan.md')).read()
    check('the plan lists the -20 dB pad lead as an owed fixture, with the '
          'OUTPUT headroom it enables',
          '## Fixtures owed' in plan and '-20 dB pad' in plan
          and 'OUTPUT headroom' in plan)
    check('PHONES L / R are proved by P67 in the coverage table, and nothing '
          'is left in "not run"',
          '| PHONES L | 97 | P67 |' in plan and '| PHONES R | 97 | P67 |' in plan
          and plan.split('### Not run, and why')[1].count('\n| ') == 1, '')
    out = subprocess.run([sys.executable, GEN, '--out',
                          tempfile.mkdtemp(prefix='s164-gen-')],
                         capture_output=True, text=True)
    tmpd = out.stdout.split('wrote ')[1].split('/patch-paths.csv')[0] \
        if 'wrote ' in out.stdout else None
    same = tmpd and all(open(os.path.join(ROOT, tmpd, f)).read() ==
                        open(os.path.join(LIST_DIR, f)).read()
                        for f in ('patch-paths.csv', 'patch-routes.csv',
                                  'patch-plan.md'))
    check('the committed list is exactly what the generator writes', same,
          out.stdout[-300:] + out.stderr[-300:])


def case_limits():
    lim = PT.Limits.load(LIST_DIR)
    check('trs_aux_out_db = 0.00 (unity NJM4580L re-receiver)',
          lim.window('trs_aux_out_db') == 0.0)
    check('phones_out_db and headroom_ref_dbu are declared and unset (nan)',
          lim.window('phones_out_db') is None
          and lim.window('headroom_ref_dbu') is None)
    check('the old single_ended_db is gone', 'single_ended_db' not in lim
          and 'single_ended_db' not in lim.blank)
    check('headroom keys: -40 dB target, -12 start, 0.5 step, 0 ceiling, '
          '1.0 dB tolerance, 3.0 dB exclusion',
          (lim['headroom_thd_db'], lim['headroom_start_dbfs'],
           lim['headroom_step_db'], lim['headroom_drive_max_dbfs'],
           lim['headroom_tol_db'], lim['headroom_exclude_db'])
          == (-40.0, -12.0, 0.5, 0.0, 1.0, 3.0))
    try:
        lim.window('no_such_key_db')
        ok = False
    except SystemExit:
        ok = True
    check('a key the limits do not declare stops the station (no default)', ok)


def case_scorer():
    lim = PT.Limits.load(LIST_DIR)
    sc = PT.Scorer(lim)
    sc.ref[1] = dict(h_db=5.28, h_deg=-145.2)
    plist = PT.PatchList(LIST_DIR)
    by = dict(plist.patches)
    L63 = by['P63'][0]
    floor = -112.7

    def score(row, h, deg, sibs=()):
        meas = dict(h_db=h, h_deg=deg, coh_dbfs=h - 12.0, thd=-80.0)
        return sc.score(row, meas, floor, {}, list(sibs), donor=24)
    v, why, notes = score(L63, 5.28 - 1.42, -145.2)
    check('P63 L as the unit read it (ref - 1.42 dB): PASS (was "+4.6 dB '
          'off" against the old -6.02)', v == 'PASS', (v, why, notes))
    v, why, _n = score(L63, 5.28 - 6.02, -145.2)
    check('... a leg at the OLD expectation (6 dB down) now FAILS',
          v == 'FAIL' and 'off what this output should give' in why, (v, why))
    v, why, _n = score(L63, 5.28 - 1.42, 34.8)
    check('... the tip inverted still FAILS (tip and ring swapped)',
          v == 'FAIL' and 'inverted' in why, (v, why))
    PL, PR, PN = by['P67']
    v, why, notes = score(PL, 5.28 - 6.02, -145.2)
    check('phones L: level RECORDED, NOT JUDGED (phones_out_db nan), PASS',
          v == 'PASS' and any('RECORDED, NOT JUDGED' in n for n in notes),
          (v, why, notes))
    v, why, _n = score(PL, 5.28 - 30.0, -145.2)
    check('... even 24 dB off is recorded, not failed, until it is set',
          v == 'PASS', (v, why))
    sib = [dict(level_ref='single', h_db=5.28 - 6.02)]
    v, why, _n = score(PR, 5.28 - 6.02, 34.8, sib)
    check('phones R inverted (the ring through tip-minus-ring): PASS',
          v == 'PASS', (v, why))
    v, why, _n = score(PR, 5.28 - 6.02, -145.2, sib)
    check('phones R in phase: FAIL', v == 'FAIL', (v, why))
    v, why, _n = score(PR, 5.28 - 9.0, 34.8, sib)
    check('phones L/R 3 dB apart: FAIL on the stereo match (1.5 dB)',
          v == 'FAIL' and 'differ' in why, (v, why))
    sib2 = sib + [dict(level_ref='single', h_db=5.28 - 6.02)]
    v, why, _n = score(PN, 5.28 - 6.02 - 45.0, 0.0, sib2)
    check('phones null 45 dB down: PASS', v == 'PASS', (v, why))
    v, why, _n = score(PN, 5.28 - 6.02 - 10.0, 0.0, sib2)
    check('phones null only 10 dB down: FAIL', v == 'FAIL', (v, why))


def case_resume():
    tmp = tempfile.mkdtemp(prefix='s164-resume-')
    rows, st = paused_state(tmp)
    check('row 97 holds the catalog\'s NOT TESTED (S117 era); runnable now, '
          'so it is NOT settled', st.verdict(97) == 'NOT TESTED'
          and 97 in st.runnable and not st.settled(97))
    check('... a NOT TESTED row that is still not-run stays settled',
          any(st.verdict(r.num) == 'NOT TESTED' and st.settled(r.num)
              for r in rows if r.category == 'not-run'))
    check('rows 39-42 (P63-P66) have no verdict: P63 is untested, not FAIL',
          all(st.verdict(n) in ('', None) for n in (39, 40, 41, 42)))
    before = dict((n, st.verdict(n)) for n in range(1, 25))
    hist = dict((n, len((st.row(n) or {}).get('history') or []))
                for n in range(1, 25))
    unit, hands, glass, live, screens = rig(tmp)
    plist = PT.PatchList(LIST_DIR)
    RA.patch_station(R.A(), 'M4', rows, st, set(), glass, 5, live=live,
                     keys=PT.KeyWatch(enabled=False))
    got = []
    for p in R.walked(hands):
        if p not in got:
            got.append(p)
    print('     resume walked %d: %s' % (len(got), ' '.join(got)))
    walks = [pid for pid, rr in plist.patches
             if any(r.get('sub') == 'hr' for r in rr)]
    k2on = [pid for pid, _rr in plist.patches
            if int(pid[1:]) >= 63]
    check('the resume walks the 24 gain-walk patches (headroom) and P63-P93 '
          '(untested) -- %d patches' % (len(walks) + len(k2on)),
          got == walks + k2on, sorted(set(got) ^ set(walks + k2on)))
    only_hr = all(hands.subs[p] == [['hr']] for p in walks)
    check('... each gain-walk patch is prompted for its headroom sub-test '
          'ALONE: no gain step re-measured', only_hr,
          dict((p, hands.subs[p]) for p in walks if hands.subs[p] != [['hr']]))
    after = dict((n, st.verdict(n)) for n in range(1, 25))
    hist2 = dict((n, len((st.row(n) or {}).get('history') or []))
                 for n in range(1, 25))
    # row 1 is MIC 1, which the TRS and phones patches also fold onto
    check('... rows 1-24 keep their verdicts; rows 2-24 gain no new entry '
          '(row 1 is also folded by the TRS/phones patches read on MIC 1)',
          before == after and all(hist[n] == hist2[n] for n in range(2, 25)),
          [(n, before[n], after[n]) for n in before if before[n] != after[n]])
    trs = [st.verdict(n) for n in (39, 40, 41, 42)]
    check('P63-P66 graded PASS against trs_aux_out_db (model leg -1.42 dB)',
          trs == ['PASS'] * 4, (trs, [l for l in glass.lines
                                      if 'P63' in l][-4:]))
    e97 = st.row(97) or {}
    check('row 97 (front phones): PASS on its new patch, the level recorded',
          e97.get('verdict') == 'PASS', (e97.get('verdict'),
                                         e97.get('measured'), e97.get('limit')))
    pats = st.d.get('patches') or {}
    hrs = dict((pid, pats.get(pid, {}).get('hr')) for pid in walks)
    check('state.json keeps a headroom record for all 24 inputs',
          all(hrs.values()), [p for p, v in hrs.items() if not v])
    exp = {}
    for pid, rr in plist.patches:
        r = rr[-1]
        if r.get('sub') != 'hr':
            continue
        n = int(r['lane'])
        clip = CLIP_DBFS + {5: -4.0, 9: 1.5}.get(n, 0.0)
        exp[pid] = clip + DR.TONE_LOSS_DB - plist.gain[0]['expected_db'] + 23.13
    # MIC 15 is S157's noisy-floor lane (RMS floor -75.5 dBFS): the model
    # calls the lead in before it is, so its ramp runs on no tone -- which is
    # exactly the case the scorer must NOT turn into "headroom above X"
    m15 = [p for p in walks if dict(plist.patches)[p][-1]['lane'] == '15'][0]
    check('MIC 15 (the model\'s noisy lane, no tone under the ramp): NO DATA '
          '"no tone reached", never a "headroom above" claim',
          hrs[m15] and hrs[m15]['verdict'] in ('NO DATA', 'FAIL')
          and 'no tone reached MIC 15' in (hrs[m15].get('why') or '')
          and not hrs[m15].get('hr_reached'), hrs[m15])
    bad = [(p, hrs[p].get('hr_dbu'), round(exp[p], 2)) for p in walks
           if p != m15 and (hrs[p] is None or hrs[p].get('hr_dbu') is None
                            or abs(hrs[p]['hr_dbu'] - exp[p]) > 0.05)]
    check('every other headroom = the model\'s 1 %% point in dBu (drive + '
          '23.13), to 0.05 dB: MIC 1 %.2f dBu' % exp[walks[0]], not bad, bad)
    h1 = hrs[walks[0]]
    check('... with dBFS at the converter and THD+N at the crossing = -40 dB',
          abs(h1['hr_dbfs'] - CLIP_DBFS) < 0.05
          and abs(h1['hr_thd_db'] + 40.0) < 0.01 and h1['verdict'] == 'PASS'
          and 'RECORDED' not in (h1.get('why') or '')
          and '1.000 %' in (h1.get('why') or ''), h1)
    hrlog = [l for l in glass.lines if 'headroom ramp' in l]
    check('the ramp is logged step by step (drive:THD+N), 0.5 dB apart, for '
          'every input', all(any(l.startswith('MIC %d headroom' % n)
                                 for l in hrlog) for n in range(1, 25))
          and ' -12.0:' in hrlog[0] and ' -11.5:' in hrlog[0], hrlog[:1])
    return st, tmp


def case_reference(st, tmp):
    lim_dir = tempfile.mkdtemp(prefix='s164-lim-')
    for f in os.listdir(LIST_DIR):
        p = os.path.join(LIST_DIR, f)
        if os.path.isfile(p):
            shutil.copy(p, lim_dir)
    limp = os.path.join(lim_dir, 'patch-limits.csv')
    orig = open(limp).read()
    out = subprocess.run([sys.executable, REF, '--state', st.path, '--limits',
                          limp, '--write'], capture_output=True, text=True)
    print('\n'.join('     ' + l for l in out.stdout.splitlines()[-3:]))
    new = open(limp).read()
    lim = PT.Limits.load(lim_dir)
    vals = [v for k, v in lim.items() if k.startswith('headroom_mic')]
    med = sorted(vals)[11:13]
    kept = [v for v in vals if abs(v - sum(med) / 2) <= 3.0]
    check('headroom_ref.py: 23 per-input values written (MIC 15 has none), '
          'the reference = the average of the inputs within 3 dB of the median',
          out.returncode == 0 and len(vals) == 23
          and abs(lim['headroom_ref_dbu'] - sum(kept) / len(kept)) < 0.01,
          (out.returncode, out.stderr[-300:], len(vals)))
    src = [r for r in read_csv(limp) if r['key'] == 'headroom_ref_dbu'][0]
    check('... MIC 5 (4 dB early) is LEFT OUT and named, MIC 15 named as '
          'having no level; MIC 9 (+1.5) is kept',
          len(kept) == 22 and 'MIC 5 ' in src['source']
          and 'MIC 15 (no 1 % level' in src['source']
          and 'MIC 9' not in src['source'].split('left out')[1],
          src['source'])
    check('... the source names the unit and the pass',
          'pass 5' in src['source'] and st.d['serial'] in src['source'],
          src['source'])
    keep_lines = [l for l in orig.split('\n')
                  if not l.startswith(('headroom_ref_dbu,', 'headroom_mic'))]
    check('... every other line of the hand-tuned file is untouched',
          [l for l in new.split('\n')
           if not l.startswith(('headroom_ref_dbu,', 'headroom_mic'))]
          == keep_lines)
    # the next pass grades against it
    sc = PT.Scorer(lim)
    ref = lim['headroom_ref_dbu']
    row = dict(expect='headroom', lane='3', level_ref='headroom', polarity='-',
               **{'in': 'MIC 3'})

    def g(dbu):
        m = dict(hr_steps=[(-12.0, -80.0, -6.5)], hr_reached=True,
                 hr_dbu=dbu, hr_dbfs=-0.3, hr_drive_dbfs=dbu - 23.13,
                 hr_thd_db=-40.0)
        return sc.score(row, m, -110.0, {}, [])
    v1, w1, _ = g(ref - 0.6)
    v2, w2, _ = g(ref - 1.4)
    v3, w3, _ = g(ref + 3.0)
    check('the next pass grades it: 0.6 dB under PASS, 1.4 dB under FAIL '
          '(PROVISIONAL 1.0 dB), above never fails',
          (v1, v2, v3) == ('PASS', 'FAIL', 'PASS'), (w1, w2, w3))
    m = dict(hr_steps=[(-12.0, -80.0, -6.5), (0.0, -55.0, 5.0)],
             hr_reached=False, hr_dbu=23.13, hr_dbfs=5.0, hr_drive_dbfs=0.0,
             hr_thd_db=-55.0)
    v, why, _ = sc.score(row, m, -110.0, {}, [])
    check('a ramp that never reaches 1 % records "headroom above X dBu"',
          v == 'PASS' and why.startswith('headroom above 23.1 dBu'), why)


def main():
    for f in (case_list, case_limits, case_scorer):
        print('-- %s' % f.__name__)
        f()
    print('-- case_resume')
    st, tmp = case_resume()
    print('-- case_reference')
    case_reference(st, tmp)
    print()
    if R.FAILS:
        print('%d check(s) FAILED' % len(R.FAILS))
        return 1
    print('all checks passed -- no unit, no bus, no write, no rails')
    return 0


if __name__ == '__main__':
    sys.exit(main())
