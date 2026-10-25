#!/usr/bin/env python3
"""check_pins.py -- every CPLD pin location against the board netlist (S173).

For each set_location_assignment in a qsf, the port's EXPECTED net (rule
table below, one place) must be the net on that U3 pin in the board's
netlist table, and that net must be on no other U3 pin. A port whose
expected net is missing from the board, or a location on the wrong net, is
a mismatch. Exit 1 on any mismatch.

    python3 check_pins.py                       # both revisions
    python3 check_pins.py quartus/dsp4_logic_revd.qsf boards/u3-pins-revD.csv
    python3 check_pins.py reports/s173/revD.dsp4_logic_revd.pin boards/u3-pins-revD.csv

A .pin file (the fitter's pin-out report) is checked the same way, so the
FITTED placement is verified and not only the request.
"""
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

PAIRS = [
    ("quartus/dsp4_logic.qsf", "boards/u3-pins-revC.csv"),
    ("quartus/dsp4_logic_revd.qsf", "boards/u3-pins-revD.csv"),
]

FIXED = {
    "sysclk": "SYSCLK", "dsp_clk": "DSP_CLK",
    "conv_bck": "C1", "conv_fs": "L0",
    "m_mcu_s4": "M_MCU_S4", "mhrx": "M_MCU_P17",
    "cdc_o": "PLL8_0", "cdc_i": "PLL8_1",
    "mems_bck": "PLL7_0", "mems_fs": "PLL7_1", "mems_i2s": "PLL7_2",
    "pcm_clk": "PI_PCM_CLK", "pcm_fs": "PI_PCM_FS",
    "pcm_din": "PI_PCM_DIN", "pcm_dout": "PI_PCM_DOUT",
    "blink_led": "BLINK_LED",
    # rev D only: the strap is tied straight to the ground net
    "board_rev0": "GND",
}
INDEXED = {
    "bcki": "BCKI{n}", "fsi": "FSI{n}", "i_dspa": "I{n}", "o_dspb": "O{n}",
    "ad": "AD{n}", "da": "DA{n}", "ni": "NI{n}", "no": "NO{n}",
    "test": "TEST{m}",          # test[0] = TEST1 ... test[3] = TEST4
}


def norm(net):
    """Rev C (mx26 aliases) and rev D (KiCad) spell the same nets differently."""
    n = net.replace("/LOGIC/", "").replace(" ", "_").upper()
    if n.startswith("LOGIC_"):
        n = n[len("LOGIC_"):]
    return n


def expected(port):
    if port in FIXED:
        return FIXED[port]
    m = re.fullmatch(r"(\w+)\[(\d+)\]", port)
    if m and m.group(1) in INDEXED:
        n = int(m.group(2))
        return INDEXED[m.group(1)].format(n=n, m=n + 1)
    return None


def check(qsf, table):
    pins = {}
    for r in csv.reader(l for l in open(table) if not l.startswith("#")):
        if r[0] != "pin":
            pins[int(r[0])] = norm(r[1])
    where = {}
    for p, n in pins.items():
        where.setdefault(n, []).append(p)

    bad = 0
    rows = 0
    for line in open(qsf):
        if qsf.endswith(".pin"):
            # the FITTED result: "port : pin : dir : standard : ..." rows
            m = re.match(r"\s*([a-z_][\w\[\]]*)\s*:\s*(\d+)\s*:\s*(input|output|bidir)", line)
            if not m:
                continue
            port, pin = m.group(1), int(m.group(2))
        else:
            m = re.match(r"\s*set_location_assignment\s+PIN_(\d+)\s+-to\s+(\S+)", line)
            if not m:
                continue
            pin, port = int(m.group(1)), m.group(2)
        rows += 1
        want = expected(port)
        got = pins.get(pin)
        if want is None:
            print(f"  {port:12s} PIN_{pin:<3d} no rule for this port")
            bad += 1
        elif got != want:
            print(f"  {port:12s} PIN_{pin:<3d} net {got}, expected {want}"
                  f" (board has {want} on {where.get(want, 'no pin')})")
            bad += 1
        elif want != "GND" and len(where[want]) != 1:
            print(f"  {port:12s} PIN_{pin:<3d} net {want} is on pins {where[want]}")
            bad += 1
    print(f"{os.path.relpath(qsf, HERE)} vs {os.path.relpath(table, HERE)}: "
          f"{rows} locations, {bad} mismatch(es)")
    return bad


def main():
    args = sys.argv[1:]
    pairs = [tuple(args)] if args else [(os.path.join(HERE, q), os.path.join(HERE, t))
                                        for q, t in PAIRS]
    sys.exit(1 if sum(check(q, t) for q, t in pairs) else 0)


if __name__ == "__main__":
    main()
