#!/usr/bin/env python3
"""find_cell_events_check.py -- S138: proves codec4619.find_cell_events() and
d24_bus_probe.listen()'s parsing against SYNTHETIC bus bytes. No serial port,
no unit, no bus -- the S137 pattern (panel_glass_buttons_check.py) applied to
the new passive-listen primitive instead of the panel loop.

Constructs realistic replies with codec4619.cell_prefix()/DX (the same
alphabet H1S1's Poll() answers with) and MH1's idle '.'/'':'' heartbeat
interleaved, then checks find_cell_events() recovers exactly the edges that
were "sent" -- in order, none dropped, none invented -- and that a cell with
NO traffic in the window answers with zero events rather than a guessed
value (the honesty bar `d24_bus_probe.py --mode listen`'s docstring states).
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', '..', '..', '..', 'tools', 'pi'))
# codec4619.py resolves Sys001Test001/Sys001Test002 BY NAME at import time
# (S136) -- off a deployed unit's pack it would find at ~/config/_matrix.csv.
# There is no unit here, so MATRIX_ADDR_HOME points matrix_addr.py at this
# session's own fixture pack instead (fixtures/config/_matrix.csv) -- the
# same override mechanism `matrix_addr.py --path` documents, applied through
# the env var so codec4619's own module-level resolution picks it up too.
os.environ.setdefault('MATRIX_ADDR_HOME', os.path.join(HERE, 'fixtures'))
import codec4619 as C   # noqa: E402

FAILS = []


def check(name, cond, detail=''):
    tag = 'ok' if cond else 'FAIL'
    print('%-4s %s%s' % (tag, name, (': ' + detail) if detail and not cond else ''))
    if not cond:
        FAILS.append(name)


def reply_bytes(addr, value):
    """One firmware-shaped reply for `addr` = `value`, in the same
    conditional-nibble shape Poll() emits (codec4619.parse_reply's docstring)."""
    pre = C.cell_prefix(addr)
    if value == 0:
        return pre
    if value <= 0xF:
        return pre + C.DX[value]
    return pre + C.DX[(value >> 4) & 0xF] + C.DX[value & 0xF]


HEARTBEAT = '.' * 3 + ':' * 2   # MH1's idle heartbeat, not newline-aligned


def test_single_edge():
    addr = 4361   # a real S136-style resolved address, arbitrary for this test
    raw = (HEARTBEAT + reply_bytes(addr, 1) + HEARTBEAT).encode('ascii')
    ev = C.find_cell_events(raw, addr)
    check('single edge, value 1', ev == [(1, ev[0][1])] if ev else False,
          repr(ev))


def test_zero_is_a_real_answer():
    # A reply of 0x00 is the bare address prefix -- codec4619.parse_reply's
    # own docstring warns this must not be mistaken for "still arriving".
    addr = 4362
    raw = (HEARTBEAT + reply_bytes(addr, 0) + HEARTBEAT).encode('ascii')
    ev = C.find_cell_events(raw, addr)
    check('a genuine zero is not silence', ev == [(0, ev[0][1])] if ev else False,
          repr(ev))


def test_two_edges_in_order():
    # "Both edges are reported" (mx_master.csv, Sys001SwMiniJack001): a plug
    # removed then refitted inside one drain must come back INSERTED then
    # NOT-INSERTED, in that order, not just the last one. A reply needs a
    # character after it that is not a data nibble to be recognised as
    # COMPLETE (codec4619.parse_reply's own docstring) -- true on a real bus,
    # which never truly ends, so every reply here is followed by heartbeat.
    addr = 4361
    raw = (reply_bytes(addr, 1) + HEARTBEAT + reply_bytes(addr, 0)
           + HEARTBEAT).encode('ascii')
    ev = C.find_cell_events(raw, addr)
    vals = [v for v, _ in ev]
    check('two edges, both kept in order', vals == [1, 0], repr(vals))


def test_no_traffic_is_zero_events_not_a_guess():
    # The cell this test asks about never appears in the window: the honesty
    # bar `d24_bus_probe.py --mode listen`'s docstring states -- zero events,
    # not a fabricated "reads 0".
    addr = 9999
    other_addr = 4361
    raw = (HEARTBEAT + reply_bytes(other_addr, 1) + HEARTBEAT).encode('ascii')
    ev = C.find_cell_events(raw, addr)
    check('an absent cell answers with zero events, not a value', ev == [], repr(ev))


def test_does_not_alias_into_the_wrong_cell():
    # Two different cells' replies in the same drain must not be confused --
    # the bounded match is what `codec4619.parse_reply`'s docstring says the
    # unbounded version got wrong on the part (S81). A HEARTBEAT gap between
    # them is realistic (MH1's idle traffic is what actually separates two
    # different cells' replies on the wire); back-to-back-with-NO-separator
    # is a genuine, pre-existing ambiguity of this bounded-match shape
    # (a trailing data nibble reads as a same-alphabet lookbehind veto for
    # whatever starts immediately after it) shared by `d24_panel.py`'s own
    # `_all_replies` and `codec4619.parse_reply` -- not something this test
    # asserts away.
    addr_a, addr_b = 4361, 4362
    raw = (reply_bytes(addr_a, 1) + HEARTBEAT + reply_bytes(addr_b, 7)
           + HEARTBEAT).encode('ascii')
    ev_a = C.find_cell_events(raw, addr_a)
    ev_b = C.find_cell_events(raw, addr_b)
    check('cell A sees only its own edge', [v for v, _ in ev_a] == [1], repr(ev_a))
    check('cell B sees only its own edge', [v for v, _ in ev_b] == [7], repr(ev_b))


def test_two_digit_value():
    addr = 4361
    raw = (reply_bytes(addr, 0x2A) + HEARTBEAT).encode('ascii')
    ev = C.find_cell_events(raw, addr)
    check('a two-nibble value round-trips', ev == [(0x2A, ev[0][1])] if ev else False,
          repr(ev))


def test_bus_probe_listen_end_to_end():
    """d24_bus_probe.listen() end to end, with codec4619.Bus's serial port
    replaced by an in-memory fake: resolve-by-name, open, read the window,
    find_cell_events, shape the dict -- the whole path `--mode listen` runs,
    minus the one thing that needs a real unit (the fd itself)."""
    sys.path.insert(0, os.path.join(HERE, '..', '..', '..', '..', 'tools', 'pi'))
    import d24_bus_probe as P   # noqa: E402  (imports codec4619, already patched)

    class FakeBus:
        def __init__(self, port=None):
            pass

        def read(self, secs):
            return (HEARTBEAT + reply_bytes(4361, 1) + HEARTBEAT).encode('ascii')

        def close(self):
            pass

    real_bus = C.Bus
    C.Bus = FakeBus
    try:
        r = P.listen('/dev/null', 'Sys001SwMiniJack001', 2.0)
    finally:
        C.Bus = real_bus
    check('listen() resolves the name off the fixture pack', r['cell'] == 4361, repr(r))
    check('listen() reports the one edge it saw', r['values'] == [1], repr(r))
    check('listen() last value', r['last'] == 1, repr(r))

    r2 = P.listen('/dev/null', 'Sys001NameNotInAnyPack999', 2.0)
    check('listen() on an unresolvable name: no crash, no guess',
          r2['cell'] is None and r2['values'] == [] and r2['error'], repr(r2))


def main():
    test_single_edge()
    test_zero_is_a_real_answer()
    test_two_edges_in_order()
    test_no_traffic_is_zero_events_not_a_guess()
    test_does_not_alias_into_the_wrong_cell()
    test_two_digit_value()
    test_bus_probe_listen_end_to_end()
    print()
    if FAILS:
        print('%d check(s) FAILED: %s' % (len(FAILS), ', '.join(FAILS)))
        return 1
    print('all checks passed -- no serial port, no unit, no bus')
    return 0


if __name__ == '__main__':
    sys.exit(main())
