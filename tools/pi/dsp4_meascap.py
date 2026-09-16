#!/usr/bin/env python3
"""dsp4_meascap.py — the TEST_MEAS capture arm (S56): arm it, wait, read it.

WHAT IT READS. `_test_meas_tap` copies MeasChan's post-fader pool block, whole
blocks, contiguous, into `_meas_cap_buf_C1_TEST_MEAS` (L2, DSP4_TEST_CAP_MAX
words) on chip 1 only. It is the same slot the RMS/THD+N/noise fit reads on
the same pass, so a spectrum of it and the node's results describe the same
samples. Chip 2 is not involved and nothing is injected.

THE HANDSHAKE, over two dispatch words with no cells yet (proposed
CaptureArm / CaptureReady, proposals/CONTRACT-PROPOSAL-S56.md):

    1. write CaptureReady = 0 and read it back as 0      (no stale result)
    2. write CaptureArm = N                              (unverified: a
       4096-sample run can finish before a read-back, and a read-back
       of 0 would then look like a dropped write)
    3. poll CaptureReady until it reads non-zero; if it has not
       moved after a generous timeout, the arm write was dropped: go to 2
    4. read N words out of the buffer: one DMA stream (dsp4_bulk, S61) on
       an image that carries it, else a peek per word. DSP4_BULK=0 forces
       the peek path.

The DSP also clears Ready itself when a run starts, so a host that skips
step 1 still cannot read a stale count as a finished run -- it can only
read the previous run's count BEFORE the new run starts, which is why step 1
is there.

Also returns the chip-1 `_diag_blk_overrun` delta across the run, because a
dropped block inside the capture is a discontinuity and would be read as
distortion. A capture with a non-zero delta is flagged, not silently used.

Library use: `capture(n, symdir)` -> dict in dsp4_fft.py's capture format.
CLI:  dsp4_meascap.py N [--symdir DIR] [--out FILE]
"""
import json
import os
import sys
import time

A_MEASCHAN = 4967
A_CAP_ARM = 4981          # 0x1375, proposed CaptureArm
A_CAP_READY = 4982        # 0x1376, proposed CaptureReady
BUF = '_meas_cap_buf_C1_TEST_MEAS'
DEFAULT_SYMDIR = '/home/app/s56'


def _scope():
    saved = sys.argv
    sys.argv = ['s']
    try:
        sys.path.insert(0, '/home/app/dspboot')
        import dsp4_scope as S                               # noqa: E402
    finally:
        sys.argv = saved
    return S


def _retry(sc, fn, *a):
    err = None
    for _ in range(8):
        try:
            return fn(*a)
        except (IOError, OSError) as e:
            err = e
            time.sleep(0.05)
            try:
                sc.d.resync()
            except Exception:
                pass
    raise err


def capture(n, symdir=DEFAULT_SYMDIR, timeout=3.0, log=print, sc=None):
    """`sc`: an open chip-1 dsp4_scope.Scope to reuse. A second Scope in
    the same process cannot claim the chip-select line (EBUSY)."""
    S = _scope()
    if sc is None:
        sc = S.Scope(1, symfile='%s/chip1.sym.json' % symdir)
        sc.d.resync()
    sc.check_chip()
    if BUF not in sc.sym:
        raise SystemExit('%s is not in %s/chip1.sym.json: not an S56 '
                         'TEST_NODES image' % (BUF, symdir))
    # The stale-map guard from the bench record: a wrong map peeks as zeros.
    if _retry(sc, sc.peek, sc.sym['_rx_active_buf']) == 0:
        raise SystemExit('_rx_active_buf peeks as 0: the symbol map is not '
                         'the running image')
    chan = _retry(sc, sc.rd, A_MEASCHAN)
    if not chan:
        raise SystemExit('MeasChan is 0: the capture copies MeasChan\'s '
                         'block and would never start')
    n = int(n)
    ovr_sym = sc.sym['_diag_blk_overrun']

    for _ in range(8):
        sc.d.write(A_CAP_READY, 0)
        time.sleep(S.SETTLE)
        if _retry(sc, sc.rd, A_CAP_READY) == 0:
            break
    else:
        raise IOError('CaptureReady would not clear')

    got = 0
    for attempt in range(4):
        ovr0 = _retry(sc, sc.peek, ovr_sym)
        sc.d.write(A_CAP_ARM, n)
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(0.05)
            try:
                v = sc._ask(A_CAP_READY)
            except (IOError, OSError):
                v = None
            if v:
                # static now; confirm it by a voted read
                got = _retry(sc, sc.rd, A_CAP_READY)
                break
        if got:
            break
        log('  arm attempt %d: CaptureReady still 0 after %.1f s, re-arming'
            % (attempt + 1, timeout))
    if not got:
        raise IOError('capture never completed (CaptureArm dropped 4 times?)')
    ovr1 = _retry(sc, sc.peek, ovr_sym)

    base = sc.sym[BUF]
    t0 = time.time()
    how = 'peek'
    if '_bulk_state' in sc.sym and os.environ.get('DSP4_BULK', '1') != '0':
        # S61: one DMA stream instead of three transactions a word.
        import dsp4_bulk
        vals, binfo = dsp4_bulk.read(sc, base, got, log=log)
        how = 'bulk %s Hz, sum %s' % (binfo['hz'], binfo['sum'])
    else:
        vals = [_retry(sc, sc.peek, base + i) for i in range(got)]
    dt = time.time() - t0
    ovr = (ovr1 - ovr0) & 0xFFFFFFFF
    log('  captured %d samples of strip %d (asked %d); read in %.2f s (%s); '
        'chip-1 overruns during the run +%d' % (got, chan, n, dt, how, ovr))
    if ovr:
        log('  ** a block overran during the capture: it may hold a '
            'discontinuity')
    return {'tool': 'dsp4_meascap', 'version': 1, 'fs_hz': 48000,
            'node': 'C1_TEST_MEAS capture, strip %d post-fader' % chan,
            'scale': 'q4.28', 'lanes': 1, 'symdir': symdir,
            'asked': n, 'overruns': ovr, 'read_s': round(dt, 2), 'read_how': how,
            'samples': vals}


def main(argv):
    args = [a for a in argv if not a.startswith('--')]
    symdir, out = DEFAULT_SYMDIR, None
    for i, a in enumerate(argv):
        if a == '--symdir':
            symdir = argv[i + 1]
        elif a == '--out':
            out = argv[i + 1]
    args = [a for a in args if a not in (symdir, out)]
    n = int(args[0]) if args else 4096
    cap = capture(n, symdir)
    out = out or '/tmp/meascap_%d.json' % n
    with open(out, 'w') as f:
        json.dump(cap, f)
    print('  wrote %s' % out)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
