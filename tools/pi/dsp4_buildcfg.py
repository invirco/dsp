#!/usr/bin/env python3
"""dsp4_buildcfg.py — decode DIAG_BUILD_CFG: what the image on the part is.

Until 2026-09-09 nothing on a running DSP4 said which block size, which
kernels or which core clock it had been built with. So the bench measured a
BLOCK=16, block-kernel, 983.04 MHz build for a week while the images that
shipped were BLOCK=8, per-sample and running at 491.52 MHz on the CGU's reset
divisors -- and every instrument agreed with itself the whole time, because
they were all reading the same wrong build (findings S8-2, S9-1).

DIAG_BUILD_CFG (0xE0EA) is one compile-time word, read in one transaction,
readable before the graph or the audio clocks exist. src/diag.h defines the
layout; this decodes it, and `--expect-shipping` fails if the part is not
carrying the configuration MW/D32/DSP/SHARC/shipping.config names.

  dsp4_buildcfg.py                    # both chips
  dsp4_buildcfg.py --chip 2
  dsp4_buildcfg.py --expect-shipping  # exit 4 unless it IS the shipping build
"""
import argparse
import sys

sys.path.insert(0, '/home/app/dspboot')

DIAG_BUILD_CFG = 0xE0EA
SIGNATURE = 0xCF000000
# THE SECOND WORD (2026-09-09, findings S11-1). DIAG_BUILD_CFG has no spare
# bit, and on 2026-09-09 that stopped being theoretical: shipping,
# shipping+DSP4_BLOCK_DECIMATE=32 and shipping+DSP4_STRIP_FUSED=1
# +DSP4_SIMD_DYN=1 -- three images 81,299 cycles/block apart on chip 2 --
# all read 0xCF45FF10. The switches that change what the kernels COST live
# here. An image built before this word exists reads 0 and is reported as
# such, not decoded.
DIAG_BUILD_CFG2 = 0xE0EB
SIGNATURE2 = 0xC2000000
CCLK_MHZ = {0: 491.52, 1: 786.432, 2: 983.040, 3: None}

# The switches the word carries, LSB-first after the block size.
FLAGS = [
    (8,  'DSP4_BLOCK_KERNELS'),
    (9,  'DSP4_BLK_LATCH'),
    (10, 'DSP4_CHAN_MASK'),
    (11, 'DSP4_SCOPE_GATE'),
    (12, 'DSP4_BQ_FLOAT'),
    (13, 'DSP4_GAIN_FLOAT'),
    (19, 'DSP4_BISECT'),
    (20, 'DSP4_TXPROBE'),
    (21, 'DSP4_PROFILE_SIGNAL'),
    (22, 'DSP4_BQ_ROUNDONCE'),
    (23, 'DSP4_BQ_GUARD'),
]
# Anything true here means the image is an instrument or a debug build and
# must never be mistaken for one that ships.
NEVER_SHIPPING = ('DSP4_BISECT', 'DSP4_TXPROBE', 'DSP4_PROFILE_SIGNAL')

# DIAG_BUILD_CFG2's switches, LSB-first.
FLAGS2 = [
    (0, 'DSP4_STRIP_FUSED'),
    (1, 'DSP4_SIMD_DYN'),
    (2, 'DSP4_SIMD_GRAPH'),
    (3, 'DSP4_SIMD_STRIPS'),
    (4, 'DSP4_SCOPE_BLK_TAP'),
    (6, 'DSP4_GATHER_FIRST'),
    (7, 'DSP4_FX_TYPE_DECLARED'),
]
# DSP4_BLOCK_DECIMATE != 1 means the graph runs on one block in N: the audio
# is wrong and the cycle count is an instrument's, not the product's.
NEVER_SHIPPING2 = ('DSP4_SCOPE_BLK_TAP',)

# The shipping configuration, mirrored from MW/D32/DSP/SHARC/shipping.config.
# Kept here rather than read from the repo because this tool runs on the bench,
# where the repo is not checked out; check_shipping_config.sh diffs the two.
SHIPPING = {
    'block': 16,
    'cclk': 2,                      # 983.040 MHz
    'block_mask': 7,
    'DSP4_BLOCK_KERNELS': 1,
    'DSP4_BLK_LATCH': 1,
    'DSP4_CHAN_MASK': 1,
    'DSP4_SCOPE_GATE': 1,
    'DSP4_BQ_FLOAT': 1,
    'DSP4_GAIN_FLOAT': 1,
    'DSP4_BQ_ROUNDONCE': 1,
    # DERIVED, not configured: dsp_block.h forces the guard off whenever
    # DSP4_BQ_FLOAT is on, and the shipping build is a float build.
    'DSP4_BQ_GUARD': 0,
    'DSP4_BISECT': 0,
    'DSP4_TXPROBE': 0,
    'DSP4_PROFILE_SIGNAL': 0,
}

# The same mirror for the second word. DSP4_SIMD_GRAPH and DSP4_SIMD_STRIPS
# are DERIVED in build.sh -- SIMD_GRAPH defaults on and SIMD_STRIPS follows
# DSP4_SIMD_DYN -- so what a shipping image reads for them is whatever the
# kernels flag makes them, and they are listed at the value the current
# shipping.config produces rather than as independent choices.
SHIPPING2 = {
    'decimate': 1,
    'DSP4_STRIP_FUSED': 0,
    'DSP4_SIMD_DYN': 0,
    'DSP4_SIMD_GRAPH': 1,
    'DSP4_SIMD_STRIPS': 0,
    'DSP4_SCOPE_BLK_TAP': 0,
    'DSP4_TX_EARLY': 0,          # a MASK: 0 = neither chip
    'DSP4_GATHER_FIRST': 1,
    'DSP4_FX_TYPE_DECLARED': 0,
}


def decode(word):
    """Return a dict, or raise ValueError if the word is not a config word."""
    if word is None or (word & 0xFF000000) != SIGNATURE:
        raise ValueError('0x%s is not a DIAG_BUILD_CFG word (signature 0xCF)'
                         % ('%08X' % word if word is not None else '????????'))
    d = {'raw': word,
         'block': word & 0xFF,
         'block_mask': (word >> 14) & 7,
         'cclk': (word >> 17) & 3}
    for bit, name in FLAGS:
        d[name] = (word >> bit) & 1
    return d


def decode2(word):
    """Decode DIAG_BUILD_CFG2, or raise ValueError."""
    if word is None or (word & 0xFF000000) != SIGNATURE2:
        raise ValueError('0x%s is not a DIAG_BUILD_CFG2 word (signature 0xC2)'
                         % ('%08X' % word if word is not None else '????????'))
    d = {'raw': word, 'decimate': (word >> 16) & 0xFF,
         # A PER-CHIP MASK, not a flag: 1 = chip 1's inter-chip TX,
         # 2 = chip 2's converter TX, 3 = both. Each chip that has it on
         # adds a block of output latency, so the value is the cost.
         'DSP4_TX_EARLY': (word >> 8) & 3}
    for bit, name in FLAGS2:
        d[name] = (word >> bit) & 1
    return d


def describe2(d):
    lines = ['raw2 0x%08X' % d['raw']]
    if d['decimate'] != 1:
        lines.append('DSP4_BLOCK_DECIMATE %d — THE GRAPH RUNS ON ONE BLOCK IN '
                     '%d: this is an instrument, the audio is wrong and the '
                     'cycle count is not the product\'s'
                     % (d['decimate'], d['decimate']))
    if d['DSP4_TX_EARLY']:
        lines.append('DSP4_TX_EARLY %d (%s) — outputs written a half ahead; '
                     '+1 block of output latency per chip'
                     % (d['DSP4_TX_EARLY'],
                        {1: 'chip 1 IC TX', 2: 'chip 2 TX',
                         3: 'both chips'}[d['DSP4_TX_EARLY']]))
    on = [n for _, n in FLAGS2 if d[n]]
    off = [n for _, n in FLAGS2 if not d[n]]
    lines.append('on2:  ' + (', '.join(on) or '-'))
    lines.append('off2: ' + (', '.join(off) or '-'))
    return lines


def diff_shipping2(d):
    out = []
    for k, want in SHIPPING2.items():
        got = d.get(k)
        if got != want:
            out.append('%s = %s, shipping is %s' % (k, got, want))
    for k in NEVER_SHIPPING2:
        if d.get(k):
            out.append('%s is SET — this is an instrument build, not a '
                       'shipping one' % k)
    return sorted(set(out))


def describe(d):
    mhz = CCLK_MHZ[d['cclk']]
    lines = ['raw 0x%08X' % d['raw'],
             'BLOCK %d' % d['block'],
             'CCLK %s' % ('%.3f MHz' % mhz if mhz else 'UNKNOWN'),
             'BLOCK_MASK %d%s' % (d['block_mask'],
                                  '' if d['block_mask'] == 7
                                  else ' (PARTIAL block loop)')]
    on = [n for _, n in FLAGS if d[n]]
    off = [n for _, n in FLAGS if not d[n]]
    lines.append('on:  ' + (', '.join(on) or '-'))
    lines.append('off: ' + (', '.join(off) or '-'))
    if mhz:
        # The budget every cycle figure is scored against, stated with the
        # build rather than assumed from a document written on another one.
        lines.append('budget %d cycles/block (%.3f MHz x %d / 48000)'
                     % (round(mhz * 1e6 * d['block'] / 48000), mhz, d['block']))
    return lines


def diff_shipping(d):
    """Return a list of human-readable differences from the shipping build."""
    out = []
    for k, want in SHIPPING.items():
        got = d.get(k)
        if got != want:
            out.append('%s = %s, shipping is %s' % (k, got, want))
    for k in NEVER_SHIPPING:
        if d.get(k):
            out.append('%s is SET — this is an instrument build, not a '
                       'shipping one' % k)
    return sorted(set(out))


def read_word(chip):
    from dsp4_config import SpiLink
    from dsp4_diag import DiagLink
    from dsp4_scope import CS_GPIO, RDY_GPIO, check_chip_id
    d = DiagLink(SpiLink('0.0', 1_000_000, CS_GPIO[chip],
                         rdy_gpio=RDY_GPIO[chip]))
    d.resync()
    check_chip_id(d.read(0xE001), chip)
    return d.read(DIAG_BUILD_CFG), d.read(DIAG_BUILD_CFG2)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--chip', type=int, choices=(1, 2), action='append')
    ap.add_argument('--word', help='decode a hex word instead of reading a part')
    ap.add_argument('--expect-shipping', action='store_true',
                    help='exit 4 unless the part carries the shipping build')
    args = ap.parse_args()

    if args.word:
        w = [int(x, 0) for x in args.word.split(',')]
        chips = [(None, (w[0], w[1] if len(w) > 1 else None))]
    else:
        chips = [(c, read_word(c)) for c in (args.chip or [1, 2])]

    rc = 0
    for chip, (word, word2) in chips:
        tag = '' if chip is None else 'chip %d: ' % chip
        try:
            d = decode(word)
        except ValueError as e:
            print('%s%s' % (tag, e))
            print('%s  an image built before 2026-09-09 has no DIAG_BUILD_CFG '
                  'and reads 0 here' % tag)
            rc = 4
            continue
        for i, line in enumerate(describe(d)):
            print('%s%s' % (tag if i == 0 else ' ' * len(tag), line))
        bad = diff_shipping(d)
        if bad:
            print('%s  NOT THE SHIPPING CONFIGURATION:' % (' ' * len(tag)))
            for b in bad:
                print('%s    %s' % (' ' * len(tag), b))
            if args.expect_shipping:
                rc = 4
        else:
            print('%s  == the shipping configuration' % (' ' * len(tag)))

        # THE SECOND WORD. Absent on any image built before 2026-09-09, and
        # said so rather than decoded as zeros -- a 0 here used to be
        # indistinguishable from "every cost switch off", which is exactly
        # the silence this word exists to end.
        pad = ' ' * len(tag)
        try:
            d2 = decode2(word2)
        except ValueError as e:
            print('%s  %s' % (pad, e))
            print('%s  no DIAG_BUILD_CFG2: this image cannot say whether it '
                  'carries the fused/SIMD kernels or a decimated graph'
                  % pad)
            if args.expect_shipping:
                rc = 4
            continue
        for line in describe2(d2):
            print('%s  %s' % (pad, line))
        bad2 = diff_shipping2(d2)
        if bad2:
            print('%s  NOT THE SHIPPING KERNEL CONFIGURATION:' % pad)
            for b in bad2:
                print('%s    %s' % (pad, b))
            if args.expect_shipping:
                rc = 4
    return rc


if __name__ == '__main__':
    sys.exit(main())
