#!/usr/bin/env python3
"""dsp4_bootchar.py — per-cycle characterisation of the boot+config handshake.

Every bench script in this tree wraps the boot in a retry ladder and reports
only the last attempt, so the standing intermittent recorded since session 5
("~2 boots in 8 wedge at BOOT_STAGE 0 or 5") has never been a measured number
— it has only ever been an anecdote taken off a retrying instrument. Four
sessions of debugging were misattributed to it.

This tool is the opposite of a retry ladder: ONE attempt per cycle, N cycles,
every cycle recorded whether it passed or failed. It drives dsp4_boot.py's
own functions (imported, not shelled out) so the reset pulse, the settle, the
stream and the per-chip elapsed time are all under its control and all land in
the CSV.

Per cycle it records:
  * !RST_D pulse, the post-reset settle actually used, and per-chip boot
    elapsed ms + whether the single attempt raised
  * SPI_RDY levels for both chips, before and after the stream
  * a PRE-CONFIG diag probe of BOTH chips: MAGIC, CHIP_ID, BOOT_STAGE,
    TICKS, SPI_RX_COUNT, SPI_ERR_COUNT, RESP_DROP, BUILD_ID
  * ONE config pass (no retry), then a POST-CONFIG probe of the same
  * for any cycle that did not reach stage >= 6: a RECHECK probe some seconds
    later, which is what answers "does a wedged cycle ever recover unaided?"

Usage (on the Pi, from /home/app/dspboot):
  python3 dsp4_bootchar.py --cycles 30 --csv bootchar.csv
  python3 dsp4_bootchar.py --cycles 16 --post-reset-delay 0.9 --tag pr900
  python3 dsp4_bootchar.py --cycles 16 --speed 5000000 --tag spi5m
  python3 dsp4_bootchar.py --cycles 16 --order 2,1 --tag order21
  python3 dsp4_bootchar.py --cycles 16 --no-reset --tag warm

The CSV is APPENDED to, with the header written once, so arms of a bisect
accumulate in one file and are told apart by --tag.
"""

import argparse
import csv
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import dsp4_boot
from dsp4_boot import CS_GPIO, RDY_GPIO, RST_GPIO, RESET_LOW_S, pad

DIAG_REGS = [
    ('magic', 0xE000), ('id', 0xE001), ('stage', 0xE002), ('cfg', 0xE003),
    ('frames', 0xE004), ('ticks', 0xE005), ('rx', 0xE00B), ('err', 0xE00C),
    ('drop', 0xE00F), ('pid', 0xE010), ('build', 0xE017),
    # DSP4_CFG_WATCH block (diag.h). Reads 0 on an image built without it,
    # which is harmless — _diag_read bounds-checks the table and a
    # register past its end reads back as 0.
    ('phase', 0xE019), ('cgufail', 0xE01A),
    ('it1', 0xE01B), ('it2', 0xE01C), ('it3', 0xE01D), ('it4', 0xE01E),
    ('pfix', 0xE01F), ('pticks', 0xE020),
]
PROBE_KEYS = [k for k, _ in DIAG_REGS]


def pinctrl_restore():
    """spidev's pinmux is applied at probe time, not per open: anything that
    claims 9/10/11 as gpiod lines leaves them plain inputs and every later
    boot fails 100% of the time looking exactly like a dead part."""
    subprocess.run(['pinctrl', 'set', '9,10,11', 'a0'],
                   check=False, capture_output=True)


def probe(chip, speed=1_000_000, dev='0.0'):
    """One diag sweep of one chip. Returns a dict; values are None where the
    link would not answer, which is itself the measurement."""
    from dsp4_config import SpiLink
    from dsp4_diag import DiagLink
    out = {k: None for k in PROBE_KEYS}
    link = None
    try:
        link = SpiLink(dev, speed, CS_GPIO[chip])
        d = DiagLink(link)
        d.resync()
        for name, addr in DIAG_REGS:
            try:
                out[name] = d.read(addr)
            except (IOError, OSError):
                break          # link is out of step; the rest would lie too
    except Exception as exc:                       # noqa: BLE001
        out['error'] = str(exc)[:80]
    finally:
        if link is not None:
            try:
                link.spi.close()
            except Exception:                      # noqa: BLE001
                pass
            req = getattr(link, '_req_cs', None)
            if req is not None:
                try:
                    req.release()
                except Exception:                  # noqa: BLE001
                    pass
    return out


def config_once(chip, product, speed=1_000_000, dev='0.0'):
    """One config pass, no retry ladder. Returns (ok, detail)."""
    from dsp4_config import SpiLink, transactions
    link = None
    try:
        link = SpiLink(dev, speed, CS_GPIO[chip])
        n = 0
        for addr, value in transactions(product, chip):
            link.write(addr, value)
            n += 1
        return True, f'{n} writes'
    except Exception as exc:                       # noqa: BLE001
        return False, str(exc)[:80]
    finally:
        if link is not None:
            try:
                link.spi.close()
            except Exception:                      # noqa: BLE001
                pass
            req = getattr(link, '_req_cs', None)
            if req is not None:
                try:
                    req.release()
                except Exception:                  # noqa: BLE001
                    pass


def release_all(gpio):
    for num in list(gpio.lines):
        try:
            gpio.lines.pop(num).release()
        except Exception:                          # noqa: BLE001
            pass


def one_cycle(args, streams, row):
    """Reset (unless --no-reset), stream each chip once, record everything."""
    import spidev
    pinctrl_restore()
    bus, dev = (int(x) for x in args.dev.split('.'))
    spi = spidev.SpiDev()
    spi.open(bus, dev)
    spi.max_speed_hz = args.speed
    spi.mode = args.spi_mode
    spi.no_cs = True
    gpio = dsp4_boot.Gpio()
    try:
        if not args.no_reset:
            rst = gpio.out(RST_GPIO, initial=1)
            rst.set_value(0)
            time.sleep(RESET_LOW_S)
            rst.set_value(1)
            time.sleep(args.post_reset_delay)
        # RDY levels BEFORE the stream. With the 10K pull-DOWNS fitted the
        # line rests asserted (0), so a 1 here means something is holding
        # the host off — that is the only thing this read can prove.
        for chip in (1, 2):
            row[f'rdy{chip}_pre'] = gpio.inp(RDY_GPIO[chip]).get_value()
        for chip in args.order:
            stream = streams[chip]
            t0 = time.monotonic()
            try:
                dsp4_boot.boot_chip(spi, gpio, chip, stream, verbose=False,
                                    attempt=1, attempts=1,
                                    spicmd=args.spi_cmd_val,
                                    chunk=args.chunk,
                                    sync=args.sync_poll)
                row[f'boot{chip}_ok'] = 1
            except TimeoutError as exc:
                row[f'boot{chip}_ok'] = 0
                row[f'boot{chip}_err'] = str(exc)[:60]
            row[f'boot{chip}_ms'] = round((time.monotonic() - t0) * 1e3, 1)
        for chip in (1, 2):
            row[f'rdy{chip}_post'] = gpio.inp(RDY_GPIO[chip]).get_value()
    finally:
        release_all(gpio)
        try:
            spi.close()
        except Exception:                          # noqa: BLE001
            pass
        pinctrl_restore()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--cycles', type=int, default=30)
    ap.add_argument('--dir', default='.', help='dir holding chip1/2.ldr')
    # DEFAULTS TO bootchar_<tag>.csv, NOT A SINGLE SHARED FILE. Every arm
    # used to land in one bootchar.csv, so the moment the probe's register
    # list changed the run aborted on the header guard below — which is the
    # guard doing its job, but it cost a full bench slot on 2026-08-31
    # before a cycle had run. One file per arm cannot collide, and
    # dsp4_bootstats.py pools files anyway. Pass --csv to override.
    ap.add_argument('--csv', default=None)
    ap.add_argument('--tag', default='base', help='arm name, written to CSV')
    ap.add_argument('--product', default='d24')
    ap.add_argument('--config-chips', default='1',
                    help='comma list of chips to configure (default 1, as '
                         'every bench _run.sh does); "none" to skip config '
                         'and characterise the BOOT half alone')
    ap.add_argument('--order', default='1,2', help='boot order, e.g. 2,1')
    ap.add_argument('--dev', default='0.0')
    ap.add_argument('--speed', type=int, default=10_000_000)
    ap.add_argument('--spi-mode', type=int, default=dsp4_boot.SPI_MODE)
    ap.add_argument('--chunk', type=int, default=dsp4_boot.CHUNK)
    ap.add_argument('--spi-cmd', default=hex(dsp4_boot.SPICMD_SINGLE_BIT))
    ap.add_argument('--sync-poll', action='store_true',
                    help="wait out H1S1's ADAU meter-poll burst before "
                         'streaming (dsp4_boot.sync_to_gap)')
    ap.add_argument('--post-reset-delay', type=float, default=dsp4_boot.POST_RESET_S)
    ap.add_argument('--no-reset', action='store_true',
                    help='warm arm: stream without pulsing !RST_D')
    ap.add_argument('--settle', type=float, default=5.0,
                    help='seconds between the stream and the pre-config probe')
    ap.add_argument('--config-settle', type=float, default=3.0)
    ap.add_argument('--recheck', type=float, default=15.0,
                    help='seconds after a failed cycle before the recheck '
                         'probe that tests unaided recovery (0 = skip)')
    args = ap.parse_args()

    args.order = [int(x) for x in args.order.split(',') if x.strip()]
    cfg_chips = ([] if args.config_chips.lower() in ('none', '')
                 else [int(x) for x in args.config_chips.split(',')])
    args.spi_cmd_val = (None if str(args.spi_cmd).lower() in ('none', 'off')
                        else int(str(args.spi_cmd), 0))

    streams = {}
    for chip in (1, 2):
        path = os.path.join(args.dir, f'chip{chip}.ldr')
        if not os.path.isfile(path):
            sys.exit(f'missing {path}')
        streams[chip] = pad(open(path, 'rb').read())

    fields = ['tag', 'cycle', 'ts', 'speed', 'spi_mode', 'post_reset',
              'no_reset', 'order', 'sync', 'cfg_chips',
              'boot1_ok', 'boot1_ms', 'boot1_err',
              'boot2_ok', 'boot2_ms', 'boot2_err',
              'rdy1_pre', 'rdy2_pre', 'rdy1_post', 'rdy2_post']
    for phase in ('pre', 'post', 'rechk'):
        for chip in (1, 2):
            for k in PROBE_KEYS:
                fields.append(f'{phase}{chip}_{k}')
    fields += ['cfg_ok', 'cfg_detail', 'verdict']

    if args.csv is None:
        args.csv = 'bootchar_%s.csv' % args.tag

    # APPEND ONLY TO A FILE WHOSE HEADER MATCHES. The probe's register list
    # grew when DSP4_CFG_WATCH landed, and appending the wider rows under
    # the narrower header silently shifted every column in the file — the
    # rows still parsed, they just meant something else. Refuse instead.
    new = not os.path.exists(args.csv)
    if not new:
        with open(args.csv, newline='') as chk:
            have = next(csv.reader(chk), [])
        if have != fields:
            sys.exit(f'{args.csv} was written with a different column set '
                     f'({len(have)} columns, this run has {len(fields)}). '
                     f'Use a different --csv rather than appending rows the '
                     f'header does not describe.')
    fh = open(args.csv, 'a', newline='')
    w = csv.DictWriter(fh, fieldnames=fields, extrasaction='ignore')
    if new:
        w.writeheader()

    tally = {}
    for cycle in range(1, args.cycles + 1):
        row = {k: '' for k in fields}
        row.update(tag=args.tag, cycle=cycle,
                   ts=time.strftime('%FT%TZ', time.gmtime()),
                   speed=args.speed, spi_mode=args.spi_mode,
                   post_reset=args.post_reset_delay,
                   no_reset=int(args.no_reset),
                   order=','.join(str(c) for c in args.order),
                   sync=int(args.sync_poll),
                   cfg_chips=','.join(str(c) for c in cfg_chips) or 'none')
        one_cycle(args, streams, row)
        time.sleep(args.settle)
        for chip in (1, 2):
            for k, v in probe(chip).items():
                if k in PROBE_KEYS:
                    row[f'pre{chip}_{k}'] = '' if v is None else v
        if cfg_chips:
            ok = True
            details = []
            for chip in cfg_chips:
                o, d = config_once(chip, args.product)
                ok = ok and o
                details.append(f'c{chip}:{d}')
            row['cfg_ok'] = int(ok)
            row['cfg_detail'] = '; '.join(details)[:100]
            time.sleep(args.config_settle)
            for chip in (1, 2):
                for k, v in probe(chip).items():
                    if k in PROBE_KEYS:
                        row[f'post{chip}_{k}'] = '' if v is None else v
            stage_key, frames_key = 'post1_stage', 'post1_frames'
        else:
            stage_key, frames_key = 'pre1_stage', 'pre1_frames'

        stage = row.get(stage_key, '')
        want = 6 if cfg_chips else 5
        if stage == '' or row.get('pre1_magic', '') == '':
            verdict = 'WEDGE_LINK'          # chip 1 never answered at all
        elif int(stage) >= want:
            verdict = 'OK'
        else:
            verdict = f'WEDGE_STAGE{stage}'
        # chip 2 is booted but never configured, so stage 5 is its pass mark
        if row.get('pre2_magic', '') == '':
            verdict += '+C2LINK'
        elif row.get('pre2_stage', '') not in ('', None) and \
                int(row['pre2_stage']) < 5:
            verdict += f"+C2STAGE{row['pre2_stage']}"
        row['verdict'] = verdict

        if verdict != 'OK' and args.recheck:
            time.sleep(args.recheck)
            for chip in (1, 2):
                for k, v in probe(chip).items():
                    if k in PROBE_KEYS:
                        row[f'rechk{chip}_{k}'] = '' if v is None else v

        w.writerow(row)
        fh.flush()
        tally[verdict] = tally.get(verdict, 0) + 1
        print(f'[{args.tag}] cycle {cycle}/{args.cycles}: {verdict:16s} '
              f'boot1 {row["boot1_ok"]}/{row["boot1_ms"]}ms '
              f'boot2 {row["boot2_ok"]}/{row["boot2_ms"]}ms '
              f'pre c1 stage={row["pre1_stage"]!r} id={row["pre1_id"]!r} '
              f'c2 stage={row["pre2_stage"]!r} id={row["pre2_id"]!r} '
              f'post c1 stage={row["post1_stage"]!r} '
              f'phase={row["post1_phase"]!r} cgufail={row["post1_cgufail"]!r} '
              f'it={row["post1_it1"]!r}/{row["post1_it2"]!r}/'
              f'{row["post1_it3"]!r}/{row["post1_it4"]!r} '
              f'pfix={row["post1_pfix"]!r} rx={row["post1_rx"]!r}'
              + (f' rechk c1 stage={row["rechk1_stage"]!r}'
                 if verdict != 'OK' and args.recheck else ''), flush=True)

    fh.close()
    ok = tally.get('OK', 0)
    n = args.cycles
    print(f'\n[{args.tag}] {ok}/{n} clean on one attempt '
          f'({100.0 * ok / n:.1f}%)')
    for k in sorted(tally):
        print(f'    {k:20s} {tally[k]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
