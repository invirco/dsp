#!/usr/bin/env python3
"""dsp4_s24_probe.py — the S24 gate on the part: the main output strips'
own Level and Mute.

WHAT IS BEING PROVED.  `Main{L,R,Ctr,Sub}[1-1]Level[1-1]` and `...Mute[1-1]`
are cells the master has always defined and the graph never had a word for:
the post-crossover chain is EQ -> COMP -> LIM -> OUTPUT_TDM and there is no
fader in it (dsp-unmapped.csv's open question Q1).  S24 puts them on the
OUTPUT_TDM node itself -- one Q4.28 coefficient folded at block rate with
the mute multiplied in, and where that coefficient is exactly 2^28 the node
runs its old copy loop unchanged.

FOUR QUESTIONS, EACH WITH A WAY TO COME OUT WRONG.

  A. THE FOLD IS ARITHMETIC ON THE PART, NOT ON THE DESK.  Write a level,
     read `_out_coeff_<nid>` back and compare it with round(level * 2^28)
     computed here.  This is the only one of the four that needs no signal,
     and it is the one that separates "the cell reached a word" from "the
     word reached the arithmetic".

  B. MUTE IS EXACTLY ZERO, NOT SMALL.  Mute = 1 with the level left at
     unity: every captured word of the output block must be EXACTLY 0.
     The control that makes it a real bar is the node's own INPUT block
     captured on the same boot -- if the limiter's block is silent too then
     the bench had no signal and the zero proves nothing.

  C. LEVEL 0.0 IS EXACTLY ZERO TOO, WITH THE MUTE BIT AT 0.  The two words
     are independent and a probe that only tests the mute cannot tell a
     working level from a coefficient stuck at unity.  This is S23's
     second negative control, one node along.

  D. UNITY PASSES THE BLOCK THROUGH.  Level 1.0, mute 0: the output's peak
     must equal the input's peak.

     THIS IS DELIBERATELY A PEAK BAR AND NOT A BIT-EXACTNESS ONE, and the
     reason is S23-1: the first capture of a boot carries a dynamics-history
     term of up to 1,412 LSB, so two captures taken at DIFFERENT POSITIONS
     within one boot cannot support a word-for-word claim.  The input here
     is downstream of the main compressor and limiter, so it moves between
     captures by construction.  The bit-exactness of the unity path is an
     argument, not a measurement, and it is made where it belongs: the
     coefficient is exactly 2^28, so `(x * 2^28 + 2^27) >> 28 == x`, and
     the generator emits the OLD COPY LOOP for that case anyway -- the
     multiply is not executed at all.  Claiming a measured bit-exact
     passthrough here would be claiming something this instrument cannot
     see.

Usage:  dsp4_s24_probe.py [out]     out = 1|2|4  (MainL / MainR / MainSub)
"""
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
from dsp4_conform import Part

# ---- chip 2, from proposals/defs/products/d32/dsp.csv (S24) -------------
# Second SPI block, allocated after every other chip-2 address, so these
# move nothing that was already landed.
OUTS = {
    1: ('MainL',   'C2_MAIN_OUT_01', 0x0877, 0x0878),
    2: ('MainR',   'C2_MAIN_OUT_02', 0x0879, 0x087A),
    4: ('MainSub', 'C2_MAIN_OUT_04', 0x087D, 0x087E),
}
AMP = 0x0D3A17B5


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def s32(v):
    return None if v is None else (v - (1 << 32) if v & 0x80000000 else v)


def q28(level):
    """round(level * 2^28) the way the node does it: float multiply by
    2^28 then `fix`, which truncates toward zero on this core."""
    return int(level * (1 << 28))


def capture(sc, src, inj, n=32, mode=2):
    """One armed capture, arm cleared on every exit (S22-1)."""
    if src not in sc.sym:
        print('    no %s in this image' % src)
        return None
    try:
        sc.d.resync()
        sc.arm(sc.sym[src], inj, AMP, mode)
        sc.wait()
        out = []
        for i in range(n):
            sc.wr(S.SCOPE_RD, i)
            out.append(s32(sc.rd(S.SCOPE_DATA)))
        return out
    except (IOError, SystemExit) as exc:
        print('    capture failed: %s' % exc)
        return None
    finally:
        try:
            sc.d.write(S.SCOPE_ARM, 0)
        except Exception:                       # noqa: BLE001
            pass


def pk(words):
    return max(abs(w) for w in words) if words else 0


def main():
    which = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    if which not in OUTS:
        print('output %d has no Level/Mute cell (only 1, 2, 4 on D32)' % which)
        return 2
    name, nid, a_lvl, a_mute = OUTS[which]
    p = Part(2)
    print('chip 2: cfg 0x%08X  cfg2 0x%08X'
          % (p.sc.rd(0xE0EA), p.sc.rd(0xE0EB)))
    print('S24 gate 3 — %s (%s), Level 0x%04X / Mute 0x%04X'
          % (name, nid, a_lvl, a_mute))

    # DM WORDS ARE READ WITH peek(addr(...)), NOT WITH rd().
    # `Scope.rd()` reads the SPI diagnostic/cell window; a DM symbol
    # address handed to it lands outside the dispatch table and answers
    # ZERO, which is indistinguishable from a feature that does not work.
    # The first run of this probe did exactly that and reported
    # `_out_coeff = 0x00000000` at every level -- and so did every control
    # word beside it, which is what gave it away (S24-7).
    coeff = '_out_coeff_%s' % nid
    if coeff not in p.sc.sym:
        print('  FAIL: %s is not in this image — the level/mute fold is not '
              'in the build under test' % coeff)
        return 1
    a_coeff = p.sc.sym[coeff]
    inj = p.sc.sym['_rx_ic_slot_C2_RECV_MAIN_L'] \
        if '_rx_ic_slot_C2_RECV_MAIN_L' in p.sc.sym else 0
    ok = True

    def setlvl(level, mute):
        p.sc.d.link.write(a_lvl, f32(level), 1)     # ramped
        time.sleep(0.05)
        p.sc.d.link.write(a_mute, mute, 0)
        time.sleep(0.20)                            # GainFast is 8 ms down

    # ---- THE PROBE'S OWN CONTROL, FIRST (S24-7) ------------------------
    # A word whose value is known and non-zero on any running graph. If
    # this reads zero the part is not running its graph, or this probe is
    # reading the wrong window, and every bar below would report a clean
    # FAIL for a reason that has nothing to do with gate 3.
    ctl = '_fdr_level_C2_MAIN_FDR'
    if ctl in p.sc.sym:
        cv = p.sc.peek(p.sc.sym[ctl])
        print('  control: %s = 0x%08X (expect 0x3F800000 = 1.0)' % (ctl, cv))
        if not cv:
            print('  INCONCLUSIVE: the control word reads zero, so chip 2 is '
                  'not running its graph (or this probe is reading the wrong '
                  'window). No verdict taken — see S24-7.')
            return 2

    # ---- A. the fold, read back off the part ---------------------------
    print('  A. the fold')
    for level, mute in ((1.0, 0), (0.5, 0), (0.25, 0), (1.0, 1), (0.0, 0)):
        setlvl(level, mute)
        got = p.sc.peek(a_coeff)
        want = 0 if mute else q28(level)
        good = abs(s32(got) - want) <= 1        # one LSB for the float step
        ok &= good
        print('     level %-5s mute %d -> _out_coeff 0x%08X  want 0x%08X  %s'
              % (level, mute, got, want & 0xFFFFFFFF,
                 'OK' if good else 'FAIL'))

    # ---- D. unity passes the block through -----------------------------
    print('  D. unity (peak bar — see the module docstring for why it is '
          'not a bit-exactness bar)')
    setlvl(1.0, 0)
    src_in = capture(p.sc, '_blk_C2_MAIN_OLIM_%02d' % which, inj)
    src_out = capture(p.sc, '_blk_%s' % nid, inj)
    pin, pout = pk(src_in or []), pk(src_out or [])
    print('     input peak %d   output peak %d' % (pin, pout))
    if pin == 0:
        print('     INCONCLUSIVE: the limiter block is silent, so nothing '
              'below can fail. Drive the bench (loadlogic.sh driveall + '
              'drive_audio.sh start) and re-run.')
        return 1
    good = pout == pin
    ok &= good
    print('     %s' % ('OK — the copy path passes the peak' if good
                       else 'FAIL — unity changed the level'))

    # ---- B. mute is exactly zero ---------------------------------------
    print('  B. mute = 1, level left at unity')
    setlvl(1.0, 1)
    muted = capture(p.sc, '_blk_%s' % nid, inj)
    nz = sum(1 for w in (muted or []) if w != 0)
    ok &= (muted is not None and nz == 0)
    print('     %d of %d words non-zero  %s'
          % (nz, len(muted or []), 'OK' if muted and nz == 0 else 'FAIL'))

    # ---- C. level 0.0 with the mute bit at 0 ---------------------------
    print('  C. level = 0.0, mute = 0 (the independent control)')
    setlvl(0.0, 0)
    zeroed = capture(p.sc, '_blk_%s' % nid, inj)
    nz = sum(1 for w in (zeroed or []) if w != 0)
    ok &= (zeroed is not None and nz == 0)
    print('     %d of %d words non-zero  %s'
          % (nz, len(zeroed or []), 'OK' if zeroed and nz == 0 else 'FAIL'))

    # restore
    setlvl(1.0, 0)
    print('  restored: level 1.0, mute 0, _out_coeff 0x%08X'
          % p.sc.peek(a_coeff))
    print('S24 GATE 3: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
