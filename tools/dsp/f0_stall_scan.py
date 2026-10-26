#!/usr/bin/env python3
"""f0_stall_scan.py -- count the ADSP-2156x anomaly 20000072 pattern in a linked image.

Anomaly 20000072 (ADSP-21560/1/4/8 anomaly list NR004940B, rev 0.0 and 0.1):
"Any floating-point compute instruction with F0 as the destination register
causes pipeline stalls when followed immediately by a no-operand or
single-operand compute instruction" -- the unused source field of the second
instruction is encoded as 0 (R0), and the core takes that for a dependency on
the F0 result. Performance only; the results are correct either way.

The scan runs on the LINKED image (elfdump disassembly of every code section),
not on the sources: only what was assembled under this build's switches counts,
macros and generated nodes included. For each instruction whose compute writes
F0/R0 from a floating-point operation, the instruction(s) that can execute next
are classified:

  sequential  the next instruction in memory
  loop-wrap   the first instruction of the loop body, when the writer is the
              last instruction of a `do ... until lce` body

and a successor counts as the stall pattern when it carries exactly one compute
and that compute reads at most one data register (PASS, NEG, ABS, NOT, FIX,
FLOAT, TRUNC, RND, MANT, LOGB, RECIPS, RSQRTS, Rx+1, Rx-1, EXP, LEFTZ, LEFTO,
and the no-operand multiplier ops). Shifts by an immediate are reported on
their own line ("imm-shift"): the anomaly text does not say whether their
encoding leaves a zero Ry field, so they are counted but kept apart.

Not followed: calls/returns/jumps (a writer before `rts` is followed by the
caller's code), and the delay slots of delayed branches are simply the next
instructions in memory, which is what they are. These are listed so a reader
can see what the count does not cover.

Usage:
    f0_stall_scan.py IMAGE.dxe [IMAGE.dxe ...] [--list] [--json OUT]
Exit 0 always (it is a counter, not a gate) unless an image cannot be read.
"""

import argparse
import collections
import json
import os
import re
import subprocess
import sys

ELFDUMP = os.environ.get('ELFDUMP', '/opt/analog/cces/3.0.3/elfdump')

LINE = re.compile(r'^([0-9a-f]{8})\s+((?:[0-9a-f]{4}\s?)+?)\s{2,}(.*)$')
LABEL = re.compile(r'^([A-Za-z_.][\w.$]*):\s*$')
DO_LOOP = re.compile(r'\bdo\s*\(pc,\s*([^)]+)\)\s*until\s+lce', re.I)

DREG = re.compile(r'\b([rf])(\d{1,2})\b')
# Ops whose compute takes ONE data-register operand (or none). Matched on the
# right-hand side of a compute part.
SINGLE_OPS = re.compile(
    r'^(?:-?\s*[rf]\d+|pass\s+[rf]\d+|-\s*[rf]\d+|abs\s+[rf]\d+|not\s+[rf]\d+|'
    r'fix\s+[rf]\d+|float\s+[rf]\d+|trunc\s+[rf]\d+|rnd\s+[rf]\d+|'
    r'mant\s+[rf]\d+|logb\s+[rf]\d+|recips\s+[rf]\d+|rsqrts\s+[rf]\d+|'
    r'[rf]\d+\s*[+-]\s*1|[rf]\d+\s*[+-]\s*ci(?:\s*-\s*1)?|'
    r'exp\s+[rf]\d+(?:\s*\(ex\))?|leftz\s+[rf]\d+|lefto\s+[rf]\d+|'
    r'fpack\s+[rf]\d+|funpack\s+[rf]\d+|'
    r'sat\s+mr[fb]|rnd\s+mr[fb]|mr[fb]|0)(?:\s*\([a-z]+\))?$', re.I)
IMM_SHIFT = re.compile(
    r'^(?:a|l)shift\s+[rf]\d+\s+by\s+-?(?:0x)?[0-9a-f]+$|^rot\s+[rf]\d+\s+by\s+-?(?:0x)?[0-9a-f]+$|'
    r'^(?:bset|bclr|btgl|btst)\s+[rf]\d+\s+by\s+-?(?:0x)?[0-9a-f]+$|'
    r'^fext\s+[rf]\d+\s+by\s+(?:0x)?[0-9a-f]+:(?:0x)?[0-9a-f]+', re.I)

# Keywords that make a part a COMPUTE (ALU / multiplier / shifter) rather than
# a register transfer, a memory access or a control instruction.
COMPUTE_KW = re.compile(
    r'\b(pass|abs|not|fix|float|trunc|rnd|mant|logb|recips|rsqrts|clip|min|max|'
    r'scalb|copysign|ashift|lshift|rot|bset|bclr|btgl|btst|fext|fdep|exp|leftz|'
    r'lefto|fpack|funpack|and|or|xor|sat|comp|compu)\b', re.I)
ARITH = re.compile(r'[rf]\d+\s*[-+*]\s*[rf(\d]|^\s*-\s*[rf]\d+|[rf]\d+\s*[+-]\s*1\b', re.I)
FLOAT_HINT = re.compile(r'\bf\d+\b|\bfloat\b|\bfix\b|\btrunc\b', re.I)


def split_top(text):
    """Split an instruction on top-level commas (not inside parentheses)."""
    parts, depth, cur = [], 0, []
    for ch in text:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        if ch == ',' and depth == 0:
            parts.append(''.join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    parts.append(''.join(cur).strip())
    return [p for p in parts if p]


def strip_cond(part):
    return re.sub(r'^(?:if\s+(?:not\s+)?\w+\s+|else\s+)', '', part.strip(), flags=re.I)


def compute_parts(text):
    """The compute parts of one instruction, as (dest, rhs) pairs."""
    text = text.rstrip(';').strip()
    out = []
    for p in split_top(text):
        p = strip_cond(p)
        if re.match(r'^(?:jump|call|rts|rti|do|lcntr|bit|modify|nop|idle|sync|emuidle|push|pop|flush|cjump|rframe)\b', p, re.I):
            continue
        if re.search(r'\b(?:dm|pm)\s*\(', p, re.I):
            continue
        m = re.match(r'^([a-z]\w*)\s*=\s*(.+)$', p, re.I)
        if m:
            dest, rhs = m.group(1).lower(), m.group(2).strip()
            if dest in ('mrf', 'mrb') or DREG.fullmatch(dest):
                if COMPUTE_KW.search(rhs) or ARITH.search(rhs) or re.fullmatch(r'mr[fb]', rhs, re.I):
                    out.append((dest, rhs))
            continue
        if re.match(r'^(?:comp|compu)\s*\(', p, re.I):
            out.append(('-', p))
    return out


def classify_successor(text):
    """'single', 'imm-shift', 'multi', 'other' (not a compute), 'unknown'."""
    if '** fail to disassemble **' in text:
        return 'unknown'
    cps = compute_parts(text)
    if not cps:
        return 'other'
    if len(cps) > 1:
        return 'multi'
    dest, rhs = cps[0]
    if dest in ('mrf', 'mrb') and re.fullmatch(r'0', rhs):
        return 'single'
    if SINGLE_OPS.match(rhs.strip()):
        return 'single'
    if IMM_SHIFT.match(rhs.strip()):
        return 'imm-shift'
    return 'two-operand'


def is_f0_float_writer(text):
    """True when a compute part of this instruction writes register 0 from a
    floating-point operation (F0 = ..., or R0 = FIX/TRUNC of an F register)."""
    for dest, rhs in compute_parts(text):
        if dest == 'f0' and FLOAT_HINT.search(rhs + ' f'):
            return True
        if dest == 'r0' and re.match(r'^(?:fix|trunc)\s+f\d+', rhs, re.I):
            return True
    return False


SECTION = re.compile(r"^\s*[0-9a-f]{4}\s+\S+\s+([0-9a-f]{8})\s.*'([^']+)'\s*$")


def code_sections(path):
    """Names of the executable sections (ELF SHF_EXECINSTR) -- data sections
    disassemble too, as nonsense, and must not be counted."""
    res = subprocess.run([ELFDUMP, '-sh', path], capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f'elfdump failed on {path}: {res.stderr.strip()}')
    out = []
    for raw in res.stdout.splitlines():
        m = SECTION.match(raw)
        if m and int(m.group(1), 16) & 0x4:
            out.append(m.group(2))
    return out


def disassemble(path):
    text = []
    for sec in code_sections(path):
        res = subprocess.run([ELFDUMP, '-ns', sec, path], capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f'elfdump failed on {path}: {res.stderr.strip()}')
        text.extend(res.stdout.splitlines())
    insns, labels, func = [], {}, '?'
    for raw in text:
        lm = LABEL.match(raw.strip())
        if lm:
            name = lm.group(1)
            if not name.startswith('.') and not name.endswith('.end'):
                func = name
            labels[name] = len(insns)
            continue
        m = LINE.match(raw)
        if m:
            insns.append({'addr': int(m.group(1), 16), 'text': m.group(3).strip(), 'func': func})
    return insns, labels


def scan(path):
    insns, labels = disassemble(path)
    # loop ends: the instruction BEFORE the `until` label is the last of the body
    wraps = {}
    for i, ins in enumerate(insns):
        m = DO_LOOP.search(ins['text'])
        if not m:
            continue
        target = m.group(1).strip()
        end = labels.get(target)
        if end is None:
            # relative form `do (pc,0x25)`: offset in words from this insn
            try:
                off = int(target, 0)
            except ValueError:
                continue
            want = ins['addr'] + off
            end = next((k for k in range(i, len(insns)) if insns[k]['addr'] >= want), None)
            if end is None:
                continue
            # the label form names the instruction AFTER the body's last one
            # in the disassembly; the offset form names the last one itself
            wraps[end] = i + 1
            continue
        wraps[end - 1] = i + 1
    hits = []
    writers = 0
    for i, ins in enumerate(insns):
        if not is_f0_float_writer(ins['text']):
            continue
        writers += 1
        succ = []
        if i + 1 < len(insns):
            succ.append(('sequential', insns[i + 1]))
        if i in wraps and wraps[i] < len(insns):
            succ.append(('loop-wrap', insns[wraps[i]]))
        for how, s in succ:
            kind = classify_successor(s['text'])
            hits.append({'func': ins['func'], 'addr': ins['addr'], 'writer': ins['text'],
                         'how': how, 'next': s['text'], 'kind': kind})
    return writers, hits


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('images', nargs='+')
    ap.add_argument('--list', action='store_true', help='print every stall-pattern site')
    ap.add_argument('--json')
    a = ap.parse_args()
    report = {}
    for img in a.images:
        writers, hits = scan(img)
        kinds = collections.Counter(h['kind'] for h in hits)
        stall = [h for h in hits if h['kind'] == 'single']
        imm = [h for h in hits if h['kind'] == 'imm-shift']
        unk = [h for h in hits if h['kind'] == 'unknown']
        by_func = collections.Counter(h['func'] for h in stall)
        name = os.path.basename(img)
        print(f'{name}: {writers} float computes write F0/R0; successors: '
              + ', '.join(f'{k} {v}' for k, v in sorted(kinds.items())))
        print(f'  20000072 pattern (single/no-operand successor): {len(stall)} sites'
              f'  [+{len(imm)} imm-shift, {len(unk)} undisassemblable]')
        for f, n in by_func.most_common():
            print(f'    {n:4d}  {f}')
        if a.list:
            for h in stall + imm:
                print(f'    {h["addr"]:08x} {h["func"]:<28} {h["writer"]:<36} -> [{h["how"]}] {h["next"]}  ({h["kind"]})')
        report[name] = {'writers': writers, 'pattern': len(stall), 'imm_shift': len(imm),
                        'unknown': len(unk), 'by_func': dict(by_func),
                        'sites': stall + imm}
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump(report, fh, indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
