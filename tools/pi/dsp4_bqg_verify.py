#!/usr/bin/env python3
"""dsp4_bqg_verify.py — the headroom guard, read off the part.

src/lib/bq_guard_test.asm runs lib/bq_headroom.asm end to end for each
worst-case cascade and then runs that cascade TWICE over the matched-sign
drive -- once with the header the sizer wrote and once with it forced to
zero, which is the kernel that landed on 2026-09-03 -- counting the
samples whose sign differs from a float64 run of the same de-quantised
coefficients.

Three verdicts, and the first two are the ones that could fail:

    H, part vs model      lib/bq_headroom.asm against tools/dsp/bq_h_load.py
    GUARDED words         the whole guarded stream, hashed, against the
                          model -- counting sign inversions proves the
                          wrap is gone, not that the right words replaced
                          it
    GUARDED inversions    must be ZERO on every cascade
    UNGUARDED inversions  must be what the model predicts, and NON-ZERO
                          on the hot ones -- a bar that only asserted the
                          guarded arm would pass on a rig that never drove
                          anything hard enough to wrap

Usage (staged by bqguard.sh):
    dsp4_bqg_verify.py <chip1.sym.json> <bqg_vectors.json>
"""

import json
import sys
import time

SYMS = json.load(open(sys.argv[1]))
REF = json.load(open(sys.argv[2]))

sys.argv = ['p']
# The PACED, VOTED reader, for dsp4_bqe_verify.py's reason: the DSP
# services this link once per audio block, an unpaced reader out-runs it
# and then returns a well-formed WRONG answer.
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


def peek(a):
    last, agree = None, 0
    for _ in range(36):
        try:
            v = sc.peek(a)
        except (IOError, SystemExit):
            last, agree = None, 0
            continue
        if v == 0xFFFFFFFF:          # how this link answers a dropped read
            last, agree = None, 0
            continue
        if v == last:
            agree += 1
            if agree >= 1:
                return v
        else:
            last, agree = v, 0
    return None


def rd(name, off=0):
    a = SYMS.get(name)
    if a is None:
        print(f'  symbol {name} is not in the image')
        sys.exit(2)
    v = peek(a + off)
    if v is None:
        print(f'  LINK FAILED reading {name}+{off}')
        sys.exit(2)
    return v


done = rd('_bqg_done')
if done != 1:
    print(f'  _bqg_done = {done} -- the guard pass did not finish')
    sys.exit(3)

fail = rd('_bqg_fail')
ncas = rd('_bqg_ncas')
nsamp = rd('_bqg_nsamp')

cases = REF['cases']
print(f'  headroom guard on the part: {ncas} cascades x {nsamp} samples of '
      f'matched-sign drive at 0 dBFS')
if fail:
    print(f'  ENGINE STALL: the sizer never finished cascade {fail} '
          f'({cases[fail - 1]["name"]})')
    sys.exit(1)
if ncas != len(cases):
    print(f'  the image holds {ncas} cascades and the reference has '
          f'{len(cases)} -- vectors and image disagree')
    sys.exit(2)

hdr = (f'  {"cascade":32s} {"st":>2s} {"H mdl":>5s} {"H part":>6s} '
       f'{"inv guarded":>11s} {"inv unguarded":>13s} {"predicted":>9s}')
print(hdr)
print('  ' + '-' * (len(hdr) - 2))

bad = []
for i, c in enumerate(cases):
    hg = rd('_bqg_hgot', i)
    fg = rd('_bqg_fgd', i)
    fu = rd('_bqg_fun', i)
    flag = ''
    if hg != c['h_model']:
        bad.append(f'{c["name"]}: the part sized H = {hg}, the model says '
                   f'{c["h_model"]}')
        flag = '  <-- H'
    if fg != 0:
        bad.append(f'{c["name"]}: the GUARDED arm inverted sign on {fg} of '
                   f'{nsamp} samples; the guard exists to make that zero')
        flag += '  <-- GUARDED'
    if fu != c['n_unguarded']:
        bad.append(f'{c["name"]}: the UNGUARDED arm inverted sign on {fu} '
                   f'samples, the model predicts {c["n_unguarded"]}')
        flag += '  <-- UNGUARDED'
    print(f'  {c["name"]:32s} {c["stages"]:2d} {c["h_model"]:5d} {hg:6d} '
          f'{fg:11d} {fu:13d} {c["n_unguarded"]:9d}{flag}')

# ---- the words themselves, not just their signs ----
hgd, sgd = rd('_bqg_hgd'), rd('_bqg_sgd')
hun, sun = rd('_bqg_hun'), rd('_bqg_sun')
print()
print(f'  GUARDED   stream hash 0x{hgd:08X} sum 0x{sgd:08X}   model '
      f'0x{REF["hash_gd"]:08X}/0x{REF["sum_gd"]:08X}   '
      f'{"MATCH" if (hgd, sgd) == (REF["hash_gd"], REF["sum_gd"]) else "DIFFERS"}')
print(f'  UNGUARDED stream hash 0x{hun:08X} sum 0x{sun:08X}   model '
      f'0x{REF["hash_un"]:08X}/0x{REF["sum_un"]:08X}   '
      f'{"MATCH" if (hun, sun) == (REF["hash_un"], REF["sum_un"]) else "DIFFERS"}')
if (hgd, sgd) != (REF['hash_gd'], REF['sum_gd']):
    bad.append('the GUARDED arm is not the guarded MODEL, word for word')
if (hun, sun) != (REF['hash_un'], REF['sum_un']):
    bad.append('the UNGUARDED arm is not the round-once MODEL, word for word')

hot = [c for c in cases if c['n_unguarded'] > 0]
print(f'\n  {len(hot)} of {len(cases)} cascades invert sign UNGUARDED '
      f'({sum(c["n_unguarded"] for c in cases)} samples in all); '
      f'guarded, {sum(rd("_bqg_fgd", i) for i in range(len(cases)))}')
if not hot:
    print('  NO cascade wrapped in either arm -- this drive never reached '
          'the ceiling, so the bar proved nothing')
    sys.exit(1)

if bad:
    print('\n  FAIL:')
    for b in bad:
        print(f'    {b}')
    sys.exit(1)
print('\n  PASS — the part sizes the H its model sizes, the guarded arm '
      'never inverts sign, and the unguarded arm inverts it exactly where '
      'the model says it does')
sys.exit(0)
