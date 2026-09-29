#!/usr/bin/env python3
"""panel_glass_buttons_check.py -- S137's half of the glass-button rule: every
screen the panel loop puts up while it is walking a board carries its own key
prompt AND the NOT LIT button, with no dead ENTER left over from the default
WAITING button set.

`glass_buttons_check.py` (S128) proves the ENTER half of the rule for the
analog/patch station's dry run. This is the panel-loop half PW's ruling
(S137, 2026-09-28) opened up: the armed factory screen now carries a working
NOT LIT button (`d24_live.PANEL_BUTTONS`), and this is the proof that every
screen `d24_runall.panel_station` writes while a panel is being walked
actually carries it -- not a sample, every DISTINCT screen, the same way
S128's checker hooked `Live._flush` rather than polling `live.json`.

Drives `d24_runall.panel_station` directly, on BOTH boards, from the two
scripted key streams in `scripts/`: PASS, NOT LIT and a wrong key, each
exercised on each board (see the report for the row-by-row verdicts this
same drive produces). No bus, no unit, no app -- pure desk proof.

    panel_glass_buttons_check.py
"""
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
PI = os.path.join(ROOT, 'tools', 'pi')
sys.path.insert(0, PI)

CATALOG = os.path.join(ROOT, 'MW', 'D24', 'DSP', 's119', 'test-catalog.csv')
SCRIPTS = {'M1': os.path.join(HERE, 'scripts', 'left-pass-notlit-wrongkey.txt'),
          'M2': os.path.join(HERE, 'scripts', 'right-pass-notlit-wrongkey.txt')}

WANTS_KEY_PROMPT = ('press the button', 'press the lit button', 'find the light')


def record_every_screen(LV):
    out = []
    original = LV.Live._flush
    original_cmd = LV.Live.command

    def flush(self):
        original(self)
        out.append(dict(self.d))

    # THE YES / NO SCREENS (PW 2026-09-29) are answered here: the desk has no
    # operator, and until that ruling those two judgements were recorded as
    # not measured under a live screen instead of being asked.
    def command(self):
        if list(self.d.get('buttons') or []) == list(LV.YESNO_BUTTONS):
            return 'yes'
        return original_cmd(self)
    LV.Live._flush = flush
    LV.Live.command = command

    def unhook():
        LV.Live._flush = original
        LV.Live.command = original_cmd
    return out, unhook


def main():
    import tempfile
    import d24_live as LV
    import d24_runall as RA

    tmp = tempfile.mkdtemp(prefix='s137-glass-')
    rows, catalog_md5 = RA.load_catalog(CATALOG)
    state = RA.State(os.path.join(tmp, 'state.json'), 'S137-DESK', catalog_md5)
    glass = RA.Glass(os.path.join(tmp, 'runall'))

    bad_no_notlit = []
    bad_no_prompt = []
    bad_has_enter = []
    yesno_screens = []
    total_screens = 0
    for st, script in SCRIPTS.items():
        live = LV.Live(os.path.join(tmp, 'runall'), run='panel', total=1,
                       enabled=True, confirm=True)
        every, unhook = record_every_screen(LV)
        a = types.SimpleNamespace(inject_keys=script, left_cell='auto',
                                  panel_timeout=5.0, random_panel_order=False)
        try:
            RA.panel_station(a, st, rows, state, set(), glass, 1,
                             quiet_flag=None, live=live, keys=None)
        finally:
            unhook()
        seen, last = [], None
        for d in every:
            key = (d.get('state'), (d.get('instruction') or '').strip(),
                  tuple(d.get('buttons') or []))
            if key != last:
                last = key
                seen.append(d)
        for d in seen:
            if d.get('state') != LV.WAITING:
                continue
            instr = (d.get('instruction') or '').strip()
            if not instr:
                continue        # nothing worth grading on this screen
            total_screens += 1
            btns = d.get('buttons') or []
            is_encoder = 'turn the encoder' in instr.lower()
            if 'enter' in btns:
                bad_has_enter.append((st, instr, btns))
            if btns == list(LV.YESNO_BUTTONS):
                yesno_screens.append((st, instr))
                continue        # a judgement: YES / NO / PAUSE, not NOT LIT
            if is_encoder:
                # The ring-turn step has no lit/dark judgement to make, so
                # NOT LIT is not offered for it -- only that ENTER stays dead.
                continue
            if 'notlit' not in btns:
                bad_no_notlit.append((st, instr, btns))
            if not any(w in instr.lower() for w in WANTS_KEY_PROMPT):
                bad_no_prompt.append((st, instr, btns))
        print('%s (%s): %d distinct screens seen, driven from %s'
              % (st, RA.PANEL_STATIONS[st], len(seen), script))

    print('\n%d panel-step screens checked (both boards).' % total_screens)
    ok = True
    print('%d yes/no judgement screen(s) asked on the glass:' % len(yesno_screens))
    for st, instr in yesno_screens:
        print('   [%s] %s' % (st, instr[:90]))
    if not yesno_screens:
        ok = False
        print('\nFAIL: no yes/no screen was asked -- the always-lit rings and '
              'the encoder ring went unasked again.')
    if bad_no_notlit:
        ok = False
        print('\nFAIL: %d screen(s) with no NOT LIT button:' % len(bad_no_notlit))
        for st, instr, btns in bad_no_notlit[:10]:
            print('   [%s] buttons=%s :: %s' % (st, btns, instr))
    if bad_has_enter:
        ok = False
        print('\nFAIL: %d screen(s) still carry a dead ENTER:' % len(bad_has_enter))
        for st, instr, btns in bad_has_enter[:10]:
            print('   [%s] buttons=%s :: %s' % (st, btns, instr))
    if bad_no_prompt:
        ok = False
        print('\nFAIL: %d screen(s) with no key prompt in the instruction:'
              % len(bad_no_prompt))
        for st, instr, btns in bad_no_prompt[:10]:
            print('   [%s] buttons=%s :: %s' % (st, btns, instr))
    if not total_screens:
        print('\nFAIL: no panel-step screen was seen at all -- this check '
              'proved nothing.')
        return 1
    if ok:
        print('\nOK: every panel-step screen carries its key prompt plus '
              'NOT LIT, and no dead ENTER.')
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
