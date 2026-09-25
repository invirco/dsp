#!/usr/bin/env python3
"""dsp4_rxscan.py — DO THE TDM INPUT LANES CARRY ANYTHING? Read the RX DMA
region, which is the only place the answer lives.

*** WRITTEN 2026-09-20 (S86). THE TWO INSTRUMENTS BEFORE IT BOTH READ A
SYMBOL NOTHING WRITES, AND BOTH ANSWERED ANYWAY. ***

`dsp4_inscan.py` before S81 peeked `_rx_slot_C1_IN_nn`; S81 rewrote it onto
`_buf_C1_IN_nn` because "the block kernels actually write" those. They do not.
Under `DSP4_BLOCK_KERNELS`:

  * a node whose output is consumed by the next node in its own strip writes
    the shared BLOCK POOL (`BLK_CHAIN_A`), and its `_buf_<nid>` survives only
    as linkage and as the identity token `_scope_tap` / `_scope_inject_blk`
    compare `r0` against. Every `C1_IN_nn`, `C1_GAIN_nn`, `C1_EQ_nn` … is one
    of these: 398 of chip 1's 442 nodes;
  * only a node that is NOT a chain head -- the 15 `XIN_*` lanes and the 29
    bus nodes -- owns a real `_buf_<nid>[DSP4_BLOCK_SIZE]`.

So `_buf_C1_XIN_CODEC_01` is live and `_buf_C1_IN_01` is a scalar in a
zero-initialised section, and a scan that reads both prints "the codec lanes
move and the mic lanes are exact digital zero" on a card whose mic lanes are
perfectly healthy. That reading stood for five sessions (S81-8, S82, S83, S84,
S85) and was diagnosed as a converter fault, a bitstream fault, a launch-phase
fault and finally a SPORT receive fault. It was none of them. See S86.

WHAT THIS READS INSTEAD. `_rx_active_buf + off + k*stride`, with `off` and
`stride` taken from the part's own `_cN_rx_off` / `_cN_rx_stride` tables and
the node names from `_cN_rx_slot_ptrs` (the PATCHED pointer, so the name
printed is the node that consumes the lane on the booted product, not the
identity mapping). Nothing here is hardcoded from the tree: every number comes
off the part, so a stale idea in this file cannot outvote the image.

CONTROLS, all of which must come out right or no per-lane verdict is printed:
  MUST MOVE      FRAME_COUNT advances -- the block ISR is turning.
  MUST NOT MOVE  `_rx_slot_C<chip>_IN_01` -- a symbol nothing writes.
  MUST NOT MOVE  `_buf_C<chip>_IN_01`     -- the symbol that produced five
                 sessions of wrong diagnosis. It is read here every run, in
                 the same pass and through the same peek path as the lanes
                 beside it, so the trap is demonstrated rather than described.

WHAT "CARRYING SAMPLES" MEANS. A lane fed by a clocked converter varies
sample to sample with nothing plugged in -- the converter's own dither. A lane
with nothing driving it is a constant, and a stuck 0xFFFFFFFF is exactly as
dead as a stuck zero. So the verdict is on DISTINCT VALUES, not on non-zero.

DO NOT MAKE THE INTERVAL A ROUND NUMBER. The block rate is 3000/s and bench
stimuli run at rates that divide into it; S80 peeked every 20 ms -- exactly 60
blocks -- and reported a live lane STATIC by aliasing. The default is 13.7 ms.

    python3 dsp4_rxscan.py --symdir /home/app/s83tn
    python3 dsp4_rxscan.py --symdir . --reps 32 --json lanes.json
    python3 dsp4_rxscan.py --symdir . --laneid      decode the _laneid CPLD
                                                    bitstream's pin/slot marker
"""
import argparse
import json
import math
import os
import sys
import time

_argv = list(sys.argv)                 # BEFORE the import: dsp4_scope parses argv
sys.argv = ['s']
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S                                              # noqa: E402

FRAME_COUNT = 0xE004
INTERVAL = 0.0137

# ---- LANES WITH NO FITTED SOURCE: STATIC IS THE CORRECT READING ----
#
# S109. `0xFFFFFFFF` on a CPLD input pin nobody drives, and `0x00000000` on
# one the CPLD ties to a constant, are both "no source", not "dead lane" --
# and this tool used to print STATIC beside them in the same column it uses
# for a converter that has stopped, so every scan since S79 has carried a
# handful of standing faults that were never faults. They are named here so
# the verdict says so, and so the "n of m CARRYING" tally is taken over the
# entries that HAVE a source. A lane in this table that starts CARRYING is
# the interesting case and is called out rather than quietly passed.
#
# This is a bench tool and runs from /home/app with no repo beside it, so
# the table is explicit rather than read out of slot-map.csv. Keep it in
# step with shared/dsp4-logic/slot-map.csv + tdm-lines.csv.
NO_SOURCE = {}
for _n in range(25, 33):
    NO_SOURCE['IN_%02d' % _n] = (
        'A_I3 is the NET lane (ni[3], pin 3) and option slot 1 is empty; '
        'there is no AD3 converter on this board')
for _n in range(1, 9):
    NO_SOURCE['XIN_SNK_%02d' % _n] = (
        'D32 snake return. D32 is out of requirements (PW 2026-09-25): '
        'pin 109 is unassigned and LOGIC ties i_dspa[5] to 0')
NO_SOURCE['XIN_CODEC_03'] = (
    'AK4619 ADC2 Lch (IN3) is not connected on rev C and has no consumer')


def s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def dbfs31(v):
    """RX lanes are 24-in-32 left-justified: full scale is 2**31."""
    a = abs(v) / float(1 << 31)
    return -336.0 if a <= 0 else 20.0 * math.log10(a)


def lane_groups(entries):
    """Group RX table entries into lanes from their own geometry.

    Within one lane the entries occupy consecutive words base..base+stride-1
    and share a stride, so a new lane starts wherever the offset is not the
    previous one plus one, or the stride changes. The group index is the DSPA
    pin when the generated lane table has no unused pin -- which is true of
    every chip-1 image in this tree -- and is reported as `lane` rather than
    `pin` so a future sparse table cannot make this a silent lie.
    """
    out, lane, prev = [], -1, None
    for off, stride in entries:
        if prev is None or off != prev[0] + 1 or stride != prev[1]:
            lane += 1
            base = off
        out.append((lane, off - base))
        prev = (off, stride)
    return out


def scan(sc, reps=16, laneid=False, chip=1, log=print):
    """Read every RX table entry out of the DMA region. Returns (rows, meta)."""
    sym = sc.sym
    pre = '_c%d_rx_' % chip

    def pk(addr, patience=40):
        for _ in range(6):
            try:
                return sc.peek(addr, patience)
            except IOError:
                time.sleep(0.02)
                try:
                    sc.d.resync()
                except Exception:
                    pass
        return None

    count = pk(sym[pre + 'slot_count'])
    if not count:
        raise SystemExit('dsp4_rxscan: %sslot_count unreadable — nothing scanned'
                         % pre)
    off_b, str_b = sym[pre + 'off'], sym[pre + 'stride']
    ptr_b, buf_p = sym[pre + 'slot_ptrs'], sym['_rx_active_buf']
    # Only the RX slot symbols, so a var that happens to share an address
    # cannot lend its name to a lane. `_cN_rx_slot_ptrs[i]` always points at
    # one of these.
    rxpre = '_rx_slot_C%d_' % chip
    byaddr = {}
    for k, v in sym.items():
        if k.startswith(rxpre):
            byaddr.setdefault(int(v), k)

    geom = []
    for i in range(count):
        geom.append((pk(off_b + i), pk(str_b + i)))
    if any(o is None or s is None for o, s in geom):
        raise SystemExit('dsp4_rxscan: the RX geometry tables did not read')
    groups = lane_groups(geom)

    fc0 = sc.d.read(FRAME_COUNT)

    controls = {}
    for cname in ('_rx_slot_C%d_IN_01' % chip, '_buf_C%d_IN_01' % chip):
        if cname in sym:
            vs = []
            for _ in range(min(reps, 12)):
                v = pk(sym[cname])
                if v is not None:
                    vs.append(v & 0xFFFFFFFF)
                time.sleep(INTERVAL)
            controls[cname] = vs

    rows = []
    for i in range(count):
        off, stride = geom[i]
        lane, slot_k = groups[i]
        ptr = pk(ptr_b + i)
        node = byaddr.get(ptr, '?')
        if node.startswith('_rx_slot_C%d_' % chip):
            node = node[len('_rx_slot_C%d_' % chip):]
        words = []
        for n in range(reps):
            b = pk(buf_p)
            if b is None:
                continue
            v = pk(b + off + (n % 16) * stride)
            if v is not None:
                words.append(v & 0xFFFFFFFF)
        r = {'entry': i, 'off': off, 'stride': stride, 'lane': lane,
             'lane_slot': slot_k, 'node': node, 'read': len(words),
             'words': ['%08x' % w for w in words[:8]]}
        r['no_source'] = NO_SOURCE.get(node)
        if words:
            sv = [s32(w) for w in words]
            rms = math.sqrt(sum((x / 2.0 ** 31) ** 2 for x in sv) / len(sv))
            r.update({'distinct': len(set(words)),
                      'rms_dbfs': round(20 * math.log10(rms) if rms > 0 else -336.0, 2),
                      'peak_dbfs': round(max(dbfs31(x) for x in sv), 2),
                      'carrying': len(set(words)) > 1})
            if laneid:
                # {8'hA5, pin[3:0], tick, slot[2:0]} in the top 16 bits. Read
                # straight from DMA there is no Q1.31 -> Q4.28 shift to undo
                # (that is the node kernel's `ashift by -3`, and it is where
                # S85-7's uniform three-bit offset came from); a lane framed
                # MFD 1 against an MFD 2 build still lands one bit out, so the
                # window is walked and the offset is reported with the mark.
                marks = set()
                for w in words:
                    for sh in range(-4, 5):
                        t = ((w << sh) if sh >= 0 else (w >> -sh)) & 0xFFFFFFFF
                        if t >> 24 == 0xA5:
                            marks.add(((t >> 20) & 0xF, (t >> 16) & 0x7, sh))
                r['marks'] = sorted(marks)
        rows.append(r)

    fc1 = sc.d.read(FRAME_COUNT)
    meta = {'chip': chip, 'count': count,
            'frame_count_delta': (fc1 - fc0) & 0xFFFFFFFF,
            'controls': {k: {'reads': len(v), 'distinct': len(set(v)),
                             'value': ('0x%08X' % v[0]) if v else None}
                         for k, v in controls.items()}}
    return rows, meta


def verdict(meta, log=print):
    """Print the controls and refuse a per-lane verdict unless they pass."""
    ok = bool(meta['frame_count_delta'])
    log('  control MUST MOVE      FRAME_COUNT +%d  [%s]'
        % (meta['frame_count_delta'],
           'ok' if ok else 'FAILED — the block loop is not turning'))
    for cname, c in meta['controls'].items():
        good = c['distinct'] == 1
        log('  control MUST NOT MOVE  %-22s %d reads, %d distinct, %s  [%s]'
            % (cname, c['reads'], c['distinct'], c['value'],
               'ok' if good else 'FAILED — the peek path is noisy'))
        ok = ok and good
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chip', type=int, default=1)
    ap.add_argument('--symdir', default='.')
    ap.add_argument('--reps', type=int, default=16)
    ap.add_argument('--tag', default='')
    ap.add_argument('--json', default=None)
    ap.add_argument('--laneid', action='store_true')
    a = ap.parse_args(_argv[1:])

    sp = os.path.join(a.symdir, 'chip%d.sym.json' % a.chip)
    sc = S.Scope(a.chip, symfile=sp)
    sc.d.resync()
    sc.check_chip()
    print('symbol map: %s (%d symbols)  tag=%s'
          % (os.path.abspath(sp), len(sc.sym), a.tag))

    rows, meta = scan(sc, reps=a.reps, laneid=a.laneid, chip=a.chip)
    print()
    if not verdict(meta):
        raise SystemExit('controls failed: no per-lane verdict is takeable')

    print()
    # `lidx` is the entry's index WITHIN its lane, not the TDM slot number:
    # the two coincide only when the lane's channel-select mask is contiguous
    # from slot 0. The `--laneid` marker prints the real slot.
    print('%-14s %5s %5s %5s %5s %5s %8s %9s %9s  %s'
          % ('node', 'entry', 'off', 'lane', 'lidx', 'read', 'distinct',
             'rms dBFS', 'pk dBFS', 'first words'))
    for r in rows:
        if not r.get('read'):
            print('%-14s %5d  UNREAD' % (r['node'], r['entry']))
            continue
        if r['no_source']:
            mark = ('CARRYING (!! an unsourced lane should not move)'
                    if r['carrying'] else 'static, NO SOURCE — expected')
        else:
            mark = 'CARRYING' if r['carrying'] else 'STATIC'
        print('%-14s %5d %5d %5d %5d %5d %8d %9.2f %9.2f  %s  %s'
              % (r['node'], r['entry'], r['off'], r['lane'], r['lane_slot'],
                 r['read'], r['distinct'], r['rms_dbfs'], r['peak_dbfs'],
                 ' '.join(r['words'][:3]), mark))
        if a.laneid:
            print('%-14s %5s marks (pin, slot, bit offset): %s'
                  % ('', '', r.get('marks')))

    scored = [r for r in rows if not r.get('no_source')]
    unsourced = [r for r in rows if r.get('no_source')]
    live = [r for r in scored if r.get('carrying')]
    print('\n%d of %d SCORED RX entries CARRYING SAMPLES'
          % (len(live), len(scored)))
    if unsourced:
        print('%d further entries have NO FITTED SOURCE and are not scored:'
              % len(unsourced))
        seen = set()
        for r in unsourced:
            if r['no_source'] in seen:
                continue
            seen.add(r['no_source'])
            names = [q['node'] for q in unsourced
                     if q['no_source'] == r['no_source']]
            print('   %s: %s' % (', '.join(names), r['no_source']))
        odd = [r['node'] for r in unsourced if r.get('carrying')]
        if odd:
            print('   !! CARRYING anyway, which needs explaining: %s'
                  % ', '.join(odd))
    if a.json:
        json.dump({'tag': a.tag, 'meta': meta, 'lanes': rows},
                  open(a.json, 'w'), indent=1)
        print('wrote %s' % a.json)


if __name__ == '__main__':
    main()
