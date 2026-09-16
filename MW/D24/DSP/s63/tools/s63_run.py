#!/usr/bin/env python3
"""s63_run.py — S63 gain-change artefacts on one mic channel, or hands-free on all 16 (PW moves the loop cable).

Loop: TEST_OSC on donor strip 6 -> AUX 1 (J45) -> loop cable -> J2x/J3x -> preamp -> lane -> TEST_MEAS capture arm.
For every transition, a 16,384-sample capture (341 ms) that SPANS the change, made ~100 ms in (s63lib.Rig.span), in
two stimulus passes:
  silent  TEST_OSC off: the source is the loop cable into the AUX 1 output stage (no 150 ohm): the artefact alone
  tone    1 kHz, level so the louder side of the transition sits at HEAD (-8) dBFS pk at the ADC and at the lane
Transitions, walked so each one starts where the last one ended (SETTLE s after the last change of any kind):
  null    no change, code 0 and code 63 (the analysis's own false-positive floor)
  hw_up / hw_dn   every consecutive pair of the table's 25 hardware steps, trim 0 dB   (48)
  bit     31<->32, 15<->16, 7<->8, 3<->4, 1<->2, 0<->1, trim 0 dB                   (12)
  trim    Gain001 0 -> +1/+3/+6/+12 dB and back at code 0, GainFast ramp             (8)
  combo   target 30 dB (code 6, trim 0.315) <-> 31 dB (code 7, trim 0.401): code latch, then the trim write  (2)
Raw captures -> DATA/<XLR>.bin (int32 LE, Q4.28) + DATA/<XLR>.jsonl (one record per capture, with bin_off);
analysis on the desk (s63_analyse.py).

  CHAN=J25 python3 s63_run.py          one channel, the cable is known to be there (no WATCH)
  python3 s63_run.py                   WATCH (S55 lane detection) -> channel -> PROMPT "move the cable" -> WATCH ...
  env: DONE=J25,...  STIMS=silent,tone  KINDS=null,hw_up,hw_dn,bit,trim,combo  SETTLE=3.0  HEAD=-8  AT=4800
AN_EN (GPIO 26) is read before every channel and never written."""
import json, os, subprocess, sys, time
import s63lib as S
import s55_run as S55R          # its dsp4_meascap import resolves to the s63 module already loaded by s63lib
T, X = S.T, S.X

SETTLE = float(os.environ.get('SETTLE', '3.0'))
HEAD = float(os.environ.get('HEAD', '-8'))
AT = int(os.environ.get('AT', '4800'))
STIMS = os.environ.get('STIMS', 'silent,tone').split(',')
KINDS = os.environ.get('KINDS', 'null,hw_up,hw_dn,bit,trim,combo').split(',')
TC = S.TABLE_CODES


def transitions():
    """(kind, (code, trim_db) from, (code, trim_db) to), in walking order"""
    out = [('null', (0, 0.0), (0, 0.0))]
    out += [('hw_up', (a, 0.0), (b, 0.0)) for a, b in zip(TC, TC[1:])]
    out += [('null', (63, 0.0), (63, 0.0))]
    out += [('hw_dn', (b, 0.0), (a, 0.0)) for a, b in reversed(list(zip(TC, TC[1:])))]
    for a, b in ((31, 32), (15, 16), (7, 8), (3, 4), (1, 2), (0, 1)):
        out += [('bit', (a, 0.0), (b, 0.0)), ('bit', (b, 0.0), (a, 0.0))]
    for d in (1.0, 3.0, 6.0, 12.0):
        out += [('trim', (0, 0.0), (0, d)), ('trim', (0, d), (0, 0.0))]
    out += [('combo', (6, 0.315), (7, 0.401)), ('combo', (7, 0.401), (6, 0.315))]
    return [t for t in out if t[0] in KINDS]


class Rig(S.Rig):
    # S55's lane detection and donor handling, on this rig
    scan = S55R.S55.scan
    set_donor = S55R.S55.set_donor
    strip_save = S55R.S55.strip_save
    strip_restore = S55R.S55.strip_restore
    an_en = S55R.S55.an_en

    def __init__(self):
        super().__init__(S.HOME + '/s63_run.jsonl')
        self.donor = 6
        self.saved = {}

    def osc(self, freq=None, level_db=None, on=True, chan=None):
        return T.Rig.osc(self, freq, level_db, on, chan=self.donor if chan is None else chan)

    def image(self, code):
        img = list(self.base)
        if self.p is not None:
            img[self.p] = S.byte(gain=code)
        return img


def change_fn(R, frm, to):
    code_ch, trim_ch = frm[0] != to[0], abs(frm[1] - to[1]) > 1e-9
    img = R.image(to[0])
    w = X.f32(10 ** (to[1] / 20.0))

    def f():
        ev = {}
        if code_ch:
            ok, got, a, b = S.chain_send_timed(img, fix_cs=not trim_ch)
            ev.update({'t_latch_lo': a, 't_latch_hi': b, 'chain_verified': ok})
        if trim_ch:
            t0 = time.time()
            try:
                R.sc.d.link.write(R.gain_addr, w, 1)
                ev['write_err'] = None
            except (IOError, OSError) as e:
                ev['write_err'] = str(e)
            ev.update({'t_write_lo': t0, 't_write_hi': time.time()})
            if code_ch:
                subprocess.run(['sudo', 'pinctrl', 'set', '6,24', 'op', 'dh'], check=True)
        return ev
    return f


def run_channel(R, xlr, p, lane):
    G = S.loop_gain(xlr)
    R.select(xlr, p, lane)
    R.meas(lane)
    R.set_code(0)
    R.set_trim(0.0)
    # presence: 1 kHz on the donor, the lane's coherent loop gain at code 0 must be the law's
    R.tone(-20.0)
    R.freq, R.level_db = 1000.0, -20.0
    m = R.windows(3, settle_windows=4, tag=xlr + ':presence')
    g0 = T.summ(m, 'H_db')
    S.P('%s presence: code 0 coherent loop gain %+.3f dB (S55 law %+.3f)' % (xlr, g0, G[0]))
    T.log({'ev': 'presence', 'xlr': xlr, 'g0': g0, 'law0': G[0]})
    if g0 is None or abs(g0 - G[0]) > 3.0:
        raise S55R.Abort('presence: coherent gain %s dB, law %.2f' % (g0, G[0]))
    tr = transitions()
    n_done = 0
    t_ch = time.time()
    for stim in STIMS:
        for kind, frm, to in tr:
            if R.code != frm[0]:
                R.set_code(frm[0])
            if R.trim_db is None or abs(R.trim_db - frm[1]) > 1e-9:
                R.set_trim(frm[1])
            lvl = None
            if stim == 'tone':
                lvl = HEAD - max(G[frm[0]] + frm[1], G[to[0]] + to[1])
            R.tone(lvl)
            wait = SETTLE - (time.time() - R.t_change)
            if wait > 0:
                time.sleep(wait)
            settled = time.time() - R.t_change
            rec, vals = R.span(change_fn(R, frm, to), at=AT)
            rec.update({'xlr': xlr, 'p': p, 'lane': lane, 'stim': stim, 'kind': kind, 'from': frm, 'to': to,
                        'osc_dbfs_pk': lvl, 'law_from': G[frm[0]], 'law_to': G[to[0]], 'settled_s': round(settled, 2),
                        't_wall': round(time.time(), 3)})
            # the part must now be in the TO state, verified; if not, the record is marked and the state forced
            bad = []
            if frm[0] != to[0]:
                R.code = to[0]
                R.t_change = time.time()
                if not rec.get('chain_verified'):
                    bad.append('chain not verified')
                    R.set_code(to[0])
            if abs(frm[1] - to[1]) > 1e-9:
                R.trim_db = to[1]
                R.t_change = time.time()
                if rec.get('write_err') or R.rd(R.gain_addr) != X.f32(10 ** (to[1] / 20.0)):
                    bad.append('trim write %s' % (rec.get('write_err') or 'did not land'))
                    R.set_trim(to[1])
            rec['invalid'] = bad or None
            S.save(vals, rec, xlr)
            ev = rec.get('s_latch_lo', rec.get('s_write_lo', AT))
            pre, post = S.quick(vals, ev)
            n_done += 1
            S.P('%s %-6s %-6s %s -> %s  change @ %s  pk pre %.1f / post %.1f dBFS  ovr %d  map %s  %s' % (
                xlr, stim, kind, frm, to, ev, pre, post, rec['overruns'], rec['map_resid_samples'],
                'INVALID %s' % bad if bad else ''))
    T.log({'ev': 'channel_captures', 'xlr': xlr, 'n': n_done, 'wall_s': round(time.time() - t_ch, 1)})
    S.P('%s: %d captures in %.1f min' % (xlr, n_done, (time.time() - t_ch) / 60))


def main():
    R = Rig()
    ok, pin = R.an_en()
    S.P('AN_EN: %s' % pin)
    if not ok:
        raise SystemExit('AN_EN is LOW: analog off — blocked (never written by this session)')
    only = os.environ.get('CHAN')
    done = set(a for a in os.environ.get('DONE', '').split(',') if a)
    R.saved[6] = R.strip_save(6)
    T.log({'ev': 'start', 'chan': only, 'done': sorted(done), 'settle': SETTLE, 'head': HEAD, 'at': AT,
           'stims': STIMS, 'kinds': KINDS, 'an_en': pin})
    R.select('base', None, S.D24.MIC5_STRIP)
    R.set_code(0)
    S.P('base image VERIFIED; strips on AUX 1: %s' % R.set_donor(6))
    chans = {c[0]: c for c in S55R.CHANNELS}
    while True:
        if only:
            ch = chans[only]
        else:
            ch = S55R.watch(R, done)
        xlr, p, lane, panel = ch
        ok, pin = R.an_en()
        if not ok:
            raise SystemExit('AN_EN went LOW — blocked')
        saved = R.strip_save(lane)
        T.log({'ev': 'channel_start', 'xlr': xlr, 'lane': lane, 'saved': saved})
        try:
            if lane == 6:
                R.set_donor(1)
            X.strip_unity(R.c1, lane)
            run_channel(R, xlr, p, lane)
            done.add(xlr)
            T.log({'ev': 'channel_done', 'xlr': xlr})
        except S55R.Abort as e:
            T.log({'ev': 'abort', 'xlr': xlr, 'why': str(e)})
            S.P('%s ABORTED: %s — nothing recorded as done' % (xlr, e))
        finally:
            R.osc(on=False)
            R.select('base', None, lane)
            R.set_code(0)
            R.strip_restore(lane, saved)
            if R.donor != 6:
                R.set_donor(6)
            R.meas(S.D24.MIC5_STRIP)
        if only:
            break
        if xlr in done:
            S55R.PROMPT('%s (%s) DONE — move the loop cable to the next XLR' % (xlr, panel))
        if len(done) >= len(S55R.CHANNELS):
            S.P('all %d channels done' % len(done))
            break


if __name__ == '__main__':
    main()
