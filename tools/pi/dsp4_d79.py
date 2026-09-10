#!/usr/bin/env python3
"""dsp4_d79.py — does a boot+config land a header word at SPI address 0?

D79, root-caused 2026-09-10. The parameter protocol is two 32-bit words,
`word0[31:16] = address` and `word1 = value`, and it carries no framing. If
the DSP's receive stream loses ONE word, every request after it is a word
out of phase: the DSP reads the previous transaction's VALUE as the next
one's ADDRESS. Config values are small integers, so `value >> 16` is
**zero** for nearly all of them -- and SPI address 0x0000 is a live audio
parameter on both chips:

    chip 1   0x0000 = _gain_coeff_C1_GAIN_01     (strip 1's gain)
    chip 2   0x0000 = _fdr_level_C2_AUX_FDR_01   (aux 1's fader head)

The value then written there is the NEXT transaction's HEADER word -- which
is why chip 1 reads `0xF0040000` (CFG_COMMIT is register 0xF004) and chip 2
read `0xE0FE0000` (DIAG_NOP). It is ONE defect with two faces, and the two
faces are just what each chip happens to have at dispatch index 0.

WHERE THE WORD GOES MISSING: `_diag_timer_isr`'s stuck-partial-request
recovery (diag.asm, added 2026-08-22) discards a word from SPI2_RFIFO after
three consecutive 1 ms ticks that find the RX FIFO neither empty nor full.
The host's config burst is 51 back-to-back transactions at 1 MHz -- 32 us a
word -- so a 1 kHz tick that keeps landing inside the second word sees
"part full" three ticks running and throws a LIVE word away.
`DSP4_SPI_PARTIAL_FIX2` is the gate that arms the recovery only while
`_spi_rx_count` is standing still, which is what residue looks like and
what a busy link does not.

This tool boots and configures N times per run and reports, per boot and per
chip, the word at dispatch index 0 (and its neighbour) plus the recovery's
own counters. Run it with the gate OFF and ON; the difference is the fix.

Reads are TWO AGREEING READS, gainfix.py's discipline, because the link
answers 0xFFFFFFFF intermittently and returns request words when the answer
phase is off -- and telling a real corruption from a read artefact is half
of what D79 needed. A word that never reads the same twice is reported
UNREADABLE, not corrupt.

Usage: dsp4_d79.py --boots 12 [--json out.json]
"""
import argparse
import json
import subprocess
import sys
import time

sys.path.insert(0, '/home/app/dspboot')

UNITY_F32 = 0x3F800000
UNITY_Q428 = 0x10000000

# (chip, symbol, expected) for dispatch index 0 and the word beside it.
# Index 0 is the casualty; the neighbour says whether the write took the
# instant path (which writes both) or the ramped one.
WATCH = {
    1: [('_gain_coeff_C1_GAIN_01', UNITY_F32),
        ('_gain_target_C1_GAIN_01', UNITY_F32)],
    2: [('_fdr_level_C2_AUX_FDR_01', UNITY_F32),
        ('_fdr_gq_C2_AUX_FDR_01', UNITY_Q428)],
}
# The recovery's own witnesses. Present only in a DSP4_CFG_WATCH build, so
# absence is reported and not treated as zero.
# ORDER MATTERS, and only for one reason: `skip` is a SUBSET of `seen` by
# construction (the ISR increments seen, then skip, on the same tick), but both
# advance while this reads them one SPI transaction at a time -- so reading
# seen first can hand back skip > seen and make the invariant look broken.
# skip is read first.
COUNTERS = {'part_fix': 0xE01F, 'part_ticks': 0xE020,
            'part_skip': 0xE022, 'part_seen': 0xE021,
            'req_word': 0xE023, 'rx_count': 0xE00B,
            'resp_drop': 0xE00F, 'spi_err': 0xE00C}


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True,
                          text=True).stdout


def read_twice(sc, addr, tries=24):
    """gainfix.py's read: two consecutive agreeing reads, or None.

    0xFFFFFFFF and a value are indistinguishable from one read, and a
    request word coming back is indistinguishable from a corrupt parameter.
    """
    last = None
    for _ in range(tries):
        try:
            v = sc.peek(addr)
        except Exception:
            last = None
            time.sleep(0.05)
            continue
        if v is None or v == 0xFFFFFFFF:
            last = None
            time.sleep(0.03)
            continue
        if v == last:
            return v
        last = v
        time.sleep(0.03)
    return None


def one_boot(n):
    """Boot both chips, configure both, then read the watched words."""
    import dsp4_scope as S
    sh('python3 dsp4_boot.py --dir . >/dev/null 2>&1')
    time.sleep(5)
    if 'FAIL' in sh('python3 dsp4_checkchip.py 2>&1').upper():
        return {'boot': n, 'error': 'chip identity gate failed'}
    sh('python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1')
    time.sleep(2)
    sh('python3 dsp4_config.py --product d24 --chip 2 --cs-gpio 24 '
       '--rdy-gpio 12 >/dev/null 2>&1')
    time.sleep(3)

    rec = {'boot': n, 'chips': {}}
    for chip, watch in sorted(WATCH.items()):
        try:
            sc = S.Scope(chip, './chip%d.sym.json' % chip)
            sc.check_chip()
        except Exception as e:
            rec['chips'][chip] = {'error': str(e)}
            continue
        got = {}
        verdict = 'ok'
        for sym, want in watch:
            if sym not in sc.sym:
                got[sym] = 'absent'
                continue
            v = read_twice(sc, sc.sym[sym])
            if v is None:
                got[sym] = 'unreadable'
                if verdict == 'ok':
                    verdict = 'unreadable'
            else:
                got[sym] = '0x%08X' % v
                if v != want:
                    verdict = 'CORRUPT'
        # `rx_count` normally reads None here and that is correct, not a
        # fault: Scope.rd votes two agreeing reads and DIAG_SPI_RX_COUNT
        # advances with this tool's own traffic, so two never agree. It is
        # kept because a value that DOES settle means the link stopped.
        ctr = {}
        for name, reg in COUNTERS.items():
            try:
                ctr[name] = sc.rd(reg)
            except Exception:
                ctr[name] = None
        rec['chips'][chip] = {'words': got, 'verdict': verdict,
                              'counters': ctr}
    return rec


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--boots', type=int, default=12)
    ap.add_argument('--json')
    a = ap.parse_args()

    boots = []
    for n in range(1, a.boots + 1):
        r = one_boot(n)
        boots.append(r)
        if 'error' in r:
            print('  boot %2d: %s' % (n, r['error']))
            continue
        for chip in sorted(r['chips']):
            c = r['chips'][chip]
            if 'error' in c:
                print('  boot %2d chip %d: %s' % (n, chip, c['error']))
                continue
            ws = ' '.join('%s=%s' % (k.split('_C')[0].lstrip('_'), v)
                          for k, v in c['words'].items())
            print('  boot %2d chip %d: %-8s %s  part_fix=%s seen=%s skip=%s '
                  'rx=%s drop=%s'
                  % (n, chip, c['verdict'], ws,
                     c['counters'].get('part_fix'),
                     c['counters'].get('part_seen'),
                     c['counters'].get('part_skip'),
                     c['counters'].get('rx_count'),
                     c['counters'].get('resp_drop')))

    print()
    bad = tot = 0
    for chip in sorted(WATCH):
        n_bad = sum(1 for b in boots
                    if b.get('chips', {}).get(chip, {}).get('verdict')
                    == 'CORRUPT')
        n_ok = sum(1 for b in boots
                   if b.get('chips', {}).get(chip, {}).get('verdict') == 'ok')
        n_un = sum(1 for b in boots
                   if b.get('chips', {}).get(chip, {}).get('verdict')
                   == 'unreadable')
        fx = [b['chips'][chip]['counters'].get('part_fix') for b in boots
              if chip in b.get('chips', {})
              and 'counters' in b['chips'][chip]]
        fx = [v for v in fx if v is not None]
        print('  chip %d: %d CORRUPT, %d ok, %d unreadable of %d boots;'
              ' recovery discards per boot %s'
              % (chip, n_bad, n_ok, n_un, len(boots),
                 ('%d..%d' % (min(fx), max(fx))) if fx else 'unwitnessed'))
        bad += n_bad
        tot += len(boots)

    if a.json:
        json.dump({'boots': boots}, open(a.json, 'w'), indent=1)
        print('  json: %s' % a.json)
    print()
    print('  %d of %d chip-boots landed a header word at dispatch index 0'
          % (bad, tot))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
