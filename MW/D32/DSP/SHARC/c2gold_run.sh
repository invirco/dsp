#!/bin/bash
# c2gold_run.sh — bench half of c2gold.sh. Boots the staged image, configures
# BOTH chips (chip 2's main loop is gated on CONFIG_COMMIT: without one its
# node graph never runs at all), lets the graph settle, and dumps every probe
# word to JSON.
set -u
DWELL="$1"; OUT="$2"; BLK="${3:-8}"
cd /home/app/dspboot

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
flock "$BENCH_LOCK_FD"
printf 'pid=%s script=c2gold_run.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
trap 'rm -f "$BENCH_LOCKFILE.info"' EXIT

sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1

for attempt in 1 2 3; do
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    ID=$(python3 dsp4_diag.py --chip 2 2>&1|grep CHIP_ID|awk '{print $2}')
    [ "$ID" = "2" ] && break
  done
  GOT=0
  for c in 1 2 3; do
    python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 2
    python3 dsp4_config.py --product d24 --chip 2 --cs-gpio 24 --rdy-gpio 12 >/dev/null 2>&1
    sleep 3
    G1=0; G2=0
    for t in 1 2 3 4 5 6; do
      O=$(python3 dsp4_diag.py --chip 1 2>&1)
      echo "$O" | grep -q "MAGIC          0xD5B40001" && {
        S=$(echo "$O"|grep BOOT_STAGE|awk '{print $2}')
        [ -n "$S" ] && [ "$S" -ge 6 ] 2>/dev/null && G1=1; }
      O2=$(python3 dsp4_diag.py --chip 2 2>&1)
      echo "$O2" | grep -q "MAGIC          0xD5B40001" && {
        S2=$(echo "$O2"|grep BOOT_STAGE|awk '{print $2}')
        [ -n "$S2" ] && [ "$S2" -ge 6 ] 2>/dev/null && G2=1; }
      [ "$G1" = "1" ] && [ "$G2" = "1" ] && { GOT=1; break; }
      sleep 1
    done
    [ "$GOT" = "1" ] && break
  done
  [ "$GOT" = "0" ] && { echo "(attempt $attempt: chips not both RUNNING)"; continue; }
  sleep "$DWELL"
  python3 - "$OUT" "$BLK" <<'PYEOF'
import json, sys
out = sys.argv[1]
BLOCK = int(sys.argv[2]) if len(sys.argv) > 2 else 8
sys.argv = ['p']
import dsp4_diag as D

# CALIBRATES the answer phase (D74). A register that reads 0 is not a
# measurement until this has run, and when the link cannot be phased this
# RAISES rather than handing back zeros -- so it is retried here and an
# exhausted retry fails the capture, rather than escaping as a traceback that
# looks like a result (which cost one point of a ladder on 2026-09-01).
dg = None
for _ in range(4):
    try:
        dg = D.DiagLink(D.SpiLink('0.0', 1000000, 24, rdy_gpio=12))
        dg.resync()
        break
    except (IOError, OSError) as e:
        dg = None
if dg is None:
    print('UNPHASED: the parameter link would not phase to chip 2')
    sys.exit(3)

def sane():
    try:
        return (dg.read(0xE000) == 0xD5B40001 and dg.read(0xE001) == 2
                and dg.read(0xE005) != 0)
    except IOError:
        return False

def peek(a):
    for _ in range(12):
        if not sane():
            continue
        try:
            v = dg.peek(a)
        except IOError:
            continue
        if sane():
            return v
    return None

sym = json.load(open('chip2.sym.json'))
# THE METERS ARE THE BIT-EXACT COMPARISON, and the reason is read timing.
#
# `_buf_<id>` holds the LAST SAMPLE PROCESSED. In the block-kernel arm that is
# always sample BLOCK-1, because the kernel finishes the whole block before it
# returns. In the PER-SAMPLE arm it is whatever sample the chain happened to be
# on when the host's SPI read landed -- and the stimulus alternates sign every
# sample, so a direct comparison of that word is a coin toss on read timing and
# would tell us nothing about the conversion.
#
# The meters do not have that problem. Each folds peak and true RMS over a
# WHOLE BLOCK and latches the result at block rate, so with a constant-
# amplitude stimulus its steady-state value is exact, deterministic, and
# identical in both builds if and only if both builds computed the same eight
# samples. That is precisely the claim under test -- and it is also the direct
# evidence for the third item of the D16 dispatch, since these meters were
# decimated to one sample per block while their sources were unconverted.
#
# The `_buf_` probes below are kept as a SECONDARY check, compared as SETS: the
# per-sample arm is sampled repeatedly and the block arm's word must be one the
# reference actually produces. That covers the two chains with no meter on them
# (monitor, and the stereo/codec outputs).
BUFS = [
    'C2_SNK_IN_01', 'C2_CODEC_AUX_IN', 'C2_PI_IN', 'C2_USB_IN',
    'C2_AUX_FDR_01', 'C2_AUX_EQ_01', 'C2_AUX_GEQ_01', 'C2_AUX_AFB_01',
    'C2_AUX_LIM_01', 'C2_AUX_DLY_01', 'C2_AUX_OUT_01',
    'C2_AUX_FDR_07', 'C2_AUX_GEQ_07', 'C2_AUX_OUT_07',
    'C2_GRP_FDR_01', 'C2_GRP_EQ_01', 'C2_GRP_GEQ_01', 'C2_GRP_GATE_01',
    'C2_GRP_COMP_01',
    # The B CHANNEL of each chip-2 dynamics pair. Under DSP4_SIMD_NEGCTL the
    # pair kernel gives channel B channel A's parameters, state and signal,
    # so B -- and only B -- must change. Without these in the probe list that
    # negative control has nothing to fire on (c2dyngold.sh, 2026-09-01).
    'C2_GRP_GATE_02', 'C2_GRP_COMP_02', 'C2_MAIN_OCOMP_02',
    'C2_AUX_LIM_02', 'C2_AUX_AFB_02', 'C2_AUX_OUT_02', 'C2_MAIN_OLIM_02',
    'C2_SUB_FDR', 'C2_SUB_EQ', 'C2_SUB_COMP', 'C2_SUB_LIM', 'C2_SUB_DLY',
    'C2_SUB_OUT',
    'C2_MIX_MAIN_L', 'C2_MIX_MAIN_R', 'C2_MAIN_FDR', 'C2_MAIN_GEQ',
    'C2_MAIN_COMP', 'C2_MAIN_LIM', 'C2_MAIN_DLY', 'C2_MAIN_XOVER',
    'C2_MAIN_OEQ_01', 'C2_MAIN_OCOMP_01', 'C2_MAIN_OLIM_01', 'C2_MAIN_OUT_01',
    'C2_FX_ENG_01', 'C2_FX_FDR_01',
    'C2_MON', 'C2_MON_DLY', 'C2_MON_OUT',
    'C2_MAIN_ST_OUT', 'C2_CODEC_AUX_OUT',
]
METERS = ['C2_MTR_AUX_01', 'C2_MTR_AUX_04', 'C2_MTR_AUX_07', 'C2_MTR_AUX_12',
          'C2_MTR_GRP_01', 'C2_MTR_GRP_04',
          'C2_MTR_MAIN_01', 'C2_MTR_MAIN_02', 'C2_MTR_MAIN_03',
          'C2_MTR_MAIN_04', 'C2_MTR_SUB',
          'C2_MTR_FX_01', 'C2_MTR_FX_06']

# CHAIN HEALTH, WITNESSED PER CHAIN AND IN BOTH ARMS.
#
# Configuring chip 2 lands a stray word in a node's parameter state, the same
# way configuring chip 1 does -- "roughly one boot in three lands the
# CFG_COMMIT header word in _gain_coeff_C1_GAIN_01", which is what gainfix.py
# exists to repair. Nobody had seen it on chip 2 before 2026-09-01 because
# nobody had ever configured chip 2. Caught here on the first run of this bar:
# _fdr_level_C2_AUX_FDR_01 read 0xE0FE0000 -- a DIAG HEADER WORD, not a float
# -- and _fdr_gq_C2_AUX_FDR_01 read 0xFFFFFFFF, so that whole aux chain
# carried zero while its neighbours carried the stimulus perfectly.
#
# A chain in that state must not be COMPARED, because what it produces is a
# function of which word the boot happened to drop, not of the conversion. So
# each chain's fader head is witnessed and the unhealthy ones are named and
# excluded rather than quietly averaged in.
FDR_OF = {
    'C2_MTR_AUX_01': 'C2_AUX_FDR_01', 'C2_MTR_AUX_04': 'C2_AUX_FDR_04',
    'C2_MTR_AUX_07': 'C2_AUX_FDR_07', 'C2_MTR_AUX_12': 'C2_AUX_FDR_12',
    'C2_MTR_GRP_01': 'C2_GRP_FDR_01', 'C2_MTR_GRP_04': 'C2_GRP_FDR_04',
    'C2_MTR_MAIN_01': 'C2_MAIN_FDR', 'C2_MTR_MAIN_02': 'C2_MAIN_FDR',
    'C2_MTR_MAIN_03': 'C2_MAIN_FDR', 'C2_MTR_MAIN_04': 'C2_MAIN_FDR',
    'C2_MTR_SUB': 'C2_SUB_FDR',
    'C2_MTR_FX_01': 'C2_FX_FDR_01', 'C2_MTR_FX_06': 'C2_FX_FDR_06',
}
UNITY_F32 = 0x3F800000
UNITY_Q428 = 0x10000000
health = {}
for mid, fid in FDR_OF.items():
    lv = sym.get('_fdr_level_' + fid)
    gq = sym.get('_fdr_gq_' + fid)
    if lv is None or gq is None:
        health[mid] = 'absent'
        continue
    a = peek(lv)
    b = peek(gq)
    if a is None or b is None:
        health[mid] = 'unreadable'
    elif a != UNITY_F32 or b != UNITY_Q428:
        health[mid] = 'level=0x%08X gq=0x%08X' % (a, b)
    else:
        health[mid] = 'ok'

res = {}      # exact probes: meters
sets = {}     # set probes: node output words, sampled repeatedly
missing = []
for mid in METERS:
    for pfx in ('_mtr_peak_', '_mtr_rms_'):
        nm = pfx + mid
        if nm not in sym:
            missing.append(nm); continue
        v = peek(sym[nm])
        if v is None:
            print('UNREADABLE ' + nm); sys.exit(2)
        res[nm] = v
for nid in BUFS:
    nm = '_buf_' + nid
    if nm not in sym:
        missing.append(nm); continue
    seen = set()
    for _ in range(6):
        v = peek(sym[nm])
        if v is None:
            print('UNREADABLE ' + nm); sys.exit(2)
        seen.add(v)
    sets[nm] = sorted(seen)
# THE OUTPUT BLOCK, SORTED -- phase-invariant and convergence-free.
#
# `_buf_<id>` is one word and the stimulus is a +/-0.5 square, so a probe of
# it catches whichever phase the graph happened to be on; and the METERS are
# per-BLOCK IIRs whose 300 ms RMS window is ~56 s of wall clock under DEC=32,
# so a 12 s dwell reads a point on a convergence curve rather than a settled
# value. Neither is a sound basis for comparing two builds that run at
# DIFFERENT SPEEDS.
#
# The node's whole output block is both. Sorting it makes it independent of
# which sample the block starts on, and a block is recomputed from scratch
# every pass, so nothing about it depends on how many passes have run.
blks = {}
for nid in BUFS:
    nm = '_blk_' + nid
    if nm not in sym:
        missing.append(nm); continue
    vals = []
    for k in range(BLOCK):
        v = peek(sym[nm] + k)
        if v is None:
            print('UNREADABLE ' + nm); sys.exit(2)
        vals.append(v)
    blks[nm] = sorted(vals)
# PAIR ELIGIBILITY, WITNESSED. A chip-2 dynamics pair falls back to its two
# scalar node calls unless both channels are ON and neither has its sidechain
# filter engaged -- and a bar comparing a paired build against an unpaired one
# is worthless if the "paired" build quietly took the fallback. c2dyngold.sh
# hit exactly that on 2026-09-01: 47 output blocks bit-exact AND the
# DSP4_SIMD_NEGCTL control changing nothing, which is what a fallback looks
# like from the outside.
witness = {}
for w in ('_gate_on_C2_GRP_GATE_01', '_gate_on_C2_GRP_GATE_02',
          '_gate_filter_on_C2_GRP_GATE_01', '_gate_filter_on_C2_GRP_GATE_02',
          '_comp_on_C2_GRP_COMP_01', '_comp_on_C2_GRP_COMP_02',
          '_comp_on_C2_MAIN_OCOMP_01', '_comp_on_C2_MAIN_OCOMP_02',
          '_lim_on_C2_AUX_LIM_01', '_lim_on_C2_AUX_LIM_02',
          '_lim_on_C2_MAIN_OLIM_01', '_lim_on_C2_MAIN_OLIM_02',
          '_cmp_gn', '_dsim_n'):
    if w in sym:
        witness[w] = peek(sym[w])
json.dump({'exact': res, 'sets': sets, 'blks': blks, 'health': health,
           'witness': witness}, open(out, 'w'))
print('  pair witness: ' + ' '.join(
    f'{k.replace("_C2_", " ")}=0x%08X' % v
    for k, v in witness.items() if v is not None))
bad = {k: v for k, v in health.items() if v != 'ok'}
print(f'{len(res)} exact probes (meters) + {len(sets)} set probes captured'
      + (f', {len(missing)} absent from the map: {missing}' if missing else ''))
print(f'  chain health: {len(health) - len(bad)} of {len(health)} ok'
      + (f'; NOT ok: {bad}' if bad else ''))
PYEOF
  RC=$?
  [ "$RC" = "0" ] && exit 0
  echo "(attempt $attempt: capture failed rc=$RC)"
done
echo "no clean capture in 3 attempts"
exit 4
