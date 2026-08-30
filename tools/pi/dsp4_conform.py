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


# ---------------------------------------------------------------------------
# THE DRIVEN-GRAPH PROBE (2026-08-29). Session 4's honest gap, closed.
#
# The strip_window probe above watches CONTROL state and it FAILED ITS OWN
# CONTROL: on an idle graph the positive control moved 2-8 of 97 quiet words
# while the unwritten interval moved 0-22, so its signal never cleared its
# noise floor and no inert verdict was reported. The note under strip_window
# names the stronger probe -- capture the BUS while the graph is DRIVEN --
# and says why it was not used: "the shipping per-sample build's scope
# injection does not reach the chain (injecting a -6 dBFS step into
# _buf_C1_IN_01 and capturing the same address returns the pre-existing
# word)."
#
# THAT WAS THE PROBE'S BUG, NOT THE FIRMWARE'S, and it is one address.
# _scope_inject runs in the per-sample loop AFTER _scatter_chipN and BEFORE
# the node chain (main.asm), which is the point the file's own header names
# -- "the one point where an input slot variable holds a value nothing
# downstream has overwritten yet". _buf_C1_IN_01 is not that slot: it is the
# INPUT NODE'S OUTPUT, and C1_IN_01's per-sample body copies _rx_slot into
# it on every sample, so a step written there is overwritten before any node
# reads it. _rx_slot_C1_IN_01 IS that slot. Under block kernels the input
# slots are the pool itself, which is why the block-form injection targets
# _blk_pool and has always worked (dsp4_pairgraph.py captures 64 of 64
# non-zero words through it).
#
# So the shipping image was drivable all along, and this probe drives it.
# ---------------------------------------------------------------------------

BUS_SRC = '_buf_C1_BUS_MAIN_L'
BUS_AMP = 0x08000000                   # -6 dBFS in Q4.28, the injected step


def bus_inject_addr(part):
    """The input slot the step must go into for it to reach the chain.

    Block builds put the input slots in the shared pool; per-sample builds
    keep a scalar _rx_slot per input node, which _scatter_chipN fills and
    _scope_inject then overwrites. The symbol table settles which build
    this is -- _blk_pool exists only under DSP4_BLOCK_KERNELS (blk_pool.h).
    """
    if '_blk_pool' in part.sc.sym:
        return part.sc.sym['_blk_pool']
    return part.sc.sym['_rx_slot_C1_IN_01']


CAPTURE_REST = 0.50        # seconds of silence before each arm
# WHERE IN THE BUFFER THE WINDOW SITS, and it is not the start. The scope
# records 1024 samples from the instant the step lands, and the first
# thirty-odd of those are the graph's INSTANTANEOUS response: the gate has
# not opened, the compressor's envelope has barely left zero, and nothing
# with a time constant has moved at all. Measured on the part 2026-08-30:
# with the window at sample 0, writing the compressor THRESHOLD moved zero
# of 32 bus words -- a positive control that fails because the window is
# blind to the whole dynamics section, not because the write did nothing.
# 900 samples is 18.75 ms at 48 kHz, past the documented attack of both
# dynamics classes, and 92 samples short of the buffer's end.
CAPTURE_OFFSET = 900


def bus_capture(part, inj, n, src=None):
    """One armed capture of the main bus with the step driving the graph.

    THE REST BEFORE THE ARM IS PART OF THE MEASUREMENT. The scope only
    drives while it is armed, so between captures the graph falls silent
    and its envelopes, hold counters and filter state release for however
    long the host happened to take. Two back-to-back captures then start
    from different states and differ in EVERY word -- measured on the part
    2026-08-30: 32 of 32 words moved over a null interval, which is a noise
    floor no positive control can clear. Waiting for the graph to come back
    to rest first makes each capture start from the same place, so the only
    thing that can move a word is what was written between them.

    Returns None rather than a wrong answer if the scope will not arm or
    the capture stalls: a dropped capture and an inert cell look identical
    from a list of words, and that is the mistake this whole probe exists
    to avoid.
    """
    time.sleep(CAPTURE_REST)
    try:
        part.sc.arm(part.sc.sym[src or BUS_SRC], inj, BUS_AMP, 2)
        part.sc.wait()
        out = []
        for i in range(CAPTURE_OFFSET, CAPTURE_OFFSET + n):
            part.sc.wr(S.SCOPE_RD, i)
            out.append(part.sc.rd(S.SCOPE_DATA))
        return out
    except (IOError, SystemExit):
        return None


# Strip-page offsets, from dsp.csv's spi_addr column via
# dsp_address_map.md -- the same numbers dsp4_pairgraph.py uses.
FDR_LEVEL, FDR_PAN, FDR_MUTE, FDR_DCA = 0x0050, 0x0051, 0x0052, 0x0053
GAIN_OFF, TUBE_ON, DLY_OFF = 0x0000, 0x004C, 0x004E
RTG_MAIN_ON = 0x0054
GATE_ON, GATE_THR, GATE_ATT = 0x0028, 0x0029, 0x002A
GATE_HOLD, GATE_REL = 0x002B, 0x002C
COMP_ON, COMP_THR, COMP_RATIO = 0x0038, 0x0039, 0x003A
COMP_ATT, COMP_REL, COMP_PAR = 0x003B, 0x003C, 0x003F


def wr_checked(part, addr, word, ramp, sym=None, want=None, log=print,
               tries=4):
    """Write, and where a DM symbol names the consequence, CHECK it.

    Every write on this link is fire-and-forget and roughly one boot in
    three leaves strip 1's gain holding the CFG_COMMIT header word. A probe
    that writes and assumes reports "nothing moved" for a write that never
    landed, which is indistinguishable from an inert cell -- the exact
    confusion this whole phase exists to avoid.
    """
    for _ in range(tries):
        try:
            part.write(addr, word, ramp)
        except Exception as e:
            log(f'  write 0x{addr:04X} failed ({e})')
            return False
        time.sleep(0.15)
        if sym is None:
            return True
        if sym not in part.sc.sym:
            return True
        got = agreeing_peek(part, part.sc.sym[sym])
        if got == want:
            return True
    log(f'  write 0x{addr:04X} did not reach {sym}: '
        f'want 0x{(want or 0):08X} got '
        f'{"unreadable" if got is None else "0x%08X" % got}')
    return False


def drive_strip(part, strip, log=print):
    """Put one strip in a state where the injected step reaches the BUS.

    A boot leaves the fader, its pan legs and the DCA wherever the config
    commit left them, and ROUTING's main crosspoint coefficient is the
    fader's pan leg times its level -- so an un-driven strip contributes
    NOTHING to the main bus and the capture is all zeros. All zeros is
    also what a dead strip, a dropped arm and a muted graph look like,
    which is why this is done explicitly rather than assumed.
    """
    b = (strip - 1) * STRIDE
    for addr, word, ramp in ((b + GAIN_OFF, f32(1.0), 4),
                             (b + FDR_LEVEL, f32(1.0), 4),
                             (b + FDR_PAN, f32(0.5), 4),
                             # RtgDca IS A GAIN, whatever the masters say.
                             # `Chan001RtgDca001` is documented with no
                             # scale law -- a DCA ASSIGNMENT -- and the
                             # kernel lands it in _fdr_dca_gain_*, which it
                             # multiplies into the fader coefficient.写 0
                             # here (the obvious "no DCA assigned") and the
                             # fader coefficient goes to zero and the strip
                             # goes silent, which is exactly what happened
                             # on 2026-08-30 and cost three probe runs.
                             # Review finding D57.
                             (b + FDR_DCA, f32(1.0), 4),
                             (b + FDR_MUTE, 0, 0),
                             # Without this the strip reaches no bus at all
                             # and the capture is all zeros -- which is also
                             # what a dead strip looks like.
                             (b + RTG_MAIN_ON, 1, 0),
                             (b + TUBE_ON, 0, 0),
                             (b + DLY_OFF, 0, 0),
                             # The dynamics have to be ON or the compressor
                             # positive control tests a bypassed node: a
                             # threshold write then changes nothing on the
                             # bus and the control fails for a reason that
                             # has nothing to do with the window.
                             (b + GATE_ON, 1, 0),
                             (b + COMP_ON, 1, 0),
                             # AND THE COMPRESSOR HAS TO BE WET. The
                             # parallel blend is `out = dry + par*(wet -
                             # dry)` and CompPar defaults to 0, so a
                             # compressor that is ON, above threshold and
                             # visibly reducing gain in _comp_gain_* passes
                             # the DRY signal through unchanged. Measured
                             # here 2026-08-30: with par at its default the
                             # bus reads 0x03FFFFEE at BOTH a -20 dB and a
                             # -55 dB threshold, to the word, while
                             # _comp_gain_C1_COMP_01 moves from 0x10000000
                             # to 0x04FE8E90. The gain reduction is computed
                             # and then blended out.
                             (b + COMP_PAR, f32(100.0), 4),
                             # FAST TIME CONSTANTS, AND A SHORT HOLD,
                             # because the probe's repeatability depends on
                             # the graph being back at rest before each
                             # capture. The shipping defaults include a
                             # 2000 ms gate HOLD and a release the strip
                             # does not finish inside the probe's rest
                             # interval, and a graph that is still releasing
                             # gives two consecutive captures that differ in
                             # every word -- a noise floor no control can
                             # clear. Measured here 2026-08-30: 32 of 32.
                             (b + GATE_THR, f32(-40.0), 4),
                             (b + GATE_ATT, f32(0.001), 4),
                             (b + GATE_HOLD, f32(1.0), 4),
                             (b + GATE_REL, f32(0.001), 4),
                             (b + COMP_THR, f32(-20.0), 4),
                             (b + COMP_RATIO, f32(4.0), 4),
                             (b + COMP_ATT, f32(0.002), 4),
                             (b + COMP_REL, f32(0.002), 4)):
        try:
            part.write(addr, word, ramp)
        except Exception as e:
            log(f'  drive_strip: 0x{addr:04X} write failed ({e})')
        time.sleep(0.02)
    time.sleep(0.5)                      # let the ramped writes arrive
    # The gain is the one that has to be right, and it is the one that goes
    # wrong: re-write it until the Q4.28 shadow reads unity.
    wr_checked(part, b + GAIN_OFF, f32(1.0), 4,
               '_gain_q_C1_GAIN_%02d' % strip, 0x10000000, log)


# The strip in chain order. A capture of each says WHERE the signal stops,
# which is the difference between "this cell is inert" and "this strip is
# not carrying anything".
_CHAIN = ('IN', 'GAIN', 'FILT', 'EQ', 'GATE', 'COMP', 'TUBE', 'DLY', 'FDR')


def chain_witness(part, inj, strip, n=4, log=print):
    """Walk the strip and report the first node whose output is dead.

    A capture of the BUS that is merely non-zero is not a witness: measured
    2026-08-30, a bus reading 0xFFFFFFF3 in every word -- thirteen LSBs of
    residue, constant -- passed a non-zero test while the fader's output was
    exactly zero and the gain control moved nothing. What the window has to
    carry is the SIGNAL.
    """
    dead = None
    for cls in _CHAIN:
        sym = '_buf_C1_%s_%02d' % (cls, strip)
        if sym not in part.sc.sym:
            continue
        w = bus_capture(part, inj, n, sym)
        if w is None:
            log(f'  chain witness: {sym} unreadable')
            return None
        pk = max(abs(w2 - (1 << 32) if w2 & 0x80000000 else w2) for w2 in w)
        log(f'  chain witness: {sym:<22} peak 0x{pk:08X}')
        if pk < BUS_AMP >> 6 and dead is None:
            dead = sym
    return dead


def driven_inert_probe(part, entries, samples, n=32, log=print, strip=1):
    """Write to a candidate inert address; the DRIVEN bus must not move.

    Same three-part shape as the control-state probe -- null interval,
    positive control, then the candidates -- but the window is the audio
    path itself, which is what "kernel-visible" was always supposed to
    mean. A cell that reaches the audio and leaves no mark in control state
    is invisible to the other probe and cannot hide from this one.

    THE BAR IS UNCHANGED AND IT IS STILL THE CONTROL'S TO CLEAR: the
    positive control must move more than 3x what the unwritten interval
    moves, and more than 3 words, or the run reports NO inert verdict.
    """
    out = []
    inj = bus_inject_addr(part)
    drive_strip(part, strip, log)
    # THE WINDOW IS THE BUS IF THE BUS CARRIES ANYTHING, and the strip's
    # own post-fader output otherwise. The bus is the stronger window --
    # it sees ROUTING and the cross-strip mix as well -- but a silent one
    # is not a window at all, and falling back SILENTLY would be the same
    # mistake as reporting inert verdicts from an idle graph. Which window
    # was used is recorded next to every verdict.
    src, window = BUS_SRC, 'bus'
    base = bus_capture(part, inj, n, src)

    def carries(words):
        if not words:
            return False
        pk = max(abs(w - (1 << 32) if w & 0x80000000 else w) for w in words)
        return pk >= (BUS_AMP >> 6)

    if base is not None and not carries(base):
        alt = '_buf_C1_FDR_%02d' % strip
        if alt in part.sc.sym:
            b2 = bus_capture(part, inj, n, alt)
            if carries(b2):
                src, window, base = alt, 'strip', b2
                log(f'  driven window: {BUS_SRC} is silent; falling back to '
                    f'{alt}, the strip output. That window sees every class '
                    f'in the strip but NOT ROUTING or the mix.')
    if base is None:
        out.append({'addr': None, 'class': 'WINDOW', 'cells': [],
                    'verdict': 'NO CAPTURE — the scope would not arm; no '
                               'inert verdict is reported from this run'})
        log('  driven window: NO CAPTURE')
        return out
    # PEAK, not "non-zero". A constant residue of a few LSBs is non-zero
    # and is not a signal; see chain_witness().
    pk = max(abs(w - (1 << 32) if w & 0x80000000 else w) for w in base)
    nz = pk if pk >= (BUS_AMP >> 6) else 0
    log(f'  driven window: {src} through inj 0x{inj:X}, '
        f'peak 0x{pk:08X} against an injected 0x{BUS_AMP:08X}')
    out.append({'addr': None, 'class': 'WINDOW', 'cells': [],
                'inject': inj, 'source': src, 'window': window,
                'window_words': n, 'nonzero': nz, 'verdict': 'INFO'})
    if not nz:
        # An all-zero capture is what a dead strip, a dropped arm and a
        # muted graph all look like. It is not a driven graph. Say WHERE it
        # died rather than only that it did.
        dead = chain_witness(part, inj, strip, log=log)
        out[-1]['verdict'] = (
            'SILENT WINDOW — every cell would look inert; no inert verdict '
            'is reported from this run'
            + (f'. The signal stops at {dead}.' if dead else ''))
        log('  driven window: SILENT — nothing is reported from this run'
            + (f'; the signal stops at {dead}' if dead else ''))
        return out

    def null_noise():
        """Which words move between two captures with nothing written."""
        a = bus_capture(part, inj, n, src)
        b = bus_capture(part, inj, n, src)
        if a is None or b is None:
            return None, None
        return {i for i in range(n) if a[i] != b[i]}, b

    def moved(before):
        after = bus_capture(part, inj, n, src)
        if after is None:
            return None, None
        return [i for i in range(n) if after[i] != before[i]], after

    # TWO POSITIVE CONTROLS, because they test different halves of the
    # window. GAIN is a linear multiply the sample path reads on every
    # sample, so it proves the window sees the STRIP at all; CompThr only
    # moves anything once the compressor's envelope has moved, so it proves
    # the window reaches past the transient into the dynamics. A run needs
    # BOTH: the first alone would let a window that is blind to everything
    # with a time constant report inert verdicts about dynamics cells.
    SETTLE = 0.3
    controls = ((0x0000, f32(0.5), 4, 'Chan%03dGain001' % strip, 'GAIN',
                 '_gain_q_C1_GAIN_%02d' % strip, 0x08000000),
                (0x0039, f32(-55.0), 4, 'Chan%03dCompThr001' % strip,
                 'CompThr', None, None))
    all_ok = True
    for off, val, ramp, cell, name, chk, chk_want in controls:
        ctl_addr = (strip - 1) * STRIDE + off
        noise, before = null_noise()
        if noise is None:
            out.append({'addr': ctl_addr, 'class': 'POSITIVE CONTROL',
                        'cells': [cell], 'verdict': 'NO CAPTURE'})
            return out
        orig = part.read(ctl_addr)
        if not wr_checked(part, ctl_addr, val, ramp, chk, chk_want, log):
            out.append({'addr': ctl_addr, 'class': 'POSITIVE CONTROL',
                        'cells': [cell],
                        'verdict': 'CONTROL WRITE DID NOT LAND — NO inert '
                                   'verdict is reported from this run'})
            return out
        time.sleep(SETTLE)
        diff, _ = moved(before)
        part.write(ctl_addr, orig, ramp)
        time.sleep(SETTLE)
        diff = [i for i in (diff or []) if i not in noise]
        ok = len(diff) > max(3, 3 * len(noise))
        all_ok = all_ok and ok
        out.append({'addr': ctl_addr, 'class': 'POSITIVE CONTROL',
                    'cells': [cell], 'window': window, 'source': src,
                    'words_moved': len(diff), 'noise_words': len(noise),
                    'moved': ok,
                    'verdict': 'CONTROL OK' if ok
                               else ('CONTROL DID NOT CLEAR THE NOISE FLOOR '
                                     f'({len(diff)} moved, {len(noise)} moved '
                                     'unwritten) — NO inert verdict is '
                                     'reported from this run')})
        log(f'  positive control ({name}): {len(diff)} of {n} bus words '
            f'moved ({len(noise)} moved on their own over the same wait)')
    if not all_ok:
        return out

    for e in samples:
        addr = e['addr']
        words, kind, _b = probes(e)
        if not words:
            continue
        noise, before = null_noise()
        if noise is None:
            continue
        orig = part.read(addr)
        part.write(addr, words[-1], 0)
        time.sleep(SETTLE)
        diff, _ = moved(before)
        part.write(addr, orig, 0)
        time.sleep(0.2)
        if diff is None:
            out.append({'addr': addr, 'cells': e['cells'],
                        'class': e['kernel_note'],
                        'verdict': 'NO CAPTURE'})
            continue
        diff = [i for i in diff if i not in noise]
        out.append({'addr': addr, 'cells': e['cells'],
                    'class': e['kernel_note'], 'wrote': words[-1],
                    'window': window, 'source': src,
                    'words_moved': len(diff), 'noise_words': len(noise),
                    'moved': bool(diff),
                    'verdict': 'INERT CONFIRMED' if not diff else 'NOT INERT'})
        log(f'  0x{addr:04X} {",".join(e["cells"])[:38]:<38} '
            f'{"inert" if not diff else "MOVED %d words" % len(diff)}'
            f'  (noise {len(noise)})')
    return out


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
    ap.add_argument('--inert-window', default='bus', choices=('bus', 'state'),
                    help='bus = the DRIVEN main-bus capture (default); '
                         'state = the strip control-state window, which '
                         'failed its own noise floor on an idle graph')
    ap.add_argument('--inert-capture', type=int, default=32,
                    help='bus words per capture (2 link reads each)')
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

    # PHASE ORDER: presence, effect, THEN inert. Running inert first was
    # tried on 2026-08-30 and is worse: it leaves the strip driven --
    # compressor wet, fast time constants, gate open -- and the EFFECT
    # phase then measures a differently configured strip (17 pass / 17
    # fail against the 18 / 16 baseline). The inert probe re-establishes
    # everything it needs in drive_strip() instead, which is where that
    # responsibility belongs.
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
        # THE DRIVEN BUS IS THE PROBE (2026-08-29). The control-state
        # window failed its own noise floor on an idle graph; this drives
        # the graph and watches the audio. --inert-window=state puts the
        # old probe back, which is how the two are compared rather than
        # asserted against each other.
        res['inert_window'] = args.inert_window
        if args.inert_window == 'state':
            res['inert'] = inert_probe(part, entries, samples)
        else:
            res['inert'] = driven_inert_probe(part, entries, samples,
                                              n=args.inert_capture)
        print(f'  inert: {len(samples)} classes sampled of '
              f'{len(cand)} candidate addresses '
              f'({args.inert_window} window)')
    elif args.phase in ('inert', 'all'):
        res['inert_skipped'] = ('the bus capture, the injection slot and '
                                'the positive control are chip-1 symbols')
        print('  inert: skipped —', res['inert_skipped'])

    res['final_health'] = part.healthy()
    with open(args.out, 'w') as fh:
        json.dump(res, fh)
    print(f'  wrote {args.out}; part healthy at exit: {res["final_health"]}')


if __name__ == '__main__':
    main()
