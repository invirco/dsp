#!/usr/bin/env python3
"""dyn_simd_inline_check.py — is the INLINED paired-dynamics path the
same instruction stream as the CALLED one?

Review finding D66 put ten `call`/`rts` pairs in the two dynamics pair
kernels at 15.04 cycles of pipeline refill each, measured, so the bodies
were inlined at the call sites. The bodies now exist twice: as the
hand-written `_..._simd` routines in `lib/dyn_simd_fx.asm`, which are
still the readable reference and are what `dyn_selftest.asm` documents,
and as the macros in `lib/dyn_simd_inline.h` that the pair kernels
expand.

TWO COPIES OF AN INSTRUCTION STREAM DRIFT. This checks they have not:

  * FLATTEN each standalone routine by textually substituting every
    `call _<name>_simd;` with that routine's own body, recursively —
    which is exactly what inlining it would produce.
  * EXPAND each macro from the header, one nested macro at a time, the
    way the assembler's preprocessor does.
  * Compare the two instruction sequences token for token, after
    stripping comments, blank lines, labels and whitespace. Label NAMES
    are canonicalised — both where a label is defined and where a `do ...
    until lce` names one — because the macro takes its loop label as a
    parameter and the standalone routine hardcodes one. Nothing else is
    forgiven: opcodes, operands, order and count all have to match.

A mismatch here means the inlined graph is computing something the
reference does not, which is a numeric change hiding in an optimisation.
It is a source-level check and it does not replace the on-part bar
(`dynst.sh`: scalar vs paired, 0 of 32 samples differ) — it localises a
failure the on-part bar can only report.

Usage:  python3 tools/dsp/dyn_simd_inline_check.py [--root <repo>]
Exit 0 = every pair matches.
"""
import argparse
import os
import re
import sys

PAIRS = [
    ('_polyq_simd',    'POLYQ_SIMD',    1),
    ('_log2q_simd',    'LOG2Q_SIMD',    1),
    ('_exp2q_simd',    'EXP2Q_SIMD',    1),
    ('_mrf_rns28_simd', 'MRF_RNS28_SIMD', 0),
    ('_compgain_simd', 'COMPGAIN_SIMD', 2),
]


def strip(text):
    """Instructions only: no comments, no labels, no whitespace runs."""
    text = re.sub(r'/\*.*?\*/', ' ', text, flags=re.S)
    out = []
    for stmt in text.split(';'):
        stmt = re.sub(r'^\s*\.?[A-Za-z_][A-Za-z0-9_]*\s*:', '', stmt)
        stmt = re.sub(r'\bdo\s+\S+\s+until\s+lce\b', 'do L until lce',
                      stmt)
        stmt = ' '.join(stmt.split())
        if stmt:
            out.append(stmt)
    return out


def routine_bodies(asm):
    """name -> source text between `_name:` and `_name.end:`."""
    bodies = {}
    for m in re.finditer(r'^(_[A-Za-z0-9_]+):\s*$', asm, flags=re.M):
        name = m.group(1)
        end = asm.find(name + '.end:', m.end())
        if end < 0:
            continue
        bodies[name] = asm[m.end():end]
    return bodies


def flatten(name, bodies, seen=()):
    """The routine with every `call _x_simd;` replaced by x's own body,
    and the trailing `rts;` of each inlined body dropped — which is what
    inlining it means."""
    if name in seen:
        raise SystemExit(f'recursive call chain through {name}')
    body = bodies[name]
    out = []
    for line in body.splitlines():
        m = re.match(r'\s*call\s+(_[A-Za-z0-9_]+)\s*;', line)
        if m and m.group(1) in bodies:
            out.append(flatten(m.group(1), bodies, seen + (name,)))
        else:
            out.append(line)
    text = '\n'.join(out)
    stmts = strip(text)
    while stmts and stmts[-1] == 'rts':
        stmts.pop()
    return '\n'.join(s + ';' for s in stmts)


def macro_defs(hdr):
    """name -> (params, body) from the `#define NAME(a,b) \\ ...` forms."""
    defs = {}
    # join continuations first, then split on the #define boundaries
    joined = hdr.replace('\\\n', ' ')
    for m in re.finditer(r'^#define\s+([A-Z0-9_]+)(\([^)]*\))?\s+(.*)$',
                         joined, flags=re.M):
        name, params, body = m.group(1), m.group(2), m.group(3)
        if name.endswith('_H'):
            continue
        params = [p.strip() for p in params[1:-1].split(',')] if params else []
        defs[name] = (params, body)
    return defs


def expand(name, defs, args=None, depth=0):
    if depth > 8:
        raise SystemExit(f'macro expansion too deep at {name}')
    params, body = defs[name]
    args = args or ['.L%d' % i for i in range(len(params))]
    for p, a in zip(params, args):
        body = re.sub(r'\b%s\b' % re.escape(p), a, body)
    # expand any nested macro invocation
    for other in sorted(defs, key=len, reverse=True):
        if other == name:
            continue
        pat = r'\b%s\b(\(([^)]*)\))?' % re.escape(other)

        def sub(m):
            inner = ([x.strip() for x in m.group(2).split(',')]
                     if m.group(2) else [])
            return ' ' + expand(other, defs, inner, depth + 1) + ' '
        body = re.sub(pat, sub, body)
    return body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=os.path.join(
        os.path.dirname(os.path.abspath(__file__)), '..', '..'))
    a = ap.parse_args()
    base = os.path.join(a.root, 'MW', 'D32', 'DSP', 'SHARC', 'src', 'lib')
    asm = open(os.path.join(base, 'dyn_simd_fx.asm')).read()
    hdr = open(os.path.join(base, 'dyn_simd_inline.h')).read()

    bodies = routine_bodies(asm)
    defs = macro_defs(hdr)

    bad = 0
    for rname, mname, nlabels in PAIRS:
        if rname not in bodies:
            print(f'  {rname:18s} <-- NOT FOUND in dyn_simd_fx.asm')
            bad += 1
            continue
        want = strip(flatten(rname, bodies))
        got = strip(expand(mname, defs,
                           ['.X%d' % i for i in range(nlabels)]))
        if want == got:
            print(f'  {rname:18s} == {mname:16s} {len(want):4d} '
                  f'instructions, identical')
            continue
        bad += 1
        print(f'  {rname:18s} != {mname:16s} <-- DIFFERS '
              f'({len(want)} vs {len(got)} instructions)')
        for i in range(max(len(want), len(got))):
            w = want[i] if i < len(want) else '<end>'
            g = got[i] if i < len(got) else '<end>'
            if w != g:
                print(f'      first difference at {i}: '
                      f'routine {w!r} / macro {g!r}')
                break

    print()
    if bad:
        print(f'DYN SIMD INLINE: {bad} of {len(PAIRS)} DIFFER — the inlined '
              f'pair kernels are not running the reference arithmetic')
        return 1
    print(f'DYN SIMD INLINE IDENTICAL: {len(PAIRS)} of {len(PAIRS)} bodies '
          f'match instruction for instruction')
    return 0


if __name__ == '__main__':
    sys.exit(main())
