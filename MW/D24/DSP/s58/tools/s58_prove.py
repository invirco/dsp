#!/usr/bin/env python3
"""s58_prove.py — S58 gate 2: the netlist input patch on the part.

  1. read-only: chip-1 `_c1_rx_node_entry[1..24]` must equal the PRE-S58 table's inverse (the patch as found);
  2. TEST_OSC 1 kHz -20 dBFS pk on donor strip 6 -> AUX 1 (MainOn/CompOn 0), 3 raw-RX scans of strips 1-24;
  3. write D24_INPUT_PATCH (d24_inputs / dsp4_config) + CONFIG_COMMIT; node_entry must equal its inverse;
  4. 3 scans again; identity patch scanned for comparison, S58 patch re-applied; TEST_MEAS on MIC 5's new strip (made transparent, off every bus) and on strip 20;
  5. no tone anywhere (no loop cable): osc off, MIC 5's register (send p15) alone to code 63 and back to 0, the
     floors of strips 1-24 read at both codes — the MIC 5 strip must be the one that rises;
  6. S55 cross-check: for every XLR S55 detected on lane L (pre-S58), old node_entry[L] == new node_entry[strip(XLR)];
  7. hand back: osc off, strip 6 and the MIC 5 strip as found, MeasChan = the MIC 5 strip, chain image as found, NEW
     patch left applied. AN_EN (GPIO 26) read, never written.
Records -> /home/app/s58/s58.jsonl."""
import json, os, subprocess, sys, time
os.environ.setdefault('SYMDIR', '/home/app/s56')
sys.path.insert(0, '/home/app/dspboot'); sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s55')
import d24_inputs as D
import s54lib as T
import s55_chain as CH
X = T.X

HOME = '/home/app/s58'
os.makedirs(HOME, exist_ok=True)
R = T.Rig(HOME + '/s58.jsonl')
c1, sc = R.c1, R.sc
M5 = D.MIC5_STRIP
S55_LANES = {'J25': 20, 'J26': 19, 'J27': 18, 'J28': 17, 'J29': 7, 'J30': 8, 'J31': 5, 'J32': 6, 'J35': 24, 'J36': 23,
             'J37': 22, 'J38': 21, 'J39': 11, 'J40': 12, 'J41': 9, 'J42': 10}
IMAGE_AS_FOUND = [0x01] * 15 + [0x00] + [0x01] * 8 + [0x00]     # S55 hand-back: J25 (p15) open code 0, INSTR off


def P(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


def an_en():
    return subprocess.run(['pinctrl', 'get', '26'], capture_output=True, text=True).stdout.strip()


def entries():
    return [R._retry(sc.peek, sc.sym['_c1_rx_node_entry'] + s - 1) for s in range(1, 25)]


def inverse(patch):
    inv = [None] * 24
    for i in range(24):
        inv[patch[i]] = i
    return inv


def scan(tag, n=3):
    rows = []
    for k in range(n):
        row = {}
        for s in range(1, 25):
            try:
                e, r, pk = X.lane(c1, s, reads=16)
            except (IOError, OSError):
                sc.d.resync(); e, r, pk = X.lane(c1, s, reads=16)
            row[s] = (e, r, pk)
        rows.append(row)
    pk = {s: max(r[s][2] for r in rows if r[s][2] is not None) for s in range(1, 25)}
    rms = {s: sorted(r[s][1] for r in rows if r[s][1] is not None)[len(rows) // 2] for s in range(1, 25)}
    order = sorted(pk, key=lambda s: -pk[s])
    T.log({'ev': 'scan', 'tag': tag, 'entry': {s: rows[0][s][0] for s in pk}, 'pk': pk, 'rms': rms})
    by_rx = {r.rx: r.xlr for r in D.XLRS}   # label by the RX entry the strip reads, whatever patch is applied
    P('%s: top strips by peak: %s' % (tag, ', '.join('%d (%s, rx %d) %.2f' % (
        s, by_rx.get(rows[0][s][0], '-'), rows[0][s][0], pk[s]) for s in order[:4])))
    return pk, rms, order


def strip_keys(s):
    return {k: c1.r('Chan%03d%s' % (s, k)) for k in ['Gain001', 'Pol001', 'Level001', 'CompOn001', 'GateOn001',
            'EqOn001', 'TubeOn001', 'MainOn001', 'Mute001', 'AuxSend001', 'AuxPick001'] + ['AuxOn%03d' % a for a in range(1, 9)]}


def restore(s, saved):
    order = ['AuxOn%03d' % a for a in range(1, 9)] + ['MainOn001', 'CompOn001', 'GateOn001', 'EqOn001', 'TubeOn001',
             'AuxPick001', 'AuxSend001', 'Pol001', 'Gain001', 'Level001', 'Mute001']
    for k in order:
        c1.wv('Chan%03d%s' % (s, k), saved[k], 1 if k == 'Gain001' else (4 if k in ('Level001', 'AuxSend001') else 0))


def chain(img):
    for _ in range(4):
        ok, got = CH.send(img)
        if ok:
            break
    T.log({'ev': 'chain', 'img': ['%02X' % b for b in img], 'verified': ok})
    if not ok:
        raise SystemExit('chain image NOT VERIFIED: %s' % got)


out = {'an_en0': an_en(), 'mic5_strip': M5}
assert D.check()
P('S58 prove — MIC 5 = J25 = %s rx %d -> strip %d under D24_INPUT_PATCH (pre-S58: %d); AN_EN %s'
  % (D.MIC5.adc, D.MIC5.rx, M5, D.MIC5.strip(D.PRE_S58_PATCH), out['an_en0']))
st = {'osc_on': R.rd(T.A_OSCON), 'osc_chan': R.rd(T.A_OSCCHAN), 'meas': R.rd(T.A_MEASCHAN)}
saved6, savedM5 = strip_keys(6), strip_keys(M5)
T.log({'ev': 'found', 'state': st, 'strip6': saved6, 'strip%d' % M5: savedM5})
P('found: OscOn %(osc_on)d OscChan %(osc_chan)d MeasChan %(meas)d' % st)

# 1. the patch as found
e_old = entries()
out['entry_found'] = e_old
out['found_is_pre_s58'] = e_old == inverse(D.PRE_S58_PATCH)
out['found_is_new'] = e_old == inverse(D.D24_INPUT_PATCH)
P('node_entry[1..24] as found: %s  pre-S58 inverse: %s  new inverse: %s' % (e_old, out['found_is_pre_s58'], out['found_is_new']))

# 2. tone, old patch
c1.wv('Chan006MainOn001', 0); c1.wv('Chan006CompOn001', 0); c1.wv('Chan006Mute001', 0); c1.wv('Chan006AuxOn001', 1)
R.osc(1000.0, -20.0, on=True, chan=6)
time.sleep(1.0)
pk0, rms0, ord0 = scan('pre-S58 patch, tone on')
tone_old = ord0[0] if pk0[ord0[0]] > -40 and pk0[ord0[0]] - pk0[ord0[1]] > 15 else None
out['tone_pre'] = {'strip': tone_old, 'pk': pk0}

# 3. land the patch on the part
X.apply_patch(c1, list(D.D24_INPUT_PATCH))
e_new = entries()
out['entry_new'] = e_new
out['new_is_new'] = e_new == inverse(D.D24_INPUT_PATCH)
P('after D24_INPUT_PATCH + COMMIT: node_entry %s  == new inverse: %s' % (e_new, out['new_is_new']))
time.sleep(1.0)
pk1, rms1, ord1 = scan('S58 patch, tone on')
tone_new = ord1[0] if pk1[ord1[0]] > -40 and pk1[ord1[0]] - pk1[ord1[1]] > 15 else None
out['tone_new'] = {'strip': tone_new, 'pk': pk1}

# 4. TEST_MEAS through the strip
X.strip_unity(c1, M5)
res = {}
for s in (M5, 16, 20):
    R.meas(s)
    m = R.windows(3, settle_windows=5, tag='meas strip %d' % s)
    res[s] = {'rms': T.summ(m, 'rms'), 'thd': T.summ(m, 'thd'), 'coh_pk': T.summ(m, 'coh_pk_dbfs')}
    P('TEST_MEAS strip %2d (%s under S58): RmsResult %.2f dBFS, ThdResult %.2f dB, coherent pk %s dBFS'
      % (s, D.xlr_on(s).xlr, res[s]['rms'], res[s]['thd'], '%.2f' % res[s]['coh_pk'] if res[s]['coh_pk'] is not None else '-'))
out['meas_tone'] = res
# 4b. the identity patch for comparison (S52-1: J25 -> C1_IN_16 = sport 1 slot 7), then the S58 patch back
X.apply_patch(c1, list(range(46)))
e_id = entries()
pk2, _, ord2 = scan('IDENTITY patch, tone on')
out['tone_identity'] = {'strip': ord2[0] if pk2[ord2[0]] > -40 and pk2[ord2[0]] - pk2[ord2[1]] > 15 else None, 'pk': pk2,
                        'entry': e_id}
X.apply_patch(c1, list(D.D24_INPUT_PATCH))
out['reapplied_is_new'] = entries() == inverse(D.D24_INPUT_PATCH)
pk3, _, ord3 = scan('S58 patch re-applied, tone on')
out['tone_new_again'] = {'strip': ord3[0] if pk3[ord3[0]] > -40 and pk3[ord3[0]] - pk3[ord3[1]] > 15 else None, 'pk': pk3}
R.osc(on=False, chan=6)
c1.wv('Chan006AuxOn001', saved6['AuxOn001'])

# 5. no loop cable: MIC 5's register alone to code 63, floors
if tone_new is None:
    P('no tone on any strip (no loop cable on a powered XLR): 150 ohm / open-input floor proof on J25 (send p15)')
    time.sleep(1.0)
    fl = {}
    for code in (0, 63, 0):
        img = list(IMAGE_AS_FOUND); img[15] = CH.byte(gain=code)
        chain(img)
        time.sleep(2.0)
        _, rms, _ = scan('code %d floors' % code, n=5)
        R.meas(M5)
        m = R.windows(4, settle_windows=20, tag='floor code %d strip %d' % (code, M5))
        fl.setdefault(code, []).append({'rms_raw': rms, 'meas_m5': T.summ(m, 'rms')})
        P('code %2d: TEST_MEAS strip %d %.2f dBFS; raw rms strip %d %.2f, 16 %.2f, 20 %.2f; loudest other %s'
          % (code, M5, T.summ(m, 'rms'), M5, rms[M5], rms[16], rms[20],
             max(((rms[s], s) for s in rms if s != M5 and rms[s] is not None))))
    out['floors'] = fl
    chain(IMAGE_AS_FOUND)

# 6. S55's detections re-read through the part's own tables
xc = {}
for x, lane in S55_LANES.items():
    s = D.strip(x)
    xc[x] = {'s55_lane': lane, 'rx_then': e_old[lane - 1], 'strip_now': s, 'rx_now': e_new[s - 1],
             'panel': D.BY_XLR[x].panel, 'ok': e_old[lane - 1] == e_new[s - 1] == D.BY_XLR[x].rx and s == D.BY_XLR[x].panel}
out['s55_crosscheck'] = xc
P('S55 cross-check (XLR: S55 lane -> rx -> strip now): ' + ', '.join('%s %d->%d->%d%s' % (
    x, v['s55_lane'], v['rx_then'], v['strip_now'], '' if v['ok'] else ' FAIL') for x, v in xc.items()))

# 7. hand back
restore(M5, savedM5)
R.meas(M5)
R.wv(T.A_OSCCHAN, st['osc_chan'])
out['handback'] = {'osc_on': R.rd(T.A_OSCON), 'osc_chan': R.rd(T.A_OSCCHAN), 'meas': R.rd(T.A_MEASCHAN),
                   'strip6': strip_keys(6) == saved6, 'strip%d' % M5: strip_keys(M5) == savedM5,
                   'entry_is_new': entries() == inverse(D.D24_INPUT_PATCH), 'an_en': an_en()}
T.log({'ev': 's58_result', **{k: v for k, v in out.items()}})
json.dump(out, open(HOME + '/s58_prove.json', 'w'), indent=1, default=str)
P('HANDBACK %s' % out['handback'])
