#!/usr/bin/env python3
"""reg_dead_check.py -- prove a data register is dead after a site in a linked image.

Written for S176's anomaly-20000072 fix: the FX-engine and noise-generator
float-island exits used to end

        f0 = f0 * f1;   r0 = fix f0;    dm(_buf_X) = r0;

and now end

        f1 = f0 * f1;   r0 = fix f1;    dm(_buf_X) = r0;

Register 0 ends with the same value either way; register 1 ends holding the
scaled float instead of the 2^28 constant. The audio is unchanged if and only
if nothing READS register 1 before something WRITES it, on every path out of
that store -- through the rest of the function, its `rts`, every caller's
continuation and every function those continuations call. That is what this
checks, on the disassembled image (elfdump), conservatively:

  * a path ends (proved) at an unconditional write of the register that does
    not also read it;
  * a path FAILS at any read: an operand, a store source, a compare, a
    register-pair (lw) access, a conditional write's own reads, or an
    instruction the parser cannot classify;
  * jumps and do-loops are followed (both ways when conditional), calls go
    into the callee with the return point pushed, `rts`/`rti` return to it,
    and with nothing pushed they return to every call site of the function;
  * an indirect jump or call, or a branch target that cannot be resolved,
    FAILS the path.

Interrupts are not followed: every ISR in this firmware banks or saves the
registers it uses (sport_init.asm / diag.asm), so it cannot read the
interrupted code's r1.

Usage:
    reg_dead_check.py IMAGE.dxe REG ADDR [ADDR ...]
      REG   r0..r15 (the f/r alias is the same register)
      ADDR  hex address of the first instruction AFTER the site
Exit 0 when every path from every ADDR is proved; 1 otherwise (the failing
path is printed).
"""

import re
import sys

sys.path.insert(0, __import__('os').path.dirname(__import__('os').path.abspath(__file__)))
import f0_stall_scan as fs  # noqa: E402  (shares the disassembler)

MAX_STEPS = 200000


def reg_tokens(text, n):
    return re.findall(r'\b[rfs]%d\b' % n, text, re.I)


def effect(text, n):
    """'read', 'kill', or 'none' for register n in one instruction."""
    if '** fail to disassemble **' in text:
        return 'read'
    body = text.rstrip(';').strip()
    parts = fs.split_top(body)
    reads = False
    kills = False
    for p in parts:
        cond = bool(re.match(r'^(?:if\s|else\b)', p.strip(), re.I))
        q = fs.strip_cond(p)
        lw = re.search(r'\(\s*lw\s*\)', q, re.I)
        m = re.match(r'^([^=]+?)\s*=\s*(.+)$', q)
        if m and not re.match(r'^(?:dm|pm)\s*\(', m.group(1).strip(), re.I):
            lhs, rhs = m.group(1).strip(), m.group(2)
            if reg_tokens(rhs, n):
                reads = True
            # a long-word load of the even partner writes this one too
            pair = lw and re.fullmatch(r'[rf]%d' % (n & ~1), lhs, re.I)
            if re.fullmatch(r'[rf]%d' % n, lhs, re.I) or pair:
                if cond:
                    pass          # a conditional write does not end the path
                else:
                    kills = True
            elif reg_tokens(lhs, n):
                reads = True      # e.g. a register used inside an address
        else:
            if reg_tokens(q, n):
                reads = True
            if lw and re.search(r'\b[rf]%d\b' % (n & ~1), q, re.I):
                reads = True      # a long-word store of the pair reads both
    if reads:
        return 'read'
    if kills:
        return 'kill'
    return 'none'


def build(path):
    insns, labels = fs.disassemble(path)
    by_addr = {ins['addr']: i for i, ins in enumerate(insns)}
    # function entry: the last non-local label at or before each instruction
    entry_of = []
    cur = None
    label_at = {}
    for name, idx in labels.items():
        label_at.setdefault(idx, []).append(name)
    for i in range(len(insns)):
        for name in label_at.get(i, []):
            if not name.startswith('.') and not name.endswith('.end'):
                cur = i
        entry_of.append(cur)
    calls = {}
    for i, ins in enumerate(insns):
        m = re.match(r'^(?:if\s+\w+\s+)?call\s+([A-Za-z_][\w.]*)', ins['text'])
        if m:
            t = resolve(m.group(1), i, insns, labels, by_addr)
            if t is not None:
                calls.setdefault(entry_of[t] if entry_of[t] is not None else t, []).append(i)
    return insns, labels, by_addr, entry_of, calls


def resolve(target, i, insns, labels, by_addr):
    target = target.strip()
    if target in labels:
        idx = labels[target]
        # `foo.end` labels can share the address of the next function's entry
        return idx if idx < len(insns) else None
    m = re.fullmatch(r'-?0x[0-9a-f]+|-?\d+', target, re.I)
    if m:
        return by_addr.get(insns[i]['addr'] + int(target, 0))
    return None


def loop_end_of(insns, labels, by_addr):
    ends = {}
    for i, ins in enumerate(insns):
        m = fs.DO_LOOP.search(ins['text'])
        if not m:
            continue
        t = m.group(1).strip()
        if t in labels:
            ends[labels[t] - 1] = i + 1
        else:
            try:
                want = ins['addr'] + int(t, 0)
            except ValueError:
                continue
            k = by_addr.get(want)
            if k is not None:
                ends[k] = i + 1
    return ends


def successors(i, stack, insns, labels, by_addr, entry_of, calls, ends):
    """Yield (index, stack) pairs that can execute after insn i, or raise."""
    text = insns[i]['text']
    t = text.rstrip(';').strip()
    nxt = []
    delayed = '(db)' in t.replace(' ', '')
    m = re.match(r'^(if\s+(?:not\s+)?\w+\s+)?jump\s+(\(pc,\s*)?([^)\s,;]+)\)?', t, re.I)
    if m:
        tgt = resolve(m.group(3), i, insns, labels, by_addr)
        if tgt is None:
            raise ValueError(f'unresolved jump at {insns[i]["addr"]:08x}: {text}')
        skip = 3 if delayed else 1
        if delayed:
            # the two delay-slot instructions run first, then the target
            nxt.append((i + 1, stack, ('delay', tgt, 2)))
        else:
            nxt.append((tgt, stack, None))
        if m.group(1) or ', else' in t:
            nxt.append((i + skip, stack, None))
        return nxt
    m = re.match(r'^(if\s+(?:not\s+)?\w+\s+)?call\s+(\(pc,\s*)?([^)\s,;]+)\)?', t, re.I)
    if m:
        tgt = resolve(m.group(3), i, insns, labels, by_addr)
        if tgt is None:
            raise ValueError(f'unresolved call at {insns[i]["addr"]:08x}: {text}')
        ret = i + (3 if delayed else 1)
        nxt.append((tgt, stack + (ret,), None))
        if m.group(1):
            nxt.append((ret, stack, None))
        return nxt
    if re.match(r'^(?:if\s+(?:not\s+)?\w+\s+)?(rts|rti)\b', t, re.I):
        cond = t.lower().startswith('if')
        if stack:
            nxt.append((stack[-1], stack[:-1], None))
        else:
            e = entry_of[i]
            sites = calls.get(e, [])
            if not sites:
                raise ValueError(f'return from {insns[e]["func"] if e is not None else "?"} '
                                 f'with no caller found')
            for s in sites:
                ret = s + (3 if '(db)' in insns[s]['text'].replace(' ', '') else 1)
                nxt.append((ret, (), None))
        if cond:
            nxt.append((i + 1, stack, None))
        return nxt
    if re.search(r'\b(?:jump|call)\s*\(\s*m\d+\s*,\s*i\d+\s*\)', t, re.I):
        raise ValueError(f'indirect branch at {insns[i]["addr"]:08x}: {text}')
    nxt.append((i + 1, stack, None))
    if i in ends:
        nxt.append((ends[i], stack, None))
    return nxt


def prove(path, n, start_addrs):
    insns, labels, by_addr, entry_of, calls = build(path)
    ends = loop_end_of(insns, labels, by_addr)
    ok = True
    for a in start_addrs:
        if a not in by_addr:
            print(f'  {a:08x}: not an instruction address')
            ok = False
            continue
        work = [(by_addr[a], (), None, [])]
        seen = set()
        steps = 0
        kills = 0
        while work:
            i, stack, pend, trail = work.pop()
            steps += 1
            if steps > MAX_STEPS:
                print(f'  {a:08x}: gave up after {MAX_STEPS} steps')
                ok = False
                break
            key = (i, stack, pend)
            if key in seen:
                continue
            seen.add(key)
            if i >= len(insns):
                print(f'  {a:08x}: ran off the end of the code')
                ok = False
                continue
            ins = insns[i]
            eff = effect(ins['text'], n)
            if eff == 'read':
                print(f'  {a:08x}: r{n} READ at {ins["addr"]:08x} {ins["func"]}: {ins["text"]}')
                for t in trail[-8:]:
                    print(f'      via {t}')
                ok = False
                continue
            if eff == 'kill':
                kills += 1
                continue
            try:
                if pend is not None:
                    _, tgt, left = pend
                    succ = [(tgt, stack, None)] if left == 1 else [(i + 1, stack, ('delay', tgt, left - 1))]
                else:
                    succ = successors(i, stack, insns, labels, by_addr, entry_of, calls, ends)
            except ValueError as e:
                print(f'  {a:08x}: {e}')
                ok = False
                continue
            for j, st, pd in succ:
                work.append((j, st, pd, trail + [f'{ins["addr"]:08x} {ins["text"]}']))
        print(f'  {a:08x} ({insns[by_addr[a]]["func"]}): '
              f'{"DEAD on every path" if ok else "NOT PROVED"} '
              f'({len(seen)} states, {kills} path ends at a write)')
    return ok


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    path, reg = sys.argv[1], sys.argv[2]
    n = int(re.fullmatch(r'[rf](\d+)', reg, re.I).group(1))
    addrs = [int(x, 16) for x in sys.argv[3:]]
    return 0 if prove(path, n, addrs) else 1


if __name__ == '__main__':
    sys.exit(main())
