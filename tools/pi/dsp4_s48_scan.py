#!/usr/bin/env python3
"""dsp4_s48_scan.py — which lane is MIC 5 actually on? (S48 gate 3)

PW has seen the 500 Hz square on J45 with a DMM, so the DAC and the output
stage are PROVEN and the signal does leave the unit. It does not appear on
the RX lane this session has been calling MIC 5. Two explanations remain and
they are told apart by looking at ALL the lanes instead of one:

  * the cable or the MIC 5 input is dead        -> NO lane moves;
  * the RX lane <-> physical channel map is wrong -> SOME OTHER lane moves.

The second is not speculation on this board: S42 found the DAC side's
OUT_1-8 block REVERSED (U81 ch n -> rear OUT_(9-n)) with the slot map never
compensating, and that alone explained a whole session's silence. The same
class of error on the ADC side would look exactly like this.

A -6 dBFS square into a mic preamp at gain 63 is a gross overload, so
whichever lane physically carries MIC 5 should CLIP -- near full scale, not a
few dB up. That is a signature no noise floor imitates.

THE NEGATIVE ARM IS THE POINT. Every lane is read with the stimulus OFF, then
ON, then OFF again. A lane is only reported as carrying the stimulus if it
rises on the ON pass AND falls back on the second OFF pass. Without that, one
noisy lane out of nineteen is certain to look like a hit.

Usage: dsp4_s48_scan.py [donor] [N] [amp_hex] [symdir]
"""
import math, sys, time
_A = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
import d24_inputs as D24

DONOR = int(_A[0]) if len(_A) > 0 else 6
N     = int(_A[1]) if len(_A) > 1 else 3
AMP   = int(_A[2], 16) if len(_A) > 2 else 0x01000000
SYM   = _A[3] if len(_A) > 3 else '/home/app/s48sq_81f4f954'
IC_WATCH = ['C2_RECV_MAIN_L', 'C2_RECV_MAIN_R', 'C2_RECV_AUX_01',
            'C2_RECV_AUX_02', 'C2_RECV_GRP_01', 'C2_RECV_FX_01', 'C2_RECV_SUB']


def s32(w):
    return w - (1 << 32) if w & 0x80000000 else w


def db(x):
    return 20 * math.log10(x) if x > 0 else float('-inf')


sc1 = S.Scope(1, symfile='%s/chip1.sym.json' % SYM); sc1.d.resync(); sc1.check_chip()
sc2 = S.Scope(2, symfile='%s/chip2.sym.json' % SYM); sc2.d.resync(); sc2.check_chip()
if '_scope_sq_phase' not in sc1.sym:
    raise SystemExit('not the S48 square image')

ents, offs, strds = (sc1.sym['_c1_rx_node_entry'], sc1.sym['_c1_rx_off'],
                     sc1.sym['_c1_rx_stride'])
ic_offs = sc2.sym['_c2_ic_rx_off']; ic_strd = sc2.sym['_c2_ic_rx_stride']
ic_ptrs = sc2.sym['_c2_ic_rx_ptrs']
ic_index = {}
for i in range(24):
    try:
        p = sc2.peek(ic_ptrs + i)
    except IOError:
        continue
    for n in IC_WATCH:
        if sc2.sym.get('_rx_ic_slot_%s' % n) == p:
            ic_index[n] = i


def c1_lane(lane, n=32):
    e = sc1.peek(ents + lane - 1)
    off = sc1.peek(offs + e); st = sc1.peek(strds + e)
    w = []
    for i in range(n):
        try:
            b = sc1.peek(sc1.sym['_rx_active_buf'])
            w.append(sc1.peek(b + off + (i % 16) * st))
        except IOError:
            pass
    if not w:
        return None, None
    r = math.sqrt(sum((s32(x) / 2.0 ** 31) ** 2 for x in w) / len(w))
    return r, max(abs(s32(x)) / 2.0 ** 31 for x in w)


def c2_lane(name, n=16):
    i = ic_index.get(name)
    if i is None:
        return None, None
    b = sc2.peek(sc2.sym['_ic_rx_active_buf'])
    off = sc2.peek(ic_offs + i); st = sc2.peek(ic_strd + i)
    w = []
    for k in range(n):
        try:
            w.append(sc2.peek(b + off + (k % 16) * st))
        except IOError:
            pass
    if not w:
        return None, None
    r = math.sqrt(sum((s32(x) / 2.0 ** 31) ** 2 for x in w) / len(w))
    return r, max(abs(s32(x)) / 2.0 ** 31 for x in w)


def sweep():
    out = {}
    for L in range(1, 25):     # all 24 analog strips (S51-4: lanes 13-24 are converter slots too)
        x = D24.xlr_on(L)
        out['C1 lane %2d %s' % (L, x.xlr if x else '')] = c1_lane(L)
    for n in IC_WATCH:
        out['C2 %s' % n] = c2_lane(n)
    return out


print('S48 lane scan — %.1f Hz square from donor strip %d, amp 0x%08X'
      % (48000.0 / (2 * N * 16), DONOR, AMP), flush=True)
print('pass 1: stimulus OFF (baseline)', flush=True)
off1 = sweep()
try:
    sc1.arm(src=sc1.sym['_scope_buf'],
            inj=sc1.sym['_rx_slot_C1_IN_%02d' % DONOR], amp=AMP, mode=0x10000 | N)
    blk = sc1.peek(sc1.sym['_scope_inj_blk'])
    print('pass 2: stimulus ON  (_scope_inj_blk = 0x%X, %s)'
          % (blk, 'FIRED' if blk else 'ZERO — NOTHING DRIVEN'), flush=True)
    if not blk:
        raise SystemExit('refusing to scan against a dead stimulus')
    time.sleep(1.0)
    on = sweep()
    on2 = sweep()
finally:
    try:
        sc1.d.write(S.SCOPE_ARM, 0)
        sc1.wr(S.SCOPE_MODE, 0); sc1.wr(S.SCOPE_INJ, 0); sc1.wr(S.SCOPE_AMP, 0)
    except Exception as exc:
        print('  WARNING: could not clear the injector: %s' % exc, flush=True)
time.sleep(1.0)
print('pass 3: stimulus OFF again (must fall back)', flush=True)
off2 = sweep()

print('', flush=True)
print('%-22s %10s %10s %10s %10s   %s'
      % ('lane', 'off1 rms', 'ON rms', 'off2 rms', 'ON peak', 'verdict'), flush=True)
hits = []
for k in off1:
    a = off1[k][0]; b = on[k][0]; b2 = on2[k][0]; c = off2[k][0]; pk = on[k][1]
    if a is None or b is None:
        print('%-22s   unreadable' % k, flush=True)
        continue
    rise = db(b) - db(a)
    fall = db(b) - db(c) if c else 0.0
    rise2 = db(b2) - db(a) if b2 else 0.0
    v = ''
    if rise > 6.0 and rise2 > 6.0 and fall > 6.0:
        v = '*** CARRIES THE STIMULUS  (+%.1f dB, falls back %.1f dB)' % (rise, fall)
        hits.append((k, rise, pk))
    elif rise > 6.0:
        v = 'rose %+.1f dB but did NOT fall back — not the stimulus' % rise
    print('%-22s %10.2f %10.2f %10.2f %10.2f   %s'
          % (k, db(a), db(b), db(c), db(pk) if pk else float('-inf'), v), flush=True)

print('', flush=True)
print('NOTE ON THE CHIP-2 LANES: they are the INTER-CHIP fabric carrying chip 1\'s', flush=True)
print('mix buses to chip 2, i.e. DOWNSTREAM of the injection and part of the DSP\'s', flush=True)
print('own path. C2_RECV_MAIN_L and C2_RECV_AUX_01 rising is EXPECTED and is a', flush=True)
print('positive control that the stimulus is real -- it is NOT the analog return.', flush=True)
print('Only chip-1 lanes 1-24 are analog inputs and only they can answer the loop.', flush=True)
print('', flush=True)
analog_hits = [h for h in hits if h[0].startswith('C1 ')]
fabric_hits = [h for h in hits if not h[0].startswith('C1 ')]
if fabric_hits and not analog_hits:
    for k, r, pk in fabric_hits:
        print('fabric (expected): %s rises %+.1f dB' % (k, r), flush=True)
hits = analog_hits
if hits:
    for k, r, pk in sorted(hits, key=lambda x: -x[1]):
        print('HIT: %s rises %+.1f dB, peak %.2f dBFS%s'
              % (k, r, db(pk), '  — CLIPPING' if pk and pk > 0.5 else ''), flush=True)
    print('The loop returns on the lane(s) above. MIC 5 (J25) is lane %d under the '
          'landed D24_INPUT_PATCH; if the hit is elsewhere, the RX lane <-> physical '
          'channel map is the fault, not the audio path.' % D24.MIC5_STRIP, flush=True)
else:
    print('NO ANALOG INPUT LANE carries the stimulus. With the square proven '
          'present at J45 AND at J25 pins 2-3 on a DMM, and the 595 image for '
          'ch5 verified 200/200 (unmuted, phantom off, gain 63), the break is '
          'INSIDE the mic channel between the XLR and the ADC input.', flush=True)
