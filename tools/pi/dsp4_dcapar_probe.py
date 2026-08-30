#!/usr/bin/env python3
"""dsp4_dcapar_probe — the two cell-semantics defects of 2026-08-30, measured.

Both were found on the part and both are fixed in the kernel; this is the
instrument that says so, and it is deliberately runnable against EITHER
image, because a fix with no before is an assertion.

    D57  RtgDca is a DCA ASSIGNMENT, not a gain. Writing the masters'
         documented "no DCA assigned" value of 0 used to set the strip's
         fader coefficient to zero and silence the channel with
         _fdr_level_ still reading 1.0.

    D59  CompPar's default left the compressor FULLY DRY. The blend is
         out = dry + par*(wet - dry), so at par = 0 a compressor that is
         ON and visibly reducing gain passes the input through untouched
         -- the threshold is not an audible control.

THE COMPRESSOR ROWS RUN FIRST, AND THAT ORDER IS THE MEASUREMENT. A
power-on default can only be read before anything writes the cell, and
the strip-driving helper this probe shares with conform.sh writes
CompPar = 100 % on purpose. Run the DCA rows first and the compressor
rows measure that write instead of the default -- which is exactly what
the first version of this probe did on 2026-08-30, and it reported a
threshold moving the bus on the PRE-fix image.

Rows, in the order they run:

    NULL     two captures with nothing written between them. The noise
             floor. Every verdict below is read against it and a run
             whose null interval moves words reports nothing.
    GR-A/B   _comp_gain_ captured on the DRIVEN graph at CompThr -20 dB
             and -55 dB, CompPar untouched. THE POSITIVE CONTROL for the
             two rows below: the compressor must be computing a
             different gain reduction at the two thresholds, or the bus
             rows below prove nothing. (_comp_gain_ has to be captured
             rather than peeked -- the scope only drives while it is
             armed, so between captures the envelope releases and a peek
             reads unity whatever the threshold is.)
    PAR-A/B  the BUS at those same two thresholds.  PASS = they DIFFER.
             Pre-fix they are identical to the word while GR-A/B move.
    DCA-0    RtgDca = 0, the documented "off".  PASS = the bus still
             carries the injected step.  On a pre-fix image the strip is
             SILENT here and the chain witness names _buf_C1_FDR_01.
    DCA-1    RtgDca = 1.0, the value the old kernel needed to stay
             audible.  Post-fix the two captures agree word for word:
             the cell reaches no audio at all, which is the fix.

Exit status is 0 whenever the measurement is VALID, whatever the verdict
-- a before run is supposed to fail, and re-booting five times over an
expected failure wastes the bench. Exit 2 means the run could not
measure (no capture, or a noise floor that no control can clear) and the
ladder should try again.

Run through dcapar.sh, which builds, stages and boots. On the bench:
    python3 dsp4_dcapar_probe.py [--strip 1] [--words 32]
"""
import argparse
import sys
import time

sys.path.insert(0, '/home/app/dspboot')

from dsp4_conform import (Part, drive_strip, bus_capture, bus_inject_addr,
                          chain_witness, f32,
                          BUS_AMP, BUS_SRC, STRIDE,
                          FDR_DCA, COMP_THR, COMP_PAR)

VERBOSE = True      # print what moves when a window will not settle
SETTLE = 1.0        # after a fader-affecting write: the GainFast ramp is
                    # ~85 ms at block rate and the link adds its own


def peak(words):
    if not words:
        return 0
    return max(abs(w - (1 << 32) if w & 0x80000000 else w) for w in words)


def differ(a, b):
    if a is None or b is None:
        return None
    return sum(1 for x, y in zip(a, b) if x != y)


def stable_capture(part, inj, n, src=None, tries=5, log=print):
    """Capture until two CONSECUTIVE captures agree word for word.

    "The graph is back at rest" is a PRECONDITION of every comparison
    here, and a fixed sleep only asserts it. Session 5 added a fixed rest
    interval and got a zero noise floor from a graph whose compressor was
    running WET; with CompPar at its default the same strip runs at full
    scale into the fader and the first capture after a parameter write
    does not repeat. Measured rather than assumed: capture until two in a
    row are identical, and report how many it took. A window that never
    settles is reported as unusable instead of being averaged over.
    """
    prev = bus_capture(part, inj, n, src)
    for k in range(2, tries + 1):
        cur = bus_capture(part, inj, n, src)
        if prev is not None and cur is not None and prev == cur:
            return cur, k
        if VERBOSE:
            log(f'    capture {k}: {differ(prev, cur)} of {n} words differ '
                f'from {k - 1}; peaks 0x{peak(prev):08X} 0x{peak(cur):08X}; '
                f'first words {[hex(w) for w in (cur or [])[:3]]}')
        prev = cur
    return None, tries


def carries(words):
    """SIGNAL, not "non-zero". A bus reading 0xFFFFFFF3 in every word --
    thirteen LSBs of constant residue -- passed a non-zero test on
    2026-08-30 while the fader's output was exactly zero."""
    return peak(words) >= (BUS_AMP >> 6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strip', type=int, default=1)
    ap.add_argument('--words', type=int, default=32)
    a = ap.parse_args()
    n, strip = a.words, a.strip
    b = (strip - 1) * STRIDE

    part = Part(1)
    inj = bus_inject_addr(part)
    gr_sym = '_comp_gain_C1_COMP_%02d' % strip
    ok = True

    def row(name, verdict, detail):
        print(f'  {name:<6} {verdict:<6} {detail}')

    print(f'=== driving strip {strip}, window {BUS_SRC}, '
          f'inject 0x{inj:X}, {n} words')

    # ---- D59: CompPar's POWER-ON DEFAULT --------------------------------
    # CompPar is never written, which is the whole point, so drive_strip's
    # own write of it is skipped. RtgDca is written 1.0 and skipped too:
    # on a PRE-fix image that is what keeps the strip audible, and on a
    # post-fix image it is an opaque selector nothing reads, so the same
    # script measures the compressor on both.
    part.write(b + FDR_DCA, f32(1.0), 0)
    drive_strip(part, strip, skip=(COMP_PAR, FDR_DCA))
    time.sleep(SETTLE)

    null_b, took = stable_capture(part, inj, n)
    row('NULL', 'PASS' if null_b is not None else 'FAIL',
        f'the driven bus repeats word for word after {took} captures'
        if null_b is not None else
        f'no two of {took} consecutive captures agree — the window never '
        f'comes to rest')
    if null_b is None or not carries(null_b):
        dead = chain_witness(part, inj, strip)
        print('  the window is not usable — no verdict is reported from '
              'this run' + (f'; the signal stops at {dead}' if dead else ''))
        return 2

    part.write(b + COMP_THR, f32(-20.0), 4)
    time.sleep(SETTLE)
    gr_a, _ = stable_capture(part, inj, n, gr_sym)
    par_a, _ = stable_capture(part, inj, n)

    part.write(b + COMP_THR, f32(-55.0), 4)
    time.sleep(SETTLE)
    gr_b, _ = stable_capture(part, inj, n, gr_sym)
    par_b, _ = stable_capture(part, inj, n)

    dgr = differ(gr_a, gr_b)
    row('GR-A', 'INFO', f'CompThr -20 dB: {gr_sym} peak 0x{peak(gr_a):08X}')
    row('GR-B', 'PASS' if dgr else 'FAIL',
        f'CompThr -55 dB: {gr_sym} peak 0x{peak(gr_b):08X} — {dgr} of {n} '
        f'words differ: the compressor {"IS" if dgr else "is NOT"} computing '
        f'a different gain reduction')
    if not dgr:
        print('  the positive control did not fire — nothing is claimed '
              'about the blend from this run')
        return 2

    dpar = differ(par_a, par_b)
    row('PAR-A', 'INFO',
        f'CompPar at its default, CompThr -20 dB: bus peak '
        f'0x{peak(par_a):08X}')
    row('PAR-B', 'PASS' if dpar else 'FAIL',
        f'CompThr -55 dB: bus peak 0x{peak(par_b):08X} — {dpar} of {n} bus '
        f'words differ from PAR-A')
    if not dpar:
        ok = False
        print('  the compressor reduces gain and the bus does not notice: '
              'at its default the blend is DRY (D59)')

    # ---- D57: RtgDca ASSIGNS, it does not scale --------------------------
    # drive_strip writes RtgDca = 0 (see its comment): the documented
    # "off", and the value that used to kill the strip.
    drive_strip(part, strip)
    time.sleep(SETTLE)
    dca0, _ = stable_capture(part, inj, n)
    if carries(dca0):
        row('DCA-0', 'PASS',
            f'RtgDca=0: bus peak 0x{peak(dca0):08X} against an injected '
            f'0x{BUS_AMP:08X} — the assignment does not scale')
    else:
        ok = False
        dead = chain_witness(part, inj, strip)
        row('DCA-0', 'FAIL',
            f'RtgDca=0: bus peak 0x{peak(dca0):08X} — SILENT'
            + (f', the signal stops at {dead}' if dead else ''))

    part.write(b + FDR_DCA, f32(1.0), 0)
    time.sleep(SETTLE)
    dca1, _ = stable_capture(part, inj, n)
    d = differ(dca0, dca1)
    row('DCA-1', 'PASS' if (d == 0 and carries(dca1)) else 'FAIL',
        f'RtgDca=1.0: bus peak 0x{peak(dca1):08X}, {d} of {n} words differ '
        f'from RtgDca=0 — the cell reaches no audio either way')
    if d != 0 or not carries(dca1):
        ok = False

    print(f'VERDICT: {"PASS" if ok else "FAIL"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
