#!/usr/bin/env python3
"""gap_list.py — the product-generic gap list: every master cell a
product's generated DSP graph does not implement, in one of four named
buckets.

`defs/gen/matrix/<p>-mx-master.csv` is the product's full master cell
list (template rows with `[a-b]` instance ranges). `defs/products/<p>/
dsp.csv` says which of those cells reach a DSP address; `defs/products/
<p>/dsp-unmapped.csv` says why every other one does not, with a `Class`
column. Neither file says whether an ADDRESSED cell is actually served
by the running kernel — a cell can sit in dsp.csv, own a real chip/page/
address, and still be INERT: nothing the generator emitted ever reads or
writes it (D38, tracked by `wire_contract.py --inert`). That is a
second, disjoint way for a cell to be a gap, and this tool is the one
place the two are merged.

FOUR BUCKETS, no others (S87 dispatch):

    dsp-missing      a DSP function this product defines and the graph
                     does not build -- either dsp-unmapped's own
                     `no-graph-node` class, or a cell dsp.csv DOES
                     address whose dispatch target is INERT. Code it.
    needs-definition cannot be implemented without a PW ruling or a
                     manual definition (`s1-2-no-behaviour`, and
                     `unbacked-meter` if that class occurs). LIST ONLY:
                     this tool never invents behaviour for these.
    not-dsp          app or MCU side; the DSP has no word for it by
                     ruling (`mcu-only`, `control-plane`, `host-managed`,
                     `surface-state`, `label`, `hardware-control`).
    shelved-matrix   the cell's family (name with instance digits
                     stripped) is one of ChanMatrixOn, ChanMatrixSend,
                     MatrixLevel, MatrixMute, MatrixName -- the
                     in-progress matrix-bus rework in defs. This bucket
                     WINS over the other three when it applies. Leave
                     these alone.

WHAT THIS REFUSES TO GUESS. A Class this tool does not recognise, a
master cell in neither dsp.csv nor dsp-unmapped.csv, or one in both --
each is a generator or contract defect, not a shape to infer a bucket
for, so each is a hard failure naming the offending cell and class
rather than a silent default (no-fallback policy, CLAUDE.md). The
`needs-definition` bucket is listed, never resolved: this tool writes
no behaviour for a cell it cannot address.

INERT ADDRESSES WITH NO MASTER CELL are D38 dispatch slots the wire
join could not attach any master cell name to (continuation words in a
multi-word coefficient block, and — for D24 specifically — cross-product
dispatch slots the D24 master never defines, e.g. AUX_AFB_09..12 /
AUX_DLY_09..12). They are not in the product's cell set, so they are
excluded from the gap list entirely, but they are counted and reported
separately: a shrinking or growing count there is still a finding, even
though it never appears on the cell CSV.

CROSS-CHECK. expanded master cell count MUST equal implemented count
plus the sum of the four buckets. This is asserted, printed either way,
and a discrepancy is reported explicitly rather than hidden.

Usage:
    gap_list.py --product d24
    gap_list.py --product d24 --table MW/D24/DSP/s87/data/gap-table.md
    gap_list.py --product d24 --csv MW/D24/DSP/s87/data/gap-cells-d24.csv
    gap_list.py --product d32          # product-generic smoke test
"""
import argparse
import csv
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from wire_contract import build, expand_pattern            # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFS = os.path.join(ROOT, 'defs')

NOT_DSP_CLASSES = {
    'mcu-only', 'control-plane', 'host-managed', 'surface-state',
    'label', 'hardware-control',
}
NEEDS_DEFINITION_CLASSES = {'s1-2-no-behaviour', 'unbacked-meter'}
DSP_MISSING_CLASSES = {'no-graph-node'}
KNOWN_CLASSES = NOT_DSP_CLASSES | NEEDS_DEFINITION_CLASSES | DSP_MISSING_CLASSES

SHELVED_FAMILIES = {
    'ChanMatrixOn', 'ChanMatrixSend', 'MatrixLevel', 'MatrixMute', 'MatrixName',
}

# ---------------------------------------------------------------------------
# HELD ON A RULING -- the split inside `no-graph-node` that decides whether a
# gap is work or a question
# ---------------------------------------------------------------------------
#
# WHY THIS TABLE EXISTS. `no-graph-node` means one thing to the generator --
# "this product defines a DSP function and the graph does not build it" -- and
# two quite different things to whoever has to close it. For some families the
# arithmetic is the whole of what is missing and a session can write it. For
# others `defs` itself records, in the cell's own Reason text, that the
# BEHAVIOUR is not decided: what the function does, where it sits, or how many
# instances it has. Coding one of those means inventing a definition, which the
# S87 dispatch forbids in terms ("the 30 no-behaviour cells and the comp GR
# meter word need PW or manual definitions, never invented") and which earlier
# sessions twice went to build and rightly stopped short of (S26, for NoiseDest
# and TalkDest).
#
# Counting both kinds as "code it" makes the work list roughly three times its
# real size and hides the only thing PW can act on, so the held families are
# named HERE, each with the ruling or open question it waits on, and land in
# `needs-definition` beside the s1-2 cells. The citation is quoted from the
# family's own Reason text in `defs/products/<p>/dsp-unmapped.csv` -- this table
# selects and attributes, it does not decide. Closing one is a defs change,
# after which its row here must go.
#
# IT CANNOT ROT SILENTLY: a family named here that is no longer a gap in the
# product being listed is a hard failure, not a stale comment.
HELD_ON_A_RULING = {
    'ChanAntiClip': (
        'PW, not ruled — defs: "Where it sits in the strip (post-fader, '
        'before the bus?) and whether it is a limiter or a gain-ride are '
        'both PW\'s, and neither is ruled" (S25 gate 4). The arithmetic is '
        'already in the graph twice over; the DECISION is what is missing.'),
    'NoiseDest': (
        'PW 2026-09-06 — defs, via d24-skin-cell-map.csv menu5/6 and '
        'menu5/8: "Rtg retired from all cells — Noise assign needs a NEW '
        'function definition in the master; never reuse Rtg". The Dest '
        'cells are not the vehicle the product is waiting for.'),
    'TalkDest': (
        'the master, not invented — defs names a COUNT and no destination, '
        'and d24-skin-cell-map.csv menu5/2 records a "RANGE CONFLICT: vocab '
        'Talk Rtg[1-3] vs 9 targets — extend to [1-9]", so the number of '
        'crosspoints is contradicted by the product as well as their targets.'),
    'MainCtrDelay': ('PW — defs: the 250 ms the master asks for is 48,000 '
                     'bytes of chip-2 L2 per output, 192,000 for all four, '
                     '"It FITS and it is still PW\'s call" (S24).'),
    'MainLDelay': ('PW — see MainCtrDelay: one of the four post-crossover '
                   'output delays held on the same memory ruling (S24).'),
    'MainRDelay': ('PW — see MainCtrDelay: one of the four post-crossover '
                   'output delays held on the same memory ruling (S24).'),
    'MainSubDelay': ('PW — see MainCtrDelay: one of the four post-crossover '
                     'output delays held on the same memory ruling (S24).'),
    'MainOutMode': (
        'open question Q2 — defs: "C2_MAIN_XOVER feeds all four outputs '
        'unconditionally and no word selects output 3\'s source". Which '
        'source output 3 carries is the LCR product question itself.'),
    'RtaOn': (
        'PW — defs: the analyser is priced by construction and "is not '
        'built: the source select below has no ruling behind it, and a meter '
        'family that reads the wrong point is worse than none". The chip-1 '
        'filterbank code EXISTS behind DSP4_RTA; what is unruled is where it '
        'listens.'),
    'RtaSrc': (
        'PW — defs: "The master names three source kinds and not which '
        'instances, so the pick list is a product question and is carried, '
        'not guessed."'),
}

BUCKETS = ('dsp-missing', 'needs-definition', 'not-dsp', 'shelved-matrix')


# ---------------------------------------------------------------------------
# THE OFFSET-REACH HOLE, CLOSED FOR THE SHARED-KERNEL RECORD CLASSES
# ---------------------------------------------------------------------------
#
# `wire_contract`'s inert test is per SYMBOL: an address is INERT when no
# emitted line names its dispatch target. That is the right test for a
# per-node body, and it is BLIND to the shared kernels. Under
# DSP4_SHARED_KERNELS a node's parameter block is reached from ONE
# address -- the stub loads the record base into i7 and the single shared
# body indexes it as `dm(i7, SHK_<CLASS>_OFF_<field>)` -- so every word
# after the base is classed OFFSET_REACH, "not proven live, but not
# claimable as dead either", and 518 of D24's addresses sit there.
#
# For these classes the question IS decidable, and from the source rather
# than by argument: the layout constants are #defined as a chain of
# `previous + 1`, so a field whose constant appears ONLY in #define lines
# is a field no instruction of the shared body can reach. Resolving that
# turns 264 D24 cells from "uncertain" into a proven gap -- among them the
# channel compressor's whole sidechain (type, key, detector source, EQ
# position, limiter mode and the HPF/LPF/Q filter) on all 24 strips, which
# the symbol-level test could only see on chip 2's eight bus compressors.
#
# THIS UNDER-REPORTS IN THE SAME DIRECTION AS THE TEST IT EXTENDS. It
# resolves the classes whose record layout is declared this way and nothing
# else; every other OFFSET_REACH address stays uncertain and is counted and
# reported as such, never folded into a bucket.
SHK_FILE = os.path.join(ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'src', 'chip1',
                        'shared_kernels.asm')
SHK_CLASSES = {'COMP': '_comp_', 'GATE': '_gate_'}


def shk_unread_fields():
    """{('COMP','filter_on'), ...} -- the shared-kernel record fields whose
    layout constant is declared and never named by an instruction.

    Returns an empty set (and says so to the caller) if the file is gone,
    rather than silently reporting that nothing is unread."""
    if not os.path.exists(SHK_FILE):
        return None
    declared, used = set(), set()
    pat = re.compile(r'SHK_(COMP|GATE)_OFF_([A-Za-z0-9_]+)')
    for raw in open(SHK_FILE, errors='replace'):
        line = raw.split('/*')[0].split('//')[0].strip()
        if not line:
            continue
        m = re.match(r'#define\s+SHK_(COMP|GATE)_OFF_([A-Za-z0-9_]+)', line)
        if m:
            declared.add((m.group(1), m.group(2)))
            continue        # the rest of a #define line is LAYOUT, not a use
        for cls, fld in pat.findall(line):
            used.add((cls, fld))
    return declared - used


def shk_unread_symbol(symbol, unread):
    """Is this dispatch target a shared-kernel record field no instruction
    reaches? `_comp_filter_on_C1_COMP_01` -> ('COMP','comp_filter_on')."""
    if not unread:
        return None
    for cls, prefix in SHK_CLASSES.items():
        if not symbol.startswith(prefix):
            continue
        # the field name is everything between the leading _ and the node id
        m = re.match(r'_((?:comp|gate)_[a-z0-9_]+?)_(C[12]_[A-Z0-9_]+)$', symbol)
        if not m:
            continue
        field = m.group(1)
        if (cls, field) in unread:
            return field
    return None


def family(cell):
    """Aux001AntiFbCtrlOn001 -> AuxAntiFbCtrlOn. Same rule as
    wire_contract.cell_family's name-shape key: strip every digit."""
    return re.sub(r'\d+', '', cell)


def _data_rows(path):
    """A defs CSV with a '#'-commented preamble: the header and data
    rows only, in DictReader form."""
    lines = []
    with open(path, newline='', encoding='utf-8') as fh:
        for line in fh:
            if line.startswith('#') or not line.strip():
                continue
            lines.append(line)
    return list(csv.DictReader(lines))


def load_master(product):
    path = os.path.join(DEFS, 'gen', 'matrix', f'{product.lower()}-mx-master.csv')
    return _data_rows(path)


def load_dsp(product):
    path = os.path.join(DEFS, 'products', product.lower(), 'dsp.csv')
    return _data_rows(path)


def load_unmapped(product):
    path = os.path.join(DEFS, 'products', product.lower(), 'dsp-unmapped.csv')
    return _data_rows(path)


def expand_master(product):
    """Every concrete cell name the master's template rows stand for,
    plus the family -> master Notes text a family carries (joined, on
    the rare family that spans more than one template row with
    different wording)."""
    cells = set()
    fam_notes = {}
    for r in load_master(product):
        instances = expand_pattern(r['_Cell'])
        note = (r.get('Notes') or '').strip()
        for c in instances:
            if c in cells:
                raise SystemExit(
                    f"gap_list: master cell {c!r} is produced by more than one "
                    f"template row in {product}-mx-master.csv -- refusing to "
                    f"guess which row owns it")
            cells.add(c)
        fam = family(instances[0])
        if note:
            fam_notes.setdefault(fam, set()).add(note)
    return cells, {f: '; '.join(sorted(n)) for f, n in fam_notes.items()}


def classify(product):
    """Returns a dict with everything --table/--csv need:
        master_total, implemented, gaps (list of row dicts),
        no_cell_inert (count), bucket_counts.
    """
    master_cells, fam_notes = expand_master(product)
    dsp_rows = {r['_Cell']: r for r in load_dsp(product)}
    unmapped_rows = {r['_Cell']: r for r in load_unmapped(product)}

    overlap = set(dsp_rows) & set(unmapped_rows)
    if overlap:
        raise SystemExit(
            f"gap_list: {len(overlap)} cell(s) appear in BOTH dsp.csv and "
            f"dsp-unmapped.csv (e.g. {sorted(overlap)[0]}) -- the generator "
            f"contradicted itself, this tool will not pick a side")

    accounted = set(dsp_rows) | set(unmapped_rows)
    missing = master_cells - accounted
    if missing:
        raise SystemExit(
            f"gap_list: {len(missing)} master cell(s) are in neither dsp.csv "
            f"nor dsp-unmapped.csv (e.g. {sorted(missing)[0]}) -- a family "
            f"the generator has not accounted for; fix the generator, this "
            f"tool will not guess a bucket for it")
    extra = accounted - master_cells
    if extra:
        raise SystemExit(
            f"gap_list: {len(extra)} cell(s) named in dsp.csv/dsp-unmapped.csv "
            f"are not produced by any master template row (e.g. "
            f"{sorted(extra)[0]})")

    plan, orphans = build(product)
    if orphans:
        raise SystemExit(
            f"gap_list: {len(orphans)} master cell(s) carry a _matrix.csv "
            f"address outside the dispatch table (e.g. {orphans[0]}) -- a "
            f"wiring defect wire_contract found, not a gap this tool sorts")

    # The inert set, PLUS the offset-reach addresses the shared-kernel
    # layout proves unreachable. Two provenances, kept apart in the row so
    # the report can say which test caught each one.
    shk_unread = shk_unread_fields()
    if shk_unread is None:
        raise SystemExit(
            f'gap_list: {SHK_FILE} is missing, so the offset-reach addresses '
            f'cannot be resolved and this tool would silently under-report '
            f'the gap by the whole shared-kernel record set. Fix the path.')

    inert_cell_site = {}          # cell -> (chip, addr, symbol, how)
    no_cell_inert = 0
    offset_uncertain = 0
    for e in plan.values():
        how = None
        if e['role'] == 'INERT':
            how = 'symbol inert'
        elif e['role'] == 'OFFSET_REACH':
            fld = shk_unread_symbol(e['symbol'] or '', shk_unread)
            if fld:
                how = 'shared-kernel field %s, never named by an instruction' % fld
            else:
                offset_uncertain += 1
                continue
        else:
            continue
        if not e['cells']:
            if how == 'symbol inert':
                no_cell_inert += 1
            continue
        for c in e['cells']:
            inert_cell_site[c] = (e['chip'], e['addr'], e['symbol'], how)

    gaps = []
    implemented = 0

    for cell, row in dsp_rows.items():
        site = inert_cell_site.get(cell)
        if site is None:
            implemented += 1
            continue
        chip, addr, symbol, how = site
        fam = family(cell)
        if fam in SHELVED_FAMILIES:
            bucket = 'shelved-matrix'
            reason = 'held by the in-progress matrix-bus rework in defs'
            kind = 'address inert'
        else:
            bucket = 'dsp-missing'
            reason = (f'addressed (chip {chip}, 0x{addr:04X}) and NOT SERVED: '
                      f'{how} — a host write lands in DM and no instruction '
                      f'of the running kernel looks at {symbol}')
            kind = ('address inert' if how == 'symbol inert'
                    else 'unread shared-kernel field')
        gaps.append({
            '_Cell': cell, 'Family': fam, 'Bucket': bucket, 'Reason': reason,
            'Class': '', 'DspAddrHex': row.get('DspAddHex', ''),
            'InertSymbol': symbol, 'Notes': fam_notes.get(fam, ''),
            '_gap_kind': kind,
        })

    for cell, row in unmapped_rows.items():
        cls = row['Class']
        if cls not in KNOWN_CLASSES:
            raise SystemExit(
                f"gap_list: {cell} carries Class {cls!r}, which is none of "
                f"the classes this tool knows how to bucket -- new classes "
                f"are adopted intentionally, not guessed at (no-fallback "
                f"policy)")
        fam = family(cell)
        reason = row.get('Reason', '')
        kind = ''
        if fam in SHELVED_FAMILIES:
            bucket = 'shelved-matrix'
        elif cls in DSP_MISSING_CLASSES:
            # THE SPLIT: no address AND no decided behaviour is a question,
            # not a work item. See HELD_ON_A_RULING.
            if fam in HELD_ON_A_RULING:
                bucket = 'needs-definition'
                kind = 'held on a ruling'
                reason = 'HELD ON: ' + HELD_ON_A_RULING[fam] + '  || ' + reason
            else:
                bucket = 'dsp-missing'
                kind = 'no address'
        elif cls in NEEDS_DEFINITION_CLASSES:
            bucket = 'needs-definition'
            kind = 'no behaviour defined'
        else:
            bucket = 'not-dsp'
        gaps.append({
            '_Cell': cell, 'Family': fam, 'Bucket': bucket,
            'Reason': reason, 'Class': cls,
            'DspAddrHex': '', 'InertSymbol': '',
            'Notes': fam_notes.get(fam, ''),
            '_gap_kind': kind,
        })

    bucket_counts = {b: 0 for b in BUCKETS}
    for g in gaps:
        bucket_counts[g['Bucket']] += 1

    # A HELD family THIS PRODUCT DEFINES and that is no longer a gap means
    # the ruling landed and this table did not follow. Fail rather than keep
    # quoting a closed question. A family the product does not define at all
    # is not stale -- a D32 has no centre output, so MainCtrDelay and
    # MainOutMode are simply absent from its master, and scoring that as a
    # landed ruling would make the check fire on the wrong product.
    gap_families = {g['Family'] for g in gaps}
    master_families = {family(c) for c in master_cells}
    stale = sorted(f for f in HELD_ON_A_RULING
                   if f in master_families and f not in gap_families)
    if stale:
        raise SystemExit(
            f"gap_list: HELD_ON_A_RULING names {len(stale)} family/families "
            f"that {product} defines and that are not gaps any more "
            f"({', '.join(stale)}) -- the ruling landed and the table did not "
            f"follow it. Remove the row(s); do not leave a closed question on "
            f"the list.")

    return {
        'master_total': len(master_cells),
        'implemented': implemented,
        'gaps': gaps,
        'no_cell_inert': no_cell_inert,
        'offset_uncertain': offset_uncertain,
        'bucket_counts': bucket_counts,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def per_family_rows(gaps):
    """(family, bucket) -> {count, notes, kinds set}, sorted by bucket then
    by count desc then by family."""
    agg = {}
    for g in gaps:
        key = (g['Family'], g['Bucket'])
        a = agg.setdefault(key, {'count': 0, 'notes': g['Notes'], 'kinds': set()})
        a['count'] += 1
        if g['_gap_kind']:
            a['kinds'].add(g['_gap_kind'])
    order = {b: i for i, b in enumerate(BUCKETS)}
    return sorted(agg.items(), key=lambda kv: (order[kv[0][1]], -kv[1]['count'], kv[0][0]))


def render_table(product, result):
    counts = result['bucket_counts']
    total_gaps = sum(counts.values())
    balance_lhs = result['master_total']
    balance_rhs = result['implemented'] + total_gaps
    balanced = balance_lhs == balance_rhs

    L = [
        f'# {product.upper()} gap table',
        '',
        'AUTO-GENERATED by `tools/dsp/gap_list.py --table`. Do not hand-edit:',
        'edit dsp-unmapped.csv Reason/Class text or the master Notes in',
        '`defs/`, then regenerate.',
        '',
        f'Expanded master cells: **{result["master_total"]}** '
        f'= implemented **{result["implemented"]}** + gaps **{total_gaps}**'
        + ('' if balanced else f'  -- MISMATCH ({balance_lhs} != {balance_rhs})'),
        '',
        f'Inert dispatch addresses with no master cell attached '
        f'(excluded from the cell set, counted here): '
        f'**{result["no_cell_inert"]}**',
        '',
        '## By bucket',
        '',
        '| Bucket | Count |',
        '|---|---|',
    ]
    for b in BUCKETS:
        L.append(f'| {b} | {counts[b]} |')
    L.append(f'| **total gaps** | **{total_gaps}** |')
    L += ['', '## By family', '',
          '| Family | Count | Bucket | Gap | Notes |',
          '|---|---|---|---|---|']
    for (fam, bucket), a in per_family_rows(result['gaps']):
        kind = ' + '.join(sorted(a['kinds'])) if bucket == 'dsp-missing' else '-'
        notes = a['notes'].replace('|', '\\|') or '-'
        L.append(f'| {fam} | {a["count"]} | {bucket} | {kind} | {notes} |')
    L.append('')
    return '\n'.join(L)


def write_csv(path, gaps):
    fields = ['_Cell', 'Family', 'Bucket', 'Reason', 'Class', 'DspAddrHex',
              'InertSymbol', 'Notes']
    rows = sorted(gaps, key=lambda g: (g['Bucket'], g['Family'], g['_Cell']))
    with open(path, 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0],
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--product', required=True,
                     help='lowercase product name, e.g. d24 (matches defs/products/<p>)')
    ap.add_argument('--table', metavar='PATH',
                     help='write the markdown bucket + per-family summary here')
    ap.add_argument('--csv', metavar='PATH',
                     help='write every gap cell, one row each, here')
    args = ap.parse_args()

    result = classify(args.product)
    counts = result['bucket_counts']
    total_gaps = sum(counts.values())
    lhs, rhs = result['master_total'], result['implemented'] + total_gaps

    print(f'  product                         : {args.product}')
    print(f'  expanded master cells           : {lhs}')
    print(f'  implemented                     : {result["implemented"]}')
    for b in BUCKETS:
        print(f'    {b:<17}          : {counts[b]}')
    print(f'  total gaps                      : {total_gaps}')
    if lhs == rhs:
        print(f'  balance check                   : OK ({lhs} == {rhs})')
    else:
        print(f'  balance check                   : MISMATCH '
              f'(master {lhs} != implemented+gaps {rhs})')
    print(f'  inert addresses, no master cell : {result["no_cell_inert"]} '
          f'(excluded from the cell set above)')
    print(f'  offset-reach, STILL UNCERTAIN    : {result["offset_uncertain"]} '
          f'addresses — not claimed either way, so the gap count above is a '
          f'FLOOR')

    if args.table:
        os.makedirs(os.path.dirname(os.path.abspath(args.table)) or '.', exist_ok=True)
        with open(args.table, 'w', encoding='utf-8') as fh:
            fh.write(render_table(args.product, result))
        print(f'\n  wrote {args.table}')

    if args.csv:
        os.makedirs(os.path.dirname(os.path.abspath(args.csv)) or '.', exist_ok=True)
        write_csv(args.csv, result['gaps'])
        print(f'  wrote {args.csv} ({len(result["gaps"])} rows)')


if __name__ == '__main__':
    main()
