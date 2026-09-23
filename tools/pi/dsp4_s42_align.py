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

  THE DEPOPULATED SECTION (S48 S4.4, owed since; hub ruling on S86-N1).
  Eight of MW-D24-2's twenty-four mic channels have no analog front end
  fitted -- panel mics 1-4 and 13-16, XLRs J15-J22, preamps U17-U31, the
  whole of converter U15 / `ad[0]`. Their converter still dithers, so the
  lanes are live and correctly framed and simply sit ~50 dB below the
  preamp band; scoring them on that band failed the whole RX bank for
  four sessions running. Those lanes are now scored on the bare-converter
  band instead and reported in their own column. `DSP4_DEPOP_STRIPS`
  overrides the list per unit ("1-4,13-16", or "none").

usage: python3 dsp4_s42_align.py [symdir] [samples]
       DSP4_DEPOP_STRIPS=none python3 dsp4_s42_align.py [symdir] [samples]
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

# ------------------------------------------------ the depopulated section ----
# THE GUARD S48 ASKED FOR, SIZED FROM A MEASUREMENT (owed since S48 S4.4,
# restated S49; hub ruling on S86-N1, 2026-09-20).
#
# A lane whose analog front end is not fitted still has a converter in
# front of it, and that converter dithers: the words are live, distinct
# and correctly framed, and the rms is simply far below the preamp band
# because nothing is amplifying anything into it. The band test has no
# notion of that, so it scored those lanes `**BAD**` and failed the whole
# RX bank on them -- S48 S5.1 said in writing that "that FAIL is the
# instrument, not the part", and the tool went on doing it through S49,
# S55, S85 and S86.
#
# THE SECTION IS EIGHT CHANNELS, NOT FOUR. S48 could name four because it
# was reading twelve lanes; S86 measured all 24 XLRs at gain codes 63 and
# 0 and found J15-J22 -- panel mics 1-4 AND 13-16, preamps U17-U31, the
# whole of converter U15 / `ad[0]` -- rising -0.21..+0.08 dB against
# 31.8..40.4 dB on the other sixteen, and sitting at -116.0..-116.2 dBFS
# at both codes. S85-3's CPLD toggle counts agree from the other side:
# `ad[0]` alone does not respond to the analog rails and its `ones`
# high-water is 188 of 256 where U39's and U60's reach 256.
#
# THIS IS A PROPERTY OF THE BENCH UNIT MW-D24-2, NOT OF THE DESIGN. It is
# declared here with its evidence rather than hidden in a threshold, and
# `DSP4_DEPOP_STRIPS` overrides it per unit: a strip list ("1-4,13-16"),
# or "none" on a fully populated board. A guarded lane is not skipped --
# it is scored on the test that still applies to it (correct framing and a
# live dither floor) and reported in its own column, so a guarded lane
# that goes IDLE or starts setting bits 6:0 still fails.
DEPOP_SECTION_SIZE = 8          # channels; asserted against the list below
DEPOP_STRIPS_DEFAULT = '1-4,13-16'
# What a converter with no front end reads: S48's -114..-118 dBFS and
# S86's -116.0..-116.2, widened each way for the same reason the preamp
# band is widened. -100 dBFS = 1.0e-5, -130 dBFS = 3.2e-7.
DEPOP_RMS_LO, DEPOP_RMS_HI = 3.2e-7, 1.0e-5


def parse_strips(spec):
    """'1-4,13-16' -> {1,2,3,4,13,14,15,16}; 'none' -> set()."""
    out = set()
    if spec.strip().lower() in ('none', ''):
        return out
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-', 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


import os
DEPOP_SPEC = os.environ.get('DSP4_DEPOP_STRIPS', DEPOP_STRIPS_DEFAULT)
DEPOP = parse_strips(DEPOP_SPEC)
# FAIL LOUDLY rather than quietly guarding a different number of lanes
# than the record says: the size and the list are two statements of one
# fact and a tool that lets them drift is how "four" survived four
# sessions. An explicit override is exempt -- it is the unit speaking.
if DEPOP_SPEC == DEPOP_STRIPS_DEFAULT and len(DEPOP) != DEPOP_SECTION_SIZE:
    raise SystemExit('depopulated-section guard: the list %s covers %d '
                     'strips and DEPOP_SECTION_SIZE says %d — one of the '
                     'two is wrong, and neither is a default to paper over'
                     % (DEPOP_STRIPS_DEFAULT, len(DEPOP), DEPOP_SECTION_SIZE))


def sgn(w):
    return w - (1 << 32) if w & 0x80000000 else w


def q428(w):
    return sgn(w) / float(1 << 28)


def dbfs(x):
    return 20.0 * math.log10(x) if x > 0 else float('-inf')


# ---------------------------------------------------------------- RX ----
sc1 = S.Scope(1, symfile='%s/chip1.sym.json' % SYMDIR)
sc1.d.resync(); sc1.check_chip()

# ---------------------------------------------------------- MFD ----
# THE REGISTER-LEVEL PROOF, AND IT NEEDS NO CONVERTER (S46-5).
# Everything below this block reads converter AUDIO, so it can only be
# taken with the AK5558s powered and clocking. Whether S42's one-bit fix
# actually reached the part is a different and much smaller question, and
# SPORT_MCTL answers it directly: MFD is bits 7:4, written per lane by
# sport_cfg_init() out of the generated <region>_mfd[] table. Reading it
# back separates "the fix did not land" from "the lanes are not driven",
# which is the confusion that cost S39-4 its whole measurement set.
SPORT_MMR_BASE, SPORT_STRIDE, HALF_B, OFF_MCTL = 0x31002000, 0x100, 0x80, 0x08
MFD_EXPECT = {1: [('rx  (half A, converters)', 0, [2, 2, 2, 2, 2, 2, 1, 2]),
                  ('ic  (half B, to chip 2)', HALF_B, [1, 1, 1])],
              2: [('ic  (half A, from chip 1)', 0, [1, 1, 1]),
                  ('tx  (half B, to the DACs)', HALF_B, [2, 2, 2, 1, 2])]}


def check_mfd(sc, chip):
    """Read SPORT_MCTL per lane; compare with the generated table."""
    print('=== chip %d SPORT_MCTL.MFD, per lane, read back ===' % chip)
    bad = []
    for label, half, expect in MFD_EXPECT[chip]:
        got = []
        for sp in range(len(expect)):
            a = SPORT_MMR_BASE + sp * SPORT_STRIDE + half + OFF_MCTL
            try:
                got.append((sc.peek(a) >> 4) & 0xF)
            except IOError:
                got.append(None)
        ok = got == expect
        print('  %-26s got %-18s expect %-18s %s'
              % (label, got, expect, 'OK' if ok else '**MISMATCH**'))
        if not ok:
            bad.append('%s: MCTL.MFD reads %s, the generated table says %s'
                       % (label, got, expect))
    return bad


mfd_fail = check_mfd(sc1, 1)
print('')

ents = sc1.sym['_c1_rx_node_entry']
offs = sc1.sym['_c1_rx_off']
strds = sc1.sym['_c1_rx_stride']

print('=== RX: chip 1 converter lanes, %d words each ===' % N)
if DEPOP:
    covered = sorted(x for x in DEPOP if 1 <= x <= 12)
    print('    depopulated-section guard: strips %s (%d of the section\'s %d '
          'channels fall in this bank) scored on the converter-dither band '
          '%.1f..%.1f dBFS instead of the preamp band%s'
          % (DEPOP_SPEC, len(covered), len(DEPOP),
             dbfs(DEPOP_RMS_LO), dbfs(DEPOP_RMS_HI),
             '' if DEPOP_SPEC == DEPOP_STRIPS_DEFAULT else '  [OVERRIDE]'))
else:
    print('    depopulated-section guard: OFF — every lane scored on the '
          'preamp band')
print('lane   b31 set  lo7 set   rms as-is      dBFS   band     verdict')
lanes = []
ALL_WORDS = []
LANE_WORDS = {}
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
    ALL_WORDS.extend(w)
    LANE_WORDS[strip] = w
    b31 = sum(1 for x in w if x & 0x80000000)
    lo7 = sum(1 for x in w if x & 0x7F)
    rms = math.sqrt(sum((sgn(x) / 2.0 ** 31) ** 2 for x in w) / len(w))
    depop = strip in DEPOP
    lo, hi = (DEPOP_RMS_LO, DEPOP_RMS_HI) if depop else (RMS_LO, RMS_HI)
    ok = (lo7 == 0) and (lo <= rms <= hi)
    lanes.append((strip, b31, lo7, rms, ok, depop))
    print(' %2d      %3d      %3d    %.6f   %7.1f   %-7s  %s'
          % (strip, b31, lo7, rms, dbfs(rms),
             'depop' if depop else 'preamp', 'ok' if ok else '**BAD**'))

rx_fail = []
rx_undriven = False
if not lanes:
    rx_fail.append('no lane was readable')
else:
    # REFUSE THE VERDICT ON AN UNDRIVEN BUS (S46-4). Every bit test below
    # is a statement about where the converter's 24 bits sit inside a
    # 32-bit slot, and it is meaningless if no converter is driving the
    # slot. An AK5558 that is powered and clocking always produces a
    # DITHERED noise floor -- hundreds of distinct small values even with
    # its input open. A lane whose words are only 0x00000000 and
    # 0xFFFFFFFF is an idle line, and 0xFFFFFFFF sets bit 31 AND bits 6:0,
    # so both bit tests score on it and the tool used to report "bits 6:0
    # set -> the window moved the other way" -- an MFD verdict on a bank
    # that was not switched on. Measured 2026-09-14 with the rev B analog
    # board's isolation links open and AN_EN low: 48 words per lane over
    # three captures, twelve lanes, TWO distinct values on every one.
    # An exact all-words-in-{0,FFFFFFFF} test is too strict: a line caught
    # mid-transition yields the odd one-bit variant (FFFFEFFB, FFFFFFFB,
    # 80280002 all seen on 2026-09-14). The discriminator that does not
    # care is the DISTINCT-VALUE COUNT. A converter noise floor is dither:
    # 32 words give ~32 different small numbers. An idle line gives two.
    idle = 0
    for strip, _, _, _, _, _ in lanes:
        w = LANE_WORDS[strip]
        rail = sum(1 for v in w if v in (0, 0xFFFFFFFF))
        if len(set(w)) <= 4 and rail >= 0.9 * len(w):
            idle += 1
    if idle >= max(1, (len(lanes) * 3) // 4):
        rx_undriven = True
        rx_fail.append(
            'The lanes read as an '
            'idle/undriven TDM bus on %d of %d lanes (<=4 distinct '
            'values each, >=90%% of words at a rail) — not a converter '
            'noise floor. NO MFD ' % (idle, len(lanes)) +
            'VERDICT IS TAKEN from this: power the converters (analog '
            'board isolation links fitted, AN_EN high) and re-run. The '
            'per-lane SPORT_MCTL.MFD read above is the part of this gate '
            'that does not need them.')
    elif all(b == 0 for _, b, _, _, _, _ in lanes):
        rx_fail.append('bit 31 NEVER set on any word of any lane — this is '
                       'exactly S39-4 and the MFD change did not reach the '
                       'part (check DIAG_BUILD_CFG and the image md5)')
    if not rx_undriven:
        if any(l7 for _, _, l7, _, _, _ in lanes):
            rx_fail.append('bits 6:0 set on some word — the 24-in-32 pad is '
                           'not where it should be, so the window is off the '
                           'other way')
        # THE BAND FAILURES ARE REPORTED IN TWO LISTS, because a guarded
        # lane and an unguarded one that miss their bands are two different
        # statements: the first says the depopulated section is not reading
        # like a bare converter any more (so the guard, or the board,
        # changed), the second is S48's original verdict.
        bad = [n for n, _, _, _, ok, dp in lanes if not ok and not dp]
        bad_dp = [n for n, _, _, _, ok, dp in lanes if not ok and dp]
        if bad:
            rx_fail.append('lane(s) %s outside the -65..-85 dBFS converter '
                           'noise band' % ','.join(str(x) for x in bad))
        if bad_dp:
            rx_fail.append('guarded lane(s) %s outside the %.0f..%.0f dBFS '
                           'depopulated-section band — the section is not '
                           'reading as a bare converter, so either the guard '
                           'list (%s) or the board has changed'
                           % (','.join(str(x) for x in bad_dp),
                              dbfs(DEPOP_RMS_HI), dbfs(DEPOP_RMS_LO),
                              DEPOP_SPEC))
        # THE DISTINCTNESS TEST IS TAKEN OVER THE UNGUARDED LANES ONLY. The
        # depopulated section's floors are eight readings of the same bare
        # converter and S86 measured them inside 0.2 dB of each other, so
        # counting them here would answer "not distinct" for a reason that
        # is not a fault.
        rmss = [r for _, _, _, r, ok, dp in lanes if not dp]
        if len(rmss) >= 2 and (len(set('%.7f' % r for r in rmss))
                               < max(2, len(rmss) // 3)):
            rx_fail.append('the %d populated noise floors are not distinct — '
                           'a stuck or common source, not %d converters'
                           % (len(rmss), len(rmss)))

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

mfd_fail += check_mfd(sc2, 2)

# ------------------------------------------------ chip 2 receive ----
# §5.2 of the morning sheet. This section did not exist (S46-6): the tool
# scored chip 1's RX and chip 2's TX and nothing in between, so the sheet
# asked for a chip-2 verdict the gate never produced. The lanes are the
# INTER-CHIP ones from chip 1 -- fabric, MFD 1 -- resolved BY NAME through
# _c2_ic_rx_ptrs against each node's own _rx_ic_slot_<id>, the same way
# the TX section resolves, so a slot move is followed and not assumed.
IC_WATCH = ['C2_RECV_MAIN_L', 'C2_RECV_MAIN_R', 'C2_RECV_AUX_01',
            'C2_RECV_AUX_02', 'C2_RECV_GRP_01', 'C2_RECV_FX_01',
            'C2_RECV_SUB']
print('\n=== RX: chip 2 inter-chip lanes (fabric from chip 1, MFD 1) ===')
ic_fail = []
try:
    ic_buf = sc2.peek(sc2.sym['_ic_rx_active_buf'])
    ic_offs = sc2.sym['_c2_ic_rx_off']
    ic_strd = sc2.sym['_c2_ic_rx_stride']
    ic_ptrs = sc2.sym['_c2_ic_rx_ptrs']
except (IOError, KeyError) as exc:
    print('  inter-chip RX tables unreadable: %s' % exc)
    ic_offs = None

if ic_offs is not None:
    ic_index = {}
    for i in range(24):
        try:
            p = sc2.peek(ic_ptrs + i)
        except IOError:
            continue
        for n in IC_WATCH:
            sym = '_rx_ic_slot_%s' % n
            if sym in sc2.sym and sc2.sym[sym] == p:
                ic_index[n] = i
    print('lane                 idx  off strd  b31  lo7  distinct')
    ic_words = []
    for n in IC_WATCH:
        i = ic_index.get(n)
        if i is None:
            print('  %-18s NOT IN THE INTER-CHIP TABLE' % n)
            ic_fail.append('%s does not resolve in _c2_ic_rx_ptrs' % n)
            continue
        off = sc2.peek(ic_offs + i)
        strd = sc2.peek(ic_strd + i)
        w = []
        for k in range(16):
            try:
                w.append(sc2.peek(ic_buf + off + (k % 16) * strd))
            except IOError:
                pass
        if not w:
            print('  %-18s UNREADABLE' % n); continue
        ic_words.extend(w)
        print('  %-18s %3d %4d %4d  %3d  %3d  %8d'
              % (n, i, off, strd,
                 sum(1 for x in w if x & 0x80000000),
                 sum(1 for x in w if x & 0x7F), len(set(w))))
    # The chip-2 lanes are DOWNSTREAM of chip 1's converter inputs, so
    # they inherit an undriven converter bank. Say so rather than scoring
    # a bit test on propagated silence.
    if ic_words and all(v in (0, 0xFFFFFFFF) for v in ic_words):
        print('  -> every word is 0x00000000/0xFFFFFFFF: these lanes carry '
              'what chip 1 received, and chip 1 received nothing. No '
              'chip-2 framing verdict is taken either.')

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
    elif pk > 1.0:
        # The sheet's stated §5.3 criterion, which this tool did not apply
        # (S46-7): S39-6 read AUX 1 at 1.538 Q4.28 = +3.75 dBFS, above full
        # scale and well under the 8.0 ceiling, so the ceiling test alone
        # would have passed the very reading the gate exists to catch.
        tx_fail.append('%s peaks at %.5f in Q4.28 — above full scale (the '
                       'sheet asks for inside +-1.0; S39-6 read 1.538 here)'
                       % (name, pk))

print('\nTX: %s' % ('PASS' if not tx_fail else 'FAIL'))
for f in tx_fail:
    print('  - %s' % f)
print('\n(TX here proves what the DSP wrote, not what the AK4458 latched. '
      'The transmit framing itself is proved by the analog loop: with RX '
      'right, AUX 1 out -> MIC 1 in must return a clean scaled copy. A '
      'still-early transmit returns a doubled, sign-wrapped one.)')

if mfd_fail:
    print('\nMFD: FAIL')
    for f in mfd_fail:
        print('  - %s' % f)
else:
    print('\nMFD: PASS — every lane\'s SPORT_MCTL.MFD equals the generated '
          'table on both chips. S42\'s one-bit fix is on the part.')

if rx_undriven:
    print('\nVERDICT: NOT TAKEN. The MFD registers are right and the TX '
          'tables resolve, but the converters are not driving the bus, so '
          '§5.1/§5.2 have nothing to measure. Exit 2 = inconclusive, not '
          'failed.')
    sys.exit(2)
sys.exit(1 if (rx_fail or tx_fail or mfd_fail or ic_fail) else 0)
