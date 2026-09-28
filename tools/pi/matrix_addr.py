#!/usr/bin/env python3
"""matrix_addr.py -- resolve matrix cell addresses BY NAME from the unit's own
DEPLOYED pack, never a literal baked into a station tool (S136).

Hub ruling this exists to enforce: "cell names are the invariant contract,
addresses are per-build artifacts" and "generate, never transcribe". S135
found `d24_panel.py` hard-coding `SKIN = 0x1524` (Sys001Skin001 = 5412),
which was only ever true of MW-D24-2's 2026-08-18 pack; after the S131
switch-over the same name is 4698. A literal address is therefore not a
constant, it is a snapshot of one unit's one pack, and every station tool
that baked one in broke the moment that pack moved.

WHERE THE ADDRESS COMES FROM. mx26's own resolution order
(`Core/AppContext.ResolveMatrixPath`, findings S45-2): `{HomePath}/config/
_matrix.mxc` packed, else `{HomePath}/config/_matrix.csv`, else the published
`{store}/Products/<P>/pd/generated/_matrix.csv`. This module walks the same
list, so a station tool resolves a name to whatever address the app it is
testing ALONGSIDE would also resolve it to -- never a different generation's
answer. `.mxc` is the container `defs/tools/mxc_pack.py` defines: magic
"MXC1", a little-endian int32 length, then the CSV bytes XORed with a fixed
key; unpacked here rather than imported, because this file runs ON the unit's
CM4 and the `defs/` submodule is not staged there.

A NAME MISSING FROM THE DEPLOYED PACK IS NOT AN ERROR HERE. It is the
expected shape of "not yet switched over" (`Sys001SwLeft001`/
`Sys001SwTalk001` on the 08-18 pack) and callers report it as NOT TESTED /
"cell not in this unit's matrix (generation X)" -- never a guessed address,
never a crash. What IS fatal is the pack itself being unreadable or
malformed: that fails loudly, per the repo's no-fallback policy, because a
tool that cannot read the pack at all has no business guessing.

    python3 matrix_addr.py Sys001Skin001 Sys001SwLeft001    # print or "ABSENT"
    python3 matrix_addr.py --describe                        # generation header
"""
import csv
import hashlib
import io
import os
import struct
import sys

MXC_MAGIC = b'MXC1'
MXC_XOR_KEY = b'Mx2024ConfigFmt!'

HOME = os.environ.get('MATRIX_ADDR_HOME', os.path.expanduser('~'))

# mx26 AppContext.ResolveMatrixPath order (findings S45-2): the packed form
# first, then its plain CSV, then the published store copy. `PRODUCT`/`STORE`
# only matter for the last tier, which nothing on-unit can reach anyway.
DEFAULT_CANDIDATES = (
    os.path.join(HOME, 'config', '_matrix.mxc'),
    os.path.join(HOME, 'config', '_matrix.csv'),
)


class MatrixPackError(Exception):
    """The deployed pack could not be found or could not be parsed. This is
    always fatal -- a name simply absent from a pack that DID parse is not
    this, see `CellNotInPack`."""


class CellNotInPack(LookupError):
    """`name` is not in this unit's deployed pack. Not a crash: report it."""

    def __init__(self, name, generation):
        self.name, self.generation = name, generation
        super().__init__(
            'cell not in this unit\'s matrix (generation %s): %s'
            % (generation, name))


def _mxc_unxor(data):
    n = len(MXC_XOR_KEY)
    return bytes(b ^ MXC_XOR_KEY[i % n] for i, b in enumerate(data))


def _unpack_mxc(raw):
    if raw[:4] != MXC_MAGIC:
        raise MatrixPackError('not an MXC file (bad magic): %r' % raw[:4])
    (length,) = struct.unpack('<i', raw[4:8])
    encoded = raw[8:8 + length]
    if len(encoded) != length:
        raise MatrixPackError('truncated MXC (want %d bytes, got %d)'
                              % (length, len(encoded)))
    return _mxc_unxor(encoded)


def _parse_matrix_csv(csv_bytes):
    text = csv_bytes.decode('utf-8-sig', errors='replace')
    rdr = csv.DictReader(io.StringIO(text))
    if not rdr.fieldnames or '_Cell' not in rdr.fieldnames or 'MxAdd' not in rdr.fieldnames:
        raise MatrixPackError('expected _matrix.csv header with _Cell + MxAdd '
                              '(got: %s)' % (rdr.fieldnames,))
    pairs = {}
    for row in rdr:
        name = (row.get('_Cell') or '').strip()
        add = (row.get('MxAdd') or '').strip()
        if not name or not add:
            continue
        pairs.setdefault(name, []).append(int(add))
    if not pairs:
        raise MatrixPackError('no (_Cell, MxAdd) rows found')
    return pairs


def _base_id(pairs):
    """Same fingerprint as `defs/tools/matrix_gen_id.py`'s base-id, so a
    report header naming a generation here matches that tool's answer for
    the same pack."""
    lines = ('%s=%d' % (n, sorted(a)[0]) for n, a in sorted(pairs.items()))
    return hashlib.sha256('\n'.join(lines).encode()).hexdigest()[:12]


class MatrixPack(object):
    """One unit's deployed name->address table, read once and cached.

    `path` overrides the resolution order (tests, or a pack pulled off a
    different unit); otherwise the first of `DEFAULT_CANDIDATES` that exists
    is used, exactly as `AppContext.ResolveMatrixPath` would pick it.
    """

    def __init__(self, path=None):
        self.path = path or self._find()
        raw = open(self.path, 'rb').read()
        csv_bytes = _unpack_mxc(raw) if raw[:4] == MXC_MAGIC else raw
        self.pairs = _parse_matrix_csv(csv_bytes)
        self.generation = _base_id(self.pairs)

    @staticmethod
    def _find():
        for p in DEFAULT_CANDIDATES:
            if os.path.isfile(p):
                return p
        raise MatrixPackError(
            'no deployed matrix pack found (looked for: %s)'
            % ', '.join(DEFAULT_CANDIDATES))

    def address(self, name):
        """The cell's base address, or raise `CellNotInPack` -- never a
        guess, never a crash."""
        if name not in self.pairs:
            raise CellNotInPack(name, self.generation)
        return sorted(self.pairs[name])[0]

    def try_address(self, name):
        """`(address, None)` or `(None, reason)` -- for callers that want a
        row to print rather than an exception to catch."""
        try:
            return self.address(name), None
        except CellNotInPack as e:
            return None, str(e)

    def describe(self):
        return {'path': self.path, 'generation': self.generation,
                'cells': len(self.pairs)}


_default_pack = None


def _pack():
    global _default_pack
    if _default_pack is None:
        _default_pack = MatrixPack()
    return _default_pack


def resolve(name):
    """The module-level convenience: resolve one name off the process-wide
    cached pack (found once, reused for the life of the process -- the pack
    does not change under a running station tool)."""
    return _pack().address(name)


def try_resolve(name):
    return _pack().try_address(name)


def generation():
    return _pack().generation


def describe():
    return _pack().describe()


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('names', nargs='*')
    ap.add_argument('--path', help='pack file to read instead of the default search')
    ap.add_argument('--describe', action='store_true')
    a = ap.parse_args()
    pack = MatrixPack(a.path)
    if a.describe or not a.names:
        d = pack.describe()
        print('pack       %s' % d['path'])
        print('generation %s' % d['generation'])
        print('cells      %d' % d['cells'])
    for name in a.names:
        addr, reason = pack.try_address(name)
        print('%-20s %s' % (name, addr if addr is not None else 'ABSENT (%s)' % reason))


if __name__ == '__main__':
    main()
