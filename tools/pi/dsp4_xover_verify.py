#!/usr/bin/env python3
"""dsp4_xover_verify.py — the main crossover's LR4 split, scored on the part.

Same three questions dsp4_geq_verify.py asks, on the family that was
inert for the same reason:

  COEFFS    the 20 words the part designed into _xover_coeffs_next
            against tools/dsp/xover_ref.design_set. A relative bar
            (4 ulps): the SHARC computes in 40-bit registers and stores
            float32, and the sine/vercosine series are 1.6e-11 off libm,
            which is inside a float32 ulp everywhere in the domain.
  RESPONSE  the magnitude of the LP and the HP path, from the
            coefficients READ BACK OFF THE PART, against the model's --
            and the two LR4 properties that say it is really a crossover:
            each path 6.02 dB down at the corner, and the two summing
            flat across the band.
  AUDIO     an impulse response captured at _buf_lp and _buf_hp. The LP
            path must roll off above the corner and the HP below it, and
            the split must MOVE when the corner does.

NEGATIVE CONTROLS:
  * OUT OF DOMAIN. The eight CrossoverFreq/CrossoverSlope cells of the
    four main sections all resolve to ONE address in the landed
    contract. A word outside the frequency table's 50-500 Hz is
    therefore not a frequency, and writing a slope must leave the split
    exactly where the last legal frequency put it -- checked word for
    word, not by eye.
  * NEVER SET. Before any legal frequency arrives the banks must hold
    the compiled identity and the node must pass its input through, so
    the design cannot be credited for a split that was there anyway.
"""

import argparse
import cmath
import json
import math
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')

import dsp4_scope as S
import xover_ref as X
from dsp4_conform import Part, SPI_ERR_COUNT, f32

BUS_AMP = 0x08000000
CAPTURE_REST = 0.50
SETTLE = 0.60
FS = 48000.0
COEFF_ULPS = 4
RESP_BAR_DB = 0.01
CORNER_BAR_DB = 0.05
SUM_BAR_DB = 0.05
AUDIO_BAR_DB = 0.60      # Q4.28 capture, finite window, block-rate publish


def ulps(a, b):
    ia = struct.unpack('<i', struct.pack('<f', float(a)))[0]
    ib = struct.unpack('<i', struct.pack('<f', float(b)))[0]
    if ia < 0:
        ia = -2147483648 - ia
    if ib < 0:
        ib = -2147483648 - ib
    return abs(ia - ib)


def from_f32w(w):
    return struct.unpack('<f', struct.pack('<I', w & 0xFFFFFFFF))[0]


def q428(w):
    v = w - (1 << 32) if w & 0x80000000 else w
    return v / float(1 << 28)


def resp(coeffs_offset, f):
    z = cmath.exp(-2j * math.pi * f / FS)
    h = 1.0 + 0j
    for i in range(0, len(coeffs_offset), 5):
        b0, n1, n2, c1, c2 = coeffs_offset[i:i + 5]
        b1 = n1 - 2 * b0
        b2 = n2 + b0
        a1 = c1 - 2
        a2 = 1 - c2
        h *= (b0 + b1 * z + b2 * z * z) / (1 + a1 * z + a2 * z * z)
    return h


def db(x):
    return 20 * math.log10(abs(x)) if abs(x) > 0 else -999.0


def dft(samples, f):
    w = -2j * math.pi * f / FS
    return sum(x * cmath.exp(w * n) for n, x in enumerate(samples))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--landed', default='landed-d24.json')
    ap.add_argument('--node', default='C2_MAIN_XOVER')
    ap.add_argument('--cell', default='MainL001CrossoverFreq001')
    ap.add_argument('--slope-cell', default='MainL001CrossoverSlope001')
    ap.add_argument('--n', type=int, default=1024)
    ap.add_argument('--json', default='')
    args = ap.parse_args()

    sys.path.insert(0, '.')
    from dsp4_family_verify import Landed
    L = Landed(args.landed)
    part = Part(2)
    part.sc.check_chip()
    print('chip 2 ready; contract %s sha %s' % (L.pin, L.sha256[:12]))
    sym = part.sc.sym
    nid = args.node

    need = ['_xover_freq_' + nid, '_xover_dirty_' + nid,
            '_xover_coeffs_next_' + nid, '_xover_lp_A_' + nid,
            '_xover_hp_A_' + nid, '_xover_active_' + nid,
            '_buf_lp_' + nid, '_buf_hp_' + nid, '_buf_' + nid]
    miss = [s for s in need if s not in sym] + \
           [c for c in (args.cell, args.slope_cell) if not L.has(c)]
    if miss:
        print('MISSING: %s' % ', '.join(miss))
        return 2

    def peekn(s, n, off=0):
        return [part.sc.peek(sym[s] + off + i) for i in range(n)]

    def staged():
        return [from_f32w(w) for w in peekn('_xover_coeffs_next_' + nid, 20)]

    def live():
        act = part.sc.peek(sym['_xover_active_' + nid])
        suf = 'B' if act else 'A'
        lp = [from_f32w(w) for w in peekn('_xover_lp_%s_%s' % (suf, nid), 10)]
        hp = [from_f32w(w) for w in peekn('_xover_hp_%s_%s' % (suf, nid), 10)]
        return suf, lp + hp

    def setfreq(v):
        part.write(L.addr(args.cell), f32(v), 0)
        time.sleep(SETTLE)

    def setslope(v):
        part.write(L.addr(args.slope_cell), int(v), 0)
        time.sleep(SETTLE)

    for cell, val in (('Main001Level001', f32(1.0)), ('Main001Mute001', 0)):
        if L.has(cell):
            part.write(L.addr(cell), val, 0)
    time.sleep(0.2)
    inj = sym['_rx_ic_slot_C2_RECV_MAIN_L']

    def capture(src, n):
        time.sleep(CAPTURE_REST)
        part.sc.arm(sym[src], inj, BUS_AMP, 1)
        part.sc.wait()
        out = []
        for i in range(n):
            part.sc.wr(S.SCOPE_RD, i)
            out.append(part.sc.rd(S.SCOPE_DATA))
        return [q428(w) for w in out]

    out = {'node': nid, 'contract': {'pin': L.pin, 'sha256': L.sha256},
           'bar': {'coeff_ulps': COEFF_ULPS, 'resp_db': RESP_BAR_DB,
                   'corner_db': CORNER_BAR_DB, 'sum_db': SUM_BAR_DB,
                   'audio_db': AUDIO_BAR_DB},
           'points': []}
    err0 = part.sc.rd(SPI_ERR_COUNT)

    # ---- NEVER SET: identity, and the node passes through -------------
    suf, lv = live()
    ident = all(abs(v - X.IDENTITY[i % 5]) < 1e-12 for i, v in enumerate(lv))
    up = capture('_buf_C2_MAIN_DLY', 64)
    lpc = capture('_buf_lp_' + nid, 64)
    eq = sum(1 for a, b in zip(up, lpc) if a == b)
    print('')
    print('never set (freq 0.0) — banks must be the compiled identity')
    print('    live bank %s %s;  LP path %d/64 samples equal to the input'
          % (suf, 'identity' if ident else 'NOT identity', eq))
    out['never_set'] = {'bank': suf, 'identity': ident, 'passthrough': eq,
                        'peak': max((abs(v) for v in lpc), default=0.0)}

    ok = ident and eq == 64 and out['never_set']['peak'] > 0

    # ---- the corners, AT EVERY SLOPE THE NODE HOLDS --------------------
    # The slope has its own word since 2026-09-09; before that all eight
    # crossover cells shared one address and only LR4 was reachable.
    print('')
    for slope in sorted(X.XOVER_SLOPES):
      setslope(slope)
      print('  slope %d dB/oct' % slope)
      for f0 in (80.0, 120.0, 250.0, 500.0, 50.0):
        setfreq(f0)
        want = X.design_set(f0, slope=slope)
        got = staged()
        wu = max(ulps(a, b) for a, b in zip(got, want))
        suf, lv = live()
        lvu = max(ulps(a, b) for a, b in zip(lv, got))
        wl, wh = lv[:10], lv[10:]
        cl, ch = db(resp(wl, f0)), db(resp(wh, f0))
        rerr = 0.0
        for k in range(-16, 17):
            f = f0 * 2.0 ** (k / 4.0)
            if not 10.0 < f < FS / 2:
                continue
            rerr = max(rerr, abs(db(resp(wl, f)) - db(resp(want[:10], f))),
                       abs(db(resp(wh, f)) - db(resp(want[10:], f))))
        serr = 0.0
        for k in range(-16, 17):
            f = f0 * 2.0 ** (k / 4.0)
            if not 10.0 < f < FS / 2:
                continue
            serr = max(serr, abs(db(resp(wl, f) + resp(wh, f))))
        rec = {'slope': slope, 'f0': f0, 'staged_ulps': wu,
               'live_vs_staged_ulps': lvu,
               'lp_at_corner_db': cl, 'hp_at_corner_db': ch,
               'resp_err_db': rerr, 'sum_err_db': serr, 'bank': suf}
        rec['ok'] = (wu <= COEFF_ULPS and lvu == 0
                     and abs(cl + 6.0206) <= CORNER_BAR_DB
                     and abs(ch + 6.0206) <= CORNER_BAR_DB
                     and rerr <= RESP_BAR_DB and serr <= SUM_BAR_DB)
        ok = ok and rec['ok']
        out['points'].append(rec)
        print('    %6.1f Hz  staged %d ulp, live==staged %s  LP %+.3f dB / '
              'HP %+.3f dB at the corner  resp %.5f dB  LP+HP %.5f dB  -> %s'
              % (f0, wu, 'yes' if lvu == 0 else 'NO (%d ulp)' % lvu, cl, ch,
                 rerr, serr, 'PASS' if rec['ok'] else 'FAIL'))

    # ---- THE SLOPE'S TWO NEGATIVE CONTROLS -----------------------------
    # (1) A SLOPE THE NODE DOES NOT HOLD is ignored, not clamped: 6 and
    #     18 are not Linkwitz-Riley alignments and 3 is not a slope at
    #     all, so the coefficients must not move a word.
    # (2) WRITING A SLOPE MUST NOT MOVE THE FREQUENCY. That is the whole
    #     defect this word was cut to fix -- until 2026-09-09 both cells
    #     resolved to one address and a slope write landed the integer 24
    #     where a corner belongs.
    print('')
    setslope(24)
    setfreq(250.0)
    before = staged()
    freq_before = from_f32w(part.sc.peek(sym['_xover_freq_' + nid]))
    bad_frozen = True
    for bad in (6, 18, 3):
        setslope(bad)
        if staged() != before:
            bad_frozen = False
        print('  slope %2d (not an LR alignment) — coefficients %s'
              % (bad, 'unmoved' if staged() == before else 'MOVED'))
    setslope(12)
    freq_after = from_f32w(part.sc.peek(sym['_xover_freq_' + nid]))
    moved_at_12 = staged() != before
    freq_held = freq_after == freq_before == 250.0
    print('  slope 12 (LR2) — coefficients %s, frequency %.1f -> %.1f Hz %s'
          % ('MOVED (as they must)' if moved_at_12 else 'DID NOT MOVE',
             freq_before, freq_after, 'held' if freq_held else 'DISTURBED'))
    out['slope_controls'] = {'ignored_not_clamped': bad_frozen,
                             'slope_moves_design': moved_at_12,
                             'freq_before': freq_before,
                             'freq_after': freq_after,
                             'freq_held': freq_held}
    ok = ok and bad_frozen and moved_at_12 and freq_held
    setslope(24)

    # ---- AUDIO: the split, and that it moves with the corner -----------
    print('')
    audio = []
    for f0 in (120.0, 400.0):
        setfreq(f0)
        lp = capture('_buf_lp_' + nid, args.n)
        hp = capture('_buf_hp_' + nid, args.n)
        ref = capture('_buf_C2_MAIN_DLY', args.n)
        row = {'f0': f0, 'points': []}
        for f, tag in ((f0 / 4.0, 'two oct below'), (f0, 'corner'),
                       (f0 * 4.0, 'two oct above')):
            if not 10.0 < f < FS / 2:
                continue
            r = abs(dft(ref, f))
            gl = db(dft(lp, f) / r) if r else float('nan')
            gh = db(dft(hp, f) / r) if r else float('nan')
            ml = db(resp(X.design_set(f0)[:10], f))
            mh = db(resp(X.design_set(f0)[10:], f))
            row['points'].append({'f': f, 'tag': tag, 'lp_db': gl,
                                  'hp_db': gh, 'lp_model': ml,
                                  'hp_model': mh})
            good = (abs(gl - ml) <= AUDIO_BAR_DB
                    and abs(gh - mh) <= AUDIO_BAR_DB)
            ok = ok and good
            print('  f0 %5.1f  %-14s %8.1f Hz  LP %+7.2f (model %+7.2f)  '
                  'HP %+7.2f (model %+7.2f)  -> %s'
                  % (f0, tag, f, gl, ml, gh, mh, 'PASS' if good else 'FAIL'))
        audio.append(row)
    out['audio'] = audio

    part.write(L.addr(args.cell), f32(0.0), 0)
    out['spi_err_delta'] = (part.sc.rd(SPI_ERR_COUNT) - err0) & 0xFFFFFFFF
    ok = ok and out['spi_err_delta'] == 0
    out['verdict'] = 'XOVER_DESIGN_OK' if ok else 'XOVER_DESIGN_FAIL'
    print('')
    print(out['verdict'])
    if args.json:
        with open(args.json, 'w') as fh:
            json.dump(out, fh, indent=1)
        print('wrote %s' % args.json)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
