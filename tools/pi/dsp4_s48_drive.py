#!/usr/bin/env python3
"""dsp4_s48_drive.py — park a sustained tone-free stimulus on AUX 1 / OUT_01
so a scope on the rear XLR can say whether the DAC side is alive (S48).

NEEDS A `DSP4_SCOPE_BLK_TAP=1` IMAGE.

S48 proved the DSP path to the transmit lane (`C2_AUX_OUT_01` goes from
-88 dBFS to -6.02 dBFS on demand, mute and polarity both behave) and proved
MIC 5's ADC side alive (its noise floor tracks the preamp gain code). It could
NOT prove the analog loop: at gain 16, 32 and 63 the captured MIC 5 block is
identical to within 0.2 dB whether the stimulus is driven or not. So the break
is at or after the DAC, and the instrument for that is PW's scope on OUT_01 —
not another number off the DSP.

This holds the drive up for as long as you let it run:

  * `--dc`     a steady +A. Shows a DC offset at the DAC pin; an AC-coupled
               output stage will show only the edge when it starts.
  * default    +A/-A toggled as fast as the parameter link allows, which is a
               square of roughly 1 Hz. Host-timed and jittery — it is NOT a
               test tone, it is something a scope can trigger on.

The stimulus is SUSTAINED by arming a `src` that matches no node, so the
capture never completes and `_scope_arm` is never cleared (see
dsp4_s48_audio.py). Ctrl-C clears the injector; so does the exception path.

Usage: dsp4_s48_drive.py [donor-strip] [amp_hex] [seconds] [symdir] [--dc]
  Default amp 0x01000000 is the LINEAR operating point: it puts exactly
  0.50000 Q4.28 (-6.02 dBFS) on the aux lane. Above that the path saturates
  (0x02000000 -> 0.846, 0x04000000 -> 1.006), so do not read a bigger number
  as more drive.
"""
import math, sys, time
_ARGV = [a for a in sys.argv[1:] if not a.startswith('--')]
_FLAGS = [a for a in sys.argv[1:] if a.startswith('--')]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

DONOR = int(_ARGV[0]) if len(_ARGV) > 0 else 6
AMP   = int(_ARGV[1], 16) if len(_ARGV) > 1 else 0x01000000
SECS  = float(_ARGV[2]) if len(_ARGV) > 2 else 120.0
SYM   = _ARGV[3] if len(_ARGV) > 3 else '/home/app/s48tap_289421ed'
DC    = '--dc' in _FLAGS

sc = S.Scope(1, symfile='%s/chip1.sym.json' % SYM)
sc.d.resync(); sc.check_chip()
if '_scope_inj_blk' not in sc.sym:
    raise SystemExit('not a DSP4_SCOPE_BLK_TAP image — nothing to drive with')
INJ = '_rx_slot_C1_IN_%02d' % DONOR
if INJ not in sc.sym:
    raise SystemExit('%s not in the map' % INJ)

print('driving strip %d -> AUX 1 -> DAC_08 -> J45 -> rear XLR OUT_01' % DONOR)
print('amp 0x%08X, %s, for %.0f s   (Ctrl-C to stop early)'
      % (AMP, 'steady DC' if DC else 'toggled +A/-A (~1 Hz square)', SECS))
try:
    sc.arm(src=sc.sym['_scope_buf'], inj=sc.sym[INJ], amp=AMP, mode=2)
    blk = sc.peek(sc.sym['_scope_inj_blk'])
    print('_scope_inj_blk = 0x%X  (%s)'
          % (blk, 'FIRED' if blk else 'ZERO — nothing is being driven'))
    if not blk:
        raise SystemExit('the donor call site never fired; refusing to pretend')
    t0 = time.time(); n = 0
    while time.time() - t0 < SECS:
        if DC:
            time.sleep(1.0)
        else:
            sc.wr(S.SCOPE_AMP, (AMP if n % 2 == 0 else -AMP) & 0xFFFFFFFF)
            n += 1
        if n % 10 == 0 or DC:
            print('  ... %5.0f s elapsed' % (time.time() - t0))
except KeyboardInterrupt:
    print('\n  interrupted')
finally:
    try:
        sc.d.write(S.SCOPE_ARM, 0)
        sc.wr(S.SCOPE_MODE, 0); sc.wr(S.SCOPE_INJ, 0); sc.wr(S.SCOPE_AMP, 0)
        print('injector cleared: ARM=%s INJ=%s MODE=%s AMP=%s'
              % (sc.rd(S.SCOPE_ARM), sc.rd(S.SCOPE_INJ),
                 sc.rd(S.SCOPE_MODE), sc.rd(S.SCOPE_AMP)))
    except Exception as exc:
        print('  WARNING: could not clear the injector: %s' % exc)
