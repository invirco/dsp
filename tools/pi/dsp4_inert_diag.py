#!/usr/bin/env python3
"""dsp4_inert_diag.py — the four INERT families, diagnosed on the part.

The 2026-09-08 family walk established that ANTI_FB, GEQ, CROSSOVER and
FX_ENGINE take every write at their landed address and change no sample.
That is a symptom. This tool asks the four mechanical questions the hub's
dispatch names, one line per family, and every answer is a READ FROM THE
PART rather than a reading of the source:

  entered?   does the node's process routine execute at all -- measured as
             the whole-graph cycle count MOVING when the family's own
             parameters change the instruction stream (FX), and for the
             cascade families as the per-node cost the node-limit ladder
             attributes to the class.  A cascade whose cost is
             coefficient-independent cannot be proved live by peeking its
             coefficients, so this tool does NOT claim it from a peek.
  bypassed?  is there an On/bypass flag the kernel reads, and what is its
             landed default?  Reported as the flag's value on the part
             AFTER the family's own On cell has been written 1.
  tables?    the ACTIVE coefficient bank, peeked, against the compiled
             identity set.  If the active bank still holds the .var
             initialiser after realistic parameters have been written, the
             coefficients were never loaded -- which is the fault.
  writes?    the node's published output word, peeked, against its input
             node's.  Equal means the node writes its buffer and passes
             the sample through.

It also answers the STAGING question, which is the one that separates
"there is no kernel" from "the kernel never gets the numbers": what does
the landed address actually hit?  Every destination symbol is peeked
before and after the write, so the report says where the host's word
landed and whether anything moved it onward.

Run through inertdiag.sh, which builds, stages, boots and configures.
"""

import argparse
import json
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')

import dsp4_scope as S
from dsp4_conform import Part, SPI_ERR_COUNT, f32

BUS_AMP = 0x08000000
CAPTURE_REST = 0.50

# THE INJECTION POINT IS THE INTER-CHIP RX SLOT, not the recv node's
# published buffer: the recv kernel OVERWRITES that buffer from the slot
# every block, so driving the buffer drives nothing. The first run of this
# tool did exactly that and read every witness at peak 0x00000000 -- a
# SILENT capture, which cannot tell an inert node from a chain that never
# received the stimulus. Same three symbols dsp4_family_verify.py uses.
C2_AUX_INJ = '_rx_ic_slot_C2_RECV_AUX_01'
C2_MAIN_INJ = '_rx_ic_slot_C2_RECV_MAIN_L'
C2_FX_INJ = '_rx_ic_slot_C2_RECV_FX_01'

PROC_CYC = '_proc_cyc'
PROC_PASSES = '_proc_passes'
PROC_MAX = '_proc_cyc_max'


class Landed:
    """The landed contract, staged as JSON by tools/dsp/landed_map.py.
    Same reader as dsp4_family_verify.py: nothing here computes an
    address."""

    def __init__(self, path):
        with open(path) as fh:
            d = json.load(fh)
        self.product = d['product']
        self.pin = d.get('pin', '')
        self.sha256 = d.get('sha256', '')
        self.cells = d['cells']

    def has(self, cell):
        return cell in self.cells

    def addr(self, cell):
        return self.cells[cell][2]

    def chip(self, cell):
        return self.cells[cell][0]

    def node(self, cell):
        return self.cells[cell][3]


# ---------------------------------------------------------------------------
# THE FOUR. `stage` names the symbols that carry the family's design
# parameters, `active` the coefficient bank the kernel actually reads, and
# `identity` the compiled .var initialiser those banks hold at reset --
# the whole question for three of the four families is whether `active`
# has moved off `identity`.
# ---------------------------------------------------------------------------

# Offset-form identity, float32 arm: b0=1 n1=2 n2=-1 c1=2 c2=1
IDENT_F = (0x3F800000, 0x40000000, 0xBF800000, 0x40000000, 0x3F800000)

FAMS = {
    'GEQ': dict(
        chip=2, node='C2_AUX_GEQ_01', inject=C2_AUX_INJ,
        witness='_buf_C2_AUX_GEQ_01', upstream='_buf_C2_AUX_EQ_01',
        stage=[('_geq_gains_C2_AUX_GEQ_01', 8),
               ('_geq_coeffs_next_C2_AUX_GEQ_01', 10)],
        active=[('_geq_coeffs_A_C2_AUX_GEQ_01', 10),
                ('_geq_coeffs_B_C2_AUX_GEQ_01', 5)],
        flags=['_geq_active_C2_AUX_GEQ_01', '_geq_swap_pending_C2_AUX_GEQ_01',
               '_geq_xfade_step_C2_AUX_GEQ_01'],
        onflag=None,
        writes=[('Aux001Geq%03d' % (i + 1), f32(12.0 if i % 2 == 0 else -12.0))
                for i in range(28)],
        restore=[('Aux001Geq%03d' % (i + 1), f32(0.0)) for i in range(28)],
        setup=[('Aux001Level001', f32(1.0)), ('Aux001Mute001', 0)],
        note='28-band graphic EQ, band gain in dB'),

    'ANTI_FB': dict(
        chip=2, node='C2_AUX_AFB_01', inject=C2_AUX_INJ,
        witness='_buf_C2_AUX_AFB_01', upstream='_buf_C2_AUX_GEQ_01',
        stage=[('_afb_notch_freq_C2_AUX_AFB_01', 6),
               ('_afb_notch_gain_C2_AUX_AFB_01', 6),
               ('_afb_notch_q_C2_AUX_AFB_01', 6),
               ('_afb_coeffs_next_C2_AUX_AFB_01', 10)],
        active=[('_afb_coeffs_A_C2_AUX_AFB_01', 10),
                ('_afb_coeffs_B_C2_AUX_AFB_01', 5)],
        flags=['_afb_active_C2_AUX_AFB_01', '_afb_swap_pending_C2_AUX_AFB_01',
               '_afb_xfade_step_C2_AUX_AFB_01'],
        onflag=('_afb_on_C2_AUX_AFB_01', '_afb_ctrl_on_C2_AUX_AFB_01'),
        writes=[('Aux001AntiFbOn001', 1), ('Aux001AntiFbCtrlOn001', 1),
                ('Aux001AntiFbNotchFreq001', f32(1000.0)),
                ('Aux001AntiFbNotchQ001', f32(4.0)),
                ('Aux001AntiFbNotchGain001', f32(-18.0))],
        restore=[('Aux001AntiFbOn001', 0), ('Aux001AntiFbCtrlOn001', 0),
                 ('Aux001AntiFbNotchGain001', f32(0.0))],
        setup=[('Aux001Level001', f32(1.0)), ('Aux001Mute001', 0)],
        note='six notches per aux'),

    'CROSSOVER': dict(
        chip=2, node='C2_MAIN_XOVER', inject=C2_MAIN_INJ,
        witness='_buf_C2_MAIN_XOVER', upstream='_buf_C2_MAIN_DLY',
        stage=[('_xover_coeffs_next_C2_MAIN_XOVER', 10)],
        active=[('_xover_lp_A_C2_MAIN_XOVER', 10),
                ('_xover_hp_A_C2_MAIN_XOVER', 10)],
        flags=['_xover_active_C2_MAIN_XOVER',
               '_xover_swap_pending_C2_MAIN_XOVER',
               '_xover_xfade_step_C2_MAIN_XOVER'],
        onflag=None,
        writes=[('MainL001CrossoverFreq001', f32(500.0)),
                ('MainL001CrossoverSlope001', 24)],
        restore=[('MainL001CrossoverFreq001', f32(50.0))],
        setup=[('Main001Level001', f32(1.0)), ('Main001Mute001', 0)],
        note='one node, LP/HP split, four output chains'),

    'FX_ENGINE': dict(
        chip=2, node='C2_FX_ENG_01', inject=C2_FX_INJ,
        witness='_buf_C2_FX_ENG_01', upstream='_buf_C2_RECV_FX_01',
        stage=[('_fx_type_C2_FX_ENG_01', 1), ('_fx_mix_C2_FX_ENG_01', 1),
               ('_fx_mix_target_C2_FX_ENG_01', 1),
               ('_fx_decay_C2_FX_ENG_01', 1),
               ('_fx_feedback_C2_FX_ENG_01', 1),
               ('_fx_damp_C2_FX_ENG_01', 1)],
        active=[],
        flags=['_fx_on_C2_FX_ENG_01', '_fx_type_C2_FX_ENG_01'],
        onflag=('_fx_on_C2_FX_ENG_01',),
        writes=[('Fx001On001', 1), ('Fx001Mix001', f32(1.0)),
                ('Fx001Decay001', f32(2.0)), ('Fx001Feedback001', f32(0.8)),
                ('Fx001Damp001', f32(0.2))],
        restore=[('Fx001Mix001', f32(0.0)), ('Fx001On001', 0)],
        setup=[('Fx001Level001', f32(1.0)), ('Fx001Mute001', 0)],
        note='FX send engine; Type selects the algorithm'),
}


def peekn(part, sym, n):
    """n words from a symbol, or None for the whole row if it is absent."""
    if sym not in part.sc.sym:
        return None
    base = part.sc.sym[sym]
    out = []
    for i in range(n):
        try:
            out.append(part.sc.peek(base + i))
        except IOError:
            out.append(None)
    return out


def hexs(words, k=5):
    if words is None:
        return 'no symbol'
    return ' '.join('--------' if w is None else '%08X' % w for w in words[:k])


def capture(part, inj, src, n, offset=0, mode=1):
    time.sleep(CAPTURE_REST)
    try:
        part.sc.arm(part.sc.sym[src], inj, BUS_AMP, mode)
        part.sc.wait()
        out = []
        for i in range(offset, offset + n):
            part.sc.wr(S.SCOPE_RD, i)
            out.append(part.sc.rd(S.SCOPE_DATA))
        return out
    except (IOError, SystemExit):
        return None


def proc_cycles(part, dwell=6.0, reps=3):
    """Whole-graph cycles per block, minimum over `reps` reads.

    _proc_cyc is the block loop's own TCOUNT delta and it is republished
    every pass, so a single read is one block and one block can be long
    for reasons that have nothing to do with the graph (an SPI burst
    being serviced, the diag link answering). The minimum over several
    reads spaced by a dwell is the graph's steady cost.
    """
    if PROC_CYC not in part.sc.sym:
        return None, None
    best = None
    passes = None
    for _ in range(reps):
        time.sleep(dwell / reps)
        try:
            c = part.sc.peek(part.sc.sym[PROC_CYC])
            p = part.sc.peek(part.sc.sym[PROC_PASSES])
        except IOError:
            continue
        if not c or not p:
            continue
        passes = p
        if best is None or c < best:
            best = c
    return best, passes


def diagnose(part, L, fam, spec, n=32, log=print):
    rec = {'family': fam, 'node': spec['node'], 'note': spec['note']}
    log('')
    log('=== %s  (%s) ===' % (fam, spec['node']))

    # --- setup: put the strip in a state where a sample can reach the node
    for cell, val in spec['setup']:
        if L.has(cell):
            part.write(L.addr(cell), val, 0)
    time.sleep(0.2)

    before = {s: peekn(part, s, k) for s, k in spec['stage']}
    act_before = {s: peekn(part, s, k) for s, k in spec['active']}
    flag_before = {s: peekn(part, s, 1) for s in spec['flags']}

    inj = part.sc.sym[spec['inject']]
    # THE NULL INTERVAL IS THE FLOOR, and this tool needed one the moment
    # a family upstream started processing. `_buf_<nid>` is the LAST
    # sample of a block, so once the GEQ RINGS, two captures of the same
    # steady graph differ wherever the impulse lands at a different phase
    # of the block -- and 32 of 32 words then "move" over an interval in
    # which nothing was written. The first run after the GEQ design
    # landed read ANTI_FB as LIVE on exactly that. Same rule
    # dsp4_family_verify.py's audio phase carries.
    cap_null = capture(part, inj, spec['witness'], n)
    cap_before = capture(part, inj, spec['witness'], n)
    up_before = capture(part, inj, spec['upstream'], n)

    # --- write the family's design parameters at their landed addresses
    err0 = part.sc.rd(SPI_ERR_COUNT)
    wrote = []
    for cell, val in spec['writes']:
        if not L.has(cell):
            wrote.append({'cell': cell, 'verdict': 'NOT_IN_CONTRACT'})
            continue
        a = L.addr(cell)
        part.write(a, val, 0)
        wrote.append({'cell': cell, 'addr': a, 'word': val})
    time.sleep(0.4)
    err1 = part.sc.rd(SPI_ERR_COUNT)
    rec['spi_err_delta'] = (err1 - err0) & 0xFFFFFFFF
    rec['wrote'] = wrote

    after = {s: peekn(part, s, k) for s, k in spec['stage']}
    act_after = {s: peekn(part, s, k) for s, k in spec['active']}
    flag_after = {s: peekn(part, s, 1) for s in spec['flags']}

    cap_after = capture(part, inj, spec['witness'], n)
    up_after = capture(part, inj, spec['upstream'], n)

    rec['stage'] = {s: {'before': before[s], 'after': after[s]} for s, _ in spec['stage']}
    rec['active'] = {s: {'before': act_before[s], 'after': act_after[s]}
                     for s, _ in spec['active']}
    rec['flags'] = {s: {'before': flag_before[s], 'after': flag_after[s]}
                    for s in spec['flags']}

    log('  landed writes: %d cells, SPI_ERR delta %d'
        % (len(spec['writes']), rec['spi_err_delta']))
    for s, _ in spec['stage']:
        moved = before[s] != after[s]
        log('  stage  %-38s %s  %s' % (s, 'MOVED  ' if moved else 'unmoved',
                                       hexs(after[s])))
    for s, _ in spec['active']:
        moved = act_before[s] != act_after[s]
        ident = (act_after[s] is not None
                 and tuple(act_after[s][:5]) == IDENT_F)
        log('  active %-38s %s  %s%s'
            % (s, 'MOVED  ' if moved else 'unmoved', hexs(act_after[s]),
               '   <- compiled identity' if ident else ''))
    for s in spec['flags']:
        log('  flag   %-38s %s' % (s, hexs(flag_after[s], 1)))

    # --- audio
    def moved(a, b):
        if a is None or b is None:
            return None
        return sum(1 for x, y in zip(a, b) if x != y)

    same_as_upstream = None
    if cap_after is not None and up_after is not None:
        same_as_upstream = sum(1 for x, y in zip(cap_after, up_after) if x == y)
    floor = moved(cap_null, cap_before)
    rec['audio'] = {
        'floor': floor,
        'witness': spec['witness'], 'upstream': spec['upstream'],
        'moved_by_write': moved(cap_before, cap_after),
        'upstream_moved': moved(up_before, up_after),
        'words': n, 'equal_to_upstream': same_as_upstream,
        'peak': max((abs(w - (1 << 32) if w & 0x80000000 else w)
                     for w in (cap_after or [0])), default=0),
    }
    # A SILENT WINDOW IS NOT A VERDICT. A capture that carries no signal
    # cannot separate an inert node from a chain the stimulus never
    # reached, so it is reported as SILENT rather than as "reaches no
    # sample" -- the same rule dsp4_family_verify.py's audio phase carries.
    mv = rec['audio']['moved_by_write']
    if rec['audio']['peak'] == 0:
        rec['audio']['verdict'] = 'SILENT'
    elif floor is not None and floor >= n:
        rec['audio']['verdict'] = 'NO_FLOOR'
    elif mv is not None and floor is not None and mv > floor:
        rec['audio']['verdict'] = 'LIVE'
    elif same_as_upstream == n:
        rec['audio']['verdict'] = 'PASS_THROUGH'
    else:
        rec['audio']['verdict'] = 'UNCHANGED_BY_WRITE'
    log('  audio  %-38s floor %s/%s, moved %s/%s by the write; %s/%s words '
        'equal to %s; peak 0x%08X -> %s'
        % (spec['witness'], floor, n, mv, n,
           same_as_upstream, n, spec['upstream'], rec['audio']['peak'],
           rec['audio']['verdict']))

    # LEAVE THE FAMILY AS FOUND, so the next family is not diagnosed
    # through this one's tail. Also part of leaving the unit as found.
    for cell, val in spec.get('restore', ()):
        if L.has(cell):
            part.write(L.addr(cell), val, 0)
    time.sleep(0.3)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--landed', default='landed-d24.json')
    ap.add_argument('--families', default='')
    ap.add_argument('--n', type=int, default=32)
    ap.add_argument('--json', default='')
    ap.add_argument('--fx-type', type=int, default=3,
                    help='FX algorithm to force for the capacity arm '
                         '(3 = Reverb, the only fully implemented one)')
    args = ap.parse_args()

    L = Landed(args.landed)
    want = [f.strip() for f in args.families.split(',') if f.strip()] or list(FAMS)

    part = Part(2)
    part.sc.check_chip()
    print('chip 2 ready; contract %s sha %s' % (L.pin, L.sha256[:12]))

    out = {'contract': {'pin': L.pin, 'sha256': L.sha256,
                        'product': L.product},
           'families': [], 'capacity': {}}

    # --- CAPACITY, baseline. Read BEFORE anything is written, so the number
    #     is the graph as the product boots it.
    c0, p0 = proc_cycles(part)
    out['capacity']['baseline_cycles'] = c0
    out['capacity']['baseline_passes'] = p0
    print('capacity: baseline whole-graph %s cycles/block (passes %s)' % (c0, p0))

    for fam in want:
        if fam not in FAMS:
            print('no such family %r' % fam)
            continue
        try:
            out['families'].append(diagnose(part, L, fam, FAMS[fam], args.n))
        except (IOError, SystemExit) as exc:
            out['families'].append({'family': fam, 'error': str(exc)})
            print('  ERROR %s' % exc)

    # --- CAPACITY with the four families driven as hard as this firmware
    #     allows. Only FX_ENGINE has an instruction stream that depends on
    #     its parameters; the cascade families run the same stages either
    #     way, which is itself the finding and is measured here rather
    #     than asserted.
    c1, _ = proc_cycles(part)
    out['capacity']['after_params_cycles'] = c1
    print('')
    print('capacity: with every landed parameter written  %s cycles/block' % c1)

    # ---- CAPACITY with every GEQ in the graph designed NON-FLAT.
    # This is the measurement that settles whether the 09-03 fit numbers
    # already carry the cost of the graphic EQ. The cascade issues the
    # same instruction stream whatever its coefficients hold -- but that
    # is an argument, and until the design landed there was no way to
    # test it on the part, because no GEQ had ever held a coefficient
    # other than the identity.
    geq_nodes = (['Aux%03dGeq%%03d' % i for i in range(1, 13)]
                 + ['Grp%03dGeq%%03d' % i for i in range(1, 5)]
                 + ['Main001Geq%03d'])
    wrote_geq = 0
    for fmt in geq_nodes:
        for b in range(1, 29):
            cell = fmt % b
            if L.has(cell):
                part.write(L.addr(cell), f32(12.0 if b % 2 else -12.0), 0)
                wrote_geq += 1
    time.sleep(1.0)
    c_geq, _ = proc_cycles(part)
    out['capacity']['geq_cells_written'] = wrote_geq
    out['capacity']['geq_active_cycles'] = c_geq
    print('capacity: every GEQ non-flat (%d cells)          %s cycles/block'
          % (wrote_geq, c_geq))
    if c0 and c_geq:
        print('capacity: GEQ-active delta vs baseline       %+d cycles/block'
              % (c_geq - c0))

    fx_nodes = ['C2_FX_ENG_%02d' % i for i in range(1, 7)]
    fx_cells = ['Fx%03dType001' % i for i in range(1, 7)]
    forced = []
    for cell in fx_cells:
        if L.has(cell):
            part.write(L.addr(cell), args.fx_type, 0)
            forced.append(cell)
    time.sleep(0.5)
    c2, _ = proc_cycles(part)
    out['capacity']['fx_type'] = args.fx_type
    out['capacity']['fx_forced_cells'] = forced
    out['capacity']['fx_active_cycles'] = c2
    out['capacity']['fx_type_readback'] = [
        peekn(part, '_fx_type_%s' % n, 1) for n in fx_nodes]
    print('capacity: FX Type=%d on %d engines            %s cycles/block'
          % (args.fx_type, len(forced), c2))
    if c1 and c2:
        print('capacity: FX reverb delta                    %+d cycles/block'
              % (c2 - c1))

    # leave the unit as found: engines back to Type 0, every GEQ flat
    for cell in forced:
        part.write(L.addr(cell), 0, 0)
    for fmt in geq_nodes:
        for b in range(1, 29):
            cell = fmt % b
            if L.has(cell):
                part.write(L.addr(cell), f32(0.0), 0)
    time.sleep(0.5)
    c_end, _ = proc_cycles(part)
    out['capacity']['restored_cycles'] = c_end
    print('capacity: restored (every GEQ flat, FX Type 0)  %s cycles/block'
          % c_end)

    if args.json:
        with open(args.json, 'w') as fh:
            json.dump(out, fh, indent=1)
        print('wrote %s' % args.json)
    return 0


if __name__ == '__main__':
    sys.exit(main())
