#!/usr/bin/env bash
# run.sh — simulation gate for the DSP4 LOGIC CPLD RTL.
#
# Icarus Verilog, Verilog-2001 (-g2005) to stay inside what Quartus Lite
# accepts for MAX V. Every testbench is self-checking and prints exactly
# one "<name>: PASS" or "<name>: FAIL" line; this script fails on
# anything that is not PASS, so it can gate build.sh alongside STA.
#
#   ./run.sh            run all testbenches
#   ./run.sh tb_clkgen  run one
#   VCD=1 ./run.sh      also write .vcd traces into work/

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE"

IV="${IVERILOG:-iverilog}"
VVP="${VVP:-vvp}"
command -v "$IV" >/dev/null || { echo "ERROR: iverilog not found" >&2; exit 2; }

WORK="$HERE/work"
mkdir -p "$WORK"

ALL_TBS=(tb_clkgen tb_pcm_reframe tb_logic_top)
TBS=("${@:-}")
[ -z "${TBS[0]:-}" ] && TBS=("${ALL_TBS[@]}")

RTL=(../rtl/dsp4_clkgen.v ../rtl/dsp4_pcm_reframe.v ../rtl/dsp4_logic_top.v)
MODELS=(model_tdm_rx.v model_pi_i2s_tx.v)

fails=0
for tb in "${TBS[@]}"; do
    out="$WORK/$tb.vvp"
    log="$WORK/$tb.log"
    if ! "$IV" -g2005 -Wall -I../generated -I../rtl \
         -s "$tb" -o "$out" "$tb.v" "${MODELS[@]}" "${RTL[@]}" 2>"$log.compile"; then
        echo "== $tb: COMPILE ERROR"
        cat "$log.compile"
        fails=$((fails + 1))
        continue
    fi
    grep -v '^$' "$log.compile" | grep -v 'warning: .*implicit' >&2 || true

    ( cd "$WORK" && "$VVP" "$out" ${VCD:+-vcd} ) >"$log" 2>&1
    if grep -q "^$tb: PASS" "$log"; then
        echo "== $tb: PASS"
    else
        echo "== $tb: FAIL"
        sed 's/^/   /' "$log"
        fails=$((fails + 1))
    fi
done

if [ "$fails" -ne 0 ]; then
    echo "SIM GATE: FAILED ($fails testbench(es))"
    exit 1
fi
echo "SIM GATE: OK (${#TBS[@]} testbench(es))"
