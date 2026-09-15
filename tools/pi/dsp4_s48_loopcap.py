#!/usr/bin/env python3
"""dsp4_s48_loopcap.py — the analog loop's STEP RESPONSE, captured (S48 gate 3).

NEEDS A `DSP4_SCOPE_BLK_TAP=1` IMAGE.

WHY A CAPTURE AND NOT A LEVEL. The earlier arms of this session toggled the
injector and re-read MIC 5's RX lane through paced `peek`s. That cannot work
and the reason is worth writing down: a peek window re-reads the SAME 16-word
block over and over, so it sees about 0.33 ms of audio however long it runs.
A host-timed toggle is ~1 Hz. The chance of a peek window landing on the edge
is well under one in a thousand — so an AC-coupled path, which passes ONLY
the edges, reads as silence no matter how alive it is.

The capture has no such problem: `_scope_tap` copies whole blocks into
`_scope_buf`, and `_scope_go` holds recording off until the stimulus has
actually been driven, so **sample 0 of the capture IS the step edge**. 1024
contiguous samples at 48 kHz is 21.3 ms, which is far longer than any
round trip through a DAC, two feet of cable and an ADC.

THE DRIVE AND THE CAPTURE MUST BE DIFFERENT STRIPS, and this is the whole
trick. The loop returns into MIC 5, i.e. strip 5's input. Injecting into
strip 5 would overwrite that same RX slot with the stimulus and the capture
would show the stimulus, not the return. So the stimulus goes into a DONOR
strip that is routed to AUX 1, and strip 5's input is captured untouched:

    donor strip -> AUX 1 -> DAC_08 -> J45 -> XLR OUT_01 -> cable
        -> MIC 5 XLR -> preamp -> AK5558 -> strip 5's RX slot -> captured

The donor's own analog input is irrelevant — it is bypassed by the injector.

WHAT COMES OUT. The sample index of the first excursion is the electrical
round-trip LATENCY in samples. Its size against the injected amplitude is the
loop transfer. A capture that stays at the floor for all 1024 samples means
the loop is open, the preamp is muted, or the gain is too low — and those are
distinguishable by raising the mic gain, which is the caller's business.

Usage: dsp4_s48_loopcap.py [cap-strip] [donor-strip] [amp_hex] [mode] [symdir]
       mode 2 = step (default, the edge is the stimulus), 1 = impulse
"""
import math, sys, time
_ARGV = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

CAP   = int(_ARGV[0]) if len(_ARGV) > 0 else 5
DONOR = int(_ARGV[1]) if len(_ARGV) > 1 else 6
AMP   = int(_ARGV[2], 16) if len(_ARGV) > 2 else 0x02000000
MODE  = int(_ARGV[3]) if len(_ARGV) > 3 else 2
SYM   = _ARGV[4] if len(_ARGV) > 4 else '/home/app/s48tap_289421ed'
FS = 2.0 ** 31          # RX slots are 24-in-32 left justified


def s32(w):
    return w - (1 << 32) if w & 0x80000000 else w


def db(x, fs=1.0):
    return 20.0 * math.log10(x / fs) if x > 0 else float('-inf')


sc = S.Scope(1, symfile='%s/chip1.sym.json' % SYM)
sc.d.resync(); sc.check_chip()
if '_scope_inj_blk' not in sc.sym:
    raise SystemExit('not a DSP4_SCOPE_BLK_TAP image')

SRC = '_buf_C1_IN_%02d' % CAP
INJ = '_rx_slot_C1_IN_%02d' % DONOR
for n in (SRC, INJ):
    if n not in sc.sym:
        raise SystemExit('%s not in the map' % n)

print('S48 gate 3 — the loop, captured')
print('  drive  : strip %d  (%s)' % (DONOR, INJ))
print('  capture: strip %d  (%s)  <- MIC %d, where the loop returns'
      % (CAP, SRC, CAP))
print('  amp    : 0x%08X, mode %d (%s)'
      % (AMP, MODE, 'step' if MODE == 2 else 'impulse'))
print('')

try:
    sc.arm(src=sc.sym[SRC], inj=sc.sym[INJ], amp=AMP, mode=MODE)
    blk = sc.peek(sc.sym['_scope_inj_blk'])
    print('  _scope_inj_blk = 0x%X  (%s)'
          % (blk, 'donor call site FIRED' if blk else 'ZERO — donor never fired'))
    n = sc.wait()
    idx = sc.rd(S.SCOPE_IDX)
    print('  capture complete, _scope_idx = %s' % idx)
    vals = sc.fetch(S.SCOPE_MAX)
finally:
    try:
        sc.d.write(S.SCOPE_ARM, 0)
        sc.wr(S.SCOPE_MODE, 0); sc.wr(S.SCOPE_INJ, 0); sc.wr(S.SCOPE_AMP, 0)
        print('  injector cleared: ARM=%s INJ=%s MODE=%s AMP=%s'
              % (sc.rd(S.SCOPE_ARM), sc.rd(S.SCOPE_INJ),
                 sc.rd(S.SCOPE_MODE), sc.rd(S.SCOPE_AMP)))
    except Exception as exc:
        print('  WARNING: could not clear the injector: %s' % exc)

sig = [s32(v) / FS for v in vals]
if not sig:
    raise SystemExit('no samples')
floor = sorted(abs(x) for x in sig)[:len(sig) // 4]
fl = math.sqrt(sum(x * x for x in floor) / len(floor)) if floor else 0.0
pk = max(abs(x) for x in sig)
ipk = max(range(len(sig)), key=lambda i: abs(sig[i]))
rms = math.sqrt(sum(x * x for x in sig) / len(sig))

print('')
print('  samples %d   quietest-quartile rms %.2f dBFS' % (len(sig), db(fl)))
print('  whole-capture rms %.2f dBFS   peak %.2f dBFS at sample %d (%.2f ms)'
      % (db(rms), db(pk), ipk, ipk / 48.0))

THRESH = fl * 8.0 if fl > 0 else 1e-7
first = next((i for i, x in enumerate(sig) if abs(x) > THRESH), None)
print('')
if first is None:
    print('  NO EXCURSION above 8x the floor anywhere in %.1f ms.' % (len(sig) / 48.0))
    print('  The loop did not return this stimulus: open cable, muted preamp,')
    print('  or the mic gain is too low for a line-level drive. Raise the gain')
    print('  (app cli chain-set 27 ch%d:mute=0,gain=N) and re-run.' % CAP)
else:
    print('  FIRST EXCURSION at sample %d = %.3f ms after the edge, %.2f dBFS'
          % (first, first / 48.0, db(abs(sig[first]))))
    print('  peak of the response %.2f dBFS' % db(pk))
    print('')
    print('  *** THE LOOP IS CLOSED: the step driven into strip %d left through'
          % DONOR)
    print('      AUX 1 / OUT_01 and came back into MIC %d. ***' % CAP)

print('')
print('  first 24 samples (dBFS, - = negative):')
for a in range(0, 24, 8):
    print('   ', '  '.join('%s%6.1f' % ('-' if sig[i] < 0 else '+',
                                        db(abs(sig[i]))) for i in range(a, a + 8)))
