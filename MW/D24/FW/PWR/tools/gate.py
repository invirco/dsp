#!/usr/bin/env python3
"""Size + CRC gate for the power-MCU images (make sizes).

boot.bin must fit the 4 KB WRP block; each .img must fit the 12 KB app
region with its CRC, carry the 'MX26' magic and the right length at +0x14,
and its appended CRC32 must match — the same check the bootloader makes.
"""
import struct
import sys
import zlib

BOOT_MAX = 4 * 1024
APP_MAX = 12 * 1024
MAGIC = 0x4D583236

ok = True
for path in sys.argv[1:]:
    d = open(path, 'rb').read()
    if path.endswith('.bin'):
        good = len(d) <= BOOT_MAX
        print('%-18s %5d B of %d  %s' % (path, len(d), BOOT_MAX, 'OK' if good else 'TOO BIG'))
    else:
        magic, ln = struct.unpack_from('<II', d, 0x10)
        crc = struct.unpack_from('<I', d, ln)[0] if ln + 4 <= len(d) else None
        good = (len(d) <= APP_MAX and magic == MAGIC and ln == len(d) - 4
                and crc == zlib.crc32(d[:ln]) & 0xFFFFFFFF)
        print('%-18s %5d B of %d  len 0x%04X crc %s  %s' % (
            path, len(d), APP_MAX, ln, '0x%08x' % crc if crc is not None else '-',
            'OK' if good else 'FAIL'))
    ok &= good
sys.exit(0 if ok else 1)
