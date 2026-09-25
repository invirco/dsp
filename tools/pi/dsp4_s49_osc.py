#!/usr/bin/env python3
"""dsp4_s49_osc.py — drive the S49 self-test cells and read the results back.

NEEDS A `DSP4_TEST_NODES=1` IMAGE. Without it the sixteen words still exist
and still take writes -- they are in the dispatch table either way -- and
nothing reads them, so every result stays at its initialiser. The tool checks
for the flag by looking for `_osc_blk_q_C1_TEST_OSC` in the staged symbol map,
which only exists inside the guard, and refuses otherwise. That check is not
optional politeness: a run against a shipping image would print four zeros and
they would look exactly like a measurement.

WHAT IT DOES. Sets OscFreq / OscLevel / OscChan / OscOn, points MeasChan at a
strip, optionally sets the crosstalk pair, waits for the window serial to
advance TWICE (the first window after any change has no fit yet and reads
ThdResult 0.00 dB by construction -- see the TEST_MEAS header), and prints
RmsResult / ThdResult / NoiseResult / XtalkResult.

THE DIGITAL LOOP, and why it needs no cable. The oscillator is injected into
the strip's INPUT BLOCK, after the input kernel has filled it from the
converter lane and before anything reads it, so the whole strip -- trim, HPF,
EQ, gate, compressor, tube, delay, fader -- is between the stimulus and the
tap. That is a real signal path measured end to end with nothing analog in it,
which is exactly what is available while the analog loop is not.

ADDRESSES. The sixteen words are chip 1, page 1, 4967..4982 in the S49 graph
(`MW/D32/DSP/SHARC/dsp.csv`, expanded by `MW/D32/DSP/gen_dsp.py`). They are
NOT in `landed-d24.json`, because the `Test[1-1]*` cells are not in any
product's `_matrix.csv` yet -- D24 and D32 do not declare the `util` scope, so
the expander never emits them. See `proposals/CONTRACT-PROPOSAL-S49.md`. Until
that lands the addresses are reached by number, and this tool PROVES each one
by writing a value and reading it back, and by peeking the symbol the map says
it should be.

Usage:
  dsp4_s49_osc.py [--strip N] [--freq HZ] [--level DBFS] [--meas N]
                  [--xsrc N] [--xdst N] [--windows N] [--off] [--symdir DIR]
                  [--ramp-ms MS] [--then-off]

THE RAMP (S110), and why a test that plays a tone out of a SPEAKER needs one.
`OscOn 0` cuts the sine at whatever instant the write lands, and that step is a
click with the full bandwidth of the converter behind it. Into the digital loop
that is harmless; out of the panel speaker it is an audible tick, and it lands
in the measurement window that follows -- the first tone-off baseline S110 took
after an abrupt stop read -38.15 dBFS against a settled floor of -58, a 20 dB
error made entirely by the harness. `--ramp-ms` fades OscLevel in equal dB
steps into the target on the way up and away from it on the way down, so the
speaker is never asked for a step. Default 0 = the old behaviour exactly, so
every existing caller is unchanged.

`--then-off` fades the tone out and leaves `OscOn 0` in the SAME session, and
prints how long the oscillator was actually on. Two invocations -- one to play,
one to stop -- cannot do that: the second one's interpreter start, link resync
and chip check all happen with the tone still sounding, which on this unit adds
two to four seconds of speaker to every measurement. A test that plays a tone
out of a panel speaker states its on-time; this is how it gets one.
"""
import argparse
import json
import math
import struct
import sys
import time

_ARGV = sys.argv[1:]
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S                                       # noqa: E402

# ---- the S49 address block (chip 1, page 1) ------------------------------
MEAS_BASE = 4967
OSC_BASE = 4975
A_MEASCHAN, A_RMS, A_THD, A_NOISE = (MEAS_BASE + i for i in range(4))
A_XSRC, A_XDST, A_XTALK, A_SEQ = (MEAS_BASE + 4 + i for i in range(4))
A_OSCON, A_OSCFREQ, A_OSCLEVEL, A_OSCCHAN = (OSC_BASE + i for i in range(4))
A_SWEEPON, A_SWEEPSTEP = OSC_BASE + 4, OSC_BASE + 5

# The symbols the SPI dispatch table points these addresses at. THEIR MAP
# ADDRESSES ARE NOT THE SPI ADDRESSES and are not compared with them -- a DM
# word address and a dispatch-table index are different things, and S48-8 is
# the record of confusing a stale map for a wrong value. What the map is used
# for here is EXISTENCE: every one of these must be in the running image's own
# map, which is what says this is a self-test build at all. The addresses
# themselves are proven the only way they can be, by writing and reading back.
ADDR_SYMS = {
    '_meas_chan_C1_TEST_MEAS':  A_MEASCHAN,
    '_meas_rms_C1_TEST_MEAS':   A_RMS,
    '_meas_thd_C1_TEST_MEAS':   A_THD,
    '_meas_noise_C1_TEST_MEAS': A_NOISE,
    '_meas_xsrc_C1_TEST_MEAS':  A_XSRC,
    '_meas_xdst_C1_TEST_MEAS':  A_XDST,
    '_meas_xtalk_C1_TEST_MEAS': A_XTALK,
    '_meas_seq_C1_TEST_MEAS':   A_SEQ,
    '_osc_on_C1_TEST_OSC':      A_OSCON,
    '_osc_freq_C1_TEST_OSC':    A_OSCFREQ,
    '_osc_level_C1_TEST_OSC':   A_OSCLEVEL,
    '_osc_chan_C1_TEST_OSC':    A_OSCCHAN,
    '_osc_sweep_on_C1_TEST_OSC':   A_SWEEPON,
    '_osc_sweep_step_C1_TEST_OSC': A_SWEEPSTEP,
}

# The measurement window, from dsp_block.h. One window is 256 blocks of 16
# samples at 48 kHz.
WIN_SAMPLES = 256 * 16
WIN_S = WIN_SAMPLES / 48000.0


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def from_f32(w):
    return struct.unpack('<f', struct.pack('<I', w & 0xFFFFFFFF))[0]


def pct(db):
    """A ratio in dB as percent, the ruled companion of every THD/THD+N
    figure (PW 2026-09-16): % = 100 * 10^(dB/20)."""
    return '%.5f %%' % (100.0 * 10.0 ** (db / 20.0))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strip', type=int, default=5,
                    help='strip the oscillator is injected into')
    ap.add_argument('--meas', type=int, default=None,
                    help='strip measured (default: the same one)')
    ap.add_argument('--freq', type=float, default=1000.0)
    ap.add_argument('--level', type=float, default=-6.0,
                    help='dBFS PEAK of the injected sine (0 = full scale)')
    ap.add_argument('--xsrc', type=int, default=0)
    ap.add_argument('--xdst', type=int, default=0)
    ap.add_argument('--windows', type=int, default=3,
                    help='windows to wait before reading (>=2; the first '
                         'after any change has no fit and reads 0.00 dB)')
    ap.add_argument('--off', action='store_true',
                    help='oscillator OFF: NoiseResult is then the strip\'s '
                         'own floor in dBFS and ThdResult reads 0.00 dB')
    ap.add_argument('--sweep', type=int, default=0, metavar='STEPS',
                    help='S60: run the periodic 20 Hz-20 kHz log CHIRP '
                         '(SweepOn 1) with a period of STEPS x 1024 samples '
                         '(16 = one 16,384 capture). The windows then read '
                         'RMS only; analyse with dsp4_fft.py --chirp')
    ap.add_argument('--ramp-ms', type=float, default=0.0, metavar='MS',
                    help='fade OscLevel in (or, with --off, out) over MS '
                         'milliseconds instead of stepping it. 0 = no ramp, '
                         'the historical behaviour. Wanted whenever the tone '
                         'leaves the box through the speaker: an abrupt stop '
                         'is a click, and the click lands in the next '
                         'measurement window (S110).')
    ap.add_argument('--then-off', action='store_true',
                    help='after the windows are read, fade out (honouring '
                         '--ramp-ms) and leave the oscillator OFF, in this '
                         'same session. Prints the measured on-time.')
    ap.add_argument('--symdir', default='/home/app/s49')
    ap.add_argument('--json', default=None, help='write the results here too')
    a = ap.parse_args(_ARGV)
    meas = a.meas if a.meas is not None else a.strip

    sc = S.Scope(1, symfile='%s/chip1.sym.json' % a.symdir)
    sc.d.resync()
    sc.check_chip()

    # ---- the image must be a self-test build -----------------------------
    if '_osc_blk_q_C1_TEST_OSC' not in sc.sym:
        raise SystemExit(
            'not a DSP4_TEST_NODES=1 image: _osc_blk_q_C1_TEST_OSC is absent '
            'from %s/chip1.sym.json. The sixteen cells exist in every image '
            'and take writes in every image; only this one reads them.'
            % a.symdir)

    print('S49 — self-test oscillator and measurement')
    print('  symbols: %s' % a.symdir)
    print('  inject : strip %d   measure: strip %d' % (a.strip, meas))
    print('  tone   : %.3f Hz at %.2f dBFS peak %s'
          % (a.freq, a.level, '(OFF)' if a.off else ''))
    print('  window : %d samples, %.1f ms' % (WIN_SAMPLES, 1000 * WIN_S))
    print('')

    # ---- prove the addresses before using them ---------------------------
    missing = [s_ for s_ in ADDR_SYMS if s_ not in sc.sym]
    if missing:
        raise SystemExit('symbols absent from the running image\'s map: %s'
                         % ', '.join(missing))
    print('  the map places all %d self-test symbols. The SPI addresses are'
          % len(ADDR_SYMS))
    print('  dispatch-table indices, a different thing from a DM address --')
    print('  they are proven below by write and read-back, not by the map.')

    def w(addr, val, tag):
        sc.d.link.write(addr, val & 0xFFFFFFFF, 0)
        time.sleep(S.SETTLE)
        got = sc.rd(addr)
        ok = (got == (val & 0xFFFFFFFF))
        print('    %-12s %5d <- 0x%08X   read 0x%08X  %s'
              % (tag, addr, val & 0xFFFFFFFF, got, 'OK' if ok else 'MISMATCH'))
        if not ok:
            raise SystemExit('write to %d did not land' % addr)

    # THE RAMP. Equal dB steps: a linear fade of a float amplitude spends
    # most of its time near the top and still steps audibly at the bottom,
    # and what the ear (and the mic) answers to is dB.
    RAMP_FLOOR_DB = -60.0        # where a fade starts and ends
    RAMP_STEPS = 24
    amp = 10.0 ** (a.level / 20.0)

    def ramp(lo_amp, hi_amp, ms, up):
        """Walk OscLevel between two amplitudes over `ms` milliseconds.
        Written without the read-back `w()` does: 24 verified writes cost
        24 x SETTLE of dead time inside a fade that is supposed to be
        smooth, and the END of the ramp is verified by `w()` anyway."""
        if ms <= 0 or lo_amp <= 0 or hi_amp <= 0:
            return
        dt = (ms / 1000.0) / RAMP_STEPS
        for i in range(1, RAMP_STEPS + 1):
            f = i / float(RAMP_STEPS)
            if not up:
                f = 1.0 - f
            a_ = lo_amp * (hi_amp / lo_amp) ** f
            sc.d.link.write(A_OSCLEVEL, f32(a_), 0)
            time.sleep(max(dt, S.SETTLE))
        print('    %-12s %s over %.0f ms in %d equal-dB steps'
              % ('OscLevel', 'fade UP' if up else 'fade DOWN', ms, RAMP_STEPS))

    floor_amp = amp * 10.0 ** (RAMP_FLOOR_DB / 20.0)

    print('')
    print('  arming:')
    # A ramped STOP has to happen BEFORE the arming write that kills the
    # oscillator, which is why this sits above `w(A_OSCON, 0)` and not with
    # the fade-in below. The level it fades FROM is the one on the part, not
    # one this invocation was told about.
    if a.off and a.ramp_ms > 0:
        cur = from_f32(sc.rd(A_OSCLEVEL))
        if sc.rd(A_OSCON) and cur > 0:
            ramp(cur * 10.0 ** (RAMP_FLOOR_DB / 20.0), cur, a.ramp_ms, False)
    w(A_OSCON, 0, 'OscOn')
    w(A_MEASCHAN, 0, 'MeasChan')
    w(A_XSRC, 0, 'XtalkSrc')
    w(A_XDST, 0, 'XtalkDst')
    w(A_OSCFREQ, f32(a.freq), 'OscFreq')
    # With a fade-in the oscillator is armed AT the floor, turned on there and
    # walked up; without one it is armed at the target as it always was.
    w(A_OSCLEVEL, f32(floor_amp if (a.ramp_ms > 0 and not a.off) else amp),
      'OscLevel')
    w(A_OSCCHAN, a.strip, 'OscChan')
    w(A_XSRC, a.xsrc, 'XtalkSrc')
    w(A_XDST, a.xdst, 'XtalkDst')
    w(A_OSCON, 0 if a.off else 1, 'OscOn')
    on_at = time.time()
    if a.ramp_ms > 0 and not a.off:
        ramp(floor_amp, amp, a.ramp_ms, True)
        w(A_OSCLEVEL, f32(amp), 'OscLevel')       # the target, verified
    # MeasChan LAST, so the first window the measurement node accumulates is
    # one the tone is already at full level in -- a window opened during the
    # fade would average the ramp and read low.
    w(A_MEASCHAN, meas, 'MeasChan')
    if a.sweep:
        # S60: SweepOn runs the periodic log chirp (the S49 stepped sweep
        # is retired); SweepStep is its period in units of 1,024 samples.
        w(A_SWEEPSTEP, a.sweep, 'SweepStep')
        w(A_SWEEPON, 1, 'SweepOn')

    # ---- wait for windows -------------------------------------------------
    print('')
    seq0 = sc.rd(A_SEQ)
    print('  window serial at arm: %d; waiting for %d more'
          % (seq0, a.windows))
    rows = []
    deadline = time.time() + a.windows * WIN_S + 10.0
    seen = seq0
    while len(rows) < a.windows:
        if time.time() > deadline:
            raise SystemExit(
                'the window serial advanced %d times in %.1f s and %d were '
                'asked for. A serial that never moves means the measurement '
                'node is not being called: check MeasChan is non-zero and '
                'that this is a block-kernel image.'
                % (len(rows), a.windows * WIN_S + 10.0, a.windows))
        time.sleep(WIN_S / 4.0)
        s_ = sc.rd(A_SEQ)
        if s_ == seen:
            continue
        seen = s_
        rms = from_f32(sc.rd(A_RMS))
        thd = from_f32(sc.rd(A_THD))
        nse = from_f32(sc.rd(A_NOISE))
        xtk = from_f32(sc.rd(A_XTALK))
        s2 = sc.rd(A_SEQ)
        fhz = a.freq
        rows.append({'seq': s_, 'freq_hz': fhz, 'rms_dbfs': rms,
                     'thd_db': thd, 'noise_dbfs': nse, 'xtalk_db': xtk,
                     'torn': s2 != s_})
        print('    seq %6d %s  RMS %8.2f dBFS   THD+N %8.2f dB = %s   '
              'noise %8.2f dBFS   xtalk %8.2f dB%s'
              % (s_, '(chirp)' if a.sweep else '',
                 rms, thd, pct(thd), nse, xtk,
                 '   (TORN)' if s2 != s_ else ''))

    if a.then_off and not a.off:
        # Stop here, in this session. See the header: the alternative is a
        # second invocation, and everything that one does before it can write
        # OscOn happens with the speaker still sounding.
        print('')
        print('  stopping:')
        ramp(floor_amp, amp, a.ramp_ms, False)
        sc.d.link.write(A_OSCON, 0, 0)
        time.sleep(S.SETTLE)
        off_at = time.time()
        got = sc.rd(A_OSCON)
        print('    %-12s %5d <- 0x%08X   read 0x%08X  %s'
              % ('OscOn', A_OSCON, 0, got, 'OK' if got == 0 else 'MISMATCH'))
        if got != 0:
            raise SystemExit('the oscillator did not stop')
        on_s = off_at - on_at
        print('    oscillator was ON for %.2f s' % on_s)

    good = [r for r in rows if not r['torn']]
    print('')
    if not good:
        raise SystemExit('every read was torn by a window boundary')
    r = good[-1]
    print('  SETTLED (seq %d):' % r['seq'])
    print('    RmsResult   %9.2f dBFS' % r['rms_dbfs'])
    print('    ThdResult   %9.2f dB   = %s' % (r['thd_db'], pct(r['thd_db'])))
    print('    NoiseResult %9.2f dBFS' % r['noise_dbfs'])
    print('    XtalkResult %9.2f dB' % r['xtalk_db'])
    if not a.off:
        want = a.level - 3.0103
        print('')
        print('    injected peak %.2f dBFS -> a sine of that peak has RMS '
              '%.2f dBFS' % (a.level, want))
        print('    measured RMS is %+.2f dB from it (the strip\'s own gain '
              'through the path)' % (r['rms_dbfs'] - want))

    if a.json:
        with open(a.json, 'w') as f:
            json.dump({'tool': 'dsp4_s49_osc', 'strip': a.strip,
                       'meas': meas, 'freq_hz': a.freq,
                       'level_dbfs_peak': a.level, 'off': a.off,
                       'xsrc': a.xsrc, 'xdst': a.xdst,
                       'window_samples': WIN_SAMPLES,
                       'ramp_ms': a.ramp_ms, 'then_off': a.then_off,
                       'on_seconds': (None if (a.off or not a.then_off)
                                      else round(on_s, 3)),
                       'rows': rows}, f, indent=1)
        print('')
        print('  wrote %s' % a.json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
