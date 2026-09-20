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
#   DRIVE_ALL    every DSPA input lane driven from the Pi's playback,
#                broadcast across all eight TDM8 slots -- the driven-
#                capacity stimulus (S19), which costs the DSP nothing
#   LANE_ID      every DSPA input lane carries a distinct word naming its
#                own pin and slot (S85) -- the successor to DRIVE_ALL, which
#                drives six pins with ONE signal and therefore cannot tell a
#                correct lane mapping from a permuted one.
#   AD_FROM_CDC  i_dspa[0..2] fed from cdc_o instead of the converters --
#                the diagnostic that closes the hole in driveall's proof
#                (S85): driving six lanes with ONE signal cannot tell a
#                correct lane mapping from a permuted one.
#   AD_RETIME    ad[0..2] captured on bck8_launch and handed to the DSP as a
#                register output instead of a wire (S85). Costs one BCK
#                period of latency on those three lanes, which the DSP's own
#                per-lane frame delay has to absorb -- so it is a switch
#                until a bench run says the lanes come alive on it.
# The ad[0..2] witness is NOT in this list any more. It is built into every
# configuration from S85, shipping included, exactly like the cdc_o witness it
# copies (hub ruling S84-N1) -- see the area cost stated beside it in
# rtl/dsp4_logic_top.v.
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
if [ "${DRIVE_ALL:-0}" = "1" ]; then
    MACRO_ARG+=(--verilog_macro=DSP4_DRIVE_ALL=1)
    NAME="${NAME}_driveall"
    NONSHIP+=("drive_all: every DSPA input lane fed from the Pi playback, all 8 slots")
    echo "*** DRIVE_ALL BUILD (i_dspa = Pi playback on every slot) ***" >&2
fi
if [ "${PI_TDM8:-0}" = "1" ]; then
    MACRO_ARG+=(--verilog_macro=DSP4_PI_TDM8=1)
    NAME="${NAME}_tdm8"
    NONSHIP+=("pi_tdm8: CM4 link at 4x frame rate (192 kHz), 8 channels each way")
    echo "*** PI_TDM8 EVALUATION BUILD (CM4 link at 4x rate, 8 channels) ***" >&2
fi
if [ "${LANE_ID:-0}" = "1" ]; then
    MACRO_ARG+=(--verilog_macro=DSP4_LANE_ID=1)
    NAME="${NAME}_laneid"
    NONSHIP+=("lane_id: every DSPA input lane carries a word naming its own pin and slot")
    echo "*** LANE_ID DIAGNOSTIC (each i_dspa lane names itself) ***" >&2
fi
if [ "${AD_FROM_CDC:-0}" = "1" ]; then
    MACRO_ARG+=(--verilog_macro=DSP4_AD_FROM_CDC=1)
    NAME="${NAME}_adcdc"
    NONSHIP+=("ad_from_cdc: i_dspa[0..2] fed from cdc_o, NOT from the converters")
    echo "*** AD_FROM_CDC DIAGNOSTIC (mic lanes fed from the codec lane) ***" >&2
fi
if [ "${AD_RETIME:-0}" = "1" ]; then
    MACRO_ARG+=(--verilog_macro=DSP4_AD_RETIME=1)
    NAME="${NAME}_adrt"
    NONSHIP+=("ad_retime: ad[0..2] captured on bck8_launch, +1 BCK of latency")
    echo "*** AD_RETIME BUILD (ad[0..2] registered, not a wire) ***" >&2
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
# CFG_BITS records the same configuration the manifest's `config:` line
# does, in one word, so a part can say what it is without a manifest to
# hand: bit 0 loopback, 1 pi_selftest, 2 pi_maincap, 3 pi_tdm8, 4 shipping
# (set when no non-shipping switch is set), 5 drive_all, 7 ad_retime,
# 8 ad_from_cdc, 9 lane_id. Bits 6 and 10-15 reserved, zero -- bit 6 was
# ad_witness and is retired at S85 because the witness is now in every
# bitstream (hub ruling S84-N1), so a bit that was always set said nothing.
#
# IT IS COMPUTED HERE, ABOVE CFG_LINE, AND IT GOES INTO THE HASH. S85 found
# the same hole the PI_TDM8 episode found, one level up: CFG_BITS is derived
# by THIS FILE, which SRC_HASH does not cover, so adding bit 7 for AD_RETIME
# changed what a part answers to the ID knock while leaving the label it is
# filed under identical. That is two functionally different bitstreams
# sharing one label again -- the exact failure the paragraph below exists to
# prevent -- and it is not caught by hashing rtl/ harder, because the change
# was not in rtl/. Putting the computed word itself in CFG_LINE closes it:
# any future change to this derivation renames every artifact it changes.
CFG_BITS_N=$(( (${LOOPBACK:-0} ? 1 : 0) \
             | (${PI_SELFTEST:-0} ? 2 : 0) \
             | (${PI_MAINCAP:-0} ? 4 : 0) \
             | (${PI_TDM8:-0} ? 8 : 0) \
             | (${DRIVE_ALL:-0} ? 32 : 0) \
             | (${AD_RETIME:-0} ? 128 : 0) \
             | (${AD_FROM_CDC:-0} ? 256 : 0) \
             | (${LANE_ID:-0} ? 512 : 0) \
             | ( ${#NONSHIP[@]} == 0 ? 16 : 0 ) ))
CFG_BITS=$(printf "16'h%04X" "$CFG_BITS_N")

CFG_LINE="loopback=${LOOPBACK:-0} pi_selftest=${PI_SELFTEST:-0}"
CFG_LINE="$CFG_LINE pi_maincap=${PI_MAINCAP:-0} pi_tdm8=${PI_TDM8:-0}"
CFG_LINE="$CFG_LINE drive_all=${DRIVE_ALL:-0}"
CFG_LINE="$CFG_LINE ad_retime=${AD_RETIME:-0}"
CFG_LINE="$CFG_LINE ad_from_cdc=${AD_FROM_CDC:-0}"
CFG_LINE="$CFG_LINE lane_id=${LANE_ID:-0}"
CFG_LINE="$CFG_LINE cfg_bits=$CFG_BITS"

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
DESIGN_ID="32'h${SRC_HASH:4:8}"
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
    echo "cdc_witness: play {L=0xCD0432B4, R=0x32FBCD4B} and record, 128 frames:"
    echo "  L = {7'b0, cdc_ones_last[8:0], 7'b0, cdc_ones_max[8:0]}"
    echo "  R = {0xCD04, cdc_toggles_last[8:0], frame_counter[15:9]}"
    echo "  cdc_ones/toggles are per 48 kHz frame over 256 TDM8 bit periods;"
    echo "  the frame counter MUST advance between two knocks or the witness"
    echo "  is dead and its zeros mean nothing (S81)"
    if [ "${AD_RETIME:-0}" = "1" ]; then
        echo "ad_retime: ad[0..2] are NOT a wire through this part in this"
        echo "  bitstream. They are captured on bck8_launch and handed to the"
        echo "  DSP as a register output, so those three lanes carry ONE BCK"
        echo "  PERIOD (81.38 ns) more latency than the shipping path and the"
        echo "  DSP's per-lane frame delay must absorb it (lane_config.c,"
        echo "  c1_rx_lanes_mfd). Measured, not assumed: the S85 witness found"
        echo "  the data stable on both bck8 edges at these pins, so the"
        echo "  capture has most of a bit period of margin on either side."
    fi
    # UNCONDITIONAL from S85 (hub ruling S84-N1): the witness is in every
    # bitstream, so every manifest documents it.
    if true; then
        echo "ad_witness: play {L=0xAD075E2<b>, R=~L} and record, 128 frames."
        echo "  The knock's low three bits are the selector:"
        echo "    <b>[1:0]  lane 0, 1 or 2   (lane 3 is NOT a knock: no"
        echo "               converter on AD3, it falls through to audio)"
        echo "    <b>[2]    0 = counted on bck8_sample (bck8 rising, the edge"
        echo "               the DSP samples the lane on -- S84's only bank)"
        echo "               1 = counted on bck8_launch (bck8 falling), added"
        echo "               at S85 to measure the converter launch phase"
        echo "  So <b> = 0,1,2 are S84's three knocks unchanged, and 4,5,6 are"
        echo "  the same three lanes on the other edge. Six banks, all counting"
        echo "  the same pass at once; one knock answers about one of them."
        echo "  L = {3'b0, bck_ratio_ok, edge, lane[1:0], ad_ones_last[8:0],"
        echo "       7'b0, ad_ones_max[8:0]}"
        echo "  R = {0xAD07, ad_toggles_last[8:0], frame_counter[15:9]}"
        echo "  Counts are per 48 kHz frame over 256 TDM8 bit periods."
        echo "  bck_ratio_ok is 1 while every conv_fs frame since power-up has"
        echo "  held exactly 256 bck8 periods -- the generator's own ratio, not"
        echo "  arrival at any pin."
        echo "  The frame counter is fs8 = conv_fs, which this part GENERATES:"
        echo "  it witnesses that the clock generator runs, NOT that the clock"
        echo "  arrives at the AK5558 pins. It MUST advance between two knocks"
        echo "  or the witness is dead and its zeros mean nothing (S81/S84)."
    fi
    # Stated because a diagnostic that costs half the part is a fact the next
    # session needs before it adds anything else, and because the fit is the
    # only place it is written down otherwise.
    echo "logic_elements: $(grep -m1 'Total logic elements' \
          output_files/dsp4_logic.fit.rpt | awk -F';' '{print $3}' | xargs)"
    echo "registers: $(grep -m1 'Total registers' \
          output_files/dsp4_logic.fit.rpt | awk -F';' '{print $3}' | xargs)"
    echo "pins: $(grep -m1 'Total pins' \
          output_files/dsp4_logic.fit.rpt | awk -F';' '{print $3}' | xargs)"
    echo "pi_link: $([ "${PI_TDM8:-0}" = "1" ] \
          && echo "2 ch x 32 bits at 192 kHz, 4 Pi frames per DSP frame, all 8 slots" \
          || echo "2 ch x 32 bits at 48 kHz, no regrouping, TDM slots 0/1 only")"
    echo "slot_map: $(grep -o 'sha256:[0-9a-f]*' ../generated/dsp4_slot_map.vh | head -1)"
    echo "sim_gate: $([ "${SKIP_SIM:-0}" = "1" ] && echo SKIPPED || echo PASS)"
    echo "device: 5M1270ZT144C4"
    echo "fmax: $(grep -A4 '; Fmax' output_files/dsp4_logic.sta.rpt | grep MHz | head -1 | awk -F';' '{print $2}' | xargs)"
} > "../bitstream/$NAME.$SRC_HASH.manifest"

echo "OK: bitstream/$NAME.$SRC_HASH.{pof,svf,manifest}"
