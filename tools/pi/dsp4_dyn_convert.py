#!/usr/bin/env python3
"""xp_dyn.py — do the dynamics nodes convert their parameters in a
BLOCK-KERNEL build?

They did not. 132 nodes carried a `_sample_idx == 0` guard, and under
DSP4_BLOCK_KERNELS the chain runs once per block with _sample_idx left at
31, so the guard never fired and every one of them ran on its .var
initialisers. The guard is now per-build; this checks the consequence on
the part rather than trusting the source.

The check is the same for every class because the conversion is:
    _<pfx>_attq = fix(attack_seconds_alpha * 2^31)      (Q0.31)
so writing a host float and reading the converted shadow proves the
block-rate code ran. It runs TWO values per node, because a shadow that
happens to equal the initialiser would otherwise read as a pass.

Usage: xp_dyn.py [chip]
"""
import struct, sys, time
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

def f32(x): return struct.unpack('<I', struct.pack('<f', float(x)))[0]
def fl(v):  return struct.unpack('<f', struct.pack('<I', (v or 0) & 0xFFFFFFFF))[0]

# (enable addr, attack addr, converted shadow symbol, scale, label)
#
# THE ENABLE MATTERS. Every one of these nodes tests its on-flag BEFORE the
# block-rate conversion and bypasses the whole body when it is clear, so a
# bypassed node does not convert its parameters -- they take effect when it
# is next enabled. A probe that runs after something else bypassed the node
# reads a stuck shadow and calls it a conversion failure; that happened on
# 2026-08-27, after dsp4_send_proof.py had switched the gate and compressor
# off to get a transparent strip.
CASES = {
 1: [(0x0028, 0x002A, '_gate_attq_C1_GATE_01',  31, 'C1_GATE_01  (x32)'),
     (0x0038, 0x003B, '_comp_attq_C1_COMP_01',  31, 'C1_COMP_01  (x32)')],
 2: [(0x0050, 0x0052, '_lim_attq_C2_AUX_LIM_01', 31, 'C2_AUX_LIM_01  (x12)'),
     (0x0430, 0x0432, '_gate_attq_C2_GRP_GATE_01', 31, 'C2_GRP_GATE_01 (x4)'),
     (0x0440, 0x0443, '_comp_attq_C2_GRP_COMP_01', 31, 'C2_GRP_COMP_01 (x4)'),
     (0x0520, 0x0523, '_comp_attq_C2_SUB_COMP',  31, 'C2_SUB_COMP   (x1)'),
     (0x0530, 0x0532, '_lim_attq_C2_SUB_LIM',    31, 'C2_SUB_LIM    (x1)'),
     (0x055F, 0x0562, '_comp_attq_C2_MAIN_COMP', 31, 'C2_MAIN_COMP  (x1)'),
     (0x056F, 0x0571, '_lim_attq_C2_MAIN_LIM',   31, 'C2_MAIN_LIM   (x1)'),
     (0x0591, 0x0594, '_comp_attq_C2_MAIN_OCOMP_01', 31, 'C2_MAIN_OCOMP_01 (x4)'),
     (0x05A1, 0x05A3, '_lim_attq_C2_MAIN_OLIM_01', 31, 'C2_MAIN_OLIM_01 (x4)')],
}

chip = int(sys.argv[1]) if len(sys.argv) > 1 else 1
sc = S.Scope(chip); sc.check_chip()
def peek(a):
    for _ in range(10):
        try: return sc.d.peek(a)
        except Exception: time.sleep(0.05)
    return None

bad = 0
for on_spi, spi, sym, frac, label in CASES[chip]:
    if sym not in sc.sym:
        print('%-22s SYMBOL %s ABSENT from the map' % (label, sym)); bad += 1; continue
    sc.d.link.write(on_spi, 1, 0)          # the node must be ENABLED to convert
    time.sleep(0.2)
    a = sc.sym[sym]
    # The HOST FLOAT this shadow is converted from. Peeking it too is what
    # separates "the write never landed" from "the conversion never ran" --
    # without it a stuck shadow has two explanations and the probe cannot
    # tell you which.
    src = sym.replace('_attq_', '_attack_')
    sa = sc.sym.get(src)
    init = peek(a)
    results = []
    for v in (0.125, 0.375):
        sc.d.link.write(spi, f32(v), 0)
        time.sleep(0.4)
        host = peek(sa) if sa else None
        got = peek(a)
        want = int(v * (1 << frac))
        landed = (host is not None and abs(fl(host) - v) < 1e-6)
        results.append((v, host, got, want, landed, got == want))
    ok = all(r[5] for r in results) and results[0][2] != results[1][2]
    bad += 0 if ok else 1
    if not ok and not all(r[4] for r in results):
        verdict = '<-- HOST WRITE DID NOT LAND (says nothing about conversion)'
    elif not ok:
        verdict = '<-- NOT CONVERTED (host float changed, shadow did not)'
    else:
        verdict = 'ok'
    print('%-22s init=0x%08X  %s  %s'
          % (label, init or 0,
             '  '.join('%.3f host=%s q=0x%08X/0x%08X'
                       % (v, ('%.4f' % fl(h)) if h is not None else 'ERR',
                          g or 0, w)
                       for v, h, g, w, _, _ in results),
             verdict))

print('DYNAMICS BLOCK-RATE CONVERSION %s (%d of %d classes failed)'
      % ('RUNS' if bad == 0 else 'BROKEN', bad, len(CASES[chip])))
sys.exit(1 if bad else 0)
