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
    '_fdr_busy',
]
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
    names += [n for n in SINGLES if n in sc.sym]

    out, bad = {}, []
    t0 = time.time()
    for n in names:
        try:
            out[n] = sc.peek(sc.addr(n))
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
    return 0


if __name__ == '__main__':
    sys.exit(main() or 0)
