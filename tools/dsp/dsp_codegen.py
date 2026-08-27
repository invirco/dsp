
_COMP_BLK_BODY = """
        #if DSP4_BLOCK_KERNELS
            /* ---- per-block kernel ----
             * Sample 0 goes through the per-sample body with _sample_idx
             * forced to 0, which runs the block-rate makeup ramp and the
             * whole parameter conversion exactly as a per-sample build
             * would -- and avoids duplicating ninety lines of conversion
             * here. Samples 1..31 then run hoisted.
             *
             * The earlier verdict that COMP was not worth converting came
             * from a bare WRAP, which measured 8 % SLOWER, and from a
             * reading that _compgain_fx "clobbers all but four registers".
             * CORRECTED 2026-08-24. An earlier note here claimed r6 also
             * survives, from a scan of _compgain_fx's OWN text. That scan
             * was not transitive: _compgain_fx calls _exp2q_fx, and the
             * polynomial _exp2q_fx reaches r6. Keeping attq in r6 meant
             * the attack alpha was destroyed after the first sample and
             * the envelope follower ran on garbage for the rest of the
             * block -- visible as a compressor output FROZEN from sample 1
             * while a correct build converged smoothly. It never showed in
             * the earlier verification because that ran on a silent bench,
             * where _compgain_fx returns unity before it ever reaches
             * exp2.
             *
             * The survivors across BOTH _envq_fx (r0, r2, r4, r5) and
             * _compgain_fx WITH ITS CALLEES (r0-r6, r8-r12) are r7, r13,
             * r14 and r15 -- which is exactly what the original note on
             * this page said before it was overridden. Four registers, so
             * the release alpha goes back to a DM load per sample. */
            l3 = 0;
            l4 = 0;
            i3 = BLK_CHAIN_A;
            i4 = BLK_CHAIN_B;

            r2 = dm(_comp_on_{nid});
            r2 = pass r2;
            if eq jump (pc, .ckb_copy_{nid});

            r5 = dm(_sample_idx);
            dm(_comp_saved_idx_{nid}) = r5;
            r5 = 0;
            dm(_sample_idx) = r5;
            r0 = dm(i3, 1);
            dm(_buf_{inp}) = r0;
            call _{nid}_process_sample;
            r0 = dm(_buf_{nid});
            dm(i4, 1) = r0;
            r5 = 1;
            dm(_sample_idx) = r5;

            r7 = dm(_comp_attq_{nid});
            r14 = dm(_comp_envelope_{nid});
            r15 = dm(_comp_mkq_{nid});

            lcntr = 31, do .ckb_lp_{nid} until lce;
                r13 = dm(i3, 1);
                r0 = abs r13;
                r1 = r14;
                r2 = r7;                  /* attq */
                r3 = dm(_comp_relq_{nid});
                call _envq_fx;
                r14 = r0;
                i0 = _comp_cgp_{nid};
                call _compgain_fx;
                dm(_comp_gain_{nid}) = r0;
                r1 = r0;
                r0 = r13;
                mrf = r0 * r1 (ssi);
                call _mrf_rns28;
                r1 = r15;
                mrf = r0 * r1 (ssi);
                call _mrf_rns28;
                r5 = r0 - r13;
                r4 = dm(_comp_parq_{nid});
                mrf = r5 * r4 (ssi);
                r1 = 0x40000000;
                r12 = 1;
                mrf = mrf + r1 * r12 (ssi);
                r1 = mr0f;
                r12 = mr1f;
                r1 = lshift r1 by -31;
                r12 = lshift r12 by 1;
                r1 = r1 or r12;
                r0 = r13 + r1;
                nop;
                nop;
            .ckb_lp_{nid}: dm(i4, 1) = r0;

            dm(_comp_envelope_{nid}) = r14;
            r5 = dm(_comp_saved_idx_{nid});
            dm(_sample_idx) = r5;
            rts;

        .ckb_copy_{nid}:
            lcntr = 32, do .ckb_cp_{nid} until lce;
                r0 = dm(i3, 1);
            .ckb_cp_{nid}: dm(i4, 1) = r0;
            rts;

        .global _{nid}_process_sample;
        _{nid}_process_sample:
        #endif
"""

_TUBE_BLK_BODY = """
        #if DSP4_BLOCK_KERNELS
            /* ---- per-block kernel ----
             * The saturation RAMP is per-sample by design (spi_handler
             * scales profile frame counts by 32 for ramps that decrement
             * once per sample), so `sat` -- and therefore sat_q -- changes
             * within the block while a ramp is running. Only the settled
             * case can hoist the conversion, so a ramping TUBE hands the
             * block to the per-sample body. A sat ramp is a transient. */
            l3 = 0;
            l4 = 0;
            i3 = BLK_CHAIN_B;
            i4 = BLK_CHAIN_A;

            r2 = dm(_tube_on_{nid});
            r2 = pass r2;
            if eq jump (pc, .tkb_copy_{nid});
            r4 = dm(_tube_sat_frames_{nid});
            r5 = 1;
            r4 = r4 - r5;
            if gt jump (pc, .tkb_ref_{nid});     /* ramping */

            f3 = dm(_tube_sat_target_{nid});
            dm(_tube_sat_{nid}) = f3;
            r4 = 0x4D800000;
            f4 = r4;
            f3 = f3 * f4;
            r9 = fix f3;                          /* sat_q, hoisted */

            lcntr = 32, do .tkb_lp_{nid} until lce;
                r8 = dm(i3, 1);
                mrf = r8 * r8 (ssi);
                call _mrf_rns28;
                r10 = 0x10000000;
                r10 = r10 - r0;
                mrf = r9 * r10 (ssi);
                call _mrf_rns28;
                r10 = 0x10000000;
                r10 = r10 + r0;
                mrf = r8 * r10 (ssi);
                call _mrf_rns28;
                nop;
                nop;
            .tkb_lp_{nid}: dm(i4, 1) = r0;
            rts;

        .tkb_copy_{nid}:
            lcntr = 32, do .tkb_cp_{nid} until lce;
                r0 = dm(i3, 1);
            .tkb_cp_{nid}: dm(i4, 1) = r0;
            rts;

        .tkb_ref_{nid}:
            lcntr = 32, do .tkb_rl_{nid} until lce;
                r0 = dm(i3, 1);
                dm(_buf_{inp}) = r0;
                call _{nid}_process_sample;
                r0 = dm(_buf_{nid});
            .tkb_rl_{nid}: dm(i4, 1) = r0;
            rts;

        .global _{nid}_process_sample;
        _{nid}_process_sample:
        #endif
"""


_DLY_BLK_BODY = """
        #if DSP4_BLOCK_KERNELS
            /* ---- per-block kernel ----
             * Slot dispatch, read-offset clamp and the write-pointer
             * load/store all happen ONCE instead of 32 times. */
            r12 = dm(_dly_pool_slot_{nid});
            i0 = _dly_buf_{nid};
            i1 = _dly_write_ptr_{nid};
            r3 = dm(_dly_local_max_{nid});

            r13 = pass r12;
            if lt jump (pc, .dkb_io_{nid});
            r14 = 8;
            comp(r12, r14);
            if ge jump (pc, .dkb_io_{nid});
{sel}

        .dkb_io_{nid}:
            r2 = dm(_dly_read_offset_{nid});
            comp(r2, r3);
            if lt jump (pc, .dkb_ok_{nid});
            r2 = r3 - 1;
        .dkb_ok_{nid}:
            r7 = i0;                    /* delay-line base, reloaded per sample */
            r1 = dm(i1, 0);             /* write pointer */
            l3 = 0;
            l4 = 0;
            l5 = 0;
            i3 = BLK_CHAIN_A;
            i4 = BLK_CHAIN_B;
            i5 = BLK_TAP_PREFDR;

            lcntr = 32, do .dkb_lp_{nid} until lce;
                r0 = dm(i3, 1);
                i0 = r7;
                m0 = r1;
                modify(i0, m0);
                dm(i0, 0) = r0;         /* write at the write pointer */
                r5 = r1 - r2;
                if lt r5 = r5 + r3;     /* read index, wrapped */
                r6 = r5 - r1;
                m0 = r6;
                modify(i0, m0);
                r0 = dm(i0, 0);
                r15 = 1;
                r1 = r1 + r15;
                comp(r1, r3);
                if ge r1 = r1 - r3;     /* advance write pointer, wrapped */
                dm(i5, 1) = r0;         /* pre-fader tap */
            .dkb_lp_{nid}: dm(i4, 1) = r0;

            dm(i1, 0) = r1;
            rts;

{labels}
        #endif
"""


_GATE_BLK_BODY = """
        #if DSP4_BLOCK_KERNELS
            /* ---- per-block kernel ----------------------------------
             * Hoisted out of the sample loop: the _sample_idx == 0 guard
             * (evaluated 32 times for work done once), the _gate_on and
             * _gate_filter_on tests, and the four converted parameters,
             * which are block constants but were re-loaded from DM every
             * sample. Envelope, gain, gain target and hold count stay in
             * registers across the block -- _envq_fx, _log2q_fx and
             * _mrf_rns28 all preserve r6-r15, which is what makes that
             * safe. The sidechain biquad does NOT (it clobbers r0-r12),
             * so a gate with its sidechain filter enabled falls back to
             * the per-sample path for the whole block.
             *
             * NOTE the guard cannot simply be kept: under block kernels
             * _sample_idx is 31 when the chain runs, so a _sample_idx == 0
             * test never fires and the parameters would never convert at
             * all. The conversion is done unconditionally, once. */
            l3 = 0;
            l4 = 0;
            i3 = BLK_CHAIN_B;
            i4 = BLK_CHAIN_A;

            r2 = dm(_gate_on_{nid});
            r2 = pass r2;
            if eq jump (pc, .gkb_copy_{nid});
            r2 = dm(_gate_filter_on_{nid});
            r2 = pass r2;
            if ne jump (pc, .gkb_ref_{nid});

            /* block-rate parameter conversion, once */
            r2 = 0x4F000000;
            f2 = r2;
            f1 = dm(_gate_attack_{nid});
            f1 = f1 * f2;
            r1 = fix f1;
            dm(_gate_attq_{nid}) = r1;
            f1 = dm(_gate_release_{nid});
            f1 = f1 * f2;
            r1 = fix f1;
            dm(_gate_relq_{nid}) = r1;
            r2 = 0x4AAA152D;
            f2 = r2;
            f1 = dm(_gate_threshold_{nid});
            f1 = f1 * f2;
            r1 = fix f1;
            dm(_gate_thrq_{nid}) = r1;
            r2 = 0x4D800000;
            f2 = r2;
            f1 = dm(_gate_range_{nid});
            f1 = f1 * f2;
            r1 = fix f1;
            dm(_gate_rngq_{nid}) = r1;

        #if DSP4_GATE_LINTHR
            /* THRESHOLD IN THE LINEAR DOMAIN, ONCE PER BLOCK.
             *
             * GATE computes log2(env) for one purpose only: to compare it
             * against a threshold. That comparison is equivalent in the
             * linear domain -- log2(env) >= thr  <=>  env >= 2^thr -- so
             * the threshold is converted ONCE here instead of the envelope
             * being converted 32 times in the sample loop. It deletes a
             * _log2q_fx call per sample, measured at ~95 cycles/sample.
             *
             * NUMERIC DEVIATION, and it is a small one. Both directions go
             * through the same polynomials, whose worst error over 0 to
             * -100 dBFS is 0.0001 dB (log2_q) and 0.0001 dB (exp2_q), so
             * the gate's EFFECTIVE THRESHOLD shifts by at most 0.0002 dB.
             * That is a fixed offset on the threshold, not per-sample
             * noise, and the linear compare is exact where the log compare
             * carried the polynomial error. Samples whose envelope sits
             * within 0.0002 dB of the threshold may open or close one
             * sample earlier or later; the gain then ramps through a
             * one-pole smoother, so nothing steps.
             *
             * NOT bit-exact against the current fixed_ref, so it needs a
             * numeric-spec amendment and PW's sign-off before it ships.
             *
             * THIS CALL MUST COME BEFORE r6/r7 ARE LOADED. _exp2q_fx
             * clobbers r0-r6, so placing it after the attack/release
             * alphas were in r6/r7 destroyed the attack alpha and the
             * envelope follower ran on garbage -- measured as a 60 dB
             * difference, not the 0.0002 dB the arithmetic predicts. */
            r0 = dm(_gate_thrq_{nid});
            call _exp2q_fx;
            r8 = r0;                      /* 2^thr, Q4.28 linear */
        #else
            r8 = dm(_gate_thrq_{nid});
        #endif
            r6 = dm(_gate_attq_{nid});
            r7 = dm(_gate_relq_{nid});

            r9 = dm(_gate_rngq_{nid});
            r10 = dm(_gate_envelope_{nid});
            r11 = dm(_gate_gain_{nid});
            r12 = dm(_gate_gain_target_q_{nid});
            r14 = dm(_gate_hold_count_{nid});
            r15 = dm(_gate_hold_{nid});

            lcntr = 32, do .gkb_lp_{nid} until lce;
                r13 = dm(i3, 1);
                r0 = abs r13;
                r1 = r10;
                r2 = r6;
                r3 = r7;
                call _envq_fx;
                r10 = r0;
                r1 = pass r0;
                if le jump (pc, .gkb_below_{nid});
        #if DSP4_GATE_LINTHR
                comp(r0, r8);             /* env vs 2^thr, both Q4.28 */
        #else
                call _log2q_fx;
                comp(r0, r8);
        #endif
                if ge jump (pc, .gkb_open_{nid});
            .gkb_below_{nid}:
                r14 = r14 - 1;
                if gt jump (pc, .gkb_ramp_{nid});
                r12 = r9;
                jump (pc, .gkb_ramp_{nid});
            .gkb_open_{nid}:
                r12 = 0x10000000;
                r14 = r15;
            .gkb_ramp_{nid}:
                r0 = r12;
                r1 = r11;
                r2 = r6;
                r3 = r7;
                call _envq_fx;
                r11 = r0;
                r1 = r0;
                r0 = r13;
                mrf = r0 * r1 (ssi);
                call _mrf_rns28;
                nop;
                nop;
            .gkb_lp_{nid}: dm(i4, 1) = r0;

            dm(_gate_envelope_{nid}) = r10;
            dm(_gate_gain_{nid}) = r11;
            dm(_gate_gain_target_q_{nid}) = r12;
            dm(_gate_hold_count_{nid}) = r14;
            rts;

        .gkb_copy_{nid}:
            /* bypassed: the per-sample body just passes x through */
            lcntr = 32, do .gkb_cp_{nid} until lce;
                r0 = dm(i3, 1);
            .gkb_cp_{nid}: dm(i4, 1) = r0;
            rts;

        .gkb_ref_{nid}:
            /* Sidechain filter enabled: hand the block to the per-sample
             * reference path. _sample_idx is driven so its once-per-block
             * conversion fires on the first sample exactly as it would in
             * a per-sample build. */
            r5 = dm(_sample_idx);
            dm(_gate_saved_idx_{nid}) = r5;
            r5 = 0;
            dm(_sample_idx) = r5;
            lcntr = 32, do .gkb_rl_{nid} until lce;
                r0 = dm(i3, 1);
                dm(_buf_{inp}) = r0;
                call _{nid}_process_sample;
                r5 = 1;
                dm(_sample_idx) = r5;
                r0 = dm(_buf_{nid});
            .gkb_rl_{nid}: dm(i4, 1) = r0;
            r5 = dm(_gate_saved_idx_{nid});
            dm(_sample_idx) = r5;
            rts;

        .global _{nid}_process_sample;
        _{nid}_process_sample:
        #endif
"""


_EQ_BLK_BODY = """
        #if DSP4_BLOCK_KERNELS
            /* ---- per-block steady state; transients go per-sample ---- */
            r4 = dm(_eq_swap_pending_{nid});
            r5 = dm(_eq_xfade_step_{nid});
            r4 = r4 or r5;
            r4 = pass r4;
            if eq jump (pc, .ekb_ss_{nid});

            /* Swap pending or fade running: hand the block to the
             * per-sample reference path a sample at a time. */
            l3 = 0;
            l4 = 0;
            l5 = 0;
            i3 = BLK_CHAIN_A;
            i4 = BLK_CHAIN_B;
            i5 = BLK_TAP_EQ;
            lcntr = 32, do .ekb_xl_{nid} until lce;
                r0 = dm(i3, 1);
                dm(_buf_{inp}) = r0;
                call _{nid}_process_sample;
                r0 = dm(_buf_{nid});
                dm(i5, 1) = r0;         /* tap carries the block too */
            .ekb_xl_{nid}: dm(i4, 1) = r0;
            rts;

        .ekb_ss_{nid}:
            /* Steady state, FUSED. FILT left its result in BLK_CHAIN_B and
             * the cascade works in place, so EQ continues on the same slot.
             * The FILT->EQ handoff is zero instructions. */
            l0 = 0;
            l1 = 0;
            l2 = 0;
            l3 = 0;
            l4 = 0;

            r4 = dm(_eq_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .ekb_b_{nid});
            i0 = _eq_coeffs_A_{nid};
            i1 = _eq_state_A_{nid};
            jump (pc, .ekb_go_{nid});
        .ekb_b_{nid}:
            i0 = _eq_coeffs_B_{nid};
            i1 = _eq_state_B_{nid};
        .ekb_go_{nid}:
            i2 = BLK_CHAIN_B;           /* the slot FILT already filtered */
            r4 = {bands};
            call _bq_fx_cascade_blk;

            /* the post-EQ tap the router picks from */
            i3 = BLK_CHAIN_B;
            i4 = BLK_TAP_EQ;
            lcntr = 32, do .ekb_tp_{nid} until lce;
                r0 = dm(i3, 1);
            .ekb_tp_{nid}: dm(i4, 1) = r0;
            rts;

        .global _{nid}_process_sample;
        _{nid}_process_sample:
        #endif
"""


_FILT_BLK_BODY = """
        #if DSP4_BLOCK_KERNELS
            /* ---- per-block steady state; transients go per-sample ---- */
            r4 = dm(_hpf_swap_pending_{nid});
            r5 = dm(_lpf_swap_pending_{nid});
            r4 = r4 or r5;
            r5 = dm(_filt_xfade_step_{nid});
            r4 = r4 or r5;
            r4 = pass r4;
            if eq jump (pc, .fkb_ss_{nid});

            /* A swap is pending or a crossfade is running: run the block
             * through the per-sample reference path, one sample at a time,
             * staging through the scalar buffers it already uses. */
            l3 = 0;
            l4 = 0;
            i3 = BLK_CHAIN_B;
            i4 = BLK_CHAIN_A;
            lcntr = 32, do .fkb_xl_{nid} until lce;
                r0 = dm(i3, 1);
                dm(_buf_{inp}) = r0;
                call _{nid}_process_sample;
                r0 = dm(_buf_{nid});
            .fkb_xl_{nid}: dm(i4, 1) = r0;
            rts;

        .fkb_ss_{nid}:
            /* Steady state, FUSED. The cascade works IN PLACE, so FILT
             * filters its INPUT slot where it stands instead of copying the
             * block to the other half of the ping-pong first. EQ then
             * cascades in place on the same slot, so the FILT->EQ handoff
             * costs nothing at all: no copy, no slot change, no call
             * between them beyond the cascade itself. Two block copies
             * deleted, 4 memory ops per sample. */
            l0 = 0;
            l1 = 0;
            l2 = 0;
            l3 = 0;
            l4 = 0;

            r4 = dm(_filt_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .fkb_b_{nid});
            i0 = _filt_hpf_A_{nid};
            i1 = _filt_state_A_{nid};
            i2 = BLK_CHAIN_B;
            r4 = 2;                     /* HPF and LPF in ONE call: their
                                         * coefficient arrays are adjacent
                                         * and the state array is 2x6, so
                                         * the cascade walks both. */
            call _bq_fx_cascade_blk;
            rts;
        .fkb_b_{nid}:
            i0 = _filt_hpf_B_{nid};
            i1 = _filt_state_B_{nid};
            i2 = BLK_CHAIN_B;
            r4 = 2;
            call _bq_fx_cascade_blk;
            rts;

        .global _{nid}_process_sample;
        _{nid}_process_sample:
        #endif
"""

#!/usr/bin/env python3
"""dsp_codegen.py — Generates SHARC+ ASM skeleton files from dsp.csv (D32).

Usage: python3 dsp_codegen.py [path/to/dsp.csv] [output_dir]
       Default input:  ../dsp.csv (relative to this script)
       Default output: ../src/

Generates:
  src/chip1/nodes/<id>.asm   — per-node ASM skeletons for Chip 1
  src/chip2/nodes/<id>.asm   — per-node ASM skeletons for Chip 2
  src/chip1/process_chain.asm — ordered call sequence for Chip 1
  src/chip2/process_chain.asm — ordered call sequence for Chip 2
  src/ramp_engine.asm         — shared slew/ramp infrastructure
  src/ramp_tables.asm         — ramp profile preset tables

Extends the D24 codegen with:
  - HPF_LPF, GATE, TUBE_SAT, DELAY, FADER_PAN, ROUTING, GEQ, ANTI_FB,
    FX_ENGINE, CROSSOVER, MONITOR, AUX_INPUT, DCA, NOISE_GEN, TALKBACK, METER
  - Slew/ramp profile support (ramp_profile column)
"""

import csv
import re
import sys
import os
from textwrap import dedent

# ===========================================================================
# Ramp profile definitions (from dsp-def.md §3b)
# ===========================================================================
# Frame period = 32 samples / 48000 Hz = 0.6667 ms
FRAME_MS = 32.0 / 48000.0 * 1000.0  # 0.6667 ms

RAMP_PROFILES = {
    'InstantCtl': {
        'mode': 'Instant', 'up_ms': 0, 'down_ms': 0,
        'curve': 'Linear', 'scope': 'Scalar',
    },
    'GainFast': {
        'mode': 'Slew', 'up_ms': 3, 'down_ms': 8,
        'curve': 'Exp', 'scope': 'Scalar',
    },
    'GainSafe': {
        'mode': 'Slew', 'up_ms': 10, 'down_ms': 30,
        'curve': 'Exp', 'scope': 'Scalar',
    },
    'EqSafe': {
        'mode': 'LinearFrames', 'up_ms': 12, 'down_ms': 12,
        'curve': 'Linear', 'scope': 'CoeffSetAtomic',
    },
    'DynSafe': {
        'mode': 'LinearFrames', 'up_ms': 6, 'down_ms': 20,
        'curve': 'Exp', 'scope': 'Scalar',
    },
}

# ===========================================================================
# Dual-instance crossfade constants (CoeffSetAtomic nodes)
# ===========================================================================
# When new biquad coefficients arrive, the dormant instance is loaded and a
# linear crossfade ramps old→new over XFADE_SAMPLES.  This avoids the
# coefficient-interpolation instability that occurs when biquad coefficients
# are slewed individually (intermediate poles can leave the unit circle).
#
# Duration matches the EqSafe ramp profile (12 ms).
XFADE_MS      = 12.0
XFADE_SAMPLES = int(XFADE_MS / 1000.0 * 48000)   # 576 samples @ 48 kHz
XFADE_STEP    = 1.0 / XFADE_SAMPLES               # ≈ 0.001736 per sample

# Audio sample-path format (decision D5): 'fixed' (Q4.28 per
# shared/numeric-spec.md, THE DEFAULT since 2026-07-31) or 'float'
# (the archived FP32 kernels, kept regenerable; also at git tag
# float-kernels-2026-07-31).
FORMAT = 'fixed'


def ms_to_frames(ms):
    """Quantize milliseconds to frame count: max(1, round(ms / 0.6667))."""
    if ms <= 0:
        return 0
    return max(1, round(ms / FRAME_MS))


def ramp_comment(profile_name):
    """Return an ASM comment block describing the ramp profile."""
    if not profile_name or profile_name not in RAMP_PROFILES:
        return '/* RampProfile: Instant (default — no ramp) */'
    p = RAMP_PROFILES[profile_name]
    up_f = ms_to_frames(p['up_ms'])
    dn_f = ms_to_frames(p['down_ms'])
    return (f'/* RampProfile: {profile_name} | Mode: {p["mode"]} | '
            f'Up: {p["up_ms"]}ms ({up_f}f) Down: {p["down_ms"]}ms ({dn_f}f) | '
            f'Curve: {p["curve"]} | Scope: {p["scope"]} */')


# ===========================================================================
# ASM header template
# ===========================================================================
HEADER = """\
/*----------------------------------------------------------------------
 * {label} ({node_type})
 * Node ID:    {node_id}
 * Chip:       {chip}
 * Channels:   {ch_count}
 * SPI Page:   {spi_page}
 * SPI Addr:   {spi_addr}
 * {ramp_line}
 *
 * AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly.
 *----------------------------------------------------------------------*/
"""


# ===========================================================================
# Helpers
# ===========================================================================
def parse_id_list(cell):
    cell = cell.strip().strip('"')
    if not cell:
        return []
    return [x.strip() for x in cell.split(';') if x.strip()]


def parse_params(cell):
    cell = cell.strip().strip('"')
    if not cell:
        return {}
    params = {}
    for pair in cell.split(';'):
        pair = pair.strip()
        if '=' in pair:
            k, v = pair.split('=', 1)
            params[k.strip()] = v.strip()
    return params


# ===========================================================================
# ASM generators — one per node type
# ===========================================================================

def gen_input_tdm(node):
    # A strip input feeds a strip that runs to completion before the next
    # one starts, so those share the pool. Inputs that are NOT part of a
    # strip (XIN_*) are not covered by DSP4_STRIPS and run AFTER the strips
    # in the call chain -- pooling them made them overwrite strip 1's slot
    # after its FILT had already written it, which read as a dead filter.
    import re as _re
    _strip_in = bool(_re.match(r'^C\d+_IN_\d+$', node['id']))
    blk_out_ptr = 'BLK_CHAIN_A' if _strip_in else f"_buf_{node['id']}"
    blk_out_decl = ('.var _buf_' + node['id'] + ';') if _strip_in \
                   else ('.var _buf_' + node['id'] + '[32];')

    p = node['params']
    return dedent(f"""\
        {ramp_comment(node['ramp_profile'])}

        /* INPUT_TDM: Read from SPORT{p.get('sport_id','?')} TDM slot {p.get('slot_start','?')} */

        #include "blk_pool.h"

        .section/dm seg_dmda;
        /* Under block kernels this kernel reads the DMA buffer directly,
         * so the slot var is unreferenced -- kept as a scalar purely so
         * block_io.asm's tables still resolve. */
        .var _rx_slot_{node['id']};
        #if DSP4_BLOCK_KERNELS
        {blk_out_decl}
        #else
        .var _buf_{node['id']};
        #endif

        .section/pm seg_pmco;
        .global _{node['id']}_process;
        _{node['id']}_process:
        #if DSP4_BLOCK_KERNELS
            /* per-BLOCK kernel: one call per block, loop inside */
            l0 = 0;
            l1 = 0;
            /* Read this channel's DMA lane straight into the pool,
             * converting Q1.31 -> Q4.28 on the way. off/stride come from
             * the lane layout, handed to this node by gen_block_io. */
            .extern _rx_active_buf;
            .extern _c1_rx_node_entry;
            .extern _c1_rx_off;
            .extern _c1_rx_stride;
            /* Look the DMA geometry up rather than hardcoding it, so the
             * boot-time input patch still applies. Block rate, not per
             * sample, so it costs nothing measurable. */
            r3 = {p.get('rx_index', 0)};
            m0 = r3;
            i1 = _c1_rx_node_entry;
            modify(i1, m0);
            r3 = dm(i1, 0);               /* my RX table entry */
            m0 = r3;
            i1 = _c1_rx_off;
            modify(i1, m0);
            r3 = dm(i1, 0);               /* off    */
            i1 = _c1_rx_stride;
            modify(i1, m0);
            r4 = dm(i1, 0);               /* stride */
            r6 = dm(_rx_active_buf);
            r3 = r6 + r3;
            i0 = r3;
            m0 = r4;
            i1 = {blk_out_ptr};
        #if DSP4_PROFILE_SIGNAL
            /* Profiling only. The bench has no analog boards and no audio
             * source, so the TDM inputs are silent -- and BOTH dynamics
             * nodes short-circuit on a zero envelope BEFORE they reach
             * log2: _compgain_fx returns unity at `if le jump .cg_unity`
             * and GATE branches to .gate_below. Profiling on silence
             * therefore measures the cheap path and understates GATE and
             * COMP badly. This substitutes a constant -6 dBFS, which is
             * above both the -40 dB gate threshold and the -20 dB
             * compressor threshold, so every node runs the path it runs
             * with real audio. */
            r2 = 0x08000000;
            r5 = 32;
            lcntr = r5; do .in_sig_{node['id']} until lce;
        .in_sig_{node['id']}:
                dm(i1, 1) = r2;
            rts;
        #endif
            r5 = 32;
            lcntr = r5; do .in_lp_{node['id']} until lce;
                r2 = dm(i0, m0);
                r2 = ashift r2 by -3;
                dm(i1, 1) = r2;
        .in_lp_{node['id']}:
                nop;
            rts;
        #else
            r0 = dm(_rx_slot_{node['id']});
            dm(_buf_{node['id']}) = r0;
            rts;
        #endif
        _{node['id']}_process.end:
    """)


def gen_gain(node):
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    return dedent(f"""\
        {rc}

        /* GAIN: Per-channel gain / trim
         *
         * Slew ramp: updated once per block (when _sample_idx == 0).
         * Per-sample: apply current coefficient, polarity, mute.
         * Mute clears output to 0.0 (r4=0 = 0x00000000 = 0.0f IEEE 754).
         */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        .section/dm seg_dmda;
        .var _gain_coeff_{node['id']} = 1.0;
        .var _gain_target_{node['id']} = 1.0;   /* ramp target */
        .var _gain_step_{node['id']} = 0.0;      /* per-frame ramp step */
        .var _gain_frames_{node['id']} = 0;       /* remaining ramp frames */
        .var _mute_{node['id']} = {p.get('mute', '0')};
        .var _polarity_{node['id']} = {p.get('polarity', '0')};
        .var _tap_post_trim_{node['id']};         /* post-trim / pre-EQ tap */
        .var _buf_{node['id']};

        .section/pm seg_pmco;
        .extern _sample_idx;
        .global _{node['id']}_process;
        _{node['id']}_process:
            /* --- Slew ramp: advance once per block, at sample 0 only --- */
            r4 = dm(_sample_idx);
            r1 = 0;
            comp(r4, r1);
            if ne jump (pc, .apply_{node['id']});

            r4 = dm(_gain_frames_{node['id']});
            r1 = 0;
            comp(r4, r1);
            if le jump (pc, .snap_{node['id']});
            /* Ramp in progress: step coefficient, decrement counter */
            r4 = r4 - 1;
            dm(_gain_frames_{node['id']}) = r4;
            f1 = dm(_gain_coeff_{node['id']});
            f2 = dm(_gain_step_{node['id']});
            f1 = f1 + f2;
            dm(_gain_coeff_{node['id']}) = f1;
            jump (pc, .apply_{node['id']});
        .snap_{node['id']}:
            /* Ramp complete or instant: snap to target */
            f1 = dm(_gain_target_{node['id']});
            dm(_gain_coeff_{node['id']}) = f1;

        .apply_{node['id']}:
            r0 = dm(_buf_{node['inputs_str']});
            f1 = dm(_gain_coeff_{node['id']});
            f0 = f0 * f1;                          /* apply gain */

            /* Polarity inversion */
            r3 = dm(_polarity_{node['id']});
            r4 = 0;
            comp(r3, r4);
            if ne f0 = -f0;

            /* Mute: force output to 0.0 */
            r2 = dm(_mute_{node['id']});
            comp(r2, r4);
            if ne r0 = r4;    /* r4 = 0 = 0x00000000 = 0.0f */

            dm(_tap_post_trim_{node['id']}) = r0;
            dm(_buf_{node['id']}) = r0;
            rts;
        _{node['id']}_process.end:
    """)


def gen_hpf_lpf(node):
    """Generate HPF+LPF filter with dual-instance crossfade.

    Two single-biquad filters (HPF then LPF) in series, wrapped in the same
    dual-instance A/B crossfade architecture as gen_eq_biquad.  Each instance
    holds both an HPF and an LPF coefficient set + state.  The SPI staging
    buffers (_hpf_coeffs_next, _lpf_coeffs_next) accept independent updates;
    whichever flag fires first triggers a crossfade that copies BOTH filter
    sets into the dormant instance (current active values for the unchanged
    filter, new values for the updated one).
    """
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    return dedent(f"""\
        {rc}

        /* HPF_LPF: High-pass + Low-pass filter — dual-instance crossfade */
        /* HPF: {p.get('hpf_freq','80')} Hz, slope {p.get('hpf_slope','18')} dB/oct */
        /* LPF: {p.get('lpf_freq','20000')} Hz */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */
        /*
         * Each instance runs HPF→LPF in series (2 biquads total).
         * Crossfade architecture identical to EQ_BIQUAD: dormant instance
         * loaded on swap_pending, {XFADE_SAMPLES}-sample linear blend.
         *
         * When EITHER hpf_swap_pending or lpf_swap_pending fires:
         *   1. Copy active instance's HPF+LPF coeffs to dormant (baseline)
         *   2. Overwrite the pending filter(s) with _next values
         *   3. Zero dormant state, start crossfade
         * This ensures the dormant instance always has a complete, consistent
         * coefficient set even if only one filter was updated.
         */

        .section/dm seg_dmda;

        /* ---- Instance A ---- */
        .var _filt_hpf_A_{nid}[5] = 1.0, 0.0, 0.0, 0.0, 0.0;
        .var _filt_lpf_A_{nid}[5] = 1.0, 0.0, 0.0, 0.0, 0.0;
        .var _filt_state_A_{nid}[4];             /* HPF w1,w2 + LPF w1,w2 */

        /* ---- Instance B ---- */
        .var _filt_hpf_B_{nid}[5] = 1.0, 0.0, 0.0, 0.0, 0.0;
        .var _filt_lpf_B_{nid}[5] = 1.0, 0.0, 0.0, 0.0, 0.0;
        .var _filt_state_B_{nid}[4];

        /* ---- SPI staging buffers ---- */
        .var _hpf_coeffs_next_{nid}[5] = 1.0, 0.0, 0.0, 0.0, 0.0;
        .var _hpf_swap_pending_{nid} = 0;
        .var _lpf_coeffs_next_{nid}[5] = 1.0, 0.0, 0.0, 0.0, 0.0;
        .var _lpf_swap_pending_{nid} = 0;

        /* ---- Crossfade control ---- */
        .var _filt_active_{nid} = 0;             /* 0=A, 1=B */
        .var _filt_xfade_alpha_{nid} = 0.0;
        .var _filt_xfade_step_{nid} = 0.0;       /* 0 = idle */

        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _biquad_mono;
        .global _{nid}_process;
        _{nid}_process:

            /* ── Check swap pending (either filter) ── */
            r4 = dm(_hpf_swap_pending_{nid});
            r4 = pass r4;
            if ne jump .filt_do_xfade_{nid};
            r4 = dm(_lpf_swap_pending_{nid});
            r4 = pass r4;
            if ne jump .filt_do_xfade_{nid};
            jump .filt_mode_check_{nid};
        .filt_do_xfade_{nid}:
            call _filt_start_xfade_{nid};

        .filt_mode_check_{nid}:
            r4 = dm(_filt_xfade_step_{nid});
            r4 = pass r4;
            if ne jump .filt_xfade_{nid};

            /* ═══ STEADY STATE ══════════════════════════════════════ */
            r0 = dm(_buf_{inp});
            r4 = dm(_filt_active_{nid});
            r4 = pass r4;
            if ne jump .filt_ss_B_{nid};
            /* Instance A */
            i0 = _filt_hpf_A_{nid};   i1 = _filt_state_A_{nid};
            call _biquad_mono;                   /* HPF */
            i0 = _filt_lpf_A_{nid};             /* i1 already at LPF state */
            call _biquad_mono;                   /* LPF */
            dm(_buf_{nid}) = r0;
            rts;
        .filt_ss_B_{nid}:
            i0 = _filt_hpf_B_{nid};   i1 = _filt_state_B_{nid};
            call _biquad_mono;
            i0 = _filt_lpf_B_{nid};
            call _biquad_mono;
            dm(_buf_{nid}) = r0;
            rts;

            /* ═══ CROSSFADE ═════════════════════════════════════════ */
        .filt_xfade_{nid}:
            r0 = dm(_buf_{inp});
            f15 = f0;                            /* save input */

            /* ── Active (old) instance: HPF → LPF ── */
            r4 = dm(_filt_active_{nid});
            r4 = pass r4;
            if ne jump .filt_xf_actB_{nid};
            i0 = _filt_hpf_A_{nid};   i1 = _filt_state_A_{nid};
            call _biquad_mono;
            i0 = _filt_lpf_A_{nid};
            call _biquad_mono;
            jump .filt_xf_act_done_{nid};
        .filt_xf_actB_{nid}:
            i0 = _filt_hpf_B_{nid};   i1 = _filt_state_B_{nid};
            call _biquad_mono;
            i0 = _filt_lpf_B_{nid};
            call _biquad_mono;
        .filt_xf_act_done_{nid}:
            f13 = f0;                            /* old output */

            /* ── Inactive (new) instance: HPF → LPF ── */
            f0 = f15;                            /* reload input */
            r4 = dm(_filt_active_{nid});
            r4 = pass r4;
            if eq jump .filt_xf_inB_{nid};
            i0 = _filt_hpf_A_{nid};   i1 = _filt_state_A_{nid};
            call _biquad_mono;
            i0 = _filt_lpf_A_{nid};
            call _biquad_mono;
            jump .filt_xf_in_done_{nid};
        .filt_xf_inB_{nid}:
            i0 = _filt_hpf_B_{nid};   i1 = _filt_state_B_{nid};
            call _biquad_mono;
            i0 = _filt_lpf_B_{nid};
            call _biquad_mono;
        .filt_xf_in_done_{nid}:
            /* f0 = new output */

            /* ── Blend + advance ── */
            f14 = dm(_filt_xfade_alpha_{nid});
            r15 = 0x3F800000;  /* 1.0 IEEE 754 */
            f15 = f15 - f14;
            f13 = f13 * f15;                    /* old × (1−α) */
            f0 = f0 * f14;                      /* new × α */
            f0 = f0 + f13;

            f14 = dm(_filt_xfade_alpha_{nid});
            f15 = dm(_filt_xfade_step_{nid});
            f14 = f14 + f15;
            dm(_filt_xfade_alpha_{nid}) = f14;
            r15 = 0x3F800000;  /* 1.0 IEEE 754 */
            comp(f14, f15);
            if ge call _filt_xfade_done_{nid};

            dm(_buf_{nid}) = f0;
            rts;

        /* ── Start crossfade ── */
        _filt_start_xfade_{nid}:
            /* Determine dormant instance */
            r4 = dm(_filt_active_{nid});
            r4 = pass r4;
            if ne jump .filt_sxf_toA_{nid};

            /* Active=A → dormant=B:
             * 1. Copy active HPF/LPF coeffs to B (baseline)
             * 2. Overwrite with any pending _next values
             * 3. Zero state B */
            /* Copy A's HPF → B's HPF */
            i0 = _filt_hpf_A_{nid};  i1 = _filt_hpf_B_{nid};
            r4 = 5;
            lcntr = r4; do .fc1_{nid} until lce;
                r0 = dm(i0, 1); dm(i1, 1) = r0;
            .fc1_{nid}:
            /* Copy A's LPF → B's LPF */
            i0 = _filt_lpf_A_{nid};  i1 = _filt_lpf_B_{nid};
            r4 = 5;
            lcntr = r4; do .fc2_{nid} until lce;
                r0 = dm(i0, 1); dm(i1, 1) = r0;
            .fc2_{nid}:
            /* Overwrite pending HPF? */
            r4 = dm(_hpf_swap_pending_{nid});
            r4 = pass r4;
            if eq jump .filt_sxf_nohpfB_{nid};
            i0 = _hpf_coeffs_next_{nid};  i1 = _filt_hpf_B_{nid};
            r4 = 5;
            lcntr = r4; do .fc3_{nid} until lce;
                r0 = dm(i0, 1); dm(i1, 1) = r0;
            .fc3_{nid}:
        .filt_sxf_nohpfB_{nid}:
            /* Overwrite pending LPF? */
            r4 = dm(_lpf_swap_pending_{nid});
            r4 = pass r4;
            if eq jump .filt_sxf_nolpfB_{nid};
            i0 = _lpf_coeffs_next_{nid};  i1 = _filt_lpf_B_{nid};
            r4 = 5;
            lcntr = r4; do .fc4_{nid} until lce;
                r0 = dm(i0, 1); dm(i1, 1) = r0;
            .fc4_{nid}:
        .filt_sxf_nolpfB_{nid}:
            /* Zero state B */
            i1 = _filt_state_B_{nid};
            r0 = 0;
            r4 = 4;
            lcntr = r4; do .fz1_{nid} until lce;
                dm(i1, 1) = r0;
            .fz1_{nid}:
            nop;
            jump .filt_sxf_go_{nid};

        .filt_sxf_toA_{nid}:
            /* Active=B → dormant=A: same pattern, copy B→A, overlay _next */
            i0 = _filt_hpf_B_{nid};  i1 = _filt_hpf_A_{nid};
            r4 = 5;
            lcntr = r4; do .fc5_{nid} until lce;
                r0 = dm(i0, 1); dm(i1, 1) = r0;
            .fc5_{nid}:
            i0 = _filt_lpf_B_{nid};  i1 = _filt_lpf_A_{nid};
            r4 = 5;
            lcntr = r4; do .fc6_{nid} until lce;
                r0 = dm(i0, 1); dm(i1, 1) = r0;
            .fc6_{nid}:
            r4 = dm(_hpf_swap_pending_{nid});
            r4 = pass r4;
            if eq jump .filt_sxf_nohpfA_{nid};
            i0 = _hpf_coeffs_next_{nid};  i1 = _filt_hpf_A_{nid};
            r4 = 5;
            lcntr = r4; do .fc7_{nid} until lce;
                r0 = dm(i0, 1); dm(i1, 1) = r0;
            .fc7_{nid}:
        .filt_sxf_nohpfA_{nid}:
            r4 = dm(_lpf_swap_pending_{nid});
            r4 = pass r4;
            if eq jump .filt_sxf_nolpfA_{nid};
            i0 = _lpf_coeffs_next_{nid};  i1 = _filt_lpf_A_{nid};
            r4 = 5;
            lcntr = r4; do .fc8_{nid} until lce;
                r0 = dm(i0, 1); dm(i1, 1) = r0;
            .fc8_{nid}:
        .filt_sxf_nolpfA_{nid}:
            i1 = _filt_state_A_{nid};
            r0 = 0;
            r4 = 4;
            lcntr = r4; do .fz2_{nid} until lce;
                dm(i1, 1) = r0;
            .fz2_{nid}:

        .filt_sxf_go_{nid}:
            /* Clear both pending flags */
            r0 = 0;
            dm(_hpf_swap_pending_{nid}) = r0;
            dm(_lpf_swap_pending_{nid}) = r0;
            /* Start crossfade */
            dm(_filt_xfade_alpha_{nid}) = r0;
            f0 = {XFADE_STEP};
            dm(_filt_xfade_step_{nid}) = f0;
            rts;
        _filt_start_xfade_{nid}.end:

        /* ── Crossfade complete ── */
        _filt_xfade_done_{nid}:
            r4 = dm(_filt_active_{nid});
            r5 = 1;
            r4 = r4 xor r5;
            dm(_filt_active_{nid}) = r4;
            r4 = 0;
            dm(_filt_xfade_alpha_{nid}) = r4;
            dm(_filt_xfade_step_{nid}) = r4;
            rts;
        _filt_xfade_done_{nid}.end:

        _{nid}_process.end:
    """)


def gen_eq_biquad(node):
    """Generate a dual-instance crossfade EQ biquad cascade.

    Architecture overview (CoeffSetAtomic):
    ──────────────────────────────────────
    Two identical N-band biquad cascades (Instance A and Instance B) share
    the same audio input.  At any time one instance is "active" (producing
    output) and the other is "dormant" (not processing).

    When H1S1 sends a new coefficient set via SPI:
      1. SPI ISR writes word-by-word into the _coeffs_next staging buffer.
      2. After the last word, ISR sets _swap_pending = 1.
      3. At the top of the next process call, the node detects the flag,
         copies _coeffs_next → dormant instance, zeros its biquad state,
         and begins a linear crossfade ramp (α: 0 → 1) over XFADE_SAMPLES
         (576 samples = 12 ms at 48 kHz).
      4. During crossfade both cascades run; the output is blended:
             out = (1 − α) × active_out + α × dormant_out
      5. When α ≥ 1.0, the dormant instance becomes the new active, and
         the ramp resets to idle (step = 0).

    Steady-state cost: 1 compare + branch (~2 cycles).
    Crossfade cost:    2× biquad cascade + 3 MACs for blend.
    """
    p = node['params']
    bands = int(p.get('bands', '4'))
    n5 = bands * 5      # coefficient words per instance
    n2 = bands * 2      # state words per instance
    rc = ramp_comment(node['ramp_profile'])
    bypass = ', '.join(['1.0, 0.0, 0.0, 0.0, 0.0'] * bands)
    nid = node['id']
    inp = node['inputs_str']
    return dedent(f"""\
        {rc}

        /* EQ_BIQUAD: {bands}-band parametric EQ — dual-instance crossfade */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */
        /*
         * Dual-instance crossfade (CoeffSetAtomic scope):
         *   Two parallel {bands}-stage biquad cascades (A/B) with independent
         *   coefficients and state.  Only the active instance runs in steady
         *   state.  When SPI delivers new coefficients, the dormant instance
         *   is loaded, its state zeroed, and a {XFADE_SAMPLES}-sample linear
         *   crossfade ({XFADE_MS} ms) blends old → new.
         *
         *   This eliminates coefficient-interpolation instability for large
         *   EQ frequency sweeps — each instance always holds a self-consistent
         *   coefficient set; no intermediate poles are generated.
         *
         * Register contract (biquad.asm): f13–f15 are preserved across
         * _biquad_cascade_N calls (lib clobbers f1–f12 only).
         */

        .section/dm seg_dmda;

        /* ---- Instance A: coefficients + biquad state ---- */
        .var _eq_coeffs_A_{nid}[{n5}] = {bypass};
        .var _eq_state_A_{nid}[{n2}];

        /* ---- Instance B: coefficients + biquad state ---- */
        .var _eq_coeffs_B_{nid}[{n5}] = {bypass};
        .var _eq_state_B_{nid}[{n2}];

        /* ---- SPI staging buffer (ISR writes here word-by-word) ---- */
        .var _eq_coeffs_next_{nid}[{n5}];
        .var _eq_swap_pending_{nid} = 0;

        /* ---- Crossfade control ---- */
        .var _eq_active_{nid} = 0;            /* 0 = A active, 1 = B active */
        .var _eq_xfade_alpha_{nid} = 0.0;     /* blend: 0.0 = all old, 1.0 = all new */
        .var _eq_xfade_step_{nid} = 0.0;      /* per-sample α increment (0 = idle) */

        .var _tap_post_eq_{nid};              /* post-EQ tap */
        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _biquad_cascade_N;
        .global _{nid}_process;
        _{nid}_process:

            /* ── 1. Check for new coefficients from SPI ──────────────── */
            r4 = dm(_eq_swap_pending_{nid});
            r4 = pass r4;
            if ne call _eq_start_xfade_{nid};

            /* ── 2. Crossfade or steady-state? ───────────────────────── */
            /*    IEEE-754 +0.0 is all-zero bits, so integer pass/zero   */
            /*    test correctly detects the idle (no-crossfade) state.   */
            r4 = dm(_eq_xfade_step_{nid});
            r4 = pass r4;
            if ne jump .eq_xfade_{nid};

            /* ═══ STEADY STATE: active instance only ═════════════════ */
            r0 = dm(_buf_{inp});
            r4 = dm(_eq_active_{nid});
            r4 = pass r4;
            if ne jump .eq_ss_B_{nid};
            i0 = _eq_coeffs_A_{nid};
            i1 = _eq_state_A_{nid};
            jump .eq_ss_run_{nid};
        .eq_ss_B_{nid}:
            i0 = _eq_coeffs_B_{nid};
            i1 = _eq_state_B_{nid};
        .eq_ss_run_{nid}:
            r4 = {bands};
            call _biquad_cascade_N;
            dm(_tap_post_eq_{nid}) = r0;
            dm(_buf_{nid}) = r0;
            rts;

            /* ═══ CROSSFADE: both instances + linear blend ═══════════ */
        .eq_xfade_{nid}:
            r0 = dm(_buf_{inp});
            f15 = f0;                            /* save input (preserved) */

            /* ── Run active (old) instance ── */
            r4 = dm(_eq_active_{nid});
            r4 = pass r4;
            if ne jump .eq_xf_actB_{nid};
            i0 = _eq_coeffs_A_{nid};
            i1 = _eq_state_A_{nid};
            jump .eq_xf_act_run_{nid};
        .eq_xf_actB_{nid}:
            i0 = _eq_coeffs_B_{nid};
            i1 = _eq_state_B_{nid};
        .eq_xf_act_run_{nid}:
            r4 = {bands};
            call _biquad_cascade_N;
            f13 = f0;                            /* f13 = old output (preserved) */

            /* ── Run inactive (new) instance ── */
            f0 = f15;                            /* reload input */
            r4 = dm(_eq_active_{nid});
            r4 = pass r4;
            if eq jump .eq_xf_inB_{nid};        /* active=A → inactive=B */
            i0 = _eq_coeffs_A_{nid};
            i1 = _eq_state_A_{nid};
            jump .eq_xf_in_run_{nid};
        .eq_xf_inB_{nid}:
            i0 = _eq_coeffs_B_{nid};
            i1 = _eq_state_B_{nid};
        .eq_xf_in_run_{nid}:
            r4 = {bands};
            call _biquad_cascade_N;
            /* f0 = new output */

            /* ── Blend: out = (1 − α) × old + α × new ── */
            f14 = dm(_eq_xfade_alpha_{nid});     /* α */
            r15 = 0x3F800000;  /* 1.0 IEEE 754 */
            f15 = f15 - f14;                     /* 1 − α */
            f13 = f13 * f15;                     /* old × (1 − α) */
            f0 = f0 * f14;                       /* new × α */
            f0 = f0 + f13;                       /* blended output */

            /* ── Advance α ── */
            f14 = dm(_eq_xfade_alpha_{nid});
            f15 = dm(_eq_xfade_step_{nid});
            f14 = f14 + f15;                     /* α += step */
            dm(_eq_xfade_alpha_{nid}) = f14;

            /* ── Check completion ── */
            r15 = 0x3F800000;  /* 1.0 IEEE 754 */
            comp(f14, f15);
            if ge call _eq_xfade_done_{nid};

            dm(_tap_post_eq_{nid}) = f0;
            dm(_buf_{nid}) = f0;
            rts;

        /* ── Start crossfade: load dormant instance with new coefficients ── */
        _eq_start_xfade_{nid}:
            /* Clear pending flag */
            r4 = 0;
            dm(_eq_swap_pending_{nid}) = r4;

            /* Determine dormant instance and copy coeffs_next into it */
            r4 = dm(_eq_active_{nid});
            r4 = pass r4;
            if ne jump .eq_sxf_toA_{nid};

            /* Active=A → dormant=B: copy coeffs, zero state */
            i0 = _eq_coeffs_next_{nid};
            i1 = _eq_coeffs_B_{nid};
            r4 = {n5};
            lcntr = r4; do .eq_cp_B_{nid} until lce;
                r0 = dm(i0, 1);
                dm(i1, 1) = r0;
            .eq_cp_B_{nid}:
            i1 = _eq_state_B_{nid};
            r0 = 0;                              /* 0x00000000 = float 0.0 */
            r4 = {n2};
            lcntr = r4; do .eq_zs_B_{nid} until lce;
                dm(i1, 1) = r0;
            .eq_zs_B_{nid}:
            nop;                                 /* pipeline gap: no branch within 2 insns of loop end */
            jump .eq_sxf_go_{nid};

        .eq_sxf_toA_{nid}:
            /* Active=B → dormant=A: copy coeffs, zero state */
            i0 = _eq_coeffs_next_{nid};
            i1 = _eq_coeffs_A_{nid};
            r4 = {n5};
            lcntr = r4; do .eq_cp_A_{nid} until lce;
                r0 = dm(i0, 1);
                dm(i1, 1) = r0;
            .eq_cp_A_{nid}:
            i1 = _eq_state_A_{nid};
            r0 = 0;
            r4 = {n2};
            lcntr = r4; do .eq_zs_A_{nid} until lce;
                dm(i1, 1) = r0;
            .eq_zs_A_{nid}:

        .eq_sxf_go_{nid}:
            /* Initiate crossfade ramp: α = 0, step = 1/576 */
            r0 = 0;
            dm(_eq_xfade_alpha_{nid}) = r0;
            f0 = {XFADE_STEP};
            dm(_eq_xfade_step_{nid}) = f0;
            rts;
        _eq_start_xfade_{nid}.end:

        /* ── Crossfade complete: flip active instance, go idle ── */
        _eq_xfade_done_{nid}:
            /* Toggle active: 0→1 or 1→0 (uses r4/r5 only — f0 preserved) */
            r4 = dm(_eq_active_{nid});
            r5 = 1;
            r4 = r4 xor r5;
            dm(_eq_active_{nid}) = r4;
            /* Reset crossfade to idle */
            r4 = 0;                              /* 0x00000000 = float 0.0 */
            dm(_eq_xfade_alpha_{nid}) = r4;
            dm(_eq_xfade_step_{nid}) = r4;       /* step=0 → idle */
            rts;
        _eq_xfade_done_{nid}.end:

        _{nid}_process.end:
    """)


def gen_gate(node):
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    return dedent(f"""\
        {rc}

        /* GATE: Noise gate with sidechain key routing */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */
        /* thr={p.get('threshold_db','-40')}dB att={p.get('attack_ms','1')}ms */
        /* hold={p.get('hold_ms','50')}ms rel={p.get('release_ms','100')}ms */
        /* range={p.get('range_db','60')}dB key={p.get('key','0')} det_src={p.get('det_src','0')} */

        .section/dm seg_dmda;
        .var _gate_on_{node['id']} = 1;
        .var _gate_threshold_{node['id']};
        .var _gate_attack_{node['id']};
        .var _gate_hold_{node['id']};
        .var _gate_release_{node['id']};
        .var _gate_range_{node['id']};         /* linear attenuation floor */
        .var _gate_key_src_{node['id']} = 0;   /* 0=self, 1-32=ext channel */
        .var _gate_det_src_{node['id']} = 0;   /* 0=pre-EQ, 1=post-EQ */
        .var _gate_filter_on_{node['id']} = 0;
        .var _gate_filter_hpf_{node['id']}[5] = 1.0, 0.0, 0.0, 0.0, 0.0; /* sidechain HPF */
        .var _gate_filter_lpf_{node['id']}[5] = 1.0, 0.0, 0.0, 0.0, 0.0; /* sidechain LPF */
        .var _gate_filter_state_{node['id']}[4]; /* HPF+LPF state */
        .var _gate_envelope_{node['id']} = 0.0;
        .var _gate_hold_count_{node['id']} = 0;
        .var _gate_gain_{node['id']} = 1.0;    /* current gate gain (0..1) */
        .var _gate_gain_target_{node['id']} = 1.0;
        .var _gate_gain_step_{node['id']} = 0.0; /* ramp step for gain smoothing */
        .var _buf_{node['id']};

        .section/pm seg_pmco;
        .extern _sample_idx;
        .extern _biquad_mono;
        .extern _dyn_envelope_follow;
        .extern _dyn_to_dB;
        .global _{node['id']}_process;
        _{node['id']}_process:
            r0 = dm(_buf_{node['inputs_str']});
            /* --- Bypass --- */
            r2 = dm(_gate_on_{node['id']});
            r3 = 0;
            comp(r2, r3);
            if eq jump (pc, .gate_bypass_{node['id']});
            f15 = f0;                   /* save dry input */

            /* --- Gate sidechain detection --- */
            f0 = abs f0;                /* rectify for peak detect */

            /* Sidechain filter (HPF+LPF on key signal) */
            r2 = dm(_gate_filter_on_{node['id']});
            r2 = pass r2;
            if eq jump (pc, .gate_no_filt_{node['id']});
            i0 = _gate_filter_hpf_{node['id']};
            i1 = _gate_filter_state_{node['id']};
            call _biquad_mono;
            f0 = abs f0;
            i0 = _gate_filter_lpf_{node['id']};
            i1 = _gate_filter_state_{node['id']} + 2;
            call _biquad_mono;
            f0 = abs f0;
        .gate_no_filt_{node['id']}:

            /* Peak envelope follower */
            f1 = dm(_gate_attack_{node['id']});
            f2 = dm(_gate_release_{node['id']});
            f3 = dm(_gate_envelope_{node['id']});
            call _dyn_envelope_follow;
            dm(_gate_envelope_{node['id']}) = f0;

            /* Convert envelope to dB, compare to threshold */
            call _dyn_to_dB;
            f14 = f0;                   /* env_dB (safe: f14 not clobbered) */
            f1 = dm(_gate_threshold_{node['id']});
            comp(f14, f1);
            if ge jump (pc, .gate_open_{node['id']});

            /* Below threshold → decrement hold counter */
            r4 = dm(_gate_hold_count_{node['id']});
            r15 = 1;
            r4 = r4 - r15;
            dm(_gate_hold_count_{node['id']}) = r4;  /* always write (negative = expired) */
            if gt jump (pc, .gate_ramp_{node['id']});
            /* Hold expired → close to range floor */
            f5 = dm(_gate_range_{node['id']});
            dm(_gate_gain_target_{node['id']}) = f5;
            jump (pc, .gate_ramp_{node['id']});

        .gate_open_{node['id']}:
            /* Above threshold → open, reset hold counter */
            r5 = 0x3F800000;  /* 1.0 IEEE 754 */
            dm(_gate_gain_target_{node['id']}) = f5;
            r4 = dm(_gate_hold_{node['id']});
            dm(_gate_hold_count_{node['id']}) = r4;

        .gate_ramp_{node['id']}:
            /* One-pole gain smoother toward target */
            f4 = dm(_gate_gain_{node['id']});
            f5 = dm(_gate_gain_target_{node['id']});
            f6 = f5 - f4;              /* delta */
            f7 = dm(_gate_attack_{node['id']});
            f8 = dm(_gate_release_{node['id']});
            r10 = 0;
            comp(r6, r10);
            if ge f9 = f7;             /* opening: attack coeff */
            if lt f9 = f8;             /* closing: release coeff */
            f6 = f6 * f9;
            f4 = f4 + f6;
            dm(_gate_gain_{node['id']}) = f4;

            /* Apply gate gain to dry signal */
            f0 = f15;
            f0 = f0 * f4;
            dm(_buf_{node['id']}) = r0;
            rts;
        .gate_bypass_{node['id']}:
            dm(_buf_{node['id']}) = r0;
            rts;
        _{node['id']}_process.end:
    """)


def gen_compressor(node):
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    return dedent(f"""\
        {rc}

        /* COMPRESSOR: Dynamics processing with sidechain */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */
        /* thr={p.get('threshold_db','-20')}dB ratio={p.get('ratio','4.0')} */
        /* att={p.get('attack_ms','5')}ms rel={p.get('release_ms','100')}ms */
        /* knee={p.get('knee_db','6')}dB makeup={p.get('makeup_db','0')}dB */
        /* type={p.get('type','VCA')} parallel={p.get('parallel','0')}% */

        .section/dm seg_dmda;
        .var _comp_on_{node['id']} = 1;
        .var _comp_threshold_{node['id']};
        .var _comp_ratio_{node['id']};
        .var _comp_attack_{node['id']};
        .var _comp_release_{node['id']};
        .var _comp_makeup_{node['id']} = 1.0;
        .var _comp_makeup_target_{node['id']} = 1.0;
        .var _comp_makeup_step_{node['id']} = 0.0;
        .var _comp_makeup_frames_{node['id']} = 0;
        .var _comp_knee_{node['id']} = 0.0;   /* hard knee until the host sets it */
        .var _comp_parallel_{node['id']} = 0.0;
        .var _comp_type_{node['id']} = 0;       /* 0=VCA, 1=FET, 2=Tube, 3=Optical */
        .var _comp_key_src_{node['id']} = 0;
        .var _comp_det_src_{node['id']} = 0;
        .var _comp_eq_pos_{node['id']} = 0;     /* 0=pre-comp, 1=post-comp */
        .var _comp_lim_mode_{node['id']} = 0;   /* 0=comp, 1=limiter */
        .var _comp_filter_on_{node['id']} = 0;
        .var _comp_filter_coeffs_{node['id']}[10]; /* HPF+LPF sidechain */
        .var _comp_filter_state_{node['id']}[4];
        .var _comp_envelope_{node['id']} = 0.0;
        .var _comp_gain_{node['id']} = 1.0;
        .var _buf_{node['id']};

        .section/pm seg_pmco;
        .extern _sample_idx;
        .extern _dyn_envelope_follow;
        .extern _dyn_to_dB;
        .extern _dyn_from_dB;
        .extern _dyn_gain_compute;
        .global _{node['id']}_process;
        _{node['id']}_process:
            r0 = dm(_buf_{node['inputs_str']});
            /* --- Bypass --- */
            r2 = dm(_comp_on_{node['id']});
            r3 = 0;
            comp(r2, r3);
            if eq jump (pc, .comp_bypass_{node['id']});
            f15 = f0;                   /* save dry input for parallel blend */

            /* --- Ramp makeup gain: once per block (sample 0 only) --- */
            r4 = dm(_sample_idx);
            r1 = 0;
            comp(r4, r1);
            if ne jump (pc, .comp_go_{node['id']});
            r4 = dm(_comp_makeup_frames_{node['id']});
            comp(r4, r1);
            if le jump (pc, .no_mramp_{node['id']});
            r4 = r4 - 1;
            dm(_comp_makeup_frames_{node['id']}) = r4;
            f1 = dm(_comp_makeup_{node['id']});
            f2 = dm(_comp_makeup_step_{node['id']});
            f1 = f1 + f2;
            dm(_comp_makeup_{node['id']}) = f1;
            jump (pc, .comp_go_{node['id']});
        .no_mramp_{node['id']}:
            f1 = dm(_comp_makeup_target_{node['id']});
            dm(_comp_makeup_{node['id']}) = f1;
        .comp_go_{node['id']}:

            /* --- Sidechain detection --- */
            f0 = abs f15;              /* rectify input for detection */

            /* Peak envelope follower */
            f1 = dm(_comp_attack_{node['id']});
            f2 = dm(_comp_release_{node['id']});
            f3 = dm(_comp_envelope_{node['id']});
            call _dyn_envelope_follow;
            dm(_comp_envelope_{node['id']}) = f0;

            /* Convert to dB */
            call _dyn_to_dB;

            /* Gain computation (log domain with soft knee) */
            f1 = dm(_comp_threshold_{node['id']});
            f2 = dm(_comp_ratio_{node['id']});
            f3 = dm(_comp_knee_{node['id']});
            call _dyn_gain_compute;
            /* f0 = gain reduction in dB (negative or zero) */

            /* Convert gain reduction to linear */
            call _dyn_from_dB;
            f14 = f0;                  /* gain_linear (safe register) */
            dm(_comp_gain_{node['id']}) = f14;

            /* Apply to signal: wet = dry * gain * makeup */
            f0 = f15;                  /* dry input */
            f0 = f0 * f14;            /* apply gain reduction */
            f1 = dm(_comp_makeup_{node['id']});
            f0 = f0 * f1;             /* apply makeup */

            /* Parallel blend: out = dry * (1-par) + wet * par */
            f2 = dm(_comp_parallel_{node['id']});
            r3 = 0x3F800000;  /* 1.0 IEEE 754 */
            f3 = f3 - f2;             /* 1 - parallel */
            f4 = f15 * f3;            /* dry * (1-par) */
            f0 = f0 * f2;             /* wet * par */
            f0 = f0 + f4;             /* blended output */

            dm(_buf_{node['id']}) = r0;
            rts;
        .comp_bypass_{node['id']}:
            dm(_buf_{node['id']}) = r0;
            rts;
        _{node['id']}_process.end:
    """)


def gen_tube_sat(node):
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    return dedent(f"""\
        {rc}

        /* TUBE_SAT: Tube saturation waveshaper */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        .section/dm seg_dmda;
        .var _tube_on_{node['id']} = 0;
        .var _tube_sat_{node['id']} = 0.0;
        .var _tube_sat_target_{node['id']} = 0.0;
        .var _tube_sat_step_{node['id']} = 0.0;
        .var _tube_sat_frames_{node['id']} = 0;
        .var _buf_{node['id']};

        .section/pm seg_pmco;
        .global _{node['id']}_process;
        _{node['id']}_process:
            r0 = dm(_buf_{node['inputs_str']});

            /* Ramp saturation amount */
            r4 = dm(_tube_sat_frames_{node['id']});
            r15 = 1;
            r4 = r4 - r15;
            if le jump (pc, .no_tramp_{node['id']});
            dm(_tube_sat_frames_{node['id']}) = r4;
            f3 = dm(_tube_sat_{node['id']});
            f2 = dm(_tube_sat_step_{node['id']});
            f3 = f3 + f2;
            dm(_tube_sat_{node['id']}) = f3;
            jump (pc, .tube_go_{node['id']});
        .no_tramp_{node['id']}:
            f3 = dm(_tube_sat_target_{node['id']});
            dm(_tube_sat_{node['id']}) = f3;
        .tube_go_{node['id']}:

            /* Waveshaper: y = x * (1 + sat * (1 - x²))
             * Provides soft clipping with even-harmonic content */
            r2 = dm(_tube_on_{node['id']});
            r2 = pass r2;
            if eq jump (pc, .tube_bypass_{node['id']});
            f1 = f0 * f0;             /* x² */
            r2 = 0x3F800000;  /* 1.0 IEEE 754 */
            f1 = f2 - f1;             /* 1 - x² */
            f1 = f3 * f1;             /* sat * (1 - x²) */
            f1 = f1 + f2;             /* 1 + sat * (1 - x²) */
            f0 = f0 * f1;             /* y = x * (...) */
        .tube_bypass_{node['id']}:

            dm(_buf_{node['id']}) = r0;
            rts;
        _{node['id']}_process.end:
    """)


def gen_delay(node):
    p = node['params']
    max_ms = float(p.get('max_ms', '250'))
    local_ms = float(p.get('local_ms', str(max_ms)))
    max_samples = max(1, int(max_ms / 1000.0 * 48000))
    local_samples = max(1, int(local_ms / 1000.0 * 48000))
    pool_slot = int(float(p.get('pool_slot', '-1')))
    rc = ramp_comment(node['ramp_profile'])

    use_shared_pool = ('pool_slot' in p) and (local_samples < max_samples)

    if not use_shared_pool:
        return dedent(f"""\
            {rc}

            /* DELAY: Audio delay line (circular buffer) */
            /* SPI page={node['spi_page']} addr={node['spi_addr']} */
            /* Max: {max_ms}ms = {max_samples} samples */

            .section/dm seg_delay;
            .var _dly_buf_{node['id']}[{max_samples}];  /* L2 SRAM delay buffer */
            .section/dm seg_dmda;
            .var _dly_write_ptr_{node['id']} = 0;
            .var _dly_read_offset_{node['id']} = 0;      /* in samples; 0 = no delay */
            .var _dly_pool_slot_{node['id']} = {pool_slot}; /* reserved for future reassignment */
            .var _dly_max_{node['id']} = {max_samples};
            .var _tap_pre_fader_{node['id']};   /* pre-fader tap */
            .var _buf_{node['id']};

            .section/pm seg_pmco;
            .global _{node['id']}_process;
            _{node['id']}_process:
                r0 = dm(_buf_{node['inputs_str']});

                /* Write to circular buffer at write pointer */
                i0 = _dly_buf_{node['id']};
                r1 = dm(_dly_write_ptr_{node['id']});
                m0 = r1;
                modify(i0, m0);
                dm(i0, 0) = r0;

                /* Read from (write_ptr - read_offset) with wrap */
                r2 = dm(_dly_read_offset_{node['id']});
                r1 = r1 - r2;
                r3 = dm(_dly_max_{node['id']});
                if lt r1 = r1 + r3;
                i0 = _dly_buf_{node['id']};
                m0 = r1;
                modify(i0, m0);
                r0 = dm(i0, 0);

                /* Advance write pointer with wrap */
                r1 = dm(_dly_write_ptr_{node['id']});
                r15 = 1;
                r1 = r1 + r15;
                r3 = dm(_dly_max_{node['id']});
                comp(r1, r3);
                if ge r1 = r1 - r3;
                dm(_dly_write_ptr_{node['id']}) = r1;

                dm(_tap_pre_fader_{node['id']}) = r0;
                dm(_buf_{node['id']}) = r0;
                rts;
            _{node['id']}_process.end:
        """)

    pool_buf_externs = '\n'.join(
        [f'.extern _dly_pool_buf_{slot:02d};' for slot in range(8)] +
        [f'.extern _dly_pool_wptr_{slot:02d};' for slot in range(8)]
    )
    slot_select = '\n'.join(
        [f'    r12 = pass r12;\n'
         f'    if eq jump (pc, .dly_slot_0_{node["id"]});'] +
        [f'    r14 = {slot};\n'
         f'    comp(r12, r14);\n'
         f'    if eq jump (pc, .dly_slot_{slot}_{node["id"]});'
         for slot in range(1, 8)]
    )
    slot_labels = '\n'.join([
        f'.dly_slot_{slot}_{node["id"]}:\n'
        f'    i0 = _dly_pool_buf_{slot:02d};\n'
        f'    i1 = _dly_pool_wptr_{slot:02d};\n'
        f'    r3 = dm(_dly_max_{node["id"]});\n'
        f'    jump (pc, .dly_io_{node["id"]});'
        for slot in range(8)
    ])

    # Per-block kernel. The 8-way slot dispatch -- up to sixteen compares
    # and branches -- is a BLOCK-CONSTANT decision that the per-sample body
    # re-evaluates on every one of the 32 samples, and it dwarfs the actual
    # delay-line I/O, which is about a dozen instructions. Hoisting it, the
    # read-offset clamp and the write-pointer load/store out of the loop is
    # the whole of the win here; the inner loop is unchanged arithmetic.
    import re as _re
    if _re.match(r'^C\d+_DLY_\d+$', node['id']):
        _n = node['id']
        _blk_sel = '\n'.join(
            ['    r12 = pass r12;\n'
             f'    if eq jump (pc, .dkb_slot_0_{_n});'] +
            [f'    r14 = {slot};\n'
             f'    comp(r12, r14);\n'
             f'    if eq jump (pc, .dkb_slot_{slot}_{_n});'
             for slot in range(1, 8)])
        _blk_lab = '\n'.join([
            f'.dkb_slot_{slot}_{_n}:\n'
            f'    i0 = _dly_pool_buf_{slot:02d};\n'
            f'    i1 = _dly_pool_wptr_{slot:02d};\n'
            f'    r3 = dm(_dly_max_{_n});\n'
            f'    jump (pc, .dkb_io_{_n});'
            for slot in range(8)])
        blk_dly_body = _DLY_BLK_BODY.format(nid=_n, sel=_blk_sel,
                                            labels=_blk_lab)
    else:
        blk_dly_body = ''

    return dedent(f"""\
        {rc}

        /* DELAY: Audio delay line with dynamic shared long-delay slot */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */
        /* Local fallback: {local_ms}ms = {local_samples} samples */
        /* Shared max:     {max_ms}ms = {max_samples} samples */

        #include "blk_pool.h"

        .section/dm seg_delay;
        {pool_buf_externs}
        .var _dly_buf_{node['id']}[{local_samples}];  /* local fallback buffer */
        .section/dm seg_dmda;
        .var _dly_write_ptr_{node['id']} = 0;
        .var _dly_read_offset_{node['id']} = 0;      /* in samples; 0 = no delay */
        .var _dly_pool_slot_{node['id']} = {pool_slot}; /* -1 = local, 0..7 = shared long slot */
        .var _dly_local_max_{node['id']} = {local_samples};
        .var _dly_max_{node['id']} = {max_samples};
        .var _tap_pre_fader_{node['id']};   /* pre-fader tap */
        .var _buf_{node['id']};

        .section/pm seg_pmco;
        .global _{node['id']}_process;
        _{node['id']}_process:
        {blk_dly_body}
            r0 = dm(_buf_{node['inputs_str']});

            /* Default to the local short buffer. Valid slot numbers promote to a shared long buffer. */
            r12 = dm(_dly_pool_slot_{node['id']});
            i0 = _dly_buf_{node['id']};
            i1 = _dly_write_ptr_{node['id']};
            r3 = dm(_dly_local_max_{node['id']});

            r13 = pass r12;
            if lt jump (pc, .dly_io_{node['id']});
            r14 = 8;
            comp(r12, r14);
            if ge jump (pc, .dly_io_{node['id']});
            {slot_select}

        .dly_io_{node['id']}:
            /* Clamp requested offset to the active buffer length. */
            r2 = dm(_dly_read_offset_{node['id']});
            comp(r2, r3);
            if lt jump (pc, .dly_offset_ok_{node['id']});
            r2 = r3 - 1;
        .dly_offset_ok_{node['id']}:

            /* Write at the selected write pointer. */
            r1 = dm(i1, 0);
            m0 = r1;
            modify(i0, m0);
            dm(i0, 0) = r0;

            /* Read from (write_ptr - read_offset) with wrap. */
            r5 = r1 - r2;
            if lt r5 = r5 + r3;
            r6 = r5 - r1;
            m0 = r6;
            modify(i0, m0);
            r0 = dm(i0, 0);

            /* Advance write pointer with wrap on the active storage. */
            r15 = 1;
            r1 = r1 + r15;
            comp(r1, r3);
            if ge r1 = r1 - r3;
            dm(i1, 0) = r1;

            dm(_tap_pre_fader_{node['id']}) = r0;
            dm(_buf_{node['id']}) = r0;
            rts;

        {slot_labels}
        _{node['id']}_process.end:
    """)


_FDR_RNS = '''            mrf = mrf + r7 * r12 (ssi);
            r8 = mr0f;
            r2 = mr1f;
            r8 = lshift r8 by -28;
            r9 = lshift r2 by 4;
            r0 = r8 or r9;
            r8 = ashift r2 by -28;
            r9 = ashift r0 by -31;
            r11 = ashift r2 by -31;
            r11 = r10 xor r11;
            comp(r8, r9);
            if ne r0 = r11;
'''


def gen_fader_pan(node):
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    is_ch_fdr = (node['chip'] == '1')  # Chip 1 channel faders need L/R pan split

    # Extra buffer vars for stereo pan split (Chip 1 only)
    lr_vars = ''
    if is_ch_fdr:
        lr_vars = (
            f'        .var _buf_L_{node["id"]};\n'
            f'        .var _buf_R_{node["id"]};'
        )

    # Output section differs between channel faders (L/R split) and bus faders
    if is_ch_fdr:
        pan_output = (
            f'            /* Save mono post-fader for sub/grp/aux/fx routing */\n'
            f'            f14 = f0;\n'
            f'            /* Constant-power pan: linear approximation\n'
            f'             * pan=0→L, 0.5→C, 1→R */\n'
            f'            r6 = 0x3F800000;  /* 1.0 IEEE 754 */\n'
            f'            f7 = f6 - f5;             /* L_gain = 1 - pan */\n'
            f'            f1 = f14 * f7;            /* L output */\n'
            f'            f2 = f14 * f5;            /* R output (R_gain = pan) */\n'
            f'            dm(_tap_post_fader_{node["id"]}) = f14;\n'
            f'            dm(_buf_{node["id"]}) = f14;     /* mono post-fader */\n'
            f'            dm(_buf_L_{node["id"]}) = f1;    /* L pan */\n'
            f'            dm(_buf_R_{node["id"]}) = f2;    /* R pan */'
        )
    else:
        pan_output = (
            f'            /* Bus fader: mono passthrough (no pan split) */\n'
            f'            dm(_tap_post_fader_{node["id"]}) = f0;\n'
            f'            dm(_buf_{node["id"]}) = f0;'
        )

    return dedent(f"""\
        {rc}

        /* FADER_PAN: Level fader + constant-power pan + mute */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        .section/dm seg_dmda;
        .var _fdr_level_{node['id']} = 1.0;
        .var _fdr_level_target_{node['id']} = 1.0;
        .var _fdr_level_step_{node['id']} = 0.0;
        .var _fdr_level_frames_{node['id']} = 0;
        .var _fdr_pan_{node['id']} = 0.5;       /* 0=L, 0.5=C, 1=R */
        .var _fdr_pan_target_{node['id']} = 0.5;
        .var _fdr_pan_step_{node['id']} = 0.0;
        .var _fdr_pan_frames_{node['id']} = 0;
        .var _fdr_mute_{node['id']} = 0;
        .var _fdr_dca_gain_{node['id']} = 1.0;  /* DCA master multiplier */
        .var _tap_post_fader_{node['id']};      /* post-fader tap */
        .var _buf_{node['id']};
{lr_vars}

        .section/pm seg_pmco;
        .global _{node['id']}_process;
        _{node['id']}_process:
            /* --- Level ramp (GainFast: 3ms up / 8ms down, Exp) --- */
            r4 = dm(_fdr_level_frames_{node['id']});
            r15 = 1;
            r4 = r4 - r15;
            if le jump (pc, .no_lramp_{node['id']});
            dm(_fdr_level_frames_{node['id']}) = r4;
            f1 = dm(_fdr_level_{node['id']});
            f2 = dm(_fdr_level_step_{node['id']});
            f1 = f1 + f2;
            dm(_fdr_level_{node['id']}) = f1;
            jump (pc, .do_pan_{node['id']});
        .no_lramp_{node['id']}:
            f1 = dm(_fdr_level_target_{node['id']});
            dm(_fdr_level_{node['id']}) = f1;
        .do_pan_{node['id']}:

            /* --- Pan ramp --- */
            r4 = dm(_fdr_pan_frames_{node['id']});
            r15 = 1;
            r4 = r4 - r15;
            if le jump (pc, .no_pramp_{node['id']});
            dm(_fdr_pan_frames_{node['id']}) = r4;
            f5 = dm(_fdr_pan_{node['id']});
            f6 = dm(_fdr_pan_step_{node['id']});
            f5 = f5 + f6;
            dm(_fdr_pan_{node['id']}) = f5;
            jump (pc, .apply_fdr_{node['id']});
        .no_pramp_{node['id']}:
            f5 = dm(_fdr_pan_target_{node['id']});
            dm(_fdr_pan_{node['id']}) = f5;
        .apply_fdr_{node['id']}:

            r0 = dm(_buf_{node['inputs_str']});

            /* Apply level (incl. DCA multiplier) */
            f3 = dm(_fdr_dca_gain_{node['id']});
            f1 = f1 * f3;       /* effective_gain = fader × DCA */
            f0 = f0 * f1;

            /* Mute */
            r2 = dm(_fdr_mute_{node['id']});
            r3 = 0;
            comp(r2, r3);
            if ne r0 = r3;      /* if muted, clear f0 (0 = 0.0f IEEE 754) */

{pan_output}
            rts;
        _{node['id']}_process.end:
    """)


def gen_routing(node):
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    fdr_id = node['inputs_str']  # e.g. C1_FDR_01
    gain_id = fdr_id.replace('_FDR_', '_GAIN_')
    eq_id = fdr_id.replace('_FDR_', '_EQ_')
    dly_id = fdr_id.replace('_FDR_', '_DLY_')
    aux_pick_defaults = ', '.join(['3'] * 12)
    fx_pick_defaults = ', '.join(['3'] * 6)

    return dedent(f"""\
        {rc}

        /* ROUTING: Fan-out to bus pre-sums (scatter accumulation) */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */
        /* Routes channel signal to Main L/R, Sub, Grp×4, Aux×12, FX×6 */
        /* Aux/Fx pickoff: 0=PreEQ, 1=PostEQ, 2=PreFdr, 3=PostFdr(default) */

        .section/dm seg_dmda;
        .extern _tap_post_trim_{gain_id};
        .extern _tap_post_eq_{eq_id};
        .extern _tap_pre_fader_{dly_id};
        .extern _tap_post_fader_{fdr_id};
        .var _rtg_main_on_{node['id']} = 1;
        .var _rtg_sub_on_{node['id']} = 0;
        .var _rtg_grp_on_{node['id']}[4] = 0, 0, 0, 0;
        .var _rtg_aux_on_{node['id']}[12];
        .var _rtg_aux_send_{node['id']}[12];      /* per-aux send level (linear) */
        .var _rtg_aux_send_target_{node['id']}[12]; /* ramp targets */
        .var _rtg_aux_send_step_{node['id']}[12];   /* ramp steps */
        .var _rtg_aux_send_frames_{node['id']}[12];  /* ramp frame counters */
        .var _rtg_aux_pick_{node['id']}[12] = {aux_pick_defaults}; /* 0=PreEQ 1=PostEQ 2=PreFdr 3=PostFdr */
        .var _rtg_fx_on_{node['id']}[6];
        .var _rtg_fx_send_{node['id']}[6];
        .var _rtg_fx_send_target_{node['id']}[6];
        .var _rtg_fx_send_step_{node['id']}[6];
        .var _rtg_fx_send_frames_{node['id']}[6];
        .var _rtg_fx_pick_{node['id']}[6] = {fx_pick_defaults}; /* 0=PreEQ 1=PostEQ 2=PreFdr 3=PostFdr */
        .var _buf_{node['id']};

        .section/pm seg_pmco;
        .extern _bus_acc_main_l; .extern _bus_acc_main_r;
        .extern _bus_acc_sub;
        .extern _bus_acc_grp_ptrs;
        .extern _bus_acc_aux_ptrs;
        .extern _bus_acc_fx_ptrs;
        .global _{node['id']}_process;
        _{node['id']}_process:

            /* ===== Aux send ramp updates (12 iterations) ===== */
            i0 = _rtg_aux_send_{node['id']};
            i1 = _rtg_aux_send_step_{node['id']};
            i2 = _rtg_aux_send_frames_{node['id']};
            i3 = _rtg_aux_send_target_{node['id']};
            r5 = 12;
            lcntr = r5; do .aux_ramp_loop_{node['id']} until lce;
                r4 = dm(i2, 0);
                r15 = 1;
                r4 = r4 - r15;
                if le jump (pc, .aux_snap_{node['id']});
                dm(i2, 1) = r4;
                f1 = dm(i0, 0); f2 = dm(i1, 1);
                f1 = f1 + f2;
                dm(i0, 1) = f1;
                jump (pc, .aux_next_{node['id']});
            .aux_snap_{node['id']}:
                f1 = dm(i3, 1);
                dm(i0, 1) = f1;
                modify(i1, 1); modify(i2, 1);
            .aux_next_{node['id']}:
                nop;                /* ea2019: pad before loop end */
            .aux_ramp_loop_{node['id']}:

            /* ===== FX send ramp updates (6 iterations) ===== */
            i0 = _rtg_fx_send_{node['id']};
            i1 = _rtg_fx_send_step_{node['id']};
            i2 = _rtg_fx_send_frames_{node['id']};
            i3 = _rtg_fx_send_target_{node['id']};
            r5 = 6;
            lcntr = r5; do .fx_ramp_loop_{node['id']} until lce;
                r4 = dm(i2, 0);
                r15 = 1;
                r4 = r4 - r15;
                if le jump (pc, .fx_snap_{node['id']});
                dm(i2, 1) = r4;
                f1 = dm(i0, 0); f2 = dm(i1, 1);
                f1 = f1 + f2;
                dm(i0, 1) = f1;
                jump (pc, .fx_next_{node['id']});
            .fx_snap_{node['id']}:
                f1 = dm(i3, 1);
                dm(i0, 1) = f1;
                modify(i1, 1); modify(i2, 1);
            .fx_next_{node['id']}:
                nop;                /* ea2019: pad before loop end */
            .fx_ramp_loop_{node['id']}:

            /* ===== Main L/R accumulate ===== */
            r2 = dm(_rtg_main_on_{node['id']});
            r2 = pass r2;
            if eq jump (pc, .rtg_no_main_{node['id']});
            f0 = dm(_bus_acc_main_l);
            f1 = dm(_buf_L_{fdr_id});
            f0 = f0 + f1;
            dm(_bus_acc_main_l) = f0;
            f0 = dm(_bus_acc_main_r);
            f1 = dm(_buf_R_{fdr_id});
            f0 = f0 + f1;
            dm(_bus_acc_main_r) = f0;
        .rtg_no_main_{node['id']}:

            /* ===== Sub accumulate ===== */
            r2 = dm(_rtg_sub_on_{node['id']});
            r2 = pass r2;
            if eq jump (pc, .rtg_no_sub_{node['id']});
            f0 = dm(_bus_acc_sub);
            f1 = dm(_buf_{fdr_id});           /* mono post-fader */
            f0 = f0 + f1;
            dm(_bus_acc_sub) = f0;
        .rtg_no_sub_{node['id']}:

            /* ===== Group accumulate (4 groups, pointer array) ===== */
            i3 = _bus_acc_grp_ptrs;
            i5 = _rtg_grp_on_{node['id']};
            f1 = dm(_buf_{fdr_id});           /* mono post-fader */
            r5 = 4;
            lcntr = r5; do .rtg_grp_loop_{node['id']} until lce;
                r2 = dm(i5, 1);               /* grp_on flag */
                r2 = pass r2;
                if eq jump (pc, .rtg_grp_skip_{node['id']});
                r3 = dm(i3, 1);               /* pointer to bus acc */
                i0 = r3;
                f4 = dm(i0, 0);               /* current acc value */
                f4 = f4 + f1;                 /* accumulate */
                dm(i0, 0) = f4;
                jump (pc, .rtg_grp_next_{node['id']});
            .rtg_grp_skip_{node['id']}:
                modify(i3, 1);
            .rtg_grp_next_{node['id']}:
                nop;                /* ea2019: branch target cannot be at loop end */
            .rtg_grp_loop_{node['id']}:

            /* ===== Aux accumulate (12 auxes, pointer array) ===== */
            /* Pickoff select: 0=PreEQ, 1=PostEQ, 2=PreFdr, 3=PostFdr */
            i3 = _bus_acc_aux_ptrs;
            i4 = _rtg_aux_send_{node['id']};
            i5 = _rtg_aux_on_{node['id']};
            i6 = _rtg_aux_pick_{node['id']};
            r5 = 12;
            lcntr = r5; do .rtg_aux_acc_{node['id']} until lce;
                r2 = dm(i5, 1);               /* aux_on flag */
                r2 = pass r2;
                if eq jump (pc, .rtg_aux_acc_skip_{node['id']});
                r6 = dm(i6, 1);               /* pickoff enum */
                r6 = pass r6;
                if eq jump (pc, .rtg_aux_pick_preeq_{node['id']});
                r7 = 1;
                comp(r6, r7);
                if eq jump (pc, .rtg_aux_pick_posteq_{node['id']});
                r7 = 2;
                comp(r6, r7);
                if eq jump (pc, .rtg_aux_pick_prefdr_{node['id']});
                f1 = dm(_tap_post_fader_{fdr_id}); /* default: PostFdr */
                jump (pc, .rtg_aux_pick_done_{node['id']});
            .rtg_aux_pick_preeq_{node['id']}:
                f1 = dm(_tap_post_trim_{gain_id});
                jump (pc, .rtg_aux_pick_done_{node['id']});
            .rtg_aux_pick_posteq_{node['id']}:
                f1 = dm(_tap_post_eq_{eq_id});
                jump (pc, .rtg_aux_pick_done_{node['id']});
            .rtg_aux_pick_prefdr_{node['id']}:
                f1 = dm(_tap_pre_fader_{dly_id});
            .rtg_aux_pick_done_{node['id']}:
                f2 = dm(i4, 1);               /* ramped send level */
                f3 = f1 * f2;                 /* signal × send */
                r3 = dm(i3, 1);               /* pointer to bus acc */
                i0 = r3;
                f4 = dm(i0, 0);               /* current acc value */
                f4 = f4 + f3;
                dm(i0, 0) = f4;
                jump (pc, .rtg_aux_acc_next_{node['id']});
            .rtg_aux_acc_skip_{node['id']}:
                modify(i4, 1); modify(i3, 1); modify(i6, 1);
            .rtg_aux_acc_next_{node['id']}:
                nop;                /* ea2019: branch target cannot be at loop end */
            .rtg_aux_acc_{node['id']}:

            /* ===== FX send accumulate (6 FX sends, pointer array) ===== */
            /* Pickoff select: 0=PreEQ, 1=PostEQ, 2=PreFdr, 3=PostFdr */
            i3 = _bus_acc_fx_ptrs;
            i4 = _rtg_fx_send_{node['id']};
            i5 = _rtg_fx_on_{node['id']};
            i6 = _rtg_fx_pick_{node['id']};
            r5 = 6;
            lcntr = r5; do .rtg_fx_acc_{node['id']} until lce;
                r2 = dm(i5, 1);               /* fx_on flag */
                r2 = pass r2;
                if eq jump (pc, .rtg_fx_acc_skip_{node['id']});
                r6 = dm(i6, 1);               /* pickoff enum */
                r6 = pass r6;
                if eq jump (pc, .rtg_fx_pick_preeq_{node['id']});
                r7 = 1;
                comp(r6, r7);
                if eq jump (pc, .rtg_fx_pick_posteq_{node['id']});
                r7 = 2;
                comp(r6, r7);
                if eq jump (pc, .rtg_fx_pick_prefdr_{node['id']});
                f1 = dm(_tap_post_fader_{fdr_id}); /* default: PostFdr */
                jump (pc, .rtg_fx_pick_done_{node['id']});
            .rtg_fx_pick_preeq_{node['id']}:
                f1 = dm(_tap_post_trim_{gain_id});
                jump (pc, .rtg_fx_pick_done_{node['id']});
            .rtg_fx_pick_posteq_{node['id']}:
                f1 = dm(_tap_post_eq_{eq_id});
                jump (pc, .rtg_fx_pick_done_{node['id']});
            .rtg_fx_pick_prefdr_{node['id']}:
                f1 = dm(_tap_pre_fader_{dly_id});
            .rtg_fx_pick_done_{node['id']}:
                f2 = dm(i4, 1);               /* ramped send level */
                f3 = f1 * f2;                 /* signal × send */
                r3 = dm(i3, 1);               /* pointer to bus acc */
                i0 = r3;
                f4 = dm(i0, 0);
                f4 = f4 + f3;
                dm(i0, 0) = f4;
                jump (pc, .rtg_fx_acc_next_{node['id']});
            .rtg_fx_acc_skip_{node['id']}:
                modify(i4, 1); modify(i3, 1); modify(i6, 1);
            .rtg_fx_acc_next_{node['id']}:
                nop;                /* ea2019: branch target cannot be at loop end */
            .rtg_fx_acc_{node['id']}:

            /* Store routing output (pass-through for metering) */
            f0 = dm(_buf_{fdr_id});
            dm(_buf_{node['id']}) = f0;
            rts;
        _{node['id']}_process.end:
    """)


def gen_geq(node):
    """Generate a dual-instance crossfade graphic EQ.

    Same architecture as gen_eq_biquad — two parallel N-stage biquad cascades
    (A/B) with XFADE_SAMPLES-sample linear crossfade.  Band count is
    configurable (default 28 for 1/3-octave).
    """
    p = node['params']
    bands = int(p.get('bands', '28'))
    n5 = bands * 5
    n2 = bands * 2
    rc = ramp_comment(node['ramp_profile'])
    bypass = ', '.join(['1.0, 0.0, 0.0, 0.0, 0.0'] * bands)
    nid = node['id']
    inp = node['inputs_str']
    return dedent(f"""\
        {rc}

        /* GEQ: {bands}-band 1/3-octave graphic EQ — dual-instance crossfade */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */
        /*
         * Dual-instance crossfade (CoeffSetAtomic scope):
         *   Two parallel {bands}-stage biquad cascades (A/B) with independent
         *   coefficients and state.  Architecture identical to EQ_BIQUAD.
         *   See gen_eq_biquad docstring for full description.
         */

        .section/dm seg_dmda;
        .var _geq_gains_{nid}[{bands}];              /* per-band gain (linear, display) */

        /* ---- Instance A ---- */
        .var _geq_coeffs_A_{nid}[{n5}] = {bypass};
        .var _geq_state_A_{nid}[{n2}];

        /* ---- Instance B ---- */
        .var _geq_coeffs_B_{nid}[{n5}] = {bypass};
        .var _geq_state_B_{nid}[{n2}];

        /* ---- SPI staging buffer ---- */
        .var _geq_coeffs_next_{nid}[{n5}] = {bypass};
        .var _geq_swap_pending_{nid} = 0;

        /* ---- Crossfade control ---- */
        .var _geq_active_{nid} = 0;
        .var _geq_xfade_alpha_{nid} = 0.0;
        .var _geq_xfade_step_{nid} = 0.0;

        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _biquad_cascade_N;
        .global _{nid}_process;
        _{nid}_process:

            /* ── Check for new coefficients ── */
            r4 = dm(_geq_swap_pending_{nid});
            r4 = pass r4;
            if ne call _geq_start_xfade_{nid};

            /* ── Crossfade or steady-state? ── */
            r4 = dm(_geq_xfade_step_{nid});
            r4 = pass r4;
            if ne jump .geq_xfade_{nid};

            /* ═══ STEADY STATE ═══════════════════════════════════════ */
            r0 = dm(_buf_{inp});
            r4 = dm(_geq_active_{nid});
            r4 = pass r4;
            if ne jump .geq_ss_B_{nid};
            i0 = _geq_coeffs_A_{nid};
            i1 = _geq_state_A_{nid};
            jump .geq_ss_run_{nid};
        .geq_ss_B_{nid}:
            i0 = _geq_coeffs_B_{nid};
            i1 = _geq_state_B_{nid};
        .geq_ss_run_{nid}:
            r4 = {bands};
            call _biquad_cascade_N;
            dm(_buf_{nid}) = r0;
            rts;

            /* ═══ CROSSFADE ═════════════════════════════════════════ */
        .geq_xfade_{nid}:
            r0 = dm(_buf_{inp});
            f15 = f0;                            /* save input */

            /* ── Active (old) instance ── */
            r4 = dm(_geq_active_{nid});
            r4 = pass r4;
            if ne jump .geq_xf_actB_{nid};
            i0 = _geq_coeffs_A_{nid};
            i1 = _geq_state_A_{nid};
            jump .geq_xf_act_run_{nid};
        .geq_xf_actB_{nid}:
            i0 = _geq_coeffs_B_{nid};
            i1 = _geq_state_B_{nid};
        .geq_xf_act_run_{nid}:
            r4 = {bands};
            call _biquad_cascade_N;
            f13 = f0;                            /* old output */

            /* ── Inactive (new) instance ── */
            f0 = f15;
            r4 = dm(_geq_active_{nid});
            r4 = pass r4;
            if eq jump .geq_xf_inB_{nid};
            i0 = _geq_coeffs_A_{nid};
            i1 = _geq_state_A_{nid};
            jump .geq_xf_in_run_{nid};
        .geq_xf_inB_{nid}:
            i0 = _geq_coeffs_B_{nid};
            i1 = _geq_state_B_{nid};
        .geq_xf_in_run_{nid}:
            r4 = {bands};
            call _biquad_cascade_N;

            /* ── Blend: out = (1 − α) × old + α × new ── */
            f14 = dm(_geq_xfade_alpha_{nid});
            r15 = 0x3F800000;  /* 1.0 IEEE 754 */
            f15 = f15 - f14;
            f13 = f13 * f15;
            f0 = f0 * f14;
            f0 = f0 + f13;

            /* ── Advance α ── */
            f14 = dm(_geq_xfade_alpha_{nid});
            f15 = dm(_geq_xfade_step_{nid});
            f14 = f14 + f15;
            dm(_geq_xfade_alpha_{nid}) = f14;
            r15 = 0x3F800000;  /* 1.0 IEEE 754 */
            comp(f14, f15);
            if ge call _geq_xfade_done_{nid};

            dm(_buf_{nid}) = f0;
            rts;

        /* ── Start crossfade: load dormant instance ── */
        _geq_start_xfade_{nid}:
            r4 = 0;
            dm(_geq_swap_pending_{nid}) = r4;

            r4 = dm(_geq_active_{nid});
            r4 = pass r4;
            if ne jump .geq_sxf_toA_{nid};

            /* Active=A → dormant=B */
            i0 = _geq_coeffs_next_{nid};
            i1 = _geq_coeffs_B_{nid};
            r4 = {n5};
            lcntr = r4; do .geq_cp_B_{nid} until lce;
                r0 = dm(i0, 1);
                dm(i1, 1) = r0;
            .geq_cp_B_{nid}:
            i1 = _geq_state_B_{nid};
            r0 = 0;
            r4 = {n2};
            lcntr = r4; do .geq_zs_B_{nid} until lce;
                dm(i1, 1) = r0;
            .geq_zs_B_{nid}:
            nop;
            jump .geq_sxf_go_{nid};

        .geq_sxf_toA_{nid}:
            /* Active=B → dormant=A */
            i0 = _geq_coeffs_next_{nid};
            i1 = _geq_coeffs_A_{nid};
            r4 = {n5};
            lcntr = r4; do .geq_cp_A_{nid} until lce;
                r0 = dm(i0, 1);
                dm(i1, 1) = r0;
            .geq_cp_A_{nid}:
            i1 = _geq_state_A_{nid};
            r0 = 0;
            r4 = {n2};
            lcntr = r4; do .geq_zs_A_{nid} until lce;
                dm(i1, 1) = r0;
            .geq_zs_A_{nid}:

        .geq_sxf_go_{nid}:
            r0 = 0;
            dm(_geq_xfade_alpha_{nid}) = r0;
            f0 = {XFADE_STEP};
            dm(_geq_xfade_step_{nid}) = f0;
            rts;
        _geq_start_xfade_{nid}.end:

        /* ── Crossfade complete ── */
        _geq_xfade_done_{nid}:
            r4 = dm(_geq_active_{nid});
            r5 = 1;
            r4 = r4 xor r5;
            dm(_geq_active_{nid}) = r4;
            r4 = 0;
            dm(_geq_xfade_alpha_{nid}) = r4;
            dm(_geq_xfade_step_{nid}) = r4;
            rts;
        _geq_xfade_done_{nid}.end:

        _{nid}_process.end:
    """)


def gen_anti_fb(node):
    """Generate anti-feedback filter with dual-instance crossfade.

    Same architecture as gen_eq_biquad but with notch_count stages.
    Control variables (_afb_on, _afb_ctrl_on, _afb_notch_freq/gain/q)
    remain separate — only the biquad coefficient set is crossfaded.
    """
    p = node['params']
    notches = int(p.get('notch_count', '6'))
    n5 = notches * 5
    n2 = notches * 2
    rc = ramp_comment(node['ramp_profile'])
    bypass = ', '.join(['1.0, 0.0, 0.0, 0.0, 0.0'] * notches)
    nid = node['id']
    inp = node['inputs_str']
    return dedent(f"""\
        {rc}

        /* ANTI_FB: Auto anti-feedback ({notches} notches) — dual-instance crossfade */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */
        /*
         * Dual-instance crossfade (CoeffSetAtomic scope):
         *   Two parallel {notches}-stage notch biquad cascades (A/B).
         *   Architecture identical to EQ_BIQUAD.
         */

        .section/dm seg_dmda;
        .var _afb_on_{nid} = 0;
        .var _afb_ctrl_on_{nid} = 0;
        .var _afb_notch_freq_{nid}[{notches}];
        .var _afb_notch_gain_{nid}[{notches}];
        .var _afb_notch_q_{nid}[{notches}];

        /* ---- Instance A ---- */
        .var _afb_coeffs_A_{nid}[{n5}] = {bypass};
        .var _afb_state_A_{nid}[{n2}];

        /* ---- Instance B ---- */
        .var _afb_coeffs_B_{nid}[{n5}] = {bypass};
        .var _afb_state_B_{nid}[{n2}];

        /* ---- SPI staging buffer ---- */
        .var _afb_coeffs_next_{nid}[{n5}];
        .var _afb_swap_pending_{nid} = 0;

        /* ---- Crossfade control ---- */
        .var _afb_active_{nid} = 0;
        .var _afb_xfade_alpha_{nid} = 0.0;
        .var _afb_xfade_step_{nid} = 0.0;

        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _biquad_cascade_N;
        .global _{nid}_process;
        _{nid}_process:

            /* ── Check for new coefficients ── */
            r4 = dm(_afb_swap_pending_{nid});
            r4 = pass r4;
            if ne call _afb_start_xfade_{nid};

            /* ── Crossfade or steady-state? ── */
            r4 = dm(_afb_xfade_step_{nid});
            r4 = pass r4;
            if ne jump .afb_xfade_{nid};

            /* ═══ STEADY STATE ═══════════════════════════════════════ */
            r0 = dm(_buf_{inp});
            r4 = dm(_afb_active_{nid});
            r4 = pass r4;
            if ne jump .afb_ss_B_{nid};
            i0 = _afb_coeffs_A_{nid};
            i1 = _afb_state_A_{nid};
            jump .afb_ss_run_{nid};
        .afb_ss_B_{nid}:
            i0 = _afb_coeffs_B_{nid};
            i1 = _afb_state_B_{nid};
        .afb_ss_run_{nid}:
            r4 = {notches};
            call _biquad_cascade_N;
            dm(_buf_{nid}) = r0;
            rts;

            /* ═══ CROSSFADE ═════════════════════════════════════════ */
        .afb_xfade_{nid}:
            r0 = dm(_buf_{inp});
            f15 = f0;

            /* ── Active (old) instance ── */
            r4 = dm(_afb_active_{nid});
            r4 = pass r4;
            if ne jump .afb_xf_actB_{nid};
            i0 = _afb_coeffs_A_{nid};
            i1 = _afb_state_A_{nid};
            jump .afb_xf_act_run_{nid};
        .afb_xf_actB_{nid}:
            i0 = _afb_coeffs_B_{nid};
            i1 = _afb_state_B_{nid};
        .afb_xf_act_run_{nid}:
            r4 = {notches};
            call _biquad_cascade_N;
            f13 = f0;

            /* ── Inactive (new) instance ── */
            f0 = f15;
            r4 = dm(_afb_active_{nid});
            r4 = pass r4;
            if eq jump .afb_xf_inB_{nid};
            i0 = _afb_coeffs_A_{nid};
            i1 = _afb_state_A_{nid};
            jump .afb_xf_in_run_{nid};
        .afb_xf_inB_{nid}:
            i0 = _afb_coeffs_B_{nid};
            i1 = _afb_state_B_{nid};
        .afb_xf_in_run_{nid}:
            r4 = {notches};
            call _biquad_cascade_N;

            /* ── Blend: out = (1 − α) × old + α × new ── */
            f14 = dm(_afb_xfade_alpha_{nid});
            r15 = 0x3F800000;  /* 1.0 IEEE 754 */
            f15 = f15 - f14;
            f13 = f13 * f15;
            f0 = f0 * f14;
            f0 = f0 + f13;

            /* ── Advance α ── */
            f14 = dm(_afb_xfade_alpha_{nid});
            f15 = dm(_afb_xfade_step_{nid});
            f14 = f14 + f15;
            dm(_afb_xfade_alpha_{nid}) = f14;
            r15 = 0x3F800000;  /* 1.0 IEEE 754 */
            comp(f14, f15);
            if ge call _afb_xfade_done_{nid};

            dm(_buf_{nid}) = f0;
            rts;

        /* ── Start crossfade: load dormant instance ── */
        _afb_start_xfade_{nid}:
            r4 = 0;
            dm(_afb_swap_pending_{nid}) = r4;

            r4 = dm(_afb_active_{nid});
            r4 = pass r4;
            if ne jump .afb_sxf_toA_{nid};

            /* Active=A → dormant=B */
            i0 = _afb_coeffs_next_{nid};
            i1 = _afb_coeffs_B_{nid};
            r4 = {n5};
            lcntr = r4; do .afb_cp_B_{nid} until lce;
                r0 = dm(i0, 1);
                dm(i1, 1) = r0;
            .afb_cp_B_{nid}:
            i1 = _afb_state_B_{nid};
            r0 = 0;
            r4 = {n2};
            lcntr = r4; do .afb_zs_B_{nid} until lce;
                dm(i1, 1) = r0;
            .afb_zs_B_{nid}:
            nop;
            jump .afb_sxf_go_{nid};

        .afb_sxf_toA_{nid}:
            /* Active=B → dormant=A */
            i0 = _afb_coeffs_next_{nid};
            i1 = _afb_coeffs_A_{nid};
            r4 = {n5};
            lcntr = r4; do .afb_cp_A_{nid} until lce;
                r0 = dm(i0, 1);
                dm(i1, 1) = r0;
            .afb_cp_A_{nid}:
            i1 = _afb_state_A_{nid};
            r0 = 0;
            r4 = {n2};
            lcntr = r4; do .afb_zs_A_{nid} until lce;
                dm(i1, 1) = r0;
            .afb_zs_A_{nid}:

        .afb_sxf_go_{nid}:
            r0 = 0;
            dm(_afb_xfade_alpha_{nid}) = r0;
            f0 = {XFADE_STEP};
            dm(_afb_xfade_step_{nid}) = f0;
            rts;
        _afb_start_xfade_{nid}.end:

        /* ── Crossfade complete ── */
        _afb_xfade_done_{nid}:
            r4 = dm(_afb_active_{nid});
            r5 = 1;
            r4 = r4 xor r5;
            dm(_afb_active_{nid}) = r4;
            r4 = 0;
            dm(_afb_xfade_alpha_{nid}) = r4;
            dm(_afb_xfade_step_{nid}) = r4;
            rts;
        _afb_xfade_done_{nid}.end:

        _{nid}_process.end:
    """)


def gen_fx_engine(node):
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    fx_class = p.get('fx_class', 'reverb')  # reverb | echo | modulation

    # Freeverb constants (48 kHz) — only used for reverb class
    comb_lens = [1557, 1617, 1491, 1422, 1277, 1356, 1188, 1116]
    ap_lens = [556, 441, 341, 225]
    comb_ofs, acc = [], 0
    for cl in comb_lens:
        comb_ofs.append(acc); acc += cl
    ap_ofs, acc = [], 0
    for al in ap_lens:
        ap_ofs.append(acc); acc += al
    comb_lens_s = ', '.join(str(x) for x in comb_lens)
    comb_ofs_s  = ', '.join(str(x) for x in comb_ofs)
    ap_lens_s   = ', '.join(str(x) for x in ap_lens)
    ap_ofs_s    = ', '.join(str(x) for x in ap_ofs)
    total_comb = sum(comb_lens)
    total_ap   = sum(ap_lens)

    # Echo buffer size depends on class
    if fx_class == 'echo':
        echo_buf_size = 48000       # 1 second @ 48kHz
    elif fx_class == 'modulation':
        echo_buf_size = 2400        # 50ms @ 48kHz (chorus/flanger/phaser)
    else:
        echo_buf_size = 8           # reverb class: 8 words for phaser state only

    # ----- DM variables (common to all classes) -----
    lines = []
    lines.append(dedent(f"""\
        {rc}

        /* FX_ENGINE [{fx_class}]: effects processor */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */
        /* Default type: {p.get('type','Reverb')} */
        /* fx_class={fx_class} */

        .section/dm seg_dmda;
        .var _fx_on_{nid} = 1;
        .var _fx_type_{nid} = 0;           /* 0=Echo,1=PingPong,2=Doubling,3=Reverb,4=Chorus,5=Flanger,6=Phaser */
        .var _fx_decay_{nid};
        .var _fx_predelay_{nid};
        .var _fx_delay_ms_{nid};
        .var _fx_feedback_{nid};
        .var _fx_balance_{nid};
        .var _fx_damp_{nid};
        .var _fx_eq_lo_{nid};
        .var _fx_eq_mid_{nid};
        .var _fx_eq_hi_{nid};
        .var _fx_hpf_coeffs_{nid}[5];
        .var _fx_mod_rate_{nid};
        .var _fx_mod_level_{nid};
        .var _fx_lfo_shape_{nid} = 0;      /* 0=sine, 1=triangle */
        .var _fx_width_{nid};
        .var _fx_mix_{nid};
        .var _fx_mix_target_{nid};
        .var _fx_mix_step_{nid} = 0.0;
        .var _fx_mix_frames_{nid} = 0;
        .var _fx_duck_on_{nid} = 0;
        .var _fx_duck_sens_{nid};

        /* LFO state */
        .var _fx_lfo_phase_{nid} = 0.0;
        .var _fx_scratch_{nid};
    """))

    # ----- Class-specific buffers -----
    if fx_class == 'reverb':
        lines.append(dedent(f"""\
        /* Reverb buffers (seg_delay for large arrays) */
        .section/dm seg_delay;
        .var _fx_comb_buf_L_{nid}[{total_comb}];
        .var _fx_comb_buf_R_{nid}[{total_comb}];
        .var _fx_allpass_buf_L_{nid}[{total_ap}];
        .var _fx_allpass_buf_R_{nid}[{total_ap}];
        .section/dm seg_dmda;
        .var _fx_rv_comb_wptrs_{nid}[8];
        .var _fx_rv_comb_lpfs_{nid}[8];
        .var _fx_rv_comb_lens_{nid}[8] = {comb_lens_s};
        .var _fx_rv_comb_ofs_{nid}[8] = {comb_ofs_s};
        .var _fx_rv_ap_wptrs_{nid}[4];
        .var _fx_rv_ap_lens_{nid}[4] = {ap_lens_s};
        .var _fx_rv_ap_ofs_{nid}[4] = {ap_ofs_s};
        /* Tiny state buf for phaser fallback */
        .var _fx_echo_buf_{nid}[{echo_buf_size}];
        .var _fx_echo_wptr_{nid} = 0;
        """))
    elif fx_class == 'echo':
        lines.append(dedent(f"""\
        /* Echo delay buffer (seg_delay) */
        .section/dm seg_delay;
        .var _fx_echo_buf_{nid}[{echo_buf_size}];
        .section/dm seg_dmda;
        .var _fx_echo_wptr_{nid} = 0;
        """))
    else:  # modulation
        lines.append(dedent(f"""\
        /* Modulation delay buffer ({echo_buf_size} samples = 50ms) */
        .var _fx_echo_buf_{nid}[{echo_buf_size}];
        .var _fx_echo_wptr_{nid} = 0;
        """))

    # ----- Output buffers + code start -----
    lines.append(dedent(f"""\
        .var _buf_L_{nid};
        .var _buf_R_{nid};
        .var _buf_{nid};

        .section/pm seg_pmco;
        .global _{nid}_process;
        _{nid}_process:
            /* Ramp mix level */
            r4 = dm(_fx_mix_frames_{nid});
            r15 = 1;
            r4 = r4 - r15;
            if le jump (pc, .no_fxramp_{nid});
            dm(_fx_mix_frames_{nid}) = r4;
            f1 = dm(_fx_mix_{nid});
            f2 = dm(_fx_mix_step_{nid});
            f1 = f1 + f2;
            dm(_fx_mix_{nid}) = f1;
            jump (pc, .fx_dispatch_{nid});
        .no_fxramp_{nid}:
            f1 = dm(_fx_mix_target_{nid});
            dm(_fx_mix_{nid}) = f1;
        .fx_dispatch_{nid}:

            /* Load input */
            r0 = dm(_buf_{inp});
            f15 = f0;                   /* dry input saved in f15 */

            /* Dispatch on algorithm type */
            r0 = dm(_fx_type_{nid});
    """))

    # ----- Dispatch table (class-filtered) -----
    if fx_class == 'reverb':
        lines.append(dedent(f"""\
            r1 = 3; comp(r0, r1); if eq jump (pc, .fx_reverb_{nid});
            r1 = 2; comp(r0, r1); if eq jump (pc, .fx_doubling_{nid});
            jump (pc, .fx_passthru_{nid});
        """))
    elif fx_class == 'echo':
        lines.append(dedent(f"""\
            r1 = 0; comp(r0, r1); if eq jump (pc, .fx_echo_{nid});
            r1 = 1; comp(r0, r1); if eq jump (pc, .fx_pingpong_{nid});
            r1 = 2; comp(r0, r1); if eq jump (pc, .fx_doubling_{nid});
            jump (pc, .fx_passthru_{nid});
        """))
    else:  # modulation
        lines.append(dedent(f"""\
            r1 = 4; comp(r0, r1); if eq jump (pc, .fx_chorus_{nid});
            r1 = 5; comp(r0, r1); if eq jump (pc, .fx_flanger_{nid});
            r1 = 6; comp(r0, r1); if eq jump (pc, .fx_phaser_{nid});
            jump (pc, .fx_passthru_{nid});
        """))

    # ----- Algorithm code: only emit what the class supports -----

    # Echo (echo class only)
    if fx_class == 'echo':
        lines.append(dedent(f"""\
        /* ===================== ECHO ===================== */
        .fx_echo_{nid}:
            r1 = dm(_fx_echo_wptr_{nid});
            r2 = dm(_fx_delay_ms_{nid});  /* delay in samples (MCU converts) */
            /* Read delayed tap */
            r3 = r1 - r2;
            r4 = {echo_buf_size};
            if lt r3 = r3 + r4;
            i0 = _fx_echo_buf_{nid};
            m0 = r3;
            modify(i0, m0);
            f13 = dm(i0, 0);             /* delayed sample (wet) */
            /* Write: input + feedback * delayed */
            f1 = dm(_fx_feedback_{nid});
            f2 = f13 * f1;
            f3 = f15 + f2;
            i0 = _fx_echo_buf_{nid};
            m0 = r1;
            modify(i0, m0);
            dm(i0, 0) = f3;
            /* Advance wptr */
            r15 = 1;
            r1 = r1 + r15;
            comp(r1, r4);
            if ge r1 = r1 - r4;
            dm(_fx_echo_wptr_{nid}) = r1;
            /* Wet signal = delayed tap */
            f0 = f13;
            jump (pc, .fx_mix_{nid});
        """))

    # Ping-Pong (echo class only)
    if fx_class == 'echo':
        half_buf = echo_buf_size // 2
        lines.append(dedent(f"""\
        /* ===================== PING-PONG ===================== */
        .fx_pingpong_{nid}:
            /* Mono input → stereo L/R alternating delays */
            /* Uses echo_buf: first half = L, second half = R */
            r1 = dm(_fx_echo_wptr_{nid});
            r2 = dm(_fx_delay_ms_{nid});
            /* L tap */
            r3 = r1 - r2;
            r4 = {half_buf};
            if lt r3 = r3 + r4;
            i0 = _fx_echo_buf_{nid};
            m0 = r3;
            modify(i0, m0);
            f13 = dm(i0, 0);             /* L delayed */
            /* R tap (second half of buffer) */
            r3 = r1 - r2;
            if lt r3 = r3 + r4;
            r5 = {half_buf};
            r3 = r3 + r5;
            i0 = _fx_echo_buf_{nid};
            m0 = r3;
            modify(i0, m0);
            f14 = dm(i0, 0);             /* R delayed */
            /* Write L: input + fb * R_delayed (cross-feed) */
            f1 = dm(_fx_feedback_{nid});
            f2 = f14 * f1;
            f3 = f15 + f2;
            i0 = _fx_echo_buf_{nid};
            m0 = r1;
            modify(i0, m0);
            dm(i0, 0) = f3;
            /* Write R: fb * L_delayed (no direct input → ping-pong) */
            f2 = f13 * f1;
            r5 = {half_buf};
            r3 = r1 + r5;
            i0 = _fx_echo_buf_{nid};
            m0 = r3;
            modify(i0, m0);
            dm(i0, 0) = f2;
            /* Advance wptr */
            r15 = 1;
            r1 = r1 + r15;
            comp(r1, r4);
            if ge r1 = r1 - r4;
            dm(_fx_echo_wptr_{nid}) = r1;
            /* Stereo out */
            f0 = f13;
            dm(_buf_R_{nid}) = f14;
            jump (pc, .fx_mix_{nid});
        """))

    # Doubling (echo & reverb classes — uses echo_buf, short delay)
    if fx_class in ('echo', 'reverb'):
        lines.append(dedent(f"""\
        /* ===================== DOUBLING ===================== */
        .fx_doubling_{nid}:
            /* Short fixed delay for thickening (15ms = 720 samples) */
            r1 = dm(_fx_echo_wptr_{nid});
            r5 = 720;
            r3 = r1 - r5;
            r4 = {echo_buf_size};
            if lt r3 = r3 + r4;
            i0 = _fx_echo_buf_{nid};
            m0 = r3;
            modify(i0, m0);
            f13 = dm(i0, 0);
            /* Write input to delay buffer */
            i0 = _fx_echo_buf_{nid};
            m0 = r1;
            modify(i0, m0);
            dm(i0, 0) = f15;
            r15 = 1;
            r1 = r1 + r15;
            comp(r1, r4);
            if ge r1 = r1 - r4;
            dm(_fx_echo_wptr_{nid}) = r1;
            f0 = f13;
            jump (pc, .fx_mix_{nid});
        """))

    # Reverb (reverb class only)
    if fx_class == 'reverb':
        lines.append(dedent(f"""\
        /* ===================== REVERB ===================== */
        .fx_reverb_{nid}:
            /* Freeverb: 8 parallel comb-LPF + 4 series allpass */
            r14 = 0x00000000;  /* 0.0 IEEE 754 */                   /* comb sum accumulator */
            i3 = _fx_rv_comb_wptrs_{nid};
            i4 = _fx_rv_comb_lens_{nid};
            i5 = _fx_rv_comb_ofs_{nid};
            i6 = _fx_rv_comb_lpfs_{nid};
            f10 = dm(_fx_feedback_{nid}); /* comb feedback */
            f11 = dm(_fx_damp_{nid});     /* damp1 */
            r12 = 0x3F800000;  /* 1.0 IEEE 754 */
            f12 = f12 - f11;             /* damp2 = 1 - damp1 */
            r5 = 8;
            lcntr = r5; do .rv_comb_{nid} until lce;
                r1 = dm(i3, 0);           /* wptr (peek) */
                r2 = dm(i4, 1);           /* comb length */
                r3 = dm(i5, 1);           /* base offset into comb buffer */
                /* Read delayed sample */
                r4 = r3 + r1;
                i0 = _fx_comb_buf_L_{nid};
                m0 = r4;
                modify(i0, m0);
                f1 = dm(i0, 0);           /* delayed sample */
                /* LPF: filt = damp1*delayed + damp2*prev */
                f4 = dm(i6, 0);           /* prev LP state */
                f5 = f11 * f1;
                f6 = f12 * f4;
                f5 = f5 + f6;
                dm(i6, 1) = f5;           /* store LP, advance i6 */
                /* Write: input + feedback * filtered */
                f7 = f10 * f5;
                f8 = f15 + f7;
                dm(i0, 0) = f8;           /* i0 still at same position */
                /* Advance wptr with wrap */
                r15 = 1;
                r1 = r1 + r15;
                comp(r1, r2);
                if ge r1 = r1 - r2;
                dm(i3, 1) = r1;           /* store, advance i3 */
                /* Accumulate */
                f14 = f14 + f1;
            .rv_comb_{nid}:

            /* Scale comb sum */
            f0 = f14;
            f1 = 0.125;                  /* 1/8 */
            f0 = f0 * f1;

            /* 4 series allpass */
            i3 = _fx_rv_ap_wptrs_{nid};
            i4 = _fx_rv_ap_lens_{nid};
            i5 = _fx_rv_ap_ofs_{nid};
            r10 = 0x3F000000;  /* 0.5 IEEE 754 */                   /* allpass feedback */
            r5 = 4;
            lcntr = r5; do .rv_ap_{nid} until lce;
                r1 = dm(i3, 0);
                r2 = dm(i4, 1);
                r3 = dm(i5, 1);
                r4 = r3 + r1;
                i0 = _fx_allpass_buf_L_{nid};
                m0 = r4;
                modify(i0, m0);
                f1 = dm(i0, 0);           /* buf_out */
                /* Write: in + fb * buf_out */
                f2 = f10 * f1;
                f3 = f0 + f2;
                dm(i0, 0) = f3;
                /* Advance wptr */
                r15 = 1;
                r1 = r1 + r15;
                comp(r1, r2);
                if ge r1 = r1 - r2;
                dm(i3, 1) = r1;
                /* Output: buf_out - input */
                f0 = f1 - f0;
            .rv_ap_{nid}:
                nop;

            /* f0 = reverb output */
            jump (pc, .fx_mix_{nid});
        """))

    # Chorus (modulation class only)
    if fx_class == 'modulation':
        lines.append(dedent(f"""\
        /* ===================== CHORUS ===================== */
        .fx_chorus_{nid}:
            /* LFO → modulated delay (1-20ms range) */
            /* Triangle LFO */
            f0 = dm(_fx_lfo_phase_{nid});
            f1 = dm(_fx_mod_rate_{nid});   /* phase increment per frame */
            f0 = f0 + f1;
            r2 = 0x3F800000;  /* 1.0 IEEE 754 */
            comp(f0, f2);
            if ge f0 = f0 - f2;
            dm(_fx_lfo_phase_{nid}) = f0;
            /* Triangle: 2*|phase - 0.5| → [0,1] */
            r3 = 0x3F000000;  /* 0.5 IEEE 754 */
            f0 = f0 - f3;
            f0 = abs f0;
            f0 = f0 + f0;
            /* Scale to modulation depth (in samples) */
            f4 = dm(_fx_mod_level_{nid});
            f0 = f0 * f4;
            /* Add base delay (480 samples = 10ms centre) */
            r5 = 0x43F00000;  /* 480.0 IEEE 754 */
            f0 = f0 + f5;
            /* Integer + frac for interpolated read */
            r1 = dm(_fx_echo_wptr_{nid});
            r2 = trunc f0;               /* integer delay */
            f6 = float r2;
            f7 = f0 - f6;               /* frac */
            dm(_fx_scratch_{nid}) = f7;
            /* Read sample[n] */
            r3 = r1 - r2;
            r4 = {echo_buf_size};
            if lt r3 = r3 + r4;
            i0 = _fx_echo_buf_{nid};
            m0 = r3;
            modify(i0, m0);
            f8 = dm(i0, 0);
            /* Read sample[n+1] */
            r15 = 1;
            r3 = r3 - r15;
            if lt r3 = r3 + r4;
            i0 = _fx_echo_buf_{nid};
            m0 = r3;
            modify(i0, m0);
            f9 = dm(i0, 0);
            /* Interpolate */
            f7 = dm(_fx_scratch_{nid});
            r10 = 0x3F800000;  /* 1.0 IEEE 754 */
            f10 = f10 - f7;
            f8 = f8 * f10;
            f9 = f9 * f7;
            f13 = f8 + f9;               /* interpolated wet */
            /* Write input to delay buffer */
            i0 = _fx_echo_buf_{nid};
            m0 = r1;
            modify(i0, m0);
            dm(i0, 0) = f15;
            r15 = 1;
            r1 = r1 + r15;
            comp(r1, r4);
            if ge r1 = r1 - r4;
            dm(_fx_echo_wptr_{nid}) = r1;
            f0 = f13;
            jump (pc, .fx_mix_{nid});
        """))

    # Flanger (modulation class only)
    if fx_class == 'modulation':
        lines.append(dedent(f"""\
        /* ===================== FLANGER ===================== */
        .fx_flanger_{nid}:
            /* Short LFO delay (0.1-5ms) with feedback */
            f0 = dm(_fx_lfo_phase_{nid});
            f1 = dm(_fx_mod_rate_{nid});
            f0 = f0 + f1;
            r2 = 0x3F800000;  /* 1.0 IEEE 754 */
            comp(f0, f2);
            if ge f0 = f0 - f2;
            dm(_fx_lfo_phase_{nid}) = f0;
            r3 = 0x3F000000;  /* 0.5 IEEE 754 */
            f0 = f0 - f3;
            f0 = abs f0;
            f0 = f0 + f0;
            f4 = dm(_fx_mod_level_{nid});  /* depth (samples, max ~240) */
            f0 = f0 * f4;
            f5 = 24.0;                    /* base: 0.5ms */
            f0 = f0 + f5;
            r2 = trunc f0;
            r1 = dm(_fx_echo_wptr_{nid});
            r3 = r1 - r2;
            r4 = {echo_buf_size};
            if lt r3 = r3 + r4;
            i0 = _fx_echo_buf_{nid};
            m0 = r3;
            modify(i0, m0);
            f13 = dm(i0, 0);             /* delayed tap */
            /* Write: input + feedback * delayed */
            f1 = dm(_fx_feedback_{nid});
            f2 = f13 * f1;
            f3 = f15 + f2;
            i0 = _fx_echo_buf_{nid};
            m0 = r1;
            modify(i0, m0);
            dm(i0, 0) = f3;
            r15 = 1;
            r1 = r1 + r15;
            comp(r1, r4);
            if ge r1 = r1 - r4;
            dm(_fx_echo_wptr_{nid}) = r1;
            f0 = f13;
            jump (pc, .fx_mix_{nid});
        """))

    # Phaser (modulation class only)
    if fx_class == 'modulation':
        lines.append(dedent(f"""\
        /* ===================== PHASER ===================== */
        .fx_phaser_{nid}:
            /* 4-stage first-order allpass chain with LFO-modulated coeff */
            /* LFO */
            f0 = dm(_fx_lfo_phase_{nid});
            f1 = dm(_fx_mod_rate_{nid});
            f0 = f0 + f1;
            r2 = 0x3F800000;  /* 1.0 IEEE 754 */
            comp(f0, f2);
            if ge f0 = f0 - f2;
            dm(_fx_lfo_phase_{nid}) = f0;
            r3 = 0x3F000000;  /* 0.5 IEEE 754 */
            f0 = f0 - f3;
            f0 = abs f0;
            f0 = f0 + f0;               /* triangle [0,1] */
            /* Map to coefficient range: a = 0.2 + 0.6 * lfo */
            r1 = 0x3F19999A;  /* 0.6 IEEE 754 */
            f0 = f0 * f1;
            r2 = 0x3E4CCCCD;  /* 0.2 IEEE 754 */
            f10 = f0 + f2;               /* allpass coefficient */
            /* 4-stage cascade */
            /* Using echo_buf[0..3] as 4 single-sample state variables */
            f0 = f15;
            i0 = _fx_echo_buf_{nid};
            r5 = 4;
            lcntr = r5; do .ph_ap_{nid} until lce;
                f1 = dm(i0, 0);           /* state = prev_in for this stage */
                f2 = f0 - f1;            /* in - state */
                f3 = f10 * f2;           /* a * (in - state) */
                f4 = f3 + f1;            /* a*(in-state) + state */
                dm(i0, 1) = f0;           /* save current input as new state */
                f0 = f4;                 /* output → input of next stage */
            .ph_ap_{nid}:
            /* Mix with feedback */
            f1 = dm(_fx_feedback_{nid});
            f2 = f0 * f1;
            f15 = f15 + f2;             /* add feedback to next frame input — approximation */
            jump (pc, .fx_mix_{nid});
        """))

    # ----- Passthrough + Mix (always present) -----
    lines.append(dedent(f"""\
        /* ===================== PASSTHROUGH ===================== */
        .fx_passthru_{nid}:
            f0 = f15;                    /* dry pass-through */

        /* ===================== DRY/WET MIX ===================== */
        .fx_mix_{nid}:
            /* f0 = wet, f15 = dry */
            f7 = dm(_fx_mix_{nid});
            r8 = 0x3F800000;  /* 1.0 IEEE 754 */
            f8 = f8 - f7;               /* 1 - mix */
            f0 = f0 * f7;               /* wet * mix */
            f1 = f15 * f8;              /* dry * (1-mix) */
            f0 = f0 + f1;
            dm(_buf_L_{nid}) = r0;
            dm(_buf_{nid}) = r0;
            rts;
        _{nid}_process.end:
    """))

    return '\n'.join(lines)


def gen_crossover(node):
    """Generate dual-output crossover with dual-instance crossfade.

    Linkwitz-Riley 24dB/oct: 2 biquad stages per path (LP and HP).
    Each instance has LP[10]+HP[10] coefficients and LP_state[4]+HP_state[4].
    During crossfade, both instances run all 4 paths, and BOTH bus outputs
    (buf_lp, buf_hp) are linearly blended.

    Register allocation during crossfade (4 biquad calls):
      f15 = saved input   (preserved across all biquad calls)
      f13 = old LP output (preserved across calls 2–4)
      f14 = old HP output (preserved across calls 3–4)
    LP blend is performed before inactive HP call; HP blend done last.
    """
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    bypass10 = '1.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0'
    bypass20 = bypass10 + ', ' + bypass10
    return dedent(f"""\
        {rc}

        /* CROSSOVER: LP/HP split — dual-instance crossfade */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */
        /* freq={p.get('freq','120')}Hz slope={p.get('slope','24')}dB/oct */
        /*
         * Linkwitz-Riley 24dB/oct (2 biquad stages per path).
         * Dual-instance crossfade blends BOTH outputs simultaneously:
         *   buf_lp = (1−α)×lp_old + α×lp_new
         *   buf_hp = (1−α)×hp_old + α×hp_new
         *
         * SPI staging buffer layout: [LP0..LP9, HP0..HP9] = 20 words.
         */

        .section/dm seg_dmda;

        /* ---- Instance A ---- */
        .var _xover_lp_A_{nid}[10] = {bypass10};
        .var _xover_hp_A_{nid}[10] = {bypass10};
        .var _xover_lp_state_A_{nid}[4];
        .var _xover_hp_state_A_{nid}[4];

        /* ---- Instance B ---- */
        .var _xover_lp_B_{nid}[10] = {bypass10};
        .var _xover_hp_B_{nid}[10] = {bypass10};
        .var _xover_lp_state_B_{nid}[4];
        .var _xover_hp_state_B_{nid}[4];

        /* ---- SPI staging buffer (LP[10] + HP[10]) ---- */
        .var _xover_coeffs_next_{nid}[20] = {bypass20};
        .var _xover_swap_pending_{nid} = 0;

        /* ---- Crossfade control ---- */
        .var _xover_active_{nid} = 0;
        .var _xover_xfade_alpha_{nid} = 0.0;
        .var _xover_xfade_step_{nid} = 0.0;

        .var _buf_lp_{nid};
        .var _buf_{nid};
        .var _buf_hp_{nid};

        .section/pm seg_pmco;
        .extern _biquad_cascade_N;
        .global _{nid}_process;
        _{nid}_process:

            /* ── Check for new coefficients ── */
            r4 = dm(_xover_swap_pending_{nid});
            r4 = pass r4;
            if ne call _xover_start_xfade_{nid};

            /* ── Mode check ── */
            r4 = dm(_xover_xfade_step_{nid});
            r4 = pass r4;
            if ne jump .xo_xfade_{nid};

            /* ═══ STEADY STATE ═══════════════════════════════════════ */
            r0 = dm(_buf_{inp});
            f15 = f0;
            r4 = dm(_xover_active_{nid});
            r4 = pass r4;
            if ne jump .xo_ss_B_{nid};
            /* Instance A */
            i0 = _xover_lp_A_{nid};
            i1 = _xover_lp_state_A_{nid};
            r4 = 2;
            call _biquad_cascade_N;
            dm(_buf_lp_{nid}) = r0;
            f0 = f15;
            i0 = _xover_hp_A_{nid};
            i1 = _xover_hp_state_A_{nid};
            r4 = 2;
            call _biquad_cascade_N;
            dm(_buf_hp_{nid}) = r0;
            dm(_buf_{nid}) = r0;
            rts;
        .xo_ss_B_{nid}:
            i0 = _xover_lp_B_{nid};
            i1 = _xover_lp_state_B_{nid};
            r4 = 2;
            call _biquad_cascade_N;
            dm(_buf_lp_{nid}) = r0;
            f0 = f15;
            i0 = _xover_hp_B_{nid};
            i1 = _xover_hp_state_B_{nid};
            r4 = 2;
            call _biquad_cascade_N;
            dm(_buf_hp_{nid}) = r0;
            dm(_buf_{nid}) = r0;
            rts;

            /* ═══ CROSSFADE: 4 biquad paths + 2 blends ═════════════ */
            /*                                                         */
            /*  Register plan:                                         */
            /*    f15 = saved input   (preserved by biquad lib)        */
            /*    f13 = old LP output (preserved by biquad lib)        */
            /*    f14 = old HP output (preserved by biquad lib)        */
            /*                                                         */
            /*  Sequence:                                              */
            /*    1. Active LP  → f13 = old_lp                         */
            /*    2. Active HP  → f14 = old_hp                         */
            /*    3. Inactive LP → blend LP → buf_lp                   */
            /*    4. Inactive HP → blend HP → buf_hp                   */
        .xo_xfade_{nid}:
            r0 = dm(_buf_{inp});
            f15 = f0;                            /* save input */

            /* ── 1. Active LP ── */
            r4 = dm(_xover_active_{nid});
            r4 = pass r4;
            if ne jump .xo_xf_aB_lp_{nid};
            i0 = _xover_lp_A_{nid};
            i1 = _xover_lp_state_A_{nid};
            jump .xo_xf_a_lp_{nid};
        .xo_xf_aB_lp_{nid}:
            i0 = _xover_lp_B_{nid};
            i1 = _xover_lp_state_B_{nid};
        .xo_xf_a_lp_{nid}:
            r4 = 2;
            call _biquad_cascade_N;
            f13 = f0;                            /* old LP */

            /* ── 2. Active HP ── */
            f0 = f15;
            r4 = dm(_xover_active_{nid});
            r4 = pass r4;
            if ne jump .xo_xf_aB_hp_{nid};
            i0 = _xover_hp_A_{nid};
            i1 = _xover_hp_state_A_{nid};
            jump .xo_xf_a_hp_{nid};
        .xo_xf_aB_hp_{nid}:
            i0 = _xover_hp_B_{nid};
            i1 = _xover_hp_state_B_{nid};
        .xo_xf_a_hp_{nid}:
            r4 = 2;
            call _biquad_cascade_N;
            f14 = f0;                            /* old HP */

            /* ── 3. Inactive LP + blend ── */
            f0 = f15;
            r4 = dm(_xover_active_{nid});
            r4 = pass r4;
            if eq jump .xo_xf_iB_lp_{nid};
            i0 = _xover_lp_A_{nid};
            i1 = _xover_lp_state_A_{nid};
            jump .xo_xf_i_lp_{nid};
        .xo_xf_iB_lp_{nid}:
            i0 = _xover_lp_B_{nid};
            i1 = _xover_lp_state_B_{nid};
        .xo_xf_i_lp_{nid}:
            r4 = 2;
            call _biquad_cascade_N;
            /* f0 = new LP; blend with f13 = old LP */
            f12 = dm(_xover_xfade_alpha_{nid});
            r11 = 0x3F800000;  /* 1.0 IEEE 754 */
            f11 = f11 - f12;
            f13 = f13 * f11;                    /* old_lp × (1−α) */
            f0 = f0 * f12;                      /* new_lp × α */
            f0 = f0 + f13;
            dm(_buf_lp_{nid}) = f0;

            /* ── 4. Inactive HP + blend ── */
            f0 = f15;                            /* reload input */
            r4 = dm(_xover_active_{nid});
            r4 = pass r4;
            if eq jump .xo_xf_iB_hp_{nid};
            i0 = _xover_hp_A_{nid};
            i1 = _xover_hp_state_A_{nid};
            jump .xo_xf_i_hp_{nid};
        .xo_xf_iB_hp_{nid}:
            i0 = _xover_hp_B_{nid};
            i1 = _xover_hp_state_B_{nid};
        .xo_xf_i_hp_{nid}:
            r4 = 2;
            call _biquad_cascade_N;
            /* f0 = new HP; blend with f14 = old HP */
            f12 = dm(_xover_xfade_alpha_{nid});
            r11 = 0x3F800000;  /* 1.0 IEEE 754 */
            f11 = f11 - f12;
            f14 = f14 * f11;                    /* old_hp × (1−α) */
            f0 = f0 * f12;                      /* new_hp × α */
            f0 = f0 + f14;
            dm(_buf_hp_{nid}) = f0;
            dm(_buf_{nid}) = r0;

            /* ── Advance α (once per sample, after both blends) ── */
            f14 = dm(_xover_xfade_alpha_{nid});
            f15 = dm(_xover_xfade_step_{nid});
            f14 = f14 + f15;
            dm(_xover_xfade_alpha_{nid}) = f14;
            r15 = 0x3F800000;  /* 1.0 IEEE 754 */
            comp(f14, f15);
            if ge call _xover_xfade_done_{nid};

            rts;

        /* ── Start crossfade: copy LP[10]+HP[10] to dormant ── */
        _xover_start_xfade_{nid}:
            r4 = 0;
            dm(_xover_swap_pending_{nid}) = r4;

            r4 = dm(_xover_active_{nid});
            r4 = pass r4;
            if ne jump .xo_sxf_toA_{nid};

            /* Active=A → dormant=B: copy coeffs, zero state */
            i0 = _xover_coeffs_next_{nid};
            i1 = _xover_lp_B_{nid};
            r4 = 10;
            lcntr = r4; do .xo_cp_lpB_{nid} until lce;
                r0 = dm(i0, 1);
                dm(i1, 1) = r0;
            .xo_cp_lpB_{nid}:
            /* i0 now at +10 → HP section of coeffs_next */
            i1 = _xover_hp_B_{nid};
            r4 = 10;
            lcntr = r4; do .xo_cp_hpB_{nid} until lce;
                r0 = dm(i0, 1);
                dm(i1, 1) = r0;
            .xo_cp_hpB_{nid}:
            i1 = _xover_lp_state_B_{nid};
            r0 = 0;
            r4 = 4;
            lcntr = r4; do .xo_zs_lpB_{nid} until lce;
                dm(i1, 1) = r0;
            .xo_zs_lpB_{nid}:
            i1 = _xover_hp_state_B_{nid};
            r4 = 4;
            lcntr = r4; do .xo_zs_hpB_{nid} until lce;
                dm(i1, 1) = r0;
            .xo_zs_hpB_{nid}:
                nop;
            jump .xo_sxf_go_{nid};

        .xo_sxf_toA_{nid}:
            /* Active=B → dormant=A */
            i0 = _xover_coeffs_next_{nid};
            i1 = _xover_lp_A_{nid};
            r4 = 10;
            lcntr = r4; do .xo_cp_lpA_{nid} until lce;
                r0 = dm(i0, 1);
                dm(i1, 1) = r0;
            .xo_cp_lpA_{nid}:
            i1 = _xover_hp_A_{nid};
            r4 = 10;
            lcntr = r4; do .xo_cp_hpA_{nid} until lce;
                r0 = dm(i0, 1);
                dm(i1, 1) = r0;
            .xo_cp_hpA_{nid}:
            i1 = _xover_lp_state_A_{nid};
            r0 = 0;
            r4 = 4;
            lcntr = r4; do .xo_zs_lpA_{nid} until lce;
                dm(i1, 1) = r0;
            .xo_zs_lpA_{nid}:
            i1 = _xover_hp_state_A_{nid};
            r4 = 4;
            lcntr = r4; do .xo_zs_hpA_{nid} until lce;
                dm(i1, 1) = r0;
            .xo_zs_hpA_{nid}:

        .xo_sxf_go_{nid}:
            r0 = 0;
            dm(_xover_xfade_alpha_{nid}) = r0;
            f0 = {XFADE_STEP};
            dm(_xover_xfade_step_{nid}) = f0;
            rts;
        _xover_start_xfade_{nid}.end:

        /* ── Crossfade complete ── */
        _xover_xfade_done_{nid}:
            r4 = dm(_xover_active_{nid});
            r5 = 1;
            r4 = r4 xor r5;
            dm(_xover_active_{nid}) = r4;
            r4 = 0;
            dm(_xover_xfade_alpha_{nid}) = r4;
            dm(_xover_xfade_step_{nid}) = r4;
            rts;
        _xover_xfade_done_{nid}.end:

        _{nid}_process.end:
    """)


def gen_limiter(node):
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    return dedent(f"""\
        {rc}

        /* LIMITER: Brick-wall peak limiter */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */
        /* threshold={p.get('threshold_db','-0.5')}dB */

        .section/dm seg_dmda;
        .var _lim_on_{node['id']} = 1;
        .var _lim_threshold_{node['id']};
        .var _lim_attack_{node['id']};
        .var _lim_release_{node['id']};
        .var _lim_envelope_{node['id']} = 0.0;
        .var _buf_{node['id']};

        .section/pm seg_pmco;
        .extern _dyn_envelope_follow;
        .extern _dyn_to_dB;
        .extern _dyn_from_dB;
        .global _{node['id']}_process;
        _{node['id']}_process:
            r0 = dm(_buf_{node['inputs_str']});
            /* --- Bypass --- */
            r2 = dm(_lim_on_{node['id']});
            r3 = 0;
            comp(r2, r3);
            if eq jump (pc, .lim_bypass_{node['id']});
            f15 = f0;                   /* save dry input */

            /* Peak detect */
            f0 = abs f0;
            f1 = dm(_lim_attack_{node['id']});
            f2 = dm(_lim_release_{node['id']});
            f3 = dm(_lim_envelope_{node['id']});
            call _dyn_envelope_follow;
            dm(_lim_envelope_{node['id']}) = f0;

            /* Convert to dB */
            call _dyn_to_dB;

            /* Brick-wall: if env_dB > threshold, reduce by excess */
            f1 = dm(_lim_threshold_{node['id']});
            f4 = f0 - f1;             /* excess dB */
            r5 = 0x00000000;  /* 0.0 IEEE 754 */
            comp(f4, f5);
            if le jump (pc, .lim_pass_{node['id']});

            /* Gain reduction = -excess dB */
            f0 = -f4;
            call _dyn_from_dB;
            f14 = f0;                 /* gain_linear < 1.0 */
            f0 = f15;
            f0 = f0 * f14;
            dm(_buf_{node['id']}) = r0;
            rts;

        .lim_bypass_{node['id']}:
            dm(_buf_{node['id']}) = r0;
            rts;
        .lim_pass_{node['id']}:
            /* No limiting needed */
            f0 = f15;
            dm(_buf_{node['id']}) = r0;
            rts;
        _{node['id']}_process.end:
    """)


def gen_monitor(node):
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    return dedent(f"""\
        {rc}

        /* MONITOR: Source select + level control */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        .section/dm seg_dmda;
        .var _mon_source_{node['id']} = 0;       /* 0=Main, 1-12=Aux, 13=Cue */
        .var _mon_level_l_{node['id']} = 1.0;
        .var _mon_level_r_{node['id']} = 1.0;
        .var _mon_level_l_target_{node['id']} = 1.0;
        .var _mon_level_r_target_{node['id']} = 1.0;
        .var _mon_level_step_{node['id']} = 0.0;
        .var _mon_level_frames_{node['id']} = 0;
        .var _buf_{node['id']};

        .section/pm seg_pmco;
        .global _{node['id']}_process;
        _{node['id']}_process:
            /* Ramp level */
            r4 = dm(_mon_level_frames_{node['id']});
            r15 = 1;
            r4 = r4 - r15;
            if le jump (pc, .no_monramp_{node['id']});
            dm(_mon_level_frames_{node['id']}) = r4;
            f1 = dm(_mon_level_l_{node['id']});
            f2 = dm(_mon_level_step_{node['id']});
            f1 = f1 + f2;
            dm(_mon_level_l_{node['id']}) = f1;
            jump (pc, .mon_sel_{node['id']});
        .no_monramp_{node['id']}:
            f1 = dm(_mon_level_l_target_{node['id']});
            dm(_mon_level_l_{node['id']}) = f1;
        .mon_sel_{node['id']}:

            /* Source select: read from appropriate bus buffer */
            /* _mon_source: 0=Main, 1+n=Aux n */
            r0 = dm(_buf_{node['inputs_str']});

            /* Apply L/R level */
            f1 = dm(_mon_level_l_{node['id']});
            f0 = f0 * f1;

            dm(_buf_{node['id']}) = r0;
            rts;
        _{node['id']}_process.end:
    """)


def gen_interchip_send(node):
    p = node['params']
    return dedent(f"""\
        /* INTERCHIP_SEND: mix-fabric line {p.get('sport_id','?')} slot {p.get('slot','?')} (global slot {p.get('global_slot', p.get('slot','?'))}, signal {p.get('signal','?')}) */

        #include "blk_pool.h"

        .section/dm seg_dmda;
        #if DSP4_BLOCK_KERNELS
        .var _tx_slot_{node['id']}[32];
        #else
        .var _tx_slot_{node['id']};
        #endif

        .section/pm seg_pmco;
        .global _{node['id']}_process;
        _{node['id']}_process:
        #if DSP4_BLOCK_KERNELS
            l2 = 0;
            l3 = 0;
            i2 = _buf_{node['inputs_str']};
            i3 = _tx_slot_{node['id']};
            lcntr = 32, do .isk_{node['id']} until lce;
                r0 = dm(i2, 1);
            .isk_{node['id']}: dm(i3, 1) = r0;
            rts;
        #else
            r0 = dm(_buf_{node['inputs_str']});
            dm(_tx_slot_{node['id']}) = r0;
            rts;
        #endif
        _{node['id']}_process.end:
    """)


def gen_interchip_recv(node):
    p = node['params']
    return dedent(f"""\
        /* INTERCHIP_RECV: mix-fabric line {p.get('sport_id','?')} slot {p.get('slot','?')} (global slot {p.get('global_slot', p.get('slot','?'))}, signal {p.get('signal','?')}) */

        .section/dm seg_dmda;
        #if DSP4_BLOCK_KERNELS
        /* Scatter writes slot[sample] under block kernels, so this MUST
         * be a 32-word array even before the node itself is converted --
         * otherwise scatter writes past a scalar. */
        .var _rx_ic_slot_{node['id']}[32];
        .var _buf_{node['id']}[32];
        #else
        .var _rx_ic_slot_{node['id']};
        .var _buf_{node['id']};
        #endif

        .section/pm seg_pmco;
        .global _{node['id']}_process;
        _{node['id']}_process:
        #if DSP4_BLOCK_KERNELS
            l0 = 0;
            l1 = 0;
            i0 = _rx_ic_slot_{node['id']};
            i1 = _buf_{node['id']};
            r5 = 32;
            lcntr = r5; do .icr_lp_{node['id']} until lce;
                r0 = dm(i0, 1);
                dm(i1, 1) = r0;
        .icr_lp_{node['id']}:
                nop;
            rts;
        #else
            r0 = dm(_rx_ic_slot_{node['id']});
            dm(_buf_{node['id']}) = r0;
            rts;
        #endif
        _{node['id']}_process.end:
    """)


def gen_mix_bus_accum(node):
    """Generate unrolled accumulation for mix bus inputs."""
    lines = []
    for inp in node['inputs']:
        lines.append(f'f1 = dm(_buf_{inp});')
        lines.append(f'f2 = dm(i0, 1);')
        lines.append(f'f1 = f1 * f2;')
        lines.append(f'f0 = f0 + f1;')
    if not node['inputs']:
        lines.append('nop;  /* no inputs wired */')
    return '\n            '.join(lines)


def gen_mix_bus(node):
    p = node['params']
    n_src = len(node['inputs'])

    if node['chip'] == '1':
        # Chip 1: ROUTING scatter already accumulated into bus_acc symbols.
        # Derive accumulator name from node ID: C1_BUS_MAIN_L → _bus_acc_main_l
        bus_suffix = node['id'].replace('C1_BUS_', '').lower()
        acc_sym = f'_bus_acc_{bus_suffix}'
        return dedent(f"""\
            /* MIX_BUS: Summing bus (bus_id={p.get('bus_id','?')}) — scatter passthrough */
            /* Chip 1: reads pre-accumulated value from {acc_sym} */

            .section/dm seg_dmda;
            .var _buf_{node['id']};

            .section/pm seg_pmco;
            .extern {acc_sym};
            .global _{node['id']}_process;
            _{node['id']}_process:
                f0 = dm({acc_sym});
                dm(_buf_{node['id']}) = f0;
                rts;
            _{node['id']}_process.end:
        """)
    else:
        # Chip 2: gather pattern — few sources (recv + groups), unrolled accumulation
        return dedent(f"""\
            /* MIX_BUS: Summing bus (bus_id={p.get('bus_id','?')}) */
            /* {n_src} sources */

            .section/dm seg_dmda;
            .var _mix_gains_{node['id']}[{max(n_src, 1)}];
            .var _buf_{node['id']};

            .section/pm seg_pmco;
            .global _{node['id']}_process;
            _{node['id']}_process:
                r0 = 0x00000000;  /* 0.0 IEEE 754 */
                /* Accumulate over {n_src} source buffers × gain */
                i0 = _mix_gains_{node['id']};
                r5 = {max(n_src, 1)};
                {gen_mix_bus_accum(node)}
                dm(_buf_{node['id']}) = f0;
                rts;
            _{node['id']}_process.end:
        """)


def gen_output_tdm(node):
    p = node['params']
    return dedent(f"""\
        /* OUTPUT_TDM: Write to SPORT{p.get('sport_id','?')} slot {p.get('slot_start','?')} */

        .section/dm seg_dmda;
        .var _tx_out_slot_{node['id']};
        .var _buf_{node['id']};

        .section/pm seg_pmco;
        .global _{node['id']}_process;
        _{node['id']}_process:
            r0 = dm(_buf_{node['inputs_str']});
            dm(_tx_out_slot_{node['id']}) = r0;
            dm(_buf_{node['id']}) = r0;
            rts;
        _{node['id']}_process.end:
    """)


def gen_meter(node):
    return dedent(f"""\
        /* METER: Read-back level / GR meter (DSP writes, host polls) */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        #include "blk_pool.h"

        .section/dm seg_dmda;
        .var _mtr_peak_{node['id']} = 0.0;
        .var _mtr_rms_{node['id']} = 0.0;
        .var _mtr_gr_{node['id']} = 0.0;         /* gain reduction (gate or comp) */

        .section/pm seg_pmco;
        .global _{node['id']}_process;
        _{node['id']}_process:
        #if DSP4_BLOCK_KERNELS
            /* Per-block. The source tap is a POOL slot (BLK_CHAIN_B, which
             * is where GAIN writes), live only while this channel's strip
             * is running -- which is why the generator now places each
             * meter immediately after its source instead of leaving it at
             * chain index 320+, thirty-one channels too late.
             *
             * The arithmetic below is UNCHANGED, deliberately. The meters
             * have four recorded defects (they read a Q4.28 word as an IEEE
             * float, among others) and the decision on whether to fix or
             * retire them is the hub's and still open. Converting a node to
             * block form is not the moment to quietly change its numerics;
             * this fixes only WHEN it samples, not WHAT it computes. */
            l2 = 0;
            i2 = BLK_CHAIN_B;
            lcntr = 32, do .mtrk_{node['id']} until lce;
                r0 = dm(i2, 1);
                call _mtr_step_{node['id']};
            .mtrk_{node['id']}: nop;
            rts;

        _mtr_step_{node['id']}:
        #endif
            /* Read source tap */
        #if !DSP4_BLOCK_KERNELS
            r0 = dm(_buf_{node['inputs_str']});
        #endif
            f0 = abs f0;

            /* Peak hold with exponential decay */
            f1 = dm(_mtr_peak_{node['id']});
            comp(f0, f1);
            if le jump (pc, .mtr_decay_{node['id']});
            dm(_mtr_peak_{node['id']}) = f0;
            rts;
        .mtr_decay_{node['id']}:
            /* Decay: peak *= 0.9995 (~150ms to -60dB at 1500 Hz frame rate) */
            r2 = 0x3F7FDF3B;  /* 0.9995 IEEE 754 */
            f1 = f1 * f2;
            dm(_mtr_peak_{node['id']}) = f1;

            /* RMS: single-pole IIR on x² */
            f3 = dm(_mtr_rms_{node['id']});
            f4 = f0 * f0;             /* x² */
            r5 = 0x3C23D70A;  /* 0.01 IEEE 754 */
            f6 = f4 - f3;
            f6 = f5 * f6;
            f3 = f3 + f6;
            dm(_mtr_rms_{node['id']}) = f3;
            rts;
        _{node['id']}_process.end:
    """)


def gen_dca(node):
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    return dedent(f"""\
        {rc}

        /* DCA: Control-only master (no audio path) */
        /* Level/Mute scalar: multiplied into all assigned member faders */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        .section/dm seg_dmda;
        .var _dca_level_{node['id']} = 1.0;
        .var _dca_level_target_{node['id']} = 1.0;
        .var _dca_level_step_{node['id']} = 0.0;
        .var _dca_level_frames_{node['id']} = 0;
        .var _dca_mute_{node['id']} = 0;

        .section/pm seg_pmco;
        .global _{node['id']}_process;
        _{node['id']}_process:
            /* Ramp DCA level */
            r4 = dm(_dca_level_frames_{node['id']});
            r15 = 1;
            r4 = r4 - r15;
            if le jump (pc, .no_dcaramp_{node['id']});
            dm(_dca_level_frames_{node['id']}) = r4;
            f1 = dm(_dca_level_{node['id']});
            f2 = dm(_dca_level_step_{node['id']});
            f1 = f1 + f2;
            dm(_dca_level_{node['id']}) = f1;
            jump (pc, .dca_done_{node['id']});
        .no_dcaramp_{node['id']}:
            f1 = dm(_dca_level_target_{node['id']});
            dm(_dca_level_{node['id']}) = f1;
        .dca_done_{node['id']}:
            /* DCA does not process audio — level is read by member faders */
            rts;
        _{node['id']}_process.end:
    """)


def gen_aux_input(node):
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    return dedent(f"""\
        {rc}

        /* AUX_INPUT: USB/BT/DAW auxiliary stereo input */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        .section/dm seg_dmda;
        .var _auxin_on_{node['id']} = 0;
        .var _auxin_level_{node['id']} = 1.0;
        .var _auxin_level_target_{node['id']} = 1.0;
        .var _auxin_level_step_{node['id']} = 0.0;
        .var _auxin_level_frames_{node['id']} = 0;
        .var _buf_{node['id']};

        .section/pm seg_pmco;
        .global _{node['id']}_process;
        _{node['id']}_process:
            /* Ramp level */
            r4 = dm(_auxin_level_frames_{node['id']});
            r15 = 1;
            r4 = r4 - r15;
            if le jump (pc, .no_auxramp_{node['id']});
            dm(_auxin_level_frames_{node['id']}) = r4;
            f1 = dm(_auxin_level_{node['id']});
            f2 = dm(_auxin_level_step_{node['id']});
            f1 = f1 + f2;
            dm(_auxin_level_{node['id']}) = f1;
            jump (pc, .auxin_go_{node['id']});
        .no_auxramp_{node['id']}:
            f1 = dm(_auxin_level_target_{node['id']});
            dm(_auxin_level_{node['id']}) = f1;
        .auxin_go_{node['id']}:

            /* Read USB/BT input, apply level */
            r0 = dm(_buf_{node['inputs_str']});
            f1 = dm(_auxin_level_{node['id']});
            f0 = f0 * f1;
            /* Check on/off */
            r2 = dm(_auxin_on_{node['id']});
            r3 = 0;
            comp(r2, r3);
            if eq r0 = r3;      /* if off, mute (0 = 0.0f IEEE 754) */
            dm(_buf_{node['id']}) = r0;
            rts;
        _{node['id']}_process.end:
    """)


def gen_talkback(node):
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    return dedent(f"""\
        {rc}

        /* TALKBACK: Talkback mic routing */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        .section/dm seg_dmda;
        .var _talk_on_{node['id']} = 0;
        .var _talk_gain_{node['id']} = 1.0;
        .var _talk_gain_target_{node['id']} = 1.0;
        .var _talk_gain_step_{node['id']} = 0.0;
        .var _talk_gain_frames_{node['id']} = 0;
        .var _talk_hpf_on_{node['id']} = 1;
        .var _talk_hpf_coeffs_{node['id']}[5];
        .var _talk_hpf_state_{node['id']}[2];
        .var _talk_route_{node['id']}[3];         /* up to 3 route destinations */
        .var _buf_{node['id']};

        .section/pm seg_pmco;
        .extern _biquad_mono;
        .global _{node['id']}_process;
        _{node['id']}_process:
            /* Check talkback active */
            r2 = dm(_talk_on_{node['id']});
            r2 = pass r2;
            if eq rts;

            /* Ramp gain */
            r4 = dm(_talk_gain_frames_{node['id']});
            r15 = 1;
            r4 = r4 - r15;
            if le jump (pc, .no_tkramp_{node['id']});
            dm(_talk_gain_frames_{node['id']}) = r4;
            f1 = dm(_talk_gain_{node['id']});
            f2 = dm(_talk_gain_step_{node['id']});
            f1 = f1 + f2;
            dm(_talk_gain_{node['id']}) = f1;
            jump (pc, .tk_go_{node['id']});
        .no_tkramp_{node['id']}:
            f1 = dm(_talk_gain_target_{node['id']});
            dm(_talk_gain_{node['id']}) = f1;
        .tk_go_{node['id']}:

            /* Read talkback mic input */
            r0 = dm(_buf_{node['inputs_str']});
            /* Apply gain */
            f1 = dm(_talk_gain_{node['id']});
            f0 = f0 * f1;

            /* HPF (remove plosives) */
            r2 = dm(_talk_hpf_on_{node['id']});
            r2 = pass r2;
            if eq jump (pc, .tk_no_hpf_{node['id']});
            i0 = _talk_hpf_coeffs_{node['id']};
            i1 = _talk_hpf_state_{node['id']};
            call _biquad_mono;
        .tk_no_hpf_{node['id']}:

            /* Route to destination bus buffers (up to 3) */
            /* Destinations set by MCU via SPI */
            dm(_buf_{node['id']}) = r0;
            rts;
        _{node['id']}_process.end:
    """)


def gen_noise_gen(node):
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    return dedent(f"""\
        {rc}

        /* NOISE_GEN: Pink/white noise + tone generator */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        .section/dm seg_dmda;
        .var _noise_on_{node['id']} = 0;
        .var _noise_level_{node['id']} = 0.0;
        .var _buf_{node['id']};
        .var _noise_hpf_on_{node['id']} = 0;
        .var _noise_lfsr_{node['id']} = 0x12345678;  /* LFSR state for PRNG */
        .var _noise_pink_state_{node['id']}[7];        /* pink filter state */

        .section/pm seg_pmco;
        .global _{node['id']}_process;
        _{node['id']}_process:
            r2 = dm(_noise_on_{node['id']});
            r2 = pass r2;
            if eq rts;

            /* LFSR white noise: x ^= x<<13; x ^= x>>17; x ^= x<<5 */
            r0 = dm(_noise_lfsr_{node['id']});
            r1 = lshift r0 by 13;
            r0 = r0 xor r1;
            r1 = lshift r0 by -17;
            r0 = r0 xor r1;
            r1 = lshift r0 by 5;
            r0 = r0 xor r1;
            dm(_noise_lfsr_{node['id']}) = r0;

            /* Convert to float [-1, 1] via multiply by 1/2^31 */
            f0 = float r0;
            r14 = 0x30000000;        /* 1/2^31 = 2^-31 IEEE 754 */
            f0 = f0 * f14;

            /* Apply level */
            f1 = dm(_noise_level_{node['id']});
            f0 = f0 * f1;

            /* Pink filter (Paul Kellet’s 3dB/oct approximation) */
            r2 = dm(_noise_hpf_on_{node['id']});
            r2 = pass r2;
            if eq jump (pc, .noise_out_{node['id']});
            /* 3-stage pinking: b0 += 0.99886*b0 + white*0.0555179 etc. */
            i0 = _noise_pink_state_{node['id']};
            f2 = dm(i0, 0);              /* b0 */
            r3 = 0x3F7FB54A;  /* 0.99886 IEEE 754 */
            f2 = f2 * f3;
            r3 = 0x3D6366BD;  /* 0.0555179 IEEE 754 */
            f4 = f0 * f3;
            f2 = f2 + f4;
            dm(i0, 1) = f2;
            f3 = dm(i0, 0);              /* b1 */
            r4 = 0x3F7E4A38;  /* 0.99332 IEEE 754 */
            f3 = f3 * f4;
            r4 = 0x3D99C165;  /* 0.0750759 IEEE 754 */
            f5 = f0 * f4;
            f3 = f3 + f5;
            dm(i0, 1) = f3;
            f4 = dm(i0, 0);              /* b2 */
            r5 = 0x3F781062;  /* 0.96900 IEEE 754 */
            f4 = f4 * f5;
            r5 = 0x3E1D8B61;  /* 0.1538520 IEEE 754 */
            f6 = f0 * f5;
            f4 = f4 + f6;
            dm(i0, 1) = f4;
            /* Sum: pink = b0 + b1 + b2 + white*0.5362 */
            f0 = f2 + f3;
            f0 = f0 + f4;
            r5 = 0x3F094467;  /* 0.5362 IEEE 754 */
            f6 = dm(_noise_level_{node['id']});
            f6 = f6 * f5;
            f0 = f0 + f6;
            /* Scale down (pink is louder than white) */
            r1 = 0x3E2AB368;  /* 0.1667 IEEE 754 */
            f0 = f0 * f1;
        .noise_out_{node['id']}:
            dm(_buf_{node['id']}) = r0;
            rts;
        _{node['id']}_process.end:
    """)


# ===========================================================================
# Post-processing: cross-file symbol visibility
# ===========================================================================

def add_global_decls(body):
    """Insert .global before each .var _symbol declaration for linker visibility.

    Every per-node .var whose name starts with underscore is potentially
    referenced by another translation unit (downstream buffer reads,
    block_io scatter/gather, SPI parameter writes).  Emitting .global is
    harmless for purely-internal vars and essential for cross-file ones.
    """
    out = []
    for line in body.split('\n'):
        m = re.match(r'^(\s*)\.var\s+(_\w+)', line)
        if m:
            out.append(f'{m.group(1)}.global {m.group(2)};')
        out.append(line)
    return '\n'.join(out)


def add_extern_decls(body):
    """Add .extern for symbols referenced via dm() but not locally declared.

    Scans for all dm(_symbol) references, collects the set of locally
    declared .var symbols, and emits .extern for the difference.  This
    resolves cross-file buffer reads (upstream _buf_*, _buf_L_*, etc.)
    without requiring each generator to track its own imports.
    """
    # Collect locally declared symbols
    local_vars = set(re.findall(r'\.var\s+(_\w+)', body))
    # Collect all dm(_sym) references (reads and writes)
    referenced = set(re.findall(r'dm\((_[A-Za-z_]\w*)\)', body))
    # Symbols that are already .extern in the body
    existing_externs = set(re.findall(r'\.extern\s+(_\w+)', body))
    # Need .extern for referenced symbols not locally declared and not already extern
    need_extern = sorted(referenced - local_vars - existing_externs)
    if not need_extern:
        return body
    # Insert .extern block right after the first .section/dm line
    extern_block = '\n'.join(f'.extern {sym};' for sym in need_extern)
    # Find insertion point: after first .section/dm line
    lines = body.split('\n')
    out = []
    inserted = False
    for line in lines:
        out.append(line)
        if not inserted and re.match(r'\s*\.section/dm\s', line):
            out.append(extern_block)
            inserted = True
    if not inserted:
        # No .section/dm found — prepend
        out = [extern_block, ''] + out
    return '\n'.join(out)


# ===========================================================================
# Generator dispatch
# ===========================================================================
GENERATORS = {
    'INPUT_TDM':      gen_input_tdm,
    'GAIN':           gen_gain,
    'HPF_LPF':        gen_hpf_lpf,
    'EQ_BIQUAD':      gen_eq_biquad,
    'EQ_MASTER':      gen_eq_biquad,
    'GATE':           gen_gate,
    'COMPRESSOR':     gen_compressor,
    'TUBE_SAT':       gen_tube_sat,
    'DELAY':          gen_delay,
    'FADER_PAN':      gen_fader_pan,
    'ROUTING':        gen_routing,
    'GEQ':            gen_geq,
    'ANTI_FB':        gen_anti_fb,
    'FX_ENGINE':      gen_fx_engine,
    'CROSSOVER':      gen_crossover,
    'LIMITER':        gen_limiter,
    'MONITOR':        gen_monitor,
    'INTERCHIP_SEND': gen_interchip_send,
    'INTERCHIP_RECV': gen_interchip_recv,
    'MIX_BUS':        gen_mix_bus,
    'OUTPUT_TDM':     gen_output_tdm,
    'METER':          gen_meter,
    'DCA':            gen_dca,
    'AUX_INPUT':      gen_aux_input,
    'TALKBACK':       gen_talkback,
    'NOISE_GEN':      gen_noise_gen,
}


# ===========================================================================
# Ramp infrastructure files
# ===========================================================================

def gen_ramp_engine():
    """Generate shared ramp state machine (called once per block)."""
    lines = []
    lines.append('/* ramp_engine.asm — Shared slew/ramp infrastructure for D32 DSP */')
    lines.append('/* AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly. */')
    lines.append('')
    lines.append('/* Frame period: 32 samples @ 48 kHz = 0.6667 ms */')
    lines.append('/* Ramp modes: Instant (0 frames), Slew, LinearFrames, ExpFrames */')
    lines.append('/* Ramp scope: Scalar (per-value ramp), CoeffSetAtomic (double-buffer swap) */')
    lines.append('')
    lines.append('/*')
    lines.append(' * SPI receive handler calls _ramp_set_target to initiate a ramp:')
    lines.append(' *   Input:  r0 = pointer to coefficient')
    lines.append(' *           r1 = new target value')
    lines.append(' *           r2 = ramp mode (0=Instant, 1=Slew, 2=LinearFrames, 3=ExpFrames)')
    lines.append(' *           r3 = frame count (0 for Instant)')
    lines.append(' *           r4 = STRIDE from the value to its companion words')
    lines.append(' *                (1 for a scalar; the array length for the routing')
    lines.append(' *                 sends, whose target/step/frames are parallel')
    lines.append(' *                 arrays -- see _spi_dispatch_cN_stride)')
    lines.append(' *')
    lines.append(' * For Instant: write target directly, frames=0')
    lines.append(' * For Slew/LinearFrames:')
    lines.append(' *   step = (target - current) / frames')
    lines.append(' *   Store step + frame count; per-block ISR decrements and applies')
    lines.append(' * For CoeffSetAtomic:')
    lines.append(' *   Write to _next buffer; set swap_pending flag')
    lines.append(' *   Process function checks flag at block start')
    lines.append(' */')
    lines.append('')
    lines.append('.section/pm seg_pmco;')
    lines.append('.global _ramp_set_target;')
    lines.append('_ramp_set_target:')
    lines.append('    i4 = r0;               /* save coeff pointer in DAG I register */')
    lines.append('    /* Stash the stride FIRST: the slew path loads the current value')
    lines.append('     * into f4, and f4 IS r4, so the incoming stride would be gone. */')
    lines.append('    r12 = r4;              /* stride */')
    lines.append('    r5 = 0;')
    lines.append('    comp(r2, r5);')
    lines.append('    if eq jump (pc, .ramp_instant);')
    lines.append('')
    lines.append('    /* Slew / LinearFrames: compute step = (target - current) / frames */')
    lines.append('    f4 = dm(i4, 0);        /* current value */')
    lines.append('    f5 = f1 - f4;           /* delta */')
    lines.append('    f6 = float r3;          /* frame count as float */')
    lines.append('    /* f5 = f5 / f6 via Newton-Raphson reciprocal (no float div in SHARC) */')
    lines.append('    f7 = RECIPS f6;         /* seed: ~8-bit 1/f6 */')
    lines.append('    f8 = f6 * f7;')
    lines.append('    r10 = 0x40000000;       /* 2.0 in IEEE 754 */')
    lines.append('    f8 = f10 - f8;')
    lines.append('    f7 = f7 * f8;           /* ~16-bit 1/f6 */')
    lines.append('    f8 = f6 * f7;')
    lines.append('    f8 = f10 - f8;')
    lines.append('    f7 = f7 * f8;           /* ~32-bit 1/f6 */')
    lines.append('    f5 = f5 * f7;           /* step = delta / frames */')
    lines.append('    /* Store target at [r0+s], step at [r0+2s], frames at [r0+3s].')
    lines.append('     *')
    lines.append('     * NOT dm(i4, 1) / dm(i4, 2) / dm(i4, 3). That form is POST-modify:')
    lines.append('     * it writes the address currently in i4 and THEN adds the modifier,')
    lines.append('     * so the old code wrote target over the LEVEL at [r0+0], step over')
    lines.append('     * the TARGET at [r0+1], and only landed frames correctly by luck.')
    lines.append('     *')
    lines.append('     * The stride is NOT always 1. A scalar parameter emits')
    lines.append('     * value/target/step/frames back to back, but the routing sends')
    lines.append('     * emit four PARALLEL ARRAYS, so element i of a 12-wide AuxSend has')
    lines.append('     * its companions 12/24/36 words away. Writing those at +1/+2/+3')
    lines.append("     * corrupts the NEIGHBOURING crosspoint's level and leaves the send")
    lines.append('     * with no ramp state at all -- which is why aux and fx sends could')
    lines.append('     * never be set over SPI. The handler passes the right stride from')
    lines.append('     * the generated _spi_dispatch_cN_stride table.')
    lines.append('     *')
    lines.append('     * Bench 2026-08-23: writing 1.0 to C2_PI_IN\'s level put 1/128 in')
    lines.append('     * the target slot, converging to ~1/129 over repeats -- that value')
    lines.append('     * is step = delta/frames, which is what identified the fault. The')
    lines.append('     * block-rate code then copied the bogus target into level and the')
    lines.append('     * audio path went silent, unrecoverable by any further write')
    lines.append('     * because the copy happens every block.')
    lines.append('     *')
    lines.append('     * Explicit address arithmetic instead, so the intent is on the')
    lines.append('     * page. */')
    lines.append('    r11 = r0;')
    lines.append('    r11 = r11 + r12;  i4 = r11;  dm(i4, 0) = f1;   /* target  [r0+s]  */')
    lines.append('    r11 = r11 + r12;  i4 = r11;  dm(i4, 0) = f5;   /* step    [r0+2s] */')
    lines.append('    r11 = r11 + r12;  i4 = r11;  dm(i4, 0) = r3;   /* frames  [r0+3s] */')
    lines.append('    rts;')
    lines.append('')
    lines.append('.ramp_instant:')
    lines.append('    /* Instant must set the TARGET as well as the value: the node\'s')
    lines.append('     * block-rate code is `if frames <= 0: level = target`, so writing')
    lines.append('     * the level alone is undone within one block. Same post-modify')
    lines.append('     * trap as above -- the old dm(i4, 3) wrote back over [r0+0].')
    lines.append('     *')
    lines.append('     * Reached for a profile-0 (InstantCtl) write to a parameter that')
    lines.append('     * HAS ramp state. Setting the level alone is not enough: the')
    lines.append('     * block-rate code runs `if frames <= 0: level = target` every')
    lines.append('     * block, so the write would be undone within one block period.')
    lines.append('     * Level and target both, and frames cleared so the snap path')
    lines.append('     * holds the new value. r5 is still 0 from the mode test. */')
    lines.append('    dm(i4, 0) = f1;                                /* level   [r0+0]  */')
    lines.append('    r11 = r0;')
    lines.append('    r11 = r11 + r12;  i4 = r11;  dm(i4, 0) = f1;   /* target  [r0+s]  */')
    lines.append('    r11 = r11 + r12;                               /* step    [r0+2s] */')
    lines.append('    r11 = r11 + r12;  i4 = r11;  dm(i4, 0) = r5;   /* frames  [r0+3s] */')
    lines.append('    rts;')
    lines.append('_ramp_set_target.end:')
    lines.append('')
    return '\n'.join(lines)


def gen_ramp_tables():
    """Generate ramp profile preset lookup tables."""
    lines = []
    lines.append('/* ramp_tables.asm — Ramp profile presets for D32 DSP */')
    lines.append('/* AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly. */')
    lines.append('')
    lines.append(f'/* Frame period: {FRAME_MS:.4f} ms (32 samples @ 48 kHz) */')
    lines.append('')
    lines.append('.section/dm seg_dmda;')
    lines.append('')
    lines.append('/* Profile table: { mode, up_frames, down_frames, curve, scope } */')
    lines.append('/* mode:  0=Instant, 1=Slew, 2=LinearFrames, 3=ExpFrames */')
    lines.append('/* curve: 0=Linear, 1=Exp, 2=Log, 3=S-Curve */')
    lines.append('/* scope: 0=Scalar, 1=CoeffSetAtomic */')
    lines.append('')

    mode_map = {'Instant': 0, 'Slew': 1, 'LinearFrames': 2, 'ExpFrames': 3}
    curve_map = {'Linear': 0, 'Exp': 1, 'Log': 2, 'S-Curve': 3}
    scope_map = {'Scalar': 0, 'CoeffSetAtomic': 1}

    # Contiguous profile table for indexed lookup by SPI/LP0 handlers
    # Profile IDs: 0=InstantCtl, 1=GainFast, 2=GainSafe, 3=EqSafe, 4=DynSafe
    lines.append('.global _ramp_profile_table;')
    lines.append('_ramp_profile_table:')

    for name, prof in RAMP_PROFILES.items():
        up_f = ms_to_frames(prof['up_ms'])
        dn_f = ms_to_frames(prof['down_ms'])
        m = mode_map.get(prof['mode'], 0)
        c = curve_map.get(prof['curve'], 0)
        s = scope_map.get(prof['scope'], 0)
        lines.append(f'    /* {name} (ID={list(RAMP_PROFILES.keys()).index(name)}) */')
        lines.append(f'    .var = {m};    /* mode: {prof["mode"]} */')
        lines.append(f'    .var = {up_f};    /* up: {prof["up_ms"]}ms = {up_f} frames */')
        lines.append(f'    .var = {dn_f};    /* down: {prof["down_ms"]}ms = {dn_f} frames */')
        lines.append(f'    .var = {c};    /* curve: {prof["curve"]} */')
        lines.append(f'    .var = {s};    /* scope: {prof["scope"]} */')
        lines.append('')

    # Also emit individual labels for direct reference
    lines.append('/* Profile offsets: _ramp_profile_table + id*5; ids per')
    lines.append(' * spi_handler.asm (0=InstantCtl 1=GainFast 2=GainSafe')
    lines.append(' * 3=EqSafe 4=DynSafe). No per-profile alias symbols. */')
    lines.append('')

    return '\n'.join(lines)


# ===========================================================================
# Block I/O: DMA buffer scatter/gather for per-sample processing
# ===========================================================================

def gen_block_io(chip_label, chip_nodes):
    """Generate DMA-layout-accurate scatter/gather + lane tables + buffers.

    Buffer layout is LANE-MAJOR (see MW/D32/DSP/dsp4-plumbing.md): each
    active lane (half-SPORT) is its own DMA stream, so a region is the
    concatenation of per-lane buffers. Packed lanes (MCPDE=1: RX and the
    inter-chip mix fabric) carry only CS-selected slots; chip-2 TX lanes
    are full-window (MCPDE=0). Node address within a region:
        region_base + off + sample*stride
    where off = lane_base_words + index_in_lane, stride = lane word
    count per sample. Per-lane config tables (sport, dir, cs, ...) are
    emitted for sport_init.asm; DMA buffers are allocated HERE with
    exact sizes.

    Chip 1: scatter RX (ADC/superset -> input slots), gather IC TX
    Chip 2: scatter IC RX (mix fabric -> recv slots), gather TX
    Each scatter/gather takes r0 = sample index (0..31).
    """
    BLOCK = 32

    def lane_layout(specs, window=None):
        """specs: [(node, sport, slot)]. window=None -> packed lanes;
        window=N -> full-window lanes of N slots.
        Returns (lanes, per_node): lanes = [{sport, cs, count}] sorted by
        sport; per_node[node_id] = (off_words, stride)."""
        by_sport = {}
        for node, sport, slot in specs:
            by_sport.setdefault(sport, []).append((slot, node))
        lanes = []
        per_node = {}
        base = 0
        for sport in sorted(by_sport):
            slots = sorted(by_sport[sport])
            cs = 0
            for slot, _ in slots:
                cs |= (1 << slot)
            count = window if window is not None else len(slots)
            for rank, (slot, node) in enumerate(slots):
                idx = slot if window is not None else rank
                per_node[node['id']] = (base + idx, count)
            lanes.append({'sport': sport, 'cs': cs, 'count': count})
            base += count * BLOCK
        return lanes, per_node

    def emit_tables(lines, prefix, nodes_ordered, per_node, extern_fmt, var_fmt):
        n = len(nodes_ordered)
        for node in nodes_ordered:
            lines.append(f'.extern {extern_fmt.format(id=node["id"])};')
        lines.append('#if DSP4_BLOCK_KERNELS')
        lines.append(f'.global {prefix}_off;')
        lines.append(f'.global {prefix}_stride;')
        lines.append('#endif')
        lines.append(f'.var {prefix}_off[{n}] =')
        for i, node in enumerate(nodes_ordered):
            comma = ',' if i < n - 1 else ';'
            off, stride = per_node[node['id']]
            lines.append(f'    {off}{comma}')
        lines.append(f'.var {prefix}_stride[{n}] =')
        for i, node in enumerate(nodes_ordered):
            comma = ',' if i < n - 1 else ';'
            off, stride = per_node[node['id']]
            lines.append(f'    {stride}{comma}')
        lines.append(f'.var {var_fmt}[{n}] =')
        for i, node in enumerate(nodes_ordered):
            comma = ',' if i < n - 1 else ';'
            lines.append(f'    {extern_fmt.format(id=node["id"])}{comma}')
        lines.append('')

    def region_words(lanes):
        return sum(ln['count'] for ln in lanes) * BLOCK

    def emit_copy_loop(lines, fn, count, base_sym, off_tbl, stride_tbl,
                       ptr_tbl, to_dma, scale=None):
        """addr = dm(base_sym) + off[i] + sample*stride[i]; copy between
        DMA word and *ptr[i]. scale (FORMAT fixed only): 'rx' converts
        converter Q1.31 -> Q4.28 (>>3); 'tx' converts Q4.28 -> Q1.31
        (<<3 with saturation). IC fabric lanes copy raw Q4.28."""
        lines.append(f'.global {fn};')
        lines.append(f'{fn}:')
        if not to_dma and scale == 'rx':
            # Under per-block kernels the INPUT_TDM kernels read the DMA
            # buffer themselves and do the >>3 inline, so staging every
            # channel into a slot array first is pure cost: 1,472 words of
            # DM and a copy per sample per channel. Nothing to do here.
            lines.append(f'#if DSP4_BLOCK_KERNELS')
            lines.append(f'    rts;')
            lines.append(f'#endif')
        lines.append(f'    /* r0 = sample index (0..{BLOCK-1}) */')
        lines.append(f'    r6 = dm({base_sym});')
        lines.append(f'    i1 = {off_tbl};')
        lines.append(f'    i2 = {stride_tbl};')
        lines.append(f'    i3 = {ptr_tbl};')
        lines.append(f'    r7 = {count};')
        loop = fn.lstrip('_')
        lines.append(f'    lcntr = r7; do .{loop}_lp until lce;')
        lines.append(f'        r3 = dm(i1, 1);       /* off */')
        lines.append(f'        r4 = dm(i2, 1);       /* stride */')
        lines.append(f'        r2 = r0 * r4 (SSI);   /* sample*stride */')
        lines.append(f'        r3 = r3 + r2;')
        lines.append(f'        r3 = r6 + r3;         /* DMA word address */')
        lines.append(f'        r5 = dm(i3, 1);       /* node slot var ptr */')
        # Per-BLOCK kernels: the slot variables become 32-word arrays so a
        # kernel can consume or produce a whole block, and both directions
        # index by sample -- one add. The TX side used to be scalar because
        # nothing converted wrote a TX slot; the block-form INTERCHIP_SEND
        # now does, so gather indexes too. Leaving it scalar once buses and
        # sends were converted would have sent sample 0 thirty-two times.
        lines.append(f'        #if DSP4_BLOCK_KERNELS')
        lines.append(f'        r5 = r5 + r0;         /* slot[sample] */')
        lines.append(f'        #endif')
        loop = fn.lstrip('_')
        if to_dma:
            lines.append(f'        i4 = r5;')
            lines.append(f'        r2 = dm(i4, 0);   /* read slot var */')
            if scale == 'tx' and FORMAT == 'fixed':
                lines.append(f'        /* Q4.28 -> Q1.31 with saturation */')
                lines.append(f'        r8 = ashift r2 by 3;')
                lines.append(f'        r9 = ashift r8 by -3;')
                lines.append(f'        comp(r9, r2);')
                lines.append(f'        if eq jump (pc, .{loop}_ok);')
                lines.append(f'        r8 = 0x7FFFFFFF;')
                lines.append(f'        r9 = ashift r2 by -31;')
                lines.append(f'        r8 = r8 xor r9;')
                lines.append(f'    .{loop}_ok:')
                lines.append(f'        r2 = r8;')
            lines.append(f'        i4 = r3;')
            lines.append(f'        dm(i4, 0) = r2;   /* write DMA */')
        else:
            lines.append(f'        i4 = r3;')
            lines.append(f'        r2 = dm(i4, 0);   /* read DMA */')
            if scale == 'rx' and FORMAT == 'fixed':
                lines.append(f'        r2 = ashift r2 by -3;  /* Q1.31 -> Q4.28 */')
            lines.append(f'        i4 = r5;')
            lines.append(f'        dm(i4, 0) = r2;   /* write slot var */')
        lines.append(f'    .{loop}_lp:')
        lines.append(f'        nop;')
        lines.append(f'    rts;')
        lines.append(f'{fn}.end:')
        lines.append('')

    def emit_meter_scan(lines, fn, count, ptr_tbl, what):
        lines.append(f'/* Peak-hold meter scan over {what} (once per block) */')
        lines.append(f'.global {fn};')
        lines.append(f'{fn}:')
        lines.append(f'    i0 = {ptr_tbl};')
        lines.append(f'    i1 = _meter_peaks;')
        lines.append(f'    m0 = 0;')
        lines.append(f'    m1 = 1;')
        lines.append(f'    r5 = {count};')
        loop = fn.lstrip('_')
        lines.append(f'    lcntr = r5; do .{loop}_lp until lce;')
        lines.append(f'        r2 = dm(i0, 1);')
        lines.append(f'        i2 = r2;')
        if FORMAT == 'fixed':
            lines.append(f'        r3 = dm(i2, 0);   /* Q4.28 sample */')
            lines.append(f'        r3 = abs r3;')
            lines.append(f'        r4 = -28;')
            lines.append(f'        f3 = float r3 by r4;  /* peaks stay FLOAT (readback contract) */')
        else:
            lines.append(f'        f3 = dm(i2, 0);')
            lines.append(f'        f3 = abs f3;')
        lines.append(f'        f4 = dm(i1, m0);')
        lines.append(f'        comp(f3, f4);')
        lines.append(f'        if gt f4 = f3;')
        lines.append(f'        dm(i1, m1) = f4;')
        lines.append(f'    .{loop}_lp:')
        lines.append(f'        nop;')
        lines.append(f'    rts;')
        lines.append(f'{fn}.end:')
        lines.append('')

    lines = []
    lines.append(f'/* block_io.asm — DMA↔node scatter/gather for {chip_label.upper()} */')
    lines.append('/* AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly. */')
    lines.append('/* Lane-major DMA layout per MW/D32/DSP/dsp4-plumbing.md. */')
    lines.append('')

    if chip_label == 'chip1':
        # --- RX: INPUT_TDM nodes, packed lanes (MCPDE=1) ---
        input_nodes = [n for n in chip_nodes if n['type'] == 'INPUT_TDM']
        input_nodes.sort(key=lambda n: (int(n['params'].get('sport_id', '0')),
                                        int(n['params'].get('slot_start', '0'))))
        num_rx = len(input_nodes)
        rx_specs = [(n, int(n['params'].get('sport_id', '0')),
                     int(n['params'].get('slot_start', '0'))) for n in input_nodes]
        rx_lanes, rx_map = lane_layout(rx_specs)

        # --- IC TX: INTERCHIP_SEND nodes, packed lanes (MCPDE=1) ---
        send_nodes = [n for n in chip_nodes if n['type'] == 'INTERCHIP_SEND']
        ic_slot_of = lambda n: int(n['params'].get('global_slot',
                                                   n['params'].get('slot', '0')))
        send_nodes.sort(key=ic_slot_of)
        num_ic = len(send_nodes)
        ic_specs = [(n, int(n['params'].get('sport_id', '7')),
                     int(n['params'].get('slot', '0'))) for n in send_nodes]
        ic_lanes, ic_map = lane_layout(ic_specs)

        lines.append('.section/dm seg_dmda;')
        lines.append('')
        lines.append(f'/* RX node tables ({num_rx} packed channels over '
                     f'{len(rx_lanes)} lanes) */')
        # Hand each INPUT_TDM node its own DMA offset and stride so its
        # block kernel can read the DMA buffer DIRECTLY, instead of scatter
        # staging 46 x 32 words into slot arrays first. That reclaims 1,472
        # words of DM and removes a whole copy per sample.
        for _i, _n in enumerate(input_nodes):
            _off, _stride = rx_map[_n['id']]
            _n['params']['rx_off'] = _off
            _n['params']['rx_stride'] = _stride
            _n['params']['rx_index'] = _i
        emit_tables(lines, '_c1_rx', input_nodes, rx_map,
                    '_rx_slot_{id}', '_c1_rx_slot_ptrs')

        lines.append('#if DSP4_BLOCK_KERNELS')
        lines.append('/* Inverse of _rx_patch_regs for the DMA-direct input kernels:')
        lines.append(' * _c1_rx_node_entry[k] = the RX table entry feeding the node at')
        lines.append(' * default index k. The per-sample scatter applied the patch by')
        lines.append(' * rewriting slot POINTERS; a kernel that reads DMA itself needs')
        lines.append(' * the mapping the other way round. Rebuilt by _rx_patch_apply. */')
        lines.append('.global _c1_rx_node_entry;')
        lines.append(f'.var _c1_rx_node_entry[{num_rx}] =')
        for _k in range(num_rx):
            lines.append('    %d%s' % (_k, ',' if _k < num_rx - 1 else ';'))
        lines.append('#endif')
        lines.append('')
        lines.append(f'.global _c1_rx_slot_count;')
        lines.append(f'.var _c1_rx_slot_count = {num_rx};')
        lines.append('')
        lines.append('/* Boot-time input patch (product config, SPI regs 0xF010+):')
        lines.append(' * _rx_patch_regs[i] = table index whose slot var receives')
        lines.append(' * RX table entry i. Identity by default; the D24 console-')
        lines.append(' * channel interleave is written by the Pi and applied at')
        lines.append(' * CONFIG_COMMIT. */')
        lines.append('.global _rx_patch_regs;')
        lines.append(f'.var _rx_patch_regs[{num_rx}] =')
        for i in range(num_rx):
            comma = ',' if i < num_rx - 1 else ';'
            lines.append(f'    {i}{comma}')
        lines.append(f'.var _c1_rx_slot_defaults[{num_rx}] =')
        for i, n in enumerate(input_nodes):
            comma = ',' if i < num_rx - 1 else ';'
            lines.append(f'    _rx_slot_{n["id"]}{comma}')
        lines.append('')

        lines.append(f'/* IC TX node tables ({num_ic} packed mix-fabric slots '
                     f'over {len(ic_lanes)} lanes) */')
        emit_tables(lines, '_c1_ic_tx', send_nodes, ic_map,
                    '_tx_slot_{id}', '_c1_ic_tx_ptrs')

        rx_words = region_words(rx_lanes)
        ic_words = region_words(ic_lanes)

        lines.append('/* DMA ping-pong buffers live in generated lane_config.c')
        lines.append(' * (byte-addressed C world — DMA + descriptors take byte')
        lines.append(' * addresses); asm reaches them via the word-converted')
        lines.append(' * active-buf pointers set by _set_rx_bufs/_set_tx_bufs. */')
        lines.append('.extern _rx_active_buf;')
        lines.append('.extern _ic_tx_active_buf;')
        lines.append('.extern _meter_peaks;')
        lines.append('')

        lines.append('.section/pm seg_pmco;')
        lines.append('')
        lines.append(f'/* Scatter {num_rx} RX channels (lane-major packed) */')
        emit_copy_loop(lines, '_scatter_chip1', num_rx, '_rx_active_buf',
                       '_c1_rx_off', '_c1_rx_stride', '_c1_rx_slot_ptrs',
                       to_dma=False, scale='rx')
        emit_meter_scan(lines, '_meter_scan_chip1', num_rx,
                        '_c1_rx_slot_ptrs', 'RX inputs')
        lines.append(f'/* Gather {num_ic} inter-chip sends (lane-major packed) */')
        emit_copy_loop(lines, '_gather_chip1', num_ic, '_ic_tx_active_buf',
                       '_c1_ic_tx_off', '_c1_ic_tx_stride', '_c1_ic_tx_ptrs',
                       to_dma=True)

        # _rx_patch_apply: rebuild the RX pointer table from the patch regs
        lines.append('/* Apply boot-time input patch: ptrs[i] = defaults[patch[i]] */')
        lines.append('.global _rx_patch_apply;')
        lines.append('_rx_patch_apply:')
        lines.append('    i0 = _rx_patch_regs;')
        lines.append('    i1 = _c1_rx_slot_ptrs;')
        lines.append(f'    r5 = {num_rx};')
        lines.append(f'    r6 = {num_rx - 1};          /* clamp bound */')
        lines.append('#if DSP4_BLOCK_KERNELS')
        lines.append('    r7 = 0;               /* running entry index for the inverse */')
        lines.append('#endif')
        lines.append('    lcntr = r5; do .c1_rxpatch until lce;')
        lines.append('        r2 = dm(i0, 1);       /* patch index */')
        lines.append('        comp(r2, r6);')
        lines.append('        if gt r2 = r6;        /* clamp out-of-range index */')
        lines.append('        r3 = 0;')
        lines.append('        comp(r2, r3);')
        lines.append('        if lt r2 = r3;')
        lines.append('        i2 = _c1_rx_slot_defaults;')
        lines.append('        m1 = r2;')
        lines.append('        modify(i2, m1);')
        lines.append('        r3 = dm(i2, 0);       /* default ptr at patch index */')
        lines.append('        dm(i1, 1) = r3;')
        lines.append('#if DSP4_BLOCK_KERNELS')
        lines.append('        /* node_entry[patch[i]] = i -- the inverse kernels need */')
        lines.append('        i2 = _c1_rx_node_entry;')
        lines.append('        m1 = r2;')
        lines.append('        modify(i2, m1);')
        lines.append('        dm(i2, 0) = r7;')
        lines.append('        r7 = r7 + 1;')
        lines.append('#endif')
        lines.append('    .c1_rxpatch:')
        lines.append('        nop;')
        lines.append('    rts;')
        lines.append('_rx_patch_apply.end:')
        lines.append('')

    elif chip_label == 'chip2':
        # --- IC RX: INTERCHIP_RECV nodes, packed lanes (MCPDE=1) ---
        recv_nodes = [n for n in chip_nodes if n['type'] == 'INTERCHIP_RECV']
        ic_slot_of = lambda n: int(n['params'].get('global_slot',
                                                   n['params'].get('slot', '0')))
        recv_nodes.sort(key=ic_slot_of)
        num_ic_rx = len(recv_nodes)
        ic_specs = [(n, int(n['params'].get('sport_id', '7')),
                     int(n['params'].get('slot', '0'))) for n in recv_nodes]
        ic_lanes, ic_map = lane_layout(ic_specs)

        # --- TX: OUTPUT_TDM nodes, full-window lanes (MCPDE=0) ---
        output_nodes = [n for n in chip_nodes if n['type'] == 'OUTPUT_TDM']
        tx_sport_slots = {int(n['params'].get('sport_slots', '8'))
                          for n in output_nodes} or {8}
        assert len(tx_sport_slots) == 1, \
            'OUTPUT_TDM sport_slots must be uniform across all TX lanes'
        sps = tx_sport_slots.pop()
        output_nodes.sort(key=lambda n: (int(n['params'].get('sport_id', '0')),
                                         int(n['params'].get('slot_start', '0'))))
        num_tx = len(output_nodes)
        tx_specs = [(n, int(n['params'].get('sport_id', '0')),
                     int(n['params'].get('slot_start', '0'))) for n in output_nodes]
        tx_lanes, tx_map = lane_layout(tx_specs, window=sps)
        # widen CS masks for multi-slot nodes (slot_count > 1)
        for n in output_nodes:
            cnt = int(n['params'].get('slot_count', '1'))
            if cnt > 1:
                sport = int(n['params'].get('sport_id', '0'))
                start = int(n['params'].get('slot_start', '0'))
                for ln in tx_lanes:
                    if ln['sport'] == sport:
                        for s in range(start, start + cnt):
                            ln['cs'] |= (1 << s)

        lines.append('.section/dm seg_dmda;')
        lines.append('')
        lines.append(f'/* IC RX node tables ({num_ic_rx} packed mix-fabric slots '
                     f'over {len(ic_lanes)} lanes) */')
        emit_tables(lines, '_c2_ic_rx', recv_nodes, ic_map,
                    '_rx_ic_slot_{id}', '_c2_ic_rx_ptrs')

        lines.append(f'/* TX node tables ({num_tx} outputs over '
                     f'{len(tx_lanes)} full-window lanes of {sps}) */')
        emit_tables(lines, '_c2_tx', output_nodes, tx_map,
                    '_tx_out_slot_{id}', '_c2_tx_ptrs')

        ic_words = region_words(ic_lanes)
        tx_words = region_words(tx_lanes)

        lines.append('/* DMA ping-pong buffers live in generated lane_config.c —')
        lines.append(' * see the chip-1 note. */')
        lines.append('.extern _ic_rx_active_buf;')
        lines.append('.extern _tx_active_buf;')
        lines.append('.extern _meter_peaks;')
        lines.append('')

        lines.append('.section/pm seg_pmco;')
        lines.append('')
        lines.append(f'/* Scatter {num_ic_rx} inter-chip recvs (lane-major packed) */')
        emit_copy_loop(lines, '_scatter_chip2', num_ic_rx, '_ic_rx_active_buf',
                       '_c2_ic_rx_off', '_c2_ic_rx_stride', '_c2_ic_rx_ptrs',
                       to_dma=False)
        lines.append(f'/* Gather {num_tx} outputs (lane-major full-window) */')
        emit_copy_loop(lines, '_gather_chip2', num_tx, '_tx_active_buf',
                       '_c2_tx_off', '_c2_tx_stride', '_c2_tx_ptrs',
                       to_dma=True, scale='tx')
        emit_meter_scan(lines, '_meter_scan_chip2', num_tx,
                        '_c2_tx_ptrs', 'TX outputs')

    if chip_label == 'chip1':
        lane_info = [('c1_rx_lanes', rx_lanes, 0, 1, 7, rx_words, 'c1_rx'),
                     ('c1_ic_lanes', ic_lanes, 1, 1, 15, ic_words, 'c1_ic')]
    else:
        lane_info = [('c2_ic_lanes', ic_lanes, 0, 1, 15, ic_words, 'c2_ic'),
                     ('c2_tx_lanes', tx_lanes, 1, 0, sps - 1, tx_words, 'c2_tx')]
    return '\n'.join(lines), lane_info


def gen_lane_config_c(chip_label, lane_info):
    """Generated C data consumed by sport_config.c (C linkage — the
    byte-addressed SHARC C ABI dot-mangles symbols, so cross-language
    data sharing goes C-to-C)."""
    BLOCK = 32
    out = []
    out.append(f'/* lane_config.c — generated lane tables + DMA buffers for {chip_label.upper()} */')
    out.append('/* AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly. */')
    out.append('/* Entries of 4: sport, cs_mask, words_per_sample, region_off. */')
    out.append('')
    for name, lanes, dirbit, mcpde, wsize, words, region in lane_info:
        n = len(lanes)
        out.append(f'const int {name}_count = {n};')
        out.append(f'const int {name}_dir = {dirbit};    /* 0 = RX (half A), 1 = TX (half B) */')
        out.append(f'const int {name}_mcpde = {mcpde};')
        out.append(f'const int {name}_wsize = {wsize};')
        out.append(f'const int {name}[{n * 4}] = {{')
        base = 0
        for i, ln in enumerate(lanes):
            comma = ',' if i < n - 1 else ''
            out.append(f'    {ln["sport"]}, 0x{ln["cs"]:04X}, {ln["count"]}, {base}{comma}')
            base += ln['count'] * BLOCK
        out.append('};')
        out.append('')
        out.append(f'const int {region}_region_words = {words};')
        # ONE object holding both halves, so ping and pong are guaranteed
        # adjacent: pong is always ping + region_words. Two separately
        # declared arrays are not guaranteed to be laid out next to each
        # other, and the DMA rings walk from one half to the other with a
        # 2D autobuffer whose YMOD is exactly that distance -- so the
        # adjacency has to be a fact, not an observation. dma_config.c
        # derives REGION_*_PONG from this symbol; there is deliberately no
        # separate _buf_pong array any more.
        out.append('#pragma align 32')
        out.append(f'unsigned int {region}_buf_ping[2 * {words}];'
                   f'  /* [0..{words}) ping, [{words}..2*{words}) pong */')
        out.append('')
    return '\n'.join(out)


def _gen_scope_gates_legacy(chip_label, chip_nodes):
    """Generate the product-scope gate table + apply routine.

    Nodes carrying a scope=D24/D32 param AND a known runtime enable
    variable are force-disabled at CONFIG_COMMIT when the booted product
    does not match. Product ids: 0=D32, 1=D24 (must match
    product_config.asm).
    """
    ENABLE_SYMS = {'AUX_INPUT': '_auxin_on_'}
    SCOPE_IDS = {'D32': 0, 'D24': 1}
    entries = []
    for n in chip_nodes:
        sc = n['params'].get('scope')
        if sc and n['type'] in ENABLE_SYMS:
            entries.append((SCOPE_IDS[sc], ENABLE_SYMS[n['type']] + n['id'],
                            n['id'], sc))

    lines = []
    lines.append(f'/* scope_gates.asm — product-scope gating for {chip_label.upper()} */')
    lines.append('/* AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly. */')
    lines.append('/* Product ids: 0=D32, 1=D24 (see product_config.asm). */')
    lines.append('')
    lines.append('.section/dm seg_dmda;')
    lines.append('')
    n_gates = len(entries)
    lines.append(f'.global _scope_gate_count;')
    lines.append(f'.var _scope_gate_count = {n_gates};')
    if entries:
        for _, sym, _, _ in entries:
            lines.append(f'.extern {sym};')
        lines.append(f'.var _scope_gate_products[{n_gates}] =')
        for i, (pid, _, nid, sc) in enumerate(entries):
            comma = ',' if i < n_gates - 1 else ';'
            lines.append(f'    {pid}{comma}    /* {nid} ({sc}) */')
        lines.append(f'.var _scope_gate_ptrs[{n_gates}] =')
        for i, (_, sym, _, _) in enumerate(entries):
            comma = ',' if i < n_gates - 1 else ';'
            lines.append(f'    {sym}{comma}')
    lines.append('')
    lines.append('.section/pm seg_pmco;')
    lines.append('')
    lines.append('/* Force-off enables of nodes scoped to a different product.')
    lines.append(' * r0 = booted product id. Clobbers r2-r5, i0-i2. */')
    lines.append('.global _scope_gates_apply;')
    lines.append('_scope_gates_apply:')
    if entries:
        lines.append('    i0 = _scope_gate_products;')
        lines.append('    i1 = _scope_gate_ptrs;')
        lines.append(f'    r5 = {n_gates};')
        lines.append('    lcntr = r5; do .sgate until lce;')
        lines.append('        r2 = dm(i0, 1);       /* node product id */')
        lines.append('        r3 = dm(i1, 1);       /* ptr to enable var */')
        lines.append('        comp(r2, r0);')
        lines.append('        if eq jump (pc, .sgate_keep);')
        lines.append('        i2 = r3;')
        lines.append('        r4 = 0;')
        lines.append('        dm(i2, 0) = r4;       /* wrong product: force off */')
        lines.append('    .sgate_keep:')
        lines.append('        nop;')
        lines.append('    .sgate:')
        lines.append('        nop;')
        lines.append('    rts;')
    else:
        lines.append('    rts;                      /* no scoped nodes on this chip */')
    lines.append('_scope_gates_apply.end:')
    lines.append('')
    return '\n'.join(lines)

def gen_scope_gates(chip_label, chip_nodes):
    """Product-scope gating.

    The DEFAULT path is the shipping generator, untouched and emitted
    verbatim -- this file's contents are data in the firmware image, so
    changing them moves the default build's md5.

    Under DSP4_BLOCK_KERNELS an additional per-node SKIP table is emitted
    and process_all consults it, so a node scoped to another product is
    never CALLED rather than being entered and returning early. Measured
    2026-08-24: the scoped nodes are ~816 cycles/sample, 8.0 % of the block
    budget. Per-sample the check would cost 32x what it saves, which is why
    it is flag-only.
    """
    SCOPE_IDS = {'D32': 0, 'D24': 1}
    legacy = _gen_scope_gates_legacy(chip_label, chip_nodes)
    pref = 'c1' if chip_label == 'chip1' else 'c2'
    entries = [(idx, SCOPE_IDS[n['params']['scope']], n['id'])
               for idx, n in enumerate(chip_nodes)
               if n['params'].get('scope') in SCOPE_IDS]

    L = [legacy.rstrip('\n'), '']
    L.append('')
    return '\n'.join(L)

def gen_eq_biquad_fixed(node):
    # Per-block wrapper, same shape as FILT: emitted AHEAD of the
    # per-sample body, which is untouched, so without the flag
    # _{nid}_process falls straight through and the default image cannot
    # move. EQ runs the cascade with r4 = 4, which is why the
    # i0-advance-between-stages fix had to land first -- without it every
    # band would have run with band 0's coefficients.
    import re as _re
    if _re.match(r'^C\d+_EQ_\d+$', node['id']):
        blk_eq_body = _EQ_BLK_BODY.format(
            nid=node['id'], inp=node['inputs_str'],
            bands=int(node['params'].get('bands', '4')))
    else:
        blk_eq_body = ''

    """Fixed-point (Q4.28) EQ biquad — offset-form cascade (D5).

    Same SPI/staging/crossfade contract as the float node: the host
    writes FLOAT RBJ coefficient words into _coeffs_next (wire format
    unchanged); at swap time _bq_fx_convert_N produces the Q4.28 offset
    coefficient set for the dormant instance (biquad_fx.asm, normative
    model fixed_ref.biquad). State is 6 words/stage (x1,x2,y1,y2,efb).
    Crossfade alpha/step stay float (control plane); the sample blend
    runs fixed: y = ya + rns((yb-ya)*alpha_q31, 31).
    """
    p = node['params']
    bands = int(p.get('bands', '4'))
    n5 = bands * 5      # coeff words per instance (fixed offset form)
    n6 = bands * 6      # state words per instance
    rc = ramp_comment(node['ramp_profile'])
    # bypass = identity: b0=1.0 -> 0x10000000; n1=2.0 -> 0x20000000;
    # n2=-1.0 -> -0x10000000; c1=2.0; c2=1.0 (a1=0,a2=0)
    bypass = ', '.join(['0x10000000, 0x20000000, 0xF0000000, 0x20000000, 0x10000000'] * bands)
    nid = node['id']
    inp = node['inputs_str']
    return dedent(f"""\
        {rc}

        /* EQ_BIQUAD (FIXED Q4.28, D5): {bands}-band, dual-instance crossfade */
        #include "blk_pool.h" 
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */
        /* Normative model: tools/dsp/fixed_ref.py::biquad (offset form). */

        .section/dm seg_dmda;

        .var _eq_coeffs_A_{nid}[{n5}] = {bypass};
        .var _eq_state_A_{nid}[{n6}];
        .var _eq_coeffs_B_{nid}[{n5}] = {bypass};
        .var _eq_state_B_{nid}[{n6}];

        /* SPI staging (FLOAT RBJ words — wire format unchanged) */
        .var _eq_coeffs_next_{nid}[{n5}];
        .var _eq_swap_pending_{nid} = 0;

        .var _eq_active_{nid} = 0;            /* 0 = A active, 1 = B */
        .var _eq_xfade_alpha_{nid} = 0.0;     /* float control */
        .var _eq_xfade_step_{nid} = 0.0;

        .var _tap_post_eq_{nid};              /* Q4.28 post-EQ tap */
        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _bq_fx_cascade_N;
        #if DSP4_BLOCK_KERNELS
        .extern _bq_fx_cascade_blk;
        #endif
        .extern _bq_fx_convert_N;
        .global _{nid}_process;
        _{nid}_process:
        {blk_eq_body}

            /* new coefficients staged? */
            r4 = dm(_eq_swap_pending_{nid});
            r4 = pass r4;
            if ne call _eq_start_xfade_{nid};

            /* crossfading? (float 0.0 is all-zero bits) */
            r4 = dm(_eq_xfade_step_{nid});
            r4 = pass r4;
            if ne jump (pc, .eq_xfade_{nid});

            /* ===== steady state: active instance only ===== */
            r0 = dm(_buf_{inp});
            r4 = dm(_eq_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .eq_ss_b_{nid});
            i0 = _eq_coeffs_A_{nid};
            i1 = _eq_state_A_{nid};
            jump (pc, .eq_ss_go_{nid});
        .eq_ss_b_{nid}:
            i0 = _eq_coeffs_B_{nid};
            i1 = _eq_state_B_{nid};
        .eq_ss_go_{nid}:
            r4 = {bands};
            call _bq_fx_cascade_N;
            dm(_tap_post_eq_{nid}) = r0;
            dm(_buf_{nid}) = r0;
            rts;

            /* ===== crossfade: run both, blend fixed ===== */
        .eq_xfade_{nid}:
            r0 = dm(_buf_{inp});
            r13 = r0;                     /* input (r13-r15 preserved by lib) */
            i0 = _eq_coeffs_A_{nid};
            i1 = _eq_state_A_{nid};
            r4 = {bands};
            call _bq_fx_cascade_N;
            r14 = r0;                     /* ya */
            r0 = r13;
            i0 = _eq_coeffs_B_{nid};
            i1 = _eq_state_B_{nid};
            r4 = {bands};
            call _bq_fx_cascade_N;        /* r0 = yb */

            /* orient: out = old + alpha*(new - old); dormant is new */
            r4 = dm(_eq_active_{nid});
            r4 = pass r4;
            if eq jump (pc, .eq_bl_{nid});     /* active A -> new is B (r0) */
            r5 = r14;                      /* new = ya */
            r14 = r0;                      /* old = yb */
            r0 = r5;
        .eq_bl_{nid}:
            /* alpha_q31 = fix(alpha * 2^31); blend in MRF */
            f4 = dm(_eq_xfade_alpha_{nid});
            r5 = 0x4F000000;               /* 2^31 as float */
            f5 = r5;
            f4 = f4 * f5;
            r4 = fix f4;
            r5 = r0 - r14;                 /* new - old */
            mrf = r5 * r4 (ssi);
            r5 = 0x40000000;               /* 2^30 rounding half */
            r12 = 1;
            mrf = mrf + r5 * r12 (ssi);
            r5 = mr0f;
            r12 = mr1f;
            r5 = lshift r5 by -31;
            r12 = lshift r12 by 1;
            r5 = r5 or r12;
            r0 = r14 + r5;                 /* blended output */
            dm(_tap_post_eq_{nid}) = r0;
            dm(_buf_{nid}) = r0;

            /* advance alpha (float control) */
            f4 = dm(_eq_xfade_alpha_{nid});
            f5 = dm(_eq_xfade_step_{nid});
            f4 = f4 + f5;
            dm(_eq_xfade_alpha_{nid}) = f4;
            r5 = 0x3F800000;               /* 1.0f */
            f5 = r5;
            comp(f4, f5);
            if lt rts;
            /* crossfade done: dormant becomes active */
            r4 = dm(_eq_active_{nid});
            r5 = 1;
            r4 = r4 xor r5;
            dm(_eq_active_{nid}) = r4;
            r4 = 0;
            dm(_eq_xfade_step_{nid}) = r4;
            dm(_eq_xfade_alpha_{nid}) = r4;
            rts;

            /* ===== stage new coeffs into the dormant instance ===== */
        _eq_start_xfade_{nid}:
            r4 = 0;
            dm(_eq_swap_pending_{nid}) = r4;
            i0 = _eq_coeffs_next_{nid};    /* float staged */
            r4 = dm(_eq_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .eq_st_a_{nid});
            i1 = _eq_coeffs_B_{nid};       /* dormant = B */
            i2 = _eq_state_B_{nid};
            jump (pc, .eq_st_go_{nid});
        .eq_st_a_{nid}:
            i1 = _eq_coeffs_A_{nid};
            i2 = _eq_state_A_{nid};
        .eq_st_go_{nid}:
            r4 = {bands};
            call _bq_fx_convert_N;
            /* zero dormant state ({n6} words) */
            r4 = 0;
            r5 = {n6};
            lcntr = r5, do .eq_zst_{nid} until lce;
        .eq_zst_{nid}:
                dm(i2, 1) = r4;
            /* start ramp: step = 1/XFADE_SAMPLES (float control) */
            f0 = {XFADE_STEP};
            dm(_eq_xfade_step_{nid}) = f0;
            r4 = 0;
            dm(_eq_xfade_alpha_{nid}) = r4;
            rts;
        _{nid}_process.end:
    """)



def _fx_bypass5(stages):
    """Q4.28 offset-form identity coefficient list for N stages."""
    return ', '.join(
        ['0x10000000, 0x20000000, 0xF0000000, 0x20000000, 0x10000000'] * stages)


def _fx_blend_asm(pfx, nid):
    """Fixed blend: r0 = old(r7) + rns((new(r0)-old)*alpha_q31, 31);
    advances alpha and finishes the crossfade. Emitted inside a node."""
    return f"""\
            /* alpha_q31 = fix(alpha * 2^31); blend in MRF */
            f4 = dm(_{pfx}_xfade_alpha_{nid});
            r5 = 0x4F000000;               /* 2^31 as float */
            f5 = r5;
            f4 = f4 * f5;
            r4 = fix f4;
            r5 = r0 - r14;                 /* new - old */
            mrf = r5 * r4 (ssi);
            r5 = 0x40000000;               /* 2^30 rounding half */
            r12 = 1;
            mrf = mrf + r5 * r12 (ssi);
            r5 = mr0f;
            r12 = mr1f;
            r5 = lshift r5 by -31;
            r12 = lshift r12 by 1;
            r5 = r5 or r12;
            r0 = r14 + r5;                 /* blended output */"""


def _fx_cascade_node(node, pfx, stages, extra_dm='', extra_store=''):
    """Fixed-point single-cascade crossfade node body (EQ/GEQ/AFB idiom).

    Mirrors the float dual-instance contract exactly: float RBJ staging
    from SPI (wire unchanged), _bq_fx_convert_N at swap time, Q4.28
    offset coefficients, 6-word/stage state, fixed sample blend with
    float control-plane alpha.
    """
    n5 = stages * 5
    n6 = stages * 6
    rc = ramp_comment(node['ramp_profile'])
    bypass = _fx_bypass5(stages)
    nid = node['id']
    inp = node['inputs_str']
    return dedent(f"""\
        {rc}

        /* {node['type']} (FIXED Q4.28, D5): {stages}-stage cascade, dual-instance crossfade */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */
        /* Normative model: tools/dsp/fixed_ref.py::biquad (offset form). */

        .section/dm seg_dmda;
{extra_dm}
        .var _{pfx}_coeffs_A_{nid}[{n5}] = {bypass};
        .var _{pfx}_state_A_{nid}[{n6}];
        .var _{pfx}_coeffs_B_{nid}[{n5}] = {bypass};
        .var _{pfx}_state_B_{nid}[{n6}];

        /* SPI staging (FLOAT RBJ words — wire format unchanged) */
        .var _{pfx}_coeffs_next_{nid}[{n5}];
        .var _{pfx}_swap_pending_{nid} = 0;

        .var _{pfx}_active_{nid} = 0;
        .var _{pfx}_xfade_alpha_{nid} = 0.0;
        .var _{pfx}_xfade_step_{nid} = 0.0;

{extra_store and '        .var _tap_post_eq_' + nid + ';'}
        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _bq_fx_cascade_N;
        .extern _bq_fx_convert_N;
        .global _{nid}_process;
        _{nid}_process:

            r4 = dm(_{pfx}_swap_pending_{nid});
            r4 = pass r4;
            if ne call _{pfx}_start_xfade_{nid};

            r4 = dm(_{pfx}_xfade_step_{nid});
            r4 = pass r4;
            if ne jump (pc, .{pfx}_xfade_{nid});

            /* ===== steady state ===== */
            r0 = dm(_buf_{inp});
            r4 = dm(_{pfx}_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .{pfx}_ss_b_{nid});
            i0 = _{pfx}_coeffs_A_{nid};
            i1 = _{pfx}_state_A_{nid};
            jump (pc, .{pfx}_ss_go_{nid});
        .{pfx}_ss_b_{nid}:
            i0 = _{pfx}_coeffs_B_{nid};
            i1 = _{pfx}_state_B_{nid};
        .{pfx}_ss_go_{nid}:
            r4 = {stages};
            call _bq_fx_cascade_N;
{extra_store}
            dm(_buf_{nid}) = r0;
            rts;

            /* ===== crossfade: run both, blend fixed ===== */
        .{pfx}_xfade_{nid}:
            r0 = dm(_buf_{inp});
            r13 = r0;                     /* input (r13-r15 preserved by lib) */
            i0 = _{pfx}_coeffs_A_{nid};
            i1 = _{pfx}_state_A_{nid};
            r4 = {stages};
            call _bq_fx_cascade_N;
            r14 = r0;                     /* ya */
            r0 = r13;
            i0 = _{pfx}_coeffs_B_{nid};
            i1 = _{pfx}_state_B_{nid};
            r4 = {stages};
            call _bq_fx_cascade_N;        /* r0 = yb */

            r4 = dm(_{pfx}_active_{nid});
            r4 = pass r4;
            if eq jump (pc, .{pfx}_bl_{nid});
            r5 = r14;                     /* active B: new is A */
            r14 = r0;
            r0 = r5;
        .{pfx}_bl_{nid}:
{_fx_blend_asm(pfx, nid)}
{extra_store}
            dm(_buf_{nid}) = r0;

            /* advance alpha (float control) */
            f4 = dm(_{pfx}_xfade_alpha_{nid});
            f5 = dm(_{pfx}_xfade_step_{nid});
            f4 = f4 + f5;
            dm(_{pfx}_xfade_alpha_{nid}) = f4;
            r5 = 0x3F800000;
            f5 = r5;
            comp(f4, f5);
            if lt rts;
            r4 = dm(_{pfx}_active_{nid});
            r5 = 1;
            r4 = r4 xor r5;
            dm(_{pfx}_active_{nid}) = r4;
            r4 = 0;
            dm(_{pfx}_xfade_step_{nid}) = r4;
            dm(_{pfx}_xfade_alpha_{nid}) = r4;
            rts;

            /* ===== stage new coeffs into dormant ===== */
        _{pfx}_start_xfade_{nid}:
            r4 = 0;
            dm(_{pfx}_swap_pending_{nid}) = r4;
            i0 = _{pfx}_coeffs_next_{nid};
            r4 = dm(_{pfx}_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .{pfx}_st_a_{nid});
            i1 = _{pfx}_coeffs_B_{nid};
            i2 = _{pfx}_state_B_{nid};
            jump (pc, .{pfx}_st_go_{nid});
        .{pfx}_st_a_{nid}:
            i1 = _{pfx}_coeffs_A_{nid};
            i2 = _{pfx}_state_A_{nid};
        .{pfx}_st_go_{nid}:
            r4 = {stages};
            call _bq_fx_convert_N;
            r4 = 0;
            r5 = {n6};
            lcntr = r5, do .{pfx}_zst_{nid} until lce;
        .{pfx}_zst_{nid}:
                dm(i2, 1) = r4;
            f0 = {XFADE_STEP};
            dm(_{pfx}_xfade_step_{nid}) = f0;
            r4 = 0;
            dm(_{pfx}_xfade_alpha_{nid}) = r4;
            rts;
        _{nid}_process.end:
    """)


def gen_geq_fixed(node):
    bands = int(node['params'].get('bands', '28'))
    nid = node['id']
    extra = f"        .var _geq_gains_{nid}[{bands}];              /* per-band gain (display) */\n"
    return _fx_cascade_node(node, 'geq', bands, extra_dm=extra)


def gen_anti_fb_fixed(node):
    notches = int(node['params'].get('notch_count', '6'))
    nid = node['id']
    extra = dedent(f"""\
        .var _afb_on_{nid} = 0;
        .var _afb_ctrl_on_{nid} = 0;
        .var _afb_notch_freq_{nid}[{notches}];
        .var _afb_notch_gain_{nid}[{notches}];
        .var _afb_notch_q_{nid}[{notches}];
""")
    extra = '\n'.join('        ' + l if l and not l.startswith('        ') else l
                       for l in extra.split('\n'))
    return _fx_cascade_node(node, 'afb', notches, extra_dm=extra)




def gen_hpf_lpf_fixed(node):
    # Per-block wrapper (DSP4_BLOCK_KERNELS). Emitted AHEAD of the
    # per-sample body, which is left byte-for-byte as it was: without the
    # flag _{nid}_process falls straight through into it, so the default
    # image cannot move.
    #
    # _bq_fx_cascade_blk was proved bit-exact against _bq_fx_cascade_N on
    # the part (DSP4_BQ_SELFTEST, 0 of 64 samples differing, two stages
    # with DIFFERENT coefficients, across a block boundary), so what is
    # left to get right is exactly this wrapper.
    #
    # Crossfades are handed to the per-sample path a sample at a time.
    # That is the reference implementation itself, so the alpha
    # bookkeeping -- and a crossfade COMPLETING mid-block, which flips the
    # active instance and must switch the remaining samples to steady
    # state -- are right by construction rather than by re-derivation. A
    # crossfade lasts 576 samples and is a transient, so its cost does not
    # matter.
    import re as _re
    _pool = bool(_re.match(r'^C\d+_FILT_\d+$', node['id']))
    if _pool:
        _nid = node['id']
        _inp = node['inputs_str']
        # The fused form calls the cascade once with r4 = 2, which walks
        # hpf then lpf as consecutive 5-word coefficient sets. That is only
        # valid while the two .var declarations stay adjacent in memory --
        # INPUT_SECTION_ALIGN(4) in the LDF could insert a gap. Verified in
        # the map at exactly 5 words apart, but a layout change would break
        # it as WRONG COEFFICIENTS rather than a link error, which is the
        # same shape as the b1 aliasing bug that shipped for months. The
        # emitted order below is what guarantees it; keep them together.
        blk_filt_body = _FILT_BLK_BODY.format(nid=_nid, inp=_inp)
    else:
        # Not a strip FILT: no pool slot, so there is no block form.
        blk_filt_body = ''

    """Fixed HPF+LPF (D5): two 1-stage offset-form biquads in series,
    dual-instance crossfade, independent float HPF/LPF staging (wire
    unchanged). On swap: copy active FIXED coeffs to dormant as the
    baseline, overwrite pending filter(s) via _bq_fx_convert_N."""
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    byp = '0x10000000, 0x20000000, 0xF0000000, 0x20000000, 0x10000000'
    fbyp = '1.0, 0.0, 0.0, 0.0, 0.0'
    return dedent(f"""\
        {rc}

        /* HPF_LPF (FIXED Q4.28, D5) — dual-instance crossfade */
        /* HPF: {p.get('hpf_freq','80')} Hz slope {p.get('hpf_slope','18')} | LPF: {p.get('lpf_freq','20000')} Hz */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        #include "blk_pool.h"

        .section/dm seg_dmda;

        .var _filt_hpf_A_{nid}[5] = {byp};
        .var _filt_lpf_A_{nid}[5] = {byp};
        .var _filt_state_A_{nid}[12];
        .var _filt_hpf_B_{nid}[5] = {byp};
        .var _filt_lpf_B_{nid}[5] = {byp};
        .var _filt_state_B_{nid}[12];

        /* float staging (wire unchanged) */
        .var _hpf_coeffs_next_{nid}[5] = {fbyp};
        .var _hpf_swap_pending_{nid} = 0;
        .var _lpf_coeffs_next_{nid}[5] = {fbyp};
        .var _lpf_swap_pending_{nid} = 0;

        .var _filt_active_{nid} = 0;
        .var _filt_xfade_alpha_{nid} = 0.0;
        .var _filt_xfade_step_{nid} = 0.0;

        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _bq_fx_cascade_N;
        .extern _bq_fx_convert_N;
        #if DSP4_BLOCK_KERNELS
        .extern _bq_fx_cascade_blk;
        #endif
        .global _{nid}_process;
        _{nid}_process:
        {blk_filt_body}

            r4 = dm(_hpf_swap_pending_{nid});
            r5 = dm(_lpf_swap_pending_{nid});
            r4 = r4 or r5;
            r4 = pass r4;
            if ne call _filt_start_xfade_{nid};

            r4 = dm(_filt_xfade_step_{nid});
            r4 = pass r4;
            if ne jump (pc, .filt_xfade_{nid});

            /* ===== steady state ===== */
            r0 = dm(_buf_{inp});
            r4 = dm(_filt_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .filt_ss_b_{nid});
            i0 = _filt_hpf_A_{nid};
            i1 = _filt_state_A_{nid};
            r4 = 1;
            call _bq_fx_cascade_N;
            i0 = _filt_lpf_A_{nid};
            r4 = 1;
            call _bq_fx_cascade_N;      /* i1 continued to LPF state */
            dm(_buf_{nid}) = r0;
            rts;
        .filt_ss_b_{nid}:
            i0 = _filt_hpf_B_{nid};
            i1 = _filt_state_B_{nid};
            r4 = 1;
            call _bq_fx_cascade_N;
            i0 = _filt_lpf_B_{nid};
            r4 = 1;
            call _bq_fx_cascade_N;
            dm(_buf_{nid}) = r0;
            rts;

            /* ===== crossfade ===== */
        .filt_xfade_{nid}:
            r0 = dm(_buf_{inp});
            r13 = r0;
            i0 = _filt_hpf_A_{nid};
            i1 = _filt_state_A_{nid};
            r4 = 1;
            call _bq_fx_cascade_N;
            i0 = _filt_lpf_A_{nid};
            r4 = 1;
            call _bq_fx_cascade_N;
            r14 = r0;                     /* ya */
            r0 = r13;
            i0 = _filt_hpf_B_{nid};
            i1 = _filt_state_B_{nid};
            r4 = 1;
            call _bq_fx_cascade_N;
            i0 = _filt_lpf_B_{nid};
            r4 = 1;
            call _bq_fx_cascade_N;        /* r0 = yb */

            r4 = dm(_filt_active_{nid});
            r4 = pass r4;
            if eq jump (pc, .filt_bl_{nid});
            r5 = r14;
            r14 = r0;
            r0 = r5;
        .filt_bl_{nid}:
            f4 = dm(_filt_xfade_alpha_{nid});
            r5 = 0x4F000000;
            f5 = r5;
            f4 = f4 * f5;
            r4 = fix f4;
            r5 = r0 - r14;
            mrf = r5 * r4 (ssi);
            r5 = 0x40000000;
            r12 = 1;
            mrf = mrf + r5 * r12 (ssi);
            r5 = mr0f;
            r12 = mr1f;
            r5 = lshift r5 by -31;
            r12 = lshift r12 by 1;
            r5 = r5 or r12;
            r0 = r14 + r5;
            dm(_buf_{nid}) = r0;

            f4 = dm(_filt_xfade_alpha_{nid});
            f5 = dm(_filt_xfade_step_{nid});
            f4 = f4 + f5;
            dm(_filt_xfade_alpha_{nid}) = f4;
            r5 = 0x3F800000;
            f5 = r5;
            comp(f4, f5);
            if lt rts;
            r4 = dm(_filt_active_{nid});
            r5 = 1;
            r4 = r4 xor r5;
            dm(_filt_active_{nid}) = r4;
            r4 = 0;
            dm(_filt_xfade_step_{nid}) = r4;
            dm(_filt_xfade_alpha_{nid}) = r4;
            rts;

            /* ===== stage into dormant ===== */
        _filt_start_xfade_{nid}:
            /* dormant pointers (i1 = coeff base, i2 = state base) and
             * active coeff base (i0) */
            r4 = dm(_filt_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .filt_st_a_{nid});
            i0 = _filt_hpf_A_{nid};       /* active = A (hpf+lpf adjacent) */
            i1 = _filt_hpf_B_{nid};
            i2 = _filt_state_B_{nid};
            jump (pc, .filt_st_go_{nid});
        .filt_st_a_{nid}:
            i0 = _filt_hpf_B_{nid};
            i1 = _filt_hpf_A_{nid};
            i2 = _filt_state_A_{nid};
        .filt_st_go_{nid}:
            /* baseline: copy active fixed hpf[5] to dormant hpf */
            r5 = 5;
            lcntr = r5, do .filt_cph_{nid} until lce;
                r4 = dm(i0, 1);
        .filt_cph_{nid}:
                dm(i1, 1) = r4;
            /* i0/i1 now at the lpf blocks only if hpf/lpf are adjacent —
             * they are separate vars, so reload explicitly */
            r4 = dm(_filt_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .filt_st2a_{nid});
            i0 = _filt_lpf_A_{nid};
            i1 = _filt_lpf_B_{nid};
            jump (pc, .filt_st2go_{nid});
        .filt_st2a_{nid}:
            i0 = _filt_lpf_B_{nid};
            i1 = _filt_lpf_A_{nid};
        .filt_st2go_{nid}:
            r5 = 5;
            lcntr = r5, do .filt_cpl_{nid} until lce;
                r4 = dm(i0, 1);
        .filt_cpl_{nid}:
                dm(i1, 1) = r4;

            /* overwrite pending filter(s) from float staging */
            r4 = dm(_hpf_swap_pending_{nid});
            r4 = pass r4;
            if eq jump (pc, .filt_nohpf_{nid});
            r4 = 0;
            dm(_hpf_swap_pending_{nid}) = r4;
            i0 = _hpf_coeffs_next_{nid};
            r4 = dm(_filt_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .filt_cvha_{nid});
            i1 = _filt_hpf_B_{nid};
            jump (pc, .filt_cvhgo_{nid});
        .filt_cvha_{nid}:
            i1 = _filt_hpf_A_{nid};
        .filt_cvhgo_{nid}:
            r4 = 1;
            call _bq_fx_convert_N;
        .filt_nohpf_{nid}:
            r4 = dm(_lpf_swap_pending_{nid});
            r4 = pass r4;
            if eq jump (pc, .filt_nolpf_{nid});
            r4 = 0;
            dm(_lpf_swap_pending_{nid}) = r4;
            i0 = _lpf_coeffs_next_{nid};
            r4 = dm(_filt_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .filt_cvla_{nid});
            i1 = _filt_lpf_B_{nid};
            jump (pc, .filt_cvlgo_{nid});
        .filt_cvla_{nid}:
            i1 = _filt_lpf_A_{nid};
        .filt_cvlgo_{nid}:
            r4 = 1;
            call _bq_fx_convert_N;
        .filt_nolpf_{nid}:

            /* zero dormant state + start ramp */
            r4 = dm(_filt_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .filt_zsa_{nid});
            i2 = _filt_state_B_{nid};
            jump (pc, .filt_zsgo_{nid});
        .filt_zsa_{nid}:
            i2 = _filt_state_A_{nid};
        .filt_zsgo_{nid}:
            r4 = 0;
            r5 = 12;
            lcntr = r5, do .filt_zst_{nid} until lce;
        .filt_zst_{nid}:
                dm(i2, 1) = r4;
            f0 = {XFADE_STEP};
            dm(_filt_xfade_step_{nid}) = f0;
            r4 = 0;
            dm(_filt_xfade_alpha_{nid}) = r4;
            rts;
        _{nid}_process.end:
    """)


def gen_crossover_fixed(node):
    """Fixed CROSSOVER (D5): LP/HP 2-stage paths, dual-instance
    crossfade blending BOTH outputs; staging [LP10+HP10] float."""
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    byp10 = ('0x10000000, 0x20000000, 0xF0000000, 0x20000000, 0x10000000, '
             '0x10000000, 0x20000000, 0xF0000000, 0x20000000, 0x10000000')
    fbyp20 = ', '.join(['1.0, 0.0, 0.0, 0.0, 0.0'] * 4)
    return dedent(f"""\
        {rc}

        /* CROSSOVER (FIXED Q4.28, D5): LP/HP split, dual-instance crossfade */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} freq={p.get('freq','120')} slope={p.get('slope','24')} */

        .section/dm seg_dmda;

        .var _xover_lp_A_{nid}[10] = {byp10};
        .var _xover_hp_A_{nid}[10] = {byp10};
        .var _xover_lp_state_A_{nid}[12];
        .var _xover_hp_state_A_{nid}[12];
        .var _xover_lp_B_{nid}[10] = {byp10};
        .var _xover_hp_B_{nid}[10] = {byp10};
        .var _xover_lp_state_B_{nid}[12];
        .var _xover_hp_state_B_{nid}[12];

        /* float staging: [LP 2 stages, HP 2 stages] */
        .var _xover_coeffs_next_{nid}[20] = {fbyp20};
        .var _xover_swap_pending_{nid} = 0;

        .var _xover_active_{nid} = 0;
        .var _xover_xfade_alpha_{nid} = 0.0;
        .var _xover_xfade_step_{nid} = 0.0;

        .var _buf_lp_{nid};
        .var _buf_{nid};
        .var _buf_hp_{nid};

        .section/pm seg_pmco;
        .extern _bq_fx_cascade_N;
        .extern _bq_fx_convert_N;
        .global _{nid}_process;
        _{nid}_process:

            r4 = dm(_xover_swap_pending_{nid});
            r4 = pass r4;
            if ne call _xover_start_xfade_{nid};

            r4 = dm(_xover_xfade_step_{nid});
            r4 = pass r4;
            if ne jump (pc, .xo_xfade_{nid});

            /* ===== steady state ===== */
            r0 = dm(_buf_{inp});
            r13 = r0;
            r4 = dm(_xover_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .xo_ss_b_{nid});
            i0 = _xover_lp_A_{nid};
            i1 = _xover_lp_state_A_{nid};
            r4 = 2;
            call _bq_fx_cascade_N;
            dm(_buf_lp_{nid}) = r0;
            r0 = r13;
            i0 = _xover_hp_A_{nid};
            i1 = _xover_hp_state_A_{nid};
            r4 = 2;
            call _bq_fx_cascade_N;
            dm(_buf_hp_{nid}) = r0;
            dm(_buf_{nid}) = r0;
            rts;
        .xo_ss_b_{nid}:
            i0 = _xover_lp_B_{nid};
            i1 = _xover_lp_state_B_{nid};
            r4 = 2;
            call _bq_fx_cascade_N;
            dm(_buf_lp_{nid}) = r0;
            r0 = r13;
            i0 = _xover_hp_B_{nid};
            i1 = _xover_hp_state_B_{nid};
            r4 = 2;
            call _bq_fx_cascade_N;
            dm(_buf_hp_{nid}) = r0;
            dm(_buf_{nid}) = r0;
            rts;

            /* ===== crossfade: 4 paths, blend LP then HP ===== */
        .xo_xfade_{nid}:
            r0 = dm(_buf_{inp});
            r13 = r0;
            /* LP: A then B */
            i0 = _xover_lp_A_{nid};
            i1 = _xover_lp_state_A_{nid};
            r4 = 2;
            call _bq_fx_cascade_N;
            r14 = r0;                     /* lp_a */
            r0 = r13;
            i0 = _xover_lp_B_{nid};
            i1 = _xover_lp_state_B_{nid};
            r4 = 2;
            call _bq_fx_cascade_N;        /* r0 = lp_b */
            r4 = dm(_xover_active_{nid});
            r4 = pass r4;
            if eq jump (pc, .xo_bl_lp_{nid});
            r5 = r14;
            r14 = r0;
            r0 = r5;
        .xo_bl_lp_{nid}:
            f4 = dm(_xover_xfade_alpha_{nid});
            r5 = 0x4F000000;
            f5 = r5;
            f4 = f4 * f5;
            r4 = fix f4;
            r5 = r0 - r14;
            mrf = r5 * r4 (ssi);
            r5 = 0x40000000;
            r12 = 1;
            mrf = mrf + r5 * r12 (ssi);
            r5 = mr0f;
            r12 = mr1f;
            r5 = lshift r5 by -31;
            r12 = lshift r12 by 1;
            r5 = r5 or r12;
            r0 = r14 + r5;
            dm(_buf_lp_{nid}) = r0;

            /* HP: A then B */
            r0 = r13;
            i0 = _xover_hp_A_{nid};
            i1 = _xover_hp_state_A_{nid};
            r4 = 2;
            call _bq_fx_cascade_N;
            r14 = r0;
            r0 = r13;
            i0 = _xover_hp_B_{nid};
            i1 = _xover_hp_state_B_{nid};
            r4 = 2;
            call _bq_fx_cascade_N;
            r4 = dm(_xover_active_{nid});
            r4 = pass r4;
            if eq jump (pc, .xo_bl_hp_{nid});
            r5 = r14;
            r14 = r0;
            r0 = r5;
        .xo_bl_hp_{nid}:
            f4 = dm(_xover_xfade_alpha_{nid});
            r5 = 0x4F000000;
            f5 = r5;
            f4 = f4 * f5;
            r4 = fix f4;
            r5 = r0 - r14;
            mrf = r5 * r4 (ssi);
            r5 = 0x40000000;
            r12 = 1;
            mrf = mrf + r5 * r12 (ssi);
            r5 = mr0f;
            r12 = mr1f;
            r5 = lshift r5 by -31;
            r12 = lshift r12 by 1;
            r5 = r5 or r12;
            r0 = r14 + r5;
            dm(_buf_hp_{nid}) = r0;
            dm(_buf_{nid}) = r0;

            f4 = dm(_xover_xfade_alpha_{nid});
            f5 = dm(_xover_xfade_step_{nid});
            f4 = f4 + f5;
            dm(_xover_xfade_alpha_{nid}) = f4;
            r5 = 0x3F800000;
            f5 = r5;
            comp(f4, f5);
            if lt rts;
            r4 = dm(_xover_active_{nid});
            r5 = 1;
            r4 = r4 xor r5;
            dm(_xover_active_{nid}) = r4;
            r4 = 0;
            dm(_xover_xfade_step_{nid}) = r4;
            dm(_xover_xfade_alpha_{nid}) = r4;
            rts;

            /* ===== stage into dormant ===== */
        _xover_start_xfade_{nid}:
            r4 = 0;
            dm(_xover_swap_pending_{nid}) = r4;
            i0 = _xover_coeffs_next_{nid};
            r4 = dm(_xover_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .xo_st_a_{nid});
            i1 = _xover_lp_B_{nid};
            jump (pc, .xo_st_go_{nid});
        .xo_st_a_{nid}:
            i1 = _xover_lp_A_{nid};
        .xo_st_go_{nid}:
            r4 = 2;
            call _bq_fx_convert_N;        /* LP stages; i0 -> HP staging */
            r4 = dm(_xover_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .xo_st2a_{nid});
            i1 = _xover_hp_B_{nid};
            jump (pc, .xo_st2go_{nid});
        .xo_st2a_{nid}:
            i1 = _xover_hp_A_{nid};
        .xo_st2go_{nid}:
            r4 = 2;
            call _bq_fx_convert_N;
            /* zero dormant states (lp 12 + hp 12) */
            r4 = dm(_xover_active_{nid});
            r4 = pass r4;
            if ne jump (pc, .xo_zsa_{nid});
            i2 = _xover_lp_state_B_{nid};
            i3 = _xover_hp_state_B_{nid};
            jump (pc, .xo_zsgo_{nid});
        .xo_zsa_{nid}:
            i2 = _xover_lp_state_A_{nid};
            i3 = _xover_hp_state_A_{nid};
        .xo_zsgo_{nid}:
            r4 = 0;
            r5 = 12;
            lcntr = r5, do .xo_zst1_{nid} until lce;
        .xo_zst1_{nid}:
                dm(i2, 1) = r4;
            r5 = 12;
            lcntr = r5, do .xo_zst2_{nid} until lce;
        .xo_zst2_{nid}:
                dm(i3, 1) = r4;
            f0 = {XFADE_STEP};
            dm(_xover_xfade_step_{nid}) = f0;
            r4 = 0;
            dm(_xover_xfade_alpha_{nid}) = r4;
            rts;
        _{nid}_process.end:
    """)



def gen_gain_fixed(node):
    """Fixed GAIN (D5): float control plane unchanged (ramp quad stays
    float, spec revision 2026-07-31); the coefficient converts to Q4.28
    once per block; the sample path is MRF MAC + rns + saturate."""
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    return dedent(f"""\
        {rc}

        /* GAIN (FIXED Q4.28, D5) — float control, fixed sample path */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        #include "blk_pool.h"

        .section/dm seg_dmda;
        .var _gain_coeff_{nid} = 1.0;            /* FLOAT (ramped) */
        .var _gain_target_{nid} = 1.0;
        .var _gain_step_{nid} = 0.0;
        .var _gain_frames_{nid} = 0;
        .var _gain_q_{nid} = 0x10000000;          /* Q4.28 shadow */
        .var _mute_{nid} = {p.get('mute', '0')};
        .var _polarity_{nid} = {p.get('polarity', '0')};
        .var _tap_post_trim_{nid};
        /* Block output and tap live in the SHARED pool; these scalars are
         * kept for linkage with unconverted consumers and carry the last
         * sample of the block. */
        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _sample_idx;
        .extern _mrf_rns28;
        .global _{nid}_process;
        _{nid}_process:
        #if !DSP4_BLOCK_KERNELS
            /* per-sample path: the block-rate work has to be guarded,
             * and that guard is re-evaluated 32 times per block. */
            r4 = dm(_sample_idx);
            r1 = 0;
            comp(r4, r1);
            if ne jump (pc, .apply_{nid});
        #endif

            r4 = dm(_gain_frames_{nid});
            r1 = 0;
            comp(r4, r1);
            if le jump (pc, .snap_{nid});
            /* Consume a BLOCK's worth of frames and apply a BLOCK's
             * worth of step. spi_handler scales every profile frame count
             * by 32 (BLOCK_SIZE), which is right for the ramps that
             * decrement once per SAMPLE. This one decrements once per
             * BLOCK, so taking 1 per block ran it 32x long: measured
             * 2026-08-23, a GainSafe down-ramp took 960 ms against the
             * 30 ms its own cell table specifies, and a GainFast fader
             * move took 85 ms instead of 3 ms. 32.0f is exact in binary,
             * so scaling the step loses nothing. */
            r5 = 32;
            r4 = r4 - r5;
            dm(_gain_frames_{nid}) = r4;
            f1 = dm(_gain_coeff_{nid});
            f2 = dm(_gain_step_{nid});
            r5 = 0x42000000;                  /* 32.0f */
            f5 = r5;
            f2 = f2 * f5;
            f1 = f1 + f2;
            dm(_gain_coeff_{nid}) = f1;
            jump (pc, .cvt_{nid});
        .snap_{nid}:
            f1 = dm(_gain_target_{nid});
            dm(_gain_coeff_{nid}) = f1;
        .cvt_{nid}:
            r2 = 0x4D800000;                      /* 2^28 as float */
            f2 = r2;
            f1 = f1 * f2;
            r1 = fix f1;
            /* CROSSPOINT-COEFFICIENT FOLD (08-25 mandate). Polarity and
             * mute are LINEAR gain terms (-1 and 0), so they belong in the
             * coefficient at CONTROL rate; the sample path is then one MAC
             * that never reads control state. Mute is exactly x*0 in this
             * format. Folding polarity is also what the normative model
             * does -- fixed_ref.gain(x, g) with g negative is
             * sat(rns(x*-g)), whereas the old per-sample form computed
             * -sat(rns(x*|g|)), and those differ by one LSB when the
             * product lands exactly on a rounding tie (rns rounds half
             * toward +inf, which is not symmetric under negation). The
             * folded form is the reference form. */
            r3 = dm(_polarity_{nid});
            r4 = 0;
            comp(r3, r4);
            if ne r1 = -r1;
            r2 = dm(_mute_{nid});
            comp(r2, r4);
            if ne r1 = r4;
            dm(_gain_q_{nid}) = r1;

        #if DSP4_BLOCK_KERNELS
            /* _mrf_rns28 inlined with its constants hoisted. The call/rts
             * and the reload of those constants were most of this node's
             * measured 72.5 cycles/sample. The saturation fix-up is a
             * CONDITIONAL MOVE, not a branch, so the body stays inside a
             * hardware loop. */
            r6 = 0x08000000;                  /* 2^27, the rounding half */
            r7 = 1;
            r10 = 0x7FFFFFFF;
            l0 = 0;
            l1 = 0;
            l4 = 0;
            i0 = BLK_CHAIN_A;
            i1 = BLK_CHAIN_B;
            /* The post-trim tap the router picks from, as a BLOCK. EQ and
             * DLY already publish theirs (BLK_TAP_EQ, BLK_TAP_PREFDR);
             * this one never was, so a block-form aux send set to pickoff
             * 0 was handed the address of the SCALAR tap and walked 32
             * words off the end of it. */
            i4 = BLK_TAP_TRIM;
            r5 = 32;
            lcntr = r5; do .gk_lp_{nid} until lce;
                r0 = dm(i0, 1);
                mrf = r0 * r1 (ssi);
                mrf = mrf + r6 * r7 (ssi);
                r8 = mr0f;
                r2 = mr1f;
                r8 = lshift r8 by -28;
                r9 = lshift r2 by 4;
                r0 = r8 or r9;
                r8 = ashift r2 by -28;
                r9 = ashift r0 by -31;
                r11 = ashift r2 by -31;
                r11 = r10 xor r11;
                comp(r8, r9);
                if ne r0 = r11;
                dm(i1, 1) = r0;
        .gk_lp_{nid}:
                dm(i4, 1) = r0;           /* post-trim tap block */
            dm(_tap_post_trim_{nid}) = r0;   /* linkage scalars */
            dm(_buf_{nid}) = r0;
            rts;
        #else
        .apply_{nid}:
            /* Pure MAC. Polarity and mute are already inside _gain_q. */
            r0 = dm(_buf_{inp});
            r1 = dm(_gain_q_{nid});
            mrf = r0 * r1 (ssi);
            call _mrf_rns28;                      /* r0 = sat(rns(x*g,28)) */

            dm(_tap_post_trim_{nid}) = r0;
            dm(_buf_{nid}) = r0;
            rts;
        #endif
        _{nid}_process.end:
    """)


def gen_fader_pan_fixed(node):
    """Fixed FADER_PAN (D5): float control (level/pan/dca ramps
    unchanged); block-rate conversion of the composite gains to Q4.28
    shadows (mono, L, R); fixed sample path."""
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    is_ch_fdr = (node['chip'] == '1')
    lr_vars = ''
    if is_ch_fdr:
        lr_vars = (f'        .var _fdr_lq_{nid} = 0;\n'
                   f'        .var _fdr_rq_{nid} = 0;')
    cvt_lr = ''
    apply_lr = ''
    # Bus faders (AUX/GRP/SUB/FX) are mono -- no pan split, so no lq/rq.
    #
    # CROSSPOINT-COEFFICIENT FOLD (08-25 mandate): the pan legs are no
    # longer MULTIPLIED here. _fdr_lq/_fdr_rq are published as the pan-leg
    # coefficients and ROUTING folds them into the main-L/main-R crosspoint
    # coefficients, so the bus feed is one MAC off the post-fader mono
    # instead of fader-multiply -> pan-multiply -> unity MAC. That deletes
    # two of the three round-and-saturate stages this node used to run per
    # sample, and one intermediate rounding with them.
    blk_lr_hoist = ''
    blk_lr_ptr = ''
    blk_lr_body = ''
    if is_ch_fdr:
        cvt_lr = dedent(f"""\
            /* L/R pan gains (linear pan law, matches float node).
             *
             * PAN GAIN ONLY -- do NOT fold `comp` in here. The sample path
             * below multiplies the ALREADY-POST-FADER mono by these, so
             * including comp applied the fader twice and the bus feed came
             * out as x * level^2 * (1-pan). It is invisible at unity, which
             * is how it shipped: bench 2026-08-23 measured the main bus
             * 6.02 dB low at level 0.5 and 12.04 dB low at level 0.25, and
             * exact at level 1.0. The float node this was ported from does
             * `f1 = f14 * f7` with f7 = 1 - pan and no comp -- the squaring
             * was introduced by the fixed-point port, not inherited. */
            r2 = 0x3F800000;
            f2 = r2;
            f5 = dm(_fdr_pan_{nid});
            f6 = f2 - f5;                     /* L gain = 1 - pan */
            r2 = 0x4D800000;
            f7 = r2;
            f6 = f6 * f7;
            r2 = fix f6;
            dm(_fdr_lq_{nid}) = r2;
            f5 = f5 * f7;
            r2 = fix f5;
            dm(_fdr_rq_{nid}) = r2;""")
    return dedent(f"""\
        {rc}

        #include "blk_pool.h"

        /* FADER_PAN (FIXED Q4.28, D5) — float control, fixed sample path */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        .section/dm seg_dmda;
        .var _fdr_level_{nid} = 1.0;
        .var _fdr_level_target_{nid} = 1.0;
        .var _fdr_level_step_{nid} = 0.0;
        .var _fdr_level_frames_{nid} = 0;
        .var _fdr_pan_{nid} = 0.5;
        .var _fdr_pan_target_{nid} = 0.5;
        .var _fdr_pan_step_{nid} = 0.0;
        .var _fdr_pan_frames_{nid} = 0;
        .var _fdr_mute_{nid} = 0;
        .var _fdr_dca_gain_{nid} = 1.0;
        .var _fdr_gq_{nid} = 0x10000000;          /* Q4.28 level*dca */
        .var _tap_post_fader_{nid};
        .var _buf_{nid};
{lr_vars}

        .section/pm seg_pmco;
        .extern _sample_idx;
        .extern _mrf_rns28;
        .global _{nid}_process;
        _{nid}_process:
            /* block-rate: float ramps + shadow conversion */
        #if !DSP4_BLOCK_KERNELS
            r4 = dm(_sample_idx);
            r1 = 0;
            comp(r4, r1);
            if ne jump (pc, .apply_{nid});
        #endif

            /* level ramp */
            r4 = dm(_fdr_level_frames_{nid});
            r1 = 0;
            comp(r4, r1);
            if le jump (pc, .lsnap_{nid});
            /* Consume a BLOCK's worth of frames and apply a BLOCK's
             * worth of step. spi_handler scales every profile frame count
             * by 32 (BLOCK_SIZE), which is right for the ramps that
             * decrement once per SAMPLE. This one decrements once per
             * BLOCK, so taking 1 per block ran it 32x long: measured
             * 2026-08-23, a GainSafe down-ramp took 960 ms against the
             * 30 ms its own cell table specifies, and a GainFast fader
             * move took 85 ms instead of 3 ms. 32.0f is exact in binary,
             * so scaling the step loses nothing. */
            r5 = 32;
            r4 = r4 - r5;
            dm(_fdr_level_frames_{nid}) = r4;
            f1 = dm(_fdr_level_{nid});
            f2 = dm(_fdr_level_step_{nid});
            r5 = 0x42000000;                  /* 32.0f */
            f5 = r5;
            f2 = f2 * f5;
            f1 = f1 + f2;
            dm(_fdr_level_{nid}) = f1;
            jump (pc, .pramp_{nid});
        .lsnap_{nid}:
            f1 = dm(_fdr_level_target_{nid});
            dm(_fdr_level_{nid}) = f1;
        .pramp_{nid}:
            /* pan ramp */
            r4 = dm(_fdr_pan_frames_{nid});
            r1 = 0;
            comp(r4, r1);
            if le jump (pc, .psnap_{nid});
            /* Consume a BLOCK's worth of frames and apply a BLOCK's
             * worth of step. spi_handler scales every profile frame count
             * by 32 (BLOCK_SIZE), which is right for the ramps that
             * decrement once per SAMPLE. This one decrements once per
             * BLOCK, so taking 1 per block ran it 32x long: measured
             * 2026-08-23, a GainSafe down-ramp took 960 ms against the
             * 30 ms its own cell table specifies, and a GainFast fader
             * move took 85 ms instead of 3 ms. 32.0f is exact in binary,
             * so scaling the step loses nothing. */
            r5 = 32;
            r4 = r4 - r5;
            dm(_fdr_pan_frames_{nid}) = r4;
            f1 = dm(_fdr_pan_{nid});
            f2 = dm(_fdr_pan_step_{nid});
            r5 = 0x42000000;                  /* 32.0f */
            f5 = r5;
            f2 = f2 * f5;
            f1 = f1 + f2;
            dm(_fdr_pan_{nid}) = f1;
            jump (pc, .cvt_{nid});
        .psnap_{nid}:
            f1 = dm(_fdr_pan_target_{nid});
            dm(_fdr_pan_{nid}) = f1;
        .cvt_{nid}:
            /* composite = level * dca; Q4.28 shadow(s) */
            f1 = dm(_fdr_level_{nid});
            f2 = dm(_fdr_dca_gain_{nid});
            f1 = f1 * f2;
            r2 = 0x4D800000;
            f2 = r2;
            f3 = f1 * f2;
            r2 = fix f3;
            /* CROSSPOINT-COEFFICIENT FOLD (08-25 mandate): mute is a LINEAR
             * gain term, so it belongs in the coefficient at control rate.
             * x*0 is exactly 0 in this format, so the sample path needs no
             * test -- it is one MAC that never reads control state. */
            r3 = dm(_fdr_mute_{nid});
            r4 = 0;
            comp(r3, r4);
            if ne r2 = r4;
            dm(_fdr_gq_{nid}) = r2;
{cvt_lr}

        #if DSP4_BLOCK_KERNELS
            /* Per-BLOCK kernel. Same shape that gave GAIN its 4x: the
             * coefficient is hoisted and _mrf_rns28 is inlined with its
             * constants held. Mute is already inside _fdr_gq. */
            r1 = dm(_fdr_gq_{nid});
{blk_lr_hoist}            r7 = 0x08000000;                  /* rounding half */
            r12 = 1;
            r10 = 0x7FFFFFFF;
            l0 = 0;
            l1 = 0;
            l2 = 0;
            l3 = 0;
            i0 = BLK_CHAIN_B;                 /* input  */
            i1 = BLK_CHAIN_A;                 /* mono   */
{blk_lr_ptr}            r14 = 32;
        .fdr_lp_{nid}:
            r0 = dm(i0, 1);
            mrf = r0 * r1 (ssi);
            mrf = mrf + r7 * r12 (ssi);
            r8 = mr0f;
            r2 = mr1f;
            r8 = lshift r8 by -28;
            r9 = lshift r2 by 4;
            r0 = r8 or r9;
            r8 = ashift r2 by -28;
            r9 = ashift r0 by -31;
            r11 = ashift r2 by -31;
            r11 = r10 xor r11;
            comp(r8, r9);
            if ne r0 = r11;
            dm(i1, 1) = r0;
            r13 = r0;
{blk_lr_body}            r14 = r14 - 1;
            if gt jump (pc, .fdr_lp_{nid});
            dm(_tap_post_fader_{nid}) = r13;  /* linkage scalars */
            dm(_buf_{nid}) = r13;
            rts;
#else
        .apply_{nid}:
            /* Pure MAC. Mute is already inside _fdr_gq; the pan legs are
             * ROUTING's main-bus crosspoint coefficients. */
            r0 = dm(_buf_{inp});
            r1 = dm(_fdr_gq_{nid});
            mrf = r0 * r1 (ssi);
            call _mrf_rns28;

            dm(_tap_post_fader_{nid}) = r0;
            dm(_buf_{nid}) = r0;
{apply_lr}
            rts;
#endif
        _{nid}_process.end:
    """)


def gen_mix_bus_fixed(node):
    """Fixed MIX_BUS (D5). Chip 1: read the 64-bit bus accumulator with
    ONE rns+saturate (exact summing, fixed_ref.mix_sum). Chip 2:
    unrolled MRF MAC over source buffers with Q4.28 gain shadows
    converted at block rate."""
    p = node['params']
    nid = node['id']
    n_src = len(node['inputs'])
    if node['chip'] == '1':
        bus_suffix = nid.replace('C1_BUS_', '').lower()
        acc_sym = f'_bus_acc_{bus_suffix}'
        return dedent(f"""\
            /* MIX_BUS (FIXED, D5): bus_id={p.get('bus_id','?')} — exact 64-bit acc readout */

            #include "blk_pool.h"

            .section/dm seg_dmda;
            #if DSP4_BLOCK_KERNELS
            .var _buf_{nid}[32];
            #else
            .var _buf_{nid};
            #endif

            .section/pm seg_pmco;
            .extern {acc_sym};
            .extern _acc64_rns28;
            .global _{nid}_process;
            _{nid}_process:
            #if DSP4_BLOCK_KERNELS
                /* One call per BLOCK instead of 32. The accumulator is
                 * already per-sample (64 words = 32 x 2), so this walks it
                 * and rounds each sample in turn. _acc64_rns28 advances i2
                 * by one, so it takes one more modify to step a pair. */
                l2 = 0;
                l3 = 0;
                i2 = {acc_sym};
                i3 = _buf_{nid};
                m0 = 1;
                lcntr = 32, do .mbk_{nid} until lce;
                    call _acc64_rns28;
                    modify(i2, m0);
                .mbk_{nid}: dm(i3, 1) = r0;
                rts;
            #else
                i2 = {acc_sym};
                call _acc64_rns28;
                dm(_buf_{nid}) = r0;
                rts;
            #endif
            _{nid}_process.end:
        """)
    macs = []
    for k, inp in enumerate(node['inputs']):
        macs.append(f'r0 = dm(_buf_{inp});')
        macs.append(f'r1 = dm(_mix_gq_{nid} + {k});')
        macs.append('mrf = mrf + r0 * r1 (ssi);')
    mac_block = '\n                '.join(macs) if macs else 'nop;'
    cvts = []
    for k in range(max(n_src, 1)):
        cvts.append(f'f1 = dm(_mix_gains_{nid} + {k});')
        cvts.append('f1 = f1 * f2;')
        cvts.append('r1 = fix f1;')
        cvts.append(f'dm(_mix_gq_{nid} + {k}) = r1;')
    cvt_block = '\n                '.join(cvts)
    ones = ', '.join(['1.0'] * max(n_src, 1))
    return dedent(f"""\
        /* MIX_BUS (FIXED, D5): bus_id={p.get('bus_id','?')} — {n_src} sources, exact MRF sum */

        .section/dm seg_dmda;
        .var _mix_gains_{nid}[{max(n_src, 1)}] = {ones};   /* FLOAT (host) */
        .var _mix_gq_{nid}[{max(n_src, 1)}];               /* Q4.28 shadow */
        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _sample_idx;
        .extern _mrf_rns28;
        .global _{nid}_process;
        _{nid}_process:
            /* block-rate gain shadow refresh */
        /* The block-rate guard exists ONLY for the per-sample build. Under
         * DSP4_BLOCK_KERNELS the node chain runs ONCE per block with
         * _sample_idx left at 31 by the scatter loop, so a surviving
         * `_sample_idx == 0` test NEVER fires and the parameters below are
         * never converted -- the node then runs on its .var initialisers.
         * Audited 2026-08-27: 132 nodes carried this dead guard. */
        #if !DSP4_BLOCK_KERNELS
            r4 = dm(_sample_idx);
            r1 = 0;
            comp(r4, r1);
            if ne jump (pc, .mix_go_{nid});
        #endif
            r2 = 0x4D800000;
            f2 = r2;
                {cvt_block}
        .mix_go_{nid}:
            r1 = 0;
            mr0f = r1;
            mr1f = r1;
            mr2f = r1;
                {mac_block}
            call _mrf_rns28;
            dm(_buf_{nid}) = r0;
            rts;
        _{nid}_process.end:
    """)


def gen_blk_pool_header():
    """blk_pool.h — slot names for the shared per-strip block buffers."""
    return """\
/* blk_pool.h — shared per-strip block buffers (KERNEL REWRITE) */
/* AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly. */
/*
 * Buffer reuse, not one buffer per node. A strip is a linear chain and the
 * strips run one after another, so the live set at any moment is small and
 * fixed: a ping-pong pair for the chain itself, the fader's L/R split, and
 * the four taps the router picks from. 8 slots x 32 = 256 words serves all
 * 32 strips; one buffer per node would want ~16K words, which is what
 * overflowed DM on 2026-08-24.
 */
#ifndef DSP4_BLK_POOL_H
#define DSP4_BLK_POOL_H

#if DSP4_BLOCK_KERNELS
.extern _blk_pool;
#define BLK(n)           (_blk_pool + (n) * 32)

/* chain ping-pong: IN->A GAIN->B FILT->A EQ->B GATE->A COMP->B TUBE->A
 * DLY->B FDR->A */
#define BLK_CHAIN_A      BLK(0)
#define BLK_CHAIN_B      BLK(1)

/* fader pan split, live until the router has read both */
#define BLK_FDR_L        BLK(2)
#define BLK_FDR_R        BLK(3)

/* taps the router picks from -- these stay live across the whole strip,
 * which is why they get their own slots instead of sharing the pair */
#define BLK_TAP_TRIM     BLK(4)
#define BLK_TAP_EQ       BLK(5)
#define BLK_TAP_PREFDR   BLK(6)
#define BLK_TAP_POSTFDR  BLK(7)

/* Strip-pair park (DSP4_SIMD_STRIPS). Pairing two strips for SIMD needs
 * both strips' blocks live at once, and the pool is reused sequentially --
 * strip N+1's block does not exist while strip N is running. ONE extra
 * slot fixes that: strip N's chain value parks here while strip N+1
 * catches up, then _bq_pair_blk interleaves the two. That is 32 words, not
 * the doubled pool an earlier note claimed was needed. */
#define BLK_PAIR_PARK    BLK(8)
#endif

#endif /* DSP4_BLK_POOL_H */
"""


def gen_bus_accumulators_fixed():
    """Fixed bus_accumulators.asm: 64-bit pairs per bus + clear."""
    names = (['main_l', 'main_r', 'sub']
             + [f'grp_{g:02d}' for g in range(1, 5)]
             + [f'aux_{a:02d}' for a in range(1, 13)]
             + [f'fx_{x:02d}' for x in range(1, 7)])
    out = []
    out.append('/* bus_accumulators.asm — FIXED (D5): 64-bit exact bus accumulators */')
    out.append('/* AUTO-GENERATED by tools/dsp/dsp_codegen.py (--format fixed) — do not edit. */')
    out.append('/* Pairs [lo, hi]; contributions via _acc64_mac; readout _acc64_rns28. */')
    out.append('')
    out.append('.section/dm seg_dmda;')
    out.append('')
    # SHARED per-strip block buffers. Strips run SEQUENTIALLY (the call
    # chain is strip-ordered: IN GAIN FILT EQ GATE COMP TUBE DLY FDR RTG),
    # so a strip's working set is dead the moment its RTG has accumulated
    # into the buses -- every strip reuses the same slots. One pool of 8
    # slots x 32 samples = 256 words serves all 32 strips, against ~16K
    # words if every node kept its own block buffer.
    out.append('#if DSP4_BLOCK_KERNELS')
    out.append('.global _blk_pool;')
    out.append('#if DSP4_SIMD_STRIPS')
    out.append('.var _blk_pool[288];    /* 8 slots + the strip-pair park */')
    out.append('#else')
    out.append('.var _blk_pool[256];')
    out.append('#endif')
    out.append('#endif')
    out.append('')
    # Under per-block kernels every SAMPLE needs its own accumulator, so
    # each bus becomes 32 [lo,hi] pairs. Same total clearing work per
    # block (25 x 64 words once, versus 25 x 2 words thirty-two times).
    # Per-sample accumulators are 25 x 64 = 1600 words against 50, and that
    # does not fit: the IN+GAIN block conversion already left under ~1.5K
    # words of DM headroom on chip 1, and adding these overflowed sec_stak.
    # They go to L2 (seg_delay), which is NO_INIT -- fine, they carry no
    # initialiser and _bus_clear_all zeroes them every block anyway.
    # These stay in L2. Measured 2026-08-24: with the shared pool the
    # conversion sits at 22,472 words of sec_dmda against 20,840 for the
    # default build, and moving the 1,600 words of accumulators back
    # internal takes it to 24,072, which overflows sec_stak. So DM headroom
    # is under ~1,600 words even after pooling. The next thing to reclaim
    # is the 1,472 words of RX slot arrays, which disappear if the IN
    # kernel reads the DMA buffer directly and does the Q1.31->Q4.28 shift
    # itself, removing a whole copy as well.
    # Still L2. Measured 2026-08-24: the RX-slot reclaim took sec_dmda to
    # 21,046 words (default is 20,840), but putting these 1,600 back
    # internal reaches 22,646 and still overflows -- the ceiling sits
    # around 22,500. L2 it is; that makes the RTG cycle figure conservative
    # rather than optimistic.
    out.append('#if DSP4_BLOCK_KERNELS')
    out.append('.section/dm seg_delay;')
    for n in names:
        out.append(f'.global _bus_acc_{n};   .var _bus_acc_{n}[64];')
    out.append('.section/dm seg_dmda;')
    out.append('#else')
    for n in names:
        out.append(f'.global _bus_acc_{n};   .var _bus_acc_{n}[2];')
    out.append('#endif')
    out.append('')
    out.append('.global _bus_acc_grp_ptrs;')
    out.append('.var _bus_acc_grp_ptrs[4] = ' +
               ', '.join(f'_bus_acc_grp_{g:02d}' for g in range(1, 5)) + ';')
    out.append('.global _bus_acc_aux_ptrs;')
    out.append('.var _bus_acc_aux_ptrs[12] = ' +
               ', '.join(f'_bus_acc_aux_{a:02d}' for a in range(1, 13)) + ';')
    out.append('.global _bus_acc_fx_ptrs;')
    out.append('.var _bus_acc_fx_ptrs[6] = ' +
               ', '.join(f'_bus_acc_fx_{x:02d}' for x in range(1, 7)) + ';')
    out.append('.var _bus_acc_all_ptrs[25] = ' + ', '.join(f'_bus_acc_{n}' for n in names) + ';')
    out.append('')
    out.append('.section/pm seg_pmco;')
    out.append('.global _bus_clear_all;')
    out.append('_bus_clear_all:')
    out.append('    i2 = _bus_acc_all_ptrs;')
    out.append('    r0 = 0;')
    out.append('    r1 = 25;')
    out.append('#if DSP4_BLOCK_KERNELS')
    out.append('    lcntr = r1, do .bca_clr until lce;')
    out.append('        r2 = dm(i2, 1);')
    out.append('        i3 = r2;')
    out.append('        r3 = 64;')
    out.append('        lcntr = r3, do .bca_clr_in until lce;')
    out.append('    .bca_clr_in:')
    out.append('            dm(i3, 1) = r0;')
    out.append('    .bca_clr:')
    out.append('        nop;')
    out.append('#else')
    out.append('    lcntr = r1, do .bca_clr until lce;')
    out.append('        r2 = dm(i2, 1);')
    out.append('        i3 = r2;')
    out.append('        dm(i3, 1) = r0;')
    out.append('    .bca_clr:')
    out.append('        dm(i3, 0) = r0;')
    out.append('#endif')
    out.append('    rts;')
    out.append('_bus_clear_all.end:')
    out.append('')
    # Per-block accumulate: one call per CONTRIBUTION per block instead of
    # one per contribution per sample. RTG's measured 601 cycles/sample is
    # almost all gating and call overhead -- with only MAIN enabled by
    # default that is two _acc64_mac calls (~30 cycles) inside 22 gated
    # loop iterations, evaluated 32 times over.
    out.append('#if DSP4_BLOCK_KERNELS')
    out.append('.global _acc64_mac_blk;')
    out.append('/* i0 = source array (32 words), i2 = accumulator (32 [lo,hi]')
    out.append(' * pairs), r1 = gain Q4.28. Exact: no rounding here, one')
    out.append(' * round happens at readout in _acc64_rns28. */')
    out.append('_acc64_mac_blk:')
    out.append('    l0 = 0;')
    out.append('    l2 = 0;')
    out.append('    r5 = 32;')
    out.append('    lcntr = r5, do .amb_lp until lce;')
    out.append('        r0 = dm(i0, 1);')
    out.append('        r2 = dm(i2, 1);            /* lo; i2 -> hi */')
    out.append('        r3 = dm(i2, 0);            /* hi           */')
    out.append('        mr0f = r2;')
    out.append('        mr1f = r3;')
    out.append('        r2 = ashift r3 by -31;')
    out.append('        mr2f = r2;')
    out.append('        mrf = mrf + r0 * r1 (ssi);')
    out.append('        r2 = mr1f;')
    out.append('        dm(i2, -1) = r2;           /* hi; i2 -> lo */')
    out.append('        r2 = mr0f;')
    out.append('    .amb_lp:')
    out.append('        dm(i2, 2) = r2;            /* lo; i2 -> next pair */')
    out.append('    rts;')
    out.append('_acc64_mac_blk.end:')
    out.append('#endif')
    out.append('')
    return '\n'.join(out)



def _fx_send_ramp_asm(nid, kind, count, srcs):
    """Block-rate CONTROL work for one send array: advance the float ramp,
    convert to a Q4.28 crosspoint coefficient with the bus-assign bit
    folded in, and resolve the pickoff enum to a source ADDRESS.

    CROSSPOINT-COEFFICIENT FOLD (08-25 mandate). Everything here is control
    state and it all resolves at control rate, so the accumulate path reads
    coefficients and addresses only. An unassigned send is a coefficient of
    exactly zero -- there is nothing left for the audio path to test.

    srcs = (pickoff 0, 1, 2, default) source expressions for this build.
    """
    s0, s1, s2, sd = srcs
    return f"""\
            l0 = 0;
            i0 = _rtg_{kind}_on_{nid};
            i4 = _rtg_{kind}_send_{nid};
            i5 = _rtg_{kind}_send_step_{nid};
            i6 = _rtg_{kind}_send_frames_{nid};
            i3 = _rtg_{kind}_send_target_{nid};
            i2 = _rtg_{kind}_sq_{nid};
            r5 = {count};
            lcntr = r5, do .{kind}rmp_{nid} until lce;
                r4 = dm(i6, 0);
                r6 = 32;
                comp(r4, r6);
                if lt r6 = r4;                /* n = min(frames, 32) */
                r4 = r4 - r6;
                dm(i6, 1) = r4;
                r4 = pass r6;
                if eq jump (pc, .{kind}snap_{nid});
                f1 = dm(i4, 0);
                f2 = dm(i5, 0);
                f3 = float r6;
                f2 = f2 * f3;                 /* step * n */
                f1 = f1 + f2;
                dm(i4, 0) = f1;
                jump (pc, .{kind}cvt_{nid});
            .{kind}snap_{nid}:
                f1 = dm(i3, 0);               /* snap to target */
                dm(i4, 0) = f1;
            .{kind}cvt_{nid}:
                r4 = 0x4D800000;              /* 2^28 float */
                f2 = r4;
                f1 = f1 * f2;
                r4 = fix f1;
                /* fold the bus-assign bit INTO the coefficient */
                r6 = 0;
                r7 = dm(i0, 1);
                r7 = pass r7;
                if eq r4 = r6;
                dm(i2, 1) = r4;               /* Q4.28 crosspoint coeff */
                modify(i4, 1);
                modify(i5, 1);
                modify(i3, 1);
            .{kind}rmp_{nid}:
                nop;

            /* Pickoff enum -> source address, once per block. Left in the
             * accumulate path it cost every enabled send up to three
             * compares and two branches PER SAMPLE. Crosspoints whose
             * coefficient is zero keep the default and are never read. */
            l1 = 0;
            i1 = _rtg_{kind}_sq_{nid};
            i5 = _rtg_{kind}_pick_{nid};
            i6 = _rtg_{kind}_src_{nid};
            r5 = {count};
            lcntr = r5, do .{kind}src_{nid} until lce;
                r6 = dm(i5, 1);               /* pickoff enum */
                r4 = dm(i1, 1);               /* coefficient */
                r0 = {sd};
                r4 = pass r4;
                if eq jump (pc, .{kind}srcd_{nid});
                r6 = pass r6;
                if eq jump (pc, .{kind}src0_{nid});
                r7 = 1;
                comp(r6, r7);
                if eq jump (pc, .{kind}src1_{nid});
                r7 = 2;
                comp(r6, r7);
                if ne jump (pc, .{kind}srcd_{nid});
                r0 = {s2};
                jump (pc, .{kind}srcd_{nid});
            .{kind}src0_{nid}:
                r0 = {s0};
                jump (pc, .{kind}srcd_{nid});
            .{kind}src1_{nid}:
                r0 = {s1};
            .{kind}srcd_{nid}:
                dm(i6, 1) = r0;
            .{kind}src_{nid}:
                nop;
"""


def gen_routing_fixed(node):
    """Fixed ROUTING (D5) as a CROSSPOINT-COEFFICIENT matrix (08-25 hub
    mandate, Bible docs/bible/10-cell-data-and-protocol.md).

    ONE precomputed Q4.28 coefficient per source x bus crosspoint. Every
    linear term -- fader level, DCA, mute, pan leg, bus assign, send level
    -- is folded into it HERE, at control rate. The accumulate path is
    exact 64-bit MACs that read a coefficient, a source address and a bus
    accumulator, and never look at control state; an unassigned or muted
    crosspoint is a coefficient of exactly zero.

    What this replaced (audited 2026-08-27): the main bus was fed from
    FADER_PAN's PRE-MULTIPLIED L/R buffers with a unity coefficient, so the
    pan leg was a second multiply with its own round-and-saturate --
    `fader then pan then unity MAC` where doctrine says one coefficient and
    one MAC. Folding it removes two of FADER_PAN's three round/saturate
    stages per sample and removes an intermediate rounding, so the bus sum
    is also strictly closer to the reference model.
    """
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    fdr_id = node['inputs_str']
    gain_id = fdr_id.replace('_FDR_', '_GAIN_')
    eq_id = fdr_id.replace('_FDR_', '_EQ_')
    dly_id = fdr_id.replace('_FDR_', '_DLY_')
    aux_pick_defaults = ', '.join(['3'] * 12)
    fx_pick_defaults = ', '.join(['3'] * 6)

    # Source expressions. Per-sample builds read SCALAR taps; block builds
    # walk 32-word tap slots out of the shared pool. The block form used to
    # hand _acc64_mac_blk the address of a SCALAR tap and let it walk 32
    # words off the end of it -- pickoffs 0/1/2 read whatever followed the
    # variable. BLK_TAP_* existed in blk_pool.h for exactly this and was
    # never wired up.
    scalar_srcs = (f'_tap_post_trim_{gain_id}', f'_tap_post_eq_{eq_id}',
                   f'_tap_pre_fader_{dly_id}', f'_tap_post_fader_{fdr_id}')
    block_srcs = ('BLK_TAP_TRIM', 'BLK_TAP_EQ', 'BLK_TAP_PREFDR',
                  'BLK_CHAIN_A')

    def send_prep(kind, count):
        return (f'        #if DSP4_BLOCK_KERNELS\n'
                + _fx_send_ramp_asm(nid, kind, count, block_srcs)
                + f'        #else\n'
                + _fx_send_ramp_asm(nid, kind, count, scalar_srcs)
                + f'        #endif\n')

    return dedent(f"""\
        {rc}

        /* ROUTING (FIXED Q4.28, D5): crosspoint-coefficient matrix mixing */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        #include "blk_pool.h"

        .section/dm seg_dmda;
        .extern _tap_post_trim_{gain_id};
        .extern _tap_post_eq_{eq_id};
        .extern _tap_pre_fader_{dly_id};
        .extern _tap_post_fader_{fdr_id};
        .extern _fdr_lq_{fdr_id};
        .extern _fdr_rq_{fdr_id};
        .var _rtg_main_on_{nid} = 1;
        .var _rtg_sub_on_{nid} = 0;
        .var _rtg_grp_on_{nid}[4] = 0, 0, 0, 0;
        .var _rtg_aux_on_{nid}[12];
        .var _rtg_aux_send_{nid}[12];
        .var _rtg_aux_send_target_{nid}[12];
        .var _rtg_aux_send_step_{nid}[12];
        .var _rtg_aux_send_frames_{nid}[12];
        .var _rtg_aux_pick_{nid}[12] = {aux_pick_defaults};
        .var _rtg_aux_sq_{nid}[12];               /* crosspoint coeffs */
        .var _rtg_aux_src_{nid}[12];              /* resolved sources  */
        .var _rtg_fx_on_{nid}[6];
        .var _rtg_fx_send_{nid}[6];
        .var _rtg_fx_send_target_{nid}[6];
        .var _rtg_fx_send_step_{nid}[6];
        .var _rtg_fx_send_frames_{nid}[6];
        .var _rtg_fx_pick_{nid}[6] = {fx_pick_defaults};
        .var _rtg_fx_sq_{nid}[6];
        .var _rtg_fx_src_{nid}[6];
        /* main/sub/group crosspoint coefficients: pan leg or unity, times
         * the bus-assign bit. Prepared below at control rate. */
        .var _rtg_mlq_{nid} = 0;
        .var _rtg_mrq_{nid} = 0;
        .var _rtg_subq_{nid} = 0;
        .var _rtg_grpq_{nid}[4] = 0, 0, 0, 0;
        /* The live-crosspoint list: (source, bus accumulator, coefficient)
         * triples, rebuilt at control rate, walked by the audio path. 25
         * crosspoints is the worst case -- main L, main R, sub, 4 groups,
         * 12 aux, 6 fx -- so the list is sized for all of them being on and
         * never needs a bounds test. _rtg_n starts at 0, so the accumulate
         * does nothing until the first control-rate pass has built it. */
        .var _rtg_list_{nid}[75];
        .var _rtg_n_{nid} = 0;
        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _sample_idx;
        .extern _bus_acc_main_l; .extern _bus_acc_main_r;
        .extern _bus_acc_sub;
        .extern _bus_acc_grp_ptrs;
        .extern _bus_acc_aux_ptrs;
        .extern _bus_acc_fx_ptrs;
        .extern _acc64_mac;
        .global _{nid}_process;
        _{nid}_process:

            /* ===== control rate: prepare every crosspoint coefficient =====
             * The block-rate guard exists ONLY for the per-sample build.
             * Under DSP4_BLOCK_KERNELS the chain runs once per block with
             * _sample_idx left at 31, so a surviving `_sample_idx == 0`
             * test never fires -- and this node's send coefficients would
             * never be computed at all. */
        #if !DSP4_BLOCK_KERNELS
            r4 = dm(_sample_idx);
            r1 = 0;
            comp(r4, r1);
            if ne jump (pc, .rtg_acc_{nid});
        #endif

            /* main L/R: pan leg x main assign. _fdr_lq/_fdr_rq are PAN
             * ONLY -- the fader, DCA and mute are already inside the
             * post-fader mono this coefficient multiplies, so folding the
             * fader in here would apply it twice (bench 2026-08-23). */
            r8 = 0;
            r9 = 0x10000000;                  /* unity Q4.28 */
            r2 = dm(_rtg_main_on_{nid});
            r1 = dm(_fdr_lq_{fdr_id});
            r2 = pass r2;
            if eq r1 = r8;
            dm(_rtg_mlq_{nid}) = r1;
            r1 = dm(_fdr_rq_{fdr_id});
            r2 = pass r2;
            if eq r1 = r8;
            dm(_rtg_mrq_{nid}) = r1;

            r2 = dm(_rtg_sub_on_{nid});
            r1 = r9;
            r2 = pass r2;
            if eq r1 = r8;
            dm(_rtg_subq_{nid}) = r1;

            l5 = 0;
            l6 = 0;
            i5 = _rtg_grp_on_{nid};
            i6 = _rtg_grpq_{nid};
            lcntr = 4, do .rtg_gq_{nid} until lce;
                r2 = dm(i5, 1);
                r1 = r9;
                r2 = pass r2;
                if eq r1 = r8;
            .rtg_gq_{nid}:
                dm(i6, 1) = r1;

{send_prep('aux', 12)}{send_prep('fx', 6)}
            /* ===== compact the LIVE crosspoints into one list =====
             * The fold above left the accumulate path reading coefficients
             * only, but it still WALKED all 25 crosspoints every sample to
             * find the two or three that are live. That walk is control
             * state too -- which crosspoints are on is a control-rate fact --
             * so it resolves here, into a dense list of
             * (source address, bus accumulator, coefficient) triples and a
             * count. The audio path then iterates over live crosspoints
             * only, with no test of any kind in it.
             *
             * Cost is one 25-entry walk per BLOCK against 25 walked per
             * SAMPLE; a channel assigned to main only goes from 25
             * iterations per sample to 2. */
        #if DSP4_BLOCK_KERNELS
            r12 = BLK_CHAIN_A;                /* post-fader mono block */
        #else
            r12 = _buf_{fdr_id};              /* post-fader mono word  */
        #endif
            l0 = 0;
            l3 = 0;
            l4 = 0;
            l5 = 0;
            i0 = _rtg_list_{nid};
            r10 = 0;                          /* live count */

            r1 = dm(_rtg_mlq_{nid});
            r1 = pass r1;
            if eq jump (pc, .lb_noml_{nid});
            dm(i0, 1) = r12;
            r2 = _bus_acc_main_l;
            dm(i0, 1) = r2;
            dm(i0, 1) = r1;
            r10 = r10 + 1;
        .lb_noml_{nid}:
            r1 = dm(_rtg_mrq_{nid});
            r1 = pass r1;
            if eq jump (pc, .lb_nomr_{nid});
            dm(i0, 1) = r12;
            r2 = _bus_acc_main_r;
            dm(i0, 1) = r2;
            dm(i0, 1) = r1;
            r10 = r10 + 1;
        .lb_nomr_{nid}:
            r1 = dm(_rtg_subq_{nid});
            r1 = pass r1;
            if eq jump (pc, .lb_nosub_{nid});
            dm(i0, 1) = r12;
            r2 = _bus_acc_sub;
            dm(i0, 1) = r2;
            dm(i0, 1) = r1;
            r10 = r10 + 1;
        .lb_nosub_{nid}:

            i4 = _rtg_grpq_{nid};
            i3 = _bus_acc_grp_ptrs;
            lcntr = 4, do .lb_grp_{nid} until lce;
                r1 = dm(i4, 1);
                r3 = dm(i3, 1);
                r1 = pass r1;
                if eq jump (pc, .lb_gskip_{nid});
                dm(i0, 1) = r12;
                dm(i0, 1) = r3;
                dm(i0, 1) = r1;
                r10 = r10 + 1;
            .lb_gskip_{nid}:
                nop;
            .lb_grp_{nid}:
                nop;

            i4 = _rtg_aux_sq_{nid};
            i5 = _rtg_aux_src_{nid};
            i3 = _bus_acc_aux_ptrs;
            lcntr = 12, do .lb_aux_{nid} until lce;
                r1 = dm(i4, 1);
                r3 = dm(i3, 1);
                r2 = dm(i5, 1);
                r1 = pass r1;
                if eq jump (pc, .lb_askip_{nid});
                dm(i0, 1) = r2;
                dm(i0, 1) = r3;
                dm(i0, 1) = r1;
                r10 = r10 + 1;
            .lb_askip_{nid}:
                nop;
            .lb_aux_{nid}:
                nop;

            i4 = _rtg_fx_sq_{nid};
            i5 = _rtg_fx_src_{nid};
            i3 = _bus_acc_fx_ptrs;
            lcntr = 6, do .lb_fx_{nid} until lce;
                r1 = dm(i4, 1);
                r3 = dm(i3, 1);
                r2 = dm(i5, 1);
                r1 = pass r1;
                if eq jump (pc, .lb_fskip_{nid});
                dm(i0, 1) = r2;
                dm(i0, 1) = r3;
                dm(i0, 1) = r1;
                r10 = r10 + 1;
            .lb_fskip_{nid}:
                nop;
            .lb_fx_{nid}:
                nop;

            dm(_rtg_n_{nid}) = r10;

        .rtg_acc_{nid}:
            /* ===== crosspoint accumulate =====
             * Nothing here reads control state and nothing here branches on
             * it. Every iteration is a live crosspoint: fetch its source,
             * its bus and its coefficient, and MAC. */
            r5 = dm(_rtg_n_{nid});
            r5 = pass r5;
            if eq jump (pc, .rtg_tail_{nid});
            l1 = 0;
            l2 = 0;
            l6 = 0;
            i6 = _rtg_list_{nid};
            lcntr = r5, do .rtg_xp_{nid} until lce;
                r6 = dm(i6, 1);               /* source            */
                r3 = dm(i6, 1);               /* bus accumulator   */
                r1 = dm(i6, 1);               /* coefficient       */
        #if DSP4_BLOCK_KERNELS
                i0 = r6;
                i2 = r3;
                call _acc64_mac_blk;
        #else
                i1 = r6;
                r0 = dm(i1, 0);
                i2 = r3;
                call _acc64_mac;
        #endif
            .rtg_xp_{nid}:
                nop;
        .rtg_tail_{nid}:

            r0 = dm(_tap_post_fader_{fdr_id});
            dm(_buf_{nid}) = r0;
            rts;
        _{nid}_process.end:
    """)


def gen_tube_sat_fixed(node):
    import re as _re
    if _re.match(r'^C\d+_TUBE_\d+$', node['id']):
        blk_tube_body = _TUBE_BLK_BODY.format(nid=node['id'], inp=node['inputs_str'])
    else:
        blk_tube_body = ''

    """Fixed TUBE_SAT (D5): y = x*(1 + sat*(1 - x^2)) entirely in
    Q4.28 MRF math; float sat ramp retained per sample with a FIX."""
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    return dedent(f"""\
        {rc}

        /* TUBE_SAT (FIXED Q4.28, D5) */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        #include "blk_pool.h"

        .section/dm seg_dmda;
        .var _tube_on_{nid} = 0;
        .var _tube_sat_{nid} = 0.0;
        .var _tube_sat_target_{nid} = 0.0;
        .var _tube_sat_step_{nid} = 0.0;
        .var _tube_sat_frames_{nid} = 0;
        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _mrf_rns28;
        .global _{nid}_process;
        _{nid}_process:
        {blk_tube_body}
            r0 = dm(_buf_{inp});

            r4 = dm(_tube_sat_frames_{nid});
            r15 = 1;
            r4 = r4 - r15;
            if le jump (pc, .no_tramp_{nid});
            dm(_tube_sat_frames_{nid}) = r4;
            f3 = dm(_tube_sat_{nid});
            f2 = dm(_tube_sat_step_{nid});
            f3 = f3 + f2;
            dm(_tube_sat_{nid}) = f3;
            jump (pc, .tube_go_{nid});
        .no_tramp_{nid}:
            f3 = dm(_tube_sat_target_{nid});
            dm(_tube_sat_{nid}) = f3;
        .tube_go_{nid}:

            r2 = dm(_tube_on_{nid});
            r2 = pass r2;
            if eq jump (pc, .tube_bypass_{nid});

            r8 = r0;                      /* x */
            r4 = 0x4D800000;              /* sat -> Q4.28 */
            f4 = r4;
            f3 = f3 * f4;
            r9 = fix f3;                  /* sat_q */

            mrf = r8 * r8 (ssi);
            call _mrf_rns28;              /* r0 = x^2 */
            r10 = 0x10000000;             /* 1.0 Q4.28 */
            r10 = r10 - r0;               /* 1 - x^2 */
            mrf = r9 * r10 (ssi);
            call _mrf_rns28;              /* sat*(1-x^2) */
            r10 = 0x10000000;
            r10 = r10 + r0;               /* 1 + sat*(1-x^2) */
            mrf = r8 * r10 (ssi);
            call _mrf_rns28;              /* y */
            jump (pc, .tube_out_{nid});
        .tube_bypass_{nid}:
            nop;
        .tube_out_{nid}:
            dm(_buf_{nid}) = r0;
            rts;
        _{nid}_process.end:
    """)


def gen_aux_input_fixed(node):
    """Fixed AUX_INPUT (D5): float level ramp per sample + FIX shadow,
    MRF sample path, integer on-gate."""
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    return dedent(f"""\
        {rc}

        /* AUX_INPUT (FIXED Q4.28, D5) */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        .section/dm seg_dmda;
        .var _auxin_on_{nid} = 0;
        .var _auxin_level_{nid} = 1.0;
        .var _auxin_level_target_{nid} = 1.0;
        .var _auxin_level_step_{nid} = 0.0;
        .var _auxin_level_frames_{nid} = 0;
        .var _auxin_q_{nid} = 0;                  /* Q4.28 coeff x assign */
        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _sample_idx;
        .extern _mrf_rns28;
        .global _{nid}_process;
        _{nid}_process:
            /* CONTROL RATE (08-25 crosspoint-coefficient mandate). This
             * node used to advance its ramp, multiply by 2^28 and FIX the
             * result on EVERY SAMPLE -- coefficient prep sitting in the
             * audio path, thirty-two times per block -- and then test the
             * input-assign bit per sample as well. Both are control state:
             * the coefficient is prepared once per block with the assign
             * bit folded in, and the sample path is one MAC.
             *
             * The frame count is consumed 32 at a time to keep the ramp
             * DURATION identical now that it advances once per block; the
             * same correction GAIN and FADER_PAN carry (2026-08-23). */
        #if !DSP4_BLOCK_KERNELS
            r4 = dm(_sample_idx);
            r1 = 0;
            comp(r4, r1);
            if ne jump (pc, .auxin_apply_{nid});
        #endif
            r4 = dm(_auxin_level_frames_{nid});
            r15 = 32;
            r4 = r4 - r15;
            if le jump (pc, .no_auxramp_{nid});
            dm(_auxin_level_frames_{nid}) = r4;
            f1 = dm(_auxin_level_{nid});
            f2 = dm(_auxin_level_step_{nid});
            r15 = 0x42000000;                 /* 32.0f */
            f15 = r15;
            f2 = f2 * f15;
            f1 = f1 + f2;
            dm(_auxin_level_{nid}) = f1;
            jump (pc, .auxin_go_{nid});
        .no_auxramp_{nid}:
            f1 = dm(_auxin_level_target_{nid});
            dm(_auxin_level_{nid}) = f1;
        .auxin_go_{nid}:
            r2 = 0x4D800000;
            f2 = r2;
            f1 = f1 * f2;
            r1 = fix f1;
            /* fold the input-assign bit INTO the coefficient */
            r3 = 0;
            r2 = dm(_auxin_on_{nid});
            r2 = pass r2;
            if eq r1 = r3;
            dm(_auxin_q_{nid}) = r1;

        .auxin_apply_{nid}:
            r0 = dm(_buf_{inp});
            r1 = dm(_auxin_q_{nid});
            mrf = r0 * r1 (ssi);
            call _mrf_rns28;
            dm(_buf_{nid}) = r0;
            rts;
        _{nid}_process.end:
    """)


def gen_monitor_fixed(node):
    """Fixed MONITOR (D5): level ramps and Q4.28 conversion at CONTROL rate,
    one MAC in the sample path.

    Two things were wrong here and both are the same mistake in different
    clothes (08-25 crosspoint-coefficient mandate, audited 2026-08-27):

    1. The ramp advanced, the float multiply by 2^28 ran and the FIX ran on
       EVERY SAMPLE. That is coefficient prep sitting in the audio path,
       thirty-two times per block, for a value that changes once per block.

    2. The L and R levels shared ONE step and ONE frames word, with their
       targets interleaved between the two values. _ramp_set_target
       addresses a parameter's companions at +s/+2s/+3s from the VALUE, and
       no single stride describes that layout -- so the ramp-stride table
       had no entry for either level, every ramped write to them degraded to
       a plain write, and the block-rate code then clobbered it from a
       target nothing had set. Both monitor levels were unsettable.

    Each level now carries its own complete quad in the standard order.

    NOT FIXED HERE, and recorded rather than papered over: the sample path
    is MONO and uses the L level only, so _mon_level_r is settable but has
    no effect. Making MONITOR genuinely stereo is a graph change, not a
    coefficient fold, and is out of this mandate's scope.
    """
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']

    def ramp(side):
        return f"""\
            r4 = dm(_mon_level_{side}_frames_{nid});
            r15 = 32;
            r4 = r4 - r15;
            if le jump (pc, .no_monramp_{side}_{nid});
            dm(_mon_level_{side}_frames_{nid}) = r4;
            f1 = dm(_mon_level_{side}_{nid});
            f2 = dm(_mon_level_{side}_step_{nid});
            r15 = 0x42000000;                 /* 32.0f */
            f15 = r15;
            f2 = f2 * f15;
            f1 = f1 + f2;
            dm(_mon_level_{side}_{nid}) = f1;
            jump (pc, .moncvt_{side}_{nid});
        .no_monramp_{side}_{nid}:
            f1 = dm(_mon_level_{side}_target_{nid});
            dm(_mon_level_{side}_{nid}) = f1;
        .moncvt_{side}_{nid}:
            r2 = 0x4D800000;
            f2 = r2;
            f1 = f1 * f2;
            r1 = fix f1;
            dm(_mon_q_{side}_{nid}) = r1;"""

    return dedent(f"""\
        {rc}

        /* MONITOR (FIXED Q4.28, D5) */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        .section/dm seg_dmda;
        .var _mon_source_{nid} = 0;
        .var _mon_level_l_{nid} = 1.0;
        .var _mon_level_l_target_{nid} = 1.0;
        .var _mon_level_l_step_{nid} = 0.0;
        .var _mon_level_l_frames_{nid} = 0;
        .var _mon_level_r_{nid} = 1.0;
        .var _mon_level_r_target_{nid} = 1.0;
        .var _mon_level_r_step_{nid} = 0.0;
        .var _mon_level_r_frames_{nid} = 0;
        .var _mon_q_l_{nid} = 0x10000000;         /* Q4.28 shadows */
        .var _mon_q_r_{nid} = 0x10000000;
        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _sample_idx;
        .extern _mrf_rns28;
        .global _{nid}_process;
        _{nid}_process:
        #if !DSP4_BLOCK_KERNELS
            r4 = dm(_sample_idx);
            r1 = 0;
            comp(r4, r1);
            if ne jump (pc, .mon_go_{nid});
        #endif
{ramp('l')}
{ramp('r')}

        .mon_go_{nid}:
            r0 = dm(_buf_{inp});
            r1 = dm(_mon_q_l_{nid});
            mrf = r0 * r1 (ssi);
            call _mrf_rns28;
            dm(_buf_{nid}) = r0;
            rts;
        _{nid}_process.end:
    """)


def gen_talkback_fixed(node):
    """Fixed TALKBACK (D5): integer on-gate, float gain ramp + FIX,
    MRF gain, fixed 1-stage HPF (coeffs converted at block rate from
    the host-written float set)."""
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    return dedent(f"""\
        {rc}

        /* TALKBACK (FIXED Q4.28, D5) */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        .section/dm seg_dmda;
        .var _talk_on_{nid} = 0;
        .var _talk_gain_{nid} = 1.0;
        .var _talk_gain_target_{nid} = 1.0;
        .var _talk_gain_step_{nid} = 0.0;
        .var _talk_gain_frames_{nid} = 0;
        .var _talk_hpf_on_{nid} = 1;
        .var _talk_hpf_coeffs_{nid}[5] = 1.0, 0.0, 0.0, 0.0, 0.0;
        .var _talk_hpf_cq_{nid}[5] = 0x10000000, 0x20000000, 0xF0000000, 0x20000000, 0x10000000;
        .var _talk_hpf_state_{nid}[6];
        .var _talk_route_{nid}[3];
        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _sample_idx;
        .extern _mrf_rns28;
        .extern _bq_fx_cascade_N;
        .extern _bq_fx_convert_N;
        .global _{nid}_process;
        _{nid}_process:
            r2 = dm(_talk_on_{nid});
            r2 = pass r2;
            if eq rts;

            /* block-rate: refresh fixed HPF coeffs from float set */
        /* The block-rate guard exists ONLY for the per-sample build. Under
         * DSP4_BLOCK_KERNELS the node chain runs ONCE per block with
         * _sample_idx left at 31 by the scatter loop, so a surviving
         * `_sample_idx == 0` test NEVER fires and the parameters below are
         * never converted -- the node then runs on its .var initialisers.
         * Audited 2026-08-27: 132 nodes carried this dead guard. */
        #if !DSP4_BLOCK_KERNELS
            r4 = dm(_sample_idx);
            r1 = 0;
            comp(r4, r1);
            if ne jump (pc, .tk_ramp_{nid});
        #endif
            i0 = _talk_hpf_coeffs_{nid};
            i1 = _talk_hpf_cq_{nid};
            r4 = 1;
            call _bq_fx_convert_N;
        .tk_ramp_{nid}:

            /* Consume a BLOCK's worth of frames and apply a BLOCK's
             * worth of step. spi_handler scales every profile frame count
             * by 32 (BLOCK_SIZE), which is right for the ramps that
             * decrement once per SAMPLE. This one decrements once per
             * BLOCK, so taking 1 per block ran it 32x long: measured
             * 2026-08-23, a GainSafe down-ramp took 960 ms against the
             * 30 ms its own cell table specifies, and a GainFast fader
             * move took 85 ms instead of 3 ms. 32.0f is exact in binary,
             * so scaling the step loses nothing. */
            r4 = dm(_talk_gain_frames_{nid});
            r15 = 0;
            comp(r4, r15);
            if le jump (pc, .no_tkramp_{nid});
            r15 = 32;
            r4 = r4 - r15;
            dm(_talk_gain_frames_{nid}) = r4;
            f1 = dm(_talk_gain_{nid});
            f2 = dm(_talk_gain_step_{nid});
            r15 = 0x42000000;                 /* 32.0f */
            f15 = r15;
            f2 = f2 * f15;
            f1 = f1 + f2;
            dm(_talk_gain_{nid}) = f1;
            jump (pc, .tk_go_{nid});
        .no_tkramp_{nid}:
            f1 = dm(_talk_gain_target_{nid});
            dm(_talk_gain_{nid}) = f1;
        .tk_go_{nid}:

            r2 = 0x4D800000;
            f2 = r2;
            f1 = f1 * f2;
            r1 = fix f1;
            r0 = dm(_buf_{inp});
            mrf = r0 * r1 (ssi);
            call _mrf_rns28;

            r2 = dm(_talk_hpf_on_{nid});
            r2 = pass r2;
            if eq jump (pc, .tk_nohpf_{nid});
            i0 = _talk_hpf_cq_{nid};
            i1 = _talk_hpf_state_{nid};
            r4 = 1;
            call _bq_fx_cascade_N;
        .tk_nohpf_{nid}:
            dm(_buf_{nid}) = r0;
            rts;
        _{nid}_process.end:
    """)


def gen_noise_gen_fixed(node):
    """Fixed-mode NOISE_GEN (D5): documented FLOAT ISLAND — synthesis
    has no golden-parity requirement; only the output converts to
    Q4.28 at the store (same boundary treatment as the FX engines)."""
    nid = node['id']
    body = gen_noise_gen(node)
    old = f""".noise_out_{nid}:
    dm(_buf_{nid}) = r0;"""
    new = f""".noise_out_{nid}:
    /* float island boundary -> Q4.28 (D5) */
    r1 = 0x4D800000;
    f1 = r1;
    f0 = f0 * f1;
    r0 = fix f0;
    dm(_buf_{nid}) = r0;"""
    assert old in body, 'noise tail pattern moved'
    return body.replace(old, new)



# IEEE-754 hex constants for fixed-mode dynamics conversions
_C_DB2L2Q25 = 0x4AAA152D   # (2^25)/(20*log10(2)): dB -> log2-domain Q6.25
_C_F_KHALF = 0x4040A8C1    # (20*log10(2))/2, for k2 = slope*K/(2*knee_db)


def _fx_recip_asm(dst, src):
    """Newton-Raphson float reciprocal: dst = 1/src; clobbers f7, f8, r10."""
    return (f"            f7 = recips {src};\n"
            f"            f8 = {src} * f7;\n"
            f"            r10 = 0x40000000;\n"
            f"            f8 = f10 - f8;\n"
            f"            f7 = f7 * f8;\n"
            f"            f8 = {src} * f7;\n"
            f"            f8 = f10 - f8;\n"
            f"            {dst} = f7 * f8;")


def gen_poly_tables_fixed():
    """Emit the exact fixed_ref polynomial coefficient integers."""
    import fixed_ref
    out = []
    out.append('/* poly_tables_fx.asm — log2/exp2 Q2.30 poly coefficients (D5) */')
    out.append('/* AUTO-GENERATED from tools/dsp/fixed_ref.py — do not edit. */')
    out.append('/* These integers ARE the normative approximants (harness-validated). */')
    out.append('')
    out.append('.section/dm seg_dmda;')
    out.append('.global _log2_poly_fx;')
    out.append('.var _log2_poly_fx[6] = ' +
               ', '.join('0x%08X' % (c & 0xFFFFFFFF) for c in fixed_ref.LOG2_POLY) + ';')
    out.append('.global _exp2_poly_fx;')
    out.append('.var _exp2_poly_fx[6] = ' +
               ', '.join('0x%08X' % (c & 0xFFFFFFFF) for c in fixed_ref.EXP2_POLY) + ';')
    out.append('')
    return '\n'.join(out)



def _fx_dyn_block_cvt(nid, pfx, with_knee, with_slope):
    """Block-rate conversion of dynamics control params to fixed:
    alphas -> Q0.31, threshold dB -> log2 Q6.25, slope/knee for the
    _compgain_fx param block. Emitted at sample_idx==0."""
    lines = []
    a = lines.append
    a(f'            r2 = 0x4F000000;              /* 2^31 float */')
    a(f'            f2 = r2;')
    a(f'            f1 = dm(_{pfx}_attack_{nid});')
    a(f'            f1 = f1 * f2;')
    a(f'            r1 = fix f1;')
    a(f'            dm(_{pfx}_attq_{nid}) = r1;')
    a(f'            f1 = dm(_{pfx}_release_{nid});')
    a(f'            f1 = f1 * f2;')
    a(f'            r1 = fix f1;')
    a(f'            dm(_{pfx}_relq_{nid}) = r1;')
    a(f'            r2 = _C_DB2L2Q25_;            /* dB -> Q6.25 log2 */')
    a(f'            f2 = r2;')
    a(f'            f1 = dm(_{pfx}_threshold_{nid});')
    a(f'            f1 = f1 * f2;')
    a(f'            r1 = fix f1;')
    a(f'            dm(_{pfx}_cgp_{nid}) = r1;    /* thr */')
    if with_slope:
        a(f'            /* slope = 1 - 1/ratio */')
        a(f'            f6 = dm(_{pfx}_ratio_{nid});')
        a(_fx_recip_asm('f6', 'f6'))
        a(f'            r2 = 0x3F800000;')
        a(f'            f5 = r2;')
        a(f'            f5 = f5 - f6;                 /* slope float */')
        a(f'            r2 = 0x4F000000;')
        a(f'            f2 = r2;')
        a(f'            f1 = f5 * f2;')
        a(f'            r1 = fix f1;')
        a(f'            dm(_{pfx}_cgp_{nid} + 1) = r1;')
    else:
        a(f'            r1 = 0x7FFFFFFF;              /* slope = ~1.0 (brick wall) */')
        a(f'            dm(_{pfx}_cgp_{nid} + 1) = r1;')
    if with_knee:
        a(f'            /* knee: halfk = knee_db/2 in Q6.25 log2; k2 = slope*K/(2*knee) Q6.25 */')
        a(f'            f4 = dm(_{pfx}_knee_{nid});')
        a(f'            r2 = 0x3DCCCCCD;              /* 0.1 dB min for soft path */')
        a(f'            f3 = r2;')
        a(f'            comp(f4, f3);')
        a(f'            if gt jump (pc, .{pfx}_soft_{nid});')
        a(f'            r1 = 0;')
        a(f'            dm(_{pfx}_cgp_{nid} + 2) = r1;')
        a(f'            dm(_{pfx}_cgp_{nid} + 3) = r1;')
        a(f'            jump (pc, .{pfx}_kdone_{nid});')
        a(f'        .{pfx}_soft_{nid}:')
        a(f'            r2 = _C_DB2L2Q25_;')
        a(f'            f2 = r2;')
        a(f'            f1 = f4 * f2;')
        a(f'            r2 = 0x3F000000;              /* 0.5 */')
        a(f'            f3 = r2;')
        a(f'            f1 = f1 * f3;')
        a(f'            r1 = fix f1;')
        a(f'            dm(_{pfx}_cgp_{nid} + 2) = r1;  /* halfk */')
        a(_fx_recip_asm('f6', 'f4'))
        a(f'            r2 = _C_F_KHALF_;             /* K/2 */')
        a(f'            f3 = r2;')
        a(f'            f6 = f6 * f3;                 /* K/(2*knee_db) */')
        a(f'            f6 = f6 * f5;                 /* * slope */')
        a(f'            r2 = 0x4C000000;              /* 2^25 float */')
        a(f'            f2 = r2;')
        a(f'            f1 = f6 * f2;')
        a(f'            r1 = fix f1;')
        a(f'            dm(_{pfx}_cgp_{nid} + 3) = r1;  /* k2 */')
        a(f'        .{pfx}_kdone_{nid}:')
    else:
        a(f'            r1 = 0;')
        a(f'            dm(_{pfx}_cgp_{nid} + 2) = r1;')
        a(f'            dm(_{pfx}_cgp_{nid} + 3) = r1;')
    body = '\n'.join(lines)
    return body.replace('_C_DB2L2Q25_', '0x%08X' % _C_DB2L2Q25).replace(
        '_C_F_KHALF_', '0x%08X' % _C_F_KHALF)


# ---------------------------------------------------------------------------
# Block-rate guard, emitted per NODE rather than per generator.
#
# `_sample_idx` is left at 31 by the scatter loop, so under
# DSP4_BLOCK_KERNELS a surviving `_sample_idx == 0` test never fires and the
# node runs on its .var initialisers. That is a real defect and it cost the
# routing sends entirely (audited 2026-08-27).
#
# But it is NOT universal, and removing the guard everywhere is its own bug.
# COMPRESSOR and GATE emit a block kernel for the plain strip instances
# (C1_COMP_01, C1_GATE_01, ...) and that kernel DRIVES `_sample_idx` itself
# before calling the per-sample body -- GATE's sidechain-filter fallback
# calls that body 32 TIMES per block with the index driven 0 then 1, so
# dropping the guard there would run the whole parameter conversion on every
# sample. The same two generators emit NO block kernel for the chip-2
# instances (C2_GRP_COMP_01, C2_MAIN_COMP, ...), whose names do not match,
# and there the guard genuinely is dead.
#
# So: keep the guard exactly where something drives the index, drop it in the
# block build everywhere else.
# ---------------------------------------------------------------------------
def _blk_rate_guard(label, nid, has_block_kernel):
    guard = (f'            r4 = dm(_sample_idx);\n'
             f'            r1 = 0;\n'
             f'            comp(r4, r1);\n'
             f'            if ne jump (pc, .{label}_{nid});\n')
    if has_block_kernel:
        return ('        /* Kept in BOTH builds: this node has a block kernel that drives\n'
                '         * _sample_idx before reaching here, so the guard fires exactly\n'
                '         * once per block and is doing its job. */\n' + guard)
    return ('        /* Per-sample builds only. Under DSP4_BLOCK_KERNELS this node has no\n'
            '         * block kernel, the chain reaches it once per block with _sample_idx\n'
            '         * at 31, and a surviving guard would never fire -- the parameters\n'
            '         * below would never convert and the node would run on its .var\n'
            '         * initialisers. */\n'
            '        #if !DSP4_BLOCK_KERNELS\n' + guard + '        #endif\n')


def gen_compressor_fixed(node):
    import re as _re
    if _re.match(r'^C\d+_COMP_\d+$', node['id']):
        blk_comp_body = _COMP_BLK_BODY.format(nid=node['id'], inp=node['inputs_str'])
    else:
        blk_comp_body = ''
    comp_go_guard = _blk_rate_guard('comp_go', node['id'], bool(blk_comp_body))

    """Fixed COMPRESSOR (D5): fixed envelope + _compgain_fx (log2
    domain, soft knee) per fixed_ref; float control converted at block
    rate; makeup + parallel blend fixed."""
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    return dedent(f"""\
        {rc}

        /* COMPRESSOR (FIXED Q4.28, D5) */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

#include "blk_pool.h"

.section/dm seg_dmda;
        .var _comp_on_{nid} = 1;
        .var _comp_threshold_{nid} = -20.0;
        .var _comp_ratio_{nid} = 4.0;
        .var _comp_attack_{nid} = 0.01;
        .var _comp_release_{nid} = 0.001;
        .var _comp_makeup_{nid} = 1.0;
        .var _comp_makeup_target_{nid} = 1.0;
        .var _comp_makeup_step_{nid} = 0.0;
        .var _comp_makeup_frames_{nid} = 0;
        .var _comp_knee_{nid} = 0.0;   /* hard knee until the host sets it */
        .var _comp_parallel_{nid} = 0.0;
        .var _comp_type_{nid} = 0;
        .var _comp_key_src_{nid} = 0;
        .var _comp_det_src_{nid} = 0;
        .var _comp_eq_pos_{nid} = 0;
        .var _comp_lim_mode_{nid} = 0;
        .var _comp_filter_on_{nid} = 0;
        .var _comp_filter_coeffs_{nid}[10];
        .var _comp_filter_state_{nid}[4];
        .var _comp_envelope_{nid} = 0;        /* Q4.28 */
        .var _comp_gain_{nid} = 0x10000000;   /* Q4.28 (display) */
        .var _comp_attq_{nid} = 0;
        .var _comp_relq_{nid} = 0;
        .var _comp_mkq_{nid} = 0x10000000;
        .var _comp_parq_{nid} = 0;            /* Q0.31 */
        .var _comp_cgp_{nid}[4];              /* thr, slope, halfk, k2 */
        .var _buf_{nid};

#if DSP4_BLOCK_KERNELS
.var _comp_saved_idx_{nid};
#endif
        .section/pm seg_pmco;
        .extern _sample_idx;
        .extern _envq_fx;
        .extern _compgain_fx;
        .extern _mrf_rns28;
        .global _{nid}_process;
        _{nid}_process:
        {blk_comp_body}
            r0 = dm(_buf_{inp});
            r2 = dm(_comp_on_{nid});
            r3 = 0;
            comp(r2, r3);
            if eq jump (pc, .comp_bypass_{nid});
            r13 = r0;                     /* dry (r13-r15 lib-safe) */
        #if DSP4_COMP_NOCVT
            jump (pc, .comp_go_{nid});   /* TEMP bisect: skip block-rate cvt */
        #endif

            /* --- block rate: makeup ramp + param conversion --- */
{comp_go_guard}
            r4 = dm(_comp_makeup_frames_{nid});
            comp(r4, r1);
            if le jump (pc, .no_mramp_{nid});
            /* Consume a BLOCK's worth of frames and apply a BLOCK's
             * worth of step. spi_handler scales every profile frame count
             * by 32 (BLOCK_SIZE), which is right for the ramps that
             * decrement once per SAMPLE. This one decrements once per
             * BLOCK, so taking 1 per block ran it 32x long: measured
             * 2026-08-23, a GainSafe down-ramp took 960 ms against the
             * 30 ms its own cell table specifies, and a GainFast fader
             * move took 85 ms instead of 3 ms. 32.0f is exact in binary,
             * so scaling the step loses nothing. */
            r5 = 32;
            r4 = r4 - r5;
            dm(_comp_makeup_frames_{nid}) = r4;
            f1 = dm(_comp_makeup_{nid});
            f2 = dm(_comp_makeup_step_{nid});
            r5 = 0x42000000;                  /* 32.0f */
            f5 = r5;
            f2 = f2 * f5;
            f1 = f1 + f2;
            dm(_comp_makeup_{nid}) = f1;
            jump (pc, .comp_cvt_{nid});
        .no_mramp_{nid}:
            f1 = dm(_comp_makeup_target_{nid});
            dm(_comp_makeup_{nid}) = f1;
        .comp_cvt_{nid}:
            r2 = 0x4D800000;
            f2 = r2;
            f1 = f1 * f2;
            r1 = fix f1;
            dm(_comp_mkq_{nid}) = r1;
            f1 = dm(_comp_parallel_{nid});
            r2 = 0x4F000000;
            f2 = r2;
            f1 = f1 * f2;
            r1 = fix f1;
            /* CLAMP. parallel = 1.0 scales to 2^31, which int32 cannot
             * hold: `fix` wrapped and stored -1, so in Q0.31 the MAXIMUM
             * parallel setting blended in essentially nothing and the
             * compressor went fully DRY -- the same output as
             * parallel = 0, with a working compressor sitting behind it.
             * Bench 2026-08-23: par 0.999 settled at -16.49 dBFS on a
             * -6.02 dBFS step, par 1.0 returned the input untouched. */
            r3 = 0;
            r2 = 0x7FFFFFFF;
            comp(r1, r3);
            if lt r1 = pass r2;
            dm(_comp_parq_{nid}) = r1;
{_fx_dyn_block_cvt(nid, 'comp', with_knee=True, with_slope=True)}
        .comp_go_{nid}:

            /* --- envelope (fixed) --- */
            r0 = abs r13;
            r1 = dm(_comp_envelope_{nid});
            r2 = dm(_comp_attq_{nid});
            r3 = dm(_comp_relq_{nid});
            call _envq_fx;
            dm(_comp_envelope_{nid}) = r0;

            /* --- gain computer (log2 domain) --- */
            i0 = _comp_cgp_{nid};
            call _compgain_fx;            /* r0 = gain Q4.28 */
            dm(_comp_gain_{nid}) = r0;

            /* wet = dry * gain * makeup */
            r1 = r0;
            r0 = r13;
            mrf = r0 * r1 (ssi);
            call _mrf_rns28;
            r1 = dm(_comp_mkq_{nid});
            mrf = r0 * r1 (ssi);
            call _mrf_rns28;

            /* parallel: out = dry + par*(wet - dry) — matches the float
             * node exactly (par==0 -> dry, its default behaviour) */
            r5 = r0 - r13;
            r4 = dm(_comp_parq_{nid});
            mrf = r5 * r4 (ssi);
            r1 = 0x40000000;
            r12 = 1;
            mrf = mrf + r1 * r12 (ssi);
            r1 = mr0f;
            r12 = mr1f;
            r1 = lshift r1 by -31;
            r12 = lshift r12 by 1;
            r1 = r1 or r12;
            r0 = r13 + r1;
            dm(_buf_{nid}) = r0;
            rts;
        .comp_bypass_{nid}:
            dm(_buf_{nid}) = r0;
            rts;
        _{nid}_process.end:
    """)


def gen_limiter_fixed(node):
    """Fixed LIMITER (D5): brick wall = _compgain_fx with slope ~1,
    hard knee."""
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    return dedent(f"""\
        {rc}

        /* LIMITER (FIXED Q4.28, D5) */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        .section/dm seg_dmda;
        .var _lim_on_{nid} = 1;
        .var _lim_threshold_{nid} = -0.5;
        .var _lim_attack_{nid} = 0.5;
        .var _lim_release_{nid} = 0.001;
        .var _lim_envelope_{nid} = 0;
        .var _lim_attq_{nid} = 0;
        .var _lim_relq_{nid} = 0;
        .var _lim_cgp_{nid}[4];
        .var _buf_{nid};

        .section/pm seg_pmco;
        .extern _sample_idx;
        .extern _envq_fx;
        .extern _compgain_fx;
        .extern _mrf_rns28;
        .global _{nid}_process;
        _{nid}_process:
            r0 = dm(_buf_{inp});
            r2 = dm(_lim_on_{nid});
            r3 = 0;
            comp(r2, r3);
            if eq jump (pc, .lim_bypass_{nid});
            r13 = r0;

        /* The block-rate guard exists ONLY for the per-sample build. Under
         * DSP4_BLOCK_KERNELS the node chain runs ONCE per block with
         * _sample_idx left at 31 by the scatter loop, so a surviving
         * `_sample_idx == 0` test NEVER fires and the parameters below are
         * never converted -- the node then runs on its .var initialisers.
         * Audited 2026-08-27: 132 nodes carried this dead guard. */
        #if !DSP4_BLOCK_KERNELS
            r4 = dm(_sample_idx);
            r1 = 0;
            comp(r4, r1);
            if ne jump (pc, .lim_go_{nid});
        #endif
{_fx_dyn_block_cvt(nid, 'lim', with_knee=False, with_slope=False)}
        .lim_go_{nid}:

            r0 = abs r13;
            r1 = dm(_lim_envelope_{nid});
            r2 = dm(_lim_attq_{nid});
            r3 = dm(_lim_relq_{nid});
            call _envq_fx;
            dm(_lim_envelope_{nid}) = r0;

            i0 = _lim_cgp_{nid};
            call _compgain_fx;
            r1 = r0;
            r0 = r13;
            mrf = r0 * r1 (ssi);
            call _mrf_rns28;
            dm(_buf_{nid}) = r0;
            rts;
        .lim_bypass_{nid}:
            dm(_buf_{nid}) = r0;
            rts;
        _{nid}_process.end:
    """)


def gen_gate_fixed(node):
    import re as _re
    if _re.match(r'^C\d+_GATE_\d+$', node['id']):
        blk_gate_body = _GATE_BLK_BODY.format(nid=node['id'],
                                              inp=node['inputs_str'])
    else:
        blk_gate_body = ''
    gate_go_guard = _blk_rate_guard('gate_go', node['id'], bool(blk_gate_body))

    """Fixed GATE (D5): fixed envelope, log2-domain threshold compare,
    integer hold counter, one-pole fixed gain smoother toward 1.0 or
    the range floor; sidechain filter via the fixed biquad core with
    block-rate coefficient conversion."""
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    return dedent(f"""\
        {rc}

        /* GATE (FIXED Q4.28, D5) */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        #include "blk_pool.h"

        .section/dm seg_dmda;
        .var _gate_on_{nid} = 1;
        .var _gate_threshold_{nid} = -40.0;
        .var _gate_attack_{nid} = 0.05;
        .var _gate_release_{nid} = 0.005;
        .var _gate_hold_{nid} = 2400;
        .var _gate_hold_count_{nid} = 0;
        .var _gate_range_{nid} = 0.001;       /* linear floor (float) */
        .var _gate_key_src_{nid} = 0;
        .var _gate_det_src_{nid} = 0;
        .var _gate_filter_on_{nid} = 0;
        .var _gate_filter_hpf_{nid}[5] = 1.0, 0.0, 0.0, 0.0, 0.0;
        .var _gate_filter_lpf_{nid}[5] = 1.0, 0.0, 0.0, 0.0, 0.0;
        .var _gate_filter_cq_{nid}[10];
        .var _gate_filter_state_{nid}[12];
        .var _gate_envelope_{nid} = 0;
        .var _gate_gain_{nid} = 0x10000000;
        .var _gate_gain_target_q_{nid} = 0x10000000;
        .var _gate_attq_{nid} = 0;
        .var _gate_relq_{nid} = 0;
        .var _gate_thrq_{nid} = 0;
        .var _gate_rngq_{nid} = 0;
        .var _buf_{nid};

        #if DSP4_BLOCK_KERNELS
        .var _gate_saved_idx_{nid};
        #endif

        .section/pm seg_pmco;
        .extern _sample_idx;
        .extern _envq_fx;
        .extern _log2q_fx;
        .extern _exp2q_fx;
        .extern _mrf_rns28;
        .extern _bq_fx_cascade_N;
        .extern _bq_fx_convert_N;

        .global _{nid}_process;
        _{nid}_process:
        {blk_gate_body}
            r0 = dm(_buf_{inp});
            r2 = dm(_gate_on_{nid});
            r3 = 0;
            comp(r2, r3);
            if eq jump (pc, .gate_bypass_{nid});
            r13 = r0;

            /* --- block rate: param conversion --- */
{gate_go_guard}
            r2 = 0x4F000000;
            f2 = r2;
            f1 = dm(_gate_attack_{nid});
            f1 = f1 * f2;
            r1 = fix f1;
            dm(_gate_attq_{nid}) = r1;
            f1 = dm(_gate_release_{nid});
            f1 = f1 * f2;
            r1 = fix f1;
            dm(_gate_relq_{nid}) = r1;
            r2 = 0x%08X;
            f2 = r2;
            f1 = dm(_gate_threshold_{nid});
            f1 = f1 * f2;
            r1 = fix f1;
            dm(_gate_thrq_{nid}) = r1;
            r2 = 0x4D800000;
            f2 = r2;
            f1 = dm(_gate_range_{nid});
            f1 = f1 * f2;
            r1 = fix f1;
            dm(_gate_rngq_{nid}) = r1;
            r2 = dm(_gate_filter_on_{nid});
            r2 = pass r2;
            if eq jump (pc, .gate_go_{nid});
            i0 = _gate_filter_hpf_{nid};
            i1 = _gate_filter_cq_{nid};
            r4 = 1;
            call _bq_fx_convert_N;
            i0 = _gate_filter_lpf_{nid};
            r4 = 1;
            call _bq_fx_convert_N;      /* i1 continued */
        .gate_go_{nid}:

            /* --- sidechain: |x| (+ optional HPF/LPF) --- */
            r0 = abs r13;
            r2 = dm(_gate_filter_on_{nid});
            r2 = pass r2;
            if eq jump (pc, .gate_nofilt_{nid});
            i0 = _gate_filter_cq_{nid};
            i1 = _gate_filter_state_{nid};
            r4 = 2;
            call _bq_fx_cascade_N;
            r0 = abs r0;
        .gate_nofilt_{nid}:

            r1 = dm(_gate_envelope_{nid});
            r2 = dm(_gate_attq_{nid});
            r3 = dm(_gate_relq_{nid});
            call _envq_fx;
            dm(_gate_envelope_{nid}) = r0;

            /* threshold compare in log2 domain */
            r1 = pass r0;
            if le jump (pc, .gate_below_{nid});   /* env==0: below */
            call _log2q_fx;
            r1 = dm(_gate_thrq_{nid});
            comp(r0, r1);
            if ge jump (pc, .gate_open_{nid});
        .gate_below_{nid}:
            r4 = dm(_gate_hold_count_{nid});
            r15 = 1;
            r4 = r4 - r15;
            dm(_gate_hold_count_{nid}) = r4;
            if gt jump (pc, .gate_ramp_{nid});
            r5 = dm(_gate_rngq_{nid});
            dm(_gate_gain_target_q_{nid}) = r5;
            jump (pc, .gate_ramp_{nid});
        .gate_open_{nid}:
            r5 = 0x10000000;
            dm(_gate_gain_target_q_{nid}) = r5;
            r4 = dm(_gate_hold_{nid});
            dm(_gate_hold_count_{nid}) = r4;
        .gate_ramp_{nid}:
            /* one-pole gain smoother (fixed): gain += a*(target-gain) */
            r0 = dm(_gate_gain_target_q_{nid});
            r1 = dm(_gate_gain_{nid});
            r2 = dm(_gate_attq_{nid});
            r3 = dm(_gate_relq_{nid});
            call _envq_fx;                 /* same one-pole form */
            dm(_gate_gain_{nid}) = r0;

            r1 = r0;
            r0 = r13;
            mrf = r0 * r1 (ssi);
            call _mrf_rns28;
            dm(_buf_{nid}) = r0;
            rts;
        .gate_bypass_{nid}:
            dm(_buf_{nid}) = r0;
            rts;
        _{nid}_process.end:
    """ % _C_DB2L2Q25)



def gen_fx_engine_fixed(node):
    """Fixed-mode FX_ENGINE (D5): documented FLOAT ISLAND — the engine
    body runs float verbatim; Q4.28 <-> float32 conversion at the node
    edges (one read, one store)."""
    nid = node['id']
    inp = node['inputs_str']
    body = gen_fx_engine(node)
    old_in = f"    r0 = dm(_buf_{inp});"
    new_in = (f"    r0 = dm(_buf_{inp});\n"
              f"    /* float island entry: Q4.28 -> float32 (D5) */\n"
              f"    r1 = -28;\n"
              f"    f0 = float r0 by r1;")
    assert body.count(old_in) == 1, 'fx input pattern moved'
    body = body.replace(old_in, new_in)
    old_out = f"    dm(_buf_{nid}) = r0;"
    new_out = (f"    /* float island exit: float32 -> Q4.28 (D5) */\n"
               f"    r1 = 0x4D800000;\n"
               f"    f1 = r1;\n"
               f"    f0 = f0 * f1;\n"
               f"    r0 = fix f0;\n"
               f"    dm(_buf_{nid}) = r0;")
    assert body.count(old_out) == 1, 'fx output pattern moved'
    return body.replace(old_out, new_out)


FIXED_GENERATORS = {
    'EQ_BIQUAD': gen_eq_biquad_fixed,
    'GEQ': gen_geq_fixed,
    'ANTI_FB': gen_anti_fb_fixed,
    'HPF_LPF': gen_hpf_lpf_fixed,
    'CROSSOVER': gen_crossover_fixed,
    'GAIN': gen_gain_fixed,
    'FADER_PAN': gen_fader_pan_fixed,
    'MIX_BUS': gen_mix_bus_fixed,
    'ROUTING': gen_routing_fixed,
    'TUBE_SAT': gen_tube_sat_fixed,
    'AUX_INPUT': gen_aux_input_fixed,
    'MONITOR': gen_monitor_fixed,
    'TALKBACK': gen_talkback_fixed,
    'NOISE_GEN': gen_noise_gen_fixed,
    'COMPRESSOR': gen_compressor_fixed,
    'LIMITER': gen_limiter_fixed,
    'GATE': gen_gate_fixed,
    'FX_ENGINE': gen_fx_engine_fixed,
}



# ===========================================================================
# Main generation
# ===========================================================================

def generate(csv_path, output_dir, force=False, node_type_filter=None):
    with open(csv_path, newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("ERROR: dsp.csv is empty", file=sys.stderr)
        return 1

    nodes = []
    for row in rows:
        nid = row['id'].strip()
        node = {
            'id': nid,
            'chip': row['chip'].strip(),
            'type': row['type'].strip(),
            'label': row.get('label', '').strip(),
            'ch_count': row.get('ch_count', '1').strip(),
            'inputs': parse_id_list(row.get('inputs', '')),
            'outputs': parse_id_list(row.get('outputs', '')),
            'spi_page': row.get('spi_page', '-1').strip(),
            'spi_addr': row.get('spi_addr', '-1').strip(),
            'params': parse_params(row.get('params', '')),
            'ramp_profile': row.get('ramp_profile', '').strip(),
        }
        node['inputs_str'] = node['inputs'][0] if node['inputs'] else node['id']
        nodes.append(node)

    chip1_nodes = [n for n in nodes if n['chip'] == '1']
    chip2_nodes = [n for n in nodes if n['chip'] == '2']

    files_written = 0
    files_skipped = 0

    for chip_label, chip_nodes in [('chip1', chip1_nodes), ('chip2', chip2_nodes)]:
        nodes_dir = os.path.join(output_dir, chip_label, 'nodes')
        os.makedirs(nodes_dir, exist_ok=True)

        call_sequence = []

        # Generated first, not because its output is needed yet, but because
        # it is what computes each input node's DMA lane offset/stride and
        # annotates the node dicts. The block kernels below read those.
        bio_text, lane_info = gen_block_io(chip_label, chip_nodes)

        # METER placement. Every chip-1 meter taps its own channel's GAIN
        # output, and under per-block kernels that value lives in a SHARED
        # pool slot (BLK_CHAIN_B) which the next strip overwrites. The
        # meters sit at chain indices 320+, after all 32 strips have run and
        # the pool has been reused 32 times, so by the time a meter reads
        # "its" channel the data is thirty-one channels stale. Moving each
        # meter to run immediately after its source keeps the read on live
        # data. Meters are sinks with no downstream consumer, which is what
        # makes the reorder safe.
        _mtr_after = {}
        if FORMAT == 'fixed':
            for n in chip_nodes:
                if n['type'] == 'METER' and n.get('inputs'):
                    _mtr_after.setdefault(n['inputs'][0], []).append(n['id'])
        _mtr_ids = {m for v in _mtr_after.values() for m in v}

        for node in chip_nodes:
            # call_sequence keeps its ORIGINAL order. The meter move is done
            # in the emitted chain under #if DSP4_BLOCK_KERNELS instead, so
            # the per-sample image -- which is the shipping one -- keeps both
            # its byte-for-byte content and its node indices, on which
            # DSP4_NODE_LIMIT and the scope-skip table both depend.
            call_sequence.append(node['id'])

            # No-fallback policy: an unknown node type is a hard error here,
            # the same way an unknown cell family is at the contract layer
            # (validate-matrix-contract.py). There used to be a gen_generic
            # stub as the default, which emitted a `/* TODO: implement */`
            # body that assembles and links but silently does nothing -- a
            # typo'd or newly-adopted type produced a running image with a
            # dead node instead of failing the build.
            gen_fn = GENERATORS.get(node['type'])
            if FORMAT == 'fixed':
                gen_fn = FIXED_GENERATORS.get(node['type'], gen_fn)
            if gen_fn is None:
                raise ValueError(
                    f"no {FORMAT} codegen for node type {node['type']!r} "
                    f"(node {node['id']}, chip {node['chip']}, "
                    f"label {node['label']!r}). Unknown node types must fail "
                    f"loudly per the no-fallback policy: add a generator to "
                    f"GENERATORS/FIXED_GENERATORS, or -- if the family is "
                    f"MCU-only and should never reach the DSP -- keep it out "
                    f"of dsp.csv via gen_dsp_csv.py.")

            ramp_line = f'RampProfile: {node["ramp_profile"]}' if node['ramp_profile'] else 'RampProfile: (none)'

            header = HEADER.format(
                label=node['label'],
                node_type=node['type'],
                node_id=node['id'],
                chip=node['chip'],
                ch_count=node['ch_count'],
                spi_page=node['spi_page'],
                spi_addr=node['spi_addr'],
                ramp_line=ramp_line,
            )

            body = gen_fn(node)
            body = add_global_decls(body)
            body = add_extern_decls(body)
            content = header + '\n' + body

            asm_path = os.path.join(nodes_dir, f"{node['id']}.asm")
            # Skip if: not forced AND file exists AND not specifically targeted by type filter
            is_targeted = node_type_filter and node['type'] in node_type_filter
            if not (force or is_targeted) and os.path.exists(asm_path):
                files_skipped += 1
                continue  # preserve manual edits; use --force to overwrite
            with open(asm_path, 'w', encoding='utf-8') as f:
                f.write(content)
            files_written += 1

        # Write process chain
        chain_path = os.path.join(output_dir, chip_label, 'process_chain.asm')
        with open(chain_path, 'w', encoding='utf-8') as f:
            f.write(f'/* {chip_label.upper()} — Processing chain call sequence */\n')
            f.write(f'/* AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly. */\n')
            f.write(f'/* {len(call_sequence)} nodes in processing order */\n\n')
            f.write(f'.section/pm seg_pmco;\n')
            if chip_label == 'chip1':
                f.write(f'.extern _bus_clear_all;\n')
            for nid in call_sequence:
                f.write(f'.extern _{nid}_process;\n')
            f.write(f'#if DSP4_BLOCK_KERNELS\n')
            f.write(f'.extern _scope_inject_blk;\n')
            f.write(f'#endif\n')
            f.write(f'#if DSP4_BLOCK_KERNELS && DSP4_SCOPE_GATE\n')
            f.write(f'.extern _product_id;\n')
            f.write(f'#endif\n')
            f.write(f'.global _{chip_label}_process_all;\n')
            f.write(f'_{chip_label}_process_all:\n')
            if chip_label == 'chip1':
                f.write(f'    call _bus_clear_all;    /* zero all bus accumulators */\n')
            # Two orthogonal knobs on this chain, both default-off.
            #
            # DSP4_NODE_LIMIT is a raw PREFIX cut: 0 runs every node, N
            # runs the first N. It is a bisect tool -- it will happily cut
            # the chain in the middle of a strip, and it removes the bus
            # and send nodes at the tail, so the audio it produces is not
            # meaningful.
            #
            # DSP4_STRIPS keeps the graph FUNCTIONAL: it drops whole
            # channel strips (IN GAIN FILT EQ GATE COMP TUBE DLY FDR RTG)
            # beyond the first N, while keeping every bus, send, cross-in
            # and transfer node. That is what a real-time-at-1x graph
            # needs, because the strips are what the budget cannot afford
            # and the buses are what the signal still has to flow through.
            strip_re = re.compile(
                r'^C\d+_(IN|GAIN|FILT|EQ|GATE|COMP|TUBE|DLY|FDR|RTG)_(\d+)$')

            # Product-scope gating (DSP4_SCOPE_GATE, block-kernel builds).
            # A per-NODE skip table was measured on the part and is a net
            # LOSS: testing a table word before all 431 calls costs more
            # than not calling the 34 scoped ones (2026-08-24, 244,795 vs
            # 243,235 cycles/block). The scoped nodes are contiguous in
            # call order, so gate whole RUNS with one compare and one
            # branch instead -- cost is per run, not per node.
            _SCOPE_IDS = {'D32': 0, 'D24': 1}
            _scope_of = {n['id']: _SCOPE_IDS.get(n['params'].get('scope'))
                         for n in chip_nodes}
            gate_runs = {}          # start idx -> (end idx, scope id, run no)
            _i, _r = 0, 0
            while _i < len(call_sequence):
                sid = _scope_of.get(call_sequence[_i])
                if sid is None:
                    _i += 1
                    continue
                _j = _i
                while (_j + 1 < len(call_sequence)
                       and _scope_of.get(call_sequence[_j + 1]) == sid):
                    _j += 1
                gate_runs[_i] = (_j, sid, _r)
                _r += 1
                _i = _j + 1
            gate_ends = {v[0]: v[2] for v in gate_runs.values()}

            for idx, nid in enumerate(call_sequence):
                if idx in gate_runs:
                    _end, _sid, _rn = gate_runs[idx]
                    f.write('#if DSP4_BLOCK_KERNELS && DSP4_SCOPE_GATE\n')
                    f.write(f'    /* nodes {idx}..{_end} are '
                            f'{"D32" if _sid == 0 else "D24"}-only */\n')
                    f.write('    r2 = dm(_product_id);\n')
                    f.write(f'    r3 = {_sid};\n')
                    f.write('    comp(r2, r3);\n')
                    f.write(f'    if ne jump (pc, .sgrun{_rn}_end);\n')
                    f.write('#endif\n')
                guards = [f'DSP4_NODE_LIMIT == 0 || {idx} < DSP4_NODE_LIMIT']
                m = strip_re.match(nid)
                if m:
                    strip = int(m.group(2)) - 1
                    guards.append(f'DSP4_STRIPS == 0 || {strip} < DSP4_STRIPS')
                f.write('#if (' + ') && ('.join(guards) + ')\n')
                if nid in _mtr_ids:
                    # Per-sample builds call the meter here, at its own chain
                    # index, exactly as they always have.
                    f.write('#if !DSP4_BLOCK_KERNELS\n')
                    f.write(f'    call _{nid}_process;\n')
                    f.write('#endif\n')
                else:
                    f.write(f'    call _{nid}_process;\n')
                f.write(f'#endif\n')
                for _m in _mtr_after.get(nid, []):
                    # ...and block builds call it HERE instead, right after
                    # its source, while that channel's pool slot is still
                    # live. Guarded so the shipping image is unchanged.
                    #
                    # It keeps its ORIGINAL chain index in the NODE_LIMIT
                    # guard. Without that, DSP4_NODE_LIMIT would mean two
                    # different things in the two builds -- and the fabric
                    # measurement, which is exactly NODE_LIMIT 320 versus 0,
                    # would silently start counting meters as strips.
                    _mi = call_sequence.index(_m)
                    f.write('#if DSP4_BLOCK_KERNELS\n')
                    f.write(f'#if (DSP4_NODE_LIMIT == 0 || {_mi} < DSP4_NODE_LIMIT)\n')
                    f.write(f'    call _{_m}_process;\n')
                    f.write('#endif\n')
                    f.write('#endif\n')
                if idx in gate_ends:
                    f.write('#if DSP4_BLOCK_KERNELS && DSP4_SCOPE_GATE\n')
                    f.write(f'.sgrun{gate_ends[idx]}_end:\n')
                    f.write('#endif\n')
                if idx == 0:
                    # Harness stimulus goes in straight after the input
                    # node. Under per-block kernels the input kernel reads
                    # DMA directly, so there is no RX slot variable left to
                    # inject into -- the hook has to sit inside the chain.
                    f.write('#if DSP4_BLOCK_KERNELS\n')
                    f.write('    call _scope_inject_blk;\n')
                    f.write('#endif\n')
            f.write(f'    rts;\n')
            f.write(f'_{chip_label}_process_all.end:\n')
        files_written += 1

        # Write block I/O (scatter/gather between DMA and node slot variables)
        bio_path = os.path.join(output_dir, chip_label, 'block_io.asm')
        with open(bio_path, 'w', encoding='utf-8') as f:
            f.write(bio_text)
        files_written += 1

        lanes_path = os.path.join(output_dir, chip_label, 'lane_config.c')
        with open(lanes_path, 'w', encoding='utf-8') as f:
            f.write(gen_lane_config_c(chip_label, lane_info))
        files_written += 1

        # Write product-scope gate table (consumed by product_config.asm)
        gates_path = os.path.join(output_dir, chip_label, 'scope_gates.asm')
        with open(gates_path, 'w', encoding='utf-8') as f:
            f.write(gen_scope_gates(chip_label, chip_nodes))
        files_written += 1

    # Fixed mode: the bus accumulators become generated (64-bit pairs)
    if FORMAT == 'fixed':
        with open(os.path.join(output_dir, 'bus_accumulators.asm'), 'w',
                  encoding='utf-8') as f:
            f.write(gen_bus_accumulators_fixed())
        files_written += 1
        with open(os.path.join(output_dir, 'poly_tables_fx.asm'), 'w',
                  encoding='utf-8') as f:
            f.write(gen_poly_tables_fixed())
        files_written += 1
        with open(os.path.join(output_dir, 'blk_pool.h'), 'w',
                  encoding='utf-8') as f:
            f.write(gen_blk_pool_header())
        files_written += 1

    # Write ramp infrastructure
    ramp_path = os.path.join(output_dir, 'ramp_engine.asm')
    with open(ramp_path, 'w', encoding='utf-8') as f:
        f.write(gen_ramp_engine())
    files_written += 1

    tables_path = os.path.join(output_dir, 'ramp_tables.asm')
    with open(tables_path, 'w', encoding='utf-8') as f:
        f.write(gen_ramp_tables())
    files_written += 1

    print(f"Generated {files_written} files in {output_dir}")
    if files_skipped:
        print(f"  Skipped {files_skipped} existing node files (use --force to overwrite)")
    print(f"  Chip 1: {len(chip1_nodes)} nodes")
    print(f"  Chip 2: {len(chip2_nodes)} nodes")
    print(f"  + ramp_engine.asm, ramp_tables.asm")

    # Summary of ramp profiles used
    profile_counts = {}
    for n in nodes:
        rp = n['ramp_profile'] or '(none)'
        profile_counts[rp] = profile_counts.get(rp, 0) + 1
    print(f"\n  Ramp profile usage:")
    for rp, cnt in sorted(profile_counts.items()):
        print(f"    {rp}: {cnt} nodes")

    return 0


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Generate SHARC+ ASM skeletons from dsp.csv')
    parser.add_argument('csv', nargs='?', help='Path to dsp.csv')
    parser.add_argument('output', nargs='?', help='Output directory (default: ../src)')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite existing node .asm files (default: skip existing to preserve manual edits)')
    parser.add_argument('--node-type', metavar='TYPE', action='append', dest='node_types',
                        help='Regenerate only nodes of this type (may be specified multiple times, e.g. --node-type GAIN)')
    parser.add_argument('--format', choices=('float', 'fixed'), default='fixed',
                        help='Audio sample-path number format (D5). DEFAULT IS FIXED as of 2026-07-31 (conversion complete); --format float rebuilds the archived FP32 kernels (also tagged float-kernels-2026-07-31)')
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    csv_path = args.csv or os.path.join(script_dir, '..', 'dsp.csv')
    out_dir  = args.output or os.path.join(script_dir, '..', 'src')

    FORMAT = args.format
    globals()['FORMAT'] = args.format
    sys.exit(generate(csv_path, out_dir, force=args.force,
                      node_type_filter=set(args.node_types) if args.node_types else None))
