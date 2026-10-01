#!/usr/bin/env python3
"""sense_sweep_check.py -- S138b: the TEMP / BLOWER / FAN sense row (gaps doc
2.3, catalog row 94), graded read-only off the panel bus. No unit, no serial
port, no write of any kind.

WHY ROW 94 IS NOT AN INSERT/REMOVE ROW, which is the one place this build
departs from the dispatch's wording and it is defs that says so. The dispatch
groups 93 and 94 and gives them the same shape -- "arm the listen before the
instruction, prompt (insert the jack, remove it), require the on-edge then the
off-edge". That is exactly right for 93. It cannot be right for 94, because
`mx_master.csv` gives `Sys[1-1]SwTempFan[1-1]` two different meanings on one
cell:

    READ  = the TEMP raw count (H1S3 PA1; the host scales it)
    WRITE = the drive mask bit0 = BLOWER bit1 = FAN

So the READ half is an analog count with no edges and no operator action that
moves it, and the only switch-like half is the WRITE -- a real blower and a
real fan -- which this dispatch forbids and which nothing here touches. The
graded check is therefore the pass-through being ALIVE and the count being off
both rails: a count of 0 or 255 is a shorted or open sensor, and what counts as
a plausible DEGREE is PW's and is recorded, not invented. Finding S138b-3.

Driven through `d24_panel.InjectedBus`, the same scripted-stream mechanism
S137's panel proofs use, extended in this session to carry named sense cells.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, '..', '..', '..', '..', 'tools', 'pi')
sys.path.insert(0, TOOLS)
os.environ.setdefault('MATRIX_ADDR_HOME', os.path.join(HERE, 'fixtures'))
import d24_panel as PL      # noqa: E402
_KA = dict(PL.KNOWN_ABSENT); PL.KNOWN_ABSENT.clear()   # S163: these cases model the panel firmware that DOES send the cell

SCRIPTS = os.path.join(HERE, 'scripts')
FAILS = []


def check(name, cond, detail=''):
    print('%-4s %s%s' % ('ok' if cond else 'FAIL', name,
                         (': ' + detail) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


def sweep(script_name, timeout=0.2):
    bus = PL.InjectedBus(os.path.join(SCRIPTS, script_name))
    asked = []

    def ask(instruction, row, n, total):
        asked.append((row, n, total, instruction))
        return lambda: None
    got = PL.sense_sweep(bus, 'right', ask, timeout=timeout,
                         log=lambda s: None)
    return got, asked, bus


def test_row_93_is_not_here():
    check('row 93 is NOT a panel sense row: it is folded into the analog '
          'station\'s mini-jack step (PW addendum 1)',
          93 not in PL.sense_rows_for('right'),
          repr(PL.sense_rows_for('right')))
    check('row 94 is', PL.sense_rows_for('right') == [94],
          repr(PL.sense_rows_for('right')))
    check('and neither is claimed by the button sweep\'s UNREACHED table any '
          'more',
          93 not in PL.UNREACHED['right'] and 94 not in PL.UNREACHED['right'],
          repr(sorted(PL.UNREACHED['right'])))


def test_a_plausible_count_passes():
    got, asked, bus = sweep('tempfan-plausible.txt')
    check('row 94 is graded', 94 in got, repr(got))
    check('a count off both rails PASSES', got[94][0] == PL.PASS, repr(got))
    check('the reading is quoted in the note', '31' in got[94][1],
          repr(got[94][1]))
    check('the operator is asked for NOTHING: the read half has no action that '
          'moves it',
          asked == [], repr(asked))
    check('the port was drained before the listen -- the arm',
          bus.flushes >= 1, repr(bus.flushes))


def test_a_rail_fails_and_says_which():
    got, _a, _b = sweep('tempfan-low-rail.txt')
    check('a count on the low rail FAILS', got[94][0] == PL.FAIL, repr(got))
    check('... and says it is a shorted or open sensor, not a temperature',
          'shorted or open' in got[94][1], repr(got[94][1]))
    check('... and says the degree band is PW\'s and unruled',
          'unruled' in got[94][1], repr(got[94][1]))
    got2, _a, _b = sweep('tempfan-high-rail.txt')
    check('a count on the high rail FAILS too', got2[94][0] == PL.FAIL,
          repr(got2))
    check('... and names the high rail', 'high rail' in got2[94][1],
          repr(got2[94][1]))


def test_silence_is_no_data_and_names_the_firmware():
    got, _a, _b = sweep('tempfan-silent.txt')
    check('no transmission is NO DATA, never a FAIL', got[94][0] == PL.NODATA,
          repr(got))
    check('... and says it is a panel-firmware precondition',
          'panel-firmware precondition' in got[94][1], repr(got[94][1]))
    check('... and says it is NOT a fault in the sensor',
          'NOT a fault' in got[94][1], repr(got[94][1]))
    check('... and says what clears it',
          'H1S3 is rebuilt' in got[94][1], repr(got[94][1]))


def test_owed_is_respected():
    bus = PL.InjectedBus(os.path.join(SCRIPTS, 'tempfan-plausible.txt'))
    got = PL.sense_sweep(bus, 'right', lambda *a: (lambda: None),
                         timeout=0.2, log=lambda s: None, owed=set())
    check('a row that already passed on an earlier run is not re-read',
          got == {}, repr(got))


def test_nothing_is_ever_written():
    """The sweep must not light, write or send. `InjectedBus` records every
    light; a `send` would not even exist on it."""
    bus = PL.InjectedBus(os.path.join(SCRIPTS, 'tempfan-plausible.txt'))
    PL.sense_sweep(bus, 'right', lambda *a: (lambda: None), timeout=0.2,
                   log=lambda s: None)
    check('no cell was lit or written during the sweep', bus.lights == [],
          repr(bus.lights))
    check('the bus offers no write on this path at all',
          not hasattr(bus, 'send'), repr(sorted(dir(bus))[-6:]))


def test_the_cell_is_resolved_by_name():
    check('the TEMP/FAN cell is resolved by NAME off the pack, never a literal',
          PL.CELL_NAMES['tempfan'] == 'Sys001SwTempFan001')
    check('... and the fixture pack\'s address is what it resolved to',
          PL.CELL_ADDR['tempfan'] == 4362, repr(PL.CELL_ADDR['tempfan']))
    check('a row whose cell is absent from the pack reports that, not a guess',
          PL.CELL_ABSENT['tempfan'] is None
          or isinstance(PL.CELL_ABSENT['tempfan'], str))


def test_mode_sense_prints_json():
    PL.KNOWN_ABSENT.update(_KA)   # the subprocess has the shipped table
    """The standalone entry, as a bench operator would run it."""
    import subprocess
    p = subprocess.run(
        [sys.executable, os.path.join(TOOLS, 'd24_panel.py'), '--mode', 'sense',
         '--panel', 'right', '--timeout', '0.2',
         '--inject', os.path.join(SCRIPTS, 'tempfan-plausible.txt')],
        capture_output=True, text=True,
        env=dict(os.environ, MATRIX_ADDR_HOME=os.path.join(HERE, 'fixtures')))
    check('--mode sense runs and prints JSON', p.returncode == 0,
          p.stdout[-300:] + p.stderr[-300:])
    try:
        d = json.loads(p.stdout)
    except Exception as e:
        check('--mode sense output parses', False, '%s: %r' % (e, p.stdout))
        return
    PL.KNOWN_ABSENT.clear()
    check('it reports row 94 and its verdict',
          d['rows'] and d['rows'][0]['num'] == 94
          and d['rows'][0]['verdict'] == PL.NODATA
          and d['rows'][0]['note'].startswith(PL.KNOWN_ABSENT_TAG), repr(d))


class Row(object):
    def __init__(self, num, group='M2'):
        self.num, self.group = num, group
        self.cls, self.automation = 'panel control', '2'

    @property
    def panel(self):
        return 'a row'


def test_the_runner_calls_row_94_a_loop_row():
    """The subtle one, and it is the reason `rows_for` had to change.

    A row the panel station grades must come back from `manual_step` as a LOOP
    row. If it comes back BLOCKED, `classify` files it as 'not-run' and
    `record_not_run` then FORCES a NOT TESTED over whatever `sense_sweep` had
    just landed -- a graded FAIL would silently become "not tested".
    """
    sys.path.insert(0, TOOLS)
    import d24_runall as RA
    step = RA.manual_step(Row(94))
    check('row 94 is a LOOP row, not BLOCKED', step['kind'] == RA.LOOP,
          repr(step))
    check('... and it says there is nothing for the operator to do',
          'Nothing to do' in step['action'], repr(step['action']))
    check('... and states what grades it',
          'listening' in step['check'], repr(step['check']))
    check('the button rows are untouched by that change',
          RA.manual_step(Row(66))['kind'] == RA.LOOP)
    check('and a row the station really cannot reach is still BLOCKED',
          RA.manual_step(Row(92))['kind'] == RA.BLOCKED)
    check('row 94 carries its own wording for --dump-dialogs',
          PL.wording('right', 94)[0] and PL.wording('right', 94)[2],
          repr(PL.wording('right', 94)))


def main():
    for fn in (test_row_93_is_not_here,
               test_the_runner_calls_row_94_a_loop_row,
               test_a_plausible_count_passes,
               test_a_rail_fails_and_says_which,
               test_silence_is_no_data_and_names_the_firmware,
               test_owed_is_respected,
               test_nothing_is_ever_written,
               test_the_cell_is_resolved_by_name,
               test_mode_sense_prints_json):
        print('-- %s' % fn.__name__)
        fn()
    print()
    if FAILS:
        print('%d check(s) FAILED: %s' % (len(FAILS), ', '.join(FAILS)))
        return 1
    print('all checks passed -- no unit, no serial port, no write, no '
          'BLOWER/FAN drive')
    return 0


if __name__ == '__main__':
    sys.exit(main())
