"""s55_handback.py — leave the unit as S55 found it: TEST_OSC off; nothing on AUX 1 (strip 6 AuxOn001 0 as S57 left
it); strip 1 AuxSend001 back to 0.0 (the J32 donor switch set it to 1.0); MeasChan 20; the 595 image S57 left:
J25 (p15) open code 0, every other register muted code 0 (0x01) incl. J42 (p0), INSTR byte (p24) 0x00. Everything read
back; AN_EN read, never written."""
import subprocess, sys
sys.path.insert(0, '/home/app/s55')
import s55_run as S
T, X = S.T, S.X
R = S.S55()
R.osc(on=False)
R.wv(T.A_OSCCHAN, 6)
R.meas(20)
R.c1.wv('Chan006AuxOn001', 0)
R.c1.wv('Chan001AuxSend001', 0)
R.image = [0x01] * 25
R.image[15] = 0x00
R.image[24] = 0x00
R.chain(0)
m = R.windows(3, settle_windows=10, tag='handback')
rec = {'ev': 'handback', 'img': ['%02X' % b for b in R.image], 'osc_on': R.rd(T.A_OSCON), 'meas': R.rd(T.A_MEASCHAN),
       'auxon1': [s for s in range(1, 25) if R.c1.r('Chan%03dAuxOn001' % s) == 1],
       's1_auxsend': X.from_f32(R.c1.r('Chan001AuxSend001')), 'lane20_rms': [w['rms'] for w in m['rows']],
       'an_en': R.an_en()[1]}
T.log(rec)
print(rec, flush=True)
