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
    'Mute': (0, 0),
}
# FX is deliberately NOT in ROUTES. The six FX engines have their own
# bypass branch and turning them on measures a different question (what the
# FX engines cost), which gate 2 of the S19 dispatch prices separately. A
# driven row that quietly switched them on would not be comparable with the
# silent row it is subtracted from.

CELL = re.compile(r'^([A-Za-z]+?)(\d*)([A-Z][A-Za-z]*?)(\d+)$')


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
                    choices=('load', 'bypass', 'bypassfx', 'probe'))
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
    fams = families(cells, a.chip)

    if a.mode == 'probe':
        probe(sc, fams, ('Level', 'AuxSend', 'CompThr', 'GateThr',
                         'LimiterThr', 'MainOn', 'AuxOn'))
        return 0

    spec = {}
    if a.mode == 'load':
        spec.update(DYN_ON)
        spec.update(DYN_THR)
        if not a.no_routes:
            spec.update(ROUTES)
    else:
        spec.update(DYN_OFF)
        if a.mode == 'bypassfx':
            spec.update(FX_OFF)
    for cls in [c.strip() for c in a.off.split(',') if c.strip()]:
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
