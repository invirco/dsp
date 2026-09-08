"""Send a KNOWN WORD through the loop and read what comes back.

A level tells you a ratio; a single set bit tells you the shift. Playing a
constant DC word means no filter or sample-timing effect can blur the
answer: whatever bit position comes back IS the net shift of the path.
"""
import os, struct, subprocess, sys, time
from collections import Counter

RATE = int(os.environ.get('RATE', 48000)); SECS = 2
# One device under `dsp4-pcm-duplex`, two under `dsp4-pcm-slave`.
REC_DEV  = os.environ.get('REC_DEV',  'hw:0,0')
PLAY_DEV = os.environ.get('PLAY_DEV', 'hw:0,0')
words = [0x00001000, 0x00010000, 0x00100000]   # single bits, well clear of clipping

for w in words:
    buf = struct.pack('<ii', w, w) * (RATE * SECS)
    open('/tmp/dc.raw', 'wb').write(buf)
    # CAPTURE TO A FILE, NOT A PIPE. Reading the pipe only after aplay
    # returns leaves arecord's stdout unread for the whole play, and at
    # 192 kHz that overruns by seconds -- measured 2026-09-08, "overrun!!!
    # (at least 7626 ms long)" on a 2-second capture, with the returned
    # word then a constant unrelated to anything played. An overrun makes
    # every number below fiction.
    rec = subprocess.Popen(['arecord', '-D', REC_DEV, '-f', 'S32_LE', '-c', '2',
                            '-r', str(RATE), '-d', str(SECS),
                            '--buffer-size=16384', '-t', 'raw', '-q',
                            '/tmp/dc_cap.raw'], stderr=subprocess.PIPE)
    time.sleep(0.2)
    subprocess.run(['aplay', '-D', PLAY_DEV, '-f', 'S32_LE', '-c', '2',
                    '-r', str(RATE), '--buffer-size=16384',
                    '-t', 'raw', '-q', '/tmp/dc.raw'],
                   check=False, stderr=subprocess.DEVNULL)
    _, rerr = rec.communicate()
    if b'overrun' in (rerr or b'') or b'underrun' in (rerr or b''):
        print(f'in 0x{w:08X} -> XRUN, no verdict: '
              f'{(rerr or b"").decode().strip()[:60]}')
        continue
    out = open('/tmp/dc_cap.raw', 'rb').read()
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
