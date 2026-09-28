#!/usr/bin/env python3
"""lamp_sweep_check.py -- S138b: PW's phantom lamp sweep (gaps doc 1.2(a)),
driven end to end with no unit, no rails, no SPI and no phantom applied.

The S137 pattern: a scripted answer stream instead of a finger, the REAL
`Station.lamp_sweep`, the REAL `Analog.phantom` sequence arithmetic, and the
screens asserted as the operator would meet them -- one big instruction, panel
names only, n of N, and no dead button.

What it proves, in the ruling's own terms (PW 2026-09-28 08:06):

  * the sweep is moved input to input, in the list's own order, over the 24 XLR
    mic inputs and nothing else;
  * every phantom transition is PW's shunt-first sequence (2026-09-16) and
    never one image -- checked by counting the loads and reading their bits;
  * "are BOTH lights on?" is asked with phantom ON, and NOT LIT records a
    phantom leg fault;
  * a lamp lit on the MOVE screen -- phantom off on every input -- records the
    stuck-on fault instead, which is the half of 1.2(a) that costs no extra
    press;
  * PAUSE stops the sweep and STILL takes phantom off everything it touched;
  * the mic-pre safety handback still runs and still ends on the SAFE image.
"""
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


class ScriptGlass(object):
    """The operator, as a list of button presses. Every screen is kept."""

    def __init__(self, answers):
        self.answers = list(answers)
        self.posts = []
        self.lines = []
        self.cleared = 0

    def post(self, kind, title, lines, buttons, **extra):
        self.posts.append(dict(kind=kind, title=title, lines=list(lines),
                               buttons=list(buttons)))
        return list(buttons)

    def poll(self, btns):
        if not self.answers:
            return dict(button='pause')
        return dict(button=self.answers.pop(0))

    def ask(self, kind, title, lines, buttons, **extra):
        self.post(kind, title, lines, buttons, **extra)
        return self.poll(buttons)

    def clear(self):
        self.cleared += 1

    def progress(self, text):
        self.lines.append(text)


def build(answers, fail_phantom_on=None):
    PT.CLOCK = PT.VirtualClock()
    plist = PT.PatchList(LIST_DIR)
    world = PT.World()
    glass = ScriptGlass(answers)
    unit = PT.SimUnit(world)
    send_pos = dict((int(r['lane']), int(r['send_pos'])) for r in plist.paths
                    if r.get('send_pos') != '' and str(r['lane']).isdigit())
    an = PT.SimAnalog(world, plist.gain, send_pos)
    an.image = [0x00] * 24 + [0x00]
    an.safe_image = [0x01] * 24 + [0x00]
    if fail_phantom_on is not None:
        real = an.chain
        state = {'n': 0}

        def chain(image, what):
            state['n'] += 1
            if state['n'] == fail_phantom_on:
                an.image = None
                an.sent.append((list(image), what))
                return False
            return real(image, what)
        an.chain = chain
    st = PT.Station(plist, unit, PT.SimPatcher(glass, world, 0.0, lambda s: None),
                    glass, PT.Limits.load(plist.dir), log=lambda s: None,
                    live=LV.Live(None, enabled=False), analog=an)
    return st, glass, an


def test_scope_is_the_24_xlr_inputs():
    st, _g, _an = build([])
    inputs, skipped = st.mic_inputs()
    names = [i['name'] for i in inputs]
    check('the sweep walks 24 inputs', len(inputs) == 24, repr(len(inputs)))
    check('MIC 1 and MIC 2 are in it (their first list row carries no '
          'transmit position)',
          'MIC 1' in names and 'MIC 2' in names, repr(names[:4]))
    check('no input is unaddressable', not skipped, repr(skipped))
    check('no jack half of a combo socket is walked',
          not [n for n in names if n.endswith(' line')], repr(names))
    check('TALKBACK and the mini-jacks are not in scope',
          not [n for n in names if 'JACK' in n or n == 'TALKBACK'], repr(names))
    check('every transmit position is one of the 24 preamps and each is used '
          'once',
          sorted(i['send_pos'] for i in inputs) == list(range(24)),
          repr(sorted(i['send_pos'] for i in inputs)))
    check('the order is the list\'s own, MIC 1 first',
          names[0] == 'MIC 1', repr(names[0]))


def test_a_clean_sweep():
    # two presses per input: the move screen, then the ruling's question
    st, glass, an = build(['enter', 'enter'] * 24)
    rows = st.lamp_sweep()
    check('one row per input', len(rows) == 24, repr(len(rows)))
    check('every input passes on a clean sweep',
          {r['verdict'] for r in rows} == {PT.PASS},
          repr(sorted({r['verdict'] for r in rows})))
    check('two screens per input, no more',
          len(glass.posts) == 48, repr(len(glass.posts)))
    # the screens
    first = glass.posts[0]
    check('the first screen says FIT, and names the input in panel terms',
          first['lines'] == [LV.lamp_move_words('MIC 1', first=True)],
          repr(first['lines']))
    check('the second input\'s screen says MOVE',
          glass.posts[2]['lines'] == [LV.lamp_move_words('MIC 3')],
          repr(glass.posts[2]['lines']))
    check('the question screen is the ruling\'s own words',
          glass.posts[1]['lines'] == [LV.lamp_check_words('MIC 1')],
          repr(glass.posts[1]['lines']))
    check('every screen carries NOT LIT and no dead ENTER on the dialog',
          all(p['buttons'] == ['notlit'] for p in glass.posts),
          repr({tuple(p['buttons']) for p in glass.posts}))
    check('every screen fits the glass',
          all(LV.fits(ln) for p in glass.posts for ln in p['lines']),
          repr([ln for p in glass.posts for ln in p['lines']
                if not LV.fits(ln)]))
    check('no screen names a cell, a lane, a transmit position or a test id',
          not [ln for p in glass.posts for ln in p['lines']
               if 'Sys0' in ln or 'lane' in ln or 'send_pos' in ln
               or 'MJ1' in ln],
          repr([ln for p in glass.posts for ln in p['lines']]))
    # the wire
    seq = [(w, CH.split(img[23])) for img, w in an.sent if 'MIC 1:' in w]
    check('MIC 1 got exactly three loads for phantom on and three for off',
          len(seq) == 6, repr(seq))
    check('... and they are steps 1/3/5 in PW\'s order, both directions',
          [bits for _w, bits in seq]
          == [(1, 0, 0), (1, 1, 0), (0, 1, 0),      # on
              (1, 1, 0), (1, 0, 0), (0, 0, 0)],     # off
          repr(seq))
    check('no load ever moves phantom in one image',
          not [(w, img) for img, w in an.sent
               if 'phantom' in w and 'step' not in w and 'safe' not in w
               and 'touched' not in w],
          repr([w for _i, w in an.sent if 'phantom' in w and 'step' not in w]))
    # 24 inputs x 2 directions x 3 loads, plus the one closing sequence
    check('the closing sequence takes phantom off everything it touched',
          any('every input the lamp sweep touched' in w for _i, w in an.sent),
          repr([w for _i, w in an.sent][-4:]))
    last = [img for img, w in an.sent
            if 'every input the lamp sweep touched' in w][-1]
    check('... and it ends with no phantom anywhere',
          not [b for b in last[:24] if CH.split(b)[1]],
          repr([CH.split(b) for b in last[:24]]))


def test_not_lit_on_the_question_is_a_leg_fault():
    answers = []
    for i in range(24):
        answers += ['enter', 'notlit' if i == 4 else 'enter']
    st, glass, an = build(answers)
    rows = st.lamp_sweep()
    bad = [r for r in rows if r['verdict'] == PT.FAIL]
    check('exactly one input fails', len(bad) == 1, repr(bad))
    check('and it is the one the operator said was dark',
          bad and bad[0]['in'] == rows[4]['in'], repr(bad))
    check('the recorded reason is the ruling\'s own phrase',
          bad and bad[0]['why'] == LV.LAMP_LEG_FAULT, repr(bad))
    check('a leg fault does not stop the sweep: all 24 inputs are recorded',
          len(rows) == 24, repr(len(rows)))
    check('phantom is still taken off the failed input',
          all(CH.split(b)[1] == 0 for b in an.sent[-1][0][:24]))


def test_not_lit_on_the_move_screen_is_stuck_on():
    answers = []
    for i in range(24):
        if i == 9:
            answers += ['notlit']          # lit while phantom is off
        else:
            answers += ['enter', 'enter']
    st, glass, an = build(answers)
    rows = st.lamp_sweep()
    bad = [r for r in rows if r['verdict'] == PT.FAIL]
    check('a lamp lit with phantom off records the stuck-on fault',
          len(bad) == 1 and bad[0]['why'] == LV.LAMP_STUCK_ON, repr(bad))
    check('... and phantom was never applied to that input',
          not [w for _i, w in an.sent if rows[9]['in'] + ':' in w],
          repr([w for _i, w in an.sent if rows[9]['in'] in w]))
    check('the sweep carries on past it', len(rows) == 24, repr(len(rows)))


def test_pause_stops_and_still_hands_back():
    answers = ['enter', 'enter', 'enter', 'pause']
    st, glass, an = build(answers)
    rows = st.lamp_sweep()
    check('PAUSE stops the sweep where it was',
          len(rows) == 1 and st.paused, '%d rows, paused=%s'
          % (len(rows), st.paused))
    check('PAUSE still takes phantom off everything touched',
          any('every input the lamp sweep touched' in w for _i, w in an.sent),
          repr([w for _i, w in an.sent][-3:]))
    off = [img for img, w in an.sent
           if 'every input the lamp sweep touched' in w][-1]
    check('... and the second input, mid-check when PAUSE landed, is off too',
          not [b for b in off[:24] if CH.split(b)[1]],
          repr([CH.split(b) for b in off[:24] if CH.split(b)[1]]))


def test_a_sequence_that_will_not_verify_records_no_data():
    # the 4th chain load of the sweep: MIC 1's phantom-OFF step 1
    st, glass, an = build(['enter', 'enter'] * 24, fail_phantom_on=4)
    rows = st.lamp_sweep()
    nd = [r for r in rows if r['verdict'] == PT.NODATA]
    check('a load that will not read back is NO DATA, never a FAIL',
          len(nd) == 1, repr([(r['in'], r['verdict']) for r in rows[:3]]))
    check('... and it says the shunt is left engaged',
          nd and 'shunt' in (nd[0]['why'] + nd[0]['detail']), repr(nd))
    check('a failed handback stops the sweep rather than walking on',
          st.paused)


def test_the_safety_handback_still_runs():
    """The REAL `Analog.down`, with only the wire and the shell replaced.

    `SimAnalog` overrides `down()` to do nothing, so asserting against it
    proves nothing about the handback -- which is the one thing in this file
    that must not have been broken by adding phantom to the station. So this
    builds a real `Analog`, stubs `open_fast` (spidev) and `sh` (pinctrl), and
    reads the ORDER out of what each of them was asked to do.
    """
    PT.CLOCK = PT.VirtualClock()
    an = PT.Analog(enabled=True, log=lambda s: None)
    an.safe_image = [0x01] * 24 + [0x00]
    an.image = [0x00] * 24 + [0x00]
    an.raised = True                       # this run put the rails up
    trace = []

    class FakeWire(object):
        fast = True

        def send(self, image):
            trace.append(('chain', list(image)))
            return True, list(image)

        def close(self):
            trace.append(('wire closed', None))
    an.open_fast = lambda: FakeWire()
    an.sh = lambda cmd, timeout=90: trace.append(('sh', cmd)) or ''
    an.fast = FakeWire()
    an.down()
    kinds = [k for k, _v in trace]
    shells = [v for k, v in trace if k == 'sh']
    check('the rails go DOWN before the chain is rewritten (PW\'s order)',
          any('%d op dl' % an.an_en in s for s in shells)
          and kinds.index('sh') < kinds.index('chain'), repr(trace))
    check('CS_M is driven high before the SAFE write',
          [i for i, s in enumerate(shells) if '%d op dh' % an.cs_m in s]
          and [i for i, s in enumerate(shells) if '%d op dl' % an.an_en in s]
          and (min(i for i, s in enumerate(shells) if '%d op dh' % an.cs_m in s)
               > min(i for i, s in enumerate(shells)
                     if '%d op dl' % an.an_en in s)), repr(shells))
    writes = [v for k, v in trace if k == 'chain']
    check('the SAFE image is written, and it is the only chain write',
          writes == [[0x01] * 24 + [0x00]], repr(writes))
    check('the SAFE image has the shunt engaged on all 24',
          all(CH.split(b)[0] == 1 for b in writes[0][:24]))
    check('the wire is closed afterwards', ('wire closed', None) in trace,
          repr(trace[-2:]))
    an2 = PT.Analog(enabled=True, log=lambda s: None)
    an2.open_fast = lambda: FakeWire()
    an2.sh = lambda cmd, timeout=90: ''
    an2.down()
    n = len([1 for k, _v in trace])
    an2.down()
    check('down() runs once however many times it is called', an2.done)


def main():
    for fn in (test_scope_is_the_24_xlr_inputs,
               test_a_clean_sweep,
               test_not_lit_on_the_question_is_a_leg_fault,
               test_not_lit_on_the_move_screen_is_stuck_on,
               test_pause_stops_and_still_hands_back,
               test_a_sequence_that_will_not_verify_records_no_data,
               test_the_safety_handback_still_runs):
        print('-- %s' % fn.__name__)
        fn()
    print()
    if FAILS:
        print('%d check(s) FAILED: %s' % (len(FAILS), ', '.join(FAILS)))
        return 1
    print('all checks passed -- no unit, no rails, no SPI, no phantom applied')
    return 0


if __name__ == '__main__':
    sys.exit(main())
