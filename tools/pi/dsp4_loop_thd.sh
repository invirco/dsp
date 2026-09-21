#!/bin/bash
# s89_loopthd.sh <stagedir> <n> -- verified boot, re-assert the Monitor loop,
# one coherent THD reading. Repeat n times to see whether the ANALOG loop THD is
# also decided at boot (S89-1 on the converter TX lane).
D=$1; N=$2
for i in $(seq 1 $N); do
  L=$(timeout 900 ~/dsp4_boot_linked.sh $D 6 2>&1 | egrep -c "FOLDED")
  cd /home/app/$D
  sudo pinctrl set 6,24 op dh
  python3 s89_set.py /home/app/$D Chan020MainOn001=1 Chan020Mute001=0 \
    Chan020Level001=f1.0:4 Chan020Pan001=f0.5:4 Chan020CompOn001=0 \
    Chan020GateOn001=0 Chan020TubeOn001=0 Chan020EqOn001=0 \
    Chan006Mute001=0 Chan006Gain001=f1.0:1 Chan006Level001=f1.0:4 \
    Chan006Pan001=f0.5:4 Chan006CompOn001=0 Chan006GateOn001=0 \
    Chan006TubeOn001=0 Chan006EqOn001=0 Chan006MainOn001=0 Chan006AuxOn001=0 \
    Main001Level001=f1.0:4 Main001Mute001=0 >/dev/null 2>&1
  sudo pinctrl set 6,24 op dh
  R=$(timeout 300 python3 dsp4_s49_osc.py --strip 20 --meas 6 --freq 1000 --level -12.0 --symdir /home/app/$D 2>&1 | egrep "RmsResult|ThdResult" | tr -s " " | tr "\n" " ")
  printf "boot %d (ic-retries %s): %s\n" "$i" "$L" "$R"
  sudo pinctrl set 6,24 op dh
done
