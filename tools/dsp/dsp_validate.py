#!/usr/bin/env python3
"""dsp_validate.py — Validate dsp.csv for the D32 SHARC+ DSP project.

Usage: python3 dsp_validate.py [path/to/dsp.csv]
       Default: ../dsp.csv (relative to this script)

Exit codes:
  0  — no errors
  1  — validation errors found

Checks:
  1. All required columns are present
  2. Node IDs are unique and non-empty
  3. chip is '1' or '2'
  4. type is a known node type
  5. ramp_profile is a known profile or empty
  6. ch_count is a positive integer
  7. spi_page/spi_addr are integers; INPUT_TDM and TDM outputs may use -1
  8. SPI (chip, page, addr) tuples are unique among nodes with valid addresses
  9. inputs and outputs reference valid node IDs
 10. Required params are present for each node type
 11. The per-chip graph is ACYCLIC on same-chip input edges, so the
     generator can order every producer ahead of its consumers
     (review finding D5). CSV rows whose inputs run later are reported
     as notes: dsp_codegen.py repairs those, and this is the
     independent second instrument that says what it had to repair.
"""

import csv
import sys
import os
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from csv_fields import parse_id_list, parse_params

# ---------------------------------------------------------------------------
REQUIRED_COLUMNS = {'id', 'chip', 'type', 'ch_count', 'inputs', 'outputs',
                    'spi_page', 'spi_addr', 'params', 'ramp_profile'}

VALID_TYPES = {
    'ANTI_FB', 'AUX_INPUT', 'COMPRESSOR', 'CROSSOVER', 'DCA', 'DELAY',
    'EQ_BIQUAD', 'FADER_PAN', 'FX_ENGINE', 'GAIN', 'GATE', 'GEQ',
    'HAPTIC', 'HPF_LPF', 'INPUT_TDM', 'INTERCHIP_RECV', 'INTERCHIP_SEND', 'LIMITER',
    'METER', 'MIX_BUS', 'MONITOR', 'NOISE_GEN', 'OUTPUT_TDM', 'ROUTING',
    'TALKBACK', 'TEST_MEAS', 'TEST_OSC', 'TUBE_SAT',
}

VALID_RAMP_PROFILES = {'', 'DynSafe', 'EqSafe', 'GainFast', 'GainSafe', 'InstantCtl'}

# Minimum required param keys per node type
REQUIRED_PARAMS = {
    'INPUT_TDM':      {'sport_id', 'slot_start', 'slot_count'},
    'OUTPUT_TDM':     {'sport_id', 'slot_start', 'slot_count'},
    'INTERCHIP_RECV': {'sport_id', 'slot'},
    'INTERCHIP_SEND': {'sport_id', 'slot'},
    'GAIN':           {'gain_db', 'mute', 'polarity'},
    'HPF_LPF':        {'hpf_freq', 'hpf_slope', 'lpf_freq'},
    'EQ_BIQUAD':      {'bands'},
    'GATE':           {'threshold_db', 'attack_ms', 'release_ms', 'hold_ms', 'range_db'},
    'COMPRESSOR':     {'threshold_db', 'ratio', 'attack_ms', 'release_ms', 'knee_db', 'makeup_db'},
    'DELAY':          {'delay_ms', 'max_ms'},
    'FADER_PAN':      {'level_db', 'mute'},       # pan is optional (absent on mono bus faders)
    'ROUTING':        {'aux_on', 'grp_on', 'main_on', 'sub_on'},
    'MIX_BUS':        {'bus_id'},                 # source_count is informational, not always set
    'GEQ':            {'bands'},
    'ANTI_FB':        {'notch_count'},
    'FX_ENGINE':      {'type'},
    'LIMITER':        {'threshold_db', 'attack_ms', 'release_ms'},
    'CROSSOVER':      {'freq', 'slope'},
    'TUBE_SAT':       {'saturation'},
    'TALKBACK':       {'gain_db', 'route'},
    'METER':          set(),                      # taps is optional (only L/R main meters set it)
    'DCA':            {'level_db', 'mute'},
    'NOISE_GEN':      {'level_db', 'on'},
    'MONITOR':        {'source'},
    # The S49 self-test pair. TEST_OSC must name the frequency and
    # level it comes up at (they are .var initialisers in the kernel);
    # TEST_MEAS must name the oscillator whose state blocks are its
    # reference, because nothing else in the graph can tell it.
    'TEST_OSC':       {'on', 'freq_hz', 'level', 'chan'},
    'TEST_MEAS':      {'meas_chan', 'osc_src'},
    # THE PANEL HAPTIC (S122). `click_hz` / `click_tau_ms` (parallel lists),
    # `click_peak`, `click_end_db` and `tone_hz` are the DESIGN of the stored
    # waveforms -- the generator builds the tables from them and from nothing
    # else -- so they are required, not optional: a haptic node that does not
    # say what it stores stores whatever the generator's last default was,
    # which is the shape this tree calls a defect.
    'HAPTIC':         {'trig', 'sample', 'level', 'test_on', 'test_level',
                       'click_hz', 'click_tau_ms', 'click_peak',
                       'click_end_db', 'tone_hz'},
}

# Types that legitimately have no SPI address
NO_SPI_TYPES = {'INPUT_TDM', 'OUTPUT_TDM', 'INTERCHIP_RECV', 'INTERCHIP_SEND',
                'METER', 'TALKBACK', 'NOISE_GEN'}

# Optional param keys seen in practice, beyond REQUIRED_PARAMS, per node type.
# Anything outside REQUIRED_PARAMS | EXTRA_PARAMS for a type is flagged as an
# unrecognized param key rather than passed through silently.
EXTRA_PARAMS = {
    'AUX_INPUT':      {'level_db', 'on', 'scope'},
    'COMPRESSOR':     {'det_src', 'eq_pos', 'filter_hpf', 'filter_lpf',
                        'filter_on', 'filter_q', 'key', 'lim_mode',
                        'parallel', 'type'},
    'DELAY':          {'local_ms', 'pool_slot'},
    'EQ_BIQUAD':      {'coeffs'},
    # host_cells names the cell families the HOST owns outright — no DSP
    # address, no kernel read (PW ruling 2026-08-30: Dca, DcaOn).
    # `lcr_page`/`lcr_addr` (S25, PW ruling R5): the channel's `Chan*LcrOn`
    # word, and on channel 1's row `syslaw_page`/`syslaw_addr` for the one
    # `Sys[1-1]LcrLaw[1-1]` word the whole desk shares. They are OPTIONAL
    # for the same reason `mo_page` is: a graph without them is a graph
    # that does not carry LCR, and the generator emits the pre-R5 pan.
    'FADER_PAN':      {'pan', 'host_cells', 'lcr_page', 'lcr_addr',
                       'syslaw_page', 'syslaw_addr'},
    'FX_ENGINE':      {'balance', 'damping', 'decay', 'delay_ms', 'duck_on',
                        'duck_sens', 'eq_hi', 'eq_lo', 'eq_mid', 'feedback',
                        'hpf', 'mix', 'mod_level', 'mod_rate',
                        'predelay_ms', 'room_size'},
    'GATE':           {'det_src', 'filter_hpf', 'filter_lpf', 'filter_on',
                        'filter_q', 'key'},
    'INPUT_TDM':      {'scope', 'signal', 'sport_slots'},
    'INTERCHIP_RECV': {'global_slot', 'scope', 'signal', 'sport_slots'},
    'INTERCHIP_SEND': {'global_slot', 'scope', 'signal', 'sport_slots'},
    # `comp_gr_src` (S23 gate 4): the COMPRESSOR whose gain word this meter
    # publishes as `Chan*CompMtr` at SPI base+3. A meter declaring a
    # `comp_gr` tap without it is refused by dsp_codegen.py rather than
    # having the compressor id guessed from the meter's own.
    'METER':          {'taps', 'comp_gr_src'},
    # `fx_sends` / `aux` (S23 gate 3): a chip-2 summing bus whose LAST
    # fx_sends sources are crosspoints -- an on/off flag and a ramped send
    # level folded into one Q4.28 coefficient at block rate -- rather than
    # fixed unity feeds. `aux` names which aux bus the node sums, and it is
    # what gen_dsp.py addresses the Fx*AuxOn/AuxSend cells from; a node with
    # fx_sends and no aux is refused there rather than guessed at.
    'MIX_BUS':        {'source_count', 'fx_sends', 'aux'},
    'MONITOR':        {'level_l_db', 'level_r_db'},
    'NOISE_GEN':      {'hpf_on'},
    'TEST_OSC':       {'sweep_on', 'sweep_step', 'meas_src'},
    'TEST_MEAS':      {'xtalk_src', 'xtalk_dst'},
    # `mo_page`/`mo_addr` (S24): the main output strip's own Level and Mute.
    # A SECOND address block, for the same reason ROUTING's `mtx_*` is one --
    # the node has a single word of its own and growing it would have moved
    # every chip-2 address above it. Present on the four post-crossover main
    # outputs and on no other OUTPUT_TDM node, which is exactly the marker
    # gen_dsp.py::expand_output_tdm and dsp_codegen.py::gen_output_tdm key
    # on: no `mo_page`, no cells, no arithmetic, byte-identical emitted text.
    #
    # `sink` (S102): the PHYSICAL thing this output's slots reach on the
    # product that scopes the node, where the lane's signal name does not
    # say it. The same shape as TALKBACK's `invert_opt` -- one output's
    # wiring, not a property of the type -- and it exists because SP1 spent
    # three sessions reading as "no route to the speaker" when the route was
    # there under another name: `C2_MON_OUT` slot 0 is `CODEC_OUT_1`, which
    # is the AK4619's AOUT1L (pin 22), which is the D24 panel speaker feed.
    # No generator reads it; it is a declaration, so that a search of the
    # topology for the speaker finds the slot that is the speaker.
    'OUTPUT_TDM':     {'scope', 'signal', 'sink', 'sport_slots',
                       'mo_page', 'mo_addr'},
    # `mtx_*` (S22 gate 1): the matrix sends and the SPI block they live in.
    # `mtx_page`/`mtx_addr` are a SECOND address block for one node -- the
    # only one in the graph -- because growing the 60-word routing block
    # would have moved every chip-1 address above it. gen_dsp.py refuses
    # `mtx_sends` without them rather than guessing an address.
    'ROUTING':        {'fx_on', 'mtx_on', 'mtx_sends', 'mtx_page',
                       'mtx_addr'},
    # `invert_opt` (S71): the name of a build flag whose 1 negates the
    # node's input sample. Carried on the talkback XLR instance only --
    # the inversion is one input's wiring (J1 hot on the codec's IN4N),
    # not a property of the TALKBACK type.
    'TALKBACK':       {'hpf_on', 'invert_opt'},
    'TUBE_SAT':       {'on'},
    'HAPTIC':         {'scope'},
}

ALLOWED_PARAMS = {t: REQUIRED_PARAMS.get(t, set()) | EXTRA_PARAMS.get(t, set())
                   for t in VALID_TYPES}


# ---------------------------------------------------------------------------
# THE SPEAKER SLOT (S122)
# ---------------------------------------------------------------------------
# PW ruling 2026-09-26: "the spkr feed is for screen button haptics only, and
# should be completely separate from all mixer signal paths." The D24 panel
# speaker is the AK4619's AOUT1L -- `CODEC_OUT_1`, the ONE codec DAC output
# fitted (S102) -- and until S122 the MONITOR bus wrote it, so the graph's own
# default left the speaker playing the main mix.
SPEAKER_SOURCE_TYPES = {'HAPTIC'}


def check_speaker_slot(rows):
    """Every slot a `sink=SPKR` output writes is fed by a HAPTIC node and by
    nothing else. Returns a list of formatted error strings (never raises):
    the caller folds them into its own error list so one run reports every
    violation rather than the first."""
    out = []
    parsed = []
    for r in rows:
        parsed.append(((r.get('id') or '').strip(),
                       (r.get('type') or '').strip(),
                       parse_params(r.get('params', '')),
                       parse_id_list(r.get('inputs', ''))))
    by_id = {nid: (ntype, prm, inp) for nid, ntype, prm, inp in parsed}

    spk = [(nid, prm, inp) for nid, ntype, prm, inp in parsed
           if ntype == 'OUTPUT_TDM' and prm.get('sink') == 'SPKR']
    if not spk:
        # NOT AN ERROR HERE, and deliberately so: this validator is run on
        # fragments and on graphs that are not a D24's, and a graph with no
        # speaker has nothing to separate. That the SHIPPING graph declares
        # one is asserted where the shipping graph is built --
        # gen_dsp_csv.py, at the bottom of the file -- which is the only
        # place that can tell "no speaker" from "the speaker went missing".
        return out
    if len(spk) > 1:
        out.append('  [speaker slot]: %d nodes declare sink=SPKR (%s). '
                   'The speaker has one feed.'
                   % (len(spk), ', '.join(n for n, _, _ in spk)))

    ok_types = '/'.join(sorted(SPEAKER_SOURCE_TYPES))
    for nid, prm, inputs in spk:
        try:
            sport = int(prm.get('sport_id', '-1'))
            start = int(prm.get('slot_start', '-1'))
            count = int(prm.get('slot_count', '1'))
        except ValueError:
            out.append('  [speaker slot] %s: sport_id/slot_start/slot_count '
                       'are not integers' % nid)
            continue
        slots = set(range(start, start + count))

        # (a) WHO FEEDS IT
        if not inputs:
            out.append('  [speaker slot] %s: has no input. The panel speaker '
                       'must be fed by a %s node.' % (nid, ok_types))
        for src in inputs:
            styp, _, sinp = by_id.get(src, ('(undeclared)', {}, []))
            if styp not in SPEAKER_SOURCE_TYPES:
                out.append(
                    '  [speaker slot] %s is fed by %s, a %s node. PW ruling '
                    '2026-09-26: the panel speaker carries HAPTICS ONLY and '
                    'is separate from every mixer signal path -- only a %s '
                    'node may reach a sink=SPKR output. Give the speaker its '
                    'own source, or send %s to an output that is not the '
                    'speaker.' % (nid, src, styp, ok_types, src))
            # a source that is itself fed by something is the same defect
            # one hop further out: the speaker's source takes no input.
            for up in sinp:
                out.append(
                    '  [speaker slot] %s reaches the speaker through %s. The '
                    'speaker source takes NO input -- that is what makes the '
                    'separation checkable in one hop.' % (up, src))

        # (b) WHO ELSE IS ON THE SLOT
        for onid, otyp, oprm, _ in parsed:
            if onid == nid or otyp != 'OUTPUT_TDM':
                continue
            try:
                osport = int(oprm.get('sport_id', '-1'))
                ostart = int(oprm.get('slot_start', '-1'))
                ocount = int(oprm.get('slot_count', '1'))
            except ValueError:
                continue
            if osport != sport:
                continue
            clash = slots & set(range(ostart, ostart + ocount))
            if clash:
                out.append(
                    '  [speaker slot] %s writes SPORT%d slot(s) %s, which is '
                    "the panel speaker's (%s). No node but the haptic feed "
                    'may write it.' % (onid, sport, sorted(clash), nid))
    return out


def validate(csv_path):
    errors = []
    warnings = []

    def err(row_num, node_id, msg):
        errors.append(f"  Row {row_num} [{node_id}]: {msg}")

    def warn(row_num, node_id, msg):
        warnings.append(f"  Row {row_num} [{node_id}]: {msg}")

    # ── Read file ────────────────────────────────────────────────────────────
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            print("ERROR: CSV file is empty or unreadable")
            return 1
        columns = set(reader.fieldnames)
        rows = list(reader)

    # ── Check 1: Required columns ────────────────────────────────────────────
    missing_cols = REQUIRED_COLUMNS - columns
    if missing_cols:
        print(f"FATAL: Missing required columns: {sorted(missing_cols)}")
        return 1

    # ── Parse all rows ───────────────────────────────────────────────────────
    all_ids = set()
    spi_addresses = {}  # (chip, page, addr) → node_id
    duplicate_rows = set()  # row_num of rows rejected as duplicate IDs

    for row_num, row in enumerate(rows, start=2):  # row 1 = header
        nid = row['id'].strip()
        chip = row['chip'].strip()
        ntype = row['type'].strip()
        ramp = row['ramp_profile'].strip()
        ch_count_str = row['ch_count'].strip()
        spi_page_str = row['spi_page'].strip()
        spi_addr_str = row['spi_addr'].strip()
        params = parse_params(row.get('params', ''))
        inputs = parse_id_list(row.get('inputs', ''))
        outputs = parse_id_list(row.get('outputs', ''))

        # ── Check 2: ID non-empty and unique ────────────────────────────────
        if not nid:
            err(row_num, '(empty)', 'Node ID is empty')
            continue
        if nid in all_ids:
            err(row_num, nid, f'Duplicate node ID')
            duplicate_rows.add(row_num)
            continue
        all_ids.add(nid)

        # ── Check 3: chip ───────────────────────────────────────────────────
        if chip not in ('1', '2'):
            err(row_num, nid, f'Invalid chip value "{chip}" (must be 1 or 2)')

        # ── Check 4: type ───────────────────────────────────────────────────
        if ntype not in VALID_TYPES:
            err(row_num, nid, f'Unknown node type "{ntype}"')

        # ── Check 5: ramp_profile ───────────────────────────────────────────
        if ramp not in VALID_RAMP_PROFILES:
            err(row_num, nid, f'Unknown ramp_profile "{ramp}"')

        # ── Check 6: ch_count ───────────────────────────────────────────────
        try:
            ch_count = int(ch_count_str)
            if ch_count < 1:
                err(row_num, nid, f'ch_count must be >= 1 (got {ch_count})')
        except ValueError:
            err(row_num, nid, f'ch_count is not an integer: "{ch_count_str}"')

        # ── Check 7: spi_page / spi_addr ────────────────────────────────────
        try:
            spi_page = int(spi_page_str)
        except ValueError:
            err(row_num, nid, f'spi_page is not an integer: "{spi_page_str}"')
            spi_page = None
        try:
            spi_addr = int(spi_addr_str)
        except ValueError:
            err(row_num, nid, f'spi_addr is not an integer: "{spi_addr_str}"')
            spi_addr = None

        has_valid_spi = spi_page is not None and spi_addr is not None and spi_page >= 0 and spi_addr >= 0

        if not has_valid_spi and ntype not in NO_SPI_TYPES:
            warn(row_num, nid, f'No SPI address (page={spi_page_str}, addr={spi_addr_str}) for type {ntype}')

        # ── Check 8: SPI address uniqueness ─────────────────────────────────
        if has_valid_spi and chip in ('1', '2'):
            key = (chip, spi_page, spi_addr)
            if key in spi_addresses:
                err(row_num, nid,
                    f'SPI address collision: chip={chip} page={spi_page} addr={spi_addr} '
                    f'already used by {spi_addresses[key]}')
            else:
                spi_addresses[key] = nid

        # ── Check 10: Required + recognized params ──────────────────────────
        required = REQUIRED_PARAMS.get(ntype, set())
        missing_params = required - set(params.keys())
        if missing_params:
            err(row_num, nid, f'Missing required params for {ntype}: {sorted(missing_params)}')
        allowed = ALLOWED_PARAMS.get(ntype, required)
        unknown_params = set(params.keys()) - allowed
        if unknown_params:
            err(row_num, nid, f'Unrecognized params for {ntype}: {sorted(unknown_params)}')

    # ── Check 9: input/output references ────────────────────────────────────
    # Re-iterate to validate references (all IDs now known)
    for row_num, row in enumerate(rows, start=2):
        if row_num in duplicate_rows:
            continue
        nid = row['id'].strip()
        inputs = parse_id_list(row.get('inputs', ''))
        outputs = parse_id_list(row.get('outputs', ''))
        for ref in inputs:
            if ref not in all_ids:
                err(row_num, nid, f'Input reference "{ref}" does not exist')
        for ref in outputs:
            if ref not in all_ids:
                err(row_num, nid, f'Output reference "{ref}" does not exist')

    # ── Check 11: process order / acyclicity, per chip ───────────────────────
    # Resolved from the graph, never from an emitted call order. A node
    # that reads a same-chip node appearing LATER in dsp.csv gets its
    # input one sample stale unless the generator reorders the chain --
    # which it now does (dsp_codegen.repair_process_order). A CYCLE it
    # cannot reorder away, and that is an error here.
    order_notes = []
    for chip in ('1', '2'):
        chip_rows = [r for r in rows if (r.get('chip') or '').strip() == chip]
        ids = [(r.get('id') or '').strip() for r in chip_rows]
        pos = {nid: i for i, nid in enumerate(ids)}
        edges = {}
        for i, r in enumerate(chip_rows):
            nid = ids[i]
            srcs = [x for x in parse_id_list(r.get('inputs', '')) if x in pos]
            edges[nid] = srcs
            for src in srcs:
                if pos[src] > i:
                    order_notes.append(
                        f'  chip {chip}: {nid} (row {i}) reads {src} '
                        f'(row {pos[src]}), which appears later — the '
                        f'generator moves {src} ahead of it')
        # DFS cycle detection (white/grey/black)
        state = {}

        def _visit(n, stack):
            state[n] = 1
            for m in edges.get(n, ()):
                if state.get(m) == 1:
                    cyc = stack[stack.index(m):] + [m] if m in stack else [m, n]
                    err(0, n, f'chip {chip}: CYCLE in the node graph: '
                              f'{" -> ".join(cyc)}. A cycle is a one-sample '
                              f'feedback path; it must be declared '
                              f'deliberately, not left for the chain order '
                              f'to resolve')
                    state[m] = 2
                elif state.get(m, 0) == 0:
                    _visit(m, stack + [m])
            state[n] = 2

        sys.setrecursionlimit(max(2000, len(ids) * 4))
        for nid in ids:
            if state.get(nid, 0) == 0:
                _visit(nid, [nid])

    # ── Check 12: THE SPEAKER SLOT BELONGS TO THE HAPTIC NODE ──────────
    #
    # PW ruling 2026-09-26 (S122): "the spkr feed is for screen button
    # haptics only, and should be completely separate from all mixer signal
    # paths." That is a property of the GRAPH, so it is checked on the
    # graph, and it fails rather than relying on anyone remembering it. The
    # same rule is enforced a second time, inside
    # dsp_codegen.py::_speaker_slot_guard, on the node set that actually
    # becomes the TX lane table -- two instruments, one declaration.
    #
    # THE DECLARATION IS `sink=SPKR` (S102) and nothing else. Which slot the
    # speaker is on is READ OFF IT, never typed here, so moving the speaker
    # to another slot moves this check with it.
    errors.extend(check_speaker_slot(rows))

    # ── Report ───────────────────────────────────────────────────────────────
    print(f"Validated {len(rows)} nodes in {os.path.basename(csv_path)}")

    if order_notes:
        print(f"\n  {len(order_notes)} process-order note(s) "
              f"(repaired by the generator, not errors):")
        for n in order_notes:
            print(n)
    else:
        print("  process order: every node's same-chip inputs already "
              "precede it in dsp.csv")

    if warnings:
        print(f"\n  {len(warnings)} warning(s):")
        for w in warnings:
            print(w)

    if errors:
        print(f"\n  {len(errors)} error(s):")
        for e in errors:
            print(e)
        return 1

    print(f"  OK — no errors{f', {len(warnings)} warning(s)' if warnings else ''}")
    return 0


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(script_dir, '..', 'dsp.csv')
    sys.exit(validate(csv_path))
