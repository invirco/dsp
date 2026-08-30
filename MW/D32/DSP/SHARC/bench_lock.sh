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
}
