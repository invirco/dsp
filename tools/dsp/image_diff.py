#!/usr/bin/env python3
"""image_diff.py -- what changed between two linked SHARC images, by symbol.

A firmware change that adds a variable or an instruction moves every address
behind it, so two images that compute the same audio still differ in almost
every word and an md5 says nothing about WHERE they differ. This compares two
.dxe files the way a reviewer would:

  code  every function's instruction list from the disassembly (elfdump),
        with each address resolved to `symbol+offset` in its own image, so a
        function that only moved compares equal;
  data  every object symbol's initial contents, word by word, with each word
        that points into a symbol resolved the same way.

It prints the functions and objects that are new, gone or different, and a
unified diff of each changed function. Everything not listed is identical up
to relocation. Usage:

    image_diff.py OLD.dxe NEW.dxe [--quiet]

Exit 0 always; it reports, the reader judges.
"""

import difflib
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import f0_stall_scan as fs  # noqa: E402

ELFDUMP = fs.ELFDUMP
SYM = re.compile(r"^([0-9a-f]{4})\s+(\S+)\s+([0-9a-f]{8})\s+([0-9a-f]{8})\s+(\w+)\s+(\w+)\s+\S+\s+'([^']*)'")
HEX = re.compile(r'0x[0-9a-f]+', re.I)


def symbols(path):
    out = subprocess.run([ELFDUMP, '-n', '.symtab', path], capture_output=True, text=True).stdout
    syms = []
    for line in out.splitlines():
        m = SYM.match(line.strip())
        if not m:
            continue
        shndx, value, size, typ, name = m.group(2), int(m.group(3), 16), int(m.group(4), 16), m.group(5), m.group(7)
        if typ not in ('object', 'function') or shndx in ('UNDEF', 'ABS') or not name:
            continue
        syms.append((value, size, name, typ, int(shndx, 16)))
    syms.sort()
    return syms


class Resolver:
    def __init__(self, syms):
        # objects and global functions only: local labels inside a function
        # would turn every branch target into a different name
        self.ranges = [(v, max(s, 1), n) for v, s, n, t, _ in syms
                       if not n.startswith('.') and not n.endswith('.end')]
        self.starts = [r[0] for r in self.ranges]

    def name(self, value):
        import bisect
        k = bisect.bisect_right(self.starts, value) - 1
        while k >= 0:
            v, s, n = self.ranges[k]
            if v <= value < v + s:
                return n if value == v else f'{n}+{value - v}'
            if value - v > 0x100000:
                break
            k -= 1
        return None


def norm_text(text, res):
    def sub(m):
        val = int(m.group(0), 16)
        if val < 0x80000:          # immediates, offsets, loop counts
            return m.group(0)
        n = res.name(val)
        return n if n else m.group(0)
    return HEX.sub(sub, text)


AGL = re.compile(r'___ADI_AGL_CRT_SW_BRANCHRETURN_\d+')
LABEL_TOKEN = re.compile(r'[A-Za-z_.][\w.$]*')


def functions(path, res):
    """Function name -> normalized instruction list. Three listing artifacts
    are removed so that only real differences remain:
      * elfdump names a branch target by the FIRST label at that address,
        which is often the previous function's `X.end`; every label token is
        replaced by the function that actually starts there;
      * the compiler's ___ADI_AGL_CRT_SW_BRANCHRETURN_<n> stubs are numbered
        by a per-run counter; they are renamed by order of appearance;
      * '** fail to disassemble **' words (alignment fill between functions)
        are counted, not compared."""
    insns, labels = fs.disassemble(path)
    canon = {}
    for name, idx in sorted(labels.items(), key=lambda kv: kv[1]):
        if not name.startswith('.') and not name.endswith('.end'):
            canon.setdefault(idx, name)
    agl = {}

    def agl_name(n):
        if n not in agl:
            agl[n] = f'___ADI_AGL_CRT_SW_BRANCHRETURN_#{len(agl)}'
        return agl[n]

    def fix_labels(text):
        def sub(m):
            tok = m.group(0)
            if tok in labels and labels[tok] in canon:
                tok = canon[labels[tok]]
            return agl_name(tok) if AGL.fullmatch(tok) else tok
        return LABEL_TOKEN.sub(sub, text)

    funcs = {}
    order = []
    fill = 0
    for ins in insns:
        f = agl_name(ins['func']) if AGL.fullmatch(ins['func']) else ins['func']
        if f not in funcs:
            funcs[f] = []
            order.append(f)
        if '** fail to disassemble **' in ins['text']:
            fill += 1
            continue
        funcs[f].append(fix_labels(norm_text(ins['text'], res)))
    return funcs, order, fill


def section_names(path):
    out = subprocess.run([ELFDUMP, '-sh', path], capture_output=True, text=True).stdout
    names = {}
    for line in out.splitlines():
        m = re.match(r"^([0-9a-f]{4})\s.*'([^']*)'\s*$", line.strip())
        if m:
            names[int(m.group(1), 16)] = m.group(2)
    return names


def loaded_memory(ldr_path):
    """System byte address -> byte, from the boot stream: what the part
    actually loads. (The .dxe's own data sections use an init encoding that
    is not a flat word array, so they are not read directly.)"""
    import ldr_stream
    mem = {}
    for b in ldr_stream.parse(open(ldr_path, 'rb').read(), ldr_path):
        if b['fill'] or b['cnt'] == 0:
            continue
        payload = b['raw'][16:16 + b['cnt']]
        base = b['tgt']
        for i, v in enumerate(payload):
            mem[base + i] = v
    return mem


def objects(dxe, syms, res):
    """Object symbol -> its loaded words, pointer words resolved to symbols.
    Word-addressed DM (32-bit) sits at 0x28000000 + 4*addr in the system
    view; the byte-addressed `_bw` sections at 0x28000000 + addr."""
    ldr = os.path.splitext(dxe)[0] + '.ldr'
    mem = loaded_memory(ldr)
    names = section_names(dxe)
    out = {}
    for value, size, name, typ, shndx in syms:
        if typ != 'object' or size == 0:
            continue
        sec = names.get(shndx, '')
        if not sec.startswith('sec_dmda'):
            continue
        if '_bw' in sec:
            if size % 4:
                continue
            base, nwords = 0x28000000 + value, size // 4
        else:
            base, nwords = 0x28000000 + 4 * value, size
        words = []
        for k in range(nwords):
            bs = [mem.get(base + 4 * k + j) for j in range(4)]
            if None in bs:
                words.append('--------')      # not in the stream (zero-init)
                continue
            words.append(bs[0] | bs[1] << 8 | bs[2] << 16 | bs[3] << 24)
        normed = []
        for w in words:
            n = res.name(w) if isinstance(w, int) and w >= 0x80000 else None
            normed.append(n if n else (w if isinstance(w, str) else '%08x' % w))
        out[name] = (words, normed)
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    quiet = '--quiet' in sys.argv
    if len(args) != 2:
        print(__doc__)
        return 2
    old, new = args
    so, sn = symbols(old), symbols(new)
    ro, rn = Resolver(so), Resolver(sn)
    fo, _, fill_o = functions(old, ro)
    fn, order, fill_n = functions(new, rn)
    added = [f for f in order if f not in fo]
    gone = [f for f in fo if f not in fn]
    changed = [f for f in order if f in fo and fo[f] != fn[f]]
    same = [f for f in order if f in fo and fo[f] == fn[f]]
    print(f'code: {len(same)} functions identical up to relocation, {len(changed)} changed, '
          f'{len(added)} new, {len(gone)} gone  (fill words not compared: {fill_o} -> {fill_n})')
    for f in added:
        print(f'  + {f} ({len(fn[f])} insns)')
    for f in gone:
        print(f'  - {f}')
    for f in changed:
        print(f'  ~ {f} ({len(fo[f])} -> {len(fn[f])} insns)')
        if not quiet:
            for line in difflib.unified_diff(fo[f], fn[f], lineterm='', n=1):
                if line.startswith(('---', '+++')):
                    continue
                print('      ' + line)
    do, dn = objects(old, so, ro), objects(new, sn, rn)
    dadd = [o for o in dn if o not in do]
    dgone = [o for o in do if o not in dn]
    # identical when the loaded words are equal outright, or equal once
    # every pointer is read as symbol+offset (the target moved); a table
    # whose plain numbers happen to fall in an address range is caught by
    # the first test, not mistaken for pointers by the second
    def same_obj(o):
        return do[o][0] == dn[o][0] or do[o][1] == dn[o][1]
    dchg = [o for o in dn if o in do and not same_obj(o)]
    dsame = [o for o in dn if o in do and same_obj(o)]
    print(f'data: {len(dsame)} objects identical up to relocation, {len(dchg)} changed, '
          f'{len(dadd)} new, {len(dgone)} gone')
    for o in dadd:
        print(f'  + {o} = {" ".join(dn[o][1][:8])}{" ..." if len(dn[o][1]) > 8 else ""}')
    for o in dgone:
        print(f'  - {o}')
    for o in dchg:
        a_, b_ = do[o][1], dn[o][1]
        diffs = [(i, a, b) for i, (a, b) in enumerate(zip(a_, b_)) if a != b]
        lens = '' if len(a_) == len(b_) else f' (size {len(a_)} -> {len(b_)})'
        print(f'  ~ {o}{lens}: ' + ', '.join(f'[{i}] {a} -> {b}' for i, a, b in diffs[:6])
              + (' ...' if len(diffs) > 6 else ''))
    return 0


if __name__ == '__main__':
    sys.exit(main())
