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

  * NOBODY PRESSES ENTER, and since PW's ruling of 2026-09-28 that is the whole
    of it: "when input signal cables are moved, they are automatically detected,
    and if so they can be measured and pass/failed and prompt next move without
    a required enter; a button would only need to be pressed to move on if
    signal is not detected." The prompt goes up, the tone is already running,
    and the runner watches the input the patch is supposed to reach. The lead
    goes in, the lane holds still for a quarter second (DETECT_STABLE_BLOCKS --
    nothing is graded mid-insertion), the step is over, and the operator is
    already moving to the next socket while the reading is taken. There is NO
    ENTER on a detected patch: the one button on the screen is NO SIGNAL, which
    is what an operator presses when they have made a patch and nothing came
    through. A tone that arrives on the WRONG input is named while they are
    standing there -- "Signal on MIC 7, expected MIC 5" -- and is never graded
    as the row that was asked for. `--confirm-enter` is the 09-26 loop, kept
    for a before/after timing run.
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
factory already runs (PW ruling S116 Q3: `factory-test-v2`, the pair at
/home/app/loopthd/s122) -- d24_selftest.py asserts it and so does this file.
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
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
import d24_live as LV                                 # noqa: E402
import d24_chain as CH                               # noqa: E402

LIST_DIR_CANDIDATES = (os.path.join(ROOT, 'MW', 'D24', 'DSP', 's121'),
                       os.path.join(HERE, 's121'),
                       '/home/app/selftest/s121')
# WHICH LIST A RUN THE WIZARD'S OWN START LAUNCHES USES (S126, PW 2026-09-27).
# `d24-testui`'s START runs `d24_runall.py` through systemd-run with no
# arguments, so `--patch-list-dir` cannot reach it and the fallback above picks
# the FULL list. On a unit whose inputs are not all populated that walks the
# operator across sockets with no front end, every one of them NO DATA.
#
# So the unit says which list it has, in a file, exactly as it already says
# which DSP pair it has (`pair.conf`, d24_selftest.PAIR_CONF). One line, the
# directory; blank or missing means the fallback, which is the full list and
# the right answer for a fully populated unit. A bench session that writes it
# owns removing it.
LIST_CONF = '/home/app/selftest/list.conf'

FS = 48000.0
# TEST_MEAS integrates over 4,096 samples (dsp_codegen.py TEST_MEAS_WIN), so a
# window is 85.3 ms and a changed MeasChan needs two of them before the fit
# means anything -- the first window after any change has no fit yet and reads
# ThdResult 0.00 dB by construction.
WIN_S = 4096.0 / FS
# TWO WINDOWS IS NOT ENOUGH, AND IT LOOKS LIKE DISTORTION WHEN IT ISN'T.
# The fit behind ThdResult subtracts the PREVIOUS window's fitted sine sample
# by sample, so a window in which anything moved -- a ramped send, a bus
# master, a pan, or just the tap arriving somewhere new -- is scored as
# distortion. Measured on MW-D24-2, 2026-09-26, sweeping the settle over the
# same three routes:
#
#     settle    aux 1 THD+N    aux 2 THD+N    main L THD+N
#          2     -19.21 dB      -24.74 dB       -3.75 dB     <- nonsense
#          4    -116.16 dB     -115.50 dB     -115.51 dB
#          6    -115.51 dB     -115.50 dB     -116.16 dB
#         12    -116.16 dB     -116.16 dB     -115.51 dB
#
# The LEVEL read -15.01 dBFS in every one of those, settle 2 included: it was
# never the level that was wrong. Four is where it settles, so four is the
# floor here and a route change -- which moves more -- gets six.
SETTLE_WINDOWS = 4
READ_WINDOWS = 2
ROUTE_SETTLE_WINDOWS = 6

# HOW LONG THE TEST_MEAS WINDOW COUNTER MAY SIT STILL BEFORE A WAIT-FOR-IT
# LOOP CALLS IT DEAD RATHER THAN SLOW (S155). A live counter turns over every
# WIN_S; this is twenty of them, which nothing this station asks for (the
# biggest settle/read request in the tree is a handful of windows) should ever
# need. A STALE SYMBOL MAP (S155, fixed in e97cd357) points `_seq()` at a word
# that never moves, so the counter it is "waiting to turn over" literally
# never does -- measured on MW-D24-2: `Unit.measure()`'s bare `nap()` loops sat
# there forever with the glass on "working - please wait" and nothing to press.
MEASURE_STALL_S = 20 * WIN_S

# THE GAIN STEP'S OWN READING (S125). Measured on MW-D24-2, 2026-09-26, by
# stepping a known level and reading the node at every settle length, five
# times each -- and by taking the same reading with the level there and with
# it gone, which is what an open or shorted element looks like to the lane:
#
#   settle windows   cost      live reading        dead reading    separation
#            0, 1    0.034 s   -61.02 (the window BEFORE the change)  wrong
#            1, 1    0.078 s   -26.78 +/-3.49      -23.68 +/-2.22    -3.10 dB
#            2, 1    0.167 s   -21.64 +/-0.02     -116.28 +/-0.46    94.64 dB
#            2, 2    0.245 s   -21.64 +/-0.01     -116.33 +/-0.30    94.68 dB
#            4, 2    0.422 s   -21.64 +/-0.01     -116.23 +/-0.45    94.58 dB
#
# Two settle windows is where the node stops reporting the window the change
# happened in; one read window after that is already exact to 0.02 dB, and
# nothing past it buys anything. So the step pays 167 ms and gets 95 dB of
# separation between a working element and a dead one.
GAIN_SETTLE_WINDOWS = 2
GAIN_READ_WINDOWS = 1

# ---------------------------------------------------------------------------
# PRE-ARMING THE READING (PW 2026-09-27, ruling d; review §2.4)
# ---------------------------------------------------------------------------
# "On tone rows, take the reading as soon as the detector sees the tone arrive.
# At ENTER, one meter peek must agree within 0.5 dB, and then the verdict shows
# at once. If it does not agree, re-measure: that patch loses the saving, not
# the correctness."
#
# ENTER STILL GATES THE VERDICT AND THE ADVANCE. Nothing is recorded before
# ENTER, nothing is put on the screen before ENTER, and a patch whose armed
# reading is not confirmed is read again -- so the worst a pre-arm can do is
# cost the 0.27 s it was trying to save.
#
# WHAT THE CONFIRMATION IS. One strip-meter peek, which needs no settling
# window at all (`Unit.meter_peak`), taken at ENTER and compared with the same
# peek taken the instant the armed reading finished. It asks one question --
# did the connection stay where it was while the hand let go? -- and it is the
# only question a pre-arm opens. A half-seated connector that settles, moves or
# falls out between the two shows up here; one that is moving DURING the armed
# reading shows up as a window spread instead (`rms_spread`, above).
PREARM_AGREE_DB = 0.5
# The armed reading is thrown away if its own windows disagree by more than
# this: that is a reading taken through a connector that was still moving.
PREARM_STABLE_DB = 0.5

# ---------------------------------------------------------------------------
# SIGNAL ARRIVAL IS THE GO-AHEAD (PW 2026-09-28, pipeline.md ~18:1x BST)
# ---------------------------------------------------------------------------
# "when input signal cables are moved, they are automatically detected, and if
# so they can be measured and pass/failed and prompt next move without a
# required enter; a button would only need to be pressed to move on if signal is
# not detected."
#
# This SUPERSEDES the 09-26 review's "ENTER still decides" for every patch the
# detector can see, and it is why `--auto-advance` is no longer a flag that is
# off: it is what the station does, and `--confirm-enter` is the old loop kept
# for a before/after timing run and for nothing else.
#
# THE STABILITY WINDOW, AND WHY THERE HAS TO BE ONE. The detector fires on the
# FIRST poll in which the lane has risen, and the first poll in which a lane has
# risen is in the middle of the operator's hand movement: an XLR latches after
# the pins mate, a TRS is wiped along its full travel, and a mini-jack passes
# through both legs shorted on the way in. Ending the step there would hand the
# reading a connector that is still moving -- which is the same fault the
# pre-arm's `PREARM_STABLE_DB` exists to catch on the ENTER path, only now there
# is no ENTER behind it to catch it. So the step ends when the lane has been
# PRESENT AND STEADY for a window, and not when it first went loud.
#
# N = 3 BLOCKS, and the block is the instrument's own: TEST_MEAS integrates over
# 4,096 samples, so WIN_S is 85.3 ms and three of them are 256 ms. Three,
# because:
#
#   * it must outlast the mechanical event. S125 measured the strip meter's
#     decay at 6.52 dB/s and the gain step needs 167 ms (two settle windows plus
#     one read) to read the node honestly; 256 ms is longer than both, so a
#     window that satisfies this test cannot be a transient the meter is still
#     holding.
#   * it must not be longer than the operator's own hand. The projected hand
#     move is 3-8 s (S123's table), so 256 ms is 3-8 % of one step: the whole
#     window is spent while their hand is still on the connector and it comes
#     off the pass's clock, not out of it.
#   * and it must be more than one block, or it is not a window at all: one
#     poll is what the old detector already did.
#
# STEADY IS 1.0 dB ACROSS THE WINDOW. The instrument here is the strip meter,
# which is a peak-hold latch and not the measurement node, so it is coarser than
# the 0.5 dB the pre-arm holds the node to -- a steady tone reads flat on it
# (peak hold on a continuous sine does not decay), and anything that moves the
# connector moves it by much more than a dB. 1.0 dB is twice PREARM_STABLE_DB on
# an instrument that is at least twice as coarse; a reading that passes it and
# is still wrong is caught downstream by `rms_spread` on the node itself.
DETECT_STABLE_BLOCKS = 3
DETECT_STEADY_DB = 1.0
# The detector's poll, and it is NOT the whole cadence -- the read itself costs
# something, and how much depends on which instrument the lane has:
#
#   * the 24 mic strips have a meter word, which needs no settling window at all
#     (S121 measured all twenty-four at 32 ms), so a poll is 50 ms + ~1 ms and
#     the 256 ms window carries five or six samples.
#   * the three codec return lanes -- the talkback XLR and the two mini-jack legs
#     -- have NO meter of their own, so `watch` reads the measurement node's own
#     RmsResult instead, and that costs one 85.3 ms window. A poll there is
#     ~135 ms and the same 256 ms window carries TWO samples.
#
# Which is why the count the window insists on is TWO and not three: two is what
# makes it a window rather than a point, and it is the floor the coarsest lane on
# the unit can actually deliver. A three-sample rule reads as stricter and is
# not: it would simply never be satisfiable on the talkback or either mini-jack
# leg, so those three patches would run to the timeout on a good unit. (Measured,
# not reasoned: the dry run does exactly that, and did, until this was two.)
DETECT_POLL_S = 0.05
DETECT_STABLE_SAMPLES = 2

# THE 150 OHM STEP, READ AGAINST THE OPEN INPUT IT WAS PROMPTED ON (S158).
# In the 150 ohm pass (PW 2026-10-01) the socket is EMPTY when the prompt goes
# up, so the first readings ARE the open input: TERM_REF_READINGS of them,
# medianed, are the reference. An open input at gain 63 is impulsive -- MIC 1
# over 20 s on 2026-10-01: single windows up to 5.7 dB over its median and
# down to 1.5 dB under it -- so the lane is followed on the median of the last
# three readings, never on one.
#
# The plug is in when the lane settles `detect_drop_db` under the open input,
# OR when it settles TERM_SMALL_STEP_DB under it AFTER an insertion burst (one
# window TERM_BURST_DB or more over the open input -- the contacts making,
# +20..+54 dB on 20 of the 24 insertions PW made on 2026-10-01, never over
# +5.7 dB on an open input left alone). The small step is what MIC 2, 3 and 4
# need: their terminated noise sits only 1.8-2.7 dB under their open noise
# (S158 table), where every other input drops 3.3-15.6 dB. A burst counts for
# TERM_BURST_HOLD_S: the settle follows the contacts within half a second on
# every insertion recorded, and a touch long ago must not license a drift.
# ENTER is on the screen the whole time and always ends the step.
TERM_REF_READINGS = 3
TERM_REF_SPAN = 20
TERM_BURST_DB = 10.0
TERM_BURST_HOLD_S = 3.0
TERM_SMALL_STEP_DB = 1.0

# HOW OFTEN THE OTHER TWENTY-THREE LANES ARE LOOKED AT WHILE WAITING (PW
# 2026-09-28: "a tone arriving on an input OTHER than the one asked for is named
# on the screen"). The sweep is one peeked word per strip and S121 measured all
# twenty-four at 32 ms, so a second between sweeps costs 3 % of the detector's
# own time and names a misplaced lead within a second of it going in -- which is
# while the operator's hand is still there, not after they have walked away.
# Before this, the sweep only ran when a step had already FAILED to detect, so a
# lead in the wrong socket was silent for the whole 20 s timeout.
WRONG_INPUT_POLL_S = 1.0
# THE TRS PAIR PROBE (S159): how often a stereo TRS patch that has not arrived
# drives the other three pairs' tips to find which pair the jack carries. One
# probe is three route writes and three settled windows, about 2 s, so it runs
# at the timeout and then every this many seconds while the step waits.
TRS_PROBE_EVERY_S = 10.0

PASS, FAIL, NODATA, SKIPPED = 'PASS', 'FAIL', 'NO DATA', 'SKIPPED'
IGNORED = 'IGNORED'
MISPATCH = 'MISPATCH'
# worst-first, for one patch's own verdict (S159 re-run record)
RANK_PATCH = {FAIL: 5, MISPATCH: 4, NODATA: 3, SKIPPED: 2, IGNORED: 1,
              PASS: 0}
# the 150 ohm pass's EIN capture (S159) -- see ein_bands() below
EIN_CAP_N = 16384            # 2.93 Hz bins; 0.65 s to fill and read (S160)
EIN_CAPS = 2
EIN_SETTLE_MIN_S = 2.0       # after the plug, before the node is trusted
EIN_SETTLE_MAX_S = 12.0      # ... and the most a settle may take
EIN_SETTLE_AGREE_DB = 0.5    # two successive windows this close = settled
FS_SINE_DB = 3.0103          # mean square of a full-scale sine is -3.01 dBFS

# The ONLY button that ends a pass. S127: `skip` and `ignore` used to sit in
# this set beside `pause`, so the one button an operator reaches for when a
# patch will not pass ended the whole walk, wrote a report of the handful of
# patches done so far, and put "Press START to run the test again" on the
# glass -- and START then began at patch 1 of 59 and overwrote that report.
# PW saw that as "the test restarted after a single fail". A fail, a skip and
# an ignore are all about ONE PATCH and the walk carries on.
STOP_BUTTONS = ('pause',)
# The buttons that are a decision about the patch that is up, and what each
# one records. Anything else the glass sends back is not a decision this
# station understands, and it re-offers the patch rather than ending the run.
PATCH_DECISIONS = {'skip': SKIPPED, 'ignore': IGNORED}

# The factory-test pair, the same constants d24_selftest.py asserts against.
# THE PAIR THAT IS BOOTED, not a hard-wired one (hub 2026-09-30). The symbols
# (TEST_MEAS window counter, osc, meters) move with every image: on S154's
# factory-test-v4 the old s122 default pointed `_seq()` at a word that never
# changes and the station waited for ever on its first floor reading.
# `pair.conf` names the booted pair (d24_selftest.PAIR_CONF); s122 is only the
# fallback when that file is missing.
def _booted_pair(conf='/home/app/selftest/pair.conf',
                 fallback='/home/app/loopthd/s122'):
    try:
        d = open(conf).read().strip()
        return d if d and os.path.isdir(d) else fallback
    except OSError:
        return fallback


FACTORY_TEST_PAIR_DIR = _booted_pair()
OSC_SYM = '_osc_blk_q_C1_TEST_OSC'
# The factory glass directory: RUN ALL's screen, dialogs and lock (S158).
GLASS_DIR = '/home/app/selftest/runall'


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
def list_conf(path=LIST_CONF):
    """The list directory this unit says it has, or None."""
    try:
        with open(path) as fh:
            for ln in fh:
                ln = ln.split('#', 1)[0].strip()
                if ln:
                    return ln
    except OSError:
        pass
    return None


def find_list_dir(explicit=None):
    tried = []
    for d in ((explicit,) if explicit else (list_conf(),) + LIST_DIR_CANDIDATES):
        if not d:
            continue
        tried.append(d)
        if os.path.exists(os.path.join(d, 'patch-paths.csv')):
            return d
    # A conf file that names a directory with no list in it is a bench mistake
    # and has to be loud: silently falling through to the full list is how an
    # operator ends up walking sockets this unit does not have.
    named = list_conf()
    if named and not explicit and named not in [
            d for d in tried if os.path.exists(os.path.join(d, 'patch-paths.csv'))]:
        raise SystemExit('%s names %s, and there is no patch-paths.csv there'
                         % (LIST_CONF, named))
    raise SystemExit('patch-paths.csv not found; looked in %s'
                     % ', '.join(tried))


def split_inputs(s):
    """`--trial-inputs "MIC 3, MIC 7"` -> ['MIC 3', 'MIC 7'], or None."""
    if not s:
        return None
    return [x.strip() for x in str(s).split(',') if x.strip()]


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
        # The seven gain steps and what each one should read. Generated from
        # defs' own mic gain law; the runner carries no gain number of its own.
        self.gain = {}
        gp = os.path.join(d, 'patch-gain-steps.csv')
        if os.path.exists(gp):
            for r in read_csv(gp):
                self.gain[int(r['code'])] = dict(
                    expected_db=float(r['expected_db']), source=r['source'],
                    drive_dbfs=(float(r['drive_dbfs'])
                                if r['drive_dbfs'] else None))
        self.routes = dict((r['route'], r['cells'].split(';'))
                           for r in read_csv(os.path.join(d, 'patch-routes.csv')))
        # THE PARKED KIT (S126, ruling c). Generated beside the paths, in the
        # order the operator is walked through it at START. An older list
        # directory has no such file and the station runs without one -- there
        # is then simply nothing to park and nothing to say about it.
        self.kit = []
        kp = os.path.join(d, 'patch-kit.csv')
        if os.path.exists(kp):
            self.kit = read_csv(kp)
        self.patches = []
        for r in self.paths:
            if not self.patches or self.patches[-1][0] != r['patch']:
                self.patches.append((r['patch'], []))
            self.patches[-1][1].append(r)

    def blocks(self):
        """The patches grouped the way the OPERATOR meets them.

        Grouped by the block, not by the lead: since PW's ruling of
        2026-09-26 the input walk alternates between the XLR lead and the
        150 ohm plug at every input -- lead in, seven gain steps, lead out,
        plug in, noise -- and that is one stretch of work with one pair of
        leads in the operator's hands, not forty-eight blocks.
        """
        out = []
        for pid, rows in self.patches:
            key = (rows[0]['lead'], rows[0]['block'])
            if not out or out[-1][0][1] != key[1]:
                out.append((key, []))
            out[-1][1].append((pid, rows))
        return out

    def standing(self, donors=None):
        return (list(self.routes['_standing_close'])
                + self.routes['_standing_strips']
                + self.routes['_standing_masters'])

    def bypass(self):
        """The processing bypass (S154, PW ruling 2026-09-30): every
        processing stage on every path a patch uses, derived from the defs by
        gen_patch_paths.cells_processing_bypass. The station reads each cell
        before writing it and puts the found value back at handback. A list
        generated before S154 has no such row, and then there is nothing to
        bypass and nothing to restore."""
        return list(self.routes.get('_standing_bypass', []))


# ---------------------------------------------------------------------------
# The unit
# ---------------------------------------------------------------------------
class MeasureStalled(Exception):
    """The TEST_MEAS window counter has not moved for MEASURE_STALL_S.

    Raised out of `Unit.measure()`'s two wait-for-counter loops (S155) --
    every caller reaches the glass through the same generic exception
    reporting the station already had (AutoPhase._go and its like), so this
    class exists only to give that report a name a reader can recognise
    instead of a silent hang.
    """


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

    # Where the processing bypass keeps what it FOUND (S154) until the
    # handback has written it back: a pass that dies between the two leaves
    # this file behind, and the next pass restores from it instead of
    # reading the bypassed zeros as the product's settings.
    bypass_state = '/home/app/selftest/bypass-found.json'

    def __init__(self, symdir=FACTORY_TEST_PAIR_DIR, landed=None):
        sys.path.insert(0, '/home/app/dspboot')
        import dsp4_scope as S                       # noqa: E402
        self.S = S
        self.symdir = symdir
        landed = landed or '/home/app/dspboot/landed-d24.json'
        self.cells = json.load(open(landed))['cells']
        self._chips = {}
        self._meas_addr = {}
        # WHEN SOMETHING LAST MOVED ON THE WIRE (S125). A settle window exists
        # because the node's fit reads a window in which anything changed as
        # distortion -- so it is owed from the CHANGE, not from the call. The
        # last written value of every cell is kept here so a write that lands
        # on the value already there is not counted as a change: `matrix-app`
        # is down for the whole session and this object is the only writer.
        self._last = {}
        self.moved_at = now()
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

    def mark_moved(self):
        """Something changed on the wire just now. See `settle_owed`."""
        self.moved_at = now()

    def settle_owed(self, full):
        """How many of `full` settle windows are STILL owed (S125).

        `measure()` counts its settle from the call. Every window it waits is
        a window the operator waits too, and it is only owed while the change
        that caused it is still inside the node's integration. The route for a
        patch is written before the prompt goes up and the operator then takes
        seconds to fit a lead, so by the time the reading is taken the wire has
        been still for tens of windows and NOTHING is owed -- the run just did
        not know that. It does now.

        The clock starts at the change, not the call, and a reading that
        arrives before the windows are up still pays the remainder.
        """
        if self.moved_at is None:
            return 0
        spent = (now() - self.moved_at) / WIN_S
        return max(0, int(math.ceil(full - spent)))

    def write(self, specs, verify=True):
        """Write `name=value` specs. Returns the names that did not read back."""
        want = {}
        for spec in specs:
            name, _, val = spec.partition('=')
            w = f32(val[1:]) if val.startswith('f') else int(val, 0)
            n, a = self.addr(name)
            if self._last.get(name) != (w & 0xFFFFFFFF):
                self.mark_moved()
            self._last[name] = w & 0xFFFFFFFF
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

    # -- the capture arm (S159) ---------------------------------------------
    def capture_meas(self, n):
        """N contiguous samples of MeasChan's strip block, through the TEST_MEAS
        capture arm (the S56 handshake, as dsp4_meascap does it -- but with
        both words resolved BY NAME from the landed map, never a literal).
        Returns (samples as floats, chip-1 block overruns during the run)."""
        sc = self.chip(1)
        buf = sc.sym.get('_meas_cap_buf_C1_TEST_MEAS')
        if buf is None:
            raise IOError('this pair has no TEST_MEAS capture arm (%s)'
                          % self.symdir)
        _c, a_arm = self.addr('Test001CaptureArm001')
        _c, a_rdy = self.addr('Test001CaptureReady001')
        for _ in range(8):
            sc.d.link.write(a_rdy, 0, 0)
            nap(0.02)
            if sc.rd(a_rdy) == 0:
                break
        else:
            raise IOError('CaptureReady would not clear')
        ovr_sym = sc.sym.get('_diag_blk_overrun')
        ovr0 = peek_settled(sc, ovr_sym) if ovr_sym else 0
        got = 0
        for _attempt in range(4):
            sc.d.link.write(a_arm, int(n), 0)
            t0 = now()
            while now() - t0 < 3.0:
                nap(0.05)
                try:
                    got = sc.rd(a_rdy)
                except (IOError, OSError):
                    got = 0
                if got:
                    break
            if got:
                break
        if not got:
            raise IOError('the capture never completed (CaptureArm dropped)')
        ovr = ((peek_settled(sc, ovr_sym) - ovr0) & 0xFFFFFFFF
               if ovr_sym else 0)
        if '_bulk_state' in sc.sym:
            import dsp4_bulk
            words, _info = dsp4_bulk.read(sc, buf, got, log=lambda *a: None)
        else:
            words = [peek_settled(sc, buf + i) for i in range(got)]
        return q28(words), ovr

    def ein_capture(self, n=EIN_CAP_N, k=EIN_CAPS):
        caps, ovr = [], []
        for _ in range(k):
            x, o = self.capture_meas(n)
            caps.append(x)
            ovr.append(o)
        out = ein_bands(caps)
        out.update(caps=k, n=n, overruns=ovr)
        return out

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
        seq0 = last_seq = self._seq()
        t_stall = now()
        while (self._seq() - seq0) & 0xFFFFFFFF < settle:
            nap(WIN_S / 2)
            cur = self._seq()
            if cur != last_seq:
                last_seq, t_stall = cur, now()
            elif now() - t_stall > MEASURE_STALL_S:
                raise MeasureStalled(
                    'the TEST_MEAS window counter has not moved for %.1f s '
                    '(settling) -- check the symbol map (symdir=%s)'
                    % (MEASURE_STALL_S, self.symdir))
        rows, seen = [], None
        kf = from_f32(peek_settled(sc, sc.sym['_osc_k_C1_TEST_OSC']))
        on = self.read('Test001OscOn001') != 0
        # t_stall resets on the ONE event that is real forward motion -- a
        # window actually banked as a row -- so both retry branches below
        # (the counter has not moved yet; the counter moved AGAIN mid-read)
        # share one clock and neither can spin past MEASURE_STALL_S without
        # a single row landing.
        t_stall = now()
        while len(rows) < windows:
            s1 = self._seq()
            if s1 == seen:
                nap(WIN_S / 3)
                if now() - t_stall > MEASURE_STALL_S:
                    raise MeasureStalled(
                        'the TEST_MEAS window counter has not moved for %.1f s '
                        '(reading) -- check the symbol map (symdir=%s)'
                        % (MEASURE_STALL_S, self.symdir))
                continue
            rms = self.readf('Test001RmsResult001')
            thd = self.readf('Test001ThdResult001')
            nse = self.readf('Test001NoiseResult001')
            a = from_f32(peek_settled(sc, sc.sym['_meas_a_C1_TEST_MEAS']))
            b = from_f32(peek_settled(sc, sc.sym['_meas_b_C1_TEST_MEAS']))
            if self._seq() != s1:            # the window turned over mid-read
                nap(WIN_S / 3)
                if now() - t_stall > MEASURE_STALL_S:
                    raise MeasureStalled(
                        'the TEST_MEAS window counter has not moved for %.1f s '
                        '(reading, mid-window) -- check the symbol map '
                        '(symdir=%s)' % (MEASURE_STALL_S, self.symdir))
                continue
            t_stall = now()
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


def donor_for(strip):
    return DONOR_ALT if int(strip) == DONOR_DEFAULT else DONOR_DEFAULT


def route_id(drive, donor):
    """The route id the generator spells, rebuilt so a run-time rebind can
    name one. Both donors exist for every drive the list uses."""
    return '%s@%d' % (str(drive).replace(':', '').replace('+', 'p'), int(donor))


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
    # THE SPREAD ACROSS THE WINDOWS (S126, ruling d). A settled reading's
    # windows agree to hundredths; a lead being pushed home while they are
    # taken does not. Pre-arming reads BEFORE the operator's ENTER, so the one
    # thing it has to be able to see is a reading taken mid-insertion -- and
    # the windows themselves say so, without another instrument.
    v = [r['rms'] for r in rows if 'rms' in r and math.isfinite(r['rms'])]
    out['rms_spread'] = (max(v) - min(v)) if len(v) > 1 else 0.0
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


# THE 150 OHM PASS'S NOISE INSTRUMENT (S159, HUB ADDENDUM 2). The node's
# RmsResult is 10*log10(Sxx/N) over DC-24 kHz with no band limit
# (dsp_codegen.py), and the T4b limit is 20 Hz-20 kHz: on a GOOD channel the
# two differ by about 3 dB (S57: -124.2 against -127.2 dBu), so the node alone
# would fail every input. The figure is therefore taken from the TEST_MEAS
# CAPTURE ARM -- contiguous samples of the same strip block the node reads
# (S56; proved on the s154 pair in S160, 0 overruns) -- band-integrated on the
# unit by dsp4_fft, after the input has SETTLED: the S158 readings were taken
# at arrival and the traces show the lane still falling seconds after the plug.


def q28(words):
    out = []
    for w in words:
        w &= 0xFFFFFFFF
        out.append((w - (1 << 32) if w & 0x80000000 else w) / float(1 << 28))
    return out


def detrend(x):
    """Mean and linear trend out: the sub-20 Hz wander (S57) inside one
    capture is a slope, and the window would otherwise smear it upward."""
    n = len(x)
    tm = (n - 1) / 2.0
    xm = sum(x) / n
    sxx = sum((i - tm) ** 2 for i in range(n))
    b = sum((i - tm) * (v - xm) for i, v in enumerate(x)) / sxx
    return [v - xm - b * (i - tm) for i, v in enumerate(x)]


def ein_bands(captures):
    """[samples (float, full scale 1.0)] -> mean-square dBFS: 20 Hz-20 kHz,
    the same A-weighted, and the raw DC-24k total, power-averaged."""
    import dsp4_fft as FFT
    u = a = tot = 0.0
    for x in captures:
        y = detrend(x)
        u += 10 ** (FFT.band_power(y, FS, 20.0, 20000.0)[0] / 10.0)
        a += 10 ** (FFT.band_power(y, FS, 20.0, 20000.0, aweight=True)[0]
                    / 10.0)
        tot += sum(v * v for v in x) / len(x)
    k = float(len(captures))
    return dict(u=10 * math.log10(u / k), a=10 * math.log10(a / k),
                total=10 * math.log10(tot / k))


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

    def decide(self, what):
        """The operator's answer to a FAILED screen that has no dialog behind
        it (a graded fail, S157), or None. The glass answers through
        `Live.command`; this is the second channel, and only the dry run's
        operator uses it."""
        return None

    def done(self, token):
        pass

    def clear(self):
        pass


class ManualPatcher(Patcher):
    """A person, a lead, and a prompt that does not wait for Enter."""

    kind = 'manual'

    def __init__(self, glass, auto=True):
        self.glass = glass
        self.last = None
        # WHICH BUTTON THE DIALOG CARRIES. The dialog is the second channel --
        # the factory screen is what the operator reads, the dialog is what the
        # runner is answered through -- and since PW's ruling of 2026-09-28 the
        # answer it needs is not DONE (the lead going in says that) but NO
        # SIGNAL. It matters that this channel has it too: `Live.command` needs
        # the app to draw a button it has never drawn before, and until it does,
        # this is the only way an operator can say a socket is dead.
        self.auto = bool(auto)

    def connect(self, patch, rows, glass):
        r = rows[0]
        lead = r['lead']
        lines = [r['prompt'] + '.']
        if r['sub'] or len(rows) > 1:
            lines.append('%d checks on this one patch -- keep the lead in '
                         'until the next instruction.' % len(rows))
        lines.append('It advances on its own when the lead is in.')
        btns = glass.post('patch', '%s  (lead %s)' % (r['prompt'], lead),
                          lines, (['nosignal', 'retry'] if self.auto
                                  else ['done']),
                          patch=patch, lead=lead, row=r['rows'])
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


def pick_patcher(glass, want='auto', auto_advance=True):
    """MANUAL unless a harness answers IDENT on a /dev/ttyACM* -- and since the
    harness back end is not built, MANUAL either way today. The probe is left
    in as the one line that has to change."""
    if want == 'harness':
        return HarnessPatcher()
    return ManualPatcher(glass, auto=auto_advance)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
class Limits(dict):
    """patch-limits.csv, and nothing else. No number lives in this file."""

    # THE EIN LIMIT IS THE PRODUCT'S, NOT THE STATION'S (HUB ADDENDUM 2 to
    # S159, PW 2026-10-01: "apply the existing -126.0 dBu EIN limit"). The
    # generator copies tools/accept/limits.csv -- the file PW ruled T4b into
    # on 2026-09-21 -- and units.csv into the list directory beside
    # patch-limits.csv, and only these keys are taken from them. A list
    # directory without them leaves the 150 ohm pass ungraded, as it was.
    EIN_KEYS = ('t4b_ein_max_dbu', 't4b_ein_a_max_dbu')

    @classmethod
    def load(cls, d):
        out = cls()
        for r in read_csv(os.path.join(d, 'patch-limits.csv')):
            out[r['key']] = float(r['value'])
        lp = os.path.join(d, 'limits.csv')
        if os.path.exists(lp):
            for r in read_csv(lp):
                if r.get('key') in cls.EIN_KEYS:
                    out[r['key']] = float(r['value'])
        up = os.path.join(d, 'units.csv')
        if os.path.exists(up):
            import socket
            unit = os.environ.get('D24_UNIT') or socket.gethostname()
            for r in read_csv(up):
                if r.get('unit') == unit and r.get('dac_fs_dbu'):
                    out['dac_fs_dbu'] = float(r['dac_fs_dbu'])
                    out['unit'] = unit
        return out

    def ein_ready(self):
        return all(k in self for k in self.EIN_KEYS + ('dac_fs_dbu',))


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

    def __init__(self, limits, log=None):
        self.lim = limits
        self.ref = {}                # lane -> {'h_db', 'h_deg'}
        self.results = []
        # THE SCORER SAYS ITS NUMBERS OUT LOUD (S128). It has always built the
        # per-step `notes`, and they have always gone only to the results CSV,
        # written at the END of a pass. A gain step that reads 6.9 dB high in
        # the middle of a walk therefore left nothing in `factory.log` but the
        # verdict sentence, and nothing to look at short of running the station
        # again.
        self.log = log or (lambda s: None)

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

    def score(self, row, meas, floor, sweep, siblings, donor=None, sweep0=None):
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

        if row['level_ref'] == 'gain':
            return self._score_gain_step(row, meas, siblings, notes)

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
        bad = self._isolation(lane, sweep, donor, sweep0)
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
            # AND AGAINST THE SAME SOCKET'S XLR, WHEN THERE IS ONE (S129).
            # The line path enters the same combo socket through its jack
            # centre, and the jack legs reach the preamp through one extra
            # series resistor per leg that the XLR pins do not. So the
            # difference between this reading and the lane's own balanced
            # reference IS the jack path's pad, measured on the unit under
            # test, and it is what a level window for this path would have to
            # be built out of. Recorded on every line patch of every pass;
            # nothing is judged on it yet.
            _r = self.ref.get(lane)
            if _r is not None and _r.get('h_db') is not None:
                notes.append('%+.2f dB against this socket\'s own XLR '
                             'reference of %.2f dB -- the jack path\'s pad, '
                             'recorded, not judged'
                             % (h - _r['h_db'], _r['h_db']))

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
                # THE LINE ROWS: `normal` MEANS THE WRONG SOCKET (S129).
                # A line patch goes into the combo socket's 6.35 mm jack
                # centre, which this board wires tip-to-cold and which
                # therefore reads INVERTED. An XLR lead in the SAME socket's
                # XLR reads normal and used to pass, so the test could not
                # tell the two sockets apart. It can now, and it says which
                # mistake was made rather than reporting a polarity fault.
                if pol_want == 'inverted' and got == 'normal' \
                        and str(row['in']).endswith(' line'):
                    return (FAIL, 'the lead is in the XLR socket, not the '
                            '6.35 mm jack centre of %s: this reading is in '
                            'phase with the XLR reference, and the jack '
                            'centre reads inverted'
                            % str(row['in'])[:-5].strip(), notes)
                return (FAIL, 'this channel came back %s and should be %s'
                        % (got, pol_want), notes)
            else:
                notes.append('polarity %s, %.0f deg from the reference'
                             % (got, d))
                # A LINE ROW THAT READS INVERTED IS THE ERRATUM, NOT HEALTH
                # (S129). It is the reading that proves the lead is in the
                # jack and not the XLR, and it is also the board fault: the
                # jack tip lands on the preamp's cold leg on MIC 3..24. The
                # pass is a pass of the SOCKET; the erratum is said out loud
                # in every pass so the red mod is not forgotten.
                if pol_want == 'inverted' and str(row['in']).endswith(' line'):
                    notes.append('ERRATUM: the jack centre is in the right '
                                 'socket and inverted, which is how this board '
                                 'revision is built (jack TIP on the preamp '
                                 'cold leg, one resistor pair per channel, MIC '
                                 '3..24) -- a red mod is owed and this row '
                                 'passes the SOCKET, not the wiring')
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

    def _score_gain_step(self, row, meas, siblings, notes):
        """One of PW's six single-element gain steps.

        WHAT IS JUDGED IS THE STEP, NOT THE LEVEL. The reading is compared
        with the SAME INPUT's code-0 reading taken seconds earlier through the
        same lead and the same output, so the loop's own gain, the drive and
        the converter all cancel and what is left is what the element added.
        The expected value is the list's, out of defs' gain law.

        BOTH READINGS ARE THE NODE'S RMS (S125). They have to be the same
        quantity, because the arithmetic is a subtraction: the meter cannot
        supply either of them honestly (see `gain_step`) and a step read off
        one instrument against a reference read off the other would be a
        number with no meaning at all.
        """
        want = meas.get('expected_db')
        here = meas.get('rms')
        ref = None
        for sib in siblings:
            if sib.get('gain_code') == 0:
                ref = sib.get('rms')
                break
        code = meas.get('gain_code')
        if (here is None or ref is None or want is None
                or not math.isfinite(here) or not math.isfinite(ref)):
            return NODATA, ('the gain step at code %s could not be read'
                            % code), notes
        # The drive was dropped by the step's own expected gain so the
        # converter sees about the same level every time, so the drop has to
        # be added back before the two readings can be subtracted.
        got = here - ref
        drive_ref = None
        for sib in siblings:
            if sib.get('gain_code') == 0:
                drive_ref = sib.get('drive_dbfs')
                break
        if drive_ref is not None and meas.get('drive_dbfs') is not None:
            got += drive_ref - meas['drive_dbfs']
        tol = self.lim['gain_step_tol_db']
        line = ('gain element %d: measured %+.2f dB, expected %+.2f dB '
                '(%s), drive %+.1f dBFS, lane %.2f dBFS, reference %.2f dBFS, '
                'settle %s of %s windows owed from the drive change, %s after '
                'it (the meter, which is not what this is judged on, read %s)'
                % (int(code).bit_length(), got, want,
                   meas.get('source') or '?', meas.get('drive_dbfs') or 0.0,
                   here, ref,
                   meas.get('settle_windows', '?'),
                   meas.get('settle_full', '?'),
                   ('%.0f ms' % (1000 * meas['since_drive_s']))
                   if meas.get('since_drive_s') is not None else 'n/a',
                   ('%.2f' % meas['meter_db'])
                   if meas.get('meter_db') is not None else '--'))
        notes.append(line)
        # EVERY STEP'S NUMBERS GO TO THE LOG AS THEY ARE TAKEN (S128).
        # Until now the only trace a gain step left in `factory.log` was the
        # patch's one verdict sentence, so a reading of 54.9 dB where the next
        # eight sockets read 48.2 could not be looked into at all without
        # running the whole station again. The notes already existed; they only
        # reached the results CSV, and only at the end of the pass.
        self.log(line)
        if abs(got - want) <= tol:
            return PASS, ('gain element %d adds %.1f dB, %.1f dB from expected'
                          % (int(code).bit_length(), got, got - want)), notes
        return FAIL, ('%s gain step %d is wrong: it adds %.1f dB and should '
                      'add %.1f dB' % (row['in'], int(code).bit_length(), got,
                                       want)), notes

    def _score_noise(self, row, meas, notes):
        n = meas.get('rms')
        if n is None or not math.isfinite(n):
            return NODATA, 'the noise reading did not come back', notes
        if meas.get('ein_band_dbfs') is not None:
            return self._score_ein(row, meas, notes)
        notes.append('%.1f dBFS at the lane with the terminator fitted' % n)
        # THE OPEN INPUT BESIDE IT (S158): what the lane read before the plug,
        # and how far the plug took it down. Informational -- it is how MIC
        # 2-4's 2 dB step (their terminated noise ~10 dB over the other 21
        # inputs') was found, and how a reading taken on an open input would
        # show itself.
        o = meas.get('open_db')
        if o is not None and math.isfinite(o):
            notes.append('open input %.1f dBFS before it, %.1f dB higher'
                         % (o, o - n))
        if meas.get('how'):
            notes.append(meas['how'])
        return (PASS, 'the input noise was measured with a 150 ohm source',
                notes + ['no EIN window is ruled for the factory station yet: '
                         'the figure is recorded, and limits.csv t4b_ein_max_dbu '
                         'is the design reference'])

    def _score_ein(self, row, meas, notes):
        """THE T4b LIMIT ON THE FACTORY 150 OHM PASS (HUB ADDENDUM 2 to S159,
        PW 2026-10-01). EIN by the S57-R method: dBu = P + 3.01 + dac_fs_dbu
        - G(code), P the capture's 20 Hz-20 kHz mean square (dBFS), G(code)
        this lane's code-0 loop gain (its balanced reference, measured on THIS
        unit through the K1 lead) plus the code's step from defs' gain table.
        The code-0 full scale is never combined with the absolute code-63
        gain -- that double count is the 5.6 dB S57-R found."""
        lane = int(row['lane'])
        ref = self.ref.get(lane)
        step = meas.get('gain_step_db')
        if ref is None or ref.get('h_db') is None or step is None:
            return (NODATA, 'the noise was captured but cannot be input-'
                    'referred: %s has no balanced reference yet (the AUX 1 '
                    'tone patch into this input sets it)' % row['in'], notes)
        g = ref['h_db'] + step
        off = FS_SINE_DB + meas['dac_fs_dbu'] - g
        u = meas['ein_band_dbfs'] + off
        a = meas['ein_a_dbfs'] + off
        meas['ein_dbu'], meas['ein_a_dbu'] = u, a
        lim_u = self.lim['t4b_ein_max_dbu']
        lim_a = self.lim['t4b_ein_a_max_dbu']
        notes.append('EIN %.1f dBu 20 Hz-20 kHz unweighted (limit %.1f), '
                     '%.1f dBu(A) (limit %.1f)' % (u, lim_u, a, lim_a))
        notes.append('%d x %d-sample captures after %.1f s settling: lane '
                     '%.2f dBFS 20-20k, %.2f A, %.2f DC-24k (node RmsResult '
                     '%.2f)' % (meas['ein_caps'], meas['ein_n'],
                                meas.get('ein_settle_s') or 0.0,
                                meas['ein_band_dbfs'], meas['ein_a_dbfs'],
                                meas['ein_total_dbfs'], meas['rms']))
        notes.append('G(code %d) %.2f dB = reference %.2f%s + step %.2f; '
                     'dBu = P + 3.01 + %.2f - G'
                     % (meas.get('gain_code', 63), g, ref['h_db'],
                        ' (carried from pass %s)' % ref['carried']
                        if ref.get('carried') else '', step,
                        meas['dac_fs_dbu']))
        o = meas.get('open_db')
        if o is not None and math.isfinite(o):
            notes.append('open input %.1f dBFS before the plug' % o)
        if meas.get('how'):
            notes.append(meas['how'])
        if any(meas.get('ein_overruns') or []):
            notes.append('a DSP block overran during a capture: the figure '
                         'may hold a discontinuity')
        bad = []
        if u > lim_u:
            bad.append('%.1f dBu, limit %.1f dBu' % (u, lim_u))
        if a > lim_a:
            bad.append('%.1f dBu(A), limit %.1f dBu(A)' % (a, lim_a))
        if bad:
            return FAIL, 'noise too high: ' + '; '.join(bad), notes
        return (PASS, 'EIN %.1f dBu, limit %.1f dBu (%.1f dBu(A), limit '
                '%.1f)' % (u, lim_u, a, lim_a), notes)

    def _isolation(self, lane, sweep, donor=None, sweep0=None):
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
            if not self._rose(k, v, sweep0):
                continue
            d = dbv(v) - dbv(here)
            if worst is None or d > worst:
                worst, who = d, k
        if worst is not None and worst > -self.lim['isolation_min_db']:
            return 'MIC %d' % who
        return None

    def _rose(self, lane, v, sweep0):
        """Did this lane get louder during THIS patch?

        A MIS-PATCH LIGHTS A LANE THAT WAS DARK; A METER TAIL IS A LANE GOING
        OUT. The strip meters hold their peak and decay slowly -- measured on
        MW-D24-2, about 6 dB per second -- so a lane driven hard by the patch
        before is still tens of decibels above its floor when the next patch
        is measured, and judging "is anything else lit" on the absolute
        reading alone would call that a mis-patch. The lane that matters is
        the one that RISES while the operator's hands are on the connector,
        which is exactly what the baseline taken at prepare time separates.
        """
        if not sweep0:
            return True
        was = sweep0.get(lane)
        if was is None or was <= 0:
            return True
        return dbv(v) - dbv(was) >= self.lim['detect_rise_db']


# ---------------------------------------------------------------------------
# The analog side: the station's own, standalone and inside RUN ALL
# ---------------------------------------------------------------------------
# WHY THIS IS HERE AT ALL (S123 item 4). Until now the station prepared the
# DSP and nothing else: the rails and the 595 mic-pre chain were somebody
# else's job, which in practice meant the hub's, by hand, before every run.
# A worker at a factory bench has no hand to do it with, and a run against
# rails that are down reads as a unit with twenty-four dead inputs. So the
# station owns the whole analog state it depends on, and owns putting it back.
#
# THE NUMBERS ARE NOT COPIED. AN_EN, CS_M and the SAFE image are imported from
# d24_selftest, which is the file that defines them; only the SEQUENCING lives
# here, and it is the sequencing PW ruled on:
#
#   up    CS_M driven high (a low CS_M gates the U2 buffer onto the shared
#         MISO and every read comes back as plausible zeros), then AN_EN,
#         ONCE for the whole pass and never through a DSP boot.
#   image the chain per block -- tone blocks with the phantom shunt released
#         at gain 0, the noise block released at gain 63, each one read back
#         and the marker written.
#   down  AN_EN LOW FIRST, then SAFE, then the oscillator and the monitor.
#         That order is PW's, taken from the handback the hub did by hand on
#         2026-09-26: the rails go down before the chain is rewritten, so a
#         chain write can never be the thing that is heard.
AN_EN_GPIO = 26
CS_M_GPIO = 27
# (gain & 63) << 2 | (phantom & 1) << 1 | (shunt & 1), twenty-four preamps and
# one trailing byte. BIT 0 IS THE PHANTOM SHUNT, not a mute -- PW 2026-09-16,
# see `d24_chain.byte`; the channel mute is digital, in the DSP strip.
CHAIN_TONE = [0x00] * 24 + [0x00]        # shunt released, phantom off, gain 0
CHAIN_NOISE = [0xFC] * 24 + [0x00]       # shunt released, phantom off, gain 63
S55_DIR = '/home/app/s55'
STAGE_DIR = '/home/app/s90'


def _selftest_consts():
    """AN_EN, CS_M and SAFE, from the file that owns them.

    Imported rather than typed so that a pin or an image that moves moves in
    one place. If d24_selftest is not beside this file -- a desk run, a dry
    run -- the module's own defaults stand and nothing analog is touched
    anyway.
    """
    try:
        sys.path.insert(0, HERE)
        import d24_selftest as D                       # noqa: E402
        return D.AN_EN_GPIO, D.CS_M_GPIO, list(D.SAFE_IMAGE)
    except Exception:
        return AN_EN_GPIO, CS_M_GPIO, [0x01] * 24 + [0x00]


class Analog:
    """The rails and the mic-pre chain, for the length of one pass."""

    def __init__(self, enabled=True, log=None, stage=STAGE_DIR, s55=S55_DIR,
                 own_rails=False):
        self.enabled = bool(enabled)
        self.log = log or (lambda s: None)
        self.stage = stage
        self.s55 = s55
        self.an_en, self.cs_m, self.safe_image = _selftest_consts()
        self.raised = False          # this run raised AN_EN, so this run lowers it
        # THE RAILS BELONG TO THE SESSION, NOT TO A PROCESS (S125). PW's rule
        # is that they go up ONCE, after the last DSP boot, and come down at
        # the handback. Under RUN ALL the self-test's group C raises them and
        # is told to LEAVE them up (`--al1-keep-rails`), so by the time this
        # station starts they are already high and `up()` would record that it
        # did not raise them -- and `down()` would then leave a unit live on
        # the shelf. `own_rails` says this process is the one that closes the
        # session, so it lowers them whoever put them up. A standalone patch
        # run does not set it and still leaves the unit exactly as found.
        self.own_rails = bool(own_rails)
        self.image = None            # the chain image currently on the part
        self.done = False
        self.fast = None             # the lean writer, opened on first use
        self.wrote = False           # did the last chain() move the wire?
        self.writes = 0
        self.write_s = 0.0

    # -- the shell ---------------------------------------------------------
    def sh(self, cmd, timeout=90):
        import subprocess
        p = subprocess.run(['/bin/bash', '-c', cmd], capture_output=True,
                           text=True, timeout=timeout)
        return (p.stdout + p.stderr).strip()

    def marker(self):
        return os.path.join(self.stage, '.chain_last')

    # -- up ----------------------------------------------------------------
    def up(self):
        """CS_M high, then the rails. Idempotent: a second call re-reads.

        RAISED ONCE PER SESSION (PW, S116 Q4). Finding them already up is the
        NORMAL case under RUN ALL, not a surprise: the self-test's group C
        raised them after the last DSP boot and was told to leave them, which
        is the whole point -- a second raise would be a second edge on a rail
        the rule says has one.
        """
        if not self.enabled or self.raised:
            return
        self.sh('sudo -n pinctrl set %d op dh' % self.cs_m)
        an = self.sh('pinctrl get %d' % self.an_en)
        if 'hi' not in an:
            self.sh('sudo -n pinctrl set %d op dh' % self.an_en)
            self.raised = True
        self.log('the analog rails are up%s'
                 % ('' if self.raised else
                    ' (already up -- raised once, earlier in this session)'))

    # -- the chain ---------------------------------------------------------
    def open_fast(self):
        """The lean writer, opened once and held for the pass.

        Measured on MW-D24-2, 2026-09-26: a chain write cost 294 ms as a
        python3 process per write, 157 ms called in-process (113 ms of that
        four `sudo pinctrl` calls), and 8 ms through this. The gain steps ask
        for 168 writes in a pass; that is the difference between 49 s of a
        worker's time and 1.3 s.
        """
        if self.fast is None and self.enabled:
            try:
                self.fast = CH.Chain()
                self.log('the mic-pre chain writer is open (%s)'
                         % ('fast' if self.fast.fast else 'pin fallback'))
            except Exception as e:
                self.fast = False
                self.log('the fast chain writer would not open (%s); falling '
                         'back to one process per write' % e)
        return self.fast or None

    def chain(self, image, what):
        """One 595 image, written and read back. Never written twice running.

        Sets `wrote` to say whether the wire actually moved, because a reading
        taken after an image that did NOT change needs no settle for it.

        An unverified write is not a known state, so the marker is removed
        rather than left saying something that was not proved -- the same rule
        the self-test runner keeps.
        """
        self.wrote = False
        if not self.enabled or image == self.image:
            return True
        self.wrote = True
        want = ' '.join('%02X' % b for b in image)
        t0 = time.time()
        fast = self.open_fast()
        if fast is not None:
            ok, got = fast.send(image)
            txt = '%s %s' % ('VERIFIED' if ok else 'MISMATCH',
                             ' '.join('%02X' % b for b in got))
        else:
            hexes = ' '.join('0x%02X' % b for b in image)
            txt = self.sh('cd %s && sudo -n python3 s55_chain.py %s 2>&1'
                          % (self.s55, hexes), timeout=120)
            ok = txt.startswith('VERIFIED 200/200') and want in txt
        self.writes += 1
        self.write_s += time.time() - t0
        if ok:
            self.sh('printf %s > %s'
                    % (_q(want), _q(self.marker())))
            self.image = image
        else:
            self.sh('rm -f %s' % _q(self.marker()))
            self.image = None
        if ok:
            why = 'verified'
        else:
            first = txt.splitlines()[0][:80] if txt else 'no reply'
            why = 'NOT VERIFIED -- %s' % first
        self.log('mic-pre chain %s: %s' % (what, why))
        return ok

    def step_image(self, send_pos, code, quiet=0x01):
        """The image for ONE gain step: the input under test at this code,
        its phantom shunt released and phantom off; every other channel
        shunted, at gain 0, and known.

        `send_pos` IS THE TX BYTE, ZERO-BASED, and it comes out of the list,
        which took it from `send_pos` in defs' own input table. It is NOT the
        preamp's position along the daisy chain and it is NOT the strip
        number: all three orders differ, and defs carries two of them in
        adjacent columns of the same row. Until S125 the list carried
        `chain_index` here and every gain step wrote a byte that drove some
        other input's preamp, or none at all -- see `load_send_pos()` in
        tools/accept/gen_patch_paths.py for the measurement that caught it.
        """
        img = [quiet] * 24 + [0x00]
        i = int(send_pos)
        if not 0 <= i < 24:
            raise AssertionError('send position %r is not on the chain'
                                 % send_pos)
        img[i] = CH.byte(shunt=0, phantom=0, gain=int(code))
        return img

    # -- phantom, and it is never one image -------------------------------
    def phantom(self, channels, on, what=''):
        """Move phantom on `channels` (transmit positions) through PW's
        shunt-first sequence. Returns (ok, [step records]).

        PW 2026-09-16 (mx26 `docs/ref-d24-analog-attach.md`, read as primary
        source in S138b): "Phantom is therefore never switched by one image."
        The five steps and the two waits are `d24_chain.phantom_sequence`,
        which is arithmetic and is asserted image by image off the bench; this
        is the three VERIFIED LOADS around it.

        THE FAILURE END STATE IS PW'S, NOT A CHOICE MADE HERE: "a step that
        does not verify stops the sequence there and leaves the shunt
        engaged, which is the safe end state." So a step that does not read
        back stops -- and the shunt is then RE-ASSERTED EXPLICITLY, on every
        failure, not only on the first step's.

        `shunt_sequence_check.py` is what made that last sentence necessary,
        and the first version of this method was wrong about it. The reasoning
        was that step 1 is the load that engages the shunt, so a stop after it
        has already left the shunt engaged and nothing more is owed. That is
        true of a failure at step 3 and FALSE of a failure at step 5, because
        step 5 is the load that RELEASES the shunt again: a write that did not
        read back is not a known state (`chain()` drops the marker for exactly
        that reason), so after a failed step 5 the shunt may be released and
        the sequence would have reported the unsafe case as the safe one. The
        re-assert is built from the last load that DID verify, with the shunt
        forced on across the set.
        """
        base = list(self.image if self.image is not None else self.safe_image)
        chans = sorted(int(c) for c in channels)
        steps = []
        ok = True
        good_img = base
        for i, (img, why, wait) in enumerate(
                CH.phantom_sequence(base, chans, on)):
            label = 'phantom %s on %s: step %d, %s' % (
                'on' if on else 'off', what or ('transmit %s' % chans),
                (1, 3, 5)[i], why)
            good = self.chain(img, label)
            steps.append(dict(step=(1, 3, 5)[i], image=list(img), ok=bool(good),
                              why=why, waited_s=wait if good else 0.0))
            if not good:
                ok = False
                self.chain(CH.with_shunt(good_img, chans, True),
                           'the phantom shunt re-asserted after a failed step '
                           '%d -- the safe end state' % (1, 3, 5)[i])
                self.log('phantom sequence STOPPED at step %d: the load did '
                         'not read back. The shunt is re-asserted and left '
                         'engaged, which is the safe end state '
                         '(PW 2026-09-16).' % (1, 3, 5)[i])
                break
            good_img = list(img)
            if wait:
                nap(wait)
        return ok, steps

    def for_block(self, lead):
        """The chain image this block needs.

        The noise block reads each input's own noise at the gain the survey
        used, so it is the one block that runs the preamps wide open; every
        other block drives a tone in and wants the preamp out of the way.
        """
        if lead == 'K5':
            return self.chain(CHAIN_NOISE, 'at full gain for the noise step')
        return self.chain(CHAIN_TONE, 'at zero gain')

    # -- down --------------------------------------------------------------
    def down(self):
        """The rails down and the chain SAFE, in that order. Runs once.

        Called on every way out -- the end of the pass, PAUSE, a signal, an
        exception -- because the failure this exists to stop is a unit that
        goes back on the shelf live.
        """
        if not self.enabled or self.done:
            return
        self.done = True
        if self.raised or self.own_rails:
            self.sh('sudo -n pinctrl set %d op dl' % self.an_en)
            self.log('the analog rails are down%s'
                     % ('' if self.raised else
                        ' (raised earlier in this session, lowered here -- '
                        'this station closes it)'))
        else:
            self.log('the analog rails were not raised by this run; left as found')
        self.sh('sudo -n pinctrl set %d op dh' % self.cs_m)
        self.image = None
        self.chain(self.safe_image,
                   'back to safe (phantom shunt engaged, gain 0, phantom off)')
        if self.fast:
            try:
                self.fast.close()
            except Exception:
                pass
            self.fast = None


def _q(s):
    return "'" + str(s).replace("'", "'\\''") + "'"


# ---------------------------------------------------------------------------
# ENTER, from a keyboard nobody has to configure
# ---------------------------------------------------------------------------
# PW 2026-09-26: "let me plug in the cable, then hit Enter." ENTER is two
# things -- a button on the glass, which the display writes into the command
# file, and the Enter key of a USB keyboard plugged into the unit. The
# keyboard is read HERE, in the runner, rather than through the display, for
# two reasons: a station started from a terminal has no display to read it,
# and the framebuffer backend's keyboard support is not something to bet a
# factory bench on. Reading the device directly needs no configuration and no
# window focus -- the `app` user is already in the `input` group.
#
# HOT-PLUG IS THE NORMAL CASE. The keyboard is a thing somebody carries to a
# bench, so the device list is re-read every few seconds and a keyboard that
# appears mid-pass starts working without a restart.
EV_KEY = 0x01
KEY_ENTER = 28
KEY_KPENTER = 96
INPUT_EVENT_SIZE = 24                      # 64-bit: 2x8 timeval + 2 + 2 + 4
KBD_RESCAN_S = 5.0


def keyboards():
    """Every input device that has an Enter key, by its /dev/input node.

    Read off /proc/bus/input/devices rather than by ioctl so this needs no
    extension module: each device block carries a `B: KEY=` bitmask and a
    `H: Handlers=` line, and a device with bit 28 set has an Enter key.
    """
    out = []
    name = handlers = keybits = None
    try:
        lines = open('/proc/bus/input/devices').read().splitlines()
    except OSError:
        return out
    for line in lines + ['']:
        if line.startswith('N: Name='):
            name, handlers, keybits = line[8:].strip('"'), None, None
        elif line.startswith('H: Handlers='):
            handlers = line[12:].split()
        elif line.startswith('B: KEY='):
            keybits = line[7:].split()
        elif not line.strip():
            if handlers and keybits:
                words = [int(w, 16) for w in keybits]
                mask = 0
                for i, w in enumerate(reversed(words)):
                    mask |= w << (64 * i)
                if (mask >> KEY_ENTER) & 1:
                    for h in handlers:
                        if h.startswith('event'):
                            out.append(('/dev/input/' + h, name))
            name = handlers = keybits = None
    return out


class KeyWatch:
    """A latch that goes true when somebody presses Enter.

    One reader thread per device, all of them daemon threads, all of them
    setting the same latch. Nothing here ever blocks the loop: the loop asks
    `pressed()`, which takes the latch and clears it.
    """

    def __init__(self, enabled=True, log=None):
        self.enabled = bool(enabled)
        self.log = log or (lambda s: None)
        self._hit = False
        self._open = set()
        self._stop = False
        self._t = None
        if self.enabled:
            import threading
            self._t = threading.Thread(target=self._scan, daemon=True)
            self._t.start()

    def pressed(self):
        if not self._hit:
            return False
        self._hit = False
        return True

    def stop(self):
        self._stop = True

    # -- the threads -------------------------------------------------------
    def _scan(self):
        import threading
        while not self._stop:
            for path, name in keyboards():
                if path in self._open:
                    continue
                self._open.add(path)
                self.log('reading the Enter key from %s (%s)' % (path, name))
                threading.Thread(target=self._read, args=(path,),
                                 daemon=True).start()
            time.sleep(KBD_RESCAN_S)

    def _read(self, path):
        import struct
        try:
            fh = open(path, 'rb', buffering=0)
        except OSError as e:
            self.log('cannot read %s (%s)' % (path, e))
            self._open.discard(path)
            return
        try:
            while not self._stop:
                b = fh.read(INPUT_EVENT_SIZE)
                if not b or len(b) < INPUT_EVENT_SIZE:
                    break
                _s, _us, typ, code, val = struct.unpack('qqHHi', b)
                if typ == EV_KEY and val == 1 and code in (KEY_ENTER,
                                                           KEY_KPENTER):
                    self._hit = True
        except OSError:
            pass
        finally:
            try:
                fh.close()
            except OSError:
                pass
            self._open.discard(path)          # unplugged: let the scan re-find it


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------
MIC_STRIPS = tuple(range(1, 25))
# The donor strip, the same two numbers the generator uses: TEST_OSC REPLACES
# a strip's input, so the strip carrying the oscillator cannot be the strip
# being measured, and the list moves the donor out of the way when its own
# input is under test.
DONOR_DEFAULT = 24
DONOR_ALT = 1
# How many inputs in a row may hear nothing before the OUTPUT becomes the
# suspect (PW 2026-09-26, step 1). Three is PW's number.
MAX_DEAF_IN_A_ROW = 3
# How long a step waits. With auto-advance the tone ends the step, so the
# timeout is the list's own. With ENTER the step waits for a PERSON, and a
# person who has gone to find a lead is not a fault: the same number, but
# many times over, so a station left running still gives up eventually.
ENTER_PATIENCE = 30
# How many times a patch is offered again before it is recorded as NO DATA. A
# wrong patch is a prompt and not a fail (PW 2026-09-26), but a prompt that
# repeats for ever is a station that has stopped, so the loop bounds itself and
# records what it saw. The operator can still press FAIL at any offer.
MAX_RETRIES = 2

# ---------------------------------------------------------------------------
# 1.2(b): the click-and-shunt trials (PW ruling 2026-09-28 08:06)
# ---------------------------------------------------------------------------
# Every number here is the INSTRUMENT's, not a limit: PW signs the limits after
# reading the trial table, and until then the row is INFORMATIONAL. Nothing in
# this block is ever compared against a reading to produce a verdict.
CLICK_PRE_S = 0.25          # quiet before the toggle: this is the floor
CLICK_POST_S = 2.5          # ... and after it. Two things set it: the 33 uF
                            # input caps through the 2x6K8 phantom feed are a
                            # 0.22 s time constant, so this is about eleven of
                            # them and it outlasts PHANTOM_SETTLE_S (0.30 s);
                            # and the METER's own drain, which is what usually
                            # ends last -- 6.52 dB/s from a -60 dBFS peak to
                            # 6 dB over a -96 dBFS floor is 4.6 s, so a loud
                            # click still truncates and says so (`truncated`).
CLICK_ABOVE_FLOOR_DB = 6.0  # what counts as "still ringing", over the floor
METER_DECAY_DB_S = 6.52     # MEASURED, S125: the strip meter's own decay.
                            # Subtracted out of the duration -- see
                            # `Station.click_metrics`.
CLICK_TABLE_NOTE = (
    'INFORMATIONAL: no click limit is ruled yet (PW 2026-09-28: trials first, '
    'then a signature). Instrument: the strip peak meter, one SPI peek a '
    'sample, which LATCHES the block peak and decays at %.2f dB/s (measured, '
    'S125). So peak_dbfs cannot be missed between polls, only reported up to '
    'poll_ms_max late; above_floor_ms carries the meter\'s own tail, and '
    'residual_ms is that tail taken back out. trunc=yes means the capture '
    'ended with the lane still ringing, so above is a LOWER BOUND and no '
    'residual is reported. energy_db_s is an UPPER BOUND, because the latch '
    'holds a peak across polls. The 150 ohm terminator is fitted throughout '
    'and no microphone is connected.' % METER_DECAY_DB_S)
CLICK_COLUMNS = ('input', 'lane', 'shunt', 'direction', 'floor_dbfs',
                 'peak_dbfs', 't_peak_ms', 'above_floor_ms', 'decay_only_ms',
                 'residual_ms', 'truncated', 'energy_db_s', 'polls',
                 'poll_ms_mean', 'poll_ms_max', 'skipped')


def click_table(results, out=sys.stdout, note=True):
    """The trial table, in the one format this session fixes.

    One line per trial, the four trials of an input together, and the note
    above it -- because a table of clicks with no instrument beside it is what
    a signature should never be given against.
    """
    if note:
        out.write('%s\n\n' % CLICK_TABLE_NOTE)
    out.write('%-9s %-4s %-8s %-9s %9s %9s %8s %9s %9s %9s %5s %9s %6s %8s '
              '%8s\n'
              % ('input', 'lane', 'shunt', 'direction', 'floor', 'peak',
                 't_peak', 'above', 'decay', 'residual', 'trunc', 'energy',
                 'polls', 'poll_ms', 'poll_max'))

    def num(v, fmt='%9.2f'):
        return (fmt % v) if isinstance(v, float) else '%9s' % '-'
    for res in results:
        if res.get('skipped'):
            out.write('%-9s %-4s %s\n' % (res['input'], res['lane'],
                                          res['skipped']))
            continue
        for t in res['trials']:
            if t.get('skipped'):
                out.write('%-9s %-4s %-8s %-9s %s\n'
                          % (res['input'], res['lane'],
                             'engaged' if t['shunt'] else 'released',
                             'off->on' if t['to_on'] else 'on->off',
                             t['skipped']))
                continue
            out.write('%-9s %-4s %-8s %-9s %s %s %s %s %s %s %5s %s %6d %s '
                      '%s\n'
                      % (res['input'], res['lane'],
                         'engaged' if t['shunt'] else 'released',
                         'off->on' if t['to_on'] else 'on->off',
                         num(t['floor_dbfs']), num(t['peak_dbfs']),
                         num(t['t_peak_ms'], '%8.1f'),
                         num(t['above_floor_ms']), num(t['decay_only_ms']),
                         num(t['residual_ms']),
                         'yes' if t.get('truncated') else '-',
                         num(t['energy_db_s']),
                         t['polls'], num(t['poll_ms_mean'], '%8.2f'),
                         num(t['poll_ms_max'], '%8.2f')))


# ---------------------------------------------------------------------------
# 2.2: THE MINI-JACK INSERTION SENSE, INSIDE THE MINI-JACK PATCH STEP
# ---------------------------------------------------------------------------
# PW 2026-09-28, ADDENDUM 1: "ONE INSERTION, TWO RESULTS." The jack-switch
# detect is NOT a station of its own. The analog station already asks the
# operator to push a plug into a mini-jack (rows 95/96, patches P90/P91), so
# the detect rides that same insertion: the listen is armed BEFORE that step's
# own instruction, the on-edge is recorded while the operator's hand is on the
# connector, the L/R signal and polarity sub-tests run on the very same plug,
# and the off-edge is recorded when it comes out again.
#
# AND THE REMOVAL COSTS NOTHING EITHER, because the list already commands it.
# P90's prompt is "Patch AUX 3 to MINI-JACK 1, with MINI-JACK 2 empty" and
# P91's is "... to MINI-JACK 2, with MINI-JACK 1 empty", so the operator MUST
# take the plug out of jack 1 to make the next patch, and that removal happens
# inside the next step's own wait. So the detect is bound to the FIRST
# mini-jack patch and the off-edge is harvested across the rest of the block.
# Only if the detect patch turns out to be the LAST one in the block -- a list
# with a single mini-jack patch -- does the station spend one screen asking for
# the plug out, because then nothing else would.
#
# WHICH JACK CARRIES THE DETECT, AND WHY IT IS DECLARED AND NOT DEDUCED.
# PW: "Only the jack wired to MJ_SW (the one sense net defs declares) gets the
# detect row". defs declares ONE cell and `fw.csv` ONE net, and
# `d24-hw-inventory.csv` puts that net's NAME on BOTH mini-jack connectors
# (Analog PCBA rev B, J2 and J3, each `GND;MJ_SW;RING;TIP`), so defs cannot
# say which socket -- and a net shared by two NC contacts would not behave the
# same way as one. That is a hardware question, recorded for PW as S138b-1 and
# NOT answered here by inspecting copper. So the choice is a DECLARATION: the
# first mini-jack patch in the list, overridable with `--mj-detect-input`, and
# the check grades EDGES rather than levels so it needs neither the polarity
# nor the socket count to be settled first.
MJ_CELL = 'Sys001SwMiniJack001'
MJ_BLOCK = 'the mini-jack inputs'
# How long the one removal screen waits, in the degenerate single-patch case.
MJ_REMOVE_S = 20.0


class MiniJackSense:
    """A read-only listen on `Sys001SwMiniJack001`, for the length of a block.

    IT WRITES NOTHING. There is no `send`, no `cell_line` and no sentinel on
    this path: open the port, drain it, and read. The cell is PUSHED on every
    change (`mx_master.csv`: "both edges are reported"), so listening is the
    only way to see an edge at all -- and it is why the drain has to happen
    before the operator is told to do anything (`arm`).

    EVERY WAY IT CAN FAIL TO OPEN IS A SENTENCE, NOT AN EXCEPTION. `matrix-app`
    owns /dev/serial0 during normal operation, the pack may not carry the cell,
    and a desk run has no port at all -- none of which is a reason for the
    analog station to stop, so `why` carries the reason and `ok` is False.
    """

    def __init__(self, log=None, port=None):
        self.log = log or (lambda s: None)
        self.ok = False
        self.why = ''
        self.addr = None
        self.C = None
        self.bus = None
        self.buf = b''
        self.events = []         # (value, monotonic seconds since the arm)
        self.armed_at = None
        try:
            for p in ('/home/app/dspboot', '/home/app/selftest', HERE):
                if p not in sys.path:
                    sys.path.insert(0, p)
            import codec4619 as C                       # noqa: E402
            import matrix_addr                           # noqa: E402
            # BY NAME, OFF THIS UNIT'S OWN DEPLOYED PACK (S136). Never a
            # literal: the same name is a different address in every generation.
            addr, err = matrix_addr.try_resolve(MJ_CELL)
            if addr is None:
                self.why = err
                return
            self.C, self.addr = C, addr
            self.bus = C.Bus(port or C.PORT)
            self.ok = True
        except Exception as e:
            self.why = ('the matrix bus could not be opened for the mini-jack '
                        'sense (%s); matrix-app owns /dev/serial0 unless a '
                        'factory pass has stopped it' % e)

    def arm(self):
        """Drain the port and start counting. BEFORE the instruction goes up."""
        if not self.ok:
            return False
        try:
            import termios
            termios.tcflush(self.bus.fd, termios.TCIFLUSH)
        except Exception:
            pass
        self.buf = b''
        self.events = []
        self.armed_at = now()
        self.log('the mini-jack insertion sense is listening on %s (read only; '
                 'nothing is written to it)' % MJ_CELL)
        return True

    def drain(self):
        """Take whatever has arrived. Cheap enough for a 50 ms poll loop."""
        if not self.ok or self.armed_at is None:
            return []
        try:
            self.buf += os.read(self.bus.fd, 1024)
        except (BlockingIOError, OSError):
            pass
        got = self.C.find_cell_events(self.buf, self.addr)
        if not got:
            if len(self.buf) > 4096:
                self.buf = self.buf[-512:]
            return []
        self.buf = self.buf[max(p for _v, p in got):]
        fresh = [(v, now() - self.armed_at) for v, _p in got]
        self.events += fresh
        for v, t in fresh:
            self.log('the mini-jack sense reported %d, %.2f s after the '
                     'instruction went up' % (v, t))
        return fresh

    def close(self):
        if self.bus is not None:
            try:
                self.bus.close()
            except Exception:
                pass
            self.bus = None
        self.ok = False


def mj_verdict(sense, name, removal_asked):
    """Row 93 from what the listen heard. Returns (verdict, why, detail).

    NO TRAFFIC AT ALL IS NOT A FAIL, and on today's unit it is the expected
    answer. The flashed H1S3 image carries generation `e80ccab5d6d8` while this
    cell landed at `46109e9fb812` -- S139 measured 0 of 2,105 shared names at
    the same address between those two -- and the shipped H1S3 variant has no
    MJ_SW read in it at all. So silence is a panel-firmware precondition and
    says so; an edge one way but not the other IS a fault, because a cell that
    answered once is a cell that is alive.
    """
    if not sense.ok:
        return (NODATA, 'the mini-jack sense could not be listened to',
                sense.why)
    ev = sense.events
    if not ev:
        return (NODATA,
                'nothing was transmitted on the mini-jack sense cell while '
                'the plug went in and came out',
                'not a fault in the jack: this unit\'s panel firmware does '
                'not carry this cell yet (the flashed H1S3 is an older '
                'generation and its image has no MJ_SW read). Re-run this row '
                'after that reflash')
    vals = [v for v, _t in ev]
    if len(set(vals)) == 1:
        if not removal_asked:
            return (NODATA,
                    'only one edge was reported (%d), and nothing in this '
                    'pass asked for the plug to come out again' % vals[0],
                    'the detect is bound to the first mini-jack patch so that '
                    'the next patch\'s own prompt is the removal')
        return (FAIL,
                'the same value (%d) was reported for the plug going in and '
                'coming out, so the cell is transmitting but not following '
                'the jack' % vals[0],
                'values: %s' % ', '.join(str(v) for v in vals))
    return (PASS,
            'the sense cell changed when the plug went into %s and changed '
            'back when it came out' % name,
            'values in order: %s' % ', '.join('%d at %.2f s' % (v, t)
                                              for v, t in ev))


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
                 blocks=None, live=None, analog=None, auto_advance=True,
                 keys=None, prearm=True, trials=False, trial_only=None,
                 mj_input=None, owed_rows=None, carry=None):
        # 1.2(b). OFF unless asked for, because it is the one thing in this
        # station that applies phantom: `--click-trials`. `trial_only` is
        # `--trial-inputs`, PW naming the good channels by hand.
        self.trials = bool(trials)
        self.trial_only = set(trial_only) if trial_only else None
        self.click_results = []
        # 2.2, PW addendum 1. `mj_input` is the patch whose insertion carries
        # the detect row; None = the first mini-jack patch in the list.
        self.mj_input = mj_input
        # --verbose (S158): every reading a NOISE step's detector takes, with
        # its time from the prompt and the plateaus as they stood. The only
        # record of what the lane did between the one-line state changes.
        self.trace = False
        self.mj = None           # the listener, opened at that patch
        self.mj_patch = None     # which patch id it was armed for
        self.mj_asked_removal = False
        self.mj_done = False
        self.L = plist
        self.u = unit
        self.p = patcher
        self.g = glass
        self.lim = limits
        self.sc = Scorer(limits, log=log)
        self.log = log or (lambda s: None)
        self.only = set(blocks or ())
        self.rows_out = []
        self.timing = []
        self.floors = {}
        # THE PEAK-METER'S OWN IDLE READING, PER STRIP (S155 item 1). A strip
        # in MIC_STRIPS is watched on its PEAK meter, not the node -- `watch`'s
        # own branch -- and `floors` is a NODE RMS reading. Comparing one
        # against the other is comparing two different instruments, and a
        # peak-hold latch reads well above an RMS floor on ordinary idle noise
        # alone (S153: the same meter drains at 6.52 dB/s, so a single peek is
        # never "the idle level", only wherever the latch happens to be). See
        # `measure_floors` and `detect`'s `hot0`.
        self.peak_floors = {}
        self.live = live or LV.Live(None, enabled=False)
        self.an = analog or Analog(enabled=False)
        # PW 2026-09-28: SIGNAL ARRIVAL IS THE GO-AHEAD. This is ON, and
        # `--confirm-enter` is the 09-26 loop kept for a before/after timing run
        # -- that ruling ("let me plug the cable in, then hit Enter") is
        # superseded for every patch the detector can see. The two paths are the
        # same loop; what changes is which event ends a step and which button the
        # screen carries.
        self.auto = bool(auto_advance)
        # RULING d. On by default; `--no-pre-arm` is what a before/after
        # timing run turns off, and auto-advance has nothing to pre-arm for
        # (its step ends on the tone, so the reading is already immediate).
        self.prearm = bool(prearm) and not self.auto
        self._armed = None       # (raw rows, the confirming meter level, when)
        self.armed_kept = 0      # patches whose armed reading was confirmed
        self.armed_lost = 0      # ... and whose was not, and was re-read
        self.armed_saved_s = 0.0
        self.keys = keys or KeyWatch(enabled=False)
        self.where = {}          # patch id -> (n of N, lead n of M, lead)
        self.passed = 0
        self.failed = 0
        # Patches the operator moved past: SKIP or IGNORE. Counted apart from
        # both tallies so the end screen cannot say "all 59 passed" about a
        # pass that measured 55 of them (S127).
        self.skipped_n = 0
        self.failures = []
        self.paused = False
        self._lead_line = ''     # folded into the next instruction, then cleared
        self._lead_now = None
        self._last_in = None
        self._last_out = None
        # The reference ends, bound by the first step (S123 addendum 3). They
        # name sockets in the prompts; nothing is parked on them (PW
        # 2026-09-30: every patch is one lead plugged fresh at both ends).
        # THE FAILED-ONLY RE-RUN (S159, HUB ADDENDUM 1, PW 2026-10-01: "re-run
        # test for failed tests only"). `owed_rows` is RUN ALL's set of
        # catalog rows without a PASS; None (a standalone run) walks the whole
        # list. `carry` is what the earlier passes left that a re-run needs
        # and does not re-measure: each lane's balanced reference, the loop
        # the find step bound, and every patch's last verdict (for the patches
        # that fold onto no catalog row, and for the EIN grade).
        self.owed_rows = set(owed_rows) if owed_rows is not None else None
        self.carry = carry or {}
        self.rerun = None        # (patches walked, patches in the list)
        for lane, e in sorted((self.carry.get('lane_refs') or {}).items()):
            self.sc.ref[int(lane)] = dict(h_db=float(e['h_db']),
                                          h_deg=float(e['h_deg']),
                                          carried=e.get('pass_no', '?'))
        self._route_up = None    # the route last written by this station
        self._lane_up = None     # ... and where MeasChan was last pointed
        self._pair_seen = None   # TRS: the pair the jack really carries (S159)
        self.ref_in = None       # (panel name, strip)
        self.ref_out = None      # (panel name, drive)
        _loop = self.carry.get('loop') or {}
        if _loop.get('in') and _loop.get('out'):
            self.ref_in = (_loop['in'][0], int(_loop['in'][1]))
            self.ref_out = (_loop['out'][0], _loop['out'][1])
        self.dead_in = {}        # strip -> why, from the find-a-loop walk
        # EVERY FAILED STEP THE OPERATOR CONFIRMED (S157, PW 2026-09-30: "the
        # end-of-run failure document lists what the operator confirmed").
        # [dict(patch, what, failure, answer)], in the order they happened.
        self.confirmed = []
        self.costs = {}          # where the machine seconds went, by name
        self._confirm_was = None
        self._own_the_screen()

    def _own_the_screen(self):
        """This station's screens carry this station's buttons.

        THE SCREEN IS SHARED AND THE RULE IS NOT (S128's one-screen-per-pass, and
        this is the seam it leaves). `Live.confirm` is what `buttons_for` reads,
        and under RUN ALL one `Live` is built for the whole pass with
        `confirm=True` -- which is right for the setup pages, because they really
        do ask for ENTER. Left alone, every WAITING screen this station wrote
        under RUN ALL would carry an ENTER button that ends nothing: the same
        dead-button fault S137 found on the panel loop, one station along.

        So the station takes the flag for as long as it owns the screen and
        `teardown` puts it back. A standalone run's `Live` was built with the
        right value already and this changes nothing there.
        """
        want = not self.auto
        if self.live.confirm != want:
            self._confirm_was = self.live.confirm
            self.live.confirm = want

    # -- setup -------------------------------------------------------------
    def standing(self):
        t0 = now()
        try:
            return self._standing()
        finally:
            self.cost('getting the unit ready', now() - t0)

    def _standing(self):
        self.live.set(state=LV.STARTING)
        self.an.up()
        donors = sorted({int(r['donor']) for r in self.L.paths})
        byp = self.bypass_capture()
        cells = self.L.standing(donors) + byp
        self.log('standing write: %d cells (every strip\'s assigns shut, both '
                 'donor strips made transparent, every bus master at unity, '
                 '%d processing cells bypassed and restored at handback)'
                 % (len(cells), len(byp)))
        bad = self.u.write(cells)
        if bad:
            raise SystemExit('the standing write did not land: %s'
                             % ', '.join(sorted(bad)[:8]))
        self.measure_floors()
        return len(cells)

    def bypass_capture(self):
        """Read every bypass cell BEFORE it is written (S154, PW ruling:
        "the handback RESTORES each cell to the value found"). Returns the
        bypass specs to write.

        A record left by an earlier pass wins over a fresh read: that pass
        wrote the bypass and never got to its handback, so what the cells
        hold NOW is the bypass, not the product's settings."""
        specs = self.L.bypass()
        if not specs:
            self._bypass_found = {}
            return []
        path = getattr(self.u, 'bypass_state', None)
        found = {}
        if path and os.path.exists(path):
            with open(path) as fh:
                found = json.load(fh)
            self.log('bypass: %d settings from an earlier pass that never '
                     'restored them (%s) -- restoring THOSE at handback, not '
                     'what the cells hold now' % (len(found), path))
        for spec in specs:
            name = spec.partition('=')[0]
            if name not in found:
                found[name] = self.u.read(name) & 0xFFFFFFFF
        if path:
            tmp = path + '.tmp'
            with open(tmp, 'w') as fh:
                json.dump(found, fh, indent=0, sort_keys=True)
            os.replace(tmp, path)
        self._bypass_found = found
        on = sorted(n for n, w in found.items() if w != 0)
        self.log('bypass: %d processing cells read; %d were not 0: %s'
                 % (len(found), len(on), ', '.join(on[:12])
                    + (' ...' if len(on) > 12 else '')))
        return specs

    def bypass_restore(self):
        """Write every bypassed cell back to the value found, and verify it.
        The record is removed only when every one read back."""
        found = getattr(self, '_bypass_found', None)
        if not found:
            return []
        bad = self.u.write(['%s=0x%08X' % (n, w)
                            for n, w in sorted(found.items())])
        path = getattr(self.u, 'bypass_state', None)
        if bad:
            self.log('bypass: %d settings did NOT read back after the '
                     'restore (%s); the record stays at %s for the next pass'
                     % (len(bad), ', '.join(sorted(bad)[:8]), path))
        else:
            self.log('bypass: %d processing settings restored to the values '
                     'found' % len(found))
            if path and os.path.exists(path):
                os.remove(path)
            self._bypass_found = {}
        return bad

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
            # THE PEAK METER'S OWN FLOOR, SAME LANE, SAME MOMENT (S155 item
            # 1). `measure()` just spent SETTLE_WINDOWS+READ_WINDOWS worth of
            # real time on this lane, so the latch is not fresh off the
            # standing write either -- two peeks, WIN_S apart, and the lower
            # one, so a latch still draining reads as what it is heading for,
            # not as wherever it happened to be caught.
            if lane in MIC_STRIPS:
                p1 = self.u.meter_peak(lane)
                nap(WIN_S)
                p2 = self.u.meter_peak(lane)
                peeks = [dbv(v) for v in (p1, p2) if v]
                if peeks:
                    self.peak_floors[lane] = min(peeks)
        pk = list(self.peak_floors.values())
        self.log('floors: %d lanes, %.1f to %.1f dBFS (node RMS); peak floor '
                 '%s'
                 % (len(lanes),
                    min(v for v in self.floors.values() if v is not None),
                    max(v for v in self.floors.values() if v is not None),
                    ('%.1f to %.1f dBFS' % (min(pk), max(pk))) if pk
                    else 'n/a'))

    # -- one patch ---------------------------------------------------------
    def prepare(self, rows):
        t0 = now()
        try:
            return self._prepare(rows)
        finally:
            self.cost('putting the route up', now() - t0)

    def _prepare(self, rows):
        """Assert the first sub-test's route, point the instrument, and read
        the lane with NOTHING plugged in. That baseline is two things at once:
        what the auto-advance watches for a change in, and the floor the tone
        has to rise above for the reading to count."""
        r = rows[0]
        lane = int(r['lane'])
        self.u.write(self.L.routes[r['route']])
        self._route_up = r['route']
        self._lane_up = lane
        # The preamp gain this patch starts at. A gain-step patch starts at
        # code 0 (its own reference); the noise patch starts at full gain,
        # which is also what makes the terminator's insertion visible.
        if str(r.get('gain_code') or '') != '' and r.get('send_pos') != '':
            self.an.image = None
            self.an.chain(self.an.step_image(r['send_pos'],
                                             int(r['gain_code'])),
                          '%s at gain code %s' % (r['in'], r['gain_code']))
            if self.an.wrote:
                self.u.mark_moved()
        freq = float(r['freq_hz']) if r['freq_hz'] else None
        lvl = float(r['level_dbfs']) if r['level_dbfs'] else None
        if r['expect'] == 'noise':
            self.u.osc(on=False)
        else:
            self.u.osc(chan=int(r['donor']), freq=freq, level_dbfs=lvl, on=True)
        self.u.meas_chan(lane)
        # 2.2, PW ADDENDUM 1: THE LISTEN IS ARMED HERE, AND HERE IS WHY.
        # `_prepare` is the last thing that happens before `p.connect` and
        # `announce` -- i.e. before the operator is told anything at all -- in
        # BOTH paths into this method (the first patch of a block, and the
        # pipeline's look-ahead). So a drain here cannot miss an edge, and an
        # edge cannot land in a window nothing is watching.
        self.mj_arm(rows)
        return dict(lane=lane, freq=freq, level=lvl,
                    floor=self.floors.get(lane),
                    watch=self.watch(lane),
                    sweep0=self.u.meter_sweep(MIC_STRIPS))

    # -- 2.2 the mini-jack insertion sense, on the patch step ---------------
    def mj_detect_patch(self):
        """The patch id whose insertion carries row 93, or None.

        DECLARED, NOT DEDUCED -- see the note on `MiniJackSense`. The default
        is the FIRST mini-jack patch in the list, which is what makes the
        removal free: the NEXT mini-jack patch's own prompt ("... with
        MINI-JACK 1 empty") is the instruction that takes the plug out again.
        """
        mine = [(pid, rows) for pid, rows in self.L.patches
                if rows[0]['block'] == MJ_BLOCK]
        if not mine:
            return None, None
        if self.mj_input:
            for pid, rows in mine:
                if rows[0]['in'] == self.mj_input:
                    return pid, rows[0]['in']
            self.log('--mj-detect-input %r is not a mini-jack patch in this '
                     'list; the detect stays on %s'
                     % (self.mj_input, mine[0][1][0]['in']))
        return mine[0][0], mine[0][1][0]['in']

    def mj_arm(self, rows):
        """Open and arm the listen, if this is the patch that carries row 93."""
        if self.mj_done:
            return
        pid, _name = self.mj_detect_patch()
        if pid is None or rows[0]['patch'] != pid:
            return
        if self.mj is None:
            self.mj = MiniJackSense(log=self.log)
            if not self.mj.ok:
                self.log('the mini-jack insertion sense is not being listened '
                         'to: %s' % self.mj.why)
        self.mj_patch = pid
        self.mj.arm()

    def mj_drain(self):
        """Called from the wait loop, so the edge is caught while the hand is
        on the connector rather than read for afterwards."""
        if self.mj is not None and self.mj_patch is not None:
            self.mj.drain()

    def mj_close(self, ask=True):
        """Score row 93 and put the listener away. Runs once, on every way out.

        IT APPENDS TO `self.rows_out` IN PLACE, and it has to: `run()` hands
        that same list object back and `patch_station` folds the RETURN VALUE
        onto the catalog rows, so a row appended to a copy would be scored by a
        standalone run and lost under RUN ALL.

        THE ONE SCREEN THIS MAY SPEND, and only in the degenerate case: if the
        detect patch was also the LAST mini-jack patch then no later prompt
        ever asked for the plug to come out, so the off-edge would be missing
        for a reason that is nothing to do with the unit. Then, and only then,
        one removal screen is put up -- never after a PAUSE, a signal or an
        exception, which is what `ask` is for.
        """
        if self.mj is None or self.mj_done:
            return
        self.mj_done = True
        pid, name = self.mj_detect_patch()
        try:
            self.mj.drain()
            vals = {v for v, _t in self.mj.events}
            if ask and self.mj.ok and len(vals) == 1 and not self.paused:
                later = [p for p, rs in self.L.patches
                         if rs[0]['block'] == MJ_BLOCK and p != pid]
                if not later:
                    self.mj_asked_removal = True
                    self.lamp_ask('Take the plug out of %s.' % name, 0, 0,
                                  'Mini-jack insertion sense', fault=None,
                                  secs=MJ_REMOVE_S)
                    t0 = now()
                    while now() - t0 < MJ_REMOVE_S and len(vals) < 2:
                        self.mj.drain()
                        vals = {v for v, _t in self.mj.events}
                        nap(0.05)
            else:
                self.mj_asked_removal = True
            v, why, detail = mj_verdict(self.mj, name or 'the mini-jack input',
                                        self.mj_asked_removal)
            self.log('the mini-jack insertion sense (row 93): %s -- %s'
                     % (v, why))
            self.rows_out.append(dict(
                path='', patch=pid or 'MJ', lead='K3', out='',
                **{'in': name or 'the mini-jack input'},
                sub='jack-switch detect', rows='93', verdict=v, why=why,
                detail=detail, h_db=None, h_deg=None, thd_db=None,
                noise_db=None, rms_db=None))
        finally:
            self.mj.close()

    def watch(self, lane, rms=False, settle=0):
        """The cheap level the auto-advance polls, in dB.

        A strip has a meter node and a meter needs no settling window, so a
        peek is current within a block -- that is the detector. The three codec
        return lanes (the talkback XLR and the two mini-jack legs) have no
        meter of their own, so those patches watch the measurement node's own
        RmsResult instead: MeasChan is already pointed at them and is not
        moving, so the reading costs one SPI read and no settle.

        `rms=True` is the NOISE step's instrument on every lane, strips too
        (S153). The strip meter is a peak-hold latch: on noise at gain 63 it is
        a sawtooth of random peaks draining at 6.52 dB/s, which is what made
        the 150 ohm step take 14-17 s, and at the prompt it is still holding
        the gain step's tone, which is what made the other steps end at 2.7 s
        on the drain alone. The node's RMS over one 85.3 ms window is steady
        to tenths of a dB on a terminated input. Each poll waits for the NEXT
        window (`settle` >= 1) so no two readings are the same window, and
        `settle` is what the caller owes on top of that.
        """
        if lane in MIC_STRIPS and not rms:
            v = self.u.meter_peak(lane)
            return dbv(v) if v else None
        m = self.u.measure(None, 0.0, windows=1,
                           settle=max(1, settle) if rms else 0)
        v = m.get('rms')
        return v if v is not None and math.isfinite(v) else None

    def _terminator_met(self, r, lvl, drop):
        """The 150 ohm step's arrival test, on the node's RMS (S158).

        Read against the OPEN input the lane has been showing, never against
        a plateau history: S157's plateau list let a wiggle of the tone lead
        stand in for the open input, and MIC 1's P13 on 2026-10-01 was graded
        on the open input at -76.9 dBFS (terminated is -87.0).

        The reference is the median of up to TERM_REF_SPAN readings before the
        last three, so a transient at the prompt is outvoted and a slow drift
        is followed rather than mistaken for a plug; it is FROZEN while the
        lane is under it, so the stability window is judged against the open
        input and not against the plug's own first readings. See TERM_* for
        the rule and the numbers.
        """
        T = self._term
        reads = T['reads']
        if (T['ref_db'] is not None and T['burst_at'] is None
                and lvl >= T['ref_db'] + TERM_BURST_DB):
            T['burst_at'] = now() - self._t0_step
            self.log('%s: something went into %s at %.1f s (%.1f dBFS, %.1f dB '
                     'over the open input)' % (r['patch'], r['in'],
                                               T['burst_at'], lvl,
                                               lvl - T['ref_db']))
        reads.append(lvl)
        if len(reads) < TERM_REF_READINGS + 3:
            return False
        ref = T['frozen']
        if ref is None:
            ref = statistics.median(reads[-(3 + TERM_REF_SPAN):-3])
            if T['ref_db'] is None:
                self.log('%s: %s open at the prompt: %.1f dBFS (node RMS, '
                         'median of %d)' % (r['patch'], r['in'], ref,
                                            len(reads) - 3))
        T['ref_db'] = ref
        burst = (T['burst_at'] is not None and now() - self._t0_step
                 - T['burst_at'] <= TERM_BURST_HOLD_S)
        med = statistics.median(reads[-3:])
        met = (med <= ref - drop or (burst and med <= ref - TERM_SMALL_STEP_DB)
               or (T['frozen'] is not None and med <= ref - TERM_SMALL_STEP_DB
                   and T['frozen_burst']))
        if met and T['frozen'] is None:
            T['frozen'], T['frozen_burst'] = ref, burst
        elif not met:
            T['frozen'], T['frozen_burst'] = None, False
            if not burst:
                T['burst_at'] = None
        return met

    def _term_words(self, lvl):
        T = self._term
        if T.get('ref_db') is None:
            return 'no open reading yet'
        return ('open %.1f dBFS, now %.1f (%.1f dB under it)%s'
                % (T['ref_db'], lvl, T['ref_db'] - lvl,
                   ', insertion at %.1f s' % T['burst_at']
                   if T.get('burst_at') is not None else ', no insertion seen'))

    def prearm_ok(self, rows):
        """Whether this patch's reading may be taken before ENTER (ruling d).

        TONE ROWS ONLY, and not the gain steps. PW: "Gain steps, EIN and
        no-tone rows are unchanged (measure after ENTER)." A gain-step patch is
        seven chain writes and seven readings with the drive moving under them;
        its first row is also the patch's tone reference, so the patch is
        excluded whole rather than half-armed.
        """
        if not self.prearm:
            return False
        r = rows[0]
        if r['expect'] != 'tone':
            return False
        # ONE DRIVE AND ONE LANE, OR NO PRE-ARM (S159). `arm` runs `acquire`,
        # which walks every sub-test -- and on a stereo TRS patch the last one
        # is the NULL, so the route left up afterwards was both legs in phase,
        # and the stability window that follows the pre-arm then watched the
        # null residual instead of the tip: a patch that arrives once and then
        # "goes away again" for ever. The mini-jack pair is the same shape on
        # the lane (MeasChan left on the R leg). Those patches wait for their
        # first row's single drive to be steady and only then read L / R /
        # null, which is what the factory (auto) path has always done.
        if (len({x['route'] for x in rows}) > 1
                or len({str(x['lane']) for x in rows}) > 1):
            return False
        return str(r.get('gain_code') or '') == ''

    def arm(self, rows, prep):
        """Take the reading NOW, the instant the tone arrived (ruling d).

        Nothing is scored, recorded or shown here. The rows come back with the
        confirming meter level beside them, and `confirm_armed` at ENTER
        decides whether they are used or thrown away.
        """
        t0 = now()
        was = dict(self.costs)
        raw = self.acquire(rows, prep)
        lvl = self.watch(int(rows[-1]['lane']))
        worst = max((x['meas'].get('rms_spread') or 0.0) for x in raw)
        self._armed = dict(raw=raw, level=lvl, at=now(), spread=worst,
                           cost=now() - t0)
        # ONE BUCKET, NOT TWO. `acquire` books its own seconds under `settled
        # readings`, and a pre-armed reading is not a second lot of them: it is
        # the SAME reading, moved off the operator's path. So the inner buckets
        # are put back and the whole cost is booked here, where the cost table
        # can be added up without counting anything twice.
        self.costs = was
        self.cost('pre-armed readings', now() - t0)
        self.log('pre-armed %s %.3f s after the tone arrived (window spread '
                 '%.2f dB)' % (rows[0]['patch'], now() - t0, worst))

    def confirm_armed(self, rows):
        """At ENTER: one meter peek, and the armed reading kept or thrown.

        Returns (raw, seconds saved) or (None, 0.0). The three ways an armed
        reading is refused are all measurements, not opinions: its own windows
        disagreed (the lead was moving while it was taken), the lane has moved
        since (the lead was pushed home, or came out), or the lane has nothing
        on it to peek at.
        """
        a, self._armed = self._armed, None
        if a is None:
            return None, 0.0
        why = None
        if a['spread'] > PREARM_STABLE_DB:
            why = ('its own windows disagreed by %.2f dB, which is a connector '
                   'still moving' % a['spread'])
        else:
            lvl = self.watch(int(rows[-1]['lane']))
            if lvl is None or a['level'] is None:
                why = 'the lane has no level to peek at'
            elif abs(lvl - a['level']) > PREARM_AGREE_DB:
                why = ('the lane moved %.2f dB between the reading and ENTER'
                       % (lvl - a['level']))
        if why:
            self.armed_lost += 1
            self.log('%s: the early reading was not used -- %s; re-reading'
                     % (rows[0]['patch'], why))
            return None, 0.0
        self.armed_kept += 1
        self.armed_saved_s += a['cost']
        return a['raw'], a['cost']

    def waiting(self, **kw):
        """Put the screen into WAITING without throwing the last patch's
        verdict banner away.

        S128 HOTFIX. `Live.set(state=WAITING)` clears `banner` on purpose --
        a state change normally means the banner is stale -- but the pipeline
        screen is a deliberate exception: the NEXT patch's instruction goes up
        (`announce`, state WAITING) and the LAST patch's verdict is then
        written over the top of it (`record`, state VERDICT). The two together
        are the screen PW reviewed: "PASS - MIC 7, terminated" above "Plug
        AUX 1 into MIC 9, then press ENTER."

        What that leaves behind is the STATE, and the state is what picks the
        buttons. `buttons_for(VERDICT)` is `['pause']`, so the glass said
        "press ENTER" with no ENTER on it. This carries the banner across so a
        caller can say WAITING -- which is the truth, something is waiting for
        the operator -- without losing the reviewed screen.
        """
        d = self.live.d
        # A SCREEN THAT ALREADY OFFERS ENTER IS LEFT ALONE. `CHECKLEAD` is the
        # one: `reprompt` puts it up deliberately, red, with its own action
        # line, immediately before the loop is re-entered, and its buttons are
        # already `enter`+`pause`. Nothing is broken there and re-stating it as
        # WAITING would quietly lose a named state that the screen dump and the
        # wording review both know by name.
        # LEADS CORRECT (`nosignal`) is the same case since PW's 2026-09-29
        # ruling moved it onto CHECK THE LEAD only: restating that screen as
        # WAITING kept its "press LEADS CORRECT" and took the button away.
        # A caller that names the banner or the action is REPLACING that
        # screen (a wrong-socket warning coming down once the lead is right),
        # and goes through.
        if ({'enter', 'nosignal'} & set(d.get('buttons') or [])
                and not {'banner', 'action'} & set(kw)):
            return
        for k in ('banner', 'banner_line', 'action'):
            kw.setdefault(k, d.get(k, ''))
        self.live.set(state=LV.WAITING, **kw)

    def watch_tone(self, lane, prep, settle=1):
        """THE TONE ROW'S INSTRUMENT (S157): the node's COHERENT level, dBFS.

        One window of the measurement node, fitted against the oscillator --
        the same `coh_dbfs` the verdict reads. Only the energy at the tone's
        own frequency and phase counts, so an open input at gain 63 (about
        -54 dBFS RMS) reads some 30 dB lower on it than on RmsResult, and an
        idle lane reads BELOW its own RMS floor. "coherent >= floor + rise"
        therefore says the tone is on this lane NOW: no residual, no decay and
        no history can pass it, because the node has none -- which is the
        whole of what the peak-hold latch got wrong (S155 P1/P6/P56).

        Each call waits for the NEXT window (`settle` >= 1), so no two polls
        read the same window. A lane with no fit (the oscillator off, or a
        part with no `_osc_k`) falls back to the RMS, which is still the node.
        """
        m = self.u.measure(prep.get('freq'), prep.get('level') or 0.0,
                           windows=1, settle=max(1, settle))
        v = m.get('coh_dbfs')
        if v is None or not math.isfinite(v):
            v = m.get('rms')
        return v if v is not None and math.isfinite(v) else None

    def steady_elsewhere(self, lane, donor, sweep, prev):
        """A lane OTHER than `lane` that is carrying a tone, or None (S157).

        THE PEAK METER IS A HINT, AND THIS IS THE ONLY WAY A HINT BECOMES A
        CLAIM. A lane counts only if it is `detect_rise_db` over its OWN peak
        floor in BOTH sweeps (`prev` and `sweep`, taken at least a stability
        window apart) AND the two readings agree within DETECT_STEADY_DB. A
        peak-hold latch that is merely DRAINING -- the lane the last patch
        used, or one the gain-63 step left noisy -- falls 6.5 dB/s and fails
        the second test; a lane that is really carrying a tone reads flat on
        a peak-hold meter and passes it. That is what the P1 "MIC 15" and P7
        "MIC 23" claims were: one peek at a latch, not a lead.
        """
        if not prev:
            return None
        rise = self.lim['detect_rise_db']
        lit = []
        for k, v in sweep.items():
            if k == lane or k == donor or not v:
                continue
            fl = self.peak_floors.get(k)
            v0 = prev.get(k)
            if fl is None or not v0:
                continue
            a, b = dbv(v0), dbv(v)
            if (a - fl >= rise and b - fl >= rise
                    and abs(b - a) <= DETECT_STEADY_DB):
                lit.append((b - fl, k))
        if not lit:
            return None
        lit.sort(reverse=True)
        return 'MIC %d' % lit[0][1]

    def _step_log(self, r, state, lvl, floor, why=''):
        """One line per state transition (S157 design): lane, level, floor,
        instrument, state."""
        self.log('%s %s: %s level %s, floor %s (node%s)%s'
                 % (r['patch'], state, r['in'],
                    ('%.1f' % lvl) if lvl is not None else '--',
                    ('%.1f' % floor) if floor is not None else '--',
                    ' coherent' if r['expect'] != 'noise' else ' RMS',
                    (' -- ' + why) if why else ''))

    def detect(self, rows, prep, token, status=None):
        """Wait for the operator's hands, not for their Enter -- the S157
        state machine (MW/D24/DSP/s157/s157-design.md).

            PROMPTED -> WAITING -> ARRIVING -> ARRIVED        the PASS path
            WAITING  -> WRONG_SOCKET (a steady hint elsewhere; keeps listening)
            WAITING  -> FAILED at detect_timeout_s (keeps listening)
            FAILED   -> nosignal / retry / pause, or an arrival

        TONE ROWS are judged on the NODE'S COHERENT LEVEL (`watch_tone`)
        against the lane's own idle floor: arrival is coherent >= floor +
        `detect_rise_db`, held for the stability window. Every patch is one
        lead plugged fresh at both ends (PW 2026-09-30), and the route for
        this patch was written before the prompt, so whatever the lane carries
        at the prompt is THIS route's tone or nothing: there is no removal
        edge on a tone row, and no "already carrying". A lead that is already
        in the right place when the prompt goes up is simply an early arrival.
        Nothing in the test depends on how fast the operator moves or on what
        the last patch left behind.

        NOISE ROWS (S158): in the 150 ohm pass the socket is empty at the
        prompt, and the plug going into it is read on the node's RMS against
        that open input (`_terminator_met`); ENTER is on the screen throughout
        and always ends the step. In the old per-input order the tone lead is
        in the socket at the prompt, and that step ends on ENTER only.

        NOTHING HERE ENDS A STEP BY ITSELF EXCEPT AN ARRIVAL (PW 2026-09-30:
        "the runner never moves past a fail without operator confirmation").
        The timeout raises the FAILED screen and the loop keeps listening, so
        a lead pushed home still arrives; there is no hard bound. What ends a
        failed step is the operator: NO SIGNAL ('nosignal', LEADS CORRECT on
        the glass) records it, RETRY runs it again from the prompt, PAUSE
        pauses.

        Returns (how, answer, seconds): how is 'rise' / 'drop' (arrived),
        'nosignal', 'retry', 'glass' (answer carries the button), and on the
        ENTER path 'enter-ok' / 'enter-no'.
        """
        r = rows[0]
        lane = prep['lane']
        rise = self.lim['detect_rise_db']
        drop = self.lim['detect_drop_db']
        tone = r['expect'] != 'noise'
        donor = int(r['donor']) if str(r.get('donor') or '').isdigit() else None
        t0 = self._t0_step = now()
        self._met_at = None
        self._stable = []
        self._wrong = None
        self._wrong_candidate = None
        self._wrong_hits = 0
        self._hinted = False
        self._sweep_prev = None
        self._pair_seen = None
        self._pair_next = 0.0
        self._parked = False
        self.waiting(status=status or LV.status_words(LV.WAITING))
        # The timeout raises the question; it no longer ends the step on the
        # ruled path. On the ENTER path it is ENTER_PATIENCE times the list's
        # number, as it always was.
        deadline_s = self.lim['detect_timeout_s'] * (1 if self.auto
                                                     else ENTER_PATIENCE)
        # THE FIRST PATCH OF A RUN GETS TWICE THE PATIENCE (S158). P1 of
        # 2026-10-01 timed out at 20 s and arrived at 22.6: the operator had
        # just come from the setup pages and picked the lead up. The red
        # screen decides nothing, but it should not be the first thing the
        # walk shows a worker who is doing nothing wrong.
        deadline_s *= getattr(self, '_patience', 1.0)
        # THE 150 OHM STEP IS ONE OF TWO SHAPES (S158). In the 150 ohm pass
        # the socket is empty at the prompt and the step auto-advances on the
        # plug (`_terminator_met`). If the patch before this one had the tone
        # lead in THIS socket (the old per-input order) the prompt reading is
        # the lead, not the open input, and no level rule can be trusted to
        # tell the lead coming out from the plug going in -- that step ends on
        # ENTER only.
        press_only = (not tone and getattr(self, '_prev_in', None) == r['in']
                      and getattr(self, '_prev_tone', False))
        self._term = dict(ref_db=None, burst_at=None, reads=[], frozen=None,
                          frozen_burst=False, out=False, warned=False,
                          press_only=press_only)
        floor0 = prep.get('floor')
        settle0 = self.u.settle_owed(SETTLE_WINDOWS)
        if tone:
            lvl0 = self.watch_tone(lane, prep, settle=settle0)
        else:
            lvl0 = self.watch(lane, rms=True, settle=settle0)
            if lvl0 is not None and math.isfinite(lvl0):
                self.log('%s: %s as the prompt went up: %.1f dBFS (node RMS)'
                         % (r['patch'], r['in'], lvl0))
        self._step_log(r, 'PROMPTED', lvl0, floor0,
                       'rise %.1f dB' % rise if tone else
                       'the terminator step: ENTER only, the tone lead was in '
                       'this socket' if press_only else
                       'the terminator step: the plug into an open input, or '
                       'ENTER')
        next_sweep = t0 + WRONG_INPUT_POLL_S
        raised = False
        state = 'WAITING'
        first = lvl0 if tone else None
        while True:
            self.live.beat()
            self.mj_drain()
            cmd = self.live.command()
            if cmd == 'pause':
                return ('glass', dict(button='pause', reason='the screen'),
                        now() - t0)
            if cmd == 'retry':
                self._step_log(r, 'RETRY', None, floor0,
                               'the operator asked for it again from the '
                               'prompt after %.1f s' % (now() - t0))
                return ('retry', None, now() - t0)
            entered = (cmd == 'enter') or self.keys.pressed()
            said_nothing = (cmd == 'nosignal')
            ans = self.p.poll(token)
            if ans is not None:
                b = ans.get('button')
                if b in ('done', 'ack'):
                    entered = True
                elif b == 'retry':
                    return ('retry', None, now() - t0)
                elif b == 'nosignal':
                    said_nothing = True
                else:
                    return ('glass', ans, now() - t0)
            # S163: A NAMED WRONG PAIR IS PARKED. Once the probe has found the
            # pair this jack carries the station stops driving and stops
            # listening: the probe's own tones and the route put back after
            # them were what kept raising ARRIVING / WAITING every 0.7 s over
            # the screen. Only a button leaves it -- LEADS CORRECT records the
            # jack order, RETRY (handled above) re-prompts, PAUSE pauses. A
            # lead moved by hand does nothing until RETRY; there is no loop.
            if self._parked:
                if said_nothing:
                    self._step_log(r, 'NO SIGNAL', None, floor0,
                                   'LEADS CORRECT on the wrong-pair screen '
                                   'after %.1f s: the jack order is recorded'
                                   % (now() - t0))
                    return ('nosignal', None, now() - t0)
                nap(DETECT_POLL_S)
                continue
            met = False
            if first is not None:
                lvl, first = first, None          # the prompt's own reading
            elif tone:
                lvl = self.watch_tone(lane, prep)
            else:
                lvl = self.watch(lane, rms=True)
            if lvl is not None and math.isfinite(lvl):
                if tone:
                    met = floor0 is not None and lvl - floor0 >= rise
                elif press_only:
                    self._term['reads'].append(lvl)
                    if (lvl0 is not None and statistics.median(
                            self._term['reads'][-3:]) <= lvl0 - drop):
                        self._term['out'] = True
                else:
                    met = self._terminator_met(r, lvl, drop)
            if self.trace and not tone:
                self.log('%s TRACE %6.2f s  %s dBFS  %s  open %s  insertion %s'
                         % (r['patch'], now() - t0,
                            ('%.2f' % lvl) if lvl is not None else '--',
                            'met' if met else '   ',
                            ('%.1f' % self._term['ref_db'])
                            if self._term['ref_db'] is not None else '--',
                            ('%.1f s' % self._term['burst_at'])
                            if self._term['burst_at'] is not None else '--'))
            if met and self._met_at is None:
                self._met_at = now()
                self._stable = [(now(), lvl)]
                self._sweep_arrive = (self.u.meter_sweep(MIC_STRIPS)
                                      if tone else None)
                self.u.mark_moved()
                self._wrong = None
                state = 'ARRIVING'
                self._step_log(r, state, lvl, floor0)
                if self.prearm_ok(rows):
                    self.live.set(state=LV.CHECKING)
                    self.arm(rows, prep)
                    self.waiting(status=LV.SIGNAL_SEEN)
                    self._hinted = True
                elif self.auto:
                    self.waiting(status=LV.SIGNAL_HOLDING, banner='',
                                 banner_line='', action='')
                    self._hinted = True
            elif met:
                self._stable.append((now(), lvl))
            elif self._met_at is not None:
                self._step_log(r, 'WAITING', lvl, floor0,
                               'the signal went away again after %.0f ms; the '
                               'stability window starts over'
                               % (1000.0 * (now() - self._met_at)))
                self._met_at, self._stable = None, []
                self._hinted = False
                state = 'WAITING'
                if not raised:
                    self.waiting(status=status or LV.status_words(LV.WAITING),
                                 banner='', banner_line='', action='')
            if self.auto and self._met_at is not None:
                ok, why = self._stable_ok()
                if ok and not tone:
                    why += ', node RMS ' + self._term_words(lvl)
                if ok and tone and self._sweep_arrive is not None:
                    # ISOLATED: no other lane steadily carrying across the
                    # stability window. Logged, never blocking -- a tone that
                    # is on two lanes is graded, and the verdict's own
                    # isolation check FAILS it, which stops the station.
                    other = self.steady_elsewhere(
                        lane, donor, self.u.meter_sweep(MIC_STRIPS),
                        self._sweep_arrive)
                    why += (', isolated' if other is None else
                            ', NOT isolated -- %s is steady too; the verdict '
                            'judges it' % other)
                if ok:
                    self._step_log(r, 'ARRIVED', lvl, floor0,
                                   '%s after %.0f ms, present and steady (%d '
                                   'blocks, %d readings, spread %s)'
                                   % ('drop' if not tone else 'rise',
                                      1000.0 * (now() - t0),
                                      DETECT_STABLE_BLOCKS,
                                      len(self._stable), why))
                    return (('drop' if not tone else 'rise'), None, now() - t0)
            if tone and self._met_at is None and now() >= next_sweep:
                next_sweep = now() + WRONG_INPUT_POLL_S
                self._look_elsewhere(r, lane, status, raised)
            # THE 150 OHM STEP: ENTER (or LEADS CORRECT, from an older screen)
            # is the operator saying the plug is in, and it is measured. The
            # one refusal is the per-input order's: the tone lead was in this
            # socket and the lane never fell from it, so the press is asked
            # once more before the lead's own noise is recorded as the input's.
            if not tone and self.auto and (entered or said_nothing):
                if (press_only and not self._term['out']
                        and not self._term['warned']):
                    self._term['warned'] = True
                    self.log('%s: ENTER, but %s still reads %.1f dBFS, as it '
                             'did with the tone lead in -- asking once more'
                             % (r['patch'], r['in'], lvl if lvl is not None
                                else float('nan')))
                    self.live.set(state=LV.WAITING,
                                  status=LV.terminator_lead_still_in(r['in']))
                    nap(DETECT_POLL_S)
                    continue
                self._step_log(r, 'ENTER', lvl, floor0,
                               'the operator says the terminator is in, after '
                               '%.1f s; %s' % (now() - t0,
                                               self._term_words(lvl)
                                               if lvl is not None else ''))
                return ('press', None, now() - t0)
            if entered and not self.auto:
                return (('enter-ok' if met else 'enter-no'), None, now() - t0)
            if entered and self.auto and self._met_at is None:
                if raised:
                    self.log('%s: ENTER with the no-signal question already up '
                             '-- taken as the answer' % r['patch'])
                    said_nothing = True
                else:
                    raised = True
                    self._raise_no_signal(r, lane, now() - t0)
            elif entered and self.auto:
                self.log('%s: ENTER while the signal is arriving -- the step '
                         'ends on the signal, so it changes nothing'
                         % r['patch'])
            if said_nothing:
                # A tone that is steadily on ANOTHER socket is not a dead
                # path: the press is answered with where it is, never graded.
                where = self._wrong or self._hint_now(lane, donor)
                if where:
                    self.log('%s: NO SIGNAL pressed, but the tone is on %s -- '
                             'not graded; asking again' % (r['patch'], where))
                    self._say_wrong(r, where)
                    continue
                self._step_log(r, 'NO SIGNAL', lvl, floor0,
                               'the operator pressed it after %.1f s'
                               % (now() - t0))
                return ('nosignal', None, now() - t0)
            if not self.auto and met != self._hinted:
                self._hinted = met
                self.waiting(status=(LV.SIGNAL_SEEN if met
                                     else LV.status_words(LV.WAITING)))
            waited = now() - t0
            if (not tone and not raised and waited >= deadline_s
                    and self._met_at is None):
                # No red screen on the 150 ohm step: ENTER has been on it all
                # along, and a step that cannot fail cannot time out into one.
                raised = True
                self._step_log(r, 'WAITING', lvl, floor0,
                               'nothing seen in %.1f s; ENTER ends it (%s)'
                               % (waited, self._term_words(lvl)
                                  if lvl is not None else ''))
                self.live.set(state=LV.WAITING,
                              status=LV.terminator_timeout_words(r['in']))
            if not raised and waited >= deadline_s and self._met_at is None:
                raised = True
                self._step_log(r, 'FAILED', lvl, floor0,
                               'nothing has arrived in %.1f s; waiting for the '
                               'operator (LEADS CORRECT / RETRY / PAUSE)'
                               % waited)
                self._raise_no_signal(r, lane, waited)
            # THE TRS PAIR PROBE (S159). A stereo TRS patch whose tip never
            # arrived is driven on the other pairs' tips, one at a time, and a
            # jack that lights on one of them is named on the glass. Only once
            # the step has FAILED, so a patch on its way in is never disturbed.
            if (tone and raised and self._met_at is None and self.trs(rows)
                    and now() >= self._pair_next):
                self._pair_next = now() + TRS_PROBE_EVERY_S
                got = self._probe_pairs(r, lane, prep, floor0)
                if got and got != self._pair_seen:
                    self._pair_seen = got
                    self._parked = True
                    self._met_at, self._stable = None, []
                    self.log('%s WRONG_PAIR: nothing on the tip of %s, but '
                             'AUX %d reaches %s through this jack -- it '
                             'carries %s' % (r['patch'], r['out'], got[0],
                                             r['in'], self.pair_name(got)))
                    self.live.set(state=LV.CHECKLEAD, banner='CHECK THE LEAD',
                                  banner_line='',
                                  status=LV.status_wrong_pair(
                                      self.pair_name(got), r['out']),
                                  action=LV.action_wrong_pair(
                                      self.pair_name(got), r['out']))
            # NO HARD BOUND ON THE RULED PATH (S157). The ENTER path, kept for
            # a timing run, still ends at its own deadline.
            if not self.auto and waited >= deadline_s:
                return ('enter-no', None, waited)
            nap(DETECT_POLL_S)

    def _stable_ok(self):
        """Has the lane been present and steady long enough to grade?

        THE WINDOW SLIDES, and it has to. A window measured from the first poll
        that saw the signal is a window that never recovers: a connector that
        wobbles 4 dB as it seats puts a 4 dB spread in the list and the spread
        would still be 4 dB a minute after it went still, so the step would sit
        there for ever with a good patch in front of it. What the test is about is
        the LAST DETECT_STABLE_BLOCKS blocks, so that is what it reads.

        Three things, and all three are asserted rather than assumed: the signal
        has been present for DETECT_STABLE_BLOCKS instrument blocks without a
        break (`_met_at` is reset by the caller if it breaks), the sliding window
        carries at least DETECT_STABLE_SAMPLES readings -- two, which is what
        makes it a window rather than a point, and the most the coarsest lane on
        the unit can deliver in 256 ms -- and its spread is inside
        DETECT_STEADY_DB.
        """
        span = DETECT_STABLE_BLOCKS * WIN_S
        if now() - self._met_at < span:
            return False, ''
        edge = now() - span
        vals = [v for t, v in self._stable if v is not None and t >= edge]
        if len(vals) < DETECT_STABLE_SAMPLES:
            return False, ''
        spread = max(vals) - min(vals)
        if spread > DETECT_STEADY_DB:
            return False, ''
        return True, '%.2f dB' % spread

    @staticmethod
    def trs(rows):
        """A stereo TRS output patch: L / R / null on one AUX A jack."""
        return (len(rows) > 1 and str(rows[0].get('out') or '').startswith(
            'AUX A') and str(rows[0].get('drive') or '').startswith('aux:'))

    @staticmethod
    def pair_name(pair):
        return 'AUX A %d-%d' % pair

    def _probe_pairs(self, r, lane, prep, floor):
        """Drive each OTHER pair's tip alone and read this lane (S159).
        Returns the (tip, ring) aux pair the jack carries, or None. The
        patch's own route is put back before returning, whatever happened."""
        own = int(str(r['drive']).split(':')[1].split('+')[0])
        need = self.lim['tone_min_over_floor_db']
        best = None
        t0 = now()
        try:
            for k in (1, 3, 5, 7):
                if k == own:
                    continue
                rid = route_id('aux:%d' % k, r['donor'])
                if rid not in self.L.routes:
                    continue
                self.u.write(self.L.routes[rid])
                self._route_up = rid
                lvl = self.watch_tone(
                    lane, prep, settle=max(1, self.u.settle_owed(
                        ROUTE_SETTLE_WINDOWS)))
                if (lvl is not None and floor is not None
                        and lvl - floor >= need
                        and (best is None or lvl > best[0])):
                    best = (lvl, k)
        finally:
            self.u.write(self.L.routes[r['route']])
            self._route_up = r['route']
            self.u.mark_moved()
            self.cost('finding which pair a TRS jack carries', now() - t0)
        return (best[1], best[1] + 1) if best else None

    def _say_wrong(self, r, where):
        """Name the input the tone is actually on, and grade nothing.

        PW 2026-09-28, verbatim shape: "signal on MIC 7, expected MIC 5". It is
        a red screen with one action on it and the same patch stays up.
        """
        self._wrong = where
        self.live.set(state=LV.CHECKLEAD, banner='CHECK THE LEAD',
                      banner_line='',
                      status=LV.status_wrong_input(where, r['in']),
                      action=LV.action_wrong_socket(where, r['in'],
                                                    confirm=not self.auto))

    def _hint_now(self, lane, donor):
        """A steady lane elsewhere RIGHT NOW: two sweeps a stability window
        apart (S157). Used where a claim is needed on the spot -- a NO SIGNAL
        press, the timeout -- rather than on the 1 s sweep's own clock."""
        a = self.u.meter_sweep(MIC_STRIPS)
        nap(DETECT_STABLE_BLOCKS * WIN_S)
        return self.steady_elsewhere(lane, donor,
                                     self.u.meter_sweep(MIC_STRIPS), a)

    def _look_elsewhere(self, r, lane, status, raised):
        """One sweep of all twenty-four lanes, and what it changes on the screen.

        Nothing is graded and nothing is recorded: the only output is the line
        the operator reads. A sweep that finds nothing steady elsewhere takes
        the red screen down again, so a lead moved to the right socket does not
        leave a stale accusation up.

        A CLAIM NEEDS A STEADY HINT (S157). This sweep is compared with the one
        a second earlier (`steady_elsewhere`): the same lane, over its own
        peak floor both times, within DETECT_STEADY_DB. A draining latch -- the
        lane the last patch used -- is never named; a lead really in the wrong
        socket is named within two sweeps, while the hand is still there.
        """
        t = now()
        donor = int(r['donor']) if str(r.get('donor') or '').isdigit() else None
        sweep = self.u.meter_sweep(MIC_STRIPS)
        where = self.steady_elsewhere(lane, donor, sweep, self._sweep_prev)
        self._sweep_prev = sweep
        self.cost('looking for a misplaced lead', now() - t)
        if where:
            if where != self._wrong:
                self.log('%s WRONG_SOCKET: the tone is on %s, not %s (steady '
                         'on two sweeps %.1f s apart)'
                         % (r['patch'], where, r['in'], WRONG_INPUT_POLL_S))
                self._say_wrong(r, where)
        elif self._wrong:
            self.log('%s WAITING: %s is quiet again' % (r['patch'], self._wrong))
            self._wrong = None
            if raised:
                self._raise_no_signal(r, lane, now() - self._t0_step,
                                      quiet=True)
            else:
                self.waiting(status=status or LV.status_words(LV.WAITING),
                             banner='', banner_line='', action='')

    def _raise_no_signal(self, r, lane, waited, quiet=False):
        """The FAILED screen the timeout puts up, and the one an ENTER press
        gets (S157: the step STOPS here and waits for the operator).

        It decides nothing: the loop goes back to watching the lane, so a lead
        pushed home after it is up still arrives on its own. The buttons are
        `buttons_for(CHECKLEAD)`: LEADS CORRECT records the fail and moves on,
        RETRY runs the step again from the prompt, PAUSE pauses.
        """
        if not quiet:
            donor = (int(r['donor']) if str(r.get('donor') or '').isdigit()
                     else None)
            where = self._wrong or self._hint_now(lane, donor)
            if where:
                self._say_wrong(r, where)
                return
            self.log('%s: nothing has reached %s in %.1f s -- asking'
                     % (r['patch'], r['in'], waited))
        self.live.set(state=LV.CHECKLEAD, banner='CHECK THE LEAD',
                      banner_line='',
                      status=LV.timeout_words(r['in'],
                                              self.lim['detect_timeout_s']),
                      action=LV.action_no_signal(confirm=not self.auto))

    def gain_step(self, r):
        """One of PW's seven gain steps: chain, drive, settle, level.

        LEVEL ONLY, AND OFF THE MEASUREMENT NODE. It used to be off the strip
        meter, one peek 50 ms after the two writes, and S125 measured what
        that reads. The meter LATCHES peaks and decays at 6.52 dB/s (measured;
        S121 estimated 6), and 50 ms of that is 0.35 dB, so:

          * the transient between the two writes -- the old drive at the NEW
            gain -- is the loudest thing in the window and the meter holds it.
            Driven with a 12.845 dB step, the settled level is -18.00 dBFS and
            the meter read -5.51: 12.49 dB of a 12.845 dB transient still
            standing at the peek.
          * a step whose element is DEAD reads the level that is no longer
            there. Measured: live -18.00 dBFS, then the stimulus removed
            entirely, and 50 ms later the meter still read -18.39 while the
            node read -23.8 and falling. 0.39 dB is not a test; the tolerance
            is 3 dB.
          * and with no lead in at all, the seven steps read -62, -64, -66,
            -69, -71, -73, -75, -77 dBFS -- a clean 2.2 dB per step, which is
            6.52 dB/s times the 0.34 s a step takes. That is the meter's own
            tail draining, and it looks exactly like a gain law.

        So the step now reads the node, at the shortest window that is
        honest (GAIN_SETTLE_WINDOWS / GAIN_READ_WINDOWS, 167 ms measured,
        95 dB of live-against-dead separation). The meter peek is KEPT and
        recorded beside it as `meter_db`, informational: it is what the
        auto-advance detector watches, and a reader chasing a bad step should
        be able to see the two instruments disagree.

        The code-0 step is still read in full -- it is also the patch's tone
        reference, so it owes a polarity and a distortion reading as well.
        """
        code = int(r['gain_code'])
        spec = self.L.gain.get(code) or {}
        drive = (float(r['level_dbfs']) if r['level_dbfs'] not in ('', None)
                 else spec.get('drive_dbfs'))
        t0 = now()
        self.an.image = None
        self.an.chain(self.an.step_image(r['send_pos'], code),
                      'gain step, %s at code %d' % (r['in'], code))
        if self.an.wrote:
            # A preamp gain change is a change on the wire like any other, and
            # the node cannot tell where it came from.
            self.u.mark_moved()
        t_drive = None
        if drive is not None:
            self.u.osc(level_dbfs=drive)
            t_drive = now()
        lvl = self.watch(int(r['lane']))
        m = dict(gain_code=code, drive_dbfs=drive, meter_db=lvl,
                 expected_db=spec.get('expected_db'), source=spec.get('source'))
        if code == 0:
            # STEP 0 IS ALSO THE PATCH'S TONE REFERENCE, so it is read
            # properly as well: level, polarity and distortion off the
            # measurement node. The other six steps ask one question and get
            # it from the meter in a single peek.
            #
            # AND IT NEEDS THE FULL SETTLE ONLY IF SOMETHING MOVED. The fit
            # behind ThdResult subtracts the previous window, so a window in
            # which anything changed reads as distortion -- but by the time
            # this runs, the route, the instrument and the chain have been
            # where they are for as long as the operator took to plug a lead
            # in, which is seconds. The settle is paid when the chain write
            # for this step actually moved the wire, and not otherwise.
            # The same clock (S125). `an.wrote` says the chain moved; the
            # unit's own `moved_at` says when any cell last did. Whichever is
            # later is what the settle is owed from.
            if self.an.wrote:
                self.u.mark_moved()
            settle = self.u.settle_owed(SETTLE_WINDOWS)
            m.update(self.u.measure(float(r['freq_hz']) if r['freq_hz'] else None,
                                    drive if drive is not None else 0.0,
                                    settle=settle))
            owed = settle
        else:
            # The honest reading, and the one the verdict is on. `freq` is
            # passed so the coherent pair comes back too -- it costs nothing
            # extra, the windows are already being taken -- but the level the
            # scorer uses is the node's RMS, which is the quantity the
            # live-against-dead separation above was measured on.
            #
            # PW's RULING (a), S129: THE SETTLE IS COUNTED FROM THE DRIVE
            # CHANGE, AS THE CODE-0 REFERENCE COUNTS ITS OWN. Until S129 this
            # branch paid a FIXED GAIN_SETTLE_WINDOWS from the `measure` CALL,
            # and the readings that failed failed HIGH and by more the bigger
            # the element: MIC 9 element 1 +3.4 dB, MIC 10 element 3 +4.3 dB,
            # MIC 9 element 6 +6.9 dB, all at lane levels around -24 dBFS and
            # all against a clean code-0 reference taken seconds earlier
            # through the same lead. That shape is a transient still inside the
            # read window, not a wrong element: the same steps on the same
            # sockets passed in an earlier pass of the same afternoon.
            #
            # WHAT WAS MEASURED, AND WHAT IT RULES OUT (s129/settle-probe):
            # the measurement node itself is exactly linear from -96 to -6
            # dBFS (RMS = commanded - 3.01 dB, the sine's own RMS factor, and
            # |H| 0.00 dB at every one of 31 levels), and it follows a 48 dB
            # DRIVE step within one or two windows. So neither the instrument
            # nor the oscillator is slow. What is left in the loop is the
            # preamp and its coupling: a gain change steps the preamp's
            # operating point and the settling of that step is inside an 85 ms
            # RMS window, which reads HIGH and reads higher the bigger the
            # step. The code-0 reference never sees it, because it pays its
            # settle from the change.
            #
            # THE BUDGET IS THE REFERENCE'S OWN, and deliberately so. Counting
            # GAIN_SETTLE_WINDOWS from the change instead of from the call
            # would pay LESS than the code did before, not more -- `watch()`
            # is one SPI peek, so the change is only milliseconds old by the
            # time `measure` is entered -- and it could not fix a reading that
            # is short of its settle. "As the code-0 reference does" is
            # therefore read as the reference's own constant, SETTLE_WINDOWS.
            # Cost: at worst two extra windows on six steps of thirteen
            # sockets, about 13 s on a whole pass.
            if self.an.wrote:
                self.u.mark_moved()
            owed = self.u.settle_owed(SETTLE_WINDOWS)
            m.update(self.u.measure(float(r['freq_hz']) if r['freq_hz'] else None,
                                    drive if drive is not None else 0.0,
                                    windows=GAIN_READ_WINDOWS,
                                    settle=owed))
        # HOW LONG THE WIRE HAD BEEN STILL WHEN THIS WAS READ (S128, kept).
        # `settle_windows` is now what was actually PAID -- the windows still
        # owed from the drive change at the moment `measure` was entered -- so
        # a step that read short of its settle says so in its own log line
        # rather than being inferred from a constant.
        m['settle_windows'] = owed
        m['settle_full'] = SETTLE_WINDOWS
        m['since_drive_s'] = now() - t_drive if t_drive else None
        self.cost('gain steps', now() - t0)
        return m

    # -- 1.2(b) the click-and-shunt trials ----------------------------------
    def transient(self, lane, action, pre_s=CLICK_PRE_S, post_s=CLICK_POST_S):
        """One lane, polled as fast as the link goes, with `action` fired once
        in the middle. Returns the raw series and where the action landed.

        THE INSTRUMENT IS THE STRIP METER, AND THE TABLE SAYS SO. `watch()` on
        a MIC lane is one SPI peek of `_mtr_peak_C1_MTR_nn`, which LATCHES the
        block's peak and then decays at a measured 6.52 dB/s (S125; S121
        estimated 6). For a transient that is the right way round -- a latch
        cannot miss the peak between two polls, it can only report it late --
        and it is why `METER_DECAY_DB_S` has to be taken back out of the
        DURATION, which is what `click_metrics` does.
        Everything this cannot say is in `CLICK_TABLE_NOTE`.

        The measurement node is NOT used here: `Test001RmsResult001` is an RMS
        over a 4,096-sample window (85.3 ms), which is coarser than the whole
        event, and a 16-word node peek spans about fifteen audio blocks and
        scrambles them (S-series finding: a peek is not a block).
        """
        series = []
        t0 = now()
        while now() - t0 < pre_s:
            series.append((now() - t0, self.watch(lane)))
        t_act = now() - t0
        action()
        while now() - t0 < pre_s + post_s:
            series.append((now() - t0, self.watch(lane)))
        return dict(t_act_s=t_act, series=series, pre_s=pre_s, post_s=post_s)

    def click_metrics(self, cap):
        """The fixed table row for one trial. INFORMATIONAL, always.

        THE COLUMNS ARE FIXED HERE (gaps doc 1.2(b): "peak / energy / duration
        table ... for PW to review and SIGN the limits"). PW signs against
        `peak_dbfs` and `residual_ms`; the rest is the instrument declaring
        itself so that a signature is against a known one:

          floor_dbfs    the lane with the 150 ohm plug in and nothing moving:
                        the median of the samples taken BEFORE the toggle.
          peak_dbfs     the highest sample after it. The meter latches, so
                        this cannot be missed between polls -- only reported
                        late, by at most poll_ms_max of decay.
          t_peak_ms     when that sample was taken, from the toggle.
          above_floor_ms  from the toggle to the last sample still more than
                        CLICK_ABOVE_FLOOR_DB over the floor.
          decay_only_ms  how much of `above_floor_ms` the METER's own 6.52 dB/s
                        decay accounts for on its own, from that peak. This is
                        not a correction factor: it is the instrument's tail,
                        and it is subtracted rather than left in the number PW
                        is being asked to sign.
          residual_ms   above_floor_ms - decay_only_ms, floored at 0. The
                        transient's OWN duration, as far as this instrument
                        can see it -- and None when `truncated`.
          truncated     the capture ENDED with the lane still above the
                        threshold, so `above_floor_ms` is a lower bound and
                        `residual_ms` cannot be worked out at all. It matters
                        because the meter's drain from a LOUD peak is long: at
                        6.52 dB/s a peak of -60 dBFS takes 4.6 s to reach 6 dB
                        over a -96 dBFS floor, which is longer than
                        CLICK_POST_S. `click_trials_check.py` is what put this
                        column here -- before it, a loud click reported a
                        residual of 0.0 ms, which reads as "no ringing at all"
                        and is the exact opposite of what it means.
          energy_db_s   10*log10(sum(p*dt)) over the samples above the floor.
                        An UPPER BOUND: the latch holds a peak across polls,
                        so the envelope integrated here is at or above the
                        true one.
          polls, poll_ms_mean, poll_ms_max   what the cadence actually was.
        """
        ser = [(t, v) for t, v in cap['series']
               if v is not None and math.isfinite(v)]
        pre = sorted(v for t, v in ser if t < cap['t_act_s'])
        post = [(t, v) for t, v in ser if t >= cap['t_act_s']]
        gaps = [b[0] - a[0] for a, b in zip(ser, ser[1:])]
        out = dict(floor_dbfs=(pre[len(pre) // 2] if pre else None),
                   peak_dbfs=None, t_peak_ms=None, above_floor_ms=None,
                   decay_only_ms=None, residual_ms=None, energy_db_s=None,
                   truncated=False, polls=len(ser),
                   poll_ms_mean=(1000.0 * sum(gaps) / len(gaps)
                                 if gaps else None),
                   poll_ms_max=(1000.0 * max(gaps) if gaps else None))
        if out['floor_dbfs'] is None or not post:
            return out
        t_pk, pk = max(post, key=lambda tv: tv[1])
        thr = out['floor_dbfs'] + CLICK_ABOVE_FLOOR_DB
        out['peak_dbfs'] = pk
        out['t_peak_ms'] = 1000.0 * (t_pk - cap['t_act_s'])
        above = [t for t, v in post if v > thr]
        if above:
            out['above_floor_ms'] = 1000.0 * (above[-1] - cap['t_act_s'])
            out['decay_only_ms'] = max(0.0, 1000.0 * (pk - thr)
                                       / METER_DECAY_DB_S)
            # THE CAPTURE RAN OUT BEFORE THE TAIL DID. Then `above_floor_ms` is
            # a lower bound and the subtraction is meaningless, so no residual
            # is reported rather than a 0 that would read as "no ringing".
            out['truncated'] = post[-1][1] > thr
            out['residual_ms'] = (None if out['truncated'] else
                                  max(0.0, out['above_floor_ms']
                                      - out['decay_only_ms']))
            e, last = 0.0, None
            for t, v in post:
                if last is not None and v > thr:
                    e += 10 ** (v / 10.0) * (t - last)
                last = t
            out['energy_db_s'] = dbv(e) if e > 0 else None
        else:
            out['above_floor_ms'] = 0.0
            out['decay_only_ms'] = 0.0
            out['residual_ms'] = 0.0
        return out

    def click_trials(self, r, prep):
        """1.2(b): the click/shunt trial set on ONE input, inside the EIN step.

        WHERE AND WHY HERE. The ruling puts it "inside the EIN step (150 ohm
        plug already in)": the terminator is the source impedance the residual
        has to be measured against, the operator's hand is already on that
        socket, and the EIN reading that has just been taken IS the floor the
        peak is quoted over. A separate visit would need the plug fitted twice.

        FOUR TRIALS PER INPUT: phantom off->on and on->off, each with the
        shunt ENGAGED and with it RELEASED. The two shunt arms are the same
        shape -- one image moves the phantom bit, with the shunt already where
        it is going to be -- so the only difference between them is the thing
        being measured.

        THE RELEASED ARM DELIBERATELY BREAKS THE SHUNT-FIRST RULE, and that is
        what it is for. PW 2026-09-16 says phantom is never switched without
        the shunt; PW 2026-09-28 asks for "shunt on/off, both directions" so
        that the rule's worth can be measured. It is therefore the one place in
        this tree that moves phantom without the sequence, it is behind
        `--click-trials` which is off by default, it only ever runs with the
        150 ohm terminator fitted (never a microphone), and it says so in the
        log every time.

        IT NEVER GRADES. No verdict, no window, no PASS and no FAIL -- the
        rows come back as a table and the row stays INFORMATIONAL until PW
        signs the limits (the ruling's own words).
        """
        lane = int(r['lane'])
        sp = str(r.get('send_pos') or '').strip()
        if sp == '':
            return dict(input=r['in'], lane=lane, trials=[],
                        skipped='no transmit position for this input in the '
                                'patch list')
        sp = int(sp)
        base = list(self.an.image if self.an.image is not None
                    else self.an.safe_image)
        self.log('click/shunt trials on %s: phantom is moved WITHOUT the '
                 'shunt-first sequence in two of the four trials, which is '
                 'what the trial measures. The 150 ohm terminator is fitted '
                 'and no microphone is connected.' % r['in'])
        trials = []
        t0 = now()
        try:
            for shunt_on in (True, False):
                for on in (True, False):
                    img0 = CH.with_phantom(
                        CH.with_shunt(base, [sp], shunt_on), [sp], not on)
                    if not self.an.chain(img0, 'click trial start state: shunt '
                                         '%s, phantom %s'
                                         % ('engaged' if shunt_on else
                                            'released',
                                            'off' if on else 'on')):
                        trials.append(dict(shunt=shunt_on, to_on=on,
                                           skipped='the start image did not '
                                                   'read back'))
                        continue
                    nap(CH.SHUNT_SETTLE_S)
                    img1 = CH.with_phantom(img0, [sp], on)
                    cap = self.transient(
                        lane, lambda i=img1: self.an.chain(
                            i, 'click trial: phantom %s' % ('on' if on
                                                            else 'off')))
                    m = self.click_metrics(cap)
                    m.update(shunt=shunt_on, to_on=on, skipped='')
                    trials.append(m)
        finally:
            # BACK THROUGH THE SEQUENCE, always. However the trials ended, the
            # input is left with phantom off and its shunt where the block
            # wants it, and the way back is PW's own sequence -- the trials'
            # exception applies to the measurement, not to the handback.
            self.an.phantom([sp], False, what='%s after the click trials'
                            % r['in'])
            self.an.chain(base, 'back to the block image after the click '
                          'trials')
        self.cost('click/shunt trials', now() - t0)
        return dict(input=r['in'], lane=lane, trials=trials, skipped='')

    # -- 1.2(a) the phantom lamp sweep --------------------------------------
    def mic_inputs(self):
        """The mic inputs the sweep walks, in the list's own order.

        Taken from the rows that carry a `send_pos`, because `send_pos` is the
        only thing that can address a preamp's own 595 byte (S125: the strip
        number, the chain index and the transmit position are three different
        orders and defs carries two of them in adjacent columns). An input
        with no transmit position in the list is not walked and says so, which
        is the no-fallback rule: writing a guessed byte moves some other
        input's phantom.
        """
        # WHICH ROWS ARE A MIC PREAMP AT ALL. `lane` in MIC_STRIPS and a name
        # that is not the jack half of the same combo socket: that is the 24
        # XLR mic inputs and nothing else. TALKBACK and the mini-jacks come in
        # on codec return lanes and have no preamp byte to write, so they are
        # not "skipped" -- they are not in this sweep's scope.
        #
        # AND THE TRANSMIT POSITION IS LOOKED FOR ACROSS EVERY ROW OF AN INPUT,
        # not just its first. MIC 1's first row in the generated list is P1 of
        # the OUTPUT walk, which carries no `send_pos` at all; taking the first
        # row would have dropped MIC 1 and MIC 2 out of the sweep and called
        # them unaddressable.
        pos, lanes, order = {}, {}, []
        for r in self.L.paths:
            name = (r.get('in') or '').strip()
            if (not name or name.endswith(' line')
                    or not str(r.get('lane') or '').isdigit()
                    or int(r['lane']) not in MIC_STRIPS):
                continue
            if name not in lanes:
                order.append(name)
                lanes[name] = int(r['lane'])
            sp = str(r.get('send_pos') or '').strip()
            if sp != '' and name not in pos:
                pos[name] = int(sp)
        out, skipped = [], []
        for name in order:
            if name in pos:
                out.append(dict(name=name, lane=lanes[name],
                                send_pos=pos[name]))
            else:
                skipped.append(name)
        if skipped:
            self.log('the lamp sweep skips %d input(s) with no transmit '
                     'position in the list: %s'
                     % (len(skipped), ', '.join(skipped)))
        return out, skipped

    def lamp_ask(self, instruction, n, total, title, fault='notlit',
                 secs=None):
        """One operator screen with ENTER and at most one fault button.

        Returns 'enter', 'notlit', 'pause' or 'skip'. Both channels are polled
        in the same breath -- the armed factory screen's own NOT LIT (S137) and
        the dialog's -- so whichever the bench has is live. `fault=None` is a
        plain ENTER screen, which is what the mini-jack removal step wants:
        there is no judgement to make there, only an action to finish.
        """
        self.live.set(state=LV.WAITING, instruction=instruction, lead_line='',
                      extra='', banner='', banner_line='', action='',
                      n=n, total=total, lead_n=0, lead_total=0,
                      buttons=(LV.LAMP_BUTTONS if fault
                               else LV.buttons_for(LV.WAITING, True)))
        btns = self.g.post('instruct', title, [instruction],
                           [fault] if fault else ['enter'])
        deadline = now() + (secs if secs is not None
                            else self.lim['detect_timeout_s'] * ENTER_PATIENCE)
        while now() < deadline:
            self.live.beat()
            cmd = self.live.command()
            if cmd in ('pause', 'notlit'):
                return cmd
            if cmd == 'enter' or self.keys.pressed():
                return 'enter'
            ans = self.g.poll(btns)
            if ans is not None:
                b = ans.get('button')
                if b in ('done', 'ack', 'enter', 'retry'):
                    return 'enter'
                if b == 'notlit':
                    return 'notlit'
                if b in STOP_BUTTONS:
                    return 'pause'
                return 'skip'
            nap(0.05)
        return 'skip'

    def lamp_sweep(self):
        """1.2(a): PW's two-LED lamp fixture, moved input to input.

        A SEPARATE SWEEP, and separate for a reason the ruling gives: it is the
        only step in the station that applies phantom, so it is not folded into
        a block that is measuring something else. It measures NOTHING -- there
        is no lane reading here at all, only the operator's eye on two LEDs --
        so it needs no oscillator, no MeasChan and no settle.

        EVERY PHANTOM TRANSITION GOES THROUGH THE SHUNT-FIRST SEQUENCE
        (`Analog.phantom`, PW 2026-09-16, S138-3): shunt on, t1, phantom
        toggled, t2, shunt restored, three verified loads. Nothing here writes
        a phantom bit in one image.

        AND IT LEAVES PHANTOM OFF ON EVERY INPUT IT TOUCHED, on every way out
        -- the answer, a PAUSE, a timeout or an exception -- because the
        fixture is a pair of LEDs across a 48 V feed and the next thing to go
        into that socket is a microphone. `Analog.down()`'s safe image is the
        backstop; this is the step's own.
        """
        inputs, skipped = self.mic_inputs()
        total = len(inputs)
        rows, touched = [], []
        self.live.set(state=LV.WAITING, instruction=LV.lamp_sweep_words(),
                      lead_line='', extra='', n=0, total=total,
                      buttons=LV.LAMP_BUTTONS)
        self.g.progress('the phantom lamp sweep: %d inputs, two questions each'
                        % total)

        def land(inp, verdict, why, detail=''):
            rows.append(dict(path='', patch='LAMP', lead='LAMP', out='',
                             **{'in': inp['name']}, sub='phantom lamp',
                             rows='', verdict=verdict, why=why, detail=detail,
                             h_db=None, h_deg=None, thd_db=None,
                             noise_db=None, rms_db=None))

        try:
            for i, inp in enumerate(inputs, 1):
                # 1. THE FIXTURE MOVES, WITH PHANTOM OFF EVERYWHERE. A lamp
                # lit here is phantom present with phantom off, and it is the
                # same NOT LIT button in the same place.
                ans = self.lamp_ask(LV.lamp_move_words(inp['name'], first=i == 1),
                                    i, total, 'Phantom lamp check - %s'
                                    % inp['name'])
                if ans == 'pause':
                    self.paused = True
                    return rows
                if ans == 'skip':
                    land(inp, SKIPPED, 'the operator moved past this input')
                    continue
                if ans == 'notlit':
                    land(inp, FAIL, LV.LAMP_STUCK_ON,
                         'a lamp was lit with phantom off on every input')
                    continue
                # 2. PHANTOM ON, through the sequence.
                touched.append(inp['send_pos'])
                ok, steps = self.an.phantom([inp['send_pos']], True,
                                            what=inp['name'])
                if not ok:
                    land(inp, NODATA, 'the phantom shunt sequence did not '
                         'verify, so phantom was not applied',
                         'stopped at step %d; the shunt is left engaged'
                         % steps[-1]['step'])
                    self.an.phantom([inp['send_pos']], False, what=inp['name'])
                    continue
                # 3. THE RULING'S QUESTION.
                ans = self.lamp_ask(LV.lamp_check_words(inp['name']), i, total,
                                    'Phantom lamp check - %s' % inp['name'])
                # 4. PHANTOM OFF, through the sequence, whatever the answer
                # was -- including a PAUSE.
                off_ok, _ = self.an.phantom([inp['send_pos']], False,
                                            what=inp['name'])
                if not off_ok:
                    land(inp, NODATA, 'phantom would not switch back off; the '
                         'shunt is left engaged on this input', '')
                    self.paused = True
                    return rows
                if ans == 'pause':
                    self.paused = True
                    return rows
                if ans == 'skip':
                    land(inp, SKIPPED, 'the operator moved past this input')
                elif ans == 'notlit':
                    land(inp, FAIL, LV.LAMP_LEG_FAULT,
                         'the operator saw one or both lights dark with '
                         'phantom on')
                else:
                    land(inp, PASS, 'both lights on with phantom on, both dark '
                         'with it off')
        finally:
            # PHANTOM OFF ON EVERYTHING THIS SWEEP TOUCHED, on every way out.
            # One sequence over the whole set, not one per input: the ruling's
            # step 1 is "shunt ON on every channel whose phantom is about to
            # change", which is what a set is for.
            if touched:
                self.an.phantom(sorted(set(touched)), False,
                                what='every input the lamp sweep touched')
            self.g.clear()
        for name in skipped:
            rows.append(dict(path='', patch='LAMP', lead='LAMP', out='',
                             **{'in': name}, sub='phantom lamp', rows='',
                             verdict=NODATA,
                             why='no transmit position for this input in the '
                                 'patch list, so its own preamp byte cannot '
                                 'be addressed',
                             detail='', h_db=None, h_deg=None, thd_db=None,
                             noise_db=None, rms_db=None))
        return rows

    def cost(self, what, secs):
        self.costs[what] = self.costs.get(what, 0.0) + secs

    def acquire(self, rows, prep):
        """Every sub-test of one patch, with the lead left where it is."""
        out = []
        for i, r in enumerate(rows):
            if str(r.get('gain_code') or '') != '' and r['expect'] != 'noise':
                if i:
                    # the route and the instrument do not move between the
                    # seven steps -- only the chain and the drive do
                    pass
                out.append(dict(row=r, meas=self.gain_step(r), sweep={}))
                continue
            # THE ROW'S OWN DRIVE, ASSERTED (S159). Row 1 used to assume the
            # route `_prepare` wrote was still up; anything that moved it in
            # between -- a pre-arm that walked to the null, the TRS pair probe
            # -- left row 1 reading whatever was last driven. A patch whose
            # rows drive different buses re-writes row 1's route every time
            # (a cell already holding its value is not a move, so no settle
            # is owed for it); a single-drive patch does it when it is known
            # to have moved.
            multi = len({x['route'] for x in rows}) > 1
            if i or multi or self._route_up != r['route'] \
                    or self._lane_up != int(r['lane']):
                self.u.write(self.L.routes[r['route']])
                self._route_up = r['route']
                freq = float(r['freq_hz']) if r['freq_hz'] else None
                lvl = float(r['level_dbfs']) if r['level_dbfs'] else None
                if r['expect'] != 'noise':
                    self.u.osc(chan=int(r['donor']), freq=freq,
                               level_dbfs=lvl, on=True)
                if int(r['lane']) != self._lane_up:
                    self.u.meas_chan(int(r['lane']))
                    self._lane_up = int(r['lane'])
            freq = float(r['freq_hz']) if r['freq_hz'] else None
            lvl = float(r['level_dbfs']) if r['level_dbfs'] else 0.0
            tm = now()
            # A NOISE ROW HAS NO FIT TO SETTLE. ROUTE_SETTLE_WINDOWS exists
            # because the coherent fit reads a changed window as distortion;
            # an RMS of a terminated input is an RMS, and six windows of it
            # is five windows of a factory worker waiting.
            # SETTLE FROM THE EVENT (S125, review §2.4). A noise row has no
            # fit to settle; a tone row owes the route window only while the
            # route change is still inside the node's integration, and by the
            # first row of a patch the route has been up since before the
            # prompt -- seconds, which is tens of windows. What is still owed
            # is what is paid.
            settle = (READ_WINDOWS if r['expect'] == 'noise'
                      else self.u.settle_owed(ROUTE_SETTLE_WINDOWS))
            ein = (r['expect'] == 'noise' and self.lim.ein_ready()
                   and int(r['lane']) in MIC_STRIPS
                   and hasattr(self.u, 'ein_capture'))
            if ein:
                settled_s = self.ein_settle(int(r['lane']))
                settle = 1
            m = self.u.measure(freq, lvl, settle=settle)
            if ein:
                m.update(self.ein_reading(r, settled_s))
            self.cost('settled readings', now() - tm)
            sweep = (self.u.meter_sweep(MIC_STRIPS)
                     if int(r['lane']) in MIC_STRIPS and r['expect'] == 'tone'
                     else {})
            out.append(dict(row=r, meas=m, sweep=sweep))
            # 1.2(b), INSIDE THE EIN STEP AND AFTER THE READING (PW
            # 2026-09-28). After, not before: the trials move phantom, and a
            # noise figure taken with a phantom transient still in the window
            # is not a noise figure. "The good channels" is the ruling's own
            # scope -- a channel whose EIN reading did not come back has
            # nothing for a click to be quoted over -- and `--trial-inputs`
            # names them by hand.
            if (self.trials and r['expect'] == 'noise'
                    and int(r['lane']) in MIC_STRIPS
                    and (self.trial_only is None
                         or r['in'] in self.trial_only)):
                good = m.get('rms')
                if good is None or not math.isfinite(good):
                    self.click_results.append(
                        dict(input=r['in'], lane=int(r['lane']), trials=[],
                             skipped='the EIN reading did not come back, so '
                                     'this is not one of the good channels'))
                else:
                    self.click_results.append(self.click_trials(r, prep))
        return out

    def ein_settle(self, lane):
        """Wait for the terminated input to stop moving (S159). The plug's own
        insertion transient takes seconds to leave a gain-63 input -- every
        S158 trace still falls at the moment the step arrived -- so the node
        is polled one window at a time until two successive windows agree,
        never sooner than EIN_SETTLE_MIN_S and never longer than
        EIN_SETTLE_MAX_S. Returns the seconds spent."""
        t0 = now()
        prev = None
        while True:
            v = self.watch(lane, rms=True, settle=1)
            el = now() - t0
            if (v is not None and prev is not None
                    and abs(v - prev) <= EIN_SETTLE_AGREE_DB
                    and el >= EIN_SETTLE_MIN_S) or el >= EIN_SETTLE_MAX_S:
                return el
            prev = v

    def ein_reading(self, r, settled_s):
        """The capture-arm figures the EIN is graded on, and what the scorer
        needs to input-refer them (the code's gain step, the unit's DAC full
        scale). The lane's code-0 loop gain is the scorer's own reference."""
        e = self.u.ein_capture()
        step = self.L.gain.get(int(r.get('gain_code') or 63))
        return dict(ein_band_dbfs=e['u'], ein_a_dbfs=e['a'],
                    ein_total_dbfs=e['total'], ein_caps=e['caps'],
                    ein_n=e['n'], ein_overruns=e['overruns'],
                    ein_settle_s=settled_s,
                    gain_step_db=(step or {}).get('expected_db'),
                    gain_code=int(r.get('gain_code') or 63),
                    dac_fs_dbu=self.lim['dac_fs_dbu'])

    def score_patch(self, rows, prep, raw):
        sibs, scored = [], []
        for item in raw:
            r, m = item['row'], item['meas']
            # per LANE, not per patch: a mini-jack patch reads two lanes and
            # they have floors of their own
            floor = self.floors.get(int(r['lane']))
            v, why, notes = self.sc.score(r, m, floor, item['sweep'], sibs,
                                          donor=int(r['donor']),
                                          sweep0=prep.get('sweep0'))
            sibs.append(dict(level_ref=r['level_ref'], h_db=m.get('h_db'),
                             h_deg=m.get('h_deg'),
                             gain_code=m.get('gain_code'),
                             rms=m.get('rms'),
                             meter_db=m.get('meter_db'),
                             drive_dbfs=m.get('drive_dbfs')))
            scored.append(dict(path=r['path'], patch=r['patch'], lead=r['lead'],
                               out=r['out'], **{'in': r['in']}, sub=r['sub'],
                               rows=r['rows'], verdict=v, why=why,
                               detail='; '.join(notes),
                               h_db=m.get('h_db'), h_deg=m.get('h_deg'),
                               thd_db=m.get('thd'), noise_db=m.get('noise'),
                               rms_db=m.get('rms')))
        return scored

    def _drive_of(self, pid):
        for r in self.L.paths:
            if r['patch'] == pid:
                return r['drive']
        return ''

    # -- the pass ----------------------------------------------------------
    def run(self):
        """The pass, with row 93 scored on the way out whatever happened.

        `mj_close` appends to `self.rows_out`, which is the very list `_run`
        returns, so the detect row is in the return value of a standalone run
        AND in what `patch_station` folds onto the catalog.
        """
        ok = False
        try:
            out = self._run()
            ok = not self.paused
            return out
        finally:
            self.mj_close(ask=ok)

    def _run(self):
        self.standing()
        seq = []
        for (lead, block), patches in self.L.blocks():
            if self.only and lead not in self.only:
                # --block names a LEAD (S158). The input walk alternates K1
                # and K5 inside one block keyed K1, so `--block K5` matched
                # nothing; it now keeps that block's own K5 patches.
                patches = [(pid, rr) for pid, rr in patches
                           if rr[0]['lead'] in self.only]
                if not patches:
                    continue
            seq.append(((lead, block), patches))
        if self.owed_rows is not None:
            total = sum(len(p) for _k, p in seq)
            seq = [(k, [(pid, rr) for pid, rr in p if self.owed_patch(pid, rr)])
                   for k, p in seq]
            seq = [(k, p) for k, p in seq if p]
            self.rerun = (sum(len(p) for _k, p in seq), total)
            self.log('the re-run walks %d of %d patches: %s'
                     % (self.rerun[0], total, ' '.join(
                         pid for _k, p in seq for pid, _r in p)))
        self.index(seq)
        if self.rerun is not None:
            words = LV.rerun_words(*self.rerun)
            self.live.set(status=words)
            self._lead_line = words
        prepared = None
        for bi, ((lead, block), patches) in enumerate(seq):
            self.lead_card(lead, block, patches, bi + 1, len(seq))
            self.an.for_block(lead)
            for pi, (pid, rows) in enumerate(patches):
                rows = self.rebind(rows)
                arrived = None
                self._patience = 2.0 if (bi == 0 and pi == 0) else 1.0
                # STEP 1: FIND A WORKING LOOP. Every candidate is an ordinary
                # prompt and every failed one waits for the operator (S157).
                if (rows[0].get('park') or '') == 'find':
                    found = self.find_loop(pid, rows)
                    if found == 'stopped':
                        return self.rows_out
                    if found is None:
                        self.no_loop()
                        return self.rows_out
                    frow, fprep = found
                    rows, arrived = [frow], fprep
                    prepared = None
                got = self.one_patch(pid, rows, lead, block, seq, bi, pi,
                                     prepared, arrived)
                if got == 'stopped':
                    return self.rows_out
                prepared = got
        self.finish()
        return self.rows_out

    def owed_patch(self, pid, rows):
        """Is this patch walked on a resume? (S159, corrected S163)

        PW 2026-10-01: "don't repeat failed tests (unless requested), only run
        untested tests". A patch is walked when it feeds a row with NO verdict
        yet (`owed_rows` is the untested set, built by the runner from
        `State.settled`); a patch whose rows all carry a PASS or a FAIL is not.
        With the operator's RE-TEST FAILED request (`carry['retest_failed']`)
        the S159 rule applies again: any row without a PASS, and a 150 ohm
        patch until its input's EIN has been graded and passed. A patch that
        folds onto no row at all (the line inputs) is owed until it has a
        recorded outcome."""
        rec = (self.carry.get('patches') or {}).get(pid) or {}
        retest = bool(self.carry.get('retest_failed'))
        if retest and rows[0]['expect'] == 'noise' and self.lim.ein_ready():
            return rec.get('ein') != PASS
        nums = {int(x) for r in rows for x in str(r.get('rows') or '').split()}
        if nums:
            return bool(nums & self.owed_rows)
        return (rec.get('verdict') != PASS) if retest else not rec

    def patch_outcomes(self):
        """Per patch walked: its worst verdict, and for a 150 ohm patch
        whether the EIN was graded and how. RUN ALL keeps these (S159)."""
        out = {}
        for s in self.rows_out:
            e = out.setdefault(s['patch'], dict(verdict=PASS))
            if RANK_PATCH.get(s['verdict'], 9) > RANK_PATCH.get(e['verdict'], 9):
                e['verdict'] = s['verdict']
            if 'EIN ' in (s.get('detail') or '') or \
                    str(s.get('why') or '').startswith(('EIN ', 'noise too high')):
                e['ein'] = s['verdict']
        return out

    def _prompt(self, pid, rows):
        """PROMPTED: the route up, the dialog posted, the instruction on the
        glass. Returns (prep, token)."""
        prep = self.prepare(rows)
        tok = self.p.connect(pid, rows, self.g)
        self.announce(pid, rows)
        return prep, tok

    def one_patch(self, pid, rows, lead, block, seq, bi, pi, prepared=None,
                  arrived=None):
        """One patch, start to recorded (S157).

        Returns the NEXT patch already prompted -- (pid, prep, token), the
        pipeline -- or None, or 'stopped' on PAUSE.

        THE PASS PATH IS THE ONLY ONE THAT ADVANCES BY ITSELF. Arrival, the
        reading, a PASS verdict, the next prompt. Everything else stops on
        this patch with the failure named and waits: LEADS CORRECT records it,
        RETRY (or re-making the patch by hand) runs it again from the prompt,
        PAUSE pauses. Nothing re-prompts, re-parks or records NO DATA on its
        own any more (PW 2026-09-30).
        """
        if arrived is not None:
            prep, tok = arrived, None
        elif prepared is not None and prepared[0] == pid:
            _p, prep, tok = prepared
        else:
            prep, tok = self._prompt(pid, rows)
        t_hand = 0.0
        while True:
            if arrived is not None:
                how, ans, dt = 'rise', None, 0.0
                arrived = None
            else:
                how, ans, dt = self.detect(rows, prep, tok)
            t_hand += dt
            if how == 'glass' and ans.get('button') in STOP_BUTTONS:
                self.p.done(tok)
                self.finish_early(rows, ans)
                return 'stopped'
            if how == 'glass' and ans.get('button') in PATCH_DECISIONS:
                # ONE PATCH, NOT THE PASS (S127) -- and an operator decision,
                # which is the confirmation the ruling asks for.
                self.p.done(tok)
                self.record(self.decided(rows, ans))
                return None
            if how == 'glass':
                self.log('%s: the screen sent %r, which is not one of this '
                         'step\'s answers -- asking again'
                         % (pid, ans.get('button')))
                self.p.done(tok)
                tok = self.p.connect(pid, rows, self.g)
                continue
            if how == 'nosignal':
                # LEADS CORRECT on the FAILED screen: the operator has looked
                # at the patch and says it is right. That is the confirmation;
                # the row is a FAIL and the walk moves on.
                self.p.done(tok)
                self.confirmed.append(dict(patch=pid, what=rows[0]['in'],
                                           failure=('jack order: %s carries %s' % (rows[0]['out'], self.pair_name(self._pair_seen)) if self.trs(rows) and self._pair_seen else 'no signal arrived'),
                                           answer='LEADS CORRECT'))
                self.record(self.no_signal(rows))
                return None
            if how in ('retry', 'enter-no'):
                # RETRY: the same patch, again from the prompt. No count: the
                # operator decides when to stop trying, not the station.
                self.p.done(tok)
                self._armed = None
                self.log('%s RETRY: running it again from the prompt' % pid)
                prep, tok = self._prompt(pid, rows)
                continue
            # ARRIVED: the reading. The 150 ohm step's ENTER comes off with
            # it; the next prompt puts its own buttons up.
            self.live.wait_buttons = None
            t1 = now()
            self.live.set(state=LV.CHECKING)
            raw, _saved = self.confirm_armed(rows)
            if raw is None:
                raw = self.acquire(rows, prep)
            if rows[0]['expect'] == 'noise':
                for item in raw:
                    item['meas']['open_db'] = self._term.get('ref_db')
                    item['meas']['how'] = (
                        'ended by ENTER' if how == 'press' else
                        'ended on the plug%s' % (
                            ' (insertion at %.1f s)' % self._term['burst_at']
                            if self._term.get('burst_at') is not None
                            else ''))
            t_read = now() - t1
            self.p.done(tok)
            scored = self.score_patch(rows, prep, raw)
            verdicts = {s['verdict'] for s in scored}
            if not verdicts - {PASS, SKIPPED, IGNORED}:
                nxt = self.next_patch(seq, bi, pi)
                ahead = None
                if nxt is not None:
                    nrows = self.rebind(nxt[1])
                    pn, tn = self._prompt(nxt[0], nrows)
                    ahead = (nxt[0], pn, tn)
                self.record(scored, prompted=ahead is not None)
                self.timing.append(dict(patch=pid, lead=lead, block=block,
                                        hand_s=t_hand, machine_s=now() - t1,
                                        read_s=t_read, subs=len(rows)))
                self.report_last(pid)
                return ahead
            # A GRADED FAIL STOPS HERE TOO (S157).
            what = self.confirm_graded(pid, rows, scored)
            if what == 'pause':
                self.finish_early(rows, dict(button='pause'))
                return 'stopped'
            if what == 'retry':
                self._armed = None
                self.log('%s RETRY: running it again from the prompt' % pid)
                prep, tok = self._prompt(pid, rows)
                continue
            worst = next(s for s in scored
                         if s['verdict'] not in (PASS, SKIPPED, IGNORED))
            self.confirmed.append(dict(patch=pid, what=LV.patch_words(
                dict(out=rows[0]['out'], **{'in': rows[0]['in']})),
                failure='%s: %s' % (worst['verdict'], worst['why']),
                answer='LEADS CORRECT'))
            for s in scored:
                if s['verdict'] not in (PASS, SKIPPED, IGNORED):
                    s['detail'] = '; '.join(x for x in (
                        s.get('detail'), 'the operator confirmed the leads '
                        'were right (LEADS CORRECT) and moved on') if x)
            self.record(scored)
            self.timing.append(dict(patch=pid, lead=lead, block=block,
                                    hand_s=t_hand, machine_s=now() - t1,
                                    read_s=t_read, subs=len(rows)))
            self.report_last(pid)
            return None

    def confirm_graded(self, pid, rows, scored):
        """The FAILED screen for a patch that arrived and did not pass.

        Returns 'record', 'retry' or 'pause'. The patch's own route is put
        back first -- nothing has been prepared past it -- so RETRY BY HAND
        works on the deployed glass, which has no RETRY button yet: pulling the
        lead out (the node's coherent level falls under floor + rise for a
        stability window) and plugging it in again runs the patch again. That
        is the second and last removal edge in the station, and it is on the
        node, so a one-second unplug is twelve windows of it.
        """
        r = rows[0]
        worst = next(s for s in scored
                     if s['verdict'] not in (PASS, SKIPPED, IGNORED))
        name = LV.patch_words(dict(out=r['out'], **{'in': r['in']}))
        prep = self.prepare(rows)
        self.log('%s FAILED: %s -- %s; waiting for the operator (LEADS '
                 'CORRECT / RETRY / PAUSE)' % (pid, worst['verdict'],
                                               worst['why']))
        self.live.set(state=LV.CHECKLEAD, banner=LV.fail_banner(
                          worst['verdict']), banner_line=name,
                      instruction=LV.instruction_for(r, confirm=False),
                      lead_line='', extra='',
                      status=LV.graded_fail_words(worst['verdict'],
                                                  worst['why']),
                      action=LV.action_graded_fail(
                          by_hand=r['expect'] != 'noise'),
                      passed=self.passed, failed=self.failed)
        lane, rise = prep['lane'], self.lim['detect_rise_db']
        floor0 = prep.get('floor')
        out_since = None
        span = DETECT_STABLE_BLOCKS * WIN_S
        while True:
            self.live.beat()
            cmd = self.live.command() or self.p.decide('graded')
            if self.keys.pressed():
                cmd = cmd or 'retry'
            if cmd == 'pause':
                return 'pause'
            if cmd == 'nosignal':
                self.log('%s: LEADS CORRECT on the failed patch -- recorded, '
                         'moving on' % pid)
                return 'record'
            if cmd in ('retry', 'enter'):
                return 'retry'
            if r['expect'] == 'noise' or floor0 is None:
                nap(DETECT_POLL_S)
                continue
            lvl = self.watch_tone(lane, prep)
            if lvl is not None and lvl - floor0 < rise:
                out_since = out_since or now()
                if now() - out_since >= span:
                    self._step_log(r, 'RETRY', lvl, floor0,
                                   'the lead came out of the failed patch; '
                                   'running it again from the prompt')
                    return 'retry'
            else:
                out_since = None
            nap(DETECT_POLL_S)

    # -- the reference ends -------------------------------------------------
    def rebind(self, rows):
        """Bind this patch's REFERENCE end to the socket the first step found.

        The list is generated before anybody plugs anything in, so it cannot
        know which input is good; it says WHICH END homes on the reference and
        this binds it. A patch that names both ends itself is returned
        untouched. NOTHING IS PARKED (PW 2026-09-30, "use one at a time"):
        this changes the NAMES in the prompt, never where a lead hangs, and
        every patch is still one lead plugged fresh at both ends.
        """
        park = (rows[0].get('park') or '').strip()
        if park in ('', 'find'):
            return rows
        if park == 'in' and self.ref_in is None:
            return rows
        if park == 'out' and self.ref_out is None:
            return rows
        if park == 'out':
            named = rows[0]['out']
            if named not in (self.kit_socket('K1'), self.ref_out[0]):
                return rows
        out = []
        for r in rows:
            r = dict(r)
            if park == 'in':
                name, strip = self.ref_in
                r['in'], r['lane'] = name, str(strip)
                r['donor'] = str(donor_for(strip))
                r['route'] = route_id(r['drive'], r['donor'])
                r['prompt'] = 'Patch %s to %s' % (r['out'], name)
            else:
                name, drive = self.ref_out
                r['out'], r['drive'] = name, drive
                r['route'] = route_id(drive, r['donor'])
                r['prompt'] = 'Patch %s to %s' % (name, r['in'])
            out.append(r)
        return out

    def kit_socket(self, lead):
        """The home socket the list names for one lead, or None."""
        for d in self.L.kit:
            if d['lead'] == lead:
                return d['socket'] or None
        return None

    def loop_candidates(self):
        """The outputs to try, and the inputs to walk, both in panel order and
        both taken from the list rather than invented here."""
        outs, ins = [], []
        for (_lead, block), patches in self.L.blocks():
            if block == 'the outputs' and not outs:
                outs = [(rr[0]['out'], rr[0]['drive']) for _p, rr in patches]
            elif block == 'the inputs' and not ins:
                for _p, rr in patches:
                    lane = str(rr[0]['lane'])
                    if lane.isdigit() and int(lane) in MIC_STRIPS:
                        ins.append((rr[0]['in'], int(lane)))
        return outs, ins

    def bind_row(self, base, out, drive, name, strip):
        r = dict(base)
        r['out'], r['drive'] = out, drive
        r['in'], r['lane'] = name, str(strip)
        r['donor'] = str(donor_for(strip))
        r['route'] = route_id(drive, r['donor'])
        r['prompt'] = 'Patch %s to %s' % (out, name)
        return r

    def find_loop(self, pid, rows):
        """Step 1 (PW 2026-09-26): find a working loop before judging anything.

        EVERY CANDIDATE IS AN ORDINARY PROMPT AND EVERY MISS IS THE
        OPERATOR'S CALL (S157). "Patch AUX 1 to MIC 1" goes up exactly as any
        patch does; if nothing arrives the step STOPS on the FAILED screen,
        and only LEADS CORRECT moves the walk to the next socket -- the walk
        used to do that by itself after 20 s, which is how five runs on
        2026-09-30 walked MIC 3, 4, 5 ... with the lead still in MIC 1. RETRY
        prompts the same socket again. Three sockets confirmed dead in a row
        and the OUTPUT becomes the suspect, as PW ruled on 2026-09-26.

        A socket confirmed dead here is logged and remembered, never recorded
        as a row: the inputs walk visits every input, MIC 1-24 in order with
        no exceptions (PW 2026-09-30), and grades it there with its own
        confirmation.
        """
        outs, ins = self.loop_candidates()
        if not outs or not ins:
            return None
        base = rows[0]
        for out, drive in outs:
            misses = 0
            for name, strip in ins:
                if strip in self.dead_in:
                    continue
                row = self.bind_row(base, out, drive, name, strip)
                while True:
                    prep, tok = self._prompt(pid, [row])
                    how, ans, _dt = self.detect([row], prep, tok,
                                                status=LV.LOOKING)
                    self.p.done(tok)
                    if how == 'glass' and ans.get('button') in STOP_BUTTONS:
                        self.finish_early([row], ans)
                        return 'stopped'
                    if how in ('retry', 'enter-no'):
                        self.log('%s RETRY: %s into %s again' % (pid, out,
                                                                  name))
                        continue
                    break
                if how in ('rise', 'drop', 'enter-ok'):
                    self.ref_in = (name, strip)
                    self.ref_out = (out, drive)
                    self.log('the loop is %s into %s: that input is the '
                             'reference for the pass' % (out, name))
                    self.live.set(state=LV.CHECKING)
                    return (row, prep)
                if how == 'glass' and ans.get('button') in PATCH_DECISIONS:
                    why = ('the operator moved past this one while the loop '
                           'was being found')
                else:
                    why = ('no signal, confirmed by the operator (LEADS '
                           'CORRECT) while the loop was being found')
                    self.confirmed.append(dict(
                        patch=pid, what='%s into %s' % (out, name),
                        failure='no signal while finding a working loop',
                        answer='LEADS CORRECT'))
                self.dead_in[strip] = why
                self.log('%s: %s into %s -- %s; the next socket is offered'
                         % (pid, out, name, why))
                misses += 1
                if misses >= MAX_DEAF_IN_A_ROW:
                    break                    # the output is the suspect now
        return None

    def no_loop(self):
        """Nothing anywhere. That is a whole-unit fault and one sentence, not
        forty fails (PW 2026-09-26)."""
        self.log('no output reached any input: the pass stops here')
        self.live.set(state=LV.STOPPING)
        self.teardown()
        self.live.set(state=LV.FINISHED, instruction='', lead_line='', extra='',
                      status=LV.NO_LOOP, action=LV.HANDOVER,
                      passed=self.passed, failed=self.failed,
                      failures=list(self.failures))

    # -- the screen ---------------------------------------------------------
    def index(self, seq):
        """Where every patch sits in the pass, so the screen can say `3 of 55`
        and `lead 1 of 3` without counting anything of its own."""
        self.where = {}
        n = 0
        for bi, (_, patches) in enumerate(seq):
            for pid, _rows in patches:
                n += 1
                self.where[pid] = (n, bi + 1, len(seq))
        self.live.set(state=LV.STARTING, total=n, n=0, lead_n=0,
                      lead_total=len(seq))

    def announce(self, pid, rows):
        """One instruction on the glass, and the state that goes with it.

        A lead change is FOLDED IN HERE and nowhere else: there is no card to
        acknowledge and nothing to press at a block boundary, because the lead
        going into the socket is the acknowledgement (S123).
        """
        n, lead_n, lead_total = self.where.get(pid, (0, 0, 0))
        r = rows[0]
        lead_line, self._lead_line = self._lead_line, ''
        self._hinted = None
        # A lead the instruction already names does not need picking up in a
        # sentence of its own: "Pick up the 150 ohm plug. Put the 150 ohm plug
        # into MIC 1." is one sentence too many for somebody holding it.
        if lead_line and LV.lead_words(r['lead']) in LV.instruction_for(r):
            lead_line = ''
        # A LEAD CHANGE INSIDE A BLOCK (S126, ruling g). With one stop per
        # input the lead changes at every patch, not at every block, so the
        # pick-up sentence follows the LEAD and not the block boundary. In the
        # three-walks order this never fires: `lead_card` has already set it.
        if not lead_line and r['lead'] != getattr(self, '_lead_now', None):
            lead_line = LV.pick_up(r['lead'])
        self._lead_now = r['lead']
        extra = LV.extra_for(r) or LV.hold_note(len(rows))
        # ONE PLAIN PROMPT FOR EVERY PATCH (PW 2026-09-30, "no parked leads,
        # use one at a time"). "Patch <out> to <in>", or "Fit the 150 ohm
        # terminator in <in>" -- never "move the other end", never a swap,
        # never a lead to take off first: every patch is one lead plugged
        # fresh at both ends, so there is nothing else to say.
        line = LV.instruction_for(r, confirm=not self.auto)
        # WHAT WAS IN THIS SOCKET A MOMENT AGO (S158): the patch before this
        # one, which is what tells the 150 ohm step whether its socket is
        # empty (the 150 ohm pass) or still has the tone lead in it.
        self._prev_in = getattr(self, '_last_in', None)
        self._prev_tone = getattr(self, '_last_tone', False)
        self._last_in = r['in']
        self._last_out = (r.get('out') or '').strip() or None
        self._last_tone = r['expect'] != 'noise'
        if r['expect'] == 'noise' and self.auto:
            # ENTER IS ON THE 150 OHM SCREEN FROM THE PROMPT (S158), and it
            # stays on it whatever is written over the prompt (see
            # `Live.wait_buttons`).
            self.live.wait_buttons = LV.TERMINATOR_BUTTONS
            extra = LV.terminator_extra(self._prev_in
                                        if not self._prev_tone else None,
                                        lead_in=(self._prev_tone and
                                                 self._prev_in == r['in']))
        else:
            self.live.wait_buttons = None
        self.live.set(state=LV.WAITING, instruction=line,
                      lead_line=lead_line, extra=extra,
                      n=n, lead_n=lead_n, lead_total=lead_total)

    def record(self, scored, prompted=False):
        """Take a patch's rows into the results, and put its verdict up.

        One patch is one thing to the operator however many measurements it
        carries, so the banner is the patch's worst row and the tally counts
        patches -- twenty-four checks that all passed is one PASS, and one bad
        leg of a stereo jack fails the patch.

        `prompted` SAYS THE NEXT PATCH IS ALREADY ON THE SCREEN (S128 hotfix).
        The pipeline puts the next instruction up before this one is scored, so
        the verdict is written OVER a screen that is already waiting for the
        operator -- and a state of VERDICT takes the ENTER button off it.
        Which was the whole fault. When a prompt is up the state stays WAITING,
        because that is what the screen is doing; only the banner changes.
        """
        self.rows_out += scored
        if not scored:
            return
        verdicts = {s['verdict'] for s in scored}
        # A PATCH NOBODY MEASURED IS NOT A FAIL AND NOT A DEAD SOCKET (S127).
        # SKIP and IGNORE say the operator could not make this patch; they say
        # nothing about the unit, so they neither condemn the parking output
        # nor go in the failure list the glass shows. They are still in the
        # results CSV with the operator's reason, which is where the one report
        # at the end reads them from.
        undecided = verdicts <= {SKIPPED, IGNORED}
        r = scored[0]
        name = LV.patch_words(dict(out=r['out'], **{'in': r['in']}))
        # The app draws the banner off `banner` alone, never off the state
        # (`FactoryView.Draw`: `verdict = s.Banner.Length > 0`), so WAITING with
        # a banner is the SAME screen with the right buttons under it.
        # AND WITH NO PROMPT UP, THE INSTRUCTION GOES (S128 hotfix). At a block
        # boundary `next_patch` returns None -- a lead change is not prepared
        # across -- so nothing new is announced and the screen keeps the
        # instruction of the patch that was just MEASURED. A verdict banner
        # over "Plug AUX 1 into MIC 1, then press ENTER.", with no ENTER, tells
        # a worker to do again what they have just done. It lasts only until
        # the next block is prepared, but the next block is prepared on the
        # UNIT and that is about a second of it. The verdict stands alone.
        st = LV.WAITING if prompted else LV.VERDICT
        gone = {} if prompted else dict(instruction='', lead_line='', extra='')
        if undecided:
            self.skipped_n += 1
            self.live.set(state=st, banner='NOT TESTED', **gone,
                          banner_line=name, action='', passed=self.passed,
                          failed=self.failed)
        elif verdicts <= {PASS}:
            self.passed += 1
            self.live.set(state=st, banner='PASS', **gone, banner_line=name,
                          action='', passed=self.passed, failed=self.failed)
        else:
            self.failed += 1
            self.failures.append(name)
            self.live.set(state=st, banner='FAIL', **gone, banner_line=name,
                          action=LV.action_failed(), passed=self.passed,
                          failed=self.failed, failures=list(self.failures))

    def next_patch(self, seq, bi, pi):
        """The next patch IN THE SAME BLOCK. A block boundary is a lead change,
        and the change is folded into that block's first instruction, so
        nothing is prepared across one."""
        patches = seq[bi][1]
        return patches[pi + 1] if pi + 1 < len(patches) else None

    def lead_card(self, lead, block, patches, n, total):
        """A lead change, and NOT a card.

        This used to put a READY dialog up and wait for a press. PW, at the
        bench on 2026-09-26, wanted it gone: a factory worker following
        instructions should never be asked to confirm that they have read one.
        So the change becomes a sentence on the next instruction's screen, and
        the block still announces itself on the terminal and in the log for
        whoever is reading those.
        """
        self._lead_line = LV.pick_up(lead)
        self._lead_now = lead
        self.g.progress('%s - %d patches' % (block, len(patches)))
        self.live.set(lead_n=n, lead_total=total)

    def no_signal(self, rows):
        """The row the NO SIGNAL button records: FAIL, in PW's own words.

        WHY THIS IS A FAIL AND `nodata` IS NOT. The station's standing rule is
        that a wrong patch is a prompt and never a fail, and it holds: `detect`
        sweeps every lane before it will honour the press, so a tone that is
        anywhere on the unit sends the operator back to re-patch instead of
        landing this row. What is left is a patch the operator made, looked at,
        and says is not carrying -- which is the one judgement about the PATH
        that only a person standing in front of it can make. It is the same shape
        as the panel loop's NOT LIT, and like NOT LIT it advances at once.
        """
        why = LV.NO_SIGNAL_FAIL
        detail = ('the operator said no signal reached %s; no tone was on any '
                  'other input either' % rows[0]['in'])
        pair = self._pair_seen if self.trs(rows) else None
        if pair:
            # THE JACK CARRIES ANOTHER PAIR (S159), and the operator says the
            # lead is in the jack marked as asked: the jack order is the fault,
            # not a dead output. Recorded as such, in words a reader can act on.
            why = ('jack %s carries aux %d/%d -- wiring/label order'
                   % (rows[0]['out'], pair[0], pair[0] + 1))
            detail = ('nothing reached %s from AUX %s; driving each other '
                      'pair\'s tip alone lit it on AUX %d, and the operator '
                      'confirmed the lead was in the jack marked %s (LEADS '
                      'CORRECT): the panel\'s TRS jack order does not match '
                      'its labels, or the lead was in another jack'
                      % (rows[0]['in'], rows[0]['drive'][4:], pair[0],
                         rows[0]['out']))
        self.log('%s: recorded FAIL -- %s' % (rows[0]['patch'], why))
        return [dict(path=r['path'], patch=r['patch'], lead=r['lead'],
                     out=r['out'], **{'in': r['in']}, sub=r['sub'],
                     rows=r['rows'], verdict=FAIL, why=why, detail=detail,
                     h_db=None, h_deg=None, thd_db=None, noise_db=None,
                     rms_db=None) for r in rows]

    def decided(self, rows, ans):
        """SKIP or IGNORE on the patch that is up. One patch, not the pass.

        PW's ruling of 2026-09-27: a fail is logged, the walk carries on, and
        every fail is in the one report at the end. SKIP and IGNORE are the
        operator's half of that -- "this one cannot be made, move on" -- so
        they record the patch with the operator's own reason and return.

        The reason comes back from the dialog and is the operator's word for
        it, so it is written down as given rather than re-worded here.
        """
        button = ans.get('button')
        verdict = PATCH_DECISIONS[button]
        reason = (ans.get('reason') or 'other').strip()
        self.log('%s %s: %s' % (rows[0]['patch'], verdict.lower(), reason))
        why = '%s by the operator: %s' % (
            'skipped' if verdict == SKIPPED else 'ignored', reason)
        return [dict(path=r['path'], patch=r['patch'], lead=r['lead'],
                     out=r['out'], **{'in': r['in']}, sub=r['sub'],
                     rows=r['rows'], verdict=verdict, why=why, detail='',
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
        self.paused = True
        self.live.set(state=LV.STOPPING)
        self.teardown()
        self.live.set(state=LV.PAUSED, instruction='', lead_line='', extra='',
                      status='Paused - the unit is safe. %s'
                             % ('Press START to run the test again.'
                                if self.rows_out else
                                'Press START when you are ready.'),
                      passed=self.passed, failed=self.failed,
                      failures=list(self.failures), action='')

    def finish(self):
        """The end of the pass: the tally, the failures by name, and who the
        unit goes to. Nothing here is a number the screen worked out."""
        self.live.set(state=LV.STOPPING)
        self.teardown()
        self.live.set(state=LV.FINISHED, instruction='', lead_line='',
                      extra='',
                      status=LV.finished_words(self.passed, self.failed,
                                               self.skipped_n),
                      action=LV.HANDOVER, passed=self.passed,
                      failed=self.failed, failures=list(self.failures),
                      n=self.live.d.get('total', 0))

    def teardown(self):
        """The unit put back safe, always, in PW's order.

        S115's lesson, and it cost PW a unit that hissed: a route asserted by a
        test and never taken down stays asserted for as long as the unit is
        powered. S123 adds the analog side to the same rule, and fixes the
        ORDER: the rails go down FIRST and the mic-pre chain is rewritten to
        SAFE after them, so a chain write can never be the thing that is heard;
        then the oscillator, the routes, and the monitor bus.

        Runs on every way out -- the last patch, PAUSE, a signal, an exception
        -- and runs once.
        """
        if getattr(self, '_torn', False):
            return
        self._torn = True
        # The screen goes back to whatever the pass around this station had it
        # set to (see `_own_the_screen`).
        if self._confirm_was is not None:
            self.live.confirm = self._confirm_was
        # The listener, if `run` was never entered (a --lamp-sweep run) or left
        # by a path that bypassed its own finally. Idempotent.
        try:
            self.mj_close(ask=False)
        except Exception as e:
            self.log('the mini-jack sense could not be closed: %s' % e)
        try:
            self.an.down()
        except Exception as e:                       # never mask the real error
            self.log('the rails and the chain could not be put back: %s' % e)
        # THE PRODUCT'S PROCESSING SETTINGS GO BACK FIRST (S154), and on
        # their own: a failure below must not cost the restore.
        try:
            self.bypass_restore()
        except Exception as e:
            self.log('the processing settings could not be restored: %s' % e)
        try:
            self.u.osc(on=False)
            self.u.write(self.L.routes['_standing_close'], verify=False)
            # The monitor bus, explicitly. It is not one of this station's
            # routes, so closing the assigns does not close it; it is also the
            # one bus that reaches an amplifier which is not on the rails.
            self.u.write(['Mon001Level001=f0', 'Mon001Level002=f0'],
                         verify=False)
        except Exception as e:
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
# One 595 chain write through the lean writer, MEASURED on MW-D24-2 on
# 2026-09-26: 8.1 ms with gpiod holding CS_M, against 157 ms calling
# s55_chain.send() in-process and 294 ms as a process per write.
CHAIN_WRITE_S = 0.0081


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
        self.moved_at = now()

    # -- the same surface as Unit -----------------------------------------
    def mark_moved(self):
        self.moved_at = now()

    def settle_owed(self, full):
        if self.moved_at is None:
            return 0
        return max(0, int(math.ceil(full - (now() - self.moved_at) / WIN_S)))

    def write(self, specs, verify=True):
        for spec in specs:
            name, _, val = spec.partition('=')
            if self.route.get(name) != val:
                self.mark_moved()
            self.route[name] = val
            self.writes += 1
            nap(CELL_WRITE_S)
        return []

    def read(self, name):
        """The last word written, as the part would read it back; a cell
        never written reads 1 -- a product setting found ON, which is the
        case the bypass exists for."""
        val = self.route.get(name)
        if val is None:
            return 1
        return f32(val[1:]) if val.startswith('f') else int(val, 0)

    def osc(self, chan=None, freq=None, level_dbfs=None, on=None):
        # ONE NAP PER CELL ACTUALLY WRITTEN, not four every time: a gain step
        # writes the level and nothing else, and charging it for the chan, the
        # frequency and the on/off it did not touch put 12 ms on every one of
        # the hundred and forty-four element steps in a pass.
        specs = 0
        if chan is not None:
            if self.osc_chan != chan:
                self.mark_moved()
            self.osc_chan = chan; specs += 1
        if freq is not None:
            if self.osc_freq != freq:
                self.mark_moved()
            self.osc_freq = freq; specs += 1
        if level_dbfs is not None:
            if self.osc_level != level_dbfs:
                self.mark_moved()
            self.osc_level = level_dbfs; specs += 1
        if on is not None:
            if self.osc_on != on:
                self.mark_moved()
            self.osc_on = on; specs += 1
        nap(CELL_WRITE_S * specs)

    def meas_chan(self, lane):
        if self.lane != lane:
            self.mark_moved()
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
        db = self.w.level(self.driven(), lane, self.osc_on, self.osc_level)
        # THE PREAMP IS PART OF THE MODEL SINCE PW'S SEVEN GAIN STEPS. Without
        # it a dry run cannot tell a correct step from a broken one, which is
        # the only way this session can check the step arithmetic at all.
        g = self.w.preamp_db(lane)
        return db + g if db > -200 else db

    def ein_capture(self, n=EIN_CAP_N, k=EIN_CAPS):
        """The capture arm, in arithmetic: the lane's noise as the model has
        it, white, so 20-20k sits 0.8 dB under DC-24k and A about 2.4 under
        that. Charged the S160 bench time (0.65 s a capture)."""
        nap(0.65 * k)
        db = self.level_at(self.lane)
        return dict(u=db - 0.79, a=db - 3.2, total=db, caps=k, n=n,
                    overruns=[0] * k)

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
        out = dict(rms=db, thd=self.w.thd, noise=db - 60.0, n=windows,
                   rms_spread=0.0)
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

    And three that are the OPERATOR and not the unit (S127). PW's three
    defects of 2026-09-27 were all about what a press does, so the dry run has
    to be able to press:

        skip:<in>        the operator presses SKIP on that patch
        ignore:<in>      ... IGNORE
        pause:<in>       ... PAUSE, which is the one press that ends the pass
    """

    # The operator's own buttons, and the fault name that presses each.
    PRESSES = ('skip', 'ignore', 'pause')

    REF_PHASE = 42.0             # this unit's loop phase at 1 kHz, arbitrary
    thd = -72.0

    gain_table = {}
    send_pos = {}
    chain = None

    def preamp_db(self, lane):
        """What this lane's preamp is adding, from the image on the chain.

        The image does not run in panel order, so the tx byte comes from the
        same map the station uses -- `send_pos`, zero-based, NOT the daisy
        chain position (S125) -- and a lane with no byte (the codec return
        lanes) has no preamp and adds nothing.
        """
        if not self.chain or not self.gain_table:
            return 0.0
        pos = self.send_pos.get(int(lane))
        if pos is None:
            return 0.0
        code = (self.chain[pos] >> 2) & 63
        # A DEAD GAIN ELEMENT. `gain:MIC 7:3` opens element 3 on that input:
        # the bit is written, the resistor is not there, so the step reads as
        # if the element were off. That is what an open FET or a missing part
        # does, and it is the thing the seven steps exist to catch.
        for f in self.faults:
            if f.startswith('gain:'):
                _k, who, bit = f.split(':')
                if who.strip() == 'MIC %d' % int(lane):
                    code &= ~(1 << (int(bit) - 1))
        spec = self.gain_table.get(code)
        return spec['expected_db'] if spec else 0.0

    def __init__(self, faults=(), quiet_floor=-96.0):
        self.faults = set(faults)
        self.floor = quiet_floor
        self.plugged_in = None
        self.plugged_out = None
        self.plugged_lanes = set()
        self.plugged_lead = None
        self.mispatched = set()
        self.pressed = set()     # (button, patch) -- a press happens once

    # THE THREE STATES OF THE NOISE SWAP, above the terminated floor (S153).
    # A lead left in carries AUX 1's idle output lifted 53 dB -- S55 read the
    # loop cable at -51 dBFS against the 150 ohm's -86 on J31 -- and an open
    # input sits between: S125's -78..-82 against S55's -86..-93.
    LEAD_IDLE_DB = 35.0
    OPEN_DB = 9.0

    def plug(self, out_port, in_port, lanes, lead=None):
        self.plugged_out, self.plugged_in = out_port, in_port
        self.plugged_lanes = set(lanes)
        self.plugged_lead = lead

    def unplug(self):
        self.plugged_in = self.plugged_out = self.plugged_lead = None
        self.plugged_lanes = set()

    def level(self, driven, lane, osc_on, osc_level):
        if not osc_on:
            # the noise rows: an open input is noisier than a terminated one,
            # and a lead still in is noisier than both
            if lane not in self.plugged_lanes:
                return self.floor + self.OPEN_DB
            if self.plugged_lead != 'K5':
                return self.floor + self.LEAD_IDLE_DB
            return self.floor
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
        # THE JACK CENTRE INVERTS, AND THE MODEL HAS TO KNOW (S129). On every
        # combo socket from MIC 3 to MIC 24 the board wires the jack TIP to the
        # preamp's cold leg -- see gen_patch_paths.block_k4 for the netlist
        # trace -- so a patch into `MIC n line` reads inverted against the same
        # socket's XLR, and that reading is what tells the two sockets apart. A
        # simulator that modelled the jack as in-phase would dry-run the whole
        # line block as the operator putting the lead in the wrong socket.
        if self.plugged_in and str(self.plugged_in).endswith(' line'):
            inverted = not inverted
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


class SimAnalog(Analog):
    """The rails and the chain, in arithmetic. It writes nothing anywhere; it
    tells the world what image is on the part so the preamps can be modelled."""

    def __init__(self, world, gain, send_pos, log=None):
        Analog.__init__(self, enabled=False, log=log)
        self.w = world
        self.w.gain_table = gain
        self.w.send_pos = send_pos
        self.sent = []           # every (image, what), in order, for the proofs

    def chain(self, image, what):
        # THE IMAGE IS TRACKED HERE TOO, and it has to be: `Analog.phantom`
        # composes PW's shunt-first sequence off `self.image` (the image
        # currently on the part), so a simulated analog that never recorded one
        # would build every step from the SAFE image and the dry run would
        # prove a sequence the bench will not send.
        self.image = list(image)
        self.w.chain = list(image)
        self.writes += 1
        self.wrote = True
        self.sent.append((list(image), what))
        nap(CHAIN_WRITE_S)
        self.write_s += CHAIN_WRITE_S
        return True

    def up(self):
        pass

    def down(self):
        pass


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


# The reach for the ENTER button, after the lead is in. It is not the hand
# move -- that is `--hand` -- it is the second action PW's ruling adds, and it
# is a parameter because it is a fact about a person and not about this code.
PRESS_S = 0.8
# The dry run's operator at a FAILED screen (S157): how long they read it
# before answering, and the list's own timeout that raises it.
SIM_ANSWER_S = 3.0
SIM_TIMEOUT_S = 20.0


class SimPatcher(ManualPatcher):
    """The operator's hands: a fixed number of seconds, then the lead is in.

    `press_s` is the reach for ENTER that PW's ruling of 2026-09-26 added, and
    `press_s=None` is the ruling of 2026-09-28 taking it away again: the
    simulated operator presses NOTHING, because on a detected patch there is
    nothing to press. It is None on the ruled path and a number only in
    `--confirm-enter`, so a dry run cannot quietly prove the old loop.
    """

    def __init__(self, glass, world, hand_s, log, press_s=PRESS_S, auto=True):
        ManualPatcher.__init__(self, glass, auto=auto)
        self.w = world
        self.hand_s = hand_s
        self.press_s = press_s
        self.log = log
        self.at = None
        self.pull_at = None
        self.press_at = None
        self.pending = None
        # THE OPERATOR AT A FAILED SCREEN (S157). Nothing advances by itself
        # any more, so the dry run's operator has to answer: they read the red
        # screen for `answer_s` and then press LEADS CORRECT; a lead they put
        # in the wrong socket they move to the right one once the screen names
        # it. Without this a faulted dry run would wait for ever, which is
        # exactly what the real station now does with nobody there.
        self.answer_s = SIM_ANSWER_S
        self.give_up_at = None
        self.fix_at = None
        self.decide_at = None

    def done(self, token):
        ManualPatcher.done(self, token)
        self.give_up_at = self.fix_at = None

    def decide(self, what):
        if self.decide_at is None:
            self.decide_at = now() + self.answer_s
            return None
        if now() >= self.decide_at:
            self.decide_at = None
            self.log('the operator presses LEADS CORRECT on the failed patch')
            return 'nosignal'
        return None

    def connect(self, patch, rows, glass):
        tok = ManualPatcher.connect(self, patch, rows, glass)
        r = rows[0]
        # THE NOISE SWAP IS TWO MOVES (S153): the tone lead stays in its
        # socket until the operator's hand gets there, half way through their
        # time, and the plug goes in at the end of it. Every other patch
        # starts with the socket empty, as it always did.
        self.pull_at = None
        if r['expect'] == 'noise' and self.w.plugged_in == r['in']:
            self.pull_at = now() + self.hand_s / 2.0
        else:
            self.w.unplug()
        self.pending = (r['out'], r['in'],
                        sorted({int(x['lane']) for x in rows}), patch,
                        r['lead'])
        self.at = now() + self.hand_s
        self.press_at = None
        self.give_up_at = self.at + SIM_TIMEOUT_S + self.answer_s
        self.fix_at = None
        return tok

    def poll(self, token):
        # THE OPERATOR'S BUTTONS, ONCE EACH (S127). A press is answered as soon
        # as the instruction is up -- a worker who can see the patch cannot be
        # made does not wait for their own hand -- and only once per patch, so
        # SKIP moves the walk on instead of answering the next prompt too.
        if self.pending:
            inp, patch = self.pending[1], self.pending[3]
            for b in World.PRESSES:
                if ('%s:%s' % (b, inp) in self.w.faults
                        and (b, patch) not in self.w.pressed):
                    self.w.pressed.add((b, patch))
                    self.at = self.press_at = None
                    self.log('the operator presses %s on %s' % (b.upper(), inp))
                    return dict(button=b, reason='awaiting part')
        if self.pull_at is not None and now() >= self.pull_at:
            self.pull_at = None
            self.w.unplug()
        if self.at is not None and now() >= self.at:
            out, inp, lanes, patch, lead = self.pending
            key = 'mispatch:%s' % inp
            if key in self.w.faults and patch not in self.w.mispatched:
                self.w.mispatched.add(patch)
                wrong = lanes[0] % 24 + 1    # the socket next door
                self.w.plug(out, 'MIC %d' % wrong, [wrong], lead)
                # ... and moves it once the screen has named the socket
                self.fix_at = now() + max(3.0, self.hand_s)
            else:
                self.w.plug(out, inp, lanes, lead)
            self.at = None
            self.press_at = (None if self.press_s is None
                             else now() + self.press_s)
        if self.fix_at is not None and now() >= self.fix_at:
            self.fix_at = None
            out, inp, lanes, patch, lead = self.pending
            self.log('the operator moves the lead to %s' % inp)
            self.w.plug(out, inp, lanes, lead)
        if self.press_at is not None and now() >= self.press_at:
            self.press_at = None
            return dict(button='done', reason='')
        if self.give_up_at is not None and now() >= self.give_up_at:
            self.give_up_at = None
            self.log('the operator presses LEADS CORRECT on %s'
                     % (self.pending[1] if self.pending else '?'))
            return dict(button='nosignal', reason='')
        return None


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------
RESULT_COLUMNS = ('path', 'patch', 'lead', 'out', 'in', 'sub', 'rows',
                  'verdict', 'why', 'detail', 'h_db', 'h_deg', 'thd_db',
                  'noise_db', 'rms_db')


# ---------------------------------------------------------------------------
# ONE RUNNER PER START
# ---------------------------------------------------------------------------
class RunLock:
    """One file, one pid, and a refusal that says so in plain words.

    WHY IT IS HERE AND NOT IN THE APP. The display's START for this station
    runs `systemctl reset-failed d24-factory` and then `systemd-run
    --unit=d24-factory`, and `reset-failed` is not a guard: it CLEARS the
    previous unit's state so a second press starts a second runner. On
    2026-09-26 that put two of them on the unit at once and the second died on
    the GPIO the first was holding -- a `gpiod ... Device or resource busy`
    traceback in factory.log, which is a stack trace where a sentence belonged.
    PW's ruling of 2026-09-27: exactly one runner per START, enforced at the
    RUNNER, because the runner is the thing that knows.

    A lock whose pid is gone is STALE and is taken over, with a line saying so:
    a unit that has been power-cycled mid-run must not need a person to delete
    a file before the test will run again.
    """

    NAME = 'runner.lock'

    def __init__(self, dirpath, argv=None):
        self.path = os.path.join(dirpath, self.NAME)
        self.argv = list(argv if argv is not None else sys.argv)
        self.held = False

    @staticmethod
    def alive(pid):
        try:
            os.kill(int(pid), 0)
        except (OSError, TypeError, ValueError):
            return False
        return True

    def read(self):
        try:
            with open(self.path) as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None

    def take(self, log=None):
        """True if this process now owns the run; False if another one does.

        The write is a whole file moved into place, so a reader never sees half
        a lock, and the pid is checked BEFORE the refusal: a lock left by a
        runner that is no longer there is not a reason to refuse anybody.
        """
        held = self.read()
        if held and held.get('pid') != os.getpid() and self.alive(held.get('pid')):
            self.other = held
            return False
        if held and log:
            log('a previous run left its marker behind and is no longer '
                'running: taking over')
        d = dict(pid=os.getpid(), started=time.time(),
                 stamp=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                 argv=self.argv)
        os.makedirs(os.path.dirname(self.path) or '.', exist_ok=True)
        tmp = self.path + '.tmp'
        with open(tmp, 'w') as fh:
            json.dump(d, fh)
        os.replace(tmp, self.path)
        self.held = True
        return True

    def release(self):
        """Only ever removes THIS process's lock."""
        if not self.held:
            return
        held = self.read()
        if held and held.get('pid') != os.getpid():
            return
        try:
            os.remove(self.path)
        except OSError:
            pass
        self.held = False


def result_key(r):
    """What makes two result rows the same measurement.

    `path` is the list's own row number and is stable across runs of the same
    list; `patch` and `sub` name the connection and which check of it. The
    three together are what a re-run supersedes.
    """
    return (str(r.get('path', '')), str(r.get('patch', '')),
            str(r.get('sub', '')))


def merge_results(path, rows):
    """This run's rows over whatever the last run in this directory left.

    WHY A MERGE AND NOT A WRITE. On 2026-09-27 PW's pass stopped part way, PW
    pressed START, and the second run OVERWROTE the report: eight measured
    patches became five, and the eight were gone. "Put every fail in the one
    report at the end" cannot survive a file that only ever holds the last
    attempt. So the run's own rows are also kept under their own name, and the
    file the report is read from carries the whole session -- the newest verdict
    for every patch anybody has reached.

    A row this run did not reach keeps the verdict it already had; a row this
    run DID reach replaces it, because the newer measurement is the true one.
    """
    keep = []
    seen = set(result_key(r) for r in rows)
    try:
        for old in read_csv(path):
            if result_key(old) not in seen:
                keep.append(old)
    except (OSError, ValueError):
        pass
    if rows:
        base = os.path.join(os.path.dirname(path) or '.', 'patch-results-%s'
                            % time.strftime('%Y%m%dT%H%M%SZ', time.gmtime()))
        mine, n = base + '.csv', 0
        while os.path.exists(mine):          # two runs inside one second
            n += 1
            mine = '%s-%d.csv' % (base, n)
        write_results(mine, rows)
    # IN LIST ORDER, not in the order the session happened to reach them: this
    # is the file a person reads the pass off.
    both = sorted(keep + list(rows),
                  key=lambda r: (int(r['path']) if str(r.get('path',
                                 '')).isdigit() else 1 << 30,
                                 str(r.get('sub', ''))))
    return write_results(path, both)


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


def block_table(station, hand_s, press_s, out=sys.stdout):
    """What each block of the pass costs, hand and machine (S123 addendum 6).

    The machine seconds are the ones the loop actually spent -- every window,
    every cell write, every chain write and every peek is inside them -- so
    the table says where the time goes and not where it was supposed to.
    """
    per_hand = hand_s + press_s
    by = {}
    order = []
    for t in station.timing:
        b = t.get('block') or '(the start)'
        if b not in by:
            by[b] = dict(n=0, subs=0, machine=0.0)
            order.append(b)
        by[b]['n'] += 1
        by[b]['subs'] += t['subs']
        by[b]['machine'] += t['machine_s']
    out.write('\n  block                     steps  readings   machine s   '
              'per step   hand s @ %.1f s\n' % per_hand)
    out.write('  ' + '-' * 78 + '\n')
    tot_n = tot_s = 0
    tot_m = 0.0
    for b in order:
        d = by[b]
        tot_n += d['n']; tot_s += d['subs']; tot_m += d['machine']
        out.write('  %-24s %6d  %8d  %10.1f  %9.3f  %14.0f\n'
                  % (b[:24], d['n'], d['subs'], d['machine'],
                     d['machine'] / max(d['n'], 1), d['n'] * per_hand))
    out.write('  ' + '-' * 78 + '\n')
    out.write('  %-24s %6d  %8d  %10.1f  %9.3f  %14.0f\n'
              % ('the whole pass', tot_n, tot_s, tot_m,
                 tot_m / max(tot_n, 1), tot_n * per_hand))
    setup = sum(v for k, v in station.costs.items()
                if k == 'getting the unit ready')
    out.write('\n  where the machine seconds go\n')
    for k, v in sorted(station.costs.items(), key=lambda kv: -kv[1]):
        out.write('    %-26s %7.1f s\n' % (k, v))
    out.write('    %-26s %7d writes, %.1f s (%.1f ms each)\n'
              % ('...of which the 595 chain', station.an.writes,
                 station.an.write_s,
                 1000.0 * station.an.write_s / max(station.an.writes, 1)))
    out.write('\n  the operator waits for the machine only when the machine '
              'is slower than their hands:\n')
    slow = [(b, by[b]['machine'] / max(by[b]['n'], 1)) for b in order]
    worst = max(slow, key=lambda x: x[1])
    out.write('    worst block: %s at %.3f s a step against %.1f s of hand\n'
              % (worst[0], worst[1], per_hand))
    return by, setup


def print_time_table(by_lead, hand_s, plist, out=sys.stdout, press_s=0.0):
    # THE OPERATOR'S SECONDS ARE TWO ACTIONS NOW, not one: the hand move and
    # the reach for ENTER (PW 2026-09-26). Both are the operator's, so both
    # are counted here and neither is hidden in the machine column.
    per_hand = hand_s + press_s
    tot_m = sum(d['machine'] for d in by_lead.values())
    tot_n = sum(d['n'] for d in by_lead.values())
    out.write('\n  lead  patches  checks   machine s   per patch   hand s @ %.1f s\n'
              % per_hand)
    out.write('  ' + '-' * 62 + '\n')
    for lead in ('K1', 'K5', 'K4', 'K2', 'K3'):
        d = by_lead.get(lead)
        if not d:
            continue
        out.write('  %-4s  %7d  %6d  %10.1f  %10.2f  %12.0f\n'
                  % (lead, d['n'], d['subs'], d['machine'],
                     d['machine'] / d['n'], d['n'] * per_hand))
    out.write('  ' + '-' * 62 + '\n')
    out.write('  all   %7d  %6d  %10.1f  %10.2f  %12.0f\n'
              % (tot_n, sum(d['subs'] for d in by_lead.values()), tot_m,
                 tot_m / max(tot_n, 1), tot_n * per_hand))
    out.write('\n  projected pass: %.0f s hands (%.0f s moving the lead + '
              '%.0f s pressing ENTER) + %.0f s machine = %.1f min\n'
              % (tot_n * per_hand, tot_n * hand_s, tot_n * press_s, tot_m,
                 (tot_n * per_hand + tot_m) / 60.0))


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
    patcher = SimPatcher(glass, world, a.hand, log, auto=a.auto_advance,
                         press_s=None if a.auto_advance else a.press)
    send_pos = {}
    for r in plist.paths:
        if r.get('send_pos') != '' and str(r['lane']).isdigit():
            send_pos[int(r['lane'])] = int(r['send_pos'])
    an = SimAnalog(world, plist.gain, send_pos, log=log)
    live = LV.Live(a.live, run='patch', enabled=bool(a.live) and not a.no_live,
                   confirm=not a.auto_advance)
    # The dry run's operator presses nothing on the ruled path: the lead going
    # in is the whole of their half of the step. In `--confirm-enter` SimPatcher
    # answers `done` `--press` seconds after its virtual hand has made the
    # connection, which is the same message the ENTER button sends.
    st = Station(plist, unit, patcher, glass, Limits.load(plist.dir), log=log,
                 blocks=a.block, live=live, analog=an,
                 auto_advance=a.auto_advance, prearm=a.prearm,
                 trials=a.click_trials,
                 trial_only=split_inputs(a.trial_inputs),
                 mj_input=a.mj_detect_input)
    rows = st.run()
    if st.click_results:
        print('')
        click_table(st.click_results)
    counts = {}
    for r in rows:
        counts[r['verdict']] = counts.get(r['verdict'], 0) + 1
    print('\nDRY RUN (no unit): %d measurements in %d patches'
          % (len(rows), len(st.timing)))
    print('  ' + ', '.join('%s %d' % (k, v) for k, v in sorted(counts.items())))
    if st.prearm:
        print('  pre-armed (ruling d): %d patches read before ENTER and '
              'confirmed at it, %d re-read. Those readings cost %.1f s and '
              'were taken while the hand was still on the connector; what '
              'comes OFF the operator\'s path is the per-patch machine time '
              'in the table below.'
              % (st.armed_kept, st.armed_lost, st.armed_saved_s))
    if a.fault:
        print('  faults injected: %s' % ', '.join(a.fault))
        for r in rows:
            if r['verdict'] != PASS:
                print('    %-5s %-22s %-9s %s'
                      % (r['patch'], r['in'], r['verdict'], r['why']))
    print_time_table(time_table(st, plist, a.hand), a.hand, plist,
                     press_s=0.0 if a.auto_advance else a.press)
    block_table(st, a.hand, 0.0 if a.auto_advance else a.press)
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


def cmd_strings(a, plist):
    """Every word the factory screen can put in front of a person, with no
    unit and no run. This is what the internal-vocabulary check reads."""
    with open(a.strings, 'w', encoding='utf-8') as fh:
        fh.write('# every operator-facing string the factory patch screen can\n'
                 '# produce. Generated, not written.\n\n')
        for s in LV.every_string(plist.paths):
            fh.write('%s\n' % s)
    print('wrote %s' % a.strings)
    return 0


# ---------------------------------------------------------------------------
# Walking the screen with no hands
# ---------------------------------------------------------------------------
# WHY THIS EXISTS. Nobody in this session can plug a lead in, and a screen
# that has only ever been seen in a drawing is a screen that has not been
# built. So the runner drives its own status file through every state the loop
# can reach, on the real unit, in front of the real display, and the display's
# own capture path photographs each one. It is the runner doing it -- the same
# `Live` object, the same words out of the same file -- so what is
# photographed is what a worker would see and not a mock-up of it.
def _row_by(plist, **want):
    for r in plist.paths:
        if all(str(r.get(k, '')) == str(v) for k, v in want.items()):
            return r
    return plist.paths[0]


def setup_pages(plist):
    """The pages the operator is walked through at START (HUB ADDENDUM 1).

    ONE BIG INSTRUCTION PER PAGE, n of N, ENTER on each -- never a checklist
    wall. `check` names the reading the machine can take to confirm the page
    live; an empty one means nothing on the unit can see that item, and the
    page says nothing about it rather than pretending.

    The order is the order of the work: the network lead, the two USB sticks,
    then the kit in the order patch-kit.csv lists it. There is no pre-START
    page: the only thing that has to be in before START is the mains lead, and
    a unit showing this screen is running from it.
    """
    # ONE USB PAGE, NOT TWO, AND IT NAMES THE TOP PANEL (S128). There used to
    # be one page per hub port, each naming a side of a "double USB pair on the
    # rear panel" -- the wrong panel, and the rear socket is the touch screen's.
    # The two sockets are on the ANALOG board on the top panel, which is what
    # the catalog has said about rows 130/131 all along, and one page that asks
    # for both is one press fewer and nothing to get wrong. The two rows are
    # still graded separately, by `usb_port:3` and `usb_port:4`, under the patch
    # pass; this page's own check reads the pair and says which one is empty.
    pages = [dict(key='network', instruction=LV.setup_network(), check='link'),
             dict(key='usb-pair', instruction=LV.setup_usb(),
                  check='usb_pair:3,4')]
    # ONE KIT PAGE, AND NOTHING HUNG ON A SOCKET (S157, PW 2026-09-30: "remove
    # the parked cable request, I see no advantage, use one at a time"). The
    # leads go on the bench; each patch asks for one, plugged fresh.
    if plist.kit:
        pages.append(dict(key='kit-bench', check='',
                          instruction=LV.bench_kit_page()))
    return pages


def screen_walk(plist, confirm=False):
    """The states, in the order a pass reaches them, each with a name.

    `confirm` is the station's own mode, and it has to be passed in rather than
    assumed: the instructions end in "then press ENTER" on one path and in a full
    stop on the other, and the walk exists so each screen can be PHOTOGRAPHED as
    the operator will see it. Default False -- the ruled path (PW 2026-09-28).
    """
    first = plist.paths[0]
    tone = _row_by(plist, lead='K1', **{'in': 'MIC 5'})
    noise = _row_by(plist, lead='K5')
    line = _row_by(plist, lead='K4')
    trs = _row_by(plist, lead='K2')
    total = len({r['patch'] for r in plist.paths})

    def at(r, n, **kw):
        d = dict(instruction=LV.instruction_for(r, confirm),
                 extra=LV.extra_for(r),
                 n=n, total=total, lead_n=1, lead_total=4)
        d.update(kw)
        return d

    return [
        ('01-armed-start', None),
        ('02-getting-ready', dict(state=LV.STARTING, n=0, total=total,
                                  lead_n=0, lead_total=4)),
        ('03-setup-network',
         dict(state=LV.WAITING, instruction=LV.setup_network(), lead_line='',
              extra='', status=LV.SETUP_TITLE, n=1,
              total=len(setup_pages(plist)), lead_n=0, lead_total=0)),
        ('04-setup-usb-seen',
         dict(state=LV.WAITING, instruction=LV.setup_usb(),
              lead_line='', extra=LV.SETUP_SEEN, status=LV.SETUP_TITLE, n=2,
              total=len(setup_pages(plist)), lead_n=0, lead_total=0)),
        ('05-setup-kit-on-the-bench',
         dict(state=LV.WAITING, lead_line='', extra='',
              instruction=LV.bench_kit_page(),
              status=LV.SETUP_TITLE, n=3, total=len(setup_pages(plist)),
              lead_n=0, lead_total=0)),
        ('06-lead-change', at(first, 1, state=LV.WAITING,
                              lead_line=LV.pick_up(first['lead']))),
        ('08-walk-to-the-next-input',
         at(tone, 1, state=LV.WAITING, lead_line='',
            instruction=LV.instruction_for(
                dict(tone, **{'in': 'MIC %d' % (int(tone['lane']) + 1)}),
                confirm),
            status=LV.LOOKING)),
        ('09-waiting', at(tone, 5, state=LV.WAITING, lead_line='')),
        ('10-signal-found', at(tone, 5, state=LV.WAITING, lead_line='',
                               status=(LV.SIGNAL_SEEN if confirm
                                       else LV.SIGNAL_HOLDING))),
        ('11-checking', at(tone, 5, state=LV.CHECKING, lead_line='')),
        ('12-pass', at(tone, 6, state=LV.VERDICT, banner='PASS',
                       banner_line=LV.patch_words(tone), passed=5, failed=0)),
        ('13-wrong-socket', at(tone, 6, state=LV.CHECKLEAD,
                               banner='CHECK THE LEAD', banner_line='',
                               status=LV.status_wrong_input('MIC 7',
                                                            tone['in']),
                               action=LV.action_wrong_socket('MIC 7',
                                                             tone['in'],
                                                             confirm))),
        ('14-no-signal', at(tone, 6, state=LV.CHECKLEAD,
                            banner='CHECK THE LEAD', banner_line='',
                            status=LV.timeout_words(tone['in'], 20.0),
                            action=LV.action_no_signal(confirm))),
        # PW 2026-09-28: the row the one button records, as the operator sees it
        # land. It is a FAIL banner like any other -- there is no separate
        # "operator said so" colour, because to the person in front of the unit
        # it is the same thing: this path did not carry.
        ('14b-no-signal-recorded',
         at(tone, 7, state=LV.VERDICT, banner='FAIL',
            banner_line=LV.patch_words(tone), action=LV.action_failed(),
            passed=5, failed=1)),
        ('15-fail', at(tone, 7, state=LV.VERDICT, banner='FAIL',
                       banner_line=LV.patch_words(tone),
                       action=LV.action_failed(), passed=5, failed=1)),
        ('15b-graded-fail-waits',
         at(tone, 7, state=LV.CHECKLEAD, banner='FAIL',
            banner_line=LV.patch_words(tone),
            status=LV.graded_fail_words('FAIL', 'the two channels did not '
                                        'cancel: only 12.0 dB down'),
            action=LV.action_graded_fail(), passed=5, failed=0)),
        ('16-terminator-step',
         at(noise, 20, state=LV.WAITING, lead_n=2, lead_line='')),
        ('16b-terminator-holding',
         at(noise, 20, state=LV.WAITING, lead_n=2, lead_line='',
            status=(LV.SIGNAL_SEEN if confirm else LV.SIGNAL_HOLDING))),
        ('17-line-step', at(line, 34, state=LV.WAITING, lead_n=3,
                            lead_line=LV.pick_up(line['lead']))),
        ('18-trs-output-step', at(trs, 48, state=LV.WAITING, lead_n=4,
                                  lead_line=LV.pick_up(trs['lead']),
                                  extra=LV.hold_note(3))),
        ('19-paused', dict(state=LV.PAUSED, n=30, total=total, instruction='',
                           lead_line='', extra='',
                           status='Paused - the unit is safe. '
                                  'Press START to run the test again.',
                           passed=28, failed=1,
                           failures=[LV.patch_words(tone)])),
        ('20-finished', dict(state=LV.FINISHED, n=total, total=total,
                             instruction='', lead_line='', extra='',
                             status=LV.finished_words(total, 0),
                             action=LV.HANDOVER, passed=total, failed=0,
                             failures=[])),
        ('21-finished-with-failures',
         dict(state=LV.FINISHED, n=total, total=total, instruction='',
              lead_line='', extra='',
              status=LV.finished_words(total - 2, 2), action=LV.HANDOVER,
              passed=total - 2, failed=2,
              failures=[LV.patch_words(tone), LV.patch_words(trs)])),
        ('22-no-signal-anywhere',
         dict(state=LV.FINISHED, n=1, total=total, instruction='',
              lead_line='', extra='', status=LV.NO_LOOP, action=LV.HANDOVER,
              passed=0, failed=0, failures=[])),
    ]


def _whole_png(path):
    """The capture file, if it is a whole PNG right now.

    The display writes this file on a loop while the walk is running, so a
    plain copy catches a half-written frame about as often as not. A PNG says
    where it starts and where it ends, so the check is exact rather than a
    sleep.
    """
    try:
        with open(path, 'rb') as fh:
            b = fh.read()
    except OSError:
        return None
    if len(b) > 64 and b[:8] == b'\x89PNG\r\n\x1a\n' and b[-8:-4] == b'IEND':
        return b
    return None


def cmd_screens(a, plist):
    out = a.screens
    os.makedirs(out, exist_ok=True)
    live = LV.Live(a.live or a.dir, run='patch',
                   total=len({r['patch'] for r in plist.paths}),
                   confirm=not a.auto_advance)
    cap = a.capture
    shots = []
    try:
        for name, state in screen_walk(plist, confirm=not a.auto_advance):
            if state is None:
                live.clear()                      # the armed screen: no run
            else:
                live.set(**state)
            t_set = time.time()
            # Hold the screen, beating so the display keeps calling the run
            # live, until the capture path has a frame newer than the change.
            got = None
            while time.time() - t_set < a.dwell or (got is None and
                                                    time.time() - t_set < a.dwell * 4):
                if state is not None:
                    live.beat()
                time.sleep(0.1)
                # THE FRAME HAS TO HAVE BEEN RENDERED AFTER THE CHANGE, not
                # merely written after it: the display re-renders on its own
                # cadence, so a file touched 0.4 s later can still carry the
                # picture it drew before. One whole capture period of margin
                # is what stops two different states photographing the same
                # screen -- which is exactly what happened on the first walk.
                if (cap and os.path.exists(cap)
                        and os.path.getmtime(cap) > t_set + a.capture_period):
                    b = _whole_png(cap)
                    if b:
                        got = b
            dst = os.path.join(out, '%s.png' % name)
            if got:
                with open(dst, 'wb') as fh:
                    fh.write(got)
                shots.append((name, dst))
                print('   %-28s %s  (%d bytes)' % (name, dst, len(got)))
            else:
                print('   %-28s NO FRAME (capture path %s)' % (name, cap))
    finally:
        live.clear()
    print('\n%d screen(s) captured into %s' % (len(shots), out))
    return 0 if shots else 1


def rails_are_up():
    """AN_EN, read off the pin. One shell call, no DSP link, no side effect."""
    import subprocess
    try:
        out = subprocess.run(['pinctrl', 'get', str(AN_EN_GPIO)],
                             capture_output=True, text=True,
                             timeout=20).stdout
    except (OSError, subprocess.SubprocessError):
        return None                      # cannot tell, so do not claim either
    return 'hi' in out


def cmd_guard(a):
    """The other half of liveness: a run that stopped without saying so.

    THE HEARTBEAT IS THE DEFINITION OF LIVE (S123), and until S127 only one side
    of that was enforced. A runner killed outright -- SIGKILL, an OOM, the mains
    -- cannot tear anything down or write anything, so it leaves the last
    instruction on the glass with a heartbeat that stops and THE RAILS UP. On
    2026-09-27 PW watched that for eight minutes and called it "froze in factory
    test mode". Nothing was going to change it, because the only thing that
    writes that file was dead. Measured on the part, that state is: AN_EN high,
    `live.json` frozen on "Plug MONITOR L into MIC 8, then press ENTER.", and a
    lock naming a pid that no longer exists.

    So this is the one check that needs no run behind it. In order, because the
    order is the whole of it:

      1. does a live pid hold the lock?  -> a run is going, touch nothing;
      2. has the screen already said the run ended?  -> only the rails are
         still worth checking;
      3. otherwise, has the heartbeat stopped for longer than the slack?  -> the
         run is gone: say so on the glass in one plain sentence;
      4. clear the dead lock, and put the rails down if they are up.

    Idempotent, and it never touches a live run. Safe from a timer, from the
    bench, or by hand. PW's order is kept: the rails go down through the
    station's own teardown, so there is not a second piece of code in this tree
    that knows it.
    """
    live_dir = a.live or a.dir
    lock = RunLock(a.dir)
    held = lock.read()
    owner = held.get('pid') if held else None
    if owner is not None and RunLock.alive(owner):
        print('a run is going (pid %s, started %s): nothing to do'
              % (owner, held.get('stamp')), flush=True)
        return 0

    try:
        with open(os.path.join(live_dir, LV.LIVE_NAME)) as fh:
            d = json.load(fh)
    except (OSError, ValueError):
        d = None
    up = rails_are_up()

    if d is None and held is None:
        if up:
            print('no run, no screen and no lock -- BUT THE RAILS ARE UP and '
                  'nothing owns them', flush=True)
        else:
            print('no run and no screen: nothing to do', flush=True)
            return 0
        gone = False
    elif d is not None and d.get('state') in (LV.PAUSED, LV.FINISHED):
        # A run that ended tidily has already torn down and its last word on
        # the glass is deliberate. The only thing left worth checking is whether
        # the rails really are down.
        gone = False
        if not up:
            print('the last run ended, its screen says so and the rails are '
                  'down: nothing to do', flush=True)
            lock_cleared = clear_stale_lock(lock, held)
            return 0 if not lock_cleared else 0
        print('the last run ended and its screen says so, BUT THE RAILS ARE UP '
              'and nothing owns them', flush=True)
    else:
        age = None if d is None else time.time() - float(d.get('heartbeat') or 0)
        stale_after = max(LV.LIVE_STALE_S, a.stale_after)
        if age is not None and age < stale_after:
            print('the screen was written %.1f s ago and nothing holds the '
                  'lock: leaving it alone for now (the slack is %.0f s)'
                  % (age, stale_after), flush=True)
            return 0
        gone = True
        print('the screen has not been written for %s and no runner holds the '
              'lock: the run is gone'
              % ('%.0f s' % age if age is not None else 'a while'), flush=True)
        live = LV.Live(live_dir, run='patch', enabled=True)
        if d:
            live.d.update(dict((k, d[k])
                              for k in ('n', 'total', 'passed', 'failed',
                                        'failures') if k in d))
        live.set(state=LV.PAUSED, instruction='', lead_line='', extra='',
                 action='',
                 status='%s %s' % (LV.stopped_words('the test program stopped'),
                                   LV.RESTART_WORDS))

    clear_stale_lock(lock, held)
    if up:
        # THE RAILS, LAST. They are only ever lowered when nothing owns them,
        # which is what the checks above have just established.
        an = Analog(enabled=not a.no_analog,
                    log=lambda t: print('   .. %s' % t, flush=True),
                    own_rails=True)
        try:
            an.down()
        except Exception as e:
            print('the rails could not be lowered: %s' % e, flush=True)
            return 1
    return 3 if (gone or up) else 0


def clear_stale_lock(lock, held):
    """Remove a lock whose pid is gone. Never removes a live one."""
    if not held:
        return False
    pid = held.get('pid')
    if pid is not None and RunLock.alive(pid):
        return False
    try:
        os.remove(lock.path)
    except OSError:
        return False
    print('   .. the dead run\'s marker is cleared, so START works again',
          flush=True)
    return True


def cmd_factory(a):
    """START on the factory screen = the WHOLE ruled sequence (PW 2026-09-27).

    WHAT WENT WRONG. The armed factory screen has launched THIS file since
    S123, when the patch walk was the only thing it drove: the app's START
    builds `python3 d24_patch.py --run --list-dir <factory.json's list> --dir
    runall --live runall` and runs it as `d24-factory.service`. S126 then built
    the full ruled order -- the setup pages, the overlap, the panel loops -- in
    `d24_runall.py`, and nothing re-pointed the armed screen at it. So PW
    pressed START, got the analog patch walk on its own, and was never asked
    for the network lead, the USB sticks or the parked kit. PW's ruling:
    "whatever START the operator presses on the factory screen is the full
    ruled sequence, setup pages first".

    THE LIST IS NOT TAKEN FROM THE COMMAND LINE HERE, and that is the other
    half of the ruling ("a quick list must never be the default behind the
    factory START"). The unit says which list it has, in `list.conf`, exactly
    as it says which DSP pair it has -- so the sequence is told nothing and
    `find_list_dir()` reads the unit's own declaration. A `--list-dir` on a
    factory START is ignored, and the log says so rather than silently
    honouring it.
    """
    sys.path.insert(0, HERE)
    import d24_runall as RA                          # noqa: E402
    # ONE RUNNER PER START, on this path too. The app's guard for this unit is
    # a `systemctl reset-failed`, which CLEARS the last run's state rather than
    # refusing a second press, so the refusal has to live here.
    lock = RunLock(a.dir)
    if not lock.take(log=lambda t: print('   .. %s' % t, flush=True)):
        other = lock.other
        print('a run is already going on this unit (pid %s, started %s): this '
              'START is refused' % (other.get('pid'), other.get('stamp')),
              flush=True)
        print(LV.second_start_words(), flush=True)
        return 2
    if a.list_dir:
        print('the factory test reads the unit\'s own list (list.conf), so '
              '--list-dir %s is ignored here; --patch-only honours it'
              % a.list_dir, flush=True)
    # THE TWO --dir ARGUMENTS ARE NOT THE SAME DIRECTORY. This station is
    # given the GLASS directory (`.../selftest/runall`); RUN ALL is given the
    # one ABOVE it and appends `runall` itself. Passing one straight through
    # gives `.../runall/runall`, a screen nothing reads and a report nobody
    # finds.
    d = a.dir.rstrip('/')
    base = os.path.dirname(d) if os.path.basename(d) == 'runall' else d
    # NO REVIEW SCREEN BEHIND THE FACTORY START (S128). The review screen is a
    # DIALOG and the armed display draws none, so a factory pass that reached it
    # sat on a prompt nobody could answer, holding the run lock, with "Finished"
    # and a START button on the glass and "The test is already running." behind
    # that START. RUN ALL refuses it on its own account too (it knows whether
    # the pass had a screen); this says it at the door as well, because the door
    # is where the rule is.
    argv = ['--dir', base, '--no-review']
    if a.symdir != FACTORY_TEST_PAIR_DIR:
        argv += ['--patch-symdir', a.symdir]
    if a.no_keyboard:
        argv.append('--no-keyboard')
    if a.stdin:
        argv.append('--stdin')
    print('the factory test: the whole ruled sequence (%s)'
          % ' '.join(['d24_runall.py'] + argv), flush=True)
    try:
        return RA.main(argv)
    finally:
        lock.release()


def cmd_run(a, plist):
    sys.path.insert(0, HERE)
    import d24_runall as RA                          # noqa: E402
    import signal
    # THE LOCK IS TAKEN BEFORE ANYTHING IS OPENED, and that order is the point.
    # `Unit()` claims the DSP chip-select GPIO, so a second runner used to get
    # as far as a `Device or resource busy` traceback -- after the first
    # runner's screen had already been overwritten by the second's. Nothing is
    # touched until this station knows it is the only one (S127).
    lock = RunLock(a.dir)
    if not lock.take(log=lambda t: print('   .. %s' % t, flush=True)):
        other = lock.other
        # ONE PLAIN SENTENCE, AND IT GOES NOWHERE THE LIVE RUN IS WRITING.
        # A refused START must not touch live.json OR progress.txt: the run
        # that is going owns both, and overwriting either takes the real run's
        # words off the screen -- which is the very thing a second press must
        # not do. So the refusal is printed, which lands in the runner's log
        # and nowhere else.
        print('a run is already going on this unit (pid %s, started %s): this '
              'START is refused' % (other.get('pid'), other.get('stamp')),
              flush=True)
        print(LV.second_start_words(), flush=True)
        return 2
    # ONE RUNNER PER UNIT, NOT PER DIRECTORY (S158). The lock above lives in
    # `--dir`, so a bench run into a scratch dir took its own lock and ran
    # BESIDE a RUN ALL that the glass had started -- one DSP, one chain, one
    # pair of rails, two owners (2026-10-01 11:15: the scratch run's teardown
    # lowered AN_EN and restored the processing cells under the factory run).
    # The factory glass directory's lock is taken too whenever it is not the
    # same place, and a run holding it refuses this one.
    unit_lock = None
    glass_dir = a.live or GLASS_DIR
    if (os.path.isdir(glass_dir)
            and os.path.realpath(glass_dir) != os.path.realpath(a.dir)):
        unit_lock = RunLock(glass_dir)
        if not unit_lock.take(log=lambda t: print('   .. %s' % t, flush=True)):
            other = unit_lock.other
            print('a run is already going on this unit (pid %s, started %s, '
                  'lock in %s): this run is refused'
                  % (other.get('pid'), other.get('stamp'), glass_dir),
                  flush=True)
            lock.release()
            return 2
    lock.partner = unit_lock            # released with it, in `end_of_run`

    glass = RA.Glass(a.dir, stdin=a.stdin)
    live = LV.Live(a.live or a.dir, run='patch',
                   enabled=not a.no_live, confirm=not a.auto_advance)
    st = None
    rows = []
    stopped_why = ''
    try:
        unit = Unit(symdir=a.symdir)
        patcher = pick_patcher(glass, a.back_end, auto_advance=a.auto_advance)
        an = Analog(enabled=not a.no_analog, log=glass.progress,
                    own_rails=a.own_rails)
        # THE KEYBOARD IS READ ON BOTH PATHS NOW. It used to be switched off
        # whenever the step did not end on a press, which was right while a press
        # could only mean "the lead is in" -- there was nothing for it to say. PW's
        # ruling of 2026-09-28 gives it something: the no-signal answer. It is the
        # one channel that certainly reaches this station on today's app (see the
        # note in `detect` about the button the glass may not draw), and a press
        # on it can still never grade a patch.
        keys = KeyWatch(enabled=not a.no_keyboard, log=glass.progress)
        st = Station(plist, unit, patcher, glass, Limits.load(plist.dir),
                     log=glass.progress, blocks=a.block, live=live, analog=an,
                     auto_advance=a.auto_advance, keys=keys,
                     trials=a.click_trials,
                     trial_only=split_inputs(a.trial_inputs),
                     mj_input=a.mj_detect_input)
        st.trace = bool(a.verbose)

        # A SIGNAL IS A WAY OUT LIKE ANY OTHER. The hub stops this station with
        # SIGINT and systemd stops it with SIGTERM; both used to leave the rails
        # up and the chain wherever the last block put it, which is a unit that
        # goes back on the bench live. The handler tears down, writes the report
        # of what completed, and re-raises.
        def stopped(sig, _frm):
            try:
                st.teardown()
            finally:
                end_of_run(a, st, plist, live, lock,
                           LV.stopped_words('it was stopped'))
            signal.signal(sig, signal.SIG_DFL)
            os.kill(os.getpid(), sig)
        for s in (signal.SIGINT, signal.SIGTERM):
            signal.signal(s, stopped)

        if a.lamp_sweep:
            an.up()
            rows = st.lamp_sweep()
        else:
            rows = st.run()
    except BaseException as e:
        # A CRASHED RUNNER ENDS THE RUN; IT DOES NOT RESTART AND IT DOES NOT
        # LIE (PW 2026-09-27). Until S127 an exception here skipped the report
        # entirely and left the last instruction on the glass with the rails
        # up, so the screen sat in test mode showing a patch nobody was going
        # to make. The traceback still goes to the log -- an engineer needs it
        # -- but the unit is safe and the screen says so first.
        stopped_why = 'the test program stopped'
        if st is not None:
            try:
                st.teardown()
            except Exception:
                pass
            rows = st.rows_out
        else:
            # Nothing was built, so there is nothing to tear down -- but the
            # rails may already be up from the automatic set that handed this
            # station the unit, and a screen that says a test is running when
            # none is would be worse than a blank one.
            try:
                Analog(enabled=not a.no_analog,
                       log=glass.progress, own_rails=True).down()
            except Exception:
                pass
        end_of_run(a, st, plist, live, lock, LV.stopped_words(stopped_why))
        raise
    finally:
        try:
            if st is not None:
                st.teardown()
        except Exception:
            pass
    end_of_run(a, st, plist, live, lock)
    return 0


def end_of_run(a, st, plist, live, lock, stopped=''):
    """Everything that has to be true once the walk is over, however it ended.

    Runs once, on every way out, and never raises: this is the code that makes
    the difference between a unit handed back safe with a report and a unit
    left on the bench with a stack trace.
    """
    if getattr(live, '_s127_ended', False):
        return
    live._s127_ended = True
    rows = st.rows_out if st is not None else []
    try:
        out = a.out or os.path.join(a.dir, 'patch-results.csv')
        print('wrote %s' % merge_results(out, rows), flush=True)
    except Exception as e:
        print('the results could not be written: %s' % e, flush=True)
    if stopped:
        try:
            live.set(state=LV.PAUSED, instruction='', lead_line='', extra='',
                     status='%s %s' % (stopped, LV.RESTART_WORDS),
                     action='',
                     passed=getattr(st, 'passed', 0),
                     failed=getattr(st, 'failed', 0),
                     failures=list(getattr(st, 'failures', [])))
        except Exception:
            pass
    for lk in (lock, getattr(lock, 'partner', None)):
        try:
            if lk is not None:
                lk.release()
        except Exception:
            pass
    # 1.2(b)'s TABLE, written on every way out and never graded. It is the
    # whole deliverable of a trials run, so it must survive a PAUSE, a signal
    # and an exception as the results CSV does.
    try:
        res = list(getattr(st, 'click_results', []) or [])
        if res:
            click_table(res)
            if a.click_out:
                with open(a.click_out, 'w', encoding='utf-8') as fh:
                    click_table(res, out=fh)
                print('wrote %s' % a.click_out, flush=True)
    except Exception as e:
        print('the click trial table could not be written: %s' % e, flush=True)
    if st is not None and not stopped and not getattr(a, 'lamp_sweep', False):
        try:
            print_time_table(time_table(st, plist, a.hand), a.hand, plist,
                             press_s=0.0 if a.auto_advance else a.press)
        except Exception:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--list-dir', help='where patch-paths.csv lives')
    ap.add_argument('--list', action='store_true', help='print the plan, stop')
    ap.add_argument('--simulate', action='store_true',
                    help='walk the whole pass with no unit')
    ap.add_argument('--run', action='store_true',
                    help='THE FACTORY TEST. Whatever START the operator '
                         'presses is the whole ruled sequence -- setup pages, '
                         'panel loops, the analog patch walk -- so --run hands '
                         'over to RUN ALL (PW 2026-09-27). Use --patch-only '
                         'for this station on its own')
    ap.add_argument('--guard', action='store_true',
                    help='one check, no run: if the lock names a pid that is '
                         'gone and the screen has stopped beating, say so on '
                         'the glass and put the rails down. Idempotent, and it '
                         'never touches a live run')
    ap.add_argument('--stale-after', type=float, default=15.0,
                    help='seconds without a heartbeat before --guard calls a '
                         'run gone (never below the screen\'s own %.0f s)'
                         % LV.LIVE_STALE_S)
    ap.add_argument('--patch-only', action='store_true',
                    help='the analog patch station ALONE, with no setup pages '
                         'and no panel loops: a development and bench entry, '
                         'never what the factory screen launches')
    ap.add_argument('--block', action='append',
                    help='only this lead (K1..K5); repeatable')
    ap.add_argument('--fault', action='append',
                    help='inject a fault in --simulate: dead:<in>, '
                         'mispatch:<in>, swap:<jack>, nonull:<jack>, '
                         'edge:<in>, gain:<in>:<element 1-6>')
    ap.add_argument('--hand', type=float, default=5.0,
                    help='seconds per hand move, for the projection')
    ap.add_argument('--press', type=float, default=PRESS_S,
                    help='seconds to reach for ENTER after the lead is in')
    ap.add_argument('--out', help='write the per-path results here')
    ap.add_argument('--strings',
                    help='dump every operator-facing string, for --check-md')
    ap.add_argument('--dir', default=GLASS_DIR,
                    help='the glass directory (--run)')
    ap.add_argument('--live', metavar='DIR',
                    help='write the factory screen\'s live status file here '
                         '(default: the glass directory)')
    ap.add_argument('--no-live', action='store_true',
                    help='do not drive the factory screen at all')
    ap.add_argument('--no-pre-arm', dest='prearm', action='store_false',
                    help='wait for ENTER before taking any reading, as the '
                         'station did before PW\'s ruling of 2026-09-27. For '
                         'a before/after timing run')
    ap.add_argument('--auto-advance', dest='auto_advance',
                    action='store_true', default=True,
                    help='end each step on the signal, not on a press. This is '
                         'what the station does (PW 2026-09-28); the flag is '
                         'kept so a script that passes it still works')
    ap.add_argument('--confirm-enter', dest='auto_advance',
                    action='store_false',
                    help='the 2026-09-26 loop: the operator plugs the lead in '
                         'and then presses ENTER. Superseded, kept for a '
                         'before/after timing run')
    ap.add_argument('--no-keyboard', action='store_true',
                    help='do not read the Enter key off a USB keyboard')
    ap.add_argument('--own-rails', action='store_true',
                    help='lower AN_EN at the handback even if this run did '
                         'not raise it. RUN ALL passes it: the self-test '
                         'raises the rails after the last DSP boot and keeps '
                         'them up (--al1-keep-rails), so this station is what '
                         'closes the session')
    ap.add_argument('--no-analog', action='store_true',
                    help='do not touch the rails or the mic-pre chain: for a '
                         'run on a unit somebody else has already set up')
    ap.add_argument('--screens', metavar='DIR',
                    help='walk the factory screen through every state it can '
                         'reach, with no unit and no lead, so each one can be '
                         'photographed')
    ap.add_argument('--dwell', type=float, default=2.5,
                    help='seconds to hold each screen in --screens')
    ap.add_argument('--capture-period', type=float, default=1.3,
                    help='the display\'s own capture cadence, in seconds: a '
                         'frame is only accepted once a whole period has '
                         'passed since the screen changed')
    ap.add_argument('--capture', default='/home/app/selftest/s105-wizard.png',
                    help='the display\'s own capture file, copied out after '
                         'each screen in --screens')
    ap.add_argument('--lamp-sweep', action='store_true',
                    help='1.2(a): PW\'s two-LED phantom lamp fixture, moved '
                         'input to input as a SEPARATE sweep. Applies phantom '
                         '-- through the shunt-first sequence on every '
                         'transition -- and measures nothing: the judgement is '
                         'the operator\'s eye on two LEDs')
    ap.add_argument('--click-trials', action='store_true',
                    help='1.2(b): inside the EIN step, with the 150 ohm plug '
                         'already in, capture the phantom-switching transient '
                         'on the lane -- both directions, shunt engaged and '
                         'released. INFORMATIONAL: it never grades, and it is '
                         'the one place that moves phantom without the '
                         'shunt-first sequence, which is what it measures. OFF '
                         'by default')
    ap.add_argument('--trial-inputs',
                    help='--click-trials: only these inputs, comma-separated '
                         'panel names ("MIC 3,MIC 7"). The default is every '
                         'input whose EIN reading came back')
    ap.add_argument('--mj-detect-input',
                    help='2.2: which mini-jack patch carries the jack-switch '
                         'detect row ("MINI-JACK 1"). The default is the FIRST '
                         'mini-jack patch in the list, so the next patch\'s own '
                         'prompt is what takes the plug out again')
    ap.add_argument('--click-out',
                    help='--click-trials: write the trial table here as well '
                         'as printing it')
    ap.add_argument('--symdir', default=FACTORY_TEST_PAIR_DIR)
    ap.add_argument('--back-end', default='auto', choices=('auto', 'harness'))
    ap.add_argument('--stdin', action='store_true')
    ap.add_argument('--verbose', action='store_true')
    a = ap.parse_args(argv)
    plist = PatchList(find_list_dir(a.list_dir))
    if a.list:
        return cmd_list(plist)
    if a.strings and not (a.simulate or a.run):
        return cmd_strings(a, plist)
    if a.screens:
        return cmd_screens(a, plist)
    if a.simulate:
        return cmd_simulate(a, plist)
    if a.guard:
        return cmd_guard(a)
    # 1.2(a) IS ITS OWN ENTRY AND NEVER THE FACTORY START'S (PW: a SEPARATE
    # sweep). It applies phantom, so it cannot be something a worker reaches by
    # pressing START before PW has signed it off at the bench.
    if a.lamp_sweep:
        if a.run and not a.patch_only:
            ap.error('--lamp-sweep is a separate sweep and is not what the '
                     'factory START runs: use --patch-only --lamp-sweep')
        return cmd_run(a, plist)
    if a.run and not a.patch_only:
        return cmd_factory(a)
    if a.run or a.patch_only:
        return cmd_run(a, plist)
    ap.error('one of --list, --simulate, --screens, --run or --lamp-sweep')


if __name__ == '__main__':
    sys.exit(main())
