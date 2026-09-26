#!/usr/bin/env python3
"""The panel station on the REAL bus with NO finger at the bench.

The negative control the injected run cannot give: every indicator write goes
out on the copper and is acked by MH1, no phantom key code is parsed out of the
heartbeat over the whole station, and every row lands NO DATA naming the press
that never came.  Run with a short --panel-timeout so it takes a minute."""
import json, os, shutil, sys, tempfile, threading, time
sys.path.insert(0, '/home/app/selftest')
import d24_runall as R

CAT = '/home/app/selftest/test-catalog.csv'


class Args:
    pass


def answerer(d, script, stop):
    seen = set()
    while not stop.is_set():
        try:
            with open(os.path.join(d, 'prompt.json')) as fh:
                p = json.load(fh)
        except (OSError, ValueError):
            time.sleep(0.02); continue
        if p['seq'] in seen or p['title'] not in script:
            time.sleep(0.02); continue
        seen.add(p['seq'])
        time.sleep(0.05)
        with open(os.path.join(d, 'answer.json'), 'w') as fh:
            json.dump(dict(seq=p['seq'], button=script[p['title']]), fh)
        time.sleep(0.05)


d = tempfile.mkdtemp()
rows, md5 = R.load_catalog(CAT)
R.classify(rows)
state = R.State(os.path.join(d, 'state.json'), 'MW-D24-2', md5)
glass = R.Glass(d)
a = Args()
a.inject_keys = None
a.panel_timeout = float(sys.argv[1]) if len(sys.argv) > 1 else 3.0
a.tools = '/home/app/selftest'
a.ignored = os.path.join(d, 'ignored.csv')
a.serial = 'MW-D24-2'
a.catalog_md5 = md5
stop = threading.Event()
threading.Thread(target=answerer, args=(d, {
    'Panel loop - the always-lit rings': 'skip',
    'Panel loop - the encoder ring': 'skip'}, stop), daemon=True).start()
t0 = time.time()
v = R.panel_station(a, 'M2', rows, state, {}, glass, 1)
stop.set()
print('\n=== real bus, no finger: %d rows, %.1f s ===' % (len(v), time.time() - t0))
for n in sorted(v):
    print('%4d  %-8s %s' % (n, v[n][0], v[n][1]))
shutil.rmtree(d, ignore_errors=True)
