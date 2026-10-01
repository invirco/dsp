#!/usr/bin/env python3
"""rerun_ein_check.py -- S159 HUB ADDENDA 1 + 2, end to end on the model.

    python3 rerun_ein_check.py

RUN ALL's REAL `patch_station` (fold, state, carry) over the REAL `Station`,
started from TODAY'S REAL STATE (data/state-pass4.json, MW-D24-2 pass 4,
fetched read-only after the pause) and the unit's own catalog. Only the
hardware is the model: the unit, the chain, the operator's hands.

  1. THE FAILED-ONLY RE-RUN. The patches walked are exactly those that feed a
     row without a PASS, plus every 150 ohm patch (no input has a GRADED EIN
     yet), plus the line-input patches (they fold onto no row and have never
     passed); nothing that passed is walked; the glass says "Re-run: N of 92".
  2. THE EIN GRADE. limits.csv's -126.0 dBu / -129.5 dBu(A), units.csv's DAC
     full scale, each lane's balanced reference CARRIED from pass 4: a good
     input passes, MIC 2/3/4 (10 dB noisier, S158/A8) and MIC 8 / MIC 20
     (S55 -123.2 / -125.2) fail with "noise too high: X dBu, limit -126.0 dBu".
     The arithmetic is checked against S57-R's own worked example.
  3. THE FOLD. An EIN FAIL replaces the row's old ungraded PASS (forced, the
     PASS kept in history); an EIN PASS leaves a TRS fail on MIC 1's row as
     the ordinary gate would.
  4. THE SECOND RE-RUN walks only what is still owed.
"""
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
TOOLS = os.path.join(ROOT, 'tools', 'pi')
sys.path.insert(0, TOOLS)
os.environ.setdefault('MATRIX_ADDR_HOME', os.path.join(
    ROOT, 'MW', 'D24', 'DSP', 's138b', 'fixtures'))
os.environ['D24_UNIT'] = 'MW-D24-2'      # units.csv row, as the hostname is
import d24_live as LV        # noqa: E402
import d24_patch as PT       # noqa: E402
import d24_runall as RA      # noqa: E402
sys.path.insert(1, os.path.join(HERE, '..', 's157'))
import detector_dry_run as DR    # noqa: E402
import trs_dry_run as TD         # noqa: E402

LIST_DIR = os.path.join(ROOT, 'MW', 'D24', 'DSP', 's121')
DATA = os.path.join(HERE, 'data')
FAILS = []


def check(name, cond, detail=''):
    print('%-4s %s%s' % ('ok' if cond else 'FAIL', name,
                         (': ' + str(detail)) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


# The lane's terminated noise at code 63, mean square dBFS over DC-24k, as the
# capture would read it (the model's 20-20k is 0.79 dB under it). -94.6 is a
# good channel (S57 MIC 5); the others are the bench's own figures.
NOISE63 = dict((m, -94.6) for m in range(1, 25))
NOISE63.update({2: -84.6, 3: -84.6, 4: -85.0,      # A8: ~10 dB noisier
                8: -91.6, 20: -92.5})              # A5: S55 -123.2 / -125.2
STEP63 = 53.108
# THE MODEL'S LOOP, CALIBRATED TO THE UNIT'S OWN CARRIED REFERENCES: pass 4
# measured a code-0 loop gain of +5.5 dB at -145.2 deg on every input, so the
# model's AUX 1 -> MIC loop does the same (a model loop of -3 dB at 42 deg
# graded every carried-reference row as 8 dB off and the wrong polarity).
DR.TONE_LOSS_DB = -5.5
PT.World.REF_PHASE = -145.2


class EinWorld(PT.World):
    """Noise rows: the terminated lane at NOISE63 (the preamp model adds the
    code-63 step back), open 9 dB higher, a tone lead 35 dB higher."""
    def level(self, driven, lane, osc_on, osc_level):
        if osc_on:
            return PT.World.level(self, driven, lane, osc_on, osc_level)
        base = NOISE63.get(int(lane), -94.6) - STEP63
        if lane not in self.plugged_lanes:
            return base + self.OPEN_DB
        if self.plugged_lead != 'K5':
            return base + self.LEAD_IDLE_DB
        return base


class AnyHands(TD.TrsHands):
    """Every prompt: the socket clear, the lead in 2 s later -- the TRS lead
    into the jack the prompt names, as labelled."""
    def connect(self, patch, rows, glass):
        r = rows[0]
        if patch not in self.plan:
            if TD.PT.Station.trs(rows):
                self.plan[patch] = [(0.0, 'clear', None),
                                    (2.0, 'plugjack', r['out'])]
            else:
                self.plan[patch] = [(0.0, 'clear', None), (2.0, 'plug', None)]
            # a patch the model cannot complete is answered, not waited on
            # for ever -- and every one is listed by the check that reads it
            self.plan[patch].append((60.0, 'press', 'nosignal'))
        print('     prompt %s %s -> %s' % (patch, r['out'], r['in']),
              flush=True)
        return TD.TrsHands.connect(self, patch, rows, glass)


class Glass(DR.Glass):
    def __init__(self):
        DR.Glass.__init__(self)
        self.lines = []

    def progress(self, text):
        self.lines.append(text)


def fresh_state(tmp):
    rows, md5 = RA.load_catalog(os.path.join(DATA, 'test-catalog-unit.csv'))
    path = os.path.join(tmp, 'state.json')
    shutil.copy(os.path.join(DATA, 'state-pass4.json'), path)
    serial = json.load(open(path))['serial']
    st = RA.State(path, serial, md5)
    st.d['retest_failed'] = True      # S163: the on-request path (RE-TEST FAILED)
    return rows, st


ORIG = dict(find_list_dir=PT.find_list_dir, Unit=PT.Unit,
            pick_patcher=PT.pick_patcher, Analog=PT.Analog)


def rig(tmp):
    """Patch RUN ALL's hardware constructors onto the model. Returns the
    pieces the checks read back."""
    for k, v in ORIG.items():
        setattr(PT, k, v)
    PT.CLOCK = PT.VirtualClock()
    world = EinWorld()
    unit = TD.TrsUnit(world, TD.LABELLED)
    plist = PT.PatchList(LIST_DIR)
    send_pos = dict((int(r['lane']), int(r['send_pos'])) for r in plist.paths
                    if r.get('send_pos') != '' and str(r['lane']).isdigit())
    glass = Glass()
    logs = glass.lines
    hands = AnyHands(glass, unit, logs.append)
    an = PT.SimAnalog(world, plist.gain, send_pos)
    an.image = [0x00] * 24 + [0x00]
    an.safe_image = [0x01] * 24 + [0x00]
    RA.PT.find_list_dir = lambda *_a, **_k: LIST_DIR
    RA.PT.Unit = lambda *a, **k: unit
    RA.PT.pick_patcher = lambda *a, **k: hands
    RA.PT.Analog = lambda *a, **k: an
    live = LV.Live(tmp, run='patch', enabled=True, confirm=False)
    screens = []
    orig = live._flush

    def flush():
        orig()
        screens.append(dict(live.d))
    live._flush = flush
    return unit, hands, glass, live, screens


class A(object):
    patch_symdir = None
    keep_rails_from_auto = False


def owed_now(rows, state):
    return set(r.num for r in rows if r.group in RA.PATCH_STATIONS
               and state.verdict(r.num) != RA.PASS)


def expected_walk(plist, owed, patches_rec):
    out = []
    for pid, rr in plist.patches:
        rec = patches_rec.get(pid) or {}
        if rr[0]['expect'] == 'noise':
            if rec.get('ein') != 'PASS':
                out.append(pid)
            continue
        # S164: a gain-walk patch is also owed while its headroom sub-test
        # (no catalog row) has not been recorded -- on RE-TEST FAILED, until
        # it has passed
        if hr_owed(rr, rec):
            out.append(pid)
            continue
        nums = {int(x) for r in rr for x in str(r.get('rows') or '').split()}
        if nums:
            if nums & owed:
                out.append(pid)
        elif rec.get('verdict') != 'PASS':
            out.append(pid)
    return out


def hr_owed(rr, rec):
    return (any(r.get('sub') == 'hr' for r in rr)
            and (rec.get('hr') or {}).get('verdict') != 'PASS')


def walked(hands):
    return [p for p, _in, _out, _t in hands.prompts]


def case_s57_arithmetic():
    """S57-R's own worked example through the scorer: P -94.63 dBFS 20-20k,
    code-0 loop gain 5.578, step 53.139, DAC FS 23.13 -> -127.21 dBu."""
    lim = PT.Limits.load(LIST_DIR)
    check('limits read FROM limits.csv / units.csv: -126.0, -129.5, 23.13',
          (lim.get('t4b_ein_max_dbu'), lim.get('t4b_ein_a_max_dbu'),
           lim.get('dac_fs_dbu')) == (-126.0, -129.5, 23.13),
          (lim.get('t4b_ein_max_dbu'), lim.get('t4b_ein_a_max_dbu'),
           lim.get('dac_fs_dbu')))
    sc = PT.Scorer(lim)
    sc.ref[5] = dict(h_db=5.578, h_deg=0.0)
    row = dict(lane='5', expect='noise', level_ref='ein', **{'in': 'MIC 5'})
    meas = dict(rms=-91.63, ein_band_dbfs=-94.63, ein_a_dbfs=-97.93,
                ein_total_dbfs=-91.63, ein_caps=2, ein_n=16384,
                ein_settle_s=3.0, gain_step_db=53.139, gain_code=63,
                dac_fs_dbu=23.13, ein_overruns=[0, 0])
    v, why, notes = sc.score(row, meas, None, {}, [])
    check('S57-R example: EIN -127.21 dBu / -130.51 dBu(A), PASS',
          v == 'PASS' and abs(meas['ein_dbu'] + 127.21) < 0.01
          and abs(meas['ein_a_dbu'] + 130.51) < 0.01,
          (v, why, meas.get('ein_dbu'), meas.get('ein_a_dbu')))
    meas2 = dict(meas, ein_band_dbfs=-84.63, ein_a_dbfs=-87.93)
    v, why, notes = sc.score(row, meas2, None, {}, [])
    check('10 dB noisier: FAIL "noise too high: -117.2 dBu, limit -126.0 dBu"',
          v == 'FAIL' and why.startswith('noise too high: -117.2 dBu, limit '
                                         '-126.0 dBu'), why)
    del sc.ref[5]
    v, why, _n = sc.score(row, dict(meas), None, {}, [])
    check('no reference on the lane: NO DATA, never a guessed gain',
          v == 'NO DATA', why)


def case_rerun_and_ein():
    tmp = tempfile.mkdtemp(prefix='s159-rerun-')
    rows, state = fresh_state(tmp)
    unit, hands, glass, live, screens = rig(tmp)
    plist = PT.PatchList(LIST_DIR)
    owed = owed_now(rows, state)
    carry = RA.patch_carry(state)
    missing = sorted(set(str(m) for m in range(1, 25))
                     - set(carry['lane_refs']), key=int)
    check('carry: pass-4 references backfilled for 22 inputs (MIC 1 5.28, '
          'MIC 2 5.55); MIC 7 and MIC 24 have none (their rows hold the '
          'failing gain step) and are re-measured by their own re-walked '
          'K1 patch', missing == ['7', '24']
          and carry['lane_refs']['1']['h_db'] == 5.28
          and carry['lane_refs']['2']['h_db'] == 5.55, missing)
    want = expected_walk(plist, owed, carry['patches'])
    before = dict((k, state.verdict(int(k))) for k in ('1', '2', '3', '4',
                                                       '21', '22', '23'))
    RA.patch_station(A(), 'M4', rows, state, set(), glass, 5, live=live,
                     keys=PT.KeyWatch(enabled=False))
    got = walked(hands)
    got_u = []
    for p in got:
        if p not in got_u:
            got_u.append(p)
    print('     re-run walked %d patches: %s' % (len(got_u), ' '.join(got_u)))
    check('re-run walks exactly the owed patches (%d of %d)'
          % (len(want), len(plist.patches)),
          got_u == want, (len(got_u), len(want),
                          sorted(set(want) ^ set(got_u))))
    rec0 = RA.patch_carry(fresh_state(tempfile.mkdtemp())[1])['patches']
    passed = [p for p in ('P1', 'P2', 'P12', 'P36', 'P61', 'P62')
              if p in got_u and not hr_owed(dict(plist.patches)[p],
                                            rec0.get(p) or {})]
    check('... and nothing that passed today (P1 P2 P12 P36 P61 P62) except '
          'for a headroom sub-test never recorded (S164)', not passed, passed)
    words = LV.rerun_words(len(want), len(plist.patches))
    check('the glass says "%s"' % words,
          any(s.get('status') == words or words in str(s.get('lead_line'))
              or words in str(s.get('instruction')) for s in screens))
    st_rows = state.d['rows']
    def last(num):
        return st_rows[str(num)]
    m1, m2, m3, m4 = last(1), last(2), last(3), last(4)
    check('MIC 1 (row 1): EIN PASS, -127.9 dBu against -126.0, with the '
          'carried pass-4 reference',
          m1['verdict'] == 'PASS' and 'EIN -127.' in m1['measured']
          and 'carried from pass 4' in m1['limit'],
          (m1['verdict'], m1['measured'], m1['limit'][:200]))
    for num, name in ((2, 'MIC 2'), (3, 'MIC 3'), (4, 'MIC 4')):
        e = last(num)
        check('%s (row %d): FAIL "noise too high: -11x dBu, limit -126.0 '
              'dBu", replacing its old PASS (kept in history)'
              % (name, num),
              e['verdict'] == 'FAIL'
              and e['measured'].startswith('noise too high: -11')
              and 'limit -126.0 dBu' in e['measured']
              and any(h['verdict'] == 'PASS' for h in e['history']),
              (e['verdict'], e['measured']))
    # MIC 8 is row 23, MIC 20 row 24 (catalog order: J31 / J32)
    for num, name in ((23, 'MIC 8'), (24, 'MIC 20')):
        e = last(num)
        check('%s (row %d): FAIL on the EIN (S55 HF excess)' % (name, num),
              e['verdict'] == 'FAIL' and 'noise too high' in e['measured'],
              (e['verdict'], e['measured']))
    trs = [last(n)['verdict'] for n in (39, 40, 41, 42)]
    check('the TRS rows 39-42 graded PASS on the labelled model', trs ==
          ['PASS'] * 4, trs)
    check('state keeps lane_refs, patch_loop and per-patch records with EIN',
          state.d.get('lane_refs') and state.d.get('patches', {})
          .get('P38', {}).get('ein') == 'FAIL'
          and state.d['patches'].get('P37', {}).get('ein') == 'PASS',
          (state.d.get('patches', {}).get('P38'),
           state.d.get('patches', {}).get('P37')))
    # -- the second re-run: only what is still owed ---------------------------
    unit2, hands2, glass2, live2, _s2 = rig(tmp)
    owed2 = owed_now(rows, state)
    want2 = expected_walk(plist, owed2, RA.patch_carry(state)['patches'])
    RA.patch_station(A(), 'M4', rows, state, set(), glass2, 6, live=live2,
                     keys=PT.KeyWatch(enabled=False))
    got2 = []
    for p in walked(hands2):
        if p not in got2:
            got2.append(p)
    print('     second re-run walked %d: %s' % (len(got2), ' '.join(got2)))
    still = sorted(n for n in owed2 if 1 <= n <= 24)
    print('     rows still owed after the first re-run: %s' % sorted(owed2))
    check('the second re-run walks exactly what is still owed (%d): the '
          'EIN-failing inputs\' 150 ohm patches, the K1 patches of their now-'
          'failing rows %s, and any line patch that has not passed (the '
          'S157 model\'s noisy MIC 15 floor grades P81 NO DATA)'
          % (len(want2), still), got2 == want2 and len(got2) < 20,
          (got2, want2))


def main():
    for fn in (case_s57_arithmetic, case_rerun_and_ein):
        print('-- %s' % fn.__name__)
        fn()
    print()
    if FAILS:
        print('%d check(s) FAILED' % len(FAILS))
        return 1
    print('all checks passed -- no unit, no bus, no write, no rails')
    return 0


if __name__ == '__main__':
    sys.exit(main())
