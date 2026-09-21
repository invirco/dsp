#!/bin/bash
# s89_bootloop.sh <stagedir> <n> -- boot the SAME image n times, score the
# inter-chip sign bit each time. Tests whether S89-1 is a per-boot lock.
D=$1; N=$2
for i in $(seq 1 $N); do
  ~/s89_boot.sh $D >/dev/null 2>&1
  sudo pinctrl set 6,24 op dh
  cd /home/app/$D
  R=$(timeout 300 python3 s89_signbit.py /home/app/$D 16 2>&1 | egrep "VERDICT|sent bit31")
  L0=$(echo "$R" | sed -n "1p" | sed "s/.*sent/sent/")
  L1=$(echo "$R" | sed -n "2p" | sed "s/.*sent/sent/")
  V0=$(echo "$R" | grep "VERDICT lane 0" | awk "{print \$NF}")
  V1=$(echo "$R" | grep "VERDICT lane 1" | awk "{print \$NF}")
  printf "boot %2d   lane0 %-12s lane1 %-12s | %s | %s\n" "$i" "$V0" "$V1" "$L0" "$L1"
  sudo pinctrl set 6,24 op dh
done
