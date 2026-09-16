#!/usr/bin/env python3
"""s63_latch.py — which CS_M edge applies the gain, and how long after it the lane moves. Tone 1 kHz on the MIC 5 loop,
code 0 <-> 1 (a one-bit, 12.8 dB step), span captures with the two chain passes GAP_S apart (0 and 50 ms). Every edge of
both passes is mapped to a capture sample; the change is located on the desk (s63_analyse envelope)."""
import os, time
import s63lib as S
import s63_run as RUN
T, X = S.T, S.X
R = RUN.Rig()
xlr, p, lane = 'J25', S.D24.MIC5.send, S.D24.MIC5_STRIP
R.select(xlr, p, lane)
G = S.loop_gain(xlr)
R.set_code(0); R.set_trim(0.0)
R.tone(-8.0 - G[1])
for gap in (0.0, 0.05, 0.05, 0.0):
    for frm, to in ((0, 1), (1, 0)):
        if R.code != frm:
            R.set_code(frm)
        time.sleep(max(0.0, 3.0 - (time.time() - R.t_change)))
        edges = []

        def f():
            ok, got, a, b = S.chain_send_timed(R.image(to), gap_s=gap, times=edges)
            return {'t_latch_lo': a, 't_latch_hi': b, 'chain_verified': ok,
                    **{'t_p%d_%s' % (k, w): t for k, w, t in edges}}
        rec, vals = R.span(f, at=4800)
        R.code = to; R.t_change = time.time()
        rec.update({'xlr': xlr, 'p': p, 'lane': lane, 'stim': 'tone', 'kind': 'latch', 'from': [frm, 0.0], 'to': [to, 0.0],
                    'gap_s': gap, 'osc_dbfs_pk': -8.0 - G[1], 'law_from': G[frm], 'law_to': G[to], 'invalid': None})
        S.save(vals, rec, 'latch_' + xlr)
        S.P('gap %.3f %d->%d: p1 lo %.0f hi %.0f  p2 lo %.0f hi %.0f  verified %s' % (
            gap, frm, to, rec['s_p1_lo'], rec['s_p1_hi'], rec['s_p2_lo'], rec['s_p2_hi'], rec['chain_verified']))
R.tone(None)
R.set_code(0)
