#!/usr/bin/env python3
"""dsp4_inscan.py <chip> [reps] — do the XIN return lanes carry anything?

For the MIC/TDM input lanes use `dsp4_rxscan.py` — see point 1 below.

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

1. READS THE BLOCK SYMBOLS THAT ARE REALLY WRITTEN -- `_buf_C<chip>_XIN_*`
   -- and REFUSES to run at all if it cannot find them, instead of skipping
   silently and reporting on nothing.

   *** CORRECTED 2026-09-20 (S86). S81 PUT `_buf_C<chip>_IN_*` IN THIS LIST
   TOO, AND THOSE ARE DEAD AS WELL. *** A node whose output feeds the next
   node of its own strip writes the shared BLOCK POOL, not `_buf_<nid>`:
   `_C1_IN_16_process` reads the RX DMA buffer straight into `BLK_CHAIN_A`
   and its own header says so. Only the nodes that are NOT chain heads --
   the `XIN_*` lanes and the buses -- own a real `_buf_<nid>[BLOCK]`. So the
   rewrite swapped one symbol nothing writes for another, and the scan then
   printed "the codec lanes move and the mic lanes are exact digital zero"
   on a card whose mic lanes were healthy. Five sessions diagnosed that as a
   converter, bitstream, launch-phase and SPORT receive fault in turn.
   **THE MIC LANES ARE NOT SCANNED HERE ANY MORE. Use `dsp4_rxscan.py`,**
   which reads the RX DMA region itself and cannot be fooled this way.

2. RUNS A MUST-MOVE CONTROL FIRST. FRAME_COUNT (0xE004) is incremented by the
   block ISR. If it does not advance across the scan, the sample loop is not
   turning, every lane is STATIC for a reason that has nothing to do with the
   lanes, and no per-lane verdict is printed at all.

3. RUNS TWO MUST-NOT-MOVE CONTROLS, through the same peek path, on
   `_rx_slot_C<chip>_IN_01` -- the symbol that voided the pre-S81 tool -- and
   on `_buf_C<chip>_IN_01`, the one that voided the S81 rewrite. Both must
   read constant. If a symbol nothing writes comes back varying, the peek
   path itself is returning garbage and MOVING means nothing either; and
   carrying the second one here means the trap is demonstrated on every run
   rather than described in a comment.

Only with every control satisfied is a per-lane verdict worth printing, and
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
import os
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
    so it is worth saying where this one came from in the output.

    THE WORKING DIRECTORY COMES FIRST, AND THAT IS THE WHOLE POINT (S82-4).
    This list used to read ~/dspboot before `.`, which is backwards for the
    only case that matters: a STAGED arm runs from its own directory
    (/home/app/ship_s82, cap_*, conf_*, geq_*...) and ~/dspboot holds
    whatever the last measurement run left behind. S82 booted the signed
    pair in /home/app/ship_s82 and this tool silently scored it through the
    S78-restore pair's map -- forty-seven lanes reported STATIC, three of
    them at 0x3F800000, which is 1.0f and not a sample at all, while a peek
    of the SAME lanes through the staged map showed every codec return
    moving. That is exactly the failure the docstring above warns about,
    committed by the tool's own search order.

    ~/dspboot stays in the list, second, because an unstaged run from that
    directory is `.` anyway and a run from somewhere else with no local map
    is better served by the deploy than by an exception.
    """
    for path in ('./chip%d.sym.json' % chip,
                 '/home/app/dspboot/chip%d.sym.json' % chip):
        try:
            return json.load(open(path)), os.path.abspath(path)
        except (IOError, OSError):
            continue
    raise SystemExit('dsp4_inscan: no chip%d.sym.json in the working '
                     'directory or /home/app/dspboot' % chip)


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
    """Every block input buffer on this image that is actually written.

    `_buf_C<chip>_XIN_*` only. The `_buf_C<chip>_IN_*` scalars are pool-
    resident node linkage and no block kernel writes them (S86); they are
    read below as a CONTROL and never as a lane."""
    pre = '_buf_C%d_XIN' % chip
    return sorted(k for k in sym if k.startswith(pre))


names = lane_names(CHIP)
print('symbol map: %s' % sym_path)
if not names:
    legacy = [k for k in sym if k.startswith('_rx_slot_C%d_IN' % CHIP)]
    print('dsp4_inscan: NO `_buf_C%d_XIN*` SYMBOLS IN THIS MAP.' % CHIP)
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
# The symbol the S81 rewrite scanned as a lane. It is read here so that every
# run of this tool re-demonstrates that it carries nothing (S86).
dead2_name = '_buf_C%d_IN_01' % CHIP
dead2_vals = sample(sym[dead2_name], 4) if dead2_name in sym else None

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
if dead2_vals is None:
    print('  MUST-NOT-MOVE: %s absent from the map — control not run'
          % dead2_name)
elif len(set(dead2_vals)) == 1:
    print('  MUST-NOT-MOVE: %s constant at 0x%08X over %d reads — the mic'
          % (dead2_name, dead2_vals[0], len(dead2_vals)))
    print('                 lanes are NOT scanned through these symbols;')
    print('                 `python3 dsp4_rxscan.py` reads the DMA region')
    print('                 and is the instrument for that question (S86).')
else:
    print('  MUST-NOT-MOVE: %s VARIED (%s) — the peek path is returning '
          'garbage.' % (dead2_name, ' '.join('0x%08X' % v for v in dead2_vals)))
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
    print('a real reading about THESE ADDRESSES — check two things before')
    print('concluding anything about converters (S82).')
    print()
    print('0. THIS TOOL SCANS THE XIN LANES ONLY. The mic lanes live in the')
    print('   RX DMA region and are read by `python3 dsp4_rxscan.py` (S86).')
    print('1. THE SYMBOL MAP ABOVE. A map from another build peeks plausible')
    print('   zeros and this tool cannot tell. If the map is not the booted')
    print("   image's, every verdict here is about the wrong addresses.")
    print('2. WHICH LOGIC BITSTREAM IS FLASHED:')
    print('     python3 dsp4_logic_id.py')
    print('   A pre-S34 bitstream drives no BCK/FS to the converters at all,')
    print('   so every lane reads exactly this (S81). The shipping artifact')
    print("   is dsp4_logic.d02d83b3cc22, design_id 0x83b3cc22 (S85);")
    print('   anything that')
    print('   answers "no reply" is older than the design-ID stamp and is')
    print('   not a bitstream this bench flashes any more.')
sys.exit(0)
