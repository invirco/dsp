#!/usr/bin/env python3
"""dsp4_conform.py — the CONTRACT CONFORMANCE HARNESS, on the live part.

The masters document a control surface. The DSP implements one. Nothing
in this tree ever checked that they are the same surface: every existing
instrument measures the kernel against ITSELF (asm vs asm, build vs
build, capture vs stored capture), so a cell that has been addressed to
the wrong variable, or is served in the wrong unit, or does nothing at
all, reproduces its own goldens perfectly.

This asks the other question. For every address the DSP will answer on:

  PRESENCE  write it over the live SPI plane at the values the masters
            document as its boundaries, and read it back through the
            protocol's own read path. Four verdicts, and only the first
            is silence: ECHO (the word lands and reads back), VOLATILE
            (the kernel overwrites it -- a device->host cell), REJECTED
            (the write does not take) and UNMAPPED (the dispatch table
            has no target). The verdict is compared against what the
            TREE predicts from the dispatch table: a disagreement is
            drift between the image on the part and the source, which is
            the one thing a self-referential golden can never catch.

  EFFECT    for families whose unit is DECLARED in wire-units.csv, write
            the documented value and require the documented consequence
            -- the coefficient the kernel derives, in the Q format the
            numeric spec names, computed from the documented unit. This
            is where a dB-vs-linear or percent-vs-fraction mismatch
            fails, by arithmetic, with the wrong answer printed next to
            the right one.

  INERT     a write that changes nothing kernel-visible. The static side
            (tools/dsp/wire_contract.py) finds the candidates by asking
            which dispatch targets no emitted line reads; this confirms
            them on the part, against a POSITIVE CONTROL -- the same
            procedure on a wired cell must show a difference, or the
            probe is measuring nothing and every cell would look inert.

NEGATIVE CONTROLS ARE PART OF THE RUN, not a separate exercise:

  --negctl-unit   corrupts one semantic expectation the way a wrong
                  wire-units.csv row would (dB read as linear). That
                  cell MUST fail. A harness whose expectations cannot
                  fail is a harness that proves nothing.
  --no-verify     writes without reading back. Every cell touched in
                  that mode must come out UNVERIFIED, never PASS -- the
                  run is required to KNOW it did not check.

Usage (staged by MW/D32/DSP/SHARC/conform.sh):
    dsp4_conform.py --plan plan.json --chip 1 --out conform_c1.json
    dsp4_conform.py --plan plan.json --chip 1 --phase effect --out e1.json
    dsp4_conform.py --plan plan.json --chip 1 --negctl-unit ChanGateRng ...
"""

import argparse
import json
import os
import re
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, '/home/app/dspboot')

import dsp4_scope as S                                       # noqa: E402
from dsp4_diag import MAGIC_VALUE                            # noqa: E402

try:
    from dsp4_block import BLOCK
except ImportError:                     # never guess the block size: the
    BLOCK = None                        # ballistics constants depend on it

FS = 48000.0

RAMP_ID = {'': 0, 'InstantCtl': 0, 'GainFast': 1, 'GainSafe': 2,
           'EqSafe': 3, 'DynSafe': 4}

Q28 = 1 << 28
Q31 = 1 << 31


def f32(x):
    return struct.unpack('<I', struct.pack('<f', float(x)))[0]


def from_f32(w):
    return struct.unpack('<f', struct.pack('<I', w & 0xFFFFFFFF))[0]


# ---------------------------------------------------------------------------
# Probe words — what it is SAFE and MEANINGFUL to write at an address
# ---------------------------------------------------------------------------
#
# The dispatch table's own comment says what the kernel keeps at each
# address, and that is the only thing in the tree that knows whether a
# word is a float coefficient or an integer index. It matters: the
# masters document Chan001Delay001 in MILLISECONDS and the kernel keeps
# raw SAMPLES there (review finding D41), so writing the documented
# 250.0 as float32 puts 0x437A0000 = 1,132,462,080 into a delay-line
# index. That is a real finding and it is recorded as one -- but it is
# not something to discover by scribbling over the pool at 6752
# addresses, so the integer classes are probed inside their own range
# and the run says so rather than quietly narrowing its own coverage.

_INT_NOTE = re.compile(
    r'\b(On|Type|Key|DetSrc|LimMode|EqPos|Shelf|swap trigger|pool_slot|'
    r'source_count|bus_id|delay offset|input_sel|phantom|InputSel|Knee|'
    r'mute|polarity|Sel|Mode|Slope)\b', re.I)
_BOUNDED_NOTE = re.compile(r'\b(delay offset|pool_slot|source_count|bus_id)\b',
                           re.I)
# NOTE THE ABSENCE OF WORD BOUNDARIES ON THE NODE FORM. Chip 1's meter
# comments name the tap (post_trim, post_fader); chip 2's name the node
# (C2_MTR_AUX_01), and `\bMtr\b` does not match inside MTR_AUX because
# the underscore is a word character. The first chip-2 sweep therefore
# probed 27 meter addresses as if they were parameters and reported them
# as unsettled reads -- the harness misclassifying, not the part.
_METER_NOTE = re.compile(r'(post_trim|post_fader|post_eq|pre_fader|'
                         r'gate_gr|comp_gr|_MTR_|\bMtr\b|\bmeter\b)', re.I)


def probes(entry):
    """(words, kind, bounded) for one address."""
    note = entry['kernel_note']
    if _METER_NOTE.search(note):
        return [], 'meter', False
    if _BOUNDED_NOTE.search(note):
        # Integer index into a pool, a list or a bus. Probed at 0 and 1
        # only; the documented full range is NOT written, because at this
        # address the documented unit is not what the kernel keeps.
        return [0, 1], 'int', True
    if _INT_NOTE.search(note):
        return [0, 1], 'int', False
    vals = entry.get('boundaries') or []
    vals = [v for v in vals if v == v and abs(v) != float('inf')]
    if vals:
        return [f32(v) for v in vals], 'float', False
    return [f32(0.0), f32(0.5), f32(1.0)], 'float', False


# ---------------------------------------------------------------------------
# The link
# ---------------------------------------------------------------------------

class Part:
    def __init__(self, chip, tries=8):
        self.sc = S.Scope(chip)
        self.chip = chip
        self.reboots = 0
        # READINESS IS THIS TOOL'S OWN JOB, not the shell script's.
        # dsp4_diag.py's unpaced reader routinely cannot answer at all on
        # a link that has been through a boot and a config -- it reported
        # "CONFIG_COMMIT DID NOT LAND" on a part that was at BOOT_STAGE 7
        # with PRODUCT_ID correct, because it read through a stream that
        # was a word out of phase. Gating the harness on that instrument
        # threw away five perfectly good boots. The paced, voted reader
        # answers the same part first time, so the gate lives here.
        last = None
        for _ in range(tries):
            try:
                self.sc.d.resync()
                self.sc.check_chip()
                if self.sc.rd(0xE002) >= 6:
                    return
                last = 'BOOT_STAGE below 6'
            except (IOError, SystemExit) as exc:
                last = str(exc)
            time.sleep(0.5)
        raise SystemExit(f'chip {chip} not ready after {tries} attempts: {last}')

    def frames(self):
        """FRAME_COUNT, read UNVOTED because it is a moving value.

        Scope.rd votes, and a counter advancing at the block rate never
        returns the same word twice -- it throws instead of answering, so
        a healthy running part reads as a dead link. This is the same
        reason Scope.wait() polls the sample index unvoted.
        """
        for _ in range(20):
            v = self.sc._ask(0xE004)
            if v:
                return v
        return None

    def healthy(self):
        try:
            if self.sc.rd(0xE000) != MAGIC_VALUE:
                return False
            if self.sc.rd(0xE002) < 6:
                return False
            f0 = self.frames()
            time.sleep(0.05)
            f1 = self.frames()
            # FRAME_COUNT must be MOVING. A part that is answering the
            # diag link while its block loop has stopped reads healthy on
            # every static register, and every verdict taken after that
            # point is a verdict about a stopped graph.
            return f0 is not None and f1 is not None and f1 != f0
        except IOError:
            return False

    def read(self, addr):
        return self.sc.rd(addr)

    def write(self, addr, word, ramp_id=0):
        self.sc.d.link.write(addr, word & 0xFFFFFFFF, ramp_id)
        time.sleep(S.SETTLE)


# ---------------------------------------------------------------------------
# PRESENCE
# ---------------------------------------------------------------------------

SPI_ERR_COUNT = 0xE00C


def presence(part, entries, verify=True, health_every=32, log=print):
    """Write every address at its documented boundaries and read it back.

    RAMP ID 0, DELIBERATELY. The presence question is whether the word
    lands and can be read back, and the handler's instant path calls
    _ramp_set_target in Instant mode, which sets level AND target and
    clears frames -- so the read-back is immediate and exact. Writing a
    ramped profile here would instead read a moving value: the first
    pilot run turned Chan001Gain001 into a hard ERROR because the voted
    reader, correctly, refused to settle on a coefficient mid-ramp. The
    ramp PROFILES get their own check in the effect phase, where waiting
    out a documented ramp time costs three cells rather than 6752.

    THE MAPPED/UNMAPPED VERDICT COMES FROM THE PART, NOT FROM THE
    READ-BACK. An unmapped address and a mapped one whose target the
    kernel clears every block both read back 0, so a read-back alone
    cannot tell "there is nothing here" from "the kernel consumed it" --
    and the swap triggers are exactly the second case. SPI_ERR_COUNT
    settles it: spi_handler.asm increments it on the .spi_error path,
    which is reached only when the dispatch entry is 0 or the address is
    out of bounds. One counter read either side of the probe batch turns
    a guess into a measurement.
    """
    results = []
    health = []
    for i, e in enumerate(entries):
        addr = e['addr']
        words, kind, bounded = probes(e)
        rec = {'addr': addr, 'cells': e['cells'], 'families': e['families'],
               'unit': e['unit'], 'role': e['role'], 'kind': kind,
               'bounded': bounded, 'predicted_mapped': e['mapped'],
               'kernel_note': e['kernel_note'], 'ramp_id': 0,
               'verified': verify, 'probes': []}
        try:
            err0 = part.read(SPI_ERR_COUNT) if verify else None
            orig = part.read(addr) if verify else None
            rec['orig'] = orig
            writes = 0
            for w in words:
                part.write(addr, w, 0)
                writes += 1
                if not verify:
                    rec['probes'].append({'wrote': w, 'read': None,
                                          'verdict': 'UNVERIFIED'})
                    continue
                rb = part.read(addr)
                if rb == w:
                    v = 'ECHO'
                elif rb == 0:
                    v = 'ZERO'
                elif rb == orig:
                    v = 'UNCHANGED'
                else:
                    v = 'VOLATILE'
                rec['probes'].append({'wrote': w, 'read': rb, 'verdict': v})
            if orig is not None and kind != 'meter':
                part.write(addr, orig, 0)
                writes += 1
                rec['restored'] = part.read(addr) == orig
            if orig is not None:
                err1 = part.read(SPI_ERR_COUNT)
                rec['err_delta'] = (err1 - err0) & 0xFFFFFFFF
                rec['writes'] = writes
                # Every write to an unmapped address counts one error, so a
                # full batch is the signature; a partial count means some
                # writes were dropped on the link and the address cannot be
                # classified from this run.
                if writes == 0:
                    # Meter addresses are not written at all, so the error
                    # counter says nothing about them: leaving live_mapped
                    # unset keeps them out of the drift comparison instead
                    # of scoring "no error" as "mapped".
                    rec['live_mapped'] = None
                elif rec['err_delta'] == 0:
                    rec['live_mapped'] = True
                elif rec['err_delta'] == writes:
                    rec['live_mapped'] = False
                else:
                    rec['live_mapped'] = None
        except IOError as exc:
            rec['error'] = str(exc)
        rec['verdict'] = collapse(rec)
        results.append(rec)

        if health_every and i % health_every == health_every - 1:
            ok = part.healthy()
            health.append({'after_index': i, 'addr': addr, 'ok': ok})
            if not ok:
                # A wedged part is a RESULT, not a lost run: name the last
                # address touched and stop, rather than carrying on
                # producing verdicts from a graph that is no longer running.
                log(f'  part unhealthy after 0x{addr:04X} '
                    f'({",".join(rec["cells"]) or "unnamed"}) — stopping')
                rec['wedged_after'] = True
                break
    return results, health


def collapse(rec):
    if 'error' in rec:
        return 'ERROR'
    if not rec['verified']:
        return 'UNVERIFIED'
    if rec['kind'] == 'meter':
        return 'SKIPPED_METER'
    vs = [p['verdict'] for p in rec['probes']]
    if not vs:
        return 'NO_PROBE'
    mapped = rec.get('live_mapped')
    if mapped is False:
        return 'UNMAPPED'
    if mapped is None:
        return 'INDETERMINATE'
    if set(vs) == {'ECHO'}:
        return 'ECHO'
    if 'VOLATILE' in vs:
        return 'VOLATILE'
    if 'ZERO' in vs:
        # Mapped, accepted without error, and reads back zero: the kernel
        # cleared it. The coefficient-set swap triggers do exactly this
        # and it is their documented behaviour.
        return 'CLEARED'
    return 'UNCHANGED'


# ---------------------------------------------------------------------------
# EFFECT — the declared families, against the documented unit
# ---------------------------------------------------------------------------
#
# Each check writes a DOCUMENTED value and predicts the coefficient the
# kernel must hold, from the documented unit alone. The prediction is
# arithmetic, written here once; the kernel's own conversion is not
# consulted, which is the whole point -- a check that derived its
# expectation from dsp_codegen would agree with any conversion the
# codegen happened to implement, including a wrong one.

def db_to_lin(db):
    return 10.0 ** (-db / 20.0)


def alpha_ms(ms):
    """One-pole coefficient for a time constant in milliseconds.

    dynamics.asm:180-181 documents the kernel's own form, 1-exp(-1/(Fs*T)),
    and dsp_simulate.py and golden_harness.py both compute it. Nothing
    between the wire and the kernel does.
    """
    import math
    t = max(ms, 1e-6) / 1000.0
    return 1.0 - math.exp(-1.0 / (FS * t))


def _s32(v):
    return v - (1 << 32) if v & 0x80000000 else v


def q(x, bits):
    v = int(round(x * (1 << bits)))
    return max(-(1 << 31), min((1 << 31) - 1, v)) & 0xFFFFFFFF


# TOLERANCE IS RELATIVE, and deliberately loose. The contract under test
# is a UNIT, not a rounding rule: the kernel is entitled to reach the
# documented value through float32 control arithmetic and a table-driven
# exp2, whose combined error is a few parts per million. 3e-5 of full
# scale is roughly 0.0003 dB -- far looser than any conversion error and
# still seven orders of magnitude tighter than the mismatches this exists
# to catch, where a documented 40 dB arrives as a saturated coefficient.
REL_TOL = 3e-5

CHECKS = [
    # (name, family, spi offset in the strip page, symbol template,
    #  documented values, predictor, Q bits, absolute tolerance in LSB)
    ('ChanGateRng', 'ChanGateRng', 0x002D, '_gate_rngq_{gate}',
     [0.0, 20.0, 40.0, 60.0], lambda v: db_to_lin(v), 28, 2),
    ('ChanCompPar', 'ChanCompPar', 0x003F, '_comp_parq_{comp}',
     [0.0, 25.0, 50.0, 100.0], lambda v: v / 100.0, 31, 2),
    ('ChanGateAtt', 'ChanGateAtt', 0x002A, '_gate_attq_{gate}',
     [0.1, 25.0, 250.0], alpha_ms, 31, 2),
    ('ChanGateRel', 'ChanGateRel', 0x002C, '_gate_relq_{gate}',
     [50.0, 500.0, 5000.0], alpha_ms, 31, 2),
    ('ChanCompAtt', 'ChanCompAtt', 0x003B, '_comp_attq_{comp}',
     [0.5, 25.0, 250.0], alpha_ms, 31, 2),
    ('ChanCompRel', 'ChanCompRel', 0x003C, '_comp_relq_{comp}',
     [5.0, 500.0, 5000.0], alpha_ms, 31, 2),
    # Hold and delay are kept in RAW SAMPLES by the kernel (the gate's own
    # default is `.var _gate_hold_ = 2400`, which is 50 ms at 48 kHz written
    # out by hand) while the masters document milliseconds. Predicting from
    # the documented unit is the whole point: if no conversion exists, this
    # is where it shows.
    ('ChanGateHold', 'ChanGateHold', 0x002B, '_gate_hold_{gate}',
     [0.0, 50.0, 2000.0], lambda v: v * FS / 1000.0, 0, 1),
    ('ChanDelay', 'ChanDelay', 0x004E, '_dly_read_offset_{dly}',
     [0.0, 10.0, 250.0], lambda v: v * FS / 1000.0, 0, 1),
]

# Relational checks: the documented consequence is a RELATION between two
# states, not a number. A sign fold is proved by negation and a mute by an
# exact zero, and neither needs the gain value to be known.
RELATIONAL = ['ChanPol', 'ChanMute']

STRIDE = 144            # chip 1's per-strip SPI page (dsp_address_map.md)


def effect(part, strip=1, negctl_unit=None, log=print):
    """Run the declared-unit checks on one strip, from the documented unit."""
    out = []
    base = (strip - 1) * STRIDE
    nodes = {'gate': 'C1_GATE_%02d' % strip, 'comp': 'C1_COMP_%02d' % strip,
             'dly': 'C1_DLY_%02d' % strip, 'gain': 'C1_GAIN_%02d' % strip,
             'fdr': 'C1_FDR_%02d' % strip}
    # Put the strip in a state where the conversions actually run: the
    # control-rate prep is epoch-gated, and a node whose On flag is clear
    # can skip the conversion entirely.
    for off, val in ((0x0028, 1), (0x0038, 1)):
        part.write(base + off, val, 0)

    for name, family, off, symtpl, values, predict, bits, tol in CHECKS:
        # A NEGATIVE-CONTROL RUN TESTS ONE THING. Letting the other checks
        # ride along puts their results in the same file, where the scorer
        # cannot tell a control row from a real one — the first run scored
        # two ramp errors from the control file as real failures.
        if negctl_unit and family != negctl_unit:
            continue
        sym = symtpl.format(**nodes)
        if sym not in part.sc.sym:
            out.append({'check': name, 'verdict': 'NO_SYMBOL', 'symbol': sym})
            continue
        dm = part.sc.sym[sym]
        rid = 4 if 'Gate' in name or 'Comp' in name else 0
        for v in values:
            try:
                part.write(base + off, f32(v), rid)
                time.sleep(0.05)
                got = part.sc.peek(dm)
            except IOError as exc:
                out.append({'check': name, 'wrote': v, 'verdict': 'ERROR',
                            'error': str(exc)})
                continue
            pv = predict(v)
            want = q(pv, bits) if bits else int(round(pv)) & 0xFFFFFFFF
            if negctl_unit == family:
                # THE NEGATIVE CONTROL. Predict as if wire-units.csv named
                # the unit the KERNEL currently assumes instead of the one
                # the masters document -- exactly the corruption a wrong
                # row in that file would introduce. A harness that still
                # passes here is not testing the unit at all.
                want = q(v, bits) if bits else int(round(v)) & 0xFFFFFFFF
            d = min((got - want) & 0xFFFFFFFF, (want - got) & 0xFFFFFFFF)
            # per-VALUE, never accumulated across the loop: a tolerance
            # carried over from a large expectation would silently widen
            # the bar on the small ones that follow it.
            t = max(tol, int(abs(_s32(want)) * REL_TOL))
            out.append({'check': name, 'family': family, 'symbol': sym,
                        'addr': base + off, 'wrote': v, 'predicted_real': pv,
                        'expected': want, 'observed': got, 'lsb_error': d,
                        'tolerance': t, 'negctl': negctl_unit == family,
                        'verdict': 'PASS' if d <= t else 'FAIL'})
            log(f'  {name:<13} {v:>8} -> want 0x{want:08X} got 0x{got:08X} '
                f'{"PASS" if d <= t else "FAIL"}')

    if negctl_unit in (None, 'ChanPol', 'ChanMute'):
        out += relational(part, base, nodes, negctl_unit, log)
    if negctl_unit is None:
        out += ramps(part, base, log)
    return out


# The ramp profiles the masters name, with the frame counts gen_dsp.py
# generates them from (RAMP_PROFILES there). The bar is an UPPER bound:
# a write carrying the documented profile id must ARRIVE, and arrive
# inside the documented time class with margin. Measuring the ramp's
# shape needs a sampler faster than the link -- a single voted read
# costs about 10 ms against a 3 ms GainFast rise -- so the shape is not
# claimed here, only the arrival, and that is said rather than implied.
RAMP_CELLS = [
    ('Chan001Gain001', 0x0000, 1, 'GainFast', 8.0),
    ('Chan001GateThr001', 0x0029, 4, 'DynSafe', 20.0),
    ('Chan001RtgLevel001', 0x0050, 1, 'GainFast', 8.0),
]


def ramps(part, base, log=print, window_ms=400.0):
    """Does a documented ramp profile arrive, and inside its time class?

    POLLED UNVOTED. Scope.rd votes, and a value that is moving never
    returns the same word twice: the first run turned every GainFast cell
    into a hard ERROR listing twelve consecutive distinct coefficients --
    which is a picture of a ramp working, reported as a dead link. An
    unvoted ask costs about 2 ms and a dropped answer reads as 0, which
    here is simply "not arrived yet".

    The arrival time is an UPPER BOUND, not a ramp shape: one ask is
    about 2 ms against a 3 ms GainFast rise, so this can say the target
    was reached and roughly when, and it deliberately claims no more.
    """
    out = []
    for cell, off, rid, profile, ms in RAMP_CELLS:
        addr = base + off
        try:
            for target in (f32(0.25), f32(0.75)):
                part.sc.d.link.write(addr, target, rid)
                t0 = time.time()
                trace, elapsed, hits = [], None, 0
                while (time.time() - t0) * 1000.0 < window_ms:
                    v = part.sc._ask(addr)
                    trace.append([round((time.time() - t0) * 1000.0, 2), v])
                    if v == target:
                        hits += 1
                        if hits >= 2:
                            elapsed = trace[-2][0]
                            break
                    else:
                        hits = 0
                ok = elapsed is not None and elapsed <= ms * 4 + 20.0
                out.append({'check': 'ramp:' + profile, 'cell': cell,
                            'addr': addr, 'ramp_id': rid,
                            'documented_ms': ms, 'wrote': target,
                            'observed': trace[-1][1] if trace else None,
                            'arrived_ms': elapsed, 'samples': len(trace),
                            'trace': trace[:80],
                            'verdict': 'PASS' if ok else 'FAIL'})
                log(f'  ramp {profile:<9} {cell} -> '
                    + ('arrived in %.1f ms (documented %.0f)' % (elapsed, ms)
                       if elapsed is not None
                       else 'NEVER ARRIVED in %.0f ms' % window_ms))
        except IOError as exc:
            out.append({'check': 'ramp:' + profile, 'cell': cell,
                        'verdict': 'ERROR', 'error': str(exc)})
    return out


def relational(part, base, nodes, negctl_unit, log):
    """ChanPol and ChanMute: proved by relation, not by a predicted word."""
    out = []
    if negctl_unit not in (None, 'ChanPol'):
        gq = None
    else:
        gq = part.sc.sym.get('_gain_q_' + nodes['gain'])
    # THE FOLD IS IN _fdr_gq, NOT _fdr_lq. _fdr_lq/_fdr_rq are the PAN
    # legs and carry no level and no mute; the composite level x dca
    # coefficient, which is where dsp_codegen folds mute to exact zero
    # ("mute is a LINEAR gain term, so it belongs in the coefficient at
    # control rate"), is _fdr_gq. Probing the pan leg made a working mute
    # read as a contract violation on the first run — the harness being
    # wrong, not the kernel.
    lq = part.sc.sym.get('_fdr_gq_' + nodes['fdr'])


    if gq is not None:
        try:
            part.write(base + 0x0001, 0, 0)
            time.sleep(0.05)
            g0 = _s32(part.sc.peek(gq))
            part.write(base + 0x0001, 1, 0)
            time.sleep(0.05)
            g1 = _s32(part.sc.peek(gq))
            part.write(base + 0x0001, 0, 0)
            want = -g0
            if negctl_unit == 'ChanPol':
                want = g0            # negctl: polarity documented as a no-op
            ok = (g1 == want) and g0 != 0
            out.append({'check': 'ChanPol', 'family': 'ChanPol',
                        'symbol': '_gain_q_' + nodes['gain'],
                        'addr': base + 0x0001,
                        'observed': g1, 'expected': want,
                        'note': f'pol=0 gives {g0}, pol=1 must give its negation',
                        'negctl': negctl_unit == 'ChanPol',
                        'verdict': 'PASS' if ok else 'FAIL'})
            log(f'  ChanPol       pol0 {g0} pol1 {g1} '
                f'{"PASS" if ok else "FAIL"}')
        except IOError as exc:
            out.append({'check': 'ChanPol', 'verdict': 'ERROR', 'error': str(exc)})

    if negctl_unit not in (None, 'ChanMute'):
        lq = None
    if lq is not None:
        try:
            part.write(base + 0x0052, 0, 0)
            time.sleep(0.1)
            m0 = part.sc.peek(lq)
            part.write(base + 0x0052, 1, 0)
            time.sleep(0.1)
            m1 = part.sc.peek(lq)
            part.write(base + 0x0052, 0, 0)
            ok = (m1 == 0) and (m0 != 0)
            if negctl_unit == 'ChanMute':
                ok = (m1 != 0)
            out.append({'check': 'ChanMute', 'family': 'ChanMute',
                        'symbol': '_fdr_gq_' + nodes['fdr'],
                        'addr': base + 0x0052,
                        'observed': m1, 'expected': 0,
                        'note': f'unmuted coefficient {m0:#x}, muted must be 0',
                        'negctl': negctl_unit == 'ChanMute',
                        'verdict': 'PASS' if ok else 'FAIL'})
            log(f'  ChanMute      unmuted {m0:#x} muted {m1:#x} '
                f'{"PASS" if ok else "FAIL"}')
        except IOError as exc:
            out.append({'check': 'ChanMute', 'verdict': 'ERROR', 'error': str(exc)})
    return out


# ---------------------------------------------------------------------------
# INERT confirmation, with its positive control
# ---------------------------------------------------------------------------

def strip_window(part, strip=1):
    """The DM span holding one strip's node state, from the symbol table.

    A bus capture would be the stronger probe, but it needs a driven
    graph and the shipping per-sample build's scope injection does not
    reach the chain (measured 2026-08-29: injecting a -6 dBFS step into
    _buf_C1_IN_01 and capturing the same address returns the pre-existing
    word, so the stimulus never lands). Rather than report inert verdicts
    from a silent bus -- where every address on the card looks inert and
    the comparison cannot fail -- the probe watches the strip's whole
    CONTROL STATE instead: every DM word belonging to the strip's nodes.

    That is weaker than a bus capture in a stated way: it sees control-
    rate state, not the sample path, so a cell that reached the audio
    without leaving a mark in DM would be missed. It is strong in the way
    that matters here, because an INERT cell is one nothing reads, and a
    cell that IS read leaves its mark in exactly this window -- which the
    positive control demonstrates on every run.
    """
    pref = ('_gate_', '_comp_', '_eq_', '_hpf_', '_lpf_', '_fdr_', '_rtg_',
            '_dly_', '_tube_', '_gain_')
    # THE WANDERING WORDS ARE EXCLUDED BY NAME, not masked at run time.
    # A first attempt kept them and calibrated with a null interval; the
    # noise came out at 0-16 words per interval against a positive
    # control of 8, which is a probe whose signal does not clear its own
    # floor. These are the running state of a live graph -- sample
    # buffers, taps, filter and envelope state, the smoothers, the delay
    # write pointer, the crossfade alpha -- and none of them is control
    # state, which is what an inert cell would have to touch.
    noisy = ('_buf_', '_tap_', '_mtr_')
    noisy_sub = ('envelope', '_state_', 'write_ptr', 'local_max', 'xfade',
                 'hold_count', '_gain_C1', 'gain_target', '_active_')
    node = re.compile(r'C1_[A-Z_]+_%02d$' % strip)
    addrs = sorted({a for n, a in part.sc.sym.items()
                    if node.search(n) and n.startswith(pref)
                    and not n.startswith(noisy)
                    and not any(x in n for x in noisy_sub)})
    return addrs


def agreeing_peek(part, addr, tries=8):
    """A DM word only counts when two independent reads agree.

    Scope.peek() is a single ask through DiagLink.read, which is the
    UNPACED reader: under audio load it answers late, rotated, or as a
    well-formed zero, and a wrong value is then indistinguishable from a
    right one. dsp4_bq_verify.py already carries this guard for the same
    reason. Without it the inert probe's snapshot noise ran at 1-22 words
    per interval against a positive control of 3 -- which was the reader,
    not the graph.
    """
    last = None
    for _ in range(tries):
        try:
            v = part.sc.peek(addr)
        except IOError:
            last = None
            continue
        if v == last:
            return v
        last = v
    return None


def snapshot(part, addrs):
    return [agreeing_peek(part, a) for a in addrs]


def inert_probe(part, entries, samples, n=64, log=print, strip=1):
    """Write to a candidate inert address; nothing kernel-visible may move.

    THE POSITIVE CONTROL IS THE POINT. A comparison that cannot fail
    proves nothing, and this one is easy to make unable to fail. So the
    same procedure runs first on a cell that IS read by the emitted
    kernel, and no inert verdict is reported unless that control moved
    the window.

    THE NOISE PASS IS THE SECOND HALF OF IT, and it is per candidate.
    A running graph moves some of these words on its own -- envelopes,
    hold counters, meters, ramp state -- and which ones move depends on
    when you look, so a mask taken once at the start does not hold for
    the rest of the run: the first attempt masked on two back-to-back
    baselines and then reported every candidate as having moved 3 to 17
    words, which is drift being read as effect. Each candidate therefore
    gets its OWN null interval -- snapshot, wait exactly as long as the
    test waits, snapshot again, with no write in between -- and only
    words that move under the write and NOT under the null count.
    """
    out = []
    addrs = strip_window(part, strip)
    base_a = snapshot(part, addrs)
    base_b = snapshot(part, addrs)
    mask = [i for i in range(len(addrs))
            if base_a[i] is not None and base_a[i] == base_b[i]]
    log(f'  window: {len(addrs)} words of strip {strip} state, '
        f'{len(mask)} quiet across two baselines')
    out.append({'addr': None, 'class': 'WINDOW', 'cells': [],
                'window_words': len(addrs), 'quiet_words': len(mask),
                'verdict': 'INFO'})

    def moved(before):
        after = snapshot(part, addrs)
        return [i for i in mask if after[i] != before[i]], after

    def null_noise(settle):
        """Which quiet words move over the test's own interval, unwritten."""
        a = snapshot(part, addrs)
        time.sleep(settle)
        b = snapshot(part, addrs)
        return {i for i in mask if a[i] != b[i]}, b

    # positive control: chip 1 strip 1 compressor threshold, whose target
    # the emitted COMP body converts on every block.
    SETTLE = 0.3
    ctl_addr = (strip - 1) * STRIDE + 0x0039
    noise, before = null_noise(SETTLE)
    orig = part.read(ctl_addr)
    part.write(ctl_addr, f32(-55.0), 4)
    time.sleep(SETTLE)
    diff, _ = moved(before)
    diff = [i for i in diff if i not in noise]
    part.write(ctl_addr, orig, 4)
    time.sleep(SETTLE)
    # THE CONTROL MUST CLEAR THE NOISE FLOOR, not merely be non-zero.
    # A control that moves two words while the unwritten interval also
    # moves two proves nothing, and reporting inert verdicts underneath
    # it would be reporting the noise. Measured 2026-08-29 on this bench:
    # control 2-8 words against a null interval of 0-22, so the probe is
    # NOT usable as it stands and says so instead of answering.
    control_ok = len(diff) > max(3, 3 * len(noise))
    out.append({'addr': ctl_addr, 'class': 'POSITIVE CONTROL',
                'cells': ['Chan%03dCompThr001' % strip],
                'words_moved': len(diff), 'noise_words': len(noise),
                'moved': control_ok,
                'verdict': 'CONTROL OK' if control_ok
                           else ('CONTROL DID NOT CLEAR THE NOISE FLOOR '
                                 f'({len(diff)} moved, {len(noise)} moved '
                                 'unwritten) — NO inert verdict is reported '
                                 'from this run')})
    log(f'  positive control (CompThr): {len(diff)} of {len(mask)} quiet '
        f'words moved ({len(noise)} moved on their own over the same wait)')
    if not control_ok:
        return out

    for e in samples:
        addr = e['addr']
        words, kind, _b = probes(e)
        if not words:
            continue
        noise, before = null_noise(SETTLE)
        orig = part.read(addr)
        part.write(addr, words[-1], 0)
        time.sleep(SETTLE)
        diff, _ = moved(before)
        diff = [i for i in diff if i not in noise]
        part.write(addr, orig, 0)
        time.sleep(0.2)
        out.append({'addr': addr, 'cells': e['cells'],
                    'class': e['kernel_note'], 'wrote': words[-1],
                    'words_moved': len(diff), 'noise_words': len(noise),
                    'moved': bool(diff),
                    'verdict': 'INERT CONFIRMED' if not diff else 'NOT INERT'})
        log(f'  0x{addr:04X} {",".join(e["cells"])[:38]:<38} '
            f'{"inert" if not diff else "MOVED %d words" % len(diff)}'
            f'  (noise {len(noise)})')
    return out


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--plan', required=True)
    ap.add_argument('--chip', type=int, choices=(1, 2), default=1)
    ap.add_argument('--out', required=True)
    ap.add_argument('--phase', default='presence',
                    choices=('presence', 'effect', 'inert', 'all'))
    ap.add_argument('--strip', type=int, default=1)
    ap.add_argument('--addr-from', type=int, default=0)
    ap.add_argument('--addr-to', type=int, default=10 ** 9)
    ap.add_argument('--limit', type=int, default=0,
                    help='stop after N addresses (coverage is LOGGED, never '
                         'silently truncated)')
    ap.add_argument('--no-verify', action='store_true',
                    help='negative control: write without reading back — '
                         'every cell touched must come out UNVERIFIED')
    ap.add_argument('--negctl-unit', default=None,
                    help='negative control: predict one family from the '
                         'unit the kernel assumes instead of the documented '
                         'one; that family MUST fail')
    ap.add_argument('--inert-samples', type=int, default=12)
    args = ap.parse_args()

    plan = json.load(open(args.plan))
    entries = [e for e in plan['entries']
               if e['chip'] == args.chip
               and args.addr_from <= e['addr'] <= args.addr_to]
    entries.sort(key=lambda e: e['addr'])
    dropped = 0
    if args.limit:
        dropped = max(0, len(entries) - args.limit)
        entries = entries[:args.limit]

    part = Part(args.chip)
    res = {'chip': args.chip, 'block': BLOCK, 'plan': os.path.basename(args.plan),
           'build_id': part.sc.rd(0xE017), 'product_id': part.sc.rd(0xE010),
           'addresses_planned': len(entries) + dropped,
           'addresses_run': len(entries), 'addresses_dropped': dropped,
           'phase': args.phase, 'verify': not args.no_verify,
           'negctl_unit': args.negctl_unit}
    if dropped:
        print(f'  NOTE: --limit dropped {dropped} addresses from this run')

    if args.phase in ('presence', 'all'):
        t0 = time.time()
        pres, health = presence(part, entries, verify=not args.no_verify)
        res['presence'] = pres
        res['health'] = health
        res['presence_seconds'] = round(time.time() - t0, 1)
        counts = {}
        for r in pres:
            counts[r['verdict']] = counts.get(r['verdict'], 0) + 1
        res['presence_counts'] = counts
        print('  presence:', counts, f'in {res["presence_seconds"]}s')

    if args.phase in ('effect', 'all'):
        # THE DECLARED-UNIT CHECKS ARE CHIP-1 STRIP CHECKS. Every family
        # wire-units.csv declares (Chan*) lives on chip 1's channel strips;
        # chip 2 carries the group/aux/main output chains, whose families
        # are all UNDECLARED and therefore get presence testing only. Say
        # so rather than running a probe against symbols that do not exist
        # and reporting the resulting NO_SYMBOL rows as coverage.
        if args.chip != 1:
            res['effect'] = []
            res['effect_skipped'] = ('chip 2 carries no family whose unit is '
                                     'declared in wire-units.csv')
            print('  effect: skipped —', res['effect_skipped'])
        else:
            res['effect'] = effect(part, args.strip, args.negctl_unit)

    if args.phase in ('inert', 'all') and args.chip == 1:
        cand = [e for e in entries if e['role'] == 'INERT' and e['cells']]
        seen, samples = set(), []
        for e in cand:                    # one per kernel class, not 896 runs
            k = re.sub(r'C[12]_[A-Z0-9_]+', '', e['kernel_note'])
            k = re.sub(r'\[\d+\]', '', k)
            if k in seen:
                continue
            seen.add(k)
            samples.append(e)
            if len(samples) >= args.inert_samples:
                break
        res['inert_candidates'] = len(cand)
        res['inert_sampled'] = len(samples)
        res['inert'] = inert_probe(part, entries, samples)
        print(f'  inert: {len(samples)} classes sampled of '
              f'{len(cand)} candidate addresses')
    elif args.phase in ('inert', 'all'):
        res['inert_skipped'] = ('the bus capture and its positive control '
                                'are chip-1 symbols')
        print('  inert: skipped —', res['inert_skipped'])

    res['final_health'] = part.healthy()
    with open(args.out, 'w') as fh:
        json.dump(res, fh)
    print(f'  wrote {args.out}; part healthy at exit: {res["final_health"]}')


if __name__ == '__main__':
    main()
