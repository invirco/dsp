#!/usr/bin/env python3
"""s67_run.py <phase> [mode] — S67 strip 5 mixer maths on the part. Phases:

  source   which input J25 carries: TEST_OSC on donor strip 6 -> AUX 1, coherent gain at strip 5 (loop ~ +5.6 dB at
           code 0 = cable; ~ -140 dB = the 150 ohm shunt)
  fader    Level 1.0 / -6 dB / -20 dB / 0 (Off) at strip 5 post-fader, MAIN L, MAIN R (and AUX 1 in osc mode)
  pan      pan index 0 / 63 / 126 under Sys LcrLaw 0 (hard-LCR table, linear stereo columns) and 1 (constant power)
  assign   MainOn 1/0 and AuxOn001 1/0 (osc mode for AUX 1): presence and the depth of the off state
  sum      OscChan 99, strips 5 and 6 on MAIN and AUX 1: equal, then strip 6 at -6 dB; linear bus law
  eqdyn    strip 5 EQ band 1 peaking 1 kHz +6 dB Q 1 (read at 1 kHz and 2 kHz), then the compressor
           (thr -20, ratio 4 and 2, knee 0) at two input levels
mode: analog (default where the cable is on) | osc.  Output: ~/s67/data/<phase>_<mode>.json + printed table."""
import json, math, sys, time
_ARGV = list(sys.argv)
import s67lib as L
T, X, PT = L.T, L.X, L.PT

PHASE = _ARGV[1]
MODE = _ARGV[2] if len(_ARGV) > 2 else 'analog'
F = 1000.0
OSC_DB = -26.0
R = L.Rig('%s/s67_run.jsonl' % L.HOME)
res = {'phase': PHASE, 'mode': MODE, 'an_en': R.an_en(), 't0': time.time()}


def stim(level_db=OSC_DB, freq=F):
    chan = L.DONOR if MODE == 'analog' else L.STRIP
    R.osc(freq, level_db, on=True, chan=chan)


def ref_chans():
    return [L.STRIP, L.MAIN_L, L.MAIN_R] + ([L.AUX1] if MODE == 'osc' else [])


def show(tag, d, base=None):
    row = ['%-26s' % tag]
    for ch in sorted(d):
        v = d[ch]['H_db']
        s = '%8.3f' % v if v is not None and v > -1e9 else '    -inf'
        if base and ch in base and v is not None and base[ch]['H_db'] is not None and v > -1e9:
            s += ' (%+7.3f)' % (v - base[ch]['H_db'])
        row.append('%d:%s' % (ch, s))
    L.P(' | '.join(row))


ovr0 = R.overruns()
R.chain(0)
if PHASE == 'source':
    R.base('analog')
    stim()
    d = R.m([L.STRIP], n=3, settle=4, tag='source')
    res['strip5'] = d[L.STRIP]
    res['verdict'] = 'loop cable on J25' if d[L.STRIP]['H_db'] > -20 else 'no loop (shunt / open)'
    show('source', d)
    L.P(res['verdict'])

elif PHASE == 'fader':
    R.base(MODE)
    if MODE == 'osc':
        R.cw('Chan%03dAuxOn001' % L.STRIP, 1)
    stim()
    rows = []
    base = None
    for tag, lin in (('0 dB', 1.0), ('-6 dB', 10 ** (-6 / 20.0)), ('-20 dB', 0.1), ('-inf (Off)', 0.0), ('0 dB again', 1.0)):
        R.level(lin)
        d = R.m(ref_chans(), n=3, settle=4, tag='fader ' + tag)
        if base is None:
            base = d
        show(tag, d, base)
        rows.append({'tag': tag, 'level': lin, 'ideal_db': L.db(lin), 'm': d})
    res['rows'] = rows

elif PHASE == 'pan':
    R.base(MODE)
    stim()
    rows = []
    for law in (0, 1):
        R.wv(L.A_LCR_LAW, law)
        for idx in (0, 63, 126):
            R.pan_idx(idx)
            d = R.m([L.STRIP, L.MAIN_L, L.MAIN_R], n=3, settle=4, tag='pan law%d idx%d' % (law, idx))
            gl, gr = L.pan_legs(law, idx)
            p = d[L.STRIP]['H_db']
            ml, mr = d[L.MAIN_L]['H_db'], d[L.MAIN_R]['H_db']
            r = {'law': law, 'idx': idx, 'pred_L_db': L.db(gl), 'pred_R_db': L.db(gr),
                 'meas_L_db': (ml - p) if ml > -1e9 else None, 'meas_R_db': (mr - p) if mr > -1e9 else None, 'm': d}
            rows.append(r)
            L.P('law %d idx %3d  L %s (pred %s)  R %s (pred %s)' % (
                law, idx, '%8.3f' % r['meas_L_db'] if r['meas_L_db'] is not None else '    -inf',
                '%8.3f' % r['pred_L_db'] if gl > 0 else '    -inf',
                '%8.3f' % r['meas_R_db'] if r['meas_R_db'] is not None else '    -inf',
                '%8.3f' % r['pred_R_db'] if gr > 0 else '    -inf'))
    R.wv(L.A_LCR_LAW, 0)
    R.pan_idx(63)
    res['rows'] = rows

elif PHASE == 'assign':
    R.base(MODE)
    stim()
    rows = []
    steps = [('Main on', 'MainOn001', 1), ('Main off', 'MainOn001', 0), ('Main on again', 'MainOn001', 1)]
    if MODE == 'osc':
        steps += [('Aux1 on', 'AuxOn001', 1), ('Aux1 off', 'AuxOn001', 0), ('Aux1 on again', 'AuxOn001', 1)]
    for tag, cell, v in steps:
        R.cw('Chan%03d%s' % (L.STRIP, cell), v)
        d = R.m(ref_chans(), n=3, settle=4, tag='assign ' + tag)
        words = {s: R.busword(s) for s in ('_buf_C1_BUS_MAIN_L', '_buf_C1_BUS_MAIN_R', '_buf_C1_BUS_AUX_01')}
        nz = {s: sum(1 for w in ws if w) for s, ws in words.items()}
        show(tag, d)
        L.P('   nonzero words of 16:', nz)
        rows.append({'tag': tag, 'cell': cell, 'v': v, 'm': d, 'nonzero16': nz})
    res['rows'] = rows

elif PHASE == 'sum':
    if MODE != 'osc':
        raise SystemExit('sum runs in osc mode (OscChan 99)')
    R.base('osc')
    for s in (L.STRIP, L.OTHER):
        R.cw('Chan%03dMute001' % s, 0)
        R.cw('Chan%03dMainOn001' % s, 0)
        R.cw('Chan%03dAuxOn001' % s, 0)
    R.osc(F, OSC_DB, on=True, chan=99)
    rows = []
    cfgs = [('strip 5 alone', {5: 1}, {5: 1.0, 6: 1.0}),
            ('strip 6 alone', {6: 1}, {5: 1.0, 6: 1.0}),
            ('5 + 6 equal', {5: 1, 6: 1}, {5: 1.0, 6: 1.0}),
            ('5 + 6(-6 dB)', {5: 1, 6: 1}, {5: 1.0, 6: 10 ** (-6 / 20.0)})]
    for tag, on, lv in cfgs:
        for s in (L.STRIP, L.OTHER):
            R.level(lv[s], s)
            R.cw('Chan%03dMainOn001' % s, on.get(s, 0))
            R.cw('Chan%03dAuxOn001' % s, on.get(s, 0))
        d = R.m([L.MAIN_L, L.MAIN_R, L.AUX1], n=3, settle=4, tag='sum ' + tag)
        show(tag, d)
        rows.append({'tag': tag, 'on': on, 'level': lv, 'm': d})
    res['rows'] = rows

elif PHASE in ('eqdyn', 'eq'):
    R.base(MODE)
    rows = []
    R.level(1.0)
    # EQ: band 1 peaking 1 kHz +6 dB Q 1; read at 1 kHz and 2 kHz, off and on
    pk = L.rbj_peaking(1000.0, 1.0, 6.0)
    res['eq_wire_found'] = [R.rd(L.A_EQ5 + i) for i in range(20)]
    for f in (1000.0, 2000.0, 250.0):
        stim(OSC_DB, f)
        R.eq_bands([L.UNITY_BQ] * 4)
        off = R.m([L.STRIP, L.MAIN_L], n=3, settle=5, tag='eq off %g' % f)
        R.eq_bands([pk] + [L.UNITY_BQ] * 3)
        on = R.m([L.STRIP, L.MAIN_L], n=3, settle=5, tag='eq on %g' % f)
        pred = L.bq_mag_db(pk, f)
        r = {'what': 'eq', 'f': f, 'pred_db': pred, 'meas_strip_db': on[L.STRIP]['H_db'] - off[L.STRIP]['H_db'],
             'meas_main_db': on[L.MAIN_L]['H_db'] - off[L.MAIN_L]['H_db'], 'off': off, 'on': on}
        rows.append(r)
        L.P('EQ %6g Hz  pred %+.3f  strip %+.3f  main L %+.3f dB' % (f, pred, r['meas_strip_db'], r['meas_main_db']))
    R.eq_bands([L.UNITY_BQ] * 4)
    # COMP: thr -20 dBFS, knee 0; steady 1 kHz, input peak at the comp from the comp-off coherent peak
    found = R.comp_state()
    res['comp_found'] = found
    for osc_db in ((-16.0, -21.0) if MODE == 'analog' else (-10.0, -16.0)):
        stim(osc_db, F)
        for ratio in (4.0, 2.0):
            R.comp(False, thr=-20.0, ratio=ratio, knee=0.0)
            off = R.m([L.STRIP, L.MAIN_L], n=3, settle=6, tag='comp off')
            R.comp(True)
            on = R.m([L.STRIP, L.MAIN_L], n=3, settle=10, tag='comp on r%g' % ratio)
            gq = R._retry(R.sc.peek, R.sc.sym['_comp_gain_C1_COMP_05'])
            env = R._retry(R.sc.peek, R.sc.sym['_comp_envelope_C1_COMP_05'])
            pk_in = off[L.STRIP]['coh_pk_dbfs']
            over = pk_in - (-20.0)
            pred = -(over * (1 - 1 / ratio)) if over > 0 else 0.0
            r = {'what': 'comp', 'osc_db': osc_db, 'ratio': ratio, 'in_pk_dbfs': pk_in, 'pred_gr_db': pred,
                 'meas_gr_strip_db': on[L.STRIP]['H_db'] - off[L.STRIP]['H_db'],
                 'meas_gr_main_db': on[L.MAIN_L]['H_db'] - off[L.MAIN_L]['H_db'],
                 'comp_gain_word_db': L.db(X.s32(gq) / 2.0 ** 28) if gq else None,
                 'envelope_dbfs': L.db(X.s32(env) / 2.0 ** 28) if env else None, 'off': off, 'on': on}
            rows.append(r)
            L.P('COMP in %.2f dBFS pk ratio %g  pred GR %+.3f  strip %+.3f  main L %+.3f  gain word %s  env %s' % (
                pk_in, ratio, pred, r['meas_gr_strip_db'], r['meas_gr_main_db'],
                '%+.3f' % r['comp_gain_word_db'] if r['comp_gain_word_db'] is not None else None,
                '%.3f' % r['envelope_dbfs'] if r['envelope_dbfs'] is not None else None))
            R.comp(False)
    R.wv(L.A_COMP5['thr'], X.f32(found['thr']))
    R.wv(L.A_COMP5['rat'], X.f32(found['rat']))
    R.wv(L.A_COMP5['knee'], X.f32(found['knee']))
    res['rows'] = rows
else:
    raise SystemExit('unknown phase ' + PHASE)

R.osc(on=False)
res['overruns_c1'] = (R.overruns() - ovr0) & 0xFFFFFFFF
res['an_en_end'] = R.an_en()
L.P('chip-1 overruns during phase:', res['overruns_c1'], '| AN_EN', res['an_en_end'])
L.save('%s_%s' % (PHASE, MODE), res)
