#!/bin/bash
# s65_ladder.sh — the driven cost ladder: base pair vs S65 pair, D24 then D32, fresh boots.
P() { sudo pinctrl set 6,24 op dh; }
set -x
cd ~/s65base && bash boot.sh /home/app/s65base 2>&1 | tail -4
P; SYMDIR=/home/app/s65base python3 s65_drive.py d24
P; BASE=1 SYMDIR=/home/app/s65base python3 s65_cost.py d24_base_driven 6
cd ~/s65 && bash boot.sh /home/app/s65 2>&1 | tail -4
P; SYMDIR=/home/app/s65 python3 s65_drive.py d24
P; SYMDIR=/home/app/s65 NSTRIPS=24 python3 s65_cost.py d24_s65_driven 6
cd ~/s65 && bash boot_d32.sh /home/app/s65 2>&1 | tail -4
P; SYMDIR=/home/app/s65 python3 s65_drive.py d32
P; SYMDIR=/home/app/s65 NSTRIPS=32 python3 s65_cost.py d32_s65_driven 6
cd ~/s65base && bash boot_d32.sh /home/app/s65base 2>&1 | tail -4
P; SYMDIR=/home/app/s65base python3 s65_drive.py d32
P; BASE=1 SYMDIR=/home/app/s65base python3 s65_cost.py d32_base_driven 6
echo LADDER_DONE
