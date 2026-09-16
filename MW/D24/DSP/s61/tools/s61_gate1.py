#!/usr/bin/env python3
"""s61_gate1.py [symdir] — where a capture readout's time goes (S61 gate 1). Read-only on the part:
the only writes are DIAG_PEEK_ADDR (a diag register) and NOPs.

  A  host: one SpiLink.xfer (RDY poll + gpiod CS low + spidev xfer2 8 bytes + CS high), split into parts
  B  DSP: after an ask, how many immediate collects until the echo appears (the poll latency, in transactions)
  C  one peek as dsp4_meascap does it (Scope.peek), per word, N words
  D  the same at SPI clocks 1 / 4 / 8 / 10 MHz (A and C only)
"""
import json, os, statistics as st, sys, time
_argv = list(sys.argv)
SYMDIR = _argv[1] if len(_argv) > 1 else '/home/app/s60'
sys.argv = ['s']
sys.path.insert(0, '/home/app/dspboot')
import dsp4_scope as S                                    # noqa: E402
from dsp4_diag import frame                                # noqa: E402

OUT = os.path.expanduser('~/s61/s61_gate1.jsonl')


def log(d):
    d['t'] = time.strftime('%H:%M:%S')
    print(json.dumps(d), flush=True)
    with open(OUT, 'a') as f:
        f.write(json.dumps(d) + '\n')


sc = S.Scope(1, symfile='%s/chip1.sym.json' % SYMDIR)
sc.check_chip()
L = sc.d.link
BUF = sc.sym['_meas_cap_buf_C1_TEST_MEAS']
if sc.peek(sc.sym['_rx_active_buf']) == 0:
    raise SystemExit('stale map')


def part_times(n=2000):
    nop = list(frame(0xE0FE, 0))
    tr = tc0 = tx = tc1 = 0.0
    for _ in range(n):
        a = time.perf_counter(); L.wait_ready()
        b = time.perf_counter(); L.line.set_value(0)
        c = time.perf_counter(); L.spi.xfer2(nop)
        d = time.perf_counter(); L.line.set_value(1)
        e = time.perf_counter()
        tr += b - a; tc0 += c - b; tx += d - c; tc1 += e - d
    return {k: round(v / n * 1e6, 1) for k, v in
            (('rdy_us', tr), ('cs_lo_us', tc0), ('xfer2_us', tx), ('cs_hi_us', tc1))}


def whole_xfer(n=2000):
    t0 = time.perf_counter()
    for _ in range(n):
        L.xfer(0xE0FE, 0)
    return round((time.perf_counter() - t0) / n * 1e6, 1)


def collects_to_answer(n=300):
    """ask MAGIC, then clock NOPs back to back and count until the echo shows."""
    want0 = int.from_bytes(frame(0xE000, 0, read=True)[0:4], 'big')
    counts, lost = [], 0
    for _ in range(n):
        sc.d._fetch()          # drain
        sc.d._fetch(0xE000, next_read=True)
        for k in range(1, 60):
            w0, w1 = sc.d._fetch()
            if want0 in (w0, w1):
                counts.append(k)
                break
        else:
            lost += 1
            sc.d.resync()
    return counts, lost


def peek_rate(n=1000):
    t0 = time.perf_counter()
    vals = [sc.peek(BUF + i) for i in range(n)]
    dt = time.perf_counter() - t0
    return round(n / dt, 1), round(dt / n * 1e6, 1), vals


log({'ev': 'start', 'symdir': SYMDIR, 'buf': BUF})
ref = None
for hz in (1_000_000, 4_000_000, 8_000_000, 10_000_000, 1_000_000):
    L.spi.max_speed_hz = hz
    sc.d.resync()
    rec = {'ev': 'clock', 'hz': hz, 'parts': part_times(), 'xfer_us': whole_xfer()}
    c, lost = collects_to_answer()
    rec['collects'] = {'median': st.median(c) if c else None, 'min': min(c) if c else None,
                       'max': max(c) if c else None, 'lost': lost,
                       'hist': {k: c.count(k) for k in sorted(set(c))}}
    try:
        r, us, vals = peek_rate(1000)
        ref = ref or vals
        rec.update({'peek_words_s': r, 'peek_us': us, 'peek_match_first': vals == ref})
    except IOError as e:
        rec['peek_err'] = str(e)
    log(rec)
