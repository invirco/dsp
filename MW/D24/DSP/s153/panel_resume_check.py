#!/usr/bin/env python3
"""panel_resume_check.py -- S153 addendum: a resumed pass with nothing to press.

PW 2026-09-30: on a resumed pass where every press row of a switch board had
already passed, the panel station still put up "press the button that is lit"
while it ran only the temperature-sense listen (row 94), and he twice looked
for a light that was not there.

Drives the real `d24_runall.panel_station` on the RIGHT board (M2) with every
row of the board already PASS except row 94, records every screen the live
file carries (hooked at `Live._flush`, as S137 does), and asserts:

  * no screen asks for a press;
  * the board's opening page says there is nothing to press;
  * the listen runs under "checking the temperature sense - nothing to press",
    with PAUSE and nothing else;

and, as the control, that a FRESH pass on the same board still opens on the
press page it always did. No bus, no unit, no app.
"""
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'pi'))
os.environ.setdefault('MATRIX_ADDR_HOME',
                      os.path.join(ROOT, 'MW', 'D24', 'DSP', 's138b',
                                   'fixtures'))
import d24_live as LV       # noqa: E402
import d24_runall as RA     # noqa: E402
RA.PL.KNOWN_ABSENT.clear()   # S163: this case models the cell being sent

CATALOG = os.path.join(ROOT, 'MW', 'D24', 'DSP', 's119', 'test-catalog.csv')
PRESS_WORDS = ('press the button', 'that is lit')
FAILS = []


def check(name, cond, detail=''):
    print('%-4s %s%s' % ('ok' if cond else 'FAIL', name,
                         (': ' + detail) if detail else ''))
    if not cond:
        FAILS.append(name)


def drive(prepass):
    tmp = tempfile.mkdtemp(prefix='s153-panel-')
    rows, md5 = RA.load_catalog(CATALOG)
    state = RA.State(os.path.join(tmp, 'state.json'), 'S153-DESK', md5)
    for r in rows:
        if r.group == 'M2' and r.num in prepass:
            state.put(r.num, RA.PASS, pass_no=1, judged='runner',
                      measured='passed on an earlier pass', limit='',
                      evidence='', source='panel loop')
    glass = RA.Glass(os.path.join(tmp, 'runall'))
    live = LV.Live(os.path.join(tmp, 'runall'), run='panel', total=1,
                   enabled=True, confirm=True)
    seen = []
    orig = LV.Live._flush

    def flush(self):
        orig(self)
        seen.append(dict(self.d))
    orig_cmd = LV.Live.command

    def command(self):
        # the desk has no operator: the always-on and encoder-ring questions
        # are answered YES, as S137's harness answers them
        if list(self.d.get('buttons') or []) == list(LV.YESNO_BUTTONS):
            return 'yes'
        return orig_cmd(self)
    LV.Live._flush = flush
    LV.Live.command = command
    script = os.path.join(tmp, 'no-keys.txt')
    open(script, 'w').close()
    a = types.SimpleNamespace(inject_keys=script, left_cell='auto',
                              panel_timeout=1.0, random_panel_order=False)
    try:
        verdicts = RA.panel_station(a, 'M2', rows, state, set(), glass, 2,
                                    quiet_flag=None, live=live, keys=None)
    except RA.Paused:
        verdicts = None
    finally:
        LV.Live._flush = orig
        LV.Live.command = orig_cmd
    screens, last = [], None
    for d in seen:
        key = (d.get('state'), (d.get('instruction') or '').strip(),
               tuple(d.get('buttons') or []))
        if key != last and key[1]:
            last = key
            screens.append(key)
    return rows, screens, verdicts


def main():
    rows, _md5 = RA.load_catalog(CATALOG)
    board = [r.num for r in rows if r.group == 'M2']
    print('the right board (M2) owns rows %s' % board)
    check('row 94, the temperature sense, is on it', 94 in board)

    print('\n-- resumed: every row passed but 94')
    _r, screens, verdicts = drive(set(board) - {94})
    for s in screens:
        print('   [%s] %s  %s' % (s[0], s[1], list(s[2])))
    press = [s for s in screens if all(w in s[1].lower() for w in PRESS_WORDS)
             or 'press the button on it' in s[1].lower()]
    check('no screen asks for a press', not press, repr(press))
    check('the opening page says there is nothing to press',
          bool(screens) and 'nothing to press' in screens[0][1], repr(screens[:1]))
    listen = [s for s in screens if 'temperature sense' in s[1]]
    check('the listen runs under "checking the temperature sense - nothing to '
          'press"', any('nothing to press' in s[1] for s in listen), repr(listen))
    check('... with PAUSE and nothing else on it',
          all(list(s[2]) == ['pause'] for s in listen), repr(listen))
    check('row 94 was still graded', verdicts is not None and 94 in verdicts,
          repr(verdicts))

    print('\n-- control: a fresh pass on the same board')
    _r, screens, _v = drive(set())
    check('a fresh pass still opens on the press page',
          bool(screens) and 'lit' in screens[0][1].lower()
          and 'nothing to press' not in screens[0][1], repr(screens[:1]))
    after = [s for s in screens if 'temperature sense' in s[1]]
    check('... and its listen still says nothing to press',
          any('nothing to press' in s[1] for s in after), repr(after))

    print()
    if FAILS:
        print('%d check(s) FAILED' % len(FAILS))
        return 1
    print('all checks passed -- no unit, no bus, no write')
    return 0


if __name__ == '__main__':
    sys.exit(main())
