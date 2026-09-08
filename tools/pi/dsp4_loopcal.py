#!/usr/bin/env python3
"""dsp4_loopcal.py — calibrate the Pi <-> CPLD <-> DSP audio loop.

Step 1 of the virtual-audio block: prove the loop is a measurement channel
before anything is measured through it. Three questions, in order, because
each one's answer decides how to read the next:

  PHASE     WHICH captured channel carries the stimulus? The Pi is an I2S
            SLAVE and LOGIC regroups four Pi frames into one DSP frame, so
            the word the stream starts on is not fixed: measured across
            consecutive runs 2026-09-08, the same stimulus came back on L
            in one capture and on R in the next. Every capture is phased
            before it is read, and the phase is reported. Reading a fixed
            channel is what made one run print "ratio 0.0000" for a loop
            that was working.

  SUMMING   Is the return the sum of the two played channels? The Pi input
            feeds a MONO main mix, so a stimulus played into both channels
            could come back at twice its amplitude. L-only, R-only and both
            settle it.

  GAIN      With the summing known, does a known word return unchanged?
            A DC word is used deliberately: no filter or sample-timing
            effect can blur it, so whatever comes back IS the path.

  LATENCY   How many samples late? The stimulus is a per-word counter, so
            every word carries its own index and the delay is read off the
            words themselves rather than off wall-clock timing. One device
            carries both directions (dsp4-pcm-duplex), so playback and
            capture share one hw_params and one DMA start.

The loop must be in PASS-THROUGH first: sixteen of the seventeen sources
that sum into C2_MIX_MAIN_L silenced, main fader at unity, main delay zero.
`passthru_setup.py` does that from the landed contract; this tool measures
what it produced and reports a PEDESTAL if anything else is still summing
in, because a DC offset under the stimulus makes every ratio below a lie.

Usage, on the bench:
    python3 dsp4_loopcal.py [--rate 192000] [--words 96000] [--json out.json]
"""

import argparse
import json
import os
import struct
import subprocess
import sys
import time

REC_DEV = os.environ.get('REC_DEV', 'hw:dsp4pcm,0')
PLAY_DEV = os.environ.get('PLAY_DEV', 'hw:dsp4pcm,0')
BUF = '--buffer-size=16384'


def play_capture(stim, rate, secs=None):
    """Play `stim` (a list of (L, R) pairs) while capturing. Returns the
    captured interleaved words, or None if either side reported an xrun --
    an xrun makes every number derived from the capture fiction."""
    raw = b''.join(struct.pack('<ii', l, r) for l, r in stim)
    open('/tmp/lc_play.raw', 'wb').write(raw)
    secs = secs or int(len(stim) / rate) + 2
    rec = subprocess.Popen(
        ['arecord', '-D', REC_DEV, '-f', 'S32_LE', '-c', '2', '-r', str(rate),
         '-d', str(secs), BUF, '-t', 'raw', '-q', '/tmp/lc_cap.raw'],
        stderr=subprocess.PIPE)
    time.sleep(0.3)
    pl = subprocess.run(
        ['aplay', '-D', PLAY_DEV, '-f', 'S32_LE', '-c', '2', '-r', str(rate),
         BUF, '-t', 'raw', '-q', '/tmp/lc_play.raw'], capture_output=True)
    _, rerr = rec.communicate()
    err = ((rerr or b'') + (pl.stderr or b'')).decode(errors='replace')
    if 'run' in err:                      # over- or underrun
        return None, err.strip()[:80]
    d = open('/tmp/lc_cap.raw', 'rb').read()
    return struct.unpack('<%di' % (len(d) // 4), d), ''


NOISE_FLOOR = 0x20        # -160 dBFS; the idle residue on the dead slot


def dominant(vals):
    """The most common non-zero value, and how many frames carried it."""
    from collections import Counter
    nz = [v for v in vals if v]
    if not nz:
        return None, 0, len(vals)
    v, n = Counter(nz).most_common(1)[0]
    return v, n, len(vals)


def phased(cap):
    """(words, 'L'|'R') — the captured channel actually carrying signal.

    `C2_MAIN_ST_OUT` drives ONE TDM slot, so exactly one captured channel
    carries the return and the other idles at a few LSB. Which one is not
    fixed across stream starts (see PHASE above), so it is detected rather
    than assumed."""
    ch = {'L': [x & 0xFFFFFFFF for x in cap[0::2]],
          'R': [x & 0xFFFFFFFF for x in cap[1::2]]}
    peaks = {k: max((v if v < (1 << 31) else (1 << 32) - v for v in s),
                    default=0) for k, s in ch.items()}
    which = 'L' if peaks['L'] >= peaks['R'] else 'R'
    return ch[which], which, peaks


def dc_word(rate, w, chan, secs=2):
    """Play a DC word into one channel (or both) and read what returns."""
    n = rate * secs
    if chan == 'L':
        stim = [(w, 0)] * n
    elif chan == 'R':
        stim = [(0, w)] * n
    else:
        stim = [(w, w)] * n
    cap, err = play_capture(stim, rate, secs + 2)
    if cap is None:
        return {'chan': chan, 'in': w, 'verdict': 'XRUN', 'error': err}
    sig, which, peaks = phased(cap)
    got, n_got, n_tot = dominant([v for v in sig if v > NOISE_FLOOR])
    return {'chan': chan, 'in': w, 'out': got, 'frames': n_got,
            'total': len(sig), 'returned_on': which,
            'peaks': {k: '0x%08X' % v for k, v in peaks.items()},
            'ratio': (got / w) if (got and w) else None}


def pedestal(rate, secs=2):
    """Capture with NOTHING played. Anything non-zero on the MEASUREMENT
    channel is another source still summing into the main bus, and it
    invalidates every amplitude measured afterwards.

    PER CHANNEL, and that is not fussiness. `C2_MAIN_ST_OUT` writes TDM
    slot 0 only despite declaring two channels, so the return's R is not
    a copy of anything and carries a small constant residue. Counting
    both channels together reported "PEDESTAL PRESENT" on a loop whose L
    was exactly zero — the residue was 8 LSB on R, about -168 dBFS, and
    it says nothing about the measurement channel."""
    rec = subprocess.run(
        ['arecord', '-D', REC_DEV, '-f', 'S32_LE', '-c', '2', '-r', str(rate),
         '-d', str(secs), BUF, '-t', 'raw', '-q', '/tmp/lc_ped.raw'],
        capture_output=True)
    d = open('/tmp/lc_ped.raw', 'rb').read()
    w = struct.unpack('<%di' % (len(d) // 4), d)
    out = {'xrun': 'run' in (rec.stderr or b'').decode(errors='replace')}
    for name, sl in (('L', w[0::2]), ('R', w[1::2])):
        out[name] = {'words': len(sl),
                     'non_zero': sum(1 for v in sl if v),
                     'peak': max((abs(v) for v in sl), default=0)}
    # CLEAN means no source is summing into the bus, and a few LSB on the
    # slot nothing drives is not a source. The threshold is the idle
    # residue measured on this loop (8 LSB, about -168 dBFS).
    out['clean'] = all(out[c]['peak'] <= NOISE_FLOOR for c in ('L', 'R'))
    return out


def latency(rate, words, gain=1.0):
    """Counter stimulus: word i carries i, so the delay is in the data.

    GUARD FIRST. The capture starts before the play does, so the head of
    the capture is whatever the loop held; the counter starts after a run
    of zeros and the first non-zero word is the arrival of counter 1."""
    guard = 8192
    stim = [(0, 0)] * guard + [(((i + 1) << 8), ((i + 1) << 8))
                               for i in range(words)]
    cap, err = play_capture(stim, rate)
    if cap is None:
        return {'verdict': 'XRUN', 'error': err}
    L, which, _ = phased(cap)
    first = next((i for i, v in enumerate(L) if v > NOISE_FLOOR), None)
    if first is None:
        return {'verdict': 'NOTHING_CAPTURED'}
    # The counter climbs by 1 per FRAME. Read the index the loop returns at
    # a series of capture positions and take the offset each implies; a
    # loop with a fixed delay gives the same offset every time, and one
    # that does not is not a measurement channel.
    offs, seq = [], []
    for k in range(first, min(first + 4096, len(L))):
        v = L[k]
        if v <= NOISE_FLOOR:
            continue
        # NORMALISE BY THE MEASURED GAIN before reading the index back
        # out of the word. The loop is not obliged to return what it was
        # given: at a path gain of 2 the counter comes back doubled, every
        # implied offset is wrong by the index itself, and the run reports
        # NO_COUNTER on a loop that is working perfectly well.
        idx = int(round(((v >> 8) & 0xFFFFFF) / gain))
        if idx <= 0:
            continue
        seq.append((k, idx))
        offs.append(k - idx)
    if not offs:
        return {'verdict': 'NO_COUNTER'}
    from collections import Counter
    off, n = Counter(offs).most_common(1)[0]
    steps = [seq[i + 1][1] - seq[i][1] for i in range(len(seq) - 1)]
    climb = sum(1 for s in steps if s == 1)
    return {'verdict': 'OK' if climb > 0.98 * max(1, len(steps)) else 'RAGGED',
            'offset_frames': off, 'offset_agreement': n / len(offs),
            'consecutive_steps': climb, 'steps': len(steps),
            'first_non_zero': first, 'returned_on': which}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--rate', type=int, default=192000)
    ap.add_argument('--words', type=int, default=96000)
    ap.add_argument('--json', default=None)
    a = ap.parse_args()

    out = {'rate': a.rate, 'rec_dev': REC_DEV, 'play_dev': PLAY_DEV}

    print('== pedestal: capture with nothing played ==')
    out['pedestal'] = pedestal(a.rate)
    p = out['pedestal']
    for ch in ('L', 'R'):
        print('  %s: %d words, %d non-zero, peak 0x%08X'
              % (ch, p[ch]['words'], p[ch]['non_zero'], p[ch]['peak']))
    if p['xrun']:
        print('  XRUN — this capture is not a measurement')
    if p['clean']:
        print('  NO PEDESTAL on the measurement channel')
    else:
        print('  PEDESTAL PRESENT on L — another source is still summing '
              'into the main bus; the ratios below are not trustworthy')

    print('== summing: the same word into L only, R only, both ==')
    out['summing'] = [dc_word(a.rate, 0x00100000, c) for c in ('L', 'R', 'LR')]
    for r in out['summing']:
        print('  played %-2s -> returned on %s: 0x%08X -> %s  ratio %s  '
              '(%s/%s frames)'
              % (r['chan'], r.get('returned_on', '?'), r['in'],
                 ('0x%08X' % r['out']) if r.get('out') else r.get('verdict'),
                 ('%.4f' % r['ratio']) if r.get('ratio') else '-',
                 r.get('frames'), r.get('total')))

    print('== gain: known words, both channels ==')
    out['gain'] = [dc_word(a.rate, w, 'LR')
                   for w in (0x00001000, 0x00010000, 0x00100000)]
    for r in out['gain']:
        print('  in 0x%08X -> out %s  ratio %s  (returned on %s)'
              % (r['in'], ('0x%08X' % r['out']) if r.get('out')
                 else r.get('verdict'),
                 ('%.4f' % r['ratio']) if r.get('ratio') else '-',
                 r.get('returned_on', '?')))

    print('== latency: counter stimulus ==')
    # the gain the loop was just measured to have, so the counter can be
    # read back out of the returned words whatever the path does to them
    g = next((r['ratio'] for r in out['gain']
              if r.get('ratio')), 1.0)
    out['measured_gain'] = g
    out['latency'] = latency(a.rate, a.words, g)
    lt = out['latency']
    if lt.get('offset_frames') is not None:
        print('  %s: %d frames at %d Hz = %.3f ms  '
              '(%.1f%% of positions agree, %d/%d consecutive +1 steps)'
              % (lt['verdict'], lt['offset_frames'], a.rate,
                 lt['offset_frames'] / a.rate * 1000.0,
                 lt['offset_agreement'] * 100.0,
                 lt['consecutive_steps'], lt['steps']))
    else:
        print('  %s %s' % (lt.get('verdict'), lt.get('error', '')))

    if a.json:
        json.dump(out, open(a.json, 'w'), indent=1, sort_keys=True)
        print('wrote %s' % a.json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
