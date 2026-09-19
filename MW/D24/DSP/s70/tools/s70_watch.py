"""Watch the talkback lane's floor until the 150 ohm shunt appears on J1.

With PW's cable on, the XLR is terminated by the AUX 1 output stage, whose own noise
(-84.55 dBu on PW's meter) swamps the preamp at every gain code -- the input-referred
figure is flat at -84 dBu across all twelve, which is the signature of a source-limited
measurement. Swapping the cable for a 150 ohm shunt drops the lane floor, and THAT is the
event this waits for: no announcement needed, the measurement announces itself."""
import json
import sys
import time

sys.path.insert(0, '/home/app/s70')
import s70lib as T                                                       # noqa: E402

DEADLINE = time.time() + float(sys.argv[1] if len(sys.argv) > 1 else 1500)
DROP_DB = 3.0

r = T.Rig()
r.osc(on=False)
r.mgn2r(11)
r.meas(T.TALK)
base = r.point(3)['rms_dbfs']
print('baseline floor at MGN +27 dB: %.3f dBFS; waiting for a drop of %.1f dB' % (base, DROP_DB),
      flush=True)
while time.time() < DEADLINE:
    time.sleep(10)
    v = r.point(2)['rms_dbfs']
    print('%s  %9.3f dBFS  (%+0.2f)' % (time.strftime('%H:%M:%S'), v, v - base), flush=True)
    if v < base - DROP_DB:
        time.sleep(5)
        v2 = r.point(3)['rms_dbfs']
        if v2 < base - DROP_DB:
            json.dump({'baseline_dbfs': base, 'dropped_to_dbfs': v2, 't': time.time()},
                      open(T.DATA + '/shunt_seen.json', 'w'))
            print('SHUNT SEEN: floor %.3f -> %.3f dBFS' % (base, v2), flush=True)
            sys.exit(0)
print('no drop within the window; the 150 ohm was not fitted', flush=True)
sys.exit(2)
