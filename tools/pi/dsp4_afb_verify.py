#!/usr/bin/env python3
"""dsp4_afb_verify.py — the anti-feedback notch design, scored on the part.

Until 2026-09-08 every ANTI_FB node in the product passed its input
through. The eighteen landed parameter cells always dispatched to the
right symbols -- the family walk read 1000.0 Hz, -18.0 dB and Q 4.0 back
off the part at `_afb_notch_freq/_gain/_q` -- and nothing turned them
into coefficients: `_afb_coeffs_next` never moved and both banks stayed
at the compiled identity. `_afb_on` took its write and was read by no
emitted line anywhere in the tree.

The design now runs ON THE DSP (src/lib/afb_design_fx.asm), because
eighteen addresses cannot also carry thirty coefficient words and a swap
trigger. This scores it the way dsp4_geq_verify.py scores the graphic
EQ's, three ways that fail differently on purpose:

  COEFFS    the 30 words the part designed into _afb_coeffs_next,
            against tools/dsp/afb_ref.kernel_set -- the model of the
            expression the kernel evaluates. NOT bit-exact and not
            claimed to be: the SHARC computes in 40-bit registers and
            stores float32, so the bar is 4 ulps.

  RESPONSE  the magnitude of what the part designed, at each notch
            centre and half and twice it, against the model's, computed
            from the coefficients READ BACK OFF THE PART.

  AUDIO     an impulse response captured at the node's own buffer and
            transformed at the notch centre. Coefficients that are right
            in memory and never reach a sample is the exact defect this
            bar exists because of.

THREE NEGATIVE CONTROLS, each of which has to fail if the tool is blind:
  * OFF: `AntiFbOn = 0` with six real notches written must design the
    COMPILED identity, and the node's output must equal its input in
    every captured sample. This is the switch the previous firmware did
    not read at all.
  * ZERO DEPTH: On = 1 with every NotchGain at 0 dB is also the exact
    identity -- a notch with no depth is not a filter.
  * OFF-CENTRE: the notch response is also scored two octaves above the
    centre, where it must be within a fraction of a dB of flat. A design
    that attenuated everything equally would pass a single-point check
    at the right frequency.

Run through afbverify.sh, which builds, stages, boots and configures.
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
import afb_ref as A
from dsp4_conform import Part, SPI_ERR_COUNT, f32

BUS_AMP = 0x08000000
CAPTURE_REST = 0.50
SETTLE_DESIGN = 0.60          # a crossfade is 576 samples; give it blocks
FS = 48000.0

RESP_BAR_DB = 0.05            # the dispatch's bar for the notch response
COEFF_ULPS = 4
AUDIO_BAR_DB = 0.60           # a Q4.28 capture over a finite window, and a
                              # high-Q notch is a narrow thing to resolve
FLAT_BAR_DB = 0.05            # two octaves above the notch


def to_f32(x):
    return struct.unpack('<f', struct.pack('<f', float(x)))[0]


def ulps(a, b):
    ia = struct.unpack('<i', struct.pack('<f', to_f32(a)))[0]
    ib = struct.unpack('<i', struct.pack('<f', to_f32(b)))[0]
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


def resp_db(coeffs_offset, f, fs=FS):
    z = cmath.exp(-2j * math.pi * f / fs)
    h = 1.0 + 0j
    for i in range(0, len(coeffs_offset), 5):
        b0, n1, n2, c1, c2 = coeffs_offset[i:i + 5]
        b1 = n1 - 2 * b0
        b2 = n2 + b0
        a1 = c1 - 2
        a2 = 1 - c2
        num = b0 + b1 * z + b2 * z * z
        den = 1 + a1 * z + a2 * z * z
        if den == 0:
            return float('nan')
        h *= num / den
    return 20 * math.log10(abs(h)) if abs(h) > 0 else -999.0


def goertzel(samples, f, fs=FS):
    w = -2j * math.pi * f / fs
    acc = 0j
    for n, x in enumerate(samples):
        acc += x * cmath.exp(w * n)
    return acc


def _looks_like_header(w):
    """DSP4_BQ_GUARD puts a headroom shift count in front of the bank.
    b0 of any designed notch is within a factor of two of 1.0, so its
    exponent field is nowhere near zero."""
    return (w >> 23) & 0xFF < 0x60


class Afb:
    """One ANTI_FB node: its landed cells and the symbols behind them."""

    def __init__(self, part, L, node, prefix, notches):
        self.part = part
        self.L = L
        self.node = node
        self.n = notches
        self.c_on = '%sAntiFbOn001' % prefix
        self.c_freq = ['%sAntiFbNotchFreq%03d' % (prefix, i + 1)
                       for i in range(notches)]
        self.c_gain = ['%sAntiFbNotchGain%03d' % (prefix, i + 1)
                       for i in range(notches)]
        self.c_q = ['%sAntiFbNotchQ%03d' % (prefix, i + 1)
                    for i in range(notches)]
        self.sym_next = '_afb_coeffs_next_%s' % node
        self.sym_a = '_afb_coeffs_A_%s' % node
        self.sym_b = '_afb_coeffs_B_%s' % node
        self.sym_freq = '_afb_notch_freq_%s' % node
        self.sym_gain = '_afb_notch_gain_%s' % node
        self.sym_q = '_afb_notch_q_%s' % node
        self.sym_on = '_afb_on_%s' % node
        self.sym_dirty = '_afb_dirty_%s' % node
        self.sym_active = '_afb_active_%s' % node
        self.buf = '_buf_%s' % node

    def missing(self):
        out = [c for c in ([self.c_on] + self.c_freq + self.c_gain + self.c_q)
               if not self.L.has(c)]
        out += [s for s in (self.sym_next, self.sym_a, self.sym_b,
                            self.sym_freq, self.sym_gain, self.sym_q,
                            self.sym_on, self.sym_dirty)
                if s not in self.part.sc.sym]
        return out

    def write(self, freqs, gains, qs, on=1):
        """The ON switch goes LAST on purpose: it is in the dirty run, so
        whatever order the parameters landed in, the design runs once
        more after all of them are in place."""
        for cell, v in zip(self.c_freq, freqs):
            self.part.write(self.L.addr(cell), f32(v), 0)
        for cell, v in zip(self.c_q, qs):
            self.part.write(self.L.addr(cell), f32(v), 0)
        for cell, v in zip(self.c_gain, gains):
            self.part.write(self.L.addr(cell), f32(v), 0)
        self.part.write(self.L.addr(self.c_on), on, 0)
        time.sleep(SETTLE_DESIGN)

    def peekn(self, sym, n):
        base = self.part.sc.sym[sym]
        return [self.part.sc.peek(base + i) for i in range(n)]

    def params_readback(self):
        return ([from_f32w(w) for w in self.peekn(self.sym_freq, self.n)],
                [from_f32w(w) for w in self.peekn(self.sym_gain, self.n)],
                [from_f32w(w) for w in self.peekn(self.sym_q, self.n)])

    def designed(self):
        return [from_f32w(w) for w in self.peekn(self.sym_next, 5 * self.n)]

    def live(self):
        act = self.part.sc.peek(self.part.sc.sym[self.sym_active])
        sym = self.sym_b if act else self.sym_a
        got = self.peekn(sym, 5 * self.n + 1)
        body = got[1:] if _looks_like_header(got[0]) else got[:-1]
        return sym, [from_f32w(w) for w in body]


def capture(part, inj, src, n, mode=1):
    time.sleep(CAPTURE_REST)
    part.sc.arm(part.sc.sym[src], inj, BUS_AMP, mode)
    part.sc.wait()
    out = []
    for i in range(n):
        part.sc.wr(S.SCOPE_RD, i)
        out.append(part.sc.rd(S.SCOPE_DATA))
    return out


def score_set(afb, freqs, gains, qs, log=print):
    want = A.kernel_set(freqs, gains, qs, on=True)
    got = afb.designed()
    rec = {'freqs': list(freqs), 'gains': list(gains), 'qs': list(qs),
           'words': len(want)}

    worst_u, worst_i = 0, -1
    for i, (a, b) in enumerate(zip(got, want)):
        u = ulps(a, b)
        if u > worst_u:
            worst_u, worst_i = u, i
    rec['worst_ulps'] = worst_u
    rec['worst_word'] = worst_i
    rec['coeff_ok'] = worst_u <= COEFF_ULPS

    worst_db, worst_f = 0.0, 0.0
    for f0 in freqs:
        for f in (f0 / 2.0, f0, f0 * 2.0):
            if f >= FS / 2 or f < 10.0:
                continue
            d = resp_db(got, f) - resp_db(want, f)
            if abs(d) > abs(worst_db):
                worst_db, worst_f = d, f
    rec['worst_resp_db'] = worst_db
    rec['worst_resp_f'] = worst_f
    rec['resp_ok'] = abs(worst_db) <= RESP_BAR_DB

    # THE DEPTH ITSELF, at each notch centre, against what was asked for.
    depths = []
    for f0, g in zip(freqs, gains):
        depths.append({'f': f0, 'asked_db': g,
                       'model_db': resp_db(want, f0),
                       'part_db': resp_db(got, f0)})
    rec['depths'] = depths
    rec['depth_ok'] = all(abs(d['part_db'] - d['model_db']) <= RESP_BAR_DB
                          for d in depths)

    log('    coeffs worst %d ulp (word %d)  response worst %+.5f dB at '
        '%.1f Hz (bar %.3f)  -> %s'
        % (worst_u, worst_i, worst_db, worst_f, RESP_BAR_DB,
           'PASS' if rec['coeff_ok'] and rec['resp_ok']
           and rec['depth_ok'] else 'FAIL'))
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--landed', default='landed-d24.json')
    ap.add_argument('--node', default='C2_AUX_AFB_01')
    ap.add_argument('--prefix', default='Aux001')
    ap.add_argument('--upstream', default='_buf_C2_AUX_GEQ_01')
    ap.add_argument('--inject', default='_rx_ic_slot_C2_RECV_AUX_01')
    ap.add_argument('--notches', type=int, default=6)
    ap.add_argument('--n', type=int, default=1024)
    ap.add_argument('--json', default='')
    args = ap.parse_args()

    sys.path.insert(0, '.')
    from dsp4_family_verify import Landed
    L = Landed(args.landed)

    part = Part(2)
    part.sc.check_chip()
    print('chip 2 ready; contract %s sha %s' % (L.pin, L.sha256[:12]))

    afb = Afb(part, L, args.node, args.prefix, args.notches)
    miss = afb.missing()
    if miss:
        print('MISSING: %s' % ', '.join(miss[:6]))
        return 2

    out = {'node': args.node, 'notches': args.notches,
           'contract': {'pin': L.pin, 'sha256': L.sha256}, 'sets': [],
           'bar': {'coeff_ulps': COEFF_ULPS, 'resp_db': RESP_BAR_DB,
                   'audio_db': AUDIO_BAR_DB, 'flat_db': FLAT_BAR_DB}}

    for cell, val in (('%sLevel001' % args.prefix, f32(1.0)),
                      ('%sMute001' % args.prefix, 0)):
        if L.has(cell):
            part.write(L.addr(cell), val, 0)
    time.sleep(0.2)
    inj = part.sc.sym[args.inject]
    err0 = part.sc.rd(SPI_ERR_COUNT)

    # A real six-notch set, spread across the contract's frequency domain.
    FREQS = [80.0, 250.0, 630.0, 1600.0, 4000.0, 10000.0]
    QS = [2.0, 4.0, 8.0, 4.0, 12.0, 6.0]
    GAINS = [-18.0, -12.0, -6.0, -18.0, -9.0, -3.0]

    # ---- NEGATIVE CONTROL 1: the ON switch ----------------------------
    print('')
    print('AntiFbOn = 0, with six real notches written — the switch the')
    print('previous firmware did not read at all')
    afb.write(FREQS, GAINS, QS, on=0)
    pf, pg, pq = afb.params_readback()
    off = afb.designed()
    ident_ok = all(abs(v - A.IDENTITY[i % 5]) < 1e-12
                   for i, v in enumerate(off))
    sym, livebank = afb.live()
    live_ok = all(abs(v - A.IDENTITY[i % 5]) < 1e-12
                  for i, v in enumerate(livebank))
    up = capture(part, inj, args.upstream, 64)
    here = capture(part, inj, afb.buf, 64)
    pass_ok = sum(1 for a, b in zip(up, here) if a == b)
    print('    parameters landed: f %s' % ' '.join('%.0f' % v for v in pf))
    print('                       g %s' % ' '.join('%.1f' % v for v in pg))
    print('                       Q %s' % ' '.join('%.1f' % v for v in pq))
    print('    staged identity %s;  live bank %s %s;  %d/64 samples equal '
          'to the input' % ('YES' if ident_ok else 'NO', sym,
                            'identity' if live_ok else 'NOT identity',
                            pass_ok))
    out['off'] = {'staged_identity': ident_ok, 'live_bank': sym,
                  'live_identity': live_ok, 'passthrough_words': pass_ok,
                  'peak': max((abs(q428(w)) for w in here), default=0.0),
                  'params': {'freq': pf, 'gain': pg, 'q': pq}}

    # ---- NEGATIVE CONTROL 2: On = 1, zero depth ------------------------
    print('')
    print('AntiFbOn = 1, every NotchGain 0 dB — a notch with no depth is')
    print('not a filter')
    afb.write(FREQS, [0.0] * args.notches, QS, on=1)
    zero = afb.designed()
    zero_ok = all(abs(v - A.IDENTITY[i % 5]) < 1e-12
                  for i, v in enumerate(zero))
    zsym, zlive = afb.live()
    zlive_ok = all(abs(v - A.IDENTITY[i % 5]) < 1e-12
                   for i, v in enumerate(zlive))
    zhere = capture(part, inj, afb.buf, 64)
    zup = capture(part, inj, args.upstream, 64)
    zpass = sum(1 for a, b in zip(zup, zhere) if a == b)
    print('    staged identity %s;  live bank %s %s;  %d/64 samples equal '
          'to the input' % ('YES' if zero_ok else 'NO', zsym,
                            'identity' if zlive_ok else 'NOT identity', zpass))
    out['zero_depth'] = {'staged_identity': zero_ok, 'live_bank': zsym,
                         'live_identity': zlive_ok,
                         'passthrough_words': zpass}

    # ---- the parameter vectors -----------------------------------------
    vectors = [
        ('six notches across 80 Hz .. 10 kHz', FREQS, GAINS, QS),
        ('all six at -18 dB, the deepest the contract allows',
         FREQS, [-18.0] * args.notches, QS),
        ('one notch only (1 kHz, Q 10, -18 dB)',
         [1000.0] + FREQS[1:], [-18.0] + [0.0] * (args.notches - 1),
         [10.0] + QS[1:]),
        ('the domain corners (40 Hz Q 1, 12 kHz Q 20)',
         [40.0, 12000.0, 40.0, 12000.0, 1000.0, 1000.0],
         [-18.0, -18.0, -6.0, -6.0, -12.0, -1.0],
         [1.0, 20.0, 20.0, 1.0, 5.0, 15.0]),
        ('out of domain — 20 Hz and 20 kHz, Q 0.2 and 40, +6 dB: CLAMPED',
         [20.0, 20000.0, 1000.0, 1000.0, 1000.0, 1000.0],
         [-18.0, -18.0, -18.0, 6.0, -30.0, -6.0],
         [0.2, 40.0, 4.0, 4.0, 4.0, 4.0]),
    ]
    print('')
    for name, fs_, gs_, qs_ in vectors:
        print('  %s' % name)
        afb.write(fs_, gs_, qs_, on=1)
        rec = score_set(afb, fs_, gs_, qs_)
        rec['name'] = name
        out['sets'].append(rec)

    # ---- AUDIO: the impulse response of one deep notch -----------------
    print('')
    f0, q0, g0 = 1000.0, 8.0, -18.0
    one_f = [f0] + [40.0] * (args.notches - 1)
    one_g = [g0] + [0.0] * (args.notches - 1)
    one_q = [q0] + [4.0] * (args.notches - 1)
    afb.write(one_f, one_g, one_q, on=1)
    ir = capture(part, inj, afb.buf, args.n)
    afb.write(one_f, [0.0] * args.notches, one_q, on=1)
    ir_flat = capture(part, inj, afb.buf, args.n)
    xs = [q428(w) for w in ir]
    xf = [q428(w) for w in ir_flat]
    want = A.kernel_set(one_f, one_g, one_q, on=True)
    audio = []
    for f, tag in ((f0 / 4.0, 'two below'), (f0, 'centre'),
                   (f0 * 4.0, 'two above')):
        a = goertzel(xs, f)
        c = goertzel(xf, f)
        got = 20 * math.log10(abs(a) / abs(c)) if abs(c) > 0 else float('nan')
        mdl = resp_db(want, f)
        bar = AUDIO_BAR_DB if tag == 'centre' else FLAT_BAR_DB + AUDIO_BAR_DB
        audio.append({'f': f, 'tag': tag, 'measured_db': got,
                      'model_db': mdl, 'err_db': got - mdl, 'bar': bar})
        print('    %-10s %8.1f Hz  measured %+7.3f dB   model %+7.3f dB   '
              'err %+.3f dB  -> %s'
              % (tag, f, got, mdl, got - mdl,
                 'PASS' if abs(got - mdl) <= bar else 'FAIL'))
    out['audio'] = {'f0': f0, 'q': q0, 'gain': g0, 'n': args.n,
                    'points': audio,
                    'peak': max((abs(v) for v in xs), default=0.0)}

    # leave the node as the product boots it
    afb.write([0.0] * args.notches, [0.0] * args.notches,
              [0.0] * args.notches, on=0)

    out['spi_err_delta'] = (part.sc.rd(SPI_ERR_COUNT) - err0) & 0xFFFFFFFF

    ok = (out['off']['staged_identity'] and out['off']['live_identity']
          and out['off']['passthrough_words'] == 64
          and out['off']['peak'] > 0
          and out['zero_depth']['staged_identity']
          and out['zero_depth']['live_identity']
          and out['zero_depth']['passthrough_words'] == 64
          and all(s['coeff_ok'] and s['resp_ok'] and s['depth_ok']
                  for s in out['sets'])
          and audio
          and all(abs(p['err_db']) <= p['bar'] for p in audio)
          and out['spi_err_delta'] == 0)
    out['verdict'] = 'AFB_DESIGN_OK' if ok else 'AFB_DESIGN_FAIL'
    print('')
    print(out['verdict'])
    if args.json:
        with open(args.json, 'w') as fh:
            json.dump(out, fh, indent=1)
        print('wrote %s' % args.json)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
