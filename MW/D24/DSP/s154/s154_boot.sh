#!/usr/bin/env bash
# s154_boot.sh STAGE_DIR -- boot the pair staged in STAGE_DIR on MW-D24-2 the
# way d24_selftest.boot_pair does, with the dispatch's rail order around it:
# AN_EN LOW first (analog last up, first down), boot + config TWICE, the
# inter-chip sign-bit gate, S_RUN (codec4619.py --run --reinit), the 595
# chain to SAFE (verified), and only then AN_EN HIGH.
set -u
STAGE="$1"
[ "$(systemctl is-active d24-factory)" = inactive ] || { echo "d24-factory is ACTIVE -- refusing"; exit 2; }
P() { sudo pinctrl set "$@"; }
handback() { P 7,9,10,11,22,23,25 a0; P 6,24 op dh; P 27 op dh; P 8,12 ip pd; }
echo "AN_EN before: $(pinctrl get 26)"
P 26 op dl; sleep 0.5
echo "AN_EN lowered: $(pinctrl get 26)"
cd "$STAGE" || exit 2
md5sum chip1.ldr chip2.ldr
for cycle in 1 2; do
  handback
  echo "--- boot cycle $cycle"; python3 dsp4_boot.py --dir . 2>&1 | tail -4
  for chip in 1 2; do
    P 6,24 op dh
    echo "--- config cycle $cycle chip $chip"
    python3 dsp4_config.py --product d24 --chip $chip 2>&1 | tail -2
  done
done
handback
echo "--- sign-bit gate"; python3 s89_signbit.py "$STAGE" 2>&1 | tail -3
echo "--- S_RUN"; (cd /home/app/dspboot && timeout 60 python3 codec4619.py --run --reinit 2>&1 | tail -2)
P 27 op dh; P 6,24 op dh
echo "--- 595 SAFE"; (cd /home/app/s55 && sudo -n python3 s55_chain.py $(for i in $(seq 24); do printf '0x01 '; done) 0x00 2>&1 | head -1)
P 26 op dh
echo "AN_EN raised: $(pinctrl get 26)"
