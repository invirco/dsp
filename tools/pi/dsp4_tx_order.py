#!/usr/bin/env python3
"""dsp4_tx_order.py -- does the chip-2 TRANSMIT path reorder blocks, or is
it handed them already out of order?

The staircase through Pi -> CPLD -> DSPA -> fabric -> DSPB -> CPLD -> Pi
returns every sample at the right position inside its 8-sample block but
a third of blocks in place and the rest from roughly the last 225 blocks
(finding S7-5). Everything upstream of chip 2's transmit path has been
excluded by measurement, and nothing so far separates

    (i)  a block that LEAVES the DSP out of order, from
    (ii) a block that ARRIVES at the gather out of order.

The firmware instrument (SHARC/src/tx_probe.asm, DSP4_TXPROBE=1) settles
it. Chip 2's TX lane 3 is a full-window lane; slot 0 is C2_MAIN_ST_OUT --
the audio -- and slot 1 is driven onto the wire but written by no node.
Straight after the gather writes slot 0 for sample s of block N, the
instrument writes into slot 1 of the SAME frame of the SAME buffer half:

    bits 31..8  N        the block counter, incremented once per block
    bit  4      half     0 = the active TX buffer is ping, 1 = pong
    bits 3..0   s        the sample index inside the block (BLOCK <= 16)

The _maincap LOGIC build presents slot 0 as the capture's LEFT channel and
slot 1 as its RIGHT, latched together from ONE DSP frame (S7-1), so a
recorded stereo frame is a coherent (audio, stamp) pair. The stamp is in
order BY CONSTRUCTION, so the capture decides it:

    stamps monotonic  -> the buffer->wire path is in order; the scramble
                         is upstream of the gather
    stamps scrambled  -> the transmit path, and the displacement is read
                         directly in BLOCKS instead of inferred from the
                         audio value

Run on the bench Pi with the duplex overlay, the _maincap bitstream and a
DSP4_TXPROBE=1 chip-2 image:

    python3 dsp4_tx_order.py [--hold 64] [--steps 1500] [--dump N]
"""
import argparse
import struct
import subprocess
import sys
import time
from collections import Counter

DEV = "hw:dsp4pcm,0"
RATE = 48000
# BLOCK is a build parameter and this tool decodes a field whose width
# follows it. It was the literal 8 until 2026-09-09, which would have
# silently mis-decoded every block-16 stamp -- the same class of mistake as
# the defect it exists to measure (findings S8-2). dsp4_block.py is generated
# beside the image and staged with it.
try:
    from dsp4_block import BLOCK
except ImportError:                       # off-target
    BLOCK = 16


def s32(v):
    return v - (1 << 32) if v >> 31 else v


def play_capture(stim, seconds):
    open("/tmp/txo_s.raw", "wb").write(
        b"".join(struct.pack("<ii", s32(v), s32(v)) for v in stim))
    rec = subprocess.Popen(
        ["arecord", "-D", DEV, "-f", "S32_LE", "-c", "2", "-r", str(RATE),
         "-d", str(seconds), "--period-size=1024", "--buffer-size=8192",
         "-t", "raw", "-q", "/tmp/txo_c.raw"], stderr=subprocess.PIPE)
    time.sleep(0.3)
    subprocess.run(["aplay", "-D", DEV, "-f", "S32_LE", "-c", "2", "-r",
                    str(RATE), "--period-size=1024", "--buffer-size=8192",
                    "-t", "raw", "-q", "/tmp/txo_s.raw"], capture_output=True)
    rec.wait()
    cap = open("/tmp/txo_c.raw", "rb").read()
    m = len(cap) // 8
    f = struct.unpack("<%di" % (m * 2), cap[:m * 8])
    return [x & 0xFFFFFFFF for x in f[0::2]], [x & 0xFFFFFFFF for x in f[1::2]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hold", type=int, default=64)
    ap.add_argument("--steps", type=int, default=1500)
    ap.add_argument("--dump", type=int, default=24,
                    help="raw (L,R) frames to print around the first stamp")
    a = ap.parse_args()

    stim = []
    for k in range(a.steps):
        stim += [((k + 1) << 8)] * a.hold
    secs = max(4, len(stim) // RATE + 2)
    L, R = play_capture(stim, secs)
    m = len(L)
    print("captured %d frames (%.2f s)" % (m, m / RATE))

    # ---- the stamp channel ------------------------------------------
    nzr = [i for i, v in enumerate(R) if v]
    if not nzr:
        print("NO STAMP: the right channel is all zero. Is this a "
              "DSP4_TXPROBE=1 image on a _maincap bitstream?")
        return 2
    r0, r1 = nzr[0], nzr[-1]
    print("stamp present on frames %d..%d (%d of %d)"
          % (r0, r1, len(nzr), m))
    if a.dump:
        print("  raw L/R from the first stamp:")
        for i in range(r0, min(r0 + a.dump, m), BLOCK):
            print("    " + "  ".join("%08x/%08x" % (L[j], R[j])
                                     for j in range(i, min(i + BLOCK, m))))

    blk = [(R[i] >> 8, (R[i] >> 4) & 1, R[i] & (BLOCK - 1))
           for i in range(r0, r1 + 1)]
    # A stamp is well-formed if its sample field matches its position in
    # the recorded stream once the stream is aligned to a block boundary.
    phase = None
    for p in range(BLOCK):
        if blk[p][2] == 0:
            phase = p
            break
    print("first sample-0 stamp at offset %s in the stamp run" % phase)

    lin = [b * BLOCK + s for b, h, s in blk]      # linear TX index
    step1 = sum(1 for x, y in zip(lin, lin[1:]) if y == x + 1)
    print("STAMP ORDER: +1 on %d of %d transitions (%.4f %%)"
          % (step1, len(lin) - 1, 100.0 * step1 / max(1, len(lin) - 1)))
    d = Counter(y - x for x, y in zip(lin, lin[1:]))
    print("  stamp delta histogram:", d.most_common(10))
    halves = Counter(h for b, h, s in blk)
    print("  buffer half seen: ping %d  pong %d" % (halves[0], halves[1]))
    hb = [h for b, h, s in blk]
    hflip = sum(1 for x, y in zip(hb, hb[1:]) if x != y)
    print("  half flips %d (a clean ping/pong gives one per block = ~%d)"
          % (hflip, len(hb) // BLOCK))
    samp = Counter(s for b, h, s in blk)
    print("  sample-index field histogram:", sorted(samp.items()))

    # ---- the audio channel ------------------------------------------
    nzl = [i for i, v in enumerate(L) if v]
    if not nzl:
        print("no audio captured on the left channel")
        return 2
    s0 = nzl[0]
    best = None
    for off in range(max(0, s0 - 60), s0 + 60):
        ok = sum(1 for i in range(off, min(off + a.steps * a.hold, m))
                 if L[i] == ((((i - off) // a.hold) + 1) << 8))
        if best is None or ok > best[1]:
            best = (off, ok)
    off, ok = best
    n = min(a.steps * a.hold, m - off)
    print("AUDIO: best offset %d, exact %d/%d = %.2f %%"
          % (off, ok, n, 100.0 * ok / n))

    # ---- the joint question -----------------------------------------
    # For every frame that carries BOTH a clean staircase value and a
    # stamp, compare the step the audio came from with the step the
    # stamp says the transmit path was on.
    joint = Counter()
    base = None
    for i in range(max(off, r0), min(off + n, r1 + 1)):
        v = L[i]
        if v == 0 or (v & 0xFF):
            continue
        k_audio = (v >> 8) - 1                    # 0-based step of the audio
        k_frame = (i - off) // a.hold             # step this frame should be
        b, h, s = blk[i - r0]
        if base is None:
            base = b * BLOCK + s - (i - off)
        k_stamp = (b * BLOCK + s - base) // a.hold
        joint[(k_stamp - k_frame, k_audio - k_frame)] += 1
    tot = sum(joint.values())
    stamp_ok = sum(v for (ds, da), v in joint.items() if ds == 0)
    audio_ok = sum(v for (ds, da), v in joint.items() if da == 0)
    print("JOINT over %d clean frames: stamp on-time %d (%.2f %%), "
          "audio on-time %d (%.2f %%)"
          % (tot, stamp_ok, 100.0 * stamp_ok / max(1, tot),
             audio_ok, 100.0 * audio_ok / max(1, tot)))
    print("  (stamp delta, audio delta) in steps, top 12:",
          joint.most_common(12))
    return 0


if __name__ == "__main__":
    sys.exit(main())
