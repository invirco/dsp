#!/usr/bin/env python3
"""cfg_words.py — the two DIAG_BUILD_CFG words a NAMED configuration must
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
  cfg_words.py <file> --check 0xCF45FF11,0xC201064F   # exit 4 on a mismatch
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

CCLK_CODE = {0: 0, 491: 0, 786: 1, 983: 2}

# Every switch either word carries, so a missing one is a KeyError here and
# not a silently-zero bit on the part.
WORD1 = ['DSP4_BLOCK_KERNELS', 'DSP4_BLK_LATCH', 'DSP4_CHAN_MASK',
         'DSP4_SCOPE_GATE', 'DSP4_BQ_FLOAT', 'DSP4_GAIN_FLOAT',
         'DSP4_BISECT', 'DSP4_TXPROBE', 'DSP4_PROFILE_SIGNAL',
         'DSP4_BQ_ROUNDONCE', 'DSP4_BQ_GUARD']
WORD2 = ['DSP4_STRIP_FUSED', 'DSP4_SIMD_DYN', 'DSP4_SIMD_GRAPH',
         'DSP4_SIMD_STRIPS', 'DSP4_SCOPE_BLK_TAP', 'DSP4_GATHER_FIRST',
         'DSP4_FX_TYPE_DECLARED', 'DSP4_DYN_LUT', 'DSP4_GATE_LINTHR',
         'DSP4_C2_BQ_GRAPH', 'DSP4_TX_EARLY', 'DSP4_BQ_SIMD_PIPE',
         'DSP4_SHARED_KERNELS', 'DSP4_BLOCK_DECIMATE']


def build_defaults():
    """{KEY: int} for every DSP4_* build.sh defaults with `${KEY:-N}`."""
    src = open(BUILD_SH).read()
    out = {}
    for m in re.finditer(r'^(DSP4_[A-Z0-9_]+)="\$\{\1:-([^}]*)\}"', src, re.M):
        v = m.group(2)
        if v.lstrip('-').isdigit():
            out[m.group(1)] = int(v)
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
    for k in set(WORD1) | set(WORD2) | {'DSP4_GEN_BLOCK', 'DSP4_BLOCK_MASK',
                                       'DSP4_CCLK_TARGET'}:
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
    """(DIAG_BUILD_CFG, DIAG_BUILD_CFG2), laid out as src/diag.h does."""
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
    # than eyeballed: every one of bits 0..31 has an owner. The fix is a
    # THIRD word, designed in MW/D32/DSP/dsp4-s28-20260911.md section 3 and
    # printed by `--design-cfg3`.
    shk = val['DSP4_SHARED_KERNELS']
    w2 = (0xC2000000
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


# ---------------------------------------------------------------------------
# THE DESIGN, NOT THE IMPLEMENTATION (S28 gate 3)
# ---------------------------------------------------------------------------
# `design_cfg3()` computes the word a THIRD DIAG_BUILD_CFG would carry. It
# is deliberately NOT called by `words()` and NOT compared by `--check`:
# nothing in the firmware produces this word yet, and making the host
# expect a word the part does not answer would break every bar in the
# release window. It exists so the design can be read as numbers -- "s21
# would read 0xC3000306 and s26 0xC3000F06" -- before PW signs, and so the
# apply step is a diff against something rather than a description of one.
#
#   31..24  0xC3      signature; distinct from 0xCF and 0xC2 in bits 27..24
#   23      INSTRUMENT  1 if ANY switch in INSTRUMENT_SWITCHES is off its
#                       shipping default. A shipping image reads 0. This is
#                       the bit that makes "is this the product or an
#                       instrument?" a question the PART answers, which is
#                       what S11-1 cost a fortnight of capacity record.
#   22..16  DSP4_STRIPS          the COMPILE-TIME strip cut, 0..127
#   15..8   DSP4_SHARED_KERNELS  the WHOLE mask, eight classes
#    7      DSP4_RTG_FABRIC
#    6      DSP4_GAIN_SIMD
#    5      DSP4_DLY_SPLIT
#    4      DSP4_C2_XPAIR
#    3..2   DSP4_DYN_INLINE      0..3
#    1      DSP4_SPI_PARTIAL_FIX2
#    0      DSP4_DYN_TABLES
#
# DIAG_BUILD_CFG2 IS NOT RE-LAID OUT. Its two legacy SHARED_KERNELS bits
# stay exactly where they are, so its VALUE does not change for any image
# and every decoder that reads it keeps working; CFG3 is what tells mask 3
# from mask 15. The image md5 still moves, because the word has to exist in
# the image to be read out of it -- that is the whole cost of this change
# and it is why it waits for the window.
INSTRUMENT_SWITCHES = {
    'DSP4_PROFILE_SIGNAL': 0, 'DSP4_TXPROBE': 0, 'DSP4_BISECT': 0,
    'DSP4_BLOCK_DECIMATE': 1, 'DSP4_NODE_LIMIT': 0, 'DSP4_SCOPE_BLK_TAP': 0,
    'DSP4_MTR_OFF': 0, 'DSP4_PATTERN': 0, 'DSP4_BQ_PROBE': 0,
    'DSP4_BQ_TRACE': 0, 'DSP4_BQ_SELFTEST': 0, 'DSP4_BQ_SHOOTOUT': 0,
    'DSP4_DYN_SHOOTOUT': 0, 'DSP4_SIMD_PROBE': 0, 'DSP4_DAG_PROBE': 0,
    'DSP4_CALL_SELFTEST': 0, 'DSP4_NUM_SELFTEST': 0, 'DSP4_CFG_WATCH': 0,
    'DSP4_FAULT_TRAP': 0, 'DSP4_STRIPS': 0,
}
CFG3_FIELDS = ['DSP4_STRIPS', 'DSP4_SHARED_KERNELS', 'DSP4_RTG_FABRIC',
               'DSP4_GAIN_SIMD', 'DSP4_DLY_SPLIT', 'DSP4_C2_XPAIR',
               'DSP4_DYN_INLINE', 'DSP4_SPI_PARTIAL_FIX2', 'DSP4_DYN_TABLES']


def design_cfg3(path=None):
    """The PROPOSED third word for `path`, and what makes it non-zero.

    Reads the same three sources `resolve()` does -- the file, build.sh's
    defaults and the derivations -- so a switch this word carries cannot be
    read from somewhere the rest of the tool is not reading.
    """
    val, _ = resolve(path)
    dflt = build_defaults()
    full = dict(dflt)
    full.update(val)
    instrument = [k for k, ship in INSTRUMENT_SWITCHES.items()
                  if int(full.get(k, ship)) != ship]
    g = lambda k: int(full.get(k, dflt.get(k, 0)))          # noqa: E731
    w3 = (0xC3000000
          | ((1 if instrument else 0) << 23)
          | ((g('DSP4_STRIPS') & 0x7F) << 16)
          | ((g('DSP4_SHARED_KERNELS') & 0xFF) << 8)
          | ((g('DSP4_RTG_FABRIC') & 1) << 7)
          | ((g('DSP4_GAIN_SIMD') & 1) << 6)
          | ((g('DSP4_DLY_SPLIT') & 1) << 5)
          | ((g('DSP4_C2_XPAIR') & 1) << 4)
          | ((g('DSP4_DYN_INLINE') & 3) << 2)
          | ((g('DSP4_SPI_PARTIAL_FIX2') & 1) << 1)
          | (g('DSP4_DYN_TABLES') & 1))
    return w3, instrument


def unrepresented(val):
    """What the two words CANNOT say about this configuration.

    A check that passes is only worth what the words carry, and this one
    carries two bits of DSP4_SHARED_KERNELS. Anything listed here is a
    setting two different images can disagree on while reading back the
    same words -- S12-7's shape, which this project treats as a defect in
    the instrument rather than a footnote.
    """
    out = []
    shk = val['DSP4_SHARED_KERNELS']
    if shk & ~3:
        out.append('DSP4_SHARED_KERNELS=%d — bits 2 (GATE) and 3 (FILT) are '
                   'NOT in DIAG_BUILD_CFG2; an image built with mask %d reads '
                   'back the same two words as one built with mask %d, so '
                   'this check does not distinguish them (S27-3). Identify '
                   'the arm by its image md5.' % (shk, shk, shk & 3))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('config', nargs='?', help='config file (default: '
                                              'shipping.config)')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--check', help='CFG,CFG2 read off the part; exit 4 on a '
                                    'mismatch')
    ap.add_argument('--design-cfg3', action='store_true',
                    help='print the PROPOSED third config word for this file '
                         '(S28 gate 3). Design only: no image produces it, '
                         'nothing checks it.')
    args = ap.parse_args()

    val, prov = resolve(args.config)
    w1, w2 = words(val)
    name = args.config or 'shipping.config'

    if args.design_cfg3:
        w3, instrument = design_cfg3(args.config)
        print('%s' % name)
        print('  DIAG_BUILD_CFG  0x%08X   (unchanged by the design)' % w1)
        print('  DIAG_BUILD_CFG2 0x%08X   (unchanged by the design)' % w2)
        print('  DIAG_BUILD_CFG3 would read 0x%08X   -- PROPOSED, not applied'
              % w3)
        print('  instrument bit: %d%s'
              % (1 if instrument else 0,
                 ('  (' + ', '.join(sorted(instrument)) + ')')
                 if instrument else '  (a shipping image)'))
        for f in CFG3_FIELDS:
            print('    %-24s %s' % (f, val.get(f, '(build.sh default)')))
        return 0

    if args.json:
        print(json.dumps({'config': name, 'cfg': w1, 'cfg2': w2,
                          'values': {k: v for k, v in sorted(val.items())},
                          'provenance': prov}, indent=1))
    else:
        print('%s' % name)
        for k in sorted(val):
            print('  %-24s %-4s  %s' % (k, val[k], prov.get(k, '')))
        print('  DIAG_BUILD_CFG  must read 0x%08X' % w1)
        print('  DIAG_BUILD_CFG2 must read 0x%08X' % w2)

    if args.check:
        got = [int(x, 0) for x in args.check.split(',')]
        bad = []
        if got[0] != w1:
            bad.append('DIAG_BUILD_CFG  part 0x%08X, %s 0x%08X (differ 0x%08X)'
                       % (got[0], name, w1, got[0] ^ w1))
        if len(got) > 1 and got[1] != w2:
            bad.append('DIAG_BUILD_CFG2 part 0x%08X, %s 0x%08X (differ 0x%08X)'
                       % (got[1], name, w2, got[1] ^ w2))
        for b in bad:
            print('CONFIG MISMATCH: ' + b)
        if bad:
            return 4
        print('the part matches %s to the bit' % name)
        for line in unrepresented(val):
            print('  BUT THE WORDS DO NOT CARRY: ' + line)
    return 0


if __name__ == '__main__':
    sys.exit(main())
