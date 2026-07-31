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

SRC_HASH=$(cat \
    <(grep -o 'sha256:[0-9a-f]*' generated/dsp4_slot_map.vh | head -1) \
    rtl/*.v quartus/dsp4_logic.qsf quartus/dsp4_logic.sdc \
    | sha256sum | cut -c1-12)

cd quartus
"$Q/quartus_map" dsp4_logic
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
cp output_files/dsp4_logic.pof "../bitstream/dsp4_logic.$SRC_HASH.pof"
cp output_files/dsp4_logic.svf "../bitstream/dsp4_logic.$SRC_HASH.svf"
{
    echo "artifact: dsp4_logic.$SRC_HASH.{pof,svf}"
    echo "built: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "slot_map: $(grep -o 'sha256:[0-9a-f]*' ../generated/dsp4_slot_map.vh | head -1)"
    echo "device: 5M1270ZT144C4"
    echo "fmax: $(grep -A4 '; Fmax' output_files/dsp4_logic.sta.rpt | grep MHz | head -1 | awk -F';' '{print $2}' | xargs)"
} > "../bitstream/dsp4_logic.$SRC_HASH.manifest"

echo "OK: bitstream/dsp4_logic.$SRC_HASH.{pof,svf,manifest}"
