#!/usr/bin/env python3
"""patch_glass_checks.py -- S155 items 1 and 2, PW's bench findings on
factory-test-v4 (2026-09-30, hub dispatch 17:36Z):

  1. ALREADY-CARRYING SOCKET, SAY SO. `detect`'s removal-edge gate (S128's
     ruling, unchanged) is right to refuse an arrival on a lane that was
     already hot at the prompt -- but it used to do that SILENTLY, and PW hit
     it on P1 (AUX 1 -> MIC 1, the lead already in): the glass just said
     WAITING for 20 s and the run reparked to MIC 3 while the tone sat on
     MIC 1 the whole time.
  2. WRONG-SOCKET FALSE ALARM. `where_is_it`'s sweep used a flat -90 dBFS
     cutoff, which MIC 15's own floor (-75.5 dBFS, the noisiest on the unit,
     S153) clears on its own with nothing plugged in at all -- most likely
     what told P1 "the tone is on MIC 15" while it sat on MIC 1.

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
# 1. ALREADY-CARRYING SOCKET, SAY SO
# ---------------------------------------------------------------------------
def test_already_carrying_says_so_at_once():
    tmp = tempfile.mkdtemp(prefix='s155-hot0-')
    st, _g, live = H.build(tmp, blocks=['K1'])
    logs = []
    st.log = logs.append
    rows = H.tone_rows(st)
    wanted = rows[0]['in']
    # PW's P1: AUX 1 already in MIC 1 when the prompt goes up. The removal
    # (the operator pulls it, S128's gate) comes a beat later, then the real
    # arrival.
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


def test_a_lane_that_was_never_hot_gets_the_plain_screen():
    """The control: a lane that is QUIET at the prompt must get the ordinary
    WAITING words, never the already-carrying line -- this is a status for a
    real condition, not a new default."""
    tmp = tempfile.mkdtemp(prefix='s155-hot0-control-')
    st, _g, live = H.build(tmp, blocks=['K1'])
    rows = H.tone_rows(st)
    wanted = rows[0]['in']

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
# 1b. THE P1 REPRODUCTION (hub addendum 2026-09-30 ~18:50, PW ~19:00): an
#     IDLE lane whose peak floor reads >12 dB over its RMS floor -- no lead
#     in before START, nothing plugged until the prompt (PW's own words:
#     "nothing was plugged before start, it was only plugged when asked").
# ---------------------------------------------------------------------------
def test_p1_an_idle_lane_with_a_loud_peak_floor_still_arrives():
    """The exact bug: MIC 1's own peak-hold floor sits >12 dB over its node
    RMS floor -- nothing to do with a lead, the same lane on two different
    instruments. The OLD `hot0` (peak `lvl0` against the RMS `floor`) read
    that gap alone as "already carrying" on a socket with nothing in it, so
    the removal edge it then demanded never came and the step burned its
    full 40 s before the operator's own plug-in at the prompt (the real
    sequence PW confirmed) was ever counted."""
    tmp = tempfile.mkdtemp(prefix='s155-p1-')
    st, _g, live = H.build(tmp, blocks=['K1'])
    logs = []
    st.log = logs.append
    rows = H.tone_rows(st)
    lane = int(rows[0]['lane'])
    rms_floor = -90.0
    peak_floor = -76.0          # 14 dB over the RMS floor -- MIC 15's own
                                # gap (S153) is 75.5 dBFS on a -90ish RMS unit
    rise = st.lim['detect_rise_db']
    assert peak_floor - rms_floor > rise, 'the scenario has to clear `rise`'

    # NOTHING PLUGGED BEFORE THE PROMPT: the lane sits at its own idle peak
    # reading (not the RMS number -- the peak meter never reads the RMS
    # floor, that is the whole bug) until poll 5, when the operator's plug
    # -- the real sequence -- brings the tone up.
    script = [peak_floor] * 5 + [-12.0] * 40

    def go():
        return H.run_detect(st, live, rows, script, floor=rms_floor,
                            peak_floor=peak_floor)
    (how, _a, dt, sc), seen = watched_screens(go)
    check('the OLD bug is real: peak vs RMS alone would have said hot0',
          (peak_floor - rms_floor) >= rise, '%.1f dB gap' % (peak_floor
                                                             - rms_floor))
    check('the FIXED station still arrives -- same instrument, no false '
          'removal demand', how == 'rise', repr(how))
    check('... at the plug-in, not after 40 s of a removal that could never '
          'come', dt < 2.0, '%.2f s' % dt)
    check('... and the log shows hot0 False, on the peak floor, not the '
          'RMS one',
          any('hot0 False' in s and '(peak)' in s for s in logs[:2]),
          repr(logs[:2]))


def test_p1_vs_p3_why_lane_1_differs_from_lane_3():
    """PW's own question: what did the two lanes' idle peak readings say?
    Modelled here with MIC 3's crest factor small enough that its peak never
    clears the RMS floor by `rise` -- `hot0` is False on BOTH instrument
    choices for MIC 3, which is why the bench saw it pass normally while
    MIC 1, with the larger gap, was the one the old code broke on."""
    tmp = tempfile.mkdtemp(prefix='s155-p1vp3-')
    st, _g, live = H.build(tmp, blocks=['K1'])
    rows = H.tone_rows(st)
    rise = st.lim['detect_rise_db']
    mic1_rms, mic1_peak = -90.0, -76.0     # gap 14 dB: clears `rise`
    mic3_rms, mic3_peak = -90.0, -85.0     # gap  5 dB: does not
    check('MIC 1\'s modelled gap clears `rise` -- this is the one hot0 broke '
          'on', (mic1_peak - mic1_rms) >= rise,
          '%.1f dB' % (mic1_peak - mic1_rms))
    check('MIC 3\'s modelled gap does not -- consistent with it passing '
          'normally on the bench',
          (mic3_peak - mic3_rms) < rise, '%.1f dB' % (mic3_peak - mic3_rms))

    def go():
        return H.run_detect(st, live, rows, [mic3_peak] * 5 + [-12.0] * 40,
                            floor=mic3_rms, peak_floor=mic3_peak)
    (how, _a, dt, _sc), _seen = watched_screens(go)
    check('and on the fixed code MIC 3\'s own step arrives cleanly either way',
          how == 'rise' and dt < 2.0, '%s %.2f s' % (how, dt))


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
               peak_floor=-96.0, watch=-96.0, sweep0={})

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
    for fn in (test_already_carrying_says_so_at_once,
               test_a_lane_that_was_never_hot_gets_the_plain_screen,
               test_p1_an_idle_lane_with_a_loud_peak_floor_still_arrives,
               test_p1_vs_p3_why_lane_1_differs_from_lane_3,
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
