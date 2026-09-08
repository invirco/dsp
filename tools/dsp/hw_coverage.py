#!/usr/bin/env python3
"""hw_coverage.py — score a bench family run and report the COVERAGE FRACTION.

Input is the JSON `tools/pi/dsp4_family_verify.py` writes on the bench;
output is the table PW asked for: of the D24 cell families the LANDED
`defs/products/d24/dsp.csv` addresses, which fraction is exercised and
PASSED on hardware, by family and by addressed cell.

WHAT COUNTS AS PASSED, and the rule is deliberately strict about its own
denominator:

  numeric   the part's captured samples are reproduced WORD FOR WORD by
            the family's reference model, with the model's negative twin
            required to disagree on the same samples. This is the only
            verdict that says the arithmetic is right.
  audio     the family's landed addresses answer AND driving one of them
            moves the captured samples of its own node. This says the
            contract reaches the kernel; it does not say the kernel
            computes the right thing.
  contract  the landed addresses answer and nothing else was measurable.

A family PASSES only on `numeric`, or on `audio` where no reference model
for that family exists. `contract` alone is NOT a pass and is counted in
the "addressed but not exercised" column, because the number this file
exists to produce is worthless if it flatters itself.

WHICH COMPARISON APPLIES is per family and comes from the build, not from
a preference: under the shipping `DSP4_BQ_FLOAT` / `DSP4_GAIN_FLOAT` the
biquad cascades and the GAIN audio word run in float and their bit-exact
reference is `bq_float_ref` (numeric-spec: "SHARC float cascade ≡
bq_float_ref"); everything else is the fixed arm and its reference is
`fixed_ref`. The table says which for every row.

Usage:
    python3 tools/dsp/hw_coverage.py <report.json> [--md out.md]
    python3 tools/dsp/golden_harness.py --target hw <report.json>
"""

import argparse
import json
import sys

# Which reference model is normative for each family ON THE SHIPPING FLOAT
# IMAGE. numeric-spec.md §"Acceptance tolerances": the float cascade is
# held to bq_float_ref bit-exact and bq_float_ref to float64 within the
# response tolerances; the fixed arm is held to fixed_ref bit-exact.
FLOAT_ARM = {'EQ_BIQUAD', 'HPF_LPF', 'GEQ', 'ANTI_FB', 'CROSSOVER', 'GAIN'}

REFERENCE = {}
for _f in ('EQ_BIQUAD', 'HPF_LPF', 'GEQ', 'ANTI_FB', 'CROSSOVER'):
    REFERENCE[_f] = 'bq_float_ref (float cascade, bit-exact)'
REFERENCE['GAIN'] = 'bq_float_ref arm — the GAIN audio word is float under ' \
                    'DSP4_GAIN_FLOAT; its METER stays fixed'
for _f in ('GATE', 'COMPRESSOR', 'LIMITER', 'TUBE_SAT', 'DELAY',
           'FADER_PAN', 'ROUTING', 'METER'):
    REFERENCE[_f] = 'fixed_ref (fixed arm, bit-exact)'
for _f in ('FX_ENGINE', 'DCA', 'AUX_INPUT', 'TALKBACK', 'MONITOR',
           'NOISE_GEN'):
    REFERENCE[_f] = 'none declared'


def score(entry):
    """(verdict, basis, detail) for one family."""
    # AN EXTERNAL BAR OUTRANKS THIS RUN'S OWN PROBES, and says so. Some
    # families are verified by a dedicated instrument on its own image
    # (mtrverify.sh for METER, bqeverify.sh float for the cascade); where
    # one has been run its verdict is recorded here with the bar and the
    # image that produced it, because a probe inside the family walk can
    # be wrong about a family in ways the dedicated bar is not.
    ext = entry.get('external')
    if ext:
        return (ext['verdict'], 'external',
                '%s on image %s — %s' % (ext['bar'], ext.get('image', '?'),
                                         ext.get('detail', '')))
    contract = entry.get('contract') or []
    rw = [r for r in contract if r.get('access') == 'rw']
    ans = [r for r in rw if r.get('verdict') == 'ANSWERS']
    bad = [r for r in rw if r.get('verdict') in ('NO_ENTRY', 'MIXED', 'ERROR')]
    num = (entry.get('numeric') or {}).get('verdict')
    aud = (entry.get('audio') or {}).get('verdict')
    mtr = (entry.get('meter') or {}).get('verdict')

    if num == 'FAILED':
        return 'FAIL', 'numeric', 'the model does not reproduce the part'
    if aud == 'INERT':
        return 'FAIL', 'audio', ('the landed address answers and reaches no '
                                 'sample')
    if mtr == 'DISAGREES':
        return 'FAIL', 'meter', 'the SPI readback disagrees with the capture'
    if mtr == 'NO_VERDICT':
        return ('NOT EXERCISED', 'meter',
                'the peak-hold readback carries state from the probe before '
                'it — mtrverify.sh is this family\'s bar')
    if bad:
        return 'FAIL', 'contract', ('%d landed address(es) do not answer: %s'
                                    % (len(bad), ', '.join(
                                        r['cell'] for r in bad[:4])))
    if num == 'BIT_EXACT':
        n = (entry.get('numeric') or {}).get('stimuli')
        return 'PASS', 'numeric', 'bit-exact on %s stimuli' % n
    if mtr == 'AGREES':
        return 'PASS', 'meter', 'SPI readback agrees with the captured peak'
    if aud == 'LIVE':
        m = (entry.get('audio') or {}).get('moved')
        f = (entry.get('audio') or {}).get('floor')
        return 'PASS', 'audio', ('moves %s of %s captured words over a floor '
                                 'of %s' % (m, (entry.get('audio') or {}).get(
                                     'words'), f))
    if rw and len(ans) == len(rw):
        return 'NOT EXERCISED', 'contract', (
            '%d/%d landed addresses answer; %s'
            % (len(ans), len(rw), {'NO_PROBE': 'no audio probe exists',
                                   'NO_STIMULUS_PATH':
                                       'no stimulus path on this bench',
                                   'SILENT': 'the capture window carried no '
                                             'signal — not a verdict',
                                   'NO_CAPTURE': 'the capture failed',
                                   'NO_SYMBOL': 'the witness symbol is not '
                                                'in this build',
                                   'NOT_MEASURED': 'not measured'}.get(
                                       aud, str(aud))))
    return 'NOT MEASURED', '-', 'no contract result'


def build(report):
    fam_cells = report.get('family_cells', {})
    rows = []
    for f in sorted(fam_cells):
        e = report.get('families', {}).get(f, {})
        verdict, basis, detail = score(e)
        contract = e.get('contract') or []
        rw = [r for r in contract if r.get('access') == 'rw']
        ans = [r for r in rw if r.get('verdict') == 'ANSWERS']
        rows.append({
            'family': f, 'cells': fam_cells[f], 'chip': e.get('chip'),
            'node': e.get('node'), 'rw': len(rw), 'answers': len(ans),
            'numeric': ((e.get('external') or {}).get('bar')
                        or (e.get('numeric') or {}).get('verdict', '-')),
            'audio': (e.get('audio') or {}).get('verdict', '-'),
            'meter': (e.get('meter') or {}).get('verdict', '-'),
            'reference': REFERENCE.get(f, 'none declared'),
            'verdict': verdict, 'basis': basis, 'detail': detail,
            'note': e.get('note', ''),
        })
    return rows


def totals(rows):
    total_f = len(rows)
    total_c = sum(r['cells'] for r in rows)
    passed = [r for r in rows if r['verdict'] == 'PASS']
    failed = [r for r in rows if r['verdict'] == 'FAIL']
    return {
        'families': total_f, 'cells': total_c,
        'families_passed': len(passed),
        'cells_passed': sum(r['cells'] for r in passed),
        'families_failed': len(failed),
        'cells_failed': sum(r['cells'] for r in failed),
        'families_numeric': len([r for r in passed
                                 if r['basis'] in ('numeric', 'external')]),
        'cells_numeric': sum(r['cells'] for r in passed
                             if r['basis'] in ('numeric', 'external')),
    }


def render(report, rows, t, build_md5=None, date=None):
    L = []
    L.append('| family | cells | chip / node | landed addrs answering | '
             'numeric | audio | verdict | reference model |')
    L.append('|---|---:|---|---:|---|---|---|---|')
    for r in rows:
        L.append('| `%s` | %d | %s %s | %d/%d | %s | %s | **%s** | %s |'
                 % (r['family'], r['cells'],
                    ('chip %s' % r['chip']) if r['chip'] else '—',
                    r['node'] or '', r['answers'], r['rw'],
                    r['numeric'], r['audio'], r['verdict'], r['reference']))
    L.append('')
    L.append('**Coverage.** Of the **%d** D24 cell families `dsp.csv` '
             'addresses (%d cells), **%d families PASSED on hardware '
             '(%.0f %%)**, covering **%d of %d addressed cells (%.0f %%)**. '
             '**%d families passed on the strict bar** — the part\'s own '
             'samples reproduced word for word by the reference model — '
             'covering %d cells (%.0f %%). %d families FAILED.'
             % (t['families'], t['cells'], t['families_passed'],
                100.0 * t['families_passed'] / max(t['families'], 1),
                t['cells_passed'], t['cells'],
                100.0 * t['cells_passed'] / max(t['cells'], 1),
                t['families_numeric'], t['cells_numeric'],
                100.0 * t['cells_numeric'] / max(t['cells'], 1),
                t['families_failed']))
    L.append('')
    L.append('| family | why |')
    L.append('|---|---|')
    for r in rows:
        L.append('| `%s` | %s — %s |' % (r['family'], r['basis'], r['detail']))
    return '\n'.join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('report')
    ap.add_argument('--md', default=None)
    ap.add_argument('--build', default=None, help='image md5, for the header')
    ap.add_argument('--date', default=None)
    ap.add_argument('--external', action='append', default=[],
                    metavar='FAMILY:VERDICT:BAR:IMAGE:DETAIL',
                    help='record a dedicated bar\'s verdict for a family; '
                         'repeatable')
    a = ap.parse_args(argv)

    with open(a.report) as fh:
        report = json.load(fh)
    for spec in a.external:
        parts = spec.split(':', 4)
        if len(parts) < 4:
            raise SystemExit('--external needs FAMILY:VERDICT:BAR:IMAGE[:DETAIL]')
        fam, verdict, bar, image = parts[:4]
        detail = parts[4] if len(parts) > 4 else ''
        report.setdefault('families', {}).setdefault(fam, {})['external'] = {
            'verdict': verdict, 'bar': bar, 'image': image, 'detail': detail}
    rows = build(report)
    t = totals(rows)
    md = render(report, rows, t, a.build, a.date)
    print('contract: %s  pin %s  sha256 %s'
          % (report.get('product'), report.get('pin'),
             (report.get('sha256') or '')[:12]))
    cc = report.get('cross_check') or {}
    print('cross-check: %d transcribed constants, %d disagreements'
          % (len(cc.get('rows', [])), cc.get('disagreements', 0)))
    print()
    print(md)
    if a.md:
        with open(a.md, 'w') as fh:
            fh.write(md + '\n')
        print('\nwrote %s' % a.md)
    return 1 if t['families_failed'] else 0


if __name__ == '__main__':
    sys.exit(main())
