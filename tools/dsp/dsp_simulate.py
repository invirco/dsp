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

def topo_sort(nodes):
    """Return nodes in topological execution order.

    Handles fan-out (ROUTING → multiple buses) and fan-in (MIX_BUS ← many
    channels) correctly via in-degree tracking.
    """
    in_degree = {nid: 0 for nid in nodes}
    successors = defaultdict(list)

    for nid, node in nodes.items():
        for out_id in node['outputs']:
            if out_id in nodes:
                successors[nid].append(out_id)
                in_degree[out_id] += 1

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

def process_node(node, state, node_states, nodes):
    """Process one BLOCK_SIZE-sample block for a node.

    Reads from input node buffers, writes to state['buf'].
    """
    ntype  = node['type']
    inputs = [nid for nid in node['inputs'] if nid in node_states]

    def get_input(idx=0):
        if idx < len(inputs):
            return node_states[inputs[idx]]['buf'].copy()
        return np.zeros(BLOCK_SIZE)

    if ntype == 'INPUT_TDM':
        pass  # buf is pre-filled with test signal by the simulator

    elif ntype in ('INTERCHIP_RECV', 'INTERCHIP_SEND', 'TALKBACK', 'NOISE_GEN',
                   'AUX_INPUT', 'DCA'):
        state['buf'] = get_input()

    elif ntype == 'METER':
        state['buf'] = get_input()   # passthrough; caller reads RMS from buf

    elif ntype == 'OUTPUT_TDM':
        state['buf'] = get_input()

    elif ntype == 'MIX_BUS':
        # Accumulate all inputs
        acc = np.zeros(BLOCK_SIZE)
        for inp_id in inputs:
            acc += node_states[inp_id]['buf']
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
            in_dB = lin_to_db(abs(x[i]))
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
        # Mono input → constant-power pan split
        x   = get_input()
        lvl = state['level_lin']
        if state['mute']:
            lvl = 0.0
        pan  = state['pan']                    # −1..+1
        ang  = (pan + 1.0) * 0.25 * math.pi   # 0..π/2
        g_l  = math.cos(ang) * lvl
        g_r  = math.sin(ang) * lvl
        state['buf']   = x * g_l              # left channel
        state['buf_r'] = x * g_r              # right channel

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
        out = np.clip(x, -thr, thr)    # simple hard limiter stub
        state['buf'] = out

    elif ntype == 'CROSSOVER':
        state['buf'] = get_input()

    elif ntype == 'MONITOR':
        state['buf'] = get_input()

    else:
        state['buf'] = get_input()  # generic passthrough


# ---------------------------------------------------------------------------
# Simulator class
# ---------------------------------------------------------------------------

class DSPSimulator:
    def __init__(self, csv_path=None):
        if csv_path is None:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            csv_path = os.path.join(script_dir, '..', 'dsp.csv')
        self.nodes   = load_nodes(csv_path)
        self.order   = topo_sort(self.nodes)
        self.reset()

    def reset(self):
        """Rebuild fresh per-node runtime state (same parsed graph)."""
        self.states  = {nid: make_state(n) for nid, n in self.nodes.items()}

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
            process_node(node, state, self.states, self.nodes)

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
    args = ap.parse_args()

    channels = [int(c.strip()) for c in args.channels.split(',')]

    sim = DSPSimulator(args.csv)
    print(f"Loaded {len(sim.nodes)} nodes, topo order: {len(sim.order)} resolved")

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
