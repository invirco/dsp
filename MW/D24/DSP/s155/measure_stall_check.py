#!/usr/bin/env python3
"""measure_stall_check.py -- S155 item 3: `Unit.measure()`'s two wait-for-
counter loops, bounded.

Hub dispatch 2026-09-30 17:36Z, item 3: "`Unit.measure()` waits on the
TEST_MEAS window counter with no timeout; with stale symbols ... it hung for
ever with the glass on 'working - please wait'". `e97cd357` fixed the stale
symbol map that caused it (the station now reads the booted pair); this
proves the OTHER half -- that a frozen counter, from whatever cause, no
longer hangs the loop, it raises `d24_patch.MeasureStalled`, a named error
the station's existing exception reporting (`AutoPhase._go` and its like)
already turns into a line on the glass instead of silence.

No unit, no bus: `Unit.measure()` is called directly against a fake chip
object that stands in for the diag link, with `PT.Unit._seq` replaced by a
counter the test controls -- the two loops are exercised exactly as written,
nothing about them is re-implemented here.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, '..', '..', '..', '..', 'tools', 'pi')
sys.path.insert(0, TOOLS)
import d24_patch as PT       # noqa: E402

FAILS = []


def check(name, cond, detail=''):
    print('%-4s %s%s' % ('ok' if cond else 'FAIL', name,
                         (': ' + detail) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


class FakePeek:
    def peek(self, addr):
        return 0


class FakeScope:
    """Just enough of `dsp4_scope.Scope` for `measure()` to read past the
    settle loop: `sym` resolves the three symbols it peeks, `d.peek` never
    raises and never returns 0xFFFFFFFF, so `peek_settled` settles on its
    first try."""

    def __init__(self):
        self.sym = {'_osc_k_C1_TEST_OSC': 0, '_meas_a_C1_TEST_MEAS': 0,
                    '_meas_b_C1_TEST_MEAS': 0}
        self.d = FakePeek()


class FakeUnit:
    """`Unit.measure`'s real body, called unbound against a stand-in for
    everything it touches OTHER than the counter -- the thing this test
    varies."""

    def __init__(self, seq_fn):
        self.symdir = 'FAKE-SYMDIR-s155'
        self._scope = FakeScope()
        self._seq_fn = seq_fn

    def chip(self, n):
        return self._scope

    def _seq(self):
        return self._seq_fn()

    def read(self, name):
        return 0

    def readf(self, name):
        return 0.0


measure = PT.Unit.measure


def run(seq_fn, **kw):
    u = FakeUnit(seq_fn)
    return measure(u, None, 0.0, **kw)


# ---------------------------------------------------------------------------
# 1. a counter that never moves at all -- the S148/e97cd357 case, a stale
#    symbol map pointing `_seq()` at a word that is never written
# ---------------------------------------------------------------------------
def test_frozen_at_zero_raises_in_the_settle_loop():
    PT.CLOCK = PT.VirtualClock()
    calls = [0]

    def frozen():
        calls[0] += 1
        return 0
    try:
        run(frozen, windows=2, settle=4)
        check('a counter frozen from the first call raises', False,
              'measure() returned instead of raising')
    except PT.MeasureStalled as e:
        check('a counter frozen from the first call raises MeasureStalled',
              True)
        check('... naming the settle loop', 'settling' in str(e), str(e))
        check('... and MEASURE_STALL_S is stated, not invented here',
              '%.1f' % PT.MEASURE_STALL_S in str(e), str(e))
    check('it did not spin forever doing it -- bounded polls',
          calls[0] < 10000, repr(calls[0]))
    check('... and it gave up within the stated bound, not early or late',
          abs(PT.CLOCK.t - PT.MEASURE_STALL_S) < PT.WIN_S,
          '%.3f s vs %.3f s' % (PT.CLOCK.t, PT.MEASURE_STALL_S))


# ---------------------------------------------------------------------------
# 2. the counter settles, then freezes -- the read-collection loop's own bound
# ---------------------------------------------------------------------------
def test_frozen_after_settling_raises_in_the_read_loop():
    PT.CLOCK = PT.VirtualClock()
    n = [0]

    def settle_then_freeze():
        if n[0] < 8:
            n[0] += 1
        return n[0]
    try:
        run(settle_then_freeze, windows=3, settle=4)
        check('a counter that settles and then freezes still raises', False,
              'measure() returned instead of raising')
    except PT.MeasureStalled as e:
        check('a counter that settles and then freezes raises MeasureStalled',
              True)
        check('... naming the read loop', 'reading' in str(e), str(e))


# ---------------------------------------------------------------------------
# 3. the control: a counter that keeps moving never raises, and the call
#    returns in bounded virtual time -- the fix must not cost a healthy run
#    anything
# ---------------------------------------------------------------------------
def test_a_live_counter_never_raises():
    PT.CLOCK = PT.VirtualClock()
    # A REAL counter turns over once per WIN_S of elapsed time, not once per
    # `_seq()` call -- tying it to the virtual clock is what makes this the
    # honest control: a call that lands inside the same window as the last
    # reads back unchanged, exactly as the real word would.
    def live():
        return int(PT.now() / PT.WIN_S)
    out = run(live, windows=2, settle=4)
    check('a counter that keeps moving returns normally', 'rms' in out,
          repr(out))
    check('... in well under the stall bound',
          PT.CLOCK.t < PT.MEASURE_STALL_S, '%.3f s' % PT.CLOCK.t)


def main():
    for fn in (test_frozen_at_zero_raises_in_the_settle_loop,
               test_frozen_after_settling_raises_in_the_read_loop,
               test_a_live_counter_never_raises):
        print('-- %s' % fn.__name__)
        fn()
    print()
    if FAILS:
        print('%d check(s) FAILED: %s' % (len(FAILS), ', '.join(FAILS)))
        return 1
    print('all checks passed -- no unit, no bus, no serial port')
    return 0


if __name__ == '__main__':
    sys.exit(main())
