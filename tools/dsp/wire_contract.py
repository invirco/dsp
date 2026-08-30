#!/usr/bin/env python3
"""wire_contract.py — the SPI wire contract, assembled from its sources.

The conformance harness needs one table that says, for every address the
DSP will answer on: which master cell(s) name it, what unit the masters
document, what the kernel keeps there, and whether any emitted process
body ever reads it. No single file holds that. This assembles it from
the four that do, and refuses to guess when they disagree.

    MW/<P>/MX/_matrix.csv          master cell -> chip/page/addr, Table,
                                   RampProfile, Type (contract-synced)
    SHARC/src/chip<N>/dsp_params.asm
                                   the DISPATCH TABLE the handler indexes:
                                   address -> DM symbol (or 0 = unmapped),
                                   with the generator's own comment saying
                                   what the kernel keeps there
    docs/contract/wire-units.csv   family -> documented unit + what the
                                   kernel expects (mx26 is SOT)
    docs/contract/<p>-wire-table.csv
                                   the master's cell surface, for the
                                   coverage cross-check: which documented
                                   cells reach the DSP at all

WHY THE DISPATCH TABLE AND NOT ghost_cells. ghost_cells.c is generated
from the same _matrix.csv rows, so checking one against the other proves
only that the generator ran. The dispatch array is what the SPI handler
actually indexes at run time -- it is the only artefact in the tree that
can say an address is unmapped -- so it is the authority here, and a cell
whose _matrix address falls outside it is reported, not assumed dead.

MANY CELLS PER ADDRESS IS NORMAL AND IS ITSELF A FINDING. The EQ and
filter bands hand the host a five- or six-word COEFFICIENT SET at the
band's base address, while the masters document Freq/Gain/Q/Shelf as four
separate cells at that same address. Both facts are true; the join is
many-to-one and this file keeps the whole list rather than picking one.

Usage:
    wire_contract.py --product d32 --plan plan.json
    wire_contract.py --product d32 --coverage        # human summary
"""

import argparse
import csv
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The DSP tree is single-sourced (dsp4-architecture-decisions.md: ONE DSP4
# firmware and ONE address map serve D24 and D32), so the dispatch tables
# always come from the D32 tree whatever product's matrix is being joined.
PARAMS_ASM = {
    1: os.path.join(ROOT, 'MW/D32/DSP/SHARC/src/chip1/dsp_params.asm'),
    2: os.path.join(ROOT, 'MW/D32/DSP/SHARC/src/chip2/dsp_params.asm'),
}
NODES_DIR = {
    1: os.path.join(ROOT, 'MW/D32/DSP/SHARC/src/chip1'),
    2: os.path.join(ROOT, 'MW/D32/DSP/SHARC/src/chip2'),
}
SHARED_SRC = os.path.join(ROOT, 'MW/D32/DSP/SHARC/src')
WIRE_UNITS = os.path.join(ROOT, 'docs/contract/wire-units.csv')


# ---------------------------------------------------------------------------
# The dispatch table
# ---------------------------------------------------------------------------

_DISPATCH_RE = re.compile(
    r'^\s*(\d+|_[A-Za-z0-9_]+(?:\s*\+\s*\d+)?)\s*,?\s*(?:/\*(.*?)\*/)?\s*$')


def parse_dispatch(chip):
    """(addr -> {symbol, offset, comment}) from _spi_dispatch_c<chip>.

    Also returns the parallel stride array. Both are generated as one
    `.var name[N] = a, b, c ...;` initialiser, so the parse is: find the
    declaration, then take one entry per following line until the `;`.
    """
    path = PARAMS_ASM[chip]
    text = open(path).read()
    out = {}
    stride = {}

    def entries(varname):
        m = re.search(r'\.var\s+%s\[(\d+)\]\s*=' % re.escape(varname), text)
        if not m:
            raise SystemExit(f'{path}: no initialiser for {varname}')
        n = int(m.group(1))
        body = text[m.end():]
        end = body.index(';')
        vals = []
        for line in body[:end].splitlines():
            line = line.strip()
            if not line:
                continue
            em = _DISPATCH_RE.match(line)
            if not em:
                raise SystemExit(f'{path}: cannot parse dispatch line {line!r}')
            vals.append((em.group(1), (em.group(2) or '').strip()))
        if len(vals) != n:
            raise SystemExit(
                f'{path}: {varname} declares {n} entries, initialiser has '
                f'{len(vals)} — the parse is wrong, not the file')
        return vals

    for addr, (expr, comment) in enumerate(entries(f'_spi_dispatch_c{chip}')):
        if expr == '0':
            out[addr] = {'symbol': None, 'offset': 0, 'comment': comment}
        else:
            parts = [p.strip() for p in expr.split('+')]
            out[addr] = {'symbol': parts[0],
                         'offset': int(parts[1]) if len(parts) > 1 else 0,
                         'comment': comment}
    for addr, (expr, _c) in enumerate(entries(f'_spi_dispatch_c{chip}_stride')):
        stride[addr] = int(expr) if expr.isdigit() else 0
    return out, stride


# ---------------------------------------------------------------------------
# Static consumption — the D38 instrument
# ---------------------------------------------------------------------------

def _source_files(chip):
    files = []
    ndir = os.path.join(NODES_DIR[chip], 'nodes')
    if os.path.isdir(ndir):
        files += [os.path.join(ndir, f) for f in sorted(os.listdir(ndir))
                  if f.endswith('.asm')]
    for f in sorted(os.listdir(NODES_DIR[chip])):
        if f.endswith('.asm') and f != 'dsp_params.asm':
            files.append(os.path.join(NODES_DIR[chip], f))
    for f in sorted(os.listdir(SHARED_SRC)):
        if f.endswith('.asm'):
            files.append(os.path.join(SHARED_SRC, f))
    lib = os.path.join(SHARED_SRC, 'lib')
    for f in sorted(os.listdir(lib)):
        if f.endswith('.asm'):
            files.append(os.path.join(lib, f))
    return files


# A line that only DECLARES a symbol, or only STORES to it, is not a use.
# Everything else that names it is counted as a use — deliberately
# conservative, so that a symbol this reports as INERT is one no emitted
# line mentions at all except its declaration. Under-reporting inert cells
# is the safe direction for a list that will be published as authoritative.
_DECL_RE = re.compile(r'^\s*\.(?:var|global|extern)\b')
_STORE_ONLY_RE = re.compile(r'^\s*dm\(\s*(_[A-Za-z0-9_]+)[^)]*\)\s*=')


def _var_runs(path):
    """The ordered .var declarations of a file, grouped into contiguous runs.

    Consecutive .var directives occupy consecutive DM words, which is how
    a node reaches a whole parameter block from ONE symbol: C1_MTR_01's
    own comment says it takes the address of _mtr_peak and "reaches the
    rest by offset". A per-symbol reference count calls every one of those
    neighbours unreferenced, which would put a live meter word on an
    inert-cell list. So the runs are tracked, and any declaration that
    follows an address-taken symbol inside the same run is reported as
    OFFSET_REACH -- not proven live, but not claimable as dead either.

    A run ends at a .section directive or at the first instruction line,
    which is where the assembler stops laying out consecutive words.
    """
    runs, cur = [], []
    for raw in open(path, errors='replace'):
        line = raw.split('/*')[0].split('//')[0].strip()
        if not line:
            continue
        if line.startswith('.section') or line.startswith('.segment'):
            if cur:
                runs.append(cur)
            cur = []
            continue
        m = re.match(r'\.var\s+(_[A-Za-z0-9_]+)', line)
        if m:
            cur.append(m.group(1))
            continue
        if line.startswith('.') or line.startswith('#'):
            continue          # .global/.extern/.align/#if — layout unaffected
        if cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return runs


_ADDR_TAKE_RE = re.compile(r'=\s*(_[A-Za-z0-9_]+)\s*;')


def consumption(chip):
    """symbol -> {'read','store','decl','offset_reach'} over emitted sources."""
    use = {}

    def slot(s):
        return use.setdefault(s, {'read': 0, 'store': 0, 'decl': 0,
                                  'offset_reach': 0})

    for path in _source_files(chip):
        taken = set()
        for raw in open(path, errors='replace'):
            line = raw.split('/*')[0].split('//')[0]
            if not line.strip():
                continue
            syms = set(re.findall(r'(_[A-Za-z0-9_]+)', line))
            if not syms:
                continue
            decl = bool(_DECL_RE.match(line))
            sm = _STORE_ONLY_RE.match(line)
            store_target = sm.group(1) if sm else None
            for s in syms:
                e = slot(s)
                if decl:
                    e['decl'] += 1
                elif s == store_target:
                    e['store'] += 1
                else:
                    e['read'] += 1
            if not decl:
                am = _ADDR_TAKE_RE.search(line)
                if am:
                    taken.add(am.group(1))
                for s in re.findall(r'(_[A-Za-z0-9_]+)\s*\+\s*\d+', line):
                    taken.add(s)
        for run in _var_runs(path):
            reached = False
            for name in run:
                if reached:
                    slot(name)['offset_reach'] += 1
                if name in taken:
                    reached = True
    return use


# ---------------------------------------------------------------------------
# The master side
# ---------------------------------------------------------------------------

_TRAIL = re.compile(r'\d+$')


def cell_family(cell, shfunction):
    """The key wire-units.csv is looked up under.

    Shared-function cells carry their family in _matrix's ShFunction
    column (Chan_Eq, ChanComp, ...). Unshared ones have none, and the
    family the masters use for them is the cell name with its instance
    numbers removed (Aux001Delay001 -> AuxDelay). wire-units.csv is keyed
    on BOTH shapes -- Chan_Mtr is a ShFunction, ChanGateRng is a name
    shape -- so both are returned, most specific first, and the caller
    takes the first that resolves.
    """
    name = re.sub(r'\d+', '', cell)          # Chan001GateRng001 -> ChanGateRng
    keys = [name]
    if 'Rtg' in name:
        # Chan001RtgMute001 is the master's Chan[1-32]Mute[1-1]: the Rtg
        # infix is the generator's, not the master's.
        keys.append(name.replace('Rtg', '', 1))
    if shfunction:
        keys.append(shfunction)
    return keys


def load_units():
    rows = list(csv.DictReader(open(WIRE_UNITS)))
    return {r['family']: r for r in rows}


def load_matrix(product):
    path = os.path.join(ROOT, 'MW', product.upper(), 'MX', '_matrix.csv')
    return list(csv.DictReader(open(path)))


def expand_pattern(cell):
    """Chan[1-32]Mtr[1-2] -> the 64 concrete names it stands for."""
    out = ['']
    for part in re.split(r'(\[\d+-\d+\])', cell):
        m = re.fullmatch(r'\[(\d+)-(\d+)\]', part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            out = [o + f'{i:03d}' for o in out for i in range(a, b + 1)]
        else:
            out = [o + part for o in out]
    return out


def load_wire_table(product):
    path = os.path.join(ROOT, 'docs/contract', f'{product.lower()}-wire-table.csv')
    if not os.path.exists(path):
        return []
    return list(csv.DictReader(open(path)))


# ---------------------------------------------------------------------------
# Boundary vectors from a Table string
# ---------------------------------------------------------------------------

_LAW_RE = re.compile(r'^\s*(-?[\d.]+)=(-?[\d.]+)/(-?[\d.]+)=(-?[\d.]+)/\[(\w+)\]\s*$')
_DB_KNEE_RE = re.compile(r'(-?[\d.]+)@(\d+)')


def boundaries(table):
    """The values a cell must survive: min, max, mid, and every knee the
    Table string names.

    Two Table shapes appear in the masters:
      '0=20/254=200/[Log]'  encoder count -> engineering value, with a law
      'dB:Off:-50@31:-30@63:-10@127:0'  a piecewise fader law whose knees
                                        are the @ positions
    Both are host-domain descriptions. What goes over the wire is the
    ENGINEERING value (dsp4_pairgraph writes -30.0 for a -30 dB threshold),
    so the vectors returned here are engineering values, and the encoder
    counts only tell us where the knees are.
    """
    t = (table or '').strip()
    if not t:
        return [], None
    m = _LAW_RE.match(t)
    if m:
        lo_v, hi_v, law = float(m.group(2)), float(m.group(4)), m.group(5)
        mid = (lo_v + hi_v) / 2.0
        if law.lower() == 'log' and lo_v > 0 and hi_v > 0:
            mid = (lo_v * hi_v) ** 0.5
        return sorted({lo_v, mid, hi_v}), law
    knees = _DB_KNEE_RE.findall(t)
    if knees:
        vals = sorted({float(v) for v, _pos in knees})
        tail = t.rsplit(':', 1)[-1]
        try:
            vals.append(float(tail))
        except ValueError:
            pass
        if 'Off' in t:
            vals.insert(0, float('-inf'))
        return sorted(set(vals)), 'dB-piecewise'
    return [], t


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def build(product):
    units = load_units()
    matrix = load_matrix(product)
    plan = {}
    orphan_cells = []          # master cell with an address outside dispatch
    dispatch = {}
    strides = {}
    cons = {}
    for chip in (1, 2):
        dispatch[chip], strides[chip] = parse_dispatch(chip)
        cons[chip] = consumption(chip)

    for chip in (1, 2):
        for addr, d in dispatch[chip].items():
            plan[(chip, addr)] = {
                'chip': chip, 'addr': addr,
                'symbol': d['symbol'], 'sym_offset': d['offset'],
                'kernel_note': d['comment'],
                'stride': strides[chip].get(addr, 0),
                'mapped': d['symbol'] is not None,
                'cells': [], 'families': [], 'tables': [],
                'ramp_profiles': [], 'unit': None, 'kernel_expects': None,
                'unit_source': None,
            }

    for r in matrix:
        if not r['DspAdd'].strip():
            continue
        chip = int(r['DspSpi'])
        addr = int(r['DspAdd'])
        e = plan.get((chip, addr))
        if e is None:
            orphan_cells.append((r['_Cell'], chip, addr))
            continue
        e['cells'].append(r['_Cell'])
        keys = cell_family(r['_Cell'], r['ShFunction'])
        e['families'].append(keys[0])
        if r['Table']:
            e['tables'].append(r['Table'])
        if r['RampProfile']:
            e['ramp_profiles'].append(r['RampProfile'])
        if e['unit'] is None:
            for k in keys:
                if k in units:
                    e['unit'] = units[k]['unit']
                    e['kernel_expects'] = units[k]['kernel_expects']
                    e['unit_source'] = k
                    break

    for e in plan.values():
        if e['unit'] is None:
            e['unit'] = 'UNDECLARED'
            e['kernel_expects'] = ''
        e['families'] = sorted(set(e['families']))
        e['tables'] = sorted(set(e['tables']))
        e['ramp_profiles'] = sorted(set(e['ramp_profiles']))
        table = e['tables'][0] if len(e['tables']) == 1 else ''
        e['boundaries'], e['law'] = boundaries(table)
        sym = e['symbol']
        if sym is None:
            e['consumed'] = None
            e['role'] = 'UNMAPPED'
        else:
            u = cons[e['chip']].get(sym, {'read': 0, 'store': 0, 'decl': 0,
                                          'offset_reach': 0})
            e['consumed'] = u['read'] > 0
            e['uses'] = u
            # THREE ROLES, and only one of them is a defect.
            #   CONSUMED  some emitted line reads it -> a host write can
            #             reach the audio path
            #   READBACK  the kernel STORES it and nothing reads it: that is
            #             a device->host cell (the meters), working as
            #             designed, not an inert control
            #   INERT     nothing but the declaration mentions it. A host
            #             write lands in DM and no line of the running
            #             kernel will ever look at it. This is the D38 class.
            if u['read'] > 0:
                e['role'] = 'CONSUMED'
            elif u['store'] > 0:
                e['role'] = 'READBACK'
            elif u['offset_reach'] > 0:
                e['role'] = 'OFFSET_REACH'
            else:
                e['role'] = 'INERT'
    return plan, orphan_cells


def coverage(product, plan, orphans):
    """Which documented master cells reach the DSP at all."""
    addressed = set()
    for e in plan.values():
        addressed.update(e['cells'])
    seen = {c for c, _ch, _a in orphans}
    addressed |= seen
    rows = load_wire_table(product)
    matrix_cells = {r['_Cell'] for r in load_matrix(product)}
    doc_total = doc_addressed = doc_nomatrix = 0
    by_family = {}
    for r in rows:
        for name in expand_pattern(r['cell']):
            doc_total += 1
            f = by_family.setdefault(r['family'],
                                     {'total': 0, 'addressed': 0, 'nomatrix': 0})
            f['total'] += 1
            # The master's PD naming and the matrix's _Cell naming differ in
            # two documented ways: meter cells carry an 'Aa' prefix in the
            # matrix, and routing cells carry an 'Rtg' infix. Try both rather
            # than call a renamed cell missing.
            cands = [name, 'Aa' + name]
            m = re.match(r'^([A-Za-z]+?)(\d{3})([A-Za-z].*)$', name)
            if m:
                cands.append(m.group(1) + m.group(2) + 'Rtg' + m.group(3))
            if any(c in addressed for c in cands):
                doc_addressed += 1
                f['addressed'] += 1
            elif not any(c in matrix_cells for c in cands):
                doc_nomatrix += 1
                f['nomatrix'] += 1
    return {'documented': doc_total, 'addressed': doc_addressed,
            'not_in_matrix': doc_nomatrix, 'by_family': by_family}


def _kernel_class(entry):
    """The generator's own words for what lives at an address, with the
    node instance stripped so instances of one class collapse together."""
    n = re.sub(r'^0x[0-9A-F]{4}:\s*', '', entry['kernel_note'])
    n = re.sub(r'C[12]_[A-Z0-9_]+\s*', '', n)
    n = re.sub(r'\[\d+\]', '[i]', n)
    return n.strip() or '(no comment)'


HAND_BEGIN = '<!-- BEGIN hand-written — preserved across regeneration -->'
HAND_END = '<!-- END hand-written -->'


def _preserved_block(out):
    """Whatever a human wrote between the markers in a previous edition.

    The static list below is generated, but the LIVE confirmation that
    goes with it -- which candidates were written on the part and what the
    bus did -- is bench evidence that no generator can re-derive. It was
    hand-added under an `AUTO-GENERATED. Do not hand-edit.` header on
    2026-08-30, which meant the next regeneration would have deleted it
    silently. Same shape as D58's stale golden: evidence that only one
    session can produce, sitting where a routine re-run destroys it.
    Anything between the markers is carried across verbatim.
    """
    try:
        prev = open(out, encoding='utf-8').read()
    except OSError:
        return ''
    i = prev.find(HAND_BEGIN)
    j = prev.find(HAND_END, i + 1)
    if i < 0 or j < 0:
        return ''
    return prev[i:j + len(HAND_END)]


def inert_markdown(entries, out):
    """The D38 authoritative inert list: counted, named, by class."""
    preserved = _preserved_block(out)
    inert = [e for e in entries if e['role'] == 'INERT']
    uncertain = [e for e in entries if e['role'] == 'OFFSET_REACH']
    groups = {}
    for e in inert:
        g = groups.setdefault(_kernel_class(e), {'addr': 0, 'cells': [],
                                                 'symbols': set()})
        g['addr'] += 1
        g['cells'] += e['cells']
        if e['symbol']:
            g['symbols'].add(re.sub(r'_C[12]_[A-Z0-9_]+$', '', e['symbol']))
    L = ['# D38 — the writable-but-inert control surface, enumerated',
         '',
         'AUTO-GENERATED by `tools/dsp/wire_contract.py --inert-md`. Do not',
         'hand-edit; change the contract or the generator and re-run.',
         '',
         'An address is INERT here when its dispatch target is named by no',
         'emitted line of any node body, shared source or library file other',
         'than its own declaration — it is written by the host, it lands in',
         'DM, and nothing in the running kernel will ever look at it. The',
         'test is deliberately conservative in the safe direction: a symbol',
         'reached by OFFSET from a neighbour (the meters do this) is counted',
         'separately as uncertain rather than claimed dead, so everything on',
         'this list is provably unreferenced and the list under-reports',
         'rather than over-reports.',
         '',
         f'**{len(inert)} addresses are inert**, naming '
         f'**{len({c for e in inert for c in e["cells"]})} master cells**. '
         f'A further **{len(uncertain)} addresses** are reachable by offset '
         f'from a symbol that is used, and are not claimed either way.',
         '']
    if preserved:
        L += ['', preserved]
    L += ['',
         '| kernel class | addresses | master cells | symbol |',
         '|---|---|---|---|']
    for name, g in sorted(groups.items(), key=lambda kv: -kv[1]['addr']):
        syms = ', '.join(f'`{s}_*`' for s in sorted(g['symbols'])[:3])
        L.append(f'| {name} | {g["addr"]} | {len(g["cells"])} | {syms} |')
    L += ['', '## the cells, by class', '']
    for name, g in sorted(groups.items(), key=lambda kv: -kv[1]['addr']):
        cells = sorted(set(g['cells']))
        L.append(f'### {name} — {g["addr"]} addresses, {len(cells)} cells')
        L.append('')
        if cells:
            shown = cells if len(cells) <= 40 else cells[:40]
            L.append('`' + '`, `'.join(shown) + '`')
            if len(cells) > len(shown):
                L.append('')
                L.append(f'...and {len(cells) - len(shown)} more of the same '
                         f'shape (one per instance).')
        else:
            L.append('No master cell names these addresses — they are '
                     'generator-side words with no documented control.')
        L.append('')
    open(out, 'w').write('\n'.join(L) + '\n')
    return len(inert)


def proposals_markdown(entries, out):
    """UNDECLARED families whose behaviour lets a unit be INFERRED.

    Reported as proposals for mx26's wire-units.csv and adopted nowhere:
    mx26 is the source of truth for cell semantics, and a spoke that
    quietly declares a unit for itself has forked the contract.
    """
    fams = {}
    for e in entries:
        if e['unit'] != 'UNDECLARED' or not e['cells']:
            continue
        for f in e['families']:
            g = fams.setdefault(f, {'addr': 0, 'tables': set(),
                                    'notes': set(), 'symbols': set(),
                                    'roles': set(), 'cells': 0})
            g['addr'] += 1
            g['cells'] += len(e['cells'])
            g['tables'].update(e['tables'])
            g['notes'].add(_kernel_class(e))
            g['roles'].add(e['role'])
            if e['symbol']:
                g['symbols'].add(re.sub(r'_C[12]_[A-Z0-9_]+$', '', e['symbol']))
    L = ['# proposals for mx26 wire-units.csv',
         '',
         'AUTO-GENERATED by `tools/dsp/wire_contract.py --proposals-md`.',
         '',
         'These are families the wire table carries as `unit=UNDECLARED`',
         'and whose unit can be INFERRED from two independent pieces of',
         "evidence: the master's own Table string (the host-domain scale",
         'law) and the quantity the kernel keeps at the address (the',
         "generator's dispatch comment and the symbol it points at).",
         '',
         '**Nothing here is adopted in this repo.** mx26 owns cell',
         'semantics; a spoke that declares a unit for itself has forked the',
         'contract. These rows are for mx26 to accept, amend or reject, and',
         'until one is accepted the family keeps presence/echo testing only.',
         '',
         '| family | addresses | cells | master Table | kernel keeps | '
         'symbol | proposal |',
         '|---|---|---|---|---|---|---|']
    for f, g in sorted(fams.items(), key=lambda kv: -kv[1]['addr']):
        tables = '; '.join(sorted(g['tables'])[:2]) or '(none)'
        notes = '; '.join(sorted(g['notes'])[:2])
        syms = ', '.join(f'`{s}_*`' for s in sorted(g['symbols'])[:2])
        notes_l = ' '.join(g['notes']).lower()
        if 'INERT' in g['roles'] and len(g['roles']) == 1:
            prop = ('no unit needed — every address in this family is INERT; '
                    'mark the cells reserved or wire them (D38)')
        elif 'coeff' in notes_l:
            # THE BIGGEST DISAGREEMENT IN THE WHOLE SURFACE. The masters
            # document Freq, Gain, Q and Shelf as four separate cells; the
            # DSP has one COEFFICIENT SET at the band's base address and
            # every one of those cells is addressed to a word of it. The
            # host is therefore expected to compute biquad coefficients,
            # which no line of the masters says. Proposing "the Table
            # domain" here would be proposing a unit for a cell that does
            # not exist on the wire.
            prop = ('**the address holds a filter COEFFICIENT, not this '
                    'parameter** — the masters document Freq/Gain/Q/Shelf as '
                    'separate cells at one coefficient-set base, so the host '
                    'computes the biquad. Declare the wire as a coefficient '
                    'set and say which side converts')
        elif not g['tables']:
            prop = 'enum/bool — no scale law in the masters'
        else:
            prop = 'declare the Table domain as the wire unit'
        L.append(f'| {f} | {g["addr"]} | {g["cells"]} | `{tables}` | '
                 f'{notes} | {syms} | {prop} |')
    L += unaddressed_section(entries)
    open(out, 'w').write('\n'.join(L) + '\n')
    return len(fams)


def unaddressed_section(entries, product='d32'):
    """Documented cells that reach no DSP address, minus the MCU-only ones.

    mcu-only-prefixes.txt is the tree's own record of which master
    families are never expected to reach the DSP. Everything left after
    subtracting it is a documented control with nowhere to go, and
    nothing in this repo says whether that is intended.
    """
    prefixes = []
    path = os.path.join(ROOT, 'mcu-only-prefixes.txt')
    if os.path.exists(path):
        prefixes = [l.strip() for l in open(path)
                    if l.strip() and not l.startswith('#')]
    addressed = {c for e in entries for c in e['cells']}
    matrix = {r['_Cell'] for r in load_matrix(product)}
    rows = load_wire_table(product)
    fams = {}
    for r in rows:
        for name in expand_pattern(r['cell']):
            cands = [name, 'Aa' + name]
            m = re.match(r'^([A-Za-z]+?)(\d{3})([A-Za-z].*)$', name)
            if m:
                cands.append(m.group(1) + m.group(2) + 'Rtg' + m.group(3))
            if any(c in addressed for c in cands):
                continue
            if any(r['family'].startswith(p) or name.startswith(p)
                   for p in prefixes):
                continue
            g = fams.setdefault(r['family'], {'n': 0, 'in_matrix': 0,
                                              'example': name})
            g['n'] += 1
            if any(c in matrix for c in cands):
                g['in_matrix'] += 1
    L = ['', '## documented cells that reach no DSP address', '',
         'After subtracting the families `mcu-only-prefixes.txt` already',
         'records as MCU-only. A cell here is documented in the masters and',
         'has nowhere to go on the DSP; the `in _matrix.csv` column says',
         'whether the matrix carries the row at all, which separates "the',
         'DSP does not implement it" from "the matrix never routed it".',
         '',
         '| family | cells with no DSP address | of those, in _matrix.csv | example |',
         '|---|---|---|---|']
    for f, g in sorted(fams.items(), key=lambda kv: -kv[1]['n']):
        L.append(f'| {f} | {g["n"]} | {g["in_matrix"]} | `{g["example"]}` |')
    L.append('')
    L.append(f'Total: **{sum(g["n"] for g in fams.values())} documented '
             f'cells across {len(fams)} families**.')
    L += ['',
          'A zero in the second column means `_matrix.csv` does not carry',
          'that cell NAME at all, which is two different things:',
          '',
          '- `*Name` cells are host-side text by design (`wire-units.csv`',
          '  says "n/a — host-side only"), so a zero there is correct.',
          '- **The `MainL` / `MainR` / `MainSub` families cannot be resolved',
          '  at all.** The masters name three main output chains; the DSP',
          '  has FOUR (`C2_MAIN_OEQ/OCOMP/OLIM_01..04`, addressed as',
          '  `Main001`..`Main004`) and nothing in either repo states the',
          '  correspondence. Until mx26 rules on it, every MainL/MainR/',
          '  MainSub cell is untestable by name — the addresses are being',
          '  swept, but under the matrix names, not the documented ones.']
    return L


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--product', default='d32')
    ap.add_argument('--plan', help='write the per-address plan as JSON')
    ap.add_argument('--coverage', action='store_true')
    ap.add_argument('--inert', action='store_true',
                    help='print the addresses whose target no emitted line reads')
    ap.add_argument('--inert-md', help='write the D38 inert list as markdown')
    ap.add_argument('--proposals-md',
                    help='write the UNDECLARED-family unit proposals for mx26')
    args = ap.parse_args()

    plan, orphans = build(args.product)
    entries = [plan[k] for k in sorted(plan)]

    mapped = [e for e in entries if e['mapped']]
    unmapped = [e for e in entries if not e['mapped']]
    inert = [e for e in mapped if e['role'] == 'INERT']
    readback = [e for e in mapped if e['role'] == 'READBACK']
    offreach = [e for e in mapped if e['role'] == 'OFFSET_REACH']
    named = [e for e in entries if e['cells']]

    print(f'  addresses in the dispatch tables : {len(entries)}')
    print(f'    mapped to a DM symbol          : {len(mapped)}')
    print(f'    unmapped (write is an error)   : {len(unmapped)}')
    print(f'    named by a master cell         : {len(named)}')
    print(f'    kernel-written readback (meters): {len(readback)}')
    print(f'    reachable by offset (uncertain) : {len(offreach)}')
    print(f'    INERT (nothing reads or writes) : {len(inert)}')
    if orphans:
        print(f'  master cells addressed outside the dispatch table: '
              f'{len(orphans)} (first: {orphans[0]})')

    if args.inert:
        for e in inert:
            print(f'  c{e["chip"]} 0x{e["addr"]:04X} {e["symbol"]:<40} '
                  f'{",".join(e["cells"]) or "(no master cell)"}')

    if args.coverage:
        cov = coverage(args.product, plan, orphans)
        print(f'\n  master cells documented in the wire table: {cov["documented"]}')
        print(f'    reaching a DSP address                 : {cov["addressed"]}')
        print(f'    absent from _matrix.csv (host/MCU-only) : {cov["not_in_matrix"]}')
        print(f'    in _matrix but with no DSP address      : '
              f'{cov["documented"] - cov["addressed"] - cov["not_in_matrix"]}')
        print('\n  by family (documented / addressed / not in matrix):')
        for fam, f in sorted(cov['by_family'].items()):
            print(f'    {fam:<22} {f["total"]:>5} {f["addressed"]:>6} '
                  f'{f["nomatrix"]:>6}')

    if args.inert_md:
        n = inert_markdown(entries, args.inert_md)
        print(f'\n  wrote {args.inert_md} ({n} inert addresses)')
    if args.proposals_md:
        n = proposals_markdown(entries, args.proposals_md)
        print(f'  wrote {args.proposals_md} ({n} UNDECLARED families)')

    if args.plan:
        with open(args.plan, 'w') as fh:
            json.dump({'product': args.product, 'entries': entries}, fh, indent=1)
        print(f'\n  wrote {args.plan} ({len(entries)} addresses)')


if __name__ == '__main__':
    main()
