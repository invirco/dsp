"""s57_table.py — the S57 table from data/*.json: one row per capture set (tag), energy-averaged.
Input-referred dBu (reconciled, S57-R): dBu_in = P_ms + 3.01 + 17.55 - (G(code) - G(0)); the code-0 converter floor
(150 ohm, f150c0, band-matched) power-subtracted where stated. Every band from the DC-removed capture."""
import glob, json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import s57_analyse as A, s57_bands as B
os.chdir(os.path.join(os.path.dirname(__file__), '..'))
G = A.G
def em(v): v = [x for x in v if x > -900]; return 10 * math.log10(sum(10 ** (x / 10) for x in v) / len(v)) if v else -999
def sub(l, f): d = 10 ** (l / 10) - 10 ** (f / 10); return 10 * math.log10(d) if d > 0 else float('nan')
tags = sys.argv[1:]
res = {}
for tag in tags:
    fs = sorted(glob.glob('data/%s_*.json' % tag))
    an = [A.anat(f) for f in fs]; bd = [B.bands(f) for f in fs]
    code = an[0]['code']
    r = {'tag': tag, 'n': len(fs), 'code': code, 'mode': bd[0].get('mode'),
         'node': em([a['node_rms'] for a in an if a.get('node_rms') is not None]) if an[0].get('node_rms') is not None else None,
         'raw': em([b['total'] for b in bd]), 'aud': em([a['b20k_dbfs'] for a in an]), 'aw': em([a['a20k_dbfs'] for a in an]),
         'lf5': em([b['0.1-5'] for b in bd]), 'lf20': em([b['5-20'] for b in bd]), 'hf': em([b['20000-24000'] for b in bd]),
         'raw_min': min(b['total'] for b in bd), 'raw_max': max(b['total'] for b in bd),
         'aud_min': min(a['b20k_dbfs'] for a in an), 'aud_max': max(a['b20k_dbfs'] for a in an),
         'kurt': [round(min(a['imp_raw']['kurtosis'] for a in an), 3), round(max(a['imp_raw']['kurtosis'] for a in an), 3)],
         'ev4s': sum(a['imp_raw']['events'] for a in an) / len(an), 'crest': [round(min(a['crest_db'] for a in an), 1), round(max(a['crest_db'] for a in an), 1)],
         'exc_rms': em([a['imp_raw']['rms_excised_dbfs'] for a in an]), 'mains_pct': sum(a['mains_share_pct'] for a in an) / len(an),
         'slope': sum(a['slope_db_dec'] for a in an) / len(an), 'lfpp': em([b['lf_pp_dbfs'] for b in bd])}
    off = 3.0103 + 17.55 - (G[code] - G[0])
    r['in_off'] = off
    for k in ('raw', 'aud', 'aw', 'lf5', 'lf20', 'hf'):
        r[k + '_dbu'] = r[k] + off
    res[tag] = r
    print(json.dumps(r))
