#!/usr/bin/env python3
"""dsp4_s48_loop.py — is the analog loop CLOSED? (S48 gate 3)

PW's loop: rear XLR OUT_01 (AUX 1, analog J45, DAC_08) patched into MIC 5's
rear XLR (J25). The unit has no oscillator — `C1_NOISE` has no oscillator and
no consumer, and `scope.asm` does impulse and step only (S39-9) — so the
stimulus is the signal the routed strip already puts on the bus, and the
question is asked with a CONTROL rather than with a tone:

    toggle `Aux001Mute001` and watch MIC 5's RX lane.

S40 gate 3's bar: AUX 1 open vs muted must move the looped RX lane BY THE
LOOP TRANSFER, not by < 1 dB. That is a stronger test than a tone because it
has a negative arm, and this tool adds two more guards:

  * a CONTROL LANE that is not in the loop (default lane 9) must NOT move —
    that is what separates "the loop carries it" from "everything moved,
    so something else did it";
  * the arms ALTERNATE open/muted/open/muted/open, so a one-way drift
    (a rail settling, a pre warming) cannot be read as a transfer.

Read-only with respect to everything except `Aux001Mute001`, which it
restores to its entry value on the way out, including on an exception.

THE SYMBOL MAP MUST BE THE RUNNING IMAGE'S. `/home/app/dspboot/chip1.sym.json`
is a DIFFERENT build's map on this bench (S46 §3), and peeking through it does
not raise — it returns plausible zeros, which reads as "the lane is silent"
rather than as "the address was wrong". The directory is an argument, the way
`dsp4_s42_align.py` takes it, and it defaults to the staged pair.

Usage: dsp4_s48_loop.py [strip] [control-lane] [arms] [words-per-arm] [symdir]
"""
import json, math, sys, time
_ARGV = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

STRIP = int(_ARGV[0]) if len(_ARGV) > 0 else 5
CTRL  = int(_ARGV[1]) if len(_ARGV) > 1 else 9
ARMS  = int(_ARGV[2]) if len(_ARGV) > 2 else 5
N     = int(_ARGV[3]) if len(_ARGV) > 3 else 96
SYMDIR = _ARGV[4] if len(_ARGV) > 4 else '/home/app/s42'
SETTLE = 1.0

L = json.load(open('/home/app/dspboot/landed-d24.json'))['cells']


def sgn(w):
    return w - (1 << 32) if w & 0x80000000 else w


def dbfs(x):
    return 20.0 * math.log10(x) if x > 0 else float('-inf')


sc1 = S.Scope(1, symfile='%s/chip1.sym.json' % SYMDIR)
sc1.d.resync(); sc1.check_chip()
sc2 = S.Scope(2, symfile='%s/chip2.sym.json' % SYMDIR)
sc2.d.resync(); sc2.check_chip()

if sc1.peek(sc1.sym['_rx_active_buf']) == 0 and sc1.peek(sc1.sym['_rx_active_buf']) == 0:
    raise SystemExit('_rx_active_buf peeks 0 twice — the symbol map in %s is '
                     'not this image\'s, or RX is not running. Refusing to '
                     'measure: a wrong map reads as silence.' % SYMDIR)

ents, offs, strds = (sc1.sym['_c1_rx_node_entry'], sc1.sym['_c1_rx_off'],
                     sc1.sym['_c1_rx_stride'])


def lane_rms(lane):
    """As-received rms of one chip-1 converter RX lane, the align tool's way."""
    e = sc1.peek(ents + lane - 1)
    off = sc1.peek(offs + e)
    strd = sc1.peek(strds + e)
    w = []
    for i in range(N):
        try:
            b = sc1.peek(sc1.sym['_rx_active_buf'])
            w.append(sc1.peek(b + off + (i % 16) * strd))
        except IOError:
            pass
    if not w:
        return None, None
    rms = math.sqrt(sum((sgn(x) / 2.0 ** 31) ** 2 for x in w) / len(w))
    return rms, sum(1 for x in w if x & 0x7F)


def aux_mute(v):
    e = L.get('Aux001Mute001')
    if e is None or e[0] != 2:
        raise SystemExit('Aux001Mute001 is not a chip-2 cell in the contract')
    sc2.wr(e[2], v)
    got = sc2.rd(e[2])
    if got != v:
        raise SystemExit('Aux001Mute001 write did not land: wrote %s read %s'
                         % (v, got))


entry = sc2.rd(L['Aux001Mute001'][2])
print('MIC %d RX lane vs AUX 1 mute — control lane %d, %d words per arm'
      % (STRIP, CTRL, N))
print('Aux001Mute001 as found: %s' % entry)
print('')
print(' arm   AUX 1     MIC %-2d rms      dBFS   | control lane %-2d    dBFS   | lo7'
      % (STRIP, CTRL))
rows = []
try:
    for a in range(ARMS):
        muted = a % 2 == 1
        aux_mute(1 if muted else 0)
        time.sleep(SETTLE)
        r, lo7 = lane_rms(STRIP)
        c, _ = lane_rms(CTRL)
        rows.append((muted, r, c))
        print(' %2d    %-7s   %.7f  %7.2f   | %.7f    %7.2f   | %s'
              % (a, 'MUTED' if muted else 'open', r, dbfs(r), c, dbfs(c), lo7))
finally:
    aux_mute(entry)
    print('')
    print('Aux001Mute001 restored to %s' % sc2.rd(L['Aux001Mute001'][2]))

op = [r for m, r, _ in rows if not m]
mu = [r for m, r, _ in rows if m]
opc = [c for m, _, c in rows if not m]
muc = [c for m, _, c in rows if m]
if op and mu:
    d_loop = dbfs(sum(op) / len(op)) - dbfs(sum(mu) / len(mu))
    d_ctrl = dbfs(sum(opc) / len(opc)) - dbfs(sum(muc) / len(muc))
    print('')
    print('MIC %d      open %.2f dBFS   muted %.2f dBFS   DELTA %+.2f dB'
          % (STRIP, dbfs(sum(op) / len(op)), dbfs(sum(mu) / len(mu)), d_loop))
    print('control %-2d open %.2f dBFS   muted %.2f dBFS   DELTA %+.2f dB'
          % (CTRL, dbfs(sum(opc) / len(opc)), dbfs(sum(muc) / len(muc)), d_ctrl))
    print('')
    if d_loop >= 1.0 and abs(d_ctrl) < 1.0:
        print('LOOP CLOSED: opening AUX 1 raises MIC %d by %.2f dB while the '
              'control lane moves %+.2f dB.' % (STRIP, d_loop, d_ctrl))
        print('Audio is passing DSP -> DAC_08 -> J45 -> XLR OUT_01 -> cable '
              '-> MIC %d -> ADC -> RX lane.' % STRIP)
    elif d_loop < 1.0:
        print('NOT PROVED: MIC %d moved %+.2f dB, under the 1 dB bar. Either '
              'the loop is open or the stimulus is below the noise.'
              % (STRIP, d_loop))
    else:
        print('INCONCLUSIVE: the control lane moved %+.2f dB too, so this is '
              'not the loop — something common moved both.' % d_ctrl)
