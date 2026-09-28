#!/usr/bin/env bash
# Deploy the D24 factory-station tool set to the unit, md5-verified.
#
# WHY THIS EXISTS (S132). Every bench deploy until now was a hand-typed `scp`,
# and on 2026-09-27 two of the eight tools `d24_selftest.py` stages were left
# behind: `dsp4_s49_osc.py` (S115's copy, no `--haptic`) and `s89_set.py`
# (S89's, no `cN@ADDR` form). Both moved in S122 and both are AL1's. The runner
# itself was deployed, so the station called a S122 runner through S115 tools
# and AL1 answered NO DATA "no settled window for: base, tone, back" -- an
# argparse error wearing an acoustic sentence -- on every pass for a day.
#
# `d24_selftest.py::stage_tools` CANNOT catch that: it md5-gates the stage
# directory against the runner's own directory, which under `--local` (the way
# the glass's own START launches it) IS `/home/app/selftest` on the unit. Source
# and stage are then the same stale file and match perfectly. The repo is the
# only thing that knows better, so the comparison has to be made from here.
#
#   ./deploy-bench-tools.sh --check     # report drift, write nothing
#   ./deploy-bench-tools.sh             # back up, copy what differs, re-verify
#
# ALSO COVERS THE PAIR DROP (S141). `/home/app/dspboot/codec4619.py` still had
# S136's literal `SYS001TEST001 = 0x1526` two sessions after this repo's copy
# was fixed to resolve by name, because nothing ever compared the two -- this
# script's TOOLS list is `$DEST`-only by design (`codec4619.py` isn't staged,
# it's imported by absolute path). The PAIRDROP list below checks/deploys
# `codec4619.py` and its `matrix_addr.py` dependency straight to
# `/home/app/dspboot`, same md5/backup/re-verify discipline, no staging.
#
# It touches PYTHON TOOLS ONLY. No pair, no app, no MCU/CPLD image, no rails.
#
# GENERATOR-SIDE GUARD (S136): before anything is compared or copied, every
# tools/pi file that talks the CM4 matrix bus is scanned for a hard-coded
# cell address -- the class of bug that put `SKIN = 0x1524` in `d24_panel.py`,
# true of one unit's one pack. A hit aborts the deploy; see
# `check-no-hardcoded-matrix-addr.py` for exactly what it looks for and why.
set -u
BENCH=${BENCH:-app@192.168.1.219}
DEST=${DEST:-/home/app/selftest}
STAGE=${STAGE:-/home/app/s90}      # the runner's --stage; stale copies purged here
DSPBOOT_DEST=${DSPBOOT_DEST:-/home/app/dspboot}   # the pair drop; codec4619.py + its dep live here
HERE=$(cd "$(dirname "$0")" && pwd)
CHECK=0
STAMP=$(date +%Y%m%d-%H%M%S)
[ "${1:-}" = "--check" ] && CHECK=1

if ! python3 "$HERE/check-no-hardcoded-matrix-addr.py"; then
  echo "!! aborting: fix the hard-coded address(es) above before deploying"
  exit 4
fi

# The station's own tools, then the eight STAGE_TOOLS the runner re-copies into
# its stage dir. Keep this list in step with d24_selftest.py::STAGE_TOOLS --
# --check names anything in that tuple that is missing from here.
#
# NOT HERE: the tools the runner calls out of /home/app/dspboot by absolute
# path (codec4619.py and the rest of that directory, which the stage
# SYMLINKS rather than copies) -- a copy of these into $DEST would be read by
# nothing. They belong to the pair drop and are checked/deployed separately,
# straight to $DSPBOOT_DEST, by the PAIRDROP loop below (S141: codec4619.py
# on the unit was still the pre-S136 literal-address copy two sessions after
# the name-resolving one landed in this repo, because nothing ever compared
# the two -- this script's own guard above only scans files that `import
# codec4619`, not the pair-drop file on the unit).
TOOLS="
d24_selftest.py
d24_runall.py
d24_patch.py
d24_panel.py
d24_live.py
d24_chain.py
d24_touch_inject.py
d24_bus_probe.py
d24_inputs.py
matrix_addr.py
s89_set.py
s89_signbit.py
s89_slotcap.py
dsp4_s49_osc.py
dsp4_bulk.py
dsp4_fft.py
dsp4_icrecv.py
"

# The pair-drop files the station tools depend on by absolute import
# (`/home/app/dspboot/codec4619.py` imports `matrix_addr` out of its own
# directory) -- checked and deployed straight to $DSPBOOT_DEST, never staged
# or symlinked, because nothing else in this repo's pipeline touches that
# directory and a drift there is otherwise silent (S141).
PAIRDROP="
codec4619.py
matrix_addr.py
"

# STAGE_TOOLS, read out of the runner rather than repeated here, so a name added
# to that tuple without being added above is reported and not silently skipped.
staged=$(sed -n '/^STAGE_TOOLS = (/,/)/p' "$HERE/d24_selftest.py" \
         | grep -o "'[^']*\.py'" | tr -d "'")
missing=""
for n in $staged; do
  echo "$TOOLS" | grep -qx "$n" || missing="$missing $n"
done
if [ -n "$missing" ]; then
  echo "!! STAGE_TOOLS names this script does not deploy:$missing"
  echo "   add them to TOOLS above -- a staged tool that never reaches $DEST is"
  echo "   exactly the S132 fault this script exists to stop."
  [ $CHECK -eq 1 ] || exit 2
fi

# sync_set NAME DEST LIST -- check (and, unless --check, deploy) one file set
# against one destination directory. Sets globals: ANY_STALE, ANY_FAILED.
ANY_STALE=0
ANY_FAILED=0
sync_set() {
  local label="$1" dest="$2" list="$3"
  echo "-- $label ($dest)"
  local want=""
  for n in $list; do
    [ -f "$HERE/$n" ] || { echo "-- $n: not in the repo, skipped"; continue; }
    want="$want $n"
  done
  [ -z "$want" ] && return 0

  local got stale a b
  got=$(ssh -o BatchMode=yes "$BENCH" "cd $dest && md5sum $want 2>/dev/null" || true)
  stale=""
  for n in $want; do
    a=$(md5sum "$HERE/$n" | cut -d' ' -f1)
    b=$(echo "$got" | awk -v f="$n" '$2==f {print $1}')
    if [ -z "$b" ]; then
      printf '%-24s ABSENT on the unit\n' "$n"; stale="$stale $n"
    elif [ "$a" != "$b" ]; then
      printf '%-24s DIFFERS  repo %s  unit %s\n' "$n" "${a:0:8}" "${b:0:8}"
      stale="$stale $n"
    else
      printf '%-24s same     %s\n' "$n" "${a:0:8}"
    fi
  done

  [ -z "$stale" ] && return 0
  ANY_STALE=1
  if [ $CHECK -eq 1 ]; then echo "== --check: would deploy to $dest:$stale"; return 0; fi

  echo "== deploying to $dest:$stale"
  for n in $stale; do
    ssh -o BatchMode=yes "$BENCH" \
      "cd $dest && [ -f $n ] && cp -p $n $n.bak-$STAMP || true"
    scp -q -o BatchMode=yes "$HERE/$n" "$BENCH:$dest/" || { ANY_FAILED=1; return 3; }
  done
  # ONLY THE LIVE STAGE, and only a real file (never a symlink, which points into
  # /home/app/dspboot and must stay byte-identical). Historical session directories
  # are left alone: a tool copy in one of those is the record of what that session
  # ran, not drift to be cleaned up. STAGE is $DEST's runner stage only -- the
  # pair drop has no separate stage to purge.
  if [ "$dest" = "$DEST" ]; then
    for n in $stale; do
      ssh -o BatchMode=yes "$BENCH" \
        "[ -f '$STAGE/$n' ] && [ ! -L '$STAGE/$n' ] && rm -f '$STAGE/$n'; true"
    done
  fi

  echo "== re-verify"
  local after
  after=$(ssh -o BatchMode=yes "$BENCH" "cd $dest && md5sum $stale 2>/dev/null")
  for n in $stale; do
    a=$(md5sum "$HERE/$n" | cut -d' ' -f1)
    b=$(echo "$after" | awk -v f="$n" '$2==f {print $1}')
    if [ "$a" = "$b" ]; then printf '%-24s OK       %s\n' "$n" "${a:0:8}"
    else printf '%-24s FAILED   repo %s  unit %s\n' "$n" "${a:0:8}" "${b:0:8}"; ANY_FAILED=1; fi
  done
}

sync_set "station tools" "$DEST" "$TOOLS"
sync_set "pair drop" "$DSPBOOT_DEST" "$PAIRDROP"

if [ $ANY_FAILED -ne 0 ]; then exit 4; fi
if [ $ANY_STALE -eq 0 ]; then echo "== nothing to deploy"; exit 0; fi
if [ $CHECK -eq 1 ]; then exit 1; fi
echo "== deployed, verified (backups: *.bak-$STAMP)"
exit 0
