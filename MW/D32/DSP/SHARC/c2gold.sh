#!/bin/bash
# c2gold.sh — CHIP 2, PER-SAMPLE vs BLOCK-KERNEL, BIT-EXACT (finding D16).
#
# The bar chip 2 did not have. busgold.sh, goldnode.sh, bqgraph.sh and the
# vector bars are all chip-1 instruments -- "the one XOVER instance is on
# chip 2, where no vector bar runs" -- so a chip-2 conversion could otherwise
# only claim "it builds and the cycle count moved".
#
# WHAT IT COMPARES, AND WHY THAT IS A FAIR COMPARISON. Every converted chip-2
# node keeps its scalar `_buf_<id>` live and equal to the LAST SAMPLE OF THE
# BLOCK: the wrapper's body writes it on every call, so the last call leaves
# sample BLOCK-1 there; FADER_PAN's and the cascades' kernels store it
# explicitly for the same reason. The per-sample build's `_buf_<id>` is also
# the last sample it processed. So the two builds publish THE SAME SAMPLE
# POSITION in the same word, node for node, and comparing them is a direct
# bit-exactness test of the conversion -- not a proxy.
#
# THE INPUT IS THE SAME IN BOTH BUILDS BY CONSTRUCTION. DSP4_PROFILE_SIGNAL
# puts the same alternating +/-0.5 square into the INTERCHIP_RECV kernels of
# both, so neither build depends on the inter-chip fabric (which delivers
# nothing on this bench -- see sigprofile2.sh) and both see an identical,
# deterministic input sequence with the same phase at the block boundary.
#
# THE METERS ARE IN THE COMPARISON ON PURPOSE. Their agreement is the direct
# evidence for the third item of the D16 dispatch: chip 2's OUTPUT_TDM and
# bus-COMPRESSOR meters were decimated to one sample per block because their
# SOURCES were unconverted. If the sources are really converted, the block
# build's meter and the per-sample build's meter are folding the same eight
# samples and must agree bit for bit.
#
# NEGATIVE CONTROL: the same comparison run against a DELIBERATELY WRONG
# pairing (each node against its neighbour in the probe list). A bar that
# cannot fail is not a bar.
set -u
DWELL="${DWELL:-12}"
BLOCK="${BLOCK:-8}"
# DECIMATED, and it has to be. Neither arm fits a block period -- chip 1 is at
# 121% of the block-8 budget with 32 strips and chip 2 is further over than
# that -- and a main loop that never finishes a block never services the link
# either, so an undecimated run would read as a dead card rather than as a
# comparison. Both arms carry the SAME decimation, so the meters fold the same
# blocks in both and the comparison is unaffected: decimation changes how OFTEN
# a pass runs, never what one computes.
DEC="${DEC:-32}"
WORK="${WORK:-/tmp/c2gold}"
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
      echo "c2gold: generated tree for block $BLOCK does not say so" >&2; exit 5; }
fi

run_arm() {   # $1 = kernels (0|1) -> writes $WORK/arm$1.json on the card
  # Two statements, not one: bash expands every word of a `local` before it
  # performs any of its assignments, so `local K="$1" D=".../$K"` expands an
  # unset K -- and under `set -u` that is a hard error rather than an empty
  # path.
  local K="$1"
  local D="$WORK/k$K-b$BLOCK"
  DSP_SRC_DIR="$SRC" DSP_BUILD_DIR="$D" \
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=$K DSP4_PROFILE_SIGNAL=1 \
    DSP4_BLOCK_DECIMATE=$DEC ./build.sh all > "$D.log" 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
    echo "ARM $K BUILD FAILED (see $D.log)" >&2; return 1; fi
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"
  scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" "$D/chip2.sym.json" \
         $BENCH:/home/app/dspboot/
  scp -q c2gold_run.sh $BENCH:/home/app/
  ssh $BENCH "bash /home/app/c2gold_run.sh $DWELL /home/app/dspboot/arm$K.json" \
    2>&1 | sed "s/^/  arm$K: /"
}

echo "=== chip-2 gold, BLOCK=$BLOCK ==="
run_arm 0 || exit 1
run_arm 1 || exit 1
scp -q $BENCH:/home/app/dspboot/arm0.json $BENCH:/home/app/dspboot/arm1.json "$WORK/"
python3 - "$WORK/arm0.json" "$WORK/arm1.json" <<'PYEOF'
import json, re, sys
A = json.load(open(sys.argv[1]))
B = json.load(open(sys.argv[2]))

# ---- primary: the meters, compared EXACTLY --------------------------------
a, b = A['exact'], B['exact']
ha, hb = A.get('health', {}), B.get('health', {})

# A chain whose fader head was corrupted by its own boot's config (D79) is
# excluded from the comparison and NAMED. What it produces is a function of
# which word that boot dropped, not of the conversion, so comparing it would
# be comparing two lotteries.
#
# THE EXCLUSION NEVER FIRED UNTIL 2026-09-01, AND THE REASON IS THIS FUNCTION.
# It keyed the health map on `probe.split('_', 2)[2]`, which for
# `_mtr_peak_C2_MTR_AUX_01` is `peak_C2_MTR_AUX_01` -- a string the health map
# cannot contain, because that map is keyed by METER ID (`C2_MTR_AUX_01`). So
# `ha.get(mid, 'ok')` took its default on every probe and every chain was
# always "healthy". Session 18 is the first run where a chain WAS corrupt,
# and the bar reported a corrupt aux-01 chain -- both its meters and all six
# of its node-output probes -- as a conversion failure.
#
# It also did not cover the SET probes at all: those are named `_buf_<node>`,
# and a corrupt chain poisons every node in it, not just its meter. Both
# probe families are now mapped to the same CHAIN TAG and excluded together.
def _tag(nid):
    """(family, instance) for a chip-2 meter or node id -- the chain it is in."""
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

allnames = [n for n in a if n in b]
excluded = [n for n in allnames if not healthy(n)]
names = [n for n in allnames if healthy(n)]
if excluded:
    print('EXCLUDED (chain unhealthy in at least one arm -- stray config word, D79):')
    for n in sorted(set(_nid(x) for x in excluded)):
        print(f'  {n:22s} arm0={ha.get(n, "?")}  arm1={hb.get(n, "?")}')
diff = [n for n in names if a[n] != b[n]]
print(f'\nCHIP-2 GOLD (exact, block-latched meters): {len(names)} probes, '
      f'{len(diff)} differ -- BIT-EXACT means 0')
for n in diff:
    print(f'  DIFFERS  {n:34s} per-sample=0x{a[n]:08X} block=0x{b[n]:08X}')

# ---- NEGATIVE CONTROL -----------------------------------------------------
# Pair each probe with its NEIGHBOUR across the two arms. A comparison that
# cannot fail is not a bar, and this is the check that it can.
shifted = names[1:] + names[:1]
nc = sum(1 for n, m in zip(names, shifted) if a[n] != b[m])
ncok = nc >= len(names) // 2
print(f'NEGCTL: {nc} of {len(names)} differ under a deliberately wrong pairing '
      f'({"PASSED" if ncok else "FAILED -- the comparison cannot fail"})')

# ---- secondary: node output words, compared as SETS ------------------------
# _buf_<id> is the last sample PROCESSED, and only the block arm reads it at a
# defined position (BLOCK-1). So the test is membership: the block arm's word
# must be one the per-sample reference actually produces.
sa, sb = A['sets'], B['sets']
# Same D79 exclusion as the meters, and for the same reason: a chain whose
# fader head took a stray config word carries garbage through every node in
# it, so its node-output probes are two lotteries as surely as its meters are.
sxcl = [n for n in sa if n in sb and not healthy(n)]
snames = [n for n in sa if n in sb and healthy(n)]
if sxcl:
    print('EXCLUDED (set probes on an unhealthy chain): '
          + ', '.join(sorted(_nid(x) for x in sxcl)))
bad = [n for n in snames if not set(sb[n]) <= set(sa[n])]
print(f'SET PROBES: {len(snames)} node outputs, {len(bad)} produced a word the '
      f'per-sample reference never does')
for n in bad:
    print(f'  OUTSIDE  {n:34s} block={[hex(x) for x in sb[n]]} '
          f'per-sample={[hex(x) for x in sa[n]]}')

ok = not diff and ncok and not bad
print('VERDICT: ' + ('CHIP-2 BIT-EXACT' if ok else
                     f'FAILED (exact {len(diff)}, sets {len(bad)}, '
                     f'negctl {"ok" if ncok else "DEAD"})'))
sys.exit(0 if ok else 1)
PYEOF
