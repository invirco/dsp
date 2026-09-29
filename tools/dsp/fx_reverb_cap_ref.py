#!/usr/bin/env python3
"""fx_reverb_cap_ref.py — the bar for PW's reverb cap (S149).

PW ruled on 2026-09-29: at most THREE of the six FX engines may be on Type
Reverb at once. `src/chip2/fx_cap.asm` is the DSP half of that rule, and a
guard is only worth what it can be shown to do — so the three passes of that
routine are transliterated here and driven over every sequence of host writes
the model can reach, checking the properties the ruling actually asks for:

  1. **The cap is never exceeded.** Not "usually": never, on any block, from
     any starting state, under any sequence of writes.
  2. **A fourth Reverb is HELD, not dropped.** The request word is never
     modified by the guard, so a read-back still says what the panel says,
     and the request is still there to be granted.
  3. **A held request is granted the moment a slot frees**, with no further
     host traffic — one block later, not never.
  4. **Swapping takes ONE block.** Moving Reverb from engine 2 to engine 5 in
     a single host transaction lands in one block, because every release is
     granted before any grant.
  5. **Which three win is deterministic** — lowest engine index — so two
     units given the same writes are in the same state.

    python3 tools/dsp/fx_reverb_cap_ref.py            # 0 = every property holds
    python3 tools/dsp/fx_reverb_cap_ref.py --exhaustive

THE NEGATIVE CONTROL IS RUN TOO: `--negctl` drops the release pass, which is
the plausible mistake (grant-only), and property 4 must then FAIL.
"""
import argparse
import itertools
import random
import sys

REVERB = 3
N = 6
CAP = 3
TYPES = (0, 1, 2, 3, 4, 5, 6)


def guard(req, live, cap=CAP, release=True):
    """One call of `_fx_type_cap`, transliterated from chip2/fx_cap.asm.

    `req` is what the host wrote (never modified — the routine only ever
    READS `_fxcap_req`); `live` is `_fx_type_live_`, returned updated.
    """
    live = list(live)
    # pass 1: every non-Reverb request is granted at once
    if release:
        for i in range(len(req)):
            if req[i] != REVERB:
                live[i] = req[i]
    # pass 2: how many are on Reverb now
    n = sum(1 for t in live if t == REVERB)
    # pass 3: grant what fits, lowest engine index first
    for i in range(len(req)):
        if req[i] != REVERB or live[i] == REVERB:
            continue
        if n >= cap:
            continue                        # HELD
        live[i] = REVERB
        n += 1
    return live


def settle(req, live, blocks=4, **kw):
    """Run the guard until it stops moving (or `blocks` blocks)."""
    for _ in range(blocks):
        nxt = guard(req, live, **kw)
        if nxt == live:
            return live, True
        live = nxt
    return live, False


def check(req, live0, **kw):
    """Every property, for one (request, starting state). Returns errors."""
    bad = []
    req_before = list(req)
    live = guard(req, live0, **kw)

    # 1: the cap is never exceeded
    if sum(1 for t in live if t == REVERB) > CAP:
        bad.append(f'cap exceeded: req={req} live0={live0} -> {live}')
    # 2: the request word is untouched
    if req != req_before:
        bad.append('the guard modified the request word')
    # 3/4: it settles, and in ONE block from any state
    live2 = guard(req, live, **kw)
    if live2 != live:
        bad.append(f'not settled after one block: req={req} '
                   f'live0={live0} -> {live} -> {live2}')
    # 5: INCUMBENCY FIRST, THEN LOWEST INDEX, and both halves matter.
    #    An engine already running Reverb and still asked for Reverb keeps
    #    its slot whatever its index -- otherwise a lower-numbered engine
    #    being switched on would EVICT a reverb that is audibly running,
    #    which is a worse behaviour than holding the new one. Among the
    #    engines that are NEWLY asking, the lowest indices win.
    got = [i for i in range(len(req)) if req[i] == REVERB
           and live[i] == REVERB]
    held = [i for i in range(len(req)) if req[i] == REVERB
            and live[i] != REVERB]
    incumbent = [i for i in got if live0[i] == REVERB]
    for i in incumbent:
        if live[i] != REVERB:
            bad.append(f'an incumbent Reverb was evicted: engine {i}')
    if held and len(got) < CAP:
        bad.append(f'a request was held with room to spare: req={req} '
                   f'live0={live0} -> {live}')
    new_got = [i for i in got if i not in incumbent]
    if held and new_got and max(new_got) > min(held):
        bad.append(f'not lowest-index-first among new requests: req={req} '
                   f'live0={live0} -> {live}')
    # ...and a held engine keeps running whatever it was running
    for i in held:
        if live[i] != live0[i] and live0[i] != REVERB:
            bad.append(f'a held engine changed type: engine {i}')
    return bad


def fuzz(n_vec, seed, **kw):
    rng = random.Random(seed)
    bad = []
    for _ in range(n_vec):
        req = [rng.choice(TYPES) for _ in range(N)]
        live0 = [rng.choice(TYPES) for _ in range(N)]
        # a reachable starting state never holds more than CAP reverbs
        while sum(1 for t in live0 if t == REVERB) > CAP:
            i = rng.randrange(N)
            if live0[i] == REVERB:
                live0[i] = 0
        bad += check(req, live0, **kw)
    return bad


def swap_case(**kw):
    """Property 4, spelled out: three reverbs on 0,1,2; the host moves the
    one on engine 1 to engine 5 in a single transaction."""
    live = [REVERB, REVERB, REVERB, 0, 0, 0]
    req = [REVERB, 0, REVERB, 0, 0, REVERB]
    live = guard(req, live, **kw)
    return live == [REVERB, 0, REVERB, 0, 0, REVERB], live


def held_then_freed(**kw):
    """Property 3: a fourth request is held, then granted when a slot
    frees, with the host writing nothing further."""
    live = [REVERB, REVERB, REVERB, 0, 0, 0]
    req = [REVERB, REVERB, REVERB, REVERB, 0, 0]
    live = guard(req, live, **kw)
    if live[3] == REVERB:
        return False, 'the fourth was granted', live
    req2 = [REVERB, REVERB, 0, REVERB, 0, 0]       # engine 2 moves to Echo
    live = guard(req2, live, **kw)
    if live[3] != REVERB:
        return False, 'the held request was not granted when a slot freed', \
            live
    return True, '', live


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('-n', '--vectors', type=int, default=20000)
    ap.add_argument('--seed', type=int, default=20260929)
    ap.add_argument('--exhaustive', action='store_true',
                    help='every request over {Echo, Reverb} x 6 against '
                         'every reachable live state')
    ap.add_argument('--negctl', action='store_true',
                    help='drop the release pass; property 4 must FAIL')
    args = ap.parse_args()

    kw = {'release': not args.negctl}
    if args.negctl:
        ok, live = swap_case(**kw)
        print(f'negative control (no release pass): swap lands in one '
              f'block = {ok} -> {live}')
        if ok:
            print('NEGATIVE CONTROL DID NOT FIRE — the model proves nothing')
            return 1
        print('OK: the check does detect a grant-only guard')
        return 0

    bad = fuzz(args.vectors, args.seed, **kw)
    print(f'reverb cap: {args.vectors} random (request, state) pairs')
    print(f'  every property                   : '
          f'{"OK" if not bad else str(len(bad)) + " FAILURES"}')
    for b in bad[:5]:
        print('    ' + b)

    if args.exhaustive:
        n = 0
        for req in itertools.product((0, REVERB), repeat=N):
            for live0 in itertools.product((0, REVERB), repeat=N):
                if sum(1 for t in live0 if t == REVERB) > CAP:
                    continue
                bad += check(list(req), list(live0), **kw)
                n += 1
        print(f'  exhaustive over Echo/Reverb      : {n} pairs')

    ok4, live4 = swap_case(**kw)
    print(f'  swap Reverb 1 -> 5 in ONE block  : '
          f'{"OK" if ok4 else "FAILED " + str(live4)}')
    ok3, why3, live3 = held_then_freed(**kw)
    print(f'  held, then granted when freed    : '
          f'{"OK" if ok3 else "FAILED " + why3}')
    if bad or not ok4 or not ok3:
        return 1
    # the negative control, every run
    nok, _ = swap_case(release=False)
    print(f'  negative control (grant only)    : '
          f'{"fires — OK" if not nok else "DID NOT FIRE"}')
    if nok:
        return 1
    print('OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
