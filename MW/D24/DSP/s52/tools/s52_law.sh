#!/bin/bash
# s52_law.sh <osc_dbfs> <gain codes...> — MIC 5 (chain-set label ch8 = p15 = J25) alone at each code; TEST_MEAS on strip 20 + quiet capture.
LVL=$1; shift
for g in "$@"; do
  echo "===== gain code $g, osc $LVL dBFS peak"
  ~/app cli chain-set 27 ch8:mute=0,gain=$g 2>&1 | grep -E "VERIFIED|MISMATCH|\[15\] ch8" | tail -2
  sleep 0.5
  cd ~/s49tap && python3 dsp4_s49_osc.py --strip 6 --meas 20 --freq 1000 --level $LVL --windows 4 --symdir /home/app/s49tap 2>&1 | grep -E "seq |RmsResult|ThdResult|NoiseResult" | tail -7
  cd ~/s52 && python3 s52_quietcap.py C1_FDR_20 /home/app/s52/law_${LVL}_g$g.json 0.5 | tail -1
done
