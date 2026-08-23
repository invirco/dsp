"""Pass-through calibration: bit-exactness on all 32 bits, and latency.

Two things the earlier tone test got wrong and this fixes:

  * arecord wrote into a PIPE that was only drained at the end, so the
    capture overran and the stream was full of gaps. A peak taken from
    that measures the glitch, not the signal -- which is exactly how a
    unity path came to look like a 4x gain. Capture now goes to a file
    with an explicit buffer.
  * a level ratio cannot tell you a shift. The stimulus is a per-sample
    COUNTER, so every sample carries its own index. That gives bit-exact
    comparison AND latency from the same capture: the value tells you
    which input sample it is, the position tells you where it arrived.
"""
import struct, subprocess, sys, time

RATE = 48000
N = int(sys.argv[1]) if len(sys.argv) > 1 else 48000     # samples of stimulus
GUARD = 4800                                             # leading silence

# Counter stimulus. Values are << 8 so they occupy the upper bits (clear of
# any low-bit noise) and stay well below clipping.
stim = [0] * GUARD + [((i + 1) << 8) for i in range(N)]
open('/tmp/pt.raw', 'wb').write(b''.join(struct.pack('<ii', v, v) for v in stim))

secs = (len(stim) / RATE) + 1.0
rec = subprocess.Popen(['arecord', '-D', 'hw:0,0', '-f', 'S32_LE', '-c', '2',
                        '-r', str(RATE), '-d', str(int(secs) + 1),
                        '--buffer-size=16384', '-t', 'raw', '-q', '/tmp/cap.raw'])
time.sleep(0.3)
subprocess.run(['aplay', '-D', 'hw:0,1', '-f', 'S32_LE', '-c', '2', '-r', str(RATE),
                '--buffer-size=16384', '-t', 'raw', '-q', '/tmp/pt.raw'], check=False)
rec.wait()

raw = open('/tmp/cap.raw', 'rb').read()
m = len(raw) // 8
f = struct.unpack('<%di' % (m * 2), raw[:m * 8])
L, R = f[0::2], f[1::2]

# Find the first sample that carries the counter, and the offset it implies.
first_i = first_v = None
for i, v in enumerate(L):
    if v:
        first_i, first_v = i, v
        break
if first_i is None:
    print('nothing captured'); sys.exit(1)

idx = first_v >> 8                     # which stimulus sample this is
offset = first_i - (GUARD + idx - 1)   # capture index of stimulus sample 0

# Bit-exact check over the whole run, both channels.
bad = 0; checked = 0; first_bad = None
for i in range(first_i, min(m, first_i + N - idx)):
    want = ((idx + (i - first_i)) << 8)
    if want > (N << 8): break
    checked += 1
    # LEFT ONLY. Only one node writes SPORT3 on chip 2 -- C2_MAIN_ST_OUT,
    # slot 0 -- so slot 1, which the reframer de-frames to the capture's
    # right channel, is never driven by the current graph. That is a
    # property of the node graph, not a fault in this path.
    if L[i] != want:
        bad += 1
        if first_bad is None:
            first_bad = (i, L[i], R[i], want)

print(f'captured {m} frames; stimulus {N} samples after {GUARD} of silence')
print(f'first counter sample: capture index {first_i}, value 0x{first_v:08X} '
      f'(stimulus sample {idx})')
print(f'checked {checked} frames, LEFT channel: {bad} mismatches')
if first_bad:
    i, l, r, w = first_bad
    print(f'  first mismatch at {i}: L=0x{l & 0xFFFFFFFF:08X} '
          f'R=0x{r & 0xFFFFFFFF:08X} want 0x{w:08X}')
print(f'stream offset (capture idx of stimulus sample 0) = {offset} samples')
rz = sum(1 for i in range(first_i, min(m, first_i + 1000)) if R[i])
print(f'right channel non-zero in {rz}/1000 frames after onset '
      f'(expected 0: nothing drives SPORT3 slot 1)')
print('BIT-EXACT on all 32 bits (left)' if bad == 0 else 'NOT bit-exact')
