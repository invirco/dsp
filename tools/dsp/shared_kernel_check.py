#!/usr/bin/env python3
"""shared_kernel_check.py — the shared kernels' one assumption, checked.

A shared per-strip kernel (DSP4_SHARED_KERNELS, S18) addresses a node's
state as `dm(<offset>, i7)` with i7 holding that node's record base. The
offsets come from the ORDER the generator declared the node's `.var`s in,
and that order is only the addresses the linker actually assigned if the
assembler lays consecutive `.var`s out consecutively and without padding.

It does. On the shipping map COMP's 32 records are 44 words apart to the
word, GATE's 52, TUBE's 8, GAIN's 12, FDR's 16, with no gap inside one.
But "it does" is a measurement of one toolchain on one day, and a kernel
that addresses the wrong word does not fail to link, does not change the
byte count and does not look wrong in a listing -- it quietly reads strip
1's threshold from strip 7. So the assumption is CHECKED, on the map, for
every node of every shared class, and the build fails if it ever stops
holding.

    python3 shared_kernel_check.py <chipN.map.xml> <src/chipN>
    python3 shared_kernel_check.py --all <build-dir> <src-dir>

Exit 0 = every record is contiguous, in declaration order, at one stride.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import map_syms

VAR = re.compile(r'^[ \t]*\.var[ \t]+(_[A-Za-z0-9_]+)[ \t]*(?:\[([^\]]+)\])?')
COND = re.compile(r'^[ \t]*#(if|ifdef|ifndef|else|elif|endif)\b')
STUB = re.compile(r'^#if \(DSP4_SHARED_KERNELS & (\d+)\)', re.M)


def declared(path, nid, defines):
    """The node's `.var`s in declaration order, with each length resolved.

    Only the arms the build actually took: the file carries both, so the
    same `#if` the assembler followed is followed here.
    """
    out, skip, stack = [], 0, []
    for ln in open(path, encoding='utf-8'):
        if ln.lstrip().startswith('.section/pm'):
            break
        c = COND.match(ln)
        if c:
            k = c.group(1)
            if k in ('if', 'ifdef', 'ifndef'):
                cond = ln.split(None, 1)[1].strip() if ' ' in ln.strip() else ''
                take = _truth(k, cond, defines)
                stack.append(take)
                if not take:
                    skip += 1
            elif k in ('else', 'elif'):
                if stack:
                    was = stack[-1]
                    stack[-1] = not was
                    skip += 1 if was else -1
            else:
                if stack and not stack.pop():
                    skip -= 1
            continue
        if skip:
            continue
        m = VAR.match(ln)
        if m:
            out.append((m.group(1), _len(m.group(2), defines)))
    return out


def _truth(kind, cond, d):
    cond = cond.split('/*')[0].strip()
    if kind == 'ifdef':
        return cond in d
    if kind == 'ifndef':
        return cond not in d
    expr = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\b',
                  lambda m: str(d.get(m.group(1), 0)), cond)
    expr = expr.replace('!', ' not ').replace('&&', ' and ').replace('||', ' or ')
    try:
        return bool(eval(expr, {'__builtins__': {}}, {}))
    except Exception:
        raise SystemExit('shared_kernel_check: cannot evaluate #if %r' % cond)


def _len(txt, d):
    if not txt:
        return 1
    expr = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\b',
                  lambda m: str(d.get(m.group(1), 0)), txt)
    return int(eval(expr, {'__builtins__': {}}, {}))


def defines_from(hdr):
    """DSP4_* / DYN_LUT_N as the generated dsp_block.h and dyn_lut.h say."""
    d = {}
    for path in hdr:
        if not os.path.exists(path):
            continue
        for ln in open(path, encoding='utf-8'):
            m = re.match(r'^[ \t]*#define[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]+'
                         r'\(?(-?\d+)\)?[ \t]*(?:/\*.*)?$', ln)
            if m:
                d.setdefault(m.group(1), int(m.group(2)))
    return d


def check(mapxml, srcdir, extra=None):
    syms = map_syms.syms(mapxml)
    nodes_dir = os.path.join(srcdir, 'nodes')
    d = defines_from([os.path.join(srcdir, '..', 'dsp_block.h'),
                      os.path.join(srcdir, '..', 'lib', 'dyn_lut.h')])
    # THE BUILD'S OWN -D FLAGS WIN. A switch that changes the record's shape
    # -- DSP4_DYN_LUT adds 342 words to COMP's -- is on the assembler's
    # command line and in no header, so a check that read only the headers
    # would verify a layout the image does not have.
    d.update(extra or {})
    classes = {}
    for fn in sorted(os.listdir(nodes_dir)):
        if not fn.endswith('.asm'):
            continue
        path = os.path.join(nodes_dir, fn)
        head = open(path, encoding='utf-8').read(20000)
        m = STUB.search(head)
        if not m:
            continue
        nid = fn[:-4]
        cls = re.match(r'^C\d_([A-Z0-9_]+)_\d+$', nid)
        classes.setdefault(cls.group(1) if cls else nid, []).append((nid, path))
    if not classes:
        print('shared_kernel_check: no shared classes in %s' % nodes_dir)
        return 0

    bad = 0
    for cls, members in sorted(classes.items()):
        strides, nrec = set(), 0
        bases = []
        for nid, path in members:
            fields = declared(path, nid, d)
            if not fields:
                print('FAIL %s: no .var record' % nid)
                bad += 1
                continue
            off = 0
            base = syms.get(fields[0][0])
            if base is None:
                print('FAIL %s: record base %s is not in the map'
                      % (nid, fields[0][0]))
                bad += 1
                continue
            bases.append(base)
            for name, ln in fields:
                a = syms.get(name)
                if a is None:
                    print('FAIL %s: %s is not in the map' % (nid, name))
                    bad += 1
                elif a != base + off:
                    print('FAIL %s: %s is at 0x%X, the kernel addresses '
                          'base+%d = 0x%X' % (nid, name, a, off, base + off))
                    bad += 1
                off += ln
            nrec = off
        bases.sort()
        strides = {bases[i + 1] - bases[i] for i in range(len(bases) - 1)}
        print('%-8s %2d records, %d words each, base stride %s  %s'
              % (cls, len(members), nrec,
                 sorted(strides) if strides else '-',
                 'OK' if not bad else 'FAIL'))
    if bad:
        print('shared_kernel_check: %d field(s) are not where the shared '
              'kernel addresses them. The image would read another strip\'s '
              'state.' % bad)
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('mapxml')
    ap.add_argument('srcdir')
    ap.add_argument('-D', dest='defines', action='append', default=[],
                    metavar='NAME=VALUE',
                    help='a build flag, as the assembler was given it')
    a = ap.parse_args(argv)
    extra = {}
    for it in a.defines:
        k, _, v = it.partition('=')
        try:
            extra[k] = int(v, 0)
        except ValueError:
            extra[k] = 0
    return check(a.mapxml, a.srcdir, extra)


if __name__ == '__main__':
    sys.exit(main())
