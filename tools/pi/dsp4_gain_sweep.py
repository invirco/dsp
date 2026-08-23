"""GAIN family on hardware: set C2_PI_IN level, play a DC word, capture.

Prints "level_float,in_word,out_word" per step. The comparison against
fixed_ref happens off-box so the reference model stays in one place.
"""
import struct, subprocess, sys, time
_ARGS = sys.argv[1:]
sys.argv = ['g']
import dsp4_diag as D

DC   = 0x00100000            # well clear of clipping at up to +18 dB
RATE = 48000
LEVELS = [float(x) for x in _ARGS[0].split(',')] if _ARGS else None
if LEVELS is None:
    import math
    LEVELS = [10 ** (db / 20.0) for db in
              (-60, -48, -36, -24, -18, -12, -6, -3, 0, 3, 6, 12, 18)]

buf = struct.pack('<ii', DC, DC) * (RATE // 2)
open('/tmp/dc1.raw', 'wb').write(buf)

link = D.SpiLink('0.0', 1000000, 24, rdy_gpio=12)   # chip 2
diag = D.DiagLink(link)

for lv in LEVELS:
    w = struct.unpack('<I', struct.pack('<f', lv))[0]   # float32 word
    # MUST go through the ramp path. _auxin_level is a RAMPED parameter:
    # the node's block-rate code does `if frames <= 0: level = target`
    # every block, so a direct (ramp_id 0) write is overwritten within one
    # block period -- which is why the first sweep showed no gain change
    # at any setting. ramp_id 1 (GainFast) routes the write through
    # _ramp_set_target so the target moves and the level follows.
    for _ in range(3):
        link.write(0x071C, w, 1)
    time.sleep(0.4)          # let the ramp finish before measuring
    rec = subprocess.Popen(['arecord','-D','hw:dsp4pcm,0','-f','S32_LE','-c','2',
                            '-r',str(RATE),'-d','1','--buffer-size=16384',
                            '-t','raw','-q','/tmp/g.raw'], stderr=subprocess.DEVNULL)
    time.sleep(0.15)
    subprocess.run(['aplay','-D','hw:dsp4pcm,1','-f','S32_LE','-c','2','-r',str(RATE),
                    '--buffer-size=16384','-t','raw','-q','/tmp/dc1.raw'],
                   check=False, stderr=subprocess.DEVNULL)
    rec.wait()
    raw = open('/tmp/g.raw','rb').read()
    n = len(raw)//8
    f = struct.unpack('<%di' % (n*2), raw[:n*8])
    L = [v for v in f[0::2] if v]
    if not L:
        print(f'{lv:.9g},{DC},NONE'); continue
    from collections import Counter
    val, _ = Counter(L).most_common(1)[0]
    print(f'{lv:.9g},{DC},{val & 0xFFFFFFFF}')
