#!/usr/bin/env python3
"""patch_glass_checks.py -- S155 items 1 and 2, and the THREE addenda that
followed, all one root cause: the strip's PEAK meter is a decaying LATCH
(6.5 dB/s, S153) and `detect` used to read it as if it were the lane's
present-tense state.

  1. ALREADY-CARRYING SOCKET (P1, AUX 1 -> MIC 1, hub ~18:50 / PW ~19:00).
     `hot0` compared the PEAK meter against the node RMS floor -- two
     instruments -- and an idle lane's own peak/RMS gap alone cleared
     `detect_rise_db` with nothing plugged in at all.
  2. WRONG-SOCKET FALSE ALARM. `where_is_it`'s sweep used a flat -90 dBFS
     cutoff on the peak meter, which MIC 15's own floor clears on its own.
  3. P6 (AUX 8 -> MIC 1, hub ~19:10): a "move the other end" patch's MIC
     input never physically moves -- the runner rewrites the ROUTE before
     the prompt -- so the peak meter is mid-decay from the OLD donor, not
     reading the new state. A swap faster than ~1.9 s (12 dB / 6.5 dB/s)
     re-latches the meter on the NEW tone before the removal edge's `lo`
     ever fell far enough, and the step could never pass, however correct.
  4. P56 (MIC 24, hub ~19:20): the THIRD face of the same thing -- an EMPTY
     socket read hot0 True because the peak meter was still decaying from
     that lane's OWN previous gain-63 noise step (lvl0 -63.7, floor0
     -101.7 node RMS).

THE FIX, all three addenda: tone rows are judged on the MEASUREMENT NODE
(RMS) throughout -- `lvl0`, `floor0`, and every poll -- never the strip's
peak meter, which no longer appears anywhere in `detect`'s own arrival or
hot0 path (only `_look_elsewhere`'s independent 1 s sweep still reads it,
for item 2). The removal edge itself survives, gated on
`self._same_connection` (set in `announce`/`find_loop`): true only when
NEITHER end of the connection changed since the last prompt -- the noise
swap's own shape, which never reaches this branch anyway (`_noise_met`
judges noise rows). "Move the other end" no longer qualifies: the route
write a moment ago already IS the removal.

No unit, no bus: this reuses S145's own harness (`build`, `run_detect`,
`Scripted`, a real `Live` behind a real `Station`) rather than rebuilding it,
so a later change to that harness is the one place either suite has to
follow.
"""
import importlib.util
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, '..', '..', '..', '..', 'tools', 'pi')
sys.path.insert(0, TOOLS)
os.environ.setdefault('MATRIX_ADDR_HOME',
                      os.path.abspath(os.path.join(HERE, '..', 's138b',
                                                   'fixtures')))
import d24_live as LV        # noqa: E402
import d24_patch as PT       # noqa: E402

S145_DIR = os.path.abspath(os.path.join(HERE, '..', 's145'))
_spec = importlib.util.spec_from_file_location(
    'patch_auto_advance_check',
    os.path.join(S145_DIR, 'patch_auto_advance_check.py'))
H = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(H)

FAILS = []


def check(name, cond, detail=''):
    print('%-4s %s%s' % ('ok' if cond else 'FAIL', name,
                         (': ' + detail) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


def watched_screens(fn):
    """Run `fn`, returning (result, every screen `Live` wrote while it ran,
    each stamped with the virtual `now()` it was written at)."""
    seen = []
    orig = LV.Live._flush

    def flush(self):
        orig(self)
        d = dict(self.d)
        d['_t'] = PT.now()
        seen.append(d)
    LV.Live._flush = flush
    try:
        out = fn()
    finally:
        LV.Live._flush = orig
    return out, seen


# ---------------------------------------------------------------------------
# 1. TONE ROWS NEVER READ THE PEAK METER ANY MORE -- the structural check
#    that covers all three addenda (P1, P6, P56) in one proof: whatever
#    story the peak meter's decay would tell, `detect`'s own lvl0/floor0/poll
#    path for a tone row cannot hear it, because it never calls `meter_peak`.
# ---------------------------------------------------------------------------
def test_hot0_and_arrival_never_touch_the_peak_meter():
    """P56 addendum, PW ~19:20: an EMPTY MIC 24 read hot0 True because the
    peak meter was still decaying from that SAME lane's own previous gain-63
    noise step (lvl0 -63.7, floor0 -101.7 node RMS) -- a THIRD face of P1 and
    P6's shared cause. `Scripted` overrides `meter_sweep` wholesale for this
    harness, so the only thing that could call `meter_peak` during a plain
    `detect()` is `watch`'s own peak branch -- which a tone row no longer
    reaches at all."""
    tmp = tempfile.mkdtemp(prefix='s155-p56-struct-')
    st, _g, live = H.build(tmp, blocks=['K1'])
    rows = H.tone_rows(st)
    calls = []
    orig_peak = st.u.meter_peak

    def traced(strip):
        calls.append(strip)
        return orig_peak(strip)
    st.u.meter_peak = traced

    def go():
        # an idle lane at the prompt (no lead, nothing driving it, just like
        # P56's MIC 24), the operator's own plug about a second later.
        return H.run_detect(st, live, rows, [-96.0] * 20 + [-12.0] * 40)
    (how, _a, dt, _sc), _seen = watched_screens(go)
    check('the step still arrives cleanly', how == 'rise', repr(how))
    check('detect never touched the peak meter for this lane',
          not calls, repr(calls))


def test_p56_noise_to_tone_transition_with_a_1s_plug():
    """The realistic P56 numbers (hub ~19:20): lvl0 -63.7, floor0 -101.7 on
    the OLD peak-vs-RMS comparison -- a 38 dB gap that cleared `rise` with
    NOTHING plugged in, purely from that lane's own gain-63 noise step still
    draining on the peak meter. On the node, with nothing plugged, the lane
    reads its own idle RMS floor; the operator's plug about a second later
    is what actually moves it."""
    tmp = tempfile.mkdtemp(prefix='s155-p56-')
    st, _g, live = H.build(tmp, blocks=['K1'])
    logs = []
    st.log = logs.append
    rows = H.tone_rows(st)
    idle_rms = -101.7

    def go():
        return H.run_detect(st, live, rows,
                            [idle_rms] * 20 + [-12.0] * 40, floor=idle_rms)
    (how, _a, dt, _sc), _seen = watched_screens(go)
    check('no false hot0 from a previous noise step\'s decay', how == 'rise',
          repr(how))
    check('... on the plug-in, not after 20 s of a removal that could never '
          'come (RMS polling costs a settle window a poll, so this is a few '
          'poll cycles, not the old peak meter\'s near-instant one)',
          dt < 2.0, '%.3f s' % dt)
    check('the log shows hot0 False, on the node RMS, not the peak meter',
          any('hot0 False' in s and 'node RMS' in s for s in logs[:2]),
          repr(logs[:2]))


# ---------------------------------------------------------------------------
# 1b. THE REMOVAL EDGE SURVIVES FOR ONE SHAPE ONLY: `_same_connection`
#     (S155 P6 addendum, PW ~19:10 -- "the route change IS the removal for
#     other-end patches"; the mechanism itself is exercised in S145's own
#     `test_move_the_other_end_needs_no_removal_edge` and
#     `test_a_literal_repeat_still_needs_the_removal_edge`). Here: the UX
#     line PW's original item 1 asked for, proved on the one case it can
#     still fire on.
# ---------------------------------------------------------------------------
def test_already_carrying_says_so_when_it_is_a_literal_repeat():
    tmp = tempfile.mkdtemp(prefix='s155-hot0-')
    st, _g, live = H.build(tmp, blocks=['K1'])
    logs = []
    st.log = logs.append
    rows = H.tone_rows(st)
    wanted = rows[0]['in']
    st._same_connection = True    # the one shape hot0 still applies to
    # already carrying at the prompt; the removal (the operator pulls it,
    # S128's gate) comes a beat later, then the real arrival.
    script = [-15.0] * 5 + [-96.0] * 5 + [-15.0] * 40

    def go():
        return H.run_detect(st, live, rows, script)
    (how, _a, dt, sc), seen = watched_screens(go)
    check('the glass says so the moment the prompt sees it already carrying',
          any(d.get('status') == LV.status_already_carrying(wanted)
              for d in seen),
          repr([d.get('status') for d in seen[:4]]))
    check('the log says so too',
          any('already carrying at the prompt' in s for s in logs),
          repr(logs[:4]))
    check('the removal+arrival rule itself is unchanged: this step still '
          'ends on the rise, after the removal', how == 'rise', repr(how))
    check('... and not before the removal was seen',
          any('the lead came out of' in s for s in logs), repr(logs))


def test_move_the_other_end_never_says_already_carrying():
    """The control the whole P6 fix is about: a "move the other end" patch
    (`_same_connection` False, `announce`'s own default) that is already
    carrying the RIGHT tone at the prompt is NOT hot0 -- it just arrives,
    with no removal line and no already-carrying line either."""
    tmp = tempfile.mkdtemp(prefix='s155-hot0-p6-')
    st, _g, live = H.build(tmp, blocks=['K1'])
    rows = H.tone_rows(st)
    wanted = rows[0]['in']
    st._same_connection = False

    def go():
        return H.run_detect(st, live, rows, [-7.6] * 4000)
    (how, _a, dt, _sc), seen = watched_screens(go)
    check('it arrives at once, not after a removal that will never come',
          how == 'rise', repr(how))
    check('... and never once says "already has signal" -- this shape is '
          'not hot0 any more',
          not any(d.get('status') == LV.status_already_carrying(wanted)
                  for d in seen),
          repr(sorted({d.get('status') for d in seen})[:6]))


def test_a_lane_that_was_never_hot_gets_the_plain_screen():
    """The other control: a lane that is QUIET at the prompt must get the
    ordinary WAITING words, never the already-carrying line."""
    tmp = tempfile.mkdtemp(prefix='s155-hot0-control-')
    st, _g, live = H.build(tmp, blocks=['K1'])
    rows = H.tone_rows(st)
    wanted = rows[0]['in']
    st._same_connection = True

    def go():
        return H.run_detect(st, live, rows, [-96.0] * 5 + [-15.0] * 40)
    (how, _a, _dt, _sc), seen = watched_screens(go)
    check('a lane quiet at the prompt still arrives normally', how == 'rise',
          repr(how))
    check('... and never once says "already has signal"',
          not any(d.get('status') == LV.status_already_carrying(wanted)
                  for d in seen),
          repr(sorted({d.get('status') for d in seen})[:6]))


# ---------------------------------------------------------------------------
# 2. WRONG-SOCKET FALSE ALARM: the margin is over THAT lane's own floor
# ---------------------------------------------------------------------------
NOISY_FLOOR_DBFS = -75.5     # MIC 15, S153: the noisiest floor on the unit


def _other_lane(lane):
    return 15 if lane != 15 else 16


def test_a_loud_floor_sitting_still_is_never_named():
    tmp = tempfile.mkdtemp(prefix='s155-noisyfloor-')
    st, _g, live = H.build(tmp, blocks=['K1'])
    rows = H.tone_rows(st)
    lane = int(rows[0]['lane'])
    noisy = _other_lane(lane)
    st.peak_floors[noisy] = NOISY_FLOOR_DBFS
    # sitting exactly AT its own floor -- nothing plugged, nothing moved. The
    # old flat -90 dBFS cutoff named this lane on sight; S155 needs it `rise`
    # dB above ITS OWN floor before it counts as carrying anything.
    at_floor = 10 ** (NOISY_FLOOR_DBFS / 20.0)

    def go():
        return H.run_detect(st, live, rows, [-96.0] * 400,
                            sweep={noisy: at_floor})
    (how, _a, _dt, _sc), seen = watched_screens(go)
    check('the asked-for lane times out honestly (nothing ever arrived)',
          how == 'timeout', repr(how))
    named = [d for d in seen
             if d.get('status') == LV.status_wrong_input('MIC %d' % noisy,
                                                         rows[0]['in'])]
    check('the noisy-floor lane is never named the whole run', not named,
          repr(sorted({d.get('status') for d in seen}))[:6])
    check('... the sweep really ran (this is the path the bug lived in)',
          'looking for a misplaced lead' in st.costs, repr(sorted(st.costs)))


def test_the_same_lane_genuinely_carrying_is_still_named():
    """The fix is a MARGIN, not a mute: the same noisy-floor lane, once it
    clears `rise` dB above its own floor, is still caught -- and caught by
    the proactive sweep, inside a couple of `WRONG_INPUT_POLL_S`, not only
    at the final timeout fallback."""
    tmp = tempfile.mkdtemp(prefix='s155-noisyfloor-hot-')
    st, _g, live = H.build(tmp, blocks=['K1'])
    rows = H.tone_rows(st)
    lane = int(rows[0]['lane'])
    noisy = _other_lane(lane)
    st.peak_floors[noisy] = NOISY_FLOOR_DBFS
    rise = st.lim['detect_rise_db']
    carrying = 10 ** ((NOISY_FLOOR_DBFS + rise + 6.0) / 20.0)
    wanted = rows[0]['in']

    def go():
        return H.run_detect(st, live, rows, [-96.0] * 400,
                            sweep={noisy: carrying})
    t0 = PT.now()
    (how, _a, dt, _sc), seen = watched_screens(go)
    t0 = seen[0]['_t'] if seen else t0    # the very first flush, i.e. WAITING
    named = [d for d in seen
             if d.get('status') == LV.status_wrong_input('MIC %d' % noisy,
                                                         wanted)]
    check('a genuinely carrying lane is still named', named,
          repr(sorted({d.get('status') for d in seen})[:6]))
    first_named_at = (min(d['_t'] for d in named) - t0) if named else None
    bound = 2 * PT.WRONG_INPUT_POLL_S * 2 + 1.0  # generous: two confirms,
                                                 # each up to a poll late
    check('... inside the proactive sweep\'s own bound, not the 20 s timeout '
          'or the 40 s hard stop',
          first_named_at is not None and first_named_at < bound,
          '%s (bound %.2f s, dt was %.2f s)'
          % (first_named_at, bound, dt))


def test_a_single_noisy_sweep_is_not_enough_it_has_to_hold():
    """The persistence half of the fix, isolated from the floor margin: a
    lane that clears the margin on exactly ONE sweep and is gone on the next
    must not be named -- the same stability the asked-for lane's own arrival
    needs (DETECT_STABLE_SAMPLES)."""
    tmp = tempfile.mkdtemp(prefix='s155-onesweep-')
    st, _g, live = H.build(tmp, blocks=['K1'])
    rows = H.tone_rows(st)
    lane = int(rows[0]['lane'])
    other = _other_lane(lane)
    st.peak_floors[other] = NOISY_FLOOR_DBFS
    rise = st.lim['detect_rise_db']
    loud = 10 ** ((NOISY_FLOOR_DBFS + rise + 6.0) / 20.0)
    calls = [0]

    def one_shot_sweep(strips):
        calls[0] += 1
        return {other: loud} if calls[0] == 1 else {}
    sc = H.Scripted(st, live, [-96.0] * 400)
    st.watch = sc.watch
    st.u.meter_sweep = one_shot_sweep
    prep = dict(lane=lane, freq=1000.0, level=-12.0, floor=-96.0,
               watch=-96.0, sweep0={})

    def go():
        return st.detect(rows, prep, None)
    (how, _a, _dt), _seen = watched_screens(go)
    check('one noisy sweep, gone on the next, is never named',
          how == 'timeout' and not st._wrong, repr((how, st._wrong)))
    check('... the sweep really ran more than once, so this proved something',
          calls[0] >= 2, repr(calls[0]))


# ---------------------------------------------------------------------------
# 3. the S145 suite it shares a harness with, still green
# ---------------------------------------------------------------------------
def test_s145_still_passes():
    import subprocess
    p = subprocess.run([sys.executable,
                        os.path.join(S145_DIR, 'patch_auto_advance_check.py')],
                       capture_output=True, text=True)
    check('patch_auto_advance_check.py (S145) still passes', p.returncode == 0,
          p.stdout[-800:] + p.stderr[-800:])


def main():
    for fn in (test_hot0_and_arrival_never_touch_the_peak_meter,
               test_p56_noise_to_tone_transition_with_a_1s_plug,
               test_already_carrying_says_so_when_it_is_a_literal_repeat,
               test_move_the_other_end_never_says_already_carrying,
               test_a_lane_that_was_never_hot_gets_the_plain_screen,
               test_a_loud_floor_sitting_still_is_never_named,
               test_the_same_lane_genuinely_carrying_is_still_named,
               test_a_single_noisy_sweep_is_not_enough_it_has_to_hold,
               test_s145_still_passes):
        print('-- %s' % fn.__name__)
        fn()
    print()
    if FAILS:
        print('%d check(s) FAILED: %s' % (len(FAILS), ', '.join(FAILS)))
        return 1
    print('all checks passed -- no unit, no bus, no serial port, no write, '
          'no rails')
    return 0


if __name__ == '__main__':
    sys.exit(main())
