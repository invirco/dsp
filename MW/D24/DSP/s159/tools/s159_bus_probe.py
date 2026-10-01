#!/usr/bin/env python3
"""s159_bus_probe.py -- can a chip-1 aux BUS buffer stand in for a mic lane's
missing `_buf_C1_XIN_` as the 150 ohm pass's noise instrument? (S159)

Two checks, rails down, nothing analog driven:

  1. UNITY. TEST_OSC on donor strip 24 at -30 dBFS pk, sent post-fader at 1.0
     to aux bus N. The capture of `_buf_C1_BUS_AUX_0N` must carry the tone at
     the oscillator's level (FFT fundamental, dBFS RMS = pk - 3.01), so a bus
     capture reads the strip at 0 dB.
  2. SAME NOISE. Oscillator off, MIC strip S sent to the same bus. The
     capture's DC-24k mean square must equal the node's RmsResult on MeasChan
     S (same signal, two instruments), and its 20-20k band figure is printed
     beside it -- the figure the EIN is graded on.

Everything it opened is closed again (the station's own _standing_close).
Run on the unit from /home/app/selftest:  python3 s159_bus_probe.py [--strip 1]
"""
import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, '/home/app/selftest')
sys.path.insert(0, HERE)
import d24_patch as PT          # noqa: E402
import dsp4_s49_osc as OSC      # noqa: E402
import dsp4_fft as FFT          # noqa: E402


def detrend(x):
    n = len(x)
    tm = (n - 1) / 2.0
    xm = sum(x) / n
    sxx = sum((i - tm) ** 2 for i in range(n))
    b = sum((i - tm) * (v - xm) for i, v in enumerate(x)) / sxx
    return [v - xm - b * (i - tm) for i, v in enumerate(x)]


def grab(sc, node, n=1024):
    cap = OSC.capture(sc, node, n)
    if 'error' in cap:
        raise SystemExit(cap['error'])
    x = OSC._q28(cap['samples'])
    y = detrend(x)
    u, _ = FFT.band_power(y, 48000, 20.0, 20000.0)
    a, _ = FFT.band_power(y, 48000, 20.0, 20000.0, aweight=True)
    return dict(total=OSC._rms_dbfs(x), band=u, a=a,
                fund=(cap.get('fft') or {}).get('fund_dbfs'),
                quarters=cap['quarter_rms_dbfs'], how=cap['how'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strip', type=int, default=1)
    ap.add_argument('--bus', type=int, default=8)
    ap.add_argument('--caps', type=int, default=6)
    ap.add_argument('--json', default='/home/app/selftest/s159-bus-probe.json')
    a = ap.parse_args()
    plist = PT.PatchList(PT.find_list_dir())
    u = PT.Unit()
    sc = u.chip(1)
    node = '_buf_C1_BUS_AUX_%02d' % a.bus
    out = dict(strip=a.strip, bus=a.bus, node=node)
    u.write(plist.routes['_standing_close'], verify=False)
    u.write(plist.routes['_standing_strips'] + plist.routes['_standing_masters'])
    try:
        # 1. unity
        u.write(['Chan024AuxOn%03d=1' % a.bus, 'Chan024AuxSend%03d=f1.0' % a.bus,
                 'Chan024AuxPick%03d=3' % a.bus])
        u.osc(chan=24, freq=1000.0, level_dbfs=-30.0, on=True)
        PT.nap(0.5)
        tone = [grab(sc, node) for _ in range(3)]
        out['tone'] = tone
        print('tone -30 dBFS pk (-33.01 RMS) on strip 24 -> aux %d: fund %s'
              % (a.bus, ['%.2f' % t['fund'] for t in tone if t['fund'] is not None]))
        u.osc(on=False)
        u.write(['Chan024AuxOn%03d=0' % a.bus])
        # 2. same noise, two instruments
        s = a.strip
        u.write(['Chan%03dAuxOn%03d=1' % (s, a.bus),
                 'Chan%03dAuxSend%03d=f1.0' % (s, a.bus),
                 'Chan%03dAuxPick%03d=3' % (s, a.bus)])
        u.meas_chan(s)
        PT.nap(0.5)
        caps = [grab(sc, node) for _ in range(a.caps)]
        node_rms = u.measure(None, 0.0, windows=4, settle=2).get('rms')
        def ms_avg(v):
            return 10 * math.log10(sum(10 ** (x / 10) for x in v) / len(v))
        out['noise'] = dict(caps=caps, node_rms=node_rms,
                            cap_total=ms_avg([c['total'] for c in caps]),
                            cap_band=ms_avg([c['band'] for c in caps]),
                            cap_a=ms_avg([c['a'] for c in caps]))
        n = out['noise']
        print('strip %d noise: node RmsResult %.2f dBFS | capture DC-24k %.2f, '
              '20-20k %.2f, A %.2f (%d captures)'
              % (s, node_rms, n['cap_total'], n['cap_band'], n['cap_a'],
                 len(caps)))
    finally:
        u.osc(on=False)
        u.write(plist.routes['_standing_close'], verify=False)
        with open(a.json, 'w') as fh:
            json.dump(out, fh, indent=1, default=str)
        print('wrote %s; sends closed, oscillator off' % a.json)


if __name__ == '__main__':
    main()
