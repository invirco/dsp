#!/usr/bin/env python3
"""dsp4_bulk.py — read a DM region in ONE streamed SPI transfer (S61).

The firmware half is MW/D32/DSP/SHARC/src/bulk_read.asm (DSP4_TEST_NODES
builds). A peek costs three parameter-link transactions and each one ~100 us
whatever the clock (findings S61-1), so a 16,384-word capture took 12.3 s.
This hands SPI2's transmit path to DMA for the region and clocks it in one
go.

THE HANDSHAKE
    1. BULK_ADDR = word address, BULK_LEN = n          (voted write-verify)
    2. BULK_CTL = 1 (arm); poll BULK_CTL until 2       (the tick checksums
                                                        1,024 words per ms)
    3. read BULK_SUM1 / BULK_SUM2 / BULK_RUNS
    4. BULK_CTL = 2 (GO) -- the part does not answer it
    5. CS low, clock (n + 2 + SLACK) words at `hz`, CS high
    6. find BULK_MAGIC at any byte offset, then n, then the n words
    7. check the two running sums against step 3
    8. wait for the tick to give the port back (BULK_CTL reads 0 and
       BULK_RUNS has moved), resync the link

THE ERROR CHECK. s1 = sum w, s2 = sum of the running s1, both mod 2^32,
computed by the DSP over the memory BEFORE the stream and by the host over
what arrived. s2 is position-weighted, so a dropped, repeated, swapped or
shifted word fails it as well as a flipped bit. A failure retries.

Library: `read(sc, addr, n, hz=...) -> (words, info)` with an open
dsp4_scope.Scope. CLI:
    dsp4_bulk.py SYMBOL|0xADDR N [--symdir DIR] [--hz HZ] [--chip 1|2]
"""
import sys
import time

A_ADDR, A_LEN, A_CTL = 0xE0D0, 0xE0D1, 0xE0D2
A_SUM1, A_SUM2, A_RUNS, A_ABORT, A_ERR = 0xE0D3, 0xE0D4, 0xE0D5, 0xE0D6, 0xE0D7
A_DSTAT, A_MS = 0xE0D8, 0xE0D9
MAGIC = 0xB0CA5E61
SLACK = 8                      # extra words clocked past the tail
DEFAULT_HZ = 10_000_000
LINK_HZ = 1_000_000            # what the parameter link is left at
# The tick gives the port back 97-101 ms after GO at 10 MHz, 1-3 ms after the
# host's last clock, later when a block delays the tick. A 4 ms wait overlapped
# it once in 389 streams and left the link unphaseable for minutes (S61-2).
POST_S = float(__import__('os').environ.get('DSP4_BULK_POST_S', '0.030'))


def available(sc):
    return '_bulk_state' in sc.sym


def sums(words):
    s1 = s2 = 0
    for w in words:
        s1 = (s1 + w) & 0xFFFFFFFF
        s2 = (s2 + s1) & 0xFFFFFFFF
    return s1, s2


def _parse(rx, n):
    """Find MAGIC, n at any byte offset; return the n words or None."""
    m = MAGIC.to_bytes(4, 'big')
    nb = n.to_bytes(4, 'big')
    start = 0
    while True:
        i = rx.find(m, start)
        if i < 0 or i > 4 * SLACK:
            return None, None
        if rx[i + 4:i + 8] == nb:
            body = rx[i + 8:i + 8 + 4 * n]
            if len(body) < 4 * n:
                return None, i
            return [int.from_bytes(body[k:k + 4], 'big')
                    for k in range(0, 4 * n, 4)], i
        start = i + 1


def _wait_state(sc, want, timeout):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if sc._ask(A_CTL) == want:
                if sc.rd(A_CTL) == want:
                    return True
        except (IOError, OSError):
            pass
        time.sleep(0.002)
    return False


def _resync(sc):
    for _ in range(8):
        try:
            sc.d.resync()
            return
        except (IOError, OSError):
            time.sleep(0.01)
    sc.d.resync()


def read(sc, addr, n, hz=DEFAULT_HZ, tries=3, log=None):
    """Stream n words from word address `addr`. Returns (words, info)."""
    link = sc.d.link
    info = {'addr': addr, 'n': n, 'hz': hz, 'attempts': []}
    t_all = time.time()
    for attempt in range(tries):
        a = {}
        t0 = time.time()
        sc.wr(A_ADDR, addr)
        sc.wr(A_LEN, n)
        sc.d.write(A_CTL, 1)
        if not _wait_state(sc, 2, 1.0 + n / 1024 * 0.01):
            a['fail'] = 'never armed (state %s)' % sc.rd(A_CTL)
            info['attempts'].append(a)
            continue
        s1, s2 = sc.rd(A_SUM1), sc.rd(A_SUM2)
        runs0, abort0 = sc.rd(A_RUNS), sc.rd(A_ABORT)
        a['t_arm_s'] = round(time.time() - t0, 3)

        t1 = time.time()
        link.wait_ready()
        link.xfer(A_CTL, 2)                     # GO: unanswered
        time.sleep(0.003)
        nbytes = 4 * (n + 2 + SLACK)
        link.spi.max_speed_hz = int(hz)
        link.line.set_value(0)
        try:
            rx = bytes(link.spi.xfer3(bytes(nbytes)))
        finally:
            link.line.set_value(1)
            link.spi.max_speed_hz = LINK_HZ
        a['t_stream_s'] = round(time.time() - t1, 3)

        words, off = _parse(rx, n)
        a['header_at_byte'] = off
        # Give the port back before judging, so a failed attempt leaves a
        # working link for the retry.
        time.sleep(POST_S)
        _resync(sc)
        if not _wait_state(sc, 0, 4.0):
            a['fail'] = 'port never returned (state %s)' % sc.rd(A_CTL)
            info['attempts'].append(a)
            continue
        runs1, abort1 = sc.rd(A_RUNS), sc.rd(A_ABORT)
        a.update({'runs': runs1 - runs0, 'aborts': abort1 - abort0,
                  'dstat': '0x%08X' % sc.rd(A_DSTAT), 'ms': sc.rd(A_MS)})
        a['t_total_s'] = round(time.time() - t0, 3)
        if words is None:
            a['fail'] = 'no header (first bytes %s)' % rx[:16].hex()
        elif sums(words) != (s1, s2):
            h1, h2 = sums(words)
            a['fail'] = ('checksum: part %08x/%08x host %08x/%08x'
                         % (s1, s2, h1, h2))
        info['attempts'].append(a)
        if log:
            log('  bulk attempt %d: %s' % (attempt + 1, a))
        if 'fail' not in a:
            info['read_s'] = round(time.time() - t_all, 3)
            info['sum'] = '%08x/%08x' % (s1, s2)
            return words, info
    raise IOError('bulk read failed %d times: %s' % (tries, info['attempts']))


def main(argv):
    sys_argv = list(argv)
    symdir, hz, chip = '/home/app/s61', DEFAULT_HZ, 1
    rest = []
    i = 0
    while i < len(sys_argv):
        if sys_argv[i] == '--symdir':
            symdir = sys_argv[i + 1]; i += 2
        elif sys_argv[i] == '--hz':
            hz = int(float(sys_argv[i + 1])); i += 2
        elif sys_argv[i] == '--chip':
            chip = int(sys_argv[i + 1]); i += 2
        else:
            rest.append(sys_argv[i]); i += 1
    saved = sys.argv
    sys.argv = ['s']
    sys.path.insert(0, '/home/app/dspboot')
    import dsp4_scope as S                               # noqa: E402
    sys.argv = saved
    sc = S.Scope(chip, symfile='%s/chip%d.sym.json' % (symdir, chip))
    sc.check_chip()
    if not available(sc):
        raise SystemExit('no _bulk_state in %s: not an S61 image' % symdir)
    what, n = rest[0], int(rest[1])
    addr = int(what, 16) if what.startswith('0x') else sc.addr(what)
    words, info = read(sc, addr, n, hz, log=print)
    print(info)
    for k in range(0, min(n, 32), 8):
        print('%5d: ' % k + ' '.join('%08x' % w for w in words[k:k + 8]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
