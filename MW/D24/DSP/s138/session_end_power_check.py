#!/usr/bin/env python3
"""session_end_power_check.py -- S138: proves session_end_power_check() (ruling
1.4, PS-PWR / row 134) end to end with NO unit, NO bus, NO display -- a
scripted `Glass(stdin=True)` answer, exactly the `d24_runall.py --stdin` path
the file already documents, driven from a real subprocess so `select.select`
on stdin works (the S137 pattern, ported from a scripted key file to a
scripted stdin line).

Three runs: "yes" -> PASS is recorded on row 134; "no" -> FAIL; --no-power-check
-> the question is never asked and row 134 is untouched.
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS_PI = os.path.join(HERE, '..', '..', '..', '..', 'tools', 'pi')
FIXTURE_HOME = os.path.join(HERE, 'fixtures')

DRIVER = r'''
import sys, os
sys.path.insert(0, %(tools_pi)r)
import d24_runall as R

state = R.State(%(state_path)r, 'SIMULATED', 'deadbeef')
glass = R.Glass(%(glass_dir)r, stdin=True)
verdict = R.session_end_power_check(state, glass)
print('RETURNED:', verdict)
'''

FAILS = []


def check(name, cond, detail=''):
    tag = 'ok' if cond else 'FAIL'
    print('%-4s %s%s' % (tag, name, (': ' + detail) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


def run_one(answer_line):
    with tempfile.TemporaryDirectory() as td:
        state_path = os.path.join(td, 'state.json')
        glass_dir = os.path.join(td, 'glass')
        driver = DRIVER % dict(tools_pi=os.path.abspath(TOOLS_PI),
                                state_path=state_path, glass_dir=glass_dir)
        env = dict(os.environ, MATRIX_ADDR_HOME=os.path.abspath(FIXTURE_HOME))
        p = subprocess.run([sys.executable, '-c', driver], input=answer_line,
                           capture_output=True, text=True, timeout=15, env=env)
        state = None
        if os.path.exists(state_path):
            state = json.load(open(state_path))
        return p, state


def test_yes_records_pass():
    p, state = run_one('yes\n')
    check('yes: process exits clean', p.returncode == 0, p.stderr[-800:])
    check('yes: PS-PWR asked and answered', 'RETURNED: PASS' in p.stdout, p.stdout)
    row = (state or {}).get('rows', {}).get('134')
    check('yes: row 134 recorded PASS', row is not None and row['verdict'] == 'PASS',
          repr(row))
    check('yes: judged by the operator, not the runner',
          row is not None and row.get('judged') == 'operator', repr(row))


def test_no_records_fail():
    p, state = run_one('no\n')
    check('no: process exits clean', p.returncode == 0, p.stderr[-800:])
    check('no: PS-PWR asked and answered', 'RETURNED: FAIL' in p.stdout, p.stdout)
    row = (state or {}).get('rows', {}).get('134')
    check('no: row 134 recorded FAIL', row is not None and row['verdict'] == 'FAIL',
          repr(row))


def test_skip_records_nothing():
    p, state = run_one('skip\n')
    check('skip: process exits clean', p.returncode == 0, p.stderr[-800:])
    check('skip: nothing recorded (returns None)', 'RETURNED: None' in p.stdout, p.stdout)
    row = (state or {}).get('rows', {}).get('134') if state else None
    check('skip: row 134 stays absent', row is None, repr(row))


def main():
    test_yes_records_pass()
    test_no_records_fail()
    test_skip_records_nothing()
    print()
    if FAILS:
        print('%d check(s) FAILED: %s' % (len(FAILS), ', '.join(FAILS)))
        return 1
    print('all checks passed -- no unit, no bus, no display; stdin only')
    return 0


if __name__ == '__main__':
    sys.exit(main())
