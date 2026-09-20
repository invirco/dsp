#!/usr/bin/env python3
"""gen_accept_fixtures.py [--product d24] [--out MW/D24/DSP/accept] -- the acceptance test's fixtures, generated (S66).

One fixture per testable path, plus a manifest. Nothing here is typed per path: a fixture is the join of

  defs/products/<p>/inputs.csv            the mic inputs: XLR, 595 send position, strip, rx cell
  defs/products/<p>/<p>-io.csv            the outputs (panel labels)
  defs/gen/matrix/<p>-diagram.csv         the product's topology (nodes and edges, gates applied by defs)
  MW/<P>/MX/_matrix.csv                   the expanded cells, with Neutral and the DSP address (generated from defs)
  tools/accept/path-cells.csv             topology element -> cell families (PROPOSED for defs; see its header)
  tools/accept/battery.csv                the test-set rows and which path types they apply to

and the loop the unit's stimulus uses (--donor-strip / --loop-aux / --ref-input; the harness replaces the loop, the
fixture's `stimulus` block is then the harness's). The rule for the cells (PW 09-14, the Neutral column's definition):
every cell on the path is written to its Neutral; a path element (an assign or send) on the path is written to its
Neutral (= enabled); the same element for every OTHER source on that bus is written to 0 (isolation); the strip under
measurement has every assign off, so it cannot feed the loop that stimulates it. A cell whose Neutral is empty is
UNDECIDABLE and is listed, never guessed; a '-' cell is not touched. Cells the binding names but the product's matrix
lacks are listed as `absent` (the family does not exist on this product).

Deterministic: same inputs, same bytes (sorted keys, no timestamps; the defs commit is recorded)."""
import argparse, collections, csv, hashlib, json, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
HERE = os.path.dirname(os.path.abspath(__file__))
FACTORY_CODES = [0, 1, 2, 4, 8, 16, 32, 63]
RESPONSE_POINTS = [20, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 15000, 20000]


def rows_csv(path):
    with open(path, newline='') as f:
        return list(csv.DictReader(l for l in f if not l.startswith('#')))


def sha(path):
    return hashlib.sha256(open(path, 'rb').read()).hexdigest()


def defs_lock():
    out = {}
    for l in open(os.path.join(ROOT, 'defs.lock')):
        if '=' in l and not l.startswith('#'):
            k, v = l.strip().split('=', 1)
            out[k] = v
    return out


class Matrix:
    """The product's expanded cells: name -> row. Families are Scope + Family with 3-digit indices."""
    RX = re.compile(r'^([A-Za-z]+)(\d{3})([A-Za-z]+)(\d{3})$')

    def __init__(self, path):
        self.cells = collections.OrderedDict((r['_Cell'], r) for r in rows_csv(path))
        self.families = set()
        for name in self.cells:
            m = self.RX.match(name)
            if m:
                self.families.add((m.group(1), m.group(3)))

    def name(self, scope, idx, family, sub):
        return '%s%03d%s%03d' % (scope, idx, family, sub)

    def subs(self, scope, idx, family):
        """Every sub-index of scope[idx]family (EqGain 1..4, AuxOn 1..8 ...)."""
        pre = '%s%03d%s' % (scope, idx, family)
        return sorted(int(n[-3:]) for n in self.cells if n.startswith(pre) and len(n) == len(pre) + 3)

    def count(self, scope):
        return len({n[len(scope):len(scope) + 3] for n in self.cells if self.RX.match(n) and self.RX.match(n).group(1) == scope})


def cell_entry(mx, name, value, element, why):
    r = mx.cells[name]
    return {'cell': name, 'value': value, 'element': element, 'why': why, 'neutral': r['Neutral'],
            'chip': r['DspSpi'] or None, 'dsp_add': int(r['DspAdd']) if r['DspAdd'] else None}


class Builder:
    def __init__(self, product, mx, binding, topo):
        self.p, self.mx, self.binding, self.topo = product, mx, binding, topo
        self.findings = collections.OrderedDict()

    def finding(self, key, text):
        self.findings.setdefault(key, text)

    def element_cells(self, element, scope_idx, bus=None, role_filter=None, value_mode='neutral'):
        """Cells for one topology element. scope_idx: {'Chan': strip, 'Aux': k, 'Main': 1, 'MainL': 1, 'MainR': 1}.
        value_mode: 'neutral' (write Neutral) or 'off' (assign off = 0)."""
        set_, undecidable, absent = [], [], []
        for b in self.binding.get(element, []):
            if role_filter and b['role'] not in role_filter:
                continue
            scope = b['scope']
            idx = scope_idx.get(scope)
            if idx is None:
                continue
            if (scope, b['family']) not in self.mx.families:
                absent.append('%s[]%s' % (scope, b['family']))
                continue
            subs = self.mx.subs(scope, idx, b['family'])
            if b['per'] == 'bus':
                subs = [s for s in subs if s == bus] if bus is not None else subs
            if not subs:
                absent.append('%s%03d%s (index not on this product)' % (scope, idx, b['family']))
                continue
            for s in subs:
                name = self.mx.name(scope, idx, b['family'], s)
                neutral = self.mx.cells[name]['Neutral']
                if b['role'] == 'drive':
                    continue           # the test sets it; listed under the test
                if value_mode == 'off':
                    set_.append(cell_entry(self.mx, name, 0, element, 'isolation: path element off'))
                elif neutral == '':
                    undecidable.append(name)
                elif neutral == '-':
                    continue
                else:
                    set_.append(cell_entry(self.mx, name, int(neutral), element,
                                           b['note'] or ('%s neutral' % b['role'])))
        return set_, undecidable, absent

    def walk(self, src, dst, avoid=()):
        """The in-line element path src -> dst on the product topology: the LONGEST path in the DAG (every in-line
        processing node, not a shortcut past them), never through a sidechain-key node (Gate ch.key) or through a
        pick tap other than at the ends, never through `avoid`. None if unreachable."""
        adj = collections.defaultdict(list)
        for e in self.topo['edges']:
            adj[e[0]].append(e[1])
        bad = set(avoid) | {n for n, g in self.topo['gates'].items() if g == 'ch.key'}
        memo = {}

        def best(n, seen):
            if n == dst:
                return [n]
            if n in memo:
                return memo[n]
            cand = None
            for m in adj[n]:
                if m in seen or (m in bad and m != dst) or (m.startswith('pick.') and m != dst):
                    continue
                t = best(m, seen | {m})
                if t and (cand is None or len(t) > len(cand)):
                    cand = t
            memo[n] = [n] + cand if cand else None
            return memo[n]
        return best(src, {src})

    def strip_chain(self, strip, path_nodes, assigns=None, bus=None):
        """Cells for the strip's own elements on `path_nodes`, plus its assigns: `assigns` = {edge: bus or None}
        enabled, every other assign edge of the strip off."""
        cells, und, absent = [], [], []
        for node in path_nodes:
            c, u, a = self.element_cells(node, {'Chan': strip}, role_filter=('neutral', 'drive'))
            cells += c; und += u; absent += a
        assigns = assigns or {}
        for edge in [e for e in self.binding if '>' in e]:
            for b in self.binding[edge]:
                if b['scope'] != 'Chan' or b['role'] != 'assign':
                    continue
                if edge in assigns:
                    k = assigns[edge]
                    c, u, a = self.element_cells(edge, {'Chan': strip}, bus=k, role_filter=('assign', 'neutral'))
                    cells += c; und += u; absent += a
                    # the same family's other buses off (only this send live)
                    if b['per'] == 'bus':
                        for s in self.mx.subs('Chan', strip, b['family']):
                            if s != k:
                                cells.append(cell_entry(self.mx, self.mx.name('Chan', strip, b['family'], s), 0, edge,
                                                        'isolation: only bus %d live' % k))
                else:
                    c, u, a = self.element_cells(edge, {'Chan': strip}, role_filter=('assign',), value_mode='off')
                    cells += c; und += u; absent += a
        return cells, und, absent

    def bus_isolation(self, edge, bus, except_strips):
        """Every other strip's assign on `edge` (bus k) off."""
        out = []
        b = [x for x in self.binding[edge] if x['role'] == 'assign'][0]
        for strip in range(1, self.mx.count('Chan') + 1):
            if strip in except_strips:
                continue
            subs = self.mx.subs('Chan', strip, b['family'])
            for s in subs:
                if b['per'] == 'bus' and s != bus:
                    continue
                out.append(cell_entry(self.mx, self.mx.name('Chan', strip, b['family'], s), 0, edge,
                                      'isolation: strip %d off bus' % strip))
        return out


def dedupe(cells):
    seen, out = {}, []
    for c in cells:
        if c['cell'] in seen:
            if seen[c['cell']]['value'] != c['value']:
                raise SystemExit('fixture conflict on %s: %s vs %s' % (c['cell'], seen[c['cell']], c))
            continue
        seen[c['cell']] = c
        out.append(c)
    return out


def universal_table(path, exclude):
    """The factory T1 reference: per code, the MEAN hardware gain re each channel's own code 0 across the measured
    channels (S55: 15 channels, J29 excluded). Not in defs: mic-gain-law.csv carries only the codes its target table
    uses (no 8, 16, 32), so the stage means are read from the measurement it was generated from."""
    law = collections.defaultdict(dict)
    for r in rows_csv(path):
        law[r['channel'].split()[0]][int(r['code'])] = float(r['loop_gain_db'])
    chans = sorted(c for c in law if c not in exclude and len(law[c]) == 64)
    return {str(c): round(sum(law[x][c] - law[x][0] for x in chans) / len(chans), 3) for c in range(64)}, chans


def tests_for(kind, battery, universal=None):
    """The battery rows that apply to this path type, with the runner's parameters."""
    out = []
    for t in battery:
        if kind not in t['applies'].split(';'):
            continue
        spec = {'test': t['test'], 'name': t['name'], 'method': t['method'], 'factory': t['factory'] != '-',
                'full': t['full'] != '-', 'reads': t['reads']}
        tid = t['test']
        if kind == 'input':
            if tid == 'T1':
                spec.update({'codes_factory': FACTORY_CODES, 'codes_full': list(range(64)), 'lane_dbfs_pk': -10.0,
                             'repeat_codes': [0, 63], 'order': 'level first, then code, then settle (S60-3)'})
                if universal:
                    spec.update({'universal_hw_gain_db': universal[0], 'universal_from': universal[1]})
            elif tid == 'T2':
                spec.update({'codes': [0, 63], 'points_hz': RESPONSE_POINTS})
            elif tid == 'T3':
                spec.update({'thdn_code': 0, 'thd_code': 63, 'lane_dbfs_pk': -3.0, 'freq_hz': 1000.0,
                             'levels_full_dbfs': [-60, -40, -20, -10, -6, -3, -1], 'harmonics': [2, 10]})
            elif tid == 'T4':
                spec.update({'factory': False, 'codes_full': FACTORY_CODES})
            elif tid == 'T4b':
                spec.update({'codes_factory': [63], 'codes_full': [63, 0], 'bands': ['20-20k', 'A', 'DC-24k']})
            elif tid in ('T5', 'T8'):
                spec.update({'from': 'T1 chirp, code 0'})
            elif tid == 'T6':
                spec.update({'freq_hz': 1000.0, 'lane_dbfs_pk': -20.0, 'code': 0})
            elif tid == 'T7':
                spec.update({'freq_hz': 10000.0, 'lane_dbfs_pk': -6.0, 'code': 2, 'neighbours': 'every other strip'})
            elif tid == 'A1':
                spec.update({'transitions': 'the mic-gain-law table steps + major carries + trims (S63-1)'})
        elif kind == 'output':
            if tid == 'T1':
                spec.update({'codes_factory': ['unity'], 'codes_full': ['unity'], 'lane_dbfs_pk': -10.0})
            elif tid == 'T2':
                spec.update({'codes': ['unity'], 'points_hz': RESPONSE_POINTS})
            elif tid == 'T3':
                spec.update({'thdn_code': 'unity', 'lane_dbfs_pk': -3.0, 'freq_hz': 1000.0})
            elif tid == 'T4':
                spec.update({'factory': True, 'bands': ['20-20k', 'A', 'DC-24k'], 'ref_input_code': 0})
            elif tid == 'T6':
                spec.update({'freq_hz': 1000.0, 'lane_dbfs_pk': -20.0})
            elif tid == 'T7':
                spec.update({'freq_hz': 10000.0, 'lane_dbfs_pk': -6.0, 'neighbours': 'every other output'})
        elif kind == 'node':
            spec.update({'tones_hz': [63, 1000, 8000], 'osc_dbfs_pk': -20.0})
        out.append(spec)
    return out


def dsp_context():
    """The DSP configuration a fixture set is valid for, and its numeric bounds.

    S82. An acceptance fixture is generated from the CONTRACT; what it will be
    scored against on a part is a firmware image, and the two have never been
    tied together in the artifact. PW signed a configuration whose audio
    differs from the unsigned one by a stated amount (DSP4_DYN_LUT and
    DSP4_GATE_LINTHR, 0.03934 dB worst bus word), so a fixture set that does
    not say which configuration it expects is a set that cannot be re-run
    later and compared.

    Both halves are READ, not typed: the triple comes from cfg_words.py, which
    computes it from build.sh and shipping.config, and the bounds come from
    limits.csv, which is the one place PW tunes them. If either is
    unavailable the manifest says so rather than carrying a stale guess --
    an absent key is a visible hole, a remembered number is not.
    """
    out = {}
    try:
        sys.path.insert(0, os.path.join(ROOT, 'tools', 'dsp'))
        import cfg_words
        val, _ = cfg_words.resolve(os.path.join(
            ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'shipping.config'))
        t = cfg_words.triple(val)
        out['shipping_config'] = 'MW/D32/DSP/SHARC/shipping.config'
        out['build_cfg'] = ['0x%08X' % w for w in t]
        out['signed'] = {k: val[k] for k in (
            'DSP4_SIMD_DYN', 'DSP4_STRIP_FUSED', 'DSP4_DYN_LUT',
            'DSP4_GATE_LINTHR') if k in val}
    except Exception as e:                      # noqa: BLE001 -- reported, not raised
        out['build_cfg_error'] = '%s: %s' % (type(e).__name__, e)
    # BOUNDS AND WITNESSES ARE CARRIED SEPARATELY (hub ruling, S83-Q1).
    # A bound is a contract term: a measurement outside it is a stop. A
    # witness is the figure a named instrument last read, recorded so the
    # manifest says what was actually measured -- a re-measurement that
    # moves but stays inside its bound REPLACES a witness and stops a
    # bound. Keeping both in one dictionary is how `comp_numeric_max_db`
    # came to hold S20's measurement as if it were a limit.
    bounds, wit = {}, {}
    path = os.path.join(ROOT, 'tools', 'accept', 'limits.csv')
    try:
        for r in rows_csv(path):
            if r['key'] in ('dyn_lut_max_db', 'gate_linthr_max_db',
                            'gate_linthr_lowthr_max_db', 'comp_numeric_max_db'):
                bounds[r['key']] = float(r['value'])
            elif r['key'].endswith('_witness_db'):
                wit[r['key']] = float(r['value'])
    except Exception as e:                      # noqa: BLE001
        bounds = {'error': '%s: %s' % (type(e).__name__, e)}
    out['numeric_bounds_db'] = bounds
    out['numeric_witnesses_db'] = wit
    out['numeric_bounds_from'] = 'tools/accept/limits.csv'
    out['proposal'] = 'proposals/CONTRACT-PROPOSAL-S82.md'
    return out


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--product', default='d24')
    ap.add_argument('--out')
    ap.add_argument('--donor-strip', type=int, default=6, help='the loop stimulus strip (TEST_OSC)')
    ap.add_argument('--alt-donor-strip', type=int, default=1, help='the donor when the path under test is the donor strip')
    ap.add_argument('--loop-aux', type=int, default=1, help='the aux bus the loop leaves on')
    ap.add_argument('--universal-law', help='per-code loop-gain measurement the factory T1 reference is averaged from '
                    '(default MW/<P>/DSP/s55/law.csv when present)')
    ap.add_argument('--universal-exclude', default='J29', help='channels flagged out of the mean (S55: J29)')
    ap.add_argument('--ref-input', default='MIC 5', help='the input an output path loops back into')
    a = ap.parse_args(argv)
    p = a.product.lower()
    P = p.upper()
    out = a.out or os.path.join(ROOT, 'MW', P, 'DSP', 'accept')
    src = {
        'inputs': os.path.join(ROOT, 'defs', 'products', p, 'inputs.csv'),
        'io': os.path.join(ROOT, 'defs', 'products', p, '%s-io.csv' % p),
        'topology': os.path.join(ROOT, 'defs', 'gen', 'matrix', '%s-diagram.csv' % p),
        'matrix': os.path.join(ROOT, 'MW', P, 'MX', '_matrix.csv'),
        'binding': os.path.join(HERE, 'path-cells.csv'),
        'battery': os.path.join(HERE, 'battery.csv'),
    }
    for k, v in src.items():
        if not os.path.exists(v):
            raise SystemExit('missing %s: %s (no fallback: the fixture set is generated from it)' % (k, v))
    lock = defs_lock()
    mx = Matrix(src['matrix'])
    binding = collections.OrderedDict()
    for b in rows_csv(src['binding']):
        binding.setdefault(b['element'], []).append(b)
    trows = rows_csv(src['topology'])
    topo = {'nodes': [r['Id'] for r in trows if r['Type'] == 'node'],
            'edges': [(r['From'], r['To']) for r in trows if r['Type'] == 'edge'],
            'gates': {r['Id']: r['Gate'] for r in trows if r['Type'] == 'node'}}
    battery = rows_csv(src['battery'])
    B = Builder(p, mx, binding, topo)
    upath = a.universal_law or os.path.join(ROOT, 'MW', P, 'DSP', 's55', 'law.csv')
    universal = None
    if os.path.exists(upath):
        tbl, chans = universal_table(upath, set(a.universal_exclude.split(',')))
        universal = (tbl, '%s: mean hardware gain re own code 0 over %d channels (%s), excluded %s' % (
            os.path.relpath(upath, ROOT), len(chans), ' '.join(chans), a.universal_exclude))
        src['universal'] = upath
        B.finding('universal-not-in-defs', 'the factory T1 reference (per-code mean stage gain) is not in defs: '
                  'common/tables/mic-gain-law.csv carries only its target codes (no 8/16/32); averaged here from %s'
                  % os.path.relpath(upath, ROOT))
    else:
        B.finding('universal-missing', 'no universal gain table for %s: factory T1 reports gains without the stage check' % P)

    # every binding element must exist in the product topology (or be an edge of it); report, don't drop silently
    for el in binding:
        if '>' in el:
            if tuple(el.split('>')) not in topo['edges']:
                B.finding('binding-edge-' + el, 'binding edge %s is not an edge of the %s topology' % (el, P))
        elif el not in topo['nodes']:
            B.finding('binding-node-' + el, 'binding element %s is not a node of the %s topology' % (el, P))
    for node in topo['nodes']:
        if node.split('.')[0] in ('ch', 'aux', 'main') and node not in binding and node not in ('ch.pick',):
            B.finding('node-no-cells-' + node, 'topology node %s has no cell binding (no cells on %s)' % (node, P))

    inputs = rows_csv(src['inputs'])
    by_panel = {r['panel']: r for r in inputs}
    donor = a.donor_strip
    aux_edge = 'ctl.auxpick>bus.aux'
    in_path = B.walk('io.in', 'pick.postfdr')           # measured at TEST_MEAS = the strip post-fader
    donor_path = B.walk('ch.insel', 'pick.postfdr')     # TEST_OSC replaces the strip's input block ahead of the chain
    aux_out = B.walk('bus.aux', 'io.out', avoid=('sub', 'rec.usb'))
    main_out = B.walk('bus.main', 'io.out', avoid=('sub', 'bus.mtx', 'mon', 'rec.usb'))

    def stimulus_loop(except_strips, donor):
        cells, und, absent = B.strip_chain(donor, donor_path, assigns={aux_edge: a.loop_aux})
        for node in aux_out:
            c, u, ab = B.element_cells(node, {'Aux': a.loop_aux}, bus=a.loop_aux)
            cells += c; und += u; absent += ab
        cells += B.bus_isolation(aux_edge, a.loop_aux, except_strips=set(except_strips) | {donor})
        return {'kind': 'loop', 'donor_strip': donor, 'aux': a.loop_aux, 'route': ['TEST_OSC', 'strip %d' % donor] +
                donor_path + aux_out, 'cells': dedupe(cells), 'undecidable': sorted(set(und)), 'absent': sorted(set(absent)),
                'harness': 'replaced by the harness source (the cells above then do not apply)'}

    fixtures, manifest = [], []
    # ---- inputs
    for r in inputs:
        strip = int(r['strip'])
        n = int(r['panel'].split()[-1])
        d = a.alt_donor_strip if strip == donor else donor
        note = ('strip %d is the loop donor: this path is stimulated from strip %d (S55 did the same for J32)'
                % (donor, d)) if strip == donor else None
        cells, und, absent = B.strip_chain(strip, in_path, assigns={})
        fx = {
            'fixture': '%s-in-mic%02d' % (p, n), 'product': p, 'type': 'input',
            'path': {'panel': r['panel'], 'xlr': r['xlr'], 'strip': strip, 'rx_cell': r['rx_cell'],
                     'preamp_595': r['preamp_595'], 'send_pos': int(r['send_pos']), 'adc': r['adc'],
                     'tdm_slot': int(r['tdm_slot']), 'measure': {'node': 'C1_TEST_MEAS', 'meas_chan': strip,
                                                                 'tap': 'post-fader'}},
            'topology': in_path,
            'drive': [{'cell': mx.name('Chan', strip, 'Gain', 1), 'what': 'DSP trim, 0 dB (Neutral) during the battery'},
                      {'chain': 'send_pos %s' % r['send_pos'], 'what': '595 gain code per test (codes below); phantom off'}],
            'set': dedupe(cells), 'undecidable': sorted(set(und)), 'absent': sorted(set(absent)),
            'stimulus': stimulus_loop([strip], d),
            'tests': tests_for('input', battery, universal),
        }
        if note:
            fx['note'] = note
        fixtures.append(fx)
    # ---- outputs
    ref = by_panel.get(a.ref_input)
    io = [r for r in rows_csv(src['io']) if r['direction'] == 'out' and r['kind'] == 'connector']
    seen_labels = set()
    outs = []
    for r in io:
        lab = r['label']
        if lab in seen_labels or r['channels'] != '1':
            continue                                    # duplicate rear-panel art / paired-jack alternatives
        seen_labels.add(lab)
        outs.append(r)
    for r in outs:
        lab = r['label']
        m = re.match(r'Aux Out A(\d+)$', lab)
        cells, und, absent = [], [], []
        status, route, measure = 'ok', None, None
        if m:
            k = int(m.group(1))
            fid = '%s-out-aux%02d' % (p, k)
            route = ['pick.postfdr', 'ctl.auxpick'] + aux_out
            c, u, ab = B.strip_chain(donor, donor_path, assigns={aux_edge: k})
            cells += c; und += u; absent += ab
            for node in aux_out:
                c, u, ab = B.element_cells(node, {'Aux': k}, bus=k)
                cells += c; und += u; absent += ab
            cells += B.bus_isolation(aux_edge, k, except_strips={donor})
        elif lab.startswith('Main Out'):
            side = lab.split()[-1]
            fid = '%s-out-main%s' % (p, side.lower())
            route = ['ch.pan'] + main_out
            c, u, ab = B.strip_chain(donor, donor_path, assigns={'ch.pan>bus.main': None})
            cells += c; und += u; absent += ab
            for node in main_out:
                c, u, ab = B.element_cells(node, {'Main': 1, 'MainL' if side == 'L' else 'MainR': 1})
                cells += c; und += u; absent += ab
            cells += B.bus_isolation('ch.pan>bus.main', None, except_strips={donor})
        elif 'Center' in lab or 'C/LF' in lab:
            fid = '%s-out-sub' % p
            route = ['ch.pan'] + (B.walk('sub', 'io.out') or [])
            c, u, ab = B.strip_chain(donor, donor_path, assigns={'ch.pan>sub': None})
            cells += c; und += u; absent += ab
            for node in ('sub', 'sub.xover', 'sub.lim'):
                if node not in binding:
                    absent.append('%s (no cells bound; D24 matrix has MainL CrossoverFreq/Slope only)' % node)
        elif lab.startswith('Monitor Out'):
            fid = '%s-out-mon%s' % (p, lab.split()[-1].lower())
            r_mon = B.walk('mon', 'io.out')
            if r_mon is None:
                status = 'undecidable'
                B.finding('mon-no-out', 'the %s topology has no edge mon -> io.out (only mon -> phones, gated off): the '
                          'Monitor Out path cannot be generated' % P)
            route = r_mon
        else:
            continue
        if ref is not None:
            rstrip = int(ref['strip'])
            c, u, ab = B.strip_chain(rstrip, in_path, assigns={})
            cells += c; und += u; absent += ab
            measure = {'loop_into': ref['panel'], 'xlr': ref['xlr'], 'strip': rstrip, 'send_pos': int(ref['send_pos']),
                       'code': 0, 'node': 'C1_TEST_MEAS', 'meas_chan': rstrip,
                       'refer': 'lane dBFS -> output dBu: P + 3.01 + dac_fs_dbu - G_loop(ref, code 0) (S57)'}
        fx = {'fixture': fid, 'product': p, 'type': 'output', 'status': status,
              'path': {'panel': lab, 'connector': r['type'], 'measure': measure,
                       'physical_ref': None},
              'topology': route, 'set': dedupe(cells), 'undecidable': sorted(set(und)), 'absent': sorted(set(absent)),
              'stimulus': {'kind': 'test_osc', 'donor_strip': donor},
              'tests': tests_for('output', battery) if status == 'ok' else []}
        fixtures.append(fx)
    B.finding('outputs-no-table', 'outputs have no defs table like inputs.csv: the output XLR ref (AUX 1 = J45, known '
              'only from S42/S48) and its DAC slot are not declared, so output fixtures carry the panel label only')

    # ---- nodes: the cue bus + RTA (S65), the first node fixture
    cue_cells, cue_absent = [], []
    for fam, why in (('CueSel', 'drive: 1 on the strip under test'),):
        if ('Chan', fam) in mx.families:
            cue_cells.append({'cells': 'Chan[1-%d]%s001' % (mx.count('Chan'), fam), 'role': 'drive', 'why': why})
    for scope, fam in (('Sys', 'CueMode'), ('Mon', 'InputSel')):
        if (scope, fam) in mx.families:
            n = mx.name(scope, 1, fam, 1)
            cue_cells.append({'cells': n, 'role': 'drive', 'neutral': mx.cells[n]['Neutral'],
                              'dsp_add': mx.cells[n]['DspAdd'] or None})
    for prop in ('Cue001Src001', 'Cue001Active001', 'Rta001Mode001', 'Rta001PeakReset001', 'Rta001MtrL001..031',
                 'Rta001MtrR001..031', 'Aux[1-12]CueSel', 'Grp[1-4]CueSel'):
        cue_absent.append('%s (proposed, CONTRACT-PROPOSAL-S65; not in the master)' % prop)
    if 'cue' in topo['nodes']:
        fixtures.append({'fixture': '%s-node-cue-rta' % p, 'product': p, 'type': 'node', 'status': 'proposal',
                         'path': {'node': 'cue', 'route': B.walk('pick.postfdr', 'cue') + ['rta'],
                                  'delivered': 'chip 2 C2_MON via MIX_2 slots 9/10 (S65-1)',
                                  'build': 'DSP4_CUE=1 DSP4_RTA=1 (both 0 in shipping.config)'},
                         'topology': ['pick.prefdr', 'pick.postfdr', 'cue', 'rta', 'mon'],
                         'set': [], 'drive': cue_cells, 'undecidable': [], 'absent': cue_absent,
                         'stimulus': {'kind': 'test_osc', 'donor_strip': donor, 'osc_dbfs_pk': -20.0},
                         'cases': [{'case': 'A afl pan L', 'tones_hz': [63, 1000, 8000], 'mono': False},
                                   {'case': 'A afl pan R', 'tones_hz': [1000], 'mono': False},
                                   {'case': 'B pfl', 'tones_hz': [1000], 'mono': True},
                                   {'case': 'C source main L/R, pan L', 'tones_hz': [1000], 'mono': False},
                                   {'case': 'C source aux 1', 'tones_hz': [1000], 'mono': True}],
                         'tests': tests_for('node', [t for t in battery if t['test'] in ('T1', 'T2')])})
        if 'rta' not in topo['nodes']:
            B.finding('rta-gated', 'the %s topology gates rta off (d24.csv has no rta key) while S65 builds it on chip 1 '
                      'behind DSP4_RTA: the node fixture is emitted as status=proposal' % P)

    # ---- write
    os.makedirs(os.path.join(out, 'fixtures'), exist_ok=True)
    keep = set()
    for fx in fixtures:
        fx['generated_from'] = {'defs_commit': lock.get('DEFS_COMMIT'), 'contract': lock.get('CONTRACT_VERSION'),
                                'matrix_gen': lock.get('%s_MATRIX_GEN' % P),
                                'loop': {'donor_strip': donor, 'loop_aux': a.loop_aux, 'ref_input': a.ref_input}}
        fn = os.path.join(out, 'fixtures', fx['fixture'] + '.json')
        keep.add(os.path.basename(fn))
        with open(fn, 'w') as f:
            json.dump(fx, f, indent=1, sort_keys=True)
            f.write('\n')
        manifest.append({'fixture': fx['fixture'], 'type': fx['type'], 'status': fx.get('status', 'ok'),
                         'panel': fx['path'].get('panel') or fx['path'].get('node'), 'cells': len(fx['set']),
                         'undecidable': len(fx['undecidable']), 'absent': len(fx['absent']),
                         'tests': [t['test'] for t in fx['tests']], 'file': 'fixtures/' + fx['fixture'] + '.json'})
    for fn in os.listdir(os.path.join(out, 'fixtures')):
        if fn.endswith('.json') and fn not in keep:
            os.remove(os.path.join(out, 'fixtures', fn))
    man = {'product': p, 'generated_by': 'tools/accept/gen_accept_fixtures.py',
           'inputs_sha256': {k: sha(v) for k, v in sorted(src.items())},
           'defs_commit': lock.get('DEFS_COMMIT'), 'contract': lock.get('CONTRACT_VERSION'),
           'loop': {'donor_strip': donor, 'loop_aux': a.loop_aux, 'ref_input': a.ref_input},
           'dsp': dsp_context(),
           'fixtures': manifest, 'findings': list(B.findings.values())}
    with open(os.path.join(out, 'manifest.json'), 'w') as f:
        json.dump(man, f, indent=1, sort_keys=True)
        f.write('\n')
    print('%s: %d fixtures (%d input, %d output, %d node) -> %s' % (
        P, len(fixtures), sum(1 for x in fixtures if x['type'] == 'input'), sum(1 for x in fixtures if x['type'] == 'output'),
        sum(1 for x in fixtures if x['type'] == 'node'), os.path.relpath(out, ROOT)))
    for x in B.findings.values():
        print('  finding:', x)


if __name__ == '__main__':
    main(sys.argv[1:])
