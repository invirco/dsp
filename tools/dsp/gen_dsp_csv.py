#!/usr/bin/env python3
"""gen_dsp_csv.py — Generates the unified DSP4 dsp.csv from the signal-chain
spec + the single-sourced TDM slot map (decision D2).

SPORT/slot facts come from shared/dsp4-logic/generated/sport_map.json —
regenerate that first (shared/dsp4-logic/gen_slot_map.py) if the slot map
changed. This script asserts its emitted sport/slot params against the map.

Topology (decisions D3/D4, hardware-map ground truth):
  Chip 1 (DSPA): 32× channel strip + superset inputs (codec return, Pi PCM,
          MEMS talkback, D32 snake) + matrix mix -> bus pre-sums; sends
          buses AND superset pass-throughs to chip 2 over the 8× TDM16 mix
          fabric (global slot = 16*line + slot; buses keep legacy order on
          global slots 0-24, pass-throughs on 25-36, rest reserved).
  Chip 2 (DSPB): bus receives -> Aux/Grp/Sub/Main/FX processing -> output
          patch onto DAC 1-16, DAC MAIN, codec (D24), NET.

Superset I/O nodes are always generated (D3: one firmware); boot-time
product config enables/routes them (scope=D24/D32 params mark
product-specific nodes; they default muted/off).

Usage:
  gen_dsp_csv.py [--out PATH] [--sport-map PATH]
  --out default: <repo>/MW/D32/DSP/SHARC/dsp.csv (the unified DSP4 tree)
"""

import argparse
import csv
import json
import os
import sys

# --- Column schema ---
# id, chip, type, label, ch_count, inputs, outputs, spi_page, spi_addr, params, ramp_profile

HEADER = ['id', 'chip', 'type', 'label', 'ch_count', 'inputs', 'outputs',
          'spi_page', 'spi_addr', 'params', 'ramp_profile']

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

parser = argparse.ArgumentParser(description='Generate unified DSP4 dsp.csv')
parser.add_argument('--out', default=os.path.join(
    REPO_ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'dsp.csv'))
parser.add_argument('--sport-map', default=os.path.join(
    REPO_ROOT, 'shared', 'dsp4-logic', 'generated', 'sport_map.json'))
# --- GEQ FEATURE PARAMETERS (2026-09-03) -----------------------------------
# The graphic EQ is the one feature whose EXTENT is a market decision rather
# than a hardware one, so it is a parameter of this generator instead of a
# constant: PW's market bar is "31-band GEQ on ALL outputs", and the cost of
# that bar has to be measurable against the shipping graph on one instrument.
#
# Defaults REPRODUCE THE SHIPPING dsp.csv BYTE FOR BYTE -- since
# 2026-09-09, 31 bands on the twelve aux buses, the four groups and the
# main bus, and nowhere else. Any other value is a different product
# configuration and is asked for explicitly.
#
# THE DEFAULT MOVED 28 -> 31 AT defs-v2026.09.08.3, and it moved every
# chip-2 address above the first GEQ node with it. The cell master now
# defines `Geq[1-31]` on every output (PW ruling: the 1/3-octave bar is
# the market bar), the address allocator below packs blocks end to end,
# and a GEQ block is exactly its band count -- so +3 words on seventeen
# nodes is +51 words on chip 2 and 195 of its 235 nodes take a new
# address. That re-layout is the change, not the three rows; it is
# recorded in MW/D32/DSP/dsp4-geq31-relayout-20260909.md. Passing
# --geq-bands 28 reproduces the pre-.3 map exactly, which is how the two
# were diffed.
#
# Bus/output COUNTS are deliberately NOT parameters here: NUM_AUX=12,
# NUM_GRP=4, NUM_FX=6 and the four main outputs are pinned by the TDM mix
# fabric's single-sourced slot map (shared/dsp4-logic/generated/
# sport_map.json), and a count this script invented would disagree with the
# slot map rather than change the product.
parser.add_argument('--geq-bands', type=int, default=31,
                    help='bands per graphic EQ instance (default 31, the '
                         '1/3-octave market bar; 28 is the pre-.3 map)')
parser.add_argument('--geq-outputs', default='aux,grp,main',
                    help='comma-separated output classes that carry a GEQ: '
                         'aux,grp,main,mainout,mon. Default '
                         '"aux,grp,main" is the shipping graph. The Centre '
                         'strip\'s GEQ is not an option (MainCtr Geq is a '
                         'landed cell, PW ruling D6).')
args = parser.parse_args()

GEQ_BANDS = args.geq_bands
if not 1 <= GEQ_BANDS <= 64:
    raise ValueError(f'--geq-bands {GEQ_BANDS} out of range 1..64')
GEQ_CLASSES = ('aux', 'grp', 'main', 'mainout', 'mon')
GEQ_ON = tuple(c.strip() for c in args.geq_outputs.split(',') if c.strip())
# No-fallback policy: an unrecognised class is a typo that would silently
# generate a graph with a feature missing.
for _c in GEQ_ON:
    if _c not in GEQ_CLASSES:
        raise ValueError(
            f'--geq-outputs: unknown class {_c!r}; known classes are '
            f'{", ".join(GEQ_CLASSES)}')

sys.path.insert(0, SCRIPT_DIR)
from geq_splice import relink_and_insert as _relink_and_insert

with open(args.sport_map, encoding='utf-8') as f:
    SPORT_MAP = json.load(f)

# signal -> {sport_id, slot, sport_slots} per (chip, side)
SIG = {}
for _chip in ('1', '2'):
    for _side in ('rx', 'tx'):
        for _line in SPORT_MAP['chips'][_chip][_side]:
            for _s in _line['slots']:
                SIG[(_chip, _side, _s['signal'])] = {
                    'sport_id': _line['sport_id'],
                    'slot': _s['slot'],
                    'sport_slots': _line['slot_count'],
                }

# mix-fabric signal -> global slot (0..127)
MIX_GLOBAL = {b['signal']: b['global_slot']
              for b in SPORT_MAP['mix_fabric']['buses']}

# Pre-flight: every mix-fabric bus's global_slot must agree with its chip-1
# tx (sport_id, slot) per the fabric_params() convention below. Check all of
# them once at load rather than asserting lazily per fabric_params() call.
_fabric_errors = []
for _signal, _g in MIX_GLOBAL.items():
    _e = SIG.get(('1', 'tx', _signal))
    if _e is None:
        _fabric_errors.append(f'{_signal}: no chip-1 tx entry in sport_map')
    elif _g != 16 * _e['sport_id'] + _e['slot']:
        _fabric_errors.append(
            f'{_signal}: global_slot={_g} != 16*sport_id+slot '
            f'({16 * _e["sport_id"] + _e["slot"]})')
if _fabric_errors:
    raise ValueError(
        'sport_map.json inconsistent for mix-fabric bus(es):\n  ' +
        '\n  '.join(_fabric_errors))


def sig_rx1(signal):
    return SIG[('1', 'rx', signal)]


def sig_tx2(signal):
    return SIG[('2', 'tx', signal)]


def input_params(signal, slot_count=1):
    e = sig_rx1(signal)
    return (f'sport_id={e["sport_id"]};slot_start={e["slot"]};'
            f'slot_count={slot_count};sport_slots={e["sport_slots"]};'
            f'signal={signal}')


def output_params(signal, slot_count=1, scope=None, sink=None):
    # `sink` names the physical thing on the far side of the lane, for the
    # cases where the signal name alone does not say it. It is emitted HERE
    # and not hand-added to dsp.csv: S102 wrote `sink=SPKR`/`sink=DNP`
    # straight into the generated file, and the next run of this script
    # (S109) silently deleted both. A generated file is regenerated, not
    # edited -- so the fact has to live in the generator.
    e = sig_tx2(signal)
    p = (f'sport_id={e["sport_id"]};slot_start={e["slot"]};'
         f'slot_count={slot_count};sport_slots={e["sport_slots"]};'
         f'signal={signal}')
    if scope:
        p += f';scope={scope}'
    if sink:
        p += f';sink={sink}'
    return p


def fabric_params(signal):
    """Inter-chip fabric slot: chip1 TX line n == chip2 RX line n."""
    e = SIG[('1', 'tx', signal)]
    g = MIX_GLOBAL[signal]
    return (f'sport_id={e["sport_id"]};slot={e["slot"]};global_slot={g};'
            f'sport_slots=16;signal={signal}')



# ===========================================================================
# THE D24 OUTPUT PATCH — which DAC slot each output node lands in
#
# The sixteen DAC slots are TDM positions on two AK4458s. Which physical
# connector a slot reaches is the ANALOG BOARD's business, and it is not
# 1:1 on either DAC. Traced (mx26 docs/d24-analog-paths.csv, 267 completed
# paths) and read off the schematic (D24 Analog rev B, sheet 12/64
# "OUT_9-16"); the AK4458 half of it is the chip's own — SDTI1 is the only
# serial input wired and the straps are TDM0-1 = 01, DIF0-1 = 10, so
# channel n is TDM slot n:
#
#   OUT_1-8 block, AK4458 U81, lane B_O0 — REVERSED, channel n -> OUT_(9-n)
#     DAC_01 -> ch1 -> J52 -> rear XLR OUT_08 / phonejack J1 ring
#     ...
#     DAC_08 -> ch8 -> J45 -> rear XLR OUT_01 / phonejack J4 tip
#   These eight are the product's Aux Out A1..A8 (defs d24-io.csv).
#
#   OUT_9-16 block, AK4458 U92, lane B_O1 — a different derangement:
#     DAC_09 -> ch1 -> PHONES_L      (J10 tip)
#     DAC_10 -> ch2 -> PHONES_R      (J10 ring)
#     DAC_11 -> ch3 -> MAIN_R        (J57, balanced, U96)
#     DAC_12 -> ch4 -> MAIN_L        (J56, balanced, U95)
#     DAC_13 -> ch5 -> NOT CONNECTED (U92 pins 32/33 are one-pin nets)
#     DAC_14 -> ch6 -> SUB_W         (J55, balanced, U94) = rear "Center/LF"
#     DAC_15 -> ch7 -> MON L         (J53 tip)
#     DAC_16 -> ch8 -> MON R         (J54 tip)
#
# WHAT THIS FIXES (S42-2). Until now aux a went to DAC_a and main out n to
# DAC_(12+n), i.e. straight down the slot numbers, and the board is not
# straight:
#   * AUX 1 left the unit on the **Aux Out A8** XLR, and the Aux Out A1
#     XLR carried aux 8. That is why S39's AUX 1 -> MIC 1 patch heard
#     nothing while the DSP provably drove the DAC lane (S39-6): the
#     signal was leaving, on the wrong connector.
#   * Main Out 1 went to DAC_13, which is not connected to anything, and
#     Main Out 2 to the Sub XLR, so nothing reached the MAIN XLRs at all.
# Reversing the eight and putting Main Out 1/2 on DAC_12/DAC_11 fixes
# both. It moves one output_params() argument per node and no address.
#
# THE THREE OPEN SOCKETS ARE SETTLED BY PW's 2026-09-28 BLOCK RULINGS, and
# S144 is where the patch follows them (they were an open question in this
# comment until this session):
#   * DAC_14 -- the rear "Center/LF" XLR J55 -- is the block's ONE C/LF
#     output (ruling D6). It is driven by `C2_OUT3_OUT` off the shared
#     Out3 tail, and NOT by aux bus 12 (S121-5: D24 declares aux 1-8, so
#     no cell reached that feed at all).
#   * DAC_15/16 -- the rear Monitor jacks J53/J54 -- carry the MONITOR bus
#     (S122-5), which they are labelled for. They used to carry main
#     output 3/4, i.e. the crossover's centre and sub legs (S121-6,
#     measured); outputs 3 and 4 are gone with the Centre/Woof rebuild.
#   * DAC_09/10 -- PHONES_L/R (J10 tip/ring) -- carry the PHONES PAIR
#     (ruling D7), not aux 9/10.
#
# SO AUX 9-12 HAVE NO COPPER, and that is the product: a D24 has eight aux
# connectors. They land on NET_OUT_06..09, on the same PROVISIONAL footing
# the four matrix outputs sit on NET_OUT_02..05 -- addressable, on a lane
# the mix fabric declares, and which physical connector (if any) a NET
# line reaches is a product decision recorded for PW, not settled here.
# DAC_13 (U92 ch5, pins 32/33 are one-pin nets) is now driven by nothing,
# which is what "not connected" should look like in the patch.
#
#   * This table is D24 copper. One firmware serves D24 and D32
#     (dsp4-architecture-decisions.md), so when the D32 analog board
#     lands, the patch becomes product config and this table is where
#     that split goes.
AUX_DAC = {
    1: 'DAC_08', 2: 'DAC_07', 3: 'DAC_06', 4: 'DAC_05',    # -> Aux Out A1..A4
    5: 'DAC_04', 6: 'DAC_03', 7: 'DAC_02', 8: 'DAC_01',    # -> Aux Out A5..A8
    9: 'NET_OUT_06', 10: 'NET_OUT_07',                     # no aux connector (S144)
    11: 'NET_OUT_08', 12: 'NET_OUT_09',                    # no aux connector (S144)
}
MAIN_OUT_DAC = {
    1: 'DAC_12',    # MAIN_L, analog J56
    2: 'DAC_11',    # MAIN_R, analog J57
}
# Main outputs 3 and 4 ARE GONE (S144, PW ruling D6). They were MainCtr and
# MainSub as post-crossover legs of the main chain, on DAC_15/16 -- the
# wrong shape by the 24 Sep master block, which draws a Centre strip off
# the Ctr Channel Bus, a Woof strip off the Main L/R sum, and ONE C/LF XLR
# through one mute, meter, delay and DAC. Their SPI words are RESERVED
# rather than reclaimed (see MAIN_OUT_RESERVE below) so that no surviving
# node's address moves.
NUM_MAIN_OUT = 2
MAIN_OUT_RESERVE = (3, 4)

rows = []

def add(nid, chip, ntype, label, ch_count, inputs, outputs,
        spi_page=-1, spi_addr=-1, params='', ramp_profile=''):
    rows.append({
        'id': nid,
        'chip': str(chip),
        'type': ntype,
        'label': label,
        'ch_count': str(ch_count),
        'inputs': inputs,
        'outputs': outputs,
        'spi_page': str(spi_page),
        'spi_addr': str(spi_addr),
        'params': params,
        'ramp_profile': ramp_profile,
    })

# ===========================================================================
# SPI address allocator — sequential packing per chip
# ===========================================================================
class AddrAlloc:
    def __init__(self):
        self.page = 1
        self.addr = 0
    def next(self, words=1):
        """Return (page, addr) and advance by `words`."""
        p, a = self.page, self.addr
        self.addr += words
        if self.addr >= 8192:  # page boundary
            self.page += 1
            self.addr = 0
        return p, a

c1_alloc = AddrAlloc()
c2_alloc = AddrAlloc()

# ---------------------------------------------------------------------------
# LATE CHIP-2 ALLOCATION (S144)
#
# A node's ROW POSITION is its process order and its CALL POSITION is its
# address, and S144 adds nodes that need to be late in the second and early
# in the first: the Centre GEQ runs between the Centre EQ and its limiter,
# the Woof strip runs after the main delay, and every one of them must take
# an address after every allocation that was already landed -- otherwise the
# whole chip-2 map below them moves and the contract bumps for nothing.
#
# Same discipline as ROUTING's `mtx_page`, OUTPUT_TDM's `mo_page` and S143's
# `xp_page`: register the width here, add the row where it runs, and let
# `resolve_late_c2()` hand out the addresses after the last existing
# allocation. A registered node that never got a row -- or a row that never
# got its address -- is a build error, not a node quietly left unreachable.
# ---------------------------------------------------------------------------
_LATE_C2 = []


def _late_c2(nid, words):
    """Register `nid` for an address allocated after every existing one."""
    _LATE_C2.append((nid, words))


def resolve_late_c2():
    by_id = {r['id']: r for r in rows}
    for nid, words in _LATE_C2:
        r = by_id.get(nid)
        if r is None:
            raise SystemExit(
                f'ERROR: {nid} was registered for a late chip-2 address and '
                f'no row was added for it.')
        if r['spi_page'] != '-1' or r['spi_addr'] != '-1':
            raise SystemExit(
                f'ERROR: {nid} already carries an SPI address '
                f'({r["spi_page"]}/{r["spi_addr"]}) and is also registered '
                f'for a late one. One allocation per node.')
        p, a = c2_alloc.next(words)
        r['spi_page'], r['spi_addr'] = str(p), str(a)

# ===========================================================================
# CHIP 1 — Input DSP: 32-channel strip
# ===========================================================================

# Signal chain per channel (from dsp-def.md §2.1):
#   IN → GAIN → HPF_LPF → EQ_BIQUAD → GATE → COMPRESSOR → TUBE_SAT → DELAY → FADER_PAN → ROUTING
# Note: ROUTING is the fan-out node that feeds bus pre-sums

NUM_CH = 32
NUM_AUX = 12
NUM_GRP = 4
NUM_FX = 6

# THE MATRIX (S22 gate 1). Both numbers are READ OFF THE CELL MASTER, not off
# the product def, and they do not agree with each other -- which is a
# question for PW and not a choice this generator may make.
#
#   Matrix[1-4]Level / Matrix[1-4]Mute        -> four output masters
#   Chan[1-64]MatrixSend[1-2] / MatrixOn[1-2] -> TWO sends per channel
#
# So the definition gives four matrix outputs and a channel the means to
# reach only two of them. D32's `mtx,12` in d32.csv disagrees with both (the
# master caps the family at four); D24's `mtx,2` intersects to two outputs
# and the same two sends. The topology master (defs/common/topology/
# diagram-master.csv) additionally names `bus.main -> bus.mtx` and
# `bus.grp -> bus.mtx` as matrix sources, and the cell master defines NO
# cell for either, so neither is built.
#
# WHAT IS BUILT, therefore, is exactly what the cells name: four matrix
# buses and four output strips, with channel sends onto the first two.
# Buses 3 and 4 carry no crosspoint at all -- their column of _xpc stays at
# the zeros rtg_fabric.asm initialises, so `_xp_lo > _xp_hi` and the
# accumulate skips them for nothing. They are built rather than omitted
# because Matrix003/004 Level and Mute ARE defined cells and the completeness
# record is the unmapped list: a strip that exists and is fed by nothing is
# an honest rendering of a definition that says exactly that, and it is one
# `NUM_MTX_SEND` away from being fed the day PW answers.
NUM_MTX = 4          # Matrix[1-4] in the cell master
NUM_MTX_SEND = 2     # Chan[1-64]MatrixSend[1-2] in the cell master

# --- Bus pre-sum IDs (Chip 1 accumulates, sends to Chip 2) ---
bus_main_l = 'C1_BUS_MAIN_L'
bus_main_r = 'C1_BUS_MAIN_R'
bus_sub    = 'C1_BUS_SUB'
bus_grp    = [f'C1_BUS_GRP_{g:02d}' for g in range(1, NUM_GRP+1)]
bus_aux    = [f'C1_BUS_AUX_{a:02d}' for a in range(1, NUM_AUX+1)]
bus_fx     = [f'C1_BUS_FX_{x:02d}'  for x in range(1, NUM_FX+1)]
bus_mtx    = [f'C1_BUS_MTX_{m:02d}' for m in range(1, NUM_MTX+1)]

# THE LEGACY 25, in the order the mix fabric's global slots 0-24 carry them
# and the order _bus_acc_all_ptrs is built in. Nothing may be inserted into
# this list: the assert below is what keeps the fabric's slot numbering and
# this graph the same fact.
legacy_bus_ids = [bus_main_l, bus_main_r, bus_sub] + bus_grp + bus_aux + bus_fx

# All bus IDs that a channel routing node feeds. The matrix buses are
# APPENDED, so every existing bus keeps its index in _xpc and in
# _bus_acc_all_ptrs and only new columns are added.
all_bus_ids = legacy_bus_ids + bus_mtx

# Slot-map signal per bus id (C1_BUS_MAIN_L -> BUS_MAIN_L)
bus_signal = {bid: bid.replace('C1_', '') for bid in all_bus_ids}

# Collect all routing node IDs per bus (filled during channel generation)
bus_sources = {bid: [] for bid in all_bus_ids}

for ch in range(1, NUM_CH + 1):
    cc = f'{ch:02d}'

    # Node IDs for this channel
    n_in    = f'C1_IN_{cc}'
    n_gain  = f'C1_GAIN_{cc}'
    n_filt  = f'C1_FILT_{cc}'
    n_eq    = f'C1_EQ_{cc}'
    n_gate  = f'C1_GATE_{cc}'
    n_comp  = f'C1_COMP_{cc}'
    n_tube  = f'C1_TUBE_{cc}'
    n_delay = f'C1_DLY_{cc}'
    n_fader = f'C1_FDR_{cc}'
    n_route = f'C1_RTG_{cc}'

    # --- INPUT ---
    # Card input index == channel index (IN_01..IN_32 on A_I0..A_I3).
    # The D24 console-channel interleave (ADC8 #1 = ch 1-4 & 13-16) is a
    # product-config input patch, not a slot-map concern.
    ip = input_params(f'IN_{cc}')
    assert f'sport_id={(ch - 1) // 8};slot_start={(ch - 1) % 8};' in ip
    add(n_in, 1, 'INPUT_TDM', f'Ch {ch} Input', 1, '', n_gain, params=ip)

    # --- GAIN (trim component of hybrid preamp) ---
    p, a = c1_alloc.next(4)  # gain + pol + phantom + input_sel
    add(n_gain, 1, 'GAIN', f'Ch {ch} Gain', 1, n_in, n_filt,
        spi_page=p, spi_addr=a,
        params='gain_db=0.0;mute=0;polarity=0',
        ramp_profile='GainFast')

    # --- HPF + LPF ---
    p, a = c1_alloc.next(12)  # hpf_freq + hpf_slope + lpf_freq + 2×biquad coeffs (5 each)
    add(n_filt, 1, 'HPF_LPF', f'Ch {ch} HPF+LPF', 1, n_gain, n_eq,
        spi_page=p, spi_addr=a,
        params='hpf_freq=80.0;hpf_slope=18;lpf_freq=20000.0',
        ramp_profile='EqSafe')

    # --- 4-BAND PEQ ---
    p, a = c1_alloc.next(24)  # 4 bands × (freq + gain + Q + shelf_on) + 4×5 biquad coeffs
    add(n_eq, 1, 'EQ_BIQUAD', f'Ch {ch} EQ', 1, n_filt, n_gate,
        spi_page=p, spi_addr=a,
        params='bands=4;coeffs=default',
        ramp_profile='EqSafe')

    # --- GATE ---
    p, a = c1_alloc.next(16)  # on + thr + att + hold + rel + rng + key + det_src + filter(on+hpf+lpf+Q) + state
    add(n_gate, 1, 'GATE', f'Ch {ch} Gate', 1, n_eq, n_comp,
        spi_page=p, spi_addr=a,
        params='threshold_db=-40.0;attack_ms=1.0;hold_ms=50.0;release_ms=100.0;range_db=60.0;key=0;det_src=0;filter_on=0;filter_hpf=80.0;filter_lpf=8000.0;filter_q=1.0',
        ramp_profile='DynSafe')

    # --- COMPRESSOR ---
    # parallel=100: CompPar is a PERCENT (review finding D40) and the blend
    # is `out = dry + par*(wet - dry)`, so the old default of 0 shipped a
    # compressor that reduced gain and then blended the reduction back out
    # -- measured fully DRY on the part 2026-08-30 at two thresholds 35 dB
    # apart. 100 % is a normal serial compressor. See comp_par_default() in
    # tools/dsp/dsp_codegen.py for the masters' row and what it does and
    # does not document.
    p, a = c1_alloc.next(20)  # on + thr + rat + att + rel + make + knee + par + type + key + det_src + eq_pos + filter params + state
    add(n_comp, 1, 'COMPRESSOR', f'Ch {ch} Comp', 1, n_gate, n_tube,
        spi_page=p, spi_addr=a,
        params='threshold_db=-20.0;ratio=4.0;attack_ms=5.0;release_ms=100.0;knee_db=6.0;makeup_db=0.0;parallel=100;type=VCA;key=0;det_src=0;lim_mode=0;eq_pos=0;filter_on=0;filter_hpf=80.0;filter_lpf=8000.0;filter_q=1.0',
        ramp_profile='DynSafe')

    # --- TUBE SATURATION ---
    p, a = c1_alloc.next(2)  # on + sat_amount
    add(n_tube, 1, 'TUBE_SAT', f'Ch {ch} Tube', 1, n_comp, n_delay,
        spi_page=p, spi_addr=a,
        params='on=0;saturation=0.0',
        ramp_profile='GainFast')

    # --- INPUT DELAY ---
    # Dynamic shared-pool policy:
    #   - every channel always has a 20 ms local delay available
    #   - up to 8 channels may borrow a shared 250 ms slot
    #   - bring-up defaults still assign slots 0-7 to channels 1-8
    p, a = c1_alloc.next(2)  # delay_ms + pool_slot
    local_ms = 20.0
    max_ms = 250.0
    pool_slot = (ch - 1) if ch <= 8 else -1
    add(n_delay, 1, 'DELAY', f'Ch {ch} Delay', 1, n_tube, n_fader,
        spi_page=p, spi_addr=a,
        params=f'delay_ms=0.0;local_ms={local_ms};max_ms={max_ms};pool_slot={pool_slot}',
        ramp_profile='InstantCtl')

    # --- FADER + PAN ---
    # level + pan + mute + one RESERVED word. The fourth word used to
    # carry the DCA assignment cell; PW's 2026-08-30 ruling makes Dca
    # and DcaOn HOST-MANAGED (the CM4 control daemon folds DCA into the
    # fader target it already sends), so the word is reserved rather
    # than reallocated -- compacting it would move every address after
    # it in the channel block for no gain.
    p, a = c1_alloc.next(4)  # level + pan + mute + reserved
    add(n_fader, 1, 'FADER_PAN', f'Ch {ch} Fader', 1, n_delay, n_route,
        spi_page=p, spi_addr=a,
        params='level_db=-inf;pan=0.0;mute=0;host_cells=Dca,DcaOn',
        ramp_profile='GainFast')

    # --- ROUTING (fan-out to all buses) ---
    # outputs: all bus pre-sums
    p, a = c1_alloc.next(60)  # main_on + sub_on + grp_on×4 + aux_on×12 + aux_send×12 + aux_pick×12 + fx_on×6 + fx_send×6 + fx_pick×6
    route_outputs = ';'.join(all_bus_ids)
    # THE MATRIX SENDS ARE NOT IN THIS BLOCK, and that is deliberate. Growing
    # the routing block from 60 words to 64 would move every chip-1 address
    # after channel 1's routing node -- the whole map, the MCU's ghost table
    # and every stored golden -- for four words. They get a block of their
    # own, allocated after every existing chip-1 allocation and named on this
    # row as `mtx_page`/`mtx_addr`, so this contract bump ADDS rows and moves
    # none. gen_dsp.py::expand_routing reads those two params.
    add(n_route, 1, 'ROUTING', f'Ch {ch} Route', 1, n_fader, route_outputs,
        spi_page=p, spi_addr=a,
        params='main_on=1;sub_on=0;grp_on=0000;aux_on=000000000000;fx_on=000000'
               f';mtx_sends={NUM_MTX_SEND};mtx_on=' + '0' * NUM_MTX_SEND,
        ramp_profile='GainFast')

    # Register this channel as a source for all buses
    for bid in all_bus_ids:
        bus_sources[bid].append(n_route)

# --- CHANNEL METERS (Chip 1, read-only) ---
p_mtr, a_mtr = c1_alloc.next(NUM_CH * 4)  # 4 meters per channel
for ch in range(1, NUM_CH + 1):
    cc = f'{ch:02d}'
    # `comp_gr_src` NAMES THE COMPRESSOR WHOSE GAIN WORD THIS METER
    # PUBLISHES (S23 gate 4). `Chan[1-64]CompMtr[1-1]` was listed
    # `unbacked-meter` for two reasons and only one of them was real: the
    # meter's SPI block is four words and base+3 was dispatched to nothing,
    # which is a gap; but there was also no DECLARED SOURCE, and pointing a
    # meter at "the compressor" by string surgery on its own node id is the
    # second address map this repo keeps deleting. The link is a param on
    # the row, resolved by the generator, and a comp_gr tap without one is a
    # hard error rather than a guess.
    #
    # It goes AFTER `taps=` on purpose: _parse_taps() reads to the end of
    # the params or the next `key=` token, so a param placed before the tap
    # list would be swallowed by it.
    add(f'C1_MTR_{cc}', 1, 'METER', f'Ch {ch} Meter', 1,
        f'C1_GAIN_{cc};C1_FDR_{cc}', '',
        spi_page=p_mtr, spi_addr=a_mtr + (ch-1)*4,
        params=f'taps=post_trim;post_fader;gate_gr;comp_gr'
               f';comp_gr_src=C1_COMP_{cc}')

# ===========================================================================
# CHIP 1 — Superset inputs (D3): codec return, Pi PCM, MEMS, D32 snake
# ===========================================================================
# INPUT_TDM reads the LOGIC-framed TDM slot; sources consumed on chip 2
# (codec aux in, Pi playback, snake returns) are passed through the mix
# fabric on global slots 25-36 (XFER_* signals in the slot map) — send
# nodes are emitted after the bus section. MEMS and codec ch1 feed the
# chip-1 TALKBACK nodes directly and do not cross. Product config gates
# all of these at boot (default off/muted). No SPI allocations here, so
# legacy chip-1 addresses are unaffected.

# THE CODEC RETURN LANES, NAMED FROM THE MEASURED MAP (S71).
# The first three labels here were a guess and all three were wrong. The
# AK4619 puts its four ADC channels on SDOUT1 in the fixed TDM256 order
# ADC1 L, ADC1 R, ADC2 L, ADC2 R (datasheet Table 2 mode 10, Figure 19),
# the init image leaves 0BH = 0x00 so every channel reads its own
# differential pin pair with no selector in the way, and the D24 analog
# netlist then fixes the rest:
#
#   slot 0  ADC1 Lch  IN1P/IN1N  mini-jack TIP   aux in L   NETLIST
#   slot 1  ADC1 Rch  IN2P/IN2N  mini-jack RING  aux in R   NETLIST, NOT RECEIVED
#   slot 2  ADC2 Lch  IN3P/IN3N  NOT CONNECTED              NETLIST
#   slot 3  ADC2 Rch  IN4N/IN4P  talkback XLR J1 MEASURED   (S70-1, inverted)
#
# S70 closed the AUX 1 -> J1 loop and drove it over 40 dB: slot 3 followed
# the oscillator at +41.75 dB constant to 0.003 dB while slots 0 and 2 did
# not move at all. So the talkback XLR is slot 3, not slot 0, and what the
# graph called "Codec ADC 1 (TB XLR)" carries the mini-jack.
#
# SLOT 1 IS NOW RECEIVED (S72, ruling S71-3 option 1): lane_layout() in
# dsp_codegen.py derives each lane's cs_mask from the slots of the nodes
# declared on it, so adding the `C1_XIN_CODEC_02` row below moves cs_mask
# from 0x000D to 0x000F -- read off the generated artefact, not hand-set.
# `C1_XIN_CODEC_03` (slot 2, IN3, not connected on rev C) stays declared so
# the lane map is complete, but feeds nothing: no entry in `xin_consumer`,
# so `add()` gives it outputs='' below.
#
# Scope: this table carries no scope tag, so it is one table for both D24
# and D32 (one firmware, dsp4-architecture-decisions.md) -- D32 gets the
# new C1_XIN_CODEC_02 lane too, feeding C2_CODEC_AUX_IN's R leg exactly as
# D24 does. Harmless: C2_CODEC_AUX_IN is default `on=0` on both products
# and D32's own analog board (with its own codec, if any) has not landed,
# so this is still a dead lane on D32 hardware -- the same dead lane
# C1_XIN_CODEC_03 was, just renumbered to the slot D24 measured.
superset_c1 = [
    ('C1_XIN_CODEC_01', 'CODEC_RET_1', 'Codec ADC 1 (Aux In L / mini-jack tip)', None),
    ('C1_XIN_CODEC_02', 'CODEC_RET_2', 'Codec ADC 2 (Aux In R / mini-jack ring)', None),
    ('C1_XIN_CODEC_03', 'CODEC_RET_3', 'Codec ADC 3 (ADC2 L / not connected)', None),
    ('C1_XIN_CODEC_04', 'CODEC_RET_4', 'Codec ADC 4 (TB XLR)', None),
    ('C1_XIN_PI_L', 'PI_PCM_L', 'Pi PCM L', None),
    ('C1_XIN_PI_R', 'PI_PCM_R', 'Pi PCM R', None),
    ('C1_XIN_MEMS', 'MEMS_TB', 'MEMS Talkback Mic', None),
] + [(f'C1_XIN_SNK_{s:02d}', f'SNAKE_RET_{s:02d}', f'Snake Return {s}', 'D32')
     for s in range(1, 9)]

# fabric pass-throughs: XFER signal -> source input node
# The aux-in pair follows the map above: L is slot 0 (mini-jack tip), R is
# now slot 1 (mini-jack ring, S72 / S71-3 option 1) via the new
# `C1_XIN_CODEC_02` lane -- the aux input is stereo, as the netlist always
# said the hardware is.
xfer_map = [
    ('XFER_CODEC_AUX_L', 'C1_XIN_CODEC_01', None),
    ('XFER_CODEC_AUX_R', 'C1_XIN_CODEC_02', None),
    ('XFER_PI_L', 'C1_XIN_PI_L', None),
    ('XFER_PI_R', 'C1_XIN_PI_R', None),
] + [(f'XFER_SNAKE_{s:02d}', f'C1_XIN_SNK_{s:02d}', 'D32') for s in range(1, 9)]

xin_consumer = {src: f'C1_XS_{sig}' for sig, src, _ in xfer_map}
xin_consumer['C1_XIN_CODEC_04'] = 'C1_TALK_01'
xin_consumer['C1_XIN_MEMS'] = 'C1_TALK_02'

for nid, sig, label, scope in superset_c1:
    ip = input_params(sig)
    if scope:
        ip += f';scope={scope}'
    add(nid, 1, 'INPUT_TDM', label, 1, '', xin_consumer.get(nid, ''), params=ip)

# --- TALKBACK ×2 ---
# TALK_01 = the talkback XLR J1, TALK_02 = the surface MEMS mic.
#
# TALK_01's source was wired to `C1_XIN_CODEC_01` on 2026-07-31 from the
# hardware map's channel NUMBER, and the number was the codec's ADC
# channel 1 rather than a TDM slot. S70-1 measured the XLR on slot 3, so
# it now reads `C1_XIN_CODEC_04` -- the lane the tone actually arrives on.
# TALK_02 is unchanged: the MEMS mic is its own lane on sport 7 and the
# graph has always had it right.
#
# `invert_opt` (S71): the build flag whose 1 negates this node's input.
# It is on TALK_01 ONLY, because the inversion it answers is a property of
# ONE input's wiring -- J1 pin 2 (hot) lands on the codec's IN4N and pin 3
# on IN4P, so the talkback reaches the DSP upside down (netlist
# `d24-analog-paths.md` "Talkback and aux"; measured S70-6 T5 at +181.56
# deg DC-extrapolated). The MEMS mic is not inverted and must not move.
# Costs nothing: the flag picks the other sign of the Q4.28 scale constant
# the node already multiplies by, so the image is the same instruction
# count either way. DEFAULT OFF -- the choice between fixing it here and
# swapping C4/C11 at IN4 on rev D is PW's, not the generator's.
p, a = c1_alloc.next(8)
talk_sources = {1: 'C1_XIN_CODEC_04', 2: 'C1_XIN_MEMS'}
talk_invert_opt = {1: 'DSP4_TALK_INVERT'}
for t in [1, 2]:
    tp = f'gain_db=0.0;hpf_on=1;route=aux1'
    if t in talk_invert_opt:
        tp += f';invert_opt={talk_invert_opt[t]}'
    add(f'C1_TALK_{t:02d}', 1, 'TALKBACK', f'Talkback {t}', 1,
        talk_sources[t], '',
        spi_page=p, spi_addr=a + (t-1)*4,
        params=tp,
        ramp_profile='GainFast')

# --- NOISE GENERATOR ---
p, a = c1_alloc.next(4)
add('C1_NOISE', 1, 'NOISE_GEN', 'Noise Gen', 1, '', '',
    spi_page=p, spi_addr=a,
    params='on=0;level_db=-20.0;hpf_on=0',
    ramp_profile='InstantCtl')

# --- BUS PRE-SUM NODES (Chip 1 accumulates, then sends to Chip 2) ---
# Each bus sums all 32 channel routing contributions and sends over the
# inter-chip mix fabric (8× TDM16). Buses keep the legacy slot order as
# global mix slots 0-24 (line = slot//16, in-line slot = slot%16).

def make_bus_and_send(bus_id, label, alloc):
    srcs = ';'.join(bus_sources[bus_id])
    sig = bus_signal[bus_id]
    g = MIX_GLOBAL[sig]
    p, a = alloc.next(2)
    add(bus_id, 1, 'MIX_BUS', label, 1, srcs, f'{bus_id}_SEND',
        spi_page=p, spi_addr=a,
        params=f'bus_id={g};source_count={NUM_CH}',
        ramp_profile='')  # bus summing is passive
    add(f'{bus_id}_SEND', 1, 'INTERCHIP_SEND', f'{label} Send', 1, bus_id, '',
        params=fabric_params(sig))

make_bus_and_send(bus_main_l, 'Main L Bus', c1_alloc)
make_bus_and_send(bus_main_r, 'Main R Bus', c1_alloc)
make_bus_and_send(bus_sub, 'Sub Bus', c1_alloc)
for g in range(NUM_GRP):
    make_bus_and_send(bus_grp[g], f'Grp {g+1} Bus', c1_alloc)
for a_idx in range(NUM_AUX):
    make_bus_and_send(bus_aux[a_idx], f'Aux {a_idx+1} Bus', c1_alloc)
for f_idx in range(NUM_FX):
    make_bus_and_send(bus_fx[f_idx], f'FX {f_idx+1} Bus', c1_alloc)
# THE MATRIX BUSES, after the legacy 25 so no existing bus moves. Their
# fabric slots are global 37-40 (MIX_2 slots 5-8), which the CPLD does not
# touch: the MIX_* lines are DSPA O<n> -> DSPB I<n> direct, `external_net` is
# empty for all of them, and no MIXSLOT_* constant appears anywhere in
# shared/dsp4-logic/rtl/. So this is a slot-map contract bump and NOT a
# bitstream change.
for m_idx in range(NUM_MTX):
    make_bus_and_send(bus_mtx[m_idx], f'Matrix {m_idx+1} Bus', c1_alloc)

# --- THE CHANNEL MATRIX SENDS' SPI BLOCK -------------------------------
# Allocated HERE, after every other chip-1 allocation, and written back onto
# the routing rows that were created in the channel loop. That is what keeps
# this contract bump additive: `dsp.csv` gains rows and not one existing
# chip-1 address moves. Four words per channel: MatrixOn[1-2] then
# MatrixSend[1-2], in the order gen_dsp.py::expand_routing emits them.
_mtx_rows = {r['id']: r for r in rows}
for ch in range(1, NUM_CH + 1):
    p, a = c1_alloc.next(2 * NUM_MTX_SEND)
    _r = _mtx_rows[f'C1_RTG_{ch:02d}']
    _r['params'] += f';mtx_page={p};mtx_addr={a}'

# --- LCR: THE PER-CHANNEL SELECT AND THE SYSTEM LAW (PW ruling R5) -----
#
# `Chan[1-32]LcrOn[1-1]` is one word per channel and `Sys[1-1]LcrLaw[1-1]`
# is ONE word for the whole desk. Both are allocated HERE, after every
# other chip-1 allocation, for the matrix sends' reason: the strip's
# 144-word page is exactly full (FADER_PAN 80..83, ROUTING 84..143), so
# putting either inside it would move every chip-1 address above channel
# 1's routing node -- the whole map, the MCU's ghost table and every
# stored golden. The bump ADDS rows and moves NONE.
#
# The consequence S22-4 paid for is handled in the DSP and not here: a
# write outside the 144-word page lands in the control-epoch catch-all
# that no strip node watches, so the FADER_PAN node raises `_fdr_busy`
# for one block whenever the (LcrOn, law) pair moves, which is the same
# word ROUTING already re-preps on when a pan ramps.
#
# The fourth word of the FADER_PAN block is NOT reused. It is reserved by
# PW's 2026-08-30 ruling (Dca host-managed) and reserved means reserved;
# reclaiming it would be a contract decision and it is not this session's.
_lcr_rows = {r['id']: r for r in rows}
for ch in range(1, NUM_CH + 1):
    p, a = c1_alloc.next(1)
    _lcr_rows[f'C1_FDR_{ch:02d}']['params'] += f';lcr_page={p};lcr_addr={a}'
_sys_p, _sys_a = c1_alloc.next(1)
_lcr_rows['C1_FDR_01']['params'] += f';syslaw_page={_sys_p};syslaw_addr={_sys_a}'

# Sanity: legacy bus order must land on global slots 0-24 unchanged. The
# matrix buses are checked separately -- they are new slots, and pinning them
# to a literal here is what would catch a slot-map edit that moved them onto
# something else.
assert [MIX_GLOBAL[bus_signal[b]] for b in legacy_bus_ids] == list(range(25))
assert [MIX_GLOBAL[bus_signal[b]] for b in bus_mtx] == list(range(37, 37 + NUM_MTX))

# --- Superset fabric pass-through sends (sources generated above) ---
for sig, src, scope in xfer_map:
    fp = fabric_params(sig)
    if scope:
        fp += f';scope={scope}'
    add(f'C1_XS_{sig}', 1, 'INTERCHIP_SEND', f'{sig} Send', 1, src, '',
        params=fp)

# --- SELF-TEST: oscillator + measurement (S49) ---
#
# The `Test[1-1]*` cell family finally gets graph nodes. Both are on CHIP 1,
# because every cell in the family names a CHANNEL (OscChan, MeasChan,
# XtalkSrc, XtalkDst are all MxDatS 33 = 0..32) and the channel strips are
# chip 1's.
#
# LAST IN THE CHIP-1 NODE LIST, and that is two decisions in one:
#
#   * ADDRESSES. The allocator packs sequentially, so a node added anywhere
#     else moves every chip-1 address above it -- the whole landed map, the
#     MCU ghost table and every stored golden. Added here they take the next
#     free words above the LCR block and NOTHING MOVES. This is the same
#     rule S22-4 followed for the matrix sends.
#   * CHAIN ORDER. The oscillator generates the block the strips will read on
#     the NEXT pass, and the measurement engine closes its window after every
#     strip has run. Both belong at the tail. The injection and the tap are
#     not these calls: they are hooks the chain emits at each strip
#     (DSP4_TEST_NODES), so the block a strip is given and the block the
#     correlation is taken against are the SAME block, with no relative delay
#     to correct for.
#     THE MEASUREMENT NODE COMES FIRST, and that is not cosmetic. The
#     strips inject and tap the block the oscillator generated on the
#     PREVIOUS pass; the measurement engine's reference self-sums have to
#     be taken over that same block, so it must run before the oscillator
#     overwrites it. Reverse these two and the reference is one block out
#     of step with the signal it is the reference for.
p, a = c1_alloc.next(8)
add('C1_TEST_MEAS', 1, 'TEST_MEAS', 'Test Measurement', 1, '', '',
    spi_page=p, spi_addr=a,
    params='meas_chan=0;xtalk_src=0;xtalk_dst=0;osc_src=C1_TEST_OSC',
    ramp_profile='InstantCtl')
p, a = c1_alloc.next(8)
add('C1_TEST_OSC', 1, 'TEST_OSC', 'Test Oscillator', 1, '', '',
    spi_page=p, spi_addr=a,
    params='on=0;freq_hz=1000.0;level=0.0;chan=0;sweep_on=0;sweep_step=0;'
           'meas_src=C1_TEST_MEAS',
    ramp_profile='InstantCtl')

# ===========================================================================
# CHIP 2 — Output DSP
# ===========================================================================

# --- Inter-chip RECV nodes (one per bus) ---
recv_ids = {}
recv_sig = {}
for bus_label, bus_key, sig in [('Main L', 'main_l', 'BUS_MAIN_L'),
                                ('Main R', 'main_r', 'BUS_MAIN_R'),
                                ('Sub', 'sub', 'BUS_SUB')]:
    nid = f'C2_RECV_{bus_key.upper()}'
    add(nid, 2, 'INTERCHIP_RECV', f'{bus_label} Recv', 1, '', '',
        params=fabric_params(sig))
    recv_ids[bus_key] = nid

for g in range(1, NUM_GRP + 1):
    nid = f'C2_RECV_GRP_{g:02d}'
    add(nid, 2, 'INTERCHIP_RECV', f'Grp {g} Recv', 1, '', '',
        params=fabric_params(f'BUS_GRP_{g:02d}'))
    recv_ids[f'grp_{g}'] = nid

for a in range(1, NUM_AUX + 1):
    nid = f'C2_RECV_AUX_{a:02d}'
    add(nid, 2, 'INTERCHIP_RECV', f'Aux {a} Recv', 1, '', '',
        params=fabric_params(f'BUS_AUX_{a:02d}'))
    recv_ids[f'aux_{a}'] = nid

for f in range(1, NUM_FX + 1):
    nid = f'C2_RECV_FX_{f:02d}'
    add(nid, 2, 'INTERCHIP_RECV', f'FX {f} Recv', 1, '', '',
        params=fabric_params(f'BUS_FX_{f:02d}'))
    recv_ids[f'fx_{f}'] = nid

last_bus_recv_idx = len(rows)  # splice point for superset recv rows

# --- AUX BUSES ×12 (Chip 2) ---
# Chain: RECV → FDR → EQ → ANTIFB → LIM → DLY → OUT
# Output patch: AUX_DAC above — the D24 copper, not the slot numbers
for a in range(1, NUM_AUX + 1):
    aa = f'{a:02d}'
    recv = recv_ids[f'aux_{a}']
    n_fdr = f'C2_AUX_FDR_{aa}'
    n_eq  = f'C2_AUX_EQ_{aa}'
    n_geq = f'C2_AUX_GEQ_{aa}'
    n_afb = f'C2_AUX_AFB_{aa}'
    n_lim = f'C2_AUX_LIM_{aa}'
    n_dly = f'C2_AUX_DLY_{aa}'
    n_out = f'C2_AUX_OUT_{aa}'

    # Update recv outputs
    for r in rows:
        if r['id'] == recv:
            r['outputs'] = n_fdr

    p, a2 = c2_alloc.next(4)
    add(n_fdr, 2, 'FADER_PAN', f'Aux {a} Fader', 1, recv, n_eq,
        spi_page=p, spi_addr=a2,
        params='level_db=0.0;pan=0.0;mute=0;host_cells=Dca,DcaOn',
        ramp_profile='GainFast')

    p, a2 = c2_alloc.next(24)
    add(n_eq, 2, 'EQ_BIQUAD', f'Aux {a} EQ', 1, n_fdr,
        n_geq if 'aux' in GEQ_ON else n_afb,
        spi_page=p, spi_addr=a2,
        params='bands=4;coeffs=default',
        ramp_profile='EqSafe')

    if 'aux' in GEQ_ON:
        p, a2 = c2_alloc.next(GEQ_BANDS)
        add(n_geq, 2, 'GEQ', f'Aux {a} GEQ', 1, n_eq, n_afb,
            spi_page=p, spi_addr=a2,
            params=f'bands={GEQ_BANDS}',
            ramp_profile='EqSafe')

    p, a2 = c2_alloc.next(24)  # 6 notches × (freq + gain + Q + biquad coeffs)
    add(n_afb, 2, 'ANTI_FB', f'Aux {a} AntiFB', 1,
        n_geq if 'aux' in GEQ_ON else n_eq, n_lim,
        spi_page=p, spi_addr=a2,
        params='notch_count=6',
        ramp_profile='EqSafe')

    p, a2 = c2_alloc.next(4)
    add(n_lim, 2, 'LIMITER', f'Aux {a} Lim', 1, n_afb, n_dly,
        spi_page=p, spi_addr=a2,
        params='threshold_db=-0.5;attack_ms=0.1;release_ms=50.0',
        ramp_profile='DynSafe')

    p, a2 = c2_alloc.next(2)
    add(n_dly, 2, 'DELAY', f'Aux {a} Delay', 1, n_lim, n_out,
        spi_page=p, spi_addr=a2,
        params='delay_ms=0.0;max_ms=250.0',
        ramp_profile='InstantCtl')

    p, a2 = c2_alloc.next(1)
    add(n_out, 2, 'OUTPUT_TDM', f'Aux {a} Out', 1, n_dly, '',
        spi_page=p, spi_addr=a2,
        params=output_params(AUX_DAC[a]))

# --- GROUP BUSES ×4 (Chip 2) ---
# Chain: RECV → FDR → EQ → GATE → COMP → (feed to Main)
for g in range(1, NUM_GRP + 1):
    gg = f'{g:02d}'
    recv = recv_ids[f'grp_{g}']
    n_fdr  = f'C2_GRP_FDR_{gg}'
    n_eq   = f'C2_GRP_EQ_{gg}'
    n_gate = f'C2_GRP_GATE_{gg}'
    n_comp = f'C2_GRP_COMP_{gg}'

    for r in rows:
        if r['id'] == recv:
            r['outputs'] = n_fdr

    p, a2 = c2_alloc.next(4)
    add(n_fdr, 2, 'FADER_PAN', f'Grp {g} Fader', 1, recv, n_eq,
        spi_page=p, spi_addr=a2,
        params='level_db=0.0;mute=0;host_cells=Dca,DcaOn',
        ramp_profile='GainFast')

    p, a2 = c2_alloc.next(24)
    add(n_eq, 2, 'EQ_BIQUAD', f'Grp {g} EQ', 1, n_fdr, n_gate,
        spi_page=p, spi_addr=a2,
        params='bands=4;coeffs=default',
        ramp_profile='EqSafe')

    p, a2 = c2_alloc.next(16)
    add(n_gate, 2, 'GATE', f'Grp {g} Gate', 1, n_eq, n_comp,
        spi_page=p, spi_addr=a2,
        params='threshold_db=-40.0;attack_ms=1.0;hold_ms=50.0;release_ms=100.0;range_db=60.0;key=0',
        ramp_profile='DynSafe')

    p, a2 = c2_alloc.next(16)
    add(n_comp, 2, 'COMPRESSOR', f'Grp {g} Comp', 1, n_gate, 'C2_MIX_MAIN_L;C2_MIX_MAIN_R',
        spi_page=p, spi_addr=a2,
        params='threshold_db=-20.0;ratio=4.0;attack_ms=5.0;release_ms=100.0;knee_db=6.0;makeup_db=0.0;type=VCA',
        ramp_profile='DynSafe')

# ===========================================================================
# THE CENTRE STRIP AND THE SHARED C/LF TAIL  (S144, PW rulings D6 + D5)
# ===========================================================================
#
# THIS IS THE OLD SUB-BUS CHAIN, RE-PATCHED, NOT A NEW ONE — which is why
# it costs no address move. `C1_BUS_SUB` carries every channel's
# `Chan*CtrOn` send: on this product THE SUB BUS IS THE CENTRE BUS (PW
# ruling R5), so the chain it feeds is the CENTRE strip and always was. It
# has been marked retired-not-deleted since S1 for want of a cell to
# reach; the 24 Sep master block gives it the whole `MainCtr` family.
#
# WHAT THE BLOCK DRAWS, and each line is one node below:
#
#   Ctr Channel Bus -> MainCtr fader/mute -> 4-band EQ -> 31-band GEQ
#                   -> anti-feedback (S144 item 4) -> limiter
#   Main L/R sum    -> MainSub Src select -> Woof LPF -> fader -> 2-band EQ
#                   -> limiter
#   both            -> Out3Mode select -> ONE mute, meter, delay and DAC
#
# EVERY NODE HERE IS A RENAME OF A SUB-CHAIN NODE OR IS ALLOCATED AFTER
# EVERY OTHER CHIP-2 NODE. The renames keep their SPI words to the word:
#
#   C2_SUB_FDR (4w)  -> C2_CTR_FDR    MainCtr Level/Mute/Dca/DcaOn
#   C2_SUB_EQ (24w)  -> C2_CTR_EQ     MainCtr Eq*, MainCtr PeqGain*
#   C2_SUB_COMP(16w) -> RESERVED      the block draws NO compressor on the
#                                     centre strip, and the 28 Sep audit
#                                     dropped every `Main*Comp*` cell from
#                                     D24's generation. The sixteen words
#                                     are held, not reclaimed.
#   C2_SUB_LIM (4w)  -> C2_CTR_LIM    MainCtr Limiter*
#   C2_SUB_DLY (2w)  -> C2_OUT3_DLY   Main Out3Delay   (the SHARED delay)
#   C2_SUB_OUT (1w)  -> C2_OUT3_OUT   Main Out3Mute, and its lane moves
#                                     from NET_OUT_01 to DAC_14, the rear
#                                     Center/LF XLR J55
#   C2_MTR_SUB (1w)  -> C2_MTR_OUT3   Main Out3Mtr     (the SHARED meter)
#
# The same shape S122 used when `C2_MON_OUT` became `C2_SPKR_OUT`: a rename
# and a new source, so no address moves.
recv_sub = recv_ids['sub']
for r in rows:
    if r['id'] == recv_sub:
        r['outputs'] = 'C2_CTR_FDR'

p, a2 = c2_alloc.next(4)
add('C2_CTR_FDR', 2, 'FADER_PAN', 'Centre Fader', 1, recv_sub, 'C2_CTR_EQ',
    spi_page=p, spi_addr=a2,
    params='level_db=0.0;mute=0;host_cells=Dca,DcaOn',
    ramp_profile='GainFast')

p, a2 = c2_alloc.next(24)
add('C2_CTR_EQ', 2, 'EQ_BIQUAD', 'Centre EQ', 1, 'C2_CTR_FDR', 'C2_CTR_GEQ',
    spi_page=p, spi_addr=a2,
    params='bands=4;coeffs=default',
    ramp_profile='EqSafe')

# `MainCtr Geq[1-31]` (PW ruling D6, block D19). NOT behind `--geq-outputs`:
# a landed contract cell that an option can switch off is a cell with no
# reader half the time, which is the shape this repo calls a defect. The
# `sub` GEQ class is gone from that option with the sub bus it named.
_late_c2('C2_CTR_GEQ', GEQ_BANDS)
add('C2_CTR_GEQ', 2, 'GEQ', 'Centre GEQ', 1, 'C2_CTR_EQ', 'C2_CTR_AFB',
    params=f'bands={GEQ_BANDS}',
    ramp_profile='EqSafe')

# `MainCtr AntiFb*` (PW ruling D9, block B25/C25). AFTER the GEQ and BEFORE
# the limiter, which is the aux chain's order (FDR -> EQ -> GEQ -> AFB ->
# LIM) and the right one: a notch placed after the limiter is a notch the
# limiter has already pumped against.
_late_c2('C2_CTR_AFB', 24)
add('C2_CTR_AFB', 2, 'ANTI_FB', 'Centre AntiFB', 1, 'C2_CTR_GEQ', 'C2_CTR_LIM',
    params='notch_count=6;fb_lim_db=-6.0',
    ramp_profile='EqSafe')

# C2_SUB_COMP's sixteen words, held so nothing below them moves. Stated as
# an allocation rather than left as a silent gap: the next reader of this
# file needs to know the hole is deliberate and what used to be in it.
c2_alloc.next(16)          # RESERVED — was C2_SUB_COMP (S144, ruling D6)

p, a2 = c2_alloc.next(4)
add('C2_CTR_LIM', 2, 'LIMITER', 'Centre Lim', 1, 'C2_CTR_AFB', 'C2_OUT3_SEL',
    spi_page=p, spi_addr=a2,
    params='threshold_db=-0.5;attack_ms=0.1;release_ms=50.0',
    ramp_profile='DynSafe')

# THE SHARED TAIL keeps C2_SUB_DLY's and C2_SUB_OUT's words, so the two
# addresses are taken HERE, in the old chain's position — but the ROWS are
# added after the Woof strip, because the Woof reads `C2_MAIN_DLY` and so
# the source select in front of the tail cannot run until the main chain
# has. Addresses come from call order; process order comes from row order;
# this is the one place in the file where the two have to be told apart.
_OUT3_DLY_PA = c2_alloc.next(2)
_OUT3_OUT_PA = c2_alloc.next(1)

# --- MAIN L/R BUS (Chip 2) ---
# Chain: RECV → MIX (with group/aux-input feeds) → MASTER_FDR → GEQ_28 →
#        COMP → LIM → DLY → XOVER → per-output EQ/COMP/LIM → OUT

# Main mix receives direct channel sums + group output feeds + superset
# aux inputs (USB/BT/codec aux/Pi/snake, all default-off) + THE SIX FX
# RETURNS.
#
# THE FX RETURNS WERE MISSING AND THAT WAS S22-2 (fixed here, S23 gate 2).
# `C2_FX_FDR_nn` has always DECLARED `outputs=C2_MIX_MAIN_L;C2_MIX_MAIN_R`,
# but a MIX_BUS is fed from its OWN `inputs` -- gen_mix_bus_fixed MACs over
# `inputs` and nothing else -- and neither main mix node listed a single FX
# return. No `_buf_C2_FX_FDR_*` was read by any mix node on either chip, so
# the six engines were INAUDIBLE on every image this tree has ever built
# while costing their full price. `outputs` is documentation; `inputs` is
# the graph.
#
# THE RETURN REACHES THE MAIN MIX AT UNITY AND THERE IS NO SEND CELL,
# because the cell master defines none: `Fx[1-8]Level`, `Fx[1-8]Mute` and
# `Fx[1-8]Dca/DcaOn` are the whole of the return's own level control and
# they are already the FADER_PAN node's. There is no `Fx*MainOn`, no
# `Fx*MainSend` and no `Fx*Pan`, so the crosspoint is a constant 1.0 and
# this gate adds NO cell and moves NO address -- it is a wiring defect
# being fixed, not a contract bump. (The return's pan word exists in the
# node and is dispatched-but-uncelled; the engine is mono end to end, so
# the two mix legs read the same block. That a stereo FX return would need
# a `Fx*Pan` cell is a question for PW, not a thing to invent.)
# THE STEREO SUPERSET RETURNS FEED THE MIX LEG THAT IS THEIR OWN SIDE
# (S143). `C2_CODEC_AUX_IN` and `C2_PI_IN` are stereo pairs -- master
# (L) and follower (R) -- so the right mix reads the followers. USB, BT
# and the eight snake returns are single nodes and feed both legs, which
# is what they have always done: the host writes ONE word for USB and BT
# (see their rows) and a snake return is one fabric slot. Making those
# genuinely stereo is a graph change with a wire behind it, so it is
# RECORDED here rather than invented.
aux_input_l = ['C2_USB_IN', 'C2_BT_IN', 'C2_CODEC_AUX_IN', 'C2_PI_IN'] + \
    [f'C2_SNK_IN_{s:02d}' for s in range(1, 9)]
aux_input_r = ['C2_USB_IN', 'C2_BT_IN', 'C2_CODEC_AUX_IN_R', 'C2_PI_IN_R'] + \
    [f'C2_SNK_IN_{s:02d}' for s in range(1, 9)]
grp_comp_ids = ';'.join(f'C2_GRP_COMP_{g:02d}' for g in range(1, NUM_GRP + 1))
aux_in_str = ';'.join(aux_input_l)
aux_in_str_r = ';'.join(aux_input_r)
fx_fdr_ids = ';'.join(f'C2_FX_FDR_{f:02d}' for f in range(1, NUM_FX + 1))
main_l_sources = f'{recv_ids["main_l"]};{grp_comp_ids};{aux_in_str};{fx_fdr_ids}'
main_r_sources = f'{recv_ids["main_r"]};{grp_comp_ids};{aux_in_str_r};{fx_fdr_ids}'

for r in rows:
    if r['id'] == recv_ids['main_l']:
        r['outputs'] = 'C2_MIX_MAIN_L'
    if r['id'] == recv_ids['main_r']:
        r['outputs'] = 'C2_MIX_MAIN_R'

p, a2 = c2_alloc.next(4)
add('C2_MIX_MAIN_L', 2, 'MIX_BUS', 'Main Mix L', 1, main_l_sources, 'C2_MAIN_FDR',
    spi_page=p, spi_addr=a2,
    params='bus_id=0')

p, a2 = c2_alloc.next(4)
add('C2_MIX_MAIN_R', 2, 'MIX_BUS', 'Main Mix R', 1, main_r_sources,
    'C2_MAIN_FDR_R',
    spi_page=p, spi_addr=a2,
    params='bus_id=1')

# ===========================================================================
# THE MAIN BUS IS STEREO FROM THE MASTER FADER ON (S143, closing S142-1)
# ===========================================================================
#
# IT WAS NOT, AND NOTHING SAID SO. `C2_MAIN_FDR` declared
# `inputs=C2_MIX_MAIN_L;C2_MIX_MAIN_R` and `ch_count=2`; the generator read
# `inputs[0]`. So `_blk_C2_MIX_MAIN_R` was computed every block by a mix bus
# with seventeen sources and read by NOTHING, and both MAIN XLRs (DAC_12
# J56, DAC_11 J57), both DAC MAIN slots, the codec aux out and the monitor
# all carried the LEFT bus. The stereo image exists on chip 1 -- S121
# measured a hard-panned strip reading exact digital zero on the other side
# -- and was discarded one node into chip 2.
#
# THE SHAPE OF THE FIX is D5's own ruling: "TWO DSP instances (Main L, Main
# R) sharing ONE parameter set". Each stage of the chain is a MASTER and a
# FOLLOWER; the follower reads the master's coefficient symbols by name,
# keeps its own state, takes NO cell and NO SPI address, and therefore
# needs no dispatch change and no contract bump. The mechanism is general
# (`follows=` in params) and lives in dsp_codegen.py under STEREO FOLLOWERS.
#
# THE TWO DYNAMICS STAGES ARE LINKED, NOT DUPLICATED. `link_in=` names the
# other leg, both legs detect on max(|L|,|R|), and from one parameter set
# and one initial envelope they compute the SAME gain sample for sample --
# so the bus compressor and the brick wall pull both sides together and the
# image does not walk. That costs the two cross-chain SIMD pairs
# (`_C2_CROSS_PAIRS`, MAIN_COMP+SUB_COMP and MAIN_LIM+SUB_LIM): the pair
# kernel reads one block per channel and has no second detector input, so
# those four nodes fall back to their scalar bodies. Stated, priced, and
# due to dissolve anyway -- S142 §3.2 deletes `C2_SUB_COMP`.
#
# ROW ORDER IS THE PROCESS ORDER (S23-3's precedent): each follower sits
# immediately after its master, so `repair_process_order` has nothing to
# move and `c2_pair_groups` still sees contiguous runs.
p, a2 = c2_alloc.next(4)
add('C2_MAIN_FDR', 2, 'FADER_PAN', 'Main Fader', 2, 'C2_MIX_MAIN_L',
    'C2_MAIN_GEQ' if 'main' in GEQ_ON else 'C2_MAIN_COMP',
    spi_page=p, spi_addr=a2,
    params='level_db=0.0;mute=0;host_cells=Dca,DcaOn',
    ramp_profile='GainFast')
add('C2_MAIN_FDR_R', 2, 'FADER_PAN', 'Main Fader R', 1, 'C2_MIX_MAIN_R',
    'C2_MAIN_GEQ_R' if 'main' in GEQ_ON else 'C2_MAIN_COMP_R',
    params='follows=C2_MAIN_FDR',
    ramp_profile='GainFast')

if 'main' in GEQ_ON:
    p, a2 = c2_alloc.next(GEQ_BANDS)
    add('C2_MAIN_GEQ', 2, 'GEQ', 'Main GEQ', 2, 'C2_MAIN_FDR', 'C2_MAIN_COMP',
        spi_page=p, spi_addr=a2,
        params=f'bands={GEQ_BANDS}',
        ramp_profile='EqSafe')
    add('C2_MAIN_GEQ_R', 2, 'GEQ', 'Main GEQ R', 1, 'C2_MAIN_FDR_R',
        'C2_MAIN_COMP_R',
        params=f'bands={GEQ_BANDS};follows=C2_MAIN_GEQ',
        ramp_profile='EqSafe')

# `Main AntiFb*` (PW ruling D9, block B25/C25): TWO INSTANCES, ONE
# PARAMETER SET -- the stereo main bus needs the same six notches on both
# legs or the image shifts as each one goes in, which is D5's ruling applied
# to the anti-feedback the way S143 applied it to the GEQ. The follower
# `.extern`s the master's notch set, its design and its ring-out gain, and
# owns its own filter state, its own crossfade and its own limiter
# ENVELOPE (an envelope is per channel or it is not an envelope).
_afb_in_l = 'C2_MAIN_GEQ' if 'main' in GEQ_ON else 'C2_MAIN_FDR'
# `outputs` is documentation and `inputs` is the graph (S22-2), and this
# file keeps the documentation true: the node ahead of the AFB pair named
# the compressor until the AFB went between them.
for r in rows:
    if r['id'] in (_afb_in_l, _afb_in_l + '_R'):
        r['outputs'] = ('C2_MAIN_AFB_R' if r['id'].endswith('_R')
                        else 'C2_MAIN_AFB')
_late_c2('C2_MAIN_AFB', 24)
add('C2_MAIN_AFB', 2, 'ANTI_FB', 'Main AntiFB', 2, _afb_in_l,
    'C2_MAIN_COMP',
    params='notch_count=6;fb_lim_db=-6.0',
    ramp_profile='EqSafe')
add('C2_MAIN_AFB_R', 2, 'ANTI_FB', 'Main AntiFB R', 1, _afb_in_l + '_R',
    'C2_MAIN_COMP_R',
    params='notch_count=6;fb_lim_db=-6.0;follows=C2_MAIN_AFB',
    ramp_profile='EqSafe')

_main_dyn_l = 'C2_MAIN_AFB'
_main_dyn_r = 'C2_MAIN_AFB_R'

p, a2 = c2_alloc.next(16)
add('C2_MAIN_COMP', 2, 'COMPRESSOR', 'Main Comp', 2,
    f'{_main_dyn_l};{_main_dyn_r}', 'C2_MAIN_LIM',
    spi_page=p, spi_addr=a2,
    params='threshold_db=-20.0;ratio=4.0;attack_ms=5.0;release_ms=100.0;knee_db=6.0;makeup_db=0.0;parallel=100;type=VCA'
           f';link_in={_main_dyn_r}',
    ramp_profile='DynSafe')
add('C2_MAIN_COMP_R', 2, 'COMPRESSOR', 'Main Comp R', 1,
    f'{_main_dyn_r};{_main_dyn_l}', 'C2_MAIN_LIM_R',
    params=f'follows=C2_MAIN_COMP;link_in={_main_dyn_l}',
    ramp_profile='DynSafe')

p, a2 = c2_alloc.next(4)
add('C2_MAIN_LIM', 2, 'LIMITER', 'Main Lim', 2,
    'C2_MAIN_COMP;C2_MAIN_COMP_R', 'C2_MAIN_DLY',
    spi_page=p, spi_addr=a2,
    params='threshold_db=-0.5;attack_ms=0.1;release_ms=50.0'
           ';link_in=C2_MAIN_COMP_R',
    ramp_profile='DynSafe')
add('C2_MAIN_LIM_R', 2, 'LIMITER', 'Main Lim R', 1,
    'C2_MAIN_COMP_R;C2_MAIN_COMP', 'C2_MAIN_DLY_R',
    params='follows=C2_MAIN_LIM;link_in=C2_MAIN_COMP',
    ramp_profile='DynSafe')

p, a2 = c2_alloc.next(2)
add('C2_MAIN_DLY', 2, 'DELAY', 'Main Delay', 2, 'C2_MAIN_LIM',
    'C2_MAIN_XOVER;C2_MAIN_ST_OUT;C2_CODEC_AUX_OUT;C2_WOOF_MIX',
    spi_page=p, spi_addr=a2,
    params='delay_ms=0.0;max_ms=250.0',
    ramp_profile='InstantCtl')
add('C2_MAIN_DLY_R', 2, 'DELAY', 'Main Delay R', 1, 'C2_MAIN_LIM_R',
    'C2_MAIN_XOVER_R;C2_MAIN_ST_OUT_R;C2_CODEC_AUX_OUT_R;C2_WOOF_MIX',
    params='delay_ms=0.0;max_ms=250.0;follows=C2_MAIN_DLY',
    ramp_profile='InstantCtl')

# THE MAIN CROSSOVER IS THE HPF HALF OF THE PAIR, and the LPF half lives on
# the Woof strip. That is what the two cell families say in as many words:
# `Main CrossoverFreq` is "Main L/R HPF crossover frequency: ONE parameter
# set driving the two DSP crossover instances (Main L and Main R); LF
# summed ..." and `MainSub CrossoverFreq` is "Woof LPF crossover frequency:
# applies when Main CrossoverLink = 0 (UNLINK); linked it follows Main
# CrossoverFreq". Two filters, one corner when linked — a Linkwitz-Riley
# pair with the low-pass placed in the strip whose cells describe it.
#
# SO THE WOOF READS `C2_MAIN_DLY`, NOT THE CROSSOVER'S LP LEG. S142 §3.2
# designed it the other way (`C2_MAIN_XOVER(LP) + C2_MAIN_XOVER_R(LP) ->
# C2_WOOF_MIX`) and that design low-passes the LF path TWICE at the same
# corner whenever `MainSub Src` is 0 and `Main CrossoverLink` is 1 — LR4
# then LR4, 12 dB down at the corner instead of 6, and LP + HP no longer
# summing flat. `MainSub Src = 0` is spelled "Main L/R **sum**" in the
# cell's own note, which is this node's input, so the sum is taken here and
# the only low-pass in the LF path is the Woof's own. Recorded as a
# departure from the S142 design in the S144 report rather than left as a
# silent difference.
#
# `Main CrossoverOn` and `Main CrossoverLink` COST NO NEW ALLOCATION. This
# node holds four words; Freq is +0 and Slope is +1, and +2/+3 were
# dispatched only as staging-array coefficients that nothing wrote.
p, a2 = c2_alloc.next(4)
add('C2_MAIN_XOVER', 2, 'CROSSOVER', 'Main Xover', 2,
    'C2_MAIN_DLY', 'C2_MAIN_OUT_01',
    spi_page=p, spi_addr=a2,
    params='freq=120.0;slope=24;on_cell=1;link_cell=1',
    ramp_profile='EqSafe')
add('C2_MAIN_XOVER_R', 2, 'CROSSOVER', 'Main Xover R', 1,
    'C2_MAIN_DLY_R', 'C2_MAIN_OUT_02',
    params='freq=120.0;slope=24;follows=C2_MAIN_XOVER',
    ramp_profile='EqSafe')

# --- Per-output processing (Main ×2) ---
# Output patch: MAIN_OUT_DAC above — outs 1/2 on the MAIN XLRs
#
# OUTPUT 2 IS MainR AND READS THE RIGHT CROSSOVER (S143). OUTPUTS 3 AND 4
# ARE GONE (S144, ruling D6): they were MainCtr and MainSub as post-
# crossover legs of the main chain, both reading the LEFT crossover, and
# the master block draws neither that way. MainCtr is the Centre strip off
# the Ctr Channel Bus and MainSub is the Woof strip off the Main L/R sum;
# both are above/below, with their own cells. Their SPI words are RESERVED,
# not reclaimed, so no address below them moves.
#
# ALSO CORRECTED BY THEIR REMOVAL, and worth recording because it was
# measured by nothing: `_buf_C2_MAIN_XOVER` is the crossover's HIGH-PASS
# leg (gen_crossover_fixed writes hp into both `_buf_hp_` and `_buf_`), so
# output 4 — MainSub, the rear "sub" jack — carried the HIGH-passed main
# bus. The sub output was high-passed. It is finding S144-1.
_xover_of_out = {1: 'C2_MAIN_XOVER', 2: 'C2_MAIN_XOVER_R'}
for out_n in range(1, 5):
    oo = f'{out_n:02d}'
    if out_n in MAIN_OUT_RESERVE:
        # Held, in the shape the loop would have allocated them: EQ 24,
        # COMP 16, LIM 4, OUT 1.
        for _w in (24, 16, 4, 1):
            c2_alloc.next(_w)
        continue
    n_eq   = f'C2_MAIN_OEQ_{oo}'
    n_comp = f'C2_MAIN_OCOMP_{oo}'
    n_lim  = f'C2_MAIN_OLIM_{oo}'
    n_out  = f'C2_MAIN_OUT_{oo}'

    p, a2 = c2_alloc.next(24)
    add(n_eq, 2, 'EQ_BIQUAD', f'Main Out {out_n} EQ', 1,
        _xover_of_out[out_n], n_comp,
        spi_page=p, spi_addr=a2,
        params='bands=4;coeffs=default',
        ramp_profile='EqSafe')

    p, a2 = c2_alloc.next(16)
    add(n_comp, 2, 'COMPRESSOR', f'Main Out {out_n} Comp', 1, n_eq, n_lim,
        spi_page=p, spi_addr=a2,
        params='threshold_db=-20.0;ratio=4.0;attack_ms=5.0;release_ms=100.0;knee_db=6.0;makeup_db=0.0;type=VCA',
        ramp_profile='DynSafe')

    p, a2 = c2_alloc.next(4)
    add(n_lim, 2, 'LIMITER', f'Main Out {out_n} Lim', 1, n_comp, n_out,
        spi_page=p, spi_addr=a2,
        params='threshold_db=-0.5;attack_ms=0.1;release_ms=50.0',
        ramp_profile='DynSafe')

    p, a2 = c2_alloc.next(1)
    add(n_out, 2, 'OUTPUT_TDM', f'Main Out {out_n}', 1, n_lim, '',
        spi_page=p, spi_addr=a2,
        params=output_params(MAIN_OUT_DAC[out_n]))

# ===========================================================================
# THE WOOF STRIP AND THE Out3 SOURCE SELECT  (S144, PW rulings D6 + D5)
# ===========================================================================
#
# Row order, not address order: every node here reads `C2_MAIN_DLY` (or
# something that does), so the rows sit AFTER the main chain and their SPI
# words are allocated after every other chip-2 node (below, with the rest
# of the late allocations). The Out3 tail's two rows — whose addresses came
# from the old sub chain — are added here too, for the same reason.
#
# `MainSub Src`: "0 = Main L/R sum / 1-16 = Aux N (D24: aux 1-8)". The
# superset declares twelve aux buses, so the select carries 1 + NUM_AUX
# sources and a D24 host uses the first nine of them. A select index past
# the source count clamps; that the cell's table says 16 and the fabric
# has 12 is a defs question, recorded, not resolved by inventing four
# buses.
#
# THE AUX TAP IS POST-DELAY (`C2_AUX_DLY_nn`), which is the aux output
# itself — a woof fed from an aux must be the same signal the aux XLR
# carries or the two disagree in the room.
# NO SPI ADDRESS, and that is the node: a fixed mono sum of the two main
# legs at unity. There is no `MainSub` cell for an LF-sum level -- the level
# is `MainSub Level` on the fader below -- so a word here would be a word
# with no cell and no reader.
add('C2_WOOF_MIX', 2, 'MIX_BUS', 'Woof LF Sum', 1,
    'C2_MAIN_DLY;C2_MAIN_DLY_R', 'C2_WOOF_SRC',
    params='bus_id=woof;source_count=2;no_spi=1')

_woof_srcs = ['C2_WOOF_MIX'] + [f'C2_AUX_DLY_{a:02d}'
                                for a in range(1, NUM_AUX + 1)]
_late_c2('C2_WOOF_SRC', 4)
add('C2_WOOF_SRC', 2, 'SOURCE_SEL', 'Woof Source', 1,
    ';'.join(_woof_srcs), 'C2_WOOF_XOVER',
    params=f'sources={len(_woof_srcs)};sel=0;xfade_ms=12.0'
           ';cell_suffix=Src',
    ramp_profile='GainFast')

# The Woof LPF. `link_from=` is `Main CrossoverLink`: with the link word
# set this node designs at the MASTER's corner and slope instead of its
# own, which is what "linked it follows Main CrossoverFreq" means. It is
# NOT a `follows=` follower — it has its own two cells and its own address.
_late_c2('C2_WOOF_XOVER', 4)
add('C2_WOOF_XOVER', 2, 'CROSSOVER', 'Woof Xover', 1,
    'C2_WOOF_SRC', 'C2_WOOF_FDR',
    params='freq=120.0;slope=24;link_from=C2_MAIN_XOVER',
    ramp_profile='EqSafe')

_late_c2('C2_WOOF_FDR', 4)
add('C2_WOOF_FDR', 2, 'FADER_PAN', 'Woof Fader', 1,
    'C2_WOOF_XOVER', 'C2_WOOF_EQ',
    params='level_db=0.0;mute=0;host_cells=Dca,DcaOn',
    ramp_profile='GainFast')

_late_c2('C2_WOOF_EQ', 24)
add('C2_WOOF_EQ', 2, 'EQ_BIQUAD', 'Woof EQ', 1, 'C2_WOOF_FDR', 'C2_WOOF_LIM',
    params='bands=2;coeffs=default',
    ramp_profile='EqSafe')

_late_c2('C2_WOOF_LIM', 4)
add('C2_WOOF_LIM', 2, 'LIMITER', 'Woof Lim', 1, 'C2_WOOF_EQ', 'C2_OUT3_SEL',
    params='threshold_db=-0.5;attack_ms=0.1;release_ms=50.0',
    ramp_profile='DynSafe')

# `Main Out3Mode` (0 = centre, 1 = subwoofer) and `Main Out3Link` ("L.R.
# Fader Link: the output-3 master fader ... follows the Main L/R fader").
# The link is a REAL DSP word, not a host mirror: with it set the Out3
# output is scaled by the main master fader's own ramped Q4.28 gain, so the
# C/LF XLR tracks the master. The Centre strip is fed from the Ctr Channel
# Bus and never passes the main fader, which is the path the link exists
# for; the Woof fed from `MainSub Src = 0` is ALREADY post-master, so
# linking applies the master fader twice there. Recorded for PW in the
# S144 report (finding S144-3) with the alternative reading — the host
# mirroring `Main Level` into `MainCtr/MainSub Level`, which would need no
# DSP word at all — and why the DSP reading was built: the cell is declared
# in D24's DSP generation, and a cell with no reader is S21-4's shape.
_late_c2('C2_OUT3_SEL', 4)
add('C2_OUT3_SEL', 2, 'SOURCE_SEL', 'Out3 Source', 1,
    'C2_CTR_LIM;C2_WOOF_LIM', 'C2_OUT3_DLY',
    params='sources=2;sel=0;xfade_ms=12.0;cell_suffix=Out3Mode'
           ';link_gain=C2_MAIN_FDR;link_cell_suffix=Out3Link',
    ramp_profile='GainFast')

p, a2 = _OUT3_DLY_PA
add('C2_OUT3_DLY', 2, 'DELAY', 'Out3 Delay', 1, 'C2_OUT3_SEL', 'C2_OUT3_OUT',
    spi_page=p, spi_addr=a2,
    params='delay_ms=0.0;max_ms=250.0;cell_prefix=Out3',
    ramp_profile='InstantCtl')

p, a2 = _OUT3_OUT_PA
add('C2_OUT3_OUT', 2, 'OUTPUT_TDM', 'Out3 (Centre/LF XLR)', 1,
    'C2_OUT3_DLY', '',
    spi_page=p, spi_addr=a2,
    params=output_params('DAC_14', scope='D24') + ';cell_prefix=Out3')

# --- FX ENGINES ×6 (Chip 2) ---
# Chain: RECV → FX_ENGINE → FDR → (feeds main/aux)
for f in range(1, NUM_FX + 1):
    ff = f'{f:02d}'
    recv = recv_ids[f'fx_{f}']
    n_eng = f'C2_FX_ENG_{ff}'
    n_fdr = f'C2_FX_FDR_{ff}'

    for r in rows:
        if r['id'] == recv:
            r['outputs'] = n_eng

    p, a2 = c2_alloc.next(24)  # all FX params: type + decay + predelay + delay_time + feedback + balance + damp + eq×3 + hpf + mod_rate + mod_level + lfo + width + mix + duck
    # ch_count 1: the engine is MONO end to end (see the return's note
    # below -- the two mix legs read the same block), so a `2` here would
    # be the comment text S142-1 was hiding behind.
    add(n_eng, 2, 'FX_ENGINE', f'FX {f} Engine', 1, recv, n_fdr,
        spi_page=p, spi_addr=a2,
        params='type=Reverb;room_size=0.7;damping=0.5;decay=2.0;predelay_ms=20.0;delay_ms=300.0;feedback=50;balance=50;eq_lo=0;eq_mid=0;eq_hi=0;hpf=80;mod_rate=1.0;mod_level=50;mix=30;duck_on=0;duck_sens=-10',
        ramp_profile='GainSafe')

    p, a2 = c2_alloc.next(4)
    add(n_fdr, 2, 'FADER_PAN', f'FX {f} Return', 1, n_eng, 'C2_MIX_MAIN_L;C2_MIX_MAIN_R',
        spi_page=p, spi_addr=a2,
        params='level_db=-6.0;mute=0;host_cells=Dca,DcaOn',
        ramp_profile='GainFast')

# --- MONITOR (Chip 2) ---
#
# THE MONITOR BUS NO LONGER REACHES A CONVERTER SLOT (S122, PW ruling
# 2026-09-26: "the spkr feed is for screen button haptics only, and should
# be completely separate from all mixer signal paths").
#
# It used to end on `C2_MON_OUT`, which wrote `CODEC_OUT_1` -- the AK4619's
# AOUT1L, the ONE codec DAC output fitted on a D24, and the panel speaker's
# feed through the TS482 on the digital board. So "monitor level" WAS
# "speaker level": the graph default (`level_l_db=0.0`, i.e. unity) left
# the speaker playing whatever the main bus carried, for as long as the
# unit stayed powered, and every self-test press that raised it left it up
# (S115, and the S110/S114 hiss PW heard). Zeroing the two monitor cells
# was the only thing that silenced it.
#
# `C2_MON_OUT` is now `C2_SPKR_OUT` and the haptic node feeds it; the
# monitor chain ENDS HERE, at `C2_MON_DLY`, publishing a block nothing
# reads. That is not an omission dressed up as a design: a D24 has NO
# connector for the monitor bus. The rear "Monitor Out" jacks are the main
# crossover's centre and sub legs (`MainCtr`/`MainSub` on DAC_15/16, S121-6),
# the headphone jack is DAC_09/10 off aux buses 9-10 and the Centre/LF XLR
# is DAC_14 off aux bus 12 -- and D24 declares aux 1-8, so no cell reaches
# any of them (S121-5). Those three sockets are ONE open PW question already
# on the board; where the monitor bus lands is part of it, and this file
# does not invent an answer. The nodes, their addresses and their cells
# (`Mon001Level001/002`, `Mon001InputSel001`) are UNCHANGED and unmoved --
# what changed is that writing them can no longer make a sound.
# THE MONITOR IS TWO INSTANCES SINCE S143, and that is what `Mon Level[1-2]`
# always meant. The node converts BOTH level cells at block rate and the
# sample path used the L shadow only, so `Mon001Level002` was settable with
# no effect -- the monitor half of S142-1, and gen_monitor_fixed's own
# "NOT FIXED HERE" note from the 08-27 audit. The follower is the R leg: it
# reads `_mon_q_r_`, the master's own converted word, off the master's own
# source select.
# ===========================================================================
# S144 (PW rulings D7 + D8): THE MONITOR REACHES ITS JACKS, THE PHONES ARE
# THEIR OWN PAIR, AND THE SOURCE IS A PICK-OFF
# ===========================================================================
#
# THE THREE OPEN SOCKETS ARE ANSWERED. The rear Monitor jacks J53/J54
# (DAC_15/16) carry the MONITOR bus -- which is what they are labelled for,
# and what they have not carried since the graph was written (S121-6 found
# them carrying the crossover's centre and sub legs; S122-5 recorded that
# the monitor chain ended on a block nothing read). The headphone jack J10
# (DAC_09/10) carries a SEPARATE phones pair with its own level and delay
# (ruling D7), not aux 9/10, which a D24 does not declare.
#
# `Mon PickOff` (ruling D8) is the tap: "0=pre-processing 1=post-processing
# 2=post-fader". Three taps of the main chain, one cell, both legs -- a
# SOURCE_SEL master and a follower, so the switch is one coefficient set and
# the two legs cannot land on different taps for a block. It powers up at 2,
# post-fader, which is the tap the monitor has always read (`C2_MAIN_FDR`),
# so the shipping default is what it was.
#
# `Mon InputSel` is UNCHANGED and still on C2_MON: "0 = the Main L-R source
# at the Mon PickOff tap / 1 = the cue bus". The pick-off chooses WHICH main
# tap; InputSel chooses main-or-cue. The phones read the SAME source select
# -- `source_from=C2_MON`, one word, both destinations, which is the
# ruling's "off the same Cue / Main L-R source select as the monitor
# output" -- and their own level and delay.
#
# `Mon CueOn` costs nothing: the host folds it and the cue state into the
# one `Mon InputSel` word (ruling D8, and the cell's own note says so).
#
# 🔴 TALKBACK INJECTION IS NOT BUILT AND IT IS NOT A GRAPH CHANGE. The
# talkback mics are CHIP-1 nodes with EMPTY outputs columns -- `C1_TALK_01`
# and `C1_TALK_02` reach no bus at all, which is the pre-existing `Talk
# Dest` gap S25 diagnosed and S26 declined -- so there is nothing on chip 2
# to inject. Reaching the phones from chip 1 needs a MIX-FABRIC SLOT for
# the talkback, and the fabric's slot map is single-sourced in
# shared/dsp4-logic/ (dsp4-architecture-decisions.md) and is a wire
# contract, not a graph edit. On top of that `Talk Dest`'s own note makes
# the destination ORDER provisional: "Main L/R + Aux 1-8 + phones ... y
# order provisional until the skin audit - PW ruling D13". So the phones
# are built with the crosspoint they will need and the injection is
# recorded as S144-4, with what it takes, rather than invented.
_late_c2('C2_MON_PICK', 4)
add('C2_MON_PICK', 2, 'SOURCE_SEL', 'Monitor Pick-off', 2,
    'C2_MIX_MAIN_L;C2_MAIN_DLY;C2_MAIN_FDR', 'C2_MON;C2_PHN',
    params='sources=3;sel=2;xfade_ms=12.0;cell_suffix=PickOff',
    ramp_profile='InstantCtl')
add('C2_MON_PICK_R', 2, 'SOURCE_SEL', 'Monitor Pick-off R', 1,
    'C2_MIX_MAIN_R;C2_MAIN_DLY_R;C2_MAIN_FDR_R', 'C2_MON_R;C2_PHN_R',
    params='sources=3;follows=C2_MON_PICK',
    ramp_profile='InstantCtl')

p, a2 = c2_alloc.next(6)
add('C2_MON', 2, 'MONITOR', 'Monitor', 2, 'C2_MON_PICK', 'C2_MON_DLY',
    spi_page=p, spi_addr=a2,
    params='level_l_db=0.0;level_r_db=0.0;source=main;follow_leg=l',
    ramp_profile='GainFast')
add('C2_MON_R', 2, 'MONITOR', 'Monitor R', 1, 'C2_MON_PICK_R', 'C2_MON_DLY_R',
    params='follows=C2_MON;follow_leg=r',
    ramp_profile='GainFast')

p, a2 = c2_alloc.next(2)
add('C2_MON_DLY', 2, 'DELAY', 'Monitor Delay', 2, 'C2_MON', 'C2_MON_OUT_L',
    spi_page=p, spi_addr=a2,
    params='delay_ms=0.0;max_ms=250.0',
    ramp_profile='InstantCtl')
add('C2_MON_DLY_R', 2, 'DELAY', 'Monitor Delay R', 1, 'C2_MON_R',
    'C2_MON_OUT_R',
    params='delay_ms=0.0;max_ms=250.0;follows=C2_MON_DLY',
    ramp_profile='InstantCtl')

# ONE NODE IS ONE SLOT (S143): the monitor pair is two OUTPUT_TDM nodes,
# one each, reading the two legs. No `mo_page`: the masters give the
# monitor a Level and a Delay and NO Mute, so there is no strip cell for
# this node to carry and it emits none.
add('C2_MON_OUT_L', 2, 'OUTPUT_TDM', 'Monitor Out L', 1, 'C2_MON_DLY', '',
    params=output_params('DAC_15', scope='D24'))
add('C2_MON_OUT_R', 2, 'OUTPUT_TDM', 'Monitor Out R', 1, 'C2_MON_DLY_R', '',
    params=output_params('DAC_16', scope='D24'))

# --- THE PHONES PAIR (Chip 2, ruling D7) ---
#
# The MONITOR kernel again, because it is exactly the right one: a source
# select it does not own (`source_from`) and one ramped level it does. Six
# words for the shape the kernel has, of which ONE carries a cell --
# `Mon PhonesLevel`, at +1 where `Mon Level[1]` sits on the monitor. The
# +0 word is the monitor's source and this node does not have one; +2 is
# the kernel's second level shadow, which both legs of a ONE-LEVEL pair
# leave alone. `mon_cells` says which, so no cell is emitted that no
# product defines.
_late_c2('C2_PHN', 6)
add('C2_PHN', 2, 'MONITOR', 'Phones', 2, 'C2_MON_PICK', 'C2_PHN_DLY',
    params='level_l_db=0.0;level_r_db=0.0;source=main;follow_leg=l'
           ';source_from=C2_MON;cell_prefix=Phones;mon_cells=Level1',
    ramp_profile='GainFast')
# follow_leg=l on BOTH legs: `Mon PhonesLevel` is ONE cell for the pair
# (the master's note: "separate from Mon Level"), so both instances run the
# same converted word. That is the difference from the monitor, whose two
# legs are two different cells.
add('C2_PHN_R', 2, 'MONITOR', 'Phones R', 1, 'C2_MON_PICK_R', 'C2_PHN_DLY_R',
    params='follows=C2_PHN;follow_leg=l',
    ramp_profile='GainFast')

_late_c2('C2_PHN_DLY', 2)
add('C2_PHN_DLY', 2, 'DELAY', 'Phones Delay', 2, 'C2_PHN', 'C2_PHN_OUT_L',
    params='delay_ms=0.0;max_ms=250.0;cell_prefix=Phones',
    ramp_profile='InstantCtl')
add('C2_PHN_DLY_R', 2, 'DELAY', 'Phones Delay R', 1, 'C2_PHN_R',
    'C2_PHN_OUT_R',
    params='delay_ms=0.0;max_ms=250.0;follows=C2_PHN_DLY',
    ramp_profile='InstantCtl')

add('C2_PHN_OUT_L', 2, 'OUTPUT_TDM', 'Phones Out L', 1, 'C2_PHN_DLY', '',
    params=output_params('DAC_09', scope='D24'))
add('C2_PHN_OUT_R', 2, 'OUTPUT_TDM', 'Phones Out R', 1, 'C2_PHN_DLY_R', '',
    params=output_params('DAC_10', scope='D24'))

# --- THE PANEL SPEAKER (Chip 2) ---
#
# The same SPI word `C2_MON_OUT` held, the same lane, the same slot -- a
# rename and a new source, so NO ADDRESS MOVES. slot_count drops 2 -> 1:
# slot 1 is `CODEC_OUT_2` = AOUT1R, whose C20 is DNP (mx26
# tools/netlist/parts.csv:67), so it reached no fitted part and is now not
# written at all.
#
# ITS ONLY INPUT IS THE HAPTIC NODE, and that is ENFORCED, not conventional:
# `dsp_validate.py::check_speaker_slot` and `dsp_codegen.py::
# _speaker_slot_guard` both refuse a graph in which any other node reaches
# the slot a `sink=SPKR` output writes. `sink=SPKR` is the single
# declaration both read.
p, a2 = c2_alloc.next(1)
add('C2_SPKR_OUT', 2, 'OUTPUT_TDM', 'Panel Speaker Out', 1, 'C2_HPT_01', '',
    spi_page=p, spi_addr=a2,
    params=output_params('CODEC_OUT_1', slot_count=1, scope='D24',
                         sink='SPKR'))

# --- USB / BT (Chip 2) ---
p, a2 = c2_alloc.next(2)
# ch_count 1: the host writes ONE word into `_buf_C2_USB_IN` over SPI and
# both mix legs read it. A stereo USB return needs a second host word and
# a second node, which is a wire question, not a graph tidy-up -- recorded
# (S143), not invented.
add('C2_USB_IN', 2, 'AUX_INPUT', 'USB Input', 1, '', 'C2_MIX_MAIN_L;C2_MIX_MAIN_R',
    spi_page=p, spi_addr=a2,
    params='level_db=-6.0;on=0',
    ramp_profile='GainFast')

p, a2 = c2_alloc.next(2)
add('C2_BT_IN', 2, 'AUX_INPUT', 'BT Input', 1, '', 'C2_MIX_MAIN_L;C2_MIX_MAIN_R',
    spi_page=p, spi_addr=a2,
    params='level_db=-6.0;on=0',
    ramp_profile='GainFast')

# --- DCA MASTERS ×8 (Chip 2, mirrored via param writes to both chips) ---
p, a2 = c2_alloc.next(16)
for d in range(1, 9):
    add(f'C2_DCA_{d:02d}', 2, 'DCA', f'DCA {d}', 1, '', '',
        spi_page=p, spi_addr=a2 + (d-1)*2,
        params='level_db=0.0;mute=0',
        ramp_profile='GainFast')

# --- OUTPUT METERS (Chip 2, read-only) ---
# Every METER declares its `taps=` explicitly: gen_dsp.py reads that
# declaration and only that (a category can no longer tell a multi-word
# channel meter from a one-word output meter), and it refuses to guess.
# `peak` is meter word +0, `rms` is word +1. The main-output meters used to
# declare `taps=L;R`, which claimed a stereo pair on four ch_count=1 mono
# outputs whose masters give one Mtr[1-1] each; the second word is the RMS,
# not an R channel. They keep their *2 stride and declare `peak;rms`: the
# RMS word stays DISPATCHED so the host can still read it, and gen_dsp.py
# emits no cell for it, because no product names one.
p_mtr, a_mtr = c2_alloc.next(40)  # aux×12 + main×8 + grp×4 + sub×1 + fx×6 = 31+
for a in range(1, NUM_AUX + 1):
    add(f'C2_MTR_AUX_{a:02d}', 2, 'METER', f'Aux {a} Meter', 1,
        f'C2_AUX_OUT_{a:02d}', '',
        spi_page=p_mtr, spi_addr=a_mtr + (a-1),
        params='taps=peak')

# Main outputs 3 and 4 are gone (S144), so their two meter word-pairs at
# a_mtr + 16 and + 18 are RESERVED with the rest of their words. The stride
# is unchanged, so MainL's and MainR's meters do not move.
for m in range(1, 5):
    if m in MAIN_OUT_RESERVE:
        continue
    add(f'C2_MTR_MAIN_{m:02d}', 2, 'METER', f'Main {m} Meter', 1,
        f'C2_MAIN_OUT_{m:02d}', '',
        spi_page=p_mtr, spi_addr=a_mtr + 12 + (m-1)*2,
        params='taps=peak;rms')

for g in range(1, NUM_GRP + 1):
    add(f'C2_MTR_GRP_{g:02d}', 2, 'METER', f'Grp {g} Meter', 1,
        f'C2_GRP_COMP_{g:02d}', '',
        spi_page=p_mtr, spi_addr=a_mtr + 20 + (g-1),
        params='taps=peak')

# THE ONE SHARED C/LF METER (S144, `Main Out3Mtr`). This is C2_MTR_SUB's
# word -- a rename and a new source, so the address does not move -- and it
# is the master block's "one C/LF XLR through one mute, meter, delay and
# DAC". It meters the OUTPUT node, after the delay, so what it reads is what
# leaves the socket.
add('C2_MTR_OUT3', 2, 'METER', 'Out3 Meter', 1, 'C2_OUT3_OUT', '',
    spi_page=p_mtr, spi_addr=a_mtr + 24,
    params='taps=peak;cell_prefix=Out3')

for f in range(1, NUM_FX + 1):
    add(f'C2_MTR_FX_{f:02d}', 2, 'METER', f'FX {f} Meter', 1,
        f'C2_FX_FDR_{f:02d}', '',
        spi_page=p_mtr, spi_addr=a_mtr + 25 + (f-1),
        params='taps=peak')

# ===========================================================================
# CHIP 2 — Superset receives + aux inputs + extra outputs (D3)
# ===========================================================================
# SPI addresses allocate after all legacy chip-2 nodes (address stability);
# recv/aux-input ROWS are spliced in right after the bus RECV block so they
# execute before the main mix reads them.

superset_c2_start = len(rows)

xfer_recv = {}
for sig, src, scope in xfer_map:
    nid = 'C2_XR_' + sig.replace('XFER_', '')
    p = fabric_params(sig)
    if scope:
        p += f';scope={scope}'
    add(nid, 2, 'INTERCHIP_RECV', f'{sig} Recv', 1, '', '', params=p)
    xfer_recv[sig] = nid

def wire_recv(sig, consumer):
    for r in rows:
        if r['id'] == xfer_recv[sig]:
            r['outputs'] = consumer

# THE TWO STEREO SUPERSET RETURNS ARE TWO INSTANCES EACH (S143).
#
# Both declared their L AND R interchip receives and the generator MAC-ed
# `inputs[0]`, so the right half of the codec aux return and of the Pi
# playback return was received over the fabric, staged into a buffer and
# read by nothing. That is S142-1's defect in two more places, and it was
# found by the arity gate rather than by reading. The follower takes no
# address: it runs the master's one coefficient (level x the on-gate), so
# `CodecAux[1-1]Level` and `Pi[1-1]Level` still mean one control.
p, a2 = c2_alloc.next(2)
add('C2_CODEC_AUX_IN', 2, 'AUX_INPUT', 'Codec Aux Input', 2,
    xfer_recv["XFER_CODEC_AUX_L"], 'C2_MIX_MAIN_L',
    spi_page=p, spi_addr=a2,
    params='level_db=-6.0;on=0',
    ramp_profile='GainFast')
add('C2_CODEC_AUX_IN_R', 2, 'AUX_INPUT', 'Codec Aux Input R', 1,
    xfer_recv["XFER_CODEC_AUX_R"], 'C2_MIX_MAIN_R',
    params='follows=C2_CODEC_AUX_IN',
    ramp_profile='GainFast')
wire_recv('XFER_CODEC_AUX_L', 'C2_CODEC_AUX_IN')
wire_recv('XFER_CODEC_AUX_R', 'C2_CODEC_AUX_IN_R')

p, a2 = c2_alloc.next(2)
add('C2_PI_IN', 2, 'AUX_INPUT', 'Pi Playback Input', 2,
    xfer_recv["XFER_PI_L"], 'C2_MIX_MAIN_L',
    spi_page=p, spi_addr=a2,
    params='level_db=-6.0;on=0',
    ramp_profile='GainFast')
add('C2_PI_IN_R', 2, 'AUX_INPUT', 'Pi Playback Input R', 1,
    xfer_recv["XFER_PI_R"], 'C2_MIX_MAIN_R',
    params='follows=C2_PI_IN',
    ramp_profile='GainFast')
wire_recv('XFER_PI_L', 'C2_PI_IN')
wire_recv('XFER_PI_R', 'C2_PI_IN_R')

for s in range(1, 9):
    sig = f'XFER_SNAKE_{s:02d}'
    nid = f'C2_SNK_IN_{s:02d}'
    p, a2 = c2_alloc.next(2)
    add(nid, 2, 'AUX_INPUT', f'Snake Return {s} Input', 1,
        xfer_recv[sig], 'C2_MIX_MAIN_L;C2_MIX_MAIN_R',
        spi_page=p, spi_addr=a2,
        params='level_db=-6.0;on=0;scope=D32',
        ramp_profile='GainFast')
    wire_recv(sig, nid)

superset_c2_end = len(rows)

# --- Extra outputs (allocated + appended last; sources run earlier) ---
#
# ONE NODE IS ONE TDM SLOT (S143). These two used to declare
# `slot_count=2` and `ch_count=2` off ONE input, and an OUTPUT_TDM node
# writes exactly one `_tx_out_slot_` word per sample: the gather copies
# `off[i] + sample*stride[i]`, one word per node per frame. So the second
# slot of each pair -- DAC_MAIN_R and CODEC_OUT_4 -- had its chip-select
# bit widened for it and was never WRITTEN at all. The right main DAC
# carried whatever the TX buffer last held, not even a copy of left.
#
# A stereo output is therefore two nodes, one slot each, reading the two
# legs. The R nodes' addresses are allocated at the very end of the chip-2
# map (below, beside the haptic node's) so this ADDS two words and MOVES
# none.
p, a2 = c2_alloc.next(1)
add('C2_MAIN_ST_OUT', 2, 'OUTPUT_TDM', 'Main Stereo Out L (DAC MAIN)', 1,
    'C2_MAIN_DLY', '',
    spi_page=p, spi_addr=a2,
    params=output_params('DAC_MAIN_L', slot_count=1))

p, a2 = c2_alloc.next(1)
add('C2_CODEC_AUX_OUT', 2, 'OUTPUT_TDM', 'Codec Aux Out L', 1,
    'C2_MAIN_DLY', '',
    spi_page=p, spi_addr=a2,
    params=output_params('CODEC_OUT_3', slot_count=1, scope='D24',
                         sink='DNP'))

# Splice superset recv/aux-input rows after the bus RECV block so process
# order is: bus recvs, superset recvs + aux inputs, aux buses, ... main mix.
superset_rows = rows[superset_c2_start:superset_c2_end]
del rows[superset_c2_start:superset_c2_end]
rows[last_bus_recv_idx:last_bus_recv_idx] = superset_rows

# ===========================================================================
# CHIP 2 — Group GEQ ×4 (added 2026-07-31 for the 48 GrpPeq matrix cells)
# ===========================================================================
# Chain becomes RECV → FDR → EQ → GEQ → GATE → COMP. SPI addresses are
# allocated after all earlier chip-2 nodes (address stability); rows are
# spliced in after each group's EQ so process order matches the chain.
for g in range(1, NUM_GRP + 1) if 'grp' in GEQ_ON else ():
    gg = f'{g:02d}'
    n_eq, n_geq, n_gate = f'C2_GRP_EQ_{gg}', f'C2_GRP_GEQ_{gg}', f'C2_GRP_GATE_{gg}'
    p, a2 = c2_alloc.next(GEQ_BANDS)
    add(n_geq, 2, 'GEQ', f'Grp {g} GEQ', 1, n_eq, n_gate,
        spi_page=p, spi_addr=a2,
        params=f'bands={GEQ_BANDS}',
        ramp_profile='EqSafe')
    geq_row = rows.pop()
    _relink_and_insert(rows, n_eq, n_gate, geq_row,
                        f'GEQ insertion {n_geq}')

# ===========================================================================
# CHIP 2 — GEQ on the remaining OUTPUTS (2026-09-03, --geq-outputs)
# ===========================================================================
# The market bar is a 31-band graphic EQ on EVERY output, and the shipping
# graph carries one on the aux buses, the groups and the main bus only. The
# outputs still without one are the two post-crossover main outputs and the
# monitor feed; each is opted in by name, and each is spliced into its chain
# the same way the group GEQ is — SPI words allocated after every earlier
# chip-2 node, so turning a class on never moves an address that was
# already allocated.
#
# THE `sub` CLASS IS GONE (S144) and so is the chain it named. `MainCtr
# Geq[1-31]` is a LANDED cell (PW ruling D6), so the Centre strip's GEQ is
# built unconditionally up with the strip — an option that can switch a
# contract cell off would leave it with no reader half the time, which is
# the shape S21-4 named. Main outputs 3 and 4 are gone with it, so
# `mainout` covers two.
#
# The monitor is listed separately from the program outputs on purpose: it
# is a listening feed off the main fader, not a program output, so "all
# outputs" does not obviously include it and its cost is 2 channels' worth.


def splice_geq(nid, label, ch_count, after, before, bands):
    """Insert a GEQ node between `after` and `before`, in chain order."""
    pg, ad = c2_alloc.next(bands)
    add(nid, 2, 'GEQ', label, ch_count, after, before,
        spi_page=pg, spi_addr=ad,
        params=f'bands={bands}',
        ramp_profile='EqSafe')
    row = rows.pop()
    _relink_and_insert(rows, after, before, row, f'GEQ splice {nid}')


if 'mainout' in GEQ_ON:
    for out_n in range(1, NUM_MAIN_OUT + 1):
        oo = f'{out_n:02d}'
        splice_geq(f'C2_MAIN_OGEQ_{oo}', f'Main Out {out_n} GEQ', 1,
                   f'C2_MAIN_OEQ_{oo}', f'C2_MAIN_OCOMP_{oo}', GEQ_BANDS)

if 'mon' in GEQ_ON:
    splice_geq('C2_MON_GEQ', 'Monitor GEQ', 2,
               'C2_MON', 'C2_MON_DLY', GEQ_BANDS)

# ===========================================================================
# CHIP 2 — MATRIX OUTPUTS ×4 (S22 gate 1)
# ===========================================================================
# Chain: RECV -> FDR (Level + Mute) -> OUT.
#
# WHAT THE DEFINITION GIVES THE STRIP, and nothing else is built: the cell
# master defines `Matrix[1-4]Level`, `Matrix[1-4]Mute` and `Matrix[1-4]Name`
# and NO other Matrix family -- no EQ, no delay, no limiter, no meter. So the
# strip is a fader and an output, and FADER_PAN is exactly that node: for a
# category that is not Chan or Aux, gen_dsp.py emits Level and Mute and
# leaves the pan word dispatched-but-uncelled. `Name` is a label the host
# stores. There is no `Matrix*Mtr` cell, so no METER node is added.
#
# WHERE THE OUTPUT GOES. The sixteen DACs are fully committed -- twelve aux
# buses and the four post-crossover main outputs between them, patched onto
# the copper by AUX_DAC / MAIN_OUT_DAC above -- so no DAC lane is free on
# either product. The NET output lines are: NET_OUT_01
# already carries C2_SUB_OUT, and NET_OUT_02..32 are unassigned and scoped
# BOTH. The four matrix outputs are patched onto NET_OUT_02..05 on the same
# footing C2_SUB_OUT sits on NET_OUT_01 -- which is to say PROVISIONALLY:
# which physical connector a matrix output appears on is a product decision
# and is recorded as a question for PW, not settled here. Changing it later
# moves one `output_params()` argument and no address.
#
# SPI addresses are allocated HERE, after every earlier chip-2 node, so this
# contract bump adds rows and moves none.
for m in range(1, NUM_MTX + 1):
    mm = f'{m:02d}'
    recv = f'C2_RECV_MTX_{mm}'
    n_fdr = f'C2_MTX_FDR_{mm}'
    n_out = f'C2_MTX_OUT_{mm}'

    add(recv, 2, 'INTERCHIP_RECV', f'Matrix {m} Recv', 1, '', n_fdr,
        params=fabric_params(f'BUS_MTX_{mm}'))

    p, a2 = c2_alloc.next(4)   # level + pan(unused) + mute + reserved
    add(n_fdr, 2, 'FADER_PAN', f'Matrix {m} Master', 1, recv, n_out,
        spi_page=p, spi_addr=a2,
        params='level_db=0.0;mute=0',
        ramp_profile='GainFast')

    p, a2 = c2_alloc.next(1)
    add(n_out, 2, 'OUTPUT_TDM', f'Matrix {m} Out', 1, n_fdr, '',
        spi_page=p, spi_addr=a2,
        params=output_params(f'NET_OUT_{m + 1:02d}'))

# ===========================================================================
# CHIP 2 — THE FX RETURNS' AUX SENDS  (S23 gate 3)
# ===========================================================================
# `Fx[1-8]AuxOn[1-12]` and `Fx[1-8]AuxSend[1-12]` -- "FX return to aux send
# on/off" and "... send level" -- are 144 cells on D32 and 144 on D24 that
# the graph built no node for. They are the last big product-visible block
# of the completeness list after the matrix.
#
# WHERE THE SUM HAPPENS, AND WHY IT IS ONE NODE PER AUX AND NOT ONE PER
# RETURN. The twelve aux buses are summed on CHIP 1 (bus-major fabric, 32
# channels a bus) and arrive on chip 2 already mixed, one word per sample,
# at `C2_RECV_AUX_nn`. The six FX returns live on chip 2. So the FX
# contribution cannot join the chip-1 accumulate at all -- it has to be
# added on chip 2, downstream of the receive and upstream of the aux
# fader, which is exactly one more summing node per aux bus:
#
#   C2_RECV_AUX_nn -> C2_MIX_AUX_nn -> C2_AUX_FDR_nn -> EQ -> GEQ -> ...
#                     ^ + C2_FX_FDR_01..06
#
# and MIX_BUS is already that node: `gen_mix_bus_fixed`'s chip-2 form is an
# exact MRF sum of `inputs` against Q4.28 coefficients converted at block
# rate, which is the same arithmetic as the main mix and the same reference
# (`fixed_ref.mix_sum`). It gains an optional SWITCHED-SEND half for this:
# the last `fx_sends` sources take their coefficient from a ramped send
# level with the on/off folded in, which is the crosspoint-coefficient
# discipline of the 08-25 mandate applied on chip 2.
#
# S22 SKETCHED A DIFFERENT SHAPE and this is a deliberate departure from
# it: it proposed the crosspoints on the return strip's own node, "category
# Fx, one instance per return, 24 SPI words", so that Fx001AuxSend001..012
# would be contiguous. Per-AUX placement costs the same 144 words, needs no
# new node class and no cross-node coefficient reads, and contiguity buys
# nothing here -- the host addresses one cell at a time and only
# `add_dispatch_block` (coefficient SETS) needs a run. Said out loud
# because the sketch is in the S22 write-up and the tree now disagrees
# with it.
#
# THE PICKOFF IS POST-FADER AND IT IS NOT SELECTABLE. The cell master
# defines `Chan*AuxPick` and `Chan*FxPick` and NO `Fx*AuxPick`, so there is
# no cell to dispatch a choice to. Post-fader is the reading that matches
# the channel sends' own default and the one the graph can take for free
# (`_blk_C2_FX_FDR_nn` is the return strip's published block); PRE-fader is
# equally available at zero cost (`_blk_C2_FX_ENG_nn`), so which one the
# product means is a QUESTION FOR PW and not a thing to decide here. It is
# in dsp-definitions-needed.md.
#
# SPI addresses are allocated after every earlier chip-2 node -- including
# the matrix strips -- so this bump ADDS rows and moves none.
mix_aux_ids = {}
for a in range(1, NUM_AUX + 1):
    aa = f'{a:02d}'
    nid = f'C2_MIX_AUX_{aa}'
    mix_aux_ids[a] = nid
    p, a2 = c2_alloc.next(2 * NUM_FX)   # AuxOn[1-6] then AuxSend[1-6]
    add(nid, 2, 'MIX_BUS', f'Aux {a} FX Sum', 1,
        f'{recv_ids[f"aux_{a}"]};{fx_fdr_ids}', f'C2_AUX_FDR_{aa}',
        spi_page=p, spi_addr=a2,
        params=f'bus_id=aux{aa};source_count={1 + NUM_FX}'
               f';fx_sends={NUM_FX};aux={a}',
        ramp_profile='GainFast')

# Splice the node into the aux chain: the receive now feeds the sum and the
# fader now reads it. Done by REWRITING the two rows rather than by adding a
# parallel path, so there is exactly one route from the aux bus to the aux
# fader and `dsp_validate` can still see it.
for a in range(1, NUM_AUX + 1):
    aa = f'{a:02d}'
    for r in rows:
        if r['id'] == recv_ids[f'aux_{a}']:
            assert r['outputs'] == f'C2_AUX_FDR_{aa}', r['outputs']
            r['outputs'] = mix_aux_ids[a]
        if r['id'] == f'C2_AUX_FDR_{aa}':
            assert r['inputs'] == recv_ids[f'aux_{a}'], r['inputs']
            r['inputs'] = mix_aux_ids[a]

# ===========================================================================
# THE MAIN OUTPUT STRIPS' OWN LEVEL AND MUTE (S24, completeness leg 2)
# ===========================================================================
#
# `Main{L,R,Ctr,Sub}[1-1]Level[1-1]` and `...Mute[1-1]` are cells the master
# has always defined and the graph has never had a word for. The reason is
# in dsp-unmapped.csv in as many words: the post-crossover output chain is
# EQ -> COMP -> LIM -> OUTPUT_TDM and there is no FADER_PAN in it, so the
# strip's own level and mute reached no address (open question Q1).
#
# WHAT IS BUILT, AND WHERE. Not a fader node -- the OUTPUT_TDM node itself.
# It is already a per-block copy from the limiter's block onto the TX slot
# array, so a level is one multiply on a word it already loads and a mute
# is that level folded to zero. A FADER_PAN would add a node, a block
# buffer, a pan the master does not define and a place in the chain for the
# ordering repair to move; this adds an arithmetic step to a node that is
# already there. `Delay` is NOT built here and is not guessed at: it needs a
# delay LINE, which is L2 and not cycles, and committing that on a chip
# whose worst-use row is already over budget is PW's call -- see the S24
# write-up.
#
# THE FOLD AND THE BYPASS ARE S23'S, DELIBERATELY. Level and mute are
# folded into ONE Q4.28 coefficient at block rate with the mute bit
# multiplied in, and where that coefficient is exactly 2^28 the node takes
# its old copy path unchanged -- so the SHIPPING DEFAULT (unity, unmuted)
# emits and executes exactly what it did before this feature existed.
#
# SPI addresses are allocated HERE, after every other chip-2 allocation
# including the aux FX sums, and written back onto the four output rows.
# Two words per output, Level then Mute, in the order gen_dsp.py::
# expand_output_tdm emits them. The bump ADDS rows and moves NONE.
#
# Outputs 3 and 4 are gone (S144) and their two word-pairs are RESERVED
# here with the rest of their words.
_mo_rows = {r['id']: r for r in rows}
for out_n in range(1, 5):
    p, a2 = c2_alloc.next(2)
    if out_n in MAIN_OUT_RESERVE:
        continue
    _mo_rows[f'C2_MAIN_OUT_{out_n:02d}']['params'] += f';mo_page={p};mo_addr={a2}'

# ===========================================================================
# CHIP 2 — THE PANEL HAPTIC NODE (S122)
# ===========================================================================
#
# PW ruling 2026-09-26: "the spkr feed is for screen button haptics only,
# and should be completely separate from all mixer signal paths." This is
# the source that replaces the monitor bus on `CODEC_OUT_1`, and it is the
# ONLY node in the graph that may reach that slot.
#
# WHAT IT IS. A one-shot player of stored clicks plus a steady test tone,
# and silence otherwise — it writes DIGITAL ZERO on every block in which
# nothing was asked for, and the zero-fill is latched, so an idle block
# costs five instructions and no memory traffic (the DSP4_AUXIN_BYPASS
# idiom). A press writes `trig`; the kernel consumes the write, plays the
# selected burst to the end and clears `busy`. Nothing in the mixer can
# reach it: the node has NO inputs.
#
# THE STORED SET IS PW'S OWN AUDITION (2026-09-25, "ticks are working"),
# modelled rather than approximated. The six candidates are WAV files on the
# bench unit (`/home/app/*.wav`) and the tonal ones are DECAYING SINES, not
# gated bursts: a log-linear fit to each file's own per-half-cycle peaks
# gives `A . exp(-n/tau) . sin(2.pi.f.n/fs)` at a peak of 0.94, and the
# model reproduces each file to within 0.0054 of full scale. So what is
# stored is 2500 Hz / tau 2.5 ms (`2_click_2k5`, the one this dispatch
# names), 3000 Hz / 1.8 ms (`6_release_3k`, the one the file names) and
# 1500 Hz / 3.0 ms (`1_click_1k5`) as a spare. WHICH IS PRESS AND WHICH IS
# RELEASE IS PW'S RULING -- proposals/CONTRACT-PROPOSAL-S122.md proposes
# 1 = press, 2 = release, 3 = spare and does not land it.
#
# THE TEST TONE is 1 kHz — exactly 48 samples at 48 kHz, so one stored
# period loops seamlessly for nothing. It is 1 kHz and not 2.5 kHz because
# AL1's whole calibration (level law, bandpass-THD ceiling, the S115 MEMS
# measurement) was taken at 1 kHz through this loop; changing the frequency
# would have thrown away the only acoustic reference this unit has.
#
# ADDRESSES ARE ALLOCATED HERE, after every other chip-2 allocation
# including the main outputs' Level/Mute, so this ADDS eight words and
# MOVES none.
#
# NO CELLS ARE EMITTED. The haptic cell family is PROPOSED, not landed
# (cell names are forever — Bible ch 7 — and PW rules them), so the eight
# words are dispatched-but-uncelled: reachable by address, named by no
# contract cell, exactly as `_mon_source_C2_MON` has always been.
p, a2 = c2_alloc.next(8)
add('C2_HPT_01', 2, 'HAPTIC', 'Panel Haptic', 1, '', 'C2_SPKR_OUT',
    spi_page=p, spi_addr=a2,
    params='trig=0;sample=1;level=1.0;test_on=0;test_level=0.0;'
           'click_hz=2500:3000:1500;click_tau_ms=2.5:1.8:3.0;'
           'click_peak=0.94;click_end_db=-60.0;tone_hz=1000.0;scope=D24',
    ramp_profile='InstantCtl')

# The row RUNS just before the output it feeds; only its ADDRESS is last.
_hpt_row = rows.pop()
_at = next(i for i, r in enumerate(rows) if r['id'] == 'C2_SPKR_OUT')
rows[_at:_at] = [_hpt_row]


# ===========================================================================
# THE RIGHT-HAND STEREO OUTPUT NODES (S143)
# ===========================================================================
#
# DAC_MAIN_R and CODEC_OUT_4 -- the two TDM slots that were enabled in the
# chip-select mask and never written (see the note on `C2_MAIN_ST_OUT`).
# They are ordinary OUTPUT_TDM nodes reading the right main delay, and
# their addresses are allocated HERE, after the haptic node's, so they ADD
# two words and MOVE none. Neither carries `mo_page`, so neither reaches a
# master cell -- the same as the L nodes they pair with.
for _sid, _sig, _lbl, _scope in (
        ('C2_MAIN_ST_OUT_R', 'DAC_MAIN_R', 'Main Stereo Out R (DAC MAIN)', None),
        ('C2_CODEC_AUX_OUT_R', 'CODEC_OUT_4', 'Codec Aux Out R', 'D24')):
    p, a2 = c2_alloc.next(1)
    _kw = {'scope': _scope, 'sink': 'DNP'} if _scope else {}
    add(_sid, 2, 'OUTPUT_TDM', _lbl, 1, 'C2_MAIN_DLY_R', '',
        spi_page=p, spi_addr=a2,
        params=output_params(_sig, slot_count=1, **_kw))
    # RUN beside their left-hand partners, which is where the chain wants
    # them; only the ADDRESS is last.
    _row = rows.pop()
    _at = next(i for i, r in enumerate(rows)
               if r['id'] == _sid[:-2])
    rows[_at + 1:_at + 1] = [_row]

# ===========================================================================
# THE GROUP -> AUX CROSSPOINTS (S143, item 3's group half; PW ruling D10)
# ===========================================================================
#
# `Grp[1-4]AuxSend[1-12]` and `Grp[1-4]AuxOn[1-12]`: every group feeds every
# aux, at a level, through a switch. Forty-eight crosspoints on the superset
# (thirty-two of them reach a D24 cell, which is where the dispatch's count
# comes from).
#
# IT IS NOT A NEW FABRIC. `C2_MIX_AUX_j` has had a SWITCHED-SEND half since
# S23 gate 3 -- per-source on/off plus a ramped level folded into ONE Q4.28
# coefficient at block rate -- and it was proved on the part there (the aux
# sum reproduced `_buf_C2_RECV_AUX_01` in 32 of 32 words with every send
# off, and both negative controls read exactly zero). This adds four more
# sources of the same kind to the same node.
#
# THE ADDRESSES ARE A SECOND BLOCK, allocated HERE -- after the main
# outputs' Level/Mute and after the haptic node, i.e. after every other
# chip-2 allocation -- so the crosspoints ADD words and MOVE NONE. Same
# mechanism, and the same reason, as ROUTING's `mtx_page`/`mtx_addr` and
# OUTPUT_TDM's `mo_page`/`mo_addr`: growing a node's first block would move
# every chip-2 address above it.
#
# `Grp[1-4]AuxPick[1-12]` IS NOT BUILT AND IS NOT DISPATCHED. It selects
# which tap of the group strip the send is taken from (PreEQ / PostEQ /
# PreFdr / PostFdr), which is a pointer select over blocks that exist but
# needs the taps published and a per-crosspoint source pointer -- a
# different mechanism from a coefficient, and cheap only once it is the
# same one the channel sends use (`Chan*AuxPick`). Giving it an address it
# had no reader for is the shape this repo calls a defect (S21-4), so it
# stays unmapped with its reason, and the send is taken from the group's
# OUTPUT (`C2_GRP_COMP_g`), which is what PostFdr means here.
_grp_srcs = [f'C2_GRP_COMP_{g:02d}' for g in range(1, NUM_GRP + 1)]
_by_id_xp = {r['id']: r for r in rows}
for a in range(1, NUM_AUX + 1):
    _r = _by_id_xp[mix_aux_ids[a]]
    _r['inputs'] += ';' + ';'.join(_grp_srcs)
    p, a2 = c2_alloc.next(2 * NUM_GRP)
    _r['params'] = _r['params'].replace(
        f';source_count={1 + NUM_FX}',
        f';source_count={1 + NUM_FX + NUM_GRP}')
    _r['params'] += (f';xp_page={p};xp_addr={a2}'
                     f';xp_map=Grp:{",".join(str(g) for g in range(1, NUM_GRP + 1))}')

# ===========================================================================
# S144's ADDRESSES, LAST OF ALL
# ===========================================================================
# Everything above this line was allocated before S144 and keeps the address
# it had. The Centre GEQ, the Woof strip and the two source selects are new
# nodes that run in the middle of chains, and this is where they take their
# words -- after the group crosspoints, which were the last allocation the
# tree had landed.
resolve_late_c2()

# `Main Out3Mute` is the C/LF output node's own mute, in the same second
# block every OUTPUT_TDM strip mute uses (`mo_page`/`mo_addr`, S24). Two
# words, Level then Mute, because that is the pair expand_output_tdm emits;
# there is no `Main Out3Level` cell -- the level is `MainCtr Level` or
# `MainSub Level` on whichever strip Out3Mode selects -- so the first word
# is dispatched and uncelled, as the main outputs' pan word is.
_out3_out_row = next(r for r in rows if r['id'] == 'C2_OUT3_OUT')
p, a2 = c2_alloc.next(2)
_out3_out_row['params'] += f';mo_page={p};mo_addr={a2}'

# --- Splice the FX chain and the aux FX sums ahead of the aux chain -----
#
# The FX engines and returns are ADDED late (their SPI addresses are
# allocated in the order this file calls add(), and moving an add() moves
# an address), but they now have to RUN early: C2_MIX_AUX_nn reads
# _blk_C2_FX_FDR_ff, so every return has to have published its block
# before the first aux sum. Rows are reordered; addresses are not.
#
# repair_process_order() in dsp_codegen.py would fix the order on its own,
# and that is exactly why this splice exists: it fixes it by moving each
# producer to just before its earliest consumer, which drops
# C2_MIX_AUX_02..12 INTO the middle of the aux chain -- and the chip-2 pair
# families require each family's nodes to be a CONTIGUOUS run of the chain
# (c2_pair_groups raises otherwise, which is how this was found: "pair
# family AUX: its 84 nodes are not a contiguous run of the chain"). Putting
# the whole FX chain and all twelve sums in front of the aux chain leaves
# the AUX family's 84 nodes untouched and needs no repair move at all.
_pre_aux = [f'C2_FX_ENG_{f:02d}' for f in range(1, NUM_FX + 1)] \
    + [f'C2_FX_FDR_{f:02d}' for f in range(1, NUM_FX + 1)] \
    + [mix_aux_ids[a] for a in range(1, NUM_AUX + 1)]
_pre_aux_set = set(_pre_aux)
_moved = sorted((r for r in rows if r['id'] in _pre_aux_set),
                key=lambda r: _pre_aux.index(r['id']))
assert len(_moved) == len(_pre_aux), 'a spliced row is missing from rows'
rows[:] = [r for r in rows if r['id'] not in _pre_aux_set]
_at = next(i for i, r in enumerate(rows) if r['id'] == 'C2_AUX_FDR_01')
rows[_at:_at] = _moved

# THE GROUP CHAIN RUNS BEFORE THE AUX SUMS NOW, and the whole chain moves
# as one. Every aux sum reads `C2_GRP_COMP_g` (the group -> aux
# crosspoints above), and `repair_process_order` would otherwise move each
# of the four COMPs on its own to just before `C2_MIX_AUX_01` -- which
# splits the GRP pair family (FDR, EQ, GEQ, GATE, COMP), and
# `c2_pair_groups` refuses a family whose nodes are not a contiguous run of
# the chain. Rows are reordered; addresses are not. Same splice, same
# reason, as the FX one immediately above -- and it has to come AFTER it,
# because that one moves the aux sums themselves.
_grp_set = {r['id'] for r in rows
            if r['id'].startswith('C2_GRP_')
            or r['id'].startswith('C2_RECV_GRP_')}
_moved_grp = [r for r in rows if r['id'] in _grp_set]
rows[:] = [r for r in rows if r['id'] not in _grp_set]
_at = next(i for i, r in enumerate(rows) if r['id'] == mix_aux_ids[1])
rows[_at:_at] = _moved_grp

# ===========================================================================
# THE SPEAKER IS DECLARED, AND IT IS THE HAPTIC NODE'S (S122)
# ===========================================================================
# PW ruling 2026-09-26. `dsp_validate.py` and `dsp_codegen.py` both refuse a
# graph in which anything but a HAPTIC node reaches a `sink=SPKR` output --
# but neither can refuse a graph with NO `sink=SPKR` output at all, because
# both are run on fragments and on graphs that are not a D24's. This is the
# one place that knows it is building the shipping graph, so this is where
# "the speaker did not quietly stop being declared" is checked.
_spk = [r for r in rows if r['type'] == 'OUTPUT_TDM'
        and ';sink=SPKR' in (';' + r['params'])]
if len(_spk) != 1:
    raise SystemExit(
        'ERROR: %d OUTPUT_TDM nodes declare sink=SPKR and the graph must have '
        'exactly one. The D24 panel speaker is CODEC_OUT_1 (AK4619 AOUT1L) and '
        'the declaration is what both speaker-slot guards read.' % len(_spk))
_spk_src = [x for x in _spk[0]['inputs'].split(';') if x]
_by_id = {r['id']: r for r in rows}
_bad = [x for x in _spk_src if _by_id.get(x, {}).get('type') != 'HAPTIC']
if not _spk_src or _bad:
    raise SystemExit(
        'ERROR: %s declares sink=SPKR and is fed by %s. PW ruling 2026-09-26: '
        'the panel speaker carries haptics only and is separate from every '
        'mixer signal path.'
        % (_spk[0]['id'], ', '.join(_bad) or 'nothing'))

# ===========================================================================
# Write CSV
# ===========================================================================
csv_path = args.out

with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=HEADER)
    writer.writeheader()
    writer.writerows(rows)

c1_count = sum(1 for r in rows if r['chip'] == '1')
c2_count = sum(1 for r in rows if r['chip'] == '2')
n_send = sum(1 for r in rows if r['type'] == 'INTERCHIP_SEND')
print(f"Generated {csv_path}")
print(f"  sport map: {args.sport_map}")
print(f"    source_hash sha256:{SPORT_MAP['source_hash'][:16]}…")
print(f"  Total nodes: {len(rows)}")
print(f"  Chip 1: {c1_count}")
print(f"  Chip 2: {c2_count}")
print(f"  Mix-fabric slots in use: {n_send} of {SPORT_MAP['mix_fabric']['total_slots']}")
print(f"  Chip 1 SPI words allocated: page {c1_alloc.page}, addr {c1_alloc.addr}")
print(f"  Chip 2 SPI words allocated: page {c2_alloc.page}, addr {c2_alloc.addr}")
