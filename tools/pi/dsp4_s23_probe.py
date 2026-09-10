#!/usr/bin/env python3
"""dsp4_s23_probe.py — the S23 gates on the part, each with its own control.

FOUR QUESTIONS, and every one of them has a way to come out wrong.

GATE 2, THE FX RETURN REACHES THE MAIN MIX (S22-2).  `C2_FX_FDR_nn` has
declared `outputs=C2_MIX_MAIN_L;C2_MIX_MAIN_R` since the graph was written
and neither mix node listed it among its INPUTS, so the six engines were
inaudible on every image this tree had built. The FX receive slot is driven,
`Fx001On/Level/Mute` are set, and `_buf_C2_MIX_MAIN_L` is captured.

  NEGATIVE CONTROL: `Fx001On001` back to 0. That is S21-4's other half --
  the cell had no reader at all -- and it now PARKS the engine: the block
  kernel publishes a block of zeros and never enters its loop. So the main
  mix must read exactly zero, and so must the engine's own block. Both are
  checked, because "the mix went quiet" and "the engine stopped" are
  different claims.

GATE 3, THE FX RETURN REACHES THE AUX BUSES.  `Fx001AuxOn001` and
`Fx001AuxSend001` on `C2_MIX_AUX_01`, the node that sums aux 1's chip-1 bus
with the six returns. Captured at `_buf_C2_MIX_AUX_01`.

  NEGATIVE CONTROL 1: `Fx001AuxOn001` 0 -- the on/off is folded INTO the
  Q4.28 crosspoint coefficient at block rate, so the contribution is
  exactly zero, not small.
  NEGATIVE CONTROL 2: `Fx001AuxSend001` 0.0 with the On flag left at 1 --
  the two words are independent and a probe that only tests the flag cannot
  tell a working send from a coefficient stuck at unity.
  AND THE PASSTHROUGH, which is the one that matters most, because this
  gate INSERTED A NODE INTO THE AUX CHAIN: with every FX send off, aux 1's
  sum must reproduce `_buf_C2_RECV_AUX_01` WORD FOR WORD. The recv
  coefficient is exactly 1.0, so `(x * 2**28 + 2**27) >> 28 == x` and the
  sum is bit-exact by construction -- which makes "0 of N words differ" a
  real bar and not a tolerance.

GATE 4, THE COMPRESSOR GAIN-REDUCTION METER.  Chip 1: strip 1 driven, the
compressor switched on with a threshold low enough to reduce, and
`Chan001CompMtr001`'s word read back against `_comp_gain_C1_COMP_01`. The
meter publishes 20*log10(gain), so the check is arithmetic on two words the
part produced -- not a comparison against a number typed here.

  NEGATIVE CONTROL: threshold back to 0 dB, where the compressor does not
  reduce; the meter must return to 0.0 dB.

Usage:  dsp4_s23_probe.py [gates]      e.g. `dsp4_s23_probe.py 2,3` (default all)
"""
import math
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
from dsp4_conform import Part, drive_strip, chain_witness

# ---- chip 2, from proposals/defs/products/d32/dsp.csv -------------------
FX1_ON = 0x0654           # Fx001On001
FX1_TYPE = 0x0655         # Fx001Type001
FX1_MIX = 0x0668          # Fx001Mix001
FX1_LEVEL = 0x066C        # Fx001Level001
FX1_MUTE = 0x066E         # Fx001Mute001
FX1_AUXON_1 = 0x07E7      # Fx001AuxOn001   (C2_MIX_AUX_01 + 0)
FX1_AUXSEND_1 = 0x07ED    # Fx001AuxSend001 (C2_MIX_AUX_01 + 6)
AUX1_LEVEL = 0x0000       # Aux001Level001
AUX1_MUTE = 0x0002        # Aux001Mute001
# ---- chip 1 ------------------------------------------------------------
CH1_COMP_ON = 56
CH1_COMP_THR = 57
CH1_COMP_RAT = 58
CH1_COMP_ATT = 59
CH1_COMP_REL = 60
CH1_COMP_PAR = 63
CH1_COMP_MTR = 4611       # Chan001CompMtr001 = meter base 4608 + 3

AMP = 0x0D3A17B5
DB_PER_LOG2 = 20.0 / math.log2(10.0)


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def from_f32(w):
    return struct.unpack('<f', struct.pack('<I', w & 0xFFFFFFFF))[0]


def s32(v):
    return None if v is None else (v - (1 << 32) if v & 0x80000000 else v)


def capture(sc, src, inj, n=32, mode=2):
    """One armed capture of `src`, with the arm cleared on every exit.

    The `finally` is S22-1's lesson and it is not optional: `_scope_tap`
    owns disarming, so a capture that never matches its armed address
    leaves `_scope_arm` set and `_scope_inject_blk` drives the graph for
    ever after. That is what four sessions of "frozen gate state" was.
    """
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


want = sys.argv[1] if len(sys.argv) > 1 else '2,3,4'
gates = {int(g) for g in want.replace(' ', '').split(',') if g}
ok = True
p2 = None


def chip2():
    global p2
    if p2 is None:
        p2 = Part(2)
        print('chip 2: cfg 0x%08X  cfg2 0x%08X'
              % (p2.sc.rd(0xE0EA), p2.sc.rd(0xE0EB)))
    return p2


def arm_fx1(part, on=1):
    """FX 1 audible: engine on, return at unity, unmuted, fully wet.

    TYPE IS LEFT AT ITS DEFAULT (0 = Echo), deliberately. Writing Type 3
    made the whole FX chain read SILENT on 2026-09-08 and that is an open
    defect in the engine, not in the wiring this gate is about; Echo is a
    real algorithm since the same date and it carries the sample.
    """
    part.write(FX1_ON, on, 0)
    part.write(FX1_LEVEL, f32(1.0), 0)
    part.write(FX1_MUTE, 0, 0)
    part.write(FX1_MIX, f32(100.0), 0)
    time.sleep(0.5)


# =========================================================================
if 2 in gates:
    print('--- gate 2: the FX return reaches the MAIN mix ---')
    p = chip2()
    inj = p.sc.sym['_rx_ic_slot_C2_RECV_FX_01']
    # THE FLOOR FIRST, AND IT IS NOT ZERO. The main mix sums 23 sources:
    # chip 1's main bus, four group outputs, twelve superset aux inputs and
    # the six FX returns. On this bench the ADC lanes are NOT silent (the
    # shipping bitstream leaves the converters' noise floor on them), so
    # chip 1's main bus carries a few counts and the main mix can never
    # read exactly zero. The first cut of this probe demanded zero and
    # called 0x0000000B -- 4e-8, about -147 dBFS -- a failure. The bar is
    # the FLOOR MEASURED ON THIS BOOT with the engine parked, which is a
    # real control: it fails if the return leaks into the mix at all.
    p.write(FX1_ON, 0, 0)
    time.sleep(0.5)
    floor = capture(p.sc, '_buf_C2_MIX_MAIN_L', inj)
    print('  Fx1On=0  main mix FLOOR peak 0x%08X (the other 22 sources)'
          % pk(floor))
    arm_fx1(p, 1)
    eng_on = capture(p.sc, '_buf_C2_FX_ENG_01', inj)
    fdr_on = capture(p.sc, '_buf_C2_FX_FDR_01', inj)
    mix_on = capture(p.sc, '_buf_C2_MIX_MAIN_L', inj)
    print('  Fx1On=1  engine peak 0x%08X  return peak 0x%08X  '
          'main mix peak 0x%08X' % (pk(eng_on), pk(fdr_on), pk(mix_on)))
    if pk(eng_on) == 0:
        print('  NO VERDICT: the engine itself is silent — nothing '
              'downstream of it can be measured')
        ok = False
    elif pk(fdr_on) == 0:
        print('  FAIL: the engine runs and the RETURN STRIP is silent')
        ok = False
    elif pk(mix_on) == 0:
        print('  FAIL: the return strip carries the block and the MAIN MIX '
              'does not — this is S22-2 unfixed')
        ok = False
    else:
        print('  the return reaches the main mix')

    p.write(FX1_ON, 0, 0)
    time.sleep(0.5)
    eng_off = capture(p.sc, '_buf_C2_FX_ENG_01', inj)
    mix_off = capture(p.sc, '_buf_C2_MIX_MAIN_L', inj)
    print('  Fx1On=0  engine peak 0x%08X  main mix peak 0x%08X'
          '   <- the negative control' % (pk(eng_off), pk(mix_off)))
    if None in (eng_off, mix_off, floor):
        print('  NO VERDICT: a control capture failed')
        ok = False
    elif pk(eng_off) != 0:
        print('  FAIL: Fx001On001 = 0 and the engine still publishes — the '
              'park is not parking')
        ok = False
    else:
        # EXACTLY ZERO where it can be exact, and the measured floor where
        # it cannot: the engine's own block is the park's own output and it
        # must be zero to the word; the mix is a 23-source sum and its bar
        # is that the return's contribution is GONE, not that the bus is
        # dead.
        drop = (20.0 * math.log10(pk(mix_on) / float(pk(mix_off)))
                if pk(mix_off) else float('inf'))
        print('  the return contributes %s dB above the parked mix; the '
              'parked mix is %+.1f dB against the floor measured before it'
              % ('%.1f' % drop if drop != float('inf') else 'inf',
                 20.0 * math.log10(max(pk(mix_off), 1) / float(max(pk(floor), 1)))))
        if drop < 90.0:
            print('  FAIL: parking the engine did not remove the return '
                  'from the main mix')
            ok = False
        elif pk(mix_off) > 4 * max(pk(floor), 1):
            print('  FAIL: the parked mix is above the floor this boot '
                  'measured — something of the return is still reaching it')
            ok = False
        else:
            print('  PASS: gate 2 — the return reaches the main mix, and '
                  'only while Fx001On001 says so; the engine parks to '
                  'EXACTLY zero')
    arm_fx1(p, 1)

# =========================================================================
if 3 in gates:
    print('--- gate 3: the FX return reaches the AUX buses ---')
    p = chip2()
    inj = p.sc.sym['_rx_ic_slot_C2_RECV_FX_01']
    arm_fx1(p, 1)
    p.write(AUX1_LEVEL, f32(1.0), 0)
    p.write(AUX1_MUTE, 0, 0)
    p.write(FX1_AUXSEND_1, f32(1.0), 0)
    time.sleep(0.2)
    p.write(FX1_AUXON_1, 1, 0)
    time.sleep(0.5)
    fdr = capture(p.sc, '_buf_C2_FX_FDR_01', inj)
    sum_on = capture(p.sc, '_buf_C2_MIX_AUX_01', inj)
    print('  send ON  return peak 0x%08X   aux 1 sum peak 0x%08X'
          % (pk(fdr), pk(sum_on)))

    p.write(FX1_AUXON_1, 0, 0)
    time.sleep(0.5)
    sum_off = capture(p.sc, '_buf_C2_MIX_AUX_01', inj)
    recv_off = capture(p.sc, '_buf_C2_RECV_AUX_01', inj)
    print('  AuxOn=0  aux 1 sum peak 0x%08X   <- negative control 1'
          % pk(sum_off))

    p.write(FX1_AUXON_1, 1, 0)
    p.write(FX1_AUXSEND_1, f32(0.0), 0)
    time.sleep(0.5)
    sum_zero = capture(p.sc, '_buf_C2_MIX_AUX_01', inj)
    print('  Send=0   aux 1 sum peak 0x%08X   <- negative control 2'
          % pk(sum_zero))

    if None in (fdr, sum_on, sum_off, recv_off, sum_zero):
        print('  NO VERDICT: a capture failed')
        ok = False
    else:
        if pk(fdr) == 0:
            print('  NO VERDICT: the return strip is silent')
            ok = False
        elif pk(sum_on) == 0:
            print('  FAIL: the send is on at unity and aux 1 is silent')
            ok = False
        elif pk(sum_off) != 0 or pk(sum_zero) != 0:
            print('  FAIL: aux 1 is not silent with the send off/at zero')
            ok = False
        else:
            print('  PASS: the return reaches aux 1, and only when sent')
        # THE PASSTHROUGH. With the sends off the inserted node must be
        # transparent, word for word.
        diff = [i for i, (a, b) in enumerate(zip(sum_off, recv_off))
                if a != b]
        print('  passthrough with every send off: %d of %d words differ '
              'from _buf_C2_RECV_AUX_01' % (len(diff), len(sum_off)))
        if diff:
            print('    first at word %d: sum 0x%08X vs recv 0x%08X'
                  % (diff[0], sum_off[diff[0]] & 0xFFFFFFFF,
                     recv_off[diff[0]] & 0xFFFFFFFF))
            print('  FAIL: inserting C2_MIX_AUX_* changed the aux bus')
            ok = False
        else:
            print('  PASS: gate 3 — the aux sum is BIT-EXACT '
                  'passthrough with the sends off')
    p.write(FX1_AUXSEND_1, f32(0.0), 0)
    p.write(FX1_AUXON_1, 0, 0)

# =========================================================================
if 4 in gates:
    print('--- gate 4: the compressor gain-reduction meter ---')
    p1 = Part(1)
    print('chip 1: cfg 0x%08X  cfg2 0x%08X'
          % (p1.sc.rd(0xE0EA), p1.sc.rd(0xE0EB)))
    if '_mtr_cgr_C1_MTR_01' not in p1.sc.sym:
        print('  no _mtr_cgr_C1_MTR_01 in this image — not an S23 build')
        ok = False
    else:
        inj = p1.sc.sym['_rx_slot_C1_IN_01']
        drive_strip(p1, 1)
        chain_witness(p1, inj, 1)
        # FAST TIME CONSTANTS, for famverify's COMPRESSOR reason: at
        # drive_strip's default alpha the envelope has not settled between
        # two reads and the meter is measured mid-ramp.
        # THE GAIN WORD IS LIVE, AND A FAST RELEASE MAKES IT UNREADABLE.
        # The first run of this probe set attack and release to 0.5 ms for
        # famverify's reason -- so the envelope settles inside the capture
        # -- and then read `_comp_gain_C1_COMP_01` AFTERWARDS: the scope's
        # step injection stops when the tap disarms, and at a 0.5 ms
        # release the gain is back at unity (0x10000000) long before a
        # paced peek can reach it. The audio said the compressor was
        # working the whole time (`_buf_C1_COMP_01` at 0x02BD1D96 against
        # `_buf_C1_GATE_01` at 0x07FFE779, -9.5 dB), so what was measured
        # was the RECOVERY, not the meter.
        #
        # Attack stays fast, so the reduction settles inside the 1024-sample
        # capture; RELEASE is 30 seconds, so the reduced gain is still
        # standing when the two words are read. The two are read back to
        # back and the check is the ARITHMETIC between them -- the meter
        # must be 20*log10 of the gain word -- not either value against a
        # number typed here.
        p1.write(CH1_COMP_ON, 1, 0)
        p1.write(CH1_COMP_PAR, f32(100.0), 0)
        p1.write(CH1_COMP_RAT, f32(4.0), 0)
        p1.write(CH1_COMP_ATT, f32(0.5), 0)
        p1.write(CH1_COMP_REL, f32(30000.0), 0)
        for thr, expect in ((0.0, 'no reduction'), (-40.0, 'reducing')):
            p1.write(CH1_COMP_THR, f32(thr), 0)
            time.sleep(0.2)
            # The graph has to be RUNNING for the compressor to have a
            # gain: one armed capture drives the strip, and the two words
            # are read straight afterwards.
            comp = capture(p1.sc, '_buf_C1_COMP_01', inj)
            gate = capture(p1.sc, '_buf_C1_GATE_01', inj)
            m = p1.sc.peek(p1.sc.addr('_mtr_cgr_C1_MTR_01'))
            g = p1.sc.peek(p1.sc.addr('_comp_gain_C1_COMP_01'))
            got = from_f32(m)
            lin = (g & 0xFFFFFFFF) / float(1 << 28)
            want_db = (max(-40.0, min(0.0, DB_PER_LOG2 * math.log2(lin)))
                       if lin > 0 else -40.0)
            err = abs(got - want_db)
            # The AUDIO's own reduction, for the same interval, as the
            # independent witness that the compressor did something.
            audio_db = (20.0 * math.log10(pk(comp) / float(pk(gate)))
                        if pk(comp) and pk(gate) else float('nan'))
            print('  thr %6.1f dB (%s): audio %+6.2f dB, _comp_gain '
                  '0x%08X = %.6f  ->  meter %+8.3f dB, 20log10(gain) '
                  '%+8.3f dB, err %.4f dB  %s'
                  % (thr, expect, audio_db, g, lin, got, want_db, err,
                     'ok' if err < 0.25 else 'MISMATCH'))
            if err >= 0.25:
                ok = False
            if abs(thr) < 1e-9 and abs(got) > 1e-6:
                print('  FAIL: the compressor is not reducing and the meter '
                      'does not read 0.0 dB')
                ok = False
            if thr < -1.0 and got > -0.5:
                print('  FAIL: the compressor IS reducing and the meter did '
                      'not move')
                ok = False
        p1.write(CH1_COMP_THR, f32(0.0), 0)
        p1.write(CH1_COMP_ON, 0, 0)

print()
print('S23 PROBE: %s' % ('PASS' if ok else 'NO VERDICT / FAIL'))
sys.exit(0 if ok else 1)
