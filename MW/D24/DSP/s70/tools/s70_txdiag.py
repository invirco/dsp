"""Where does the tone stop? Strip 6 -> AUX 1 bus -> chip 2 -> DAC -> J45.

Gate 0 reads the donor strip tracking the oscillator exactly and every codec return flat,
so either the loop cable / analog return is open or the tone never leaves the DSP. This
walks the transmit side first, because it is free and because S55's handback explicitly
set Chan006AuxOn001 to 0."""
import sys
sys.path.insert(0, '/home/app/s69')
import s69lib as L                                                       # noqa: E402

X = L.X
r = L.Rig()
r.osc(freq=1000.0, level_db=-20.0, on=True)

CELLS = ['Chan006Level001', 'Chan006Mute001', 'Chan006Pan001', 'Chan006AuxOn001',
         'Chan006AuxSend001', 'Chan006MainOn001', 'Chan006Gain001', 'Chan006Polarity001']
for c in CELLS:
    try:
        v = r.c1.r(c)
        print('%-22s raw 0x%08X  f32 %g' % (c, v, X.from_f32(v)))
    except Exception as e:
        print('%-22s ERR %s' % (c, e))

print()
for ch, name in ((6, 'strip 6 post-fader'), (33, 'MAIN L'), (34, 'MAIN R'),
                 (35, 'AUX 1'), (36, 'AUX 2')):
    r.meas(ch)
    p = r.point(3)
    print('MeasChan %-3d %-20s rms %9.3f dBFS' % (ch, name, p['rms_dbfs']))
r.osc(on=False)
