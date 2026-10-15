#!/usr/bin/env python3
# Turn a raw app .bin (linked at 0x08001000) into a bootable image:
# pad to 4 bytes, patch the length into the app header (+0x14), append
# zlib CRC32. The bootloader verifies both before jumping.
import struct
import sys
import zlib

APP_MAGIC = 0x4D583236  # 'MX26'

bin_path, out_path = sys.argv[1], sys.argv[2]
d = bytearray(open(bin_path, 'rb').read())
while len(d) % 4:
    d.append(0xFF)
magic = struct.unpack_from('<I', d, 0x10)[0]
assert magic == APP_MAGIC, f'app header magic missing (got 0x{magic:08X})'
struct.pack_into('<I', d, 0x14, len(d))
crc = zlib.crc32(d) & 0xFFFFFFFF
d += struct.pack('<I', crc)
open(out_path, 'wb').write(d)
print(f'{out_path}: {len(d)} bytes, crc 0x{crc:08x}')
