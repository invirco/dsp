#!/usr/bin/env python3
"""test_node_ref.py — the float32 reference for the S49 self-test nodes.

WHAT IT IS FOR. `dsp_codegen.py::gen_test_osc / gen_test_meas` emit SHARC
assembly for an oscillator and a measurement engine whose whole point is to
publish numbers nobody can check by eye. This is the arithmetic those two
kernels perform, written again in Python at the SAME precision (float32
throughout, via numpy's float32 or a struct round-trip when numpy is absent),
so the algorithm can be scored against closed-form answers BEFORE an image is
flashed -- the same discipline tools/dsp/fixed_ref.py serves the fixed arm.

It is a reference for the METHOD, not a bit-exact model of the instruction
stream: the SHARC multiplier rounds the same way IEEE single does, but the
order the assembler's registers force on a sum is not reproduced here. What
it proves is that the method -- magic-circle resonator, per-sample residual
against the previous window's least-squares fit, log2 by exponent split --
gives the answers it claims to, and what its floors are.

Run it: python3 tools/dsp/test_node_ref.py
"""
import math
import struct
import sys


def f32(x):
    """Round to IEEE single, the format both the kernel and this run in."""
    return struct.unpack('<f', struct.pack('<f', x))[0]


SAMPLE_RATE_HZ = 48000.0
BLOCK = 16
WIN_BLOCKS = 256
WIN = BLOCK * WIN_BLOCKS


class Osc:
    """The TEST_OSC kernel: x <- x + k*y ; y <- y - k*x, renormalised once
    per block on E = x^2 + y^2 - k*x*y."""

    def __init__(self, f_hz, level):
        self.set_freq(f_hz)
        self.level = f32(level)

    def set_freq(self, f_hz):
        f_hz = min(max(f_hz, 20.0), 20000.0)
        # the kernel's degree-13 Taylor for sin, in the same Horner form
        x = f32(f_hz * f32(math.pi / SAMPLE_RATE_HZ))
        z = f32(x * x)
        cs = (-1.0 / 39916800.0, 1.0 / 362880.0, -1.0 / 5040.0,
              1.0 / 120.0, -1.0 / 6.0, 1.0)
        p = f32(cs[0])
        for cc in cs[1:]:
            p = f32(f32(p * z) + f32(cc))
        self.k = f32(f32(x * p) * 2.0)
        # ...and for cos, the amplitude scale: the invariant is held at 1,
        # where the state reaches 1/cos(pi*f/fs).
        cc_ = (1.0 / 479001600.0, -1.0 / 3628800.0, 1.0 / 40320.0,
               -1.0 / 720.0, 1.0 / 24.0, -1.0 / 2.0, 1.0)
        p = f32(cc_[0])
        for c1 in cc_[1:]:
            p = f32(f32(p * z) + f32(c1))
        self.cos = p
        self.f = f_hz
        self.x, self.y = f32(0.0), f32(1.0)

    def block(self):
        """One block: (s[], c[], q[]) where q is the Q4.28 injected block."""
        s, c, q = [], [], []
        k, x, y = self.k, self.x, self.y
        amp = f32(f32(self.level * f32(float(1 << 28))) * self.cos)
        for _ in range(BLOCK):
            x = f32(x + f32(k * y))
            y = f32(y - f32(k * x))
            s.append(x)
            c.append(y)
            q.append(int(f32(x * amp)))
        # one Newton step on the invariant, twice
        e = f32(f32(f32(x * x) + f32(y * y)) + f32(f32(f32(x * y)) * k))
        g = f32(1.5 - f32(0.5 * e))
        g2 = f32(f32(0.5) * f32(f32(g * g) * e))
        g = f32(g * f32(1.5 - g2))
        self.x, self.y = f32(x * g), f32(y * g)
        return s, c, q


class Meas:
    """The TEST_MEAS kernel: per-sample correlation and residual, closed once
    per window."""

    def __init__(self):
        self.reset()
        self.a = f32(0.0)
        self.b = f32(0.0)
        self.seq = 0
        self.rms = self.thd = self.noise = float('nan')

    def reset(self):
        self.axx = self.axs = self.axc = self.aee = f32(0.0)
        self.ass = self.acc = self.asc = f32(0.0)
        self.blk = 0

    def tap(self, x, s, c):
        """One block of MeasChan, with the reference block it was given.
        Subtotals in registers, added to the window once -- exactly what the
        kernel does, and the reason it does it."""
        bxx = bxs = bxc = bee = f32(0.0)
        for i in range(BLOCK):
            xi, si, ci = f32(x[i]), f32(s[i]), f32(c[i])
            bxx = f32(bxx + f32(xi * xi))
            bxs = f32(bxs + f32(xi * si))
            bxc = f32(bxc + f32(xi * ci))
            e = f32(xi - f32(f32(self.a * si) + f32(self.b * ci)))
            bee = f32(bee + f32(e * e))
        self.axx = f32(self.axx + bxx)
        self.axs = f32(self.axs + bxs)
        self.axc = f32(self.axc + bxc)
        self.aee = f32(self.aee + bee)

    def step(self, s, c):
        """The node's own per-block work: reference self-sums, then the
        window test. Returns True on the block the window closes."""
        bss = bcc = bsc = f32(0.0)
        for i in range(BLOCK):
            si, ci = f32(s[i]), f32(c[i])
            bss = f32(bss + f32(si * si))
            bcc = f32(bcc + f32(ci * ci))
            bsc = f32(bsc + f32(si * ci))
        self.ass = f32(self.ass + bss)
        self.acc = f32(self.acc + bcc)
        self.asc = f32(self.asc + bsc)
        self.blk += 1
        if self.blk < WIN_BLOCKS:
            return False
        self.close()
        return True

    def close(self):
        FLOOR = f32(1e-30)
        sxx = max(self.axx, FLOOR)
        see = max(self.aee, FLOOR)
        k = f32(3.010299956639812)
        l2n = f32(math.log(WIN, 2.0))
        self.rms = f32(f32(f32(math.log(sxx, 2.0)) - l2n) * k)
        self.noise = f32(f32(f32(math.log(see, 2.0)) - l2n) * k)
        self.thd = f32(f32(f32(math.log(see, 2.0))
                           - f32(math.log(sxx, 2.0))) * k)
        det = f32(f32(self.ass * self.acc) - f32(self.asc * self.asc))
        if det <= FLOOR:
            self.a = self.b = f32(0.0)
        else:
            inv = f32(1.0 / det)
            self.a = f32(f32(f32(self.axs * self.acc)
                             - f32(self.axc * self.asc)) * inv)
            self.b = f32(f32(f32(self.axc * self.ass)
                             - f32(self.axs * self.asc)) * inv)
        self.seq += 1
        self.reset()


def run(f_hz, level, windows=4, path=None, meas_gain=1.0):
    """Drive the pair for `windows` windows. `path` is an optional function
    applied to each injected sample, standing in for whatever the strip does
    to it between the injection point and the tap."""
    osc = Osc(f_hz, level)
    meas = Meas()
    out = []
    # THE TRUTH, kept in float64 beside the float32 kernel: the mean square
    # of exactly the samples that were fed in. RmsResult is scored against
    # THIS and not against A^2/2, because the window holds a non-integer
    # number of cycles at a non-arbitrary phase and A^2/2 is therefore the
    # wrong answer by up to four tenths of a dB at 20 Hz -- a property of an
    # 85 ms window, not of the arithmetic, and one that would otherwise hide
    # inside the tolerance it forced.
    ref = 0.0
    # The chain's order: the strips are given the PREVIOUS block, the
    # measurement node runs, then the oscillator regenerates.
    s, c, q = osc.block()
    for _ in range(windows * WIN_BLOCKS):
        x = [(q[i] / float(1 << 28)) * meas_gain for i in range(BLOCK)]
        if path:
            x = [path(v) for v in x]
        ref += sum(v * v for v in x)
        meas.tap(x, s, c)
        if meas.step(s, c):
            out.append((meas.seq, meas.rms, meas.thd, meas.noise,
                        10.0 * math.log10(ref / WIN) if ref > 0
                        else float('-inf')))
            ref = 0.0
        s, c, q = osc.block()
    return out, osc


def main():
    ok = True

    def check(name, got, want, tol):
        nonlocal ok
        good = abs(got - want) <= tol
        ok = ok and good
        print('  %-44s got %10.4f  want %10.4f  %s'
              % (name, got, want, 'OK' if good else 'FAIL'))

    print('S49 self-test node reference — float32 throughout')
    print('  window %d samples (%d blocks x %d), fs %g Hz'
          % (WIN, WIN_BLOCKS, BLOCK, SAMPLE_RATE_HZ))
    print('')

    # ---- 1. the oscillator holds its amplitude and its frequency --------
    print('1. the oscillator')
    for f in (20.0, 100.0, 1000.0, 10000.0, 20000.0):
        osc = Osc(f, 1.0)
        pk = 0.0
        zc, prev = [], None
        for b in range(3000):            # 1 second
            _s, _c, q = osc.block()
            s = [v / float(1 << 28) for v in q]
            for i, v in enumerate(s):
                pk = max(pk, abs(v))
                if prev is not None and prev < 0 <= v:
                    zc.append(b * BLOCK + i)
                prev = v
        meas_f = (len(zc) - 1) * SAMPLE_RATE_HZ / (zc[-1] - zc[0]) \
            if len(zc) > 1 else 0.0
        err_hz = meas_f - f
        print('    %8.1f Hz: peak %.7f   measured %10.4f Hz  (%+.4f Hz, '
              '%+.1f ppm)' % (f, pk, meas_f, err_hz, 1e6 * err_hz / f))
        ok = ok and abs(pk - 1.0) < 2e-4
        ok = ok and abs(err_hz) < max(0.05, f * 5e-5)
    print('')

    # ---- 2. a clean digital loop: THD+N is the instrument's own floor ---
    print('2. unity digital path, level 0.5, 1 kHz')
    out, _ = run(1000.0, 0.5, windows=4)
    for seq, rms, thd, noise, ref in out:
        print('    window %d   RMS %8.3f dBFS (true %8.3f)   THD+N %8.2f dB'
              '   noise %8.2f dBFS' % (seq, rms, ref, thd, noise))
    check('RMS against the samples actually injected', out[-1][1],
          out[-1][4], 0.02)
    check('...and that is A^2/2 at 1 kHz', out[-1][4],
          20 * math.log10(0.5 / math.sqrt(2)), 0.02)
    check('first window reads THD+N 0 dB (no fit yet)', out[0][2], 0.0, 0.001)
    print('    THD+N floor of the method, settled: %.2f dB' % out[-1][2])
    ok = ok and out[-1][2] < -100.0
    print('')

    # ---- 3. a KNOWN distortion must come back at its own size -----------
    #
    # A SQUARER, y = x + d*x^2, is the cleanest closed-form distortion
    # available to a per-sample path function -- and it produces TWO
    # products, which is exactly why it is the right test. With x = A sin,
    #
    #   x^2 = A^2/2 - (A^2/2) cos 2wt
    #
    # so the path gains a second harmonic of amplitude d*A^2/2 AND a DC
    # offset of the same size. ThdResult is THD+N -- everything that is not
    # a sinusoid at f, and a DC offset is emphatically not one -- so the
    # expected answer is NOT the harmonic's own dBc. Against a fundamental
    # power of A^2/2 the residual is
    #
    #   (d A^2/2)^2 / 2   (the harmonic)  +  (d A^2/2)^2   (the offset)
    #
    # i.e. three halves of ... = 3x the harmonic's own power, 10*log10(3) =
    # 4.771 dB above it. Scoring against that rather than against the
    # harmonic alone is the difference between testing the measurement and
    # testing a guess about it.
    print('3. a known second harmonic, injected by squaring the path')
    print('   (a squarer also makes DC of the same size; THD+N counts it,')
    print('    so the expected reading is the harmonic + 10log10(3) dB)')
    OFF = 10.0 * math.log10(3.0)
    for target_db in (-40.0, -60.0, -80.0, -100.0):
        A = 0.5
        d = 2.0 * (10.0 ** (target_db / 20.0)) / A
        out, _ = run(1000.0, A, windows=3, path=lambda v, d=d: v + d * v * v)
        got = out[-1][2]
        print('    h2 at %6.1f dBc  ->  ThdResult %8.2f dB' % (target_db, got))
        check('  THD+N tracks h2+DC at %.0f dBc' % target_db, got,
              target_db + OFF, 0.1)
    print('')

    # ---- 3b. the level cell means the same thing at every frequency -----
    #
    # AND THE ONE PLACE THE WINDOW'S LENGTH SHOWS. RmsResult is the mean
    # square over DSP4_TEST_WIN_SAMPLES = 4096 samples, and the mean square
    # of a sine over a NON-INTEGER number of cycles is not A^2/2 -- it
    # depends on the phase the window opens at as well as on how many cycles
    # it holds. At 1 kHz the window holds 85 cycles and the term is
    # thousandths of a dB. At 20 Hz it holds 1.71 and the term runs to a few
    # tenths. That is a property of an 85 ms window and not an error in the
    # arithmetic, and 85 ms is the choice that gives the THD+N floor above:
    # a longer window costs float32 accumulator precision faster than it
    # buys cycles (512 blocks: -111 dB; 1024: -102 dB; measured here).
    #
    # So the check scores RmsResult against the float64 mean square of the
    # samples that were ACTUALLY injected, and prints the window term
    # beside it rather than hiding it in a tolerance.
    print('3b. OscLevel against frequency (tolerance = the window-fraction')
    print('    term, which is the only frequency dependence there is)')
    for f in (20.0, 200.0, 1000.0, 10000.0, 20000.0):
        m = f * WIN / SAMPLE_RATE_HZ
        # The exact mean square of the windowed sine, summed rather than
        # approximated, so the check scores the ARITHMETIC and the window
        # term is not an error budget anybody has to argue about. The
        # oscillator's first sample is n = 1 (x starts at zero and the
        # recurrence advances before the store), which matters at 20 Hz.
        for lvl_db in (0.0, -20.0, -60.0):
            lvl = 10.0 ** (lvl_db / 20.0)
            out, _ = run(f, lvl, windows=2)
            got, want = out[-1][1], out[-1][4]
            wdb = want - (lvl_db - 3.0103)
            check('  %6.0f Hz at %5.1f dBFS peak (%.2f cyc, window %+.3f dB)'
                  % (f, lvl_db, m, wdb), got, want, 0.05)
    print('')

    # ---- 4. with the oscillator silent, NoiseResult is the floor -------
    print('4. oscillator off: the degenerate branch')
    meas = Meas()
    import random
    random.seed(20260915)
    nf = 1e-4
    sil = [0.0] * BLOCK
    res = None
    for _ in range(2 * WIN_BLOCKS):
        x = [random.gauss(0.0, nf) for _ in range(BLOCK)]
        meas.tap(x, sil, sil)
        if meas.step(sil, sil):
            res = (meas.rms, meas.thd, meas.noise)
    print('    RMS %8.2f dBFS   THD+N %8.2f dB   noise %8.2f dBFS'
          % res)
    check('NoiseResult == RmsResult with no reference', res[2], res[0], 0.001)
    check('ThdResult reads 0 dB with no reference', res[1], 0.0, 0.001)
    check('the floor is the noise that was put in', res[0],
          20 * math.log10(nf), 0.2)
    print('')

    print('REFERENCE %s' % ('PASSED' if ok else 'FAILED'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
