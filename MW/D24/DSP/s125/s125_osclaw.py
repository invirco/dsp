#!/usr/bin/env python3
"""Is the test oscillator's level law 1 dB per dB?

The seven gain steps lean on it completely: the drive is dropped by each
step's own expected gain (down to -60 dBFS) so the converter sees about the
same level every time, and the scorer adds that drop back before it subtracts.
If the commanded dB and the delivered dB are not the same thing, every gain
step is wrong by the difference and nothing downstream can tell.
"""
import sys, time, json
sys.path.insert(0, '/home/app/selftest')
import d24_patch as P

STRIP = P.DONOR_DEFAULT
LEVELS = [-30, -48, -60, -66, -72, -78, -83, -90, -96]
u = P.Unit()
u.meas_chan(STRIP)
rows = []
try:
    for lv in LEVELS:
        u.osc(chan=STRIP, freq=1000.0, level_dbfs=lv, on=True)
        time.sleep(1.0)
        m = u.measure(1000.0, lv, windows=2, settle=6)
        cell = u.readf('Test001OscLevel001')
        rows.append(dict(cmd=lv, rms=m.get('rms'), coh=m.get('coh_dbfs'),
                         h_db=m.get('h_db'), cell=cell,
                         meter=P.dbv(u.meter_peak(STRIP) or 0)))
    ref = rows[0]
    print('%8s %10s %10s %10s %10s %10s' %
          ('cmd dB', 'cell', 'node rms', 'coherent', 'meter pk', 'rms-rel'))
    for r in rows:
        print('%8.1f %10.6f %10.2f %10s %10.2f %10.2f   (commanded %+.1f)'
              % (r['cmd'], r['cell'], r['rms'],
                 ('%.2f' % r['coh']) if r['coh'] is not None else '--',
                 r['meter'], r['rms'] - ref['rms'], r['cmd'] - ref['cmd']))
finally:
    u.osc(on=False)
json.dump(rows, open('/home/app/selftest/s125-osclaw.json', 'w'), indent=1)
