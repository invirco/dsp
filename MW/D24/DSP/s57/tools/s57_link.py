"""s57_link.py <tag> <count> <mode> — is the burst the host's SPI traffic? Code stays where it is (no chain write),
TEST_OSC off, MeasChan = the MIC 5 strip. Each 16k capture-arm run is taken with the link in one state for its whole 0.34 s:
  quiet   arm, sleep 0.5 s, then one read of CaptureReady (no traffic during the run)
  c1      arm, then back-to-back chip-1 reads of MeasSeq until Ready (the S54 window loop's traffic, flat out)
  c2      arm, then back-to-back chip-2 reads (chip 2's CS, chip 1 silent) for 0.5 s, then Ready on chip 1
  win     arm, then S54-style windows() polling on chip 1 (seq polls at WIN_S/3 plus the 7 result reads)
Modes cycle in the order given if mode is a comma list."""
import json, os, sys, time
os.environ.setdefault('SYMDIR', '/home/app/s56')
A = sys.argv[1:]
sys.path.insert(0, '/home/app/s54'); sys.path.insert(0, '/home/app/s56')
import s54lib as T
import dsp4_meascap as MC
X = T.X
tag, count, modes = A[0], int(A[1]), A[2].split(',')
D = '/home/app/s57/data'
r = T.Rig(logpath='/home/app/s57/s57_link.jsonl')
r.meas(T.LOOP)
r.osc(on=False)
sc = r.sc
c2 = X.Chip(2) if 'c2' in modes else None
BUF = MC.BUF
for i in range(count):
    mode = modes[i % len(modes)]
    for _ in range(8):
        sc.d.write(MC.A_CAP_READY, 0); time.sleep(0.01)
        if r.rd(MC.A_CAP_READY) == 0:
            break
    ovr0 = r._retry(sc.peek, sc.sym['_diag_blk_overrun'])
    sc.d.write(MC.A_CAP_ARM, 16384)
    t0 = time.time(); nio = 0
    if mode == 'quiet':
        time.sleep(0.5)
    elif mode == 'c1':
        while time.time() - t0 < 0.5:
            try:
                sc._ask(T.A_SEQ); nio += 1
            except (IOError, OSError):
                pass
    elif mode == 'c2':
        while time.time() - t0 < 0.5:
            try:
                c2.sc._ask(T.A_SEQ); nio += 1
            except (IOError, OSError):
                pass
    elif mode == 'win':
        while time.time() - t0 < 0.5:
            try:
                sc._ask(T.A_SEQ); nio += 1
                time.sleep(T.WIN_S / 3)
            except (IOError, OSError):
                pass
    got = r.rd(MC.A_CAP_READY)
    if got != 16384:
        time.sleep(0.5); got = r.rd(MC.A_CAP_READY)
    ovr = (r._retry(sc.peek, sc.sym['_diag_blk_overrun']) - ovr0) & 0xFFFFFFFF
    vals = [r._retry(sc.peek, sc.sym[BUF] + j) for j in range(got)]
    cap = {'tool': 's57_link', 'fs_hz': 48000, 'scale': 'q4.28', 'lanes': 1, 'node': 'C1_TEST_MEAS capture, the MIC 5 strip',
           'samples': vals, 'overruns': ovr, 't_arm': round(t0, 3), 'code': int(os.environ.get('S57_CODE', '63')),
           'tone': 0, 'tag': tag, 'idx': i, 'mode': mode, 'link_ios': nio}
    json.dump(cap, open('%s/%s_%02d.json' % (D, tag, i), 'w'))
    T.log({'ev': 'link', 'tag': tag, 'idx': i, 'mode': mode, 'ios': nio, 'ovr': ovr, 'n': got, 't_arm': round(t0, 3)})
    print('%s_%02d %-5s ios %4d n %d ovr +%d' % (tag, i, mode, nio, got, ovr), flush=True)
