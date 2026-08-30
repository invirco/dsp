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
from dsp4_conform import (Part, chain_witness, drive_strip, f32, STRIDE,
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
# Reading DM: a zero has to prove the link is alive
# ---------------------------------------------------------------------------
#
# THE FIRST RUN OF THIS TOOL (2026-08-30) WAS SCORED BY THE READER, NOT BY
# THE PART. It used dsp4_conform.agreeing_peek -- two reads that agree --
# and got `_fdr_gq_` = 0 and `_fdr_lq_` = 0 while `_fdr_rq_` came back as
# 0x04000000, which is exactly right for the pan that had just been
# written. Two of three coefficients cannot be wrong in a node that
# computes all three from the same two floats in the same six
# instructions. A DROPPED ANSWER ON THIS LINK READS AS ZERO, and a zero
# agrees with itself as cleanly as a real value does.
#
# dsp4_num_verify.py hit the same thing on 2026-08-29 and solved it the
# same way: vote, and CORROBORATE a zero through the same peek path it
# came from, against a DM word this build is known to hold at a non-zero
# constant. `_scope_len` is that word -- scope.asm initialises it to
# SCOPE_LEN and nothing writes it -- so if the peek path can still fetch
# 1024 from it, a zero at the address in question is the part's answer
# and not the link's.

SENTINEL = {}


def _sentinel_ok(part):
    if not SENTINEL:
        return False
    for _ in range(6):
        try:
            if part.sc.peek(SENTINEL['addr']) == SENTINEL['want']:
                return True
        except IOError:
            return False
    return False


def vpeek(part, addr, need=2, limit=8, rounds=3):
    """A voted peek whose zeros are corroborated. None if it never
    settles -- and None is a REFUSAL TO ANSWER, never a value."""
    for _ in range(rounds):
        seen = {}
        for _ in range(limit):
            try:
                v = part.sc.peek(addr)
            except IOError:
                continue
            seen[v] = seen.get(v, 0) + 1
            if seen[v] >= need:
                if v != 0 or _sentinel_ok(part):
                    return v
                break
        try:
            part.sc.d.resync()
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

def capture(part, src, inj, amp, mode, n, tries=3, log=None):
    """One armed run: rest, arm, wait, read n words from sample 0.

    FROM SAMPLE 0, unlike the bus probe's window at 900. That probe wants
    the graph's SETTLED response; this one wants the graph's response from
    a KNOWN STATE, and sample 0 is the only sample whose state the host
    can read beforehand.
    """
    if src not in part.sc.sym:
        if log:
            log(f'      no symbol {src!r} in this image — cannot capture')
        return None
    last = ''
    for _ in range(tries):
        time.sleep(CAPTURE_REST)
        try:
            part.sc.d.resync()
            part.sc.arm(part.sc.sym[src], inj, amp, mode)
            part.sc.wait()
            out = []
            for i in range(n):
                part.sc.wr(S.SCOPE_RD, i)
                out.append(part.sc.rd(S.SCOPE_DATA))
            return [s32(w) for w in out]
        except (IOError, SystemExit) as exc:
            last = str(exc)
    if log:
        log(f'      capture of {src} failed in {tries} attempts: {last}')
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
            (GATE_HOLD, 8, 0)]


def _gate_model(xs, p, st0, twin=False):
    """Returns the GAIN after each sample, not the product.

    THE GATE'S OUTPUT IS x * gain, so a stimulus that goes quiet hides
    the whole ladder -- the same lesson boundary_vectors learned when its
    scenario gaps were digital silence. The scope can only inject an
    impulse or a step, so a burst-then-quiet stimulus does not exist on
    the part at all, and the close arm cannot be reached through the
    product. It can be reached directly: the scope records ANY DM
    address, so this captures `_gate_gain_` and models the trajectory
    that drives it. That is a stronger reading of D30 than the product
    would have been -- it is the ladder itself."""
    att, rel, thr, rng, hold = p
    st = list(st0) + [0]                  # hold count: see the note above
    step = fr.gate_step_nohold if twin else fr.gate_step
    out = []
    for x in xs:
        step(x, st, att, rel, thr, rng, hold)
        out.append(st[1])
    return out


def _comp_setup(strip):
    """COMP ON with the gate held TRANSPARENT rather than bypassed.

    The obvious setup is `GateOn = 0`, and with it this bar could not
    read the compressor's input at all: on three consecutive boots a
    capture of `_buf_C1_GATE_01` came back at peak 0 on every amplitude,
    while the chain witness taken minutes earlier through the same
    injection read 0x07FFFF07 at that address.

    THE BYPASS PATH IS NOT THE PROBLEM, and that was measured rather than
    assumed (2026-08-30): driving the strip and writing GateOn 1 -> 0 ->
    1 while capturing both `_buf_C1_EQ_01` and `_buf_C1_GATE_01` gives
    221910965 -> 221910965 with the gate OFF -- the input passed through
    BIT-IDENTICALLY -- and 221910965 -> 221910944 with it on, which is
    the settled gain. The bypassed gate carries the signal exactly as its
    emitted `.gate_bypass` arm says it does. The zero captures were the
    instrument, in the recorded link-intermittent class (review finding
    D60), and they are not worked around by pretending otherwise.

    What the setup below does instead is make the gate TRANSPARENT by its
    own controls rather than by its bypass: threshold at the documented
    minimum so it is always open, range 0 dB so its floor IS unity, and
    fast time constants so it settles inside a capture. The node then
    multiplies by exactly 1.0, which is exactly x, so the compressor's
    input is the injected word and the gate is exercised rather than
    skipped."""
    return [(GATE_ON, 1, 0), (GATE_THR, f32(-80.0), 0),
            (GATE_RNG, f32(0.0), 0), (GATE_ATT, f32(0.5), 0),
            (GATE_REL, f32(0.5), 0), (GATE_HOLD, 8, 0),
            (COMP_ON, 1, 0), (TUBE_ON, 0, 0),
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
    """FADER_PAN at an UNTIDY level, not a power of two.

    The node's own output is one MAC and one round-and-saturate, so the
    only thing a capture can separate is the rounding -- and at level 0.5
    or 0.25 the product has no low bits and round-to-nearest gives the
    identical word as truncation. 0.37 and 0.317 put a fraction into
    both the coefficient and the pan legs. (The squared-gain defect this
    node shipped lived in the BUS FEED, which has a pan leg in it;
    `_buf_<FDR>` does not, and the harness tests that form where it
    belongs.)"""
    return [(GATE_ON, 0, 0), (COMP_ON, 0, 0), (TUBE_ON, 0, 0),
            (FDR_LEVEL, f32(0.37), 0), (FDR_PAN, f32(0.317), 0),
            (FDR_MUTE, 0, 0)]


def _fdr_model(xs, p, st0, twin=False):
    """The node's OWN output is one MAC with the level coefficient; the
    pan legs are ROUTING's crosspoint coefficients and appear nowhere in
    `_buf_<FDR>`. The negative control is therefore the rounding, not the
    squared gain -- see fixed_ref.fdr_apply_trunc."""
    gq = p[0]
    f = fr.fdr_apply_trunc if twin else fr.fdr_apply
    return [f(x, gq) for x in xs]


NODES = {
    # name: (input symbol, output symbol, setup, param symbols, state
    #        symbols, model, converted-parameter cross-check, stimuli)
    'GATE': dict(
        inp='_buf_C1_EQ_%02d', out='_gate_gain_C1_GATE_%02d',
        setup=_gate_setup, model=_gate_model,
        params=['_gate_attq_C1_GATE_%02d', '_gate_relq_C1_GATE_%02d',
                '_gate_thrq_C1_GATE_%02d', '_gate_rngq_C1_GATE_%02d',
                '_gate_hold_C1_GATE_%02d'],
        # THE HOLD COUNT IS NOT READ, and that is a property of the
        # ladder rather than a shortcut. It is decremented on EVERY
        # sample the gate spends below threshold and is never floored, so
        # at 48 kHz no voting reader can ever settle it -- and nothing
        # reads its VALUE: the ladder only tests its sign. At rest the
        # gate is closed (which the rest gain below proves, because a
        # closed gate has settled onto the range floor), so the counter
        # is at or below zero, and 0 is the representative of that whole
        # class. The first run of this tool peeked it and got a
        # corroborated-looking 0 for exactly this reason.
        state=['_gate_envelope_C1_GATE_%02d', '_gate_gain_C1_GATE_%02d',
               '_gate_gain_target_q_C1_GATE_%02d'],
        cvt=lambda p: [('gate range floor (D39: dB on the wire)',
                        p[3], fr.gate_range_q(40.0)),
                       ('gate threshold -> Q6.25 log2',
                        p[2], fr.gate_thr_q(-40.0)),
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
        # THE GAIN-COMPUTER PARAMETERS ARE CHECKED, not assumed. The
        # first run left them out and the compressor's twin could not
        # separate on any stimulus -- which is exactly what an all-zero
        # `_comp_cgp_` produces, because a zero threshold and a zero
        # slope give unity gain on every sample, and at unity gain the
        # makeup's second rounding is arithmetically invisible. A
        # parameter the model reads has to be a parameter the run
        # verified.
        cvt=lambda p: [('comp makeup -> Q4.28', p[2],
                        fr.comp_makeup_q(1.37)),
                       ('comp parallel blend (D40: PERCENT on the wire)',
                        p[3], fr.comp_par_q(100.0)),
                       ('comp threshold -> Q6.25 log2', p[4],
                        fr.fix32(fr.f32(fr.f32(-30.0) * fr.F32_DB_LOG2))),
                       ('comp slope (1 - 1/ratio) -> Q0.31', p[5],
                        fr.fix32(fr.f32(fr.f32(0.75) * fr.F32_2P31))),
                       ('comp half-knee (hard knee: zero)', p[6], 0),
                       ('comp k2 (hard knee: zero)', p[7], 0)],
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
        cvt=lambda p: [('fdr level coefficient', p[0],
                        fr.fdr_coeffs(0.37, 0.317, 0)[0]),
                       ('fdr LEFT pan leg (linear law; D42 open)',
                        p[1], fr.fdr_coeffs(0.37, 0.317, 0)[1]),
                       ('fdr RIGHT pan leg', p[2],
                        fr.fdr_coeffs(0.37, 0.317, 0)[2])],
        stim=[('step', 2), ('impulse', 1)],
        why='the pan law and the level coefficient (D31)'),
}

# AMPLITUDES. Untidy words first: the round ones (0x08000000 = -6 dBFS
# exactly) put every intermediate on the Q4.28 grid, which is precisely
# where a dropped rounding is invisible.
AMPS = [0x0D3A17B5, 0x0553C1A7, 0x08000000, 0x1A6F2E93, 0x02000000]


def _candidates(n=192):
    """A deterministic spread of untidy amplitudes between -40 and 0 dBFS.

    A fixed LCG rather than `random`, so two runs of this bar drive the
    part with the same words and a disagreement between them is the part,
    not the stimulus."""
    out, x = [], 0x1234567
    while len(out) < n:
        x = (1103515245 * x + 12345) & 0x7FFFFFFF
        v = 0x00A00000 + (x % 0x07000000)
        if v & 0xFFFF:                      # keep it off the round grid
            out.append(v)
    return out


def choose_amps(spec, p, st0, n, mode, log=print):
    """The amplitudes on which this node's NEGATIVE CONTROL can fire.

    Computed from the model BEFORE the part is driven, which is the only
    honest way to run this: a twin that happens to agree on the stimulus
    proves nothing, and hunting for a separating amplitude by capturing
    is slow AND leaves "no amplitude worked" ambiguous between a bad
    choice and a dead probe. For the stateless nodes the synthetic input
    below IS the captured input (everything upstream is bypassed); for
    the stateful ones it is a close enough proxy to rank candidates, and
    the real capture is checked for separation again before it is scored.

    THE FIRST RUN OF THIS BAR NEEDED THIS. With five hand-picked
    amplitudes, FADER_PAN's round-versus-truncate control fired on none
    of them and the compressor's second-rounding control on none either
    -- not because the arithmetic agrees, but because five words out of
    2^31 is not a search.
    """
    shape = (lambda a: [a] + [0] * (n - 1)) if mode == 1 else \
            (lambda a: [a] * n)
    good = []
    for a in AMPS + _candidates():
        xs = shape(a)
        try:
            if spec['model'](xs, p, st0) != spec['model'](xs, p, st0,
                                                          twin=True):
                good.append(a)
        except Exception:
            continue
        if len(good) >= 3:
            break
    if not good:
        log('  NO amplitude in the search separates this node from its '
            'negative control on this stimulus — the run will say so '
            'rather than report a pass')
    return good


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
        v = vpeek(part, part.sc.sym[name] + off)
        if v is None:
            return None
        # SIGNED. Every word read here is a signed fixed-point quantity,
        # and two of them are always negative: the gate's threshold and
        # the compressor's, both dB below zero in the Q6.25 log2 domain.
        # Returned unsigned they read as ~4.07e9, and a threshold that
        # large is one no envelope can cross -- so the modelled gate
        # never opened, the modelled compressor never left unity gain,
        # and at unity gain the makeup's second rounding is invisible.
        # BOTH nodes then reported "the negative control cannot separate"
        # on every stimulus, which is what sent this bar hunting for a
        # stimulus when the fault was in the reader (2026-08-30).
        out.append(s32(v))
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

    if bad:
        log(f'  {bad} converted parameter(s) do NOT match the model — the '
            f'sample path below would be measuring the wrong coefficients, '
            f'so it is not run for this node')
        return bad, 0, 0

    inj = inject_addr(part, strip)

    # A WARM-UP CAPTURE BEFORE THE STATE IS READ, and the GATE is why.
    # The hold counter is reloaded ONLY when the gate opens, so it still
    # holds whatever the LAST thing to drive this strip left in it -- and
    # `drive_strip` writes GateHold as a float (the standing
    # ms-vs-samples KNOWN_MISMATCH), which the kernel reads as
    # 1,065,353,216 samples, six hours of hold. Measured here 2026-08-30:
    # with the chain witness driving the strip beforehand, the gate was
    # still reading target = unity long after the level had gone, and no
    # stimulus could reach the close arm. One armed capture with the new
    # hold in place reloads the counter with the SHORT value, and the
    # rest that follows every capture then expires it. The state read
    # below is therefore a state the run PUT the node in, not one it
    # hopes to find.
    st = None
    for _ in range(3):
        capture(part, spec['out'] % strip, inj, AMPS[0], 2, 4, tries=2)
        time.sleep(CAPTURE_REST)
        st = read_params(part, spec['state'], strip)
        if name != 'GATE' or st is None or st[2] == p[3]:
            break
        log(f'  gate still open at rest (target {st[2]}, floor {p[3]}) — '
            f'driving it again so the new hold value takes')
    if st is None and spec['state']:
        log('  node state unreadable — no verdict for this node')
        return 0, 0, 0
    st0 = list(st or [])
    if st0:
        log(f'  state at rest: {st0}')
    if name == 'GATE' and st0:
        # AT REST THE GATE MUST BE CLOSED, which means its target has
        # settled onto the range floor. That is the whole basis for
        # modelling the unreadable hold counter as zero: a closed gate is
        # one whose counter has already expired.
        rng = p[3]
        if st0[2] != rng:
            log(f'  the gate is NOT closed at rest (target {st0[2]}, range '
                f'floor {rng}) — its hold counter has not expired, so the '
                f'unreadable counter cannot be modelled. No verdict')
            return 0, 0, 0

    measurable, allbad = 0, bad
    walked = [False]
    for stim_name, mode in spec['stim']:
        amps = choose_amps(spec, p, st0, n, mode, log)
        for amp in amps:
            ys = capture(part, spec['out'] % strip, inj, amp, mode, n, log=log)
            if ys is None:
                continue
            ys2 = capture(part, spec['out'] % strip, inj, amp, mode, n, log=log)
            if ys2 != ys:
                # THE REPEAT IS THE NOISE FLOOR. Two runs of the same
                # stimulus from the same rest must be identical; if they
                # are not, the graph did not come back to rest and no
                # comparison below means anything.
                log(f'  {stim_name} amp 0x{amp:08X}: repeat capture DIFFERS '
                    f'in {sum(a != c for a, c in zip(ys, ys2))} of {n} '
                    f'words — not at rest, trying another amplitude')
                continue
            xs = capture(part, spec['inp'] % strip, inj, amp, mode, n, log=log)
            if xs is None:
                continue
            if max(abs(v) for v in xs) < (amp >> 4):
                # A CAPTURE OF SILENCE IS NOT A RESULT. The injected word
                # is known, so "the input never arrived" is separable from
                # "the twin agrees" and has to be said as itself.
                log(f'  {stim_name} amp 0x{amp:08X}: the injection is NOT '
                    f'reaching {spec["inp"] % strip} (captured peak '
                    f'{max(abs(v) for v in xs)}) — not a verdict')
                if not walked[0]:
                    # WALK THE CHAIN AGAIN, HERE. The witness at the top of
                    # the run was taken before this node's setup writes;
                    # what matters is where the signal stops NOW, with
                    # those writes in place. A node that goes silent when
                    # a neighbour is bypassed is a cell-semantics
                    # question, and it cannot be asked from one witness
                    # taken at a different time.
                    walked[0] = True
                    log('  re-walking the chain with this node\'s setup in '
                        'place:')
                    chain_witness(part, inj, strip)
                continue
            want = spec['model'](xs, p, st0)
            twin = spec['model'](xs, p, st0, twin=True)
            sep = sum(a != c for a, c in zip(want, twin))
            if sep == 0:
                # SAY WHAT THE CAPTURE ACTUALLY HELD. "Cannot separate" is
                # true of a stimulus the twin survives AND of a capture
                # that is silent, and those are completely different
                # problems -- the first is a bad choice of amplitude, the
                # second is a graph that is not carrying the injection at
                # all. The first run of this tool could not tell them
                # apart and reported ten identical lines per node.
                log(f'  {stim_name} amp 0x{amp:08X}: the negative control '
                    f'cannot separate — input peak {max(abs(v) for v in xs)}, '
                    f'output peak {max(abs(v) for v in ys)}; '
                    f'x[0:4] {xs[:4]} y[0:4] {ys[:4]}')
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


# ---------------------------------------------------------------------------
# `_bq_fx_convert_N` on the part (review finding D27)
# ---------------------------------------------------------------------------
#
# This one has no sample path to capture: it is a PARAMETER conversion,
# and it is the routine that shipped the b1 = 0 defect its own header
# documents -- the `fix` destination was r1, which is f1, which held b1,
# so `n1 = b1 + 2*b0` read a destroyed register and every biquad in the
# product silently ran with b1 = 0. Until now the only check on it was
# "happens on the dev box" (dsp4_eq_probe.py's own words).
#
# The strip's four EQ bands take RAW BIQUAD COEFFICIENTS with a swap
# trigger (D51), so the contract path drives the routine directly: write
# four float sets, trigger the swap, wait out the 12 ms crossfade, and
# read the twenty converted words back out of whichever instance is now
# active. The vectors are boundary_vectors.BQCVT -- the same sets the
# harness uses -- so both halves quote the same numbers.

EQ_C0, EQ_SWAP = 0x0010, 0x0024
XFADE_SETTLE = 0.4         # 576 samples of crossfade is 12 ms; this is
                           # thirty times that, plus the link's own latency


def run_bqcvt(part, strip, log=print):
    """Returns (verdicts, groups measured)."""
    import boundary_vectors as bv
    b = (strip - 1) * STRIDE
    log('--- BQCVT: `_bq_fx_convert_N`, the b1 site and the Q = 0.10 corner '
        '(D27)')
    for sym in ('_eq_active_C1_EQ_%02d', '_eq_coeffs_A_C1_EQ_%02d',
                '_eq_coeffs_B_C1_EQ_%02d'):
        if (sym % strip) not in part.sc.sym:
            log(f'  no symbol {sym % strip} — cannot measure')
            return 0, 0
    sets = list(bv.BQCVT)
    unity = (1.0, 0.0, 0.0, 0.0, 0.0, 'pad')
    bad, groups = 0, 0
    for g in range(0, len(sets), 4):
        chunk = (sets[g:g + 4] + [unity] * 4)[:4]
        for band, v in enumerate(chunk):
            for i, c in enumerate(v[:5]):
                part.write(b + EQ_C0 + band * 5 + i, f32(c), 0)
                time.sleep(0.01)
        part.write(b + EQ_SWAP, 1, 0)
        time.sleep(XFADE_SETTLE)
        act = vpeek(part, part.sc.sym['_eq_active_C1_EQ_%02d' % strip])
        if act is None:
            log('  _eq_active unreadable — group skipped')
            continue
        base = part.sc.sym[('_eq_coeffs_B_C1_EQ_%02d' if act else
                            '_eq_coeffs_A_C1_EQ_%02d') % strip]
        words = [vpeek(part, base + k) for k in range(20)]
        if any(w is None for w in words):
            log('  converted set unreadable — group skipped')
            continue
        groups += 1
        for band, v in enumerate(chunk):
            got = tuple(s32(w) for w in words[band * 5:band * 5 + 5])
            want = fr.bq_convert_f32(*v[:5])
            lost = fr.bq_convert_b1_lost(*v[:5])
            ok = got == want
            bad += not ok
            sep = (want != lost)
            fired = (got != lost)
            if sep and not fired:
                bad += 1
            log(f'  {v[5][:46]:46s} {"ok" if ok else "MISMATCH":8s} '
                f'{"b1 control fires" if sep and fired else ("b1 control PASSES (b1 = 0)" if not sep else "b1 CONTROL DID NOT FIRE")}')
            if not ok:
                log(f'      part  {got}')
                log(f'      model {want}')
    # leave the bands where the rest of the run expects them
    for band in range(4):
        for i, c in enumerate(unity[:5]):
            part.write(b + EQ_C0 + band * 5 + i, f32(c), 0)
    part.write(b + EQ_SWAP, 1, 0)
    time.sleep(XFADE_SETTLE)
    return bad, groups


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--chip', type=int, default=1)
    ap.add_argument('--strip', type=int, default=1)
    ap.add_argument('--n', type=int, default=96,
                    help='samples per capture (each word is a paced read)')
    ap.add_argument('--nodes', default='BQCVT,GATE,COMP,TUBE,FDR')
    a = ap.parse_args()

    part = Part(a.chip)
    # Arm the peek path's corroborating sentinel before anything reads a
    # DM word: a zero is only believable while this still answers.
    if '_scope_len' in part.sc.sym:
        want = part.sc.peek(part.sc.sym['_scope_len'])
        if want:
            SENTINEL.update(addr=part.sc.sym['_scope_len'], want=want)
            print(f'  peek sentinel: _scope_len = {want}')
    if not part.healthy():
        print('PART NOT HEALTHY (magic, boot stage or a frame count that is '
              'not moving) — no verdict')
        return 3
    drive_strip(part, a.strip)
    # WHERE DOES THE SIGNAL STOP? A capture of zeros is what a bypassed
    # node, an undriven strip and a dropped arm all look like, so the
    # chain is walked once before any verdict is attempted and the walk is
    # printed whatever it says.
    chain_witness(part, inject_addr(part, a.strip), a.strip)

    total_bad, total_meas = 0, 0
    unmeasured = []
    for name in a.nodes.split(','):
        name = name.strip().upper()
        if name == 'BQCVT':
            bad, meas = run_bqcvt(part, a.strip)
        elif name not in NODES:
            print(f'unknown node {name!r}')
            return 3
        else:
            bad, meas, _ = run_node(part, name, NODES[name], a.strip, a.n)
        total_bad += bad
        total_meas += meas
        if not meas:
            unmeasured.append(name)

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
    if unmeasured:
        # A NODE WITH NO VERDICT IS NOT A NODE THAT PASSED, and a run
        # that reported the two together would be the exact mistake this
        # bench's own checklist warns about: reading a bar's SILENCE as a
        # result. Exit 2 sends the runner round another boot.
        print(f'NODE VERIFY INCOMPLETE: {", ".join(unmeasured)} produced no '
              f'measurable stimulus. The nodes that DID measure are '
              f'bit-exact ({total_meas} stimuli), but this run is not a '
              f'pass for the ones that did not.')
        return 2
    print(f'NODE VERIFY BIT-EXACT: every captured sample of every node '
          f'matches fixed_ref, and every negative control fired '
          f'({total_meas} stimuli)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
