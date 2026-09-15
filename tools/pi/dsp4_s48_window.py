#!/usr/bin/env python3
"""dsp4_s48_window.py — drive the square AND measure both sides, one run.

NEEDS the S48 square image (`_scope_sq_phase` in the map).

The drive holds the link's chip-select line, so a separate reader cannot run
beside it — measurement has to happen inside the driving process. That is the
whole reason this exists.

WHY A PEEK WINDOW IS LEGITIMATE HERE, when S48-14 said it was not: a peek
window re-reads the same 16-word block and so observes about 0.33 ms of audio
however long it runs. Against a ~1 Hz host-toggled edge that is hopeless. But
a 500 Hz square is CONTINUOUS and its period is 96 samples = 2 ms, so any
0.33 ms window lands inside it and sees full amplitude. The earlier objection
does not apply to a sustained tone.

Reports, per sample point:
  * `C2_AUX_OUT_01` |peak| — the drive itself, so a window can never be
    scored against a stimulus that was not running;
  * MIC 5 RX rms and peak — the loop return, which is the question;
  * a control lane the loop does not feed, so "everything moved" and "the
    loop moved" stay distinguishable.

Usage: dsp4_s48_window.py [secs] [donor] [cap] [ctrl] [N] [amp_hex] [symdir]
"""
import math, sys, time
_A = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SECS  = float(_A[0]) if len(_A) > 0 else 120.0
DONOR = int(_A[1]) if len(_A) > 1 else 6
CAP   = int(_A[2]) if len(_A) > 2 else 5
CTRL  = int(_A[3]) if len(_A) > 3 else 9
N     = int(_A[4]) if len(_A) > 4 else 3
AMP   = int(_A[5], 16) if len(_A) > 5 else 0x01000000
SYM   = _A[6] if len(_A) > 6 else '/home/app/s48sq_81f4f954'
BLOCK = 16


def s32(w):
    return w - (1 << 32) if w & 0x80000000 else w


def q28(w):
    return s32(w) / float(1 << 28)


def db(x, fs=1.0):
    return 20 * math.log10(x / fs) if x > 0 else float('-inf')


sc1 = S.Scope(1, symfile='%s/chip1.sym.json' % SYM); sc1.d.resync(); sc1.check_chip()
sc2 = S.Scope(2, symfile='%s/chip2.sym.json' % SYM); sc2.d.resync(); sc2.check_chip()
if '_scope_sq_phase' not in sc1.sym:
    raise SystemExit('not the S48 square image')

ents, offs, strds = (sc1.sym['_c1_rx_node_entry'], sc1.sym['_c1_rx_off'],
                     sc1.sym['_c1_rx_stride'])
o2, s2, p2 = sc2.sym['_c2_tx_off'], sc2.sym['_c2_tx_stride'], sc2.sym['_c2_tx_ptrs']
IDX = None
for i in range(24):
    try:
        q = sc2.peek(p2 + i)
    except IOError:
        continue
    if sc2.sym.get('_tx_out_slot_C2_AUX_OUT_01') == q:
        IDX = i


def rx(lane, n=32):
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


def aux():
    if IDX is None:
        return None
    b = sc2.peek(sc2.sym['_tx_active_buf'])
    off = sc2.peek(o2 + IDX); st = sc2.peek(s2 + IDX)
    v = []
    for j in range(16):
        try:
            v.append(sc2.peek(b + off + (j % 16) * st))
        except IOError:
            pass
    return max(abs(q28(x)) for x in v) if v else None


print('S48 window: %.0f s, %.1f Hz square, amp 0x%08X'
      % (SECS, 48000.0 / (2 * N * BLOCK), AMP), flush=True)
print('  donor strip %d -> AUX 1 -> OUT_01 -> cable -> MIC %d ; control lane %d'
      % (DONOR, CAP, CTRL), flush=True)
r0, _ = rx(CAP)
c0, _ = rx(CTRL)
a0 = aux()
print('  BEFORE (injector off): AUX1 %s | MIC%d %.2f | ctrl%d %.2f dBFS'
      % ('%.5f (%.2f dBFS)' % (a0, db(a0)) if a0 else 'n/a', CAP,
         db(r0) if r0 else float('-inf'), CTRL, db(c0) if c0 else float('-inf')),
      flush=True)
try:
    sc1.arm(src=sc1.sym['_scope_buf'], inj=sc1.sym['_rx_slot_C1_IN_%02d' % DONOR],
            amp=AMP, mode=0x10000 | N)
    blk = sc1.peek(sc1.sym['_scope_inj_blk'])
    print('  _scope_inj_blk = 0x%X  (%s)'
          % (blk, 'FIRED' if blk else 'ZERO — NOTHING IS BEING DRIVEN'), flush=True)
    if not blk:
        raise SystemExit('refusing to report levels against a dead stimulus')
    t0 = time.time()
    peaks = []
    while time.time() - t0 < SECS:
        a = aux(); r, rp = rx(CAP); c, _ = rx(CTRL)
        if r:
            peaks.append(r)
        print('  t=%5.1f s  AUX1 %8.5f (%6.2f dBFS) | MIC%d rms %7.2f pk %7.2f | ctrl%d %7.2f dBFS'
              % (time.time() - t0, a if a else 0, db(a) if a else float('-inf'),
                 CAP, db(r) if r else float('-inf'), db(rp) if rp else float('-inf'),
                 CTRL, db(c) if c else float('-inf')), flush=True)
        time.sleep(4.0)
finally:
    try:
        sc1.d.write(S.SCOPE_ARM, 0)
        sc1.wr(S.SCOPE_MODE, 0); sc1.wr(S.SCOPE_INJ, 0); sc1.wr(S.SCOPE_AMP, 0)
        print('  injector cleared: ARM=%s INJ=%s MODE=%s AMP=%s'
              % (sc1.rd(S.SCOPE_ARM), sc1.rd(S.SCOPE_INJ),
                 sc1.rd(S.SCOPE_MODE), sc1.rd(S.SCOPE_AMP)), flush=True)
    except Exception as exc:
        print('  WARNING: could not clear the injector: %s' % exc, flush=True)
time.sleep(0.5)
r1, _ = rx(CAP)
print('  AFTER (injector off): MIC%d %.2f dBFS' % (CAP, db(r1) if r1 else float('-inf')),
      flush=True)
if r0 and peaks:
    m = sum(peaks) / len(peaks)
    print('  MIC%d: floor %.2f -> driven %.2f dBFS   DELTA %+.2f dB'
          % (CAP, db(r0), db(m), db(m) - db(r0)), flush=True)
