#!/usr/bin/env python3
"""s177_latency_model.py -- the D24 analog-in -> analog-out latency, stage by stage.

The model is the firmware's own buffering, read from the source:

  * a chip holds every sample for TWO of its blocks (src/dma_config.c: one
    DMA row = one block, YCNT = 2; src/sport_init.asm: the core reads the RX
    row that just completed and writes the TX row the DDE clocks next). A
    sample at position j of input row n waits B-j frames for the row to
    finish, one block period for the graph, and leaves at position j of the
    next TX row: 2B for every j.
  * DSP4_TX_EARLY on a chip writes one row further ahead (_blk_latch_bufs):
    +B on that chip (S11, measured +16 per chip at block 16).
  * a TX phase offset of k frames (the S177 proposal: the deferred gather
    at a fixed point after the interrupt into the NEXT row, with the TX row
    grid started k frames behind the RX grid) costs +k on that chip in place
    of +B.
  * the residual is what the block structure does not explain: on the Pi
    path (latency.sh), the re-framer's frame each way and the capture
    snapshot; on the analog path, the ADC retime and the converters' own
    group delay.

The anchors are the measured arms, and the model has to reproduce each of
them before any projection is printed.

    python3 s177_latency_model.py            # anchors, then the lever table
"""
import sys

FS = 48000

# Converter group delays, 1/fs, from the AK data sheets on Dropbox
# (_Desktop mac/D24/D24-datasheets/): AK5558 short-delay sharp (SD strap,
# dsp4-s42 sheet 13/64) 5; AK4458 short-delay sharp, the parallel-mode
# default (table 16) 5.8; the same figures at 96 kHz.
AK5558_GD = 5.0
AK4458_GD = 5.8

# The residual of the Pi-path arms (median, S11 / S17): 66/67 - 64.
PI_RESID = 2.5
# The analog residual: S60's whole loop 91.40 (findings S60, the
# s121 per-unit nominal) - 5 blocks of 16 - the two converters.
S60_LOOP = 91.40
ANA_RESID = S60_LOOP - 80 - AK5558_GD - AK4458_GD          # 0.6


def pipeline(blocks, guards, offsets=()):
    """blocks: block size per chip stage; guards: block size of each
    TX_EARLY guard; offsets: k frames of each TX phase offset."""
    return sum(2 * b for b in blocks) + sum(guards) + sum(offsets)


def analog(pipe):
    return pipe + ANA_RESID + AK5558_GD + AK4458_GD


ANCHORS = [
    # (what, measured, model)
    ('S11 B16 TX_EARLY=0, Pi path', 66, pipeline([16, 16], []) + PI_RESID),
    ('S17 B16 TX_EARLY=0, Pi path', 67, pipeline([16, 16], []) + PI_RESID),
    ('S11/S17 B16 TX_EARLY=2 (ships)', 82, pipeline([16, 16], [16]) + PI_RESID),
    ('S11 B16 TX_EARLY=3', 99, pipeline([16, 16], [16, 16]) + PI_RESID),
    ('S11 B32 TX_EARLY=0', 131, pipeline([32, 32], []) + PI_RESID),
    ('S83 signed pair (contract 82)', 80, pipeline([16, 16], [16]) + PI_RESID),
    ('S60 analog loop, B16 TX_EARLY=2', 91.40, analog(pipeline([16, 16], [16]))),
]

LEVERS = [
    # (name, pipeline samples, note)
    ('today: B16, chip-2 guard', pipeline([16, 16], [16]), 'measured (S60)'),
    ('(b) B16, guard off, gather at end', pipeline([16, 16], []),
     'the S9-2 frame-0 race returns'),
    ('(b2) B16, chip-2 TX offset k=3', pipeline([16, 16], [], [3]),
     'deadline fixed, load-independent'),
    ('(a) B8 both, chip-2 guard', pipeline([8, 8], [8]), ''),
    ('(a+b2) B8 both, offset k=3 on both', pipeline([8, 8], [], [3, 3]),
     'chip 1 needs it too at B8'),
    ('(a+b2) B8 both, offset k=2 on both', pipeline([8, 8], [], [2, 2]),
     'only if the DMA lead is < 2 frames'),
    ('(a) B4 both, chip-2 guard', pipeline([4, 4], [4]), 'capacity: no'),
    ('chip 1 B8, chip 2 B16 + k=3', pipeline([8, 16], [], [3, 3]), ''),
    ('(c) one chip, B16, guard', pipeline([16], [16]), 'card rev E'),
    ('(c) one chip, B16, offset k=3', pipeline([16], [], [3]), 'card rev E'),
    ('(c) one chip, B8, offset k=3', pipeline([8], [], [3]), 'card rev E'),
]


def main():
    ok = True
    print('ANCHORS (measured vs model)')
    for what, meas, mod in ANCHORS:
        err = mod - meas
        flag = '' if abs(err) <= 3 else '  <-- OFF'
        ok &= abs(err) <= 3
        print(f'  {what:<36} measured {meas:7.2f}  model {mod:7.2f}  {err:+5.2f}{flag}')
    print(f'  analog residual (S60 - 80 - converters): {ANA_RESID:.2f} samples')
    if not ok:
        print('model does not reproduce its anchors; no projection printed')
        return 1
    print()
    print(f'{"lever":<40} {"pipe":>5} {"analog":>7} {"ms@48k":>7} {"ms@96k":>7}  note')
    for name, pipe, note in LEVERS:
        a = analog(pipe)
        tag = ' <= 1.0 ms' if a / FS * 1e3 <= 1.0 else ''
        print(f'  {name:<38} {pipe:5.0f} {a:7.1f} {a / FS * 1e3:7.3f} '
              f'{a / 96000 * 1e3:7.3f}  {note}{tag}')
    print()
    budget = FS * 1e-3 - ANA_RESID - AK5558_GD - AK4458_GD
    print(f'1.0 ms at 48 kHz leaves the pipeline {budget:.1f} samples '
          f'(48 - {ANA_RESID:.1f} residual - {AK5558_GD + AK4458_GD:.1f} converters)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
