#!/usr/bin/env python3
"""d24_patch.py -- the analog station: one patch list, walked by hand (S121).

    d24_patch.py --list                     print the plan and stop
    d24_patch.py --simulate                 the whole pass on a desk, no unit
    d24_patch.py --simulate --hand 5        ... with 5 s per hand move
    d24_patch.py --run [--block K1]         the real thing, on the unit
    d24_patch.py --time-table               seconds per patch type, projected

WHAT IT IS. PW 2026-09-26: "tester will prompt the operator to patch a single
cable then press enter, the signal path will be tested with pass/fail, then the
next patch will be prompted, until all signal paths are tested", and then
2026-09-26 again: the manual loop is the PRODUCTION path, not a fallback, and
the figure of merit is OPERATOR SECONDS. So this file is written around the
operator's hands, and every machine cost is pushed out of their way:

  * NOBODY PRESSES ENTER. The prompt goes up, the tone is already running, and
    the runner watches the input the patch is supposed to reach. The moment the
    lead goes in, the meter on that lane rises and the step is over -- the
    operator is already moving to the next socket while the reading is taken.
    Enter stays on the glass as a fallback and for a step that will not
    auto-advance on its own.
  * THE NOISE ROWS AUTO-ADVANCE TOO. A 150 ohm terminator makes no tone, so
    there is nothing to detect -- except that fitting it DROPS the lane's own
    noise, because an open mic input is much noisier than a terminated one.
    That drop is the insertion, and it is what ends the step.
  * SCORING IS PIPELINED. The verdict for patch N is computed while the
    operator's hands are on patch N+1. The operator never waits for a
    measurement; they wait only for their own hands.
  * THE LEAD CHANGES FOUR TIMES IN A WHOLE PASS, and the list is ordered so it
    never goes back to a lead already put down.

WHAT IT MEASURES, and with what. The stimulus is the DSP's own TEST_OSC; the
instrument is TEST_MEAS. Both need a DSP4_TEST_NODES=1 image, which is what the
factory already runs (PW ruling S116 Q3: `factory-test-v1`, the pair at
/home/app/loopthd/s109) -- d24_selftest.py asserts it and so does this file.
Per path:

  level      the COHERENT loop gain: TEST_MEAS fits the lane against the
             oscillator's own sine and cosine every window and leaves the
             signed in-phase and quadrature amplitudes in `_meas_a`/`_meas_b`.
             |H| from those two is a level that noise cannot inflate, which
             RmsResult can. (The algebra is S54's, in s54lib.py; it is repeated
             here rather than imported because that file lives in a session
             directory and this one ships to the unit.)
  polarity   arg(H) -- and it is RELATIVE, never absolute. A 1 kHz tone through
             this unit arrives with 91.4 samples of latency rotated into its
             phase, which is 1.9 cycles, so an absolute sign means nothing. The
             K1 block MEASURES a reference phase on each input lane and every
             later reading on that lane is judged against it: within 90 deg is
             `normal`, beyond it is `inverted`.
  presence   the strip meters, peeked. `_mtr_peak_C1_MTR_nn` is one word per
             strip and needs no settling window, so it is what the auto-advance
             watches and what the wrong-socket sweep reads across all 24 lanes
             in one go. TEST_MEAS is pointed at ONE lane and costs a settle
             every time it moves, which is why it is the verdict and not the
             detector.
  THD/noise  ThdResult and NoiseResult off the same windows, reported in dB AND
             in percent (PW's standing rule).

A WRONG PATCH IS NOT A FAIL. If the expected lane stays quiet, the runner reads
every lane and says where the lead actually is -- "the lead is in MIC 7, not
MIC 5" -- and prompts again. Only a path that is patched right and still does
not carry a tone is a failure, and even then RETRY comes first.
"""
import argparse
import cmath
import csv
import json
import math
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
LIST_DIR_CANDIDATES = (os.path.join(ROOT, 'MW', 'D24', 'DSP', 's121'),
                       os.path.join(HERE, 's121'),
                       '/home/app/selftest/s121')

FS = 48000.0
# TEST_MEAS integrates over 4,096 samples (dsp_codegen.py TEST_MEAS_WIN), so a
# window is 85.3 ms and a changed MeasChan needs two of them before the fit
# means anything -- the first window after any change has no fit yet and reads
# ThdResult 0.00 dB by construction.
WIN_S = 4096.0 / FS
SETTLE_WINDOWS = 2
READ_WINDOWS = 2
# A ROUTE CHANGE NEEDS LONGER THAN A MEASCHAN CHANGE. The send, the bus master
# and the pan are all ramped cells, and the fit that produces ThdResult treats
# a level still on its way somewhere as distortion: measured on MW-D24-2 on
# 2026-09-26, a reading taken two windows after a route assert gave THD+N
# figures from -4 dB to -115 dB on paths whose LEVEL was -15.01 dBFS every
# time. The level was never wrong; the fit had not settled. So a reading that
# follows a route change waits longer.
ROUTE_SETTLE_WINDOWS = 6

PASS, FAIL, NODATA, SKIPPED = 'PASS', 'FAIL', 'NO DATA', 'SKIPPED'
MISPATCH = 'MISPATCH'

# The factory-test pair, the same constants d24_selftest.py asserts against.
FACTORY_TEST_PAIR_DIR = '/home/app/loopthd/s109'
OSC_SYM = '_osc_blk_q_C1_TEST_OSC'


# ---------------------------------------------------------------------------
# The clock
# ---------------------------------------------------------------------------
# Every wait in this file goes through `now()` and `nap()` so the dry run can
# replace them with a virtual clock and walk all eighty-one patches in a second
# while still reporting the seconds a real pass would take. The real path is
# `time.time` and `time.sleep` and nothing else.
class _RealClock:
    now = staticmethod(time.time)
    nap = staticmethod(time.sleep)


class VirtualClock:
    """A clock that never waits and still counts."""

    def __init__(self, t0=0.0):
        self.t = t0

    def now(self):
        return self.t

    def nap(self, dt):
        self.t += dt


CLOCK = _RealClock()


def now():
    return CLOCK.now()


def nap(dt):
    CLOCK.nap(dt)


def pct_of_db(db):
    """A ratio in dB as percent. PW's standing rule (2026-09-16): every
    THD/THD+N figure is printed in dB AND in percent, never one alone."""
    return 100.0 * 10.0 ** (db / 20.0)


def dbpct(db):
    if db is None or not math.isfinite(db):
        return '--'
    return '%.2f dB = %.3f %%' % (db, pct_of_db(db))


def dbv(x):
    return 20.0 * math.log10(x) if x and x > 0 else float('-inf')


def wrap180(deg):
    return (deg + 180.0) % 360.0 - 180.0


# ---------------------------------------------------------------------------
# The list
# ---------------------------------------------------------------------------
def find_list_dir(explicit=None):
    for d in ((explicit,) if explicit else LIST_DIR_CANDIDATES):
        if d and os.path.exists(os.path.join(d, 'patch-paths.csv')):
            return d
    raise SystemExit('patch-paths.csv not found; looked in %s'
                     % ', '.join(x for x in LIST_DIR_CANDIDATES if x))


def read_csv(path):
    with open(path, newline='') as fh:
        return list(csv.DictReader(l for l in fh if not l.startswith('#')))


class PatchList:
    """The generated list, grouped the way the operator meets it.

    `paths` is one row per measurement; `patches` is the list of (patch id,
    its rows) in order. Rows sharing a patch id are sub-tests of ONE physical
    connection, so the operator is prompted once for the lot -- which is the
    runner-interface's `connect` contract, and the reason a stereo jack costs
    one hand move and not three.
    """

    def __init__(self, d):
        self.dir = d
        self.paths = read_csv(os.path.join(d, 'patch-paths.csv'))
        self.routes = dict((r['route'], r['cells'].split(';'))
                           for r in read_csv(os.path.join(d, 'patch-routes.csv')))
        self.patches = []
        for r in self.paths:
            if not self.patches or self.patches[-1][0] != r['patch']:
                self.patches.append((r['patch'], []))
            self.patches[-1][1].append(r)

    def blocks(self):
        out = []
        for pid, rows in self.patches:
            key = (rows[0]['lead'], rows[0]['block'])
            if not out or out[-1][0] != key:
                out.append((key, []))
            out[-1][1].append((pid, rows))
        return out

    def standing(self, donors=None):
        return (list(self.routes['_standing_close'])
                + self.routes['_standing_strips']
                + self.routes['_standing_masters'])


# ---------------------------------------------------------------------------
# The unit
# ---------------------------------------------------------------------------
class Unit:
    """Cells, meters and the measurement node, over ONE long-lived link.

    WHY NOT s89_set.py. That tool is a process per write: it starts Python,
    opens a Scope per chip, resyncs the diag link, writes one cell, sleeps
    0.05 s, sleeps 0.15 s more and reads it back. It exists to be readable from
    a shell and it is the right tool for four cells. This station writes ten to
    forty cells per patch across eighty-one patches; at a fifth of a second
    each that is minutes of the operator's time spent on sleeps that are in the
    tool and not in the hardware. So the link is opened ONCE here and the
    sleeps are gone; read-back stays, because a write that did not land is the
    one failure mode that reads like a dead path.
    """

    def __init__(self, symdir=FACTORY_TEST_PAIR_DIR, landed=None):
        sys.path.insert(0, '/home/app/dspboot')
        import dsp4_scope as S                       # noqa: E402
        self.S = S
        self.symdir = symdir
        landed = landed or '/home/app/dspboot/landed-d24.json'
        self.cells = json.load(open(landed))['cells']
        self._chips = {}
        self._meas_addr = {}
        self.check_factory_image()

    def chip(self, n):
        if n not in self._chips:
            sc = self.S.Scope(n, symfile='%s/chip%d.sym.json' % (self.symdir, n))
            sc.d.resync()
            sc.check_chip()
            self._chips[n] = sc
        return self._chips[n]

    def check_factory_image(self):
        """Refuse a shipping image, loudly.

        TEST_OSC and TEST_MEAS are compiled out unless DSP4_TEST_NODES=1. The
        sixteen dispatch words still exist and still take writes either way, so
        a station run against a shipping pair would read four zeros and they
        would look exactly like a measurement of a dead unit (dsp4_s49_osc.py
        makes the same check for the same reason).
        """
        sc = self.chip(1)
        if OSC_SYM not in sc.sym:
            raise SystemExit(
                '%s is not in the staged symbol map (%s): this is not a\n'
                'DSP4_TEST_NODES=1 pair, and without it the oscillator does not\n'
                'exist. The factory pair is %s (PW ruling S116 Q3).'
                % (OSC_SYM, self.symdir, FACTORY_TEST_PAIR_DIR))

    # -- cells -------------------------------------------------------------
    def addr(self, name):
        e = self.cells.get(name)
        if e is None:
            raise KeyError('%s is not in the contract' % name)
        return e[0], e[2]

    def write(self, specs, verify=True):
        """Write `name=value` specs. Returns the names that did not read back."""
        want = {}
        for spec in specs:
            name, _, val = spec.partition('=')
            w = f32(val[1:]) if val.startswith('f') else int(val, 0)
            n, a = self.addr(name)
            self.chip(n).d.link.write(a, w & 0xFFFFFFFF, 0)
            want[name] = w & 0xFFFFFFFF
        if not verify:
            return []
        bad = []
        for name, w in want.items():
            n, a = self.addr(name)
            if self.chip(n).rd(a) != w:
                bad.append(name)
        return bad

    def read(self, name):
        n, a = self.addr(name)
        return self.chip(n).rd(a)

    def readf(self, name):
        return from_f32(self.read(name))

    # -- meters ------------------------------------------------------------
    def meter_peak(self, strip):
        """One strip's linear peak, straight off the meter node's own word.

        No window, no settle: the meter latches the block's peak and decays, so
        a peek is current within a block. That is what makes it the detector
        the auto-advance polls and the sweep that finds a misplaced lead.
        """
        sc = self.chip(1)
        sym = sc.sym.get('_mtr_peak_C1_MTR_%02d' % strip)
        if sym is None:
            return None
        return from_f32(peek_settled(sc, sym))

    def meter_sweep(self, strips):
        return dict((s, self.meter_peak(s)) for s in strips)

    # -- the oscillator ----------------------------------------------------
    def osc(self, chan=None, freq=None, level_dbfs=None, on=None):
        specs = []
        if freq is not None:
            specs.append('Test001OscFreq001=f%g' % freq)
        if level_dbfs is not None:
            specs.append('Test001OscLevel001=f%g' % (10 ** (level_dbfs / 20.0)))
        if chan is not None:
            specs.append('Test001OscChan001=%d' % chan)
        if on is not None:
            specs.append('Test001OscOn001=%d' % (1 if on else 0))
        if specs:
            bad = self.write(specs)
            if bad:
                raise SystemExit('oscillator cells did not read back: %s'
                                 % ', '.join(bad))

    def meas_chan(self, lane):
        self.write(['Test001MeasChan001=%d' % lane])

    def measure(self, freq, level_dbfs, windows=READ_WINDOWS,
                settle=SETTLE_WINDOWS):
        """One settled reading of whatever MeasChan is pointed at.

        Returns rms/thd/noise straight off the node and, when the oscillator is
        running, the coherent transfer function H: |H| in dB is the level the
        verdict uses and arg(H) in degrees is the phase the polarity is judged
        from. Both come from `_meas_a`/`_meas_b`, the signed in-phase and
        quadrature amplitudes of the node's own least-squares fit against the
        oscillator's reference -- the only signed quantity the part publishes.
        """
        sc = self.chip(1)
        seq0 = self._seq()
        while (self._seq() - seq0) & 0xFFFFFFFF < settle:
            nap(WIN_S / 2)
        rows, seen = [], None
        kf = from_f32(peek_settled(sc, sc.sym['_osc_k_C1_TEST_OSC']))
        on = self.read('Test001OscOn001') != 0
        while len(rows) < windows:
            s1 = self._seq()
            if s1 == seen:
                nap(WIN_S / 3)
                continue
            rms = self.readf('Test001RmsResult001')
            thd = self.readf('Test001ThdResult001')
            nse = self.readf('Test001NoiseResult001')
            a = from_f32(peek_settled(sc, sc.sym['_meas_a_C1_TEST_MEAS']))
            b = from_f32(peek_settled(sc, sc.sym['_meas_b_C1_TEST_MEAS']))
            if self._seq() != s1:            # the window turned over mid-read
                continue
            seen = s1
            row = dict(rms=rms, thd=thd, noise=nse, a=a, b=b)
            if on and kf > 0 and freq:
                w = 2 * math.pi * freq / FS
                z = cmath.exp(1j * w)
                r = (z - 1) / kf
                L = 10 ** (level_dbfs / 20.0)
                H = (a + b * r) / (L * math.cos(w / 2))
                row['h_db'] = dbv(abs(H))
                row['h_deg'] = math.degrees(cmath.phase(H))
                row['coh_dbfs'] = dbv(abs(a + b * r) / math.cos(w / 2))
            rows.append(row)
        return fold(rows)

    def _seq(self):
        sc = self.chip(1)
        return peek_settled(sc, sc.sym['_meas_seq_C1_TEST_MEAS'])


def fold(rows):
    """Average the windows. Levels in dB average in power; phase averages as a
    unit vector, because 179 deg and -179 deg are half a degree apart and their
    arithmetic mean is zero."""
    out = {}
    for k in ('rms', 'thd', 'noise', 'h_db', 'coh_dbfs'):
        v = [r[k] for r in rows if k in r and math.isfinite(r[k])]
        if v:
            out[k] = 10 * math.log10(sum(10 ** (x / 10) for x in v) / len(v))
    v = [cmath.exp(1j * math.radians(r['h_deg'])) for r in rows if 'h_deg' in r]
    if v:
        out['h_deg'] = math.degrees(cmath.phase(sum(v) / len(v)))
    out['n'] = len(rows)
    return out


def peek_settled(sc, addr):
    """Read until two reads agree.

    The diag link intermittently answers 0xFFFFFFFF, and a single read cannot
    tell that from a real value -- dsp4_mtr_state.py hit exactly this and
    reported a peak of NaN twice before the retry went in.
    """
    last = None
    for _ in range(24):
        try:
            v = sc.d.peek(addr)
        except Exception:
            last = None
            nap(0.02)
            continue
        if v == 0xFFFFFFFF:
            last = None
            nap(0.02)
            continue
        if v == last:
            return v
        last = v
    return last if last is not None else 0


def f32(x):
    import struct
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def from_f32(w):
    import struct
    return struct.unpack('<f', struct.pack('<I', (w or 0) & 0xFFFFFFFF))[0]


# ---------------------------------------------------------------------------
# The patch back ends
# ---------------------------------------------------------------------------
class Patcher:
    """One connection at a time, however it is made.

    The interface is the harness revision's (`s121/harness-ref/
    runner-interface.md`): `connect` makes exactly one path from the list and
    NOTHING about the test changes with the back end. PW ruled on 2026-09-26
    that the manual loop is the production path and that no effort goes into
    the harness now, so `HarnessPatcher` below is a declaration of the shape
    and not an implementation -- it exists so the list, the loop and the
    scoring cannot quietly grow a manual-only assumption.
    """

    kind = 'none'

    def identify(self):
        return self.kind

    def connect(self, patch, rows, glass):
        """Put the patch in front of whoever makes it. Returns a token the
        loop polls; None means the connection is already made."""
        raise NotImplementedError

    def poll(self, token):
        """The operator's answer, or None. Never blocks."""
        return None

    def done(self, token):
        pass

    def clear(self):
        pass


class ManualPatcher(Patcher):
    """A person, a lead, and a prompt that does not wait for Enter."""

    kind = 'manual'

    def __init__(self, glass):
        self.glass = glass
        self.last = None

    def connect(self, patch, rows, glass):
        r = rows[0]
        lead = r['lead']
        lines = [r['prompt'] + '.']
        if r['sub'] or len(rows) > 1:
            lines.append('%d checks on this one patch -- leave the lead in '
                         'until the next instruction.' % len(rows))
        lines.append('It advances on its own when the lead is in.')
        btns = glass.post('patch', '%s  (lead %s)' % (r['prompt'], lead),
                          lines, ['done'], patch=patch, lead=lead,
                          row=r['rows'])
        self.last = patch
        return btns

    def poll(self, token):
        return self.glass.poll(token) if token else None

    def done(self, token):
        self.glass.clear()


class HarnessPatcher(Patcher):
    """The USB-CDC harness. DECLARED, NOT BUILT (PW 2026-09-26).

    The wire protocol is written down in s121/harness-ref/runner-interface.md:
    `IDENT`, `SELFTEST`, `CLEAR`, `CONNECT "<out>" "<in>"`, `TERMINATE`,
    `PHANTOM`, every state change atomic (latch, read back, 50 ms settle) and
    every reply one final `OK ...` or `ERR <code> <text>`. Everything this loop
    does around `connect()` -- the route cells, the windows, the level and
    polarity arithmetic, the wrong-socket sweep, the scoring -- is already back
    end agnostic, so building this class is writing a serial client and
    nothing else. It is deliberately left raising rather than half-written: a
    stub that silently returns success is how a station comes to report a pass
    for a path nobody connected.
    """

    kind = 'harness'

    def __init__(self, port=None):
        self.port = port

    def connect(self, patch, rows, glass):
        raise NotImplementedError(
            'the harness back end is not built: PW ruled on 2026-09-26 that '
            'the manual loop is the production path. The wire protocol is in '
            's121/harness-ref/runner-interface.md and the list already carries '
            'every path it needs.')


def pick_patcher(glass, want='auto'):
    """MANUAL unless a harness answers IDENT on a /dev/ttyACM* -- and since the
    harness back end is not built, MANUAL either way today. The probe is left
    in as the one line that has to change."""
    if want == 'harness':
        return HarnessPatcher()
    return ManualPatcher(glass)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
class Limits(dict):
    """patch-limits.csv, and nothing else. No number lives in this file."""

    @classmethod
    def load(cls, d):
        out = cls()
        for r in read_csv(os.path.join(d, 'patch-limits.csv')):
            out[r['key']] = float(r['value'])
        return out


class Scorer:
    """Turns readings into verdicts, and keeps the two things a later reading
    is judged against: each input lane's BALANCED REFERENCE level and phase.

    The reference is measured, not predicted. K1 patches an XLR output into an
    XLR input, which is the one configuration on this unit whose level and
    polarity are definitionally correct -- both legs driven, both legs read --
    and every single-ended reading on that lane afterwards is a ratio against
    it. That is what makes the windows survive a change of drive level, a gain
    law revision, or a different unit.
    """

    def __init__(self, limits):
        self.lim = limits
        self.ref = {}                # lane -> {'h_db', 'h_deg'}
        self.results = []

    def polarity_of(self, lane, deg):
        """normal / inverted / uncertain, against the lane's reference phase."""
        r = self.ref.get(lane)
        if r is None or deg is None or 'h_deg' not in r:
            return None, None
        d = abs(wrap180(deg - r['h_deg']))
        edge = abs(d - self.lim['polarity_margin_deg'])
        if edge < self.lim['polarity_uncertain_deg']:
            return 'uncertain', d
        return ('normal' if d < self.lim['polarity_margin_deg']
                else 'inverted'), d

    def score(self, row, meas, floor, sweep, siblings, donor=None):
        """One path's verdict, and the plain sentence that goes with it.

        `meas` is the settled reading, `floor` the same lane with the tone off,
        `sweep` every lane's meter while this path was driven, and `siblings`
        the readings already taken on sub-tests of the same patch.
        """
        lane = int(row['lane'])
        want = row['expect']
        notes = []
        h = meas.get('h_db')
        deg = meas.get('h_deg')

        if want == 'noise':
            return self._score_noise(row, meas, notes)

        # `floor` is the lane's own dBFS floor and `h` is a loop GAIN, so the
        # comparison is made on the lane: the coherent level the fit found.
        here = meas.get('coh_dbfs', meas.get('rms'))
        rise = (here - floor) if (here is not None and floor is not None
                                  and math.isfinite(here)) else None
        if want == 'tone':
            if rise is None or rise < self.lim['tone_min_over_floor_db']:
                return (NODATA, 'no tone reached %s: the lane sat %s over its '
                        'own floor' % (row['in'],
                                       '%.1f dB' % rise if rise is not None
                                       else 'nothing measurable'), notes)
        elif want == 'null':
            single = [s['h_db'] for s in siblings
                      if s.get('level_ref') == 'single' and s.get('h_db') is not None]
            if not single:
                return (NODATA, 'the null has nothing to be measured against: '
                        'neither single-ended sub-test produced a reading', notes)
            rel = h - max(single) if h is not None else None
            if rel is None:
                return NODATA, 'the null produced no reading at all', notes
            notes.append('%.1f dB below the louder of the two channels' % rel)
            if rel <= self.lim['null_max_db']:
                return PASS, ('the two channels cancelled to %.1f dB below '
                              'either one' % rel), notes
            return (FAIL, 'the two channels did not cancel: only %.1f dB down, '
                    'so they are not matched or they are crossed' % rel, notes)

        # -- isolation: the tone must be on THIS lane and no other ----------
        bad = self._isolation(lane, sweep, donor)
        if bad:
            return (MISPATCH, 'the tone is on %s, not %s' % (bad, row['in']), notes)

        # -- level ----------------------------------------------------------
        ref_mode = row['level_ref']
        if ref_mode == 'ref':
            self.ref[lane] = dict(h_db=h, h_deg=deg)
            notes.append('this reading is now %s\'s balanced reference: '
                         '%.2f dB, %.1f deg' % (row['in'], h, deg or 0.0))
        elif ref_mode == 'single':
            r = self.ref.get(lane)
            if r is None or r.get('h_db') is None:
                notes.append('no balanced reference on this lane yet, so the '
                             'level is reported and not judged')
            else:
                want_db = r['h_db'] + self.lim['single_ended_db']
                d = h - want_db
                notes.append('%.2f dB, which is %+.2f dB from the %+.2f dB this '
                             'lane\'s balanced reference predicts'
                             % (h, d, want_db))
                if abs(d) > self.lim['level_tol_db']:
                    return (FAIL, 'the level is %+.1f dB off what a single-ended '
                            'leg of this output should give' % d, notes)
        elif ref_mode == 'info':
            notes.append('%.2f dB loop gain, reported: no window is ruled for '
                         'this path yet' % h)

        # -- the two halves of a stereo jack must match each other -----------
        sibs = [s for s in siblings if s.get('level_ref') == 'single'
                and s.get('h_db') is not None]
        if ref_mode == 'single' and sibs:
            d = abs(h - sibs[-1]['h_db'])
            if d > self.lim['stereo_match_tol_db']:
                return (FAIL, 'the two channels of this jack differ by %.1f dB'
                        % d, notes)
            notes.append('within %.2f dB of the other channel' % d)

        # -- polarity ---------------------------------------------------------
        pol_want = row['polarity']
        uncertain = None
        if pol_want == 'ref':
            pass                                     # stored above
        elif pol_want in ('normal', 'inverted'):
            got, d = self.polarity_of(lane, deg)
            if got is None:
                notes.append('polarity not judged: this lane has no reference '
                             'phase yet')
            elif got == 'uncertain':
                # NOT a silent pass. PW made polarity a measured item, so a
                # reading that lands on the decision boundary is reported as
                # uncalled and says how far off the boundary it was -- the one
                # thing a reader needs to decide whether to look again.
                uncertain = d
                notes.append('polarity UNCERTAIN: %.0f deg from the reference, '
                             'too near the %.0f deg boundary to call'
                             % (d, self.lim['polarity_margin_deg']))
            elif got != pol_want:
                if pol_want == 'normal' and got == 'inverted':
                    return (FAIL, 'this channel came back inverted, which on a '
                            'stereo jack is tip and ring swapped', notes)
                return (FAIL, 'this channel came back %s and should be %s'
                        % (got, pol_want), notes)
            else:
                notes.append('polarity %s, %.0f deg from the reference'
                             % (got, d))
        elif pol_want == 'info' and deg is not None:
            notes.append('phase %.1f deg, reported only' % deg)

        thd = meas.get('thd')
        if thd is not None and math.isfinite(thd):
            notes.append('THD+N %s' % dbpct(thd))
        if uncertain is not None:
            return (PASS, 'the tone arrived on %s at the right level, but its '
                    'polarity could not be called: %.0f deg from the reference'
                    % (row['in'], uncertain), notes)
        return PASS, 'the tone arrived on %s and nowhere else' % row['in'], notes

    def _score_noise(self, row, meas, notes):
        n = meas.get('rms')
        if n is None or not math.isfinite(n):
            return NODATA, 'the noise reading did not come back', notes
        notes.append('%.1f dBFS at the lane with the terminator fitted' % n)
        return (PASS, 'the input noise was measured with a 150 ohm source',
                notes + ['no EIN window is ruled for the factory station yet: '
                         'the figure is recorded, and limits.csv t4b_ein_max_dbu '
                         'is the design reference'])

    def _isolation(self, lane, sweep, donor=None):
        """The loudest OTHER lane, if it is not far enough down.

        THE DONOR STRIP IS NOT A LANE UNDER TEST and is skipped. The
        oscillator REPLACES a strip's input, so the donor's own meter sits at
        the drive level for every patch of the pass -- measured on MW-D24-2:
        MIC 24 read -12.0 dBFS while every real path read about -15. Counting
        it would make every single patch report the tone as being on the donor
        rather than where the lead is.
        """
        if not sweep:
            return None
        here = sweep.get(lane)
        if here is None or here <= 0:
            return None
        worst, who = None, None
        for k, v in sweep.items():
            if k == lane or k == donor or not v or v <= 0:
                continue
            d = dbv(v) - dbv(here)
            if worst is None or d > worst:
                worst, who = d, k
        if worst is not None and worst > -self.lim['isolation_min_db']:
            return 'MIC %d' % who
        return None


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------
MIC_STRIPS = tuple(range(1, 25))
# How many times a patch is offered again before it is recorded as NO DATA. A
# wrong patch is a prompt and not a fail (PW 2026-09-26), but a prompt that
# repeats for ever is a station that has stopped, so the loop bounds itself and
# records what it saw. The operator can still press FAIL at any offer.
MAX_RETRIES = 2


class Station:
    """One pass of the patch list.

    The shape is three steps per patch, and the order of the three is the whole
    point: PREPARE puts the route up and takes the unplugged baseline, ACQUIRE
    waits for the operator's hands and then reads, and SCORE is arithmetic. The
    next patch is PREPARED and prompted BEFORE the last one is SCORED, so the
    only thing the operator ever waits for is the reading itself -- about half
    a second, while their hand is still on the connector -- and never for the
    verdict, the state file or the report line.
    """

    def __init__(self, plist, unit, patcher, glass, limits, log=None,
                 blocks=None):
        self.L = plist
        self.u = unit
        self.p = patcher
        self.g = glass
        self.lim = limits
        self.sc = Scorer(limits)
        self.log = log or (lambda s: None)
        self.only = set(blocks or ())
        self.rows_out = []
        self.timing = []
        self.floors = {}

    # -- setup -------------------------------------------------------------
    def standing(self):
        donors = sorted({int(r['donor']) for r in self.L.paths})
        cells = self.L.standing(donors)
        self.log('standing write: %d cells (every strip\'s assigns shut, both '
                 'donor strips made transparent, every bus master at unity)'
                 % len(cells))
        bad = self.u.write(cells)
        if bad:
            raise SystemExit('the standing write did not land: %s'
                             % ', '.join(sorted(bad)[:8]))
        self.measure_floors()
        return len(cells)

    def measure_floors(self):
        """Each lane's own floor, once, with the oscillator off.

        A floor is a property of the LANE, not of the patch, and it cannot be
        taken per patch: the list parks one lead in MIC 1 for the whole TRS
        block, so a "floor" read just before those patches would be the tone
        that is already there. Taken here, at the start, with nothing plugged
        in and nothing driven, it is what it says it is -- and it costs the
        operator nothing, because at this point they are still picking up the
        first lead.
        """
        self.u.osc(on=False)
        lanes = sorted({int(r['lane']) for r in self.L.paths})
        for lane in lanes:
            self.u.meas_chan(lane)
            m = self.u.measure(None, 0.0)
            self.floors[lane] = m.get('rms')
        self.log('floors: %d lanes, %.1f to %.1f dBFS'
                 % (len(lanes),
                    min(v for v in self.floors.values() if v is not None),
                    max(v for v in self.floors.values() if v is not None)))

    # -- one patch ---------------------------------------------------------
    def prepare(self, rows):
        """Assert the first sub-test's route, point the instrument, and read
        the lane with NOTHING plugged in. That baseline is two things at once:
        what the auto-advance watches for a change in, and the floor the tone
        has to rise above for the reading to count."""
        r = rows[0]
        lane = int(r['lane'])
        self.u.write(self.L.routes[r['route']])
        freq = float(r['freq_hz']) if r['freq_hz'] else None
        lvl = float(r['level_dbfs']) if r['level_dbfs'] else None
        if r['expect'] == 'noise':
            self.u.osc(on=False)
        else:
            self.u.osc(chan=int(r['donor']), freq=freq, level_dbfs=lvl, on=True)
        self.u.meas_chan(lane)
        return dict(lane=lane, freq=freq, level=lvl,
                    floor=self.floors.get(lane), watch=self.watch(lane))

    def watch(self, lane):
        """The cheap level the auto-advance polls, in dB.

        A strip has a meter node and a meter needs no settling window, so a
        peek is current within a block -- that is the detector. The three codec
        return lanes (the talkback XLR and the two mini-jack legs) have no
        meter of their own, so those patches watch the measurement node's own
        RmsResult instead: MeasChan is already pointed at them and is not
        moving, so the reading costs one SPI read and no settle.
        """
        if lane in MIC_STRIPS:
            v = self.u.meter_peak(lane)
            return dbv(v) if v else None
        m = self.u.measure(None, 0.0, windows=1, settle=0)
        v = m.get('rms')
        return v if v is not None and math.isfinite(v) else None

    def detect(self, rows, prep, token):
        """Wait for the operator's hands, not for their Enter.

        Tone rows rise; noise rows drop, because an open mic input is noisier
        than a terminated one and fitting the plug is what changes it. Either
        way the glass button is polled in the same breath, so PAUSE, SKIP and
        the Enter fallback are always live.
        """
        r = rows[0]
        lane = prep['lane']
        rise = self.lim['detect_rise_db']
        drop = self.lim['detect_drop_db']
        t0 = now()
        deadline = t0 + self.lim['detect_timeout_s']
        # THE BASELINE IS NOT prepare()'s READING, and this is the one place
        # that matters. When the prompt goes up the PREVIOUS patch's lead is
        # still in the unit -- the operator has not pulled it yet -- so a
        # baseline taken before the prompt can be the wrong socket's state. So
        # the detector tracks the lane's own extreme SINCE THE PROMPT WENT UP:
        # the quietest it has been for a tone row, the loudest for a noise row.
        # Pulling the old lead and fitting the new one is exactly the shape
        # that produces, and it needs no knowledge of what came before.
        lo = hi = None
        while now() < deadline:
            ans = self.p.poll(token)
            if ans is not None:
                return ('glass', ans, now() - t0)
            lvl = self.watch(lane)
            if lvl is not None and math.isfinite(lvl):
                lo = lvl if lo is None else min(lo, lvl)
                hi = lvl if hi is None else max(hi, lvl)
                if r['expect'] == 'noise':
                    if hi - lvl >= drop:
                        return ('drop', None, now() - t0)
                elif lvl - lo >= rise:
                    return ('rise', None, now() - t0)
            nap(0.05)
        return ('timeout', None, now() - t0)

    def acquire(self, rows, prep):
        """Every sub-test of one patch, with the lead left where it is."""
        out = []
        for i, r in enumerate(rows):
            if i:
                self.u.write(self.L.routes[r['route']])
                freq = float(r['freq_hz']) if r['freq_hz'] else None
                lvl = float(r['level_dbfs']) if r['level_dbfs'] else None
                if r['expect'] != 'noise':
                    self.u.osc(chan=int(r['donor']), freq=freq,
                               level_dbfs=lvl, on=True)
                if int(r['lane']) != int(rows[i - 1]['lane']):
                    self.u.meas_chan(int(r['lane']))
            freq = float(r['freq_hz']) if r['freq_hz'] else None
            lvl = float(r['level_dbfs']) if r['level_dbfs'] else 0.0
            m = self.u.measure(freq, lvl, settle=ROUTE_SETTLE_WINDOWS)
            sweep = (self.u.meter_sweep(MIC_STRIPS)
                     if int(r['lane']) in MIC_STRIPS and r['expect'] == 'tone'
                     else {})
            out.append(dict(row=r, meas=m, sweep=sweep))
        return out

    def score_patch(self, rows, prep, raw):
        sibs, scored = [], []
        for item in raw:
            r, m = item['row'], item['meas']
            # per LANE, not per patch: a mini-jack patch reads two lanes and
            # they have floors of their own
            floor = self.floors.get(int(r['lane']))
            v, why, notes = self.sc.score(r, m, floor, item['sweep'], sibs,
                                          donor=int(r['donor']))
            sibs.append(dict(level_ref=r['level_ref'], h_db=m.get('h_db'),
                             h_deg=m.get('h_deg')))
            scored.append(dict(path=r['path'], patch=r['patch'], lead=r['lead'],
                               out=r['out'], **{'in': r['in']}, sub=r['sub'],
                               rows=r['rows'], verdict=v, why=why,
                               detail='; '.join(notes),
                               h_db=m.get('h_db'), h_deg=m.get('h_deg'),
                               thd_db=m.get('thd'), noise_db=m.get('noise'),
                               rms_db=m.get('rms')))
        return scored

    def where_is_it(self, lane, sweep, donor=None):
        """The plain sentence for a lead that went into the wrong socket.

        The donor strip is skipped for the same reason it is skipped in the
        isolation check: it carries the oscillator by construction, so it is
        always the loudest thing on the unit and would be named every time.
        """
        lit = [(dbv(v), k) for k, v in sweep.items()
               if k != donor and v and dbv(v) > -90]
        lit.sort(reverse=True)
        if not lit:
            return None
        top_db, top = lit[0]
        if top == lane:
            return None
        return 'MIC %d' % top

    # -- the pass ----------------------------------------------------------
    def run(self):
        self.standing()
        seq = []
        for (lead, block), patches in self.L.blocks():
            if self.only and lead not in self.only:
                continue
            seq.append(((lead, block), patches))
        prepared = None
        token = None
        pending = None                 # (rows, prep, raw) waiting to be scored
        for bi, ((lead, block), patches) in enumerate(seq):
            self.lead_card(lead, block, patches, bi + 1, len(seq))
            for pi, (pid, rows) in enumerate(patches):
                if prepared is None:
                    prepared = self.prepare(rows)
                    token = self.p.connect(pid, rows, self.g)
                prep, tok = prepared, token
                prepared, token = None, None
                raw = None
                t_hand = 0.0
                tries = 0
                while raw is None:
                    how, ans, dt = self.detect(rows, prep, tok)
                    t_hand += dt
                    if how == 'glass' and ans.get('button') in (
                            'pause', 'skip', 'ignore'):
                        self.p.done(tok)
                        if pending:
                            self.rows_out += self.score_patch(*pending)
                            pending = None
                        self.finish_early(rows, ans)
                        return self.rows_out
                    if how != 'timeout':
                        t1 = now()
                        raw = self.acquire(rows, prep)
                        break
                    # A wrong patch is a prompt, never a fail: find the lead,
                    # say where it is, and offer the same patch again.
                    sweep = self.u.meter_sweep(MIC_STRIPS)
                    where = self.where_is_it(int(rows[0]['lane']), sweep,
                                             int(rows[0]['donor']))
                    self.p.done(tok)
                    if pending:
                        self.rows_out += self.score_patch(*pending)
                        pending = None
                    tries += 1
                    again = (self.reprompt(pid, rows, where)
                             if tries <= MAX_RETRIES else None)
                    if again is None:
                        self.rows_out += self.nodata(rows, where, tries)
                        break
                    prep, tok = again
                if raw is None:
                    continue
                self.p.done(tok)
                # PIPELINE: the next patch goes up before this one is scored.
                nxt = self.next_patch(seq, bi, pi)
                if nxt is not None:
                    prepared = self.prepare(nxt[1])
                    token = self.p.connect(nxt[0], nxt[1], self.g)
                if pending:
                    self.rows_out += self.score_patch(*pending)
                pending = (rows, prep, raw)
                self.timing.append(dict(patch=pid, lead=lead, hand_s=t_hand,
                                        machine_s=now() - t1,
                                        subs=len(rows)))
                self.report_last(pid)
        if pending:
            self.rows_out += self.score_patch(*pending)
        self.teardown()
        return self.rows_out

    def next_patch(self, seq, bi, pi):
        """The next patch IN THE SAME BLOCK. A block boundary is a lead change
        and gets its own card, so nothing is prepared or prompted across one."""
        patches = seq[bi][1]
        return patches[pi + 1] if pi + 1 < len(patches) else None

    def lead_card(self, lead, block, patches, n, total):
        d = LEAD_TEXT.get(lead, {})
        lines = ['Take lead %s: %s.' % (lead, d.get('name', lead)),
                 '%d patches at this step.' % len(patches),
                 'Each one advances on its own as soon as the lead is in.']
        if d.get('wiring'):
            lines.append('Wiring: %s.' % d['wiring'])
        self.g.ask('station', 'Step %d of %d - %s' % (n, total, block), lines,
                   ['ack'], lead=lead)

    def reprompt(self, pid, rows, where):
        """A wrong patch is a prompt, never a fail (PW 2026-09-26)."""
        r = rows[0]
        self.log('%s: %s' % (pid, ('the tone came back on %s, not %s -- '
                                   'prompting again' % (where, r['in'])) if where
                             else ('nothing reached %s -- prompting again'
                                   % r['in'])))
        if where:
            lines = ['The tone came back on %s, not %s.' % (where, r['in']),
                     'Move the lead to %s.' % r['in']]
        else:
            lines = ['Nothing reached %s.' % r['in'],
                     'Check both ends of the lead are fully home.']
        lines.append('It advances on its own when the tone arrives.')
        ans = self.g.ask('instruct', 'Check the patch', lines, ['retry', 'fail'],
                         patch=pid)
        if ans['button'] in ('retry', 'done', 'ack'):
            prep = self.prepare(rows)
            return prep, self.p.connect(pid, rows, self.g)
        return None

    def nodata(self, rows, where, tries=0):
        why = ('the lead was in %s and never in %s' % (where, rows[0]['in'])
               if where else 'no tone reached %s' % rows[0]['in'])
        if tries:
            why += ' after %d attempt%s' % (tries, '' if tries == 1 else 's')
        return [dict(path=r['path'], patch=r['patch'], lead=r['lead'],
                     out=r['out'], **{'in': r['in']}, sub=r['sub'],
                     rows=r['rows'], verdict=NODATA, why=why, detail='',
                     h_db=None, h_deg=None, thd_db=None, noise_db=None,
                     rms_db=None) for r in rows]

    def report_last(self, pid):
        done = [x for x in self.rows_out if x['patch'] != pid]
        if not done:
            return
        last = done[-1]
        self.log('%s %s: %s' % (last['patch'], last['verdict'], last['why']))

    def finish_early(self, rows, ans):
        self.log('the pass stopped at %s (%s)'
                 % (rows[0]['patch'], ans.get('button')))
        self.teardown()

    def teardown(self):
        """The oscillator off and the routes shut, always.

        S115's lesson, and it cost PW a unit that hissed: a route asserted by a
        test and never taken down stays asserted for as long as the unit is
        powered. Everything this station opened is closed here.
        """
        try:
            self.u.osc(on=False)
            self.u.write(self.L.routes['_standing_close'], verify=False)
        except Exception as e:                       # never mask the real error
            self.log('teardown could not complete: %s' % e)


LEAD_TEXT = {
    'K1': dict(name='the XLR lead', wiring='an ordinary balanced XLR lead'),
    'K2': dict(name='the jack-to-XLR lead',
               wiring='6.35 mm TRS one end, male XLR the other'),
    'K3': dict(name='the XLR-to-mini-jack lead',
               wiring='female XLR one end, 3.5 mm stereo jack the other'),
    'K4': dict(name='the XLR-to-jack lead',
               wiring='female XLR one end, 6.35 mm TRS the other'),
    'K5': dict(name='the 150 ohm plug',
               wiring='a male XLR plug with 150 ohm inside it'),
}


# ---------------------------------------------------------------------------
# The dry run
# ---------------------------------------------------------------------------
# WHY A SIMULATION AT ALL. This session cannot plug a lead in. What it CAN do
# is prove that the loop reaches every outcome it claims to -- a clean pass, a
# lead in the wrong socket, a dead path, a swapped stereo pair, a null that
# does not null, a phase too near the boundary to call -- and put a number on
# the operator's seconds. The model below is deliberately crude about the
# audio and exact about the TIMING: it reproduces the window arithmetic, the
# settle, the cell writes and the poll interval, so the machine seconds it
# reports are the ones the real loop will spend. The hand seconds are a
# parameter, because they are a fact about a person and not about this code.
CELL_WRITE_S = 0.004          # one SPI write plus its read-back, measured shape
PEEK_S = 0.003                # one diag peek, ditto


class SimUnit:
    """A D24 that exists only in arithmetic."""

    def __init__(self, world):
        self.w = world
        self.route = {}
        self.osc_on = False
        self.osc_chan = None
        self.osc_freq = None
        self.osc_level = -12.0
        self.lane = 0
        self.writes = 0

    # -- the same surface as Unit -----------------------------------------
    def write(self, specs, verify=True):
        for spec in specs:
            name, _, val = spec.partition('=')
            self.route[name] = val
            self.writes += 1
            nap(CELL_WRITE_S)
        return []

    def osc(self, chan=None, freq=None, level_dbfs=None, on=None):
        if chan is not None:
            self.osc_chan = chan
        if freq is not None:
            self.osc_freq = freq
        if level_dbfs is not None:
            self.osc_level = level_dbfs
        if on is not None:
            self.osc_on = on
        nap(CELL_WRITE_S * 4)

    def meas_chan(self, lane):
        self.lane = lane
        nap(CELL_WRITE_S)

    def driven(self):
        """Which aux/main leg the route currently opens, as the list names it."""
        d = self.osc_chan
        out = []
        for k, v in self.route.items():
            if not k.startswith('Chan%03d' % (d or 0)):
                continue
            if k.endswith('MainOn001') and v == '1':
                out.append('main')
            elif 'AuxOn' in k and v == '1':
                out.append('aux%d' % int(k[-3:]))
            elif k.endswith('CtrOn001') and v == '1':
                out.append('ctr')
        return sorted(out)

    def level_at(self, lane):
        """dB at `lane`, from the world's idea of what is plugged where.

        THE DONOR STRIP READS THE OSCILLATOR. The stimulus replaces that
        strip's input, so its meter sits at the drive level for the whole
        pass whatever is or is not plugged in. The model says so because the
        bench found it and the model had not: on MW-D24-2 the donor read
        -12.0 dBFS while real paths read -15, which made the donor the
        loudest lane on the unit and would have turned every patch into a
        mis-patch report.
        """
        if self.osc_on and lane == self.osc_chan:
            return self.osc_level
        return self.w.level(self.driven(), lane, self.osc_on, self.osc_level)

    def meter_peak(self, strip):
        nap(PEEK_S)
        db = self.level_at(strip)
        return 10 ** (db / 20.0) if db > -200 else 0.0

    def meter_sweep(self, strips):
        return dict((s, self.meter_peak(s)) for s in strips)

    def measure(self, freq, level_dbfs, windows=READ_WINDOWS,
                settle=SETTLE_WINDOWS):
        nap(WIN_S * (settle + windows))
        db = self.level_at(self.lane)
        out = dict(rms=db, thd=self.w.thd, noise=db - 60.0, n=windows)
        if self.osc_on and db > -200:
            out['h_db'] = db - (level_dbfs if level_dbfs is not None else 0.0)
            out['h_deg'] = self.w.phase(self.driven(), self.lane)
            out['coh_dbfs'] = db
        return out


class World:
    """What is actually plugged in, and what is wrong with the unit.

    `faults` is how every branch of the scorer gets exercised without a unit:

        dead:<in>        the path to that input carries nothing
        mispatch:<in>    the operator puts the lead in the WRONG socket once
        swap:<jack>      that stereo jack has tip and ring crossed
        nonull:<jack>    its two channels are 4 dB apart, so the null fails
        edge:<in>        the phase on that lane lands on the decision boundary
    """

    REF_PHASE = 42.0             # this unit's loop phase at 1 kHz, arbitrary
    thd = -72.0

    def __init__(self, faults=(), quiet_floor=-96.0):
        self.faults = set(faults)
        self.floor = quiet_floor
        self.plugged_in = None
        self.plugged_out = None
        self.plugged_lanes = set()
        self.mispatched = set()

    def plug(self, out_port, in_port, lanes):
        self.plugged_out, self.plugged_in = out_port, in_port
        self.plugged_lanes = set(lanes)

    def unplug(self):
        self.plugged_in = self.plugged_out = None
        self.plugged_lanes = set()

    def level(self, driven, lane, osc_on, osc_level):
        if not osc_on:
            # the noise rows: an open input is noisier than a terminated one
            terminated = (self.plugged_in is not None)
            return self.floor + (0.0 if terminated else 9.0)
        if not driven or lane not in self.plugged_lanes:
            return self.floor
        if 'dead:%s' % self.plugged_in in self.faults:
            return self.floor
        legs = len(driven)
        base = osc_level - 3.0            # the unit's own loop gain, flat
        if self.single_ended:
            base -= 6.02
            if legs > 1:                  # the null: two legs cancelling
                base -= 34.0
                if 'nonull:%s' % self.plugged_out in self.faults:
                    base += 30.0
        return base

    @property
    def single_ended(self):
        return bool(self.plugged_out and self.plugged_out.startswith(
            ('AUX A', 'MONITOR', 'MINI-JACK')))

    def phase(self, driven, lane):
        d = self.REF_PHASE
        inverted = False
        if ('edge:%s' % self.plugged_out in self.faults) and self.single_ended:
            # only the judged readings, never the reference one: a lane whose
            # reference moved with it would show no difference at all
            return d + 90.0
        if self.single_ended and driven and driven[0].startswith('aux'):
            # the ring leg reads inverted against the tip: that is the lead
            k = int(driven[0][3:])
            inverted = (k % 2 == 0)
        if 'swap:%s' % self.plugged_out in self.faults:
            inverted = not inverted
        return d + (180.0 if inverted else 0.0)


class SimGlass:
    """The glass, with nobody behind it: every dialog is acknowledged at once
    and no patch is ever answered by a button, because the whole point is that
    the loop advances on the UNIT."""

    def __init__(self, log):
        self.log = log
        self.seq = 0
        self.prompts = []

    def post(self, kind, title, lines, buttons, **extra):
        self.seq += 1
        self.prompts.append((kind, title, list(lines)))
        return list(buttons) + ['skip', 'ignore', 'pause']

    def poll(self, btns):
        return None

    def ask(self, kind, title, lines, buttons, **extra):
        self.post(kind, title, lines, buttons, **extra)
        return dict(button=buttons[0])

    def clear(self):
        pass

    def progress(self, text):
        self.log(text)


class SimPatcher(ManualPatcher):
    """The operator's hands: a fixed number of seconds, then the lead is in."""

    def __init__(self, glass, world, hand_s, log):
        ManualPatcher.__init__(self, glass)
        self.w = world
        self.hand_s = hand_s
        self.log = log
        self.at = None

    def connect(self, patch, rows, glass):
        tok = ManualPatcher.connect(self, patch, rows, glass)
        r = rows[0]
        self.w.unplug()
        self.pending = (r['out'], r['in'],
                        sorted({int(x['lane']) for x in rows}), patch)
        self.at = now() + self.hand_s
        return tok

    def poll(self, token):
        if self.at is not None and now() >= self.at:
            out, inp, lanes, patch = self.pending
            key = 'mispatch:%s' % inp
            if key in self.w.faults and patch not in self.w.mispatched:
                self.w.mispatched.add(patch)
                wrong = lanes[0] % 24 + 1    # the socket next door
                self.w.plug(out, 'MIC %d' % wrong, [wrong])
            else:
                self.w.plug(out, inp, lanes)
            self.at = None
        return None


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
RESULT_COLUMNS = ('path', 'patch', 'lead', 'out', 'in', 'sub', 'rows',
                  'verdict', 'why', 'detail', 'h_db', 'h_deg', 'thd_db',
                  'noise_db', 'rms_db')


def write_results(path, rows):
    with open(path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, RESULT_COLUMNS, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow(dict((k, ('%.3f' % v) if isinstance(v, float) else v)
                            for k, v in r.items()))
    return path


def time_table(station, plist, hand_s):
    """Seconds per patch type, and the projected pass.

    `hand` is the operator; everything else is this loop. The split matters
    because only one of the two is worth optimising further, and the table is
    what says which.
    """
    by_lead = {}
    for t in station.timing:
        d = by_lead.setdefault(t['lead'], dict(n=0, machine=0.0, subs=0))
        d['n'] += 1
        d['machine'] += t['machine_s']
        d['subs'] += t['subs']
    return by_lead


def print_time_table(by_lead, hand_s, plist, out=sys.stdout):
    tot_m = sum(d['machine'] for d in by_lead.values())
    tot_n = sum(d['n'] for d in by_lead.values())
    out.write('\n  lead  patches  checks   machine s   per patch   hand s @ %.0f s\n'
              % hand_s)
    out.write('  ' + '-' * 62 + '\n')
    for lead in ('K1', 'K5', 'K4', 'K2', 'K3'):
        d = by_lead.get(lead)
        if not d:
            continue
        out.write('  %-4s  %7d  %6d  %10.1f  %10.2f  %12.0f\n'
                  % (lead, d['n'], d['subs'], d['machine'],
                     d['machine'] / d['n'], d['n'] * hand_s))
    out.write('  ' + '-' * 62 + '\n')
    out.write('  all   %7d  %6d  %10.1f  %10.2f  %12.0f\n'
              % (tot_n, sum(d['subs'] for d in by_lead.values()), tot_m,
                 tot_m / max(tot_n, 1), tot_n * hand_s))
    out.write('\n  projected pass: %.0f s hands + %.0f s machine = %.1f min\n'
              % (tot_n * hand_s, tot_m, (tot_n * hand_s + tot_m) / 60.0))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def cmd_list(plist):
    for (lead, block), patches in plist.blocks():
        print('\n== %s  %s  (%d patches)' % (lead, block, len(patches)))
        for pid, rows in patches:
            r = rows[0]
            subs = ('  [%s]' % ', '.join(x['sub'] for x in rows)
                    if len(rows) > 1 else '')
            print('   %-5s %-46s lane %-3s%s'
                  % (pid, r['prompt'], r['lane'], subs))
    print('\n%d patches, %d measurements'
          % (len(plist.patches), len(plist.paths)))
    return 0


def cmd_simulate(a, plist):
    global CLOCK
    CLOCK = VirtualClock()
    log = (lambda s: print('   .. %s' % s)) if a.verbose else (lambda s: None)
    world = World(faults=a.fault or ())
    glass = SimGlass(log)
    unit = SimUnit(world)
    patcher = SimPatcher(glass, world, a.hand, log)
    st = Station(plist, unit, patcher, glass, Limits.load(plist.dir), log=log,
                 blocks=a.block)
    rows = st.run()
    counts = {}
    for r in rows:
        counts[r['verdict']] = counts.get(r['verdict'], 0) + 1
    print('\nDRY RUN (no unit): %d measurements in %d patches'
          % (len(rows), len(st.timing)))
    print('  ' + ', '.join('%s %d' % (k, v) for k, v in sorted(counts.items())))
    if a.fault:
        print('  faults injected: %s' % ', '.join(a.fault))
        for r in rows:
            if r['verdict'] != PASS:
                print('    %-5s %-22s %-9s %s'
                      % (r['patch'], r['in'], r['verdict'], r['why']))
    print_time_table(time_table(st, plist, a.hand), a.hand, plist)
    if a.out:
        print('\nwrote %s' % write_results(a.out, rows))
    if a.strings:
        with open(a.strings, 'w', encoding='utf-8') as fh:
            fh.write('# every operator-facing string this station can produce,\n'
                     '# for the internal-vocabulary check. Generated, not written.\n\n')
            for kind, title, lines in glass.prompts:
                fh.write('%s\n' % title)
                for ln in lines:
                    fh.write('  %s\n' % ln)
            for r in rows:
                fh.write('%s\n' % r['why'])
                if r['detail']:
                    fh.write('%s\n' % r['detail'])
        print('wrote %s' % a.strings)
    return 0


def cmd_run(a, plist):
    sys.path.insert(0, HERE)
    import d24_runall as RA                          # noqa: E402
    glass = RA.Glass(a.dir, stdin=a.stdin)
    unit = Unit(symdir=a.symdir)
    patcher = pick_patcher(glass, a.back_end)
    st = Station(plist, unit, patcher, glass, Limits.load(plist.dir),
                 log=glass.progress, blocks=a.block)
    try:
        rows = st.run()
    finally:
        try:
            st.teardown()
        except Exception:
            pass
    out = a.out or os.path.join(a.dir, 'patch-results.csv')
    print('wrote %s' % write_results(out, rows))
    print_time_table(time_table(st, plist, a.hand), a.hand, plist)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--list-dir', help='where patch-paths.csv lives')
    ap.add_argument('--list', action='store_true', help='print the plan, stop')
    ap.add_argument('--simulate', action='store_true',
                    help='walk the whole pass with no unit')
    ap.add_argument('--run', action='store_true', help='the real pass')
    ap.add_argument('--block', action='append',
                    help='only this lead (K1..K5); repeatable')
    ap.add_argument('--fault', action='append',
                    help='inject a fault in --simulate: dead:<in>, '
                         'mispatch:<in>, swap:<jack>, nonull:<jack>, edge:<in>')
    ap.add_argument('--hand', type=float, default=5.0,
                    help='seconds per hand move, for the projection')
    ap.add_argument('--out', help='write the per-path results here')
    ap.add_argument('--strings',
                    help='dump every operator-facing string, for --check-md')
    ap.add_argument('--dir', default='/home/app/selftest/runall',
                    help='the glass directory (--run)')
    ap.add_argument('--symdir', default=FACTORY_TEST_PAIR_DIR)
    ap.add_argument('--back-end', default='auto', choices=('auto', 'harness'))
    ap.add_argument('--stdin', action='store_true')
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args(argv)
    plist = PatchList(find_list_dir(a.list_dir))
    if a.list:
        return cmd_list(plist)
    if a.simulate:
        return cmd_simulate(a, plist)
    if a.run:
        return cmd_run(a, plist)
    ap.error('one of --list, --simulate or --run')


if __name__ == '__main__':
    sys.exit(main())
