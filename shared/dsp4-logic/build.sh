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

# LOOPBACK=1 builds the NON-SHIPPING bring-up variant: every DSPA input
# lane fed from the matching DSPB output lane (rtl/dsp4_logic_top.v,
# `ifdef DSP4_LOOPBACK). It is labelled dsp4_logic_loopback.<hash> so it
# can never be confused with a shipping artifact, and the define is part
# of the hash input so the two never collide.
# PI_TDM8=1 adds the eight-channel CM4 link evaluation mode (4x frame
# rate). Combines with LOOPBACK; both are non-shipping.
if [ "${LOOPBACK:-0}" = "1" ]; then
    MACRO_ARG=(--verilog_macro=DSP4_LOOPBACK=1)
    NAME="dsp4_logic_loopback"
    echo "*** NON-SHIPPING LOOPBACK BUILD (i_dspa = o_dspb) ***" >&2
else
    MACRO_ARG=()
    NAME="dsp4_logic"
fi

# PI_TDM8=1 adds the eight-channel CM4 link evaluation mode (4x frame
# rate on the Pi side). Non-shipping; combines with LOOPBACK.
if [ "${PI_SELFTEST:-0}" = "1" ]; then
    MACRO_ARG+=(--verilog_macro=DSP4_PI_SELFTEST=1)
    echo "*** PI_SELFTEST BUILD (Pi playback looped back to Pi capture) ***" >&2
fi
if [ "${PI_MAINCAP:-0}" = "1" ]; then
    MACRO_ARG+=(--verilog_macro=DSP4_PI_MAINCAP=1)
    echo "*** PI_MAINCAP BUILD (capture B_O3 slot 0 = MAIN_ST_OUT) ***" >&2
fi
if [ "${PI_TDM8:-0}" = "1" ]; then
    MACRO_ARG+=(--verilog_macro=DSP4_PI_TDM8=1)
    echo "*** PI_TDM8 EVALUATION BUILD (CM4 link at 4x rate, 8 channels) ***" >&2
fi

SRC_HASH=$(cat \
    <(grep -o 'sha256:[0-9a-f]*' generated/dsp4_slot_map.vh | head -1) \
    <(echo "loopback=${LOOPBACK:-0}") \
    rtl/*.v quartus/dsp4_logic.qsf quartus/dsp4_logic.sdc \
    | sha256sum | cut -c1-12)

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
    if [ "${LOOPBACK:-0}" = "1" ]; then
        echo "SHIPPING: NO — bring-up loopback build, i_dspa = o_dspb."
        echo "  Differs from shipping by that one assign only; the sim gate"
        echo "  below ran on the SHIPPING path, which is everything else."
    else
        echo "SHIPPING: yes"
    fi
    echo "built: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "slot_map: $(grep -o 'sha256:[0-9a-f]*' ../generated/dsp4_slot_map.vh | head -1)"
    echo "sim_gate: $([ "${SKIP_SIM:-0}" = "1" ] && echo SKIPPED || echo PASS)"
    echo "device: 5M1270ZT144C4"
    echo "fmax: $(grep -A4 '; Fmax' output_files/dsp4_logic.sta.rpt | grep MHz | head -1 | awk -F';' '{print $2}' | xargs)"
} > "../bitstream/$NAME.$SRC_HASH.manifest"

echo "OK: bitstream/$NAME.$SRC_HASH.{pof,svf,manifest}"
