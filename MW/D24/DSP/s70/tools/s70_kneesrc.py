"""Is the knee ANALOG at all? Read the DIGITAL side of the same drives.

The loop compresses above an oscillator level of about -18 dBFS and the lane then pins.
Everything after the AUX 1 bus is analog, but everything before it is the graph -- and the
strip carries a GATE and a COMP that are on by default. If the AUX 1 bus block itself
compresses, the finding is a DSP one and there is nothing analog to report."""
import sys
sys.path.insert(0, '/home/app/s70')
import s70lib as T                                                       # noqa: E402

r = T.Rig()
print('osc dBFS   strip 6 dBFS   dev    AUX 1 bus dBFS   dev    lane(code 0) dBFS   dev', flush=True)
r.mgn2r(0)
base = {}
for lvl in (-45.0, -30.0, -21.0, -19.0, -17.0, -15.0, -13.0, -12.0):
    row = []
    for ch in (6, T.AUX1_BUS, T.TALK):
        p = r.tone(1000.0, lvl, chan=ch)
        ideal = lvl - 3.01 + (0.0 if ch != T.TALK else 8.756)
        row.append((p['rms_dbfs'], p['rms_dbfs'] - ideal))
    print('%8.1f   %12.3f  %+6.3f   %14.3f  %+6.3f   %17.3f  %+6.3f'
          % (lvl, row[0][0], row[0][1], row[1][0], row[1][1], row[2][0], row[2][1]), flush=True)

print('\nstrip 6 node state (is anything dynamic in the donor path?):', flush=True)
for c in ('Chan006GateOn001', 'Chan006CompOn001', 'Chan006TubeOn001', 'Chan006Level001',
          'Chan006CompThresh001', 'Chan006CompRatio001', 'Chan006GateThresh001'):
    try:
        v = r.c1.r(c)
        print('   %-24s raw 0x%08X  f32 %g' % (c, v, T.X.from_f32(v)))
    except Exception as e:
        print('   %-24s (%s)' % (c, e))
r.osc(on=False)
r.mgn2r(T.MGN_INIT)
