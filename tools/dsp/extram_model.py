#!/usr/bin/env python3
"""extram_model.py — host model of the delay pool's L2 and EXTRAM backends.

Why this exists
----------------
S75 adds an external-RAM (HyperRAM on xSPI0) backend for the firmware's
delay lines, alongside the L2-only backend that ships today. The part is
NOT on the board yet, so nothing about the new backend can be proved
against silicon. This module is the substitute: a host-side model of the
pool (both backends) plus a simulated HyperBus device that honours block
timing, not just storage, so the design's two claims —

  1. adding the EXTRAM backend does not perturb what the L2 backend already
     ships (the head-range read path is untouched code), and
  2. the tail range the EXTRAM backend newly serves is bit-exact against
     an infinite-precision reference, including across the history ring's
     wraparound, and fits its bus-bandwidth budget —

can be checked by something other than reading the diff. extram_bitexact.py
is the harness that does the checking; this file is only the model.

All sample values are int32 (the firmware is fixed-point Q4.28). Every
array in this module is dtype=np.int32 and no arithmetic is performed on
sample values anywhere here — they are moved, never computed on, which is
the only way a model can promise never to introduce a rounding difference
of its own.

Layout (matches the firmware's pool design, S75)
-------------------------------------------------
Each line keeps an L2 "head" ring of `head_len` samples (a multiple of
BLOCK) — this is the entire L2 backend, unchanged. The EXTRAM backend
additionally keeps, per line, a write-staging row (one of two, selected by
block parity) that mirrors the current block's samples in the layout the
external history store uses, and a read-staging row (also one of two)
that holds the 2*BLOCK words fetched two blocks ago for lines whose
requested delay reaches past the head.

The external history store is modelled as SLOTS rows of BLOCK samples per
line (SLOTS * BLOCK = 12000 samples = 250 ms @ 48 kHz = max_len), addressed
slot-major: address(slot, line) = slot*(n_lines*BLOCK) + line*BLOCK. That
layout is what makes the end-of-block flush a SINGLE HyperRAM write of
n_lines*BLOCK words (every line's block for one slot is contiguous) — the
write side of the design's bandwidth claim. The read side, a per-line
prefetch of two slots' worth of one line's history, is issued as two
separate BLOCK-word reads (the two slots are never adjacent addresses
under slot-major layout, whether or not the slot-ring wraps); the ring
wrap is handled entirely by the slot arithmetic being mod SLOTS, not by
any special-cased transfer shape. See extram_bitexact.py's report for
where this reading of "split transfer" is a judgment call rather than a
literal spec transcription.

Two-block arming transient
---------------------------
A prefetch issued while finishing block B is for consumption at block
B+2 (the read-staging half shares parity with B, and (B+2) has the same
parity as B, so the half that block B+2 reads is exactly the one block B
last wrote). That pipeline means a line's FIRST TWO blocks after its
offset changes to (or within) the tail range have no valid staged data
yet — the staged content on hand was fetched for whatever offset was
active two blocks ago. The model returns exactly zero for those samples,
by design, matching the firmware's own bounded, stated transient rather
than returning stale or undefined data that would make the harness's
comparisons ambiguous.
"""

import sys

import numpy as np

BLOCK = 16          # samples per audio block
SLOTS = 750         # history slots; SLOTS*BLOCK = 12000 samples = 250 ms @ 48 kHz

I32_MIN = -(1 << 31)
I32_MAX = (1 << 31) - 1


class HyperRamModel:
    """A HyperBus device that honours block timing, not just storage.

    word_addr is a plain word index (0..size_words-1). The class is
    "byte-addressed" only in the sense that a real HyperBus part is —
    nothing here ever transfers a partial word, so word addressing is
    the faithful and simpler choice for a model that only needs to prove
    data integrity and bus-clock accounting, not byte-level bus mechanics.
    """

    def __init__(self, size_words, clk_mhz=100.0, block=BLOCK):
        self.size_words = int(size_words)
        self.clk_mhz = float(clk_mhz)
        self.block = int(block)
        self.mem = np.zeros(self.size_words, dtype=np.int32)
        self.transfers = []       # list of (issue_block, n_words, direction)
        self._cur_block = 0

    def set_block(self, block_index):
        """Tell the model which audio block subsequent read()/write() calls
        are issued from, for the transfer log. The pool calls this once per
        process_block()."""
        self._cur_block = int(block_index)

    @staticmethod
    def clocks_for(n_words):
        """xSPI clocks for one transfer of n_words 32-bit words.

        overhead = 20 clocks (3 clocks of CA + up to 12 of initial latency
        + CS setup/hold); one 32-bit word is 4 bytes, and octal DDR moves
        8 bits x 2 edges per clock, i.e. 1 byte/clock, so a word costs 4
        clocks: total = 20 + n_words*4.
        """
        return 20 + int(n_words) * 4

    def read(self, word_addr, n):
        word_addr = int(word_addr)
        n = int(n)
        end = word_addr + n
        if word_addr < 0 or end > self.size_words:
            raise IndexError(
                f'HyperRAM read [{word_addr}:{end}) out of range '
                f'0..{self.size_words}')
        out = self.mem[word_addr:end].copy()
        self.transfers.append((self._cur_block, n, 'read'))
        return out

    def write(self, word_addr, data):
        word_addr = int(word_addr)
        data = np.asarray(data, dtype=np.int32)
        n = int(data.shape[0])
        end = word_addr + n
        if word_addr < 0 or end > self.size_words:
            raise IndexError(
                f'HyperRAM write [{word_addr}:{end}) out of range '
                f'0..{self.size_words}')
        self.mem[word_addr:end] = data
        self.transfers.append((self._cur_block, n, 'write'))

    def bus_clocks_in_block(self, block_index):
        return sum(self.clocks_for(n) for (b, n, _d) in self.transfers
                   if b == block_index)

    def clocks_available_per_block(self):
        return self.clk_mhz * 1e6 * self.block / 48000.0

    def busy_fraction(self, block_index):
        return (self.bus_clocks_in_block(block_index) /
                self.clocks_available_per_block())

    def assert_no_overrun(self):
        for b in sorted(set(b for (b, _n, _d) in self.transfers)):
            f = self.busy_fraction(b)
            if f > 1.0:
                raise RuntimeError(
                    f'HyperRAM overrun at block {b}: busy fraction '
                    f'{f:.3f} > 1.0')


class DelayPool:
    """N delay lines, backed by an L2 head ring plus (extram only) a
    simulated HyperRAM history store. See the module docstring for the
    layout and the two-block arming transient.
    """

    def __init__(self, n_lines, head_len, max_len, backend, ram=None,
                 block=BLOCK, slots=SLOTS):
        if backend not in ('l2', 'extram'):
            raise ValueError(f'unknown backend {backend!r}')
        if backend == 'extram' and ram is None:
            raise ValueError('extram backend requires ram=HyperRamModel(...)')
        self.n_lines = int(n_lines)
        self.head_len = int(head_len)
        self.max_len = int(max_len)
        self.backend = backend
        self.ram = ram
        self.block = int(block)
        self.slots = int(slots)

        self.head_ring = np.zeros((self.n_lines, self.head_len), dtype=np.int32)

        # Per-line bookkeeping for the arming transient: the block index at
        # which each line's CURRENT offset took effect, and what that
        # offset was (so a change can be detected on the next call).
        self._last_off = [None] * self.n_lines
        self._off_since = [0] * self.n_lines

        if backend == 'extram':
            self.wstage = np.zeros((2, self.n_lines * self.block), dtype=np.int32)
            self.rstage = np.zeros((2, self.n_lines, 2 * self.block), dtype=np.int32)
        else:
            self.wstage = None
            self.rstage = None

    def process_block(self, block_index, inputs, offsets):
        """Advance the pool by one block.

        inputs:  int32 array shaped (n_lines, BLOCK)
        offsets: length n_lines, per-line requested delay in samples
                 (block-constant, as in the firmware)
        returns: int32 array shaped (n_lines, BLOCK)

        Semantics (must match the firmware bit for bit):
          * sample k is written at head ring index (wptr+k) mod head_len,
            and (extram only) into wstage[block_index & 1].
          * output sample k, for off < head_len, comes from the head ring
            at (wptr - off + k) mod head_len -- both backends, identical
            code path, which is the head-range bit-exactness claim.
          * for off >= head_len: 'l2' clamps off to head_len-1 and uses
            the same head-ring formula (this is what ships today);
            'extram' serves it from the read-staging half fetched two
            blocks ago, UNLESS this line's offset changed fewer than two
            blocks ago, in which case the output is exactly zero (the
            arming transient -- see module docstring).
          * at the end of the block: the write-staging row is flushed to
            the RAM at hist[slot], slot = block_index % SLOTS; then, for
            every line whose off >= head_len, two slots' worth of that
            line's history are prefetched into the OTHER read-staging
            half, to be consumed at block_index+2.
        """
        inputs = np.asarray(inputs, dtype=np.int32)
        offsets = [int(o) for o in offsets]
        if inputs.shape != (self.n_lines, self.block):
            raise ValueError(f'inputs shape {inputs.shape} != '
                              f'{(self.n_lines, self.block)}')
        if len(offsets) != self.n_lines:
            raise ValueError('offsets length must equal n_lines')

        wptr = (block_index * self.block) % self.head_len
        half = block_index & 1
        out = np.zeros((self.n_lines, self.block), dtype=np.int32)

        for i in range(self.n_lines):
            off = offsets[i]
            if off != self._last_off[i]:
                self._off_since[i] = block_index
                self._last_off[i] = off

            # --- write path: L2 head ring (both backends) ---
            for k in range(self.block):
                self.head_ring[i, (wptr + k) % self.head_len] = inputs[i, k]

            if self.backend == 'extram':
                self.wstage[half, i * self.block:(i + 1) * self.block] = inputs[i, :]

            # --- read path ---
            if off < self.head_len:
                for k in range(self.block):
                    out[i, k] = self.head_ring[i, (wptr - off + k) % self.head_len]
            elif self.backend == 'l2':
                eff = self.head_len - 1
                for k in range(self.block):
                    out[i, k] = self.head_ring[i, (wptr - eff + k) % self.head_len]
            else:  # extram, tail range
                if block_index - self._off_since[i] < 2:
                    out[i, :] = 0          # arming transient: not valid yet
                else:
                    ph = (self.block - (off % self.block)) % self.block
                    out[i, :] = self.rstage[half, i, ph:ph + self.block]

        if self.backend == 'extram':
            slot = block_index % self.slots
            row_stride = self.n_lines * self.block
            self.ram.set_block(block_index)

            # Single burst: every line's block for this slot is contiguous.
            self.ram.write(slot * row_stride, self.wstage[half])

            # Per-line prefetch for lines in the tail range, to be
            # consumed at block_index + 2.
            target_slot = (slot + 2) % self.slots
            for i in range(self.n_lines):
                off = offsets[i]
                if off >= self.head_len:
                    q, ph = divmod(off, self.block)
                    start = (target_slot - q - (1 if ph else 0)) % self.slots
                    s0 = start
                    s1 = (start + 1) % self.slots
                    d0 = self.ram.read(s0 * row_stride + i * self.block, self.block)
                    d1 = self.ram.read(s1 * row_stride + i * self.block, self.block)
                    self.rstage[half, i, 0:self.block] = d0
                    self.rstage[half, i, self.block:2 * self.block] = d1

        return out


def reference_delay(inputs_stream, off, max_len):
    """The ideal delayed stream for ONE line, from an infinite-precision
    ring (no slot quantisation, no arming transient, no bus): the
    third-party check that DelayPool's tail range is measured against.

    output[t] = inputs_stream[t - off] for t >= off, else 0.

    max_len is accepted for symmetry with DelayPool and is asserted
    against (a delay this model can't itself serve past isn't a delay
    the pool is claiming to serve either) but otherwise unused — the
    reference ring is exact and unbounded, which is the point of it.
    """
    off = int(off)
    if off < 0:
        raise ValueError('off must be >= 0')
    if off >= max_len:
        raise ValueError(f'off {off} >= max_len {max_len}')
    x = np.asarray(inputs_stream, dtype=np.int32)
    out = np.zeros_like(x)
    if off == 0:
        out[:] = x
    elif off < len(x):
        out[off:] = x[:len(x) - off]
    return out


if __name__ == '__main__':
    print(__doc__)
    sys.exit(0)
