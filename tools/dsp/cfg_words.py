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

    # build.sh refuses this pair rather than mis-building it (S18).
    if val['DSP4_SHARED_KERNELS'] and val['DSP4_SIMD_DYN']:
        raise SystemExit('cfg_words.py: DSP4_SHARED_KERNELS with '
                         'DSP4_SIMD_DYN is not a configuration — build.sh '
                         'exits 2 on it (S18).')

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


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('config', nargs='?', help='config file (default: '
                                              'shipping.config)')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--check', help='CFG,CFG2 read off the part; exit 4 on a '
                                    'mismatch')
    args = ap.parse_args()

    val, prov = resolve(args.config)
    w1, w2 = words(val)
    name = args.config or 'shipping.config'

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
    return 0


if __name__ == '__main__':
    sys.exit(main())
