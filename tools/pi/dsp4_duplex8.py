"""DUPLEX proof for the 8-channel CM4 link.

aplay and arecord run SIMULTANEOUSLY. The stimulus is a per-word counter,
so every word carries its own index and the captured stream must climb by
exactly +1 per word. Each run of 8 consecutive words is one 48 kHz frame
across slots 0..7, so a clean climb proves all eight slots in BOTH
directions at once -- de-framing on the way in, re-framing on the way out.
"""
import struct, subprocess, sys, time

RATE = 192000
N    = int(sys.argv[1]) if len(sys.argv) > 1 else 192000   # words
GUARD = 8192

stim = [0]*GUARD + [((i+1) << 8) for i in range(N)]
open('/tmp/d8.raw','wb').write(b''.join(struct.pack('<i', v) for v in stim))

secs = int(len(stim)/RATE) + 2
rec = subprocess.Popen(['arecord','-D','hw:dsp4pcm,0','-f','S32_LE','-c','2',
                        '-r',str(RATE),'-d',str(secs),'--buffer-size=16384',
                        '-t','raw','-q','/tmp/d8cap.raw'], stderr=subprocess.PIPE)
time.sleep(0.3)
pl = subprocess.run(['aplay','-D','hw:dsp4pcm,1','-f','S32_LE','-c','2',
                     '-r',str(RATE),'--buffer-size=16384','-t','raw','-q',
                     '/tmp/d8.raw'], capture_output=True)
_, rerr = rec.communicate()

raw = open('/tmp/d8cap.raw','rb').read()
w = struct.unpack('<%di' % (len(raw)//4), raw)
nz = [(i, v) for i, v in enumerate(w) if v]
if not nz:
    print('nothing captured'); sys.exit(1)
start = nz[0][0]
seq = [v >> 8 for v in w[start:start+N] if v]
steps = [seq[i+1]-seq[i] for i in range(len(seq)-1)]
good = sum(1 for s in steps if s == 1)
print(f'captured {len(w)} words; first non-zero at {start} = {seq[0]}')
print(f'counter range {min(seq)}..{max(seq)} over {len(seq)} words')
print(f'consecutive +1 steps: {good}/{len(steps)} = {good/max(1,len(steps))*100:.2f}%')
print('aplay  stderr:', (pl.stderr or b"").decode().strip()[:70] or '(none)')
print('arecord stderr:', (rerr or b"").decode().strip()[:70] or '(none)')
print('DUPLEX 8-CHANNEL: PASS' if good == len(steps) else 'DUPLEX 8-CHANNEL: FAIL')
