#!/usr/bin/env python3
"""s89_signbit.py <symdir> [nwords] -- DOES THE INTER-CHIP LINK CARRY THE SIGN BIT?

Needs no stimulus, no routing and no strip setup, and it covers all three
inter-chip lanes separately, because S89-1 is PER LANE.

  lane 0 (SPORT 0, entries 0..15)   MAIN L / MAIN R -- live from the summed mic
                                    lane noise, because a fresh boot leaves every
                                    strip at MainOn=1. Noise crosses zero.
  lane 1 (SPORT 1, entries 16..31)  the two codec return lanes -- live from the
                                    AK4619's own dither whenever the rails are up.

Compares chip 1's inter-chip TX ring with chip 2's inter-chip RX ring.

  CLEAN  chip 2 sees about as many negative words as chip 1 sent.
  FOLDED chip 2 sees none: received = sent & 0x7FFFFFFF (S89-1).
"""
import json, sys
_A = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR = _A[0]
NW = int(_A[1]) if len(_A) > 1 else 32

# A LINK THAT WILL NOT ANSWER IS NOT A FOLDED LINK. Without this, any
# exception here (most often "cannot phase the parameter link", which is the
# CS_M/U2 defect: GPIO27 comes back from a Pi reboot as `ip pd` and enables U2
# on MISO) exits 1 and reads to the caller as FOLDED. The boot wrapper then
# rebooted the pair six times against a fault a one-line pinctrl fixes.
# That one line is `op dh`, not `ip pu`, since S109: the pull no longer holds
# the pin against whatever sinks it, so it has to be DRIVEN high.
def _unreadable(msg):
    print('CANNOT READ THE PART: %s' % msg)
    print('  If this is "cannot phase the parameter link", try:  '
          'sudo pinctrl set 27 op dh')
    sys.exit(2)
GROUPS = (('lane 0 (SPORT 0)  MAIN L/R', (0, 1)),
          ('lane 1 (SPORT 1)  codec ret', (25, 26)))
res = {}
for chip in (1, 2):
    try:
        sc = S.Scope(chip, symfile='%s/chip%d.sym.json' % (SYMDIR, chip))
        sc.d.resync(); sc.check_chip()
    except Exception as e:
        _unreadable(e)
    syms = json.load(open('%s/chip%d.sym.json' % (SYMDIR, chip)))
    if 'symbols' in syms: syms = syms['symbols']
    def A(n):
        v = syms[n]
        return int(v, 0) if isinstance(v, str) else v
    if chip == 1:
        act, offt, strt = '_ic_tx_active_buf', '_c1_ic_tx_off', '_c1_ic_tx_stride'
    else:
        act, offt, strt = '_ic_rx_active_buf', '_c2_ic_rx_off', '_c2_ic_rx_stride'
    base = sc.peek(A(act))
    for label, ents in GROUPS:
        neg = tot = 0
        seen = set()
        for e in ents:
            off = sc.peek(A(offt) + e); st = sc.peek(A(strt) + e)
            ws = [sc.peek(base + off + (k % 16) * st) & 0xFFFFFFFF for k in range(NW)]
            neg += sum(1 for w in ws if w & 0x80000000)
            tot += len(ws); seen |= set(ws)
        res[(chip, label)] = (neg, tot, len(seen))

verdicts = []
for label, _ in GROUPS:
    s_neg, s_tot, s_dis = res[(1, label)]
    r_neg, r_tot, r_dis = res[(2, label)]
    print('  %-28s  sent bit31 %3d/%3d (distinct %2d)   received bit31 %3d/%3d (distinct %2d)'
          % (label, s_neg, s_tot, s_dis, r_neg, r_tot, r_dis))
    if s_dis < 4 or s_neg == 0:
        v = 'INCONCLUSIVE'
    elif r_neg == 0:
        v = 'FOLDED'
    elif r_neg >= s_neg // 2:
        v = 'CLEAN'
    else:
        v = 'PARTIAL'
    verdicts.append((label, v))
for label, v in verdicts:
    print('  VERDICT %-28s %s' % (label, v))
overall = ('FOLDED' if any(v == 'FOLDED' for _, v in verdicts)
           else ('INCONCLUSIVE' if all(v == 'INCONCLUSIVE' for _, v in verdicts)
                 else 'CLEAN'))
print('OVERALL: %s' % overall)
# EXIT CODE IS THE GATE. 0 clean, 1 folded, 2 nothing to judge on -- so a boot
# script can retry on 1 and refuse to measure on 2.
sys.exit({'CLEAN': 0, 'FOLDED': 1}.get(overall, 2))
