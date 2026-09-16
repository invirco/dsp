"""s55_repeat.py <XLR> [timeout_s] — S55 hub addendum: REPEAT T4/T4b on one channel after PW refits the 150 ohm.
The run's own conditions: every powered register open at code 0, the channel under test at code 63, TEST_OSC off,
MeasChan = its lane. Arms the SHUNT detection only on a TRANSITION: the floor must be seen >= -70 dBFS (shunt off /
being handled) or, if it is already below at arming, it must first rise and fall again — an untouched shunt never
counts as a refit. Captures saved as data/<XLR>r_c63_* / _c00_* (the first run's files are not touched).
Times out (exit 2) with the unit handed back if nothing happens."""
import json, os, sys, time
A = list(sys.argv)   # s52lib clears sys.argv on import
sys.path.insert(0, '/home/app/s55')
import s55_run as S
T = S.T
xlr = A[1]
timeout = float(A[2]) if len(A) > 2 else 900.0
ch = [c for c in S.CHANNELS if c[0] == xlr][0]
_, p, lane, panel = ch
R = S.S55()
ok, pin = R.an_en()
S.P('AN_EN: %s' % pin)
if not ok:
    raise SystemExit('AN_EN LOW — blocked')
saved = R.strip_save(lane)
S.X.strip_unity(R.c1, lane)
R.osc(on=False)
R.chain(63, p)
R.meas(lane)
S.P('REPEAT %s (%s): code 63 (p%d), TEST_OSC off, watching lane %d; timeout %.0f s' % (xlr, panel, p, lane, timeout))
# baseline AFTER the code-switch transient (the first arming read -41 dBFS on the settle window and false-triggered)
base_w = R.windows(20, settle_windows=40, tag=xlr + ':repeatbase')['rows']
base = sorted(w['rms'] for w in base_w)[10]
T.log({'ev': 'repeat_baseline', 'xlr': xlr, 'median': base, 'rms': [w['rms'] for w in base_w]})
S.P('  baseline (settled, 20-window median) %.2f dBFS; refit = a disturbance >= %.2f, then <= %.2f and < %.0f held %.0f s'
    % (base, base + 6, base - 4, S.SHUNT_DBFS, S.SHUNT_HOLD_S))
t0 = time.time()
seen_high, since, last_print, status = False, None, 0, 'timeout'
first = base
while time.time() - t0 < timeout:
    v = R.windows(1, settle_windows=1, tag=xlr + ':repeatwatch')['rows'][0]['rms']
    if time.time() - last_print > 30:
        S.P('  lane %d RMS %.2f dBFS (disturbance seen: %s)' % (lane, v, seen_high)); last_print = time.time()
    if v >= base + 6:
        if not seen_high:
            S.P('  disturbance: %.2f dBFS' % v)
        seen_high, since = True, None
    elif seen_high and v <= base - 4 and v < S.SHUNT_DBFS:
        since = since or time.time()
        if time.time() - since >= S.SHUNT_HOLD_S:
            status = 'refit'
            break
    else:
        since = None
T.log({'ev': 'repeat_arm_result', 'xlr': xlr, 'status': status, 'first_rms': first, 'waited_s': round(time.time() - t0)})
out = None
if status == 'refit':
    S.P('%s: floor %.2f dBFS held %.0f s after a rise -> 150 ohm refit taken' % (xlr, v, S.SHUNT_HOLD_S))
    out = S.noise(R, (xlr + 'r', p, lane, panel))
    json.dump({'xlr': xlr, 'lane': lane, 'p': p, 't4': out}, open('%s/%sr_repeat.json' % (S.DATA, xlr), 'w'))
else:
    S.P('%s: no refit seen in %.0f s (first reading %.2f dBFS) — nothing measured' % (xlr, timeout, first))
R.osc(on=False)
R.chain(0)
R.strip_restore(lane, saved)
R.meas(T.LOOP)
S.P('DONE status=%s' % status)
sys.exit(0 if status == 'refit' else 2)
