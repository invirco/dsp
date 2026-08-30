#!/usr/bin/env python3
"""dsp4_node_verify.py — the STRIP NODES against fixed_ref, ON THE PART
(review findings D28, D29, D30, D31; and D35's complaint about all of it).

WHAT THIS IS FOR. Until 2026-08-30 the golden-coverage map had a hole in
the middle of it: COMP's wet path, the GATE state machine, TUBE and
FADER_PAN had no reference model of any kind, and the only in-part
instruments the strip had (`bq_selftest.asm`, `dyn_selftest.asm`)
compare ASSEMBLY AGAINST ASSEMBLY -- they prove two emitted paths agree,
not that either one is the ruled arithmetic (review finding D35). The
three most recent shipped audio defects all lived in exactly that hole:
the squared pan gain, the percent parallel blend, and a compressor that
was dry by default.

WHAT IT DOES. It does NOT run a probe copy of the arithmetic. It drives
the REAL GRAPH through the scope, captures a node's INPUT and its OUTPUT
over the same stimulus from the same rested state, reads the node's own
converted parameters and state out of DM, runs fixed_ref over the
captured input, and requires the model to reproduce the captured output
WORD FOR WORD. The thing under test is the shipping node body, not a
transcription of it.

    inject step/impulse -> [ IN GAIN FILT EQ | node | ... ] -> capture
                                  ^ capture the node's input too

TWO CAPTURES, ONE STATE. The scope records one address at a time, so the
input and the output come from two consecutive armed runs. They are
comparable because the graph is brought back TO REST between them
(`CAPTURE_REST`, the discipline dsp4_conform.py established): with the
stimulus, the parameters and the starting state identical, the second
run produces the same samples as the first. That is not assumed -- every
node's first row is a REPEAT capture of its own output, and a run whose
repeat differs reports nothing.

THE NEGATIVE CONTROL IS IN THE MODEL, NOT IN A SECOND IMAGE. Each node
carries a deliberately-wrong twin in fixed_ref -- the gate ladder without
its hold counter, the compressor's makeup without its second rounding,
the tube without the middle of its three roundings, the fader with the
level folded into the pan leg a second time (which is the 2026-08-23
defect, exactly). The twin is run over the SAME captured input, and the
run requires it to DISAGREE with the part. A stimulus on which the twin
happens to agree proves nothing, so the tool re-drives with a different
amplitude until one separates them and says which one it used. No
rebuild, no second boot: the control costs nothing but arithmetic.

THE PARAMETER CONVERSION IS CHECKED SEPARATELY FROM THE SAMPLE PATH, and
that split is the point. The cell values this writes are converted by the
node at block rate; the converted words are peeked and compared against
the model's own conversion (`fdr_coeffs`, `tube_sat_q`, `gate_range_q`,
...), which is where D39's dB range and D40's percent blend went wrong.
The sample path is then run from the PART's converted words, so a
conversion fault and an arithmetic fault cannot mask one another.

Usage, on the bench:
    python3 dsp4_node_verify.py [--strip 1] [--n 96] [--nodes GATE,COMP]
Run through goldnode.sh, which builds, stages and boots.
"""
import argparse
import struct
import sys
import time

sys.path.insert(0, '/home/app/dspboot')

import dsp4_scope as S
import fixed_ref as fr
from dsp4_conform import (Part, agreeing_peek, drive_strip, f32, STRIDE,
                          CAPTURE_REST, GATE_ON, GATE_THR, GATE_ATT,
                          GATE_HOLD, GATE_REL, COMP_ON, COMP_THR,
                          COMP_RATIO, COMP_ATT, COMP_REL, COMP_PAR,
                          TUBE_ON, FDR_LEVEL, FDR_PAN, FDR_MUTE)

# Strip-page offsets dsp4_conform does not already name, from
# dsp_address_map.md (Chan001 page).
GATE_RNG = 0x002D
COMP_MKUP, COMP_KNEE = 0x003D, 0x003E
TUBE_SAT = 0x004D


def s32(v):
    return v - (1 << 32) if v & 0x80000000 else v


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

def capture(part, src, inj, amp, mode, n, tries=3):
    """One armed run: rest, arm, wait, read n words from sample 0.

    FROM SAMPLE 0, unlike the bus probe's window at 900. That probe wants
    the graph's SETTLED response; this one wants the graph's response from
    a KNOWN STATE, and sample 0 is the only sample whose state the host
    can read beforehand.
    """
    for _ in range(tries):
        time.sleep(CAPTURE_REST)
        try:
            part.sc.arm(part.sc.sym[src], inj, amp, mode)
            part.sc.wait()
            out = []
            for i in range(n):
                part.sc.wr(S.SCOPE_RD, i)
                out.append(part.sc.rd(S.SCOPE_DATA))
            return [s32(w) for w in out]
        except (IOError, SystemExit):
            try:
                part.sc.d.resync()
            except Exception:
                pass
    return None


def inject_addr(part, strip):
    """The input slot _scope_inject must drive for the step to reach the
    chain. Same resolution dsp4_conform.bus_inject_addr makes, per strip:
    the block build's slots are the pool, the per-sample build's are the
    input node's own _rx_slot (NOT _buf_C1_IN_nn, which the IN node
    overwrites every sample -- the mistake that made the shipping image
    look undrivable for a whole session)."""
    if '_blk_pool' in part.sc.sym:
        return part.sc.sym['_blk_pool']
    return part.sc.sym['_rx_slot_C1_IN_%02d' % strip]


# ---------------------------------------------------------------------------
# The nodes. Each entry says how to put its node in a known state, what to
# read out of DM, how to model it, and how to get it wrong.
# ---------------------------------------------------------------------------

def _gate_setup(strip):
    """GATE ON, everything after it BYPASSED so the capture is the gate's
    own output and nothing downstream can move it. A SHORT HOLD in RAW
    SAMPLES: the kernel reads `_gate_hold_` as an integer sample count
    while the masters document milliseconds (the standing KNOWN_MISMATCH
    conform.sh reports), so a float write here would set a hold of a
    billion samples and the hold arm would never be reached inside a
    capture."""
    return [(GATE_ON, 1, 0), (COMP_ON, 0, 0), (TUBE_ON, 0, 0),
            (GATE_THR, f32(-40.0), 0), (GATE_ATT, f32(0.05), 0),
            (GATE_REL, f32(0.5), 0), (GATE_RNG, f32(40.0), 0),
            (GATE_HOLD, 24, 0)]


def _gate_model(xs, p, st0, twin=False):
    att, rel, thr, rng, hold = p
    st = list(st0)
    step = fr.gate_step_nohold if twin else fr.gate_step
    return [step(x, st, att, rel, thr, rng, hold) for x in xs]


def _comp_setup(strip):
    """COMP ON with the gate OUT OF THE WAY (bypassed), so the captured
    input is the injected step itself and the only arithmetic between the
    two captures is the compressor's."""
    return [(GATE_ON, 0, 0), (COMP_ON, 1, 0), (TUBE_ON, 0, 0),
            (COMP_THR, f32(-30.0), 0), (COMP_RATIO, f32(4.0), 0),
            (COMP_ATT, f32(0.05), 0), (COMP_REL, f32(0.01), 0),
            (COMP_KNEE, f32(0.0), 0),
            # A MAKEUP THAT IS NOT UNITY, and an untidy one. At makeup =
            # 1.0 the second of the two roundings is arithmetically
            # invisible -- rns28(w * 2^28) is w -- so the negative
            # control cannot fire and the capture proves only the first
            # multiply. 1.37 puts a fraction into the intermediate.
            (COMP_MKUP, f32(1.37), 0),
            (COMP_PAR, f32(100.0), 0)]


def _comp_model(xs, p, st0, twin=False):
    attq, relq, mkq, parq, thr, slope, halfk, k2 = p
    env = st0[0]
    wetf = fr.comp_wet_1round if twin else fr.comp_wet
    out = []
    for x in xs:
        env = fr.env_step(fr.alu_abs(x), env, attq, relq)
        g = fr.comp_gain(env, thr, slope, halfk, k2)
        out.append(fr.comp_blend(x, wetf(x, g, mkq), parq))
    return out


def _tube_setup(strip):
    """TUBE ON with the dynamics bypassed. The saturation is written
    UNTIDY on purpose: at sat = 1.0 with a tidy sample the middle
    rounding lands on the Q4.28 grid exactly and the two-rounding twin
    agrees word for word (measured while building the vector set -- a
    400k-point search found the disagreement only where neither operand
    is tidy)."""
    return [(GATE_ON, 0, 0), (COMP_ON, 0, 0),
            (TUBE_ON, 1, 0), (TUBE_SAT, f32(0.8588), 0)]


def _tube_model(xs, p, st0, twin=False):
    satq = p[0]
    f = fr.tube_2round if twin else fr.tube
    return [f(x, satq) for x in xs]


def _fdr_setup(strip):
    """FADER_PAN at a level that is NOT unity. The squared-gain defect
    this node shipped is exact at level 1.0 -- that is why it shipped --
    so a capture at unity cannot see it and the negative control cannot
    fire. 0.5 is where the bench measured 6.02 dB of error."""
    return [(GATE_ON, 0, 0), (COMP_ON, 0, 0), (TUBE_ON, 0, 0),
            (FDR_LEVEL, f32(0.5), 0), (FDR_PAN, f32(0.25), 0),
            (FDR_MUTE, 0, 0)]


def _fdr_model(xs, p, st0, twin=False):
    gq, lq = p[0], p[1]
    if twin:
        return [fr.fdr_pan_squared(x, gq, lq) for x in xs]
    return [fr.fdr_apply(x, gq) for x in xs]


NODES = {
    # name: (input symbol, output symbol, setup, param symbols, state
    #        symbols, model, converted-parameter cross-check, stimuli)
    'GATE': dict(
        inp='_buf_C1_EQ_%02d', out='_buf_C1_GATE_%02d',
        setup=_gate_setup, model=_gate_model,
        params=['_gate_attq_C1_GATE_%02d', '_gate_relq_C1_GATE_%02d',
                '_gate_thrq_C1_GATE_%02d', '_gate_rngq_C1_GATE_%02d',
                '_gate_hold_C1_GATE_%02d'],
        state=['_gate_envelope_C1_GATE_%02d', '_gate_gain_C1_GATE_%02d',
               '_gate_gain_target_q_C1_GATE_%02d',
               '_gate_hold_count_C1_GATE_%02d'],
        cvt=lambda p: [('gate range floor (D39: dB on the wire)',
                        p[3], fr.gate_range_q(40.0)),
                       ('gate threshold -> Q6.25 log2',
                        s32(p[2]), fr.gate_thr_q(-40.0)),
                       ('gate attack alpha -> Q0.31',
                        p[0], fr.dyn_alpha_q(0.05))],
        stim=[('impulse', 1), ('step', 2)],
        why='the hold/range/smoother ladder (D30)'),
    'COMP': dict(
        inp='_buf_C1_GATE_%02d', out='_buf_C1_COMP_%02d',
        setup=_comp_setup, model=_comp_model,
        params=['_comp_attq_C1_COMP_%02d', '_comp_relq_C1_COMP_%02d',
                '_comp_mkq_C1_COMP_%02d', '_comp_parq_C1_COMP_%02d',
                '_comp_cgp_C1_COMP_%02d', '_comp_cgp_C1_COMP_%02d+1',
                '_comp_cgp_C1_COMP_%02d+2', '_comp_cgp_C1_COMP_%02d+3'],
        state=['_comp_envelope_C1_COMP_%02d'],
        cvt=lambda p: [('comp makeup -> Q4.28', p[2],
                        fr.comp_makeup_q(1.37)),
                       ('comp parallel blend (D40: PERCENT on the wire)',
                        p[3], fr.comp_par_q(100.0))],
        stim=[('step', 2), ('impulse', 1)],
        why='the makeup second rounding and the parallel blend (D28)'),
    'TUBE': dict(
        inp='_buf_C1_COMP_%02d', out='_buf_C1_TUBE_%02d',
        setup=_tube_setup, model=_tube_model,
        params=['_tube_sat_C1_TUBE_%02d'],
        state=[],
        cvt=None,           # the sat word is a FLOAT; converted below
        stim=[('step', 2), ('impulse', 1)],
        why='the three chained roundings, PLUGIN-CLASS (D29)'),
    'FDR': dict(
        inp='_buf_C1_DLY_%02d', out='_buf_C1_FDR_%02d',
        setup=_fdr_setup, model=_fdr_model,
        params=['_fdr_gq_C1_FDR_%02d', '_fdr_lq_C1_FDR_%02d',
                '_fdr_rq_C1_FDR_%02d'],
        state=[],
        cvt=lambda p: [('fdr level coefficient', s32(p[0]),
                        fr.fdr_coeffs(0.5, 0.25, 0)[0]),
                       ('fdr LEFT pan leg (linear law; D42 open)',
                        s32(p[1]), fr.fdr_coeffs(0.5, 0.25, 0)[1]),
                       ('fdr RIGHT pan leg', s32(p[2]),
                        fr.fdr_coeffs(0.5, 0.25, 0)[2])],
        stim=[('step', 2), ('impulse', 1)],
        why='the pan law and the level coefficient (D31)'),
}

# AMPLITUDES, TRIED IN ORDER UNTIL ONE SEPARATES THE TWIN. Untidy words
# first: the round ones (0x08000000 = -6 dBFS exactly) put every
# intermediate on the Q4.28 grid, which is precisely where a dropped
# rounding is invisible.
AMPS = [0x0D3A17B5, 0x0553C1A7, 0x08000000, 0x1A6F2E93, 0x02000000]


def read_params(part, syms, strip):
    """Peek a node's converted words. Symbols may carry a `+n` offset."""
    out = []
    for s in syms:
        name = s % strip
        off = 0
        if '+' in name:
            name, o = name.split('+')
            off = int(o)
        if name not in part.sc.sym:
            return None
        v = agreeing_peek(part, part.sc.sym[name] + off)
        if v is None:
            return None
        out.append(v)
    return out


def run_node(part, name, spec, strip, n, log=print):
    """One node: converted parameters, then the sample path, then the
    negative control. Returns (verdicts, ok, measurable)."""
    b = (strip - 1) * STRIDE
    log(f'--- {name}: {spec["why"]}')
    for off, word, ramp in spec['setup'](strip):
        part.write(b + off, word, ramp)
        time.sleep(0.02)
    time.sleep(0.6)                     # let the block-rate conversion run

    p = read_params(part, spec['params'], strip)
    if p is None:
        log('  parameters unreadable — no verdict')
        return 0, 0, 0

    # ---- 1. the block-rate CONVERSION, against the model's own -------
    bad = 0
    for label, got, want in (spec['cvt'](p) if spec['cvt'] else []):
        ok = (got == want)
        bad += not ok
        log(f'  cvt {label:52s} {got:12d} / {want:12d}  '
            f'{"ok" if ok else "<-- MISMATCH"}')

    if name == 'TUBE':
        # TUBE holds its saturation as the FLOAT CELL and converts it in
        # the sample body, so what comes back here is an IEEE word, not a
        # Q4.28 one. The value written is in the KERNEL's units (a linear
        # 0..1 multiplier); the masters' own scale law for this cell is
        # `0=0/127=100/[Lin]` and the wire contract records its unit as
        # UNDECLARED, which is finding D65 -- at the documented maximum
        # the node's `fix` is handed 100 * 2^28 and leaves its domain
        # entirely. Nothing here can settle that; it is written in the
        # units the kernel reads so that the ARITHMETIC can be measured.
        satf = struct.unpack('<f', struct.pack('<I', p[0] & 0xFFFFFFFF))[0]
        p = [fr.tube_sat_q(satf)]
        log(f'  cvt {"tube saturation cell (unit UNDECLARED, D65)":52s} '
            f'{satf!r} -> Q4.28 {p[0]}')

    st0 = read_params(part, spec['state'], strip) or []
    st0 = [s32(v) for v in st0]
    if st0:
        log(f'  state at rest: {st0}')

    inj = inject_addr(part, strip)
    measurable, allbad = 0, bad
    for stim_name, mode in spec['stim']:
        for amp in AMPS:
            ys = capture(part, spec['out'] % strip, inj, amp, mode, n)
            if ys is None:
                continue
            ys2 = capture(part, spec['out'] % strip, inj, amp, mode, n)
            if ys2 != ys:
                # THE REPEAT IS THE NOISE FLOOR. Two runs of the same
                # stimulus from the same rest must be identical; if they
                # are not, the graph did not come back to rest and no
                # comparison below means anything.
                log(f'  {stim_name} amp 0x{amp:08X}: repeat capture DIFFERS '
                    f'in {sum(a != c for a, c in zip(ys, ys2))} of {n} '
                    f'words — not at rest, trying another amplitude')
                continue
            xs = capture(part, spec['inp'] % strip, inj, amp, mode, n)
            if xs is None:
                continue
            want = spec['model'](xs, p, st0)
            twin = spec['model'](xs, p, st0, twin=True)
            sep = sum(a != c for a, c in zip(want, twin))
            if sep == 0:
                log(f'  {stim_name} amp 0x{amp:08X}: the negative control '
                    f'cannot separate on this stimulus — trying another '
                    f'amplitude')
                continue
            diff = [i for i in range(n) if ys[i] != want[i]]
            tdiff = sum(1 for i in range(n) if ys[i] != twin[i])
            measurable += 1
            allbad += len(diff) > 0
            allbad += (tdiff == 0)
            log(f'  {stim_name:8s} amp 0x{amp:08X}  '
                f'model {n - len(diff)} of {n} bit-exact   '
                f'negative control differs in {tdiff} of {n} '
                f'(predicted {sep})')
            if diff:
                for i in diff[:4]:
                    log(f'      [{i:3d}] x {xs[i]:12d}  part {ys[i]:12d}  '
                        f'model {want[i]:12d}  d {ys[i] - want[i]:+d}')
            break
        else:
            log(f'  {stim_name}: no amplitude produced a usable capture')
    return allbad, measurable, measurable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chip', type=int, default=1)
    ap.add_argument('--strip', type=int, default=1)
    ap.add_argument('--n', type=int, default=96,
                    help='samples per capture (each word is a paced read)')
    ap.add_argument('--nodes', default='GATE,COMP,TUBE,FDR')
    a = ap.parse_args()

    part = Part(a.chip)
    if not part.healthy():
        print('PART NOT HEALTHY (magic, boot stage or a frame count that is '
              'not moving) — no verdict')
        return 3
    drive_strip(part, a.strip)

    total_bad, total_meas = 0, 0
    for name in a.nodes.split(','):
        name = name.strip().upper()
        if name not in NODES:
            print(f'unknown node {name!r}')
            return 3
        bad, meas, _ = run_node(part, name, NODES[name], a.strip, a.n)
        total_bad += bad
        total_meas += meas

    print()
    if total_meas == 0:
        print('NODE VERIFY COULD NOT MEASURE: no stimulus produced a '
              'repeatable capture whose negative control separates. This is '
              'not a pass and not a failure — the run has no verdict.')
        return 2
    if total_bad:
        print(f'NODE VERIFY FAILED: {total_bad} verdicts against '
              f'{total_meas} measurable stimuli')
        return 1
    print(f'NODE VERIFY BIT-EXACT: every captured sample of every node '
          f'matches fixed_ref, and every negative control fired '
          f'({total_meas} stimuli)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
