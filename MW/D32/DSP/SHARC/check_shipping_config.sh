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
set -u
cd "$(dirname "$0")/../../../.."
python3 - "$@" <<'PY'
import sys
sys.path.insert(0, 'tools/dsp')
import build_config

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

# THE THIRD WORD'S MIRROR (S75), checked the same way as want2/mirror2 above
# -- and for the same reason the check above quotes S74 by name: S74 found
# DSP4_TALK_INVERT sitting in DIAG_BUILD_CFG2 but never in THIS script's
# want2, so shipping.config could disagree with dsp4_buildcfg.SHIPPING2 on
# that one key and nothing here would notice. DIAG_BUILD_CFG3 is one flag
# old (DSP4_EXTRAM, S75) and gets its own want3 from day one rather than
# waiting to be the next gap.
mirror3 = ns['SHIPPING3']
want3 = {
    'DSP4_EXTRAM': bdefault('DSP4_EXTRAM', 0),
}
for k, v in cfg.items():
    if k in want3:
        want3[k] = v
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
import cfg_words
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
# THE THIRD WORD'S readback (S75). DIAG_BUILD_CFG3's DM cell only exists
# `#if DSP4_EXTRAM` (diag.asm) -- widening DM for every image just to carry
# a word that is 0 on every shipping build today would have cost S75 its
# byte-identical-rebuild proof. So with mirror3['DSP4_EXTRAM'] == 0 (today's
# shipping value) 0xE0EC is not in the part's dispatch table at all: it
# reads back the unmapped answer, plain 0 -- NOT 0xC4000000 -- and the line
# below must say that plainly rather than quote a signed word the part will
# never return, or a bench operator chasing a "wrong" CFG3 reading would be
# chasing a phantom.
if mirror3['DSP4_EXTRAM']:
    w3 = 0xC4000000 | (mirror3['DSP4_EXTRAM'] & 1)
    cfg3_msg = 'and DIAG_BUILD_CFG3 0x%08X' % w3
else:
    cfg3_msg = ('and DIAG_BUILD_CFG3 UNMAPPED (reads 0x00000000, not '
                '0xC4000000 -- DSP4_EXTRAM=0 compiles the word out entirely; '
                'this is the normal reading today, not a fault)')
print('shipping config: consistent; DIAG_BUILD_CFG must read 0x%08X, '
      'DIAG_BUILD_CFG2 0x%08X, %s' % (w, w2, cfg3_msg))
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
