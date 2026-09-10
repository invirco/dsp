#!/usr/bin/env python3
"""dsp4_s25_pan_probe.py — THE PAN LAW ON THE PART (PW ruling R5).

WHAT IS BEING PROVED. R5 (amended) puts the whole mixer on ONE 127-entry
table of (gL, gC, gR): `Sys[1-1]LcrLaw[1-1]` selects the law, every
channel's `Pan` is an INDEX into it, `Chan*LcrOn` selects the
three-column read per channel, and `Chan*CtrOn` gates the centre leg.
This probe reads the three published legs off the running graph and
requires them to equal, WORD FOR WORD, what tools/dsp/pan_table.py says
the table holds — for both laws, both modes, and five pan positions
including both extremes and the exact centre.

The model is not a copy of the arithmetic: pan_table.py is the module the
GENERATOR built the tables from, so a disagreement here is a real
disagreement between the law and the part and not two transcriptions
drifting apart.

THE CONTROL IS THE TABLE ITSELF, AND IT IS TAKEN FIRST (S24-7). Before
any verdict, the probe reads `_pan_tab_lcr` at the centre index straight
out of the part's DM and compares it with the model. If that disagrees,
either the image does not carry the table or this probe is reading the
wrong window, and every bar below would report a clean FAIL for a reason
that has nothing to do with the pan law. It refuses a verdict instead.
That is the discipline S24-7 cost a session to learn: `Scope.rd()` reads
the SPI cell window and answers ZERO for a DM address, which is exactly
what a broken feature looks like. DM words are read with `peek(addr())`.

THE FOUR THINGS THAT CAN GO WRONG, and each has a row that fails on it:

  1. The table is not in the image, or is the wrong law's words.
     -> the control, above.
  2. `Pan` does not become an INDEX (the round, the clamp, the x3).
     -> five positions per arm, including 0 and 126, which land on
        different words of the table and cannot all be right by accident.
  3. `Chan*LcrOn` does not select the three-column read.
     -> every position is taken twice, once in each mode, and the LCR
        arm's legs are the stereo arm's MINUS half the centre, which no
        stuck value reproduces.
  4. `Sys[1-1]LcrLaw[1-1]` does not swap the table.
     -> every position is taken under both laws. Law 0 and law 1 agree
        at index 0, 63 and 126 and DISAGREE at 31 and 94, so a law
        select that does nothing fails on exactly those two rows and the
        probe says which.

AND THE ONE THAT MATTERS MOST, because it is the claim the rest of the
session rests on: under law 0 with LCR off, the legs must equal the
PRE-R5 arithmetic `fix((1-p) * 2^28)` / `fix(p * 2^28)` word for word.
That is scored separately and named, because R5 is only safe to land if
turning it on does not move a single non-LCR channel's audio.

Usage:  dsp4_s25_pan_probe.py [channel]     default 1
"""
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
sys.path.insert(0, '.')
import dsp4_scope as S
from dsp4_conform import Part
import pan_table as PT

# From proposals/defs/products/d32/dsp.csv (S25). `Sys[1-1]LcrLaw[1-1]`
# has no product cell yet -- the hub lands it -- but the graph dispatches
# it, which is exactly the state R5 describes and the reason it is named
# by address here rather than looked up.
PAN_ADDR = {ch: 81 + 144 * (ch - 1) for ch in range(1, 33)}
LCR_ADDR = {ch: 4934 + (ch - 1) for ch in range(1, 33)}
SYSLAW_ADDR = 4966
POSITIONS = (0, 31, PT.PAN_CENTRE, 94, 126)
# The crosspoint bar's pan position. NOT the centre: see the comment at
# that bar for why an index whose centre leg is unity cannot witness it.
XP_IDX = 31


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def u32(v):
    return v & 0xFFFFFFFF


def main():
    ch = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    nid = 'C1_FDR_%02d' % ch
    rtg = 'C1_RTG_%02d' % ch
    p = Part(1)
    print('chip 1: cfg 0x%08X  cfg2 0x%08X'
          % (p.sc.rd(0xE0EA), p.sc.rd(0xE0EB)))
    print('S25 gate 2 — the one pan table, channel %d (%s)' % (ch, nid))

    sym = p.sc.sym
    for need in ('_pan_tab_lcr', '_pan_tab_cp', '_sys_lcr_law',
                 '_fdr_lq_%s' % nid, '_fdr_cq_%s' % nid, '_fdr_rq_%s' % nid,
                 '_fdr_lcr_on_%s' % nid):
        if need not in sym:
            print('  FAIL: %s is not in this image — the pan table is not in '
                  'the build under test' % need)
            return 1

    # ---- THE CONTROL, FIRST (S24-7): the table's own words -------------
    print('  control: the table in the part\'s DM, at the centre index')
    ctl_ok = True
    for law, base in ((0, '_pan_tab_lcr'), (1, '_pan_tab_cp')):
        got = [u32(p.sc.peek(sym[base] + 3 * PT.PAN_CENTRE + k))
               for k in range(3)]
        want = [u32(w) for w in
                PT.table_q428(law)[3 * PT.PAN_CENTRE:3 * PT.PAN_CENTRE + 3]]
        good = got == want
        ctl_ok &= good
        print('    %-14s idx %d -> %s   want %s   %s'
              % (base, PT.PAN_CENTRE,
                 ' '.join('0x%08X' % w for w in got),
                 ' '.join('0x%08X' % w for w in want),
                 'OK' if good else 'MISMATCH'))
    if not ctl_ok:
        print('  INCONCLUSIVE: the table in the image is not the table the '
              'model describes, so nothing below would mean anything. No '
              'verdict taken — see S24-7.')
        return 2

    ok = True
    shipping_rows = 0
    shipping_ok = 0

    def setpan(law, lcr, idx):
        p.sc.d.link.write(SYSLAW_ADDR, law, 0)
        time.sleep(0.05)
        p.sc.d.link.write(LCR_ADDR[ch], lcr, 0)
        time.sleep(0.05)
        # `Pan` is GainFast/Slew — 3 ms up, 8 ms down. 250 ms is a
        # generous multiple, and the read below is of the CONVERTED legs,
        # so a ramp still in flight shows up as a mismatch rather than as
        # a number that happens to be close.
        p.sc.d.link.write(PAN_ADDR[ch], f32(idx / float(PT.PAN_POSITIONS - 1)),
                          1)
        time.sleep(0.25)

    for law in (0, 1):
        for lcr in (0, 1):
            print('  law %d (%s), LcrOn=%d'
                  % (law, PT.LAW_NAMES[law], lcr))
            for idx in POSITIONS:
                setpan(law, lcr, idx)
                got = (u32(p.sc.peek(sym['_fdr_lq_%s' % nid])),
                       u32(p.sc.peek(sym['_fdr_cq_%s' % nid])),
                       u32(p.sc.peek(sym['_fdr_rq_%s' % nid])))
                want = tuple(u32(w) for w in PT.read_legs(law, idx, bool(lcr)))
                good = got == want
                ok &= good
                note = ''
                # The claim the session rests on: law 0 with LCR off must
                # be the PRE-R5 arithmetic, word for word.
                if law == 0 and lcr == 0:
                    shipping_rows += 1
                    pre = tuple(u32(w) for w in PT.shipping_linear(idx))
                    same = (got[0], got[2]) == pre
                    shipping_ok += same
                    note = ('  == pre-R5 %s' % ('YES' if same else 'NO'))
                print('    idx %3d  gL 0x%08X gC 0x%08X gR 0x%08X   %s%s'
                      % (idx, got[0], got[1], got[2],
                         'OK' if good else
                         'FAIL want %s' % ' '.join('0x%08X' % w for w in want),
                         note))

    # ---- the centre leg reaching the crosspoint ------------------------
    # `Chan*CtrOn` is dispatched to `_rtg_sub_on` and the sub bus IS the
    # centre bus on this product. With LCR on and CtrOn on, ROUTING's
    # sub crosspoint must carry the fader's centre leg and not unity;
    # with CtrOn off it must be exactly zero whatever the pan says.
    #
    # TAKEN OFF CENTRE ON PURPOSE. At index 63 the hard-LCR centre leg IS
    # unity, so the LCR arm and the plain-sub arm read the same word and
    # the bar cannot tell them apart -- it would pass on a build that
    # ignored `LcrOn` entirely. Index 31's centre leg is 0x07DF7DF8, which
    # is neither unity nor zero, so all three rows are distinct.
    subq = '_rtg_subq_%s' % rtg
    ctron = 85 + 144 * (ch - 1)
    if subq in sym:
        print('  the centre leg at the crosspoint (Chan%03dCtrOn001 @ %d), '
              'pan index %d' % (ch, ctron, XP_IDX))
        for lcr, on, expect in ((1, 1, 'the centre leg'),
                                (0, 1, 'unity (a plain sub send)'),
                                (1, 0, 'exactly zero')):
            setpan(0, lcr, XP_IDX)
            p.sc.d.link.write(ctron, on, 0)
            time.sleep(0.25)
            got = u32(p.sc.peek(sym[subq]))
            cq = u32(p.sc.peek(sym['_fdr_cq_%s' % nid]))
            want = 0 if not on else (cq if lcr else 0x10000000)
            good = got == want
            ok &= good
            print('    LcrOn=%d CtrOn=%d -> _rtg_subq 0x%08X  want 0x%08X '
                  '(%s)  %s' % (lcr, on, got, want, expect,
                                'OK' if good else 'FAIL'))
        p.sc.d.link.write(ctron, 0, 0)

    # restore: law 0, LCR off, pan centre — the shipping default
    setpan(0, 0, PT.PAN_CENTRE)
    print('  restored: law 0, LcrOn 0, pan centre')
    print('  pre-R5 identity: %d of %d positions word-for-word'
          % (shipping_ok, shipping_rows))
    print('S25 GATE 2: %s' % ('PASS' if ok and shipping_ok == shipping_rows
                              else 'FAIL'))
    return 0 if (ok and shipping_ok == shipping_rows) else 1


if __name__ == '__main__':
    sys.exit(main())
