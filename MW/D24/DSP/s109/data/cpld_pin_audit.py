#!/usr/bin/env python3
"""cpld_pin_audit.py (S109) — per-pin audit of the D24 LOGIC CPLD: fitter pin report x netlist fan-out.

For every one of U3's 144 pins: what the RTL calls it and which direction the
FITTER gives it, what net it is on, and which ACTIVE devices (not connectors,
not passives) are on that net besides U3 itself -- resolving 33R series taps
to the far side.
"""
import csv, re, sys, os, collections

FANOUT = os.path.expanduser('~/mx26/docs/d24-cpld-fanout.csv')
PINS = os.path.expanduser('~/mx26/docs/d24-netlist-global-pins.csv')
PIN = sys.argv[1] if len(sys.argv) > 1 else \
    '/home/peter/dsp/shared/dsp4-logic/quartus/output_files/dsp4_logic.pin'

fit = {}
for line in open(PIN):
    m = re.match(r'^(\S.*?)\s+:\s+(\d+)\s+:\s*(\S*)\s*:', line)
    if m:
        nm = m.group(1).strip().rstrip(':').strip()
        fit[int(m.group(2))] = (nm, m.group(3).strip() or '-')

rows = [r for r in csv.DictReader([l for l in open(PINS) if not l.startswith('#')])]
bygid = collections.defaultdict(list)
idx = {}
for r in rows:
    bygid[r['global_id']].append(r)
    idx[(r['board'], r['refdes'], r['pin'])] = r['global_id']

ACTIVE = re.compile(r'^(U|Q|Y)\d')
PASSIVE = re.compile(r'^R\d')


def far_side(board, ref, pin):
    """Other end of a two-pin passive -> active devices on that net."""
    other = '2' if pin == '1' else '1'
    g = idx.get((board, ref, other))
    if not g:
        return []
    m = bygid[g]
    if len(m) > 20:
        return ['(rail)']
    out = []
    for r in m:
        if ACTIVE.match(r['refdes']):
            out.append(f"{r['board']}:{r['refdes']}.{r['pin']}")
        elif PASSIVE.match(r['refdes']) and not (r['board'] == board and r['refdes'] == ref):
            out += [x + '**' for x in far_side(r['board'], r['refdes'], r['pin'])]
    return out


out = []
for r in csv.DictReader([l for l in open(FANOUT) if not l.startswith('#')]):
    pin = int(r['pin'])
    name, direction = fit.get(pin, ('(absent)', '-'))
    g = r['global_id']
    members = bygid.get(g, [])
    act, conn = [], []
    if len(members) > 40:
        act = ['(rail)']
    else:
        for m in members:
            ref, p = m['refdes'], m['pin']
            if m['board'] == 'dsp' and ref == 'U3':
                continue
            if ACTIVE.match(ref):
                act.append(f"{m['board']}:{ref}.{p}")
            elif PASSIVE.match(ref):
                act += [x + ' (via %s:%s)' % (m['board'], ref) for x in far_side(m['board'], ref, p)]
            else:
                conn.append(f"{m['board']}:{ref}.{p}")
    out.append((pin, name, direction, r['canonical_name'], r['boards'],
                '; '.join(dict.fromkeys(act)) or 'NONE',
                ', '.join(conn) or '-'))

w = csv.writer(sys.stdout)
w.writerow(['pin', 'rtl_name', 'fitter_dir', 'net', 'boards', 'active_devices_besides_U3', 'connector_pins'])
for row in sorted(out):
    w.writerow(row)
