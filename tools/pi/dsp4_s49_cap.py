#!/usr/bin/env python3
"""dsp4_s49_cap.py — capture a node's block into the file dsp4_fft.py reads.

NEEDS `DSP4_SCOPE_BLK_TAP=1` AS WELL AS `DSP4_TEST_NODES=1`. The tap is what
copies whole blocks into `_scope_buf`; the self-test nodes are what put a tone
in them. Both are checked before anything is armed.

WHY A CAPTURE AND NOT A PEEK, restated because S48 section 7.4 paid for it: a
peek window re-reads the SAME sixteen-word block however long it runs, so it
sees a third of a millisecond of audio and can tell you nothing about a
waveform. `_scope_tap` copies 1024 CONTIGUOUS samples -- 21.3 ms at 48 kHz --
and that is a spectrum's worth.

NOTHING IS INJECTED BY THIS TOOL. `--inj` is deliberately absent: the stimulus
is the TEST_OSC node, armed by dsp4_s49_osc.py through the cells, and it is
already running when this is called. Arming the scope's own injector as well
would put a step on top of the tone and the FFT would measure the step.

THE OUTPUT declares its own scale, because a level is meaningless without one
and the two scales in this system are 18.06 dB apart (S48 7.2): `q4.28` for a
node block, where 1.0 is converter full scale, and `rx24in32` for a raw
converter slot.

Usage:
  dsp4_s49_cap.py <node> [--out FILE] [--n 1024] [--symdir DIR] [--chip N]
    e.g. dsp4_s49_cap.py C1_FDR_05 --out /tmp/s49_fdr05.json
"""
import argparse
import json
import sys
import time

_ARGV = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S                                       # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('node', help='node id (C1_FDR_05) or _buf_ symbol')
    ap.add_argument('--out', default=None)
    ap.add_argument('--n', type=int, default=S.SCOPE_MAX)
    ap.add_argument('--chip', type=int, default=1)
    ap.add_argument('--symdir', default='/home/app/s49tap')
    ap.add_argument('--scale', default='q4.28',
                    choices=('q4.28', 'rx24in32'))
    a = ap.parse_args(_ARGV)

    sym = a.node if a.node.startswith('_') else '_buf_%s' % a.node
    sc = S.Scope(a.chip, symfile='%s/chip%d.sym.json' % (a.symdir, a.chip))
    sc.d.resync()
    sc.check_chip()
    if '_scope_inj_blk' not in sc.sym:
        raise SystemExit('not a DSP4_SCOPE_BLK_TAP image (%s)' % a.symdir)
    if '_osc_blk_q_C1_TEST_OSC' not in sc.sym:
        raise SystemExit('not a DSP4_TEST_NODES image (%s)' % a.symdir)
    if sym not in sc.sym:
        raise SystemExit('%s is not in the chip %d map' % (sym, a.chip))

    print('dsp4_s49_cap — capturing %s (%s)' % (sym, a.symdir))
    # src = the node to record, inj = 0: capture only, no stimulus of our
    # own. The tone is already running, driven through the cells.
    sc.arm(src=sc.sym[sym], inj=0, amp=0, mode=0)
    sc.wait()
    idx = sc.rd(S.SCOPE_IDX)
    print('  _scope_idx = %s' % idx)
    n = min(a.n, S.SCOPE_MAX)
    t0 = time.time()
    vals = sc.fetch(n)
    print('  %d samples in %.1f s' % (len(vals), time.time() - t0))

    cap = {'tool': 'dsp4_s49_cap', 'version': 1, 'fs_hz': 48000,
           'node': sym, 'scale': a.scale, 'lanes': 1,
           'symdir': a.symdir, 'samples': vals}
    out = a.out or ('/tmp/%s.json' % sym.strip('_'))
    with open(out, 'w') as f:
        json.dump(cap, f)
    print('  wrote %s' % out)
    print('  run:   python3 dsp4_fft.py %s --png %s.png'
          % (out, out.rsplit('.', 1)[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
