#!/usr/bin/env python3
"""The panel station driven through the FACTORY SCREEN (live.json), not the
dialog: a scripted key stream for the panel, and a stand-in for the app's
ENTER button. Proves the S127 path with no finger at the bench."""
import json, os, shutil, sys, tempfile, threading, time
sys.path.insert(0, '/home/peter/dsp/tools/pi')
import d24_runall as R
import d24_live as LV

CAT = '/home/peter/dsp/MW/D24/DSP/s116/test-catalog.csv'
KEYS = '/home/peter/dsp/MW/D24/DSP/s120/keys-clean-right.txt'


class Args:
    pass


def screen_watcher(d, stop, seen):
    """Stand in for the operator at the glass: report every distinct page, and
    press ENTER on anything that asks for it."""
    last = None
    while not stop.is_set():
        try:
            with open(os.path.join(d, 'live.json')) as fh:
                s = json.load(fh)
        except (OSError, ValueError):
            time.sleep(0.05); continue
        k = (s['state'], s['instruction'], s['extra'], s['n'], s['total'])
        if k != last:
            last = k
            seen.append(s)
            print('  GLASS %-8s %s/%s | %s%s'
                  % (s['state'], s['n'], s['total'], s['instruction'],
                     ('  [%s]' % s['extra']) if s['extra'] else ''))
            if 'Press ENTER' in s['instruction']:
                time.sleep(0.3)
                with open(os.path.join(d, 'command.json'), 'w') as fh:
                    json.dump(dict(command='enter', stamp=time.time()), fh)
                print('  (the operator presses ENTER)')
        time.sleep(0.05)


d = tempfile.mkdtemp()
rows, md5 = R.load_catalog(CAT)
R.classify(rows)
state = R.State(os.path.join(d, 'state.json'), 'TESTUNIT', md5)
glass = R.Glass(d)
a = Args()
a.inject_keys = KEYS
a.panel_timeout = 5.0
a.tools = '/home/peter/dsp/tools/pi'
a.ignored = os.path.join(d, 'ignored.csv')
a.serial = 'TESTUNIT'
a.catalog_md5 = md5
live = LV.Live(d, run='panel', enabled=True, confirm=True)
stop, seen = threading.Event(), []
threading.Thread(target=screen_watcher, args=(d, stop, seen), daemon=True).start()

print('=== the station card, on the glass ===')
steps = [(st, r) for st, _n, _h, _rl in R.STATIONS
         for r in R.manual_rows_for(st, rows, state, {})]
card = R.station_card('M2', steps, glass, 0, live=live, keys=None)
print('  card answered:', card)
print('=== the loop, on the glass ===')
t0 = time.time()
v = R.panel_station(a, 'M2', rows, state, {}, glass, 1, live=live)
stop.set(); time.sleep(0.3)
print('\n=== %d rows landed in %.1f s ===' % (len(v), time.time() - t0))
for n in sorted(v):
    print('%4d  %-8s %s' % (n, v[n][0], v[n][1]))
shutil.rmtree(d, ignore_errors=True)
