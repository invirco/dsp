#!/usr/bin/env python3
"""dsp4_s29_playpath.py — WHERE THE PLAYBACK SIGNAL STOPS (S29 gate 4).

S12-10, S17 and S27-7 all end in the same place: the through-DSP latency
arm scores 0.0 % coherent at every offset, and the DSP's own main chain
reads a CONSTANT from C2_MIX_MAIN_L to C2_MAIN_ST_OUT with the CM4
playing.  S27-7 narrowed the break to "upstream of the DSP, on the
playback side" and stopped there, because reading the END of a chain
tells you it is dead and not where it died.

THIS TOOL READS EVERY STAGE OF THE PLAYBACK CHAIN, IN ORDER, ON BOTH
CHIPS, AND REPORTS THE FIRST ONE THAT IS NOT MOVING.

The chain, from the CPLD to the capture lane (dsp.csv, slot-map.csv):

    pcm_tdm (LOGIC re-framer)  ->  i_dspa[6]      A_I6 slots 0,1
      C1_XIN_PI_L / _R         INPUT_TDM   sport 6, slots 0/1
      C1_XS_XFER_PI_L / _R     INTERCHIP_SEND  sport 1, slots 11/12
                               ->  MIX_1 global slots 27,28
      C2_XR_PI_L / _R          INTERCHIP_RECV  sport 1, slots 11/12
      C2_PI_IN                 AUX_INPUT   (Pi001On/Pi001Level)
      C2_MIX_MAIN_L / _R       MIX_BUS
      C2_MAIN_FDR -> ... -> C2_MAIN_DLY -> C2_MAIN_ST_OUT  -> B_O3

A STAGE THAT IS MOVING IS NOT NECESSARILY RIGHT, AND THAT IS THE POINT
OF THE CONTROL.  Every stage is sampled N times with the stimulus
PLAYING and N times with it STOPPED, and a stage is called live only if
its samples move while playing AND are constant (or differently
distributed) when they are not.  A buffer that changes in both states is
noise or a free-running counter, not the stimulus; a buffer that is
constant in both is dead.  Without the silent control a moving word
proves nothing, which is the shape of error this whole programme keeps
finding.

The caller owns the stimulus.  `--play-cmd` / `--stop-cmd` default to
drive_audio.sh, which is what the driven capacity rows use.

Usage:
  dsp4_s29_playpath.py                       both chips, 12 samples a stage
  dsp4_s29_playpath.py --samples 20
  dsp4_s29_playpath.py --no-silent-control   (says so in the output)
"""
import argparse
import subprocess
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

# (chip, symbol, what it is).  Order IS the chain order: the first dead
# stage is the break.
CHAIN = [
    (1, '_buf_C1_XIN_PI_L',     'A_I6 slot 0 -> chip 1 input kernel'),
    (1, '_buf_C1_XIN_PI_R',     'A_I6 slot 1 -> chip 1 input kernel'),
    # C1_XS_XFER_PI_L/R have NO _buf_ of their own -- an INTERCHIP_SEND
    # writes straight into the TX DMA region -- so the send is observed
    # from the other side, at C2_XR_PI_*.  A break between the two shows
    # as XIN live and XR dead, which is enough to place it.
    (2, '_buf_C2_XR_PI_L',      'chip 2 inter-chip recv, MIX_1 slot 11'),
    (2, '_buf_C2_XR_PI_R',      'chip 2 inter-chip recv, MIX_1 slot 12'),
    (2, '_buf_C2_PI_IN',        'Pi playback AUX_INPUT (Pi001On/Level)'),
    (2, '_buf_C2_MIX_MAIN_L',   'main mix bus L'),
    (2, '_buf_C2_MIX_MAIN_R',   'main mix bus R'),
    (2, '_buf_C2_MAIN_FDR',     'main fader/pan'),
    (2, '_buf_C2_MAIN_DLY',     'main delay'),
    (2, '_buf_C2_MAIN_ST_OUT',  'main stereo out -> B_O3 (the capture lane)'),
]

# THE CONTROL THAT IS NOT PART OF THE CHAIN.  One of chip 1's ADC input
# kernels: on the `driveall` bitstream it carries the same stimulus, on
# `maincap` it carries whatever the converters do.  Reading it beside the
# chain separates "the CM4 is not playing" from "the Pi lane is dead".
WITNESS = [
    (1, '_buf_C1_IN_01',        'ADC lane 0 slot 0 (bitstream witness)'),
    (2, '_buf_C2_RECV_MAIN_L',  "chip 1's 32-strip bus into main (must be "
                                'DEAD after the pass-through setup)'),
]


def sample(sc, addr, n, dwell):
    vals = []
    for _ in range(n):
        try:
            vals.append(sc.peek(addr))
        except Exception as exc:            # noqa: BLE001 - reported, not raised
            vals.append(None)
            if len(vals) == 1:
                print('    (first read failed: %s)' % exc)
        time.sleep(dwell)
    return vals


def describe(vals):
    good = [v for v in vals if v is not None]
    if not good:
        return 'UNREADABLE', '-'
    uniq = sorted(set(good))
    if len(uniq) == 1:
        return 'CONSTANT', '0x%08x' % uniq[0]
    return 'MOVING', '%d distinct, e.g. %s' % (
        len(uniq), ' '.join('0x%08x' % v for v in uniq[:3]))


def run(scopes, rows, n, dwell):
    out = {}
    for chip, symbol, what in rows:
        sc = scopes.get(chip)
        if sc is None or symbol not in sc.sym:
            out[symbol] = ('ABSENT', 'not in chip %d.sym.json' % chip, what)
            continue
        state, detail = describe(sample(sc, sc.sym[symbol], n, dwell))
        out[symbol] = (state, detail, what)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--samples', type=int, default=12)
    ap.add_argument('--dwell', type=float, default=0.08,
                    help='seconds between samples of one stage')
    ap.add_argument('--play-cmd',
                    default='bash /home/app/drive_audio.sh start')
    ap.add_argument('--stop-cmd',
                    default='bash /home/app/drive_audio.sh stop')
    ap.add_argument('--no-silent-control', action='store_true',
                    help='skip the stimulus-off pass. The report says so; a '
                         'moving word then proves nothing on its own.')
    a = ap.parse_args()

    rows = CHAIN + WITNESS
    scopes = {}
    for chip in sorted({c for c, _, _ in rows}):
        scopes[chip] = S.Scope(chip)
        scopes[chip].d.resync()
        # REFUSE THE WRONG PART. A card that came up as two chip 1s reads
        # healthy through every other register and answers chip 2's symbol
        # addresses with chip 1's memory (2026-08-23, and S8-3's pin
        # sequence is why it can still happen). A chain walk is exactly the
        # measurement that would not notice.
        scopes[chip].check_chip()

    silent = {}
    if not a.no_silent_control:
        subprocess.run(a.stop_cmd, shell=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2.0)
        print('=== stimulus STOPPED (the control)')
        silent = run(scopes, rows, a.samples, a.dwell)

    subprocess.run(a.play_cmd, shell=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(3.0)
    print('=== stimulus PLAYING')
    playing = run(scopes, rows, a.samples, a.dwell)

    print()
    print('%-26s %-10s %-10s  %s' % ('stage', 'silent', 'playing', 'what'))
    first_dead = None
    for chip, symbol, what in CHAIN:
        sp, dp, _ = playing[symbol]
        ss = silent.get(symbol, ('not taken', '', ''))[0]
        live = (sp == 'MOVING') and (a.no_silent_control or ss != 'MOVING')
        if not live and first_dead is None:
            first_dead = (symbol, what, sp, dp, ss)
        print('%-26s %-10s %-10s  %s' % (symbol, ss, sp, what))
        print('%-26s %-21s  %s' % ('', '', dp))
    for chip, symbol, what in WITNESS:
        sp, dp, _ = playing[symbol]
        ss = silent.get(symbol, ('not taken', '', ''))[0]
        print('%-26s %-10s %-10s  %s  [%s]' % (symbol, ss, sp, what, dp))

    print()
    if a.no_silent_control:
        print('NOTE: the stimulus-off control was NOT taken, so "MOVING" here '
              'means "not constant", not "carrying the stimulus".')
    if first_dead is None:
        print('THE WHOLE PLAYBACK CHAIN IS LIVE: every stage moves with the '
              'stimulus and not without it.')
        return 0
    sym, what, sp, dp, ss = first_dead
    print('THE BREAK IS AT %s (%s): %s while playing (%s), %s silent.'
          % (sym, what, sp, dp, ss))
    return 1


if __name__ == '__main__':
    sys.exit(main())
