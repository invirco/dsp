#!/usr/bin/env python3
"""dsp4_capacity.py — what the IMAGE ON THE PART costs, per block.

WHY THIS EXISTS, AND WHY IT IS NOT sigprofile2.

The capacity record is taken with `sigprofile.sh` / `sigprofile2.sh` /
`fxcost.sh`, which build an INSTRUMENT: `DSP4_PROFILE_SIGNAL=1` (the input
kernels synthesise a square so the dynamics cannot be measured on their
cheap branch) and `DSP4_BLOCK_DECIMATE=32` (the graph runs on one block in
thirty-two, so a graph that does not fit still completes and can be read).
Those are the right choices for attributing cost to a CLASS. They are not
the shipping image, and the shipping image is what has to fit.

On 2026-09-09 the two instruments disagreed by 78,248 cycles/block — 23.9 %
of the budget — for the same nominal configuration (findings S10-6), which
is the same shape of error as S8-2: a number quoted for a build that is not
the one running. So the pair that ships gets read directly:

  * `_proc_cyc`      the LAST block pass
  * `_proc_cyc_max`  the WORST block pass seen since reset — the one the
                     budget actually has to cover; a margin quoted off
                     `_proc_cyc` is a margin against an average
  * `_proc_passes`   how many passes are in that max
  * `DIAG_BLK_OVERRUN` / `DIAG_FRAME_COUNT` — the arbiter. Cycles are an
                     argument; a block the main loop failed to keep up
                     with is the fact.
  * `CGU0_CTL` / `CGU0_DIV` — THE CLOCK THE IMAGE IS ACTUALLY RUNNING AT.
                     Every budget on this project was quoted at 983.04 MHz
                     for a fortnight while the part ran at 491.52 (S9-1),
                     so the budget is derived from what the CGU says, not
                     from what the build intended.
  * `DIAG_BUILD_CFG` — which build this is, in its own words.

  dsp4_capacity.py                    both chips, 30 s dwell
  dsp4_capacity.py --chip 2 --dwell 600
  dsp4_capacity.py --json cap.json
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, '/home/app/dspboot')

import dsp4_scope as S

CGU0_CTL = 0x3108D000
CGU0_DIV = 0x3108D00C

DIAG_FRAME_COUNT = 0xE004
DIAG_BLK_OVERRUN = 0xE00A
DIAG_BUILD_CFG = 0xE0EA
# The cost switches (S11-1). Read on every capacity row, because the first
# word cannot tell the shipping image from the fused/SIMD one and those two
# are 81,299 cycles/block apart on chip 2.
DIAG_BUILD_CFG2 = 0xE0EB

# CGU0_CTL MSEL -> CCLK in Hz. The rows are cgu_init.asm's own table; a
# value not in it is reported as the raw word rather than guessed at,
# because a guessed clock is exactly how the 491.52 MHz fortnight happened.
CTL_CCLK = {
    0x00002800: 491_520_000,     # the CGU RESET row
    0x00004000: 786_432_000,
    0x00005000: 983_040_000,
}


def moving(sc, reg, tries=16):
    """Read a register that is COUNTING.

    `Scope.rd` is a voted reader: it asks until one value has been seen
    twice. That is right for a settled register and impossible for a
    moving one — DIAG_FRAME_COUNT advances about eight counts between two
    asks at 3,000 blocks/s, so it never repeats and the voted reader
    reports a healthy part as an unsettled register. `Scope.wait()` makes
    the same exception for the scope's sample index and says why.

    So: single unvoted asks, and the sanity check is MONOTONICITY rather
    than repetition — three asks that increase, none of them zero (a
    dropped answer on this link always reads as zero).
    """
    last = None
    seen = []
    for _ in range(tries):
        v = sc._ask(reg)
        if not v:
            continue
        if last is not None and v < last:
            seen = []                    # went backwards: not a reading
        else:
            seen.append(v)
        last = v
        if len(seen) >= 3:
            return seen[-1]
    raise IOError('register 0x%04X never gave three increasing asks' % reg)


def peek(sc, addr):
    """ONE patient handshake. Not a retry ladder — that is the trap.

    `Scope.peek` writes DIAG_PEEK_ADDR and reads DIAG_PEEK_DATA, retrying
    the read on IOError, and it is correct. Two "improvements" were tried
    on 2026-09-09 and both returned a WELL-FORMED WRONG ANSWER:

      * reading the data half with the paced voted reader `rd()` — which
        fires up to twelve pipelined asks of its own — returned
        DIAG_FRAME_COUNT's value for `_proc_cyc`, increasing by eight per
        read;
      * wrapping the whole handshake in a 24-try agreement loop returned a
        value increasing by three per read, i.e. `_proc_passes`.

    The peek window is a TWO-TRANSACTION handshake and its second half can
    be answered from a different request under audio load. Every extra
    transaction is another chance for that. So: one handshake, patiently
    retried inside `Scope.peek`, and nothing layered on top.

    A dropped answer still reads as ZERO on this link, and that is not
    fixable from here — chip 2 at 93 % load returns 0 for all three cost
    words while every paced read of a NAMED register is correct. A zero is
    therefore reported as a zero and read as "unreadable under this load",
    not as "this chip costs nothing".
    """
    return sc.peek(addr, patience=40)


def read_chip(chip, dwell, symfile=None):
    # THE SYMBOL MAP MUST BE THE ONE THIS IMAGE WAS BUILT WITH. The map
    # moves on every build, so a stale chipN.sym.json points `_proc_cyc` at
    # whatever now lives at that address -- which answers, and looks like a
    # cycle count. Prefer the copy staged next to the .ldr that was booted
    # (the run directory), and fall back to ~/dspboot only if there is none.
    if symfile is None:
        local = './chip%d.sym.json' % chip
        symfile = local if os.path.exists(local) else \
            '/home/app/dspboot/chip%d.sym.json' % chip
    sc = S.Scope(chip, symfile)
    sc.check_chip()
    out = {'chip': chip}

    cfg = sc.rd(DIAG_BUILD_CFG)
    out['build_cfg'] = '0x%08X' % cfg
    out['block'] = cfg & 0xFF
    out['block_kernels'] = (cfg >> 8) & 1

    cfg2 = sc.rd(DIAG_BUILD_CFG2)
    out['build_cfg2'] = '0x%08X' % cfg2
    if (cfg2 & 0xFF000000) == 0xC2000000:
        out['decimate'] = (cfg2 >> 16) & 0xFF
        out['strip_fused'] = cfg2 & 1
        out['simd_dyn'] = (cfg2 >> 1) & 1
        # A PER-CHIP MASK in bits 9..8, not a flag: 1 = chip 1 IC TX,
        # 2 = chip 2 TX, 3 = both. Each chip costs a block of output latency.
        out['tx_early'] = (cfg2 >> 8) & 3
        out['gather_first'] = (cfg2 >> 6) & 1
    else:
        # Not an error: every image built before 2026-09-09 reads 0 here.
        # Recorded as unknown rather than as "all switches off", which is the
        # silence the word exists to end.
        out['decimate'] = None
        for k in ('strip_fused', 'simd_dyn', 'tx_early', 'gather_first'):
            out[k] = None

    ctl = peek(sc, CGU0_CTL)
    div = peek(sc, CGU0_DIV)
    out['cgu0_ctl'] = '0x%08X' % ctl
    out['cgu0_div'] = '0x%08X' % div
    cclk = CTL_CCLK.get(ctl)
    out['cclk_hz'] = cclk
    # The BUDGET is a fact about the clock and the block, and nothing else:
    # BLOCK samples at 48 kHz is BLOCK/48000 s of core time.
    out['budget'] = int(cclk * out['block'] / 48000) if cclk else None

    f0 = moving(sc, DIAG_FRAME_COUNT)
    o0 = sc.rd(DIAG_BLK_OVERRUN)
    t0 = time.time()
    time.sleep(dwell)
    f1 = moving(sc, DIAG_FRAME_COUNT)
    o1 = sc.rd(DIAG_BLK_OVERRUN)
    el = time.time() - t0

    out['frames'] = (f1 - f0) & 0xFFFFFFFF
    out['overruns'] = (o1 - o0) & 0xFFFFFFFF
    out['seconds'] = round(el, 1)
    out['block_rate'] = round(out['frames'] / el, 1) if el else None
    out['overrun_pct'] = (round(100.0 * out['overruns'] / out['frames'], 3)
                          if out['frames'] else None)

    sym = sc.sym
    for name in ('_proc_cyc', '_proc_cyc_max', '_proc_passes'):
        out[name.lstrip('_')] = peek(sc, sym[name]) if name in sym else None

    if out['budget']:
        for k in ('proc_cyc', 'proc_cyc_max'):
            v = out[k]
            out[k + '_pct'] = (round(100.0 * v / out['budget'], 2)
                               if v is not None else None)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chip', type=int, action='append')
    ap.add_argument('--dwell', type=float, default=30.0)
    ap.add_argument('--json')
    a = ap.parse_args()
    chips = a.chip or [1, 2]

    rows = []
    for c in chips:
        try:
            r = read_chip(c, a.dwell)
        except (IOError, SystemExit, KeyError) as exc:
            print('chip %d: UNREADABLE (%s)' % (c, exc))
            rows.append({'chip': c, 'error': str(exc)})
            continue
        rows.append(r)
        clk = ('%.2f MHz' % (r['cclk_hz'] / 1e6)) if r['cclk_hz'] else \
              'UNKNOWN (CGU0_CTL %s)' % r['cgu0_ctl']
        print('chip %d  build_cfg %s  block %d  kernels %d  CCLK %s'
              % (c, r['build_cfg'], r['block'], r['block_kernels'], clk))
        print('        cfg2 %s  decimate %s  fused %s  simd_dyn %s  '
              'tx_early %s  gather_first %s'
              % (r['build_cfg2'], r['decimate'], r['strip_fused'],
                 r['simd_dyn'], r['tx_early'], r['gather_first']))
        print('        CGU0_CTL %s  CGU0_DIV %s  budget %s cycles/block'
              % (r['cgu0_ctl'], r['cgu0_div'], r['budget']))
        print('        _proc_cyc     %8s  %s%%'
              % (r['proc_cyc'], r.get('proc_cyc_pct')))
        print('        _proc_cyc_max %8s  %s%%   <-- the block the budget has to cover'
              % (r['proc_cyc_max'], r.get('proc_cyc_max_pct')))
        print('        _proc_passes  %8s' % r['proc_passes'])
        print('        %d blocks in %.1f s (%.1f/s), OVERRUN %d (%s%%)'
              % (r['frames'], r['seconds'], r['block_rate'] or 0,
                 r['overruns'], r['overrun_pct']))
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump({'chips': rows}, fh, indent=1, sort_keys=True)
        print('wrote %s' % a.json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
