#!/usr/bin/env python3
"""dsp4_inscan.py <chip> [reps] — do the TDM input lanes carry anything?

*** REWRITTEN 2026-09-20 (S81, hub ruling Q6). THE PREVIOUS VERSION WAS VOID
ON EVERY BUILD THAT SHIPS, AND IT ANSWERED ANYWAY. ***

It peeked `_rx_slot_C<chip>_IN_NN`. Those symbols still EXIST in the map --
thirty-two of them on the current chip-1 image -- but under
`DSP4_BLOCK_KERNELS` nothing ever writes them, so every one reads a constant
zero whether the lane behind it is alive or dead. The tool then printed
`STATIC 1 distinct in 8 reads` twenty-four times and a tidy summary line, and
the standing bench recipe recommended it for exactly the question it could
not answer. S79 quoted it as evidence (S80-19 voids that part of S79-2).

An instrument that answers static zero on a build where it cannot work is
worse than no instrument, because it is believed. So this version does three
things the old one did not:

1. READS THE BLOCK SYMBOLS -- `_buf_C<chip>_IN_*` and `_buf_C<chip>_XIN_*`,
   which the block kernels actually write -- and REFUSES to run at all if it
   cannot find them, instead of skipping silently and reporting on nothing.

2. RUNS A MUST-MOVE CONTROL FIRST. FRAME_COUNT (0xE004) is incremented by the
   block ISR. If it does not advance across the scan, the sample loop is not
   turning, every lane is STATIC for a reason that has nothing to do with the
   lanes, and no per-lane verdict is printed at all.

3. RUNS A MUST-NOT-MOVE CONTROL, through the same peek path, on
   `_rx_slot_C<chip>_IN_01` -- the very symbol that voided the old tool. It
   must read constant. If a symbol nothing writes comes back varying, the
   peek path itself is returning garbage and MOVING means nothing either.

Only with both controls satisfied is a per-lane verdict worth printing, and
the tool says which direction each control came out.

WHAT "MOVING" MEANS. A lane fed by a clocked converter varies sample to
sample with nothing plugged in -- the converter's own noise floor. A lane fed
by an unclocked one is a constant. So the question is "does it MOVE", not "is
it non-zero": a stuck non-zero word is exactly as dead as a stuck zero, which
is why `_buf_C1_XIN_MEMS` sitting at 0xFFFFFFFF counts as STATIC here.

DO NOT MAKE THE INTERVAL A ROUND NUMBER. The block rate is 3000/s and bench
stimuli run at rates that divide into it; S80's first pass peeked every 20 ms
-- exactly 60 blocks -- and reported `CODEC_04` falsely STATIC by aliasing
against a 2.5 ms drive period. The default here is 13.7 ms for that reason.

    python3 dsp4_inscan.py 1
    python3 dsp4_inscan.py 1 16          16 reads per lane
"""
import json
import sys
import time

CHIP = int(sys.argv[1]) if len(sys.argv) > 1 else 1
REPS = int(sys.argv[2]) if len(sys.argv) > 2 else 8
INTERVAL = 0.0137                  # deliberately not a multiple of 1/3000 s
FRAME_COUNT = 0xE004
MAGIC = 0xD5B40001

sys.argv = ['i']
import dsp4_diag as D               # noqa: E402


def load_syms(chip):
    """The symbol map for the image that is actually booted.

    A map from a different build peeks plausible ZEROS rather than raising,
    so it is worth saying where this one came from in the output."""
    for path in ('/home/app/dspboot/chip%d.sym.json' % chip,
                 './chip%d.sym.json' % chip):
        try:
            return json.load(open(path)), path
        except (IOError, OSError):
            continue
    raise SystemExit('dsp4_inscan: no chip%d.sym.json in /home/app/dspboot '
                     'or the working directory' % chip)


sym, sym_path = load_syms(CHIP)

link = D.SpiLink('0.0', 1000000, 6 if CHIP == 1 else 24,
                 rdy_gpio=8 if CHIP == 1 else 12)
diag = D.DiagLink(link)
diag.resync()


def peek(a, patience=25):
    """One bracketed peek, with 0xFFFFFFFF resolved rather than discarded.

    The link's "I don't know" and a genuinely stuck 0xFFFFFFFF lane are the
    same 32 bits, and the old tool simply skipped the value -- which is why
    `_buf_C1_XIN_MEMS`, stuck at 0xFFFFFFFF since S79, came back UNREADABLE
    from a link that was answering perfectly. The two are separable: a read
    whose MAGIC brackets both hold is a read the part answered, so an
    0xFFFFFFFF inside good brackets is the LANE's value. Retry anyway, in
    case a later attempt shows something else, and fall back to it only if
    every bracketed attempt said the same thing."""
    bracketed_ff = False
    for _ in range(patience):
        try:
            if diag.read(0xE000) != MAGIC:
                continue
            v = diag.peek(a)
            if diag.read(0xE000) != MAGIC:
                continue
            if v == 0xFFFFFFFF:
                bracketed_ff = True
                continue
            return v
        except IOError:
            continue
    return 0xFFFFFFFF if bracketed_ff else None


def sample(addr, reps=REPS):
    vals = []
    for _ in range(reps):
        v = peek(addr)
        if v is not None:
            vals.append(v)
        time.sleep(INTERVAL)
    return vals


def lane_names(chip):
    """Every block input buffer on this image, in a readable order."""
    pre = '_buf_C%d_' % chip
    names = [k for k in sym
             if k.startswith(pre) and ('_IN_' in k or k.startswith(pre + 'XIN'))]
    return sorted(names)


names = lane_names(CHIP)
print('symbol map: %s' % sym_path)
if not names:
    legacy = [k for k in sym if k.startswith('_rx_slot_C%d_IN' % CHIP)]
    print('dsp4_inscan: NO `_buf_C%d_*IN*` SYMBOLS IN THIS MAP.' % CHIP)
    if legacy:
        print('  %d legacy `_rx_slot_C%d_IN*` symbols are present, and those '
              'are' % (len(legacy), CHIP))
        print('  the ones that read a constant zero under block kernels '
              '(S80-19).')
        print('  Reporting on them is what this rewrite exists to stop.')
    print('  Either the map does not match the booted image, or this image '
          'was')
    print('  built without the block kernels. NOTHING IS SCANNED.')
    raise SystemExit(3)

# ---- control 1: the sample loop must be turning ----
fc0 = diag.read(FRAME_COUNT)

# ---- control 2: a symbol nothing writes must read constant ----
dead_name = '_rx_slot_C%d_IN_01' % CHIP
dead_vals = sample(sym[dead_name], 4) if dead_name in sym else None

rows = []
for name in names:
    vals = sample(sym[name])
    rows.append((name, vals))

fc1 = diag.read(FRAME_COUNT)

print()
print('CONTROLS')
if fc0 is None or fc1 is None:
    print('  MUST-MOVE  : FRAME_COUNT unreadable — the link did not answer.')
    raise SystemExit(2)
print('  MUST-MOVE  : FRAME_COUNT %d -> %d (%s)'
      % (fc0, fc1, 'advancing' if fc1 != fc0 else 'FROZEN'))
if fc1 == fc0:
    print()
    print('THE SAMPLE LOOP IS NOT TURNING. Every lane below would read STATIC')
    print('for that reason alone, so no lane verdict is printed. Fix the boot')
    print('(BOOT_STAGE, SPORT errors) before reading anything into the lanes.')
    raise SystemExit(2)
if dead_vals is None:
    print('  MUST-NOT-MOVE: %s absent from the map — control not run' % dead_name)
elif len(set(dead_vals)) == 1:
    print('  MUST-NOT-MOVE: %s constant at 0x%08X over %d reads (as it must '
          'be:' % (dead_name, dead_vals[0], len(dead_vals)))
    print('                 nothing writes it under block kernels)')
else:
    print('  MUST-NOT-MOVE: %s VARIED (%s) — the peek path is returning '
          'garbage,' % (dead_name, ' '.join('0x%08X' % v for v in dead_vals)))
    print('                 so MOVING below cannot be trusted either.')
    raise SystemExit(2)

print()
moving = static = unread = 0
for name, vals in rows:
    short = name.replace('_buf_C%d_' % CHIP, '')
    if not vals:
        print('  %-18s UNREADABLE' % short)
        unread += 1
        continue
    uniq = set(vals)
    if len(uniq) > 1:
        moving += 1
        tag = 'MOVING'
    else:
        static += 1
        tag = 'STATIC'
    print('  %-18s %-6s %2d distinct in %2d reads   e.g. %s'
          % (short, tag, len(uniq), len(vals),
             ' '.join('0x%08X' % v for v in vals[:4])))

print()
print('chip%d: MOVING %d / STATIC %d / UNREADABLE %d   '
      '(controls passed, so these mean what they say)'
      % (CHIP, moving, static, unread))
if moving == 0:
    print()
    print('EVERY LANE IS STATIC. With the sample loop proven turning, that is')
    print('a real reading and not an instrument fault — but check WHICH LOGIC')
    print('BITSTREAM IS FLASHED before concluding anything about converters:')
    print('`dsp4_logic.a1f6672af6c3`, the one the bench has lived on, predates')
    print('the S34 converter-clock fix and drives no BCK/FS to the converters')
    print('at all, so every lane reads exactly this (S81).')
    print('  python3 dsp4_logic_id.py')
sys.exit(0)
