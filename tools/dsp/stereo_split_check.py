#!/usr/bin/env python3
"""stereo_split_check.py — the desk gate S142-1 did not have.

WHAT IT IS FOR
--------------
On 2026-09-28 the chip-2 main bus was found to be MONO from the master
fader onward: `C2_MAIN_FDR` declared `inputs = C2_MIX_MAIN_L;C2_MIX_MAIN_R`
and `ch_count = 2`, the generator read `inputs[0]`, and so both MAIN XLRs,
both DAC MAIN slots, the codec aux out and the monitor carried the LEFT
bus. `_blk_C2_MIX_MAIN_R` was computed every block by a mix bus with
seventeen sources and read by nothing at all (finding S142-1).

Nothing in the tree could see it. `dsp_validate.py` checked the ROW;
`check-sharc-codegen-drift.sh` checked that the emitted tree matched its
own generator; the golden harness checked arithmetic. None of them asked
the one question that would have caught it: **does the code that was
emitted actually read what the graph says it reads, and does the right
half of a stereo output stay on the right half?**

This script asks it, in two gates:

  GATE A — EVERY DECLARED INPUT REACHES AN INSTRUCTION.
      For every node, every id in its dsp.csv `inputs` must appear as
      `_blk_<id>` or `_buf_<id>` in the assembly that was emitted for it
      (its own node file, or the per-chip generated file that runs it: a
      SIMD pair driver, the block-io tables, the chain). An input that
      reaches no instruction is computed every block and thrown away, and
      that is exactly the defect.

      ONE EXEMPTION, stated rather than blanket: a CHIP-1 MIX_BUS gathers
      its thirty-two per-strip sources through the routing fabric's
      POINTER TABLES (`rtg_fabric.asm`, DSP4_RTG_FABRIC), so those sources
      are never named in any body. The exemption is checked, not assumed:
      the fabric's own table must carry a row per (strip, bus).

  GATE A2 — EVERY EMITTED READ IS DECLARED.
      The other direction, and it is what makes gate B a proof about the
      CODE rather than about the spreadsheet: if the emitted bodies read
      exactly what dsp.csv declares and nothing else, then reachability
      computed on dsp.csv is reachability in the image.

  GATE B — A ONE-SIDED OUTPUT STAYS ONE-SIDED.
      Colour chip 2 by reachability from `C2_MIX_MAIN_L` and from
      `C2_MIX_MAIN_R` over the SIGNAL edges, and check every chip-2 sink
      against a DECLARED expectation with a reason. Reachability is the
      exact statement a numeric run can only sample: a sink the left bus
      cannot reach carries exactly zero of a hard-left signal, at every
      level, on every block. The numeric companion is
      `dsp_simulate.py --stereo-proof`, which drives the same claim
      through the audio model.

      A `link_in=` EDGE IS NOT A SIGNAL EDGE, and the distinction is the
      whole of the stereo-link design. The left output's GAIN depends on
      the right channel's envelope -- that is what "linked, not
      duplicated" means and it is why the image does not walk under
      compression -- but no right-channel SAMPLE is added to the left
      output. `out = dry_L * gain(max(|L|,|R|))` is exactly zero whenever
      `dry_L` is, whatever the gain does. So the detector edges are
      excluded from the cone and reported separately, by name, rather
      than left to make every main output read "both".

Usage:
  python3 tools/dsp/stereo_split_check.py [--csv PATH] [--src DIR] [-v]
  python3 tools/dsp/stereo_split_check.py --negative-control
        # prove the gates fire: re-run gate A against a graph in which one
        # declared input has been taken away from the code that reads it

Exit: 0 pass, 1 fail, 2 usage/environment error.
"""

import argparse
import csv
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DEF_CSV = os.path.join(REPO_ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'dsp.csv')
DEF_SRC = os.path.join(REPO_ROOT, 'MW', 'D32', 'DSP', 'SHARC', 'src')

sys.path.insert(0, SCRIPT_DIR)
from csv_fields import parse_id_list, parse_params

# A reference to another node's audio, as the emitted assembly spells it.
#
# `_blk_` is the per-block array and `_buf_` the scalar the per-sample
# build publishes. `_mtr_wide_`/`_mtr_wblk_` are the WIDE-WORD meter tap
# (PW ruling 2026-08-29): a METER reads its source in the meter's own
# Q8.24 format and never touches `_blk_`, so leaving them out would make
# every meter in the graph look like it read nothing. `_tap_*_` are the
# named pick-off points a meter or a router reads instead of the node's
# output.
#
# TWO CLASSES, and the difference decides what has to be declared.
# An AUDIO form carries the node's output; a PICK-OFF form is one of the
# named alternate tap points inside a strip (`Chan*AuxPick` chooses
# between post-trim, post-EQ, pre-fader and post-fader) or a dynamics
# gain word a meter publishes. A pick-off is a real edge and it is
# checked -- it just does not have to appear in `inputs`, because the
# chain's order is already fixed by the strip it lives in.
_AUDIO_FORMS = ('blk', 'buf', 'mtr_wide', 'mtr_wblk')
_TAP_FORMS = ('tap_post_fader', 'tap_post_eq', 'tap_pre_fader',
              'tap_post_trim', 'gate_gr', 'comp_gain')
_REF_FORMS = _AUDIO_FORMS + _TAP_FORMS
_REF_RE = re.compile(r'_(?:%s)_([A-Z][A-Z0-9_]*)\b'
                     % '|'.join(_REF_FORMS))
_AUDIO_RE = re.compile(r'_(?:%s)_([A-Z][A-Z0-9_]*)\b'
                       % '|'.join(_AUDIO_FORMS))
_REF_ONE = r'_(?:%s)_%%s\b' % '|'.join(_REF_FORMS)

# `C1_EQ_07` -> ('C1', '07'): a node's chip and strip instance, for the
# same-strip rule on pick-off edges.
_STRIP_RE = re.compile(r'^(C\d)_[A-Z]+_(\d+)$')


def _same_strip(a, b):
    ma, mb = _STRIP_RE.match(a), _STRIP_RE.match(b)
    return bool(ma and mb and ma.groups() == mb.groups())

# Where a node's reads may live besides its own file.
#
# NARROW, AND IT HAS TO BE. Letting a read count from anywhere in the
# emitted chip would defeat the gate outright: `process_chain.asm` names
# `_blk_<nid>` for every node it calls (the scope tap), and
# `block_io.asm` names every block that crosses the fabric -- so a node
# whose own body reads NOTHING would still look satisfied. That is not a
# hypothetical: run this script against the tree at `ce3a9d4b` with a
# chip-wide blob and `C2_MAIN_FDR`'s unread `C2_MIX_MAIN_R` passes.
#
# So the default is the node's OWN body, and exactly two families
# delegate, each for a stated reason:
#   METER  -- the per-strip meter kernels are SHARED (DSP4_SHARED_KERNELS)
#             and `shared_kernels.asm` holds the tap reads;
#   chip-1 MIX_BUS -- gathered by pointer through the routing fabric, see
#             _RTG_SRC_RE below (and check_rtg_exemption, which proves the
#             fabric really covers them).
_DELEGATED_FILES = {
    'METER': ('shared_kernels.asm', 'dyn_pairs.asm', 'bq_pairs.asm'),
}

# THE ONE EXEMPTION (see the header). A chip-1 MIX_BUS's per-strip sources
# are gathered by pointer, never by name.
_RTG_SRC_RE = re.compile(r'^C1_RTG_\d+$')

# ---------------------------------------------------------------------------
# KNOWN, RECORDED, NOT FIXED HERE.
#
# A gate that has to be green to be useful, and a defect that is real, are
# not the same thing -- so a known instance is carried HERE, by (consumer,
# producer) and with the finding that owns it, instead of being widened out
# of the rule. Each entry is a defect this gate found and a later dispatch
# owns; removing one is how it gets closed.
#
# S143-1 — THE CHANNEL METER'S SECOND INPUT REACHES NOTHING. Every
# `C1_MTR_nn` declares `inputs = C1_GAIN_nn;C1_FDR_nn` and
# `taps = post_trim;post_fader;gate_gr;comp_gr`, and `gen_meter_fixed`
# reads `inputs_str` -- `C1_GAIN_nn`, post-trim -- and nothing else. The
# `post_fader` tap is not a second SOURCE at all: it maps to meter word +1
# (`Chan[1-32]Mtr002`, gen_dsp.py's tap table), which is the true RMS of
# the SAME post-trim wide word. So the fader's own meter cell does not
# follow the fader, and `C1_FDR_nn` is computed every block and read by
# nothing -- S142-1's shape, on thirty-two more nodes. Found by this gate
# on 2026-09-28 and recorded rather than improvised: whether `Mtr002` is
# meant to be post-fader is a contract question (the master's Notes), and
# a meter that changes what it measures is a bench reading, not a desk
# edit. It is chip 1, which S143 does not touch.
_KNOWN_UNREAD = [
    (re.compile(r'^C1_MTR_(\d+)$'), re.compile(r'^C1_FDR_(\d+)$'),
     'S143-1: the channel meter reads its post-TRIM source only; the '
     '`post_fader` tap is meter word +1 (true RMS of the same word), not '
     'a second source. Recorded 2026-09-28, chip 1, not S143\'s build.'),
]


def known_unread(consumer, producer):
    for cre, pre, why in _KNOWN_UNREAD:
        mc, mp = cre.match(consumer), pre.match(producer)
        if mc and mp and mc.groups() == mp.groups():
            return why
    return None


# ---------------------------------------------------------------------------
# GATE B's expectations. WHICH SIDE EVERY CHIP-2 SINK IS ON, AND WHY.
#
# 'L' / 'R'  reachable from that main mix and NOT from the other
# 'both'     reachable from both (a genuine mono sum, or a mono bus)
# 'none'     reachable from neither main mix
#
# Stated here rather than derived, because "what the graph does" is what
# was wrong: a derived expectation would have agreed with the mono bus.
# Every entry carries the reason a reader would otherwise have to go and
# find, and a sink missing from this table fails the gate.
# ---------------------------------------------------------------------------
_SIDE_EXPECT = {
    'C2_MAIN_OUT_01': ('L', 'MainL XLR — DAC_12, J56 (hardware-map).'),
    'C2_MAIN_OUT_02': ('R', 'MainR XLR — DAC_11, J57. This is the reading '
                            'S142-1 was about: before S143 it carried LEFT.'),
    # S144 built item 1, so main outputs 3 and 4 are gone and the Centre/LF
    # XLR is here instead.
    'C2_OUT3_OUT': ('both', 'The ONE Centre/LF XLR — DAC_14, J55 (PW ruling '
                            'D6). BOTH is the correct answer and it is the '
                            'Woof half that gives it: `C2_WOOF_MIX` is the '
                            'mono sum of `C2_MAIN_DLY` and `C2_MAIN_DLY_R`, '
                            'so a hard-panned strip reaches this socket '
                            'from either side — which is what a mono sub '
                            'of L+R means. The Centre half reaches it from '
                            'neither: `C2_CTR_*` is fed from the Ctr '
                            'Channel Bus (`Chan*CtrOn` summed on chip 1), '
                            'not from the main mix. Which half is audible '
                            'is `Main Out3Mode`, a coefficient, so the cone '
                            'is the union of the two by construction.'),
    'C2_MAIN_ST_OUT': ('L', 'DAC MAIN L (SPORT3 slot 0).'),
    'C2_MAIN_ST_OUT_R': ('R', 'DAC MAIN R (SPORT3 slot 1) — a slot that '
                              'was chip-select enabled and never written '
                              'until S143.'),
    'C2_CODEC_AUX_OUT': ('L', 'CODEC_OUT_3 (D24, DNP).'),
    'C2_CODEC_AUX_OUT_R': ('R', 'CODEC_OUT_4 (D24, DNP) — the other half '
                                'of the same unwritten pair.'),
    'C2_MON_DLY': ('L', 'Monitor L. The chain ends here: a D24 has no '
                        'connector for the monitor bus yet (S122). The '
                        'phones/monitor outputs are S142 §3.3 item 2.'),
    'C2_MON_DLY_R': ('R', 'Monitor R — `Mon Level[2]` had no reader at all '
                          'before S143.'),
    'C2_SPKR_OUT': ('none', 'The panel speaker carries HAPTICS ONLY and '
                            'nothing else may reach it (PW ruling '
                            '2026-09-26; both speaker-slot guards enforce '
                            'it independently).'),

}
# Whole families, matched after the exact table.
_SIDE_EXPECT_RE = [
    (re.compile(r'^C2_AUX_OUT_\d+$'),
     ('none', 'An aux output carries its own aux bus, which is summed on '
              'chip 1 from the channel sends — not from the main mix.')),
    (re.compile(r'^C2_MTX_OUT_\d+$'),
     ('none', 'A matrix output carries its own matrix bus. (Every Matrix '
              'cell is gone from D24 generation 46109e9fb812; the nodes '
              'stay for D32.)')),
    (re.compile(r'^C2_MTR_'),
     ('any', 'A meter is a sink with no audio consumer; which side it '
             'reads is the side of the thing it meters.')),
]


def side_expectation(nid):
    if nid in _SIDE_EXPECT:
        return _SIDE_EXPECT[nid]
    for pat, exp in _SIDE_EXPECT_RE:
        if pat.match(nid):
            return exp
    return None


# ---------------------------------------------------------------------------

def load_rows(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def read_text(path):
    try:
        with open(path, encoding='utf-8') as f:
            return f.read()
    except OSError:
        return ''


def gather_sources(src_dir):
    """Per chip: the node files, and the delegated files per type."""
    blobs = {}
    node_text = {}
    for chip in ('chip1', 'chip2'):
        d = os.path.join(src_dir, chip)
        blobs[chip] = {
            t: '\n'.join(read_text(os.path.join(d, f)) for f in files)
            for t, files in _DELEGATED_FILES.items()
        }
        nd = os.path.join(d, 'nodes')
        if os.path.isdir(nd):
            for fn in os.listdir(nd):
                if fn.endswith('.asm'):
                    node_text[fn[:-4]] = read_text(os.path.join(nd, fn))
    return blobs, node_text


def gate_a(rows, blobs, node_text, ids, verbose):
    """Every declared input reaches an instruction. Returns error list."""
    errs = []
    exempt = 0
    checked = 0
    known = []
    for r in rows:
        nid = r['id'].strip()
        chip = 'chip1' if r['chip'].strip() == '1' else 'chip2'
        body = node_text.get(nid)
        if body is None:
            continue                      # no node file (nothing emitted)
        hay = body + blobs[chip].get(r['type'].strip(), '')
        for src in parse_id_list(r.get('inputs', '')):
            if src == nid or src not in ids:
                continue
            if (r['type'].strip() == 'MIX_BUS' and chip == 'chip1'
                    and _RTG_SRC_RE.match(src)):
                exempt += 1
                continue
            why = known_unread(nid, src)
            if why is not None:
                known.append((nid, src, why))
                continue
            checked += 1
            if not re.search(_REF_ONE % re.escape(src), hay):
                errs.append(
                    f'{nid} ({r["type"].strip()}) declares input {src} and '
                    f'no emitted instruction reads _blk_{src}, _buf_{src} '
                    f'or any named tap of it. '
                    f'That input is computed every block and read by '
                    f'nothing — the S142-1 shape.')
    if verbose:
        print(f'  gate A: {checked} declared input edges verified in the '
              f'emitted code, {exempt} gathered by the routing fabric\'s '
              f'pointer tables (chip-1 MIX_BUS).')
    if known:
        print(f'  gate A: {len(known)} KNOWN unread edge(s), recorded and '
              f'not fixed here:')
        for why in sorted({w for _, _, w in known}):
            n = sum(1 for _, _, w in known if w == why)
            print(f'    {n} x {why}')
    return errs, checked, exempt


def check_rtg_exemption(rows, blobs, verbose):
    """The fabric really does gather what gate A exempted."""
    errs = []
    n_strip = sum(1 for r in rows if _RTG_SRC_RE.match(r['id'].strip()))
    fab = read_text(os.path.join(DEF_SRC, 'rtg_fabric.asm'))
    m = re.search(r'RTG_STRIPS?\D+(\d+)', fab)
    declared = int(m.group(1)) if m else None
    if declared is not None and declared != n_strip:
        errs.append(
            f'the routing fabric declares {declared} strips and the graph '
            f'has {n_strip} C1_RTG_* nodes: gate A exempts a chip-1 '
            f'MIX_BUS\'s per-strip sources because the fabric gathers them, '
            f'so the two counts have to agree.')
    elif verbose:
        print(f'  gate A exemption: the routing fabric covers all '
              f'{n_strip} C1_RTG_* strips.')
    return errs


def emitted_reads(rows, node_text, ids):
    """node -> the ids its OWN emitted body reads as audio."""
    out = {}
    for r in rows:
        nid = r['id'].strip()
        body = node_text.get(nid)
        if body is None:
            continue
        audio, taps = set(), set()
        for m in _AUDIO_RE.finditer(body):
            if m.group(1) in ids and m.group(1) != nid:
                audio.add(m.group(1))
        for m in _REF_RE.finditer(body):
            src = m.group(1)
            if src in ids and src != nid and src not in audio:
                taps.add(src)
        out[nid] = (audio, taps)
    return out


def gate_a2(rows, reads, verbose):
    """Every emitted read is a declared input. Returns error list.

    THE OTHER DIRECTION, and it is what licenses gate B. Reachability is
    computed on dsp.csv; it is a statement about the IMAGE only if the
    emitted bodies read exactly what dsp.csv says they read. A body that
    reaches a node the row does not name is a hidden edge, and a hidden
    edge into the right main bus is how a "one-sided" output would stop
    being one without anything saying so.
    """
    errs = []
    n = ntap = 0
    for r in rows:
        nid = r['id'].strip()
        if nid not in reads:
            continue
        # DECLARED means named on the row, in `inputs` OR in a param that
        # names a node. A meter's `comp_gr_src` (S23 gate 4) and a
        # dynamics node's `link_in` (S143) are reads of another node that
        # are deliberately NOT audio inputs -- the first is a gain word,
        # the second a detector -- so they belong on the row but not in
        # the chain's input list. What matters here is only that the edge
        # is written down somewhere the reader can find it.
        declared = {s for s in parse_id_list(r.get('inputs', ''))
                    if s != nid}
        for v in parse_params(r.get('params', '')).values():
            for tok in str(v).split(';'):
                tok = tok.strip()
                if tok and tok != nid:
                    declared.add(tok)
        audio, taps = reads[nid]
        n += len(audio)
        for src in sorted(audio - declared):
            errs.append(
                f'{nid} reads an OUTPUT of {src} and the row does not name '
                f'{src} anywhere. An undeclared audio edge is invisible to '
                f'the process-order repair, to dsp_validate and to gate B.')
        for src in sorted(taps - declared):
            ntap += 1
            if not _same_strip(nid, src):
                errs.append(
                    f'{nid} reads a NAMED TAP of {src} ({src} is not in the '
                    f'same strip and the row does not name it). A pick-off '
                    f'across strips is an edge the chain order does not '
                    f'guarantee; declare it.')
    if verbose:
        print(f'  gate A2: {n} emitted audio read(s), all declared; '
              f'{ntap} in-strip pick-off read(s).')
    return errs


def build_signal_edges(rows, ids):
    """consumer -> set(producers) over SIGNAL edges only.

    Taken from dsp.csv, which gate A has just proved is what the code
    does. `link_in=` is dropped: it is a DETECTOR input, it modulates a
    gain and adds no sample (see the header).
    """
    edges = {}
    detectors = {}
    for r in rows:
        nid = r['id'].strip()
        link = parse_params(r.get('params', '')).get('link_in')
        srcs = {s for s in parse_id_list(r.get('inputs', ''))
                if s in ids and s != nid}
        if link and link in srcs:
            srcs.discard(link)
            detectors[nid] = link
        edges[nid] = srcs
    return edges, detectors


def reachable_from(edges, roots, ids):
    """Every node whose value depends on any of `roots` (forward cone)."""
    fwd = {}
    for dst, srcs in edges.items():
        for s in srcs:
            fwd.setdefault(s, set()).add(dst)
    seen = set(roots) & ids
    stack = list(seen)
    while stack:
        n = stack.pop()
        for d in fwd.get(n, ()):
            if d not in seen:
                seen.add(d)
                stack.append(d)
    return seen


def gate_b(rows, edges, detectors, ids, verbose):
    errs = []
    left = reachable_from(edges, ['C2_MIX_MAIN_L'], ids)
    right = reachable_from(edges, ['C2_MIX_MAIN_R'], ids)

    # THE TRIPWIRE. S142-1 in one line: the right main mix computed and
    # read by nothing.
    if len(right) <= 1:
        errs.append(
            'C2_MIX_MAIN_R reaches NOTHING. That is S142-1 exactly: the '
            'right main bus is computed every block by a seventeen-source '
            'mix and discarded, and every main output carries LEFT.')

    sinks = [r['id'].strip() for r in rows
             if r['chip'].strip() == '2'
             and (r['type'].strip() in ('OUTPUT_TDM', 'METER')
                  or r['id'].strip() in _SIDE_EXPECT)]
    table = []
    for nid in sinks:
        got_l, got_r = nid in left, nid in right
        got = ('both' if got_l and got_r else
               'L' if got_l else 'R' if got_r else 'none')
        exp = side_expectation(nid)
        if exp is None:
            errs.append(
                f'{nid} is a chip-2 sink and _SIDE_EXPECT in '
                f'stereo_split_check.py does not say which side it should '
                f'be on. Say so (with the reason), or the gate is checking '
                f'nothing about it.')
            continue
        want, why = exp
        ok = (want == 'any') or (got == want)
        table.append((nid, want, got, ok, why))
        if not ok:
            errs.append(
                f'{nid}: expected {want}, the emitted graph gives {got}. '
                f'{why}')
    if verbose:
        print(f'  gate B: left cone {len(left)} nodes, right cone '
              f'{len(right)} nodes.')
        if detectors:
            print('    stereo-link detector edges (gain, not signal):')
            for d, s in sorted(detectors.items()):
                print(f'      {d} detects on max(|its own|, |{s}|)')
        for nid, want, got, ok, why in table:
            print(f'    {"OK " if ok else "BAD"} {nid:22s} want={want:4s} '
                  f'got={got}')
    return errs, left, right, table


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--csv', default=DEF_CSV)
    ap.add_argument('--src', default=DEF_SRC)
    ap.add_argument('-v', '--verbose', action='store_true')
    ap.add_argument('--negative-control', action='store_true',
                    help='prove gate A fires: delete one read from a copy '
                         'of one emitted body and require the failure')
    args = ap.parse_args()

    for p in (args.csv, args.src):
        if not os.path.exists(p):
            print(f'ERROR: missing {p}', file=sys.stderr)
            return 2

    rows = load_rows(args.csv)
    ids = {r['id'].strip() for r in rows}
    blobs, node_text = gather_sources(args.src)

    print('stereo split check')
    print(f'  graph: {args.csv} ({len(rows)} nodes)')
    print(f'  code:  {args.src} ({len(node_text)} node bodies)')

    if args.negative_control:
        # Take the right main mix away from the fader that reads it --
        # which is the pre-S143 tree in one edit -- and require gate A to
        # say so. A gate nobody has seen fail is not a gate.
        victim = 'C2_MAIN_FDR_R'
        if victim not in node_text:
            print(f'ERROR: {victim} is not in the emitted tree; the '
                  f'negative control needs the S143 graph', file=sys.stderr)
            return 2
        node_text[victim] = re.sub(r'_(?:blk|buf)_C2_MIX_MAIN_R\b',
                                   '_blk_SILENCE', node_text[victim])
        errs, _, _ = gate_a(rows, blobs, node_text, ids, args.verbose)
        hit = [e for e in errs if victim in e and 'C2_MIX_MAIN_R' in e]
        if not hit:
            print('NEGATIVE CONTROL FAILED: gate A did not fire when the '
                  'right main mix stopped being read.', file=sys.stderr)
            return 1
        print(f'  negative control: gate A fired as required')
        print(f'    {hit[0]}')
        return 0

    errs, checked, exempt = gate_a(rows, blobs, node_text, ids, args.verbose)
    errs += check_rtg_exemption(rows, blobs, args.verbose)
    errs += gate_a2(rows, emitted_reads(rows, node_text, ids), args.verbose)
    sig_edges, detectors = build_signal_edges(rows, ids)
    berrs, left, right, table = gate_b(rows, sig_edges, detectors, ids,
                                       args.verbose)
    errs += berrs

    if not args.verbose:
        print(f'  gate A: {checked} declared input edges read by the '
              f'emitted code ({exempt} fabric-gathered)')
        print(f'  gate B: {len(table)} chip-2 sinks checked; left cone '
              f'{len(left)}, right cone {len(right)}, '
              f'{len(detectors)} stereo-link detector edge(s)')
    if errs:
        print(f'\n{len(errs)} failure(s):')
        for e in errs:
            print(f'  {e}')
        return 1
    print('\nstereo split check passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
