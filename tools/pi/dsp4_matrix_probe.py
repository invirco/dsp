#!/usr/bin/env python3
"""dsp4_matrix_probe.py — does a channel reach the matrix bus, and does the
matrix master reach its words? (S22 gate 1.)

Two questions, each with its own negative control, because a number that
cannot come out wrong is not evidence.

THE CROSSPOINT (chip 1).  Strip 1 is taken off every legacy bus -- MainOn 0,
sub and the four groups already 0 by default -- so the matrix crosspoint is
the ONLY live one on that strip. `Chan001MatrixOn001` is set and
`Chan001MatrixSend001` written to a known level, the strip is driven by the
scope's step, and `_buf_C1_BUS_MTX_01` is captured. The bus must carry the
strip's post-fader block.

  NEGATIVE CONTROL: `Chan001MatrixOn001` back to 0. The crosspoint
  coefficient is then exactly zero (the assign bit is folded INTO the
  coefficient at control rate, D5), so the bus must read exactly zero. A
  capture that is non-zero with the send off is a bus being fed by something
  this probe did not ask for.

THE MASTER (chip 2).  `Matrix001Level001` and `Matrix001Mute001` are written
over SPI and read back out of the node's own words. That is the "contract
answering" half: the cells the definition names reach the kernel variables
the graph builds.

Usage:  dsp4_matrix_probe.py [matrix_index]
"""
import struct, sys, time
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
from dsp4_conform import Part, STRIDE, drive_strip, chain_witness

# From proposals/defs/products/d32/dsp.csv (chip 1, channel stride 144).
CHAN_MAIN_ON = 0x0054          # Chan001MainOn001
MTX_ON_BASE = 0x12C6           # Chan001MatrixOn001/002
MTX_SEND_BASE = 0x12C8         # Chan001MatrixSend001/002
# chip 2
MTX_LEVEL = 0x07D3             # Matrix001Level001,  +5 per matrix
MTX_MUTE = 0x07D5              # Matrix001Mute001
MTX_STRIDE = 5

AMP = 0x0D3A17B5


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def s32(v):
    return None if v is None else (v - (1 << 32) if v & 0x80000000 else v)


def capture(sc, src, inj, amp, n=32):
    try:
        sc.d.resync()
        sc.arm(sc.sym[src], inj, amp, 2)
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


M = int(sys.argv[1]) if len(sys.argv) > 1 else 1
ok = True

print('--- chip 1: the crosspoint ---')
p1 = Part(1)
sc1 = p1.sc
print('cfg 0x%08X  cfg2 0x%08X' % (sc1.rd(0xE0EA), sc1.rd(0xE0EB)))
bus = '_buf_C1_BUS_MTX_%02d' % M
if bus not in sc1.sym:
    sys.exit('no %s in this image — not a matrix build' % bus)
inj = sc1.sym['_rx_slot_C1_IN_01']

# THE STRIP HAS TO BE DRIVEN BEFORE ANY BUS CAN BE. A boot leaves the
# channel fader at its dsp.csv default of `level_db=-inf`, so the post-fader
# block -- which is the ONLY source the dense crosspoint path reads -- is
# exactly zero however hard the input is driven. drive_strip() is the
# established helper for this and it is what every other bus bar uses; the
# first run of this probe skipped it and measured a silent matrix bus fed by
# a silent strip.
drive_strip(p1, 1)
chain_witness(p1, inj, 1)
p1.write(CHAN_MAIN_ON, 0, 0)                       # off every legacy bus
time.sleep(0.05)
# UNITY IS 1.0, NOT 0.0 dB. `_rtg_<kind>_send_` is a LINEAR gain: the
# send-ramp prep multiplies it by 2^28 and FIXes the result into the
# crosspoint coefficient, with the on/off bit folded in. The cell's `dB:`
# table is the SURFACE mapping, not what the DSP word holds. Writing 0.0
# here asks for silence, which is what the first run of this probe measured
# and briefly mistook for a dead crosspoint.
p1.write(MTX_SEND_BASE + (M - 1), f32(1.0), 0)     # unity into matrix M
time.sleep(0.05)
p1.write(MTX_ON_BASE + (M - 1), 1, 0)
time.sleep(0.5)

# POSITIVE CONTROL FIRST: is the strip driven at all? A silent matrix bus
# means nothing if the strip that feeds it is silent too.
fdr = capture(sc1, '_buf_C1_FDR_01', inj, AMP)
pk_fdr = max(abs(x) for x in fdr) if fdr else 0
print('  strip 1 post-fader peak = 0x%08X   <- the positive control'
      % pk_fdr)
if pk_fdr == 0:
    print('  NO VERDICT: the strip is not driven; nothing downstream can be')
    ok = False

live = capture(sc1, bus, inj, AMP)
print('  send ON : %s' % (live[:6] if live else None))

p1.write(MTX_ON_BASE + (M - 1), 0, 0)
time.sleep(0.5)
off = capture(sc1, bus, inj, AMP)
print('  send OFF: %s' % (off[:6] if off else None))

if live is None or off is None:
    print('  NO VERDICT: a capture failed')
    ok = False
else:
    pk_on = max(abs(x) for x in live)
    pk_off = max(abs(x) for x in off)
    print('  peak with the send ON  = 0x%08X' % pk_on)
    print('  peak with the send OFF = 0x%08X   <- the negative control' % pk_off)
    if pk_on == 0:
        print('  FAIL: the matrix bus is silent with the send ON')
        ok = False
    elif pk_off != 0:
        print('  FAIL: the matrix bus is NOT silent with the send OFF')
        ok = False
    else:
        print('  PASS: the channel reaches matrix %d, and only when sent' % M)

print('--- chip 2: the master ---')
p2 = Part(2)
sc2 = p2.sc
lvl_sym = '_fdr_level_C2_MTX_FDR_%02d' % M
mute_sym = '_fdr_mute_C2_MTX_FDR_%02d' % M
if lvl_sym not in sc2.sym:
    sys.exit('no %s in this image' % lvl_sym)
for val, name in ((f32(-6.0), '-6.0 dB'), (f32(0.0), '0.0 dB')):
    p2.write(MTX_LEVEL + (M - 1) * MTX_STRIDE, val, 0)
    time.sleep(0.3)
    got = sc2.peek(sc2.addr(lvl_sym))
    print('  Level %-8s written 0x%08X  read 0x%08X  %s'
          % (name, val, got, 'ok' if got == val else 'MISMATCH'))
    ok &= (got == val)
for val in (1, 0):
    p2.write(MTX_MUTE + (M - 1) * MTX_STRIDE, val, 0)
    time.sleep(0.3)
    got = sc2.peek(sc2.addr(mute_sym))
    print('  Mute  %-8s written %d           read %s  %s'
          % ('', val, got, 'ok' if got == val else 'MISMATCH'))
    ok &= (got == val)

print()
print('MATRIX PROBE: %s' % ('PASS' if ok else 'NO VERDICT / FAIL'))
sys.exit(0 if ok else 1)
