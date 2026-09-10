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
                         'aux,grp,main,sub,mainout,mon. Default '
                         '"aux,grp,main" is the shipping graph.')
args = parser.parse_args()

GEQ_BANDS = args.geq_bands
if not 1 <= GEQ_BANDS <= 64:
    raise ValueError(f'--geq-bands {GEQ_BANDS} out of range 1..64')
GEQ_CLASSES = ('aux', 'grp', 'main', 'sub', 'mainout', 'mon')
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


def output_params(signal, slot_count=1, scope=None):
    e = sig_tx2(signal)
    p = (f'sport_id={e["sport_id"]};slot_start={e["slot"]};'
         f'slot_count={slot_count};sport_slots={e["sport_slots"]};'
         f'signal={signal}')
    if scope:
        p += f';scope={scope}'
    return p


def fabric_params(signal):
    """Inter-chip fabric slot: chip1 TX line n == chip2 RX line n."""
    e = SIG[('1', 'tx', signal)]
    g = MIX_GLOBAL[signal]
    return (f'sport_id={e["sport_id"]};slot={e["slot"]};global_slot={g};'
            f'sport_slots=16;signal={signal}')


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

superset_c1 = [
    ('C1_XIN_CODEC_01', 'CODEC_RET_1', 'Codec ADC 1 (TB XLR)', None),
    ('C1_XIN_CODEC_03', 'CODEC_RET_3', 'Codec ADC 3 (Aux In L)', None),
    ('C1_XIN_CODEC_04', 'CODEC_RET_4', 'Codec ADC 4 (Aux In R)', None),
    ('C1_XIN_PI_L', 'PI_PCM_L', 'Pi PCM L', None),
    ('C1_XIN_PI_R', 'PI_PCM_R', 'Pi PCM R', None),
    ('C1_XIN_MEMS', 'MEMS_TB', 'MEMS Talkback Mic', None),
] + [(f'C1_XIN_SNK_{s:02d}', f'SNAKE_RET_{s:02d}', f'Snake Return {s}', 'D32')
     for s in range(1, 9)]

# fabric pass-throughs: XFER signal -> source input node
xfer_map = [
    ('XFER_CODEC_AUX_L', 'C1_XIN_CODEC_03', None),
    ('XFER_CODEC_AUX_R', 'C1_XIN_CODEC_04', None),
    ('XFER_PI_L', 'C1_XIN_PI_L', None),
    ('XFER_PI_R', 'C1_XIN_PI_R', None),
] + [(f'XFER_SNAKE_{s:02d}', f'C1_XIN_SNK_{s:02d}', 'D32') for s in range(1, 9)]

xin_consumer = {src: f'C1_XS_{sig}' for sig, src, _ in xfer_map}
xin_consumer['C1_XIN_CODEC_01'] = 'C1_TALK_01'
xin_consumer['C1_XIN_MEMS'] = 'C1_TALK_02'

for nid, sig, label, scope in superset_c1:
    ip = input_params(sig)
    if scope:
        ip += f';scope={scope}'
    add(nid, 1, 'INPUT_TDM', label, 1, '', xin_consumer[nid], params=ip)

# --- TALKBACK ×2 ---
# Sources wired 2026-07-31 per hardware map: TALK_01 = codec ADC ch1
# (talkback XLR), TALK_02 = surface MEMS mic.
p, a = c1_alloc.next(8)
talk_sources = {1: 'C1_XIN_CODEC_01', 2: 'C1_XIN_MEMS'}
for t in [1, 2]:
    add(f'C1_TALK_{t:02d}', 1, 'TALKBACK', f'Talkback {t}', 1,
        talk_sources[t], '',
        spi_page=p, spi_addr=a + (t-1)*4,
        params=f'gain_db=0.0;hpf_on=1;route=aux1',
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
# Output patch: Aux 1-12 → DAC_01..DAC_12 (B_O0 + B_O1 low half)
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
        params=output_params(f'DAC_{a:02d}'))

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

# --- SUB BUS (Chip 2) ---
# Chain: RECV → FDR → EQ → COMP → LIM → DLY → OUT
# Output patch: Sub → NET_OUT_01 (no dedicated analog sub DAC on DSP4;
# provisional pending product-config output patch layer)
recv_sub = recv_ids['sub']
for r in rows:
    if r['id'] == recv_sub:
        r['outputs'] = 'C2_SUB_FDR'

p, a2 = c2_alloc.next(4)
add('C2_SUB_FDR', 2, 'FADER_PAN', 'Sub Fader', 1, recv_sub, 'C2_SUB_EQ',
    spi_page=p, spi_addr=a2,
    params='level_db=0.0;mute=0;host_cells=Dca,DcaOn',
    ramp_profile='GainFast')

p, a2 = c2_alloc.next(24)
add('C2_SUB_EQ', 2, 'EQ_BIQUAD', 'Sub EQ', 1, 'C2_SUB_FDR', 'C2_SUB_COMP',
    spi_page=p, spi_addr=a2,
    params='bands=4;coeffs=default',
    ramp_profile='EqSafe')

p, a2 = c2_alloc.next(16)
add('C2_SUB_COMP', 2, 'COMPRESSOR', 'Sub Comp', 1, 'C2_SUB_EQ', 'C2_SUB_LIM',
    spi_page=p, spi_addr=a2,
    params='threshold_db=-20.0;ratio=4.0;attack_ms=5.0;release_ms=100.0;knee_db=6.0;makeup_db=0.0;type=VCA',
    ramp_profile='DynSafe')

p, a2 = c2_alloc.next(4)
add('C2_SUB_LIM', 2, 'LIMITER', 'Sub Lim', 1, 'C2_SUB_COMP', 'C2_SUB_DLY',
    spi_page=p, spi_addr=a2,
    params='threshold_db=-0.5;attack_ms=0.1;release_ms=50.0',
    ramp_profile='DynSafe')

p, a2 = c2_alloc.next(2)
add('C2_SUB_DLY', 2, 'DELAY', 'Sub Delay', 1, 'C2_SUB_LIM', 'C2_SUB_OUT',
    spi_page=p, spi_addr=a2,
    params='delay_ms=0.0;max_ms=250.0',
    ramp_profile='InstantCtl')

p, a2 = c2_alloc.next(1)
add('C2_SUB_OUT', 2, 'OUTPUT_TDM', 'Sub Out', 1, 'C2_SUB_DLY', '',
    spi_page=p, spi_addr=a2,
    params=output_params('NET_OUT_01'))

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
aux_input_ids = ['C2_USB_IN', 'C2_BT_IN', 'C2_CODEC_AUX_IN', 'C2_PI_IN'] + \
    [f'C2_SNK_IN_{s:02d}' for s in range(1, 9)]
grp_comp_ids = ';'.join(f'C2_GRP_COMP_{g:02d}' for g in range(1, NUM_GRP + 1))
aux_in_str = ';'.join(aux_input_ids)
fx_fdr_ids = ';'.join(f'C2_FX_FDR_{f:02d}' for f in range(1, NUM_FX + 1))
main_l_sources = f'{recv_ids["main_l"]};{grp_comp_ids};{aux_in_str};{fx_fdr_ids}'
main_r_sources = f'{recv_ids["main_r"]};{grp_comp_ids};{aux_in_str};{fx_fdr_ids}'

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
add('C2_MIX_MAIN_R', 2, 'MIX_BUS', 'Main Mix R', 1, main_r_sources, 'C2_MAIN_FDR',
    spi_page=p, spi_addr=a2,
    params='bus_id=1')

p, a2 = c2_alloc.next(4)
add('C2_MAIN_FDR', 2, 'FADER_PAN', 'Main Fader', 2, 'C2_MIX_MAIN_L;C2_MIX_MAIN_R',
    'C2_MAIN_GEQ' if 'main' in GEQ_ON else 'C2_MAIN_COMP',
    spi_page=p, spi_addr=a2,
    params='level_db=0.0;mute=0;host_cells=Dca,DcaOn',
    ramp_profile='GainFast')

if 'main' in GEQ_ON:
    p, a2 = c2_alloc.next(GEQ_BANDS)
    add('C2_MAIN_GEQ', 2, 'GEQ', 'Main GEQ', 2, 'C2_MAIN_FDR', 'C2_MAIN_COMP',
        spi_page=p, spi_addr=a2,
        params=f'bands={GEQ_BANDS}',
        ramp_profile='EqSafe')

p, a2 = c2_alloc.next(16)
add('C2_MAIN_COMP', 2, 'COMPRESSOR', 'Main Comp', 2,
    'C2_MAIN_GEQ' if 'main' in GEQ_ON else 'C2_MAIN_FDR', 'C2_MAIN_LIM',
    spi_page=p, spi_addr=a2,
    params='threshold_db=-20.0;ratio=4.0;attack_ms=5.0;release_ms=100.0;knee_db=6.0;makeup_db=0.0;parallel=100;type=VCA',
    ramp_profile='DynSafe')

p, a2 = c2_alloc.next(4)
add('C2_MAIN_LIM', 2, 'LIMITER', 'Main Lim', 2, 'C2_MAIN_COMP', 'C2_MAIN_DLY',
    spi_page=p, spi_addr=a2,
    params='threshold_db=-0.5;attack_ms=0.1;release_ms=50.0',
    ramp_profile='DynSafe')

p, a2 = c2_alloc.next(2)
add('C2_MAIN_DLY', 2, 'DELAY', 'Main Delay', 2, 'C2_MAIN_LIM',
    'C2_MAIN_XOVER;C2_MAIN_ST_OUT;C2_CODEC_AUX_OUT',
    spi_page=p, spi_addr=a2,
    params='delay_ms=0.0;max_ms=250.0',
    ramp_profile='InstantCtl')

p, a2 = c2_alloc.next(4)
add('C2_MAIN_XOVER', 2, 'CROSSOVER', 'Main Xover', 2,
    'C2_MAIN_DLY', 'C2_MAIN_OUT_01;C2_MAIN_OUT_02;C2_MAIN_OUT_03;C2_MAIN_OUT_04',
    spi_page=p, spi_addr=a2,
    params='freq=120.0;slope=24',
    ramp_profile='EqSafe')

# --- Per-output processing (Main ×4) ---
# Output patch: Main xover outs 1-4 → DAC_13..DAC_16 (B_O1 high half)
for out_n in range(1, 5):
    oo = f'{out_n:02d}'
    n_eq   = f'C2_MAIN_OEQ_{oo}'
    n_comp = f'C2_MAIN_OCOMP_{oo}'
    n_lim  = f'C2_MAIN_OLIM_{oo}'
    n_out  = f'C2_MAIN_OUT_{oo}'

    p, a2 = c2_alloc.next(24)
    add(n_eq, 2, 'EQ_BIQUAD', f'Main Out {out_n} EQ', 1, 'C2_MAIN_XOVER', n_comp,
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
        params=output_params(f'DAC_{12 + out_n:02d}'))

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
    add(n_eng, 2, 'FX_ENGINE', f'FX {f} Engine', 2, recv, n_fdr,
        spi_page=p, spi_addr=a2,
        params='type=Reverb;room_size=0.7;damping=0.5;decay=2.0;predelay_ms=20.0;delay_ms=300.0;feedback=50;balance=50;eq_lo=0;eq_mid=0;eq_hi=0;hpf=80;mod_rate=1.0;mod_level=50;mix=30;duck_on=0;duck_sens=-10',
        ramp_profile='GainSafe')

    p, a2 = c2_alloc.next(4)
    add(n_fdr, 2, 'FADER_PAN', f'FX {f} Return', 1, n_eng, 'C2_MIX_MAIN_L;C2_MIX_MAIN_R',
        spi_page=p, spi_addr=a2,
        params='level_db=-6.0;mute=0;host_cells=Dca,DcaOn',
        ramp_profile='GainFast')

# --- MONITOR / PHONES (Chip 2) ---
# Output patch: monitor → codec DAC ch1/2 (D24 talkback SPKR path;
# B_O2 is D32 SNAKE — D32 monitor/snake output patch TBD with the
# product-config output layer)
p, a2 = c2_alloc.next(6)
add('C2_MON', 2, 'MONITOR', 'Monitor', 2, 'C2_MAIN_FDR', 'C2_MON_DLY',
    spi_page=p, spi_addr=a2,
    params='level_l_db=0.0;level_r_db=0.0;source=main',
    ramp_profile='GainFast')

p, a2 = c2_alloc.next(2)
add('C2_MON_DLY', 2, 'DELAY', 'Monitor Delay', 2, 'C2_MON', 'C2_MON_OUT',
    spi_page=p, spi_addr=a2,
    params='delay_ms=0.0;max_ms=250.0',
    ramp_profile='InstantCtl')

p, a2 = c2_alloc.next(1)
add('C2_MON_OUT', 2, 'OUTPUT_TDM', 'Monitor Out', 2, 'C2_MON_DLY', '',
    spi_page=p, spi_addr=a2,
    params=output_params('CODEC_OUT_1', slot_count=2, scope='D24'))

# --- USB / BT (Chip 2) ---
p, a2 = c2_alloc.next(2)
add('C2_USB_IN', 2, 'AUX_INPUT', 'USB Input', 2, '', 'C2_MIX_MAIN_L;C2_MIX_MAIN_R',
    spi_page=p, spi_addr=a2,
    params='level_db=-6.0;on=0',
    ramp_profile='GainFast')

p, a2 = c2_alloc.next(2)
add('C2_BT_IN', 2, 'AUX_INPUT', 'BT Input', 2, '', 'C2_MIX_MAIN_L;C2_MIX_MAIN_R',
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

for m in range(1, 5):
    add(f'C2_MTR_MAIN_{m:02d}', 2, 'METER', f'Main {m} Meter', 1,
        f'C2_MAIN_OUT_{m:02d}', '',
        spi_page=p_mtr, spi_addr=a_mtr + 12 + (m-1)*2,
        params='taps=peak;rms')

for g in range(1, NUM_GRP + 1):
    add(f'C2_MTR_GRP_{g:02d}', 2, 'METER', f'Grp {g} Meter', 1,
        f'C2_GRP_COMP_{g:02d}', '',
        spi_page=p_mtr, spi_addr=a_mtr + 20 + (g-1),
        params='taps=peak')

add('C2_MTR_SUB', 2, 'METER', 'Sub Meter', 1, 'C2_SUB_OUT', '',
    spi_page=p_mtr, spi_addr=a_mtr + 24,
    params='taps=peak')

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

p, a2 = c2_alloc.next(2)
add('C2_CODEC_AUX_IN', 2, 'AUX_INPUT', 'Codec Aux Input', 2,
    f'{xfer_recv["XFER_CODEC_AUX_L"]};{xfer_recv["XFER_CODEC_AUX_R"]}',
    'C2_MIX_MAIN_L;C2_MIX_MAIN_R',
    spi_page=p, spi_addr=a2,
    params='level_db=-6.0;on=0',
    ramp_profile='GainFast')
wire_recv('XFER_CODEC_AUX_L', 'C2_CODEC_AUX_IN')
wire_recv('XFER_CODEC_AUX_R', 'C2_CODEC_AUX_IN')

p, a2 = c2_alloc.next(2)
add('C2_PI_IN', 2, 'AUX_INPUT', 'Pi Playback Input', 2,
    f'{xfer_recv["XFER_PI_L"]};{xfer_recv["XFER_PI_R"]}',
    'C2_MIX_MAIN_L;C2_MIX_MAIN_R',
    spi_page=p, spi_addr=a2,
    params='level_db=-6.0;on=0',
    ramp_profile='GainFast')
wire_recv('XFER_PI_L', 'C2_PI_IN')
wire_recv('XFER_PI_R', 'C2_PI_IN')

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
p, a2 = c2_alloc.next(1)
add('C2_MAIN_ST_OUT', 2, 'OUTPUT_TDM', 'Main Stereo Out (DAC MAIN)', 2,
    'C2_MAIN_DLY', '',
    spi_page=p, spi_addr=a2,
    params=output_params('DAC_MAIN_L', slot_count=2))

p, a2 = c2_alloc.next(1)
add('C2_CODEC_AUX_OUT', 2, 'OUTPUT_TDM', 'Codec Aux Out', 2,
    'C2_MAIN_DLY', '',
    spi_page=p, spi_addr=a2,
    params=output_params('CODEC_OUT_3', slot_count=2, scope='D24'))

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
# outputs still without one are the sub, the four post-crossover main
# outputs and the monitor feed; each is opted in by name, and each is
# spliced into its chain the same way the group GEQ is — SPI words
# allocated after every earlier chip-2 node, so turning a class on never
# moves an address that was already allocated.
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


if 'sub' in GEQ_ON:
    splice_geq('C2_SUB_GEQ', 'Sub GEQ', 1,
               'C2_SUB_EQ', 'C2_SUB_COMP', GEQ_BANDS)

if 'mainout' in GEQ_ON:
    for out_n in range(1, 5):
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
# WHERE THE OUTPUT GOES. The sixteen DACs are fully committed -- aux 1-12 on
# DAC_01..12 and the four post-crossover main outputs on DAC_13..16 -- so no
# DAC lane is free on either product. The NET output lines are: NET_OUT_01
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
_mo_rows = {r['id']: r for r in rows}
for out_n in range(1, 5):
    p, a2 = c2_alloc.next(2)
    _mo_rows[f'C2_MAIN_OUT_{out_n:02d}']['params'] += f';mo_page={p};mo_addr={a2}'

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
