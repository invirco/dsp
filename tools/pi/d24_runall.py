#!/usr/bin/env python3
"""d24_runall.py -- RUN ALL: one START, every auto test pipelined, every manual
test stepped, one complete report.

S117 / PW 2026-09-26 ("RUN ALL SHAPE RULED"). There are two categories of test.
AUTO needs no operator. MANUAL needs the operator to push buttons, answer to
LED signals, change leads, plug a stick in. One button push pipelines the whole
AUTO set; the MANUAL set is then stepped in station order, each step an INSTRUCT
dialog and an ACKNOWLEDGEMENT; then ONE complete report is written.

WHY THE LOGIC IS HERE AND NOT IN THE APP. The on-glass wizard is a thin client:
it launches this file, tails `runall/progress.txt`, draws whatever
`runall/prompt.json` asks for and writes the operator's answer to
`runall/answer.json`. Everything that decides anything -- the category split,
the station order, the rails rule, IGNORE, the pass arithmetic, the report --
lives here, in Python, where it can be read and run without a unit. That is the
simplest, fastest thing PW asked for: one place to change, and the C# side has
no opinions to keep in step.

THE AUTO SET IS NOT REIMPLEMENTED. The auto phase shells out to
`d24_selftest.py` exactly once per pass with `--only <the owed test ids>`, in
the catalog's own `group`/`order` (S113 A1->A5). That runner already stops the
mixer once, stages once, boots the pair once and raises the rails once (S116
Q4); re-driving it test by test would pay all of that per row. The verdicts are
read back out of the results CSV it appends to, which is the same file the glass
rolls up from, so the report and the glass cannot disagree.

STATE, AND WHY IT IS CUMULATIVE. `runall/state.json` is the unit's state, not
the run's: per catalog row the final verdict and the pass that produced it,
earlier fails kept as history. A PASS is never re-run (PW 09-26, no redundant
tests); a later pass runs only what is still OWED -- no PASS yet and not
IGNORED. The file is keyed on the unit's own serial and survives an app restart
and a power cycle, so a unit can go to the rework bench and come back to the
next pass.

    python3 d24_runall.py                      # a pass, driven from the glass
    python3 d24_runall.py --stdin              # the same pass, answered on stdin
    python3 d24_runall.py --auto-only          # the auto set and the report
    python3 d24_runall.py --report-only        # re-write the report from state
    python3 d24_runall.py --ignore 56 --reason 'fixture not built'
    python3 d24_runall.py --unignore 56
    python3 d24_runall.py --check-md FILE      # the internal-vocabulary grep
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import d24_panel as PL                                  # noqa: E402
import d24_patch as PT                                 # noqa: E402

PASS, FAIL, NODATA = 'PASS', 'FAIL', 'NO DATA'
IGNORED, SKIPPED, NOTTESTED = 'IGNORED', 'SKIPPED', 'NOT TESTED'
# Worst-wins, for an item covered by more than one test and for a row whose
# passes span passes. IGNORED is deliberately worse than PASS and better than
# nothing: it is never a PASS (S117 §6) but it does stop a row being owed.
RANK = {PASS: 0, IGNORED: 1, SKIPPED: 2, NOTTESTED: 3, NODATA: 4, FAIL: 5}

DIR_DEFAULT = '/home/app/selftest'

# --- the auto set's cost model ----------------------------------------------
# Measured, not estimated: the deltas between consecutive result stamps in
# S116's full `--section A,B,C` run (MW/D24/DSP/s116/logs/
# full-run-2026-09-26T130813Z.csv, 13:08:13Z -> 13:11:43Z, 210.4 s). Used for
# the one progress line's "remaining" figure and for nothing else, so a drift
# of a second or two costs nothing.
COST = {
    'HD0-1': 2, 'AS-CM4': 0, 'USB-HUB': 0, 'NW1': 0, 'NW3': 63, 'NW4': 23,
    'NW2': 30, 'ML1': 4, 'ML2': 0, 'ML-M': 5, 'ML-P1': 5, 'ML-P2': 5,
    'ML-B0': 0, 'CC1': 1, 'CC2': 0, 'MC1': 1, 'MC2': 0, 'MC3': 0,
    'DR1': 11, 'DR2': 9, 'DY1-RDY1': 7, 'DY1-RDY2': 0,
    'DC1-CS1': 1, 'DC1-CS2': 0, 'DC1-CS6': 0, 'DC1-CS7': 0, 'DC1-CS8': 0,
    'DC2-CS1': 0, 'DC2-CS2': 1, 'DC2-CS6': 0, 'DC2-CS7': 0, 'DC2-CS8': 0,
    'AS-DSPA': 4, 'AS-DSPB': 2, 'AS-CPLD': 15, 'AS-ADC': 2, 'AS-DAC': 4,
    'AS-PWR': 0, 'AL1': 17, 'HD-PWR': 0,
}

# --- plain English for the human page ---------------------------------------
# The .md report and every on-glass dialog are written for a person on a
# production line, so no test id, no cell name and no fw.csv name reaches
# either (PW 09-21). This is the one place a test id is turned into words.
PLAIN = {
    'HD0-1': 'screen link', 'HD-PWR': 'screen power link',
    'NW1': 'network link', 'NW2': 'network error counters',
    'NW3': 'network packet loss', 'NW4': 'network throughput',
    'AS-CM4': 'compute module', 'USB-HUB': 'internal USB hub',
    'ML1': 'main control processor link', 'ML2': 'main control processor version',
    'ML-M': 'dispatch processor', 'ML-P1': 'right panel processor link',
    'ML-P2': 'left panel processor link', 'ML-B0': 'panel processor reprogramming line',
    'DR1': 'audio processor reset, held', 'DR2': 'audio processor reset, released',
    'MC1': 'microphone gain chain latch', 'MC2': 'microphone gain chain readback',
    'MC3': 'microphone gain chain, safe image',
    'CC1': 'converter select', 'CC2': 'converter registers',
    'AS-DSPA': 'audio processor A', 'AS-DSPB': 'audio processor B',
    'AS-CPLD': 'clock master', 'AS-ADC': 'input converters',
    'AS-DAC': 'output converters', 'AS-PWR': 'power processor',
    'AL1': 'speaker to microphone loop',
}
for _n in (1, 2, 6, 7, 8):
    PLAIN['DC1-CS%d' % _n] = 'audio processor select line %d, asserted' % _n
    PLAIN['DC2-CS%d' % _n] = 'audio processor select line %d, answered' % _n
for _c in (1, 2):
    PLAIN['DY1-RDY%d' % _c] = 'audio processor %s ready line' % 'AB'[_c - 1]


def plain_test(t):
    return PLAIN.get(t, t)


# The row NAMES the human page prints. The catalog's `item` is the workbook's
# own string and names parts the way the schematic does -- "S MCU H1S1
# (STM32U575)", "Link 'dig-analog-dac'", "DSP chip-select CS6". Those are not
# what an operator on a line is holding, so the page prints the plain name and
# the JSON twin keeps the workbook's. Nothing here renames a PANEL item: "MIC
# 5", "Aux Out A1" and the board's own header designators are already the names
# a person uses and are left exactly as they are.
NAMES = [
    (r"^Display link HDMI0.*$", 'screen link'),
    (r"^HDMI FPC.*$", 'screen link ribbon'),
    (r"^TFT display$", 'screen'),
    (r"^CM4 compute module$", 'compute module'),
    (r"^Ethernet \(RJ45\)$", 'network socket'),
    (r"^H1S1 MCU \(STM32U575\) link$", 'main control processor link'),
    (r"^S MCU H1S1 \(STM32U575\)$", 'main control processor'),
    (r"^M MCU \(STM32G031\)$", 'dispatch processor'),
    (r"^Power MCU \(STM32F030F4, always-on\)$", 'power processor'),
    (r"^Right panel MCU link.*$", 'right panel processor link'),
    (r"^Left panel MCU link.*$", 'left panel processor link'),
    (r"^DSP chip-select CS(\d+).*$", r'audio processor select line \1'),
    (r"^DSP reset RST_D.*$", 'audio processor reset line'),
    (r"^Codec select CS_C.*$", 'talkback converter select line'),
    (r"^Mic-gain chain latch CS_M.*$", 'microphone gain chain latch'),
    (r"^SHARC DSP A \(ADSP-21564\)$", 'audio processor A'),
    (r"^SHARC DSP B \(ADSP-21564\)$", 'audio processor B'),
    (r"^CPLD clock master \(MAX V\)$", 'clock master'),
    (r"^ADC AK5558.*$", 'input converters'),
    (r"^DAC AK4458.*$", 'output converters'),
    (r"^Codec AK4619$", 'talkback converter'),
    (r"^Panel MEMS mic \(talkback\) \+ Speaker$", 'panel microphone and speaker'),
    (r"^Link 'dig-dsp-a'$", 'audio processor A link'),
    (r"^Link 'dig-dsp-b'$", 'audio processor B link'),
    (r"^Link 'dig-analog-adc'$", 'input converter link'),
    (r"^Link 'dig-analog-dac'$", 'output converter link'),
    (r"^Link 'dig-panel-a'$", 'right panel link'),
    (r"^Link 'dig-panel-b'$", 'left panel link'),
    (r"^Link 'hdmi-pwr'$", 'screen power link'),
    (r"^Link 'hdmi-fpc'$", 'screen ribbon link'),
    (r"^Link 'pedal'$", 'foot pedal link'),
    (r"^Link 'fan'$", 'fan link'),
    (r"^Link 'phones'$", 'headphone link'),
    (r"^Link 'minijack'$", 'small jack link'),
    (r"^Link 'analog-12v'$", 'analog board supply link'),
    (r"^Link 'opt(\d)'$", r'expansion link \1'),
    (r"^Link 'd32compat'$", 'expansion compatibility link'),
    (r"^USB A \(dual jack, hub port (\d)\)$",
     r'rear USB socket \1 of the double pair'),
    (r"^HDMI 1 \(placeholder\)$", 'second screen socket (not fitted)'),
    (r"^P1 Foot Pedal \(RJ45\)$", 'foot pedal socket'),
    (r"^USB-C Multitrack/DAW$", 'expansion card USB-C socket'),
]


def plain_name(item):
    for pat, rep in NAMES:
        if re.match(pat, item):
            return re.sub(pat, rep, item)
    return item


# --- the vocabulary the human page may not carry ----------------------------
# Checked by --check-md, which is the acceptance grep. Every pattern here is
# Matrix-internal: a bench test id, a matrix cell name, a firmware-table name,
# a node id, a session tag, a repo path, a group code. The JSON twin carries
# all of it; the page a person reads carries none of it.
INTERNAL = [
    (r'\bfw\.csv\b', 'firmware table name'),
    (r'\bdefs\b', 'definitions repo'),
    (r'\bMW/', 'repo path'),
    (r'\bC[12]_[A-Z]', 'DSP node id'),
    (r'\b[A-Z][a-z]+\d{3}[A-Z][a-z]+\d{3}\b', 'matrix cell name'),
    (r'\bMxAdd\b|\bMxDat\b', 'matrix bus column'),
    (r'\bdsp4_\w+|\bs89_\w+|\bd24_\w+\.py', 'bench tool name'),
    (r'\bgroups? [AM][1-8]\b', 'run-group code'),
    (r'\bS\d{2,3}\b', 'session tag'),
    (r'\bDC[12]-CS\d|\bDY1-RDY\d|\bAS-[A-Z]{3,4}\b|\bML-?[A-Z0-9]{1,3}\b'
     r'|\bNW[1-4]\b|\bHD0-\d|\bHD-PWR\b|\bDR[12]\b|\bMC[123]\b|\bCC[12]\b'
     r'|\bAL1\b|\bUSB-HUB\b', 'bench test id'),
]


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def md5_file(path):
    h = hashlib.md5()
    with open(path, 'rb') as fh:
        for blk in iter(lambda: fh.read(65536), b''):
            h.update(blk)
    return h.hexdigest()


def unit_serial():
    """The unit's own serial, so the state and the ignores belong to a board and
    not to a directory. The CM4's is in /proc/cpuinfo; a desk run gets a name
    that cannot be mistaken for a unit."""
    try:
        for line in open('/proc/cpuinfo'):
            if line.lower().startswith('serial'):
                return line.split(':', 1)[1].strip()
    except OSError:
        pass
    return 'no-serial'


# ---------------------------------------------------------------------------
# The catalog, and what each row is
# ---------------------------------------------------------------------------
def split_list(s):
    return [x for x in re.split(r'[,\s]+', (s or '').strip()) if x]


class Row:
    """One catalog row, plus what RUN ALL decided about it."""

    def __init__(self, d):
        self.d = d
        self.num = int(d['num'])
        self.board = d['board']
        self.item = d['item']
        self.key = d['board'] + '|' + d['item']
        self.cls = d.get('class', '')
        self.group = (d.get('group') or '').strip()
        self.order = int(d['order']) if (d.get('order') or '').strip().isdigit() else 9999
        self.automation = (d.get('automation') or '').strip()
        self.tests = split_list(d.get('tests'))
        self.covers = [int(x) for x in split_list(d.get('covers')) if x.isdigit()]
        self.category = ''          # auto | manual | not-run
        self.reason = ''            # why, when not-run
        self.step = None            # the manual step, when there is one

    # The panel name, which is what the operator is told. The catalog's `item`
    # is the workbook's own string and carries the firmware table's name for
    # the part in brackets -- "MONO AUX (fw.csv MonoAux) button". The bracket
    # comes off; nothing else is reworded, so the name on the glass is still
    # the name in the workbook.
    @property
    def panel(self):
        s = re.sub(r'\s*\([^)]*fw\.csv[^)]*\)', '', self.item)
        s = re.sub(r'\s*\(rev [^)]*\)', '', s)
        s = re.sub(r',\s*\)', ')', s)
        s = re.sub(r'\s+', ' ', s).strip()
        return s

    @property
    def report_name(self):
        """The name the human page prints. `panel` is what the operator is
        told at the bench, where the workbook's own words for a panel part are
        right; this is what a report READER sees, where a schematic designator
        is not."""
        return plain_name(self.panel)


def load_catalog(path):
    with open(path, newline='', encoding='utf-8') as fh:
        rows = [Row(d) for d in csv.DictReader(fh) if (d.get('num') or '').strip().isdigit()]
    rows.sort(key=lambda r: r.num)
    return rows, md5_file(path)


# ---------------------------------------------------------------------------
# The manual set: stations, and one step per row
# ---------------------------------------------------------------------------
# Station order is S113's M1..M7 with the ANALOG stations moved to the end, so
# the analog rails go up ONCE and late (S116 Q4 / PW 09-10: analog last up,
# first down). `rails` says the station needs them; `hand` is S113 §3's "what
# the operator has in hand", said once per station and not per row.
#
# M6 (the slot-1 card) and M8 (no bench time) are not stations: their rows are
# NOT RUN and say why in the report (S117 §1). M7 ("Meter checks, lid off") is
# RETIRED (S119 / PW 2026-09-26): component and assembly faults are the
# assembler's QC job, not a lid-off bench step. Its 24 rows moved to group
# `QC` and are classified NOT RUN, each with its own reason -- see
# `QC_REASON` below -- so there is no station, no rails and no dialog for it
# any more.
STATIONS = [
    ('M1', 'Left switch panel',
     'a finger and an eye, at the left half of the front panel', False),
    ('M2', 'Right switch panel',
     'a finger and an eye, at the right half of the front panel', False),
    ('M3', 'Foot pedal',
     'the foot pedal, its lead and the network lead', False),
    ('M5', 'Rear panel sockets',
     'a USB memory stick, a screen and its lead, the mains lead', False),
    ('M4', 'Analog paths',
     'the five-lead patch kit: an XLR lead, a jack-to-XLR lead, an '
     'XLR-to-jack lead, an XLR-to-mini-jack lead and the 150 ohm plug',
     True),
]
STATION_NAME = {k: n for k, n, _h, _r in STATIONS}
STATION_NUM = {k: i + 1 for i, (k, _n, _h, _r) in enumerate(STATIONS)}

# What a step asks for.
#   measure  the runner takes the reading after the operator says Done
#   judge    only a person can say; the question is worded so Yes = pass
#   blocked  there is no test to run: no host capability and nothing a person
#            can judge. NOT RUN, with the missing piece named.
#   fixture  the test is real and the fixture is not built. The station is
#            still visited and the step is Skipped with that reason.
#   loop     the row is graded inside a panel loop, not by a dialog of its own
MEASURE, JUDGE, BLOCKED, FIXTURE, LOOP = ('measure', 'judge', 'blocked',
                                          'fixture', 'loop')

# The two stations that are ONE LOOP rather than a walk of dialogs (S120), and
# which side of the front panel each one is.
PANEL_STATIONS = {'M1': 'left', 'M2': 'right'}

# The analog station is ONE LOOP as well (S121), for the same reason the panel
# stations are: the operator's hands are the slow part, and a dialog per row
# would stop them between every socket. Eighty-one patches prove forty-five of
# this station's forty-eight rows, and the three it cannot reach say why.
PATCH_STATIONS = {'M4'}

# The M4 rows the patch list does not reach, each with its own reason. None of
# them is a unit fault and none is dropped (S117 section 1).
PATCH_UNREACHED = {
    35: ('the Centre/LF socket is on a converter lane this product has no '
         'cell for: nothing the host can write puts a signal on it'),
    97: ('the headphone socket is on two converter lanes this product has no '
         'cells for: nothing the host can write puts a signal on it'),
    148: ('this row is a screen link, not an audio path: it does not belong '
          'to this station'),
}
# Rows proved by the paths that run over them rather than by a path of their
# own -- the partner stamping S117 established. The board-to-board link to the
# headphone jack board IS the four stereo jacks' signal path, and the link to
# the mini-jack board IS the two mini-jacks'.
PATCH_PARTNERS = {146: (39, 40, 41, 42), 147: (95, 96)}

NO_KEYREAD = ('the host cannot see this control or sense line change: this unit '
              'has no per-control read through the panel processors')
NO_LEDDRIVE = ('the host cannot light one indicator at a time: this unit has no '
               'indicator drive for the panel processors')
NO_HARNESS = 'the loopback lead set is not built'


_PATCH_ROWS = None


def PATCH_ROWS():
    """The catalog rows the generated patch list actually names.

    Read from the list, never restated here: the list is generated from defs
    and the port table, and a second copy of which rows it covers is a second
    thing to keep in step. An unreadable list is an error, not an empty set --
    an empty set would quietly turn the whole station into NOT RUN.
    """
    global _PATCH_ROWS
    if _PATCH_ROWS is None:
        plist = PT.PatchList(PT.find_list_dir())
        out = set()
        for row in plist.paths:
            out.update(int(x) for x in row['rows'].split())
        if not out:
            raise SystemExit('the patch list names no catalog rows at all')
        _PATCH_ROWS = out
    return _PATCH_ROWS


def manual_step(r):
    """The one step a manual row becomes: what the operator is told, what kind
    of acknowledgement it takes, and what the runner measures afterwards.

    The text is built from the columns that are RELIABLE -- board, item, class
    -- and from the phrasing table below. It is NOT built from the catalog's
    `short` / `pass_when` prose, which is misaligned by one row from row 132
    up (finding S117-1: row 133, the mains inlet, carries the second screen
    socket's criterion; row 134, the power switch, carries the inlet's). S116
    found the same shift on rows 127/203 and left it flagged. Generating a
    dialog from that text would put the wrong instruction in front of an
    operator, so this table is the source and the catalog prose is not read.
    """
    where = {'M1': 'on the left of the front panel',
             'M2': 'on the right of the front panel',
             'M3': 'on the foot pedal',
             'M4': 'on the rear panel',
             'M5': 'on the rear panel'}.get(r.group, '')
    name = r.panel

    # --- station 5 / rear sockets: the three that can be read today ---------
    if r.num in (130, 131):
        port = 3 if r.num == 130 else 4
        side = 'left' if r.num == 130 else 'right'
        return dict(kind=MEASURE, measure='usb_port:%d' % port,
                    action='Plug the USB memory stick into the %s socket of the '
                           'double USB pair on the rear panel.' % side,
                    check='the stick appears on the unit')
    if r.num == 132:
        return dict(kind=BLOCKED,
                    reason='the second screen socket is a placeholder on this '
                           'revision and is not fitted')
    if r.num == 133:
        return dict(kind=JUDGE,
                    action='Look at the mains inlet on the rear panel.',
                    question='Is the mains lead fully home in the inlet, and is '
                             'the unit running from it?')
    if r.num == 134:
        return dict(kind=BLOCKED,
                    reason='working the power switch shuts the unit down; it is '
                           'checked when the session ends, not inside a pass')
    if r.num == 127 or r.num == 203:
        return dict(kind=BLOCKED, reason='covered by the automatic set')

    # --- the two switch panels: the loop (S120) ------------------------------
    # Stations M1 and M2 are not walked one dialog per row. They are ONE LOOP:
    # the tester lights the next button's indicator, the operator presses the
    # button under it, and the key code that comes back grades the switch row
    # and the indicator row together. `panel_station()` owns every row it can
    # reach; what it cannot reach is named here, row by row, in its own words.
    if r.group in PANEL_STATIONS:
        side = PANEL_STATIONS[r.group]
        why = PL.UNREACHED.get(side, {}).get(r.num)
        if why:
            return dict(kind=BLOCKED, reason=why)
        if r.num in PL.rows_for(side):
            action, question, check = PL.wording(side, r.num)
            return dict(kind=LOOP, side=side, action=action,
                        question=question, check=check)
        return dict(kind=BLOCKED, reason=(NO_LEDDRIVE if 'LED' in r.cls
                                          else NO_KEYREAD))
    if r.cls in ('pedal switch', 'pedal LED'):
        return dict(kind=BLOCKED,
                    reason=NO_LEDDRIVE if 'LED' in r.cls else NO_KEYREAD)
    if r.group == 'M3':
        return dict(kind=FIXTURE, reason='the foot pedal and its lead are not at '
                                         'the bench',
                    action='Plug the foot pedal into the pedal socket on the rear '
                           'panel, with its own lead into the pedal.',
                    check='the pedal link comes up')

    # --- the analog paths ---------------------------------------------------
    # One loop, not forty-eight dialogs (S121). `patch_station()` owns every
    # row the patch list reaches; what it cannot reach is named here, row by
    # row, in its own words.
    if r.group in PATCH_STATIONS:
        why = PATCH_UNREACHED.get(r.num)
        if why:
            return dict(kind=BLOCKED, reason=why)
        if r.num in PATCH_PARTNERS or r.num in PATCH_ROWS():
            return dict(kind=LOOP, action='Patch %s as the tester asks.' % name,
                        question='', check='a tone reaches it and nowhere else')
        return dict(kind=BLOCKED,
                    reason='no signal path in the patch list reaches this row')

    # Anything else in a station group: a plain operator judgement, worded so
    # Yes is a pass. No row reaches here on today's catalog; it is here so a
    # new row does not fall through into silence.
    return dict(kind=JUDGE,
                action='Check %s %s.' % (name, where),
                question='Is it right?')


# ---------------------------------------------------------------------------
# QC (S119 / PW 2026-09-26): the 24 rows retired from the meter station
# ---------------------------------------------------------------------------
# "Meter checks, lid off" is out: component and assembly faults are the
# assembler's QC job (feeder/reel verification, AOI, X-ray, flying-probe test,
# first power-up, first-article inspection, a pilot build), not a bench step
# with a lid off. Every one of the 24 rows still gets a line in the report --
# never silently dropped (S117 §1) -- as either:
#
#   * covered by <test>: an automatic test elsewhere in this catalog already
#     proves the connector, because the header's own nets are exactly what
#     that test exercises (defs/products/d24/d24-hw-inventory.csv has the
#     nets per header; ITEMS in d24_selftest.py has the test-to-net map);
#   * board-level test at the assembler: nothing in this catalog proves the
#     connector, so it is the assembler's continuity/presence check, not a
#     bench one. No row is reworded beyond this -- the row already names the
#     board and the designator.
QC_REASON = {
    # DSP PCBA J1/J2: the CPLD's own clock (C1/L0) and LOGIC_AD/DA bus.
    # AS-CPLD ("clocks present and locked; configuration in flash matches the
    # shipping bitstream") cannot pass without this header intact. Named in
    # PLAIN, not by test id -- the human page carries no bench test ids
    # (INTERNAL, above), and a plain name is what "name the test" needs here.
    164: 'covered by the clock master test: it already needs this header’s clock and logic-bus lines',
    165: 'covered by the clock master test: it already needs this header’s clock and logic-bus lines',
    # DSP PCBA J3/J4/J6: CS_C, CS_M and both chips' SPI2 SS/RDY -- every one of
    # those nets already has its own dedicated automatic test (fw.csv Dsp1/
    # Dsp2/RdyDspA/RdyDspB/MicGainLatch/Codec).
    166: ('covered by the converter-select, microphone-gain-latch and audio-'
          'processor select/ready tests: every net on this header already '
          'has its own automatic test'),
    167: ('covered by the converter-select, microphone-gain-latch and audio-'
          'processor select/ready tests: every net on this header already '
          'has its own automatic test'),
    168: ('covered by the audio-processor select and ready tests: both '
          'processors’ select and ready lines on this header already '
          'have their own automatic test'),
    # Digital J7: the same magjack as row 128 "Ethernet (RJ45)".
    172: ('covered by the network link, error-counter, packet-loss and '
          'throughput tests: they already exercise this magjack'),
    # Digital J24/J25: the CM4 module's own 2x100 B2B connectors.
    181: 'covered by the compute-module test: the unit being up and reachable already proves this connector',
    182: 'covered by the compute-module test: the unit being up and reachable already proves this connector',
}
QC_BOARD_LEVEL = 'board-level test at the assembler'


def classify(rows):
    """AUTO from the catalog's own `automation` column (1 = AUTO, any of 2/3/4
    = MANUAL), cross-checked against the `group` column, which is what RUN ALL
    actually orders by. Rows with no automation declared (`-`), group M8 (no
    bench time), group M6 (the slot-1 card does not exist) and group QC (the
    retired meter station, S119) are NOT RUN and say so in the report; they
    are never silently dropped."""
    warn = []
    for r in rows:
        auto_col = r.automation == '1'
        auto_grp = r.group.startswith('A')
        if auto_col != auto_grp:
            warn.append('#%d: automation %r but group %r'
                        % (r.num, r.automation, r.group))
        if r.group == 'QC':
            r.category, r.reason = 'not-run', QC_REASON.get(r.num, QC_BOARD_LEVEL)
        elif r.group == 'M8' or r.automation in ('', '—', '-'):
            r.category, r.reason = 'not-run', (
                'no test is declared for this row: it is out of scope for the '
                'factory test or its method has not been written')
        elif r.group == 'M6':
            r.category, r.reason = 'not-run', (
                'the expansion card this row belongs to does not exist yet')
        elif auto_grp:
            r.category = 'auto'
        else:
            r.category = 'manual'
            r.step = manual_step(r)
            if r.step['kind'] == BLOCKED:
                r.category, r.reason = 'not-run', r.step['reason']
    return warn


# ---------------------------------------------------------------------------
# State: the unit's cumulative verdict per row
# ---------------------------------------------------------------------------
class State:
    def __init__(self, path, serial, catalog_md5):
        self.path = path
        self.d = {'serial': serial, 'catalog_md5': catalog_md5,
                  'created': stamp(), 'passes': 0, 'rows': {}, 'current': None}
        if os.path.exists(path):
            try:
                with open(path) as fh:
                    old = json.load(fh)
                if old.get('serial') == serial:
                    self.d = old
                    self.d['catalog_md5'] = catalog_md5
            except (OSError, ValueError):
                pass
        self.d.setdefault('rows', {})
        self.d.setdefault('passes', 0)

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        tmp = self.path + '.tmp'
        with open(tmp, 'w') as fh:
            json.dump(self.d, fh, indent=1, sort_keys=True)
        os.replace(tmp, self.path)

    def row(self, num):
        return self.d['rows'].get(str(num))

    def verdict(self, num):
        e = self.row(num)
        return e['verdict'] if e else ''

    def put(self, num, verdict, force=False, **kw):
        """Record a verdict for a row. A row's FINAL verdict is the best it has
        ever reached -- a PASS is not undone by a later NO DATA, because a pass
        is never re-run -- and every earlier verdict is kept as history so a
        fail that was fixed still shows in the report.

        `force` (S119) bypasses the rank gate: it is for `record_not_run`
        alone, whose NOT TESTED is not a measurement that can be "worse" than
        an earlier SKIPPED/NO DATA/FAIL, it is the catalog saying this row is
        no longer a check that can be run at all -- a category change, not a
        regression. Without it, a row skipped at a station under an OLDER
        catalog (SKIPPED outranks NOT TESTED) would carry that stale verdict
        and reason forever, never reaching the new one, because the row can
        never again out-rank it by being run. The old entry is still kept in
        `history`, so nothing is lost from the report -- it just stops being
        the headline."""
        key = str(num)
        e = self.d['rows'].get(key)
        new = dict(verdict=verdict, stamp=stamp(), **kw)
        if e is None:
            new['history'] = []
            self.d['rows'][key] = new
            return
        hist = e.pop('history', [])
        if force or RANK[verdict] <= RANK.get(e['verdict'], 9):
            hist.append({k: v for k, v in e.items() if k != 'history'})
            new['history'] = hist
            self.d['rows'][key] = new
        else:
            hist.append({k: v for k, v in new.items() if k != 'history'})
            e['history'] = hist


# ---------------------------------------------------------------------------
# IGNORE (S117 §6): per unit serial, one reason, expires when the catalog moves
# ---------------------------------------------------------------------------
IGNORE_COLS = ['serial', 'num', 'reason', 'catalog_md5', 'stamp']
REASONS = ['awaiting part', 'known rev-C erratum', 'fixture not built', 'other']


def read_ignored(path, serial, catalog_md5):
    """The live ignores for this unit. An ignore is stamped with the catalog md5
    it was taken against and EXPIRES when that moves: a row's runner or limits
    changing is exactly the case where last week's "ignore this" is no longer a
    statement anybody made."""
    live, stale = {}, {}
    if not os.path.exists(path):
        return live, stale
    with open(path, newline='') as fh:
        for d in csv.DictReader(fh):
            if d.get('serial') != serial or not (d.get('num') or '').isdigit():
                continue
            n = int(d['num'])
            if d.get('reason') == '':          # an UNIGNORE row
                live.pop(n, None)
                stale.pop(n, None)
                continue
            (live if d.get('catalog_md5') == catalog_md5 else stale)[n] = d
    return live, stale


def write_ignore(path, serial, num, reason, catalog_md5):
    exists = os.path.exists(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=IGNORE_COLS)
        if not exists:
            w.writeheader()
        w.writerow(dict(serial=serial, num=num, reason=reason,
                        catalog_md5=catalog_md5, stamp=stamp()))


# ---------------------------------------------------------------------------
# The glass: one prompt file out, one answer file in
# ---------------------------------------------------------------------------
class Glass:
    """The operator, whether they are behind the unit's own display or behind a
    terminal. `ask()` blocks until an answer comes back, which is the whole
    protocol: a JSON file with a sequence number out, a JSON file with the same
    sequence number and a button in. The sequence number is what stops a stale
    answer.json -- one left by the press before, or by an app that was restarted
    mid-dialog -- being read as an answer to this question."""

    def __init__(self, dirpath, stdin=False, autoskip=False):
        self.dir = dirpath
        self.prompt_path = os.path.join(dirpath, 'prompt.json')
        self.answer_path = os.path.join(dirpath, 'answer.json')
        self.progress_path = os.path.join(dirpath, 'progress.txt')
        self.stdin = stdin
        self.autoskip = autoskip
        self.seq = int(time.time())
        os.makedirs(dirpath, exist_ok=True)

    def progress(self, text):
        with open(self.progress_path, 'w') as fh:
            fh.write(text.rstrip() + '\n')
        print('   .. %s' % text, flush=True)

    def clear(self):
        for p in (self.prompt_path, self.answer_path):
            try:
                os.remove(p)
            except OSError:
                pass

    def ask(self, kind, title, lines, buttons, **extra):
        """Put one dialog up and wait for the operator to answer it."""
        btns = self.post(kind, title, lines, buttons, **extra)
        ans = self._wait(btns)
        try:
            os.remove(self.prompt_path)
        except OSError:
            pass
        print('   -> %s%s' % (ans.get('button'),
                              (' (%s)' % ans['reason']) if ans.get('reason') else ''),
              flush=True)
        return ans

    def post(self, kind, title, lines, buttons, **extra):
        """Put one dialog up and DO NOT wait. Returns the button list the glass
        was given, which `poll()` needs to recognise a valid answer.

        `ask()` is post + wait, and the split exists for the panel loop (S120):
        there the dialog and the panel race each other -- the operator answers
        most steps by pressing a button ON THE UNIT, not on the glass, and the
        glass button is only there for the one judgement a press cannot make
        ("it did not light"). A blocking ask cannot hear the panel.

        `buttons` is the ordered list of button ids the dialog offers; the glass
        draws them in that order and hands back the one that was pressed. Every
        dialog carries `skip` and `ignore` as well, and PAUSE, which is offered
        at every step (S117 §3): added here so no caller can forget any of the
        three."""
        self.seq += 1
        btns = list(buttons)
        # IGNORE and PAUSE are offered everywhere. SKIP is not offered on the
        # review screen: there is nothing there to skip past -- NEXT already
        # does that -- and six slots is the width of the glass, so a seventh
        # button would be a button the operator cannot reach.
        for b in (('ignore', 'pause') if kind == 'review'
                  else ('skip', 'ignore', 'pause')):
            if b not in btns:
                btns.append(b)
        if len(btns) > 6:
            raise AssertionError('a dialog offers %d buttons; the glass has six '
                                 'slots: %r' % (len(btns), btns))
        p = dict(seq=self.seq, kind=kind, title=title, lines=list(lines),
                 buttons=btns, reasons=REASONS, stamp=stamp(), **extra)
        tmp = self.prompt_path + '.tmp'
        with open(tmp, 'w') as fh:
            json.dump(p, fh, indent=1)
        os.replace(tmp, self.prompt_path)
        print('\n== %s: %s' % (kind.upper(), title), flush=True)
        for ln in lines:
            print('   %s' % ln, flush=True)
        print('   [%s]' % ' / '.join(btns), flush=True)
        return btns

    def poll(self, btns):
        """The answer to the dialog `post()` put up, or None if nobody has
        pressed anything yet. Never blocks."""
        if self.autoskip:
            return dict(button='skip', reason='fixture not built')
        if self.stdin:
            import select
            if not select.select([sys.stdin], [], [], 0)[0]:
                return None
            line = sys.stdin.readline()
            if not line:
                return dict(button='pause', reason='input closed')
            parts = line.strip().split(':', 1)
            b = parts[0].strip().lower()
            if b in btns:
                return dict(button=b,
                            reason=parts[1].strip() if len(parts) > 1 else '')
            return None
        try:
            with open(self.answer_path) as fh:
                a = json.load(fh)
            if int(a.get('seq', -1)) == self.seq and a.get('button') in btns:
                return a
        except (OSError, ValueError, TypeError):
            pass
        return None

    def taken(self, ans):
        """Clear a posted dialog once its answer has been taken."""
        try:
            os.remove(self.prompt_path)
        except OSError:
            pass
        print('   -> %s%s' % (ans.get('button'),
                              (' (%s)' % ans['reason']) if ans.get('reason') else ''),
              flush=True)

    def _wait(self, btns):
        if self.autoskip:
            return dict(button='skip', reason='fixture not built')
        if self.stdin:
            while True:
                line = sys.stdin.readline()
                if not line:
                    return dict(button='pause', reason='input closed')
                parts = line.strip().split(':', 1)
                b = parts[0].strip().lower()
                if b in btns:
                    return dict(button=b,
                                reason=parts[1].strip() if len(parts) > 1 else '')
                print('   ? one of %s' % ', '.join(btns), flush=True)
        while True:
            try:
                with open(self.answer_path) as fh:
                    a = json.load(fh)
                if int(a.get('seq', -1)) == self.seq and a.get('button') in btns:
                    return a
            except (OSError, ValueError, TypeError):
                pass
            time.sleep(0.3)


class Paused(Exception):
    """The operator pressed PAUSE. The pass stops where it is, the state keeps
    the step it stopped on, and the next START resumes there."""


# ---------------------------------------------------------------------------
# The auto phase
# ---------------------------------------------------------------------------
def auto_plan(rows, state, ignored):
    """The owed AUTO rows in S113 group/order, and the test ids they need.

    A test is asked for once even when several rows need it; a row that has
    already PASSED or is IGNORED is not asked for at all (PW 09-26, no
    redundant tests). The test list keeps `order`, so `--only` runs the set in
    the order the groups were designed in."""
    owed, tests = [], []
    for r in sorted((x for x in rows if x.category == 'auto'),
                    key=lambda x: (x.order, x.num)):
        if r.num in ignored or state.verdict(r.num) == PASS:
            continue
        owed.append(r)
        for t in r.tests:
            if t not in tests:
                tests.append(t)
    return owed, tests


def run_auto(a, rows, state, ignored, glass, csv_path):
    """One `d24_selftest.py` for the whole owed auto set, and its verdicts read
    back out of the results CSV it appends to."""
    owed, tests = auto_plan(rows, state, ignored)
    if not tests:
        glass.progress('auto set: nothing owed -- every automatic row has a '
                       'verdict already')
        return 0.0, [], owed
    before = os.path.getsize(csv_path) if os.path.exists(csv_path) else 0
    total = sum(COST.get(t, 5) for t in tests)
    cmd = [sys.executable, os.path.join(a.tools, 'd24_selftest.py'), '--local',
           '--csv', csv_path, '--section', 'A,B,C', '--only', ','.join(tests)]
    if a.no_app_restart:
        cmd.append('--no-app-restart')
    if a.stage:
        cmd += ['--stage', a.stage]
    print('\n--- auto set: %d test%s over %d row%s, about %d s ---\n%s'
          % (len(tests), '' if len(tests) == 1 else 's', len(owed),
             '' if len(owed) == 1 else 's', total, ' '.join(cmd)), flush=True)
    t0 = time.time()
    done = []
    by_test = {}
    for r in rows:
        for t in r.tests:
            by_test.setdefault(t, []).append(r)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1)
    log = []
    for line in proc.stdout:
        log.append(line)
        sys.stdout.write(line)
        sys.stdout.flush()
        m = re.match(r'^([A-Z][A-Z0-9-]+) \.\.\.\s*$', line.strip())
        if not m:
            continue
        t = m.group(1)
        if t not in COST:
            continue
        spent = sum(COST.get(x, 5) for x in done)
        grp = (by_test.get(t) or [None])[0]
        glass.progress('AUTO %s - %s - %d s gone, about %d s left'
                       % (('group ' + grp.group) if grp else 'running',
                          plain_test(t), time.time() - t0, max(0, total - spent)))
        done.append(t)
    proc.wait()
    secs = time.time() - t0
    glass.progress('auto set finished in %d s' % secs)
    return secs, read_new_rows(csv_path, before), owed


def read_new_rows(csv_path, before):
    """The rows the runner just appended. Read by byte offset rather than by
    stamp: the file is append-only and two tests in the same second are
    ordinary, so the offset is the only thing that cannot mis-slice it."""
    if not os.path.exists(csv_path):
        return []
    with open(csv_path, newline='') as fh:
        head = fh.readline()
        cols = next(csv.reader([head]))
        fh.seek(max(before, len(head)))
        body = fh.read()
    out = []
    for rec in csv.reader(body.splitlines()):
        if len(rec) == len(cols):
            out.append(dict(zip(cols, rec)))
    return out


def stamp_auto(rows, state, results, passno):
    """Write the auto verdicts onto the catalog rows, and onto every row a test
    fully covers (S116 Q5, the nine pairs). The guard: a partner row is stamped
    only when EVERY test that row declares has just run -- pressing the row
    that declares two tests stamps the one that declares one, never the other
    way round."""
    by_key = {}
    for d in results:
        by_key.setdefault(d['board'] + '|' + d['item'], []).append(d)
    by_num = {r.num: r for r in rows}
    ran = set(d['test'] for d in results)
    stamped = []
    for r in rows:
        mine = by_key.get(r.key, [])
        if not mine:
            continue
        worst = max(mine, key=lambda d: RANK.get(d['verdict'], 9))
        state.put(r.num, worst['verdict'], pass_no=passno, source=worst['test'],
                  measured=worst['measured'], limit=worst['limit'],
                  evidence=worst['evidence'], judged='runner')
        for n in r.covers:
            p = by_num.get(n)
            if p is None or p is r or not p.tests:
                continue
            if not set(p.tests) <= ran:
                continue
            # A row that took its OWN reading in this pass keeps it. The nine
            # pairs cover each other symmetrically, so without this the second
            # row of a pair would have its direct evidence replaced by "taken
            # from the check run for row N" -- true, but less than it already
            # had.
            if by_key.get(p.key):
                continue
            if state.verdict(n) == PASS and worst['verdict'] != PASS:
                continue
            state.put(n, worst['verdict'], pass_no=passno, source=worst['test'],
                      measured=worst['measured'], limit=worst['limit'],
                      evidence='%s; taken from the check run for row %d'
                               % (worst['evidence'], r.num),
                      judged='runner', stamped_from=r.num)
            stamped.append((r.num, n))
    return stamped


# ---------------------------------------------------------------------------
# The manual phase
# ---------------------------------------------------------------------------
def measure(kind, tools):
    """What the runner reads after the operator says Done. Every hook returns
    (verdict, measured, limit, evidence)."""
    name, _, arg = kind.partition(':')
    if name == 'usb_port':
        out = subprocess.run(['bash', '-c', 'lsusb -t; lsusb'],
                             capture_output=True, text=True, timeout=30)
        txt = out.stdout + out.stderr
        port = 'Port %s:' % arg
        hit = [ln for ln in txt.splitlines() if port in ln]
        dev = [ln for ln in hit if 'Class=' in ln and 'Hub' not in ln]
        v = PASS if dev else NODATA
        return (v, ('a device on port %s: %s' % (arg, dev[0].strip())) if dev
                else 'nothing on port %s' % arg,
                'a device enumerates on that socket', txt)
    return (NODATA, 'no reading taken', '', 'no measurement hook for %r' % kind)


def manual_rows_for(station, rows, state, ignored):
    out = []
    for r in sorted((x for x in rows if x.category == 'manual'
                     and x.group == station), key=lambda x: x.num):
        if r.num in ignored or state.verdict(r.num) == PASS:
            continue
        out.append(r)
    return out


def run_manual(a, rows, state, ignored, glass, passno):
    """The manual set, stepped in station order. A station card first, then one
    dialog per owed row; `back` re-does the step before, `pause` stops the pass
    where it is."""
    t0 = time.time()
    steps = []                      # flat (station, row) list, for `back`
    for st, _name, _hand, _rails in STATIONS:
        for r in manual_rows_for(st, rows, state, ignored):
            steps.append((st, r))
    if not steps:
        glass.progress('manual set: nothing owed')
        return 0.0
    cur = state.d.get('current') or {}
    i = int(cur.get('step', 0)) if cur.get('phase') == 'manual' else 0
    i = max(0, min(i, len(steps) - 1))
    carded = set()
    rails_up = False
    while i < len(steps):
        st, r = steps[i]
        state.d['current'] = {'phase': 'manual', 'step': i, 'pass': passno,
                             'row': r.num}
        state.save()
        if st not in carded:
            card_ans = station_card(st, steps, glass, i)
            carded.add(st)
            if card_ans['button'] == 'pause':
                raise Paused()
            if card_ans['button'] in ('skip', 'ignore'):
                reason = card_ans.get('reason') or 'station skipped'
                for j in range(i, len(steps)):
                    if steps[j][0] != st:
                        break
                    verdict = IGNORED if card_ans['button'] == 'ignore' else SKIPPED
                    record_manual(a, state, steps[j][1], verdict, reason, passno,
                                  ignored, glass)
                    i = j + 1
                continue
        if st in PANEL_STATIONS:
            # One loop for the whole station, not one dialog per row (S120).
            panel_station(a, st, rows, state, ignored, glass, passno)
            while i < len(steps) and steps[i][0] == st:
                i += 1
            continue
        need_rails = dict((k, rl) for k, _n, _h, rl in STATIONS)[st]
        if need_rails and not rails_up:
            rails_up = True
            glass.progress('the analog rails are raised once here, for the '
                           'analog stations')
        if st in PATCH_STATIONS:
            # One loop for the whole station as well (S121). It comes AFTER the
            # rails block above on purpose: this is the only station that needs
            # them, it is last in the order, and PW's rule is that they go up
            # once and late.
            patch_station(a, st, rows, state, ignored, glass, passno)
            while i < len(steps) and steps[i][0] == st:
                i += 1
            continue
        glass.progress('MANUAL station %d of %d, step %d of %d - row %d'
                       % (STATION_NUM[st], len(STATIONS), i + 1, len(steps), r.num))
        ans = one_step(a, r, glass, i, len(steps))
        if ans['button'] == 'pause':
            raise Paused()
        if ans['button'] == 'back':
            i = max(0, i - 1)
            continue
        apply_answer(a, state, r, ans, passno, ignored, glass)
        i += 1
    state.d['current'] = None
    if rails_up:
        glass.progress('the analog rails are lowered again')
    return time.time() - t0


def panel_station(a, st, rows, state, ignored, glass, passno):
    """One switch panel, as ONE LOOP (S120).

    The tester lights the indicator of the next button to press; the operator
    presses the button under it; the key code that comes back grades the switch
    row AND the indicator row, and the next indicator lights. The glass carries
    one button, NOT LIT, which is the only judgement a press cannot make.

    The loop advances on the PANEL, not on the glass: `Glass.post` puts the
    step up and `Glass.poll` is asked for an answer between bus reads, so a
    press on the unit ends the step in the time the bus takes (measured on
    MW-D24-2: the indicator is lit 1.8 ms after the write and one panel's key
    report costs about 3 ms of MH1's sweep -- see s120/panel-loop.md)."""
    side = PANEL_STATIONS[st]
    byrow = dict((r.num, r) for r in rows)
    verdicts = {}

    def land(num, verdict, note, operator=True):
        r = byrow.get(num)
        if r is None or num in ignored:
            return
        verdicts[num] = (verdict, note)
        state.put(num, verdict, pass_no=passno,
                  judged='operator' if operator else 'runner',
                  measured=note, limit='', evidence='', source='panel loop')

    bus = PL.InjectedBus(a.inject_keys) if a.inject_keys else PL.PanelBus()
    pending = {'paused': False}

    def ask(step, n, total, tries):
        if tries:
            lines = ['%s did not light.' % step.what.capitalize(),
                     'Press %s anyway, so the switch itself is still checked.'
                     % step.name]
        else:
            lines = ['Press the button that is lit: %s.' % step.name,
                     'It is %s that should be lit.' % step.what,
                     'If nothing lit, press NOT LIT.']
        btns = glass.post('instruct', 'Panel loop - %s' % step.name, lines,
                          ['notlit'], row=step.sw_row, station=st)

        def tick():
            ans = glass.poll(btns)
            if ans is None:
                return None
            glass.taken(ans)
            b = ans['button']
            if b == 'pause':
                pending['paused'] = True
                return 'skip'
            if b == 'ignore':
                pending['ignore'] = ans.get('reason') or 'other'
                return 'skip'
            return b
        return tick

    try:
        owed = set(r.num for r in rows
                   if r.group == st and r.num not in ignored
                   and state.verdict(r.num) != PASS)
        steps, extra = PL.loop(bus, side, ask, timeout=a.panel_timeout,
                               log=glass.progress, owed=owed)
        for step in steps:
            land(step.sw_row, step.sw or NODATA, step.sw_note
                 or 'the loop did not reach this button')
            land(step.led_row, step.led or NODATA, step.led_note
                 or 'the loop did not reach this indicator')
            if pending['paused']:
                break
        if pending['paused']:
            raise Paused()
        # The indicators that no write can move: they are lit whenever the unit
        # is on, so one question grades them all.
        if 'always_on' in extra:
            nums, what = extra['always_on']
            owed_ao = [n for n in nums if n in owed]
            if owed_ao:
                ans = glass.ask('instruct', 'Panel loop - the always-lit rings',
                                ['Two indicators are lit whenever the unit is '
                                 'on and nothing can switch them off.',
                                 'Look at %s.' % what,
                                 'Are both lit?'], ['yes', 'no'], station=st)
                if ans['button'] == 'pause':
                    raise Paused()
                for n in owed_ao:
                    if ans['button'] == 'yes':
                        land(n, PASS, 'the operator confirmed it is lit')
                    elif ans['button'] == 'no':
                        land(n, FAIL, 'the operator answered that it is not lit')
                    else:
                        land(n, SKIPPED, ans.get('reason') or 'other')
        # The encoder: it turns, and its ring steps round.
        if 'encoder' in extra:
            turn_row, led_row = extra['encoder']
            if turn_row in owed:
                land(*((turn_row,) + panel_encoder(bus, glass, st,
                                                   a.panel_timeout)))
            if led_row in owed:
                PL.encoder_leds(bus)
                ans = glass.ask('instruct', 'Panel loop - the encoder ring',
                                ['The eight indicators around the encoder have '
                                 'just been stepped round twice.',
                                 'Did all eight light in turn?'],
                                ['yes', 'no'], row=led_row, station=st)
                if ans['button'] == 'pause':
                    raise Paused()
                if ans['button'] == 'yes':
                    land(led_row, PASS, 'the operator saw all eight light in turn')
                elif ans['button'] == 'no':
                    land(led_row, FAIL, 'the operator did not see all eight light')
                else:
                    land(led_row, SKIPPED, ans.get('reason') or 'other')
    finally:
        try:
            bus.light(0)
            bus.light_enc(0)
        except Exception:
            pass
        bus.close()
        glass.clear()
        state.save()
    glass.progress('panel loop (%s): %d rows graded'
                   % (PL.PANEL_NAME[side], len(verdicts)))
    return verdicts


def patch_station(a, st, rows, state, ignored, glass, passno):
    """The analog paths, as ONE LOOP (S121).

    The tester prompts one patch, the operator makes it, and the step ends the
    moment the tone arrives -- no Enter, and the next prompt is already up
    while the last one is being scored. One patch can prove more than one row
    (a stereo jack is one connection and three checks), and one row can be
    proved by more than one patch (an output XLR and the TRS jack beside it
    carry the same bus off the same stage), so the verdicts are folded
    worst-wins exactly as a row covered by two tests always has been.
    """
    byrow = dict((r.num, r) for r in rows)
    owed = set(r.num for r in rows
               if r.group == st and r.num not in ignored
               and state.verdict(r.num) != PASS)
    plist = PT.PatchList(PT.find_list_dir())
    limits = PT.Limits.load(plist.dir)
    unit = PT.Unit(symdir=a.patch_symdir)
    patcher = PT.pick_patcher(glass)
    station = PT.Station(plist, unit, patcher, glass, limits,
                         log=glass.progress)
    try:
        results = station.run()
    finally:
        try:
            station.teardown()
        except Exception as e:
            glass.progress('the analog station could not be torn down: %s' % e)
    # -- fold the paths onto the catalog rows -----------------------------
    per_row = {}
    for res in results:
        for num in (int(x) for x in (res['rows'] or '').split()):
            per_row.setdefault(num, []).append(res)
    verdicts = {}
    for num, hits in sorted(per_row.items()):
        if num not in byrow or num in ignored:
            continue
        worst = max(hits, key=lambda h: RANK.get(h['verdict'], 9))
        v = worst['verdict']
        if v == PT.MISPATCH:                # never a unit verdict on its own
            v = NODATA
        note = worst['why']
        if len(hits) > 1:
            note += ' (%d of %d checks on this item)' % (
                sum(1 for h in hits if h['verdict'] == worst['verdict']),
                len(hits))
        state.put(num, v, pass_no=passno, judged='runner', measured=note,
                  limit=worst.get('detail', ''), evidence='',
                  source='analog patch loop')
        verdicts[num] = v
    # -- the rows proved by the paths that run over them -------------------
    for num, partners in sorted(PATCH_PARTNERS.items()):
        if num not in byrow or num in ignored or num not in owed:
            continue
        got = [verdicts[p] for p in partners if p in verdicts]
        if not got:
            continue
        v = max(got, key=lambda x: RANK.get(x, 9))
        state.put(num, v, pass_no=passno, judged='runner',
                  measured='proved by the signal paths that cross this link: '
                           '%s' % plain_rows(byrow, partners),
                  limit='', evidence='', source='analog patch loop')
        verdicts[num] = v
    state.save()
    glass.progress('analog paths: %d rows graded from %d checks'
                   % (len(verdicts), len(results)))
    return verdicts


def plain_rows(byrow, nums):
    return ', '.join(byrow[n].panel for n in nums if n in byrow)


def panel_encoder(bus, glass, st, timeout):
    """The encoder ring itself: one detent each way, read off the bus.

    A detent sends the ring's new position, so direction is the difference
    between two positions and not a flag -- and the position wraps 8 -> 1 and
    1 -> 8, which is why the comparison is on the wrap as well as the step."""
    btns = glass.post('instruct', 'Panel loop - the encoder',
                      ['Turn the encoder ONE click clockwise, then ONE click '
                       'anticlockwise.',
                       'The tester reads the ring position each time.'],
                      ['notlit'], station=st)
    seen, last = [], None
    t0 = time.time()
    while time.time() - t0 < timeout:
        got = bus.wait_key(0.2, tick=lambda: glass.poll(btns))
        if got is None:
            continue
        kind, value, _ms = got
        if kind == 'glass':
            glass.taken({'button': value})
            return SKIPPED, 'the operator stopped at the encoder'
        if kind != 'enc':
            continue
        if last is not None and value != last:
            seen.append(1 if (value - last) % 8 == 1 else -1)
        last = value
        if 1 in seen and -1 in seen:
            break
    try:
        os.remove(glass.prompt_path)
    except OSError:
        pass
    if 1 in seen and -1 in seen:
        return PASS, 'the ring position stepped both ways: %r' % (seen,)
    if seen:
        return FAIL, ('the ring only stepped %s'
                      % ('clockwise' if 1 in seen else 'anticlockwise'))
    return NODATA, 'the encoder sent no ring position within %.0f s' % timeout


def station_card(st, steps, glass, i):
    name = STATION_NAME[st]
    hand = dict((k, h) for k, _n, h, _r in STATIONS)[st]
    rails = dict((k, rl) for k, _n, _h, rl in STATIONS)[st]
    n = sum(1 for s, _r in steps[i:] if s == st)
    lines = ['What you need in hand: %s.' % hand,
             '%d check%s at this station.' % (n, '' if n == 1 else 's')]
    if rails:
        lines.append('The analog supplies are LIVE for this station.')
    return glass.ask('station', 'Station %d - %s' % (STATION_NUM[st], name),
                     lines, ['ack'], station=st, station_num=STATION_NUM[st])


def one_step(a, r, glass, i, total):
    s = r.step
    title = 'Check %d - %s' % (r.num, r.panel)
    if s['kind'] == MEASURE:
        return glass.ask('instruct', title,
                         [s['action'], 'Press Done when it is in place; the '
                          'unit then checks that %s.' % s['check']],
                         ['done', 'back'], row=r.num)
    if s['kind'] == JUDGE:
        return glass.ask('instruct', title, [s['action'], s['question']],
                         ['yes', 'no', 'back'], row=r.num)
    # FIXTURE: the step is real, the thing it needs is not here.
    return glass.ask('instruct', title,
                     [s['action'],
                      'This needs something that is not at the bench: %s.'
                      % s['reason'],
                      'Press Done if you have it; otherwise Skip.'],
                     ['done', 'back'], row=r.num)


def apply_answer(a, state, r, ans, passno, ignored, glass):
    b = ans['button']
    s = r.step
    if b == 'ignore':
        reason = ans.get('reason') or 'other'
        write_ignore(a.ignored, a.serial, r.num, reason, a.catalog_md5)
        ignored[r.num] = dict(reason=reason)
        state.put(r.num, IGNORED, pass_no=passno, judged='operator',
                  measured='ignored: ' + reason, limit='', evidence='',
                  source='operator')
        return
    if b == 'skip':
        record_manual(a, state, r, SKIPPED, ans.get('reason') or 'other',
                      passno, ignored, glass)
        return
    if b == 'no':
        state.put(r.num, FAIL, pass_no=passno, judged='operator',
                  measured='the operator answered No to: ' + s.get('question', ''),
                  limit=s.get('question', ''), evidence='', source='operator')
        return
    if b == 'yes':
        state.put(r.num, PASS, pass_no=passno, judged='operator',
                  measured='the operator answered Yes to: ' + s.get('question', ''),
                  limit=s.get('question', ''), evidence='', source='operator')
        return
    # done -> the runner takes the reading, where there is one to take
    if s['kind'] == MEASURE:
        v, m, lim, ev = measure(s['measure'], a.tools)
        state.put(r.num, v, pass_no=passno, judged='runner', measured=m,
                  limit=lim, evidence=ev, source='operator set it up')
        glass.progress('row %d: %s - %s' % (r.num, v, m))
        return
    state.put(r.num, NODATA, pass_no=passno, judged='operator',
              measured='acknowledged, but nothing is measured for this row yet',
              limit=s.get('check', ''), evidence='', source='operator')


def record_manual(a, state, r, verdict, reason, passno, ignored, glass):
    if verdict == IGNORED:
        write_ignore(a.ignored, a.serial, r.num, reason, a.catalog_md5)
        ignored[r.num] = dict(reason=reason)
    state.put(r.num, verdict, pass_no=passno, judged='operator',
              measured='%s: %s' % (verdict.lower(), reason), limit='',
              evidence='', source='operator')


def record_not_run(rows, state, passno):
    """Every row that is NOT RUN gets its line, once, with its reason. §1: never
    silently dropped. `force=True` (S119): NOT TESTED here is the catalog's own
    classification, not a graded measurement, so it must land even when an
    earlier SKIPPED/NO DATA/FAIL outranks it -- see `State.put`."""
    for r in rows:
        if r.category != 'not-run':
            continue
        if state.verdict(r.num) in (PASS, IGNORED):
            continue
        state.put(r.num, NOTTESTED, pass_no=passno, judged='-',
                  measured='', limit='', evidence=r.reason,
                  source='', reason=r.reason, force=True)


# ---------------------------------------------------------------------------
# The review screen, and the next pass
# ---------------------------------------------------------------------------
def review(rows, state, ignored, glass, a):
    """After a pass and its report: every row without a PASS, walked one at a
    time, and any of them can be set aside before anything else runs (S117 §5).

    IT IS A WALK, NOT A LIST WITH CHECKBOXES, and that is deliberate. The glass
    has no row picker and building one would be the only new widget in this
    whole change; a walk needs none, and it costs the operator NOTHING when they
    have nothing to set aside -- the first screen already carries START NEXT
    PASS, so one press starts the next pass. Walking is only paid by an operator
    who is actually setting rows aside, one press per row they step past and two
    per row they set aside.
    """
    i = 0
    while True:
        owed = owed_rows(rows, state, ignored)
        if not owed:
            glass.ask('review', 'Nothing is owed',
                      ['Every check has a pass or an agreed set-aside.',
                       'The report on this unit is complete.'], ['ack'])
            return False
        i = max(0, min(i, len(owed) - 1))
        r = owed[i]
        v = state.verdict(r.num) or 'not run yet'
        lines = ['%d row%s still owed on this unit. Start the next pass, or step '
                 'through them and set aside what cannot be run.'
                 % (len(owed), '' if len(owed) == 1 else 's'),
                 '',
                 'Check %d - %s' % (r.num, r.panel),
                 'Result so far: %s.' % v.lower()]
        m = (state.row(r.num) or {}).get('measured') or ''
        if m:
            lines.append(scrub(m)[:160])
        ans = glass.ask('review', 'Review - pass %d done - %d of %d owed'
                        % (state.d['passes'], i + 1, len(owed)),
                        lines, ['next-pass', 'next', 'back', 'stop'],
                        row=r.num, owed=len(owed))
        b = ans['button']
        if b == 'next-pass':
            return True
        if b == 'stop' or b == 'pause':
            return False
        if b == 'next':
            i += 1
            if i >= len(owed):
                i = 0
            continue
        if b == 'back':
            i -= 1
            continue
        if b == 'ignore':
            reason = ans.get('reason') or 'other'
            write_ignore(a.ignored, a.serial, r.num, reason, a.catalog_md5)
            ignored[r.num] = dict(reason=reason, stamp=stamp())
            state.put(r.num, IGNORED, pass_no=state.d['passes'],
                      judged='operator', measured='set aside: ' + reason,
                      limit='', evidence='', source='operator')
            state.save()
            continue
        if b == 'skip':
            return False


def owed_rows(rows, state, ignored):
    """Owed = no PASS yet and not IGNORED, and something can actually be run for
    it: a NOT RUN row with nothing behind it is not owed, it is reported."""
    out = []
    for r in rows:
        if r.num in ignored or state.verdict(r.num) in (PASS, IGNORED):
            continue
        if r.category == 'not-run':
            continue
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------
def scrub(text):
    """The human page carries no Matrix-internal vocabulary, so the one place a
    verdict's own words can smuggle some in -- the measured/limit strings the
    runner wrote -- is filtered here. Test ids become their plain-English
    names; anything else internal becomes a plain word. The JSON twin keeps the
    original, so nothing is lost, only moved."""
    s = text or ''
    for t in sorted(PLAIN, key=len, reverse=True):
        s = re.sub(r'(?<![A-Za-z0-9-])%s(?![A-Za-z0-9-])' % re.escape(t),
                   PLAIN[t], s)
    s = re.sub(r'\bfw\.csv\b', 'the wiring table', s)
    s = re.sub(r'\s*\bS\d{2,3}\b', '', s)
    s = re.sub(r'\b[A-Z][a-z]+\d{3}[A-Z][a-z]+\d{3}\b', 'a control setting', s)
    s = re.sub(r'\b(?:dsp4|s89|d24)_\w+(?:\.py|\.sh)?', 'a bench tool', s)
    s = re.sub(r'\bMW/\S+', 'a file in the repository', s)
    s = re.sub(r'\bC[12]_[A-Z]\w*', 'a processing node', s)
    s = re.sub(r'\b([AM])([1-8])\b', r'group \1\2', s)
    s = re.sub(r'\bgroup ([AM])([1-8])\b', 'a run group', s)
    return s


def tally(rows, state, ignored):
    t = {PASS: 0, FAIL: 0, NODATA: 0, IGNORED: 0, SKIPPED: 0, NOTTESTED: 0,
         'no verdict': 0}
    for r in rows:
        v = IGNORED if r.num in ignored else state.verdict(r.num)
        t[v if v in t else 'no verdict'] += 1
    return t


def write_report(a, rows, state, ignored, stale, timing):
    os.makedirs(a.reports, exist_ok=True)
    st = stamp().replace(':', '')
    base = os.path.join(a.reports, '%s-%s' % (a.serial, st))
    t = tally(rows, state, ignored)
    try:
        import d24_selftest as S
        img = (S.FACTORY_TEST_IMAGE_NAME, S.FACTORY_TEST_BUILD_CFG)
    except Exception:                                   # noqa: BLE001
        img = ('factory-test-v1', ())

    def line_for(r):
        e = state.row(r.num) or {}
        v = IGNORED if r.num in ignored else (e.get('verdict') or 'no verdict')
        who = {'runner': 'the unit', 'operator': 'the operator'}.get(
            e.get('judged', ''), '-')
        return r, e, v, who

    # FAILs first (S117 §4), then the things that could not answer, then what
    # was never run, then what was set aside. `RANK` is the worst-wins order for
    # merging verdicts; this is the reading order for a person, which is not the
    # same list -- a row with no verdict at all belongs after a NO DATA, not
    # before a FAIL.
    show = {FAIL: 0, NODATA: 1, '': 2, SKIPPED: 3, NOTTESTED: 4, IGNORED: 5,
            PASS: 6}
    order = sorted(rows, key=lambda r: (show.get(
        IGNORED if r.num in ignored else state.verdict(r.num), 2), r.num))

    md = []
    md.append('# D24 factory test report')
    md.append('')
    md.append('Unit %s  ·  %s  ·  pass %d  ·  test image %s'
              % (a.serial, stamp(), state.d['passes'], img[0]))
    md.append('')
    md.append('| result | rows |')
    md.append('|---|---|')
    for k in (PASS, FAIL, NODATA, IGNORED, SKIPPED, NOTTESTED, 'no verdict'):
        label = {NODATA: 'no data', NOTTESTED: 'not tested'}.get(k, k.lower())
        md.append('| %s | %d |' % (label, t[k]))
    md.append('| **all rows** | **%d** |' % len(rows))
    md.append('')
    md.append('Wall time this pass %s.  Automatic part %s, operator part %s.'
              % (secs(timing.get('wall')), secs(timing.get('auto')),
                 secs(timing.get('manual'))))
    md.append('')
    if t[IGNORED]:
        md.append('**This unit cannot be signed off while %d row%s ignored.**'
                  % (t[IGNORED], ' is' if t[IGNORED] == 1 else 's are'))
        md.append('')
    md.append('## Every check that is not a pass')
    md.append('')
    md.append('| check | what it is | result | reading | limit | judged by | pass | what to do |')
    md.append('|---|---|---|---|---|---|---|---|')
    for r in order:
        rr, e, v, who = line_for(r)
        if v == PASS:
            continue
        md.append('| %d | %s | %s | %s | %s | %s | %s | %s |'
                  % (rr.num, cell(rr.report_name), v.lower(),
                     cell(scrub(e.get('measured', '')), 90),
                     cell(scrub(e.get('limit', '')), 60), who,
                     e.get('pass_no', '-'),
                     cell(scrub(e.get('reason') or remedy(rr, e)), 140)))
    md.append('')
    md.append('## Every check that passed')
    md.append('')
    md.append('| check | what it is | reading | judged by | pass |')
    md.append('|---|---|---|---|---|')
    for r in sorted(rows, key=lambda x: x.num):
        rr, e, v, who = line_for(r)
        if v != PASS:
            continue
        md.append('| %d | %s | %s | %s | %s |'
                  % (rr.num, cell(rr.report_name), cell(scrub(e.get('measured', '')), 90),
                     who, e.get('pass_no', '-')))
    md.append('')
    if ignored:
        md.append('## Checks set aside on purpose')
        md.append('')
        md.append('| check | what it is | reason | when |')
        md.append('|---|---|---|---|')
        for n in sorted(ignored):
            rr = next((x for x in rows if x.num == n), None)
            d = ignored[n]
            md.append('| %d | %s | %s | %s |'
                      % (n, cell(rr.report_name if rr else ''), d.get('reason', ''),
                         d.get('stamp', '')))
        md.append('')
    if stale:
        md.append('%d earlier set-aside%s expired because the check list moved '
                  'and now count as owed: %s.'
                  % (len(stale), '' if len(stale) == 1 else 's',
                     ', '.join(str(n) for n in sorted(stale))))
        md.append('')
    md.append('## History')
    md.append('')
    any_hist = False
    for r in sorted(rows, key=lambda x: x.num):
        h = (state.row(r.num) or {}).get('history') or []
        if not h:
            continue
        any_hist = True
        md.append('- **%d %s**: %s' % (r.num, cell(r.report_name), '; '.join(
            '%s on pass %s (%s)' % (x.get('verdict'), x.get('pass_no', '-'),
                                    scrub(x.get('measured', ''))[:70])
            for x in h)))
    if not any_hist:
        md.append('Nothing has changed verdict on this unit yet.')
    md.append('')
    with open(base + '.md', 'w') as fh:
        fh.write('\n'.join(md) + '\n')

    twin = dict(serial=a.serial, stamp=stamp(), passes=state.d['passes'],
                catalog_md5=a.catalog_md5,
                factory_image=dict(name=img[0], build_cfg=list(img[1])),
                timing=timing, tally={k: t[k] for k in t},
                ignored={str(k): v for k, v in ignored.items()},
                stale_ignores=sorted(stale),
                rows=[dict(num=r.num, board=r.board, item=r.item,
                           cls=r.cls, group=r.group, category=r.category,
                           tests=r.tests, covers=r.covers,
                           verdict=(IGNORED if r.num in ignored
                                    else state.verdict(r.num)),
                           **{k: v for k, v in (state.row(r.num) or {}).items()
                              if k != 'verdict'})
                      for r in sorted(rows, key=lambda x: x.num)])
    with open(base + '.json', 'w') as fh:
        json.dump(twin, fh, indent=1, sort_keys=True)
    return base + '.md', base + '.json'


def remedy(r, e):
    v = e.get('verdict')
    if v == FAIL:
        return 'look at this part before the unit goes on'
    if v == NODATA:
        return 'the check ran but could not read an answer'
    if v == SKIPPED:
        return 'run it when what it needs is at the bench'
    if not v:
        return 'not run in this pass'
    return 'no action recorded'


def cell(s, n=80):
    s = ' '.join((s or '').split()).replace('|', '/')
    return s if len(s) <= n else s[:n - 1] + '…'


def secs(v):
    return '-' if v is None else '%d s' % round(v)


DIALOG_COLS = ['station', 'station_name', 'check', 'panel_name', 'cls',
               'category', 'kind', 'station_card', 'instruction', 'question',
               'buttons', 'runner_measures', 'not_run_reason']


def dump_dialogs(rows, path):
    """Every manual dialog this catalog produces, in the order the operator
    meets them, plus every row that is NOT RUN and the reason. One file, so the
    wording is reviewed once rather than a screen at a time."""
    hand = dict((k, h) for k, _n, h, _r in STATIONS)
    with open(path, 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=DIALOG_COLS)
        w.writeheader()
        for st, name, _h, rails in STATIONS:
            mine = [r for r in rows if r.group == st]
            card = ('What you need in hand: %s. %d check(s) at this station.%s'
                    % (hand[st], sum(1 for r in mine if r.category == 'manual'),
                       ' The analog supplies are LIVE for this station.'
                       if rails else ''))
            for r in sorted(mine, key=lambda x: x.num):
                s = r.step or {}
                w.writerow(dict(
                    station=STATION_NUM[st], station_name=name, check=r.num,
                    panel_name=r.panel, cls=r.cls, category=r.category,
                    kind=s.get('kind', ''), station_card=card,
                    instruction=s.get('action', ''),
                    question=s.get('question', ''),
                    buttons=('yes/no' if s.get('kind') == JUDGE else
                             'done' if s.get('kind') in (MEASURE, FIXTURE) else
                             ('yes/no' if s.get('question') else 'notlit')
                             if s.get('kind') == LOOP else ''),
                    runner_measures=s.get('measure', '') or s.get('check', ''),
                    not_run_reason=r.reason if r.category == 'not-run' else ''))
        for r in sorted(rows, key=lambda x: x.num):
            if r.category != 'not-run' or r.group in STATION_NUM:
                continue
            w.writerow(dict(station='', station_name='not a station',
                            check=r.num, panel_name=r.panel, cls=r.cls,
                            category=r.category, kind='', station_card='',
                            instruction='', question='', buttons='',
                            runner_measures='', not_run_reason=r.reason))
    print('wrote %s' % path)


def check_md(path):
    bad = []
    for i, line in enumerate(open(path, encoding='utf-8'), 1):
        for pat, what in INTERNAL:
            for m in re.finditer(pat, line):
                bad.append('%s:%d: %r (%s)' % (os.path.basename(path), i,
                                               m.group(0), what))
    if bad:
        print('\n'.join(bad))
        print('\n%d internal token(s) in %s' % (len(bad), path))
        return 1
    print('%s: clean -- no Matrix-internal vocabulary' % path)
    return 0


# ---------------------------------------------------------------------------
def one_pass(a, rows, state, ignored, glass, csv_path, resumed):
    passno = state.d['passes'] + 1
    t0 = time.time()
    timing = {}
    if resumed and (state.d.get('current') or {}).get('phase') == 'manual':
        # Straight back to the step it stopped on. `current` is NOT touched
        # here -- run_manual() reads the step out of it.
        passno = int((state.d['current'] or {}).get('pass') or passno)
        glass.progress('resuming pass %d at the step it stopped on' % passno)
        # The automatic part of THIS pass already ran, before the pause. Its
        # seconds are in the state, so a resumed pass still reports them rather
        # than printing a dash for work that was done.
        timing['auto'] = (state.d.get('pass_timing') or {}).get('auto')
        timing['resumed'] = True
    else:
        state.d['current'] = {'phase': 'auto', 'pass': passno}
        state.save()
        if a.manual_only:
            timing['auto'] = None
        else:
            secs_auto, results, _owed = run_auto(a, rows, state, ignored, glass,
                                                 csv_path)
            timing['auto'] = secs_auto
            state.d['pass_timing'] = {'auto': secs_auto, 'pass': passno}
            stamped = stamp_auto(rows, state, results, passno)
            if stamped:
                print('   partner rows stamped: %s'
                      % ', '.join('%d->%d' % x for x in stamped))
            state.save()
    if a.auto_only:
        timing['manual'] = None
    else:
        timing['manual'] = run_manual(a, rows, state, ignored, glass, passno)
    record_not_run(rows, state, passno)
    state.d['passes'] = passno
    state.d['current'] = None
    timing['wall'] = time.time() - t0
    state.save()
    return timing


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--dir', default=DIR_DEFAULT)
    ap.add_argument('--tools', help='where d24_selftest.py lives (default: '
                                    'beside this file)')
    ap.add_argument('--patch-symdir', default=PT.FACTORY_TEST_PAIR_DIR,
                    help='the staged pair the analog station measures through')
    ap.add_argument('--catalog')
    ap.add_argument('--csv', help='the results file the auto runner appends to')
    ap.add_argument('--stage', default='/home/app/s90')
    ap.add_argument('--stdin', action='store_true',
                    help='answer the dialogs on stdin instead of through the '
                         'glass: "done", "yes", "no", "back", "pause", '
                         '"skip: fixture not built", "ignore: awaiting part"')
    ap.add_argument('--autoskip', action='store_true',
                    help='answer every dialog with Skip, reason "fixture not '
                         'built". For a station walk with no fixtures at all.')
    ap.add_argument('--auto-only', action='store_true')
    ap.add_argument('--manual-only', action='store_true')
    ap.add_argument('--report-only', action='store_true')
    ap.add_argument('--no-review', action='store_true',
                    help='write the report and stop; do not put the review '
                         'screen up')
    ap.add_argument('--no-app-restart', action='store_true', default=True)
    ap.add_argument('--app-restart', dest='no_app_restart', action='store_false')
    ap.add_argument('--ignore', type=int, metavar='NUM')
    ap.add_argument('--unignore', type=int, metavar='NUM')
    ap.add_argument('--reason', default='other')
    ap.add_argument('--reset-state', action='store_true',
                    help='forget this unit\'s cumulative verdicts and start at '
                         'pass 1. The ignores file is not touched.')
    ap.add_argument('--check-md', metavar='FILE')
    ap.add_argument('--dump-dialogs', metavar='FILE',
                    help='write every manual row\'s dialog text to a CSV and '
                         'exit: one row per catalog row, the station it is at, '
                         'what the operator is told, what they are asked, and '
                         'what the runner measures afterwards. This is the list '
                         'PW reviews -- the wording is generated, so the review '
                         'is of this file and not of 140 screens.')
    ap.add_argument('--panel-timeout', type=float, default=30.0,
                    help='how long one button in the panel loop waits for a '
                         'press before it lands NO DATA (default 30 s)')
    ap.add_argument('--inject-keys', metavar='FILE',
                    help='drive the panel loop from a scripted key stream '
                         'instead of the bus -- proves the runner side with no '
                         'finger at the bench (see d24_panel.py)')
    ap.add_argument('--serial')
    a = ap.parse_args()

    if a.check_md:
        sys.exit(check_md(a.check_md))

    a.tools = a.tools or HERE
    a.catalog = a.catalog or os.path.join(a.dir, 'test-catalog.csv')
    csv_path = a.csv or os.path.join(a.dir, 'item-status.csv')
    a.runall = os.path.join(a.dir, 'runall')
    a.reports = os.path.join(a.dir, 'reports')
    a.ignored = os.path.join(a.dir, 'ignored.csv')
    a.serial = a.serial or unit_serial()

    rows, a.catalog_md5 = load_catalog(a.catalog)
    warn = classify(rows)
    if a.dump_dialogs:
        dump_dialogs(rows, a.dump_dialogs)
        return
    state_path = os.path.join(a.runall, 'state.json')
    if a.reset_state and os.path.exists(state_path):
        os.remove(state_path)
    state = State(state_path, a.serial, a.catalog_md5)
    live, stale = read_ignored(a.ignored, a.serial, a.catalog_md5)

    if a.ignore:
        write_ignore(a.ignored, a.serial, a.ignore, a.reason, a.catalog_md5)
        state.put(a.ignore, IGNORED, pass_no=state.d['passes'],
                  judged='operator', measured='ignored: ' + a.reason,
                  limit='', evidence='', source='operator')
        state.save()
        print('row %d IGNORED on unit %s: %s' % (a.ignore, a.serial, a.reason))
        return
    if a.unignore:
        write_ignore(a.ignored, a.serial, a.unignore, '', a.catalog_md5)
        e = state.row(a.unignore)
        if e and e.get('verdict') == IGNORED:
            hist = e.get('history') or []
            back = hist.pop() if hist else None
            state.d['rows'][str(a.unignore)] = (
                dict(back, history=hist) if back else
                dict(verdict='', stamp=stamp(), history=hist))
        state.save()
        print('row %d UNIGNORED on unit %s' % (a.unignore, a.serial))
        return

    glass = Glass(a.runall, stdin=a.stdin, autoskip=a.autoskip)
    print('D24 RUN ALL -- unit %s -- catalog %s (%d rows) -- %s'
          % (a.serial, a.catalog_md5[:12], len(rows), stamp()))
    for w in warn:
        print('   catalog warning: %s' % w)
    cats = {}
    for r in rows:
        cats[r.category] = cats.get(r.category, 0) + 1
    print('   %s' % ', '.join('%s %d' % (k, cats[k]) for k in sorted(cats)))

    if a.report_only:
        md, js = write_report(a, rows, state, live, stale, {})
        print('report: %s\n        %s' % (md, js))
        return

    resumed = bool(state.d.get('current'))
    while True:
        try:
            timing = one_pass(a, rows, state, live, glass, csv_path, resumed)
        except Paused:
            state.save()
            glass.progress('paused at step %s of the operator set -- the next '
                           'START resumes here'
                           % ((state.d.get('current') or {}).get('step')))
            print('PAUSED')
            return
        resumed = False
        md, js = write_report(a, rows, state, live, stale, timing)
        t = tally(rows, state, live)
        print('\npass %d: %d PASS / %d FAIL / %d NO DATA / %d ignored / '
              '%d skipped / %d not tested (of %d rows) in %s'
              % (state.d['passes'], t[PASS], t[FAIL], t[NODATA], t[IGNORED],
                 t[SKIPPED], t[NOTTESTED], len(rows), secs(timing.get('wall'))))
        print('report: %s\n        %s' % (md, js))
        glass.progress('pass %d complete - report written - %d of %d rows pass'
                       % (state.d['passes'], t[PASS], len(rows)))
        if a.no_review or a.auto_only:
            break
        if not review(rows, state, live, glass, a):
            break
    glass.clear()


if __name__ == '__main__':
    main()
