#!/usr/bin/env python3
"""dsp4_accept.py -- the closed-loop audio acceptance runner (S66): a generated fixture in, a per-path pass/flag out.

    dsp4_accept.py run    --fixture FX.json --mode factory|full --unit MW-D24-2 --source replay:MAP.json|live
                          [--limits tools/accept/limits.csv] [--out DIR]
    dsp4_accept.py report DIR [DIR ...]           one table per unit/mode from the per-path results
    dsp4_accept.py plan   --manifest MANIFEST.json [--mode factory|full]   projected time per path and per unit

WHAT IT DOES. A fixture (tools/accept/gen_accept_fixtures.py, from defs) names the path, the cells that make it live
and the tests of the standard audio test set that apply (mx26 docs/spec-audio-test-set.md). The runner asks a SOURCE
for each measurement the selected mode needs, analyses it with the same instruments the hand sessions used
(dsp4_chirp.analyse for the chirp: gain, response, latency, polarity; dsp4_fft for THD+N/THD and the band-limited
noise), and judges every number against ONE limits file (provisional; PW tunes it, nothing is hard-coded here).
Verdicts: PASS, FLAG (a number outside the provisional limit), NO DATA (the source had nothing for it -- never a
pass), INFO (reported, no limit). A path is FLAG if any test flags, INCOMPLETE if a test the mode requires has no
data, else PASS.

MODES (the dispatch): factory = T1 at the eight codes 0 1 2 4 8 16 32 63 (T2 at min/max, T5, T8 fall out of the
same chirps), T3's two points (THD+N at min gain, THD at max gain), T4b at full gain only, T7 at 10 kHz, and the
output noise on output paths; full = everything the battery has for the path type.

SOURCES. `live` drives the unit through the bench rig (s61lib API: chain, chirp, tone, capture; cells through the
app's MxDat path). NOT EXERCISED: S66 was a desk session. `replay:MAP.json` answers from recorded data: each key
names capture files (analysed here exactly as a live capture would be) or a recorded result (a tone/meter figure a
session measured; reported with its provenance, and the method is named in the result). Keys the runner asks:

  ref                    the chirp's reference (the donor strip's post-fader period)       capture
  chirp:cNN              the path's chirp at code NN (1 or 2 captures; 2 gives the SNR)   capture
  gain:cNN               loop gain at 1 kHz, dB (tone/meter method)                       value
  resp:cNN               {Hz: dB re 1 kHz} (tone method)                                  value
  phase                  {polarity: +1|-1, latency_gd12: samples} (tone method)          value
  tone:cNN:m3            1 kHz at lane -3 dBFS pk                                          capture
  thdn:cNN:m3            THD+N dB at lane -3 dBFS pk (meter)                               value
  thd_avg:cNN            {thd_db, n} THD h2..h10 from averaged captures                    value
  thdn_vs_level          [{lane_dbfs, thd_db}] at min gain                                  value
  floor:cNN              tone-off floor dBFS at code NN (loop source)                     value
  silence150:cNN         tone off, the EIN source (150 ohm)                                capture
  outnoise               tone off, the output under test looped into the reference input  capture
  refgain:c00            the reference input's loop gain at code 0                         value
  mute                   {open_dbfs, muted_dbfs, what}                                     value
  xtalk10k               {neighbours: {strip: dB}, control_db}                              value
  artefacts              {kind: s63, dir, xlr}                                              s63 captures
  node_rows              [the S65 prove rows]                                                value
A key the map declares as {"kind": "none", "why": ...} reports NO DATA with that reason."""
import argparse, csv, glob, json, lzma, math, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import dsp4_chirp as CH          # noqa: E402
import dsp4_fft as FFT           # noqa: E402

FS = 48000.0
FACTORY = 'factory'


def pct(db):
    return 100.0 * 10 ** (db / 20.0)


def dbpct(db):
    return '%.2f dB = %.4f %%' % (db, pct(db)) if db is not None and math.isfinite(db) else '—'


def emean(v):
    return 10 * math.log10(sum(10 ** (x / 10) for x in v) / len(v))


def q428(cap):
    return [(v - (1 << 32) if v & 0x80000000 else v) / float(1 << 28) for v in cap['samples']]


def read_csv(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(l for l in f if not l.startswith('#')))


def load_limits(path):
    out = {}
    for r in read_csv(path):
        v = r['value']
        try:
            out[r['key']] = float(v)
        except ValueError:
            out[r['key']] = v
    return out


def load_unit(path, unit):
    for r in read_csv(path):
        if r['unit'] == unit:
            for k in ('dac_fs_dbu', 'loop_latency_samples', 'adc_floor_dbfs'):
                r[k] = float(r[k])
            return r
    raise SystemExit('unit %s not in %s' % (unit, path))


# ------------------------------------------------------------------------------------------------ sources
class ReplaySource:
    def __init__(self, path):
        self.path = path
        self.m = json.load(open(path))
        self.base = os.path.join(ROOT, self.m.get('base', ''))
        self.items = self.m['items']
        self._cache = {}

    def describe(self):
        return 'replay %s (%s)' % (os.path.relpath(self.path, ROOT), self.m.get('what', ''))

    def get(self, key):
        spec = self.items.get(key)
        if spec is None:
            return None
        k = spec['kind']
        if k == 'none':
            return {'none': spec['why']}
        if k == 'value':
            return {'value': spec['value'], 'from': spec.get('from'), 'method': spec.get('method')}
        if k == 'capture':
            if key not in self._cache:
                caps = []
                for f in spec['files']:
                    c = json.load(open(os.path.join(self.base, f)))
                    c['_file'] = f
                    caps.append(c)
                self._cache[key] = caps
            return {'captures': self._cache[key], 'from': spec['files'], 'extra': spec.get('extra', {}),
                    'method': spec.get('method', 'capture')}
        if k == 's63':
            return {'s63': spec}
        raise SystemExit('replay %s: unknown kind %s' % (key, k))


class LiveSource:
    """The bench rig. NOT EXERCISED on the part (S66 was a desk session): the sequence is S60/S61's, and the first
    live run must be watched. The chain and the stimulus go through the s61lib rig (RIG_DIR, default /home/app/s61).
    Cells are MxDat CODES (the Neutral column), which the host converts to wire values through the wire table; this
    repo has no verified host command that writes a cell by name and code, so the runner does not invent one: set
    ACCEPT_SET_CMD to a template such as '<cmd> {cell} {value}' once the app's path is confirmed, or it refuses."""

    def __init__(self, fixture, unit):
        rig = os.environ.get('RIG_DIR', '/home/app/s61')
        sys.path.insert(0, rig)
        import s61lib as S                                # noqa: E402  (bench only)
        self.S, self.fx, self.unit = S, fixture, unit
        self.R = S.T.Rig(os.path.join(rig, 'accept.jsonl'))
        self.applied = False
        self.G = {}

    def describe(self):
        return 'live (s61lib rig)'

    def _apply(self):
        if self.applied:
            return
        import shlex, subprocess
        tpl = os.environ.get('ACCEPT_SET_CMD')
        if not tpl:
            raise SystemExit('live: ACCEPT_SET_CMD is not set -- no verified host command writes a cell by MxDat code '
                             '(see LiveSource); refusing to run with the fixture cells unapplied')
        for c in self.fx.get('stimulus', {}).get('cells', []) + self.fx['set']:
            subprocess.run(shlex.split(tpl.format(cell=c['cell'], value=c['value'])), check=True)
        self.applied = True

    def _cap(self, meas, tag, periods=1.2):
        c = self.S.capture(self.R, 16384, meas, tag, wait_periods=periods)
        return c

    def get(self, key):
        self._apply()
        S, R = self.S, self.R
        strip = self.fx['path']['strip'] if self.fx['type'] == 'input' else self.fx['path']['measure']['strip']
        donor = self.fx['stimulus']['donor_strip']
        parts = key.split(':')
        if key == 'ref':
            R.chain(0)
            S.chirp(R, -20.0, 0, chan=donor)
            return {'captures': [self._cap(donor, 'accept_ref')], 'from': ['live'], 'extra': {}}
        if parts[0] == 'chirp':
            code = int(parts[1][1:])
            level = -10.0 - self.G.get(code, 5.6 + 53.1 * (code > 0))
            S.chirp(R, level, 0, chan=donor)              # LEVEL FIRST, then the code (S60-3)
            R.chain(code)
            time.sleep(1.0)
            caps = [self._cap(strip, 'accept_chirp_c%02d_%d' % (code, k)) for k in ((1, 2) if code in (0, 63) else (1,))]
            for c in caps:
                c['osc_dbfs_pk'] = level
            return {'captures': caps, 'from': ['live'], 'extra': {}}
        if parts[0] == 'tone':
            code = int(parts[1][1:])
            level = -3.0 - self.G.get(code, 5.6)
            S.tone(R, 1000.0, level, chan=donor)
            R.chain(code)
            time.sleep(1.3)
            return {'captures': [self._cap(strip, 'accept_tone_c%02d' % code, periods=0.0)], 'from': ['live'], 'extra': {}}
        if parts[0] in ('silence150', 'outnoise'):
            code = int(parts[1][1:]) if len(parts) > 1 else 0
            R.chain(code)
            R.wv(S.A_SWEEPON, 0)
            R.osc(on=False, chan=donor)
            time.sleep(1.3)
            return {'captures': [self._cap(strip, 'accept_%s' % key.replace(':', '_'), periods=0.0)], 'from': ['live'],
                    'extra': {}}
        return None                                       # meter-method keys: not wired live (the fast form is used)


# ------------------------------------------------------------------------------------------------ the tests
class Run:
    def __init__(self, fx, mode, src, limits, unit):
        self.fx, self.mode, self.src, self.L, self.u = fx, mode, src, limits, unit
        self.tests = {t['test']: t for t in fx['tests']}
        self.res = []
        self.G = {}               # code -> loop gain dB, from T1
        self.T1_method = None
        self.chirp = {}           # code -> analyse() result

    def add(self, test, verdict, summary, **detail):
        self.res.append({'test': test, 'verdict': verdict, 'summary': summary, 'detail': detail})

    def wanted(self, tid):
        t = self.tests.get(tid)
        if not t:
            return None
        return t if (t['factory'] if self.mode == FACTORY else t['full']) else None

    # ---- chirp analysis, cached
    def chirp_at(self, code):
        if code in self.chirp:
            return self.chirp[code]
        ref, cap = self.src.get('ref'), self.src.get('chirp:c%02d' % code)
        if not ref or not cap or 'captures' not in ref or 'captures' not in cap:
            self.chirp[code] = None
            return None
        rc = ref['captures'][0]
        y = q428(cap['captures'][0])
        y2 = q428(cap['captures'][1]) if len(cap['captures']) > 1 else None
        c0 = cap['captures'][0]
        lvl = c0.get('osc_level') or 10 ** (c0['osc_dbfs_pk'] / 20.0)
        x = [v * lvl / rc['osc_level'] for v in q428(rc)]
        r = CH.analyse(y, x, 0, points=CH.POINTS if not self.tests.get('T2') else self.tests['T2']['points_hz'], y2=y2)
        r['files'] = cap['from']
        r['overruns'] = sum(c.get('overruns', 0) for c in cap['captures'])
        self.chirp[code] = r
        return r

    # ---- T1
    def t1(self):
        t = self.wanted('T1')
        if not t:
            return
        if self.fx['type'] != 'input':
            return self.add('T1', 'NO DATA', 'output/node T1 not in the recorded sets')
        codes = t['codes_factory'] if self.mode == FACTORY else t['codes_full']
        chirps = {c: self.chirp_at(c) for c in codes}
        vals = {c: self.src.get('gain:c%02d' % c) for c in codes}
        if all(chirps.values()):
            G = {c: chirps[c]['gain_1k_db'] for c in codes}
            method = 'chirp (dsp4_chirp, S60/S61 fast form)'
            prov = sorted({f for c in codes for f in chirps[c]['files']})
        elif all(v and 'value' in v for v in vals.values()):
            G = {c: float(vals[c]['value']) for c in codes}
            method = 'recorded tone/meter gain (%s)' % (vals[codes[0]].get('method') or 'TEST_MEAS coherent')
            prov = sorted({v['from'] for v in vals.values()})
        else:
            have = [c for c in codes if chirps[c] or (vals[c] and 'value' in vals[c])]
            return self.add('T1', 'NO DATA', 'gain at %d of %d codes' % (len(have), len(codes)))
        self.G.update(G)
        self.T1_method = method
        ref = t.get('universal_hw_gain_db') or {}
        tol = self.L['t1_stage_tol_db']
        rows, flags = [], []
        for c in codes:
            hw = G[c] - G[0]
            mean = ref.get(str(c))
            dev = hw - mean if mean is not None else None
            rows.append({'code': c, 'gain_db': round(G[c], 3), 'hw_re_c0_db': round(hw, 3),
                         'universal_db': mean, 'dev_db': None if dev is None else round(dev, 3)})
            if dev is not None and c not in (0, 63) and abs(dev) > tol:   # 63 is judged against the stage sum below
                flags.append('code %d %+.3f dB off the universal %.3f' % (c, dev, mean))
        # code 63 against the sum of its stages (linear-additive, S54-3)
        pred = None
        stages = [1, 2, 4, 8, 16, 32]
        if all(s in G for s in stages) and 63 in G:
            lin = lambda d: 10 ** (d / 20.0)
            p = lin(G[0]) + sum(lin(G[s]) - lin(G[0]) for s in stages)
            pred = 20 * math.log10(p)
            if abs(G[63] - pred) > self.L['t1_c63_sum_tol_db']:
                flags.append('code 63 %+.3f dB off the stage sum' % (G[63] - pred))
        mono = None
        if self.mode != FACTORY and len(codes) == 64:
            bad = [(c, c & ~(1 << b)) for c in range(1, 64) for b in range(6) if c >> b & 1 and G[c] <= G[c & ~(1 << b)]]
            mono = not bad
            if bad:
                flags.append('not monotonic: %s' % bad[:4])
            steps = sorted(G[c] - G[c - 1] for c in range(1, 64))
        s = 'code 0 %+.3f dB, code 63 %+.3f dB (range %.2f dB)' % (G[0], G[max(codes)], G[max(codes)] - G[0])
        if pred is not None:
            s += '; code 63 vs stage sum %+.3f dB' % (G[63] - pred)
        worst = max((r for r in rows if r['dev_db'] is not None and r['code'] not in (0, 63)), key=lambda r: abs(r['dev_db']), default=None)
        if worst:
            s += '; worst stage vs universal %+.3f dB (code %d)' % (worst['dev_db'], worst['code'])
        if mono is not None:
            s += '; monotonic %s' % ('yes' if mono else 'NO')
        self.add('T1', 'FLAG' if flags else 'PASS', s, method=method, rows=rows, c63_stage_sum_db=pred, flags=flags,
                 provenance=prov)

    # ---- T2
    def t2(self):
        t = self.wanted('T2')
        if not t:
            return
        if self.fx['type'] != 'input':
            return self.add('T2', 'NO DATA', 'output/node response not in the recorded sets')
        lo, hi = t['codes'][0], t['codes'][-1]
        out, flags, method = {}, [], None
        for code in (lo, hi):
            r = self.chirp_at(code)
            if r:
                resp, method = dict(r['response']), 'chirp'
            else:
                v = self.src.get('resp:c%02d' % code)
                if not v or 'value' not in v:
                    return self.add('T2', 'NO DATA', 'no response at code %d' % code)
                resp, method = {int(float(k)): float(x) for k, x in v['value'].items()}, 'recorded tone (%s)' % v['from']
            out[code] = {int(f): round(d, 3) for f, d in resp.items()}
            for f, d in resp.items():
                limit_lo = -self.L['t2_20hz_maxgain_down_db'] if (code == hi and int(f) == 20) else -self.L['t2_path_tol_db']
                if d < limit_lo or d > self.L['t2_path_tol_db']:
                    flags.append('code %d %g Hz %+.3f dB' % (code, f, d))
        s = '; '.join('code %d: 20 Hz %+.2f, 20 kHz %+.2f' % (c, out[c][20], out[c][20000]) for c in (lo, hi))
        self.add('T2', 'FLAG' if flags else 'PASS', s, method=method, response=out, flags=flags)

    # ---- T3
    def t3(self):
        t = self.wanted('T3')
        if not t:
            return
        if self.fx['type'] != 'input':
            return self.add('T3', 'NO DATA', 'output THD+N not in the recorded sets')
        parts, flags, det, nodata = [], [], {}, []
        c_min, c_max = t['thdn_code'], t['thd_code']
        cap = self.src.get('tone:c%02d:m3' % c_min)
        if cap and 'captures' in cap:
            a = FFT.analyse(q428(cap['captures'][0]), FS)
            det['thdn_min'] = {'code': c_min, 'thdn_db': a['thdn_db'], 'thd_db': a['thd_db'], 'fund_dbfs': a['fund_dbfs'],
                               'method': 'FFT (dsp4_fft)', 'from': cap['from']}
        else:
            v = self.src.get('thdn:c%02d:m3' % c_min)
            if v and 'value' in v:
                det['thdn_min'] = {'code': c_min, 'thdn_db': float(v['value']), 'method': 'TEST_MEAS ThdResult', 'from': v['from']}
        if 'thdn_min' in det:
            d = det['thdn_min']['thdn_db']
            parts.append('THD+N code %d %s' % (c_min, dbpct(d)))
            if d > self.L['t3_thdn_min_gain_max_db']:
                flags.append('THD+N at min gain %s' % dbpct(d))
        else:
            nodata.append('THD+N at min gain')
        avg = self.src.get('thd_avg:c%02d' % c_max)
        cap = self.src.get('tone:c%02d:m3' % c_max)
        if cap and 'captures' in cap:
            ths = [FFT.analyse(q428(c), FS) for c in cap['captures']]
            single = 10 * math.log10(sum(10 ** (a['thd_db'] / 10) for a in ths) / len(ths))
            det['thd_max_single'] = {'code': c_max, 'thd_db': single, 'thdn_db': ths[0]['thdn_db'], 'n': len(ths),
                                     'method': 'FFT h2..h10, %d capture(s)' % len(ths), 'from': cap['from']}
        if avg and 'value' in avg:
            det['thd_max_avg'] = dict(avg['value'], method='coherent average (%s)' % avg['from'])
        use = det.get('thd_max_avg') or det.get('thd_max_single')
        if use:
            parts.append('THD code %d %s (%s)' % (c_max, dbpct(use['thd_db']), use['method'].split(' (')[0]))
            if 'thd_max_avg' in det and 'thd_max_single' in det:
                parts[-1] += ', single capture %s' % dbpct(det['thd_max_single']['thd_db'])
            if use['thd_db'] > self.L['t3_thd_max_gain_max_db']:
                flags.append('THD at max gain %s' % dbpct(use['thd_db']))
        else:
            v = self.src.get('thdn:c%02d:m3' % c_max)
            if v and 'value' in v:
                det['thdn_max_meter'] = {'thdn_db': float(v['value']), 'from': v['from']}
                parts.append('THD-only at code %d not measured (THD+N %s, noise-limited)' % (c_max, dbpct(float(v['value']))))
            nodata.append('THD at max gain')
        if self.mode != FACTORY:
            v = self.src.get('thdn_vs_level')
            if v and 'value' in v:
                det['thdn_vs_level'] = v['value']
        verdict = 'FLAG' if flags else ('NO DATA' if nodata else 'PASS')
        if flags and nodata:
            verdict = 'FLAG'
        self.add('T3', verdict, '; '.join(parts) or 'no data', flags=flags, missing=nodata, **det)

    # ---- T4 / T4b
    def noise_bands(self, caps):
        u = [FFT.band_power(q428(c), FS, 20.0, 20000.0)[0] for c in caps]
        a = [FFT.band_power(q428(c), FS, 20.0, 20000.0, aweight=True)[0] for c in caps]
        raw = [FFT.band_power(q428(c), FS, 0.0, FS / 2)[0] for c in caps]
        return emean(u), emean(a), emean(raw)

    def t4(self):
        t = self.wanted('T4')
        if not t:
            return
        if self.fx['type'] == 'output':
            cap, g = self.src.get('outnoise'), self.src.get('refgain:c00')
            if not cap or 'captures' not in cap or not g or 'value' not in g:
                why = (cap or {}).get('none') or 'no output-noise capture'
                return self.add('T4', 'NO DATA', why)
            u, a, raw = self.noise_bands(cap['captures'])
            off = 3.0103 + self.u['dac_fs_dbu'] - float(g['value'])
            fl = self.u['adc_floor_dbfs']
            corr = lambda p: 10 * math.log10(10 ** (p / 10) - 10 ** (fl / 10)) if p > fl else float('-inf')
            det = {'captures': len(cap['captures']), 'lane_dbfs': {'20-20k': u, 'A': a, 'DC-24k': raw},
                   'dbu': {'20-20k': u + off, 'A': a + off, 'DC-24k': raw + off},
                   'dbu_floor_corrected': {'20-20k': corr(u) + off, 'A': corr(a) + off},
                   'ref_gain_db': float(g['value']), 'from': cap['from']}
            flags = []
            if u + off > self.L['t4_out_noise_max_dbu']:
                flags.append('20-20k %.2f dBu' % (u + off))
            if a + off > self.L['t4_out_noise_a_max_dbu']:
                flags.append('A %.2f dBu(A)' % (a + off))
            return self.add('T4', 'FLAG' if flags else 'PASS', '%.2f dBu 20-20k, %.2f dBu(A), %.2f dBu DC-24k (%d captures; '
                            'floor-corrected %.2f / %.2f)' % (u + off, a + off, raw + off, len(cap['captures']),
                                                               det['dbu_floor_corrected']['20-20k'], det['dbu_floor_corrected']['A']),
                            flags=flags, **det)
        if self.fx['type'] != 'input':
            return
        rows = {}
        for c in t['codes_full']:
            v = self.src.get('floor:c%02d' % c)
            if v and 'value' in v:
                rows[c] = float(v['value'])
        if not rows:
            return self.add('T4', 'NO DATA', 'no tone-off floors at the T1 codes')
        s = ', '.join('c%d %.1f' % (c, rows[c]) for c in sorted(rows))
        if len(rows) < len(t['codes_full']):
            s += ' (%d of %d codes)' % (len(rows), len(t['codes_full']))
        ir = {c: rows[c] - self.G[c] for c in rows if c in self.G}
        if ir:
            s += '; input-referred %.1f..%.1f dBFS-eq' % (min(ir.values()), max(ir.values()))
        self.add('T4', 'INFO', 'floor dBFS ' + s, floors=rows, input_referred=ir)

    def t4b(self):
        t = self.wanted('T4b')
        if not t:
            return
        codes = t['codes_factory'] if self.mode == FACTORY else t['codes_full']
        det, flags, parts = {}, [], []
        for c in codes:
            cap = self.src.get('silence150:c%02d' % c)
            if not cap or 'captures' not in cap:
                if c == 63:
                    return self.add('T4b', 'NO DATA', (cap or {}).get('none') or 'no 150 ohm capture at code 63')
                continue
            if c not in self.G:
                v = self.src.get('gain:c%02d' % c)
                if v and 'value' in v:
                    self.G[c] = float(v['value'])
            if c not in self.G:
                return self.add('T4b', 'NO DATA', 'no loop gain at code %d to input-refer with' % c)
            u, a, raw = self.noise_bands(cap['captures'])
            off = 3.0103 + self.u['dac_fs_dbu'] - self.G[c]
            det[c] = {'captures': len(cap['captures']), 'lane_dbfs': {'20-20k': u, 'A': a, 'DC-24k': raw},
                      'dbu': {'20-20k': u + off, 'A': a + off, 'DC-24k': raw + off}, 'loop_gain_db': self.G[c],
                      'overruns': sum(x.get('overruns', 0) for x in cap['captures']), 'from': cap['from']}
            if c == 63:
                parts.append('EIN %.1f dBu 20-20k / %.1f dBu(A) (DC-24k %.1f; %d captures, source %s)'
                             % (u + off, a + off, raw + off, len(cap['captures']), self.u['ein_source']))
                if u + off > self.L['t4b_ein_max_dbu']:
                    flags.append('EIN %.1f dBu' % (u + off))
                if a + off > self.L['t4b_ein_a_max_dbu']:
                    flags.append('EIN(A) %.1f dBu' % (a + off))
            else:
                parts.append('code %d %.1f dBu 20-20k (converter floor)' % (c, u + off))
        self.add('T4b', 'FLAG' if flags else 'PASS', '; '.join(parts), flags=flags, codes=det,
                 note='dBu = P + 3.01 + %.2f - G_loop(code), G from T1 of this run (%s)' % (self.u['dac_fs_dbu'], self.T1_method))

    # ---- T5 / T8
    def t5_t8(self):
        want5, want8 = self.wanted('T5'), self.wanted('T8')
        if not (want5 or want8):
            return
        r = self.chirp_at(0) if self.fx['type'] == 'input' else None
        if r:
            pol, lat, method = r['polarity'], r['latency_gd_1k_2k'], 'chirp code 0'
        else:
            v = self.src.get('phase')
            if not v or 'value' not in v:
                if want5:
                    self.add('T5', 'NO DATA', 'no chirp or phase fit')
                if want8:
                    self.add('T8', 'NO DATA', 'no chirp or phase fit')
                return
            pol, lat, method = v['value']['polarity'], v['value']['latency_gd12'], 'tone phase fit (%s)' % v['from']
        if want5:
            exp = self.u.get('loop_polarity') or self.L['t5_expected']
            got = 'inverted' if pol < 0 else 'in phase'
            self.add('T5', 'PASS' if got == exp else 'FLAG', '%s (loop expects %s)' % (got, exp), method=method)
        if want8:
            nom, tol = self.u['loop_latency_samples'], self.L['t8_latency_tol_samples']
            self.add('T8', 'PASS' if abs(lat - nom) <= tol else 'FLAG',
                     '%.3f samples = %.3f ms (loop nominal %.2f +- %.2f)' % (lat, lat / 48.0, nom, tol), method=method,
                     latency_samples=lat)

    # ---- T6
    def t6(self):
        if not self.wanted('T6'):
            return
        v = self.src.get('mute')
        if not v or 'value' not in v:
            return self.add('T6', 'NO DATA', (v or {}).get('none') or 'no DSP mute measurement')
        d = v['value']['open_dbfs'] - v['value']['muted_dbfs']
        self.add('T6', 'PASS' if d >= self.L['t6_mute_min_db'] else 'FLAG', 'mute depth %.2f dB' % d, **v['value'])

    # ---- T7
    def t7(self):
        if not self.wanted('T7'):
            return
        v = self.src.get('xtalk10k')
        if not v or 'value' not in v:
            return self.add('T7', 'NO DATA', (v or {}).get('none') or 'no 10 kHz crosstalk')
        nb = {int(k): float(x) for k, x in v['value']['neighbours'].items()}
        ws, wd = max(nb.items(), key=lambda kv: kv[1])
        ctl = v['value'].get('control_db')
        self.add('T7', 'FLAG' if wd > self.L['t7_xtalk_max_db'] else 'PASS',
                 'worst neighbour strip %d %.2f dB of %d%s' % (ws, wd, len(nb), ', detector floor %.2f dB' % ctl if ctl else ''),
                 neighbours=nb, control_db=ctl, method=v.get('method'), provenance=v['from'])

    # ---- A1
    def a1(self):
        if not self.wanted('A1'):
            return
        v = self.src.get('artefacts')
        if not v or 's63' not in v:
            return self.add('A1', 'NO DATA', (v or {}).get('none') or 'no span captures')
        spec = v['s63']
        sys.path.insert(0, os.path.join(ROOT, 'MW', 'D24', 'DSP', 's63', 'tools'))
        try:
            import s63_analyse as A           # numpy: desk side, as S63
        except ImportError as e:
            return self.add('A1', 'NO DATA', 'the span analysis needs numpy (%s)' % e)
        rows = []
        for r in A.load(os.path.join(ROOT, spec['dir']), spec['xlr']):
            if r.get('invalid') or r['stim'] != 'silent' or r['kind'] == 'null':
                continue
            a = A.analyse_one(r)
            peak_flag = a['detected'] and a['peak_dbfs'] > self.L['a1_peak_max_dbfs']
            pump = a['pump_ms'] if a['dc_detect'] else 0.0
            pump_flag = pump > self.L['a1_pump_max_ms']
            rows.append({'kind': r['kind'], 'from': r['from'], 'to': r['to'], 'peak_dbfs': a['peak_dbfs'], 'detected': a['detected'],
                         'pump_ms': pump, 'pump_open': a.get('pump_open'), 'flag': ('peak ' if peak_flag else '') + ('pump' if pump_flag else '')})
        fl = [r for r in rows if r['flag']]
        det = [r for r in rows if r['detected']]
        worst = max(det, key=lambda r: r['peak_dbfs'], default=None)
        s = 'silent: %d transitions, %d PASS / %d FLAG; worst detected %s' % (
            len(rows), len(rows) - len(fl), len(fl),
            '%.1f dBFS %s %s->%s' % (worst['peak_dbfs'], worst['kind'], worst['from'][0], worst['to'][0]) if worst else 'none')
        if fl:
            s += '; flagged: ' + ', '.join('%s %s->%s (%s)' % (r['kind'], r['from'][0], r['to'][0], r['flag'].strip()) for r in fl)
        self.add('A1', 'FLAG' if fl else 'PASS', s, rows=rows, method='s63_analyse.analyse_one on the span captures, limits from limits.csv')

    # ---- node (cue/RTA, S65)
    def node(self):
        v = self.src.get('node_rows')
        if not v or 'value' not in v:
            return self.add('T1', 'NO DATA', (v or {}).get('none') or 'no node rows')
        mono = {c['case']: c.get('mono', False) for c in self.fx.get('cases', [])}
        lvl_flags, shape_flags, parts = [], [], []
        for r in v['value']:
            err = r['err_db']
            octs = list(r.get('oct_db', {}).values())
            cold = r.get('cold_max_db')
            tag = '%s %g Hz' % (r['case'], r['f'])
            if r['case'] not in mono:
                lvl_flags.append('%s: case not in the fixture' % tag)
            if abs(err) > self.L['node_level_tol_db']:
                lvl_flags.append('%s: level %+.3f dB' % (tag, err))
            if octs and min(octs) < self.L['node_octave_min_db']:
                shape_flags.append('%s: octave %.1f dB' % (tag, min(octs)))
            if mono.get(r['case']):
                # a mono case is hot on both sides by design: the two sides must agree instead
                if abs(r['cold_same_band_db'] - r['hot_db']) > self.L['node_level_tol_db']:
                    shape_flags.append('%s: mono sides differ %.3f dB' % (tag, r['cold_same_band_db'] - r['hot_db']))
                cold = None
            elif cold is not None and cold > self.L['node_cold_max_dbfs']:
                shape_flags.append('%s: cold %.1f dBFS' % (tag, cold))
            parts.append('%s %+.3f dB, octave >= %.2f, cold %s' % (tag, err, min(octs) if octs else float('nan'),
                                                                  '%.1f' % cold if cold is not None else 'mono (both hot)'))
        rows = v['value']
        self.add('T1', 'FLAG' if lvl_flags else 'PASS', '%d rows; worst level %+.3f dB re expected' % (
            len(rows), max((r['err_db'] for r in rows), key=abs)), rows=parts, flags=lvl_flags,
            method=v.get('method'), provenance=v['from'])
        colds = [r['cold_max_db'] for r in rows if not mono.get(r['case']) and r.get('cold_max_db') is not None]
        self.add('T2', 'FLAG' if shape_flags else 'PASS', 'octave neighbours >= %.2f dB down; cold side <= %.1f dBFS; '
                 'mono cases equal on both sides' % (min(min(r['oct_db'].values()) for r in rows if r.get('oct_db')), max(colds)),
                 flags=shape_flags)

    def go(self):
        if self.fx['type'] == 'node':
            self.node()
        else:
            self.t1(); self.t2(); self.t3(); self.t4(); self.t4b(); self.t5_t8(); self.t6(); self.t7(); self.a1()
        need = [t for t in self.tests if self.wanted(t)]
        got = {r['test']: r['verdict'] for r in self.res}
        if any(v == 'FLAG' for v in got.values()):
            verdict = 'FLAG'
        elif any(got.get(t, 'NO DATA') == 'NO DATA' for t in need):
            verdict = 'INCOMPLETE'
        else:
            verdict = 'PASS'
        order = ['T1', 'T2', 'T3', 'T4', 'T4b', 'T5', 'T6', 'T7', 'T8', 'A1']
        self.res.sort(key=lambda r: order.index(r['test']) if r['test'] in order else 99)
        return verdict


def jsonable(o):
    if isinstance(o, float):
        return o if math.isfinite(o) else str(o)
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    return o


def cmd_run(a):
    fx = json.load(open(a.fixture))
    if fx.get('status') not in (None, 'ok', 'proposal'):
        raise SystemExit('%s: status %s -- nothing to run' % (fx['fixture'], fx.get('status')))
    limits = load_limits(a.limits)
    unit = load_unit(a.units, a.unit)
    src = ReplaySource(a.source.split(':', 1)[1]) if a.source.startswith('replay:') else LiveSource(fx, unit)
    t0 = time.time()
    R = Run(fx, a.mode, src, limits, unit)
    verdict = R.go()
    out = {'fixture': fx['fixture'], 'panel': fx['path'].get('panel') or fx['path'].get('node'), 'type': fx['type'],
           'unit': a.unit, 'mode': a.mode, 'source': src.describe(), 'verdict': verdict, 'tests': R.res,
           'limits': os.path.relpath(a.limits, ROOT), 'fixture_from': fx.get('generated_from'),
           }
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, fx['fixture'] + '.json'), 'w') as f:
        json.dump(jsonable(out), f, indent=1)
        f.write('\n')
    print('%-18s %-10s %-10s' % (fx['fixture'], a.mode, verdict))
    for r in R.res:
        print('   %-4s %-8s %s' % (r['test'], r['verdict'], r['summary']))
    return verdict


def cmd_report(a):
    rows = []
    for d in a.dirs:
        for f in sorted(glob.glob(os.path.join(d, '*.json'))):
            rows.append(json.load(open(f)))
    if not rows:
        raise SystemExit('no results')
    tests = ['T1', 'T2', 'T3', 'T4', 'T4b', 'T5', 'T6', 'T7', 'T8', 'A1']
    by = {}
    for r in rows:
        by.setdefault((r['unit'], r['mode']), []).append(r)
    lines = []
    mark = {'PASS': 'pass', 'FLAG': '**FLAG**', 'NO DATA': '·', 'INFO': 'info'}
    for (unit, mode), rs in sorted(by.items()):
        lines += ['## %s — %s mode' % (unit, mode), '',
                  '| path | panel | verdict | ' + ' | '.join(tests) + ' |', '|---|---|---|' + '---|' * len(tests)]
        for r in sorted(rs, key=lambda r: r['fixture']):
            v = {t['test']: mark.get(t['verdict'], t['verdict']) for t in r['tests']}
            lines.append('| %s | %s | %s | %s |' % (r['fixture'], r['panel'], r['verdict'], ' | '.join(v.get(t, '') for t in tests)))
        lines += ['', '### Detail', '']
        for r in sorted(rs, key=lambda r: r['fixture']):
            lines.append('**%s (%s) — %s.** Source: %s.' % (r['fixture'], r['panel'], r['verdict'], r['source']))
            for t in r['tests']:
                lines.append('- %s %s: %s' % (t['test'], t['verdict'], t['summary']))
            lines.append('')
    txt = '\n'.join(lines) + '\n'
    if a.md:
        open(a.md, 'w').write(txt)
    print(txt)


def cmd_plan(a):
    man = json.load(open(a.manifest))
    base = os.path.dirname(a.manifest)
    cost = {r['step']: float(r['seconds']) for r in read_csv(a.costs)}
    out = []
    for m in man['fixtures']:
        if m['status'] not in ('ok',):
            continue
        fx = json.load(open(os.path.join(base, m['file'])))
        tests = {t['test']: t for t in fx['tests'] if (t['factory'] if a.mode == FACTORY else t['full'])}
        steps = {}
        add = lambda k, n: steps.__setitem__(k, steps.get(k, 0) + n)
        if fx['type'] == 'input':
            if 'T1' in tests:
                t1 = tests['T1']
                codes = t1['codes_factory'] if a.mode == FACTORY else t1['codes_full']
                add('chirp_capture', len(codes) + (len(t1['repeat_codes']) if a.mode != FACTORY else 0))
            if 'T3' in tests:
                add('tone_capture', 2 + (len(tests['T3']['levels_full_dbfs']) if a.mode != FACTORY else 0))
            if 'T4' in tests:
                add('silence_capture', len(tests['T4']['codes_full']))
            if 'T4b' in tests:
                add('silence_capture', len(tests['T4b']['codes_factory' if a.mode == FACTORY else 'codes_full']))
            if 'T6' in tests:
                add('tone_capture', 2)
            if 'T7' in tests:
                add('xtalk_neighbour_meter', 23)
            if 'A1' in tests:
                add('span_capture', 72)
        else:
            add('chirp_capture', 1); add('tone_capture', 1); add('silence_capture', 1)
            if 'T6' in tests:
                add('tone_capture', 2)
            if 'T7' in tests:
                add('xtalk_neighbour_meter', 12)
        caps = sum(n for k, n in steps.items() if k.endswith('_capture'))
        acq = sum(cost[k] * n for k, n in steps.items())
        out.append({'fixture': m['fixture'], 'type': fx['type'], 'steps': steps, 'acq_s': acq,
                    'desk_s': acq + caps * cost['analysis_desk'], 'cm4_s': acq + caps * cost['analysis_cm4']})
    ins = [o for o in out if o['type'] == 'input']
    outs = [o for o in out if o['type'] == 'output']
    print('mode %s, %d input + %d output paths' % (a.mode, len(ins), len(outs)))
    for o in out[:1] + outs[:1]:
        print('  %-16s %s -> %.1f s desk / %.1f s CM4 analysis' % (o['fixture'], o['steps'], o['desk_s'], o['cm4_s']))
    tot = lambda k: sum(o[k] for o in out)
    moves = len(out) * cost['cable_move_manual']
    print('  manual loop, one path at a time: %.1f min instrument time (desk analysis), %.1f min CM4; + %d cable moves '
          '= %.1f min' % (tot('desk_s') / 60, tot('cm4_s') / 60, len(out), (tot('desk_s') + moves) / 60))
    if ins:
        # harness: every register at one code, all lanes driven; per code one setup, per lane one chirp (S61-3)
        t1 = ins[0]['steps'].get('chirp_capture', 0)
        codes = t1 - (0 if a.mode == FACTORY else 2)
        h = codes * (cost['harness_code_setup'] + len(ins) * cost['harness_lane_chirp'])
        other = sum((o['steps'].get('tone_capture', 0) * cost['tone_capture'] + o['steps'].get('silence_capture', 0) * cost['silence_capture']
                     + o['steps'].get('span_capture', 0) * cost['span_capture']) for o in ins)
        xt = sum(o['steps'].get('xtalk_neighbour_meter', 0) for o in ins) * cost['xtalk_neighbour_meter']
        an = sum(sum(n for k, n in o['steps'].items() if k.endswith('_capture')) for o in ins) * cost['analysis_desk']
        print('  harness (inputs): chirps %.1f min + tone/noise%s %.1f min + analysis %.1f min = %.1f min; + 10 kHz '
              'crosstalk by meter, every source x %d neighbours, %.1f min (total %.1f min)'
              % (h / 60, '/spans' if a.mode != FACTORY else '', other / 60, an / 60, (h + other + an) / 60,
                 len(ins) - 1, xt / 60, (h + other + an + xt) / 60))
    return out


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sp = ap.add_subparsers(dest='cmd', required=True)
    r = sp.add_parser('run')
    r.add_argument('--fixture', required=True)
    r.add_argument('--mode', choices=('factory', 'full'), default='factory')
    r.add_argument('--unit', default='MW-D24-2')
    r.add_argument('--source', required=True)
    r.add_argument('--limits', default=os.path.join(ROOT, 'tools', 'accept', 'limits.csv'))
    r.add_argument('--units', default=os.path.join(ROOT, 'tools', 'accept', 'units.csv'))
    r.add_argument('--out', default='accept-results')
    p = sp.add_parser('report')
    p.add_argument('dirs', nargs='+')
    p.add_argument('--md')
    q = sp.add_parser('plan')
    q.add_argument('--manifest', required=True)
    q.add_argument('--mode', choices=('factory', 'full'), default='factory')
    q.add_argument('--costs', default=os.path.join(ROOT, 'tools', 'accept', 'step-costs.csv'))
    a = ap.parse_args(argv)
    return {'run': cmd_run, 'report': cmd_report, 'plan': cmd_plan}[a.cmd](a)


if __name__ == '__main__':
    main(sys.argv[1:])
