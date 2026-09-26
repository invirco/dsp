#!/usr/bin/env python3
"""s123_loop_check.py -- one lead, one reading, one plain answer.

S123 addendum 2: two patches carried no tone. The digital half is proved
alive to the DSP's own transmit slot and every input is proved to be
listening to a live preamp, so the one link left is the analog stage after
the DAC, the lead, and the socket. That needs a hand, and PW has one.

This is what runs the moment the lead is in. It drives ONE output, reads ONE
input, and then reads EVERY input, so an answer is never just "no" -- if the
tone came back somewhere else, it says where.

    s123_loop_check.py --drive mainL --lane 17
    s123_loop_check.py --drive aux5  --lane 17 --rails-down

Rails are raised on the first call and left up unless --rails-down, so two
patches in a row cost one rail cycle and one chain write.
"""
import argparse
import os
import sys
import time

sys.path.insert(0, '/home/app/selftest')
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                '..', '..', '..', '..', 'tools', 'pi'))
import d24_patch as P                                   # noqa: E402

# The drives this can assert, by the name a person would use, mapped to the
# route id the generated list already carries. Nothing new is invented here.
DRIVES = {
    'mainL': ('MAIN L', 'mainL@24'),
    'mainR': ('MAIN R', 'mainR@24'),
    'aux1': ('AUX 1', 'aux1@24'),
    'aux2': ('AUX 2', 'aux2@24'),
    'aux3': ('AUX 3', 'aux3@24'),
    'aux4': ('AUX 4', 'aux4@24'),
    'aux5': ('AUX 5', 'aux5@24'),
    'aux6': ('AUX 6', 'aux6@24'),
    'aux7': ('AUX 7', 'aux7@24'),
    'aux8': ('AUX 8', 'aux8@24'),
}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--drive', default='mainL', choices=sorted(DRIVES))
    ap.add_argument('--lane', type=int, default=17)
    ap.add_argument('--gain', type=int, default=0,
                    help='mic preamp gain code for this reading')
    ap.add_argument('--rails-down', action='store_true',
                    help='put the rails down and the chain SAFE afterwards')
    ap.add_argument('--list-dir', default='/home/app/selftest/quick')
    ap.add_argument('--symdir', default=P.FACTORY_TEST_PAIR_DIR)
    a = ap.parse_args(argv)
    name, route = DRIVES[a.drive]

    plist = P.PatchList(a.list_dir)
    if route not in plist.routes:
        raise SystemExit('%s is not a route in this list' % route)
    u = P.Unit(symdir=a.symdir)
    an = P.Analog(enabled=True, log=lambda s: print('   .. %s' % s))
    try:
        an.up()
        an.image = None
        an.chain([((a.gain & 63) << 2)] * 24 + [0x00],
                 'at gain code %d' % a.gain)
        bad = u.write(plist.standing())
        if bad:
            print('   standing write did not land: %s' % ', '.join(sorted(bad)[:6]))
        u.write(plist.routes[route])
        u.osc(chan=24, freq=1000.0, level_dbfs=-12.0, on=True)
        time.sleep(0.4)

        u.meas_chan(a.lane)
        m = u.measure(1000.0, -12.0, settle=P.ROUTE_SETTLE_WINDOWS)
        sweep = u.meter_sweep(P.MIC_STRIPS)
        lit = sorted(((P.dbv(v), k) for k, v in sweep.items()
                      if k != 24 and v and P.dbv(v) > -80), reverse=True)

        print('\n=== %s -> MIC %d, preamp gain code %d' % (name, a.lane, a.gain))
        print('   level        %s dBFS' % _f(m.get('rms')))
        print('   loop gain    %s dB   (the coherent fit against the '
              'oscillator)' % _f(m.get('h_db')))
        print('   phase        %s deg' % _f(m.get('h_deg')))
        print('   THD+N        %s dB' % _f(m.get('thd')))
        print('   noise        %s dB' % _f(m.get('noise')))
        print('   every input: %s'
              % (', '.join('MIC %d %.1f dB' % (k, d) for d, k in lit[:6])
                 if lit else 'nothing above -80 dBFS on any input'))

        h = m.get('h_db')
        if h is not None and h > -60:
            print('\n   TONE PRESENT on MIC %d. The loop is closed: %s reaches '
                  'that input.' % (a.lane, name))
        elif lit and lit[0][1] != a.lane:
            print('\n   NO TONE on MIC %d -- it came back on MIC %d. The lead '
                  'is in the wrong socket.' % (a.lane, lit[0][1]))
        else:
            print('\n   NO TONE ANYWHERE. %s did not reach any input.' % name)
    finally:
        try:
            u.osc(on=False)
            u.write(plist.routes['_standing_close'], verify=False)
            u.write(['Mon001Level001=f0', 'Mon001Level002=f0'], verify=False)
        except Exception as e:
            print('   teardown: %s' % e)
        if a.rails_down:
            an.down()
            print('   the unit is safe: rails down, chain SAFE')
        else:
            print('   rails LEFT UP for the next patch '
                  '(--rails-down puts them back)')
    return 0


def _f(v):
    return '-' if v is None else '%8.2f' % v


if __name__ == '__main__':
    sys.exit(main())
