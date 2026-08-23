#!/bin/bash
for a in 0x00800000 0x01000000 0x02000000 0x04000000 0x08000000 0x0C000000 0x10000000; do
  echo "AMP $a"
  python3 dsp4_comp_probe.py --parallel 0.999 --attack 0.2 --release 0.01 --amp $a --n 200 2>&1 | grep -E "^199 "
done
