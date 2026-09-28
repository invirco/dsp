#!/usr/bin/env python3
"""click_trials_check.py -- S138b: the click-and-shunt trials (gaps doc 1.2(b)),
proved off the bench. No SPI, no unit, no phantom, no 150 ohm plug.

The trials are what PW reads before signing a click limit, so the two things
that have to be right are the ARITHMETIC of the table and the fact that the
table is never a verdict. Both are checked here, plus the wire:

  * `click_metrics` on a synthetic capture whose answer is known by
    construction -- including the one piece of arithmetic that is easy to get
    wrong and impossible to see afterwards: the strip meter's own 6.52 dB/s
    decay is taken back OUT of the duration, so a capture that is nothing but
    the meter draining reports a residual of ~0 and not 767 ms of "ringing";
  * the four trials, and that the two shunt arms differ ONLY in the shunt bit;
  * that phantom is moved by ONE image inside a trial -- which is the
    deliberate exception to PW's shunt-first rule, and the thing being measured
    -- and that the handback afterwards goes back through the sequence;
  * that NOTHING in the whole path produces a PASS, a FAIL or a limit;
  * that the trials are OFF unless asked for, and skip a channel whose EIN
    reading did not come back.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, '..', '..', '..', '..', 'tools', 'pi')
sys.path.insert(0, TOOLS)
os.environ.setdefault('MATRIX_ADDR_HOME', os.path.join(HERE, 'fixtures'))
import d24_chain as CH      # noqa: E402
import d24_live as LV       # noqa: E402
import d24_patch as PT      # noqa: E402

LIST_DIR = os.path.join(HERE, '..', 's121')
FAILS = []


def check(name, cond, detail=''):
    print('%-4s %s%s' % ('ok' if cond else 'FAIL', name,
                         (': ' + detail) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


# ---------------------------------------------------------------------------
# The arithmetic
# ---------------------------------------------------------------------------
def capture(floor, peak, hold_s, pre_s=None, post_s=None, dt=0.005):
    """A capture the way the meter would give one: `hold_s` at `peak`, then the
    meter's own decay back down to the floor."""
    pre_s = PT.CLICK_PRE_S if pre_s is None else pre_s
    post_s = PT.CLICK_POST_S if post_s is None else post_s
    ser = []
    t = 0.0
    while t < pre_s:
        ser.append((t, floor))
        t += dt
    t_act = t
    while t < pre_s + post_s:
        since = t - t_act
        v = peak if since <= hold_s else max(
            floor, peak - PT.METER_DECAY_DB_S * (since - hold_s))
        ser.append((t, v))
        t += dt
    return dict(t_act_s=t_act, series=ser, pre_s=pre_s, post_s=post_s)


def test_metrics_on_a_pure_meter_tail():
    """A capture that is ONLY the latch draining: no real transient at all."""
    st = object.__new__(PT.Station)
    m = PT.Station.click_metrics(st, capture(-96.0, -85.0, 0.0))
    check('the floor is the median of the pre-samples',
          abs(m['floor_dbfs'] + 96.0) < 1e-9, repr(m['floor_dbfs']))
    check('the peak is the highest post sample',
          abs(m['peak_dbfs'] + 85.0) < 1e-9, repr(m['peak_dbfs']))
    check('the peak is found at the toggle', abs(m['t_peak_ms']) < 6.0,
          repr(m['t_peak_ms']))
    want = 1000.0 * (85.0 - 90.0) / -PT.METER_DECAY_DB_S   # (peak - thr)/decay
    check('above_floor_ms is the meter draining to floor+6 dB',
          abs(m['above_floor_ms'] - want) < 10.0,
          '%r vs %r' % (m['above_floor_ms'], want))
    check('decay_only_ms accounts for all of it',
          abs(m['decay_only_ms'] - want) < 1.0,
          '%r vs %r' % (m['decay_only_ms'], want))
    check('so the RESIDUAL is ~0: the instrument, not the unit',
          m['residual_ms'] < 12.0, repr(m['residual_ms']))
    check('energy is reported as a number', isinstance(m['energy_db_s'], float),
          repr(m['energy_db_s']))
    check('the poll cadence is reported',
          abs(m['poll_ms_mean'] - 5.0) < 0.5 and m['polls'] > 200,
          repr((m['polls'], m['poll_ms_mean'])))


def test_metrics_on_a_real_transient():
    """400 ms held at the peak, then the same drain. The residual must be the
    400 ms and not the 400 + the drain."""
    st = object.__new__(PT.Station)
    m = PT.Station.click_metrics(st, capture(-96.0, -85.0, 0.400))
    check('a held transient shows up in the residual',
          abs(m['residual_ms'] - 400.0) < 15.0, repr(m['residual_ms']))
    check('... and above_floor_ms is the residual PLUS the meter tail',
          abs(m['above_floor_ms'] - (400.0 + m['decay_only_ms'])) < 15.0,
          repr((m['above_floor_ms'], m['decay_only_ms'])))
    check('a capture that finished is not flagged truncated',
          m['truncated'] is False, repr(m['truncated']))
    # A LOUD CLICK OUTLASTS THE WINDOW, AND THAT HAS TO SHOW. At 6.52 dB/s the
    # meter takes 3.07 s to drain from -70 dBFS to 6 dB over a -96 dBFS floor,
    # which is longer than CLICK_POST_S. Before `truncated` existed this case
    # reported residual_ms = 0.0 -- "no ringing at all" -- about the loudest
    # click in the set.
    louder = PT.Station.click_metrics(st, capture(-96.0, -70.0, 0.400))
    check('a click still ringing when the capture ends is flagged truncated',
          louder['truncated'] is True, repr(louder['truncated']))
    check('... and reports NO residual rather than a 0 that reads as silence',
          louder['residual_ms'] is None, repr(louder['residual_ms']))
    check('... while still reporting the peak it did see',
          abs(louder['peak_dbfs'] + 70.0) < 1e-9, repr(louder['peak_dbfs']))
    check('... and above_floor_ms as the lower bound it is (the whole window)',
          abs(louder['above_floor_ms'] - 1000.0 * PT.CLICK_POST_S) < 20.0,
          repr(louder['above_floor_ms']))
    check('... and its energy is higher than the quiet one',
          louder['energy_db_s'] > m['energy_db_s'],
          repr((louder['energy_db_s'], m['energy_db_s'])))


def test_metrics_on_a_silent_capture():
    st = object.__new__(PT.Station)
    m = PT.Station.click_metrics(st, capture(-96.0, -96.0, 0.0))
    check('nothing above the floor reports zeros, not None',
          (m['above_floor_ms'], m['residual_ms']) == (0.0, 0.0), repr(m))
    check('... and no energy figure is invented', m['energy_db_s'] is None,
          repr(m['energy_db_s']))


def test_metrics_never_grade():
    st = object.__new__(PT.Station)
    m = PT.Station.click_metrics(st, capture(-96.0, -20.0, 0.100))
    check('a metrics row carries no verdict, no pass and no limit',
          not [k for k in m
               if k in ('verdict', 'pass', 'fail', 'limit', 'why')],
          repr(sorted(m)))


# ---------------------------------------------------------------------------
# The trials on the wire
# ---------------------------------------------------------------------------
def build():
    PT.CLOCK = PT.VirtualClock()
    plist = PT.PatchList(LIST_DIR)
    world = PT.World()
    glass = PT.SimGlass(lambda s: None)
    unit = PT.SimUnit(world)
    send_pos = dict((int(r['lane']), int(r['send_pos'])) for r in plist.paths
                    if r.get('send_pos') != '' and str(r['lane']).isdigit())
    an = PT.SimAnalog(world, plist.gain, send_pos)
    an.image = PT.CHAIN_NOISE
    an.safe_image = [0x01] * 24 + [0x00]
    st = PT.Station(plist, unit,
                    PT.SimPatcher(glass, world, 0.0, lambda s: None), glass,
                    PT.Limits.load(plist.dir), log=lambda s: None,
                    live=LV.Live(None, enabled=False), analog=an, trials=True)
    # The peek costs time, as it does on the part -- otherwise the virtual
    # clock never advances and `transient`'s own poll loop cannot end.
    hits = {'n': 0}

    def watch(lane):
        PT.nap(0.005)
        hits['n'] += 1
        return -96.0 if hits['n'] % 97 else -60.0
    st.watch = watch
    return st, an


def ein_row(plist):
    for r in plist.paths:
        if r['expect'] == 'noise' and r['in'] == 'MIC 3':
            return r
    raise AssertionError('no EIN row for MIC 3 in the list')


def test_four_trials_and_the_matrix():
    st, an = build()
    r = ein_row(st.L)
    res = st.click_trials(r, {})
    check('four trials on one input', len(res['trials']) == 4,
          repr(len(res['trials'])))
    got = [(t['shunt'], t['to_on']) for t in res['trials']]
    check('both directions with the shunt ENGAGED and with it RELEASED',
          sorted(got) == [(False, False), (False, True),
                          (True, False), (True, True)], repr(got))
    check('every trial carries the whole fixed column set',
          all(all(k in t for k in ('floor_dbfs', 'peak_dbfs', 't_peak_ms',
                                   'above_floor_ms', 'decay_only_ms',
                                   'residual_ms', 'truncated', 'energy_db_s',
                                   'polls', 'poll_ms_mean', 'poll_ms_max'))
              for t in res['trials']), repr(sorted(res['trials'][0])))
    check('no trial carries a verdict',
          not [k for t in res['trials'] for k in t
               if k in ('verdict', 'pass', 'fail', 'limit')],
          repr(sorted(res['trials'][0])))
    check('the input is named in panel terms', res['input'] == 'MIC 3',
          repr(res['input']))


def test_the_two_arms_differ_only_in_the_shunt_bit():
    st, an = build()
    r = ein_row(st.L)
    sp = int(r['send_pos'])
    an.sent = []
    st.click_trials(r, {})
    starts = [(CH.split(img[sp]), w) for img, w in an.sent
              if 'click trial start state' in w]
    check('four start images, one per trial', len(starts) == 4, repr(starts))
    engaged = [bits for bits, w in starts if 'shunt engaged' in w]
    released = [bits for bits, w in starts if 'shunt released' in w]
    check('the engaged arm starts with the shunt bit set',
          all(b[0] == 1 for b in engaged), repr(engaged))
    check('the released arm starts with it clear',
          all(b[0] == 0 for b in released), repr(released))
    check('the gain code is the EIN gain in every arm, untouched',
          {b[2] for bits, _w in starts for b in (bits,)} == {63},
          repr([b[2] for b, _w in starts]))
    toggles = [(CH.split(img[sp]), w) for img, w in an.sent
               if w.startswith('click trial: phantom')]
    check('each trial moves phantom with exactly ONE image',
          len(toggles) == 4, repr(toggles))
    check('... and only the phantom bit moves between the start and the toggle',
          all(s[0] == t[0] and s[2] == t[2] and s[1] != t[1]
              for (s, _a), (t, _b) in zip(starts, toggles)),
          repr(list(zip([s for s, _a in starts], [t for t, _b in toggles]))))


def test_the_handback_goes_back_through_the_sequence():
    st, an = build()
    r = ein_row(st.L)
    sp = int(r['send_pos'])
    an.sent = []
    st.click_trials(r, {})
    tail = [w for _i, w in an.sent][-4:]
    check('the trials end with PW\'s sequence, not a bare image',
          len([w for w in tail if 'step' in w]) == 3, repr(tail))
    check('... and then back to the block\'s own image',
          an.sent[-1][0] == list(PT.CHAIN_NOISE), repr(an.sent[-1]))
    check('phantom is off on that input when the trials end',
          CH.split(an.sent[-1][0][sp])[1] == 0,
          repr(CH.split(an.sent[-1][0][sp])))


def test_a_row_with_no_transmit_position_is_skipped_not_guessed():
    st, an = build()
    r = dict(ein_row(st.L))
    r['send_pos'] = ''
    an.sent = []
    res = st.click_trials(r, {})
    check('no transmit position: no trial and no write at all',
          res['trials'] == [] and res['skipped'] and not an.sent,
          repr((res, len(an.sent))))


def test_the_gate():
    PT.CLOCK = PT.VirtualClock()
    plist = PT.PatchList(LIST_DIR)
    st = PT.Station(plist, PT.SimUnit(PT.World()),
                    PT.SimPatcher(PT.SimGlass(lambda s: None), PT.World(), 0.0,
                                  lambda s: None),
                    PT.SimGlass(lambda s: None), PT.Limits.load(plist.dir),
                    log=lambda s: None)
    check('the trials are OFF unless asked for', st.trials is False)
    check('and no input is named by default', st.trial_only is None)
    st2 = PT.Station(plist, PT.SimUnit(PT.World()),
                     PT.SimPatcher(PT.SimGlass(lambda s: None), PT.World(),
                                   0.0, lambda s: None),
                     PT.SimGlass(lambda s: None), PT.Limits.load(plist.dir),
                     log=lambda s: None, trials=True,
                     trial_only=PT.split_inputs('MIC 3, MIC 7'))
    check('--trial-inputs names the good channels by hand',
          st2.trial_only == {'MIC 3', 'MIC 7'}, repr(st2.trial_only))


def test_the_table():
    st, an = build()
    r = ein_row(st.L)
    res = [st.click_trials(r, {})]
    res.append(dict(input='MIC 9', lane=9, trials=[],
                    skipped='the EIN reading did not come back'))
    buf = io.StringIO()
    PT.click_table(res, out=buf)
    txt = buf.getvalue()
    check('the table carries the instrument note above it',
          'INFORMATIONAL' in txt and '6.52 dB/s' in txt, repr(txt[:120]))
    check('... and says the terminator is fitted and no microphone is',
          '150 ohm terminator' in txt and 'no microphone' in txt)
    check('the header names every fixed column',
          all(c in txt for c in ('input', 'shunt', 'direction', 'peak',
                                 'residual', 'trunc', 'energy', 'poll')),
          repr(txt[:400]))
    check('one line per trial plus the skipped channel',
          len([ln for ln in txt.splitlines() if 'MIC ' in ln]) == 5,
          repr([ln for ln in txt.splitlines() if 'MIC ' in ln]))
    check('the table says PASS and FAIL nowhere',
          'PASS' not in txt and 'FAIL' not in txt, repr(txt))
    check('both shunt states and both directions are named in words',
          all(w in txt for w in ('engaged', 'released', 'off->on', 'on->off')))
    check('the skipped channel keeps its reason in the table',
          'the EIN reading did not come back' in txt)


def main():
    for fn in (test_metrics_on_a_pure_meter_tail,
               test_metrics_on_a_real_transient,
               test_metrics_on_a_silent_capture,
               test_metrics_never_grade,
               test_four_trials_and_the_matrix,
               test_the_two_arms_differ_only_in_the_shunt_bit,
               test_the_handback_goes_back_through_the_sequence,
               test_a_row_with_no_transmit_position_is_skipped_not_guessed,
               test_the_gate,
               test_the_table):
        print('-- %s' % fn.__name__)
        fn()
    print()
    if FAILS:
        print('%d check(s) FAILED: %s' % (len(FAILS), ', '.join(FAILS)))
        return 1
    print('all checks passed -- no SPI, no unit, no phantom, no terminator')
    return 0


if __name__ == '__main__':
    sys.exit(main())
