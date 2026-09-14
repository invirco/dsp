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

# Four of the seven are FREE-RUNNING counters (TICKS, FRAME_COUNT,
# SEC_COUNT, SPI_RX_COUNT). rd() votes -- it needs the same non-zero
# value twice -- so it can never resolve one of those, and this gate read
# "disagree 3" on a correct map and a healthy link (S46-3, 2026-09-14:
# all 12 asks answered, each value larger than the last). The test that
# actually expresses the question is a BRACKET: ask, peek, ask. If the
# peek lands between the two register reads, the symbol and the register
# are the same object -- and for a moving counter that is a far stronger
# statement than equality, because a wrong address cannot track it.
COUNTERS = {'_diag_ticks', '_spi_rx_count', '_frame_count', '_sec_count'}

agree = disagree = skipped = 0
for name, reg, label in PAIRS:
    if name not in sc.sym:
        print('  %-18s NOT IN MAP' % name); skipped += 1; continue
    a = sc.sym[name]
    try:
        if name in COUNTERS:
            v1, peek_v, v2 = sc.rd_counter(reg, addr=a)
            ok = (v1 <= peek_v <= v2)
            shown = '%d..%d' % (v1, v2)
        else:
            reg_v = sc.rd(reg)
            peek_v = sc.peek(a)
            ok = (peek_v == reg_v)
            shown = str(reg_v)
    except IOError as exc:
        print('  %-18s @0x%05X  UNREADABLE: %s' % (name, a, exc))
        disagree += 1; continue
    print('  %-18s @0x%05X  peek %-12s  %-14s %-14s %s'
          % (name, a, peek_v, label, shown,
             'agree' if ok else '**DISAGREE**'))
    if ok: agree += 1
    else: disagree += 1
print('chip%d: agree %d / disagree %d / not-in-map %d' % (CHIP, agree, disagree, skipped))
