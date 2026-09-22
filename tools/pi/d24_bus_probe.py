#!/usr/bin/env python3
"""d24_bus_probe.py -- the two matrix-bus reads section 1 needs and no existing tool does.

Runs ON the unit's CM4 (it wants /dev/serial0) and prints JSON on stdout. The
transport is `codec4619.py`'s, imported rather than copied: raw termios on
/dev/serial0, newline-terminated tokens, address nibbles 'h'..'w', and
`parse_reply`'s bounded match rather than `startswith` (MH1's idle '.'/':'
heartbeat is not newline-aligned with cell traffic, so a real reply arrives as
`.:imjn40` far more often than as a clean line of its own).

    --mode stest     S_RUN then S_TEST; return the raw bytes and the identity
                     line each MCU answered with. This is what enumerates the
                     bus: H1S1, H1S3 and H1S4 each hold their own
                     `testMessage[]` and `TestMessage()` transmits it on '&'.
    --mode cell      N round trips on ONE H1S1-local cell, with the response
                     time of each. The request is CodecPoll()'s 0xFB sentinel
                     -- "hand back the guard byte" -- which sets TXD/TXF on
                     Sys001Test001 and ISSUES NO SPI. That matters twice: the
                     codec is not touched, and the reply lands on the ADDRESS
                     cell, never on the DATA cell whose RXF is the trigger.
                     Answering on the trigger cell is what made the first S81
                     firmware free-run a burst of unasked SPI across the copper
                     the CM4 boots the SHARCs over.

`matrix-app` owns /dev/serial0. Stop it before running this, and put it back.

    python3 d24_bus_probe.py --mode stest
    python3 d24_bus_probe.py --mode cell --reps 3
"""
import argparse
import json
import re
import sys
import time

sys.path.insert(0, '/home/app/dspboot')
import codec4619 as C

GUARD_FETCH = 0xFB              # CodecPoll() sentinel: hand back codecReadGuard
# The identity strings the three MCUs answer S_TEST with. H1S1's lives at
# ~/build-h1s1/Core/Inc/matrix.cs:46 (`char testMessage[100] = "// H1S1 DSP\n"`);
# the panels' are the same mechanism in their own firmware. MH1 is the
# dispatcher and is matched separately because it also emits the idle
# heartbeat, so its absence from a burst is not evidence it is dead.
MCU_PAT = re.compile(r'//\s*(H1S1|H1S3|H1S4|MH1)\b[^\r\n]*')


def stest(port):
    b = C.Bus(port)
    try:
        run_raw = b.run()
        time.sleep(0.2)
        t0 = time.time()
        raw = b.test()
        ms = (time.time() - t0) * 1000.0
    finally:
        b.close()
    text = (run_raw + raw).decode('ascii', 'replace')
    seen = {}
    for m in MCU_PAT.finditer(text):
        seen.setdefault(m.group(1), m.group(0).strip())
    return {'mode': 'stest', 'window_ms': round(ms, 1),
            'mcus': seen, 'raw': text}


def cell(port, addr, reps):
    """`reps` guard fetches on one cell. Each is a full host -> MH1 -> H1S1 ->
    MH1 -> host round trip; `_request` waits for the ADDRESS cell to answer
    rather than reading a fixed window, because H1S1 transmits only when MH1
    raises S3 and a fixed window aliases one request's reply into the next."""
    b = C.Bus(port)
    out = []
    try:
        for _ in range(reps):
            t0 = time.time()
            v = b._request(GUARD_FETCH, 0x00, 0.25)
            out.append({'value': v, 'ms': round((time.time() - t0) * 1000.0, 1),
                        'raw': b.last_raw.decode('ascii', 'replace')})
            time.sleep(0.1)
    finally:
        b.close()
    vals = [r['value'] for r in out]
    return {'mode': 'cell', 'cell': addr, 'reps': reps, 'reads': out,
            'answered': sum(1 for v in vals if v is not None),
            'identical': len(set(vals)) == 1 and vals[0] is not None}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--mode', choices=('stest', 'cell'), required=True)
    ap.add_argument('--reps', type=int, default=3)
    ap.add_argument('--cell', default='0x1526',
                    help='cell address for --mode cell (default Sys001Test001 = 5414)')
    ap.add_argument('--port', default=C.PORT)
    a = ap.parse_args()
    if a.mode == 'stest':
        r = stest(a.port)
    else:
        r = cell(a.port, int(a.cell, 0), a.reps)
    print(json.dumps(r))


if __name__ == '__main__':
    main()
