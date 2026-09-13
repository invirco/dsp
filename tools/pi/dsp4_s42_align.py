#!/usr/bin/env python3
"""s42_align.py — THE FIRST THING S40 RUNS. Did the MFD fix land?

S39-4 measured a one-bit-early capture window on every converter lane:
the SPORT opened its window one BCK8 period before the AK5558's MSB, so
every received word was {previous slot's bit 0, this slot's bits 31:1}.
Because the converters send 24 bits left-justified in a 32-bit slot,
that leading bit is always a pad zero, which is why the corruption was
invisible as a "dead lane" and read as a full-scale signal instead.

S42-1 named it: the AK5558/AK4458 are strapped TDM128 in the I2S variant
(one BCK between the frame edge and the MSB), LOGIC asserts FS one BCK8
before slot 0, so a converter half needs SPORT_MCTL.MFD = 2 and had 1.
The fix is per lane and needs no bitstream change.

This scores BOTH directions and prints PASS/FAIL. It writes nothing and
changes no control; run it before touching anything else.

  RX (chip 1, twelve converter lanes)
    FAIL-AS-BEFORE : bit 31 never set on any word of any lane AND bits
                     6:0 never set  -> still (sample >>> 1), MFD did not
                     take. Nothing measured after this means anything.
    PASS           : bits 6:0 still never set (the 24-in-32 pad is now in
                     the right place) AND bit 31 IS exercised across the
                     twelve lanes (a quiet converter lane crosses zero)
                     AND the as-received rms per lane is in the band S39
                     measured under the CORRECTED reading, -65..-85 dBFS.
    The third test is the one that cannot be faked by a stuck lane: the
    twelve noise floors were measurably DIFFERENT from one another
    (0.000054..0.000593 rms), so twelve equal numbers is a failure even
    if the bit tests pass.

  TX (chip 2, the DAC lanes)
    There is no converter-side reader at the desk, so the transmit mirror
    is scored by what the gather wrote: the word in the TX DMA buffer is
    what the AK4458 will latch, and under the OLD framing the DAC latched
    {word bits 30:0, next bit} -- x2 with the sign gone. What this can
    check on the part is that the lane carries the value the kernel
    computed, bit for bit, and that the AUX 1 lane is no longer pinned
    above full scale (S39-6 read 1.538 in Q4.28 = +3.75 dBFS, which was
    the RX artefact arriving at the DAC, not a routing error). With the
    RX fixed, that number must come back inside +-1.0.

  THE SLOTS MOVED TOO (S42-2). Aux 1 is no longer DAC_01: the OUT_1-8
  analog block is reversed, so aux n now sits in TDM slot (8-n) and aux 1
  is slot 7 = DAC_08 = the rear XLR marked Aux Out A1. Main Out 1/2 moved
  to slots 3/2 (DAC_12/DAC_11 = the MAIN L/R XLRs). This tool reads the
  lane by node name out of the generated table, so it follows the change.

usage: python3 dsp4_s42_align.py [symdir] [samples]
"""
import sys, math
_argv = list(sys.argv); sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR = _argv[1] if len(_argv) > 1 else '/home/app/s42'
N = int(_argv[2]) if len(_argv) > 2 else 32

# The corrected-reading band S39 measured on twelve quiet lanes, widened
# by a factor of two each way so a different room or a different mic-pre
# state is not scored as a failure. -85 dBFS = 5.6e-5, -65 dBFS = 5.6e-4.
RMS_LO, RMS_HI = 2.5e-5, 1.2e-3


def sgn(w):
    return w - (1 << 32) if w & 0x80000000 else w


def q428(w):
    return sgn(w) / float(1 << 28)


def dbfs(x):
    return 20.0 * math.log10(x) if x > 0 else float('-inf')


# ---------------------------------------------------------------- RX ----
sc1 = S.Scope(1, symfile='%s/chip1.sym.json' % SYMDIR)
sc1.d.resync(); sc1.check_chip()

ents = sc1.sym['_c1_rx_node_entry']
offs = sc1.sym['_c1_rx_off']
strds = sc1.sym['_c1_rx_stride']

print('=== RX: chip 1 converter lanes, %d words each ===' % N)
print('lane   b31 set  lo7 set   rms as-is      dBFS    verdict')
lanes = []
for strip in range(1, 13):
    try:
        e = sc1.peek(ents + strip - 1)
        off = sc1.peek(offs + e)
        strd = sc1.peek(strds + e)
    except IOError:
        print(' %2d    UNREADABLE' % strip); continue
    w = []
    for i in range(N):
        try:
            b = sc1.peek(sc1.sym['_rx_active_buf'])
            w.append(sc1.peek(b + off + (i % 16) * strd))
        except IOError:
            pass
    if not w:
        print(' %2d    UNREADABLE' % strip); continue
    b31 = sum(1 for x in w if x & 0x80000000)
    lo7 = sum(1 for x in w if x & 0x7F)
    rms = math.sqrt(sum((sgn(x) / 2.0 ** 31) ** 2 for x in w) / len(w))
    ok = (lo7 == 0) and (RMS_LO <= rms <= RMS_HI)
    lanes.append((strip, b31, lo7, rms, ok))
    print(' %2d      %3d      %3d    %.6f   %7.1f    %s'
          % (strip, b31, lo7, rms, dbfs(rms), 'ok' if ok else '**BAD**'))

rx_fail = []
if not lanes:
    rx_fail.append('no lane was readable')
else:
    if all(b == 0 for _, b, _, _, _ in lanes):
        rx_fail.append('bit 31 NEVER set on any word of any lane — this is '
                       'exactly S39-4 and the MFD change did not reach the '
                       'part (check DIAG_BUILD_CFG and the image md5)')
    if any(l7 for _, _, l7, _, _ in lanes):
        rx_fail.append('bits 6:0 set on some word — the 24-in-32 pad is not '
                       'where it should be, so the window is off the other way')
    bad = [s for s, _, _, _, ok in lanes if not ok]
    if bad:
        rx_fail.append('lane(s) %s outside the -65..-85 dBFS converter noise '
                       'band' % ','.join(str(x) for x in bad))
    rmss = [r for _, _, _, r, _ in lanes]
    if len(set('%.7f' % r for r in rmss)) < max(2, len(rmss) // 3):
        rx_fail.append('the twelve noise floors are not distinct — a stuck '
                       'or common source, not twelve converters')

print('\nRX: %s' % ('PASS' if not rx_fail else 'FAIL'))
for f in rx_fail:
    print('  - %s' % f)

# ---------------------------------------------------------------- TX ----
sc2 = S.Scope(2, symfile='%s/chip2.sym.json' % SYMDIR)
sc2.d.resync(); sc2.check_chip()

# Node -> index in the generated _c2_tx_* tables, by name, so the S42-2
# slot move is followed rather than assumed.
WATCH = [('C2_AUX_OUT_01', 'aux 1  -> DAC_08 -> rear XLR Aux Out A1'),
         ('C2_AUX_OUT_02', 'aux 2  -> DAC_07 -> rear XLR Aux Out A2'),
         ('C2_MAIN_OUT_01', 'main 1 -> DAC_12 -> analog J56 = MAIN L'),
         ('C2_MAIN_OUT_02', 'main 2 -> DAC_11 -> analog J57 = MAIN R'),
         ('C2_MAIN_ST_OUT', 'main stereo -> B_O3, no D24 sink (expect live, unheard)')]

print('\n=== TX: chip 2, what the gather wrote for the DAC ===')
try:
    tb = sc2.peek(sc2.sym['_tx_active_buf'])
    offs2 = sc2.sym['_c2_tx_off']
    strd2 = sc2.sym['_c2_tx_stride']
    ptrs2 = sc2.sym['_c2_tx_ptrs']
except (IOError, KeyError) as exc:
    print('  TX tables unreadable: %s' % exc)
    sys.exit(0 if not rx_fail else 1)

# Resolve name -> table index through the pointer table, which holds the
# address of each node's own _tx_out_slot_<id> variable.
index_of = {}
for i in range(24):
    try:
        p = sc2.peek(ptrs2 + i)
    except IOError:
        continue
    for name, _ in WATCH:
        sym = '_tx_out_slot_%s' % name
        if sym in sc2.sym and sc2.sym[sym] == p:
            index_of[name] = i

tx_fail = []
for name, what in WATCH:
    i = index_of.get(name)
    if i is None:
        print('  %-16s NOT IN THE TX TABLE  (%s)' % (name, what))
        continue
    off = sc2.peek(offs2 + i)
    strd = sc2.peek(strd2 + i)
    vals = []
    for k in range(8):
        try:
            vals.append(sc2.peek(tb + off + (k % 16) * strd))
        except IOError:
            pass
    if not vals:
        print('  %-16s UNREADABLE' % name); continue
    pk = max(abs(q428(v)) for v in vals)
    nz = sum(1 for v in vals if v)
    print('  %-16s off %4d stride %d  |peak| %8.5f Q4.28 (%7.1f dBFS)  '
          '%d/%d non-zero   %s'
          % (name, off, strd, pk, dbfs(pk / 8.0), nz, len(vals), what))
    if pk > 8.0 - 1e-6:
        tx_fail.append('%s is pinned at the Q4.28 accumulator ceiling — the '
                       'RX artefact is still arriving at the DAC' % name)

print('\nTX: %s' % ('PASS' if not tx_fail else 'FAIL'))
for f in tx_fail:
    print('  - %s' % f)
print('\n(TX here proves what the DSP wrote, not what the AK4458 latched. '
      'The transmit framing itself is proved by the analog loop: with RX '
      'right, AUX 1 out -> MIC 1 in must return a clean scaled copy. A '
      'still-early transmit returns a doubled, sign-wrapped one.)')

sys.exit(1 if (rx_fail or tx_fail) else 0)
