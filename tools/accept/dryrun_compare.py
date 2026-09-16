#!/usr/bin/env python3
"""dryrun_compare.py -- S66 gate 3: do the generated tables reproduce the hand tables? (markdown to stdout)

Generated = MW/D24/DSP/s66/results/{factory,full}/*.json (dsp4_accept.py on the replay maps).
Hand = the tables the sessions published from the same data, read from the files those sessions wrote:
  S61  MW/D24/DSP/s61/results.json            chirp gain/response/latency/polarity, THD+N code 0 (S60/S61 table)
  S63  MW/D24/DSP/s63/data/s63_thd_J25.json   THD h2..h10 code 63, 32 averaged;  s63_results.json  silent A1 summary
  S57  MW/D24/DSP/s57/data/s57_table.jsonl    MIC 5 EIN (150 ohm) g1;  s57_outnoise.out  AUX 1 output noise
  S60  MW/D24/DSP/s60/data/s60_t7.jsonl       10 kHz crosstalk worst neighbour
  S55  MW/D24/DSP/s55/channels.md             per-channel T2/T3/T4b/T5/T8 row;  trim-table.md  worst deviation + flags
  S65  findings S65-3 table (the prove rows' own err/oct/cold as the session printed them)
Tolerances are the printing precision of the hand table (a 2-decimal table cannot be matched closer than 0.005) or
the noise the session stated; every comparison is listed, none is dropped."""
import csv, json, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
D = os.path.join(ROOT, 'MW', 'D24', 'DSP')
RES = os.path.join(D, 's66', 'results')
rows = []


def res(mode, fid):
    p = os.path.join(RES, mode, fid + '.json')
    return json.load(open(p)) if os.path.exists(p) else None


def test(r, tid):
    return next((t for t in r['tests'] if t['test'] == tid), None)


def cmp(path, what, hand, gen, tol, src):
    if gen is None or hand is None:
        rows.append((path, what, hand, gen, None, tol, 'MISSING', src))
        return
    if isinstance(hand, str):
        rows.append((path, what, hand, gen, None, tol, 'ok' if hand == gen else 'DIFF', src))
        return
    d = gen - hand
    rows.append((path, what, hand, gen, d, tol, 'ok' if abs(d) <= tol + 1e-9 else 'DIFF', src))


def num(s):
    return float(s.replace('−', '-').replace('+', ''))


def main():
    inputs = {r['xlr']: r for r in csv.DictReader(open(os.path.join(ROOT, 'defs/products/d24/inputs.csv')))}
    fid = lambda x: 'd24-in-mic%02d' % int(inputs[x]['panel'].split()[-1])

    # ---- MIC 5: S61 / S60 / S63 / S57
    s61 = json.load(open(os.path.join(D, 's61/results.json')))
    f = res('factory', 'd24-in-mic05')
    t1 = {r['code']: r['gain_db'] for r in test(f, 'T1')['detail']['rows']}
    for c in (0, 1, 2, 4, 8, 16, 32, 63):
        cmp('MIC 5 factory', 'T1 gain code %d (chirp)' % c, s61['codes'][str(c)]['gain_1k'], t1[c], 0.0005, 'S61 results.json')
    t2 = test(f, 'T2')['detail']['response']
    for c in (0, 63):
        hand = dict(s61['codes'][str(c)]['response'])
        for hz in (20, 50, 100, 10000, 20000):
            cmp('MIC 5 factory', 'T2 code %d %d Hz' % (c, hz), hand[hz], t2[str(c)][str(hz)], 0.0005, 'S61 results.json')
    lat = test(f, 'T8')['detail']['latency_samples']
    cmp('MIC 5 factory', 'T8 latency 1-2 kHz, samples', s61['codes']['0']['latency_gd12'], lat, 0.0005, 'S61 results.json')
    cmp('MIC 5 factory', 'T5 polarity', 'inverted' if s61['codes']['0']['polarity'] < 0 else 'in phase',
        test(f, 'T5')['summary'].split()[0], 0, 'S61 results.json')
    t3 = test(f, 'T3')['detail']
    cmp('MIC 5 factory', 'T3 THD+N code 0, dB', s61['thdn_0']['thdn_db'], t3['thdn_min']['thdn_db'], 0.005, 'S61 results.json')
    thd = json.load(open(os.path.join(D, 's63/data/s63_thd_J25.json')))['63']
    cmp('MIC 5 factory', 'T3 THD code 63 (32 averaged), dB', thd['thd_db'], t3['thd_max_avg']['thd_db'], 0.005, 'S63 s63_thd_J25.json')
    cmp('MIC 5 factory', 'T3 THD code 63 single capture, dB (S60-2 printed -60.92 on the S60 capture)', -60.92,
        t3['thd_max_single']['thd_db'], 0.1, 'S60-2 (different capture: S61 vs S60)')
    g1 = [json.loads(l) for l in open(os.path.join(D, 's57/data/s57_table.jsonl')) if '"tag": "g1"' in l][0]
    t4b = test(f, 'T4b')['detail']['codes']['63']
    cmp('MIC 5 factory', 'T4b noise lane 20-20k, dBFS', g1['aud'], t4b['lane_dbfs']['20-20k'], 0.0005, 'S57 s57_table.jsonl g1')
    cmp('MIC 5 factory', 'T4b noise lane A, dBFS', g1['aw'], t4b['lane_dbfs']['A'], 0.0005, 'S57 s57_table.jsonl g1')
    # the dBu figure divides by THIS run's T1 gain at code 63 (the S61 chirp, 58.743) where S57 used S54's tone (58.717):
    # the S61 code-63 chirp carries the loop source's noise (+0.026 dB, S61-3), so the two differ by that and no more
    cmp('MIC 5 factory', 'T4b EIN 20-20k, dBu (divisor: run chirp G63 vs S54 tone G63)', g1['aud_dbu'], t4b['dbu']['20-20k'], 0.03, 'S57 s57_table.jsonl g1')
    cmp('MIC 5 factory', 'T4b EIN A, dBu (divisor: run chirp G63 vs S54 tone G63)', g1['aw_dbu'], t4b['dbu']['A'], 0.03, 'S57 s57_table.jsonl g1')
    t7 = [json.loads(l) for l in open(os.path.join(D, 's60/data/s60_t7.jsonl')) if 'summary' in l][0]
    cmp('MIC 5 factory', 'T7 worst neighbour 10 kHz, dB', t7['worst'][1], max(test(f, 'T7')['detail']['neighbours'].values()), 0.0005, 'S60 s60_t7.jsonl')
    full = res('full', 'd24-in-mic05')
    s63 = json.load(open(os.path.join(D, 's63/data/s63_results.json')))['J25']['summary']['silent']
    a1 = test(full, 'A1')['detail']['rows']
    cmp('MIC 5 full', 'A1 silent transitions', s63['n'], len(a1), 0, 'S63 s63_results.json')
    cmp('MIC 5 full', 'A1 silent PASS', s63['pass'], sum(1 for r in a1 if not r['flag']), 0, 'S63 s63_results.json')
    cmp('MIC 5 full', 'A1 silent pump flags', s63['flag_pump'], sum(1 for r in a1 if 'pump' in r['flag']), 0, 'S63 s63_results.json')
    worst = max((r for r in a1 if r['detected']), key=lambda r: r['peak_dbfs'])
    cmp('MIC 5 full', 'A1 worst detected peak, dBFS', float(s63['worst'].split()[0]), worst['peak_dbfs'], 0.05, 'S63 s63_results.json (1 decimal)')

    # ---- the S55 channels: channels.md rows + trim-table.md
    md = open(os.path.join(D, 's55/channels.md')).read()
    trim = open(os.path.join(D, 's55/trim-table.md')).read()
    worst = dict((m.group(1), (float(m.group(2)), int(m.group(3))))
                 for m in re.finditer(r'(J\d+) ([+-]\d+\.\d+) dB \(code (\d+)\)', trim.split('Worst per-channel deviation')[1].split('\n')[0]))
    flagged = re.findall(r'(J\d+) \(MIC \d+\): -?\d', trim.split('Deviation flags')[1].split('\n')[0])
    for line in md.split('\n'):
        cells = [c.strip() for c in line.strip('|').split('|')]
        if len(cells) < 15 or not re.match(r'J\d+$', cells[0]) or cells[0] == 'J25':
            continue
        xlr = cells[0]
        p = '%s %s' % (inputs[xlr]['panel'], xlr)
        f, fu = res('factory', fid(xlr)), res('full', fid(xlr))
        if not f:
            rows.append((p, 'result', None, None, None, 0, 'MISSING', ''))
            continue
        r2 = test(f, 'T2')['detail']['response']
        h0, h63 = [num(x) for x in cells[7].split('/')]
        cmp(p, 'T2 20 Hz code 0', h0, r2['0']['20'], 0.005, 'S55 channels.md')
        cmp(p, 'T2 20 Hz code 63', h63, r2['63']['20'], 0.005, 'S55 channels.md')
        c63 = num(cells[9].split('dB')[0])
        cmp(p, 'T3 THD+N code 63 @ -3 dBFS (noise-limited)', c63, test(f, 'T3')['detail']['thdn_max_meter']['thdn_db'], 0.005, 'S55 channels.md')
        e, ea = [num(x) for x in cells[11].split('/')]
        d4 = test(f, 'T4b')['detail']['codes']['63']['dbu']
        cmp(p, 'T4b EIN 20-20k dBu', e, d4['20-20k'], 0.05, 'S55 channels.md (1 decimal)')
        cmp(p, 'T4b EIN A dBu', ea, d4['A'], 0.05, 'S55 channels.md (1 decimal)')
        cmp(p, 'T5 polarity', cells[13], test(f, 'T5')['summary'].split()[0], 0, 'S55 channels.md')
        cmp(p, 'T8 latency samples', num(cells[14]), test(f, 'T8')['detail']['latency_samples'], 0.005, 'S55 channels.md (2 decimals)')
        # law.csv carries 3 decimals and the universal mean is rounded to 3 again: 0.002 dB is the rounding, and the
        # comparison is made AT the hand table's worst code (two codes within the rounding can swap places)
        dv = {r['code']: r['dev_db'] for r in test(fu, 'T1')['detail']['rows']}
        cmp(p, 'T1 deviation from the universal mean at the hand worst code %d, dB' % worst[xlr][1], worst[xlr][0], dv[worst[xlr][1]],
            0.002, 'S55 trim-table.md (3-decimal law)')
        cmp(p, 'T1 stage flag (> 0.5 dB)', 'FLAG' if xlr in flagged else 'PASS', test(fu, 'T1')['verdict'], 0, 'S55 trim-table.md flags')
    # MIC 5's own worst deviation (S54 sweep in the same table)
    dv = {r['code']: r['dev_db'] for r in test(full, 'T1')['detail']['rows']}
    cmp('MIC 5 full', 'T1 deviation from the universal mean at the hand worst code %d, dB' % worst['J25'][1], worst['J25'][0],
        dv[worst['J25'][1]], 0.002, 'S55 trim-table.md (3-decimal law)')

    # ---- AUX 1 output noise: S57
    o = test(res('factory', 'd24-out-aux01'), 'T4')['detail']
    out = open(os.path.join(D, 's57/data/s57_outnoise.out')).read()
    u = re.search(r'20 Hz-20 kHz unweighted\s+\S+ dBFS\s+=\s+\S+ /\s+(\S+) dBu\s+corrected\s+\S+ dBFS =\s+\S+ /\s+(\S+) dBu', out)
    a = re.search(r'20 Hz-20 kHz A-weighted\s+\S+ dBFS\s+=\s+\S+ /\s+(\S+) dBu\s+corrected\s+\S+ dBFS =\s+\S+ /\s+(\S+) dBu', out)
    cmp('AUX 1 out', 'T4 20-20k dBu', float(u.group(1)), o['dbu']['20-20k'], 0.015, 'S57 s57_outnoise.out')
    cmp('AUX 1 out', 'T4 A dBu', float(a.group(1)), o['dbu']['A'], 0.015, 'S57 s57_outnoise.out')
    cmp('AUX 1 out', 'T4 20-20k dBu floor-corrected', float(u.group(2)), o['dbu_floor_corrected']['20-20k'], 0.015, 'S57 s57_outnoise.out')
    cmp('AUX 1 out', 'T4 A dBu floor-corrected', float(a.group(2)), o['dbu_floor_corrected']['A'], 0.015, 'S57 s57_outnoise.out')

    # ---- cue/RTA node: the S65-3 table as printed
    n = res('factory', 'd24-node-cue-rta')
    hand = [('A afl pan L 63 Hz', -0.072, 48.38), ('A afl pan L 1000 Hz', 0.009, 48.58), ('A afl pan L 8000 Hz', 0.001, 40.74),
            ('A afl pan R 1000 Hz', -0.001, 48.57), ('B pfl 1000 Hz', -0.001, 48.57),
            ('C source main L/R, pan L 1000 Hz', -0.001, 48.57), ('C source aux 1 1000 Hz', -0.001, 48.57)]
    genrows = test(n, 'T1')['detail']['rows']
    for tag, err, octv in hand:
        g = next(r for r in genrows if r.startswith(tag + ' '))
        m = re.search(r' ([+-]\d+\.\d+) dB, octave >= (\d+\.\d+)', g)
        cmp('cue/RTA node', '%s error dB' % tag, err, float(m.group(1)), 0.0005, 'S65-3 table')
        cmp('cue/RTA node', '%s octave down dB' % tag, octv, float(m.group(2)), 0.005, 'S65-3 table')
    cmp('cue/RTA node', 'verdict', 'PASS', n['verdict'], 0, 'S65-3 (every row within 0.1 dB, octave >= 40.7)')

    ok = sum(1 for r in rows if r[6] == 'ok')
    print('# S66 dry run: generated tables against the hand tables\n')
    print('**%d of %d comparisons agree within tolerance** (%d DIFF, %d MISSING). Generated by `tools/accept/dryrun_compare.py`; '
          'tolerance = the hand table\'s printing precision unless stated.\n' % (ok, len(rows), sum(1 for r in rows if r[6] == 'DIFF'),
                                                                                 sum(1 for r in rows if r[6] == 'MISSING')))
    print('| path | quantity | hand | generated | Δ | tol | | hand source |')
    print('|---|---|---:|---:|---:|---:|---|---|')
    fmt = lambda v: '—' if v is None else (v if isinstance(v, str) else '%.4f' % v)
    for p, w, h, g, d, t, s, src in rows:
        print('| %s | %s | %s | %s | %s | %s | %s | %s |' % (p, w, fmt(h), fmt(g), '' if d is None else '%+.4f' % d, t, s, src))
    return 0 if ok == len(rows) else 1


if __name__ == '__main__':
    sys.exit(main())
