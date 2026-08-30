#!/usr/bin/env python3
"""dsp4_dcapar_probe — the two cell-semantics defects of 2026-08-30, measured.

Both were found on the part and both are fixed in the kernel; this is the
instrument that says so, and it is deliberately runnable against EITHER
image, because a fix with no before is an assertion.

    D57  `RtgDca` is a DCA ASSIGNMENT, not a gain. Writing the masters'
         documented "no DCA assigned" value of 0 used to set the strip's
         fader coefficient to zero and silence the channel with
         _fdr_level_ still reading 1.0. SUPERSEDED 2026-08-30 by PW's Q2
         ruling: `Dca` and `DcaOn` are HOST-MANAGED, the CM4 control
         daemon folds DCA into the fader target it already sends, and
         the address is RESERVED. What is measured now is that the cell
         LEFT the writable surface -- which subsumes D57, because an
         address the handler rejects cannot scale anything.

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
    DCA-U    a write to 0x0053 against the part's own SPI_ERR_COUNT.
             PASS = the counter MOVES: the address is unmapped, which is
             what "left the DSP-writable surface" means on the part
             rather than in a document. Its NEGATIVE CONTROL is the
             mapped neighbour 0x0052 (FDR_MUTE) written the same way in
             the same batch -- the counter must not move for that one,
             or the probe is reading an error the link caused.
    DCA-A    the bus either side of that rejected write. PASS = 0 of n
             words differ: the cell reaches no audio at all. On a
             pre-2026-08-30 image the same write LANDS, and before D57
             it silenced the strip outright.

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
                          BUS_AMP, BUS_SRC, STRIDE, SPI_ERR_COUNT,
                          FDR_MUTE, FDR_RESERVED, COMP_THR, COMP_PAR)

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
    # own write of it is skipped. The DCA word is written 1.0 first and
    # NOT skipped-because-it-matters: on a pre-2026-08-30 image that is
    # what keeps the strip audible, and on this one the handler rejects
    # the write, so the same script measures the compressor on both.
    part.write(b + FDR_RESERVED, f32(1.0), 0)
    drive_strip(part, strip, skip=(COMP_PAR,))
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

    # ---- Q2: the DCA cell is HOST-MANAGED, and off the wire ------------
    # Two questions, and the second is worthless without the first: is
    # 0x0053 rejected by the SPI handler, and does the graph notice a
    # write to it. The error counter answers the first; the bus answers
    # the second; and the mapped neighbour written in the same batch is
    # what separates "this address is unmapped" from "the link dropped a
    # write", which look identical from one counter reading.
    drive_strip(part, strip)
    time.sleep(SETTLE)
    dca_before, _ = stable_capture(part, inj, n)

    e0 = part.read(SPI_ERR_COUNT)
    part.write(b + FDR_MUTE, 0, 0)                   # mapped: must NOT error
    e1 = part.read(SPI_ERR_COUNT)
    part.write(b + FDR_RESERVED, f32(1.0), 0)        # reserved: must error
    e2 = part.read(SPI_ERR_COUNT)
    ctl_quiet = (e1 == e0)
    rejected = (e2 > e1)
    row('DCA-U', 'PASS' if (rejected and ctl_quiet) else 'FAIL',
        f'SPI_ERR_COUNT {e0} -> {e1} across the MAPPED 0x{b + FDR_MUTE:04X} '
        f'-> {e2} across 0x{b + FDR_RESERVED:04X}: the reserved address '
        f'{"IS" if rejected else "is NOT"} rejected'
        + ('' if ctl_quiet else
           ' — AND THE CONTROL FIRED TOO, so this counter is not measuring '
           'the address'))
    if not (rejected and ctl_quiet):
        ok = False

    time.sleep(SETTLE)
    dca_after, _ = stable_capture(part, inj, n)
    d = differ(dca_before, dca_after)
    row('DCA-A', 'PASS' if (d == 0 and carries(dca_after)) else 'FAIL',
        f'bus peak 0x{peak(dca_after):08X}, {d} of {n} words differ across '
        f'the rejected write — the cell reaches no audio')
    if d != 0 or not carries(dca_after):
        ok = False
        dead = chain_witness(part, inj, strip)
        if dead:
            print(f'  the signal stops at {dead}')

    print(f'VERDICT: {"PASS" if ok else "FAIL"}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
