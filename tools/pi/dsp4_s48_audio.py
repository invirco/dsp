#!/usr/bin/env python3
"""dsp4_s48_audio.py — first audio through the D24 on rev C (S48 gate 3/4).

NEEDS A `DSP4_SCOPE_BLK_TAP=1` IMAGE. On the shipping pair the host-settable
injector cannot reach the node chain at all: under `DSP4_BLOCK_KERNELS` the
per-sample `_scope_inject` writes `_buf_<nid>`, which no block kernel reads,
while `_scope_inject_blk` — "the write the chain actually reads" — exists only
in a tap build. S48 measured that the hard way: a 0.25 Q4.28 step captured
back perfectly from `_buf_C1_IN_05` while the TX lanes never moved.

TWO THINGS THIS GETS RIGHT THAT THE FIRST ATTEMPT DID NOT:

1. **The injection point is the RX SLOT, not the node buffer.**
   `_scope_inject_blk` is handed `r0` = the slot symbol the host named and
   `r1` = where that node's block actually lives, and each per-strip call
   site returns immediately unless `r0 == _scope_inj`. So `_scope_inj` must
   be `_rx_slot_C1_IN_NN`. Naming `_buf_C1_IN_NN` arms a call site that
   never fires — silently.

2. **The stimulus is SUSTAINED by arming a `src` that matches no node.**
   `_scope_tap` advances `_scope_idx` only for the node whose identity
   equals `_scope_src`, and clears `_scope_arm` only when the buffer fills.
   Point `_scope_src` at `_scope_buf` itself — an address no node is — and
   the capture never completes, so `_scope_arm` stays 1 and the injector
   keeps driving. Arming a real node instead gives 1024 samples (21 ms at
   48 kHz) and then silence, which reads as "the path is dead".

`_scope_inj_blk` IS THE WITNESS. The chain writes that variable with the live
pool-slot address right before it injects, and 0 when there is no redirect.
Non-zero means this strip's call site fired. A measurement is refused if it
never does — a zero there means the level below belongs to nothing.

FULL SCALE, STATED FIRST (PW's standing convention). The TX lanes are Q4.28.
**0 dBFS is 1.0** — the value that maps to the DAC's full scale — and the
accumulator ceiling is 8.0, three bits of headroom above it. This tool
reports `dBFS` against 1.0 and prints the `/8` figure beside it in brackets,
because `dsp4_s42_align.py` and the S39/S42/S46 records quote the /8
convention and the two differ by exactly 18.06 dB. RX lanes are 24-in-32
left-justified, so their full scale is 2**31 and one convention only.

Restores `_scope_arm`/`_scope_inj`/`_scope_mode`/`_scope_amp` on every exit.

Usage: dsp4_s48_audio.py [strip] [amp_hex] [toggles] [symdir]
"""
import json, math, sys, time
_ARGV = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

STRIP   = int(_ARGV[0]) if len(_ARGV) > 0 else 5
AMP     = int(_ARGV[1], 16) if len(_ARGV) > 1 else 0x08000000   # 0.5 Q4.28
TOGGLES = int(_ARGV[2]) if len(_ARGV) > 2 else 8
SYMDIR  = _ARGV[3] if len(_ARGV) > 3 else '/home/app/s48tap'

WATCH = [('C2_AUX_OUT_01', 'aux 1  -> DAC_08 -> J45 -> rear XLR OUT_01'),
         ('C2_MAIN_OUT_01', 'main 1 -> DAC_12 -> J56 MAIN L')]
FS_Q428 = 1.0          # 0 dBFS at the DAC
CEIL_Q428 = 8.0        # the accumulator ceiling, the /8 convention


def s32(w):
    return w - (1 << 32) if w & 0x80000000 else w


def q428(w):
    return s32(w) / float(1 << 28)


def db(x, fs=1.0):
    return 20.0 * math.log10(x / fs) if x > 0 else float('-inf')


sc1 = S.Scope(1, symfile='%s/chip1.sym.json' % SYMDIR)
sc1.d.resync(); sc1.check_chip()
sc2 = S.Scope(2, symfile='%s/chip2.sym.json' % SYMDIR)
sc2.d.resync(); sc2.check_chip()

for need in ('_scope_inj_blk', '_scope_buf'):
    if need not in sc1.sym:
        raise SystemExit('%s is not in %s/chip1.sym.json — this is not a '
                         'DSP4_SCOPE_BLK_TAP image.' % (need, SYMDIR))
SLOT = '_rx_slot_C1_IN_%02d' % STRIP
if SLOT not in sc1.sym:
    raise SystemExit('%s not in the map' % SLOT)

ents, offs, strds = (sc1.sym['_c1_rx_node_entry'], sc1.sym['_c1_rx_off'],
                     sc1.sym['_c1_rx_stride'])
if sc1.peek(sc1.sym['_rx_active_buf']) == 0 and \
   sc1.peek(sc1.sym['_rx_active_buf']) == 0:
    raise SystemExit('_rx_active_buf peeks 0 twice — wrong map for the running '
                     'image, or RX is not running. Refusing to measure.')


def rx_rms(lane, n=64):
    e = sc1.peek(ents + lane - 1)
    off = sc1.peek(offs + e); strd = sc1.peek(strds + e)
    w = []
    for i in range(n):
        try:
            b = sc1.peek(sc1.sym['_rx_active_buf'])
            w.append(sc1.peek(b + off + (i % 16) * strd))
        except IOError:
            pass
    if not w:
        return None, None
    rms = math.sqrt(sum((s32(x) / 2.0 ** 31) ** 2 for x in w) / len(w))
    pk = max(abs(s32(x)) / 2.0 ** 31 for x in w)
    return rms, pk


offs2, strd2, ptrs2 = (sc2.sym['_c2_tx_off'], sc2.sym['_c2_tx_stride'],
                       sc2.sym['_c2_tx_ptrs'])
index_of = {}
for i in range(24):
    try:
        p = sc2.peek(ptrs2 + i)
    except IOError:
        continue
    for name, _ in WATCH:
        if sc2.sym.get('_tx_out_slot_%s' % name) == p:
            index_of[name] = i


def tx_peak(name, k=16):
    i = index_of.get(name)
    if i is None:
        return None
    b = sc2.peek(sc2.sym['_tx_active_buf'])
    off = sc2.peek(offs2 + i); strd = sc2.peek(strd2 + i)
    vals = []
    for j in range(k):
        try:
            vals.append(sc2.peek(b + off + (j % 16) * strd))
        except IOError:
            pass
    return max(abs(q428(v)) for v in vals) if vals else None


def line(tag):
    a = tx_peak('C2_AUX_OUT_01'); m = tx_peak('C2_MAIN_OUT_01')
    r, rpk = rx_rms(STRIP)
    def tx(v):
        if v is None:
            return '   UNREADABLE   '
        return '%8.5f %7.2f dBFS [%6.1f/8]' % (v, db(v, FS_Q428),
                                               db(v, CEIL_Q428))
    print('  %-14s AUX1 %s | MAIN %s | MIC%d RX rms %7.2f pk %7.2f dBFS'
          % (tag, tx(a), tx(m), STRIP,
             db(r) if r else float('-inf'), db(rpk) if rpk else float('-inf')))
    return a, r


def arm_sustained(amp):
    """Arm with a src that matches no node, so the run never completes."""
    sc1.arm(src=sc1.sym['_scope_buf'], inj=sc1.sym[SLOT], amp=amp & 0xFFFFFFFF,
            mode=2)


print('S48 gate 3 — strip %d driven through the BLOCK injector' % STRIP)
print('  image   : %s' % SYMDIR)
print('  inject  : %s @ 0x%X   (the RX SLOT, not _buf_)' % (SLOT, sc1.sym[SLOT]))
print('  amp     : 0x%08X = %.4f Q4.28 = %.2f dBFS at the DAC'
      % (AMP, AMP / float(1 << 28), db(AMP / float(1 << 28), FS_Q428)))
print('  full scale: 0 dBFS = 1.0 Q4.28 on TX; [x/8] is the align-tool '
      'convention, 18.06 dB below')
print('')
try:
    print('ARM 0 — injector OFF (the floor):')
    base_a, base_r = line('quiet')

    arm_sustained(AMP)
    time.sleep(0.5)
    blk = sc1.peek(sc1.sym['_scope_inj_blk'])
    print('')
    print('  _scope_inj_blk = 0x%X  (%s)'
          % (blk, 'redirect FIRED — strip %d call site is live' % STRIP if blk
             else 'ZERO — the call site never fired'))
    if not blk:
        raise SystemExit('Refusing to quote a level: the injection is not '
                         'reaching strip %d.' % STRIP)
    print('')
    print('ARM 1 — sustained DC step (+A). The DSP path is proved here; an '
          'AC-coupled output will not pass DC to the loop:')
    dc_a, dc_r = line('+A DC')

    print('')
    print('ARM 2 — amp toggled +A/-A, host-timed (a square of a few Hz). '
          'The loop returns the EDGES:')
    tog = []
    for t in range(TOGGLES):
        sc1.wr(S.SCOPE_AMP, (AMP if t % 2 == 0 else -AMP) & 0xFFFFFFFF)
        a, r = line('%s' % ('+A' if t % 2 == 0 else '-A'))
        if r:
            tog.append(r)
finally:
    try:
        sc1.d.write(S.SCOPE_ARM, 0)
        sc1.wr(S.SCOPE_MODE, 0); sc1.wr(S.SCOPE_INJ, 0); sc1.wr(S.SCOPE_AMP, 0)
        print('')
        print('injector cleared: ARM=%s INJ=%s MODE=%s AMP=%s'
              % (sc1.rd(S.SCOPE_ARM), sc1.rd(S.SCOPE_INJ),
                 sc1.rd(S.SCOPE_MODE), sc1.rd(S.SCOPE_AMP)))
    except Exception as exc:
        print('  WARNING: could not clear the injector: %s' % exc)

print('')
print('AFTER — injector off again:')
time.sleep(0.5)
line('quiet')
if base_r and tog:
    mean = sum(tog) / len(tog)
    print('')
    print('MIC %d RX: floor %.2f dBFS -> toggled %.2f dBFS   DELTA %+.2f dB'
          % (STRIP, db(base_r), db(mean), db(mean) - db(base_r)))
