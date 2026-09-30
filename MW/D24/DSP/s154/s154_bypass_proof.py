#!/usr/bin/env python3
"""s154_bypass_proof.py SYMDIR [LISTDIR] -- the S154 patch-test bypass, proved on the unit.

Uses the station's OWN code (d24_patch.Station.bypass_capture/_restore and the
list's standing + `_standing_bypass` rows): reads every bypass cell, writes the
standing route and the bypass, puts TEST_OSC on strip 24 into MAIN and AUX 1
at unity, reads the TX slots hard left and hard right at -12 and -6 dBFS
(PW: MAIN L/R must match AUX within 0.5 dB at the same send), then restores
and reads every bypass cell back against what was found.
"""
import math, os, random, sys, time, types
SYMDIR = sys.argv[1]
LIST = sys.argv[2] if len(sys.argv) > 2 else '/home/app/selftest/s121'
HERE = os.path.dirname(os.path.abspath(__file__))
sys.argv = ['s']
# This file's own directory FIRST, so a proof staged beside a new d24_patch.py
# runs that one and not the deployed station's.
sys.path.insert(0, '/home/app/selftest'); sys.path.insert(0, '/home/app/dspboot')
sys.path.insert(0, HERE)
import d24_patch as PT

u = PT.Unit(symdir=SYMDIR)
u.bypass_state = '/home/app/selftest/s154-bypass-proof-found.json'
L = PT.PatchList(LIST)
st = types.SimpleNamespace(L=L, u=u, log=print)
for m in ('bypass_capture', 'bypass_restore'):
    setattr(st, m, types.MethodType(getattr(PT.Station, m), st))
sc2 = u.chip(2)

def s32(w):
    w &= 0xFFFFFFFF
    return w - (1 << 32) if w & 0x80000000 else w

def peak_db(node, reps=400):
    addr = sc2.sym['_tx_out_slot_' + node]; pk = 0.0
    for _ in range(reps):
        time.sleep(random.uniform(0, 0.0015))
        try:
            pk = max(pk, abs(s32(sc2.peek(addr + random.randrange(32)))) / 2.0 ** 28)
        except IOError:
            pass
    return 20 * math.log10(pk) if pk > 0 else -999.0

specs = st.bypass_capture()
found = dict(st._bypass_found)
bad = u.write(L.standing() + specs)
bad += u.write(['Chan024MainOn001=1', 'Chan024CtrOn001=0', 'Chan024AuxOn001=1',
                'Chan024AuxSend001=f1.0', 'Chan024AuxPick001=3'])
print('standing %d + bypass %d written, %d did not read back %s'
      % (len(L.standing()), len(specs), len(bad), bad[:6]))
worst = 0.0
for pan, leg in ((0.0, 'C2_MAIN_OUT_01'), (1.0, 'C2_MAIN_OUT_02')):
    u.write(['Chan024Pan001=f%g' % pan])
    for lv in (-12.0, -6.0):
        u.osc(chan=24, freq=1000.0, level_dbfs=lv, on=True)
        time.sleep(1.2)
        a, m = peak_db('C2_AUX_OUT_01'), peak_db(leg)
        worst = max(worst, abs(m - a))
        print('pan %.0f osc %5.1f  AUX_OUT_01 %7.2f  %s %7.2f  MAIN-AUX %+.2f dB'
              % (pan, lv, a, leg[3:], m, m - a))
print('WORST |MAIN-AUX| %.2f dB -> %s (PW: within 0.5 dB)'
      % (worst, 'PASS' if worst <= 0.5 else 'FAIL'))
u.osc(on=False)
rb = st.bypass_restore()
back = dict((n, u.read(n) & 0xFFFFFFFF) for n in found)
diff = [n for n in found if back[n] != found[n]]
print('restore: %d cells, %d differ from the value found %s; record removed: %s'
      % (len(found), len(diff), diff[:6], not os.path.exists(u.bypass_state)))
print('found non-zero (the product settings the bypass took out and put back):')
nz = sorted(n for n, w in found.items() if w)
print('  ' + ' '.join('%s=0x%X' % (n, found[n]) for n in nz))
