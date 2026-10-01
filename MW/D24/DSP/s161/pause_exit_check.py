#!/usr/bin/env python3
"""pause_exit_check.py -- S161, on the model (no unit, no bus, no rails).

  1. PAUSE in the patch station leaves the pass OPEN: patch_station raises
     Paused with state.d['current'] still on the step, keeps what was scored,
     and a resumed station walks only what is still owed (S159 rules).
  2. EXIT on the factory summary never posts a dialog: session_end on a pass
     that built the factory screen asks nothing, lowers the rails, and the
     wizard path (no screen) still asks the power question.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 's159'))
import rerun_ein_check as R      # noqa: E402  (sets up paths and the model)

RA, PT, LV, TD = R.RA, R.PT, R.LV, R.TD
check = R.check


def case_pause():
    tmp = tempfile.mkdtemp(prefix='s161-pause-')
    rows, state = R.fresh_state(tmp)
    unit, hands, glass, live, screens = R.rig(tmp)
    plist = PT.PatchList(R.LIST_DIR)
    want = R.expected_walk(plist, R.owed_now(rows, state),
                           RA.patch_carry(state)['patches'])
    stop_at = want[10]
    hands.plan[stop_at] = [(0.0, 'clear', None), (3.0, 'press', 'pause')]
    state.d['current'] = {'phase': 'manual', 'step': 7, 'pass': 5, 'row': 1}
    raised = False
    try:
        RA.patch_station(R.A(), 'M4', rows, state, set(), glass, 5, live=live,
                         keys=PT.KeyWatch(enabled=False))
    except RA.Paused:
        raised = True
    got = R.walked(hands)
    check('PAUSE at %s raises Paused out of patch_station' % stop_at, raised)
    check('the walk stopped there, not after the whole station',
          got and got[-1] == stop_at and len(set(got)) <= 11,
          (len(set(got)), got[-3:]))
    check('state.d["current"] still on the step (pass left open)',
          (state.d.get('current') or {}).get('step') == 7
          and state.d.get('passes', 4) != 5, state.d.get('current'))
    done = [p for p in dict.fromkeys(got) if p != stop_at]
    kept = state.d.get('patches') or {}
    check('what was scored before the pause is kept (%d patches)' % len(done),
          all(p in kept for p in done[-3:]),
          [p for p in done if p not in kept])
    # resume: a fresh station over the same state walks only what is owed NOW
    # (an EIN FAIL in the first segment re-owes that input's rows, S159)
    want2 = R.expected_walk(plist, R.owed_now(rows, state),
                            RA.patch_carry(state)['patches'])
    unit, hands2, glass, live, screens = R.rig(tmp)
    try:
        RA.patch_station(R.A(), 'M4', rows, state, set(), glass, 5, live=live,
                         keys=PT.KeyWatch(enabled=False))
    except RA.Paused:
        pass
    again = list(dict.fromkeys(R.walked(hands2)))
    fresh = [p for p in done
             if (kept.get(p) or {}).get('verdict') == 'PASS']
    check('the resume does not re-walk patches that passed before the pause',
          not [p for p in again if p in fresh], [p for p in again if p in fresh])
    check('the resume walks the paused patch and the failed ones, nothing else',
          stop_at in again and not [p for p in again if p not in want2],
          [p for p in again if p not in want2])


class DialogGlass(object):
    def __init__(self):
        self.asked = 0
        self.rails = 0

    def ask(self, *a, **k):
        self.asked += 1
        return dict(button='yes')

    def progress(self, *a, **k):
        pass


def case_exit():
    lowered = []
    RA.lower_rails = lambda g: lowered.append(1)
    state = type('S', (), dict(d={}, put=lambda *a, **k: None,
                               save=lambda s: None))()
    a = type('A', (), dict(no_power_check=False, _screen_built=True))()
    g = DialogGlass()
    RA.session_end(a, state, g)
    check('factory path: EXIT posts no dialog', g.asked == 0, g.asked)
    check('factory path: the rails are put safe', lowered == [1], lowered)
    a._screen_built = False
    g = DialogGlass()
    RA.session_end(a, state, g)
    check('wizard path: the power question is still asked', g.asked == 1,
          g.asked)


if __name__ == '__main__':
    case_pause()
    case_exit()
    if R.FAILS:
        print('FAILED: %s' % ', '.join(R.FAILS))
        sys.exit(1)
    print('all checks passed -- no unit, no bus, no write, no rails')
