#!/usr/bin/env python3
"""S163: a named WRONG_PAIR parks the screen. Reuses the S159 TRS model."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 's159'))
sys.argv = [sys.argv[0]]
import trs_dry_run as T          # noqa: E402
PT, LV, DR = T.PT, T.LV, T.DR
check = T.check


def parked_run(after):
    out = []
    for s in after:
        if s['state'] != LV.CHECKLEAD:
            break
        out.append(s)
    return out


def named_at(logs, pid):
    return [l for l in logs if '%s WRONG_PAIR' % pid in l]


for pid, (jack, _) in sorted(T.JACK.items()):
    # reversed order: this jack carries the opposite pair; press LEADS CORRECT late
    st, h, u, logs, screens = T.build(T.REVERSED)
    h.plan[pid] = [(0.0, 'clear', None), (2.0, 'plugjack', jack),
                   (120.0, 'press', 'nosignal')]
    T.run_patch(st, pid)
    n = named_at(logs, pid)
    if not n:     # a palindromic pair (none today) would not be wrong
        check('%s names a pair' % pid, False, logs[-5:])
        continue
    i = next(k for k, s in enumerate(screens) if 'This jack carries' in str(s.get('status')))
    after = screens[i:]
    states = {s['state'] for s in after}
    check('%s: after naming, the glass never leaves CHECKLEAD (no ARRIVING/WAITING flicker)' % pid,
          [s['state'] for s in after].count(LV.CHECKLEAD) == len(parked_run(after))
          and not {LV.WAITING, 'arriving'} & states, sorted(states))
    parked = [s for s in after if s['state'] == LV.CHECKLEAD]
    check('%s: the parked screen is one stable text, buttons LEADS CORRECT/RETRY/PAUSE' % pid,
          len({(s['status'], s['action']) for s in parked}) == 1
          and all(s['buttons'] == ['nosignal', 'retry', 'pause'] for s in parked),
          sorted({tuple(s['buttons']) for s in parked}))
    check('%s: named once, then no further probing or ARRIVING lines' % pid,
          len(n) == 1 and not [l for l in logs if ('%s ARRIVING' % pid) in l and logs.index(l) > logs.index(n[0])],
          len(n))
    rec = [r for r in st.rows_out if r['patch'] == pid]
    check('%s: LEADS CORRECT records FAIL with the jack-order finding on all sub-tests' % pid,
          rec and all(r['verdict'] == 'FAIL' and 'wiring/label order' in r['why']
                      and 'no signal' not in r['why'] for r in rec),
          [(r['verdict'], r['why']) for r in rec])

# a lead moved by hand does nothing until RETRY (never auto-loops)
st, h, u, logs, screens = T.build(T.REVERSED)
h.plan['P63'] = [(0.0, 'clear', None), (2.0, 'plugjack', 'AUX A 1-2'),
                 (30.0, 'plugjack', 'AUX A 7-8'), (60.0, 'press', 'nosignal')]
T.run_patch(st, 'P63')
check('moved lead without RETRY: still parked, records the FAIL (no auto-loop)',
      [r['verdict'] for r in st.rows_out if r['patch'] == 'P63'] == ['FAIL'] * 3
      and not any('P63 ARRIVED' in l for l in logs))
# mis-plugged lead: RETRY re-prompts cleanly and passes
st, h, u, logs, screens = T.build(T.REVERSED)
h.plan['P63'] = [(0.0, 'clear', None), (2.0, 'plugjack', 'AUX A 1-2'), (45.0, 'press', 'retry')]
h.plan2['P63'] = [(0.0, 'clear', None), (1.0, 'plugjack', 'AUX A 7-8')]
T.run_patch(st, 'P63')
check('RETRY re-prompts and the corrected lead passes',
      h.seen.get('P63') == 2 and T.subs(st, 'P63') == {'L': 'PASS', 'R': 'PASS', 'null': 'PASS'}, h.seen)
# labelled jacks unaffected
st, h, u, logs, screens = T.build(T.LABELLED)
h.plan['P63'] = [(0.0, 'clear', None), (2.0, 'plugjack', 'AUX A 1-2')]
T.run_patch(st, 'P63')
check('labelled jacks: no WRONG_PAIR, passes', not named_at(logs, 'P63')
      and T.subs(st, 'P63') == {'L': 'PASS', 'R': 'PASS', 'null': 'PASS'})
print()
if T.FAILS:
    print('%d check(s) FAILED' % len(T.FAILS)); sys.exit(1)
print('all checks passed -- no unit, no bus, no write, no rails')
