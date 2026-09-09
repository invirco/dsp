#!/usr/bin/env bash
# build.sh — DSP4 LOGIC CPLD build (map -> fit -> sta -> asm -> pof/svf)
#
# Produces hash-labelled artifacts in bitstream/ (decision D2: the
# committed .pof is labelled with the source hash). The label is the
# first 12 hex chars of sha256 over: the slot-map source hash + all RTL
# + the qsf/sdc — so any behavioural or pin change renames the output.
#
# Quartus Prime Lite (never committed) expected at /opt/intelFPGA_lite/21.1.

set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
Q="${QUARTUS_DIR:-/opt/intelFPGA_lite/21.1/quartus}/bin"

cd "$HERE"
python3 gen_slot_map.py >/dev/null   # keep generated/ current

# SIM GATE: the RTL must pass the self-checking testbenches before it is
# allowed to become a hash-labelled bitstream. Skip only with SKIP_SIM=1
# (and then say so in the manifest).
if [ "${SKIP_SIM:-0}" = "1" ]; then
    echo "WARNING: simulation gate SKIPPED (SKIP_SIM=1)" >&2
elif command -v "${IVERILOG:-iverilog}" >/dev/null 2>&1; then
    ./sim/run.sh
else
    echo "ERROR: iverilog not found — install it or set SKIP_SIM=1" >&2
    exit 1
fi

# NON-SHIPPING BUILD SWITCHES. Each one appends to the artifact NAME and
# to NONSHIP[], so the filename and the manifest both say what the
# bitstream is. The hash already distinguishes them (below); the NAME is
# what a human reads at the bench, and it must not read "shipping".
#
#   LOOPBACK     every DSPA input lane fed from the matching DSPB output
#                lane (rtl/dsp4_logic_top.v, `ifdef DSP4_LOOPBACK)
#   PI_SELFTEST  Pi playback looped back to Pi capture inside LOGIC
#   PI_MAINCAP   capture B_O3 slot 0 (MAIN_ST_OUT) instead of slots 2/3
#   PI_TDM8      CM4 link at 4x frame rate, 8 channels each way
NAME="dsp4_logic"
MACRO_ARG=()
NONSHIP=()

if [ "${LOOPBACK:-0}" = "1" ]; then
    MACRO_ARG+=(--verilog_macro=DSP4_LOOPBACK=1)
    NAME="${NAME}_loopback"
    NONSHIP+=("loopback: i_dspa = o_dspb, no converters in the path")
    echo "*** NON-SHIPPING LOOPBACK BUILD (i_dspa = o_dspb) ***" >&2
fi
if [ "${PI_SELFTEST:-0}" = "1" ]; then
    MACRO_ARG+=(--verilog_macro=DSP4_PI_SELFTEST=1)
    NAME="${NAME}_pisel"
    NONSHIP+=("pi_selftest: Pi capture fed from Pi playback, DSP not in the path")
    echo "*** PI_SELFTEST BUILD (Pi playback looped back to Pi capture) ***" >&2
fi
if [ "${PI_MAINCAP:-0}" = "1" ]; then
    MACRO_ARG+=(--verilog_macro=DSP4_PI_MAINCAP=1)
    NAME="${NAME}_maincap"
    NONSHIP+=("pi_maincap: capture B_O3 slot 0, not the product slots 2/3")
    echo "*** PI_MAINCAP BUILD (capture B_O3 slot 0 = MAIN_ST_OUT) ***" >&2
fi
if [ "${PI_TDM8:-0}" = "1" ]; then
    MACRO_ARG+=(--verilog_macro=DSP4_PI_TDM8=1)
    NAME="${NAME}_tdm8"
    NONSHIP+=("pi_tdm8: CM4 link at 4x frame rate (192 kHz), 8 channels each way")
    echo "*** PI_TDM8 EVALUATION BUILD (CM4 link at 4x rate, 8 channels) ***" >&2
fi

# THE ARTIFACT HASH COVERS EVERY MACRO, AND IT DID NOT.
#
# It covered `loopback=` and nothing else, so a PI_TDM8 build and a plain
# build of the SAME RTL produced the same filename and a manifest that
# recorded neither. Two functionally different bitstreams -- one that
# regroups four Pi frames per DSP frame and one that does not -- were
# therefore indistinguishable once flashed, and that is not hypothetical:
# on 2026-09-08 a loop measurement was taken through some bitstream, the
# bench was then left on `dsp4_logic.a1f6672af6c3` (2026-08-21, which
# ties pcm_din to 1'b0 and has no Pi capture path at all), and nothing
# recorded anywhere could say which logic the measurement had run on. The
# sample-order result taken from it had to be discarded rather than
# explained.
#
# A bitstream must name its own configuration. Every macro goes into the
# hash AND into the manifest.
CFG_LINE="loopback=${LOOPBACK:-0} pi_selftest=${PI_SELFTEST:-0}"
CFG_LINE="$CFG_LINE pi_maincap=${PI_MAINCAP:-0} pi_tdm8=${PI_TDM8:-0}"

SRC_HASH=$(cat \
    <(grep -o 'sha256:[0-9a-f]*' generated/dsp4_slot_map.vh | head -1) \
    <(echo "$CFG_LINE") \
    rtl/*.v quartus/dsp4_logic.qsf quartus/dsp4_logic.sdc \
    | sha256sum | cut -c1-12)

# DESIGN ID: the low 32 bits of the artifact hash, stamped into the
# bitstream as a read-only register (S5-9). It is DERIVED here and never
# typed, so "read the register, compare to the manifest" is a real check
# and not a transcription. It deliberately does NOT feed SRC_HASH -- it is
# a function of it -- so adding the stamp does not change any label.
#
# CFG_BITS records the same configuration the manifest's `config:` line
# does, in one word, so a part can say what it is without a manifest to
# hand: bit 0 loopback, 1 pi_selftest, 2 pi_maincap, 3 pi_tdm8, 4 shipping
# (set when no non-shipping switch is set). Bits 5-15 reserved, zero.
DESIGN_ID="32'h${SRC_HASH:4:8}"
CFG_BITS_N=$(( (${LOOPBACK:-0} ? 1 : 0) \
             | (${PI_SELFTEST:-0} ? 2 : 0) \
             | (${PI_MAINCAP:-0} ? 4 : 0) \
             | (${PI_TDM8:-0} ? 8 : 0) \
             | ( ${#NONSHIP[@]} == 0 ? 16 : 0 ) ))
CFG_BITS=$(printf "16'h%04X" "$CFG_BITS_N")
MACRO_ARG+=(--verilog_macro="DSP4_DESIGN_ID=$DESIGN_ID")
MACRO_ARG+=(--verilog_macro="DSP4_CFG_BITS=$CFG_BITS")

cd quartus
"$Q/quartus_map" dsp4_logic "${MACRO_ARG[@]}"
"$Q/quartus_fit" dsp4_logic
"$Q/quartus_sta" dsp4_logic
"$Q/quartus_asm" dsp4_logic
"$Q/quartus_cpf" -c -q 10MHz -g 3.3 -n p \
    output_files/dsp4_logic.pof output_files/dsp4_logic.svf

# STA gate: fail on unmet timing
if grep -q "Timing requirements not met" output_files/dsp4_logic.sta.rpt; then
    echo "ERROR: timing not met" >&2
    exit 1
fi

mkdir -p ../bitstream
cp output_files/dsp4_logic.pof "../bitstream/$NAME.$SRC_HASH.pof"
cp output_files/dsp4_logic.svf "../bitstream/$NAME.$SRC_HASH.svf"
{
    echo "artifact: $NAME.$SRC_HASH.{pof,svf}"
    if [ ${#NONSHIP[@]} -gt 0 ]; then
        echo "SHIPPING: NO — ${#NONSHIP[@]} non-shipping switch(es) set:"
        for n in "${NONSHIP[@]}"; do echo "  - $n"; done
        echo "  Everything not listed is the shipping path, and the sim gate"
        echo "  below ran on it."
    else
        echo "SHIPPING: yes"
    fi
    echo "built: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "config: $CFG_LINE"
    echo "design_id: $DESIGN_ID"
    echo "cfg_bits: $CFG_BITS"
    echo "id_readback: play {L=0xD5D51D1D, R=0x2A2AE2E2} on hw:dsp4pcm and"
    echo "  record: L = design_id, R = 0xD594<cfg_bits> for 128 frames"
    echo "pi_link: $([ "${PI_TDM8:-0}" = "1" ] \
          && echo "2 ch x 32 bits at 192 kHz, 4 Pi frames per DSP frame, all 8 slots" \
          || echo "2 ch x 32 bits at 48 kHz, no regrouping, TDM slots 0/1 only")"
    echo "slot_map: $(grep -o 'sha256:[0-9a-f]*' ../generated/dsp4_slot_map.vh | head -1)"
    echo "sim_gate: $([ "${SKIP_SIM:-0}" = "1" ] && echo SKIPPED || echo PASS)"
    echo "device: 5M1270ZT144C4"
    echo "fmax: $(grep -A4 '; Fmax' output_files/dsp4_logic.sta.rpt | grep MHz | head -1 | awk -F';' '{print $2}' | xargs)"
} > "../bitstream/$NAME.$SRC_HASH.manifest"

echo "OK: bitstream/$NAME.$SRC_HASH.{pof,svf,manifest}"
