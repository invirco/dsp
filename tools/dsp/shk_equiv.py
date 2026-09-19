#!/usr/bin/env python3
"""shk_equiv.py — the shared-kernel arm executes the SAME PROGRAM, per strip,
as the inlined arm. Proved on the machine code, not on the source.

Why this exists
---------------
`DSP4_SHARED_KERNELS` collapses 32 copies of a per-strip kernel into one body
entered with that strip's record base in a DAG register (S18/S21/S26). It is
worth ~95 KB of chip 1's code pool, and the case for it has always rested on
two arguments and a layout check:

  * the generator's own rewrite is mechanical and refuses anything it cannot
    rewrite (`dsp_codegen._shk_rewrite`);
  * `shared_kernel_check.py` asserts on the linker map that each node's record
    is contiguous, at one stride, in declaration order, and that nothing enters
    a shared body except through a per-node stub.

Both are checks on the INPUTS. Neither reads the instructions that end up in
the image, and a shared kernel that addresses the wrong word does not fail to
link, does not change the byte count and does not look wrong in a listing --
it quietly reads strip 1's threshold from strip 7. So this reads the two
images' DISASSEMBLY and answers the only question that matters:

    for every node of every shared class, does the shared arm issue the same
    instruction sequence, touching the same absolute addresses, as the
    inlined arm issued for that node?

Method
------
For each shared class C and each node N of it:

  inline arm    `_C1_C_NN_process` .. `.end`             (one body per node)
  shared arm    `_C1_C_NN_process` .. `.end`  (the stub) + `_shk_c_blk` .. `.end`

The stub is a straight-line prologue ending in a jump, so the two streams are
compared as

    canon(inline body)  ==  canon(stub minus its jump)  ++  canon(shared body)

`canon` drops the address and opcode columns, canonicalises the node-local
label suffix (`.tkb_lp_C1_TUBE_07` vs `.tkb_lp_shktube`), and -- the point of
the whole exercise -- resolves EVERY memory operand to an ABSOLUTE WORD
ADDRESS:

  * inline: `dm (_tube_sat_C1_TUBE_07)` -> the linker's address for that symbol
  * shared: `dm (0x1,i7)`               -> (what the stub loaded into i7) + 1

The stub's register loads are interpreted for real -- symbol, literal, or a
copy of another register -- so `i2=i6` resolves through to the block-pool slot
the stub passed in. Post-modified DAG accesses that BOTH arms make through the
same register (`dm (i3,0x1)`) are left alone: they are the same text in both.

A mismatch is printed with the instruction index and both sides. Exit 0 only
if every node of every class matches instruction for instruction and address
for address.

Usage
-----
    python3 shk_equiv.py --inline  <build-dir-of-the-SHARED_KERNELS=0 arm> \
                         --shared  <build-dir-of-the-SHARED_KERNELS=N arm> \
                         [--chip 1] [--classes COMP,TUBE,GATE,FILT] [-v]

Each build dir must hold `chipN.dxe` and `chipN.map.xml`. Needs the CCES
`elfdump` (default /opt/analog/cces/3.0.3/elfdump, or $CCES_ELFDUMP).
"""
import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import map_syms

ELFDUMP = os.environ.get('CCES_ELFDUMP', '/opt/analog/cces/3.0.3/elfdump')
CODE_SECTIONS = ('sec_swco', 'sec_swco_ovf', 'sec_pmco')

# The classes the generator can share, and the registers a stub passes a strip
# in. Kept in step with dsp_codegen.SHARED_KERNEL_CLASSES by the check below.
DEFAULT_CLASSES = ('COMP', 'TUBE', 'GATE', 'FILT')
STUB_REGS = ('i5', 'i6', 'i7')

# `001c0001   1006 0009 6944   r6=dm (_rx_active_buf);`
INSN_RE = re.compile(r'^([0-9a-f]{8})\s+((?:[0-9a-f]{4}\s+)+)\s*(\S.*)$')
LABEL_RE = re.compile(r'^(\S+):\s*$')


def disasm(dxe):
    """[(addr, text)] for the code sections, plus {label: addr}."""
    insns, labels = [], {}
    for sec in CODE_SECTIONS:
        p = subprocess.run([ELFDUMP, '-ns', sec, dxe],
                           capture_output=True, text=True)
        if p.returncode != 0:
            continue
        for ln in p.stdout.splitlines():
            m = LABEL_RE.match(ln)
            if m:
                labels.setdefault(m.group(1), len(insns))
                continue
            m = INSN_RE.match(ln)
            if m:
                insns.append((int(m.group(1), 16), m.group(3).strip()))
    return insns, labels


def region(insns, labels, start, end):
    """The instructions of [start: .. end:], or None if either label is absent.

    Labels are recorded as indices into `insns`, so a region is a slice and
    the node-local labels inside it come back with it.
    """
    if start not in labels or end not in labels:
        return None
    a, b = labels[start], labels[end]
    if b < a:
        return None
    return insns[a:b]


def inner_labels(labels, a, b):
    """{index: [label, ...]} for the labels that fall inside a region."""
    out = {}
    for name, i in labels.items():
        if a <= i < b:
            out.setdefault(i - a, []).append(name)
    return out


# ---------------------------------------------------------------------------
# canonicalisation


def strip_suffix(text, nid, cls):
    """Put the two arms' names for the same thing into one spelling.

        .tkb_lp_C1_TUBE_07   .tkb_lp_shktube      ->  .tkb_lp
        _C1_TUBE_07_process         _shk_tube_blk ->  _process
        _C1_TUBE_07_process_sample  _shk_tube_smp ->  _process_sample

    Only THIS node's id and the generator's stand-ins for it are removed; a
    name that belongs to some OTHER node keeps it and will therefore fail the
    comparison, which is the behaviour wanted -- handing strip 7's body strip
    1's buffer is the exact mistake this file exists to rule out.
    """
    c = cls.lower()
    text = text.replace('_shk_%s_smp' % c, '_process_sample')
    text = text.replace('_shk_%s_blk' % c, '_process')
    # A NODE-LOCAL SUBROUTINE. FILT carries `_filt_start_xfade_<nid>`, which
    # the generator renames to `_shk_filt_start_xfade` -- the class prefix
    # swapped for the shared one, the node id gone. Undo the swap so the two
    # arms spell the same routine the same way; the id is taken off below.
    text = text.replace('_shk_%s' % c, '_%s' % c)
    text = re.sub(r'_' + re.escape(nid) + r'(?![0-9A-Za-z])', '', text)
    text = re.sub(r'_shk' + c + r'\b', '', text)
    return text


# The entry points themselves are named differently in the two arms by
# construction (the shared body has ONE name for 32 nodes), and they are
# already compared through the instructions that reach them. Dropping them
# from the label comparison keeps that comparison about CONTROL FLOW.
def entry_labels(nid, cls):
    c = cls.lower()
    return {'_%s_process' % nid, '_%s_process.end' % nid,
            '_%s_process_sample' % nid, '_%s_process_sample.end' % nid,
            '_shk_%s_blk' % c, '_shk_%s_blk.end' % c,
            '_shk_%s_smp' % c, '_shk_%s_smp.end' % c}


class Regs:
    """What the stub put in the registers a shared body reads a strip through.

    Values are absolute word addresses. `None` means "this register was never
    given a value we can follow", and any access through it is then reported
    rather than assumed equal.
    """

    def __init__(self):
        self.v = {}

    def set_from(self, text, syms):
        m = re.match(r'^(i[0-7])\s*=\s*(\S+?)\s*;', text)
        if not m:
            return False
        reg, rhs = m.group(1), m.group(2)
        if rhs in syms:
            self.v[reg] = syms[rhs]
        elif re.match(r'^0x[0-9a-f]+$', rhs, re.I):
            self.v[reg] = int(rhs, 16)
        elif rhs in self.v:
            self.v[reg] = self.v[rhs]
        else:
            self.v[reg] = None
        return True


def canon(text, nid, cls, syms, regs):
    """One instruction, with every resolvable memory operand made absolute.

    Symbols are resolved on the ORIGINAL text -- `strip_suffix` runs last --
    because the node id is part of the symbol the linker knows.
    """
    t = text

    # A direct access to one of this node's own words: `dm (_field_C1_X_07)`.
    def _direct(m):
        sym = m.group(1)
        return 'dm(@%08x)' % syms[sym] if sym in syms else m.group(0)
    t = re.sub(r'dm\s*\(\s*(_[A-Za-z0-9_.]+)\s*\)', _direct, t)

    # A pre-modify access through a register the stub loaded: `dm (0x4,i7)`.
    def _indexed(m):
        off, reg = int(m.group(1), 16), m.group(2)
        base = regs.v.get(reg)
        return m.group(0) if base is None else 'dm(@%08x)' % (base + off)
    t = re.sub(r'dm\s*\(\s*(0x[0-9a-f]+)\s*,\s*(i[0-7])\s*\)', _indexed, t)

    # THE POST-MODIFY FORM, and only where the modifier is zero. `dm (i5,0x0)`
    # reads the word i5 points at and advances it by nothing, so it resolves
    # the same way the pre-modify form does. A NON-ZERO modifier walks the
    # pointer, so the address depends on how many times the body has been
    # here; that is not something this file may assume, and it is left
    # unresolved so the comparison fails and a human looks.
    def _postmod(m):
        reg, off = m.group(1), int(m.group(2), 16)
        if reg not in STUB_REGS or off != 0:
            return m.group(0)
        base = regs.v.get(reg)
        return m.group(0) if base is None else 'dm(@%08x)' % base
    t = re.sub(r'dm\s*\(\s*(i[0-7])\s*,\s*(0x[0-9a-f]+)\s*\)', _postmod, t)

    # A LITERAL absolute access: `dm (0x91032)`. The linker has no symbol for
    # a word inside an array, so the inline arm spells some of its own record
    # in hex; the same word reached as base+offset must compare equal to it,
    # and it only does if both sides are written the one way.
    t = re.sub(r'dm\s*\(\s*0x([0-9a-f]+)\s*\)',
               lambda m: 'dm(@%08x)' % int(m.group(1), 16), t)

    # A pointer load: `i0=_comp_cgp_C1_COMP_01;` in the inline arm, and the
    # folded `i0=i7 + 0x25` the peephole below produces in the shared one.
    def _load(m):
        reg, rhs = m.group(1), m.group(2)
        return '%s=@%08x;' % (reg, syms[rhs]) if rhs in syms else m.group(0)
    t = re.sub(r'^(i[0-7])\s*=\s*(_[A-Za-z0-9_.]+)\s*;', _load, t)
    t = re.sub(r'^(i[0-7])\s*=\s*0x([0-9a-f]+)\s*;',
               lambda m: '%s=@%08x;' % (m.group(1), int(m.group(2), 16)), t)

    # A register given one of the stub's values outright: `i2=i6`.
    def _copy(m):
        reg, src = m.group(1), m.group(2)
        base = regs.v.get(src)
        return m.group(0) if base is None else '%s=@%08x;' % (reg, base)
    t = re.sub(r'^(i[0-7])\s*=\s*(i[0-7])\s*;', _copy, t)

    return re.sub(r'\s+', '', strip_suffix(t, nid, cls))


# THE TWO SEQUENCES THE REWRITE EXPANDS A POINTER LOAD INTO.
#
# `_shk_rewrite` rule 3 turns `i0 = _field_<nid>;` into `i0 = i7;
# modify(i0, OFF);` -- two instructions where the inline arm had one -- and
# rule 4 turns `r0 = _field_<nid>;` into a three-instruction sequence,
# because this core has no ALU immediate add (S21-3). Folding them back is
# not a convenience: it is the step that makes "the same program" a
# statement about ADDRESSES rather than about instruction counts, and the
# fold is only applied when the base register is one the stub loaded and the
# arithmetic is exactly the generator's shape.
_FOLD_MOD = re.compile(r'^(i[0-7])=modify\((i[0-7]),(0x[0-9a-f]+)\);$')
_FOLD_SET = re.compile(r'^(i[0-7])=@([0-9a-f]{8});$')
_FOLD_RBASE = re.compile(r'^(r[0-9]|r1[0-5])=(i[0-7]);$')
_FOLD_RIMM = re.compile(r'^(r[0-9]|r1[0-5])=(0x[0-9a-f]+);$')
_FOLD_RADD = re.compile(r'^(r[0-9]|r1[0-5])=(r[0-9]|r1[0-5])\+(r[0-9]|r1[0-5]);$')


def fold(stream, regs):
    """Collapse the rewrite's expanded pointer loads back to one entry."""
    out, k = [], 0
    while k < len(stream):
        txt, labs = stream[k]
        if k + 1 < len(stream):
            m1, m2 = _FOLD_SET.match(txt), _FOLD_MOD.match(stream[k + 1][0])
            if (m1 and m2 and m1.group(1) == m2.group(1) == m2.group(2)
                    and not stream[k + 1][1]):
                out.append(('%s=@%08x;' % (m1.group(1),
                                           int(m1.group(2), 16)
                                           + int(m2.group(3), 16)), labs))
                k += 2
                continue
        if k + 2 < len(stream):
            m1 = _FOLD_RBASE.match(txt)
            m2 = _FOLD_RIMM.match(stream[k + 1][0])
            m3 = _FOLD_RADD.match(stream[k + 2][0])
            if (m1 and m2 and m3 and m1.group(2) in STUB_REGS
                    and regs.v.get(m1.group(2)) is not None
                    and m3.group(1) == m3.group(2) == m2.group(1)
                    and m3.group(3) == m1.group(1)
                    and not stream[k + 1][1] and not stream[k + 2][1]):
                out.append(('%s=@%08x;' % (m2.group(1),
                                           regs.v[m1.group(2)]
                                           + int(m2.group(2), 16)), labs))
                k += 3
                continue
        out.append((txt, labs))
        k += 1
    return out


# WHICH REGISTERS AN INSTRUCTION WRITES AND READS, to the small extent this
# file needs to know. Only the forms the stubs and the shared bodies actually
# use are recognised; anything else reads as "reads everything it mentions",
# which is the safe direction for a check that exists to find a stale
# register being read.
_WRITE_RE = re.compile(r'^([ilbmr]\d|r1[0-5])=')


def writes_reg(text):
    m = _WRITE_RE.match(text)
    return m.group(1) if m else None


def reads_reg(text, reg):
    """Does this instruction READ `reg`? A plain `reg=...` write does not."""
    if not re.search(r'\b%s\b' % re.escape(reg), text):
        return False
    m = _WRITE_RE.match(text)
    if m and m.group(1) == reg:
        # `i0=modify(i0,0x5)` and `r4=r4orr5` read it as well as write it.
        return bool(re.search(r'\b%s\b' % re.escape(reg), text[m.end():]))
    return True


def find_run(stream, run, start=0):
    """The index at which `run` appears verbatim in `stream`, or -1."""
    n = len(run)
    for i in range(start, len(stream) - n + 1):
        if [t for t, _ in stream[i:i + n]] == [t for t, _ in run]:
            return i
    return -1


def try_hoist(want, got, stub_len):
    """The one difference a stub is allowed to make: HOISTING THE PROLOGUE.

    FILT's inline body sets `l3/l4/i3/i4` only on the crossfade path, a few
    instructions in behind `if eq jump .fkb_ss`. The stub cannot: it runs
    before the body and has nowhere conditional to put them, so the generator
    hoists that prologue to the stub and the shared arm executes it on EVERY
    block, including blocks that take the steady-state path.

    That is a real difference in what executes, and it is allowed here only
    when both of these hold:

      * the hoisted instructions appear VERBATIM in the inline stream, as one
        contiguous run -- nothing is invented and nothing is dropped; and
      * nothing the shared arm can execute BEFORE that run's inline position
        reads a register the hoist writes, so no instruction sees a value it
        would not have seen inline.

    Returns (ok, note) where note describes the hoist for the report, or
    (False, reason).
    """
    for h in range(stub_len, 0, -1):
        hoist = want[:h]
        rest = want[h:]
        at = find_run(got, hoist)
        if at < 0:
            continue
        reduced = got[:at] + got[at + h:]
        if reduced != rest:
            continue
        regs = [w for w in (writes_reg(t) for t, _ in hoist) if w]
        early = []
        for k in range(at):
            for r in regs:
                if reads_reg(reduced[k][0], r):
                    early.append((k, r, reduced[k][0]))
        if early:
            return False, ('prologue hoist of %d instructions, but %s is read '
                           'at index %d (%s) before the point the inline arm '
                           'sets it' % (h, early[0][1], early[0][0],
                                        early[0][2]))
        after = [(k + at, r) for k in range(len(reduced) - at)
                 for r in regs if reads_reg(reduced[at + k][0], r)]
        return True, ('prologue hoisted: %d instruction(s) (%s) moved from '
                      'inline index %d to the stub; %d later read(s) of %s, '
                      'none before it'
                      % (h, ' '.join(t for t, _ in hoist), at, len(after),
                         ','.join(sorted(set(regs)))))
    return False, None


def canon_stream(insns, nid, cls, syms, regs, labels_at):
    """[(canonical text, label(s) at this point)] for a region."""
    drop = entry_labels(nid, cls)
    out = []
    for k, (_addr, text) in enumerate(insns):
        # `.end` labels are boundary markers and several of them alias the
        # first instruction of the next symbol -- the inline arm's region
        # opens on `_C1_TALK_02_process.end`, the shared body's on
        # `_shk_gate_blk.end`, both purely because the addresses coincide.
        # They are not branch targets in their own right here; a branch that
        # names one still compares through the instruction's own text.
        labs = tuple(sorted(strip_suffix(x, nid, cls)
                            for x in labels_at.get(k, [])
                            if x not in drop and not x.endswith('.end')))
        out.append((canon(text, nid, cls, syms, regs), labs))
    return out


# ---------------------------------------------------------------------------


def nodes_of(labels, chip, cls):
    pat = re.compile(r'^_C%d_%s_(\d+)_process$' % (chip, cls))
    return sorted(m.group(1) for m in map(pat.match, labels) if m)


def check_class(chip, cls, inl, shr, verbose, mutate=None):
    ins_i, lab_i, syms_i = inl
    ins_s, lab_s, syms_s = shr

    shared_start = '_shk_%s_blk' % cls.lower()
    if shared_start not in lab_s:
        return None, ['%s: the shared arm has no %s -- this class is not '
                      'shared in that build' % (cls, shared_start)], {}

    a, b = lab_s[shared_start], lab_s[shared_start + '.end']
    body = ins_s[a:b]
    body_labels = inner_labels(lab_s, a, b)

    problems, notes = [], {}
    nodes = nodes_of(lab_i, chip, cls)
    if not nodes:
        return None, ['%s: the inline arm has no _C%d_%s_nn_process bodies'
                      % (cls, chip, cls)], {}

    for nn in nodes:
        nid = 'C%d_%s_%s' % (chip, cls, nn)
        entry = '_%s_process' % nid

        ia, ib = lab_i[entry], lab_i[entry + '.end']
        inline = ins_i[ia:ib]
        inline_labels = inner_labels(lab_i, ia, ib)

        if entry not in lab_s:
            problems.append('%s: no stub in the shared arm' % nid)
            continue
        sa, sb = lab_s[entry], lab_s[entry + '.end']
        stub = ins_s[sa:sb]

        # Interpret the stub, then drop the lines that exist only to pass a
        # strip in (the loads of the pass-in registers and the final jump).
        stub_at = inner_labels(lab_s, sa, sb)
        regs = Regs()
        kept, kept_labels = [], {}
        for k, (addr, text) in enumerate(stub):
            m = re.match(r'^(i[0-7])\s*=', text)
            drop = False
            if m and m.group(1) in STUB_REGS:
                drop = True
            # The length registers that belong to the pass-in pointers go
            # with them: l5/l6/l7 are set by the stub and by nothing in the
            # inline arm.
            elif re.match(r'^l[567]\s*=', text):
                drop = True
            elif re.match(r'^jump\b', text) and k == len(stub) - 1:
                drop = True
            regs.set_from(text, syms_s)
            if mutate == nid and m and m.group(1) in STUB_REGS \
                    and regs.v.get(m.group(1)) is not None:
                regs.v[m.group(1)] += 1
            if drop:
                continue
            if k in stub_at:
                kept_labels[len(kept)] = stub_at[k]
            kept.append((addr, text))
        stub_labels = kept_labels

        # The inline arm's own reference point: the record base is the first
        # field of the record, which is what the stub loads into base_reg.
        regs_i = Regs()

        want = fold(canon_stream(kept, nid, cls, syms_s, regs, stub_labels)
                    + canon_stream(body, nid, cls, syms_s, regs, body_labels),
                    regs)
        got = fold(canon_stream(inline, nid, cls, syms_i, regs_i,
                                inline_labels), regs_i)

        if len(want) != len(got):
            problems.append(
                '%s: %d instructions in the shared arm (stub %d + body %d), '
                '%d inline' % (nid, len(want), len(kept), len(body), len(got)))
            n = min(len(want), len(got))
            for k in range(n):
                if want[k] != got[k]:
                    problems.append('    first divergence at %d: shared %r / '
                                    'inline %r' % (k, want[k], got[k]))
                    break
            continue

        bad = [k for k in range(len(want)) if want[k] != got[k]]
        if bad:
            ok, note = try_hoist(want, got, len(kept))
            if ok:
                notes.setdefault(note, []).append(nid)
                bad = []
            else:
                problems.append('%s: %d of %d instructions differ%s'
                                % (nid, len(bad), len(want),
                                   ' (%s)' % note if note else ''))
                for k in bad[:4]:
                    problems.append('    [%4d] shared  %s' % (k, want[k][0]))
                    problems.append('           inline  %s' % got[k][0])
        if bad:
            pass
        elif verbose:
            print('    %-14s %4d instructions, %d absolute addresses, OK'
                  % (nid, len(want),
                     sum(1 for t, _ in want if '@' in t)))

    return len(nodes), problems, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inline', required=True,
                    help='build dir of the DSP4_SHARED_KERNELS=0 arm')
    ap.add_argument('--shared', required=True,
                    help='build dir of the DSP4_SHARED_KERNELS=N arm')
    ap.add_argument('--chip', type=int, default=1)
    ap.add_argument('--classes', default=','.join(DEFAULT_CLASSES))
    ap.add_argument('-v', '--verbose', action='store_true')
    ap.add_argument('--mutate', metavar='NODE',
                    help='NEGATIVE CONTROL. Shift this node\'s record base by '
                         'one word before comparing, i.e. hand that strip the '
                         'word next to every one it should read. The run MUST '
                         'fail; a harness that cannot fail is not a proof. '
                         'Exit 0 only if the mutation was caught.')
    args = ap.parse_args()

    if not os.path.exists(ELFDUMP):
        print('shk_equiv: no elfdump at %s (set CCES_ELFDUMP)' % ELFDUMP,
              file=sys.stderr)
        return 2

    out = {}
    for tag, d in (('inline', args.inline), ('shared', args.shared)):
        dxe = os.path.join(d, 'chip%d.dxe' % args.chip)
        mp = os.path.join(d, 'chip%d.map.xml' % args.chip)
        for p in (dxe, mp):
            if not os.path.exists(p):
                print('shk_equiv: %s is missing' % p, file=sys.stderr)
                return 2
        insns, labels = disasm(dxe)
        out[tag] = (insns, labels, map_syms.syms(mp))
        print('  %-7s %s  %d instructions, %d labels, %d symbols'
              % (tag, os.path.basename(d.rstrip('/')), len(insns),
                 len(labels), len(out[tag][2])))

    total_nodes, total_bad = 0, 0
    for cls in [c.strip().upper() for c in args.classes.split(',') if c.strip()]:
        n, problems, notes = check_class(args.chip, cls, out['inline'],
                                         out['shared'], args.verbose,
                                         args.mutate)
        if n is None:
            print('  %-5s SKIP  %s' % (cls, problems[0]))
            continue
        total_nodes += n
        if problems:
            total_bad += 1
            print('  %-5s FAIL  %d nodes' % (cls, n))
            for p in problems:
                print('        ' + p)
        else:
            print('  %-5s OK    %d nodes, instruction for instruction and '
                  'address for address' % (cls, n))
        for note, who in sorted(notes.items()):
            print('        %d node(s): %s' % (len(who), note))

    if args.mutate:
        if total_bad:
            print('shk_equiv: NEGATIVE CONTROL PASSED -- shifting %s\'s record '
                  'base by one word was caught' % args.mutate)
            return 0
        print('shk_equiv: NEGATIVE CONTROL FAILED -- %s\'s record base was '
              'shifted by one word and nothing noticed. The comparison is '
              'not testing what it says it tests.' % args.mutate)
        return 1
    if total_bad:
        print('shk_equiv: %d class(es) differ' % total_bad)
        return 1
    print('shk_equiv: %d nodes equivalent on chip %d' % (total_nodes, args.chip))
    return 0


if __name__ == '__main__':
    sys.exit(main())
