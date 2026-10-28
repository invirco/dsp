#!/usr/bin/env python3
"""NAMM-D24-6 Q6 desk check: the talkback switch + LEDs (row 92) and the P1
link check (rows 101/129/145, and 58 with the pedal station on). No unit, no
bus, no serial port, no write.

Talkback, against S135 variant B's contract (WRITE = LED mask bit0/bit1,
READ = 1 held / 0 released, both edges):
  * row 92 is a graded loop row on a pack that carries Sys001SwTalk001, and
    stays unreached with the pack's reason on one that does not
  * press + release with each light lit alone = PASS; the lights are written
    1, then 2, then 0 (dark) on the way out
  * a press with no release = FAIL (stuck); NOT LIT = FAIL naming the light;
    nothing at all = NO DATA (firmware precondition); PAUSE = paused
  * the real panel_station grades it after the other rows have passed, and a
    failed step waits for the operator (S157)

P1 link:
  * link_check / link_verdicts on a fake relay: answered, relay only, nothing
  * with the pedal station off nothing changes (rows stay NOT RUN); with it on
    rows 101/129/145 are loop rows and 58 is graded there
  * a whole P1 board pass, unit stubbed: the pedal answering is the go-ahead,
    every link row lands, the pedal rows the link cannot grade say why
"""
import io
import json
import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'pi'))
os.environ.setdefault('MATRIX_ADDR_HOME', os.path.join(
    ROOT, 'MW', 'D24', 'DSP', 's138b', 'fixtures'))
os.environ['D24_UNIT'] = 'MW-D24-2'
import d24_live as LV        # noqa: E402
import d24_runall as RA      # noqa: E402
import d24_pedal as PD       # noqa: E402
import d24_boards as BB      # noqa: E402
PL = RA.PL
RA.LIST_DIR = os.path.join(ROOT, 'MW', 'D24', 'DSP', 's121')
CATALOG = os.path.join(ROOT, 'MW', 'D24', 'DSP', 's164', 'data',
                       'test-catalog-unit.csv')
FAILS = []


def check(name, cond, detail=''):
    print('%-4s %s%s' % ('ok' if cond else 'FAIL', name,
                         (': ' + str(detail)) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


def classified():
    rows, md5 = RA.load_catalog(CATALOG)
    RA.classify(rows)
    return dict((r.num, r) for r in rows), rows, md5


def script(lines):
    path = tempfile.mktemp(prefix='q6-keys-')
    with open(path, 'w') as fh:
        fh.write('\n'.join(lines) + '\n')
    return path


def tb(lines, ticks=None, timeout=0.6):
    bus = PL.InjectedBus(script(lines))
    asked = []

    def ask(n, total):
        asked.append(n)
        seq = list((ticks or {}).get(n, []))
        return lambda: seq.pop(0) if seq else None
    v, note, paused = PL.talkback_check(bus, 'right', ask, timeout=timeout,
                                        log=lambda *_: None)
    return v, note, paused, bus.lights, asked


# -- talkback: classification ---------------------------------------------
by, rows, md5 = classified()
check('fixture pack carries Sys001SwTalk001 (%s)' % PL.SW_TALK,
      PL.SW_TALK is not None)
r92 = by[92]
check('row 92 is a graded loop row on the right panel',
      r92.category == 'manual' and r92.step['kind'] == RA.LOOP
      and r92.step['side'] == 'right', (r92.category, r92.step))
check('row 92 is no longer in the unreached table',
      92 not in PL.UNREACHED['right'])
check('... and its wording names TALKBACK and NOT LIT',
      'TALKBACK' in r92.step['action'] and 'NOT LIT' in r92.step['action'])

# -- talkback: the check itself --------------------------------------------
v, note, paused, lights, asked = tb(['5 swtalk 1', '5 swtalk 0',
                                     '5 swtalk 1', '5 swtalk 0'])
check('press + release with each light lit alone: PASS', v == RA.PASS, note)
check('... each light written alone, then both dark: 1, 2, 0',
      lights == [('swtalk', 1), ('swtalk', 2), ('swtalk', 0)], lights)
check('... the operator is asked twice (n of 2)', asked == [1, 2], asked)
v, note, _p, lights, _a = tb(['5 swtalk 1', '5 swtalk 0', '5 swtalk 1'])
check('second press never released: FAIL, stuck down',
      v == RA.FAIL and 'stuck' in note, note)
check('... and the lights still go dark', lights[-1] == ('swtalk', 0), lights)
v, note, _p, _l, _a = tb(['5 swtalk 1', '5 swtalk 0'], ticks={2: ['notlit']})
check('NOT LIT on the second light: FAIL naming it',
      v == RA.FAIL and 'its other light' in note and 'mask 2' in note, note)
v, note, _p, _l, _a = tb([])
check('nothing transmitted at all: NO DATA, the firmware precondition',
      v == RA.NODATA and 'nothing was transmitted' in note, note)
v, note, _p, _l, _a = tb(['5 swtalk 0', '5 swtalk 0'])
check('releases but never a press: FAIL', v == RA.FAIL and
      'never a press' in note, note)
v, note, paused, _l, _a = tb(['5 swtalk 1'], ticks={1: ['skip']})
check('PAUSE during the row: NO DATA, paused', paused and v == RA.NODATA,
      (v, note))


# -- talkback: the real panel station ---------------------------------------
def right_station(keys, confirm='yes'):
    tmp = tempfile.mkdtemp(prefix='q6-panel-')
    b, rws, m = classified()
    state = RA.State(os.path.join(tmp, 'state.json'), 'Q6-DESK', m)
    for r in rws:
        if r.group == 'M2' and r.num != 92:
            state.put(r.num, RA.PASS, pass_no=1, judged='runner',
                      measured='passed earlier', limit='', evidence='',
                      source='panel loop')
    glass = RA.Glass(os.path.join(tmp, 'runall'))
    live = LV.Live(os.path.join(tmp, 'runall'), run='panel', total=1,
                   enabled=True, confirm=True)
    seen = []
    orig_flush, orig_cmd = LV.Live._flush, LV.Live.command

    def flush(self):
        orig_flush(self)
        seen.append(dict(self.d))

    def command(self):
        if list(self.d.get('buttons') or []) == list(LV.YESNO_BUTTONS):
            return confirm
        return orig_cmd(self)
    LV.Live._flush, LV.Live.command = flush, command
    a = types.SimpleNamespace(inject_keys=script(keys), left_cell='auto',
                              panel_timeout=0.6, random_panel_order=False)
    paused = False
    try:
        RA.panel_station(a, 'M2', rws, state, set(), glass, 2, live=live,
                         keys=None)
    except RA.Paused:
        paused = True
    finally:
        LV.Live._flush, LV.Live.command = orig_flush, orig_cmd
    e = state.row(92) or {}
    shutil.rmtree(tmp, ignore_errors=True)
    return e, seen, paused


e, seen, _p = right_station(['5 swtalk 1', '5 swtalk 0', '5 swtalk 1',
                             '5 swtalk 0'])
check('panel station: row 92 PASS with the other rows already passed',
      e.get('verdict') == RA.PASS, e)
check('... the glass asked for the lit button by name, with NOT LIT',
      any('TALKBACK' in (s.get('instruction') or '') and 'notlit' in
          (s.get('buttons') or []) for s in seen))
e, seen, _p = right_station(['5 swtalk 1'], confirm='yes')
check('panel station: a stuck switch stops on a FAIL screen and YES records '
      'it', e.get('verdict') == RA.FAIL and 'recorded by the operator' in
      (e.get('measured') or '') and any(s.get('banner') == 'FAIL'
                                        for s in seen), e)

# -- the pedal link: fake relay ---------------------------------------------


class FakeRelay(object):
    def __init__(self, relay=True, pedal=True):
        self.relay, self.pedal = relay, pedal
        self.sent, self.opened, self.shut_n = b'', [], 0
        self._rx = b''

    def info(self):
        return 'i H1S4-PDL1 rx=0 tx=0' if self.relay else None

    def open(self, fmt='E', baud=115200):
        self.opened.append(fmt)
        return 'o%s%d' % (fmt, baud)

    def shut(self):
        self.shut_n += 1
        return 'x'

    def drain(self, secs=0.05):
        self._rx = b''
        return b''

    def send(self, data):
        self.sent += data
        if self.pedal and data == b'V':
            self._rx += (b'P1 1.1-s169 uid=0123456789ABCDEF01234567 '
                         b'optr=FFFFFEAA disp=CA by=probe set=auto\n')

    def recv(self, n, timeout):
        out, self._rx = self._rx[:n], self._rx[n:]
        return out

    def close(self):
        pass


fr = FakeRelay()
got = PD.link_check(fr, secs=0.3)
res = PD.link_verdicts(got)
check('pedal answers: relay PASS, pedal PASS, the V line kept',
      res['relay'] == 'PASS' and res['pedal'] == 'PASS'
      and got['v'].startswith('P1 1.1-s169'), (got, res))
check('... asks only V, at 8N1, and closes the relay again',
      fr.sent == b'V' and fr.opened == ['N'] and fr.shut_n == 1,
      (fr.sent, fr.opened, fr.shut_n))
res = PD.link_verdicts(PD.link_check(FakeRelay(pedal=False), secs=0.2))
check('relay answers, pedal silent: pedal FAIL, through-path NO DATA',
      (res['relay'], res['pedal']) == ('NO DATA', 'FAIL'), res)
res = PD.link_verdicts(PD.link_check(FakeRelay(relay=False), secs=0.2))
check('relay silent: through-path FAIL, pedal NO DATA',
      (res['relay'], res['pedal']) == ('FAIL', 'NO DATA'), res)

# -- the pedal station: classification --------------------------------------
check('pedal station off (the factory default): 101/129/145 stay NOT RUN, '
      '58 stays unreached',
      all(by[n].category == 'not-run' for n in (101, 129, 145, 58)))

# -- a whole P1 board pass, stubbed ------------------------------------------
ID = BB.make_id('PEDAL01')
tmp = tempfile.mkdtemp(prefix='q6-p1-')
d = os.path.join(tmp, 'selftest')
os.makedirs(os.path.join(d, 'runall'))
shutil.copy(CATALOG, os.path.join(d, 'test-catalog.csv'))
conf = os.path.join(d, 'board.conf')
with open(conf, 'w') as fh:
    fh.write(BB.conf_text('p1', ID))
saved = dict((k, getattr(RA, k)) for k in
             ('ensure_pair', 'lower_rails', 'run_auto', 'PEDAL_STATION',
              'STATIONS', 'STATION_NAME', 'STATION_NUM', 'STATION_ORDER'))
saved_ge = dict(RA.GRADED_ELSEWHERE)
saved_relay = PD.Relay
RA.ensure_pair = lambda *a, **k: None
RA.lower_rails = lambda *a, **k: None
RA.run_auto = lambda *a, **k: (0.0, [], [])
PD.Relay = lambda *a, **k: FakeRelay()
old_stdin = sys.stdin
sys.stdin = io.StringIO('ack\n' + 'done\n' * 4)
try:
    rc = RA.main(['--dir', d, '--board-conf', conf, '--serial', 'UNIT-1',
                  '--stdin', '--no-power-check', '--no-review'])
finally:
    sys.stdin = old_stdin
    PD.Relay = saved_relay
    pedal_on = RA.PEDAL_STATION
    for k, v in saved.items():
        setattr(RA, k, v)
st = json.load(open(os.path.join(d, 'runall', 'boards', ID, 'state.json')))
check('P1 board: the pedal station is switched on by the profile', pedal_on)
check('P1 board: the link rows 101/129/145 PASS from the pedal\'s answer',
      all(st['rows'][str(n)]['verdict'] == 'PASS' for n in (101, 129, 145)),
      dict((n, st['rows'].get(str(n), {}).get('verdict'))
           for n in (101, 129, 145)))
check('... the left panel\'s through-path (58) PASS from the relay half, and '
      'not overwritten NOT TESTED at the end of the pass',
      st['rows']['58']['verdict'] == 'PASS', st['rows'].get('58'))
check('... the V line is the evidence',
      'P1 1.1-s169' in st['rows']['101'].get('evidence', ''))
check('... footswitches and display (98-100) NOT TESTED with a reason',
      all(st['rows'][str(n)]['verdict'] == 'NOT TESTED'
          and st['rows'][str(n)].get('reason') for n in (98, 99, 100)))
# -- the pedal station on the factory screen (the live path) ----------------
def pedal_live(relay, confirm):
    t = tempfile.mkdtemp(prefix='q6-pedal-')
    b, rws, m = classified()
    state = RA.State(os.path.join(t, 'state.json'), 'Q6-DESK', m)
    glass = RA.Glass(os.path.join(t, 'runall'))
    live = LV.Live(os.path.join(t, 'runall'), run='pedal', total=1,
                   enabled=True, confirm=True)
    seen = []
    orig_flush, orig_cmd = LV.Live._flush, LV.Live.command

    def flush(self):
        orig_flush(self)
        seen.append(dict(self.d))

    def command(self):
        if list(self.d.get('buttons') or []) == list(LV.YESNO_BUTTONS):
            return confirm.pop(0) if confirm else 'yes'
        return orig_cmd(self)
    LV.Live._flush, LV.Live.command = flush, command
    PD.Relay = lambda *a, **k: relay
    RA.PEDAL_POLL_S = 0.05
    a = types.SimpleNamespace(panel_timeout=0.1)
    try:
        got = RA.pedal_station(a, 'M3', rws, state, set(), glass, 1,
                               live=live)
    finally:
        LV.Live._flush, LV.Live.command = orig_flush, orig_cmd
        PD.Relay = saved_relay
    shutil.rmtree(t, ignore_errors=True)
    return got, state, seen


got, state, seen = pedal_live(FakeRelay(), [])
check('factory screen: the pedal answering is the go-ahead, no button '
      'pressed', got == {101: 'PASS', 129: 'PASS', 145: 'PASS', 58: 'PASS'}
      and not any(s.get('banner') == 'FAIL' for s in seen), got)
check('... the screen said to plug the pedal in, with PAUSE only',
      any('Plug the foot pedal' in (s.get('instruction') or '')
          and s.get('buttons') == ['pause'] for s in seen))
got, state, seen = pedal_live(FakeRelay(pedal=False), ['no', 'yes'])
check('factory screen: a silent pedal stops on FAIL; NO tries again, YES '
      'records it', got == {101: 'FAIL', 129: 'FAIL', 145: 'FAIL', 58: 'NO DATA'}
      and sum(1 for s in seen if s.get('banner') == 'FAIL') >= 2
      and 'recorded by the operator' in state.row(101)['measured'], got)

RA.GRADED_ELSEWHERE.clear()
RA.GRADED_ELSEWHERE.update(saved_ge)
RA.set_pedal_station(False)
check('switching the pedal station off again puts row 58 back where it was',
      RA.PEDAL_THROUGH_ROW not in RA.GRADED_ELSEWHERE
      and 'M3' not in RA.STATION_ORDER)
shutil.rmtree(tmp, ignore_errors=True)

print('%s -- no unit, no bus, no serial port, no write'
      % ('all checks passed' if not FAILS else
         '%d check(s) FAILED' % len(FAILS)))
sys.exit(1 if FAILS else 0)
