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
    # input_patch.json travels with dsp4_config.py (S77). The config tool
    # reads the patch from a file beside ITSELF, the file has been generated
    # from defs since S59 and moved at S72 and S74c, and until S77 nothing in
    # this tree deployed it -- so every bench script was applying whatever
    # copy /home/app/dspboot happened to hold, or failing outright when it
    # held none. Same reason the link tools are here.
    # dsp4_buildcfg.py joins them at S80, and it is the same fault a third
    # time. It is the ONLY thing on the bench that decodes what the image on
    # the part was built with, `--expect-shipping` is what scores a part
    # against shipping.config, and nothing deployed it -- so a bench read the
    # whatever copy of it had last been scp'd by hand. That mattered the
    # moment DIAG_BUILD_CFG3 got fields: a PRE-S80 copy reading the new word
    # passes its own signature check, decodes bit 0 alone, ignores the
    # instrument bit, the park gate, the matrix gate and the whole
    # shared-kernel mask, and reports "== the shipping configuration" while
    # having read almost none of it. A stale decoder that says PASS is worse
    # than one that raises.
    # dsp4_cclk.py, dsp4_blk30.py, dsp4_inscan.py and dsp4_logic_id.py join
    # at S80-12, the same fault a fourth time, found by auditing the class
    # rather than waiting for the next symptom. dsp4_cclk.py is the
    # MAGIC-bracketed clock read the bench recipe names as the SAFE
    # replacement for dsp4_diag.py --rate, which is unguarded and measured
    # -10509.64 MHz on a starved chip -- so the one tool the recipe trusts
    # instead of an ungoverned read was itself unmanaged. dsp4_blk30.py is
    # the block bar; its own contract refuses to score unless dsp4_block.py
    # is staged beside it, i.e. it assumes a deploy discipline that does not
    # exist for itself. dsp4_inscan.py was rewritten this session onto live
    # symbols, and a rewrite that nothing deploys would sit unrefreshed on
    # the card. dsp4_logic_id.py is the only tool that can say which
    # bitstream is on the part. Verified on the card today: the first three
    # are ABSENT from /home/app/dspboot/, and the logic_id copy that IS
    # there is 2b379c11... dated 2026-09-09 against the repo's 280f7ab4...
    # -- stale, a live instance of exactly this defect.
    # pan_table.py joins at S83, and it is the input_patch.json shape a
    # second time rather than a new one. `fixed_ref.py` now models the pan
    # legs through the law table (PW's S83-Q3 ruling: the wire's grid is
    # the contract) and imports `pan_table` to do it -- but every staged
    # arm's `fixed_ref.py` resolves through a symlink into ~/dspboot, so
    # the copy that runs is THIS one, and a module it imports has to be
    # here too. A bar that scp'd pan_table.py into its own stage
    # directory still died on `ModuleNotFoundError` (measured
    # 2026-09-20), because the importer was never in that directory.
    # dsp4_rxscan.py joins at S86, and it is the same class a sixth time from
    # the other end: the tool that answers "does this TDM lane carry samples"
    # has to be the one on the card, because the two that were there before it
    # both read a symbol nothing writes and both answered anyway. It is
    # deployed beside dsp4_inscan.py, which now points at it.
    scp -q "$dir/dsp4_config.py" "$dir/dsp4_diag.py" "$dir/dsp4_scope.py" \
           "$dir/dsp4_bootlog.py" "$dir/dsp4_spiphase.py" \
           "$dir/dsp4_buildcfg.py" \
           "$dir/dsp4_cclk.py" "$dir/dsp4_blk30.py" \
           "$dir/dsp4_inscan.py" "$dir/dsp4_logic_id.py" \
           "$dir/dsp4_rxscan.py" \
           "$dir/../../MW/D24/DSP/input_patch.json" \
           "$dir/../dsp/pan_table.py" \
           "$BENCH_HOST:/home/app/dspboot/" 2>/dev/null \
      || echo ">>> BENCH DEPLOY: could not refresh the link tools on $BENCH_HOST" >&2
}
