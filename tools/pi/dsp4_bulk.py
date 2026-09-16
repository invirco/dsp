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
    5. wait for SPI_RDY HIGH = the GO-ack (S62; the pin is held low from
       the moment GO lands until the stream is armed)
    6. CS low, clock (n + 2 + SLACK) words at `hz`, CS high
    7. wait for SPI_RDY LOW (the tick has seen the stream end) and then
       HIGH (the port is back on the parameter link) -- no transaction in
       between, so the restore's EN cycle can never land inside one
    8. find BULK_MAGIC at any byte offset, then n, then the n words
    9. check the two running sums against step 3
   10. rephase the link, confirm BULK_CTL reads 0 and BULK_RUNS has moved

On an image without `_bulk_rdy_hs` (the S61 pair) steps 5 and 7 fall back to
S61's fixed waits (3 ms and DSP4_BULK_POST_S).

RECOVERY (S62-2). If the link will not phase after a stream it is almost
always one stray word in the part's RX FIFO: every request is then framed a
word out, and the firmware's stuck-partial discard only fires after the link
has stood still for 3 ms. `rephase()` stands still 10 ms, re-phases and
proves it with a MAGIC read, up to REPHASE_S; it never waits minutes.

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
# Only used against images WITHOUT the RDY handshake (S61 pair).
POST_S = float(__import__('os').environ.get('DSP4_BULK_POST_S', '0.030'))
GO_S = 0.003
RDY_TIMEOUT_S = 1.0          # a missing edge is a failure, not a wait
LOW_SEEN_S = 0.050           # look this long for the release low, then go on
REPHASE_S = 1.0              # bound on rephase()
STILL_S = 0.010              # > 3 ticks: lets the stuck-partial discard fire
DIAG_MAGIC = 0xD5B40001


def available(sc):
    return '_bulk_state' in sc.sym


def handshake(sc):
    """True when the image drives SPI_RDY as the bulk handshake (S62)."""
    return '_bulk_rdy_hs' in sc.sym


def _wait_rdy(link, level, timeout=RDY_TIMEOUT_S):
    """Poll SPI_RDY for `level` (1 = the link's ready sense). Returns the
    seconds it took, or None on timeout."""
    want = link.rdy_ready if level else 1 - link.rdy_ready
    t0 = time.monotonic()
    end = t0 + timeout
    while True:
        if link.rdy.get_value() == want:
            return time.monotonic() - t0
        if time.monotonic() > end:
            return None


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


def rephase(sc, limit=REPHASE_S):
    """Put the parameter link back in phase, bounded. Returns the seconds a
    repair took (0.0 when the first resync phased it). Raises IOError after
    `limit`.

    The first attempt is the ordinary resync. If that cannot phase, the usual
    cause (S62-1) is a stray word in the part's RX FIFO, so every request is
    framed one word out -- and host traffic keeps the firmware's discard
    disarmed, which is how S61 stayed unphaseable for two minutes. So: stand
    still STILL_S, re-phase once, and believe it only if MAGIC reads back."""
    t0 = time.monotonic()
    try:
        sc.d.resync()
        if sc.d.read(0xE000) == DIAG_MAGIC:
            return 0.0
    except (IOError, OSError):
        pass
    last = None
    while time.monotonic() - t0 < limit:
        time.sleep(STILL_S)
        try:
            sc.d.phase = None
            sc.d.calibrate(tries=1)
            if sc.d.read(0xE000) == DIAG_MAGIC:
                return time.monotonic() - t0
            last = 'MAGIC read back wrong'
        except (IOError, OSError) as e:
            last = str(e)[:80]
    raise IOError('link would not re-phase in %.1f s: %s' % (limit, last))


_resync = rephase                # S61 name, kept for callers


def read(sc, addr, n, hz=DEFAULT_HZ, tries=3, log=None):
    """Stream n words from word address `addr`. Returns (words, info)."""
    link = sc.d.link
    hs = handshake(sc) and link.rdy is not None
    info = {'addr': addr, 'n': n, 'hz': hz, 'handshake': hs, 'attempts': []}
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
        if hs:
            dt = _wait_rdy(link, 1)             # GO-ack: armed, clock now
            if dt is None:
                a['fail'] = 'no GO-ack on SPI_RDY'
                info['attempts'].append(a)
                a['rephase_s'] = round(rephase(sc), 3)
                continue
            a['go_ack_ms'] = round(dt * 1000, 2)
        else:
            time.sleep(GO_S)
        nbytes = 4 * (n + 2 + SLACK)
        link.spi.max_speed_hz = int(hz)
        link.line.set_value(0)
        try:
            rx = bytes(link.spi.xfer3(bytes(nbytes)))
        finally:
            link.line.set_value(1)
            link.spi.max_speed_hz = LINK_HZ
        a['t_stream_s'] = round(time.time() - t1, 3)

        # Let the port come back BEFORE parsing (parsing 16k words takes
        # longer than the tick's low phase), so a failed attempt also leaves a
        # working link for the retry.
        if hs:
            dl = _wait_rdy(link, 0, LOW_SEEN_S)  # the tick saw the stream end
            if dl is None:
                # Missed it (or a late tick): not an error. The firmware only
                # restores after 3 ms of silence on the wire, and every
                # transaction below waits for RDY high.
                a['release_low_unseen'] = True
                dl = LOW_SEEN_S
            dh = _wait_rdy(link, 1)
            if dh is None:
                a['rdy_release'] = 'RDY stayed low'
            else:
                a['release_ms'] = round((dl + dh) * 1000, 2)
        else:
            time.sleep(POST_S)
        words, off = _parse(rx, n)
        a['header_at_byte'] = off
        try:
            a['rephase_s'] = round(rephase(sc), 3)
        except IOError as e:
            a['fail'] = str(e)
            info['attempts'].append(a)
            continue
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
