#!/usr/bin/env python3
"""blk30.py <chip> <seconds> — the blk_* real-time bar on ONE chip.

Reads FRAME_COUNT (0xE004), BLK_OVERRUN (0xE00A), SPORT0_ERR_A (0xE012),
BOOT_STAGE (0xE002) at t0 and again after <seconds>, and reports the
deltas. The bar (S27): ~BLOCK_RATE blocks/s and ZERO overruns.

Deltas, not --clear: a counter clear is a write to a running card and the
figure it produces cannot be cross-checked against the start value.
"""
import sys, time, os
CHIP = int(sys.argv[1]) if len(sys.argv) > 1 else 1
WINDOW = float(sys.argv[2]) if len(sys.argv) > 2 else 30.0
try:
    from dsp4_block import BLOCK, BLOCK_RATE
except ImportError:
    print('REFUSED: dsp4_block.py is not staged beside me — the bar cannot '
          'be scored against a block size the image was not built with')
    sys.exit(2)
sys.argv = ['b']
import dsp4_diag as D

link = D.SpiLink('0.0', 1000000, 6 if CHIP == 1 else 24,
                 rdy_gpio=8 if CHIP == 1 else 12)
diag = D.DiagLink(link); diag.resync()
REGS = [('FRAME_COUNT', 0xE004), ('BLK_OVERRUN', 0xE00A),
        ('SPORT0_ERR_A', 0xE012), ('BOOT_STAGE', 0xE002),
        ('CHIP_ID', 0xE001), ('SEC_COUNT', 0xE006)]

def snap(patience=40):
    """One coherent snapshot: MAGIC either side, so a link that slipped
    mid-read is discarded rather than averaged in."""
    for _ in range(patience):
        try:
            if diag.read(0xE000) != 0xD5B40001:
                continue
            v = {n: diag.read(a) for n, a in REGS}
            if diag.read(0xE000) != 0xD5B40001:
                continue
            return v
        except IOError:
            continue
    return None

a = snap()
if a is None:
    print(f'chip{CHIP}: UNKNOWN — link never answered'); sys.exit(2)
if a['CHIP_ID'] != CHIP:
    print(f'chip{CHIP}: WRONG CHIP_ID {a["CHIP_ID"]} — every figure below '
          f'would be fiction (S8-3)'); sys.exit(3)
t0 = time.time(); time.sleep(WINDOW); b = snap()
if b is None:
    print(f'chip{CHIP}: UNKNOWN — link answered once then stopped'); sys.exit(2)
dt = time.time() - t0
blocks = b['FRAME_COUNT'] - a['FRAME_COUNT']
over   = b['BLK_OVERRUN'] - a['BLK_OVERRUN']
rate   = blocks / dt
print(f'chip{CHIP}: BOOT_STAGE {a["BOOT_STAGE"]}->{b["BOOT_STAGE"]}  '
      f'SEC_COUNT {b["SEC_COUNT"]}')
print(f'chip{CHIP}: {blocks} blocks in {dt:.1f} s = {rate:.0f}/s '
      f'(bar {BLOCK_RATE}/s at BLOCK={BLOCK})')
print(f'chip{CHIP}: BLK_OVERRUN {a["BLK_OVERRUN"]} -> {b["BLK_OVERRUN"]} '
      f'(delta {over})   SPORT0_ERR_A 0x{b["SPORT0_ERR_A"]:08X}')
ok = rate > 0.98 * BLOCK_RATE and over == 0 and b['SPORT0_ERR_A'] == 0 \
     and b['BOOT_STAGE'] == 7
print(f'chip{CHIP}: {"BLK_OK" if ok else "BLK_FAIL"}')
sys.exit(0 if ok else 1)
