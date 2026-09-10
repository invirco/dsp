#!/usr/bin/env python3
"""dsp4_dyn_lut_audio.py — does the table's gain reach the AUDIO, and how
far is it from the polynomial it replaced?

WHY THIS EXISTS AND WHY famverify CANNOT ANSWER IT.  famverify's audio arm
moves a cell and asks whether the samples moved.  For a DSP4_DYN_LUT node
that is exactly the wrong gesture: the cell it moves is the THRESHOLD, the
threshold is the curve, and a curve that has moved restarts the design step
-- so `_dlut_live` drops, the kernel takes the polynomial loop, and the
capture famverify takes is the polynomial's.  Measured on the part
2026-09-10: the LIMITER family's audio record is BIT-IDENTICAL on the
shipping arm and on the table arm, peak 0x00818682 both, and that identity
is the design working rather than the table being absent.

So this tool takes TWO captures around the design step instead of one:

    1. write the threshold, then capture IMMEDIATELY -- the cursor is
       short of DYN_LUT_N and the node is running the exact polynomial;
    2. wait for the cursor to reach DYN_LUT_N, then capture again -- the
       same node, the same parameters, the same envelope state, now on
       the table.

The difference between those two captures IS the table's error in the
audio, measured through the whole node rather than modelled.  The bar is
the table's own design bound (0.1 dB, PW 2026-09-09).

It can fail, which is the point:
  * the cursor never leaves DYN_LUT_N after the write -> the design step
    is not restarting, so the two captures are the same capture and the
    tool says so instead of printing a reassuring 0.000 dB;
  * the cursor never REACHES DYN_LUT_N -> no table verdict at all;
  * the captures are all zeros -> a dead node, and a dead node agrees
    with everything.

Usage (on the bench, beside a staged image):
  dsp4_dyn_lut_audio.py --chip 2 --node C2_AUX_LIM_01 \\
      --cell Aux001LimiterThr001 --value -20 --landed landed-d24.json
"""
import argparse
import json
import math
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

DYN_LUT_N = 337          # K = 4; the image's own cursor is what is compared


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def vpeek(sc, addr, tries=8):
    seen = {}
    for _ in range(tries):
        v = sc.peek(addr)
        seen[v] = seen.get(v, 0) + 1
        if seen[v] >= 2:
            return v
    raise IOError('0x%X never agreed with itself: %r' % (addr, seen))


def cpeek(sc, addr, tries=6):
    """The DESIGN CURSOR, read while it is allowed to be MOVING.

    Scope.rd and vpeek vote, and a counter the design step advances by
    DYN_LUT_CHUNK every block never returns the same word twice: the
    first run of this tool threw `0x9469C never agreed with itself:
    {28: 1, 40: 1, 52: 1, ...}` -- eight reads, each 12 higher than the
    last, which is the design step working. That is Part.frames()'s
    lesson (a moving value cannot be voted) applied to the one counter
    this tool exists to watch move.

    So: read twice. If the two agree, that is the answer and the cursor
    is settled. If the second is HIGHER, the cursor is advancing and the
    LATER value is the answer -- monotone by construction, because
    _dyn_lut_step only ever adds. Anything else is a link fault.
    """
    last = None
    for _ in range(tries):
        v = sc.peek(addr)
        if last is not None and last <= v:
            return v
        last = v
    raise IOError('0x%X is neither settled nor monotone: last %r'
                  % (addr, last))


def signed(v):
    return v - (1 << 32) if v & 0x80000000 else v


def capture(sc, src, inj, amp, n, offset, cur=None):
    """One armed step capture, read from OFFSET.

    Returns (samples, cursor_when_the_window_filled).

    THE CURSOR IS READ BETWEEN wait() AND THE READBACK, and that is the
    whole point of the split. The DSP fills _scope_buf at the audio rate
    -- 1,024 samples is 21 ms -- and then the host walks the window out
    over SPI two transactions per word, which is hundreds of
    milliseconds. A design-cursor read taken AFTER that walk says
    nothing about the samples: the first version of this tool read it
    there, saw 337, and refused a comparison whose samples were in fact
    entirely from the polynomial era. What decides the arithmetic in the
    window is where the cursor stood when the window FILLED, which is
    the instant wait() returns.

    The offset is famverify's, and it is not decoration: a step into a
    node with a time constant is silent for the first few hundred
    samples, and reading from sample 0 returns a window of zeros. The
    first run of this tool did exactly that and correctly refused to
    call it a verdict ("a dead node agrees with everything").
    """
    sc.arm(src, inj, amp, 2)             # mode 2 = step
    if not sc.wait():
        raise SystemExit('scope never disarmed — the sample loop is not '
                         'turning')
    at_fill = cpeek(sc, cur) if cur is not None else None
    out = []
    for i in range(offset, offset + n):
        sc.wr(S.SCOPE_RD, i)
        out.append(signed(sc.rd(S.SCOPE_DATA)))
    return out, at_fill


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chip', type=int, default=2)
    ap.add_argument('--sym')
    ap.add_argument('--node', default='C2_AUX_LIM_01')
    ap.add_argument('--class', dest='cls', choices=('comp', 'lim'))
    ap.add_argument('--cell', default='Aux001LimiterThr001',
                    help='the THRESHOLD cell — the write that restarts '
                         'the design step')
    ap.add_argument('--value', type=float, default=-20.0)
    ap.add_argument('--setup', default='',
                    help='cell=value pairs written first, comma separated')
    ap.add_argument('--inject', default='_rx_ic_slot_C2_RECV_AUX_01')
    ap.add_argument('--amp', default='0x08000000')
    ap.add_argument('--n', type=int, default=32)
    ap.add_argument('--offset', type=int, default=900,
                    help='famverify\'s window: a step is silent at the '
                         'start of a node with a time constant')
    ap.add_argument('--landed', default='landed-d24.json')
    ap.add_argument('--wait', type=float, default=1.0,
                    help='seconds to allow the design step to finish')
    ap.add_argument('--bar', type=float, default=0.1)
    a = ap.parse_args()

    cells = json.load(open(a.landed))['cells']

    sc = S.Scope(a.chip, a.sym) if a.sym else S.Scope(a.chip)
    sc.check_chip()

    cls = a.cls or ('lim' if '_LIM' in a.node.upper() else 'comp')
    cur = sc.sym.get('_%s_lutc_%s' % (cls, a.node))
    if cur is None:
        print('NO LUT SYMBOLS _%s_lutc_%s — this is not a DSP4_DYN_LUT '
              'image, or %s is not of class %s' % (cls, a.node, a.node, cls))
        return 2
    witness = sc.sym['_buf_%s' % a.node]
    inj = sc.sym[a.inject]

    def wcell(name, word):
        _chip, _page, addr = cells[name][0], cells[name][1], cells[name][2]
        sc.d.link.write(addr, word & 0xFFFFFFFF, 0)
        time.sleep(S.SETTLE)

    # THE DOT DECIDES THE TYPE, and it has to decide it explicitly.
    # `Aux001Level001=1.0` is a FLOAT cell and `Aux001Mute001=0` is a
    # boolean, and a rule of "small whole numbers are integers" writes
    # integer 1 into the level -- which the kernel reads as 1.4e-45 and
    # the whole chain goes silent. That is what the first two runs of
    # this tool captured as "all zeros".
    for item in filter(None, a.setup.split(',')):
        name, _, val = item.partition('=')
        wcell(name, f32(val) if '.' in val or 'e' in val.lower()
              else int(val, 0))
    time.sleep(0.3)

    n_all = cpeek(sc, cur)
    print('cursor before the write: %d' % n_all)

    # ---- 1. the write, then the polynomial capture ----------------------
    wcell(a.cell, f32(a.value))
    c_after = cpeek(sc, cur)
    poly, c_fill = capture(sc, witness, inj, int(a.amp, 16), a.n,
                           a.offset, cur)
    c_poly = cpeek(sc, cur)
    print('cursor: %d straight after the write, %d WHEN THE WINDOW FILLED, '
          '%d after the readback' % (c_after, c_fill, c_poly))
    if c_after >= DYN_LUT_N and c_poly >= DYN_LUT_N:
        print('THE DESIGN STEP DID NOT RESTART. Both captures below would '
              'be the same arithmetic, so this run has no verdict about '
              'the table: either %s is not the curve, or the key compare '
              'is not seeing the write. (Writing the value the node '
              'ALREADY has does this: the key matches and nothing '
              'restarts.)' % a.cell)
        return 4
    if c_fill >= DYN_LUT_N:
        # THE FIRST CAPTURE HAS TO BE THE POLYNOMIAL, and here it cannot
        # be shown to be. The design step restarted (c_after was short)
        # but finished BEFORE the capture was read back, so the samples
        # in the window may be from either side of the changeover and
        # nothing here can say which.
        #
        # It is an arithmetic race, not a flake: at DYN_LUT_CHUNK = 4 the
        # 337-point table fills in 85 blocks = 28 ms, against _scope_buf's
        # 1,024 samples = 21 ms. The two are close enough that the window
        # can straddle the changeover. Measured on the part 2026-09-10 at
        # CHUNK = 4: cursor 36 straight after the write, 337 by the time
        # the window had filled, and the two captures then BIT-IDENTICAL
        # -- which is what "both captures ran on the table" looks like,
        # and is indistinguishable here from "the two arms agree
        # exactly".
        #
        # THE FIX IS A WIDER WINDOW, not a longer sleep: rebuild the arm
        # with a smaller DYN_LUT_CHUNK (-DDYN_LUT_CHUNK=1 puts the design
        # at 337 blocks = 112 ms, five times the buffer) and re-run. A
        # comparison that cannot fail is not evidence, so this returns
        # no verdict rather than the 0.000 dB PASS it would otherwise
        # print.
        print('NO VERDICT: the design step had already finished when the '
              'first window filled (cursor %d after the write, %d at the '
              'fill), so that window is not known to be the '
              'polynomial\'s.' % (c_after, c_fill))
        print('  Rebuild with -DDYN_LUT_CHUNK=1 (337 blocks = 112 ms of '
              'polynomial, against _scope_buf\'s 1024 samples = 21 ms) '
              'and re-run.')
        return 6

    # ---- 2. wait for the table, then the table capture ------------------
    deadline = time.time() + a.wait
    while time.time() < deadline:
        if cpeek(sc, cur) >= DYN_LUT_N:
            break
        time.sleep(0.05)
    c_lut = vpeek(sc, cur)   # settled by now: voted
    print('cursor after waiting %.2f s: %d of %d' % (a.wait, c_lut,
                                                     DYN_LUT_N))
    if c_lut < DYN_LUT_N:
        print('THE TABLE IS STILL BEING DESIGNED — no verdict.')
        return 3
    lut, _ = capture(sc, witness, inj, int(a.amp, 16), a.n, a.offset)

    # ---- the comparison -------------------------------------------------
    if not any(poly) or not any(lut):
        print('A CAPTURE IS ALL ZEROS (poly %d non-zero, lut %d) — a dead '
              'node agrees with everything, so this is not a verdict.'
              % (sum(1 for v in poly if v), sum(1 for v in lut if v)))
        return 5

    diff = [(i, p, l) for i, (p, l) in enumerate(zip(poly, lut)) if p != l]
    worst, wi = 0.0, 0
    for i, p, l in diff:
        if p and l and (p > 0) == (l > 0):
            d = abs(20.0 * math.log10(abs(l) / abs(p)))
        else:
            d = float('inf')
        if d > worst:
            worst, wi = d, i
    print('captured %d samples of _buf_%s through %s'
          % (a.n, a.node, a.inject))
    print('  polynomial: peak %d   table: peak %d'
          % (max(abs(v) for v in poly), max(abs(v) for v in lut)))
    print('  %d of %d samples differ; worst %.5f dB at sample %d '
          '(poly %d, table %d)'
          % (len(diff), a.n, worst, wi, poly[wi] if diff else 0,
             lut[wi] if diff else 0))
    ok = worst <= a.bar
    print('THE TABLE\'S GAIN REACHES THE AUDIO, and it is %.5f dB from the '
          'polynomial it replaced — bar %.3f dB: %s'
          % (worst, a.bar, 'PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
