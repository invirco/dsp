
_COMP_BLK_BODY = """
        #if DSP4_BLOCK_KERNELS
            /* ---- per-block kernel ----
             * Sample 0 goes through the per-sample body with _sample_idx
             * forced to 0, which runs the block-rate makeup ramp and the
             * whole parameter conversion exactly as a per-sample build
             * would -- and avoids duplicating ninety lines of conversion
             * here. Samples 1..BLOCK-1 then run hoisted.
             *
             * THE LOOP COUNT IS DSP4_BLOCK_SIZE-1 AND IT USED TO BE A
             * LITERAL 31. That literal survived the block-size
             * parameterisation (2026-08-28) because it is the only loop
             * count in the generator that was written as a number rather
             * than derived, and nothing downstream could see it: at
             * BLOCK=8 the compressor ran 1+31 = 32 samples of an 8-sample
             * block, reading 32 words from BLK_CHAIN_A and writing 32 to
             * BLK_CHAIN_B -- three slots past the end of each, over
             * BLK_FDR_L/R and BLK_TAP_TRIM. It is what made COMP look
             * BLOCK-INVARIANT (13.5k cycles/block at both block sizes);
             * it was doing the same 32 samples of work either way.
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

            lcntr = DSP4_BLOCK_SIZE-1, do .ckb_lp_{nid} until lce;
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
            lcntr = DSP4_BLOCK_SIZE, do .ckb_cp_{nid} until lce;
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

            lcntr = DSP4_BLOCK_SIZE, do .tkb_lp_{nid} until lce;
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
            lcntr = DSP4_BLOCK_SIZE, do .tkb_cp_{nid} until lce;
                r0 = dm(i3, 1);
            .tkb_cp_{nid}: dm(i4, 1) = r0;
            rts;

        .tkb_ref_{nid}:
            lcntr = DSP4_BLOCK_SIZE, do .tkb_rl_{nid} until lce;
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
            /* CIRCULAR DAG ADDRESSING (review finding D25).
             *
             * The loop this replaces rebuilt BOTH addresses from the base
             * and a modifier on every sample -- two M-register writes, two
             * modify()s, and a compare-and-fixup to wrap the write pointer
             * by hand: seventeen instructions to move two words, on top of
             * the register-to-DAG hazard that an `m0 = r1` immediately
             * followed by a `modify(i0, m0)` costs twice per sample.
             *
             * The DAGs do modulo arithmetic for free. Give the write
             * cursor and the read cursor the same base and the same
             * length and the post-modify wraps in hardware; the two
             * cursors then keep their spacing for the whole block because
             * both advance by one. Five instructions, no M-register write
             * inside the loop, and the pointer arithmetic that is left is
             * per BLOCK.
             *
             * B AND I ARE WRITTEN TOGETHER on this core -- `b0 = x` also
             * loads i0 -- so the base goes down FIRST and the cursor after
             * it, or the offset is lost.
             *
             * Bit-exact by construction: sample k is written at
             * base + (wptr + k) mod max and read from
             * base + (wptr - offset + k) mod max, which is what the hand
             * arithmetic computed, and the write pointer handed back is
             * the same (wptr + BLOCK) mod max. */
            r7 = i0;                    /* delay-line base */
            r1 = dm(i1, 0);             /* write pointer, an OFFSET */
            r5 = r1 - r2;
            if lt r5 = r5 + r3;         /* read index, wrapped */

            m0 = 1;
            l0 = r3;
            b0 = r7;                    /* sets i0 too -- cursor next */
            r6 = r7 + r1;
            i0 = r6;                    /* write cursor */
            m2 = 1;
            l2 = r3;
            b2 = r7;
            r6 = r7 + r5;
            i2 = r6;                    /* read cursor  */

            l3 = 0;
            l4 = 0;
            l5 = 0;
            i3 = BLK_CHAIN_A;
            i4 = BLK_CHAIN_B;
            i5 = BLK_TAP_PREFDR;

            lcntr = DSP4_BLOCK_SIZE, do .dkb_lp_{nid} until lce;
                r0 = dm(i3, 1);
                dm(i0, m0) = r0;        /* write; the DAG wraps it */
                r0 = dm(i2, m2);        /* read;  the DAG wraps it */
                dm(i5, 1) = r0;         /* pre-fader tap */
            .dkb_lp_{nid}: dm(i4, 1) = r0;

            /* the cursor back to an offset, and the DAGs back to LINEAR --
             * a non-zero L left behind would silently make the next node's
             * i0/i2 walk wrap into this delay line. */
            r1 = i0;
            r1 = r1 - r7;
            dm(i1, 0) = r1;
            l0 = 0;
            l2 = 0;
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
            /* GATE RANGE IS DECIBELS ON THE WIRE (review finding D39).
             * The master documents Chan[1-32]GateRng as depth in dB
             * (d32-mx-master.csv, table 0=0/127=60, note "Gate
             * depth/range 0-60dB"). This used to scale the wire float
             * straight by 2^28 and use it as a LINEAR floor, so a host
             * writing the documented 40.0 got 40.0 x 2^28 -- saturated
             * garbage -- and the deepest gate the protocol can ask for
             * produced no attenuation at all. dsp_simulate.py:237 has
             * always performed this conversion, which is what proved the
             * convention was dB before it was ever measured.
             *
             * CELL SEMANTICS ARE THE CONTRACT AND THE MASTERS WIN, so the
             * conversion belongs here: floor = 10^(-dB/20), which is
             * 2^(-dB * log2(10)/20), clamped to the documented 0..60 dB.
             * It is BLOCK RATE -- this whole section sits behind the
             * _sample_idx == 0 guard -- and _exp2q_fx preserves r6-r15 in
             * both its table and polynomial forms, so the live sample in
             * r13 survives the call. */
            f1 = dm(_gate_range_{nid});
            r2 = 0x00000000;              /* 0 dB, documented minimum */
            f2 = r2;
            comp(f1, f2);
            if lt f1 = f2;
            r2 = 0x42700000;              /* 60 dB, documented maximum */
            f2 = r2;
            comp(f1, f2);
            if gt f1 = f2;
            r2 = 0xBE2A152D;              /* -log2(10)/20 */
            f2 = r2;
            f1 = f1 * f2;
            r2 = 0x4C000000;              /* x 2^25 -> Q6.25 for _exp2q_fx */
            f2 = r2;
            f1 = f1 * f2;
            r0 = fix f1;
            call _exp2q_fx;               /* r0 = 2^l, Q4.28 */
            dm(_gate_rngq_{nid}) = r0;
        #if DSP4_PAIRED_GRAPH
            r1 = dm(_gate_hold_{nid});
            dm(_gate_holdq_{nid}) = r1;   /* five consecutive param words */
        #endif

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

            lcntr = DSP4_BLOCK_SIZE, do .gkb_lp_{nid} until lce;
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
            lcntr = DSP4_BLOCK_SIZE, do .gkb_cp_{nid} until lce;
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
            lcntr = DSP4_BLOCK_SIZE, do .gkb_rl_{nid} until lce;
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
             * per-sample reference path a sample at a time.
             *
             * IN PLACE ON BLK_CHAIN_B, like the steady path below and like
             * FILT's two paths (review finding D55, 2026-08-29). This read
             * BLK_CHAIN_A until today, which is only the right slot when
             * FILT happens to be crossfading TOO -- FILT's transient path
             * was the only writer of A. The two crossfades are independent
             * events, so the common case (an EQ band written while the
             * filters sit still) had this node processing the block GAIN
             * read rather than the one it wrote: the whole strip's trim,
             * HPF and LPF vanished for the 576 samples of the fade. Both
             * classes now read and write the same slot on every path, so
             * the four combinations are one case. */
            l3 = 0;
            l4 = 0;
            l5 = 0;
            i3 = BLK_CHAIN_B;
            i4 = BLK_CHAIN_B;
            i5 = BLK_TAP_EQ;
            lcntr = DSP4_BLOCK_SIZE, do .ekb_xl_{nid} until lce;
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
            lcntr = DSP4_BLOCK_SIZE, do .ekb_tp_{nid} until lce;
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
             * staging through the scalar buffers it already uses.
             *
             * IN PLACE ON BLK_CHAIN_B (review finding D55, 2026-08-29).
             * This wrote BLK_CHAIN_A until today, which EQ's transient path
             * then read -- correct only when BOTH were crossfading. With
             * EQ steady, EQ cascaded the stale contents of B and this
             * node's output was dropped on the floor for the 576 samples of
             * the fade. The read and the write walk together, so sample i
             * is consumed before it is overwritten. */
            l3 = 0;
            l4 = 0;
            i3 = BLK_CHAIN_B;
            i4 = BLK_CHAIN_B;
            lcntr = DSP4_BLOCK_SIZE, do .fkb_xl_{nid} until lce;
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
# BLOCK SIZE — the single source of truth for the whole firmware
# ===========================================================================
# Every loop count, DMA ring geometry, slot-array size, per-block ramp step
# and verdict rate in this tree is derived from BLOCK. Nothing downstream
# hardcodes a sample count: the generator emits the DSP4_BLOCK_* macros into
# src/dsp_block.h and hand-maintained sources include that header.
#
# 2026-08-28 (PW ruling): 8 is the working operating point. The block-64
# veto stands; 32 was the operating point until today and every figure in
# the ledger taken before this change is a BLOCK-32 figure.
#
# Latency: the digital path is a small multiple of the block, so halving
# the block halves the path. At 32 the measured pipeline was 93 samples;
# the same ratio at 8 predicts ~23 samples = 0.48 ms at 48 kHz.
#
# BLOCK must be a power of two: spi_handler converts block-rate ramp frame
# counts to samples with a shift, and the DMA 2D geometry wants the ring
# halves aligned.
#
# THE SHIPPING BLOCK SIZE IS 8 (PW ruling 2026-08-28) -- the default in
# the line below, and the only value the repo tree is ever generated at.
# DSP4_GEN_BLOCK overrides it for a SCRATCH tree only (2026-08-29): the
# capacity table has to report ceilings at BLOCK = 8 AND 32, and the block
# size is baked into every generated file, so the 32 tree is generated
# beside the repo's and built with DSP_SRC_DIR rather than by editing this
# constant and regenerating back.
BLOCK = int(__import__('os').environ.get('DSP4_GEN_BLOCK', 8))

BLOCK_SHIFT = BLOCK.bit_length() - 1
assert BLOCK == (1 << BLOCK_SHIFT) and BLOCK >= 2, \
    f'BLOCK must be a power of two >= 2, got {BLOCK}'
BLOCK_HALF = BLOCK // 2
BLOCKS_PER_SEC = 48000.0 / BLOCK

# How often the meters convert their fixed-point state to the float the
# host reads. The MEASUREMENT is every sample of every block; only the
# presentation is rate-limited, because a square root and two float
# converts per meter per block is real money at BLOCK=8 and no display
# needs 6 kHz. 8 gives 750 Hz at BLOCK=8.
MTR_CVT_DIV = 8


def _f32hex(x):
    """IEEE-754 single-precision bit pattern of x, as an ASM hex literal."""
    import struct
    return '0x%08X' % struct.unpack('<I', struct.pack('<f', float(x)))[0]


# ===========================================================================
# Ramp profile definitions (from dsp-def.md §3b)
# ===========================================================================
# Frame period = BLOCK samples / 48000 Hz
FRAME_MS = BLOCK / 48000.0 * 1000.0

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


def comp_par_default(params):
    """CompPar's power-on value: (percent, Q0.31 word).

    THE DEFAULT IS FULLY WET, and it is a contract fix, not a taste
    choice. The blend is `out = dry + par*(wet - dry)`, so par = 0 is a
    compressor that is ON, above threshold and visibly reducing gain in
    `_comp_gain_*` while passing the input through UNCHANGED. Measured on
    the part 2026-08-30 by MW/D32/DSP/SHARC/dcapar.sh, which is kept
    runnable against either image so this has a before: with the old
    default the main bus read 0x03FFFF74 at BOTH a -20 dB and a -55 dB
    threshold, 0 of 32 words differing, while `_comp_gain_C1_COMP_01`
    captured on the same driven graph moved 0x0579F843 -> 0x00444578.
    A default-configured strip's compressor threshold was not an audible
    control at all. With this default the same two thresholds give
    0x015E7DD7 and 0x0011114D, 32 of 32 words differing.

    The masters carry no default for `Chan[1-32]CompPar[1-1]` (review
    finding D59): the row (d32-mx-master.csv) gives Notes "Parallel
    compression blend (dry/wet)", MxDatS 33 and Table
    `0=0/127=100/[Lin]`, and its MxDat
    column -- the one that carries a documented default where the masters
    have one, e.g. EqGain's 60 of 121 -- is EMPTY. So the unit is ruled
    (percent, D40) and the default is not. 100 % is the only value at
    which a compressor left at its defaults behaves like a compressor,
    which is the reading the hub dispatched; that the masters do not
    state it is written up as a PW question rather than hidden here.

    par = 100 % scales to exactly 2^31, which int32 cannot hold, so the
    Q0.31 word saturates to 0x7FFFFFFF -- the same clamp the block-rate
    conversion applies, stated here so the power-on word and the first
    converted word are the same number.
    """
    try:
        pct = float(params.get('parallel', 100))
    except (TypeError, ValueError):
        pct = 100.0
    pct = min(max(pct, 0.0), 100.0)
    q = min(int(round(pct / 100.0 * (1 << 31))), 0x7FFFFFFF)
    return pct, q


def ms_to_frames(ms):
    """Quantize milliseconds to ramp-engine FRAMES: max(1, round(ms / FRAME_MS)).

    A frame is one audio BLOCK, so FRAME_MS moves with BLOCK (0.1667 ms
    at BLOCK=8, 0.6667 at BLOCK=32). MW/D32/DSP/gen_dsp.py imports this
    function rather than restating the arithmetic -- it used to carry its
    own hardcoded 0.667 and baked block-32 frame counts into
    ghost_cells.c (review finding D10).
    """
    if ms <= 0:
        return 0
    return max(1, round(ms / FRAME_MS))


def block_size_guard(what, comment_style='asm'):
    """A build-time #error that fires when a generated file's BAKED,
    generation-time block size disagrees with the dsp_block.h the build
    is using (review finding D12).

    Some generated files cannot express their sizes as macros: array
    extents that the assembler must see as literals, DMA region word
    counts the C side declares, ramp frame counts quantised at
    generation. Those are frozen at GENERATION time. The loop counts,
    pool macros and DMA geometry that WALK them resolve
    DSP4_BLOCK_SIZE at BUILD time. Nothing tied the two together: a
    stale generated tree rebuilt against a fresh dsp_block.h, or a
    hand-edited header, walks 2*DSP4_BLOCK_SIZE over arrays sized for
    the old block -- a silent out-of-bounds DM write with no assembler,
    link or runtime guard. That is the same mechanism the six 08-28
    block-32 literals exploited.

    `what` names what is baked, so the error says which file to look at.
    """
    o, c = ('/*', '*/')
    return '\n'.join([
        f'{o} GENERATION-TIME BLOCK SIZE GUARD (review finding D12).',
        f' * {what}',
        f' * are baked here at GENERATION time from BLOCK={BLOCK}. What walks',
        f' * them resolves DSP4_BLOCK_SIZE at BUILD time. This makes the two',
        f' * disagreeing a build failure instead of an out-of-bounds write. {c}',
        f'#if DSP4_BLOCK_SIZE != {BLOCK}',
        f'#error "STALE GENERATED FILE: baked for DSP4_BLOCK_SIZE={BLOCK}, '
        f'built against a different one. Regenerate: python3 '
        f'tools/dsp/dsp_codegen.py <dsp.csv> <src> --force"',
        '#endif',
        '',
    ])


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
#include "dsp_block.h"
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
                   else ('.var _buf_' + node['id'] + '[DSP4_BLOCK_SIZE];')

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
             * and GATE takes .gkb_below without ever calling _log2q_fx.
             * Profiling on silence therefore measures the cheap path and
             * understates GATE and COMP badly.
             *
             * The stimulus is a full-rate square wave at +/-0.5 (Q4.28
             * 0x08000000 = -6 dBFS). The production read is EXECUTED and
             * then DISCARDED -- deliberately, and the reason is a defect
             * this replaces:
             *
             *   - the production read (`dm(i0, m0)` + the Q1.31 -> Q4.28
             *     shift) still runs, so this path cannot UNDERSTATE the
             *     cost of the node it stands in for;
             *   - but its VALUE is thrown away. An earlier version added
             *     the stimulus to it, which made the stimulus a function
             *     of the input -- and the input is not independent of the
             *     output. On roughly a third of boots the RX word this
             *     kernel reads came back carrying the strip's own signal
             *     at about -0.5 instead of the -1 LSB idle, in antiphase
             *     with the locally generated square, and CANCELLED it:
             *     the strip then ran on silence with BOOT_STAGE 7, a
             *     clean pass rate and clean DMA/SPORT status, i.e. no
             *     indicator except the dynamics witness showed anything
             *     wrong. Caught 2026-08-28 by FILT's captured input word
             *     reading exactly +1 LSB, which requires a pre-add sample
             *     of -0x07FFFFFF. A stimulus must not be a function of
             *     anything the graph it stimulates can influence;
             *   - |x| is CONSTANT at -6 dBFS, which is above the -40 dB
             *     gate threshold and the -20 dB compressor threshold at
             *     every sample, so the envelope never dips back onto a
             *     cheap branch mid-block;
             *   - the sample WORD alternates, so a path that is stuck,
             *     bypassed or reading a stale slot does not look like a
             *     working one. A constant would survive most of those.
             *
             * With the shipping defaults (gate on/-40 dB, comp on/-20 dB,
             * ratio 4, hard knee) the settled witnesses are _gate_gain =
             * 0x10000000 (open) and _comp_gain ~ 0x04C7xxxx (-10.5 dB of
             * gain reduction) -- both only reachable through log2/exp2,
             * so reading them proves the expensive path ran. */
            r5 = DSP4_BLOCK_SIZE;
            r7 = 0x08000000;              /* +0.5 Q4.28 = -6 dBFS */
            lcntr = r5; do .in_sig_{node['id']} until lce;
                r2 = dm(i0, m0);          /* production read, still paid */
                r2 = ashift r2 by -3;     /* production shift, still paid */
                r2 = r7;                  /* DISCARD it -- see above */
                dm(i1, 1) = r2;
        .in_sig_{node['id']}:
                r7 = -r7;                 /* flip sign, |x| unchanged */
            rts;
        #endif
            r5 = DSP4_BLOCK_SIZE;
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
    par_pct, _par_q = comp_par_default(p)
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
        .var _comp_parallel_{node['id']} = {par_pct};   /* PERCENT (D40); fully wet by default (D59) */
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

            /* Parallel blend: out = dry * (1-par) + wet * par.
             * CompPar IS PERCENT ON THE WIRE (review finding D40): the
             * master documents 0=0/127=100, so the 0..1 fraction this
             * blend wants is the written value over 100. Clamped to the
             * documented domain, as the fixed node does. */
            f2 = dm(_comp_parallel_{node['id']});
            r3 = 0x3C23D70A;  /* 1/100 */
            f2 = f2 * f3;             /* percent -> 0..1 */
            r3 = 0x00000000;  /* 0 %, documented minimum */
            comp(f2, f3);
            if lt f2 = f3;
            r3 = 0x3F800000;  /* 1.0 IEEE 754 = 100 %, documented maximum */
            comp(f2, f3);
            if gt f2 = f3;
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
        /* PER-SAMPLE BODY, gated out of block-kernel builds (2026-08-29,
         * program-memory reclamation). Unlike GATE/COMP/EQ/FILT/TUBE, the
         * DLY block kernel has NO fallback into this path -- it handles
         * every slot, offset and wrap case itself and rts's -- so under
         * DSP4_BLOCK_KERNELS this body was unreachable code the linker
         * still had to place: ~212 bytes in each of 32 nodes per chip. */
        #if !DSP4_BLOCK_KERNELS
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
        #endif
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
        /* DCA ASSIGNMENT vs DCA GAIN (review finding D57).
         *
         * `_fdr_dca_sel_` is the CELL: `<Cat>[n]RtgDca[1-1]`, which the
         * masters document as "DCA group assignment (1-8 or off)" with
         * MxDatS 9 -- nine states, no scale law, no unit, the InstantCtl
         * profile of a selector. It is STORED HERE AND MULTIPLIED BY
         * NOTHING. Until 2026-08-30 the wire word landed in
         * `_fdr_dca_gain_` instead and was multiplied straight into the
         * fader coefficient, so a host writing the obvious "no DCA
         * assigned" value of 0 SILENCED the strip with `_fdr_level_`
         * still reading 1.0 -- found on the part when it killed the
         * conformance probe's driven strip three runs running.
         *
         * `_fdr_dca_gain_` stays as the RESOLVED master gain the
         * assignment selects, and is unity because nothing resolves it
         * yet: the eight DCA masters are nodes on CHIP 2 and every
         * channel strip is on CHIP 1, so a chip-1 fader cannot read the
         * master it is assigned to, and whether the DSP should apply DCA
         * gain at all (rather than the host folding it into the fader
         * level it already sends) is a contract question, not a kernel
         * one. Both are in the PW question filed with D57. Nothing but a
         * ruling should write this word. */
        .var _fdr_dca_sel_{node['id']} = 0;     /* 0 = no DCA assigned */
        .var _fdr_dca_gain_{node['id']} = 1.0;  /* resolved master gain */
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
        .var _tx_slot_{node['id']}[DSP4_BLOCK_SIZE];
        #else
        .var _tx_slot_{node['id']};
        #endif

        .section/pm seg_pmco;
        .global _{node['id']}_process;
        _{node['id']}_process:
        #if DSP4_BLOCK_KERNELS
            /* NOTHING TO DO (review finding D25). This body used to copy the
             * source bus block into _tx_slot_{node['id']} so that
             * _gather_chip1 had a named array to read. The gather walks a
             * pointer table, and gen_block_io now points that table straight
             * at _buf_{node['inputs_str']}, so the copy was moving a block to
             * hand the same block over. The slot array above is kept
             * declared -- it is the per-sample build's target and it costs a
             * block-kernel image nothing but DM it no longer touches.
             *
             * The node is NOT removed from the chain: DSP4_NODE_LIMIT counts
             * chain positions, and taking one out would silently renumber
             * every profile point ever recorded against this graph. */
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
        .var _rx_ic_slot_{node['id']}[DSP4_BLOCK_SIZE];
        .var _buf_{node['id']}[DSP4_BLOCK_SIZE];
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
            r5 = DSP4_BLOCK_SIZE;
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
    nid = node['id']
    # WIDE-WORD METERING (PW ruling 2026-08-29), 'scalar' shape. This node
    # is a COPY: there is no accumulator at its tap point and no wider form
    # of the signal exists here, because its producer is an unconverted
    # per-sample node that already stored a rounded Q4.28 word. What it can
    # honestly publish is that same value in the meter's format, which is
    # one arithmetic shift. It costs the meters that read it four bits at
    # the bottom (-144 dB instead of -168) and it does NOT fix their
    # one-sample-per-block decimation -- that is the source's, and it is
    # recorded on the meter node itself.
    mtr = p.get('mtr_sink', '')
    mtr_decl = ('' if not mtr else
                f'        .var _mtr_wide_{nid};\n')
    mtr_pub = ('' if not mtr else
               f'            r1 = ashift r0 by -4;    /* Q4.28 -> Q8.24 */\n'
               f'            dm(_mtr_wide_{nid}) = r1;\n')
    return dedent(f"""\
        /* OUTPUT_TDM: Write to SPORT{p.get('sport_id','?')} slot {p.get('slot_start','?')} */

        .section/dm seg_dmda;
        .var _tx_out_slot_{nid};
        .var _buf_{nid};
{mtr_decl}
        .section/pm seg_pmco;
        .global _{nid}_process;
        _{nid}_process:
            r0 = dm(_buf_{node['inputs_str']});
            dm(_tx_out_slot_{nid}) = r0;
            dm(_buf_{nid}) = r0;
{mtr_pub}            rts;
        _{nid}_process.end:
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
            /* Per-block, with the step INLINED. The source tap is a POOL
             * slot (BLK_CHAIN_B, which is where GAIN writes), live only
             * while this channel's strip is running -- which is why the
             * generator places each meter immediately after its source
             * instead of leaving it at chain index 320+, thirty-one
             * channels too late.
             *
             * THE ARITHMETIC BELOW IS UNCHANGED, deliberately, and that
             * includes its oddities: the new-peak path stores the peak and
             * does NOT update the RMS, so the RMS only advances on the
             * decay path. That is what the shared step did and it is
             * reproduced exactly. The meters have four recorded defects
             * (they read a Q4.28 word as an IEEE float, among others) and
             * whether to fix, decimate or retire them is the hub's decision
             * and still open -- so this changes only how the same
             * arithmetic is REACHED, not what it computes.
             *
             * What the inline removes: a call and an rts on every one of
             * 32 samples x 32 meters = 1,024 invocations per block, plus
             * the two constant reloads, which now sit in f2 and f5 across
             * the whole loop (nothing in the body touches them). Measured
             * 2026-08-27: the meters were 32,324 cycles/block, 37.5 % of
             * the fabric. */
            l2 = 0;
            i2 = BLK_CHAIN_B;
            r2 = 0x3F7FDF3B;          /* 0.9995 IEEE 754, hoisted */
            f2 = r2;
            r5 = 0x3C23D70A;          /* 0.01   IEEE 754, hoisted */
            f5 = r5;
            lcntr = DSP4_BLOCK_SIZE, do .mtrk_{node['id']} until lce;
                r0 = dm(i2, 1);
                f0 = abs f0;
                f1 = dm(_mtr_peak_{node['id']});
                comp(f0, f1);
                if le jump (pc, .mtrd_{node['id']});
                dm(_mtr_peak_{node['id']}) = f0;
                jump (pc, .mtrk_{node['id']});
            .mtrd_{node['id']}:
                f1 = f1 * f2;                     /* peak *= 0.9995 */
                dm(_mtr_peak_{node['id']}) = f1;
                f3 = dm(_mtr_rms_{node['id']});
                f4 = f0 * f0;                     /* x^2 */
                f6 = f4 - f3;
                f6 = f5 * f6;
                f3 = f3 + f6;
                dm(_mtr_rms_{node['id']}) = f3;
            .mtrk_{node['id']}:
                nop;
            rts;
        #else
            /* Read source tap */
            r0 = dm(_buf_{node['inputs_str']});
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
        #endif
        _{node['id']}_process.end:
    """)


# Which pool slot a meter's SOURCE publishes its block into. This is a
# fact about the source node's block kernel, not a guess:
#   GAIN       -- gen_gain_fixed writes BLK_TAP_TRIM (the post-trim tap)
#   FADER_PAN  -- gen_fader_pan_fixed writes its mono result to BLK_CHAIN_A
# Any other source publishes no block, and the meter falls back to the
# scalar _buf_ of its source: ONE sample per block, correctly converted,
# instead of the whole block. That is a real limitation and it is NOT
# hidden -- the generated node says so and it is recorded in tasks.md.
#
# It is still a repair. Before 2026-08-28 every meter read BLK_CHAIN_B
# unconditionally, and on chip 2 that is not its source at all: FADER_PAN
# READS BLK_CHAIN_B and writes BLK_CHAIN_A, and OUTPUT_TDM and
# COMPRESSOR do not touch the pool. Twenty-one chip-2 meters were
# metering another node's signal.
_METER_SRC_BLOCK = {
    'GAIN': 'BLK_TAP_TRIM',
    'FADER_PAN': 'BLK_CHAIN_A',
}


# ---------------------------------------------------------------------------
# WIDE-WORD METERING (PW ruling 2026-08-29 ~17:05)
#
# Every meter taps the SIGNAL'S WIDE FORM at its tap point -- the
# most-significant 32-bit word of the accumulator that produced it, which is
# the Q8.24 view of an unrounded, unsaturated Q4.28xQ4.28 product -- and never
# a rounded/saturated 32-bit store made for the meter's benefit. Truncation is
# fine for metering; the ABSENCE OF SATURATION is the point, because a meter
# that saturates with the signal cannot show over-range at all.
#
# TWO SHAPES, and which one a meter gets is a fact about its SOURCE, not a
# preference:
#
#   'acc'    -- the source's tap point is a live MAC accumulator (GAIN's
#               trim product, FADER_PAN's level product). The meter's three
#               per-sample instructions move INTO the source's block loop and
#               read mr1b in-register; the source hands the block's finished
#               accumulators to the meter through _mtr_acc_<meter>, five words
#               ONCE PER BLOCK. Nothing rounded is stored for the meter and
#               nothing is stored per sample.
#
#   'scalar' -- the source has no accumulator at the tap point at all: chip
#               2's OUTPUT_TDM is a copy and its COMPRESSOR finishes in the
#               ALU, and both are unconverted per-sample nodes that publish
#               one word per block. The wide form there IS that word, so the
#               source publishes _mtr_wide_<src> = ashift(x, -4): the same
#               value in the meter's Q8.24 format, at the same tap point. It
#               costs those meters four bits at the BOTTOM (-144 dB instead of
#               -168) and it does not fix their one-sample-per-block
#               decimation, which is a property of the unconverted source and
#               is recorded, not hidden.
#
# THE METER'S INPUT FORMAT IS Q8.24 EVERYWHERE. _mtr_fold's block mean square
# and its peak conversion are derived from that one fact (meter_fx.asm), and
# fixed_ref.meter_block takes Q8.24 samples for the same reason.
_MTR_WIDE_ACC = ('GAIN', 'FADER_PAN')


def _mtr_acc_flush(meter_id):
    """Hand a block's meter accumulators to the meter node. Five words at
    BLOCK rate, against BLOCK rounded stores it replaces.

    SHARED (lib/meter_fx.asm::_mtr_flush) rather than inlined: 38 copies
    of eight instructions is 1,368 bytes of a chip 1 that has under two
    thousand left, and this is block-rate code."""
    return (f'            r0 = _mtr_acc_{meter_id};\n'
            f'            call _mtr_flush;')


def gen_meter_fixed(node):
    """METER — rebuilt in-kernel 2026-08-28, moved onto the WIDE WORD
    2026-08-29 (PW rulings).

    NORMATIVE REFERENCE: fixed_ref.meter_block, which now takes Q8.24
    samples. The meter no longer reads a stored Q4.28 block at all: see
    the _MTR_WIDE_ACC note above for the two shapes and why each source
    gets the one it gets.
    """
    nid = node['id']
    src = node['inputs_str']
    mode = node['params'].get('mtr_wide_mode', 'scalar')

    if mode == 'acc':
        blk_body = dedent(f"""\
            /* WIDE WORD, 'acc' shape. {src} accumulated this block's peak,
             * trough and exact sum of squares from the MS word of its own
             * product register, inside its own loop, and left them here.
             * There is no per-sample work in this node at all and nothing
             * rounded was stored anywhere on the way.
             *
             * The load and the fold are ONE SHARED ROUTINE
             * (lib/meter_fx.asm::_mtr_load_fold): eleven instructions in
             * each of 32 meter nodes is 2,112 bytes, and chip 1 has under
             * two thousand left. */
            r0 = _mtr_peak_{nid};
            r1 = _mtr_acc_{nid};
            call _mtr_load_fold;
            rts;""")
        note_ps = (f'_mtr_wide_{src}, the Q8.24 word {src} publishes '
                   f'from its\n             * product register before it '
                   f'rounds or saturates.')
        blk_tail = ''
    else:
        blk_body = dedent(f"""\
            /* WIDE WORD, 'scalar' shape. {src} has no accumulator at this
             * tap point -- it is an unconverted per-sample node -- so it
             * publishes the same value in the meter's Q8.24 format and this
             * node walks it. RECORDED LIMITATION, unchanged by the wide-word
             * work: {src} produces ONE word per block under
             * DSP4_BLOCK_KERNELS, so this meter still sees one sample per
             * block. Fixing that means block-converting the SOURCE. */
            l2 = 0;
            m2 = 0;
            i2 = _mtr_wide_{src};
            r8 = 0x80000000;              /* running max: most negative */
            r9 = 0x7FFFFFFF;              /* running min: most positive */
            mrf = 0;
            lcntr = DSP4_BLOCK_SIZE, do .mtrk_{nid} until lce;
                r0 = dm(i2, m2);
                r8 = max(r8, r0);
                mrf = mrf + r0 * r0 (ssi);
            .mtrk_{nid}:
                r9 = min(r9, r0);
            r0 = _mtr_peak_{nid};""")
        note_ps = (f'_mtr_wide_{src}, the Q8.24 word {src} publishes.')
        blk_tail = ('        #if !DSP4_MTR_NOFOLD\n'
                    '            call _mtr_fold;\n'
                    '        #endif\n'
                    '            rts;')

    return dedent(f"""\
        /* METER: level read-back (DSP writes, host polls) */
        /* SPI page={node['spi_page']} addr={node['spi_addr']} */

        #include "blk_pool.h"

        .section/dm seg_dmda;
        /* ORDER IS LOAD-BEARING: _mtr_fold takes the address of
         * _mtr_peak_{nid} and reaches the rest by offset. The three float
         * words keep their names and their SPI dispatch entries. */
        .var _mtr_peak_{nid} = 0.0;      /* +0 linear peak, host contract */
        .var _mtr_rms_{nid} = 0.0;       /* +1 linear TRUE rms            */
        .var _mtr_gr_{nid} = 0.0;        /* +2 gain reduction -- see below */
        .var _mtr_st_{nid}[4];           /* +3 pk_lo pk_hi ms_lo ms_hi     */
        /* The block accumulators. FIVE words, not four: the sum of Q8.24
         * squares is Q16.48 and a block of them overruns 64 bits, so mr2f
         * is state and not a sign extension. Filled by {src} under block
         * kernels and by this node's own per-sample body otherwise. */
        .var _mtr_acc_{nid}[5];          /* mx mn ssq_lo ssq_hi ssq_ex     */

        .section/pm seg_pmco;
        .extern _mtr_fold;
        .extern _mtr_load_fold;
        .extern _sample_idx;
        .extern _mtr_wide_{src};
        .global _{nid}_process;
        _{nid}_process:
        #if DSP4_MTR_OFF
            /* measurement only: what the meter costs, by removing it */
            rts;
        #elif DSP4_BLOCK_KERNELS
{blk_body}
{blk_tail}
        #else
            /* Per SAMPLE. The block accumulators live in DM because there
             * is no loop to hold them in registers, and the fold fires on
             * the last sample of the block -- so both paths run the SAME
             * arithmetic and the same reference covers both.
             *
             * Source: {note_ps} */
            r0 = dm(_mtr_wide_{src});
            r4 = dm(_sample_idx);
            r1 = 0;
            comp(r4, r1);
            if ne jump (pc, .mtacc_{nid});
            /* first sample of the block: seed rather than accumulate */
            dm(_mtr_acc_{nid} + 0) = r0;
            dm(_mtr_acc_{nid} + 1) = r0;
            mrf = 0;
            mrf = mrf + r0 * r0 (ssi);
            r2 = mr0f;
            dm(_mtr_acc_{nid} + 2) = r2;
            r2 = mr1f;
            dm(_mtr_acc_{nid} + 3) = r2;
            r2 = mr2f;
            dm(_mtr_acc_{nid} + 4) = r2;
            rts;
        .mtacc_{nid}:
            r2 = dm(_mtr_acc_{nid} + 0);
            r2 = max(r2, r0);
            dm(_mtr_acc_{nid} + 0) = r2;
            r2 = dm(_mtr_acc_{nid} + 1);
            r2 = min(r2, r0);
            dm(_mtr_acc_{nid} + 1) = r2;
            r2 = dm(_mtr_acc_{nid} + 2);
            mr0f = r2;
            r3 = dm(_mtr_acc_{nid} + 3);
            mr1f = r3;
            r2 = dm(_mtr_acc_{nid} + 4);
            mr2f = r2;
            mrf = mrf + r0 * r0 (ssi);
            r2 = mr0f;
            dm(_mtr_acc_{nid} + 2) = r2;
            r2 = mr1f;
            dm(_mtr_acc_{nid} + 3) = r2;
            r2 = mr2f;
            dm(_mtr_acc_{nid} + 4) = r2;
            r1 = DSP4_BLOCK_SIZE - 1;
            comp(r4, r1);
            if ne rts;
            r8 = dm(_mtr_acc_{nid} + 0);
            r9 = dm(_mtr_acc_{nid} + 1);
            r0 = _mtr_peak_{nid};
            call _mtr_fold;
            rts;
        #endif
        _{nid}_process.end:

        /* _mtr_gr_{nid} IS STILL NOT WRITTEN, and that is recorded defect
         * 4. It is not a numerics bug: the meter's `taps` parameter names
         * gate_gr and comp_gr but dsp.csv carries no ids for them, so
         * there is nothing to read without inventing a naming convention
         * between MTR_nn and GATE_nn. That belongs in the mx26 contract,
         * not here. The word stays declared and zero. */
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
    lines.append(f'/* Frame period: {BLOCK} samples @ 48 kHz = {FRAME_MS:.4f} ms */')
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
    lines.append(f'/* Frame period: {FRAME_MS:.4f} ms ({BLOCK} samples @ 48 kHz) */')
    lines.append('')
    lines.append('#include "dsp_block.h"')
    lines.append('')
    lines.append(block_size_guard(
        'The up/down FRAME counts below -- a frame is one BLOCK, so each\n'
        ' * is ms / (BLOCK / 48000), quantised at generation --'))
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
    Each scatter/gather takes r0 = sample index (0..BLOCK-1).
    """

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

    def emit_tables(lines, prefix, nodes_ordered, per_node, extern_fmt, var_fmt,
                    blk_sym=None):
        """blk_sym(node) -> the symbol the pointer table should hold under
        per-block kernels, when that differs from the per-sample one. Used to
        point the inter-chip gather straight at the bus buffers (D25)."""
        n = len(nodes_ordered)
        for node in nodes_ordered:
            lines.append(f'.extern {extern_fmt.format(id=node["id"])};')
        if blk_sym:
            lines.append('#if DSP4_BLOCK_KERNELS')
            for node in nodes_ordered:
                lines.append(f'.extern {blk_sym(node)};')
            lines.append('#endif')
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
        if blk_sym:
            lines.append('#if DSP4_BLOCK_KERNELS')
            lines.append(f'.var {var_fmt}[{n}] =')
            for i, node in enumerate(nodes_ordered):
                comma = ',' if i < n - 1 else ';'
                lines.append(f'    {blk_sym(node)}{comma}')
            lines.append('#else')
            lines.append(f'.var {var_fmt}[{n}] =')
            for i, node in enumerate(nodes_ordered):
                comma = ',' if i < n - 1 else ';'
                lines.append(f'    {extern_fmt.format(id=node["id"])}{comma}')
            lines.append('#endif')
        else:
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

    def emit_meter_scan(lines, fn, count, ptr_tbl, what, dead_under_block=False):
        lines.append(f'/* Peak-hold meter scan over {what} (once per block) */')
        lines.append(f'.global {fn};')
        lines.append(f'{fn}:')
        if dead_under_block:
            # Review finding D14. The scan reads the RX SLOT variables, and
            # under per-block kernels nothing writes them: _scatter_chip1
            # returns immediately (the INPUT_TDM kernels read the DMA buffer
            # themselves) and the slot vars stay at their reset value for the
            # life of the image. The scan therefore folded 46 zeros into
            # _meter_peaks every block -- about 500 cycles to compute a
            # result that was already frozen.
            #
            # DELETING IT CHANGES NO VALUE THE HOST CAN SEE, and that is the
            # whole justification: the legacy input peaks are ALREADY dead in
            # a block-kernel image, they are not being killed here. What
            # replaces them is the rebuilt METER node on each strip's
            # post-trim signal (src/lib/meter_fx.asm), which measures every
            # sample of every block. Re-animating the legacy array would mean
            # giving the INPUT_TDM kernels a running max, which is ADDING
            # per-sample work to feed a superseded read-back -- a decision
            # for the meter ruling, not for an efficiency batch.
            lines.append('#if DSP4_BLOCK_KERNELS')
            lines.append('    rts;')
            lines.append('#endif')
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
    lines.append('#include "dsp_block.h"')
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
        # Review finding D25. Under per-block kernels each INTERCHIP_SEND
        # node existed only to COPY its source bus block into a private
        # _tx_slot array so that the gather had a named place to read --
        # 37 nodes x 2 memory operations x BLOCK, plus 37 call/rts, for a
        # copy that changes nothing. The gather already walks a POINTER
        # table, so it can point at the bus buffer itself. The send bodies
        # then have nothing left to do and return immediately.
        #
        # SAFE BECAUSE THE BUS BUFFERS ARE PRIVATE, not pool slots: nothing
        # between the bus node and the gather writes _buf_<bus>, so the
        # gather reads exactly the words the copy would have handed it.
        lines.append('/* D25: under block kernels these point at the SOURCE bus')
        lines.append(' * buffers, and the INTERCHIP_SEND bodies are empty. */')
        emit_tables(lines, '_c1_ic_tx', send_nodes, ic_map,
                    '_tx_slot_{id}', '_c1_ic_tx_ptrs',
                    blk_sym=lambda nd: f'_buf_{nd["inputs_str"]}')

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
                        '_c1_rx_slot_ptrs', 'RX inputs', dead_under_block=True)
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
    out = []
    out.append(f'/* lane_config.c — generated lane tables + DMA buffers for {chip_label.upper()} */')
    out.append('/* AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly. */')
    out.append('/* Entries of 4: sport, cs_mask, words_per_sample, region_off. */')
    out.append('')
    out.append('#include "dsp_block.h"')
    out.append('')
    out.append(block_size_guard(
        'The lane region_off values below (count * BLOCK) and the\n'
        ' * region_words / DMA ping-pong buffer extents (lane total * BLOCK)'))
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
    # bypass = identity: b0=1.0 -> 0x10000000; n1=2.0 stored HALVED as
    # nh=1.0 in Q5.27 -> 0x10000000 (PW ruling 2026-08-29);
    # n2=-1.0 -> -0x10000000; c1=2.0; c2=1.0 (a1=0,a2=0)
    bypass = ', '.join(['0x10000000, 0x10000000, 0xF0000000, 0x20000000, 0x10000000'] * bands)
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
{_xfade_blend_core('eq', nid)}
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
        ['0x10000000, 0x10000000, 0xF0000000, 0x20000000, 0x10000000'] * stages)


def _xfade_blend_core(pfx, nid):
    """THE dual-instance crossfade blend, emitted from one place.

    In:  r0 = new instance output, r14 = old, both Q4.28
         _{pfx}_xfade_alpha_{nid} = the float control ramp
    Out: r0 = blended sample.  Clobbers r4, r5, r12, f4, f5, MRF.

    Normative model: fixed_ref.xfade_blend. Boundary vectors and the
    negative control live in golden_harness.t_blend_boundary, and the
    in-part bit-exactness proof (lib/num_selftest.asm) calls a routine
    generated from THIS function, so the tested instructions and the
    shipped instructions are the same text.
    """
    return """\
            f4 = dm(_{pfx}_xfade_alpha_{nid});
            r5 = 0x4F000000;               /* 2^31 as float */
            f5 = r5;
            f4 = f4 * f5;
            r4 = fix f4;                   /* alpha_q31; `fix` saturates */
            /* alpha*(new - old) as TWO MACs into the 80-bit MRF, so the
             * difference is NEVER formed in a 32-bit register (review
             * finding D3). `new` and `old` are independently saturated
             * Q4.28 outputs, so new-old spans +/-(2^32-1) and the old
             * `r5 = r0 - r14` wrapped when the two instances straddled
             * full scale mid-swap -- up to a block of full-scale-wrong
             * samples, a click. Same instruction count, and identical
             * arithmetic everywhere the subtract did not wrap.
             * Model: fixed_ref.xfade_blend. The final add cannot
             * overflow -- the result is a convex combination of two
             * int32s, bounded by them; the bound is in numeric-spec.md.
             *
             * EMITTED FROM ONE PLACE: _xfade_blend_core() in
             * dsp_codegen.py. Every EQ/GEQ/AFB/FILT/CROSSOVER node and
             * the in-part self-test (lib/num_selftest.asm) get these
             * exact instructions from this one expression, so the
             * sequence the self-test proves bit-exact against the model
             * is the sequence the nodes run. */
            mrf = r0 * r4 (ssi);           /* + new*alpha */
            mrf = mrf - r14 * r4 (ssi);    /* - old*alpha */
            r5 = 0x40000000;               /* 2^30 rounding half */
            r12 = 1;
            mrf = mrf + r5 * r12 (ssi);
            r5 = mr0f;
            r12 = mr1f;
            r5 = lshift r5 by -31;
            r12 = lshift r12 by 1;
            r5 = r5 or r12;
            r0 = r14 + r5;                 /* blended output */""".format(pfx=pfx, nid=nid)


def _fx_blend_asm(pfx, nid):
    """Fixed blend: r0 = old(r7) + rns((new(r0)-old)*alpha_q31, 31);
    advances alpha and finishes the crossfade. Emitted inside a node."""
    return f"""\
{_xfade_blend_core(pfx, nid)}"""


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
    byp = '0x10000000, 0x10000000, 0xF0000000, 0x20000000, 0x10000000'
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
{_xfade_blend_core('filt', nid)}
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
    byp10 = ('0x10000000, 0x10000000, 0xF0000000, 0x20000000, 0x10000000, '
             '0x10000000, 0x10000000, 0xF0000000, 0x20000000, 0x10000000')
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
{_xfade_blend_core('xover', nid)}
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
{_xfade_blend_core('xover', nid)}
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



_GAIN_BLK_COMMON = """\
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
             * words off the end of it.
             *
             * THIS STORE IS NOT THE METER'S (PW ruling 2026-08-29). It
             * survives the wide-word rework because the ROUTER reads it --
             * pickoff 0, post-trim -- and the router needs a Q4.28 sample.
             * The ruling's "kill every tap store whose only consumer is a
             * meter" therefore kills nothing on this node, and D20's
             * -17 c/s/strip stays blocked on the GAIN->FILT coefficient
             * fold rather than on the meter. Stated, not glossed. */
            i4 = BLK_TAP_TRIM;
"""


_GAIN_BLK_FUSED = """\
        #if DSP4_STRIP_FUSED
            /* FUSED (2026-08-28): the same seventeen instructions, two
             * samples at a time, interleaved, the second accumulating in
             * MRB so even the MAC pair does not serialise.
             *
             * SIZE THIS HONESTLY. The 2026-08-28 baseline measures this
             * node at 17.7 cycles/sample for seventeen instructions, i.e.
             * the loop already issues at about one instruction per cycle
             * and there are no stalls left to hide. Interleaving buys the
             * loop bookkeeping and nothing else -- one cycle/sample, at
             * most. It is here because it is free and bit-exact, not
             * because it is the lever.
             *
             * Nothing about the ARITHMETIC changes -- same operations,
             * same order within a sample, same single rounding -- so this
             * is bit-exact by construction, not by tolerance.
             *
             * comp/conditional-move pairs are kept ADJACENT: the condition
             * reads ASTAT from the last flag-setting instruction, so an
             * interleaved shift between a comp and its `if ne` would move
             * on stale flags. */
            r5 = DSP4_BLOCK_HALF;
            lcntr = r5; do .gk_lp_{nid} until lce;
                r0 = dm(i0, 1);                   /* xA */
                r3 = dm(i0, 1);                   /* xB */
                mrf = r0 * r1 (ssi);
                mrb = r3 * r1 (ssi);
                mrf = mrf + r6 * r7 (ssi);
                mrb = mrb + r6 * r7 (ssi);
                r8 = mr0f;
                r12 = mr0b;
                r2 = mr1f;
                r4 = mr1b;
                r8 = lshift r8 by -28;
                r12 = lshift r12 by -28;
                r9 = lshift r2 by 4;
                r13 = lshift r4 by 4;
                r0 = r8 or r9;                    /* yA candidate */
                r3 = r12 or r13;                  /* yB candidate */
                r8 = ashift r2 by -28;
                r12 = ashift r4 by -28;
                r9 = ashift r0 by -31;
                r13 = ashift r3 by -31;
                r11 = ashift r2 by -31;
                r14 = ashift r4 by -31;
                r11 = r10 xor r11;
                r14 = r10 xor r14;
                comp(r8, r9);
                if ne r0 = r11;                   /* yA saturated */
                comp(r12, r13);
                if ne r3 = r14;                   /* yB saturated */
                dm(i1, 1) = r0;
                dm(i4, 1) = r0;                   /* post-trim tap block */
                dm(i1, 1) = r3;
        .gk_lp_{nid}:
                dm(i4, 1) = r3;
            dm(_tap_post_trim_{nid}) = r3;   /* linkage scalars */
            dm(_buf_{nid}) = r3;
            rts;
        #else
            r5 = DSP4_BLOCK_SIZE;
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
                dm(i4, 1) = r0;
            dm(_tap_post_trim_{nid}) = r0;   /* linkage scalars */
            dm(_buf_{nid}) = r0;
            rts;
        #endif
"""


_GAIN_BLK_METERED = """\
            /* WIDE-WORD METER, INLINE (PW ruling 2026-08-29). This node's
             * meter no longer walks a stored block: it accumulates the MS
             * word of THIS MAC, in register, before the rounding half is
             * added and before the saturation fix-up runs.
             *
             *     r12 = mr1b   is the Q8.24 view of x*g -- sign, the full
             *                  over-range the 32-bit store cannot hold,
             *                  and 24 fractional bits (-144 dB).
             *
             * THE AUDIO MAC MOVED TO MRB so MRF can carry the meter's
             * exact sum of squares across the whole block. That is also
             * why this node does not use the STRIP_FUSED two-at-a-time
             * loop when it feeds a meter: fusion needs both accumulators
             * for two audio samples and there is no third. The audio
             * arithmetic is bit-identical either way, and the fused loop's
             * own comment sizes the interleave at one cycle/sample at most.
             *
             * Cost: four instructions per sample HERE, against four per
             * sample plus the block loads, the call and the pointer setup
             * that the meter node no longer runs. */
            r13 = 0x80000000;                 /* block max: most negative */
            r15 = 0x7FFFFFFF;                 /* block min: most positive */
            mrf = 0;                          /* exact sum of squares     */
            /* ONE SAMPLE BEHIND, and that is what makes it free. Reading
             * mr1b in the instruction after the MAC that produced it
             * stalls on the multiplier's result latency, and the first cut
             * of this loop measured +25.5 cycles/sample/strip at BLOCK 8
             * against a fused loop with a separate meter node -- three
             * instructions of arithmetic paying for themselves several
             * times over in stalls. The meter's three ops therefore run on
             * the PREVIOUS sample's wide word while the current MAC is in
             * flight, and the last sample's are done after the loop.
             *
             * Seeding r12 = 0 is EXACTLY neutral, not approximately: zero
             * adds nothing to the sum of squares, and the block peak is
             * max(hi, -lo) which is non-negative already, so widening the
             * range by a zero cannot move it. */
            r12 = 0;
            r5 = DSP4_BLOCK_SIZE;
            lcntr = r5; do .gk_lp_{nid} until lce;
                r0 = dm(i0, 1);
                mrb = r0 * r1 (ssi);
                r13 = max(r13, r12);          /* meter, one sample behind */
                mrf = mrf + r12 * r12 (ssi);
                r15 = min(r15, r12);
                r12 = mr1b;                   /* WIDE post-trim, Q8.24 */
                mrb = mrb + r6 * r7 (ssi);
                r8 = mr0b;
                r2 = mr1b;
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
                dm(i4, 1) = r0;
            dm(_tap_post_trim_{nid}) = r0;   /* linkage scalars */
            dm(_buf_{nid}) = r0;
            /* the last sample's meter ops, outside the loop */
            r13 = max(r13, r12);
            mrf = mrf + r12 * r12 (ssi);
            r15 = min(r15, r12);
{flush}
            rts;
"""


def gen_gain_fixed(node):
    """Fixed GAIN (D5): float control plane unchanged (ramp quad stays
    float, spec revision 2026-07-31); the coefficient converts to Q4.28
    once per block; the sample path is one MAC + rns + saturate.

    Where this node feeds a METER the sample path also carries the meter's
    three instructions on the WIDE word (PW ruling 2026-08-29) -- see
    _GAIN_BLK_METERED."""
    p = node['params']
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    mtr = p.get('mtr_sink', '')
    if mtr:
        # DSP4_MTR_OFF still means "what do the meters cost": with the
        # accumulation living inside this loop, removing the meter node
        # alone would have measured nothing. The preprocessor picks one
        # body, so carrying both costs the image nothing.
        blk_body = (_GAIN_BLK_COMMON
                    + '        #if DSP4_MTR_OFF\n'
                    + _GAIN_BLK_FUSED.format(nid=nid)
                    + '        #else\n'
                    + _GAIN_BLK_METERED.format(
                        nid=nid, flush=_mtr_acc_flush(mtr))
                    + '        #endif\n')
        mtr_decl = (
            '        /* The Q8.24 word the PER-SAMPLE path publishes for\n'
            '         * ' + mtr + '. The block path never stores it -- it hands\n'
            '         * the finished accumulators over instead. */\n'
            '        .var _mtr_wide_' + nid + ';\n')
        mtr_extern = ('        .extern _mtr_acc_' + mtr + ';\n'
                      '        .extern _mtr_flush;\n')
        mtr_pub = (
            '            r12 = mr1f;                           '
            '/* WIDE post-trim, Q8.24 */\n'
            '            dm(_mtr_wide_' + nid + ') = r12;\n')
    else:
        blk_body = _GAIN_BLK_COMMON + _GAIN_BLK_FUSED.format(nid=nid)
        mtr_decl = ''
        mtr_extern = ''
        mtr_pub = ''
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
{mtr_decl}
        .section/pm seg_pmco;
        .extern _sample_idx;
        .extern _mrf_rns28;
{mtr_extern}        .global _{nid}_process;
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
             * by DSP4_BLOCK_SIZE, which is right for the ramps that
             * decrement once per SAMPLE. This one decrements once per
             * BLOCK, so taking 1 per block ran it BLOCK times long:
             * measured 2026-08-23 at BLOCK=32, a GainSafe down-ramp took
             * 960 ms against the 30 ms its own cell table specifies, and a
             * GainFast fader move took 85 ms instead of 3 ms. A power of
             * two is exact in binary, so scaling the step loses nothing. */
            r5 = DSP4_BLOCK_SIZE;
            r4 = r4 - r5;
            dm(_gain_frames_{nid}) = r4;
            f1 = dm(_gain_coeff_{nid});
            f2 = dm(_gain_step_{nid});
            r5 = DSP4_BLOCK_F32;              /* BLOCK_SIZE as float */
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
{blk_body}
        #else
        .apply_{nid}:
            /* Pure MAC. Polarity and mute are already inside _gain_q. */
            r0 = dm(_buf_{inp});
            r1 = dm(_gain_q_{nid});
            mrf = r0 * r1 (ssi);
{mtr_pub}            call _mrf_rns28;                      /* r0 = sat(rns(x*g,28)) */

            dm(_tap_post_trim_{nid}) = r0;
            dm(_buf_{nid}) = r0;
            rts;
        #endif
        _{nid}_process.end:
    """)


_FDR_BLK_METERED = """\
            /* WIDE-WORD METER, INLINE (PW ruling 2026-08-29). See GAIN's
             * copy of this note: the meter accumulates the MS word of this
             * node's own product, in register, unrounded and unsaturated,
             * and hands the finished block accumulators to the meter node
             * five words at a time. */
            r13 = 0x80000000;                 /* block max: most negative */
            r15 = 0x7FFFFFFF;                 /* block min: most positive */
            mrf = 0;                          /* exact sum of squares     */
            /* i4 carries the accumulator hand-over below and this node's
             * block preamble sets l0-l3 only. A stale l4 would make that a
             * CIRCULAR write. */
            l4 = 0;
            /* One sample behind, for the multiplier-latency reason written
             * out in GAIN's copy of this loop. r6 = 0 is exactly neutral. */
            r6 = 0;
            r14 = DSP4_BLOCK_SIZE;
            lcntr = r14; do .fdr_lp_{nid} until lce;
                r0 = dm(i0, 1);
                mrb = r0 * r1 (ssi);
                r13 = max(r13, r6);           /* meter, one sample behind */
                mrf = mrf + r6 * r6 (ssi);
                r15 = min(r15, r6);
                r6 = mr1b;                    /* WIDE post-fader, Q8.24 */
                mrb = mrb + r7 * r12 (ssi);
                r8 = mr0b;
                r2 = mr1b;
                r8 = lshift r8 by -28;
                r9 = lshift r2 by 4;
                r0 = r8 or r9;
                r8 = ashift r2 by -28;
                r9 = ashift r0 by -31;
                r11 = ashift r2 by -31;
                r11 = r10 xor r11;
                comp(r8, r9);
                if ne r0 = r11;
        .fdr_lp_{nid}:
                dm(i1, 1) = r0;
            dm(_tap_post_fader_{nid}) = r0;   /* linkage scalars */
            dm(_buf_{nid}) = r0;
            /* the last sample's meter ops, outside the loop */
            r13 = max(r13, r6);
            mrf = mrf + r6 * r6 (ssi);
            r15 = min(r15, r6);
{flush}
            rts;
"""


_FDR_BLK_PAIR = """\
        #if DSP4_STRIP_FUSED
            /* FUSED (2026-08-28): two samples per iteration, interleaved,
             * second accumulator in MRB -- the same treatment as GAIN.
             * The bigger change here is the LOOP: the unfused body is a
             * manual counter with a branch at the bottom, which a
             * hardware loop replaces outright. The pan legs are already
             * gone (the 08-25 crosspoint fold), so the body really is one
             * MAC per sample. Identical arithmetic, so bit-exact by
             * construction. */
            r14 = DSP4_BLOCK_HALF;
            lcntr = r14; do .fdr_lp_{nid} until lce;
                r0 = dm(i0, 1);                 /* xA */
                r3 = dm(i0, 1);                 /* xB */
                mrf = r0 * r1 (ssi);
                mrb = r3 * r1 (ssi);
                mrf = mrf + r7 * r12 (ssi);
                mrb = mrb + r7 * r12 (ssi);
                r8 = mr0f;
                r5 = mr0b;
                r2 = mr1f;
                r4 = mr1b;
                r8 = lshift r8 by -28;
                r5 = lshift r5 by -28;
                r9 = lshift r2 by 4;
                r6 = lshift r4 by 4;
                r0 = r8 or r9;                  /* yA candidate */
                r3 = r5 or r6;                  /* yB candidate */
                r8 = ashift r2 by -28;
                r5 = ashift r4 by -28;
                r9 = ashift r0 by -31;
                r6 = ashift r3 by -31;
                r11 = ashift r2 by -31;
                r13 = ashift r4 by -31;
                r11 = r10 xor r11;
                r13 = r10 xor r13;
                comp(r8, r9);
                if ne r0 = r11;                 /* yA saturated */
                comp(r5, r6);
                if ne r3 = r13;                 /* yB saturated */
                dm(i1, 1) = r0;
        .fdr_lp_{nid}:
                dm(i1, 1) = r3;
            dm(_tap_post_fader_{nid}) = r3;   /* linkage scalars */
            dm(_buf_{nid}) = r3;
            rts;
        #else
            r14 = DSP4_BLOCK_SIZE;
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
        #endif
"""


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
    # These three are the remains of the pan-leg multiply, which the 08-25
    # crosspoint-coefficient fold deleted: the legs are ROUTING's
    # coefficients now, so the block body really is one MAC per sample.
    # The FUSED loop below assumes exactly that and does not splice them
    # in, so if they ever come back the generator must say so rather than
    # emit a fused loop that silently drops them.
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
    if blk_lr_hoist or blk_lr_ptr or blk_lr_body:
        raise ValueError(
            f'{nid}: the FADER_PAN block body has pan-leg work again '
            '(blk_lr_*), which the DSP4_STRIP_FUSED loop does not carry. '
            'Splice it into both loops or drop the fused one.')

    # WIDE-WORD METER, inline (PW ruling 2026-08-29). Same shape as GAIN's
    # and for the same reason: the meter reads the MS word of THIS product
    # register before the rounding half goes in, so the audio MAC moves to
    # MRB and MRF carries the block's exact sum of squares. A metered fader
    # does not take the STRIP_FUSED two-at-a-time loop -- fusion wants both
    # accumulators for two audio samples and there is no third.
    mtr = node['params'].get('mtr_sink', '')
    if mtr:
        if blk_lr_body:
            raise ValueError(
                f'{nid}: a metered FADER_PAN with pan-leg work in the sample '
                'path -- the metered loop does not carry blk_lr_body.')
        # See GAIN: DSP4_MTR_OFF must still remove the meter's arithmetic
        # now that it lives inside this node's loop.
        blk_mtr = ('        #if DSP4_MTR_OFF\n'
                   + _FDR_BLK_PAIR.format(nid=nid, blk_lr_body=blk_lr_body)
                   + '        #else\n'
                   + _FDR_BLK_METERED.format(
                       nid=nid, flush=_mtr_acc_flush(mtr))
                   + '        #endif\n')
        blk_pair = ''
        mtr_decl = (
            '        /* The Q8.24 word the PER-SAMPLE path publishes for\n'
            '         * ' + mtr + '. The block path never stores it -- it hands\n'
            '         * the finished accumulators over instead. */\n'
            '        .var _mtr_wide_' + nid + ';\n')
        mtr_extern = ('        .extern _mtr_acc_' + mtr + ';\n'
                      '        .extern _mtr_flush;\n')
        mtr_pub = (
            '            r12 = mr1f;                           '
            '/* WIDE post-fader, Q8.24 */\n'
            '            dm(_mtr_wide_' + nid + ') = r12;\n')
    else:
        blk_mtr = ''
        blk_pair = _FDR_BLK_PAIR.format(
            nid=nid, blk_lr_body=blk_lr_body)
        mtr_decl = ''
        mtr_extern = ''
        mtr_pub = ''
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
        /* DCA ASSIGNMENT vs DCA GAIN (review finding D57).
         *
         * `_fdr_dca_sel_` is the CELL: `<Cat>[n]RtgDca[1-1]`, which the
         * masters document as "DCA group assignment (1-8 or off)" with
         * MxDatS 9 -- nine states, no scale law, no unit, the InstantCtl
         * profile of a selector. It is STORED HERE AND MULTIPLIED BY
         * NOTHING. Until 2026-08-30 the wire word landed in
         * `_fdr_dca_gain_` instead and was multiplied straight into the
         * fader coefficient, so a host writing the obvious "no DCA
         * assigned" value of 0 SILENCED the strip with `_fdr_level_`
         * still reading 1.0 -- found on the part when it killed the
         * conformance probe's driven strip three runs running.
         *
         * `_fdr_dca_gain_` stays as the RESOLVED master gain the
         * assignment selects, and is unity because nothing resolves it
         * yet: the eight DCA masters are nodes on CHIP 2 and every
         * channel strip is on CHIP 1, so a chip-1 fader cannot read the
         * master it is assigned to, and whether the DSP should apply DCA
         * gain at all (rather than the host folding it into the fader
         * level it already sends) is a contract question, not a kernel
         * one. Both are in the PW question filed with D57. Nothing but a
         * ruling should write this word. */
        .var _fdr_dca_sel_{nid} = 0;              /* 0 = no DCA assigned */
        .var _fdr_dca_gain_{nid} = 1.0;           /* resolved master gain */
        .var _fdr_gq_{nid} = 0x10000000;          /* Q4.28 level*dca */
        /* 1 while either float ramp still has frames to run. ROUTING's
         * main L/R crosspoint coefficients are this node's pan legs, so it
         * has to keep re-prepping while the pan moves (review finding D22).
         * A ramp is not an SPI write and the control epoch never sees it. */
        #if DSP4_BLOCK_KERNELS
        .global _fdr_busy_{nid};
        .var _fdr_busy_{nid} = 0;
        #endif

        .var _tap_post_fader_{nid};
        .var _buf_{nid};
{lr_vars}
{mtr_decl}
        .section/pm seg_pmco;
        .extern _sample_idx;
        .extern _mrf_rns28;
{mtr_extern}        .global _{nid}_process;
        _{nid}_process:
            /* block-rate: float ramps + shadow conversion */
        #if !DSP4_BLOCK_KERNELS
            r4 = dm(_sample_idx);
            r1 = 0;
            comp(r4, r1);
            if ne jump (pc, .apply_{nid});
        #endif

        #if DSP4_BLOCK_KERNELS
            /* Ramps-active publication for the control-rate gate (D22).
             * Taken from the frame counts BEFORE they are consumed: the
             * block that runs a ramp's last frames still moves the pan
             * legs, so ROUTING has to prep on that block too.
             *
             * MAX, not OR: unlike the routing sends, these two counters
             * are NOT clamped at zero -- `frames -= BLOCK` on a ramp with
             * fewer than BLOCK frames left leaves a negative count that the
             * snap test then treats as done, and OR-ing a negative word
             * with a live one gives a negative answer. */
            r4 = dm(_fdr_level_frames_{nid});
            r1 = dm(_fdr_pan_frames_{nid});
            r1 = max(r1, r4);
            r5 = 0;
            r1 = max(r1, r5);
            dm(_fdr_busy_{nid}) = r1;
        #endif

            /* level ramp */
            r4 = dm(_fdr_level_frames_{nid});
            r1 = 0;
            comp(r4, r1);
            if le jump (pc, .lsnap_{nid});
            /* Consume a BLOCK's worth of frames and apply a BLOCK's
             * worth of step. spi_handler scales every profile frame count
             * by DSP4_BLOCK_SIZE, which is right for the ramps that
             * decrement once per SAMPLE. This one decrements once per
             * BLOCK, so taking 1 per block ran it BLOCK times long:
             * measured 2026-08-23 at BLOCK=32, a GainSafe down-ramp took
             * 960 ms against the 30 ms its own cell table specifies, and a
             * GainFast fader move took 85 ms instead of 3 ms. A power of
             * two is exact in binary, so scaling the step loses nothing. */
            r5 = DSP4_BLOCK_SIZE;
            r4 = r4 - r5;
            dm(_fdr_level_frames_{nid}) = r4;
            f1 = dm(_fdr_level_{nid});
            f2 = dm(_fdr_level_step_{nid});
            r5 = DSP4_BLOCK_F32;              /* BLOCK_SIZE as float */
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
             * by DSP4_BLOCK_SIZE, which is right for the ramps that
             * decrement once per SAMPLE. This one decrements once per
             * BLOCK, so taking 1 per block ran it BLOCK times long:
             * measured 2026-08-23 at BLOCK=32, a GainSafe down-ramp took
             * 960 ms against the 30 ms its own cell table specifies, and a
             * GainFast fader move took 85 ms instead of 3 ms. A power of
             * two is exact in binary, so scaling the step loses nothing. */
            r5 = DSP4_BLOCK_SIZE;
            r4 = r4 - r5;
            dm(_fdr_pan_frames_{nid}) = r4;
            f1 = dm(_fdr_pan_{nid});
            f2 = dm(_fdr_pan_step_{nid});
            r5 = DSP4_BLOCK_F32;              /* BLOCK_SIZE as float */
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
{blk_lr_ptr}{blk_mtr}{blk_pair}#else
        .apply_{nid}:
            /* Pure MAC. Mute is already inside _fdr_gq; the pan legs are
             * ROUTING's main-bus crosspoint coefficients. */
            r0 = dm(_buf_{inp});
            r1 = dm(_fdr_gq_{nid});
            mrf = r0 * r1 (ssi);
{mtr_pub}            call _mrf_rns28;

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
            .var _buf_{nid}[DSP4_BLOCK_SIZE];
            #else
            .var _buf_{nid};
            #endif

            .section/pm seg_pmco;
            .extern {acc_sym};
            .extern _acc64_rns28;
            .global _{nid}_process;
            _{nid}_process:
            #if DSP4_BLOCK_KERNELS
                /* One pass per BLOCK, with _acc64_rns28 INLINED and its
                 * constants hoisted. The accumulator is already
                 * per-sample (3 x BLOCK words = BLOCK [lo, hi, ex]
                 * TRIPLES), so this walks it and rounds each sample in
                 * turn.
                 *
                 * The shared routine costs a call, an rts and two constant
                 * reloads on every one of 25 buses x BLOCK samples per
                 * block, which is the same shape that made GAIN 4x cheaper
                 * when it was inlined. The saturation fix-up here is a
                 * CONDITIONAL MOVE, not the early `rts` the shared routine
                 * uses, so the body stays inside a hardware loop.
                 * Arithmetic must stay bit-identical to
                 * fixed_ref.mix_sum.
                 *
                 * THE SATURATION TEST IS OVER ALL 80 BITS (review finding
                 * D1). Two conditions, ORed into one conditional move:
                 *   (a) bits 63..59 are the sign of y, and
                 *   (b) ex is the sign extension of hi.
                 * (b) is the one the two-word accumulator could not ask,
                 * because it manufactured ex from hi on every load -- so a
                 * bus sum past +/-128.0 wrapped and then passed (a) as a
                 * clean, full-scale, wrong-sign sample. (b) is tested on
                 * the low 16 bits only: MR2F holds bits 79..64 and the
                 * read-back representation of the unused upper half is not
                 * relied on. */
                l2 = 0;
                l3 = 0;
                i2 = {acc_sym};
                i3 = _buf_{nid};
                r8 = 0x08000000;          /* 2^27, the rounding half */
                r9 = 1;
                r10 = 0x7FFFFFFF;
                lcntr = DSP4_BLOCK_SIZE, do .mbk_{nid} until lce;
                    r1 = dm(i2, 1);       /* lo; i2 -> hi              */
                    mr0f = r1;
                    r2 = dm(i2, 1);       /* hi; i2 -> ex              */
                    mr1f = r2;
                    r3 = dm(i2, 1);       /* ex; i2 -> next triple     */
                    mr2f = r3;
                    mrf = mrf + r8 * r9 (ssi);
                    r1 = mr0f;
                    r2 = mr1f;
                    r1 = lshift r1 by -28;
                    r12 = lshift r2 by 4;
                    r0 = r1 or r12;
                    /* saturation value, by the sign of the TRUE top word */
                    r11 = lshift r3 by 16;
                    r11 = ashift r11 by -31;
                    r11 = r10 xor r11;
                    /* (a) */
                    r1 = ashift r2 by -28;
                    r12 = ashift r0 by -31;
                    comp(r1, r12);
                    if ne r0 = r11;
                    /* (b) */
                    r1 = ashift r2 by -31;
                    r3 = r3 xor r1;
                    r3 = lshift r3 by 16;
                    r3 = pass r3;
                    if ne r0 = r11;
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


def gen_block_header():
    """dsp_block.h — the block size, as preprocessor macros.

    THE contract between the generator and the hand-maintained sources.
    Pure #defines, so the same header serves the assembler (main.asm,
    spi_handler.asm, the src/lib kernels) and the C compiler
    (dma_config.c). Anything that needs a sample count per block asks
    here; nothing hardcodes one.
    """
    import fixed_ref
    import math
    _mtr_alpha_q, _mtr_beta_q = fixed_ref.meter_coeffs(BLOCK)
    # LEGACY (float) meter peak decay, applied once per block by
    # main.asm -> _meter_decay_block. Same time constant as the new
    # meter's peak hold, expressed as the multiplicative per-block
    # survivor rather than the one-pole increment: exp(-1 / (rate*tau)).
    _mtr_legacy_decay = math.exp(
        -1.0 / (BLOCKS_PER_SEC * fixed_ref.METER_TAU_PEAK_S))
    return f"""\
/* dsp_block.h — audio block size (samples per DMA block) */
/* AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly. */
/*
 * BLOCK SIZE IS A BUILD PARAMETER. Change it in dsp_codegen.py (BLOCK)
 * and regenerate; every loop count, slot array, DMA ring, ramp step and
 * verdict rate in the tree follows from these macros.
 *
 * 2026-08-28 (PW ruling): the working operating point is {BLOCK}.
 * Predicted digital latency ~23 samples = 0.48 ms at 48 kHz, from the
 * 93-samples-at-BLOCK-32 pipeline measured on the part. Any figure in
 * the ledger or the options paper that predates this header is a
 * BLOCK-32 figure and is labelled as one.
 *
 * DSP4_BLOCK_SIZE   samples per block
 * DSP4_BLOCK_HALF   for the two-samples-per-iteration fused kernels
 * DSP4_BLOCK_SHIFT  log2(BLOCK): block-rate frames -> samples
 * DSP4_BLOCK_F32    BLOCK as an IEEE-754 single, for per-block ramp steps
 * DSP4_BLOCK_RATE   blocks per second at 48 kHz -- the verdict rate
 */
#ifndef DSP4_BLOCK_H
#define DSP4_BLOCK_H

#define DSP4_BLOCK_SIZE   {BLOCK}
#define DSP4_BLOCK_HALF   {BLOCK_HALF}
#define DSP4_BLOCK_SHIFT  {BLOCK_SHIFT}
#define DSP4_BLOCK_F32    {_f32hex(BLOCK)}
#define DSP4_BLOCK_RATE   {int(BLOCKS_PER_SEC)}

/* METER coefficients. They live here because they are functions of the
 * BLOCK RATE, not of the meter: the time constants are fixed properties
 * (RMS window {fixed_ref.METER_TAU_RMS_S * 1000:.0f} ms, peak-hold decay
 * {fixed_ref.METER_TAU_PEAK_S:.3f} s) and the per-block coefficient that
 * realises them moves when the block size moves. Getting this wrong is
 * exactly the third recorded meter defect -- a constant derived for 1500
 * blocks/s applied once per SAMPLE, which ran the decay 32x fast.
 * Q4.28, one - exp(-1 / (rate * tau)). Normative source:
 * tools/dsp/fixed_ref.py::meter_coeffs.
 *
 * DSP4_MTR_CVT_DIV rate-limits only the float CONVERSION for the host
 * ({int(BLOCKS_PER_SEC) // MTR_CVT_DIV} Hz); the measurement itself is
 * every sample of every block. */
#define DSP4_MTR_ALPHA_Q  {_mtr_alpha_q}
#define DSP4_MTR_BETA_Q   {_mtr_beta_q}
#define DSP4_MTR_CVT_DIV  {MTR_CVT_DIV}

/* LEGACY float meter (src/lib/meter.asm), IEEE-754 single. The peak
 * array decays by this factor once per BLOCK, so it is the same
 * {fixed_ref.METER_TAU_PEAK_S:.3f} s time constant expressed as a survivor:
 * exp(-1 / (rate * tau)) = {_mtr_legacy_decay:.9f} at {int(BLOCKS_PER_SEC)} blocks/s.
 * It used to be a hand constant, 0.99950, derived for 1500 blocks/s and
 * left unchanged when the operating point moved to BLOCK={BLOCK} -- so it
 * decayed in 0.333 s, FOUR TIMES FAST, in the shipping image (review
 * finding D6). It is the same recorded meter-defect class as
 * DSP4_MTR_BETA_Q above, in the one meter path the 08-28 rebuild did not
 * replace, and it is derived here for the same reason. */
#define DSP4_MTR_DECAY_F32 {_f32hex(_mtr_legacy_decay)}

/* PAIRED GRAPH. DSP4_SIMD_DYN says the paired dynamics KERNELS are in the
 * image; DSP4_SIMD_GRAPH says the graph is WIRED for them -- the odd pool,
 * the pair drivers and the pair-ordered chain. They are separate because
 * the self-test build wants the kernels and their scalar twins and nothing
 * else: with the drivers in as well, chip 1's PM overflows sec_swco. Every
 * piece of the wiring is guarded on this one macro. */
#ifndef DSP4_SIMD_GRAPH
#define DSP4_SIMD_GRAPH 1
#endif
#if DSP4_SIMD_DYN && DSP4_SIMD_GRAPH
#define DSP4_PAIRED_GRAPH 1
#else
#define DSP4_PAIRED_GRAPH 0
#endif

/* PAIRED BIQUADS IN THE GRAPH (2026-08-29). The same separation once more:
 * DSP4_SIMD_PROBE puts _bq_pair_blk and _bq_fx_cascade_simd in the image
 * for the self-test, DSP4_BQ_GRAPH wires the FILT and EQ classes of a
 * strip PAIR into one call the way the dynamics already are. The kernel
 * side has been measured at 1.43-1.54x since the paired-cascade hang was
 * root-caused; until this macro nothing in the GRAPH used it.
 *
 * DSP4_BQ_PAIRED is what the library and the drivers are guarded on, so a
 * probe build and a graph build reach the same code and there is one
 * copy of it. */
#ifndef DSP4_BQ_GRAPH
#define DSP4_BQ_GRAPH 1
#endif
#if DSP4_PAIRED_GRAPH && DSP4_BQ_GRAPH
#define DSP4_BQ_PAIRED_GRAPH 1
#else
#define DSP4_BQ_PAIRED_GRAPH 0
#endif
#if DSP4_BQ_PAIRED_GRAPH || DSP4_SIMD_PROBE
#define DSP4_BQ_PAIRED 1
#else
#define DSP4_BQ_PAIRED 0
#endif

#endif /* DSP4_BLOCK_H */
"""


def gen_block_py():
    """dsp4_block.py — the block size for the Pi-side bench tools.

    Same number as dsp_block.h, same source. Staged next to the .ldr by
    the harness scripts so the verdict is always scored against the block
    size the image on the part was actually built with.
    """
    q = chr(34) * 3
    return (
        q + 'dsp4_block.py -- audio block size, for the Pi-side bench tools.\n'
        '\n'
        'AUTO-GENERATED by tools/dsp/dsp_codegen.py -- do not edit directly.\n'
        'Staged onto the bench beside the .ldr files by the harness scripts.\n'
        + q + '\n'
        '\n'
        f'BLOCK = {BLOCK}                 # samples per DMA block\n'
        f'BLOCK_RATE = {int(BLOCKS_PER_SEC)}          '
        '# blocks/s at 48 kHz -- the real-time bar\n')


def gen_blk_pool_header():
    """blk_pool.h — slot names for the shared per-strip block buffers."""
    return """\
/* blk_pool.h — shared per-strip block buffers (KERNEL REWRITE) */
/* AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly. */
/*
 * Buffer reuse, not one buffer per node. A strip is a linear chain and the
 * strips run one after another, so the live set at any moment is small and
 * fixed: a ping-pong pair for the chain itself, the fader's L/R split, and
 * the four taps the router picks from. 8 slots x BLOCK serves all 32
 * strips; one buffer per node would want ~16K words at BLOCK=32, which is
 * what overflowed DM on 2026-08-24.
 */
#ifndef DSP4_BLK_POOL_H
#define DSP4_BLK_POOL_H

#include "dsp_block.h"

#if DSP4_BLOCK_KERNELS
.extern _blk_pool;
#define BLK(n)           (_blk_pool + (n) * DSP4_BLOCK_SIZE)

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
 * catches up, then _bq_pair_blk interleaves the two. That is ONE slot --
 * BLOCK words -- not the doubled pool an earlier note claimed. */
#define BLK_PAIR_PARK    BLK(8)

/* ---- THE ODD POOL (DSP4_SIMD_DYN) ---------------------------------
 * Pairing the dynamics needs BOTH strips of a pair to hold live chain
 * blocks at the same moment, and the pool above cannot do that: it is
 * reused sequentially, so strip N's block is dead the instant strip N+1
 * starts. The earlier scaffolding parked ONE slot (BLK_PAIR_PARK) and
 * copied into and out of it, which is enough for a biquad pair inside a
 * single strip's kernel but not for a pair whose two strips each run
 * four head nodes and four tail nodes around the paired dynamics: the
 * TAPS (trim, EQ, pre-fader) are written in the head and read by RTG in
 * the TAIL, so parking the chain alone would leave strip A's router
 * reading strip B's taps.
 *
 * So the ODD strip of each pair gets a whole SECOND POOL and the even
 * strip keeps the original. No copying at all: strip A's nodes are
 * GENERATED against BLK_*_P1 and strip B's against BLK_*, both pools
 * are live across the pair, and the paired kernels read one channel
 * from each. Cost is 8 slots x BLOCK words -- 64 words at BLOCK=8.
 *
 * With DSP4_SIMD_DYN off every BLK_*_P1 collapses onto its BLK_*
 * original, so a node generated for the odd pool assembles to exactly
 * the bytes it did before pairing existed. That aliasing is what keeps
 * the shipping image byte-identical while the generator emits P1 names
 * for half the strips.
 */
#if DSP4_PAIRED_GRAPH
.extern _blk_pool1;
#define BLK1(n)             (_blk_pool1 + (n) * DSP4_BLOCK_SIZE)
#define BLK_CHAIN_A_P1      BLK1(0)
#define BLK_CHAIN_B_P1      BLK1(1)
#define BLK_FDR_L_P1        BLK1(2)
#define BLK_FDR_R_P1        BLK1(3)
#define BLK_TAP_TRIM_P1     BLK1(4)
#define BLK_TAP_EQ_P1       BLK1(5)
#define BLK_TAP_PREFDR_P1   BLK1(6)
#define BLK_TAP_POSTFDR_P1  BLK1(7)
#else
#define BLK_CHAIN_A_P1      BLK_CHAIN_A
#define BLK_CHAIN_B_P1      BLK_CHAIN_B
#define BLK_FDR_L_P1        BLK_FDR_L
#define BLK_FDR_R_P1        BLK_FDR_R
#define BLK_TAP_TRIM_P1     BLK_TAP_TRIM
#define BLK_TAP_EQ_P1       BLK_TAP_EQ
#define BLK_TAP_PREFDR_P1   BLK_TAP_PREFDR
#define BLK_TAP_POSTFDR_P1  BLK_TAP_POSTFDR
#endif
#endif

#endif /* DSP4_BLK_POOL_H */
"""


NUM_SELFTEST_TEMPLATE = '''\
/*======================================================================
 * num_selftest.asm — is the ASSEMBLY the same arithmetic as fixed_ref,
 * AT the wide-accumulator and blend boundaries and on BOTH sides of them?
 *
 * AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly.
 *
 * Two arms, for the two touchpoints the 2026-08-28 review found could
 * WRAP rather than saturate:
 *
 *   MIX   review finding D1 (SEVERE). The bus accumulators. Zero a
 *         [lo, hi, ex] triple, MAC N contributions into it with the
 *         REAL _acc64_mac, read it out with the REAL _acc64_rns28.
 *         No copied arithmetic: these are the routines the graph runs.
 *   BLEND review finding D3. The dual-instance crossfade. The probe
 *         body is emitted from _xfade_blend_core() in dsp_codegen.py --
 *         the SAME expression that emits it into all 32 EQ, all 32
 *         FILT and both crossover nodes -- so the instructions proved
 *         here are the instructions those nodes execute.
 *
 * THE VECTORS STRADDLE THE BOUNDARIES ON PURPOSE, and the host reads
 * the results back and compares them against fixed_ref.mix_sum and
 * fixed_ref.xfade_blend. They are the same vectors golden_harness.py
 * uses, so "asm == model" and "model is right" are checked on identical
 * numbers.
 *
 * NEGATIVE CONTROL, IN THE SAME INSTRUMENT: DSP4_NUM_NEGCTL=1 swaps the
 * fixed routines for _nst_mac_old / _nst_rns_old / _nst_blend_old, which
 * are the PRE-FIX arithmetic -- the 64-bit accumulator that discards
 * MR2F and the 32-bit new-old difference. The host requires those to
 * FAIL exactly the vectors that cross a boundary and to PASS every
 * vector that does not. A test that cannot fail proves nothing, and
 * this bench has produced two of those already.
 *
 * TIMING ARM: the same two MAC forms over the same work, against the
 * 1 kHz diag tick. That is the per-MAC cost of the third word, MEASURED.
 *
 * Debug only: DSP4_NUM_SELFTEST. Never in a shipping image.
 *====================================================================*/

#include "dsp_block.h"
#include "diag.h"

#if DSP4_NUM_SELFTEST

.section/dm seg_dmda;

/* ---- MIX vectors: {nmix} of them ------------------------------------
 * Each is (n1, x1, g1, n2, x2, g2): n1 contributions of x1*g1 followed
 * by n2 of x2*g2 (n2 = 0 for the single-part vectors). Unity x unity is
 * exactly 2^56 in Q8.56, so a count of 128 lands the sum EXACTLY on the
 * old 64-bit +/-128.0 boundary and 127/129 sit one contribution either
 * side of it.
 */
.global _nst_mix_v;
.var _nst_mix_v[{nmix6}] =
{mixv};
.global _nst_mix_n;     .var _nst_mix_n = {nmix};
.global _nst_mix_r;     .var _nst_mix_r[{nmix}];

/* ---- BLEND vectors: {nbl} of them, (new, old, alpha_f32) ---------- */
.global _nst_bl_v;
.var _nst_bl_v[{nbl3}] =
{blv};
.global _nst_bl_n;      .var _nst_bl_n = {nbl};
.global _nst_bl_r;      .var _nst_bl_r[{nbl}];

/* the blend core reads its alpha from here (pfx=nst, nid=PROBE) */
.global _nst_xfade_alpha_PROBE;
.var _nst_xfade_alpha_PROBE = 0.0;

/* one accumulator triple for the MIX arm */
.global _nst_acc;       .var _nst_acc[3];

/* ---- results / timing ------------------------------------------- */
.global _nst_done;      .var _nst_done = 0;
.global _nst_negctl;    .var _nst_negctl = DSP4_NUM_NEGCTL;
/* TIMING. Six (ticks, tcount) PAIRS -- ticks alone quantises to 1 ms,
 * which at 200k iterations is 2.46 cycles/MAC and cannot see a two- or
 * three-instruction change. TCOUNT counts core clocks down and reloads
 * from DIAG_TPERIOD, so
 *     cycles = (ticks_end - ticks_start) * DIAG_TPERIOD
 *              + (tcount_start - tcount_end)
 * which is the form main.asm already uses for its per-block cost. */
.global _nst_tick;      .var _nst_tick[20] =
    0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0;
/* BLOCK arms present? The block-kernel MAC only exists in a
 * DSP4_BLOCK_KERNELS build, and that is the operating point the
 * capacity work runs at, so it gets its own pair of arms there. */
.global _nst_have_blk;  .var _nst_have_blk = DSP4_BLOCK_KERNELS;
.global _nst_blk_n;     .var _nst_blk_n = DSP4_BLOCK_SIZE;
/* BLOCK arms need a BLOCK-long source and a BLOCK-triple accumulator */
.global _nst_blk_src;   .var _nst_blk_src[DSP4_BLOCK_SIZE];
.global _nst_blk_acc;   .var _nst_blk_acc[3*DSP4_BLOCK_SIZE];
.global _nst_tper;      .var _nst_tper = DIAG_TPERIOD;
.global _nst_iters;     .var _nst_iters = 200000;

.section/pm seg_pmco;
.extern _acc64_mac;
.extern _acc64_rns28;
.extern _diag_ticks;
#if DSP4_BLOCK_KERNELS
.extern _acc64_mac_blk;
#endif

/*----------------------------------------------------------------------
 * _xfade_blend_probe — the SHIPPED blend body, callable.
 * In:  r0 = new, r14 = old, _nst_xfade_alpha_PROBE = alpha (float)
 * Out: r0 = blended sample
 *----------------------------------------------------------------------*/
.global _xfade_blend_probe;
_xfade_blend_probe:
{blend_core}
    rts;
_xfade_blend_probe.end:

/*----------------------------------------------------------------------
 * _nst_blend_old — the PRE-FIX blend: the difference in 32 bits.
 * Same registers. Only the two MACs differ.
 *----------------------------------------------------------------------*/
.global _nst_blend_old;
_nst_blend_old:
    f4 = dm(_nst_xfade_alpha_PROBE);
    r5 = 0x4F000000;
    f5 = r5;
    f4 = f4 * f5;
    r4 = fix f4;
    r5 = r0 - r14;                 /* new - old, IN 32 BITS: wraps */
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
    rts;
_nst_blend_old.end:

/*----------------------------------------------------------------------
 * _nst_mac_old / _nst_rns_old — the PRE-FIX bus accumulator: two words,
 * MR2F discarded on store and manufactured from the sign of hi on load.
 * Byte-for-byte what lib/mac64_fx.asm held before 2026-08-29.
 *----------------------------------------------------------------------*/
.global _nst_mac_old;
_nst_mac_old:
    r2 = dm(i2, 1);
    r3 = dm(i2, 0);
    mr0f = r2;
    mr1f = r3;
    r2 = ashift r3 by -31;
    mr2f = r2;
    mrf = mrf + r0 * r1 (ssi);
    r2 = mr1f;
    dm(i2, -1) = r2;
    r2 = mr0f;
    dm(i2, 0) = r2;
    rts;
_nst_mac_old.end:

#if DSP4_BLOCK_KERNELS
/*----------------------------------------------------------------------
 * _nst_mac_blk_old — the PRE-FIX per-BLOCK accumulate: BLOCK [lo, hi]
 * pairs, MR2F discarded. Byte-for-byte what the generator emitted as
 * _acc64_mac_blk before 2026-08-29. Timing arm only.
 *----------------------------------------------------------------------*/
.global _nst_mac_blk_old;
_nst_mac_blk_old:
    l0 = 0;
    l2 = 0;
    r5 = DSP4_BLOCK_SIZE;
    lcntr = r5, do .nmbo_lp until lce;
        r0 = dm(i0, 1);
        r2 = dm(i2, 1);            /* lo; i2 -> hi */
        r3 = dm(i2, 0);            /* hi           */
        mr0f = r2;
        mr1f = r3;
        r2 = ashift r3 by -31;
        mr2f = r2;
        mrf = mrf + r0 * r1 (ssi);
        r2 = mr1f;
        dm(i2, -1) = r2;           /* hi; i2 -> lo */
        r2 = mr0f;
    .nmbo_lp:
        dm(i2, 2) = r2;            /* lo; i2 -> next pair */
    rts;
_nst_mac_blk_old.end:
#endif

.global _nst_rns_old;
_nst_rns_old:
    r1 = dm(i2, 1);
    r2 = dm(i2, 0);
    mr0f = r1;
    mr1f = r2;
    r3 = ashift r2 by -31;
    mr2f = r3;
    r1 = 0x08000000;
    r3 = 1;
    mrf = mrf + r1 * r3 (ssi);
    r1 = mr0f;
    r2 = mr1f;
    r1 = lshift r1 by -28;
    r3 = lshift r2 by 4;
    r0 = r1 or r3;
    r1 = ashift r2 by -28;
    r3 = ashift r0 by -31;
    comp(r1, r3);
    if eq rts;
    r0 = 0x7FFFFFFF;
    r1 = ashift r2 by -31;
    r0 = r0 xor r1;
    rts;
_nst_rns_old.end:

/*----------------------------------------------------------------------
 * _num_selftest — run both arms once, then the timing arm.
 *----------------------------------------------------------------------*/
.global _num_selftest;
_num_selftest:
    l0 = 0; l1 = 0; l2 = 0; l3 = 0; l4 = 0; l5 = 0;

    /* ================= MIX arm ================= */
    i4 = _nst_mix_v;
    i5 = _nst_mix_r;
    r14 = dm(_nst_mix_n);
    lcntr = r14, do .nst_mix_lp until lce;
        /* zero the triple */
        r0 = 0;
        dm(_nst_acc) = r0;
        dm(_nst_acc + 1) = r0;
        dm(_nst_acc + 2) = r0;
        /* part 1 */
        r10 = dm(i4, 1);           /* n1 */
        r11 = dm(i4, 1);           /* x1 */
        r12 = dm(i4, 1);           /* g1 */
        r10 = pass r10;
        if eq jump (pc, .nst_p2);
        lcntr = r10, do .nst_a1 until lce;
            r0 = r11;
            r1 = r12;
            i2 = _nst_acc;
#if DSP4_NUM_NEGCTL
            call _nst_mac_old;
#else
            call _acc64_mac;
#endif
            nop;
        .nst_a1:
            nop;
    .nst_p2:
        /* part 2 */
        r10 = dm(i4, 1);           /* n2 */
        r11 = dm(i4, 1);           /* x2 */
        r12 = dm(i4, 1);           /* g2 */
        r10 = pass r10;
        if eq jump (pc, .nst_rd);
        lcntr = r10, do .nst_a2 until lce;
            r0 = r11;
            r1 = r12;
            i2 = _nst_acc;
#if DSP4_NUM_NEGCTL
            call _nst_mac_old;
#else
            call _acc64_mac;
#endif
            nop;
        .nst_a2:
            nop;
    .nst_rd:
        i2 = _nst_acc;
#if DSP4_NUM_NEGCTL
        call _nst_rns_old;
#else
        call _acc64_rns28;
#endif
        dm(i5, 1) = r0;
        nop;
    .nst_mix_lp:
        nop;

    /* ================= BLEND arm ================= */
    i4 = _nst_bl_v;
    i5 = _nst_bl_r;
    r14 = dm(_nst_bl_n);
    lcntr = r14, do .nst_bl_lp until lce;
        r10 = dm(i4, 1);           /* new */
        r11 = dm(i4, 1);           /* old */
        r12 = dm(i4, 1);           /* alpha, float bits */
        dm(_nst_xfade_alpha_PROBE) = r12;
        r0 = r10;
        r14 = r11;
#if DSP4_NUM_NEGCTL
        call _nst_blend_old;
#else
        call _xfade_blend_probe;
#endif
        dm(i5, 1) = r0;
        nop;
    .nst_bl_lp:
        nop;

    /* ================= TIMING arm =================
     * The SAME work through both MAC forms. Three arms:
     *   pair 0  null loop (the setup and loop overhead)
     *   pair 1  _acc64_mac   -- the three-word form the graph now runs
     *   pair 2  _nst_mac_old -- the pre-fix two-word form
     * Each pair is (ticks, tcount) at the start and again at the end,
     * six pairs in _nst_tick. The host computes
     *   cycles = (ticks_end - ticks_start) * DIAG_TPERIOD
     *            + (tcount_start - tcount_end)
     * which is main.asm's own per-block accounting form -- ticks alone
     * quantise to 1 ms, which at 200k iterations is 2.46 cycles/MAC and
     * cannot see a two-instruction change. */
    r2 = tcount;
    r0 = dm(_diag_ticks);
    dm(_nst_tick + 0) = r0;
    dm(_nst_tick + 1) = r2;
    r10 = dm(_nst_iters);
    lcntr = r10, do .nst_tn until lce;
        r0 = 0x40000000;
        r1 = 0x10000000;
        i2 = _nst_acc;
        nop;
        nop;
    .nst_tn:
        nop;
    r2 = tcount;
    r0 = dm(_diag_ticks);
    dm(_nst_tick + 2) = r0;
    dm(_nst_tick + 3) = r2;

    r2 = tcount;
    r0 = dm(_diag_ticks);
    dm(_nst_tick + 4) = r0;
    dm(_nst_tick + 5) = r2;
    r10 = dm(_nst_iters);
    lcntr = r10, do .nst_tnew until lce;
        r0 = 0x40000000;
        r1 = 0x10000000;
        i2 = _nst_acc;
        call _acc64_mac;
        nop;
    .nst_tnew:
        nop;
    r2 = tcount;
    r0 = dm(_diag_ticks);
    dm(_nst_tick + 6) = r0;
    dm(_nst_tick + 7) = r2;

    r2 = tcount;
    r0 = dm(_diag_ticks);
    dm(_nst_tick + 8) = r0;
    dm(_nst_tick + 9) = r2;
    r10 = dm(_nst_iters);
    lcntr = r10, do .nst_told until lce;
        r0 = 0x40000000;
        r1 = 0x10000000;
        i2 = _nst_acc;
        call _nst_mac_old;
        nop;
    .nst_told:
        nop;
    r2 = tcount;
    r0 = dm(_diag_ticks);
    dm(_nst_tick + 10) = r0;
    dm(_nst_tick + 11) = r2;

#if DSP4_BLOCK_KERNELS
    /* pair 3 = _acc64_mac_blk (3 word), pair 4 = the pre-fix 2-word
     * block form. Each call is BLOCK MACs, so the host divides by
     * iters * BLOCK. This is the form the block-8 operating point runs
     * and the one the capacity arithmetic is built on. */
    r2 = tcount;
    r0 = dm(_diag_ticks);
    dm(_nst_tick + 12) = r0;
    dm(_nst_tick + 13) = r2;
    r10 = dm(_nst_iters);
    lcntr = r10, do .nst_tbn until lce;
        r1 = 0x10000000;
        i0 = _nst_blk_src;
        i2 = _nst_blk_acc;
        call _acc64_mac_blk;
        nop;
    .nst_tbn:
        nop;
    r2 = tcount;
    r0 = dm(_diag_ticks);
    dm(_nst_tick + 14) = r0;
    dm(_nst_tick + 15) = r2;

    r2 = tcount;
    r0 = dm(_diag_ticks);
    dm(_nst_tick + 16) = r0;
    dm(_nst_tick + 17) = r2;
    r10 = dm(_nst_iters);
    lcntr = r10, do .nst_tbo until lce;
        r1 = 0x10000000;
        i0 = _nst_blk_src;
        i2 = _nst_blk_acc;
        call _nst_mac_blk_old;
        nop;
    .nst_tbo:
        nop;
    r2 = tcount;
    r0 = dm(_diag_ticks);
    dm(_nst_tick + 18) = r0;
    dm(_nst_tick + 19) = r2;
#endif

    r0 = 1;
    dm(_nst_done) = r0;
    rts;
_num_selftest.end:

#endif /* DSP4_NUM_SELFTEST */
'''


def gen_num_selftest():
    """lib/num_selftest.asm — the in-part bit-exactness proof for the two
    WRAP findings (D1, D3).

    Vectors come from tools/dsp/boundary_vectors.py, the same module
    golden_harness.py and the Pi-side reader use, and the blend body
    comes from _xfade_blend_core() -- the same expression that emits it
    into every EQ/FILT/CROSSOVER node. Neither the numbers nor the
    instructions are retyped here, which is what makes the result a
    proof about the shipped code rather than about a copy.
    """
    import boundary_vectors as bv

    def row(v):
        n1, x1, g1, n2, x2, g2 = v[:6]
        return ('    ' + ', '.join(f'0x{w & 0xFFFFFFFF:08X}'
                                   for w in (n1, x1, g1, n2, x2, g2))
                + f',   /* {v[6]} */')

    mixv = '\n'.join(row(v) for v in bv.MIX)
    mixv = mixv.rstrip(',') if not mixv.endswith('*/') else mixv
    # strip the trailing comma of the LAST row (it is before the comment)
    lines = mixv.split('\n')
    lines[-1] = lines[-1].replace(',   /*', '    /*', 1)
    mixv = '\n'.join(lines)

    bl = []
    for v in bv.BLEND:
        bl.append('    0x%08X, 0x%08X, 0x%08X,   /* %s */'
                  % (v[0] & 0xFFFFFFFF, v[1] & 0xFFFFFFFF,
                     bv.f32_bits(v[2]), v[3]))
    bl[-1] = bl[-1].replace(',   /*', '    /*', 1)
    blv = '\n'.join(bl)

    return NUM_SELFTEST_TEMPLATE.format(
        nmix=len(bv.MIX), nmix6=6 * len(bv.MIX), mixv=mixv,
        nbl=len(bv.BLEND), nbl3=3 * len(bv.BLEND), blv=blv,
        blend_core=_xfade_blend_core('nst', 'PROBE'))


# ===========================================================================
# Control-rate gate (review finding D22/D24)
# ===========================================================================
#
# The strip nodes rebuild control state -- send ramps, pickoff resolution,
# crosspoint lists, float->fixed parameter conversion -- once per BLOCK, for
# state that only changes when the host writes a parameter or while a ramp is
# running. At BLOCK=8 that is the largest floor gap in the strip (RTG alone
# measured 232.6 cycles/sample of a 1,466-cycle strip).
#
# THE GATE IS AN EPOCH COUNTER, NOT A FLAG, and the difference matters. A
# flag has to be CLEARED by whoever consumes it, so two nodes in the same
# strip race for it: whichever runs first clears the write out from under the
# other. A counter is only ever incremented by the writer; each node keeps
# its own "epoch I last prepped at" word and compares. Nothing shared is
# mutated by a reader, so any number of nodes can watch the same strip.
#
# ONE STRIP = ONE COUNTER. Chip 1's SPI address space is 32 contiguous
# 144-word channel pages (Chan001Gain001 at 0, Chan002Gain001 at 144, ...,
# Chan032Gain001 at 4464), so the strip a write belongs to is addr/144 --
# computed in the handler as (addr * 7282) >> 20, which is EXACT over
# 0..4607 and needs no divide and no MR register (the handler runs as an
# ISR and must not disturb the multiplier the audio path is using).
# Addresses at or above 4608 -- the meter read-back block, diag and product
# config -- land in a 33rd catch-all slot that no strip node watches.
#
# THE RACE THAT IS LEFT IS BENIGN AND IS HANDLED BY ORDER: a node reads the
# epoch BEFORE it preps and stores that value AFTER. A write that lands
# mid-prep therefore leaves epoch > seen and the node preps again next
# block, rather than recording that it has already seen it.
#
# RAMPS ARE NOT SPI WRITES, so the epoch does not see them: a node that
# advanced a ramp this block publishes its own "busy" word and keeps
# prepping while it is set. The node that consumes a ramped value from
# ANOTHER node (ROUTING reads FADER_PAN's pan legs) watches that node's busy
# word too.
#
# Bit-exactness: skipping the prep is exact because the prep is idempotent
# on unchanged inputs -- it recomputes the same coefficients from the same
# parameters and stores them over themselves. That is checked, not asserted:
# DSP4_CTL_ALWAYS=1 puts the unconditional prep back in the same image, and
# the two builds must agree sample for sample.
CTL_EPOCH_SLOTS = 33          # 32 chip-1 strips + one catch-all
CTL_ADDR_STRIDE = 144         # SPI addresses per channel page
CTL_RECIP_M = 7282            # ceil(2^20 / 144); (a*M)>>20 == a/144 for a < 4608
CTL_RECIP_SH = 20


def gen_ctl_epoch():
    """ctl_epoch.asm -- the per-strip control-epoch counters (D22/D24)."""
    out = []
    out.append('/* ctl_epoch.asm — per-strip control-rate epoch counters (D22/D24) */')
    out.append('/* AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit. */')
    out.append('/*')
    out.append(' * One counter per chip-1 channel strip, incremented by the SPI')
    out.append(' * handler on every accepted write into that strip\'s 144-word page,')
    out.append(' * plus a catch-all slot for everything outside the strip pages.')
    out.append(' *')
    out.append(' * A node preps its control state when the counter differs from the')
    out.append(' * epoch it last prepped at, or while it (or a node it depends on) is')
    out.append(' * running a ramp. Readers never write these words, so a strip can')
    out.append(' * carry any number of watchers without a clear-race.')
    out.append(' *')
    out.append(' * CHIP 1 ONLY. Chip 2 assembles this file too -- everything under')
    out.append(' * src/ is assembled once per chip -- but its nodes are not')
    out.append(' * strip-shaped, none of them gate on an epoch, and the fader-busy')
    out.append(' * pointer table below names chip-1 symbols that do not exist in a')
    out.append(' * chip-2 link. So the whole body is behind CHIP_ID == 1.')
    out.append(' *')
    out.append(' * INITIALISED TO 1, and the node-side "last seen" words to 0, so every')
    out.append(' * gated node preps on the first block after reset whatever the host')
    out.append(' * has or has not written.')
    out.append(' */')
    out.append('')
    out.append('#include "dsp_block.h"')
    out.append('')
    out.append('/* Only the block-kernel builds gate anything, so only they carry')
    out.append(' * the counters or the handler bump that feeds them: the per-sample')
    out.append(' * image is byte-identical either side of this file. */')
    out.append('#if DSP4_BLOCK_KERNELS && CHIP_ID == 1')
    out.append('.section/dm seg_dmda;')
    out.append('')
    out.append('.global _ctl_epoch;')
    out.append(f'.var _ctl_epoch[{CTL_EPOCH_SLOTS}] = '
               + ', '.join(['1'] * CTL_EPOCH_SLOTS) + ';')
    out.append('')
    out.append('/* Per-strip gate state, INDEXED not per-node, and the reason is')
    out.append(' * program memory rather than data memory. Chip 1\'s VISA code')
    out.append(' * section is 99.9 % full in the paired 32-strip build (block 3')
    out.append(' * used 131,070 of 131,072 words; the overflow into block 2 leaves')
    out.append(' * about 1,400). A directly-addressed DM access is a LONG VISA')
    out.append(' * instruction, so an inline gate of nine instructions cost ~41')
    out.append(' * words per node -- 1,320 across 32 ROUTING nodes, which is more')
    out.append(' * than the whole remaining margin, and the paired build stopped')
    out.append(' * linking. Indexed arrays plus one shared routine put the caller')
    out.append(' * at three instructions.')
    out.append(' *')
    out.append(' * _rtg_ep    the epoch each ROUTING node last prepped at')
    out.append(' * _rtg_busy  1 while that node still has a send ramp running')
    out.append(' * _fdr_busy_ptrs  where to find the fader\'s ramp flag, whose pan')
    out.append(' *            legs are the ROUTING node\'s main L/R coefficients */')
    out.append('.global _rtg_ep;')
    out.append('.var _rtg_ep[32] = ' + ', '.join(['0'] * 32) + ';')
    out.append('.global _rtg_busy;')
    out.append('.var _rtg_busy[32] = ' + ', '.join(['0'] * 32) + ';')
    for k in range(1, 33):
        out.append(f'.extern _fdr_busy_C1_FDR_{k:02d};')
    out.append('.global _fdr_busy_ptrs;')
    out.append('.var _fdr_busy_ptrs[32] =')
    for k in range(1, 33):
        out.append(f'    _fdr_busy_C1_FDR_{k:02d}'
                   + (',' if k < 32 else ';'))
    out.append('')
    out.append('.section/pm seg_pmco;')
    out.append('')
    out.append('/*--------------------------------------------------------------')
    out.append(' * _ctl_strip_prep_needed — does strip r0 have to rebuild its')
    out.append(' * ROUTING control state this block?')
    out.append(' *')
    out.append(' * In:  r0 = strip index, 0..31')
    out.append(' * Out: returns with AZ SET (so the caller\'s `if eq jump` is')
    out.append(' *      taken) when the prep can be SKIPPED. When it cannot, the')
    out.append(' *      node\'s epoch has already been updated to the value read')
    out.append(' *      here and AZ is clear.')
    out.append(' * Clobbers: r1, r2, r3, r4, i4, m4, l4.')
    out.append(' *')
    out.append(' * THE EPOCH IS STORED HERE, BEFORE the caller preps, and that is')
    out.append(' * deliberate in the other direction from the obvious: the value')
    out.append(' * stored is the one READ at this instant, so an SPI write that')
    out.append(' * lands while the prep runs leaves _ctl_epoch AHEAD of what was')
    out.append(' * stored and is picked up on the next block. Storing the epoch')
    out.append(' * read AFTER the prep would swallow it.')
    out.append(' *-------------------------------------------------------------*/')
    out.append('.global _ctl_strip_prep_needed;')
    out.append('_ctl_strip_prep_needed:')
    out.append('    l4 = 0;')
    out.append('    m4 = r0;')
    out.append('    i4 = _ctl_epoch;')
    out.append('    modify(i4, m4);')
    out.append('    r4 = dm(i4, 0);                 /* this strip\'s epoch    */')
    out.append('    i4 = _rtg_ep;')
    out.append('    modify(i4, m4);')
    out.append('    r1 = dm(i4, 0);')
    out.append('    r1 = r1 xor r4;                 /* 0 iff unchanged       */')
    out.append('    i4 = _rtg_busy;')
    out.append('    modify(i4, m4);')
    out.append('    r2 = dm(i4, 0);')
    out.append('    r1 = r1 or r2;                  /* own send ramps        */')
    out.append('    i4 = _fdr_busy_ptrs;')
    out.append('    modify(i4, m4);')
    out.append('    r3 = dm(i4, 0);')
    out.append('    i4 = r3;')
    out.append('    r2 = dm(i4, 0);')
    out.append('    r1 = r1 or r2;                  /* the fader\'s pan ramp  */')
    out.append('    if eq rts;                      /* nothing to do         */')
    out.append('    i4 = _rtg_ep;')
    out.append('    modify(i4, m4);')
    out.append('    dm(i4, 0) = r4;')
    out.append('    r1 = pass r1;                   /* leave AZ clear        */')
    out.append('    rts;')
    out.append('_ctl_strip_prep_needed.end:')
    out.append('#endif')
    out.append('')
    return '\n'.join(out) + '\n'


_CTL_STRIP_RE = re.compile(
    r'^C1_(IN|GAIN|FILT|EQ|GATE|COMP|TUBE|DLY|FDR|RTG|MTR)_(\d{2})$')


def ctl_strip_idx(nid):
    """The epoch slot a chip-1 strip node watches, or None if the node is
    not a chip-1 strip node at all. Chip 2's FADER_PANs and GATEs share the
    generator functions but have no strip page, so they must not gate."""
    m = _CTL_STRIP_RE.match(nid)
    if not m:
        return None
    k = int(m.group(2))
    return k - 1 if 1 <= k <= 32 else None


def ctl_gate(nid, tag, skip_label, busy=()):
    """The control-rate gate prologue (review finding D22).

    THREE INSTRUCTIONS, and the work is in _ctl_strip_prep_needed
    (ctl_epoch.asm). Inline it was nine, but a directly-addressed DM access
    is a LONG VISA instruction and nine of them came to ~41 words per node
    -- 1,320 across the 32 ROUTING nodes, against about 1,400 words left in
    chip 1's code section in the paired 32-strip build. The call costs a
    call/rts and a handful of indexed loads once per node per block, about
    2.5 cycles/sample/strip, against the ~200 the gate saves.

    Emits nothing for a node that has no strip page.
    """
    idx = ctl_strip_idx(nid)
    if idx is None:
        return ''
    return ('        #if DSP4_BLOCK_KERNELS && !DSP4_CTL_ALWAYS\n'
            f'            r0 = {idx};\n'
            '            call _ctl_strip_prep_needed;\n'
            f'            if eq jump (pc, {skip_label});\n'
            '        #endif\n')


def ctl_gate_var(nid, tag):
    """The externs the gate call needs. The gate STATE is indexed, not
    per-node: see _rtg_ep / _rtg_busy in ctl_epoch.asm."""
    if ctl_strip_idx(nid) is None:
        return ''
    return ('        #if DSP4_BLOCK_KERNELS\n'
            '        .extern _ctl_strip_prep_needed;\n'
            '        .extern _rtg_busy;\n'
            '        #endif\n')


def gen_bus_accumulators_fixed():
    """Fixed bus_accumulators.asm: 64-bit pairs per bus + clear."""
    names = (['main_l', 'main_r', 'sub']
             + [f'grp_{g:02d}' for g in range(1, 5)]
             + [f'aux_{a:02d}' for a in range(1, 13)]
             + [f'fx_{x:02d}' for x in range(1, 7)])
    out = []
    out.append('/* bus_accumulators.asm — FIXED (D5): 64-bit exact bus accumulators */')
    out.append('/* AUTO-GENERATED by tools/dsp/dsp_codegen.py (--format fixed) — do not edit. */')
    out.append('/* TRIPLES [lo, hi, ex] = the whole 80-bit MRF (review finding D1);')
    out.append(' * contributions via _acc64_mac / _acc64_mac_blk, readout _acc64_rns28. */')
    out.append('#include "dsp_block.h"')
    out.append('')
    out.append(block_size_guard(
        'The block pool extents and every bus accumulator extent below'))
    out.append('.section/dm seg_dmda;')
    out.append('')
    # SHARED per-strip block buffers. Strips run SEQUENTIALLY (the call
    # chain is strip-ordered: IN GAIN FILT EQ GATE COMP TUBE DLY FDR RTG),
    # so a strip's working set is dead the moment its RTG has accumulated
    # into the buses -- every strip reuses the same slots. One pool of 8
    # slots x BLOCK samples serves all 32 strips, against ~16K words at
    # BLOCK=32 if every node kept its own block buffer.
    out.append('#if DSP4_BLOCK_KERNELS')
    out.append('.global _blk_pool;')
    out.append('#if DSP4_SIMD_STRIPS')
    out.append(f'.var _blk_pool[{9 * BLOCK}];'
               f'    /* 8 slots + the strip-pair park, x{BLOCK} */')
    out.append('#else')
    out.append(f'.var _blk_pool[{8 * BLOCK}];    /* 8 slots x{BLOCK} */')
    out.append('#endif')
    # The odd pool is its OWN array, not slots 9..16 of the first. That is
    # deliberate and it is what the bench reads: a probe can ask the symbol
    # table whether _blk_pool1 exists, and get both "is this a paired-graph
    # build" and "where does the odd strip's chain live" from one lookup,
    # instead of computing an offset that only a matching build makes true.
    out.append('#if DSP4_PAIRED_GRAPH')
    out.append('.global _blk_pool1;')
    out.append(f'.var _blk_pool1[{8 * BLOCK}];   '
               f'/* the ODD strip of each pair, 8 slots x{BLOCK} */')
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
    # THESE ARE NOW INTERNAL, and that is the single biggest thing in the
    # fabric. Measured 2026-08-27 on the part: buses + sends cost 52,427
    # cycles/block, 61 % of an 86,212-cycle fabric, which is 32.8
    # cycles/sample for what is one round-and-saturate per bus. The
    # arithmetic does not explain that; the ADDRESS does. Every
    # _acc64_mac_blk reads two words and writes two words per sample per
    # live crosspoint, and every readout reads two more, and all of it was
    # going to L2 at 0x20000000 -- off-core, and contending with the DMA
    # that is streaming audio through the same fabric.
    #
    # They lived in L2 because putting them internal "overflowed sec_stak"
    # (2026-08-24). That was never a memory limit: sec_stak was declared
    # AFTER sec_dmda in the LDF, so Block 0 had to hold everything while
    # the overflow region sat at 0 %. With the reserve declared first
    # (2026-08-27) chip 1 has ~178 KB of DM free and these 1,600 words fit
    # with room to spare.
    out.append('#if DSP4_BLOCK_KERNELS')
    for n in names:
        out.append(f'.global _bus_acc_{n};   .var _bus_acc_{n}[{3 * BLOCK}];')
    out.append('#else')
    for n in names:
        out.append(f'.global _bus_acc_{n};   .var _bus_acc_{n}[3];')
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
    out.append('        /* 3 x BLOCK: one [lo, hi, ex] TRIPLE per SAMPLE.')
    out.append('         * It was 2 x BLOCK while the accumulator was 64-bit,')
    out.append('         * and a literal 64 before that -- right only at')
    out.append('         * BLOCK=32; at BLOCK=8 each bus zeroed 48 words past')
    out.append('         * its own array. */')
    out.append('        r3 = 3*DSP4_BLOCK_SIZE;')
    out.append('        lcntr = r3, do .bca_clr_in until lce;')
    out.append('    .bca_clr_in:')
    out.append('            dm(i3, 1) = r0;')
    out.append('    .bca_clr:')
    out.append('        nop;')
    out.append('#else')
    out.append('    lcntr = r1, do .bca_clr until lce;')
    out.append('        r2 = dm(i2, 1);')
    out.append('        i3 = r2;')
    out.append('        dm(i3, 1) = r0;      /* lo */')
    out.append('        dm(i3, 1) = r0;      /* hi */')
    out.append('    .bca_clr:')
    out.append('        dm(i3, 0) = r0;      /* ex */')
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
    out.append('/* i0 = source array (BLOCK words), i2 = accumulator (BLOCK')
    out.append(' * [lo, hi, ex] TRIPLES), r1 = gain Q4.28. Exact: no rounding')
    out.append(' * here, one round happens at readout in _acc64_rns28.')
    out.append(' *')
    out.append(' * THE THIRD WORD IS MR2F and it is review finding D1. The')
    out.append(' * pair form discarded it and rebuilt it from the sign of hi,')
    out.append(' * which caps the accumulator at 64-bit Q8.56 = +/-128.0 with')
    out.append(' * nothing saturating it -- and the readout then checked a')
    out.append(' * value that had already wrapped. Cost of the third word is')
    out.append(' * +3 instructions per MAC here; see lib/mac64_fx.asm for the')
    out.append(' * trade against a saturating 64-bit accumulate. */')
    out.append('_acc64_mac_blk:')
    out.append('    l0 = 0;')
    out.append('    l2 = 0;')
    out.append('    r5 = DSP4_BLOCK_SIZE;')
    out.append('    lcntr = r5, do .amb_lp until lce;')
    out.append('        r0 = dm(i0, 1);')
    out.append('        r2 = dm(i2, 1);            /* lo; i2 -> hi */')
    out.append('        mr0f = r2;')
    out.append('        r2 = dm(i2, 1);            /* hi; i2 -> ex */')
    out.append('        mr1f = r2;')
    out.append('        r2 = dm(i2, 0);            /* ex           */')
    out.append('        mr2f = r2;')
    out.append('        mrf = mrf + r0 * r1 (ssi);')
    out.append('        r2 = mr2f;')
    out.append('        dm(i2, -1) = r2;           /* ex; i2 -> hi */')
    out.append('        r2 = mr1f;')
    out.append('        dm(i2, -1) = r2;           /* hi; i2 -> lo */')
    out.append('        r2 = mr0f;')
    out.append('    .amb_lp:')
    out.append('        dm(i2, 3) = r2;            /* lo; i2 -> next triple */')
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
                r6 = DSP4_BLOCK_SIZE;
                comp(r4, r6);
                if lt r6 = r4;                /* n = min(frames, BLOCK) */
                r4 = r4 - r6;
                dm(i6, 1) = r4;
        #if DSP4_BLOCK_KERNELS && !DSP4_CTL_ALWAYS
                /* D22: "is any send ramp still running?", accumulated where
                 * the frame count is already in a register. The min() above
                 * clamps frames at zero, so OR is enough to ask it. */
                r11 = r11 or r4;
        #endif
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
    # D22 control-rate gate. This node's prep is the largest floor gap in
    # the strip; it runs only when the strip's control epoch has moved, or
    # while one of its own send ramps or the fader's pan ramp is running.
    gate = ctl_gate(nid, 'rtg', f'.rtg_acc_{nid}')
    gate_var = ctl_gate_var(nid, 'rtg')
    strip_idx = ctl_strip_idx(nid)
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
        #if DSP4_BLOCK_KERNELS
        .extern _fdr_busy_{fdr_id};
        .extern _ctl_epoch;
        #endif
        /* CONTROL-RATE GATE (review finding D22). This node's whole prep
         * section -- 18 send ramps, 18 pickoff resolutions and the
         * 25-crosspoint list rebuild -- ran EVERY BLOCK for state that
         * changes only when the host writes a parameter or while a ramp is
         * running. At BLOCK=8 that measured 232.6 cycles/sample against a
         * floor of 8-15, the largest gap in the strip.
         *
         * _rtg_ep holds the control epoch this node last prepped at and is
         * compared against _ctl_epoch[strip], which the SPI handler bumps on
         * any accepted write into this strip's 144-word page. _rtg_busy is
         * set while any of this node's own 18 send ramps still has frames
         * left; _fdr_busy_{fdr_id} is the same for the fader, whose pan legs
         * this node's main L/R coefficients are computed from.
         *
         * NOTHING IN THE AUDIO PATH MOVES. The prep is idempotent on
         * unchanged inputs -- it recomputes the same coefficients and stores
         * them over themselves -- so not running it is exact, not
         * approximate. DSP4_CTL_ALWAYS=1 restores the unconditional prep in
         * the same image as the negative control. */
{gate_var}
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

{gate}
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

        #if DSP4_BLOCK_KERNELS && !DSP4_CTL_ALWAYS
            r11 = 0;                      /* "any send ramp still running" */
        #endif
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

        #if DSP4_BLOCK_KERNELS && !DSP4_CTL_ALWAYS
            /* Ramps are not SPI writes, so the epoch never sees them: while
             * any send ramp still has frames its coefficient changes every
             * block, and the prep has to keep running. r11 was accumulated
             * inside the two send-ramp loops above, where the frame count
             * was already in a register -- one instruction each, against the
             * ten a separate 18-word scan cost, in a PM section with about a
             * thousand words left in the paired build. It survives the
             * pickoff-resolution and list-build loops between them; neither
             * of those touches r11. */
            dm(_rtg_busy + {strip_idx}) = r11;
        #endif

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
            r15 = DSP4_BLOCK_SIZE;
            r4 = r4 - r15;
            if le jump (pc, .no_auxramp_{nid});
            dm(_auxin_level_frames_{nid}) = r4;
            f1 = dm(_auxin_level_{nid});
            f2 = dm(_auxin_level_step_{nid});
            r15 = DSP4_BLOCK_F32;             /* BLOCK_SIZE as float */
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
            r15 = DSP4_BLOCK_SIZE;
            r4 = r4 - r15;
            if le jump (pc, .no_monramp_{side}_{nid});
            dm(_mon_level_{side}_frames_{nid}) = r4;
            f1 = dm(_mon_level_{side}_{nid});
            f2 = dm(_mon_level_{side}_step_{nid});
            r15 = DSP4_BLOCK_F32;             /* BLOCK_SIZE as float */
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
        .var _talk_hpf_cq_{nid}[5] = 0x10000000, 0x10000000, 0xF0000000, 0x20000000, 0x10000000;
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
             * by DSP4_BLOCK_SIZE, which is right for the ramps that
             * decrement once per SAMPLE. This one decrements once per
             * BLOCK, so taking 1 per block ran it BLOCK times long:
             * measured 2026-08-23 at BLOCK=32, a GainSafe down-ramp took
             * 960 ms against the 30 ms its own cell table specifies, and a
             * GainFast fader move took 85 ms instead of 3 ms. A power of
             * two is exact in binary, so scaling the step loses nothing. */
            r4 = dm(_talk_gain_frames_{nid});
            r15 = 0;
            comp(r4, r15);
            if le jump (pc, .no_tkramp_{nid});
            r15 = DSP4_BLOCK_SIZE;
            r4 = r4 - r15;
            dm(_talk_gain_frames_{nid}) = r4;
            f1 = dm(_talk_gain_{nid});
            f2 = dm(_talk_gain_step_{nid});
            r15 = DSP4_BLOCK_F32;             /* BLOCK_SIZE as float */
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
    # SIMD (DSP4_SIMD_DYN) needs the SAME coefficient in both compute
    # units. A SIMD data access reads TWO CONSECUTIVE WORDS -- PEx takes
    # the addressed word and PEy the one after it -- so walking the table
    # above with modifier 2 would hand PEy C[k+1] where it wants C[k].
    # These are the same integers with every entry doubled, so one
    # dm(i0, 2) broadcasts. Doubled here rather than copied at run time
    # so there is still exactly one source for the numbers.
    out.append('#if DSP4_SIMD_DYN')
    for name, poly in (('_log2_poly_dup', fixed_ref.LOG2_POLY),
                       ('_exp2_poly_dup', fixed_ref.EXP2_POLY)):
        pairs = []
        for c in poly:
            w = '0x%08X' % (c & 0xFFFFFFFF)
            pairs.append(w + ', ' + w)
        out.append('.global %s;' % name)
        out.append('.var %s[12] =\n    ' % name + ',\n    '.join(pairs) + ';')
    out.append('#endif')
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

    # WIDE-WORD METERING (PW ruling 2026-08-29), 'scalar' shape. Chip 2's
    # bus compressors finish in the ALU (`r0 = r13 + r1`), not in a product
    # register, so there is no MS word to take: the wide form at this tap
    # point IS r0. It is published in the meter's Q8.24 format so one fold
    # serves every meter. These nodes have no block kernel, so their meters
    # still see one word per block -- recorded on the meter, not hidden.
    _mtr = node['params'].get('mtr_sink', '')
    mtr_decl = ('' if not _mtr else
                f"        .var _mtr_wide_{node['id']};\n")
    mtr_pub = ('' if not _mtr else
               f'            r1 = ashift r0 by -4;    /* Q4.28 -> Q8.24 */\n'
               f"            dm(_mtr_wide_{node['id']}) = r1;\n")

    """Fixed COMPRESSOR (D5): fixed envelope + _compgain_fx (log2
    domain, soft knee) per fixed_ref; float control converted at block
    rate; makeup + parallel blend fixed."""
    rc = ramp_comment(node['ramp_profile'])
    nid = node['id']
    inp = node['inputs_str']
    par_pct, par_q = comp_par_default(node['params'])
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
        .var _comp_parallel_{nid} = {par_pct};   /* PERCENT (D40); fully wet by default (D59) */
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
        .var _comp_parq_{nid} = 0x{par_q:08X};   /* Q0.31, = _comp_parallel_ converted */
        .var _comp_cgp_{nid}[4];              /* thr, slope, halfk, k2 */
        .var _buf_{nid};
{mtr_decl}
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
             * by DSP4_BLOCK_SIZE, which is right for the ramps that
             * decrement once per SAMPLE. This one decrements once per
             * BLOCK, so taking 1 per block ran it BLOCK times long:
             * measured 2026-08-23 at BLOCK=32, a GainSafe down-ramp took
             * 960 ms against the 30 ms its own cell table specifies, and a
             * GainFast fader move took 85 ms instead of 3 ms. A power of
             * two is exact in binary, so scaling the step loses nothing. */
            r5 = DSP4_BLOCK_SIZE;
            r4 = r4 - r5;
            dm(_comp_makeup_frames_{nid}) = r4;
            f1 = dm(_comp_makeup_{nid});
            f2 = dm(_comp_makeup_step_{nid});
            r5 = DSP4_BLOCK_F32;              /* BLOCK_SIZE as float */
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
            /* PARALLEL BLEND IS PERCENT ON THE WIRE (review finding
             * D40). The master documents Chan[1-32]CompPar as 0-100 %
             * (d32-mx-master.csv, table 0=0/127=100); this used to
             * multiply the raw wire value by 2^31 with no /100, so any
             * documented value of 1 % or more pinned the blend fully wet
             * and the control could not take an intermediate setting at
             * all. The masters win: clamp to the documented 0..100 and
             * scale by 2^31/100. */
            f1 = dm(_comp_parallel_{nid});
            r2 = 0x00000000;              /* 0 %, documented minimum */
            f2 = r2;
            comp(f1, f2);
            if lt f1 = f2;
            r2 = 0x42C80000;              /* 100 %, documented maximum */
            f2 = r2;
            comp(f1, f2);
            if gt f1 = f2;
            r2 = 0x4BA3D70A;              /* 2^31 / 100 */
            f2 = r2;
            f1 = f1 * f2;
            r1 = fix f1;
            /* CLAMP. parallel = 100 % scales to exactly 2^31, which int32 cannot
             * hold: `fix` wraps and stores -1, so in Q0.31 the MAXIMUM
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
{mtr_pub}            rts;
        .comp_bypass_{nid}:
            dm(_buf_{nid}) = r0;
{mtr_pub}            rts;
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
        #if !DSP4_PAIRED_GRAPH
        .var _gate_hold_count_{nid} = 0;
        #endif
        .var _gate_range_{nid} = 0.001;       /* linear floor (float) */
        .var _gate_key_src_{nid} = 0;
        .var _gate_det_src_{nid} = 0;
        .var _gate_filter_on_{nid} = 0;
        .var _gate_filter_hpf_{nid}[5] = 1.0, 0.0, 0.0, 0.0, 0.0;
        .var _gate_filter_lpf_{nid}[5] = 1.0, 0.0, 0.0, 0.0, 0.0;
        .var _gate_filter_cq_{nid}[10];
        .var _gate_filter_state_{nid}[12];
        /* DECLARATION ORDER IS THE PAIR INTERFACE. _gate_pair_blk gathers
         * and scatters the gate STATE as four consecutive words
         * (env, gain, target, hold count) and reads its PARAMETERS as five
         * (attq, relq, thrq, rngq, hold), so under a paired graph the hold
         * count moves next to the other three state words and `hold` gets
         * a converted twin next to the other four parameters. Both moves
         * are guarded, so a build without pairing keeps the old layout and
         * therefore the old bytes. */
        .var _gate_envelope_{nid} = 0;
        .var _gate_gain_{nid} = 0x10000000;
        .var _gate_gain_target_q_{nid} = 0x10000000;
        #if DSP4_PAIRED_GRAPH
        .var _gate_hold_count_{nid} = 0;
        #endif
        .var _gate_attq_{nid} = 0;
        .var _gate_relq_{nid} = 0;
        .var _gate_thrq_{nid} = 0;
        .var _gate_rngq_{nid} = 0;
        #if DSP4_PAIRED_GRAPH
        .var _gate_holdq_{nid} = 2400;
        #endif
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
            /* GATE RANGE IS DECIBELS ON THE WIRE (review finding D39).
             * The master documents Chan[1-32]GateRng as depth in dB
             * (d32-mx-master.csv, table 0=0/127=60, note "Gate
             * depth/range 0-60dB"). This used to scale the wire float
             * straight by 2^28 and use it as a LINEAR floor, so a host
             * writing the documented 40.0 got 40.0 x 2^28 -- saturated
             * garbage -- and the deepest gate the protocol can ask for
             * produced no attenuation at all. dsp_simulate.py:237 has
             * always performed this conversion, which is what proved the
             * convention was dB before it was ever measured.
             *
             * CELL SEMANTICS ARE THE CONTRACT AND THE MASTERS WIN, so the
             * conversion belongs here: floor = 10^(-dB/20), which is
             * 2^(-dB * log2(10)/20), clamped to the documented 0..60 dB.
             * It is BLOCK RATE -- this whole section sits behind the
             * _sample_idx == 0 guard -- and _exp2q_fx preserves r6-r15 in
             * both its table and polynomial forms, so the live sample in
             * r13 survives the call. */
            f1 = dm(_gate_range_{nid});
            r2 = 0x00000000;              /* 0 dB, documented minimum */
            f2 = r2;
            comp(f1, f2);
            if lt f1 = f2;
            r2 = 0x42700000;              /* 60 dB, documented maximum */
            f2 = r2;
            comp(f1, f2);
            if gt f1 = f2;
            r2 = 0xBE2A152D;              /* -log2(10)/20 */
            f2 = r2;
            f1 = f1 * f2;
            r2 = 0x4C000000;              /* x 2^25 -> Q6.25 for _exp2q_fx */
            f2 = r2;
            f1 = f1 * f2;
            r0 = fix f1;
            call _exp2q_fx;               /* r0 = 2^l, Q4.28 */
            dm(_gate_rngq_{nid}) = r0;
        #if DSP4_PAIRED_GRAPH
            r1 = dm(_gate_hold_{nid});
            dm(_gate_holdq_{nid}) = r1;   /* five consecutive param words */
        #endif
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
    'METER': gen_meter_fixed,
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


# ---------------------------------------------------------------------------
# SIMD STRIP PAIRING (DSP4_SIMD_DYN)
#
# The kernels have paired the dynamics since 2026-08-28 and measured
# 2.04-2.12x on COMP and 2.36-2.54x on GATE -- but nothing in the GRAPH ran
# paired, because the chain is STRIP-ORDERED and the block pool is reused
# strip by strip: strip N+1's block does not exist while strip N is running,
# so a pair could never hold two live channels.
#
# What makes it work is not a park and a copy. It is TWO POOLS. The ODD
# strip of each pair is GENERATED against a second set of slot macros
# (BLK_*_P1) and the even strip keeps the originals, so both strips' whole
# working sets -- chain ping-pong AND the three taps the router reads in the
# TAIL, which is what a single parked slot could never cover -- are live at
# the same moment, at zero copying cost. With DSP4_SIMD_DYN off the P1 names
# alias the originals (blk_pool.h) and the image is byte-identical.
#
# The chain then runs, per pair:
#     A: IN GAIN FILT EQ        (odd strip, pool 1)
#     B: IN GAIN FILT EQ        (even strip, pool 0)
#     GATE pair, COMP pair      (one channel from each pool)
#     A: TUBE DLY FDR RTG
#     B: TUBE DLY FDR RTG
#
# The paired dynamics run IN PLACE on each pool's BLK_CHAIN_B, which is the
# same net slot movement as the scalar ping-pong (B --GATE--> A --COMP--> B),
# so the tails need no change at all. The RTG order within a pair is A then
# B as before; bus accumulation is exact 64-bit integer addition, so strip
# order cannot change a bus sum in any case.
# ---------------------------------------------------------------------------

# The classes that make up a channel strip, in chain order, split at the
# dynamics. Only chip 1 has these -- chip 2's dynamics are C2_GRP_COMP,
# C2_MAIN_COMP and friends, which have no block kernel and no pair.
_STRIP_HEAD = ('IN', 'GAIN', 'FILT', 'EQ')
# Where the head splits when the BIQUADS pair too (DSP4_BQ_GRAPH):
# IN and GAIN stay per strip, FILT and EQ become pair calls.
_STRIP_HEAD_SCALAR = ('IN', 'GAIN')
_STRIP_BQ = ('FILT', 'EQ')
_STRIP_DYN  = ('GATE', 'COMP')
_STRIP_TAIL = ('TUBE', 'DLY', 'FDR', 'RTG')
_STRIP_TYPES = _STRIP_HEAD + _STRIP_DYN + _STRIP_TAIL

_STRIP_NODE_RE = re.compile(
    r'^C(\d+)_(' + '|'.join(_STRIP_TYPES) + r')_(\d+)$')

# Every pool slot a strip node can name. The odd strip of a pair gets the
# _P1 twin of each.
_POOL_SLOT_RE = re.compile(
    r'\b(BLK_CHAIN_A|BLK_CHAIN_B|BLK_FDR_L|BLK_FDR_R|BLK_TAP_TRIM'
    r'|BLK_TAP_EQ|BLK_TAP_PREFDR|BLK_TAP_POSTFDR)\b')


def _odd_pool(text):
    """Rewrite a generated node body onto the odd pool's slot macros."""
    return _POOL_SLOT_RE.sub(lambda m: m.group(1) + '_P1', text)


def _strip_index(nid):
    """1-based strip number of a strip node, or None."""
    m = _STRIP_NODE_RE.match(nid)
    return int(m.group(3)) if m else None


def gen_dyn_pairs(chip_label, strips, meter_src):
    """chipN/dyn_pairs.asm — one driver per paired class per strip pair.

    A driver is a NODE as far as the chain is concerned: it is called once
    per block and it leaves its pair's two channels exactly where the two
    scalar nodes would have left them.

    THE BLOCK-RATE CONVERSION IS NOT DUPLICATED HERE. Both dynamics classes
    convert their control parameters once per block inside their own
    per-sample body, behind the `_sample_idx == 0` guard, and the scalar
    COMPRESSOR block kernel already drives that body for sample 0 for
    exactly this reason. The driver does the same for both channels and
    hands the pair kernel the remaining BLOCK-1 samples through _dsim_n.
    That is what makes sample 0 bit-identical to the scalar path by
    construction rather than by inspection, and it is why there is no
    second copy of the conversion arithmetic to drift.

    THE FALLBACK IS NET-PRESERVING. A pair whose channels disagree -- one
    gate off, one sidechain filter on, one compressor bypassed -- cannot
    run paired, and the two scalar nodes ping-pong B->A->B across the two
    of them. The driver therefore calls the scalar nodes and squares the
    slots up itself, so that "the dynamics section reads BLK_CHAIN_B and
    writes BLK_CHAIN_B" holds on BOTH paths and the two drivers can make
    their bypass decisions independently.
    """
    out = []
    a = out.append
    a(f'/* {chip_label.upper()} — SIMD strip-pair dynamics drivers */')
    a('/* AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly. */')
    a('#include "dsp_block.h"')
    a('#include "blk_pool.h"')
    a('')
    a('#if DSP4_PAIRED_GRAPH')
    a('')
    a('.section/dm seg_dmda;')
    a('.var _dynpair_saved_idx;')
    a('')
    a('.section/pm seg_pmco;')
    a('.extern _sample_idx;')
    a('.extern _dsim_n;')
    a('.extern _gate_pair_blk;')
    a('.extern _comp_pair_blk;')
    a('.extern _cmp_gn;')

    pairs = []
    nums = sorted(strips)
    for i in range(0, len(nums) - 1, 2):
        pairs.append((nums[i], nums[i + 1]))
    odd_left = nums[-1] if len(nums) % 2 else None

    for sa, sb in pairs:
        for sn in (sa, sb):
            g, c, e = strips[sn]['GATE'], strips[sn]['COMP'], strips[sn]['EQ']
            for sym in (f'_{g}_process', f'_{g}_process_sample',
                        f'_{c}_process', f'_{c}_process_sample',
                        f'_gate_on_{g}', f'_gate_filter_on_{g}',
                        f'_gate_attq_{g}', f'_gate_envelope_{g}',
                        f'_comp_on_{c}', f'_comp_attq_{c}',
                        f'_comp_envelope_{c}', f'_comp_gain_{c}',
                        f'_buf_{e}', f'_buf_{g}', f'_buf_{c}'):
                a(f'.extern {sym};')

    for sa, sb in pairs:
        ga, gb = strips[sa]['GATE'], strips[sb]['GATE']
        ca, cb = strips[sa]['COMP'], strips[sb]['COMP']
        ia, ib = strips[sa]['EQ'], strips[sb]['EQ']
        tag = f'{sa:02d}_{sb:02d}'

        # ---- GATE pair -------------------------------------------------
        a('')
        a(f'/* ---- strips {sa} + {sb}: GATE ---- */')
        a(f'.global _DYNGATE_{tag}_process;')
        a(f'_DYNGATE_{tag}_process:')
        a('    /* Both channels must be on the same path or there is no pair. */')
        for g in (ga, gb):
            a(f'    r0 = dm(_gate_on_{g});')
            a('    r0 = pass r0;')
            a(f'    if eq jump (pc, .dgs_{tag});')
        for g in (ga, gb):
            a(f'    r0 = dm(_gate_filter_on_{g});')
            a('    r0 = pass r0;')
            a(f'    if ne jump (pc, .dgs_{tag});')
        a('')
        a('    /* sample 0 through each channel\'s own per-sample body: that is')
        a('     * where the block-rate parameter conversion lives. */')
        a('    r5 = dm(_sample_idx);')
        a('    dm(_dynpair_saved_idx) = r5;')
        a('    r5 = 0;')
        a('    dm(_sample_idx) = r5;')
        for g, inp, slot in ((ga, ia, 'BLK_CHAIN_B_P1'), (gb, ib, 'BLK_CHAIN_B')):
            a(f'    r0 = dm({slot});')
            a(f'    dm(_buf_{inp}) = r0;')
            a(f'    call _{g}_process_sample;')
            a(f'    r0 = dm(_buf_{g});')
            a(f'    dm({slot}) = r0;')
        a('    r5 = dm(_dynpair_saved_idx);')
        a('    dm(_sample_idx) = r5;')
        a('')
        a('    /* samples 1..BLOCK-1, two channels in one instruction stream */')
        a('    r0 = DSP4_BLOCK_SIZE-1;')
        a('    dm(_dsim_n) = r0;')
        a('    dm(_dsim_n + 1) = r0;')
        a(f'    r4 = _gate_attq_{ga};        /* attq relq thrq rngq hold */')
        a(f'    r5 = _gate_attq_{gb};')
        a(f'    r6 = _gate_envelope_{ga};    /* env gain target holdcount */')
        a(f'    r7 = _gate_envelope_{gb};')
        a('    r0 = BLK_CHAIN_B_P1;')
        a('    r1 = 1;')
        a('    r8 = r0 + r1;')
        a('    r0 = BLK_CHAIN_B;')
        a('    r9 = r0 + r1;')
        a('    call _gate_pair_blk;')
        a('    rts;')
        a('')
        a(f'.dgs_{tag}:')
        a('    /* scalar fallback, squared up to B-in/B-out per pool */')
        a(f'    call _{ga}_process;          /* B_P1 -> A_P1 */')
        a('    l3 = 0; l4 = 0;')
        a('    i3 = BLK_CHAIN_A_P1;')
        a('    i4 = BLK_CHAIN_B_P1;')
        a(f'    lcntr = DSP4_BLOCK_SIZE, do .dgs_c1_{tag} until lce;')
        a('        r0 = dm(i3, 1);')
        a(f'    .dgs_c1_{tag}: dm(i4, 1) = r0;')
        a(f'    call _{gb}_process;          /* B -> A */')
        a('    i3 = BLK_CHAIN_A;')
        a('    i4 = BLK_CHAIN_B;')
        a(f'    lcntr = DSP4_BLOCK_SIZE, do .dgs_c2_{tag} until lce;')
        a('        r0 = dm(i3, 1);')
        a(f'    .dgs_c2_{tag}: dm(i4, 1) = r0;')
        a('    rts;')
        a(f'_DYNGATE_{tag}_process.end:')

        # ---- COMP pair -------------------------------------------------
        a('')
        a(f'/* ---- strips {sa} + {sb}: COMP ---- */')
        a(f'.global _DYNCOMP_{tag}_process;')
        a(f'_DYNCOMP_{tag}_process:')
        for c in (ca, cb):
            a(f'    r0 = dm(_comp_on_{c});')
            a('    r0 = pass r0;')
            a(f'    if eq jump (pc, .dcs_{tag});')
        a('')
        a('    r5 = dm(_sample_idx);')
        a('    dm(_dynpair_saved_idx) = r5;')
        a('    r5 = 0;')
        a('    dm(_sample_idx) = r5;')
        for c, g, slot in ((ca, ga, 'BLK_CHAIN_B_P1'), (cb, gb, 'BLK_CHAIN_B')):
            a(f'    r0 = dm({slot});')
            a(f'    dm(_buf_{g}) = r0;')
            a(f'    call _{c}_process_sample;')
            a(f'    r0 = dm(_buf_{c});')
            a(f'    dm({slot}) = r0;')
        a('    r5 = dm(_dynpair_saved_idx);')
        a('    dm(_sample_idx) = r5;')
        a('')
        a('    r0 = DSP4_BLOCK_SIZE-1;')
        a('    dm(_dsim_n) = r0;')
        a('    dm(_dsim_n + 1) = r0;')
        a(f'    r4 = _comp_attq_{ca};        /* attq relq mkq parq thr slope halfk k2 */')
        a(f'    r5 = _comp_attq_{cb};')
        a(f'    r6 = _comp_envelope_{ca};')
        a(f'    r7 = _comp_envelope_{cb};')
        a('    r0 = BLK_CHAIN_B_P1;')
        a('    r1 = 1;')
        a('    r8 = r0 + r1;')
        a('    r0 = BLK_CHAIN_B;')
        a('    r9 = r0 + r1;')
        a('    call _comp_pair_blk;')
        a('    /* the pair writes its gain display to the shared park; give it')
        a('     * back to each node so dsp4_dyn_witness.py still reads a live')
        a('     * per-strip compressor gain. */')
        a('    i0 = _cmp_gn;')
        a('    r0 = dm(i0, 1);')
        a(f'    dm(_comp_gain_{ca}) = r0;')
        a('    r0 = dm(i0, 1);')
        a(f'    dm(_comp_gain_{cb}) = r0;')
        a('    rts;')
        a('')
        a(f'.dcs_{tag}:')
        a('    /* scalar fallback, squared up to B-in/B-out per pool */')
        a('    l3 = 0; l4 = 0;')
        a('    i3 = BLK_CHAIN_B_P1;')
        a('    i4 = BLK_CHAIN_A_P1;')
        a(f'    lcntr = DSP4_BLOCK_SIZE, do .dcs_c1_{tag} until lce;')
        a('        r0 = dm(i3, 1);')
        a(f'    .dcs_c1_{tag}: dm(i4, 1) = r0;')
        a(f'    call _{ca}_process;          /* A_P1 -> B_P1 */')
        a('    i3 = BLK_CHAIN_B;')
        a('    i4 = BLK_CHAIN_A;')
        a(f'    lcntr = DSP4_BLOCK_SIZE, do .dcs_c2_{tag} until lce;')
        a('        r0 = dm(i3, 1);')
        a(f'    .dcs_c2_{tag}: dm(i4, 1) = r0;')
        a(f'    call _{cb}_process;          /* A -> B */')
        a('    rts;')
        a(f'_DYNCOMP_{tag}_process.end:')

    if odd_left is not None:
        a('')
        _odd_pool = '_P1 (odd)' if odd_left % 2 else 'base (even)'
        a(f'/* strip {odd_left} has no partner: it runs its two dynamics nodes')
        a(' * scalar, in place in the chain. Nothing is emitted here for it.')
        a(' *')
        a(' * WHICH POOL: pool parity follows the STRIP NUMBER, not the')
        a(' * position in the pair list -- see `if sn % 2` below, which puts')
        a(' * every odd-numbered strip on _P1. The unpaired tail is the')
        a(' * highest strip number of an odd-sized set, so it is odd, so it')
        a(f' * runs on the {_odd_pool} pool. (This comment said "the EVEN')
        a(' * pool" until 2026-08-29 -- review finding D9. Dead today: 32')
        a(' * strips pair evenly and each node file is generated')
        a(' * self-consistently either way, but it would have misled the')
        a(' * first odd-count product.) */')

    a('')
    a('#if DSP4_GATE_LINTHR')
    a('#error "DSP4_SIMD_DYN pairs the GATE in the log2 domain; '
      'DSP4_GATE_LINTHR converts the threshold to linear once per block '
      'and the two are different arithmetic. Build with DSP4_GATE_LINTHR=0."')
    a('#endif')
    a('#if !DSP4_BLOCK_KERNELS')
    a('#error "DSP4_SIMD_GRAPH is a per-BLOCK pairing: build with '
      'DSP4_BLOCK_KERNELS=1."')
    a('#endif')
    a('')
    a('#endif /* DSP4_PAIRED_GRAPH */')
    return '\n'.join(out) + '\n'


# ---------------------------------------------------------------------------
# BIQUAD STRIP PAIRING IN THE GRAPH (2026-08-29)
#
# The dynamics have been pair-ordered in the graph since 2026-08-28 and the
# biquads have not, for one reason: _bq_pair_blk HUNG. That was root-caused
# on 2026-08-29 (a clobbered register, five words of DM) and the paired
# cascade measured at 1.43-1.54x, but nothing in the graph called it.
#
# This is the same wiring the dynamics got, one class earlier in the strip:
#
#     A: IN GAIN          (odd strip, pool 1)
#     B: IN GAIN          (even strip, pool 0)
#     FILT pair, EQ pair  <-- new
#     GATE pair, COMP pair
#     A: TUBE DLY FDR RTG
#     B: TUBE DLY FDR RTG
#
# It is SAFE TO REORDER because both classes work IN PLACE on their own
# pool's BLK_CHAIN_B: A's GAIN output sits in BLK_CHAIN_B_P1 while B's IN and
# GAIN run on the base pool, so no slot is read by one strip while the other
# writes it. That is the same property the two-pool design was built for.
#
# THE FALLBACK IS THE SCALAR NODES, unchanged. A pair whose channels are not
# both in steady state -- a coefficient swap staged, a crossfade running --
# cannot run paired, and the driver calls the two nodes' own block bodies,
# which handle exactly those cases and work in place. So "the biquad section
# reads BLK_CHAIN_B and writes BLK_CHAIN_B" holds on both paths, per pool,
# and neither driver has to know what the other decided.
_BQ_PAIR_CLASSES = ('FILT', 'EQ')


def _bq_pair_ptrs(cls, nid, rc='r8', rs='r9'):
    """Pick the ACTIVE instance's coefficient and state bases into the
    registers _bq_pair_blk wants them in.

    Conditional MOVES, not a branch: two `if eq` in a row read the ASTAT
    that `pass` set, and nothing between them touches the flags. The
    DESTINATION is a parameter so each strip lands in its final register --
    selecting both into r8/r9 and shuffling afterwards cost six
    instructions a pair, which is 1,152 bytes of a chip that has under two
    thousand left.
    """
    if cls == 'FILT':
        a_c, a_s = f'_filt_hpf_A_{nid}', f'_filt_state_A_{nid}'
        b_c, b_s = f'_filt_hpf_B_{nid}', f'_filt_state_B_{nid}'
        act = f'_filt_active_{nid}'
    else:
        a_c, a_s = f'_eq_coeffs_A_{nid}', f'_eq_state_A_{nid}'
        b_c, b_s = f'_eq_coeffs_B_{nid}', f'_eq_state_B_{nid}'
        act = f'_eq_active_{nid}'
    return [f'    r2 = {a_c};', f'    r3 = {a_s};',
            f'    {rc} = {b_c};', f'    {rs} = {b_s};',
            f'    r0 = dm({act});', '    r0 = pass r0;',
            f'    if eq {rc} = r2;', f'    if eq {rs} = r3;']


def _bq_pair_steady(cls, nid):
    """OR together everything that takes this node off the steady-state
    path. Non-zero in r1 means the pair cannot run."""
    if cls == 'FILT':
        syms = (f'_hpf_swap_pending_{nid}', f'_lpf_swap_pending_{nid}',
                f'_filt_xfade_step_{nid}')
    else:
        syms = (f'_eq_swap_pending_{nid}', f'_eq_xfade_step_{nid}')
    out = []
    for sym in syms:
        out.append(f'    r0 = dm({sym});')
        out.append('    r1 = r1 or r0;')
    return out


def gen_bq_pairs(chip_label, strips, bands_of):
    """chipN/bq_pairs.asm — one driver per paired biquad class per pair."""
    out = []
    a = out.append
    a(f'/* {chip_label.upper()} — SIMD strip-pair biquad drivers */')
    a('/* AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly. */')
    a('#include "dsp_block.h"')
    a('#include "blk_pool.h"')
    a('')
    a('#if DSP4_BQ_PAIRED_GRAPH')
    a('')
    a('.section/pm seg_pmco;')
    a('.extern _bq_pair_blk;')
    a('')
    a('/* The post-EQ tap copy, ONCE. Every pair copies the same two pool')
    a(' * slots to the same two tap slots -- the addresses are macros, not')
    a(' * per-pair facts -- so sixteen copies of this loop were 1,850 bytes')
    a(' * of chip 1\'s program memory for nothing, and chip 1 has 926 bytes')
    a(' * of it left. */')
    a('.global _bqp_tap_eq;')
    a('_bqp_tap_eq:')
    a('    l3 = 0; l4 = 0;')
    a('    i3 = BLK_CHAIN_B_P1;')
    a('    i4 = BLK_TAP_EQ_P1;')
    a('    lcntr = DSP4_BLOCK_SIZE, do .bqt1 until lce;')
    a('        r0 = dm(i3, 1);')
    a('    .bqt1: dm(i4, 1) = r0;')
    a('    i3 = BLK_CHAIN_B;')
    a('    i4 = BLK_TAP_EQ;')
    a('    lcntr = DSP4_BLOCK_SIZE, do .bqt2 until lce;')
    a('        r0 = dm(i3, 1);')
    a('    .bqt2: dm(i4, 1) = r0;')
    a('    rts;')
    a('_bqp_tap_eq.end:')

    nums = sorted(strips)
    pairs = [(nums[i], nums[i + 1]) for i in range(0, len(nums) - 1, 2)]

    for sa, sb in pairs:
        for sn in (sa, sb):
            f, e = strips[sn]['FILT'], strips[sn]['EQ']
            for sym in (f'_{f}_process', f'_hpf_swap_pending_{f}',
                        f'_lpf_swap_pending_{f}', f'_filt_xfade_step_{f}',
                        f'_filt_active_{f}', f'_filt_hpf_A_{f}',
                        f'_filt_state_A_{f}', f'_filt_hpf_B_{f}',
                        f'_filt_state_B_{f}',
                        f'_{e}_process', f'_eq_swap_pending_{e}',
                        f'_eq_xfade_step_{e}', f'_eq_active_{e}',
                        f'_eq_coeffs_A_{e}', f'_eq_state_A_{e}',
                        f'_eq_coeffs_B_{e}', f'_eq_state_B_{e}'):
                a(f'.extern {sym};')

    for sa, sb in pairs:
        tag = f'{sa:02d}_{sb:02d}'
        for cls in _BQ_PAIR_CLASSES:
            na, nb = strips[sa][cls], strips[sb][cls]
            # FILT is always two stages -- HPF then LPF, adjacent
            # coefficient blocks, one 2x6 state array. EQ's length is its
            # band count, and a pair is ONE instruction stream.
            stages = 2 if cls == 'FILT' else bands_of[na]
            stages_b = 2 if cls == 'FILT' else bands_of.get(nb, stages)
            if stages_b != stages:
                raise ValueError(
                    f'{na} has {stages} stages and {nb} has '
                    f'{stages_b}: a SIMD pair is ONE instruction '
                    f'stream, so the two strips must ask for the same '
                    f'cascade length.')
            if stages > 4:
                raise ValueError(
                    f'{na}: {stages} stages -- _bq_pair_blk\'s interleave '
                    f'scratch is sized for 4 (biquad_fx.asm).')
            a('')
            a(f'/* ---- strips {sa} + {sb}: {cls} ---- */')
            a(f'.global _BQP{cls}_{tag}_process;')
            a(f'_BQP{cls}_{tag}_process:')
            a('    /* Both channels must be in steady state or there is no')
            a('     * pair: a staged coefficient set or a running crossfade')
            a("     * goes through the node's own reference path. */")
            _st = []
            for n in (na, nb):
                _st += _bq_pair_steady(cls, n)
            # The first OR has nothing to OR with, so start from the load.
            assert _st[1] == '    r1 = r1 or r0;'
            _st[0] = _st[0].replace('    r0 = dm(', '    r1 = dm(')
            del _st[1]
            for line in _st:
                a(line)
            a('    r1 = pass r1;')
            a(f'    if ne jump (pc, .bqs_{cls}_{tag});')
            a('')
            for line in _bq_pair_ptrs(cls, na, 'r8', 'r9'):
                a(line)
            a('    r10 = BLK_CHAIN_B_P1;         /* strip A, odd pool */')
            a('#if DSP4_BQ_NEGCTL')
            a('    /* NEGATIVE CONTROL: give strip B strip A\'s coefficient')
            a('     * and state pointers, so the pair computes ONE channel')
            a('     * twice. The bus sum MUST differ, or the comparison that')
            a('     * says the paired graph is bit-exact was not testing')
            a('     * anything. */')
            a('    r11 = r8;')
            a('    r12 = r9;')
            a('#else')
            for line in _bq_pair_ptrs(cls, nb, 'r11', 'r12'):
                a(line)
            a('#endif')
            a('    r13 = BLK_CHAIN_B;            /* strip B, base pool */')
            a(f'    r4 = {stages};')
            a('    call _bq_pair_blk;')
            if cls == 'EQ':
                a('    /* the post-EQ tap the router picks from, both pools */')
                a('    call _bqp_tap_eq;')
            a('    rts;')
            a('')
            a(f'.bqs_{cls}_{tag}:')
            a('    /* scalar fallback: both nodes work IN PLACE on their own')
            a('     * pool, so nothing has to be squared up afterwards. */')
            a(f'    call _{na}_process;')
            a(f'    call _{nb}_process;')
            a('    rts;')
            a(f'_BQP{cls}_{tag}_process.end:')

    if len(nums) % 2:
        a('')
        a(f'/* strip {nums[-1]} has no partner: its FILT and EQ run scalar,')
        a(' * in place in the chain, on the odd pool. Nothing here for it. */')

    a('')
    a('#if !DSP4_BLOCK_KERNELS')
    a('#error "DSP4_BQ_GRAPH is a per-BLOCK pairing: build with '
      'DSP4_BLOCK_KERNELS=1."')
    a('#endif')
    a('')
    a('#endif /* DSP4_BQ_PAIRED_GRAPH */')
    return '\n'.join(out) + '\n'


def process_order_violations(seq, by_id):
    """Every (consumer, i, producer, j) edge in `seq` where a node reads a
    same-chip node that runs LATER in the chain.

    Resolved FROM THE GRAPH (dsp.csv `inputs`), never from the emitted
    call order — that is the whole point. Cross-chip inputs are not
    edges here: they arrive over the TDM fabric, one block delayed by
    construction, and the chain cannot order them.
    """
    pos = {nid: i for i, nid in enumerate(seq)}
    bad = []
    for i, nid in enumerate(seq):
        for src in by_id[nid]['inputs']:
            j = pos.get(src)
            if j is not None and j > i:
                bad.append((nid, i, src, j))
    return bad


def repair_process_order(chip_label, seq, chip_nodes):
    """Order the chain so every producer runs before its consumers.

    Review finding D5: chip 2's main mix read _buf_C2_USB_IN and
    _buf_C2_BT_IN at chain position 157/158 while the only writers of
    those buffers -- the AUX_INPUT nodes themselves -- ran at 196/197.
    The mix therefore took whatever those buffers held from the PREVIOUS
    sample. That is the wrong-graph-order class, and it was in the
    shipping image.

    This is a MINIMAL, STABLE repair, not a topological sort: the chain
    keeps its dsp.csv order except where a dependency forces a move, and
    each violating producer is moved to immediately before its earliest
    consumer. A full re-sort would shuffle nodes that have no reason to
    move and make every future diff unreadable.

    Anything left over after the repair is a hard error: a violation the
    repair cannot fix is a cycle in the graph, and a cycle is a design
    question, not something a generator may quietly linearise.
    """
    by_id = {n['id']: n for n in chip_nodes}
    seq = list(seq)
    moved = []
    for _ in range(len(seq) + 1):
        bad = process_order_violations(seq, by_id)
        if not bad:
            break
        consumer, i, producer, j = bad[0]
        seq.insert(i, seq.pop(j))
        moved.append((producer, consumer))
    remaining = process_order_violations(seq, by_id)
    if remaining:
        detail = '; '.join(f'{c} reads {p}, which still runs later'
                           for c, _, p, _ in remaining[:6])
        raise ValueError(
            f'{chip_label}: the process chain cannot be ordered so every '
            f'producer runs before its consumers -- this means a CYCLE in '
            f'the dsp.csv graph. {detail}. A cycle is a one-sample feedback '
            f'path and it has to be declared deliberately, not linearised '
            f'by the generator.')
    return seq, moved


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
            _by_id = {n['id']: n for n in nodes}
            for n in chip_nodes:
                if n['type'] == 'METER' and n.get('inputs'):
                    src_id = n['inputs'][0]
                    _mtr_after.setdefault(src_id, []).append(n['id'])
                    # Resolve the source's block publication ONCE, here,
                    # where the whole graph is in hand. No-fallback policy
                    # does not apply: a source that publishes no block is a
                    # known, recorded state, not an unknown one -- the
                    # generated node says so in its own header.
                    src = _by_id.get(src_id)
                    if src is None:
                        raise ValueError(
                            f"METER {n['id']} names input {src_id!r}, which "
                            f"is not a node in dsp.csv")
                    n['params']['mtr_src_blk'] = _METER_SRC_BLOCK.get(
                        src['type'], '')
                    # WIDE-WORD METERING (PW ruling 2026-08-29). Which of
                    # the two shapes this meter gets is a fact about its
                    # SOURCE -- see _MTR_WIDE_ACC. The link is recorded on
                    # BOTH nodes because both emit code for it: the source
                    # publishes, the meter consumes.
                    mode = ('acc' if src['type'] in _MTR_WIDE_ACC
                            else 'scalar')
                    n['params']['mtr_wide_mode'] = mode
                    if src['params'].get('mtr_sink'):
                        raise ValueError(
                            f"{src_id} feeds more than one METER "
                            f"({src['params']['mtr_sink']} and {n['id']}). "
                            f"The wide-word meter accumulates INSIDE the "
                            f"source's loop into one meter's accumulator "
                            f"block, so a second meter on the same source "
                            f"needs a decision, not a second store.")
                    src['params']['mtr_sink'] = n['id']
                    src['params']['mtr_wide_mode'] = mode
        _mtr_ids = {m for v in _mtr_after.values() for m in v}

        # ---- SIMD strip pairing: which nodes are generated on which pool
        #
        # strips[<n>][<CLASS>] = node id, for every complete channel strip.
        # The ODD strip of each pair (1, 3, 5, ...) is generated against the
        # BLK_*_P1 slot macros so a pair can hold both channels live; the
        # even one keeps the originals. A meter rides on whichever pool its
        # source is on, because what it taps is a pool slot.
        strips = {}
        for n in chip_nodes:
            m = _STRIP_NODE_RE.match(n['id'])
            if m:
                strips.setdefault(int(m.group(3)), {})[m.group(2)] = n['id']
        # Only COMPLETE strips pair: a partial one has no dynamics to pair.
        strips = {k: v for k, v in strips.items()
                  if all(c in v for c in _STRIP_TYPES)}
        odd_pool_ids = set()
        for sn, cls in strips.items():
            if sn % 2:
                odd_pool_ids.update(cls.values())
                for src in cls.values():
                    odd_pool_ids.update(_mtr_after.get(src, []))

        for node in chip_nodes:
            # call_sequence starts in dsp.csv order and is then repaired
            # for producer-before-consumer below (D5). The METER move is a
            # separate thing and is still done in the emitted chain under
            # #if DSP4_BLOCK_KERNELS, so the per-sample image keeps its
            # meter indices, on which DSP4_NODE_LIMIT and the scope-skip
            # table both depend.
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
            if node['id'] in odd_pool_ids:
                # Odd strip of a SIMD pair: same kernel, second pool. With
                # DSP4_SIMD_DYN off every _P1 macro aliases its original, so
                # this assembles to the bytes it did before pairing existed.
                body = _odd_pool(body)
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

        # GRAPH PROCESS-ORDER CHECK AND REPAIR (review finding D5).
        # Resolved from dsp.csv's `inputs`, not from the emitted order.
        _pre_bad = process_order_violations(
            call_sequence, {n['id']: n for n in chip_nodes})
        call_sequence, _moved = repair_process_order(
            chip_label, call_sequence, chip_nodes)
        if _pre_bad:
            print(f'  {chip_label}: process order repaired -- '
                  f'{len(_pre_bad)} stale-read edge(s):')
            for _c, _i, _p, _j in _pre_bad:
                print(f'      {_c} (#{_i}) read {_p} (#{_j}), which ran later')
            for _p, _c in _moved:
                print(f'      moved {_p} to run before {_c}')

        # Write process chain
        chain_path = os.path.join(output_dir, chip_label, 'process_chain.asm')
        with open(chain_path, 'w', encoding='utf-8') as f:
            f.write(f'/* {chip_label.upper()} — Processing chain call sequence */\n')
            f.write(f'/* AUTO-GENERATED by tools/dsp/dsp_codegen.py — do not edit directly. */\n')
            f.write(f'/* {len(call_sequence)} nodes in processing order */\n')
            f.write('/*\n')
            f.write(' * PROCESS ORDER IS CHECKED AGAINST THE GRAPH, not assumed\n')
            f.write(' * (review finding D5). Every node runs after every same-chip\n')
            f.write(' * node named in its dsp.csv `inputs`; the generator repairs\n')
            f.write(' * the order where it has to and fails outright on a cycle.\n')
            if _moved:
                f.write(' *\n')
                f.write(' * Moved out of dsp.csv order for this chip:\n')
                for _p, _c in _moved:
                    f.write(f' *   {_p} -> ahead of {_c}\n')
            else:
                f.write(' *\n')
                f.write(' * Nothing had to move: dsp.csv order is already correct here.\n')
            f.write(' */\n\n')
            # THE CHAIN NEEDS THE BLOCK HEADER. DSP4_PAIRED_GRAPH is defined
            # there, and without the include it is simply undefined here --
            # which the preprocessor reads as 0, so a DSP4_SIMD_DYN=1 build
            # emitted the SCALAR chain and every "paired" measurement was a
            # scalar one. It presented as the paired GATE costing nothing.
            f.write('#include "dsp_block.h"\n\n')
            f.write(f'.section/pm seg_pmco;\n')
            if chip_label == 'chip1':
                f.write(f'.extern _bus_clear_all;\n')
            for nid in call_sequence:
                f.write(f'.extern _{nid}_process;\n')
            if strips:
                f.write('#if DSP4_PAIRED_GRAPH\n')
                _pn = sorted(strips)
                for _k in range(0, len(_pn) - 1, 2):
                    _tg = f'{_pn[_k]:02d}_{_pn[_k + 1]:02d}'
                    f.write(f'.extern _DYNGATE_{_tg}_process;\n')
                    f.write(f'.extern _DYNCOMP_{_tg}_process;\n')
                    f.write('#if DSP4_BQ_PAIRED_GRAPH\n')
                    f.write(f'.extern _BQPFILT_{_tg}_process;\n')
                    f.write(f'.extern _BQPEQ_{_tg}_process;\n')
                    f.write('#endif\n')
                f.write('#endif\n')
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
            # ---- one emitter, two orderings ---------------------------
            #
            # The strip-ordered chain and the SIMD PAIR-ORDERED chain are
            # the same nodes with the same guards in a different sequence,
            # so they share this emitter. `seq` is a list of entries --
            # ('node', nid) or ('pair', CLASS, tag, sa, sb) -- and
            # `pos_of` maps a node id to the position DSP4_NODE_LIMIT
            # counts. Under pairing that position is the PAIR-ORDER one,
            # which is what makes limits 1..18 walk exactly one pair and
            # consecutive differences read as per-class costs again.
            def emit_chain(seq, pos_of, sgpfx):
                # Product-scope gating (DSP4_SCOPE_GATE, block-kernel
                # builds). A per-NODE skip table was measured on the part
                # and is a net LOSS: testing a table word before all 431
                # calls costs more than not calling the 34 scoped ones
                # (2026-08-24, 244,795 vs 243,235 cycles/block). The scoped
                # nodes are contiguous in call order, so gate whole RUNS
                # with one compare and one branch instead -- cost is per
                # run, not per node.
                runs, _i, _r = {}, 0, 0
                while _i < len(seq):
                    sid = (_scope_of.get(seq[_i][1])
                           if seq[_i][0] == 'node' else None)
                    if sid is None:
                        _i += 1
                        continue
                    _j = _i
                    while (_j + 1 < len(seq) and seq[_j + 1][0] == 'node'
                           and _scope_of.get(seq[_j + 1][1]) == sid):
                        _j += 1
                    runs[_i] = (_j, sid, _r)
                    _r += 1
                    _i = _j + 1
                ends = {v[0]: v[2] for v in runs.values()}

                for idx, ent in enumerate(seq):
                    if idx in runs:
                        _end, _sid, _rn = runs[idx]
                        f.write('#if DSP4_BLOCK_KERNELS && DSP4_SCOPE_GATE\n')
                        f.write(f'    /* nodes {idx}..{_end} are '
                                f'{"D32" if _sid == 0 else "D24"}-only */\n')
                        f.write('    r2 = dm(_product_id);\n')
                        f.write(f'    r3 = {_sid};\n')
                        f.write('    comp(r2, r3);\n')
                        f.write(f'    if ne jump (pc, .{sgpfx}{_rn}_end);\n')
                        f.write('#endif\n')

                    if ent[0] == 'pair':
                        _cls, _tag, _sa, _sb = ent[1], ent[2], ent[3], ent[4]
                        _p = pos_of[('pair', _cls, _tag)]
                        _nl = f'DSP4_NODE_LIMIT == 0 || {_p} < DSP4_NODE_LIMIT'
                        # Both strips have to be in the graph for a pair to
                        # exist. With an odd DSP4_STRIPS the last strip is
                        # in on its own, and its two dynamics nodes run
                        # SCALAR -- on their own pool, which is why that
                        # costs nothing but the call.
                        f.write(f'#if ({_nl}) && (DSP4_STRIPS == 0 || '
                                f'{_sb - 1} < DSP4_STRIPS)\n')
                        _pfx = ('DYN' if _cls in _STRIP_DYN else 'BQP')
                        f.write(f'    call _{_pfx}{_cls}_{_tag}_process;\n')
                        f.write(f'#elif ({_nl}) && (DSP4_STRIPS == 0 || '
                                f'{_sa - 1} < DSP4_STRIPS)\n')
                        f.write(f'    call _{strips[_sa][_cls]}_process;\n')
                        f.write('#endif\n')
                        continue

                    nid = ent[1]
                    guards = [f'DSP4_NODE_LIMIT == 0 || '
                              f'{pos_of[nid]} < DSP4_NODE_LIMIT']
                    m = strip_re.match(nid)
                    if m:
                        strip = int(m.group(2)) - 1
                        guards.append(f'DSP4_STRIPS == 0 || {strip} < DSP4_STRIPS')
                    f.write('#if (' + ') && ('.join(guards) + ')\n')
                    if nid in _mtr_ids:
                        # Per-sample builds call the meter here, at its own
                        # chain index, exactly as they always have.
                        f.write('#if !DSP4_BLOCK_KERNELS\n')
                        f.write(f'    call _{nid}_process;\n')
                        f.write('#endif\n')
                    else:
                        f.write(f'    call _{nid}_process;\n')
                    f.write('#endif\n')
                    for _m in _mtr_after.get(nid, []):
                        # ...and block builds call it HERE instead, right
                        # after its source, while that channel's pool slot
                        # is still live. Guarded so the shipping image is
                        # unchanged.
                        f.write('#if DSP4_BLOCK_KERNELS\n')
                        f.write(f'#if (DSP4_NODE_LIMIT == 0 || '
                                f'{pos_of[_m]} < DSP4_NODE_LIMIT)\n')
                        f.write(f'    call _{_m}_process;\n')
                        f.write('#endif\n')
                        f.write('#endif\n')
                    if idx in ends:
                        f.write('#if DSP4_BLOCK_KERNELS && DSP4_SCOPE_GATE\n')
                        f.write(f'.{sgpfx}{ends[idx]}_end:\n')
                        f.write('#endif\n')
                    if idx == 0:
                        # Harness stimulus goes in straight after the input
                        # node. Under per-block kernels the input kernel
                        # reads DMA directly, so there is no RX slot
                        # variable left to inject into -- the hook has to
                        # sit inside the chain.
                        f.write('#if DSP4_BLOCK_KERNELS\n')
                        f.write('    call _scope_inject_blk;\n')
                        f.write('#endif\n')

            # The strip-ordered chain: every node in dsp.csv order, each
            # keeping its own index. Meters keep their ORIGINAL index too --
            # without that, DSP4_NODE_LIMIT would mean two different things
            # in the two builds, and the fabric measurement, which is
            # exactly NODE_LIMIT 320 versus 0, would silently start counting
            # meters as strips.
            scalar_seq = [('node', nid) for nid in call_sequence]
            scalar_pos = {nid: i for i, nid in enumerate(call_sequence)}

            # The pair-ordered chain, built only where there are pairs to
            # build (chip 1). Chip 2's dynamics are C2_GRP_COMP and friends:
            # they have no block kernel, so there is nothing to pair and its
            # chain file is unchanged.
            pair_nums = sorted(strips)
            pair_seq, pair_pos = [], {}
            if pair_nums:
                _strip_ids = {i for c in strips.values() for i in c.values()}
                _first = min(i for i, n in enumerate(call_sequence)
                             if n in _strip_ids)
                _last = max(i for i, n in enumerate(call_sequence)
                            if n in _strip_ids)
                _span = call_sequence[_first:_last + 1]
                if any(n not in _strip_ids for n in _span):
                    raise ValueError(
                        f'{chip_label}: the channel strips are not a '
                        f'contiguous run of the chain, so the SIMD pair '
                        f'order cannot be built by reordering that run')
                # TWO pair-ordered chains, because the biquads pair
                # independently of the dynamics (DSP4_BQ_GRAPH): one with
                # FILT and EQ still per strip, one with them paired too.
                bq_seq, bq_pos = [], {}
                pair_seq += [('node', n) for n in call_sequence[:_first]]
                bq_seq += [('node', n) for n in call_sequence[:_first]]
                for _k in range(0, len(pair_nums) - 1, 2):
                    _sa, _sb = pair_nums[_k], pair_nums[_k + 1]
                    _tag = f'{_sa:02d}_{_sb:02d}'
                    for _cls in _STRIP_HEAD:
                        pair_seq.append(('node', strips[_sa][_cls]))
                    for _cls in _STRIP_HEAD:
                        pair_seq.append(('node', strips[_sb][_cls]))
                    for _cls in _STRIP_HEAD_SCALAR:
                        bq_seq.append(('node', strips[_sa][_cls]))
                    for _cls in _STRIP_HEAD_SCALAR:
                        bq_seq.append(('node', strips[_sb][_cls]))
                    for _cls in _STRIP_BQ:
                        bq_seq.append(('pair', _cls, _tag, _sa, _sb))
                    for _cls in _STRIP_DYN:
                        pair_seq.append(('pair', _cls, _tag, _sa, _sb))
                        bq_seq.append(('pair', _cls, _tag, _sa, _sb))
                    for _cls in _STRIP_TAIL:
                        pair_seq.append(('node', strips[_sa][_cls]))
                        bq_seq.append(('node', strips[_sa][_cls]))
                    for _cls in _STRIP_TAIL:
                        pair_seq.append(('node', strips[_sb][_cls]))
                        bq_seq.append(('node', strips[_sb][_cls]))
                if len(pair_nums) % 2:
                    for _cls in _STRIP_TYPES:
                        pair_seq.append(('node', strips[pair_nums[-1]][_cls]))
                        bq_seq.append(('node', strips[pair_nums[-1]][_cls]))
                pair_seq += [('node', n) for n in call_sequence[_last + 1:]]
                bq_seq += [('node', n) for n in call_sequence[_last + 1:]]
                for _sq, _ps in ((pair_seq, pair_pos), (bq_seq, bq_pos)):
                    for _i, _e in enumerate(_sq):
                        _ps[_e[1] if _e[0] == 'node'
                            else ('pair', _e[1], _e[2])] = _i
                    # A meter runs if and only if its source ran, so it
                    # takes its source's position rather than one of its own.
                    for _src, _ms in _mtr_after.items():
                        for _m in _ms:
                            if _src in _ps:
                                _ps[_m] = _ps[_src]

            if pair_seq:
                f.write('/* SIMD PAIR ORDER (DSP4_PAIRED_GRAPH). Head A, head B,\n')
                f.write(' * the two paired dynamics calls, tail A, tail B --\n')
                f.write(f' * {len(pair_seq)} positions against '
                        f'{len(scalar_seq)} strip-ordered ones, because each\n')
                f.write(' * pair replaces four dynamics nodes with two driver\n')
                f.write(' * calls. DSP4_NODE_LIMIT COUNTS THESE POSITIONS in\n')
                f.write(' * this build, so limits 1..18 walk exactly one pair.\n')
                f.write(' */\n')
                f.write('#if DSP4_BQ_PAIRED_GRAPH\n')
                emit_chain(bq_seq, bq_pos, 'bqgrun')
                f.write('#elif DSP4_PAIRED_GRAPH\n')
                emit_chain(pair_seq, pair_pos, 'psgrun')
                f.write('#else\n')
                emit_chain(scalar_seq, scalar_pos, 'sgrun')
                f.write('#endif\n')
            else:
                emit_chain(scalar_seq, scalar_pos, 'sgrun')
            f.write(f'    rts;\n')
            f.write(f'_{chip_label}_process_all.end:\n')
        files_written += 1

        # Write the SIMD strip-pair dynamics drivers. Always written --
        # the whole file is inside #if DSP4_SIMD_DYN, so it costs the
        # default image nothing and the tree never carries a stale copy.
        pairs_path = os.path.join(output_dir, chip_label, 'dyn_pairs.asm')
        with open(pairs_path, 'w', encoding='utf-8') as f:
            f.write(gen_dyn_pairs(chip_label, strips, _mtr_after))
        files_written += 1

        # Paired biquad drivers. Same rule as dyn_pairs.asm: always
        # written, whole file inside #if DSP4_BQ_PAIRED_GRAPH, so the tree
        # never carries a stale copy and the default image is untouched.
        _bands = {n['id']: int(n['params'].get('bands', '4'))
                  for n in chip_nodes}
        bqp_path = os.path.join(output_dir, chip_label, 'bq_pairs.asm')
        with open(bqp_path, 'w', encoding='utf-8') as f:
            f.write(gen_bq_pairs(chip_label, strips, _bands))
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

    # Fixed mode: the bus accumulators become generated (80-bit triples)
    if FORMAT == 'fixed':
        with open(os.path.join(output_dir, 'bus_accumulators.asm'), 'w',
                  encoding='utf-8') as f:
            f.write(gen_bus_accumulators_fixed())
        files_written += 1
        # The numeric boundary self-test (D1/D3). Always written -- the
        # whole file is inside #if DSP4_NUM_SELFTEST, so it costs the
        # default image nothing and the tree never carries a stale copy.
        os.makedirs(os.path.join(output_dir, 'lib'), exist_ok=True)
        with open(os.path.join(output_dir, 'lib', 'num_selftest.asm'), 'w',
                  encoding='utf-8') as f:
            f.write(gen_num_selftest())
        files_written += 1
        with open(os.path.join(output_dir, 'poly_tables_fx.asm'), 'w',
                  encoding='utf-8') as f:
            f.write(gen_poly_tables_fixed())
        files_written += 1
        with open(os.path.join(output_dir, 'blk_pool.h'), 'w',
                  encoding='utf-8') as f:
            f.write(gen_blk_pool_header())
        files_written += 1
        with open(os.path.join(output_dir, 'ctl_epoch.asm'), 'w',
                  encoding='utf-8') as f:
            f.write(gen_ctl_epoch())
        files_written += 1

    # dsp_block.h is NOT fixed-mode-only: it is the block-size contract the
    # whole tree reads, including the C DMA configuration.
    with open(os.path.join(output_dir, 'dsp_block.h'), 'w',
              encoding='utf-8') as f:
        f.write(gen_block_header())
    files_written += 1

    # ...and the same number for the BENCH tools, which score a pass rate
    # against 48000/BLOCK. A verdict tool that carries its own copy of the
    # block size will one day score an image that was not built with it.
    #
    # It goes BESIDE THE GENERATED TREE, always, so a harness can stage the
    # copy that matches the image it just built. The repo's tools/pi copy is
    # only rewritten when this is the SHIPPING tree: a DSP4_GEN_BLOCK
    # scratch generation used to overwrite it too, because pi_dir is derived
    # from this script's own location rather than from output_dir, and every
    # bench run after a block-32 generation then scored a block-8 image
    # against 1500 blocks/s (2026-08-29 -- the mislabelling was harmless
    # because the honest rule was applied by hand, and it is fixed here so
    # that it does not have to be).
    with open(os.path.join(output_dir, 'dsp4_block.py'), 'w',
              encoding='utf-8') as f:
        f.write(gen_block_py())
    files_written += 1
    if 'DSP4_GEN_BLOCK' not in os.environ:
        pi_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              '..', 'pi')
        if os.path.isdir(pi_dir):
            with open(os.path.join(pi_dir, 'dsp4_block.py'), 'w',
                      encoding='utf-8') as f:
                f.write(gen_block_py())
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
