#!/usr/bin/env python3
"""s39_chain.py — walk strip 1's chain on a MAP-ANCHORED image.

Every reading here is peek(sym[name]) and that is only legitimate because
the map was generated from the same build as the .ldr that is booted
(see dsp4_s39_symcheck.py; on the previous pair it was not, and that is
what produced S38-3/S38-5/S38-6).

Under DSP4_BLOCK_KERNELS the strip does NOT run through `_buf_C1_IN_01`:
`_C1_IN_01_process` reads the SPORT DMA buffer straight into the shared
block pool, and every node after it reads and writes BLOCK-word slots of
that pool. So the chain is walked in the POOL, not in the per-node
scalars -- the scalars survive only as linkage and carry the LAST sample
of the block. Reading `_buf_C1_IN_01` and calling the chain dead, which
is what an injection into that scalar invites, measures a variable no
block kernel reads.

Pool layout is blk_pool.h: 0 chain A, 1 chain B, 2 fdr L, 3 fdr R,
4 tap trim, 5 tap EQ, 6 tap pre-fader, 7 tap post-fader; BLOCK words each.
"""
import sys, time, json, struct
_argv = list(sys.argv); sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

SYMDIR = _argv[1] if len(_argv) > 1 else '/home/app/s39'
BLOCK = 16
sc1 = S.Scope(1, symfile='%s/chip1.sym.json' % SYMDIR); sc1.d.resync(); sc1.check_chip()
sc2 = S.Scope(2, symfile='%s/chip2.sym.json' % SYMDIR); sc2.d.resync(); sc2.check_chip()

def q28(w):
    v = w - (1 << 32) if w & 0x80000000 else w
    return v / float(1 << 28)

def block(sc, base, n=BLOCK):
    out = []
    for i in range(n):
        try:
            out.append(sc.peek(base + i))
        except IOError:
            out.append(None)
    return out

def summarise(tag, vals, fmt=q28):
    got = [v for v in vals if v is not None]
    if not got:
        print('  %-26s UNREADABLE' % tag); return
    nz = [v for v in got if v not in (0, 0xFFFFFFFF)]
    conv = [fmt(v) for v in got]
    pk = max(abs(c) for c in conv)
    print('  %-26s %2d/%2d read, %2d non-zero, %2d distinct | peak %+.6f | %s'
          % (tag, len(got), len(vals), len(nz), len(set(got)), pk,
             ' '.join('%+.4f' % c for c in conv[:6])))

P = sc1.sym['_blk_pool']
SLOT = {'chainA (strip in)': 0, 'chainB (post GAIN)': 1,
        'fdr L': 2, 'fdr R': 3, 'tap post-trim': 4,
        'tap EQ': 5, 'tap pre-fader': 6, 'tap post-fader': 7}

print('=== chip 1: the shared block pool at 0x%05X (strip that ran last) ===' % P)
for name, s in SLOT.items():
    summarise(name, block(sc1, P + s * BLOCK))

print('\n=== chip 1: the SPORT RX DMA buffer -- the true converter input ===')
try:
    rxb = sc1.peek(sc1.sym['_rx_active_buf'])
    off = sc1.peek(sc1.sym['_c1_rx_off'])
    strd = sc1.peek(sc1.sym['_c1_rx_stride'])
    ent = sc1.peek(sc1.sym['_c1_rx_node_entry'])
    print('  _rx_active_buf 0x%05X  entry %d  off %d  stride %d' % (rxb, ent, off, strd))
    lane = [sc1.peek(rxb + off + i * strd) for i in range(BLOCK)]
    nz = [v for v in lane if v]
    print('  lane 1 raw (Q1.31): %s' % ' '.join('0x%08X' % v for v in lane[:8]))
    print('  lane 1: %d/%d non-zero, %d distinct' % (len(nz), len(lane), len(set(lane))))
    # sample it again -- a converter with a clock moves even on silence
    time.sleep(0.2)
    lane2 = [sc1.peek(rxb + off + i * strd) for i in range(BLOCK)]
    print('  lane 1 again      : %s' % ' '.join('0x%08X' % v for v in lane2[:8]))
    print('  MOVED between the two reads: %s'
          % ('YES' if lane != lane2 else 'no -- static'))
except (IOError, KeyError) as exc:
    print('  unreadable: %s' % exc)

print('\n=== chip 1: linkage scalars (LAST sample of the block) ===')
for n in ('_rx_slot_C1_IN_01', '_buf_C1_IN_01', '_buf_C1_GAIN_01',
          '_tap_post_trim_C1_GAIN_01', '_gain_coeff_C1_GAIN_01',
          '_gain_q_C1_GAIN_01', '_mute_C1_GAIN_01'):
    if n not in sc1.sym:
        print('  %-28s not in map' % n); continue
    try:
        v = sc1.peek(sc1.sym[n])
        print('  %-28s 0x%08X   (q28 %+.6f)' % (n, v, q28(v)))
    except IOError:
        print('  %-28s unreadable' % n)

print('\n=== chip 2: the bus accumulators ===')
for n in ('_bus_acc_aux_01', '_bus_acc_main_l', '_bus_acc_main_r'):
    if n not in sc2.sym:
        print('  %-20s not in map' % n); continue
    summarise(n, block(sc2, sc2.sym[n], 3))
