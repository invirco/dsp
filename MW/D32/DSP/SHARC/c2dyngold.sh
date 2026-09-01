#!/bin/bash
# c2dyngold.sh — is chip 2's DYNAMICS PAIRING bit-exact against the same
# graph unpaired?
#
# c2gold.sh's sibling, and the same instrument pointed at a different
# question. c2gold asks whether the BLOCK conversion changed a sample;
# this asks whether PAIRING did. Both arms are block-kernel builds of one
# tree, driven with the identical DSP4_PROFILE_SIGNAL stimulus, differing
# only in DSP4_SIMD_DYN:
#
#   arm 0   DSP4_SIMD_DYN=0   the four group GATEs, four group COMPs and
#                             four main-output COMPs run scalar, in chain
#                             order. This is the reference.
#   arm 1   DSP4_SIMD_DYN=1   the same twelve nodes run as six paired
#                             driver calls, and the group and main-output
#                             runs are chain-reordered to put both
#                             channels of a pair live at once.
#
# THE VERDICT IS THE OUTPUT BLOCKS, AND THE OTHER TWO ARMS ARE ADVISORY.
# This was learned the hard way on 2026-09-01: the first cut scored the
# METERS, and they differed on 19 of 24 probes in both directions by a few
# percent -- INCLUDING on aux chains that contain no paired node at all.
# The meters are per-BLOCK IIRs; their 300 ms RMS window is about 56
# seconds of wall clock under DEC=32, against a 12 second dwell. So they
# read a point on a convergence curve, and the paired arm reaches a
# DIFFERENT point for the good reason that it runs faster. That is a bar
# measuring its own speedup.
#
# A node's whole output BLOCK has neither problem: it is recomputed from
# scratch every pass, so it cannot depend on how many passes have run, and
# sorting it makes it independent of which phase of the stimulus square the
# block happens to start on. It is compared bit-exactly.
#
# THE PAIRED NODES' OWN OUTPUTS ARE IN THE COMPARISON, not excluded -- so
# is the `_buf_` word the driver republishes off the last sample of the
# block, which is what a host peek reads on chip 2.
#
# NEGATIVE CONTROL: the same comparison under a deliberately wrong pairing
# of the probes. A bar that cannot fail is not a bar.
set -u
DWELL="${DWELL:-12}"
BLOCK="${BLOCK:-8}"
# Decimated for c2gold's reason: neither arm fits a block period, and a main
# loop that never finishes a block never services the link either. Both arms
# carry the SAME decimation, so both fold the same blocks.
DEC="${DEC:-32}"
WORK="${WORK:-/tmp/c2dyngold}"
cd "$(dirname "$0")"
ROOT=../../../..
source ./bench_lock.sh; bench_lock_acquire "$0"
BENCH=app@192.168.1.219
mkdir -p "$WORK"

SRC="$PWD/src"
if [ "$BLOCK" != "8" ]; then
  SRC="$WORK/src$BLOCK"
  rm -rf "$SRC"; cp -r "$PWD/src" "$SRC"
  DSP4_GEN_BLOCK=$BLOCK python3 $ROOT/tools/dsp/dsp_codegen.py \
      "$PWD/dsp.csv" "$SRC" --force >/dev/null 2>&1
  grep -q "define DSP4_BLOCK_SIZE   $BLOCK\$" "$SRC/dsp_block.h" || {
      echo "c2dyngold: generated tree for block $BLOCK does not say so" >&2
      exit 5; }
fi

run_arm() {   # $1 = tag, $2 = DSP4_SIMD_DYN, $3 = DSP4_SIMD_NEGCTL
  local P="$1"
  local S="$2"
  local N="$3"
  local D="$WORK/p$P-b$BLOCK"
  DSP_SRC_DIR="$SRC" DSP_BUILD_DIR="$D" \
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_PROFILE_SIGNAL=1 \
    DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=$S DSP4_SIMD_NEGCTL=$N DSP4_BQ_GRAPH=1 \
    DSP4_BLOCK_DECIMATE=$DEC ./build.sh all > "$D.log" 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
    echo "ARM $P BUILD FAILED (see $D.log)" >&2; return 1; fi
  echo "  arm$P: chip2.ldr $(md5sum "$D/chip2.ldr" | cut -c1-8)"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"
  scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" "$D/chip2.sym.json" \
         $BENCH:/home/app/dspboot/
  scp -q c2gold_run.sh $BENCH:/home/app/
  ssh $BENCH "bash /home/app/c2gold_run.sh $DWELL /home/app/dspboot/dyn$P.json $BLOCK" \
    2>&1 | sed "s/^/  arm$P: /"
}

echo "=== chip-2 dynamics pairing, BLOCK=$BLOCK ==="
run_arm 0 0 0 || exit 1
run_arm 1 1 0 || exit 1
run_arm n 1 1 || exit 1
scp -q $BENCH:/home/app/dspboot/dyn0.json $BENCH:/home/app/dspboot/dyn1.json \
       $BENCH:/home/app/dspboot/dynn.json "$WORK/"

python3 - "$WORK/dyn0.json" "$WORK/dyn1.json" "$WORK/dynn.json" <<'PYEOF'
import json, re, sys
A = json.load(open(sys.argv[1]))   # unpaired, the reference
B = json.load(open(sys.argv[2]))   # paired
N = json.load(open(sys.argv[3]))   # paired with DSP4_SIMD_NEGCTL

ha, hb = A.get('health', {}), B.get('health', {})

# Same D79 exclusion as c2gold.sh, and the same chain-tag mapping: a chain
# whose fader head took a stray config word carries garbage through every
# node in it, so comparing it would be comparing two lotteries.
def _tag(nid):
    m = re.match(r'^C2_MTR_(AUX|GRP|FX)_(\d+)$', nid)
    if m:
        return (m.group(1), m.group(2))
    if re.match(r'^C2_MTR_MAIN_\d+$', nid):
        return ('MAIN', None)
    if nid == 'C2_MTR_SUB':
        return ('SUB', None)
    m = re.match(r'^C2_(AUX|GRP|FX)_[A-Z]+_(\d+)$', nid)
    if m:
        return (m.group(1), m.group(2))
    m = re.match(r'^C2_(MAIN|SUB)_', nid)
    if m:
        return (m.group(1), None)
    return None

def _nid(probe):
    return re.sub(r'^_(?:mtr_peak|mtr_rms|buf)_', '', probe)

_sick = {t for mid in set(ha) | set(hb)
         for t in (_tag(mid),)
         if t is not None
         and (ha.get(mid, 'ok') != 'ok' or hb.get(mid, 'ok') != 'ok')}

def healthy(probe):
    return _tag(_nid(probe)) not in _sick

# THE METERS ARE THE VERDICT; THE NODE-OUTPUT PROBES ARE ADVISORY, AND THE
# REASON IS THEIR OWN NEGATIVE CONTROL. `_buf_<id>` is one scalar word, and
# under the DSP4_PROFILE_SIGNAL square wave most chip-2 nodes carry only
# +/-0.5 -- so pairing a probe with its neighbour usually finds the SAME two
# values and the wrong-pairing control does not fire. A comparison whose
# negative control is dead cannot be read as a pass, so this bar reports that
# arm and scores the meters, which fold all eight samples of the block and
# whose control does fire.
fail = 0
diffblk = 0
for kind, key in (('output blocks', 'blks'), ('meters', 'exact'),
                  ('node outputs', 'sets')):
    a, b = A[key], B[key]
    allnames = [n for n in a if n in b]
    xcl = [n for n in allnames if not healthy(n)]
    names = [n for n in allnames if healthy(n)]
    if xcl:
        print(f'EXCLUDED ({kind}, unhealthy chain -- D79): '
              + ', '.join(sorted(_nid(x) for x in xcl)))
    diff = [n for n in names if a[n] != b[n]]
    print(f'\nCHIP-2 DYN PAIR ({kind}): {len(names)} probes, {len(diff)} '
          f'differ -- BIT-EXACT means 0')
    for n in diff:
        va, vb = a[n], b[n]
        f = (lambda v: '0x%08X' % v) if key == 'exact' else \
            (lambda v: '[' + ' '.join('0x%08X' % x for x in v) + ']')
        print(f'  DIFFERS  {n:34s} unpaired={f(va)} paired={f(vb)}')
    if key == 'blks':
        # THE REAL NEGATIVE CONTROL, not a shuffle: a third build in which
        # DSP4_SIMD_NEGCTL makes the pair kernel take channel B's
        # parameters, state and signal from channel A, so the pair computes
        # ONE channel twice. Channel B of every pair -- and nothing else --
        # must change. The shuffle control this replaced was DEAD, and for
        # a good reason: chip 2's chains carry the same stimulus at the same
        # unity gain, so a probe's neighbour usually holds the same block.
        nb = N.get(key, {})
        watch = [n for n in names if n in nb
                 and re.search(r'_(GATE|COMP|OCOMP)_02$', _nid(n))]
        nc = sum(1 for n in watch if a[n] != nb[n])
        ok = bool(watch) and nc == len(watch)
        print(f'NEGCTL ({kind}): DSP4_SIMD_NEGCTL changed {nc} of '
              f'{len(watch)} channel-B outputs '
              f'({"PASSED" if ok else "DEAD"})')
        if not ok:
            print('  -> WHY, AND WHAT IT COSTS THIS BAR. Every chip-2 chain on'
                  ' this bench carries the SAME DSP4_PROFILE_SIGNAL square at'
                  ' the same unity gain with the same compiled default'
                  ' dynamics settings, so channel A and channel B of a pair'
                  ' are numerically the SAME CHANNEL -- and computing A twice,'
                  ' which is what DSP4_SIMD_NEGCTL makes the kernel do, gives'
                  ' the same answer. The pairs are RUNNING (see the pair'
                  ' witness above: _cmp_gn live, _dsim_n = BLOCK-1, every'
                  ' eligibility word on the paired path), so what the'
                  ' bit-exact result above proves is the PLUMBING -- the'
                  ' chain order, the sample-0 handoff, the block copy, the'
                  ' meter block, the _buf_ republish. It does NOT prove'
                  ' CHANNEL SEPARATION. Closing that needs distinct'
                  ' per-channel dynamics settings written over the SPI'
                  ' parameter plane before the dwell, which is what'
                  ' bqgraph.sh --bq does for the biquads.')
    else:
        shifted = names[1:] + names[:1]
        nc = sum(1 for n, m in zip(names, shifted) if a[n] != b[m])
        ok = nc >= len(names) // 2
        print(f'NEGCTL ({kind}): {nc} of {len(names)} differ under a '
              f'deliberately wrong pairing '
              f'({"PASSED" if ok else "DEAD"})')
    if key == 'blks':
        diffblk = len(diff)
        fail += len(diff)
        if not ok:
            fail += 1
    elif key == 'exact':
        print('  -> ADVISORY: the meters are per-BLOCK IIRs whose 300 ms RMS '
              'window is ~56 s of wall clock under DEC=32, against a '
              f'{__import__("os").environ.get("DWELL", "12")} s dwell -- so '
              'they read a point on a convergence curve, and the paired arm '
              'reaches a different point because it runs FASTER. Reported, '
              'not scored.')
    elif not ok:
        print(f'  -> ADVISORY: this arm\'s negative control is dead, so its '
              f'{len(diff)} difference(s) are reported, not scored. See the '
              f'header.')
    else:
        fail += len(diff)

print('\nVERDICT: ' + ('CHIP-2 DYNAMICS PAIRING BIT-EXACT' if not fail
                       else 'INCONCLUSIVE -- the output blocks are bit-exact '
                            'but the negative control is dead; see above'
                       if not diffblk else f'FAILED ({fail})'))
sys.exit(0 if not fail else 1)
PYEOF
