#!/bin/bash
P() { sudo pinctrl set 6,24 op dh; }
set -x
cd ~/s65s26 && bash boot.sh /home/app/s65s26 2>&1 | tail -6
P; SYMDIR=/home/app/s65s26 python3 s56_setup.py 2>&1 | tail -3
P; SYMDIR=/home/app/s65s26 python3 s65_hookcheck.py
P; SYMDIR=/home/app/s65s26 python3 s65_drive.py d24
P; SYMDIR=/home/app/s65s26 NSTRIPS=24 python3 s65_cost.py d24_s26_s65_driven 6
cd ~/s65s26base && bash boot.sh /home/app/s65s26base 2>&1 | tail -4
P; SYMDIR=/home/app/s65s26base python3 s65_drive.py d24
P; BASE=1 SYMDIR=/home/app/s65s26base python3 s65_cost.py d24_s26_base_driven 6
cd ~/s65s26 && bash boot_d32.sh /home/app/s65s26 2>&1 | tail -4
P; SYMDIR=/home/app/s65s26 python3 s65_drive.py d32
P; SYMDIR=/home/app/s65s26 NSTRIPS=32 python3 s65_cost.py d32_s26_s65_driven 6
cd ~/s65s26base && bash boot_d32.sh /home/app/s65s26base 2>&1 | tail -4
P; SYMDIR=/home/app/s65s26base python3 s65_drive.py d32
P; BASE=1 SYMDIR=/home/app/s65s26base python3 s65_cost.py d32_s26_base_driven 6
echo LADDER_DONE
