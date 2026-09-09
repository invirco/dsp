#!/usr/bin/env python3
"""dsp4_logic_id.py -- read the LOGIC CPLD's design-ID register off the part.

Until 2026-09-09 "which bitstream is running" cost a measurement: flash,
then infer identity from how the capture behaves (findings S5-9). The
design now carries a read-only ID, and this is the reader.

There is exactly one path off a MAX V that needs no hands: the CM4's PCM
link. So the register is read by KNOCKING on it --

    play  {L = 0xD5D51D1D, R = 0x2A2AE2E2}   (R is the exact inverse of L)
    record L = design_id, R = 0xD594<cfg_bits>, for 128 frames

-- and the reply is checked against the artifact's manifest. The magic
0xD594 in the top half of the right channel is what distinguishes a reply
from audio that happens to be playing.

    python3 dsp4_logic_id.py
    python3 dsp4_logic_id.py --expect ae1ac4a9

Exit status is 0 only if a reply was found (and matched --expect, if given).
"""
import argparse
import struct
import subprocess
import sys
import time
from collections import Counter

DEV = "hw:dsp4pcm,0"
RATE = 48000
KNOCK_L = 0xD5D51D1D
KNOCK_R = 0x2A2AE2E2
ID_MAGIC = 0xD594

CFG_NAMES = [(1 << 0, "loopback"), (1 << 1, "pi_selftest"),
             (1 << 2, "pi_maincap"), (1 << 3, "pi_tdm8"),
             (1 << 4, "SHIPPING")]


def s32(v):
    return v - (1 << 32) if v >> 31 else v


def knock(seconds=3, knock_frames=2048):
    """Play the knock inside silence, capture the whole thing."""
    pre = RATE // 2
    body = [(KNOCK_L, KNOCK_R)] * knock_frames
    frames = [(0, 0)] * pre + body + [(0, 0)] * (RATE - len(body))
    raw = b"".join(struct.pack("<ii", s32(l), s32(r)) for l, r in frames)
    open("/tmp/dsp4_knock.raw", "wb").write(raw)

    rec = subprocess.Popen(
        ["arecord", "-D", DEV, "-f", "S32_LE", "-c", "2", "-r", str(RATE),
         "-d", str(seconds), "--period-size=1024", "--buffer-size=8192",
         "-t", "raw", "-q", "/tmp/dsp4_knock_cap.raw"], stderr=subprocess.PIPE)
    time.sleep(0.3)
    subprocess.run(["aplay", "-D", DEV, "-f", "S32_LE", "-c", "2", "-r",
                    str(RATE), "--period-size=1024", "--buffer-size=8192",
                    "-t", "raw", "-q", "/tmp/dsp4_knock.raw"],
                   capture_output=True)
    rec.wait()
    cap = open("/tmp/dsp4_knock_cap.raw", "rb").read()
    n = len(cap) // 8
    f = struct.unpack("<%di" % (n * 2), cap[:n * 8])
    return [x & 0xFFFFFFFF for x in f[0::2]], [x & 0xFFFFFFFF for x in f[1::2]]


def describe(cfg):
    on = [name for bit, name in CFG_NAMES if cfg & bit]
    return ", ".join(on) if on else "(no flags)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--expect", help="design id in hex, e.g. ae1ac4a9")
    ap.add_argument("--reps", type=int, default=1)
    args = ap.parse_args()

    ok = True
    for rep in range(args.reps):
        left, right = knock()
        replies = [(l, r) for l, r in zip(left, right)
                   if (r >> 16) == ID_MAGIC]
        if not replies:
            print("no reply: nothing in the capture carried the 0x%04X marker."
                  % ID_MAGIC)
            print("  Either the bitstream predates the ID register, or the")
            print("  capture path is not reaching the CM4 at all.")
            ok = False
            continue
        c = Counter(replies)
        (did, cfgw), n = c.most_common(1)[0]
        cfg = cfgw & 0xFFFF
        print("design_id: 32'h%08x   cfg_bits: 16'h%04X   %s"
              % (did, cfg, describe(cfg)))
        print("  reply frames %d of %d captured, %d distinct reply words"
              % (n, len(left), len(c)))
        if len(c) != 1:
            print("  WARNING: the reply was not stable -- %s"
                  % ", ".join("%08x/%08x x%d" % (a, b, k)
                              for (a, b), k in c.most_common(4)))
            ok = False
        if args.expect is not None:
            want = int(args.expect, 16)
            if did == want:
                print("  MATCHES --expect %08x" % want)
            else:
                print("  MISMATCH: expected %08x, part says %08x" % (want, did))
                ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
