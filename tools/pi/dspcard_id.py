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
  J  the BOARD_REV0 strap read off the COPPER by a JTAG SAMPLE/PRELOAD of
     U3.81 (S175; PW ruling S174 Q1 (a)), over the CPLD openocd path the
     flash tools already use (/home/app/cpld-jtag.cfg). Rev C leaves the pad
     open and the CPLD's weak pull-up reads 1; rev D ties it to GND and it
     reads 0. SAMPLE never drives a pin and does not leave user mode, so it
     works with any image, a blank CPLD, or the shipping image running, and
     disturbs none of them. Never EXTEST, never a reprogram. The answer is
     evidence only when the tap is the 5M1270Z (IDCODE), the boundary
     register measures exactly 636 cells (a marker shifted through it comes
     out 636 bits later), and the cell reads the same in every sample.
     The JTAG GPIOs are put back to the state they were found in.
  U  U7's ROM-bootloader chip ID (U575 0x482, G0B1 0x467): NOT AVAILABLE from
     this tool. MH1 has no GET_ID path -- its loader enters the bootloader and
     mass-erases in the same step -- and no SWD channel to U7 is established.

Verdict: C or D when at least one source names a revision and none names the
other; CONFLICT when two disagree (never flash); UNKNOWN when none names one.
J and K read the same net (K through the rev D image, J through the boundary
cell), so J != K is a CONFLICT that means the tool or the net is wrong. J on
its own is enough: it is the only source a virgin card (blank U7, blank or
rev C CPLD) answers, and a virgin rev D card must identify as D so that its
first CPLD and H1S1 flashes are allowed.

    python3 dspcard_id.py                    # both sources, human + JSON line
    python3 dspcard_id.py --want C           # exit 0 only if positively rev C
    python3 dspcard_id.py --no-bus           # knock + JTAG (matrix-app running)
    python3 dspcard_id.py --only-jtag        # the copper alone (dsp4_config auto)
    python3 dspcard_id.py --self-test        # the parsers and rules, no hardware

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

# Source J: facts out of the 5M1270ZT144 BSDL (Quartus `quartus_eda --bsdl
# 5M1270ZT144C4`, see shared/dsp4-logic/bsdl/README.md for the regeneration
# and its sha256). Only the five numbers below are used.
JTAG_CFG = '/home/app/cpld-jtag.cfg'
JTAG_TAP = 'cpld.tap'
JTAG_GPIOS = (7, 22, 23, 25)            # TCK, TDO, TDI, TMS (J17 only)
CPLD_IDCODE = 0x020A30DD                # IDCODE_REGISTER, version 0
IR_SAMPLE = 0x005                       # SAMPLE/PRELOAD (0000000101)
IR_BYPASS = 0x3FF
BOUNDARY_LENGTH = 636
U3_81_CELL = 522                        # BSC group 174: (BC_4, IO81, input)
J_MARKER = 0xC3A55A3C                   # shifted in first; out after 636
J_SAMPLES = 3


def j_fields():
    """openocd drscan field list: the marker, then all ones (the BSDL's safe
    value for every control cell) so the PRELOAD latch never holds an enable."""
    total = 32 + BOUNDARY_LENGTH
    fields = [(32, J_MARKER)]
    left = total - 32
    while left:
        w = min(32, left)
        fields.append((w, (1 << w) - 1))
        left -= w
    return fields


def openocd_script(samples=J_SAMPLES):
    """init (TAP reset + IDCODE), SAMPLE, the scans, BYPASS, shutdown.
    Nothing here can drive a pin: no EXTEST, no CLAMP, no svf."""
    scan = ' '.join('%d 0x%x' % f for f in j_fields())
    cmds = ['init', 'irscan %s 0x%03x' % (JTAG_TAP, IR_SAMPLE)]
    for n in range(samples):
        cmds.append('echo "J_SAMPLE%d [drscan %s %s]"' % (n, JTAG_TAP, scan))
    cmds += ['irscan %s 0x%03x' % (JTAG_TAP, IR_BYPASS), 'shutdown']
    return '; '.join(cmds)


def unpack_scan(tokens):
    """Hex field values (openocd prints one per field) -> the bit list in
    shift order: bit 0 is the first bit out of TDO, i.e. boundary cell 0."""
    widths = [w for w, _ in j_fields()]
    if len(tokens) != len(widths):
        return None
    bits = []
    for w, t in zip(widths, tokens):
        v = int(t, 16)
        bits.extend((v >> i) & 1 for i in range(w))
    return bits


def register_length(bits):
    """Where the marker came out = the boundary register's length, or None."""
    mark = [(J_MARKER >> i) & 1 for i in range(32)]
    for off in range(len(bits) - 31):
        if bits[off:off + 32] == mark:
            return off
    return None


def classify_jtag(out):
    """(revision or None, why, detail) for one openocd run's output."""
    if out is None:
        return None, 'no JTAG answer', {}
    m = re.search(r'tap/device found: (0x[0-9a-fA-F]+)', out)
    idc = int(m.group(1), 16) if m else None
    detail = {'idcode': None if idc is None else '0x%08x' % idc}
    if idc is None:
        return None, 'JTAG: no tap answered (cable, pins or openocd)', detail
    if idc & 0x0FFFFFFF != CPLD_IDCODE & 0x0FFFFFFF:
        return None, ('JTAG: tap IDCODE 0x%08x is not the 5M1270Z (0x%08x)'
                      % (idc, CPLD_IDCODE)), detail
    reads, lengths = [], []
    for n in range(J_SAMPLES):
        mm = re.search(r'J_SAMPLE%d ((?:[0-9a-fA-F]+ ?)+)' % n, out)
        bits = unpack_scan(mm.group(1).split()) if mm else None
        if bits is None:
            return None, 'JTAG: sample %d did not come back' % n, detail
        lengths.append(register_length(bits))
        reads.append(bits[U3_81_CELL])
    detail.update({'register_length': lengths, 'u3_81': reads})
    if any(L != BOUNDARY_LENGTH for L in lengths):
        return None, ('JTAG: boundary register measured %s cells, the BSDL '
                      'says %d -- the cell index cannot be trusted'
                      % (lengths, BOUNDARY_LENGTH)), detail
    if len(set(reads)) != 1:
        return None, 'JTAG: U3.81 read %s -- not stable: no evidence' % reads, detail
    rev = 'C' if reads[0] else 'D'
    return rev, ('JTAG SAMPLE: U3.81 (BOARD_REV0) reads %d x%d = %s = rev %s '
                 'copper' % (reads[0], J_SAMPLES,
                             'open, weak pull-up' if rev == 'C' else 'strapped to GND',
                             rev)), detail


PIN_LINE = re.compile(r'^\s*(\d+):\s*(\S+)\s+(.*?)\|\s*(hi|lo)\b')


def parse_pins(text):
    """`pinctrl get` lines -> {gpio: (func, pull or None, level)}."""
    pins = {}
    for line in text.splitlines():
        m = PIN_LINE.match(line)
        if not m:
            continue
        pull = next((t for t in m.group(3).split() if t in ('pu', 'pd', 'pn')), None)
        pins[int(m.group(1))] = (m.group(2), pull, m.group(4))
    return pins


def restore_args(gpio, state):
    """The pinctrl set argument list that puts one pin back as found."""
    func, pull, level = state
    args = [str(gpio), func]
    if func == 'op':
        args.append('dh' if level == 'hi' else 'dl')
    if pull:
        args.append(pull)
    return args


def pinctrl_get(gpios):
    r = subprocess.run(['pinctrl', 'get', ','.join(map(str, gpios))],
                       capture_output=True, text=True, timeout=10)
    return parse_pins(r.stdout)


def read_jtag(cfg):
    """(openocd output or None, error or None, pin report). Fail closed."""
    if not os.path.isfile(cfg):
        return None, 'not read: no openocd JTAG config at %s' % cfg, {}
    try:
        before = pinctrl_get(JTAG_GPIOS)
    except (OSError, subprocess.SubprocessError) as e:
        return None, 'not read: pinctrl unavailable (%s)' % e, {}
    if sorted(before) != sorted(JTAG_GPIOS):
        return None, 'not read: could not snapshot GPIOs %s' % (JTAG_GPIOS,), {}
    out, err = None, None
    try:
        r = subprocess.run(['sudo', '-n', 'openocd', '-f', cfg,
                            '-c', openocd_script()],
                           capture_output=True, text=True, timeout=60)
        out = r.stdout + r.stderr
    except (OSError, subprocess.SubprocessError) as e:
        err = 'not read: openocd failed (%s)' % e
    finally:
        # linuxgpiod leaves its lines claimed (S8-3): put back what was found.
        for g in JTAG_GPIOS:
            subprocess.run(['sudo', '-n', 'pinctrl', 'set'] + restore_args(g, before[g]),
                           capture_output=True, timeout=10)
    try:
        after = pinctrl_get(JTAG_GPIOS)
    except (OSError, subprocess.SubprocessError):
        after = {}
    pins = {'before': {g: ' '.join(v) for g, v in before.items()},
            'restored': after == before}
    if after != before:
        pins['after'] = {g: ' '.join(v) for g, v in after.items()}
    return out, err, pins


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
    ap.add_argument('--no-jtag', action='store_true', help='skip source J')
    ap.add_argument('--only-jtag', action='store_true',
                    help='source J alone: the copper, nothing that needs the '
                         'bus or the PCM path')
    ap.add_argument('--jtag-cfg', default=JTAG_CFG)
    ap.add_argument('--port', default='/dev/serial0')
    ap.add_argument('--self-test', action='store_true',
                    help='check the parsers and verdict rules; no hardware')
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.only_jtag:
        args.no_bus = args.no_knock = True
        args.no_jtag = False

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
    if not args.no_jtag:
        out, err, pins = read_jtag(args.jtag_cfg)
        rev, why, detail = (None, err, {}) if err else classify_jtag(out)
        if pins and not pins.get('restored'):
            why += ' -- WARNING: the JTAG GPIOs did not go back as found: %s' % pins
        found['J'] = dict(detail, rev=rev, why=why, pins=pins)
        revs.append(rev)
    found['U'] = {'rev': None, 'why': 'U7 chip ID not readable from this tool '
                  '(no MH1 GET_ID path, no SWD channel to U7)'}

    v = verdict(revs)
    for k in ('H', 'K', 'J', 'U'):
        if k in found:
            print('  %s  %s' % (k, found[k]['why']))
    if v == 'CONFLICT':
        print('  CONFLICT: %s' % ', '.join(
            '%s says rev %s' % (k, found[k]['rev']) for k in ('H', 'K', 'J')
            if k in found and found[k]['rev']))
    print('CARD=%s' % v)
    print(json.dumps({'card': v, 'want': args.want, 'sources': found}))
    if v == 'CONFLICT':
        return 4
    if v == 'UNKNOWN':
        return 3
    if args.want and v != args.want:
        return 5
    return 0


def self_test():
    """The parsers and the rules against synthetic openocd/pinctrl output."""
    def scan_out(cell81, length=BOUNDARY_LENGTH):
        cells = [1] * length
        cells[U3_81_CELL] = cell81
        stream = cells + [(J_MARKER >> i) & 1 for i in range(32)]
        stream += [1] * (32 + BOUNDARY_LENGTH - len(stream))
        stream = stream[:32 + BOUNDARY_LENGTH]
        toks, pos = [], 0
        for w, _ in j_fields():
            toks.append('%x' % sum(b << i for i, b in enumerate(stream[pos:pos + w])))
            pos += w
        return ' '.join(toks)

    def run(reads, idc=CPLD_IDCODE, length=BOUNDARY_LENGTH):
        out = 'Info : JTAG tap: cpld.tap tap/device found: 0x%08x (mfg: 0x06e)\n' % idc
        for n, r in enumerate(reads):
            out += 'J_SAMPLE%d %s\n' % (n, scan_out(r, length))
        return classify_jtag(out)[0]

    checks = [
        ('rev C copper reads 1', run([1, 1, 1]) == 'C'),
        ('rev D copper reads 0', run([0, 0, 0]) == 'D'),
        ('unstable read is no evidence', run([1, 0, 1]) is None),
        ('missing sample is no evidence', run([1, 1]) is None),
        ('wrong IDCODE is no evidence', run([0, 0, 0], idc=0x020A20DD) is None),
        ('wrong register length is no evidence', run([0, 0, 0], length=600) is None),
        ('no tap is no evidence', classify_jtag('Error: no device found')[0] is None),
        ('verdict D alone (virgin rev D)', verdict([None, None, 'D']) == 'D'),
        ('verdict J vs K conflict', verdict([None, 'C', 'D']) == 'CONFLICT'),
        ('verdict H vs J conflict', verdict(['C', None, 'D']) == 'CONFLICT'),
        ('verdict nothing', verdict([None, None, None]) == 'UNKNOWN'),
        ('verdict all agree', verdict(['C', 'C', 'C']) == 'C'),
        ('script has no EXTEST/CLAMP/svf',
         not re.search(r'0x00f|0x00a|svf|extest', openocd_script(), re.I)),
        ('script SAMPLEs then BYPASSes',
         'irscan cpld.tap 0x005' in openocd_script()
         and openocd_script().endswith('irscan cpld.tap 0x3ff; shutdown')),
    ]
    p = parse_pins('7: a0 pd | lo // GPIO7 = SPI0_CE1_N\n'
                   '22: ip pd | lo // GPIO22 = input\n'
                   '26: op -- pd | hi // GPIO26 = output\n'
                   '25: op dl pn | lo // GPIO25 = output\n')
    checks += [
        ('pinctrl a0 parsed', p.get(7) == ('a0', 'pd', 'lo')),
        ('restore a0', restore_args(7, p[7]) == ['7', 'a0', 'pd']),
        ('restore op high', restore_args(26, p[26]) == ['26', 'op', 'dh', 'pd']),
        ('restore op low', restore_args(25, p[25]) == ['25', 'op', 'dl', 'pn']),
    ]
    bad = [n for n, ok in checks if not ok]
    for n, ok in checks:
        print('  %s  %s' % ('ok  ' if ok else 'FAIL', n))
    print('self-test: %d/%d' % (len(checks) - len(bad), len(checks)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
