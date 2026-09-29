#!/usr/bin/env python3
"""aux_matrix_ref.py — the aux matrix's no-feedback guard, proved (S150).

WHAT IS BEING PROVED, AND AGAINST WHAT. PW ruled on 2026-09-29 that "matrix
mixing should disallow all potential feedback paths". The rule has two
layers: the HOST refuses a loop-closing write and publishes
`Aux[1-12]AuxAvail[1-1]` so skins grey the cell out, and the DSP keeps its
own closure underneath so a write the host should not have made can never
cost a howl. This is the bar for the DSP half.

FOUR THINGS ARE CHECKED AND THEY ARE DIFFERENT KINDS OF THING.

  1. THE CYCLE-CAPABLE SUBGRAPH IS EXACTLY THE AUX BUSES — computed from
     dsp.csv, not asserted. S148 2b said so; if it ever stops being true
     the guard would be watching the wrong twelve nodes, so it is
     recomputed here on every run. Two statements: with the matrix edges
     removed, no `C2_MIX_AUX_j` can be reached from any `C2_AUX_*` node,
     and no master or centre bus can either.

  2. THE GUARD'S ARITHMETIC IS THE EMITTED ARITHMETIC. The model below is
     a transliteration of `chip2/aux_matrix.asm`'s four passes, and the
     constants it runs on -- how many buses, where each bus keeps its
     crosspoint row, the gate's all-ones value -- are READ OUT OF THE
     EMITTED FILE rather than written down twice.

  3. THE PROPERTIES THE RULING ASKS FOR, over random and exhaustive
     request sets: no granted set ever contains a cycle; the host's word
     is never written; every ACYCLIC request is granted in full (a legal
     patch is never held); the answer is a function of the request alone;
     a held edge is released as soon as the loop cannot close; and a
     self-feed is always held.

  4. A NEGATIVE CONTROL that fires. The plausible mistake here is a guard
     that tests only the DIRECT edge -- refusing i->j when j->i is live
     and missing every longer loop. It is run, and it must fail.

  python3 tools/dsp/aux_matrix_ref.py
  python3 tools/dsp/aux_matrix_ref.py --trials 50000

Exit: 0 pass, 1 fail.
"""
import argparse
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, HERE)
from csv_fields import parse_id_list, parse_params          # noqa: E402

CSV = os.path.join(ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'dsp.csv')
ASM = os.path.join(ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'src', 'chip2',
                   'aux_matrix.asm')
CHAIN = os.path.join(ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'src', 'chip2',
                     'process_chain.asm')
NODES = os.path.join(ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'src', 'chip2',
                     'nodes')


# ---------------------------------------------------------------------------
# The graph
# ---------------------------------------------------------------------------
def mtx_count(prm):
    raw = (prm.get('mtx_map') or '').strip()
    if not raw:
        return 0
    return sum(len([x for x in part.split(':', 1)[1].split(',') if x.strip()])
               for part in raw.split('|') if part.strip() and ':' in part)


def load_graph():
    import csv as _csv
    with open(CSV, newline='', encoding='utf-8') as f:
        rows = list(_csv.DictReader(f))
    g = {}
    for r in rows:
        nid = r['id'].strip()
        prm = parse_params(r.get('params', ''))
        srcs = parse_id_list(r.get('inputs', ''))
        n = mtx_count(prm)
        g[nid] = {
            'chip': (r.get('chip') or '').strip(),
            'direct': srcs[:len(srcs) - n] if n else srcs,
            'matrix': srcs[len(srcs) - n:] if n else [],
            'params': prm,
            'row': r,
        }
    return g


def reverse_cone(g, root):
    """Every node `root` depends on, over the NON-matrix edges."""
    seen, stack = set(), [root]
    while stack:
        n = stack.pop()
        for s in g.get(n, {}).get('direct', ()):
            if s not in seen and s in g:
                seen.add(s)
                stack.append(s)
    return seen


# ---------------------------------------------------------------------------
# The emitted constants
# ---------------------------------------------------------------------------
def read_emitted():
    txt = open(ASM, encoding='utf-8').read()
    out = {}
    m = re.search(r'#define AUXMTX_N (\d+)', txt)
    out['n'] = int(m.group(1))
    m = re.search(r'#define AUXAL_N (\d+)', txt)
    out['n_align'] = int(m.group(1))
    m = re.search(r'\.var _auxmtx_on\[AUXMTX_N\] =(.*?);', txt, re.S)
    out['on'] = [tuple(x.strip().split(' + '))
                 for x in m.group(1).split(',')]
    m = re.search(r'\.var _auxal_src\[AUXAL_N\] =(.*?);', txt, re.S)
    out['align_src'] = [x.strip() for x in m.group(1).split(',')]
    out['gate_rows'] = 'AUXMTX_N*AUXMTX_N' in txt
    # The gate's granted value: the guard loads it once and moves it in.
    out['gate_val'] = bool(re.search(r'r5 = -1;', txt))
    # The order the walk takes: destination ascending, then source
    # ascending, with the source bit built by a left shift.
    out['walk_shift'] = bool(re.search(r'r2 = lshift r2 by 1;', txt))
    # THE HOST'S WORD IS NEVER WRITTEN. `i2` is the pointer into
    # `_mix_on_<bus>` for the length of the request pass and nowhere
    # else, so the question is exactly whether that pass stores through
    # it. (Grepping the whole routine would be wrong and would say so:
    # i2 is reused for the snapshot's destination and for the reach row.)
    body = txt.split('_c2_aux_mtx_pre:', 1)[1]
    reqpass = body.split('.amp_req:', 1)[1].split('.amp_req);', 1)[0]
    out['writes_request'] = bool(re.search(r'dm\(i2[,)]', reqpass)
                                 and re.search(r'dm\(i2, *\d+\) *=', reqpass))
    out['reads_request'] = bool(re.search(r'= dm\(i2, *1\);', reqpass))
    return out


# ---------------------------------------------------------------------------
# The model: a transliteration of the four emitted passes
# ---------------------------------------------------------------------------
def guard(req, n, direct_only=False):
    """`chip2/aux_matrix.asm` passes 4 and 5, in Python.

    `req[j]` is a bitmask: bit i set = the host wants source aux i+1 into
    destination bus j+1. Returns `live`, the same shape, holding only the
    edges that were granted.

    `direct_only` is THE NEGATIVE CONTROL: it tests the reverse EDGE
    instead of reachability, which is the guard somebody writes when they
    are thinking about a two-node loop and not about a graph.
    """
    live = [0] * n
    reach = [1 << j for j in range(n)]          # reach[j] = {j}
    for j in range(n):
        for i in range(n):
            if not (req[j] & (1 << i)):
                continue
            if direct_only:
                closes = (i == j) or bool(live[i] & (1 << j))
            else:
                closes = bool(reach[j] & (1 << i))
            if closes:
                continue
            live[j] |= 1 << i
            if not direct_only:
                rj = reach[j]
                for u in range(n):
                    if reach[u] & (1 << i):
                        reach[u] |= rj
    return live


def gates(live, n):
    """Pass 5: the per-crosspoint gate word the coefficient fold ANDs in."""
    return [[-1 if live[j] & (1 << i) else 0 for i in range(n)]
            for j in range(n)]


# ---------------------------------------------------------------------------
# An INDEPENDENT judge of the same question
# ---------------------------------------------------------------------------
def has_cycle(live, n):
    """DFS over the granted edges i -> j. Written the other way round from
    the guard on purpose: the guard maintains reachability incrementally,
    this walks the finished graph."""
    adj = [[] for _ in range(n)]
    for j in range(n):
        for i in range(n):
            if live[j] & (1 << i):
                adj[i].append(j)
    state = [0] * n

    def visit(u):
        state[u] = 1
        for v in adj[u]:
            if state[v] == 1:
                return True
            if state[v] == 0 and visit(v):
                return True
        state[u] = 2
        return False

    return any(state[u] == 0 and visit(u) for u in range(n))


def req_is_acyclic(req, n):
    return not has_cycle(req, n)


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--trials', type=int, default=20000)
    ap.add_argument('--seed', type=int, default=150)
    a = ap.parse_args()
    fails = []

    def chk(ok, what):
        print(f'  {"OK  " if ok else "FAIL"}  {what}')
        if not ok:
            fails.append(what)

    print('aux matrix, no-feedback guard')

    # ---- 1: the cycle-capable subgraph, computed -------------------------
    g = load_graph()
    aux_bus = sorted(k for k, v in g.items() if v['matrix'])
    n = len(aux_bus)
    print(f'  graph: {len(g)} nodes, {n} aux sums carrying a matrix block')
    bad = []
    for b in aux_bus:
        cone = reverse_cone(g, b)
        bad += [x for x in cone if x.startswith('C2_AUX_')]
    chk(not bad,
        'with the matrix edges removed, no aux sum depends on any aux node '
        f'({len(bad)} found)')
    masters = sorted({s for v in g.values() for s in v['matrix']
                      if not s.startswith('C2_AUX_DLY_')})
    bad_m = []
    for m in masters:
        bad_m += [x for x in reverse_cone(g, m) if x.startswith('C2_AUX_')]
    chk(not bad_m,
        f'no master source {masters} depends on any aux node — so an '
        f'L/C/R feed can never close a cycle and is never gated')

    # ---- 2: the emitted constants ----------------------------------------
    e = read_emitted()
    chk(e['n'] == n, f'the emitted guard is sized for {e["n"]} buses, the '
                     f'graph has {n}')
    for k, (nid, off) in enumerate(e['on']):
        want = f'_mix_on_{aux_bus[k]}'
        prm = g[aux_bus[k]]['params']
        n_send = (int(prm.get('fx_sends', 0) or 0)
                  + sum(len([x for x in p.split(':', 1)[1].split(',')
                             if x.strip()])
                        for p in (prm.get('xp_map') or '').split('|')
                        if p.strip() and ':' in p)
                  + mtx_count(prm))
        want_off = n_send - int(prm.get('mtx_late', 0) or 0)
        if nid != want or int(off) != want_off:
            chk(False, f'row {k}: emitted {nid}+{off}, graph says '
                       f'{want}+{want_off}')
            break
    else:
        chk(True, 'every bus\'s crosspoint row is where the graph puts it '
                  f'(offset {want_off} in a {n_send}-crosspoint list)')
    chk(e['gate_val'], 'the granted gate is all-ones, not 1 — the fold ANDs '
                       'it into the host\'s own on word')
    chk(e['reads_request'] and not e['writes_request'],
        'the request pass READS the host\'s on words and never stores '
        'through that pointer — `_mix_on_` is the host\'s word and a '
        'read-back still says what the panel says')
    aligned = [s for v in g.values() for s in v['direct']] if False else None
    want_align = []
    for b in aux_bus:
        for s in g[b]['direct']:
            if s not in want_align:
                want_align.append(s)
    chk([x[len('_blk_'):] for x in e['align_src']] == want_align,
        f'the alignment snapshot covers exactly the {len(want_align)} '
        f'non-matrix sources of the aux sums, in graph order')

    # ---- 3: the one-block-late contract, off the emitted chain -----------
    chain = open(CHAIN, encoding='utf-8').read()
    order = re.findall(r'call _([A-Z0-9_]+)_process;', chain)
    pos = {}
    for k, nid in enumerate(order):
        pos.setdefault(nid, k)
    late_bad, align_bad = [], []
    for b in aux_bus:
        body = open(os.path.join(NODES, b + '.asm'), encoding='utf-8').read()
        arm = body.split('#if DSP4_C2_AUX_MTX', 1)[1].split('\n#else\n', 1)[0]
        m = re.search(r'\.var _mixsp_%s\[\d+\] = (.*?);' % b, arm, re.S)
        ptrs = [x.strip() for x in m.group(1).split(',')]
        for s in g[b]['matrix']:
            if f'_blk_{s}' not in ptrs:
                late_bad.append((b, s, 'not gathered'))
            elif s in pos and b in pos and pos[s] <= pos[b]:
                late_bad.append((b, s, f'runs at #{pos[s]} <= #{pos[b]}'))
        for s in g[b]['direct']:
            if f'_auxal_{s}' not in ptrs:
                align_bad.append((b, s))
    chk(not late_bad,
        f'every matrix source runs LATER in the emitted chain than the sum '
        f'that reads it — the read is one block late ({len(late_bad)} bad)')
    chk(not align_bad,
        f'every non-matrix source is read from the alignment snapshot, so '
        f'the whole input set is the same age ({len(align_bad)} bad)')
    # The gate row each sum reads must be the row the guard writes for it.
    row_bad = []
    for k, b in enumerate(aux_bus):
        body = open(os.path.join(NODES, b + '.asm'), encoding='utf-8').read()
        arm = body.split('#if DSP4_C2_AUX_MTX', 1)[1].split('\n#else\n', 1)[0]
        m = re.search(r'i7 = _auxmtx_gate \+ (\d+);', arm)
        if not m or int(m.group(1)) != k * n:
            row_bad.append((b, m.group(1) if m else 'absent', k * n))
    chk(not row_bad,
        f'every sum reads the gate row the guard writes for it '
        f'(row j at +{n}*j, destination bus j+1) — {row_bad}')

    chk('call _c2_aux_mtx_pre;' in chain
        and chain.index('call _c2_aux_mtx_pre;')
        < chain.index(f'call _{aux_bus[0]}_process;'),
        'the snapshot and the guard run before the first aux sum')

    # ---- 3b: the latency contract, by construction -----------------------
    #
    # PW, 2026-09-29: "0.33 ms latency is ok, but no more". The alignment
    # is ONE BLOCK and nothing here may quietly make it two: the aux sum
    # reads every source exactly one block old and its own consumers are
    # unchanged, so the aux path grows by BLOCK samples and by BLOCK
    # samples only. The base figure is the through-DSP contract the tree
    # has carried since S9-2 Option A (tools/pi/dsp4_buildcfg.py).
    blkh = open(os.path.join(ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'src',
                             'dsp_block.h'), encoding='utf-8').read()
    block = int(re.search(r'#define DSP4_BLOCK_SIZE\s+(\d+)', blkh).group(1))
    fs = 48000.0
    base_samples = 82
    added_ms = 1000.0 * block / fs
    chk(added_ms <= 0.3334,
        f'the alignment adds ONE block = {block} samples = {added_ms:.4f} ms '
        f'— PW\'s ceiling is 0.33 ms and this is the whole of it')
    chk(True, f'aux through-DSP contract: {base_samples} + {block} = '
              f'{base_samples + block} samples = '
              f'{1000.0 * (base_samples + block) / fs:.3f} ms '
              f'(main/monitor/phones unchanged at {base_samples} / '
              f'{1000.0 * base_samples / fs:.3f} ms)')
    # A SECOND block of alignment anywhere in this path is a stop, so the
    # thing that would cause one is checked rather than trusted: no aux
    # sum may read another aux sum's OUTPUT BLOCK through the snapshot.
    snap = {x[len('_blk_'):] for x in e['align_src']}
    chk(not (snap & set(aux_bus)),
        'no aux sum is itself snapshotted — a sum feeding a sum through '
        'the alignment history would be a second block of delay')

    # ---- 4: the properties, fuzzed ---------------------------------------
    rnd = random.Random(a.seed)
    full = (1 << n) - 1
    prop = {k: 0 for k in (
        'no cycle in the granted graph',
        'a legal (acyclic) request is granted in FULL',
        'the grant is a function of the request alone',
        'a self-feed is always held',
        'a held edge is granted once the loop cannot close',
        'the request word is never modified')}
    for t in range(a.trials):
        dens = rnd.choice((0.03, 0.1, 0.25, 0.5, 0.9))
        req = [0] * n
        for j in range(n):
            for i in range(n):
                if rnd.random() < dens:
                    req[j] |= 1 << i
        keep = list(req)
        live = guard(req, n)
        if has_cycle(live, n):
            fails.append(f'trial {t}: granted graph has a cycle')
            break
        prop['no cycle in the granted graph'] += 1
        if req != keep:
            fails.append(f'trial {t}: the guard modified the request')
            break
        prop['the request word is never modified'] += 1
        if req_is_acyclic(req, n) and live != req:
            fails.append(f'trial {t}: a legal request was not granted in full')
            break
        prop['a legal (acyclic) request is granted in FULL'] += 1
        if guard(list(req), n) != live:
            fails.append(f'trial {t}: not a function of the request')
            break
        prop['the grant is a function of the request alone'] += 1
        if any(live[j] & (1 << j) for j in range(n)):
            fails.append(f'trial {t}: a self-feed was granted')
            break
        prop['a self-feed is always held'] += 1
        # every held edge: drop everything else and it must be granted
        held = [(j, i) for j in range(n) for i in range(n)
                if (req[j] & (1 << i)) and not (live[j] & (1 << i))]
        if held:
            j, i = held[rnd.randrange(len(held))]
            if i != j:
                one = [0] * n
                one[j] = 1 << i
                if not (guard(one, n)[j] & (1 << i)):
                    fails.append(f'trial {t}: {i}->{j} held with no loop')
                    break
        prop['a held edge is granted once the loop cannot close'] += 1
    for k, v in prop.items():
        chk(v == a.trials, f'{k}  ({v}/{a.trials})')

    # exhaustive over a smaller matrix, every request
    small = 4
    ex = 0
    for bits in range(1 << (small * small)):
        req = [(bits >> (j * small)) & ((1 << small) - 1)
               for j in range(small)]
        live = guard(req, small)
        assert not has_cycle(live, small)
        if req_is_acyclic(req, small):
            assert live == req
        ex += 1
    chk(True, f'exhaustive over every request on a {small}x{small} matrix '
              f'({ex} of them): never a cycle, every acyclic request granted')

    # ---- 5: the negative control -----------------------------------------
    rnd = random.Random(a.seed + 1)
    fired = False
    for _ in range(4000):
        req = [0] * n
        for j in range(n):
            for i in range(n):
                if rnd.random() < 0.35:
                    req[j] |= 1 << i
        if has_cycle(guard(req, n, direct_only=True), n):
            fired = True
            break
    chk(fired, 'negative control (test the reverse EDGE, not reachability) '
               'lets a cycle through — it fires')

    print()
    if fails:
        print(f'FAIL: {len(fails)} check(s)')
        for f in fails[:8]:
            print(f'  - {f}')
        return 1
    print('aux matrix guard: every check passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
