"""Send a KNOWN WORD through the loop and read what comes back.

A level tells you a ratio; a single set bit tells you the shift. Playing a
constant DC word means no filter or sample-timing effect can blur the
answer: whatever bit position comes back IS the net shift of the path.
"""
import struct, subprocess, sys, time
from collections import Counter

RATE = 48000; SECS = 2
words = [0x00001000, 0x00010000, 0x00100000]   # single bits, well clear of clipping

for w in words:
    buf = struct.pack('<ii', w, w) * (RATE * SECS)
    open('/tmp/dc.raw', 'wb').write(buf)
    rec = subprocess.Popen(['arecord', '-D', 'hw:0,0', '-f', 'S32_LE', '-c', '2',
                            '-r', str(RATE), '-d', str(SECS), '-t', 'raw', '-q'],
                           stdout=subprocess.PIPE)
    time.sleep(0.2)
    subprocess.run(['aplay', '-D', 'hw:0,1', '-f', 'S32_LE', '-c', '2',
                    '-r', str(RATE), '-t', 'raw', '-q', '/tmp/dc.raw'],
                   check=False, stderr=subprocess.DEVNULL)
    out, _ = rec.communicate()
    n = len(out) // 8
    f = struct.unpack('<%di' % (n * 2), out[:n * 8])
    L = [x & 0xFFFFFFFF for x in f[0::2]]
    nz = [x for x in L if x]
    if not nz:
        print(f'in 0x{w:08X} -> nothing came back'); continue
    val, cnt = Counter(nz).most_common(1)[0]
    ratio = val / w
    shift = ''
    for s in range(-8, 9):
        if s >= 0 and val == (w << s) & 0xFFFFFFFF: shift = f'= in << {s}'; break
        if s < 0 and val == w >> (-s): shift = f'= in >> {-s}'; break
    print(f'in 0x{w:08X} -> out 0x{val:08X}  ({cnt}/{len(nz)} of non-zero frames)'
          f'  ratio {ratio:.4f}  {shift}')
