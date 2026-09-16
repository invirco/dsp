#!/usr/bin/env python3
"""s60_found.py [tag] — read-only snapshot of the unit before/after S60: TEST_OSC/TEST_MEAS words, strips 5/6,
AN_EN/CS_M, the input patch on the part, and whether the MIC 5 strip carries the loop (TEST_MEAS on it for
a few windows). Writes nothing to the part except MeasChan, which it puts back."""
import json, subprocess, sys, time
_ARGV = list(sys.argv)
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/dspboot')
import s54lib as T
import d24_inputs as D
X = T.X
tag = _ARGV[1] if len(_ARGV) > 1 else 'found'
R = T.Rig('/home/app/s60/s60_found.jsonl')
c1 = R.c1
pin = lambda n: subprocess.run(['pinctrl', 'get', str(n)], capture_output=True, text=True).stdout.strip()
st = {'tag': tag, 'an_en': pin(26), 'cs_m': pin(27)}
for k, a in (('OscOn', 4975), ('OscChan', 4978), ('SweepOn', 4979), ('SweepStep', 4980), ('MeasChan', 4967),
             ('XtalkSrc', 4971), ('XtalkDst', 4972), ('CaptureArm', 4981), ('CaptureReady', 4982)):
    st[k] = R.rd(a)
st['OscFreq'] = X.from_f32(R.rd(4976)); st['OscLevel'] = X.from_f32(R.rd(4977))
KEYS = ['Gain001', 'Pol001', 'Level001', 'CompOn001', 'GateOn001', 'EqOn001', 'TubeOn001', 'MainOn001', 'Mute001',
        'AuxSend001', 'AuxPick001'] + ['AuxOn%03d' % a for a in range(1, 9)]
for s in (5, 6):
    st['strip%d' % s] = {k: c1.r('Chan%03d%s' % (s, k)) for k in KEYS}
st['mutes'] = {s: c1.r('Chan%03dMute001' % s) for s in range(1, 25)}
ent = [R._retry(R.sc.peek, R.sc.sym['_c1_rx_node_entry'] + s - 1) for s in range(1, 25)]
inv = [None] * 24
for i in range(24):
    inv[D.D24_INPUT_PATCH[i]] = i
st['patch_is_s58'] = ent == inv
meas0 = st['MeasChan']
R.on = st['OscOn'] == 1 and st['SweepOn'] == 0
R.freq = st['OscFreq']; R.level_db = T.dbv(st['OscLevel']) if st['OscLevel'] > 0 else None
R.meas(D.MIC5_STRIP, st['XtalkSrc'], st['XtalkDst'])
m = R.windows(2, settle_windows=3, tag='found_mic5')
st['mic5_rms'] = T.summ(m, 'rms'); st['mic5_coh_gain'] = T.summ(m, 'H_db')
R.wv(4967, meas0)
st['sym_osc_ch'] = '_osc_ch_pos_C1_TEST_OSC' in R.sc.sym
T.log(dict(ev='found', **st))
print(json.dumps(st, indent=1))
