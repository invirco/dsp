#!/usr/bin/env python3
"""dsp_simulate.py — Python audio simulation of the D32 DSP signal graph.

Reads dsp.csv, builds the execution graph via topological sort, and runs
audio frames through numpy implementations of each node type.  Validates
signal flow, gain staging, and filter responses before hardware is available.

Usage
-----
  # Full channel 1 strip test (sine in, trace RMS at each stage):
  python3 dsp_simulate.py

  # Specific test type and parameters:
  python3 dsp_simulate.py --test sine   --freq 1000 --channels 1
  python3 dsp_simulate.py --test noise  --channels 1,2,3
  python3 dsp_simulate.py --test impulse --channels 1

  # Override per-node params at runtime:
  python3 dsp_simulate.py --gain-db 6 --hpf 200 --lpf 8000

  # Show frequency response of HPF/LPF or EQ for channel 1:
  python3 dsp_simulate.py --freq-response hpf --channel 1
  python3 dsp_simulate.py --freq-response eq  --channel 1

  # Save output to WAV:
  python3 dsp_simulate.py --wav out.wav --duration 0.5

Exit codes: 0 = OK, 1 = error.

Requires: numpy.  scipy and matplotlib are optional (used for freq response
and WAV output if available).
"""

import csv
import sys
import os
import math
import argparse
import numpy as np
from collections import defaultdict, deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csv_fields import parse_id_list as _parse_id_list, parse_params as _parse_params

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAMPLE_RATE   = 48000
# SHARC frame size. Single source: dsp_codegen.BLOCK, so the simulator and
# the firmware can never disagree about a block.
from dsp_codegen import BLOCK as BLOCK_SIZE
NYQUIST       = SAMPLE_RATE / 2.0
Q_MIN         = 0.10   # ruled minimum filter Q (PW 2026-08-29)

# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def load_nodes(csv_path):
    """Return list of node dicts from dsp.csv."""
    with open(csv_path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    nodes = {}
    for row in rows:
        nid = row['id'].strip()
        node = {
            'id':           nid,
            'chip':         row['chip'].strip(),
            'type':         row['type'].strip(),
            'label':        row.get('label', '').strip(),
            'ch_count':     int(row.get('ch_count', '1').strip()),
            'inputs':       _parse_id_list(row.get('inputs', '')),
            'outputs':      _parse_id_list(row.get('outputs', '')),
            'spi_page':     row.get('spi_page', '-1').strip(),
            'spi_addr':     row.get('spi_addr', '-1').strip(),
            'params':       _parse_params(row.get('params', '')),
            'ramp_profile': row.get('ramp_profile', '').strip(),
        }
        nodes[nid] = node
    return nodes


# ---------------------------------------------------------------------------
# Topological sort (Kahn's algorithm)
# ---------------------------------------------------------------------------

def fabric_links(nodes):
    """INTERCHIP_RECV id -> the INTERCHIP_SEND that feeds it (S143).

    THE TWO CHIPS WERE NOT CONNECTED IN THIS MODEL AT ALL. A recv node
    carries no `inputs` -- its samples arrive over the TDM mix fabric, not
    over a graph edge -- so every chip-2 node in this simulator read
    silence, and nothing downstream of the interchip boundary could be
    asked a question. That is why S142-1's mono main bus had to be found
    by reading the generator.

    The link is the mix fabric's own single source of truth: the
    `global_slot` both ends carry (shared/dsp4-logic/generated/
    sport_map.json, decision D2). Matched here rather than by name,
    because the names are a convention and the slot is the wire.

    ONE BLOCK OF LATENCY IS NOT MODELLED, and it is stated rather than
    hidden: on the part the DMA hands chip 2 the block chip 1 finished,
    so the fabric is one block old. Here the two run in the same pass.
    That is a LATENCY difference, not a ROUTING one -- which side of the
    desk a sample comes out on does not depend on it -- and the stereo
    proof this connection exists for is a routing question.
    """
    sends = {}
    for nid, n in nodes.items():
        if n['type'] == 'INTERCHIP_SEND':
            gs = n['params'].get('global_slot')
            if gs is not None:
                sends[str(gs)] = nid
    out = {}
    for nid, n in nodes.items():
        if n['type'] == 'INTERCHIP_RECV':
            gs = n['params'].get('global_slot')
            if gs is not None and str(gs) in sends:
                out[nid] = sends[str(gs)]
    return out


def topo_sort(nodes):
    """Return nodes in topological execution order.

    Handles fan-out (ROUTING → multiple buses) and fan-in (MIX_BUS ← many
    channels) correctly via in-degree tracking.
    """
    in_degree = {nid: 0 for nid in nodes}
    successors = defaultdict(list)
    links = fabric_links(nodes)

    for nid, node in nodes.items():
        for out_id in node['outputs']:
            if out_id in nodes:
                successors[nid].append(out_id)
                in_degree[out_id] += 1
    # The mix fabric is an edge here even though it is not an `inputs`
    # edge: chip 2 cannot run before chip 1 has produced the block it
    # reads. Without this the order is undefined across the boundary.
    for recv, send in links.items():
        successors[send].append(recv)
        in_degree[recv] += 1
    # A follower runs its master's coefficients, so it runs after it --
    # the same edge dsp_codegen.process_order_violations adds (S143).
    for nid, node in nodes.items():
        m = node['params'].get('follows')
        if m in nodes:
            successors[m].append(nid)
            in_degree[nid] += 1

    queue = deque(nid for nid, deg in in_degree.items() if deg == 0)
    order = []
    while queue:
        nid = queue.popleft()
        order.append(nid)
        for succ in successors[nid]:
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)

    if len(order) != len(nodes):
        unresolved = set(nodes) - set(order)
        print(f"WARNING: {len(unresolved)} nodes not in topological order "
              f"(possible cycle or disconnected nodes): {sorted(unresolved)[:5]}...")
    return order


# ---------------------------------------------------------------------------
# Biquad helpers
# ---------------------------------------------------------------------------

def biquad_coeffs_bypass():
    """DF-II transposed biquad coefficients for unity gain (passthrough)."""
    return np.array([1.0, 0.0, 0.0, 0.0, 0.0])  # [b0, b1, b2, a1, a2]


def check_q(q):
    """The ruled minimum filter Q (PW 2026-08-29, shared/numeric-spec.md).
    Rejected, not clamped: a silently clamped Q is the same class of
    defect as the silently saturated n1 the floor was ruled alongside."""
    if q < Q_MIN:
        raise ValueError(f'Q = {q} is below the ruled minimum {Q_MIN}')
    return q


def biquad_coeffs_hpf(freq_hz, q=0.707):
    """2nd-order Butterworth high-pass filter coefficients."""
    check_q(q)
    freq_hz = max(1.0, min(freq_hz, NYQUIST - 1))
    w0 = 2 * math.pi * freq_hz / SAMPLE_RATE
    alpha = math.sin(w0) / (2 * q)
    cos_w0 = math.cos(w0)
    b0 =  (1 + cos_w0) / 2
    b1 = -(1 + cos_w0)
    b2 =  (1 + cos_w0) / 2
    a0 =   1 + alpha
    a1 =  -2 * cos_w0
    a2 =   1 - alpha
    return np.array([b0/a0, b1/a0, b2/a0, a1/a0, a2/a0])


def biquad_coeffs_lpf(freq_hz, q=0.707):
    """2nd-order Butterworth low-pass filter coefficients."""
    check_q(q)
    freq_hz = max(1.0, min(freq_hz, NYQUIST - 1))
    w0 = 2 * math.pi * freq_hz / SAMPLE_RATE
    alpha = math.sin(w0) / (2 * q)
    cos_w0 = math.cos(w0)
    b0 =  (1 - cos_w0) / 2
    b1 =   1 - cos_w0
    b2 =  (1 - cos_w0) / 2
    a0 =   1 + alpha
    a1 =  -2 * cos_w0
    a2 =   1 - alpha
    return np.array([b0/a0, b1/a0, b2/a0, a1/a0, a2/a0])


def biquad_coeffs_peaking(freq_hz, gain_db, q=0.707):
    """Peaking EQ biquad coefficients."""
    check_q(q)
    freq_hz = max(1.0, min(freq_hz, NYQUIST - 1))
    A  = 10 ** (gain_db / 40.0)
    w0 = 2 * math.pi * freq_hz / SAMPLE_RATE
    alpha = math.sin(w0) / (2 * q)
    cos_w0 = math.cos(w0)
    b0 =   1 + alpha * A
    b1 =  -2 * cos_w0
    b2 =   1 - alpha * A
    a0 =   1 + alpha / A
    a1 =  -2 * cos_w0
    a2 =   1 - alpha / A
    return np.array([b0/a0, b1/a0, b2/a0, a1/a0, a2/a0])


def biquad_process(block, coeffs, state):
    """Process one block through a single biquad (DF-II transposed).

    state: list/array of [w1, w2] — updated in-place.
    Returns output block (float64 numpy array).
    """
    b0, b1, b2, a1, a2 = coeffs
    w1, w2 = state[0], state[1]
    out = np.empty_like(block)
    for i, x in enumerate(block):
        y   = b0 * x + w1
        w1  = b1 * x - a1 * y + w2
        w2  = b2 * x - a2 * y
        out[i] = y
    state[0], state[1] = w1, w2
    return out


def biquad_cascade(block, coeffs_list, states):
    """Process through a cascade of N biquads."""
    x = block
    for i, coeffs in enumerate(coeffs_list):
        x = biquad_process(x, coeffs, states[i])
    return x


# ---------------------------------------------------------------------------
# Node state initialisation
# ---------------------------------------------------------------------------

def make_state(node):
    """Create mutable runtime state for a node."""
    ntype = node['type']
    p = node['params']
    state = {'buf': np.zeros(BLOCK_SIZE), 'accumulator': False}

    if ntype == 'GAIN':
        state['gain_lin']  = db_to_lin(float(p.get('gain_db', '0')))
        state['mute']      = int(p.get('mute', '0'))
        state['polarity']  = int(p.get('polarity', '0'))

    elif ntype == 'HPF_LPF':
        hpf_hz  = float(p.get('hpf_freq', '80'))
        lpf_hz  = float(p.get('lpf_freq', '20000'))
        state['hpf_coeffs'] = biquad_coeffs_hpf(hpf_hz)
        state['lpf_coeffs'] = biquad_coeffs_lpf(lpf_hz)
        state['hpf_state']  = [0.0, 0.0]
        state['lpf_state']  = [0.0, 0.0]

    elif ntype == 'EQ_BIQUAD':
        bands = int(p.get('bands', '4'))
        # Default: 4-band bypass (100 Hz, 800 Hz, 3 kHz, 10 kHz peak at 0 dB)
        freqs = [100.0, 800.0, 3000.0, 10000.0][:bands]
        state['coeffs'] = [biquad_coeffs_bypass() for _ in range(bands)]
        state['states'] = [[0.0, 0.0] for _ in range(bands)]

    elif ntype == 'GATE':
        state['env']        = 0.0
        state['gain']       = 0.0      # 0 = open, 1 = gated
        state['threshold']  = db_to_lin(float(p.get('threshold_db', '-40')))
        state['attack']     = _ms_to_tc(float(p.get('attack_ms', '1')))
        state['release']    = _ms_to_tc(float(p.get('release_ms', '100')))
        state['hold_left']  = 0
        state['hold_count'] = int(float(p.get('hold_ms', '50')) * SAMPLE_RATE / 1000)
        state['range_lin']  = db_to_lin(-abs(float(p.get('range_db', '60'))))

    elif ntype == 'COMPRESSOR':
        state['env_dB']     = -120.0
        state['gain_dB']    = 0.0
        state['threshold']  = float(p.get('threshold_db', '-20'))
        state['ratio']      = float(p.get('ratio', '4'))
        state['attack']     = _ms_to_tc(float(p.get('attack_ms', '5')))
        state['release']    = _ms_to_tc(float(p.get('release_ms', '100')))
        state['knee']       = float(p.get('knee_db', '6'))
        state['makeup_lin'] = db_to_lin(float(p.get('makeup_db', '0')))

    elif ntype == 'TUBE_SAT':
        state['on']         = int(p.get('on', '1'))
        state['drive']      = float(p.get('saturation', '0.3'))

    elif ntype == 'DELAY':
        max_ms  = float(p.get('max_ms', '250'))
        delay_ms = float(p.get('delay_ms', '0'))
        max_samp = int(max_ms * SAMPLE_RATE / 1000) + BLOCK_SIZE
        state['buf_ring']   = np.zeros(max_samp)
        state['write_ptr']  = 0
        state['delay_samp'] = int(delay_ms * SAMPLE_RATE / 1000)
        state['max_samp']   = max_samp

    elif ntype == 'FADER_PAN':
        state['level_lin']  = db_to_lin(float(p.get('level_db', '0').replace('-inf', '-120')))
        state['pan']        = float(p.get('pan', '0.0'))   # −1 = full L, +1 = full R
        state['mute']       = int(p.get('mute', '0'))
        # For stereo nodes, buf_r holds right channel
        state['buf_r']      = np.zeros(BLOCK_SIZE)

    elif ntype == 'ROUTING':
        # buf holds the mono dry signal; routing target is handled in process
        state['aux_on']     = int(p.get('aux_on', '1'))
        state['grp_on']     = int(p.get('grp_on', '0'))
        state['main_on']    = int(p.get('main_on', '1'))
        state['sub_on']     = int(p.get('sub_on', '0'))
        state['fx_on']      = int(p.get('fx_on', '0'))

    elif ntype == 'SOURCE_SEL':
        # The select index lives in STATE, not in the row, so a desk proof
        # can move it the way a host would (S144). It starts where the row
        # says the node powers up.
        state['sel'] = int(p.get('sel', 0))

    elif ntype == 'MIX_BUS':
        state['accumulator'] = True    # zero at start of each frame, accumulate inputs

    elif ntype in ('INTERCHIP_SEND', 'INTERCHIP_RECV'):
        pass  # passthrough — connected by shared buffer reference at runtime

    return state


# ---------------------------------------------------------------------------
# Gain / dB helpers
# ---------------------------------------------------------------------------

def db_to_lin(db):
    if db <= -120:
        return 0.0
    return 10.0 ** (db / 20.0)


def lin_to_db(lin):
    if lin < 1e-12:
        return -120.0
    return 20.0 * math.log10(abs(lin))


def _ms_to_tc(ms):
    """Per-sample exponential time constant for ms attack/release."""
    if ms <= 0:
        return 1.0
    return math.exp(-1.0 / (ms * 0.001 * SAMPLE_RATE))


# ---------------------------------------------------------------------------
# Per-node process functions
# ---------------------------------------------------------------------------

def process_node(node, state, node_states, nodes, links=None,
                 bus_weights=None):
    """Process one BLOCK_SIZE-sample block for a node.

    Reads from input node buffers, writes to state['buf'].
    """
    ntype  = node['type']
    inputs = [nid for nid in node['inputs'] if nid in node_states]
    # A DETECTOR input is not a signal input (S143): `link_in` names the
    # other leg of a stereo-linked dynamics pair and modulates the gain.
    link = node['params'].get('link_in')

    def get_input(idx=0):
        if idx < len(inputs):
            return node_states[inputs[idx]]['buf'].copy()
        return np.zeros(BLOCK_SIZE)

    def detect_input():
        """|dry|, or max(|L|,|R|) on a stereo-linked node."""
        x = np.abs(get_input())
        if link and link in node_states:
            x = np.maximum(x, np.abs(node_states[link]['buf']))
        return x

    if ntype == 'INPUT_TDM':
        pass  # buf is pre-filled with test signal by the simulator

    elif ntype == 'INTERCHIP_RECV':
        # Across the mix fabric, by global slot (S143 — see fabric_links).
        src = (links or {}).get(node['id'])
        state['buf'] = (node_states[src]['buf'].copy() if src
                        else get_input())

    elif ntype in ('INTERCHIP_SEND', 'TALKBACK', 'NOISE_GEN',
                   'AUX_INPUT', 'DCA', 'TEST_OSC', 'TEST_MEAS'):
        state['buf'] = get_input()

    elif ntype == 'HAPTIC':
        # The panel speaker's source (S122). It has no input and it is
        # SILENT unless the host triggers it, which no simulation of the
        # audio graph does -- so silence is the right model here, and it is
        # the whole point of the node: nothing in the mix reaches it.
        state['buf'] = np.zeros(BLOCK_SIZE)

    elif ntype == 'METER':
        state['buf'] = get_input()   # passthrough; caller reads RMS from buf

    elif ntype == 'OUTPUT_TDM':
        state['buf'] = get_input()

    elif ntype == 'MIX_BUS':
        # Accumulate all inputs, each through its CROSSPOINT COEFFICIENT.
        #
        # THE PAN IS THE CROSSPOINT AND IT LIVES HERE (08-25 mandate). A
        # chip-1 strip's fader publishes `_fdr_lq`/`_fdr_rq`/`_fdr_cq` and
        # ROUTING folds them into the main-L / main-R / centre crosspoint
        # coefficients; the fader's own output is post-fader MONO. So a
        # hard-panned strip reaches the other main bus through a
        # coefficient of exactly zero, not through a scaled sample -- and
        # a model that summed every source at unity, as this one did until
        # S143, could not tell a panned desk from a mono one. `bus_weights`
        # is {(bus, source): gain}; anything not in it is unity, which is
        # what every other bus in the graph is.
        acc = np.zeros(BLOCK_SIZE)
        w = bus_weights or {}
        nid = node['id']
        for inp_id in inputs:
            g = w.get((nid, inp_id), 1.0)
            if g == 0.0:
                continue
            acc += node_states[inp_id]['buf'] * g
        state['buf'] = acc

    elif ntype == 'GAIN':
        x = get_input()
        if state['mute']:
            state['buf'] = np.zeros(BLOCK_SIZE)
        else:
            g = state['gain_lin']
            if state['polarity']:
                g = -g
            state['buf'] = x * g

    elif ntype == 'HPF_LPF':
        x = get_input()
        x = biquad_process(x, state['hpf_coeffs'], state['hpf_state'])
        x = biquad_process(x, state['lpf_coeffs'], state['lpf_state'])
        state['buf'] = x

    elif ntype == 'EQ_BIQUAD':
        x = get_input()
        state['buf'] = biquad_cascade(x, state['coeffs'], state['states'])

    elif ntype == 'GATE':
        x = get_input()
        out = np.empty(BLOCK_SIZE)
        env    = state['env']
        gain   = state['gain']
        tc_a   = state['attack']
        tc_r   = state['release']
        thresh = state['threshold']
        hold_c = state['hold_count']
        hold_l = state['hold_left']
        rng    = state['range_lin']
        for i in range(BLOCK_SIZE):
            lvl = abs(x[i])
            # Level follower (peak)
            if lvl > env:
                env = lvl + tc_a * (env - lvl)
            else:
                env = lvl + tc_r * (env - lvl)
            # Gate logic
            if env >= thresh:
                target = 1.0
                hold_l = hold_c
            else:
                if hold_l > 0:
                    hold_l -= 1
                    target = 1.0
                else:
                    target = rng
            gain = gain + 0.01 * (target - gain)   # simple smoothing
            out[i] = x[i] * gain
        state['env'] = env
        state['gain'] = gain
        state['hold_left'] = hold_l
        state['buf'] = out

    elif ntype == 'COMPRESSOR':
        x = get_input()
        det = detect_input()   # |dry|, or max(|L|,|R|) when link_in (S143)
        out = np.empty(BLOCK_SIZE)
        env_dB   = state['env_dB']
        gain_dB  = state['gain_dB']
        thresh   = state['threshold']
        ratio    = state['ratio']
        knee     = state['knee']
        tc_a     = state['attack']
        tc_r     = state['release']
        makeup   = state['makeup_lin']
        for i in range(BLOCK_SIZE):
            in_dB = lin_to_db(det[i])
            # Envelope follower (dB domain)
            if in_dB > env_dB:
                env_dB = in_dB + tc_a * (env_dB - in_dB)
            else:
                env_dB = in_dB + tc_r * (env_dB - in_dB)
            # Gain computation (hard knee)
            over = env_dB - thresh
            if over > 0:
                target_gain_dB = -over * (1.0 - 1.0 / ratio)
            else:
                target_gain_dB = 0.0
            gain_dB = gain_dB + 0.01 * (target_gain_dB - gain_dB)
            out[i] = x[i] * db_to_lin(gain_dB) * makeup
        state['env_dB'] = env_dB
        state['gain_dB'] = gain_dB
        state['buf'] = out

    elif ntype == 'TUBE_SAT':
        x = get_input()
        if state['on']:
            drive = max(0.01, state['drive'])
            # Soft clip: tanh waveshaper with drive
            state['buf'] = np.tanh(x * (1.0 + drive * 4.0)) / (1.0 + drive * 0.5)
        else:
            state['buf'] = x

    elif ntype == 'DELAY':
        x = get_input()
        ring  = state['buf_ring']
        wp    = state['write_ptr']
        d     = state['delay_samp']
        maxs  = state['max_samp']
        out   = np.empty(BLOCK_SIZE)
        for i in range(BLOCK_SIZE):
            ring[wp] = x[i]
            rp = (wp - d) % maxs
            out[i] = ring[rp]
            wp = (wp + 1) % maxs
        state['write_ptr'] = wp
        state['buf'] = out

    elif ntype == 'FADER_PAN':
        # THE FADER'S OUTPUT IS POST-FADER MONO. The pan is NOT applied
        # here and has not been in the firmware since the 2026-08-25
        # crosspoint-coefficient mandate: `_fdr_lq`/`_fdr_rq`/`_fdr_cq`
        # are published for ROUTING to fold into the BUS crosspoints, and
        # the node's own sample path is one MAC by `_fdr_gq` (level x
        # mute). This model applied the pan twice -- once here and, from
        # S143, once at the crosspoint -- which made a hard-panned strip
        # read 6e-17 on its LIVE side instead of full scale, and hid a
        # zero behind a rounding error. The legs live in `bus_weights`
        # now; see DSPSimulator.set_pan and the MIX_BUS note.
        x   = get_input()
        lvl = state['level_lin']
        if state['mute']:
            lvl = 0.0
        state['buf']   = x * lvl
        state['buf_r'] = state['buf']         # kept: same post-fader word

    elif ntype == 'ROUTING':
        state['buf'] = get_input()
        # Fan-out to bus nodes is handled implicitly via MIX_BUS accumulation

    elif ntype == 'GEQ':
        # Passthrough stub — GEQ coefficients not yet implemented
        state['buf'] = get_input()

    elif ntype == 'ANTI_FB':
        state['buf'] = get_input()

    elif ntype == 'FX_ENGINE':
        state['buf'] = get_input()

    elif ntype == 'LIMITER':
        x   = get_input()
        thr = db_to_lin(float(node['params'].get('threshold_db', '-0.5')))
        # A STEREO-LINKED brick wall applies ONE gain to both legs (S143):
        # the reduction is computed from max(|L|,|R|) and multiplied in, so
        # a leg that is silent stays exactly silent. Clipping each leg on
        # its own is the thing `link_in` exists to stop.
        if link and link in node_states:
            det = detect_input()
            g = np.where(det > thr, thr / np.maximum(det, 1e-30), 1.0)
            state['buf'] = x * g
        else:
            state['buf'] = np.clip(x, -thr, thr)    # simple hard limiter stub

    elif ntype == 'CROSSOVER':
        state['buf'] = get_input()

    elif ntype == 'MONITOR':
        state['buf'] = get_input()

    elif ntype == 'SOURCE_SEL':
        # S144. The select is a COEFFICIENT on the part: exactly one source
        # at 1.0 in the steady state, two during a ramped crossfade. The
        # model carries the steady state, which is the state every desk
        # proof runs in -- and it reads the index off the row rather than
        # defaulting to input 0, because a select that silently models
        # position 0 would pass `--stereo-proof` for a graph patched the
        # wrong way round.
        sel = int(state.get('sel', node['params'].get('sel', 0)))
        n = len(node['inputs'])
        if not 0 <= sel < n:
            raise ValueError(
                f"{node['id']}: sel={sel} outside 0..{n - 1}")
        state['buf'] = get_input(sel)

    else:
        state['buf'] = get_input()  # generic passthrough


# ---------------------------------------------------------------------------
# Simulator class
# ---------------------------------------------------------------------------

class DSPSimulator:
    def __init__(self, csv_path=None):
        if csv_path is None:
            # THE DEFAULT POINTED AT NOTHING. `tools/dsp/../dsp.csv` is
            # `tools/dsp.csv`, which has never existed -- a leftover from
            # when this script lived beside the graph. Running it with no
            # --csv raised FileNotFoundError, which is why every recorded
            # use of it passes one. The graph is where the codegen reads
            # it from (S143).
            script_dir = os.path.dirname(os.path.abspath(__file__))
            repo = os.path.dirname(os.path.dirname(script_dir))
            csv_path = os.path.join(repo, 'MW', 'D32', 'DSP', 'SHARC',
                                    'dsp.csv')
        self.nodes   = load_nodes(csv_path)
        self.order   = topo_sort(self.nodes)
        self.links   = fabric_links(self.nodes)
        # (bus, source) -> crosspoint gain. Unity unless a pan puts it
        # elsewhere; see set_pan() and the MIX_BUS note.
        self.bus_weights = {}
        self.reset()

    def reset(self):
        """Rebuild fresh per-node runtime state (same parsed graph)."""
        self.states  = {nid: make_state(n) for nid, n in self.nodes.items()}
        self.bus_weights = self._default_bus_weights()
        # A FOLLOWER RUNS ITS MASTER'S PARAMETERS (S143). In the emitted
        # code that is an `.extern`; here it is the master's state dict
        # keys copied in at reset, which is the same statement and keeps
        # the two from drifting when a test moves a master.
        for nid, n in self.nodes.items():
            m = n['params'].get('follows')
            if m in self.states:
                for k, v in self.states[m].items():
                    if k in ('buf', 'buf_r', 'buf_ring', 'write_ptr',
                             'accumulator', 'states', 'hpf_state',
                             'lpf_state', 'env_dB', 'gain_dB', 'env',
                             'gain', 'hold_left'):
                        continue
                    self.states[nid][k] = v

    # ── The pan crosspoint (S143) ────────────────────────────────────────────

    def _default_bus_weights(self):
        """The crosspoint coefficients dsp.csv's ROUTING rows declare.

        THE SIMULATOR USED TO SUM EVERY BUS AT UNITY, which is not the
        desk: a strip's `Chan*AuxSend`/`FxSend`/`GrpOn` decide whether it
        reaches a bus at all, and the graph's own defaults are main ON and
        everything else OFF (`main_on=1;sub_on=0;grp_on=0000;
        aux_on=000000000000;fx_on=000000;mtx_on=00`). Summing them all at
        unity meant every strip reached all twenty-nine buses, so the six
        FX returns fed the main mix a second, unpanned copy of the whole
        desk -- and a hard-panned strip came back on the far side at 0.74
        (measured here, S143). The bits are read from the row.
        """
        w = {}
        for nid, n in self.nodes.items():
            if n['type'] != 'ROUTING':
                continue
            p = n['params']
            for bus in n['outputs']:
                if bus not in self.nodes:
                    continue
                g = 0.0
                if bus in ('C1_BUS_MAIN_L', 'C1_BUS_MAIN_R'):
                    g = float(int(p.get('main_on', '1')))
                elif bus == 'C1_BUS_SUB':
                    g = float(int(p.get('sub_on', '0')))
                else:
                    for pref, key in (('C1_BUS_GRP_', 'grp_on'),
                                      ('C1_BUS_AUX_', 'aux_on'),
                                      ('C1_BUS_FX_', 'fx_on'),
                                      ('C1_BUS_MTX_', 'mtx_on')):
                        if bus.startswith(pref):
                            bits = p.get(key, '')
                            i = int(bus[len(pref):]) - 1
                            g = float(bits[i] == '1') if i < len(bits) else 0.0
                            break
                w[(bus, nid)] = g
        return w

    def set_pan(self, channel, pan):
        """Pan a chip-1 strip, as the CROSSPOINT COEFFICIENT it really is.

        `pan` is -1 hard left .. +1 hard right, matching FADER_PAN's own
        parameter. The strip's post-fader signal is MONO; what a pan moves
        is the coefficient the main-L and main-R buses MAC it with (the
        08-25 crosspoint fold), so that is what this writes. Hard left is
        a right-hand coefficient of EXACTLY ZERO -- not -120 dB, zero --
        which is what makes `--stereo-proof`'s claim exact.
        """
        rtg = f'C1_RTG_{channel:02d}'
        fdr = f'C1_FDR_{channel:02d}'
        if rtg not in self.nodes:
            raise KeyError(rtg)
        if fdr in self.states:
            self.states[fdr]['pan'] = pan
        ang = (pan + 1.0) * 0.25 * math.pi
        g_l, g_r = math.cos(ang), math.sin(ang)
        if abs(pan + 1.0) < 1e-12:
            g_l, g_r = 1.0, 0.0
        elif abs(pan - 1.0) < 1e-12:
            g_l, g_r = 0.0, 1.0
        self.bus_weights[('C1_BUS_MAIN_L', rtg)] = g_l
        self.bus_weights[('C1_BUS_MAIN_R', rtg)] = g_r

    # ── Parameter control ────────────────────────────────────────────────────

    def set_gain(self, channel, gain_db):
        nid = f'C1_GAIN_{channel:02d}'
        if nid in self.states:
            self.states[nid]['gain_lin'] = db_to_lin(gain_db)

    def set_hpf(self, channel, freq_hz):
        nid = f'C1_FILT_{channel:02d}'
        if nid in self.states:
            self.states[nid]['hpf_coeffs'] = biquad_coeffs_hpf(freq_hz)
            self.states[nid]['hpf_state']  = [0.0, 0.0]

    def set_lpf(self, channel, freq_hz):
        nid = f'C1_FILT_{channel:02d}'
        if nid in self.states:
            self.states[nid]['lpf_coeffs'] = biquad_coeffs_lpf(freq_hz)
            self.states[nid]['lpf_state']  = [0.0, 0.0]

    def set_eq_band(self, channel, band, freq_hz, gain_db, q=0.707):
        nid = f'C1_EQ_{channel:02d}'
        if nid in self.states:
            self.states[nid]['coeffs'][band] = biquad_coeffs_peaking(freq_hz, gain_db, q)

    def set_fader(self, channel, level_db, pan=0.0):
        nid = f'C1_FDR_{channel:02d}'
        if nid in self.states:
            self.states[nid]['level_lin'] = db_to_lin(level_db)
            self.states[nid]['pan'] = pan

    # ── Signal injection ─────────────────────────────────────────────────────

    def inject(self, channel, block):
        """Write a BLOCK_SIZE audio block into INPUT_TDM node for a channel."""
        nid = f'C1_IN_{channel:02d}'
        if nid in self.states:
            self.states[nid]['buf'] = block.astype(np.float64)

    # ── Frame processing ─────────────────────────────────────────────────────

    def process_frame(self):
        """Process one block of BLOCK_SIZE samples through the full graph."""
        # Zero all MIX_BUS accumulators at start of frame
        for nid, state in self.states.items():
            if state.get('accumulator'):
                state['buf'] = np.zeros(BLOCK_SIZE)

        for nid in self.order:
            if nid not in self.nodes:
                continue
            node  = self.nodes[nid]
            state = self.states[nid]
            process_node(node, state, self.states, self.nodes,
                         links=self.links, bus_weights=self.bus_weights)

    # ── Utility: read RMS from a node's output buffer ────────────────────────

    def rms(self, node_id):
        if node_id not in self.states:
            return 0.0
        b = self.states[node_id]['buf']
        return float(np.sqrt(np.mean(b ** 2)))

    def rms_db(self, node_id):
        return lin_to_db(self.rms(node_id))

    # ── High-level test helpers ───────────────────────────────────────────────

    def run_channel_strip(self, channel=1, test='sine', freq=1000.0,
                          n_frames=150, gain_db=0.0, hpf_hz=None, lpf_hz=None):
        """Run n_frames through channel strip and return per-stage RMS (dB).

        Returns a dict: stage_name -> rms_db list (one entry per frame).
        """
        self.set_gain(channel, gain_db)
        # Open fader to unity for testing (CSV default is -inf = fader down)
        self.set_fader(channel, 0.0, pan=0.0)
        if hpf_hz is not None:
            self.set_hpf(channel, hpf_hz)
        if lpf_hz is not None:
            self.set_lpf(channel, lpf_hz)

        strip_nodes = [
            f'C1_IN_{channel:02d}',
            f'C1_GAIN_{channel:02d}',
            f'C1_FILT_{channel:02d}',
            f'C1_EQ_{channel:02d}',
            f'C1_GATE_{channel:02d}',
            f'C1_COMP_{channel:02d}',
            f'C1_TUBE_{channel:02d}',
            f'C1_DLY_{channel:02d}',
            f'C1_FDR_{channel:02d}',
            f'C1_RTG_{channel:02d}',
        ]

        history = defaultdict(list)
        t = 0.0

        for frame in range(n_frames):
            # Generate test block
            t_arr = np.arange(BLOCK_SIZE) / SAMPLE_RATE + t
            if test == 'sine':
                block = np.sin(2 * math.pi * freq * t_arr)
            elif test == 'noise':
                block = np.random.randn(BLOCK_SIZE) * 0.5
            elif test == 'impulse':
                block = np.zeros(BLOCK_SIZE)
                if frame == 0:
                    block[0] = 1.0
            else:
                block = np.zeros(BLOCK_SIZE)
            t += BLOCK_SIZE / SAMPLE_RATE

            self.inject(channel, block)
            self.process_frame()

            for nid in strip_nodes:
                if nid in self.states:
                    history[nid].append(self.rms_db(nid))

        return history

    def frequency_response(self, channel=1, node_type='hpf', n_freqs=200):
        """Sweep test tones through the strip and return (freqs, gains_db).

        node_type: 'hpf'  — measure after HPF_LPF node
                   'eq'   — measure after EQ node
                   'strip'— measure after full channel strip (RTG node)
        """
        target_map = {
            'hpf':   f'C1_FILT_{channel:02d}',
            'eq':    f'C1_EQ_{channel:02d}',
            'strip': f'C1_RTG_{channel:02d}',
        }
        target_node = target_map.get(node_type, f'C1_FILT_{channel:02d}')

        freqs  = np.logspace(np.log10(20), np.log10(20000), n_freqs)
        gains  = []

        for freq in freqs:
            # Reset state for this measurement
            self.states[f'C1_FILT_{channel:02d}']['hpf_state'] = [0.0, 0.0]
            self.states[f'C1_FILT_{channel:02d}']['lpf_state'] = [0.0, 0.0]
            # Warm-up run to settle filters
            for _ in range(20):
                t_arr = np.arange(BLOCK_SIZE) / SAMPLE_RATE
                block = np.sin(2 * math.pi * freq * t_arr)
                self.inject(channel, block)
                self.process_frame()
            # Measure RMS over 10 frames
            rms_sum = 0.0
            for _ in range(10):
                t_arr = np.arange(BLOCK_SIZE) / SAMPLE_RATE
                block = np.sin(2 * math.pi * freq * t_arr)
                self.inject(channel, block)
                self.process_frame()
                rms_sum += self.rms(target_node)
            gains.append(lin_to_db(rms_sum / 10.0) - lin_to_db(0.5 ** 0.5))  # ref = 0 dBFS

        return freqs, np.array(gains)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _strip_label(node_id):
    """Short display name for a node ID."""
    parts = node_id.split('_')
    # e.g. C1_GAIN_01 → GAIN_01
    return '_'.join(parts[1:]) if len(parts) > 1 else node_id



# ---------------------------------------------------------------------------
# THE STEREO PROOF (S143) — the numeric half
# ---------------------------------------------------------------------------

_PROOF_SINKS = [
    ('C2_MAIN_OUT_01', 'L', 'MainL XLR (DAC_12, J56)'),
    ('C2_MAIN_OUT_02', 'R', 'MainR XLR (DAC_11, J57)'),
    # S144: main outputs 3 and 4 are gone; the ONE Centre/LF XLR is here.
    # AT THE SHIPPING DEFAULT `Main Out3Mode` IS 0 = CENTRE, and the Centre
    # strip is fed from the Ctr Channel Bus (`Chan*CtrOn`, summed on chip 1)
    # and not from the main mix at all — so a hard-panned strip reads
    # EXACTLY ZERO here at either pan. The Woof half is proved by its own
    # pass below, with the select moved the way a host would move it.
    ('C2_OUT3_OUT', 'none', 'The Centre/LF XLR (DAC_14, J55) at Out3Mode=0: '
                            'the Centre strip is off the Ctr Channel Bus, '
                            'which a main-bus pan cannot reach'),
    ('C2_MAIN_ST_OUT', 'L', 'DAC MAIN L'),
    ('C2_MAIN_ST_OUT_R', 'R', 'DAC MAIN R'),
    ('C2_CODEC_AUX_OUT', 'L', 'CODEC_OUT_3'),
    ('C2_CODEC_AUX_OUT_R', 'R', 'CODEC_OUT_4'),
    ('C2_MON_DLY', 'L', 'Monitor L'),
    ('C2_MON_DLY_R', 'R', 'Monitor R'),
]


def stereo_proof(sim, channel=1, freq=1000.0, frames=8):
    """Hard-pan one strip; every sink on the other side must read ZERO.

    THE READING S142 ASKED FOR, taken on the desk instead of the bench.
    A strip panned hard left puts EXACTLY ZERO into the right main bus --
    the crosspoint coefficient is zero, not small (see set_pan) -- so
    every output fed only by the right leg must be zero to the last bit,
    and every output fed by the left leg must not be. Then the same run
    with the pan hard right, which is the control: a test that only ever
    pans one way cannot tell a stereo desk from one wired backwards.

    It is run twice more with the strip at CENTRE, where both sides must
    be live and equal -- otherwise "zero on the far side" would also be
    satisfied by a graph that had simply stopped passing audio.
    """
    print()
    print('STEREO PROOF (S143) — hard-pan strip %d, read every chip-2 sink'
          % channel)
    missing = [n for n, _, _ in _PROOF_SINKS if n not in sim.states]
    if missing:
        print('  ERROR: this graph has no %s — it is not an S143 graph'
              % ', '.join(missing))
        return 1

    def run(pan):
        sim.reset()
        sim.set_gain(channel, 0.0)
        sim.set_fader(channel, 0.0)
        sim.set_pan(channel, pan)
        # Every OTHER strip muted, so what arrives at a sink arrives from
        # this one and there is nothing to argue about.
        for ch in range(1, 33):
            nid = 'C1_FDR_%02d' % ch
            if nid in sim.states and ch != channel:
                sim.states[nid]['mute'] = 1
        for f in range(frames):
            t = (np.arange(BLOCK_SIZE) + f * BLOCK_SIZE) / SAMPLE_RATE
            sim.inject(channel, 0.5 * np.sin(2 * math.pi * freq * t))
            sim.process_frame()
        return {n: sim.states[n]['buf'].copy() for n, _, _ in _PROOF_SINKS}

    fails = []
    for pan, label, live_side in ((-1.0, 'hard LEFT', 'L'),
                                  (+1.0, 'hard RIGHT', 'R')):
        got = run(pan)
        print('  %s:' % label)
        for nid, side, why in _PROOF_SINKS:
            b = got[nid]
            peak = float(np.max(np.abs(b)))
            nz = int(np.count_nonzero(b))
            # 'none' is a side nothing reaches from the main mix at all --
            # exactly zero at both pans, not "zero on the far side" (S144).
            want_live = (side == live_side)
            ok = (peak > 0.0) if want_live else (nz == 0)
            print('    %-3s %-20s %-5s peak=%-12.9g %s'
                  % ('OK ' if ok else 'BAD', nid, side,
                     peak, 'live' if want_live else 'must be EXACTLY 0'))
            if not ok:
                fails.append('%s at pan %s: side %s, peak %.9g, %d non-zero '
                             'sample(s) — %s' % (nid, label, side, peak, nz,
                                                 why))

    # THE CONTROL: centre. Both sides live, and equal, or "zero on the far
    # side" is satisfied by a graph that passes nothing at all.
    got = run(0.0)
    print('  CENTRE (control — both sides live and equal):')
    lpk = float(np.max(np.abs(got['C2_MAIN_OUT_01'])))
    rpk = float(np.max(np.abs(got['C2_MAIN_OUT_02'])))
    ok = lpk > 0.0 and rpk > 0.0 and abs(lpk - rpk) <= 1e-12 * max(lpk, 1.0)
    print('    %-3s MainL peak=%.9g  MainR peak=%.9g  delta=%.3g'
          % ('OK ' if ok else 'BAD', lpk, rpk, abs(lpk - rpk)))
    if not ok:
        fails.append('centre control: MainL %.9g, MainR %.9g — a centred '
                     'strip must reach both XLRs at the same level'
                     % (lpk, rpk))
    for nid, side, why in _PROOF_SINKS:
        if side != 'none':
            continue
        nz = int(np.count_nonzero(got[nid]))
        print('    %-3s %-20s none  %d non-zero sample(s) at CENTRE'
              % ('OK ' if nz == 0 else 'BAD', nid, nz))
        if nz:
            fails.append('%s reads %d non-zero sample(s) from a CENTRED '
                         'strip and the main mix must not reach it at all '
                         '— %s' % (nid, nz, why))

    # ── THE Out3 SELECT, MOVED (S144) ───────────────────────────────────
    #
    # The pass above proves the C/LF XLR carries the CENTRE at the shipping
    # default. This one proves the other half of the same socket: with
    # `Main Out3Mode` = 1 the Woof strip drives it, the Woof is the MONO SUM
    # of the two main legs, and a mono sum of L+R is reached from EITHER
    # side. Both readings are true of one output and they are what the
    # coefficient between them selects; the static gate
    # (`stereo_split_check` gate B) reports the union, 'both'.
    print('  Out3Mode = 1 (Woof: the mono LF sum of both main legs):')
    for pan, label in ((-1.0, 'hard LEFT'), (+1.0, 'hard RIGHT'),
                       (0.0, 'CENTRE')):
        sim.reset()
        sim.states['C2_OUT3_SEL']['sel'] = 1
        sim.set_gain(channel, 0.0)
        sim.set_fader(channel, 0.0)
        sim.set_pan(channel, pan)
        for ch in range(1, 33):
            nid = 'C1_FDR_%02d' % ch
            if nid in sim.states and ch != channel:
                sim.states[nid]['mute'] = 1
        for f in range(frames):
            t = (np.arange(BLOCK_SIZE) + f * BLOCK_SIZE) / SAMPLE_RATE
            sim.inject(channel, 0.5 * np.sin(2 * math.pi * freq * t))
            sim.process_frame()
        pk = float(np.max(np.abs(sim.states['C2_OUT3_OUT']['buf'])))
        ok3 = pk > 0.0
        print('    %-3s C2_OUT3_OUT  %-10s peak=%-12.9g must be LIVE'
              % ('OK ' if ok3 else 'BAD', label, pk))
        if not ok3:
            fails.append('C2_OUT3_OUT at Out3Mode=1, pan %s: peak %.9g — the '
                         'Woof is the mono sum of both main legs, so it is '
                         'reached from either side' % (label, pk))

    if fails:
        print()
        print('%d failure(s):' % len(fails))
        for f in fails:
            print('  ' + f)
        return 1
    print()
    print('stereo proof passed: every one-sided sink reads EXACTLY zero on '
          'the far side, both ways, and the centre control is live and '
          'balanced')
    return 0


def main():
    ap = argparse.ArgumentParser(description='D32 DSP Python signal-graph simulator')
    ap.add_argument('--csv', default=None, help='Path to dsp.csv')
    ap.add_argument('--test', choices=['sine', 'noise', 'impulse'], default='sine',
                    help='Test signal type (default: sine)')
    ap.add_argument('--freq', type=float, default=1000.0,
                    help='Sine frequency Hz (default: 1000)')
    ap.add_argument('--channels', default='1',
                    help='Comma-separated channel numbers to test (default: 1)')
    ap.add_argument('--gain-db', type=float, default=0.0,
                    help='Input gain in dB (default: 0)')
    ap.add_argument('--hpf', type=float, default=None,
                    help='HPF cutoff frequency Hz (overrides CSV default)')
    ap.add_argument('--lpf', type=float, default=None,
                    help='LPF cutoff frequency Hz (overrides CSV default)')
    ap.add_argument('--frames', type=int, default=150,
                    help='Number of BLOCK-sample frames to process (default: 150)')
    ap.add_argument('--freq-response', choices=['hpf', 'eq', 'strip'], default=None,
                    dest='freq_response',
                    help='Plot/print frequency response at given node type')
    ap.add_argument('--wav', default=None,
                    help='Save output WAV file (requires scipy)')
    ap.add_argument('--duration', type=float, default=1.0,
                    help='WAV duration in seconds (default: 1.0)')
    ap.add_argument('--stereo-proof', action='store_true',
                    help='hard-pan a strip and read every chip-2 sink: the '
                         'numeric half of the S143 proof (see stereo_proof)')
    args = ap.parse_args()

    channels = [int(c.strip()) for c in args.channels.split(',')]

    sim = DSPSimulator(args.csv)
    print(f"Loaded {len(sim.nodes)} nodes, topo order: {len(sim.order)} resolved")

    if args.stereo_proof:
        return stereo_proof(sim, channel=channels[0], freq=args.freq)

    # ── Frequency response test ──────────────────────────────────────────────
    if args.freq_response:
        ch = channels[0]
        print(f"\nFrequency response ({args.freq_response}, channel {ch}):")
        freqs, gains = sim.frequency_response(ch, args.freq_response)
        # Print table at ~1/3-octave intervals
        print(f"  {'Freq (Hz)':>10}  {'Gain (dB)':>10}")
        print(f"  {'-'*10}  {'-'*10}")
        step = max(1, len(freqs) // 20)
        for i in range(0, len(freqs), step):
            print(f"  {freqs[i]:>10.1f}  {gains[i]:>10.2f}")

        # Try matplotlib
        try:
            import matplotlib.pyplot as plt
            plt.figure(figsize=(10, 5))
            plt.semilogx(freqs, gains)
            plt.xlabel('Frequency (Hz)')
            plt.ylabel('Gain (dB)')
            plt.title(f'Frequency Response — {args.freq_response.upper()} Ch{ch}')
            plt.grid(True, which='both', alpha=0.4)
            plt.xlim(20, 20000)
            plt.tight_layout()
            plt.show()
        except ImportError:
            print("  (matplotlib not available — skipping plot)")
        return 0

    # ── Channel strip trace ──────────────────────────────────────────────────
    for ch in channels:
        print(f"\nChannel {ch} strip — {args.test} @ {args.freq:.0f} Hz, "
              f"gain={args.gain_db:+.1f} dB, {args.frames} frames:")

        history = sim.run_channel_strip(
            channel=ch,
            test=args.test,
            freq=args.freq,
            n_frames=args.frames,
            gain_db=args.gain_db,
            hpf_hz=args.hpf,
            lpf_hz=args.lpf,
        )

        # Print steady-state RMS (last 10 frames average) per stage
        print(f"  {'Stage':<18}  {'RMS (dB)':>10}  {'Status'}")
        print(f"  {'-'*18}  {'-'*10}  {'-'*20}")
        prev_rms = None
        for nid, rms_list in history.items():
            if not rms_list:
                continue
            steady = np.mean(rms_list[-10:])
            label = _strip_label(nid)
            delta = ''
            if prev_rms is not None and abs(prev_rms) < 200:
                diff = steady - prev_rms
                delta = f'({diff:+.1f} dB)' if abs(diff) > 0.1 else '(flat)'
            status = 'OK' if steady > -100 else 'SILENT'
            print(f"  {label:<18}  {steady:>10.2f}  {delta} {status}")
            prev_rms = steady

    # ── WAV output ───────────────────────────────────────────────────────────
    if args.wav:
        try:
            from scipy.io import wavfile
        except ImportError:
            print("ERROR: scipy not available — cannot write WAV")
            return 1

        ch = channels[0]
        n_frames = int(args.duration * SAMPLE_RATE / BLOCK_SIZE)
        sim.reset()  # clean state — don't carry over the trace run above
        sim.set_gain(ch, args.gain_db)
        if args.hpf:
            sim.set_hpf(ch, args.hpf)
        if args.lpf:
            sim.set_lpf(ch, args.lpf)

        out_buf = []
        for frame in range(n_frames):
            t_arr = np.arange(BLOCK_SIZE) / SAMPLE_RATE + frame * BLOCK_SIZE / SAMPLE_RATE
            block = np.sin(2 * math.pi * args.freq * t_arr)
            sim.inject(ch, block)
            sim.process_frame()
            out_nid = f'C1_RTG_{ch:02d}'
            out_buf.append(sim.states[out_nid]['buf'].copy())

        audio = np.concatenate(out_buf).astype(np.float32)
        wavfile.write(args.wav, SAMPLE_RATE, audio)
        print(f"\nWrote {len(audio)} samples to {args.wav}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
