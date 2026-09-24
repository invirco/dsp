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
its own sake: AN_EN is `lo` on this unit and a dispatched session may not raise
it (bench note 19 / S49-15, "AN_EN is never written by a dispatched session"),
so the mic front ends are not converting and a dark lane is the TEST STATE. A
converter reported FAIL for that would be a defect invented by the harness.
Every test that depends on the rails therefore reads `_an_en()` first and says so.

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
  * it puts GPIO27 back to `ip pu` -- CS_M left low gates the U2 MISO buffer and
    looks exactly like a DSP link phase fault;
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
    'HD0-1':   [('HDMI FPC (rev B)', 'Display link HDMI0 → TFT'),        # 128
                (B_ASM, 'TFT display')],                                  # 204
    'HD0-2':   [('HDMI FPC (rev B)', 'Display link HDMI0 → TFT'),
                (B_ASM, 'TFT display')],
    'HD-PWR':  [(B_LINK, "Link 'hdmi-pwr'")],                             # 152
    'NW1':     [('Digital', 'Ethernet (RJ45)')],                          # 129
    'NW2':     [('Digital', 'Ethernet (RJ45)')],
    'NW3':     [('Digital', 'Ethernet (RJ45)')],
    'NW4':     [('Digital', 'Ethernet (RJ45)')],
    'AS-CM4':  [(B_ASM, 'CM4 compute module')],                           # 194
    'USB-HUB': [],           # no workbook item: the spec files it under section-2 UA1
    # B -- through H1S1 over the matrix bus
    'ML1':     [(B_DSP, 'H1S1 MCU (STM32U575) link'),                     # 102
                (B_ASM, 'S MCU H1S1 (STM32U575)')],                       # 203
    'ML2':     [(B_DSP, 'H1S1 MCU (STM32U575) link'),
                (B_ASM, 'S MCU H1S1 (STM32U575)')],
    'ML-M':    [(B_ASM, 'M MCU (STM32G031)')],                            # 202
    'ML-P1':   [(B_DSP, 'Right panel MCU link (fw.csv SW_RIGHT)'),        # 126
                (B_LINK, "Link 'dig-panel-a'")],                          # 144
    'ML-P2':   [(B_DSP, 'Left panel MCU link (fw.csv SW_LEFT)'),          # 127
                (B_LINK, "Link 'dig-panel-b'")],                          # 145
    'ML-B0':   [(B_DSP, 'Right panel MCU link (fw.csv SW_RIGHT)'),
                (B_DSP, 'Left panel MCU link (fw.csv SW_LEFT)')],
    'DR1':     [(B_DSP, 'DSP reset RST_D (fw.csv Reset)')],               # 111
    'DR2':     [(B_DSP, 'DSP reset RST_D (fw.csv Reset)')],
    'MC1':     [(B_DSP, 'Mic-gain chain latch CS_M (fw.csv MicGain)')],   # 112
    'MC2':     [(B_DSP, 'Mic-gain chain latch CS_M (fw.csv MicGain)')],
    'MC3':     [(B_DSP, 'Mic-gain chain latch CS_M (fw.csv MicGain)')],
    'CC1':     [(B_DSP, 'Codec select CS_C (fw.csv Codec)'),              # 113
                (B_ASM, 'Codec AK4619')],                                 # 200
    'CC2':     [(B_DSP, 'Codec select CS_C (fw.csv Codec)'),
                (B_ASM, 'Codec AK4619')],
    # C -- from the DSPs
    'AS-DSPA': [(B_ASM, 'SHARC DSP A (ADSP-21564)'),                      # 195
                (B_LINK, "Link 'dig-dsp-a'")],                            # 140
    'AS-DSPB': [(B_ASM, 'SHARC DSP B (ADSP-21564)'),                      # 196
                (B_LINK, "Link 'dig-dsp-b'")],                            # 141
    'AS-CPLD': [(B_ASM, 'CPLD clock master (MAX V)')],                    # 197
    'AS-ADC':  [(B_ASM, 'ADC AK5558 ×3 (U15 dead, U39, U60)'),            # 199
                (B_LINK, "Link 'dig-analog-adc'")],                       # 142
    'AS-DAC':  [(B_ASM, 'DAC AK4458 ×2'),                                 # 198
                (B_LINK, "Link 'dig-analog-dac'")],                       # 143
    'AS-PWR':  [(B_ASM, 'Power MCU (STM32F030F4, always-on)')],           # 201
    'MM1':     [(B_LSW, 'Panel MEMS mic (talkback)')],                    # 56
    'SP1':     [(B_LSW, 'Speaker')],                                      # 57
}
# DC1/DC2 fan out over the chip selects, one workbook row each (103-110) --
# EXCEPT CS3 and CS4 (rows 105/106). Those two nets are not chip selects in
# either direction: they carry DSPA's and DSPB's SPI2_RDY BACK to the CM4, and
# an assert-one-read-one test of them was a permanent NO DATA because it asked
# a question the wiring cannot answer (S100). They get DY1 instead, which tests
# what the line actually does.
DC_SELECTS = (1, 2, 5, 6, 7, 8)
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
for _t in ('AS-DSPA', 'AS-DSPB', 'AS-CPLD', 'AS-ADC', 'AS-DAC', 'AS-PWR', 'MM1', 'SP1'):
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


# --- the six selects that cannot answer, and why each one cannot -------------
#
# S100 checked all eight against MW/D24/HW/hardware-map.md and defs fw.csv
# rather than treating "not CS1/CS2" as one diagnosis. They are not one
# diagnosis: CS7/CS8 are as mis-described by the workbook row as CS3/CS4 were.
# fw.csv declares Dsp1..Dsp8 as H1S1 pins B12/C14/B14/B13/C13/B15/C15/H0 on
# nets CS1..CS8, so each row is an H1S1 PIN ON A NET, and H1S1 drives none of
# them: all eight are GPIO_Input and must stay that way (~/build-h1s1
# Core/Src/main.c MX_GPIO_Init_2, "ALL EIGHT CS pins are OWNED BY THE CM4").
DC_NO_DATA = {
    5: ('CS5 reaches no fitted part; the CM4 line is claimed for CS_M on this unit',
        'no part behind the select, and no read path to the net',
        'SPEC CORRECTION (S100). hardware-map.md:410-411: "CS1-8 DSP chip-select '
        'provision (8-DSP scaling -- only CS1/CS2 live on DSP4)". fw.csv Dsp5 is '
        'H1S1 pin C13 on net CS5, and H1S1 holds it an INPUT by decision, so nothing '
        'asserts it and H1S1 publishes no cell that could report its level -- there '
        'is no read path in either direction, not merely no part. Separately, the D8 '
        'amendment gives CS_M a spare stack CS line and this unit carries that as a '
        'proto wire from the CM4 CS5 pin (GPIO27) to the CS_M pad, so the CM4 end of '
        'CS5 is no longer free: driving it would move mic gain. MC1/MC2/MC3 exercise '
        'that wire; they do not exercise the board CS5 net.'),
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
    -- they are SPI_RDY and belong to DY1 -- and CS5-CS8 each say why they
    cannot answer in DC_NO_DATA above rather than sharing one blanket line."""
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
                raw + '\nPREREQUISITE: the analog rails. AN_EN (GPIO26) is low and a dispatched '
                      'session may not raise it (bench note 19 / S49-15: "AN_EN is never written '
                      'by a dispatched session"). With the front ends unpowered a STATIC lane is '
                      'the test state, not a converter fault, so this is NO DATA and not FAIL.')
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
                raw + '\nPREREQUISITE: the analog rails. AN_EN (GPIO26) is low and a dispatched '
                      'session may not raise it (bench note 19 / S49-15), so a STATIC lane here '
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


# --- the combined speaker + MEMS-mic test (S102) ----------------------------
#
# MM1 and SP1 are ONE measurement taken twice, not two tests: SP1 plays a tone
# out the panel speaker and the ONLY thing that can hear it is MM1's MEMS mic,
# sitting on the same Left Switch board. So one sequence runs -- idle capture,
# tone on, tone off -- and the two rows take their verdicts out of it. They stay
# two rows because they are two PARTS on the board inventory (56 the mic, 57 the
# speaker) and a unit with a dead speaker and a live mic has to land on 57.
#
# THE ROUTE EXISTS AND ALWAYS DID (S102, correcting S90-P6). What was missing
# was its NAME. The speaker is codec TDM slot 0 -- `C2_MON_OUT`'s left slot,
# `signal=CODEC_OUT_1` -- which is the AK4619's AOUT1L on pin 22, the ONLY
# codec DAC output fitted on a D24 (mx26 tools/netlist/parts.csv:67; AOUT1R,
# AOUT2L and AOUT2R have their caps C20/C21/C22 DNP). From there:
#
#   U3.22 -> analog C23 -> SPKR -> analog J59.12 = digital J42.12 -> C82
#         -> TS482 (digital U32) -> SPKR0/SPKR1 -> lswitch J1.6/7 -> J2.1/2
#
# and upstream of the slot the chain is ordinary graph:
#
#   C1_TEST_OSC (inject at C1_IN_nn) -> strip -> C1_RTG_nn main_on
#     -> MAIN mix -> C2_MAIN_FDR -> C2_MON -> C2_MON_DLY -> C2_MON_OUT slot 0
#
# Every hop has a contract cell: Chan<nn>MainOn/Level/Pan/Mute, Main001Level001,
# Mon001Level001/002. The node graph now says so out loud -- `sink=SPKR` on
# `C2_MON_OUT` (and `sink=DNP` on `C2_CODEC_AUX_OUT`, which reaches no fitted
# part at all) -- which is why a search of the topology for the speaker no
# longer comes back empty.
#
# TWO PREREQUISITES REMAIN AND BOTH ARE NAMED RATHER THAN WORKED AROUND:
#   * the analog rails (AN_EN, CM4 GPIO26). A dispatched session never writes
#     it (bench note 19 / S49-15). Without them the MEMS lane is dark and the
#     TS482 has no supply, so neither half can read.
#   * a DSP4_TEST_NODES=1 pair. TEST_OSC's injection hook is inside that guard,
#     so on the shipping image the oscillator cells take writes and nothing
#     reads them -- the same prerequisite AS-DAC carries.
_SPKR_OSC_STRIP = 20              # S89's donor strip, for the same reason
_SPKR_FREQ_HZ = 1000.0
_SPKR_DRIVE_DBFS = -20.0
_SPKR_MARGIN_DB = 20.0            # the spec's criterion
_SPKR_RETURN_DB = 3.0             # tone off -> back within this of the floor
_OSC_SYM = '_osc_blk_q_C1_TEST_OSC'


def _mems_row(rows):
    hit = [x for x in rows if 'MEMS' in x]
    return hit[0] if hit else None


def _mems_rms(row):
    """rxscan column 7 is the lane's rms in dBFS (same column t_asadc reads)."""
    if row is None:
        return None
    try:
        return float(row.split()[7])
    except (IndexError, ValueError):
        return None


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


def _spkr_capture(r):
    """One run of the whole sequence, cached on the rig so MM1 and SP1 read
    the SAME capture rather than scanning the lane twice and disagreeing."""
    cached = getattr(r, '_spkr_cap', None)
    if cached is not None:
        return cached

    cap = {'an': r.an_en(), 'route_rc': None, 'route_txt': '', 'probe': '',
           'tone': None, 'back': None, 'osc_on': '', 'osc_off': ''}
    idle_rows = _lane_rows(rxscan(r))
    cap['idle_rows'] = idle_rows
    cap['idle_row'] = _mems_row(idle_rows)
    cap['idle'] = _mems_rms(cap['idle_row'])

    # Is this a pair that can be driven at all? The symbol only exists inside
    # `#if DSP4_TEST_NODES`, which is exactly the check dsp4_s49_osc.py makes
    # before it refuses -- a shipping image would otherwise take every write
    # and read back a number that looks like a measurement.
    cap['testnodes'] = r.out(
        'cd %s && python3 -c "import json;j=json.load(open(\'chip1.sym.json\'));'
        'print(\'%s\' in j)"' % (r.a.stage, _OSC_SYM), timeout=60) == 'True'

    # The route is asserted and PROVED whatever the rails do: these are SPI
    # parameter writes through the image's own dispatch table, and the
    # read-back is what turns "there is a route" from a claim into a reading.
    close, route = _route_cells()
    rc1, t1 = _set(r, close)
    rc2, t2 = _set(r, route)
    # s89_set.py exits 0 whatever it printed, so the exit code alone does not
    # say the route was asserted. A name the contract does not carry, or a
    # link that would not phase, has to fail LOUDLY here -- everything
    # downstream would otherwise be a reading of the default configuration.
    # `NOT IN CONTRACT` is expected on the CLOSE write and only there: it
    # walks strips 1-32 and a D24 has 24, so 25-32 have no cells.
    bad = rc1 or rc2 or 'Traceback' in t1 or 'Traceback' in t2 \
        or 'NOT IN CONTRACT' in t2
    cap['route_rc'] = 1 if bad else 0
    cap['route_txt'] = ('--- other strips off MAIN ---\n%s\n--- the route ---\n%s'
                        % (t1[-400:], t2[-800:]))
    cap['probe'] = r.out('cd %s && python3 s89_set.py %s Mon001Level001 Mon001Level002 '
                         'Main001Level001 Chan%03dMainOn001 2>&1'
                         % (r.a.stage, r.a.stage, _SPKR_OSC_STRIP), timeout=120)

    if cap['testnodes']:
        cap['osc_on'] = r.out(
            'cd %s && python3 dsp4_s49_osc.py --strip %d --freq %g --level %g '
            '--symdir %s 2>&1' % (r.a.stage, _SPKR_OSC_STRIP, _SPKR_FREQ_HZ,
                                  _SPKR_DRIVE_DBFS, r.a.stage), timeout=300)
        tone_rows = _lane_rows(rxscan(r))
        cap['tone_row'] = _mems_row(tone_rows)
        cap['tone'] = _mems_rms(cap['tone_row'])
        cap['osc_off'] = r.out('cd %s && python3 dsp4_s49_osc.py --off --symdir %s 2>&1'
                               % (r.a.stage, r.a.stage), timeout=300)
        back_rows = _lane_rows(rxscan(r))
        cap['back_row'] = _mems_row(back_rows)
        cap['back'] = _mems_rms(cap['back_row'])

    r._spkr_cap = cap
    return cap


def t_mm1(r):
    """The mic half: is the MEMS lane alive, and where does it idle. This is
    also SP1's reference level, which is why it is one capture."""
    cap = _spkr_capture(r)
    v, m, lim, ev = _lane_verdict(r, cap['idle_rows'], 'MEMS', 'MEMS',
                                  'lane alive; idle floor within the declared window')
    return v, m, lim, ev + ('\nThe spec asks for the PDM clock as well as the lane, and nothing '
                            'on the CM4 reads it: the CPLD\'s lane witness counts cdc_o only -- '
                            'there is no counter on the MEMS group (bench note 31) -- so "lane '
                            'stuck" and "no PDM clock" are not separated by any read path that '
                            'exists. A stuck 0xFFFFFFFF is what S79-2 recorded on this lane too.'
                            '\nThis reading is the idle half of the combined SP1 capture (S102); '
                            'SP1 measures the same lane with the tone on.')


SPKR_ROUTE_NOTE = (
    'THE ROUTE, named (S102, correcting S90-P6 which read it as absent). The speaker is '
    'codec TDM slot 0 = C2_MON_OUT slot 0 = signal CODEC_OUT_1 = AK4619 AOUT1L (analog U3 '
    'pin 22) -- the ONLY codec DAC output fitted on a D24 (mx26 tools/netlist/parts.csv:67: '
    'C20/C21/C22 on AOUT1R/AOUT2L/AOUT2R are DNP). U3.22 -> C23 -> SPKR -> analog J59.12 = '
    'digital J42.12 -> C82 -> TS482 (digital U32) -> SPKR0/SPKR1 -> lswitch J1.6/7 -> J2.1/2 '
    '(mx26 docs/d24-netlist-global-pins.csv G0209/G3461/G3462/G3463). Upstream: C1_TEST_OSC '
    'injects at C1_IN_%02d -> strip -> MAIN -> C2_MAIN_FDR -> C2_MON -> C2_MON_DLY -> '
    'C2_MON_OUT slot 0, every hop with a contract cell (Chan%03dMainOn001/Level001/Pan001/'
    'Mute001, Main001Level001, Mon001Level001/002). MW/D32/DSP/SHARC/dsp.csv now declares it: '
    'sink=SPKR on C2_MON_OUT, sink=DNP on C2_CODEC_AUX_OUT.'
    % (_SPKR_OSC_STRIP, _SPKR_OSC_STRIP))


def t_sp1(r):
    """The speaker half: with the route asserted, does the tone reach the mic.

    Two prerequisites can stop this short and they are reported apart, because
    they belong to different people: the rails are PW's (a dispatched session
    never raises AN_EN) and the TEST_NODES pair is a build."""
    cap = _spkr_capture(r)
    lim = '1 kHz tone on the MEMS lane >= %g dB above its idle floor; tone off -> floor returns' \
        % _SPKR_MARGIN_DB
    an = cap['an']
    rails = 'hi' in an
    ev = ['%s\n' % SPKR_ROUTE_NOTE,
          'AN_EN (GPIO%d) = %s' % (AN_EN_GPIO, an),
          'DSP4_TEST_NODES pair (%s in chip1.sym.json): %s' % (_OSC_SYM, cap['testnodes']),
          '--- the route write (exit %s) ---\n%s' % (cap['route_rc'], cap['route_txt']),
          '--- read back through the image\'s own dispatch table ---\n%s' % cap['probe'],
          '--- MEMS lane, idle ---\n%s' % (cap['idle_row'] or 'no MEMS lane in the scan')]

    if cap['route_rc']:
        return (NODATA, 'the route write failed -- nothing downstream would be measured',
                lim, '\n'.join(ev))
    if cap['idle_row'] is None:
        return NODATA, 'no MEMS lane in the scan', lim, '\n'.join(ev)

    if not cap['testnodes'] or not rails:
        missing = []
        if not rails:
            missing.append('the analog rails (AN_EN = %s; a dispatched session may not raise '
                           'it -- bench note 19 / S49-15)' % an.split('//')[0].strip())
        if not cap['testnodes']:
            missing.append('a DSP4_TEST_NODES=1 pair (TEST_OSC\'s injection hook is inside '
                           'that guard; the staged pair is the shipping pair)')
        return (NODATA,
                'route asserted and read back; waiting on %s' % ' and '.join(missing),
                lim,
                '\n'.join(ev) + '\nPREREQUISITE: ' + '; '.join(missing)
                + '. The route itself is not a prerequisite any more -- it is written above '
                  'and read back above. What is left is a stimulus and a powered analog path.')

    ev.append('--- oscillator on ---\n%s' % cap['osc_on'])
    ev.append('--- MEMS lane, tone on ---\n%s' % (cap['tone_row'] or 'gone from the scan'))
    ev.append('--- oscillator off ---\n%s' % cap['osc_off'])
    ev.append('--- MEMS lane, tone off ---\n%s' % (cap['back_row'] or 'gone from the scan'))
    idle, tone, back = cap['idle'], cap['tone'], cap['back']
    if idle is None or tone is None or back is None:
        return NODATA, 'the scan did not give an rms for every leg', lim, '\n'.join(ev)
    rise, ret = tone - idle, back - idle
    m = 'idle %.2f dBFS, tone %.2f dBFS (+%.2f dB), back %.2f dBFS (%+.2f dB)' \
        % (idle, tone, rise, ret, back, ret)
    ok = rise >= _SPKR_MARGIN_DB and ret <= _SPKR_RETURN_DB
    return (PASS if ok else FAIL), m, lim, '\n'.join(ev)


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
    r.rsh("mkdir -p %s && cp %s/candidate-s82/chip1.ldr %s/candidate-s82/chip2.ldr "
          "%s/candidate-s82/chip1.sym.json %s/candidate-s82/chip2.sym.json %s/"
          % (s, DSPBOOT, DSPBOOT, DSPBOOT, DSPBOOT, s), timeout=120)
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
    return r.out('ls -l %s | head -20; md5sum %s/chip1.ldr %s/chip2.ldr' % (s, s, s))


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
    r.pin('%d ip pu' % CS_M_GPIO)
    notes.append('CS_M: %s' % r.out('pinctrl get %d' % CS_M_GPIO))
    notes.append('AN_EN: %s' % r.an_en())
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
    with open(path, newline='') as fh:
        for i, row in enumerate(csv.DictReader(fh), start=1):
            have.add((row['board'], row['item']))
            n = (row.get('num') or '').strip()
            if n:
                numbered = True
                if n != str(i):
                    sys.exit('ERROR: %s: num %r is not the row position %d (%s | %s)'
                             % (path, n, i, row['board'], row['item']))
            by_num[i] = (row['board'], row['item'])
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
            r.run('MM1', lambda: t_mm1(r))
            r.run('SP1', lambda: t_sp1(r))
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
