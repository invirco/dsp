#!/usr/bin/env python3
"""s67_eqprobe.py — bisect the S67-6 MAIN L excess: reproduce with base('osc'), then one change at a time,
reading MAIN L RMS and MAIN L : strip 5 energy (XtalkSrc 5 / XtalkDst 33) after each."""
import time
import s67lib as L
T, X = L.T, L.X
R = L.Rig('/home/app/s67/s67_eqprobe.jsonl')
sym = R.sc.sym
pk = L.rbj_peaking(1000.0, 1.0, 6.0)


def peek(n, k=1):
    return [R._retry(R.sc.peek, sym[n] + i) for i in range(k)]


def win(tag, n=2):
    R.wv(T.A_MEASCHAN, 33); R.wv(T.A_XSRC, 5); R.wv(T.A_XDST, 33)
    s0 = R.rd(T.A_SEQ)
    while (R.rd(T.A_SEQ) - s0) & 0xFFFFFFFF < 3:
        time.sleep(0.03)
    out = []
    for _ in range(n):
        s = R.rd(T.A_SEQ)
        while R.rd(T.A_SEQ) == s:
            time.sleep(0.02)
        out.append('%.2f/%.2f' % (X.from_f32(R.rd(T.A_RMS)), X.from_f32(R.rd(T.A_XTALK))))
    act = (peek('_eq_active_C1_EQ_05')[0], peek('_eq_active_C1_EQ_06')[0])
    bus = [X.s32(w) / 2.0 ** 28 for w in peek('_buf_C1_BUS_MAIN_L', 8)]
    L.P('%-44s MAIN L rms/ratio %s  eq_active(5,6) %s  busL[0:8] %s' % (tag, out, act, ['%.4f' % b for b in bus]))
    T.log({'ev': 'probe', 'tag': tag, 'win': out, 'act': act, 'bus': bus})


R.chain(0)
R.base('osc')
R.osc(1000.0, -26.0, on=True, chan=5)
win('after base(osc) + osc on')
R.cw('Chan005MainOn001', 0); win('strip 5 MainOn 0')
R.cw('Chan005MainOn001', 1); win('strip 5 MainOn 1')
R.osc(1000.0, -26.0, on=False, chan=5); win('osc off')
R.osc(1000.0, -26.0, on=True, chan=5); win('osc on')
for k in range(4):
    R._retry(R.c1.raw_w, L.A_EQ5_SWAP, 1); time.sleep(0.2)
    win('one swap trigger (#%d), unity->unity' % (k + 1))
R.cw('Chan006Mute001', 0); win('strip 6 Mute 0')
R.cw('Chan006Mute001', 1); win('strip 6 Mute 1')
R.eq_bands([pk] + [L.UNITY_BQ] * 3); win('eq peak (3 triggers)')
R.eq_bands([L.UNITY_BQ] * 4); win('eq unity (3 triggers)')
R.wv(T.A_XSRC, 0); R.wv(T.A_XDST, 0)
R.osc(on=False)
