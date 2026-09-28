#!/usr/bin/env python3
"""mj_sense_check.py -- S138b: the mini-jack insertion sense (gaps doc 2.2),
folded into the mini-jack step of the analog patch loop per PW's ADDENDUM 1 of
2026-09-28, "one insertion, two results". No unit, no bus, no serial port.

What has to be true, and all of it is asserted here:

  * THE LISTEN IS ARMED BEFORE THE INSTRUCTION. That is the whole mechanism --
    the cell is pushed on change, so an edge that lands before anything is
    listening is gone -- and it is proved by ordering, not by reading the code:
    the arm's sequence number must be lower than the first mini-jack screen's.
  * ONE INSERTION, TWO RESULTS: the same patch that grades the L/R signal rows
    (95/96) also produces row 93, and the operator is asked for nothing extra.
  * The off-edge is free, because the NEXT mini-jack patch's own prompt is what
    takes the plug out. Only a list with a single mini-jack patch spends a
    screen on it.
  * PASS on both edges; FAIL naming what is missing when the cell answered but
    the value never moved; NO DATA -- never FAIL -- when nothing was
    transmitted at all, which is what today's unit will do, because its panel
    firmware does not carry the cell.
  * The detect row carries `rows=93`, so `d24_runall.patch_station` folds it
    onto the catalog row with no special case.
  * Nothing on this path writes anything.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, '..', '..', '..', '..', 'tools', 'pi')
sys.path.insert(0, TOOLS)
os.environ.setdefault('MATRIX_ADDR_HOME', os.path.join(HERE, 'fixtures'))
import d24_live as LV       # noqa: E402
import d24_patch as PT      # noqa: E402

LIST_DIR = os.path.join(HERE, '..', 's121')
FAILS = []
SEQ = [0]


def nxt():
    SEQ[0] += 1
    return SEQ[0]


def check(name, cond, detail=''):
    print('%-4s %s%s' % ('ok' if cond else 'FAIL', name,
                         (': ' + detail) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


class FakeSense(object):
    """`MiniJackSense` with the port replaced by a script.

    `script` is a list of (value, after_n_drains): the edge the panel MCU
    pushes, and how many drains into the listen it arrives. `writes` exists so
    the proof can assert that nothing ever writes -- it is never incremented,
    because there is no code path that would.
    """

    def __init__(self, script=(), ok=True, why=''):
        self.script = list(script)
        self.ok = ok
        self.why = why or ('the matrix bus could not be opened for the '
                           'mini-jack sense')
        self.events = []
        self.armed_at = None
        self.arms = []
        self.drains = 0
        self.closed = 0
        self.writes = 0

    def arm(self):
        if not self.ok:
            return False
        self.events = []
        self.drains = 0
        self.armed_at = 0.0
        self.arms.append(nxt())
        return True

    def drain(self):
        if not self.ok or self.armed_at is None:
            return []
        self.drains += 1
        out = [(v, float(self.drains))
               for v, when in self.script if when == self.drains]
        self.events += out
        return out

    def close(self):
        self.closed += 1
        self.ok = False


class ScriptGlass(object):
    def __init__(self):
        self.posts = []
        self.lines = []

    def post(self, kind, title, lines, buttons, **extra):
        self.posts.append(dict(kind=kind, title=title, lines=list(lines),
                               buttons=list(buttons), seq=nxt()))
        return list(buttons)

    def poll(self, btns):
        return dict(button='done')

    def ask(self, kind, title, lines, buttons, **extra):
        self.post(kind, title, lines, buttons, **extra)
        return dict(button=buttons[0])

    def clear(self):
        pass

    def progress(self, text):
        self.lines.append(text)

    def done(self, token):
        pass

    def connect(self, patch, rows, glass):
        self.posts.append(dict(kind='connect', title=patch, lines=[],
                               buttons=[], seq=nxt()))
        return patch


def build(sense, list_dir=LIST_DIR, mj_input=None):
    PT.CLOCK = PT.VirtualClock()
    plist = PT.PatchList(list_dir)
    world = PT.World()
    glass = ScriptGlass()
    unit = PT.SimUnit(world)
    send_pos = dict((int(r['lane']), int(r['send_pos'])) for r in plist.paths
                    if r.get('send_pos') != '' and str(r['lane']).isdigit())
    an = PT.SimAnalog(world, plist.gain, send_pos)
    an.image = [0x00] * 24 + [0x00]
    an.safe_image = [0x01] * 24 + [0x00]
    st = PT.Station(plist, unit,
                    PT.SimPatcher(glass, world, 0.0, lambda s: None), glass,
                    PT.Limits.load(plist.dir), log=lambda s: None,
                    live=LV.Live(None, enabled=False), analog=an,
                    blocks=['K3'], mj_input=mj_input)
    st.mj = sense
    return st, glass, an


def run_k3(sense, **kw):
    """The mini-jack block of the real patch loop, start to finish."""
    st, glass, an = build(sense, **kw)
    real = PT.MiniJackSense
    PT.MiniJackSense = lambda log=None, port=None: sense
    try:
        rows = st.run()
    finally:
        PT.MiniJackSense = real
    return st, glass, an, rows


def detect_rows(rows):
    return [r for r in rows if r['sub'] == 'jack-switch detect']


def test_it_is_bound_to_the_first_mini_jack_patch():
    st, _g, _an = build(FakeSense())
    pid, name = st.mj_detect_patch()
    mine = [(p, rs) for p, rs in st.L.patches
            if rs[0]['block'] == PT.MJ_BLOCK]
    check('there are two mini-jack patches in the list', len(mine) == 2,
          repr([p for p, _r in mine]))
    check('the detect is bound to the FIRST of them',
          (pid, name) == (mine[0][0], mine[0][1][0]['in']),
          repr((pid, name)))
    st2, _g, _an = build(FakeSense(), mj_input='MINI-JACK 2')
    check('--mj-detect-input moves it',
          st2.mj_detect_patch() == (mine[1][0], 'MINI-JACK 2'),
          repr(st2.mj_detect_patch()))
    st3, _g, _an = build(FakeSense(), mj_input='MINI-JACK 9')
    check('a name that is not in the list does not move it and does not crash',
          st3.mj_detect_patch() == (mine[0][0], mine[0][1][0]['in']),
          repr(st3.mj_detect_patch()))


def test_the_arm_is_before_the_instruction():
    sense = FakeSense(script=[(1, 2), (0, 40)])
    st, glass, _an, _rows = run_k3(sense)
    check('the listen was armed', sense.arms, repr(sense.arms))
    # The real prompt is `ManualPatcher.connect`'s own dialog, kind 'patch'.
    mj_posts = [p for p in glass.posts
                if p['kind'] == 'patch' and 'MINI-JACK 1' in p['title']]
    check('the mini-jack patch was prompted', mj_posts,
          repr([(p['kind'], p['title'][:40]) for p in glass.posts[:3]]))
    check('THE ARM CAME FIRST: nothing the operator does can land in a window '
          'nothing is watching',
          sense.arms[0] < mj_posts[0]['seq'],
          'arm at %r, prompt at %r' % (sense.arms, mj_posts[0]['seq']))
    check('the listen was drained while the wait loop was running',
          sense.drains > 1, repr(sense.drains))


def test_both_edges_pass():
    sense = FakeSense(script=[(1, 2), (0, 5)])
    st, glass, an, rows = run_k3(sense)
    d = detect_rows(rows)
    check('exactly one detect row', len(d) == 1, repr(d))
    check('both edges is a PASS', d and d[0]['verdict'] == PT.PASS, repr(d))
    check('the row is folded onto catalog row 93 with no special case',
          d and d[0]['rows'] == '93', repr(d and d[0]['rows']))
    check('it is named in panel terms, not by cell or address',
          d and d[0]['in'] == 'MINI-JACK 1' and 'Sys0' not in d[0]['why'],
          repr(d and (d[0]['in'], d[0]['why'])))
    check('the L/R rows of the same patch are still there: ONE insertion, TWO '
          'results',
          len([r for r in rows if r['rows'] == '95']) == 2,
          repr([(r['sub'], r['rows']) for r in rows]))
    check('no extra screen was spent on the removal (the next patch\'s own '
          'prompt is it)',
          not [p for p in glass.posts
               if p['lines'] and 'Take the plug out' in p['lines'][0]],
          repr([p['lines'] for p in glass.posts if p['lines']]))
    check('the listener was closed', sense.closed >= 1, repr(sense.closed))
    check('nothing was written to the sense cell', sense.writes == 0)


def test_one_edge_only_is_a_fail_and_names_it():
    sense = FakeSense(script=[(1, 2), (1, 5)])
    _st, _g, _an, rows = run_k3(sense)
    d = detect_rows(rows)
    check('the same value twice is a FAIL',
          d and d[0]['verdict'] == PT.FAIL, repr(d))
    check('... and it says the cell is transmitting but not following the jack',
          d and 'not following the jack' in d[0]['why'], repr(d and d[0]['why']))


def test_no_traffic_is_no_data_and_names_the_firmware():
    sense = FakeSense(script=[])
    _st, _g, _an, rows = run_k3(sense)
    d = detect_rows(rows)
    check('silence is NO DATA, never a FAIL',
          d and d[0]['verdict'] == PT.NODATA, repr(d))
    check('... and it says plainly that this is not a fault in the jack',
          d and 'not a fault in the jack' in d[0]['detail'], repr(d))
    check('... and names the panel firmware as the precondition',
          d and 'panel firmware' in d[0]['detail'], repr(d))
    check('... and says what to do about it',
          d and 'reflash' in d[0]['detail'], repr(d))


def test_a_bus_that_would_not_open():
    sense = FakeSense(ok=False)
    _st, _g, _an, rows = run_k3(sense)
    d = detect_rows(rows)
    check('a port that would not open is NO DATA with the reason',
          d and d[0]['verdict'] == PT.NODATA and d[0]['detail'], repr(d))
    check('the analog station still ran its own rows',
          len([r for r in rows if r['rows'] in ('95', '96')]) == 4,
          repr(len(rows)))


def test_the_verdict_function_on_its_own():
    """The four cases, without a station around them."""
    s = FakeSense(script=[(1, 1), (0, 2)])
    s.arm()
    s.drain()
    s.drain()
    v, why, _d = PT.mj_verdict(s, 'MINI-JACK 1', True)
    check('two different values: PASS', v == PT.PASS, repr((v, why)))
    s2 = FakeSense(script=[(1, 1)])
    s2.arm()
    s2.drain()
    v2, why2, _d = PT.mj_verdict(s2, 'MINI-JACK 1', False)
    check('one edge and nothing asked for a removal: NO DATA, not FAIL',
          v2 == PT.NODATA, repr((v2, why2)))
    check('... and it says nothing asked for the plug to come out',
          'come out' in why2, repr(why2))
    v3, _w, _d = PT.mj_verdict(s2, 'MINI-JACK 1', True)
    check('one edge when a removal WAS asked for: FAIL', v3 == PT.FAIL,
          repr(v3))
    s4 = FakeSense(script=[])
    s4.arm()
    v4, _w, d4 = PT.mj_verdict(s4, 'MINI-JACK 1', True)
    check('no traffic: NO DATA with the firmware reason', v4 == PT.NODATA,
          repr(v4))
    check('zero is a real value, not "no reply"',
          PT.mj_verdict(_zero_then_one(), 'MINI-JACK 1', True)[0] == PT.PASS)


def _zero_then_one():
    s = FakeSense(script=[(0, 1), (1, 2)])
    s.arm()
    s.drain()
    s.drain()
    return s


def test_mj_close_runs_once():
    sense = FakeSense(script=[(1, 2), (0, 5)])
    st, _g, _an, rows = run_k3(sense)
    before = len(st.rows_out)
    st.mj_close(ask=False)
    st.teardown()
    check('row 93 is not recorded twice however many ways out there are',
          len(st.rows_out) == before, repr(len(st.rows_out)))


class Row(object):
    def __init__(self, num, group='M2'):
        self.num, self.group, self.category = num, group, 'not-run'
        self.cls, self.automation, self.reason = 'panel control', '2', 'because'

    @property
    def panel(self):
        return 'a row'


def test_the_runner_does_not_let_the_panel_station_claim_row_93():
    sys.path.insert(0, TOOLS)
    import d24_runall as RA
    check('row 93 is listed as graded at another station',
          93 in RA.GRADED_ELSEWHERE, repr(sorted(RA.GRADED_ELSEWHERE)))
    step = RA.manual_step(Row(93))
    check('the panel station is told so in plain words',
          step['kind'] == RA.BLOCKED
          and 'mini-jack step of the analog station' in step['reason'],
          repr(step))
    check('... and the panel sense sweep does not claim it either',
          93 not in PL_sense_rows(), repr(PL_sense_rows()))

    # AND THE BUG THIS STOPS: `record_not_run` forcing NOT TESTED over a graded
    # verdict. A 'not-run' row normally MUST be forced (S119), because there
    # NOT TESTED is the catalog reclassifying the row -- but row 93 IS a check,
    # it just ran elsewhere.
    class FakeState(object):
        def __init__(self, have):
            self.have = dict(have)
            self.wrote = []

        def verdict(self, num):
            return self.have.get(num)

        def put(self, num, verdict, **kw):
            self.wrote.append((num, verdict))
            self.have[num] = verdict
    st = FakeState({93: PT.FAIL})
    RA.record_not_run([Row(93)], st, 1)
    check('a FAIL the analog station landed on row 93 is NOT overwritten with '
          'NOT TESTED', st.wrote == [], repr(st.wrote))
    st2 = FakeState({})
    RA.record_not_run([Row(93)], st2, 1)
    check('but a row nothing graded still gets its line, with the reason '
          '(never silently dropped)',
          st2.wrote == [(93, RA.NOTTESTED)], repr(st2.wrote))
    st3 = FakeState({95: PT.FAIL})
    RA.record_not_run([Row(95)], st3, 1)
    check('an ordinary not-run row is still forced, exactly as S119 needs',
          st3.wrote == [(95, RA.NOTTESTED)], repr(st3.wrote))


def PL_sense_rows():
    sys.path.insert(0, TOOLS)
    import d24_panel as PL
    return PL.sense_rows_for('right')


def main():
    for fn in (test_the_runner_does_not_let_the_panel_station_claim_row_93,
               test_it_is_bound_to_the_first_mini_jack_patch,
               test_the_arm_is_before_the_instruction,
               test_both_edges_pass,
               test_one_edge_only_is_a_fail_and_names_it,
               test_no_traffic_is_no_data_and_names_the_firmware,
               test_a_bus_that_would_not_open,
               test_the_verdict_function_on_its_own,
               test_mj_close_runs_once):
        print('-- %s' % fn.__name__)
        fn()
    print()
    if FAILS:
        print('%d check(s) FAILED: %s' % (len(FAILS), ', '.join(FAILS)))
        return 1
    print('all checks passed -- no unit, no bus, no serial port, no write')
    return 0


if __name__ == '__main__':
    sys.exit(main())
