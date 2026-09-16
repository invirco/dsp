"""s57_gain_set.py — MIC 5 code 63 (p15, unmuted, phantom off), TEST_OSC off, NOTHING on AUX 1 (strip 6's S56 hand-back
send removed; every strip's AuxOn001 and the chip-2 source families read back). Lane RMS read for the record."""
import os, sys
os.environ.setdefault('SYMDIR', '/home/app/s56')
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s56')
import s54lib as T
X = T.X
P = lambda *a: print(*a, flush=True)
r = T.Rig(logpath='/home/app/s57/s57_gain_set.jsonl'); c1 = r.c1
r.osc(on=False); r.meas(20)
c1.wv('Chan006AuxOn001', 0)
P('chain:', r.chain(63))
on = [s for s in range(1, 25) if c1.r('Chan%03dAuxOn001' % s) == 1]
c2 = X.Chip(2)
fam = {f: c2.r('%s001On001' % f) for f in ('Usb', 'Bt', 'CodecAux', 'Pi')}
m = r.windows(3, settle_windows=40, tag='gain_set')
g = [w['rms'] for w in m['rows']]
T.log({'ev': 'gain_set', 'auxon1': on, 'fam': fam, 'osc_on': r.rd(T.A_OSCON), 'lane_rms': g})
P('OscOn %d | strips with AuxOn001=1: %s | chip-2 sources On: %s | strip 20 AuxOn001 %d' % (r.rd(T.A_OSCON), on, fam, c1.r('Chan020AuxOn001')))
P('lane RMS at code 63, DC-24 kHz (TEST_MEAS): %s dBFS' % ' '.join('%.2f' % v for v in g))
