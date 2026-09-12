#!/usr/bin/env python3
"""s39_symcheck.py — IS THE HOST SYMBOL MAP THIS IMAGE'S MAP?

Every "the state block is zero" reading on this bench came through
peek(sym[name]). This tests the MAP, not the part, using variables whose
value is known independently of the map:

  _diag_ticks   is what DIAG register 0xE005 (TICKS) returns. On a
                running part it is large and moving. If peek at the map's
                address for it returns 0 while the register returns
                millions, the address is not this image's.
  _spi_rx_count is DIAG 0xE00B, _spi_err_count is 0xE00C,
  _blk_overrun  is DIAG 0xE00A, _frame_count is 0xE004.

Five independent register/symbol pairs. A map that is right for the image
agrees on all five; a map from a different link agrees on none.
"""
import sys, time
_argv = list(sys.argv)
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

_a = _argv
CHIP = int(_a[1]) if len(_a) > 1 else 1
SYMDIR = _a[2] if len(_a) > 2 else '/home/app/dspboot'
sc = S.Scope(CHIP, symfile='%s/chip%d.sym.json' % (SYMDIR, CHIP))
sc.d.resync(); sc.check_chip()

PAIRS = [('_diag_ticks', 0xE005, 'TICKS'),
         ('_spi_rx_count', 0xE00B, 'SPI_RX_COUNT'),
         ('_spi_err_count', 0xE00C, 'SPI_ERR_COUNT'),
         ('_blk_overrun', 0xE00A, 'BLK_OVERRUN'),
         ('_frame_count', 0xE004, 'FRAME_COUNT'),
         ('_sec_count', 0xE006, 'SEC_COUNT'),
         ('_diag_resp_drop', 0xE00F, 'RESP_DROP')]

agree = disagree = skipped = 0
for name, reg, label in PAIRS:
    if name not in sc.sym:
        print('  %-18s NOT IN MAP' % name); skipped += 1; continue
    a = sc.sym[name]
    try:
        reg_v = sc.rd(reg)
    except IOError:
        reg_v = None
    try:
        peek_v = sc.peek(a)
    except IOError:
        peek_v = None
    # These are counters: read the register FIRST, peek second, so a
    # peek slightly ahead is the expected direction and a peek of ZERO
    # against a large register cannot be a race.
    ok = (reg_v is not None and peek_v is not None
          and (peek_v == reg_v or (reg_v > 1000 and peek_v >= reg_v)))
    print('  %-18s @0x%05X  peek %-12s  %-14s %-12s  %s'
          % (name, a, '--' if peek_v is None else str(peek_v),
             label, '--' if reg_v is None else str(reg_v),
             'agree' if ok else '**DISAGREE**'))
    if ok: agree += 1
    else: disagree += 1
print('chip%d: agree %d / disagree %d / not-in-map %d' % (CHIP, agree, disagree, skipped))
