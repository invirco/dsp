#!/usr/bin/env python3
"""dsp4_s48_stim.py — drive strip N's input from scope.asm and see what comes
back (S48 gate 3).

The unit has no oscillator (S39-9): `C1_NOISE` has no oscillator and no
consumer, and `scope.asm` offers impulse (mode 1) and step (mode 2) only. In
step mode the injector rewrites the named input slot EVERY sample, immediately
after `_scatter_chip1` and before the node chain, so a step at `_buf_C1_IN_NN`
is the largest stimulus this image can put on the strip without a rebuild.

WHAT EACH ARM PROVES, and they are different questions:

  * `_buf_C1_IN_05` -> `C2_AUX_OUT_01` is the WHOLE DSP path — strip 5's
    gain/fader/pan/aux-send on chip 1, the inter-chip fabric, chip 2's aux
    chain and the gather that writes the DAC window. It is measured on the
    TX lane, which is what the DSP handed the AK4458.
  * the MIC 5 RX lane is the ANALOG return, and only PW's loop cable closes
    it. A step is DC and an AC-coupled output stage will not pass it, so the
    RX arm here is read for its TRANSITIONS: the amplitude is toggled +A/-A
    and the lane is sampled across the toggles.

Amplitude is Q4.28: 0x10000000 = 1.0 = full scale. Default 0.25 FS, which is
-12 dBFS and well clear of both the noise floor and the accumulator ceiling.

Restores `_scope_inj`/`_scope_mode`/`_scope_amp` to 0 on the way out, always.

Usage: dsp4_s48_stim.py [strip] [amp_q428_hex] [toggles] [symdir]
"""
import json, math, sys, time
_ARGV = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

STRIP   = int(_ARGV[0]) if len(_ARGV) > 0 else 5
AMP     = int(_ARGV[1], 16) if len(_ARGV) > 1 else 0x04000000   # 0.25 Q4.28
TOGGLES = int(_ARGV[2]) if len(_ARGV) > 2 else 6
SYMDIR  = _ARGV[3] if len(_ARGV) > 3 else '/home/app/s42'

WATCH = [('C2_AUX_OUT_01', 'aux 1  -> DAC_08 -> rear XLR OUT_01'),
         ('C2_MAIN_OUT_01', 'main 1 -> DAC_12 -> J56 MAIN L')]


def q428(w):
    v = w - (1 << 32) if w & 0x80000000 else w
    return v / float(1 << 28)


def sgn(w):
    return w - (1 << 32) if w & 0x80000000 else w


def dbfs(x):
    return 20.0 * math.log10(x) if x > 0 else float('-inf')


sc1 = S.Scope(1, symfile='%s/chip1.sym.json' % SYMDIR)
sc1.d.resync(); sc1.check_chip()
sc2 = S.Scope(2, symfile='%s/chip2.sym.json' % SYMDIR)
sc2.d.resync(); sc2.check_chip()

INJ = sc1.sym['_buf_C1_IN_%02d' % STRIP]
ents, offs, strds = (sc1.sym['_c1_rx_node_entry'], sc1.sym['_c1_rx_off'],
                     sc1.sym['_c1_rx_stride'])


def rx_rms(lane, n=48):
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
        return None
    return math.sqrt(sum((sgn(x) / 2.0 ** 31) ** 2 for x in w) / len(w))


tb = sc2.peek(sc2.sym['_tx_active_buf'])
offs2, strd2, ptrs2 = (sc2.sym['_c2_tx_off'], sc2.sym['_c2_tx_stride'],
                       sc2.sym['_c2_tx_ptrs'])
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


def tx_peak(name, k=8):
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


def report(tag):
    out = []
    for name, what in WATCH:
        pk = tx_peak(name)
        out.append('%s %s' % (name, 'UNREADABLE' if pk is None
                              else '%.5f Q4.28 (%6.1f dBFS)' % (pk, dbfs(pk / 8.0))))
    r = rx_rms(STRIP)
    print('  %-22s  %s  | MIC %d RX %7.2f dBFS'
          % (tag, '   '.join(out), STRIP, dbfs(r) if r else float('-inf')))
    return r


print('strip %d input <- scope step, amp 0x%08X = %.4f Q4.28 (%.1f dBFS of FS)'
      % (STRIP, AMP, AMP / float(1 << 28), dbfs(AMP / float(1 << 28) / 8.0)))
print('inject slot _buf_C1_IN_%02d @ 0x%X' % (STRIP, INJ))
print('')
try:
    print('BEFORE (no injection):')
    base = report('quiet')

    sc1.arm(src=sc1.sym['_buf_C1_IN_%02d' % STRIP], inj=INJ, amp=AMP, mode=2)
    time.sleep(1.0)
    print('')
    print('STEP DRIVEN (+A), and toggled +A/-A:')
    live = []
    for t in range(TOGGLES):
        a = AMP if t % 2 == 0 else (-AMP) & 0xFFFFFFFF
        sc1.wr(S.SCOPE_AMP, a)
        time.sleep(0.4)
        live.append(report('%+d amp' % (1 if t % 2 == 0 else -1)))
finally:
    try:
        sc1.wr(S.SCOPE_MODE, 0); sc1.wr(S.SCOPE_INJ, 0); sc1.wr(S.SCOPE_AMP, 0)
        sc1.d.write(S.SCOPE_ARM, 0)
    except Exception as exc:
        print('  WARNING: could not clear the injector: %s' % exc)
    print('')
    print('injector cleared (_scope_inj/_scope_mode/_scope_amp = 0)')

print('')
print('AFTER (injector off):')
time.sleep(1.0)
after = report('quiet')
if base and after and live:
    lv = [x for x in live if x]
    if lv:
        print('')
        print('MIC %d RX: quiet %.2f dBFS -> driven %.2f dBFS  DELTA %+.2f dB'
              % (STRIP, dbfs(base), dbfs(sum(lv) / len(lv)),
                 dbfs(sum(lv) / len(lv)) - dbfs(base)))
