#!/usr/bin/env python3
"""cfg_words.py — the three DIAG_BUILD_CFG words a NAMED configuration must
read back on the part.

check_shipping_config.sh answers this question for `shipping.config` alone,
by diffing it against the bench mirror in tools/pi/dsp4_buildcfg.py. S20
needed it for a SECOND named configuration (`shipping.config.s20`, a proposed
successor), because gate 1's requirement is that the image read back
DIAG_BUILD_CFG / DIAG_BUILD_CFG2 matching THE FILE to the bit -- and a
proposal has no mirror to diff against.

So this computes both words from three things and nothing else:

  * the config file itself (tools/dsp/build_config.py reads it);
  * build.sh's DEFAULTS for every switch the file does not name, READ OUT OF
    build.sh rather than written down here (the check_shipping_config.sh
    discipline: a default in two places is findings S8-2 waiting to happen);
  * the DERIVATIONS, which are the only values stated in this file, each
    with the line of source that owns it.

  cfg_words.py                                  # shipping.config
  cfg_words.py MW/D32/DSP/SHARC/shipping.config.s20
  cfg_words.py <file> --json
  cfg_words.py <file> --check 0xCF45FF11,0xC201064F,0xC4000F26  # exit 4 on a
                                                     # mismatch in ANY word
"""
import argparse
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)
import build_config                                          # noqa: E402

ROOT = os.path.normpath(os.path.join(_HERE, '..', '..'))
BUILD_SH = os.path.join(ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'build.sh')
SHIPPING_CONFIG = os.path.join(ROOT, 'MW', 'D32', 'DSP', 'SHARC',
                               'shipping.config')

CCLK_CODE = {0: 0, 491: 0, 786: 1, 983: 2}

# Every switch a word carries, so a missing one is a KeyError here and not a
# silently-zero bit on the part. THIS FILE OWNS THE FIELD LIST FOR ALL THREE
# WORDS: check_shipping_config.sh's completeness gate uses these lists as its
# denominator, so a field added to a word in src/diag.h and not added here is
# not an omission, it is drift, and the check says so.
WORD1 = ['DSP4_BLOCK_KERNELS', 'DSP4_BLK_LATCH', 'DSP4_CHAN_MASK',
         'DSP4_SCOPE_GATE', 'DSP4_BQ_FLOAT', 'DSP4_GAIN_FLOAT',
         'DSP4_BISECT', 'DSP4_TXPROBE', 'DSP4_PROFILE_SIGNAL',
         'DSP4_BQ_ROUNDONCE', 'DSP4_BQ_GUARD']
WORD2 = ['DSP4_STRIP_FUSED', 'DSP4_SIMD_DYN', 'DSP4_SIMD_GRAPH',
         'DSP4_SIMD_STRIPS', 'DSP4_SCOPE_BLK_TAP', 'DSP4_GATHER_FIRST',
         'DSP4_FX_TYPE_DECLARED', 'DSP4_DYN_LUT', 'DSP4_GATE_LINTHR',
         'DSP4_C2_BQ_GRAPH', 'DSP4_TX_EARLY', 'DSP4_BQ_SIMD_PIPE',
         'DSP4_SHARED_KERNELS', 'DSP4_BLOCK_DECIMATE',
         # S72: the talkback polarity, bit 29 -- out of the signature, see
         # `words()` and the note in src/diag.h.
         'DSP4_TALK_INVERT',
         # S80: DIAG_BUILD_CFG2 HAS CARRIED THIS SINCE S49 (bit 24,
         # DIAG_CFG2_TEST_NODES in src/diag.h) AND THIS FILE DID NOT KNOW.
         # It is 0 in shipping.config, so `words()` computed the right word
         # for every image anyone has built -- and would have computed a
         # word 0x01000000 short for the first DSP4_TEST_NODES=1 arm anybody
         # scored with it, which is the one arm the tool exists to score. The
         # bench decoder (tools/pi/dsp4_buildcfg.py FLAGS2) has read it since
         # S49; only the repo-side computation was blind. Exactly the gap the
         # completeness gate below was built for, found by pointing that gate
         # at a third word.
         'DSP4_TEST_NODES']
# DIAG_BUILD_CFG3 (S75, filled S80). The switches the two full words cannot
# carry. DSP4_SHARED_KERNELS appears in BOTH lists on purpose: CFG2 carries
# two bits of the mask and is not re-laid out, CFG3 carries all eight.
WORD3 = ['DSP4_RTG_FABRIC', 'DSP4_GAIN_SIMD', 'DSP4_DLY_SPLIT',
         'DSP4_C2_XPAIR', 'DSP4_DYN_INLINE', 'DSP4_DYN_TABLES',
         'DSP4_SHARED_KERNELS', 'DSP4_SPI_PARTIAL_FIX2', 'DSP4_RTA',
         'DSP4_CUE', 'DSP4_AUXIN_BYPASS', 'DSP4_EXTRAM',
         # S89e: the deferred gather, bits 7..6. A per-chip mask, so the
         # VALUE is what it costs and what it covers, exactly as
         # DSP4_TX_EARLY is in WORD2.
         'DSP4_TX_DEFER']
# The CAPABILITY bits of DIAG_BUILD_CFG3 -- not build switches, so not in
# WORD3 and not resolvable from any config file. Each is a property of the
# SOURCE TREE, 1 here and 0 in every image built before the named session,
# and each exists because without it two images that behave differently
# answer identically.
CFG3_CAPS = {
    # S79: CFG_MTX_MASK (0xF006) is latched and resolved at CONFIG_COMMIT and
    # C2_MIX_AUX_nn sits behind its aux bit. One image boots every product
    # (D8), so this is not a switch and cannot be one -- but a host that
    # sends the fourth product word to a pre-S79 image is writing to a cell
    # with no reader, and nothing the part answered could say so.
    'MTX_GATE': 1,
}


def build_defaults():
    """{KEY: int} for every DSP4_* default build.sh declares.

    A plain `${KEY:-N}` is read directly. Two forms REFERENCE another switch
    rather than naming a number -- `${KEY:-$OTHER}` and
    `${KEY:-${OTHER:-N}}` -- and they used to be dropped on the floor here,
    which was survivable while nothing asked about them and is not any more:
    DIAG_BUILD_CFG3's instrument bit (S80) has to know the shipping value of
    EVERY switch none of the three words carries, and two of them
    (DSP4_NODE_LIMIT2, DSP4_DYN_SELFTEST) are of exactly that shape. A
    switch whose default this function could not read would have been a
    switch the instrument bit was silently blind to -- S12-7's shape in the
    tool built to close it.
    """
    src = open(BUILD_SH).read()
    raw = {}
    for m in re.finditer(r'^(DSP4_[A-Z0-9_]+)="\$\{\1:-([^}]*)\}"', src, re.M):
        raw[m.group(1)] = m.group(2)
    for m in re.finditer(r'^(DSP4_[A-Z0-9_]+)="\$\{\1:-\$\{([A-Z0-9_]+):-'
                         r'([^}]*)\}\}"', src, re.M):
        raw.setdefault(m.group(1), '$' + m.group(2))

    def resolve_raw(key, seen=()):
        v = raw.get(key)
        if v is None:
            return None
        if v.lstrip('-').isdigit():
            return int(v)
        if v.startswith('$') and v[1:] not in seen:
            return resolve_raw(v[1:].strip('{}'), seen + (key,))
        return None

    out = {}
    for k in raw:
        v = resolve_raw(k)
        if v is not None:
            out[k] = v
    return out


def resolve(path=None):
    """The full switch state a build from `path` produces.

    Returns (values, provenance) where provenance says, per key, whether the
    value came from the FILE, build.sh's DEFAULT, or a DERIVATION.
    """
    cfg = build_config.load(path) if path else build_config.load()
    if not cfg:
        raise SystemExit('cfg_words.py: %s names no configuration' % path)
    dflt = build_defaults()
    val, prov = {}, {}

    # ENVIRONMENT FIRST, exactly as build.sh reads it: shipping.config is
    # sourced only where the environment does not already say otherwise, so
    # `DSP4_X=... ./build.sh` still builds the control arm it always did. A
    # tool that scored the FILE while the part carries an override would be
    # the S11-1 gap in a new place, so the override is honoured here AND
    # named in the provenance.
    # EVERY SWITCH build.sh DECLARES, not only the ones a word carries. Until
    # S80 this loop read the two words' fields plus DSP4_AUXIN_BYPASS, which
    # was in neither word and was resolved anyway so `unrepresented()` could
    # say so -- a switch this tool does not read is a switch it cannot warn
    # about, which is how the park gate came to ship at build.sh's default
    # for nine days (S78-Q3). DIAG_BUILD_CFG3's instrument bit generalises
    # that: it is 1 if ANY switch none of the three words carries is off its
    # shipping value, so the tool has to resolve all of them or the bit is a
    # guess.
    for k in set(build_defaults()) | set(WORD1) | set(WORD2) | set(WORD3) | {
            'DSP4_GEN_BLOCK', 'DSP4_BLOCK_MASK', 'DSP4_CCLK_TARGET'}:
        if os.environ.get(k, '') != '':
            val[k], prov[k] = int(os.environ[k], 0), 'ENVIRONMENT override'
        elif k in cfg:
            val[k], prov[k] = cfg[k], 'file'
        elif k in dflt:
            val[k], prov[k] = dflt[k], 'build.sh default'

    # ---- the derivations, each with the source line that owns it ----
    # build.sh: DSP4_GAIN_FLOAT="${DSP4_GAIN_FLOAT:-$DSP4_BQ_FLOAT}"
    if prov.get('DSP4_GAIN_FLOAT') != 'ENVIRONMENT override' and 'DSP4_GAIN_FLOAT' not in cfg:
        val['DSP4_GAIN_FLOAT'] = val['DSP4_BQ_FLOAT']
        prov['DSP4_GAIN_FLOAT'] = 'derived: follows DSP4_BQ_FLOAT (build.sh)'
    # src/dsp_block.h: the float cascades are guard-free, so the guard is
    # FORCED off -- a config file that says 1 does not describe the image.
    if val['DSP4_BQ_FLOAT']:
        val['DSP4_BQ_GUARD'] = 0
        prov['DSP4_BQ_GUARD'] = ('derived: forced 0 by DSP4_BQ_FLOAT '
                                 '(src/dsp_block.h)')
    # build.sh: DSP4_SIMD_STRIPS_DEFAULT follows DSP4_SIMD_DYN.
    if prov.get('DSP4_SIMD_STRIPS') != 'ENVIRONMENT override' and 'DSP4_SIMD_STRIPS' not in cfg:
        val['DSP4_SIMD_STRIPS'] = 1 if val['DSP4_SIMD_DYN'] else 0
        prov['DSP4_SIMD_STRIPS'] = ('derived: follows DSP4_SIMD_DYN '
                                    '(build.sh DSP4_SIMD_STRIPS_DEFAULT)')

    # S18's refusal of DSP4_SHARED_KERNELS with DSP4_SIMD_DYN was mirrored
    # here and is GONE FROM BOTH (S21-2): the pair drivers reach a shared
    # class through that node's own stub, which loads the strip's record
    # base, so the two switches act on different code. build.sh checks it
    # per build (`shared_kernel_check.py --entries`) instead of refusing it.

    code = CCLK_CODE.get(val['DSP4_CCLK_TARGET'])
    if code is None:
        raise SystemExit('cfg_words.py: DSP4_CCLK_TARGET=%s is not 0, 786 or '
                         '983' % val['DSP4_CCLK_TARGET'])
    val['cclk'] = code
    prov['cclk'] = 'derived: %s MHz -> code %d' % (val['DSP4_CCLK_TARGET'], code)
    return val, prov


def words(val):
    """(DIAG_BUILD_CFG, DIAG_BUILD_CFG2), laid out as src/diag.h does.

    The THIRD word is `word3()`; this function keeps its two-tuple shape
    because check_shipping_config.sh and every arm script unpack it as a pair.
    `triple()` is the one that returns all three.
    """
    w1 = (0xCF000000
          | (val['DSP4_BQ_GUARD'] << 23) | (val['DSP4_BQ_ROUNDONCE'] << 22)
          | (val['DSP4_PROFILE_SIGNAL'] << 21) | (val['DSP4_TXPROBE'] << 20)
          | ((1 if val['DSP4_BISECT'] else 0) << 19)
          | (val['cclk'] << 17) | (val['DSP4_BLOCK_MASK'] << 14)
          | (val['DSP4_GAIN_FLOAT'] << 13) | (val['DSP4_BQ_FLOAT'] << 12)
          | (val['DSP4_SCOPE_GATE'] << 11) | (val['DSP4_CHAN_MASK'] << 10)
          | (val['DSP4_BLK_LATCH'] << 9) | (val['DSP4_BLOCK_KERNELS'] << 8)
          | (val['DSP4_GEN_BLOCK'] & 0xFF))
    # TWO BITS OF A FOUR-BIT MASK (S27-3). The word has room allocated for
    # bit 0 (COMP, at bit 5) and bit 1 (TUBE, at bit 15) and none for bit 2
    # (GATE) or bit 3 (FILT), which S26 added -- so `shipping.config.s21`
    # (mask 3) and `shipping.config.s26` (mask 15) produce IDENTICAL words
    # (0xC2019E6F, both of them) and the part cannot say which of the two it
    # is running. Widening it moves DIAG_BUILD_CFG2 on every image, so it is
    # named here and in `unrepresented()` below rather than changed
    # mid-window; until then the image md5 identifies a shared-kernel arm.
    #
    # AND THERE ARE NO FREE BITS IN THIS WORD (S28-5). This comment used to
    # say "free bits in w2 for the fix: 24 and 26-29" -- those are the ZERO
    # bits of the 0xC2 SIGNATURE, not spare field space, and bit 24 in
    # particular is what distinguishes 0xC2 from 0xC3. Enumerated rather
    # than eyeballed: every one of bits 0..31 has an owner.
    #
    # THE FIX LANDED AT S80 AND IT IS `word3()` BELOW, at S75's address and
    # signature. S28 gate 3 had designed a THIRD word of its own -- signature
    # 0xC3, every one of bits 23..0 allocated -- and this file carried it,
    # unapplied and printed by a `--design-cfg3` switch, for nine days while
    # S75 landed a DIFFERENT word of the same name (0xC4, one bit). The two
    # could not both be right; the hub ruled S75's (S75-13) and the 0xC3
    # design is DELETED, its field set carried into word3() at S75's
    # signature. S27-3 is closed there: bits 15..8 are the whole mask.
    #
    # S72 SPENT ONE OF THEM ANYWAY, AND SAYS SO: DSP4_TALK_INVERT is bit 29,
    # a zero bit of the signature, which is S49's move one bit along (bit 24
    # / DSP4_TEST_NODES). It was taken from the signature's ZERO side on
    # purpose -- with the flag off the word is still 0xC2000000, so a stale
    # decoder keeps reading shipping images correctly and REJECTS only the
    # inverted-talkback one. Narrowing at 25 instead would have made the
    # wrong arm the silently-accepted one. The signature is now six bits
    # (31..30, 28..25); the NEXT flag is the third word, not a seventh
    # narrowing.
    shk = val['DSP4_SHARED_KERNELS']
    w2 = (0xC2000000
          | ((1 if val['DSP4_TALK_INVERT'] else 0) << 29)
          # S49's bit, added to this computation at S80 -- see WORD2's note.
          | ((1 if val['DSP4_TEST_NODES'] else 0) << 24)
          | ((val['DSP4_BLOCK_DECIMATE'] & 0xFF) << 16)
          | (((shk >> 1) & 1) << 15)
          | ((val['DSP4_BQ_SIMD_PIPE'] & 3) << 13)
          | (val['DSP4_C2_BQ_GRAPH'] << 12)
          | (val['DSP4_GATE_LINTHR'] << 11)
          | (val['DSP4_DYN_LUT'] << 10)
          | ((val['DSP4_TX_EARLY'] & 3) << 8)
          | (val['DSP4_FX_TYPE_DECLARED'] << 7)
          | (val['DSP4_GATHER_FIRST'] << 6)
          | ((shk & 1) << 5)
          | ((1 if val['DSP4_SCOPE_BLK_TAP'] else 0) << 4)
          | (val['DSP4_SIMD_STRIPS'] << 3)
          | (val['DSP4_SIMD_GRAPH'] << 2)
          | (val['DSP4_SIMD_DYN'] << 1)
          | val['DSP4_STRIP_FUSED'])
    return w1, w2


def uncarried():
    """{KEY: shipping value} for every switch NONE of the three words carries.

    Derived, never written down: build.sh's declared defaults less every field
    of the three words, each at the value `shipping.config` resolves it to.
    This is the list DIAG_BUILD_CFG3's instrument bit (bit 23) is the truth
    value of, and src/diag.h carries the same list as literals --
    check_shipping_config.sh proves the two are the same list with the same
    values, in both directions, so the mirror is checked rather than trusted.
    """
    dflt = build_defaults()
    # THE FILE AND build.sh's DEFAULTS, AND DELIBERATELY NOT `resolve()`.
    # resolve() honours an ENVIRONMENT override, which is right when it is
    # describing the image being built and catastrophic here: the baseline
    # this is compared against would move with the very override the
    # instrument bit exists to detect, so `DSP4_PATTERN=1 ./build.sh` would
    # produce an image reading "shipping". The baseline is a property of
    # shipping.config alone.
    ship = build_config.load(SHIPPING_CONFIG)
    carried = set(WORD1) | set(WORD2) | set(WORD3) | {
        'DSP4_GEN_BLOCK', 'DSP4_BLOCK_MASK', 'DSP4_CCLK_TARGET'}
    return {k: ship.get(k, dflt[k]) for k in sorted(dflt) if k not in carried}


def instrument(val):
    """The switches in `val` that are off their shipping value.

    A non-empty list means DIAG_BUILD_CFG3 bit 23 reads 1 and the image is an
    instrument or a debug build, whatever else it looks like. WHICH switch is
    not in the word -- fifty-six bits do not exist -- so this returns the
    names for the tool to print and the part answers only the bit.
    """
    return [k for k, ship in sorted(uncarried().items())
            if int(val.get(k, ship)) != ship]


def word3(val):
    """DIAG_BUILD_CFG3, laid out as src/diag.h does (S75 address and
    signature, S80 fields).

    Signature 0xC4, bit 0 DSP4_EXTRAM: S75's, unmoved, because the hub ruled
    S75's layout stands (S75-13) and a landed signature is not renegotiable.
    Bits 23..1 were free and are now the switches the two full words cannot
    carry, plus the capability bits in CFG3_CAPS and the instrument bit.
    """
    shk = val['DSP4_SHARED_KERNELS']
    return (0xC4000000
            | ((1 if instrument(val) else 0) << 23)
            | ((val['DSP4_RTG_FABRIC'] & 1) << 22)
            | ((val['DSP4_GAIN_SIMD'] & 1) << 21)
            | ((val['DSP4_DLY_SPLIT'] & 1) << 20)
            | ((val['DSP4_C2_XPAIR'] & 1) << 19)
            | ((val['DSP4_DYN_INLINE'] & 3) << 17)
            | ((val['DSP4_DYN_TABLES'] & 1) << 16)
            # THE WHOLE EIGHT-CLASS MASK, which is what closes S27-3: CFG2
            # carries bits 0 and 1 of it (word bits 5 and 15) and mask 3 and
            # mask 15 have read back the same CFG2 since S26.
            | ((shk & 0xFF) << 8)
            | ((val['DSP4_TX_DEFER'] & 3) << 6)
            | ((val['DSP4_SPI_PARTIAL_FIX2'] & 1) << 5)
            | ((val['DSP4_RTA'] & 1) << 4)
            | ((val['DSP4_CUE'] & 1) << 3)
            | ((CFG3_CAPS['MTX_GATE'] & 1) << 2)
            | ((1 if val['DSP4_AUXIN_BYPASS'] else 0) << 1)
            | (1 if val['DSP4_EXTRAM'] else 0))


def triple(val):
    """(DIAG_BUILD_CFG, DIAG_BUILD_CFG2, DIAG_BUILD_CFG3)."""
    w1, w2 = words(val)
    return w1, w2, word3(val)


def unrepresented(val):
    """What the THREE words cannot say about this configuration.

    A check that passes is only worth what the words carry, and anything
    listed here is a setting two different images can disagree on while
    reading back the same three words -- S12-7's shape, which this project
    treats as a defect in the instrument rather than a footnote.

    S80 EMPTIED MOST OF THIS LIST AND THE REST OF IT IS ONE ENTRY. The two
    standing items were DSP4_AUXIN_BYPASS (S79) and DSP4_SHARED_KERNELS bits
    2..3 (S27-3); DIAG_BUILD_CFG3 carries both. What remains is the fifty-odd
    switches behind the instrument BIT: it says an image is not the product,
    and it does not say which switch made it so.
    """
    out = []
    instr = instrument(val)
    if instr:
        out.append('%d switch%s off the shipping value — %s. '
                   'DIAG_BUILD_CFG3 bit 23 reads 1, so the part DOES say '
                   '"this is not the product"; it does not say which switch, '
                   'and two different instrument arms read back the same '
                   'three words. Identify the arm by its image md5.'
                   % (len(instr), '' if len(instr) == 1 else 'es',
                      ', '.join('%s=%s' % (k, val.get(k)) for k in instr)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('config', nargs='?', help='config file (default: '
                                              'shipping.config)')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--check', help='CFG,CFG2[,CFG3] read off the part; exit 4 '
                                    'on a mismatch in any of them')
    ap.add_argument('--uncarried', action='store_true',
                    help='print the switches NO word carries a field for, at '
                         'their shipping value -- the list DIAG_BUILD_CFG3 '
                         'bit 23 is the truth value of')
    args = ap.parse_args()

    val, prov = resolve(args.config)
    w1, w2, w3 = triple(val)
    name = args.config or 'shipping.config'

    if args.uncarried:
        unc = uncarried()
        print('%s: %d switches in no word, DIAG_BUILD_CFG3 bit 23 is their '
              'truth value' % (name, len(unc)))
        for k, ship in sorted(unc.items()):
            got = val.get(k, ship)
            print('  %-26s shipping %-4s  this file %-4s %s'
                  % (k, ship, got, '' if int(got) == ship else '  <-- OFF'))
        instr = instrument(val)
        print('  instrument bit: %d%s'
              % (1 if instr else 0,
                 ('  (' + ', '.join(instr) + ')') if instr
                 else '  (a shipping image)'))
        return 0

    if args.json:
        print(json.dumps({'config': name, 'cfg': w1, 'cfg2': w2, 'cfg3': w3,
                          'instrument': instrument(val),
                          'values': {k: v for k, v in sorted(val.items())},
                          'provenance': prov}, indent=1))
    else:
        print('%s' % name)
        for k in sorted(val):
            print('  %-24s %-4s  %s' % (k, val[k], prov.get(k, '')))
        print('  DIAG_BUILD_CFG  must read 0x%08X' % w1)
        print('  DIAG_BUILD_CFG2 must read 0x%08X' % w2)
        print('  DIAG_BUILD_CFG3 must read 0x%08X' % w3)

    if args.check:
        got = [int(x, 0) for x in args.check.split(',')]
        want = [(w1, 'DIAG_BUILD_CFG '), (w2, 'DIAG_BUILD_CFG2'),
                (w3, 'DIAG_BUILD_CFG3')]
        bad = []
        for i, (w, label) in enumerate(want):
            if i >= len(got):
                continue
            if got[i] != w:
                bad.append('%s part 0x%08X, %s 0x%08X (differ 0x%08X)'
                           % (label, got[i], name, w, got[i] ^ w))
                # A CFG3 of plain 0 has one meaning and it is worth saying,
                # because it looks like a dead link and is not: the image
                # predates S80, where the word stopped being compiled out
                # `#if DSP4_EXTRAM` and became unconditional.
                if i == 2 and got[i] == 0:
                    bad.append('  ^ 0x00000000 at 0xE0EC is the UNMAPPED '
                               'answer: this image was built before S80 and '
                               'has no DIAG_BUILD_CFG3 cell at all, so it '
                               'cannot say whether it carries the off-aux '
                               'park gate, the matrix gate, the whole '
                               'shared-kernel mask or the external-RAM pool')
        for b in bad:
            print('CONFIG MISMATCH: ' + b)
        if bad:
            return 4
        if len(got) < 3:
            print('the part matches %s to the bit in the %d word%s given — '
                  'DIAG_BUILD_CFG3 (0x%08X) was NOT checked'
                  % (name, len(got), '' if len(got) == 1 else 's', w3))
        else:
            print('the part matches %s to the bit in all three words' % name)
        for line in unrepresented(val):
            print('  BUT THE WORDS DO NOT CARRY: ' + line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
