#!/bin/bash
# bisect.sh — build/flash/measure one bisect point with a pass RATE.
#
# Two rules this enforces, both learned the hard way on 2026-08-23:
#
#  1. A build flag is not trusted until it is seen in the RUNNING image.
#     _build_flags (main.asm) encodes every bisect define; the harness
#     peeks it off the part and aborts if it does not match what was
#     asked for. Four DSP4_STUB_* defines once silently failed to reach
#     easm21k and a day of results were all one identical image.
#
#  2. A single alive/dead call is not a measurement. Every point gets N
#     repeats and a pass rate. NODE_LIMIT 5 vs 6 looked decisive on one
#     run each and did not reproduce in either direction.
#
# usage:  [FLAG=val ...] ./bisect.sh <repeats>
set -u
REPEATS="${1:-3}"
cd "$(dirname "$0")"
BENCH=app@192.168.1.219

DSP4_BLOCK_MASK="${DSP4_BLOCK_MASK:-7}"
DSP4_NODE_LIMIT="${DSP4_NODE_LIMIT:-0}"
DSP4_COMMIT_STAGE="${DSP4_COMMIT_STAGE:-2}"
DSP4_NO_IDLE_OVERRIDE="${DSP4_NO_IDLE_OVERRIDE:-0}"
DSP4_STUB_COMPGAIN="${DSP4_STUB_COMPGAIN:-0}"
DSP4_STUB_EXP2="${DSP4_STUB_EXP2:-0}"
DSP4_STUB_LOG2="${DSP4_STUB_LOG2:-0}"
DSP4_STUB_POLY="${DSP4_STUB_POLY:-0}"
DSP4_COMP_NOCVT="${DSP4_COMP_NOCVT:-0}"
DSP4_BLOCK_DECIMATE="${DSP4_BLOCK_DECIMATE:-1}"
DSP4_STRIPS="${DSP4_STRIPS:-0}"
export DSP4_BLOCK_MASK DSP4_NODE_LIMIT DSP4_COMMIT_STAGE DSP4_NO_IDLE_OVERRIDE \
       DSP4_STUB_COMPGAIN DSP4_STUB_EXP2 DSP4_STUB_LOG2 DSP4_STUB_POLY DSP4_COMP_NOCVT DSP4_BLOCK_DECIMATE DSP4_STRIPS

EXPECT=$(( (DSP4_BLOCK_MASK & 0xF) \
        | ((DSP4_NODE_LIMIT & 0xFFF) << 4) \
        | ((DSP4_COMMIT_STAGE & 0x3) << 16) \
        | ((DSP4_NO_IDLE_OVERRIDE & 1) << 18) \
        | ((DSP4_STUB_COMPGAIN & 7) << 19) \
        | ((DSP4_STUB_EXP2 & 1) << 22) \
        | ((DSP4_STUB_LOG2 & 1) << 23) \
        | ((DSP4_STUB_POLY & 1) << 24) \
        | ((DSP4_COMP_NOCVT & 1) << 25) \
        | ((DSP4_BLOCK_DECIMATE & 0x3F) << 26) ))

DSP4_BISECT=0 ./build.sh > /tmp/bisect_build.log 2>&1
if [ "$(grep -ciE '\[Error|Build FAILED' /tmp/bisect_build.log)" -ne 0 ]; then
    echo "BUILD FAILED"; grep -iE '\[Error|error:' /tmp/bisect_build.log | head -5; exit 2
fi
MD5=$(md5sum build/chip1.ldr | cut -c1-12)
read -r ADDR ADDR2 <<<"$(python3 -c "
import re
s=open('build/chip1.map.xml',errors='ignore').read()
def a(n):
    m=re.search(n+r\"' address='(0x[0-9a-fA-F]+)'\", s); return m.group(1) if m else ''
print(a('build_flags'), a('build_flags2'))")"
[ -z "$ADDR" ] || [ -z "$ADDR2" ] && { echo "no _build_flags/_build_flags2 in map"; exit 2; }
EXPECT2=$(( DSP4_STRIPS & 0x3F ))

scp -q build/chip1.ldr build/chip2.ldr ../../../../tools/pi/dsp4_block.py $BENCH:/home/app/dspboot/
scp -q ../../../../tools/pi/dsp4_audio_verdict.py $BENCH:/home/app/dspboot/audio_verdict.py
scp -q bisect_run.sh $BENCH:/home/app/
printf 'mask=%d limit=%d commit=%d noidle=%d stub_cg=%d nocvt=%d  md5=%s  stamp@%s expect=0x%08X\n' \
  "$DSP4_BLOCK_MASK" "$DSP4_NODE_LIMIT" "$DSP4_COMMIT_STAGE" "$DSP4_NO_IDLE_OVERRIDE" \
  "$DSP4_STUB_COMPGAIN" "$DSP4_COMP_NOCVT" "$MD5" "$ADDR" "$EXPECT"
printf '  strips=%d  stamp2@%s expect2=0x%08X\n' "$DSP4_STRIPS" "$ADDR2" "$EXPECT2"

ssh $BENCH "bash /home/app/bisect_run.sh $REPEATS $ADDR $EXPECT $ADDR2 $EXPECT2"
