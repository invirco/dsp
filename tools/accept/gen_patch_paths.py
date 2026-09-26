#!/usr/bin/env python3
"""gen_patch_paths.py -- the D24 audio patch list, generated (S121).

ONE list of signal paths for the analog station. Every entry is one D24 OUTPUT
reaching one D24 INPUT, named the way the panel names them, with the route that
makes it live, the stimulus, and what the reading has to be. The operator's
view of the same list is a sequence of PATCHES: one lead, moved once.

    gen_patch_paths.py [--out MW/D24/DSP/s121] [--check]

It writes three files and prints a summary:

    patch-paths.csv    one row per PATH (a measurement). The `patch` column
                       groups them: consecutive rows sharing a patch id are
                       sub-tests of ONE physical connection and the operator is
                       prompted once (runner-interface.md, `connect`).
    patch-routes.csv   one row per ROUTE id: the cells, by NAME, that make that
                       output live and everything else silent.
    patch-plan.md      the human table -- patches per lead, per cable type,
                       and the coverage proof.

WHERE THE FACTS COME FROM, and what is NOT invented here:

  * defs/products/d24/d24-io.csv -- the rear panel inventory: which socket is
    an XLR and which is a TRS jack, and that the "Aux Out A 1-2 ... 7-8" TRS
    jacks are a PAIRED JACK ALTERNATIVE to the Aux Out A1..A8 XLRs (the same
    eight aux buses reach both).
  * defs/products/d24/dsp.csv -- every cell this file names is checked to
    exist. A route that names a cell the product does not declare is a hard
    error, never a silent drop (the no-fallback rule).
  * tools/pi/d24_inputs.py -- MIC n is on strip n, which is what MeasChan and
    the Chan<nnn> cells are indexed by.
  * tools/dsp/dsp_codegen.py TEST_MEAS_LANE_CODES -- MeasChan 51/53/55 are the
    codec return lanes: the mini-jack tip, the talkback XLR and the mini-jack
    ring. Nothing else can measure those three inputs at all.
  * s121/harness-ref/d24-harness-ports.csv -- the harness revision's port
    table: panel name, direction, catalog row, and how each TRS jack is wired
    (MONITOR tip->hot with ring+sleeve->cold; the stereo jacks tip->L,
    ring->R, common sleeve). The catalog rows come from here so the station
    and the harness stamp the same rows.

THE STEREO RULE (PW 2026-09-26). Every stereo TRS jack, input or output, is
ONE patch through ONE standard lead, and the channels are separated by DRIVING
them separately, not by splitting the lead:

  * a stereo TRS OUTPUT through K2 (tip->pin 2, ring->pin 3) presents L-R at
    the XLR input, so the patch is three sub-tests -- L alone (normal), R alone
    (inverted), both in phase (a null). The null is what proves L and R match
    and are not crossed; the polarity of the L-alone reading is what proves tip
    and ring are not swapped.
  * a stereo TRS INPUT through K3 is driven from ONE balanced XLR output, whose
    pin 2 becomes L and pin 3 becomes R, so ONE stimulus reads both lanes at
    once -- L normal, R inverted, equal level. An inverted LEFT is a channel
    swap, scored as a swap and not as two failures.

POLARITY IS RELATIVE AND THE LIST SAYS SO. `polarity` is NOT an absolute sign:
a 1 kHz tone through this unit's loop arrives with the whole path's latency
rotated into its phase (units.csv records 91.40 samples on MW-D24-2, which is
1.9 cycles at 1 kHz). What the runner measures is the phase of the coherent
fit against TEST_OSC's own reference -- `_meas_a`/`_meas_b`, the signed
in-phase and quadrature amplitudes the measurement node already computes every
window -- and what the list asks for is that phase RELATIVE to a reference
reading taken on the SAME input lane earlier in the same pass. `ref` marks the
rows that ESTABLISH a reference; `normal` and `inverted` are judged against it.
Rows whose lane never carries a balanced reference (the codec lanes) carry
`info`, and say so, until a good unit sets them.
"""
import argparse
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(ROOT, 'tools', 'pi'))

DEFS_DSP = os.path.join(ROOT, 'defs', 'products', 'd24', 'dsp.csv')
DEFS_IO = os.path.join(ROOT, 'defs', 'products', 'd24', 'd24-io.csv')
OUT_DEFAULT = os.path.join(ROOT, 'MW', 'D24', 'DSP', 's121')
PORTS = os.path.join(OUT_DEFAULT, 'harness-ref', 'd24-harness-ports.csv')

# ---------------------------------------------------------------------------
# The leads. One of each, standard and off the shelf (PW 2026-09-26).
# ---------------------------------------------------------------------------
# `wiring` is what the operator's lead must actually be, and it is the reason
# each block reads the way it does. K2 and K4 are the same wiring with opposite
# XLR gender, because one goes INTO a panel input and the other ONTO a panel
# output; there is no adapter in the kit.
LEADS = {
    'K1': dict(name='XLR-F to XLR-M',
               wiring='straight balanced: pin 1-1, 2-2, 3-3',
               use='a D24 XLR output into a D24 XLR input'),
    'K2': dict(name='6.35 mm TRS to XLR-M',
               wiring='tip -> pin 2, ring -> pin 3, sleeve -> pin 1',
               use='a D24 TRS output jack into a D24 XLR input'),
    'K3': dict(name='XLR-F to 3.5 mm TRS',
               wiring='pin 2 -> tip, pin 3 -> ring, pin 1 -> sleeve',
               use='a D24 XLR output into the stereo mini-jack input'),
    'K4': dict(name='XLR-F to 6.35 mm TRS',
               wiring='pin 2 -> tip, pin 3 -> ring, pin 1 -> sleeve',
               use="a D24 XLR output into a combo jack's TRS line centre"),
    'K5': dict(name='150 ohm XLR-M terminator',
               wiring='150 ohm across pins 2-3, pin 1 to the shell',
               use='the input noise (EIN) reading, one input at a time'),
}

# The order the blocks are walked. It is the order that costs the operator the
# least: the lead type changes exactly four times, and inside K5 and K4 the
# hand is already on the input row it was on for K1.
BLOCK_ORDER = ('K1', 'K5', 'K4', 'K2', 'K3')

# ---------------------------------------------------------------------------
# The donor strip: where the oscillator goes in
# ---------------------------------------------------------------------------
# TEST_OSC REPLACES a strip's input block (dsp_codegen.py `_test_osc_inject`:
# "The stimulus REPLACES the strip's input rather than adding to it"), so the
# strip carrying the oscillator cannot also be measured. D24 declares Chan
# cells for strips 1..24 ONLY -- there is no strip 25 to hide the donor on --
# so the donor is one of the twenty-four and the list moves it out of the way
# when its own input is the one under test.
DONOR_DEFAULT = 24
DONOR_ALT = 1


def donor_for(strip):
    """The strip the oscillator is injected into while `strip` is measured."""
    return DONOR_ALT if strip == DONOR_DEFAULT else DONOR_DEFAULT


# ---------------------------------------------------------------------------
# Levels and windows -- PROVISIONAL, and each one says what it is derived from
# ---------------------------------------------------------------------------
# NOTHING HERE IS A SPEC LIMIT. These are the windows a factory reading has to
# land in for the path to be called proven, and every one of them is either
# (a) a topological ratio that follows from how the lead is wired, or (b) a
# placeholder marked so, waiting on a good unit or a PW ruling. The runner
# reads them from patch-paths.csv; it never carries a number of its own.
#
# THE BALANCED REFERENCE is not predicted at all: the first K1 patch on each
# input lane MEASURES the loop gain and every later reading on that lane is
# judged against it. That is what makes the list survive a change of drive
# level, a gain-law revision or a different unit.
#
# SINGLE-ENDED = BALANCED - 6.02 dB is the ratio, and it is a ratio, not a
# guess: a balanced XLR output drives pin 2 and pin 3 in anti-phase, so the
# differential the input sees is twice one leg; a TRS jack's tip drives one leg
# and the input's other leg sits at the sleeve. It holds only if the
# single-ended driver swings the same voltage as one leg of the balanced one,
# which is an OUTPUT-STAGE fact this repo does not record -- see the report's
# open items. The window is wide enough (+-3 dB) to pass either convention and
# narrow enough to catch a dead or halved path; PW tightens it from a good
# unit.
SINGLE_ENDED_DB = -6.02
LEVEL_TOL_DB = 3.0
# The null: L-R with L and R driven identically. What is left is the L/R match
# of the output stage plus the lead. -30 dB below the single-ended reading is
# a placeholder that a crossed or absent channel cannot reach; a good unit sets
# the real figure.
NULL_MAX_DB = -30.0
# The two sub-tests of a stereo output must match each other far more tightly
# than either matches the absolute window: they share everything but the
# channel.
STEREO_MATCH_TOL_DB = 1.5
# Tone present: how far above the lane's own idle floor the reading must rise
# before the runner will call it a tone at all, and how far below the measured
# lane every OTHER input must stay. 40 dB is the harness revision's figure for
# the same check (runner-interface.md, "Detecting a wrong connection").
TONE_MIN_OVER_FLOOR_DB = 40.0
ISOLATION_MIN_DB = 40.0

# The stimulus. 1 kHz because that is where the wrong-connection check is
# specified and where a switch pair isolates worst; -12 dBFS because S89e's
# loop window was taken there and it leaves headroom at every gain code the
# station uses.
TONE_HZ = 1000.0
TONE_DBFS = -12.0


# ---------------------------------------------------------------------------
# Reading the sources
# ---------------------------------------------------------------------------
def read_csv(path, comment='#'):
    with open(path, newline='') as fh:
        return list(csv.DictReader(l for l in fh if not l.startswith(comment)))


def load_cells():
    """Every cell name the product declares, so a route can be checked."""
    names = set()
    with open(DEFS_DSP, newline='') as fh:
        for row in csv.reader(fh):
            if row and row[0] and not row[0].startswith('#'):
                names.add(row[0])
    if len(names) < 1000:
        raise SystemExit('dsp.csv gave only %d cell names: wrong file?' % len(names))
    return names


def load_ports():
    """The harness revision's port table, keyed by panel name."""
    rows = read_csv(PORTS)
    out = {}
    for r in rows:
        out[r['port']] = r
    return out


# ---------------------------------------------------------------------------
# The output map: which D24 socket each DSP output actually reaches
# ---------------------------------------------------------------------------
# NOT invented here. docs/d24-dac-lane-xlr-candidate-20260913.md walked the
# Analog PCBA netlist DAC lane by DAC lane, and tools/dsp/gen_dsp_csv.py's
# AUX_DAC / MAIN_OUT_DAC tables are what the firmware actually emits. The two
# agree, and together they say something this station has to act on:
#
#   THREE REAR SOCKETS HAVE NO HOST-REACHABLE SOURCE ON A D24.
#   * PHONES L / PHONES R (analog J10, DAC_09/10) are C2_AUX_OUT_09/10 --
#     aux buses 9 and 10. D24 declares Aux001..Aux008 and no more, so no cell
#     exists to open them.
#   * Centre/LF Out (analog J55, DAC_14) is C2_AUX_OUT_12 -- aux bus 12, the
#     same story.
#   The candidate doc says it plainly at its §148-154: "the headphones
#   (DAC_09/10) have no DSP source node at all" and the Centre/LF XLR is a
#   PARK for aux 12, not a design. This station therefore cannot drive those
#   three sockets, and says so by name instead of generating a patch that
#   would fail for a reason that is not the unit's fault.
#
#   MONITOR L / MONITOR R ARE THE CROSSOVER'S 3rd AND 4th OUTPUTS.
#   Analog J53/J54 are DAC_15/16 = C2_MAIN_OUT_03/04, whose cells are named
#   MainCtr001* and MainSub001*. So the rear monitor jacks are fed by the main
#   crossover's CENTRE and SUB legs, not by the monitor bus (C2_MON_OUT goes
#   to the codec and the panel speaker, which is a different thing entirely --
#   S102 found the same and left the question open). Two consequences the list
#   has to carry: the crossover is set wide and shallow for the station, and
#   MONITOR R -- the SUB leg -- is tested at a LOW frequency, because a
#   crossover exists precisely to stop 1 kHz reaching it.
UNREACHABLE = {
    'C/LF': ('the Centre/LF XLR is DAC_14, which the firmware feeds from aux '
             'bus 12 (C2_AUX_OUT_12); D24 declares aux buses 1-8 only, so no '
             'cell can open it'),
    'PHONES L': ('the headphone jack is DAC_09/10, which the firmware feeds '
                 'from aux buses 9 and 10 (C2_AUX_OUT_09/10); D24 declares aux '
                 'buses 1-8 only, so no cell can open it'),
    'PHONES R': ('the headphone jack is DAC_09/10, which the firmware feeds '
                 'from aux buses 9 and 10 (C2_AUX_OUT_09/10); D24 declares aux '
                 'buses 1-8 only, so no cell can open it'),
}

# The crossover, set once for the station: as high and as gentle as the cell
# laws allow (50..500 Hz, 6..24 dB/octave), so the two monitor legs overlap as
# much as the product permits and each can be reached with one tone.
XOVER_FREQ_HZ = 500.0
XOVER_SLOPE = 6
# MONITOR R is the SUB leg. 100 Hz is two octaves under the crossover, where a
# 6 dB/octave leg is within about 1 dB of its passband.
SUB_TONE_HZ = 100.0


def fmt(v):
    """A cell value the way s89_set.py spells it: floats as f<x>, ints bare."""
    return ('f%g' % v) if isinstance(v, float) else str(int(v))


def cells_close_assigns(strips, auxes):
    """Every strip's route to every bus this station can drive, shut.

    The oscillator REPLACES the donor strip's input, so the other strips carry
    only their own converter lanes -- which are the inputs under test, with a
    patch lead in them. Without this, a lead into MIC 5 puts MIC 5 on the main
    bus and the next MAIN patch measures the lead instead of the DSP.
    """
    out = []
    for s in strips:
        out.append('Chan%03dMainOn001=0' % s)
        out.append('Chan%03dCtrOn001=0' % s)
        for a in auxes:
            out.append('Chan%03dAuxOn%03d=0' % (s, a))
    return out


def cells_donor_transparent(d):
    """The donor strip, made a wire: nothing between the oscillator and the bus.

    S54-2's lesson, and S115's: a donor left at the configuration defaults has
    its gate and compressor ON, and a route that is not asserted still produces
    a plausible number.
    """
    return ['Chan%03dPol001=0' % d,
            'Chan%03dEqOn001=0' % d,
            'Chan%03dEqHpf001=0' % d,
            'Chan%03dGateOn001=0' % d,
            'Chan%03dCompOn001=0' % d,
            'Chan%03dTubeOn001=0' % d,
            'Chan%03dDelay001=0' % d,
            'Chan%03dLevel001=f1.0' % d,
            'Chan%03dMute001=0' % d,
            'Chan%03dPan001=f0.5' % d,
            'Chan%03dGain001=f1.0' % d]


def cells_bus_masters(auxes):
    """Every bus master open at unity, so a reading is the PATH and not a fader."""
    out = []
    for a in auxes:
        out += ['Aux%03dLevel001=f1.0' % a, 'Aux%03dMute001=0' % a,
                'Aux%03dEqOn001=0' % a, 'Aux%03dLimiterOn001=0' % a,
                'Aux%03dAntiFbOn001=0' % a, 'Aux%03dDelay001=0' % a]
    out += ['Main001Level001=f1.0', 'Main001Mute001=0', 'Main001Delay001=0',
            'MainL001Level001=f1.0', 'MainL001Mute001=0',
            'MainR001Level001=f1.0', 'MainR001Mute001=0',
            'MainCtr001Level001=f1.0', 'MainCtr001Mute001=0',
            'MainSub001Level001=f1.0', 'MainSub001Mute001=0',
            'MainL001CrossoverFreq001=f%g' % XOVER_FREQ_HZ,
            'MainL001CrossoverSlope001=%d' % XOVER_SLOPE]
    return out


def route_cells(donor, drive, auxes):
    """The cells that change per patch: which bus the donor strip feeds.

    `drive` is the list's own word for the output under test -- 'aux:1',
    'aux:1+2', 'main:L', 'main:R', 'xover:ctr', 'xover:sub' or 'none'. Every
    other assign on the donor is written 0 in the same breath, so a route is
    always asserted whole and never left half-set from the patch before.
    """
    off = {'main': 0, 'ctr': 0}
    off_aux = dict((a, 0) for a in auxes)
    pan = 0.5
    kind, _, arg = drive.partition(':')
    if kind == 'aux':
        for a in (int(x) for x in arg.split('+')):
            off_aux[a] = 1
    elif kind == 'main':
        off['main'] = 1
        pan = 0.0 if arg == 'L' else 1.0
    elif kind == 'xover':
        off['ctr'] = 1
    elif kind != 'none':
        raise SystemExit('unknown drive %r' % drive)
    out = ['Chan%03dMainOn001=%d' % (donor, off['main']),
           'Chan%03dCtrOn001=%d' % (donor, off['ctr']),
           'Chan%03dPan001=%s' % (donor, fmt(pan))]
    for a in auxes:
        out.append('Chan%03dAuxOn%03d=%d' % (donor, a, off_aux[a]))
        if off_aux[a]:
            out.append('Chan%03dAuxSend%03d=f1.0' % (donor, a))
            out.append('Chan%03dAuxPick%03d=3' % (donor, a))   # post-fader
    return out


# ---------------------------------------------------------------------------
# The list
# ---------------------------------------------------------------------------
AUXES = tuple(range(1, 9))
STRIPS = tuple(range(1, 25))
# The codec return lanes. MeasChan 1..32 are strips and 33..50 are buses, so
# these three inputs cannot be measured any other way at all
# (dsp_codegen.py TEST_MEAS_LANE_CODES, proven on the part in S70/S73).
LANE_TALKBACK = 53
LANE_MJ_L = 51
LANE_MJ_R = 55

# The output the list parks a lead on when the patch is about the INPUT. AUX 1
# is chosen because it is the first path the station proves (patch 1), so by
# the time anything is parked on it, it has already passed.
PARK_OUT = 'AUX 1'
PARK_DRIVE = 'aux:1'
# The input the list parks a lead in when the patch is about the OUTPUT. MIC 1
# for the same reason, and because it is not the donor strip.
PARK_IN = 'MIC 1'
PARK_IN_STRIP = 1

# The eight aux XLRs and the two main XLRs, in the order the K1 block proves
# them. Every one is a socket in its own right and gets a patch of its own
# before AUX 1 is parked for the rest of the block. (C/LF is missing on
# purpose: see UNREACHABLE.)
XLR_OUTS = [('AUX %d' % a, 'aux:%d' % a) for a in AUXES] + [
    ('MAIN L', 'main:L'), ('MAIN R', 'main:R')]

# The stereo TRS output jacks: one patch, three sub-tests. `l`/`r` are the two
# aux buses the jack's tip and ring carry -- the SAME buses the Aux Out A XLRs
# carry, tapped in parallel off the same output stage (findings.md: the TRS
# jack is "J9.19/20 in parallel" with the XLR), which is why a jack can fail
# while its XLR passes and both are worth a patch.
STEREO_TRS_OUTS = [('AUX A %d-%d' % (a, a + 1), a, a + 1) for a in (1, 3, 5, 7)]

# The two mono TRS output jacks. They are the crossover's centre and sub legs
# (see UNREACHABLE's note), so the SUB one is tested low.
MONO_TRS_OUTS = [('MONITOR L', 'xover:ctr', TONE_HZ,
                  'the crossover CENTRE leg, tested in its passband'),
                 ('MONITOR R', 'xover:sub', SUB_TONE_HZ,
                  'the crossover SUB leg: a 1 kHz tone is what the crossover '
                  'exists to keep out of it, so this one path is tested at '
                  '%g Hz' % SUB_TONE_HZ)]

COLUMNS = ('path', 'patch', 'lead', 'block', 'out', 'in', 'sub', 'drive',
           'lane', 'donor', 'route', 'freq_hz', 'level_dbfs', 'expect',
           'level_ref', 'polarity', 'rows', 'prompt', 'note')


class Builder:
    def __init__(self, ports, cells):
        self.ports, self.cells = ports, cells
        self.paths, self.routes, self.missing = [], {}, []
        self.n = 0
        self.patch = 0
        self.notrun = []

    def rows_for(self, *names):
        out = []
        for nm in names:
            p = self.ports.get(nm)
            if p and p.get('catalog_row'):
                out.append(p['catalog_row'])
        return ' '.join(sorted(set(out), key=int))

    def route(self, donor, drive):
        rid = '%s@%d' % (drive.replace(':', '').replace('+', 'p'), donor)
        if rid not in self.routes:
            self.routes[rid] = route_cells(donor, drive, AUXES)
        return rid

    def add(self, **kw):
        if 'in_' in kw:                      # `in` is a keyword; the column is not
            kw['in'] = kw.pop('in_')
        self.n += 1
        kw.setdefault('sub', '')
        kw.setdefault('note', '')
        kw.setdefault('prompt', '')
        kw.setdefault('freq_hz', TONE_HZ)
        kw.setdefault('level_dbfs', TONE_DBFS)
        row = dict((c, '') for c in COLUMNS)
        row.update(kw)
        row['path'] = self.n
        row['patch'] = 'P%d' % self.patch
        row['route'] = self.route(int(kw['donor']), kw['drive'])
        self.paths.append(row)

    def new_patch(self):
        self.patch += 1
        return 'P%d' % self.patch

    # -- the blocks ---------------------------------------------------------
    def block_k1(self):
        """The mic paths and the talkback: a balanced XLR output into a
        balanced XLR input, which is the reference every other reading on that
        lane is judged against."""
        plan = []
        for i, (out, drive) in enumerate(XLR_OUTS):
            plan.append((out, drive, 'MIC %d' % (i + 1), i + 1))
        for mic in range(len(XLR_OUTS) + 1, 25):
            plan.append((PARK_OUT, PARK_DRIVE, 'MIC %d' % mic, mic))
        for out, drive, inp, strip in plan:
            self.new_patch()
            self.add(lead='K1', block='the microphone inputs', out=out, in_=inp,
                     drive=drive, lane=strip, donor=donor_for(strip),
                     expect='tone', level_ref='ref', polarity='ref',
                     rows=self.rows_for(out, inp),
                     prompt='Patch %s to %s' % (out, inp))
        self.new_patch()
        self.add(lead='K1', block='the microphone inputs', out=PARK_OUT,
                 in_='TALKBACK', drive=PARK_DRIVE, lane=LANE_TALKBACK,
                 donor=DONOR_DEFAULT, expect='tone', level_ref='info',
                 polarity='info', rows=self.rows_for(PARK_OUT, 'TALKBACK'),
                 prompt='Patch %s to TALKBACK' % PARK_OUT,
                 note='the talkback XLR is on the AK4619 codec, not the mic '
                      'preamps: a different gain law and about 23 dB more noise '
                      '(S70), so its level is reported and not judged until PW '
                      'rules a window')

    def block_k5(self):
        """The input noise rows: a 150 ohm terminator and no tone at all."""
        for strip in STRIPS:
            self.new_patch()
            self.add(lead='K5', block='the input noise rows', out='',
                     in_='MIC %d' % strip, drive='none', lane=strip,
                     donor=donor_for(strip), expect='noise', level_ref='ein',
                     polarity='-', level_dbfs='', freq_hz='',
                     rows=self.rows_for('MIC %d' % strip),
                     prompt='Fit the 150 ohm terminator in MIC %d' % strip,
                     note='EIN at the gain the 2026-09-16 survey used; the '
                          'window is limits.csv t4b_ein_max_dbu')

    def block_k4(self):
        """The line paths: the same combo jacks, entered through the TRS centre.

        HOW THE LINE PATH IS SELECTED IS NOT IN THIS REPO. Chan<n>InputSel001
        is declared `mcu` -- "MCU hardware control" -- so it is not a DSP write
        this runner can make, and nothing in defs, the DSP graph or the 595
        image says what else selects it. On a combo jack the TRS centre is
        normally switched mechanically by the plug, in which case there is
        nothing to set and this block just works. The list therefore sets NO
        selection cell, measures the path, and reports the level rather than
        judging it -- the tone-present verdict is the factory question either
        way. See the report's open items.
        """
        for strip in STRIPS:
            self.new_patch()
            self.add(lead='K4', block='the line inputs', out=PARK_OUT,
                     in_='MIC %d line' % strip, drive=PARK_DRIVE, lane=strip,
                     donor=donor_for(strip), expect='tone', level_ref='info',
                     polarity='normal', rows='',
                     prompt='Patch %s to the TRS centre of MIC %d'
                            % (PARK_OUT, strip),
                     note='no catalog row declares the combo TRS line path, and '
                          'nothing in defs says how it is selected: level '
                          'reported, tone presence judged')

    def block_k2(self):
        """The TRS output jacks, read through one XLR input."""
        for name, drive, hz, why in MONO_TRS_OUTS:
            self.new_patch()
            self.add(lead='K2', block='the TRS outputs', out=name, in_=PARK_IN,
                     drive=drive, lane=PARK_IN_STRIP, donor=DONOR_DEFAULT,
                     freq_hz=hz, expect='tone', level_ref='info',
                     polarity='normal', rows=self.rows_for(name, PARK_IN),
                     prompt='Patch %s to %s' % (name, PARK_IN), note=why)
        for jack, la, ra in STEREO_TRS_OUTS:
            self.new_patch()
            base = dict(lead='K2', block='the TRS outputs', out=jack,
                        in_=PARK_IN, lane=PARK_IN_STRIP, donor=DONOR_DEFAULT,
                        rows=self.rows_for('%s L' % jack, PARK_IN),
                        prompt='Patch %s to %s' % (jack, PARK_IN))
            self.add(sub='L', drive='aux:%d' % la, expect='tone',
                     level_ref='single', polarity='normal',
                     note='tip alone: one leg of aux %d into a balanced input' % la,
                     **base)
            self.add(sub='R', drive='aux:%d' % ra, expect='tone',
                     level_ref='single', polarity='inverted',
                     note='ring alone: the input reads tip minus ring, so a '
                          'healthy ring reads inverted against the tip',
                     **base)
            self.add(sub='null', drive='aux:%d+%d' % (la, ra), expect='null',
                     level_ref='null', polarity='-',
                     note='both in phase: what is left is the L/R match. A '
                          'crossed or absent channel cannot null',
                     **base)

    def block_k3(self):
        """The stereo mini-jacks: one balanced drive, both lanes at once.

        BOTH JACKS LAND ON THE SAME CODEC LANE. The AK4619 has one stereo aux
        input and it is ADC1 L/R -- MeasChan 51 and 55 -- while the Analog PCBA
        carries two identical TIP/RING/GND/MJ_SW connectors (J2 and J3) for the
        two panel jacks. So the station proves each jack's own copper, one at a
        time, and CANNOT tell which jack a signal arrived through: the prompt
        says to leave the other one empty, and a tone with both plugged would
        be ambiguous rather than wrong.
        """
        for n in (1, 2):
            lane_l, lane_r = LANE_MJ_L, LANE_MJ_R
            other = 2 if n == 1 else 1
            jack = 'MINI-JACK %d' % n
            self.new_patch()
            base = dict(lead='K3', block='the mini-jack inputs', out=PARK_OUT,
                        in_=jack, drive=PARK_DRIVE, donor=DONOR_DEFAULT,
                        rows=self.rows_for('%s L' % jack),
                        prompt='Patch %s to %s, with MINI-JACK %d empty'
                               % (PARK_OUT, jack, other))
            self.add(sub='L', lane=lane_l, expect='tone', level_ref='single',
                     polarity='info',
                     note='pin 2 reaches the tip, so the left lane carries the '
                          'drive as it stands', **base)
            self.add(sub='R', lane=lane_r, expect='tone', level_ref='single',
                     polarity='info',
                     note='pin 3 reaches the ring, so the right lane carries '
                          'the drive inverted. An inverted LEFT is a channel '
                          'swap, not two failures', **base)

    def block_unreachable(self):
        for name, why in sorted(UNREACHABLE.items()):
            p = self.ports.get(name, {})
            self.notrun.append(dict(port=name, row=p.get('catalog_row', ''),
                                    reason=why))

    def build(self):
        self.block_k1()
        self.block_k5()
        self.block_k4()
        self.block_k2()
        self.block_k3()
        self.block_unreachable()
        self.check()
        return self

    def check(self):
        """Every cell the routes name must be declared by the product."""
        for rid, cl in sorted(self.routes.items()):
            for spec in cl:
                nm = spec.split('=')[0]
                if nm not in self.cells:
                    self.missing.append('%s: %s' % (rid, nm))
        for spec in (cells_close_assigns(STRIPS, AUXES)
                     + cells_donor_transparent(DONOR_DEFAULT)
                     + cells_donor_transparent(DONOR_ALT)
                     + cells_bus_masters(AUXES)):
            nm = spec.split('=')[0]
            if nm not in self.cells:
                self.missing.append('standing: %s' % nm)
        if self.missing:
            raise SystemExit('cells named but not declared by the product:\n  '
                             + '\n  '.join(sorted(set(self.missing))))


# ---------------------------------------------------------------------------
# Writing it out
# ---------------------------------------------------------------------------
HEAD_PATHS = """\
# patch-paths.csv -- GENERATED by tools/accept/gen_patch_paths.py (S121). Do not edit.
# ONE row per measurement. Rows sharing a `patch` id are sub-tests of ONE physical
# connection and the operator is prompted once for the lot.
#   lead        which of the five kit leads this patch uses (see patch-plan.md)
#   out / in    D24 PANEL names. J numbers belong in records, never in a prompt
#   drive       which bus the oscillator is routed to: the `route` column's cells do it
#   lane        MeasChan: 1..24 a strip, 51/53/55 the codec return lanes
#   donor       the strip the oscillator replaces (never the lane under test)
#   expect      tone = a tone must be there; null = it must cancel; noise = no tone at all
#   level_ref   ref = this reading SETS the lane's balanced reference
#               single = about %.2f dB under that reference (one leg of a balanced pair)
#               null   = at or below %.0f dB relative to the same jack's single-ended reading
#               ein    = the input noise window, limits.csv t4b_ein_max_dbu
#               info   = measured and reported, not judged (no window ruled yet)
#   polarity    ref = sets the lane's reference phase; normal/inverted = against it;
#               info = reported only; - = not applicable
""" % (SINGLE_ENDED_DB, NULL_MAX_DB)

HEAD_ROUTES = """\
# patch-routes.csv -- GENERATED by tools/accept/gen_patch_paths.py (S121). Do not edit.
# The cells, BY NAME, that assert one route. Written whole every time, so a route is
# never half-set from the patch before. Values: f<x> is an IEEE-754 float word.
"""


def write_paths(out, b):
    path = os.path.join(out, 'patch-paths.csv')
    with open(path, 'w', newline='') as fh:
        fh.write(HEAD_PATHS)
        w = csv.DictWriter(fh, COLUMNS, extrasaction='ignore')
        w.writeheader()
        for r in b.paths:
            w.writerow(r)
    return path


def write_routes(out, b):
    path = os.path.join(out, 'patch-routes.csv')
    with open(path, 'w', newline='') as fh:
        fh.write(HEAD_ROUTES)
        w = csv.writer(fh)
        w.writerow(('route', 'cells'))
        w.writerow(('_standing_close', ';'.join(cells_close_assigns(STRIPS, AUXES))))
        for d in sorted({DONOR_DEFAULT, DONOR_ALT}):
            w.writerow(('_standing_donor_%d' % d,
                        ';'.join(cells_donor_transparent(d))))
        w.writerow(('_standing_masters', ';'.join(cells_bus_masters(AUXES))))
        for rid in sorted(b.routes):
            w.writerow((rid, ';'.join(b.routes[rid])))
    return path


def write_plan(out, b):
    path = os.path.join(out, 'patch-plan.md')
    by_lead, patches = {}, {}
    for r in b.paths:
        by_lead.setdefault(r['lead'], set()).add(r['patch'])
        patches.setdefault(r['patch'], []).append(r)
    L = ['<!-- GENERATED by tools/accept/gen_patch_paths.py (S121). Do not edit. -->',
         '# The D24 audio patch plan', '',
         '%d patches, %d measurements, %d lead changes.'
         % (b.patch, b.n, len(BLOCK_ORDER) - 1), '',
         '## The kit', '',
         '| lead | what it is | how it is wired | patches |',
         '|---|---|---|---|']
    for k in BLOCK_ORDER:
        d = LEADS[k]
        L.append('| %s | %s | %s | %d |'
                 % (k, d['name'], d['wiring'], len(by_lead.get(k, ()))))
    L += ['',
          'One of each. The order above is the order the station walks, so the '
          'operator changes lead type %d times in a whole pass and never goes '
          'back to a lead already put down.' % (len(BLOCK_ORDER) - 1), '',
          '## The blocks', '',
          '| # | lead | block | patches | measurements | the end that stays put |',
          '|---|---|---|---|---|---|']
    seen = []
    for r in b.paths:
        key = (r['lead'], r['block'])
        if key not in seen:
            seen.append(key)
    for i, (lead, block) in enumerate(seen, start=1):
        mine = [r for r in b.paths if r['lead'] == lead and r['block'] == block]
        pp = sorted({r['patch'] for r in mine})
        outs = {r['out'] for r in mine}
        ins = {r['in'] for r in mine}
        outs.discard('')
        if not outs:
            parked = 'nothing: the terminator moves on its own'
        elif len(outs) == 1 and len(ins) > 1:
            parked = 'the output end, on %s' % list(outs)[0]
        elif len(ins) == 1 and len(outs) > 1:
            parked = 'the input end, in %s' % list(ins)[0]
        elif len(outs) == 1 and len(ins) == 1:
            parked = 'both ends'
        else:
            nout = len(outs)
            park = sorted(((sum(1 for r in mine if r['out'] == o), o)
                           for o in outs), reverse=True)[0]
            parked = ('the input end walks all %d; the output end moves once '
                      'per output for the first %d and then stays on %s for '
                      'the remaining %d' % (len(pp), nout, park[1],
                                            len(pp) - nout))
        L.append('| %d | %s | %s | %d | %d | %s |'
                 % (i, lead, block, len(pp), len(mine), parked))
    L += ['', '## Coverage', '',
          'Every D24 analog socket, and what proves it.', '',
          '| socket | catalog row | proved by |', '|---|---|---|']
    for name, p in sorted(b.ports.items(), key=lambda kv: int(kv[1]['catalog_row'] or 0)):
        hits = [r['patch'] for r in b.paths
                if r['out'] == name or r['in'] == name
                or r['in'].startswith(name + ' ')
                or (r['out'] and name.startswith(r['out'] + ' '))
                or (r['in'] and name.startswith(r['in'] + ' '))]
        if hits:
            L.append('| %s | %s | %s |' % (name, p['catalog_row'],
                                           ', '.join(sorted(set(hits),
                                                            key=lambda s: int(s[1:])))))
    L += ['', '### Not run, and why', '',
          'These are not failures and not omissions. The socket exists; no cell '
          'this product declares can put a signal on it.', '',
          '| socket | catalog row | why |', '|---|---|---|']
    for n in b.notrun:
        L.append('| %s | %s | %s |' % (n['port'], n['row'], n['reason']))
    L.append('')
    with open(path, 'w') as fh:
        fh.write('\n'.join(L))
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--out', default=OUT_DEFAULT)
    ap.add_argument('--check', action='store_true',
                    help='build and validate, write nothing')
    a = ap.parse_args(argv)
    b = Builder(load_ports(), load_cells()).build()
    if a.check:
        print('OK: %d patches, %d paths, %d routes, %d sockets not run'
              % (b.patch, b.n, len(b.routes), len(b.notrun)))
        return 0
    os.makedirs(a.out, exist_ok=True)
    for p in (write_paths(a.out, b), write_routes(a.out, b), write_plan(a.out, b)):
        print('wrote %s' % os.path.relpath(p, ROOT))
    print('%d patches, %d measurements, %d sockets not run'
          % (b.patch, b.n, len(b.notrun)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
