#!/usr/bin/env python3
"""s61_loop.py — S61 gate 3: s60_loop.py unchanged but for s61lib (bulk readout). Originally S60 gates 3 and 4 on the MIC 5 -> AUX 1 loop (cable on J25), captures only (analysis on the desk,
s60_analyse.py). Chain: MIC 5's register alone (send p15), phantom off, verified images (s54lib.chain).

  ref     chirp -20 dBFS pk on strip 6, capture strip 6 post-fader: the reference sweep (bit-identical every period)
  gain    for codes 0,63,1,2,4,8,16,32: chirp at lane -10 dBFS pk (osc = -10 - G_T1), capture the MIC 5 strip;
          codes 0 and 63 twice (SNR)
  thdn    1 kHz tone, lane -3 dBFS pk, codes 0 and 63: one 16k capture each (FFT THD+N)
  ein     code 63, oscillator off: one 16k capture (source = the loop cable / AUX 1 output stage, not 150 R)
  lanes   the read-all-lanes timing: per other strip, (a) strip up + capture, (b) strip up + one TEST_MEAS window
Every step is timed; /home/app/s61/s61_loop.jsonl."""
import json, os, sys, time
import s61lib as S
T, X, CH = S.T, S.X, S.CH
R = T.Rig('/home/app/s61/s61_loop.jsonl')
c1 = R.c1
M5 = T.LOOP
G_T1 = {0: 5.578, 1: 18.423, 2: 25.041, 4: 32.475, 8: 39.927, 16: 47.169, 32: 53.744, 63: 58.717}   # S55 law.csv, J25
which = os.environ.get('WHICH', 'ref,gain,thdn,ein,lanes').split(',')   # s52lib clears sys.argv on import
timing = {}
# SETTLE after a gain-code change: the first run (SETTLE 0) caught the preamp's LF recovery from the switch in
# code 63's first capture (-46 dBFS, tau ~0.4 s) -- see findings S60. TAG separates the runs' files.
SETTLE = float(os.environ.get('SETTLE', '0'))
TAG = os.environ.get('TAG', '')


def settle(tm):
    t0 = time.time(); time.sleep(SETTLE); tm.add('settle', time.time() - t0)


def tstep(name, t0):
    timing.setdefault(name, []).append(round(time.time() - t0, 3))


if 'ref' in which:
    R.chain(0)
    S.chirp(R, -20.0, 0, chan=6)
    S.capture(R, 16384, 6, 'ref_strip6_m20')
    S.P('reference captured')

if 'gain' in which:
    for code in [int(c) for c in os.environ.get('CODES', '0,63,1,2,4,8,16,32').split(',')]:
        tm = S.Timer()
        # LEVEL FIRST, THEN GAIN: switching the code up under the previous code's stimulus overdrives the
        # preamp and its coupling caps pump a DC offset that decays with tau ~0.3 s (S60-3)
        L = -10.0 - G_T1[code]
        t0 = time.time(); S.chirp(R, L, 0, chan=6); tm.add('osc words', time.time() - t0)
        t0 = time.time(); R.chain(code); tm.add('chain', time.time() - t0)
        settle(tm)
        for k in ((1, 2) if (code in (0, 63) or os.environ.get('TWO')) else (1,)):
            cap = S.capture(R, 16384, M5, 'chirp%s_c%02d_%d' % (TAG, code, k), tm=tm, extra={'osc_dbfs_pk': L})
            S.P('code %2d capture %d: osc %.2f dBFS pk, overruns %d, read %.1f s, total capture %.1f s'
                % (code, k, L, cap['overruns'], cap['read_s'], cap['t_capture_s']))
        T.log({'ev': 'gain_timing', 'code': code, 't': tm.t})
        timing['chirp_code_%d' % code] = tm.t

if 'thdn' in which:
    for code in [int(c) for c in os.environ.get('THDN_CODES', '0,63').split(',')]:
        tm = S.Timer()
        L = -3.0 - G_T1[code]
        t0 = time.time(); S.tone(R, 1000.0, L, chan=6); R.chirp_steps = 0; R.chirp_level = 10 ** (L / 20); tm.add('osc words', time.time() - t0)
        t0 = time.time(); R.chain(code); tm.add('chain', time.time() - t0)
        settle(tm)
        time.sleep(0.3)
        cap = S.capture(R, 16384, M5, 'thdn%s_c%02d' % (TAG, code), wait_periods=0.0, tm=tm, extra={'osc_dbfs_pk': L, 'tone_hz': 1000.0})
        S.P('THD+N capture code %d osc %.2f: overruns %d, %.1f s' % (code, L, cap['overruns'], cap['t_capture_s']))
        timing['thdn_code_%d' % code] = tm.t

if 'ein' in which:
    tm = S.Timer()
    t0 = time.time(); R.chain(63); tm.add('chain', time.time() - t0)
    settle(tm)
    t0 = time.time(); R.wv(S.A_SWEEPON, 0); R.osc(on=False, chan=6); tm.add('osc words', time.time() - t0)
    time.sleep(0.3)
    cap = S.capture(R, 16384, M5, 'ein%s_c63_loopsrc' % TAG, wait_periods=0.0, tm=tm)
    S.P('EIN capture (loop cable as source): overruns %d, %.1f s' % (cap['overruns'], cap['t_capture_s']))
    timing['ein'] = tm.t

if 'lanes' in which:
    # per-lane cost for the harness case; strips 7, 8, 9 (muted as found) brought up and put back
    R.chain(0)
    S.chirp(R, -10.0 - G_T1[0], 0, chan=6)
    KEYS = ['Gain001', 'Pol001', 'Level001', 'CompOn001', 'GateOn001', 'EqOn001', 'TubeOn001', 'MainOn001', 'Mute001'] + \
           ['AuxOn%03d' % a for a in range(1, 9)]
    for n in (7, 8, 9):
        pfx = 'Chan%03d' % n
        saved = {k: c1.r(pfx + k) for k in KEYS}
        t0 = time.time(); X.strip_unity(c1, n); t_up = time.time() - t0
        t0 = time.time()
        cap = S.capture(R, 16384, n, 'lane_s%02d_chirp' % n, wait_periods=1.0)
        t_cap = time.time() - t0
        t0 = time.time()
        R.meas(n)
        R.on = False
        m = R.windows(1, settle_windows=2, tag='lane_meter_s%02d' % n)
        t_met = time.time() - t0
        t0 = time.time()
        for k in reversed(KEYS):
            c1.wv(pfx + k, saved[k], 1 if k == 'Gain001' else (4 if k == 'Level001' else 0))
        t_dn = time.time() - t0
        S.P('strip %d: up %.2f s, capture %.2f s (read %.1f), one meter window %.2f s, restore %.2f s'
            % (n, t_up, t_cap, cap['read_s'], t_met, t_dn))
        timing.setdefault('lanes', []).append({'strip': n, 'up': t_up, 'capture': t_cap, 'read': cap['read_s'],
                                               'meter': t_met, 'restore': t_dn})
    R.wv(T.A_MEASCHAN, M5)

T.log({'ev': 'timing', 'which': which, 'timing': timing})
print(json.dumps(timing, indent=1))
