#!/bin/bash
for a in 0x00040000 0x00200000 0x00300000 0x00400000 0x00800000 0x02000000 0x08000000; do
  echo "AMP $a"
  python3 dsp4_gate_probe.py --amp $a --n 300 2>&1 | grep -E "^299 "
done
