#!/bin/bash
# check_shipping_config.sh — shipping.config and the bench-side mirror of it
# must not drift apart.
#
# shipping.config is the ONE place the shipping build parameters are named
# (build.sh sources it, dsp_codegen.py reads DSP4_GEN_BLOCK from it). The bench
# cannot read it -- the repo is not checked out there -- so
# tools/pi/dsp4_buildcfg.py carries a mirror, SHIPPING, which is what
# `--expect-shipping` scores a running part against. Two copies of a fact is
# how S8-2 happened; this is the check that keeps them one fact.
#
# A key may legitimately appear in only one of the two: shipping.config has
# DSP4_GEN_BLOCK (spelt `block` in the word) and the mirror has DERIVED values
# such as DSP4_BQ_GUARD, which dsp_block.h forces off in a float build. What is
# not allowed is the same key with two different values.
#
# THERE ARE THREE WORDS AS OF S80, and this script checks all three plus the
# one thing neither the file nor the mirrors own: src/diag.h's literals for
# DIAG_BUILD_CFG3's instrument bit, which have to agree with the list
# cfg_words.uncarried() derives. It prints the TRIPLE a shipping image must
# read back, computed from the bench mirror, and refuses to print it unless
# cfg_words.py -- computing independently from build.sh and the file -- gets
# the same three numbers.
#
# THIS IS THE HOST HALF. It never touches a part. `tools/pi/dsp4_buildcfg.py
# --expect-shipping` is the other half and reads the triple off the DSP.
set -u
cd "$(dirname "$0")/../../../.."
python3 - "$@" <<'PY'
import sys
sys.path.insert(0, 'tools/dsp')
import build_config

# THE ARGUMENTS, NAMED RATHER THAN IGNORED (S80). This script took "$@" and
# looked at none of it, so `check_shipping_config.sh --expect-shipping` --
# which is how the dispatch that landed DIAG_BUILD_CFG3 spelt it, and a
# reasonable thing to type -- passed silently and meant nothing. A flag that
# is accepted and does nothing is worse than one that is refused: it reads
# like a check that ran. There is exactly one mode here (the HOST half: the
# file against the mirrors), `--expect-shipping` is accepted as its name
# because that is what it does, and anything else is refused.
for _a in sys.argv[1:]:
    if _a in ('--expect-shipping', '--host'):
        continue
    print('check_shipping_config.sh: unknown argument %r.\n'
          '  This script has one mode: it proves shipping.config and the two\n'
          '  bench mirrors are one fact, and prints the triple a shipping\n'
          '  image must read back. `--expect-shipping` is accepted as a name\n'
          '  for that. To score a PART, run the bench tool:\n'
          '      tools/pi/dsp4_buildcfg.py --expect-shipping' % _a)
    sys.exit(2)

# THE FILE, NAMED. This script is about `shipping.config` specifically --
# it diffs it against the bench mirror -- so it must not follow a
# SHIPPING_CONFIG in the environment to some other configuration and then
# report that the mirror disagrees with it (S20).
cfg = build_config.load('MW/D32/DSP/SHARC/shipping.config')
ns = {}
src = open('tools/pi/dsp4_buildcfg.py').read()
exec(compile(src.split('def decode')[0], 'dsp4_buildcfg.py', 'exec'), ns)
mirror = ns['SHIPPING']

# The two spellings of the same fact.
alias = {'DSP4_GEN_BLOCK': 'block', 'DSP4_BLOCK_MASK': 'block_mask'}
cclk_code = {0: 0, 491: 0, 786: 1, 983: 2}

bad = []
for k, v in cfg.items():
    if k == 'DSP4_CCLK_TARGET':
        want = cclk_code.get(v)
        if want is None:
            bad.append('shipping.config DSP4_CCLK_TARGET=%s is not 0, 786 or 983' % v)
        elif mirror.get('cclk') != want:
            bad.append("cclk: shipping.config says %s MHz (code %s), "
                       "dsp4_buildcfg.SHIPPING says code %s"
                       % (v, want, mirror.get('cclk')))
        continue
    mk = alias.get(k, k)
    if mk in mirror and mirror[mk] != v:
        bad.append('%s: shipping.config %s, dsp4_buildcfg.SHIPPING %s'
                   % (k, v, mirror[mk]))

# THE SECOND WORD'S MIRROR, checked the same way. shipping.config does not
# name DSP4_STRIP_FUSED / DSP4_SIMD_DYN / DSP4_TX_EARLY -- they take
# build.sh's defaults -- and that is exactly how the capacity record spent a
# fortnight quoting an image with two of them ON (S11-1). So the defaults are
# READ OUT OF build.sh here and diffed against the bench mirror, rather than
# being a third place the same fact is written down.
import re
bsh = open('MW/D32/DSP/SHARC/build.sh').read()
def bdefault(key, fallback):
    m = re.search(r'^%s="\$\{%s:-([^}]*)\}"' % (key, key), bsh, re.M)
    if not m:
        return fallback
    v = m.group(1)
    return int(v) if v.lstrip('-').isdigit() else v

mirror2 = ns['SHIPPING2']
want2 = {
    'decimate':               bdefault('DSP4_BLOCK_DECIMATE', 1),
    'DSP4_STRIP_FUSED':       bdefault('DSP4_STRIP_FUSED', 0),
    'DSP4_SIMD_DYN':          bdefault('DSP4_SIMD_DYN', 0),
    'DSP4_SIMD_GRAPH':        bdefault('DSP4_SIMD_GRAPH', 1),
    'DSP4_SCOPE_BLK_TAP':     bdefault('DSP4_SCOPE_BLK_TAP', 0),
    'DSP4_TX_EARLY':          bdefault('DSP4_TX_EARLY', 0),
    'DSP4_GATHER_FIRST':      bdefault('DSP4_GATHER_FIRST', 1),
    'DSP4_FX_TYPE_DECLARED':  bdefault('DSP4_FX_TYPE_DECLARED', 0),
    # S74: DSP4_TALK_INVERT was in DIAG_BUILD_CFG2 (bit 29, S72) but never
    # in THIS check's want2 -- shipping.config could disagree with the
    # dsp4_buildcfg.SHIPPING2 mirror on this one key and neither the WORD1
    # loop above (which only compares against `mirror`, the word-1 dict,
    # and this key is not in it) nor this dict would have caught it. Closed
    # the same way the other word-2 switches are: build.sh's default, then
    # shipping.config's override.
    'DSP4_TALK_INVERT':       bdefault('DSP4_TALK_INVERT', 0),
    # S77: the five DIAG_BUILD_CFG2 fields neither this dict nor the bench
    # mirror carried. Four are 0 and always were; DSP4_SHARED_KERNELS is 15
    # since S76, and its absence here is why this script announced
    # 0xE2010244 for an image that reads 0xE2018264 -- while printing
    # "consistent". See the completeness gate below, which is the part that
    # stops the next one.
    'DSP4_DYN_LUT':           bdefault('DSP4_DYN_LUT', 0),
    'DSP4_GATE_LINTHR':       bdefault('DSP4_GATE_LINTHR', 0),
    'DSP4_C2_BQ_GRAPH':       bdefault('DSP4_C2_BQ_GRAPH', 0),
    'DSP4_BQ_SIMD_PIPE':      bdefault('DSP4_BQ_SIMD_PIPE', 0),
    'DSP4_SHARED_KERNELS':    bdefault('DSP4_SHARED_KERNELS', 0),
    # S80, AND FOUND BY THIS SCRIPT'S OWN GATE. DIAG_BUILD_CFG2 has carried
    # DSP4_TEST_NODES at bit 24 since S49 and the bench mirror has decoded it
    # since S49 -- this dict never had it, and neither did cfg_words.WORD2, so
    # the word the repo side COMPUTED for a DSP4_TEST_NODES=1 arm was
    # 0x01000000 short of what that arm's part answers. Nothing had built one
    # since (it is 0 in shipping.config), so nothing had failed; adding the
    # word-3 fields to the completeness gate turned it up in the word above.
    'DSP4_TEST_NODES':        bdefault('DSP4_TEST_NODES', 0),
}
# DSP4_SIMD_STRIPS is derived: build.sh defaults it to 1 whenever
# DSP4_SIMD_DYN is on. Derived, so computed here rather than read.
want2['DSP4_SIMD_STRIPS'] = 1 if want2['DSP4_SIMD_DYN'] else 0
# shipping.config may still override any of them.
for k, v in cfg.items():
    kk = 'decimate' if k == 'DSP4_BLOCK_DECIMATE' else k
    if kk in want2:
        want2[kk] = v
for k, v in want2.items():
    if mirror2.get(k) != v:
        bad.append('%s: the build says %s, dsp4_buildcfg.SHIPPING2 says %s'
                   % (k, v, mirror2.get(k)))

# THE THIRD WORD'S MIRROR (S75, twelve switches wide since S80), checked the
# same way as want2/mirror2 above -- and for the same reason the check above
# quotes S74 by name: S74 found DSP4_TALK_INVERT sitting in DIAG_BUILD_CFG2 but
# never in THIS script's want2, so shipping.config could disagree with
# dsp4_buildcfg.SHIPPING2 on that one key and nothing here would notice. want3
# is DERIVED from cfg_words.WORD3 rather than typed out, so a field added to
# the word reaches this check without anybody remembering to add it.
mirror3 = ns['SHIPPING3']
import cfg_words
want3 = {k: bdefault(k, 0) for k in cfg_words.WORD3}
for k, v in cfg.items():
    if k in want3:
        want3[k] = v
# THE CAPABILITY BITS ARE NOT SWITCHES and cannot come from build.sh or from
# the config file: they are properties of the SOURCE TREE (MTX_GATE = this
# image resolves CFG_MTX_MASK, S79), so cfg_words.py states them and the
# bench mirror has to agree with that statement rather than with a default
# that does not exist. INSTRUMENT is the same shape and is 0 for a shipping
# image by definition.
want3.update(cfg_words.CFG3_CAPS)
want3['INSTRUMENT'] = 1 if cfg_words.instrument(
    cfg_words.resolve('MW/D32/DSP/SHARC/shipping.config')[0]) else 0
for k, v in want3.items():
    if mirror3.get(k) != v:
        bad.append('%s: the build says %s, dsp4_buildcfg.SHIPPING3 says %s'
                   % (k, v, mirror3.get(k)))

# ---- THE COMPLETENESS GATE (S77) ----
#
# Everything above compares the keys somebody remembered to list. Three times
# now a switch has reached DIAG_BUILD_CFG/CFG2 and never reached these dicts
# -- DSP4_STRIP_FUSED and DSP4_SIMD_DYN (S11-1), DSP4_TALK_INVERT (S74-2),
# and DSP4_SHARED_KERNELS with DYN_LUT, GATE_LINTHR, C2_BQ_GRAPH and
# BQ_SIMD_PIPE beside it (S77) -- and each time the check PASSED while the
# word it announced was wrong, because a key in only one copy was allowed.
# tools/dsp/cfg_words.py owns the list of fields each word carries, so that
# list is the denominator here: a field the word carries and these mirrors
# do not is DRIFT, not an omission.
alias2 = {'DSP4_BLOCK_DECIMATE': 'decimate'}
for k in cfg_words.WORD1:
    kk = alias.get(k, k)
    if kk not in mirror and k not in ('DSP4_GAIN_FLOAT',):
        bad.append('%s is in DIAG_BUILD_CFG and not in '
                   'dsp4_buildcfg.SHIPPING' % k)
for k in cfg_words.WORD2:
    kk = alias2.get(k, k)
    if kk not in want2:
        bad.append('%s is in DIAG_BUILD_CFG2 and not in this script\'s want2'
                   % k)
    if kk not in mirror2:
        bad.append('%s is in DIAG_BUILD_CFG2 and not in '
                   'dsp4_buildcfg.SHIPPING2' % k)
# THE THIRD WORD, under the same gate from its first full day (S80). It landed
# with one field (S75) and nobody had to remember anything; it now carries
# twelve switches, two multi-bit fields and two bits that are not switches at
# all, which is exactly the size at which the last three gaps opened.
for k in cfg_words.WORD3:
    if k not in want3:
        bad.append('%s is in DIAG_BUILD_CFG3 and not in this script\'s want3'
                   % k)
    if k not in mirror3:
        bad.append('%s is in DIAG_BUILD_CFG3 and not in '
                   'dsp4_buildcfg.SHIPPING3' % k)
for k in list(cfg_words.CFG3_CAPS) + ['INSTRUMENT']:
    if k not in mirror3:
        bad.append('%s is a DIAG_BUILD_CFG3 field and not in '
                   'dsp4_buildcfg.SHIPPING3' % k)
# ...and every field the DECODER reads must be a field somebody expects a
# value for, which is the gate run the other way round. S77's hole was a field
# in the word and not in the mirror; the mirror carrying a field the word does
# not have would be the same defect with the sign flipped -- the check would
# compare a key the part can never answer and pass on it for ever.
_decl3 = set(cfg_words.WORD3) | set(cfg_words.CFG3_CAPS) | {'INSTRUMENT'}
for _bit, k in ns['FLAGS3']:
    if k not in _decl3:
        bad.append('dsp4_buildcfg.FLAGS3 decodes %s, which cfg_words.py does '
                   'not say DIAG_BUILD_CFG3 carries' % k)

# ---- EVERY WORD FIELD MUST BE NAMED IN shipping.config (S82) ----
#
# THE FIFTH TIME, AND THE FIRST TIME IT IS A RULE RATHER THAN A PATCH.
# S8-2/S9-1 (block, block kernels, core clock), S11-1 (STRIP_FUSED /
# SIMD_DYN), S76 (SHARED_KERNELS) and S79 (AUXIN_BYPASS) are one fault with
# four dates on it: a switch that decides what ships reached the image
# through build.sh's default while shipping.config -- the file whose entire
# job is to be the one place the shipping configuration is written down --
# said nothing about it. Every previous fix named the one switch that had
# just been found.
#
# The checks above are not this check. They prove the FILE and the MIRRORS
# agree, and they agree perfectly about a switch neither of them names,
# because both sides fall through to the same build.sh default. What that
# cannot survive is build.sh's default MOVING: the image changes, the word
# changes, and every copy of the configuration still agrees with every
# other. So: a field a config word carries is a field the shipping image is
# identified by, and it must be NAMED here.
#
# The exemptions are the values NO configuration can set, and each is named
# rather than pattern-matched, because an exemption list that grows by
# regex is how the hole reopens. DSP4_BQ_GUARD is forced to 0 by
# src/dsp_block.h under DSP4_BQ_FLOAT (cfg_words.resolve says so in its
# provenance), so a line setting it would not describe the image.
_UNSETTABLE = {'DSP4_BQ_GUARD'}
_named = set(cfg)
for k in sorted((set(cfg_words.WORD1) | set(cfg_words.WORD2)
                 | set(cfg_words.WORD3)) - _named - _UNSETTABLE):
    bad.append('%s is carried by a config word and is NOT NAMED in '
               'shipping.config: the shipping image takes it from build.sh\'s '
               'default, which is findings S8-2 / S11-1 / S76 / S79 and is '
               'the fault this file exists for' % k)
# ...and the exemption list itself is checked, in both directions: a key
# exempted here that a word does not carry, or that a configuration CAN
# set, is an exemption nobody will revisit.
for k in sorted(_UNSETTABLE):
    if k in _named:
        bad.append('%s is in check_shipping_config.sh\'s _UNSETTABLE list and '
                   'shipping.config names it anyway -- one of the two is '
                   'wrong' % k)
    prov = cfg_words.resolve('MW/D32/DSP/SHARC/shipping.config')[1].get(k, '')
    if not prov.startswith('derived'):
        bad.append('%s is exempted from the naming rule as unsettable, but '
                   'cfg_words.py resolves it from %r -- it is settable and '
                   'must be named in shipping.config' % (k, prov))

# ---- THE INSTRUMENT BIT'S LIST, IN BOTH PLACES (S80) ----
#
# DIAG_BUILD_CFG3 bit 23 is the truth value of "any switch NO word carries a
# field for is off its shipping value". src/diag.h has to compute that at
# assembly time, from literals, because the cell that carries the word is
# assembled -- so the list and its values exist twice, which is the S8-2 shape
# this whole script exists to police. cfg_words.uncarried() DERIVES the list
# from build.sh and shipping.config; the block in diag.h is checked against it
# in BOTH directions and on the VALUES, so the duplication is proved rather
# than trusted.
_diag_h = open('MW/D32/DSP/SHARC/src/diag.h').read()
_m = re.search(r'#define DIAG_CFG3_INSTR_SUM \((.*?)\)\n#if', _diag_h, re.S)
if not _m:
    bad.append('src/diag.h has no DIAG_CFG3_INSTR_SUM block: DIAG_BUILD_CFG3 '
               'bit 23 cannot be computed and this check cannot verify it')
else:
    _hdr = dict((g[0], int(g[1]))
                for g in re.findall(r'\+\s*\((DSP4_[A-Z0-9_]+)\s*!=\s*'
                                    r'(-?\d+)\)', _m.group(1)))
    _want = cfg_words.uncarried()
    for k in sorted(set(_want) - set(_hdr)):
        bad.append('%s is carried by NO config word and is NOT in '
                   'src/diag.h\'s DIAG_CFG3_INSTR_SUM: an image built with it '
                   'moved would read back bit 23 = 0 and call itself the '
                   'product' % k)
    for k in sorted(set(_hdr) - set(_want)):
        bad.append('src/diag.h\'s DIAG_CFG3_INSTR_SUM compares %s, which is '
                   'not in cfg_words.uncarried() — either a config word now '
                   'carries a field for it (so it must come out of the sum) '
                   'or build.sh no longer declares it' % k)
    for k in sorted(set(_hdr) & set(_want)):
        if _hdr[k] != _want[k]:
            bad.append('%s: src/diag.h\'s DIAG_CFG3_INSTR_SUM compares '
                       'against %s, the shipping value is %s'
                       % (k, _hdr[k], _want[k]))

for b in bad:
    print('SHIPPING CONFIG DRIFT: ' + b)
if bad:
    sys.exit(1)

# Print the word a shipping image must read back, so a bench can check by eye.
w = (0xCF000000
     | (mirror['DSP4_BQ_GUARD'] << 23) | (mirror['DSP4_BQ_ROUNDONCE'] << 22)
     | (mirror['DSP4_PROFILE_SIGNAL'] << 21) | (mirror['DSP4_TXPROBE'] << 20)
     | ((1 if mirror['DSP4_BISECT'] else 0) << 19)
     | (mirror['cclk'] << 17) | (mirror['block_mask'] << 14)
     | (mirror['DSP4_GAIN_FLOAT'] << 13) | (mirror['DSP4_BQ_FLOAT'] << 12)
     | (mirror['DSP4_SCOPE_GATE'] << 11) | (mirror['DSP4_CHAN_MASK'] << 10)
     | (mirror['DSP4_BLK_LATCH'] << 9) | (mirror['DSP4_BLOCK_KERNELS'] << 8)
     | mirror['block'])
# EVERY FIELD, in cfg_words.py's layout. The five added in S77 are the two
# DSP4_SHARED_KERNELS bits (5 and 15 -- two bits of a four-bit field, S27-3)
# and DYN_LUT / GATE_LINTHR / C2_BQ_GRAPH / BQ_SIMD_PIPE.
shk = mirror2['DSP4_SHARED_KERNELS']
w2 = (0xC2000000
      | ((1 if mirror2['DSP4_TALK_INVERT'] else 0) << 29)
      | ((mirror2['decimate'] & 0xFF) << 16)
      | (((shk >> 1) & 1) << 15)
      | ((mirror2['DSP4_BQ_SIMD_PIPE'] & 3) << 13)
      | (mirror2['DSP4_C2_BQ_GRAPH'] << 12)
      | (mirror2['DSP4_GATE_LINTHR'] << 11)
      | (mirror2['DSP4_DYN_LUT'] << 10)
      | ((mirror2['DSP4_TX_EARLY'] & 3) << 8)
      | (mirror2['DSP4_FX_TYPE_DECLARED'] << 7)
      | (mirror2['DSP4_GATHER_FIRST'] << 6)
      | ((shk & 1) << 5)
      | ((1 if mirror2['DSP4_SCOPE_BLK_TAP'] else 0) << 4)
      | (mirror2['DSP4_SIMD_STRIPS'] << 3)
      | (mirror2['DSP4_SIMD_GRAPH'] << 2)
      | (mirror2['DSP4_SIMD_DYN'] << 1)
      | mirror2['DSP4_STRIP_FUSED'])
# THE THIRD WORD'S readback (S75, filled S80). Built from the BENCH MIRROR's
# own dict, like w and w2 above and not from cfg_words.py: the point of
# printing it here is that the mirror a bench actually scores a part against
# produces this word, so computing it from the repo-side tool would prove
# nothing about the mirror. Between S75 and S80 this had to print "UNMAPPED,
# reads 0" instead of a word, because diag.asm defined the DM cell only
# `#if DSP4_EXTRAM` and every shipping image answered plain 0 at 0xE0EC. The
# cell is unconditional now, so there is a word to print -- and a part that
# still answers 0 is a pre-S80 image and says so.
shk3 = mirror3['DSP4_SHARED_KERNELS']
w3 = (0xC4000000
      | ((1 if mirror3['INSTRUMENT'] else 0) << 23)
      | ((mirror3['DSP4_RTG_FABRIC'] & 1) << 22)
      | ((mirror3['DSP4_GAIN_SIMD'] & 1) << 21)
      | ((mirror3['DSP4_DLY_SPLIT'] & 1) << 20)
      | ((mirror3['DSP4_C2_XPAIR'] & 1) << 19)
      | ((mirror3['DSP4_DYN_INLINE'] & 3) << 17)
      | ((mirror3['DSP4_DYN_TABLES'] & 1) << 16)
      | ((shk3 & 0xFF) << 8)
      | ((mirror3['DSP4_TX_DEFER'] & 3) << 6)
      | ((mirror3['DSP4_SPI_PARTIAL_FIX2'] & 1) << 5)
      | ((mirror3['DSP4_RTA'] & 1) << 4)
      | ((mirror3['DSP4_CUE'] & 1) << 3)
      | ((mirror3['MTX_GATE'] & 1) << 2)
      | ((1 if mirror3['DSP4_AUXIN_BYPASS'] else 0) << 1)
      | (1 if mirror3['DSP4_EXTRAM'] else 0))
# AND THE TWO SIDES OF THE TRIPLE MUST AGREE. The words above come from the
# bench mirror; cfg_words.py computes the same three from build.sh and the
# file. They are independent computations of one fact, which is the only
# reason either is worth printing, so the disagreement is an error and not a
# footnote -- this is the check that would have caught S77's 0xE2010244
# without needing a part on a bench to notice.
_val, _ = cfg_words.resolve('MW/D32/DSP/SHARC/shipping.config')
_t = cfg_words.triple(_val)
for _lbl, _a, _b in (('DIAG_BUILD_CFG', w, _t[0]),
                     ('DIAG_BUILD_CFG2', w2, _t[1]),
                     ('DIAG_BUILD_CFG3', w3, _t[2])):
    if _a != _b:
        print('SHIPPING CONFIG DRIFT: %s: the bench mirror computes 0x%08X, '
              'cfg_words.py computes 0x%08X (differ 0x%08X)'
              % (_lbl, _a, _b, _a ^ _b))
        sys.exit(1)
print('shipping config: consistent; the part must read DIAG_BUILD_CFG '
      '0x%08X, DIAG_BUILD_CFG2 0x%08X, DIAG_BUILD_CFG3 0x%08X' % (w, w2, w3))
print('  on the bench:  dsp4_buildcfg.py --expect-shipping        '
      '# reads all three off the part')
print('  by hand:       dsp4_buildcfg.py --expect-shipping --word '
      '0x%08X,0x%08X,0x%08X' % (w, w2, w3))
print('  a part answering 0x00000000 at 0xE0EC is a PRE-S80 image: it has no '
      'DIAG_BUILD_CFG3 cell at all')
# ...AND WHAT A PASS HERE DOES NOT COVER (S79). `consistent` means the
# mirrors agree with the file, which is worth exactly what the two words
# carry -- and `cfg_words.unrepresented()` is the list of settings two
# images can disagree on while reading back the same pair. Printing it on
# every pass is the same discipline as S77-11's completeness gate: a check
# that is silent about its own blind spot reads as a check that has none.
# The list is a property of the CONFIGURATION, not of these mirrors, so it
# is resolved from the file the same way the words are -- `mirror2` is the
# bench tool's own dict and carries only what a word carries, which is
# exactly the set this list is about.
_val, _ = cfg_words.resolve('MW/D32/DSP/SHARC/shipping.config')
for _line in cfg_words.unrepresented(_val):
    print('  NOT IN EITHER WORD: ' + _line)
PY
