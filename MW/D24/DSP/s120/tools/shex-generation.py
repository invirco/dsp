import re, sys
def load(path):
    mem, ext = {}, 0
    for line in open(path):
        line = line.strip()
        if not line.startswith(':'):
            continue
        n = int(line[1:3], 16)
        typ = line[7:9]
        body = line[9:9 + n * 2]
        if typ == '04':
            ext = int(body, 16) << 16
        elif typ == '00':
            addr = int(line[3:7], 16)
            for i, b in enumerate(bytes.fromhex(body)):
                mem[ext + addr + i] = b
    return mem
for path in sys.argv[1:]:
    mem = load(path)
    lo, hi = min(mem), max(mem)
    blob = bytes(mem.get(a, 0) for a in range(lo, hi + 1))
    print('== %s  %d bytes at 0x%08X' % (path, len(blob), lo))
    print('   slave addressed:', open(path).readline().strip()[3:7])
    for m in re.finditer(rb'// H1S[0-9] [A-Za-z ]+', blob):
        print('   identity string:', m.group().decode())
    gens = {'app / H1S1 on this unit (5412)': (5232, 5412, 5414, 5415),
            'panel source in Dropbox (17553)': (17312, 17553, 17555, 17556)}
    for gen, (e, s, t1, t2) in gens.items():
        pat = b''.join(x.to_bytes(4, 'little') for x in (0, e, s, t1, t2))
        print('   MATRIX[] generation %-34s %s' % (gen, 'FOUND' if pat in blob else '-'))
