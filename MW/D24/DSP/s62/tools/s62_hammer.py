#!/usr/bin/env python3
"""s62_hammer.py — reproduce the S61 overlap stall on purpose (S62 gate 1).

Bulk-reads a static region of chip 1 back to back with a SHORT post-stream wait
(env POST, seconds; S61 failed once at 0.004) until a read fails, then records
what the link looks like at that moment and how long it takes to come back:

  * RDY (GPIO 8) duty over 50 ms
  * raw MISO of 12 MAGIC ask/collect pairs, searched for MAGIC at EVERY BIT
    offset of the concatenated stream (word-, byte- or bit-slipped?)
  * then one phasing attempt per second (DiagLink.calibrate) until it
    answers or LIMIT s pass, with a raw window logged every 10 s
  * after recovery: the SPI2 diag registers, the partial-request counters and
    the bulk counters

Env: POST (0.004), N (2000), LEN (16384), SYM (_spi_dispatch_c1_spms),
     STOP (1 = stop at the first failure), LIMIT (240), HZ (10e6),
     STRAT (none | bytes: on a failure try 1..3-byte realigns first).
Log: /home/app/s62/s62_hammer.jsonl"""
import json, os, sys, time
sys.path.insert(0, '/home/app/s62'); sys.path.insert(0, '/home/app/dspboot')
_argv = list(sys.argv); sys.argv = ['s']
import dsp4_scope as S                                   # noqa: E402
import dsp4_bulk as B                                    # noqa: E402
from dsp4_diag import frame                              # noqa: E402
sys.argv = _argv

LOG = os.environ.get('LOG', '/home/app/s62/s62_hammer.jsonl')
POST = float(os.environ.get('POST', '0.004'))
N = int(os.environ.get('N', '2000'))
LEN = int(os.environ.get('LEN', '16384'))
SYM = os.environ.get('SYM', '_spi_dispatch_c1_spms')
STOP = os.environ.get('STOP', '1') == '1'
LIMIT = float(os.environ.get('LIMIT', '240'))
HZ = int(float(os.environ.get('HZ', '10e6')))
STRAT = os.environ.get('STRAT', 'none')
# HOT = ms of back-to-back NOP transactions (no RDY wait, no sleep) clocked
# right after the stream, so the tick's port hand-back (1-3 ms after the last
# clock) lands INSIDE host traffic instead of by chance. 0 = stock timing.
HOT = float(os.environ.get('HOT', '0'))
HOTN = []
# HOTRDY = ms of NOP transactions that each honour SPI_RDY (link.xfer waits
# for it) clocked across the hand-back on a HANDSHAKE image, before the
# host's own low-then-high wait: a host that obeys RDY but not the rule.
HOTRDY = float(os.environ.get('HOTRDY', '0'))
# HOTRAW = the same but raw CS/xfer2 with NO RDY wait: a host that ignores
# the handshake altogether. Only the firmware's TUR guard protects it.
HOTRAW = float(os.environ.get('HOTRAW', '0'))
MAGIC = 0xD5B40001


def log(rec):
    rec['t'] = round(time.time(), 3)
    with open(LOG, 'a') as f:
        f.write(json.dumps(rec) + '\n')
    print(json.dumps(rec), flush=True)


def rdy_duty(link, ms=50):
    hi = n = 0
    end = time.time() + ms / 1000.0
    while time.time() < end:
        hi += link.rdy.get_value(); n += 1
    return round(hi / max(n, 1), 3), n


def raw_probe(link, pairs=12):
    """Ask MAGIC / collect with NOP, no RDY wait on a stuck line, raw bytes."""
    rx = b''
    ask = frame(0xE000, 0, read=True)
    nop = frame(0xE0FE, 0)
    for _ in range(pairs):
        for buf in (ask, nop):
            link.line.set_value(0)
            try:
                rx += bytes(link.spi.xfer2(list(buf)))
            finally:
                link.line.set_value(1)
            time.sleep(0.002)
    bits = int.from_bytes(rx, 'big')
    nb = 8 * len(rx)
    offs = []
    for o in range(nb - 31):
        if (bits >> (nb - 32 - o)) & 0xFFFFFFFF == MAGIC:
            offs.append(o)
    ask0 = int.from_bytes(ask[:4], 'big')
    eoffs = [o for o in range(nb - 31) if (bits >> (nb - 32 - o)) & 0xFFFFFFFF == ask0]
    return {'hex': rx[:48].hex(), 'magic_bit_offsets': offs[:12],
            'magic_mod32': sorted(set(o % 32 for o in offs)),
            'echo_mod32': sorted(set(o % 32 for o in eoffs)), 'n_echo': len(eoffs)}


def diag_regs(sc):
    out = {}
    for name, a in (('SPI_RX_COUNT', 0xE00B), ('SPI_ERR_COUNT', 0xE00C), ('SPI_STAT', 0xE00D),
                    ('SPI_STAT_STK', 0xE00E), ('RESP_DROP', 0xE00F), ('SPI_CTL', 0xE014),
                    ('SPI_RXCTL', 0xE015), ('SPI_TXCTL', 0xE016),
                    ('BULK_CTL', B.A_CTL), ('RUNS', B.A_RUNS), ('ABORT', B.A_ABORT), ('ERR', B.A_ERR),
                    ('DSTAT', B.A_DSTAT), ('MS', B.A_MS)):
        try:
            v = sc.rd_counter(a) if name in ('SPI_RX_COUNT', 'PART_SEEN', 'PART_SKIP') else sc.rd(a)
            out[name] = '0x%08X' % v if name.startswith('SPI_') and 'COUNT' not in name or name == 'DSTAT' else v
        except (IOError, OSError) as e:
            out[name] = 'ERR %s' % str(e)[:60]
    for sym in ('_spi_partial_fix', '_spi_partial_ticks', '_spi_partial_rxmark'):
        if sym in sc.sym:
            try:
                out[sym] = sc.peek(sc.sym[sym])
            except (IOError, OSError) as e:
                out[sym] = 'ERR %s' % str(e)[:60]
    return out


def stream_words(link, pairs=4):
    out = []
    for _ in range(pairs):
        for a, r in ((0xE000, True), (0xE0FE, False)):
            rx = link.xfer(a, 0, read=r)
            out += ['%08x' % int.from_bytes(rx[:4], 'big'), '%08x' % int.from_bytes(rx[4:], 'big')]
    return ' '.join(out)


def verified(sc):
    """The real reader: calibrate, then MAGIC and CHIP_ID must both read right."""
    try:
        sc.d.phase = None
        ph = sc.d.calibrate(tries=1)
        m = sc.d.read(0xE000)
        c = sc.d.read(0xE001)
        return (m == MAGIC and c == 1), '%s m=%08x c=%d' % (ph, m, c)
    except (IOError, OSError) as e:
        return False, 'ERR ' + str(e)[:50]


def tight(link, pairs=40):
    """Back-to-back ask MAGIC / collect NOP with the normal RDY wait and no
    sleep -- traffic that keeps FIX2's gate shut. Returns how many collect
    windows carried MAGIC with the echo, and the raw head."""
    ask = frame(0xE000, 0, read=True)
    ask0 = int.from_bytes(ask[:4], 'big')
    good = 0
    raw = b''
    for _ in range(pairs):
        link.xfer(0xE000, 0, read=True)
        rx = link.xfer(0xE0FE, 0)
        raw += rx
        w0, w1 = int.from_bytes(rx[:4], 'big'), int.from_bytes(rx[4:], 'big')
        if (w1 == ask0 and w0 == MAGIC) or (w0 == ask0 and w1 == MAGIC):
            good += 1
    return good, raw[:32].hex()


STUDY = []
STATS = {}


def summ(v):
    v = sorted(x for x in v if x is not None)
    if not v:
        return None
    return {'n': len(v), 'min': v[0], 'med': v[len(v) // 2], 'p99': v[min(len(v) - 1, int(len(v) * 0.99))], 'max': v[-1]}


def stuck_study(sc):
    link = sc.d.link
    g, h = tight(link)
    if g >= 30:
        return
    rec = {'ev': 'stuck_study', 'initial': (g, h), 'steps': []}
    t0 = time.time()
    if os.environ.get('STUDY') == 'full':
        rec['stream0'] = stream_words(link)
        for step in ('none', 'none', 'realign1w', 'none', 'realign1w', 'realign1w', 'pause10ms', 'none'):
            if step == 'realign1w':
                link.realign(4)
            elif step.startswith('pause'):
                time.sleep(0.010)
            ok, why = verified(sc)
            rec['steps'].append((step, round(time.time() - t0, 3), ok, why, stream_words(link, 2)))
            if ok:
                break
        STUDY.append(rec)
        log(rec)
        return
    if os.environ.get('STUDY') == 'calib':
        for k in range(8):
            try:
                sc.d.phase = None
                ph = sc.d.calibrate(tries=1)
                g, h = tight(link)
                rec['steps'].append(('calib1', round(time.time() - t0, 3), ph, g, h))
                if g >= 30:
                    break
            except (IOError, OSError):
                g, h = tight(link, 4)
                rec['steps'].append(('calib1_fail', round(time.time() - t0, 3), g, h))
        STUDY.append(rec)
        log(rec)
        return
    for step in ('tight', 'realign4', 'tight', 'realign4', 'realign1', 'realign2', 'realign3',
                 'pause2ms', 'pause10ms', 'pause50ms', 'tight'):
        if step.startswith('realign'):
            link.realign(int(step[7:]))
        elif step.startswith('pause'):
            time.sleep(float(step[5:-2]) / 1000.0)
        g, h = tight(link)
        rec['steps'].append((step, round(time.time() - t0, 3), g, h))
        if g >= 30 and step != 'tight':
            break
    STUDY.append(rec)
    log(rec)


def recover(sc, t_fail):
    link = sc.d.link
    t_next_raw = 0
    tries = 0
    while time.time() - t_fail < LIMIT:
        tries += 1
        el = time.time() - t_fail
        if el >= t_next_raw and STRAT != 'pause':
            log({'ev': 'stuck_raw', 'el_s': round(el, 2), 'rdy': rdy_duty(link, 20), **raw_probe(link, 4)})
            t_next_raw += 10
        if STRAT == 'pause':
            for k in range(50):
                time.sleep(0.010)
                ok, why = verified(sc)
                if ok:
                    return k + 1, 'pause10ms x%d (%s) in %.3f s' % (k + 1, why, time.time() - t_fail)
            continue
        if STRAT == 'bytes':
            for nb in (0, 1, 2, 3, 4, 5, 6, 7):
                try:
                    if nb:
                        link.realign(nb)
                    sc.d.phase = None
                    sc.d.calibrate(tries=1)
                    return tries, 'bytes%d' % nb
                except (IOError, OSError):
                    pass
        else:
            try:
                sc.d.phase = None
                sc.d.calibrate(tries=1)
                return tries, 'calibrate'
            except (IOError, OSError):
                pass
        time.sleep(1.0)
    return tries, None


def main():
    B.POST_S = POST
    if HOTRDY > 0 or HOTRAW > 0:
        _orig_w = B._wait_rdy
        nop = list(frame(0xE0FE, 0))

        def _hot_wait(link, level, timeout=B.RDY_TIMEOUT_S):
            if level == 0:
                end = time.time() + max(HOTRDY, HOTRAW) / 1000.0
                k = 0
                while time.time() < end:
                    if HOTRAW > 0:
                        link.line.set_value(0)
                        try:
                            link.spi.xfer2(nop)
                        finally:
                            link.line.set_value(1)
                    else:
                        try:
                            link.xfer(0xE0FE, 0)
                        except TimeoutError:
                            pass
                    k += 1
                HOTN.append(k)
            return _orig_w(link, level, timeout)
        B._wait_rdy = _hot_wait
    if HOT > 0:
        _orig = B._resync

        def _hot_resync(sc_):
            link = sc_.d.link
            nop = list(frame(0xE0FE, 0))
            end = time.time() + HOT / 1000.0
            k = 0
            while time.time() < end:
                link.line.set_value(0)
                try:
                    link.spi.xfer2(nop)
                finally:
                    link.line.set_value(1)
                k += 1
            HOTN.append(k)
            if os.environ.get('PROBE') == '1':
                stuck_study(sc_)
            return _orig(sc_)
        B._resync = _hot_resync
    sc = S.Scope(1, symfile='/home/app/s62/chip1.sym.json')
    sc.check_chip()
    addr = sc.addr(SYM)
    r0 = diag_regs(sc)
    log({'ev': 'start', 'post': POST, 'n': N, 'len': LEN, 'sym': SYM, 'hz': HZ, 'strat': STRAT, 'regs': r0})
    ref = None
    if os.environ.get('REFPEEK') == '1':
        t_ref = time.time()
        ref = [sc.peek(addr + k) for k in range(LEN)]
        log({'ev': 'ref_peek', 'len': LEN, 's': round(time.time() - t_ref, 1),
             'nonzero': sum(1 for v in ref if v), 'sum': '%08x/%08x' % B.sums(ref)})
    ok = fails = odd = 0
    t_start = time.time()
    for i in range(N):
        t0 = time.time()
        try:
            w, info = B.read(sc, addr, LEN, hz=HZ, tries=1)
        except Exception as e:                      # noqa: BLE001
            t_fail = time.time()
            fails += 1
            link = sc.d.link
            snap = {'ev': 'fail', 'i': i, 'post': POST, 'dt_s': round(t_fail - t0, 3),
                    'err': str(e)[:300]}
            if STRAT != 'pause':
                snap['rdy'] = rdy_duty(link)
                snap.update(raw_probe(link))
            log(snap)
            tries, how = recover(sc, t_fail)
            t_rec = time.time()
            log({'ev': 'recovered' if how else 'not_recovered', 'i': i, 'after_s': round(t_rec - t_fail, 2),
                 'tries': tries, 'how': how,
                 'regs': (diag_regs(sc) if STRAT != 'pause' else {'_spi_partial_fix': sc.peek(sc.sym['_spi_partial_fix'])}) if how else None})
            if STOP or not how:
                break
            continue
        for a in info['attempts']:
            for k in ('go_ack_ms', 'release_ms', 'rephase_s'):
                if k in a:
                    STATS.setdefault(k, []).append(a[k])
            if a.get('release_low_unseen'):
                STATS['low_unseen'] = STATS.get('low_unseen', 0) + 1
            if a.get('rephase_s'):
                log({'ev': 'repaired', 'i': i, 'attempt': a})
            if 'rdy_release' in a or 'fail' in a:
                log({'ev': 'slip', 'i': i, 'attempt': a})
        if len(info['attempts']) > 1:
            STATS['retries'] = STATS.get('retries', 0) + len(info['attempts']) - 1
        STATS.setdefault('read_s', []).append(info.get('read_s'))
        if ref is None:
            ref = w
        nd = sum(1 for u, v in zip(w, ref) if u != v)
        if nd:
            odd += 1
            log({'ev': 'diff', 'i': i, 'ndiff': nd})
        ok += 1
        if i % 100 == 99:
            log({'ev': 'progress', 'i': i + 1, 'ok': ok, 'fails': fails, 'diff': odd,
                 'el_s': round(time.time() - t_start, 1), 'last': info['attempts'][-1],
                 'hot_n': (min(HOTN), max(HOTN)) if HOTN else None})
    tur = sc.peek(sc.sym['_bulk_tur_holds']) if '_bulk_tur_holds' in sc.sym else None
    log({'ev': 'stats', 'retries': STATS.get('retries', 0), 'low_unseen': STATS.get('low_unseen', 0),
         'tur_holds': tur, 'hot_n': summ(HOTN) if HOTN else None,
         **{k: summ(v) for k, v in STATS.items() if isinstance(v, list)}})
    log({'ev': 'end', 'post': POST, 'ok': ok, 'fails': fails, 'diff': odd,
         'el_s': round(time.time() - t_start, 1), 'regs': diag_regs(sc)})


if __name__ == '__main__':
    main()
