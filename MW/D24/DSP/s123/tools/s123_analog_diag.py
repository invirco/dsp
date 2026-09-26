#!/usr/bin/env python3
"""s123_analog_diag.py -- which half of the patch loop is dead?

S123 addendum 2: two patches in a row carried no tone at all (AUX 5 -> MIC 5,
h = -125 dB with the lane at its own floor; AUX 6 -> MIC 6, nothing). Rails
up, chain at zero gain verified. The loop has two analog halves and the
station cannot tell them apart from a single reading, so this splits them,
and NEITHER test needs a hand at the bench:

  THE INPUT HALF -- preamp -> ADC -> TDM -> strip.
      Measured by SWEEPING THE PREAMP GAIN and watching each lane's own
      noise. An analog input chain that is alive cannot help but get noisier
      as its preamp gain goes up: the preamp's own noise is amplified with
      everything else. A lane whose reading does not move between gain code 0
      and gain code 63 is not listening to a preamp at all -- the rails, the
      mute bit, the chain or the lane map is wrong -- and no lead in any
      socket would ever have read anything.

  THE OUTPUT HALF -- bus -> output node -> TDM slot -> DAC -> XLR.
      Measured by DRIVING the bus with the station's own oscillator and
      reading the word the DSP actually puts in that output's transmit slot
      (`_tx_out_slot_C2_AUX_OUT_nn`). That proves everything up to the DAC's
      pin. What it cannot prove is the analog stage after it -- which is
      exactly the part S109 left unproved on this unit.

    s123_analog_diag.py [--lanes 5,6,11,17,24] [--outs 5,6,1] [--keep-rails]

It raises the rails, and puts them down again the way the station does:
AN_EN low first, then SAFE.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, '/home/app/selftest')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', '..', '..', '..', 'tools', 'pi'))
import d24_patch as P                                   # noqa: E402


def chain_image(gain):
    """(gain & 63) << 2 | phantom << 1 | mute. Phantom off, NOT muted."""
    return [((gain & 63) << 2)] * 24 + [0x00]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--lanes', default='5,6,11,17,24')
    ap.add_argument('--outs', default='5,6,1')
    ap.add_argument('--list-dir', default='/home/app/selftest/quick')
    ap.add_argument('--symdir', default=P.FACTORY_TEST_PAIR_DIR)
    ap.add_argument('--gains', default='0,16,32,48,63')
    ap.add_argument('--keep-rails', action='store_true')
    a = ap.parse_args(argv)
    lanes = [int(x) for x in a.lanes.split(',') if x.strip()]
    outs = [int(x) for x in a.outs.split(',') if x.strip()]
    gains = [int(x) for x in a.gains.split(',') if x.strip()]

    plist = P.PatchList(a.list_dir)
    u = P.Unit(symdir=a.symdir)
    an = P.Analog(enabled=True, log=lambda s: print('   .. %s' % s))

    print('=== the unit as found')
    print('   AN_EN: %s' % an.sh('pinctrl get %d' % an.an_en))
    print('   CS_M : %s' % an.sh('pinctrl get %d' % an.cs_m))
    print('   chain marker: %s' % (an.sh('cat %s 2>/dev/null' % an.marker())
                                   or '(none -- unknown)'))
    try:
        an.up()
        u.osc(on=False)

        # ---------------------------------------------------------------
        print('\n=== THE INPUT HALF: does each lane\'s own noise follow the '
              'preamp gain?')
        print('   (nothing plugged in; the preamps see an open input, which is '
              'the noisiest thing they can see)')
        rows = {}
        for g in gains:
            an.image = None                        # force the write every time
            ok = an.chain(chain_image(g), 'at gain code %d' % g)
            time.sleep(0.4)
            for lane in lanes:
                u.meas_chan(lane)
                m = u.measure(None, 0.0)
                rows.setdefault(lane, {})[g] = (m.get('rms'), ok)
        hdr = '   lane |' + ''.join(' gain %-3d |' % g for g in gains) + '  span'
        print(hdr)
        print('   ' + '-' * (len(hdr) - 3))
        verdict_in = {}
        for lane in lanes:
            vals = [rows[lane][g][0] for g in gains]
            good = [v for v in vals if v is not None]
            span = (max(good) - min(good)) if len(good) > 1 else None
            verdict_in[lane] = span
            print('   %4d |' % lane
                  + ''.join(' %8s |' % ('%.1f' % v if v is not None else '-')
                            for v in vals)
                  + ('  %5.1f dB' % span if span is not None else '   -'))
        print('\n   a lane whose reading moves with the gain is LISTENING to a '
              'live preamp;')
        print('   a lane that does not move is not connected to one.')

        # ---------------------------------------------------------------
        print('\n=== THE OUTPUT HALF: does the oscillator reach each output\'s '
              'transmit slot?')
        an.image = None
        an.chain(chain_image(0), 'back to gain code 0 for the output test')
        cells = plist.standing()
        bad = u.write(cells)
        if bad:
            print('   standing write did not land: %s' % ', '.join(sorted(bad)[:6]))
        sc2 = u.chip(2)
        for n in outs:
            route = 'aux%d@24' % n
            if route not in plist.routes:
                print('   AUX %d: no route in this list' % n)
                continue
            u.write(plist.routes[route], verify=False)
            u.osc(chan=24, freq=1000.0, level_dbfs=-12.0, on=True)
            time.sleep(0.35)
            sym = sc2.sym.get('_tx_out_slot_C2_AUX_OUT_%02d' % n)
            buf = sc2.sym.get('_buf_C2_AUX_OUT_%02d' % n)
            mtr = sc2.sym.get('_mtr_wide_C2_AUX_OUT_%02d' % n)
            def peek(addr, k=16):
                if addr is None:
                    return []
                return [P.from_f32(sc2.rd(addr + i)) for i in range(k)]
            slot = peek(sym)
            b = peek(buf)
            pk = max((abs(x) for x in b if x == x), default=0.0)
            pk2 = max((abs(x) for x in slot if x == x), default=0.0)
            mv = peek(mtr, 1)
            print('   AUX %d: node buffer peak %s | transmit slot peak %s | '
                  'wide meter %s'
                  % (n, P.dbv(pk) if pk else '-inf',
                     P.dbv(pk2) if pk2 else '-inf',
                     ('%.6f' % mv[0]) if mv else '-'))
            u.osc(on=False)
            time.sleep(0.1)
    finally:
        try:
            u.osc(on=False)
            u.write(plist.routes['_standing_close'], verify=False)
            u.write(['Mon001Level001=f0', 'Mon001Level002=f0'], verify=False)
        except Exception as e:
            print('   teardown: %s' % e)
        if not a.keep_rails:
            an.down()
        print('\n=== the unit as left')
        print('   AN_EN: %s' % an.sh('pinctrl get %d' % an.an_en))
        print('   chain marker: %s' % (an.sh('cat %s 2>/dev/null' % an.marker())
                                       or '(none)'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
