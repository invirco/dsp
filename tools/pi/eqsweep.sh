#!/bin/bash
# EQ family vector sweep: each set is band 0, bands 1-3 unity.
for v in "1.0,0.0,0.0,0.0,0.0:unity" \
         "0.5,0.0,0.0,0.0,0.0:gain_half" \
         "1.0,-1.0,0.0,0.0,0.0:fir_b1_neg" \
         "1.0,1.0,0.0,0.0,0.0:fir_b1_pos" \
         "1.0,0.0,-1.0,0.0,0.0:fir_b2_neg" \
         "1.0,0.0,0.5,0.0,0.0:fir_b2_pos" \
         "1.0,0.0,0.0,-0.5,0.0:fb_a1" \
         "1.0,0.0,0.0,0.0,-0.25:fb_a2" \
         "0.2,0.4,0.2,-0.5,0.2:mixed" ; do
  c="${v%%:*}"; n="${v##*:}"
  echo "VECTOR $n $c"
  python3 dsp4_eq_probe.py --bands custom --rbj "$c" --n 12 2>&1 | grep -E "^[0-9]+ "
done
