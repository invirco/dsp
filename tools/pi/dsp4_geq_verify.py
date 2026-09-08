#!/usr/bin/env python3
"""dsp4_geq_verify.py — the graphic EQ's band design, scored on the part.

Until 2026-09-08 every GEQ in the product passed its input through: the
28 landed band cells wrote raw dB floats into a fifth of the coefficient
array and nothing ever swapped them in. The design now runs ON THE DSP
(src/lib/geq_design_fx.asm), because 28 addresses cannot carry 140
coefficients plus a trigger. This scores it, three ways, and the three
fail differently on purpose:

  COEFFS    the 140 words the part designed into _geq_coeffs_next,
            against tools/dsp/geq_ref.kernel_set -- the model of the
            expression the kernel evaluates. NOT bit-exact and not
            claimed to be: the SHARC computes in 40-bit registers and
            stores float32, so the bar is a relative one (4 ulps),
            and the polynomial's own 2.1e-9 is inside it.

  RESPONSE  the magnitude response of what the part designed, at each
            band centre and an octave either side, against the model's.
            This is the bar that means something -- numeric-spec.md
            gives the biquad family +/-0.01 dB for f0 >= 50 Hz -- and it
            is computed from the coefficients READ BACK OFF THE PART, so
            it cannot pass on a set the part does not hold.

  AUDIO     an impulse response captured at the node's own buffer and
            transformed at three frequencies. Coefficients that are
            right in memory and never reach a sample is the exact defect
            this whole bar exists because of, so the audio is measured
            separately and is allowed a looser bar (the capture is Q4.28
            and the window is finite).

NEGATIVE CONTROLS, both of which have to fail if the tool is blind:
  * FLAT: every band at 0 dB must design the COMPILED identity word for
    word, and the node's output must equal its input in every captured
    sample. A verifier that cannot tell a designed flat GEQ from an
    inert one proves nothing about the boosted case.
  * WRONG-BAND: the +12 dB response is also scored at the centre of a
    DIFFERENT band, where it must be ~0 dB. A design that boosted every
    band equally would pass a single-point check at the right centre.

Run through geqverify.sh, which builds, stages, boots and configures.
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
import geq_ref as G
from dsp4_conform import Part, SPI_ERR_COUNT, f32

BUS_AMP = 0x08000000
CAPTURE_REST = 0.50
SETTLE_DESIGN = 0.60          # a crossfade is 576 samples; give it blocks
FS = 48000.0

# numeric-spec.md, biquad family
RESP_BAR_DB = 0.01            # f0 >= 50 Hz
RESP_BAR_DB_LF = 0.05         # including the 20 Hz extreme
COEFF_ULPS = 4
AUDIO_BAR_DB = 0.30           # a Q4.28 capture over a finite window


def to_f32(x):
    return struct.unpack('<f', struct.pack('<f', float(x)))[0]


def ulps(a, b):
    """Distance in float32 ulps between two doubles, via their f32 images."""
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
    """Magnitude of an offset-encoded cascade at f, in dB."""
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


def goertzel_db(samples, f, fs=FS):
    """|X(f)| of an impulse response, in dB relative to the flat case.

    A plain DFT bin at an arbitrary f, computed directly -- 3 frequencies
    over 1024 samples is 3072 multiply-adds and needs no numpy, which the
    bench does not have.
    """
    w = -2j * math.pi * f / fs
    acc = 0j
    for n, x in enumerate(samples):
        acc += x * cmath.exp(w * n)
    return acc


class Geq:
    """One GEQ node: its landed cells and the symbols behind them."""

    def __init__(self, part, L, node, cell_fmt, bands):
        self.part = part
        self.L = L
        self.node = node
        self.bands = bands
        self.cells = [cell_fmt % (b + 1) for b in range(bands)]
        self.sym_next = '_geq_coeffs_next_%s' % node
        self.sym_a = '_geq_coeffs_A_%s' % node
        self.sym_b = '_geq_coeffs_B_%s' % node
        self.sym_gains = '_geq_gains_%s' % node
        self.sym_dirty = '_geq_dirty_%s' % node
        self.sym_active = '_geq_active_%s' % node
        self.sym_pend = '_geq_swap_pending_%s' % node
        self.buf = '_buf_%s' % node

    def missing(self):
        out = [c for c in self.cells if not self.L.has(c)]
        out += [s for s in (self.sym_next, self.sym_a, self.sym_b,
                            self.sym_gains, self.sym_dirty)
                if s not in self.part.sc.sym]
        return out

    def write(self, gains):
        for cell, g in zip(self.cells, gains):
            self.part.write(self.L.addr(cell), f32(g), 0)
        time.sleep(SETTLE_DESIGN)

    def peekn(self, sym, n):
        base = self.part.sc.sym[sym]
        return [self.part.sc.peek(base + i) for i in range(n)]

    def designed(self):
        """The staged set, as floats."""
        return [from_f32w(w) for w in self.peekn(self.sym_next, 5 * self.bands)]

    def live(self):
        """The bank the cascade is READING, as floats. Which one that is
        moves with every swap, so it is read rather than assumed."""
        act = self.part.sc.peek(self.part.sc.sym[self.sym_active])
        sym = self.sym_b if act else self.sym_a
        # DSP4_BQ_GUARD puts a headroom header word in front of the bank.
        got = self.peekn(sym, 5 * self.bands + 1)
        hdr = got[0]
        body = got[1:] if _looks_like_header(hdr) else got[:-1]
        return sym, [from_f32w(w) for w in body]


def _looks_like_header(w):
    """The guard's header is a small integer shift count, not a float
    coefficient. b0 of any designed band is within a factor of four of
    1.0, so its exponent field is nowhere near zero."""
    return (w >> 23) & 0xFF < 0x60


def capture(part, inj, src, n, mode=1):
    time.sleep(CAPTURE_REST)
    part.sc.arm(part.sc.sym[src], inj, BUS_AMP, mode)
    part.sc.wait()
    out = []
    for i in range(n):
        part.sc.wr(S.SCOPE_RD, i)
        out.append(part.sc.rd(S.SCOPE_DATA))
    return out


def score_set(geq, gains, log=print):
    """COEFFS + RESPONSE for one gain vector."""
    want = G.kernel_set(gains)
    got = geq.designed()
    rec = {'gains': list(gains), 'words': len(want)}

    worst_u, worst_i = 0, -1
    for i, (a, b) in enumerate(zip(got, want)):
        u = ulps(a, b)
        if u > worst_u:
            worst_u, worst_i = u, i
    rec['worst_ulps'] = worst_u
    rec['worst_word'] = worst_i
    rec['coeff_ok'] = worst_u <= COEFF_ULPS

    # response, from what the PART holds
    worst_db, worst_f = 0.0, 0.0
    pts = []
    for i in range(geq.bands):
        f0 = G.centre(i)
        for f in (f0 / 2.0, f0, f0 * 2.0):
            if f >= FS / 2:
                continue
            d = resp_db(got, f) - resp_db(want, f)
            pts.append((f, d))
            if abs(d) > abs(worst_db):
                worst_db, worst_f = d, f
    rec['worst_resp_db'] = worst_db
    rec['worst_resp_f'] = worst_f
    bar = RESP_BAR_DB if worst_f >= 50.0 else RESP_BAR_DB_LF
    rec['resp_bar'] = bar
    rec['resp_ok'] = abs(worst_db) <= bar
    log('    coeffs worst %d ulp (word %d)  response worst %+.5f dB at '
        '%.1f Hz (bar %.3f)  -> %s'
        % (worst_u, worst_i, worst_db, worst_f, bar,
           'PASS' if rec['coeff_ok'] and rec['resp_ok'] else 'FAIL'))
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--landed', default='landed-d24.json')
    ap.add_argument('--node', default='C2_AUX_GEQ_01')
    ap.add_argument('--cell-fmt', default='Aux001Geq%03d')
    ap.add_argument('--bands', type=int, default=28)
    ap.add_argument('--band', type=int, default=17, help='band for the audio bar')
    ap.add_argument('--gain', type=float, default=12.0)
    ap.add_argument('--n', type=int, default=1024)
    ap.add_argument('--json', default='')
    args = ap.parse_args()

    sys.path.insert(0, '.')
    from dsp4_family_verify import Landed
    L = Landed(args.landed)

    part = Part(2)
    part.sc.check_chip()
    print('chip 2 ready; contract %s sha %s' % (L.pin, L.sha256[:12]))

    geq = Geq(part, L, args.node, args.cell_fmt, args.bands)
    miss = geq.missing()
    if miss:
        print('MISSING: %s' % ', '.join(miss[:6]))
        return 2

    out = {'node': args.node, 'bands': args.bands,
           'contract': {'pin': L.pin, 'sha256': L.sha256}, 'sets': [],
           'bar': {'coeff_ulps': COEFF_ULPS, 'resp_db': RESP_BAR_DB,
                   'resp_db_lf': RESP_BAR_DB_LF, 'audio_db': AUDIO_BAR_DB}}

    for cell, val in (('Aux001Level001', f32(1.0)), ('Aux001Mute001', 0)):
        if L.has(cell):
            part.write(L.addr(cell), val, 0)
    time.sleep(0.2)
    inj = part.sc.sym['_rx_ic_slot_C2_RECV_AUX_01']

    err0 = part.sc.rd(SPI_ERR_COUNT)

    # ---- NEGATIVE CONTROL 1: flat designs the compiled identity --------
    print('')
    print('flat (every band 0 dB) — must design the COMPILED identity')
    geq.write([0.0] * args.bands)
    flat = geq.designed()
    ident_ok = all(abs(v - G.IDENTITY[i % 5]) < 1e-12 for i, v in enumerate(flat))
    sym, livebank = geq.live()
    live_ok = all(abs(v - G.IDENTITY[i % 5]) < 1e-12
                  for i, v in enumerate(livebank))
    up = capture(part, inj, '_buf_C2_AUX_EQ_01', 64)
    here = capture(part, inj, geq.buf, 64)
    pass_ok = sum(1 for a, b in zip(up, here) if a == b)
    print('    staged identity %s;  live bank %s %s;  %d/64 samples equal '
          'to the input' % ('YES' if ident_ok else 'NO', sym,
                            'identity' if live_ok else 'NOT identity', pass_ok))
    out['flat'] = {'staged_identity': ident_ok, 'live_bank': sym,
                   'live_identity': live_ok, 'passthrough_words': pass_ok,
                   'peak': max((abs(q428(w)) for w in here), default=0.0)}

    # ---- the gain vectors ---------------------------------------------
    b = args.band
    vectors = [
        ('one band +%.0f dB (band %d, %.0f Hz)'
         % (args.gain, b, G.centre(b)),
         [args.gain if i == b else 0.0 for i in range(args.bands)]),
        ('one band -%.0f dB (band %d)' % (args.gain, b),
         [-args.gain if i == b else 0.0 for i in range(args.bands)]),
        ('alternating +/-%.0f dB' % args.gain,
         [args.gain * (-1) ** i for i in range(args.bands)]),
        ('every band +%.0f dB' % args.gain, [args.gain] * args.bands),
        ('ramp -12..+12 dB',
         [-12.0 + 24.0 * i / (args.bands - 1) for i in range(args.bands)]),
    ]
    print('')
    for name, gains in vectors:
        print('  %s' % name)
        geq.write(gains)
        rec = score_set(geq, gains)
        rec['name'] = name
        out['sets'].append(rec)

    # ---- AUDIO: the impulse response of one boosted band ---------------
    print('')
    gains = [args.gain if i == b else 0.0 for i in range(args.bands)]
    geq.write(gains)
    f0 = G.centre(b)
    ir_flat = None
    ir = capture(part, inj, geq.buf, args.n)
    geq.write([0.0] * args.bands)
    ir_flat = capture(part, inj, geq.buf, args.n)
    xs = [q428(w) for w in ir]
    xf = [q428(w) for w in ir_flat]
    probe = [(f0 / 4.0, 'quarter'), (f0, 'centre'), (f0 * 4.0, 'four x')]
    audio = []
    for f, tag in probe:
        if f >= FS / 2:
            continue
        a = goertzel_db(xs, f)
        c = goertzel_db(xf, f)
        got = 20 * math.log10(abs(a) / abs(c)) if abs(c) > 0 else float('nan')
        want = resp_db(G.kernel_set(gains), f)
        audio.append({'f': f, 'tag': tag, 'measured_db': got,
                      'model_db': want, 'err_db': got - want})
        print('    %-8s %8.1f Hz  measured %+7.3f dB   model %+7.3f dB   '
              'err %+.3f dB  -> %s'
              % (tag, f, got, want, got - want,
                 'PASS' if abs(got - want) <= AUDIO_BAR_DB else 'FAIL'))
    out['audio'] = {'band': b, 'centre': f0, 'gain': args.gain,
                    'n': args.n, 'points': audio,
                    'peak': max((abs(v) for v in xs), default=0.0)}

    out['spi_err_delta'] = (part.sc.rd(SPI_ERR_COUNT) - err0) & 0xFFFFFFFF

    ok = (out['flat']['staged_identity'] and out['flat']['live_identity']
          and out['flat']['passthrough_words'] == 64
          and out['flat']['peak'] > 0
          and all(s['coeff_ok'] and s['resp_ok'] for s in out['sets'])
          and audio
          and all(abs(p['err_db']) <= AUDIO_BAR_DB for p in audio)
          and out['spi_err_delta'] == 0)
    out['verdict'] = 'GEQ_DESIGN_OK' if ok else 'GEQ_DESIGN_FAIL'
    print('')
    print(out['verdict'])
    if args.json:
        with open(args.json, 'w') as fh:
            json.dump(out, fh, indent=1)
        print('wrote %s' % args.json)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
