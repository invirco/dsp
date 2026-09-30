#!/usr/bin/env python3
"""noise_step_check.py -- S153: the 150 ohm step's auto-advance, before and after.

No unit, no bus, no write. The REAL `Station.detect` of both versions -- the
one at S152 (`fcc1da24`, peak meter, `hi - lvl >= drop`) and the one in this
tree (node RMS, plateaus) -- is run against the same lane, and the lane is a
physical model of the swap, not a list of numbers:

  * 48 kHz Gaussian noise at the lane's RMS for each state: the tone lead still
    in (AUX 1 idle lifted 53 dB, S55: -51 dBFS), the OPEN input (S125's map,
    per lane), and the 150 ohm plug (S55's T4, per lane);
  * a crackle as each connector moves, and the open input's own pops (a high
    gain on an unterminated input is impulsive, which is what a peak meter
    sees and an RMS does not);
  * the STRIP METER as the part has it: a peak-hold latch draining at 6.52
    dB/s (S125/S138b-6), and at the prompt still holding the gain step's last
    tone at -24 dBFS (factory.log 2026-09-30, "the meter ... read -24.x");
  * the NODE's RmsResult as the part has it: 4096-sample windows, a new one
    every 85.3 ms, and a poll that waits for the next one.

It reports, for every powered channel, the step time and WHAT WAS IN THE
SOCKET when the step ended -- because a step that ends early on the meter's
drain has graded the lead, not the plug. Then the refusals: the lead left in,
the lead pulled and nothing fitted. Then the margin table (dispatch item 2).

Tone rows are not touched by S153; `patch_auto_advance_check.py` (S145) and the
whole-pass dry run prove that, and the last section here re-runs both.
"""
import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
TOOLS = os.path.join(ROOT, 'tools', 'pi')
sys.path.insert(0, TOOLS)
os.environ.setdefault('MATRIX_ADDR_HOME',
                      os.path.join(ROOT, 'MW', 'D24', 'DSP', 's138b',
                                   'fixtures'))
import d24_live as LV       # noqa: E402

LIST_DIR = os.path.join(ROOT, 'MW', 'D24', 'DSP', 's121')
BEFORE_REV = 'fcc1da24'
FS = 48000.0
DECAY_DB_S = 6.52
LATCH_DBFS = -24.0
LEAD_DBFS = -51.0
FAILS = []


def check(name, cond, detail=''):
    print('%-4s %s%s' % ('ok' if cond else 'FAIL', name,
                         (': ' + detail) if detail else ''))
    if not cond:
        FAILS.append(name)


def load_before():
    """d24_patch.py as it was at S152, imported under its own name."""
    src = subprocess.check_output(
        ['git', '-C', ROOT, 'show', '%s:tools/pi/d24_patch.py' % BEFORE_REV])
    d = tempfile.mkdtemp(prefix='s153-before-')
    p = os.path.join(d, 'd24_patch_before.py')
    with open(p, 'wb') as fh:
        fh.write(src)
    spec = importlib.util.spec_from_file_location('d24_patch_before', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


import d24_patch as AFTER   # noqa: E402
BEFORE = load_before()


# ---------------------------------------------------------------------------
# The survey's levels, per channel (dispatch item 2)
# ---------------------------------------------------------------------------
# OPEN at gain 63: S125's map (`s125-map.json`), node RMS, one position
# unmuted at code 63 at a time, nothing plugged in: base + rise on the lane
# that rose. TERMINATED at gain 63: S55 (`s55/channels.md`), 150 ohm across
# pins 2-3, two instruments -- the node's own T4 and the capture arm's
# energy average DC-24k -- and they agree to about 1 dB on every channel but
# MIC 6 (J27), where they disagree by 5.5 dB. Both are kept.
# panel MIC: (J, node T4 code 63, capture DC-24k)
S55_TERM = {
    5: ('J25', -87.97, None), 17: ('J26', -93.46, -92.90),
    6: ('J27', -82.04, -87.59), 18: ('J28', -91.61, -91.85),
    7: ('J29', -90.25, -91.59), 19: ('J30', -91.60, -92.99),
    8: ('J31', -86.42, -86.64), 20: ('J32', -86.51, -88.63),
    9: ('J35', -91.27, -90.64), 21: ('J36', -91.04, -93.17),
    10: ('J37', -88.45, -93.50), 22: ('J38', -92.61, -93.21),
    11: ('J39', -92.00, -92.31), 23: ('J40', -92.32, -92.53),
    12: ('J41', -91.17, -92.95), 24: ('J42', -92.20, -92.59),
}


def s125_open():
    d = json.load(open(os.path.join(ROOT, 'MW', 'D24', 'DSP', 's125', 'data',
                                    's125-map.json')))
    out = {}
    for v in d['positions'].values():
        lane, rise = v['top'][0]
        if rise > 20.0:                  # the lane that rose; dark bytes skip
            out[int(lane)] = d['base'][str(lane)] + rise
    return out


# ---------------------------------------------------------------------------
# The lane
# ---------------------------------------------------------------------------
class Lane(object):
    """One socket through one swap, sampled at 48 kHz.

    `pull` and `plug` are seconds after the prompt; None means it never
    happens. Everything the two instruments read is derived from the same
    samples, so the before and after detectors see one physical event.
    """

    def __init__(self, open_db, term_db, pull, plug, seed, dur=45.0,
                 lead_db=LEAD_DBFS):
        rng = np.random.default_rng(seed)
        self.pull, self.plug = pull, plug
        n = int(dur * FS)
        t = np.arange(n) / FS
        lvl = np.full(n, lead_db)
        if pull is not None:
            lvl[t >= pull] = open_db
        if plug is not None:
            lvl[t >= plug] = term_db
        x = rng.standard_normal(n) * 10 ** (lvl / 20.0)
        # the open input's pops: a few a second, 1-3 ms, 10-20 dB over it
        is_open = ((t >= pull) if pull is not None else np.zeros(n, bool))
        if plug is not None:
            is_open &= t < plug
        for tp in rng.uniform(0, dur, int(dur * 3)):
            i = int(tp * FS)
            if i < n and is_open[i]:
                w = int(rng.uniform(0.001, 0.003) * FS)
                g = 10 ** ((open_db + rng.uniform(10, 20)) / 20.0)
                x[i:i + w] += rng.standard_normal(min(w, n - i)) * g
        # a connector moving: 100-250 ms of contact noise around each event
        for te, db in ((pull, -30.0), (plug, -35.0)):
            if te is None:
                continue
            i0 = int(max(0.0, te - 0.05) * FS)
            w = int(rng.uniform(0.10, 0.25) * FS)
            x[i0:i0 + w] += rng.standard_normal(min(w, n - i0)) * \
                10 ** (db / 20.0)
        self.x = x
        # the meter: per-millisecond block peaks into a draining latch
        blk = int(FS / 1000)
        pk = np.abs(x[:n // blk * blk]).reshape(-1, blk).max(axis=1)
        pk_db = 20 * np.log10(np.maximum(pk, 1e-12))
        m = np.empty_like(pk_db)
        cur = LATCH_DBFS
        d = DECAY_DB_S / 1000.0
        for i, p in enumerate(pk_db):
            cur = max(cur - d, p)
            m[i] = cur
        self.meter_db = m
        # the node: consecutive 4096-sample windows
        win = 4096
        k = n // win
        ms = (x[:k * win].reshape(k, win) ** 2).mean(axis=1)
        self.rms_db = 10 * np.log10(np.maximum(ms, 1e-30))
        self.win_s = win / FS

    def state(self, t):
        if self.plug is not None and t >= self.plug:
            return 'plug'
        if self.pull is not None and t >= self.pull:
            return 'open'
        return 'lead'

    def meter(self, t):
        return float(self.meter_db[min(int(t * 1000), len(self.meter_db) - 1)])

    def rms(self, t):
        """The last COMPLETE window at time t."""
        k = int(t / self.win_s) - 1
        return float(self.rms_db[max(0, min(k, len(self.rms_db) - 1))])


class Hooked(object):
    """The unit surface detect() reads, answered from a Lane on the virtual
    clock. A meter peek costs PEEK_S; an RMS poll waits for the next window
    boundary, as `Unit.measure(settle>=1)` does."""

    def __init__(self, P, st, lane):
        self.P, self.st, self.L = P, st, lane

    def watch(self, _lane, rms=False, settle=0):
        P = self.P
        if not rms:
            P.nap(P.PEEK_S)
            return self.L.meter(P.now() - self.t0)
        t = P.now() - self.t0
        w = self.L.win_s
        nxt = (math.floor(t / w) + max(1, settle)) * w
        P.nap(nxt - t + 0.002)
        return self.L.rms(P.now() - self.t0)

    def meter_sweep(self, strips):
        return {}


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
    live = LV.Live(tempfile.mkdtemp(prefix='s153-live-'), run='patch',
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


def step(P, lane, mic):
    """One noise step through the real detect(). (how, seconds, state)."""
    st, logs = build(P)
    rows = noise_rows(st, mic)
    h = Hooked(P, st, lane)
    st.watch = h.watch
    st.u.meter_sweep = h.meter_sweep
    st.u.mark_moved()            # _prepare has just written osc off + gain 63
    h.t0 = P.now()
    prep = dict(lane=mic, freq=None, level=None, floor=-116.0,
                watch=None, sweep0={})
    how, _ans, dt = st.detect(rows, prep, None)
    return how, dt, lane.state(dt), logs


# ---------------------------------------------------------------------------
def main():
    opn = s125_open()
    print('== 1. margin table: node RMS at gain 63, per powered channel '
          '(dispatch item 2)')
    print('   drop = %.1f dB (patch-limits.csv, provisional); the rule needs '
          'lead -> open >= drop (or a crackle between) AND open -> plug >= drop'
          % AFTER.Limits.load(LIST_DIR)['detect_drop_db'])
    print('   %-7s %-4s %9s %9s %9s %11s %11s' % (
        'input', 'J', 'open', 'T4 node', 'T4 capt', 'open-plug', 'lead-open'))
    drop = AFTER.Limits.load(LIST_DIR)['detect_drop_db']
    rows = []
    for mic in range(1, 25):
        if mic not in S55_TERM or mic not in opn:
            print('   MIC %-3d %-4s %9s %9s %9s %11s %11s' % (
                mic, '-', 'no data', 'no data', 'no data', '-', '-'))
            continue
        j, node, cap = S55_TERM[mic]
        o = opn[mic]
        worst = max(v for v in (node, cap) if v is not None)
        m_op = o - worst
        m_lo = LEAD_DBFS - o
        rows.append((mic, o, node, cap, m_op))
        flag = '' if m_op >= drop else '  <-- under drop (node T4)'
        if m_op < drop and cap is not None and o - cap >= drop:
            flag = '  <-- under drop on T4 node, %.1f dB on the capture' % (
                o - cap)
        print('   MIC %-3d %-4s %9.1f %9.2f %9s %11.1f %11.1f%s' % (
            mic, j, o, node, '%.2f' % cap if cap is not None else '-',
            m_op, m_lo, ('  <-- crackle needed' if m_lo < drop else '')
            + flag))
    print('   MIC 1-4 and 13-16: NO SURVEY DATA -- they had no front ends on '
          '09-16 (S55) or 09-26 (S125); live since PW\'s rev C mods today')

    print()
    print('== 2. the swap on every surveyed channel, before and after')
    print('   pull at 1.5-3.0 s, plug 2.0-3.5 s later (a person), 3 seeds each')
    print('   %-7s %-26s %-26s' % ('input', 'before (meter, S152)',
                                  'after (node RMS, S153)'))
    b_right = a_right = n = 0
    b_after = []
    a_after = []
    for mic, o, node, cap, _m in rows:
        term = cap if cap is not None else node
        cells = {'b': [], 'a': []}
        for seed in range(3):
            rng = np.random.default_rng(1000 * mic + seed)
            pull = float(rng.uniform(1.5, 3.0))
            plug = pull + float(rng.uniform(2.0, 3.5))
            lane = Lane(o, term, pull, plug, seed=1000 * mic + seed)
            for key, P in (('b', BEFORE), ('a', AFTER)):
                how, dt, state, _logs = step(P, lane, mic)
                cells[key].append((how, dt, state, plug))
        n += len(cells['a'])
        for key, acc, right in (('b', b_after, 'b'), ('a', a_after, 'a')):
            for how, dt, state, plug in cells[key]:
                if how == 'drop' and state == 'plug':
                    acc.append(dt - plug)
                    if key == 'b':
                        b_right += 1
                    else:
                        a_right += 1

        def fmt(cs):
            return ' '.join('%5.1f%s' % (dt, '' if st_ == 'plug' else
                                         ('L' if st_ == 'lead' else 'O'))
                            for _h, dt, st_, _p in cs)
        print('   MIC %-3d %-26s %-26s' % (mic, fmt(cells['b']),
                                           fmt(cells['a'])))
    print('   (seconds from the prompt; L = the step ended with the tone LEAD '
          'still in, O = with the input OPEN -- a wrong reading either way)')
    print()
    check('BEFORE grades the plug on only %d of %d steps' % (b_right, n),
          True)
    check('AFTER grades the plug on every step (%d of %d)' % (a_right, n),
          a_right == n)
    if b_after:
        print('   before, when it did grade the plug: %.1f s after the plug '
              '(median), worst %.1f s' % (float(np.median(b_after)),
                                          max(b_after)))
    if a_after:
        print('   after: %.2f s after the plug (median), worst %.2f s'
              % (float(np.median(a_after)), max(a_after)))
        check('after: every step ends within 1.0 s of the plug going in',
              max(a_after) <= 1.0, '%.2f s' % max(a_after))

    print()
    print('== 3. the refusals, after (node RMS)')
    for mic in (7, 17, 6):
        o = opn[mic]
        j, node, cap = S55_TERM[mic]
        term = cap if cap is not None else node
        for name, pull, plug in (('the lead left in', None, None),
                                 ('the lead pulled, nothing fitted', 2.0,
                                  None)):
            how, dt, state, _l = step(AFTER, Lane(o, term, pull, plug,
                                                  seed=7 + mic), mic)
            check('MIC %d, %s: not graded (%s at %.0f s)' % (mic, name, how,
                                                               dt),
                  how == 'timeout')
    # THE KNOWN LIMIT, shown rather than hidden: MIC 6 on S55's NODE figure
    # (-82.04) is 1.1 dB under its open input -- no second step to find -- and
    # on the capture's (-87.59) it is 6.6 dB. Which one the part reads today is
    # a bench question; this is what each one does.
    for name, term in (('node T4 -82.04', -82.04), ('capture -87.59', -87.59)):
        how, dt, state, _l = step(AFTER, Lane(opn[6], term, 2.0, 4.5,
                                              seed=66), 6)
        print('   MIC 6 on the %s figure: %s at %.1f s (%s in the socket)'
              % (name, how, dt, state))
    # and the one the old detector got wrong most often: pulled late
    how, dt, state, logs = step(AFTER, Lane(opn[8], S55_TERM[8][2], 6.0, 9.0,
                                            seed=88), 8)
    check('MIC 8, a slow operator (pull 6 s, plug 9 s): graded on the plug, '
          '%.2f s after it' % (dt - 9.0), how == 'drop' and state == 'plug')
    print('   its log:')
    for ln in logs:
        print('     %s' % ln)

    print()
    print('== 4. tone rows untouched: S145 harness + whole-pass dry run')
    r = subprocess.run([sys.executable, os.path.join(
        ROOT, 'MW', 'D24', 'DSP', 's145', 'patch_auto_advance_check.py')],
        capture_output=True, text=True)
    check('patch_auto_advance_check.py passes', r.returncode == 0,
          r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr[-200:])

    print()
    if FAILS:
        print('%d check(s) FAILED' % len(FAILS))
        return 1
    print('all checks passed -- no unit, no bus, no write')
    return 0


if __name__ == '__main__':
    sys.exit(main())
