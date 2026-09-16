"""s60lib — the S60 chirp driver on top of s54lib (TEST_OSC SweepOn/SweepStep chirp, TEST_MEAS capture arm)."""
import json, math, os, subprocess, sys, time
os.environ['SYMDIR'] = os.environ.get('SYMDIR', '/home/app/s60')
sys.path.insert(0, '/home/app/s60'); sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/dspboot')
import s54lib as T                                        # noqa: E402
import dsp4_meascap as MC                                 # noqa: E402
import dsp4_chirp as CH                                   # noqa: E402
X = T.X
SYMDIR = os.environ['SYMDIR']
A_SWEEPON, A_SWEEPSTEP = 4979, 4980
HOME = '/home/app/s60'
DATA = HOME + '/data'
os.makedirs(DATA, exist_ok=True)


def P(*a):
    print(time.strftime('%H:%M:%S'), *a, flush=True)


class Timer:
    def __init__(self):
        self.t = {}

    def add(self, k, dt):
        self.t[k] = self.t.get(k, 0.0) + dt


def chirp(R, level_db, steps=0, chan=6):
    R.wv(A_SWEEPSTEP, steps)
    R.wv(T.A_OSCLEVEL, X.f32(10 ** (level_db / 20.0)))
    R.wv(T.A_OSCCHAN, chan)
    R.wv(T.A_OSCON, 1)
    R.wv(A_SWEEPON, 1)
    R.on = False          # s54lib's coherent fit is meaningless during a chirp
    R.chirp_level = X.from_f32(R.rd(T.A_OSCLEVEL))
    R.chirp_steps = steps


def tone(R, freq, level_db, chan=6):
    R.wv(A_SWEEPON, 0)
    R.osc(freq, level_db, on=True, chan=chan)


def capture(R, n, meas, tag, wait_periods=1.2, extra=None, tm=None):
    """Arm on MeasChan `meas` after the path has seen `wait_periods` whole periods; save to DATA/tag.json."""
    t0 = time.time()
    if R.rd(T.A_MEASCHAN) != meas:
        R.wv(T.A_MEASCHAN, meas)
    L = CH.period(getattr(R, 'chirp_steps', 0))
    time.sleep(wait_periods * L / 48000.0)
    t1 = time.time()
    lines = []
    cap = MC.capture(n, SYMDIR, sc=R.sc, log=lines.append)
    t2 = time.time()
    cap.update({'tag': tag, 'meas': meas, 'code': R.code, 'osc_level': getattr(R, 'chirp_level', None),
                'steps': getattr(R, 'chirp_steps', None), 't_setup_wait_s': round(t1 - t0, 3),
                't_capture_s': round(t2 - t1, 3)})
    if extra:
        cap.update(extra)
    with open('%s/%s.json' % (DATA, tag), 'w') as f:
        json.dump(cap, f)
    T.log({'ev': 'capture', 'tag': tag, 'meas': meas, 'code': R.code, 'overruns': cap['overruns'],
           'read_s': cap['read_s'], 't_capture_s': cap['t_capture_s'], 'lines': lines})
    if tm is not None:
        tm.add('wait', t1 - t0); tm.add('capture+read', t2 - t1)
    return cap


def fs_samples(cap):
    return [(v - (1 << 32) if v & 0x80000000 else v) / float(1 << 28) for v in cap['samples']]
