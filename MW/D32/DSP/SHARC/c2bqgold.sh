#!/bin/bash
# c2bqgold.sh — is chip 2's BIQUAD PAIRING bit-exact against the same graph
# with the cascades scalar?
#
# c2dyngold.sh's sibling, one class earlier in the chain. Three arms, one
# tree, the identical DSP4_PROFILE_SIGNAL stimulus, differing only in two
# preprocessor symbols:
#
#   arm 0   DSP4_C2_BQ_GRAPH=0     the 24 EQ/GEQ/AFB/OEQ cascades that pair
#                                  run as scalar nodes in chain order, the
#                                  dynamics pairs untouched. THIS ARM IS
#                                  BYTE-IDENTICAL TO THE PREVIOUS COMMIT'S
#                                  BUILD -- checked, not assumed -- so it is
#                                  the configuration 240,681 cycles/block
#                                  was measured on.
#   arm 1   DSP4_C2_BQ_GRAPH=1     the same 24 cascades run as 24 paired
#                                  driver calls on _bq_fx_cascade_simd, with
#                                  the pair owning the interleaved
#                                  coefficient and state arrays.
#   arm n   DSP4_C2_BQ_NEGCTL=1    channel B's coefficients are gathered as
#                                  ZERO at engage. Every channel-B cascade
#                                  output must move and NO channel-A one may.
#   arm r   DSP4_C2_BQ_NOLATCH=1   the ROUND-TRIP arm: the state is scattered
#                                  back and the latch dropped on EVERY block,
#                                  so the engage/disengage bookkeeping runs
#                                  six thousand times a second instead of once
#                                  per coefficient swap. Must be bit-exact
#                                  against BOTH other arms.
#
# WHY THE ROUND-TRIP ARM EXISTS. The latch is only taken down by a
# coefficient swap or a crossfade, and nothing on this bench writes chip 2's
# filter coefficients -- so in arms 0/1/n the gather runs ONCE, at the first
# block, and the scatter never runs at all. That leaves the half of the
# design that a real EQ change exercises completely untested. Running the
# round trip every block tests it at block rate and needs no SPI plane: a
# gather that maps the interleave wrongly in EITHER direction cannot survive
# being run and undone 6,000 times a second and still be bit-exact.
#
# WHY THAT CONTROL AND NOT CHIP 1'S. DSP4_BQ_NEGCTL gives strip B strip A's
# coefficients, so the pair computes one channel twice. On chip 2 that is
# DEAD: nothing configures chip 2's filters, so every cascade runs the same
# .var bypass initialisers and A and B are numerically the same filter --
# the gap the 2026-09-01 record named on the dynamics pairs and could not
# close. Zeroing ONE channel's coefficients closes it without needing
# distinct per-channel settings over the SPI plane: it can only be produced
# by a kernel that keeps the two channels' coefficients apart, and it
# cannot be masked by the two channels carrying the same signal.
#
# THE VERDICT IS THE OUTPUT BLOCKS, for c2dyngold's reason: `_buf_` is one
# word of a +/-0.5 square (read timing), and the meters are per-block IIRs
# whose 300 ms window is ~56 s of wall clock under DEC=32 against a 12 s
# dwell, so they read a point on a convergence curve and the faster arm
# reaches a different point. A node's output BLOCK, sorted, is neither.
#
# THE LATCH IS WITNESSED. A pair that never engaged ran its two scalar node
# bodies all along, which from the outside is indistinguishable from a
# bit-exact result -- the same trap c2dyngold hit as a silent fallback. Each
# arm prints _bqi_lat_* and the run FAILS if the paired arm's latches are
# not up.
set -u
DWELL="${DWELL:-12}"
BLOCK="${BLOCK:-8}"
# Decimated for c2gold's reason: neither arm fits a block period, and a main
# loop that never finishes a block never services the link either. Both arms
# carry the SAME decimation, so both fold the same blocks.
DEC="${DEC:-32}"
WORK="${WORK:-/tmp/c2bqgold}"
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
      echo "c2bqgold: generated tree for block $BLOCK does not say so" >&2
      exit 5; }
fi

run_arm() {   # $1 = tag, $2 = C2_BQ_GRAPH, $3 = C2_BQ_NEGCTL, $4 = C2_BQ_NOLATCH
  local P="$1" G="$2" N="$3" L="${4:-0}"
  local D="$WORK/p$P-b$BLOCK"
  DSP_SRC_DIR="$SRC" DSP_BUILD_DIR="$D" \
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_PROFILE_SIGNAL=1 \
    DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1 DSP4_BQ_GRAPH=1 \
    DSP4_C2_BQ_GRAPH=$G DSP4_C2_BQ_NEGCTL=$N DSP4_C2_BQ_NOLATCH=$L \
    DSP4_BLOCK_DECIMATE=$DEC ./build.sh all > "$D.log" 2>&1
  if [ "$(grep -ciE '\[Error|Build FAILED' "$D.log")" -ne 0 ]; then
    echo "ARM $P BUILD FAILED (see $D.log)" >&2; return 1; fi
  echo "  arm$P: chip1.ldr $(md5sum "$D/chip1.ldr" | cut -c1-8)" \
       "chip2.ldr $(md5sum "$D/chip2.ldr" | cut -c1-8)"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip1.map.xml" > "$D/chip1.sym.json"
  python3 $ROOT/tools/dsp/map_syms.py "$D/chip2.map.xml" > "$D/chip2.sym.json"
  scp -q "$D/chip1.ldr" "$D/chip2.ldr" "$D/chip1.sym.json" "$D/chip2.sym.json" \
         $BENCH:/home/app/dspboot/
  scp -q c2gold_run.sh $BENCH:/home/app/
  ssh $BENCH "bash /home/app/c2gold_run.sh $DWELL /home/app/dspboot/bq$P.json $BLOCK" \
    2>&1 | sed "s/^/  arm$P: /"
}

echo "=== chip-2 biquad pairing (native interleave), BLOCK=$BLOCK ==="
run_arm 0 0 0 0 || exit 1
run_arm 1 1 0 0 || exit 1
run_arm n 1 1 0 || exit 1
run_arm r 1 0 1 || exit 1
scp -q $BENCH:/home/app/dspboot/bq0.json $BENCH:/home/app/dspboot/bq1.json \
       $BENCH:/home/app/dspboot/bqn.json $BENCH:/home/app/dspboot/bqr.json \
       "$WORK/"

python3 - "$WORK/bq0.json" "$WORK/bq1.json" "$WORK/bqn.json" "$WORK/bqr.json" <<'PYEOF'
import json, re, sys
A = json.load(open(sys.argv[1]))   # cascades scalar, the reference
B = json.load(open(sys.argv[2]))   # cascades paired
N = json.load(open(sys.argv[3]))   # paired with DSP4_C2_BQ_NEGCTL
R = json.load(open(sys.argv[4]))   # paired with DSP4_C2_BQ_NOLATCH

ha, hb = A.get('health', {}), B.get('health', {})

# The D79/D81 exclusion, unchanged: a chain whose fader head took a stray
# config word carries garbage through every node in it, so comparing it
# would be comparing two lotteries.
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
    return re.sub(r'^_(?:mtr_peak|mtr_rms|buf|blk)_', '', probe)

_sick = {t for mid in set(ha) | set(hb)
         for t in (_tag(mid),)
         if t is not None
         and (ha.get(mid, 'ok') != 'ok' or hb.get(mid, 'ok') != 'ok')}

def healthy(probe):
    return _tag(_nid(probe)) not in _sick

# THE LATCH WITNESS, BEFORE ANYTHING IS COMPARED. A paired arm whose pairs
# never engaged took the scalar fallback on every block, and that is
# bit-exact for a reason that has nothing to do with this kernel.
wb = {k: v for k, v in B.get('witness', {}).items()
      if k.startswith('_bqi_lat_')}
wa = {k: v for k, v in A.get('witness', {}).items()
      if k.startswith('_bqi_lat_')}
print('LATCH WITNESS (paired arm): '
      + (' '.join(f'{k[9:]}={v}' for k, v in sorted(wb.items()))
         if wb else 'NONE FOUND'))
latch_ok = bool(wb) and all(v == 1 for v in wb.values())
if wa:
    print(f'  control arm carries {len(wa)} latch symbol(s) -- it should '
          f'carry none; the arms are not what they claim to be')
if not latch_ok:
    print('  -> THE PAIRED ARM DID NOT ENGAGE ITS PAIRS. Everything below is '
          'a comparison of the scalar path against itself.')

fail = 0 if latch_ok else 1
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
    print(f'\nCHIP-2 BQ PAIR ({kind}): {len(names)} probes, {len(diff)} '
          f'differ -- BIT-EXACT means 0')
    for n in diff:
        va, vb = a[n], b[n]
        f = (lambda v: '0x%08X' % v) if key == 'exact' else \
            (lambda v: '[' + ' '.join('0x%08X' % x for x in v) + ']')
        print(f'  DIFFERS  {n:34s} scalar={f(va)} paired={f(vb)}')
    if key == 'blks':
        # THE NEGATIVE CONTROL. DSP4_C2_BQ_NEGCTL gathers channel B's
        # coefficients as ZERO, so B's cascade is a dead filter and A's is
        # untouched. The criterion is two-sided and both halves matter:
        # every channel-B cascade must move (the kernel reads B's own
        # coefficients) and no channel-A cascade may (it does not read
        # B's). A one-sided "something moved" would also pass for a kernel
        # that simply broke.
        #
        # THE "MUST NOT MOVE" SET IS THE CHANNEL-A CASCADES ON INDEPENDENT
        # CHAINS, AND THAT EXCLUDES THE MAIN-OUTPUT ONES. A MOUT chain
        # reads C2_MAIN_XOVER, which is fed by the main mix, which sums
        # every aux and group output on the chip -- so C2_MAIN_OEQ_01 is
        # DOWNSTREAM of every channel B and must move whatever the kernel
        # does. Requiring it to hold still is requiring the graph not to be
        # a graph. The aux and group cascades read their own chain's fader
        # and are the honest test of channel separation.
        #
        # This was learned by running the bar: its first cut scored
        # C2_MAIN_OEQ_01 in `keep`, the bar FAILED, and the cause was the
        # criterion rather than the kernel -- C2_MAIN_OEQ_01 moved because
        # its INPUT moved. The five aux and group channel-A cascades did
        # not move in that same run.
        nb = N.get(key, {})
        BQ_B = re.compile(r'_(EQ|GEQ|AFB|OEQ)_02$')
        BQ_A = re.compile(r'^C2_(AUX|GRP)_(EQ|GEQ|AFB)_01$')
        watch = [n for n in names if n in nb and BQ_B.search(_nid(n))]
        keep = [n for n in names if n in nb and BQ_A.match(_nid(n))]
        hit = [n for n in watch if a[n] != nb[n]]
        leak = [n for n in keep if a[n] != nb[n]]
        moved = [n for n in a if n in nb and a[n] != nb[n]]
        ok = bool(hit) and len(hit) == len(watch) and not leak
        print(f'NEGCTL ({kind}): DSP4_C2_BQ_NEGCTL moved {len(hit)} of '
              f'{len(watch)} channel-B cascade outputs and {len(leak)} of '
              f'{len(keep)} independent-chain channel-A ones (A must be 0), '
              f'{len(moved)} probes in all '
              f'({"PASSED" if ok else "FAILED"})')
        for n in sorted(moved):
            print(f'    moved: {_nid(n)}')
        if leak:
            print('  -> A CHANNEL-A CASCADE MOVED when only channel B\'s '
                  'coefficients were touched: the two channels are NOT '
                  'independent in the paired kernel.')
        diffblk = len(diff)
        fail += len(diff)
        if not ok:
            fail += 1
    elif key == 'exact':
        print('  -> ADVISORY: the meters are per-BLOCK IIRs whose 300 ms RMS '
              'window is ~56 s of wall clock under DEC=32 against a short '
              'dwell, so they read a point on a convergence curve and the '
              'paired arm reaches a different point because it runs FASTER. '
              'Reported, not scored.')
    else:
        print('  -> ADVISORY: `_buf_` is one word of a +/-0.5 square, so it '
              'is read-timing dependent. Reported, not scored.')

# THE ROUND TRIP. Arm r runs the engage/disengage bookkeeping every block
# instead of once, so it must agree with the scalar arm AND with the latched
# arm. This is the only coverage the gather and the scatter get: nothing on
# this bench writes chip 2's filter coefficients, so in the other three arms
# the gather runs once and the scatter never runs at all.
for lbl, ref in (('scalar', A), ('latched', B)):
    a, r = ref['blks'], R['blks']
    names = [n for n in a if n in r and healthy(n)]
    diff = [n for n in names if a[n] != r[n]]
    print(f'\nROUND TRIP vs {lbl} (output blocks): {len(names)} probes, '
          f'{len(diff)} differ -- BIT-EXACT means 0')
    for n in diff:
        print(f'  DIFFERS  {n:34s} {lbl}='
              + '[' + ' '.join('0x%08X' % x for x in a[n]) + '] roundtrip='
              + '[' + ' '.join('0x%08X' % x for x in r[n]) + ']')
    fail += len(diff)

print('\nVERDICT: ' + ('CHIP-2 BIQUAD PAIRING BIT-EXACT' if not fail
                       else f'FAILED ({fail})'))
sys.exit(0 if not fail else 1)
PYEOF
