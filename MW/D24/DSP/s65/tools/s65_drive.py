#!/usr/bin/env python3
"""s65_drive.py PRODUCT [level_dbfs] — the DRIVEN regime without a CPLD flash (S65): TEST_OSC's S65 arm, channel 99,
replaces EVERY strip's input block with a 1 kHz sine (default -6 dBFS pk), and dsp4_driven_setup.py --mode load opens
every bus assign and send on chip 1 and puts every gate/compressor at -60 dB, On. The injector costs the same on the
base pair and the S65 pair, so the difference between them is the cue bus's. Witness: the comp/gate gain-reduction
meter words of strips 1-3 must be non-zero."""
import os, subprocess, sys, time
import s65lib as L
T = L.T
prod = sys.argv[1] if len(sys.argv) > 1 else 'd24'
lvl = float(sys.argv[2]) if len(sys.argv) > 2 else -6.0
out = subprocess.run(['python3', 'dsp4_driven_setup.py', '--chip', '1', '--mode', 'load', '--landed',
                      '/home/app/dspboot/landed-%s.json' % prod], capture_output=True, text=True)
print('\n'.join((out.stdout + out.stderr).splitlines()[-6:]))
subprocess.run(['sudo', 'pinctrl', 'set', '6,24', 'op', 'dh'], check=True)
R = T.Rig()
R.osc(freq=1000.0, level_db=lvl, on=True, chan=99)
time.sleep(1.0)
w = {}
for s in (1, 2, 3):
    for k in ('_mtr_gr_C1_MTR_%02d' % s, '_mtr_cgr_C1_MTR_%02d' % s, '_mtr_peak_C1_MTR_%02d' % s):
        if k in R.sc.sym:
            w[k] = '0x%08X' % R.peek(k)
print('OscChan', R.rd(T.A_OSCCHAN), 'OscOn', R.rd(T.A_OSCON), 'level %.2f dBFS' % R.level_db)
print('witness', w)
T.log({'ev': 'drive', 'prod': prod, 'level': lvl, 'witness': w})
