#!/usr/bin/env python3
"""dsp4_bq_verify.py — the biquad cascades against fixed_ref, ON THE PART.

bq_selftest.asm runs _bq_fx_cascade_N and _bq_fx_cascade_blk over
byte-identical data inside the DSP and diffs them against each other. That
proves the two asm forms AGREE; it cannot prove either of them is the
arithmetic the numeric spec names, because both arms are asm. Until this
existed the biquad -- the hottest kernel in the strip and the one the
offset-coefficient form and the error feedback both live in -- had no
asm-vs-MODEL instrument at all, while the mix accumulator and the
crossfade blend each had one (dsp4_num_verify.py).

It reads the self-test's own coefficients, stimulus and both result
buffers off the part and re-runs fixed_ref.biquad over the SAME words, so
the model is driven by what the part actually held rather than by a
transcription of it. Three verdicts:

    ref vs blk     the existing asm-vs-asm bar (must be 0 of 2*BLOCK)
    ref vs model   the per-sample cascade against fixed_ref
    blk vs model   the block/fused cascade against fixed_ref

This is the acceptance instrument for the halved-n1 encoding (PW ruling
2026-08-29, minimum EQ Q = 0.10): the kernel accumulates nh's product
twice into the exact 80-bit MRF and the model does the same, so the two
must agree to the bit, and a transcription error in either would show
here as a nonzero model diff while the asm-vs-asm diff stayed clean.

Usage (staged by bqst.sh):
    dsp4_bq_verify.py <chip1.sym.json> <block_size>
"""

import json
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fixed_ref as fr

SYMS = json.load(open(sys.argv[1]))
BLOCK = int(sys.argv[2])
N = 2 * BLOCK

sys.argv = ['p']
# THE PACED READER, NOT dsp4_diag's. This read the part through
# DiagLink until 2026-08-30 and could not answer it at all: five
# boot+config rounds in a row returned MAGIC 0 and `done = None` while
# dsp4_scope's paced, voted read got MAGIC 0xD5B40001, CHIP_ID 1 and a
# moving FRAME_COUNT off the same part seconds later, first try. That is
# the same defect session 5 took out of pairgraph_run.sh -- the DSP
# services this link once per audio block and the unpaced reader
# out-runs it, then returns a well-formed wrong answer -- and this bar
# had been failing on it. Confirmed not to be a firmware change: the
# tree from before that day's fixes fails the old reader identically.
import dsp4_scope as S

sc = S.Scope(1)
sc.d.resync()
# ONE FAILED READ IS NOT PROOF THE WRONG PART IS ON THE OTHER END. The
# link intermittently answers a read with nothing and check_chip reads
# that as "CHIP 0" -- six diag reads in front of six fresh processes did
# not clear it on 2026-08-30, and re-voting on the SAME Scope did, first
# try. Never SKIP the check: a Scope(1) answering as chip 2 makes every
# symbol address here wrong. Retry on the same object -- constructing a
# second one grabs the RDY GPIO while the first still holds it and fails
# with EBUSY, which looks like a dead part and is not.
for _attempt in range(6):
    try:
        sc.check_chip()
        break
    except SystemExit:
        if _attempt == 5:
            raise
        time.sleep(1.0)


def peek(a):
    """Only trust a value the link agrees with on two independent reads."""
    last = None
    for _ in range(24):
        try:
            v = sc.peek(a)
        except (IOError, SystemExit):
            last = None
            continue
        if v == 0xFFFFFFFF:
            last = None
            continue
        if v == last:
            return v
        last = v
    return None


def sg(v):
    return None if v is None else (v - (1 << 32) if v & 0x80000000 else v)


def block(base, n):
    out = []
    for i in range(n):
        v = peek(base + i)
        if v is None:
            print(f'LINK FAILED reading word {i} at 0x{base + i:x}')
            sys.exit(2)
        out.append(sg(v))
    return out


def trace():
    """Dump the paired-cascade trace, when the image carries it.

    Printed WHETHER OR NOT the self-test completed: a wedge is exactly
    when these words are worth reading, and every earlier report of this
    hang could say only that _bqst_done stayed 0.
    """
    names = [('_bqp_phase', 'bqp phase   (1 in .. 8 scattered)'),
             ('_bqs_phase', 'bqs phase   (1 in, 2 PEYEN, 3 loops done,'
                            ' 4 MODE1 back)'),
             ('_bqs_stages', 'bqs stages  (expect the stage count)'),
             ('_bqs_samps', 'bqs samples (expect stages x BLOCK)')]
    got = [(lbl, peek(SYMS[n])) for n, lbl in names if n in SYMS]
    for lbl, v in got:
        print(f'  {lbl:52} = {v}')
    faults = [('_fault_count', 'ILOPI CB7I SOVFI ILADI RINSEQI CB15I'),
              ('_fault_total', 'faults taken, total'),
              ('_fault_first', 'first vector index (-1 = none)')]
    if '_fault_count' in SYMS:
        c = [peek(SYMS['_fault_count'] + 2 * i) for i in range(6)]
        print(f'  {"fault counts  " + faults[0][1]:52} = {c}')
        for n, lbl in faults[1:]:
            print(f'  {lbl:52} = {sg(peek(SYMS[n]))}')


done = peek(SYMS['_bqst_done'])
print('done    =', done)
if '_bqs_phase' in SYMS or '_fault_count' in SYMS:
    print('trace:')
    trace()
if done != 1:
    print('SELF-TEST DID NOT COMPLETE -- nothing to verify')
    sys.exit(2)

coeffs = block(SYMS['_bqst_coeffs'], 10)
x = block(SYMS['_bqst_x'], N)
ref = block(SYMS['_bqst_ref'], N)
blk = block(SYMS['_bqst_blk'], N)

print('coeffs  =', ' '.join(f'{c & 0xFFFFFFFF:08X}' for c in coeffs))

# ---- the model: the same two-stage cascade over the same stimulus ----
st = [fr.biquad_state(), fr.biquad_state()]
model = []
for xv in x:
    y = xv
    for s in range(2):
        y = fr.biquad(y, tuple(coeffs[5 * s:5 * s + 5]), st[s])
    model.append(y)


def biquad_pre_ruling(x, coeffs, state):
    """THE NEGATIVE CONTROL: the pre-ruling arithmetic, which accumulated
    the stored n1 word ONCE. Reading today's halved words with it halves
    every n1 term, so it must DISAGREE with the part -- if it does not,
    the stimulus never exercised n1 and this whole comparison proved
    nothing about the encoding that was just landed."""
    b0, nh, n2, c1, c2 = coeffs
    x1, x2, y1, y2, efb = state
    acc = (b0 * (x - 2 * x1 + x2) + nh * x1 + n2 * x2 - c1 * y1 + c2 * y2)
    acc += (2 * y1 - y2) << fr.QB
    acc += efb
    y = fr.sat32(fr.rns(acc, fr.QB))
    state[4] = acc - (y << fr.QB)
    state[0], state[1] = x, x1
    state[2], state[3] = y, y1
    return y


st = [fr.biquad_state(), fr.biquad_state()]
negctl = []
for xv in x:
    y = xv
    for s_ in range(2):
        y = biquad_pre_ruling(y, tuple(coeffs[5 * s_:5 * s_ + 5]), st[s_])
    negctl.append(y)


def diff(a, b, name):
    idx = [i for i in range(N) if a[i] != b[i]]
    worst = max((abs(a[i] - b[i]) for i in idx), default=0)
    print(f'{name:16} ndiff = {len(idx):3} of {N}   maxdiff = {worst}'
          f'   first = {idx[0] if idx else -1}')
    return len(idx)


bad = 0
bad += diff(ref, blk, 'ref vs blk')
bad += diff(ref, model, 'ref vs MODEL')
bad += diff(blk, model, 'blk vs MODEL')
n_neg = diff(ref, negctl, 'ref vs NEGCTL')
if n_neg == 0:
    print('\nNEGATIVE CONTROL DID NOT FIRE: the single-accumulation model '
          'agrees with the part, so this stimulus never exercised n1 and '
          'the match above says nothing about the halved-n1 encoding.')
    bad += 1

if bad:
    print('\nfirst eight samples (asm ref / asm blk / model):')
    for i in range(min(8, N)):
        mark = '' if ref[i] == blk[i] == model[i] else '   <-- DIFFERS'
        print(f'  [{i:2}] {ref[i]:12} {blk[i]:12} {model[i]:12}{mark}')
    print('\nFAIL')
    sys.exit(1)

# ---- the PAIRED (SIMD) arm, when the image carries it ---------------
# _bq_pair_blk gathers two strips, runs _bq_fx_cascade_simd and scatters
# back; the self-test compares its result against the SCALAR result for
# the same two strips and leaves the count in _sq_pdiff. Nothing read
# that word until now, so the pair arm had a verdict inside the part and
# no way out of it -- which is how a fixed hang stayed on the record as
# unresolved for four sessions.
if '_sq_pdiff' in SYMS:
    pdiff = peek(SYMS['_sq_pdiff'])
    if pdiff is None:
        print('\nPAIR ARM: link failed reading _sq_pdiff')
        bad += 1
    else:
        pdiff = sg(pdiff)
        if pdiff < 0:
            print('\npair arm NOT BUILT (DSP4_SKIP_PAIR=1)')
        else:
            print(f'\npair vs scalar   ndiff = {pdiff}')
        if pdiff > 0:
            print('PAIR ARM FAILED: _bq_pair_blk does not reproduce the '
                  'scalar cascade')
            bad += 1
    if '_sq_raw' in SYMS:
        raw = block(SYMS['_sq_raw'], 5)
        s_ms, m_ms = raw[1] - raw[0], raw[3] - raw[2]
        print(f'pair timing      scalar {s_ms} ms   simd {m_ms} ms'
              + (f'   ({s_ms / m_ms:.2f}x)' if m_ms else ''))
    if bad:
        print('\nFAIL')
        sys.exit(1)

print('\nPASS — both asm cascades are bit-exact against fixed_ref')
