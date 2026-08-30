#!/usr/bin/env python3
"""dsp4_cfgstress.py — amplify the CONFIG_COMMIT wedge and name its exchange.

dsp4_bootchar.py measures the honest per-boot rate, and at a few percent that
is far too slow to bisect: a 32-cycle arm costs 13 minutes and cannot tell 1/32
from 0/32. This tool trades honesty for rate. It boots ONCE, writes the config
data registers ONCE, and then writes CONFIG_COMMIT over and over, checking the
part between each one — so every trial is a fresh execution of the commit path
(_rx_patch_apply, _cgu_raise_cclk, _scope_gates_apply) at a couple of seconds
instead of half a minute, and the SAME already-good patch registers are used
every time.

That last property is the discriminator this session needs:

  * if repeating the commit alone wedges the part, the mechanism is INSIDE
    the commit path — and the only thing in there that can stop the core
    dead is _cgu_raise_cclk's four unbounded spin-waits on CGU0_STAT;
  * if it never wedges however long it runs, the wedge needs the fresh
    WRITE SEQUENCE that precedes it, i.e. a parameter-link framing slip
    that lands a value somewhere it should not (the 2026-08-28 finding
    where CFG_COMMIT's own header word 0xF0040000 turned up in
    _gain_coeff_C1_GAIN_01 is the same family).

--raw dumps the literal MISO bytes of known-distinct transactions once the
part is wedged. That is what identifies the failing exchange rather than the
symptom: a starved slave whose core has stopped shifts its RX shift register
back out, so MISO carries the host's PREVIOUS transaction verbatim — and the
diag read protocol's echo check accepts exactly that, returning (echo, 0) for
every register. "BOOT_STAGE reads 0" has been recorded as a link intermittent
since session 5; if this dump shows the lag, that 0 was never a register value.
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dsp4_boot import CS_GPIO

CFG_COMMIT = 0xF004
DIAG_MAGIC = 0xE000
DIAG_STAGE = 0xE002
MAGIC_VALUE = 0xD5B40001


def _open(chip, speed=1_000_000, dev='0.0'):
    from dsp4_config import SpiLink
    return SpiLink(dev, speed, CS_GPIO[chip])


def _close(link):
    try:
        link.spi.close()
    except Exception:                              # noqa: BLE001
        pass
    req = getattr(link, '_req_cs', None)
    if req is not None:
        try:
            req.release()
        except Exception:                          # noqa: BLE001
            pass


def probe_stage(chip):
    """(magic, stage) or (None, None) if the link would not answer."""
    from dsp4_diag import DiagLink
    link = _open(chip)
    try:
        d = DiagLink(link)
        d.resync()
        return d.read(DIAG_MAGIC), d.read(DIAG_STAGE)
    except (IOError, OSError):
        return None, None
    finally:
        _close(link)


def raw_dump(chip, n=4):
    """Clock n transactions with DISTINCT MOSI words and return what came
    back, so the relationship between MISO and MOSI can be read off directly
    instead of inferred through the echo check."""
    link = _open(chip)
    out = []
    try:
        for i in range(n):
            mosi = bytes([0xA0 + i, 0x11, 0x22, 0x33, 0xB0 + i, 0x44, 0x55, 0x66])
            if link.line:
                link.line.set_value(0)
            try:
                rx = bytes(link.spi.xfer2(list(mosi)))
            finally:
                if link.line:
                    link.line.set_value(1)
            out.append((mosi.hex(), rx.hex()))
            time.sleep(0.002)
    finally:
        _close(link)
    return out


def write_regs(chip, product, include_commit):
    from dsp4_config import transactions
    link = _open(chip)
    try:
        n = 0
        for addr, value in transactions(product, chip):
            if addr == CFG_COMMIT and not include_commit:
                continue
            link.write(addr, value)
            n += 1
        return n
    finally:
        _close(link)


def commit_once(chip):
    link = _open(chip)
    try:
        link.write(CFG_COMMIT, 1)
    finally:
        _close(link)


def boot(directory, settle):
    import subprocess
    subprocess.run(['pinctrl', 'set', '9,10,11', 'a0'],
                   check=False, capture_output=True)
    r = subprocess.run([sys.executable, 'dsp4_boot.py', '--dir', directory],
                       capture_output=True, text=True)
    time.sleep(settle)
    return r.returncode == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--boots', type=int, default=6)
    ap.add_argument('--commits', type=int, default=40,
                    help='CONFIG_COMMIT writes attempted per boot')
    ap.add_argument('--chip', type=int, default=1, choices=(1, 2))
    ap.add_argument('--product', default='d24')
    ap.add_argument('--dir', default='.')
    ap.add_argument('--settle', type=float, default=5.0)
    ap.add_argument('--gap', type=float, default=0.4,
                    help='seconds between a commit and the check after it')
    ap.add_argument('--tag', default='stress')
    ap.add_argument('--raw', action='store_true',
                    help='dump raw MISO from a wedged part')
    ap.add_argument('--mode', choices=('commit', 'full'), default='commit',
                    help="'commit' repeats CONFIG_COMMIT alone against "
                         'already-good patch registers, which isolates the '
                         "commit path; 'full' repeats the WHOLE 51-write "
                         'sequence, which additionally exercises the '
                         'parameter-link framing that produced the '
                         '2026-08-28 stray-write finding')
    args = ap.parse_args()

    total_commits = 0
    wedges = 0
    survived = []
    for b in range(1, args.boots + 1):
        if not boot(args.dir, args.settle):
            print(f'[{args.tag}] boot {b}: dsp4_boot.py failed', flush=True)
            continue
        magic, stage = probe_stage(args.chip)
        if magic != MAGIC_VALUE:
            print(f'[{args.tag}] boot {b}: chip {args.chip} did not come up '
                  f'(magic={magic}, stage={stage}) — skipping', flush=True)
            continue
        if args.mode == 'commit':
            n = write_regs(args.chip, args.product, include_commit=False)
            print(f'[{args.tag}] boot {b}: up at stage {stage}, {n} data regs '
                  f'written; committing up to {args.commits} times', flush=True)
        else:
            print(f'[{args.tag}] boot {b}: up at stage {stage}; repeating the '
                  f'FULL write sequence up to {args.commits} times', flush=True)
        this = 0
        for c in range(1, args.commits + 1):
            if args.mode == 'commit':
                commit_once(args.chip)
            else:
                write_regs(args.chip, args.product, include_commit=True)
            total_commits += 1
            this += 1
            time.sleep(args.gap)
            magic, stage = probe_stage(args.chip)
            if magic != MAGIC_VALUE or stage in (None, 0):
                wedges += 1
                survived.append(this)
                print(f'[{args.tag}] boot {b}: WEDGED on commit {c} '
                      f'(magic={magic}, stage={stage})', flush=True)
                if args.raw:
                    print(f'[{args.tag}] raw MISO from the wedged part '
                          f'(MOSI -> MISO, 4 distinct transactions):',
                          flush=True)
                    for mosi, miso in raw_dump(args.chip):
                        print(f'    {mosi}  ->  {miso}', flush=True)
                break
        else:
            survived.append(this)
            print(f'[{args.tag}] boot {b}: survived all {this} commits '
                  f'(stage {stage})', flush=True)

    unit = 'commits' if args.mode == 'commit' else 'full sequences'
    print(f'\n[{args.tag}] {wedges} wedge(s) in {total_commits} {unit}')
    if total_commits:
        print(f'[{args.tag}] per-trial wedge rate '
              f'{100.0 * wedges / total_commits:.2f}%')
    print(f'[{args.tag}] commits survived per boot: {survived}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
