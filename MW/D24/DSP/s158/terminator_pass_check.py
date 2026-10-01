#!/usr/bin/env python3
"""terminator_pass_check.py -- S158: the 150 ohm pass, replayed on what the
bench recorded, and the three faults of 2026-10-01 reproduced.

    python3 terminator_pass_check.py        every case, ok/FAIL per check

No unit, no bus, no write. The REAL `Station.detect` runs on a virtual clock
against node-RMS readings fed at the times they were taken:

  1. THE FAULTS, REPRODUCED on the runner MW-D24-2 ran this morning (S157,
     f87002c8) and shown gone on this tree:
       a. P13 MIC 1 graded the OPEN input -- a lead wiggle made a second
          "lead in" plateau, so pulling the lead was taken for the whole swap;
       b. P15 MIC 2 / P17 MIC 3 never arrived -- the plug is 1.8 dB under the
          open input there and the rule wanted 3;
       c. P16 NO SIGNAL "after 0.7 s" -- a press left in command.json from
          P15 was spent on the next prompt.
  2. THE 24 INSERTIONS PW MADE (data/k5-trace-2026-10-01.csv), cut to the
     150 ohm pass's shape -- the socket open at the prompt -- graded on the
     plug, at the plug, on the terminated level.
  3. MIC 1 OPEN FOR 20 s (data/mic1-open-2026-10-01.csv), spikes and all:
     never graded.
  4. S153's PHYSICAL MODEL (48 kHz noise, pops, contact crackle, 4096-sample
     windows) in the pass shape, every surveyed channel x three hand speeds.
  5. The old per-input shape (the tone lead in the socket at the prompt): ENTER
     only, the lead-still-in question asked once.
  6. Presses: one answers the screen it was pressed on; PAUSE always counts.
  7. The lock: a run is refused while the factory glass's lock is held.
  8. The pass order and its screen: the 150 ohm pass is one block after the
     input walk, and every one of its screens carries ENTER.
"""
import csv
import importlib.util
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
TOOLS = os.path.join(ROOT, 'tools', 'pi')
sys.path.insert(0, TOOLS)
os.environ.setdefault('MATRIX_ADDR_HOME',
                      os.path.join(ROOT, 'MW', 'D24', 'DSP', 's138b',
                                   'fixtures'))
import d24_live as LV       # noqa: E402
import d24_patch as NEW     # noqa: E402

LIST_DIR = os.path.join(ROOT, 'MW', 'D24', 'DSP', 's121')
DATA = os.path.join(HERE, 'data')
S157_REV = 'f87002c8'          # the runner MW-D24-2 ran on 2026-10-01
FAILS = []


def check(name, cond, detail=''):
    print('%-4s %s%s' % ('ok' if cond else 'FAIL', name,
                         (': ' + str(detail)) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


def load_rev(rev, name):
    src = subprocess.check_output(
        ['git', '-C', ROOT, 'show', '%s:tools/pi/d24_patch.py' % rev])
    d = tempfile.mkdtemp(prefix='s158-%s-' % rev)
    p = os.path.join(d, name + '.py')
    with open(p, 'wb') as fh:
        fh.write(src)
    spec = importlib.util.spec_from_file_location(name, p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


OLD = load_rev(S157_REV, 'd24_patch_s157')


# ---------------------------------------------------------------------------
# The station, on a virtual clock, reading a list of (t, dBFS)
# ---------------------------------------------------------------------------
class Glass(object):
    def post(self, kind, title, lines, buttons, **extra):
        return list(buttons)

    def poll(self, btns):
        return None

    def ask(self, kind, title, lines, buttons, **extra):
        return dict(button=buttons[0])

    def clear(self):
        pass

    def progress(self, text):
        pass


def build(P):
    P.CLOCK = P.VirtualClock()
    plist = P.PatchList(LIST_DIR)
    world = P.World()
    glass = Glass()
    unit = P.SimUnit(world)
    send_pos = dict((int(r['lane']), int(r['send_pos'])) for r in plist.paths
                    if r.get('send_pos') != '' and str(r['lane']).isdigit())
    an = P.SimAnalog(world, plist.gain, send_pos)
    an.image = [0x00] * 24 + [0x00]
    an.safe_image = [0x01] * 24 + [0x00]
    live = LV.Live(tempfile.mkdtemp(prefix='s158-live-'), run='patch',
                   enabled=True, confirm=False)
    logs = []
    st = P.Station(plist, unit,
                   P.SimPatcher(glass, world, 0.0, lambda s: None, auto=True,
                                press_s=None),
                   glass, P.Limits.load(plist.dir), log=logs.append,
                   live=live, analog=an, auto_advance=True)
    return st, logs


def noise_rows(st, mic):
    for pid, rows in st.L.patches:
        if rows[0]['expect'] == 'noise' and int(rows[0]['lane']) == mic:
            return rows
    raise AssertionError('no noise patch for MIC %d' % mic)


class Feed(object):
    """`watch` answered from a recorded trace: each poll waits for the next
    reading's own time and returns it, so the detector sees the readings at
    the cadence the node delivered them. Past the end the last value repeats
    every 0.18 s (the bench cadence). `presses` = {seconds: command}."""

    def __init__(self, P, trace, presses=None, give_up=45.0):
        self.P, self.trace = P, list(trace)
        self.i = 0
        self.presses = sorted((presses or {}).items())
        self.give_up = give_up

    def watch(self, _lane, rms=False, settle=0):
        P = self.P
        t = P.now() - self.t0
        if self.i < len(self.trace):
            tt, v = self.trace[self.i]
            self.i += 1
            if tt > t:
                P.nap(tt - t)
            return v
        P.nap(0.18)
        return self.trace[-1][1]

    def command(self):
        t = self.P.now() - self.t0
        if t > self.give_up:
            return 'pause'
        if self.presses and t >= self.presses[0][0]:
            return self.presses.pop(0)[1]
        return None


def run(P, mic, trace, presses=None, give_up=45.0, lead_in=False):
    """One noise step through the real detect(): (how, seconds, logs, st)."""
    st, logs = build(P)
    rows = noise_rows(st, mic)
    f = Feed(P, trace, presses, give_up)
    st.watch = f.watch
    st.u.meter_sweep = lambda strips: {}
    st.live.command = f.command
    if lead_in:
        # what `announce` records when the patch before had the tone lead in
        # this same socket -- the old per-input order
        st._prev_in, st._prev_tone = rows[0]['in'], True
    st.u.mark_moved()
    f.t0 = P.now()
    prep = dict(lane=mic, freq=None, level=None, floor=-116.0, watch=None,
                sweep0={})
    how, ans, dt = st.detect(rows, prep, None)
    if how == 'glass' and (ans or {}).get('button') == 'pause':
        how = 'waiting'
    return how, dt, logs, st


def load_traces(name):
    out = {}
    with open(os.path.join(DATA, name)) as fh:
        rows = [ln for ln in fh if not ln.startswith('#')]
    for r in csv.DictReader(rows):
        out.setdefault(r['patch'], []).append((float(r['t_s']),
                                               float(r['rms_dbfs'])))
    return out


def med3(v, i):
    return statistics.median(x[1] for x in v[max(0, i - 2):i + 1])


def to_pass_shape(v):
    """Cut a lead-in/out/plug trace to the 150 ohm pass's shape: start where
    the lane is OPEN -- the first median-of-three 3 dB under the prompt
    reading, plus three readings for the pull's own transient -- and re-time
    it from there. Returns (trace, plug_t, open_db, term_db) where plug_t is
    the first reading of the insertion (the burst, or the first reading
    halfway down to the terminated level)."""
    lead = v[0][1]
    if lead > -65.0:                # a tone lead at the prompt (-29..-58)
        i0 = next(i for i in range(2, len(v)) if med3(v, i) <= lead - 3.0) + 3
    else:                           # already open at the prompt (P15, MIC 2)
        i0 = 0
    cut = v[i0:]
    t0 = cut[0][0]
    cut = [(round(t - t0 + 0.2, 3), x) for t, x in cut]
    term = statistics.median(x for _t, x in cut[-3:])   # the trace ends
    # three readings after the old detector's own arrival
    opn = statistics.median(x for _t, x in cut[:6])
    plug = None
    for t, x in cut[3:]:
        if x >= opn + 10.0 or x <= (opn + term) / 2.0 and opn - term >= 3.0:
            plug = t
            break
    if plug is None:
        plug = next(t for i, (t, x) in enumerate(cut) if i >= 3
                    and med3(cut, i) <= opn - 1.0)
    return cut, plug, opn, term


# ---------------------------------------------------------------------------
# 1. the faults of 2026-10-01, reproduced and gone
# ---------------------------------------------------------------------------
def case_false_pass_mic1():
    """P13, 10:5x: plateaus "-52.1 -> -52.1 -> -76.5", ARRIVED at -76.9 --
    the OPEN input (MIC 1 terminated is -87.0). The shape: the tone lead in
    at the prompt, a wiggle of it, the lead in again, then pulled -- and the
    plug not yet fitted."""
    tr, t = [], 0.0
    for v in ([-52.1] * 14 + [-63.5, -40.0] + [-52.1] * 6 + [-68.8]
              + [-77.0, -76.5, -77.2, -78.6, -76.9, -77.3] * 30):
        tr.append((round(t, 3), v))
        t += 0.18
    how, dt, logs, _st = run(OLD, 1, tr, give_up=30.0)
    check('1a REPRODUCED on S157 (%s): a lead wiggle then a pull, no plug -- '
          'graded on the open input' % S157_REV, how == 'drop',
          (how, [ln for ln in logs if 'ARRIVED' in ln or 'plateau' in ln][:3]))
    how2, _dt2, logs2, _s2 = run(NEW, 1, tr, give_up=30.0, lead_in=True)
    check('1a GONE: the same trace in the per-input order is never graded '
          '(that step is ENTER only now)', how2 == 'waiting',
          (how2, logs2[-3:]))
    opn = [(round(0.18 * i, 3), v) for i, v in enumerate(
        [-77.0, -76.5, -77.2, -78.6, -76.9, -77.3] * 160)]
    how3, _dt3, logs3, _s3 = run(NEW, 1, opn, give_up=150.0)
    check('1a GONE: the open input alone, in the pass shape, is never graded',
          how3 == 'waiting', (how3, logs3[-3:]))


def case_small_step_never_arrived():
    """P15 MIC 2 and P17 MIC 3: the plug WAS fitted (PW, addendum 1); the
    lane fell 1.8 dB, under the 3 dB rule. Today's own P15 trace is already
    the pass shape -- MIC 2 was open at its prompt."""
    tr = load_traces('k5-trace-2026-10-01.csv')
    p15 = tr['P15']
    how, dt, logs, _st = run(OLD, 2, p15, give_up=40.0)
    check('1b REPRODUCED on S157: MIC 2, plug in at 6.3 s, a 1.8 dB step -- '
          'never arrives', how == 'waiting', (how, dt))
    how2, dt2, logs2, _s2 = run(NEW, 2, p15, give_up=40.0)
    check('1b GONE: MIC 2 grades on the plug (insertion at 6.3 s)',
          how2 == 'drop' and 6.3 <= dt2 < 8.0, (how2, dt2, logs2[-2:]))
    cut, plug, opn, term = to_pass_shape(tr['P17'])
    how3, _d3, _l3, _s3 = run(OLD, 3, tr['P17'], give_up=40.0)
    check('1b REPRODUCED on S157: MIC 3 (open -76.3 -> -78.1) never arrives',
          how3 == 'waiting', how3)
    how4, dt4, logs4, _s4 = run(NEW, 3, cut, give_up=40.0)
    check('1b GONE: MIC 3 grades on the plug (%.1f s, step %.1f dB)'
          % (plug, opn - term), how4 == 'drop' and plug <= dt4 < plug + 2.0,
          (how4, dt4, logs4[-2:]))


def case_carried_over_press():
    """P16 NO SIGNAL "after 0.7 s": the operator's LEADS CORRECT on P15 was
    taken, and a second tap was still in command.json when P16's prompt went
    up."""
    tmp = tempfile.mkdtemp(prefix='s158-cmd-')
    live = LV.Live(tmp, run='patch', enabled=True, confirm=False)
    live.set(state=LV.CHECKLEAD, instruction='Patch AUX 1 to MIC 2.')
    tap = time.time()
    press(live, 'nosignal', stamp=tap)
    check('1c the first tap answers the screen it was pressed on',
          live.command() == 'nosignal')
    press(live, 'nosignal', stamp=time.time())      # the second tap
    time.sleep(0.05)                                # recording, chain, route
    live.set(state=LV.WAITING, instruction='Patch AUX 1 to MIC 3.')
    check('1c GONE: the second tap, left in the file, is dropped by the next '
          'prompt', live.command() is None)
    press(live, 'nosignal', stamp=time.time())
    check('... a press made on the new screen is taken',
          live.command() == 'nosignal')
    # the old runner took it: what S157's Live did with the same file
    import d24_live_s157 as OLDLV                       # noqa: E402
    old = OLDLV.Live(tempfile.mkdtemp(prefix='s158-cmd-old-'), run='patch',
                     enabled=True, confirm=False)
    old.set(state=LV.CHECKLEAD, instruction='Patch AUX 1 to MIC 2.')
    press(old, 'nosignal', stamp=time.time())
    old.command()
    press(old, 'nosignal', stamp=time.time())
    old.set(state=LV.WAITING, instruction='Patch AUX 1 to MIC 3.')
    check('1c REPRODUCED on S157\'s d24_live: the next prompt spends it',
          old.command() == 'nosignal')


def press(live, button, stamp=None, screen=None):
    d = dict(command=button, stamp=time.time() if stamp is None else stamp)
    if screen is not None:
        d['screen'] = screen
    with open(os.path.join(live.dir, LV.COMMAND_NAME), 'w') as fh:
        json.dump(d, fh)


# ---------------------------------------------------------------------------
# 2./3. the bench's own readings
# ---------------------------------------------------------------------------
def case_the_24_insertions():
    tr = load_traces('k5-trace-2026-10-01.csv')
    order = sorted(tr, key=lambda p: int(p[1:]))
    late, rows = [], []
    for k, pid in enumerate(order):
        mic = k + 1
        cut, plug, opn, term = to_pass_shape(tr[pid])
        how, dt, logs, st = run(NEW, mic, cut, give_up=max(40.0, plug + 20))
        after = dt - plug
        rows.append((mic, opn, term, opn - term, plug, how, dt, after))
        ok = how == 'drop' and 0.0 <= after < 3.0
        if ok:
            late.append(after)
        check('MIC %-2d open %.1f -> %.1f (%.1f dB), plug at %.1f s: graded '
              'on the plug, %.2f s after it' % (mic, opn, term, opn - term,
                                               plug, after), ok,
              (how, dt, [ln for ln in logs if 'ARRIV' in ln or 'insert'
                         in ln or 'something' in ln][:3]))
    if late:
        check('24/24 graded on the plug; median %.2f s after it, worst %.2f s'
              % (statistics.median(late), max(late)), len(late) == 24,
              '%d of 24' % len(late))
    return rows


def case_mic1_open_20s():
    tr = load_traces('mic1-open-2026-10-01.csv')['P13']
    cut = [(t, v) for t, v in tr if t >= 1.1]          # after the pull
    t0 = cut[0][0]
    cut = [(t - t0 + 0.2, v) for t, v in cut]
    # play it three times over: a minute of an open input
    span = cut[-1][0] + 0.18
    long = [(t + k * span, v) for k in range(3) for t, v in cut]
    how, dt, logs, _st = run(NEW, 1, long, give_up=55.0)
    check('MIC 1 OPEN, nothing fitted, a minute of its own spikes: never '
          'graded', how == 'waiting', (how, dt, logs[-3:]))


# ---------------------------------------------------------------------------
# 4. S153's physical model, in the pass shape
# ---------------------------------------------------------------------------
def case_physical_model():
    spec = importlib.util.spec_from_file_location(
        's153_model', os.path.join(HERE, '..', 's153', 'noise_step_check.py'))
    M = importlib.util.module_from_spec(spec)
    import contextlib
    import io
    with contextlib.redirect_stdout(io.StringIO()):
        spec.loader.exec_module(M)
    opn = M.s125_open()
    got, n, seed = [], 0, 1580
    for mic in sorted(M.S55_TERM):
        if mic not in opn:
            continue
        j, node, cap = M.S55_TERM[mic]
        for plug in (1.5, 3.0, 8.0):
            seed += 1
            # the socket is open at the prompt: the "lead" level IS the open
            # input, and there is no pull
            lane = M.Lane(opn[mic], node, None, plug, seed, dur=45.0,
                          lead_db=opn[mic])
            k = 0.0
            tr = []
            while k < 44.0:
                k += lane.win_s
                tr.append((round(k, 4), lane.rms(k)))
            how, dt, logs, _st = run(NEW, mic, tr, give_up=40.0)
            n += 1
            if how == 'drop' and dt >= plug:
                got.append(dt - plug)
            elif how == 'drop':
                check('model MIC %d (open %.1f, T4 %.1f), plug %.1f s: graded '
                      'BEFORE the plug' % (mic, opn[mic], node, plug), False,
                      dt)
    check('S153 model, pass shape: %d of %d steps graded on the plug, median '
          '%.2f s after it, worst %.2f s'
          % (len(got), n, statistics.median(got) if got else -1,
             max(got) if got else -1), len(got) == n,
          '%d of %d' % (len(got), n))


# ---------------------------------------------------------------------------
# 5. the old per-input shape: ENTER only
# ---------------------------------------------------------------------------
def case_lead_in_shape_is_enter_only():
    tr = load_traces('k5-trace-2026-10-01.csv')['P13']      # MIC 1, whole
    how, dt, logs, _st = run(NEW, 1, tr, give_up=60.0, lead_in=True)
    check('per-input order (tone lead in at the prompt): never auto-graded, '
          'even through a real pull and plug', how == 'waiting', (how, dt))
    how2, dt2, logs2, st2 = run(NEW, 1, tr, presses={40.0: 'enter'},
                                give_up=60.0, lead_in=True)
    check('... ENTER after the swap measures it', how2 == 'press'
          and 40.0 <= dt2 < 41.0, (how2, dt2))
    lead = [(round(0.18 * i, 3), -53.8) for i in range(300)]
    how3, dt3, logs3, st3 = run(NEW, 1, lead, presses={5.0: 'enter'},
                                give_up=15.0, lead_in=True)
    d = json.load(open(os.path.join(st3.live.dir, LV.LIVE_NAME)))
    check('... ENTER with the lead still in is asked once more, not measured',
          how3 == 'waiting' and 'still reads as if the tone lead'
          in (d.get('status') or ''), (how3, d.get('status')))
    how4, dt4, _l4, _s4 = run(NEW, 1, lead, presses={5.0: 'enter',
                                                     8.0: 'enter'},
                              give_up=30.0, lead_in=True)
    check('... and the second ENTER measures it (the operator has looked)',
          how4 == 'press' and 8.0 <= dt4 < 9.0, (how4, dt4))


# ---------------------------------------------------------------------------
# 6. presses
# ---------------------------------------------------------------------------
def case_presses():
    tmp = tempfile.mkdtemp(prefix='s158-press-')
    live = LV.Live(tmp, run='patch', enabled=True, confirm=False)
    live.wait_buttons = LV.TERMINATOR_BUTTONS        # as `announce` sets it
    live.set(state=LV.WAITING, instruction='Fit the 150 ohm terminator in '
             'MIC 1.')
    s1 = live.screen
    check('live.json carries the screen number the app echoes',
          json.load(open(live.path)).get('screen') == s1)
    press(live, 'enter', screen=s1)
    check('an app that echoes `screen` is taken on that screen',
          live.command() == 'enter')
    live.set(state=LV.WAITING, status='something else')        # same screen
    press(live, 'enter', screen=s1)
    check('... a status change is not a new screen',
          live.command() == 'enter')
    live.set(state=LV.WAITING, instruction='Fit the 150 ohm terminator in '
             'MIC 2.', buttons=['enter', 'pause'])
    press(live, 'enter', screen=s1)
    check('... and is dropped once the next instruction is up',
          live.command() is None)
    time.sleep(0.05)
    press(live, 'pause', stamp=live.t0 + 0.001)      # as old as a run allows
    check('PAUSE is never dropped, however old', live.command() == 'pause')
    press(live, 'enter', stamp=live.screen_t + 0.05)
    check('an app with no `screen` is held to its stamp: a fresh press counts',
          live.command() == 'enter')


# ---------------------------------------------------------------------------
# 7. the lock
# ---------------------------------------------------------------------------
def case_unit_lock():
    glass = tempfile.mkdtemp(prefix='s158-glass-')
    scratch = tempfile.mkdtemp(prefix='s158-scratch-')
    other = subprocess.Popen(['sleep', '60'])        # RUN ALL, standing in
    with open(os.path.join(glass, NEW.RunLock.NAME), 'w') as fh:
        json.dump(dict(pid=other.pid, stamp='2026-10-01T10:15:34Z',
                       argv=['d24_patch.py', '--run']), fh)
    import contextlib
    import io
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = NEW.main(['--patch-only', '--block', 'K5', '--list-dir', LIST_DIR,
                       '--dir', scratch, '--live', glass, '--no-keyboard'])
    check('a bench run into a scratch dir is refused while the glass lock is '
          'held (2026-10-01 11:15)', rc == 2 and 'refused' in out.getvalue(),
          (rc, out.getvalue()[-300:]))
    check('... and it left the scratch dir unlocked',
          not os.path.exists(os.path.join(scratch, NEW.RunLock.NAME)))
    other.kill()
    other.wait()


# ---------------------------------------------------------------------------
# 8. the order and the screen
# ---------------------------------------------------------------------------
def case_order_and_screens():
    plist = NEW.PatchList(LIST_DIR)
    blocks = [(lead, block, [p for p, _r in ps])
              for (lead, block), ps in plist.blocks()]
    names = [b for _l, b, _p in blocks]
    check('the 150 ohm pass is a block of its own',
          'the 150 ohm pass' in names, names)
    k5 = [b for b in blocks if b[1] == 'the 150 ohm pass'][0]
    check('... of 24 patches, one per input', len(k5[2]) == 24, len(k5[2]))
    i_in = names.index('the inputs')
    check('... straight after the input walk', names[i_in + 1] ==
          'the 150 ohm pass', names)
    inputs = [b for b in blocks if b[1] == 'the inputs'][0]
    leads = {r[0]['lead'] for pid, r in plist.patches if pid in inputs[2]}
    check('... and the input walk carries no terminator step any more',
          leads == {'K1'}, leads)
    seen = []
    orig = LV.Live._flush

    def flush(self):
        orig(self)
        seen.append(dict(self.d))
    LV.Live._flush = flush
    import contextlib
    import io
    tmp = tempfile.mkdtemp(prefix='s158-pass-')
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            NEW.main(['--simulate', '--list-dir', LIST_DIR, '--live', tmp,
                      '--dir', tmp])
    finally:
        LV.Live._flush = orig
    tw = [d for d in seen if 'terminator' in (d.get('instruction') or '')
          and d.get('state') == LV.WAITING]
    check('every 150 ohm waiting screen of a whole simulated pass carries '
          'ENTER', tw and all('enter' in d['buttons'] for d in tw),
          sorted({tuple(d['buttons']) for d in tw}))
    other = [d for d in seen if 'terminator' not in (d.get('instruction')
                                                     or '')
             and d.get('state') == LV.WAITING and 'enter' in d['buttons']]
    check('... and no other waiting screen does', not other,
          [(d.get('instruction'), d['buttons']) for d in other[:3]])
    extra = {d.get('extra') for d in tw}
    check('... the line under it says where the plug comes from',
          any('Move it from MIC 1' in (e or '') for e in extra), extra)


def main():
    # S157's d24_live, for 1c's reproduction
    src = subprocess.check_output(
        ['git', '-C', ROOT, 'show', '%s:tools/pi/d24_live.py' % S157_REV])
    d = tempfile.mkdtemp(prefix='s158-lv-')
    with open(os.path.join(d, 'd24_live_s157.py'), 'wb') as fh:
        fh.write(src)
    sys.path.insert(0, d)
    for name, fn in (('1a', case_false_pass_mic1),
                     ('1b', case_small_step_never_arrived),
                     ('1c', case_carried_over_press),
                     ('2', case_the_24_insertions),
                     ('3', case_mic1_open_20s),
                     ('4', case_physical_model),
                     ('5', case_lead_in_shape_is_enter_only),
                     ('6', case_presses),
                     ('7', case_unit_lock),
                     ('8', case_order_and_screens)):
        print('-- %s %s' % (name, fn.__name__))
        fn()
    print()
    if FAILS:
        print('%d check(s) FAILED' % len(FAILS))
        return 1
    print('all checks passed -- no unit, no bus, no write, no rails')
    return 0


if __name__ == '__main__':
    sys.exit(main())
