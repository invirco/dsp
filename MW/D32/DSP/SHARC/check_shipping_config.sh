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

cfg = build_config.load()
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
print('shipping config: consistent; DIAG_BUILD_CFG must read 0x%08X' % w)
PY
