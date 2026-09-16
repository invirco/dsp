cd ~/s56
while pgrep -f s57_cap.py >/dev/null; do sleep 5; done
S57_CODE=63 python3 ~/s57/s57_link.py lk 12 quiet,c1,c2
python3 ~/s57/s57_lfrec.py c63 40
for c in 48 32 16 0; do python3 ~/s57/s57_cap.py g2c$c $c 5; if [ $c = 32 ] || [ $c = 0 ]; then python3 ~/s57/s57_lfrec.py c$c 40; fi; done
echo QUEUE-DONE
