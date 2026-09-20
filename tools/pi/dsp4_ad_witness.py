#!/usr/bin/env python3
"""dsp4_ad_witness.py -- ask the LOGIC CPLD whether ad[0..2] are moving (S84).

THE QUESTION THIS RETIRES. Every AK5558 mic lane on this D24 reads EXACT
DIGITAL ZERO -- 32 of 32, rails up, the 595 chain unmuted at gain 63 phantom
off and VERIFIED 200/200, tone off and tone on alike -- while the four AK4619
codec return lanes carry their own dithered floor in the very same pass. S83
measured that on both current bitstreams; S84 measured it again on
`s41_mhrx_pullup_off.15f3ae07dae1`, which the bench's dated flash log says the
part carried from 2026-09-13 to 2026-09-19, the window that contains the day
S54-S58 measured real preamp noise on this unit. Three bitstreams, one answer.

Everything a desk or the SPI link can ask has now been asked. What no session
could ask is the one thing on the far side of the DSP's own bisect: are the
AK5558 OUTPUT PINS moving at all? The CPLD can see them -- ad[0..2] arrive at
U3 and pass through it as a plain wire -- and nothing else on the card can.

So the witness rides the one path off this part that needs no hands: the same
knock-and-answer on the CM4's PCM link that `dsp4_logic_id.py` uses for the
design ID and `dsp4_cdc_witness.py` uses for cdc_o, with a third word pair.

    play  {L = 0xAD075E2<n>, R = ~L}   for lane n = 0, 1, 2
    record for 128 frames:
        L = {5'b0, lane[1:0], ad_ones_last[8:0], 7'b0, ad_ones_max[8:0]}
        R = {0xAD07, ad_toggles_last[8:0], frame_counter[15:9]}

ONE LANE PER KNOCK. Three lanes at cdc precision do not fit in a 64-bit reply,
and a reply at lower precision would not separate "stuck high" from "carrying
data" -- which is the whole question. The lane is echoed back in the left
word and checked here, so a decode that ignored the selector cannot pass.

WHAT THE THREE NUMBERS SEPARATE, which one "is it zero" bit would fuse:

    ones = 0,   toggles = 0    the lane is at exact digital zero
    ones = 256, toggles = 0    the lane is stuck HIGH -- a different fault
    ones > 0,   toggles > 0    the lane is carrying data: the ADC is clocked,
                               out of reset, and converting

`max` is the high-water mark of `ones` since power-up, so a burst of activity
between two knocks is not averaged away by a quiet frame.

WHAT IT CANNOT WITNESS, said plainly. The frame counter is fs8, and
`conv_fs = fs8` is an OUTPUT of this CPLD -- so it witnesses that the clock
generator runs and frames, NOT that the bit clock and frame sync ARRIVE at the
AK5558 pins. U3.142 and U3.141 are the only drivers on those nets and nothing
in a MAX V can see the far end of a net it drives. A dead ad[] therefore does
not by itself separate "the ADCs have no clock" from "the ADCs are held in
reset" from "the ADCs have no analog rail"; it separates all three of those
from "the ADCs are converting and something downstream eats the data", which
is the fork ten sessions could not take. The probe list stands either way.

THE FRAME COUNTER IS THE NEGATIVE CONTROL AND IT IS NOT OPTIONAL. S80's
lesson (finding S80-19) is that an instrument answering static zero on a build
where it cannot work is worse than no instrument at all. Two knocks more than
~11 ms apart MUST return different counter values; if they do not, this tool
says so and refuses to report the zeros as a measurement. `--reps 2` (the
default) is what makes that check possible.

THE OTHER CONTROL IS FREE AND IS TAKEN BY DEFAULT: cdc_o. It is the same
counter on the same sample strobe in the same bitstream, pointed at the codec
lane that IS live. A run where cdc_o answers data and ad[0..2] answer zero has
proved, inside one instrument, that the witness works and the lanes do not.
`--no-cdc` skips it.

    python3 dsp4_ad_witness.py
    python3 dsp4_ad_witness.py --reps 4 --lanes 0,1,2
"""
import argparse
import struct
import subprocess
import sys
import time
from collections import Counter

RATE = 48000
KNOCK3_BASE = 0xAD075E20
AD_MAGIC = 0xAD07
CDC_KNOCK_L = 0xCD0432B4
CDC_KNOCK_R = 0x32FBCD4B
CDC_MAGIC = 0xCD04
BITS_PER_FRAME = 256


def _devices():
    """(playback, capture) device names for the dsp4pcm card, as it is.

    Not assumed to be the same device: under `dsp4-pcm-slave` (the overlay
    this bench stands on) device 0 is capture-only and device 1 is playback,
    and hardcoding one name is how S77 turned "wrong device" into "the CPLD
    does not answer".
    """
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


def knock(kl, kr, seconds=3, knock_frames=2048):
    """Play one knock inside silence, capture the whole thing."""
    pre = RATE // 2
    body = [(kl, kr)] * knock_frames
    frames = [(0, 0)] * pre + body + [(0, 0)] * (RATE - len(body))
    raw = b"".join(struct.pack("<ii", s32(l), s32(r)) for l, r in frames)
    open("/tmp/dsp4_adknock.raw", "wb").write(raw)

    rec = subprocess.Popen(
        ["arecord", "-D", REC_DEV, "-f", "S32_LE", "-c", "2", "-r", str(RATE),
         "-d", str(seconds), "--period-size=1024", "--buffer-size=8192",
         "-t", "raw", "-q", "/tmp/dsp4_adknock_cap.raw"],
        stderr=subprocess.PIPE)
    time.sleep(0.3)
    subprocess.run(["aplay", "-D", PLAY_DEV, "-f", "S32_LE", "-c", "2", "-r",
                    str(RATE), "--period-size=1024", "--buffer-size=8192",
                    "-t", "raw", "-q", "/tmp/dsp4_adknock.raw"],
                   capture_output=True)
    rec.wait()
    cap = open("/tmp/dsp4_adknock_cap.raw", "rb").read()
    n = len(cap) // 8
    f = struct.unpack("<%di" % (n * 2), cap[:n * 8])
    return [x & 0xFFFFFFFF for x in f[0::2]], [x & 0xFFFFFFFF for x in f[1::2]]


def decode_ad(l, r):
    # L = {5'b0, lane[1:0], ones_last[8:0], 7'b0, ones_max[8:0]} -- 5+2+9+7+9.
    # The lane is bits [26:25]. It was read at [25:24] on the first run, which
    # is {lane[0], ones_last[8]}: that happens to equal 0 for lane 0 with any
    # ones count below 256, so lane 0 passed and lanes 1 and 2 reported a
    # mismatch on a part that was answering correctly. The lane echo did its
    # job -- it caught a transcription error, which is what it is for -- but
    # it caught this reader's, so the layout is spelled out here beside the
    # shift.
    return {"lane": (l >> 25) & 0x3,
            "ones": (l >> 16) & 0x1FF, "max": l & 0x1FF,
            "toggles": (r >> 7) & 0x1FF, "frames": r & 0x7F}


def decode_cdc(l, r):
    return {"lane": None,
            "ones": (l >> 16) & 0x1FF, "max": l & 0x1FF,
            "toggles": (r >> 7) & 0x1FF, "frames": r & 0x7F}


def reading(kl, kr, magic, decoder, want_lane=None):
    """One knock, reduced to a median reading.

    The reply lasts 128 Pi frames and the witness updates every 48 kHz frame,
    so the capture holds many readings of a live counter. The median is the
    measurement; the spread is printed, because taking one arbitrary frame and
    calling it the answer is how a jittering counter becomes a clean lie.
    """
    left, right = knock(kl, kr)
    rep = [decoder(l, r) for l, r in zip(left, right) if (r >> 16) == magic]
    if not rep:
        return None, 0
    if want_lane is not None:
        wrong = [d for d in rep if d["lane"] != want_lane]
        if wrong:
            return "LANE_MISMATCH", len(wrong)
    ones = sorted(d["ones"] for d in rep)
    tog = sorted(d["toggles"] for d in rep)
    mid = len(rep) // 2
    d = dict(rep[mid])
    d.update(ones=ones[mid], ones_lo=ones[0], ones_hi=ones[-1],
             toggles=tog[mid], tog_lo=tog[0], tog_hi=tog[-1],
             max=max(x["max"] for x in rep))
    return d, len(rep)


def verdict(d):
    if d["ones"] == 0 and d["toggles"] == 0 and d["max"] == 0:
        return ("EXACT DIGITAL ZERO -- the pin never went high in any frame "
                "since power-up")
    if d["ones"] == BITS_PER_FRAME and d["toggles"] == 0:
        return "STUCK HIGH -- %d ones, no transitions" % d["ones"]
    if d["toggles"] == 0 and d["max"] > 0:
        return ("STATIC at %d ones, no transitions in the last frame "
                "(high-water %d)" % (d["ones"], d["max"]))
    return ("CARRYING DATA -- %d of %d bit periods high, %d transitions, in "
            "the last frame" % (d["ones"], BITS_PER_FRAME, d["toggles"]))


def run_one(name, kl, kr, magic, decoder, reps, want_lane=None):
    """Knock `reps` times; return (seen, ok). Prints as it goes."""
    seen = []
    for rep in range(reps):
        d, n = reading(kl, kr, magic, decoder, want_lane)
        if d is None:
            print("  %s: no reply -- nothing carried the 0x%04X marker. "
                  "Either this bitstream has no such witness or the capture "
                  "path is not reaching the CM4." % (name, magic))
            return seen, False
        if d == "LANE_MISMATCH":
            print("  %s: the part answered about a DIFFERENT lane (%d reply "
                  "frames disagreed). The knock decode and this reader do not "
                  "agree; nothing is reported." % (name, n))
            return seen, False
        seen.append(d)
        print("  %-6s knock %d: ones %3d [%d..%d]  max %3d  toggles %3d "
              "[%d..%d]  frame_ctr %3d  (%d reply frames)"
              % (name, rep + 1, d["ones"], d["ones_lo"], d["ones_hi"],
                 d["max"], d["toggles"], d["tog_lo"], d["tog_hi"],
                 d["frames"], n))
    return seen, True


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.split("\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reps", type=int, default=2,
                    help="knocks per lane; 2 or more makes the frame-counter "
                         "control possible (default 2)")
    ap.add_argument("--lanes", default="0,1,2",
                    help="which ad lanes to ask about (default 0,1,2)")
    ap.add_argument("--no-cdc", action="store_true",
                    help="skip the cdc_o control arm")
    args = ap.parse_args()

    if args.reps < 2:
        print("REFUSING: --reps must be at least 2. One knock cannot check "
              "the frame counter, and zeros without that check are not a "
              "measurement (S80-19).")
        return 2

    lanes = [int(x) for x in args.lanes.split(",") if x.strip() != ""]
    if any(l not in (0, 1, 2) for l in lanes):
        print("REFUSING: lanes are 0, 1 and 2. AD3 carries no converter on "
              "the D24 and is not a knock.")
        return 2

    ok = True
    results = {}

    if not args.no_cdc:
        print("cdc_o (the CONTROL: the codec lane S83/S84 measured live)")
        seen, good = run_one("cdc_o", CDC_KNOCK_L, CDC_KNOCK_R, CDC_MAGIC,
                             decode_cdc, args.reps)
        if good:
            results["cdc_o"] = seen
            print("    -> %s" % verdict(seen[-1]))
        else:
            ok = False
        print()

    for lane in lanes:
        kl = KNOCK3_BASE | lane
        kr = (~kl) & 0xFFFFFFFF
        print("ad[%d]  (knock L=0x%08X R=0x%08X)" % (lane, kl, kr))
        seen, good = run_one("ad[%d]" % lane, kl, kr, AD_MAGIC, decode_ad,
                             args.reps, want_lane=lane)
        if good:
            results["ad[%d]" % lane] = seen
            print("    -> %s" % verdict(seen[-1]))
        else:
            ok = False
        print()

    # ---- the negative control, per arm ----
    for name, seen in results.items():
        ctrs = {d["frames"] for d in seen}
        if len(ctrs) == 1:
            print("!! %s: THE FRAME COUNTER DID NOT MOVE -- %d on every "
                  "knock." % (name, seen[0]["frames"]))
            print("   The witness is not advancing, so its zeros mean "
                  "nothing and are NOT reported as a measurement.")
            ok = False
        else:
            print("   %s: frame counter advanced %s -- the witness is live."
                  % (name, " -> ".join(str(d["frames"]) for d in seen)))

    # ---- the two-sided verdict, which is the point of the control arm ----
    if ok and not args.no_cdc and "cdc_o" in results:
        cdc = results["cdc_o"][-1]
        ads = [results[k][-1] for k in sorted(results) if k != "cdc_o"]
        cdc_live = cdc["toggles"] > 0
        ad_dead = all(d["ones"] == 0 and d["toggles"] == 0 and d["max"] == 0
                      for d in ads)
        print()
        if cdc_live and ad_dead:
            print("VERDICT: cdc_o is carrying data and ad[%s] are at exact "
                  "digital zero, in the SAME bitstream, on the SAME sample "
                  "strobe, in the same run."
                  % ",".join(str(l) for l in lanes))
            print("  The instrument is therefore proved working by the arm "
                  "that answers, and the AK5558 outputs are not moving. The "
                  "fault is at or before those pins -- the ADCs' own clock "
                  "inputs, their reset/PDN, or their analog supply -- and NOT "
                  "downstream in the CPLD, the slot map, the SPORT or the "
                  "graph, all of which are carrying the codec's data past it.")
        elif cdc_live and not ad_dead:
            print("VERDICT: ad lanes are MOVING. The lanes are alive at the "
                  "CPLD and the zero the DSP reads is downstream of this "
                  "part -- slot map, SPORT, DMA or graph.")
        elif not cdc_live:
            print("VERDICT: the cdc_o control is NOT carrying data either, so "
                  "this run cannot say the witness works. Re-take it with the "
                  "codec live before reading anything into the ad lanes.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
