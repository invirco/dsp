#!/usr/bin/env python3
"""dsp4_dsp_latency.py -- loop latency through a path that is NOT bit-transparent.

`dsp4_loop_latency.py` recovers latency by having every captured word vote
for an offset, which needs the loop to return the stimulus unchanged. That
holds for the LOGIC-only loop (_pisel) and NOT for the through-DSP arm: the
DSP delivers each sample at the right position inside its 8-sample block
but from the wrong block (findings 2026-09-09), so only about a third of
the words are where they belong and a per-word vote finds spurious modes --
which is exactly how the 14,550 figure in the 2026-09-08 note was produced.

The fix is not a better decoder but an honest statistic. A staircase is
played, every candidate offset is SCORED by the fraction of captured frames
that carry the exact expected value, and the answer is reported only with
its margin over the runner-up. A coherent fraction of a third still puts a
sharp peak at the true offset; a spurious mode does not have one, and the
margin says which happened.

    python3 dsp4_dsp_latency.py --reps 20
    python3 dsp4_dsp_latency.py --reps 20 --tag pisel

The absolute number carries the ALSA start offset (arecord is deliberately
started PRE seconds early), so quote DIFFERENCES between arms measured the
same way, not the raw figure.
"""
import argparse
import struct
import subprocess
import sys
import time

# CAPTURE AND PLAYBACK ARE TWO DEVICE NAMES, NOT ONE (S12-10, 2026-09-10).
#
# This module used ONE `DEV` for both arecord and aplay, which is right only
# under the `dsp4-pcm-duplex` overlay. The bench stands on
# `dsp4-pcm-slave`, where the card exposes them SEPARATELY:
#
#   card 0: dsp4pcm, device 0: bcm2835-i2s-dir-hifi   CAPTURE only
#   card 0: dsp4pcm, device 1: bcm2835-i2s-dit-hifi   PLAYBACK only
#
# So `aplay -D hw:dsp4pcm,0` had no playback stream to open. Its failure was
# swallowed -- `capture_output=True` and no return-code check -- and the run
# then scored a capture with no stimulus in it. That is the whole of the null
# signature S12-10 recorded on EVERY image including the shipping control:
# offset 14779 on all 20 reps of both boots, spread 0, coherent 0.0 %.
#
# Measured on the bench 2026-09-10: arecord on device 0 and aplay on device 1
# run CONCURRENTLY under the slave overlay -- 48,000 frames captured while the
# playback ran -- so the two-device form needs no overlay flip and no reboot.
# Both are overridable; DSP4_PCM_DEV sets both at once for a duplex overlay.
import os as _os

_both = _os.environ.get("DSP4_PCM_DEV")
CAP_DEV = _os.environ.get("DSP4_PCM_CAP") or _both or "hw:dsp4pcm,0"
PLAY_DEV = _os.environ.get("DSP4_PCM_PLAY") or _both or "hw:dsp4pcm,1"
RATE = 48000
PRE = 0.30              # arecord head start, seconds
HOLD = 64
STEPS = 1500


def build_stim(path, hold=None, steps=None):
    global HOLD, STEPS
    if hold:
        HOLD = hold
    if steps:
        STEPS = steps
    vals = []
    for k in range(STEPS):
        vals += [(k + 1) << 8] * HOLD
    open(path, "wb").write(b"".join(struct.pack("<ii", v, v) for v in vals))
    return vals


def one_rep(seconds):
    rec = subprocess.Popen(
        ["arecord", "-D", CAP_DEV, "-f", "S32_LE", "-c", "2", "-r", str(RATE),
         "-d", str(seconds), "--period-size=1024", "--buffer-size=8192",
         "-t", "raw", "-q", "/tmp/dsp4_lat_cap.raw"], stderr=subprocess.DEVNULL)
    time.sleep(PRE)
    # THE PLAYBACK'S RETURN CODE IS CHECKED, AND IT WAS NOT. An aplay that
    # cannot open its device exits non-zero in a few milliseconds and the run
    # then scores an empty capture, which is a well-formed wrong answer.
    play = subprocess.run(["aplay", "-D", PLAY_DEV, "-f", "S32_LE", "-c", "2",
                           "-r", str(RATE), "--period-size=1024",
                           "--buffer-size=8192", "-t", "raw", "-q",
                           "/tmp/dsp4_lat.raw"], capture_output=True)
    rec.wait()
    if play.returncode != 0:
        sys.exit('aplay -D %s failed (rc %d): %s\nA capture with no stimulus '
                 'in it is not a latency. Check the PCM overlay and the '
                 'device names (DSP4_PCM_PLAY / DSP4_PCM_CAP).'
                 % (PLAY_DEV, play.returncode,
                    play.stderr.decode(errors='replace').strip()[:200]))
    cap = open("/tmp/dsp4_lat_cap.raw", "rb").read()
    n = len(cap) // 8
    f = struct.unpack("<%di" % (n * 2), cap[:n * 8])
    return [x & 0xFFFFFFFF for x in f[0::2]]


def score(left, lo, hi, stride=4):
    """Exact-match fraction for every candidate offset. Returns sorted list."""
    n = len(left)
    out = []
    for off in range(lo, hi):
        hit = 0
        tot = 0
        i = off
        while i < min(off + STEPS * HOLD, n):
            k = (i - off) // HOLD
            if left[i] == ((k + 1) << 8):
                hit += 1
            tot += 1
            i += stride
        if tot:
            out.append((hit / tot, off))
    out.sort(reverse=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--tag", default="arm")
    ap.add_argument("--lo", type=int, default=14380)
    ap.add_argument("--hi", type=int, default=14780)
    ap.add_argument("--hold", type=int, default=HOLD)
    ap.add_argument("--steps", type=int, default=STEPS)
    args = ap.parse_args()

    build_stim("/tmp/dsp4_lat.raw", args.hold, args.steps)
    seconds = int(STEPS * HOLD / RATE + PRE + 1.5)

    results = []
    for r in range(args.reps):
        left = one_rep(seconds)
        rank = score(left, args.lo, args.hi)
        if not rank:
            print("rep %2d: no candidate offsets scored" % r)
            continue
        best_f, best_off = rank[0]
        # runner-up at least 16 samples away, so the peak's own shoulder
        # is not mistaken for a competitor
        # The score is flat across one plateau of the staircase, so the
        # runner-up has to be a genuinely different alignment: at least two
        # plateaus away, or it is the peak's own shoulder.
        second = next((f for f, o in rank[1:] if abs(o - best_off) >= 2 * HOLD),
                      0.0)
        # Peak WIDTH: how many offsets score within 2% of the best. A real
        # alignment gives about one plateau; a spurious mode gives a smear.
        width = sum(1 for f, o in rank if f >= best_f - 0.02)
        results.append((best_off, best_f, second))
        print("rep %2d: offset %6d  coherent %5.1f%%  runner-up %5.1f%%  "
              "margin x%.1f  peak width %d"
              % (r, best_off, 100 * best_f, 100 * second,
                 best_f / second if second else float("inf"), width))

    if not results:
        return 1
    offs = sorted(o for o, _, _ in results)
    print("\n%s: %d reps" % (args.tag, len(results)))
    print("  offset  min %d  median %d  max %d  spread %d"
          % (offs[0], offs[len(offs) // 2], offs[-1], offs[-1] - offs[0]))
    print("  coherent fraction  min %.1f%%  max %.1f%%"
          % (100 * min(f for _, f, _ in results),
             100 * max(f for _, f, _ in results)))
    worst = min((f / s if s else float("inf")) for _, f, s in results)
    print("  worst margin over the runner-up: x%.1f" % worst)
    if worst < 2.0:
        print("  WARNING: a margin under 2x is not a measurement -- do not quote it")
    # THE MARGIN GUARD ABOVE HAS A HOLE AND IT SWALLOWED A WHOLE ARM (S12-10).
    #
    # When the runner-up is 0.0 the margin is INFINITE, so `worst < 2.0` is
    # false and a run in which NOTHING correlated printed a clean-looking
    # summary. That is exactly S11-6's signature -- offset 14779 on every
    # rep, spread 0, coherent 0.0 % -- and S11-6 fixed the CAUSE (the
    # missing pass-through setup) without closing the reporting hole, so
    # 2026-09-09 it returned the same confident wrong answer on both the
    # candidate and, in the control, on the shipping pair.
    #
    # An offset whose coherent fraction is zero is the best of a flat
    # field. It is not a latency and this tool now refuses to be quoted
    # for one.
    best_coherent = max(f for _, f, _ in results)
    if best_coherent <= 0.0:
        print("  NO VERDICT: the coherent fraction is 0.0%% on every rep -- "
              "nothing in the capture correlates with the stimulus, so the "
              "offset is the best of a flat field and is NOT a latency. "
              "Check the capture path (the through-DSP arm needs the "
              "_maincap bitstream AND a duplex PCM overlay) before "
              "re-running.")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
