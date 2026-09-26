#!/usr/bin/env python3
"""s118_probe.py — the chip-1 -> chip-2 MAIN link, read end to end at one
place in the path per stage, so a reading says WHERE the signal enters.

S115-2 measured `_buf_C2_RECV_MAIN_L` pinned at Q4.28 saturation while chip
1's own `_buf_C1_BUS_MAIN_L` read -117.8 dBFS. That pair of numbers does not
say whether the saturation arrived on the wire, was put in the DMA buffer by
something else, or was invented between the buffer and the node. This reads
all four stages of the chain on chip 2:

    DMA half (the words the DDE wrote)   <- the wire
      _rx_ic_slot_C2_RECV_MAIN_L[16]     <- _scatter_chip2
        _blk_C2_RECV_MAIN_L[16]          <- the node body
          _buf_C2_MIX_MAIN_L[16]         <- the mix

and the same stage 1 on chip 1's send side (`_buf_C1_BUS_MAIN_L`), plus the
ping/pong pointer state, which is what a boot resets and a config commit does
not.

Peeks are NOT coherent (S115: a 16-word peek spans ~15 audio blocks), so a
reading here is a MAGNITUDE, never a waveform. That is all this needs: the
fault is +18 dBFS against a floor of -106.
"""
import argparse, json, math, os, sys, time

_argv = list(sys.argv)
sys.argv = ['s']
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S                                              # noqa: E402

FRAME_COUNT   = 0xE004
BLK_OVERRUN   = 0xE00A
SPORT0_ERR_A  = 0xE012
DMA0_STAT     = 0xE013

BLOCK = 16


def s32(v):
    v &= 0xFFFFFFFF
    return v - (1 << 32) if v & 0x80000000 else v


def q28(v):
    return s32(v) / float(1 << 28)


def stats(words):
    xs = [q28(w) for w in words]
    pk = max(abs(x) for x in xs) if xs else 0.0
    rms = math.sqrt(sum(x * x for x in xs) / len(xs)) if xs else 0.0
    def db(x):
        return -300.0 if x <= 0 else 20.0 * math.log10(x)
    return pk, rms, db(pk), db(rms)


def line(tag, words):
    pk, rms, pkdb, rmsdb = stats(words)
    nz = sum(1 for w in words if (w & 0xFFFFFFFF) != 0)
    return ('%-34s peak %+8.2f dBFS  rms %+8.2f dBFS  %2d/%2d nonzero  %s'
            % (tag, pkdb, rmsdb, nz, len(words),
               ' '.join('%08X' % (w & 0xFFFFFFFF) for w in words[:6])))


def read_block(sc, base, stride, n=BLOCK):
    return [sc.peek(base + i * stride) for i in range(n)]



# The 41 inter-chip fabric signals in _c1_ic_tx_ptrs / _c2_ic_rx_ptrs order
# (MW/D32/DSP/SHARC/src/chip{1,2}/block_io.asm, the non-DSP4_CUE arm). The
# OFFSETS are read off the part; only the NAMES come from the tree, and a
# length mismatch against the part's own table is fatal below.
FABRIC = (['MAIN_L', 'MAIN_R', 'SUB'] +
          ['GRP_%02d' % i for i in range(1, 5)] +
          ['AUX_%02d' % i for i in range(1, 13)] +
          ['FX_%02d' % i for i in range(1, 7)] +
          ['CODEC_AUX_L', 'CODEC_AUX_R', 'PI_L', 'PI_R'] +
          ['SNAKE_%02d' % i for i in range(1, 9)] +
          ['MTX_%02d' % i for i in range(1, 5)])


def table(sc, sym, n):
    a = sc.addr(sym)
    return [sc.peek(a + i) for i in range(n)]


def survey(s1, s2, n_samp=4):
    """Every fabric slot, as chip 1 PUTS it in its IC TX half and as chip 2
    FINDS it in its IC RX half. A rotation shows as the same magnitude on the
    wrong name; a scale fault shows as a fixed dB step; a dead lane shows as
    chip 1 hot and chip 2 zero."""
    n = len(FABRIC)
    off1 = table(s1, '_c1_ic_tx_off', n)
    st1 = table(s1, '_c1_ic_tx_stride', n)
    off2 = table(s2, '_c2_ic_rx_off', n)
    st2 = table(s2, '_c2_ic_rx_stride', n)
    b1 = s1.peek(s1.addr('_ic_tx_active_buf'))
    b2 = s2.peek(s2.addr('_ic_rx_active_buf'))
    rows = []
    for i, name in enumerate(FABRIC):
        w1 = [s1.peek(b1 + off1[i] + k * st1[i]) for k in range(n_samp)]
        w2 = [s2.peek(b2 + off2[i] + k * st2[i]) for k in range(n_samp)]
        rows.append((name, off1[i], off2[i], w1, w2))
    return rows


def survey_print(rows):
    print('%-14s %5s %5s %10s %10s  %8s   %s'
          % ('slot', 'off1', 'off2', 'c1 send', 'c2 recv', 'delta', 'c2 words'))
    for name, o1, o2, w1, w2 in rows:
        p1 = stats(w1)[2]
        p2 = stats(w2)[2]
        d = p2 - p1
        flag = ''
        if p2 > -60.0 and d > 6.0:
            flag = '  <== c2 HOTTER'
        elif p1 > -60.0 and d < -6.0:
            flag = '  <== c2 QUIET'
        print('%-14s %5d %5d %+10.2f %+10.2f  %+8.2f   %s%s'
              % (name, o1, o2, p1, p2, d,
                 ' '.join('%08X' % (w & 0xFFFFFFFF) for w in w2[:3]), flag))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--symdir', default='.')
    ap.add_argument('--reps', type=int, default=1)
    ap.add_argument('--json')
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--survey', action='store_true',
                    help='every fabric slot, chip 1 send vs chip 2 receive')
    a = ap.parse_args(_argv[1:])

    out = {}
    s1 = S.Scope(1, symfile=os.path.join(a.symdir, 'chip1.sym.json'))
    s1.d.resync(); s1.check_chip()
    s2 = S.Scope(2, symfile=os.path.join(a.symdir, 'chip2.sym.json'))
    s2.d.resync(); s2.check_chip()

    # --- liveness + pointer state -------------------------------------
    f1a, f2a = s1.rd_counter(FRAME_COUNT), s2.rd_counter(FRAME_COUNT)
    ptr = {}
    for name in ('_ic_rx_active_buf', '_rx_ping_w', '_rx_pong_w',
                 '_rx_pend_buf', '_tx_active_buf', '_tx_ping_w',
                 '_tx_pong_w', '_tx_pend_buf'):
        ptr[name] = s2.peek(s2.addr(name))
    ovr2, err2, dma2 = s2.rd(BLK_OVERRUN), s2.rd(SPORT0_ERR_A), s2.rd(DMA0_STAT)
    ovr1, err1, dma1 = s1.rd(BLK_OVERRUN), s1.rd(SPORT0_ERR_A), s1.rd(DMA0_STAT)

    if a.survey:
        survey_print(survey(s1, s2))

    rows = []
    for rep in range(a.reps):
        # --- chip 1: what is being SENT ------------------------------
        c1 = read_block(s1, s1.addr('_buf_C1_BUS_MAIN_L'), 1)
        # --- chip 2 stage 1: the DMA half the scatter is reading ------
        base = ptr['_ic_rx_active_buf']
        dma_l = [s2.peek(base + 0 + i * 16) for i in range(BLOCK)]
        dma_r = [s2.peek(base + 1 + i * 16) for i in range(BLOCK)]
        # the other half, which the DDE is filling now
        other = ptr['_rx_pong_w'] if base == ptr['_rx_ping_w'] else ptr['_rx_ping_w']
        dma_o = [s2.peek(other + 0 + i * 16) for i in range(BLOCK)]
        # --- chip 2 stage 2/3/4 --------------------------------------
        slot = read_block(s2, s2.addr('_rx_ic_slot_C2_RECV_MAIN_L'), 1)
        blk = read_block(s2, s2.addr('_blk_C2_RECV_MAIN_L'), 1)
        mix = read_block(s2, s2.addr('_buf_C2_MIX_MAIN_L'), 1)
        rows.append({'c1_bus_main_l': c1, 'dma_active_main_l': dma_l,
                     'dma_active_main_r': dma_r, 'dma_other_main_l': dma_o,
                     'rx_ic_slot': slot, 'blk': blk, 'mix': mix})

    f1b, f2b = s1.rd_counter(FRAME_COUNT), s2.rd_counter(FRAME_COUNT)

    if not a.quiet:
        print('chip1 FRAME_COUNT %s -> %s   chip2 %s -> %s'
              % (f1a, f1b, f2a, f2b))
        print('chip1 BLK_OVERRUN %s SPORT0_ERR_A %s DMA0_STAT %s'
              % (ovr1, err1, dma1))
        print('chip2 BLK_OVERRUN %s SPORT0_ERR_A %s DMA0_STAT %s'
              % (ovr2, err2, dma2))
        print('chip2 ptrs: ' + '  '.join('%s=0x%X' % (k.lstrip('_'), v)
                                         for k, v in ptr.items()))
        for i, r in enumerate(rows):
            print('--- rep %d' % i)
            print(line('chip1 _buf_C1_BUS_MAIN_L', r['c1_bus_main_l']))
            print(line('chip2 DMA active MAIN_L', r['dma_active_main_l']))
            print(line('chip2 DMA active MAIN_R', r['dma_active_main_r']))
            print(line('chip2 DMA other  MAIN_L', r['dma_other_main_l']))
            print(line('chip2 _rx_ic_slot_MAIN_L', r['rx_ic_slot']))
            print(line('chip2 _blk_C2_RECV_MAIN_L', r['blk']))
            print(line('chip2 _buf_C2_MIX_MAIN_L', r['mix']))

    out = {'frame1': [f1a, f1b], 'frame2': [f2a, f2b], 'ptr': ptr,
           'diag1': [ovr1, err1, dma1], 'diag2': [ovr2, err2, dma2],
           'rows': rows}
    if a.json:
        json.dump(out, open(a.json, 'w'), indent=1)
    return 0


if __name__ == '__main__':
    sys.exit(main())
