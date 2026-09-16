#!/usr/bin/env python3
"""replay_d24_recorded.py [--out MW/D24/DSP/s66/replay] -- replay maps for dsp4_accept.py from the D24 sessions'
recorded data (S66 gate 3). One map per fixture that has any recorded data; every key points at the files a live run
would have captured, or at the recorded result a session measured (named, with its method). Nothing is re-measured
or re-typed: captures stay where the sessions committed them.

  MIC 5 (J25)      S61 chirps + reference, S61 THD+N tone captures, S63 averaged THD and span captures, S57 150 ohm
                   captures, S60 10 kHz crosstalk, S54/S55 64-code law
  15 channels      S55: law.csv (64-code tone gain), the loop json (T2 tone response, T3 ThdResult, T5/T8 phase fit),
                   the 150 ohm captures
  AUX 1 output     S57 output-noise captures (looped into MIC 5 at code 0)
  cue/RTA node     S65 proof rows"""
import argparse, ast, csv, glob, json, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
D = 'MW/D24/DSP'


def rel(p):
    return os.path.relpath(p, ROOT)


def value(v, frm, method=None):
    o = {'kind': 'value', 'value': v, 'from': frm}
    if method:
        o['method'] = method
    return o


def capture(files, method='capture'):
    return {'kind': 'capture', 'files': [rel(f) for f in files], 'method': method}


def none(why):
    return {'kind': 'none', 'why': why}


def lit(s):
    if not isinstance(s, str):
        return s
    return ast.literal_eval(s.replace('-inf', '-1e999').replace('inf', '1e999').replace('nan', 'None'))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default=os.path.join(ROOT, D, 's66', 'replay'))
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    inputs = {r['xlr']: r for r in csv.DictReader(open(os.path.join(ROOT, 'defs/products/d24/inputs.csv')))}
    law = {}
    for r in csv.DictReader(open(os.path.join(ROOT, D, 's55/law.csv'))):
        law.setdefault(r['channel'].split()[0], {})[int(r['code'])] = float(r['loop_gain_db'])
    maps = {}

    def fid(xlr):
        return 'd24-in-mic%02d' % int(inputs[xlr]['panel'].split()[-1])

    def law_items(xlr, frm):
        return {'gain:c%02d' % c: value(g, frm, 'TEST_MEAS coherent gain, 1 kHz tone') for c, g in law[xlr].items()}

    # ---- MIC 5 (J25)
    S61 = os.path.join(ROOT, D, 's61/data')
    it = {'ref': capture([os.path.join(S61, 'ref_strip6_m20.json')], 'S61 chirp reference, strip 6 post-fader')}
    for c in (0, 1, 2, 4, 8, 16, 32, 63):
        fs = sorted(glob.glob(os.path.join(S61, 'chirp_c%02d_[12].json' % c)))
        it['chirp:c%02d' % c] = capture(fs, 'S61 chirp (bulk read)')
    it.update(law_items('J25', rel(os.path.join(ROOT, D, 's55/law.csv')) + ' (J25 from S54 s54_t1all)'))
    it['tone:c00:m3'] = capture([os.path.join(S61, 'thdn_c00.json')], 'S61 THD+N tone capture')
    it['tone:c63:m3'] = capture([os.path.join(S61, 'thdn_c63.json')], 'S61 THD+N tone capture')
    thd = json.load(open(os.path.join(ROOT, D, 's63/data/s63_thd_J25.json')))['63']
    it['thd_avg:c63'] = value({'thd_db': thd['thd_db'], 'n': thd['n'], 'floor_dbc': thd['floor_bin_avg_dbc']},
                              rel(os.path.join(ROOT, D, 's63/data/s63_thd_J25.json')), 'S63 coherent average, h2..h10')
    S57 = os.path.join(ROOT, D, 's57/data')
    it['silence150:c63'] = capture(sorted(glob.glob(os.path.join(S57, 'g1_[0-9][0-9].json'))), 'S57 150 ohm, code 63')
    it['silence150:c00'] = capture(sorted(glob.glob(os.path.join(S57, 'f150c0_[0-9][0-9].json'))), 'S57 150 ohm, code 0')
    t7 = [json.loads(l) for l in open(os.path.join(ROOT, D, 's60/data/s60_t7.jsonl')) if '"t7_10k_summary"' in l][0]
    it['xtalk10k'] = value({'neighbours': {str(s): d for s, d in t7['rows']}, 'control_db': t7['control_db']},
                           rel(os.path.join(ROOT, D, 's60/data/s60_t7.jsonl')), 'S60 coherent 10 kHz, code 2, lane -6 dBFS pk')
    it['mute'] = none("no DSP strip-mute measurement exists: S54's T6 toggled the 595 bit 0, which is the PHANTOM SHUNT "
                      "(PW 09-16), not a mute")
    it['floor:c00'] = none('the tone-off floors at the factory codes were read by meter in S54 on the loop source, not kept as captures')
    it['artefacts'] = {'kind': 's63', 'dir': D + '/s63/data', 'xlr': 'J25'}
    maps[fid('J25')] = {'what': 'MIC 5 / J25: S61 chirps + tones, S63 THD avg + spans, S57 150 ohm, S60 T7, S54/S55 law',
                        'items': it}

    # ---- the S55 channels
    S55 = os.path.join(ROOT, D, 's55/data')
    for f in sorted(glob.glob(os.path.join(S55, 'J*_loop.json'))):
        r = json.load(open(f))
        xlr = r['xlr']
        if xlr not in law:
            continue
        it = law_items(xlr, rel(os.path.join(ROOT, D, 's55/law.csv')))
        t2 = lit(r['t2'])
        for code in ('0', '63'):
            it['resp:c%02d' % int(code)] = value({str(p['f']): p['re1k'] for p in t2[code]}, rel(f) + ' t2', 'tone, coherent')
        for row in lit(r['t3']):
            if row['target'] == -3.0:
                it['thdn:c%02d:m3' % row['code']] = value(row['thd'], rel(f) + ' t3', 'TEST_MEAS ThdResult (THD+N)')
        it['thdn_vs_level'] = value([{'code': x['code'], 'lane_dbfs': x['target'], 'thdn_db': x['thd']} for x in lit(r['t3'])],
                                    rel(f) + ' t3')
        fit = lit(r['t58'])
        it['phase'] = value({'polarity': -1 if fit['polarity'] == 'INVERTED' else 1,
                             'latency_gd12': fit['fits'][0]['delay_samples']}, rel(f) + ' t58', 'tone phase fit 1-2 kHz')
        for code in (63, 0):
            fs = sorted(glob.glob(os.path.join(S55, '%s_c%02d_*.json' % (xlr, code))))
            if fs:
                it['silence150:c%02d' % code] = capture(fs, 'S55 150 ohm')
        it['xtalk10k'] = none('S55 did not measure crosstalk (S60 did, on MIC 5 only)')
        it['mute'] = none('no DSP strip-mute measurement exists')
        it['artefacts'] = none('S63 ran MIC 5 only; the WATCH path for the other channels was not exercised')
        it['thd_avg:c63'] = none('THD-only at max gain was measured on MIC 5 only (S63)')
        maps[fid(xlr)] = {'what': '%s / %s: S55 (tone law, T2/T3/T5/T8 by TEST_MEAS, 150 ohm captures)' % (inputs[xlr]['panel'], xlr),
                          'items': it}

    # ---- AUX 1 output
    maps['d24-out-aux01'] = {'what': 'AUX 1 / J45 output noise: S57, looped into MIC 5 at code 0', 'items': {
        'outnoise': capture(sorted(glob.glob(os.path.join(S57, 'aux1n_[0-9][0-9].json'))), 'S57 output noise via MIC 5 code 0'),
        'refgain:c00': value(law['J25'][0], rel(os.path.join(ROOT, D, 's55/law.csv')) + ' J25 code 0'),
        'mute': none('no output mute measurement exists'),
        'xtalk10k': none('no output crosstalk measurement exists')}}

    # ---- the cue/RTA node
    rows = [json.loads(l) for l in open(os.path.join(ROOT, D, 's65/data/s65_prove.jsonl')) if '"ev": "row"' in l]
    maps['d24-node-cue-rta'] = {'what': 'cue bus + RTA: S65 proof rows through the parameter link', 'items': {
        'node_rows': value([{k: x.get(k) for k in ('case', 'f', 'band', 'hot_db', 'err_db', 'oct_db', 'cold_max_db', 'cold_same_band_db')} for x in rows],
                           rel(os.path.join(ROOT, D, 's65/data/s65_prove.jsonl')), 'Rta001MtrL/R band reads, median of 3')}}

    for name, m in sorted(maps.items()):
        m['base'] = ''
        m['fixture'] = name
        with open(os.path.join(a.out, name + '.json'), 'w') as f:
            json.dump(m, f, indent=1, sort_keys=True)
            f.write('\n')
    print('%d replay maps -> %s' % (len(maps), rel(a.out)))


if __name__ == '__main__':
    main(sys.argv[1:])
