#!/usr/bin/env python3
"""dsp4_scope — stimulus and capture inside the DSP.

The Pi audio round-trip carries an 8x gain error and reorders samples by
up to ~190 places (measured 2026-08-23), so it cannot carry a measurement.
This drives src/scope.asm instead: inject a known word straight into an
input slot after scatter, record a node output every sample, read the
buffer back over the parameter link. Nothing crosses the audio channel.

  --inj   symbol of the input slot to drive   (omit for capture-only)
  --src   symbol of the node buffer to record
  --amp   value to inject, as Q4.28 or 0x-hex
  --mode  impulse | step
  --n     samples to read back (<= 1024)

An impulse response characterises a biquad completely, so EQ/FILT is an
impulse plus an FFT on the host rather than a swept sine.
"""
import argparse, json, sys, time

sys.path.insert(0, '/home/app/dspboot')
from dsp4_config import SpiLink
from dsp4_diag import DiagLink, frame

DIAG_PEEK_ADDR = 0xE0F0
DIAG_PEEK_DATA = 0xE0F1
# Named scope registers. One transaction each -- the peek window needs two
# and under audio load the second can be answered from a different request.
SCOPE_SRC, SCOPE_INJ, SCOPE_AMP = 0xE0E0, 0xE0E1, 0xE0E2
SCOPE_MODE, SCOPE_ARM, SCOPE_RD = 0xE0E3, 0xE0E4, 0xE0E5
SCOPE_DATA, SCOPE_LEN = 0xE0E6, 0xE0E7
SCOPE_RUNS, SCOPE_IDX = 0xE0E8, 0xE0E9
CS_GPIO = {1: 6, 2: 24}
RDY_GPIO = {1: 8, 2: 12}
SETTLE = 0.002     # three audio block periods; see Scope.rd
SCOPE_MAX = 1024   # buffer capacity; the REGISTER is SCOPE_LEN above


class Scope:
    def __init__(self, chip, symfile=None):
        self.chip = chip
        self.sym = json.load(open(symfile or 'chip%d.sym.json' % chip))
        # RDY GPIO is per chip and MUST be passed: without it SpiLink
        # defaults to chip 1's line, and a Scope(2) then answers as chip 1
        # while being read with chip 2's symbol addresses. Bench
        # 2026-08-23: DIAG_CHIP_ID read 1 from a Scope(2), and a whole
        # chip-2 chain walk read as dead because of it.
        self.d = DiagLink(SpiLink('0.0', 1_000_000, CS_GPIO[chip],
                                  rdy_gpio=RDY_GPIO[chip]))
        self.d.resync()

    def check_chip(self):
        """Refuse to measure the wrong part. dsp4_boot.py can silently leave
        chip 2 running chip 1's firmware, and a mis-addressed link answers
        as chip 1 regardless -- either way every symbol address is then
        wrong and the capture is fiction."""
        got = self.rd(0xE001)
        if got != self.chip:
            raise SystemExit('link answers as CHIP %d, expected %d — '
                             'wrong CS/RDY or chip 2 is running chip 1 firmware'
                             % (got, self.chip))

    def addr(self, name):
        if name.startswith('0x'):
            return int(name, 16)
        if name not in self.sym:
            raise SystemExit('no symbol %r in the chip %d map' % (name, self.chip))
        return self.sym[name]

    def peek(self, a, patience=40):
        """Patient read. Under audio load the block loop answers a block
        later, and an impatient reader calls that a dead link -- which is
        exactly how a healthy card at STAGE 7 got written off twice."""
        last = None
        for _ in range(patience):
            try:
                self.d.write(DIAG_PEEK_ADDR, a)
                return self.d.read(DIAG_PEEK_DATA)
            except IOError as e:
                last = e
        raise IOError('peek 0x%X never answered in %d tries: %s' % (a, patience, last))

    def rd(self, reg, need=2, limit=12):
        """Read one register: paced ask, settle, single collect, voted.

        The DSP services this link ONCE PER AUDIO BLOCK (the block loop
        polls it), so the host must not out-run it. dsp4_diag.read() fires
        an ask and then up to 24 collect NOPs back to back -- 25 requests
        against one answer per 667 us -- which overruns the response FIFO
        and desynchronises the stream. Its answers then come back as a
        well-formed (echo, 0) rather than an error, so a wrong value is
        indistinguishable from a real one: bench 2026-08-23 read
        _scope_len as 0 when it is 1024, and a gain coefficient as
        0xE0FE0000, which is a request word.

        Asking once and waiting SETTLE (three block periods) before a
        single collect measured 25/25 correct where the unpaced path
        managed 8/25.

        CORRECTED 2026-08-31 (D74). This used to say the pair "normally
        arrives ROTATED (value, echo) -- that is this silicon's steady
        state, not a fault -- so both arrangements are accepted, with the
        echo deciding". There are two arrangements, they are NOT
        interchangeable, and the echo cannot tell them apart: it is in
        word 1 in both. Accepting either is what made a running part read
        CHIP 0. The arrangement comes from DiagLink.calibrate().
        """
        seen = {}
        for i in range(limit):
            v = self._ask(reg)
            if v is None:
                # A lost answer leaves master and slave a word apart; the
                # next ask inherits that, so re-align rather than simply
                # asking again into a stream that is still shifted.
                if i % 3 == 2:
                    self.d.link.realign()
                    self.d.phase = None       # a realign moves the window
                continue
            seen[v] = seen.get(v, 0) + 1
            # A DROPPED ANSWER ON THIS LINK ALWAYS READS AS ZERO, so the
            # two cases are not symmetric: a non-zero value repeated is
            # real, while zero has to out-vote the possibility that it is
            # simply the absence of an answer. A register that genuinely
            # holds 0 returns nothing else, so it still resolves -- it
            # just needs more agreement to do it.
            nz = {k: c for k, c in seen.items() if k}
            if nz and max(nz.values()) >= need:
                return max(nz, key=nz.get)
            if not nz and seen.get(0, 0) >= need + 2:
                return 0
        raise IOError('register 0x%04X never settled: %s'
                      % (reg, {hex(k): n for k, n in seen.items()} or 'no answer'))

    def _ask(self, reg):
        """One paced ask, one collect, decoded with the link's CALIBRATED
        answer phase (see DiagLink, D74). Deciding the arrangement from the
        echo's position alone is what returned the previous request's value
        — 0, after a NOP — and called a running part a dead link."""
        if self.d.phase is None:
            self.d.calibrate()
        want0 = int.from_bytes(frame(reg, 0, read=True)[0:4], 'big')
        self.d._fetch(reg, next_read=True)
        time.sleep(SETTLE)
        w0, w1 = self.d._fetch()
        v = self.d._value(w0, w1, want0)
        if v is not None:
            return v
        time.sleep(SETTLE)
        return None

    def wr(self, reg, val, tries=8):
        """Write and confirm by reading back. Writes are dropped under
        audio load exactly as reads are, and an unverified arm produces a
        capture full of zeros that looks like a real null result."""
        val &= 0xFFFFFFFF
        for _ in range(tries):
            self.d.write(reg, val)
            time.sleep(SETTLE)
            try:
                if self.rd(reg) == val:
                    return
            except IOError:
                pass
        raise IOError('register 0x%04X would not take 0x%08X' % (reg, val))

    def arm(self, src, inj=0, amp=0, mode=1, tries=8):
        """Arm, and PROVE the arm landed by watching the run counter.

        The arm write is fire-and-forget like every write on this link.
        When it was dropped, wait() saw the previous run's finished state
        and fetch() handed back the previous run's buffer -- a stale
        capture that looks exactly like a fresh one. Chain-walking a
        signal path with stale captures reads as "the signal stops here",
        which is a wrong answer no amount of care downstream can catch.
        """
        self.d.write(SCOPE_ARM, 0)
        time.sleep(SETTLE)
        self.wr(SCOPE_SRC, src)
        self.wr(SCOPE_INJ, inj)
        self.wr(SCOPE_AMP, amp)
        self.wr(SCOPE_MODE, mode)
        for _ in range(tries):
            before = self.rd(SCOPE_RUNS)
            self.d.write(SCOPE_ARM, 1)
            time.sleep(SETTLE)
            if self.rd(SCOPE_RUNS) != before:
                return
        raise IOError('scope would not arm (run counter never advanced)')

    def wait(self, timeout=5.0):
        """Wait for the buffer to fill, polling the sample INDEX.

        Deliberately does NOT use the voting read: while a capture is in
        flight the index is a MOVING value and no two reads agree, so
        voting throws instead of waiting (bench 2026-08-23, chip 2 caught
        mid-fill: 0x3e, 0x5c, 0x74 ... all distinct). A single unvoted ask
        is right here because a dropped answer reads as 0, which is simply
        "not finished" and costs one more loop. The completed value is
        confirmed twice, since by then the index is static.

        ARM is not used: the buffer fills in ~21 ms, faster than a read,
        so ARM is almost always already back to 0 and says nothing.
        """
        end = time.time() + timeout
        n = 0
        while time.time() < end:
            v = self._ask(SCOPE_IDX)
            if v is not None and v >= SCOPE_MAX:
                if self._ask(SCOPE_IDX) == v:      # static now: confirm
                    return True
            n = v if v is not None else n
            time.sleep(0.02)
        raise IOError('capture stalled at %s of %d samples' % (n, SCOPE_MAX))

    def fetch(self, n):
        out = []
        for i in range(n):
            self.wr(SCOPE_RD, i)
            out.append(self.rd(SCOPE_DATA))
        return out


def q28(x):
    return int(round(x * (1 << 28))) & 0xFFFFFFFF


def s32(v):
    return v - (1 << 32) if v & 0x80000000 else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chip', type=int, default=1, choices=(1, 2))
    ap.add_argument('--src', required=True)
    ap.add_argument('--inj', default=None)
    ap.add_argument('--amp', default='1.0')
    ap.add_argument('--mode', default='impulse', choices=('impulse', 'step'))
    ap.add_argument('--n', type=int, default=32)
    ap.add_argument('--raw', action='store_true', help='print hex words')
    a = ap.parse_args()

    sc = Scope(a.chip)
    amp = int(a.amp, 16) if a.amp.startswith('0x') else q28(float(a.amp))
    inj = sc.addr(a.inj) if a.inj else 0
    sc.arm(sc.addr(a.src), inj, amp, 1 if a.mode == 'impulse' else 2)
    if not sc.wait():
        raise SystemExit('scope never disarmed — the sample loop is not turning')
    vals = sc.fetch(min(a.n, sc.rd(SCOPE_LEN) or SCOPE_MAX))
    if a.raw:
        for i in range(0, len(vals), 8):
            print('%4d: ' % i + ' '.join('%08x' % v for v in vals[i:i + 8]))
    else:
        for i, v in enumerate(vals):
            print('%4d  %11d  %+.9f' % (i, s32(v), s32(v) / (1 << 28)))


if __name__ == '__main__':
    main()
