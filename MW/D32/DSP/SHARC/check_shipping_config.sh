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
w2 = (0xC2000000
      | ((mirror2['decimate'] & 0xFF) << 16)
      | (mirror2['DSP4_FX_TYPE_DECLARED'] << 7)
      | (mirror2['DSP4_GATHER_FIRST'] << 6)
      | ((mirror2['DSP4_TX_EARLY'] & 3) << 8)
      | ((1 if mirror2['DSP4_SCOPE_BLK_TAP'] else 0) << 4)
      | (mirror2['DSP4_SIMD_STRIPS'] << 3)
      | (mirror2['DSP4_SIMD_GRAPH'] << 2)
      | (mirror2['DSP4_SIMD_DYN'] << 1)
      | mirror2['DSP4_STRIP_FUSED'])
print('shipping config: consistent; DIAG_BUILD_CFG must read 0x%08X '
      'and DIAG_BUILD_CFG2 0x%08X' % (w, w2))
PY
