#!/usr/bin/env python3
"""d24_panel.py -- the panel loop: the tester lights an indicator, the operator
presses the button under it, the tester reads the key code back (S120).

Runs ON the unit's CM4 (it wants /dev/serial0). `matrix-app` owns that port, so
stop it first and put it back, exactly as `d24_bus_probe.py` requires.

THE LOOP NEEDS NO FIRMWARE CHANGE AND NO NEW WIRE. Both halves of the round trip
are already in the shipping panel firmware, and both are ONE matrix cell:

    Sys001Skin001 (5412, 0x1524 -> "imjl")
        WRITE it  -> the panel lights the ONE indicator whose radio index equals
                     the value and extinguishes the other thirteen.  `WrRadioLed()`
                     compares the cell's RECEIVED data against each LED's
                     `radioData`; nothing else moves an indicator, and a press
                     does not move one either.  0 lights none.
        READ it   -> a press arrives as this cell carrying the pressed button's
                     radio index.  `RdRadioSwitch()` sets the cell's TRANSMIT
                     data and raises its flag, and MH1 relays it to the host.
    Sys001Enc001  (5232, 0x1470 -> "ilrh")
        the same pair for the encoder: the ring's eight indicators follow the
        received value, and a detent sends the new position 1..8.

MEASURED ON MW-D24-2 (S120): the host->indicator hop is 1.77 ms to MH1's own ack
(mean of 10, 1.74..1.82), a full cell round trip through a slave MCU is 3.07 ms
(2.92..3.39), and one panel's relay costs about 3 ms of MH1's bus sweep.  So the
machine part of press->indicator is UNDER 10 ms, against PW's 50 ms bar, with the
product's firmware untouched.

S120-1, CLOSED BY PW's RULING (a) AND defs-v2026.09.27: THE LEFT PANEL HAS A
CELL OF ITS OWN.  Until then both panels decoded the SAME cell and the left
panel's six indices 1..6 were the right panel's HOME..FX MUTE, so a value of 3
lit FX on the left AND +48 on the right and a press of either arrived
identically: the loop had to be run one panel at a time with the operator told
which, and a press on the other panel's button of the same index was
undetectable.  `Sys001SwLeft001` (5005) ends that -- a press on it can only be
the left board and a press on `Sys001Skin001` can only be the right, and the
loop now says which board pressed it and FAILS a step answered by the other
one.  See `cells_for()`: the address has to be in H1S4's own MATRIX[] table
before it means anything, so while that board is unidentified the loop writes
both cells and the first press settles it.

    d24_panel.py --mode probe                 who is on the bus, and how fast
    d24_panel.py --mode rtt --reps 10         the two hops, timed on the part
    d24_panel.py --mode light --value 7       light one indicator and hold it
    d24_panel.py --mode watch --secs 20       print key codes as they arrive
    d24_panel.py --mode loop --panel right    the loop, on a terminal
    d24_panel.py --mode loop --panel right --inject s120/keys-clean.txt
                                              the same loop with no finger
"""
import argparse
import json
import os
import random
import sys
import termios
import time

for _p in ('/home/app/dspboot', '/home/app/selftest',
           os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)
import codec4619 as C                                    # noqa: E402

SKIN = 0x1524          # Sys001Skin001 = 5412 -- the RIGHT panel's radio group
ENC = 0x1470           # Sys001Enc001  = 5232 -- the encoder ring

# ---------------------------------------------------------------------------
# THE LEFT PANEL'S OWN CELL (S120-1, PW ruling (a) 2026-09-27)
# ---------------------------------------------------------------------------
# `Sys001SwLeft001`, landed in defs at defs-v2026.09.27 and addressed 5005 by
# the expansion (`MW/D24/MX/_matrix.csv`, Shex 'ikpu'). Before it, BOTH boards
# decoded Sys001Skin001 and the left board's radio indices 1..6 were the right
# board's HOME..FX MUTE, so a value of 3 lit FX on the left AND +48 on the
# right and a press of either arrived identically. That is the aliasing this
# address ends.
#
# IT ONLY ENDS IT ONCE H1S4 CARRIES IT. The address lives in the panel
# firmware's own `MATRIX[]` table (`Core/Inc/matrix.cs`), so until H1S4 is
# rebuilt and reflashed the left board still answers on SKIN and nothing else.
# The loop therefore does not assume: it lights the left board on BOTH cells
# until a press tells it which one that board is running, then uses only that
# one -- and from then on a press arriving on SKIN during a LEFT step is a
# press on the RIGHT board and is recorded as one. `--left-cell` forces it.
#
# 🔴 AND THE FIRMWARE CANNOT BE GIVEN THIS ADDRESS YET, WHICH IS FINDING S120-2
# COMING DUE. The panel firmware's address table is GENERATED from the UNIT'S
# OWN APP PACK, not from defs: H1S4/Core/Inc/matrix.h opens
#
#   // matrix.h - GENERATED on-unit from config/_matrix.mxc (app build
#   // 260714102659)
#   // 2026-08-19: aligns panel fw addresses with the RUNNING app generation.
#   // Do not confuse with the Dropbox MX/matrix.h (newer generation, drifted).
#
# so the flashed panels and the running app agree with each other on 5412, and
# it is THIS REPO's contract (4698) and Dropbox (17553) that are the other two
# generations. The new cell exists in NONE of the app's pack, so there is no
# app-generation address to use -- and its DEFS address is already taken in the
# app's generation:
#
#   H1S4/Core/Inc/matrix.h:4936:  #define Main004EqGain001 5005
#
# Baking 5005 into H1S4 would therefore make an EQ gain change light a
# left-panel indicator once matrix-app is running. It is harmless during a
# factory pass, because matrix-app is stopped for the whole of one and this
# tool is the only writer -- and it is NOT harmless in a product.
#
# SO THE ORDER IS FIXED AND IT IS THE HUB'S: rebuild the app's `_matrix.mxc`
# from defs-v2026.09.27.1 so the app and defs are ONE generation, regenerate
# matrix.h from that pack, and flash BOTH panel boards against it in one go --
# which also moves Sys001Skin001 from 5412 to 4698, so the pack, the app and
# both panel MCUs move together or not at all. Until then this address is the
# factory test's alone and no panel firmware should carry it.
SW_LEFT = 0x138D       # Sys001SwLeft001 = 5005 -- the LEFT panel's radio group
CELL_NAME = {0x1524: 'Sys001Skin001', 0x138D: 'Sys001SwLeft001',
             0x1470: 'Sys001Enc001'}
# Which cell each panel's radio group is on, once it is known.
PANEL_CELL = {'right': SKIN, 'left': None}      # None = not yet identified

# ---------------------------------------------------------------------------
# What is on each panel
# ---------------------------------------------------------------------------
# `idx` is the firmware's own radio index (matrix.cs `rsw[]`/`wled[]` order,
# which is also fw.csv's SkinNum): the value a press sends and the value that
# lights that button's indicator.  `sw` and `led` are catalog row numbers.
#
# The sweep order is the catalog's own `order` column -- the walk S113 took off
# the workbook -- so the hand crosses the panel once rather than jumping about.
RIGHT = [
    # idx, name,            sw row, led row, what the indicator is
    (6,  'FX MUTE',          59, 61, 'the RED ring'),
    (1,  'HOME',             62, 63, 'the white ring'),
    (2,  'MENU',             64, 65, 'the white ring'),
    (3,  '+48',              66, 67, 'the white ring'),
    (4,  'FEEDBACK',         68, 69, 'the white ring'),
    (7,  'MUTE',             70, 71, 'the white ring'),
    (8,  'SCENE',            72, 73, 'the white ring'),
    (9,  'L',                74, 75, 'the white ring'),
    (10, 'C',                76, 77, 'the white ring'),
    (5,  'CH ASSIGN',        79, 80, 'the white ring'),
    (11, 'R',                81, 82, 'the white ring'),
    (12, 'MONITOR',          83, 84, 'the white ring'),
    (13, 'REC/PLY',          85, 87, 'the RED ring'),
    (14, 'STUDIO CTL',       88, 89, 'the white ring'),
]
LEFT = [
    (1, 'MONO AUX',          43, 44, 'the white pair'),
    (2, 'STEREO AUX',        45, 46, 'the white pair'),
    (3, 'FX',                47, 48, 'the white pair'),
    (4, 'EQ',                49, 50, 'the white pair'),
    (5, 'AUX ON FADERS',     51, 52, 'the white pair'),
    (6, 'OVERVIEW',          53, 54, 'the white pair'),
]

# Two indicators on the right panel are NOT in the radio group: `MainInit()`
# drives PB11 and PF1 high and leaves them there, so they are lit whenever the
# unit is on and no write can move them.  One question grades both.
ALWAYS_ON = {
    'right': ([60, 86],
              'the white ring around FX MUTE and the white ring around REC/PLY'),
}

# The encoder is the right panel's alone: rows 90 (the ring turns) and 91 (its
# eight indicators step round).
ENC_ROWS = {'right': (90, 91)}

# Rows this station reaches the panel for and still cannot grade, each with the
# reason in the words the report prints.  Nothing here is invented: it is what
# the firmware table and the netlist say.
UNREACHED = {
    'right': {
        78: ('no indicator is declared for this designator: the firmware table '
             'gives the C button one indicator pair and the loop grades it on '
             'row 77'),
        92: ('the talkback switch and its two indicators pass through the panel '
             'processor with no matrix cell bound, so the host can neither read '
             'the switch nor light the indicators'),
        93: ('the mini-jack sense passes through the panel processor with no '
             'matrix cell bound, so the host cannot read it'),
        94: ('the temperature, blower and fan lines pass through the panel '
             'processor with no matrix cell bound, so the host cannot read them'),
    },
    'left': {
        55: ('the red indicator is driven by the processor boot pin, not by the '
             'processor, so nothing the host writes can light it'),
        58: ('the pedal path through this panel needs the pedal and its lead, '
             'which is the foot pedal station'),
    },
}

PANELS = {'right': RIGHT, 'left': LEFT}
PANEL_NAME = {'right': 'right switch panel', 'left': 'left switch panel'}


def wording(side, num):
    """What the operator is told for one row, and what grades it.

    The loop does not put one dialog in front of each row -- it lights one
    indicator and reads one key code -- but every row it grades still has its
    own wording, and this is where it is written so `--dump-dialogs` can print
    the whole station for review in one file."""
    for idx, name, sw, led, what in PANELS[side]:
        if num == sw:
            return ('Press the button that is lit: %s.' % name, '',
                    "the key code that comes back is %s's" % name)
        if num == led:
            return ('%s is lit under %s; press that button. If nothing lit, '
                    'press NOT LIT.' % (what.capitalize(), name), '',
                    'the operator pressed the button under the lit indicator')
    if side in ALWAYS_ON and num in ALWAYS_ON[side][0]:
        return ('Look at %s.' % ALWAYS_ON[side][1],
                'Are both lit?', '')
    if side in ENC_ROWS:
        turn, leds = ENC_ROWS[side]
        if num == turn:
            return ('Turn the encoder ONE click clockwise, then ONE click '
                    'anticlockwise.', '',
                    'the ring position steps both ways')
        if num == leds:
            return ('The eight indicators around the encoder are stepped round '
                    'twice.', 'Did all eight light in turn?', '')
    return ('', '', '')


def rows_for(side):
    """Every catalog row this loop grades on one panel: the sweep's two rows per
    button, the indicators that are lit whenever the unit is on, and the
    encoder's pair."""
    out = set()
    for _idx, _name, sw, led, _what in PANELS[side]:
        out.add(sw)
        out.add(led)
    if side in ALWAYS_ON:
        out.update(ALWAYS_ON[side][0])
    if side in ENC_ROWS:
        out.update(ENC_ROWS[side])
    return out


# ---------------------------------------------------------------------------
# The bus
# ---------------------------------------------------------------------------
class PanelBus:
    """The matrix bus, seen as the two things the loop needs: light one, and
    tell me what was pressed.

    Reads are drained continuously rather than in windows.  MH1 puts a ':'/'.'
    heartbeat on the same line every 250 ms and a key report is not newline
    aligned with it, so the stream is parsed for the CELL, never for a line."""

    def __init__(self, port=C.PORT, run=True):
        self.bus = C.Bus(port)
        self.buf = b''
        self.lit = None
        if run:
            # S_RUN: MH1 may have been left in its flash dispatcher.
            self.bus.send(b'+\n')
            time.sleep(1.0)
        self.flush()

    def close(self):
        self.bus.close()

    def flush(self):
        termios.tcflush(self.bus.fd, termios.TCIFLUSH)
        self.buf = b''

    def light(self, value, cells=(SKIN,)):
        """Write the radio cell(s) and wait for MH1's ack on each. Returns the
        last ack in ms, or None the moment one write is not acked.

        `cells` defaults to `(SKIN,)` for every caller that only ever knew one
        cell (`mode_probe`, `mode_rtt`, `mode_light`); `loop()` passes
        `cells_for()`'s list, which is TWO cells while a left-board step's
        firmware is unidentified (S129) -- both must be written, so a press
        from either board still lands during that window.

        `CheckHost()` forwards the line to the bus, waits for the slave UART to
        go idle and only THEN writes S_RUN back, so the ack is stamped after the
        last byte has reached both panels -- it is the hop, not a guess at it."""
        self.lit = value
        ms = None
        for cell in cells:
            self.flush()
            self.bus.send(C.cell_line(cell, value))
            ms = self._wait_raw(lambda o: b'+' in o, 0.5)
            if ms is None:
                return None
        return ms

    def light_enc(self, value):
        self.flush()
        t0 = time.time()
        self.bus.send(C.cell_line(ENC, value))
        return self._wait_raw(lambda o: b'+' in o, 0.5)

    def _wait_raw(self, pred, secs):
        t0 = time.time()
        out = b''
        while time.time() - t0 < secs:
            try:
                out += os.read(self.bus.fd, 512)
            except BlockingIOError:
                time.sleep(0.0005)
                continue
            if pred(out):
                return (time.time() - t0) * 1000.0
        return None

    def poll(self):
        """Drain the port and return every completed cell event since the last
        call, as (cell, value) with cell in ('skin', 'swleft', 'enc').

        'swleft' is the left panel's own cell (S129). A press that arrives on
        it can only have come from the left board, and a press on 'skin' can
        only have come from the right -- which is the whole point of giving the
        left board an address of its own."""
        try:
            self.buf += os.read(self.bus.fd, 1024)
        except BlockingIOError:
            pass
        except OSError:
            pass
        events = []
        for name, addr in (('skin', SKIN), ('swleft', SW_LEFT), ('enc', ENC)):
            pre = C.cell_prefix(addr)
            events += [(name, v, pos) for v, pos in _all_replies(self.buf, pre)]
        events.sort(key=lambda e: e[2])
        if events:
            # Keep only the tail that has not been consumed: everything up to
            # the last complete match is done with.
            cut = max(e[2] for e in events)
            self.buf = self.buf[cut:]
        elif len(self.buf) > 4096:
            self.buf = self.buf[-512:]
        return [(n, v) for n, v, _ in events]

    def wait_key(self, timeout, tick=None):
        """Block until a key event arrives or `timeout` runs out.

        `tick` is called about every 50 ms and may return a value; the first
        value it returns that is not None ends the wait and is handed back as
        ('glass', value).  That is how the operator's NOT LIT button and a
        press on the panel race each other for the same step."""
        t0 = time.time()
        last = t0
        while time.time() - t0 < timeout:
            for ev in self.poll():
                return ev + ((time.time() - t0) * 1000.0,)
            if tick is not None and time.time() - last >= 0.05:
                last = time.time()
                got = tick()
                if got is not None:
                    return ('glass', got, (time.time() - t0) * 1000.0)
            time.sleep(0.002)
        return None


def _all_replies(raw, prefix):
    """Every completed `prefix<digits>` token in `raw`, with its end offset.

    The same bounded match `codec4619.parse_reply` uses and for the same
    reason, but it returns ALL of them: a loop that drops the earlier of two
    presses that arrived in one drain would score the second press against the
    first step."""
    import re
    text = raw.decode('ascii', 'replace')
    pat = re.compile('(?<![%s%s])%s([%s]{0,2})(?=[^%s])'
                     % (C.AX, C.DX, prefix, C.DX, C.DX))
    out = []
    for m in pat.finditer(text):
        tail = m.group(1)
        out.append((int(tail, 16) if tail else 0, m.end()))
    return out


class InjectedBus:
    """The same two operations with no unit behind them: a scripted key stream.

    This is what proves the runner side without a finger at the bench.  The
    script is one event per line:

        <delay_ms> <value>        a press: that button's radio index
        <delay_ms> enc <value>    an encoder detent
        <delay_ms> glass notlit   the operator says the indicator stayed dark
        <delay_ms> -              nothing at all: a dead switch

    Every fault the loop has to grade can be played this way, which is how the
    runner side is proved with no finger at the bench."""

    def __init__(self, path):
        self.script = []
        for ln in open(path):
            ln = ln.split('#', 1)[0].strip()
            if not ln:
                continue
            parts = ln.split()
            delay = float(parts[0])
            if parts[1] == 'enc':
                self.script.append((delay, 'enc', int(parts[2])))
            elif parts[1] == 'glass':
                self.script.append((delay, 'glass', parts[2]))
            elif parts[1] == '-':
                self.script.append((delay, 'silence', 0))
            else:
                self.script.append((delay, 'skin', int(parts[1])))
        self.i = 0
        self.lit = None
        self.lights = []

    def close(self):
        pass

    def flush(self):
        pass

    def light(self, value, cells=(SKIN,)):
        self.lit = value
        for cell in cells:
            self.lights.append(('swleft' if cell == SW_LEFT else 'skin', value))
        return 1.8

    def light_enc(self, value):
        self.lights.append(('enc', value))
        return 1.8

    def poll(self):
        return []

    def wait_key(self, timeout, tick=None):
        if tick is not None:
            got = tick()
            if got is not None:
                return ('glass', got, 0.0)
        if self.i >= len(self.script):
            return None
        delay, kind, value = self.script[self.i]
        self.i += 1
        if kind == 'silence':
            return None
        time.sleep(min(delay, 50.0) / 1000.0)
        return (kind, value, delay)

    def exhausted(self):
        return self.i >= len(self.script)


# ---------------------------------------------------------------------------
# The loop
# ---------------------------------------------------------------------------
PASS, FAIL, NODATA, SKIPPED = 'PASS', 'FAIL', 'NO DATA', 'SKIPPED'


class Step(object):
    """One button's turn in the loop, and the two rows it grades."""

    def __init__(self, idx, name, sw_row, led_row, what):
        self.idx, self.name = idx, name
        self.sw_row, self.led_row, self.what = sw_row, led_row, what
        self.sw = self.led = None
        self.sw_note = self.led_note = ''
        self.ms = None
        self.got = None


# WHAT A PRESS PROVES, AND WHAT IT DOES NOT (S128, second pass).
#
# The loop grades TWO rows off one press: the switch, and the indicator above
# it. The indicator half is an INFERENCE -- "it lit, and the operator pressed
# the button under it" -- and the inference is only sound if an operator who
# saw nothing light had a way to SAY SO. On the dialog they do: NOT LIT is one
# of the buttons. On the armed factory screen there are two buttons, ENTER and
# PAUSE, and no way to report a dark indicator at all.
#
# It matters because the instruction NAMES the button ("press the button that
# is lit: MONO AUX"). A worker who can read will press MONO AUX whether or not
# anything lit, and the loop then records that they saw it light.
#
# THEY HAVE NOT BEEN SEEING IT LIGHT. Read off the shipping panel firmware on
# MW-D24-2, 2026-09-27, both boards:
#
#   * `MX_GPIO_Init()` configures EVERY panel pin `GPIO_MODE_INPUT` with a
#     pull-up -- the LED pins included.
#   * the block in `MainInit()` that made the indicator pins outputs is
#     COMMENTED OUT, on H1S3 and on H1S4 alike.
#   * H1S3 then makes exactly TWO pins outputs, PB11 and PF1, and drives them
#     permanently high: the two "always on white led next to red led".
#     H1S4 makes none.
#
# So `WrRadioLed()` writes ODR bits on input pins and nothing moves. The only
# lit indicators on the whole front panel are the right board's two always-on
# whites -- which is exactly what PW reported: "right board switch test didn't
# illuminate buttons", "the bottom 3 buttons never illuminated" (MONITOR,
# REC/PLY and STUDIO CTL have no always-on white beside them; FX MUTE does).
#
# The firmware is not this repo's to change. What IS this repo's is not
# claiming a reading nobody took: where the operator could not have said "it
# did not light", the indicator row is NO DATA with the reason.
LED_NOT_SEEN = ('the screen named the button, and it has no way to say an '
                'indicator stayed dark, so the press proves the switch and '
                'nothing about the indicator')


def cells_for(panel, known=None):
    """Which radio cell(s) to write for one panel (S129).

    The right panel is Sys001Skin001 and always has been. The left panel is
    Sys001SwLeft001 from defs-v2026.09.27 -- but only once H1S4 carries that
    address in its own `MATRIX[]`, so until a press says which cell that board
    is running, BOTH are written and the answer identifies the firmware.
    Writing SKIN for a left step lights the right board's same index too, which
    is exactly the aliasing the new cell exists to end; it is done only while
    the board is unidentified, and it stops the moment it answers.
    """
    if panel != 'left':
        return [SKIN]
    if known == SW_LEFT:
        return [SW_LEFT]
    if known == SKIN:
        return [SKIN]
    return [SW_LEFT, SKIN]


def loop(bus, panel, ask, timeout=30.0, log=print, owed=None, hold=None,
         can_say_notlit=True, left_cell='auto', random_order=False):
    """Walk one panel.  `ask` puts the step in front of the operator and returns
    the button they pressed on the glass, or None if they have not pressed one
    yet -- it is polled, because the panel and the glass race for every step.

    `random_order`: S130 item 5, behind a flag, default OFF (PW has not ruled
    on it). The design problem it answers is S129 item 4's: with no
    indicator readback, a
    dark panel and a screen that NAMES the button are indistinguishable from a
    dead switch that just happens to be lit -- PW's own pass proved it (S129
    HANDS ADDENDUM 7 / the FX MUTE / HOME / MENU mis-fires, an operator hunting
    a dark panel, not three switch faults). With `random_order` the walk order
    is shuffled and `ask` is expected to stop naming the button (see
    `d24_live.panel_press_words_blind`/`panel_retry_words_blind`): a correct
    key code then proves both that the switch works AND that the operator saw
    the light, because reading the name off the glass can no longer produce
    it. Grading is unchanged -- `st.idx` is still matched by VALUE, never by
    position -- so this only permutes `steps` before the walk.

    `hold`, if given, is called before each indicator is lit and may block. It
    is how the panel loop stays out of the acoustic test's way (S126, ruling a):
    the panel microphone hears button clicks, so while the speaker is sounding
    the next indicator waits rather than inviting a press. It is a HOLD, never a
    skip -- the button is still lit, still pressed and still graded; only the
    moment moves, by about a second.

    Returns (steps, extra) where `extra` carries the rows that are not part of
    the sweep: the always-lit indicators, the encoder, and the rows this station
    cannot reach.

    `can_say_notlit` is False when the operator is behind the ARMED FACTORY
    SCREEN, which draws no dialog and therefore offers no NOT LIT button. See
    LED_NOT_SEEN: the indicator half of each step is then recorded as not
    measured rather than inferred from a press."""
    steps = [Step(*s) for s in PANELS[panel]]
    if random_order:
        random.shuffle(steps)
    # WHICH CELL THIS BOARD IS ON. 'auto' finds out from the first press;
    # 'new'/'shared' force it, for a bench run that knows what is flashed.
    known = {'new': SW_LEFT, 'shared': SKIN}.get(left_cell)
    if panel != 'left':
        known = SKIN
    said_cell = False
    if owed is not None:
        # A button whose two rows have both already passed is not lit again:
        # no test runs twice for the same proof (PW 09-26). The sweep keeps its
        # order, so the hand still crosses the panel once.
        steps = [s for s in steps if s.sw_row in owed or s.led_row in owed]
    for n, st in enumerate(steps):
        if hold is not None:
            hold(log)
        cells = cells_for(panel, known)
        if not said_cell:
            said_cell = True
            log('the %s is lit on %s'
                % (PANEL_NAME[panel],
                   ' and '.join(CELL_NAME.get(c, hex(c)) for c in cells)
                   + (' (both, until a press says which one this board runs)'
                      if len(cells) > 1 else '')))
        ack = bus.light(st.idx, cells)
        # THE ACK IS A MEASUREMENT AND IT IS WORTH PRINTING. It separates "the
        # host could not even get the write to the panel" from "the write went
        # out and nothing lit", which is the whole of the question PW asked
        # about the bottom three buttons.
        log('light %d (%s) - the panel acked the write in %s'
            % (st.idx, st.name,
               ('%.1f ms' % ack) if ack is not None else 'NO ACK'))
        if ack is None:
            st.sw = st.led = NODATA
            st.sw_note = st.led_note = 'the panel bus did not acknowledge the write'
            continue
        tries = 0
        while True:
            answer = ask(st, n, len(steps), tries)
            got = bus.wait_key(timeout, tick=answer)
            if got is None:
                st.sw = NODATA
                st.led = NODATA
                st.sw_note = 'no key code arrived within %.0f s' % timeout
                st.led_note = 'not reached: the button sent nothing'
                break
            kind, value, ms = got
            if kind == 'glass':
                if value == 'notlit':
                    st.led = FAIL
                    st.led_note = '%s did not light when the tester lit it' % st.what
                    tries += 1
                    continue
                st.sw = st.led = SKIPPED
                st.sw_note = st.led_note = 'the operator skipped this button'
                break
            if kind not in ('skin', 'swleft'):
                continue                       # an encoder detent in the middle
            # WHICH BOARD PRESSED IT (S129). A press on Sys001SwLeft001 can
            # only be the LEFT board and a press on Sys001Skin001 can only be
            # the RIGHT one, so the cell the press arrived on IS the board --
            # the thing the shared cell could never tell anybody.
            from_cell = SW_LEFT if kind == 'swleft' else SKIN
            if known is None:
                known = from_cell
                log('the %s answered on %s, so that is the cell this board '
                    'runs; the other one is not written again'
                    % (PANEL_NAME[panel], CELL_NAME.get(from_cell)))
            elif from_cell != known:
                # The wrong board. Before S129 this arrived on the same cell as
                # a right press of the same index and was graded as a pass.
                st.sw = FAIL
                st.sw_note = ('that press came from the %s, not the %s: it '
                              'arrived on %s'
                              % ('left switch panel' if kind == 'swleft'
                                 else 'right switch panel',
                                 PANEL_NAME[panel],
                                 CELL_NAME.get(from_cell)))
                if st.led is None:
                    st.led = NODATA
                    st.led_note = ('not reached: the press came from the other '
                                   'switch board')
                break
            st.got, st.ms = value, ms
            if value == st.idx:
                st.sw = PASS
                st.sw_note = 'key code %d in %.0f ms' % (value, ms)
                if st.led is None:
                    if can_say_notlit:
                        st.led = PASS
                        st.led_note = ('%s lit, and the operator pressed the '
                                       'button under it' % st.what)
                    else:
                        st.led = NODATA
                        st.led_note = LED_NOT_SEEN
                break
            other = dict((s.idx, s.name) for s in steps).get(value)
            st.sw = FAIL
            st.sw_note = ('the tester lit %s and the key code that came back was '
                          '%d%s' % (st.name, value,
                                    ' (%s)' % other if other else ''))
            if st.led is None:
                st.led = NODATA
                st.led_note = 'not reached: the wrong key code came back'
            break
    extra = {}
    if panel in ALWAYS_ON:
        extra['always_on'] = ALWAYS_ON[panel]
    if panel in ENC_ROWS:
        extra['encoder'] = ENC_ROWS[panel]
    extra['unreached'] = UNREACHED.get(panel, {})
    return steps, extra


def encoder_leds(bus, laps=2, dwell=0.12):
    """Step the ring's eight indicators round, twice.  Nothing to read back --
    this one is the operator's eye."""
    for _ in range(laps):
        for v in range(1, 9):
            bus.light_enc(v)
            time.sleep(dwell)
    bus.light_enc(0)


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------
def mode_probe(a):
    b = C.Bus(a.port)
    try:
        b.send(b'+\n')
        time.sleep(1.0)
        b.read(0.3)
        termios.tcflush(b.fd, termios.TCIFLUSH)
        t0 = time.time()
        b.send(b'&\n')
        marks, out = {}, b''
        while time.time() - t0 < 1.5:
            try:
                out += os.read(b.fd, 512)
            except BlockingIOError:
                time.sleep(0.0005)
                continue
            for k in ('H1S1', 'H1S3', 'H1S4'):
                if k not in marks and ('// %s' % k).encode() in out:
                    marks[k] = round((time.time() - t0) * 1000.0, 2)
            if len(marks) == 3:
                break
    finally:
        b.close()
    print(json.dumps({'mode': 'probe', 'mcus_ms': marks,
                      'panels_present': sorted(k for k in marks
                                               if k in ('H1S3', 'H1S4'))}))


def mode_rtt(a):
    bus = PanelBus(a.port)
    out = {'mode': 'rtt', 'light_ms': [], 'key_relay_ms': []}
    try:
        for i in range(a.reps):
            out['light_ms'].append(round(bus.light((i % 14) + 1) or -1, 2))
            time.sleep(0.05)
        bus.light(0)
        for _ in range(max(1, a.reps // 2)):
            bus.flush()
            t0 = time.time()
            bus.bus.send(b'&\n')
            marks, raw = {}, b''
            while time.time() - t0 < 1.0:
                try:
                    raw += os.read(bus.bus.fd, 512)
                except BlockingIOError:
                    time.sleep(0.0005)
                    continue
                for k in ('H1S1', 'H1S3', 'H1S4'):
                    if k not in marks and ('// %s' % k).encode() in raw:
                        marks[k] = round((time.time() - t0) * 1000.0, 2)
                if len(marks) == 3:
                    break
            out['key_relay_ms'].append(marks)
            time.sleep(0.2)
    finally:
        bus.close()
    good = [m for m in out['light_ms'] if m > 0]
    if good:
        out['light_mean_ms'] = round(sum(good) / len(good), 2)
        out['light_max_ms'] = max(good)
    print(json.dumps(out))


def mode_light(a):
    bus = PanelBus(a.port)
    try:
        ms = bus.light_enc(a.value) if a.cell == 'enc' else bus.light(a.value)
        print(json.dumps({'mode': 'light', 'cell': a.cell, 'value': a.value,
                          'ack_ms': None if ms is None else round(ms, 2)}))
        if a.hold:
            time.sleep(a.hold)
    finally:
        bus.close()


def mode_watch(a):
    bus = PanelBus(a.port)
    t0 = time.time()
    print('watching for %.0f s -- press panel buttons' % a.secs, flush=True)
    try:
        while time.time() - t0 < a.secs:
            for kind, value in bus.poll():
                print('%8.3f s  %-4s %d' % (time.time() - t0, kind, value),
                      flush=True)
            time.sleep(0.002)
    finally:
        bus.close()


def mode_loop(a):
    bus = InjectedBus(a.inject) if a.inject else PanelBus(a.port)

    def ask(st, n, total, tries):
        if tries:
            print('\n   %s did not light. Press %s anyway.' % (st.what, st.name),
                  flush=True)
        else:
            print('\n[%d/%d] press the button that is lit: %s   (%s)'
                  % (n + 1, total, st.name, st.what), flush=True)
        return lambda: None

    try:
        steps, extra = loop(bus, a.panel, ask, timeout=a.timeout)
    finally:
        try:
            bus.light(0)
        finally:
            bus.close()
    rows = []
    for st in steps:
        rows.append(dict(num=st.sw_row, name='%s button' % st.name,
                         verdict=st.sw, note=st.sw_note))
        rows.append(dict(num=st.led_row, name='%s indicator' % st.name,
                         verdict=st.led, note=st.led_note))
    print(json.dumps({'mode': 'loop', 'panel': a.panel, 'rows': rows,
                      'unreached': extra['unreached']}, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--mode', required=True,
                    choices=('probe', 'rtt', 'light', 'watch', 'loop'))
    ap.add_argument('--panel', choices=('right', 'left'), default='right')
    ap.add_argument('--cell', choices=('skin', 'enc'), default='skin')
    ap.add_argument('--value', type=int, default=0)
    ap.add_argument('--hold', type=float, default=0.0)
    ap.add_argument('--secs', type=float, default=20.0)
    ap.add_argument('--reps', type=int, default=10)
    ap.add_argument('--timeout', type=float, default=30.0)
    ap.add_argument('--inject', help='a scripted key stream instead of the bus')
    ap.add_argument('--port', default=C.PORT)
    a = ap.parse_args()
    {'probe': mode_probe, 'rtt': mode_rtt, 'light': mode_light,
     'watch': mode_watch, 'loop': mode_loop}[a.mode](a)


if __name__ == '__main__':
    main()
