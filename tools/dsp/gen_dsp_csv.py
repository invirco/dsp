#!/usr/bin/env python3
"""gen_dsp_csv.py — Generates dsp.csv for D32 from dsp-def.md signal chain spec.

Outputs: ../dsp.csv

Covers:
  Chip 1: 32× channel strip (IN → GAIN → HPF_LPF → EQ → GATE → COMP → TUBE → DELAY → FADER_PAN → ROUTING)
          + Talkback ×2 + Noise gen + Meters
          + Bus pre-sum sends (Main L/R, Sub, 4×Grp, 12×Aux, 6×FX) via inter-chip SPORT
  Chip 2: Bus receives → Aux ×12, Group ×4, Sub ×1, Main ×4, FX ×6, Monitor, meters, outputs
"""

import csv
import io
import os

# --- Column schema ---
# id, chip, type, label, ch_count, inputs, outputs, spi_page, spi_addr, params, ramp_profile

HEADER = ['id', 'chip', 'type', 'label', 'ch_count', 'inputs', 'outputs',
          'spi_page', 'spi_addr', 'params', 'ramp_profile']

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

# Collect all routing node IDs per bus (filled during channel generation)
bus_sources = {bid: [] for bid in all_bus_ids}

for ch in range(1, NUM_CH + 1):
    cc = f'{ch:02d}'
    sport_id = (ch - 1) // 8
    slot = (ch - 1) % 8

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
    add(n_in, 1, 'INPUT_TDM', f'Ch {ch} Input', 1, '', n_gain,
        params=f'sport_id={sport_id};slot_start={slot};slot_count=1')

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

# --- TALKBACK ×2 ---
p, a = c1_alloc.next(8)
for t in [1, 2]:
    add(f'C1_TALK_{t:02d}', 1, 'TALKBACK', f'Talkback {t}', 1, '', '',
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
# Each bus sums all 32 channel routing contributions and sends via inter-chip SPORT

# Inter-chip slot allocation: 25 buses total
#   Main L/R = slots 0,1
#   Sub = slot 2
#   Grp 1-4 = slots 3-6
#   Aux 1-12 = slots 7-18
#   FX 1-6 = slots 19-24
ic_slot = 0

def make_bus_and_send(bus_id, label, ic_slot_num, alloc):
    srcs = ';'.join(bus_sources[bus_id])
    p, a = alloc.next(2)
    add(bus_id, 1, 'MIX_BUS', label, 1, srcs, f'{bus_id}_SEND',
        spi_page=p, spi_addr=a,
        params=f'bus_id={ic_slot_num};source_count={NUM_CH}',
        ramp_profile='')  # bus summing is passive
    add(f'{bus_id}_SEND', 1, 'INTERCHIP_SEND', f'{label} Send', 1, bus_id, '',
        params=f'sport_id=7;slot={ic_slot_num}')
    return ic_slot_num + 1

ic_slot = make_bus_and_send(bus_main_l, 'Main L Bus', ic_slot, c1_alloc)
ic_slot = make_bus_and_send(bus_main_r, 'Main R Bus', ic_slot, c1_alloc)
ic_slot = make_bus_and_send(bus_sub, 'Sub Bus', ic_slot, c1_alloc)
for g in range(NUM_GRP):
    ic_slot = make_bus_and_send(bus_grp[g], f'Grp {g+1} Bus', ic_slot, c1_alloc)
for a_idx in range(NUM_AUX):
    ic_slot = make_bus_and_send(bus_aux[a_idx], f'Aux {a_idx+1} Bus', ic_slot, c1_alloc)
for f_idx in range(NUM_FX):
    ic_slot = make_bus_and_send(bus_fx[f_idx], f'FX {f_idx+1} Bus', ic_slot, c1_alloc)

# ===========================================================================
# CHIP 2 — Output DSP
# ===========================================================================

# --- Inter-chip RECV nodes (one per bus) ---
recv_ids = {}
ic_slot = 0
for bus_label, bus_key in [('Main L', 'main_l'), ('Main R', 'main_r'), ('Sub', 'sub')]:
    nid = f'C2_RECV_{bus_key.upper()}'
    add(nid, 2, 'INTERCHIP_RECV', f'{bus_label} Recv', 1, '', '',
        params=f'sport_id=7;slot={ic_slot}')
    recv_ids[bus_key] = nid
    ic_slot += 1

for g in range(1, NUM_GRP + 1):
    nid = f'C2_RECV_GRP_{g:02d}'
    add(nid, 2, 'INTERCHIP_RECV', f'Grp {g} Recv', 1, '', '',
        params=f'sport_id=7;slot={ic_slot}')
    recv_ids[f'grp_{g}'] = nid
    ic_slot += 1

for a in range(1, NUM_AUX + 1):
    nid = f'C2_RECV_AUX_{a:02d}'
    add(nid, 2, 'INTERCHIP_RECV', f'Aux {a} Recv', 1, '', '',
        params=f'sport_id=7;slot={ic_slot}')
    recv_ids[f'aux_{a}'] = nid
    ic_slot += 1

for f in range(1, NUM_FX + 1):
    nid = f'C2_RECV_FX_{f:02d}'
    add(nid, 2, 'INTERCHIP_RECV', f'FX {f} Recv', 1, '', '',
        params=f'sport_id=7;slot={ic_slot}')
    recv_ids[f'fx_{f}'] = nid
    ic_slot += 1

# --- AUX BUSES ×12 (Chip 2) ---
# Chain: RECV → FDR → EQ → ANTIFB → LIM → DLY → OUT
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
        params=f'sport_id={(a-1)//8 + 2};slot_start={(a-1)%8};slot_count=1')

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
# Chain: RECV → EQ → COMP → LIM → DLY → OUT
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
    params='sport_id=4;slot_start=0;slot_count=1')

# --- MAIN L/R BUS (Chip 2) ---
# Chain: RECV → MIX (with group feeds) → MASTER_FDR → GEQ_28 → COMP → LIM → DLY → XOVER → per-output EQ/COMP/LIM → OUT

# Main mix receives direct channel sums + group output feeds
grp_comp_ids = ';'.join(f'C2_GRP_COMP_{g:02d}' for g in range(1, NUM_GRP + 1))
main_l_sources = f'{recv_ids["main_l"]};{grp_comp_ids}'
main_r_sources = f'{recv_ids["main_r"]};{grp_comp_ids}'

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
add('C2_MAIN_DLY', 2, 'DELAY', 'Main Delay', 2, 'C2_MAIN_LIM', 'C2_MAIN_XOVER',
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

    sport_out = 4  # main outputs on SPORT4
    p, a2 = c2_alloc.next(1)
    add(n_out, 2, 'OUTPUT_TDM', f'Main Out {out_n}', 1, n_lim, '',
        spi_page=p, spi_addr=a2,
        params=f'sport_id={sport_out};slot_start={out_n-1+1};slot_count=1')

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
    params='sport_id=5;slot_start=0;slot_count=2')

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

# --- DCA MASTERS ×8 (Chip 2, mirrored via LP0) ---
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
# Write CSV
# ===========================================================================
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(script_dir, '..', 'dsp.csv')

with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=HEADER)
    writer.writeheader()
    writer.writerows(rows)

c1_count = sum(1 for r in rows if r['chip'] == '1')
c2_count = sum(1 for r in rows if r['chip'] == '2')
print(f"Generated {csv_path}")
print(f"  Total nodes: {len(rows)}")
print(f"  Chip 1: {c1_count}")
print(f"  Chip 2: {c2_count}")
print(f"  Chip 1 SPI words allocated: page {c1_alloc.page}, addr {c1_alloc.addr}")
print(f"  Chip 2 SPI words allocated: page {c2_alloc.page}, addr {c2_alloc.addr}")
