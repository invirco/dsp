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
args = parser.parse_args()

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
    assert g == 16 * e['sport_id'] + e['slot'], signal
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

# --- Bus pre-sum IDs (Chip 1 accumulates, sends to Chip 2) ---
bus_main_l = 'C1_BUS_MAIN_L'
bus_main_r = 'C1_BUS_MAIN_R'
bus_sub    = 'C1_BUS_SUB'
bus_grp    = [f'C1_BUS_GRP_{g:02d}' for g in range(1, NUM_GRP+1)]
bus_aux    = [f'C1_BUS_AUX_{a:02d}' for a in range(1, NUM_AUX+1)]
bus_fx     = [f'C1_BUS_FX_{x:02d}'  for x in range(1, NUM_FX+1)]

# All bus IDs that a channel routing node feeds
all_bus_ids = [bus_main_l, bus_main_r, bus_sub] + bus_grp + bus_aux + bus_fx

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
    p, a = c1_alloc.next(20)  # on + thr + rat + att + rel + make + knee + par + type + key + det_src + eq_pos + filter params + state
    add(n_comp, 1, 'COMPRESSOR', f'Ch {ch} Comp', 1, n_gate, n_tube,
        spi_page=p, spi_addr=a,
        params='threshold_db=-20.0;ratio=4.0;attack_ms=5.0;release_ms=100.0;knee_db=6.0;makeup_db=0.0;parallel=0;type=VCA;key=0;det_src=0;lim_mode=0;eq_pos=0;filter_on=0;filter_hpf=80.0;filter_lpf=8000.0;filter_q=1.0',
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
    p, a = c1_alloc.next(4)  # level + pan + mute + dca_coeff
    add(n_fader, 1, 'FADER_PAN', f'Ch {ch} Fader', 1, n_delay, n_route,
        spi_page=p, spi_addr=a,
        params='level_db=-inf;pan=0.0;mute=0',
        ramp_profile='GainFast')

    # --- ROUTING (fan-out to all buses) ---
    # outputs: all bus pre-sums
    p, a = c1_alloc.next(60)  # main_on + sub_on + grp_on×4 + aux_on×12 + aux_send×12 + aux_pick×12 + fx_on×6 + fx_send×6 + fx_pick×6
    route_outputs = ';'.join(all_bus_ids)
    add(n_route, 1, 'ROUTING', f'Ch {ch} Route', 1, n_fader, route_outputs,
        spi_page=p, spi_addr=a,
        params='main_on=1;sub_on=0;grp_on=0000;aux_on=000000000000;fx_on=000000',
        ramp_profile='GainFast')

    # Register this channel as a source for all buses
    for bid in all_bus_ids:
        bus_sources[bid].append(n_route)

# --- CHANNEL METERS (Chip 1, read-only) ---
p_mtr, a_mtr = c1_alloc.next(NUM_CH * 4)  # 4 meters per channel
for ch in range(1, NUM_CH + 1):
    cc = f'{ch:02d}'
    add(f'C1_MTR_{cc}', 1, 'METER', f'Ch {ch} Meter', 1,
        f'C1_GAIN_{cc};C1_FDR_{cc}', '',
        spi_page=p_mtr, spi_addr=a_mtr + (ch-1)*4,
        params='taps=post_trim;post_fader;gate_gr;comp_gr')

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

# Sanity: legacy bus order must land on global slots 0-24 unchanged
assert [MIX_GLOBAL[bus_signal[b]] for b in all_bus_ids] == list(range(25))

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
        params='level_db=0.0;pan=0.0;mute=0',
        ramp_profile='GainFast')

    p, a2 = c2_alloc.next(24)
    add(n_eq, 2, 'EQ_BIQUAD', f'Aux {a} EQ', 1, n_fdr, n_geq,
        spi_page=p, spi_addr=a2,
        params='bands=4;coeffs=default',
        ramp_profile='EqSafe')

    p, a2 = c2_alloc.next(28)  # 28-band GEQ
    add(n_geq, 2, 'GEQ', f'Aux {a} GEQ', 1, n_eq, n_afb,
        spi_page=p, spi_addr=a2,
        params='bands=28',
        ramp_profile='EqSafe')

    p, a2 = c2_alloc.next(24)  # 6 notches × (freq + gain + Q + biquad coeffs)
    add(n_afb, 2, 'ANTI_FB', f'Aux {a} AntiFB', 1, n_geq, n_lim,
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
        params='level_db=0.0;mute=0',
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
    params='level_db=0.0;mute=0',
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
# aux inputs (USB/BT/codec aux/Pi/snake, all default-off)
aux_input_ids = ['C2_USB_IN', 'C2_BT_IN', 'C2_CODEC_AUX_IN', 'C2_PI_IN'] + \
    [f'C2_SNK_IN_{s:02d}' for s in range(1, 9)]
grp_comp_ids = ';'.join(f'C2_GRP_COMP_{g:02d}' for g in range(1, NUM_GRP + 1))
aux_in_str = ';'.join(aux_input_ids)
main_l_sources = f'{recv_ids["main_l"]};{grp_comp_ids};{aux_in_str}'
main_r_sources = f'{recv_ids["main_r"]};{grp_comp_ids};{aux_in_str}'

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
add('C2_MAIN_FDR', 2, 'FADER_PAN', 'Main Fader', 2, 'C2_MIX_MAIN_L;C2_MIX_MAIN_R', 'C2_MAIN_GEQ',
    spi_page=p, spi_addr=a2,
    params='level_db=0.0;mute=0',
    ramp_profile='GainFast')

p, a2 = c2_alloc.next(28)
add('C2_MAIN_GEQ', 2, 'GEQ', 'Main GEQ', 2, 'C2_MAIN_FDR', 'C2_MAIN_COMP',
    spi_page=p, spi_addr=a2,
    params='bands=28',
    ramp_profile='EqSafe')

p, a2 = c2_alloc.next(16)
add('C2_MAIN_COMP', 2, 'COMPRESSOR', 'Main Comp', 2, 'C2_MAIN_GEQ', 'C2_MAIN_LIM',
    spi_page=p, spi_addr=a2,
    params='threshold_db=-20.0;ratio=4.0;attack_ms=5.0;release_ms=100.0;knee_db=6.0;makeup_db=0.0;parallel=0;type=VCA',
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
        params='level_db=-6.0;mute=0',
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
p_mtr, a_mtr = c2_alloc.next(40)  # aux×12 + main×8 + grp×4 + sub×1 + fx×6 = 31+
for a in range(1, NUM_AUX + 1):
    add(f'C2_MTR_AUX_{a:02d}', 2, 'METER', f'Aux {a} Meter', 1,
        f'C2_AUX_OUT_{a:02d}', '',
        spi_page=p_mtr, spi_addr=a_mtr + (a-1))

for m in range(1, 5):
    add(f'C2_MTR_MAIN_{m:02d}', 2, 'METER', f'Main {m} Meter', 1,
        f'C2_MAIN_OUT_{m:02d}', '',
        spi_page=p_mtr, spi_addr=a_mtr + 12 + (m-1)*2,
        params='taps=L;R')

for g in range(1, NUM_GRP + 1):
    add(f'C2_MTR_GRP_{g:02d}', 2, 'METER', f'Grp {g} Meter', 1,
        f'C2_GRP_COMP_{g:02d}', '',
        spi_page=p_mtr, spi_addr=a_mtr + 20 + (g-1))

add('C2_MTR_SUB', 2, 'METER', 'Sub Meter', 1, 'C2_SUB_OUT', '',
    spi_page=p_mtr, spi_addr=a_mtr + 24)

for f in range(1, NUM_FX + 1):
    add(f'C2_MTR_FX_{f:02d}', 2, 'METER', f'FX {f} Meter', 1,
        f'C2_FX_FDR_{f:02d}', '',
        spi_page=p_mtr, spi_addr=a_mtr + 25 + (f-1))

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
