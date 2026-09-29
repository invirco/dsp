#!/usr/bin/env python3
"""c2_mix_cost.py — what a chip-2 mix bus costs, counted off the emitted ASM.

WHY IT IS COUNTED AND NOT ASSERTED. S148 priced lever L1 from two MEASURED
rates taken on other code — 192 cycles/block per declared source for the
generic wrapper (S23-5) and 5.29 cycles/MAC for chip 1's fabric
(FRONTIER_RTG_RESIDUAL) — and multiplied them out. That is the right way to
price a lever nobody has built. Once it IS built the number should come from
the thing itself, and cycles cannot be measured desk-side, so this counts
the INSTRUCTIONS the two paths actually execute, straight out of the
generated assembly, for a stated number of live crosspoints.

WHAT AN INSTRUCTION COUNT IS AND IS NOT. It is exact about what the part is
asked to do and silent about stalls: SHARC memory stalls, the pipeline and
the L1/L2 placement all sit between this and a cycle. The tree's own
calibration is the wrapper path itself — S148 §6.2 prices that node at 2,112
cycles/block from S23-5's measured rate — so the cycles-per-instruction
ratio it implies is printed, and every derived figure in the S149 report is
carried at that ratio rather than at 1.0.

    python3 tools/dsp/c2_mix_cost.py                  # one aux bus, live 0..n
    python3 tools/dsp/c2_mix_cost.py --regimes        # the D24 table
    python3 tools/dsp/c2_mix_cost.py --node C2_MIX_MAIN_L -s 23 --sends 0

A MODEL OF EMITTED CODE IS A COPY OF IT, AND A COPY DRIFTS. Nothing here is
written down twice: both paths are read out of the files the generator
wrote, so a generator change moves this number with it instead of leaving it
behind.
"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, '..', '..'))
SRC = os.path.join(ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'src')
BLOCK = 16

_LOOP_RE = re.compile(r'^lcntr\s*=\s*([^,]+),\s*do\s+(\.\S+)\s+until\s+lce;')
_LABEL_RE = re.compile(r'^(\.[A-Za-z_0-9]+|[A-Za-z_][A-Za-z_0-9]*):\s*(.*)$')

# The preprocessor arms these files carry, at the values the SHIPPING image
# builds them with. Anything not named here is taken as present.
_FLAGS = {
    'DSP4_BLOCK_KERNELS': 1,
    'DSP4_BQ_GUARD': 0,
    'DSP4_CUE': 0,
    'DSP4_RTA': 0,
    'DSP4_SCOPE_BLK_TAP': 0,
    'DSP4_AUXIN_BYPASS': 0,
    'DSP4_CHAN_MASK': 1,
    # The aux matrix is OFF here so every number S149 recorded still
    # reproduces; the matrix arm is counted by its own entry points below.
    'DSP4_C2_AUX_MTX': 0,
}


def _cond(cond, flags):
    cond = cond.replace('(', ' ').replace(')', ' ')
    out = True
    for t in cond.split():
        if t == '&&':
            continue
        neg = t.startswith('!')
        key = t[1:] if neg else t
        val = bool(flags.get(key, 1))
        out &= (not val) if neg else val
    return out


def _strip(path, flags):
    """[(label, instruction)] for the arms `flags` selects."""
    out, stack = [], []
    txt = open(path, encoding='utf-8').read()
    txt = re.sub(r'/\*.*?\*/', ' ', txt, flags=re.S)
    for raw in txt.splitlines():
        s = raw.strip()
        if not s:
            continue
        if s.startswith('#'):
            tok = s.split()[0]
            if tok in ('#if', '#ifdef', '#ifndef'):
                stack.append(_cond(s[len(tok):], flags))
            elif tok == '#else' and stack:
                stack[-1] = not stack[-1]
            elif tok == '#endif' and stack:
                stack.pop()
            continue
        if not all(stack):
            continue
        m = _LABEL_RE.match(s)
        lbl = None
        if m and (s.startswith('.') or m.group(1).startswith('_')):
            lbl, s = m.group(1), m.group(2).strip()
        if s.startswith('.'):
            continue                                # assembler directive
        out.append((lbl, s or None))
    return out


def _tree(pairs, i=0):
    """(nodes, next_index). Node = ('i', text) | ('loop', bound, body)."""
    nodes = []
    while i < len(pairs):
        _, ins = pairs[i]
        i += 1
        if ins is None:
            continue
        nodes.append(('i', ins))
        m = _LOOP_RE.match(ins)
        if m:
            body, i = _tree_until(pairs, i, m.group(2))
            nodes.append(('loop', m.group(1).strip(), body))
    return nodes, i


def _tree_until(pairs, i, tail):
    """The body of a hardware loop, up to and including its LAST
    instruction.

    THE LABEL IS NOT ALWAYS THE LAST INSTRUCTION, and getting that wrong
    silently drops the loop's most expensive line. The generators emit
    both shapes -- `.lbl: insn;` on one line, and `.lbl:` alone with the
    instruction under it -- so the body ends at the first instruction AT
    OR AFTER the tail label, whichever way it was written.
    """
    body = []
    seen_label = False
    while i < len(pairs):
        lbl, ins = pairs[i]
        i += 1
        if lbl == tail:
            seen_label = True
        if ins is not None:
            body.append(('i', ins))
            m = _LOOP_RE.match(ins)
            if m:
                inner, i = _tree_until(pairs, i, m.group(2))
                body.append(('loop', m.group(1).strip(), inner))
            if seen_label:
                break
    return body, i


def _ev(nodes, counts):
    n = 0
    for node in nodes:
        if node[0] == 'i':
            n += 1
        else:
            _, bound, body = node
            if bound not in counts:
                if re.fullmatch(r'\d+', bound):
                    counts[bound] = int(bound)
                else:
                    raise KeyError(f'no loop bound for {bound!r}')
            n += counts[bound] * _ev(body, counts)
    return n


def _slice(pairs, start, stop):
    a = next(k for k, (lbl, _) in enumerate(pairs) if lbl == start)
    b = (next(k for k, (lbl, _) in enumerate(pairs) if lbl == stop)
         if stop else len(pairs))
    return pairs[a:b]


# ---------------------------------------------------------------------------
# The fabric path
# ---------------------------------------------------------------------------

# A DEAD crosspoint's whole cost, spelled out because it is the lever:
# load the coefficient, load the source address, test, take the branch,
# decrement, loop. Six instructions, against eighty for a live one.
DEAD_SCAN = 6


def _fabric_pairs():
    return _strip(os.path.join(SRC, 'chip2', 'mix_fabric.asm'),
                  dict(_FLAGS, DSP4_C2_MIX_FABRIC=1))


def fabric_cost(n_src, n_live, pairs=None):
    """Instructions `_c2_mix_fabric` executes for one bus, one block."""
    p = pairs or _fabric_pairs()
    counts = {'DSP4_BLOCK_SIZE': BLOCK, 'r5': n_live}
    brk = next(k for k, (_, ins) in enumerate(p)
               if ins and 'jump (pc, .cmf_scan)' in ins)
    sil = next(k for k, (lbl, _) in enumerate(p) if lbl == '.cmf_silent')
    head = next(k for k, (lbl, _) in enumerate(p) if lbl == '_c2_mix_fabric')
    scan = next(k for k, (lbl, _) in enumerate(p) if lbl == '.cmf_scan')

    prologue = _ev(_tree(p[head:scan])[0], counts)
    live_scan = _ev(_tree(p[scan:brk + 1])[0], counts)
    # From the scan's exit to the accumulate's own entry: the four
    # instructions that reload the output pointer and test for silence.
    entry = 4
    if n_live:
        rest = _ev(_tree(p[brk + 1 + entry:sil])[0], counts)
    else:
        rest = _ev(_tree(p[sil:])[0], counts)
    return (prologue + n_live * live_scan + (n_src - n_live) * DEAD_SCAN
            + entry + rest)


# ---------------------------------------------------------------------------
# The generic-wrapper path
# ---------------------------------------------------------------------------

def wrapper_cost(nid, n_src, n_send):
    """Instructions the GENERIC WRAPPER path executes for one bus, one
    block, with at least one switched send live — so the S23 bypass is NOT
    taken, which is exactly the regime S148-1 priced at 192 cycles/block
    per declared source."""
    path = os.path.join(SRC, 'chip2', 'nodes', f'{nid}.asm')
    p = _strip(path, dict(_FLAGS, DSP4_C2_MIX_FABRIC=0))
    counts = {'DSP4_BLOCK_SIZE': BLOCK, 'DSP4_BLOCK_SIZE-1': BLOCK - 1,
              'DSP4_BLOCK_HALF': BLOCK // 2, str(n_send): n_send,
              str(n_src): n_src}
    body = _ev(_tree(_slice(p, f'_{nid}_process_sample', None))[0], counts)
    pre = _slice(p, f'_{nid}_process', f'_{nid}_process_sample')
    nodes, _ = _tree(pre)

    def walk(ns):
        n = 0
        for node in ns:
            if node[0] == 'i':
                n += 1
                if node[1].startswith(f'call _{nid}_process_sample'):
                    n += body
            else:
                n += counts[node[1]] * walk(node[2])
        return n
    return walk(nodes)


# ---------------------------------------------------------------------------
# THE AUX MATRIX (S150)
# ---------------------------------------------------------------------------

def node_prologue(nid, mtx_on):
    """What a chip-2 aux sum runs BEFORE it tail-jumps into the fabric.

    The switched-send fold, the plain gains' conversion and -- under the
    matrix arm -- the second fold loop that ANDs the no-feedback guard's
    gate in. Counted off the emitted code, both arms, from the node's
    entry to the `jump _c2_mix_fabric;` that ends it.

    Returns (full, bypass): the path when at least one crosspoint is live,
    and the S23 bypass path when none is and the plain gain is unity.
    """
    path = os.path.join(SRC, 'chip2', 'nodes', f'{nid}.asm')
    p = _strip(path, dict(_FLAGS, DSP4_C2_MIX_FABRIC=1,
                          DSP4_C2_AUX_MTX=1 if mtx_on else 0))
    counts = {'DSP4_BLOCK_SIZE': BLOCK, 'DSP4_BLOCK_SIZE-1': BLOCK - 1,
              'DSP4_BLOCK_HALF': BLOCK // 2}
    head = next(k for k, (lbl, _) in enumerate(p) if lbl == f'_{nid}_process')
    jmp = next(k for k, (_, ins) in enumerate(p)
               if ins and ins.startswith('jump _c2_mix_fabric'))
    run = next(k for k, (lbl, _) in enumerate(p) if lbl == f'.mixrun_{nid}')
    cp = next(k for k, (lbl, _) in enumerate(p) if lbl == f'.mixcp_{nid}')
    full = _ev(_tree(p[head:jmp + 1])[0], counts)
    # The bypass leaves at the block copy: everything up to `.mixrun`
    # minus the run-path jump, plus the copy loop and its two tail stores.
    byp = _ev(_tree(p[head:run])[0], counts)
    return full, byp


def aux_pre_cost():
    """`_c2_aux_mtx_pre`: the alignment snapshot and the guard.

    Two numbers, because it has two regimes and they are three thousand
    instructions apart:

      steady   every block. The snapshot, the request bitmask, and the
               dozen exclusive-ors that say the request has not changed.
      worst    a block in which the request DID change: the closure is
               rebuilt from nothing. Bounded by construction -- a DAG on
               twelve nodes has at most sixty-six edges, so the update
               walk runs at most sixty-six times.
    """
    path = os.path.join(SRC, 'chip2', 'aux_matrix.asm')
    p = _strip(path, dict(_FLAGS, DSP4_C2_AUX_MTX=1))
    txt = open(path, encoding='utf-8').read()
    n = int(re.search(r'#define AUXMTX_N (\d+)', txt).group(1))
    na = int(re.search(r'#define AUXAL_N (\d+)', txt).group(1))
    counts = {'DSP4_BLOCK_SIZE': BLOCK, 'AUXMTX_N': n, 'AUXAL_N': na}

    def at(lbl):
        return next(k for k, (l, _) in enumerate(p) if l == lbl)

    head, cp, req, chg = (at('_c2_aux_mtx_pre'), at('.amp_cp'),
                          at('.amp_req'), at('.amp_chg'))
    sv, j, i, u, g = (at('.amp_sv'), at('.amp_j'), at('.amp_i'),
                      at('.amp_u'), at('.amp_g'))
    end = len(p)
    # software loops: body x trip count, counted between their labels
    snap = _ev(_tree(p[head:cp])[0], counts) + na * _ev(
        _tree(p[cp:req])[0], counts)
    reqp = n * _ev(_tree(p[req:chg])[0], counts)
    chgp = n * _ev(_tree(p[chg:sv - 1])[0], counts) + 3
    steady = snap + reqp + chgp
    # the rebuild. `.amp_j` .. `.amp_i` is the per-destination head;
    # `.amp_i` .. `.amp_u` the per-source test; `.amp_u` .. `.amp_inext`
    # the reach update, which runs only for a GRANTED edge.
    inext = at('.amp_inext')
    per_j = _ev(_tree(p[j:i])[0], counts)
    per_i = _ev(_tree(p[i:u])[0], counts) + _ev(_tree(p[inext:g - 1])[0],
                                                counts)
    per_u = _ev(_tree(p[u:inext])[0], counts)
    gate = n * _ev(_tree(p[g:end])[0], counts)
    max_edges = n * (n - 1) // 2
    rebuild = (n * per_j + n * n * per_i + max_edges * n * per_u + gate)
    return {'steady': steady, 'snapshot': snap, 'request': reqp,
            'change_test': chgp, 'worst': steady + rebuild,
            'rebuild': rebuild, 'n': n, 'n_align': na}


# The tree's own calibration, unchanged from S149 §1.3: S148 §6.2 prices
# C2_MIX_AUX_01 off the S23 bypass at 2,112 cycles/block and this counts
# 2,394 instructions on the same node and the same path.
CPI = 2112.0 / 2394.0
BUDGET = 327680.0          # chip 2, cycles/block at 983.04 MHz, 3,000 blk/s
POINT = BUDGET / 100.0
D24_AUX = 8                # CFG_AUX_MASK 0x00FF


def pts(instr):
    return instr * CPI / POINT


def matrix_bill():
    """The chip-2 aux-sum bill with and without the matrix, D24, counted.

    THE MATRIX'S UNCONDITIONAL COST IS THE FOLD AND THE PRE-PASS, and it
    is paid in every regime including the idle one, because a crosspoint
    that is OFF still has its level ramped and its on/off bit folded once
    a block -- that is how the S23 bypass knows it is off. What the
    matrix does NOT cost when idle is the fabric: with every switched
    coefficient zero the bypass still fires and the sum is still a block
    copy.

    THE IN-USE ROW IS THE WORST PATCH THE GUARD WILL ALLOW, not an
    average. Every FX return and every group send open on every aux (the
    S148 in-use definition), plus the MAXIMAL legal matrix: a DAG on
    eight aux buses has at most 8*7/2 = 28 edges, which is bus j taking a
    feed from every lower-numbered bus, plus all three masters into all
    eight. Fifty-two more live crosspoints, and the no-feedback guard
    makes it the most that can ever be live at once.
    """
    base_full, base_byp = node_prologue('C2_MIX_AUX_01', False)
    mtx_full, mtx_byp = node_prologue('C2_MIX_AUX_01', True)
    pre = aux_pre_cost()
    p = _fabric_pairs()
    rows = {}
    # idle: every aux on the S23 bypass
    rows['idle, every aux on the S23 bypass'] = (
        D24_AUX * base_byp, D24_AUX * mtx_byp + pre['steady'])
    # in use, without the matrix: 11 of 11 live
    base_use = D24_AUX * (base_full + fabric_cost(11, 11, p))
    mtx_use = pre['steady'] + sum(
        mtx_full + fabric_cost(26, 14 + j, p) for j in range(D24_AUX))
    rows['desk in use (worst legal patch with the matrix)'] = (
        base_use, mtx_use)
    return rows, pre, (base_full, base_byp, mtx_full, mtx_byp)


# S149 §3.2's terms, arm B, D24, chip 2. Constructions on S148's MEASURED
# baselines; nothing here was taken on a part.
S149_R1 = 74.83          # Echo default, nothing switched on, L1+L2
S149_DREV = 2.485        # one FX engine Echo -> Reverb
S149_DUSE = 5.08         # the desk in use, on the fabric


def _matrix_regimes():
    rows, pre, pro = matrix_bill()
    base_full, base_byp, mtx_full, mtx_byp = pro
    print('the aux matrix, counted off the emitted code')
    print(f'  cycles per instruction (S148 calibration)   {CPI:.3f}')
    print()
    print('  one aux sum, instructions per block:')
    print(f'    prologue, S23 bypass taken      {base_byp:6d} -> '
          f'{mtx_byp:6d}   (+{mtx_byp - base_byp})')
    print(f'    prologue, full path             {base_full:6d} -> '
          f'{mtx_full:6d}   (+{mtx_full - base_full})')
    print()
    print('  _c2_aux_mtx_pre, instructions per block:')
    print(f'    alignment snapshot ({pre["n_align"]:2d} blocks)  '
          f'{pre["snapshot"]:6d}')
    print(f'    the request bitmask             {pre["request"]:6d}')
    print(f'    "did it change?"                {pre["change_test"]:6d}')
    print(f'    STEADY STATE                    {pre["steady"]:6d}'
          f'   = {pts(pre["steady"]):.2f} points')
    print(f'    a block in which it DID change  {pre["worst"]:6d}'
          f'   = {pts(pre["worst"]):.2f} points, bounded')
    print()
    print('  D24 chip-2 aux bill, 8 buses:')
    print(f'    {"regime":46s} {"before":>8s} {"after":>8s} {"points":>8s}')
    deltas = {}
    for k, (b, m) in rows.items():
        deltas[k] = pts(m - b)
        print(f'    {k:46s} {b:8d} {m:8d} {pts(m - b):+8.2f}')
    print()
    u3 = deltas['idle, every aux on the S23 bypass']
    duse = deltas['desk in use (worst legal patch with the matrix)']
    print('  the regimes, arm B (constructions on S149 §3.3, not new')
    print('  measurements — no cycle figure here was taken on a part):')
    print(f'    {"regime":54s} {"S149":>8s} {"S150":>8s}')
    for label, rev, use in (
            ('R1  Echo default, nothing switched on', 0, False),
            ("R2' three reverbs (PW's cap), nothing switched on", 3, False),
            ('R3  Echo default, desk IN USE', 0, True),
            ("R4' three reverbs AND the desk in use", 3, True)):
        was = S149_R1 + rev * S149_DREV + (S149_DUSE if use else 0.0)
        now = was + (duse if use else u3)
        print(f'    {label:54s} {was:7.2f}% {now:7.2f}%')
    print()
    print('  ABORT LINE ~97 %. The worst regime the product can be put')
    print('  into is the last row, and the no-feedback guard is what')
    print('  makes it a WORST case rather than an open-ended one.')


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--node', default='C2_MIX_AUX_01')
    ap.add_argument('-s', '--sources', type=int, default=11)
    ap.add_argument('--sends', type=int, default=10)
    ap.add_argument('--regimes', action='store_true',
                    help='the D24 chip-2 table S149 reports')
    ap.add_argument('--matrix', action='store_true',
                    help='the aux matrix bill and the S150 regimes')
    args = ap.parse_args()

    if args.matrix:
        _matrix_regimes()
        return 0
    n_src, n_send = args.sources, args.sends
    w = wrapper_cost(args.node, n_src, n_send)
    print(f'{args.node}: {n_src} declared sources, {n_send} switched')
    print(f'  generic wrapper, off the S23 bypass : {w:6d} instr/block')
    print(f'  S148-1 priced the same node at 2,112 cycles/block -> '
          f'{2112 / w:.2f} cycles per instruction')
    print()
    print('  live   fabric   saved   marginal/source')
    prev = None
    for live in range(0, n_src + 1):
        f = fabric_cost(n_src, live)
        marg = '' if prev is None else f'{f - prev:6d}'
        print(f'  {live:4d}   {f:6d}  {w - f:6d}   {marg}')
        prev = f

    if args.regimes:
        print()
        _regimes()
    return 0


def wrapper_model(n_plain, n_send):
    """The wrapper path at a source count no node in the graph HAS.

    S148's aux matrix would take an aux bus from 11 declared sources to
    about 21, and there is no such node to count, so the wrapper is
    extrapolated — from per-source items read off the emitted code, and
    ANCHORED on the two real nodes below, which is what keeps this an
    extrapolation rather than a guess.

      a PLAIN source   3 (prologue) + 80 (stage) + 48 (MAC) + 64 (its
                       gain converted on every sample, because the
                       block-rate guard is compiled out) = 195
      a SWITCHED one   3 + 80 + 48 + ~19 (folded once per block) = 150
    """
    return 700 + 195 * n_plain + 150 * n_send


def _anchor_check():
    """wrapper_model against the two nodes that exist. +/- 3 %."""
    out = []
    for nid, n_plain, n_send in (('C2_MIX_AUX_01', 1, 10),
                                 ('C2_MIX_MAIN_L', 23, 0),
                                 ('C2_WOOF_MIX', 2, 0)):
        n_src = n_plain + n_send
        real = wrapper_cost(nid, n_src, n_send)
        model = wrapper_model(n_plain, n_send)
        out.append((nid, real, model, 100.0 * (model - real) / real))
    return out


def _regimes():
    """The D24 chip-2 mix bill, both paths, in S148 §6.2's regimes."""
    p = _fabric_pairs()
    rows = []
    # eight aux buses on a D24 (CFG_AUX_MASK 0x00FF), 11 declared sources
    aux_w = wrapper_cost('C2_MIX_AUX_01', 11, 10)
    main_w = wrapper_cost('C2_MIX_MAIN_L', 23, 0)
    woof_w = wrapper_cost('C2_WOOF_MIX', 2, 0)
    for name, n, live, count, w in (
            ('aux, S23 bypass (1 live feed)', 11, 1, 8, aux_w),
            ('aux, one FX return open', 11, 2, 8, aux_w),
            ('aux, every FX return open', 11, 7, 8, aux_w),
            ('aux, FX + every group send', 11, 11, 8, aux_w),
            ('main L/R', 23, 23, 2, main_w),
            ('woof mix', 2, 2, 1, woof_w)):
        f = fabric_cost(n, live, p)
        rows.append((name, count, w, f))
    # The aux matrix is NOT built (PW has not ruled on aux latency), so the
    # row S148 priced its regimes on is the extrapolated one and says so.
    rows.append(('aux + matrix, fully patched (model)', 8,
                 wrapper_model(1, 20), fabric_cost(21, 21, p)))
    print('  regime                              x   wrapper   fabric'
          '    saved')
    for name, c, w, f in rows:
        print(f'  {name:34s} {c:2d} {c*w:9d} {c*f:8d} {c*(w-f):8d}')
    print()
    print('  wrapper_model anchored on the nodes that exist:')
    for nid, real, model, err in _anchor_check():
        print(f'    {nid:14s} counted {real:6d}   model {model:6d}   '
              f'{err:+5.1f} %')
    print('    (C2_WOOF_MIX is TWO sources, where the fixed term is most of')
    print('     the cost and a linear model has nothing to fit. The model is')
    print('     used only for the 21-source extrapolation above, which sits')
    print('     between the two anchors it does reproduce.)')


if __name__ == '__main__':
    sys.exit(main())
