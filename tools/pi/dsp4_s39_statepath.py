#!/usr/bin/env python3
"""s39_statepath.py — WHERE DOES THE HOST'S SYMBOL MAP DISAGREE WITH THE PART?

S38-5 read C1_GAIN_01's whole node state block as zero through the diag
PEEK window and the host symbol map, and concluded the block is "never
written". S38-3 read `_proc_cyc` / `_proc_passes` as zero the same way on
BOTH chips -- including the healthy one -- and concluded the image is
uninstrumented.

Neither conclusion follows from the source:

  * `_gain_coeff_<nid>` and `_gain_target_<nid>` are declared
    `.var ... = 1.0` and `_gain_q_<nid> = 0x10000000`, so a part that
    booted and never took a single write must read 1.0f / Q4.28 unity
    THERE, not zero;
  * `_proc_cyc` / `_proc_passes` are written by the block loop in
    main.asm UNCONDITIONALLY -- there is no build flag on them -- so
    "uninstrumented build" is not a state this tree can produce.

Both readings came through ONE path: peek(sym[name]). This asks the same
question through TWO paths that share nothing:

  A. peek(sym[name])              -- host symbol map + diag peek window
  B. the SPI PARAMETER read       -- spi_handler.asm resolves the address
                                     from `_spi_dispatch_c1`, which is
                                     INSIDE the image, so it cannot be
                                     stale with respect to the image

The dispatch table's own read path (spi_handler.asm, `.spi_read`) reads
the very DM word the write path targets -- there is no shadow store -- so
A and B name the same variable by two independent routes. If they
disagree, the symbol map is not this image's.
"""
import sys, time
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S

CHIP = 1
sc = S.Scope(CHIP, symfile='/home/app/dspboot/chip%d.sym.json' % CHIP)
sc.d.resync()
sc.check_chip()

def rd(reg):
    try:
        return sc.rd(reg)
    except IOError as e:
        return None

def pk(name):
    if name not in sc.sym:
        return None, None
    a = sc.sym[name]
    try:
        return a, sc.peek(a)
    except IOError:
        return a, None

def show(w):
    return '--' if w is None else '0x%08X' % w

print('BOOT_STAGE %s  FRAME_COUNT %s  PRODUCT_ID %s  BUILD_ID %s'
      % (rd(0xE002), rd(0xE004), rd(0xE010), show(rd(0xE017))))
print('BUILD_CFG  %s  SPI_ERR %s  BLK_OVERRUN %s'
      % (show(rd(0xE018)), rd(0xE00C), rd(0xE00A)))

# ---- A vs B on the cells that have BOTH a symbol and an SPI address ----
# (name, spi_addr, boot-time initialiser from the node ASM)
PAIRS = [
    ('_gain_coeff_C1_GAIN_01',    0x0000, 0x3F800000),
    ('_polarity_C1_GAIN_01',      0x0001, 0x00000000),
    ('_fdr_level_C1_FDR_01',      0x0050, None),
    ('_fdr_pan_C1_FDR_01',        0x0051, None),
    ('_fdr_mute_C1_FDR_01',       0x0052, None),
]
print('\n--- A (peek via host symbol map)  vs  B (SPI param read, in-image) ---')
for name, spi, init in PAIRS:
    a, va = pk(name)
    vb = rd(spi)
    tag = ''
    if va is not None and vb is not None:
        tag = 'AGREE' if va == vb else '**DISAGREE**'
    print('  %-26s sym %s peek %s | spi 0x%04X read %s   %s   init %s'
          % (name, ('--' if a is None else '0x%05X' % a), show(va),
             spi, show(vb), tag, show(init)))

# ---- the rest of the C1_GAIN_01 state block, peek only ----
print('\n--- C1_GAIN_01 node state block, peek only (S38-5 read all zero) ---')
for name, init in (('_gain_coeff_C1_GAIN_01', 0x3F800000),
                   ('_gain_target_C1_GAIN_01', 0x3F800000),
                   ('_gain_step_C1_GAIN_01', 0x00000000),
                   ('_gain_frames_C1_GAIN_01', 0x00000000),
                   ('_gain_q_C1_GAIN_01', 0x10000000),
                   ('_mute_C1_GAIN_01', 0x00000000),
                   ('_polarity_C1_GAIN_01', 0x00000000),
                   ('_tap_post_trim_C1_GAIN_01', None),
                   ('_buf_C1_GAIN_01', None)):
    a, v = pk(name)
    note = ''
    if v is not None and init is not None:
        note = 'as built' if v == init else '**NOT the initialiser**'
    print('  %-28s @%s = %s  %s' % (name, ('--' if a is None else '0x%05X' % a),
                                    show(v), note))

# ---- the instrument S38-3 called absent ----
print('\n--- block-cost instrumentation (main.asm, unconditional) ---')
for name in ('_proc_cyc', '_proc_cyc_max', '_proc_passes', '_diag_ticks'):
    a, v = pk(name)
    print('  %-16s @%s = %s (%s)' % (name, ('--' if a is None else '0x%05X' % a),
                                     show(v), 'n/a' if v is None else v))
time.sleep(0.5)
print('  --- again, 0.5 s later (these must MOVE on a running block loop) ---')
for name in ('_proc_cyc', '_proc_passes'):
    a, v = pk(name)
    print('  %-16s = %s (%s)' % (name, show(v), 'n/a' if v is None else v))

# ---- the control-epoch counter the strip nodes gate their prep on ----
print('\n--- _ctl_epoch[0] (strip 1) and [32] (catch-all) ---')
if '_ctl_epoch' in sc.sym:
    base = sc.sym['_ctl_epoch']
    for i in (0, 32):
        try:
            print('  _ctl_epoch[%2d] @0x%05X = %s' % (i, base + i, show(sc.peek(base + i))))
        except IOError:
            print('  _ctl_epoch[%2d] unreadable' % i)
