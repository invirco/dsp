#!/usr/bin/env python3
"""S113: build setup-state.csv, run-order.csv and the group/order-annotated
catalog from the s110 catalog plus the state table read out of the runner."""
import csv, os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    '..', '..', '..', '..'))
SRC  = os.path.join(ROOT, 'MW/D24/DSP/s110/test-catalog.csv')
OUT  = os.path.join(ROOT, 'MW/D24/DSP/s113')
R    = 'tools/pi/d24_selftest.py'

# ---------------------------------------------------------------------------
# The measured / derived cost model. Every number carries its provenance in
# test-order.md; the constants live here so the two CSVs and the report cannot
# disagree.
# ---------------------------------------------------------------------------
C_PY       = 1     # python3 start + argparse + Rig
C_APPSTOP  = 3     # app_stop(): systemctl stop + time.sleep(2) + an_en read
C_STAGE    = 5     # stage_setup(): cp pair, symlink loop, 5 scp, ls+md5sum
C_BOOT     = 9     # boot_pair(): 2 x (dsp4_boot + 2 x dsp4_config) + s89_signbit
C_LINK     = 2     # link_alive(): dsp4_diag on both chips
C_HANDBACK = 2     # handback() under --no-app-restart: SAFE chain + pinctrl

# per-test run cost, seconds
RUN = {
 'HD0-1': 2, 'HD0-2': 1, 'HD-PWR': 0, 'NW1': 1, 'NW2': 30, 'NW3': 246,
 'NW4': 25, 'AS-CM4': 1, 'USB-HUB': 1,
 'ML1': 3, 'ML2': 1, 'ML-M': 5, 'ML-P1': 5, 'ML-P2': 5, 'ML-B0': 0,
 'CC1': 1, 'CC2': 2, 'MC1': 1, 'MC2': 0, 'MC3': 1,
 'DR1': 7, 'DR2': 12, 'DY1-RDY1': 12, 'DY1-RDY2': 0,
 'DC1-CS1': 1, 'DC1-CS2': 1, 'DC1-CS6': 0, 'DC1-CS7': 0, 'DC1-CS8': 0,
 'DC2-CS1': 1, 'DC2-CS2': 2, 'DC2-CS6': 0, 'DC2-CS7': 0, 'DC2-CS8': 0,
 'AS-DSPA': 4, 'AS-DSPB': 3, 'AS-CPLD': 25, 'AS-ADC': 2, 'AS-DAC': 4,
 'AS-PWR': 0, 'AL1': 10,
}

# ---------------------------------------------------------------------------
# The state table, one entry per test id, read out of the runner.
# fields: pair, an_en, cs_m, codec, c595, app, image, fixture, press, meter,
#         handback, evidence
# ---------------------------------------------------------------------------
N = 'no'; Y = 'yes'
def S(pair, an_en, cs_m, codec, c595, app, image, fixture, press, meter,
      handback, ev):
    return dict(requires_pair_boot=pair, requires_an_en=an_en,
                requires_cs_m_driven=cs_m, requires_codec_init=codec,
                requires_595=c595, requires_app=app, requires_image=image,
                requires_fixture=fixture, requires_press=press,
                requires_meter=meter, handback=handback, evidence=ev)

APP_EITHER = 'either'
APP_TESTUI = 'd24-testui (matrix-app STOPPED)'
NOHB = 'nothing (the run never stops the app)'
HB   = 'session handback: 595 SAFE, CS_M op dh, AN_EN as found'

STATE = {
# --- A: read from the CM4, nothing stopped -------------------------------
'HD0-1':  S(N,N,N,N,'none',APP_EITHER,'n/a','none',N,N,NOHB,
            R+':319-340 (sysfs status/edid/modes + kmsprint only); main :2366 is '
            'outside the app_stop at :2377'),
'HD0-2':  S(N,N,N,N,'none',APP_EITHER,'n/a','none',N,N,NOHB,
            R+':342-379 harvests /tmp/d24_hdsoak.log; the sampler is started at '
            ':2350-2364 and WIPED at :2352 on every press that names HD0-2'),
'HD-PWR': S(N,N,N,N,'none',APP_EITHER,'n/a','none',N,N,NOHB,
            R+':383-389 -- inferred from r.results["HD0-1"], no read of its own'),
'NW1':    S(N,N,N,N,'none',APP_EITHER,'n/a','none',N,N,NOHB,
            R+':392-406 ethtool + /sys/class/net/eth0/carrier'),
'NW2':    S(N,N,N,N,'none',APP_EITHER,'n/a','none',N,N,NOHB,
            R+':414-458; needs r._nw2_before taken at :2371 BEFORE NW3, and '
            'sleeps 30 s for its own idle control (:439-442)'),
'NW3':    S(N,N,N,N,'none',APP_EITHER,'n/a','none',N,N,NOHB,
            R+':460-525; ping -c 200 -i 0.2 x --nw3-runs (default 3, :2300) x '
            '2 targets'),
'NW4':    S(N,N,N,N,'none',APP_EITHER,'n/a','none',N,N,NOHB,
            R+':527-591; iperf3 server on the unit, 2 x 10 s'),
'AS-CM4': S(N,N,N,N,'none',APP_EITHER,'n/a','none',N,N,NOHB,
            R+':593-623; accepts matrix-app OR d24-testui (:594-599)'),
'USB-HUB':S(N,N,N,N,'none',APP_EITHER,'n/a','none',N,N,NOHB,
            R+':625-633 lsusb -t'),
# --- B: the H1S1 matrix bus, mixer stopped, pair NOT needed ---------------
'ML1':    S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB,
            R+':647-659 -> _bus :638-645 -> d24_bus_probe.py --mode cell; '
            'tools/pi/d24_bus_probe.py:25 "matrix-app owns /dev/serial0"'),
'ML2':    S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB,
            R+':661-671; md5sum of H1S1.shex only -- no bus transaction'),
'ML-M':   S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB,
            R+':673-683 -> _bus --mode stest; leans on r.results["ML1"]'),
'ML-P1':  S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB,
            R+':702-703 -> _panel :685-700 -> _bus --mode stest'),
'ML-P2':  S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB,
            R+':706-707 -> _panel :685-700 -> _bus --mode stest'),
'ML-B0':  S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB,
            R+':710-714 -- static NO DATA, no read at all'),
'CC1':    S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB,
            R+':1006-1014 -> _codec_read :996-1004 -> codec4619.py --read 05 '
            'on the H1S1 bus'),
'CC2':    S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB,
            R+':1016-1044; writes and restores 05H, caches r._cc1_val from CC1'),
'MC1':    S(N,N,Y,N,'armed',APP_TESTUI,'n/a','none',N,N,HB,
            R+':958-965 -> _chain :953-956 -> /home/app/s55/s55_chain.py; CS_M '
            'is the latch and gates the U2 MISO read-back (:975-994, :1986-1998)'),
'MC2':    S(N,N,Y,N,'safe',APP_TESTUI,'n/a','none',N,N,HB,
            R+':967-973 -- writes SAFE_IMAGE (:101) and reads it back'),
'MC3':    S(N,N,Y,N,'safe',APP_TESTUI,'n/a','none',N,N,HB,
            R+':975-994 -- reads r._mc1_raw from MC1 and pinctrl get 27'),
# --- B: the DSP pair ------------------------------------------------------
'DR1':    S(Y,N,Y,N,'none',APP_TESTUI,'shipping','none',N,N,HB,
            R+':912-936 needs an ADVANCING heartbeat before the pulse, i.e. the '
            'pair already booted -- main :2399 boots it unconditionally'),
'DR2':    S(Y,N,Y,N,'none',APP_TESTUI,'shipping','none',N,N,HB,
            R+':938-951 -- calls boot_pair() itself (:940) and rxscan (:945)'),
'DY1-RDY1':S(Y,N,Y,N,'none',APP_TESTUI,'shipping','none',N,N,HB,
            R+':852-871 -> _rdy_cycle :824-850, which dips !RST_D and calls '
            'boot_pair() (:836); cached on the rig at :849'),
'DY1-RDY2':S(Y,N,Y,N,'none',APP_TESTUI,'shipping','none',N,N,HB,
            R+':852-871 -- reads the SAME cached _rdy_cycle (:825-827); one dip '
            'serves both chips (:800-805)'),
'DC1-CS1':S(Y,N,Y,N,'none',APP_TESTUI,'shipping','none',N,N,HB,
            R+':873-890 -> _deassert :727 + _diag :717-719'),
'DC1-CS2':S(Y,N,Y,N,'none',APP_TESTUI,'shipping','none',N,N,HB, R+':873-890'),
'DC1-CS6':S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB,
            R+':889 -> _dc_nodata :768-774 -- a dict lookup (:733-766), no read'),
'DC1-CS7':S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB, R+':889 -> _dc_nodata :768-774'),
'DC1-CS8':S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB, R+':889 -> _dc_nodata :768-774'),
'DC2-CS1':S(Y,N,Y,N,'none',APP_TESTUI,'shipping','none',N,N,HB,
            R+':892-910 -- dsp4_buildcfg.py + _diag; the S82 triple check at '
            ':908 is EVIDENCE ONLY, the verdict is CHIP_ID (:906)'),
'DC2-CS2':S(Y,N,Y,N,'none',APP_TESTUI,'shipping','none',N,N,HB, R+':892-910'),
'DC2-CS6':S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB, R+':894 -> t_dc1 -> _dc_nodata'),
'DC2-CS7':S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB, R+':894 -> t_dc1 -> _dc_nodata'),
'DC2-CS8':S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB, R+':894 -> t_dc1 -> _dc_nodata'),
# --- C: read from the DSPs ------------------------------------------------
'AS-DSPA':S(Y,N,Y,N,'none',APP_TESTUI,'shipping','none',N,N,HB,
            R+':1093-1094 -> _as_dsp :1072-1091 (diag, heartbeat, buildcfg, rxscan)'),
'AS-DSPB':S(Y,N,Y,N,'none',APP_TESTUI,'shipping','none',N,N,HB,
            R+':1097-1098 -> _as_dsp :1072-1091 (no rxscan for chip 2, :1081)'),
'AS-CPLD':S(Y,N,Y,N,'none',APP_TESTUI,'shipping','none',N,N,HB,
            R+':1101-1127 -- dsp4_logic_id.py + dsp4_blk30.py 1 10 and 2 10 '
            '(two 10 s overrun windows)'),
'AS-ADC': S(Y,Y,Y,N,'none',APP_TESTUI,'shipping','none',N,N,HB,
            R+':1162-1207 -- rxscan; AN_EN is read at :1176 and a STATIC lane '
            'with the rails DOWN is NO DATA, not FAIL (:1199-1205)'),
'AS-DAC': S(Y,N,Y,N,'none',APP_TESTUI,'test-node-pair','none',N,N,HB,
            R+':1209-1229 -- s89_slotcap.py; the criterion needs TEST_OSC '
            'running, which exists only under DSP4_TEST_NODES=1 (:1222-1229)'),
'AS-PWR': S(N,N,N,N,'none',APP_TESTUI,'n/a','none',N,N,HB,
            R+':1231-1240 -- static NO DATA plus one pinctrl get 26'),
'AL1':    S(Y,Y,Y,Y,'safe',APP_TESTUI,'test-node-pair','none',N,N,HB,
            R+':1615-1712 -> _al1_prereq :1450-1522: raises AN_EN (:1461-1463), '
            'codec_init (:1475), ensure_pair (:1478), TEST_NODES symbol check '
            '(:1482-1484), route write (:1494-1496); handback lowers the rails '
            '(:2129-2135)'),
}

# ---------------------------------------------------------------------------
# groups
# ---------------------------------------------------------------------------
GROUPS = [
 ('A1', 'CM4 reads -- the app stays up',
  'nothing stopped, no DSP link, AN_EN as found, app in either role',
  ['HD0-1','AS-CM4','USB-HUB','NW1','NW3','NW4','NW2','HD0-2','HD-PWR']),
 ('A2', 'Matrix bus exclusive -- mixer stopped, pair not needed',
  'matrix-app STOPPED + stage populated (app_stop :2377, stage_setup :2384)',
  ['ML1','ML2','ML-M','ML-P1','ML-P2','ML-B0','CC1','CC2','MC1','MC2','MC3']),
 ('A3', 'The DSP pair -- reset, boot and the chip selects',
  'A2 + the pair booted to BOOT_STAGE 7 (boot_pair :2399), CS_M op dh',
  ['DR1','DR2','DY1-RDY1','DY1-RDY2',
   'DC1-CS1','DC1-CS2','DC1-CS6','DC1-CS7','DC1-CS8',
   'DC2-CS1','DC2-CS2','DC2-CS6','DC2-CS7','DC2-CS8']),
 ('A4', 'The pair, read -- no new state',
  'A3 as it left it: the pair up and answering (no boot of its own)',
  ['AS-DSPA','AS-DSPB','AS-CPLD','AS-PWR']),
 ('A5', 'Rails up -- the analog lanes and the acoustic loop',
  'A4 + AN_EN op dh (:1461) + AK4619 initialised (codec_init :1475)',
  ['AS-ADC','AS-DAC','AL1']),
]

# manual groups: (id, name, shared_state, [row numbers])
def rng(a, b, skip=()):
    return [n for n in range(a, b + 1) if n not in skip]

MANUAL = [
 ('M1', 'Left switch panel -- a finger and an eye',
  'the operator at the left panel; no fixture', rng(43, 55) + [58]),
 ('M2', 'Right switch panel -- a finger and an eye',
  'the operator at the right panel; no fixture', rng(59, 94, skip=(56, 57))),
 ('M3', 'P1 pedal -- the pedal, its lead and the RJ45',
  'the P1 pedal plugged in', [98, 99, 100, 101, 129, 145]),
 ('M4', 'The H1 analog loopback harness -- XLR, mini-jack, phones',
  'the H1 self-cable loopback harness on the analog I/O (BLOCKED: the harness '
  'does not exist yet)', rng(1, 42) + [95, 96, 97, 146, 147, 148]),
 ('M5', 'Rear plugs -- USB, HDMI, mains',
  'a USB stick, an HDMI sink and the mains lead in hand', [130, 131, 132, 133, 134]),
 ('M6', 'Slot-1 / net card and its links -- BLOCKED, no card exists',
  'a slot-1 card fitted (none exists)', [135, 136, 137, 138, 149, 150, 152]),
 ('M7', 'A meter -- rails, continuity, headers',
  'a DMM and the lid off', [153, 163] + rng(164, 175) + [177] + rng(178, 184)
  + [186, 187]),
 ('M8', 'No bench time -- out of scope or no test declared',
  'none: these rows are not scheduled', rng(113, 124) + rng(154, 162)
  + [176, 185] + rng(188, 192)),
]

# estimated operator cost per manual class, STATED ASSUMPTIONS (see report)
MANUAL_RUN = {'panel switch': 10, 'panel LED': 10, 'panel encoder': 20,
              'panel control': 20, 'pedal switch': 10, 'pedal LED': 10,
              'control': 20, 'analog input': 60, 'analog output': 60,
              'analog input (codec path)': 60, 'analog input (mini-jack)': 60,
              'analog output (phones)': 60, 'USB-A': 30, 'HDMI': 20,
              'power': 30, 'digital audio': 60, 'board-to-board link': 30,
              'power link / header': 30, 'board header': 30,
              'debug / test header': 30, 'psu monitor': 0}
MANUAL_SETUP = {'M1': 60, 'M2': 60, 'M3': 120, 'M4': 300, 'M5': 60,
                'M6': 120, 'M7': 180, 'M8': 0}

# ---------------------------------------------------------------------------
rows = list(csv.DictReader(open(SRC)))
bynum = {int(r['num']): r for r in rows}
tests_of = {}
for r in rows:
    if r['tests']:
        tests_of[int(r['num'])] = [t.strip() for t in r['tests'].split(',')]

# which catalog rows each test covers
rows_of_test = {}
for n, ts in tests_of.items():
    for t in ts:
        rows_of_test.setdefault(t, []).append(n)

os.makedirs(OUT, exist_ok=True)

# ---- 1. setup-state.csv --------------------------------------------------
COLS = ['num', 'item', 'runner', 'requires_pair_boot', 'requires_an_en',
        'requires_cs_m_driven', 'requires_codec_init', 'requires_595',
        'requires_app', 'requires_image', 'requires_fixture',
        'requires_press', 'requires_meter', 'handback', 'est_setup_s',
        'est_run_s', 'evidence']

# est_setup_s: what a SINGLE press of that row pays before the test body runs,
# under the runner as it stands today (the BEFORE model).
def press_setup(num):
    r = bynum[num]
    sec = r['runner_section']
    ts = tests_of[num]
    s = C_PY
    if sec == 'A':
        return s
    s += C_APPSTOP + C_STAGE
    if sec == 'B':
        s += C_BOOT                     # main :2399, unconditional
    elif set(ts) == {'AL1'}:
        s += C_LINK                     # main :2418 ensure_pair
    else:
        s += C_BOOT                     # main :2421
    return s + C_HANDBACK

sstate = []
for num in sorted(tests_of):
    r = bynum[num]
    ts = tests_of[num]
    sts = [STATE[t] for t in ts]
    def any_(k, yes=Y):
        return yes if any(s[k] == yes for s in sts) else N
    c595 = 'none'
    for s in sts:
        if s['requires_595'] == 'armed':
            c595 = 'armed'
        elif s['requires_595'] == 'safe' and c595 == 'none':
            c595 = 'safe'
    img = 'shipping' if any(s['requires_image'] == 'shipping' for s in sts) else 'n/a'
    if any(s['requires_image'] == 'test-node-pair' for s in sts):
        img = 'test-node-pair'
    sstate.append({
        'num': num, 'item': r['item'],
        'runner': '%s --section %s --only %s' % (R, r['runner_section'], r['tests']),
        'requires_pair_boot': any_('requires_pair_boot'),
        'requires_an_en': any_('requires_an_en'),
        'requires_cs_m_driven': any_('requires_cs_m_driven'),
        'requires_codec_init': any_('requires_codec_init'),
        'requires_595': c595,
        'requires_app': (APP_TESTUI if r['runner_section'] in ('B', 'C')
                         else APP_EITHER),
        'requires_image': img,
        'requires_fixture': 'none',
        'requires_press': N, 'requires_meter': N,
        'handback': sts[0]['handback'],
        'est_setup_s': press_setup(num),
        'est_run_s': sum(RUN[t] for t in ts),
        'evidence': ' | '.join('%s: %s' % (t, STATE[t]['evidence']) for t in ts),
    })

with open(os.path.join(OUT, 'setup-state.csv'), 'w', newline='') as fh:
    w = csv.DictWriter(fh, COLS); w.writeheader()
    for row in sstate:
        w.writerow(row)

# ---- the no-runner list --------------------------------------------------
norunner = [r for r in rows if not r['tests']]
with open(os.path.join(OUT, 'setup-state-no-runner.csv'), 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['num', 'item', 'runner', 'automation', 'class',
                'requires_fixture', 'requires_press', 'requires_meter',
                'spec_section'])
    FIX = {}
    for gid, gname, gstate, nums in MANUAL:
        for n in nums:
            FIX[n] = (gid, gstate)
    for r in norunner:
        n = int(r['num'])
        a = r['automation']
        gid, gstate = FIX.get(n, ('?', '?'))
        w.writerow([n, r['item'], 'no runner', a, r['class'], gstate,
                    'yes' if '3' in a else 'no',
                    'yes' if '4' in a else 'no', r['spec_section']])

# ---- 2. run-order.csv ----------------------------------------------------
order_of, group_of = {}, {}
out = []
o = 0
placed = set()
for gid, gname, gstate, tests in GROUPS:
    seen = set()
    for t in tests:
        for num in sorted(rows_of_test.get(t, [])):
            if num in seen or num in placed:
                continue
            seen.add(num); placed.add(num); o += 1
            note = ''
            if t == 'HD0-1' and num == min(rows_of_test['HD0-1']):
                note = ('start the HD0-2 soak sampler here (:2350-2364) and harvest '
                        'it at the END of A1, once per session, not once per press')
            if t == 'NW2':
                note = ('NW2 needs its before-sample taken before NW3 (:2371) and '
                        'sleeps 30 s for its own idle control')
            if gid == 'A2' and t == 'ML1':
                note = ('TRANSITION into A2: app_stop (:2377) + stage_setup (:2384), '
                        'once for A2-A5. No boot_pair: nothing in A2 reads the pair')
            if gid == 'A3' and t == 'DR1':
                note = ('TRANSITION into A3: ONE boot_pair (:2399). DR1 needs an '
                        'advancing heartbeat; DR2 and DY1 re-boot as part of their '
                        'own measurement and leave the pair up')
            if gid == 'A4' and t == 'AS-DSPA':
                note = ('NO transition: A3 ends with the pair at BOOT_STAGE 7 '
                        '(_rdy_cycle :836, t_dr2 :940), which is exactly A4\'s state')
            if gid == 'A5' and t == 'AS-ADC':
                note = ('TRANSITION into A5: AN_EN op dh + 1 s settle (:1461-1463) '
                        'and codec_init (:1475). AS-ADC is moved OUT of the dark-rail '
                        'block so it can reach a verdict instead of NO DATA')
            if t == 'AL1':
                note = ('last: handback (:2433) lowers AN_EN, writes the 595 SAFE '
                        'image and re-drives CS_M -- the session leaves each state once')
            out.append({'group_id': gid, 'group_name': gname,
                        'shared_state': gstate, 'order': o, 'num': num,
                        'item': bynum[num]['item'], 'transition_note': note})

for gid, gname, gstate, nums in MANUAL:
    first = True
    for num in nums:
        if num not in bynum or num in placed:
            continue
        placed.add(num); o += 1
        note = ('FIXTURE CHANGE: %s' % gstate) if first else ''
        first = False
        out.append({'group_id': gid, 'group_name': gname,
                    'shared_state': gstate, 'order': o, 'num': num,
                    'item': bynum[num]['item'], 'transition_note': note})

missing = sorted(set(bynum) - placed)
if missing:
    sys.exit('UNPLACED ROWS: %s' % missing)

for x in out:
    order_of[x['num']] = x['order']; group_of[x['num']] = x['group_id']

with open(os.path.join(OUT, 'run-order.csv'), 'w', newline='') as fh:
    w = csv.DictWriter(fh, ['group_id', 'group_name', 'shared_state', 'order',
                            'num', 'item', 'transition_note'])
    w.writeheader()
    for x in out:
        w.writerow(x)

# ---- 3. test-catalog.csv, two appended columns ---------------------------
with open(SRC) as fh:
    rdr = csv.reader(fh)
    hdr = next(rdr)
    body = list(rdr)
with open(os.path.join(OUT, 'test-catalog.csv'), 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(hdr + ['group', 'order'])
    for line in body:
        n = int(line[0])
        w.writerow(line + [group_of[n], order_of[n]])

# ---- the arithmetic ------------------------------------------------------
before = []
for row in sstate:
    before.append((row['num'], row['est_setup_s'], row['est_run_s'],
                   row['est_setup_s'] + row['est_run_s']))
B_TOTAL = sum(x[3] for x in before)

# AFTER: one process, --section A,B,C, the group order above
after_parts = [
    ('python3 start', C_PY),
    ('A1 tests', sum(RUN[t] for t in GROUPS[0][3])),
    ('A1->A2 transition: app_stop + stage_setup', C_APPSTOP + C_STAGE),
    ('A2 tests', sum(RUN[t] for t in GROUPS[1][3])),
    ('A2->A3 transition: one boot_pair', C_BOOT),
    ('A3 tests', sum(RUN[t] for t in GROUPS[2][3])),
    ('A3->A4 transition: none', 0),
    ('A4 tests', sum(RUN[t] for t in GROUPS[3][3])),
    ('A4->A5 transition: AN_EN + codec_init (inside AL1/_al1_prereq)', 0),
    ('A5 tests', sum(RUN[t] for t in GROUPS[4][3])),
    ('handback', C_HANDBACK),
]
A_TOTAL = sum(v for _, v in after_parts)

print('rows placed: %d' % len(placed))
print('runner rows: %d   no-runner rows: %d' % (len(sstate), len(norunner)))
print()
print('BEFORE total: %d s  (%.1f min) over %d presses' % (B_TOTAL, B_TOTAL/60.0, len(before)))
print('AFTER  total: %d s  (%.1f min) in 1 press' % (A_TOTAL, A_TOTAL/60.0))
print('saving: %d s (%.1f min, %.0f%%)' % (B_TOTAL-A_TOTAL, (B_TOTAL-A_TOTAL)/60.0,
                                           100.0*(B_TOTAL-A_TOTAL)/B_TOTAL))
print()
print('--- BEFORE, per press ---')
for n, s, rr, tot in before:
    print('  row %-3d  setup %3d + run %3d = %4d s   %s' % (n, s, rr, tot, bynum[n]['tests']))
print()
print('--- AFTER, per block ---')
for k, v in after_parts:
    print('  %-58s %4d s' % (k, v))
print()
print('--- AFTER, per group subtotal ---')
for gid, gname, gstate, tests in GROUPS:
    print('  %s %-58s %4d s' % (gid, gname[:58], sum(RUN[t] for t in tests)))
print()
setup_before = sum(x[1] for x in before)
run_before = sum(x[2] for x in before)
print('BEFORE: setup %d s + run %d s' % (setup_before, run_before))
print('AFTER : setup %d s + run %d s' % (C_PY+C_APPSTOP+C_STAGE+C_BOOT+C_HANDBACK,
                                         sum(RUN[t] for g in GROUPS for t in g[3])))
# manual fixture changeovers
def fixture_of(n):
    for gid, gname, gstate, nums in MANUAL:
        if n in nums:
            return gid
    return 'AUTO'
seq_cat = [fixture_of(n) for n in sorted(bynum)]
seq_new = [fixture_of(x['num']) for x in out]
def changes(seq):
    c = 0; prev = None
    for s in seq:
        if s != prev:
            c += 1; prev = s
    return c
print()
print('fixture/station changeovers, catalog order: %d' % changes(seq_cat))
print('fixture/station changeovers, grouped order: %d' % changes(seq_new))
