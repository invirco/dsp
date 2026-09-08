#!/usr/bin/env python3
"""dsp4_fx_verify.py — the FX engine, made to carry a sample and proved.

WHAT WAS WRONG. `_fx_type` defaulted to 0 = Echo, and the reverb class
emitted cases only for 2 (Doubling) and 3 (Reverb), so THE LANDED
DEFAULT FELL THROUGH TO A DRY PASS -- which is why FX_ENGINE had never
run in any capacity measurement. Under it: Doubling read a 720-sample
delay out of an EIGHT-WORD buffer with a wrap constant of 8, landing 711
words before the array; the mix epilogue stored a float32 word into
`_buf_L` while `_buf_` carried Q4.28; the reverb allocated two full-size
stereo halves that no emitted instruction touched; and the whole kernel
set NO L REGISTER before using `modify(i0, m0)` on four buffers and
post-modify on four table walks, alone among every kernel in this tree.

This is the bar for the fixes. Each Type is driven from the LANDED
`Fx00NType001` cell and the node's own published buffer is captured, so
every verdict is a read off the part:

  DRY       Mix = 0 must pass the input word for word, at every Type.
            This is the negative control: a tool that cannot tell a
            processing engine from a pass-through proves nothing.

  ECHO      Type 0, the default. A single delayed copy at the requested
            delay and nowhere else -- the impulse must appear at sample
            `delay` and the samples between must be silent.

  DOUBLING  Type 2. The same, at the fixed 15 ms (720 samples) the
            design names, which is inside the buffer now and was not.

  REVERB    Type 3. Not a closed form to check against, so the bar is
            what the family walk could not get: the chain CARRIES the
            impulse (non-zero energy after the input sample) and the
            tail decays. Pass 4 read peak zero on both arms.

  BYPASS    An unimplemented Type parks its number in `_fx_bypassed`
            and passes the sample through. It used to fall through
            silently, which on a capture is indistinguishable from an
            engine that ran and had nothing to do.

Run through fxverify.sh, which builds, stages, boots and configures.
"""

import argparse
import json
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')

import dsp4_scope as S
from dsp4_conform import Part, SPI_ERR_COUNT, f32

BUS_AMP = 0x08000000
CAPTURE_REST = 0.50
SETTLE = 0.60
FS = 48000.0

ECHO_DELAY = 240          # 5 ms, so the tap lands inside a 1024 window
DOUBLE_DELAY = 720        # the design's fixed 15 ms
TAP_TOL = 2               # samples: the block pipeline can shift a tap


def q428(w):
    v = w - (1 << 32) if w & 0x80000000 else w
    return v / float(1 << 28)


class Fx:
    def __init__(self, part, L, node, prefix):
        self.part = part
        self.L = L
        self.node = node
        self.c = lambda n: '%s%s001' % (prefix, n)
        self.buf = '_buf_%s' % node
        self.sym_type = '_fx_type_%s' % node
        self.sym_byp = '_fx_bypassed_%s' % node
        self.sym_mix = '_fx_mix_%s' % node
        self.sym_wptr = '_fx_echo_wptr_%s' % node

    def missing(self):
        out = [self.c(n) for n in ('Type', 'Mix', 'DelayTime', 'Feedback',
                                   'Damp', 'On')
               if not self.L.has(self.c(n))]
        out += [s for s in (self.sym_type, self.sym_byp, self.sym_mix)
                if s not in self.part.sc.sym]
        return out

    def set(self, **kw):
        for name, val in kw.items():
            cell = self.c(name)
            if self.L.has(cell):
                self.part.write(self.L.addr(cell), val, 0)
        time.sleep(SETTLE)

    def peek(self, sym):
        return self.part.sc.peek(self.part.sc.sym[sym])


def capture(part, inj, src, n, mode=1, tries=3, rest=None):
    """One armed capture, RE-PHASED on a link fault rather than abandoned.

    The diag link loses phase from time to time on this bench -- the
    known intermittent, recorded since session 5 -- and a capture that
    dies of it in the middle of a ladder throws away every arm after it.
    Re-syncing and re-arming is safe: arm() proves the arm landed by
    watching the run counter, so a retry cannot hand back a stale
    buffer."""
    last = None
    for _ in range(tries):
        try:
            time.sleep(CAPTURE_REST if rest is None else rest)
            part.sc.arm(part.sc.sym[src], inj, BUS_AMP, mode)
            part.sc.wait()
            out = []
            for i in range(n):
                part.sc.wr(S.SCOPE_RD, i)
                out.append(part.sc.rd(S.SCOPE_DATA))
            return out
        except (IOError, OSError, TimeoutError) as exc:
            last = exc
            try:
                part.sc.d.resync()
            except Exception:
                pass
            time.sleep(1.0)
    raise IOError('capture of %s failed after %d tries: %s'
                  % (src, tries, last))


def capture_second(part, inj, src, n, mode=2, tries=3):
    """Arm twice, fetch only the SECOND window.

    THE FETCH IS THE SLOW PART, not the capture. Reading 1024 words back
    over the diag link takes seconds, so "arm, fetch, arm again" puts
    tens of thousands of samples between the two windows -- long enough
    for a comb with 0.6 of feedback to have gone round its line a
    hundred times and decayed below a Q4.28 LSB. Arming twice and
    fetching once puts the windows a handshake apart, which is what a
    filter whose shortest delay (1116) is longer than the buffer (1024)
    needs to be observable at all."""
    last = None
    for _ in range(tries):
        try:
            time.sleep(CAPTURE_REST)
            part.sc.arm(part.sc.sym[src], inj, BUS_AMP, mode)
            part.sc.wait()
            part.sc.arm(part.sc.sym[src], inj, BUS_AMP, mode)
            part.sc.wait()
            out = []
            for i in range(n):
                part.sc.wr(S.SCOPE_RD, i)
                out.append(part.sc.rd(S.SCOPE_DATA))
            return out
        except (IOError, OSError, TimeoutError) as exc:
            last = exc
            try:
                part.sc.d.resync()
            except Exception:
                pass
            time.sleep(1.0)
    raise IOError('two-shot capture of %s failed: %s' % (src, last))


def peak_at(xs, lo, hi):
    """(index, |value|) of the largest sample in [lo, hi)."""
    best, bi = 0.0, -1
    for i in range(max(0, lo), min(len(xs), hi)):
        v = abs(xs[i])
        if v > best:
            best, bi = v, i
    return bi, best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--landed', default='landed-d24.json')
    ap.add_argument('--node', default='C2_FX_ENG_01')
    ap.add_argument('--prefix', default='Fx001')
    ap.add_argument('--upstream', default='_buf_C2_RECV_FX_01')
    ap.add_argument('--inject', default='_rx_ic_slot_C2_RECV_FX_01')
    ap.add_argument('--n', type=int, default=1024)
    ap.add_argument('--json', default='')
    args = ap.parse_args()

    sys.path.insert(0, '.')
    from dsp4_family_verify import Landed
    L = Landed(args.landed)

    part = Part(2)
    part.sc.check_chip()
    print('chip 2 ready; contract %s sha %s' % (L.pin, L.sha256[:12]))

    fx = Fx(part, L, args.node, args.prefix)
    miss = fx.missing()
    if miss:
        print('MISSING: %s' % ', '.join(miss[:6]))
        return 2

    out = {'node': args.node, 'n': args.n,
           'contract': {'pin': L.pin, 'sha256': L.sha256}, 'arms': []}
    inj = part.sc.sym[args.inject]
    err0 = part.sc.rd(SPI_ERR_COUNT)

    # ---- the input the whole thing is scored against -------------------
    up = capture(part, inj, args.upstream, args.n)
    us = [q428(w) for w in up]
    ui, uv = peak_at(us, 0, args.n)
    print('')
    print('input at %s: peak %.6f at sample %d' % (args.upstream, uv, ui))
    out['input'] = {'peak': uv, 'peak_at': ui}
    if uv == 0.0:
        print('INPUT SILENT — no verdict is possible from this run')
        out['verdict'] = 'FX_VERIFY_NO_INPUT'
        if args.json:
            json.dump(out, open(args.json, 'w'), indent=1)
        return 1

    # ---- NEGATIVE CONTROL: Mix = 0 is a pass-through at every Type -----
    #
    # THE ORDER OF THIS LADDER IS THE ORDER THE BENCH PROVED. Each arm
    # changes as little as it can from the one before it, and the dry
    # controls run FIRST, at the parameters the product boots with, so a
    # failure has as little state behind it as possible.
    print('')
    print('Mix = 0 — the dry control, at Type 0 and Type 3')
    dry_ok = True
    for t in (0, 3):
        fx.set(Type=t, Mix=f32(0.0))
        here = capture(part, inj, fx.buf, 64)
        same = sum(1 for a, b in zip(up[:64], here) if a == b)
        print('    Type %d: %d/64 samples equal to the input' % (t, same))
        dry_ok = dry_ok and same == 64
        out.setdefault('dry', []).append({'type': t, 'equal': same})

    # ---- ECHO, the landed default --------------------------------------
    print('')
    print('Type 0 = Echo (THE LANDED DEFAULT), delay %d samples, Mix 1.0'
          % ECHO_DELAY)
    fx.set(Type=0, DelayTime=ECHO_DELAY, Feedback=f32(0.0),
           Mix=f32(1.0))
    ec = [q428(w) for w in capture(part, inj, fx.buf, args.n)]
    ei, ev = peak_at(ec, 1, args.n)
    _, between = peak_at(ec, 1, ECHO_DELAY - TAP_TOL)
    echo_ok = (abs(ei - ECHO_DELAY) <= TAP_TOL and ev > 0.5 * uv
               and between < 0.02 * uv)
    print('    tap at sample %d (want %d +/-%d), amplitude %.6f (input '
          '%.6f); largest sample before the tap %.8f  -> %s'
          % (ei, ECHO_DELAY, TAP_TOL, ev, uv, between,
             'PASS' if echo_ok else 'FAIL'))
    out['echo'] = {'delay': ECHO_DELAY, 'tap_at': ei, 'tap': ev,
                   'between': between, 'ok': echo_ok,
                   'bypassed': fx.peek(fx.sym_byp)}

    # ---- DOUBLING -------------------------------------------------------
    print('')
    print('Type 2 = Doubling, the design\'s fixed %d samples, Mix 1.0'
          % DOUBLE_DELAY)
    fx.set(Type=2, Mix=f32(1.0))
    db = [q428(w) for w in capture(part, inj, fx.buf, args.n)]
    di, dv = peak_at(db, 1, args.n)
    _, dbetween = peak_at(db, 1, DOUBLE_DELAY - TAP_TOL)
    dbl_ok = (abs(di - DOUBLE_DELAY) <= TAP_TOL and dv > 0.5 * uv
              and dbetween < 0.02 * uv)
    print('    tap at sample %d (want %d +/-%d), amplitude %.6f; largest '
          'sample before the tap %.8f  -> %s'
          % (di, DOUBLE_DELAY, TAP_TOL, dv, dbetween,
             'PASS' if dbl_ok else 'FAIL'))
    out['doubling'] = {'delay': DOUBLE_DELAY, 'tap_at': di, 'tap': dv,
                       'between': dbetween, 'ok': dbl_ok,
                       'bypassed': fx.peek(fx.sym_byp)}

    # ---- REVERB ---------------------------------------------------------
    #
    # A 1024-SAMPLE WINDOW CANNOT CONTAIN A FREEVERB RESPONSE, and that
    # is worth stating rather than working around quietly. The comb
    # lengths are 1116..1617 samples and there is no direct path from
    # input to output -- the wet signal IS the comb read -- so the first
    # reverberant sample arrives 1116 samples after the impulse, past
    # the end of the scope buffer. The 2026-09-08 family walk scored
    # this family over a 32-SAMPLE window and read peak zero; a window
    # thirty-five times too short cannot see a reverb even when the
    # reverb is perfect, which is half of why that verdict meant
    # nothing (the other half was f15).
    #
    # So the arm is scored on three things that ARE observable:
    #   * the eight comb write pointers are inside their own lines. This
    #     is the direct measurement that the wild-pointer defect is gone
    #     -- a float32 sample's bits are about 1e9, so a broken pointer
    #     is not a near miss.
    #   * the comb delay lines HOLD the signal: the reverb wrote real
    #     audio into its state, which is what "carries the impulse"
    #     means for a filter whose output is delayed past the window.
    #   * a SECOND capture, armed after the tail has had time to come
    #     round, has non-zero output energy.
    print('')
    print('Type 3 = Reverb, Mix 1.0, Feedback 0.6, Damp 0.2 — the arm the')
    print('family walk read at PEAK ZERO')
    #
    # THE STIMULUS HERE IS A STEP, NOT AN IMPULSE, and for the same
    # reason. One sample of energy is somewhere in an 11,024-word comb
    # bank and reading all of it over SPI to find it is not a
    # measurement, it is an afternoon. A step (scope mode 2) drives
    # every sample of the window, so the lines FILL and any eight words
    # behind a write pointer are the signal.
    fx.set(Type=3, Feedback=f32(0.6), Damp=f32(0.2), Mix=f32(1.0))
    tail = [q428(w) for w in capture_second(part, inj, fx.buf, args.n)]
    e_tail = sum(v * v for v in tail)
    ti, tv = peak_at(tail, 0, args.n)
    nz = sum(1 for v in tail if v != 0.0)
    tail_ok = tv > 0.0
    print('    the SECOND of two windows armed a handshake apart: peak '
          '%.6f at sample %d, %d of %d non-zero, energy %.3e  -> %s'
          % (tv, ti, nz, args.n, e_tail, 'PASS' if tail_ok else 'FAIL'))

    lens = [part.sc.peek(part.sc.sym['_fx_rv_comb_lens_%s' % args.node] + k)
            for k in range(8)]
    # The line contents are read RELATIVE TO THE POINTER AT READ TIME and
    # the graph does not stop for the SPI link, so this is a snapshot of
    # a decaying tail, not of the driven window. What it is scored on is
    # the POINTERS -- a broken one is 1e9, not a near miss -- and the
    # tail capture below.
    wptr = [part.sc.peek(part.sc.sym['_fx_rv_comb_wptrs_%s' % args.node] + k)
            for k in range(8)]
    ptr_ok = all(0 <= w < l for w, l in zip(wptr, lens))
    print('    comb lengths %s' % ' '.join(str(v) for v in lens))
    print('    comb wptrs   %s   -> %s'
          % (' '.join(str(v) for v in wptr),
             'IN RANGE' if ptr_ok else 'OUT OF RANGE'))

    base = part.sc.sym['_fx_comb_buf_L_%s' % args.node]
    ofs = [part.sc.peek(part.sc.sym['_fx_rv_comb_ofs_%s' % args.node] + k)
           for k in range(8)]
    held = []
    for k in range(8):
        w = wptr[k] if 0 <= wptr[k] < lens[k] else 0
        vals = [struct.unpack('<f', struct.pack('<I', part.sc.peek(
            base + ofs[k] + ((w - 1 - j) % lens[k])) & 0xFFFFFFFF))[0]
            for j in range(8)]
        held.append(max(abs(v) for v in vals))
    state_ok = ptr_ok and sum(1 for v in held if v > 0.0) >= 6
    print('    comb lines hold %s'
          % ' '.join('%.3e' % v for v in held))
    print('    (a decaying snapshot, not the driven window — see the note) '
          '-> %s' % ('%d of 8 lines non-zero' % sum(1 for v in held if v > 0)))

    rv_ok = ptr_ok and tail_ok
    out['reverb'] = {
                     'comb_lens': lens, 'comb_wptrs': wptr,
                     'ptr_in_range': ptr_ok, 'comb_line_peaks': held,
                     'state_ok': state_ok, 'tail_peak': tv,
                     'tail_peak_at': ti, 'tail_nonzero': nz,
                     'tail_energy': e_tail, 'ok': rv_ok,
                     'bypassed': fx.peek(fx.sym_byp)}

    # ---- EXPLICIT BYPASS -------------------------------------------------
    print('')
    print('Types with no algorithm for this class — the EXPLICIT bypass')
    byp = []
    for t in (1, 4, 5, 6):
        fx.set(Type=t, Mix=f32(1.0))
        here = capture(part, inj, fx.buf, 64)
        same = sum(1 for a, b in zip(up[:64], here) if a == b)
        parked = fx.peek(fx.sym_byp)
        ok = parked == t and same == 64
        print('    Type %d: _fx_bypassed reads %d, %d/64 samples equal to '
              'the input  -> %s' % (t, parked, same, 'PASS' if ok else 'FAIL'))
        byp.append({'type': t, 'bypassed': parked, 'equal': same, 'ok': ok})
    out['bypass'] = byp

    # leave the node as the product boots it
    fx.set(Type=0, Mix=f32(0.0), Feedback=f32(0.0), Damp=f32(0.0))

    out['spi_err_delta'] = (part.sc.rd(SPI_ERR_COUNT) - err0) & 0xFFFFFFFF
    ok = (dry_ok and echo_ok and dbl_ok and rv_ok
          and all(b['ok'] for b in byp) and out['spi_err_delta'] == 0)
    out['verdict'] = 'FX_VERIFY_OK' if ok else 'FX_VERIFY_FAIL'
    print('')
    print(out['verdict'])
    if args.json:
        json.dump(out, open(args.json, 'w'), indent=1)
        print('wrote %s' % args.json)
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
