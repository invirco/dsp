"""Round-trip offset in samples, for a differential latency measurement.

A single offset mixes ALSA start skew with real path latency and cannot
separate them. Run this on two bitstreams with IDENTICAL ALSA settings --
one looping inside LOGIC, one going through the DSP -- and the difference
is the DSP's contribution, with the skew cancelled.
"""
import struct, subprocess, sys, time

RATE = 48000; N = 48000; GUARD = 4800
REPS = int(sys.argv[1]) if len(sys.argv) > 1 else 5

stim = [0]*GUARD + [((i+1) << 8) for i in range(N)]
open('/tmp/lat.raw','wb').write(b''.join(struct.pack('<ii', v, v) for v in stim))

offs = []
for r in range(REPS):
    rec = subprocess.Popen(['arecord','-D','hw:dsp4pcm,0','-f','S32_LE','-c','2',
                            '-r',str(RATE),'-d','3','--period-size=1024',
                            '--buffer-size=8192','-t','raw','-q','/tmp/latcap.raw'],
                           stderr=subprocess.DEVNULL)
    time.sleep(0.3)
    subprocess.run(['aplay','-D','hw:dsp4pcm,1','-f','S32_LE','-c','2','-r',str(RATE),
                    '--period-size=1024','--buffer-size=8192','-t','raw','-q',
                    '/tmp/lat.raw'], check=False, stderr=subprocess.DEVNULL)
    rec.wait()
    raw = open('/tmp/latcap.raw','rb').read()
    m = len(raw)//8
    f = struct.unpack('<%di' % (m*2), raw[:m*8])
    L = f[0::2]
    hit = next(((i, v) for i, v in enumerate(L) if v), None)
    if hit is None:
        print(f'  rep {r}: nothing captured'); continue
    p, v = hit
    off = p - (GUARD + (v >> 8) - 1)
    offs.append(off)
    print(f'  rep {r}: first value {v>>8} at capture index {p} -> offset {off}')

if offs:
    offs.sort()
    print(f'OFFSET samples: min {offs[0]} median {offs[len(offs)//2]} max {offs[-1]} '
          f'spread {offs[-1]-offs[0]}')
