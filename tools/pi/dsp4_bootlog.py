#!/usr/bin/env python3
"""dsp4_bootlog.py — one append-only line per boot attempt and per diag read.

Session 13's first finding was that the boot+config failure rate had never
been measured: every bench script wraps the boot in a retry ladder and
reports only the last attempt, so a per-cycle rate of a few percent was
recorded for four sessions as "~2 boots in 8 wedge". The fix is not another
one-off script — it is that the two tools EVERY bench script already goes
through keep a record of their own, so the rate is a tracked number without
anyone remembering to track it.

dsp4_boot.py appends one row per chip per ATTEMPT (so a retry is visible as
a retry, never hidden behind the attempt that worked), and dsp4_diag.py
appends one row per CLI dump carrying MAGIC, CHIP_ID and BOOT_STAGE
together — MAGIC being the anchor that separates a genuinely wedged part
from a dropped answer, which the protocol's echo check does not.

Default path: ./bootlog.csv (i.e. /home/app/dspboot/bootlog.csv on the
bench). DSP4_BOOTLOG overrides it; DSP4_BOOTLOG=off disables logging.
Failures to write are swallowed — a logging problem must never take a
bench run down with it.
"""

import csv
import os
import sys
import time

FIELDS = ['ts', 'tool', 'chip', 'attempt', 'ok', 'ms', 'bytes',
          'magic', 'stage', 'note']


def path():
    p = os.environ.get('DSP4_BOOTLOG', 'bootlog.csv')
    return None if p.lower() in ('off', 'none', '') else p


def log(**kw):
    p = path()
    if p is None:
        return
    row = {k: '' for k in FIELDS}
    row['ts'] = time.strftime('%FT%TZ', time.gmtime())
    row['tool'] = os.path.basename(sys.argv[0] or 'python')
    row.update({k: v for k, v in kw.items() if k in FIELDS})
    try:
        new = not os.path.exists(p)
        with open(p, 'a', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS, extrasaction='ignore')
            if new:
                w.writeheader()
            w.writerow(row)
    except OSError:
        pass
