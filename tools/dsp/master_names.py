#!/usr/bin/env python3
"""master_names.py — the master cell-name spellings, in one place.

Two facts about cell names are needed by the generator, the wire-contract
join and every bench probe, and they must not drift apart:

1. THE Rtg RETIREMENT (mx26 ruling 2026-08-25). The masters dropped the
   `Rtg` infix from the routing cells: `Chan001RtgMute001` is now
   `Chan001Mute001`, and `RtgFx` became `FxOn` because the family is an
   on/off rather than a routing verb. `docs/contract/<p>-wire-table.csv`
   — mx26's own generated wire table, byte-identical to the copy in this
   tree — is the authority for the spelling.

2. THE DEFS PIN LAGS IT. `defs.lock` pins `defs-v2026.08.20`; the rename
   landed after it on an mx26 commit that carries no contract tag, and
   `sync-from-mx26.sh --update-lock` refuses an untagged HEAD by design.
   So `MW/*/MX/_matrix.csv` in this repo still spells the old names, and
   anything joining the matrix to the wire table has to translate.

THIS MODULE IS TEMPORARY. When the pin advances past the rename, every
lookup resolves by its current name, `gen_dsp.py` reports 0 legacy hits,
and the table goes.
"""

import csv
import os
import re

# current master suffix -> the suffix defs-v2026.08.20 still carries
MASTER_RENAME_2026_08_25 = {
    'Level':        'RtgLevel',
    'Pan':          'RtgPan',
    'Mute':         'RtgMute',
    'MainOn':       'RtgMainOn',
    'CtrOn':        'RtgCtrOn',
    'GrpOn':        'RtgGrpOn',
    'AuxOn':        'RtgAuxOn',
    'AuxSend':      'RtgAuxSend',
    'AuxPick':      'RtgAuxPick',
    'FxOn':         'RtgFx',
    'FxSend':       'RtgFxSend',
    'FxPick':       'RtgFxPick',
    'MatrixOn':     'RtgMatrixOn',
    'MatrixSend':   'RtgMatrixSend',
    'Dest':         'Rtg',
    # Renamed in the masters too, but no generator emits a cell for it:
    # `Dca` is HOST-MANAGED (PW ruling 2026-08-30). Listed so the tools can
    # tell the pinned matrix's `Aux001RtgDca001` from an unaccounted row.
    'Dca':          'RtgDca',
}

LEGACY_TO_CURRENT = {v: k for k, v in MASTER_RENAME_2026_08_25.items()}

# Cat + instance + suffix + function, e.g. Chan001AuxSend012
CELL_RE = re.compile(r'^([A-Za-z]+)(\d{3})([A-Za-z]+)(\d{3})$')


def split_cell(cell):
    """('Chan', '001', 'AuxSend', '012'), or None if not cell-shaped."""
    m = CELL_RE.match(cell)
    return m.groups() if m else None


def suffix(cell):
    """Chan001DcaOn001 -> 'DcaOn'; None if the name is not cell-shaped."""
    parts = split_cell(cell)
    return parts[2] if parts else None


def current_name(cell):
    """The name the CURRENT masters use for a legacy `_matrix.csv` cell.

    Unchanged when the cell is already current, or is not cell-shaped.
    """
    parts = split_cell(cell)
    if not parts:
        return cell
    cat, inst, suf, fun = parts
    cur = LEGACY_TO_CURRENT.get(suf)
    return f'{cat}{inst}{cur}{fun}' if cur else cell


def legacy_name(cell):
    """The name defs-v2026.08.20's `_matrix.csv` carries for a current cell.

    Returns None when the suffix was not renamed — the caller wants the
    current name in that case, and conflating the two hides misses.
    """
    parts = split_cell(cell)
    if not parts:
        return None
    cat, inst, suf, fun = parts
    legacy = MASTER_RENAME_2026_08_25.get(suf)
    return f'{cat}{inst}{legacy}{fun}' if legacy else None


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
