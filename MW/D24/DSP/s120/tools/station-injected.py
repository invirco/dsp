#!/usr/bin/env python3
"""Drive d24_runall's panel station end to end through the REAL glass protocol
(prompt.json out, answer.json in) with a scripted key stream instead of a bus."""
import json, os, shutil, sys, tempfile, threading, time
sys.path.insert(0, '/home/peter/dsp/tools/pi')
import d24_runall as R

CAT = '/home/peter/dsp/MW/D24/DSP/s116/test-catalog.csv'


class Args:
    pass


def answerer(d, script, stop):
    """Stand in for the wizard: watch prompt.json, answer it from `script`."""
    seen = set()
    while not stop.is_set():
        try:
            with open(os.path.join(d, 'prompt.json')) as fh:
                p = json.load(fh)
        except (OSError, ValueError):
            time.sleep(0.02); continue
        if p['seq'] in seen:
            time.sleep(0.02); continue
        want = script.get(p['title'])
        if want is None:
            time.sleep(0.02); continue
        seen.add(p['seq'])
        time.sleep(0.05)
        with open(os.path.join(d, 'answer.json'), 'w') as fh:
            json.dump(dict(seq=p['seq'], button=want), fh)
        time.sleep(0.05)


def run(side, station, keys, script, label):
    d = tempfile.mkdtemp()
    rows, md5 = R.load_catalog(CAT)
    R.classify(rows)
    state = R.State(os.path.join(d, 'state.json'), 'TESTUNIT', md5)
    glass = R.Glass(d)
    a = Args()
    a.inject_keys = keys
    a.panel_timeout = 5.0
    a.tools = '/home/peter/dsp/tools/pi'
    a.ignored = os.path.join(d, 'ignored.csv')
    a.serial = 'TESTUNIT'
    a.catalog_md5 = md5
    stop = threading.Event()
    t = threading.Thread(target=answerer, args=(d, script, stop), daemon=True)
    t.start()
    v = R.panel_station(a, station, rows, state, {}, glass, 1)
    stop.set()
    print('\n=== %s: %d rows landed ===' % (label, len(v)))
    for n in sorted(v):
        print('%4d  %-8s %s' % (n, v[n][0], v[n][1]))
    shutil.rmtree(d, ignore_errors=True)
    return v


if __name__ == '__main__':
    right_script = {
        'Panel loop - the always-lit rings': 'yes',
        'Panel loop - the encoder ring': 'yes',
    }
    run('right', 'M2', '/home/peter/dsp/MW/D24/DSP/s120/keys-clean-right.txt',
        right_script, 'RIGHT PANEL, clean walk')
    run('right', 'M2', '/home/peter/dsp/MW/D24/DSP/s120/keys-faults-right.txt',
        {'Panel loop - the always-lit rings': 'no',
         'Panel loop - the encoder ring': 'no'}, 'RIGHT PANEL, faults')
    run('left', 'M1', '/home/peter/dsp/MW/D24/DSP/s120/keys-clean-left.txt',
        {}, 'LEFT PANEL, clean walk')
