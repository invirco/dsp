#!/usr/bin/env python3
"""ldr_stream.py — inspect and surgically edit SHARC+ boot streams (.ldr).

Written 2026-08-21 to find out why the D32 firmware was accepted by the
boot host end to end and then never executed an instruction. The answer
was in the block structure, not the code, and none of the CCES tools show
it — hence this one.

Stream format (ADSP-2156x boot ROM, HRM ch.36). A stream is a chain of
16-byte block headers, little-endian:

    word 0  block code   0xAD << 24 | checksum << 16 | flags << 8 | bcode
    word 1  target address (system view, e.g. 0x282xxxxx for core L1)
    word 2  byte count
    word 3  argument

The checksum is the XOR of the other 15 header bytes. Flag bit 0 marks a
ZERO-FILL block: the count is still the number of bytes written, but the
payload is NOT in the stream, so the next header follows immediately.
Flag 0x80 marks the FINAL block; the first block of a stream carries
0x50 and its argument is the byte count of everything after its own
header.

THE RULE THIS TOOL EXISTS TO ENFORCE. A zero-fill block that is followed
by any further block desynchronises the boot kernel and the part never
runs — measured 2026-08-21 on rev C, chip 2, by front-inserting a single
640-byte fill into an image that boots 3/3 (it then booted 0/3) and
appending the identical block instead (3/3 again). elfloader emits
exactly that shape by default, which is why every D32 production image
built before this date was unbootable. `-NoFillBlock` in build.sh's
LDRFLAGS is the fix; `check` here is the guard that stops it coming back.

Subcommands:
    dump      <ldr>...                     block table + summary
    check     <ldr>...                     exit non-zero on a bad stream
    poke      <in> <out> <addr> <n> [fill] [front]
                                           insert one block, to test
                                           whether a region or a block
                                           shape is survivable
    graft     <prefix> <N|all> <tail> <out>
                                           first N blocks of `prefix` in
                                           front of `tail`'s payload, so
                                           a boot proves the kernel
                                           consumed them — this is how
                                           the offending block is found
"""
import struct
import sys

SIG = 0xAD
FLAG_FILL = 0x01
FLAG_FINAL = 0x80


def parse(data, path='<stream>'):
    """Walk the block chain. Raises ValueError on a malformed stream."""
    off = 0
    out = []
    while off + 16 <= len(data):
        bc, tgt, cnt, arg = struct.unpack_from('<IIII', data, off)
        if (bc >> 24) != SIG:
            raise ValueError(f'{path}: bad block signature at offset {off} '
                             f'(block code 0x{bc:08x})')
        flg = (bc >> 8) & 0xFF
        span = 16 if (flg & FLAG_FILL) else 16 + cnt
        out.append({'off': off, 'raw': data[off:off + span], 'flg': flg,
                    'tgt': tgt, 'cnt': cnt, 'arg': arg,
                    'fill': bool(flg & FLAG_FILL),
                    'final': bool(flg & FLAG_FINAL)})
        off += span
    if off != len(data):
        raise ValueError(f'{path}: {len(data) - off} trailing bytes — the '
                         f'block chain does not span the file')
    return out


def _fix_header(buf):
    """Recompute the header XOR checksum in-place over buf[:16]."""
    buf = bytearray(buf)
    buf[2] = 0
    x = 0
    for i, b in enumerate(buf[:16]):
        if i != 2:
            x ^= b
    buf[2] = x
    return bytes(buf)


def _rebuild(info, body, final):
    """Reassemble a stream and refresh the first block's byte-count arg."""
    out = bytearray(info + b''.join(body) + final)
    struct.pack_into('<I', out, 12, len(out) - 16)
    out[:16] = _fix_header(out[:16])
    return bytes(out)


def _make_header(flags, tgt, cnt, arg=0, bcode=0x01):
    hdr = struct.pack('<IIII', (SIG << 24) | (flags << 8) | bcode,
                      tgt, cnt, arg)
    return _fix_header(hdr)


def bad_fills(blocks):
    """Fill blocks with anything after them — the unbootable shape."""
    return [b for i, b in enumerate(blocks)
            if b['fill'] and i < len(blocks) - 1]


def cmd_dump(paths, verbose=True):
    for p in paths:
        blocks = parse(open(p, 'rb').read(), p)
        data = sum(b['cnt'] for b in blocks if not b['fill'])
        fills = [b for b in blocks if b['fill']]
        size = sum(len(b['raw']) for b in blocks)
        print(f'== {p}  size={size}  blocks={len(blocks)}  payload={data}B  '
              f'fillblocks={len(fills)}  fillbytes={sum(b["cnt"] for b in fills)}')
        if verbose:
            print('       off      code        target      bytes  flags')
            for b in blocks:
                kind = ('ZEROFILL' if b['fill']
                        else 'FINAL' if b['final'] else '')
                print(f'  {b["off"]:9d}  0x{b["flg"]:02x}      '
                      f'0x{b["tgt"]:08x} {b["cnt"]:10d}  {kind}')


def cmd_check(paths):
    rc = 0
    for p in paths:
        try:
            blocks = parse(open(p, 'rb').read(), p)
        except ValueError as exc:
            print(f'FAIL {exc}')
            rc = 1
            continue
        bad = bad_fills(blocks)
        if bad:
            rc = 1
            print(f'FAIL {p}: {len(bad)} zero-fill block(s) are followed by '
                  f'further blocks. The SPI target boot kernel loses stream '
                  f'sync after such a block and the part never executes. '
                  f'Rebuild with elfloader -NoFillBlock. First offender: '
                  f'0x{bad[0]["tgt"]:08x} ({bad[0]["cnt"]} B) at offset '
                  f'{bad[0]["off"]}.')
        else:
            print(f'ok   {p}: {len(blocks)} blocks, no mid-stream fill blocks')
    return rc


def cmd_poke(argv):
    src, dst, addr, nbytes = argv[0], argv[1], int(argv[2], 0), int(argv[3], 0)
    opts = argv[4:]
    fill, front = 'fill' in opts, 'front' in opts
    blocks = parse(open(src, 'rb').read(), src)
    extra = (_make_header(FLAG_FILL, addr, nbytes) if fill
             else _make_header(0x00, addr, nbytes) + b'\x00' * nbytes)
    body = [b['raw'] for b in blocks[1:-1]]
    body = [extra] + body if front else body + [extra]
    out = _rebuild(blocks[0]['raw'], body, blocks[-1]['raw'])
    open(dst, 'wb').write(out)
    parse(out, dst)
    print(f'{dst}: {len(out)} B, +{nbytes} B '
          f'{"ZEROFILL" if fill else "data"} block at 0x{addr:08x} '
          f'({"front" if front else "end"})')


def cmd_graft(argv):
    pre, n_arg, tail, dst = argv[:4]
    P = parse(open(pre, 'rb').read(), pre)
    T = parse(open(tail, 'rb').read(), tail)
    pbody = [b['raw'] for b in P[1:-1]]
    tbody = [b['raw'] for b in T[1:-1]]
    n = len(pbody) if n_arg == 'all' else int(n_arg)
    out = _rebuild(P[0]['raw'], pbody[:n] + tbody, T[-1]['raw'])
    open(dst, 'wb').write(out)
    parse(out, dst)
    print(f'{dst}: {len(out)} B, prefix blocks {n}/{len(pbody)}, '
          f'tail {len(tbody)}')


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    cmd, rest = argv[1], argv[2:]
    if cmd == 'dump':
        cmd_dump([a for a in rest if not a.startswith('-')],
                 verbose='-q' not in rest)
    elif cmd == 'check':
        return cmd_check(rest)
    elif cmd == 'poke':
        cmd_poke(rest)
    elif cmd == 'graft':
        cmd_graft(rest)
    else:
        print(f'unknown subcommand {cmd!r}')
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
