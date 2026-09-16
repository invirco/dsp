import os, sys, time
ARG = list(sys.argv)
os.environ.setdefault('SYMDIR', '/home/app/s56')
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s56')
import s54lib as T
import dsp4_meascap as MC
r = T.Rig(logpath='/home/app/s56/s56_cost.jsonl'); sc = r.sc
r.meas(6)
R = sc.sym['_meas_cap_ready_C1_TEST_MEAS']
t0 = time.time(); runs = 0; done = 0
while time.time() - t0 < float(ARG[1]):
    sc.d.write(MC.A_CAP_ARM, 16384); runs += 1
    time.sleep(0.36)
    if r._retry(sc.peek, R) == 16384: done += 1
print('soak %.1f s: %d arms, %d read Ready=16384 afterwards' % (time.time() - t0, runs, done))
T.log({'ev': 'soak', 'seconds': time.time() - t0, 'arms': runs, 'ready_after': done})
