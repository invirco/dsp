#!/bin/bash
# sigprofile2_run.sh — bench half of sigprofile2.sh (CHIP 2 class profile).
#
# sigprofile_run.sh's twin. Same boot/config ladder, same bench lock, same
# "witness before the number" rule -- but the number comes off CHIP 2 and the
# witness is two-sided (see sigprofile2.sh's header).
set -u
PT="$1"; PP="$2"; DWELL="$3"
cd /home/app/dspboot

BENCH_LOCKFILE=/home/app/dspboot/.bench.lock
exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
if ! flock -n "$BENCH_LOCK_FD"; then
  holder="$(cat "$BENCH_LOCKFILE.info" 2>/dev/null)"
  echo ">>> BENCH LOCKED: waiting for the card ($BENCH_LOCKFILE)." >&2
  [ -n "$holder" ] && echo ">>> held by: $holder" >&2
  flock "$BENCH_LOCK_FD"
fi
printf 'pid=%s script=sigprofile2_run.sh started=%s\n' "$$" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
trap 'rm -f "$BENCH_LOCKFILE.info"' EXIT

sudo systemctl stop matrix-app >/dev/null 2>&1
sudo pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0 >/dev/null 2>&1

boot_and_config() {
  for t in 1 2 3; do
    python3 dsp4_boot.py --dir . >/dev/null 2>&1; sleep 5
    ID=$(python3 dsp4_diag.py --chip 2 2>&1|grep CHIP_ID|awk '{print $2}'); [ "$ID" = "2" ] && break
  done
  # CHIP 2 IS CONFIGURED TOO, AND THAT IS THE POINT.
  #
  # Every session before this one configured chip 1 only ("chip 2 is never
  # configured; BOOT_STAGE 5 is its pass mark"). BOOT_STAGE 5 is WAITCFG: the
  # main loop is gated on _boot_config_received, which CONFIG_COMMIT sets, so
  # a chip 2 that is never configured NEVER ENTERS ITS BLOCK LOOP and its node
  # graph has never run on this bench at all. That is why there was no chip-2
  # cost record to have -- not an oversight in the measurement, an absence of
  # anything to measure. Chip 2 gets its own CONFIG_COMMIT here and its pass
  # mark becomes STAGE 7 (RUNNING), the same as chip 1's.
  GOT=0
  for c in 1 2 3; do
    python3 dsp4_config.py --product d24 --chip 1 >/dev/null 2>&1; sleep 2
    python3 dsp4_config.py --product d24 --chip 2 --cs-gpio 24 --rdy-gpio 12 \
        >/dev/null 2>&1; sleep 3
    G1=0; G2=0
    for t in 1 2 3 4 5 6; do
      O=$(python3 dsp4_diag.py --chip 1 2>&1)
      if echo "$O" | grep -q "MAGIC          0xD5B40001"; then
        S=$(echo "$O"|grep BOOT_STAGE|awk '{print $2}'); T=$(echo "$O"|grep TICKS|awk '{print $2}')
        if [ -n "$S" ] && [ "$T" != "0" ] && [ "$S" -ge 6 ] 2>/dev/null; then G1=1; fi
      fi
      O2=$(python3 dsp4_diag.py --chip 2 2>&1)
      if echo "$O2" | grep -q "MAGIC          0xD5B40001"; then
        S2=$(echo "$O2"|grep BOOT_STAGE|awk '{print $2}')
        if [ -n "$S2" ] && [ "$S2" -ge 6 ] 2>/dev/null; then G2=1; fi
      fi
      [ "$G1" = "1" ] && [ "$G2" = "1" ] && { GOT=1; break; }
      sleep 1
    done
    [ "$GOT" = "1" ] && break
    echo "  (config round $c: chip1_running=$G1 chip2_running=$G2)" >&2
  done
  echo "$GOT"
}

for attempt in 1 2 3; do
  G=$(boot_and_config)
  [ "$G" = "0" ] && { echo "  (attempt $attempt: one or both chips never reached RUNNING)"; continue; }
  python3 gainfix.py 2>&1 | sed 's/^/  /'
  sleep "$DWELL"
  R=$(python3 - "$PT" "$PP" <<'PYEOF'
import json, sys
addrs = sys.argv[1:3]
sys.argv = ['p']
import dsp4_diag as D

def link_for(chip):
    # CALIBRATES the answer phase (D74). A register that reads 0 is not a
    # measurement until this has run -- and when it CANNOT phase the link it
    # raises rather than handing back zeros, which is the whole point of the
    # fix. Raising is right; letting it kill the point is not. On 2026-09-01
    # one point of a fourteen-point ladder was lost to exactly that, because
    # the traceback escaped the retry ladder and looked like a result. Retried
    # here, and an exhausted retry reports WITNESS-UNPHASED so the outer loop
    # re-boots instead of recording a number that was never taken.
    cs, rdy = (6, 8) if chip == 1 else (24, 12)
    last = None
    for _ in range(4):
        try:
            dg = D.DiagLink(D.SpiLink('0.0', 1000000, cs, rdy_gpio=rdy))
            dg.resync()
            return dg
        except (IOError, OSError) as e:
            last = e
    print(f'WITNESS-UNPHASED chip {chip}: {last}')
    sys.exit(3)

d1 = link_for(1)
d2 = link_for(2)

def sane(dg, cid):
    try:
        return (dg.read(0xE000) == 0xD5B40001
                and dg.read(0xE001) == cid
                and dg.read(0xE005) != 0)
    except IOError:
        return False

def peek(dg, cid, a):
    for _ in range(12):
        if not sane(dg, cid):
            continue
        try:
            v = dg.peek(a)
        except IOError:
            continue
        if sane(dg, cid):
            return v
    return None

# --- witness 1: chip 1 is carrying its input (sigprofile.sh's own) ---
s1 = json.load(open('chip1.sym.json'))
g = peek(d1, 1, s1['_gain_coeff_C1_GAIN_01']) if '_gain_coeff_C1_GAIN_01' in s1 else None
if g is None:
    print('WITNESS1-UNREADABLE'); sys.exit(2)
if g != 0x3F800000:
    print(f'WITNESS1-DEAD 0x{g:08X}'); sys.exit(3)

# --- witness 2: chip 2's graph is carrying the stimulus ---
# Chip 2 is NEVER CONFIGURED, so there is no coefficient to check, and the
# inter-chip fabric cannot be witnessed by reading its RX slots: with
# DSP4_PROFILE_SIGNAL the INTERCHIP_RECV kernels execute that read and discard
# it (see the kernel's own note). What IS the input to every chip-2 chain is
# the recv node's published BLOCK, so that is what gets witnessed -- and it is
# witnessed as a SQUARE WAVE, sample 0 against sample 1, because a constant
# would survive a stuck or bypassed path and the alternation does not.
s2 = json.load(open('chip2.sym.json'))
# BUILD-AWARE. The block arm publishes a whole block (`_blk_<id>`) and the
# alternation is witnessed WITHIN it, sample 0 against sample 1. The
# per-sample arm has no block: its recv writes the scalar `_buf_<id>`, one
# sample at a time, so what can be witnessed there is that the word is one of
# the two the stimulus produces. Falling back rather than failing is what lets
# the same instrument measure the per-sample CONTROL that says what the
# conversion bought.
STIM = 0x08000000
live = []
for tag in ('MAIN_L', 'AUX_01', 'GRP_01'):
    bnm, snm = '_blk_C2_RECV_' + tag, '_buf_C2_RECV_' + tag
    if bnm in s2:
        v0 = peek(d2, 2, s2[bnm])
        v1 = peek(d2, 2, s2[bnm] + 1)
        if v0 is None or v1 is None:
            print(f'WITNESS2-UNREADABLE {bnm}'); sys.exit(2)
        if v0 != 0 and v1 == ((-v0) & 0xFFFFFFFF):
            live.append(f'{tag}=0x{v0:08X}/0x{v1:08X}')
    elif snm in s2:
        v = peek(d2, 2, s2[snm])
        if v is None:
            print(f'WITNESS2-UNREADABLE {snm}'); sys.exit(2)
        if v in (STIM, (-STIM) & 0xFFFFFFFF):
            live.append(f'{tag}=0x{v:08X}(scalar)')
if not live:
    print('WITNESS2-SILENT (no probed recv carried the stimulus)')
    sys.exit(3)

# Informational, not a gate: which dynamics nodes have left their cheap
# branch. Only meaningful at limits that include them, so a zero here is not
# an error -- it is printed so the record says what the graph reached.
dyn = []
for nm in ['_lim_envelope_C2_AUX_LIM_01', '_comp_gain_C2_GRP_COMP_01',
           '_gate_gain_C2_GRP_GATE_01']:
    if nm in s2:
        v = peek(d2, 2, s2[nm])
        if v:
            dyn.append(f'{nm.split("_C2_")[0].lstrip("_")}=0x{v:08X}')

c = peek(d2, 2, int(addrs[0], 16))
p = peek(d2, 2, int(addrs[1], 16))
if c is None or p is None or p == 0:
    print(f'unreadable (cyc={c} passes={p})'); sys.exit(1)
print(f'passes={p}  {c} cycles/pass  chip2_live[{" ".join(live)}]'
      f'  dyn[{" ".join(dyn) if dyn else "-"}]  gain_coeff=0x{g:08X} OK')
PYEOF
)
  RC=$?
  case "$R" in
    WITNESS*) echo "  (attempt $attempt: $R — re-running boot+config)";;
    *) echo "$R"; exit $RC;;
  esac
done
echo "no clean witness in 3 attempts"
exit 4
