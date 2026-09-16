cd ~/s56
set -x
python3 ~/s57/s57_cap.py f150c0 0 5
python3 ~/s57/s57_lfrec.py c0 40
python3 ~/s57/s57_cap.py g1v 63 3
S57_CODE=63 python3 ~/s57/s57_link.py lk 12 quiet,c1,c2
python3 ~/s57/s57_lfrec.py c63 40
for c in 48 32 16; do python3 ~/s57/s57_cap.py g2c$c $c 5; done
python3 ~/s57/s57_lfrec.py c16 40
python3 ~/s57/s57_cap.py g3b 63 5 60
python3 ~/s57/s57_cap.py hb 0 0 0 1
echo QUEUE-DONE
