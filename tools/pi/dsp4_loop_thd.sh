#!/bin/bash
# dsp4_loop_thd.sh <stagedir> [boots] -- THE CABLE-LOOP THD ACCEPTANCE LEG.
# EXIT CODE IS THE VERDICT: 0 = PASS, 1 = FAIL, 2 = INCONCLUSIVE.
#
# WHY THIS EXISTS (S88-1, S89, S89e). The signed shipping configuration was
# proved by golden captures, dsp_validate, dry runs, conformance walks, family
# verdicts and a driven capacity row -- ALL OF THEM HOST-SIDE OR DIGITAL --
# and it shipped with 57 % THD at the XLR. Every digital probe was clean,
# because the defect was between the output slot and the wire: the chip-2
# gather overwriting a transmit row the DDE had not finished reading
# (MW/D24/DSP/s89/dac-fold-fix.md). NOTHING IN THE PROOF LISTENED, so nothing
# could see it. This leg listens, with no dScope, no PW's hands and no CPLD
# flash: a cable from an output back into a mic input, the self-test
# oscillator at one end and the self-test analyser at the other.
#
# THE LANE IS THE UNIT'S, NOT THIS SCRIPT'S. The loop cable on MW-D24-2 is on
# Monitor L -> MIC 6 today (PW moved it for the S89 TRS set); it was AUX 1 ->
# MIC 6 before that. OSC_STRIP/MEAS_STRIP name it, so a cable move is an
# environment variable and not an edit.
#
# THE ARM MUST BE A DSP4_TEST_NODES=1 BUILD OF THE CONFIGURATION UNDER PROOF.
# TEST_OSC and TEST_MEAS are the instrument and shipping.config carries
# DSP4_TEST_NODES=0, so the literal shipping image cannot measure itself. The
# proof is therefore of the CONFIGURATION -- every other switch at its
# shipping value -- and MW/D32/DSP/SHARC/loopthd.sh is what builds it that
# way. Say which image was measured; do not call a TEST_NODES arm "the
# shipping image".
#
# THE BOOT IS GATED (S89-1). The inter-chip link locks a bit period out on
# about one boot in seven and folds the sign bit, which reads as ~56 % THD and
# is NOT this defect. dsp4_boot_linked.sh retries until s89_signbit.py passes,
# so a folded link can never be mistaken for a folded DAC.
#
#   dsp4_loop_thd.sh ~/s89e_x2 3
#   OSC_STRIP=6 MEAS_STRIP=5 dsp4_loop_thd.sh ~/arm 1     # AUX 1 -> MIC 5
#   THD_LIMIT_PCT=1.0 dsp4_loop_thd.sh ~/arm 1
set -u
D=${1:?usage: dsp4_loop_thd.sh <stagedir> [boots]}
# Accept either an absolute path or one relative to /home/app, and keep any
# sub-directory: `basename` here would turn `loopthd/ship` into `ship` and
# then boot whatever happens to sit at /home/app/ship.
D=${D#/home/app/}; D=${D#/}
N=${2:-1}

OSC_STRIP="${OSC_STRIP:-20}"          # the strip the oscillator drives (Monitor L source)
MEAS_STRIP="${MEAS_STRIP:-6}"         # the strip the cable returns to (MIC 6)
FREQ="${FREQ:-1000}"                  # bin-centred at 16,320 samples (S63)
DRIVES="${DRIVES:--12.0 -22.0}"
# THE LIMIT IS THE LOOP'S OWN FLOOR PLUS MARGIN, NOT A SPEC NUMBER. Six
# independent clean arms (S89's all-off control and S89e's t0/g1/g2/x2/x2d26/
# x2d47) all read 0.321-0.360 % at -12 dBFS drive on this cable, and the
# folding arm reads 57.3-59.7 %: a 45 dB separation with nothing in between.
# 1 % is set to sit in that gap -- it fails the defect by 35 dB and passes the
# floor by 10 dB. It is NOT an audio specification for the product and must
# not be quoted as one.
LIMIT="${THD_LIMIT_PCT:-1.0}"
# The return level the loop gives when it is alive, and the window either side.
# A reading taken on a dead or re-patched lane is INCONCLUSIVE, not a pass:
# a silent lane reads a low THD for the same reason a dead probe does.
LVL_MIN="${LOOP_LVL_MIN_DBFS:--45.0}"
LVL_MAX="${LOOP_LVL_MAX_DBFS:--5.0}"
# THE LOOP MUST TRACK THE DRIVE, AND THIS IS THE CHECK THAT SAYS SO.
# The level window above catches a DEAD lane. It does not catch a lane that is
# alive and WRONG, and this bench has produced two of those in one day:
#   * the 595 chain left at matrix-app's gain pinned the return at -0.7 dBFS
#     for every drive from -12 to -42 dBFS, and a CLEAN build read 39 % THD;
#   * an unasserted route left the donor strip's compressor on (threshold near
#     -22 dBFS, S70-3) and 10 dB of drive moved the return 4.9 dB.
# Both sat inside the window. Two drives 10 dB apart must move the return by
# 10 dB: anything else is a compressor, a limiter or a rail, and the THD
# number taken beside it means nothing. INCONCLUSIVE, never a pass.
TRACK_TOL="${LOOP_TRACK_TOL_DB:-2.0}"

# ---- THE LOADED REGIME (S91) -------------------------------------------
#
# WHY A LOOP READING TAKEN AT IDLE IS NOT THE WHOLE PROOF. The defect this
# leg exists to catch is a function of WHERE IN THE BLOCK PERIOD chip 2's
# gather lands, and until DSP4_TX_DEFER that position was the node graph's
# cycle count (MW/D24/DSP/s89/dac-fold-fix.md). So a clean reading at the
# graph's idle speed says nothing about the graph's loaded speed, and the
# S89e figures were all taken at idle: chip 2 sits at ~77.5 % of budget with
# the product's default routes and dynamics, and at ~84.4 % with every bus
# assign and send open and every dynamics node on.
#
# LOAD_SETUP=1 applies `dsp4_driven_setup.py --mode load` to BOTH chips
# after the gated boot and BEFORE the route write, so the loop's own two
# strips are the only ones the route then clears and the other thirty stay
# loaded. It also prints where the gather actually landed -- chip 2's
# `_proc_cyc` as a percentage of budget, read on the same boot as the THD
# number beside it -- because "clean at 84 % of budget" is the claim, and a
# percentage nobody read is not a claim.
#
# IT IS NOT THE `driveall` DRIVEN ROW AND MUST NOT BE CALLED ONE. That row
# needs the driveall bitstream, which broadcasts the Pi's playback onto
# every DSPA input lane -- including the one this cable returns to, so the
# loop cannot be measured on it at all. What is measurable is the LOADED
# configuration on the shipping bitstream, and S86's own table is why that
# is the right stand-in: chip 2 reads 84.41 % silent-loaded against 84.47 %
# driven, 0.06 points apart, because the cost of the load is the routes and
# the engaged dynamics rather than the sample values.
LOAD_SETUP="${LOAD_SETUP:-0}"
LOAD_PRODUCT="${LOAD_PRODUCT:-d24}"
POS_DWELL="${POS_DWELL:-15}"
# THE LOADED CONFIGURATION IS NOT TRANSPARENT TO THE LOOP, AND CLEARING THE
# LOOP'S OWN TWO STRIPS IS NOT ENOUGH (S91). `--mode load` turns EVERY
# dynamics node on with a -60 dB threshold, and the loop's donor is Monitor L,
# whose source is the MAIN bus -- so the MAIN compressor and limiter sit on the
# loop path, downstream of both strips the route write clears. Measured: with
# the load applied and nothing else changed, the return sat at -63.4 dBFS and
# 10 dB of drive moved it 0.01 dB. That is the S70-3 trap one level up, and
# the tracking check caught it rather than a number being reported.
#
# So the classes on the loop path are switched off AFTER the load is applied.
# What that costs the position is almost nothing and the position readout
# below says so on the same boot: chip 2's cost here is the OPEN BUSES, not
# the dynamics' expensive branch (S91's own ladder puts row C within 0.01
# points of row B on chip 2).
LOAD_OFF="${LOAD_OFF:-Comp,Gate,Limiter}"

# Cell names are three digits wide (Chan006, Chan020); pad rather than
# interpolating, so OSC_STRIP=6 does not silently address "Chan06".
OSC=$(printf '%03d' "$OSC_STRIP")
MEAS=$(printf '%03d' "$MEAS_STRIP")

worst=0; worst_lvl=""; rc=0; any=0; lvls=""
for i in $(seq 1 "$N"); do
    L=$(timeout 900 "${BOOT_SH:-$HOME/dsp4_boot_linked.sh}" "$D" 8 2>&1 | grep -c "FOLDED")
    cd "/home/app/$D" || exit 2
    sudo pinctrl set 6,24 op dh
    # THE LOADED REGIME, BEFORE THE ROUTE AND NOT AFTER IT. `--mode load`
    # turns every dynamics node ON; the route write below clears the two
    # strips the loop runs through, so running it the other way round would
    # put the donor's compressor back and the reading would be of a
    # compressor (S70-3). Order is the check here.
    if [ "$LOAD_SETUP" = "1" ]; then
        for C in 1 2; do
            python3 dsp4_driven_setup.py --chip $C --mode load \
                    --landed "landed-$LOAD_PRODUCT.json" \
                    ${LOAD_OFF:+--off "$LOAD_OFF"} \
                    > "/tmp/loopthd_load_c$C.$$" 2>&1 \
                || { echo "LOAD SETUP FAILED on chip $C -- the reading that"
                     echo "follows would be of the DEFAULT configuration:"
                     sed 's/^/    /' "/tmp/loopthd_load_c$C.$$"
                     rm -f "/tmp/loopthd_load_c$C.$$"; exit 2; }
            echo "  load c$C: $(tail -1 "/tmp/loopthd_load_c$C.$$")"
            rm -f "/tmp/loopthd_load_c$C.$$"
        done
        # WHERE THE GATHER LANDED, on this boot, in the part's own words.
        sudo pinctrl set 6,24 op dh
        python3 dsp4_capacity.py --dwell "$POS_DWELL" --tag loopthd-load \
                --json "/tmp/loopthd_pos.$$.json" 2>&1 \
            | sed -n 's/^chip \([12]\) .*/CHIP \1/p;s/^ *_proc_cyc  *\([0-9]*\)  *\([0-9.]*\)%/  _proc_cyc \1 = \2 % of budget/p' \
            | sed 's/^/  position: /'
        rm -f "/tmp/loopthd_pos.$$.json"
        sudo pinctrl set 6,24 op dh
        # THE LOAD OPENS EVERY STRIP INTO MAIN, AND MAIN IS THE LOOP'S SOURCE.
        # Monitor L takes MAIN (S89), so with every assign open the cable
        # carries the SUM of all 32 strips' converter noise, not the tone.
        # Measured: the return sat at -19.00 dBFS and 10 dB of drive moved it
        # 0.50 dB, because the tone was ~31 dB under that sum. Closing every
        # OTHER strip's MAIN assign puts the donor alone on the loop while the
        # aux and matrix fabric -- which is where chip 2's loaded cost
        # actually is -- stays wide open. The position printed above is taken
        # AFTER this, so the number the THD is quoted against is the number
        # the part was running at.
        CLOSE=""
        for s in $(seq 1 32); do
            [ "$s" = "$OSC_STRIP" ] && continue
            CLOSE="$CLOSE Chan$(printf '%03d' "$s")MainOn001=0"
        done
        python3 s89_set.py "/home/app/$D" $CLOSE > /tmp/loopthd_close.$$ 2>&1 \
            || { echo "MAIN-CLOSE WRITE FAILED -- the loop would be measuring"
                 echo "the sum of every strip, not the tone:"
                 sed 's/^/    /' /tmp/loopthd_close.$$
                 rm -f /tmp/loopthd_close.$$; exit 2; }
        echo "  loop path: $(( 32 - 1 )) other strips closed off MAIN"
        rm -f /tmp/loopthd_close.$$
        sudo pinctrl set 6,24 op dh
    fi
    # The donor strip is part of the instrument and is NOT transparent out of
    # dsp4_config.py (S70-2/S70-3): its compressor is ON with a threshold near
    # -22 dBFS and would read as an analog overload. Both strips are cleared
    # here, every time, and the return strip is taken off every bus so it
    # cannot feed the loop that stimulates it.
    python3 s89_set.py "/home/app/$D" \
        Chan${OSC}MainOn001=1 Chan${OSC}Mute001=0 \
        Chan${OSC}Level001=f1.0:4 Chan${OSC}Pan001=f0.5:4 \
        Chan${OSC}CompOn001=0 Chan${OSC}GateOn001=0 \
        Chan${OSC}TubeOn001=0 Chan${OSC}EqOn001=0 \
        Chan${MEAS}Mute001=0 Chan${MEAS}Gain001=f1.0:1 \
        Chan${MEAS}Level001=f1.0:4 Chan${MEAS}Pan001=f0.5:4 \
        Chan${MEAS}CompOn001=0 Chan${MEAS}GateOn001=0 \
        Chan${MEAS}TubeOn001=0 Chan${MEAS}EqOn001=0 \
        Chan${MEAS}MainOn001=0 Chan${MEAS}AuxOn001=0 \
        Main001Level001=f1.0:4 Main001Mute001=0 > /tmp/loopthd_route.$$ 2>&1
    if [ $? -ne 0 ]; then
        # NOT >/dev/null. The route write used to be discarded, and the first
        # run of MW/D32/DSP/SHARC/loopthd.sh then measured a DEFAULT config
        # (s89_set.py had not been staged): the donor strip's own compressor
        # is ON out of dsp4_config.py with a threshold near -22 dBFS (S70-3),
        # so the loop compressed and the leg reported PASS on a route that
        # was never asserted.
        echo "ROUTE WRITE FAILED -- the reading that follows would be of the"
        echo "DEFAULT configuration, not of the loop:"
        sed 's/^/    /' /tmp/loopthd_route.$$; rm -f /tmp/loopthd_route.$$
        exit 2
    fi
    rm -f /tmp/loopthd_route.$$
    for LV in $DRIVES; do
        sudo pinctrl set 6,24 op dh
        R=$(timeout 300 python3 dsp4_s49_osc.py --strip "$OSC_STRIP" \
              --meas "$MEAS_STRIP" --freq "$FREQ" --level "$LV" \
              --symdir "/home/app/$D" 2>&1)
        lvl=$(echo "$R" | sed -n 's/.*RmsResult *\(-\?[0-9.]*\) dBFS.*/\1/p' | head -1)
        pct=$(echo "$R" | sed -n 's/.*ThdResult .*= *\([0-9.]*\) %.*/\1/p' | head -1)
        if [ -z "$lvl" ] || [ -z "$pct" ]; then
            echo "boot $i drive $LV: NO READING (ic-retries $L)"; rc=2; continue
        fi
        printf 'boot %d (ic-retries %s) drive %s : level %s dBFS  THD+N %s %%\n' \
               "$i" "$L" "$LV" "$lvl" "$pct"
        any=1
        awk -v l="$lvl" -v lo="$LVL_MIN" -v hi="$LVL_MAX" \
            'BEGIN{exit !(l>lo && l<hi)}' || { echo "  LOOP LEVEL OUT OF WINDOW ($LVL_MIN..$LVL_MAX dBFS): the cable is off this lane, the route is not up, or the preamp chain is not at the reference gain. A THD reading taken here means nothing."; rc=2; continue; }
        awk -v p="$pct" -v w="$worst" 'BEGIN{exit !(p>w)}' && { worst=$pct; worst_lvl=$lvl; }
        lvls="$lvls $LV:$lvl"
    done
    # The tracking check, across the drives this boot actually took.
    if [ "$(echo $lvls | wc -w)" -ge 2 ]; then
        msg=$(echo $lvls | awk -v tol="$TRACK_TOL" '
            { for (i = 1; i <= NF; i++) { split($i, a, ":"); d[i] = a[1]; l[i] = a[2] }
              for (i = 2; i <= NF; i++) {
                  want = d[i] - d[i-1]; got = l[i] - l[i-1]; e = got - want
                  if (e < 0) e = -e
                  if (e > tol) {
                      printf "%s -> %s dBFS of drive moved the return %.2f dB, expected %.2f (tolerance %s dB)", d[i-1], d[i], got, want, tol
                      exit } } }')
        if [ -n "$msg" ]; then
            echo "  LOOP DOES NOT TRACK THE DRIVE: $msg"
            echo "  Something in the path is compressing, limiting or railing, and"
            echo "  the THD beside it means nothing. Check, in this order: the 595"
            echo "  preamp chain (matrix-app leaves it at a gain that PINS the lane"
            echo "  -- write the reference image before measuring); the donor"
            echo "  strip's own CompOn/GateOn, which are ON out of dsp4_config.py"
            echo "  (S70-3); and whether the route was asserted at all."
            rc=2
        fi
    fi
    lvls=""
    sudo pinctrl set 6,24 op dh
done

[ "$any" = "1" ] || { echo "LOOP THD: INCONCLUSIVE -- no usable reading"; exit 2; }
[ "$rc" = "2" ] && { echo "LOOP THD: INCONCLUSIVE -- at least one reading was unusable (see above)"; exit 2; }
if awk -v w="$worst" -v l="$LIMIT" 'BEGIN{exit !(w<=l)}'; then
    printf 'LOOP THD: PASS  worst %s %% at %s dBFS, limit %s %% (strip %s -> strip %s)\n' \
           "$worst" "$worst_lvl" "$LIMIT" "$OSC_STRIP" "$MEAS_STRIP"
    exit 0
fi
printf 'LOOP THD: FAIL  worst %s %% at %s dBFS, limit %s %% (strip %s -> strip %s)\n' \
       "$worst" "$worst_lvl" "$LIMIT" "$OSC_STRIP" "$MEAS_STRIP"
echo "  This is the S88-1 shape: the digital word at the output slot can be a"
echo "  textbook sine and the wire still fold. Check DSP4_TX_DEFER before"
echo "  anything else -- MW/D24/DSP/s89/dac-fold-fix.md."
exit 1
