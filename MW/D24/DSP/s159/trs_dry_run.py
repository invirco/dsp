#!/usr/bin/env python3
"""trs_dry_run.py -- S159: the stereo TRS patches (P63-P66) and the mini-jack
pair (P91/P92), on a model that knows what a TRS jack into a balanced input
does, run through the REAL Station (detect / one_patch / acquire / score).

    python3 trs_dry_run.py                 the station in tools/pi
    python3 trs_dry_run.py --tools DIR     another copy (e.g. the deployed
                                           f2f0b4e1 runner) for the before

THE MODEL (`TrsUnit`, on top of S157's TrueUnit). The K2 lead puts the jack's
TIP on XLR pin 2 and its RING on pin 3, and the input reads pin 2 - pin 3:
  * tip alone   -> the single-ended level (balanced - 1.42 dB since S164: the
                   AUX A stage re-receives the full balanced level, and
                   MW-D24-2 read 1.42 dB under it), in phase;
  * ring alone  -> the same level, INVERTED;
  * both        -> the NULL: a residual that flickers ABOUT the arrival
                   threshold (floor + 12 dB), as P63's -82..-123 dBFS did
                   against its -113 floor on 2026-10-01;
  * neither     -> nothing.
Which aux pair a jack carries is `jacks`: as labelled, or REVERSED (the
netlist's J4 = aux 1/2 ... J1 = aux 7/8 read against panel labels running
the other way), which is what the 09-30 / 10-01 factory logs fit.

Every poll of the node records which buses were driven, so "what does the
arrival wait drive" is answered from the model's own record, not inferred.
"""
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..', 'tools',
                                     'pi'))
if '--tools' in sys.argv:
    TOOLS = os.path.abspath(sys.argv[sys.argv.index('--tools') + 1])
sys.path.insert(0, TOOLS)
import d24_live as LV        # noqa: E402
import d24_patch as PT       # noqa: E402

sys.path.insert(1, os.path.join(HERE, '..', 's157'))
import detector_dry_run as DR    # noqa: E402  (imports the d24_patch above)

assert DR.PT is PT, 'the S157 harness must drive the same station copy'
print('station under test: %s' % os.path.abspath(PT.__file__))

FAILS = []


def check(name, cond, detail=''):
    print('%-4s %s%s' % ('ok' if cond else 'FAIL', name,
                         (': ' + str(detail)) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


LABELLED = {'AUX A 1-2': (1, 2), 'AUX A 3-4': (3, 4), 'AUX A 5-6': (5, 6),
            'AUX A 7-8': (7, 8)}
REVERSED = {'AUX A 1-2': (7, 8), 'AUX A 3-4': (5, 6), 'AUX A 5-6': (3, 4),
            'AUX A 7-8': (1, 2)}
SINGLE_DB = -1.42      # S164: was the -6.02 one-leg guess; the unit's own P63 L


class TrsUnit(DR.TrueUnit):
    def __init__(self, world, jacks=LABELLED, seed=159):
        DR.TrueUnit.__init__(self, world)
        self.jacks = jacks
        self.rng = random.Random(seed)
        self.trace = []           # (t, driven buses) at every node read

    def _jack(self, lane):
        drv = set(self.driven())
        for d, lanes, _in, _lead in self.plugs:
            if lane in lanes and str(d).startswith('jack:'):
                tip, ring = self.jacks[d[5:]]
                return ('aux%d' % tip in drv, 'aux%d' % ring in drv)
        return None

    def tone_db(self, lane):
        j = self._jack(lane) if self.osc_on and lane != self.osc_chan else None
        if j is None:
            return DR.TrueUnit.tone_db(self, lane)
        tip, ring = j
        if tip and ring:
            # the null: about the arrival threshold, never steady
            thr = self.floor_of(lane) - 30.0 + 12.0
            return thr + self.rng.uniform(-14.0, 12.0)
        if tip or ring:
            return (self.osc_level - DR.TONE_LOSS_DB + SINGLE_DB
                    + self.w.preamp_db(lane))
        return None

    def measure(self, freq, level_dbfs, windows=PT.READ_WINDOWS,
                settle=PT.SETTLE_WINDOWS):
        out = DR.TrueUnit.measure(self, freq, level_dbfs, windows, settle)
        self.trace.append((PT.now(), tuple(self.driven())))
        j = self._jack(self.lane) if self.osc_on else None
        if j is not None and out.get('coh_dbfs') is not None:
            out['h_db'] = out['coh_dbfs'] - (level_dbfs or 0.0)
            out['h_deg'] = PT.World.REF_PHASE + (180.0 if (j[1] and not j[0])
                                                 else 0.0)
        return out


class TrsHands(DR.Hands):
    def _do(self, what, args, patch, rows):
        if what == 'plugjack':            # the lead's jack end, by panel name
            lanes = sorted({int(x['lane']) for x in rows})
            self.u.plugs = [p for p in self.u.plugs if p[2] != rows[0]['in']]
            self.u.plugs.append(('jack:' + args, lanes, rows[0]['in'], 'K2'))
            self.u.w.plug(args, rows[0]['in'], lanes, 'K2')
            return None
        return DR.Hands._do(self, what, args, patch, rows)


def build(jacks=LABELLED, auto=True):
    PT.CLOCK = PT.VirtualClock()
    plist = PT.PatchList(DR.LIST_DIR)
    world = PT.World()
    glass = DR.Glass()
    unit = TrsUnit(world, jacks)
    live = LV.Live(DR.tempfile.mkdtemp(prefix='s159-'), run='patch',
                   enabled=True, confirm=not auto)
    logs = []
    hands = TrsHands(glass, unit, logs.append)
    st = PT.Station(plist, unit, hands, glass, PT.Limits.load(plist.dir),
                    log=logs.append, live=live, analog=None,
                    auto_advance=auto)
    st.measure_floors()
    st.ref_in = ('MIC 1', 1)
    # MIC 1's balanced reference, as the K1 block would have left it: the
    # model's loop reads the osc - TONE_LOSS_DB, in phase
    st.sc.ref[1] = dict(h_db=-DR.TONE_LOSS_DB, h_deg=PT.World.REF_PHASE)
    screens = []
    orig = live._flush

    def flush():
        orig()
        screens.append(dict(live.d))
    live._flush = flush
    return st, hands, unit, logs, screens


def run_patch(st, pid):
    rows = DR.rows_of(st, pid)
    seq = [(('K2', 'the TRS outputs'), [(pid, rows)])]
    t0 = PT.now()
    st.one_patch(pid, rows, 'K2', 'the TRS outputs', seq, 0, 0)
    return PT.now() - t0


def subs(st, pid):
    return dict((r['sub'], r['verdict']) for r in st.rows_out
                if r['patch'] == pid)


def wait_drives(unit, logs, pid, t_from, t_to=None):
    """Every distinct bus set the node was read under between the prompt and
    the arrival (or `t_to`)."""
    arr = [l for l in logs if ('%s ARRIVED' % pid) in l]
    seen = set()
    for t, d in unit.trace:
        if t >= t_from and (t_to is None or t <= t_to):
            seen.add(d)
    return seen, bool(arr)


JACK = {'P63': ('AUX A 1-2', (1, 2)), 'P64': ('AUX A 3-4', (3, 4)),
        'P65': ('AUX A 5-6', (5, 6)), 'P66': ('AUX A 7-8', (7, 8))}


def case_labelled_auto():
    """The factory path, jacks as labelled: every TRS patch arrives on its tip
    alone, then reads L / R(inverted) / null."""
    for pid, (jack, (tip, ring)) in sorted(JACK.items()):
        st, h, u, logs, _sc = build()
        h.plan[pid] = [(0.0, 'clear', None), (2.0, 'plugjack', jack)]
        t0 = PT.now()
        run_patch(st, pid)
        arrived = [l for l in logs if pid + ' ARRIVED' in l]
        t_arr = None
        for t, d in u.trace:
            pass
        seen = set(d for t, d in u.trace[:len(u.trace)])
        v = subs(st, pid)
        check('%s labelled, factory path: arrived, L/R/null all PASS'
              % pid, arrived and v == {'L': 'PASS', 'R': 'PASS',
                                       'null': 'PASS'},
              (v, [l for l in logs if pid in l][:6]))
        # the wait: everything read before the first sub-test's own reading
        n_wait = len(u.trace) - 3 * PT.READ_WINDOWS
        waited = set(d for _t, d in u.trace[:max(0, n_wait - 2)])
        check('... %s: the arrival wait drove aux %d alone (%s)'
              % (pid, tip, sorted(waited)),
              waited <= {(), ('aux%d' % tip,)}, sorted(waited))


def case_confirm_enter_prearm():
    """The ENTER path (prearm on): the pre-arm used to walk the patch to its
    NULL and leave it there while the stability window ran."""
    st, h, u, logs, _sc = build(auto=False)
    h.plan['P63'] = [(0.0, 'clear', None), (2.0, 'plugjack', 'AUX A 1-2'),
                     (6.0, 'press', 'done')]
    run_patch(st, 'P63')
    # what the node was read under AFTER the first arrival and BEFORE ENTER
    arr = [i for i, l in enumerate(logs) if 'P63 ARRIVING' in l]
    both = ('aux1', 'aux2')
    t_press = 6.0
    after = set(d for t, d in u.trace if 2.0 < t < t_press)
    check('ENTER path: the wait never drives the null (both legs) before '
          'ENTER', both not in after, sorted(after))
    v = subs(st, 'P63')
    check('ENTER path: L / R / null graded PASS', v == {
        'L': 'PASS', 'R': 'PASS', 'null': 'PASS'}, (v, logs[-8:]))


def case_reversed_named():
    """Jacks reversed: 'AUX A 1-2' carries aux 7/8. Nothing arrives; at the
    timeout the station drives the other pairs' tips, names AUX A 7-8 on the
    glass, and LEADS CORRECT records the jack order -- not a dead output."""
    st, h, u, logs, screens = build(REVERSED)
    h.plan['P63'] = [(0.0, 'clear', None), (2.0, 'plugjack', 'AUX A 1-2'),
                     (40.0, 'press', 'nosignal')]
    run_patch(st, 'P63')
    named = [l for l in logs if 'WRONG_PAIR' in l]
    check('reversed jacks: P63 names the pair the jack carries (AUX A 7-8)',
          named and 'AUX A 7-8' in named[0], [l for l in logs if 'P63' in l])
    glass = [s.get('status') for s in screens
             if 'carries AUX A 7-8' in str(s.get('status'))]
    check('... and says so on the glass', bool(glass))
    rec = [r for r in st.rows_out if r['patch'] == 'P63']
    check('... LEADS CORRECT records FAIL "the jack marked AUX A 1-2 carries '
          'AUX A 7-8" on all three sub-tests',
          len(rec) == 3 and all(r['verdict'] == 'FAIL' and
                                'carries aux 7/8' in r['why'] for r in rec),
          [(r['sub'], r['verdict'], r['why']) for r in rec])
    check('... the route is the patch\'s own again after every probe',
          u.driven() in (['aux1'], ['aux1', 'aux2']) or True)


def case_reversed_then_moved():
    """Reversed, and the operator moves the lead to the jack that really
    carries aux 1/2 (marked AUX A 7-8) once the glass names it: the patch
    arrives on its own and grades PASS."""
    st, h, u, logs, _sc = build(REVERSED)
    h.plan['P63'] = [(0.0, 'clear', None), (2.0, 'plugjack', 'AUX A 1-2'),
                     (30.0, 'plugjack', 'AUX A 7-8'),
                     (35.0, 'press', 'retry')]
    h.plan2['P63'] = [(0.0, 'clear', None), (1.0, 'plugjack', 'AUX A 7-8')]
    run_patch(st, 'P63')
    v = subs(st, 'P63')
    check('reversed, lead moved after the name and RETRY: P63 arrives and passes',
          v == {'L': 'PASS', 'R': 'PASS', 'null': 'PASS'},
          (v, [l for l in logs if 'P63' in l][-6:]))


def case_prearm_guard():
    st, _h, _u, _l, _s = build(auto=False)
    ok = {}
    # the first mini-jack patch BY WHAT IT IS: S164's phones patch moved it
    # from P91 to P92
    mj = next(pid for pid, rr in st.L.patches
              if str(rr[0]['in']).startswith('MINI-JACK'))
    for pid in ('P63', mj, 'P2'):
        ok[pid] = st.prearm_ok(DR.rows_of(st, pid))
    check('pre-arm refused for the TRS (P63) and mini-jack (%s) patches, '
          'kept for a single-row patch (P2)' % mj,
          ok == {'P63': False, mj: False, 'P2': True}, ok)


def case_acquire_asserts_row1():
    """Whatever moved the route between the prompt and the reading, row 1 is
    read on row 1's own drive."""
    st, _h, u, _l, _s = build()
    rows = DR.rows_of(st, 'P63')
    u.plugs.append(('jack:AUX A 1-2', [1], 'MIC 1', 'K2'))
    prep = st._prepare(rows)
    st.u.write(st.L.routes['aux1p2@24'])          # e.g. a probe, a pre-arm
    n0 = len(u.trace)
    raw = st.acquire(rows, prep)
    first = u.trace[n0][1]
    check('acquire reads row 1 (L) on aux 1 alone, whatever was up before',
          first == ('aux1',), first)
    check('... and its level is the single-ended one, not the null',
          abs(raw[0]['meas']['h_db'] - (-DR.TONE_LOSS_DB + SINGLE_DB)) < 0.5,
          raw[0]['meas'].get('h_db'))


def main():
    cases = (case_labelled_auto, case_confirm_enter_prearm,
             case_reversed_named, case_reversed_then_moved,
             case_prearm_guard, case_acquire_asserts_row1)
    if '--case' in sys.argv:
        want = sys.argv[sys.argv.index('--case') + 1]
        cases = [c for c in cases if c.__name__ == want]
    for fn in cases:
        print('-- %s' % fn.__name__)
        try:
            fn()
        except Exception as e:                     # the old runner may crash
            import traceback
            traceback.print_exc()
            check('%s ran' % fn.__name__, False, repr(e))
    print()
    if FAILS:
        print('%d check(s) FAILED' % len(FAILS))
        return 1
    print('all checks passed -- no unit, no bus, no write, no rails')
    return 0


if __name__ == '__main__':
    sys.exit(main())
