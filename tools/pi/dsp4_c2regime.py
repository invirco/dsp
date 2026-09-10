#!/usr/bin/env python3
"""dsp4_c2regime.py -- what chip 2's graph is DOING on this boot (S17-6).

S17 filed, and did not explain, a chip-2 D24 cost that is boot-dependent by
ten points on one image, one product and one measured clock: 92.88 % with
zero overruns on one boot and 102.83 % with 2.49 % of blocks missed on two
others, `_proc_passes` tracking the shortfall exactly. A capacity number that
moves ten points with nothing changed is not a number, and the only way to
turn it into one is to read what differs BETWEEN THE BOOTS rather than to
argue about it.

So this reads, once per boot and after the same dwell the capacity run uses,
every chip-2 word that can put a per-block kernel on a different branch:

  * the three cascade classes' CROSSFADE state -- `_eq_*`, `_geq_*`,
    `_afb_*` `active` / `swap_pending` / `start_xfade` / `xfade_alpha`.
    A cascade mid-crossfade runs BOTH coefficient sets and blends, so a
    node stuck in a crossfade is a node costing twice its steady cost.
  * the dynamics ENGAGEMENT words -- `_comp_on`, `_gate_on`, `_lim_on`,
    `_afb_on`, `_afb_ctrl_on`, `_comp_filter_on`, `_gate_filter_on`, and
    the envelopes they run on -- because above and below threshold are
    different branches at the compiled defaults.
  * the FX engines' `_fx_on` / `_fx_bypassed` / `_fx_duck_on`.
  * the two mask words, which decide how much of the graph runs at all.
  * `_fdr_level_C2_AUX_FDR_01`, which is SPI address 0x0000 and therefore
    the word D71's CFG_COMMIT header lands in on roughly one boot in three.

Every word is read with Scope.rd()'s paced/voted path, and the whole set is
written as JSON so two boots can be diffed by machine rather than by eye.

Usage:  python3 dsp4_c2regime.py --json regime.json [--chip 2]
"""
import argparse
import json
import re
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

# Families read in full, one word per node instance. Kept as prefixes rather
# than a hand-listed set so a generator that adds a node adds a column here.
FAMILIES = [
    '_eq_active', '_eq_swap_pending', '_eq_start_xfade', '_eq_xfade_alpha',
    '_geq_active', '_geq_swap_pending', '_geq_start_xfade', '_geq_xfade_alpha',
    '_afb_active', '_afb_swap_pending', '_afb_start_xfade', '_afb_xfade_alpha',
    '_afb_on', '_afb_ctrl_on',
    '_comp_on', '_comp_filter_on', '_comp_envelope',
    '_gate_on', '_gate_filter_on', '_gate_envelope',
    '_lim_on', '_lim_envelope',
    '_fx_on', '_fx_bypassed', '_fx_duck_on',
    # THE FX ENGINES' OWN STATE (S21). `_fx_on` says the engine is enabled
    # and `_fx_bypassed` says whether the Type it was given is one the class
    # implements -- neither says a sample ever reached it. These do:
    #   _fx_type          which algorithm, as the host left it
    #   _fx_rv_comb_wptrs the eight comb write pointers. They advance on
    #                     every sample the reverb runs, signal or not, so a
    #                     wptr away from zero proves the KERNEL RAN.
    #   _fx_rv_comb_lpfs  the comb bank's one-pole damping states. REPORTED,
    #                     NOT REQUIRED: `filt = damp*delayed + (1-damp)*prev`
    #                     is identically `prev` when `damp` is 0, and `damp`
    #                     is 0 at boot -- `_fx_damp_<nid>` is a `.var` with
    #                     no initialiser and no host had ever written
    #                     `Fx<n>Damp`. All eight stay at zero on a reverb
    #                     that is carrying full scale, which is why they are
    #                     not the signal witness (measured 2026-09-10).
    #   _fx_echo_wptr     the delay line's write pointer, which advances on
    #                     Types 0 and 2 whether or not there is signal, so it
    #                     proves the KERNEL RAN and not that it had input.
    #   _buf_             the word the engine publishes into the FX return.
    '_fx_type', '_fx_rv_comb_lpfs', '_fx_rv_comb_wptrs', '_fx_echo_wptr',
    '_fx_mix',
]
# THE REVERB'S OWN DELAY LINE, which is where the proof actually is: with
# audio playing, the Freeverb body writes `input + feedback*filtered` into
# every one of its eight comb lines on every sample, so the buffer fills with
# signal whatever the parameters are. Sampled at a spread of offsets rather
# than read whole -- it is 11,024 words an engine and every word is a paced
# read.
FX_COMB_BUF = '_fx_comb_buf_L_C2_FX_ENG_'
FX_COMB_PROBES = (0, 137, 401, 1013, 1557, 3175, 4666, 6088, 7365, 8721, 9909)
# The FX engines' published output. Named as a prefix of its own because
# `_buf_` is every node's output on both chips and reading all of them would
# make this tool a full graph dump.
FX_BUF = '_buf_C2_FX_ENG_'
SINGLES = ['_aux_mask_live', '_chan_mask_live', '_fdr_level_C2_AUX_FDR_01']

DIAG_FRAME_COUNT = 0xE004
DIAG_BLK_OVERRUN = 0xE00A
DIAG_BUILD_CFG = 0xE0EA
DIAG_BUILD_CFG2 = 0xE0EB
NODE_SUF = re.compile(r'_C\d_[A-Z0-9_]+$')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chip', type=int, default=2)
    ap.add_argument('--json')
    ap.add_argument('--tag', default='')
    ap.add_argument('--require-fx', action='store_true',
                    help='ALSO require the FX engines to be in the regime '
                         '(S21): every engine enabled, at the Type asked '
                         'for, not parked in the unimplemented-Type bypass, '
                         'and -- for the reverb -- with its comb bank live, '
                         'which is the only word that proves a sample '
                         'actually reached the plugin. --fx-type says which '
                         'algorithm the row is for.')
    ap.add_argument('--fx-type', type=int, default=None,
                    help='the Type --require-fx expects to find on all six '
                         'engines')
    ap.add_argument('--require-driven', action='store_true',
                    help='exit 1 unless EVERY dynamics envelope on this chip '
                         'is live. S19: a driven capacity row that was not '
                         'preceded by this check is a claim, not a '
                         'measurement -- the regime has to be proved on the '
                         'part before the row is taken, because the whole '
                         'reason the record needed redoing is that nobody '
                         'was checking which branch the graph was on.')
    a = ap.parse_args()

    sc = S.Scope(a.chip)
    sc.check_chip()

    names = []
    for fam in FAMILIES:
        names += sorted(k for k in sc.sym
                        if k.startswith(fam) and NODE_SUF.sub('', k) == fam)
    # The comb-filter states are an ARRAY per engine; the family walk above
    # matches only the base symbol, so the other seven words are added here.
    # One live word is enough to prove the bank ran, but reading all eight
    # separates "the reverb ran" from "one word happens to be non-zero".
    for fam in ('_fx_rv_comb_lpfs', '_fx_rv_comb_wptrs'):
        for k in sorted(k for k in sc.sym if NODE_SUF.sub('', k) == fam):
            names += ['%s+%d' % (k, i) for i in range(1, 8)]
    names += sorted(k for k in sc.sym if k.startswith(FX_BUF))
    for k in sorted(k for k in sc.sym if k.startswith(FX_COMB_BUF)):
        names += ['%s+%d' % (k, i) for i in FX_COMB_PROBES]
    names += [n for n in SINGLES if n in sc.sym]

    out, bad = {}, []
    t0 = time.time()
    for n in names:
        base, _, off = n.partition('+')
        try:
            out[n] = sc.peek(sc.addr(base) + (int(off) if off else 0))
        except IOError:
            bad.append(n)
    rec = {
        'tag': a.tag,
        'chip': a.chip,
        'read_s': round(time.time() - t0, 1),
        'n_read': len(out),
        'unreadable': bad,
        'diag': {},
        'words': out,
    }
    for nm, reg in (('frame_count', DIAG_FRAME_COUNT),
                    ('blk_overrun', DIAG_BLK_OVERRUN),
                    ('build_cfg', DIAG_BUILD_CFG),
                    ('build_cfg2', DIAG_BUILD_CFG2)):
        try:
            rec['diag'][nm] = sc.rd(reg)
        except IOError:
            rec['diag'][nm] = None

    # The one-line summary, so a boot can be classified from the console
    # without opening the JSON.
    def cnt(fam):
        return sum(1 for k, v in out.items()
                   if NODE_SUF.sub('', k) == fam and v not in (0, None))
    rec['summary'] = {f: cnt(f) for f in FAMILIES}
    print('chip %d  read %d words in %.1f s  unreadable %d'
          % (a.chip, len(out), rec['read_s'], len(bad)))
    for f in FAMILIES:
        tot = sum(1 for k in out if NODE_SUF.sub('', k) == f)
        print('  %-22s %2d/%2d non-zero' % (f, rec['summary'][f], tot))
    for n in SINGLES:
        if n in out:
            print('  %-22s 0x%08X' % (n, out[n]))
    print('  overruns %s / frames %s  cfg %s/%s'
          % (rec['diag']['blk_overrun'], rec['diag']['frame_count'],
             rec['diag']['build_cfg'], rec['diag']['build_cfg2']))
    if a.json:
        json.dump(rec, open(a.json, 'w'), indent=1)
        print('  -> %s' % a.json)

    if a.require_driven:
        # A MASKED NODE IS NOT A FAILED REGIME. On D24 the channel mask
        # skips strips 25-32 and the aux mask skips aux 9-12, so sixteen
        # chip-1 envelopes and four chip-2 ones are zero because the nodes
        # never ran -- which is the product being a D24, not the stimulus
        # failing to arrive. The masks are read off the part
        # (`_chan_mask_live` / `_aux_mask_live`, the words the graph itself
        # gates on) rather than inferred from the product name.
        chan_mask = out.get('_chan_mask_live')
        aux_mask = out.get('_aux_mask_live')

        def masked(name):
            m = re.search(r'_C\d_(?:AUX_)?[A-Z]+_?[A-Z]*_(\d+)$', name)
            if not m:
                return False
            n = int(m.group(1))
            if '_AUX_' in name:
                return aux_mask is not None and not (aux_mask >> (n - 1)) & 1
            if re.search(r'_C1_(GATE|COMP)_\d+$', name):
                return chan_mask is not None and not (chan_mask >> (n - 1)) & 1
            return False

        dead, skipped = [], []
        for fam in ('_comp_envelope', '_gate_envelope', '_lim_envelope'):
            for k, v in sorted(out.items()):
                if NODE_SUF.sub('', k) == fam and not v:
                    (skipped if masked(k) else dead).append(k)
        if skipped:
            print('  %d envelope(s) zero on MASKED nodes, not counted'
                  % len(skipped))
        live = sum(rec['summary'][f] for f in
                   ('_comp_envelope', '_gate_envelope', '_lim_envelope'))
        tot = live + len(dead)
        rec['regime'] = {'live': live, 'dead': dead, 'masked': skipped}
        if a.json:
            json.dump(rec, open(a.json, 'w'), indent=1)
        print('  DRIVEN REGIME: %d of %d dynamics envelopes live on chip %d'
              % (live, tot, a.chip))
        if dead:
            for k in dead[:12]:
                print('    SILENT: %s' % k)
            if len(dead) > 12:
                print('    ... and %d more' % (len(dead) - 12))
            return 1

    if a.require_fx:
        # WHICH TYPES ARE ALGORITHMS. The shipped graph declares
        # `type=Reverb` on all six engines, so every one of them is the
        # generator's `reverb` CLASS, which implements Types 0 (Echo),
        # 2 (Doubling) and 3 (Reverb) and parks 1, 4, 5 and 6 in an explicit
        # bypass. A row at a parked Type is a row for the bypass branch and
        # is reported as one -- it is not a failure of the instrument, and it
        # is not a measurement of that algorithm either.
        IMPLEMENTED = (0, 2, 3)
        eng = sorted(k for k in out if NODE_SUF.sub('', k) == '_fx_on')
        n_on = sum(1 for k in eng if out[k])
        types = {k.replace('_fx_on', '_fx_type'): None for k in eng}
        for k in list(types):
            types[k] = out.get(k)
        byp = {k: out[k] for k in out
               if NODE_SUF.sub('', k) == '_fx_bypassed' and out[k]}
        combs = {}
        for k, v in out.items():
            if k.startswith(FX_COMB_BUF):
                combs.setdefault(re.sub(r'\+\d+$', '', k), []).append(v)
        live_combs = sum(1 for v in combs.values() if any(v))
        lpfs = {}
        for k, v in out.items():
            if k.startswith('_fx_rv_comb_lpfs'):
                lpfs.setdefault(re.sub(r'\+\d+$', '', k), []).append(v)
        live_lpfs = sum(1 for v in lpfs.values() if any(v))
        wptrs = {}
        for k, v in out.items():
            if k.startswith('_fx_rv_comb_wptrs'):
                wptrs.setdefault(re.sub(r'\+\d+$', '', k), []).append(v)
        live_wptrs = sum(1 for v in wptrs.values() if any(v))
        pub = {k: v for k, v in out.items() if k.startswith(FX_BUF)}
        want = a.fx_type
        wrong = sorted(k for k, v in types.items()
                       if want is not None and v != want)
        rec['fx'] = {'engines': len(eng), 'on': n_on,
                     'types': types, 'bypassed': byp,
                     'comb_lines_live': live_combs,
                     'comb_lines': len(combs),
                     'comb_lpfs_live': live_lpfs, 'comb_lpfs': len(lpfs),
                     'comb_wptrs_live': live_wptrs, 'comb_wptrs': len(wptrs),
                     'published_nonzero': sum(1 for v in pub.values() if v),
                     'published': len(pub),
                     'want_type': want}
        if a.json:
            json.dump(rec, open(a.json, 'w'), indent=1)
        print('  FX REGIME: %d of %d engines on, Type %s, %d parked in the '
              'unimplemented-Type bypass, %d of %d comb delay lines carrying '
              'signal (%d of %d wptrs advanced, %d of %d damping states '
              'non-zero), %d of %d engines publishing non-zero'
              % (n_on, len(eng),
                 sorted(set(v for v in types.values() if v is not None)) or '?',
                 len(byp), live_combs, len(combs),
                 live_wptrs, len(wptrs), live_lpfs, len(lpfs),
                 rec['fx']['published_nonzero'], len(pub)))
        rc = 0
        if not eng:
            print('    NO FX ENGINES on chip %d -- --require-fx is a chip-2 '
                  'check' % a.chip)
        elif n_on != len(eng):
            print('    NOT ENGAGED: %d engine(s) have _fx_on = 0'
                  % (len(eng) - n_on))
            rc = 1
        if wrong:
            for k in wrong[:6]:
                print('    WRONG TYPE: %s = %s, wanted %s'
                      % (k, types[k], want))
            rc = 1
        if want in IMPLEMENTED and byp:
            for k in sorted(byp)[:6]:
                print('    PARKED: %s = %s (the dispatch found no algorithm '
                      'for that Type)' % (k, byp[k]))
            rc = 1
        if want == 3 and combs and live_combs != len(combs):
            print('    NO SIGNAL IN THE PLUGIN: %d of %d comb delay lines '
                  'read zero at every probe, so the reverb ran over silence'
                  % (len(combs) - live_combs, len(combs)))
            rc = 1
        if want == 3 and wptrs and live_wptrs != len(wptrs):
            print('    KERNEL DID NOT RUN: %d of %d comb write-pointer banks '
                  'are still at their initialisers'
                  % (len(wptrs) - live_wptrs, len(wptrs)))
            rc = 1
        if want == 3 and lpfs and not live_lpfs:
            print('    (all %d damping states zero -- Fx<n>Damp has never '
                  'been written on this boot, so damp = 0 makes the one-pole '
                  'an identity on its own state. Reported, not required.)'
                  % len(lpfs))
        if want is not None and want not in IMPLEMENTED:
            print('    Type %d is NOT IMPLEMENTED for the reverb class the '
                  'graph declares: %d of %d engines are parked in the '
                  'explicit bypass and this row prices the BYPASS.'
                  % (want, len(byp), len(eng)))
        if rc:
            return rc
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
