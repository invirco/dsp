#!/usr/bin/env python3
"""dspcard_id.py -- identify the DSP card revision POSITIVELY, for the flash guard.

S174 (PW ruling S173 Q4 (a)): no CPLD and no H1S1 flash without positive
identification of the card. A rev C CPLD image on rev D copper is a bus fight
(S173-2: FSI1-3/BCKI1 into DSPB's outputs, TEST1 into NI0, TEST3 into
PI_TX2), and so is the reverse; an H1S1 image for the wrong U7 does not run.
"Nothing answered" is NOT an identification: a rev D card with a blank U7, or
with a rev C CPLD image, says nothing either.

Runs ON the unit's CM4. Each source below gives a revision or NO EVIDENCE;
none of them guesses.

  H  H1S1's announcement on the matrix bus (d24_bus_probe.stest: S_RUN, then
     '&'; needs /dev/serial0, which matrix-app owns -- stop it first).
       "// H1S1 DSP"              the rev C image; it runs only on the U575
                                  -> rev C
       "// H1S1 DSP G0B1 rev 1"   the rev D port; it runs only on the G0B1 and
                                  names its REV_ID straps (code 1) -> rev D
       anything else, or nothing  no evidence (blank U7, unknown image, a
                                  strap code no revision is defined for)
  K  the CPLD design-ID knock (dsp4_logic_id.knock): an image built for rev D
     (cfg bit 10) reads the BOARD_REV0 strap live (bit 11: low = rev D
     copper), so it identifies the copper whichever card it is on. A rev C
     image does not read the strap: no evidence.
  U  U7's ROM-bootloader chip ID (U575 0x482, G0B1 0x467): NOT AVAILABLE from
     this tool. MH1 has no GET_ID path -- its loader enters the bootloader and
     mass-erases in the same step -- and no SWD channel to U7 is established.

Verdict: C or D when at least one source names a revision and none names the
other; CONFLICT when two disagree (never flash); UNKNOWN when none names one.

    python3 dspcard_id.py                    # both sources, human + JSON line
    python3 dspcard_id.py --want C           # exit 0 only if positively rev C
    python3 dspcard_id.py --no-bus           # knock only (matrix-app running)

Exit: 0 = positive (and equal to --want, if given), 3 = UNKNOWN,
4 = CONFLICT, 5 = positive but not --want.
"""
import argparse
import json
import os
import re
import subprocess
import sys

for _p in ('/home/app/dspboot', '/home/app/selftest',
           os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

REV_D_CODE = 1          # the REV_ID strap code rev D carries (DSPC-L11)
H1S1_REVC = re.compile(r'^//\s*H1S1 DSP\s*$')
H1S1_G0B1 = re.compile(r'^//\s*H1S1 DSP G0B1 rev ([0-9?])\s*$')


def classify_h1s1(line):
    """(revision or None, why) for one H1S1 identity line (or None)."""
    if not line:
        return None, 'no H1S1 announcement (blank or absent U7, or no image)'
    line = line.strip()
    if H1S1_REVC.match(line):
        return 'C', 'H1S1 says %r: the rev C image, which runs only on the U575' % line
    m = H1S1_G0B1.match(line)
    if m:
        code = m.group(1)
        if code == str(REV_D_CODE):
            return 'D', 'H1S1 says %r: the G0B1 port, straps code %s = rev D' % (line, code)
        return None, ('H1S1 says %r: a G0B1 with strap code %s, which no '
                      'revision is defined for' % (line, code))
    return None, 'H1S1 says %r: not an identity this tool knows' % line


def classify_knock(cfg):
    """(revision or None, why) for one knock cfg word (or None)."""
    import dsp4_logic_id as L
    if cfg is None:
        return None, 'no knock reply (no ID-capable CPLD image, or no PCM path)'
    if not cfg & L.CFG_REVD_IMAGE:
        return None, ('knock cfg 0x%04X: a rev C image, which does not read '
                      'the BOARD_REV0 strap' % cfg)
    rev = 'D' if cfg & L.CFG_REVD_BOARD else 'C'
    return rev, ('knock cfg 0x%04X: a rev D image reading BOARD_REV0 %s = rev '
                 '%s copper' % (cfg, 'low' if rev == 'D' else 'high', rev))


def verdict(revs):
    named = set(r for r in revs if r)
    if len(named) > 1:
        return 'CONFLICT'
    if named:
        return named.pop()
    return 'UNKNOWN'


def app_active():
    try:
        return subprocess.run(['systemctl', 'is-active', 'matrix-app'],
                              capture_output=True, text=True).stdout.strip()
    except OSError:
        return 'unknown'


def read_bus(port):
    if app_active() == 'active':
        return None, 'not read: matrix-app is running and owns %s' % port
    try:
        import d24_bus_probe as P
        return P.stest(port)['mcus'].get('H1S1'), None
    except Exception as e:          # an unreadable source is no evidence
        return None, 'not read: %s' % e


def read_knock():
    try:
        import dsp4_logic_id as L
        from collections import Counter
        left, right = L.knock()
        replies = [(l, r) for l, r in zip(left, right) if (r >> 16) == L.ID_MAGIC]
        if not replies:
            return None, None, None
        (did, cfgw), _ = Counter(replies).most_common(1)[0]
        return did, cfgw & 0xFFFF, len(Counter(replies))
    except Exception as e:
        return None, None, 'not read: %s' % e


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--want', choices=('C', 'D'),
                    help='exit 0 only if the card is positively this revision')
    ap.add_argument('--no-bus', action='store_true', help='skip source H')
    ap.add_argument('--no-knock', action='store_true', help='skip source K')
    ap.add_argument('--port', default='/dev/serial0')
    args = ap.parse_args()

    found = {}
    revs = []
    if not args.no_bus:
        line, err = read_bus(args.port)
        rev, why = (None, err) if err else classify_h1s1(line)
        found['H'] = {'line': line, 'rev': rev, 'why': why}
        revs.append(rev)
    if not args.no_knock:
        did, cfg, extra = read_knock()
        if isinstance(extra, str):
            rev, why = None, extra
        else:
            rev, why = classify_knock(cfg)
            if extra and extra > 1:
                rev, why = None, why + ' -- but the reply was not stable: no evidence'
        found['K'] = {'design_id': None if did is None else '%08x' % did,
                      'cfg': None if cfg is None else '%04X' % cfg,
                      'rev': rev, 'why': why}
        revs.append(rev)
    found['U'] = {'rev': None, 'why': 'U7 chip ID not readable from this tool '
                  '(no MH1 GET_ID path, no SWD channel to U7)'}

    v = verdict(revs)
    for k in ('H', 'K', 'U'):
        if k in found:
            print('  %s  %s' % (k, found[k]['why']))
    print('CARD=%s' % v)
    print(json.dumps({'card': v, 'want': args.want, 'sources': found}))
    if v == 'CONFLICT':
        return 4
    if v == 'UNKNOWN':
        return 3
    if args.want and v != args.want:
        return 5
    return 0


if __name__ == '__main__':
    sys.exit(main())
