"""s57_pw_setup.py — PW bench window: MIC 5 (the MIC 5 strip) at code 63 -> AUX 1 alone, unity, TEST_OSC off.
Guard first: the lane at code 63 must read the 150 ohm floor (~ -92 dBFS), not the loop (~ -52): routing MIC 5 at
+58.7 dB to AUX 1 with the loop cable on J45->J25 would close a feedback loop. Then dsp4_apply_strip.py <MIC 5 strip> 1 (every
strip and USB/BT/CodecAux/Pi off AUX 1, strips muted, the MIC 5 strip unmuted, post-fader send 1.0), then the MIC 5 strip off MAIN
and every other bus, EQ/comp/gate/tube off, gain/fader unity. Verify: all AuxOn001 read back, MIC-5-strip 16k capture FFT
(20-20k, A, DC-24k), AUX 1 TX lane RMS from chip 2's TX words (Q1.31, 1.0 = DAC FS), with a runaway guard."""
import json, math, os, subprocess, sys, time
os.environ.setdefault('SYMDIR', '/home/app/s56')
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s56')
import s54lib as T
import dsp4_meascap as MC
import dsp4_fft as F
X = T.X
P = lambda *a: print(*a, flush=True)
r = T.Rig(logpath='/home/app/s57/s57_pw_setup.jsonl'); c1 = r.c1
r.osc(on=False); r.meas(T.LOOP)
P('chain:', r.chain(63))
m = r.windows(3, settle_windows=40, tag='pw_guard')
g = [w['rms'] for w in m['rows']]
P('guard, lane RMS at code 63 (DC-24k):', ['%.2f' % v for v in g])
if max(g) > -80.0:
    r.chain(0)
    raise SystemExit('LANE AT %.1f dBFS: looks like the LOOP CABLE, not 150 ohm. NOT ROUTED; MIC 5 back to code 0.' % max(g))
# dsp4_apply_strip.py cannot run here: this process already holds chip 1's CS (EBUSY). Same writes, AUX 1 only.
c2 = X.Chip(2)
for s_ in range(1, 25):
    if s_ != T.LOOP:
        c1.wv('Chan%03dAuxOn001' % s_, 0)
for fam in ('Usb', 'Bt', 'CodecAux', 'Pi'):
    c2.wv('%s001On001' % fam, 0)
c2.wv('Aux001Level001', X.f32(1.0), 4)
c2.wv('Aux001Mute001', 0)
c1.wv('Chan%03dGain001' % T.LOOP, X.f32(1.0), 1)
c1.wv('Chan%03dLevel001' % T.LOOP, X.f32(1.0), 4)
c1.wv('Chan%03dMute001' % T.LOOP, 0)
c1.wv('Chan%03dAuxPick001' % T.LOOP, 3)
def ramped(name, val):
    # a ramped cell reads back its CURRENT ramp value; write once, then poll until it settles
    import time as _t
    c1.w(name, X.f32(val), 4)
    for _ in range(40):
        _t.sleep(0.05)
        got = X.from_f32(c1.r(name))
        if abs(got - val) < 1e-6:
            return got
    raise SystemExit('%s reads %.6f after 2 s, wanted %.6f' % (name, got, val))
P('Chan020AuxSend001 settled at', ramped('Chan%03dAuxSend001' % T.LOOP, 1.0))
c1.wv('Chan%03dAuxOn001' % T.LOOP, 1)
p = 'Chan%03d' % T.LOOP
for k in ('MainOn001', 'CompOn001', 'GateOn001', 'EqOn001', 'TubeOn001', 'Pol001'):
    c1.wv(p + k, 0)
for a in range(2, 9):
    c1.wv(p + 'AuxOn%03d' % a, 0)
for a in range(1, 7):
    c1.wv(p + 'FxOn%03d' % a, 0)
for a in range(1, 5):
    c1.wv(p + 'GrpOn%03d' % a, 0)
st = {k: c1.r(p + k) for k in ('Mute001', 'MainOn001', 'AuxOn001', 'AuxPick001', 'CompOn001', 'GateOn001', 'EqOn001', 'TubeOn001', 'Pol001')}
st['Gain001'] = X.from_f32(c1.r(p + 'Gain001')); st['Level001'] = X.from_f32(c1.r(p + 'Level001')); st['AuxSend001'] = X.from_f32(c1.r(p + 'AuxSend001'))
P('the MIC 5 strip:', st)
on = [s for s in range(1, 25) if c1.r('Chan%03dAuxOn001' % s) == 1]
P('strips with AuxOn001 = 1:', on, '| OscOn', r.rd(T.A_OSCON), '| muted:', len([s for s in range(1, 25) if c1.r('Chan%03dMute001' % s) == 1]), 'of 24')
# AUX 1 TX lane, with a runaway guard
sc2 = c2.sc
ptrs, offs, strd = sc2.sym['_c2_tx_ptrs'], sc2.sym['_c2_tx_off'], sc2.sym['_c2_tx_stride']
want = sc2.sym['_tx_out_slot_C2_AUX_OUT_01']
idx = [i for i in range(24) if sc2.peek(ptrs + i) == want][0]
off, sd = sc2.peek(offs + idx), sc2.peek(strd + idx)
def tx(n):
    w = []
    while len(w) < n:
        try:
            b = sc2.peek(sc2.sym['_tx_active_buf'])
            w.extend(X.s32(sc2.peek(b + off + k * sd)) / 2.0 ** 31 for k in range(16))
        except IOError:
            pass
    return w
v = tx(160)
if max(abs(x) for x in v) == 0:
    raise SystemExit('AUX 1 TX lane reads all zero: route did not land')
if T.dbv(math.sqrt(sum(x * x for x in v) / len(v))) > -60:
    c1.wv(p + 'Mute001', 1)
    raise SystemExit('AUX 1 TX lane above -60 dBFS: the MIC 5 strip MUTED again (runaway guard)')
v = tx(3200)
tx_rms = 10 * math.log10(sum(x * x for x in v) / len(v))
cap = MC.capture(16384, '/home/app/s56', sc=r.sc, log=lambda *a: None)
sig = [X.s32(x) / float(1 << 28) for x in cap['samples']]
mean = sum(sig) / len(sig)
raw = 10 * math.log10(sum((x - mean) ** 2 for x in sig) / len(sig))
b20 = F.band_power(sig, 48000.0, 20, 20000)[0]; aw = F.band_power(sig, 48000.0, 20, 20000, aweight=True)[0]
rec = {'ev': 'pw_ready', 'tx_rms_dbfs_dc24k': tx_rms, 'tx_words': len(v), 'cap_raw': raw, 'cap_b20k': b20, 'cap_a20k': aw,
       'overruns': cap['overruns'], 'strip20': st, 'auxon1': on}
T.log(rec)
json.dump(dict(cap, tag='pw_ready'), open('/home/app/s57/data/pw_ready_00.json', 'w'))
P('AUX 1 TX lane RMS (chip 2 TX words, %d point samples, DC-24 kHz, Q1.31): %.2f dBFS' % (len(v), tx_rms))
P('the MIC 5 strip post-fader capture (feeds AUX 1 at unity): DC-24k %.2f, 20-20k %.2f, A %.2f dBFS, ovr +%d' % (raw, b20, aw, cap['overruns']))
P('expected at J45 (+3.01 +23.13): 20-20k %.2f dBu, A %.2f dBu' % (b20 + 26.14, aw + 26.14))
