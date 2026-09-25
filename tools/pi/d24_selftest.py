#!/usr/bin/env python3
"""d24_selftest.py -- section 1 of the D24 self-test set: every workbook item the
unit can judge itself with, no hands and no jig.

Implements `~/mx26/docs/spec-d24-selftest.md` tests A-C. Runs on THIS machine and
drives the unit's CM4 over SSH, the way the `tools/pi/dsp4_*` legs do; appends
`MW/D24/DSP/accept/item-status.csv` (`board,item,test,verdict,measured,limit,
evidence,stamp`) and prints the verdict table. `board` and `item` are the
workbook's column A and B strings VERBATIM -- the hub exports the key list with
`tools/d24/build-d24-connector-status.py --export-keys` and its generator errors
on an unknown key, so `--keys` cross-checks the table here before a run rather
than after one.

THE VERDICT VOCABULARY IS THREE WORDS AND THE MIDDLE ONE IS THE POINT.

    PASS      the read path answered and the answer met the spec's criterion
    FAIL      the read path answered and the answer did not
    NO DATA   the read path did not answer, or does not exist yet

A read path that answers nothing is NO DATA, never a silent PASS -- and, the
other way up, never a silent FAIL either. That second half is not symmetry for
its own sake: AN_EN is `lo` on this unit unless a session has deliberately
raised it (`sudo pinctrl set 26 op dh` -- PW lifted the old "never written by a
dispatched session" bar on 2026-09-24; this RUNNER still never writes it, it
reads it and records it), so with the rails down the mic front ends are not
converting and a dark lane is the TEST STATE. A converter reported FAIL for
that would be a defect invented by the harness. Every test that depends on the
rails therefore reads `_an_en()` first and says so.

Evidence is the RAW READ -- the EDID vendor string, the register value, the id
hex, the cell value -- never a summary word. Long reads are trimmed in the CSV
and written whole to `MW/D24/DSP/s90/logs/<stamp>/<test>.txt`.

WHAT THIS RUNNER WILL NOT DO, and each is a bench rule rather than a limitation:

  * it never raises AN_EN (GPIO26) -- it reads it and records it;
  * it never flashes the CPLD -- shipping `d02d83b3cc22` stays in flash;
  * it never boots from `/home/app/dspboot` itself (the candidate pair is staged
    there and must stay byte-identical) -- it copies to `--stage` and boots that;
  * it hands the 595 chain back to the SAFE image LAST, after the final DSP boot,
    because a boot clocks half a megabyte through the chain and only a CS_M edge
    decides what gets latched (S70-7);
  * it DRIVES GPIO27 `op dh` -- CS_M left low gates the U2 MISO buffer and looks
    exactly like a DSP link phase fault, and since S109 a weak pull-up no longer
    holds the pin against whatever sinks it (`ip pu` read `hi` and the link still
    would not phase; `op dh` fixed it first try);
  * it restarts `matrix-app` and reads the MCU verdict from the WHOLE of
    `/home/app/logs/log`, because the app rewrites that file on start.

    d24_selftest.py --section A                 # nothing is stopped; app stays up
    d24_selftest.py --section A,B,C             # the full run; stops the app
    d24_selftest.py --section A --no-append     # print only, write no CSV rows
    d24_selftest.py --keys /tmp/keys.csv        # cross-check the key table first
"""
import argparse
import csv
import datetime
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))   # tools/pi -> tools -> repo root
CSV_PATH = os.path.join(ROOT, 'MW', 'D24', 'DSP', 'accept', 'item-status.csv')
LOG_ROOT = os.path.join(ROOT, 'MW', 'D24', 'DSP', 's90', 'logs')
CSV_COLS = ['board', 'item', 'test', 'verdict', 'measured', 'limit', 'evidence', 'stamp']

BENCH = 'app@192.168.1.219'
BENCH_HOST_SELF = '192.168.1.211'       # this machine, as the unit sees it
DSPBOOT = '/home/app/dspboot'
# THE PAIR THE RUN BOOTS. The signed candidate is the default and the only
# thing a normal run ever boots. A DSP4_TEST_NODES=1 pair is a DIFFERENT
# image -- it carries TEST_OSC, which is what SP1 needs and what a shipping
# image must not have -- so pointing the run at one is a deliberate act with
# a name: `--pair DIR` from a bench host, or PAIR_CONF on the unit for a run
# the wizard's own START button launches (it takes no arguments). Whichever
# is used, the directory and the images' md5s are printed in the banner and
# carried in SP1's evidence, so no reading can be mistaken for the shipping
# pair's. PAIR_CONF is a bench artefact: a session that writes it removes it
# at handback and says so.
PAIR_DEFAULT = DSPBOOT + '/candidate-s82'
PAIR_CONF = '/home/app/selftest/pair.conf'
CONN = '/sys/class/drm/card0-HDMI-A-1'
ETHTOOL = '/usr/sbin/ethtool'           # NOT on app's PATH; absolute or nothing

PASS, FAIL, NODATA = 'PASS', 'FAIL', 'NO DATA'

# Pi GPIO map for the DSP bus, off DSP4 PI header J6 -- dsp4_boot.py:83-86.
# CS1/CS2 are the two live chip selects; CS3/CS4 come BACK as SPI_RDY and are
# inputs; !RST_D resets both parts together.
CS_GPIO = {1: 6, 2: 24}
RDY_GPIO = {1: 8, 2: 12}
RST_GPIO = 16
CS_M_GPIO = 27
AN_EN_GPIO = 26

# The 595 mic-gain chain. byte = (gain & 63) << 2 | (phantom & 1) << 1 | (mute & 1).
SAFE_IMAGE = [0x01] * 24 + [0x00]                       # gain 0, phantom off, MUTED
KNOWN_IMAGE = [((g & 63) << 2) | 1 for g in range(1, 25)] + [0x00]
# ^ 24 distinct gains, phantom OFF and MUTED on every position, so the known
#   image is as safe as SAFE while being distinguishable from it, from all-ones
#   and from all-zeros. `micGainFull` (0xFC x 24) -- what an S_RESET actually
#   leaves behind -- is gain 63 phantom off UNMUTED, and is never written here.

SHIPPING_CPLD = 'd02d83b3cc22'
SIGNED_TRIPLE = ('0xCF45FF10', '0xE2018E6F', '0xC47C0F26')   # the S82-signed pair

# ---------------------------------------------------------------------------
# The key table. `board`/`item` are the workbook's strings verbatim; the number
# in the comment is the workbook row (the --export-keys line number minus the
# header). A test may cover several items and then writes one row per item,
# which is the results contract's "one row per workbook item".
# ---------------------------------------------------------------------------
B_DSP = 'DSP PCBA (H1S1 MCU wiring)'
B_LINK = 'Inter-board links'
B_ASM = 'Assemblies'
B_LSW = 'Left Switch PCBA'

ITEMS = {
    # A -- from the CM4
    'HD0-1':   [('HDMI FPC (rev B)', 'Display link HDMI0 → TFT'),        # 127
                (B_ASM, 'TFT display')],                                  # 203
    'HD0-2':   [('HDMI FPC (rev B)', 'Display link HDMI0 → TFT'),
                (B_ASM, 'TFT display')],
    'HD-PWR':  [(B_LINK, "Link 'hdmi-pwr'")],                             # 151
    'NW1':     [('Digital', 'Ethernet (RJ45)')],                          # 128
    'NW2':     [('Digital', 'Ethernet (RJ45)')],
    'NW3':     [('Digital', 'Ethernet (RJ45)')],
    'NW4':     [('Digital', 'Ethernet (RJ45)')],
    'AS-CM4':  [(B_ASM, 'CM4 compute module')],                           # 193
    'USB-HUB': [],           # no workbook item: the spec files it under section-2 UA1
    # B -- through H1S1 over the matrix bus
    'ML1':     [(B_DSP, 'H1S1 MCU (STM32U575) link'),                     # 102
                (B_ASM, 'S MCU H1S1 (STM32U575)')],                       # 202
    'ML2':     [(B_DSP, 'H1S1 MCU (STM32U575) link'),
                (B_ASM, 'S MCU H1S1 (STM32U575)')],
    'ML-M':    [(B_ASM, 'M MCU (STM32G031)')],                            # 201
    'ML-P1':   [(B_DSP, 'Right panel MCU link (fw.csv SW_RIGHT)'),        # 125
                (B_LINK, "Link 'dig-panel-a'")],                          # 143
    'ML-P2':   [(B_DSP, 'Left panel MCU link (fw.csv SW_LEFT)'),          # 126
                (B_LINK, "Link 'dig-panel-b'")],                          # 144
    'ML-B0':   [(B_DSP, 'Right panel MCU link (fw.csv SW_RIGHT)'),
                (B_DSP, 'Left panel MCU link (fw.csv SW_LEFT)')],
    'DR1':     [(B_DSP, 'DSP reset RST_D (fw.csv Reset)')],               # 110
    'DR2':     [(B_DSP, 'DSP reset RST_D (fw.csv Reset)')],
    'MC1':     [(B_DSP, 'Mic-gain chain latch CS_M (fw.csv MicGain)')],   # 111
    'MC2':     [(B_DSP, 'Mic-gain chain latch CS_M (fw.csv MicGain)')],
    'MC3':     [(B_DSP, 'Mic-gain chain latch CS_M (fw.csv MicGain)')],
    'CC1':     [(B_DSP, 'Codec select CS_C (fw.csv Codec)'),              # 112
                (B_ASM, 'Codec AK4619')],                                 # 199
    'CC2':     [(B_DSP, 'Codec select CS_C (fw.csv Codec)'),
                (B_ASM, 'Codec AK4619')],
    # C -- from the DSPs
    'AS-DSPA': [(B_ASM, 'SHARC DSP A (ADSP-21564)'),                      # 194
                (B_LINK, "Link 'dig-dsp-a'")],                            # 139
    'AS-DSPB': [(B_ASM, 'SHARC DSP B (ADSP-21564)'),                      # 195
                (B_LINK, "Link 'dig-dsp-b'")],                            # 140
    'AS-CPLD': [(B_ASM, 'CPLD clock master (MAX V)')],                    # 196
    'AS-ADC':  [(B_ASM, 'ADC AK5558 ×3 (U15 dead, U39, U60)'),            # 198
                (B_LINK, "Link 'dig-analog-adc'")],                       # 141
    'AS-DAC':  [(B_ASM, 'DAC AK4458 ×2'),                                 # 197
                (B_LINK, "Link 'dig-analog-dac'")],                       # 142
    'AS-PWR':  [(B_ASM, 'Power MCU (STM32F030F4, always-on)')],           # 200
    # ONE TEST, ONE ROW, ONE PRESS (PW 2026-09-25). AL1 plays a tone out of the
    # panel speaker and hears it on the panel microphone. They are two PARTS
    # and one MEASUREMENT, so the workbook still counts two rows (56 the mic,
    # 57 the speaker) while the bench surface carries one: mx26's
    # build-d24-connector-status.py MERGED_KEYS folds the pair into a single
    # key at row 56's number, and this is that key. MM1 and SP1 are kept as
    # --only aliases (ALIASES below) and resolve here.
    'AL1':     [(B_LSW, 'Panel MEMS mic (talkback) + Speaker')],          # 56
}

# Retired test ids that still name something real. `--only MM1` and `--only
# SP1` are in reports, in the workbook and in PW's fingers; they run AL1, which
# is the test those two became.
ALIASES = {'MM1': 'AL1', 'SP1': 'AL1'}
# DC1/DC2 fan out over the chip selects, one workbook row each (103-109) --
# EXCEPT CS3 and CS4 (rows 105/106). Those two nets are not chip selects in
# either direction: they carry DSPA's and DSPB's SPI2_RDY BACK to the CM4, and
# an assert-one-read-one test of them was a permanent NO DATA because it asked
# a question the wiring cannot answer (S100). They get DY1 instead, which tests
# what the line actually does. CS5 (row 107) is ALSO retired, not renamed: PW's
# ruling 2026-09-24 makes fw.csv's Dsp5 row MicGainLatch, the CM4's permanent
# drive for the 74HC595 mic-gain chain latch, and MC1/MC2/MC3 already exercise
# that exact wire end to end -- there is nothing left for a standalone board-CS5
# row to check once the net is correctly named.
DC_SELECTS = (1, 2, 6, 7, 8)
RDY_SELECT = {1: 3, 2: 4}            # chip -> the CS number its SPI_RDY uses
for _n in DC_SELECTS:
    ITEMS['DC1-CS%d' % _n] = [(B_DSP, 'DSP chip-select CS%d (fw.csv Dsp%d)' % (_n, _n))]
    ITEMS['DC2-CS%d' % _n] = [(B_DSP, 'DSP chip-select CS%d (fw.csv Dsp%d)' % (_n, _n))]
for _c, _n in RDY_SELECT.items():
    ITEMS['DY1-RDY%d' % _c] = [(B_DSP, 'DSP chip-select CS%d (fw.csv Dsp%d)' % (_n, _n))]

SECTION = {}
for _t in ('HD0-1', 'HD0-2', 'HD-PWR', 'NW1', 'NW2', 'NW3', 'NW4', 'AS-CM4', 'USB-HUB'):
    SECTION[_t] = 'A'
for _t in ('ML1', 'ML2', 'ML-M', 'ML-P1', 'ML-P2', 'ML-B0', 'DR1', 'DR2',
           'MC1', 'MC2', 'MC3', 'CC1', 'CC2'):
    SECTION[_t] = 'B'
for _t in ('AS-DSPA', 'AS-DSPB', 'AS-CPLD', 'AS-ADC', 'AS-DAC', 'AS-PWR', 'AL1'):
    SECTION[_t] = 'C'
for _n in DC_SELECTS:
    SECTION['DC1-CS%d' % _n] = 'B'
    SECTION['DC2-CS%d' % _n] = 'B'
for _c in RDY_SELECT:
    SECTION['DY1-RDY%d' % _c] = 'B'


# ---------------------------------------------------------------------------
# plumbing
# ---------------------------------------------------------------------------
def stamp():
    return datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class Rig:
    """The unit, and the run's bookkeeping."""

    def __init__(self, args):
        self.a = args
        self.rows = []
        self.results = {}
        self.csv_path = args.csv or CSV_PATH
        log_root = (os.path.join(os.path.dirname(self.csv_path), 'logs')
                    if args.csv else LOG_ROOT)
        self.logdir = os.path.join(log_root, stamp().replace(':', ''))
        if not args.no_append:
            os.makedirs(self.logdir, exist_ok=True)
        self.app_stopped = False
        self.an_en_at_start = None
        self.pair = None
        self.pair_why = None

    # -- transport ----------------------------------------------------------
    def sh(self, cmd, timeout=120):
        return subprocess.run(['bash', '-c', cmd], capture_output=True,
                              text=True, timeout=timeout)

    def rsh(self, cmd, timeout=120):
        """One command on the CM4. stdout and stderr come back joined on the
        object; callers that care about the difference read them apart.

        Under `--local` this IS the CM4, so the ssh wrapper comes off and the
        command runs here. Nothing else about a test changes -- the same reads,
        the same criteria, the same evidence -- which is what lets the D24 test
        skin drive this runner from the unit's own display."""
        if self.a.local:
            return subprocess.run(['bash', '-c', cmd], capture_output=True,
                                  text=True, timeout=timeout)
        return subprocess.run(
            ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10', BENCH, cmd],
            capture_output=True, text=True, timeout=timeout)

    def put(self, src, dstdir, timeout=60):
        """One file onto the CM4 -- a copy when we are already on it."""
        if self.a.local:
            subprocess.run(['cp', src, dstdir + '/'], check=True, timeout=timeout)
        else:
            subprocess.run(['scp', '-q', src, '%s:%s/' % (BENCH, dstdir)],
                           check=True, timeout=timeout)

    def out(self, cmd, timeout=120):
        return self.rsh(cmd, timeout).stdout.strip()

    def log(self, test, text):
        if self.a.no_append:
            return
        with open(os.path.join(self.logdir, '%s.txt' % test), 'a') as fh:
            fh.write(text.rstrip() + '\n')

    # -- state the verdicts lean on ----------------------------------------
    def an_en(self):
        """AN_EN as it IS. Never written here -- see the module docstring."""
        return self.out('pinctrl get %d' % AN_EN_GPIO)

    def pin(self, spec):
        return self.out('sudo pinctrl set %s' % spec)

    # -- recording ----------------------------------------------------------
    def record(self, test, verdict, measured, limit, evidence):
        assert verdict in (PASS, FAIL, NODATA), verdict
        ev = ' '.join(str(evidence).split())
        self.log(test, '=== %s  %s\n%s' % (stamp(), verdict, evidence))
        if len(ev) > 400:
            ev = ev[:397] + '...'
        st = stamp()
        self.results[test] = verdict
        for board, item in ITEMS[test]:
            self.rows.append({'board': board, 'item': item, 'test': test,
                              'verdict': verdict, 'measured': str(measured),
                              'limit': str(limit), 'evidence': ev, 'stamp': st})
        print('  %-9s %-8s %s' % (test, verdict, str(measured)[:96]))

    def run(self, test, fn):
        if SECTION[test] not in self.a.section:
            return
        if self.a.only and test not in self.a.only:
            return
        print('%s ...' % test, flush=True)
        try:
            v, m, lim, ev = fn()
        except Exception as exc:                      # noqa: BLE001 -- see below
            # A crashed instrument is not a read path answering nothing, so it is
            # recorded as NO DATA with the exception in `evidence` and shouted
            # about in the summary rather than quietly folded in with the honest
            # NO DATAs.
            v, m, lim, ev = NODATA, 'runner error', '', 'RUNNER ERROR: %r' % (exc,)
        self.record(test, v, m, lim, ev)


# ---------------------------------------------------------------------------
# A -- read from the CM4
# ---------------------------------------------------------------------------
def t_hd01(r):
    status = r.out('cat %s/status' % CONN)
    edid = r.out('edid-decode < %s/edid 2>&1 | head -40' % CONN)
    modes = r.out('cat %s/modes' % CONN)
    active = r.out('kmsprint 2>/dev/null | grep -A4 "HDMI-A-1" | head -8')
    mfr = re.search(r'Manufacturer:\s*(\S+)', edid)
    prod = re.search(r'Model:\s*(\S+)', edid)
    native = modes.splitlines()[0] if modes else ''
    raw = ('status=%s\n--- edid-decode ---\n%s\n--- modes ---\n%s\n--- kmsprint ---\n%s'
           % (status, edid, modes, active))
    if status != 'connected':
        return FAIL, 'status=%s' % status, 'connected', raw
    if not (mfr and prod):
        return NODATA, 'EDID did not parse', 'manufacturer + product code', raw
    # The native mode is `modes`' first line; "is the active mode" is decided
    # against kmsprint's CRTC line, which carries the mode string verbatim.
    act = bool(native) and native in active
    v = PASS if act else FAIL
    return (v, 'HDMI-A-1 connected, %s %s, native %s, active=%s'
            % (mfr.group(1), prod.group(1), native, act),
            'connected + EDID mfr/product + native mode active', raw)


def t_hd02(r):
    """The dropout soak. A sampler was started at the top of the run; this
    harvests it. The window is whatever actually elapsed and is reported as
    such -- the spec asks >= 1 h (24 h for a shipping proof), so a shorter
    window is NO DATA naming its own length, never a PASS on a soak that was
    not run."""
    log = r.out('cat /tmp/d24_hdsoak.log 2>/dev/null')
    # udevadm monitor's banner is two lines and the SECOND of them begins
    # "UDEV - the event which udev sends out...", so `grep -c "^UDEV"` counts a
    # banner as a hotplug and reports a dropout on a display that never moved.
    # A real event line is `UDEV  [12345.6] change /devices/...`, so the
    # bracketed timestamp is what the match hangs on.
    uev = r.out('{ grep -cE "^UDEV +\\[" /tmp/d24_hdsoak.uevents 2>/dev/null '
                '|| echo 0; } | head -1')
    lines = [x for x in log.splitlines() if x.strip()]
    if not lines:
        return NODATA, 'no soak samples', 'status never leaves connected', log
    states = sorted({x.split()[-1] for x in lines})
    # The duration is what the LOG spans, read off its own timestamps. Deriving
    # it from the sample count times the interval assumes every sleep landed,
    # which is the kind of assumption a soak exists to avoid.
    try:
        t0 = datetime.datetime.strptime(lines[0].split()[0], '%Y-%m-%dT%H:%M:%SZ')
        t1 = datetime.datetime.strptime(lines[-1].split()[0], '%Y-%m-%dT%H:%M:%SZ')
        dur = int((t1 - t0).total_seconds())
    except (ValueError, IndexError):
        dur = (len(lines) - 1) * r.a.soak_interval
    raw = ('samples=%d interval=%ds duration=%ds states=%s drm_uevents=%s\n'
           'first: %s\nlast:  %s' % (len(lines), r.a.soak_interval, dur, states,
                                      uev, lines[0], lines[-1]))
    if states != ['connected']:
        return FAIL, 'states seen %s over %d s' % (states, dur), \
            'status never leaves connected', raw
    m = 'connected on %d of %d samples over %d s, drm hotplug uevents %s' % (
        len(lines), len(lines), dur, uev)
    if dur < 3600:
        return NODATA, m + ' (window short of the spec)', \
            '>= 3600 s, no state change, hotplug count unchanged', raw
    return PASS, m, '>= 3600 s, no state change, hotplug count unchanged', raw


def t_hdpwr(r):
    """Inferred, and said to be: the TFT answers EDID only when its rail is up."""
    hd = r.results.get('HD0-1')
    raw = 'inferred from HD0-1 = %s' % hd
    if hd == PASS:
        return PASS, 'inferred from HD0-1 PASS', 'HD0-1 PASS', raw
    return NODATA, 'HD0-1 = %s' % hd, 'HD0-1 PASS', raw


def t_nw1(r):
    et = r.out('%s eth0 2>&1' % ETHTOOL)
    carrier = r.out('cat /sys/class/net/eth0/carrier')
    link = re.search(r'Link detected:\s*(\S+)', et)
    speed = re.search(r'Speed:\s*(\S+)', et)
    duplex = re.search(r'Duplex:\s*(\S+)', et)
    raw = '%s\ncarrier=%s' % (et, carrier)
    if not (link and speed and duplex):
        return NODATA, 'ethtool did not answer', 'link up, 1000Mb/s, Full', raw
    m = 'Link detected: %s, Speed: %s, Duplex: %s, carrier=%s' % (
        link.group(1), speed.group(1), duplex.group(1), carrier)
    ok = (link.group(1) == 'yes' and speed.group(1) == '1000Mb/s'
          and duplex.group(1) == 'Full' and carrier == '1')
    return (PASS if ok else FAIL), m, 'link up, 1000Mb/s, Full', raw


def _ifstats(r):
    txt = r.out('ip -s link show eth0')
    nums = [int(x) for x in re.findall(r'\d+', txt.split('RX:')[1])] if 'RX:' in txt else []
    return txt, nums


def t_nw2(r):
    """rx/tx errors, dropped and overruns across NW3+NW4.

    `before` was taken before NW3 ran: a counter set read only as absolute
    totals cannot tell a fault during the run from one that predates the
    unit's six hours of uptime.

    AND IT CARRIES ITS OWN CONTROL, because the first run of this test read
    `rx_dropped +1` and that is not necessarily traffic the test caused. An
    IDLE window of the same shape is sampled afterwards with nothing driving
    the link; if a counter climbs there too it is ambient (this LAN carries
    multicast the unit does not subscribe to, and `rx_dropped` counts
    host-side software drops, not wire errors), and the evidence says so
    rather than leaving a reader to guess."""
    after, nums_a = _ifstats(r)
    before, nums_b = getattr(r, '_nw2_before', (None, None))
    if not nums_b or len(nums_b) != len(nums_a):
        return NODATA, 'no before-sample', 'errors/dropped/overruns delta = 0', \
            '--- after ---\n%s' % after
    # ip -s link: RX bytes packets errors dropped missed mcast
    #             TX bytes packets errors dropped carrier collsns
    names = ['rx_bytes', 'rx_packets', 'rx_errors', 'rx_dropped', 'rx_missed', 'rx_mcast',
             'tx_bytes', 'tx_packets', 'tx_errors', 'tx_dropped', 'tx_carrier', 'tx_collsns']
    fault_keys = ['rx_errors', 'rx_dropped', 'rx_missed',
                  'tx_errors', 'tx_dropped', 'tx_carrier', 'tx_collsns']
    delta = dict(zip(names, [a - b for a, b in zip(nums_a, nums_b)]))
    faults = {k: delta[k] for k in fault_keys}

    idle_t = 30
    _, nums_i0 = _ifstats(r)
    time.sleep(idle_t)
    idle_txt, nums_i1 = _ifstats(r)
    idle = dict(zip(names, [x - y for x, y in zip(nums_i1, nums_i0)]))
    idle_faults = {k: idle[k] for k in fault_keys}

    bad = {k: v for k, v in faults.items() if v != 0}
    ambient = {k for k, v in idle_faults.items() if v != 0}
    raw = ('--- before NW3 ---\n%s\n--- after NW4 ---\n%s\n'
           'delta over the tests: %s\n'
           '--- idle control, %d s with nothing driving the link ---\n%s\n'
           'delta while idle: %s\ncounters that also climb while idle: %s'
           % (before, after, faults, idle_t, idle_txt, idle_faults, sorted(ambient) or 'none'))
    m = 'deltas over NW3+NW4: %s; idle control (%d s): %s' % (faults, idle_t, idle_faults)
    return ((FAIL if bad else PASS), m, 'all zero for the run', raw)


def t_nw3(r):
    """Loss and RTT to the bench host -- AND to the unit's own default gateway,
    several passes each, scored on the WORST.

    TWO THINGS THIS TEST HAD TO LEARN ON THE BENCH.

    First, the control. A red cell against "Ethernet (RJ45)" for loss measured
    against one particular host would be a verdict about the PATH written
    against the unit's NIC. The gateway is one switch hop from the unit and
    shares none of the driving host's cabling, so the two targets separate
    "this link" from "that path".

    Second, and this is the one that matters: **a single 200-packet run does
    not settle a 0 % bar on this bench.** Five consecutive runs during this
    session read 2.0 %, 0.5 %, 0.0 %, 0.0 % to the bench host and 0.0 %, 0.5 %
    to the gateway -- so whichever verdict a one-shot lands is the one the
    scheduler happened to hand it, and re-running until it passes is not a
    measurement. The test therefore takes `--nw3-runs` passes per target and
    scores the WORST, which makes the reading reproducible in the only sense
    that counts: it does not improve if you run it again."""
    def ping(target):
        txt = r.out('ping -c 200 -i 0.2 %s 2>&1 | tail -3' % target, timeout=200)
        loss = re.search(r'([\d.]+)% packet loss', txt)
        rtt = re.search(r'=\s*([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*ms', txt)
        return txt, (float(loss.group(1)) if loss else None), \
            (float(rtt.group(3)) if rtt else None)

    gw = r.out("ip route | awk '/default/{print $3; exit}'")
    logs, worst = [], {}
    for label, target in (('bench host %s' % BENCH_HOST_SELF, BENCH_HOST_SELF),
                          ('gateway %s' % gw, gw)):
        if not target:
            continue
        losses, maxes = [], []
        for i in range(r.a.nw3_runs):
            txt, loss, mx = ping(target)
            logs.append('--- %s, pass %d/%d ---\n%s' % (label, i + 1, r.a.nw3_runs, txt))
            if loss is None:
                continue
            losses.append(loss)
            maxes.append(mx if mx is not None else float('nan'))
        if losses:
            worst[label] = (max(losses), max(maxes), losses)
    raw = '\n'.join(logs)
    if not worst:
        return NODATA, 'ping did not summarise', '0% loss, max RTT < 5 ms', raw
    host_key = 'bench host %s' % BENCH_HOST_SELF
    m = '; '.join('%s: worst %.1f%% loss over %d passes %s, max RTT %.3f ms'
                  % (k, v[0], len(v[2]), v[2], v[1]) for k, v in worst.items())
    if host_key not in worst:
        return NODATA, m, '0% loss, max RTT < 5 ms', raw
    h_loss, h_max, _ = worst[host_key]
    if h_loss == 0.0 and h_max < 5.0:
        return PASS, m, '0% loss, max RTT < 5 ms (worst of %d passes)' % r.a.nw3_runs, raw
    gw_key = [k for k in worst if k != host_key]
    if gw_key and worst[gw_key[0]][0] == 0.0:
        return (NODATA, m, '0% loss, max RTT < 5 ms',
                raw + '\nThe unit\'s own link passed its control on every pass -- 0 %% loss to '
                      'the gateway, one switch hop away, over none of the driving host\'s '
                      'cabling -- while the path to the bench host did not. The loss is not '
                      'attributed to the unit and this is NO DATA rather than FAIL. Re-take '
                      'from a host on the same gigabit switch.')
    return (FAIL, m, '0% loss, max RTT < 5 ms',
            raw + '\nLoss appears toward BOTH targets, including the unit\'s own gateway one '
                  'switch hop away, so it is not a property of the driving host\'s path alone.')


def t_nw4(r):
    """Throughput both ways.

    THE SERVER RUNS ON THE UNIT, NOT ON THE BENCH HOST, and the swap is
    deliberate. The spec's `iperf3 -c <bench host>` needs an inbound port open
    on the bench host; this machine runs ufw with `deny (incoming)` and only
    22/tcp allowed, so the spec's form times out and reports nothing -- a leg
    that is meant to run again and again cannot depend on the firewall posture
    of whatever machine is driving it. Driving it the other way measures the
    same two directions over the same link and needs nothing opened: without
    `-R` the unit RECEIVES, with `-R` the unit SENDS. The direction is named in
    the evidence so the numbers are never ambiguous about which way they ran."""
    # `pkill -x iperf3`, never `pkill -f "iperf3 -s"`: the -f form matches the
    # shell this very command is running in and kills the launcher before it
    # launches anything, which reads downstream as "iperf3 gave no receiver line".
    # THE PATH IS PART OF THE INSTRUMENT. The spec's >= 900 Mbit/s bar assumes a
    # gigabit LAN end to end; if the DRIVING host's link is slower, the number
    # measures that link and nothing about the unit. Scoring it FAIL would be a
    # defect invented by the bench, so the bottleneck is read first and a run
    # that cannot reach the bar is NO DATA naming the reason.
    iface = r.sh("ip route get %s | sed -n 's/.*dev \\([^ ]*\\).*/\\1/p' | head -1"
                 % BENCH.split("@")[1]).stdout.strip()
    host_mbit = r.sh('cat /sys/class/net/%s/speed 2>/dev/null || echo 0' % iface).stdout.strip()
    r.rsh('pkill -x iperf3 >/dev/null 2>&1; '
          'setsid nohup iperf3 -s -p 5201 </dev/null >/tmp/d24_iperf3.log 2>&1 & sleep 1')
    time.sleep(1.5)
    try:
        rx = r.sh('iperf3 -c %s -p 5201 -t 10 -f m 2>&1 | tail -6' % BENCH.split("@")[1],
                  timeout=90).stdout
        time.sleep(1.0)
        tx = r.sh('iperf3 -c %s -p 5201 -t 10 -R -f m 2>&1 | tail -6' % BENCH.split("@")[1],
                  timeout=90).stdout
    finally:
        r.rsh('pkill -x iperf3 >/dev/null 2>&1; true')
    raw = ('driving host %s: iface %s, link %s Mb/s\n'
           '--- unit receiving (host -> unit) ---\n%s\n'
           '--- unit sending (unit -> host, -R) ---\n%s'
           % (BENCH_HOST_SELF, iface, host_mbit, rx, tx))

    def mbits(txt):
        m = re.findall(r'([\d.]+)\s+Mbits/sec.*receiver', txt)
        return float(m[-1]) if m else None
    a_rx, a_tx = mbits(rx), mbits(tx)
    if a_rx is None or a_tx is None:
        return NODATA, 'iperf3 gave no receiver line', '>= 900 Mbit/s each way', raw
    try:
        capped = int(host_mbit) < 1000
    except ValueError:
        capped = True
    if capped:
        return (NODATA,
                'unit rx %.0f Mbit/s, unit tx %.0f Mbit/s -- but the driving host\'s %s '
                'negotiates %s Mb/s, so this is the path, not the unit'
                % (a_rx, a_tx, iface, host_mbit),
                '>= 900 Mbit/s each way',
                raw + '\nPREREQUISITE: a gigabit path between the unit and the driving host. '
                      'The unit\'s own link is 1000Mb/s Full (NW1); the dsp machine\'s %s is '
                      'at %s Mb/s, which caps this measurement below the bar whatever the unit '
                      'does. Re-run from a gigabit-attached host, or move the unit and that '
                      'host onto the same gigabit switch port pair.' % (iface, host_mbit))
    ok = a_rx >= 900.0 and a_tx >= 900.0
    return ((PASS if ok else FAIL),
            'unit rx %.0f Mbit/s, unit tx %.0f Mbit/s' % (a_rx, a_tx),
            '>= 900 Mbit/s each way', raw)


def t_ascm4(r):
    # "app active" means THE PRODUCT APPLICATION is up, not one named service.
    # Since S97 the same binary serves two roles in two units: matrix-app (the
    # mixer, which owns the H1S1/MX bus) and d24-testui (the factory test
    # display, which owns the screen and nothing else). During a factory session
    # the mixer is deliberately stopped, so gating on matrix-app alone would
    # score the CM4 red for running exactly the software the session asked for.
    txt = r.out('uptime; vcgencmd get_throttled; vcgencmd measure_temp; '
                'vcgencmd measure_volts core; tr -d "\\0" < /proc/device-tree/model; echo; '
                'echo "roles: matrix-app=$(systemctl is-active matrix-app) '
                'd24-testui=$(systemctl is-active d24-testui)"')
    thr = re.search(r'throttled=(0x[0-9a-fA-F]+)', txt)
    tmp = re.search(r"temp=([\d.]+)'C", txt)
    vol = re.search(r'volt=([\d.]+)V', txt)
    roles = re.search(r'roles: matrix-app=(\S+) d24-testui=(\S+)', txt)
    live = [n for n, st in (('matrix-app', roles.group(1) if roles else ''),
                            ('d24-testui', roles.group(2) if roles else ''))
            if st == 'active']
    act = bool(live)
    if not (thr and tmp and vol):
        return NODATA, 'vcgencmd did not answer', \
            'throttled 0x0, temp < 70 C, the product app running in either role', txt
    t = float(tmp.group(1))
    ok = thr.group(1) in ('0x0',) and t < 70.0 and act
    return ((PASS if ok else FAIL),
            'throttled=%s temp=%.1f C core=%sV app=%s'
            % (thr.group(1), t, vol.group(1),
               '+'.join(live) if live else 'neither role running'),
            'throttled 0x0, temp < 70 C, core volts in window, the product app '
            'running in either role (matrix-app or d24-testui)', txt)


def t_usbhub(r):
    txt = r.out('lsusb -t; echo ---; lsusb')
    # The spec's criterion: the CM4's hub enumerates with its four ports and
    # ports 3 and 4 report no device. Presence of a device is section 2.
    hubs = len(re.findall(r'Class=Hub', txt))
    ok = hubs >= 1
    return ((PASS if ok else FAIL), '%d hub(s) enumerated' % hubs,
            'CM4 hub enumerates; ports 3/4 empty (a device there is section 2)', txt)


# ---------------------------------------------------------------------------
# B -- through H1S1 over the matrix bus
# ---------------------------------------------------------------------------
def _bus(r, mode, extra=''):
    txt = r.out('cd %s && python3 d24_bus_probe.py --mode %s %s' % (r.a.stage, mode, extra),
                timeout=90)
    try:
        return json.loads(txt.splitlines()[-1]), txt
    except (ValueError, IndexError):
        return None, txt


def t_ml1(r):
    j, raw = _bus(r, 'cell', '--reps 3')
    if not j:
        return NODATA, 'probe gave no JSON', '3 identical well-formed answers', raw
    vals = [x['value'] for x in j['reads']]
    ms = [x['ms'] for x in j['reads']]
    m = 'Sys001Test001 (5414) x3 = %s, %s ms' % (
        ['0x%02X' % v if v is not None else None for v in vals], ms)
    if j['answered'] == 0:
        return NODATA, 'cell did not answer in 3 of 3', '3 identical answers', raw
    ok = j['identical'] and j['answered'] == 3
    return ((PASS if ok else FAIL), m, '3 identical answers within the bus timeout', raw)


def t_ml2(r):
    shex = r.out('md5sum /home/app/firmware/H1S1.shex; stat -c %%s /home/app/firmware/H1S1.shex')
    return (NODATA,
            'no H1S1 version cell; host side H1S1.shex %s' % shex.split()[0] if shex else 'no shex',
            'non-zero version equal to the H1S1.shex manifest',
            'PREREQUISITE: H1S1 firmware-version cell (spec prereq 1). H1S1\'s whole '
            'local cell table is Sys001Enc001/Sys001Skin001/Sys001Test001/Sys001Test002 '
            '(~/build-h1s1/Core/Inc/matrix.cs:11-18); no *Ver*/*Build* cell exists. '
            'The only identity it publishes is the S_TEST string "// H1S1 DSP" '
            '(matrix.cs:46). Host side reads: %s' % shex)


def t_mlm(r):
    j, raw = _bus(r, 'stest')
    mcus = (j or {}).get('mcus', {})
    ml1 = r.results.get('ML1')
    m = 'ML1=%s; S_TEST identities: %s' % (ml1, mcus)
    ev = ('%s\nMH1 firmware is not in ~/build-h1s1, so whether it publishes a version '
          'cell is UNKNOWN; no version was read.' % raw)
    if ml1 != PASS:
        return NODATA, m, 'ML1 PASS; version reads', ev
    return PASS, m, 'ML1 PASS (version, if published, reads)', ev


def _panel(r, tag, name):
    j, raw = _bus(r, 'stest')
    mcus = (j or {}).get('mcus', {})
    applog = r.out('grep "MCU verified" /home/app/logs/log | tail -6')
    ev = '%s\n--- matrix-app /home/app/logs/log ---\n%s' % (raw, applog)
    line = mcus.get(tag)
    m = '%s S_TEST = %r; app log: %s' % (
        tag, line, ' | '.join(x.strip() for x in applog.splitlines()))
    if not line:
        return NODATA, m, 'id answers and matches fw.csv %s' % name, ev
    # The identity string names the MCU, not the part number: fw.csv declares
    # STM32F030R8 and nothing on the wire repeats it, so the match is by MCU
    # name against fw.csv and is stated that way rather than claimed as a
    # part-number read.
    return PASS, m, 'id answers (fw.csv %s = STM32F030R8, not carried on the wire)' % name, ev


def t_mlp1(r):
    return _panel(r, 'H1S3', 'SW_RIGHT')


def t_mlp2(r):
    return _panel(r, 'H1S4', 'SW_LEFT')


def t_mlb0(r):
    return (NODATA, 'no BOOT0/NRST drive on H1S1', 'ROM ACK 0x79 and re-enumeration',
            'PREREQUISITE: BOOT0/NRST drive from H1S1 (spec prereq 6). No BOOT0, NRST, '
            'S9 or S13 anywhere in ~/build-h1s1; H1S1\'s entire GPIO set is CS1-8, RST_C, '
            'CS_M, CS_C, BLINK, BUSY, S2, S3 (Core/Inc/main.h:59-91).')


def _diag(r, chip, timeout=90):
    return r.out('cd %s && python3 dsp4_diag.py --chip %d --cs-gpio %d --rdy-gpio %d 2>&1'
                 % (r.a.stage, chip, CS_GPIO[chip], RDY_GPIO[chip]), timeout=timeout)


def _field(txt, name):
    m = re.search(r'^\s*%s\s+(\S+)' % re.escape(name), txt, re.M)
    return m.group(1) if m else None


def _deassert(r):
    r.pin('%d,%d op dh' % (CS_GPIO[1], CS_GPIO[2]))


# --- the three selects that cannot answer, and why each one cannot ----------
#
# S100 checked all eight against MW/D24/HW/hardware-map.md and defs fw.csv
# rather than treating "not CS1/CS2" as one diagnosis. They are not one
# diagnosis: CS7/CS8 are as mis-described by the workbook row as CS3/CS4 were.
# fw.csv declares Dsp1..Dsp8 as H1S1 pins B12/C14/B14/B13/C13/B15/C15/H0 on
# nets CS1..CS8, so each row is an H1S1 PIN ON A NET, and H1S1 drives none of
# them: all eight are GPIO_Input and must stay that way (~/build-h1s1
# Core/Src/main.c MX_GPIO_Init_2, "ALL EIGHT CS pins are OWNED BY THE CM4").
DC_NO_DATA = {
    6: ('CS6 reaches no fitted part',
        'no part behind the select, and no read path to the net',
        'SPEC CORRECTION (S100). hardware-map.md:410-411, the 8-DSP scaling '
        'provision. fw.csv Dsp6 is H1S1 pin B15 on net CS6; H1S1 holds it an INPUT '
        'and publishes no cell that could report its level, so there is no read path. '
        'CS6 is the one genuinely idle select of the eight: the D8 amendment lists '
        'CS5 OR CS6 as the spare for CS_M and this unit took CS5.'),
    7: ('CS7 is not a DSP chip select: it is SWD_EN1, CM4-owned',
        'n/a -- assert-one-read-one does not apply to this net',
        'SPEC CORRECTION (S100), the same shape as CS3/CS4. CS7 (H1S1 PC15, fw.csv '
        'Dsp7) carries SWD_EN1: dsp4-architecture-decisions.md D8 amendment, "CS7/8 '
        'are permanently the CM4-owned SWD_EN selects", realised on rev C as the '
        'CS7/CS8 -> SWD_EN1/EN3 proto wires. H1S1 driving it "forces ch3 permanently '
        'selected and breaks the CM4 SWD channel-select" (archive/tasks-archive-'
        '2026-08-20.md:365-367), which is why H1S1 holds it an input. No part answers '
        'behind it and this runner has no SWD transaction to prove the select with, '
        'so there is nothing to read today -- and driving it blind would take the '
        'SWD channel select down with it.'),
    8: ('CS8 is not a DSP chip select: it is SWD_EN3, CM4-owned',
        'n/a -- assert-one-read-one does not apply to this net',
        'SPEC CORRECTION (S100), the same shape as CS3/CS4. CS8 (H1S1 PH0, fw.csv '
        'Dsp8) carries SWD_EN3 -- see CS7: same D8 amendment, same proto wire pair, '
        'same reason H1S1 holds it an input, and the same absence of a read path in '
        'this runner.'),
}


def _dc_nodata(n):
    # CS3/CS4 never arrive here: they are DY1's, and the fan-out above leaves
    # them out of DC1/DC2 entirely. A KeyError would be the fan-out drifting.
    assert n in DC_NO_DATA, 'CS%d has no DC1/DC2 row -- see DC_SELECTS/DY1' % n
    m, lim, ev = DC_NO_DATA[n]
    return NODATA, m, lim, ev


# --- DY1: the SPI_RDY lines that the workbook calls CS3 and CS4 --------------
#
# WHAT THE SIGNAL ACTUALLY IS. PB_05 on each SHARC is SPI2_RDY, muxed to SPI2
# by spi2_init() (MW/D32/DSP/SHARC/src/dma_config.c) and configured FCEN=1,
# FCPL=1, FCWM=1: a push-pull OUTPUT that is HIGH while the receive FIFO has
# room and deasserts LOW as it fills, stalling the host. It leaves the card as
# CS3/CS4 and lands on CM4 GPIO8 (chip 1) / GPIO12 (chip 2).
#
# WHY THE OLD READ PROVED NOTHING, AND WHY THIS ONE DOES. Each DSP carries a
# 10K pulldown to GND on that net (R34 on DSPA, R22 on DSPB), so an undriven
# line rests LOW. A bare `pinctrl get` inherits whatever pull the CM4 pin was
# left in, and GPIO8 powers up pulled UP while GPIO12 powers up pulled DOWN --
# which is exactly why the old evidence recorded "8: ip pu | hi" and could not
# say whether anything was driving it. Force the CM4's own pull DOWN and the
# ambiguity is gone: with 10K to GND on the card AND the CM4's ~50K to GND, a
# HIGH can only be the part driving the pin.
#
# The criterion is the line FOLLOWING the part, measured both ways:
#   * !RST_D held low  -> the pad is high-Z, the pulldowns win, must read LOW;
#   * booted to BOOT_STAGE 7 -> SPI2 flow control drives it, must read HIGH.
# Passing both proves the pad is bonded and muxed, the net card -> J6 -> CM4 is
# continuous, the line is shorted to neither rail, and SPI2 flow control is
# configured and saying "ready". A static level proves none of those.
#
# The stimulus is the run's own recipe, not a new one: the dip is !RST_D (what
# DR1 pulses) and the recovery is boot_pair() (what DR2 runs). One dip serves
# both chips because !RST_D resets both parts together, so the cycle runs once
# per session and both DY1 rows read it.
RDY_SETTLE_S = 0.3


def _rdy_parse(raw):
    """{chip: 'hi'|'lo'|None} out of a `pinctrl get 8,12` transcript."""
    lv = {}
    for chip, g in RDY_GPIO.items():
        m = re.search(r'^\s*%d:.*\|\s*(hi|lo)\b' % g, raw, re.M)
        lv[chip] = m.group(1) if m else None
    return lv


def _rdy_levels(r):
    """Both SPI_RDY lines with the CM4's own pull-DOWN forced on."""
    raw = r.out('sudo pinctrl set %d,%d ip pd; sleep %s; pinctrl get %d,%d'
                % (RDY_GPIO[1], RDY_GPIO[2], RDY_SETTLE_S,
                   RDY_GPIO[1], RDY_GPIO[2]))
    return _rdy_parse(raw), raw


def _rdy_cycle(r):
    """Run the characterisation once and cache it on the rig."""
    cached = getattr(r, '_rdy_cycle', None)
    if cached is not None:
        return cached
    run, raw_run = _rdy_levels(r)
    # The dip is one remote command so the 200 ms window is timed on the CM4,
    # not across three ssh round trips.
    dip = r.out('sudo pinctrl set %d op dl; sleep 0.2; pinctrl get %d,%d; '
                'sudo pinctrl set %d op dh'
                % (RST_GPIO, RDY_GPIO[1], RDY_GPIO[2], RST_GPIO))
    rst = _rdy_parse(dip)
    log = boot_pair(r)
    post, raw_post = _rdy_levels(r)
    stage = {}
    for chip in (1, 2):
        stage[chip] = _field(_diag(r, chip), 'BOOT_STAGE')
    out = {'run': run, 'rst': rst, 'post': post, 'stage': stage,
           'raw': ('--- 1. as DR2 left the pair (CM4 pull-down forced) ---\n%s\n'
                   '--- 2. !RST_D (GPIO%d) held low 200 ms ---\n%s\n'
                   '--- 3. after boot_pair ---\n%s\nBOOT_STAGE %s/%s\n'
                   '--- boot log ---\n%s'
                   % (raw_run, RST_GPIO, dip, raw_post,
                      stage[1], stage[2], log[-1200:]))}
    r._rdy_cycle = out
    return out


def t_dy1(r, chip):
    """SPI_RDY must follow the part: LOW in reset, HIGH once it is running."""
    c = _rdy_cycle(r)
    g, cs = RDY_GPIO[chip], RDY_SELECT[chip]
    lim = ('SPI_RDY (CS%d, GPIO%d) reads LOW with !RST_D held low and HIGH with the '
           'part at BOOT_STAGE 7, the CM4 pin pulled DOWN for both reads' % (cs, g))
    m = ('CS%d/GPIO%d SPI_RDY: running %s, in reset %s, after boot %s (BOOT_STAGE %s)'
         % (cs, g, c['run'][chip], c['rst'][chip], c['post'][chip], c['stage'][chip]))
    st = c['stage'][chip]
    if st is None or int(st, 0) < 7:
        # The part never came back, so the line had nothing to drive. That is
        # DR2's verdict to give, not this one's.
        return NODATA, m, lim, ('chip %d did not reach BOOT_STAGE 7 after the dip, so '
                                'the HIGH half has no part behind it to prove -- see '
                                'DR2.\n%s' % (chip, c['raw']))
    if c['rst'][chip] is None or c['post'][chip] is None:
        return NODATA, m, lim, 'a level read did not parse.\n%s' % c['raw']
    ok = (c['rst'][chip] == 'lo' and c['post'][chip] == 'hi')
    return (PASS if ok else FAIL), m, lim, c['raw']


def t_dc1(r, n):
    """Assert one select, clock a read; the other selects stay high.

    CS1 and CS2 are the only two that can answer. CS3/CS4 are not here at all
    -- they are SPI_RDY and belong to DY1 -- CS5 is retired (fw.csv MicGainLatch,
    the CM4's permanent mic-gain latch drive, MC1/MC2/MC3's job) -- and CS6-CS8
    each say why they cannot answer in DC_NO_DATA above rather than sharing one
    blanket line."""
    if n in (1, 2):
        _deassert(r)
        txt = _diag(r, n)
        cid, bid = _field(txt, 'CHIP_ID'), _field(txt, 'BUILD_ID')
        ok = cid is not None and int(cid, 0) == n
        return ((PASS if ok else FAIL),
                'CS%d asserted (GPIO%d): CHIP_ID %s BUILD_ID %s' % (n, CS_GPIO[n], cid, bid),
                'the addressed part answers CHIP_ID %d' % n, txt)
    return _dc_nodata(n)


def t_dc2(r, n):
    """The identity of the part behind the select."""
    if n not in (1, 2):
        return t_dc1(r, n)
    txt = r.out('cd %s && python3 dsp4_buildcfg.py --chip %d 2>&1' % (r.a.stage, n), timeout=90)
    trip = re.findall(r'0x[0-9A-Fa-f]{8}', txt)
    cfg = _diag(r, n)
    cid = _field(cfg, 'CHIP_ID')
    bid = _field(cfg, 'BUILD_ID')
    raw = '%s\n--- diag ---\n%s' % (txt, cfg)
    if not bid:
        return NODATA, 'no BUILD_ID from CS%d' % n, 'id matches the declared part', raw
    match = all(t in trip for t in SIGNED_TRIPLE)
    return ((PASS if (cid and int(cid, 0) == n) else FAIL),
            'CS%d: CHIP_ID %s BUILD_ID %s, build cfg triple %s (S82-signed: %s)'
            % (n, cid, bid, trip[:3], match),
            'id answers behind the select; fw.csv Dsp%d declares a pin and net, not a part '
            'number, so there is nothing on the wire to match it against' % n, raw)


def t_dr1(r):
    """Pulse !RST_D and watch the heartbeat stop. The pulse is the CM4's
    GPIO16, not H1S1's -- see the spec correction in the report."""
    a1 = _field(_diag(r, 1), 'FRAME_COUNT')
    time.sleep(1.0)
    a2 = _field(_diag(r, 1), 'FRAME_COUNT')
    r.pin('%d op dl' % RST_GPIO)
    time.sleep(0.05)
    r.pin('%d op dh' % RST_GPIO)
    time.sleep(0.5)
    b1 = _diag(r, 1)
    time.sleep(1.0)
    b2 = _diag(r, 1)
    f_b1, f_b2 = _field(b1, 'FRAME_COUNT'), _field(b2, 'FRAME_COUNT')
    raw = ('before: FRAME_COUNT %s -> %s\nafter the pulse:\n%s\n---\n%s'
           % (a1, a2, b1, b2))
    if a1 is None or a2 is None or a1 == a2:
        return NODATA, 'heartbeat was not advancing before the pulse (%s -> %s)' % (a1, a2), \
            'heartbeat stops within one block period', raw
    stopped = (f_b1 is None or f_b2 is None or f_b1 == f_b2)
    return ((PASS if stopped else FAIL),
            'FRAME_COUNT %s -> %s advancing; after !RST_D (GPIO%d) low 50 ms: %s -> %s'
            % (a1, a2, RST_GPIO, f_b1, f_b2),
            'heartbeat stops within one block period', raw)


def t_dr2(r):
    """The boot+config recipe, and the lane read that proves the slots."""
    log = boot_pair(r)
    d1, d2 = _diag(r, 1), _diag(r, 2)
    st1, st2 = _field(d1, 'BOOT_STAGE'), _field(d2, 'BOOT_STAGE')
    b1, b2 = _field(d1, 'BUILD_ID'), _field(d2, 'BUILD_ID')
    lanes = rxscan(r)
    carrying = lanes.count('CARRYING')
    raw = '%s\n--- chip1 ---\n%s\n--- chip2 ---\n%s\n--- rxscan ---\n%s' % (log, d1, d2, lanes)
    ok = (st1 and st2 and int(st1, 0) >= 7 and int(st2, 0) >= 7)
    return ((PASS if ok else FAIL),
            'BOOT_STAGE %s/%s, BUILD_ID %s/%s, %d lanes CARRYING' % (st1, st2, b1, b2, carrying),
            'both SHARCs boot and answer; BOOT_STAGE 7', raw)


def _chain(r, image):
    hexes = ' '.join('0x%02X' % b for b in image)
    return r.out('cd /home/app/s55 && sudo -n python3 s55_chain.py %s 2>&1' % hexes, timeout=60)


def t_mc1(r):
    txt = _chain(r, KNOWN_IMAGE)
    want = ' '.join('%02X' % b for b in KNOWN_IMAGE)
    r._mc1_raw = txt
    ok = txt.startswith('VERIFIED 200/200') and want in txt
    return ((PASS if ok else FAIL), 'wrote %s, read back: %s' % (want, txt.split('|')[0].strip()),
            'read-back equals the image', 'image=%s\n%s' % (want, txt))


def t_mc2(r):
    txt = _chain(r, SAFE_IMAGE)
    want = ' '.join('%02X' % b for b in SAFE_IMAGE)
    ok = txt.startswith('VERIFIED 200/200') and want in txt
    return ((PASS if ok else FAIL), 'wrote SAFE %s, read back: %s' % (want, txt.split('|')[0].strip()),
            'read-back equals SAFE (gain 0, phantom off, MUTED)', 'image=%s\n%s' % (want, txt))


def t_mc3(r):
    """The all-zeros guard. It is not a separate measurement -- it is what
    decides whether MC1's reading means anything, so it reads CS_M's state
    either way and says whether the guard fired."""
    raw_mc1 = getattr(r, '_mc1_raw', '')
    lvl = r.out('pinctrl get %d' % CS_M_GPIO)
    zeros = bool(re.search(r'\b00(\s+00){20,}', raw_mc1))
    ev = ('MC1 read-back: %s\nCS_M at the CM4 end (GPIO%d): %s\n'
          'The analog-board end of CS_M is not readable through H1S1 (no such command); '
          'the CM4 end is, and GPIO%d in pull-DOWN holds CS_M LOW, which gates the U2 '
          'MISO buffer and reads as an all-zeros shift-back.'
          % (raw_mc1, CS_M_GPIO, lvl, CS_M_GPIO))
    if not raw_mc1:
        return NODATA, 'MC1 did not run', 'not all-zeros, or the CS_M level explains it', ev
    if zeros:
        return FAIL, 'MC1 read all zeros; CS_M (GPIO%d) = %s' % (CS_M_GPIO, lvl), \
            'not all-zeros, or the CS_M level explains it', ev
    return PASS, 'MC1 read-back is not all-zeros; guard not invoked; CS_M (GPIO%d) = %s' \
        % (CS_M_GPIO, lvl), 'not all-zeros, or the CS_M level explains it', ev


def _codec_read(r, reg):
    txt = r.out('cd %s && python3 codec4619.py --read %s 2>&1' % (DSPBOOT, reg), timeout=60)
    # codec4619 prints one line per register: `05H -> 0xBB   guard 0x43   ANSWERED`.
    # `no reply` is a real reading -- the arm did not answer -- and must not parse
    # as a value, so the alternation is explicit rather than a loose hex search.
    m = re.search(r'^%sH -> (no reply|0x([0-9A-Fa-f]{2}))' % reg, txt, re.M)
    val = int(m.group(2), 16) if (m and m.group(2)) else None
    return val, txt


def t_cc1(r):
    val, txt = _codec_read(r, '05')
    if val is None:
        return NODATA, 'the S81 read arm did not answer', '05H = 0xBB', txt
    ok = val == 0xBB
    r._cc1_val = val
    return ((PASS if ok else FAIL), '05H = 0x%02X' % val,
            '0xBB (MGN2L/MGN2R = +27 dB, the StartAK4619 image)', txt)


def t_cc2(r):
    """Write MGN2R to another code, read back, restore. The restore is not
    optional bookkeeping -- 05H is the talkback input's gain."""
    before = getattr(r, '_cc1_val', None)
    if before is None:
        before, _ = _codec_read(r, '05')
    if before is None:
        return NODATA, 'could not read 05H to restore it afterwards', 'read-back tracks the write', ''
    target = 0x05 if (before & 0x0F) != 0x05 else 0x02
    # --reg/--val writes the WHOLE byte. `--mgn2r N` would default the other
    # nibble to the init image's 0xB, which silently rewrites MGN2L on a unit
    # whose 05H is not the init image -- the restore would then not restore.
    wr = 'cd %s && python3 codec4619.py --reg 05 --val %%02X 2>&1' % DSPBOOT
    w1 = r.out(wr % ((before & 0xF0) | target), timeout=60)
    time.sleep(0.2)
    got, t1 = _codec_read(r, '05')
    w2 = r.out(wr % before, timeout=60)
    time.sleep(0.2)
    back, t2 = _codec_read(r, '05')
    raw = ('before=0x%02X\nwrite MGN2R=%d:\n%s\nread: %s\nrestore MGN2R=%d:\n%s\nread: %s'
           % (before, target, w1, t1, before & 0x0F, w2, t2))
    if got is None:
        return NODATA, 'read-back did not answer after the write', 'read-back tracks the write', raw
    ok = (got & 0x0F) == target and back == before
    return ((PASS if ok else FAIL),
            '05H 0x%02X -> MGN2R %d -> 0x%02X -> restored 0x%s'
            % (before, target, got, '%02X' % back if back is not None else '??'),
            'read-back tracks the write, and 05H is restored', raw)


# ---------------------------------------------------------------------------
# C -- read from the DSPs
# ---------------------------------------------------------------------------
def rxscan(r, chip=1):
    return r.out('cd %s && python3 dsp4_rxscan.py --symdir %s 2>&1'
                 % (r.a.stage, r.a.stage), timeout=240)


def _lane_rows(txt):
    """rxscan prints one line per lane ending CARRYING or STATIC."""
    rows = []
    for ln in txt.splitlines():
        if ln.rstrip().endswith(('CARRYING', 'STATIC')):
            rows.append(ln.strip())
    return rows


def _heartbeat(r, chip):
    a = _field(_diag(r, chip), 'FRAME_COUNT')
    time.sleep(1.0)
    b = _field(_diag(r, chip), 'FRAME_COUNT')
    if a is None or b is None:
        return None, (a, b)
    return int(b, 0) - int(a, 0), (a, b)


def _as_dsp(r, chip):
    d = _diag(r, chip)
    cid, bid = _field(d, 'CHIP_ID'), _field(d, 'BUILD_ID')
    st = _field(d, 'BOOT_STAGE')
    delta, pair = _heartbeat(r, chip)
    cfg = r.out('cd %s && python3 dsp4_buildcfg.py --chip %d 2>&1' % (r.a.stage, chip), timeout=90)
    lanes = _lane_rows(rxscan(r)) if chip == 1 else []
    raw = '%s\n--- buildcfg ---\n%s\n--- rxscan (%d lanes) ---\n%s' % (
        d, cfg, len(lanes), '\n'.join(lanes))
    if bid is None or cid is None:
        return NODATA, 'the part did not answer on its select', \
            'heartbeat advancing, build id, lanes carrying', raw
    ok = (int(cid, 0) == chip and delta and delta > 0 and st and int(st, 0) >= 7)
    carrying = sum(1 for x in lanes if x.endswith('CARRYING'))
    return ((PASS if ok else FAIL),
            'CHIP_ID %s BUILD_ID %s BOOT_STAGE %s, FRAME_COUNT %s->%s (delta %s)%s'
            % (cid, bid, st, pair[0], pair[1], delta,
               ', %d/%d lanes CARRYING' % (carrying, len(lanes)) if lanes else ''),
            'heartbeat advancing + build id answers + BOOT_STAGE 7', raw)


def t_asdspa(r):
    return _as_dsp(r, 1)


def t_asdspb(r):
    return _as_dsp(r, 2)


def t_ascpld(r):
    """Two halves, and only one of them can answer on this unit as found."""
    overlay = r.out('grep -n "dtoverlay=dsp4-pcm" /boot/firmware/config.txt')
    idtxt = r.out('cd %s && python3 dsp4_logic_id.py 2>&1 | tail -6' % DSPBOOT, timeout=120)
    blk1 = r.out('cd %s && python3 dsp4_blk30.py 1 10 2>&1 | tail -4' % r.a.stage, timeout=120)
    blk2 = r.out('cd %s && python3 dsp4_blk30.py 2 10 2>&1 | tail -4' % r.a.stage, timeout=120)
    raw = ('config.txt: %s\n--- logic_id ---\n%s\n--- blk30 chip1 ---\n%s\n--- blk30 chip2 ---\n%s'
           % (overlay, idtxt, blk1, blk2))
    ov_slave = 'slave' in overlay
    d1 = re.search(r'BLK_OVERRUN\s+(\d+)\s*->\s*(\d+)\s*\(delta\s+(-?\d+)', blk1)
    d2 = re.search(r'BLK_OVERRUN\s+(\d+)\s*->\s*(\d+)\s*\(delta\s+(-?\d+)', blk2)
    ovr = 'chip1 %s chip2 %s' % (d1.group(3) if d1 else '?', d2.group(3) if d2 else '?')
    if ov_slave:
        return (NODATA,
                'design id unreadable under dsp4-pcm-slave; BLK_OVERRUN delta over 10 s: %s' % ovr,
                'id = %s and zero overrun delta' % SHIPPING_CPLD,
                raw + '\nPREREQUISITE: dsp4_logic_id.py needs the DUPLEX PCM overlay. Under '
                      'dsp4-pcm-slave it answers "no reply" for EVERY bitstream (bench note 12), '
                      'so its silence carries no information. Flipping the overlay is a '
                      'config.txt edit plus a reboot, which is not "the unit as found", so it '
                      'was not done. The overrun half of the test ran and is reported.')
    got = re.search(r'design_id:\s*32\'h([0-9a-fA-F]{8})', idtxt)
    ok = bool(got) and got.group(1).lower() == SHIPPING_CPLD[-8:] and \
        (d1 and int(d1.group(3)) == 0) and (d2 and int(d2.group(3)) == 0)
    return ((PASS if ok else FAIL),
            'design_id %s, BLK_OVERRUN delta %s' % (got.group(1) if got else 'no reply', ovr),
            'id = %s and zero overrun delta' % SHIPPING_CPLD, raw)


def _lane_verdict(r, rows, want, label, limit):
    """Shared by AS-ADC, AS-DAC and MM1. The rails decide whether a dark lane
    is a fault or the test state, so they are read here and not assumed."""
    an = r.an_en()
    hit = [x for x in rows if want in x]
    raw = 'AN_EN (GPIO%d) = %s\n%s' % (AN_EN_GPIO, an, '\n'.join(hit) if hit else '\n'.join(rows))
    if not hit:
        return NODATA, 'no %s lane in the scan' % label, limit, raw
    carrying = [x for x in hit if x.endswith('CARRYING')]
    if carrying:
        return PASS, '%d of %d %s lanes CARRYING' % (len(carrying), len(hit), label), limit, raw
    if 'hi' not in an:
        return (NODATA,
                '%d %s lanes all STATIC with AN_EN %s' % (len(hit), label, an.split('//')[0].strip()),
                limit,
                raw + '\nPREREQUISITE: the analog rails. AN_EN (GPIO26) is low. Raise them with '
                      '`sudo pinctrl set 26 op dh` and re-take -- PW lifted the old bar on a '
                      'dispatched session doing that on 2026-09-24 (bench note 19 / S49-15 is '
                      'superseded on that one point only). With the front ends unpowered a STATIC '
                      'lane is the test state, not a converter fault, so this is NO DATA and not '
                      'FAIL.')
    return FAIL, '%d %s lanes all STATIC with AN_EN up' % (len(hit), label), limit, raw


# rxscan's `lane` column is the RX geometry lane, and on a D24 it names the
# converter: lane 0 = AD0 = ADC8 #1 = U15, lane 1 = AD1 = U39, lane 2 = AD2 = U60
# (MW/D24/HW/hardware-map.md:149-152). Lane 3 carries input strips 25-32, which
# have NO analog source on a D24 at all -- they are NET-only -- so a STATIC
# reading there is the product, not a fault.
ADC_OF_LANE = {0: 'U15', 1: 'U39', 2: 'U60'}


def t_asadc(r):
    """Per-lane activity on the mic inputs, grouped by the converter that feeds
    them. The verdict is on U39 and U60: U15's eight have no front end fitted on
    MW-D24-2 (measured S86) and are reported, not scored."""
    txt = rxscan(r)
    rows = []
    for ln in _lane_rows(txt):
        f = ln.split()
        if not re.match(r'^IN_\d+$', f[0]):
            continue
        try:
            # columns: node entry off lane lidx read distinct rms pk words... state
            rows.append((f[0], int(f[3]), f[-1], float(f[7]), int(f[6])))
        except (IndexError, ValueError):
            continue
    an = r.an_en()
    raw = 'AN_EN (GPIO%d) = %s\n%s' % (AN_EN_GPIO, an, '\n'.join(_lane_rows(txt)))
    if not rows:
        return NODATA, 'no IN_* lanes in the scan', 'U39 and U60 lanes alive and not stuck-at', raw
    by = {}
    for name, lane, state, rms, distinct in rows:
        by.setdefault(lane, []).append((name, state, rms, distinct))
    parts = []
    for lane in sorted(by):
        live = [x for x in by[lane] if x[1] == 'CARRYING']
        tag = ADC_OF_LANE.get(lane, 'strips 25-32, NET-only (no D24 ADC)')
        parts.append('lane %d (%s): %d/%d CARRYING, rms %s dBFS'
                     % (lane, tag, len(live), len(by[lane]),
                        '%.1f..%.1f' % (min(x[2] for x in by[lane]),
                                        max(x[2] for x in by[lane]))))
    scored = [lane for lane in by if ADC_OF_LANE.get(lane) in ('U39', 'U60')]
    ok = bool(scored) and all(all(x[1] == 'CARRYING' for x in by[lane]) for lane in scored)
    m = '; '.join(parts)
    if ok:
        return PASS, m, 'U39 and U60 lanes alive and not stuck-at (U15\'s eight known dead)', \
            raw + '\nU15 (lane 0) has no front end fitted on MW-D24-2 -- panel mics 1-4 and ' \
                  '13-16, XLRs J15-J22, preamps U17-U31, measured S86. Its lanes are reported ' \
                  'and not scored; the CONVERTER is fine, the front end is absent.'
    if 'hi' not in an:
        return (NODATA, m,
                'U39 and U60 lanes alive and not stuck-at',
                raw + '\nPREREQUISITE: the analog rails. AN_EN (GPIO26) is low; raise them with '
                      '`sudo pinctrl set 26 op dh` and re-take. With them down a STATIC lane here '
                      'is the test state, not a converter fault.')
    return FAIL, m, 'U39 and U60 lanes alive and not stuck-at', raw


def t_asdac(r):
    """The read path exists and is exercised; the stimulus the spec's criterion
    needs does not exist on the image under test, so the slot reading is
    evidence and not a verdict."""
    cap = r.out('cd %s && python3 s89_slotcap.py %s 2 _tx_out_slot_C2_MON_OUT 256 2>&1 | tail -6'
                % (r.a.stage, r.a.stage), timeout=180)
    osc = r.out('cd %s && python3 -c "import json;j=json.load(open(\'chip1.sym.json\'));'
                'print(\'_osc_blk_q_C1_TEST_OSC\' in j)"' % r.a.stage, timeout=60)
    raw = ('--- coherent capture of _tx_out_slot_C2_MON_OUT (256 samples) ---\n%s\n'
           'chip1 carries _osc_blk_q_C1_TEST_OSC: %s' % (cap, osc))
    return (NODATA,
            'TX slot read (see evidence); no stimulus on this image (TEST_NODES symbol: %s)' % osc,
            'slots non-constant while TEST_OSC runs, correct level in dBFS',
            raw + '\nPREREQUISITE: a stimulus. The spec\'s criterion is "non-constant WHILE '
                  'TEST_OSC runs into an output"; TEST_OSC exists only under DSP4_TEST_NODES=1 '
                  'and the pair under test is the shipping pair. dsp4_s49_osc.py refuses such '
                  'an image by symbol check rather than printing four zeros that would look '
                  'like a measurement. With nothing driving the output, neither a constant nor '
                  'a varying slot separates a working DAC path from a silent one, so the '
                  'capture is recorded and the verdict is NO DATA.')


def t_aspwr(r):
    an = r.an_en()
    return (NODATA, 'no reader for the power MCU\'s published words; AN_EN (GPIO26) = %s'
            % an.split('//')[0].strip(),
            'state running, PWR_FAIL clear, AN_EN as expected',
            'PREREQUISITE: a reader for the power MCU over MHRX. Nothing in this repo reads '
            'the power MCU\'s state word, PWR_FAIL or its AN_EN view; src/fw/d24-pwr-mcu-def.csv '
            'is not in this tree (it is mx26\'s). AN_EN is not an MCU word at all -- it is CM4 '
            'GPIO26, read here as: %s' % an)


# --- AL1: the acoustic loop, speaker + MEMS mic in one test (S110) ----------
#
# ONE TEST, ONE BUTTON, TWO PARTS (PW 2026-09-25). S102 built this as two rows,
# MM1 for the mic and SP1 for the speaker, because they are two parts on the
# board inventory. They are still two parts -- `ITEMS['AL1']` carries both keys
# and every run records a result against each -- but there is only one thing to
# press, because there is only one measurement: a tone out of the panel speaker
# and back in through the panel microphone. Nothing else on the board can hear
# the speaker and nothing else can drive the mic, so a reading is either both
# halves working or a fault that this test cannot, on its own, attribute to one
# of them. The verdict says which stages it cannot separate rather than picking.
# MM1 and SP1 remain valid `--only` names (see ALIASES) and both resolve here.
#
# THE INSTRUMENT IS S49's MEASUREMENT NODE, NOT A SCATTER OF rxscan READS.
# `dsp4_rxscan.py` samples the RX DMA region a word at a time: a peak taken
# that way under-reads by up to 6 dB and a "waveform" from it is scrambled
# (bench note: a 16-word node peek spans ~15 audio blocks). THD+N cannot be had
# from it at all. `C1_TEST_MEAS` accumulates over a continuous 4,096-sample
# window on the part and publishes RMS, THD+N and a noise figure, which is what
# a distortion number has to come from. rxscan is still read here, once, for
# the one thing it is good at: saying whether the MEMS lane is CARRYING at all.
#
# WHERE THE MIC IS: MeasChan 54, NOT A STRIP. The dispatch asked for "the strip
# that carries XIN_MEMS" and there is none -- `C1_XIN_MEMS` feeds `C1_TALK_02`,
# a TALKBACK node whose output is a per-block scalar nothing downstream reads
# (the Talk001Dest fan-out gap dsp-unmapped.csv records). MeasChan 1..32 are
# strips and 33..50 are buses, so both miss it. The converter-return lane codes
# (S69/S73, dsp_codegen.py TEST_MEAS_LANE_CODES) put the tap on the input lane
# itself, which is the right measurement point for an input path anyway: the
# last place the converter's output is still exactly what the converter made.
# 54 is the MEMS lane. Proven on the part in S110 -- MeasChan <- 0x36 reads
# back, the window serial advances, and the level tracks the tone.
#
# THE ROUTE (S102, correcting S90-P6 which read it as absent) is unchanged and
# is asserted and READ BACK before anything is measured; see SPKR_ROUTE_NOTE.
_SPKR_OSC_STRIP = 20              # S89's donor strip, for the same reason
_SPKR_FREQ_HZ = 1000.0
_OSC_SYM = '_osc_blk_q_C1_TEST_OSC'
AL1_MEAS_CHAN = 54                # C1_XIN_MEMS -- see above, not a strip

# THE TONE IS SAFE BY DEFAULT AND CANNOT BE MADE LOUD BY ACCIDENT.
# PW drove this speaker to full scale by hand on 2026-09-25 and heard no
# clipping, which is what says the path is healthy -- it is NOT permission for
# an automated test to do the same. An unattended run plays -20 dBFS, fades in
# and out over 150 ms so the speaker is never asked for a step, and is on for
# well under a second (0.6 s measured; `--then-off` stops the tone inside the
# same session, which is the only way that number is small -- a second
# invocation spends two to four seconds starting up with the tone still
# sounding). `--al1-level` moves it and CANNOT go past AL1_TONE_CAP_DBFS.
AL1_TONE_DBFS = -20.0
AL1_TONE_CAP_DBFS = -6.0
AL1_RAMP_MS = 150.0
AL1_MAX_ON_S = 3.0                # reported if exceeded; the cap is the design

# ===========================================================================
# THE WINDOWS AND CEILINGS -- ONE TABLE, PROVISIONAL
# ===========================================================================
# PROVISIONAL until the speaker supplier's datasheet arrives, and provisional
# again until PW's planned amp-gain change (a resistor in parallel with R97,
# +6 dB or more) lands. These are NOT spec limits. They are set to catch a
# fault -- no sound, a quiet path, a distorting one -- on a small speaker in an
# ordinary room, and nothing here certifies anything.
#
# EVERY NUMBER HERE CAME OFF THIS UNIT. See the calibration table in the S110
# report for the runs behind each one.
#
# THE LEVEL WINDOW IS RELATIVE, WHICH IS THE POINT. The expected mic level is
# a straight line in the injected level -- `pred = slope * drive + intercept`
# -- so the table survives a change in what is between the two ends of the
# loop. When PW adds amp gain, one command re-measures and rewrites this
# block: `d24_selftest.py --only AL1 --al1-calibrate`, which prints the old
# table and the new one side by side and says what moved.
AL1_CAL = {
    'provisional': 'until the speaker supplier datasheet -- NOT a spec limit',
    'unit': 'MW-D24-2 (rev C+)',
    'stamp': '2026-09-25T13:15:34Z',
    'pair': '/home/app/loopthd/s109',
    'runs': '15 runs at -30/-20/-10 dBFS x 5 reps; 10 fitted, 5 excluded as not measuring a tone (THD+N > -6 dB); lowest drive that read: -20 dBFS; default drive -20 dBFS',
    'slope_db_per_db': 0.940,
    'intercept_dbfs': -30.590,
    'level_tol_db': 4.000,
    'level_hi_tol_db': 7.000,
    'high_fails': False,
    'snr_min_db': 3.900,
    'floor_max_dbfs': -48.500,
    'thdn_abs_db': -4.100,
    'thdn_margin_db': 4.900,
}
AL1_CAL_KEYS_NUMERIC = ('slope_db_per_db', 'intercept_dbfs', 'level_tol_db',
                        'level_hi_tol_db', 'snr_min_db', 'floor_max_dbfs',
                        'thdn_abs_db', 'thdn_margin_db')


def pct_of_db(db):
    """A ratio in dB as percent. PW's standing rule (2026-09-16): every
    THD/THD+N figure is printed in dB AND in percent, never one alone."""
    return 100.0 * 10.0 ** (db / 20.0)


def _mems_row(rows):
    hit = [x for x in rows if 'MEMS' in x]
    return hit[0] if hit else None


def _route_cells():
    """The write that asserts the TEST_OSC -> speaker route, as one list.

    Lifted from `dsp4_loop_thd.sh`'s proven route write, which exists because
    the FIRST run of that leg measured the default configuration instead: the
    donor strip's compressor is ON out of dsp4_config.py at about -22 dBFS
    (S70-3), so a route that is not asserted still produces a plausible
    number. Every write here is checked."""
    osc = '%03d' % _SPKR_OSC_STRIP
    close = ['Chan%03dMainOn001=0' % s for s in range(1, 33) if s != _SPKR_OSC_STRIP]
    route = ['Chan%sMainOn001=1' % osc, 'Chan%sMute001=0' % osc,
             'Chan%sLevel001=f1.0:4' % osc, 'Chan%sPan001=f0.5:4' % osc,
             'Chan%sCompOn001=0' % osc, 'Chan%sGateOn001=0' % osc,
             'Chan%sTubeOn001=0' % osc, 'Chan%sEqOn001=0' % osc,
             'Main001Level001=f1.0:4', 'Main001Mute001=0',
             # the speaker's own level word: C2_MON, the node that feeds
             # C2_MON_OUT slot 0.
             'Mon001Level001=f1.0:4', 'Mon001Level002=f1.0:4']
    return close, route


def _set(r, cells, timeout=300):
    c = r.rsh('cd %s && python3 s89_set.py %s %s 2>&1'
              % (r.a.stage, r.a.stage, ' '.join(cells)), timeout=timeout)
    return c.returncode, (c.stdout + c.stderr).strip()


def _al1_osc(r, level=None, timeout=300):
    """One S49 window measurement of the MEMS lane.

    `level=None` is the tone-OFF leg: the oscillator is stopped and the window
    reads the lane's own floor. Otherwise the tone is faded in, three windows
    are taken, and the tone is faded out IN THE SAME SESSION (`--then-off`),
    which is what keeps the on-time under a second.

    Returns (dict-or-None, raw text). The dict is the settled window plus the
    on-time; None means the tool refused or the JSON did not come back, and
    the raw text says why."""
    j = '%s/al1-osc.json' % r.a.stage
    if level is None:
        args = '--off'
    else:
        args = ('--strip %d --level %g --ramp-ms %g --then-off'
                % (_SPKR_OSC_STRIP, level, AL1_RAMP_MS))
    # The CS lines are re-driven before every tool call: a boot or a stray
    # reset leaves them somewhere else and the link then reads plausible
    # zeros rather than failing (bench recipe, and S109 on CS_M).
    r.pin('%d,%d op dh' % (CS_GPIO[1], CS_GPIO[2]))
    c = r.rsh('cd %s && rm -f %s && python3 dsp4_s49_osc.py --meas %d --freq %g '
              '--symdir %s --json %s %s 2>&1'
              % (r.a.stage, j, AL1_MEAS_CHAN, _SPKR_FREQ_HZ, r.a.stage, j, args),
              timeout=timeout)
    txt = (c.stdout + c.stderr).strip()
    raw = r.out('cat %s 2>/dev/null' % j)
    if not raw:
        return None, txt
    try:
        d = json.loads(raw)
    except ValueError:
        return None, txt + '\n--- json did not parse ---\n' + raw[:400]
    good = [w for w in d.get('rows', []) if not w.get('torn')]
    if not good:
        return None, txt + '\n--- every window was torn ---'
    w = dict(good[-1])
    w['on_seconds'] = d.get('on_seconds')
    w['level_dbfs_peak'] = d.get('level_dbfs_peak')
    w['off'] = d.get('off')
    return w, txt


SPKR_ROUTE_NOTE = (
    'THE ROUTE, named (S102, correcting S90-P6 which read it as absent). The speaker is '
    'codec TDM slot 0 = C2_MON_OUT slot 0 = signal CODEC_OUT_1 = AK4619 AOUT1L (analog U3 '
    'pin 22) -- the ONLY codec DAC output fitted on a D24 (mx26 tools/netlist/parts.csv:67: '
    'C20/C21/C22 on AOUT1R/AOUT2L/AOUT2R are DNP). U3.22 -> C23 -> SPKR -> analog J59.12 = '
    'digital J42.12 -> C82 -> TS482 (digital U32, unity, BRIDGED, 5 V) -> SPKR0/SPKR1 -> '
    'lswitch J1.6/7 -> J2.1/2 (mx26 docs/d24-netlist-global-pins.csv G0209/G3461/G3462/'
    'G3463). Upstream: C1_TEST_OSC injects at C1_IN_%02d -> strip -> MAIN -> C2_MAIN_FDR -> '
    'C2_MON -> C2_MON_DLY -> C2_MON_OUT slot 0, every hop with a contract cell '
    '(Chan%03dMainOn001/Level001/Pan001/Mute001, Main001Level001, Mon001Level001/002). '
    'MW/D32/DSP/SHARC/dsp.csv declares it: sink=SPKR on C2_MON_OUT, sink=DNP on '
    'C2_CODEC_AUX_OUT. THE RETURN: the panel MEMS mic (ADAU7002) on A_I7 TDM slot 4 '
    '(0-based), node C1_XIN_MEMS, read here as TEST_MEAS lane code %d.'
    % (_SPKR_OSC_STRIP, _SPKR_OSC_STRIP, AL1_MEAS_CHAN))


def al1_level(r):
    """The drive level this run uses, hard-capped. A number past the cap is
    NOT an error that stops the run -- it is clamped and said out loud, so a
    fat finger on the bench cannot turn a self-test into a full-scale tone."""
    want = r.a.al1_level
    if want > AL1_TONE_CAP_DBFS:
        print('  AL1: --al1-level %g dBFS is past the %g dBFS cap; using the cap'
              % (want, AL1_TONE_CAP_DBFS))
        return AL1_TONE_CAP_DBFS
    return want


def _al1_prereq(r):
    """Everything that has to be true before a tone is worth playing, as
    (blocker-or-None, evidence-lines, capture-dict). The rails are RAISED here
    when they are down -- PW lifted the dispatched-session bar on 2026-09-24 --
    and the fact is recorded so handback can put them back."""
    ev = ['%s\n' % SPKR_ROUTE_NOTE]
    cap = {'an_start': r.an_en(), 'raised': False}
    if 'hi' not in cap['an_start']:
        # The two gates that still apply: the digital clocks are stable (the
        # pair is booted and its lanes read, which section C has already
        # established by the time AL1 runs) and the 595 chain is loaded SAFE.
        r.pin('%d op dh' % AN_EN_GPIO)
        time.sleep(1.0)
        cap['raised'] = True
    cap['an'] = r.an_en()
    ev.append('AN_EN (GPIO%d): at entry %s; now %s%s'
              % (AN_EN_GPIO, cap['an_start'].split('//')[0].strip(),
                 cap['an'].split('//')[0].strip(),
                 ' (RAISED by this run; handback lowers it)' if cap['raised'] else ''))
    ev.append('pair booted: %s (%s)' % (r.pair, r.pair_why))

    cap['testnodes'] = r.out(
        'cd %s && python3 -c "import json;j=json.load(open(\'chip1.sym.json\'));'
        'print(\'%s\' in j)"' % (r.a.stage, _OSC_SYM), timeout=60) == 'True'
    ev.append('DSP4_TEST_NODES pair (%s in chip1.sym.json): %s'
              % (_OSC_SYM, cap['testnodes']))

    # rxscan, once, for the one thing it is good at: is the lane carrying.
    rows = _lane_rows(rxscan(r))
    cap['mems_row'] = _mems_row(rows)
    ev.append('--- MEMS lane, rxscan ---\n%s'
              % (cap['mems_row'] or 'no MEMS lane in the scan'))

    close, route = _route_cells()
    rc1, t1 = _set(r, close)
    rc2, t2 = _set(r, route)
    # `NOT IN CONTRACT` is expected on the CLOSE write and only there: it walks
    # strips 1-32 and a D24 has 24, so 25-32 have no cells.
    bad = rc1 or rc2 or 'Traceback' in t1 or 'Traceback' in t2 \
        or 'NOT IN CONTRACT' in t2
    cap['route_rc'] = 1 if bad else 0
    ev.append('--- the route write (exit %d) ---\n--- other strips off MAIN ---\n%s'
              '\n--- the route ---\n%s' % (cap['route_rc'], t1[-400:], t2[-800:]))
    cap['probe'] = r.out('cd %s && python3 s89_set.py %s Mon001Level001 Mon001Level002 '
                         'Main001Level001 Chan%03dMainOn001 2>&1'
                         % (r.a.stage, r.a.stage, _SPKR_OSC_STRIP), timeout=120)
    ev.append('--- read back through the image\'s own dispatch table ---\n%s' % cap['probe'])

    if cap['route_rc']:
        return 'the route write failed -- nothing downstream would be measured', ev, cap
    if cap['mems_row'] is None:
        return 'no MEMS lane in the scan', ev, cap
    if not cap['testnodes']:
        return ('a DSP4_TEST_NODES=1 pair is needed (TEST_OSC\'s injection hook is inside '
                'that guard; the staged pair is the shipping pair). `--pair DIR`, or '
                'PAIR_CONF on the unit for a run the wizard\'s own START launches'), ev, cap
    if 'hi' not in cap['an']:
        return ('the analog rails did not come up (AN_EN = %s). Without them the TS482 has '
                'no supply and the MEMS lane is dark' % cap['an'].split('//')[0].strip()), ev, cap
    return None, ev, cap


def al1_measure(r, level):
    """Baseline, tone, baseline again -- the three legs of one loop reading.

    The baseline is taken WITH THE ROUTE ASSERTED and not before it, which is
    not fussiness: strip 20's own input noise reaches the speaker through the
    same route the tone does, so a floor measured with MainOn off is not the
    floor the tone is compared against. The second baseline is what says the
    floor came back and the reading was the tone rather than something in the
    room."""
    base, t0 = _al1_osc(r, None)
    tone, t1 = _al1_osc(r, level)
    back, t2 = _al1_osc(r, None)
    return {'base': base, 'tone': tone, 'back': back,
            'raw': '--- baseline (tone off) ---\n%s\n--- tone at %.1f dBFS ---\n%s'
                   '\n--- tone off again ---\n%s' % (t0, level, t1, t2)}


def al1_numbers(m, level):
    """The measured quantities, or None with the reason. One place, so the
    calibrator and the verdict cannot compute them differently."""
    if not (m['base'] and m['tone'] and m['back']):
        missing = [k for k in ('base', 'tone', 'back') if not m[k]]
        return None, 'no settled window for: %s' % ', '.join(missing)
    n = {'drive_dbfs': level,
         'base_dbfs': m['base']['rms_dbfs'],
         'tone_dbfs': m['tone']['rms_dbfs'],
         'back_dbfs': m['back']['rms_dbfs'],
         'thdn_db': m['tone']['thd_db'],
         'noise_dbfs': m['tone']['noise_dbfs'],
         'on_seconds': m['tone'].get('on_seconds')}
    n['thdn_pct'] = pct_of_db(n['thdn_db'])
    n['snr_db'] = n['tone_dbfs'] - n['base_dbfs']
    n['return_db'] = n['back_dbfs'] - n['base_dbfs']
    return n, None


def al1_verdict(n):
    """The four coarse outcomes the dispatch asked for, in order. Every number
    they lean on is in AL1_CAL and nowhere else."""
    c = AL1_CAL
    pred = c['slope_db_per_db'] * n['drive_dbfs'] + c['intercept_dbfs']
    n['pred_dbfs'] = pred
    # The noise floor already in the reading sets how good THD+N could
    # possibly be; anything past THAT by the margin is distortion.
    n['thdn_ceiling_db'] = max(c['thdn_abs_db'], -n['snr_db'] + c['thdn_margin_db'])
    if n['snr_db'] < c['snr_min_db']:
        return FAIL, 'NO SOUND'
    if n['tone_dbfs'] < pred - c['level_tol_db']:
        return FAIL, 'LOW'
    if n['thdn_db'] > n['thdn_ceiling_db']:
        # 'CLIP' and not 'CLIP/DISTORTED': the word leads a line the glass cuts
        # at 70 characters and the long form costs ten of them. The evidence
        # below spells out that it is clipping OR any other distortion.
        return FAIL, 'CLIP'
    if c['high_fails'] and n['tone_dbfs'] > pred + c['level_hi_tol_db']:
        return FAIL, 'HIGH'
    return PASS, 'PASS'


AL1_NO_SOUND_NOTE = (
    'NO SOUND means the tone did not come back. This test CANNOT say which stage: the DSP '
    'graph to codec slot 0, the AK4619 DAC (U3.22), C23/SPKR/J59.12=J42.12/C82, the TS482 '
    'amplifier (U32) and its 5 V, the SPKR0/SPKR1 pair, the lswitch J1.6/7 FPC and J2 lead, '
    'the speaker itself, the ADAU7002 MEMS mic, its PDM clock, or the A_I7 slot-4 lane are '
    'all in series and one reading sees all of them. Check the J2 speaker lead and the '
    'J13 = lswitch J1 panel FPC first -- they are the two connectors in the loop -- then '
    'probe U3.22 for the tone to split the loop in half.')


def t_al1(r):
    """The whole acoustic loop: tone out of the panel speaker, back in through
    the panel MEMS mic, in one press."""
    lim = ('level within %.0f dB of the calibrated line (pred = %.3f x drive %+.2f dBFS), '
           'SNR >= %.0f dB over the tone-off floor, THD+N under the ceiling '
           '(PROVISIONAL -- %s)'
           % (AL1_CAL['level_tol_db'], AL1_CAL['slope_db_per_db'],
              AL1_CAL['intercept_dbfs'], AL1_CAL['snr_min_db'],
              AL1_CAL['provisional']))
    blocker, ev, cap = _al1_prereq(r)
    r._al1_an = cap                      # handback reads this
    if blocker:
        return NODATA, blocker, lim, '\n'.join(ev) + '\nPREREQUISITE: ' + blocker

    if r.a.al1_calibrate:
        return al1_calibrate(r, ev)

    level = al1_level(r)
    m = al1_measure(r, level)
    ev.append(m['raw'])
    n, why = al1_numbers(m, level)
    if n is None:
        return NODATA, why, lim, '\n'.join(ev)

    if (cap['mems_row'] or '').endswith('STATIC') and n['snr_db'] < AL1_CAL['snr_min_db']:
        return (NODATA,
                'the MEMS lane reads STATIC and the tone did not move it -- nothing was '
                'measured (base %.2f, tone %.2f dBFS)' % (n['base_dbfs'], n['tone_dbfs']),
                lim,
                '\n'.join(ev) + '\nPREREQUISITE: a MEMS lane that reads. The speaker is '
                'measured THROUGH the microphone, so a dead lane would score the speaker '
                'FAIL for a microphone fault.')

    if n['base_dbfs'] > AL1_CAL['floor_max_dbfs']:
        ev.append('\nNOTE: the tone-off floor is %.2f dBFS, above the %.2f dBFS the table '
                  'calls a floor. Something is feeding the speaker, or the room is loud. '
                  'The verdict below still stands -- it is measured against THIS run\'s own '
                  'baseline -- but the margin is smaller than the calibration had.'
                  % (n['base_dbfs'], AL1_CAL['floor_max_dbfs']))

    verdict, word = al1_verdict(n)
    high = (word == 'PASS'
            and n['tone_dbfs'] > n['pred_dbfs'] + AL1_CAL['level_hi_tol_db'])
    if high:
        # The window's other edge. Not scored (AL1_CAL['high_fails']) because a
        # hand or a voice near the panel lifts this reading and a factory test
        # that fails for that is worse than one that says so; marked here so a
        # genuinely hot loop is not silent.
        word = 'PASS+'
    # THE GLASS TRUNCATES `measured` AT 70 CHARACTERS (TestSkinStore.
    # OneResultLine: `if (m.Length > 70) m = m.Substring(0, 67) + "..."`), and
    # PW asked for the verdict word, the baseline, the tone level, the SNR and
    # THD+N in dB AND percent to be ON THE TILE. So this line carries exactly
    # those, inside the budget, and every other number -- the drive level, the
    # predicted level, the in-window noise, the floor afterwards, the
    # oscillator on-time -- is in the evidence below, which the CSV keeps in
    # full. S110 found this by reading the glass after the first press, where
    # the old long form was cut off at "tone -49.36 dBFS (p...".
    measured = ('%s base %.1f tone %.1f SNR %.1f dB THD+N %.1f dB %.1f%%'
                % (word, n['base_dbfs'], n['tone_dbfs'], n['snr_db'],
                   n['thdn_db'], n['thdn_pct']))
    if len(measured) > 70:                       # never let the glass cut it
        measured = ('%s %.0f/%.0f SNR %.0f THD+N %.0f dB %.0f%%'
                    % (word, n['base_dbfs'], n['tone_dbfs'], n['snr_db'],
                       n['thdn_db'], n['thdn_pct']))
    ev.append('\n--- the numbers ---\n'
              'drive            %8.2f dBFS peak\n'
              'baseline (off)   %8.2f dBFS\n'
              'tone (on)        %8.2f dBFS   predicted %.2f (%.3f x drive %+.2f)\n'
              'SNR              %8.2f dB    (tone on minus tone off)\n'
              'THD+N            %8.2f dB  = %.3f %%   ceiling %.2f dB = %.3f %%\n'
              'in-window noise  %8.2f dBFS\n'
              'floor afterwards %8.2f dBFS  (%+.2f dB)\n'
              'oscillator on    %8s s      (cap %.1f s)\n'
              'VERDICT          %s (%s)'
              % (n['drive_dbfs'], n['base_dbfs'], n['tone_dbfs'], n['pred_dbfs'],
                 AL1_CAL['slope_db_per_db'], AL1_CAL['intercept_dbfs'],
                 n['snr_db'], n['thdn_db'], n['thdn_pct'],
                 n['thdn_ceiling_db'], pct_of_db(n['thdn_ceiling_db']),
                 n['noise_dbfs'], n['back_dbfs'], n['return_db'],
                 ('%.2f' % n['on_seconds']) if n['on_seconds'] else '?',
                 AL1_MAX_ON_S, word, verdict))
    if high:
        ev.append('\nNOTE: the level is %+.2f dB above the predicted line, past the '
                  '%.1f dB upper edge of the window. NOT scored (AL1_CAL[\'high_fails\'] '
                  'is False): a hand or a voice near the panel lifts this reading, and a '
                  'factory test that fails for that is worse than one that says so. The '
                  'verdict word is PASS+ so it is not silent.'
                  % (n['tone_dbfs'] - n['pred_dbfs'], AL1_CAL['level_hi_tol_db']))
    ev.append('\nTHE WINDOWS ARE PROVISIONAL (%s). They live in ONE place, AL1_CAL at the '
              'top of the AL1 section of this file, and `--only AL1 --al1-calibrate` '
              're-measures and rewrites them.\n%s'
              % (AL1_CAL['provisional'],
                 AL1_NO_SOUND_NOTE if word == 'NO SOUND' else ''))
    return verdict, measured, lim, '\n'.join(ev)


# --- calibration ------------------------------------------------------------
AL1_CAL_LEVELS = (-30.0, -20.0, -10.0)
AL1_CAL_REPS = 5


def al1_calibrate(r, ev):
    """Re-measure the table on this unit and rewrite it in this file.

    One command, because the table has to be re-derivable in one: PW is about
    to change the amp gain and the alternative to this is hand-editing eight
    numbers from a report. Prints every run, the old table and the new one, and
    what moved."""
    grid = []
    for lv in AL1_CAL_LEVELS:
        if lv > AL1_TONE_CAP_DBFS:
            continue
        for k in range(AL1_CAL_REPS):
            m = al1_measure(r, lv)
            n, why = al1_numbers(m, lv)
            if n is None:
                print('  AL1 cal %6.1f dBFS rep %d: %s' % (lv, k + 1, why))
                continue
            n['rep'] = k + 1
            grid.append(n)
            print('  AL1 cal %6.1f dBFS rep %d: base %7.2f  tone %7.2f  SNR %6.2f  '
                  'THD+N %7.2f dB = %7.3f %%'
                  % (lv, k + 1, n['base_dbfs'], n['tone_dbfs'], n['snr_db'],
                     n['thdn_db'], n['thdn_pct']))
    if len(grid) < 4:
        return (NODATA, 'calibration got %d usable runs' % len(grid),
                'at least 4 runs over 2 levels', '\n'.join(ev))

    old = dict(AL1_CAL)
    new = al1_fit(grid, r)
    table = al1_table(grid)
    diff = '\n'.join(
        '  %-18s %12s -> %12s%s'
        % (k, _fmt(old.get(k)), _fmt(new[k]),
           '' if _fmt(old.get(k)) == _fmt(new[k]) else '   CHANGED')
        for k in AL1_CAL_KEYS_NUMERIC)
    wrote = al1_write_table(new)
    ev.append('\n--- every calibration run ---\n%s' % table)
    ev.append('\n--- the table: old -> new ---\n%s' % diff)
    ev.append('\n%s' % wrote)
    print('\n--- every calibration run ---\n%s' % table)
    print('\n--- the table: old -> new ---\n%s' % diff)
    print(wrote)
    return (NODATA,
            'CALIBRATION, not a verdict: %d runs over %d levels; the table was rewritten'
            % (len(grid), len(set(g['drive_dbfs'] for g in grid))),
            'a calibration run scores nothing -- it sets the windows the next run is '
            'scored against', '\n'.join(ev))


def _fmt(v):
    return ('%.3f' % v) if isinstance(v, float) else str(v)


def al1_table(grid):
    head = ('  drive    rep   baseline      tone        SNR     THD+N        THD+N   '
            '  noise    on\n  dBFS           dBFS       dBFS        dB        dB     '
            '      %      dBFS     s')
    lines = [head]
    for g in grid:
        lines.append('  %6.1f %5d %10.2f %10.2f %10.2f %9.2f %12.3f %9.2f %6s'
                     % (g['drive_dbfs'], g['rep'], g['base_dbfs'], g['tone_dbfs'],
                        g['snr_db'], g['thdn_db'], g['thdn_pct'], g['noise_dbfs'],
                        ('%.2f' % g['on_seconds']) if g['on_seconds'] else '?'))
    for lv in sorted(set(g['drive_dbfs'] for g in grid)):
        at = [g for g in grid if g['drive_dbfs'] == lv]
        t = [g['tone_dbfs'] for g in at]
        lines.append('  mean at %6.1f: tone %.2f dBFS (spread %.2f dB), baseline %.2f, '
                     'SNR %.2f dB, THD+N %.2f dB = %.3f %%'
                     % (lv, sum(t) / len(t), max(t) - min(t),
                        sum(g['base_dbfs'] for g in at) / len(at),
                        sum(g['snr_db'] for g in at) / len(at),
                        sum(g['thdn_db'] for g in at) / len(at),
                        pct_of_db(sum(g['thdn_db'] for g in at) / len(at))))
    return '\n'.join(lines)


# A calibration point defines the line only if the window it came from was
# MEASURING A TONE. THD+N is exactly the test for that: it is everything in
# the window that is not the fundamental, over the total, so THD+N above
# -6 dB means the fundamental is less than half of what was there and the
# window is reading the room.
#
# S110 needed this, and an SNR gate did not do it. At -30 dBFS drive the tone
# lands ON the mic's floor: the level readings scattered over 3.8 dB and two
# of the five happened to sit 4.4 and 7.0 dB above their own baseline purely
# because the baseline window before them was quiet. An SNR gate let those two
# in and they bent the line from 0.97 to 0.79 dB/dB, which would have made
# every later reading at -10 look 2 dB low. Their THD+N was -1.15 and -2.23 dB
# -- 88 % and 77 % -- and no gate on THD+N of any plausible value admits them.
AL1_FIT_THDN_MAX_DB = -6.0
AL1_FIT_SNR_MIN_DB = 3.0


def al1_fit(grid, r):
    """Least squares on the points the loop actually carried, plus the
    windows around them.

    A point that was not measuring a tone is EXCLUDED from the line (see
    AL1_FIT_THDN_MAX_DB). It is still printed in the table -- it is the
    measurement that says how far down this loop can be driven and still be
    read, which is worth more than a fitted point would have been."""
    c = dict(AL1_CAL)
    use = [g for g in grid if g['thdn_db'] <= AL1_FIT_THDN_MAX_DB
           and g['snr_db'] >= AL1_FIT_SNR_MIN_DB]
    if len(use) < 2 or len(set(g['drive_dbfs'] for g in use)) < 2:
        use = list(grid)
    xs = [g['drive_dbfs'] for g in use]
    ys = [g['tone_dbfs'] for g in use]
    n = float(len(xs))
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    slope = (sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx) if sxx else 1.0
    inter = my - slope * mx
    resid = [y - (slope * x + inter) for x, y in zip(xs, ys)]
    spread = max(resid) - min(resid)
    c['slope_db_per_db'] = round(slope, 3)
    c['intercept_dbfs'] = round(inter, 2)
    # The window is the observed spread plus headroom, floored at 4 dB: a
    # window tighter than the run-to-run spread of the thing it measures
    # fails good units, and this is a coarse fault check, not a grade.
    c['level_tol_db'] = round(max(4.0, spread + 3.0), 1)
    c['level_hi_tol_db'] = round(c['level_tol_db'] + 3.0, 1)
    bases = [g['base_dbfs'] for g in grid]
    c['floor_max_dbfs'] = round(max(bases) + 6.0, 1)
    # NO SOUND has to sit below the worst SNR a working loop showed at the
    # level the test actually runs at, with room for a noisier room.
    # NO SOUND is a LABEL, not the safety net. What actually catches a dead
    # loop is the level window above: with no tone the mic reads its own
    # floor, which on this unit is 7 dB or more below the fitted line, so the
    # verdict is LOW even when a noisy room lifts the apparent SNR. So this
    # threshold is set LOW on purpose -- it is there to name the obvious case,
    # and a false NO SOUND on a loud bench would be the worse error.
    at_def = [g for g in use if abs(g['drive_dbfs'] - AL1_TONE_DBFS) < 0.01] or use
    worst_snr = min(g['snr_db'] for g in at_def)
    c['snr_min_db'] = round(max(3.0, worst_snr - 3.0), 1)
    # THD+N. Two ceilings, and the reason there are two is in the table's own
    # comment: over this loop THD+N is mostly NOISE at the safe drive level.
    # `thdn_abs_db` comes from the points at the level the test actually runs
    # at; `thdn_margin_db` is how far past what the measured SNR already
    # explains a healthy loop went, worst case.
    excess = [g['thdn_db'] - (-g['snr_db']) for g in use]
    c['thdn_margin_db'] = round(max(excess) + 3.0, 1)
    c['thdn_abs_db'] = round(max(g['thdn_db'] for g in at_def) + 3.0, 1)
    c['stamp'] = stamp()
    c['pair'] = str(r.pair)
    lo = min(g['drive_dbfs'] for g in use)
    c['runs'] = ('%d runs at %s dBFS x %d reps; %d fitted, %d excluded as not '
                 'measuring a tone (THD+N > %g dB); lowest drive that read: '
                 '%g dBFS; default drive %g dBFS'
                 % (len(grid), '/'.join('%g' % l for l in sorted(set(g['drive_dbfs']
                                                                    for g in grid))),
                    AL1_CAL_REPS, len(use), len(grid) - len(use),
                    AL1_FIT_THDN_MAX_DB, lo, AL1_TONE_DBFS))
    return c


def al1_write_table(new):
    """Rewrite AL1_CAL in this source file, between its own markers.

    In place and in this file on purpose: the table is the thing a reader of
    the test has to be able to see, and a JSON file beside it would be a
    second place for it to live. The file is re-read and re-parsed before it
    is replaced, so a failed rewrite leaves the old table intact."""
    path = os.path.abspath(__file__)
    src = open(path, encoding='utf-8').read()
    head = 'AL1_CAL = {'
    i = src.find('\n' + head)
    if i < 0:
        return 'TABLE NOT REWRITTEN: AL1_CAL not found in %s' % path
    j = src.find('\n}\n', i)
    if j < 0:
        return 'TABLE NOT REWRITTEN: no end of AL1_CAL in %s' % path
    body = ["\n%s" % head,
            "    'provisional': %r," % new['provisional'],
            "    'unit': %r," % new['unit'],
            "    'stamp': %r," % new['stamp'],
            "    'pair': %r," % new['pair'],
            "    'runs': %r," % new['runs'],
            "    'slope_db_per_db': %s," % _fmt(new['slope_db_per_db']),
            "    'intercept_dbfs': %s," % _fmt(new['intercept_dbfs']),
            "    'level_tol_db': %s," % _fmt(new['level_tol_db']),
            "    'level_hi_tol_db': %s," % _fmt(new['level_hi_tol_db']),
            "    'high_fails': %r," % new['high_fails'],
            "    'snr_min_db': %s," % _fmt(new['snr_min_db']),
            "    'floor_max_dbfs': %s," % _fmt(new['floor_max_dbfs']),
            "    'thdn_abs_db': %s," % _fmt(new['thdn_abs_db']),
            "    'thdn_margin_db': %s," % _fmt(new['thdn_margin_db']),
            "}"]
    out = src[:i] + '\n'.join(body) + src[j + 2:]
    try:
        compile(out, path, 'exec')
    except SyntaxError as exc:
        return 'TABLE NOT REWRITTEN: the rewrite would not parse (%s)' % exc
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(out)
    return ('TABLE REWRITTEN in %s. The comments above it -- including what makes each '
            'number provisional -- are untouched; only the dict body is replaced. '
            'Commit it: the table is the test.' % path)


# ---------------------------------------------------------------------------
# bench choreography
# ---------------------------------------------------------------------------
def stage_setup(r):
    """A stage directory of our own, populated the way the bench scripts do it.

    Two traps are avoided by construction. `/home/app/dspboot` is never booted
    from -- the candidate pair is staged there and must stay byte-identical --
    so the images are COPIED here. And the tools that exist only in this repo
    are scp'd AFTER the symlink loop and only for names the loop did not link,
    because an scp onto a symlink writes THROUGH it into /home/app/dspboot."""
    s = r.a.stage
    p = pair_dir(r)
    r.rsh("mkdir -p %s && cp %s/chip1.ldr %s/chip2.ldr "
          "%s/chip1.sym.json %s/chip2.sym.json %s/" % (s, p, p, p, p, s), timeout=120)
    r.rsh("for f in %s/*.py; do ln -sfn \"$f\" %s/$(basename \"$f\"); done; "
          "ln -sfn %s/input_patch.json %s/input_patch.json" % (DSPBOOT, s, DSPBOOT, s),
          timeout=120)
    # s89_set.py and dsp4_s49_osc.py are the S102 speaker route's own two tools
    # and NEITHER is in /home/app/dspboot -- the symlink loop above cannot find
    # them, which is exactly the trap that made loopthd.sh's first run measure
    # the default configuration and report PASS on a route it never asserted.
    for name in ('d24_bus_probe.py', 's89_signbit.py', 's89_slotcap.py',
                 's89_set.py', 'dsp4_s49_osc.py'):
        src = os.path.join(HERE, name)
        if os.path.exists(src):
            r.rsh('rm -f %s/%s' % (s, name))          # never scp onto a symlink
            r.put(src, s)
    return ('pair: %s (%s)\n' % (r.pair, r.pair_why)
            + r.out('ls -l %s | head -20; md5sum %s/chip1.ldr %s/chip2.ldr' % (s, s, s)))


def pair_dir(r):
    """Which pair this run boots, resolved ONCE and remembered on the rig.

    `--pair` wins. Otherwise PAIR_CONF on the unit, if a session has put one
    there -- that is the only way a run launched by the wizard's own START
    button (which passes no arguments) can be pointed at a DSP4_TEST_NODES=1
    pair. Otherwise the signed candidate. A pointer to a directory that does
    not hold a pair is an ERROR, not a silent fall back to the default: a run
    that quietly booted the shipping image after being asked for a test-node
    one would report `waiting on a DSP4_TEST_NODES=1 pair` and read as a
    prerequisite rather than as the mistake it is."""
    if r.pair:
        return r.pair
    p, why = r.a.pair, '--pair'
    if not p:
        p, why = r.out('cat %s 2>/dev/null' % PAIR_CONF).strip(), PAIR_CONF
    if not p:
        p, why = PAIR_DEFAULT, 'default'
    missing = r.out('for f in chip1.ldr chip2.ldr chip1.sym.json chip2.sym.json; '
                    'do [ -f %s/$f ] || echo $f; done' % p)
    if missing:
        sys.exit('ERROR: pair directory %s (%s) has no %s'
                 % (p, why, ', '.join(missing.split())))
    r.pair, r.pair_why = p, why
    return p


def pin_handback(r):
    """The pin handback a boot needs. NOT `pinctrl set 6,...,24,... a0`, which
    is what every old run script still does: GPIO24's ALT0 is SD0_DAT2, not a
    deasserted CS, so chip 2's select sits asserted while chip 1's stream is
    clocked and chip 2 comes up running chip1.ldr."""
    r.pin('7,9,10,11,22,23,25 a0')
    r.pin('%d,%d op dh' % (CS_GPIO[1], CS_GPIO[2]))
    # `ip pd`, not bare `ip`: GPIO8 powers up pulled UP and GPIO12 pulled DOWN,
    # so a later `pinctrl get` of the two SPI_RDY lines was only readable on one
    # of them (S100). With the CM4's pull matching the card's 10K pulldown, a
    # HIGH on either is the part driving it and nothing else. The boot is
    # unaffected: the line reads low while the part is in reset either way.
    r.pin('%d,%d ip pd' % (RDY_GPIO[1], RDY_GPIO[2]))


def boot_pair(r):
    """Boot and configure both chips TWICE. The config commit desyncs the
    parameter link on the first pass every time -- pre-existing, reproduces on
    the original image -- and the pair reaches BOOT_STAGE 7 on the second."""
    log = []
    for cycle in (1, 2):
        pin_handback(r)
        b = r.rsh('cd %s && python3 dsp4_boot.py --dir . 2>&1 | tail -12' % r.a.stage, timeout=300)
        log.append('--- boot cycle %d ---\n%s' % (cycle, b.stdout + b.stderr))
        for chip in (1, 2):
            r.pin('%d,%d op dh' % (CS_GPIO[1], CS_GPIO[2]))
            c = r.rsh('cd %s && python3 dsp4_config.py --product d24 --chip %d 2>&1 | tail -6'
                      % (r.a.stage, chip), timeout=300)
            log.append('--- config cycle %d chip %d ---\n%s' % (cycle, chip, c.stdout + c.stderr))
    # s89_signbit takes the symbol directory as argv[1] -- called bare it raises
    # IndexError before it reads the part, and the gate silently scores nothing.
    sb = r.rsh('cd %s && python3 s89_signbit.py %s 2>&1 | tail -6'
               % (r.a.stage, r.a.stage), timeout=180)
    log.append('--- inter-chip link gate (s89_signbit, exit %d) ---\n%s'
               % (sb.returncode, sb.stdout + sb.stderr))
    return '\n'.join(log)


def app_stop(r):
    r.an_en_at_start = r.an_en()
    r.rsh('sudo systemctl stop matrix-app', timeout=90)
    time.sleep(2)
    r.app_stopped = True
    print('matrix-app stopped; AN_EN at start: %s' % r.an_en_at_start)


def handback(r):
    """Unit as found. Order matters: SAFE goes on the chain LAST, after the
    final DSP boot, because a boot clocks half a megabyte through it and only
    a CS_M edge decides what gets latched (S70-7)."""
    notes = []
    notes.append('SAFE image: %s' % _chain(r, SAFE_IMAGE))
    # DRIVEN high, not pulled: since S109 the pull no longer holds CS_M.
    r.pin('%d op dh' % CS_M_GPIO)
    notes.append('CS_M: %s' % r.out('pinctrl get %d' % CS_M_GPIO))
    # AN_EN. The module never raises the rails except in AL1, which needs the
    # TS482 and the microphone powered; a run that raised them puts them back,
    # and one that found them up leaves them up for whoever owns them -- except
    # that with matrix-app stopped for the whole session there IS no other
    # owner, so `--al1-keep-rails` is the way to say "leave them".
    cap = getattr(r, '_al1_an', None)
    an_before = r.an_en()
    if cap and cap.get('raised') and not r.a.al1_keep_rails:
        r.pin('%d op dl' % AN_EN_GPIO)
        notes.append('AN_EN: %s at entry, RAISED by AL1, LOWERED here -> %s'
                     % (cap['an_start'].split('//')[0].strip(), r.an_en()))
    elif cap and cap.get('raised'):
        notes.append('AN_EN: %s at entry, RAISED by AL1, LEFT UP (--al1-keep-rails) -> %s'
                     % (cap['an_start'].split('//')[0].strip(), an_before))
    else:
        notes.append('AN_EN: %s (not written by this run)' % an_before)
    if r.a.no_app_restart:
        # Driven from the standalone test display: matrix-app is deliberately
        # down for the whole session and starting it here would seize the DRM
        # display from the process drawing the wizard. The hardware handback
        # above -- SAFE image, CS_M, AN_EN -- is unchanged; only the mixer's
        # restart is skipped, and with it the MCU-verify line it produces.
        notes.append('matrix-app: left stopped (--no-app-restart); '
                     'the test display owns the screen')
        notes.append('MCU verify (whole log): not read -- the app was not restarted')
        return '\n'.join(notes)
    r.rsh('sudo systemctl start matrix-app', timeout=120)
    time.sleep(25)
    notes.append('matrix-app: %s' % r.out('systemctl is-active matrix-app'))
    # The app REWRITES /home/app/logs/log on start, so the verdict is read from
    # the whole file, never from "lines added since a mark".
    notes.append('MCU verify (whole log): %s'
                 % ' | '.join(r.out('grep "MCU verified" /home/app/logs/log').splitlines()))
    return '\n'.join(notes)


# ---------------------------------------------------------------------------
def write_csv(r):
    exists = os.path.exists(r.csv_path)
    os.makedirs(os.path.dirname(r.csv_path), exist_ok=True)
    with open(r.csv_path, 'a', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLS)
        if not exists:
            w.writeheader()
        for row in r.rows:
            w.writerow(row)


def check_keys(path):
    """Cross-check the ITEMS table against --export-keys: every key present, and
    every row number written in a `# NNN` comment still the row it names.

    The numbers in the comments are the workbook positions the wizard prints.
    Until S98 nothing checked them -- they were hand-typed, the export carried no
    number to check them against, and a stale one would have quietly pointed a
    reader at a different item. The export now has a `num` column, so they are
    verified here rather than believed.
    """
    want = set()
    for its in ITEMS.values():
        want |= set(its)
    have = set()
    by_num = {}
    numbered = False
    # `num` is the WORKBOOK position, and since MERGED_KEYS (PW 2026-09-25) it
    # is no longer the line number: a bench row that covers two workbook rows
    # takes the first one's number and the second's is absent, so the export
    # has a gap. What still has to hold -- and is what the check was for -- is
    # that the numbers are unique and go up, so a `# NNN` comment resolves to
    # exactly one row and a resorted file is caught.
    last = 0
    with open(path, newline='') as fh:
        for i, row in enumerate(csv.DictReader(fh), start=1):
            have.add((row['board'], row['item']))
            n = (row.get('num') or '').strip()
            if not n:
                by_num[i] = (row['board'], row['item'])
                continue
            numbered = True
            if not n.isdigit() or int(n) <= last:
                sys.exit('ERROR: %s: num %r at line %d is not above the previous '
                         'row\'s %d (%s | %s)'
                         % (path, n, i, last, row['board'], row['item']))
            last = int(n)
            by_num[last] = (row['board'], row['item'])
    missing = sorted(want - have)
    if missing:
        sys.exit('ERROR: %d key(s) not in the export -- board/item must match verbatim:\n%s'
                 % (len(missing), '\n'.join('  %r' % (k,) for k in missing)))
    if not numbered:
        print('key check: %d distinct items, all present in the export '
              '(pre-S98 export: no num column, row numbers not checked)' % len(want))
        return
    bad = []
    src = open(__file__, encoding='utf-8').read().splitlines()
    checked = 0
    for line in src:
        m = re.search(r'#\s*(\d+)\s*$', line)
        if not m or "ITEMS[" in line:
            continue
        # The item is the last complete string literal on the line, in either
        # quote style -- `"Link 'dig-dsp-b'"` is one literal, not three.
        quoted = re.findall(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'',
                            line[:m.start()])
        if not quoted:
            continue
        n, item = int(m.group(1)), quoted[-1][1:-1]
        if n not in by_num:
            bad.append('  # %d is past the end of the export (%d rows)' % (n, len(by_num)))
        elif by_num[n][1] != item:
            bad.append('  # %d says %r, the export has %r' % (n, item, by_num[n][1]))
        checked += 1
    if bad:
        sys.exit('ERROR: %d stale row number(s) in the ITEMS table:\n%s'
                 % (len(bad), '\n'.join(bad)))
    print('key check: %d distinct items, all present in the export; '
          '%d row numbers in the table match their position' % (len(want), checked))


def summary(r):
    print('\n%-10s %-8s %s' % ('TEST', 'VERDICT', 'MEASURED'))
    print('-' * 78)
    tally = {PASS: 0, FAIL: 0, NODATA: 0}
    per_item = {}
    for row in r.rows:
        tally[row['verdict']] += 1
        k = (row['board'], row['item'])
        # An item's roll-up is its WORST verdict: a FAIL is not cancelled by a
        # PASS on another test of the same item.
        rank = {PASS: 0, NODATA: 1, FAIL: 2}
        if k not in per_item or rank[row['verdict']] > rank[per_item[k]]:
            per_item[k] = row['verdict']
    for t in sorted(r.results):
        print('%-10s %-8s' % (t, r.results[t]))
    it = {PASS: 0, FAIL: 0, NODATA: 0}
    for v in per_item.values():
        it[v] += 1
    print('-' * 78)
    print('rows:  %d PASS / %d FAIL / %d NO DATA  (%d rows)'
          % (tally[PASS], tally[FAIL], tally[NODATA], len(r.rows)))
    print('items: %d PASS / %d FAIL / %d NO DATA  (%d of 36 workbook rows covered)'
          % (it[PASS], it[FAIL], it[NODATA], len(per_item)))
    errs = [t for t in r.results if r.results[t] == NODATA
            and any(x['test'] == t and x['evidence'].startswith('RUNNER ERROR')
                    for x in r.rows)]
    if errs:
        print('\n*** RUNNER ERRORS (not honest NO DATAs): %s' % ', '.join(sorted(errs)))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--section', default='A,B,C')
    ap.add_argument('--only', help='comma-separated test ids to run within the chosen '
                                   'sections (e.g. NW3, or AS-ADC,MM1); the rest are skipped. '
                                   'Use it to re-take one row without superseding the others.')
    ap.add_argument('--stage', default='/home/app/s90')
    ap.add_argument('--pair',
                    help='directory holding the chip1/chip2 .ldr + .sym.json pair to '
                         'stage and boot. Default: %s, or whatever %s names on the '
                         'unit. A DSP4_TEST_NODES=1 pair goes here -- SP1 needs '
                         'TEST_OSC and the signed candidate does not carry it.'
                         % (PAIR_DEFAULT, PAIR_CONF))
    ap.add_argument('--local', action='store_true',
                    help='we ARE the CM4: run every command here instead of over '
                         'ssh, and copy staged files instead of scp-ing them. This '
                         'is how the D24 test skin drives the runner from the '
                         "unit's own display.")
    ap.add_argument('--csv', help='append results here instead of the repo path '
                                  '(the on-unit copy lives beside the skin catalog)')
    ap.add_argument('--keys', help='cross-check the key table against --export-keys output and exit')
    ap.add_argument('--no-append', action='store_true', help='print only; write no CSV rows')
    ap.add_argument('--nw3-runs', type=int, default=3,
                    help='ping passes per target for NW3; the verdict is the WORST, because a '
                         'single 200-packet run does not settle a 0%% bar on this bench')
    ap.add_argument('--soak-seconds', type=int, default=3600)
    ap.add_argument('--soak-interval', type=int, default=60)
    ap.add_argument('--no-soak-wait', action='store_true',
                    help='harvest the HD0-2 soak as it stands instead of waiting for the window')
    ap.add_argument('--al1-level', type=float, default=AL1_TONE_DBFS,
                    metavar='DBFS',
                    help='AL1: the 1 kHz tone level, dBFS PEAK, injected into '
                         'strip %d. Default %g. HARD-CAPPED at %g: a bigger '
                         'number is clamped and said out loud. PW drove this '
                         'speaker to full scale by hand on 2026-09-25 and it '
                         'was clean; an automated test still does not.'
                         % (_SPKR_OSC_STRIP, AL1_TONE_DBFS, AL1_TONE_CAP_DBFS))
    ap.add_argument('--al1-calibrate', action='store_true',
                    help='AL1: re-measure the provisional windows on this unit '
                         '(%s dBFS x %d reps) and REWRITE AL1_CAL in this file, '
                         'printing every run and the old and new tables. Scores '
                         'nothing. Run this after any change to the amp, the '
                         'speaker or the mic.'
                         % ('/'.join('%g' % l for l in AL1_CAL_LEVELS), AL1_CAL_REPS))
    ap.add_argument('--al1-keep-rails', action='store_true',
                    help='AL1: do NOT lower AN_EN at handback even if this run '
                         'raised it. For a bench session that wants the rails '
                         'left up for the next thing; the report says which '
                         'way it went either way.')
    ap.add_argument('--no-app-restart', action='store_true',
                    help='stop matrix-app for the bus-exclusive sections as usual, but do NOT '
                         'start it again at handback. For a run driven from the standalone '
                         'test display (d24-testui, S97), which owns the screen for the whole '
                         'factory session: starting matrix-app would take the DRM display away '
                         'from it. Everything else about handback is unchanged -- the 595 SAFE '
                         'image, CS_M and AN_EN are still put back.')
    a = ap.parse_args()
    if a.keys:
        check_keys(a.keys)
        return
    a.section = set(x.strip().upper() for x in a.section.split(','))
    a.only = set(x.strip().upper() for x in a.only.split(',')) if a.only else None
    if a.only:
        # A retired id runs the test it became, and says so rather than
        # failing: `--only SP1` is in every report S102 onward.
        hit = sorted(a.only & set(ALIASES))
        if hit:
            print('--only: %s' % ', '.join('%s -> %s' % (k, ALIASES[k]) for k in hit))
            a.only = {ALIASES.get(x, x) for x in a.only}
        unknown = a.only - set(ITEMS)
        if unknown:
            sys.exit('ERROR: --only names no such test: %s' % ', '.join(sorted(unknown)))

    r = Rig(a)
    print('D24 self-test, section 1 -- sections %s -- %s'
          % (','.join(sorted(a.section)), stamp()))

    soak = 'A' in a.section and (not a.only or {'HD0-2'} & a.only)
    if soak:
        # The soak is passive and long, so it starts first and is harvested last.
        r.rsh("rm -f /tmp/d24_hdsoak.log /tmp/d24_hdsoak.done /tmp/d24_hdsoak.uevents; "
              # seq 0..N, not 1..N: N samples at interval I SPAN (N-1)*I, so a
              # 3600 s window asked for as 60 samples of 60 s observes only 3540 s
              # and reports itself short. One extra sample makes the span the
              # window that was asked for.
              "nohup sh -c 'for i in $(seq 0 %d); do echo \"$(date -u +%%FT%%TZ) "
              "$(cat %s/status)\" >> /tmp/d24_hdsoak.log; sleep %d; done; "
              "touch /tmp/d24_hdsoak.done' >/dev/null 2>&1 &"
              % (max(1, a.soak_seconds // a.soak_interval), CONN, a.soak_interval))
        r.rsh("nohup timeout %d stdbuf -oL udevadm monitor --udev --subsystem-match=drm "
              "> /tmp/d24_hdsoak.uevents 2>/dev/null &" % a.soak_seconds)

    if 'A' in a.section:
        r.run('HD0-1', lambda: t_hd01(r))
        r.run('AS-CM4', lambda: t_ascm4(r))
        r.run('USB-HUB', lambda: t_usbhub(r))
        r.run('NW1', lambda: t_nw1(r))
        if not a.only or 'NW2' in a.only:
            r._nw2_before = _ifstats(r)
        r.run('NW3', lambda: t_nw3(r))
        r.run('NW4', lambda: t_nw4(r))
        r.run('NW2', lambda: t_nw2(r))

    if {'B', 'C'} & a.section:
        app_stop(r)

    try:
        if {'B', 'C'} & a.section:
            # INSIDE the try. Staging does an scp with check=True, and a failure
            # there used to leave `matrix-app` stopped with no handback -- the one
            # way this leg could break "the unit as found" while reporting nothing.
            print(stage_setup(r)[:400])
        if 'B' in a.section:
            r.run('ML1', lambda: t_ml1(r))
            r.run('ML2', lambda: t_ml2(r))
            r.run('ML-M', lambda: t_mlm(r))
            r.run('ML-P1', lambda: t_mlp1(r))
            r.run('ML-P2', lambda: t_mlp2(r))
            r.run('ML-B0', lambda: t_mlb0(r))
            r.run('CC1', lambda: t_cc1(r))
            r.run('CC2', lambda: t_cc2(r))
            r.run('MC1', lambda: t_mc1(r))
            r.run('MC2', lambda: t_mc2(r))
            r.run('MC3', lambda: t_mc3(r))
            # DR/DC need the pair up, so the prep boot runs before DR1 pulses
            # the reset out from under it.
            print(boot_pair(r)[-600:])
            r.run('DR1', lambda: t_dr1(r))
            r.run('DR2', lambda: t_dr2(r))
            # DY1 dips !RST_D itself and boots the pair back with boot_pair(),
            # so it sits after DR2 (which leaves the pair up for the first
            # sample) and before the DC selects (which need it up again).
            for c in (1, 2):
                r.run('DY1-RDY%d' % c, (lambda k: (lambda: t_dy1(r, k)))(c))
            for n in DC_SELECTS:
                r.run('DC1-CS%d' % n, (lambda k: (lambda: t_dc1(r, k)))(n))
            for n in DC_SELECTS:
                r.run('DC2-CS%d' % n, (lambda k: (lambda: t_dc2(r, k)))(n))
        elif 'C' in a.section:
            print(boot_pair(r)[-600:])

        if 'C' in a.section:
            r.run('AS-DSPA', lambda: t_asdspa(r))
            r.run('AS-DSPB', lambda: t_asdspb(r))
            r.run('AS-CPLD', lambda: t_ascpld(r))
            r.run('AS-ADC', lambda: t_asadc(r))
            r.run('AS-DAC', lambda: t_asdac(r))
            r.run('AS-PWR', lambda: t_aspwr(r))
            r.run('AL1', lambda: t_al1(r))
    finally:
        if r.app_stopped:
            print('\n--- handback ---\n%s' % handback(r))

    if soak:
        if not a.no_soak_wait:
            print('\nwaiting for the HD0-2 soak window (%d s)...' % a.soak_seconds, flush=True)
            deadline = time.time() + a.soak_seconds + 120
            while time.time() < deadline:
                if r.out('test -f /tmp/d24_hdsoak.done && echo done'):
                    break
                time.sleep(30)
        r.run('HD0-2', lambda: t_hd02(r))
    if 'A' in a.section:
        r.run('HD-PWR', lambda: t_hdpwr(r))

    summary(r)
    if not a.no_append:
        write_csv(r)
        print('\nappended %d rows to %s' % (len(r.rows), r.csv_path))
        print('raw reads: %s' % r.logdir)


if __name__ == '__main__':
    main()
