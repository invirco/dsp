#!/usr/bin/env python3
"""s162_compare.py -- S162 (Q542 Schottky fitted) against S160 (before), OPEN
inputs, code 63 unless named. NOT EIN.

    s162_compare.py S160_DATA S162_DATA [--png OUT_DIR]

  * per input: 20-20k and A input-referred, the 10-20 kHz octave over the
    same run's MIC 5, and the HF hump (peak of the 300 Hz-smoothed excess over
    the same run's MIC 5, 6-23.9 kHz);
  * the S162 drift map: per drift capture pair, time since rails-up, the
    14-23.9 kHz peak (200 Hz smoothing; s160_ab.py stopped at 21.5k), its
    excess over the S162 MIC 5 reference, and the 10-20 kHz octave and the
    20-24 kHz band input-referred over MIC 5;
  * the S160 A/B points on the same axes, times approximate (S160 recorded no
    rails-up stamp: t = the record's stamp minus the first record's, plus the
    first record's own settle + capture time).
"""
import calendar
import json
import os
import sys
import time

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import s162_analyse as A          # noqa: E402

DAC = A.units_dac_fs()
STEPS = A.gain_steps()
HUMP_MIN_DB = 6.0       # a smoothed excess below this is "no hump"


def load(path):
    r = json.load(open(path))
    f, p, raw = A.psd(r['captures'])
    g = A.G0[r['input']] + STEPS[r['code']]
    r.update(f=f, p=p, off=3.0103 + DAC - g)
    return r


def sm(p, f, hz):
    k = max(1, int(hz / f[1]))
    return np.convolve(10 * np.log10(p + 1e-30), np.ones(k) / k, mode='same')


def hump(r, ref, lo=6000, hi=23900, hz=300):
    f = r['f']
    d = sm(r['p'], f, hz) + r['off'] - (sm(ref['p'], f, hz) + ref['off'])
    m = (f > lo) & (f < hi)
    i = int(np.argmax(np.where(m, d, -1e9)))
    return float(f[i]), float(d[i])


def octave_over(r, ref, lo=10000, hi=20000):
    return (A.band(r['f'], r['p'], lo, hi) + r['off']
            - A.band(ref['f'], ref['p'], lo, hi) - ref['off'])


def runs(d):
    return dict((fn[:-10], load(os.path.join(d, fn)))
                for fn in sorted(os.listdir(d))
                if fn.startswith('MIC') and fn.endswith('_open.json'))


def drift(d, ref):
    out = []
    dd = os.path.join(d, 'drift')
    for fn in sorted(os.listdir(dd)):
        r = load(os.path.join(dd, fn))
        t = r['captures'][0]['t_rails']
        f = r['f']
        s = sm(r['p'], f, 200)
        m = (f > 14000) & (f < 23900)
        j = int(np.argmax(np.where(m, s, -1e9)))
        hf, hx = hump(r, ref, 14000, 23900, 200)
        out.append(dict(inp=r['input'], t=t, peak=float(f[j]), lvl=float(s[j]),
                        hump_f=hf, hump_x=hx, oct=octave_over(r, ref),
                        top=octave_over(r, ref, 20000, 24000)))
    return out


def s160_ab(d, ref):
    dd = os.path.join(d, 'ab')
    recs = [json.load(open(os.path.join(dd, fn)))
            for fn in sorted(os.listdir(dd)) if fn.startswith('seq')]
    st = [calendar.timegm(time.strptime(r['stamp'], '%Y-%m-%dT%H:%M:%SZ'))
          for r in recs]
    first_len = recs[0]['captures'][-1]['t'] + 8.0     # captures + node RMS
    out = []
    for r, s in zip(recs, st):
        g = A.G0[r['input']] + STEPS[r['code']]
        span = r['captures'][-1]['t'] + 8.0
        for c in r['captures']:
            x = dict(r, captures=[c])
            f, p, _ = A.psd([c])
            x.update(f=f, p=p, off=3.0103 + DAC - g)
            t = (s - st[0]) + first_len - span + c['t']
            hf, hx = hump(x, ref, 14000, 23900, 200)
            out.append(dict(inp=r['input'], code=r['code'], t=t, hump_f=hf,
                            hump_x=hx, oct=octave_over(x, ref),
                            top=octave_over(x, ref, 20000, 24000)))
    return out


def main():
    d0, d1 = sys.argv[1], sys.argv[2]
    png = sys.argv[sys.argv.index('--png') + 1] if '--png' in sys.argv else None
    B, C = runs(d0), runs(d1)
    print('S162 vs S160, MW-D24-2, OPEN inputs (NOT EIN). Input-referred by '
          'S57-R (dac_fs %.2f dBu, pass-4 G0 + mic-gain-codes).' % DAC)
    print('Hump = peak of the 300 Hz-smoothed input-referred excess over the '
          'SAME run\'s MIC 5, 6-23.9 kHz.\n')
    print('%-9s | %22s | %22s | %22s | %22s | %24s' % (
        'setting', '20-20k dBu  S160/S162', 'A dBu      S160/S162',
        '10-20k oct over MIC5', '20-24k over MIC5', 'hump  S160 -> S162'))
    for k in ('MIC1_c63', 'MIC2_c63', 'MIC3_c63', 'MIC4_c63', 'MIC5_c63',
              'MIC2_c00', 'MIC2_c32', 'MIC2_c48'):
        if k not in B or k not in C:
            continue
        b, c = B[k], C[k]
        u = [A.band(x['f'], x['p'], 20, 20000) + x['off'] for x in (b, c)]
        a = [A.band(x['f'], x['p'], 20, 20000, aw=True) + x['off'] for x in (b, c)]
        o = [octave_over(b, B['MIC5_c63']), octave_over(c, C['MIC5_c63'])]
        q = [octave_over(b, B['MIC5_c63'], 20000, 24000),
             octave_over(c, C['MIC5_c63'], 20000, 24000)]
        h = [hump(b, B['MIC5_c63']), hump(c, C['MIC5_c63'])]
        print('%-9s | %9.1f %9.1f    | %9.1f %9.1f    | %+8.1f %+8.1f     | '
              '%+8.1f %+8.1f     | %5.0f Hz %+5.1f -> %5.0f Hz %+5.1f'
              % (k, u[0], u[1], a[0], a[1], o[0], o[1], q[0], q[1],
                 h[0][0], h[0][1],
                 h[1][0], h[1][1]))
    print('\n1 kHz bands 14-24 kHz, input-referred dB over the same run\'s MIC 5 '
          '(code 63):')
    edges = list(range(14000, 24001, 1000))
    print('%-14s ' % '' + ' '.join('%6d' % (e // 1000) for e in edges[:-1]) + '  kHz')
    for k in ('MIC1_c63', 'MIC2_c63', 'MIC3_c63', 'MIC4_c63'):
        for tag, R in (('S160', B), ('S162', C)):
            r, ref = R[k], R['MIC5_c63']
            print('%-14s ' % ('%s %s' % (k[:4], tag)) + ' '.join(
                '%+6.1f' % (A.band(r['f'], r['p'], lo, hi) + r['off']
                            - A.band(ref['f'], ref['p'], lo, hi) - ref['off'])
                for lo, hi in zip(edges, edges[1:])))
    print('\nTHE COMPONENT NEAR NYQUIST, 22-24 kHz: band power, and the power '
          'OVER the same run\'s MIC 5 code 63 (power difference), lane dBFS and '
          'input-referred dBu:')
    for tag, R in (('S160', B), ('S162', C)):
        ref = R['MIC5_c63']
        pr = 10 ** (A.band(ref['f'], ref['p'], 22000, 24000) / 10.0)
        for k in ('MIC1_c63', 'MIC2_c63', 'MIC3_c63', 'MIC4_c63', 'MIC2_c48',
                  'MIC2_c32'):
            r = R[k]
            pb = 10 ** (A.band(r['f'], r['p'], 22000, 24000) / 10.0)
            ex = 10 * np.log10(max(pb - pr, 1e-30))
            print('  %s %-9s band %7.1f dBFS / %7.1f dBu   excess %7.1f dBFS '
                  '/ %7.1f dBu' % (tag, k, 10 * np.log10(pb),
                                   10 * np.log10(pb) + r['off'], ex,
                                   ex + r['off']))
    D = drift(d1, C['MIC5_c63'])
    print('\nS162 DRIFT MAP from a cold rails-up (2 x 16k per point; ref = S162 '
          'MIC 5 code 63):')
    print('%-6s %8s | %9s %8s | %9s %8s | %10s | %10s' % (
        'input', 't s', 'peak Hz', 'dB/bin', 'hump Hz', 'over M5',
        '10-20k o/M5', '20-24k o/M5'))
    for x in D:
        print('%-6s %8.1f | %9.0f %8.1f | %9.0f %+8.1f | %+10.1f | %+10.1f'
              % (x['inp'], x['t'], x['peak'], x['lvl'], x['hump_f'],
                 x['hump_x'], x['oct'], x['top']))
    m2 = [x for x in D if x['inp'] == 'MIC 2']
    hx = np.array([x['hump_x'] for x in m2])
    hf = np.array([x['hump_f'] for x in m2])
    oc = np.array([x['oct'] for x in m2])
    print('\nMIC 2 drift summary: hump excess %+.1f..%+.1f dB (median %+.1f); '
          'where >= %.0f dB the peak spans %s; 10-20k octave over MIC 5 '
          '%+.1f..%+.1f dB'
          % (hx.min(), hx.max(), np.median(hx), HUMP_MIN_DB,
             ('%.0f-%.0f Hz' % (hf[hx >= HUMP_MIN_DB].min(),
                                hf[hx >= HUMP_MIN_DB].max()))
             if (hx >= HUMP_MIN_DB).any() else 'nothing (no point reaches it)',
             oc.min(), oc.max()))
    AB = s160_ab(d0, B['MIC5_c63'])
    print('\nS160 A/B (before), per capture, t approx. since rails-up:')
    for x in AB:
        print('  %-6s code %2d t~%6.1f s  hump %5.0f Hz %+5.1f dB  10-20k o/M5 '
              '%+5.1f  20-24k o/M5 %+5.1f' % (x['inp'], x['code'], x['t'],
                                              x['hump_f'], x['hump_x'],
                                              x['oct'], x['top']))
    if png:
        plots(B, C, D, AB, png)


def plots(B, C, D, AB, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    os.makedirs(out, exist_ok=True)
    binhz = C['MIC5_c63']['f'][1]

    def dens(r):
        return 10 * np.log10(r['p'] / binhz + 1e-30) + r['off']

    fig, axs = plt.subplots(2, 2, figsize=(13, 8), sharex=True, sharey=True)
    for ax, k in zip(axs.flat, ('MIC1_c63', 'MIC2_c63', 'MIC3_c63', 'MIC4_c63')):
        for tag, R, col in (('S160 before', B, 'tab:red'),
                            ('S162 Schottky', C, 'tab:blue')):
            ax.semilogx(R[k]['f'][1:], dens(R[k])[1:], lw=0.6, color=col,
                        label='%s (20-20k %.1f dBu)' % (
                            tag, A.band(R[k]['f'], R[k]['p'], 20, 20000)
                            + R[k]['off']))
        ax.semilogx(C['MIC5_c63']['f'][1:], dens(C['MIC5_c63'])[1:], lw=0.5,
                    color='0.6', label='S162 MIC 5 (reference)')
        ax.set_title('%s code 63, open' % k[:4].replace('MIC', 'MIC '))
        ax.set_xlim(1000, 24000)
        ax.grid(True, which='both', alpha=0.3)
        ax.legend(fontsize=7, loc='upper left')
    for ax in axs[1]:
        ax.set_xlabel('Hz')
    for ax in axs[:, 0]:
        ax.set_ylabel('input-referred dBu/sqrt(Hz)')
    fig.suptitle('MW-D24-2 Q542 Schottky A/B: S160 (before) vs S162 (after), '
                 'OPEN inputs, NOT EIN')
    fig.tight_layout()
    fig.savefig(os.path.join(out, 's162-before-after-mic1-4.png'), dpi=110)
    plt.close(fig)

    fig, axs = plt.subplots(2, 2, figsize=(13, 8), sharex=True, sharey=True)
    for ax, k in zip(axs.flat, ('MIC1_c63', 'MIC2_c63', 'MIC3_c63', 'MIC4_c63')):
        for tag, R, col in (('S160 before', B, 'tab:red'),
                            ('S162 Schottky', C, 'tab:blue')):
            ax.plot(R[k]['f'], dens(R[k]), lw=0.5, color=col, label=tag)
        for tag, R, col in (('S160 MIC 5', B, '0.75'), ('S162 MIC 5', C, '0.45')):
            ax.plot(R['MIC5_c63']['f'], dens(R['MIC5_c63']), lw=0.4, color=col,
                    label=tag)
        ax.axvline(22100, color='k', lw=0.5, ls=':')
        ax.axvline(23700, color='k', lw=0.5, ls='--')
        ax.set_xlim(12000, 24000)
        ax.set_title('%s code 63, open (dotted: AK4619 ADC passband edge 22.1k; '
                     'dashed: -3 dB 23.7k)' % k[:4].replace('MIC', 'MIC '),
                     fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7, loc='upper left')
    for ax in axs[1]:
        ax.set_xlabel('Hz (linear)')
    for ax in axs[:, 0]:
        ax.set_ylabel('input-referred dBu/sqrt(Hz)')
    fig.suptitle('12-24 kHz zoom: the group component moves from 16.6-18.9 kHz '
                 '(S160) to the Nyquist edge (S162). OPEN inputs, NOT EIN')
    fig.tight_layout()
    fig.savefig(os.path.join(out, 's162-before-after-12-24k.png'), dpi=110)
    plt.close(fig)

    fig, axs = plt.subplots(1, 2, figsize=(13, 4.8), sharey=True)
    k = 16
    for ax, tag, R in ((axs[0], 'S160 before', B), (axs[1], 'S162 Schottky', C)):
        ref = R['MIC5_c63']
        for key in ('MIC1_c63', 'MIC2_c63', 'MIC3_c63', 'MIC4_c63'):
            r = R[key]
            a = np.convolve(dens(r), np.ones(k) / k, mode='same')
            b = np.convolve(dens(ref), np.ones(k) / k, mode='same')
            ax.semilogx(r['f'][k:-k], (a - b)[k:-k], lw=0.8,
                        label='%s - MIC 5' % key[:4])
        ax.axhline(0, color='k', lw=0.5)
        ax.set_xlim(1000, 24000)
        ax.set_title('%s: excess over MIC 5, code 63' % tag)
        ax.set_xlabel('Hz')
        ax.grid(True, which='both', alpha=0.3)
        ax.legend(fontsize=8)
    axs[0].set_ylabel('dB, input-referred, 47 Hz smoothing')
    fig.tight_layout()
    fig.savefig(os.path.join(out, 's162-excess-vs-mic5-before-after.png'),
                dpi=110)
    plt.close(fig)

    fig, axs = plt.subplots(4, 1, figsize=(11, 12), sharex=True)
    for inp, mk, col in (('MIC 2', 'o', 'tab:blue'), ('MIC 4', 's', 'tab:green')):
        xs = [x for x in D if x['inp'] == inp]
        t = [x['t'] / 60.0 for x in xs]
        axs[0].plot(t, [x['hump_f'] for x in xs], mk + '-', color=col, ms=4,
                    lw=0.8, label='S162 %s' % inp)
        axs[1].plot(t, [x['hump_x'] for x in xs], mk + '-', color=col, ms=4,
                    lw=0.8, label='S162 %s' % inp)
        axs[2].plot(t, [x['oct'] for x in xs], mk + '-', color=col, ms=4,
                    lw=0.8, label='S162 %s' % inp)
        axs[3].plot(t, [x['top'] for x in xs], mk + '-', color=col, ms=4,
                    lw=0.8, label='S162 %s' % inp)
    for inp, mk in (('MIC 2', 'x'), ('MIC 4', '+')):
        xs = [x for x in AB if x['inp'] == inp]
        t = [x['t'] / 60.0 for x in xs]
        for ax, key in zip(axs, ('hump_f', 'hump_x', 'oct', 'top')):
            ax.plot(t, [x[key] for x in xs], mk, color='tab:red', ms=7,
                    label='S160 %s (before, codes 63/48/32, t approx.)' % inp)
    axs[0].set_ylabel('hump peak Hz (14-23.9k)')
    axs[1].set_ylabel('peak excess over MIC 5 dB')
    axs[2].set_ylabel('10-20 kHz octave over MIC 5 dB')
    axs[3].set_ylabel('20-24 kHz over MIC 5 dB')
    axs[3].set_xlabel('minutes since rails-up')
    for ax in axs:
        ax.grid(True, alpha=0.3)
        ax.legend(fontsize=7)
    axs[0].set_title('MW-D24-2 drift map from a cold rails-up, open inputs, '
                     'code 63 (S162) with S160 A/B points')
    fig.tight_layout()
    fig.savefig(os.path.join(out, 's162-drift-map.png'), dpi=110)
    plt.close(fig)
    print('\nplots: %s' % out)


if __name__ == '__main__':
    main()
