"""Evaluate the 8-channel CM4 link (Route A): 2ch @ 192 kHz = 8ch @ 48 kHz.

The DSP4_PATTERN firmware puts a word naming its own position in every
TDM8 slot -- 0x5A5A | lane<<8 | slot -- and the evaluation bitstream taps
DSPB lane 0, whose eight slots are all driven. If the 4x-rate scheme
works, a 192 kHz stereo capture must show all EIGHT distinct words
cycling: 0x5A5A0000 .. 0x5A5A0007.

At 48 kHz it could only ever show two of them. That is the whole test.
"""
import struct, subprocess, sys
from collections import Counter

RATE = int(sys.argv[1]) if len(sys.argv) > 1 else 192000
SECS = 2
subprocess.run(['arecord', '-D', 'hw:dsp4pcm,0', '-f', 'S32_LE', '-c', '2',
                '-r', str(RATE), '-d', str(SECS), '--buffer-size=16384',
                '-t', 'raw', '-q', '/tmp/t8.raw'], check=False)
raw = open('/tmp/t8.raw', 'rb').read()
n = len(raw) // 8
f = struct.unpack('<%di' % (n * 2), raw[:n * 8])
vals = [x & 0xFFFFFFFF for x in f]
c = Counter(vals)
print(f'rate {RATE}, {n} frames, {len(vals)} words')
print('most common words:')
for v, k in c.most_common(10):
    tag = ''
    if (v & 0xFFFF0000) == 0x5A5A0000:
        tag = f'  <- pattern lane {(v >> 8) & 0xFF} slot {v & 0xFF}'
    print(f'  0x{v:08X}  {k:7d} ({k/len(vals)*100:5.1f}%){tag}')
slots = sorted({v & 0xFF for v in vals if (v & 0xFFFF0000) == 0x5A5A0000})
print(f'distinct pattern SLOTS seen: {slots}')
print(f'RESULT: {len(slots)} of 8 slots reached the Pi')
