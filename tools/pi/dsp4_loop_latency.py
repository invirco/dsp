"""Round-trip latency of the CM4 loop at 48 kHz, on a NAMED bitstream.

WHAT THIS MEASURES AND WHY IT IS NOT ONE NUMBER. A single captured offset
is the sum of two unrelated things:

  * the PATH, which is fixed by the hardware -- CPLD TDM framing, the
    SPORT DMA window, the DSP block, the CPLD capture re-frame; and
  * the ALSA START SKEW, which is where the capture stream happened to
    open relative to the playback stream and is different on every run
    and every boot.

The skew is the larger of the two and it is NOISE. It is removed by
DIFFERENCE: the same stimulus and the same ALSA settings are run against
two bitstreams that differ only in where the loop closes --

    <name>_pisel    Pi -> CPLD -> Pi         (DSP not in the path)
    <name>_maincap  Pi -> CPLD -> DSPA -> fabric -> DSPB -> CPLD -> Pi

-- and the difference of the two offsets is the DSP's contribution with
the skew cancelled. Run this script once per bitstream and subtract.

48 kHz ONLY, ENFORCED. On a non-TDM8 bitstream LOGIC masters pcm_clk and
pcm_fs at 48 kHz and the CM4 is a clock slave, so the wire rate is 48 kHz
whatever ALSA is told; asking ALSA for anything else does not change the
wire, it only mislabels the samples. That mislabelling is exactly how the
2026-09-08 "reorders samples" result was produced and then withdrawn. The
rate is therefore a constant here, not an argument.

THE OFFSET IS FOUND FROM THE COUNTER, NOT FROM THE FIRST NON-ZERO SAMPLE.
The stimulus is silence, then one impulse, then a ramp whose every sample
carries its own index in the top 24 bits. Finding the edge alone cannot
tell a late start from a dropped block, and it breaks outright when the
loop carries a DC pedestal (which it does until the main chain is set to
unity). Instead every captured sample votes: a sample of value v seen at
capture index i implies offset i - stim_index(v), and a clean loop makes
every vote agree. The spread of those votes IS the reorder/drop check,
so gate 4 falls out of the same capture as gate 3.
"""
import os, struct, subprocess, sys, time
from collections import Counter

RATE  = 48000                 # NOT an argument -- see the module docstring
GUARD = 4800                  # 100 ms of silence before the impulse
N     = int(os.environ.get('N', 48000))       # ramp length in samples
REPS  = int(os.environ.get('REPS', 20))
DEV   = os.environ.get('DEV', 'hw:dsp4pcm,0')     # duplex: one device
PLAY_DEV = os.environ.get('PLAY_DEV', DEV)
REC_DEV  = os.environ.get('REC_DEV',  DEV)
PERIOD = os.environ.get('PERIOD', '1024')
BUFFER = os.environ.get('BUFFER', '8192')
TAG    = os.environ.get('TAG', 'run')

# Stimulus: GUARD zeros, one impulse, then the counter ramp. The impulse
# is a distinct value no ramp sample takes, so it can be found on its own
# when the counter vote is inconclusive.
IMPULSE = 0x7F000000
stim = [0] * GUARD + [IMPULSE] + [((i + 1) << 8) for i in range(N)]
STIM_BASE = GUARD + 1          # capture index of ramp sample 0 at offset 0

with open('/tmp/loplat.raw', 'wb') as f:
    f.write(b''.join(struct.pack('<ii', v, v) for v in stim))

secs = int(len(stim) / RATE) + 2


def one_rep(r):
    rec = subprocess.Popen(
        ['arecord', '-D', REC_DEV, '-f', 'S32_LE', '-c', '2', '-r', str(RATE),
         '-d', str(secs), '--period-size=' + PERIOD, '--buffer-size=' + BUFFER,
         '-t', 'raw', '-q', '/tmp/loplatcap.raw'], stderr=subprocess.PIPE)
    time.sleep(0.3)
    pl = subprocess.run(
        ['aplay', '-D', PLAY_DEV, '-f', 'S32_LE', '-c', '2', '-r', str(RATE),
         '--period-size=' + PERIOD, '--buffer-size=' + BUFFER, '-t', 'raw',
         '-q', '/tmp/loplat.raw'], capture_output=True)
    _, rerr = rec.communicate()

    raw = open('/tmp/loplatcap.raw', 'rb').read()
    m = len(raw) // 8
    f = struct.unpack('<%di' % (m * 2), raw[:m * 8])
    L = f[0::2]

    # Every captured sample that looks like a ramp word votes for an
    # offset. A ramp word is a multiple of 256 whose index is in range;
    # that is 24 bits of self-identification, so a false vote needs the
    # loop to invent a valid counter word, not merely to be noisy.
    votes = Counter()
    for i, v in enumerate(L):
        if v and v != IMPULSE and (v & 0xFF) == 0:
            idx = (v >> 8) - 1
            if 0 <= idx < N:
                votes[i - (STIM_BASE + idx)] += 1
    if not votes:
        return None, {'reason': 'no ramp words captured',
                      'aplay': (pl.stderr or b'').decode().strip()[:60],
                      'arecord': (rerr or b'').decode().strip()[:60]}
    off, agree = votes.most_common(1)[0]
    total = sum(votes.values())

    imp = next((i for i, v in enumerate(L) if v == IMPULSE), None)
    imp_off = None if imp is None else imp - GUARD

    return off, {
        'agree': agree, 'total': total,
        'distinct_offsets': len(votes),
        'impulse_offset': imp_off,
        'aplay': (pl.stderr or b'').decode().strip()[:60],
        'arecord': (rerr or b'').decode().strip()[:60],
    }


print(f'{TAG}: rate {RATE} play {PLAY_DEV} rec {REC_DEV} '
      f'period {PERIOD} buffer {BUFFER} reps {REPS} ramp {N}')
offs, imps, agrees = [], [], []
for r in range(REPS):
    off, info = one_rep(r)
    if off is None:
        print(f'  rep {r:2d}: FAILED -- {info["reason"]} '
              f'(aplay {info["aplay"]!r} arecord {info["arecord"]!r})')
        continue
    offs.append(off)
    agrees.append(info['agree'] / info['total'])
    if info['impulse_offset'] is not None:
        imps.append(info['impulse_offset'])
    print(f'  rep {r:2d}: offset {off:6d}  counter agreement '
          f'{info["agree"]}/{info["total"]} '
          f'({info["distinct_offsets"]} distinct)  impulse {info["impulse_offset"]}')

if not offs:
    print(f'{TAG}: NO RESULT'); sys.exit(1)

s = sorted(offs)
mean = sum(offs) / len(offs)
print(f'{TAG}: OFFSET samples  n {len(offs)}  min {s[0]}  mean {mean:.1f}  '
      f'max {s[-1]}  median {s[len(s)//2]}  spread {s[-1]-s[0]}')
print(f'{TAG}: OFFSET ms       min {s[0]/RATE*1000:.3f}  mean {mean/RATE*1000:.3f}  '
      f'max {s[-1]/RATE*1000:.3f}')
if imps:
    si = sorted(imps)
    print(f'{TAG}: IMPULSE offset  n {len(imps)}  min {si[0]}  max {si[-1]} '
          f'(counter-minus-impulse median {s[len(s)//2] - si[len(si)//2]})')
print(f'{TAG}: counter agreement min {min(agrees)*100:.4f}% '
      f'mean {sum(agrees)/len(agrees)*100:.4f}%  '
      f'-- 100% means every captured ramp word sat at the same offset '
      f'(no reorder, no drop)')
