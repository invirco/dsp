#!/usr/bin/env python3
"""shared_kernel_survey.py — what sharing each per-strip class would return,
and what stands in the way (S18 gate 4).

85 % of chip 1's code pool is 32 copies of 9 kernels. S18 shared ONE of them
(COMP) and measured the ratio on the part. The other eight are PW's call, and
a decision table for them is only worth reading if it is MEASURED rather than
estimated -- so this reads the same three sources the change itself does:

  * the LINKER MAP for the bytes each class actually occupies and for the
    per-node record's stride and contiguity;
  * the GENERATED SOURCE for whether the class's copies are one body (the
    same normalisation `gen_shared_kernels` applies before it shares
    anything) and for how many addressing sites the rewrite has to touch;
  * the BODY'S OWN REGISTER USE, because the mechanism needs two DAG index
    registers that no callee on the class's path touches -- and RTG, the
    single biggest class in the pool, uses all eight.

    python3 shared_kernel_survey.py <chipN.map.xml> <src/chipN>

The `share?` column is the verdict this tool is for: YES with the two spare
registers named, or NO with the reason.
"""
import argparse
import collections
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import map_syms
import dsp_codepool

# The DAG index registers a class's kernel can see moved: its own body's,
# plus every library routine it can reach, transitively. Read off the
# libraries, because "i5 and i7 are free" is the whole safety of the
# mechanism and a wrong answer there is a kernel addressing another strip.
NODE_RE_UNUSED = None
NODE_RE = re.compile(r'^C(\d)_([A-Z0-9]+(?:_[A-Z0-9]+)*?)_(\d+)$')

# The per-node stub costs the same for every class, because it is the same
# stub: the pool prologue the body used to open with, the record base, the
# predecessor pointer and a jump. MEASURED at 72 bytes on both classes S18
# landed -- COMP 1000 -> 72 and TUBE 390 -> 72.
STUB_BYTES = 72


def lib_index(libdir):
    """{routine: (dag regs it touches, routines it calls)} for every library."""
    idx = {}
    if not os.path.isdir(libdir):
        return idx
    for fn in sorted(os.listdir(libdir)):
        if not fn.endswith('.asm'):
            continue
        txt = open(os.path.join(libdir, fn), encoding='utf-8',
                   errors='replace').read()
        txt = re.sub(r'/\*.*?\*/', '', txt, flags=re.S)
        # split at each `.global _name;` / `_name:` pair -- library routines
        # are flat, one label per entry point
        # WHOLE-FILE granularity, deliberately. Splitting at the entry
        # labels missed every routine whose label is indented -- which is
        # every routine in dyn_lut_fx.asm, so i6 came back "spare" for a
        # class that calls _dyn_lut_gain. A register is charged to a class
        # if ANY routine in a file it calls into touches it; that is
        # pessimistic by at most a register or two and cannot be wrong in
        # the direction that matters.
        regs = {int(x) for x in re.findall(r'\bi([0-7])\b', txt)}
        calls = set(re.findall(r'call\s+(_[a-z][A-Za-z0-9_]*)', txt))
        for name in re.findall(r'^[ \t]*\.global[ \t]+(_[a-z][A-Za-z0-9_]*)[ \t]*;',
                               txt, re.M):
            idx[name] = (regs, calls)
    return idx


def reach(calls, idx, seen=None):
    """Every DAG index register reachable through `calls`, transitively."""
    seen = seen if seen is not None else set()
    out = set()
    for c in calls:
        if c in seen or c not in idx:
            continue
        seen.add(c)
        regs, more = idx[c]
        out |= regs | reach(more, idx, seen)
    return out


def survey(mapxml, srcdir):
    syms = map_syms.syms(mapxml)
    pool = dsp_codepool.parse(mapxml)
    per_obj = collections.Counter()
    for _tier, obj, nbytes, _ in pool:
        per_obj[obj] += nbytes
    total = sum(per_obj.values())

    nodes_dir = os.path.join(srcdir, 'nodes')
    libd = lib_index(os.path.join(os.path.dirname(srcdir.rstrip('/')), 'lib'))

    byclass = collections.defaultdict(list)
    for fn in sorted(os.listdir(nodes_dir)):
        if not fn.endswith('.asm'):
            continue
        nid = fn[:-4]
        m = NODE_RE.match(nid)
        if m:
            byclass[m.group(2)].append(nid)

    rows = []
    for cls, nids in sorted(byclass.items()):
        if len(nids) < 4:
            continue
        bodies, dagset, sites = {}, set(), collections.Counter()
        calls = set()
        for nid in nids:
            t = open(os.path.join(nodes_dir, nid + '.asm'),
                     encoding='utf-8').read()
            i = t.find('.section/pm')
            code = t[i:] if i >= 0 else t
            # A class that is ALREADY shared carries both arms. The question
            # this tool answers is about the INLINE one -- ask it of the stub
            # arm and it reports the registers the stub itself uses as taken,
            # which is how the first run of this survey came to say COMP had
            # no spare registers on the very build that proves it has two.
            code = re.sub(r'^#if \(DSP4_SHARED_KERNELS[^\n]*\n.*?^#else\n',
                          '', code, flags=re.S | re.M)
            code = re.sub(r'^#endif\n(?=\Z)', '', code, flags=re.M)
            bare = re.sub(r'/\*.*?\*/', '', code, flags=re.S)
            n = re.sub(r'^#if \(DSP4_SHARED_KERNELS[^\n]*\n.*?^#else\n', '',
                       t, flags=re.S | re.M).replace(nid, '@NODE@')
            n = re.sub(r'BLK_([A-Z_]+)_P1\b', r'BLK_\1', n)
            n = re.sub(r'_buf_C\d_[A-Z0-9_]+', '_buf_@PREV@', n)
            n = re.sub(r'SPI page=\d+ addr=\d+', 'SPI page=@ addr=@', n)
            # The file HEADER is not the body: gen_shared_kernels never sees
            # it, so neither does this. Dropping it here is what makes the
            # verdict the same one the generator would reach.
            n = n.split('*/', 1)[1] if n.lstrip().startswith('/*') else n
            bodies.setdefault(n, []).append(nid)
            if nid == nids[0]:
                dagset = {int(x) for x in re.findall(r'\bi([0-7])\b', bare)}
                sym = r'_([a-z][A-Za-z0-9_]*)_' + re.escape(nid)
                sites['direct'] = len(re.findall(r'dm\(\s*%s' % sym, bare))
                sites['base'] = len(re.findall(r'\bi[0-7]\s*=\s*%s\s*;' % sym, bare))
                sites['addr'] = len(re.findall(r'\br1?[0-9]\s*=\s*%s\s*;' % sym, bare))
                calls = set(re.findall(r'call\s+(_[a-z][A-Za-z0-9_]*)', bare))

        dagset |= reach(calls, libd)
        spare = sorted(set(range(8)) - dagset)

        objs = [n for n in nids if n in per_obj]
        nbytes = sum(per_obj[n] for n in objs)
        each = nbytes // max(len(objs), 1)

        base_field = None
        m = re.search(r'^\s*\.var\s+(_[A-Za-z0-9_]+)',
                      open(os.path.join(nodes_dir, nids[0] + '.asm'),
                           encoding='utf-8').read(), re.M)
        if m:
            base_field = m.group(1)
        strides = set()
        if base_field:
            fld = base_field[:-len(nids[0])]
            addrs = sorted(a for a in (syms.get(fld + n) for n in nids)
                           if a is not None)
            strides = {addrs[i + 1] - addrs[i] for i in range(len(addrs) - 1)}

        one_body = len(bodies) == 1
        if not one_body:
            why = 'copies are %d distinct bodies' % len(bodies)
        elif len(spare) < 2:
            why = 'only %d spare DAG reg(s) (%s)' % (len(spare), spare or '-')
        elif len(strides) != 1:
            why = 'record stride is not constant: %s' % sorted(strides)
        else:
            # The tool names the CANDIDATES; which two a landing takes is a
            # decision (COMP took i7/i5 and left i6 alone -- dyn_lut_fx's
            # SIMD gain path documents i6 as its own, and only the scalar
            # arm is in the shipping image).
            why = 'YES  spare %s' % ('/'.join('i%d' % r for r in spare))
        rows.append(dict(cls=cls, n=len(nids), each=each, total=nbytes,
                         pct=100.0 * nbytes / total if total else 0,
                         spare=spare, sites=dict(sites),
                         stride=sorted(strides), one=one_body, verdict=why))
    return rows, total


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('mapxml')
    ap.add_argument('srcdir')
    a = ap.parse_args(argv)
    rows, total = survey(a.mapxml, a.srcdir)
    rows.sort(key=lambda r: -r['total'])
    print('code pool %d bytes' % total)
    print('%-9s %3s %7s %8s %6s %8s  %-16s %s'
          % ('class', 'n', 'each', 'total', '%pool', 'returns', 'sites d/b/a',
             'share?'))
    got = 0
    for r in rows:
        s = r['sites']
        ret = r['n'] * r['each'] - r['n'] * STUB_BYTES - r['each']
        r['ret'] = max(ret, 0)
        if r['verdict'].startswith('YES'):
            got += r['ret']
        print('%-9s %3d %7d %8d %5.1f%% %8d  %-16s %s'
              % (r['cls'], r['n'], r['each'], r['total'], r['pct'], r['ret'],
                 '%d/%d/%d' % (s.get('direct', 0), s.get('base', 0),
                               s.get('addr', 0)),
                 r['verdict']))
    print('\nreturns = n*each - n*%d - each, the stub-and-one-body model '
          'measured on' % STUB_BYTES)
    print('COMP (predicted 28,696, actual 28,800) and TUBE (9,786 / 9,834), '
          'S18 section 4.')
    print('every class marked YES, done: %d bytes' % got)
    return 0


if __name__ == '__main__':
    sys.exit(main())
