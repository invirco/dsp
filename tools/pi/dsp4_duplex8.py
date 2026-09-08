"""DUPLEX proof for the 8-channel CM4 link.

aplay and arecord run SIMULTANEOUSLY. The stimulus is a per-word counter,
so every word carries its own index and the captured stream must climb by
exactly +1 per word. Each run of 8 consecutive words is one 48 kHz frame
across slots 0..7, so a clean climb proves all eight slots in BOTH
directions at once -- de-framing on the way in, re-framing on the way out.

ONE DEVICE, NOT TWO. Under the old `dsp4-pcm-slave` overlay the card
exposed a capture-only device 0 and a playback-only device 1, because its
two dummy codecs were single-direction and no single dai-link could carry
both ways. Opening both at once re-programmed one bcm2835-i2s block
twice, and the counter came back scrambled -- values under ~200 across
20,000 frames, dominant step -191, with ALSA reporting no under/overrun
(2026-09-08). `dsp4-pcm-duplex` gives ONE device with `playback 1 :
capture 1`, so both directions share one hw_params.

    PLAY_DEV / REC_DEV override the defaults for a bench still on the old
    overlay: PLAY_DEV=hw:dsp4pcm,1 REC_DEV=hw:dsp4pcm,0
"""
import os, struct, subprocess, sys, time

REC_DEV  = os.environ.get('REC_DEV',  'hw:dsp4pcm,0')
PLAY_DEV = os.environ.get('PLAY_DEV', 'hw:dsp4pcm,0')
# THE PI FRAME IS 192 kHz, NOT 48 kHz. `shared/dsp4-logic/slot-map.csv`
# (lane A_I6) says LOGIC "regroups 4 Pi frames per DSP frame": the Pi runs
# a 2-slot 32-bit I2S frame and four of them make one 8-slot 48 kHz DSP
# frame. RATE is overridable because a codec that constrains the rate
# (google,voicehat declares 48 kHz only) will make ALSA clamp it, and the
# clamp is worth measuring rather than arguing about.

RATE = int(os.environ.get('RATE', 192000))
N    = int(sys.argv[1]) if len(sys.argv) > 1 else 192000   # words
GUARD = 8192

stim = [0]*GUARD + [((i+1) << 8) for i in range(N)]
open('/tmp/d8.raw','wb').write(b''.join(struct.pack('<i', v) for v in stim))

secs = int(len(stim)/RATE) + 2
rec = subprocess.Popen(['arecord','-D',REC_DEV,'-f','S32_LE','-c','2',
                        '-r',str(RATE),'-d',str(secs),'--buffer-size=16384',
                        '-t','raw','-q','/tmp/d8cap.raw'], stderr=subprocess.PIPE)
time.sleep(0.3)
pl = subprocess.run(['aplay','-D',PLAY_DEV,'-f','S32_LE','-c','2',
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
