#!/bin/bash
# dsp4_probe_after_boot.sh — boot, config, then IMMEDIATELY run a probe.
#
# Runs ON THE PI:
#     bash dsp4_probe_after_boot.sh /home/app/dspboot/work dsp4_xpoint_chain.py
#
# The parameter link answers reliably for a while after a fresh boot and
# drifts out of word phase later; a probe started cold will often fail its
# first read-back and look like a firmware fault. Boot and probe in one pass.
set -u
cd /home/app/dspboot
DIR="$1"; shift
python3 dsp4_boot.py --dir "$DIR" 2>&1 | grep -E "booted"
sleep 0.6
python3 dsp4_config.py --product "${PRODUCT:-d24}" --chip 1 2>&1 | tail -1
python3 dsp4_config.py --product "${PRODUCT:-d24}" --chip 2 2>&1 | tail -1
sleep 1.0
timeout "${PROBE_TIMEOUT:-300}" python3 "$@"
