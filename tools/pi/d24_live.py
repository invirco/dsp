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
HANDSOFF = 'handsoff'      # the unit is testing itself; nothing to press
SUMMARY = 'summary'        # the end-of-pass summary, one page of it
FINISHED = 'finished'
STOPPING = 'stopping'      # the unit is being put back safe
STATES = (STARTING, WAITING, CHECKING, VERDICT, CHECKLEAD, PAUSED, HANDSOFF,
          SUMMARY, FINISHED, STOPPING)

# The states during which the little activity indicator must be moving. A
# still screen must never leave a worker wondering whether it is stuck, which
# is why STOPPING is in here too: putting the rails down takes a few seconds
# and looks like nothing at all.
BUSY_STATES = (STARTING, WAITING, CHECKING, CHECKLEAD, HANDSOFF, STOPPING)


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


def pick_up(lead, socket=None):
    """The sentence that folds a lead change into the instruction after it.

    There is no READY card and nothing to press at a block boundary (S123):
    the lead going into the socket IS the acknowledgement, so the only thing
    the change needs is one more sentence on the same screen.

    With the kit parked (S126, ruling c) the sentence can say WHERE the lead
    is, which is the whole of what PW asked for: "a lead change becomes one
    instruction -- pick up the lead hanging from AUX 3."
    """
    if socket:
        return 'Pick up %s, hanging on %s.' % (lead_words(lead),
                                               socket_words(socket))
    return 'Pick up %s.' % lead_words(lead)


def take_off(lead, socket, in_socket=False):
    """Free a socket that has a parked kit lead on it (S126, ruling c).

    Every socket a lead can usefully be parked on is one some walk has to
    visit, so the walk pays for it once -- here, as one more sentence on the
    screen that was already asking for that socket, and never as a card.
    """
    if in_socket:
        return 'Take %s out of %s first.' % (lead_words(lead),
                                             socket_words(socket))
    return 'Take %s off %s first.' % (lead_words(lead), socket_words(socket))


def repark(lead, socket):
    """The one instruction the ruling asks for when a socket a lead was parked
    on does not work: hang it somewhere that does."""
    return 'Hang %s on %s instead.' % (lead_words(lead), socket_words(socket))


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


def move_input(name, confirm=True):
    """The walk that finds a working loop, in the words of an ordinary
    instruction. It is a diagnosis, and it must never read as one: a worker
    is told to move a lead, not that the unit has a dead input."""
    return ('Move the lead to %s%s'
            % (socket_words(name), ', then press ENTER.' if confirm else '.'))


def move_output(out, into, confirm=True):
    return ('Move the other end to %s, and this end to %s%s'
            % (out, socket_words(into), ', then press ENTER.' if confirm else '.'))


# ---------------------------------------------------------------------------
# HANDS OFF (PW ruling, S129 addendum 4)
# ---------------------------------------------------------------------------
# "If any of the tests require touch display silence then notify user and take
# control for those tests, with active progress."
#
# ONE step on this unit genuinely needs it, and it is the one that has been
# failing: AL1, the speaker-to-panel-microphone loop. Since S126 the automatic
# set runs UNDER the operator's panel loop, so the microphone that has to hear
# the speaker is six inches from a finger clicking buttons -- and AL1 read
# NO DATA, "no settled window for: base, tone, back", on PW's passes having
# passed on 09-25 and 09-26 when nothing ran under it.
#
# The hold that was supposed to prevent that gave up after 8 s and AL1 takes 17,
# so the loop lit the next button while the tone was still sounding. The cap is
# now longer than the step, the glass says what is happening, the progress
# counts up, and a press during the window is DROPPED rather than queued -- a
# queued press would be spent on the step after, which is the same class of
# fault one layer up.
def hands_off_words(what, secs):
    return 'Hands off - the unit is testing itself (%s, about %d s).' % (what,
                                                                        secs)


HANDS_OFF_NOTE = 'Do not touch the screen or the front panel until this clears.'


def move_other_end(out, into, confirm=True):
    """THE PATCH WHERE ONLY THE OUTPUT END MOVES (S129, item 7).

    "Plug AUX 1 into MIC 7" is the right sentence when both ends move. It is
    the WRONG one when the lead is already in MIC 7 and the only thing that has
    to move is the other end, because a worker reads it, looks at MIC 7, sees a
    lead in it, and presses ENTER.

    That is what MIC 7 did on both of PW's completed passes, and the evidence
    says the hardware is innocent: MIC 7 passes every tone patch in the loop
    block at -12 dBFS, its 595 byte drives its own preamp and no other (+32.8
    dB of noise at gain 63, measured lane by lane on 2026-09-27), its lane floor
    is -113.9 dBFS in the middle of the pack, and its meter node reads a
    -20 dBFS oscillator exactly. The patch it fails, three attempts running, is
    the FIRST patch of the input block -- the one where the previous block left
    the lead in MIC 7 and only the output end moves, from AUX 3 to AUX 1.

    So the sentence says which end, and it says the other one stays put.
    """
    return ('Move the OTHER end of the lead to %s - this end stays in %s%s'
            % (out, socket_words(into),
               ', then press ENTER.' if confirm else '.'))


def swap_for_plug(name, confirm=True):
    """The noise step, which PW ruled is sequential: the lead comes out and
    the plug goes into the socket it just left."""
    return ('Take the lead out of %s and put the 150 ohm plug in%s'
            % (socket_words(name), ', then press ENTER.' if confirm else '.'))


# ---------------------------------------------------------------------------
# THE SETUP PAGES (HUB ADDENDUM 1, PW 2026-09-27)
# ---------------------------------------------------------------------------
# "Before any lead-by-lead patching, the operator is walked through the whole
# setup on the D24's own screen, in panel names... ONE big instruction per page,
# with n of N and ENTER to confirm each. Do not put a checklist wall on one
# page."
#
# There is NO PRE-START PAGE, and the reason is worth stating once: the only
# thing that has to be in before START is the mains lead, and a unit that is
# showing this screen is running from it. The network lead is NOT a pre-START
# item any more -- since ruling (a) the network tests run in the background
# UNDER the patch pass, minutes after START -- so it is setup page 1 like
# everything else.
#
# WHERE THE MACHINE CAN SEE IT, IT SAYS SO. The two USB sticks and the network
# link are read live and the page shows the tick; a parked lead's far end sits
# on an undriven output and nothing on the unit can see it, so no page claims
# otherwise.
SETUP_TITLE = 'Set the bench up'


def setup_network(confirm=True):
    return ('Plug the network lead into the network socket on the rear panel%s'
            % (', then press ENTER.' if confirm else '.'))


def setup_usb(side=None, confirm=True):
    """The two USB sockets, in PANEL TERMS AND ON THE RIGHT PANEL (S128).

    PW at the bench, 2026-09-27: "there are 2 usb sockets on top (analog board),
    back (digital board) socket is currently occupied with touch panel." The page
    said "the left socket of the double USB pair on the REAR panel", which is the
    wrong panel and the wrong board -- the catalog has always had these two rows
    against the ANALOG board -- and it sent the worker to the one socket they must
    not touch, because unplugging it takes the display away.

    ONE PAGE FOR BOTH, and `side` is accepted and ignored so the old two-page
    call still works. Which of the two sockets is hub port 3 and which is port 4
    is not something this page needs to assert -- and asserting it wrongly is how
    the rear-panel sentence happened. The worker fills both; the machine reads
    both and names the empty one if there is one.
    """
    return ('Put a USB memory stick into each of the TWO USB sockets on the top '
            'panel%s' % (', then press ENTER.' if confirm else '.'))


# The rear USB socket is the TOUCH PANEL'S, and it is not a page: it is graded by
# the display working at all. Said here so the vocabulary check sees it and so
# nobody adds a page that asks a worker to pull it out.
USB_REAR_IS_THE_PANEL = ('The USB socket on the back panel is the touch '
                         'screen\'s. Leave it alone.')


def park_kit_page(row, confirm=True):
    """One kit item's setup page, from patch-kit.csv's facts.

    The CSV carries the lead code, which end is parked and the panel socket;
    the words are here, so there is one vocabulary and `--check-md` polices it.
    """
    lead, end, socket = row.get('lead'), row.get('end'), row.get('socket')
    tail = ', then press ENTER.' if confirm else '.'
    if end == 'bench':
        return ('Put %s on the bench, where you can reach it%s'
                % (lead_words(lead), tail))
    if end == 'in':
        return ('Put %s into %s and leave it there%s'
                % (lead_words(lead), socket_words(socket), tail))
    return ('Hang %s on %s and leave it there%s'
            % (lead_words(lead), socket_words(socket), tail))


SETUP_SEEN = 'The unit can see it.'
SETUP_NOT_SEEN = 'The unit cannot see it yet.'
SETUP_DONE = 'The bench is set up.'


NO_LOOP = 'No signal on any socket - call the supervisor.'
LOOKING = 'Looking for a working socket...'


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


# The banner a patch gets when nobody measured it: the operator said SKIP or
# IGNORE, the walk carried on, and the one report at the end lists it with
# their reason (S127). It is neither a pass nor a fail and it does not pretend
# to be either.
NOT_TESTED = 'NOT TESTED'


def action_not_tested():
    return 'Nothing was measured on this one - moving on.'


def finished_words(passed, failed, not_tested=0):
    """The end of the pass, counting everything that happened to a patch.

    S127: a pass that carried on past a skip used to end on "all N passed",
    because the tally only knew about two outcomes. A worker who skipped four
    patches was told the unit passed everything.
    """
    bits = ['%d passed' % passed]
    if failed:
        bits.append('%d failed' % failed)
    if not_tested:
        bits.append('%d not tested' % not_tested)
    if len(bits) == 1:
        return 'Finished - all %d passed.' % passed
    return 'Finished - %s.' % ', '.join(bits)


HANDOVER = 'Give this unit to the supervisor.'

# A RUN THAT ENDED WITHOUT FINISHING, IN WORDS A WORKER CAN ACT ON (S127).
# Until this existed, a station that fell over left the last instruction on the
# glass with the rails still up, and the screen sat in test mode showing a
# patch nobody was going to make. PW saw that as "froze in factory test mode".
# The sentence says the same two things in every case: it stopped, and the unit
# is safe to touch.
STOPPED_WORDS = 'The test stopped before it finished. The unit is safe.'


def stopped_words(why=''):
    """The same sentence with one plain clause about what stopped.

    `why` is written for the person at the unit, not for a log: "the test
    program stopped", never an exception class.
    """
    if not why:
        return STOPPED_WORDS
    return ('The test stopped before it finished - %s. The unit is safe.'
            % why)


RESTART_WORDS = 'Press START to run the test again.'


# HOW MUCH FITS ON THE ONE INSTRUCTION (S128, measured on the glass).
#
# `FactoryView.axaml` draws the instruction at FontSize 104 with LineHeight 118
# in a row 320 px tall on a 1920x1080 panel with an 80 px margin each side. That
# is TWO LINES, about 34 characters each. A third line runs into the status line
# under it and a fifth is simply not drawn.
#
# Witnessed: the analog station's card, 253 characters, came out five lines deep
# with "Station 3 of 3" printed through the middle of it
# (`s128/screens/08-...png`). The card had never been seen on the glass before
# S128 -- it was a dialog, which has no such limit -- so the first time it was
# drawn was the first time it was too long.
GLASS_MAX_CHARS = 100


def fits(instruction):
    """Does this instruction fit the two lines the screen draws?"""
    return len(instruction or '') <= GLASS_MAX_CHARS


def station_card_words(name, hand, checks, rails):
    """The card a worker reads before a stretch of hand work, as ONE
    instruction for the one-instruction screen (S127).

    The dialog version of this card is three lines and a button; the factory
    screen is one big instruction and ENTER, so the same facts are said as one
    sentence a person can act on. The station's own name is not on it: the
    screen already says which station this is, and PW's rule for this display
    is one thing to read, not a heading and a body.

    WHAT THE WORKER MUST ACT ON IS THE INSTRUCTION; WHAT THEY MUST CARRY IS THE
    SECOND LINE (S128). The kit list is four leads and a plug and it will not
    fit in two lines at 104 px whatever is done to it, so it goes in `extra` --
    the grey line under the instruction, which wraps and has room. Use
    `station_card_extra()` for it.
    """
    bits = ['Next: %s.' % name.lower()]
    if rails:
        bits.append('Supplies LIVE.')
    bits.append('%d check%s. Press ENTER.'
                % (checks, '' if checks == 1 else 's'))
    return ' '.join(bits)


def station_card_extra(hand):
    """The second line of a station card: what to have in hand."""
    return 'You need %s.' % hand


# What the glass says while a panel loop runs. The UNIT is the instruction --
# it lights the indicator of the button to press next -- so the screen says the
# one thing the unit cannot, and then stays still.
PANEL_LOOP_WORDS = 'Press the button on the front panel that is lit.'


# WHICH SWITCH BOARD THE WORKER IS AT, ON EVERY STEP (S128, HUB ADDENDUM 1).
#
# PW at the bench, 2026-09-27: "led test was only one switch board, and didn't
# cover all switches." Both halves of that follow from one hole. The front panel
# is TWO switch boards, they are walked one after the other, and BOTH of them
# decode the same matrix cell with the same indices 1..6 (finding S120-1) -- so
# for the first six steps of either loop an indicator lights on BOTH boards and
# the key code that comes back does not say which board it came from. S120 shipped
# that with one mitigation: "the two stations are separate, the operator is told
# which panel they are at."
#
# Then S125 gave the two stations ONE card, because the operator is already
# standing at the front panel -- and S127 gave the loop ONE standing page that
# says "press the button on the front panel that is lit". Between them, the one
# place the worker was ever told which of the two boards to work was gone. A
# worker who stays on the board they started on presses that board for all twenty
# steps: six of them score (the shared indices) and the other fourteen do not,
# which is a pass that covered one board and called it the front panel.
#
# So the board is named in the step's own words, on every step, and in the status
# line -- no extra press, and nothing for a worker to remember.
def panel_side_words(panel):
    """The board, in the words on the glass. `panel` is `d24_panel.PANEL_NAME`."""
    return panel.replace(' switch panel', '').upper() + ' switch board'


# A STEP OF THE PANEL LOOP THAT IS NOT "PRESS THE LIT ONE" GETS ITS OWN WORDS
# (S128). The standing page above is right for the sweep -- fourteen buttons,
# one instruction, the unit saying which -- and wrong for every step that asks
# for something else. PW's first real pass hit that: the runner was waiting for
# the encoder and the glass still read "Press the button on the front panel that
# is lit", so the one thing on the screen was the one thing not being asked for.
ENCODER_WORDS = 'Turn the encoder one click clockwise, then one back.'


def panel_retry_words(name, what, panel=''):
    """The indicator did not light, and the switch under it is still worth a
    press. Said on the glass as well as in the dialog, because the dialog is
    what the runner is answered through and the glass is what is read."""
    if panel:
        return ('%s: %s did not light. Press %s anyway.'
                % (panel_side_words(panel), what, name))
    return ('%s did not light. Press %s anyway, so the switch itself is still '
            'checked.' % (what.capitalize(), name))


def panel_press_words(name, what, panel=''):
    """One named button of the sweep, for the glass.

    The BOARD and the BUTTON are both named, and it is two lines because that
    is all the screen draws (GLASS_MAX_CHARS). The sweep's standing page named
    neither -- the unit names the button by lighting it -- but the unit lights
    the same index on BOTH boards, so the screen has to say which board, and a
    worker who cannot tell which indicator lit has to be able to read the name.
    """
    if panel:
        # `what` carries its own capitals -- "the RED ring" -- and
        # `str.capitalize()` would flatten them, so only the first letter moves.
        return ('%s: press the lit button, %s. %s should be lit.'
                % (panel_side_words(panel), name, what[:1].upper() + what[1:]))
    return ('Press the button that is lit: %s. It is %s that should be lit.'
            % (name, what))


def panel_already_passed(already, total):
    """The second line of a panel loop that is only walking what it owes.

    S128. A re-test walks the buttons whose rows have not passed yet and no
    others (PW 09-26, no test twice for the same proof). On PW's second pass
    that was four of the right board's fourteen and the screen said nothing,
    so it read as the loop giving up: "exited after a few button clicks".
    """
    if not already:
        return ''
    return ('%d of the %d checks on this board passed on an earlier run and '
            'are not repeated.' % (already, total))


def panel_loop_words(panel=''):
    """The standing page for one board's sweep."""
    if not panel:
        return PANEL_LOOP_WORDS
    return ('Work the %s. Press the button on it that is lit.'
            % panel_side_words(panel))


def panel_judgement_missed(what):
    """A judgement this screen cannot put to the operator.

    PW's ruling of 2026-09-27: where a step cannot be taken, the station
    records it, says so in one plain sentence, and carries on with whatever can
    still be tested. The yes/no questions in the panel loop need two buttons
    and this screen has one, so they are recorded as not measured rather than
    guessed at or, worse, waited on for ever.
    """
    return ('%s: not checked, because this screen cannot ask a yes or no '
            'question yet.' % what)


def second_start_words():
    """START pressed while a test is already going.

    It is an ordinary thing for a worker to do -- the screen was slow, so they
    pressed it again -- and until S127 it started a SECOND test on the same
    unit, which died on the hardware the first one was holding. The refusal
    says the one thing the person needs: yours is still going, keep following
    it.
    """
    return 'The test is already running. Carry on with the instructions.'


def every_string(rows=()):
    """Every operator-facing string this screen can produce.

    Fed to the internal-vocabulary check, which is the acceptance grep: the
    page a person reads carries no test id, no cell name, no lead code and no
    repo path. Passing `rows` (the patch list) makes the check cover the real
    instructions and not just the fixed furniture.
    """
    out = list(STATUS_WORDS.values())
    out += [SIGNAL_SEEN, NO_LOOP, LOOKING,
            move_input('MIC 6'), move_input('MIC 6', False),
            move_output('AUX 2', 'MIC 1'), move_output('AUX 2', 'MIC 1', False),
            swap_for_plug('MIC 7'), swap_for_plug('MIC 7', False),
            action_no_signal(), action_no_signal(False), action_failed(),
            action_not_tested(),
            HANDOVER, 'ENTER', 'PAUSE', 'START',
            finished_words(55, 0), finished_words(53, 2),
            finished_words(51, 2, 2), finished_words(53, 0, 2),
            STOPPED_WORDS, stopped_words('the test program stopped'),
            stopped_words('it was stopped'),
            stopped_words('it was paused'), RESTART_WORDS,
            second_start_words(), PANEL_LOOP_WORDS, ENCODER_WORDS,
            panel_loop_words('left switch panel'),
            panel_loop_words('right switch panel'),
            panel_already_passed(0, 36), panel_already_passed(24, 36),
            panel_retry_words('MONO AUX', 'the white pair',
                              'left switch panel'),
            panel_press_words('MONO AUX', 'the white pair',
                              'left switch panel'),
            panel_press_words('FX MUTE', 'the RED ring',
                              'right switch panel'),
            panel_judgement_missed('The always-lit rings'),
            panel_judgement_missed('The ring around the encoder'),
            station_card_words('Front panel switches',
                               'a finger and an eye, at the front panel',
                               44, False),
            station_card_words('Analog paths', 'the patch kit', 33, True),
            station_card_extra('a finger and an eye, at the front panel'),
            'PASS', 'FAIL', NOT_TESTED]
    for lead in sorted(LEAD_WORDS):
        out.append(pick_up(lead))
        out.append(pick_up(lead, 'AUX 2'))
        out.append(take_off(lead, 'AUX 2'))
        out.append(take_off(lead, 'MIC 2', in_socket=True))
        out.append(repark(lead, 'AUX 5'))
        for end, sock in (('out', 'AUX 3'), ('in', 'MIC 2'), ('bench', '')):
            row = dict(lead=lead, end=end, socket=sock)
            out.append(park_kit_page(row))
            out.append(park_kit_page(row, confirm=False))
    out += [SETUP_TITLE, setup_network(), setup_network(False),
            setup_usb(), setup_usb(confirm=False), USB_REAR_IS_THE_PANEL,
            SETUP_SEEN, SETUP_NOT_SEEN, SETUP_DONE]
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
    # THE SUMMARY HAS ONE BUTTON AND IT IS EXIT (PW 2026-09-27, addendum 3):
    # "a complete grid of all tests should be shown, and remain until user
    # exits, otherwise, no time to review anything". So no PAUSE -- the pass is
    # over -- no START underneath it, and no timeout anywhere: the screen stays
    # up until EXIT is pressed. On a paged summary EXIT turns the page and the
    # last press leaves it.
    if state == SUMMARY:
        return ['exit']
    # HANDS OFF HAS NO BUTTON AT ALL (PW ruling, S129 addendum 4): "if any of
    # the tests require touch display silence then notify user and take control
    # for those tests, with active progress". A button that did nothing would
    # be worse than none, and a button that QUEUED a press would spend it on
    # the step after -- which is the fault this is fixing, one layer up.
    if state == HANDSOFF:
        return []
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
            # THE END-OF-PASS SUMMARY (PW 2026-09-27): "when the test completes
            # it should show a summary of what passed and failed, no detail,
            # just pass/fail status for each test". `summary` is ONE PAGE of it
            # -- a list of [short name, verdict] pairs, already ordered, already
            # truncated to what a column can hold -- and `n`/`total` are the
            # page numbers, so the renderer still counts nothing. `summary` is
            # empty in every other state.
            summary=[], summary_title='',
            buttons=buttons_for(STARTING, confirm))
        if self.enabled:
            os.makedirs(dirpath, exist_ok=True)
            self._flush()

    # -- writing -----------------------------------------------------------
    def _flush(self):
        if not self.enabled:
            return
        # THE PROGRESS PAIR IS ALWAYS DRAWABLE (S127). `n` and `total` are the
        # only two numbers on this file a renderer does arithmetic with, so the
        # writer owes it a pair it can draw: 0 <= n <= total, total at least 1.
        # A run that stopped before it had a list left total at 0 here, which is
        # a division nobody can draw, and an off-by-one leaves a bar past the
        # end of its own track. Clamped rather than asserted: this is the code
        # that runs while something has already gone wrong.
        total = max(1, int(self.d.get('total') or 0))
        self.d['total'] = total
        self.d['n'] = min(max(0, int(self.d.get('n') or 0)), total)
        self.seq += 1
        self.d['seq'] = self.seq
        self.d['heartbeat'] = time.time()
        self.d['stamp'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
        tmp = self.path + '.tmp'
        with open(tmp, 'w') as fh:
            json.dump(self.d, fh)
        os.replace(tmp, self.path)

    _warned = set()

    def set(self, **kw):
        """Change some fields and put the screen up. A state carries its own
        default status line and its own busy flag, so a caller that only knows
        it moved to CHECKING does not also have to know the words."""
        # AN INSTRUCTION THAT WILL NOT FIT IS SAID IN THE LOG (S128). It is not
        # an error -- nothing about a factory pass should stop over wording, and
        # this is the code that runs while a worker is standing there -- but it
        # is invisible from a terminal and obvious on the glass, which is the
        # worst way round. See GLASS_MAX_CHARS.
        instr = kw.get('instruction')
        if instr and not fits(instr) and instr not in Live._warned:
            Live._warned.add(instr)
            print('   .. this instruction is %d characters and the screen '
                  'draws about %d: %r' % (len(instr), GLASS_MAX_CHARS, instr),
                  flush=True)
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
            if state != SUMMARY:
                kw.setdefault('summary', [])
                kw.setdefault('summary_title', '')
            if state == HANDSOFF:
                kw.setdefault('can_pause', False)
            elif state != SUMMARY:
                kw.setdefault('can_pause', True)
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
        return cmd if cmd in ('pause', 'enter', 'exit') else None
