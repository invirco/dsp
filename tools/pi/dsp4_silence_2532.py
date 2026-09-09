"""Silence the eight chip-1 strips a D24 does not have but still runs.

The DSP4 firmware is ONE image running 32 strips, and all 32 sum into
C2_RECV_MAIN_L. D24 is a 24-channel product: its matrix has zero Chan025
cells and defs-v2026.09.08.4's d24/dsp.csv accordingly has 102 cells each
for Chan001..024 and none for Chan025..032. The contract is right; there
is simply no D24 cell for strips that are not supposed to be running.

Measured consequence on the bench: with everything the D24 contract CAN
silence silenced and the Pi input off, C2_MAIN_ST_OUT sits at positive
full scale (0x7FFFFFE0) for 48,000 frames out of 48,000. After this
script it reads 0x00000000 for 48,000 out of 48,000.

The addresses below are D32's rows for exactly those cells: decision D3
makes the DSP address map SHARED between the products, and
Chan024MainOn001 reads 0x0D44 in both files, so these are the same words
on the same part.

BENCH WORKAROUND, NOT A FIX. The real defect is that D24's product
config already says these strips are off -- dsp4_config.py sends
CFG_CHAN_MASK = 0x00FFFFFF -- and the firmware stores the word in
_chan_mask and never reads it. See MW/D32/DSP/dsp4-loop-latency-20260909.md
section 3. Delete this file once _chan_mask has a reader.
"""
import sys, time
sys.argv = ['s']; sys.path.insert(0, '/home/app/dspboot')
from dsp4_conform import Part

CELLS = [
    ('Chan025MainOn001', 1, 3540, 0),
    ('Chan025Mute001', 1, 3538, 1),
    ('Chan026MainOn001', 1, 3684, 0),
    ('Chan026Mute001', 1, 3682, 1),
    ('Chan027MainOn001', 1, 3828, 0),
    ('Chan027Mute001', 1, 3826, 1),
    ('Chan028MainOn001', 1, 3972, 0),
    ('Chan028Mute001', 1, 3970, 1),
    ('Chan029MainOn001', 1, 4116, 0),
    ('Chan029Mute001', 1, 4114, 1),
    ('Chan030MainOn001', 1, 4260, 0),
    ('Chan030Mute001', 1, 4258, 1),
    ('Chan031MainOn001', 1, 4404, 0),
    ('Chan031Mute001', 1, 4402, 1),
    ('Chan032MainOn001', 1, 4548, 0),
    ('Chan032Mute001', 1, 4546, 1),
]

p1 = Part(1)
for cell, chip, addr, val in CELLS:
    assert chip == 1, cell
    p1.write(addr, val)
time.sleep(0.5)
print('silenced %d cells on chip 1 (strips 25-32, via the D32 rows)' % len(CELLS))
