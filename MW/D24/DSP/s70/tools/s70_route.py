"""Route the donor strip onto AUX 1 and PROVE it on the bus, then re-run the gate-0 ladder.

A fresh boot+config leaves Chan006AuxOn001 = 0 and Chan006AuxSend001 = 0.0, so the AUX 1
bus block is EXACTLY zero (-336 dBFS) and the DAC has nothing to send: gate 0 was reading
an open loop that was open inside the DSP. AuxSend is a RAMPED cell (ramp profile 1), so
it is written with ramp_id 1 and verified with tolerance, never for an exact word."""
import json
import sys
import time

sys.path.insert(0, '/home/app/s69')
import s69lib as L                                                       # noqa: E402

X = L.X
LANES = {51: 'CODEC_RET_1 (slot 0, ADC1 Lch, graph "TB XLR")',
         52: 'CODEC_RET_3 (slot 2, ADC2 Lch, graph "Aux In L")',
         53: 'CODEC_RET_4 (slot 3, ADC2 Rch, netlist talkback)'}

r = L.Rig('/home/app/s70/s70.jsonl')
r.osc(freq=1000.0, level_db=-80.0, on=True)
r.c1.wv('Chan006AuxOn001', 1)
r.c1.wv('Chan006AuxSend001', X.f32(1.0), ramp=1)
time.sleep(0.5)
send = X.from_f32(r.c1.r('Chan006AuxSend001'))
print('AuxOn001 %d  AuxSend001 %.6f (ramped, tolerance)' % (r.c1.r('Chan006AuxOn001'), send))
assert abs(send - 1.0) < 1e-5, send

r.meas(35)
print('AUX 1 bus with osc -80 dBFS: %.3f dBFS' % r.point(3)['rms_dbfs'])

out = {'gate': '0b', 'rows': []}
for lvl in [None, -80.0, -70.0, -60.0, -50.0, -40.0]:
    if lvl is None:
        r.osc(on=False)
    else:
        r.osc(freq=1000.0, level_db=lvl, on=True)
    for ch in sorted(LANES) + [35]:
        r.meas(ch)
        p = r.point(3)
        row = {'osc_dbfs': lvl, 'chan': ch, 'rms_dbfs': p['rms_dbfs'],
               'thd_db': p['thd_db'], 'noise_dbfs': p['noise_dbfs']}
        if lvl is not None:
            row['fit'] = r.fit()
        out['rows'].append(row)
        print('osc %-6s chan %-3d %-46s rms %9.3f%s'
              % ('off' if lvl is None else '%.0f' % lvl, ch,
                 LANES.get(ch, 'AUX 1 bus'), p['rms_dbfs'],
                 ('  loop %+8.3f dB  phase %+8.2f' % (row['fit']['gain_db'],
                                                      row['fit']['phase_deg']))
                 if lvl is not None else ''), flush=True)
r.osc(on=False)
json.dump(out, open('/home/app/s70/data/gate0b.json', 'w'), indent=1)
print('written /home/app/s70/data/gate0b.json')
