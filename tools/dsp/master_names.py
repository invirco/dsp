#!/usr/bin/env python3
"""master_names.py — cell-name shape and the host-managed families.

The generator, the wire-contract join and every bench probe need the same
answer to "what is this cell called and who owns it", and they must not
drift apart.

THERE IS NO RENAME TABLE HERE ANY MORE. Until defs-v2026.09.08 this
module carried MASTER_RENAME_2026_08_25, a translation between the
spelling `MW/*/MX/_matrix.csv` was pinned at (`Chan001RtgMute001`,
`AaChan001Mtr001`) and the spelling the masters had moved on to
(`Chan001Mute001`, `Chan001Mtr001`). The pin has advanced past the
rename: `defs/` is the one source, the expansion carries the current
spelling, and every lookup now resolves by the master's own name. An
alias reintroduced here would be a second source of truth by another
route — see the S1 dispatch, 2026-09-08.
"""

import csv
import os
import re

# Cat + instance + suffix + function, e.g. Chan001AuxSend012.
# The suffix admits digits after its first letter: D24 carries
# `Main001Out3Mode001`, and a letters-only class silently treats that as
# "not cell-shaped" rather than as the cell it is.
CELL_RE = re.compile(r'^([A-Za-z]+)(\d{3})([A-Za-z][A-Za-z0-9]*)(\d{3})$')


def split_cell(cell):
    """('Chan', '001', 'AuxSend', '012'), or None if not cell-shaped."""
    m = CELL_RE.match(cell)
    return m.groups() if m else None


def category(cell):
    """Chan001DcaOn001 -> 'Chan'; None if the name is not cell-shaped."""
    parts = split_cell(cell)
    return parts[0] if parts else None


def suffix(cell):
    """Chan001DcaOn001 -> 'DcaOn'; None if the name is not cell-shaped."""
    parts = split_cell(cell)
    return parts[2] if parts else None


# ---------------------------------------------------------------------------
# Host-managed families
# ---------------------------------------------------------------------------
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DSP_CSV = os.path.join(_ROOT, 'MW/D32/DSP/SHARC/dsp.csv')

_HOST_MANAGED = None


def host_managed_families(dsp_csv=None):
    """Cell families the HOST owns outright, read from dsp.csv.

    PW's 2026-08-30 ruling (Q2 closed) put the DCA fold in the CM4 control
    daemon: the effective fader is `fader dB + DCA dB` with the mutes
    OR-ed, written through the fader TARGET the DSP already ramps. So
    `Dca` and `DcaOn` get no DSP address and no line of the kernel reads
    them. The node that used to carry the word declares the departure with
    `host_cells=`, which makes dsp.csv the one source for it.

    A family here is NOT a gap: it is the reason the cells under it have
    no address. An unaddressed cell nothing accounts for is a finding; an
    unaddressed cell a ruling accounts for is a decision, and the two have
    to read differently.
    """
    global _HOST_MANAGED
    path = dsp_csv or DSP_CSV
    if _HOST_MANAGED is None or dsp_csv:
        fams = set()
        with open(path, newline='', encoding='utf-8') as fh:
            for row in csv.DictReader(fh):
                for pair in (row.get('params') or '').split(';'):
                    k, _, v = pair.partition('=')
                    if k.strip() == 'host_cells':
                        fams.update(f.strip() for f in v.split(',') if f.strip())
        if dsp_csv:
            return fams
        _HOST_MANAGED = fams
    return _HOST_MANAGED
