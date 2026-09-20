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

S85: TWO EDGES, ONE PASS. S84 answered the question it was built for and
opened a bigger one -- the pins move and the DSP reads exact zero -- and S84-6
named the one thing the `driveall` proof never covered. Under `driveall` the
lane is a register output of the CPLD launched on its own `bck8_launch`.
The AK5558 lanes are not: they are launched by three converters off
`conv_bck`, which leaves U3.142, crosses a five-33R-tap star, is re-buffered
on the Analog board, clocks the converter, and comes back on `ad[n]` -- and
then crosses U3 combinationally (`i_dspa[n] = ad[n]`, not a register anywhere
in it) to the DSP's pin. So the witness now runs SIX banks, the same three
lanes counted on both bck8 edges at once, and the knock's bit 2 chooses which
bank answers:

    play  {L = 0xAD075E2<b>, R = ~L}     b[1:0] = lane, b[2] = edge
        b = 0,1,2   lane 0,1,2 counted on bck8_sample  (S84's three knocks,
                    unchanged, so the S84 numbers are directly comparable)
        b = 4,5,6   lane 0,1,2 counted on bck8_launch  (S85)
    L = {3'b0, bck_ratio_ok, edge, lane[1:0], ones_last[8:0],
         7'b0, ones_max[8:0]}

Both banks count the SAME pass -- they are not two runs -- so the comparison
is a measurement and not a repeatability question. They are 40.69 ns apart on
an 81.38 ns bit period.

    the banks AGREE           the lane is stable across at least half a bit
                              period; the CPLD samples it correctly and the
                              loss is downstream of this part
    the banks DISAGREE        the data transitions between the two edges, so
                              one of them sits in the converter's launch
                              shadow: the phase is the fault and the fix is
                              in the LOGIC

`bck_ratio_ok` is the generator's own ratio check: 1 while every conv_fs frame
since power-up has held exactly 256 bck8 periods. It still says nothing about
arrival at the AK5558 pins -- nothing in a MAX V can -- but it is the one
thing that would make every `ones` number here a count out of the wrong 256.

    python3 dsp4_ad_witness.py
    python3 dsp4_ad_witness.py --reps 4 --lanes 0,1,2
    python3 dsp4_ad_witness.py --edges sample        # the S84 reading only
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
EDGE_NAME = {0: "sample", 1: "launch"}
# Half a TDM8 bit period: the two banks are this far apart, on a bit period of
# 81.38 ns. Printed beside the comparison so the number the reading has to be
# argued against is on the page and not in someone's head.
BCK8_HALF_NS = 40.69


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
    # L = {3'b0, bck_ratio_ok, edge, lane[1:0], ones_last[8:0], 7'b0,
    #      ones_max[8:0]} -- 3+1+1+2+9+7+9.
    # The lane is bits [26:25]. It was read at [25:24] on the first run, which
    # is {lane[0], ones_last[8]}: that happens to equal 0 for lane 0 with any
    # ones count below 256, so lane 0 passed and lanes 1 and 2 reported a
    # mismatch on a part that was answering correctly. The lane echo did its
    # job -- it caught a transcription error, which is what it is for -- but
    # it caught this reader's, so the layout is spelled out here beside the
    # shift. S85 adds the edge at [27] and the ratio bit at [28] ABOVE the
    # lane, deliberately: everything S84 decoded is where S84 left it.
    return {"lane": (l >> 25) & 0x3, "edge": (l >> 27) & 0x1,
            "bck_ok": (l >> 28) & 0x1,
            "ones": (l >> 16) & 0x1FF, "max": l & 0x1FF,
            "toggles": (r >> 7) & 0x1FF, "frames": r & 0x7F}


def decode_cdc(l, r):
    return {"lane": None, "edge": None, "bck_ok": None,
            "ones": (l >> 16) & 0x1FF, "max": l & 0x1FF,
            "toggles": (r >> 7) & 0x1FF, "frames": r & 0x7F}


def reading(kl, kr, magic, decoder, want_lane=None, want_edge=None):
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
    if want_edge is not None:
        wrong = [d for d in rep if d["edge"] != want_edge]
        if wrong:
            return "EDGE_MISMATCH", len(wrong)
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


def run_one(name, kl, kr, magic, decoder, reps, want_lane=None,
            want_edge=None):
    """Knock `reps` times; return (seen, ok). Prints as it goes."""
    seen = []
    for rep in range(reps):
        d, n = reading(kl, kr, magic, decoder, want_lane, want_edge)
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
        if d == "EDGE_MISMATCH":
            print("  %s: the part answered about the OTHER sampling edge (%d "
                  "reply frames disagreed). Either this bitstream predates "
                  "S85 -- in which case bit 2 of the knock is part of the "
                  "fixed pattern and no knock with it set is answered at all "
                  "-- or the decode is wrong. Nothing is reported."
                  % (name, n))
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
    ap.add_argument("--edges", default="both",
                    choices=("both", "sample", "launch"),
                    help="which counter bank(s) to ask for. 'sample' is "
                         "exactly S84's reading; 'both' also asks the "
                         "bck8_launch bank and compares them (default both)")
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

    edges = {"both": [0, 1], "sample": [0], "launch": [1]}[args.edges]

    for lane in lanes:
        for edge in edges:
            kl = KNOCK3_BASE | (edge << 2) | lane
            kr = (~kl) & 0xFFFFFFFF
            name = "ad[%d]/%s" % (lane, EDGE_NAME[edge])
            print("%-14s (knock L=0x%08X R=0x%08X)" % (name, kl, kr))
            seen, good = run_one(name, kl, kr, AD_MAGIC, decode_ad,
                                 args.reps, want_lane=lane, want_edge=edge)
            if good:
                results[name] = seen
                print("    -> %s" % verdict(seen[-1]))
                if seen[-1].get("bck_ok") == 0:
                    print("    !! bck_ratio_ok is CLEAR: at least one conv_fs "
                          "frame since power-up did not hold exactly 256 bck8 "
                          "periods. Every count above is out of an unknown "
                          "denominator; fix that before reading anything into "
                          "them.")
                    ok = False
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

    # ---- THE EDGE COMPARISON, which is the point of the second bank ----
    #
    # The two banks counted the SAME pass, so any difference between them is
    # the lane changing between the two edges and nothing else -- not drift,
    # not a different run, not a different bitstream. Printed per lane with
    # the deltas, because "they disagree" without the size of the
    # disagreement does not locate anything.
    if args.edges == "both":
        print()
        print("THE EDGE COMPARISON -- both banks counted the same pass, "
              "%.2f ns apart" % BCK8_HALF_NS)
        # THE VERDICT IS ON `toggles`, AND `ones` IS CORROBORATION. The two
        # banks COUNT concurrently but are READ by separate knocks seconds
        # apart, so `ones` -- which is what the converter happened to be
        # emitting -- drifts with the content between the two readings and a
        # few counts of difference mean nothing. `toggles` is the statistic
        # that MUST move if a sampling point sits on a data transition: half
        # those bit periods would resolve arbitrarily and the transition
        # count could not come back identical. S85 measured `toggles`
        # identical on every lane in every rail state while `ones` wandered
        # by up to 5 on ad[0], which is exactly the asymmetry this rule
        # exists to read correctly.
        #
        # The median ACROSS KNOCKS, not the last knock: one knock is one
        # reading of a live counter and the run already pays for `--reps`.
        def med(seen, key):
            v = sorted(d[key] for d in seen)
            return v[len(v) // 2]

        agree, disagree = [], []
        for lane in lanes:
            a = results.get("ad[%d]/sample" % lane)
            b = results.get("ad[%d]/launch" % lane)
            if not a or not b:
                print("  ad[%d]: one of the two banks did not answer -- no "
                      "comparison" % lane)
                continue
            a_ones, a_tog = med(a, "ones"), med(a, "toggles")
            b_ones, b_tog = med(b, "ones"), med(b, "toggles")
            d_ones, d_tog = b_ones - a_ones, b_tog - a_tog
            print("  ad[%d]  sample: ones %3d toggles %3d | "
                  "launch: ones %3d toggles %3d | "
                  "delta ones %+d toggles %+d   (median of %d/%d knocks)"
                  % (lane, a_ones, a_tog, b_ones, b_tog, d_ones, d_tog,
                     len(a), len(b)))
            if abs(d_tog) <= 2:
                agree.append(lane)
            else:
                disagree.append(lane)
            if abs(d_ones) > 8:
                print("       (ones differs by %+d between the two READINGS; "
                      "the banks count together but are knocked separately, "
                      "so this is content drift unless toggles moved too)"
                      % d_ones)
        print()
        if disagree:
            print("VERDICT ON THE PHASE: lane(s) %s return DIFFERENT TRANSITION "
                  "COUNTS on the two edges."
                  % ", ".join("ad[%d]" % l for l in disagree))
            print("  Both banks saw the same 256 bit periods of the same "
                  "frames. A lane whose count depends on WHEN in the bit "
                  "period it is sampled is a lane whose data is not stable "
                  "across the window the DSP samples in -- the converter's "
                  "launch phase, plus the round trip out and back, has moved "
                  "the data edge onto one of these two sampling points. That "
                  "is a LOGIC fix: capture the lane on the edge it is valid "
                  "on and re-launch it to the DSP.")
        elif agree:
            print("VERDICT ON THE PHASE: lane(s) %s return the SAME transition "
                  "count on both edges."
                  % ", ".join("ad[%d]" % l for l in agree))
            print("  The data is stable across at least the 40.69 ns between "
                  "them, so neither sampling point is sitting on a data "
                  "transition and the phase at the CPLD is not the fault. "
                  "What that does NOT clear is the path from this part's ad "
                  "pin to the DSP's own sampling edge: `i_dspa[n] = ad[n]` is "
                  "combinational, so the DSP samples the converter's data "
                  "through U3's pin-to-pin delay on top of the round trip, "
                  "and nothing here witnesses that.")

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
