#!/usr/bin/env python3
"""d24_boards.py -- the D24 board test: one board, swapped into a known-good
unit, tested by the factory runner on the rows that exercise it (NAMM-D24-6).

PW 2026-10-28: "i also need test fixture code working to help me test the PCBs
for new D24 revC models." There is no fixture hardware yet, so the fixture is
a whole unit: MW-D24-2 with every other board known-good, the new board swapped
in, and the factory runner (`d24_runall.py`) run over the subset of catalog
rows that the new board is on. Nothing about HOW a row is tested changes; this
file decides WHICH rows, and under WHOSE name the verdicts are kept.

A BOARD PROFILE is that subset. Each row in it has a role:

    home     the part the row tests is ON this board
    link     the row tests a connection that crosses this board (a connector,
             a trace between two boards) -- a fail implicates this board or the
             board at the other end, and the other end is known-good
    carrier  the row is run only because another row in the profile is graded
             inside it (row 93's jack-sense is graded by the mini-jack patches)

A row the runner cannot run (no test written, fixture not built) stays in the
profile on purpose: the board's report lists it NOT TESTED with the runner's
own reason, which is the "missing test" list -- never silently dropped (S117
section 1).

THE BOARD SESSION. `board.conf` beside `list.conf` and `pair.conf`
(/home/app/selftest), written by the desk (`tools/accept/board_test.py start`)
and removed by it (`... end`). While it exists, every pass -- the glass START
included, which runs the runner with no arguments -- is a pass of THAT board:
the rows are the profile's, the cumulative state and the ignores are keyed on
the board's ID, and a resume runs that board's untested rows only. Without it
the runner is the whole-unit factory pass, unchanged. A bench session that
writes it owns removing it.

THE BOARD ID is the FIX-L2 label (fixtures common/docs/fix-labels-traceability
.md section 1.1): 7 Crockford base32 characters + 1 Luhn mod 32 check
character, printed as two groups of four. Typed for now (no scanner, no issued
roll register); a typed ID is normalised the way the station will be: lower
case accepted, O -> 0, I and L -> 1, hyphens and spaces ignored.

    python3 d24_boards.py --check-id 7KQ3-M9XD     # is this a label ID?
    python3 d24_boards.py --make-id 7KQ3M9X        # payload -> full ID
    python3 d24_boards.py --profiles               # the profiles, one line each
    python3 d24_boards.py --self-test
"""
import argparse
import os
import sys

# ---------------------------------------------------------------------------
# FIX-L2 board ID
# ---------------------------------------------------------------------------
ALPHABET = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'       # Crockford: no I L O U
N = len(ALPHABET)
_FOLD = {'O': '0', 'I': '1', 'L': '1'}


def normalise_id(text):
    """What the operator typed -> the 8 characters, or raise ValueError with a
    sentence an operator can act on."""
    s = ''.join(_FOLD.get(c, c) for c in (text or '').upper()
                if c not in '- \t')
    bad = sorted(set(c for c in s if c not in ALPHABET))
    if bad:
        raise ValueError('a board label has no %s in it' % ', '.join(bad))
    if len(s) != 8:
        raise ValueError('a board label is 8 characters, this is %d' % len(s))
    if not _luhn_ok(s):
        raise ValueError('the label does not check: one character is mistyped')
    return s


def _luhn_sum(chars, first_factor):
    f, t = first_factor, 0
    for c in reversed(chars):
        a = f * ALPHABET.index(c)
        t += a // N + a % N
        f = 3 - f
    return t


def _luhn_ok(s):
    return _luhn_sum(s, 1) % N == 0


def check_char(payload):
    """Luhn mod 32 check character for a 7-character payload."""
    return ALPHABET[(N - _luhn_sum(payload, 2) % N) % N]


def make_id(payload):
    p = ''.join(_FOLD.get(c, c) for c in payload.upper() if c not in '- ')
    if len(p) != 7 or any(c not in ALPHABET for c in p):
        raise ValueError('a payload is 7 Crockford characters')
    return p + check_char(p)


def show_id(s):
    """How the label prints it: two groups of four."""
    return '%s-%s' % (s[:4], s[4:])


# ---------------------------------------------------------------------------
# The profiles
# ---------------------------------------------------------------------------
HOME, LINK, CARRIER = 'home', 'link', 'carrier'


def _rows(role, *spans):
    out = {}
    for s in spans:
        for n in (range(s[0], s[1] + 1) if isinstance(s, tuple) else (s,)):
            out[n] = role
    return out


def _merge(*parts):
    d = {}
    for p in parts:
        for n, role in p.items():
            d.setdefault(n, role)           # first role named wins
    return d


# Where each part is, from MW/D24/HW/hardware-map.md (sections 1, 2, 4) and
# the catalog's own `board` column. The catalog files a part under
# "Assemblies" or "Inter-board links" rather than under the board it sits on,
# so the catalog alone cannot say which rows a board owns: this table can.
#
#   DSP card     U3 CPLD, U5/U6 SHARC, U7 H1S1 (S MCU), U8 MH1 (M MCU), Y1, and
#                every DSP-side end of the CS/RDY/RST/CS_M/CS_C lines
#   Digital      CM4 carrier, Ethernet, HDMI0 + its power, the USB hub, U34
#                power MCU, the MEMS bridge and speaker amp, mains inlet and
#                switch, the pedal socket, the option slots, the converter
#                FPCs J41/J42, and the CM4 end of every DSP-card line
#   Analog       preamps, ADC/DAC converters, the 595 gain chain, the talkback
#                codec, every analog socket, the top-panel USB pair
#   Phone Jack   the four stereo TRS jacks (Aux Out A 1-8) and Phones 1
#   Left/Right   the switch panels, their MCUs (H1S4/H1S3) and what passes
#                through them (talkback mic, mini-jack sense, temp/fan sense)
#   P1 pedal     the pedal itself
#
# AL1 (row 56) is in four profiles: its tone leaves DSP B, goes out through the
# talkback codec (Analog) and the speaker amp (Digital), and comes back off the
# panel microphone (Left Switch) through the MEMS bridge (Digital). It needs no
# lead and no hand, so it costs nothing to run in every board it crosses.
_DSP_LINES = _rows(LINK, (102, 112), 125, 126)      # CM4 <-> DSP card wiring
_SWITCH_LINKS = _rows(LINK, 143, 144)

PROFILES = {
    'dsp': dict(
        name='DSP card', label='DSP',
        rows=_merge(
            _rows(HOME, (102, 112), 194, 195, 196, 201, 202, (113, 124),
                  (164, 168)),
            _rows(LINK, 125, 126, (139, 144), 197, 198, 199, 56)),
        note='the automatic set only: every row is answered by the unit '
             'itself, no leads, no hands'),
    'digital': dict(
        name='Digital board', label='Digital',
        rows=_merge(
            _rows(HOME, 127, 128, 129, 132, 133, 134, 151, 193, 200, 203,
                  (169, 192), (135, 138), 149, 152),
            _DSP_LINES,
            _rows(LINK, (139, 142), 143, 144, 145, 148, 150, 130, 131,
                  197, 198, 199, 56)),
        note='the automatic set, the two top-panel USB sticks and the mains '
             'inlet; no analog leads'),
    'analog': dict(
        name='Analog board', label='Analog',
        rows=_merge(
            _rows(HOME, (1, 38), 95, 96, 130, 131, 197, 198, 199, 111, 112,
                  (153, 163)),
            _rows(LINK, (39, 42), 97, 141, 142, 146, 147, 150, 56)),
        whole_station=True,
        note='every analog socket: the whole patch list, 24 inputs'),
    'phonejack': dict(
        name='Phone Jack board', label='Phone Jack',
        rows=_merge(_rows(HOME, (39, 42), 97), _rows(LINK, 146)),
        note='the four stereo jacks and the front phones jack: the jack '
             'patches of the analog station only'),
    'left': dict(
        name='Left switch panel', label='Left Switch',
        rows=_merge(_rows(HOME, (43, 56), 58),
                    _rows(LINK, 126, 144)),
        note='the left panel loop, the talkback microphone and speaker, '
             'and the panel processor link'),
    'right': dict(
        name='Right switch panel', label='Right Switch',
        rows=_merge(_rows(HOME, (59, 94)),
                    _rows(LINK, 125, 143),
                    _rows(CARRIER, 95, 96)),
        note='the right panel loop and the panel processor link; the two '
             'mini-jack patches carry the jack-sense check'),
    'p1': dict(
        name='P1 foot pedal', label='P1',
        rows=_merge(_rows(HOME, (98, 101)),
                    _rows(LINK, 129, 145, 58)),
        pedal_station=True,
        note='plug the pedal in: its link is checked over the cable; the '
             'footswitches and the display are not graded yet'),
}
ORDER = ('dsp', 'digital', 'analog', 'phonejack', 'left', 'right', 'p1')
assert set(ORDER) == set(PROFILES)


def profile(key):
    try:
        return PROFILES[key]
    except KeyError:
        raise ValueError('no board profile %r; the profiles are %s'
                         % (key, ', '.join(ORDER)))


def scope(rows, key):
    """The catalog rows a board's test runs, in catalog order. Rows the
    profile names that the catalog does not have are an error: a renumbered
    catalog must not quietly shrink a board's test."""
    want = profile(key)['rows']
    have = set(r.num for r in rows)
    gone = sorted(set(want) - have)
    if gone:
        raise ValueError('the %s profile names rows the catalog does not '
                         'have: %s' % (key, ', '.join(map(str, gone))))
    return [r for r in rows if r.num in want]


# ---------------------------------------------------------------------------
# board.conf -- the board session on the unit
# ---------------------------------------------------------------------------
BOARD_CONF = '/home/app/selftest/board.conf'


def read_conf(path=BOARD_CONF):
    """{'profile': ..., 'id': ..., ...} or None when no board session is open.
    A file that is there but wrong is an error, not "no session": a bench that
    meant to test a board must never fall through to a whole-unit pass."""
    try:
        with open(path) as fh:
            text = fh.read()
    except OSError:
        return None
    d = {}
    for ln in text.splitlines():
        ln = ln.split('#', 1)[0].strip()
        if not ln:
            continue
        if '=' not in ln:
            raise SystemExit('%s: "%s" is not key=value' % (path, ln))
        k, v = ln.split('=', 1)
        d[k.strip()] = v.strip()
    if not d:
        return None
    try:
        profile(d.get('profile', ''))
        d['id'] = normalise_id(d.get('id', ''))
    except ValueError as e:
        raise SystemExit('%s: %s' % (path, e))
    return d


def conf_text(key, board_id, rev='', operator=''):
    profile(key)
    lines = ['# D24 board session (NAMM-D24-6). While this file exists every',
             '# runner pass tests this board only. tools/accept/board_test.py',
             '# end removes it.',
             'profile=%s' % key, 'id=%s' % normalise_id(board_id)]
    if rev:
        lines.append('rev=%s' % rev)
    if operator:
        lines.append('operator=%s' % operator)
    return '\n'.join(lines) + '\n'


# ---------------------------------------------------------------------------
# The coverage table (the review stop's table is generated, not typed)
# ---------------------------------------------------------------------------
def coverage(rows):
    """Per profile: (key, [(num, role, category, reason, name)]). `rows` must
    be classified (`d24_runall.classify`)."""
    out = []
    for key in ORDER:
        p = PROFILES[key]
        lines = []
        for r in scope(rows, key):
            lines.append((r.num, p['rows'][r.num], r.category, r.reason,
                          r.item))
        out.append((key, lines))
    return out


def unassigned(rows):
    """Catalog rows no profile names."""
    named = set()
    for p in PROFILES.values():
        named.update(p['rows'])
    return [r for r in rows if r.num not in named]


# ---------------------------------------------------------------------------
def _self_test():
    fails = []

    def ok(name, cond):
        print('%-4s %s' % ('ok' if cond else 'FAIL', name))
        if not cond:
            fails.append(name)
    full = make_id('7KQ3M9X')
    ok('a made ID checks', _luhn_ok(full))
    ok('typed with a hyphen and lower case', normalise_id(
        show_id(full).lower()) == full)
    for i in range(8):
        for c in ALPHABET:
            if c == full[i]:
                continue
            bad = full[:i] + c + full[i + 1:]
            if _luhn_ok(bad):
                ok('single change at %d to %s caught' % (i, c), False)
    ok('every single-character change is caught', not any(
        'single change' in f for f in fails))
    swaps = 0
    for i in range(7):
        sw = full[:i] + full[i + 1] + full[i] + full[i + 2:]
        if sw != full and _luhn_ok(sw):
            swaps += 1
    ok('adjacent swaps of this ID caught', swaps == 0)
    ok('O and I/L fold', normalise_id(full.replace('0', 'O')) == full)
    for bad, why in (('ABC', '8 characters'), (full[:7] + 'U', 'no U'),
                     (full[:7] + ALPHABET[(ALPHABET.index(full[7]) + 1) % N],
                      'does not check')):
        try:
            normalise_id(bad)
            ok('refused: %s' % why, False)
        except ValueError as e:
            ok('refused: %s (%s)' % (why, e), True)
    ok('no profile is empty', all(p['rows'] for p in PROFILES.values()))
    ok('every role is known', all(v in (HOME, LINK, CARRIER)
                                  for p in PROFILES.values()
                                  for v in p['rows'].values()))
    txt = conf_text('dsp', show_id(full), rev='C')
    import tempfile
    with tempfile.NamedTemporaryFile('w', delete=False) as fh:
        fh.write(txt)
    d = read_conf(fh.name)
    os.unlink(fh.name)
    ok('board.conf round-trips', d['profile'] == 'dsp' and d['id'] == full
       and d['rev'] == 'C')
    ok('no board.conf is no session', read_conf('/nonexistent/board.conf')
       is None)
    print('%s' % ('all checks passed' if not fails
                  else '%d check(s) FAILED' % len(fails)))
    return 1 if fails else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check-id', metavar='ID')
    ap.add_argument('--make-id', metavar='PAYLOAD')
    ap.add_argument('--profiles', action='store_true')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args(argv)
    if a.self_test:
        return _self_test()
    if a.check_id:
        try:
            s = normalise_id(a.check_id)
        except ValueError as e:
            print('NOT a board label: %s' % e)
            return 1
        print('board label %s' % show_id(s))
        return 0
    if a.make_id:
        print(show_id(make_id(a.make_id)))
        return 0
    if a.profiles:
        for k in ORDER:
            p = PROFILES[k]
            print('%-10s %-20s %3d rows  %s' % (k, p['name'], len(p['rows']),
                                                p['note']))
        return 0
    ap.print_help()
    return 0


if __name__ == '__main__':
    sys.exit(main())
