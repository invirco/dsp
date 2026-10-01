#!/usr/bin/env python3
"""s160_analyse.py -- the desk half of the S160 MIC 1-5 noise-floor audit.

    s160_analyse.py DATA_DIR [--png OUT_DIR]

Per setting (one JSON from s160_audit.py): 6 x 16,384-sample captures of the
strip, each mean-removed and Hann-windowed, periodograms averaged (2.93 Hz
bins). Reported per setting:

  * band totals, mean-square dBFS (a full-scale sine reads -3.01): DC-24k
    (what the node's RmsResult reads), 20 Hz-20 kHz, and 20 Hz-20 kHz
    A-weighted;
  * the same INPUT-REFERRED by the S57-R method: dBu = P + 3.01 + dac_fs_dbu
    - G(code), G(code) = the lane's code-0 loop gain from today's factory pass
    (pass 4 references) + the code's step from defs' mic-gain-codes.csv.
    OPEN INPUTS: an input-referred open-input figure is an investigation
    number, NOT an EIN -- EIN is defined with a 150 ohm source and nothing
    here is graded against limits.csv t4b_ein_max_dbu;
  * the excess over MIC 1 and over MIC 5 per octave band, input-referred;
  * discrete lines: bins over a running-median floor, and the 50 Hz / 60 Hz
    families looked up by name.
"""
import json
import math
import os
import sys

import numpy as np

FS = 48000.0
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..',
                                    '..', '..', '..'))
DAC_FS_DBU = None
# today's factory pass (pass 4, 2026-10-01 12:17Z) code-0 balanced references,
# AUX 1 -> MIC n through K1, from runall/state.json (see the S159 notes)
G0 = {'MIC 1': 5.28, 'MIC 2': 5.55, 'MIC 3': 5.55, 'MIC 4': 5.55,
      'MIC 5': 5.54}


def units_dac_fs():
    for line in open(os.path.join(ROOT, 'tools', 'accept', 'units.csv')):
        if line.startswith('MW-D24-2,'):
            return float(line.split(',')[2])
    raise SystemExit('MW-D24-2 is not in units.csv')


def gain_steps():
    out = {}
    for line in open(os.path.join(ROOT, 'defs', 'common', 'tables',
                                  'mic-gain-codes.csv')):
        if line[:1].isdigit():
            c = line.split(',')
            out[int(c[0])] = float(c[2])
    return out


def q28(words):
    a = np.array(words, dtype=np.int64) & 0xFFFFFFFF
    a = np.where(a >= 2 ** 31, a - 2 ** 32, a)
    return a.astype(np.float64) / 2.0 ** 28


def a_weight_db(f):
    f = np.maximum(f, 1e-3)
    f2 = f * f
    ra = (12194.0 ** 2 * f2 * f2) / ((f2 + 20.6 ** 2) * np.sqrt(
        (f2 + 107.7 ** 2) * (f2 + 737.9 ** 2)) * (f2 + 12194.0 ** 2))
    return 20 * np.log10(ra) + 2.0


def psd(caps):
    """Mean-square per bin (one-sided), averaged over captures. Sum of the
    returned array over a band = the band's mean-square power."""
    acc, raw = None, []
    for c in caps:
        x = q28(c['samples'])
        raw.append(float(np.mean(x * x)))
        x = x - x.mean()
        n = len(x)
        w = np.hanning(n)
        X = np.fft.rfft(x * w)
        p = (np.abs(X) ** 2) / (n * np.sum(w * w))
        p[1:-1] *= 2.0
        acc = p if acc is None else acc + p
    p = acc / len(caps)
    f = np.fft.rfftfreq(len(caps[0]['samples']), 1.0 / FS)
    return f, p, 10 * math.log10(np.mean(raw))


def band(f, p, lo, hi, aw=False):
    m = (f >= lo) & (f <= hi)
    q = p[m] * (10 ** (a_weight_db(f[m]) / 10.0) if aw else 1.0)
    return 10 * math.log10(np.sum(q))


def lines(f, p, k=40, over_db=8.0, top=14):
    db = 10 * np.log10(p + 1e-30)
    from numpy.lib.stride_tricks import sliding_window_view
    pad = np.pad(db, k, mode='edge')
    floor = np.median(sliding_window_view(pad, 2 * k + 1), axis=1)
    ex = db - floor
    pk = [i for i in range(2, len(f) - 1)
          if ex[i] >= over_db and db[i] >= db[i - 1] and db[i] >= db[i + 1]
          and f[i] >= 10]
    pk.sort(key=lambda i: -ex[i])
    return [(round(float(f[i]), 1), round(float(ex[i]), 1),
             round(float(db[i]), 1)) for i in pk[:top]]


def at(f, p, hz, half=2.0):
    """Line strength near `hz`: the max bin within +-half Hz over the median
    of the 40 bins either side, in dB."""
    db = 10 * np.log10(p + 1e-30)
    m = (f >= hz - half) & (f <= hz + half)
    if not m.any():
        return None
    i = np.argmax(np.where(m, db, -1e9))
    nb = db[max(0, i - 40):i - 4].tolist() + db[i + 5:i + 41].tolist()
    return round(float(db[i] - np.median(nb)), 1)


OCT = [(10, 20), (20, 50), (50, 100), (100, 200), (200, 500), (500, 1000),
       (1000, 2000), (2000, 5000), (5000, 10000), (10000, 20000),
       (20000, 24000)]


def main():
    d = sys.argv[1]
    png = sys.argv[sys.argv.index('--png') + 1] if '--png' in sys.argv else None
    dac = units_dac_fs()
    steps = gain_steps()
    recs = []
    for fn in sorted(os.listdir(d)):
        if not fn.endswith('.json') or not fn.startswith('MIC'):
            continue
        r = json.load(open(os.path.join(d, fn)))
        f, p, raw = psd(r['captures'])
        g = G0[r['input']] + steps[r['code']]
        off = 3.0103 + dac - g
        r.update(f=f, p=p, raw_dbfs=raw, g=g, off=off, tag=fn[:-5])
        recs.append(r)
    by = dict((r['tag'], r) for r in recs)
    print('S160 MIC 1-5 OPEN-input noise audit, MW-D24-2, %s (symbols %s)'
          % (recs[0]['stamp'], recs[0]['symdir']))
    print('input-referred dBu = P + 3.01 + %.2f (units.csv dac_fs_dbu) - G; '
          'G = pass-4 code-0 ref + mic-gain-codes step' % dac)
    print('OPEN INPUTS: these are NOT EIN figures (EIN needs the 150 ohm '
          'source); nothing here is graded against -126.0 dBu.\n')
    hdr = ('%-12s %6s %8s %8s %8s %8s | %9s %9s %9s'
           % ('setting', 'G dB', 'node', 'DC-24k', '20-20k', 'A',
              'in 20-20k', 'in A', 'in DC-24k'))
    print(hdr)
    print('-' * len(hdr))
    for r in recs:
        f, p = r['f'], r['p']
        u = band(f, p, 20, 20000)
        a = band(f, p, 20, 20000, aw=True)
        t = 10 * math.log10(np.sum(p)) if True else None
        r['u'], r['a'], r['t'] = u, a, t
        print('%-12s %6.2f %8.2f %8.2f %8.2f %8.2f | %9.1f %9.1f %9.1f'
              % (r['tag'].replace('_open', ''), r['g'], r['node_rms'], r['raw_dbfs'],
                 u, a, u + r['off'], a + r['off'], r['raw_dbfs'] + r['off']))
    print('\nPER OCTAVE, input-referred dB OVER the reference (code 63, open):')
    refs = [k for k in ('MIC1_c63_open', 'MIC5_c63_open') if k in by]
    for ref in refs:
        R = by[ref]
        print('  vs %s' % ref.replace('_open', ''))
        print('  %-10s ' % '' + ' '.join('%7s' % ('%g-%g' % (lo / 1000.0 if lo >= 1000 else lo, hi / 1000.0 if hi >= 1000 else hi)) for lo, hi in OCT))
        for r in recs:
            if r['code'] != 63 or r['tag'] == ref:
                continue
            cells = []
            for lo, hi in OCT:
                x = band(r['f'], r['p'], lo, hi) + r['off']
                y = band(R['f'], R['p'], lo, hi) + R['off']
                cells.append('%+7.1f' % (x - y))
            print('  %-10s ' % r['input'] + ' '.join(cells))
    print('\nNAMED LINES (dB over the local floor; None = off the grid):')
    fams = [('50 Hz', [50, 100, 150, 200, 250]),
            ('60 Hz', [60, 120, 180, 240, 300])]
    for r in recs:
        s = []
        for name, hzs in fams:
            s.append('%s %s' % (name, ' '.join(
                '%s' % at(r['f'], r['p'], h) for h in hzs)))
        print('  %-12s %s' % (r['tag'].replace('_open', ''), ' | '.join(s)))
    print('\nSTRONGEST LINES (Hz, dB over a +-40-bin running median, bin dBFS):')
    for r in recs:
        print('  %-12s %s' % (r['tag'].replace('_open', ''),
                              ', '.join('%g Hz +%g' % (a, b)
                                        for a, b, _c in lines(r['f'], r['p']))))
    if png:
        plot(recs, by, png)


def plot(recs, by, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(out, exist_ok=True)
    binhz = recs[0]['f'][1]

    def dens(r):          # input-referred dBu/sqrt(Hz)
        return 10 * np.log10(r['p'] / binhz + 1e-30) + r['off']

    fig, ax = plt.subplots(figsize=(11, 6))
    for k in ('MIC1_c63_open', 'MIC2_c63_open', 'MIC3_c63_open',
              'MIC4_c63_open', 'MIC5_c63_open'):
        if k in by:
            r = by[k]
            ax.semilogx(r['f'][1:], dens(r)[1:], lw=0.7,
                        label='%s (20-20k %.1f dBu in.-ref.)'
                        % (r['input'], r['u'] + r['off']))
    ax.set_xlim(10, 24000)
    ax.set_xlabel('Hz')
    ax.set_ylabel('input-referred dBu/sqrt(Hz)')
    ax.set_title('MW-D24-2, code 63, OPEN inputs (not EIN): MIC 1-5, 6 x 16k '
                 'captures averaged')
    ax.grid(True, which='both', alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out, 's160-mic1-5-open-c63.png'), dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 6))
    for k in ('MIC2_c00_open', 'MIC2_c32_open', 'MIC2_c48_open',
              'MIC2_c63_open', 'MIC1_c63_open'):
        if k in by:
            r = by[k]
            ax.semilogx(r['f'][1:], 10 * np.log10(r['p'][1:] / binhz),
                        lw=0.7, label='%s code %d (lane 20-20k %.1f dBFS)'
                        % (r['input'], r['code'], r['u']))
    ax.set_xlim(10, 24000)
    ax.set_xlabel('Hz')
    ax.set_ylabel('lane dBFS/sqrt(Hz) (NOT input-referred)')
    ax.set_title('MW-D24-2 MIC 2 open at codes 0/32/48/63, MIC 1 code 63 for '
                 'reference')
    ax.grid(True, which='both', alpha=0.3)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out, 's160-mic2-by-code.png'), dpi=110)
    plt.close(fig)

    if 'MIC5_c63_open' in by:
        R = by['MIC5_c63_open']
        fig, ax = plt.subplots(figsize=(11, 5))
        k = 16
        for key in ('MIC1_c63_open', 'MIC2_c63_open', 'MIC3_c63_open',
                    'MIC4_c63_open'):
            if key in by:
                r = by[key]
                a = np.convolve(dens(r), np.ones(k) / k, mode='same')
                b = np.convolve(dens(R), np.ones(k) / k, mode='same')
                ax.semilogx(r['f'][k:-k], (a - b)[k:-k], lw=0.8,
                            label='%s - MIC 5' % r['input'])
        ax.axhline(0, color='k', lw=0.5)
        ax.set_xlim(10, 24000)
        ax.set_xlabel('Hz')
        ax.set_ylabel('dB (input-referred, 47 Hz smoothing)')
        ax.set_title('Excess over MIC 5, code 63, open inputs')
        ax.grid(True, which='both', alpha=0.3)
        ax.legend(fontsize=8)
        fig.tight_layout()
        fig.savefig(os.path.join(out, 's160-excess-vs-mic5.png'), dpi=110)
        plt.close(fig)
    print('\nplots: %s' % out)


if __name__ == '__main__':
    main()
