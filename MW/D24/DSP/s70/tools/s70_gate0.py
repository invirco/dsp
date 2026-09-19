"""S70 gate 0 — the loop with AN_EN HIGH: does the talkback lane follow the oscillator,
and WHICH lane is it (S69-1)?

Deliberately starts 20 dB below anything that could stress the codec's analog pin: at the
init gain (+27 dB) the AK4619's input full scale is 2.83 Vpp / 10^(27/20) = 127 mVpp, and
the DAC's full scale at J45 is 11.1 V RMS, so an oscillator above about -33 dBFS would
already be over the part's ABSOLUTE MAXIMUM (the lower of AVDD+0.3 and 4.3 V) if the
talkback input carries no pad. Whether it carries one is exactly what the first ladder
measures, so the ladder runs low and climbs.
"""
import json
import os
import sys
import time

sys.path.insert(0, '/home/app/s69')
import s69lib as L                                                       # noqa: E402

LANES = {51: 'CODEC_RET_1 (slot 0, ADC1 Lch, graph "TB XLR")',
         52: 'CODEC_RET_3 (slot 2, ADC2 Lch, graph "Aux In L")',
         53: 'CODEC_RET_4 (slot 3, ADC2 Rch, netlist talkback)'}
LEVELS = [None, -80.0, -70.0, -60.0, -50.0]      # None = oscillator off

r = L.Rig('/home/app/s70/s70.jsonl')
out = {'gate': 0, 'an_en_expected': 'hi', 'mgn2r_code': L.MGN_INIT,
       'mgn2r_db': L.MGN_DB[L.MGN_INIT], 'rows': []}
r.osc(freq=1000.0, level_db=-80.0, on=False)
for lvl in LEVELS:
    if lvl is None:
        r.osc(on=False)
    else:
        r.osc(freq=1000.0, level_db=lvl, on=True)
    for ch in sorted(LANES) + [6]:
        r.meas(ch)
        p = r.point(3)
        row = {'osc_dbfs': lvl, 'chan': ch, 'rms_dbfs': p['rms_dbfs'],
               'thd_db': p['thd_db'], 'noise_dbfs': p['noise_dbfs']}
        if lvl is not None:
            row['fit'] = r.fit()
        out['rows'].append(row)
        print('osc %-6s chan %-3d %-46s rms %9.3f  thd %8.2f  noise %9.3f%s'
              % ('off' if lvl is None else '%.0f' % lvl, ch,
                 LANES.get(ch, 'donor strip 6'), p['rms_dbfs'], p['thd_db'],
                 p['noise_dbfs'],
                 ('  loop %+8.3f dB  phase %+8.2f' % (row['fit']['gain_db'],
                                                      row['fit']['phase_deg']))
                 if lvl is not None else ''), flush=True)
r.osc(on=False)
os.makedirs('/home/app/s70/data', exist_ok=True)
json.dump(out, open('/home/app/s70/data/gate0.json', 'w'), indent=1)
print('written /home/app/s70/data/gate0.json')
