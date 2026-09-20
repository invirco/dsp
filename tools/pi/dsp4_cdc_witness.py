#!/usr/bin/env python3
"""dsp4_cdc_witness.py -- ask the LOGIC CPLD what CDC_O is actually carrying (S81).

THE QUESTION THIS RETIRES. The D24's converters have been dark since S71.
S80 bisected the fault to UPSTREAM OF THE CPLD: under the `driveall`
bitstream every slot of `i_dspa[4]` carries the stimulus at exactly
-6.02 dBFS, so the SHARC's I4 pin, its SPORT, the RX DMA, the slot map and
the graph buffers are good end to end -- and on the shipping bitstream the
same lane reads exact digital zero. What nobody could say without a scope on
the converter board was whether `cdc_o`, the codec's own data return, is
carrying anything at all. The CPLD can see that pin. It could not say so,
because a MAX V has no readback and the TEST pins land on a DNP header.

So the witness rides the ONE path off this part that needs no hands: the
same knock-and-answer on the CM4's PCM link that `dsp4_logic_id.py` uses for
the design ID, with a different word pair.

    play  {L = 0xCD0432B4, R = 0x32FBCD4B}   (R is the exact inverse of L)
    record for 128 frames:
        L = {7'b0, cdc_ones_last[8:0], 7'b0, cdc_ones_max[8:0]}
        R = {0xCD04, cdc_toggles_last[8:0], frame_counter[15:9]}

WHAT THE THREE NUMBERS SEPARATE, which one "is it zero" bit would fuse:

    ones = 0,   toggles = 0    the lane is at exact digital zero
    ones = 256, toggles = 0    the lane is stuck HIGH -- a different fault
    ones > 0,   toggles > 0    the lane is carrying data

`max` is the high-water mark of `ones` since power-up, so a single burst
between two knocks is not averaged away by a quiet frame.

WHAT IT CANNOT WITNESS, said plainly because the question it was asked was
"BCLK/FS present at the codec": conv_bck and conv_fs are OUTPUTS of the
CPLD. It knows it generates them; it cannot know they ARRIVE, and nothing in
a MAX V can. A static cdc_o therefore does not by itself separate "the codec
has no clock" from "the codec has a clock and is not converting". Taken with
the S81 SPI read arm -- which has the codec answering its own register image
with RSTN set and PMAD1/2 on -- it narrows to the clock/frame pair reaching
the part, or the analog rails to it.

THE FRAME COUNTER IS THE NEGATIVE CONTROL AND IT IS NOT OPTIONAL. S80's
lesson (`dsp4_inscan.py`, finding S80-19) is that an instrument which answers
static zero on a build where it cannot work is worse than no instrument at
all. Two knocks more than ~11 ms apart MUST return different counter values;
if they do not, this tool says so and refuses to report the zeros as a
measurement. `--reps 2` (the default) is what makes that check possible.

    python3 dsp4_cdc_witness.py
    python3 dsp4_cdc_witness.py --reps 4
"""
import argparse
import struct
import subprocess
import sys
import time
from collections import Counter

RATE = 48000
KNOCK_L = 0xCD0432B4
KNOCK_R = 0x32FBCD4B
CDC_MAGIC = 0xCD04
BITS_PER_FRAME = 256            # TDM8 x 32-bit slots at the BCK8 sample edge


def _devices():
    """(playback, capture) device names for the dsp4pcm card, as it is.

    Same probe as dsp4_logic_id.py and for the same reason (S77): device 0 is
    capture-only under `dsp4-pcm-slave` and playback lives on device 1, so a
    hard-coded pair reports "no reply" on a CPLD that answers perfectly."""
    def probe(cmd):
        try:
            out = subprocess.run([cmd, "-l"], capture_output=True,
                                 text=True).stdout
        except OSError:
            return None
        for line in out.splitlines():
            if "dsp4pcm" in line and "device" in line:
                try:
                    return "hw:dsp4pcm,%d" % int(
                        line.split("device", 1)[1].split(":")[0].strip())
                except (ValueError, IndexError):
                    continue
        return None
    return probe("aplay") or "hw:dsp4pcm,0", probe("arecord") or "hw:dsp4pcm,0"


PLAY_DEV, REC_DEV = _devices()


def s32(v):
    return v - (1 << 32) if v >> 31 else v


def knock(seconds=3, knock_frames=2048):
    """Play the knock inside silence, capture the whole thing."""
    pre = RATE // 2
    body = [(KNOCK_L, KNOCK_R)] * knock_frames
    frames = [(0, 0)] * pre + body + [(0, 0)] * (RATE - len(body))
    raw = b"".join(struct.pack("<ii", s32(l), s32(r)) for l, r in frames)
    open("/tmp/dsp4_cdc_knock.raw", "wb").write(raw)

    rec = subprocess.Popen(
        ["arecord", "-D", REC_DEV, "-f", "S32_LE", "-c", "2", "-r", str(RATE),
         "-d", str(seconds), "--period-size=1024", "--buffer-size=8192",
         "-t", "raw", "-q", "/tmp/dsp4_cdc_cap.raw"], stderr=subprocess.PIPE)
    time.sleep(0.3)
    subprocess.run(["aplay", "-D", PLAY_DEV, "-f", "S32_LE", "-c", "2", "-r",
                    str(RATE), "--period-size=1024", "--buffer-size=8192",
                    "-t", "raw", "-q", "/tmp/dsp4_cdc_knock.raw"],
                   capture_output=True)
    rec.wait()
    cap = open("/tmp/dsp4_cdc_cap.raw", "rb").read()
    n = len(cap) // 8
    f = struct.unpack("<%di" % (n * 2), cap[:n * 8])
    return [x & 0xFFFFFFFF for x in f[0::2]], [x & 0xFFFFFFFF for x in f[1::2]]


def decode(l, r):
    # L = {7'd0, cdc_ones_last[8:0], 7'd0, cdc_ones_max[8:0]} -- the LAST
    # frame is the HIGH half, the high-water mark the low half. Reading them
    # the other way round is silent: both are small non-negative counts and a
    # swapped pair still looks like a plausible reading.
    return {"ones": (l >> 16) & 0x1FF, "max": l & 0x1FF,
            "toggles": (r >> 7) & 0x1FF, "frames": r & 0x7F}


def one_reading():
    """Aggregate the WHOLE reply window, never one frame of it.

    The reply lasts 128 Pi frames and the witness updates every 48 kHz frame,
    so the 128 recorded words are 128 DIFFERENT readings -- which is the
    point, and which is also why taking the modal word (what the design-ID
    reader does, correctly, for a constant register) would hand back one
    arbitrary frame and call it the measurement. `ones` and `toggles` are
    reported as min/median/max across the window; `max` and the frame counter
    are read from the last frame, the first being a running high-water mark
    and the second the liveness control."""
    left, right = knock()
    rep = [decode(l, r) for l, r in zip(left, right) if (r >> 16) == CDC_MAGIC]
    if not rep:
        return None, 0, None
    ones = sorted(d["ones"] for d in rep)
    tog = sorted(d["toggles"] for d in rep)
    mid = len(rep) // 2
    d = dict(rep[-1])
    d.update(ones=ones[mid], ones_lo=ones[0], ones_hi=ones[-1],
             toggles=tog[mid], tog_lo=tog[0], tog_hi=tog[-1],
             max=max(x["max"] for x in rep))
    return d, len(rep), None


def verdict(d):
    if d["ones"] == 0 and d["toggles"] == 0 and d["max"] == 0:
        return ("CDC_O IS AT EXACT DIGITAL ZERO -- never once high since the "
                "CPLD powered up.")
    if d["ones"] == BITS_PER_FRAME and d["toggles"] == 0:
        return "CDC_O IS STUCK HIGH -- not silence, a different fault."
    if d["toggles"] == 0 and d["max"] > 0:
        return ("CDC_O is static NOW but was active earlier (max %d) -- the "
                "lane stopped rather than never started." % d["max"])
    return ("CDC_O IS CARRYING DATA: %d of %d bit periods high, %d "
            "transitions, in the last frame." % (d["ones"], BITS_PER_FRAME,
                                                 d["toggles"]))


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=2,
                    help="knocks to take; 2 or more enables the liveness "
                         "check on the frame counter (default 2)")
    a = ap.parse_args()

    seen = []
    for rep in range(a.reps):
        d, n, c = one_reading()
        if d is None:
            print("no reply: nothing in the capture carried the 0x%04X marker."
                  % CDC_MAGIC)
            print("  Either the flashed bitstream predates the CDC_O witness")
            print("  (S81), or the capture path is not reaching the CM4.")
            return 1
        seen.append(d)
        print("knock %d: ones %3d [%d..%d]  max %3d  toggles %3d [%d..%d]  "
              "frame_ctr %3d  (%d reply frames)"
              % (rep + 1, d["ones"], d["ones_lo"], d["ones_hi"], d["max"],
                 d["toggles"], d["tog_lo"], d["tog_hi"], d["frames"], n))
        if rep + 1 < a.reps:
            time.sleep(0.25)

    # The instrument's own negative control, before any conclusion is drawn.
    if len(seen) > 1:
        ctrs = {d["frames"] for d in seen}
        if len(ctrs) == 1:
            print()
            print("THE WITNESS IS DEAD, NOT THE LANE. The frame counter read "
                  "%d on every knock;" % seen[0]["frames"])
            print("  it advances every 10.7 ms, so identical values across "
                  "knocks a quarter of a")
            print("  second apart mean the counter is not running. NOTHING "
                  "above is a measurement.")
            return 1
        print()
        print("liveness: frame counter moved across knocks (%s) -- the "
              "witness is running."
              % " -> ".join(str(d["frames"]) for d in seen))

    print()
    print(verdict(seen[-1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
