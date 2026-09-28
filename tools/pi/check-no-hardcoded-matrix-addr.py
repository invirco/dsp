#!/usr/bin/env python3
"""check-no-hardcoded-matrix-addr.py -- the generator-side guard for S136.

WHAT THIS CATCHES. `d24_panel.py` hard-coded `SKIN = 0x1524` and `codec4619.py`
hard-coded `SYS001TEST001 = 0x1526`, both true of MW-D24-2's 2026-08-18 pack
alone; after the S131 switch-over the same names are 4698 and 4699. A NUMBER
literal token that looks like a matrix cell address, sitting in the source of
any tool that talks the CM4 serial matrix bus, is exactly that bug waiting to
happen again -- so this scans for the token, not the bug's symptom.

SCOPE: `codec4619.py` itself -- the CM4 serial-matrix-bus transport (raw
termios on /dev/serial0, `cell_line`/`cell_prefix`) -- plus every
`tools/pi/*.py` file that `import`s it. `codec4619.py` is scanned directly
and unconditionally (S141: it does not `import codec4619`, so the old
import-only filter silently skipped the one file that actually had the S136
bug -- `SYS001TEST001 = 0x1526` sat in it undetected for two sessions because
this guard only ever looked at its CALLERS). That is deliberately not
"every tools/pi file": the `dsp4_*` tools address a DIFFERENT product's DSP
data memory (D32's SHARC, offsets
computed from that product's own `defs/products/d32/dsp.csv` and resolved at
BUILD time into an ELF map, `dsp4_scope`'s `sym[]` table), never from a
unit's deployed `_matrix.mxc` -- a hex literal there is not this bug's shape,
and folding them into "the deployed pack" story would be inventing a
mechanism that does not exist for that product. If a `dsp4_*` tool ever
starts reading a runtime pack the way the D24 station tools do, it joins this
scope then, not before.

WHAT COUNTS AS THE LITERAL: a NUMBER token, in actual code (never inside a
string or a comment -- `tokenize` already tells those apart), spelled as
exactly four hex digits (`0x` + 4), and assigned directly to a bare NAME
(`NAME = 0xNNNN`) -- the exact shape of the bug (`SYS001TEST001 = 0x1526`,
`SKIN = 0x1524`). Every matrix cell address on this product is
`DspAddHex`-shaped, `0xNNNN` (mx26 `ProjectBuilder.Matrix.cs`). The
assignment-only shape (S141) is deliberate, not a loosening: `codec4619.py`'s
own `cell_prefix()` uses genuine 4-hex-digit bitmasks (`0xF000`..`0xFFFF`)
inline in a tuple, which a bare "any 4-hex NUMBER token" scan flags as a
false positive the moment the file is scanned directly; an assignment is
what actually bakes a snapshot address into a name, a mask used in an
expression never does. `codec4619.py`'s own non-address constants
(`GUARD_FETCH = 0xFB`, the `INIT_IMAGE` register bytes) are one or two hex
digits and do not match either way, and `matrix_addr.py` itself -- which
legitimately parses `0x` from a pack file and unpacks the MXC magic -- is
exempt because the WHOLE POINT of this guard is that name resolution
replaces the literal; the resolver is where it is allowed to live.

    python3 check-no-hardcoded-matrix-addr.py            # exit 1 on any hit
"""
import sys
import tokenize
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXEMPT = {'matrix_addr.py', Path(__file__).name}
HEX4 = __import__('re').compile(r'^0[xX][0-9A-Fa-f]{4}$')


def imports_codec4619(text):
    import re
    return re.search(r'^\s*import\s+codec4619\b', text, re.M) is not None


def needs_scan(path, text):
    """codec4619.py is the transport itself and is always scanned, even
    though it never imports itself (S141)."""
    if path.name == 'codec4619.py':
        return True
    return imports_codec4619(text)


def literal_hits(path):
    hits = []
    with open(path, 'rb') as f:
        try:
            tokens = list(tokenize.tokenize(f.readline))
        except (tokenize.TokenizeError, SyntaxError, IndentationError) as e:
            return [(0, 'could not tokenize: %s' % e)]
    significant = [t for t in tokens if t.type not in (
        tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT,
        tokenize.DEDENT, tokenize.ENCODING)]
    for i, tok in enumerate(significant):
        if tok.type != tokenize.NUMBER or not HEX4.match(tok.string):
            continue
        if i < 2:
            continue
        prev, prevprev = significant[i - 1], significant[i - 2]
        if (prev.type == tokenize.OP and prev.string == '='
                and prevprev.type == tokenize.NAME):
            hits.append((tok.start[0], tok.string))
    return hits


def main():
    bad = []
    for path in sorted(HERE.glob('*.py')):
        if path.name in EXEMPT:
            continue
        text = path.read_text(encoding='utf-8', errors='replace')
        if not needs_scan(path, text):
            continue
        for line, tok in literal_hits(path):
            bad.append((path.name, line, tok))
    if bad:
        print('FAIL: literal matrix-cell-shaped address(es) in station tools '
              '(resolve by name via matrix_addr.py instead -- S136):')
        for name, line, tok in bad:
            print('  %s:%d: %s' % (name, line, tok))
        return 1
    print('OK: no hard-coded matrix addresses in any tools/pi file that '
          'imports codec4619')
    return 0


if __name__ == '__main__':
    sys.exit(main())
