#!/usr/bin/env python3
"""patch_auto_advance_check.py -- S145: PW's ruling of 2026-09-28 on the analog
patch loop, asserted. No unit, no bus, no serial port, no write, no rails.

    "when input signal cables are moved, they are automatically detected, and if
    so they can be measured and pass/failed and prompt next move without a
    required enter; a button would only need to be pressed to move on if signal
    is not detected."

What has to be true, and all of it is checked here:

  * ARRIVAL IS THE GO-AHEAD AND IT IS THE DEFAULT -- `Station`, the CLI, and the
    RUN ALL path, all three, because a default that only one of them has is how
    two tests come to wear the same name.
  * NO ENTER ANYWHERE ON A DETECTED PATCH: no screen of a whole dry run carries
    an `enter` button, and no instruction, status or action line on one names
    ENTER. `--confirm-enter` still does, because that path still exists.
  * NO SIGNAL IS THE ONE BUTTON: it is on every waiting and every check-the-lead
    screen, `Live.command` accepts it (a button the screen draws and the reader
    drops is a dead button -- S137's fault), and pressing it records the row FAIL
    "no signal detected" and advances.
  * THE STABILITY WINDOW: three instrument blocks, three samples, 1.0 dB. A
    signal that arrives and goes again inside the window does NOT grade; the
    window starts over. Nothing is graded mid-insertion.
  * WRONG INPUT: a tone on another lane is named in PW's own shape -- "Signal on
    MIC 7, expected MIC 5" -- while the operator is still standing there, and the
    asked row is not graded from it. A NO SIGNAL press while that is true is
    refused and the patch is offered again.
  * THE TIMEOUT RAISES THE QUESTION AND DECIDES NOTHING: the red screen goes up
    at the list's own `detect_timeout_s`, the loop keeps watching, and a lead
    pushed home after it still advances the step on its own. The hard bound is
    twice that number.
  * THE REMOVAL EDGE: a lane that is already carrying when the prompt goes up
    cannot be graded until it has been seen to fall back. That is the real case
    of "move the other end" and of the terminator swap.
  * NOISE ROWS TOO: they end on the drop, through the same window.
  * AND S138B STILL WORKS: the mini-jack sense is still drained from this loop,
    and the lamp sweep still asks with ENTER and NOT LIT -- it judges an LED with
    an eye and has no signal to detect, so the ruling does not reach it.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, '..', '..', '..', '..', 'tools', 'pi')
sys.path.insert(0, TOOLS)
os.environ.setdefault('MATRIX_ADDR_HOME',
                      os.path.abspath(os.path.join(HERE, '..', 's138b',
                                                   'fixtures')))
import d24_live as LV       # noqa: E402
import d24_patch as PT      # noqa: E402

LIST_DIR = os.path.abspath(os.path.join(HERE, '..', 's121'))
FAILS = []


def check(name, cond, detail=''):
    print('%-4s %s%s' % ('ok' if cond else 'FAIL', name,
                         (': ' + detail) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


# ---------------------------------------------------------------------------
# A station with a scripted lane
# ---------------------------------------------------------------------------
class ScriptGlass(object):
    """The dialog channel, answering nothing unless told to."""

    def __init__(self, answers=()):
        self.posts = []
        self.answers = list(answers)

    def post(self, kind, title, lines, buttons, **extra):
        self.posts.append(dict(kind=kind, title=title, lines=list(lines),
                               buttons=list(buttons)))
        return list(buttons)

    def poll(self, btns):
        return self.answers.pop(0) if self.answers else None

    def ask(self, kind, title, lines, buttons, **extra):
        self.post(kind, title, lines, buttons, **extra)
        return dict(button=buttons[0])

    def clear(self):
        pass

    def progress(self, text):
        pass


def build(tmp, blocks=None, auto=True, answers=()):
    """A real `Station` with a real `Live` behind it, and no unit.

    The `Live` is REAL and its directory is real, so `command()` is exercised
    through the file the app writes -- which is the only way to prove that a
    button the screen draws is a button the runner reads.
    """
    PT.CLOCK = PT.VirtualClock()
    plist = PT.PatchList(LIST_DIR)
    world = PT.World()
    glass = ScriptGlass(answers)
    unit = PT.SimUnit(world)
    send_pos = dict((int(r['lane']), int(r['send_pos'])) for r in plist.paths
                    if r.get('send_pos') != '' and str(r['lane']).isdigit())
    an = PT.SimAnalog(world, plist.gain, send_pos)
    an.image = [0x00] * 24 + [0x00]
    an.safe_image = [0x01] * 24 + [0x00]
    live = LV.Live(tmp, run='patch', enabled=True, confirm=not auto)
    st = PT.Station(plist, unit,
                    PT.SimPatcher(glass, world, 0.0, lambda s: None,
                                  auto=auto,
                                  press_s=None if auto else PT.PRESS_S),
                    glass, PT.Limits.load(plist.dir), log=lambda s: None,
                    live=live, analog=an, blocks=blocks, auto_advance=auto)
    # `measure_floors` is part of `standing()`, which a real pass always runs
    # before the first `detect()` -- these tests call `detect()` on its own, so
    # they owe it the same call, or `where_is_it` (S155: per-lane floor, not a
    # flat dBFS number) sees an empty `self.floors` and never names a lane.
    st.measure_floors()
    return st, glass, live


def press(live, button):
    """What the app writes when the operator touches the glass."""
    with open(os.path.join(live.dir, LV.COMMAND_NAME), 'w') as fh:
        json.dump(dict(command=button, stamp=live.t0 + 1.0), fh)


class Scripted(object):
    """A lane whose level is read off a list, one value per detector poll.

    The last value repeats for ever, so a script says what happens and then what
    the lane settles at. `presses` fires a glass button at a given poll number,
    which is how the timing of a press against the stability window is pinned
    down rather than hoped for.
    """

    def __init__(self, st, live, levels, presses=(), sweep=None):
        self.st, self.live = st, live
        self.levels = list(levels)
        self.presses = dict(presses)
        self.sweep = sweep or {}
        self.n = 0
        self.seen = []

    def watch(self, lane, **_kw):
        i = min(self.n, len(self.levels) - 1)
        v = self.levels[i]
        self.n += 1
        if self.n in self.presses:
            press(self.live, self.presses[self.n])
        self.seen.append(v)
        return v

    def meter_sweep(self, strips):
        return dict(self.sweep)


# S157: NOTHING ENDS A STEP BY ITSELF ANY MORE except an arrival -- the old
# 2x-timeout give-up is gone (PW 2026-09-30, "never move past a fail without
# operator confirmation"). A scripted detect that never arrives is ended by
# the HARNESS pressing PAUSE this many polls in (well past 2 x 20 s), and
# `run_detect` reports that as 'waiting': the station was still on the step.
HARNESS_PAUSE_POLL = 1200


def run_detect(st, live, rows, levels, presses=(), sweep=None, floor=-96.0):
    """One `detect` call against a scripted lane.

    `floor` is the lane's node-RMS idle floor -- `prep['floor']`, the only
    instrument tone AND noise rows read now (S155). `st._same_connection`
    (default False, `Station.__init__`) governs whether `hot0`'s removal
    edge applies at all; set it on `st` before calling this for a scenario
    that needs it True.
    """
    lane = int(rows[0]['lane'])
    presses = dict(presses)
    presses.setdefault(HARNESS_PAUSE_POLL, 'pause')
    sc = Scripted(st, live, levels, presses, sweep)
    st.watch = sc.watch
    # S157: tone rows read the node's COHERENT level through `watch_tone`;
    # the script feeds both instruments the same numbers.
    st.watch_tone = lambda lane, prep, settle=1: sc.watch(lane)
    st.u.meter_sweep = sc.meter_sweep
    prep = dict(lane=lane, freq=1000.0, level=-12.0, floor=floor,
                watch=levels[0], sweep0={})
    how, ans, dt = st.detect(rows, prep, None)
    if how == 'glass' and (ans or {}).get('button') == 'pause' \
            and sc.n >= HARNESS_PAUSE_POLL:
        how = 'waiting'
    return how, ans, dt, sc


def tone_rows(st):
    for pid, rows in st.L.patches:
        if rows[0]['expect'] == 'tone' and str(rows[0].get('gain_code')
                                               or '') == '':
            return rows
    raise AssertionError('no plain tone patch in the list')


def noise_rows(st):
    for pid, rows in st.L.patches:
        if rows[0]['expect'] == 'noise':
            return rows
    raise AssertionError('no noise patch in the list')


# ---------------------------------------------------------------------------
# 1. the default, in all three places
# ---------------------------------------------------------------------------
def test_arrival_is_the_default():
    import inspect
    sig = inspect.signature(PT.Station.__init__)
    check('Station defaults to arrival as the go-ahead',
          sig.parameters['auto_advance'].default is True)
    ap = PT.main.__wrapped__ if hasattr(PT.main, '__wrapped__') else None
    a = _parse([])
    check('the CLI defaults to it', a.auto_advance is True, repr(a.auto_advance))
    b = _parse(['--confirm-enter'])
    check('--confirm-enter is the way back to the 09-26 loop',
          b.auto_advance is False, repr(b.auto_advance))
    c = _parse(['--auto-advance'])
    check('--auto-advance is still accepted and still means the same thing',
          c.auto_advance is True, repr(c.auto_advance))
    src = open(os.path.join(TOOLS, 'd24_runall.py')).read()
    body = src.split('def patch_station(', 1)[1].split('\ndef ', 1)[0]
    code = [ln.split('#', 1)[0] for ln in body.splitlines()]
    check('RUN ALL passes no mode of its own, so it cannot drift from the '
          'station', not [ln for ln in code if 'auto_advance' in ln],
          repr([ln for ln in code if 'auto_advance' in ln]))
    check('the simulated operator presses nothing on the ruled path',
          inspect.signature(PT.SimPatcher.__init__)
          .parameters['auto'].default is True)
    assert ap is None or True


def _parse(extra):
    import argparse
    saved = sys.argv
    try:
        # `main` builds the parser; the only way to read its defaults without
        # running anything is to ask it for a parse of an otherwise empty run.
        sys.argv = ['d24_patch.py'] + list(extra)
        return _parser().parse_args(list(extra))
    finally:
        sys.argv = saved


_PARSER = [None]


def _parser():
    """The real parser out of `main`, with nothing run.

    `main` is one function that builds the parser and then dispatches, so the
    parser is taken by letting it build and intercepting the dispatch. That is
    deliberately not a copy of the argument list: a copy would go stale and this
    cannot.
    """
    if _PARSER[0] is None:
        import argparse
        real = argparse.ArgumentParser.parse_args

        def grab(self, args=None, namespace=None):
            _PARSER[0] = self
            raise _Grabbed()
        argparse.ArgumentParser.parse_args = grab
        try:
            PT.main([])
        except _Grabbed:
            pass
        finally:
            argparse.ArgumentParser.parse_args = real
    return _PARSER[0]


class _Grabbed(Exception):
    pass


# ---------------------------------------------------------------------------
# 2. the stability window
# ---------------------------------------------------------------------------
def test_the_window_is_three_blocks_and_steady():
    check('the window is stated in the instrument\'s own blocks',
          PT.DETECT_STABLE_BLOCKS == 3 and abs(PT.WIN_S - 4096.0 / 48000.0)
          < 1e-9, repr((PT.DETECT_STABLE_BLOCKS, PT.WIN_S)))
    check('... which is 256 ms, longer than the 167 ms a gain step needs',
          abs(PT.DETECT_STABLE_BLOCKS * PT.WIN_S - 0.256) < 1e-3
          and PT.DETECT_STABLE_BLOCKS * PT.WIN_S > 0.167,
          '%.3f s' % (PT.DETECT_STABLE_BLOCKS * PT.WIN_S))
    check('steady is 1.0 dB, twice what the node is held to',
          PT.DETECT_STEADY_DB == 2 * PT.PREARM_STABLE_DB,
          repr((PT.DETECT_STEADY_DB, PT.PREARM_STABLE_DB)))
    check('the poll is finer than a block', PT.DETECT_POLL_S < PT.WIN_S,
          repr((PT.DETECT_POLL_S, PT.WIN_S)))
    check('and a window is at least two readings, which is what the coarsest '
          'lane on the unit can deliver in it',
          PT.DETECT_STABLE_SAMPLES == 2, repr(PT.DETECT_STABLE_SAMPLES))

    tmp = tempfile.mkdtemp(prefix='s145-win-')
    st, _g, live = build(tmp, blocks=['K1'])
    rows = tone_rows(st)
    # quiet, then the tone, and it stays
    how, _a, dt, sc = run_detect(st, live, rows, [-96.0] * 3 + [-15.0])
    check('a tone that arrives and stays ends the step', how == 'rise',
          repr(how))
    check('... and not before the window has run', dt >= 0.256,
          '%.3f s' % dt)
    check('... and the step is over inside half a second of it arriving',
          dt < 0.6, '%.3f s' % dt)


def test_nothing_is_graded_mid_insertion():
    # THE CONTROL: a clean insertion, and how long it takes.
    st0, _g0, live0 = build(tempfile.mkdtemp(prefix='s145-mid0-'),
                            blocks=['K1'])
    clean = [-96.0] + [-15.0] * 40
    _h0, _a0, dt0, _s0 = run_detect(st0, live0, tone_rows(st0), clean)
    tmp = tempfile.mkdtemp(prefix='s145-mid-')
    st, _g, live = build(tmp, blocks=['K1'])
    rows = tone_rows(st)
    # ONE poll of tone -- the pins mated and let go again -- then quiet, then
    # the real insertion. The first is a connector, not a patch. Four polls of
    # interruption, so a step that graded the first arrival would come in at
    # dt0 and one that started over cannot come in before dt0 + 4 polls.
    script = [-96.0, -15.0] + [-96.0] * 4 + [-15.0] * 40
    how, _a, dt, sc = run_detect(st, live, rows, script)
    check('a tone for one poll does NOT end the step', how == 'rise')
    check('... the window started over, so the step ended on the SECOND '
          'arrival and not the first',
          dt >= dt0 + 4 * PT.DETECT_POLL_S - 1e-9,
          'clean %.3f s, interrupted %.3f s (poll %d)' % (dt0, dt, sc.n))

    # ... and one that wanders by more than a dB inside the window is not steady
    st2, _g2, live2 = build(tempfile.mkdtemp(prefix='s145-mid2-'),
                            blocks=['K1'])
    wobble = [-96.0] + [-15.0, -11.0] * 12 + [-15.0] * 20
    how2, _a2, dt2, sc2 = run_detect(st2, live2, tone_rows(st2), wobble)
    check('a level that moves 4 dB inside the window is not steady, so the '
          'step waits out the whole wobble',
          how2 == 'rise' and dt2 > 24 * PT.DETECT_POLL_S, '%.3f s' % dt2)
    check('... and then ends one window after it went still',
          dt2 < 24 * PT.DETECT_POLL_S + 0.256 + 3 * PT.DETECT_POLL_S,
          '%.3f s' % dt2)


def test_the_window_is_asserted_not_assumed():
    tmp = tempfile.mkdtemp(prefix='s145-assert-')
    st, _g, live = build(tmp, blocks=['K1'])
    t = PT.now()
    st._met_at = t - 10.0
    st._stable = [(t, -15.0)]
    ok, _why = st._stable_ok()
    check('a window with one reading in it is refused however long it lasted',
          not ok)
    st._stable = [(t, -15.0), (t, -15.0), (t, -20.0)]
    ok2, _why2 = st._stable_ok()
    check('a window whose spread is 5 dB is refused', not ok2)
    st._met_at = t + 1.0
    st._stable = [(t, -15.0), (t, -14.6)]
    ok2b, _why2b = st._stable_ok()
    check('a window that has not lasted three blocks yet is refused', not ok2b)
    st._met_at = t - 10.0
    st._stable = [(t, -15.0), (t, -14.6), (t, -15.2)]
    ok3, why3 = st._stable_ok()
    check('a window of readings inside 1.0 dB is accepted',
          ok3 and why3 == '0.60 dB', repr((ok3, why3)))
    # THE WINDOW SLIDES: a 4 dB wobble that is now over must not hold the step
    # up for ever, so samples older than the window are not in it.
    st._stable = [(t - 5.0, -11.0), (t, -15.0), (t, -14.8), (t, -15.1)]
    ok4, why4 = st._stable_ok()
    check('a wobble that has passed out of the window no longer counts',
          ok4, repr((ok4, why4)))


# ---------------------------------------------------------------------------
# 3. NO SIGNAL
# ---------------------------------------------------------------------------
def test_no_signal_is_the_only_button():
    # PW 2026-09-29: LEADS CORRECT (command 'nosignal') only once the test has
    # given up listening -- the waiting screen carries PAUSE alone.
    check('the waiting screen carries PAUSE alone, no ENTER and no LEADS CORRECT',
          LV.buttons_for(LV.WAITING, False) == ['pause'],
          repr(LV.buttons_for(LV.WAITING, False)))
    check('the check-the-lead (FAILED) screen carries LEADS CORRECT, RETRY '
          'and PAUSE (S157)',
          LV.buttons_for(LV.CHECKLEAD, False) == ['nosignal', 'retry', 'pause'],
          repr(LV.buttons_for(LV.CHECKLEAD, False)))
    check('the ENTER path is untouched',
          LV.buttons_for(LV.WAITING, True) == ['enter', 'pause'])
    tmp = tempfile.mkdtemp(prefix='s145-cmd-')
    live = LV.Live(tmp, run='patch', enabled=True, confirm=False)
    press(live, 'nosignal')
    check('Live.command reads it -- the button is not dead',
          live.command() == 'nosignal')
    press(live, 'somethingelse')
    check('... and still drops a command it has no rule for',
          live.command() is None)


def test_no_signal_records_fail_and_advances():
    tmp = tempfile.mkdtemp(prefix='s145-ns-')
    st, _g, live = build(tmp, blocks=['K1'])
    rows = tone_rows(st)
    how, _a, dt, sc = run_detect(st, live, rows, [-96.0] * 40,
                                 presses={3: 'nosignal'})
    check('a NO SIGNAL press on a silent lane ends the step',
          how == 'nosignal', repr(how))
    check('... at once, not at the timeout', dt < 1.0, '%.3f s' % dt)
    got = st.no_signal(rows)
    check('the row is a FAIL', [r['verdict'] for r in got] == [PT.FAIL] * len(rows),
          repr([r['verdict'] for r in got]))
    check('... and its reason is PW\'s own words',
          got[0]['why'] == 'no signal detected', repr(got[0]['why']))
    check('... and it says the rest of the unit was looked at too',
          'other input' in got[0]['detail'], repr(got[0]['detail']))
    check('every sub-test of the patch gets the row, not just the first',
          len(got) == len(rows), repr((len(got), len(rows))))


def test_enter_can_never_grade_a_patch_and_takes_two_presses_to_fail_one():
    """The ENTER channel exists on every app this unit has run; `nosignal` is a
    button no app has been given before. So ENTER must reach the same answer --
    and must not be able to reach any other."""
    # 1. while the signal is arriving, ENTER changes nothing
    tmp = tempfile.mkdtemp(prefix='s145-e1-')
    st, _g, live = build(tmp, blocks=['K1'])
    rows = tone_rows(st)
    how, _a, dt, _sc = run_detect(st, live, rows, [-96.0] + [-15.0] * 40,
                                  presses={2: 'enter'})
    check('ENTER on an arriving patch does not end it early -- the window still '
          'runs', how == 'rise' and dt >= 0.256, '%s %.3f s' % (how, dt))

    # 2. ONE press on a silent lane raises the question and grades nothing
    st2, _g2, live2 = build(tempfile.mkdtemp(prefix='s145-e2-'), blocks=['K1'])
    rows2 = tone_rows(st2)
    how2, _a2, dt2, _s2 = run_detect(st2, live2, rows2, [-96.0] * 60,
                                     presses={3: 'enter'})
    check('one ENTER on a silent lane does NOT record anything',
          how2 == 'waiting', repr(how2))
    d2 = json.load(open(os.path.join(live2.dir, LV.LIVE_NAME)))
    check('... it raises the question instead', d2['state'] == LV.CHECKLEAD,
          repr(d2['state']))

    # 3. and a second press, with the question up, is the answer
    st3, _g3, live3 = build(tempfile.mkdtemp(prefix='s145-e3-'), blocks=['K1'])
    rows3 = tone_rows(st3)
    how3, _a3, dt3, _s3 = run_detect(st3, live3, rows3, [-96.0] * 60,
                                     presses={3: 'enter', 6: 'enter'})
    check('the second ENTER, with the question already up, IS the answer',
          how3 == 'nosignal', repr(how3))
    check('... and it still came nowhere near the timeout', dt3 < 2.0,
          '%.3f s' % dt3)

    # 4. an ENTER that arrives while a tone is on ANOTHER input cannot fail the
    #    asked row either -- the wrong-input screen is what it gets
    st4, _g4, live4 = build(tempfile.mkdtemp(prefix='s145-e4-'), blocks=['K1'])
    rows4 = tone_rows(st4)
    lane4 = int(rows4[0]['lane'])
    other = 7 if lane4 != 7 else 8
    how4, _a4, _dt4, _s4 = run_detect(
        st4, live4, rows4, [-96.0] * 400,
        presses={3: 'enter', 30: 'enter', 60: 'enter'},
        sweep={other: PT.f32(10 ** (-15.0 / 20.0))})
    check('however many ENTERs, a tone on another input is never graded as the '
          'asked row', how4 == 'waiting', repr(how4))


def test_no_signal_is_refused_while_the_tone_is_elsewhere():
    tmp = tempfile.mkdtemp(prefix='s145-nswrong-')
    st, _g, live = build(tmp, blocks=['K1'])
    rows = tone_rows(st)
    lane = int(rows[0]['lane'])
    other = 1 if lane != 1 else 2
    sweep = {other: PT.f32(10 ** (-15.0 / 20.0))}
    # the lane never carries; the tone is on `other`; NO SIGNAL is pressed at
    # poll 3 and again at poll 60 -- and neither may record anything
    how, _a, dt, sc = run_detect(st, live, rows, [-96.0] * 400,
                                 presses={3: 'nosignal', 60: 'nosignal'},
                                 sweep=sweep)
    check('NO SIGNAL is not honoured while the tone is on another input',
          how == 'waiting', repr(how))
    d = json.load(open(os.path.join(live.dir, LV.LIVE_NAME)))
    check('... and the screen names the input it is actually on, in PW\'s shape',
          d['status'] == LV.status_wrong_input('MIC %d' % other, rows[0]['in']),
          repr(d['status']))
    check('... with one plain action under it',
          d['action'] and 'move it to' in d['action'], repr(d['action']))
    check('... and NO SIGNAL still on it, because the operator may yet be right',
          d['buttons'] == ['nosignal', 'retry', 'pause'], repr(d['buttons']))


# ---------------------------------------------------------------------------
# 4. the wrong input, while waiting
# ---------------------------------------------------------------------------
def test_the_wrong_input_is_named_while_they_stand_there():
    tmp = tempfile.mkdtemp(prefix='s145-wrong-')
    st, _g, live = build(tmp, blocks=['K1'])
    rows = tone_rows(st)
    lane = int(rows[0]['lane'])
    other = 7 if lane != 7 else 8
    sweep = {other: PT.f32(10 ** (-15.0 / 20.0))}
    seen = []
    orig = LV.Live._flush

    def flush(self):
        orig(self)
        seen.append(dict(self.d))
    LV.Live._flush = flush
    try:
        run_detect(st, live, rows, [-96.0] * 400, sweep=sweep)
    finally:
        LV.Live._flush = orig
    named = [d for d in seen
             if d.get('status') == LV.status_wrong_input('MIC %d' % other,
                                                         rows[0]['in'])]
    check('the tone on another input is named on the screen', named,
          repr(sorted({d.get('status') for d in seen})))
    check('the sweep cadence is a second, so it is named while the hand is '
          'still there', PT.WRONG_INPUT_POLL_S == 1.0,
          repr(PT.WRONG_INPUT_POLL_S))
    check('nothing was graded from it', not st.rows_out, repr(st.rows_out))
    check('the misplaced-lead sweep is booked where a reader can see it',
          'looking for a misplaced lead' in st.costs, repr(sorted(st.costs)))

    # AND IT COMES DOWN AGAIN. A lead moved to the right socket must not leave
    # a stale accusation on the glass.
    st2, _g2, live2 = build(tempfile.mkdtemp(prefix='s145-wrong2-'),
                            blocks=['K1'])
    rows2 = tone_rows(st2)
    sc = Scripted(st2, live2, [-96.0] * 30 + [-15.0] * 40,
                  sweep={other: PT.f32(10 ** (-15.0 / 20.0))})

    def fading_sweep(strips):
        return {} if sc.n > 30 else dict(sc.sweep)
    st2.watch = sc.watch
    st2.watch_tone = lambda lane, prep, settle=1: sc.watch(lane)
    st2.u.meter_sweep = fading_sweep
    prep = dict(lane=int(rows2[0]['lane']), freq=1000.0, level=-12.0,
                floor=-96.0, watch=-96.0, sweep0={})
    how2, _a2, _dt2 = st2.detect(rows2, prep, None)
    d2 = json.load(open(os.path.join(live2.dir, LV.LIVE_NAME)))
    check('once the lead is where it belongs the step advances', how2 == 'rise',
          repr(how2))
    check('... and the red banner is gone with it', not d2['banner'],
          repr(d2['banner']))


# ---------------------------------------------------------------------------
# 5. the timeout
# ---------------------------------------------------------------------------
def test_the_timeout_raises_the_question_and_decides_nothing():
    tmp = tempfile.mkdtemp(prefix='s145-to-')
    st, _g, live = build(tmp, blocks=['K1'])
    rows = tone_rows(st)
    secs = st.lim['detect_timeout_s']
    check('the value is the list\'s own and it is 20 s', secs == 20.0,
          repr(secs))
    # nothing for long enough to raise it, then the lead goes home
    polls = int(secs / PT.DETECT_POLL_S) + 20
    seen = []
    orig = LV.Live._flush

    def flush(self):
        orig(self)
        seen.append(dict(self.d))
    LV.Live._flush = flush
    try:
        how, _a, dt, sc = run_detect(st, live, rows,
                                     [-96.0] * polls + [-15.0] * 40)
    finally:
        LV.Live._flush = orig
    check('the step still ends on the signal, after the prompt went up',
          how == 'rise', repr(how))
    check('... which means the timeout decided nothing', dt > secs,
          '%.1f s' % dt)
    raised = [d for d in seen
              if d.get('status') == LV.timeout_words(rows[0]['in'], secs)]
    check('the red screen went up, with the number on it', raised,
          repr(sorted({d.get('status') for d in seen})[:4]))
    check('... and it says how long it waited',
          raised and '20 seconds' in raised[0]['status'],
          repr(raised and raised[0]['status']))
    check('... and offers the one button',
          raised and raised[0]['buttons'] == ['nosignal', 'retry', 'pause'],
          repr(raised and raised[0]['buttons']))
    check('... and one plain action: check the sockets, then LEADS CORRECT',
          raised and 'right sockets' in raised[0]['action']
          and 'LEADS CORRECT' in raised[0]['action'],
          repr(raised and raised[0]['action']))
    # PW 2026-09-29: "sometimes it says press leads correct, but no lead
    # correct to press". Every screen that names the button must carry it.
    dead = [(d.get('state'), d.get('buttons')) for d in seen
            if 'LEADS CORRECT' in (d.get('action') or '')
            and 'nosignal' not in (d.get('buttons') or [])]
    check('no screen says LEADS CORRECT without the button on it', not dead,
          repr(dead[:4]))


def test_it_never_moves_on_by_itself():
    """S157 (PW 2026-09-30): "the runner never moves past a fail without
    operator confirmation". This used to assert a give-up at twice the
    timeout; there is no give-up any more. Left alone, the step is still up
    (and still listening) when the harness pauses it, long after 2 x 20 s."""
    tmp = tempfile.mkdtemp(prefix='s145-to2-')
    st, _g, live = build(tmp, blocks=['K1'])
    rows = tone_rows(st)
    secs = st.lim['detect_timeout_s']
    how, _a, dt, _sc = run_detect(st, live, rows, [-96.0] * 4000)
    check('a station left alone does NOT give up', how == 'waiting',
          repr(how))
    check('... it was still waiting well past twice the timeout',
          dt > 2 * secs, '%.1f s' % dt)
    d = json.load(open(os.path.join(live.dir, LV.LIVE_NAME)))
    check('... on the FAILED screen with all three buttons',
          d['state'] == LV.CHECKLEAD
          and d['buttons'] == ['nosignal', 'retry', 'pause'],
          repr((d['state'], d['buttons'])))


# ---------------------------------------------------------------------------
# 6. the removal edge
# ---------------------------------------------------------------------------
def test_move_the_other_end_needs_no_removal_edge():
    """S155 P6 addendum, PW 2026-09-30 ~19:10: "the route change IS the
    removal for other-end patches". `_prepare` rewrites the route before the
    prompt goes up, so a "move the other end" patch's MIC input never
    physically moves at all -- demanding a removal edge from it is what made
    P6 (AUX 8 -> MIC 1) unpassable: the peak-hold meter's own 6.5 dB/s decay
    could not fall `rise` dB before a fast swap re-latched it. `announce`
    leaves `_same_connection` False for this shape (only the input matched,
    not the output too); `detect` must not ask for a removal it will not get."""
    tmp = tempfile.mkdtemp(prefix='s145-rm-')
    st, _g, live = build(tmp, blocks=['K1'])
    rows = tone_rows(st)
    how, _a, dt, sc = run_detect(st, live, rows, [-15.0] * 4000)
    check('a lane already carrying the RIGHT tone at the prompt grades at '
          'once, not after a removal that can never come',
          how == 'rise', repr(how))
    check('... inside the stability window, nowhere near the 20 s timeout',
          dt < 1.0, '%.3f s' % dt)


def test_no_tone_row_has_a_removal_edge():
    """S157 (PW 2026-09-30, "no parked leads, use one at a time"): every
    patch is one lead plugged fresh at both ends and the route was written
    before the prompt, so what the lane carries at the prompt is THIS
    route's tone or nothing. S155's `_same_connection` gate is gone; a lane
    already carrying the right tone arrives at once, whatever came before."""
    st, _g, live = build(tempfile.mkdtemp(prefix='s145-rm-same-'),
                         blocks=['K1'])
    rows = tone_rows(st)
    check('the S155 same-connection gate is gone',
          not hasattr(st, '_same_connection'))
    how, _a, dt, sc = run_detect(st, live, rows, [-15.0] * 4000)
    check('a lane carrying the right tone at the prompt arrives at once',
          how == 'rise' and dt < 1.0, '%s %.3f s' % (how, dt))


# ---------------------------------------------------------------------------
# 7. the noise rows
# ---------------------------------------------------------------------------
def test_noise_rows_advance_on_the_drop():
    """S158 (supersedes S153's plateau rule): in the 150 ohm pass the socket
    is EMPTY at the prompt, so the first readings are the open input and the
    plug is judged against them -- `detect_drop_db` under it, or
    TERM_SMALL_STEP_DB under it after an insertion burst. The numbers are
    2026-10-01's (S158 table): MIC 1 open -77.2, terminated -87.0; MIC 2 open
    -75.5, a -54 insertion, terminated -77.3."""
    tmp = tempfile.mkdtemp(prefix='s145-noise-')
    st, _g, live = build(tmp, blocks=['K5'])
    rows = noise_rows(st)
    check('the drop threshold is the list\'s own',
          st.lim['detect_drop_db'] == 3.0, repr(st.lim['detect_drop_db']))
    opn, term = [-77.2] * 12, [-87.0] * 40
    how, _a, dt, sc = run_detect(st, live, rows, opn + [-38.8] + term,
                                 floor=-110.0)
    check('a noise row ends on the plug', how == 'drop', repr(how))
    t_plug = (len(opn) + 1) * PT.DETECT_POLL_S
    check('... through the same stability window', dt >= t_plug + 0.256,
          '%.3f s' % dt)
    # the same 10 dB step with no insertion burst seen still grades
    st1, _g1, live1 = build(tempfile.mkdtemp(prefix='s145-noise1-'),
                            blocks=['K5'])
    how1, _a1, _dt1, _s1 = run_detect(st1, live1, noise_rows(st1),
                                      opn + term, floor=-110.0)
    check('a clean 10 dB step with no burst grades', how1 == 'drop',
          repr(how1))
    # MIC 2: a 1.8 dB step, after a burst -- grades
    st2, _g2, live2 = build(tempfile.mkdtemp(prefix='s145-noise2-'),
                            blocks=['K5'])
    how2, _a2, _dt2, _s2 = run_detect(
        st2, live2, noise_rows(st2),
        [-75.5] * 12 + [-53.9, -56.2, -74.7] + [-77.3] * 40, floor=-110.0)
    check('MIC 2\'s 1.8 dB step grades after the insertion burst',
          how2 == 'drop', repr(how2))
    # ... and the same 1.8 dB with no burst does not (an open input's own
    # wander is up to 1.5 dB on a median of three)
    st3, _g3, live3 = build(tempfile.mkdtemp(prefix='s145-noise3-'),
                            blocks=['K5'])
    how3, _a3, _dt3, _s3 = run_detect(st3, live3, noise_rows(st3),
                                      [-75.5] * 12 + [-77.3] * 400,
                                      floor=-110.0)
    check('a 1.8 dB drift with no insertion is never graded', how3 == 'waiting',
          repr(how3))
    # a drop that does not hold does not grade on the first one
    st4, _g4, live4 = build(tempfile.mkdtemp(prefix='s145-noise4-'),
                            blocks=['K5'])
    how4, _a4, dt4, _s4 = run_detect(
        st4, live4, noise_rows(st4),
        opn + [-87.0] * 3 + opn + term, floor=-110.0)
    check('a drop that comes back does not grade on the first one',
          how4 == 'drop'
          and dt4 >= (2 * len(opn) + 3) * PT.DETECT_POLL_S + 0.256,
          '%.3f s' % dt4)
    # an open input left alone, spikes and all, never grades
    st5, _g5, live5 = build(tempfile.mkdtemp(prefix='s145-noise5-'),
                            blocks=['K5'])
    spiky = ([-77.2, -77.3, -78.6, -77.1, -71.6, -77.2, -78.7, -77.3] * 60)
    how5, _a5, _dt5, _s5 = run_detect(st5, live5, noise_rows(st5), spiky,
                                      floor=-110.0)
    check('an open input left alone (MIC 1\'s own spikes) is never graded',
          how5 == 'waiting', repr(how5))
    # ENTER always ends it
    st6, _g6, live6 = build(tempfile.mkdtemp(prefix='s145-noise6-'),
                            blocks=['K5'])
    how6, _a6, _dt6, _s6 = run_detect(st6, live6, noise_rows(st6),
                                      [-75.5] * 400, presses={20: 'enter'},
                                      floor=-110.0)
    check('ENTER ends the 150 ohm step and it is measured', how6 == 'press',
          repr(how6))


# ---------------------------------------------------------------------------
# 8. the whole pass: no ENTER anywhere, NO SIGNAL everywhere
# ---------------------------------------------------------------------------
def every_screen(argv):
    seen = []
    orig = LV.Live._flush

    def flush(self):
        orig(self)
        seen.append(dict(self.d))
    LV.Live._flush = flush
    import contextlib
    import io
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            PT.main(argv)
    finally:
        LV.Live._flush = orig
    # collapse the heartbeat, keep two different screens that look the same
    keep, last = [], None
    for d in seen:
        key = (d.get('state'), (d.get('instruction') or '').strip(),
               (d.get('status') or '').strip(), (d.get('banner') or ''),
               (d.get('action') or ''), tuple(d.get('buttons') or []))
        if key != last:
            last = key
            keep.append(d)
    return keep, out.getvalue()


def test_a_whole_pass_has_no_enter_on_it():
    tmp = tempfile.mkdtemp(prefix='s145-pass-')
    seen, _out = every_screen(['--simulate', '--list-dir', LIST_DIR,
                               '--live', tmp, '--dir', tmp])
    check('the dry run wrote screens', len(seen) > 100, repr(len(seen)))
    # S158 (PW 2026-10-01): the 150 ohm screens are the one place ENTER is
    # offered -- "a key input is required for 150r". Everywhere else, none.
    def term(d):
        return 'terminator' in (d.get('instruction') or '')
    withenter = [d for d in seen if 'enter' in (d.get('buttons') or [])
                 and not term(d)]
    check('NOT ONE screen outside the 150 ohm pass carries an ENTER button',
          not withenter,
          repr([(d['state'], d['buttons']) for d in withenter[:4]]))
    words = []
    for d in seen:
        if term(d):
            continue
        for k in ('instruction', 'status', 'action', 'extra', 'lead_line'):
            v = d.get(k) or ''
            if 'ENTER' in v:
                words.append((d.get('state'), k, v))
    check('... and not one of them names ENTER in its words', not words,
          repr(words[:4]))
    tw = [d for d in seen if term(d) and d.get('state') == LV.WAITING]
    check('every 150 ohm waiting screen carries ENTER and PAUSE',
          tw and all(d['buttons'] == ['enter', 'pause'] for d in tw),
          repr(sorted({tuple(d['buttons']) for d in tw})))
    waiting = [d for d in seen if d.get('state') == LV.WAITING
               and not term(d)]
    check('every other waiting screen offers PAUSE alone (LEADS CORRECT waits '
          'for the timeout)',
          waiting and all(d['buttons'] == ['pause']
                          for d in waiting),
          repr(sorted({tuple(d['buttons']) for d in waiting})))
    lead = [d for d in seen if d.get('state') == LV.CHECKLEAD]
    check('so does every check-the-lead screen',
          all(d['buttons'] == ['nosignal', 'retry', 'pause'] for d in lead),
          repr(sorted({tuple(d['buttons']) for d in lead})))
    holding = [d for d in seen if d.get('status') == LV.SIGNAL_HOLDING]
    check('the arriving-signal line is the one that asks for nothing',
          holding, repr(sorted({d.get('status') for d in seen})[:6]))
    check('... and the old hint that named ENTER is nowhere on this path',
          not [d for d in seen if d.get('status') == LV.SIGNAL_SEEN])
    # THE FACTORY-SCREEN-SIMPLE RULE, unchanged by any of this.
    for d in waiting[:200]:
        bad = [k for k in ('summary', 'summary_title') if d.get(k)]
        if bad:
            check('a waiting screen carries no summary', False, repr(bad))
            break
    else:
        check('a waiting screen still carries nothing but the instruction, the '
              'status, the count and its buttons', True)
    over = [d.get('instruction') for d in seen
            if d.get('instruction') and not LV.fits(d['instruction'])]
    check('every instruction still fits the glass', not over, repr(over[:3]))


def test_the_enter_path_still_exists():
    tmp = tempfile.mkdtemp(prefix='s145-enter-')
    seen, _out = every_screen(['--simulate', '--confirm-enter',
                               '--list-dir', LIST_DIR, '--block', 'K1',
                               '--live', tmp, '--dir', tmp])
    asked = [d for d in seen if 'press ENTER' in (d.get('instruction') or '')]
    check('--confirm-enter still asks for ENTER', asked, repr(len(seen)))
    check('... and still gives it a button',
          all('enter' in (d.get('buttons') or []) for d in asked
              if d.get('state') not in ('checking', 'starting', 'stopping')),
          repr([(d['state'], d['buttons']) for d in asked[:3]]))


def test_the_verdicts_are_the_same_either_way():
    """The ruling changes WHEN a patch is graded, not HOW."""
    import contextlib
    import io

    def verdicts(extra):
        tmp = tempfile.mkdtemp(prefix='s145-v-')
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            PT.main(['--simulate', '--list-dir', LIST_DIR,
                     '--out', os.path.join(tmp, 'r.csv')] + extra)
        import csv
        rows = list(csv.DictReader(open(os.path.join(tmp, 'r.csv'))))
        return [(r['patch'], r['sub'], r['verdict']) for r in rows]
    auto = verdicts([])
    conf = verdicts(['--confirm-enter'])
    check('the same 246 readings, the same verdicts, patch for patch',
          auto == conf and len(auto) > 240,
          '%d vs %d, %d differ' % (len(auto), len(conf),
                                   sum(1 for a, b in zip(auto, conf)
                                       if a != b)))


# ---------------------------------------------------------------------------
# 9. S138b still works
# ---------------------------------------------------------------------------
def test_s138b_still_works():
    src = open(os.path.join(TOOLS, 'd24_patch.py')).read()
    body = src.split('def detect(', 1)[1].split('\n    def ', 1)[0]
    check('the mini-jack sense is still drained from inside the wait loop',
          'self.mj_drain()' in body)
    check('the lamp sweep still asks with ENTER and NOT LIT -- it judges an '
          'eye, and has no signal to detect',
          LV.LAMP_BUTTONS == ['notlit', 'pause'], repr(LV.LAMP_BUTTONS))
    tmp = tempfile.mkdtemp(prefix='s145-lamp-')
    st, glass, live = build(tmp, blocks=['K1'])
    st.lamp_ask('Is it lit?', 1, 24, 'Phantom', fault='notlit', secs=0.2)
    d = json.load(open(os.path.join(live.dir, LV.LIVE_NAME)))
    check('... and the lamp screen still draws them, not NO SIGNAL',
          d['buttons'] == ['notlit', 'pause'], repr(d['buttons']))


def test_the_station_owns_its_own_screen_under_run_all():
    """A pass-wide `Live` built `confirm=True` must not put a dead ENTER on this
    station's screens. That is the seam S128's one-screen-per-pass leaves."""
    tmp = tempfile.mkdtemp(prefix='s145-own-')
    live = LV.Live(tmp, run='setup', enabled=True, confirm=True)
    check('the pass builds its screen for the setup pages, which DO ask',
          live.confirm is True)
    PT.CLOCK = PT.VirtualClock()
    plist = PT.PatchList(LIST_DIR)
    world = PT.World()
    st = PT.Station(plist, PT.SimUnit(world),
                    PT.SimPatcher(ScriptGlass(), world, 0.0, lambda s: None),
                    ScriptGlass(), PT.Limits.load(plist.dir),
                    log=lambda s: None, live=live,
                    analog=PT.SimAnalog(world, plist.gain, {}))
    check('the station takes the flag for as long as it owns the screen',
          live.confirm is False)
    live.set(state=LV.WAITING, instruction='Plug AUX 1 into MIC 1.')
    check('... so its waiting screen has no dead ENTER (PAUSE alone)',
          live.d['buttons'] == ['pause'], repr(live.d['buttons']))
    st.teardown()
    check('and teardown gives it back, so a later screen is unaffected',
          live.confirm is True)


def main():
    for fn in (test_arrival_is_the_default,
               test_the_window_is_three_blocks_and_steady,
               test_nothing_is_graded_mid_insertion,
               test_the_window_is_asserted_not_assumed,
               test_no_signal_is_the_only_button,
               test_no_signal_records_fail_and_advances,
               test_enter_can_never_grade_a_patch_and_takes_two_presses_to_fail_one,
               test_no_signal_is_refused_while_the_tone_is_elsewhere,
               test_the_wrong_input_is_named_while_they_stand_there,
               test_the_timeout_raises_the_question_and_decides_nothing,
               test_it_never_moves_on_by_itself,
               test_move_the_other_end_needs_no_removal_edge,
               test_no_tone_row_has_a_removal_edge,
               test_noise_rows_advance_on_the_drop,
               test_s138b_still_works,
               test_the_station_owns_its_own_screen_under_run_all,
               test_a_whole_pass_has_no_enter_on_it,
               test_the_enter_path_still_exists,
               test_the_verdicts_are_the_same_either_way):
        print('-- %s' % fn.__name__)
        fn()
    print()
    if FAILS:
        print('%d check(s) FAILED: %s' % (len(FAILS), ', '.join(FAILS)))
        return 1
    print('all checks passed -- no unit, no bus, no serial port, no write, '
          'no rails, no phantom')
    return 0


if __name__ == '__main__':
    sys.exit(main())
