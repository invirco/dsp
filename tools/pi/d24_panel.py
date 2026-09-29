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
    d24_panel.py --mode resolve               what this run resolved SKIN/ENC/
                                              SW_LEFT/SW_TALK to, and from which
                                              pack (S136) -- no bus, no hands
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
import matrix_addr                                        # noqa: E402

# ADDRESSES ARE RESOLVED BY NAME FROM THIS UNIT'S OWN DEPLOYED PACK (S136),
# never baked in: SKIN was 5412 (0x1524) on MW-D24-2's 2026-08-18 pack and is
# 4698 after the S131 switch-over, same name both times. SKIN and ENC are
# core to every generation this tool has run against -- a pack that lacks
# either is broken, not "not yet switched over", and gets no fallback.
CELL_NAMES = {'skin': 'Sys001Skin001', 'enc': 'Sys001Enc001',
              'swleft': 'Sys001SwLeft001', 'swtalk': 'Sys001SwTalk001',
              'mjsw': 'Sys001SwMiniJack001', 'tempfan': 'Sys001SwTempFan001'}


def _resolve_required(key):
    addr, err = matrix_addr.try_resolve(CELL_NAMES[key])
    if addr is None:
        sys.exit('FATAL: %s' % err)
    return addr


SKIN = _resolve_required('skin')      # Sys001Skin001 -- the RIGHT panel's radio group
ENC = _resolve_required('enc')        # Sys001Enc001  -- the encoder ring

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
#
# UNLIKE SKIN/ENC, THIS ONE IS EXPECTED TO BE ABSENT SOMETIMES: it lands in
# defs at defs-v2026.09.27 and is not on any pack built before it (MW-D24-2's
# 08-18 pack included). `SW_LEFT` is the address once the deployed pack
# carries the name, `SW_LEFT_ABSENT` is the reason string when it does not --
# never a guess, never a crash, see `loop()`.
SW_LEFT, SW_LEFT_ABSENT = matrix_addr.try_resolve(CELL_NAMES['swleft'])
# `Sys001SwTalk001` -- the talkback switch/LEDs cell, defs-v2026.09.27.3. Not
# wired into this tool's read/light logic yet (that is S135's bespoke H1S3
# image, still optional); its presence only changes ROW 92's reason below.
SW_TALK, SW_TALK_ABSENT = matrix_addr.try_resolve(CELL_NAMES['swtalk'])
# `Sys001SwMiniJack001`/`Sys001SwTempFan001` -- the mini-jack insertion sense
# and TEMP/BLOWER/FAN pass-through, both landed in defs at generation
# `46109e9fb812` (gaps doc 2.2/2.3, S138). Resolved here so `poll()` can
# surface them, but S138 did NOT wire a graded MJ1/TF1 check off them: both
# cells are PUSHED ON CHANGE, not held, so a read with no fresh edge in the
# window is indistinguishable from "no traffic yet" -- see findings.md
# S138-4. Present here as read-only infrastructure for that to be finished.
MJSW, MJSW_ABSENT = matrix_addr.try_resolve(CELL_NAMES['mjsw'])
TEMPFAN, TEMPFAN_ABSENT = matrix_addr.try_resolve(CELL_NAMES['tempfan'])

# The same four by key, so a table row can name the cell it wants rather than
# carrying an address (S136: by name, never a literal) -- see `SENSE` below.
CELL_ADDR = {'skin': SKIN, 'enc': ENC, 'swleft': SW_LEFT, 'swtalk': SW_TALK,
             'mjsw': MJSW, 'tempfan': TEMPFAN}
CELL_ABSENT = {'swleft': SW_LEFT_ABSENT, 'swtalk': SW_TALK_ABSENT,
               'mjsw': MJSW_ABSENT, 'tempfan': TEMPFAN_ABSENT}

CELL_NAME = {SKIN: CELL_NAMES['skin'], ENC: CELL_NAMES['enc']}
if SW_LEFT is not None:
    CELL_NAME[SW_LEFT] = CELL_NAMES['swleft']
if SW_TALK is not None:
    CELL_NAME[SW_TALK] = CELL_NAMES['swtalk']
if MJSW is not None:
    CELL_NAME[MJSW] = CELL_NAMES['mjsw']
if TEMPFAN is not None:
    CELL_NAME[TEMPFAN] = CELL_NAMES['tempfan']
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
    (6,  'FX MUTE',          59, 61, 'the RED LED'),
    (1,  'HOME',             62, 63, 'the white LED'),
    (2,  'MENU',             64, 65, 'the white LED'),
    (3,  '+48',              66, 67, 'the white LED'),
    (4,  'FEEDBACK',         68, 69, 'the white LED'),
    (7,  'MUTE',             70, 71, 'the white LED'),
    (8,  'SCENE',            72, 73, 'the white LED'),
    (9,  'L',                74, 75, 'the white LED'),
    (10, 'C',                76, 77, 'the white LED'),
    (5,  'CH ASSIGN',        79, 80, 'the white LED'),
    (11, 'R',                81, 82, 'the white LED'),
    (12, 'MONITOR',          83, 84, 'the white LED'),
    (13, 'REC/PLY',          85, 87, 'the RED LED'),
    (14, 'STUDIO CTL',       88, 89, 'the white LED'),
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
              'the white LED on FX MUTE and the white LED on REC/PLY'),
}

# The encoder is the right panel's alone: rows 90 (the ring turns) and 91 (its
# eight indicators step round).
ENC_ROWS = {'right': (90, 91)}

# Rows this station reaches the panel for and still cannot grade, each with the
# reason in the words the report prints.  Nothing here is invented: it is what
# the firmware table and the netlist say.
def _talkback_reason():
    if SW_TALK is None:
        return SW_TALK_ABSENT
    return ('%s exists on this unit\'s pack (address %d) but this tool has no '
            'read/light logic wired to it yet -- that is S135\'s bespoke H1S3 '
            'image, still optional' % (CELL_NAMES['swtalk'], SW_TALK))


UNREACHED = {
    'right': {
        78: ('no indicator is declared for this designator: the firmware table '
             'gives the C button one indicator pair and the loop grades it on '
             'row 77'),
        92: _talkback_reason(),
        # 94 IS GRADED NOW (S138b, gaps doc 2.3). It was "no matrix cell bound"
        # until S138 bound it and "no graded check wired yet" until this
        # session wired `sense_sweep()` below -- a second, read-only pass over
        # the SAME open bus, run from `panel_station` right after the sweep,
        # because it is not a light-one/press-one row.
        # 93 is graded by the ANALOG station's mini-jack step (PW's addendum of
        # 2026-09-28) and is kept out of this table AND out of `SENSE` so that
        # neither station claims it -- see `d24_runall.GRADED_ELSEWHERE`.
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
                    'the encoder position steps both ways')
        if num == leds:
            return ('The eight indicators around the encoder are stepped round '
                    'twice.', 'Did all eight light in turn?', '')
    # The sense rows (S138b). A phase with no instruction asks the operator for
    # nothing -- row 94's read half is a temperature count, so there is nothing
    # for them to do -- and the action line says so rather than being blank.
    for row in SENSE.get(side, ()):
        if num == row.num:
            acts = [i for i, _c in row.phases if i]
            return (' '.join(acts) if acts
                    else 'Nothing to do: the tester listens for %s.' % row.what,
                    '', 'the cell reports %s while the tester is listening'
                    % ' and then '.join(c for _i, c in row.phases))
    return ('', '', '')


def rows_for(side):
    """Every catalog row this STATION grades on one panel: the sweep's two rows
    per button, the indicators that are lit whenever the unit is on, the
    encoder's pair, and -- since S138b -- the read-only sense rows.

    THE SENSE ROWS ARE IN HERE AND NOT IN `PANELS`, and the distinction is the
    one `panel_station` makes too: they are graded by the same station, on the
    same open bus, but by `sense_sweep` rather than by the button sweep. What
    this set decides is whether `d24_runall.manual_step` calls the row a LOOP
    row at all -- and a row left out of it comes back BLOCKED, which makes it
    category 'not-run', which lets `record_not_run` FORCE a NOT TESTED over the
    verdict `sense_sweep` had just landed. That is what this line fixes.
    """
    out = set()
    for _idx, _name, sw, led, _what in PANELS[side]:
        out.add(sw)
        out.add(led)
    if side in ALWAYS_ON:
        out.update(ALWAYS_ON[side][0])
    if side in ENC_ROWS:
        out.update(ENC_ROWS[side])
    out.update(sense_rows_for(side))
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
        for name, addr in (('skin', SKIN), ('swleft', SW_LEFT), ('enc', ENC),
                          ('mjsw', MJSW), ('tempfan', TEMPFAN)):
            if addr is None:
                continue        # not on this unit's pack (S136); nothing to match
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

    and, for the sense rows (S138b), the same line shape with the cell named:

        <delay_ms> mjsw <value>     MJ_SW pushed this value
        <delay_ms> tempfan <value>  the TEMP raw count was pushed

    Every fault the loop has to grade can be played this way, which is how the
    runner side is proved with no finger at the bench."""

    # The cells a scripted line may name. `poll()` hands these back the way
    # `PanelBus.poll` does, so `sense_sweep` cannot tell the two apart.
    POLLED = ('mjsw', 'tempfan')

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
            elif parts[1] in self.POLLED:
                self.script.append((delay, parts[1], int(parts[2])))
            elif parts[1] == '-':
                self.script.append((delay, 'silence', 0))
            else:
                self.script.append((delay, 'skin', int(parts[1])))
        self.i = 0
        self.lit = None
        self.lights = []
        self.flushes = 0

    def close(self):
        pass

    def flush(self):
        # COUNTED, because the drain-before-the-prompt ordering is the whole
        # mechanism of the sense rows and a proof has to be able to assert it.
        self.flushes += 1

    def light(self, value, cells=(SKIN,)):
        self.lit = value
        for cell in cells:
            self.lights.append(('swleft' if cell == SW_LEFT else 'skin', value))
        return 1.8

    def light_enc(self, value):
        self.lights.append(('enc', value))
        return 1.8

    def poll(self):
        """The next scripted event, if it is one of the polled cells.

        A `silence` line is how a script says "this phase gets nothing", and a
        button/encoder line is left where it is: `poll` is the sense rows' read
        and `wait_key` is the button sweep's, and a script that drives both
        must not have one of them eat the other's events.
        """
        if self.i >= len(self.script):
            return []
        delay, kind, value = self.script[self.i]
        if kind == 'silence':
            self.i += 1
            return []
        if kind not in self.POLLED:
            return []
        self.i += 1
        time.sleep(min(delay, 50.0) / 1000.0)
        return [(kind, value)]

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
# Same string d24_runall.State/d24_selftest use for "nobody asked the
# question" (S137): NOT LIT is PW's ruling that a dark LED is never asked
# about the switch underneath it, so the switch is NOT TESTED, not SKIPPED
# (SKIPPED is the operator declining a button that WAS asked).
NOTTESTED = 'NOT TESTED'


# ---------------------------------------------------------------------------
# THE SENSE ROWS: graded BY LISTENING DURING THE OPERATOR'S ACTION (S138b)
# ---------------------------------------------------------------------------
# Rows 93 (mini-jack insertion sense, MJ_SW) and 94 (TEMP / BLOWER / FAN
# pass-through), gaps doc 2.2/2.3, PW 2026-09-28.
#
# WHY THIS SHAPE AND NOT A READ. Both cells are PUSHED ON CHANGE, not held --
# `mx_master.csv` for `Sys[1-1]SwMiniJack[1-1]` says "both edges are reported"
# in as many words -- so a read taken AFTER the operator has acted cannot be
# told from "nothing has been transmitted yet". That is finding S138-4, and it
# is what blocked the graded check. The answer is not a better read: it is to
# be LISTENING while the operator acts. So each phase is
#
#     drain the port  ->  put the instruction up  ->  poll until the edge
#
# in that order, and the drain is before the prompt so that nothing the
# operator does can land in a window this code is not yet watching.
#
# NOTHING HERE WRITES. `Sys001SwTempFan001`'s WRITE half is the BLOWER/FAN
# drive mask (mx_master: "WRITE = the drive mask bit0 = BLOWER bit1 = FAN"),
# which is a fan and a blower on a real unit, so "write something to provoke a
# reply" is out of bounds -- this session's dispatch says so and so does
# sense. There is no `light()` call and no `cell_line()` in this whole block.
#
# 🔴 AND ON TODAY'S UNIT NEITHER CELL CAN ANSWER, which is why "no traffic at
# all" is a verdict of its own and not a FAIL. The flashed H1S3 image carries
# generation `e80ccab5d6d8`; these cells landed at `46109e9fb812`, and S139
# measured "0 shared at the same address" between those two generations. The
# flashed `matrix.cs` also has no MJ_SW read, no PA1 TEMP read and no
# BLOWER/FAN drive in it at all (the shipped H1S3-A variant is declare-only).
# So a factory pass on today's unit must say "this unit's panel firmware does
# not carry this cell", never "the jack is broken" -- see SENSE_NO_TRAFFIC.
SENSE_NO_TRAFFIC = (
    'nothing was transmitted on %s during the window, so there is no edge to '
    'grade. This is a panel-firmware precondition and NOT a fault in the jack '
    'or the sensor: the cell is only answered once H1S3 is rebuilt against a '
    'generation that carries it and reads the net. Re-run this row after that '
    'reflash')


class SenseRow(object):
    """One sense row: what the operator is asked to do, and what must move.

    `phases` is a list of (instruction, what_the_change_is_called). A phase
    with an empty instruction asks the operator for nothing and is a plain
    listen -- which is all row 94's READ half can be, because its read is the
    TEMP raw count and the only switch-like half it has is the WRITE this
    never touches.

    `band` is (low, high) EXCLUSIVE on the value, or None for no band. It is
    the sensor-connected check, not a temperature: a raw count sitting on
    either rail is a short or an open, and what counts as a plausible DEGREE
    is PW's, unruled, and recorded rather than invented here.
    """

    def __init__(self, num, cell_key, what, phases, band=None, note=''):
        self.num, self.cell_key, self.what = num, cell_key, what
        self.phases, self.band, self.note = phases, band, note


# 🔴 ROW 93 IS NOT HERE, AND THAT IS PW'S ADDENDUM OF 2026-09-28: "ONE
# INSERTION, TWO RESULTS". The mini-jack insertion sense is NOT its own
# station -- the detect is folded into the mini-jack step of the ANALOG patch
# loop (`d24_patch.Station.mj_sense`), so one plug going into one socket gives
# both the L/R signal test and the jack-switch detect. The listen arms before
# that step's own "insert" instruction, so it costs the operator nothing.
# `d24_runall.GRADED_ELSEWHERE` is what stops the panel station claiming it.
SENSE = {
    'right': [
        SenseRow(94, 'tempfan', 'the temperature sense',
                 [('', 'a temperature reading')], band=(0, 255),
                 note='READ-ONLY, and a plain listen: the read half is the '
                      'TEMP raw count, so there is no operator action that '
                      'moves it and the WRITE half is the BLOWER/FAN drive '
                      'mask, which is never written. The band is 0 < count < '
                      '255 -- a count on either rail is a short or an open. '
                      'The catalog\'s own criterion ("moves with the unit\'s '
                      'own warm-up", twice 10 min apart) is a second, '
                      'session-spanning reading and is still owed (S138b-3)'),
    ],
}


def sense_rows_for(side):
    return [s.num for s in SENSE.get(side, ())]


def sense_sweep(bus, side, ask, timeout=30.0, log=print, owed=None,
                idle=None):
    """Grade the sense rows of one board by listening while the operator acts.

    `ask(instruction, row, phase_n, phase_total)` puts one phase's instruction
    on the glass and returns a `tick()` callable exactly as the button sweep's
    `ask` does -- polled between bus reads, so PAUSE stays live. A phase with
    an empty instruction is not asked at all and is listened through.

    `idle` is the tick for those unasked phases: nothing on the glass changes,
    but the run has to go on saying it is alive. Without it a 30 s listen with
    no instruction (the temperature sense, row 94) let the factory screen's
    heartbeat go stale, the screen took the run for dead and offered START,
    and a press there tried to launch a second run ("the test did not start",
    PW 2026-09-29).

    Returns {row number: (verdict, note)}.
    """
    out = {}
    for row in SENSE.get(side, ()):
        if owed is not None and row.num not in owed:
            continue
        addr = CELL_ADDR.get(row.cell_key)
        if addr is None:
            out[row.num] = (NODATA, CELL_ABSENT.get(row.cell_key)
                            or ('%s is not on this unit\'s pack'
                                % CELL_NAMES[row.cell_key]))
            log('%s: %s' % (row.what, out[row.num][1]))
            continue
        seen, paused = [], False
        for i, (instruction, called) in enumerate(row.phases, 1):
            # THE DRAIN IS THE ARM, AND IT IS BEFORE THE PROMPT.
            bus.flush()
            tick = (ask(instruction, row.num, i, len(row.phases))
                    if instruction else idle)
            got = _listen(bus, row.cell_key, timeout, tick)
            if got == 'pause':
                paused = True
                break
            seen.append((called, got))
        if paused:
            out[row.num] = (NODATA, 'the run was paused during this row')
            break
        missing = [called for called, got in seen if not got]
        if len(missing) == len(seen):
            out[row.num] = (NODATA, SENSE_NO_TRAFFIC
                            % CELL_NAMES[row.cell_key])
        elif missing:
            # SOME traffic but not all the edges: the cell IS answering, so
            # this is a real fault and it is named by the edge that never came.
            out[row.num] = (FAIL, 'no change was reported on %s, although %s '
                            'was: %s answered, so the cell is live and the '
                            'net is not following'
                            % (' or '.join(missing),
                               ' and '.join(c for c, g in seen if g),
                               CELL_NAMES[row.cell_key]))
        else:
            out[row.num] = _sense_verdict(row, seen)
        log('%s (row %d): %s -- %s'
            % (row.what, row.num, out[row.num][0], out[row.num][1]))
    return out


def _listen(bus, key, timeout, tick=None):
    """Every value this cell pushed inside `timeout`, or 'pause'.

    Ends on the FIRST event: an edge is what the phase is waiting for, and
    waiting out the rest of the window after it has arrived is the operator
    standing there for nothing.
    """
    t0 = time.time()
    last = t0
    while time.time() - t0 < timeout:
        for name, value in bus.poll():
            if name == key:
                return [value]
        if tick is not None and time.time() - last >= 0.05:
            last = time.time()
            got = tick()
            if got is not None:
                return 'pause' if got in ('skip', 'pause') else []
        time.sleep(0.002)
    return []


def _sense_verdict(row, seen):
    """Every phase reported something. What that adds up to."""
    vals = [got[0] for _called, got in seen]
    if row.band is not None:
        low, high = row.band
        bad = [v for v in vals if not low < v < high]
        if bad:
            return (FAIL, 'the count read %s, which is on the %s rail: a '
                    'sensor that is shorted or open, not a temperature '
                    '(the plausible DEGREE band is PW\'s and is unruled)'
                    % (', '.join(str(v) for v in bad),
                       'low' if bad[0] <= low else 'high'))
        return (PASS, 'the cell reported %s, inside %d < count < %d'
                % (', '.join(str(v) for v in vals), low, high))
    if len(vals) > 1 and len(set(vals)) == 1:
        # Both actions reported, both the same value: the cell is transmitting
        # but it is not following the jack.
        return (FAIL, 'both actions were reported as the same value (%d), so '
                'the cell is transmitting but not following the jack'
                % vals[0])
    return (PASS, 'a change was reported for %s (%s)'
            % (' and '.join(called for called, _g in seen),
               ', '.join('%s=%d' % (called, got[0]) for called, got in seen)))


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
# saw nothing light had a way to SAY SO. NOT LIT is that way, on the dialog
# AND on the armed factory screen (S137, PW's panel-loop ruling: a second
# button, NOT LIT, is the explicit exception to the armed screen's
# one-button rule, for this step only). `can_say_notlit` stays as a
# parameter for a caller with genuinely no NOT LIT channel at all
# (mode_loop's bare terminal driver, unscripted); every real caller now
# passes True.
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
    if SW_LEFT is None:
        # loop() must never reach here: it short-circuits a left panel to a
        # NOT TESTED result before calling this when the name is absent from
        # this unit's pack (S136). Fail loud rather than write a bare `None`.
        raise matrix_addr.CellNotInPack(CELL_NAMES['swleft'], matrix_addr.generation())
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

    `random_order`: S130 item 5, behind a flag, default OFF -- and STAYS off
    (S137, PW's panel-loop ruling of 2026-09-28: "keeping the leds in the
    same order will speed up operator time"; PW chose the fixed order). The
    design problem it would answer is S129 item 4's: with no indicator
    readback, a dark panel and a screen that NAMES the button are
    indistinguishable from a dead switch that just happens to be lit -- PW's
    own pass proved it (S129 HANDS ADDENDUM 7 / the FX MUTE / HOME / MENU
    mis-fires, an operator hunting a dark panel, not three switch faults).
    With `random_order` the walk order is shuffled and `ask` is expected to
    stop naming the button (see `d24_live.panel_press_words_blind`): a
    correct key code then proves both that the switch works AND that the
    operator saw the light, because reading the name off the glass can no
    longer produce it. Grading is unchanged -- `st.idx` is still matched by
    VALUE, never by position -- so this only permutes `steps` before the
    walk.

    `hold`, if given, is called before each indicator is lit and may block. It
    is how the panel loop stays out of the acoustic test's way (S126, ruling a):
    the panel microphone hears button clicks, so while the speaker is sounding
    the next indicator waits rather than inviting a press. It is a HOLD, never a
    skip -- the button is still lit, still pressed and still graded; only the
    moment moves, by about a second.

    Returns (steps, extra) where `extra` carries the rows that are not part of
    the sweep: the always-lit indicators, the encoder, and the rows this station
    cannot reach.

    `can_say_notlit` is False only for a caller with no NOT LIT channel at
    all -- the armed factory screen has one now (S137: `live.json`'s
    `buttons` carries `notlit` and `command.json` carries the press, since
    the dialog protocol the ARMED screen draws no prompt for). See
    LED_NOT_SEEN: with no channel, the indicator half of each step is
    recorded as not measured rather than inferred from a press."""
    steps = [Step(*s) for s in PANELS[panel]]
    if panel == 'left' and SW_LEFT is None:
        # S136: Sys001SwLeft001 is not on this unit's deployed pack (it lands
        # at defs-v2026.09.27). No fallback, no aliasing guess -- every row
        # this panel owns is NOT TESTED and the bus is never touched.
        for st in steps:
            st.sw = st.led = NODATA
            st.sw_note = st.led_note = SW_LEFT_ABSENT
        return steps, {'unreached': UNREACHED.get(panel, {})}
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
        while True:
            answer = ask(st, n, len(steps))
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
                    # S137, PW's panel-loop ruling, verbatim: "a button to
                    # press if led change is not observed so machine can
                    # note, and skip to next." The LED is FAILED on the
                    # operator's word; the switch underneath it was never
                    # asked about, so it is NOT TESTED, not FAILED -- and the
                    # step ends here, at once, with no retry.
                    st.led = FAIL
                    st.led_note = 'operator saw no light'
                    st.sw = NOTTESTED
                    st.sw_note = 'skipped: LED dark'
                    break
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
            st.sw_note = ('on the %s, the tester lit %s and the key code that '
                          'came back was %d%s'
                          % (PANEL_NAME[panel], st.name, value,
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


def mode_resolve(a):
    """Print what this run resolved, and from where -- no bus, no hands, no
    matrix-app stop/start. This is the S136 proof: SKIN/ENC/SW_LEFT/SW_TALK
    against the pack this process actually found, by name, never a literal."""
    d = matrix_addr.describe()
    rows = {}
    for key, addr in (('skin', SKIN), ('enc', ENC), ('swleft', SW_LEFT),
                      ('swtalk', SW_TALK)):
        name = CELL_NAMES[key]
        rows[name] = addr if addr is not None else 'NOT TESTED (%s)' % {
            'skin': None, 'enc': None, 'swleft': SW_LEFT_ABSENT,
            'swtalk': SW_TALK_ABSENT}[key]
    print(json.dumps({'mode': 'resolve', 'pack': d['path'],
                      'generation': d['generation'], 'cells': d['cells'],
                      'resolved': rows}, indent=1))


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

    def ask(st, n, total):
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


def mode_sense(a):
    """S138b: the sense rows on their own, read-only, injectable.

    Nothing here writes a cell -- there is no `light()` on this path at all --
    so it is safe to run against a live unit with matrix-app stopped.
    """
    bus = InjectedBus(a.inject) if a.inject else PanelBus(a.port)

    def ask(instruction, row, n, total):
        print('\n[row %d, %d/%d] %s' % (row, n, total, instruction),
              file=sys.stderr, flush=True)
        return lambda: None

    # The running commentary goes to STDERR so that stdout is JSON and nothing
    # else -- this mode is read by a script, the way `d24_bus_probe.py` is.
    try:
        got = sense_sweep(bus, a.panel, ask, timeout=a.timeout,
                          log=lambda s: print(s, file=sys.stderr, flush=True))
    finally:
        bus.close()
    print(json.dumps({'mode': 'sense', 'panel': a.panel,
                      'rows': [dict(num=n, verdict=v, note=w)
                               for n, (v, w) in sorted(got.items())]},
                     indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--mode', required=True,
                    choices=('probe', 'rtt', 'light', 'watch', 'loop',
                             'resolve', 'sense'))
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
     'watch': mode_watch, 'loop': mode_loop, 'resolve': mode_resolve,
     'sense': mode_sense}[a.mode](a)


if __name__ == '__main__':
    main()
