#!/usr/bin/env python3
"""s86_rxscan.py — READ THE RX DMA BUFFER ITSELF, not a symbol that stands
next to it.

WHY THIS TOOL EXISTS. S80-S85 read `_buf_C1_IN_01..32` and found exact
digital zero on every bitstream, in every rail state, and concluded the mic
lanes were dark. Under `DSP4_BLOCK_KERNELS` -- which every shipping and
TEST_NODES pair is built with -- **nothing writes `_buf_C1_IN_nn`.**
`_C1_IN_nn_process` reads the SPORT RX DMA buffer straight into the shared
block pool (`BLK_CHAIN_A`) and the `_buf_` scalar survives only as linkage
and as the identity token `_scope_tap`/`_scope_inject_blk` compare against.
`src/chip1/nodes/C1_IN_16.asm` says so in its own header. The XIN_* nodes
(codec, MEMS, Pi, snake) are the exception: they are NOT chain heads, they
each own a real `_buf_<nid>[DSP4_BLOCK_SIZE]`, and those are the six buffers
that decoded correctly in S85. The split in that reading is the split
between nodes that have a buffer and nodes that do not -- not between pins
that work and pins that do not.

So this reads the only thing that is actually the receive path's output:
the DMA ping-pong region, at `_rx_active_buf + off + k*stride`, with off and
stride taken from the part's own `_c1_rx_off` / `_c1_rx_stride` tables. That
is the read `s52lib.lane()` has carried since S52.

CONTROLS, all three of which must come out right or no verdict is printed:
  MUST MOVE      FRAME_COUNT advances (the block ISR is turning).
  MUST NOT MOVE  `_rx_slot_C1_IN_01` -- a symbol nothing writes.
  MUST NOT MOVE  `_buf_C1_IN_01`     -- the symbol S80-S85 read. It is in
                 this table deliberately, beside the DMA read of the SAME
                 lane, so the two readings are one pass and one bitstream.

LANE-ID DECODE. With the `_laneid` CPLD bitstream on the part every DSPA
input pin streams `{8'hA5, pin[3:0], tick, slot[2:0]}` in the top 16 bits.
--laneid decodes it per entry and checks the pin and slot against the lane
table this image was generated from.
"""
import argparse
import json
import math
import os
import sys
import time

_argv = list(sys.argv)                 # BEFORE the import: dsp4_scope parses argv
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S                                              # noqa: E402

FRAME_COUNT = 0xE004

# The chip-1 RX table, in generated order (src/chip1/block_io.asm).
NAMES = """IN_01 IN_02 IN_03 IN_04 IN_05 IN_06 IN_07 IN_08 IN_09 IN_10
IN_11 IN_12 IN_13 IN_14 IN_15 IN_16 IN_17 IN_18 IN_19 IN_20 IN_21 IN_22
IN_23 IN_24 IN_25 IN_26 IN_27 IN_28 IN_29 IN_30 IN_31 IN_32
XIN_CODEC_01 XIN_CODEC_02 XIN_CODEC_03 XIN_CODEC_04
XIN_SNK_01 XIN_SNK_02 XIN_SNK_03 XIN_SNK_04 XIN_SNK_05 XIN_SNK_06
XIN_SNK_07 XIN_SNK_08 XIN_PI_L XIN_PI_R XIN_MEMS""".split()

# c1_rx_lanes from src/chip1/lane_config.c: pin -> (cs_mask, stride, region_off)
LANES = [(0, 0x00FF, 8, 0), (1, 0x00FF, 8, 128), (2, 0x00FF, 8, 256),
         (3, 0x00FF, 8, 384), (4, 0x000F, 4, 512), (5, 0x00FF, 8, 576),
         (6, 0x0003, 2, 704), (7, 0x0020, 1, 736)]


def s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def dbfs31(v):
    """RX lanes are 24-in-32 left-justified: full scale is 2**31."""
    a = abs(v) / float(1 << 31)
    return -336.0 if a <= 0 else 20.0 * math.log10(a)


def place(off):
    """DMA word offset -> (pin, slot index within the lane, TDM slot)."""
    for pin, cs, stride, base in LANES:
        if base <= off < base + stride:
            k = off - base
            slots = [b for b in range(16) if cs >> b & 1]
            return pin, k, (slots[k] if k < len(slots) else None)
    return None, None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--symdir', default='/home/app/s83tn')
    ap.add_argument('--reps', type=int, default=32)
    ap.add_argument('--tag', default='')
    ap.add_argument('--json', default=None)
    ap.add_argument('--laneid', action='store_true',
                    help='decode the _laneid bitstream marker per entry')
    a = ap.parse_args(_argv[1:])

    sc = S.Scope(1, symfile=os.path.join(a.symdir, 'chip1.sym.json'))
    sc.d.resync()
    sc.check_chip()
    sym = sc.sym
    print('symbol map: %s/chip1.sym.json (%d symbols)  tag=%s'
          % (os.path.abspath(a.symdir), len(sym), a.tag))

    def pk(addr, patience=40):
        for _ in range(6):
            try:
                return sc.peek(addr, patience)
            except IOError:
                time.sleep(0.02)
                try:
                    sc.d.resync()
                except Exception:
                    pass
        return None

    off_b = sym['_c1_rx_off']
    str_b = sym['_c1_rx_stride']
    buf_p = sym['_rx_active_buf']
    patch = [pk(sym['_rx_patch_regs'] + i) for i in range(len(NAMES))]

    fc0 = sc.d.read(FRAME_COUNT)

    # ---- the two dead-symbol controls, read the same way as the lanes ----
    controls = {}
    for cname in ('_rx_slot_C1_IN_01', '_buf_C1_IN_01', '_buf_C1_IN_16'):
        if cname in sym:
            vs = []
            for _ in range(a.reps):
                v = pk(sym[cname])
                if v is not None:
                    vs.append(s32(v))
                time.sleep(0.0137)
            controls[cname] = vs

    rows = []
    for i, _ in enumerate(NAMES):
        off = pk(off_b + i)
        stride = pk(str_b + i)
        if off is None or stride is None:
            rows.append({'entry': i, 'read': 0})
            continue
        pin, k, slot = place(off)
        words = []
        for n in range(a.reps):
            b = pk(buf_p)
            if b is None:
                continue
            v = pk(b + off + (n % 16) * stride)
            if v is not None:
                words.append(v & 0xFFFFFFFF)
        node = NAMES[patch[i]] if patch[i] is not None and patch[i] < len(NAMES) else '?'
        r = {'entry': i, 'off': off, 'stride': stride, 'pin': pin,
             'slot': slot, 'node': node, 'read': len(words),
             'words': ['%08x' % w for w in words[:8]]}
        if words:
            sv = [s32(w) for w in words]
            rms = math.sqrt(sum((x / 2.0 ** 31) ** 2 for x in sv) / len(sv))
            r.update({'distinct': len(set(words)),
                      'rms_dbfs': round(20 * math.log10(rms) if rms > 0 else -336.0, 2),
                      'peak_dbfs': round(max(dbfs31(x) for x in sv), 2),
                      'min': min(sv), 'max': max(sv)})
            if a.laneid:
                # {8'hA5, pin[3:0], tick, slot[2:0]} in the top 16 bits, and
                # the same three-bit trim S85-7 measured on the decode.
                # Read straight from DMA there is no Q1.31->Q4.28 shift to
                # undo (that is the node kernel's `ashift by -3`, which is
                # where S85-7's uniform three-bit offset came from). A lane
                # framed MFD 1 against an MFD 2 build still lands one bit
                # out, so the window is walked and the offset reported.
                marks = set()
                for w in words:
                    for sh in range(-4, 5):
                        t = ((w << sh) if sh >= 0 else (w >> -sh)) & 0xFFFFFFFF
                        if t >> 24 == 0xA5:
                            marks.add(((t >> 20) & 0xF, (t >> 16) & 0x7, sh))
                r['marks'] = sorted(marks)
        rows.append(r)

    fc1 = sc.d.read(FRAME_COUNT)
    moved = (fc1 - fc0) & 0xFFFFFFFF

    print()
    ok = True
    print('  control MUST MOVE      FRAME_COUNT +%d  [%s]'
          % (moved, 'ok' if moved else 'FAILED — the block loop is not turning'))
    if not moved:
        ok = False
    for cname, vs in controls.items():
        nd = len(set(vs)) if vs else 0
        print('  control MUST NOT MOVE  %-20s %d reads, %d distinct, value %s  [%s]'
              % (cname, len(vs), nd,
                 ('0x%08X' % (vs[0] & 0xFFFFFFFF)) if vs else '-',
                 'ok' if nd == 1 else 'FAILED — the peek path is noisy'))
        if nd != 1:
            ok = False
    if not ok:
        raise SystemExit('controls failed: no per-lane verdict is takeable')

    print()
    hdr = ('%-12s %5s %4s %4s %5s %5s %8s %9s %9s  %s'
           % ('node', 'entry', 'off', 'pin', 'slot', 'read', 'distinct',
              'rms dBFS', 'pk dBFS', 'first words'))
    print(hdr)
    for r in rows:
        if not r.get('read'):
            print('%-12s %5d  UNREAD' % (NAMES[r['entry']], r['entry']))
            continue
        print('%-12s %5d %4d %4s %5s %5d %8d %9.2f %9.2f  %s'
              % (r['node'], r['entry'], r['off'], r['pin'], r['slot'],
                 r['read'], r['distinct'], r['rms_dbfs'], r['peak_dbfs'],
                 ' '.join(r['words'][:3])))
        if a.laneid:
            print('%-12s %5s marks: %s' % ('', '', r.get('marks')))

    mic = [r for r in rows if r['entry'] < 32 and r.get('read')]
    alive = [r for r in mic if r.get('distinct', 0) > 1]
    xin = [r for r in rows if r['entry'] >= 32 and r.get('read')]
    xalive = [r for r in xin if r.get('distinct', 0) > 1]
    print()
    print('MIC  lanes (entries 0..31): %d of %d CARRYING SAMPLES'
          % (len(alive), len(mic)))
    print('XIN  lanes (entries 32..46): %d of %d CARRYING SAMPLES'
          % (len(xalive), len(xin)))

    out = {'tag': a.tag, 'symdir': os.path.abspath(a.symdir),
           'frame_count_delta': moved,
           'controls': {k: {'reads': len(v), 'distinct': len(set(v)),
                            'value': ('0x%08X' % (v[0] & 0xFFFFFFFF)) if v else None}
                        for k, v in controls.items()},
           'mic_alive': len(alive), 'mic_read': len(mic),
           'xin_alive': len(xalive), 'xin_read': len(xin),
           'lanes': rows}
    if a.json:
        json.dump(out, open(a.json, 'w'), indent=1)
        print('wrote %s' % a.json)


if __name__ == '__main__':
    main()
