"""s70lib -- the standard test set on the D24 talkback input, with the loop CLOSED.

WHAT S70 ADDS TO s69lib. Three things S69 could not know:

1. THE LANE. Gate 0 with AN_EN high and the AUX 1 -> J1 cable fitted puts the tone on
   MeasChan 53 = `_buf_C1_XIN_CODEC_04` = TDM slot 3 = ADC2 Rch, at +41.75 dB, and on
   NEITHER of the other two received codec lanes. The netlist walk is right and the
   graph's `C1_XIN_CODEC_01` "Codec ADC 1 (TB XLR)" is misnamed (S69-1, settled).
2. THE ROUTE. A fresh boot+config leaves `Chan006AuxOn001` 0 and `Chan006AuxSend001`
   0.0, so the AUX 1 bus block is EXACTLY zero and the DAC sends nothing. Every S70 run
   asserts the route and PROVES it on MeasChan 35 before it measures anything.
3. THE CEILING, which is a real one. The AK4619's analog input pins take 3.3 Vpp each at
   AVDD 3.3 V (datasheet 2050) and their absolute maximum is the lower of AVDD+0.3 and
   4.3 V. The measured loop gain puts the ADC's full scale at the talkback XLR at
   -18.6 dBu at MGN +27 dB, i.e. about 6 dB of loss between J1 and the pins, so the
   oscillator must never go above about -7 dBFS whatever the gain code. Everything here
   is capped at OSC_MAX = -12 dBFS, 5 dB below that, and the cap is asserted not assumed.

   *** CORRECTED 2026-09-20 (S79). THE PARAGRAPH ABOVE IS LEFT AS IT STOOD BECAUSE IT IS
   THE REASONING THE OLD CAP RESTED ON, AND IT IS WRONG IN THE UNSAFE DIRECTION. ***

   There is no 6 dB of loss between J1 and the codec's pins. mx26's netlist walk
   (`docs/d24-analog-paths.md:130-131`, and independently `MW/D24/DSP/s71/codec-lanes.md`
   and `dsp4-s34-20260911.md`) puts ONE COUPLING CAPACITOR on each leg -- J1 pin 2 -> C4
   -> IN4N, pin 3 -> C11 -> IN4P -- and no divider, no pad and no resistor of any kind.
   The 6.16 dB S70 attributed to that loss is the datasheet's own notation: read
   "+/-2.83 Vpp" as PER PIN, the differential full scale is 5.66 Vpp = 2.001 Vrms =
   +8.24 dBu, and S70's loop-derived +8.36 dBu agrees with it to 0.12 dB. S70 raised the
   per-pin reading and dismissed it as "12 dB", which is a sign error: reading the
   number per pin makes the codec's differential full scale LARGER by 6 dB, so it CLOSES
   the gap. See MW/D24/DSP/s79/bypass.md section 1.

   The consequence for this file is not academic. With no pad, the pins see what J1 sees.
   Full scale at J1 is DAC_FS_DBU - loop_gain, and at OSC_MAX = -12 dBFS the DAC puts
   +11.13 dBu across J1 = 7.9 Vpp differential = about 3.95 Vpp PER PIN -- above the
   3.3 Vpp the pins are specified for and at the absolute maximum. The old cap was
   believed to sit 5 dB below the ceiling and in fact sat about 1 dB ABOVE it.

   So OSC_MAX is no longer a constant. `osc_ceiling()` derives it from the loop gain
   this rig actually measures and the codec's own differential full scale, with no pad
   term at all, and every oscillator call is still asserted against it.
"""
import json
import math
import os
import sys
import time

sys.path.insert(0, '/home/app/s69')
import s69lib as S69                                                     # noqa: E402

X = S69.X
FS = S69.FS
MGN_DB = S69.MGN_DB
MGN_INIT = S69.MGN_INIT
DAC_FS_DBU = S69.DAC_FS_DBU
pct = S69.pct

TALK = 53                    # S70: the talkback lane, measured -- CODEC_RET_4, slot 3
AUX1_BUS = 35                # the S67 bus tap: proves the DAC is being fed
DONOR = S69.DONOR
# THE CODEC'S DIFFERENTIAL FULL SCALE AT ITS OWN PINS, in dBu, read PER PIN
# (S79): 2.83 Vpp on each of IN4P/IN4N is 5.66 Vpp differential = 2.0011 Vrms.
AK4619_FS_DBU = 8.24
# ...and how far above it the pins may be driven before the 3.3 Vpp linear
# spec is exceeded: 20*log10(3.3/2.83).
AK4619_PIN_HEADROOM_DB = 1.34
# The margin this rig keeps below the codec's own full scale, in dB. ZERO,
# and that is the argument rather than an omission: at full scale the ADC is
# already clipping, so every dB above it buys no measurement at all and
# spends the 1.34 dB that is the pins' ONLY remaining margin. A positive
# margin here would also clamp the T1 ladder's own low-gain points (MGN
# code 0 needs -15.26 dBFS to put the lane at -6.5), i.e. it would stop the
# rig measuring the part where the part is linear.
OSC_MARGIN_DB = 0.0
# THE OLD CONSTANT, KEPT ONLY AS A CEILING ON THE CEILING. Nothing derives
# a level from it any more -- see osc_ceiling() -- but no arm may exceed it
# either, so a future change to the derivation cannot silently raise it.
OSC_MAX = -12.0              # hard cap on oscillator level (the codec's analog pin)
LOOP_AT_27 = 41.75           # gate 0, MGN2R code 11
VOL_0DB = 0x30               # ADC digital volume: 0x30 = 0.0 dB, 0.5 dB a step, HIGHER IS QUIETER
VOLAD2R = 0x09               # the ADC2 Rch digital volume register
DATA = '/home/app/s70/data'


def loop_est(code):
    """The loop gain expected at MGN2R `code`, from gate 0's measured +41.75 dB at +27 dB."""
    return LOOP_AT_27 + (MGN_DB[code] - 27.0)


def osc_ceiling():
    """The highest oscillator level this rig will pass, in dBFS.

    Derived, not declared (S79). The pins see J1, because the netlist puts
    nothing but a coupling cap on each leg, so the J1 level that reaches the
    codec's own full scale is `AK4619_FS_DBU` and the oscillator level that
    produces it is that minus the DAC's full scale. Stay `OSC_MARGIN_DB`
    below, and never above the old hard cap.

    On today's numbers (DAC full scale +23.13 dBu, codec +8.24 dBu) that is
    -14.89 dBFS, against the -12.00 dBFS this file used to pass: the old cap
    put +11.13 dBu across J1, 2.89 dB ABOVE the codec's full scale and about
    3.95 Vpp on each pin against a 3.3 Vpp rating."""
    osc_at_pin_fs = AK4619_FS_DBU - DAC_FS_DBU
    return min(OSC_MAX, osc_at_pin_fs - OSC_MARGIN_DB)


def osc_for(code, lane_peak_dbfs=-6.5):
    """Oscillator level that lands the lane at `lane_peak_dbfs` PEAK, capped at the pin ceiling.

    RmsResult reports a full-scale sine as -3.01 dBFS, so the peak is rms + 3.01 and the
    oscillator level IS the peak on its own side: lane_peak = osc + loop_gain."""
    return min(osc_ceiling(), lane_peak_dbfs - loop_est(code))


def vol_code(db):
    """ADC digital volume code for `db` of gain (Tables 11/14: attenuation, so higher = quieter)."""
    c = VOL_0DB - int(round(db / 0.5))
    if not 0 <= c <= 0xFE:
        raise SystemExit('ADC volume %+g dB is outside the table' % db)
    return c


def adc_fs_dbu(loop_gain_db):
    """ADC full scale at the talkback XLR for the code this loop gain was measured at (S57-R)."""
    return DAC_FS_DBU - loop_gain_db


def dbfs_to_dbu(dbfs, loop_gain_db):
    """A lane level in dBFS -> dBu at the talkback XLR, at the code `loop_gain_db` belongs to."""
    return dbfs + adc_fs_dbu(loop_gain_db)


class Rig(S69.Rig):
    def __init__(self, logpath='/home/app/s70/s70.jsonl'):
        os.makedirs(DATA, exist_ok=True)
        super().__init__(logpath)
        self.route()

    def route(self):
        """Strip 6 -> AUX 1 with the donor's OWN DYNAMICS BYPASSED, proved on the bus.

        THE DONOR STRIP IS PART OF THE INSTRUMENT AND IT IS NOT TRANSPARENT BY DEFAULT.
        `Chan006CompOn001` comes up 1 out of boot+config, and its threshold sits near
        -22 dBFS: above that the oscillator is compressed before it ever reaches the DAC.
        Measured 2026-09-19 -- strip 6's post-fader block, the AUX 1 bus and the talkback
        lane all read -1.391 / -2.891 / -4.391 / -5.141 dB low at oscillator -17 / -15 /
        -13 / -12 dBFS, the same three numbers to 0.01 dB, so the loss is upstream of the
        DAC and is the compressor. Left on, it reads as an analog overload knee that is
        not there. Nothing in s54lib/s69lib bypasses it."""
        self.c1.wv('Chan006CompOn001', 0)
        self.c1.wv('Chan006GateOn001', 0)
        self.c1.wv('Chan006TubeOn001', 0)
        for c in ('Chan006CompOn001', 'Chan006GateOn001', 'Chan006TubeOn001'):
            if self.c1.r(c) != 0:
                raise SystemExit('%s did not clear: the donor strip is not transparent' % c)
        self.c1.wv('Chan006AuxOn001', 1)
        self.c1.wv('Chan006AuxSend001', X.f32(1.0), ramp=1)
        time.sleep(0.4)
        send = X.from_f32(self.c1.r('Chan006AuxSend001'))
        if self.c1.r('Chan006AuxOn001') != 1 or abs(send - 1.0) > 1e-4:
            raise SystemExit('AUX 1 route did not land: on=%d send=%r'
                             % (self.c1.r('Chan006AuxOn001'), send))

    def prove_route(self, level_db=-40.0):
        """The AUX 1 bus must carry the tone, or nothing downstream means anything."""
        self.osc(freq=1000.0, level_db=level_db, on=True)
        self.meas(AUX1_BUS)
        rms = self.point(3)['rms_dbfs']
        if abs(rms - (level_db - 3.01)) > 0.2:
            raise SystemExit('AUX 1 bus reads %.3f dBFS, expected %.3f: the DAC is not being fed'
                             % (rms, level_db - 3.01))
        return rms

    def osc(self, freq=None, level_db=None, on=True, chan=DONOR):
        cap = osc_ceiling()
        if level_db is not None and level_db > cap + 1e-9:
            raise SystemExit(
                'oscillator %.2f dBFS is above the %.2f dBFS cap: with no pad '
                'between J1 and the codec pins (S79) that level puts %.2f dBu '
                'across J1, and the AK4619 reaches full scale at %.2f dBu'
                % (level_db, cap, DAC_FS_DBU + level_db, AK4619_FS_DBU))
        return S69.Rig.osc(self, freq=freq, level_db=level_db, on=on, chan=chan)

    def tone(self, freq, level_db, chan=TALK, n=3):
        """One settled measurement: the results window and the coherent fit together."""
        self.osc(freq=freq, level_db=level_db, on=True)
        self.meas(chan)
        p = self.point(n)
        p.update(self.fit())
        p['osc_dbfs'] = level_db
        p['freq_hz'] = freq
        p['chan'] = chan
        return p

    def volad2r(self, db):
        """ADC2 Rch digital volume, in dB of gain. Restores with db=0."""
        self.codec_reg(VOLAD2R, vol_code(db))


def save(name, obj):
    p = os.path.join(DATA, name)
    json.dump(obj, open(p, 'w'), indent=1)
    print('written', p, flush=True)
    return p
