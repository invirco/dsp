#!/usr/bin/env python3
"""check_click_model.py — the stored haptic clicks ARE PW's audition files.

S122. `C2_HPT_01`'s click tables are generated (dsp_codegen.py::
_haptic_click_table) from four numbers per click — frequency, decay, peak and
truncation — and the claim this script exists to test is that those numbers
reproduce the WAV files PW auditioned on 2026-09-25 and called "ticks are
working", rather than merely resembling them.

It reads the Q4.28 words straight out of the GENERATED assembly (never out of
the generator, which would only prove the generator agrees with itself) and
compares them sample for sample with the files.

The audition files are not in this repo — they are 126 kB each of reference
material and belong in the shared store. Point --wav-dir at wherever they are:

  ~/Stonepower Dropbox/Peter Watts/_Matrix/Products/D24/dsp/audition-20260925/
  or /home/app/ on MW-D24-2, where PW played them from.

Usage:
  ./check_click_model.py [--asm PATH] [--wav-dir DIR] [--tol 0.01]
Exit: 0 match, 1 a click is off by more than --tol, 2 nothing to compare.
"""
import argparse
import os
import re
import struct
import sys

Q28 = float(1 << 28)
HERE = os.path.dirname(os.path.abspath(__file__))
ASM = os.path.normpath(os.path.join(
    HERE, '..', '..', '..', '..', 'MW', 'D32', 'DSP', 'SHARC', 'src', 'chip2',
    'nodes', 'C2_HPT_01.asm'))

# stored index (1-based `sample` cell) -> the audition file it models
CLICKS = [(1, '2_click_2k5.wav',  '2500 Hz, tau 2.5 ms  (press)'),
          (2, '6_release_3k.wav', '3000 Hz, tau 1.8 ms  (release)'),
          (3, '1_click_1k5.wav',  '1500 Hz, tau 3.0 ms  (spare)')]
BURST_AT_S = 0.150      # every audition file holds one burst starting here


def asm_words(lines, name):
    i = next(k for k, l in enumerate(lines) if l.startswith('.var %s[' % name))
    n = int(re.search(r'\[(\d+)\]', lines[i]).group(1))
    vals, k = [], i + 1
    while len(vals) < n:
        vals += [int(x, 16) for x in re.findall(r'0x([0-9A-Fa-f]{8})', lines[k])]
        k += 1
    if len(vals) != n:
        raise SystemExit('%s declares %d words and lists %d' % (name, n, len(vals)))
    return [v - (1 << 32) if v >= (1 << 31) else v for v in vals]


def wav_mono(path):
    """Left channel of a 32-bit PCM WAV, as floats in [-1, 1)."""
    d = open(path, 'rb').read()
    i, off, n, ch, bits, sr = 12, None, 0, 2, 32, 48000
    while i + 8 <= len(d):
        cid, sz = d[i:i + 4], struct.unpack('<I', d[i + 4:i + 8])[0]
        if cid == b'fmt ':
            _, ch, sr, _, _, bits = struct.unpack('<HHIIHH', d[i + 8:i + 24])
        elif cid == b'data':
            off, n = i + 8, sz
        i += 8 + sz + (sz & 1)
    if off is None or bits != 32:
        raise SystemExit('%s: expected 32-bit PCM' % path)
    cnt = n // 4
    v = struct.unpack('<%di' % cnt, d[off:off + cnt * 4])
    return [x / 2.0 ** 31 for x in v[::ch]], sr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--asm', default=ASM)
    ap.add_argument('--wav-dir', default='.')
    ap.add_argument('--tol', type=float, default=0.01,
                    help='max allowed |stored - file| in full-scale units')
    a = ap.parse_args()

    lines = open(a.asm).read().split('\n')
    offs = asm_words(lines, '_hpt_off_C2_HPT_01')
    lens = asm_words(lines, '_hpt_len_C2_HPT_01')
    tab = asm_words(lines, '_hpt_tab_C2_HPT_01')
    tone = asm_words(lines, '_hpt_tone_C2_HPT_01')
    print('%s\n  %d clicks at offsets %s, lengths %s; %d table words, '
          '%d tone words' % (a.asm, len(offs), offs, lens, len(tab), len(tone)))

    bad = missing = 0
    for idx, fname, what in CLICKS:
        path = os.path.join(a.wav_dir, fname)
        if not os.path.exists(path):
            print('  sample %d  %-24s NO FILE at %s' % (idx, what, path))
            missing += 1
            continue
        ref, sr = wav_mono(path)
        ref = ref[int(BURST_AT_S * sr):]
        o, n = offs[idx - 1], lens[idx - 1]
        got = [v / Q28 for v in tab[o:o + n]]
        m = min(len(got), len(ref))
        diff = [got[k] - ref[k] for k in range(m)]
        worst = max(abs(x) for x in diff)
        rms = (sum(x * x for x in diff) / m) ** 0.5
        ok = worst <= a.tol
        bad += 0 if ok else 1
        print('  sample %d  %-24s %4d words  peak %.4f (file %.4f)  '
              'max|diff| %.5f  rms %.6f  last %.2e  %s'
              % (idx, what, n, max(abs(v) for v in got),
                 max(abs(v) for v in ref[:n]), worst, rms, got[-1],
                 'OK' if ok else 'OVER TOLERANCE'))

    # The tone is checked against arithmetic, not against a file: it is one
    # exact period of 1 kHz at 48 kHz and there is nothing to fit.
    import math
    amp = ((1 << 28) - 1) / Q28
    err = max(abs(tone[k] / Q28 - amp * math.sin(2 * math.pi * k / len(tone)))
              for k in range(len(tone)))
    print('  test tone  %d samples = exactly %g Hz at 48 kHz   max|err| %.3e'
          % (len(tone), 48000.0 / len(tone), err))
    if err > 1e-8:
        bad += 1
        print('    OVER TOLERANCE')

    if missing == len(CLICKS):
        print('nothing to compare: pass --wav-dir')
        return 2
    print('MATCH' if not bad else '%d click(s) over tolerance' % bad)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
