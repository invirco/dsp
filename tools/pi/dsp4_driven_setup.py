#!/usr/bin/env python3
"""dsp4_driven_setup.py — put the graph in the DRIVEN regime, or take it out.

WHY THIS EXISTS (S19). Every capacity figure in this tree before 2026-09-10
was taken on a bench with no signal, and S18 §1 measured what that is worth:
chip 2's dynamics have a cheap branch below threshold, so the same image and
the same product read 92.7 % of budget silent and 112.3 % with its dynamics
engaged. A capacity number is only a product number if it says which branch
the graph was on, and the only way to say that is to PUT it on the expensive
one deliberately and then prove it.

Getting signal to the part is the CPLD's job (`loadlogic.sh driveall`: every
DSPA input lane carries the CM4's playback, and the DSP pays nothing for it).
This tool does the other half — the CONFIGURATION that decides whether that
signal reaches a dynamics node at all, and whether it is above its threshold
when it gets there:

  * ROUTES.  At boot a strip is routed to MAIN and nothing else
    (`_rtg_main_on` = 1, sub/grp/aux/fx all 0, every aux send 0.0), so 23 of
    the 25 inter-chip buses carry silence however loud the inputs are, and
    chip 2's twelve aux limiters, four group gates and four group
    compressors sit on their cheap branch. `--mode load` opens every bus
    assign and every send.
  * THRESHOLDS.  -60 dB on every compressor, gate and limiter, so a node is
    above threshold on any real signal rather than only on a peak.
  * ENGAGEMENT.  `On` = 1 on every one of them.
  * THE PLUGIN LOAD.  `--mode loadfx` is `load` plus the six FX engines:
    every strip's assign and send to every FX bus opened, and the engines
    switched on, all wet, at a named Type. See FX_ROUTES below for why that
    is a mode of its own and not a line in ROUTES.

`--mode bypass` is the control the driven figure needs: the same image with
every dynamics node switched OFF, so the driven-minus-silent delta on it is
the INSTRUMENT'S OWN COST rather than the graph's. If that delta is not
approximately zero, the stimulus is being paid for somewhere and the driven
figure has to be netted against it (S18 had to net 0.18 points off chip 2 for
`DSP4_PROFILE_SIGNAL`'s synthesis; this instrument is meant to need none).

UNITS. Nothing here converts: chip 1 and chip 2 both carry a zero wire-unit
conversion table for every address written below, so the word on the wire is
the word the kernel reads. Thresholds are IEEE-754 float32 dB, sends and
levels are LINEAR float32 (`_fdr_level` initialises to 1.0, not to the CSV's
`level_db=-inf`), `On` words are integers. `--probe` prints what a
representative address held BEFORE anything was written, which is the check
that the unit assumption is the part's and not this file's.

The landed map is the contract's, staged beside the image; a cell that is not
in it for this product is not written and is counted as absent, never
guessed at.

Usage:
    dsp4_driven_setup.py --chip 1 --mode load   --landed landed-d24.json
    dsp4_driven_setup.py --chip 2 --mode bypass --landed landed-d24.json
    dsp4_driven_setup.py --chip 1 --mode probe  --landed landed-d24.json
    dsp4_driven_setup.py --chip 2 --mode loadfx --fx-type 3 \
                         --landed landed-d32.json
"""
import argparse
import json
import re
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

THR_DB = -60.0


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


# family suffix (with its trailing instance digits stripped) -> (value, ramped)
#
# RAMPED OR NOT IS THE HOST'S JOB (dsp4_tubedly_probe.wrv): the profile
# lives in the request word, and a ramped parameter written with ramp_id 0
# takes the instant path and is then clobbered by the node's own block-rate
# code from a target that was never set. Sends and levels ramp; on/off flags
# and thresholds do not.
DYN_ON = {
    'CompOn': (1, 0),
    'GateOn': (1, 0),
    'LimiterOn': (1, 0),
}
DYN_THR = {
    'CompThr': (f32(THR_DB), 0),
    'GateThr': (f32(THR_DB), 0),
    'LimiterThr': (f32(THR_DB), 0),
}
DYN_OFF = {
    'CompOn': (0, 0),
    'GateOn': (0, 0),
    'LimiterOn': (0, 0),
}
# `bypassfx` goes one step further and switches the six FX engines off with
# the dynamics. It exists to ATTRIBUTE the residue: with the dynamics
# bypassed, chip 2 still costs 0.7 points more driven than silent, and that
# is either the FX engines' own input paths or the meters' peak-update
# branch. Turning the engines off separates the two, which is the
# difference between a number the record can name and a number it cannot.
# 'On' also catches the four AUX_INPUT `On` cells (Pi/Usb/Bt/CodecAux),
# which are 0 at boot anyway.
FX_OFF = {'On': (0, 0)}
ROUTES = {
    'MainOn': (1, 0),
    'CtrOn': (1, 0),
    'GrpOn': (1, 0),
    'AuxOn': (1, 0),
    'AuxSend': (f32(1.0), 1),
    # THE MATRIX SENDS (added S23). `load` means "every assign and send
    # open", and the matrix is an assign and a send -- it was absent here
    # only because the family did not exist when this table was written.
    #
    # IT CANNOT MOVE ANY ROW ON RECORD. Every driven figure taken before
    # today was taken against a landed map with no `Matrix*` cell in it, so
    # this table's lookup found nothing to write; and the rows this session
    # compares against S21's are deliberately taken against the LANDED map
    # too, for exactly that comparability. A row taken with
    # DSP_LANDED_DIR pointing at the proposal now opens the matrix as well,
    # which is what makes the matrix's ACCUMULATE cost measurable at all:
    # a bus row whose 32 coefficients are every one zero is skipped by the
    # fabric for one compare per block, so a matrix nobody has sent to
    # costs almost nothing and a driven row cannot see it.
    #
    # `AuxOn`/`AuxSend` reach the FX returns' aux crosspoints too, without
    # a line being added: `Fx001AuxSend001` and `Chan001AuxSend001` are the
    # same family suffix, so the same lookup opens both.
    'MatrixOn': (1, 0),
    'MatrixSend': (f32(1.0), 1),
    'Mute': (0, 0),
}
# FX is deliberately NOT in ROUTES. The six FX engines have their own
# bypass branch and turning them on measures a different question (what the
# FX engines cost), which `--mode loadfx` answers separately. A driven row
# that quietly switched them on would not be comparable with the silent row
# it is subtracted from.

# ---------------------------------------------------------------------------
# `--mode loadfx`: THE PLUGIN LOAD (S21)
# ---------------------------------------------------------------------------
#
# WHY IT IS A SEPARATE MODE AND NOT A LINE IN ROUTES. PW's requirement of
# 2026-08-28 is that 32 strips is the MINIMUM and the fit must carry headroom
# for plugins. The FX engines ARE that plugin load, and until S21 they had
# never been driven in a capacity measurement: `--mode load` leaves the six
# `Chan<nn>FxSend` at 0.0 and every `Chan<nn>FxOn` at 0, so BUS_FX_01..06
# carry silence however loud the inputs are, and the engines run their
# algorithm over zeros. The Freeverb body costs the same over zeros as over
# signal -- there is no cheap branch in it -- so the CYCLE difference between
# `load` and `loadfx` at the same Type is small by construction; what
# `loadfx` changes is that the engines are at the Type the product ships
# rather than at the `.var` default, and that their inputs are LIVE, which is
# the part the record could not previously say.
#
# WHAT IT WRITES, on top of everything `load` writes:
#
#   chip 1  Chan<nn>FxOn<k>   = 1     every strip's assign to every FX bus
#           Chan<nn>FxSend<k> = 1.0   linear, RAMPED (a send is a ramped cell)
#   chip 2  Fx<n>On           = 1     the engine (its `.var` is 1 at boot
#                                     anyway; written so the row does not
#                                     depend on that)
#           Fx<n>Type         = --fx-type   0=Echo 1=PingPong 2=Doubling
#                                           3=Reverb 4=Chorus 5=Flanger
#                                           6=Phaser
#           Fx<n>Mix          = 1.0   ALL WET. The mix epilogue costs the
#                                     same at any value, but a wet engine is
#                                     the one whose output the meters can see,
#                                     which is how the regime is proved.
#
# TYPES 1, 4, 5 AND 6 ARE NOT IMPLEMENTED FOR THIS CLASS and the node says so
# on the part: the dispatch parks the Type in `_fx_bypassed_<nid>` and passes
# the input through dry. A row taken at one of those Types is a row for the
# BYPASS branch, and `dsp4_c2regime.py --require-fx` reports it as such
# rather than letting it look like an algorithm that happens to be cheap.
FX_ROUTES = {
    'FxOn': (1, 0),
    'FxSend': (f32(1.0), 1),
}
# THE ENGINE'S OWN PARAMETERS, at a real operating point.
#
# They are written because at boot they are NOT at one: every `_fx_*` word
# the reverb reads except the Type and the mix is a `.var` with no
# initialiser, i.e. ZERO, and the host had never written one. A reverb with
# `damp = 0` and `feedback = 0` still runs every instruction of the Freeverb
# body -- there is no data-dependent branch anywhere in it, which is why the
# CYCLE figure does not move -- but it is a degenerate setting, and "six
# reverbs" should mean six reverbs. These are the values dsp.csv declares for
# the node (room_size 0.7, damping 0.5, decay 2.0, predelay 20 ms, delay
# 300 ms, feedback 50 %, mod 1.0 Hz / 50 %), so the row is the graph's own
# default patch rather than a setting invented here.
#
# `Balance` is NOT here although dsp.csv declares it: the cell master gives
# it mode `mcu`, not `rw`, so it is not this link's to write and the landed
# map filters it out. It is a parameter of the algorithm, so the row is
# stated as "the graph's default patch with Balance left where the MCU has
# it" rather than pretending the write happened.
FX_PARAMS = {
    'Damp': (f32(0.5), 0),
    'Decay': (f32(2.0), 0),
    'PreDelay': (f32(20.0), 0),
    'DelayTime': (f32(300.0), 0),
    'Feedback': (f32(50.0), 0),
    'StereoWidth': (f32(50.0), 0),
    'ModRate': (f32(1.0), 0),
    'ModLevel': (f32(50.0), 0),
    'EqLo': (f32(0.0), 0),
    'EqMid': (f32(0.0), 0),
    'EqPresence': (f32(0.0), 0),
}
# THE SENDS, CLOSED. The rung that separates "chip 2's FX return chain is
# carrying signal" from "the engines are running an algorithm": with these
# written, BUS_FX_01..06 go silent and the six engines run over zeros, which
# is exactly the regime every `--mode load` row in the record was taken in.
FX_SENDS_OFF = {
    'FxOn': (0, 0),
    'FxSend': (f32(0.0), 1),
}

CELL = re.compile(r'^([A-Za-z]+?)(\d*)([A-Z][A-Za-z]*?)(\d+)$')

# A FAMILY SUFFIX IS NOT ALWAYS ONE NODE CLASS, and for `loadfx` it matters.
# `On` is TALKBACK and NOISE_GEN on chip 1 and AUX_INPUT *and* FX_ENGINE on
# chip 2, so an unfiltered `On = 1` would switch the talkback and the noise
# generator on, and open eight snake inputs and the Pi/USB/BT feeds, none of
# which is the plugin load being priced. Any family named here is written
# only where the landed map says the cell belongs to that node class; a
# family not named here is written across the family as before.
FAM_CLASS = {
    'On': 'FX_ENGINE',
    'Type': 'FX_ENGINE',
    'Mix': 'FX_ENGINE',
}

# ---------------------------------------------------------------------------
# `--mode use`: THE USE-PROPORTIONAL COST (S24)
# ---------------------------------------------------------------------------
#
# S23 priced every new node RUNNING and said so in as many words: its rows do
# NOT include the two costs proportional to USE. An aux sum whose six
# coefficients are all zero takes the block-level bypass, and a matrix bus row
# whose thirty-two are all zero is skipped by the fabric for one compare per
# block. `--mode load` writes both families wide open, which gives the WORST
# use and no way to price one crosspoint; this mode writes them to a NAMED
# COUNT so a ladder of rungs on one boot prices the two slopes separately:
#
#   * how much a BUS costs when it stops being empty (bypass/skip lost), and
#   * how much each ADDITIONAL live source on that bus costs (one MAC).
#
# The count is the SOURCE instance, and every BUS is written at every rung --
# so `--use-fxaux 1` means "one FX return into each of the twelve aux buses",
# not "one crosspoint in the whole graph". That is what makes the difference
# between two rungs divide by a bus count.
#
# EVERY RUNG WRITES THE WHOLE FAMILY, the sources above the count explicitly
# OFF. A rung is therefore a complete state and not an increment on the rung
# before it, so the ladder can be run in any order and a rung that fails
# cannot silently contaminate the next one.
#
# The families are matched on the cell name's PREFIX as well as its suffix:
# `AuxOn`/`AuxSend` is the same family suffix on `Chan<nn>AuxSend<m>` (a strip
# into an aux, chip 1) and on `Fx<n>AuxSend<m>` (an FX return into an aux,
# chip 2), and only the second is the S23 aux-sum crosspoint being priced
# here. The first is opened by `--mode load` and stays where the load put it.
USE_FAMS = {
    'fxaux': ('Fx',   'AuxOn',    'AuxSend'),
    'mtx':   ('Chan', 'MatrixOn', 'MatrixSend'),
}


def apply_use(sc, fams, counts, buses=None, verify=True):
    """Write the use-proportional crosspoint families to a named count.

    counts: {'fxaux': N, 'mtx': M} -- sources 1..N opened on each bus.
    buses:  {'fxaux': B, 'mtx': C} -- and only on buses 1..B; None or 0
            means every bus.

    THE BUS AXIS EXISTS BECAUSE THE FIRST LADDER SAID IT WAS THE ONE THAT
    MATTERS (S24). Opening one FX return into all twelve aux buses cost
    chip 2 9.77 points; opening all six into all twelve cost 0.11 more.
    Almost the whole price is a BUS losing its block-level bypass, not a
    crosspoint doing a MAC -- so 'how many sources' is the cheap axis and
    'how many buses' is the expensive one, and a ladder that cannot vary
    the second cannot say how many aux buses a product can afford.

    Opened cells get assign 1 and send 1.0 (linear, ramped); everything
    else is closed (assign 0, send 0.0). Returns (written, failed, live)."""
    buses = buses or {}
    done = failed = live = 0
    for key, n in sorted(counts.items()):
        nb = buses.get(key) or 0
        prefix, on_fam, send_fam = USE_FAMS[key]
        for fam, (on_val, off_val, ramp) in (
                (on_fam,   (1, 0, 0)),
                (send_fam, (f32(1.0), f32(0.0), 1))):
            cells = fams.get(fam, [])
            sel = []
            for cell, addr in cells:
                m = CELL.match(cell)
                if not m or m.group(1) != prefix:
                    continue
                # group 2 is the SOURCE instance (which FX return, which
                # strip); group 4 is the BUS (which aux, which matrix).
                sel.append((int(m.group(2) or 0), int(m.group(4) or 0),
                            cell, addr))
            if not sel:
                print('  %-12s no %s* cell for this product' % (fam, prefix))
                continue
            ok = bad = opened = 0
            for src, bus, cell, addr in sorted(sel):
                live_here = n and src <= n and (not nb or bus <= nb)
                val = on_val if live_here else off_val
                try:
                    sc.d.link.write(addr, val, ramp)
                    time.sleep(S.SETTLE)
                    if verify:
                        got = None
                        for _ in range(12 if ramp else 4):
                            try:
                                got = sc.rd(addr)
                            except IOError:
                                got = None
                            if got == val:
                                break
                            time.sleep(0.03)
                        if got != val:
                            bad += 1
                            continue
                    ok += 1
                    if val == on_val:
                        opened += 1
                except (IOError, OSError):
                    bad += 1
            done += ok
            failed += bad
            if fam == on_fam:
                live += opened
            print('  %-12s %3d/%-3d written, %d open '
                  '(%s sources 1..%d on buses 1..%s)'
                  % (fam, ok, len(sel), opened, prefix, n,
                     nb if nb else 'all'))
    return done, failed, live


def families(cells, chip):
    """{family_suffix: [(cellname, addr), ...]} for one chip, rw only."""
    out = {}
    for name, v in cells.items():
        if v[0] != chip or v[5] != 'rw':
            continue
        m = CELL.match(name)
        if not m:
            continue
        fam = m.group(3)
        out.setdefault(fam, []).append((name, v[2]))
    for k in out:
        out[k].sort()
    return out


def families_classed(cells, chip):
    """{family_suffix: [(cellname, addr), ...]} with FAM_CLASS applied."""
    out = {}
    for name, v in cells.items():
        if v[0] != chip or v[5] != 'rw':
            continue
        m = CELL.match(name)
        if not m:
            continue
        fam = m.group(3)
        if fam in FAM_CLASS and v[4] != FAM_CLASS[fam]:
            continue
        out.setdefault(fam, []).append((name, v[2]))
    for k in out:
        out[k].sort()
    return out


def probe(sc, fams, names):
    for fam in names:
        for cell, addr in fams.get(fam, [])[:1]:
            try:
                v = sc.rd(addr)
                print('  probe %-24s 0x%04X = 0x%08X  (%g as float32)'
                      % (cell, addr, v,
                         struct.unpack('<f', struct.pack('<I', v))[0]))
            except IOError:
                print('  probe %-24s 0x%04X = UNREADABLE' % (cell, addr))


def apply(sc, fams, spec, verify=True):
    done = failed = absent = 0
    for fam, (val, ramp) in sorted(spec.items()):
        cells = fams.get(fam, [])
        if not cells:
            absent += 1
            print('  %-12s absent for this product' % fam)
            continue
        ok = bad = 0
        for cell, addr in cells:
            try:
                sc.d.link.write(addr, val, ramp)
                time.sleep(S.SETTLE)
                if verify:
                    got = None
                    for _ in range(12 if ramp else 4):
                        try:
                            got = sc.rd(addr)
                        except IOError:
                            got = None
                        if got == val:
                            break
                        time.sleep(0.03)
                    if got != val:
                        bad += 1
                        continue
                ok += 1
            except (IOError, OSError):
                bad += 1
        done += ok
        failed += bad
        print('  %-12s %3d/%-3d written 0x%08X%s'
              % (fam, ok, len(cells), val, '  RAMPED' if ramp else ''))
    return done, failed, absent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chip', type=int, default=1, choices=(1, 2))
    ap.add_argument('--mode', default='load',
                    choices=('load', 'loadfx', 'fxtype', 'fxoff',
                             'fxsendon', 'fxsendoff',
                             'bypass', 'bypassfx', 'probe', 'use'))
    ap.add_argument('--fx-type', type=int, default=3,
                    help='loadfx: the algorithm every FX engine runs. '
                         '0=Echo 1=PingPong 2=Doubling 3=Reverb 4=Chorus '
                         '5=Flanger 6=Phaser. 1/4/5/6 are not implemented '
                         'for the reverb class the shipped graph declares '
                         'and park in the explicit bypass.')
    ap.add_argument('--fx-mix', type=float, default=1.0,
                    help='loadfx: dry/wet, linear. 1.0 = all wet, which is '
                         'what makes the engine visible to the FX return '
                         'meters and therefore provable.')
    ap.add_argument('--landed', default=None,
                    help='landed-<product>.json staged beside the image')
    ap.add_argument('--no-routes', action='store_true',
                    help='engage the dynamics but leave the bus assigns alone')
    ap.add_argument('--off', default='',
                    help='comma-separated dynamics classes to switch OFF '
                         'after the mode is applied: Comp, Gate, Limiter. '
                         'This is the per-CLASS driven attribution and it '
                         'needs no rebuild and no reboot -- take a driven '
                         'row with everything on, then one per class with '
                         'that class bypassed, and the differences are what '
                         'each class costs ON ITS EXPENSIVE BRANCH, on the '
                         'shipping image rather than on a DSP4_NODE_LIMIT '
                         'instrument built for the purpose.')
    ap.add_argument('--use-fxaux', type=int, default=0,
                    help='use: FX returns opened into EVERY aux bus (0..6). '
                         'The S23 aux sum takes its block-level bypass at 0 '
                         'and pays the full seven-source fold above it.')
    ap.add_argument('--use-mtx', type=int, default=0,
                    help='use: strips opened into EVERY matrix bus (0..32). '
                         'A matrix bus row with no live send is skipped by '
                         'the fabric for one compare per block.')
    ap.add_argument('--use-fxaux-buses', type=int, default=0,
                    help='use: restrict the FX-return aux sends to aux '
                         'buses 1..N (0 = every bus). THE EXPENSIVE AXIS: '
                         'a bus that has any live send loses its '
                         'block-level bypass and pays the full fold.')
    ap.add_argument('--use-mtx-buses', type=int, default=0,
                    help='use: restrict the channel matrix sends to matrix '
                         'buses 1..N (0 = every bus).')
    ap.add_argument('--no-verify', action='store_true')
    a = ap.parse_args()

    path = a.landed
    if path is None:
        for cand in ('./landed-d24.json', './landed-d32.json',
                     '/home/app/dspboot/landed-d24.json'):
            try:
                open(cand).close()
                path = cand
                break
            except OSError:
                continue
    if path is None:
        print('no landed map: pass --landed')
        return 2
    lm = json.load(open(path))
    cells = lm['cells']
    print('landed map %s  product %s  pin %s  %d cells'
          % (path, lm.get('product'), lm.get('pin'), len(cells)))

    sc = S.Scope(a.chip)
    sc.check_chip()
    # `loadfx` is the only mode that writes a family whose suffix spans more
    # than one node class, so it is the only one that gets the filter -- every
    # other mode keeps the behaviour its numbers were taken with.
    fams = (families_classed(cells, a.chip)
            if a.mode in ('loadfx', 'fxtype', 'fxoff')
            else families(cells, a.chip))
    # FX_PARAMS names families that exist only on FX_ENGINE nodes anyway
    # (Damp, Decay, PreDelay, ...), so the filter is not needed for them --
    # but Balance and Delay-like suffixes are not unique across the master,
    # so the classed view is used for every fx mode.

    if a.mode == 'probe':
        probe(sc, fams, ('Level', 'AuxSend', 'CompThr', 'GateThr',
                         'LimiterThr', 'MainOn', 'AuxOn', 'FxOn', 'FxSend',
                         'Type', 'Mix'))
        return 0

    if a.mode == 'use':
        # The classed view is NOT used: `AuxOn`/`MatrixOn` are unambiguous
        # families and the prefix filter inside apply_use is what separates
        # the strip crosspoints from the FX-return ones.
        counts = {'fxaux': a.use_fxaux, 'mtx': a.use_mtx}
        buses = {'fxaux': a.use_fxaux_buses, 'mtx': a.use_mtx_buses}
        print('chip %d  mode use  fxaux=%d/%s bus  mtx=%d/%s bus'
              % (a.chip, a.use_fxaux, a.use_fxaux_buses or 'all',
                 a.use_mtx, a.use_mtx_buses or 'all'))
        t0 = time.time()
        done, failed, liveon = apply_use(sc, fams, counts, buses,
                                         verify=not a.no_verify)
        print('chip %d use: %d written, %d FAILED, %d assigns OPEN, %.0f s'
              % (a.chip, done, failed, liveon, time.time() - t0))
        return 1 if failed else 0

    spec = {}
    if a.mode == 'fxtype':
        # THE LADDER STEP. Only the engine cells, so a row taken after it
        # differs from the row before it in the ALGORITHM and in nothing
        # else -- same boot, same clock, same routes, same dynamics.
        spec = {'On': (1, 0), 'Type': (a.fx_type, 0),
                'Mix': (f32(a.fx_mix), 1)}
        spec.update(FX_PARAMS)
    elif a.mode == 'fxoff':
        # `Fx<n>On = 0`, AND SINCE S23 THIS IS A REAL RUNG.
        #
        # It used to be the WITNESS FOR S21-4 and the note here said so:
        # `_fx_on_<nid>` was written by the SPI dispatch table and read by
        # NOTHING, the FX_ENGINE body had no on/off branch at all, so this
        # rung ran the same algorithm as the rung before it and the two rows
        # read the same. S23 gate 2 gave the cell its reader -- the engine's
        # per-sample body tests it and the block wrapper parks the whole
        # node on it -- so this rung now measures what a switched-off engine
        # costs, and the ladder's OTHER baseline (`--fx-type 4`, an
        # unimplemented Type parked in the explicit bypass) is what it should
        # be read against: bypass still runs the node, parked does not.
        spec = {'On': (0, 0)}
    elif a.mode == 'fxsendon':
        spec = dict(FX_ROUTES)
    elif a.mode == 'fxsendoff':
        spec = dict(FX_SENDS_OFF)
    elif a.mode in ('load', 'loadfx'):
        spec.update(DYN_ON)
        spec.update(DYN_THR)
        if not a.no_routes:
            spec.update(ROUTES)
        if a.mode == 'loadfx':
            spec.update(FX_ROUTES)
            spec.update(FX_PARAMS)
            # The engine cells are chip 2's; the send/assign cells are chip
            # 1's. Both are written from the same mode so one command puts
            # ONE chip in the regime and the caller runs it per chip, which
            # is what capacity_run.sh already does.
            spec['On'] = (1, 0)
            spec['Type'] = (a.fx_type, 0)
            spec['Mix'] = (f32(a.fx_mix), 1)
    else:
        spec.update(DYN_OFF)
        if a.mode == 'bypassfx':
            spec.update(FX_OFF)
    for cls in [c.strip() for c in a.off.split(',') if c.strip()]:
        if a.mode in ('fxtype', 'fxoff', 'fxsendon', 'fxsendoff'):
            print('--off has no meaning in mode %s' % a.mode)
            return 2
        key = cls + 'On'
        if key not in DYN_ON and key not in DYN_OFF:
            print('unknown class for --off: %s' % cls)
            return 2
        spec[key] = (0, 0)

    print('chip %d  mode %s' % (a.chip, a.mode))
    t0 = time.time()
    done, failed, absent = apply(sc, fams, spec, verify=not a.no_verify)
    print('chip %d %s: %d written, %d FAILED, %d families absent, %.0f s'
          % (a.chip, a.mode, done, failed, absent, time.time() - t0))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
