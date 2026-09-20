"""s83_gate2.py — the S54 MIC 5 loop, and WHERE THE TONE ACTUALLY LANDS.

S82 left every AK5558 mic lane at exact digital zero on the fixed bitstream,
unmuted, gain 63, phantom off, VERIFIED 200/200 in five conditions — while a
codec lane in the same pass moved. The hub asked first whether S58's input
patch is reading the wrong lanes because the two bitstreams generate different
slot maps. THE DESK HALF OF THAT IS ANSWERED AND SAYS NO: the `A_I0/A_I1/A_I2`
rows of `shared/dsp4-logic/slot-map.csv` and `tdm-lines.csv` are byte-identical
between the commit that built the retired bitstream (`a4ee3d1f`) and HEAD, so
`MIC 5 -> sport 1, slot 7 -> _buf_C1_IN_16` holds on both and there is no lane
movement for the patch to be wrong about.

So this is the bench half, and it assumes nothing about which lane is which:
ONE tone is driven into the loop and EVERY lane is read, with the tone off and
then on. The tone names its own lane. If it names none, the lanes are dark and
the run says so with the readings rather than inferring a cause.

THE ROUTE IS PROVED DIGITALLY FIRST. The donor strip is part of the instrument
and is not transparent out of `dsp4_config.py` (S70-2/3): `Chan006CompOn001`
comes up 1 with a threshold near -22 dBFS and `Chan006AuxSend001` comes up 0.0,
either of which fakes an analog fault. `s70lib.Rig.route()` clears both and
`prove_route()` requires the AUX 1 bus to carry the tone before anything analog
is read — so "the tone never reached the DAC" and "the ADC lane is dark" are
separated before either is claimed.
"""
import json
import os
import subprocess
import sys
import time

_argv = list(sys.argv)
SYMDIR = os.environ.setdefault('SYMDIR', '/home/app/s83tn')
sys.path.insert(0, '/home/app/s70')
sys.path.insert(0, '/home/app/s69')
sys.path.insert(0, '/home/app/s54')
import s70lib as T                                                  # noqa: E402

OUT = os.environ.get('S83_OUT', '/home/app/s83/gate2.json')
LANESCAN = os.path.join(SYMDIR, 's83_lanescan.py')
MIC5_LANE = '_buf_C1_IN_16'          # defs/products/d24/inputs.csv: J25 -> sport 1 slot 7


def lanescan(tag, path):
    """The lane read, in its own process: one Scope per chip per process."""
    r = subprocess.run([sys.executable, LANESCAN, '--symdir', SYMDIR,
                        '--tag', tag, '--json', path],
                       capture_output=True, text=True)
    sys.stdout.write(r.stdout)
    sys.stderr.write(r.stderr)
    try:
        return json.load(open(path))
    except (IOError, ValueError):
        return None


def main():
    out = {}
    cap = T.osc_ceiling()
    print('oscillator ceiling %.2f dBFS (derived, S79)' % cap, flush=True)

    # ---- 1. the route, proved on the bus before anything analog is read
    r = T.Rig()
    bus = r.prove_route(level_db=-40.0)
    print('AUX 1 bus carries the tone: %.3f dBFS at oscillator -40.0' % bus,
          flush=True)
    out['aux1_bus_dbfs_at_-40'] = bus

    # ---- 2. every lane, tone OFF
    r.osc(on=False)
    time.sleep(0.5)
    r._close()                              # one Scope per CS: hand the link over
    off = lanescan('tone-off', '/home/app/s83/lanes-off.json')
    out['off'] = off

    # ---- 3. every lane, tone ON at the capped level
    r = T.Rig()
    r.osc(freq=1000.0, level_db=cap, on=True)
    time.sleep(0.5)
    r._close()
    on = lanescan('tone-on', '/home/app/s83/lanes-on.json')
    out['on'] = on
    out['osc_dbfs'] = cap

    # ---- 4. the verdict: which lane MOVED when the tone was turned on
    if off and on:
        byname = {l['sym']: l for l in off['lanes']}
        print('\n%-26s %-22s %-22s %s'
              % ('lane', 'tone OFF', 'tone ON', 'verdict'))
        found = []
        for l in on['lanes']:
            o = byname.get(l['sym'], {})
            a = '%d distinct, peak %.1f dBFS' % (o.get('distinct', 0),
                                                 o.get('peak_dbfs', -336.0))
            b = '%d distinct, peak %.1f dBFS' % (l.get('distinct', 0),
                                                 l.get('peak_dbfs', -336.0))
            rise = l.get('peak_dbfs', -336.0) - o.get('peak_dbfs', -336.0)
            v = ('TONE (+%.1f dB)' % rise if rise > 6.0 else
                 'moving, no rise' if l.get('distinct', 0) > 1 else 'dark')
            if rise > 6.0:
                found.append((l['sym'], rise))
            print('%-26s %-22s %-22s %s' % (l['sym'], a, b, v))
        out['tone_lanes'] = [{'sym': s, 'rise_db': round(d, 3)} for s, d in found]
        print()
        if not found:
            print('NO LANE CARRIES THE TONE. The AUX 1 bus does (above), so the '
                  'stimulus reaches the DAC and the loop is broken downstream of '
                  'it: either the cable is not in J25 or the AK5558s are not '
                  'converting. This run does not choose between those.')
        else:
            names = ', '.join('%s (+%.1f dB)' % (s, d) for s, d in found)
            print('THE TONE LANDS IN: %s' % names)
            print('The input patch says MIC 5 is %s.' % MIC5_LANE)
            print('AGREES' if any(s == MIC5_LANE for s, _ in found)
                  else 'DISAGREES — the patch and the part name different lanes')
    json.dump(out, open(OUT, 'w'), indent=1)
    print('\nwrote', OUT)


if __name__ == '__main__':
    main()
