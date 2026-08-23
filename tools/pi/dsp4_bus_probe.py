#!/usr/bin/env python3
"""dsp4_bus_probe — fader gain/pan law and the main bus accumulator.

Chain: IN -> GAIN -> FILT -> EQ -> GATE -> COMP -> TUBE -> DLY -> FDR -> RTG -> BUS

Captures three points for the same stimulus so the fader's own stages can
be told apart:
    _buf_C1_FDR_01     mono post-fader   (x * gq)
    _buf_L_C1_FDR_01   pan-split left
    _buf_C1_BUS_MAIN_L bus readout after _acc64_rns28

FDR level and pan are RAMPED (GainFast) and must be written with
ramp_id=1; with ramp_id=0 the node clobbers them from an unset target.
FDR decrements its frame count once per BLOCK and spi_handler scales the
count by 32, so a level change takes ~128 blocks (~85 ms) to settle.
"""
import argparse, struct, sys, time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S
from dsp4_tubedly_probe import wrv, transparent_chain, f32, DLY_OFF

FDR_LEVEL, FDR_PAN, FDR_MUTE, FDR_DCA = 0x0050, 0x0051, 0x0052, 0x0053


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--level', type=float, default=1.0)
    ap.add_argument('--pan', type=float, default=0.5)
    ap.add_argument('--amp', default='0x08000000')
    a = ap.parse_args()

    sc = S.Scope(1)
    sc.check_chip()
    inj = sc.sym['_rx_slot_C1_IN_01']
    transparent_chain(sc)
    wrv(sc, DLY_OFF, 0)
    wrv(sc, FDR_MUTE, 0)
    wrv(sc, FDR_DCA, f32(1.0), ramp_id=1, settle=0.05)
    wrv(sc, FDR_LEVEL, f32(a.level), ramp_id=1, settle=0.05)
    wrv(sc, FDR_PAN, f32(a.pan), ramp_id=1, settle=0.05)
    time.sleep(0.6)                       # FDR ramps at block rate, ~85 ms

    amp = int(a.amp, 16)
    out = []
    for name in ('_buf_C1_FDR_01', '_buf_L_C1_FDR_01', '_buf_C1_BUS_MAIN_L'):
        sc.arm(sc.sym[name], inj, amp, 2)     # step
        sc.wait()
        v = sc.fetch(8)[7]
        out.append(v - (1 << 32) if v & 0x80000000 else v)
    print('FDR level=%g pan=%g in=%d mono=%d L=%d bus=%d'
          % (a.level, a.pan, amp, out[0], out[1], out[2]))


if __name__ == '__main__':
    main()
