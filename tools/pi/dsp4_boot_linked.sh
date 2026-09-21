#!/bin/bash
# dsp4_boot_linked.sh <stagedir> [maxtries] -- boot the pair and DO NOT HAND IT
# BACK until the inter-chip link has come up with the sign bit intact.
#
# S89-1: the inter-chip SPORT receive lock comes up one bit period out on
# roughly one boot in five to one in ten, on every build measured, and every
# inter-chip word then arrives with bit 31 zeroed -- audio's negative half folds
# to just under the +8.0 Q4.28 rail. Nothing in the SPORT registers differs on a
# bad boot, so the only way to know is to look at the data. A boot that is not
# checked is a boot that is 10-20% likely to be silently folded.
#
# Exit 0 = linked and verified. Exit 1 = could not get a clean link.
set -u
D=${1:?usage: dsp4_boot_linked.sh <stagedir> [maxtries]}
N=${2:-6}
for t in $(seq 1 "$N"); do
    "${BOOT_SH:-$HOME/s89_boot.sh}" "$D" >/dev/null 2>&1 || true
    sudo pinctrl set 6,24 op dh
    cd "/home/app/$D" || exit 1
    if python3 s89_signbit.py "/home/app/$D" 16 > /tmp/s89_link.$$ 2>&1; then
        echo "link verified on boot attempt $t"
        grep -E 'VERDICT|OVERALL' /tmp/s89_link.$$
        rm -f /tmp/s89_link.$$
        exit 0
    fi
    rc=$?
    if [ "$rc" = "2" ]; then
        echo "attempt $t: INCONCLUSIVE -- nothing negative on the wire to judge on"
        cat /tmp/s89_link.$$
    else
        echo "attempt $t: FOLDED (S89-1) -- rebooting the pair"
    fi
done
rm -f /tmp/s89_link.$$
echo "FAILED: no clean inter-chip link in $N attempts"
exit 1
