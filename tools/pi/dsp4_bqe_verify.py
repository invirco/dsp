#!/usr/bin/env python3
"""dsp4_bqe_verify.py — the ROUND-ONCE cascade against fixed_ref, read off
the part.

src/lib/bqe_verify.asm runs the graph's cascade kernel and the round-once
cascade kernel over the same DEFS curve set inside the DSP, diffs them
on-chip, and reduces each arm's whole output stream to an order-sensitive
hash and a running 32-bit sum. This reads those back and scores them
against the reference tools/dsp/gen_bqe_vectors.py computed from
fixed_ref over the identical vectors.

Four verdicts:

    ARM A vs fixed_ref        the kernel the graph calls, against the model
    ARM B vs the round-once model
    A vs B, count             against the model's own prediction
    A vs B, WHICH cells       the divergence bitmap, exactly

The bitmap is the two-sided control and it is the reason this bar is not
just "assert zero". Built at DSP4_BQ_ROUNDONCE=0 arm A is the
per-stage-saturating contract and the two arms MUST diverge -- on the hot
cascades at 0 dBFS and nowhere else. Built at 1 arm A is the landed kernel
and the two arms must agree on every word. A bar that could only pass one
of those two ways would not be able to tell a kernel that wrapped
everywhere from one that never saturated at all.

THE FLOAT ARM (2026-09-03). With float the shipping cascade the same rig
asks the same question of `lib/biquad_fx.asm`'s float kernels, and the
reference is `tools/dsp/bq_float_ref.py` rather than fixed_ref:

    ARM A vs bq_float_ref on the float32 OFFSET wire   (the shipping one)
    ARM B vs bq_float_ref on the DIRECT-form wire      (the control)
    A vs B, count and WHICH cells

The bitmap is still the two-sided control and it is not degenerate: the
bypass cascades must AGREE to the bit and everything with a pole away
from the origin must DIFFER, so a reconstruction that quietly did nothing
fails as loudly as one that corrupted the identity filter.

Usage (staged by bqeverify.sh):
    dsp4_bqe_verify.py <chip1.sym.json> <bqe_vectors.json> <0|1 expected ro>
    dsp4_bqe_verify.py <chip1.sym.json> <bqe_vectors.json> float
"""

import json
import sys
import time

SYMS = json.load(open(sys.argv[1]))
REF = json.load(open(sys.argv[2]))
FLOAT_ARM = (sys.argv[3] == 'float')
WANT_RO = None if FLOAT_ARM else int(sys.argv[3])

sys.argv = ['p']
# The PACED, VOTED reader. dsp4_bq_verify.py's header carries the measured
# reason: the DSP services this link once per audio block, an unpaced
# reader out-runs it and then returns a well-formed WRONG answer.
import dsp4_scope as S

sc = S.Scope(1)
sc.d.resync()
for _attempt in range(6):
    try:
        sc.check_chip()
        break
    except SystemExit:
        if _attempt == 5:
            raise
        time.sleep(1.0)


def peek(a, allow_ff=False):
    """Only trust a value the link agrees with on independent reads.

    0xFFFFFFFF is how this link answers a DROPPED transaction, so every
    other reader in the tree throws it away. `_bqev_first` is -1 when
    nothing differed, which is the same word -- and throwing it away is
    exactly what made the landed arm read as a dead link on the first run
    of this bar. Where the value is legitimately -1 the vote is three
    agreeing reads instead of two, and ndiff is the cross-check: zero
    differences and a first index of -1 have to arrive together.
    """
    last, agree = None, 0
    need = 3 if allow_ff else 2
    for _ in range(36):
        try:
            v = sc.peek(a)
        except (IOError, SystemExit):
            last, agree = None, 0
            continue
        if v == 0xFFFFFFFF and not allow_ff:
            last, agree = None, 0
            continue
        if v == last:
            agree += 1
            if agree >= need - 1:
                return v
        else:
            last, agree = v, 0
    return None


def sg(v):
    return None if v is None else (v - (1 << 32) if v & 0x80000000 else v)


def rd(name, allow_ff=False):
    a = SYMS.get(name)
    if a is None:
        print(f'  symbol {name} is not in the image')
        sys.exit(2)
    v = peek(a, allow_ff)
    if v is None:
        print(f'  LINK FAILED reading {name}')
        sys.exit(2)
    return v


done = rd('_bqev_done')
if done != 1:
    print(f'  _bqev_done = {done} -- the verify pass did not finish')
    sys.exit(3)

ro = rd('_bqev_ro')
is_float = rd('_bqev_float')
ncas = rd('_bqev_ncas')
nlvl = rd('_bqev_nlvl')
nblk = rd('_bqev_nblk')
blk = rd('_bqev_blk')
nstage = rd('_bqev_nstage')
bmw = rd('_bqev_bmw')
nwords = rd('_bqev_nwords')
ndiff = rd('_bqev_ndiff')
maxdiff = rd('_bqev_maxdiff')
first = sg(rd('_bqev_first', allow_ff=True))
ha, sa = rd('_bqev_hash_a'), rd('_bqev_sum_a')
hb, sb = rd('_bqev_hash_b'), rd('_bqev_sum_b')
# THE BITMAP IS READ WITH allow_ff, and it is the same trap _bqev_first
# fell into: a bitmap word is 32 divergence bits, so an all-diverging word
# IS 0xFFFFFFFF, which is also how this link answers a dropped
# transaction. The fixed arm never came near it (29 of 576 cells); the
# float arm diverges on 566 of 576, so most of its words are 0xFFFFFFFF
# and the two-agreeing-reads vote threw every one of them away and read a
# healthy part as a dead link. Three agreeing reads instead.
base = SYMS['_bqev_bmap']
bmap = []
for i in range(bmw):
    v = peek(base + i, allow_ff=True)
    if v is None:
        print(f'  LINK FAILED reading _bqev_bmap[{i}]')
        sys.exit(2)
    bmap.append(v)

if FLOAT_ARM:
    print(f'  image: DSP4_BQ_FLOAT = {is_float}   (arm A is the shipping '
          f'float cascade on the OFFSET wire)')
else:
    print(f'  image: DSP4_BQ_ROUNDONCE = {ro}   (arm A is '
          f'{"round-once" if ro else "the per-stage-saturating contract"})')
print(f'  vectors: {ncas} cascades x {nstage} stages, {nlvl} levels x '
      f'{nblk} blocks x {blk} samples = {nwords} words/arm')

fail = []
if FLOAT_ARM:
    if not is_float:
        fail.append('image is DSP4_BQ_FLOAT=0, the bar was staged for the '
                    'FLOAT arm')
    if not REF.get('float'):
        fail.append('the vector set was not generated with --float')
else:
    if is_float:
        fail.append('image is DSP4_BQ_FLOAT=1, the bar was staged for the '
                    'FIXED arm')
    if ro != WANT_RO:
        fail.append(f'image is DSP4_BQ_ROUNDONCE={ro}, the bar was staged '
                    f'for {WANT_RO}')
for k, got, want in (('ncas', ncas, REF['ncas']), ('nstage', nstage,
                     REF['nstage']), ('nlvl', nlvl, REF['nlvl']),
                     ('nblk', nblk, REF['nblk']), ('block', blk,
                     REF['block']), ('nwords', nwords, REF['nwords'])):
    if got != want:
        fail.append(f'{k}: part {got}, reference {want} -- the image and the '
                    f'reference are not the same vector set')
if fail:
    for f in fail:
        print(f'  FAIL: {f}')
    sys.exit(1)

# ---- arm A against its model -------------------------------------------
MODEL = 'bq_float_ref' if FLOAT_ARM else 'fixed_ref'
if FLOAT_ARM:
    want_a = ('offset wire', REF['hash_a'], REF['sum_a'])
    want_b = ('direct wire', REF['hash_b'], REF['sum_b'])
    name_b = '_bqfd_cascade_simd'
else:
    want_a = ('roundonce', REF['hash_b'], REF['sum_b']) if ro else \
             ('contract', REF['hash_a'], REF['sum_a'])
    want_b = ('round-once', REF['hash_b'], REF['sum_b'])
    name_b = '_bqe_cascade_simd'
okA = (ha == want_a[1] and sa == want_a[2])
print(f'  ARM A  _bq_fx_cascade_simd  hash 0x{ha:08X} sum 0x{sa:08X}   '
      f'vs {MODEL} {want_a[0]} 0x{want_a[1]:08X}/0x{want_a[2]:08X}   '
      f'{"MATCH" if okA else "MISMATCH"}')

okB = (hb == want_b[1] and sb == want_b[2])
print(f'  ARM B  {name_b:20s}hash 0x{hb:08X} sum 0x{sb:08X}   '
      f'vs {MODEL} {want_b[0]} 0x{want_b[1]:08X}/0x{want_b[2]:08X}   '
      f'{"MATCH" if okB else "MISMATCH"}')

# ---- A vs B ------------------------------------------------------------
if FLOAT_ARM:
    exp_ndiff, exp_first = REF['ndiff'], REF['first']
    exp_max, exp_bmap = REF['maxdiff'], REF['bmap']
else:
    exp_ndiff = 0 if ro else REF['ndiff']
    exp_first = -1 if ro else REF['first']
    exp_max = 0 if ro else REF['maxdiff']
    exp_bmap = [0] * bmw if ro else REF['bmap']
okD = (ndiff == exp_ndiff and first == exp_first)
okM = (maxdiff == exp_max)
okBM = (bmap == exp_bmap)
pct = 100.0 * ndiff / nwords if nwords else 0.0
print(f'  A vs B: {ndiff} of {nwords} words differ ({pct:.3f}%), '
      f'first at {first}, max |d| {maxdiff}')
print(f'          model predicts {exp_ndiff} differing, first at {exp_first},'
      f' max |d| {exp_max}   {"MATCH" if (okD and okM) else "MISMATCH"}')
ncell = sum(bin(w).count('1') for w in bmap)
nexp = sum(bin(w).count('1') for w in exp_bmap)
print(f'          divergence bitmap: part {ncell} of {ncas * nlvl} cells, '
      f'model {nexp}   {"MATCH" if okBM else "MISMATCH"}')
if not okBM:
    for i in range(bmw):
        if bmap[i] != exp_bmap[i]:
            print(f'            word {i}: part 0x{bmap[i]:08X} '
                  f'model 0x{exp_bmap[i]:08X}')

ok = okA and okB and okD and okM and okBM
print()
if ok:
    if FLOAT_ARM:
        print('  BQE_VERIFY PASS — the SHIPPING FLOAT cascade kernel computes '
              'bq_float_ref\'s words on')
        print('  the part, 0 ULP over the whole vector set, and the offset '
              'reconstruction is live:')
        print(f'  it agrees with the direct wire on the bypass cascades and '
              f'differs on {nexp} of {ncas * nlvl} cells, exactly the ones '
              f'the model names')
    else:
        print('  BQE_VERIFY PASS — the round-once cascade kernel IS the '
              'round-once model, over the whole vector set')
        if ro:
            print('  and the landed kernel is bit-identical to the validated '
                  'round-once arm on every word')
        else:
            print('  and it is 0-ULP identical to the CONTRACT except on the '
                  f'{nexp} (cascade, level) cells fixed_ref says overflow')
else:
    print('  BQE_VERIFY FAIL')
sys.exit(0 if ok else 1)
