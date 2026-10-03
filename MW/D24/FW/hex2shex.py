#!/usr/bin/env python3
# Convert an Intel hex to the Matrix "shex" flash-stream format:
#  - record 1: :02<MCUID>04<ext-addr>CS   (extended-address record, MCU id in place of the 0000 field)
#  - data:     16-byte aligned records, checksum replaced by literal "CS"
#  - EOF:      :00000001CS      (type-05 start-address records dropped)
import sys

def parse_hex(path):
    mem = {}
    ext = 0
    for line in open(path):
        line = line.strip()
        if not line.startswith(":"):
            continue
        n = int(line[1:3], 16)
        addr = int(line[3:7], 16)
        typ = int(line[7:9], 16)
        data = bytes.fromhex(line[9:9 + n * 2])
        if typ == 4:
            ext = int(line[9:13], 16) << 16
        elif typ == 0:
            for i, b in enumerate(data):
                mem[ext + addr + i] = b
    return mem

def emit_shex(mem, mcuid, out):
    base = min(mem) & 0xFFFF0000
    lines = [":02%s04%04XCS" % (mcuid, base >> 16)]
    lo = min(mem) & ~0xF
    hi = max(mem)
    a = lo
    while a <= hi:
        chunk = bytes(mem.get(a + i, 0xFF) for i in range(16))
        if any((a + i) in mem for i in range(16)):
            lines.append(":10%04X00%sCS" % ((a - base) & 0xFFFF, chunk.hex().upper()))
        a += 16
    lines.append(":00000001CS")
    open(out, "w", newline="\n").write("\n".join(lines) + "\n")
    return len(lines)

if __name__ == "__main__":
    hexfile, mcuid, out = sys.argv[1:4]
    mem = parse_hex(hexfile)
    n = emit_shex(mem, mcuid, out)
    print("%s -> %s: %d records, %d bytes image" % (hexfile, out, n, len(mem)))
