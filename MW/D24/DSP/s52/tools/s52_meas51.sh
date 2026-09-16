#!/bin/bash
export SYMDIR=/home/app/s51_119ea9d9
~/app cli chain-set 27 ch8:mute=0,gain=0 2>&1 | grep -E "VERIFIED|MISMATCH|\[15\] ch8" | tail -2
cd ~/s51_119ea9d9
python3 dsp4_s49_osc.py --strip 6 --meas 20 --freq 1000 --level -20 --windows 12 --symdir $SYMDIR --json /home/app/s52/m51_g0_m20.json 2>&1 | grep -E "seq |SETTLED|Result"
cd ~/s52 && python3 s52_overrun.py
cd ~/s51_119ea9d9
python3 dsp4_s49_osc.py --strip 6 --meas 20 --off --windows 16 --symdir $SYMDIR --json /home/app/s52/m51_g0_off.json 2>&1 | grep -E "seq |SETTLED|Result"
python3 dsp4_s49_osc.py --strip 6 --meas 20 --freq 1000 --level -20 --windows 3 --symdir $SYMDIR 2>&1 | grep -E "RmsResult|ThdResult"
