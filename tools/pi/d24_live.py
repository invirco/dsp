#!/usr/bin/env python3
"""d24_live.py -- the factory screen's live status file, and the plain words on it.

PW 2026-09-26, at the bench: "it should say aux 5 to mic 5 on the product
display. let's stop, remove all the clutter, add some realtime activity and
progress indicator, ie what it's currently doing, simple, simple, simple, for a
factory worker who knows nothing about the product, but can follow
instructions."

So there are exactly four things on the glass while a manual loop runs -- the
INSTRUCTION, one live STATUS line, the PROGRESS, and PAUSE -- and this file is
the only place any of those words are chosen. The display is a renderer: it
draws what it is given and decides nothing. That split is deliberate. Every
string a factory worker reads is generated here, in one file, where the
internal-vocabulary check can be pointed at it (`d24_runall.py --check-md`),
rather than in C# where it would be a resource nobody greps.

WHY A SECOND FILE AND NOT prompt.json. `runall/prompt.json` is a DIALOG: a
title, some lines and up to six buttons, put up once and waited on. It is the
right shape for "this fixture is not built, skip or ignore?" and the wrong
shape for a screen that has to change four times inside one patch while nobody
presses anything. The dialog protocol also only counts as live when the app
finds the `d24-runall` unit running, which is how a station launched any other
way drew its card inside a page that said the run had finished. So:

    runall/live.json      what the screen shows, RIGHT NOW. Rewritten on every
                          state change and at least once a second otherwise;
                          its `heartbeat` is what makes a run live, whatever
                          launched it.
    runall/command.json   the one button. The app writes it, the runner takes
                          it and deletes it.

Both are written whole, to a temporary name, and moved into place, so a reader
that catches the wrong millisecond gets the old file and never half of one.

THE HEARTBEAT IS THE DEFINITION OF LIVE (S123 item 3). A run is live while
`now - heartbeat < LIVE_STALE_S`. Nothing else is consulted -- not a systemd
unit, not a process table -- so a station started from a terminal, from the
screen's own START, or under any unit name at all draws the same screen.
"""
import json
import os
import time

LIVE_NAME = 'live.json'
COMMAND_NAME = 'command.json'

# A screen older than this is not a running test. The runner beats at
# BEAT_S; three beats of slack covers one blocking measurement (about 0.7 s)
# and a loaded CM4 without ever leaving a dead run on the glass for long.
LIVE_STALE_S = 3.0
BEAT_S = 0.5

# The states, and what each one means to the person standing at the unit.
# Anything not in here is a bug, not a new state: the renderer is allowed to
# fall back to the `status` string but the screen's colour comes from these.
STARTING = 'starting'      # rails, chain, routes -- before the first patch
WAITING = 'waiting'        # the tone is up, waiting for the lead to go in
CHECKING = 'checking'      # the lead is in, the reading is being taken
VERDICT = 'verdict'        # a patch has been scored; `banner` carries it
CHECKLEAD = 'checklead'    # the lead is in the wrong socket, or in nothing
PAUSED = 'paused'
FINISHED = 'finished'
STOPPING = 'stopping'      # the unit is being put back safe
STATES = (STARTING, WAITING, CHECKING, VERDICT, CHECKLEAD, PAUSED, FINISHED,
          STOPPING)

# The states during which the little activity indicator must be moving. A
# still screen must never leave a worker wondering whether it is stuck, which
# is why STOPPING is in here too: putting the rails down takes a few seconds
# and looks like nothing at all.
BUSY_STATES = (STARTING, WAITING, CHECKING, CHECKLEAD, STOPPING)


# ---------------------------------------------------------------------------
# The words
# ---------------------------------------------------------------------------
# The leads, in the words a person would use to pick one up off the bench.
# The kit codes (K1..K5) are records, not instructions, and never reach the
# glass.
LEAD_WORDS = {
    'K1': 'the XLR lead',
    'K2': 'the jack-to-XLR lead',
    'K3': 'the XLR-to-mini-jack lead',
    'K4': 'the XLR-to-jack lead',
    'K5': 'the 150 ohm plug',
}


def lead_words(lead):
    return LEAD_WORDS.get(lead, 'the next lead')


def pick_up(lead):
    """The sentence that folds a lead change into the instruction after it.

    There is no READY card and nothing to press at a block boundary (S123):
    the lead going into the socket IS the acknowledgement, so the only thing
    the change needs is one more sentence on the same screen.
    """
    return 'Pick up %s.' % lead_words(lead)


def socket_words(name):
    """A socket, the way the front of the unit names it.

    The list carries `MIC 5 line` for the jack centre of a combo socket, which
    is a column value and not a thing anyone can read off the panel. It is the
    one name that has to be turned back into a sentence.
    """
    name = (name or '').strip()
    if name.endswith(' line'):
        return 'the jack socket of %s' % name[:-len(' line')]
    return name


def instruction_for(row, confirm=True):
    """The one big line: what to plug into what.

    `row` is a patch-paths.csv row. The CSV's own `prompt` column says "Patch
    AUX 5 to MIC 5", which is the list's voice; this is the operator's.

    PW, 2026-09-26, having watched a pass advance under their hands: "I like
    it, but let me plug in the cable, then hit Enter." So the instruction is
    two things a person does in order, and it says both -- the step does not
    end until the second one.
    """
    into = socket_words(row.get('in'))
    out = (row.get('out') or '').strip()
    if not out:                                  # the terminator rows: no source
        line = 'Put %s into %s' % (lead_words(row.get('lead')), into)
    else:
        line = 'Plug %s into %s' % (out, into)
    return line + (', then press ENTER.' if confirm else '.')


def extra_for(row):
    """The one qualifying sentence a patch may need, or ''.

    Two patches in the whole list need one: a mini-jack, because the other
    mini-jack has to be empty for the reading to mean anything, and a patch
    with more than one check on it, because the lead must stay put.
    """
    note = ''
    if 'MINI-JACK' in (row.get('in') or ''):
        other = '2' if row.get('in', '').endswith('1') else '1'
        note = 'Leave MINI-JACK %s empty.' % other
    return note


def hold_note(n_checks):
    if n_checks > 1:
        return 'Leave the lead in until the screen changes.'
    return ''


def patch_words(row):
    """A patch named the way the end-of-run list names it."""
    out = (row.get('out') or '').strip()
    into = socket_words(row.get('in'))
    if not out:
        return '%s, terminated' % into
    return '%s into %s' % (out, into)


# The live status line, per state. One sentence, present tense, no jargon.
STATUS_WORDS = {
    STARTING: 'Getting the unit ready...',
    WAITING: 'Waiting for the lead...',
    CHECKING: 'Checking...',
    PAUSED: 'Paused - the unit is safe.',
    STOPPING: 'Putting the unit back safe...',
}


# The hint, and it is ONLY a hint: the tester can see the signal arrive and
# says so, but the step still waits for ENTER (PW 2026-09-26).
SIGNAL_SEEN = 'Signal found - press ENTER.'


def status_words(state):
    return STATUS_WORDS.get(state, '')


# The one plain action a red screen offers. Exactly one, always something the
# person can do with their hands.
def action_wrong_socket(actual, wanted, confirm=True):
    return ('The lead is in %s - move it to %s%s'
            % (actual, socket_words(wanted),
               ', then press ENTER.' if confirm else '.'))


def action_no_signal(confirm=True):
    return ('Push the lead in firmly at both ends%s'
            % (', then press ENTER again.' if confirm else '.'))


def action_failed():
    return 'Leave it - the supervisor will look at this one.'


def finished_words(passed, failed):
    if not failed:
        return 'Finished - all %d passed.' % passed
    return 'Finished - %d passed, %d failed.' % (passed, failed)


HANDOVER = 'Give this unit to the supervisor.'


def every_string(rows=()):
    """Every operator-facing string this screen can produce.

    Fed to the internal-vocabulary check, which is the acceptance grep: the
    page a person reads carries no test id, no cell name, no lead code and no
    repo path. Passing `rows` (the patch list) makes the check cover the real
    instructions and not just the fixed furniture.
    """
    out = list(STATUS_WORDS.values())
    out += [SIGNAL_SEEN,
            action_no_signal(), action_no_signal(False), action_failed(),
            HANDOVER, 'ENTER', 'PAUSE', 'START',
            finished_words(55, 0), finished_words(53, 2),
            'PASS', 'FAIL']
    for lead in sorted(LEAD_WORDS):
        out.append(pick_up(lead))
    for r in rows:
        out.append(instruction_for(r))
        out.append(instruction_for(r, confirm=False))
        if extra_for(r):
            out.append(extra_for(r))
        out.append(patch_words(r))
        out.append(action_wrong_socket('MIC 6', r.get('in')))
        out.append(action_wrong_socket('MIC 6', r.get('in'), confirm=False))
    out.append(hold_note(3))
    return [s for s in out if s]


# The buttons on the glass, per state. The screen draws what it is given and
# owns no rule about when a button exists: PW's ENTER is only offered where
# pressing it means something, PAUSE is offered wherever a run can be stopped,
# and START is what replaces both once the pass is over.
def buttons_for(state, confirm=True):
    if state in (PAUSED, FINISHED):
        return ['start']
    if confirm and state in (WAITING, CHECKLEAD):
        return ['enter', 'pause']
    return ['pause']


# ---------------------------------------------------------------------------
# The file
# ---------------------------------------------------------------------------
class Live:
    """One small JSON file, rewritten whenever the screen should change.

    Every field is a thing to draw. There is no field the renderer has to
    interpret, look up or count, because the moment the renderer counts
    something it owns a rule, and the rules belong on this side where the
    patch list is.
    """

    def __init__(self, dirpath, run='patch', total=0, enabled=True,
                 confirm=True):
        self.dir = dirpath
        self.enabled = bool(enabled and dirpath)
        self.path = os.path.join(dirpath or '.', LIVE_NAME)
        self.cmd_path = os.path.join(dirpath or '.', COMMAND_NAME)
        self.seq = 0
        self.t0 = time.time()
        # `confirm` is PW's ruling of 2026-09-26: the operator plugs the lead
        # in and presses ENTER, and the step does not end until they do. It is
        # what puts the ENTER button on the screen; auto-advance is the same
        # loop with this off.
        self.confirm = bool(confirm)
        self.d = dict(
            v=1, run=run, seq=0, state=STARTING, stamp='', heartbeat=0.0,
            instruction='', lead_line='', extra='', status=status_words(STARTING),
            busy=True, banner='', banner_line='', action='',
            n=0, total=int(total), lead_n=0, lead_total=0,
            passed=0, failed=0, failures=[], can_pause=True,
            buttons=buttons_for(STARTING, confirm))
        if self.enabled:
            os.makedirs(dirpath, exist_ok=True)
            self._flush()

    # -- writing -----------------------------------------------------------
    def _flush(self):
        if not self.enabled:
            return
        self.seq += 1
        self.d['seq'] = self.seq
        self.d['heartbeat'] = time.time()
        self.d['stamp'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        tmp = self.path + '.tmp'
        with open(tmp, 'w') as fh:
            json.dump(self.d, fh)
        os.replace(tmp, self.path)

    def set(self, **kw):
        """Change some fields and put the screen up. A state carries its own
        default status line and its own busy flag, so a caller that only knows
        it moved to CHECKING does not also have to know the words."""
        state = kw.get('state')
        if state is not None:
            if state not in STATES:
                raise AssertionError('%r is not a screen state' % state)
            kw.setdefault('status', status_words(state))
            kw.setdefault('busy', state in BUSY_STATES)
            kw.setdefault('buttons', buttons_for(state, self.confirm))
            if state != VERDICT and state != CHECKLEAD:
                kw.setdefault('banner', '')
                kw.setdefault('banner_line', '')
                kw.setdefault('action', '')
        self.d.update(kw)
        self._flush()

    def beat(self):
        """Say the run is alive without changing anything on it.

        Cheap enough to call inside the detector's 50 ms poll; it only rewrites
        the file every BEAT_S, so the screen's watcher is not woken twenty
        times a second for a file whose contents did not move.
        """
        if not self.enabled:
            return
        if time.time() - self.d['heartbeat'] >= BEAT_S:
            self._flush()

    def clear(self):
        """Take the screen down. The run is over and the app goes back to
        whatever it shows when nothing is running."""
        if not self.enabled:
            return
        for p in (self.path, self.cmd_path):
            try:
                os.remove(p)
            except OSError:
                pass

    # -- the one button ----------------------------------------------------
    def command(self):
        """The operator's button, or None.

        Deliberately NOT the dialog's answer.json: PAUSE has to work in the
        states where no dialog is posted -- while a reading is being taken,
        while a verdict is up -- and a dialog answer is only valid against the
        sequence number of the dialog that is currently up. This file carries
        no sequence number because there is only ever one button on the screen
        and only one run to press it at.
        """
        if not self.enabled:
            return None
        try:
            with open(self.cmd_path) as fh:
                c = json.load(fh)
        except (OSError, ValueError):
            return None
        try:
            os.remove(self.cmd_path)
        except OSError:
            pass
        if float(c.get('stamp', 0)) < self.t0:
            return None                      # left over from a previous run
        cmd = c.get('command')
        return cmd if cmd in ('pause', 'enter') else None
