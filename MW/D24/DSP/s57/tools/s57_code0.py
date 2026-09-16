"""s57_code0.py — MIC 5 to code 0 (p15, unmuted, phantom off); TEST_OSC off; the MIC 5 strip -> AUX 1 routing untouched."""
import os, sys
os.environ.setdefault('SYMDIR', '/home/app/s56')
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s56')
import s54lib as T
r = T.Rig(logpath='/home/app/s57/s57_code0.jsonl')
if r.rd(T.A_OSCON):
    r.wv(T.A_OSCON, 0)
b = r.chain(0)
c1 = r.c1
print('CODE0 SET  %s  OscOn %d  strip20 AuxOn %d Mute %d' % (b, r.rd(T.A_OSCON), c1.r('Chan%03dAuxOn001' % T.LOOP), c1.r('Chan%03dMute001' % T.LOOP)), flush=True)
