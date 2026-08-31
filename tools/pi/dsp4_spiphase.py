#!/usr/bin/env python3
"""dsp4_spiphase.py — what the parameter link's word phase is actually doing.

D74. The stuck-partial-request recovery in `_diag_timer_isr` and the host's
own `SpiLink.realign()` both change the PARITY of the words sitting in the
DSP's SPI2 receive FIFO, and the firmware frames a request purely by
counting to two. This tool measures that directly instead of inferring it
from whichever bench script failed:

  --mode counters   read the D74 register block once (SPI_PART_SEEN/SKIP/FIX,
                    SPI_RX_COUNT/ERR_COUNT, live SPI_STAT.RFS)
  --mode inject     put a KNOWN single-word residue in the DSP's RX FIFO
                    (one host realign), then poll WITHOUT ever realigning
                    again and report whether, and after how long, the link
                    frames itself back up
  --mode pause      the same injection, then no traffic at all for --idle
                    seconds, then one read — separates "traffic heals it"
                    from "silence heals it", which is exactly the difference
                    DSP4_SPI_PARTIAL_FIX2 makes to the recovery's arming
  --mode scope      drive dsp4_scope.Scope.rd() the way busgold does and
                    report the counters on either side of it

Every mode prints the counter block before and after, so a run that heals
the link says which mechanism did it.
"""
import argparse, sys, time

sys.path.insert(0, '/home/app/dspboot')
sys.path.insert(0, '.')
from dsp4_config import SpiLink, frame
from dsp4_diag import DiagLink, DIAG_NOP

CS_GPIO = {1: 6, 2: 24}
RDY_GPIO = {1: 8, 2: 12}

# The D74 block plus what it has to be read against.
COUNTERS = [(0xE000, 'MAGIC'), (0xE001, 'CHIP_ID'), (0xE002, 'BOOT_STAGE'),
            (0xE00B, 'RX_COUNT'), (0xE00C, 'ERR_COUNT'), (0xE00D, 'SPI_STAT'),
            (0xE00E, 'STAT_STK'), (0xE00F, 'RESP_DROP'),
            (0xE01F, 'PART_FIX'), (0xE020, 'PART_TICKS'),
            (0xE021, 'PART_SEEN'), (0xE022, 'PART_SKIP'),
            (0xE023, 'REQ_WORD')]


def rfs(stat):
    """SPI_STAT.RFS -> words in the RX FIFO (0 empty, 2 = one word, 4 full)."""
    return (stat >> 12) & 7


def release(link):
    """Give the CS/RDY lines and spidev back.

    gpiod holds a line exclusively for the life of the request object, so a
    second SpiLink on the same chip (dsp4_scope.Scope, here) dies with
    EBUSY. Nothing in the bench tools ever needed two links in one process
    before; this one does, because the point is to hand the SAME link state
    from one reader to another."""
    for attr in ('_req_cs', '_req_rdy'):
        req = getattr(link, attr, None)
        if req is not None:
            try:
                req.release()
            except Exception:
                pass
    try:
        link.spi.close()
    except Exception:
        pass


class Phase:
    def __init__(self, chip, settle):
        self.chip = chip
        self.settle = settle
        self.open()

    def open(self):
        self.link = SpiLink('0.0', 1_000_000, CS_GPIO[self.chip],
                            rdy_gpio=RDY_GPIO[self.chip])
        self.d = DiagLink(self.link)

    def close(self):
        release(self.link)
        self.link = self.d = None

    # ---- a read that NEVER realigns -----------------------------------
    def ask(self, reg):
        """One paced ask+collect. Returns the value, or None if unanswered.

        Deliberately has no repair in it: realigning is the thing under
        test, so an observation that realigns cannot see the fault it is
        looking for."""
        want0 = int.from_bytes(frame(reg, 0, read=True)[0:4], 'big')
        self.d._fetch(reg, next_read=True)
        time.sleep(self.settle)
        w0, w1 = self.d._fetch()
        if w0 == want0:
            return w1
        if w1 == want0:
            return w0
        return None

    def ask_n(self, reg, n=6):
        """Ask up to n times, no realign. Returns (value, tries) or (None, n)."""
        for i in range(n):
            v = self.ask(reg)
            if v is not None:
                return v, i + 1
        return None, n

    def counters(self, label, repair=True):
        out = {}
        for addr, name in COUNTERS:
            try:
                out[name] = self.d.read(addr) if repair else self.ask(addr)
            except IOError:
                out[name] = None
        print('  %-10s ' % label + '  '.join(
            '%s=%s' % (k, ('-' if v is None else
                           ('0x%08X' % v if k in ('MAGIC', 'SPI_STAT',
                                                  'STAT_STK', 'REQ_WORD')
                            else v)))
            for k, v in out.items()))
        if out.get('SPI_STAT') is not None:
            print('             RFS=%d (0 empty, 2 = one word held, 4 full)'
                  % rfs(out['SPI_STAT']))
        return out


def mode_counters(p, a):
    p.counters('now')


def mode_phase(p, a):
    """Report the link's calibrated answer phase, and prove the decode.

    'post' is the arrangement that used to read every register as 0 off a
    perfectly healthy part (D74). Printing it, and the registers read
    through it, is the witness that the phase was detected rather than
    stumbled past."""
    for i in range(a.polls):
        p.d.phase = None
        ph = p.d.calibrate()
        vals = [p.d.read(r) for r in (0xE000, 0xE001, 0xE002, 0xE010)]
        print('  %2d  phase=%-5s MAGIC=0x%08X CHIP_ID=%d BOOT_STAGE=%d '
              'PRODUCT_ID=%d' % (i, ph, vals[0], vals[1], vals[2], vals[3]))


def mode_inject(p, a):
    print('=== inject: one host realign, then %d unrepaired polls at %.0f ms'
          % (a.polls, a.settle * 1000))
    p.d.resync()
    before = p.counters('before')
    v, tries = p.ask_n(0xE000, 4)
    print('  pre-inject MAGIC = %s in %d tries' % (
        '-' if v is None else '0x%08X' % v, tries))
    t0 = time.time()
    p.link.realign()
    healed = None
    misses = 0
    for i in range(a.polls):
        v = p.ask(0xE000)
        if v == 0xD5B40001:
            healed = i
            print('  HEALED after %d polls, %.1f ms (%d unanswered before it)'
                  % (i, (time.time() - t0) * 1000, misses))
            break
        misses += 1
    if healed is None:
        print('  NOT HEALED in %d polls / %.1f ms of continuous traffic'
              % (a.polls, (time.time() - t0) * 1000))
    after = p.counters('after')
    for k in ('RX_COUNT', 'ERR_COUNT', 'PART_FIX', 'PART_SEEN', 'PART_SKIP'):
        if before.get(k) is not None and after.get(k) is not None:
            print('  d%-10s %+d' % (k, after[k] - before[k]))


def mode_pause(p, a):
    print('=== pause: one host realign, then %.0f ms of SILENCE, then read'
          % (a.idle * 1000))
    p.d.resync()
    before = p.counters('before')
    p.link.realign()
    time.sleep(a.idle)
    v, tries = p.ask_n(0xE000, 4)
    print('  after the pause MAGIC = %s in %d unrepaired tries' % (
        '-' if v is None else '0x%08X' % v, tries))
    after = p.counters('after')
    for k in ('RX_COUNT', 'ERR_COUNT', 'PART_FIX', 'PART_SEEN', 'PART_SKIP'):
        if before.get(k) is not None and after.get(k) is not None:
            print('  d%-10s %+d' % (k, after[k] - before[k]))


def mode_scope(p, a):
    import dsp4_scope as S
    print('=== scope: Scope(%d).rd() the way busgold drives it' % p.chip)
    before = p.counters('before')
    p.close()
    sc = S.Scope(p.chip)
    sc.d.resync()
    ok = 0
    for i in range(a.polls):
        try:
            got = sc.rd(0xE001)
            ok += (got == p.chip)
            if got != p.chip:
                print('  read %d: CHIP %s (expected %d)' % (i, got, p.chip))
        except IOError as e:
            print('  read %d: %s' % (i, e))
    print('  %d of %d check_chip reads correct' % (ok, a.polls))
    release(sc.d.link)
    del sc
    p.open()
    after = p.counters('after')
    for k in ('RX_COUNT', 'ERR_COUNT', 'PART_FIX', 'PART_SEEN', 'PART_SKIP'):
        if before.get(k) is not None and after.get(k) is not None:
            print('  d%-10s %+d' % (k, after[k] - before[k]))


def mode_raw(p, a):
    """Print the RAW words the host clocks in, transaction by transaction.

    Everything above this interprets the stream; in a broken state the
    interpretation is the thing in doubt. This prints what came back with
    no repair and no voting, so a wedged link says which of the two halves
    is out of phase -- the DSP's request framing (echo word wrong) or the
    host's answer framing (right words, wrong pairing)."""
    want0 = int.from_bytes(frame(0xE001, 0, read=True)[0:4], 'big')
    print('  want echo 0x%08X; ask = E001|READ, collect = NOP' % want0)
    for i in range(a.polls):
        if a.realign_at == i:
            p.link.realign()
            print('  %2d  --- host realign (one word) ---' % i)
        w0, w1 = p.d._fetch(0xE001, next_read=True)
        print('  %2d  ask     rx 0x%08X 0x%08X%s' % (
            i, w0, w1, '   <-- echo in w0' if w0 == want0 else
            ('   <-- echo in w1' if w1 == want0 else '')))
        time.sleep(a.settle)
        w0, w1 = p.d._fetch()
        print('  %2d  collect rx 0x%08X 0x%08X%s' % (
            i, w0, w1, '   <-- echo in w0' if w0 == want0 else
            ('   <-- echo in w1' if w1 == want0 else '')))
        if a.gap:
            time.sleep(a.gap)


def mode_diagnose(p, a):
    """Run at the moment a bench script says the link is dead.

    Three questions in one pass, in the order that separates the two
    halves of the link: does it answer at all; does SILENCE mend it (the
    stuck-partial recovery needs the request counter to stand still, so
    silence is the only thing that can arm it); does one host realign mend
    it (a word of RX parity, which is the other half). Whichever of the
    two mends it names which one broke."""
    def raw(tag, n=6):
        """One ask, then n collects, every word printed.

        The offset between question and answer is the whole diagnosis, and
        it is only visible if the ASK's own returned words are printed too
        and the collects are run out past one: an answer that is a whole
        transaction late looks identical to no answer at all when you stop
        after the first collect, which is exactly what Scope._ask does and
        dsp4_diag.read (24 collects) does not."""
        want0 = int.from_bytes(frame(0xE001, 0, read=True)[0:4], 'big')
        nop0 = int.from_bytes(frame(0xE0FE, 0)[0:4], 'big')

        def mark(w0, w1):
            if w0 == want0:
                return 'E001 echo in w0 (aligned answer)'
            if w1 == want0:
                return 'E001 echo in w1 (rotated by one word)'
            if w0 == nop0 or w1 == nop0:
                return 'NOP echo — this is the PREVIOUS transaction answer'
            return ''
        w0, w1 = p.d._fetch(0xE001, next_read=True)
        print('  %-13s ask      0x%08X 0x%08X  %s' % (tag, w0, w1, mark(w0, w1)))
        time.sleep(p.settle)
        hits = 0
        for i in range(n):
            w0, w1 = p.d._fetch()
            m = mark(w0, w1)
            hits += w0 == want0 or w1 == want0
            print('  %-13s coll %d   0x%08X 0x%08X  %s' % (tag, i, w0, w1, m))
        print('  %-13s answered on %d of %d collects' % (tag, hits, n))
        return hits

    raw('broken?')
    time.sleep(a.idle)
    raw('after %.0fms' % (a.idle * 1000))
    p.link.realign()
    raw('after realign')
    p.counters('repaired')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chip', type=int, default=1, choices=(1, 2))
    ap.add_argument('--mode', default='counters',
                    choices=('counters', 'inject', 'pause', 'scope',
                             'raw', 'diagnose', 'phase'))
    ap.add_argument('--polls', type=int, default=40)
    ap.add_argument('--settle', type=float, default=0.002)
    ap.add_argument('--idle', type=float, default=0.05)
    ap.add_argument('--gap', type=float, default=0.0,
                    help='extra idle between transactions, seconds')
    ap.add_argument('--realign-at', type=int, default=-1,
                    help='inject one host realign before this poll index')
    a = ap.parse_args()
    p = Phase(a.chip, a.settle)
    {'counters': mode_counters, 'inject': mode_inject,
     'pause': mode_pause, 'scope': mode_scope, 'raw': mode_raw,
     'diagnose': mode_diagnose, 'phase': mode_phase}[a.mode](p, a)


if __name__ == '__main__':
    main()
