#!/bin/bash
# bench_lock.sh — one card, one runner.
#
# Session 10's method failure: two dynst.sh invocations landed on the
# bench at once, each booting the card out from under the other, and the
# symptom (wedged main loop, DMA0_STAT stuck at zero) was indistinguishable
# from a firmware hang until a byte-identical control image reproduced it
# under the same contention and passed cleanly alone. There is exactly one
# card at app@192.168.1.219 and nothing before this stopped a second script
# from driving it while the first one still had it.
#
# Sourced by every script that builds for the bench and then scp/ssh's onto
# it. Acquires an exclusive host-side flock before any of that starts and
# holds it for the rest of the process; a second invocation on this host
# — this script, or a different one that also sources this file — blocks
# behind the first and says so loudly rather than racing it on the part.
#
# Usage: source it right after `cd "$(dirname "$0")"`, then call
#   bench_lock_acquire "$0"
set -u

BENCH_LOCKFILE="${BENCH_LOCKFILE:-/tmp/dsp4-bench.lock}"

bench_lock_acquire() {
    local caller="${1:-$0}"
    exec {BENCH_LOCK_FD}>"$BENCH_LOCKFILE"
    if ! flock -n "$BENCH_LOCK_FD"; then
        local holder
        holder="$(cat "$BENCH_LOCKFILE.info" 2>/dev/null)"
        echo ">>> BENCH LOCKED: $caller is waiting for the card ($BENCH_LOCKFILE)." >&2
        [ -n "$holder" ] && echo ">>> held by: $holder" >&2
        flock "$BENCH_LOCK_FD"
        echo ">>> BENCH LOCKED: $caller acquired the card, proceeding." >&2
    fi
    printf 'pid=%s script=%s host=%s started=%s\n' \
        "$$" "$caller" "$(hostname)" "$(date -u +%FT%TZ)" > "$BENCH_LOCKFILE.info"
    # released automatically when the process holding $BENCH_LOCK_FD exits;
    # the info file is cosmetic (a human-readable "who has it") and is
    # cleared on exit so a stale name is never reported as the holder.
    trap 'rm -f "$BENCH_LOCKFILE.info"' EXIT
    bench_deploy_link_tools
}

# ---- the host half of the parameter link travels with the lock ----
#
# D74 (2026-08-31) landed a fix in tools/pi/dsp4_diag.py and
# tools/pi/dsp4_scope.py — the answer-phase calibration — and NOT ONE bar
# script deployed either file. Every one of them scp's the image, the
# per-bar probe and its own _run.sh, and then drives whatever copy of the
# link tools happens to be sitting on the card. A fix to the link can
# therefore be in the repo, be green on the bench by hand, and still be
# absent from every bar that matters.
#
# The lock is the one thing every bench script already sources, so the
# deploy hangs off it. A failure here is reported and NOT fatal: a bar
# that cannot reach the card will say so on its own terms a moment later,
# and turning an ssh hiccup into an exit from a shared helper would be
# worse than the stale copy this exists to prevent.
BENCH_HOST="${BENCH_HOST:-app@192.168.1.219}"

bench_deploy_link_tools() {
    local dir
    dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../../tools/pi" 2>/dev/null && pwd)"
    [ -n "$dir" ] || { echo ">>> BENCH DEPLOY: no tools/pi found" >&2; return 0; }
    scp -q "$dir/dsp4_config.py" "$dir/dsp4_diag.py" "$dir/dsp4_scope.py" \
           "$dir/dsp4_bootlog.py" "$dir/dsp4_spiphase.py" \
           "$BENCH_HOST:/home/app/dspboot/" 2>/dev/null \
      || echo ">>> BENCH DEPLOY: could not refresh the link tools on $BENCH_HOST" >&2
}
