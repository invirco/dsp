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

THE SECOND ASSUMPTION, ADDED S21: THAT NOTHING ENTERS THE SHARED BODY
EXCEPT THROUGH A STUB. `build.sh` refused DSP4_SHARED_KERNELS together
with DSP4_SIMD_DYN from S18 until 2026-09-10 on the grounds that "the
SIMD pair drivers call _C1_COMP_nn_process_sample directly, and a shared
body reached that way would run on whatever record base the last strip
left in the register". The premise is true and the conclusion is not:
`_C1_COMP_nn_process_sample` is that NODE's stub, which loads i7 and i5
before jumping to `_shk_comp_smp`, so a caller that names it gets the
right strip whether it is the chain or a pair driver.

That was an argument, and an argument is exactly the kind of thing this
file exists to replace. `--entries` reads the whole chip source tree and
requires:

  * every reference to `_shk_<cls>_blk` / `_shk_<cls>_smp` outside
    `shared_kernels.asm` to be one of that class's own per-node stubs;
  * every stub to set BOTH registers the class's body needs -- the record
    base and, where the canonical body reads a predecessor's scalar
    buffer, the predecessor pointer -- before its jump;
  * each stub's base to be its OWN node's record base, and its
    predecessor pointer to be a `_buf_` of some other node (never its
    own), which is what "the pair layout" means for a class whose members
    are reached two at a time.

    python3 shared_kernel_check.py <chipN.map.xml> <src/chipN>
    python3 shared_kernel_check.py <chipN.map.xml> <src/chipN> --entries

Exit 0 = every record is contiguous, in declaration order, at one stride,
and every entry into a shared body carries a base.
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
    # THE ARM STACK. Each entry is [taking_this_arm, any_arm_taken_yet],
    # and the second half is what `#elif` needs: it is NOT `#else`.
    #
    # It was treated as one until S26, and the cost was 1,152 false
    # failures the moment a class with an `#elif` in its record joined the
    # table. FILT's is
    #
    #     #if DSP4_BQ_FLOAT ... #elif DSP4_BQ_GUARD ... #else ... #endif
    #
    # and with both flags 0 the old walker skipped the `#if` arm, then at
    # `#elif` merely INVERTED that -- taking an arm whose own condition it
    # never evaluated, counting `_filt_hrl` and `_filt_hrw` into the record,
    # and then reporting that the linker had put every field after them in
    # the wrong place. The generator was never wrong: it emits its offset
    # `#define`s inside the same conditionals and the ASSEMBLER evaluates
    # them. Only this independent re-reading was.
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
                stack.append([take, take])
                if not take:
                    skip += 1
            elif k in ('else', 'elif'):
                if stack:
                    was, any_taken = stack[-1]
                    if k == 'else':
                        take = not any_taken
                    else:
                        cond = (ln.split(None, 1)[1].strip()
                                if ' ' in ln.strip() else '')
                        take = (not any_taken) and _truth('if', cond, defines)
                    stack[-1] = [take, any_taken or take]
                    skip += (1 if was else 0) - (1 if take else 0)
            else:
                if stack and not stack.pop()[0]:
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
    """A field's length in words. An UNKNOWN name is a hard error, not a
    zero: a zero-length field silently shifts every field after it and the
    check then blames the linker (S21-3)."""
    if not txt:
        return 1
    unknown = sorted({n for n in re.findall(r'\b[A-Za-z_][A-Za-z0-9_]*\b', txt)
                      if n not in d})
    if unknown:
        raise SystemExit(
            'shared_kernel_check: `.var ...[%s]` uses %s, which is in no '
            'header this reader was given and on no -D flag. A length it '
            'cannot resolve would shift every field after it, so it refuses '
            'rather than assume one.' % (txt, ', '.join(unknown)))
    expr = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\b',
                  lambda m: str(d[m.group(1)]), txt)
    return int(eval(expr, {'__builtins__': {}}, {}))


_ARITH_OK = re.compile(r'^[\s0-9A-Za-z_()+\-*/<>%]+$')


def defines_from(hdr, seed=None):
    """DSP4_* / DYN_LUT_N as the generated dsp_block.h and dyn_lut.h say.

    EXPRESSIONS ARE EVALUATED, NOT SKIPPED (S21-3). This used to match only
    `#define NAME <integer>`, so `DYN_LUT_N`, whose definition is
    `(((DYN_LUT_OCTHI - DYN_LUT_OCTLO + 1) << DYN_LUT_K) + 1)`, was absent
    from the table -- and an absent name resolves to 0 in `_len()`, which
    made `.var _comp_lut_<nid>[DYN_LUT_N]` a ZERO-WORD field. Every COMP
    field after the table then appeared to be 337 words further along than
    the kernel addresses it, and the check reported the LINKER as wrong
    about a layout that was in fact correct. With DSP4_DYN_LUT=0 -- the only
    configuration S18 ever built shared kernels in -- the field does not
    exist and nothing showed.

    Two passes, because a header may use a name before this reader has seen
    it; anything still unresolved after the second pass is left out and
    `_len()` will say so by failing on it rather than assuming a length.

    THE HEADER'S OWN CONDITIONALS ARE FOLLOWED (S26), and `seed` is what
    makes that possible: dsp_block.h DERIVES several of the names the
    records are conditional on, from flags that only exist on the
    assembler's command line, so the two cannot be read independently.

        #if DSP4_SIMD_DYN && DSP4_SIMD_GRAPH
        #define DSP4_PAIRED_GRAPH 1
        #else
        #define DSP4_PAIRED_GRAPH 0
        #endif

        #if DSP4_BQ_ROUNDONCE && !DSP4_BQ_FLOAT
        #ifndef DSP4_BQ_GUARD
        #define DSP4_BQ_GUARD 1
        #endif
        #else
        #undef DSP4_BQ_GUARD
        #define DSP4_BQ_GUARD 0
        #endif

    This used to collect EVERY `#define` in the file and keep the FIRST,
    which for DSP4_BQ_GUARD is the 1 inside an arm that the shipping
    configuration does not take -- so GATE's `_gate_filter_cq` was counted
    at 11 words where the assembler emits 10, and every field after it in
    both GATE and FILT was reported as misplaced by the linker. The
    records were correct; this reader was not.

    Seeding with the -D flags and letting the header's unconditional
    defines land ON TOP is exactly what the assembler does, and it is why
    the caller must NOT re-apply -D afterwards: a `#undef` here is the
    header overriding the command line on purpose.
    """
    d = dict(seed or {})
    pending = []
    for path in hdr:
        if not os.path.exists(path):
            continue
        skip, stack = 0, []
        for ln in open(path, encoding='utf-8'):
            c = COND.match(ln)
            if c:
                k = c.group(1)
                if k in ('if', 'ifdef', 'ifndef'):
                    cond = (ln.split(None, 1)[1].strip()
                            if ' ' in ln.strip() else '')
                    take = _truth(k, cond, d)
                    stack.append([take, take])
                    if not take:
                        skip += 1
                elif k in ('else', 'elif'):
                    if stack:
                        was, any_taken = stack[-1]
                        if k == 'else':
                            take = not any_taken
                        else:
                            cond = (ln.split(None, 1)[1].strip()
                                    if ' ' in ln.strip() else '')
                            take = (not any_taken) and _truth('if', cond, d)
                        stack[-1] = [take, any_taken or take]
                        skip += (1 if was else 0) - (1 if take else 0)
                else:
                    if stack and not stack.pop()[0]:
                        skip -= 1
                continue
            if skip:
                continue
            u = re.match(r'^[ \t]*#undef[ \t]+([A-Za-z_][A-Za-z0-9_]*)', ln)
            if u:
                d.pop(u.group(1), None)
                pending = [(n, b) for n, b in pending if n != u.group(1)]
                continue
            m = re.match(r'^[ \t]*#define[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]+'
                         r'([^\\]*?)[ \t]*(?:/\*.*)?$', ln)
            if not m:
                continue
            name, body = m.group(1), m.group(2).strip()
            if not body or not _ARITH_OK.match(body):
                continue
            # A LATER DEFINE IN A TAKEN ARM WINS, and it must: the header
            # forces DSP4_BQ_GUARD to 0 after undefining whatever the
            # command line said. Resolve it now where it is a plain
            # integer, so the conditionals below it see the new value.
            d.pop(name, None)
            pending = [(n, b) for n, b in pending if n != name]
            if re.fullmatch(r'-?\d+', body):
                d[name] = int(body)
            else:
                pending.append((name, body))
    for _ in range(2):
        for name, body in pending:
            if name in d:
                continue
            expr = re.sub(r'\b([A-Za-z_][A-Za-z0-9_]*)\b',
                          lambda mm: str(d[mm.group(1)])
                          if mm.group(1) in d else mm.group(1), body)
            if re.search(r'[A-Za-z_]', expr):
                continue
            try:
                d[name] = int(eval(expr, {'__builtins__': {}}, {}))
            except Exception:
                continue
    return d


def check(mapxml, srcdir, extra=None):
    syms = map_syms.syms(mapxml)
    nodes_dir = os.path.join(srcdir, 'nodes')
    # -D FLAGS SEED THE HEADER, they do not overwrite it (S26). A switch
    # that changes the record's shape -- DSP4_DYN_LUT adds 342 words to
    # COMP's -- is on the assembler's command line and in no header, so it
    # has to reach this table; but dsp_block.h DERIVES others from those
    # same flags and `#undef`s the command line's value on purpose, so
    # applying -D last would put back a value the header deliberately
    # removed. Seeding and letting the header land on top is what the
    # assembler does. See defines_from's docstring.
    d = defines_from([os.path.join(srcdir, '..', 'dsp_block.h'),
                      os.path.join(srcdir, '..', 'lib', 'dyn_lut.h')],
                     seed=extra or {})
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


# ---------------------------------------------------------------------------
# THE ENTRY POINTS (S21)
# ---------------------------------------------------------------------------

_SHK_REF = re.compile(r'\b_shk_([a-z0-9_]+)_(blk|smp)\b')
_LABEL = re.compile(r'^\s*_([A-Za-z0-9_]+):\s*$')
_IREG_SET = re.compile(r'^\s*(i[0-7])\s*=\s*(_[A-Za-z0-9_]+)\s*;')
_JUMP_SHK = re.compile(r'^\s*jump\s+_shk_([a-z0-9_]+)_(blk|smp)\s*;')


def _blank_inert_stubs(txt, mask):
    """Blank the stub arms this build did not assemble, keeping line count.

    A node of a shared class carries BOTH arms -- the stub under
    `#if (DSP4_SHARED_KERNELS & n)` and the inline body under `#else` --
    and only one of them is in the image. With GATE and FILT in the class
    table but their bits clear, their `jump _shk_gate_blk;` is text in an
    arm the assembler skipped, and reading it as a live entry point
    reported 128 failures against an image that contains neither body.

    A class whose bit is clear is not half-enabled, it is absent, and the
    check has to agree with the preprocessor about which arm exists.
    """
    out, i = [], 0
    lines = txt.split('\n')
    while i < len(lines):
        m = STUB.match(lines[i])
        if m and not (int(m.group(1)) & mask):
            # skip to the matching #else / #endif at this nesting depth
            depth = 0
            out.append('')
            i += 1
            while i < len(lines):
                ln = lines[i].lstrip()
                if ln.startswith('#if'):
                    depth += 1
                elif ln.startswith('#endif'):
                    if depth == 0:
                        break
                    depth -= 1
                elif ln.startswith('#else') and depth == 0:
                    break
                out.append('')
                i += 1
            continue
        out.append(lines[i])
        i += 1
    return '\n'.join(out)


def entries(srcdir, extra=None):
    """Every path into a shared body starts at a stub that loads a base.

    Reads the arm the build took (the same `#if` walk `declared()` uses is
    not needed here: the stub arm and the inline arm cannot both name
    `_shk_*`, because the inline arm is the code the stub replaced).
    """
    d = defines_from([os.path.join(srcdir, '..', 'dsp_block.h'),
                      os.path.join(srcdir, '..', 'lib', 'dyn_lut.h')],
                     seed=extra or {})
    mask = d.get('DSP4_SHARED_KERNELS', 0)
    if not mask:
        print('shared_kernel_check --entries: DSP4_SHARED_KERNELS=0, '
              'no shared bodies to enter')
        return 0

    nodes_dir = os.path.join(srcdir, 'nodes')
    bad = 0
    # class -> the stub labels that are allowed to name it
    stubs = {}
    for fn_ in sorted(os.listdir(nodes_dir)):
        if not fn_.endswith('.asm'):
            continue
        nid = fn_[:-4]
        path = os.path.join(nodes_dir, fn_)
        txt = open(path, encoding='utf-8').read()
        m = STUB.search(txt)
        if not m or not (int(m.group(1)) & mask):
            continue
        cls = re.match(r'^C\d_([A-Z0-9_]+)_\d+$', nid)
        cls = cls.group(1).lower() if cls else nid.lower()
        # walk the stub arm: from the `#if (DSP4_SHARED_KERNELS & n)` to the
        # `#else`, collecting label -> (registers set, jump target)
        arm = txt[m.end():]
        arm = arm.split('\n#else', 1)[0]
        arm = re.sub(r'/\*.*?\*/',
                     lambda mm: '\n' * mm.group(0).count('\n'), arm, flags=re.S)
        cur, regs, seen = None, {}, 0
        for ln in arm.split('\n'):
            lm = _LABEL.match(ln)
            if lm:
                cur, regs = lm.group(1), {}
                continue
            rm = _IREG_SET.match(ln)
            if rm:
                regs[rm.group(1)] = rm.group(2)
                continue
            jm = _JUMP_SHK.match(ln)
            if not jm:
                continue
            seen += 1
            tgt = '_shk_%s_%s' % (jm.group(1), jm.group(2))
            if cur is None:
                print('FAIL %s: a jump to %s with no label above it'
                      % (nid, tgt))
                bad += 1
                continue
            if jm.group(1) != cls:
                print('FAIL %s: stub _%s jumps to %s, which is class %r and '
                      'not %r' % (nid, cur, tgt, jm.group(1), cls))
                bad += 1
            # the record base: this node's own first field
            base = [v for v in regs.values() if v.endswith('_' + nid)]
            prev = [v for v in regs.values()
                    if v.startswith('_buf_') and not v.endswith('_' + nid)]
            if not base:
                print('FAIL %s: stub _%s jumps to %s without loading a '
                      'register with one of its OWN fields (loaded: %s)'
                      % (nid, cur, tgt, sorted(regs.items()) or 'nothing'))
                bad += 1
            if len(base) > 1:
                print('FAIL %s: stub _%s loads %d of its own fields into DAG '
                      'registers (%s); the body takes exactly one base'
                      % (nid, cur, len(base), sorted(base)))
                bad += 1
            if len(prev) > 1:
                print('FAIL %s: stub _%s loads %d predecessor buffers (%s); '
                      'the body reads exactly one' % (nid, cur, len(prev),
                                                      sorted(prev)))
                bad += 1
            stubs.setdefault(cls, set()).add('_%s' % cur)
        if not seen:
            print('FAIL %s: carries a `#if (DSP4_SHARED_KERNELS & %s)` arm '
                  'that never jumps to a shared body' % (nid, m.group(1)))
            bad += 1

    if not stubs:
        # No node of a shared class on this chip -- chip 2 has no strip
        # COMP/TUBE at all. Same answer `check()` gives for the same tree.
        print('shared_kernel_check --entries: no shared classes in %s'
              % nodes_dir)
        return 1 if bad else 0

    # every OTHER reference to a shared body, anywhere in this chip's tree
    allowed = set()
    for v in stubs.values():
        allowed |= v
    n_ref = 0
    for root, _dirs, files in os.walk(srcdir):
        for fn_ in sorted(files):
            if not fn_.endswith('.asm'):
                continue
            if fn_ == 'shared_kernels.asm':
                continue
            path = os.path.join(root, fn_)
            nid = fn_[:-4]
            # COMMENTS OUT FIRST, AND ACROSS LINES. A stub's own header
            # comment names the body it jumps to, so a per-line
            # `split('/*')` leaves every continuation line of it looking
            # like an instruction.
            txt2 = re.sub(r'/\*.*?\*/', lambda mm: '\n' * mm.group(0).count('\n'),
                          open(path, encoding='utf-8').read(), flags=re.S)
            txt2 = _blank_inert_stubs(txt2, mask)
            cur = None
            for ln in txt2.split('\n'):
                lm = _LABEL.match(ln)
                if lm:
                    cur = '_' + lm.group(1)
                for m2 in _SHK_REF.finditer(ln):
                    n_ref += 1
                    if ln.lstrip().startswith('.extern'):
                        continue
                    if cur in allowed:
                        continue
                    print('FAIL %s: %s is named at %r, which is not one of '
                          'class %s\'s per-node stubs'
                          % (nid, m2.group(0), ln.strip()[:70], m2.group(1)))
                    bad += 1
    for cls in sorted(stubs):
        print('entries  %-6s %3d stubs, each loading its own record base; '
              '%s' % (cls, len(stubs[cls]), 'OK' if not bad else 'FAIL'))
    if bad:
        print('shared_kernel_check --entries: %d entry point(s) into a shared '
              'body do not carry a strip. Under DSP4_SIMD_DYN that is the '
              'defect build.sh refused the combination for; under any '
              'configuration it is the wrong strip\'s state.' % bad)
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('mapxml')
    ap.add_argument('srcdir')
    ap.add_argument('-D', dest='defines', action='append', default=[],
                    metavar='NAME=VALUE',
                    help='a build flag, as the assembler was given it')
    ap.add_argument('--entries', action='store_true',
                    help='also check that every path into a shared body '
                         'starts at a per-node stub that loads that strip '
                         "'s record base (S21; the assumption build.sh "
                         'refused DSP4_SIMD_DYN over)')
    a = ap.parse_args(argv)
    extra = {}
    for it in a.defines:
        k, _, v = it.partition('=')
        try:
            extra[k] = int(v, 0)
        except ValueError:
            extra[k] = 0
    rc = check(a.mapxml, a.srcdir, extra)
    if a.entries:
        rc |= entries(a.srcdir, extra)
    return rc


if __name__ == '__main__':
    sys.exit(main())
