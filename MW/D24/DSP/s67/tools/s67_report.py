#!/usr/bin/env python3
"""s67_report.py <datadir> — the S67 tables (measured vs predicted) from s67_run.py's JSON, desk side."""
import json, math, os, sys

D = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), '..', 'data')


def J(n):
    p = os.path.join(D, n + '.json')
    return json.load(open(p)) if os.path.exists(p) else None


def f(v, w=8, p=3):
    if v is None or v < -1e9:
        return '-inf'.rjust(w)
    return ('%' + str(w) + '.' + str(p) + 'f') % v


def db(x):
    return 20 * math.log10(x) if x > 0 else float('-inf')


def H(m, ch):
    return m[str(ch)]['H_db']


for mode in ('analog', 'osc'):
    r = J('fader_' + mode)
    if not r:
        continue
    print('\n## fader, %s (dB re fader 0 dB; ideal = 20 log10 Level)' % mode)
    chans = [5, 33, 34] + ([35] if mode == 'osc' else [])
    print('| fader | ideal | ' + ' | '.join({5: 'strip 5 post-fdr', 33: 'MAIN L', 34: 'MAIN R', 35: 'AUX 1'}[c] for c in chans) + ' | worst err |')
    b = r['rows'][0]['m']
    for row in r['rows']:
        vals = [H(row['m'], c) - H(b, c) if H(row['m'], c) > -1e9 else None for c in chans]
        err = max(abs(v - row['ideal_db']) for v in vals) if all(v is not None for v in vals) and row['level'] > 0 else None
        print('| %s | %s | %s | %s |' % (row['tag'], f(row['ideal_db'], 7), ' | '.join(f(v, 8) for v in vals),
                                        ('%.4f' % err) if err is not None else ('exact 0 (H = 0)' if all(v is None for v in vals) else '?')))
    print('absolute at 0 dB:', {c: round(H(b, c), 4) for c in chans})

r = J('pan_analog') or J('pan_osc')
if r:
    print('\n## pan (%s): MAIN L/R re strip 5 post-fader, dB' % r['mode'])
    print('| law | idx | L meas | L pred | R meas | R pred | worst err |')
    for x in r['rows']:
        errs = [abs(a - b) for a, b in ((x['meas_L_db'], x['pred_L_db']), (x['meas_R_db'], x['pred_R_db'])) if a is not None]
        print('| %d | %d | %s | %s | %s | %s | %s |' % (x['law'], x['idx'], f(x['meas_L_db']), f(x['pred_L_db']),
                                                      f(x['meas_R_db']), f(x['pred_R_db']), '%.4f' % max(errs)))

for mode in ('analog', 'osc'):
    r = J('assign_' + mode)
    if not r:
        continue
    print('\n## assign, %s (coherent H dB; nonzero words of 16 in the bus block)' % mode)
    for x in r['rows']:
        print('| %s | %s | %s |' % (x['tag'], ' | '.join('%s:%s' % (c, f(v['H_db'])) for c, v in sorted(x['m'].items())),
                                     x['nonzero16']))

r = J('sum_osc')
if r:
    print('\n## sum (osc, OscChan 99), coherent H dB re the oscillator')
    single = {c: H(r['rows'][0]['m'], c) for c in (33, 34, 35)}
    for x in r['rows']:
        g6 = x['level']['6'] if '6' in x['level'] else x['level'].get(6)
        on = x['on']
        n5 = 1 if ('5' in on or 5 in on) else 0
        n6 = 1 if ('6' in on or 6 in on) else 0
        pred_gain = db(n5 * 1.0 + n6 * g6)
        print('| %s | ' % x['tag'] + ' | '.join('%d:%s (pred %s)' % (c, f(H(x['m'], c)), f(single[c] + pred_gain))
                                               for c in (33, 34, 35)) + ' |')

for mode in ('analog', 'osc'):
    r = J('eqdyn_' + mode)
    if not r:
        continue
    print('\n## EQ/dyn, %s' % mode)
    for x in r['rows']:
        if x['what'] == 'eq':
            print('| EQ %g Hz | pred %+.3f | strip %+.4f | MAIN L %+.4f |' % (x['f'], x['pred_db'], x['meas_strip_db'], x['meas_main_db']))
        else:
            env = x['envelope_dbfs']
            pred_env = -(env + 20.0) * (1 - 1 / x['ratio']) if env > -20 else 0.0
            print('| COMP in %.2f dBFS pk, ratio %g | pred(peak) %+.3f | pred(envelope %.2f) %+.3f | gain word %+.3f | strip %+.3f | MAIN L %+.3f |' % (
                x['in_pk_dbfs'], x['ratio'], x['pred_gr_db'], env, pred_env, x['comp_gain_word_db'],
                x['meas_gr_strip_db'], x['meas_gr_main_db']))
