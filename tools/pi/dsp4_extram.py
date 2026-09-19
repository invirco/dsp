#!/usr/bin/env python3
"""dsp4_extram.py — decode the S75 external-RAM delay pool's diag registers.

S75 codes the delay/reverb memory pool against a HyperRAM part that no
shipping card carries yet: DSP4_EXTRAM defaults 0, and every rev C board in
the field has no RAM fitted at all. The whole design rests on that probe
failing SAFELY and SAYING WHY -- "no device answered" has to be visibly
different from "a device answered and something is wrong with it", because
the first is every unmodified card ever built and the second is a real
fault. Nothing on the bench read that back before this tool: dsp4_buildcfg.py
covers DIAG_BUILD_CFG/CFG2, and CFG2's own note is what set the shape this
S75 addition takes -- "the next flag of this kind needs a third word, not a
seventh narrowing of the signature" (see diag.h) -- which is DIAG_BUILD_CFG3.

DIAG_BUILD_CFG3 and the five DIAG_EXTRAM_* registers below are compiled in
ONLY when DSP4_EXTRAM=1 (diag.asm gates the whole block behind
`#if DSP4_EXTRAM`, deliberately, so the L2 arm's shipping pair stays
byte-identical). So on today's shipping image -- built DSP4_EXTRAM=0 -- all
six addresses are simply unmapped and read back 0. That 0 is not an error
and not a lesser reading of a RAM that isn't there; it is the complete
answer "this image carries no pool logic at all", and this tool says so in
those words rather than treating it as a failed read.

  DIAG_BUILD_CFG3    0xE0EC   signature 0xC4 in bits 31..24, bit 0 =
                              DSP4_EXTRAM (pool compiled in). Says what the
                              image WAS BUILT WITH, nothing about runtime.
  DIAG_EXTRAM_STAT   0xE0ED   what the image DID: backend in force, whether
                              a device answered and passed, why not if not,
                              and this chip's pool line count.
  DIAG_EXTRAM_ID0/1  0xE0EE/EF  raw HyperBus register-space ID words.
  DIAG_EXTRAM_XFERS  0xE0F2   MDMA staging transfers issued.
  DIAG_EXTRAM_STALLS 0xE0F3   blocks whose staging was skipped.

See src/diag.h's "DIAG_BUILD_CFG3" and "THE RUNTIME SIDE OF THE POOL"
sections for the authoritative bit layout; this mirrors it exactly.

Usage:
  dsp4_extram.py                       # both chips, read off the bench
  dsp4_extram.py --chip 1              # one chip
  dsp4_extram.py --expect-rev-c        # assert the unmodified-card reading
  dsp4_extram.py --decode 0xC4000001,0x00200030,0xFFFFFFFF,0xFFFFFFFF,0,0
                                        # decode CFG3,STAT,ID0,ID1,XFERS,
                                        # STALLS given on the command line;
                                        # touches no hardware

Requires python3-spidev + python3-libgpiod on the Pi for a live read;
--decode works anywhere, including off the bench.
"""
import argparse
import sys

sys.path.insert(0, '/home/app/dspboot')

DIAG_BUILD_CFG3 = 0xE0EC
SIGNATURE3 = 0xC4000000
DIAG_EXTRAM_STAT = 0xE0ED
DIAG_EXTRAM_ID0 = 0xE0EE
DIAG_EXTRAM_ID1 = 0xE0EF
DIAG_EXTRAM_XFERS = 0xE0F2
DIAG_EXTRAM_STALLS = 0xE0F3

# The order --decode takes its six values in, and the order read_chip()
# returns them in.
REG_NAMES = ('CFG3', 'STAT', 'ID0', 'ID1', 'XFERS', 'STALLS')

FAIL_TEXT = {
    0: 'none',
    1: 'controller init failed',
    2: 'STIG timeout',
    3: 'ID floated (no device)',
    4: 'pattern test failed',
    5: 'forced off by product config',
}

# dsp_block.h's S75 geometry note: the pool is wired to chip 1's 32 channel
# delays only; chip 2 is 0 lines BY SCOPE, not by fault (its aux/sub/main/
# monitor delays are still per-sample and cannot be staged). diag.h's own
# bench-check note gives the two expected STAT readings this pins:
# 0x00200030 on chip 1, 0x00000030 on chip 2.
POOL_LINES_EXPECT = {1: 32, 2: 0}


def decode3(word):
    """Decode DIAG_BUILD_CFG3, or raise ValueError if the signature is wrong.

    A literal 0 does NOT fail this check by signature -- 0 & 0xFF000000 is
    0, not 0xC4000000 -- so it raises here too. Callers must special-case
    a raw 0 themselves (see describe_chip()): it is the expected reading
    of an image built with DSP4_EXTRAM=0, not a decode error.
    """
    if word is None or (word & 0xFF000000) != SIGNATURE3:
        raise ValueError('0x%s is not a DIAG_BUILD_CFG3 word (signature 0xC4)'
                         % ('%08X' % word if word is not None else '????????'))
    return {'raw': word, 'DSP4_EXTRAM': word & 1}


def decode_stat(word):
    """Decode DIAG_EXTRAM_STAT. Never raises -- every 32-bit value is a
    legal reading of this register, including the all-zero unmapped one."""
    return {
        'raw': word,
        'backend': 'EXTRAM' if word & 1 else 'L2',
        'present': bool((word >> 1) & 1),
        'fail': (word >> 4) & 0xF,
        'lines': (word >> 16) & 0xFFFF,
    }


def describe_chip(chip, cfg3, stat, id0, id1, xfers, stalls):
    """Return a list of human-readable lines decoding one chip's S75 block."""
    lines = []

    lines.append('raw CFG3       0x%08X' % cfg3)
    no_cfg3 = False
    try:
        d3 = decode3(cfg3)
        lines.append('  signature OK (0xC4); DSP4_EXTRAM = %d -- the pool '
                     'IS compiled in' % d3['DSP4_EXTRAM']
                     if d3['DSP4_EXTRAM'] else
                     '  signature OK (0xC4); DSP4_EXTRAM = 0 -- the pool is '
                     'NOT compiled in')
    except ValueError as e:
        if cfg3 == 0:
            no_cfg3 = True
            lines.append('  this image has no CFG3, i.e. it was built with '
                         'DSP4_EXTRAM=0. That is the NORMAL reading today, '
                         'not a fault: DIAG_BUILD_CFG3 and every DIAG_EXTRAM_* '
                         'register are compiled out entirely on a '
                         'DSP4_EXTRAM=0 image and read back the unmapped 0.')
        else:
            lines.append('  %s -- garbage, or the wrong address' % e)

    d = decode_stat(stat)
    lines.append('raw STAT       0x%08X' % stat)
    if no_cfg3:
        lines.append('  (unmapped -- no pool compiled in, see CFG3 above; '
                     'the fields below are the unmapped-register 0, not a '
                     'measurement)')
    lines.append('  backend      %s' % d['backend'])
    lines.append('  present      %s' % ('yes -- a device answered and '
                                        'passed the test' if d['present']
                                        else 'no'))
    lines.append('  fail code    %d (%s)' % (d['fail'],
                                             FAIL_TEXT.get(d['fail'],
                                                          'UNKNOWN CODE')))
    note = ''
    if not no_cfg3 and chip is not None \
            and POOL_LINES_EXPECT.get(chip) is not None:
        want = POOL_LINES_EXPECT[chip]
        note = '  (expected %d for chip %d)' % (want, chip)
        if d['lines'] != want:
            note += '  <-- DOES NOT MATCH'
    lines.append('  pool lines   %d%s' % (d['lines'], note))

    for name, val in (('ID0', id0), ('ID1', id1)):
        floated = '  (0xFFFFFFFF -- bus floated, nothing answered)' \
            if val == 0xFFFFFFFF else ''
        lines.append('raw %-11s0x%08X%s' % (name, val, floated))

    lines.append('XFERS          %d transfers issued' % xfers)
    lines.append('STALLS         %d blocks skipped staging' % stalls)
    return lines


def check_rev_c(chip, cfg3, stat):
    """Return (ok, reason) against the reading an UNMODIFIED rev C card
    must give. There is no RAM at all on rev C, so which reading is
    "correct" depends on how the image was built -- see the module
    docstring and diag.h's S75 sections for the two cases this decides
    between."""
    d = decode_stat(stat)

    if cfg3 == 0:
        # Case A: built DSP4_EXTRAM=0 -- CFG3 and every EXTRAM_* register
        # are compiled out and read the unmapped 0.
        if stat == 0:
            return True, ('case A (built DSP4_EXTRAM=0): CFG3 and '
                          'EXTRAM_STAT both read 0 -- unmapped, exactly as '
                          'expected for today\'s shipping image')
        return False, ('CFG3 reads 0 (no pool compiled in) but STAT reads '
                       '0x%08X, not also 0 -- if the pool is not compiled '
                       'in, EXTRAM_STAT must be unmapped too' % stat)

    # Otherwise this is claiming to be a DSP4_EXTRAM=1 build (case B).
    if cfg3 != 0xC4000001:
        return False, ('CFG3 = 0x%08X -- neither the DSP4_EXTRAM=0 reading '
                       '(0x00000000) nor the DSP4_EXTRAM=1 one '
                       '(0xC4000001)' % cfg3)

    problems = []
    if d['backend'] != 'L2':
        problems.append('backend = EXTRAM, expected L2 (no RAM to have '
                        'switched to)')
    if d['present']:
        problems.append('present = 1, expected 0 -- no device should '
                        'answer on an unmodified card')
    if d['fail'] == 0 and not d['present']:
        problems.append('fail = 0 with present = 0 -- the probe did not '
                        'run at all')
    elif d['fail'] == 4:
        problems.append('fail = 4 (pattern test failed) -- something '
                        'answered the ID read and then failed the pattern '
                        'test; on a board with no RAM fitted this is a '
                        'wiring or bus fault, not an absent part')
    elif d['fail'] != 3:
        problems.append('fail = %d (%s), expected 3 (ID floated / no '
                        'device)' % (d['fail'], FAIL_TEXT.get(d['fail'],
                                                             'UNKNOWN CODE')))
    want_lines = POOL_LINES_EXPECT.get(chip)
    if want_lines is not None and d['lines'] != want_lines:
        problems.append('pool lines = %d, expected %d for chip %d'
                        % (d['lines'], want_lines, chip))

    if problems:
        return False, 'case B (built DSP4_EXTRAM=1): ' + '; '.join(problems)
    return True, ('case B (built DSP4_EXTRAM=1): STAT = 0x%08X matches the '
                  'unmodified rev-C reading (backend L2, not present, '
                  'fail 3 ID floated, %d lines)' % (stat, d['lines']))


def read_chip(chip):
    """Read all six S75 registers off one chip, in REG_NAMES order.

    Raises ImportError if spidev/gpiod are not installed (i.e. this is
    not being run on the bench Pi/CM4), and IOError/OSError for a
    transport that is present but not talking to a part.
    """
    from dsp4_config import SpiLink
    from dsp4_diag import DiagLink
    from dsp4_scope import CS_GPIO, RDY_GPIO, check_chip_id
    d = DiagLink(SpiLink('0.0', 1_000_000, CS_GPIO[chip],
                         rdy_gpio=RDY_GPIO[chip]))
    d.resync()
    check_chip_id(d.read(0xE001), chip)
    return tuple(d.read(a) for a in (DIAG_BUILD_CFG3, DIAG_EXTRAM_STAT,
                                     DIAG_EXTRAM_ID0, DIAG_EXTRAM_ID1,
                                     DIAG_EXTRAM_XFERS, DIAG_EXTRAM_STALLS))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--chip', type=int, choices=(1, 2), action='append',
                    help='read only this chip (repeatable); default both')
    ap.add_argument('--decode', metavar='CFG3,STAT,ID0,ID1,XFERS,STALLS',
                    help='decode six register values given on the command '
                         'line (hex or decimal) instead of reading hardware')
    ap.add_argument('--expect-rev-c', action='store_true',
                    help='assert the reading an unmodified rev C card must '
                         'give; exit 1 if it does not')
    args = ap.parse_args()

    if args.decode:
        try:
            vals = [int(x, 0) for x in args.decode.split(',')]
        except ValueError as e:
            print('--decode: %s' % e, file=sys.stderr)
            return 2
        if len(vals) != 6:
            print('--decode needs exactly 6 values (%s), got %d'
                  % (','.join(REG_NAMES), len(vals)), file=sys.stderr)
            return 2
        chip = (args.chip or [None])[0]
        tag = '' if chip is None else 'chip %d: ' % chip
        for i, line in enumerate(describe_chip(chip, *vals)):
            print('%s%s' % (tag if i == 0 else ' ' * len(tag), line))
        rc = 0
        if args.expect_rev_c:
            ok, reason = check_rev_c(chip, vals[0], vals[1])
            print('%s%s: %s' % (' ' * len(tag), 'PASS' if ok else 'FAIL',
                                reason))
            if not ok:
                rc = 1
        return rc

    chips = sorted(set(args.chip)) if args.chip else [1, 2]
    try:
        readings = {c: read_chip(c) for c in chips}
    except ImportError as e:
        print('ERROR: SPI transport unavailable (%s) -- this tool reads '
              'hardware only on the bench Pi/CM4, with python3-spidev and '
              'python3-libgpiod installed. Use --decode to exercise the '
              'decoder off the bench.' % e, file=sys.stderr)
        return 2
    except (IOError, OSError) as e:
        print('ERROR: could not read the S75 registers over SPI (%s)' % e,
             file=sys.stderr)
        return 2

    rc = 0
    for c in chips:
        tag = 'chip %d: ' % c
        for i, line in enumerate(describe_chip(c, *readings[c])):
            print('%s%s' % (tag if i == 0 else ' ' * len(tag), line))
        if args.expect_rev_c:
            ok, reason = check_rev_c(c, readings[c][0], readings[c][1])
            print('%s%s: %s' % (' ' * len(tag), 'PASS' if ok else 'FAIL',
                                reason))
            if not ok:
                rc = 1
    return rc


if __name__ == '__main__':
    sys.exit(main())
