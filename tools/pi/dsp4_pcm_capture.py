#!/usr/bin/env python3
"""dsp4_pcm_capture.py — rung 2: prove the LOGIC->Pi capture path.

Records the I2S stream the LOGIC CPLD sends on pcm_din and checks it
against what the DSP is known to be transmitting.

With the DSP4_PATTERN firmware every transmit slot carries a word that
names its own position:

    0x5A5A | lane<<8 | slot

and the loopback bitstream's reframer de-frames two TDM8 slots of DSPB
output lane 0 into the Pi's left and right channels. So a correct capture
reads a constant 0x5A5A0000 on the left and 0x5A5A0001 on the right, and
the check is bit-exact across all 32 bits -- the lanes carry 32-bit words
and anything less than all 32 would hide exactly the edge/alignment
faults this is here to catch.

Usage:
    dsp4_pcm_capture.py [--device hw:0,0] [--seconds 2] [--expect-l 0x5A5A0000]
"""
import argparse
import struct
import subprocess
import sys
from collections import Counter


def capture(device, seconds, rate):
    cmd = ['arecord', '-D', device, '-f', 'S32_LE', '-c', '2',
           '-r', str(rate), '-d', str(seconds), '-t', 'raw', '-q']
    return subprocess.run(cmd, capture_output=True, check=True).stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--device', default='hw:dsp4pcm,0')
    ap.add_argument('--seconds', type=int, default=2)
    ap.add_argument('--rate', type=int, default=48000)
    ap.add_argument('--expect-l', type=lambda x: int(x, 0), default=0x5A5A0000)
    ap.add_argument('--expect-r', type=lambda x: int(x, 0), default=0x5A5A0001)
    ap.add_argument('--list', action='store_true', help='list capture devices')
    args = ap.parse_args()

    if args.list:
        subprocess.run(['arecord', '-l'])
        return 0

    raw = capture(args.device, args.seconds, args.rate)
    n = len(raw) // 8
    if n == 0:
        print('captured nothing'); return 1
    frames = struct.unpack('<%di' % (n * 2), raw[:n * 8])
    left = [f & 0xFFFFFFFF for f in frames[0::2]]
    right = [f & 0xFFFFFFFF for f in frames[1::2]]

    lc, rc = Counter(left), Counter(right)
    lv, ln = lc.most_common(1)[0]
    rv, rn = rc.most_common(1)[0]

    print(f'captured {n} frames at {args.rate} Hz from {args.device}')
    print(f'  left  most common 0x{lv:08X}  {ln}/{n} = {ln/n*100:.2f}%'
          f'   expected 0x{args.expect_l:08X}')
    print(f'  right most common 0x{rv:08X}  {rn}/{n} = {rn/n*100:.2f}%'
          f'   expected 0x{args.expect_r:08X}')

    ok = True
    for name, val, cnt, want in (('left', lv, ln, args.expect_l),
                                 ('right', rv, rn, args.expect_r)):
        if val != want:
            # A one-bit rotation is the classic edge/alignment fault, so
            # say so rather than just printing two hex numbers.
            for sh, how in ((1, 'shifted LEFT one bit'),
                            (-1, 'shifted RIGHT one bit')):
                cand = ((want << sh) | (want >> (32 - sh))) & 0xFFFFFFFF \
                    if sh > 0 else ((want >> 1) | (want << 31)) & 0xFFFFFFFF
                if val == cand:
                    print(f'  {name}: value is the expected word {how}'); break
            ok = False
        if cnt / n < 0.99:
            print(f'  {name}: only {cnt/n*100:.2f}% of frames agree —'
                  f' the stream is not stable')
            ok = False

    print('RUNG 2 CAPTURE: ' + ('BIT-EXACT PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
