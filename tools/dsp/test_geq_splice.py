#!/usr/bin/env python3
"""test_geq_splice.py — R3: geq_splice.relink_and_insert (used by
gen_dsp_csv.py's GEQ insertion) must fail loudly with a contextual
message when the chain it expects is not in the graph, instead of the
bare StopIteration that predated review §2.4 / patch §5.2.

Run directly: python3 test_geq_splice.py
"""
import sys

from geq_splice import relink_and_insert

results = []


def check(name, cond):
    results.append((name, cond))


def t_happy_path():
    rows = [{'id': 'A', 'outputs': 'B', 'inputs': ''},
            {'id': 'B', 'outputs': '', 'inputs': 'A'}]
    new_row = {'id': 'X'}
    relink_and_insert(rows, 'A', 'B', new_row, 'happy path')
    check('relink_and_insert rewires and inserts in chain order',
          [r['id'] for r in rows] == ['A', 'X', 'B']
          and rows[0]['outputs'] == 'X'
          and rows[2]['inputs'] == 'X')


def t_multi_value_chain():
    # A fans out to B and C; only the A->B leg should be retargeted, and
    # B's other input (D) must survive untouched.
    rows = [{'id': 'A', 'outputs': 'B;C', 'inputs': ''},
            {'id': 'B', 'outputs': '', 'inputs': 'A;D'},
            {'id': 'C', 'outputs': '', 'inputs': 'A'}]
    new_row = {'id': 'X'}
    relink_and_insert(rows, 'A', 'B', new_row, 'multi-value chain')
    b_row = next(r for r in rows if r['id'] == 'B')
    c_row = next(r for r in rows if r['id'] == 'C')
    check('relink_and_insert touches only the matched leg',
          rows[0]['outputs'] == 'X;C' and b_row['inputs'] == 'X;D'
          and c_row['inputs'] == 'A')


def t_missing_after():
    # `after_id` absent from the graph: the exact "out of sync" case
    # review §2.4 flagged as an unhandled StopIteration.
    rows = [{'id': 'B', 'outputs': '', 'inputs': 'A'}]
    new_row = {'id': 'X'}
    try:
        relink_and_insert(rows, 'MISSING', 'B', new_row, 'out-of-sync graph')
        check('missing after_id raises ValueError, not StopIteration', False)
    except StopIteration:
        check('missing after_id raises ValueError, not StopIteration', False)
    except ValueError as e:
        check('missing after_id raises ValueError, not StopIteration',
              'MISSING' in str(e) and 'out-of-sync graph' in str(e))


def t_missing_before():
    rows = [{'id': 'A', 'outputs': 'B', 'inputs': ''}]
    new_row = {'id': 'X'}
    try:
        relink_and_insert(rows, 'A', 'MISSING', new_row, 'out-of-sync graph')
        check('missing before_id raises ValueError, not StopIteration', False)
    except StopIteration:
        check('missing before_id raises ValueError, not StopIteration', False)
    except ValueError as e:
        check('missing before_id raises ValueError, not StopIteration',
              'MISSING' in str(e))


def t_missing_both():
    rows = [{'id': 'Z', 'outputs': '', 'inputs': ''}]
    new_row = {'id': 'X'}
    try:
        relink_and_insert(rows, 'A', 'B', new_row, 'out-of-sync graph')
        check('missing both ids raises ValueError naming both', False)
    except ValueError as e:
        check('missing both ids raises ValueError naming both',
              "'A'" in str(e) and "'B'" in str(e))


def main():
    for t in (t_happy_path, t_multi_value_chain, t_missing_after,
              t_missing_before, t_missing_both):
        t()
    fails = 0
    for name, ok in results:
        fails += (not ok)
        print(f'{"PASS" if ok else "FAIL"}  {name}')
    print(f'\n{len(results) - fails}/{len(results)} passed')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
