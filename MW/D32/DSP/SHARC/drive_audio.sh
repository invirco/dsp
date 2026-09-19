#!/bin/bash
# drive_audio.sh — the DRIVEN-capacity stimulus, on the BENCH side.
#
# Runs on the CM4. Plays a full-scale stream into the PCM link, which the
# `driveall` LOGIC bitstream broadcasts across all eight TDM8 slots of every
# DSPA input lane — so all 46 of chip 1's input kernels see signal and the
# DSP pays NOTHING for the stimulus. That is the whole point: S18 measured
# `DSP4_PROFILE_SIGNAL`'s in-kernel synthesis at 41 points of chip 1's budget
# (71.7 % silent against 113 % driven on a chip whose real cost is
# signal-independent), so every number taken with it on chip 1 was the
# instrument.
#
# THE WAVEFORM IS A SQUARE, and that is a choice, not a default. |x| is then
# CONSTANT, so every dynamics node is above its threshold in every sample of
# every block and the regime does not modulate between blocks the way a
# sine's would. Right is the inverse of left, so a lane or slot that is
# silently reading its neighbour shows up as a cancellation rather than
# hiding behind two identical channels.
#
# IT IS NOT FULL SCALE, AND THAT IS THE WHOLE STORY OF S77's FIRST THREE
# HOURS. It was `(1<<31)-1` from S19 until 2026-09-19, when every driven row
# of the session came back with the regime NOT PROVEN -- chip 1's dynamics on
# their cheap branch, 15 of 48 envelopes nominally "live" at 3e-6 and the
# ceiling reading 90 % where the record says 119 %. The stimulus was
# arriving: measured on the part, what the CM4 plays reaches chip 1's SPORT
# RX DMA buffer EXACTLY and SHIFTED ONE BIT LEFT --
#
#     played 0x40000000 -> rx 0x80000000      played 0x00100000 -> rx 0x00200000
#     played 0x10000000 -> rx 0x20000000      played 0x00000004 -> rx 0x00000008
#
# -- so a full-scale square at 0x7FFFFFFF wraps to 0x00000002 and 0xFFFFFFFE.
# The part was being driven at 2 LSB, which is silence wearing a driven
# label: exactly the class of fault this instrument exists to prevent, one
# layer below where it was looking. The regime proof CAUGHT it (NOT PROVEN on
# every row) -- what nobody had was a reason.
#
# So the amplitude is a quarter of full scale (-12 dBFS at the CM4, -6 dBFS
# at the part after the shift), which leaves a bit of headroom against the
# shift instead of standing on the edge of it, and is the level
# `dsp4_dyn_witness.py` already predicts its compressor reading from. Every
# dynamics node in the driven configuration sits at a -60 dB threshold, so
# 18 dB of stimulus either way does not change which BRANCH the graph is on
# -- which is what the row measures -- but it does change the compressor's
# gain-reduction arithmetic, so rows below and above this change are not
# interchangeable to the cycle. Where the shift comes from is NOT explained
# here: it is present on both driveall bases (14df62d98a4d and the pre-S34
# 907492a607bd) and absent from the CPLD-internal pisel loop, which returns
# `in << 0` (S77 finding).
#
# IT IS GENERATED, NOT PLAYED FROM A FILE, so the stream has NO GAP. A
# looped `aplay file` restarts every pass, and a restart is tens of
# milliseconds of silence — enough to drop every envelope on the part and
# put the graph back on its cheap branch in the middle of a dwell.
#
#   drive_audio.sh start     start the gapless stream in the background
#   drive_audio.sh stop      stop and confirm the device is idle
#   drive_audio.sh status    playing or idle
#
# PLAYBACK IS DEVICE 1 OF THE dsp4pcm CARD (S17-2). Device 0 is CAPTURE under
# the slave overlay and has no playback stream at all; `aplay` on it fails, and
# `latency.sh` swallowed that failure for two sessions and reported a null
# signature on every image. The device is named here once, and the format is
# PROBED with a one-second file before the endless stream is trusted, so a
# refused format is an error here instead of a zero-amplitude capacity row.
#
# BY NAME, NOT BY INDEX (S77). This said `hw:0,1` from S17 until 2026-09-19,
# when the first driven row of the session died with `aplay: audio open error:
# No such file or directory` -- the CM4 had come up with the two vc4-hdmi
# cards at 0 and 2 and `dsp4pcm` at 1, so `hw:0,1` addressed an HDMI card's
# nonexistent second device. Nothing about the card, the overlay or the
# bitstream had changed; ALSA card ORDER is not stable across boots, and an
# index written into a script is a bench-state assumption exactly like the
# stale symbol map in S10-9. The card is resolved by its name here and the
# index never appears. `DEV=` still overrides for a one-off.
set -u
DEV="${DEV:-hw:CARD=dsp4pcm,DEV=1}"
FREQ="${FREQ:-400}"
# Peak sample value. A quarter of full scale: see the note above.
AMP="${AMP:-536870912}"
PIDF=/tmp/dsp4_drive.pid
GEN=/tmp/dsp4_drive_gen.py
PROBE=/tmp/dsp4_drive_probe_$AMP.wav

write_gen() {
    cat > "$GEN" <<'PY'
import struct, sys
rate, freq = 48000, float(sys.argv[1])
period = rate / freq
# One second of square, built once and written for ever.
buf = bytearray()
full = int(sys.argv[2])
for i in range(rate):
    v = full if (i % period) < (period / 2) else -full
    buf += struct.pack('<ii', v, -v)
buf = bytes(buf)
out = sys.stdout.buffer
try:
    while True:
        out.write(buf)
        out.flush()
except (BrokenPipeError, KeyboardInterrupt):
    pass
PY
    [ -f "$PROBE" ] && return 0
    python3 - "$PROBE" "$FREQ" "$AMP" <<'PY'
import struct, sys, wave
path, freq = sys.argv[1], float(sys.argv[2])
rate = 48000
period = rate / freq
full = int(sys.argv[3])
frames = bytearray()
for i in range(rate):
    v = full if (i % period) < (period / 2) else -full
    frames += struct.pack('<ii', v, -v)
w = wave.open(path, 'wb')
w.setnchannels(2); w.setsampwidth(4); w.setframerate(rate)
w.writeframes(bytes(frames)); w.close()
PY
}

case "${1:-status}" in
start)
    write_gen
    if [ -f "$PIDF" ] && kill -0 "$(cat $PIDF)" 2>/dev/null; then
        echo "drive_audio: already running (pid $(cat $PIDF))"; exit 0
    fi
    if ! timeout 15 aplay -q -D "$DEV" "$PROBE" >/tmp/dsp4_drive.probe 2>&1; then
        echo "drive_audio: aplay REFUSED $DEV"; sed 's/^/  /' /tmp/dsp4_drive.probe; exit 3
    fi
    nohup bash -c "python3 '$GEN' $FREQ $AMP | aplay -q -D '$DEV' -f S32_LE -c 2 -r 48000 -t raw" \
        >/tmp/dsp4_drive.log 2>&1 &
    echo $! > "$PIDF"
    sleep 3
    if ! pgrep -f "aplay -q -D $DEV -f S32_LE" >/dev/null; then
        echo "drive_audio: stream died"; sed 's/^/  /' /tmp/dsp4_drive.log; exit 3
    fi
    echo "drive_audio: streaming ${FREQ} Hz square, peak $AMP, on $DEV (pid $(cat $PIDF))"
    ;;
stop)
    [ -f "$PIDF" ] && { kill "$(cat $PIDF)" 2>/dev/null; rm -f "$PIDF"; }
    pkill -f "aplay -q -D $DEV" 2>/dev/null
    pkill -f "$GEN" 2>/dev/null
    sleep 1
    if pgrep -f "aplay -q -D $DEV" >/dev/null; then
        echo "drive_audio: STILL PLAYING"; exit 1
    fi
    echo "drive_audio: stopped"
    ;;
status)
    if pgrep -f "aplay -q -D $DEV" >/dev/null; then echo "drive_audio: PLAYING"
    else echo "drive_audio: idle"; fi
    ;;
*)
    echo "usage: $0 start|stop|status" >&2; exit 2 ;;
esac
