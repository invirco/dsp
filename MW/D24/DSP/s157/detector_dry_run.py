#!/usr/bin/env python3
"""detector_dry_run.py -- S157 item 4: the patch station's detector, replayed
against the operator behaviours that broke it, on a simulator that has the
two properties the old detector tripped over.

    python3 detector_dry_run.py            every case, ok/FAIL per check

THE SIMULATOR (`TrueUnit`) is SimUnit plus what the bench showed:
  * the strip PEAK meter is a peak-hold LATCH that drains at 6.5 dB/s (S153),
    and an idle lane's peak reads well over its RMS floor (MIC 1: 14 dB,
    S155's model of P1; MIC 15's RMS floor is -75.5 dBFS);
  * the measurement node reads the lane NOW: RMS is tone plus noise, and the
    COHERENT level (the fit against the oscillator) is the tone alone --
    noise shows on it about 30 dB down;
  * a lane can carry a RESIDUAL for a while (the gain-63 open-input noise the
    150 ohm step leaves, -54 dBFS RMS);
  * more than one lead can be in the unit at once (a lead left in).

THE OPERATOR (`Hands`) is a script per prompt: plug fresh at t, move only the
output end at t, plug the wrong socket then move it, leave the last lead in,
never come back, press RETRY / LEADS CORRECT / PAUSE at t.

Every case runs the REAL `Station` -- `detect`, `one_patch`, `find_loop`,
`confirm_graded` -- on a virtual clock, behind a REAL `Live` whose files the
checks read back.
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, '..', '..', '..', '..', 'tools', 'pi')
sys.path.insert(0, TOOLS)
os.environ.setdefault('MATRIX_ADDR_HOME',
                      os.path.abspath(os.path.join(HERE, '..', 's138b',
                                                   'fixtures')))
import d24_live as LV        # noqa: E402
import d24_panel as PL       # noqa: E402
import d24_patch as PT       # noqa: E402

LIST_DIR = os.path.abspath(os.path.join(HERE, '..', 's121'))
FAILS = []
FORBIDDEN = ('other end', 'stays', 'park', 'leave the lead')


def check(name, cond, detail=''):
    print('%-4s %s%s' % ('ok' if cond else 'FAIL', name,
                         (': ' + str(detail)) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


# ---------------------------------------------------------------------------
# The unit, as the bench found it
# ---------------------------------------------------------------------------
LATCH_DB_PER_S = 6.52
RMS_FLOOR = {1: -101.1, 3: -101.4, 15: -75.5, 24: -101.7}
PEAK_GAP = {1: 14.0, 3: 5.0}          # idle peak over idle RMS, per lane
TONE_LOSS_DB = 3.0 + 1.4 - 1.4        # the loop's own gain: the -12 osc reads
                                      # about -15 (World.level's convention)


def drive_key(drive):
    d = str(drive or '')
    if d.startswith('aux:'):
        return ['aux%d' % int(x) for x in d[4:].split('+')]
    if d.startswith('main'):
        return ['main']
    if d.startswith('ctr'):
        return ['ctr']
    return []


class TrueUnit(PT.SimUnit):
    def __init__(self, world):
        PT.SimUnit.__init__(self, world)
        self.plugs = []                 # [(drive, lanes, in_name, lead)]
        self.dead_out = set()           # drives that carry nothing
        self.residual = {}              # lane -> (rms dBFS, until t)
        self.latch = {}                 # lane -> (dB, t)
        self.low = {}                   # drive -> dB lost on that output

    # -- what is on a lane -----------------------------------------------
    def floor_of(self, lane):
        return RMS_FLOOR.get(lane, -100.5)

    def tone_db(self, lane):
        if not self.osc_on or lane == self.osc_chan:
            return None
        drv = set(self.driven())
        for d, lanes, _in, _lead in self.plugs:
            if lane in lanes and set(drive_key(d)) & drv \
                    and d not in self.dead_out:
                return (self.osc_level - TONE_LOSS_DB - self.low.get(d, 0.0)
                        + self.w.preamp_db(lane))
        return None

    def noise_db(self, lane):
        n = self.floor_of(lane)
        r = self.residual.get(lane)
        if r and PT.now() < r[1]:
            n = 10 * PT.math.log10(10 ** (n / 10) + 10 ** (r[0] / 10))
        return n

    def level_at(self, lane):
        if self.osc_on and lane == self.osc_chan:
            return self.osc_level
        if not self.osc_on:
            return PT.SimUnit.level_at(self, lane)   # the noise rows' model
        t = self.tone_db(lane)
        return t if t is not None else self.noise_db(lane)

    # -- the node ----------------------------------------------------------
    def measure(self, freq, level_dbfs, windows=PT.READ_WINDOWS,
                settle=PT.SETTLE_WINDOWS):
        out = PT.SimUnit.measure(self, freq, level_dbfs, windows, settle)
        if not self.osc_on:
            return out
        lane = self.lane
        t = self.tone_db(lane)
        n = self.noise_db(lane)
        if t is None:
            out['rms'] = n
            out['coh_dbfs'] = n - 30.0         # noise barely fits a sine
            out['h_db'] = out['coh_dbfs'] - (level_dbfs or 0.0)
        else:
            out['rms'] = 10 * PT.math.log10(10 ** (t / 10) + 10 ** (n / 10))
            out['coh_dbfs'] = t
        return out

    # -- the peak-hold latch -------------------------------------------------
    def meter_peak(self, strip):
        PT.nap(PT.PEEK_S)
        t = self.tone_db(strip) if self.osc_on else None
        inst = (t + 3.0) if t is not None else \
            self.noise_db(strip) + PEAK_GAP.get(strip, 3.0)
        if self.osc_on and strip == self.osc_chan:
            inst = self.osc_level + 3.0
        now = PT.now()
        held = self.latch.get(strip)
        if held is not None:
            held_now = held[0] - LATCH_DB_PER_S * (now - held[1])
        else:
            held_now = -300.0
        if inst >= held_now:
            self.latch[strip] = (inst, now)
            v = inst
        else:
            v = held_now
        return 10 ** (v / 20.0)

    def seed_latch(self, strip, db):
        self.latch[strip] = (db, PT.now())


# ---------------------------------------------------------------------------
# The operator
# ---------------------------------------------------------------------------
class Hands(PT.ManualPatcher):
    """A script per prompt. `plan[pid]` is a list of (seconds after the
    prompt, action, args) run in order, once per prompt of that patch; the
    SAME pid prompted again (RETRY) runs `plan2[pid]` if given."""

    def __init__(self, glass, unit, log):
        PT.ManualPatcher.__init__(self, glass, auto=True)
        self.u, self.log = unit, log
        self.plan, self.plan2 = {}, {}
        self.queue = []
        self.prompts = []
        self.seen = {}
        self.decisions = []

    def connect(self, patch, rows, glass):
        tok = PT.ManualPatcher.connect(self, patch, rows, glass)
        t0 = PT.now()
        n = self.seen.get(patch, 0)
        self.seen[patch] = n + 1
        self.prompts.append((patch, rows[0]['in'], rows[0].get('out'), t0))
        plan = (self.plan2.get(patch) if n and patch in self.plan2
                else self.plan.get(patch, ()))
        self.queue = [(t0 + dt, what, args, patch, rows) for dt, what, args
                      in plan]
        return tok

    def _do(self, what, args, patch, rows):
        r = rows[0]
        lanes = sorted({int(x['lane']) for x in rows})
        if what == 'unplug':
            self.u.plugs = [p for p in self.u.plugs if p[2] != args]
        elif what == 'clear':
            self.u.plugs = []
            self.u.w.unplug()
        elif what == 'plug':            # this patch, fresh
            self.u.plugs.append((r['drive'], lanes, r['in'], r['lead']))
            self.u.w.plug(r['out'], r['in'], lanes, r['lead'])
        elif what == 'plug_into':       # this patch's output, another socket
            name, lane = args
            self.u.plugs.append((r['drive'], [lane], name, r['lead']))
            self.u.w.plug(r['out'], name, [lane], r['lead'])
        elif what == 'move_out':        # only the output end moves
            self.u.plugs = [p for p in self.u.plugs if p[2] != r['in']]
            self.u.plugs.append((r['drive'], lanes, r['in'], r['lead']))
            self.u.w.plug(r['out'], r['in'], lanes, r['lead'])
        elif what == 'press':
            self.decisions.append((PT.now(), args))
            return dict(button=args, reason='')
        return None

    def poll(self, token):
        now = PT.now()
        while self.queue and self.queue[0][0] <= now:
            _t, what, args, patch, rows = self.queue.pop(0)
            ans = self._do(what, args, patch, rows)
            if ans is not None:
                return ans
        return None

    def decide(self, what):
        # the graded-fail screen reads presses from here (and the glass)
        ans = self.poll(None)
        return ans.get('button') if ans else None

    def done(self, token):
        pass


class Glass(object):
    def __init__(self):
        self.posts = []

    def post(self, kind, title, lines, buttons, **extra):
        self.posts.append(dict(kind=kind, title=title, lines=list(lines),
                               buttons=list(buttons)))
        return list(buttons)

    def poll(self, btns):
        return None

    def ask(self, kind, title, lines, buttons, **extra):
        self.post(kind, title, lines, buttons, **extra)
        return dict(button=buttons[0])

    def clear(self):
        pass

    def progress(self, text):
        pass


def build():
    PT.CLOCK = PT.VirtualClock()
    plist = PT.PatchList(LIST_DIR)
    world = PT.World()
    glass = Glass()
    unit = TrueUnit(world)
    send_pos = dict((int(r['lane']), int(r['send_pos'])) for r in plist.paths
                    if r.get('send_pos') != '' and str(r['lane']).isdigit())
    an = PT.SimAnalog(world, plist.gain, send_pos)
    an.image = [0x00] * 24 + [0x00]
    an.safe_image = [0x01] * 24 + [0x00]
    tmp = tempfile.mkdtemp(prefix='s157-')
    live = LV.Live(tmp, run='patch', enabled=True, confirm=False)
    logs = []
    hands = Hands(glass, unit, logs.append)
    st = PT.Station(plist, unit, hands, glass, PT.Limits.load(plist.dir),
                    log=logs.append, live=live, analog=an, auto_advance=True)
    st.measure_floors()
    screens = []
    orig = live._flush

    def flush():
        orig()
        d = dict(live.d)
        d['_t'] = PT.now()
        screens.append(d)
    live._flush = flush
    return st, hands, unit, live, logs, screens


def rows_of(st, pid):
    for p, rows in st.L.patches:
        if p == pid:
            return st.rebind(rows)
    raise KeyError(pid)


def one(st, pid, rows=None):
    """One patch through the real `one_patch`, prompted fresh."""
    rows = rows or rows_of(st, pid)
    seq = [(('K1', 'the outputs'), [(pid, rows)])]
    t0 = PT.now()
    got = st.one_patch(pid, rows, 'K1', 'the outputs', seq, 0, 0)
    return got, PT.now() - t0


def verdict_of(st, pid):
    v = [r['verdict'] for r in st.rows_out if r['patch'] == pid]
    return v


def logged(logs, *words):
    return [l for l in logs if all(w in l for w in words)]


# ---------------------------------------------------------------------------
# The cases
# ---------------------------------------------------------------------------
def case_fresh_socket_fast_and_slow():
    for hand in (0.5, 1.0, 2.0, 5.0, 10.0):
        st, h, u, live, logs, _sc = build()
        h.plan['P2'] = [(0.0, 'clear', None), (hand, 'plug', None)]
        got, dt = one(st, 'P2')
        v = verdict_of(st, 'P2')
        check('fresh socket, lead in at %.1f s: PASS, no stall' % hand,
              v == ['PASS'] and not logged(logs, 'FAILED'),
              (v, [l for l in logs if 'P2' in l][:6]))
        arr = logged(logs, 'P2 ARRIVED')
        check('... it arrived after the plug, not before (%.1f s)' % hand,
              arr and dt >= hand, (dt, arr))


def case_output_end_swap_1s_and_5s():
    """P6's shape with nothing parked: the previous lead AUX 1 -> MIC 1 is
    still in; the operator moves ONLY the output end to AUX 2. The MIC end
    never leaves, the peak latch on MIC 1 is still full of the old tone --
    and none of that is looked at."""
    for hand in (1.0, 5.0, 0.3):
        st, h, u, live, logs, _sc = build()
        u.plugs = [('aux:1', [1], 'MIC 1', 'K1')]
        u.w.plug('AUX 1', 'MIC 1', [1], 'K1')
        u.seed_latch(1, -4.6)
        h.plan['P2'] = [(hand, 'move_out', None)]
        got, dt = one(st, 'P2')
        check('output-end swap in %.1f s: PASS' % hand,
              verdict_of(st, 'P2') == ['PASS'] and not logged(logs, 'FAILED'),
              [l for l in logs if 'P2' in l][:6])
        check('... graded after the swap (%.1f s)' % hand, dt >= hand, dt)


def case_noise_to_tone_residual():
    """P56's face: the lane still carries the gain-63 residual (-54 dBFS RMS)
    when the prompt goes up; the lead goes in 1 s later. Must PASS, at the
    plug, not before -- the residual is noise and the coherent level sees
    through it."""
    for hand in (1.0, 3.0):
        st, h, u, live, logs, _sc = build()
        u.residual[2] = (-54.0, PT.now() + 6.0)
        u.seed_latch(2, -50.0)
        h.plan['P14'] = [(0.0, 'clear', None), (hand, 'plug', None)]
        got, dt = one(st, 'P14')
        prompted = logged(logs, 'P14 PROMPTED')
        check('noise->tone, residual -54 dBFS on the lane, plug at %.1f s: '
              'PASS' % hand, verdict_of(st, 'P14')
              and set(verdict_of(st, 'P14')) == {'PASS'},
              (verdict_of(st, 'P14'), [l for l in logs if 'P14' in l][:6]))
        arr = logged(logs, 'P14 ARRIVED')
        check('... the residual did not arrive; the lead did (%.1f s)' % hand,
              arr and not logged(logs, 'P14 ARRIVING', 'level -8')[:0]
              and dt >= hand, (dt, prompted, arr))


def case_terminator_swap_speeds():
    """The 150 ohm step, the one same-socket repeat left: the tone lead is
    in MIC 1 when the prompt goes up; the operator pulls it at once (0.2 s)
    and fits the plug 0.5 / 1 / 5 s later. The prompt's own node reading is
    the "lead in" state, so a pull right after the prompt still shows both
    steps (S157 fix; the dry run found it at --hand 1)."""
    for gap in (0.5, 1.0, 5.0):
        st, h, u, live, logs, _sc = build()
        rows = rows_of(st, 'P13')
        u.plugs = [('aux:1', [1], 'MIC 1', 'K1')]
        u.w.plug('AUX 1', 'MIC 1', [1], 'K1')
        h.plan['P13'] = [(0.2, 'clear', None), (0.2 + gap, 'plug', None)]
        got, dt = one(st, 'P13', rows)
        check('terminator: lead out at 0.2 s, plug %.1f s later: graded on '
              'the plug' % gap, verdict_of(st, 'P13') == ['PASS']
              and dt >= 0.2 + gap and not logged(logs, 'P13 FAILED'),
              (verdict_of(st, 'P13'), dt, [l for l in logs if 'P13' in l][:6]))
    st, h, u, live, logs, _sc = build()
    rows = rows_of(st, 'P13')
    u.plugs = [('aux:1', [1], 'MIC 1', 'K1')]
    u.w.plug('AUX 1', 'MIC 1', [1], 'K1')
    h.plan['P13'] = [(0.5, 'clear', None), (60.0, 'press', 'nosignal')]
    got, dt = one(st, 'P13', rows)
    check('terminator: lead pulled, nothing fitted -- never graded; it stops '
          'and waits for the operator', dt >= 60.0
          and logged(logs, 'P13 FAILED'), dt)


def case_wrong_socket_named_then_moved():
    st, h, u, live, logs, sc = build()
    h.plan['P14'] = [(0.0, 'clear', None), (1.0, 'plug_into', ('MIC 3', 3)),
                     (6.0, 'clear', None), (6.5, 'plug', None)]
    got, dt = one(st, 'P14')
    w = logged(logs, 'P14 WRONG_SOCKET', 'MIC 3')
    check('a lead in the wrong socket is named (MIC 3, expected MIC 2)', w,
          [l for l in logs if 'P14' in l][:8])
    named = [d for d in sc if d.get('status')
             == LV.status_wrong_input('MIC 3', 'MIC 2')]
    check('... on the glass, in PW\'s shape', named)
    check('... nothing was graded while it was there, and it PASSES once '
          'moved', set(verdict_of(st, 'P14')) == {'PASS'} and dt >= 6.5,
          (verdict_of(st, 'P14'), dt))


def case_lead_left_in():
    """The last patch's lead is left in MIC 2 while MIC 3 is asked for. AUX 1
    still carries the tone, so MIC 2 reads it STEADY: named, never graded as
    MIC 3; moved at 5 s, MIC 3 passes."""
    st, h, u, live, logs, sc = build()
    u.plugs = [('aux:1', [2], 'MIC 2', 'K1')]
    u.w.plug('AUX 1', 'MIC 2', [2], 'K1')
    h.plan['P16'] = [(5.0, 'clear', None), (5.5, 'plug', None)]
    got, dt = one(st, 'P16')
    check('a lead left in MIC 2 is named while MIC 3 is asked for',
          logged(logs, 'P16 WRONG_SOCKET', 'MIC 2'),
          [l for l in logs if 'P16' in l][:6])
    check('... and MIC 3 is graded only after the lead moved',
          set(verdict_of(st, 'P16')) == {'PASS'} and dt >= 5.5,
          (verdict_of(st, 'P16'), dt))


def case_draining_latch_is_never_a_claim():
    """P1's "MIC 15" and P7's "MIC 23": a latch that is only draining (the
    last patch's lane, a noisy floor) is never named, however loud it
    starts."""
    st, h, u, live, logs, sc = build()
    u.seed_latch(15, -4.0)
    u.seed_latch(23, -7.6)
    h.plan['P14'] = [(0.0, 'clear', None), (8.0, 'plug', None)]
    got, dt = one(st, 'P14')
    check('two draining latches, 8 s of waiting: no wrong-socket claim',
          not logged(logs, 'WRONG_SOCKET'),
          logged(logs, 'WRONG_SOCKET'))
    check('... and the patch passes at the plug',
          set(verdict_of(st, 'P14')) == {'PASS'} and dt >= 8.0)


def case_p1_idle_mic1():
    """S155 item 1: MIC 1 idle, its peak 14 dB over its RMS floor, nothing in
    the socket until the operator plugs it after the prompt."""
    st, h, u, live, logs, sc = build()
    h.plan['P2'] = [(0.0, 'clear', None), (2.0, 'plug', None)]
    got, dt = one(st, 'P2')
    check('idle MIC 1 (14 dB peak/RMS gap), plugged at 2 s: PASS at the plug',
          verdict_of(st, 'P2') == ['PASS'] and 2.0 <= dt < 4.0, dt)


def case_dead_output_fails_and_stops():
    st, h, u, live, logs, sc = build()
    u.dead_out.add('aux:2')
    h.plan['P2'] = [(0.0, 'clear', None), (1.0, 'plug', None),
                    (95.0, 'press', 'nosignal')]
    got, dt = one(st, 'P2')
    failed = logged(logs, 'P2 FAILED')
    check('a dead output raises the FAILED screen at the timeout', failed)
    during = [d for d in sc if d['state'] == LV.CHECKLEAD]
    check('... and STOPS: nothing recorded before the operator answered',
          dt >= 95.0, dt)
    check('... the FAILED screen carries LEADS CORRECT, RETRY and PAUSE',
          during and all(d['buttons'] == ['nosignal', 'retry', 'pause']
                         for d in during if d['state'] == LV.CHECKLEAD),
          sorted({tuple(d['buttons']) for d in during}))
    check('... LEADS CORRECT records FAIL "no signal detected"',
          verdict_of(st, 'P2') == ['FAIL']
          and st.rows_out[-1]['why'] == LV.NO_SIGNAL_FAIL)
    check('... and the confirmation is listed', st.confirmed
          and st.confirmed[-1]['answer'] == 'LEADS CORRECT', st.confirmed)


def case_timeout_waits_then_still_arrives():
    st, h, u, live, logs, sc = build()
    h.plan['P2'] = [(0.0, 'clear', None), (125.0, 'plug', None)]
    got, dt = one(st, 'P2')
    check('nobody for 125 s: the step waited (no give-up at 2 x 20 s) and '
          'the late lead still PASSES', verdict_of(st, 'P2') == ['PASS']
          and dt >= 125.0, (verdict_of(st, 'P2'), dt))
    check('... it raised the question once, at 20 s',
          len(logged(logs, 'P2 FAILED')) == 1)


def case_retry_button_reprompts():
    st, h, u, live, logs, sc = build()
    h.plan['P2'] = [(0.0, 'clear', None), (25.0, 'press', 'retry')]
    h.plan2['P2'] = [(1.0, 'plug', None)]
    got, dt = one(st, 'P2')
    check('RETRY on the FAILED screen prompts the same patch again',
          h.seen.get('P2') == 2 and logged(logs, 'P2 RETRY'), h.seen)
    check('... and the retried patch passes', verdict_of(st, 'P2') == ['PASS'])


def case_graded_fail_stops():
    """A patch that ARRIVES and does not pass (a TRS pair with tip and ring
    crossed) stops on its FAILED screen. RETRY by hand -- the lead out for
    1 s and back -- runs it again; LEADS CORRECT then records it."""
    st, h, u, live, logs, sc = build()
    u.w.faults.add('swap:AUX A 1-2')
    st.ref_in = ('MIC 1', 1)
    rows = rows_of(st, 'P63')
    h.plan['P63'] = [(0.0, 'clear', None), (1.0, 'plug', None),
                     (8.0, 'clear', None)]
    h.plan2['P63'] = [(1.0, 'plug', None), (40.0, 'press', 'nosignal')]
    seq = [(('K2', 'the TRS outputs'), [('P63', rows)])]
    t0 = PT.now()
    st.one_patch('P63', rows, 'K2', 'the TRS outputs', seq, 0, 0)
    dt = PT.now() - t0
    check('a graded FAIL stops on its FAILED screen',
          logged(logs, 'P63 FAILED'), [l for l in logs if 'P63' in l][:8])
    check('... the lead out for 1 s is a retry by hand, from the prompt',
          logged(logs, 'P63 RETRY', 'came out') and h.seen.get('P63') == 2,
          h.seen)
    check('... nothing recorded until LEADS CORRECT, 40 s into the retry',
          dt >= 40.0 and 'FAIL' in verdict_of(st, 'P63'),
          (dt, verdict_of(st, 'P63')))
    check('... and the record says the operator confirmed it',
          any('LEADS CORRECT' in (r.get('detail') or '')
              for r in st.rows_out if r['verdict'] == 'FAIL'))


def case_find_loop_waits_for_the_operator():
    st, h, u, live, logs, sc = build()
    u.dead_out.add('aux:1')         # AUX 1 -> MIC 1 cannot work ...
    rows = rows_of(st, 'P1')
    # ... the operator plugs it, then answers LEADS CORRECT at 100 s
    h.plan['P1'] = [(0.0, 'clear', None), (1.0, 'plug', None),
                    (100.0, 'press', 'nosignal')]
    t0 = PT.now()
    found = st.find_loop('P1', rows)
    first = [p for p in h.prompts if p[0] == 'P1']
    check('P1 dead: the walk did NOT move to MIC 2 by itself (100 s)',
          len(first) >= 2 and first[1][3] - t0 >= 100.0,
          [(p[1], round(p[3] - t0, 1)) for p in first[:3]])
    check('... it moved after LEADS CORRECT, and says so in the log',
          logged(logs, 'P1: AUX 1 into MIC 1', 'LEADS CORRECT'))
    check('... the confirmation is listed', st.confirmed
          and 'finding a working loop' in st.confirmed[0]['failure'])


def case_no_forbidden_words_anywhere():
    """PW ~19:40: no prompt may say "other end", "stays", "park" or "leave the
    lead". Every screen and every dialog line of a whole dry run, faults and
    all, and every setup page."""
    import contextlib
    import io
    seen = []
    orig = LV.Live._flush

    def flush(self):
        orig(self)
        seen.append(dict(self.d))
    LV.Live._flush = flush
    posts = []
    orig_post = PT.SimGlass.post

    def post(self, kind, title, lines, buttons, **extra):
        posts.append(' '.join([title] + list(lines)))
        return orig_post(self, kind, title, lines, buttons, **extra)
    PT.SimGlass.post = post
    tmp = tempfile.mkdtemp(prefix='s157-words-')
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            PT.main(['--simulate', '--hand', '2', '--live', tmp,
                     '--fault', 'mispatch:MIC 7', '--fault', 'dead:MIC 5'])
    finally:
        LV.Live._flush = orig
        PT.SimGlass.post = orig_post
    texts = []
    for d in seen:
        for k in ('instruction', 'lead_line', 'extra', 'status', 'action',
                  'banner', 'banner_line'):
            if d.get(k):
                texts.append(d[k])
    texts += posts
    texts += [p['instruction'] for p in PT.setup_pages(PT.PatchList(LIST_DIR))]
    bad = sorted({t for t in texts for w in FORBIDDEN if w in t.lower()})
    check('%d screen lines, %d dialog posts and the setup pages: none says '
          '%s' % (len(seen), len(posts), ' / '.join(repr(w)
                                                    for w in FORBIDDEN)),
          texts and not bad, bad[:6])
    instr = sorted({d['instruction'] for d in seen if d.get('state')
                    == LV.WAITING and d.get('instruction')
                    and 'Pick up' not in d['instruction']})
    plain = [t for t in instr if not (t.startswith('Patch ')
                                      or t.startswith('Fit the 150 ohm'))
             and 'bench' not in t and 'USB' not in t
             and 'network' not in t]
    check('every patch prompt is the plain "Patch <out> to <in>." or "Fit the '
          '150 ohm terminator in <in>."', not plain, plain[:5])
    check('the only kit page puts the leads on the bench',
          [p['instruction'] for p in PT.setup_pages(PT.PatchList(LIST_DIR))
           if p['key'].startswith('kit')] == [LV.bench_kit_page()])


def case_panel_step_stops():
    """The switch panels (every station of RUN ALL): a press that never comes
    and a wrong key both stop on the step and ask; NO lights it again, YES
    records."""
    class Bus(object):
        def __init__(self, script):
            self.script = list(script)
            self.lit = []

        def light(self, idx, cells=None):
            self.lit.append(idx)
            return 1.0

        def wait_key(self, timeout, tick=None):
            return self.script.pop(0) if self.script else None

    side = 'right'
    first = PL.Step(*PL.PANELS[side][0])
    other = PL.PANELS[side][1][0]
    asked = []

    def ask(st, n, total):
        return lambda: None

    def confirm(st, why):
        asked.append((st.name, why))
        return 'retry' if len(asked) == 1 else 'record'
    # step 1: timeout, NO (retry), then the right key; step 2: wrong key,
    # YES (record). Only the first two steps are owed.
    owed = {first.sw_row, first.led_row, PL.PANELS[side][1][2],
            PL.PANELS[side][1][3]}
    bus = Bus([None, ('skin', first.idx, 30.0), ('skin', 99, 30.0)])
    steps, _x = PL.loop(bus, side, ask, timeout=30.0, log=lambda s: None,
                        owed=owed, confirm=confirm)
    s1, s2 = steps[0], steps[1]
    check('panel: a press that never came stops and asks',
          asked and 'no key code' in asked[0][1], asked)
    check('... NO lights it again (lit twice) and the retried press PASSES',
          bus.lit.count(first.idx) == 2 and s1.sw == 'PASS',
          (bus.lit, s1.sw, s1.sw_note))
    check('... a wrong key stops and asks too, and YES records the FAIL',
          len(asked) == 2 and s2.sw == 'FAIL'
          and 'recorded by the operator' in s2.sw_note, (asked, s2.sw_note))
    check('panel words: the stopped step names the failure plainly',
          LV.panel_fail_wrong_key('MONO AUX', 'FX MUTE')
          == 'The panel sent FX MUTE, not MONO AUX.')


def case_row94_says_why():
    line = LV.nodata_words('the temperature sense', LV.NODATA_PANEL_FIRMWARE)
    check('row 94 NO DATA on the glass, one line in panel words',
          line == 'The temperature sense: the panel firmware does not send '
                  'it yet.' and LV.fits(line), line)
    src = open(os.path.join(TOOLS, 'd24_runall.py')).read()
    check('... and the panel station puts it up for every NO DATA sense row',
          'LV.nodata_words(what_of.get(num' in src
          and 'NODATA_SAY_S' in src)


def main():
    for fn in (case_fresh_socket_fast_and_slow,
               case_output_end_swap_1s_and_5s,
               case_noise_to_tone_residual,
               case_terminator_swap_speeds,
               case_wrong_socket_named_then_moved,
               case_lead_left_in,
               case_draining_latch_is_never_a_claim,
               case_p1_idle_mic1,
               case_dead_output_fails_and_stops,
               case_timeout_waits_then_still_arrives,
               case_retry_button_reprompts,
               case_graded_fail_stops,
               case_find_loop_waits_for_the_operator,
               case_no_forbidden_words_anywhere,
               case_panel_step_stops,
               case_row94_says_why):
        print('-- %s' % fn.__name__)
        fn()
    print()
    if FAILS:
        print('%d check(s) FAILED' % len(FAILS))
        return 1
    print('all checks passed -- no unit, no bus, no write, no rails')
    return 0


if __name__ == '__main__':
    sys.exit(main())
