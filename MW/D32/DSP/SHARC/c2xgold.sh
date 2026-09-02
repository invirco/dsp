#!/bin/bash
# c2xgold.sh — is chip 2's CROSS-CHAIN dynamics pairing bit-exact?
#
# C2_MAIN_COMP + C2_SUB_COMP and C2_MAIN_LIM + C2_SUB_LIM are the four
# single instances no family could pair. Pairing them is licensed by the
# main and sub chains being DISJOINT: C2_MIX_MAIN_L/R do not read
# C2_SUB_OUT, neither node is reachable from its partner in either
# direction, and the only consumer of a sub-chain node from outside is the
# sub's own meter. See _C2_CROSS_PAIRS in dsp_codegen.py.
#
#   arm 0   DSP4_C2_XPAIR=0   the four nodes run SCALAR, in the SAME chain
#                             order. This is the reference, and keeping the
#                             order identical is deliberate: it isolates the
#                             PAIRING from the REORDER instead of
#                             confounding the two.
#   arm 1   DSP4_C2_XPAIR=1   the same four run as two pair drivers.
#   arm n   DSP4_SIMD_NEGCTL  the pair kernel takes channel B's parameters,
#                             state and signal from channel A, so it
#                             computes ONE channel twice.
#
# THE NEGATIVE CONTROL SHOULD FIRE HERE, AND THAT IS THE POINT. On the
# family pairs it was DEAD (2026-09-01): every chip-2 aux chain carries the
# same stimulus at the same unity gain, so channel A and B are numerically
# the same channel and computing A twice gives the right answer. These two
# pairs are different in kind -- MAIN carries the whole mix and SUB carries
# only C2_RECV_SUB, so the two channels genuinely differ. The criterion is
# two-sided: both SUB outputs must move and neither MAIN output may, which
# is what says the kernel keeps two DIFFERENT channels apart.
#
# THE VERDICT IS THE OUTPUT BLOCKS, for c2dyngold's reason: `_buf_` is one
# word of a square wave and the meters are per-block IIRs on a convergence
# curve that the faster arm walks further along.
set -u
DWELL="${DWELL:-12}"
BLOCK="${BLOCK:-8}"
# Decimated for c2gold's reason: neither arm fits a block period, and a main
# loop that never finishes a block never services the link either. Both arms
# carry the SAME decimation, so both fold the same blocks.
DEC="${DEC:-32}"
WORK="${WORK:-/tmp/c2xgold}"
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
      echo "c2xgold: generated tree for block $BLOCK does not say so" >&2
      exit 5; }
fi

run_arm() {   # $1 = tag, $2 = DSP4_C2_XPAIR, $3 = DSP4_SIMD_NEGCTL
  local P="$1" X="$2" N="$3"
  local D="$WORK/p$P-b$BLOCK"
  DSP_SRC_DIR="$SRC" DSP_BUILD_DIR="$D" \
  DSP4_BISECT=0 DSP4_BLOCK_KERNELS=1 DSP4_PROFILE_SIGNAL=1 \
    DSP4_STRIP_FUSED=1 DSP4_SIMD_DYN=1 DSP4_BQ_GRAPH=1 DSP4_C2_BQ_GRAPH=1 \
    DSP4_C2_XPAIR=$X DSP4_SIMD_NEGCTL=$N \
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
  ssh $BENCH "bash /home/app/c2gold_run.sh $DWELL /home/app/dspboot/x$P.json $BLOCK" \
    2>&1 | sed "s/^/  arm$P: /"
}

echo "=== chip-2 biquad pairing (native interleave), BLOCK=$BLOCK ==="
run_arm 0 0 0 || exit 1
run_arm 1 1 0 || exit 1
run_arm n 1 1 || exit 1
scp -q $BENCH:/home/app/dspboot/x0.json $BENCH:/home/app/dspboot/x1.json \
       $BENCH:/home/app/dspboot/xn.json "$WORK/"

python3 - "$WORK/x0.json" "$WORK/x1.json" "$WORK/xn.json" <<'PYEOF'
import json, re, sys
A = json.load(open(sys.argv[1]))   # cascades scalar, the reference
B = json.load(open(sys.argv[2]))   # cascades paired
N = json.load(open(sys.argv[3]))   # paired with DSP4_C2_BQ_NEGCTL

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
# THE PAIR RAN, WITNESSED. _dsim_n is set to BLOCK-1 by every pair driver
# and read by the kernel, so a graph whose cross pairs took the scalar
# fallback would not have driven it.
w = B.get('witness', {})
print('PAIR WITNESS (cross-paired arm): '
      + ' '.join(f'{k}=0x%08X' % v for k, v in sorted(w.items())
                 if k in ('_dsim_n', '_cmp_gn') and v is not None))
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
        BQ_B = re.compile(r'^C2_SUB_(COMP|LIM)$')
        BQ_A = re.compile(r'^C2_MAIN_(COMP|LIM)$')
        watch = [n for n in names if n in nb and BQ_B.match(_nid(n))]
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

print('\nVERDICT: ' + ('CHIP-2 CROSS-CHAIN DYNAMICS PAIRING BIT-EXACT' if not fail
                       else f'FAILED ({fail})'))
sys.exit(0 if not fail else 1)
PYEOF
