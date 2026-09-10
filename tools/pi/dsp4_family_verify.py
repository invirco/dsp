#!/usr/bin/env python3
"""dsp4_family_verify.py — every D24 kernel family, on the part, addressed
THROUGH THE LANDED CONTRACT.

WHAT IS NEW HERE, and it is not another probe. Every hardware instrument
this bench has ever run reached its parameters by arithmetic:
`(strip - 1) * 144 + 0x0029` for a gate threshold, transcribed out of
`dsp_address_map.md` into a constant at the top of a script. That is a
second opinion about the address map. Since defs-v2026.09.08.2 there is a
LANDED one -- `defs/products/<p>/dsp.csv`, proposed by this repo and
landed by the hub -- and this tool resolves every address it writes by
CELL NAME out of that file. An address it cannot find is a missing row in
the contract, and an address that does not answer is a defect in one of
the two; either way the run says which cell.

    landed dsp.csv  --(landed_map.py --json)-->  staged next to the images
                    --> cell name -> (chip, page, addr) -> the SPI link

THREE PHASES, and they answer three different questions.

  CONTRACT   For every family, every `rw` cell of a representative node is
             written at its landed address and read back, with the part's
             own `SPI_ERR_COUNT` either side. The handler increments that
             counter only when the dispatch entry is 0 or the address is
             out of bounds, so it separates "the kernel consumed the word"
             from "there is nothing at this address" -- which a read-back
             of 0 cannot. Output: per family, how many landed addresses
             ANSWER.

  NUMERIC    The families that have a reference model are run against it
             on captured samples and must match WORD FOR WORD. This does
             not re-implement the comparison: it calls the run_node() the
             goldnode bar already uses, so GATE, COMP, TUBE, FDR and the
             biquad conversion are scored by the instrument that carries
             their negative controls.

  AUDIO      For every family with a node in the capture chain, the family
             is driven and a node buffer captured, and the family must
             MOVE THE AUDIO -- a landed address that answers and reaches
             no sample is exactly the D38 inert surface, and it is
             reported as inert rather than as a pass.

A family with no kernel is NOT a failure and is not scored as one. It is
reported as `no-kernel` with the reason, because the coverage fraction
this run exists to produce has to be honest about its own denominator.

Usage, on the bench:
    python3 dsp4_family_verify.py --landed landed-d24.json \\
            [--families GAIN,GATE,...] [--json out.json] [--strip 1]
Run through famverify.sh, which builds, stages and boots.
"""

import argparse
import json
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')

import dsp4_scope as S
import fixed_ref as fr
from dsp4_conform import (Part, SPI_ERR_COUNT, bus_capture, f32,
                          drive_strip)

# ---------------------------------------------------------------------------
# The landed map, staged. The bench has no `defs` checkout, so the contract
# arrives as the flat JSON tools/dsp/landed_map.py writes. Nothing below
# computes an address.
# ---------------------------------------------------------------------------


class Landed:
    def __init__(self, path):
        with open(path) as fh:
            d = json.load(fh)
        self.product = d['product']
        self.pin = d.get('pin', '')
        self.sha256 = d.get('sha256', '')
        self.cells = d['cells']

    def has(self, cell):
        return cell in self.cells

    def e(self, cell):
        try:
            return self.cells[cell]
        except KeyError:
            raise KeyError('cell %r is not in the landed map for %s'
                           % (cell, self.product))

    def chip(self, cell):
        return self.e(cell)[0]

    def addr(self, cell):
        return self.e(cell)[2]

    def node(self, cell):
        return self.e(cell)[3]

    def nodetype(self, cell):
        return self.e(cell)[4]

    def access(self, cell):
        return self.e(cell)[5]

    def nodes_of(self, ntype):
        return sorted({e[3] for e in self.cells.values() if e[4] == ntype})

    def cells_of_node(self, node):
        return sorted(c for c, e in self.cells.items() if e[3] == node)

    def families(self):
        out = {}
        for e in self.cells.values():
            out[e[4]] = out.get(e[4], 0) + 1
        return out


# ---------------------------------------------------------------------------
# THE CROSS-CHECK. Every constant the existing bench harness reaches its
# parameters by, named as the CELL it is meant to be, so the run can say
# whether the transcription and the contract agree. A disagreement here is
# the whole reason this file exists: it means every measurement taken
# through the old constant was taken at an address the contract does not
# name.
# ---------------------------------------------------------------------------

TRANSCRIBED = {
    # dsp4_conform.py / dsp4_node_verify.py constant  : landed cell (strip 1)
    'GAIN_OFF   0x0000': ('Chan001Gain001', 0x0000),
    'FILT_HPF   0x0004': ('Chan001EqHpf001', 0x0004),
    'FILT_LPF   0x000A': ('Chan001EqLpf001', 0x000A),
    'EQ_B1      0x0010': ('Chan001EqFreq001', 0x0010),
    'GATE_ON    0x0028': ('Chan001GateOn001', 0x0028),
    'GATE_THR   0x0029': ('Chan001GateThr001', 0x0029),
    'GATE_ATT   0x002A': ('Chan001GateAtt001', 0x002A),
    'GATE_HOLD  0x002B': ('Chan001GateHold001', 0x002B),
    'GATE_REL   0x002C': ('Chan001GateRel001', 0x002C),
    'GATE_RNG   0x002D': ('Chan001GateRng001', 0x002D),
    'COMP_ON    0x0038': ('Chan001CompOn001', 0x0038),
    'COMP_THR   0x0039': ('Chan001CompThr001', 0x0039),
    'COMP_RATIO 0x003A': ('Chan001CompRat001', 0x003A),
    'COMP_ATT   0x003B': ('Chan001CompAtt001', 0x003B),
    'COMP_REL   0x003C': ('Chan001CompRel001', 0x003C),
    'COMP_MKUP  0x003D': ('Chan001CompMake001', 0x003D),
    'COMP_KNEE  0x003E': ('Chan001CompKnee001', 0x003E),
    'COMP_PAR   0x003F': ('Chan001CompPar001', 0x003F),
    'TUBE_ON    0x004C': ('Chan001TubeOn001', 0x004C),
    'TUBE_SAT   0x004D': ('Chan001TubeSat001', 0x004D),
    'DLY_OFF    0x004E': ('Chan001Delay001', 0x004E),
    'FDR_LEVEL  0x0050': ('Chan001Level001', 0x0050),
    'FDR_PAN    0x0051': ('Chan001Pan001', 0x0051),
    'FDR_MUTE   0x0052': ('Chan001Mute001', 0x0052),
    'RTG_MAINON 0x0054': ('Chan001MainOn001', 0x0054),
}


def cross_check(L, log=print):
    """Every transcribed constant against the landed address for its cell."""
    rows, bad = [], 0
    for label, (cell, const) in sorted(TRANSCRIBED.items()):
        if not L.has(cell):
            rows.append({'constant': label, 'cell': cell,
                         'verdict': 'NOT_IN_CONTRACT'})
            bad += 1
            continue
        got = L.addr(cell)
        ok = got == const
        rows.append({'constant': label, 'cell': cell, 'landed': got,
                     'transcribed': const,
                     'verdict': 'AGREE' if ok else 'DISAGREE'})
        if not ok:
            bad += 1
            log('  DISAGREE %-18s %s: transcribed 0x%04X, landed 0x%04X'
                % (label, cell, const, got))
    log('  cross-check: %d of %d transcribed constants agree with the '
        'landed contract' % (len(rows) - bad, len(rows)))
    return rows, bad


# ---------------------------------------------------------------------------
# FAMILY TABLE. One representative node per family per chip, the cell that
# proves the family reaches audio, and where the capture is taken.
#
# `probe` is the cell written to move the audio and the two values to
# write; `witness` is the buffer captured. A family with witness=None has
# no capture point in this build's chain and is scored on CONTRACT alone,
# which the report says in as many words.
# ---------------------------------------------------------------------------

# Injection points. Chip 1 takes the step into its input slot after
# scatter; chip 2 has no converter input of its own and receives over the
# inter-chip SPORT, so its injection point is the RECEIVE slot the chain
# starts from. NO_INJECT names a node that generates its own signal and
# must be captured with the scope injecting nothing; inject=None names a
# family this bench has no stimulus path to at all, and it is reported as
# such rather than as an inert one.
C1_INJ = '_rx_slot_C1_IN_01'
C1_CODEC_INJ = '_rx_slot_C1_XIN_CODEC_01'
C2_AUX_INJ = '_rx_ic_slot_C2_RECV_AUX_01'
C2_FX_INJ = '_rx_ic_slot_C2_RECV_FX_01'
C2_MAIN_INJ = '_rx_ic_slot_C2_RECV_MAIN_L'
NO_INJECT = 'NONE'

# THE STEP IS DC, and that decides what a probe is allowed to be. The
# scope's step stimulus is a constant -0.5, so by the time the capture
# window opens at sample 900 the only thing a filter can change about it
# is its DC GAIN. A peaking EQ at 1 kHz has unity gain at DC and would
# read INERT on a step no matter how well it works, which is a wrong
# answer, not a cautious one -- so the biquad families are probed with a
# coefficient set whose DC gain moves (a high-pass, a low shelf) and the
# delay is probed at capture offset 0, where a delay is the difference
# between a step and silence.

FAMILIES = {
    'GAIN': dict(chip=1, node='C1_GAIN_01', inject=C1_INJ,
                 witness='_buf_C1_GAIN_01',
                 probe=('Chan001Gain001', f32(1.0), f32(4.0)),
                 note='per-strip input trim'),
    'HPF_LPF': dict(chip=1, node='C1_FILT_01', inject=C1_INJ,
                    witness='_buf_C1_FILT_01', kind='biquad',
                    stim='impulse', offset=0,
                    probe=('Chan001EqHpf001', 'unity', 'hpf4k'),
                    note='strip HPF/LPF, one biquad pair'),
    'EQ_BIQUAD': dict(chip=1, node='C1_EQ_01', inject=C1_INJ,
                      witness='_buf_C1_EQ_01', kind='biquad', bands=4,
                      stim='impulse', offset=0,
                      probe=('Chan001EqGain001', 'unity', 'loshelf12'),
                      note='4-band parametric, float cascade'),
    'GATE': dict(chip=1, node='C1_GATE_01', inject=C1_INJ,
                 witness='_buf_C1_GATE_01',
                 probe=('Chan001GateThr001', f32(-80.0), f32(0.0)),
                 # HOLD IN MILLISECONDS, which is what the cell has
                 # declared all along and what the wire now carries. The
                 # first run of this bar had to write a raw 48 here,
                 # because `_gate_hold_*` is an integer sample count and
                 # the handler stored the host's float32 word into it
                 # unconverted -- the documented 1.0 ms became
                 # 1,065,353,216 samples and the gate never closed again.
                 # Fixed 2026-09-08 at the SPI boundary from the landed
                 # wire-units.csv; verified on the part, 1.0 -> 48 and
                 # 50.0 -> 2400, and the read comes back in ms.
                 setup=[('Chan001GateOn001', 1),
                        ('Chan001GateHold001', f32(1.0))],
                 note='ladder + hold + range'),
    'COMPRESSOR': dict(chip=1, node='C1_COMP_01', inject=C1_INJ,
                       witness='_buf_C1_COMP_01',
                       probe=('Chan001CompThr001', f32(0.0), f32(-40.0)),
                       # FAST TIME CONSTANTS SO THE NULL INTERVAL HAS A
                       # FLOOR. At drive_strip's 0.002 alpha the envelope
                       # has not settled between two captures and they
                       # differ in all 32 words, which leaves the probe no
                       # discrimination at all (measured 2026-09-08:
                       # floor 32/32, probe delta only 2.3x the null
                       # delta). A ~0.5 alpha settles inside the rest.
                       setup=[('Chan001CompOn001', 1),
                              ('Chan001CompPar001', f32(100.0)),
                              ('Chan001CompAtt001', f32(0.5)),
                              ('Chan001CompRel001', f32(0.5))],
                       note='gain computer + makeup + parallel blend'),
    'TUBE_SAT': dict(chip=1, node='C1_TUBE_01', inject=C1_INJ,
                     witness='_buf_C1_TUBE_01',
                     probe=('Chan001TubeSat001', f32(0.0), f32(1.0)),
                     setup=[('Chan001TubeOn001', 1)],
                     note='three chained roundings'),
    'DELAY': dict(chip=1, node='C1_DLY_01', inject=C1_INJ,
                  witness='_buf_C1_DLY_01', offset=0,
                  probe=('Chan001Delay001', f32(0.0), f32(250.0)),
                  note='per-strip delay line; probed at capture offset 0, '
                       'where a delay is a step against silence'),
    'FADER_PAN': dict(chip=1, node='C1_FDR_01', inject=C1_INJ,
                      witness='_buf_C1_FDR_01',
                      probe=('Chan001Level001', f32(1.0), f32(0.25)),
                      note='level coefficient + pan legs'),
    'ROUTING': dict(chip=1, node='C1_RTG_01', inject=C1_INJ,
                    witness='_buf_C1_BUS_AUX_01',
                    probe=('Chan001AuxSend001', f32(1.0), f32(0.25)),
                    setup=[('Chan001AuxOn001', 1)],
                    note='crosspoints into every bus'),
    'METER': dict(chip=1, node='C1_MTR_01', inject=C1_INJ, witness=None,
                  probe=None, meter='_mtr_peak_C1_MTR_01',
                  meter_src='_buf_C1_GAIN_01',
                  note='read-only peak/rms/gr words; changes no sample, so '
                       'its verdict is the readback against the capture'),
    'NOISE_GEN': dict(chip=1, node='C1_NOISE', inject=NO_INJECT,
                      witness='_buf_C1_NOISE',
                      probe=('Noise001On001', 0, 1),
                      setup=[('Noise001Level001', f32(1.0))],
                      note='generator: captured with the scope injecting '
                           'nothing'),
    'TALKBACK': dict(chip=1, node='C1_TALK_01', inject=C1_CODEC_INJ,
                     witness='_buf_C1_TALK_01',
                     probe=('Talk001Gain001', f32(1.0), f32(4.0)),
                     setup=[('Talk001On001', 1)],
                     note='talkback injection node, fed from the codec '
                          'return rather than the strip input'),
    # ---- chip 2: the aux chain is RECV_AUX -> FDR -> EQ -> GEQ -> AFB ->
    # LIM -> DLY -> OUT, so one injection point walks six families.
    # THE PROBED BAND IS 18, NOT 1, AND THE REASON IS THE WINDOW. Band 1
    # of the ISO third-octave set is 19.95 Hz: its impulse response takes
    # 2,400 samples to ring once, so over the 32-sample capture a +12 dB
    # boost moves b0 by 4e-4 and the family would read INERT for a
    # graphic EQ that is working perfectly. Band 18 is 1 kHz, which the
    # window resolves; dsp4_geq_verify.py scores the whole band set
    # against the model and is where the numeric verdict lives.
    'GEQ': dict(chip=2, node='C2_AUX_GEQ_01', inject=C2_AUX_INJ,
                witness='_buf_C2_AUX_GEQ_01', stim='impulse', offset=0,
                probe=('Aux001Geq018', f32(0.0), f32(12.0)),
                setup=[('Aux001Level001', f32(1.0)), ('Aux001Mute001', 0)],
                note='28-band graphic EQ, one gain in dB per band'),
    'ANTI_FB': dict(chip=2, node='C2_AUX_AFB_01', inject=C2_AUX_INJ,
                    witness='_buf_C2_AUX_AFB_01', stim='impulse', offset=0,
                    probe=('Aux001AntiFbNotchGain001', f32(0.0), f32(-18.0)),
                    setup=[('Aux001Level001', f32(1.0)),
                           ('Aux001Mute001', 0),
                           ('Aux001AntiFbOn001', 1),
                           ('Aux001AntiFbCtrlOn001', 1),
                           ('Aux001AntiFbNotchFreq001', f32(1000.0)),
                           ('Aux001AntiFbNotchQ001', f32(4.0))],
                    note='six notches per aux'),
    'LIMITER': dict(chip=2, node='C2_AUX_LIM_01', inject=C2_AUX_INJ,
                    witness='_buf_C2_AUX_LIM_01',
                    probe=('Aux001LimiterThr001', f32(0.0), f32(-30.0)),
                    setup=[('Aux001Level001', f32(1.0)),
                           ('Aux001Mute001', 0),
                           ('Aux001LimiterOn001', 1)],
                    note='output-side limiter'),
    # TYPE IS LEFT AT ITS DEFAULT HERE, DELIBERATELY, AND THAT IS WHY
    # THIS FAMILY READS INERT.
    #
    # `_fx_type` defaults to 0 = Echo and the algorithm dispatch has cases
    # only for 2 (Doubling) and 3 (Reverb); everything else falls through
    # to a dry pass-through, so the inert verdict is true of the shipping
    # configuration and not of the kernel. Setting Type = 3 was tried on
    # 2026-09-08 and made the whole FX chain read SILENT -- peak zero on
    # both arms, where the default Type carries the impulse -- so the
    # reverb path does not merely fail to reverberate, it takes the
    # sample with it. `_C2_FX_ENG_01_process` sets NO L register and then
    # uses `modify(i0, m0)` four times on its comb and delay buffers,
    # which every other kernel in this tree guards with `l0 = 0`; that is
    # the first thing to check. Until it is, driving Type from a bar that
    # runs against the whole graph risks scribbling through a circular
    # buffer of whatever length the previous node left behind.
    'FX_ENGINE': dict(chip=2, node='C2_FX_ENG_01', inject=C2_FX_INJ,
                      witness='_buf_C2_FX_ENG_01', stim='impulse', offset=0,
                      probe=('Fx001Mix001', f32(0.0), f32(100.0)),
                      setup=[('Fx001On001', 1),
                             ('Fx001Level001', f32(1.0)),
                             ('Fx001Mute001', 0)],
                      note='FX send engine; Type defaults to 0 = Echo, '
                           'which the dispatch does not implement'),
    'DCA': dict(chip=2, node='C2_DCA_01', inject=None, witness=None,
                probe=None,
                note='HOST-MANAGED since the 2026-08-30 ruling (D57) — the '
                     'DSP applies no DCA gain, so there is nothing on the '
                     'part for an audio probe to find'),
    'AUX_INPUT': dict(chip=2, node='C2_BT_IN', inject=None,
                      witness='_buf_C2_BT_IN',
                      probe=('Bt001Level001', f32(1.0), f32(0.25)),
                      setup=[('Bt001On001', 1)],
                      note='BT/USB/codec auxiliary input; its samples arrive '
                           'on a TDM slot this bench cannot drive'),
    'CROSSOVER': dict(chip=2, node='C2_MAIN_XOVER', inject=C2_MAIN_INJ,
                      witness='_buf_C2_MAIN_OEQ_01', stim='impulse',
                      offset=0,
                      probe=('MainL001CrossoverFreq001', f32(60.0),
                             f32(500.0)),
                      setup=[('Main001Level001', f32(1.0)),
                             ('Main001Mute001', 0)],
                      note='one node, four output chains'),
    'MONITOR': dict(chip=2, node='C2_MON', inject=C2_MAIN_INJ,
                    witness='_buf_C2_MON',
                    probe=('Mon001Level001', f32(1.0), f32(0.25)),
                    setup=[('Main001Level001', f32(1.0)),
                           ('Main001Mute001', 0)],
                    note='monitor bus tap'),
    # ---- S23: the matrix, and the FX returns' two destinations ---------
    #
    # THREE OF THESE FOUR ARE NOT NODE TYPES, and that is why the walk's
    # default family list is the union of the landed NodeTypes and this
    # table rather than the NodeTypes alone. `Matrix*Level/Mute` are cells
    # of a FADER_PAN and `Chan*MatrixSend/On` are cells of a ROUTING, so a
    # NodeType-keyed walk can only ever report the matrix as part of two
    # families that were already passing -- which is exactly how a feature
    # can be shipped un-witnessed. `contract_cells` names the cells each
    # entry is answerable for, so the sweep is precise instead of
    # re-writing sixty routing words for the four that are new.
    'MATRIX': dict(chip=1, node='C1_RTG_01', inject=C1_INJ,
                   witness='_buf_C1_BUS_MTX_01',
                   probe=('Chan001MatrixSend001', f32(1.0), f32(0.25)),
                   setup=[('Chan001MainOn001', 0),
                          ('Chan001MatrixOn001', 1)],
                   contract_cells=['Chan001MatrixOn001', 'Chan001MatrixOn002',
                                   'Chan001MatrixSend001',
                                   'Chan001MatrixSend002'],
                   note='channel -> matrix bus crosspoint (S22 gate 1); '
                        'MainOn is taken off so the matrix send is the only '
                        'live crosspoint on the strip'),
    'MATRIX_OUT': dict(chip=2, node='C2_MTX_FDR_01',
                       inject='_rx_ic_slot_C2_RECV_MTX_01',
                       witness='_buf_C2_MTX_FDR_01',
                       probe=('Matrix001Level001', f32(1.0), f32(0.25)),
                       setup=[('Matrix001Mute001', 0)],
                       contract_cells=['Matrix%03dLevel001' % m
                                       for m in range(1, 5)]
                                      + ['Matrix%03dMute001' % m
                                         for m in range(1, 5)],
                       note='matrix output strip: level + mute, on '
                            'NET_OUT_02..05'),
    # Gate 2. The FX return had NO PATH TO ANY BUS until S23 (S22-2), so
    # this entry is the standing bar for the wiring as much as for the
    # cells: witnessed at the MAIN MIX, which is the node whose `inputs`
    # was missing the return.
    'FX_RETURN': dict(chip=2, node='C2_FX_FDR_01', inject=C2_FX_INJ,
                      witness='_buf_C2_MIX_MAIN_L',
                      probe=('Fx001Level001', f32(1.0), f32(0.25)),
                      setup=[('Fx001On001', 1), ('Fx001Mute001', 0),
                             ('Fx001Mix001', f32(100.0))],
                      contract_cells=['Fx001Level001', 'Fx001Mute001'],
                      note='FX return -> main mix (S22-2); Type is left at '
                           'its default 0 = Echo for FX_ENGINE\'s reason'),
    # Gate 3. MIX_BUS IS a NodeType and it had no cells at all before
    # S23 -- the 144 Fx*AuxOn/AuxSend words live on C2_MIX_AUX_01..12.
    'MIX_BUS': dict(chip=2, node='C2_MIX_AUX_01', inject=C2_FX_INJ,
                    witness='_buf_C2_MIX_AUX_01',
                    probe=('Fx001AuxSend001', f32(1.0), f32(0.25)),
                    setup=[('Fx001On001', 1), ('Fx001Mute001', 0),
                           ('Fx001Level001', f32(1.0)),
                           ('Fx001Mix001', f32(100.0)),
                           ('Aux001Mute001', 0),
                           ('Fx001AuxOn001', 1)],
                    contract_cells=['Fx001AuxOn001', 'Fx001AuxSend001',
                                    'Fx002AuxOn001', 'Fx002AuxSend001'],
                    note='FX return -> aux bus crosspoint (S23 gate 3); the '
                         'send level is a LINEAR gain, as Chan*AuxSend is'),
}

# ---------------------------------------------------------------------------
# BIQUAD PROBE SETS. A biquad cell names the BASE of a coefficient set, not
# a scalar: the landed map gives Chan001EqFreq001, EqGain001 and EqQ001 the
# same address 0x0010 with RampScope=CoeffSetAtomic, because the host
# resolves f0/gain/Q into five RBJ coefficients and writes them as one set.
# So the probe writes the set the host would write, then the node's SWAP
# trigger -- base + 5*bands -- which is what makes a written set take
# effect. Probing the base word alone would poke b0 into a live cascade,
# which is not what any host does and not what the cell means.
# ---------------------------------------------------------------------------

def _rbj_unity():
    return (1.0, 0.0, 0.0, 0.0, 0.0)


def _rbj_highpass(f0, q=0.707, fs=48000.0):
    import math
    w0 = 2.0 * math.pi * f0 / fs
    al = math.sin(w0) / (2.0 * q)
    c = math.cos(w0)
    b0, b1, b2 = (1 + c) / 2, -(1 + c), (1 + c) / 2
    a0, a1, a2 = 1 + al, -2 * c, 1 - al
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


def _rbj_lowshelf(f0, gain_db, s=1.0, fs=48000.0):
    import math
    A = 10.0 ** (gain_db / 40.0)
    w0 = 2.0 * math.pi * f0 / fs
    c, sn = math.cos(w0), math.sin(w0)
    al = sn / 2.0 * math.sqrt((A + 1 / A) * (1 / s - 1) + 2)
    tsa = 2 * math.sqrt(A) * al
    b0 = A * ((A + 1) - (A - 1) * c + tsa)
    b1 = 2 * A * ((A - 1) - (A + 1) * c)
    b2 = A * ((A + 1) - (A - 1) * c - tsa)
    a0 = (A + 1) + (A - 1) * c + tsa
    a1 = -2 * ((A - 1) + (A + 1) * c)
    a2 = (A + 1) + (A - 1) * c - tsa
    return (b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0)


COEFF_SETS = {
    'unity': _rbj_unity(),
    'hpf4k': _rbj_highpass(4000.0),
    'loshelf12': _rbj_lowshelf(200.0, 12.0),
}


def write_coeffset(part, base, name, bands=1):
    """Write one named RBJ set into every band, then pull the swap trigger."""
    c = COEFF_SETS[name]
    for band in range(bands):
        for i, v in enumerate(c):
            part.write(base + band * 5 + i, f32(v), 0)
    part.write(base + bands * 5, 1, 0)          # SWAP
    time.sleep(0.10)


# ---------------------------------------------------------------------------
# CONTRACT PHASE
# ---------------------------------------------------------------------------

def contract_phase(part, L, node, log=print, cells=None):
    """Write every rw cell of one node at its LANDED address; read it back;
    count the part's own SPI errors either side.

    `cells` overrides the node's cell list, for the S23 entries whose cells
    belong to a node OTHER families already sweep: `Chan*MatrixSend/On` are
    four of C1_RTG_01's sixty words, and re-writing the other fifty-six to
    reach them would be sixty transactions and a disturbed router for no
    extra evidence. A named cell the landed contract does not carry is
    reported as NOT_IN_CONTRACT rather than skipped, because a harness
    entry naming a cell that no longer exists is a stale harness.

    The verdict per address:
      ANSWERS   the write raised no SPI error -- the dispatch table has an
                entry for it
      NO_ENTRY  every write raised one -- the address is out of bounds or
                the dispatch entry is 0
      MIXED     some writes errored and some did not; the link dropped
                words and the address cannot be classified from this run
    """
    out = []
    for cell in (cells if cells is not None else L.cells_of_node(node)):
        if not L.has(cell):
            out.append({'cell': cell, 'verdict': 'NOT_IN_CONTRACT'})
            continue
        if L.access(cell) != 'rw':
            out.append({'cell': cell, 'addr': L.addr(cell),
                        'access': L.access(cell), 'verdict': 'NOT_RW'})
            continue
        addr = L.addr(cell)
        rec = {'cell': cell, 'addr': addr, 'access': 'rw'}
        try:
            err0 = part.read(SPI_ERR_COUNT)
            orig = part.read(addr)
            writes = 0
            reads = []
            for w in (0x00000000, 0x3F800000):
                part.write(addr, w, 0)
                writes += 1
                reads.append(part.read(addr))
            part.write(addr, orig, 0)
            writes += 1
            err1 = part.read(SPI_ERR_COUNT)
            d = (err1 - err0) & 0xFFFFFFFF
            rec.update(orig=orig, reads=reads, writes=writes, err_delta=d)
            rec['verdict'] = ('ANSWERS' if d == 0 else
                              'NO_ENTRY' if d == writes else 'MIXED')
        except IOError as exc:
            rec['verdict'] = 'ERROR'
            rec['error'] = str(exc)
        out.append(rec)
    ans = sum(1 for r in out if r['verdict'] == 'ANSWERS')
    rw = sum(1 for r in out if r.get('access') == 'rw')
    log('  contract: %d of %d rw cells on %s answer at their landed address'
        % (ans, rw, node))
    for r in out:
        if r['verdict'] in ('NO_ENTRY', 'ERROR', 'MIXED'):
            log('    %-32s 0x%04X  %s' % (r['cell'], r['addr'], r['verdict']))
    return out


CAPTURE_REST = 0.50
BUS_AMP = 0x08000000              # -6 dBFS in Q4.28, the injected step


def capture(part, inj, src, n, offset, mode=2):
    """One armed capture, resting the graph first and reading the window
    and the STIMULUS the family needs.

    bus_capture() is fixed at a step and offset 900. That is right for
    anything with a time constant and wrong twice over: it is blind to a
    delay line, and a step is DC, so a filter whose gain at DC does not
    move cannot be seen with it at all. A 28-band GEQ's band 1 sits near
    25 Hz and a peaking section has unity gain at DC -- so the first run
    of this bar read GEQ, ANTI_FB and CROSSOVER as INERT when what it had
    measured was its own stimulus. mode=1 is the impulse, and an impulse
    response is frequency-complete."""
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


# ---------------------------------------------------------------------------
# AUDIO PHASE
# ---------------------------------------------------------------------------

def audio_phase(part, L, fam, spec, n=32, log=print):
    """Drive the family between two states; the captured node buffer must
    MOVE. A landed address that answers and reaches no sample is the D38
    inert surface, and it is reported as inert rather than as a pass."""
    rec = {'family': fam, 'witness': spec['witness'],
           'inject': spec.get('inject'), 'kind': spec.get('kind', 'scalar')}
    if spec['witness'] is None or spec['probe'] is None:
        rec['verdict'] = 'NO_PROBE'
        log('  audio: %-12s no probe point — %s' % (fam, spec['note']))
        return rec
    if spec.get('inject') is None:
        rec['verdict'] = 'NO_STIMULUS_PATH'
        log('  audio: %-12s no stimulus path on this bench' % fam)
        return rec
    syms = [spec['witness']]
    if spec['inject'] != NO_INJECT:
        syms.append(spec['inject'])
    for sym in syms:
        if sym not in part.sc.sym:
            rec['verdict'] = 'NO_SYMBOL'
            rec['missing'] = sym
            log('  audio: %-12s no symbol %s' % (fam, sym))
            return rec
    inj = 0 if spec['inject'] == NO_INJECT else part.sc.sym[spec['inject']]
    offset = spec.get('offset', 900)
    mode = 1 if spec.get('stim') == 'impulse' else 2
    cell, lo, hi = spec['probe']
    if not L.has(cell):
        rec['verdict'] = 'CELL_NOT_IN_CONTRACT'
        rec['cell'] = cell
        return rec
    addr = L.addr(cell)
    rec.update(cell=cell, addr=addr, offset=offset,
               stim=spec.get('stim', 'step'))

    def apply(state):
        if rec['kind'] == 'biquad':
            write_coeffset(part, addr, state, spec.get('bands', 1))
        else:
            part.write(addr, state, 4)
        time.sleep(0.30)

    try:
        # SETUP FIRST, and every setup address comes out of the contract
        # too. A family whose On flag is clear passes its input through
        # untouched, and the probe would then read INERT for a node that
        # is simply switched off -- the wrong answer, not a cautious one.
        setup = []
        for scell, sval in spec.get('setup', ()):
            if not L.has(scell):
                setup.append({'cell': scell, 'verdict': 'NOT_IN_CONTRACT'})
                continue
            part.write(L.addr(scell), sval, 0)
            setup.append({'cell': scell, 'addr': L.addr(scell), 'wrote': sval})
        rec['setup'] = setup
        time.sleep(0.2)

        # THE NULL INTERVAL IS THE FLOOR. Two captures with nothing written
        # between them: whatever moves there is what the graph does on its
        # own, and a family whose probe moves no more than that has not
        # been shown to do anything.
        apply(lo)
        a = capture(part, inj, spec['witness'], n, offset, mode)
        b = capture(part, inj, spec['witness'], n, offset, mode)
        if a is None or b is None:
            rec['verdict'] = 'NO_CAPTURE'
            log('  audio: %-12s capture failed' % fam)
            return rec
        floor = sum(1 for x, y in zip(a, b) if x != y)
        apply(hi)
        c = capture(part, inj, spec['witness'], n, offset, mode)
        if c is None:
            rec['verdict'] = 'NO_CAPTURE'
            log('  audio: %-12s capture failed' % fam)
            return rec
        moved = sum(1 for x, y in zip(b, c) if x != y)

        def _pk(words):
            return max((abs(w - (1 << 32) if w & 0x80000000 else w)
                        for w in words), default=0)
        pk_lo, pk_hi = _pk(b), _pk(c)
        pk = max(pk_lo, pk_hi)
        # COUNTING WORDS IS NOT ENOUGH, and the first bench run proved it:
        # the compressor's envelope sits in a rounding limit cycle, so two
        # captures over a NULL interval differ in all 32 words and a probe
        # that changes the output completely still scores `moved == floor`.
        # The magnitudes separate them where the counts cannot.
        fd = max((abs(x - y) for x, y in zip(a, b)), default=0)
        pd = max((abs(x - y) for x, y in zip(b, c)), default=0)
        rec.update(floor=floor, moved=moved, words=n, peak=pk,
                   peak_lo=pk_lo, peak_hi=pk_hi,
                   floor_delta=fd, probe_delta=pd)
        # THE PEAK RATIO IS THE THIRD DISCRIMINATOR, and for the dynamics
        # it is the only one that works. A gate that shuts drops its
        # output ~36 dB; a compressor 34 dB over threshold at 4:1 takes
        # ~25 dB off. Both are unmistakable in the peak and both can hide
        # in a word count, because their envelopes never settle to the
        # same word twice and the null interval already moves all 32.
        big = max(pk_lo, pk_hi)
        small = min(pk_lo, pk_hi)
        ratio = big > 2 * small + (1 << 16)
        if moved > floor or pd > max(8 * fd, 1 << 20) or ratio:
            rec['verdict'] = 'LIVE'
        elif pk == 0:
            # NOT "inert". A window that carries no signal at all cannot
            # tell an inert cell from a chain that never received the
            # stimulus, and calling that a result is the mistake the
            # conformance harness exists to avoid.
            rec['verdict'] = 'SILENT'
        elif floor >= n:
            # NO FLOOR, so no discrimination: the null interval already
            # moves every word. Not a verdict either way.
            rec['verdict'] = 'NO_FLOOR'
        else:
            rec['verdict'] = 'INERT'
        apply(lo)
    except IOError as exc:
        rec['verdict'] = 'ERROR'
        rec['error'] = str(exc)
    log('  audio: %-12s %-24s floor %s/%s moved %s/%s peak 0x%08X->0x%08X '
        '-> %s'
        % (fam, spec['witness'], rec.get('floor'), rec.get('floor_delta'),
           rec.get('moved'), rec.get('probe_delta'),
           rec.get('peak_lo', 0), rec.get('peak_hi', 0), rec['verdict']))
    return rec


def meter_phase(part, L, spec, inj, log=print):
    """MTR: the peak word the host reads over SPI against the peak the
    scope captured from the point the meter says it taps.

    This is the one family whose verdict cannot be "did the audio move" --
    a meter changes no sample by design. The tap is read off the graph's
    own `taps=` declaration: C1_MTR_01 declares
    `post_trim;post_fader;gate_gr;comp_gr`, which names WORDS at +0..+3,
    so `_mtr_peak` is the POST-TRIM point (the GAIN node's output) and not
    the fader's.

    BOTH INTERPRETATIONS ARE REPORTED, because the recorded defect
    (2026-08-23) is exactly a units confusion: the node stores a Q4.28
    integer where the host contract says float32. Scoring only one of them
    would decide the question the measurement is supposed to answer.
    """
    rec = {'family': 'METER', 'readback': spec['meter'],
           'source': spec['meter_src']}
    for sym in (spec['meter'], spec['meter_src']):
        if sym not in part.sc.sym:
            rec['verdict'] = 'NO_SYMBOL'
            rec['missing'] = sym
            return rec
    try:
        w = capture(part, inj, spec['meter_src'], 64, 900)
        if w is None:
            rec['verdict'] = 'NO_CAPTURE'
            return rec
        cap_peak = max(abs(x - (1 << 32) if x & 0x80000000 else x) for x in w)
        got = part.sc.peek(part.sc.sym[spec['meter']]) & 0xFFFFFFFF
        ref = cap_peak / float(1 << 28)
        as_float = struct.unpack('<f', struct.pack('<I', got))[0]
        as_q428 = got / float(1 << 28)
        rec.update(captured_peak=cap_peak, captured_linear=ref,
                   meter_word=got, meter_as_float32=as_float,
                   meter_as_q428=as_q428)

        def close(x):
            return ref > 0 and abs(x - ref) <= 0.05 * ref
        if close(as_float):
            rec['verdict'] = 'AGREES'
            rec['reading'] = 'float32, as the host contract says'
        elif close(as_q428):
            rec['verdict'] = 'AGREES_AS_Q428'
            rec['reading'] = ('the word is a Q4.28 INTEGER, not the float32 '
                              'the host contract declares')
        else:
            # A PEAK HOLD IS STATEFUL, so a disagreement here is NOT a
            # verdict on the meter. This tool's first run reported
            # DISAGREES -- readback 7.05 against a captured peak of 0.5 --
            # and the meter was fine: the contract sweep immediately
            # before it writes 1.0f into every rw cell of the node it is
            # probing, which drove the strip near full scale, and the
            # peak-hold had not decayed by the time this read it. The
            # family's real bar is mtrverify.sh, which drives a known
            # stimulus on its own image and scores the 64-bit meter state
            # against fixed_ref.meter_block; it reads METER_BIT_EXACT on
            # this tree. Report the numbers and name the bar.
            rec['verdict'] = 'NO_VERDICT'
            rec['reading'] = (
                'neither reading matches, and a peak HOLD carries state '
                'from whatever ran before it — run mtrverify.sh for this '
                'family rather than reading a verdict out of this line')
    except IOError as exc:
        rec['verdict'] = 'ERROR'
        rec['error'] = str(exc)
    log('  meter: captured %.6f  word 0x%08X = %.6f as float32 / %.6f as '
        'Q4.28 -> %s'
        % (rec.get('captured_linear', 0), rec.get('meter_word', 0),
           rec.get('meter_as_float32', 0), rec.get('meter_as_q428', 0),
           rec['verdict']))
    return rec

# ---------------------------------------------------------------------------
# NUMERIC PHASE — delegated to the instruments that carry the models
# ---------------------------------------------------------------------------

NUMERIC_NODES = {'GATE': 'GATE', 'COMPRESSOR': 'COMP', 'TUBE_SAT': 'TUBE',
                 'FADER_PAN': 'FDR'}


def numeric_phase(part, fams, strip, n, bq_arm='float', log=print):
    """run_node() from the goldnode bar, per family, on THIS image.

    Not a re-implementation: the model, the converted-parameter check and
    the deliberately-wrong twin all live in dsp4_node_verify, so a family
    scored here is scored by the instrument whose negative control has to
    fire before it will report anything at all.
    """
    import dsp4_node_verify as NV
    # ARM NODE_VERIFY'S ZERO SENTINEL. Its voted reader treats a value of 0
    # as "possibly a dropped answer" and only accepts it when a known
    # non-zero register still reads correctly -- and that register is
    # registered in dsp4_node_verify.main(), which this tool does not call.
    # Left empty, EVERY genuinely-zero parameter word reads as None: the
    # compressor's hard-knee words are zero by default, so COMPRESSOR lost
    # its whole verdict to "parameters unreadable" on two bench runs before
    # the cause was this one missing line.
    try:
        want = part.sc.peek(part.sc.sym['_scope_len'])
        if want:
            NV.SENTINEL.update(addr=part.sc.sym['_scope_len'], want=want)
            log('  zero sentinel: _scope_len = %d' % want)
        else:
            log('  zero sentinel UNARMED — a parameter that is genuinely 0 '
                'will read as unreadable')
    except (IOError, KeyError) as exc:
        log('  zero sentinel UNARMED (%s)' % exc)
    out = {}
    for fam in fams:
        name = NUMERIC_NODES.get(fam)
        if name is None:
            continue
        log('--- numeric: %s (%s)' % (fam, name))
        try:
            bad, meas, _ = NV.run_node(part, name, NV.NODES[name], strip, n)
        except (IOError, SystemExit) as exc:
            out[fam] = {'verdict': 'ERROR', 'error': str(exc)}
            continue
        out[fam] = {'node': name, 'verdicts_against': bad, 'stimuli': meas,
                    'verdict': ('BIT_EXACT' if meas and not bad else
                                'FAILED' if bad else 'NO_STIMULUS')}
    if ('EQ_BIQUAD' in fams or 'HPF_LPF' in fams) and bq_arm != 'float':
        log('--- numeric: BQCVT (the biquad coefficient conversion)')
        try:
            bad, groups = NV.run_bqcvt(part, strip)
            v = ('BIT_EXACT' if groups and not bad else
                 'FAILED' if bad else 'NO_STIMULUS')
            for fam in ('EQ_BIQUAD', 'HPF_LPF'):
                if fam in fams:
                    out[fam] = {'node': 'BQCVT', 'verdicts_against': bad,
                                'stimuli': groups, 'verdict': v}
        except (IOError, SystemExit) as exc:
            for fam in ('EQ_BIQUAD', 'HPF_LPF'):
                if fam in fams:
                    out[fam] = {'verdict': 'ERROR', 'error': str(exc)}
    elif bq_arm == 'float':
        # BQCVT IS THE FIXED ARM'S CONVERTER AND IT DOES NOT APPLY HERE.
        # `_bq_fx_convert_N` produces Q4.28 offset-form coefficients; under
        # DSP4_BQ_FLOAT the node stores IEEE float32 and the reference is
        # `bq_float_ref`, not `fixed_ref` (numeric-spec.md, "SHARC float
        # cascade = bq_float_ref"). Running it anyway is what the first
        # bench run did, and it reported a FAILURE that was the harness
        # quoting the wrong model: the part held 0x3F800000 (float 1.0)
        # where fixed_ref predicted 268435456 (Q4.28 1.0). The float arm's
        # bit-exact bar is `bqeverify.sh float`, run separately.
        log('--- numeric: BQCVT SKIPPED — this image is the FLOAT cascade; '
            'its bit-exact bar is bqeverify.sh float against bq_float_ref')
        for fam in ('EQ_BIQUAD', 'HPF_LPF'):
            if fam in fams:
                out[fam] = {
                    'node': 'BQCVT', 'verdict': 'NOT_APPLICABLE',
                    'reason': 'float cascade; bit-exact bar is '
                              'bqeverify.sh float vs bq_float_ref'}
    return out


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--landed', default='landed-d24.json')
    ap.add_argument('--families', default=None,
                    help='comma list; default every family in the landed map')
    ap.add_argument('--chips', default='1,2')
    ap.add_argument('--strip', type=int, default=1)
    ap.add_argument('--n', type=int, default=64)
    ap.add_argument('--json', default=None)
    ap.add_argument('--no-numeric', action='store_true')
    ap.add_argument('--bq-arm', default='float',
                    choices=('float', 'fixed'),
                    help='which biquad arm the image was built '
                         'with (DSP4_BQ_FLOAT)')
    a = ap.parse_args()

    L = Landed(a.landed)
    print('landed contract: %s  pin %s  sha256 %s  %d cells'
          % (L.product, L.pin or '?', L.sha256[:12], len(L.cells)))
    fam_counts = L.families()

    report = {'product': L.product, 'pin': L.pin, 'sha256': L.sha256,
              'bq_arm': a.bq_arm,
              'family_cells': fam_counts, 'families': {},
              'cross_check': None, 'chips': {}}

    print('\n== cross-check: transcribed constants vs the landed contract ==')
    rows, bad = cross_check(L)
    report['cross_check'] = {'rows': rows, 'disagreements': bad}

    # THE UNION, NOT THE LANDED NODE TYPES ALONE (S23). `fam_counts` is
    # keyed by NodeType, so a feature whose cells sit on a node type that
    # was already passing -- the matrix's four sends on a ROUTING, its
    # masters on a FADER_PAN -- can never get a family of its own, and the
    # walk would report the graph complete while the feature had never been
    # witnessed. An entry in FAMILIES is a claim that something is
    # answerable for, so it runs whether or not its name is a NodeType.
    want = ([f.strip().upper() for f in a.families.split(',')]
            if a.families else sorted(set(fam_counts) | set(FAMILIES)))
    chips = [int(c) for c in a.chips.split(',')]

    for chip in chips:
        fams = [f for f in want
                if f in FAMILIES and FAMILIES[f]['chip'] == chip]
        if not fams:
            continue
        print('\n== chip %d ==' % chip)
        try:
            part = Part(chip)
        except SystemExit as exc:
            print('  chip %d not ready: %s' % (chip, exc))
            report['chips'][chip] = {'ready': False, 'error': str(exc)}
            for f in fams:
                report['families'][f] = {
                    'chip': chip, 'node': FAMILIES[f]['node'],
                    'cells': fam_counts.get(f, 0),
                    'note': FAMILIES[f]['note'],
                    'verdict': 'NOT_MEASURED',
                    'reason': 'chip %d not ready' % chip}
            continue
        healthy = part.healthy()
        report['chips'][chip] = {'ready': True, 'healthy': healthy}
        # WHICH BUILD THIS ARM WAS TAKEN ON (2026-09-09, findings S9-5).
        # Five famverify reports were taken on 2026-09-09 in five different
        # configurations and not one of them recorded which -- so telling the
        # block-8 per-sample control from the block-16 block-kernel arm meant
        # trusting a filename. DIAG_BUILD_CFG is one transaction and the part
        # answers it; there is no reason for a report not to carry it.
        try:
            cfg = part.sc.rd(0xE0EA)
            report['chips'][chip]['build_cfg'] = '0x%08X' % cfg
            print('  chip %d build_cfg 0x%08X' % (chip, cfg))
        except (IOError, SystemExit) as exc:
            report['chips'][chip]['build_cfg'] = None
            print('  chip %d build_cfg unreadable: %s' % (chip, exc))
        print('  chip %d ready, healthy=%s' % (chip, healthy))
        if not healthy:
            print('  the block loop is not turning — CONTRACT only, no audio')

        for f in fams:
            report['families'][f] = {
                'chip': chip, 'node': FAMILIES[f]['node'],
                'cells': fam_counts.get(f, 0), 'note': FAMILIES[f]['note']}

        # ORDER MATTERS, and it is numeric -> audio -> contract.
        #
        # The CONTRACT phase writes 0 and 1.0f to every rw cell of the
        # node it is probing. That is the right probe for "does this
        # address answer" and the wrong state for anything measuring
        # audio: the first cut of this tool ran it first and every family
        # afterwards captured silence, because a strip whose gain has
        # been written and restored around a zero is a strip that spent
        # the interval muted. Numeric goes first because it is the
        # strictest and sets up its own state; audio follows from a
        # freshly driven strip; the contract sweep, which leaves the
        # graph disturbed, goes last and needs no audio at all.
        if chip == 1 and healthy and not a.no_numeric:
            print('\n== numeric (chip 1) ==')
            drive_strip(part, a.strip)
            # WARM THE LINK BEFORE THE FIRST NODE. drive_strip fires ~18
            # writes back to back and the first paced peek after that burst
            # comes back empty often enough to matter: the first bench run
            # lost COMPRESSOR's whole verdict to "parameters unreadable"
            # purely because it was the node that happened to go first.
            time.sleep(1.0)
            for _ in range(3):
                try:
                    part.sc.peek(part.sc.sym['_scope_len'])
                    break
                except IOError:
                    time.sleep(0.5)
            num = numeric_phase(part, fams, a.strip, a.n, a.bq_arm)
            for f, v in num.items():
                report['families'][f]['numeric'] = v

        if healthy:
            print('\n== audio ==')
            if chip == 1:
                drive_strip(part, a.strip)
            for f in fams:
                spec = FAMILIES[f]
                report['families'][f]['audio'] = audio_phase(
                    part, L, f, spec, a.n)
                if spec.get('meter'):
                    report['families'][f]['meter'] = meter_phase(
                        part, L, spec, part.sc.sym[spec['inject']])
                if chip == 1:
                    drive_strip(part, a.strip, log=lambda *_: None)
        else:
            for f in fams:
                report['families'][f]['audio'] = {'verdict': 'NOT_MEASURED'}

        print('\n== contract ==')
        for f in fams:
            print('- %s (%s, %d cells)'
                  % (f, FAMILIES[f]['node'], fam_counts.get(f, 0)))
            report['families'][f]['contract'] = contract_phase(
                part, L, FAMILIES[f]['node'],
                cells=FAMILIES[f].get('contract_cells'))

    # families the landed map addresses but this tool has no entry for
    for f in fam_counts:
        report['families'].setdefault(f, {
            'chip': None, 'cells': fam_counts[f],
            'verdict': 'NO_HARNESS_ENTRY'})

    if a.json:
        with open(a.json, 'w') as fh:
            json.dump(report, fh, indent=1, sort_keys=True)
        print('\nwrote %s' % a.json)
    print('\n== summary ==')
    for f in sorted(report['families']):
        e = report['families'][f]
        c = e.get('contract') or []
        ans = sum(1 for r in c if r.get('verdict') == 'ANSWERS')
        rw = sum(1 for r in c if r.get('access') == 'rw')
        print('%-12s cells %5s  contract %3s/%-3s  audio %-16s numeric %-11s'
              ' %s'
              % (f, e.get('cells'), ans, rw,
                 (e.get('audio') or {}).get('verdict', '-'),
                 (e.get('numeric') or {}).get('verdict', '-'),
                 (e.get('meter') or {}).get('verdict', '')))
    return 0


if __name__ == '__main__':
    sys.exit(main())
