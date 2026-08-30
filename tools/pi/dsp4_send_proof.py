#!/usr/bin/env python3
"""xp_send.py — can a routing send actually reach its aux bus?

Three things had to be true at once for this to work and none of them were:
the send's ramp target had to land (the ramp-stride table said stride 0 for
every scalar and 12 for the sends, and _ramp_set_target wrote the companions
onto neighbouring crosspoints before that); the send COEFFICIENT had to be
computed (ROUTING's block-rate prep sat behind a `_sample_idx == 0` guard
that never fires in a block-kernel build); and the pickoff had to name a
real source (the block form handed _acc64_mac_blk the address of a SCALAR
tap).

So this probe asserts the whole path, and runs a negative control first:
with the send at 0 the aux bus must read 0, or the test cannot fail.
"""
import struct, sys, time
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
import fixed_ref as fr

GAIN = 0x0000
GATE_ON, COMP_ON, TUBE_ON, DLY_OFF = 0x0028, 0x0038, 0x004C, 0x004E
FDR_LEVEL, FDR_PAN, FDR_MUTE = 0x0050, 0x0051, 0x0052
HPF0, HPF_SW, LPF0, LPF_SW = 0x0004, 0x0009, 0x000A, 0x000F
EQ0, EQ_SW = 0x0010, 0x0024
AUX_ON_1, AUX_SEND_1, AUX_PICK_1 = 0x005A, 0x0066, 0x0072   # from the map, checked below
UNITY = [1.0, 0.0, 0.0, 0.0, 0.0]
AMP = 0x08000000

def f32(x): return struct.unpack('<I', struct.pack('<f', float(x)))[0]
def sgn(v): return v - (1 << 32) if v & 0x80000000 else v
def rns(a, sh=28):
    """Delegates to the normative model (review finding D32): this
    used to be a hand copy of the round-and-saturate, which is
    exactly the arithmetic that must not exist in two places."""
    return fr.sat32(fr.rns(a, sh))

sc = S.Scope(1); sc.check_chip()
POOL = sc.sym.get('_blk_pool')
INJ = (POOL if POOL else sc.sym['_rx_slot_C1_IN_01'])
MONO = (POOL if POOL else sc.sym['_buf_C1_FDR_01'])
AUXBUS = sc.sym['_buf_C1_BUS_AUX_01']
SQ = sc.sym['_rtg_aux_sq_C1_RTG_01']
SRC = sc.sym.get('_rtg_aux_src_C1_RTG_01')
print('build: %s   aux_sq=0x%X  aux_src=%s' %
      ('BLOCK KERNELS' if POOL else 'per-sample',
       SQ, ('0x%X' % SRC) if SRC else 'absent'))

def peek(a):
    for _ in range(8):
        try: return sc.d.peek(a)
        except Exception: time.sleep(0.05)
    return None
def cap(addr):
    sc.arm(addr, INJ, AMP, 2)
    if not sc.wait(): raise SystemExit('scope never disarmed')
    return sgn(sc.fetch(8)[7])
def wr(a, v, rid=0):
    sc.d.link.write(a, v, rid); time.sleep(0.05)

# transparent strip
wr(GAIN, f32(1.0), 1)
for base, sw in ((HPF0, HPF_SW), (LPF0, LPF_SW)):
    for i, c in enumerate(UNITY): wr(base + i, f32(c))
    for _ in range(3): wr(sw, 1)
for band in range(4):
    for i, c in enumerate(UNITY): wr(EQ0 + band * 5 + i, f32(c))
for _ in range(3): wr(EQ_SW, 1)
for a in (GATE_ON, COMP_ON, TUBE_ON, FDR_MUTE): wr(a, 0)
wr(DLY_OFF, 0)
wr(FDR_LEVEL, f32(1.0), 1); wr(FDR_PAN, f32(0.5), 1)
time.sleep(0.8)

bad = 0
# ---- negative control: send off -> aux bus silent ----
wr(AUX_ON_1, 0); wr(AUX_SEND_1, f32(0.0), 1); time.sleep(0.6)
off = cap(AUXBUS)
print('negative control: AuxOn=0 -> aux bus = %d  %s'
      % (off, 'ok' if off == 0 else '<-- NOT SILENT, probe is meaningless'))
bad += 0 if off == 0 else 1

for pick, name in ((3, 'post-fader'), (0, 'post-trim'), (1, 'post-EQ'), (2, 'pre-fader')):
    wr(AUX_PICK_1, pick)
    wr(AUX_ON_1, 1)
    for lvl in (1.0, 0.5):
        wr(AUX_SEND_1, f32(lvl), 1)
        time.sleep(0.6)
        coeff = peek(SQ)
        src = peek(SRC) if SRC else None
        bus = cap(AUXBUS)
        want_c = int(round(lvl * (1 << 28)))
        # The strip is configured transparent, so the value at every pickoff
        # is the injected amplitude; the bus is that times the crosspoint
        # coefficient, rounded once at _acc64_rns28.
        want_b = rns(AMP * want_c)
        ok = (coeff == want_c and bus == want_b and bus != 0)
        bad += 0 if ok else 1
        print('pick=%-11s send=%-4g coeff=0x%08X/0x%08X src=%s bus=%10d/%-10d  %s'
              % (name, lvl, coeff or 0, want_c,
                 ('0x%X' % src) if src else '-', bus, want_b,
                 'ok' if ok else '<-- MISMATCH'))
wr(AUX_ON_1, 0); wr(AUX_SEND_1, f32(0.0), 1)
print('SENDS %s (%d checks mismatched)' % ('WORK' if bad == 0 else 'BROKEN', bad))
sys.exit(1 if bad else 0)
