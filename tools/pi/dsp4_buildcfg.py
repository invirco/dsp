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
# SIX BITS, not eight, and NOT CONTIGUOUS (S49 then S72). Bits 31..30 and
# 28..25 are the signature (0b11 0001), bit 29 is DSP4_TALK_INVERT and bit 24
# is DSP4_TEST_NODES; see the notes in diag.h. Both flags were placed so the
# word a SHIPPING image reads is still 0xC2000000 and only the unusual arm
# trips an older tool: a decoder masking 0xFF000000 rejects a self-test image
# (0xC3000000) and one masking 0xFE000000 rejects an inverted-talkback image
# (0xE2000000), instead of misreading either as shipping. Loud on the arm
# that is wrong is the right way round.
SIGMASK2 = 0xDE000000           # 0xFF000000 less bit 29 and bit 24
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
    # ADDED S18. diag.h has carried these since S12/S14/S15 -- they were put
    # in the word precisely because a switch that changes cost or audio and
    # cannot be read back is a gap the next session pays for -- and this
    # decoder, the only thing that reads the word, never learned them. So
    # `dsp4_buildcfg.py` reported `off2: ...` for four switches it was not
    # looking at, which is the S12-7 shape one layer down.
    (10, 'DSP4_DYN_LUT'),
    (11, 'DSP4_GATE_LINTHR'),
    (12, 'DSP4_C2_BQ_GRAPH'),
    # ADDED S49. The self-test nodes change what the chain calls and what
    # chip 1 costs; a switch like that has to be readable off the part.
    (24, 'DSP4_TEST_NODES'),
    # ADDED S72. The talkback polarity (diag.h's bit 29, taken out of the
    # signature). It changes AUDIO and nothing else on the part said which
    # way up the talkback was -- S71-4's gap.
    (29, 'DSP4_TALK_INVERT'),
]
# DSP4_BLOCK_DECIMATE != 1 means the graph runs on one block in N: the audio
# is wrong and the cycle count is an instrument's, not the product's.
NEVER_SHIPPING2 = ('DSP4_SCOPE_BLK_TAP',)
# DSP4_TEST_NODES is NOT in that list: it is a proposal for the
# shipping image, not an instrument-only switch (S49). It is 0 in
# shipping.config today, so a 1 still shows up as a difference.

# THE THIRD WORD (S75, FILLED AND UNGATED AT S80). DIAG_BUILD_CFG2's own note
# (diag.h) says the next flag of its class needs a new word rather than a
# seventh narrowing of a signature already down to six bits and fully
# allocated below it -- DSP4_EXTRAM was that flag and S75 took the word for
# it, bit 0 only, 23..1 free. S80 filled them with the switches neither full
# word can carry, because by then the hole had cost two sessions of record: an
# image with the off-aux park gate on and one with it off read back the SAME
# 0xE2018264 (S79), and mask 3 and mask 15 of DSP4_SHARED_KERNELS have read
# back the same CFG2 since S26 (S27-3).
#
# THE WORD IS NO LONGER COMPILED OUT. S75 gated the DM cell `#if DSP4_EXTRAM`
# to keep its byte-identical-rebuild proof, so 0xE0EC read plain 0 on every
# shipping image; every image's md5 moved once at S80 and the word is
# unconditional. A 0 here now means the image PREDATES S80 -- see decode3().
DIAG_BUILD_CFG3 = 0xE0EC
SIGNATURE3 = 0xC4000000

# LSB-first. Two entries are not build switches and are marked: MTX_GATE is a
# CAPABILITY (the image has a reader for CFG_MTX_MASK, S79) and INSTRUMENT is
# the truth value of "any switch no word carries is off its shipping value".
FLAGS3 = [
    (0, 'DSP4_EXTRAM'),
    (1, 'DSP4_AUXIN_BYPASS'),
    (2, 'MTX_GATE'),
    (3, 'DSP4_CUE'),
    (4, 'DSP4_RTA'),
    (5, 'DSP4_SPI_PARTIAL_FIX2'),
    (16, 'DSP4_DYN_TABLES'),
    (19, 'DSP4_C2_XPAIR'),
    (20, 'DSP4_DLY_SPLIT'),
    (21, 'DSP4_GAIN_SIMD'),
    (22, 'DSP4_RTG_FABRIC'),
    (23, 'INSTRUMENT'),
]
# The multi-bit fields, extracted in decode3() rather than as flags: the VALUE
# is the cost, exactly as DSP4_TX_EARLY and DSP4_BQ_SIMD_PIPE are in CFG2.
#   15..8   DSP4_SHARED_KERNELS   the WHOLE eight-class mask
#   18..17  DSP4_DYN_INLINE       0..3
#
# INSTRUMENT IS THE ONE FIELD THAT MUST NEVER BE 1 IN A SHIPPING IMAGE, and
# unlike NEVER_SHIPPING/NEVER_SHIPPING2 it is not a switch that could be
# argued into the product later: it is the statement that one is.
NEVER_SHIPPING3 = ('INSTRUMENT',)

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
    'DSP4_TEST_NODES': 0,
    # S74 (PW ruling 2026-09-19 evening: "tb polarity can be signed in
    # code"). shipping.config has it 1; the D24 ships inverted-corrected.
    'DSP4_TALK_INVERT': 1,
    # S9-2 Option A, ADOPTED on CHIP 2 by PW 2026-09-09. A MASK:
    # 1 = chip 1's inter-chip TX, 2 = chip 2's converter TX, 3 = both.
    # Costs +16 samples of output latency on the chip that has it, so
    # the through-DSP contract figure is 82 samples / 1.708 ms at
    # block 16.
    'DSP4_TX_EARLY': 2,
    'DSP4_GATHER_FIRST': 1,
    'DSP4_FX_TYPE_DECLARED': 0,
    # THE FIVE CFG2 FIELDS THIS MIRROR DID NOT CARRY (S77). Four of them are
    # 0 and always have been, so their absence never changed the word; the
    # fifth is DSP4_SHARED_KERNELS, which S76 landed in shipping.config at 15
    # and did not mirror here. The consequence was live: `--expect-shipping`
    # scored the ACTUAL shipping image as a mismatch (expect 0xE2010244, the
    # part reads 0xE2018264, the two SHARED_KERNELS bits), and
    # check_shipping_config.sh announced the wrong word while reporting
    # "consistent" -- because a key present in only ONE of the two copies was
    # allowed. That is S8-2's shape in the pair of files built to prevent it,
    # and it is the third time (S11-1, S74-2, this). The hole is closed
    # structurally in check_shipping_config.sh: every field cfg_words.py
    # says the word carries must appear here, or the check fails.
    'DSP4_DYN_LUT': 0,
    'DSP4_GATE_LINTHR': 0,
    'DSP4_C2_BQ_GRAPH': 0,
    'DSP4_BQ_SIMD_PIPE': 0,
    'DSP4_SHARED_KERNELS': 15,
}

# The mirror of the third word (S75). It carries one flag, DSP4_EXTRAM, and
# it is 0 today for a hardware reason rather than a pending decision: no
# DSP4 card in the field has the HyperRAM part fitted, so build.sh and
# shipping.config both default it off and every shipping image is built
# that way. It is here, in its own dict, for the same reason DSP4_TALK_INVERT
# is in SHIPPING2 and not folded into SHIPPING2's diff loop by hand -- S74
# found that a flag left out of THIS file's mirrors is a flag
# check_shipping_config.sh cannot catch drifting, and CFG3 must not reopen
# that gap for itself on its first day.
SHIPPING3 = {
    'DSP4_EXTRAM': 0,
    # S79: the off-aux park gate SHIPS. It reached shipping.config nine days
    # after S32 measured it, having defaulted to 0 in build.sh the whole time
    # (S78-Q3) -- and no word the part answered could say which of the two it
    # was running until this one.
    'DSP4_AUXIN_BYPASS': 1,
    # The capability, not a switch: 1 on any image built from the S79 tree or
    # later. A 0 here on a part the host is sending CFG_MTX_MASK to means the
    # host is writing to a cell with no reader.
    'MTX_GATE': 1,
    'DSP4_CUE': 0,
    'DSP4_RTA': 0,
    'DSP4_SPI_PARTIAL_FIX2': 1,
    'DSP4_DYN_TABLES': 0,
    'DSP4_DYN_INLINE': 2,
    'DSP4_C2_XPAIR': 1,
    'DSP4_DLY_SPLIT': 1,
    'DSP4_GAIN_SIMD': 1,
    'DSP4_RTG_FABRIC': 1,
    # The whole eight-class mask, which is the field that closes S27-3: CFG2
    # carries two bits of it and reads back 3 whether the image was built with
    # 3, 7 or 15.
    'DSP4_SHARED_KERNELS': 15,
    'INSTRUMENT': 0,
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
    if word is None or (word & SIGMASK2) != SIGNATURE2:
        raise ValueError('0x%s is not a DIAG_BUILD_CFG2 word '
                         '(signature 0b11 0001 in bits 31..30, 28..25)'
                         % ('%08X' % word if word is not None else '????????'))
    d = {'raw': word, 'decimate': (word >> 16) & 0xFF,
         # A PER-CHIP MASK, not a flag: 1 = chip 1's inter-chip TX,
         # 2 = chip 2's converter TX, 3 = both. Each chip that has it on
         # adds a block of output latency, so the value is the cost.
         'DSP4_TX_EARLY': (word >> 8) & 3,
         # Two-bit fields, like TX_EARLY: the VALUE is the cost.
         'DSP4_BQ_SIMD_PIPE': (word >> 13) & 3,
         # THE SHARED-KERNEL CLASS MASK (S18). Two bits, and they are not
         # adjacent -- diag.h had exactly two spare bits left. bit 5 is mask
         # bit 0, bit 15 is mask bit 1.
         'DSP4_SHARED_KERNELS': ((word >> 5) & 1) | (((word >> 15) & 1) << 1)}
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
    if d['DSP4_BQ_SIMD_PIPE']:
        lines.append('DSP4_BQ_SIMD_PIPE %d' % d['DSP4_BQ_SIMD_PIPE'])
    # THE WORD CARRIES TWO BITS OF THIS MASK AND THE MASK HAS FOUR (S27-3).
    # DIAG_BUILD_CFG2 has room for bit 0 (COMP, at bit 5) and bit 1 (TUBE, at
    # bit 15) and no room allocated for bit 2 (GATE) or bit 3 (FILT), which
    # S26 added. So `shipping.config.s21` (mask 3) and `shipping.config.s26`
    # (mask 15) produce the SAME two words, and this decoder cannot tell them
    # apart -- which is S12-7's shape one flag along. Say that here instead
    # of printing a number that reads like the whole mask, and point at the
    # word that DOES carry all four bits (DIAG_BUILD_CFG3, S80).
    if d['DSP4_SHARED_KERNELS']:
        lines.append('DSP4_SHARED_KERNELS %d (%s) — that class runs ONE body '
                     'for all 32 strips'
                     % (d['DSP4_SHARED_KERNELS'],
                        ', '.join(n for b, n in ((1, 'COMP'), (2, 'TUBE'))
                                  if d['DSP4_SHARED_KERNELS'] & b)))
        lines.append('  ^ TWO BITS ONLY: GATE (bit 2) and FILT (bit 3) are '
                     'NOT carried in DIAG_BUILD_CFG2, so this value does not '
                     'distinguish shipping.config.s21 from .s26 (S27-3). '
                     'DIAG_BUILD_CFG3 bits 15..8 carry the whole mask (S80) '
                     '-- read it there; fall back to the image md5 only on a '
                     'pre-S80 image, where CFG3 is unmapped.')
    on = [n for _, n in FLAGS2 if d[n]]
    off = [n for _, n in FLAGS2 if not d[n]]
    lines.append('on2:  ' + (', '.join(on) or '-'))
    lines.append('off2: ' + (', '.join(off) or '-'))
    return lines


def decode3(word):
    """Decode DIAG_BUILD_CFG3, or raise ValueError.

    UNLIKE decode()/decode2(), a raw value of 0 is not raised on -- it is
    decoded and REPORTED, because it has one meaning and it is not a garbage
    read. Between S75 and S80 diag.asm defined the _diag_build_cfg3 DM cell
    only `#if DSP4_EXTRAM` (a word of DM moves every address behind it, which
    would have cost S75 the "the L2 arm rebuilds byte-identical" proof), so
    0xE0EC was not in the dispatch table at all on a DSP4_EXTRAM=0 image and
    fell through to the unmapped-address default. S80 made the cell
    unconditional, so a 0 now means THE IMAGE PREDATES S80: it cannot say
    whether it carries the off-aux park gate, the matrix gate, the whole
    shared-kernel mask or the external-RAM pool. That is a real finding about
    a part on a bench, not a fault in this tool, so it decodes rather than
    raising -- and `diff_shipping3` fails it, because a shipping image built
    today answers 0xC47C0F26.
    """
    if word == 0:
        return {'raw': 0, 'present': False}
    if word is None or (word & 0xFF000000) != SIGNATURE3:
        raise ValueError('0x%s is not a DIAG_BUILD_CFG3 word (signature 0xC4)'
                         % ('%08X' % word if word is not None else '????????'))
    d = {'raw': word, 'present': True,
         'DSP4_SHARED_KERNELS': (word >> 8) & 0xFF,
         'DSP4_DYN_INLINE': (word >> 17) & 3}
    for bit, name in FLAGS3:
        d[name] = (word >> bit) & 1
    return d


def describe3(d):
    if not d['present']:
        return ['raw3 0x%08X — no DIAG_BUILD_CFG3 cell: this image was built '
                'BEFORE S80 (0xE0EC unmapped, reads 0). It cannot say whether '
                'it carries the off-aux park gate, the CFG_MTX_MASK reader, '
                'the whole shared-kernel mask or the external-RAM pool'
                % d['raw']]
    lines = ['raw3 0x%08X' % d['raw']]
    if d['INSTRUMENT']:
        lines.append('INSTRUMENT — at least one switch NO config word carries '
                     'a field for is off its shipping value: this is an '
                     'instrument or a debug build, whatever else it looks '
                     'like. WHICH switch is not in the word (fifty-six bits '
                     'do not exist); identify the arm by its image md5')
    if not d['MTX_GATE']:
        lines.append('MTX_GATE 0 — this image has NO reader for CFG_MTX_MASK '
                     '(0xF006): a host that sends the fourth product word to '
                     'it is writing to a cell nothing reads, and every chip-2 '
                     'matrix chain runs whatever the product is (pre-S79)')
    if d['DSP4_AUXIN_BYPASS']:
        lines.append('DSP4_AUXIN_BYPASS — the chip-2 off-aux park gate is in: '
                     'an AUX_INPUT whose `on` cell is 0 is not called at all')
    lines.append('DSP4_SHARED_KERNELS %d (%s) — the WHOLE eight-class mask, '
                 'which is what CFG2 could not say (S27-3)'
                 % (d['DSP4_SHARED_KERNELS'],
                    ', '.join(n for b, n in ((1, 'COMP'), (2, 'TUBE'),
                                             (4, 'GATE'), (8, 'FILT'))
                              if d['DSP4_SHARED_KERNELS'] & b) or 'none'))
    lines.append('DSP4_DYN_INLINE %d' % d['DSP4_DYN_INLINE'])
    on = [n for _, n in FLAGS3 if d[n]]
    off = [n for _, n in FLAGS3 if not d[n]]
    lines.append('on3:  ' + (', '.join(on) or '-'))
    lines.append('off3: ' + (', '.join(off) or '-'))
    return lines


def diff_shipping3(d):
    out = []
    if not d['present']:
        return ['DIAG_BUILD_CFG3 is ABSENT (0xE0EC reads 0): this image was '
                'built before S80 and cannot state its own park gate, matrix '
                'gate, shared-kernel mask or memory pool. A shipping image '
                'built today reads 0xC47C0F26']
    for k, want in SHIPPING3.items():
        got = d.get(k)
        if got != want:
            out.append('%s = %s, shipping is %s' % (k, got, want))
    for k in NEVER_SHIPPING3:
        if d.get(k):
            out.append('%s is SET — this is an instrument build, not a '
                       'shipping one' % k)
    return sorted(set(out))


def diff_shipping2(d):
    out = []
    for k, want in SHIPPING2.items():
        got = d.get(k)
        # DSP4_SHARED_KERNELS IS TWO BITS OF FOUR IN THIS WORD (S27-3), so the
        # decoded value can never be 15 however the image was built: mask 15
        # reads back as 3, mask 7 as 3, mask 12 as 0. Comparing the decoded
        # value against the mirror's 15 therefore reported EVERY shipping
        # image as "NOT THE SHIPPING KERNEL CONFIGURATION", which is how S77
        # found this — on the shipping pair, at the end of a bench session,
        # with the part reading the correct word. Only the two bits the word
        # actually carries can be compared, and what the other two are is a
        # question DIAG_BUILD_CFG3 answers since S80 (bits 15..8).
        if k == 'DSP4_SHARED_KERNELS':
            if got is not None and (got & 3) != (want & 3):
                out.append('%s = %s in the two bits this word carries, '
                           'shipping is %s (%s in those two bits); the other '
                           'two bits are not in CFG2 at all (S27-3) — '
                           'DIAG_BUILD_CFG3 bits 15..8 carry the whole mask '
                           '(S80); on a pre-S80 image, the image md5'
                           % (k, got, want, want & 3))
            continue
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


def read_word3(chip):
    """Read DIAG_BUILD_CFG3 alone (S75).

    Kept separate from read_word() rather than folded into a 3-tuple: other
    tools (dsp4_checkchip.py, dsp4_diag.py) import read_word() and unpack it
    as `w, w2 = ...` -- this file's contract with them must not change shape
    just because a third word now exists. Only this file's own CLI uses it.
    """
    from dsp4_config import SpiLink
    from dsp4_diag import DiagLink
    from dsp4_scope import CS_GPIO, RDY_GPIO, check_chip_id
    d = DiagLink(SpiLink('0.0', 1_000_000, CS_GPIO[chip],
                         rdy_gpio=RDY_GPIO[chip]))
    d.resync()
    check_chip_id(d.read(0xE001), chip)
    return d.read(DIAG_BUILD_CFG3)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--chip', type=int, choices=(1, 2), action='append')
    ap.add_argument('--word', help='decode a hex word instead of reading a part')
    ap.add_argument('--expect-shipping', action='store_true',
                    help='exit 4 unless the part carries the shipping build')
    args = ap.parse_args()

    if args.word:
        w = [int(x, 0) for x in args.word.split(',')]
        chips = [(None, (w[0], w[1] if len(w) > 1 else None,
                         w[2] if len(w) > 2 else None))]
    else:
        chips = [(c, read_word(c) + (read_word3(c),))
                 for c in (args.chip or [1, 2])]

    rc = 0
    for chip, (word, word2, word3) in chips:
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

        # THE THIRD WORD (S75, filled S80). word3 is None only from a --word
        # fewer than three values given -- decode3 raises on that exactly as
        # decode2 raises on a missing word2, and that is reported the same
        # way. A word3 of plain 0 is NOT an error case (see decode3): it
        # decodes cleanly and is diffed against SHIPPING3 like any other
        # word.
        try:
            d3 = decode3(word3)
        except ValueError as e:
            print('%s  %s' % (pad, e))
            print('%s  no DIAG_BUILD_CFG3 word given: this image predates '
                  'S75, or only two words were supplied to --word' % pad)
            if args.expect_shipping:
                rc = 4
            continue
        for line in describe3(d3):
            print('%s  %s' % (pad, line))
        bad3 = diff_shipping3(d3)
        if bad3:
            print('%s  NOT THE SHIPPING CONFIGURATION IN THE THIRD WORD:'
                  % pad)
            for b in bad3:
                print('%s    %s' % (pad, b))
            if args.expect_shipping:
                rc = 4
    return rc


if __name__ == '__main__':
    sys.exit(main())
