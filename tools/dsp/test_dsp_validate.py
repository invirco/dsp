#!/usr/bin/env python3
"""test_dsp_validate.py — R4: dsp_validate.py must reject one malformed
row per failure class, quoting the row/id in the error rather than
passing the row through to codegen. Each case writes a minimal synthetic
dsp.csv to a temp file and asserts validate() returns nonzero with a
message naming the offending row.

Run directly: python3 test_dsp_validate.py
"""
import contextlib
import csv
import io
import os
import sys
import tempfile

from dsp_validate import validate

HEADER = ['id', 'chip', 'type', 'ch_count', 'inputs', 'outputs',
          'spi_page', 'spi_addr', 'params', 'ramp_profile']

results = []


def check(name, cond):
    results.append((name, cond))


def run_validate(rows):
    """Write `rows` (list of dicts, HEADER keys) to a temp CSV, validate
    it, and return (exit_code, captured_stdout)."""
    fd, path = tempfile.mkstemp(suffix='.csv')
    try:
        with os.fdopen(fd, 'w', newline='', encoding='utf-8') as f:
            w = csv.DictWriter(f, fieldnames=HEADER)
            w.writeheader()
            w.writerows(rows)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = validate(path)
        return code, buf.getvalue()
    finally:
        os.unlink(path)


def base_row(**over):
    r = {'id': 'N1', 'chip': '1', 'type': 'GAIN', 'ch_count': '1',
         'inputs': '', 'outputs': '', 'spi_page': '1', 'spi_addr': '0',
         'params': 'gain_db=0.0;mute=0;polarity=0', 'ramp_profile': ''}
    r.update(over)
    return r


def t_empty_id():
    code, out = run_validate([base_row(id='')])
    check('empty id rejected, message names the row',
          code == 1 and 'Row 2' in out and 'empty' in out.lower())


def t_duplicate_id():
    rows = [base_row(id='DUP'), base_row(id='DUP', spi_addr='4')]
    code, out = run_validate(rows)
    check('duplicate id rejected outright (not reprocessed)',
          code == 1 and 'Duplicate node ID' in out and 'DUP' in out)


def t_bad_chip():
    code, out = run_validate([base_row(chip='3')])
    check('invalid chip value rejected, message quotes it',
          code == 1 and 'N1' in out and '"3"' in out)


def t_unknown_type():
    code, out = run_validate([base_row(type='FROBNICATE')])
    check('unknown node type rejected, message quotes it',
          code == 1 and '"FROBNICATE"' in out)


def t_unknown_ramp_profile():
    code, out = run_validate([base_row(ramp_profile='Bogus')])
    check('unknown ramp_profile rejected, message quotes it',
          code == 1 and '"Bogus"' in out)


def t_bad_ch_count():
    code, out = run_validate([base_row(ch_count='0')])
    check('ch_count < 1 rejected, message names the row',
          code == 1 and 'N1' in out and 'ch_count' in out)


def t_non_integer_spi():
    code, out = run_validate([base_row(spi_addr='not-a-number')])
    check('non-integer spi_addr rejected, message quotes it',
          code == 1 and '"not-a-number"' in out)


def t_spi_collision():
    rows = [base_row(id='A', spi_page='1', spi_addr='0'),
            base_row(id='B', spi_page='1', spi_addr='0')]
    code, out = run_validate(rows)
    check('SPI address collision rejected, message names both ids',
          code == 1 and 'collision' in out.lower() and 'A' in out
          and 'B' in out)


def t_missing_required_param():
    code, out = run_validate([base_row(params='gain_db=0.0')])
    check('missing required param rejected, message names the type',
          code == 1 and 'Missing required params' in out and 'GAIN' in out)


def t_unrecognized_param():
    code, out = run_validate(
        [base_row(params='gain_db=0.0;mute=0;polarity=0;bogus_key=1')])
    check('unrecognized param rejected, message quotes the key',
          code == 1 and 'Unrecognized params' in out and 'bogus_key' in out)


def t_dangling_reference():
    code, out = run_validate([base_row(inputs='DOES_NOT_EXIST')])
    check('dangling input reference rejected, message quotes it',
          code == 1 and 'DOES_NOT_EXIST' in out
          and 'does not exist' in out.lower())


def t_cycle():
    rows = [base_row(id='X', inputs='Y', outputs='Y'),
            base_row(id='Y', inputs='X', outputs='X')]
    code, out = run_validate(rows)
    check('same-chip cycle rejected, message names it a cycle',
          code == 1 and 'CYCLE' in out)


def t_valid_row_passes():
    code, out = run_validate([base_row()])
    check('a well-formed row passes (control)', code == 0)


# ---------------------------------------------------------------------------
# S143 — the arity contract and the follower rules (from finding S142-1)
# ---------------------------------------------------------------------------

def _fdr(nid, **over):
    r = {'id': nid, 'chip': '2', 'type': 'FADER_PAN', 'ch_count': '1',
         'inputs': '', 'outputs': '', 'spi_page': '1', 'spi_addr': '0',
         'params': 'level_db=0.0;mute=0', 'ramp_profile': ''}
    r.update(over)
    return r


def t_unread_second_input():
    """S142-1 itself: two inputs, a generator that reads one, nothing said."""
    rows = [base_row(id='L', spi_addr='0'), base_row(id='R', spi_addr='1'),
            _fdr('F', inputs='L;R', ch_count='2', spi_addr='2')]
    code, out = run_validate(rows)
    check('S142-1: a declared input the generator cannot read is rejected',
          code == 1 and 'read by nothing' in out and 'S142-1' in out)


def t_ch_count_without_follower():
    """`ch_count` stops being comment text."""
    rows = [base_row(id='L', spi_addr='0'),
            _fdr('F', inputs='L', ch_count='2', spi_addr='2')]
    code, out = run_validate(rows)
    check('S143: ch_count=2 with no follower is rejected',
          code == 1 and 'ch_count=2' in out and 'follower' in out)


def t_follower_with_address():
    rows = [base_row(id='L', spi_addr='0'), base_row(id='R', spi_addr='1'),
            _fdr('F', inputs='L', ch_count='2', spi_addr='2'),
            _fdr('F_R', inputs='R', spi_addr='3',
                 params='follows=F')]
    code, out = run_validate(rows)
    check('S143: a follower carrying an SPI address is rejected',
          code == 1 and 'must take no address' in out)


def t_follower_before_master():
    rows = [base_row(id='L', spi_addr='0'), base_row(id='R', spi_addr='1'),
            _fdr('F_R', inputs='R', spi_page='-1', spi_addr='-1',
                 params='follows=F'),
            _fdr('F', inputs='L', ch_count='2', spi_addr='2')]
    code, out = run_validate(rows)
    check('S143: a follower placed before its master is rejected',
          code == 1 and 'appears before it' in out)


def t_follower_type_mismatch():
    rows = [base_row(id='L', spi_addr='0'), base_row(id='R', spi_addr='1'),
            _fdr('F', inputs='L', ch_count='2', spi_addr='2'),
            base_row(id='F_R', chip='2', inputs='R', spi_page='-1',
                     spi_addr='-1',
                     params='gain_db=0.0;mute=0;polarity=0;follows=F')]
    code, out = run_validate(rows)
    check('S143: a follower of a different type is rejected',
          code == 1 and 'second instance' in out)


def t_link_in_not_an_input():
    rows = [base_row(id='L', spi_addr='0'), base_row(id='R', spi_addr='1'),
            {'id': 'C', 'chip': '2', 'type': 'LIMITER', 'ch_count': '1',
             'inputs': 'L', 'outputs': '', 'spi_page': '1', 'spi_addr': '2',
             'params': 'threshold_db=-0.5;attack_ms=0.1;release_ms=50.0;'
                       'link_in=R',
             'ramp_profile': ''}]
    code, out = run_validate(rows)
    check('S143: link_in that is not also an input is rejected',
          code == 1 and 'never stages its buffer' in out)


def t_valid_follower_passes():
    """The control: the S143 shape the graph actually uses."""
    rows = [base_row(id='L', spi_addr='0'), base_row(id='R', spi_addr='1'),
            _fdr('F', inputs='L', ch_count='2', spi_addr='2'),
            _fdr('F_R', inputs='R', spi_page='-1', spi_addr='-1',
                 params='follows=F')]
    code, out = run_validate(rows)
    check('S143: a well-formed master/follower pair passes (control)',
          code == 0)


def main():
    for t in (t_empty_id, t_duplicate_id, t_bad_chip, t_unknown_type,
              t_unknown_ramp_profile, t_bad_ch_count, t_non_integer_spi,
              t_spi_collision, t_missing_required_param,
              t_unrecognized_param, t_dangling_reference, t_cycle,
              t_valid_row_passes,
              t_unread_second_input, t_ch_count_without_follower,
              t_follower_with_address, t_follower_before_master,
              t_follower_type_mismatch, t_link_in_not_an_input,
              t_valid_follower_passes):
        t()
    fails = 0
    for name, ok in results:
        fails += (not ok)
        print(f'{"PASS" if ok else "FAIL"}  {name}')
    print(f'\n{len(results) - fails}/{len(results)} passed')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
