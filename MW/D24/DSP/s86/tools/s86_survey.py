#!/usr/bin/env python3
"""s86_survey.py — all 24 D24 preamps, noise at code 63 and code 0, one 595
image per reading, on lanes that are now known to carry samples.

Gate 3 asks for the preamp survey's typical figure to be re-stated on the
fixed pair. This takes it the way S55 took its rows -- the register under test
alone open, phantom off, the INSTR byte 0x00, TEST_MEAS on that channel's own
strip -- but for all 24 XLRs in one pass, so the three AK5558 banks can be
compared against each other in one rail state and one boot.

It reports dBFS only. The dBu conversion needs the channel's OWN loop gain
(S54 T1) and only MIC 5 has one on record; the arithmetic is in s86_gate3.py
and is deliberately not repeated here on borrowed calibration.

The number that matters per channel is the RISE from code 0 to code 63: a
preamp whose noise floor does not move with 63 codes of gain is not reaching
its converter, whatever the absolute figure says.
"""
import json
import math
import os
import sys
import time

_ARGV = list(sys.argv)
os.environ.setdefault('SYMDIR', '/home/app/s83tn')
sys.path.insert(0, '/home/app/s55')
sys.path.insert(0, '/home/app/s54')
import s54lib as T                                                  # noqa: E402
import s55_chain as CH                                              # noqa: E402
import d24_inputs as D24                                            # noqa: E402

P = lambda *a: print(*a, flush=True)                                # noqa: E731
CODES = [int(c) for c in (os.environ.get('CODES') or '63,0').split(',')]
WINDOWS = int(os.environ.get('WINDOWS') or 6)


def chain_only(send_pos, code):
    img = [0x01] * 25
    img[send_pos] = CH.byte(mute=0, gain=code)
    img[24] = 0x00
    for _ in range(4):
        ok, got = CH.send(img)
        if ok:
            return img
    raise SystemExit('595 image for send %d code %d NOT VERIFIED' % (send_pos, code))


def main():
    outdir = '/home/app/s86'
    os.makedirs(outdir, exist_ok=True)
    R = T.Rig(os.path.join(outdir, 's86_survey.jsonl'))
    R.osc(on=False)
    rows = []
    P('%-5s %-4s %-6s %-5s %-4s %-5s %s'
      % ('xlr', 'mic', 'preamp', 'ADC', 'ad', 'strip',
         '  '.join('code %-2d dBFS' % c for c in CODES) + '   rise dB'))
    for x in D24.XLRS:
        strip = x.strip(D24.D24_INPUT_PATCH)
        vals = {}
        for code in CODES:
            chain_only(x.send, code)
            R.code = code
            R.meas(strip)
            m = R.windows(WINDOWS, settle_windows=12,
                          tag='s86_survey_%s_c%d' % (x.xlr, code))
            vals[code] = {'noise': T.summ(m, 'noise'), 'rms': T.summ(m, 'rms'),
                          'spread': T.spread(m, 'rms')}
        rise = (vals[CODES[0]]['noise'] - vals[CODES[-1]]['noise']
                if len(CODES) > 1 else None)
        rows.append({'xlr': x.xlr, 'panel': x.panel, 'preamp': x.preamp,
                     'adc': x.adc, 'ad': x.ad, 'slot': x.slot, 'rx': x.rx,
                     'send': x.send, 'strip': strip,
                     'by_code': {str(k): v for k, v in vals.items()},
                     'rise_db': rise})
        P('%-5s %-4d %-6s %-5s %-4d %-5d %s   %s'
          % (x.xlr, x.panel, x.preamp, x.adc, x.ad, strip,
             '  '.join('%11.2f' % vals[c]['noise'] for c in CODES),
             ('%7.2f' % rise) if rise is not None else '      -'))

    P('')
    for adc in ('U15', 'U39', 'U60'):
        g = [r for r in rows if r['adc'] == adc]
        if not g:
            continue
        rs = [r['rise_db'] for r in g if r['rise_db'] is not None]
        n63 = [r['by_code'][str(CODES[0])]['noise'] for r in g]
        P('%s (ad[%d], %d channels): code %d noise %.2f..%.2f dBFS, '
          'gain rise %.2f..%.2f dB, median rise %.2f'
          % (adc, g[0]['ad'], len(g), CODES[0], min(n63), max(n63),
             min(rs), max(rs), sorted(rs)[len(rs) // 2]))
    json.dump({'codes': CODES, 'windows': WINDOWS, 'rows': rows},
              open(os.path.join(outdir, 's86_survey.json'), 'w'), indent=1)
    P('\nwrote %s/s86_survey.json' % outdir)


if __name__ == '__main__':
    main()
