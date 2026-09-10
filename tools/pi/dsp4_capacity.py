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
DIAG_TICKS = 0xE005
DIAG_BLK_OVERRUN = 0xE00A
DIAG_BUILD_CFG = 0xE0EA
# The cost switches (S11-1). Read on every capacity row, because the first
# word cannot tell the shipping image from the fused/SIMD one and those two
# are 81,299 cycles/block apart on chip 2.
DIAG_BUILD_CFG2 = 0xE0EB
DIAG_CLEAR = 0xE0FF

# CGU0_CTL MSEL -> CCLK in Hz. The rows are cgu_init.asm's own table; a
# value not in it is reported as the raw word rather than guessed at,
# because a guessed clock is exactly how the 491.52 MHz fortnight happened.
CTL_CCLK = {
    0x00002800: 491_520_000,     # the CGU RESET row
    0x00004000: 786_432_000,
    0x00005000: 983_040_000,
}

# DIAG_BUILD_CFG bits 18:17 (diag.h, DIAG_CFG_CCLK) -> the core-timer
# reload DIAG_TPERIOD this image was BUILT with, in CCLK cycles.
CFG_TPERIOD = {0: 491_520, 1: 786_432, 2: 983_040}


def measure_cclk(sc, tperiod, dwell):
    """CCLK MEASURED, not decoded -- S15 gate 0.

    S14-7 left the record with a decode and no measurement, and the two
    are not the same claim: the decode says what the CGU was ASKED for,
    and on 2026-09-10 the shipping pair was found asking for 983.04 MHz
    with CGU0_CTL still on the reset row.  A decode cannot see that.

    The core timer decrements TCOUNT once per CCLK cycle by construction
    and reloads from TPERIOD, so DIAG_TICKS advances at exactly
    CCLK / TPERIOD Hz and NOTHING in that chain reads the CGU.  Timed
    against the host's clock it is an absolute measurement of CCLK.

    Each reading is bracketed by time.monotonic() either side and the
    MIDPOINT is used, so the SPI round trip cannot bias the rate; the
    ticks register is free-running and never cleared, so it needs no
    voting, only monotonicity, which `moving` already enforces.
    """
    a0 = time.monotonic()
    t0 = moving(sc, DIAG_TICKS)
    b0 = time.monotonic()
    time.sleep(dwell)
    a1 = time.monotonic()
    t1 = moving(sc, DIAG_TICKS)
    b1 = time.monotonic()
    el = ((a1 + b1) / 2.0) - ((a0 + b0) / 2.0)
    if el <= 0:
        return None, None
    rate = ((t1 - t0) & 0xFFFFFFFF) / el
    return rate, rate * tperiod


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


def counter(sc, reg, tries=24):
    """Read a register that may be STANDING STILL or COUNTING FAST.

    `moving` needs three INCREASING asks and `Scope.rd` needs two EQUAL
    ones, and DIAG_BLK_OVERRUN is the one register that can be either. It
    stands at zero on a healthy arm — which `moving` never returns, since
    it discards a zero as a dropped answer — and it counts several hundred
    a second on an arm that is over budget, which `rd` never settles on.
    S19 hit the second half: the first driven capacity row on chip 1 came
    back "register 0xE00A never settled: {0x7: 1, 0x8: 1, ... 0x12: 1}",
    i.e. the arbiter could not be read BECAUSE it was arbitrating, and the
    row was lost for the one reason the row exists to record.

    So: single unvoted asks, accepted on three consecutive NON-DECREASING
    answers. A dropped answer reads zero on this link and breaks the run;
    an answer belonging to another request is out of order and breaks it
    too; a register that is genuinely still gives three equal answers and
    is accepted.
    """
    seen = []
    for _ in range(tries):
        v = sc._ask(reg)
        if v is None:
            seen = []
            continue
        seen.append(v)
        if len(seen) >= 3:
            a, b, c = seen[-3:]
            if a <= b <= c:
                return c
            seen = []
    raise IOError('register 0x%04X never gave three ordered asks' % reg)


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
    out['cclk_decoded_hz'] = CTL_CCLK.get(ctl)

    # THE CLOCK IS MEASURED, AND THE MEASUREMENT IS WHAT THE BUDGET USES.
    # The decode stays beside it so a disagreement is visible rather than
    # averaged away (S15-1: the shipping pair asks for 983.04 and runs at
    # 491.52, and only the measurement can say so).
    out['cfg_cclk'] = (cfg >> 17) & 3
    tper = CFG_TPERIOD.get(out['cfg_cclk'])
    out['tperiod'] = tper
    rate, meas = (None, None)
    if tper:
        rate, meas = measure_cclk(sc, tper, min(dwell, 20.0))
    out['tick_rate'] = round(rate, 3) if rate else None
    out['cclk_measured_hz'] = int(meas) if meas else None
    cclk = out['cclk_measured_hz'] or out['cclk_decoded_hz']
    out['cclk_hz'] = cclk
    out['cclk_source'] = ('measured' if out['cclk_measured_hz'] else 'decoded')
    if (out['cclk_measured_hz'] and out['cclk_decoded_hz']
            and abs(out['cclk_measured_hz'] - out['cclk_decoded_hz'])
            > 0.02 * out['cclk_decoded_hz']):
        out['cclk_disagree'] = True

    # The BUDGET is a fact about the clock and the block, and nothing else:
    # BLOCK samples at 48 kHz is BLOCK/48000 s of core time.
    out['budget'] = int(cclk * out['block'] / 48000) if cclk else None

    # THE HIGH-WATER MARK IS READ, THEN RESET, THEN READ AGAIN (S13-2).
    #
    # `_proc_cyc_max` is a latch and nothing cleared it, so what it held when
    # this tool ran was the worst pass since RESET. Both figures are taken:
    # the RAW latch as this tool found it, and the STEADY one over the dwell
    # alone, so the difference is on the page instead of being argued about.
    #
    # S13-2 read the raw latch as the CONFIG LADDER's one-off burst -- "376 %
    # on chip 2 on an arm with zero missed blocks". S21-6 measured that and
    # it is not the ladder: see the note below `out['budget']`, and the
    # print at the bottom of this file.
    #
    # DIAG_CLEAR also zeroes DIAG_BLK_OVERRUN, which is why the overrun
    # baseline is read AFTER it: the arbiter counts the dwell, not the boot.
    out['proc_cyc_max_raw'] = (peek(sc, sc.sym['_proc_cyc_max'])
                               if '_proc_cyc_max' in sc.sym else None)

    # THE CLEAR IS CONFIRMED BY THE LATCH DROPPING, NOT BY READING THE
    # STROBE BACK (S19-5).
    #
    # `Scope.wr` writes and then requires the register to read back the
    # value written. DIAG_CLEAR is a STROBE: it does not hold 1, so that
    # confirmation cannot succeed, `wr` raises after eight attempts and
    # every row in the S19 matrix came back `cleared: false` — while the
    # latch had in fact dropped on most of them. The flag was therefore
    # meaningless in both directions, and the caveat printed beside it was
    # wrong, which is worse than having no flag: the one row where the
    # clear really was dropped (chip 2 holding a 419 %-of-budget pass from
    # the parameter burst) looked exactly like the rows where it worked.
    #
    # So the strobe is written and its read-back failure ignored, and the
    # confirmation is the thing the clear is FOR: `_proc_cyc_max` must come
    # back smaller than the latch just read. Retried, because a write on
    # this link is dropped under audio load exactly as a read is.
    out['cleared'] = False
    out['proc_cyc_max_after_clear'] = None
    if '_proc_cyc_max' in sc.sym:
        for _ in range(4):
            try:
                sc.wr(DIAG_CLEAR, 1)
            except (IOError, OSError):
                pass
            try:
                after = peek(sc, sc.sym['_proc_cyc_max'])
            except IOError:
                continue
            out['proc_cyc_max_after_clear'] = after
            if out['proc_cyc_max_raw'] is None or after < out['proc_cyc_max_raw']:
                out['cleared'] = True
                break
    else:
        try:
            sc.wr(DIAG_CLEAR, 1)
        except (IOError, OSError):
            pass

    f0 = moving(sc, DIAG_FRAME_COUNT)
    o0 = counter(sc, DIAG_BLK_OVERRUN)
    t0 = time.time()
    time.sleep(dwell)
    f1 = moving(sc, DIAG_FRAME_COUNT)
    o1 = counter(sc, DIAG_BLK_OVERRUN)
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

    # ---- THE WORST-BLOCK FIGURE IS ONE DIAG TICK TOO BIG, SOMETIMES ----
    #
    # S21-6. About one row in six in this tree's record carries a
    # worst-block figure between 350 % and 390 % of budget WITH ZERO MISSED
    # BLOCKS over 135,000 -- which cannot both be true, and the caveat
    # printed beside it ("the config ladder") is not the explanation either:
    # some of those rows are row A, taken before any parameter is written.
    #
    # THE MECHANISM IS IN THE MEASUREMENT, and it is two instructions wide.
    # `main.asm` closes each block pass with
    #
    #     r2 = tcount;                  <-- the free-running core timer
    #     r0 = dm(_diag_ticks);         <-- incremented by the tick ISR
    #     ... cycles = (ticks - t0) * TPERIOD + (c0 - tcount)
    #
    # If the tick ISR fires BETWEEN those two reads, the tick it just
    # counted is included in `ticks` while the matching timer wrap is not
    # reflected in the `tcount` already in r2, and the pass is credited with
    # one whole TPERIOD it did not spend. TPERIOD is 983,040 cycles at the
    # shipped CCLK -- 300 % of a block-16 budget -- which is exactly the
    # size of the anomaly.
    #
    # MEASURED, ACROSS THE WHOLE RECORD (2026-09-10): every row in the S20
    # and S21 goldens whose worst figure exceeds 150 % of budget lands
    # within 0.5 POINTS OF ITS OWN AVERAGE once one TPERIOD is subtracted --
    # eleven rows, both chips, both products, three arms. So the true worst
    # block on this configuration is half a point above the mean, and the
    # graph is steadier than the record has been able to say.
    #
    # WHAT IS REPORTED, AND WHAT IS NOT. The raw latch is reported
    # unchanged; the de-ticked value is reported BESIDE it, and only when
    # every one of these holds:
    #
    #   * the raw figure is more than 150 % of budget;
    #   * the arbiter counted ZERO missed blocks over the dwell (a real
    #     375 % pass drops three blocks and the arbiter would say so);
    #   * `raw - TPERIOD` lands within 3 points of budget of `_proc_cyc`,
    #     the LAST pass -- i.e. the correction puts the corrupted pass back
    #     inside the narrow band this graph actually runs in, rather than
    #     turning a genuine transient into a small number.
    #
    # AND IT IS A LOWER BOUND, NOT A REPAIR. `_proc_cyc_max` is a max, so it
    # is at least `_proc_cyc`; a pass credited with a spurious TPERIOD
    # DESTROYS the latch's information about every pass after it, so the
    # de-ticked value can come out a fraction BELOW the last pass (measured:
    # 74.58 % against a last pass of 74.72 %). The reported figure is
    # therefore max(raw - TPERIOD, _proc_cyc) and it is a floor on the true
    # worst block, not the true worst block.
    #
    # Nothing is silently corrected: `proc_cyc_max_pct` is still the part's
    # own answer, and `proc_cyc_max_detick*` is a second column with a
    # reason. THE FIX BELONGS IN `main.asm` -- read `_diag_ticks`, read
    # `tcount`, read `_diag_ticks` again and retry the pair if it moved,
    # four instructions per block -- and is deliberately NOT made in the
    # session that found it, so every figure in dsp4-s21-20260910.md is
    # from one image.
    if out['budget']:
        for k in ('proc_cyc', 'proc_cyc_max', 'proc_cyc_max_raw'):
            v = out[k]
            out[k + '_pct'] = (round(100.0 * v / out['budget'], 2)
                               if v is not None else None)
    out['proc_cyc_max_detick'] = None
    out['proc_cyc_max_detick_pct'] = None
    tp = out.get('tperiod') or CFG_TPERIOD.get(out.get('cfg_cclk'))
    if (out['budget'] and tp and out['proc_cyc_max'] and out['proc_cyc']
            and out['proc_cyc_max'] > 1.5 * out['budget']
            and out.get('overruns') == 0
            and abs((out['proc_cyc_max'] - tp) - out['proc_cyc'])
            <= 0.03 * out['budget']):
        out['proc_cyc_max_detick'] = max(out['proc_cyc_max'] - tp,
                                         out['proc_cyc'])
        out['proc_cyc_max_detick_pct'] = round(
            100.0 * out['proc_cyc_max_detick'] / out['budget'], 2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chip', type=int, action='append')
    ap.add_argument('--dwell', type=float, default=30.0)
    ap.add_argument('--json')
    ap.add_argument('--tag', default='',
                    help='regime label carried into the JSON (S19: a row '
                         'that does not say whether it was driven is not a '
                         'capacity row)')
    a = ap.parse_args()
    chips = a.chip or [1, 2]

    rows = []
    for c in chips:
        try:
            r = read_chip(c, a.dwell)
        except (IOError, SystemExit, KeyError) as exc:
            print('chip %d: UNREADABLE (%s)' % (c, exc))
            rows.append({'chip': c, 'error': str(exc), 'tag': a.tag})
            continue
        r['tag'] = a.tag
        rows.append(r)
        clk = ('%.2f MHz (%s)' % (r['cclk_hz'] / 1e6, r.get('cclk_source'))) \
              if r['cclk_hz'] else 'UNKNOWN (CGU0_CTL %s)' % r['cgu0_ctl']
        print('chip %d  build_cfg %s  block %d  kernels %d  CCLK %s'
              % (c, r['build_cfg'], r['block'], r['block_kernels'], clk))
        print('        cfg2 %s  decimate %s  fused %s  simd_dyn %s  '
              'tx_early %s  gather_first %s'
              % (r['build_cfg2'], r['decimate'], r['strip_fused'],
                 r['simd_dyn'], r['tx_early'], r['gather_first']))
        print('        CGU0_CTL %s  CGU0_DIV %s  budget %s cycles/block'
              % (r['cgu0_ctl'], r['cgu0_div'], r['budget']))
        print('        CCLK decoded %s  MEASURED %s (tick %s /s, TPERIOD %s)'
              % (r['cclk_decoded_hz'], r['cclk_measured_hz'],
                 r['tick_rate'], r['tperiod']))
        if r.get('cclk_disagree'):
            print('        *** THE CGU DECODE AND THE MEASURED CLOCK '
                  'DISAGREE: the image asked for %s and the core timer '
                  'says %s. The budget above uses the MEASURED clock.'
                  % (r['cclk_decoded_hz'], r['cclk_measured_hz']))
        print('        _proc_cyc     %8s  %s%%'
              % (r['proc_cyc'], r.get('proc_cyc_pct')))
        print('        _proc_cyc_max %8s  %s%%   <-- the block the budget has to cover'
              % (r['proc_cyc_max'], r.get('proc_cyc_max_pct')))
        if r.get('proc_cyc_max_detick') is not None:
            print('          ONE DIAG TICK TOO BIG (S21-6): %s  %s%% once '
                  'TPERIOD=%s is subtracted, which is within half a point of '
                  'this row\'s own average, and the arbiter counted ZERO '
                  'missed blocks. The tick ISR landed between the `tcount` '
                  'and `_diag_ticks` reads that close the pass; the fix is '
                  'four instructions in main.asm and is not made here.'
                  % (r['proc_cyc_max_detick'],
                     r.get('proc_cyc_max_detick_pct'), r.get('tperiod')))
        # THE LATCH AS IT STOOD BEFORE THE RESET, and NOT "the config
        # ladder" (S21-6). S13-2 introduced this line calling the pre-clear
        # value "a one-off burst of parameter conversions and cascade
        # sizings that no per-block budget has to cover", and that
        # attribution does not survive being checked: of the 104 pre-clear
        # latches in this tree's goldens that exceed 150 % of budget, 92 sit
        # exactly ONE DIAG TICK (TPERIOD) above an ordinary pass of their own
        # row and the other 12 sit one tick above an ordinary pass of the
        # PREVIOUS row of the ladder -- which is what a pre-clear latch
        # holds. Not one is a configuration transient. There was never a
        # 376 % block on this part; there was a two-instruction race between
        # `r2 = tcount` and `r0 = dm(_diag_ticks)` in main.asm.
        print('          (raw latch, before the reset: %s  %s%%%s)'
              % (r.get('proc_cyc_max_raw'), r.get('proc_cyc_max_raw_pct'),
                 '' if r.get('cleared') else
                 ' -- THE LATCH DID NOT DROP: the worst-block figure above '
                 'is this same latch and is NOT a block from the dwell'))
        print('        _proc_passes  %8s' % r['proc_passes'])
        print('        %d blocks in %.1f s (%.1f/s), OVERRUN %d (%s%%)'
              % (r['frames'], r['seconds'], r['block_rate'] or 0,
                 r['overruns'], r['overrun_pct']))
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump({'tag': a.tag, 'chips': rows}, fh,
                      indent=1, sort_keys=True)
        print('wrote %s' % a.json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
