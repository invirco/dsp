#!/usr/bin/env python3
"""s39_authority.py — does each control actually MOVE the audio it names?

A read-back proves a word landed in the kernel's DM. It does NOT prove
the kernel's audio path reads that word. This drives each control to
three values and measures the level at the point downstream of it, so
every claim is a response curve rather than a read-back.

Level is RMS over N samples of ONE fixed pool offset. A peek is serviced
once per block, so N samples span N blocks: that is a sample of the
signal's amplitude distribution, which is what a 20*log10 ratio between
two settings needs. No waveform and no frequency is claimed from it.
"""
import sys, time, json, struct, math
_argv = list(sys.argv); sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR = _argv[1] if len(_argv) > 1 else '/home/app/s39'
N = int(_argv[2]) if len(_argv) > 2 else 40
L = json.load(open('/home/app/dspboot/landed-d24.json'))['cells']
f32 = lambda x: struct.unpack('<I', struct.pack('<f', float(x)))[0]

sc1 = S.Scope(1, symfile='%s/chip1.sym.json' % SYMDIR); sc1.d.resync(); sc1.check_chip()
sc2 = S.Scope(2, symfile='%s/chip2.sym.json' % SYMDIR); sc2.d.resync(); sc2.check_chip()
SC = {1: sc1, 2: sc2}

def cw(name, val, ramp=0):
    e = L.get(name)
    if not e: return False
    SC[e[0]].d.link.write(e[2], val & 0xFFFFFFFF, ramp); time.sleep(S.SETTLE)
    return True

def q28(w):
    return (w - (1 << 32) if w & 0x80000000 else w) / float(1 << 28)

def level(sc, addr, n=N):
    v = []
    for _ in range(n):
        try: v.append(q28(sc.peek(addr)))
        except IOError: pass
        time.sleep(0.008)
    if not v: return None, None
    return (math.sqrt(sum(x*x for x in v)/len(v)), max(abs(x) for x in v))

def db(x, ref):
    if not x or not ref or x <= 0 or ref <= 0: return '   --  '
    return '%+7.2f' % (20*math.log10(x/ref))

POINTS = [
    ('C1 tap pre-fader',   sc1, sc1.sym['_blk_pool'] + 6*16 + 4),
    ('C1 tap post-fader',  sc1, sc1.sym['_blk_pool'] + 7*16 + 4),
    ('C1 FDR L',           sc1, sc1.sym['_blk_pool'] + 2*16 + 4),
    ('C2 MIX_MAIN_L',      sc2, sc2.sym['_buf_C2_MIX_MAIN_L'] + 2),
    ('C2 MIX_AUX_01',      sc2, sc2.sym['_buf_C2_MIX_AUX_01'] + 2),
    ('C2 MAIN_FDR',        sc2, sc2.sym['_buf_C2_MAIN_FDR'] + 2),
]

def snapshot(tag):
    print('  %-22s' % tag, end='')
    out = {}
    for name, sc, a in POINTS:
        r, p = level(sc, a)
        out[name] = r
    print('')
    for name, _, _ in POINTS:
        r = out[name]
        print('      %-20s rms %s' % (name, '--' if r is None else '%.8f' % r))
    return out

# baseline: everything open
for n, v, r in (('Chan001Gain001', f32(1.0), 1), ('Chan001Pan001', f32(0.0), 4),
                ('Chan001Mute001', 0, 0), ('Chan001MainOn001', 1, 0),
                ('Chan001AuxPick001', 3, 0), ('Chan001AuxSend001', f32(1.0), 4),
                ('Chan001AuxOn001', 1, 0), ('Aux001Mute001', 0, 0),
                ('Main001Mute001', 0, 0), ('Aux001Level001', f32(1.0), 4),
                ('Main001Level001', f32(1.0), 4)):
    cw(n, v, r)

print('=== A. CHANNEL FADER authority: Chan001Level001 ===')
res = {}
for lv in (1.0, 0.1, 0.0):
    cw('Chan001Level001', f32(lv), 4); time.sleep(1.2)
    res[lv] = snapshot('Level = %.2f' % lv)
print('  --- change from Level 1.0 (expect -20 dB at 0.1, silence at 0.0) ---')
for name, _, _ in POINTS:
    print('      %-20s 0.1: %s   0.0: %s'
          % (name, db(res[0.1][name], res[1.0][name]), db(res[0.0][name], res[1.0][name])))

cw('Chan001Level001', f32(1.0), 4); time.sleep(1.0)

print('\n=== B. CHANNEL GAIN authority: Chan001Gain001 ===')
res = {}
for g in (1.0, 0.1):
    cw('Chan001Gain001', f32(g), 1); time.sleep(1.2)
    res[g] = snapshot('Gain = %.2f' % g)
print('  --- change from Gain 1.0 (expect -20 dB at 0.1) ---')
for name, _, _ in POINTS:
    print('      %-20s %s' % (name, db(res[0.1][name], res[1.0][name])))
cw('Chan001Gain001', f32(1.0), 1); time.sleep(1.0)

print('\n=== C. AUX MASTER authority: Aux001Level001 ===')
res = {}
for lv in (1.0, 0.1):
    cw('Aux001Level001', f32(lv), 4); time.sleep(1.2)
    res[lv] = snapshot('Aux master = %.2f' % lv)
print('  --- change from 1.0 ---')
for name, _, _ in POINTS:
    print('      %-20s %s' % (name, db(res[0.1][name], res[1.0][name])))
cw('Aux001Level001', f32(1.0), 4)

print('\n=== D. which chip-2 TX lane responds to MAIN vs AUX 1 ===')
tb = sc2.peek(sc2.sym['_tx_active_buf'])
def lanes():
    out = []
    for ln in range(8):
        v = []
        for k in range(6):
            try: v.append(q28(sc2.peek(tb + ln + k*8)))
            except IOError: pass
        out.append(max(abs(x) for x in v) if v else None)
    return out
cw('Main001Mute001', 0); cw('Aux001Mute001', 0); time.sleep(1.2)
both = lanes()
cw('Main001Mute001', 1); time.sleep(1.2); nomain = lanes()
cw('Main001Mute001', 0); cw('Aux001Mute001', 1); time.sleep(1.2); noaux = lanes()
cw('Aux001Mute001', 0)
print('  lane :  both open      main muted     aux1 muted')
for ln in range(8):
    f = lambda v: '--' if v[ln] is None else '%.6f' % v[ln]
    print('   %d   :  %-13s %-13s %s' % (ln, f(both), f(nomain), f(noaux)))
