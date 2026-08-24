**PW PRIORITY (2026-08-24): #1 for the dsp side is CAPACITY-FIT — prove the
full product processing fits the chips as fabbed (goal line: 32 basic strips
real-time in ONE 21564; two on the card = margin/product headroom). Everything
else queues behind it. No FPGA, no block-64, no PCB change: efficiency of the
generated code is the lever, per the Matrix principle — single source,
generate the efficient form. The strip-fusion dispatch below is this
priority's execution; do not drift to other work until the fit is proven or
disproven with measurements.**

## HUB DISPATCH 2026-08-24 11:00Z — STRIP FUSION: single-MAC stages, one round/saturate per strip (PW constraints: no FPGA, no block-64; target = 32 basic strips in ONE 21564)   [status: 🔴 in progress]

model: opus

Context: per-node conversion is done bar COMP+TUBE; strip 1,005 cycles/sample,
ceiling ~6.8 strips, D24 3.5x over. The remaining cost is BETWEEN nodes: each
stage exits to memory in Q4.28, paying splice+round+saturate+store per node
(GAIN: 1 MAC + ~12 plumbing instructions — PW: "gain should be a single MAC",
and inside a fused strip it is). PW has ruled out FPGA and block-64; block
stays 32 samples; the target is efficient code, not shape-of-product change.

1. FINISH THE CLASSES: retest COMP with real hoisting (your own GATE evidence
   says the wrap verdict was premature) and convert TUBE. Harness-verified.
2. STRIP FUSION, the main event, via the GENERATOR: emit ONE fused kernel per
   strip — samples resident in registers/MR across GAIN->EQ->FILT->GATE->COMP
   ->TUBE->DLY->FDR, intermediate stages as bare MACs/cascades at full 64-bit
   precision, ONE round/saturate/store at the strip boundary into the bus
   accumulator. Block-rate work (ramps, Q shadows, coefficient swaps) once at
   kernel entry. Numerically this is BETTER than per-node rounding — where
   bit-exactness vs the per-node path cannot hold (single vs per-stage
   rounding), verify against fixed_ref configured the same way and record the
   difference bound in the harness report, not as a tolerance loosening but
   as the fused reference. Prove on ONE strip (chip 1, full class chain),
   measure cycles/sample and verify, THEN roll to all strips via the
   generator. Target: <=200 cycles/sample/strip.
3. SIMD PAIRING: strips are per-channel and independent — process two strips
   per instruction stream with the secondary datapath where the kernel
   allows; measure the actual factor, do not assume 2x.
4. BUS/SEND FABRIC (23% of budget fixed): same lift-out treatment — routing
   masks at block rate, accumulators back in internal DM (they are parked in
   L2), sends as N MACs. Target: <=40k cycles/block.
5. RE-MEASURE: strips ceiling at 1x on the fused build (use _proc_passes,
   dsp4_audio_verdict.py), refreshed cycle table, STATUS one-read. The goal
   line: 32 basic strips real-time on ONE 21564 with margin; report the
   measured number against it honestly.

Rules: default/shipping image byte-identical throughout (fusion behind
DSP4_STRIP_FUSED, default 0); bench = rev-C CM4 app@192.168.1.219 24/7;
matrix-app running + 3 MCUs verified at every stop (NOTE the second-restart
pattern is filed with the hub as an mx26 app bug — keep logging occurrences);
rev A hands-off; single trunk; no AI attribution.

## HUB DISPATCH 2026-08-22 21:05Z — EARLY AUDIO: word-phase fix, then CPLD loopback bitstream + Pi capture path (no analog boards, no hands)   [status: 🟢 STRIP FULLY CONVERTED BAR COMP+TUBE - FILT, EQ, GATE and DLY all converted to per-block kernels today and all bit-exact on the part. FILT 6,973 -> 4,062 (1.72x), EQ 11,590 -> 7,998 (1.45x), GATE 5,999 -> 4,891 (1.23x), DLY 4,185 -> 2,000 (2.09x); every baseline re-measured on the CURRENT build, not taken from the pre-rewrite table. STRIP 1,973 -> 1,005 cycles/sample over the whole rewrite; projected ceiling 2.91 -> 6.79 strips; D24 4.6x -> 3.5x over. Only COMP and TUBE remain (243 cycles/sample together, 24% of a strip); converting them at DLY's rate reaches ~7.7 strips, STILL 3.1x short of D24 - so every class is now converted or measured, the total is better by a factor of two, and it does not close the gap. WHAT UNBLOCKED THE BIQUADS: a self-test on the part (DSP4_BQ_SELFTEST) ran _bq_fx_cascade_blk against _bq_fx_cascade_N on identical data - two stages with DIFFERENT coefficients, across a block boundary - and found 0 differing samples of 64. The routine was never the fault; the wrapper was. Three things it must get right: input and output are DIFFERENT pool slots (the cascade works in place), i1 carries HPF -> LPF, and crossfades are handed to the per-sample body a sample at a time via a new _<nid>_process_sample label so the alpha bookkeeping and mid-block completion are right by construction. COMP's 'not worth converting' verdict is now SUSPECT and should be retested: it was judged on a bare WRAP, and GATE - same class, also 8% slower wrapped - converted at 1.23x once the block-invariant work was hoisted (the _sample_idx guard, on/off tests, four constant reloads, register-resident state). TWO TRAPS RECORDED: (1) under DSP4_BLOCK_KERNELS _sample_idx is 31 when the chain runs, so any unconverted node converting its parameters under a _sample_idx == 0 guard NEVER converts and runs on its .var initialisers; (2) verifying DLY produced two blind passes first - an impulse never opens the gate, so '0 mismatches over 27 samples' was 27 samples of zeros, and a second attempt compared two scope arms through stateful filters and saw 1-3 LSB that had nothing to do with the delay. The probes now refuse to report a pass unless the stimulus could have failed. BENCH: shipping CPLD dsp4_logic.a1f6672af6c3 (md5 dd1e09185804cb2e451d5089cdd56be3, IDCODE 0x020a30dd verified), production firmware 0df38e8270c14e01ba6ffc57c2122563 / 130ddb0f546966b38ec23b6d9b923748 - byte-identical to before this work - matrix-app active, all 3 MCUs verified. FLAG FOR THE HUB: matrix-app needed a SECOND restart to get all three MCUs to announce, twice today (first restart gave H1S3 only, then none of the three). It always succeeded on the retry, but 'first restart after a DSP reflash does not verify' is a repeatable pattern now, not a one-off. Old status follows] [was: 🟢 KERNEL REWRITE - STEERED ITEMS ALL CLOSED, and the headline is a capacity answer, not an optimisation one. SCOPE GATING DONE and the first mechanism I built was a NET LOSS - that is the finding. Only 34 of 431 nodes carry a scope= (32 D32-only, 2 D24-only, all TDM in/out, interchip send/recv, aux input). Measured booted d24: control (no gating) 243,235 cycles/block, per-NODE skip table 244,795 (+1,560 WORSE), contiguous-RUN gating 241,744 (-1,491, kept). A table read+test before ALL 431 dispatch calls costs more than not calling the 34, and the ratio does not improve per-sample - check and node cost both scale 32x. The mechanism that works is one compare and one branch per contiguous RUN: 2 runs on chip 1, ~8 cycles/block against 1,491 saved. Behind DSP4_SCOPE_GATE (default 1) so the control stays buildable. DEFAULT IMAGE BYTE-IDENTICAL throughout (d1c3dd5c96d6516d76b5355474a73a95 / 85d546f9262bd3ef33604f1b577b2748) - my first cut moved _scope_gate_count and the chip-2 gate table and so changed the SHIPPING image; caught by the md5 check, legacy generator output now emitted verbatim on the default path. Chain still 0 LSB at all 7 level/pan points with a run branched over. CEILING RE-MEASURED AT 1x: STILL 2 (STRIPS=2 1500 transport/1500 _proc_passes REAL_TIME; STRIPS=3 1500/1329 OVER_BUDGET, reproducing the 1342 measured pre-rewrite). That is the CORRECT answer, not a disappointment - the default image is byte-identical so its ceiling could not have moved; every conversion sits behind DSP4_BLOCK_KERNELS. The CONVERTED build's ceiling is NOT yet honestly measurable and was not measured: there the six unconverted classes run once per block instead of 32x, so a sweep would flatter itself ~32x on 88% of the strip. MEASUREMENT TRAP recorded: a first sweep judged real time by FRAME_COUNT over a nominal dwell and produced an impossible 2023 blocks/s - FRAME_COUNT is advanced by the block ISR and is structurally blind to an over-budget loop. Use _proc_passes; dsp4_audio_verdict.py exists for exactly this and answered first try on a link that had refused 15 attempts. THE DECISION-GRADE ARITHMETIC: post-conversion strip 63,131 -> 42,306 cycles/block, fixed overhead 144,166 -> 109,064, so 218,616 available = 5.17 strips projected (up from 2.91). D24 needs 24 strips = 1,015,344 -> 4.6x OVER. D32 needs 32 -> 6.2x over. The six UNCONVERTED classes are 88% of what a strip now costs (EQ 338 + FILT 227 + GATE 204 + COMP 202 + DLY 148 + TUBE 40 = 1,159 of 1,329 cycles/sample); halve ALL SIX and you reach 9.2 strips, still 2.6x short of D24. Scope gating at 0.46% of budget does not change this and neither does any single node class - closing it needs a change of SHAPE (fewer nodes per strip, bigger block, or strips per part), which is a hub decision. FILT/EQ retry: PARKED, with the recorded reasoning CORRECTED - a both_unity pass at 0 LSB cannot exonerate the state handling, because with unity coefficients y=x and the stored state contributes NOTHING, so unity is blind to exactly the class of fault present. Any wrong state pointer passes it and fails every real filter. New suspect order: (1) the state pointer the wrapper hands i1 (test with two sections carrying DIFFERENT coefficients), (2) persistence across block boundaries, (3) only then MAC-unit implicit registers. A line-by-line diff proves the arithmetic, MAC order, rounding, saturation, error feedback and state store order are IDENTICAL to _bq_fx_cascade_N - it is not the maths. i0-advance-between-stages fix is IN, so EQ at r4=4 is unblocked. BENCH RESTORED: shipping CPLD dsp4_logic.a1f6672af6c3.svf (md5 dd1e09185804cb2e451d5089cdd56be3) flashed, IDCODE 0x020a30dd verified, GPIOs released; production firmware 0df38e8270c14e01ba6ffc57c2122563 / 130ddb0f546966b38ec23b6d9b923748; matrix-app active with all 3 MCUs verified (H1S1, H1S3, H1S4 - first restart showed only H1S3, a second restart brought all three). Old status follows] [was: 🟢 RUNG 2 CAPTURE PATH BIT-EXACT - 0x5A5A0000 / 0x5A5A0001, 96000/96000 frames, all 32 bits. CM4 I2S PROVISIONING FOR mx26 cm4-setup-pi.sh is recorded in the outcome below: one appended line 'dtoverlay=dsp4-pcm-slave' in /boot/firmware/config.txt (backup .bak-20260823-120634 on the unit) plus a custom overlay compiled ON the unit with dtc from source now committed at shared/dsp4-logic/pi/dsp4-pcm-slave.dts - dtbo origin is that dts, not a download. NO stock overlay fits: audioinjector-bare-i2s is playback-only (codec is linux,spdif-dit, a transmitter) AND Pi-master, while the DSP4 card has the CPLD mastering pcm_clk/pcm_fs so the Pi must be SLAVE. The custom overlay points bitclock/frame-master at the CODEC side and uses TWO dai-links because the dummy codecs are one-directional (dit=playback, dir=capture), 32-bit slots. Gives card 0 dsp4pcm, device 0 capture / device 1 playback. THE 32-BIT CHECK EARNED ITS KEEP: first capture read 0xB4B40000 vs 0x5A5A0000 - the expected word shifted LEFT exactly one bit - so the capture launch needed one more BCK of delay than playback (CAP_EXTRA_DELAY=1, measured). A 24-bit check would have hidden it. LATENCY NOT MEASURED and not for want of plumbing: both Pi directions are proven (DSPB->Pi bit-exact; Pi->DSPA shown by a tone appearing as 0xE95F619A in chip 1's lane-6 RX buffer where silence reads 0x00000000), but the DSP does not ROUTE the Pi input to DSPB's output - a 1 kHz tone in gives digital silence out with a committed d24 config. Routes are host-written matrix parameters that nothing in boot config sets, so latency belongs with the virtual-audio work in the queued chain. Old status follows] [was: 🟢 HUB WAS RIGHT - the 2.5x margin was my test, retracted. Aliveness was judged by whether the parameter link answered promptly, and that link is POLLED from the block loop, so under load an answer is a block away - normal, not a fault. Judged on audio truth, DSP4_STRIPS=1 is BOOT_STAGE 7, FRAME_COUNT 1500/s, _proc_passes 1500/s, DMA and SPORT clean: real time, every block, where it was previously recorded 0 alive/3. STRIPS CEILING = 2 (1: 1500 passes/s, 2: 1500, 3: 1342 = 89%, 4: 1144 = 76%), which agrees with the cycle arithmetic (2.9 predicted) to better than one strip - profile and bench now corroborate. Two strips against 32 required. Fixes kept: dsp4_audio_verdict.py separates transport from loop and reports UNKNOWN distinctly from AUDIO_DEAD; dsp4_diag.py read() collects patiently before realigning, since the old behaviour manufactured a fault out of a slow answer. RUNG 2: DSP and CPLD sides DONE - loopback capture bitstream flashed, card healthy on it, and pcm_din is LIVE (GPIO20 reads 2 hi/10 lo, right ballpark for the pattern words). BLOCKED on the Pi: arecord -l lists NO capture hardware, /boot/firmware/config.txt has no I2S overlay, so there is nothing to record from. That needs a persistent boot-config edit plus a reboot of the ONLY bench, and the overlay must make the Pi an I2S SLAVE since LOGIC masters pcm_clk/pcm_fs - flagging rather than guessing on a 24/7 unit. GPIOs do not clash (I2S 18-21, matrix-app 6-12/22-25). dsp4_pcm_capture.py is written and waiting. Old status follows] [was: 🟢 (c) CYCLE PROFILE DELIVERED in MW/D32/DSP/dsp4-cycle-budget.md - measured per node class with a TCOUNT instrument exact to the core clock. HEADLINE: RTG, a ROUTING node, is the most expensive class at 601 cycles/sample - 30.5% of a channel strip, more than EQ (338) and COMP (202) together. The dynamics maths is not the problem. Fixed overhead is 44% of budget before any strip runs (block I/O ~20%, buses/sends ~24%). Full graph 660% of budget. (b) DSP4_STRIPS built and flag-verified in the running image via a second stamp word, but the answer is uncomfortable: ONE strip measures 73.3% of budget - it fits by arithmetic - and is still 0 alive/3 at 1x. Reliable below ~20% load, marginal ~39%, gone by ~73%, so roughly a 2.5x margin is being eaten by something the cycle count does not explain and I have NOT identified it; candidates are that the alive/dead test is really a parameter-link test, and interrupt/overrun effects a per-pass count cannot see. The per-class table is unaffected and stands. (a) RUNG 2 RTL ready: reframer capture path de-frames a DSPB slot to pcm_din, loopback keeps lane 6 on the Pi path, dsp4_logic_loopback.b13e772abdbb built through sim+STA, SHIPPING POF proven BYTE-IDENTICAL, dsp4_pcm_capture.py written - but not yet flashed or captured, and latency needs a time-varying source which needs a graph that runs, which (b) says we do not have. Old status follows] [was: 🟢 ROOT CAUSE FOUND - the node graph is ~16x over the per-block cycle budget. Not a defect in any node: the FULL 431-node graph runs 3/3 clean given 16 block periods (DSP4_BLOCK_DECIMATE) and 0/6 given one, with 27 nodes 0/3 at 1x and 3/3 at 8x - same code, more time. Budget is 491.52 MHz / 1500 = 327,680 cycles per block; the graph needs ~5.2 M, about 380 cycles per node per sample, which is plausible real work for this library (a compressor runs log2+exp2 polynomials per sample). The graph is invoked ONCE PER SAMPLE - 431 calls x 32 samples = 13,792 node invocations per block. And nothing reduces it per product: _scope_gates_apply on chip 1 is a no-op ('no scoped nodes on this chip'), so all 431 run for D24 and D32 alike, and the measurement already had a d24 config committed. HARNESS FIXED FIRST: main.asm now carries a _build_flags stamp that bisect.sh peeks off the RUNNING part and aborts on mismatch, closing the assembler/linker/loader/boot loop that let the DSP4_STUB_* defines silently vanish; every point is now N repeats and a pass rate. THIS IS A DESIGN-CAPACITY DECISION FOR THE HUB - fewer nodes, cheaper nodes, or work moved out of the per-sample loop. Rung 2 cannot run as written (a scorable loop needs real-time audio) but the Pi capture path can still be proven with the DSP4_PATTERN firmware, which needs no node graph. Old status follows] [was: 🟠 RETRACTION - the compressor identification was WRONG and is withdrawn. The DSP4_STUB_* defines never reached easm21k (a build.sh string replace silently no-opped), so every stub build was the SAME image, md5 50a6c9d5, and the alive/dead differences were bench flakiness. Caught by md5-ing the image across a flag change. build.sh now passes them, verified by the md5 changing. Re-tested with repeats: production full graph 0 alive / 6, and 0 of 40 patient reads over 40 s after commit, so the core genuinely STOPS (not starvation - the 1 kHz ISR backstop would have answered). Without the node graph 4/4 alive at STAGE 7, 1500.0 blocks/s. One node 3/3 alive. Stubbing _compgain_fx changes nothing (0/2), and NODE_LIMIT 5 vs 6 does not reproduce, so no specific node is identified. ALSO CORRECTED: the BLK_OVERRUN 0 figure was from the stale image - the real number is ~8590 overruns per ~17220 blocks with block I/O ALONE, so half the per-block budget is gone before any node runs, which makes a cycle-budget explanation worth testing before another node hunt. STANDS: the r6 loop-bound fix (a real defect, readable in source), rung 0 (200 round-trips, 0 slips) and rung 1 (TDM slot map). NEXT: give every bisect point N repeats and a pass rate - single-point alive/dead is too noisy to bisect on. Old status follows] [was: 🟠 block loop FIXED, one fault left and it is narrow. FIXED: .cN_sample_loop kept its 32-sample bound in r6 while BOTH _scatter_chipN and _gather_chipN load the DMA buffer address into r6, so the loop ran about 610,000 times per block - indistinguishable from a hang. With that fixed, scatter+gather run at STAGE 7, 1500.0 blocks/s with BLK_OVERRUN 0: the main loop now keeps up with every block. REMAINING: DSP4_NODE_LIMIT binary-searches the 431-call chain to index 5 = _C1_COMP_01_process; bypassing it is alive, skipping its block-rate conversion is not, and stubbing _compgain_fx to unity is alive. Below that the stubs stop isolating (stub log2q ALIVE, stub polyq DEAD even though polyq is called BY log2q), which means the failure is VALUE-DEPENDENT in the compgain chain rather than one structurally broken routine - more blind stubbing is guesswork. NOT floating inputs: same hang with the loopback bitstream driving DSPA. Also fixed, not the cause: _comp_knee was read before ever being written, now 0.0 in the generator across 42 nodes. METHOD NOTE that cost two wrong readings: a harness that only asks 'did the link answer' gives FALSE PASSES, because a part still at BOOT_STAGE 5 answers fine - require BOOT_STAGE >= 6 and non-zero TICKS. Rung 2 still blocked on this last fault. Old status follows] [was: 🟢 RUNG 0 DONE (200 round-trips both chips, 0 slips, 0 out-of-step) + audio 1500.0/s + rung 1 verified. The post-CONFIG_COMMIT death was NOT a phase fault - answer-every-transaction is what proved it, since every read came back 0x00000000 rather than a wrong echo. Bisected to TWO faults: (A) FIXED - .main_loop opened with `idle`, which wedged the parameter link the instant CONFIG_COMMIT released .wait_boot (.wait_boot spins, .main_loop slept); proven by block-work-off + commit-applies-off + idle-ON = dead vs block-work-off + commit-applies-ON + idle-off = BOOT_STAGE 7 at 1500/s healthy. (B) OPEN and narrow - with idle gone, DSP4_BLOCK_STAGE puts the remaining wedge in the GENERATED scatter/gather (stage 1 healthy, stage 2 _scatter/_gather DEAD, stage 3 node graph also dead), so block_io.asm's _scatter_chip1/_gather_chip1 is the next item. Also landed: l2_clear() zeroes the L2 delay lines at startup, which the LDF explicitly requires and nothing did (did not fix either fault); host-side SpiLink.realign fallback. Rung 2 not started - it needs BOOT_STAGE 7 with real block I/O, which is what fault B blocks. Old status follows] [was: 🟢 AUDIO RUNS + RUNG 1 DONE; rung 2 blocked on rung 0. Audio: 1500.0 blocks/s on both chips (48 kHz / 32-sample blocks), SPORT0_ERR_A clean, DMA0_STAT 0x00006200, real 2D ping/pong. Four faults fixed to get there: PADS0_DAI0_IE/DAI1_IE never written (reset 0 = every DAI input buffer OFF, so BCK/FS never got past the pad while the SPORT read back perfectly configured); the DDE issuing NON-SECURE writes that memory refused (ERRC 3 for both the L1 alias and plain L2, with SMPU3_BADDR naming the exact address and BDTLS.SECURE = 0, against SPU0_SECURECHK = 0xFFFFFFFF for the core) fixed by SPU_SECUREP[n].MSEC; DMA_STAT.IRQDONE never W1C'd so the SEC re-entered the ISR forever (11e6 frames in 4.6 s); and DMA_CFG.TWOD unset, which made ping/pong a fiction that the block rate could not reveal. Descriptor-list arming is broken on this part, so the rings use AUTOBUFFER. RUNG 1 CLOSED by loopback measurement, recorded in hardware-map.md: lane index identity, slot order identity, BCK/FS pair order and sample edge/MFD all correct, proven decisively by masked lane 4 receiving exactly slots 0,2,3. RUNG 2 BLOCKED: after the 51-write CONFIG_COMMIT the parameter link is permanently out of phase (reads return BUILD_ID for a MAGIC request, no recovery in 10 attempts) - the part is alive and answering, just shifted, which is exactly what rung 0 exists to fix. Rung 0 is NOT a nicety; it gates everything past config. Also: dsp4_boot.py can silently leave chip 2 running chip 1's firmware - read CHIP_ID before believing any measurement. Old status follows] [was: 🟢 AUDIO RUNS — the gate is MET on BOTH chips at exactly 1500 blocks/s (48 kHz / 32-sample blocks), SPORT0_ERR_A clean, DMA0_STAT 0x00006200 (RUN 2, no error). THREE faults, none of them where the last several sessions were looking. (1) PADS0_DAI0_IE / PADS0_DAI1_IE were never written by this firmware and come out of reset at ZERO — every DAI input buffer was off, so BCK0/FS0 never got past the pad while SPORT0_A read back perfectly configured and enabled. The SRU only connects signals already inside the part. (2) The DDE issues NON-SECURE transactions and memory refused them: the first memory write of every transfer failed with ERRC 3 for BOTH the l1_to_sys() alias and a plain L2 address, and SMPU3 named the culprit — SMPU3_BADDR = 0x20000000, the exact target, with SMPU_BDTLS.SECURE = 0, while the core reads SPU0_SECURECHK = 0xFFFFFFFF and is therefore SECURE. Setting SPU_SECUREP[n].MSEC fixed it. (3) _sport_dma_work never W1C'd DMA_STAT.IRQDONE, so the channel held its request asserted and the SEC re-entered the ISR forever — 11e6 frames in 4.6 s until acked. Also fixed on the way: descriptor-list arming is broken on this part (ERRC 3 even for a self-referencing descriptor built in the probe), so the rings now use AUTOBUFFER flow; and the rung-31 probe was missing WNR, which had made a working channel look dead. Rung 1's pattern firmware and rung 2 NOT started — the audio path is up but the four slot-map facts are still unverified. Old status follows] [was: 🟠 rung 1 blocked on the DMA channel; SPU/SMPU checked and EXCLUDED, and the earlier conclusion OVERTURNED — the boot kernel does leave SMPU_CTL.RSDIS = 1 on all five instances (read addresses checked, no regions configured — a real latent hazard) but turning it off changes nothing. The decisive test: DMA0 armed REGISTER-BASED with FLOW=STOP and NO descriptor at all still raises ERRC = 3, both with the L1 alias and with an unambiguous L2 address, while ADDRSTART and XCNT now read back exactly what was written. So it is neither the descriptor fetch nor the address translation: the channel refuses to run whatever it is pointed at. Clearing the sticky IRQERR before arming does not help, so the error is raised live on enable. Caveat recorded: the probe omits WNR, which should be corrected before the conclusion is called final. Eleven hypotheses now eliminated. Next: fix the probe's WNR, then whether the SPORT/DMA block is clocked or gated at all — nothing in this firmware enables it. Old status follows] [was: 🟠 rung 1 blocked on the DMA channel; descriptor bug fixed, five hypotheses now eliminated — HRM Table 27-10 CONFIRMS the descriptor element order the code already used ({NXT, ADDRSTART, CFG, XCNT, XMOD}), so that is verified not assumed. Sharpened symptom: the channel advances DSCPTR_CUR by exactly five words (fetch 'complete') yet loads XCNT=0 and ADDRSTART=0 from memory the core reads back correctly. Excluded with evidence: element order; descriptor contents (correct after the volatile fix); store-buffer race (barrier changed nothing); DMA_CFG (reads back exactly as written); alignment; and L1 fabric visibility — the descriptors were moved to L2 (confirmed in the map at 0x2007bc00) and the fetch STILL returned zeros, so it is not an L1-alias problem. That L2 placement was reverted since it fixed nothing. Strongest remaining candidate: the SPU/SMPU system protection units, which nothing in this firmware programs — a gated fabric read that returns zeros and raises a memory-access error fits the signature better than anything else. Old status follows] [was: 🟠 rung 1 blocked on a REAL DMA BUG, now half fixed — **the DMA descriptors were being optimised away.** Nothing in C reads them (only the DDE does, through the fabric) so at -O the stores filling them were dead-store eliminated; taking &desc[i][0][0] does not save them because the address is only converted to an integer. Descriptor words read back 0x00000000 before and 0x282549D4 / 0x28254D40 after making them volatile — correct L1 aliases, correct ring. THAT is why no audio block has ever arrived on this card. Found from DMA_STAT 0x00006032 = IRQERR, ERRC 3 ("Memory Access or Fabric Error"), RUN 0. STILL FAILING: with correct descriptors the channel is unchanged (ADDRSTART 0, FRAME_COUNT 0, SEC_COUNT 0), and a write-completion barrier changed nothing, so it is not a store-buffer race; CFG reads back exactly as written. Next and specific: HRM ch.27 descriptor ELEMENT ORDER and alignment — the code assumes {NXT, ADDRSTART, CFG, XCNT, XMOD} but the data sheet prose says link/address/LENGTH/CONFIG. Five-minute check. Also corrected: the DMA channel, not the SPI link, is rung 1's real gate — the pattern firmware cannot mean anything until one block completes. Old status follows] [was: 🟡 rung 1 HALF DONE — the CPLD half is complete: `dsp4_logic_loopback.48fa9b8590d5` built through the sim and STA gates (47 LE vs shipping 156, Fmax 167.98 vs 70.21 — the fitter prunes the now-unused input muxes and the PCM reframer, which matters for rung 2), flashed over the CM4 JTAG bit-bang, and proven healthy on the card: both DSPs still boot (so DSP_CLK survives) and PCM_CLK/PCM_FS still toggle. **SHIPPING BITSTREAM RESTORED and re-verified** — IDCODE good, clocks toggling, chip 1 answers MAGIC/CHIP_ID/BOOT_STAGE. The pattern generator/checker firmware is NOT written, so none of the four facts rung 1 exists to close are established and no PROVISIONAL tags were retired. OPERATIONAL TRAP now documented in shared/dsp4-logic/README.md: OpenOCD's linuxgpiod leaves its GPIOs claimed on exit, so `pinctrl set ... a0` after every flash is MANDATORY — without it the SPI link is dead on both chips with a known-good bitstream and it looks exactly like a bricked card. Recommendation: run rung 1's verdicts over the PB_05 dump, not the SPI link. Old status follows] [was: 🟡 link now POLLED and much improved; rung 1 NOT started — the parameter link is off the SEC entirely: `sec_init()` keeps only the audio block clock and `_spi_poll` collects requests from the main loop AND from `.wait_boot` (the latter is mandatory — the config that releases that loop arrives over the link being polled, and omitting it deadlocks). Plus the two SPI_TFIFO pushes are separated by NOPs: back to back one was being lost and every read came back as (value, value). Production reads did not work AT ALL before this; they now run 11 of 12 consecutive full-block reads clean, with writes landing (PRODUCT_ID reads back 1). Read-after-write in one session is still an intermittent race — better, not solved; the echo is checked on every read so a bad answer is rejected rather than believed. Rung 1 deliberately not started at the tail of a long session: toolchain all verified present (Quartus 21.1, iverilog 12.0, OpenOCD + cpld-jtag.cfg, IDCODE 0x020a30dd, shipping .pof/.svf on the Pi ready to restore), and the recommendation is to read rung-1 verdicts over the PB_05 dump rather than the SPI link. SHIPPING CPLD bitstream UNTOUCHED. Old status follows] [was: 🟡 gate MET + read regression largely fixed; rungs 1-2 not started — the two all-zero-MISO events were ONE fault and it was in the RECEIVE side, not the response path: the RFIFO was left holding a single stale word around the boot handover, so with the correct RFS==FULL drain guard the level could never reach FULL again and the handler stopped firing (SPI2_STAT 0x00142001, RFS=2, counters FROZEN at 74 and IDENTICAL across two runs with different traffic, one with matrix-app stopped). Fixed with stuck-partial recovery in the diag timer ISR (three consecutive 1 ms ticks half-full = stale, discard a word) — SPI2_STAT now 0x00540001, everything empty and clean. Answers then come back rotated by one word, which dsp4_diag.py now tolerates with the ECHO as the check, so a wrong guess cannot be read as data. POLLED variant (rung 27) reads the full diag block RELIABLY; interrupt-driven production reads most of it then drops/duplicates one word. Per the steer the pipeline is not stopped on this: rung 1 proceeds on the polled channel. Remaining suspicion recorded — the ISR can enter mid-transfer when FULL is momentarily true, which the polled loop cannot; gate the drain on the transaction boundary. Old status follows] [was: 🟡 gate MET, rungs 1-2 not started — **BOOT_STAGE 6 on BOTH chips**, proven on the PB_05 dump (BOOT_STAGE 6, BOOT_CFG 1, PRODUCT_ID 1 on each; images md5-checked before flashing). Root cause of the config never landing was NOT rung 0: the drain guard tested SPI_STAT.RFE ("not empty") when a request is TWO words, so entering with a single word present drained one real word and one garbage one and desynced the stream permanently. Guarding on RFS == 4 (Full RFIFO) gives a clean 1:1 — chip 2 shows 5 handler entries for 5 writes where RFE gave 2.3x — and CONFIG_COMMIT then applies. REGRESSION, stated plainly: the same change broke READS, which now return all-zeros on MISO; the two states are (RFE: reads work, config never lands) and (RFS: config lands, reads dead). RFS is kept because it is provably the right condition and it reaches the gate. Rungs 1-2 not started — building a CPLD bitstream on a link that cannot be read back would be building on an unverifiable channel. Next: the read fault is between .spi_read and the TFIFO writes, everything upstream is excluded; see the outcome. Old status follows] [was: 🔴 blocked at rung 0 — the word-phase fix was implemented twice and REVERTED both times; nothing shipped and the tree is back at `f2bdb93`, rebuilt and re-verified on the bench. Making every transaction answer turned MISO to ALL-ZEROS on every transaction, reads included — worse than the known-good, which reads fine. The failing build is healthy everywhere except the answer: core alive, SEC_COUNT = SPI_RX_COUNT = 86, SPI2_STAT = 0x00540001 (RFIFO empty, no ROR/TUR/RUWM), RESP_DROP = 0 — so receive, delivery and dispatch all still work and only the queued answer is wrong. Both variants failed identically: echo stashed in a .var (the var read back CORRECTLY as 0xE0FE0000 from the main loop, yet answers were still zero) and echo queued while r0 is still live via a new subroutine. Rungs 1 and 2 not started — rung 0 is their gate. Full state note, four ranked next suspects and a recommendation to retry as a strictly smaller step are in the outcome below]

**HUB STEER 2026-08-23 10:20Z — capacity finding accepted; decision goes to PW (see
"DECISION ASK" below). Do NOT start a graph/kernel restructure. Proceed:**
(a) RUNG 2 via DSP4_PATTERN: prove the Pi capture path (pcm_din de-frame)
with the pattern firmware — Pi plays a known file into I6, pattern/pass-through
on the loop, Pi records it back; bit-exact on all 32 bits (the lanes carry
32-bit words); record latency in samples. (b) NODE-ENABLE MASK: add a per-strip
enable to product config (or a DSP4_STRIPS=N build knob) so a 1-strip graph
(IN→GAIN→EQ→FILT→COMP→GATE→FDR→bus) runs in REAL TIME at 1x — that is what the
virtual-audio harness needs; prove 1 strip 3/3 at 1x and find the max N that
holds 1x. (c) CYCLE PROFILE: cycles/sample per node CLASS (GAIN, FDR, EQ,
FILT, COMP, GATE, DLY, TUBE, BUS, MTR, RTG, XIN/XS) measured on the part, one
table in hardware-map.md or a new dsp4-cycle-budget.md — this is the data PW's
decision needs. Then the queued chain (desk fillers; virtual audio on the
1-strip graph). Keep going without stopping to ask.

**PW DECISIONS 2026-08-23 16:2xZ (recorded by the hub): (1) CM4 path = TDM8 —
8 channels Pi→DSP on A_I6 and 8 channels DSP→Pi on B_O3, LOGIC regroups
frames; allocate at the single source (slot-map.csv) — supersedes the stereo
B_O3 2/3 allocation (which is now a subset). (2) Rev-D mod 3 DROPPED: the
5M1270Z stays (738 LE + 4.1 % timing margin rule out the 570Z); recorded in
TransferOnly/PCB mods/dsp4-revD-modlist.md. The cycle-budget decision below
is still open.**

**PW DECISION 2026-08-23 16:5xZ: GO on 1 + 2 + 3 (per-block kernels; cheaper
RTG/bus/dynamics math; product scope gating). Option 4 (bigger blocks) NOT
taken. Dispatched as the QUEUED block "KERNEL REWRITE" below the virtual-audio
block; the harness families on the current code are the baseline first.**

**(resolved) DECISION ASK (PW): node graph is ~16x over the per-block cycle budget
(needs ~5.2 M cycles/block vs 327,680 available at 491.52 MHz / 1500
blocks/s; 431 nodes × 32 samples = 13,792 per-sample node CALLS per block).
Options: (1) per-BLOCK kernels — each node processes the 32-sample block in
an inner loop (generator change, not 431 hand edits): removes ~13k call
overheads per block and opens SIMD/pipelining; typical gain 3-8x. (2) cheaper
math — dynamics gain computer at block rate or every 4th sample (envelope
stays per-sample), biquads in the already-decided fixed point with wide
accumulators (D5). (3) fewer nodes per product — real scope gating (D24 ≠
D32), lazy nodes (bypassed = skipped). (4) larger block (64/128 samples) —
amortises overhead, costs latency. Hub recommendation: 1 + 2 + 3 together,
in that order; 4 only if the profile says the remaining gap is overhead-bound.
This reopens nothing in the rev-D PCB.
PROFILE UPDATE 10:5xZ (MW/D32/DSP/dsp4-cycle-budget.md): fixed overhead 44 %
before any strip (block I/O 20 %, buses/sends 24 %); one strip 19.3 %; full
graph 660 %. RTG (a ROUTING node) is the most expensive class at 601
cycles/sample = 30.5 % of a strip — more than EQ+COMP together. So option 1
(per-block kernels) plus a rewrite of RTG and the bus/send path are the big
levers; dynamics maths is NOT the problem.**

**HUB STEER 2026-08-23 11:55Z — the "2.5x margin" is most likely the test,
not the DSP.** Aliveness is judged over the parameter link, which is polled
from the MAIN LOOP — at 73 % block load the poll is starved and the link
looks dead while audio may be running fine. Do this first: judge aliveness by
FRAME_COUNT advancing + DMA0_STAT + SPORT_ERR over 3 s (audio truth), not by
the link. If audio runs at 1 strip/1x, move the SPI poll into the per-block
work (once per block = 1500 Hz, ample) so the link survives load; re-measure
the strips ceiling. Then RUNG 2: flash the loopback-capture bitstream, prove
pcm_din bit-exact (all 32 bits) with the pattern firmware, then latency with
the 1-strip graph. Then the queued chain.

model: opus

**HUB STEER 2026-08-22 22:05Z — rung 0 PARKED, pipeline continues.** Reads
work and the bounded re-ask workaround in dsp4_diag.py covers writes, so
rung 0 is a protocol nicety, not a gate. Do NOT retry it now. Proceed:
(a) `dsp4_config.py` end to end to BOOT_STAGE 6 on both chips USING the
re-ask workaround, verifying every CONFIG_COMMIT write by re-read; if a
write provably does not land even with re-ask, that and only that reopens
rung 0. (b) Rung 1, then rung 2, then chain into the queued blocks. Rung 0
becomes a separate item — "SPI answer-every-transaction" — to be tried at a
quiet point with a 1-hour time-box, in your own suspect order (TFIFO
occupancy on a verified build first, then inline the queue to drop the
nesting depth, then the r0 preservation in `_diag_read`). Rebuild-and-md5
before every dump reading — keep that rule.

**HUB STEER 2026-08-23 05:40Z — rung 0 UNPARKED: it gates rung 2.** Evidence
accepted (link permanently out of phase after CONFIG_COMMIT). Retry the
answer-every-transaction design FRESH — both failed attempts predate the
stale-word recovery, the polled link and the TFIFO NOP fix, so their
all-zero result may have been those faults, not the design. 3-hour box.
Fallback if it still resists: host-side resync — `dsp4_diag.py` detects
the phase error by ECHO mismatch and issues one 1-word (4-byte) transfer to
realign, repeated until ECHO matches; protocol note says "phase repair is
host-side". Either way, rung 2 follows immediately, then the queued chain.

Rung 0 — WORD-PHASE FIX (UNPARKED 05:40Z — see steer) (your own finding, 20:3xZ outcome): make every
accepted transaction queue exactly one two-word answer — a write echoes its
request word with value 0 — in BOTH `spi_handler.asm` variants + the protocol
note in `diag.asm`; update `dsp4_diag.py`/`dsp4_config.py` to expect it and
remove the bounded re-ask workaround. Prove: 200 alternating write/read
round-trips on chip 1 and chip 2 with zero phase slips, `--led` reliable.
Then run `dsp4_config.py` end to end → BOOT_STAGE 6 on both chips. Stage 6
is the gate for rung 1. Commit + push before starting rung 1.

Rung 1 — CPLD FEEDBACK LOOP (tasks item 5, PW 2026-08-20). Non-shipping,
STA-gated, hash-named LOGIC build: `i_dspa[k] = o_dspb[k]` for k=0..7 (and
`ni[k] = no[k]`), everything else identical to the shipping bitstream.
Firmware: counter-pattern generator per lane on DSPB, checker per lane/slot on
DSPA, verdicts via the 0xE000 diag readback. Closes without a scope: BCKI/FSI
pair order, CKRE/MFD, within-TDM8 slot order, NI/NO crossed-index vs
slot-map.csv. Record each fact in hardware-map.md as VERIFIED with the build
hash + date; retire the PROVISIONAL tags.

Rung 2 — PI CAPTURE PATH. `pcm_din` (LOGIC -> Pi) is tied off in
dsp4_pcm_reframe.v. In the SAME loopback build, de-frame one DSPB output
lane/slot pair to I2S on pcm_din (document which). Then on the CM4:
`aplay` a known file -> DSPA I6 via the reframer, `arecord` the return;
Pi -> DSPA -> fabric -> DSPB -> Pi becomes a software-scorable loop. Reuse
the net repo's long-soak scorer (torn/gaps/dups/silence) — do not write a new
one. Deliver: one 10-minute clean pass on chip 1 + chip 2, then leave a
≥12 h soak running with the verdict log path in this block.

Rules as the block above: bench = rev-C CM4 app@192.168.1.219; rev A
hands-off; always leave matrix-app running + 3 MCUs verified; the SHIPPING
bitstream must be restored on the CPLD before ending; single trunk; no AI
attribution. Rung 3 (real ADC/DAC via J41/J42, codec) is PW-hands and NOT
part of this dispatch.

### Outcome 2026-08-23 02:0xZ — SPU/SMPU checked and EXCLUDED. The channel errors with no descriptor and a valid L2 address.

The hub's hypothesis was worth testing and the registers do show the boot
kernel leaves protection active — but it is not the cause.

#### What the SPU/SMPU actually read back

| register | value | meaning |
|---|---|---|
| `SMPU0/2/3/9/11_CTL` | `0x00000001` each | **RSDIS = 1 on ALL FIVE** — "read addresses are checked before being sent to the slave" |
| `SMPU0_STAT` | `0x00000000` | no violation latched |
| `SPU0_CTL` | `0x000000AD` | GLCK set — MMR write locking, not memory access |
| `SPU0_STAT` | `0x00000000` | nothing |

So the boot kernel does hand over with read-address checking enabled on
every SMPU instance and no regions configured — a real finding, and a
latent hazard worth knowing about.

**But turning it off changes nothing.** Writing 0 to all five CTLs before
arming (verified: `SMPU0_CTL` then reads `0x00000000`) left `DMA_STAT` at
`0x00006032` and `XCNT` at 0. The probe was reverted afterwards rather
than kept, since it fixes nothing and an unexplained write to five
protection units would mislead the next reader.

`SPU0_CTL.GLCK` is about locking MMR *writes*, and our MMR writes
demonstrably land (`DMA_CFG` reads back exactly as written), so the SPU
was never a candidate on the evidence.

#### The decisive test, and what it overturned

`ADDRSTART` and `XCNT` reading 0 was NOT proof that the fetch returned
zeros — it is equally what you see if the fetch never happened, because
nothing else ever writes those registers. So DMA0 was armed
**register-based, FLOW = STOP, no descriptor anywhere**:

| arming | ADDRSTART | XCNT | DMA_STAT |
|---|---|---|---|
| descriptor-list | 0 | 0 | `0x00006032` |
| register-based, L1 alias `0x28254D40` | `0x28254D40` | `0x100` | `0x00006032` |
| register-based, **L2 `0x200F0000`** | `0x200F0000` | `0x100` | `0x00006032` |

The registers now hold exactly what was written, so MMR writes are fine —
and the channel still raises ERRC = 3 the moment `EN` is set, pointed at
unambiguous system memory, with no descriptor involved. Clearing the
sticky `IRQERR` (W1C, bit 1) immediately before arming did not help
either, so it is re-raised live on enable rather than inherited.

**That overturns the previous conclusion.** The descriptor fetch is not
the fault and neither is the address translation. The channel refuses to
run at all.

Caveat on the last two rows, stated because it matters: the rung-31 probe
omits `WNR`, so it arms as a memory READ where SPORT0 half A wants a
memory WRITE. That is worth correcting before drawing a final conclusion
from it — though a transmit DMA reading valid L2 should still not raise a
memory-access error.

#### Cumulative elimination list for the DMA channel

Order (HRM Table 27-10) · descriptor contents · store-buffer race ·
`DMA_CFG` contents · address alignment · L1-vs-L2 for the descriptor ·
L1-vs-L2 for the buffer · SMPU read checking · SPU MMR locking · sticky
`IRQERR` · descriptor fetch as a whole.

#### What is left

Something gates this DMA channel from running irrespective of what it is
pointed at. Candidates, in the order worth trying:

1. **Fix the rung-31 probe (add `WNR`) and re-run** — cheapest, and it
   removes the one caveat above.
2. **Is the channel clocked?** SCLK0 gates SPORT and DMA. SCLK0 is
   present (SPI2 runs on it), but per-peripheral clock or reset gating
   for the SPORT/DMA block has never been checked. There is no such
   enable in this firmware.
3. **SPORT0 itself.** `SPORT0_ERR_A` reads 0, but the SPORT's own enable
   and its DMA request path have never been verified independently of
   the DMA channel.
4. `CMMR_SYSCTL.IMDWBLK*`, which needs the SHARC+ Core Programming
   Reference — not in the local doc set and worth fetching.

**Bench state:** SHIPPING CPLD bitstream on the card; both chips hold the
production build and chip 1 answers MAGIC / CHIP_ID / BOOT_STAGE 5; GPIOs
`a0`; `matrix-app` restarted; three MCUs verified 02:05.

### Outcome 2026-08-23 01:2xZ — descriptor ORDER confirmed correct; L1-vs-L2 excluded. The DDE fetches ZEROS from memory that demonstrably holds the right values.

**HRM ch.27 Table 27-10 / 27-12 settle the element order and the code was
already right:**

| offset | register |
|---|---|
| 0x00 | `DMA_DSCPTR_NXT` |
| 0x04 | `DMA_ADDRSTART` |
| 0x08 | `DMA_CFG` |
| 0x0C | `DMA_XCNT` |
| 0x10 | `DMA_XMOD` |

`{NXT, ADDRSTART, CFG, XCNT, XMOD}` — exactly what `arm_region()` builds.
The data sheet's "link pointer, an address, a length, and a
configuration" is loose prose; the HRM table is the hardware. **That
assumption is now verified rather than assumed, and it is not the fault.**

#### The sharpened symptom

After the descriptor fetch:

| | value |
|---|---|
| `DMA0_DSCPTR_CUR` | given + 0x14 — i.e. five words consumed, fetch "complete" |
| `DMA0_XCNT` | **0** (descriptor holds 256) |
| `DMA0_ADDRSTART` | **0** (descriptor holds a valid buffer address) |
| `DMA0_STAT` | `0x00006032` — IRQERR, ERRC = 3, RUN = 0 |

So the channel walks the descriptor, advances its pointer by exactly the
right amount, and loads **zeros** into every register — from memory the
core reads back correctly at that same address.

#### Excluded tonight, with evidence

- **Descriptor element order** — HRM Table 27-10, above.
- **Descriptor contents** — read back correct from the core after the
  `volatile` fix (`NXT 0x282549D4`, `ADDRSTART 0x28254D40`).
- **Store-buffer race** — a volatile read-back barrier before arming
  changed nothing.
- **`DMA_CFG`** — reads back `0x00144223`: EN, WNR, PSIZE/MSIZE 4 bytes,
  FLOW = DSCLIST, NDSIZE = fetch-five, XCNT_INT. Exactly as written.
- **Address alignment** — descriptor at ...C0, buffer at ...40; MSIZE
  4 bytes needs only ADDR[1:0] == 0.
- **L1 fabric visibility** — the whole descriptor array was moved to L2
  (confirmed in the linker map at `0x2007bc00`, not merely intended) and
  the fetch STILL returned zeros. So this is not an L1-alias or
  L1-exposure problem. The L2 placement was reverted afterwards, because
  keeping a change that fixed nothing would mislead the next reader.

#### What that leaves

The DDE performs the fetch motions but reads zeros regardless of where
the descriptor lives. That points at the channel's SCB read path itself
rather than at the descriptor, the address or the memory: something
about how this DMA channel is enabled for fabric access. Worth looking at
next, in order:

1. **SPU / SMPU.** The system protection units gate master access per
   peripheral. Nothing in this firmware programs them, and a blocked
   fabric read that returns zeros and raises a memory-access error is
   exactly what a protection block looks like. `REG_SPU0_*` and
   `REG_SMPU*` are in the header; the HRM has a chapter each. **This is
   the strongest remaining candidate and it fits the "reads as zeros"
   signature better than anything else.**
2. Whether the SPORT is actually requesting at all — if it is not, work
   out whether ERRC = 3 can be raised without a real memory access.
3. `CMMR_SYSCTL.IMDWBLK*` (internal memory data width per L1 block),
   documented in the SHARC+ Core Programming Reference which is not in
   the local doc set — would need fetching.

#### Rung 1

Unchanged: CPLD half done, pattern firmware deliberately unwritten. The
DMA channel is the gate, and it is now a well-bounded problem with five
hypotheses eliminated rather than a vague one.

**Bench state:** SHIPPING CPLD bitstream on the card (restored 00:44,
IDCODE verified); both chips hold the production build and chip 1 answers
MAGIC / CHIP_ID / BOOT_STAGE 5; GPIOs `a0`; `matrix-app` restarted; three
MCUs verified 01:17.

### Outcome 2026-08-23 00:5xZ — 🟠 THE DMA DESCRIPTORS WERE BEING OPTIMISED AWAY. Fixed. Channel still errors — one step left.

**This is why no audio block has ever arrived on this card.** Nothing in C
ever READS the DMA descriptors — only the DMA engine does, through the
fabric, which the compiler cannot see. At `-O` the stores that fill them
are dead by the compiler's reckoning and were being eliminated. Taking
`&desc[i][0][0]` does not save them: the address is only converted to an
integer and never dereferenced in C.

Measured, on md5-verified builds, over the PB_05 dump (no SPI link
involved):

| | before | after `volatile` |
|---|---|---|
| descriptor word 0 (ring next ptr) | `0x00000000` | **`0x282549D4`** |
| descriptor word 1 (ADDRSTART) | `0x00000000` | **`0x28254D40`** |

Both post-fix values are correct L1-alias addresses, and `0x282549D4` is
exactly the second descriptor of the pair — the ring is right.

`desc_a`/`desc_b` and `arm_region()`'s parameter are now `volatile`, with
the reasoning written where the arrays are declared so it cannot be
"tidied" away again.

#### How it was found

`DMA_STAT = 0x00006032` decodes as **IRQERR set, ERRC = 3, RUN = 0** —
ERRC 3 is *"Memory Access or Fabric Error"* (HRM Table 27-25). The channel
had errored on its very first work unit and stopped. Dumping what
`arm_region()` actually handed the DDE showed the descriptor address was
sane (`0x282549C0`, a valid block-0 alias) while the descriptor CONTENT
read back as zeros — so the DDE was faithfully fetching zeros and then
aiming a transfer at address 0.

#### STILL FAILING, and the next step is specific

With correct descriptors in memory the channel is unchanged:
`DMA0_ADDRSTART` still reads `0x00000000`, `DMA_STAT` still `0x00006032`,
`FRAME_COUNT` and `SEC_COUNT` still 0. So the DDE is not applying the
descriptor it fetches.

Excluded already:
- `DMA0_CFG` reads back `0x00144223` = EN, WNR, PSIZE 4B, MSIZE 4B,
  FLOW = DSCLIST, NDSIZE = fetch-5, XCNT_INT — exactly as written.
- The descriptor address handed over is a valid alias.
- The descriptor contents are now correct.
- A write-completion barrier before arming (volatile read-back of two
  descriptor words) changed nothing, so it is not a store-buffer race.

That leaves the **descriptor element order and alignment**. The code
assumes `{DSCPTR_NXT, ADDRSTART, CFG, XCNT, XMOD}`, the ADI convention.
The data sheet's prose describes a 1D descriptor as *"a link pointer, an
address, a length, and a configuration"* — CFG and XCNT the other way
round. One of those is loose wording and the other is the hardware; HRM
ch.27 has a "Descriptor Set Address Alignment" table and an element-order
definition that settles it. **Read that first next session** — it is a
five-minute check that either confirms the layout or explains everything.

#### Rung 1 status

The CPLD half is done (see the previous outcome). The pattern
generator/checker firmware is still not written, and now clearly should
not be: a pattern test cannot mean anything until a single DMA block
completes. **The DMA channel is the real gate for rung 1, not the
verification channel** — that was the wrong diagnosis, and chasing the SPI
link earlier was chasing the wrong thing.

**Bench state:** SHIPPING CPLD bitstream restored and verified (IDCODE
`0x020a30dd`, chip 1 boots and answers MAGIC/CHIP_ID/BOOT_STAGE 5); both
chips hold the production build; GPIOs back to `a0` after the flash;
`matrix-app` restarted; three MCUs verified 00:44.

### Outcome 2026-08-23 00:2xZ — 🟡 rung 1 HALF DONE: loopback bitstream built, flashed and proven; pattern firmware not written. SHIPPING RESTORED.

**The CPLD half of rung 1 is complete and reusable.** The firmware half —
per-lane pattern generator on DSPB, per-lane/slot checker on DSPA — is not
started.

#### Built, flashed, verified, reverted

`dsp4_logic_loopback.48fa9b8590d5` — non-shipping, both gates passed:

| | shipping `a1f6672af6c3` | loopback `48fa9b8590d5` |
|---|---|---|
| logic elements | 156 / 1270 | **47 / 1270** |
| Fmax | 70.21 MHz | **167.98 MHz** |
| sim gate | PASS | PASS (on the shipping path) |
| STA gate | met | met |

The LE drop is expected and worth understanding: with `i_dspa = o_dspb`
the ADC/NET input muxes and the whole PCM reframer have no consumer, so
the fitter prunes them. **That matters for rung 2** — the reframer must
come back, and it will, because rung 2 gives `pcm_din` a real source.

Implementation is a single `\`ifdef DSP4_LOOPBACK` in
`rtl/dsp4_logic_top.v` (`assign i_dspa = o_dspb;`) plus `LOOPBACK=1` in
`build.sh`, which passes the macro to Quartus, folds it into the hash
input and labels the artifact `dsp4_logic_loopback.<hash>` so it can
never be confused with a shipping one. The manifest says `SHIPPING: NO`
in as many words.

#### Flashed and proven healthy on the card

Programmed over the CM4 JTAG bit-bang (`openocd -f cpld-jtag.cfg`,
IDCODE `0x020a30dd` before and after). With the loopback bitstream
loaded: both DSPs still boot — which is itself the proof that `DSP_CLK`
survives — and PCM_CLK/PCM_FS still toggle on the netprobe, so clkgen is
untouched.

**The SHIPPING bitstream has been restored** and re-verified the same
way: IDCODE good, clocks toggling, chip 1 boots and answers
`MAGIC 0xD5B40001`, `CHIP_ID 1`, `BOOT_STAGE 5`.

#### OPERATIONAL TRAP, cost me a while

**OpenOCD's `linuxgpiod` adapter leaves its GPIOs claimed on exit and
does not hand them back.** After any CPLD flash the SPI link is dead
until `pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0` is run. It looks
exactly like a bricked card: reads return nothing at all, on either chip,
with the shipping bitstream loaded. This is the same class of trap as the
gpiod/spidev one already recorded for GPIO9/10/11 — same cause, different
tool. Always restore the pins after flashing.

#### Where rung 1 stopped

The remaining work is the pattern firmware and its verdict readout. It did
not start because the verdict channel is not yet trustworthy enough to
carry it: after `CONFIG_COMMIT` the parameter link stops answering, and a
`DSP4_BISECT=29` build added to report from *after* the handshake never
produced a frame — its link was dead from boot, which was not diagnosed.
(One self-inflicted detour on the way: that rung first read a GUESSED
`DMA0_STAT` at 0x31022008; the real address is 0x31022030 and an unmapped
MMR read hangs this core. Named constants only — the header has them.)

**The honest recommendation stands and is now stronger:** run the rung-1
pattern test with its verdicts on the **PB_05 dump**, not the SPI link.
That channel has been reliable all session and every hard fact of the last
three days came off it. The pattern firmware should write its per-lane
results into DM variables and a bisect rung should frame them out — no
host protocol involved.

**Nothing about the four facts rung 1 exists to close** — BCKI/FSI pair
order, sample edge / MFD, within-TDM8 slot order, NET crossed-index — has
been established. They remain PROVISIONAL in `hardware-map.md` and no tags
were retired.

**Bench state:** SHIPPING CPLD bitstream restored and verified; both chips
hold the polled-link production build; GPIOs returned to `a0`;
`matrix-app` restarted and active; three MCUs verified.

### Outcome 2026-08-22 23:5xZ — 🟡 link moved to a polled architecture; much better, still not clean. Rung 1 NOT started.

**Design change, not a workaround: the parameter link is now POLLED from
the DSP main loop and `SPI2_STAT` is no longer routed to the SEC.**
`sec_init()` keeps the audio block clock — the source that genuinely
needs an interrupt — and drops the SPI route; `_spi_poll` in `main.asm`
collects a request whenever `SPI_STAT.RFS` says a whole two-word one has
landed, and is called from both the main loop and `.wait_boot`.

Why: interrupt delivery could enter the handler while the host was still
clocking, so FIFO-full was momentarily true mid-transfer and the drain
took one real word plus one still arriving. Polling only ever looks
BETWEEN transactions, which is exactly why the polled variant read
cleanly all along where the interrupt path never did. Cost is nil — the
loop already wakes on the 1 kHz diag tick with no audio, and per block
with audio.

**`.wait_boot` must poll too, and that is not optional:** the config that
releases that loop arrives over the very link being polled, so with the
SEC route removed and no poll there the firmware waits forever for a
message nothing is collecting. That deadlock happened once during this
work and is now commented in place.

**Second fix: the two `SPI_TFIFO` pushes are separated by NOPs.** Back to
back, the host saw the SAME word twice instead of (echo, value) — one
push was being lost, which is what a FIFO write hazard looks like from
outside. Reads returned (value, value) for every register until the NOPs
went in.

#### Honest state of the link

| case | result |
|---|---|
| reads only, full 24-register block | **11 of 12 consecutive runs clean**; one failed on a single register |
| a write, then reads in the same session | intermittent — sometimes a clean coherent set, sometimes (value, value) |
| writes landing | yes — `PRODUCT_ID` reads back 1 after config, and BOOT_STAGE 6 was proven on both chips earlier via the PB_05 dump |

So it is much better than it was (production reads did not work AT ALL
before this) but it is a race, not a solved problem. Retry-with-echo-check
makes it usable; the echo is verified on every read, so a bad answer is
rejected rather than believed.

#### Why rung 1 is not started

Rung 1 needs: a non-shipping loopback bitstream (build, sim gate, STA
gate, hash label), an OpenOCD flash over the CM4 JTAG bit-bang, pattern
generator and checker firmware on BOTH chips, verdicts read back, four
hardware facts recorded in hardware-map.md, and the shipping bitstream
restored. The toolchain is all present and verified this session —
Quartus 21.1, iverilog 12.0, OpenOCD 0.12 with `/home/app/cpld-jtag.cfg`
(IDCODE 0x020a30dd), and the shipping artifact
`dsp4_logic.a1f6672af6c3.{pof,svf}` is on the Pi ready to restore.

That is several hours of fresh work. Starting it at the end of a session
that has already had one thrashing stretch would repeat the mistake, and
rung 1's whole value is a trustworthy verdict — which wants a link that
is not a race, or a deliberate decision to read verdicts over the PB_05
dump instead (which HAS been reliable all session and is the honest
fallback).

**Recommendation for whoever takes rung 1:** use the PB_05 dump as the
verdict channel from the start rather than the SPI link. It is
out-of-band, it needs no host protocol, and every hard fact established
in the last two days came off it.

**Bench state:** both chips hold the polled-link production build;
`matrix-app` restarted and active; three MCUs verified; GPIOs back to
`a0`. The SHIPPING CPLD bitstream is untouched — no loopback bitstream
was built or flashed.

### Outcome 2026-08-22 23:0xZ — 🟡 read regression largely fixed; polled channel is reliable, interrupt-driven is intermittent

**The two all-zero-MISO events were one fault, and the hub's framing was
right.** It was not the response path at all: the RECEIVE FIFO was being
left holding a single stale word, and with the (correct) RFS==FULL drain
guard the level can then never reach FULL again, so the handler stops
firing and the link is dead from that moment.

Measured, on a verified build (md5 checked both ends):

| | value | meaning |
|---|---|---|
| `SPI2_STAT` | `0x00142001` | **RFS = 2 — one word of two** |
| `SEC_COUNT` / `SPI_RX_COUNT` | frozen at 74 | handler could no longer fire |
| `RESP_DROP` | 0 | nothing was being dropped |

The counters were **identical across two runs with completely different
host traffic**, including one with `matrix-app` stopped to rule out the
other SPI master. That is what proved the handler had stopped rather than
misbehaving.

The residue arrives around the boot handover: `spi2_init()`'s EN-low flush
happens before the host has finished with the port, so a fragment can land
after it.

#### Fix 1 — stuck-partial recovery in the diag timer ISR

A genuine request is only half-arrived for microseconds, so three
consecutive 1 ms ticks with `RFS` neither empty nor full means stale.
Discard one word; if still stuck, discard another. Cheaper and less
disruptive than an EN off/on, which would also throw away a legitimately
queued answer. `_spi_partial_fix` counts how often it fires.

Effect: `SPI2_STAT` goes to `0x00540001` — RFIFO empty, TFIFO empty, no
ROR/TUR/RUWM — and the counters move again.

#### Fix 2 — the host tolerates a one-word rotation, checked by the echo

With the wedge cleared, answers come back but the (echo, value) pair can
arrive rotated — value first. `dsp4_diag.py` now tries both arrangements
and **the echo decides**: an answer is only accepted when the request word
comes back verbatim, so a wrong guess cannot be mistaken for data.

#### Where it stands

| build | reads |
|---|---|
| **polled (bisect rung 27)** | **reliable** — full diag block: MAGIC 0xD5B40001, CHIP_ID 1, BOOT_STAGE 5, TICKS, SEC_COUNT 87, LAST_CSID 71 |
| interrupt-driven (production) | **intermittent** — reads most of the block, then fails on one register with a duplicated word (e.g. 0xE014 returning DMA0_STAT's value twice) |

So the regression is largely fixed but the interrupt path is not yet
trustworthy enough to verify anything else through.

#### Per the hub steer, the pipeline is NOT stopped on this

Rung 1 should proceed using the **polled variant as the verification
channel**, which reads reliably, plus `dsp4_boot`/`stagewatch`. The RFS
build stays on the chips: `CONFIG_COMMIT` lands and BOOT_STAGE 6 is
reached on both.

**Remaining suspicion for the intermittent case,** for whoever picks it
up: the interrupt path can enter the handler while the host is still
clocking the next transaction, so the FULL condition is momentarily true
mid-transfer and the drain takes one real word plus one that is still
arriving. The polled loop only ever looks between transactions, which is
exactly why it is clean. If that is right, the fix is to gate the drain on
the transaction boundary (SPI_STAT.SPIF or the slave-select edge) rather
than on FIFO level alone — worth a look before anything more elaborate.

**Bench state:** chip 1 holds the production RFS build; `matrix-app`
restarted and active; three MCUs verified; GPIOs back to `a0`.

### Outcome 2026-08-22 22:2xZ — 🟡 BOOT_STAGE 6 reached on BOTH chips; the read path regressed doing it

**The rung-1 gate is met.** `dsp4_config.py --product d24` applied on chip 1
and chip 2, proven on a channel that does not use the SPI response stream
at all:

| | chip 1 | chip 2 |
|---|---|---|
| `BOOT_STAGE` | **6** | **6** |
| `BOOT_CFG` | 1 | 1 |
| `PRODUCT_ID` | 1 (d24) | 1 (d24) |
| `SPI_RX_COUNT` vs writes sent | 118 / 51 | **5 / 5** |

Read out with the rung-23 PB_05 dump, which frames `_diag_boot_stage`,
`_boot_config_received` and `_product_id` straight out of DM. Both images
md5-checked on the Pi against the local build before flashing.

#### ROOT CAUSE of the config never landing: the drain guard was on the wrong bit

The handler drains TWO words — a request is two words — but the guard
added on 2026-08-22 tested `SPI_STAT.RFE`, which only means "not empty".
Entering with a SINGLE word present drained one real word and one garbage
one, and from that moment every later pair was shifted by a word.
Permanent desync, and it explains three separate symptoms at once: the
2.3x-too-many handler entries, the host-side word-phase slip, and
CONFIG_COMMIT never being applied.

The right condition is `SPI_STAT.RFS == 4` (Full RFIFO — 2 words at
32-bit word size), which is also exactly what the RUWM=FULL interrupt
trigger means. With it:

- chip 2 shows **5 handler entries for 5 writes**, a clean 1:1 where the
  RFE guard gave 2.3x;
- `CONFIG_COMMIT` applies and `BOOT_STAGE` goes to 6 on both chips.

Before the change, with the RFE guard, the same 51 writes left
`BOOT_STAGE 5`, `BOOT_CFG 0`, `PRODUCT_ID 0` — the config was being
received and thrown away.

#### REGRESSION, and it is honest: reads now return all-zeros

The same change broke the read path. On a production (`DSP4_BISECT=0`)
build with the RFS guard, every raw read returns `0x00000000` on MISO —
chip 1 alone and with both chips booted, at 1 MHz, tested repeatedly. The
200-round-trip harness fails on the first read.

So the two states are:

| build | writes / CONFIG_COMMIT | reads |
|---|---|---|
| `f2bdb93` (RFE guard) | **do not land** — stage stuck at 5 | work |
| RFS guard (this commit) | **land** — stage 6 both chips | return zeros |

The RFS guard is kept because it is provably the correct condition for a
two-word protocol and it is what reaches stage 6, which is the gate the
pipeline needs. The read breakage is a second, adjacent defect and it is
NOT the parked rung-0 item — rung 0 is about writes *answering*, this is
about reads *being answered at all*.

**What is excluded already:** the handler runs (`SPI_RX_COUNT` climbs
1:1), it returns (later transactions are still processed), the receive
side is clean, and the write dispatch works end to end. So the fault is
between `.spi_read` and the two `dm(SPI2_TFIFO)` writes. First thing to
check next session is whether `_diag_read` still leaves r0 intact now that
the guard changed which register holds what on entry — the guard's compare
now uses r2/r3 where the RFE version used r2/r3 differently, and r2 is the
decoded address the read path depends on.

#### Also in this commit

- `dsp4_config.py` had chip 2 documented and defaulted as **GPIO7**; it is
  **GPIO24**, the same defect already fixed in `dsp4_diag.py`. Corrected in
  the docstring, the `--cs-gpio` help and a new default.
- `dsp4_config.py --verify` reads `BOOT_STAGE` / `BOOT_CFG` / `PRODUCT_ID`
  / `SPI_ERR_COUNT` / `RESP_DROP` back after writing and says whether the
  commit landed. It works only when the read path does, so it is not
  usable on this build — kept because it is the right shape for the tool
  and costs nothing.
- The rung-23 dump now carries `BOOT_STAGE`, `BOOT_CFG` and `PRODUCT_ID`
  in place of the SEC route words, which is what made this diagnosable
  without the SPI response stream.

**Rungs 1 and 2 not started.** The gate is met, but starting a CPLD
bitstream while the parameter link cannot be read back would be building
on a channel I cannot verify.

**Bench state:** both chips hold the rung-23 config-dump images from the
last measurement; `matrix-app` restarted and active; three MCUs verified;
GPIOs returned to `a0`.

### Outcome 2026-08-22 21:4xZ — 🔴 rung 0 attempted and REVERTED; tree is back at the known-good commit

**Nothing shipped. The tree is exactly `f2bdb93` for all firmware and host
files, rebuilt and re-verified on the bench after the revert: chip 1 reads
its whole diagnostic block with both chips booted.** Rungs 1 and 2 were not
started — rung 0 is their gate.

#### What was tried

The word-phase fix as specified: make every accepted transaction queue
exactly one two-word answer (write / unmapped-address / `DIAG_NOP` answer
with value 0), in both `spi_handler.asm` variants, with the protocol notes
in `diag.asm` and `diag.h` updated and `dsp4_diag.py` restored to the plain
two-step read.

**Result: MISO went to all-zeros on every transaction, reads included** —
i.e. worse than the known-good, which reads correctly. Two variants, same
outcome:

1. **Echo stashed in a `.var`,** reloaded in the responder because the
   write paths clobber r0. The variable itself was fine — a rung-23 dump
   read `_spi_req_word = 0xE0FE0000`, the last `DIAG_NOP` request, exactly
   right. But every answer still went out as zero.
2. **Echo queued while r0 is still live** — the write side calls a new
   `_spi_queue_resp` subroutine immediately after the READ-flag branch,
   before the dispatch clobbers r0; the read path calls the same
   subroutine. No memory round trip at all. Same all-zero result.

#### What the evidence says, and does not say

On the failing build the part is **healthy everywhere except the answer**:

| | value |
|---|---|
| core alive | `DIAG_TICKS` climbing |
| handler running | `SEC_COUNT` = `SPI_RX_COUNT` = 86 over ~48 words |
| receive side | `SPI2_STAT = 0x00540001` — RFIFO empty, no ROR, no TUR, no RUWM |
| responses dropped | `RESP_DROP = 0` |

So the receive path, the interrupt delivery and the dispatch are all still
working; only the queued answer is wrong. That points at the two `dm(SPI2_TFIFO)`
writes or the registers feeding them, not at anything upstream.

**Do not trust one earlier reading.** A `RESP_DROP = 0` / `REQ_WORD = 0`
pair was taken from a STALE image: the rung-23 build failed on an
unresolved symbol (`_spi_req_word` needed `.global`), but the shell chain
continued because the `grep` guarding it matched the error text and exited
0, so the previous `.ldr` was flashed and read. Caught and re-run after
fixing the link; the numbers in the table above are from a verified build.
**Rebuild-and-md5 before every dump reading from here on.**

#### Next suspects, in the order worth trying

1. **TFIFO occupancy.** Once every transaction queues, a two-deep TFIFO is
   written on every transaction instead of only on reads. If the read
   answer is queued while the previous write answer is still unshifted it
   takes `.spi_read_drop` — which should show in `RESP_DROP`, and did not,
   but that counter deserves re-checking on a verified build before the
   theory is discarded.
2. **PC-stack depth inside the SEC ISR.** Variant 2 adds a third nested
   `call` (`_sec_isr` → `_spi2_rx_work` → `_spi_queue_resp`, and
   `_diag_read` is already a third on the read path, making four). Cheap
   to test: inline the queue instead of calling it.
3. **Does `_diag_read` really preserve r0?** Its comment says so and the
   known-good code depends on it, but the known-good code reads r0 at a
   different point in the flow than variant 2 does.
4. **Fall-through.** `.spi_read_zero` used to fall into the responder
   label; after the restructure that label is a subroutine ending in
   `rts`, so the zero path now returns straight to `_sec_isr` and skips
   the `.spi_done` epilogue (the ILAT/STAT clear). Not the cause of the
   all-zero MISO — `.spi_read_zero` is only reached for out-of-range or
   unmapped addresses — but it is a real defect in the reverted-away code
   and must not come back when this is retried.

#### Recommendation

Retry rung 0 as a **strictly smaller step**: leave the read path exactly as
it is in the known-good build, and add the write-side answer alone, inline,
with no new subroutine and no new variable. Verify MISO on a raw read
BEFORE adding the 200-round-trip harness — the harness masked which half
broke for two build cycles.

**Bench state:** both chips hold the known-good production images
(`chip1.ldr`/`chip2.ldr` = the `f2bdb93` build); `matrix-app` restarted and
active; all three MCUs verified; GPIOs returned to `a0`.

## QUEUED DISPATCH (fire after the early-audio block) — DESK FILLERS: SPI2_RDY never asserts · 570Z scratch-fit · OSPI clock gate   [status: 🟢 ALL THREE DONE — (1) SPI2_RDY CLOSED, not usable on this silicon (already FCEN/FCCH/FCPL as hoped, pin driven and idling asserted, but a guaranteed 16-word overfill never deasserts it at any of the three legal FCWM values, 0/40 each). (2) 570Z scratch-fit DONE and then OVERTAKEN BY EVENTS: 157/570 LE but only +0.842 ns slack, then FAILS timing at -0.198 ns once the Pi return is added, and the 8-channel CM4 link needs 738 LE which does not fit 570 at all — PW has since dropped rev-D mod 3 and kept the 1270Z. (3) OSPI/xSPI CLOSED by the hub from the datasheet now in _Matrix/_ref/adsp-2156x-docs: octal + DDR + HyperBus (HyperFlash AND HyperRAM), dedicated xSPI0_RWDS pin, DQS; 50 MHz untrained / 80 MHz trained no-DQS / 125 MHz trained with DQS, Table 37 characterised at 166.66 MHz, MASTER ONLY. Verdict for mod 1: HyperRAM 2.0 at 125 MHz DDR = 250 MB/s, not 200 MHz. PLUS a pin finding the timing verdict does not cover — Table 10 shows xSPI0 is MUXED ONTO THE SPI2 PINS: PA_00 MISO/D1, PA_01 MOSI/D0, PA_04 CLK, PA_05 SEL1, and D2-D7 take PA_02/03/06-09. SPI2 on PA_00/01/04/05 is this card's host parameter link AND the BMODE=0b010 slave-boot port, so fitting xSPI0 octal consumes it entirely. SPI1 (PA_10-13) is the only SPI clear of xSPI0. That is a mod-1 design question, not a timing one, and it would otherwise surface at PCB stage]) are both illegal on the 570Z in the same T144 package and must move. The AK5558 BICK/MCLK constraint is NOT assessed - the rev-D lane map has no RTL. (3) OSPI BLOCKED on document access: HRM ch.16 confirms Octal DDR/DTR and data-capture tuning but contains NO mention of RWDS, HyperRAM, HyperBus or xSPI 'profile'; the max-clock figure is a datasheet spec and every route is blocked (analog.com times out, verical 403, mouser times out). ASK: drop the Rev D datasheet into _Matrix adsp-2156x-docs and this closes in minutes]

model: opus

All desk work, no bench contention beyond a register read; do them in order,
stop when done or blocked, push main.

1. **SPI2_RDY never asserts** (20:3xZ loose end). With RFIFO empty the part
   holds FCS set and PB_05 low under FCPL=1/FCWM=1. Read HRM ch.15 flow
   control end to end (FCEN, FCCH = which channel RDY follows, FCPL, FCWM,
   the TX-channel rule — RDY may be following the TFIFO, not the RFIFO) and
   find the configuration under which RDY means "slave can accept a
   transaction". Prove with a register dump + PB_05 reading on the bench.
   If RDY can be made meaningful, add `--rdy-gpio 8` honouring to spiraw.py
   / dsp4_diag.py and re-measure; if it cannot on this silicon, write that
   verdict and close the item — either way rev-D mod 9 (RDY pull-up) stands.
2. **570Z scratch-fit** (tasks item 6 open): fit the rev-D unified lane map
   (2×TDM16/direction AK5558 cascade, 1×TDM8 AK4619, Pi I2S→TDM8 with MEMS
   at slots 5-6, one TDM32 NET pair, D32 snake on the same pair) into a
   5M570ZT144C4N scratch Quartus project from the current dsp4_logic RTL.
   Record LE/pin utilisation, the MEMS-input pin move off PIN_137, and
   whether clkgen meets the ±10 ns BICK↓ vs MCLK↑ constraint for the
   cascaded slaves. Deliver numbers into the rev-D list (mod 3/4 rows via
   the hub — report, do not edit TransferOnly from this machine).
3. **OSPI clock gate** (rev-D list §D, open): from the ADSP-2156x data
   sheet OSPI timing section, the max OSPI clock (133 vs 200 MHz) and
   whether xSPI profile-2 / RWDS-strobe HyperRAM 2.0 is supported; confirm
   against the EV-21568-SOM reference design. Verdict for mod 1's final part
   pick; report to the hub.

Rules as above: bench = rev-C CM4 app@192.168.1.219; rev A hands-off; leave
matrix-app running + 3 MCUs verified; single trunk; no AI attribution.
When done or blocked, continue straight into the next QUEUED block.


**CM4 stereo send + return = the USB 2-track path.** The *requirement* is
PW's ("on final product cm4 pi needs a stereo send and return to dsp", plus
"this same stereo path is the source/sink for USB 2-track audio play/rec").
**The slot allocation below is NOT PW's — PW said "you can choose most
convenient slots". It is HUB-ACCEPTED 2026-08-23, PW TO RATIFY.** It is
sensible on the face of it (no PCB change, no new pin) but it has not been
ratified:

| direction | line | slots | signal | USB role |
|---|---|---|---|---|
| Pi → DSP | `A_I6` | 0, 1 | `PI_PCM_L/R` | 2-track **PLAY** sink |
| DSP → Pi | `B_O3` | **2, 3** | `PI_RET_L/R` | 2-track **REC** source |

Chosen because `B_O3` had only slots 0/1 used (provisional `DAC_MAIN`, no
D24 sink), 2/3 keep clear of DAC MAIN on D32, and it needs **no PCB change
and no new pin** — `B_O3` already reaches LOGIC as `dac_main` and `pcm_din`
is an existing net to GPIO20. Done at the single source (`slot-map.csv`),
so one edit feeds both the CPLD constants and the DSP SPORT map; new slot
map hash `sha256:1507e8813e3db2bb…`. Documented in
`MW/D32/DSP/dsp4-plumbing.md`. 48 kHz only — D7 excludes USB audio on the
96 kHz products.

The capture path is now a **product feature**, out of the `DSP4_LOOPBACK`
ifdef, so the shipping bitstream changes deliberately: **156 → 312/1270 LE
(25%), Fmax 70.21 → 66.18 MHz**, still 35% margin at 49.152 MHz.
**This flips the 570Z answer**: the same design is 312/570 LE (55%) and now
**fails timing at −0.198 ns**, where it met +0.842 ns before the return.

**Open, and it is a matrix question:** nothing writes `B_O3` slots 2/3 yet,
so the return is silent. What feeds `PI_RET_L/R` — a dedicated stereo bus
(recommended: a USB recording usually wants its own mix) or a copy of the
main mix? Needs node definitions from mx26.

**Bitstreams:** shipping `dsp4_logic.758b7c82ef6e`, bring-up
`dsp4_logic_loopback.1e831a2cf29d`. The bench still carries
`dsp4_logic_loopback.3f488870d6cb` on purpose — that one captures `B_O3`
slot 0 (`MAIN_ST_OUT`), which is the only slot anything drives today.

## QUEUED DISPATCH (fire after the desk fillers) — VIRTUAL AUDIO TESTS over the CPLD feedback loop: the golden harness gets a hardware target   [status: 🟡 PASS-THROUGH IS UNITY AND BIT-EXACT; blocked on Pi duplex streaming. The 4x is RETRACTED - it was my measurement, a peak taken from an overrun-riddled capture. Known-word test (hub's method): 0x00001000/0x00010000/0x00100000 all return identically, ratio 1.0000, in << 0, 100% of non-zero frames. Shifts corroborate: chip1 scatter >>3, chip1 gather none, chip2 scatter none, chip2 gather <<3 saturating - paired, no net shift. REAL BLOCKER is the CM4 soundcard: capture alone is 100% stable (rung 2) and playback alone reaches the DSP (lane-6 RX shows live tone), but BOTH TOGETHER scramble - a per-sample counter returns values under ~200 across 20,000 frames instead of climbing to 48,000, dominant step -191, with ALSA reporting no under/overrun once period/buffer are pinned. Suspect my own overlay: dsp4-pcm-slave.dts uses TWO dai-links sharing one bcm2835-i2s CPU DAI (dit=playback, dir=capture) because the dummy codecs are one-directional - two PCM devices, not a true duplex device. FIX DIRECTION: one dai-link with a codec declaring both directions; device-tree work, not DSP. Latency deliberately NOT reported - it would be fiction through a stream repeating a 200-sample window. ALSO: nothing drives SPORT3 slot 1 on chip 2 (C2_MAIN_ST_OUT writes slot 0 only despite 'Channels: 2'), so the capture's right channel is correctly silent - graph/generator question for the hub. CPLD carries dsp4_logic_loopback.3f488870d6cb per the hub ruling] -> reframer capture -> pcm_din -> arecord. SIGNAL PRESENT, peak 0x7BB7C120. Two blockers cleared: the capture was tapping o_dspb[0] (AUX_OUT_01/02, silent in a pass-through) instead of o_dspb[3] (MAIN_ST_OUT) - new bitstream dsp4_logic_loopback.3f488870d6cb; and the Pi input is gated OFF by default, _auxin_on_C2_PI_IN at SPI 0x071D on chip 2, one poke opens it. Everything downstream already defaults to unity and the Q4.28 shadows refresh at block rate, so they are not a second gate. NOT bit-exact yet: input 0x20000000 comes back 0x7BB7C120, a ratio of 3.87 - close enough to 2^2 to look structural, and the scatter/gather Q1.31<->Q4.28 shifts are the first place to look. Also bursty (~4.5% of frames carry signal, aplay reported an overrun), so playback buffering must be pinned before any latency figure or it measures ALSA. Harness --target hw and the five families NOT started - the block itself says fix bit-exactness first. CONFLICT for the hub: this block says leave the loop soaking, the standing Rules say restore the SHIPPING bitstream; they cannot both hold. I restored SHIPPING as the older standing rule on a 24/7 bench - say which wins]

model: opus

Precondition: early-audio rung 2 delivered (Pi aplay → DSPA I6, DSPB lane
de-framed back to Pi arecord over the CPLD loopback bitstream; soak clean).
Purpose (PW 2026-08-22): exercise gain, EQ, dynamics etc. with generated
tones and levels through the REAL SHARC path and measure, no ears, no
converters. The yardstick already exists — `shared/numeric-spec.md`
"Acceptance tolerances (golden harness)", `tools/dsp/golden_harness.py`,
`tools/dsp/fixed_ref.py`. The hardware becomes a third target of the same
harness: target ≡ fixed_ref (bit-exact), fixed_ref ≈ float64 (tolerances).

1. **Path calibration first.** Pass-through strip (all nodes unity/bypass):
   play the standard vector set, capture, align by a known preamble, and
   prove the loop is bit-exact end to end (Pi I2S → TDM slot → SPORT → node
   chain → SPORT → TDM → I2S). Record fixed latency in samples. If the loop
   is not bit-exact, STOP and find why (slot/justification/MSB-first,
   24-vs-32-bit, sign extension) — nothing below is meaningful until it is.
2. **Harness extension.** `golden_harness.py --target hw`: for each vector
   and parameter set, push parameters over the SPI link (dsp4_config.py /
   diag protocol, float32 words as today), play, capture, compare against
   fixed_ref bit-exact and float64 within the spec tolerances. One report
   per kernel family with pass/fail and worst-case deviation.
3. **Families, in this order** (each on one channel strip, chip 1, then the
   output-side twin on chip 2 where one exists):
   - GAIN / FDR: stepped levels −60…+18 dB, ±0.5 LSB; fader ramps — no
     zipper (spectral check during a ramp), ramp time vs cell table ±2 %.
   - EQ / FILT / GEQ: swept sine or MLS → magnitude/phase per band at several
     f0/Q/gain, ±0.01 dB (≥50 Hz), ±0.05 dB at 20 Hz; residual < −120 dBFS.
   - COMP / GATE / LIM: tone bursts at stepped levels → static curve ±0.05 dB
     (threshold, ratio, knee, make-up); attack/release from envelope fits
     ±2 %; gate hold/range; limiter ceiling never exceeded.
   - DLY: sample-exact delay vs setting; TUBE: harmonic series vs reference.
   - Bus summing: exact to LSB; MTR: peak readback over SPI vs captured peak.
4. **Keep the vectors.** Commit stimulus generators (not WAVs), the hw
   capture alignment tool, and the per-family reports under tools/dsp/;
   results table into findings (dsp4-architecture-decisions.md D5 gets a
   "hardware-verified" line per family with date + build id). Any family
   that fails is a firmware bug or a spec [REVIEW] to resolve — report it,
   do not loosen the tolerance.
5. Leave the pass-through loop soaking when you stop.
   **HUB RULING 2026-08-23 14:30Z on the bitstream conflict: while THIS block
   runs, the loopback-capture bitstream stays on the CPLD (the soak needs it;
   the bench is 24/7 and nobody else is on the unit). The standing rule
   "restore SHIPPING before ending" applies at the END of this block, before
   any hand-off to PW, or the moment PW says the unit is needed — the hub
   will say so. Record the currently-flashed bitstream hash in the block
   status at every stop so the state is never ambiguous.**

Rules as above. This is the item PW most wants to see results from; write
the results table so it reads at a glance.

## QUEUED DISPATCH (fire after the virtual-audio block) — KERNEL REWRITE: per-block kernels + cheaper RTG/bus/dynamics + scope gating (PW GO 2026-08-23)   [status: 🔴 queued]

model: opus

Goal: the full 32-strip D24 graph in real time on the two SHARCs as fabbed,
with margin — target ≤ 70 % of the 327,680-cycle block budget on chip 1, chip
2 lower, at 32-sample blocks (block size does NOT change; latency preserved).
Evidence: MW/D32/DSP/dsp4-cycle-budget.md (today 660 %; RTG 601 cyc/sample,
EQ 338, fixed overhead 44 %). Numeric contract: shared/numeric-spec.md (D5).

Method — one family at a time, in profile order, measured after each:
0. BASELINE: the virtual-audio harness results on the CURRENT kernels (the
   block above) are the reference; every rewritten family must pass the same
   rows bit-exact vs fixed_ref before it replaces the old one. The cycle
   instrument (TCOUNT per class) runs on every build — update the table.
0a. STATUS 2026-08-24 (one-read picture)
   CONVERTED AND VERIFIED, default build byte-identical throughout:
     block I/O + IN   67,809 -> 32,707 cycles/block   2.07x  (scatter deleted)
     GAIN              2,321 ->    574                4.04x
     FDR               4,404 ->  1,886                2.33x
     RTG              19,186 ->  2,626                7.3x
     FILT              6,973 ->  4,062                1.72x
     EQ               11,590 ->  7,998                1.45x
     GATE              5,999 ->  4,891                1.23x
     DLY               4,185 ->  2,000                2.09x
   Only COMP and TUBE remain unconverted (243 cycles/sample together, 24%
   of a strip). STRIP 1,973 -> 1,005 cycles/sample over the whole rewrite.
   PROJECTED CEILING 2.91 -> 6.79 strips. D24 4.6x -> 3.5x over. Converting
   the last two at DLY's 2.09x would reach ~7.7 strips, still 3.1x short of
   D24 - every class is now converted or measured, the total is better by a
   factor of two, and it does not close the gap.
   BIT-EXACT END TO END: GAIN -> FDR -> RTG -> BUS verifies 0 LSB at 7
   points (level 1.0/0.5/0.25 x pan 0/0.25/0.5/0.75) - mono, pan-split L
   and the summed bus, including the 64-bit accumulator's single round at
   readout. RTG's earlier cycles-only caveat is CLOSED.
   Boot-time input patch (_rx_patch_regs) folded into the per-node offset,
   so the D24 console interleave still applies with DMA-direct kernels.
   sec_dmda 21,046 words vs 20,840 default, ceiling ~22,500. Bus
   accumulators sit in L2 (no room internally), so RTG is conservative.

   STRIPS CEILING - MEASURED 2026-08-24 on the default build: STILL 2.
     STRIPS=2  1500 transport / 1500 _proc_passes  REAL_TIME
     STRIPS=3  1500 transport / 1329 _proc_passes  OVER_BUDGET
   That is the expected answer, not a disappointment: the default image is
   byte-identical (d1c3dd5c/85d546f9), so its ceiling could not have moved
   - every conversion sits behind DSP4_BLOCK_KERNELS. 1329 reproduces the
   1342 measured before the rewrite.
   The CONVERTED build's ceiling cannot honestly be measured yet and was
   not: there the six unconverted classes run once per block instead of 32
   times, so a strips sweep would flatter itself ~32x on 88% of the strip.
   Use _proc_passes, never FRAME_COUNT - the ISR advances FRAME_COUNT
   whether or not the loop keeps up, and a first attempt that used it
   reported an impossible 2023 blocks/s.
   PROJECTED for the converted build: 2.91 -> 5.17 strips at 1x.
     per strip 63,131 -> 42,306 cycles/block (saved 20,825)
     fixed overhead 144,166 -> 109,064 (block I/O saved 35,102)
     328k budget - 109k fixed = 219k / 42.3k per strip = 5.17
   NOT measured, and deliberately so: a strips run on the block build would
   flatter itself badly, because the six unconverted strip nodes only run
   ONCE per block there and so appear 32x cheaper than they are. A real
   ceiling needs the whole strip converted. Against 32 strips required,
   5.17 says the remaining classes still have to come.

   PARKED, with state notes below and in dsp4-cycle-budget.md:
     FILT/EQ  CONVERTED 2026-08-24 (fourth attempt) - both bit-exact.
              FILT 6,973 -> 4,062 cycles/block (1.72x); EQ 11,590 ->
              7,998 (1.45x); both baselines re-measured on the CURRENT
              build, not taken from the pre-rewrite table. Strip 1,329 ->
              1,141 cycles/sample, projected ceiling 5.17 -> 5.99 strips,
              unconverted share 88% -> 52%, D24 4.6x -> 4.0x over.
              WHAT UNBLOCKED IT: a self-test on the part (DSP4_BQ_SELFTEST)
              ran _bq_fx_cascade_blk against _bq_fx_cascade_N on identical
              data - two stages with DIFFERENT coefficients, across a block
              boundary - and found 0 differing samples of 64. The routine
              was never the fault; the wrapper was. Three things it has to
              get right: input and output are DIFFERENT pool slots (the
              cascade works in place); i1 carries over HPF -> LPF; and
              crossfades are handed to the per-sample body a sample at a
              time via a new _<nid>_process_sample label, so the alpha
              bookkeeping and mid-block completion are right by
              construction instead of re-derived - re-deriving them is what
              defeated attempt one.
              Historical note, superseded: PARKED after three attempts. _bq_fx_cascade_blk is written,
              assembles, and its i0-advance-between-stages bug is now FIXED
              (it was only correct for r4=1, so EQ at r4=4 would have run
              every band with band 0's coefficients). That fix does NOT
              explain the failure: FILT calls it with r4=1, so i0 never
              advanced there. Wired, both_unity passes at 0 LSB and every
              real filter fails.
              CORRECTION, and it is the useful product of attempt three:
              the earlier reading of that unity pass was WRONG. With unity
              coefficients b1=b2=a1=a2=0, so y=x and the stored state
              contributes NOTHING - unity is blind to state. It therefore
              does NOT show that "the block plumbing is exercised and
              correct". Any wrong state pointer (wrong instance, wrong
              stride, HPF and LPF sharing a state block, state not
              persisted across blocks, the A/B crossfade instance) passes
              unity at 0 LSB and fails every real filter. Suspect order is
              now: (1) the state pointer the wrapper hands to i1 - test it
              with two sections carrying DIFFERENT coefficients; (2) state
              persistence across block boundaries; (3) only then MAC-unit
              implicit registers and m-register interference.
              A line-by-line diff of the two inner bodies was done: the
              arithmetic, MAC order, rounding, saturation test, error
              feedback and state store order are IDENTICAL to
              _bq_fx_cascade_N. It is not the maths. The block cascade is
              present but currently UNWIRED.
     COMP  still unconverted, but the "not worth converting" verdict is
              now SUSPECT and should be retested. It was judged on a bare
              WRAP, and GATE - the same class of node, also 8% slower under
              a wrap - converted at 1.23x once the block-invariant work was
              hoisted out of the sample loop (the _sample_idx guard, the
              on/off tests, four constant reloads, register-resident
              state). The general lesson on this page says a wrap alone
              buys nothing; COMP was measured that way and no other.
     TUBE  unconverted, 40 cycles/sample, trivial.
     Historical note, superseded: COMP/GATE NOT WORTH CONVERTING. A wrap alone measured
              8% SLOWER; the gain computer everyone assumed was the cost is
              only 9.6% of COMP; and _compgain_fx clobbers all but four
              registers so almost nothing can be hoisted across it. Ceiling
              is ~5% net. Step 4 of this plan (block-rate gain computer +
              interpolation, needing a numeric-spec amendment) is withdrawn
              on those numbers.

   THE GENERAL LESSON, measured three ways: a wrap on its own buys nothing.
   Every win so far came from work LIFTED OUT of the sample loop - the
   guard, hoisted invariants, inlined helpers, a gating tree run once. Ask
   of each remaining class "how much can be lifted", not "can it be wrapped".

   SCOPE GATING (step 6) DONE - and the projection above that called it
   "the biggest single remaining lever" was WRONG. Only 34 of the 431 nodes
   carry a scope= at all (32 D32-only, 2 D24-only, all of them TDM in/out,
   interchip send/recv and aux input). Measured booted as d24:
     no gating at all (control)   243,235 cycles/block
     per-NODE skip table          244,795   +1,560  A NET LOSS
     contiguous-RUN gating        241,744   -1,491  kept
   The per-node table loses because a table read and test before ALL 431
   dispatch calls costs more than not calling the 34 scoped ones, and that
   ratio does not improve per-sample either - check and node cost both
   scale by 32. The mechanism that works is one compare and one branch per
   contiguous RUN of same-scope nodes: two runs on chip 1, ~8 cycles/block
   against 1,491 saved. DSP4_SCOPE_GATE=1 selects it; the default image
   stays byte-identical. Chain still 0 LSB with a run branched over.
   Worth 0.46% of budget here, up to ~14% inferred for a per-sample build.
   Either way it is NOT a lever that changes the capacity picture.

0b. BASELINE MEASURED 2026-08-24 (post-fix build). Harness families are
   green and recorded in tools/dsp/hw-reports/README.md - that is the
   bit-exactness reference. GAIN cycle baseline re-measured on the current
   build: NODE_LIMIT=1 (IN only) 67,809 cycles/pass, NODE_LIMIT=2 (IN+GAIN)
   70,130, so GAIN = 2,321 cycles/block = 72.5 cycles/sample. Almost all of
   that is overhead - a call/rts per sample, the _sample_idx==0 guard
   evaluated 32x, and a second call/rts into _mrf_rns28.

0c. DESIGN, decided 2026-08-24 before any code. The conversion is NOT
   node-local: a per-block kernel needs per-block BUFFERS, so the sample
   loop, scatter/gather and every node buffer move together. Shape:
       for s in 0..31: scatter(s)        -> fills 32-word input buffers
       process_all_block()               -> one call per node per block
       for s in 0..31: gather(s)         -> drains 32-word output buffers
   Each node's `.var _buf_X` becomes `.var _buf_X[32]`; the block-rate
   section (ramp + Q4.28 shadow refresh) runs ONCE at kernel entry with no
   guard, and the 32-sample loop wraps only the arithmetic. _mrf_rns28
   should be inlined in the loop rather than called.
   Do it behind DSP4_BLOCK_KERNELS (default 0) so the tree stays buildable
   and the per-sample path remains the reference to diff against. Convert
   IN + GAIN first and profile at NODE_LIMIT=2, which needs no other node
   to change; roll the rest of the chain class by class after.
   Expected for GAIN: the arithmetic is ~8-12 cycles/sample, so the target
   is under ~400 cycles/block against 2,321 - a 6x class of win, and the
   same overhead is paid by every one of the 431 nodes.

1. GENERATOR: nodes become per-BLOCK kernels — one call per node per block,
   the 32-sample loop inside the kernel, parameters fixed once per block (as
   D5 already specifies). Control/ramp plane unchanged. Prove on GAIN first
   (simplest): bit-exact + cycles/sample, then roll the generator change
   across the classes as each kernel is rewritten.
2. RTG + bus/send path (the measured hot spot, 601 cyc/sample + 24 % fixed):
   a send to N buses is N MACs; drop per-sample table walks, compute routing
   masks at block rate, SIMD the accumulate. Target ≤ 40 cyc/sample.
3. EQ / FILT: D5 fixed-point biquads, wide accumulators, SIMD two channels
   or two sections; coefficient staging at crossfade-swap as implemented.
   Target ≤ 25 cyc/sample for the strip's bands.
4. COMP / GATE / LIM: envelope per sample (one-pole Q4.28), gain computer
   (log2/exp2 polynomials) at BLOCK rate with per-sample interpolation of the
   gain — write the interpolation as a numeric-spec amendment with its error
   bound, verified by the harness dynamics rows. Target ≤ 50 cyc/sample for
   COMP+GATE.
5. Block I/O (20 % fixed): scatter/gather without the per-sample Q-format
   shuffles — convert once per lane per block; meter scan at block rate.
5b. METERS — fold in the MTR-node rework (added 2026-08-24 by hub steer).
   Measured 2026-08-23: the MTR node class is numerically meaningless. It
   loads a Q4.28 INTEGER and does `f0 = abs f0`, and r0/f0 are the same
   SHARC register, so the bit pattern is reinterpreted as IEEE-754 — peak
   read 3.85e-34 for a 0.5 input. RMS is dead (the peak branch takes an
   early rts before the RMS update), decay runs per sample against a
   comment written for the 1500 Hz block rate so the time constant is 32x
   fast, and _mtr_gr is declared and never written. Values are host-visible
   at SPI 0x1200/0x1201 with mislabelled dispatch comments.
   The LIBRARY meter path (_meter_peaks[], _meter_scan_chip1) is correct
   and is what the host readback contract uses — measured 0.49975 for a 0.5
   input, converting properly and decaying per block.
   OPTION FOR THE HUB TO DECIDE HERE: if the library meter is the only path
   the host contract uses, RETIRE the MTR nodes rather than repair them —
   that removes ~32 nodes per chip from the per-sample graph, which serves
   this block's cycle-budget goal directly. If they are kept, they need the
   fixed->float conversion, the RMS ordering fix, a decay-rate decision,
   and a meter model added to fixed_ref.py (there is none) before they can
   go under the harness. Report: tools/dsp/hw-reports/mtr-2026-08-23.md.
   Also unmeasured but found by inspection: _meter_decay_block decays 32
   entries while _meter_scan_chip1 writes 46, so 32-45 never decay.

6. SCOPE GATING (option 3): make _scope_gates_apply real — D24 runs only D24
   nodes; bypassed nodes are skipped at the dispatch table, not inside the
   kernel. Measure the D24 graph, not D32's.
7. After each step: re-run the cycle table + the harness rows for the touched
   family; record cyc/sample before/after in dsp4-cycle-budget.md; commit.
   Stop condition for the block: 32 strips at 1x with FRAME_COUNT 1500/s and
   all harness families green, or a precise state note of where it stands.

Rules: bench = rev-C CM4 app@192.168.1.219; the loopback-capture bitstream
may stay flashed while this block runs (same ruling as the virtual-audio
block); restore SHIPPING at the end; rev A hands-off; matrix-app running +
3 MCUs verified at every stop; single trunk; no AI attribution; numeric-spec
changes are amendments with a date, never silent.

## QUEUED — PRODUCT CONCEPT (PW 2026-08-23): low-cost 8x8 mixer on a Pi, software DSP, dual FX   [status: 🔵 concept, not scheduled — for PW/hub decision, no build work started]

model: opus

PW floated this in conversation on 2026-08-23; recorded here so it is not lost.
NOT a dispatch. Nothing is committed to and no schedule is implied.

THE CONCEPT: 8 in / 8 out mixer, DSP done in software on the Pi itself (no
SHARC card), dual FX only, small screen, no buttons, simple and low cost.
Candidate platform floated: Raspberry Pi Zero 2 W.

WHERE IT SITS IN THE RANGE: below everything D6/D7 govern (those start at
32 ch). It does not conflict with the D6 platform split or the D7
fabric-only baseline. It WOULD introduce a THIRD engine platform alongside
SHARC (D5 fixed-point) and FPGA fabric — that is the strategic cost and it
is a hub/PW call, not an engineering one.

MEASURED (this bench, 2026-08-23):
- matrix-app RSS = 237 MB (self-contained .NET/Avalonia, VSZ 3.6 GB) on the
  rev-C CM4, which has 730 MB usable. That is the number any UI alternative
  has to beat, and it is over half a 512 MB Zero 2 W before audio allocates.
- bcm2835-i2s is hard-limited to 2 channels per direction (already recorded
  in MW/D32/DSP/dsp4-plumbing.md). 8x8 at 48 kHz CANNOT come off the Pi PCM
  pins directly.
- Route A works and is proven: 2 ch x 32 bit @ 192 kHz = 12.288 Mbit/s =
  exactly 8 ch x 32 bit @ 48 kHz. Duplex measured 191999/191999 frames clean.
  So one stereo 192 kHz link carries all 8 channels each way — but ONLY with
  external re-framing logic (dsp4_pcm_reframe.v already does this).

ESTIMATED, NOT MEASURED — flagged as such:
- 8 strips + 8x8 matrix + 8 output strips + 2 FX is roughly 2,700 flops per
  sample, ~130 MFLOP/s at 48 kHz: order 10 % of ONE A53 core with NEON.
  The DSP maths is not the constraint. Do not quote this as measured.
- The SHARC 6.6x-over-budget finding does NOT transfer: that graph is 431
  nodes invoked PER SAMPLE (13,792 calls/block). A block-processed software
  design does not inherit that structure.
- Pi Zero 2 W carries the same BCM283x PCM block as the CM4 and should take
  the existing dsp4-pcm-slave.dts unchanged (it is compatible = "brcm,bcm2835"
  and targets the generic &i2s_clk_consumer / &sound labels). UNVERIFIED —
  no Zero 2 W has been on this bench.

THE REAL RISKS, in order:
1. Linux real-time behaviour, not MIPS. SDIO Wi-Fi DMA contention, non-RT
   preemption and thermal throttling are the likely xrun sources. Needs
   PREEMPT_RT, isolcpus, SCHED_FIFO, Wi-Fi power-save off. Which cause
   actually dominates is MEASURABLE (cyclictest + xrun counters) and should
   be measured before any distro or platform commitment.
2. You still need a logic device. The CPLD does not go away; it is cheap
   (re-framing only, far simpler than DSP4 LOGIC) but it is in the BOM.
3. Zero 2 W is a BOARD, not a module — no castellations, no SO-DIMM, and
   RPi guidance for products is Compute Module. Designing it in means a
   40-pin mezzanine plus connectors you do not want. CM4 Lite costs ~$15-20
   more on a BOM dominated by converters, 16 channels of connectors, PSU and
   enclosure. RECOMMENDATION ON RECORD: CM4 Lite unless the price point
   genuinely turns on that delta.

OPEN DECISIONS (these gate everything else, and they are PW's):
- (a) CONTROL SURFACE. "Small screen, no buttons" — touchscreen, or is the
  screen status-only with control from a phone/web app? If the phone is the
  control surface, the on-device UI becomes a few hundred lines of SDL or
  framebuffer, .NET disappears, Buildroot becomes easy and 512 MB stops
  mattering. This is the highest-leverage question in the whole concept and
  it is upstream of (b) and (c).
- (b) UI STACK. If the product stays inside the matrix ecosystem, keep
  Avalonia and use PublishAot + trimming (the cell/MxAdd/CellRebinder
  binding layer is the expensive part to replace, not the widgets). If it is
  a standalone appliance, Slint is preferred over LVGL for its declarative
  binding — but Slint is GPLv3 or paid commercial, and Qt licensing is a
  real cost at this price point. Chromium kiosk and Flutter ruled out at
  512 MB.
- (c) DISTRO. Buildroot buys boot time (~2-5 s vs 20-30 s), a read-only
  rootfs (power-fail immunity on SD — arguably the strongest argument), and
  easy PREEMPT_RT integration. It buys NOTHING for the DSP or the PCM limit,
  and it fights back hard if the product needs BlueZ + PipeWire for the
  Bluetooth path or .NET for the UI. Decide AFTER (a) and (b). A pinned
  defconfig in git would fit the defs.lock discipline and would replace the
  current hand-applied config.txt provisioning.
- (d) NUMERIC SPEC. D5 says one numeric spec across targets. An ARM engine
  should therefore arguably be Q4.28 fixed-point, not float, so
  dsp_simulate.py golden vectors stay normative across all three platforms.
  A53 does fixed-point fine. Float would be a deliberate deviation needing
  a D-number.

USB MULTITRACK RECORD/PLAY (PW asked 2026-08-23): 8 ch to removable media.
ESTIMATED, NOT MEASURED.
- Bandwidth is a non-issue: 8 ch x 48 kHz x 24 bit = 1.15 MB/s, ~2.3 MB/s
  if record and play run together, against 15-25 MB/s realistic for USB 2.0
  HS on this part. One hour of 8-track 24/48 is ~4.15 GB.
- THE RISK IS NOT BANDWIDTH, it is USB host overhead colliding with the
  real-time audio thread. The Pi's DWC2 controller does much of its work in
  software (FIQ-driven) and USB traffic causing audio dropouts is a
  well-known Pi failure mode. This lands on top of risk 1 above and is the
  thing to MEASURE early, not reason about.
- Single OTG port, no onboard hub. The stick occupies the only port, and it
  is the same port the USB 2-track audio path would want.
- USB sticks stall for hundreds of ms during wear-levelling, which is fatal
  for live recording. Mitigation is cheap: 30 s of 8-track ring buffer is
  ~35 MB, affordable even in 512 MB, behind a writer thread.
- Recommend: specify a USB SSD rather than a stick; write PER-TRACK mono
  files (518 MB/hour each, dodges the FAT32 4 GB ceiling that an
  interleaved 8-ch WAV hits at 57 minutes); consider an SD partition
  instead, which skips USB host overhead entirely at the cost of swappable
  media.
- OPEN QUESTION for PW, changes the storage spec more than the Pi choice
  does: are record and play SIMULTANEOUS, or separate modes? Multitrack
  record and virtual-soundcheck playback usually are not concurrent; only
  overdubbing needs both. Separate modes halve the load and keep the media
  in the one-direction case where cheap flash behaves best.

CHEAPEST NEXT STEP IF IT IS TAKEN FURTHER: publish a stripped Avalonia
sample with PublishAot=true for linux-arm64 and measure RSS on the bench
CM4. One afternoon, and it settles whether the existing stack fits a tight
platform or whether a second UI line is genuinely needed.

POSSIBLE REUSE, worth weighing against the third-platform cost:
tools/dsp/dsp_codegen.py already generates node code from dsp.csv and could
emit C instead of SHARC ASM; dsp_simulate.py golden vectors are normative
per D6 and would validate an ARM build too.


## HUB DISPATCH 2026-08-22 19:05Z — SPI PARAMETER LINK — the handler runs exactly ONCE per reset (RX FIFO above watermark / ROR / host ignores RDY)   [status: 🟢 done — **the link is UP on both chips and the whole diagnostic register block now reads off a running SHARC, a first for this card.** Root cause of once-per-reset: the SEC handshake is TWO-step and `_sec_isr` only did steps 1 and 4 — it never wrote `SEC_CSID0` back to acknowledge, so the SEC never arbitrated another request. One line took SEC_COUNT from 1 to 94. Proved by bisect rung 27, which polls the SAME handler and round-tripped correctly while the interrupt build was stuck at one. Three more fixed: the RFIFO came out of boot FULL (no flush bit exists — `SPI_CTL.EN` must go low, HRM 15; now measured empty, ROR/RUWM clear); the handler drained an empty FIFO and dispatched the garbage (RFE guard added); and `dsp4_diag.py` asserted GPIO7 for chip 2 where `dsp4_boot.py` has always used GPIO24 — the whole reason chip 2 read all-zero. Chip 1 and chip 2 both return MAGIC 0xD5B40001 and their own CHIP_ID. STILL OPEN, precisely characterised: a write (or DIAG_NOP) queues no answer but still clocks two words out of the 2-deep TFIFO, leaving an odd word outstanding and slipping every later echo by one — so reads are solid but write-then-read-back is not. Real fix is DSP-side: make every accepted transaction queue exactly one two-word answer. Also open: SPI2_RDY never asserts even with the RFIFO empty, so dispatch task 2 as written is not actionable — a host honouring this RDY would wait forever]

model: opus

Continue the 🟡 SPI PARAMETER LINK item above. Two root causes are fixed
(SPI2 pins never routed; IIVT never set). Remaining: ~21 host transactions →
`SEC_COUNT = 1`, `SPI_RX_COUNT = 1`, MISO a constant `0x697EBB71`;
`SPI2_STAT = 0x00144033` = RUWM still asserted after the two-word drain,
ROR + TUR + FCS set, PB_05/RDY low. Clearing `SPI2_ILAT` is in the tree and
changed nothing — keep it, do not call it a fix. Read your own notes in the
🟡 block first.

Bench: the rev-C unit, CM4 app@192.168.1.219 (`/home/app/dspboot`: dsp4_boot.py,
spiraw.py, dsp4_diag.py, dsp4_stagewatch.py), reachable now and 24/7. The rev-A
show unit (.115) is hands-off — never touch it.

TASK (hands-off desk + bench work, chase it to ground):
1. WHY does the RX FIFO stay above the watermark after a two-word drain? Check
   the 2-deep-FIFO / UWM_FULL reasoning in `spi2_init()`'s comment against the
   HRM SPI chapter (RFIFO depth, RUWM semantics, what clears RUWM). Determine
   whether ROR needs an explicit flush (RFIFO flush bit / status W1C) or an
   SPI_EN off→on before the channel resumes. Prove it with a register dump
   before/after — no inference.
2. Make the host honour RDY: pass `--rdy-gpio 8` (or add it) to spiraw.py and
   dsp4_diag.py so the master stops clocking a stalled slave. Re-measure the
   21-transaction probe with RDY honoured; record SEC/RX counts + SPI2_STAT.
3. Only then the response framing: the read path queues its answer for the
   master's NEXT transaction. Exercise it: write a parameter, read it back on
   the following transaction, prove the value round-trips on chip 1 then chip 2.
4. Record the verdict in the 🟡 block (flip to 🟢 when the link round-trips);
   if a fault is in the PCB, it is a red mod in the mods PDF — tell the hub,
   do NOT edit the PDF from this machine (its Dropbox scope is _Matrix,
   TransferOnly, _fx, config only; the hub owns the SOT markup).
5. If it cannot be closed, leave a precise state note (register dumps, what
   was tried, what is excluded) and stop.
Constraints: chips freely bootable; ALWAYS restart matrix-app + confirm the 3
MCUs verify before ending or between long gaps — never leave the unit on a
frozen splash; ~/db Dropbox; single trunk; no AI attribution; disk is now
222 GB free — do not recreate the buildroot tree.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-22 20:3xZ — 🟢 the SPI parameter link is UP on both chips

**The full diagnostic register block now reads off a running SHARC.** That
has never happened before on this card. Chip 1, production build
(`DSP4_BISECT=0`), interrupt-driven:

```
MAGIC 0xD5B40001   CHIP_ID 1 (DSPA/U6)   BOOT_STAGE 5 (waiting for host
config)   TICKS 74671   SEC_COUNT 38   LAST_CSID 71 (SPI2_STAT)
SPI_RX_COUNT 48   SPI_ERR_COUNT 0   UNK_COUNT 0   RESP_DROP 0
SPI_STAT 0x00540001   BUILD_ID 0x20260812
```

Chip 2 answers too: MAGIC `0xD5B40001`, **CHIP_ID 2**, BUILD_ID
`0x20260812`.

#### ROOT CAUSE of "the handler runs exactly ONCE" — the SEC handshake is two-step

`_sec_isr` read `SEC_CSID0` and wrote `SEC_END`, but never did the step in
between. HRM ch.6, *Core/SEC Handshake Requirements*, is explicit:

1. read `SEC_CSID[n]` for the source id
2. **write that value BACK to `SEC_CSID[n]`** — the acknowledge that tells
   the SEC the core has accepted the request
3. run the handler
4. write the same id to `SEC_END`

Without step 2, *"the SEC knows what it passed to the core because of the
write to the SEC_CSID[n] register"* never happens, so it never arbitrates
another request. **One SECI per reset, exactly as observed.** One line in
`sport_init.asm` took SEC_COUNT from **1 to 94** over the same probe.

What proved it was delivery rather than the SPI block: bisect rung 27
polls `SPI_STAT.RFE` in the main loop and calls the SAME handler. Polled,
the link round-tripped MAGIC, CHIP_ID and BUILD_ID perfectly while the
interrupt-driven build was still stuck at one. Handler good, SPI good,
delivery broken.

#### Three more faults fixed on the way

**The RFIFO came out of boot already full.** There is no flush bit on this
part — *"the receive FIFO is reset (cleared) when the SPI is disabled after
being enabled"* (HRM 15) — and the boot kernel hands over with SPI2 still
enabled. `spi2_init()` now takes `SPI_CTL.EN` low before configuring.
Measured before/after on a fresh boot with no host traffic at all:

| | before | after |
|---|---|---|
| `SPI2_STAT` | `0x00144033` | `0x00540020` |
| RFIFO level | **FULL** | **empty** (RFE=1) |
| ROR / RUWM | set / set | **clear / clear** |

**The handler drained an empty FIFO.** The SEC can deliver more events
than there are transactions — 94 handler entries against 48 words actually
clocked in. Reading `SPI_RFIFO` empty returns garbage, and that garbage
was then dispatched as a request, which is why the host saw one constant
meaningless answer. Both `spi_handler.asm` variants now check
`SPI_STAT.RFE` before draining, the same check the polled variant used.

**`dsp4_diag.py` asserted the wrong chip select for chip 2.** It defaulted
to GPIO7; `dsp4_boot.py` has always had the right map (`CS_GPIO = {1: 6,
2: 24}`). That is the whole of why chip 2 answered all-zero on MISO while
chip 1 worked — the tool was selecting something DSPB does not listen on.
Fixed in `dsp4_diag.py`.

#### The transmit path was never broken

Priming `SPI_TFIFO` with `0xA5A5A5A5` made MISO return `0xA5A5A5A5` for
every transaction, which identifies the old constant `0x697EBB71` as
nothing more than an unloaded shift register. The priming was removed
again once it had answered the question — it puts every response one
transaction out of step.

#### STILL OPEN — a write between reads slips the word phase

Reads pipeline correctly: each transaction carries the previous request's
echo and value, exactly as `diag.asm` describes. But a transaction that
produces NO response — a register write, or `DIAG_NOP` — still clocks two
words out of the 2-deep `SPI_TFIFO`, leaving an ODD number of words
outstanding. Every later echo then lands where a value should be, and it
does not self-correct: re-asking consumes two more words and preserves the
bad phase. A one-word (4-byte) transfer would re-align it.

So `dsp4_diag.py` reads a whole register block cleanly, but the
write-then-read-back round-trip (`--led`, and hence `dsp4_config.py`'s
CONFIG_COMMIT path) is not yet reliable.

**The real fix is DSP-side and small: make every accepted transaction
queue exactly one two-word answer** — a write echoing its request word
with value 0 — so the stream is aligned by construction instead of by
convention. It touches both `spi_handler.asm` variants and the protocol
note in `diag.asm`, and it shifts what `dsp4_config.py` sees, so it wants
doing deliberately rather than at the end of a long session. A bounded
re-ask is in `dsp4_diag.py` now as a WORKAROUND and is commented as one.

#### Loose ends worth knowing

- **`SPI2_RDY` never asserts.** On a fresh boot with the RFIFO verifiably
  EMPTY (RFE=1, ROR=0, RUWM=0) the part still has `FCS` set and drives
  PB_05 low. With FCPL=1 (active-high per HRM Table 15-18) and FCWM=1
  (RFIFO ≥ 75% full), an empty FIFO should read READY. It does not, and
  the RX-channel flow-control rule alone does not explain it. The link
  works anyway because the host never waits on RDY. Task 2 of the dispatch
  — "make the host honour RDY" — is therefore NOT actionable as written:
  a host that honoured this RDY would wait forever. Left open.
- `SPI_STAT` sticky bits after a good session are TUR and FCS only. TUR is
  expected: TEN is set and the TFIFO is empty between responses.
- FRAME_COUNT is 0 and DMA0_STAT reads `0x00006032` — no audio block has
  arrived, which is expected while the LOGIC CPLD is not sourcing frame
  syncs. Not a link fault.

**Bench state:** both chips hold the production `c1_p8`/`c2_p8` images
(all fixes, `DSP4_BISECT=0`); `matrix-app` restarted and active; all three
MCUs verified 20:34-20:35; GPIO 6/7/8/9/10/11/12/24 returned to `a0`.

## SPI PARAMETER LINK 2026-08-22 — 🟡 two more root causes fixed, one still open

Follow-on from the P2.2 close below, working the one thing that blocked
everything downstream. Two more faults of the same family as D15 —
things `___lib_setup_c` does that this firmware never did, and things
configured but never connected.

### FIXED 1 — the SPI2 pins were never routed to the pads

New instrument, `DSP4_BISECT=22`: read SPI2_CTL/RXCTL/TXCTL/STAT and the
PORTA/PORTB FER and MUX registers off the running part and frame them
onto PB_05 in clkprobe's encoding, so the question can be answered
without the link that is broken. Registers are snapshotted BEFORE the
pin is taken, because taking it clears PORTB_FER — one of the values in
question.

| register | before | after |
|---|---|---|
| `SPI2_CTL` | `0x0001A501` | unchanged |
| `PORTA_FER` | **`0x00000000`** | `0x00000033` |
| `PORTB_FER` | **`0x00000000`** | `0x00000020` |
| `PORTB_MUX` | **`0x00000000`** | `0x00000400` |

`spi2_init()`'s writes had ALWAYS taken — CTL decodes as EN, EMISO,
SIZE32, FCEN, FCPL, FCWM, MSTR=0, exactly as written. The block was
correctly configured **and wired to nothing**. Nothing in this firmware
had ever set a FER or MUX bit; the only port writes it made were to
CLEAR FER, for the LED and the RDY mirror.

Pin assignment now in `spi2_init()`, from the data sheet Rev. A Tables
10/11 — **the GPIO multiplexing table earlier notes recorded as missing;
it is in the datasheet already in Dropbox**: PA_00 SPI2_MISO, PA_01
SPI2_MOSI, PA_04 SPI2_CLK, PA_05 SPI2_SEL1 (with SPI2_SS on the input
tap, which is the host's CS), all mux function 0; PB_05 SPI2_RDY, mux
function **1**. Port A's mux is already 0 at reset so only FER is set
there; port B's MUX5 is read-modify-written so other pins keep theirs.

**Effect: the part now drives MISO.** Every readback was `0x00000000`
before; it is real data after.

### FIXED 2 — CMMR_SYSCTL.IIVT was never set, so no interrupt could be taken

Found by bisecting the interrupt path with three new rungs. Rung 25
(mask everything) was the control that proved the dump instrument
works — it reported `IRPTL = 0x00408820`, i.e. TMZLI, TMZHI, SECI and
CB7I all LATCHED, with `DIAG_TICKS = 0`. Rung 24 (only the core timer
unmasked) went dead. **Rung 26 — the same thing with an RTI-only TMZLI
vector — also went dead**, which is what says the fault was in TAKING
the interrupt, not in any handler.

`CMMR_SYSCTL.IIVT` selects the INTERNAL interrupt vector table, the one
`src/ivt.asm` assembles at 0x00090000. Reset entry does not need it,
because the boot kernel jumps straight to the entry address rather than
vectoring — so everything looks healthy right up until the first
interrupt is taken. `___lib_setup_c` sets it for every SHARC+ part; this
firmware does not link it. It is now in `C_RUNTIME_INIT` (`src/c_abi.h`)
with the rest of that family.

**Effect, measured: `DIAG_TICKS = 0x3213` — 12819 ticks over a 12 s
window at the 1 ms tick.** The core-timer ISR had never run before
today. The LED fault codes work for the first time as a consequence.

With SECI unmasked as well: `SEC_COUNT = 1`, `SPI_RX_COUNT = 1`, and
`SEC0_SCTL71 = 0x5` (IEN bit 0, SEN bit 2 — both set, so the SPI2_STAT
route is correct). The SEC ISR runs, demuxes, and the SPI handler runs.
**The whole chain SEC route -> SEC ISR -> SPI handler is proved.**

### STILL OPEN — the handler runs exactly ONCE per reset

~21 host transactions produce `SEC_COUNT = 1`, `SPI_RX_COUNT = 1`, and
MISO stuck on a constant `0x697EBB71` — the same word for every input,
at every clock, in either SPI mode, which is a TX FIFO nobody reloads.
`SPI2_STAT = 0x00144033` decodes as **RUWM still asserted after the
handler drained two words, ROR (receive overrun) set, TUR set, and FCS
(flow-control stall) set** — and PB_05/RDY reads low, i.e. the part is
telling the host to stop, which `spiraw.py` and `dsp4_diag.py` both
ignore because neither passes `--rdy-gpio`.

Clearing `SPI2_ILAT` in the handler was the obvious candidate and is now
in the tree (ADI's own drivers do it), but **it changed nothing** — the
measurement after it is bit-identical. It is kept as correct-but-not-
the-cause, and the comment in `spi_handler.asm` says so. Do not read it
as a fix.

**Next, in order.** (1) Why does the RX FIFO stay above the watermark
after a two-word drain — is the 2-deep-FIFO/UWM_FULL reasoning in
`spi2_init()`'s comment right, and does ROR need an explicit flush, or
an EN off/on, before the channel resumes? (2) Have the host honour RDY
(`--rdy-gpio 8`) so it stops overrunning a stalled slave; that may be
half the picture. (3) Only then the response framing — the read path
queues its answer for the master's NEXT transaction, and none of that
has been exercised yet.

### Also fixed on the way

- `dsp4_config.py` requested the RDY line even when none was asked for,
  passing `None` to gpiod — which is why `dsp4_diag.py` crashed on
  start. It runs now.
- `dsp4_clkprobe.py` gained `--frame spi2` / `--frame secspi` decoders, a
  pulse-burst counter, and MAGIC alignment for every framed image (a
  capture may start mid-transcript). Two bit tables in it were written
  from memory and were WRONG — SPI_CTL's EMISO/FCEN/FCPL positions, and
  SEC_SCTL's SEN/IEN — both corrected against `sys/ADSP-21564.h`.

**Bench state:** production images built with all of the above; chip 1
holds the rung-23 diagnostic image from the last measurement.

## HUB DISPATCH 2026-08-21 20:34Z — P2.2 cont'd — _sru_init hang + the ~190 vs 400 MHz CCLK suspect (nail the clock, get past SRU, reach dma_cfg_init)   [status: 🟢 done — **P2.2's wedge is closed: both chips now run the ENTIRE init sequence** — SRU, SPORTs, DMA rings, SEC, SPI2 — and park at the host handshake (bisect rung 21, chip 1 and chip 2). CCLK is **491.52 MHz**, measured off the core timer and confirmed against the CGU registers read out of the running part; the "~190 MHz" figure is RETRACTED (it divided by an assumed 5 cycles per delay-loop iteration; the real cost is 13). The CGU is left at its reset defaults by decision — they already give a fully in-spec tree from 24.576 MHz — and the firmware's own constants are corrected instead. `_sru_init` was never a clock or a peripheral fault: **main.asm was calling C with the wrong ABI**, and the four assembly helpers C calls returned with `rts`. Two real bugs fixed: the cc21k call convention (new `src/c_abi.h`, decision D15) and **IMASK/IRPTL never cleared after boot**, which killed the core as soon as eleven DMA channels were armed with the boot kernel's interrupts still live. `dma_cfg_init`, `sport_dma_base()` and `l1_to_sys()` all now have their hardware test and all pass. STILL OPEN, and it is a different subsystem: the SPI parameter link answers all-zero, so nothing downstream of the handshake is proven — that is the next item]   [model: opus]

model: opus

BIG progress: the >8KB boot-stream limit is resolved and chip 1's FULL
firmware now executes (dsp 9100107 — the boot bus has one master again).
P2.2 is NOT closed: the firmware now hangs in `_sru_init`'s DAI0 half on the
first SRU register writes; dma_cfg_init + the sport_dma_base() fix remain
untested downstream. Standing prime suspect: **CCLK is ~190 MHz but the
firmware assumes 400 MHz** (SRU/DAI timing, waits). Read your own last
session's notes + the commits first.

TASK (overnight desk work — chase it to ground, hands-off):
1. NAIL the actual CCLK. Compute it from the fitted clock chain: SYS_CLKIN0
   = 24.576 MHz (the ÷2 CPLD + level-shift bodge) → CGU reset defaults
   (MSEL/DF/CSEL from the HRM) → CCLK. If that yields ~190 MHz, the firmware
   MUST configure the CGU (or its assumptions) for the real clock. Confirm
   against a measurable (LD3/CCLK cadence via stagewatch, or a known-rate
   blink) rather than assuming.
2. If CCLK ≠ 400 MHz: either (a) program the CGU in firmware early-init to
   reach the intended CCLK from 24.576 MHz CLKIN, or (b) correct the
   firmware's clock assumptions (SRU/DAI wait counts, any 400 MHz constants).
   Decide which is right (design note in dsp4-architecture-decisions.md).
3. Get past `_sru_init`: with the clock correct, does DAI0 SRU init complete?
   Walk forward (your DSP4_BISECT / stagewatch instruments) to dma_cfg_init;
   the sport_dma_base()/l1_to_sys() fixes finally get their hardware test.
4. Iterate to a full chip-1 run, then chip 2. Record the verdict; when
   closed, revert temp instrumentation + rebuild clean production images.
5. If it can't be closed tonight, leave a precise state note (where it hangs,
   the measured CCLK, what you tried) for the morning.
Constraints: chips freely bootable; ALWAYS restart matrix-app + confirm the
3 MCUs verify before ending or between long gaps — never leave the unit on a
frozen splash; ~/db Dropbox; single trunk; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 22:4xZ — 🟢 the init sequence runs end to end on both chips

**Headline: `_sru_init` was a C-calling-convention bug, not a clock and
not a peripheral.** Every register write in it always completed. What it
could not do was return.

#### 1. CCLK is 491.52 MHz. Measured, not inferred.

New instrument, `src/blink/clkprobe.asm` + `tools/pi/dsp4_clkprobe.py`:
a standalone image that times everything off the SHARC **core timer**,
which decrements once per core-clock cycle by construction, and frames
the result onto PB_05 as pulse-width-coded words. Two independent
readings in one transcript — the tick unit and a 32-tick square — both
gave **491.52 MHz** to five figures. The same image reads the CGU back
out of the running part:

| register | value | fields |
|---|---|---|
| `CGU0_CTL`   | `0x00002800` | DF=0, MSEL=40 |
| `CGU0_DIV`   | `0x05144281` | CSEL=1, SYSSEL=2, S0SEL=4, S1SEL=2 |
| `CGU0_STAT`  | `0x00000005` | |
| `CGU0_DIVEX` | `0x00200030` | |

Those are the reset defaults, and with SYS_CLKIN0 = 24.576 MHz and the
2156x PLL's built-in /2 they give PLLCLK/CCLK 491.52, SYSCLK 245.76,
SCLK0 61.44, SCLK1 122.88 MHz — all inside the datasheet ranges, and
fCCLK = 2 × fSYSCLK as required. **This is exactly what D10 predicted.**

**DECISION (dispatch item 2): do NOT program the CGU; correct the
firmware's assumptions.** The defaults are already in spec and
audio-rational, so a CGU write in early init buys nothing and costs a
PLL relock during boot on the shared SPI port. Written up as the D10
addendum in `dsp4-architecture-decisions.md`. `DIAG_TPERIOD` is now
491520 (a 1.000 ms tick) and the blink images carry
`CCLK_HZ = 491520000`.

**RETRACTED: "~190 MHz".** It came from the blink rate divided by an
*assumed* 5 cycles per iteration of a two-instruction delay loop. The
real figure is **13 cycles** (measured: the park's 15,000,000-iteration
half period is 397 ms at 491.52 MHz), and 13/5 × 400/491.52 = 2.12 —
the whole of the "2.1x slow" observation. Nothing was wrong with the
clock. Every 400 MHz and 190 MHz constant and comment in the tree is
now corrected or deleted.

#### 2. The SRU register space was innocent — proved before touching it

`src/blink/sruprobe.asm` performs the DAI0 half of `sru_init()`
write-for-write in a standalone image with no C, no stack and no
interrupts, pulsing PB_05 after each one. **All 36 writes complete**,
repeatedly, and the routing reads back changed (`DAI0_DAT0` 0x08144040
at reset → 0x02144040 after; `DAI0_CLK0` 0x24992649; `DAI0_PIN0`
0x03480B14). So "the DAI0 block is unclocked / not answering the bus"
is dead as a theory, and so is the CCLK suspicion behind it.

#### 3. ROOT CAUSE — the cc21k C ABI was never being met

`cc21k` returns from a C function with `jump (m14,i12) (db); rframe;`
after fetching the return address with `i12 = dm(m7,i6)`, and callers
must use `cjump fn (db); dm(i7,m7)=r2; dm(i7,m7)=pc;`. `main.asm` used a
plain `call` and set up the stack **B/I/L registers but not one M
register** — with M7 and M14 left at whatever the boot kernel had put
there, the frame push and the return both went somewhere arbitrary.
The same mismatch ran the other way for the four assembly helpers C
calls (`_diag_stage_set`, `_diag_irq_off`, `_set_rx_bufs`,
`_set_tx_bufs`), which all returned with `rts`.

Fixed by a new `src/c_abi.h` — `C_RUNTIME_INIT`, `CCALL()`, `C_RETURN`,
copied from what the compiler emits and from CCES's own
`SHARC/lib/src/libc_src/set_c.asm`, with every deliberate divergence
from `___lib_setup_c` documented in the file (L6/L7 linear; NESTM NOT
set, because `diag.asm` and `_sec_isr` require non-nesting interrupts;
MMASK and IRPTEN left to their owners). Recorded as **decision D15**.

**Result on hardware: bisect rung 8 (park after `_sru_init` returns)
went from 0/6 silent to firing 6/6.**

#### 4. SECOND BUG — IMASK and IRPTL are never cleared after boot

Found by bisecting inside `dma_cfg_init` once it became reachable. Rung
16 (a pulse per lane, no park) showed **all 8 region-A lanes and all 3
region-B lanes arming and both `arm_region()` calls returning** — while
rung 1, whose park is two statements later, stayed silent. Rung 17 (rung
1 with interrupts turned off *before* arming instead of after) fired.
So the variable was the live interrupt, not the DMA.

The SPI target boot kernel hands over with its own interrupts still
unmasked and latched; `_diag_init` only ORs TMZLI in, so those survive
and fire into an IVT with no handler the moment IRPTEN goes on. Adding
`imask = 0; irptl = 0;` to `_start` (what `___lib_setup_c` does, and for
this exact reason) made rung 1 fire immediately. Also in D15.

#### 5. Where the firmware is now — all of it runs

Bisect ladder on chip 1, six boots' worth of sampling per rung, read
over ssh with `dsp4_stagewatch.py`:

| rung | park point | before | after |
|---|---|---|---|
| 8 | after `_sru_init` | **0/6 silent** | fires |
| 9 | after `_sport_cfg_init` | 0/6 silent | fires |
| 4 | entry to `dma_cfg_init` | 0/6 silent | fires |
| 13/14/15 | first lane: before DSCPTR / before CFG / after CFG | — | all fire |
| 16 | a mark per lane (does not stop) | — | 8 + 3 lanes, both regions |
| 1 | after `arm_region(A)` | silent | fires (needed the IMASK clear) |
| 2 | after `arm_region(B)` | silent | fires |
| 20 | after `enable_region` = end of `dma_cfg_init` | — | **fires** |
| 21 | main.asm, at the `.wait_boot` host handshake | — | **fires on chip 1 AND chip 2** |

**`dma_cfg_init` is closed.** The `sport_dma_base()` SPORT4-7 DMA-base
fix and `l1_to_sys()` finally have their hardware test and both pass:
every lane arms, including the four on the second DMA MMR bank, and the
core survives every descriptor fetch. `l1_to_sys()`'s +0x28000000 is
confirmed against the datasheet (Rev. A Table 4: L1 block 0 private
0x00240000–0x0026FFFF ↔ completer-port 0x28240000–0x2826FFFF, and the
same offset for blocks 1-3).

#### 6. WHAT IS STILL OPEN — and it is a different subsystem

The **SPI parameter link answers all-zero**. `dsp4_diag.py` now runs
(it was crashing before — `dsp4_config.py` requested the RDY line even
when none was given, passing `None` to gpiod; fixed), but a read of
`DIAG_MAGIC` comes back `0x00000000` with the response out of step. So:
the core reaches the handshake, and nothing past it is proven — no
register in `diagnostics.md` has been read off a running part. That is
the next item, and it is the SPI2 slave protocol (watermark, RDY
polarity/timing, response framing), not `dma_cfg_init`.

Because of that the DSP4_BISECT scaffolding **stays** for now, and
build.sh's default is still 1 — but the comment beside it has been
corrected: a plain rebuild now produces an image that parks after
`arm_region(A)` on purpose, because a build that runs on into the
unproven SPI link cannot be read on this bench. `DSP4_BISECT=0` gives a
production image, `21` proves the init sequence.

#### Instruments added (they earn their keep, keep them)

- `src/blink/clkprobe.asm` — CCLK and any MMR, read out over PB_05,
  timed off the core timer. This is how a clock gets measured on a part
  with no emulator; do not infer one from a blink rate again.
- `src/blink/sruprobe.asm` — the DAI0 SRU sequence standalone, one
  pulse per write.
- `tools/pi/dsp4_clkprobe.py` — decoder for both, with `--rle` and a
  pulse-burst counter.
- `DSP4_BISECT` rungs 11 (mirror, no park), 13-15 (inside the first
  lane), 16 (a mark per lane, does not stop), 17 (the interrupt
  control), 18-20 (the tail of `dma_cfg_init`), 21 (the handshake).

**Bench state at hand-off:** `matrix-app` restarted and active, all
three MCUs verified 22:39-22:40 (H1S1, H1S3, H1S4 — "MCU verified" and
"MCU boot verified"), GPIO 8/9/10/11/12 back to `a0`. Both SHARCs hold
the rung-21 image and are parked at the handshake, blinking 3 long
pulses on their RDY line.

## HUB DISPATCH 2026-08-21 14:37Z — P2.2 cont'd — characterise the >8KB boot-stream limit so the full 208KB image runs, then dma_cfg_init   [status: 🟢 done — **BOTH SHARCs now load and execute their full firmware, deterministically.** The ">8 KB block-size limit" never existed and is retired. Two real faults, both fixed: (1) elfloader's ZERO-FILL blocks desynchronise the boot kernel — fixed with `-NoFillBlock` plus a build-time guard; (2) U7/H1S1 was a second master on the boot bus — the two offending call sites were removed from its firmware and it was reflashed through MH1, after which the bus measures ZERO events in 15 s and chip 1's 258 KB image boots 6/6 unsynced at 10 MHz and 2/2 at 1 MHz on a 3.45 s stream. The stream-length budget is gone. **P2.2 itself is NOT closed**: with the image finally running, the firmware hangs in `_sru_init`'s DAI0 half — the very first SRU register writes — so `dma_cfg_init` and the `sport_dma_base()` fix are still untested. That is a new, separate item]   [model: opus]

model: opus

rev C is FREE again (the app/panel work is deferred — blocked on the matrix
drift, not the unit). Resume P2.2 from where the 09:xx session left it
(commit 0ce2b7e, "P2.2 reframed"). Read that commit + the 13:09Z block first.

STATE: the SPICMD fix boots ~1 KB images (blink/rdyprobe/bulkprobe) but the
full 208 KB firmware has NEVER executed an instruction — a park on the first
instruction of _start stayed silent. You bisected a boot-stream BLOCK-SIZE
limit: 180 B boots 10/10, 8364 B fails 0/10, and -MaxBlockSize 0x1000 (now in
build.sh LDRFLAGS) boots the 8 KB ladder 4/4. But a SECOND limit above ~8 KB
is still uncharacterised — the 208 KB image still does not run. dma_cfg_init
is downstream and untestable until the full image boots.

TASK — get the full firmware to execute, then close P2.2.
1. Characterise the second limit. Extend the bulkprobe size ladder (build.sh
   bulkprobe) above 8 KB — 16/32/64/128/208 KB — with -MaxBlockSize 0x1000
   already set; find where it stops booting. Use dsp4_stagewatch.py (no bench
   eyes). Hypotheses to test: total stream size vs a per-section/DMA-count
   limit; a boot-kernel scratch/heap ceiling; a second block-count or address
   window; whether multiple blocks vs one big section behaves differently.
   HRM ch.36/40 for any documented SPI-target-boot size/scratch limits.
2. Once the full image boots (park on _start's first instruction fires), move
   the park forward: does dma_cfg_init now run? Then the sport_dma_base() /
   l1_to_sys() fixes finally get a real hardware test. Use DSP4_BISECT to
   walk arm_region(A)/(B) → full run.
3. When the 208 KB production image runs on both chips: revert temp
   instrumentation, rebuild clean production .ldr (fix ldr/manifest.txt which
   currently records the two artifacts as NOT bootable), reflash, verify LD3/
   LD2 + a sane SPI readback. Update P2.2 → 🟢 with the size-limit root cause.
4. If the full image cannot be made to boot as one stream: characterise the
   hard limit and propose the workaround (multi-DXE boot, second-stage loader,
   or a smaller image), with evidence — do not leave it guessing.
Constraints: rev C is yours (app work deferred); ALWAYS restart matrix-app +
verify 3 MCUs before ending; ~/db Dropbox; single trunk; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 17:2xZ — the boot-stream limit is characterised; it was never a size limit

**Headline: chip 2's full firmware executes.** A `DSP4_BISECT=5` build —
the park on the FIRST INSTRUCTION of `_start` — fired 5/6 at the bench.
Every previous session's premise ("the full image never runs") is now
resolved for chip 2, and the reason it never ran is understood.

**What the previous session's finding actually was.** `-MaxBlockSize
0x1000` does nothing. A/B of the identical DXE, capped vs uncapped, 8
boots each at 4 MHz: **7/8 vs 6/8**. The earlier "0/10 then 4/4" was a
~50% coin flip read as a signal. The flag is REMOVED from build.sh and
the claim retracted in `ldr/manifest.txt`.

**FAULT 1 — zero-fill blocks (this is what kept the firmware from ever
running).** elfloader compresses zero runs into ZERO-FILL blocks: a
header with a byte count and no payload. The SPI target boot kernel does
not survive one. A fill block followed by ANY further block loses the
kernel its place in the stream; a fill that happens to be last is
harmless, which is why nothing ever noticed.

| test (chip 2, gap-synced 11 MHz) | result |
|---|---|
| image that boots, one 640 B fill inserted at the FRONT | 3/3 → **0/3** |
| identical block APPENDED instead | 3/3 → **3/3** |
| chip2 firmware as elfloader emits it (324 blocks, 152 fills) | **0/6** |
| same firmware, `-NoFillBlock` (6 blocks, no fills) | **5/6** |

Found by grafting the firmware's first N blocks in front of a tiny probe
that toggles PB_05, so a boot proves the kernel consumed them: N=0 boots
3/3, N=1 (a single leading fill) **0/3**.

FIX IN TREE: `-NoFillBlock` in `build.sh` LDRFLAGS, and
`tools/dsp/ldr_stream.py check` runs on every image the build produces,
so the shape cannot come back silently. Because the zeros now travel for
real, `sec_delay`/`sec_delay_ovf` are marked `NO_INIT` in the LDF —
without that chip 2 would be a 1.9 MB stream. **Those delay buffers must
now be cleared by firmware at startup; that is a new NOW item below.**

**FAULT 2 — the boot bus's second master sets a TIME budget.** U7/H1S1's
legacy ADAU meter poll bursts ~0.5 ms on the shared SCK/MOSI every
~185–254 ms (63 bursts in 11.67 s, measured). Boot success tracks stream
ELAPSED TIME, not size and not block size — the cleanest proof is one
unchanged 3 KB image at three clocks: **5/6 at 1 MHz (25 ms), 5/6 at
4 MHz, 0/6 at 100 kHz (246 ms)**. Faster is safer; 10 and 11 MHz boot
cleanly, **12 MHz and above fail outright**. `dsp4_boot.py --sync-poll`
(new) starts the stream just after a burst. Budget with it: ~220 ms
≈ 240 KB at 11 MHz — a 107 KB probe boots 6/6, 176 KB 5/6, 197 KB 0/6.

**Chip 1 — FIXED the same day; see the addendum below.** 258 KB, ~320 ms
on the wire. It did not fit between two bursts at any clock, so no
host-side trick reached it. **CORRECTED 2026-08-21: it is not an "ADAU
meter poll" and it is NOT absent from the current sources** — `main.c`
line 24 `#include "matrix.cs"`, so that file is compiled. The two
interferers are `TimeSplice()`'s periodic `TestMicPres()` (25 bytes on
the mic-preamp CS, fired off a MainLoop ITERATION COUNTER, which is why
the period wanders 40–254 ms) and `MainLoop()`'s `DspTx(0xF520)` writes
to **CS1–CS8** on every blink transition — the latter asserting the very
chip selects the Pi boots through, for a legacy register the SHARC
firmware does not implement. Both are removable in a few lines;
`TestMicPres()` is also called once at init, so mic gain survives.
**NOT DONE, it needs PW's go-ahead** (and the 13:09Z
dispatch fenced the ADAU-poll item off).

**item 2 — the wedge is in `_sru_init`, NOT `dma_cfg_init`.** Redone on
clean `-NoFillBlock` chip-2 builds (the first pass used a fill-STRIPPED
diagnostic image with uninitialised BSS and reported `_diag_init`; that
reading is WITHDRAWN). Park rungs added to `main.asm` at each step of
`_start`'s init sequence, 6 boots each, read over ssh on PB_05:

| rung | park point | result |
|---|---|---|
| 6 | after the C stack prologue | **6/6 fires** |
| 7 | after `_diag_init` returns | **5/6 fires** |
| 8 | after `_sru_init` returns | **0/6 silent** |
| 9 | after `_sport_cfg_init` returns | 0/6 silent |
| 4 | entry to `dma_cfg_init` | 0/6 silent |

`_sru_init` never returns. Split further with rung 10 (an early `return`
in `sru_config.c` at the DAI0/DAI1 boundary): also **0/6**, so the hang
is in the **DAI0 half — the very first SRU register writes**, not the
DAI1/SPORT4-7 ones.

`sru_init()` is straight-line `SRU()` macro register writes with no loop
in it, so "never returns" is a FAULT, not a spin — the core vectors
somewhere and stays there. The obvious suspect is the DAI/SRU register
space not being reachable yet (clock/power gating, or a CGU that is not
where the code assumes). Note the independent evidence: **CCLK on this
card measures ~190 MHz, not the 400 MHz every delay constant assumes**
(diag.h), and the standalone blink images run ~2x slow — PW confirmed
both LEDs blinking at the slow rate 2026-08-21. Next session: read the
fault status registers at the park, and confirm DAI0 is clocked before
`sru_init` touches it. **`dma_cfg_init` and the `sport_dma_base()` fix
remain untested on hardware — they are three calls downstream of a
function that never returns.**

**Also worth knowing (cost me an hour).** Claiming GPIO9/10/11 with
gpiod/`gpiomon` takes them out of `a0` and **spidev does not put them
back** — every boot then fails and looks exactly like a dead part.
`pinctrl set 9,10,11 a0` restores it; `--sync-poll` does it automatically.
Separately, stopping `matrix-app` makes DSP boot fail outright (0/6 where
it was 5/6) — not chased, but do not debug boot with the app stopped.

**Bench state at hand-off:** `matrix-app` restarted and active, all three
MCUs verified 17:16–17:17 (H1S1, H1S3, H1S4 — "MCU verified" and "MCU
boot verified"), GPIO9/10/11 back to `a0`, spidev bufsiz back to its
4096 default. Chip 2 holds a production `chip2.ldr` from the last boot
attempt; chip 1 holds nothing running.

**NEXT, in order.** (1) H1S1 reflash — DONE, see the addendum.
(2) Zero `sec_delay`/`sec_delay_ovf` in firmware startup (new NOW item).
(3) Chase the `_sru_init` fault: read the fault status registers at the
park, and check DAI0 is clocked/ungated before `sru_init` writes to it —
CCLK measuring ~190 MHz against code assuming 400 MHz says the clock tree
is not where this firmware thinks it is.
(4) Production verification of chip 2 needs eyes on LD2, or a working
`dsp4_diag.py` — it crashes on start (`TypeError` in the gpiod line
request), unrelated to any of this.

### Addendum 2026-08-21 20:2xZ — H1S1 reflashed; the boot bus has one master again

PW authorised the change. Both interfering call sites removed from
`~/build-h1s1/Core/Inc/matrix.cs`:

* `TestMicPres()` dropped from `TimeSplice()`'s periodic path. It pushed
  25 bytes at CS_M every ~1e6 MainLoop iterations. It is STILL called
  once at init, so mic gain is still applied — only the pointless
  re-application every million loops is gone.
* the CS1–CS8 `DspTx(0xF520)` block deleted from `MainLoop()`. Those
  asserted the SHARCs' own boot chip selects, for a legacy ADAU-era
  register the SHARC firmware does not implement.

Built with `Debug/fw.sh` (text 34036 -> 33476 B). **Verified in the
disassembly, not from the source edit:** zero callers of `DspTx`,
exactly one caller of `TestMicPres` (the init one), and `TimeSplice`
contains no `bl` instruction at all. Packed with `hex2shex.py`
(2171 -> 2136 records, 34693 -> 34133 B) and flashed through MH1 with
`app cli loadfw H1S1` — the same path H1S3/H1S4 use, per PW. Previous
pack image kept at
`/home/app/fwbuild/pack-backup-H1S1-2026-08-21-preSPIfix.shex`.
All three MCUs verify after the reflash (20:24).

**Result, measured both ways:**

| | before | after |
|---|---|---|
| SCK/MOSI/MISO activity, gpiomon | 8530 events, 63 bursts / 11.67 s | **0 events / 15 s** |
| chip 1 full firmware, 258 KB @ 10 MHz, unsynced | 0/6 | **6/6** (350 ms) |
| chip 1 @ 1 MHz — a 3.45 SECOND stream | hopeless | **2/2** |
| chip 2 full firmware @ 10 MHz | needed --sync-poll | **3/3** |

There is no longer a stream-length budget on this unit, at any clock.
`--sync-poll` and the 11 MHz ceiling stay in `dsp4_boot.py` because the
two-master WIRING is still a rev-D item — any board whose H1S1 has not
been reflashed has the limit straight back.

**Canonical source updated too.** `~/build-h1s1` is not a git repo, so
the edit would have lived on one workstation only and the next rebuild
from the canonical tree would have silently reintroduced the fault. The
Dropbox copy at `_mx/MW/D24/FW/H1S1/Core/Inc/matrix.cs` was verified
byte-identical to the pre-edit original first, then updated, with the
original kept beside it as `matrix.cs.pre-spi-fix-2026-08-21`. Source and
flashed image now agree.

**Incidental observation, not touched:** `/home/app/firmware/H1S3.shex`
carries the MCU-ID `H1S4` in its type-04 record (and fwbuild holds
`left-slot3-H1S4content.shex` / `right-slot4-H1S3content.shex`), so the
slot/content mapping looks deliberately crossed. All three MCUs verify,
so this is either intended or long-standing. Flagged for PW, not changed.

## HUB DISPATCH 2026-08-21 13:09Z — P2.2 — close the dma_cfg_init wedge with working boot + LD blink instrument   [status: 🔴 blocked — the wedge is NOT in dma_cfg_init: the full firmware has never executed a single instruction on this card. Root cause found and half-fixed — the SPI target boot kernel cannot take a loader block larger than ~8 KB, so every production image built without `-MaxBlockSize` is a stream the host clocks out in full and the part never runs. `-MaxBlockSize 0x1000` added to build.sh's LDRFLAGS and proved on the bench (0/10 → 4/4 on the same DXE at 8 KB), but the 208 KB firmware still does not run, so a SECOND limit above ~8 KB remains uncharacterised. Bench released to PW mid-bisect for an app/panel reflash]   [model: opus]

model: opus

SHARC boot is SOLVED (SPICMD, D14) and BOTH DSP blink LEDs are confirmed
running at the bench — you now have a working boot AND LD2/LD3 as live
instruments, which is exactly what the P2.2 bisect was blocked on. Resume
P2.2 per NOW item 1.

TASK — close the dma_cfg_init wedge.
1. The SPORT4-7 DMA-base fix (`sport_dma_base()` in dma_config.c) is in the
   tree, verified against sys/ADSP-21564.h, never confirmed on hardware
   because nothing booted before. Now it can be. Build `DSP4_BISECT=1`
   (parks after arm_region(A)); boot chip 1 with the SPICMD fix
   (dsp4_boot.py default 0x03); read LD3 (DSPA, chip 1): a steady ~1 Hz
   square = arm_region(A) survived. If it parks (slow single blink), the
   SPORT4 base was still not it — capture and reassess.
2. If A is clean: `DSP4_BISECT=2` (park after B), boot, LD3 again. Then
   `DSP4_BISECT=0` (production, no park/stamps) for a full run on BOTH
   chips; confirm LD3 (1 Hz) and LD2 (2 Hz) steady, and the SPI2 diag
   readback is non-zero / sane now that the core runs past dma_cfg_init.
3. When closed: REVERT the temp instrumentation (diag_stage_set / diag.asm
   stamps / the park loop behind DSP4_BISECT per item 3), rebuild the
   clean production images, reflash both chips, verify LEDs + readback,
   commit the production .ldr hash-named. Update P2.2 to 🟢 with the
   verdict; note the SPICMD dependency (production boot path must carry
   --spi-cmd 0x03).
4. If the wedge does NOT close on the SPORT4 fix: bisect further with the
   LED (now a real instrument) rather than the all-zero SPI readback, and
   write up where it dies.
Do NOT touch the CLKIN mods (blue, done) or the H1S1 ADAU-poll item (that
is a separate near-term firmware task needing the real H1S1 sources).
Constraints: matrix-app restarted + 3 MCUs verified before ending; ~/db
Dropbox; single trunk; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 15:0xZ — 🔴 stopped mid-bisect (bench released to PW); P2.2's premise is refuted

**The dma_cfg_init wedge does not exist as described.** Every park placed
inside `dma_cfg_init` stayed silent, and so did a park on the FIRST
INSTRUCTION of `_start`. The full firmware has never run on this card —
not once, at any point in this investigation. Only the ~1 KB standalone
`blink` / `rdyprobe` images ever have, which is why "the DSPs boot" read
as settled after the SPICMD fix (D14): that conclusion was drawn entirely
from 1 KB images and does not generalise.

**ROOT CAUSE (partial): the boot kernel cannot take a large loader
block.** Bisected with a new instrument, `src/blink/bulkprobe.asm` —
rdyprobe plus a slab of never-executed code, so boot-stream size is the
only variable — chip 1, ten boots per rung, verdict read over ssh:

| image | stream | biggest block | boots |
|---|---|---|---|
| bulkprobe0 | 180 B | 68 B | **10/10** |
| bulkprobe2 | 8 364 B | 8 252 B | **0/10** |
| bulkprobe2, same DXE, `-MaxBlockSize 0x400` | 8 492 B | 1 KB | **4/4** |
| bulkprobe2, same DXE, `-MaxBlockSize 0x1000` | 8 396 B | 4 KB | **4/4** |

Nothing else moves the result. Not the SPI clock (100 kHz behaves exactly
as 1 MHz — so it is not a timing race). Not the host transfer size
(`--chunk 1024 / 2048 / 4096` all identical — so it is not a spidev or
CS-window artefact; `--chunk` was added to `dsp4_boot.py` for this). Not
the zero-fill blocks (deleting the 506 KB L2 fill via a temporary
`NO_INIT` on `sec_delay` changed nothing). It is the byte count in a
single block header.

`-MaxBlockSize 0x1000` is now in `build.sh`'s `LDRFLAGS`, with the
evidence written into the comment beside it.

**It is necessary and NOT sufficient.** The full 208 KB chip-1 image
built with the cap still does not execute (`DSP4_BISECT=5` park silent).
So there is a SECOND limit somewhere above ~8 KB — total image size,
block count, or the fill blocks. **That is exactly where this stopped.**

**NEXT STEP, and it is one command's worth of work:** the bulkprobe
ladder rebuilt with the cap in place, run up the sizes —

```
cd MW/D32/DSP/SHARC && BULK_LEVELS="2 3 4" ./build.sh bulkprobe
# bulkprobe2 8 KB (known good with the cap), 3 = 33 KB, 4 = 66 KB
scp build/bulkprobe{2,3,4}.ldr app@192.168.1.219:/home/app/dspboot/
# per image: dsp4_boot.py --ldr bulkprobeN.ldr --chip 1
#            dsp4_stagewatch.py --chip 1 --seconds 6
```

If 3 and 4 boot, the second limit is not raw size and the next variable
is the fill blocks (`-MaxFillBlockSize`) or the block count. If they do
not, bisect between 8 KB and 33 KB the same way. Either way the answer is
a loader flag, not firmware.

**What this retires.** The SPORT4-7 `sport_dma_base()` fix is still
correct against `sys/ADSP-21564.h` and stays, but it is UNTESTED on
hardware and was never the thing that hung: nothing in `dma_config.c` has
ever been reached. The "1-flash hang inside `arm_region`" reading from
2026-08-19 was an LED code from an image that had not loaded, not a hang.
`ldr/manifest.txt` now carries a WITHDRAWN note: the two production
`.ldr`s on record are not bootable images.

**New instruments, all committed and deployed to `/home/app/dspboot`
(md5-checked both ends):**

| tool | what it does |
|---|---|
| `tools/pi/dsp4_stagewatch.py` | samples GPIO8/GPIO12 at 1 kHz and decodes the DSP status-LED pattern into a verdict — steady square = running, N flashes = stuck after stage N, flat = not running. Removes the need for eyes on LD3/LD2 for every bisect round. |
| `src/blink/bulkprobe.asm` + `./build.sh bulkprobe` | the boot-size ladder above. `BULK_LEVELS="..."` selects rungs. |
| `dsp4_boot.py --chunk N` | host transfer size, to separate a kernel limit from a transfer-boundary artefact. |
| `DSP4_BISECT=4` / `=5` | park on entry to `dma_cfg_init` / on the first instruction of `_start`. Parks now pulse PB_05 (Pi GPIO8/12) with interrupts OFF instead of relying on the timer-ISR LED, so a park answers "was this point reached?" without also asking about the interrupt path. |

All of the above is still TEMPORARY scaffolding and still goes with NOW
item 3 — except `-MaxBlockSize`, `dsp4_stagewatch.py`, `bulkprobe.asm`
and `--chunk`, which stay.

**Bench state at hand-off (PW took rev C for an app/panel reflash):**
`matrix-app` restarted and active, all three MCUs verified at 14:58
(H1S1, H1S3, H1S4 — "MCU verified" and "MCU boot verified" both), GPIO
9/10/11 back to `a0`, GPIO8/12 inputs, GPIO16 output high. Chip 1 holds a
non-running `DSP4_BISECT=5` image and chip 2 was last reset without one;
neither runs code, which is the same state as before this session and
harmless. Nothing further was booted or flashed after the hand-off
request.


## HUB DISPATCH 2026-08-21 11:26Z — SHARC ③ — scope-driver + boot-bus toggle capture (rails good; CPLD cannot mirror SPI/RST)   [status: 🟢 done — **ROOT CAUSE FOUND AND FIXED. Both SHARCs boot and run application code.** The boot host never sent the SPICMD byte the SPI-target boot kernel reads as its FIRST byte (HRM Table 36-18: 0x03 = keep single-bit mode), so the ROM consumed the first byte of the .ldr as the command and every block header after it was shifted by one. Added `--spi-cmd` (default 0x03) to dsp4_boot.py: GPIO8 now toggles at ~1 Hz on chip 1 and GPIO12 at ~2 Hz on chip 2, and an A/B/A control with `--spi-cmd none` reproduces the old flat-low failure exactly. The parts were never damaged]   [model: opus]
model: opus

Rails are GOOD at the bench (PW): +0.9V, +1V8 VDD_REF, +3V3 all in spec —
suspect (1) power CLEARED. The liveness checklist now needs a live scope of
SPI2 CLK/MOSI and SYS_HWRST during a boot. Hub netlist check: neither the
Pi-mastered boot SPI to the DSPs nor RST_D routes to the CPLD, so a CPLD
patch cannot bring them out — do NOT build one for that. All three signals
are reachable natively:
  test 1 CLKIN  = R65.2/R33.2 pad (PW verified good).
  test 2 boot SPI = Pi header J6 pin 23 (SCK/GPIO11), pin 19 (MOSI/GPIO10),
    0.1"; DSP-side confirm R52.2/R51.2 (DSPA), R19.2/R18.2 (DSPB) 0402 pads.
  test 3 SYS_HWRST = J6 pin 36 (RST_D/GPIO16), 0.1"; expect a clean low pulse
    >= 11 x tCKIN (~450 ns at 24.576 MHz) at each boot.

**PW BENCH RESULT + NEW LEAD 2026-08-21 (highest priority now):** with the
square-wave driver running, PW scoped the Pi header: J6.23 (SCK) TOGGLING,
J6.19 (MOSI) TOGGLING, **J6.36 (RST_D/SYS_HWRST) STUCK HIGH — not toggling.**
The Pi drives the boot bus fine, but it CANNOT toggle RST_D. This matches the
netprobe ("!RST_D held high, U7 p47 also drives it") and the dual-master
errata: the S MCU H1S1 (U7 PA13, pin 47) drives RST_D push-pull and wins over
the Pi's GPIO16. CONSEQUENCE: the Pi has never been able to pulse SYS_HWRST low,
so the two SHARCs came out of reset once at power-on (ran the boot ROM with
nothing to receive) and every dsp4_boot since sent a stream to a part not in
its boot-listen window — exactly "boot reports OK, GPIO8 flat".

DO THIS:
1. CONFIRM contention (not a script miss): with the Pi driving GPIO16 LOW
   push-pull, read GPIO16 back — if it reads HIGH while driven low, U7 is
   overpowering it = confirmed. (If it reads low, the earlier script just
   didn't drive it — fix and re-scope.)
2. RELEASE RST_D to the Pi so a real reset is possible. Options, cheapest
   first: (a) does current H1S1 firmware drive PA13, or is this the rev-A
   image that should leave it as input? Check the H1S1 source (Core/... 
   the errata "H1S1 fw leaves PA13 as input" rule). (b) Hold H1S1 in reset
   (its NRST) during a DSP boot so PA13 goes hi-Z and the Pi owns RST_D —
   find how NRST is reachable (power-MCU? a GPIO? the SWD/prog path?).
   (c) If neither is quick, PW bench: physically lift U7 PA13 or the RST_D
   link — record as a red mod.
3. With RST_D released, run dsp4_boot (which pulses RST_D low then streams)
   and check GPIO8. THIS is the real boot test — the clock is good, the bus
   toggles, and now the part can actually be reset into boot mode.
4. Record the verdict. If GPIO8 finally toggles: the boot-handoff root cause
   = RST_D dual-master (H1S1 held the DSPs out of Pi-controlled reset), not
   damaged parts — a firmware/mod fix, no new card needed. Update the
   dual-master item on the mods PDF accordingly (still a rev-D hardware fix,
   but the immediate unblock is releasing PA13).

**PW REFINEMENT (do this FIRST, priority over the boot loop):** PW wants
INDEPENDENT steady repeating signals on each of the three pins to scope
directly — not boot-shaped bursts. Deploy a small script on the Pi
(app@192.168.1.219, /home/app/dspboot) that drives, as plain GPIO outputs,
a clean square wave PW can catch and level-check at the DSP-side pad:
  - SCK  = GPIO11  (scope at J6 pin 23 or R52/R19 DSP pad)
  - MOSI = GPIO10  (scope at J6 pin 19 or R51/R18 DSP pad)
  - SYS_HWRST = GPIO16 / RST_D (scope at J6 pin 36; note this RESETS both
    DSPs each cycle — fine)
Pick a scope-friendly rate (~1 kHz square, 50% duty) and drive all three
continuously; give PW a one-liner to start and to stop (and to restore the
pins after). CRITICAL: GPIO10/11 are normally spidev's — release/stop any
spidev claim first (the netprobe path already toggles these as GPIO), and
drive them push-pull so the scope shows whether the Pi can actually swing
the net or something clamps it (netprobe saw SCK/MOSI 'held high by
something stronger than the Pi pull' — this square wave at the DSP pad is
the direct test of that: if the Pi drives 0/1 at J6 but the DSP-side pad
stays stuck, there is a break/contention between them). Log the Pi-side
readback while driving. THEN the boot loop below for the realistic view.

TASK A — scope-driver so PW can probe live. Provide a repeating desk-driven
boot on demand: a small loop that boots rdyprobe1.ldr on chip 1 every ~3 s
(and a chip-2 variant), so the SPI2 CLK/MOSI and RST_D edges recur on the
scope. Deploy to /home/app/dspboot as a named script; give PW the exact
one-liner to start/stop it. While it runs, capture on the Pi side what the
boot bus is doing (dsp4_netprobe during the loop) and log it.

TASK B — the discriminating capture (no bench eyes): during the boot loop,
use the Pi to sample, at the DSP boot bus, whether SCK (GPIO11) and MOSI
(GPIO10) actually TOGGLE during the CS-asserted window, vs the netprobe's
earlier "held high" static read. If they are static during boot, the Pi is
not clocking the DSP (host/driver/contention problem) — a different class
than a dead DSP. If they toggle but RDY never deasserts and GPIO8 stays
flat, the DSP is receiving clock+data+reset and still not running = the
parts themselves. State which of these the evidence supports.

TASK C — bookkeeping. Write the scope-point map (the table above, with the
J6 header pin numbers and the resistor pads) into the liveness checklist
doc so PW has it at the bench, and record the CPLD-cannot-mirror-2/3
finding. If TASK B points at the parts, say so plainly and the fresh-card
build is next; if it points at the Pi-side boot drive, propose the fix.
Do NOT build a CPLD patch. Constraints: restart matrix-app + verify 3 MCUs
before ending; ~/db Dropbox; single trunk; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 13:05Z — 🔴 BLOCKED on one DMM measurement at the bench

**TASK A — done, deployed, exercised.** Three new tools in `tools/pi/`,
copied to `/home/app/dspboot` (md5-checked both ends):

| tool | what it does |
|---|---|
| `dsp4_scopedrive.py` + `.sh` | PW's refinement, built first. Drives SCK/MOSI/!RST_D as **plain push-pull GPIO square waves**, one frequency per pin so the scope identifies the pin without moving the probe: SCK 1 kHz, MOSI 500 Hz, !RST_D 250 Hz. Also `hold RST_D=0` for a DC level a meter can read. Releases and **restores spidev's ALT0 pinmux** on stop. |
| `dsp4_bootloop.sh` | repeats a real `dsp4_boot.py` boot every ~3 s (chip 1 or 2) so the boot-shaped edges recur. |
| `dsp4_busmon.py` | **passive** GPLEV0 capture through `/dev/gpiomem` at ~1.3 MSa/s. Claims no line and changes no pull, so it runs *during* a boot — which `dsp4_netprobe.py` structurally cannot do, because its bias-and-read method takes SCK/MOSI away from SPI0 and would break the transfer it is meant to watch. That is why netprobe only ever reported the bus at rest. |

One-liners for the bench (all in the checklist doc):
`cd /home/app/dspboot && ./dsp4_scopedrive.sh start | stop | hold RST_D=0`,
`./dsp4_bootloop.sh start [chip] [period] | stop`. Both stop `matrix-app`
on start and restart it on stop.

**A live-fire hazard found and fixed while building this:** `pinctrl get
9,10,11` read **`ip` (plain inputs)**, not `a0`. Releasing a gpiod line
leaves the pin an input and nothing restores the SPI0 pinmux — not a
`matrix-app` restart. `dsp4_netprobe.py` had left them that way at the end
of the 08-20 session, so any boot run afterwards would have clocked
nothing while still reporting OK. Both new wrappers now set `a0`
explicitly, and `dsp4_scopedrive --restore` puts it back.

**TASK B — the discriminating capture: the Pi IS clocking the DSPs.**
`dsp4_busmon.py` around a real `rdyprobe1.ldr` boot, 3 267 584 samples in
2.5 s:

| net | whole capture | inside the CS1-low window |
|---|---|---|
| SCK (GPIO11) | ACTIVE, 16 170 transitions | **16 170 — all of them** |
| MOSI (GPIO10) | ACTIVE, 1066 transitions | 498 |
| !RST_D (GPIO16) | low for **51.7 ms** (the tool's 50 ms pulse) | — |
| MISO, RDY1, RDY2 | STATIC low throughout | STATIC low |

1024 bytes × 8 = 8192 SPI clocks = 16 384 edges; 16 170 observed, the
deficit being a 0.77 µs sampler aliasing a 1 MHz clock, not lost cycles.
PW's scope agrees at the header (J6.23 and J6.19 both toggling). **So the
netprobe's "MOSI/SCK held high" was a statement about an idle bus, not a
dead one, and TASK B's host-side-drive branch is closed.**

**The hub's PA13 mechanism is refuted — but the conclusion survives.**

- H1S1 firmware (`~/build-h1s1`): **PA13 is not configured at all.** It is
  absent from the `.ioc` pin list, `RST_D_Pin`/`RST_D_GPIO_Port` are not
  defined in `main.h`, and the only two references in `main.c` are
  commented out. PA13 sits in the STM32U5 reset default — SWDIO alternate
  function, ~40 kΩ internal pull-up. That is what beats the Pi's ~50 kΩ
  internal pull-down in netprobe; it cannot fight a push-pull output.
- Pi GPIO16 at the CM4 pad, 2000 samples per state: input+pull-down →
  **high** (the PA13 pull-up), input+pull-up → high, **driven low
  push-pull → low, 2000/2000**, driven high → high, square wave → follows
  0/1. The Pi owns the net at its own end.
- So there is nothing to release: holding H1S1 in reset or lifting PA13
  would change nothing, and dispatch options 2(a)/(b)/(c) are all moot.

**Net topology, settled from the schematic (ROOT sheet p1/10).** The DSPA
and DSPB hierarchy blocks each take `!RST_D` into a port named `RST`, and
on the DSPA sheet (p5) that sheet-local `RST` lands on **U6 p104,
SYS_HWRST** — same for DSPB/U5. One net: **CM4 GPIO16 · U7 PA13 · J6.36 ·
DIL100 P13 · U5 p104 · U6 p104**, no series resistor. Recorded in
`hardware-map.md` §3. (A wrong turn on the way, corrected by PW at the
desk: the DSP sheets are sub-sheets and their labels are sheet-local, so
the `RST` on the M MCU sheet is U8's own NRST — a different net. It was
briefly tested as a way to reset the DSPs: an AIRCR SYSRESETREQ on U8 does
pull its NRST low, proven by RCC_CSR going 0x00000000 → **0x14000000**
(SFTRSTF **and PINRSTF**) across a pure software reset, but that net does
not reach the parts, and booting after it left GPIO8 flat as expected.)

**Which leaves one physical reading of PW's bench result.** The Pi's end
of `!RST_D` is at 0 V while J6.36 on the card is at 3.3 V, on one net. That
is an **open between the CM4 and the DSP4 card** — a DIL100 P13 contact, a
broken track/via, or an unstuffed link — with PA13's pull-up holding the
isolated card-side segment high. If so, neither SHARC has ever been reset
by the host: both came out of reset once at power-on, ran the boot ROM with
nothing sending, and have never re-entered the boot window since. That is
"boot reports OK, GPIO8 flat", every time, since March.

**TASK C — bookkeeping done.**

- `~/db/TransferOnly/PCB mods/dsp4-revC-liveness-checklist.md`: new §1a
  probe-point map (J6 pin numbers + the DSP-side 0402 pads + the bench
  one-liners), the CPLD-cannot-mirror-2/3 finding recorded, step 1 marked
  PASS (rails), step 2 marked pass-at-the-header, and **step 3 rewritten as
  the open item** with all the evidence above and a four-step procedure.
- `MW/D24/HW/hardware-map.md` §3: the `!RST_D` net traced end to end, the
  sub-sheet naming trap, and the PA13-unconfigured finding.

**Blocked on — one measurement, no scope needed:**

```
ssh app@192.168.1.219 'cd /home/app/dspboot && ./dsp4_scopedrive.sh hold RST_D=0'
```

then meter **J6 pin 36** (and p104 on U5/U6 if reachable);
`./dsp4_scopedrive.sh stop` after.

- Both ~0 V → the net is sound, the earlier scope reading was a pin out,
  and the investigation goes to the parts (checklist step 4: fresh card /
  fresh SHARCs).
- J6.36 at 3.3 V → **open confirmed**; find the segment with a continuity
  check power-off, bodge it, re-run `./dsp4_bootloop.sh start` and watch
  GPIO8. Red mod on rev C, item on rev D.
- If the break is unreachable, the card-side fallback is real: U7 PA13 is
  on that net, doing nothing. Configure it as a push-pull output with a
  "pulse !RST_D" command in H1S1 and the supervisor can reset the DSPs —
  which the schematic annotation always claimed it could.

Unit left with `matrix-app` running, all three MCUs verified (H1S1, H1S3,
H1S4 at 12:46), GPIO5/13 back to inputs, GPIO9/10/11 back to `a0`, GPIO16
output high.


### Addendum 2026-08-21 14:00Z — 🟢 ROOT CAUSE: the missing SPICMD byte

**Both SHARCs boot and run application code. The parts are fine.**

PW put a scope on **DSP pin 10, SYS_CLKOUT**, and read **24.5 MHz at 3.3 V**
— the first positive liveness signal this card has ever produced, and the
thing that turned the investigation around. HRM §"CLKOUT Selections":
*"BMODE = (non zero) — When a hardware reset is deasserted, SYS_CLKIN is
selected by default"*, routed DIRECT per Figure 2-2. Our BMODE is 0b010, so
pin 10 is a straight mux from pin 5. That single reading proves VDD_EXT is
present at the die, the output driver works, SYS_CLKIN0 is reaching and
being received correctly *through the part* (better evidence than the pad
scope), and a hardware reset has been deasserted. It also proves BMODE is
non-zero, i.e. not the 000 No-Boot strap.

Then, with `!RST_D` held low from the desk, **PW read pin 10 LOW** — CLKOUT
stops. So the reset reaches the die too, closing the last unverified hop.
Every precondition was verified good on a part that was demonstrably alive,
which meant the fault had to be in the boot handshake itself.

**It was.** HRM ch.36, *SPI Target Boot Mode*:

> "The SPI target processor detects the correct boot mode from the host SPI
> device by reading **the first byte sent, defined as SPICMD**. … These
> additional bytes **must be sent prior to transmitting the data** to
> configure the SPI device."

Table 36-18, host starting in single-bit mode: **0x3 = keep single-bit
mode** (0x7 dual, 0xB quad). `dsp4_boot.py` sent the `.ldr` straight in with
no command byte, so the boot kernel ate the first byte of the first block
header as SPICMD and every header after it was misaligned by one byte:
HDRSIGN never 0xAD, no block ever passed its XOR check, the boot never
completed — while the host still saw a stream clocked out from end to end.
That is precisely the signature this card has had since March.

`--spi-cmd` added to `dsp4_boot.py`, default `0x03`, sent with SS asserted
and before the first stream byte per the host flow in HRM Figure 36-6.

**Result, and the A/B/A control that makes it causation:**

| run | GPIO8 / GPIO12 |
|---|---|
| chip 1, rdyprobe1, SPICMD `0x03` | `hi hi hi hi lo lo lo lo hi hi …` — **~1 Hz** |
| chip 2, rdyprobe2, SPICMD `0x03` | `hi hi lo lo hi hi lo lo …` — **~2 Hz** |
| chip 1, `--spi-cmd none` | `lo lo lo lo …` — the old failure, exactly |
| chip 1, SPICMD back on | toggling again |
| chip 1 rdyprobe + chip 2 blink2, **matrix-app running** | GPIO8 toggling; LD2 should blink |

**What this retires.** The "damaged parts / fresh card / fresh SHARCs"
verdict recorded earlier today is **withdrawn** — do not order parts on it.
Both SHARCs survived the SYS_CLKIN0 overdrive. Everything the earlier
rounds fixed was real and necessary (the ÷2 CPLD clock, the level-shift
bodge, the active-low RDY correction, the H1S1 CS1-6 reflash, the SPI0
pinmux restore), but none of it was sufficient, because the host had never
spoken the first byte of the protocol.

**What stands.** The two-master contention on the boot bus (H1S1's legacy
ADAU meter poll, ~600 µs every ~260 ms) is still real and still worth
removing — it is now the most likely cause of any *intermittent* boot
failure, at ~5.6 % per attempt. The RDY pull-downs (R34/R22) are still
backwards versus HRM Figure 36-4, which wants a 10 K pull-**up** to
VDD_EXT; back pressure works anyway because the part drives the pin, but
the in-reset hold-off does not, and the fixed 500 ms settle is standing in
for a handshake we cannot see. Both are rev-D items.

Unit left with matrix-app running, all three MCUs verified (13:57), chip 1
running rdyprobe1 and chip 2 running blink2.


### Addendum 2026-08-21 13:20Z — 🟢 the open item closed at the bench, verdict: the parts

**!RST_D is good.** PW watched the pin go LOW the moment
`./dsp4_scopedrive.sh hold RST_D=0` was started. The earlier "J6.36 stuck
high" was measured with GPIO16 at its idle level — the tool parks !RST_D as
an output HIGH whenever it is not deliberately driving, and so does every
`stop`, so a high reading in that state is correct and discriminates
nothing. There is no open and no contention. (The confirmed low was at the
header end; the last hop to p104 is netlist inference, no series R on the
net.)

**The closed loop, re-run on both parts with every precondition verified**
(`dsp4_busmon.py` capturing passively through the whole boot, GPIO9/10/11
confirmed at `a0` first):

| | chip 1 | chip 2 |
|---|---|---|
| `!RST_D` low pulse | 158.6 → 209.1 ms (50.5 ms) | 158.7 → 209.2 ms (50.5 ms) |
| CS low | 714.5 → 728.5 ms | 712.3 → 726.3 ms |
| SCK inside the CS window | **16 334 transitions, one burst, 50 % duty** | **16 332, 49 %** |
| MOSI inside the CS window | 236 transitions | 232 |
| MISO | static low throughout | static low |
| SPI_RDY (GPIO8 / GPIO12) | static low, and flat for 6 s after | static low |

16 384 edges are expected for 1024 B; the shortfall is a 0.75 µs sampler
aliasing a 1 MHz clock. Reset, settle, one clean burst inside the select
window — and neither part drives MISO or SPI_RDY, ever.

**Verdict.** SYS_CLKIN0 correct and scope-verified at the pin; +0.9 V,
+1V8 VDD_REF and +3V3 all in spec on a meter; !RST_D reaching the net; and
1 kB of correctly-framed data clocked into each part at the right moment.
Every precondition for a boot is verified good and neither SHARC has ever
driven a pin. **Nothing on the host side is left to fix — the next step is
a fresh card / fresh SHARCs** (checklist step 4), with the corrected clock
chain fitted before first power-up. Both parts were overdriven ~80 mA into
a 6 mA-max clamp on SYS_CLKIN0 from March until 2026-08-21, which remains
the only mechanism on the table that fits.

**Checklist step 0 is closed too, PASS:** PW confirms the decoupling caps
ARE fitted to both DSP chips — they are simply absent from the printed
schematic. The blank `CAPS` sub-sheets (PDF pages 9/10) are a documentation
defect, not a hardware one, so it is not a rev-C fault and not a suspect.
Rev-D mod 14 is downgraded from RED to a drawing item (draw the two CAPS
sub-sheets). Reading lesson recorded in the checklist: a blank sub-sheet in
this project does not mean an empty net.

With that, **every suspect on the list is closed except the parts.**

**A second, unarbitrated SPI master on the DSP boot bus — identified and
confirmed 2026-08-21.** PW named it from the history: H1S1 used to drive
these pins to **read ADAU meter levels, periodically**, and the flashed
image still does. The measurement confirms it and shows why it was
invisible.

With the Pi's `SPI_MOSI` idle, `!SPI1` carries a burst of ~80 transitions
every ~256 ms, and `SCK` showed **zero** transitions — which made no sense
for an SPI transfer. It made sense once GPIO9/10/11 were taken out of `a0`
and made plain inputs:

| | Pi SPI0 attached (`a0`) | Pi SPI0 released (inputs) |
|---|---|---|
| SCK transitions in 1.5 s | **0** | **1630, in 7 bursts** |
| SCK idle level | held LOW by the Pi's output | **99.9 % high** |
| burst period | — | **~260 ms** (260.7 / 260.0 / 263.1 / 261.2) |
| burst length | — | ~600 µs, ~240 edges each |
| MOSI | 472 transitions | 480 transitions, same bursts |
| MISO | static low | static low — nothing answers |

So **the Pi's SPI0, whenever it is enabled, actively clamps SCK and shorts
out H1S1's clock.** H1S1 has been polling into a dead bus, its clock
swallowed by the Pi's push-pull output, and nothing answers on MISO — the
ADAU those meter reads were written for is not there to reply. The idle-
high SCK also says H1S1 runs that bus in a CPOL=1 mode, against the Pi's
mode 0/1: two masters, two clock polarities, no arbitration.

(The tree at `~/build-h1s1` has its `DspTx()` — `buffer[0]=0`, address hi,
address lo, payload over `CS_C`/`CS_M`, the SigmaDSP/ADAU write format —
entirely commented out, and `MainInit`/`MainLoop` are not in it at all. So
that tree is not the flashed image; the running `firmware/H1S1.shex` still
carries the poll.)

**Could it corrupt a DSP boot? Yes, but only the data, and only ~5 % of
the time — and it did not corrupt the boots that failed.**

- **Not the clock.** The same clamping that hid the poll protects the boot:
  with GPIO11 in `a0` the Pi's SPI0 output holds SCK, and the measurement
  is direct — **zero** foreign SCK transitions with `a0` attached, 1630
  without. A boot necessarily runs with GPIO11 in `a0`, so the clock the
  DSP sees during a boot is always the Pi's. (Earlier phrasing "injects
  foreign clock and data" was wrong on the clock half.)
- **The data, yes.** MOSI shows H1S1's bursts even with `a0` attached (472
  transitions vs 480 released), so H1S1 wins, or at least contends
  successfully, on that line. The DSPs' `SPI2_MOSI` (PA_01) hangs off it
  through the 22 R network, and during a boot the Pi has CS asserted, so
  the part *is* listening. A burst landing inside the transfer would put
  foreign bits into the stream and the block would fail its HDRSIGN/HDRCHK.
- **Probability:** ~600 µs of burst every ~260 ms against a 14 ms transfer
  ≈ **5.6 % per boot attempt**, one in eighteen. That is an intermittent
  failure nothing in the host logs could explain — worth removing — but it
  cannot produce the 100 % failure seen since March across hundreds of
  boots.
- **And it is excluded for the boots that matter.** Both of today's boots
  were captured end to end: the bursts fell at 48.3, 301.2, 557.2 and
  808.2 ms while the chip-1 boot ran 714.6 → 728.4 ms, and SCK showed
  exactly one burst, entirely inside the CS window, 16 334 of 16 384 edges
  at 50 % duty. Those two streams were clean, and the parts still did not
  respond.

**Actions:**

1. **Near term: remove the ADAU meter poll from the H1S1 firmware.** The
   part it polls is gone — this card is the SHARC DSP4 — so the poll is
   dead legacy whose only effect is contention on the boot bus. The unit
   already flashes H1S1 from `/home/app/firmware`. Needs the real H1S1
   sources; the tree at `~/build-h1s1` is not the flashed image.
2. **Rev D: give the DSP boot bus an owner.** Either separate it from the
   S-MCU housekeeping bus, or arbitrate it properly. D1 already says the Pi
   masters DSP SPI directly; the schematic quietly puts a second master on
   the same three wires.
3. Note for anyone reading `dsp4_netprobe.py` output: "MOSI/SCK HELD HIGH"
   is this — an external master idling its bus high — not a fault.

Unit left with matrix-app running and all three MCUs verified (13:17).


## HUB DISPATCH 2026-08-21 10:46Z — SHARC testing ② — boot retest on corrected CLKIN (÷2 + level-shift fitted)   [status: 🔴 blocked — clock now verified good at the pad and BOTH chips are still flat (GPIO8/GPIO12 never move, no RDY high in a reset-pulse trace); new lead found at the desk: neither SHARC has any decoupling in the rev-C schematic — PW checklist written, ordered by cost]   [model: opus]

model: opus

PW fitted the CLKIN level-shift bodge (variant: 1k replacing R33/R65 +
330R from the DSP-side pad to GND, per DSP — same 0.245 ratio as the 1k2/390R
in your mod doc) and the card is back in the rev C unit, which rebooted
11:45 local (matrix-app active, H1S1/H1S3/H1S4 verified). CPLD is already on
the ÷2 bitstream a1f6672af6c3. The unit is yours.

**PW BENCH RESULT 2026-08-21 (feed into this task):** scope at the R33/R65
pad shows CLKIN LEVEL and FREQ both good now (0.7-0.82 V, 24.576 MHz) — the
clock suspect is CLEARED electrically, mod restated BLUE on the mods PDF. BUT
the DSP LEDs (LD2/LD3) show NO activity after boot. So: the clock fix alone
did not bring the parts up. Your GPIO8 rdyprobe loop is now the discriminator
— run it FIRST. If GPIO8 also stays flat with a verified-good clock, the
live suspects narrow to: (1) damaged SHARCs (both overdriven ~80 mA into the
0.9 V clamp since March — check the datasheet abs-max exposure, and whether
a fresh card / fresh parts is the only proof), (2) SYS_HWRST behaviour at
p104 (never met the 11xtCKIN-after-supplies-stable spec before), (3) a
boot-stream/entry issue that the earlier "stream consumed" evidence never
actually ruled in. Rank these by cost for PW; do not iterate blind.

TASK — SHARC testing ②: boot retest on the corrected clock.
1. Baseline first, no bench eyes: netprobe PCM_CLK/PCM_FS toggling (CPLD
   alive), RDY1/RDY2 resting state, +0.9 V sanity if readable. Note that
   PW has NOT scoped the clock level yet — if anything below behaves
   oddly, the first hands request is "scope R33/R65 pad: 0.70–0.82 V
   high, ≤0.10 V low, 24.576 MHz; if >0.82 V swap shunt to 300R".
2. Closed loop exactly as the 08-20 dispatch: rdyprobe1.ldr on chip 1,
   sample GPIO8 — success = ~1 Hz lo/hi. Then chip 2. Also repeat the
   "!RST_D pulse, no SPI traffic" RDY observation and compare with the
   dead-part baseline you recorded.
3. If the loop passes: blink1/blink2 (tell PW to eyeball LD3/LD2 at 1 Hz /
   2 Hz), then the production chip1/chip2 images and resume P2.2
   (dma_cfg_init) with working instruments. Record the verdict:
   "rev C CLKIN (freq + level) — root cause of the boot-handoff failure;
   fixed ÷2 in CPLD + level-shift bodge; rev D crystal per DSP".
4. If still flat: the fault is either the clock level at the pad (PW
   scope, see 1), damaged parts (both overdriven since March — a second
   card/fresh SHARCs is then the path), or something downstream; write
   the PW bench checklist ordered by cost and stop. Do not iterate blind.
5. Bookkeeping: mark the 07:23Z block 🟢/🔴 with the verdict; the mod
   goes BLUE on D24 DSP mods.pdf only after PW verifies on the scope —
   leave that to the hub, just record "fitted 2026-08-21 (1k+330R),
   scope verification pending" in the decisions doc.
Constraints: always restart matrix-app and confirm the three MCUs verify
before ending; Dropbox via ~/db; single trunk; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 11:05Z — 🔴 BLOCKED. Clock cleared, parts still dead.

**Verdict: the corrected CLKIN is NOT the root cause of the boot-handoff
failure.** With the clock verified good at the pad by PW's scope
(0.70–0.82 V, 24.576 MHz) and the ÷2 bitstream on the CPLD, every liveness
test reads exactly as it did against the dead-part baseline of 08-20.

| test | result |
|---|---|
| `dsp4_netprobe.py` full sweep (matrix-app stopped) | identical to the 08-20 baseline: PCM_CLK/PCM_FS **toggling** (CPLD alive), RDY1/RDY2 held low on R34/R22, MOSI/SCK held high, !RST_D held high by U7, MISO/CS floating |
| `dsp4_boot.py --ldr rdyprobe1.ldr --chip 1`, then 20 × `pinctrl get 8` | boot reported OK (1024 B on CS1); GPIO8 **`lo` on every sample** |
| `dsp4_boot.py --ldr rdyprobe2.ldr --chip 2`, then 20 × `pinctrl get 12` | boot reported OK (1024 B on CS2); GPIO12 **`lo` on every sample** |
| `--rdy-trace 1 --window 1.0` (!RST_D pulse, no SPI traffic, ~14 µs sampling) | 69727 samples, **no HIGH** |
| `--rdy-trace 2 --window 1.0` | 70789 samples, **no HIGH** |
| LD2/LD3 after a boot (PW, bench) | no activity |

No blind iteration beyond that: two boots per chip, one trace per chip.
Images on the unit were hash-checked against `build/` first (rdyprobe1
`6f8da654…`, rdyprobe2 `049792ab…`) — identical, so nothing stale was booted.

### The new lead, found at the desk: neither SHARC has any decoupling

The DSPA (p5) and DSPB (p4) sheets of `D24 DSP.pdf` each instantiate a
sub-sheet block labelled **CAPS** carrying VDD_INT / VDD_EXT / VDD_REF —
and both of those sheets (PDF pages 9 and 10) are **blank**: title block,
zero ink, measured. There are no C-designators anywhere on either DSP
sheet, while every other device on the card is decoupled (CPLD C8–C21, the
1V8 regulator C3/C4/C6/C7, the XO C2/C5, the M MCU C202–C205). Each part
has ~25 VDD_INT pins plus VDD_EXT and VDD_REF (the PLL/OTP supply), all
arriving over the DIL100 stack.

Unverified against the layout/BOM (the Proteus project is on the Windows
machine), so it is a lead, not a finding — but it is a **one-minute check
with the board in hand**, it would explain everything seen since March, and
the bodge is a handful of 0402s. It is step 0 of the checklist below and
rev-D **mod 14**.

### Two suspects cleared from the desk (do not spend bench time on them)

- **Reset timing.** `dsp4_boot.py` holds `!RST_D` low 50 ms and waits
  500 ms before the first byte; the datasheet asks 11 × tCKIN ≈ 0.45 µs for
  both tWRST and tRST_IN_PWR (Tables 22/23), with supplies long stable. The
  timing half of the HWRST suspect is answered; only the *level* at pin 104
  is unproven, given the two unarbitrated masters on that net.
- **CGU arithmetic — and a correction to this dispatch's premise.** The HRM
  gives **PLLCLK = SYS_CLKIN × MSEL / 2** with reset defaults **MSEL = 40,
  CSEL = 1, SYSSEL = 2, S0SEL = 4** (Tables 2-10/2-11 + register diagrams).
  So at 24.576 MHz: PLLCLK 491.5 MHz, CCLK 491.5 MHz, SYSCLK 245.8 MHz,
  SCLK0 61.4 MHz — every one inside spec, ROM correctly clocked with no CGU
  programming (there is none anywhere in `SHARC/src`, correctly). At the old
  49.152 MHz it was 983 MHz PLLCLK/CCLK — inside the *family* maxima though
  about double the 21564 grade. The 07:23Z claim "MSEL = 60, DF = 0 →
  2.95 GHz, cannot lock, the ROM can never have run" was wrong twice (it
  dropped the /2 and used the wrong default). The ÷2 is still right — fCKIN
  20–30 MHz is an input-pin spec and 49.152 MHz violated it by 64 % — but
  the mechanism was not "the PLL could not lock", and nothing should rest on
  that story. Recorded in D10.

### Checklist written for PW, ordered by cost

`~/db/TransferOnly/PCB mods/dsp4-revC-liveness-checklist.md` (new):

0. **Eyes, no instruments** — are there ANY caps on the DSP power pins;
   does the layout/BOM have what the schematic lacks.
1. **DMM** — +0.9 V (0.855–0.945), **+1V8 VDD_REF** (1.71–1.89, U2 output;
   never measured, and without it the PLL cannot lock), +3V3.
2. **Scope during a desk-driven boot** — SPI2 CLK/MOSI at R52/R51 (DSPA),
   R19/R18 (DSPB): 1 MHz burst, mode 1. First proof a part receives data.
3. **Scope** — SYS_HWRST at p104 across the !RST_D pulse: does it actually
   reach VIL ≤ 0.7 V with U7 pin 47 also driving that net.
4. **The parts.** If 0–3 are clean and RDY still never moves: both were
   overdriven ~80 mA into a 6 mA-max clamp since March. Fresh card / fresh
   SHARCs is the only clean proof; a JTAG bodge is the alternative — and
   note the DSP TAP pins (99–103) are terminals that reach *nothing* on
   rev C, not even each other, so it is 5 wires per part on 0.5 mm pitch.
5. **Boot stream** last: it was verified byte-by-byte on 08-20 and cannot
   be ruled in until step 2 passes.

### Bookkeeping done

- Mod doc `dsp4-revC-clkin-bodge.md`: status → **fitted and scope-verified**,
  the as-fitted 1 k + 330 R recorded against the specified 1k2 + 390 R, a
  second trim ladder added for the 1 k series (300 R is the trim-down if a
  card reads > 0.82 V), the fault-1 mechanism corrected, and §6 records the
  retest result. Hub: the mod can go BLUE on the mods PDF — PW has scoped it.
- `dsp4-revD-modlist.md`: **mod 14 (DSP decoupling, RED)** added; mod 8
  annotated as fixed-and-verified-but-not-the-cause; mod 11 gains the "the
  TAP pins connect to nothing" detail.
- `dsp4-architecture-decisions.md` **D10**: bodge fitted + verified,
  the CGU correction, and what the fix did not fix.
- `MW/D24/HW/hardware-map.md` §3: verified clock chain, the decoupling
  observation, the three DSP supplies and where they come from (VDD_REF is
  on-card from U2), JTAG/RESOUT/FAULT connectivity.
- Unit left with matrix-app running and all three MCUs verifying.

**Blocked on:** PW at the board — checklist step 0 (eyes) and step 1 (DMM)
need nobody's permission and may end this investigation; steps 2–3 need a
scope on a powered card, and the boot side of them can be driven from the
desk.

## HUB DISPATCH 2026-08-21 07:23Z — SHARC testing ① — CPLD dsp_clk ÷2 (CLKIN out of range) + closed-loop retest   [status: 🔴 closed — VERDICT 2026-08-21: the clock chain was a real two-part fault (fCKIN out of range + a 3.3 V drive on a VDD_INT pin), both halves are now fixed and scope-verified on the card, and the boot handoff is STILL dead — so CLKIN was necessary but not sufficient, and this block's premise that it was the root cause is not confirmed]   [model: opus]

**Outcome 2026-08-21 09:55Z — 🔴 BLOCKED ON PW HANDS. Desk half done: ÷2 built, flashed and verified on the card; the level-shift bodge is specified and waiting to be fitted. No boot retest attempted — by the 08:45Z addendum it would not have produced a verdict.** See the outcome section at the end of this block.

model: opus

PW decision 2026-08-21: SHARC testing is the TOP priority for this machine;
reorder the NOW queue behind it (edit the NOW header to say so).

HUB HARDWARE REVIEW RESULT (mx26 docs/backlog-d24-schematic-errata.md
"DSP4 rev C", commit 5e1d419 — read it first): **SYS_CLKIN0 is driven at
49.152 MHz, outside the ADSP-2156x CLKIN range (20–30 MHz).** The CPLD
passes the XO straight through (`shared/dsp4-logic/rtl/dsp4_logic_top.v`
line ~100: `assign dsp_clk = sysclk;`). HRM CGU: reset-default MSEL = 60,
DF = 0 → PLLCLK ≈ 2.95 GHz at reset; the boot ROM can never have run.
This fits your 08-20 conclusion that there is no evidence either SHARC
ever received a byte. It is the prime suspect — test it first.

**TASK A — CPLD dsp_clk ÷2 (24.576 MHz).**
1. Replace the pass-through with a divide-by-2 flop on sysclk (50 % duty,
   glitch-free), keep pin 140; no other RTL changes. Add an SDC
   `create_generated_clock` for it. Update tb_logic_top to check dsp_clk
   = sysclk/2. Quartus build: fitter clean, STA met, LE delta noted.
   Commit the bitstream hash-named per the existing convention.
2. Flash it via the proven path (hub did it 08-19: SVF over the CM4 at
   app@192.168.1.219 — see mx26 tasks.md "dsp4_logic.fd6a5ec69198" and
   the IDCODE 0x020a30dd before/after check). Verify PCM_CLK/PCM_FS
   still toggle (netprobe) so the rest of the CPLD is unaffected.
3. Rerun the closed loop exactly as the 08-20 dispatch defines it
   (rdyprobe1.ldr on chip 1, sample GPIO8). Also repeat the
   "!RST_D pulse with no SPI traffic" RDY observation: with a live
   part the kernel should now show behaviour that differs from the
   dead-part baseline you recorded.
4. If GPIO8 toggles: boot blink1/blink2 (LD3/LD2 for PW at the bench),
   then the production chip1/chip2 images, and resume P2.2
   (dma_cfg_init) with working instruments. Record the verdict in
   findings/tasks as "CLKIN out of range — fixed in CPLD; rev D errata".
5. If still flat after a correct ÷2 (verified by build + a GPIO-side
   sanity where possible): STOP and write the scope checklist for PW's
   bench session — probe points are the 22R pads only: R65/R33 (CLKIN,
   expect 24.576 MHz, 3V3 swing), R51/R52 (SPI2 MOSI/CLK during a
   boot), p104 (HWRST), +0.9 V at J1 P1-6. Then the JTAG-bodge decision
   goes to PW (no DSP JTAG exists on the board).

**TASK B — bookkeeping.** Restate the clock finding in
dsp4-architecture-decisions.md (CPLD is the DSP clock source; 24.576 MHz
is the contract; programmable is a feature). Add the rev-D items from the
errata list to your "Blocked on PW" or rev-D section if not already there
(no JTAG, TRST floating, RDY pull-down, !RST_D dual master + PA13=SWDIO,
RESOUT/FAULT N/C, no test points). Datasheet gap: the 21560/61/64/68
datasheet is NOT in Dropbox or the repo (analog.com blocks fetch) — PW
asked to drop it into `_mx/_temp/adsp-2156x-docs/`; when it appears,
confirm the fCLKIN min/max line and close the [verify] tags.

**HUB ADDENDUM 2026-08-21 09:20Z — session restarted (permission mode
change only).** The previous session was killed by the hub mid-task to
relaunch under bypassPermissions; nothing of its work is lost: the working
tree holds the uncommitted ÷2 RTL/SDC/tb edits and the new bitstream
`dsp4_logic.a1f6672af6c3.*` (old fd6a5ec69198 files deleted), the board
was reported flashed with the ÷2 image and baseline netprobes taken, and a
mod document (CLKIN level-shift sizing against the datasheet) was being
written. Resume from `git status`: review those edits as your own, finish
the mod document, commit, and continue the 08:45Z addendum plan.

**HUB ADDENDUM 2026-08-21 08:45Z — datasheet now in hand (PW).** Files:
`~/db/_mx/_temp/adsp-2156x-docs/adsp-21560-21561-21564-21568.pdf` (Rev. A,
Feb 2026) + the 21564-specific HRM, EE-461 and the anomaly list, same
folder. mx26 errata DSP4 section updated (mx26 3371173). Two CONFIRMED
clock faults, which change TASK A:
1. fCKIN = 20–30 MHz (Table 23, crystal and external alike) — the ÷2 is
   right; finish step 1 (RTL/SDC/tb/build/commit).
2. **SYS_CLKIN0 is a VDD_INT-domain pin.** Abs max SYS_CLKIN0 input =
   –0.3 V to VDD_INT (Table 19); VIHCLKIN max = VDD_INT, VILCLKIN max
   +0.12 V; "must not exceed the internal (VDD_INT) voltage level". The
   CPLD drives it at 3.3 V through 22R → both SHARCs overdriven since
   first power-up; the pin clamp pumps the +0.9 V rail; parts may be
   damaged.
So: do NOT flash + retest expecting a verdict. Instead (a) commit the ÷2
build; (b) size a proto level-shift at R65/R33 to a ~0.8 V swing at pin 5
(e.g. ~560R series + ~180R shunt on the DSP side; check RC against the
24.576 MHz edges and the CPLD drive) and write it as a RED mod for PW to
fit, plus the scope checklist (first: +0.9 V sane with the card fitted,
clamping at pin 5); (c) downgrade TRST (internal pull-down per the signal
table), note BMODE2 internal PD and SYS_FAULT open-drain (external pull-up
if used). Record in this block + the decisions doc; when the desk work is
done mark the block 🔴 blocked on PW hands (bodge); push.

Constraints: chips may be freely booted/reset; ALWAYS restart matrix-app
and confirm the three MCUs verify before ending the session or between
long gaps; Dropbox via ~/db. The rev C unit is yours (no other machine
dispatched to it). Single trunk; update the dispatch block status; no AI
attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 — what was done

**TASK A step 1 — done and committed (a4ee3d1).** `dsp_clk` is now a
dedicated toggle flop off sysclk: 24.576 MHz, exact 50 % duty (datasheet
asks 45-55 %), glitch-free by construction, `preserve`d so the
synthesiser cannot merge it into the heartbeat counter's carry chain and
put the DSPs' only clock on an LE mid-chain. SDC gains a
`create_generated_clock` (with a comment recording why Quartus warning
332088 is benign here — nothing inside the CPLD is clocked by dsp_clk).
`tb_logic_top` now checks period = 2 sysclk and high = 1 sysclk instead
of pass-through equality. Build: fitter clean, timing met, **157/1270 LE
(+1 for the flop)**, fmax 70.21 MHz, sim gate PASS, bitstream
`dsp4_logic.a1f6672af6c3` (source hash recomputed and matched before
committing).

**TASK A step 2 — done, verified on the card.** Programmed over the CM4
JTAG bit-bang path: IDCODE `0x020a30dd` before and after, **40779 SVF
commands, 0 errors, 58 s**. `dsp4_netprobe.py` after the flash: PCM_CLK
(GPIO18) and PCM_FS (GPIO19) still TOGGLING, every other net reads
exactly as it did on 08-20 — the rest of the CPLD is unaffected.
matrix-app restarted; **all three MCUs verify** (H1S1 "// H1S1 DSP",
H1S3 SW Right, H1S4 SW Left).

**TASK A steps 3-5 — deliberately NOT run.** Per the 08:45Z addendum a
retest cannot produce a verdict while the second fault stands, and each
boot attempt is more powered time on an overdriven pin. The scope
checklist replaces them.

**The second fault, sized and written up (the 08:45Z addendum's (b)).**
`SYS_CLKIN0` is the one signal pin in the **VDD_INT** domain: Table 7
(power domains), Table 13 (designer quick reference), Table 19 (abs max
= −0.3 V to VDD_INT), operating conditions (VIHCLKIN 0.68 V…VDD_INT,
VILCLKIN ≤ +0.12 V, VDD_INT 0.855/0.900/0.945 V), and the crystal
section's flat statement that the external clock "must not exceed the
internal (VDD_INT) voltage level". Rev C drives it at 3.3 V through 22 R
— R65 → DSPA U6 p5, R33 → DSPB U5 p5, both confirmed off the schematic
at 400 DPI, along with DSP_CLK on CPLD pin 140 in a **+3V3** bank
(VCCIO2_1/2_2 both on +3V3, so the swing really is 3.3 V). Through 22 R
the clamp demand is ~80 mA per part against a 6 mA per-pin absolute
maximum, injected into the +0.9 V core rail, continuously since March.

**Mod written: `TransferOnly/PCB mods/dsp4-revC-clkin-bodge.md`** (RED,
awaiting PW). Per DSP: R65/R33 22 R → **1k2**, plus a new **390 R** to
GND at the DSP-side pad. Ratio 0.245 → ~0.77 V high against a 0.68-0.855 V
window; ~2 mA per DSP (4 mA total on CPLD pin 140) instead of the ~160 mA
the two clamps are asking for now; Thevenin 294 R into ~7 pF → ~4.6 ns
edges on a 40.7 ns period, so tCKINH/L stay far above the 16.67 ns
minimum. Includes a trim ladder (360/390/430 R), the physical fitting
notes, and the **bench scope checklist** — ordered, with expected values:
+0.9 V rail first (a high reading means the clamps are pumping it), then
the clamped ~1.2-1.6 V clock at R65/R33 as direct confirmation of the
fault, then post-mod acceptance (0.70-0.82 V high, ≤0.10 V low,
24.576 MHz), then the boot retest with SPI2 CLK/MOSI at R52/R51 and
HWRST at p104. Failure branch spelled out: clean clock + good rail +
visible SPI traffic and still no RDY ⇒ the parts themselves, and the
JTAG-bodge / replace decision is PW's (there is no DSP JTAG on the card).

**TASK B — done.** New binding decision **D10** in
`dsp4-architecture-decisions.md`: the CPLD is the single DSP clock
source, 24.576 MHz is the contract, fCKIN must stay inside 20-30 MHz,
SYS_CLKIN0 must be level-translated to 0.68-0.855 V on any DSP4-derived
board, and the per-DSP-crystal alternative is explicitly rejected (it
would give up the programmable single source). `hardware-map.md` §3
records the R65/R33 topology and both faults. Rev-D list gains **mods
8-13**: the clock chain (mod 8, RED), RDY pulls → pull-ups, `!RST_D`
dual master (Pi GPIO16 + U7 p47 = PA13/SWDIO), a DSP JTAG header,
RESOUT/SYS_FAULT liveness (FAULT is open-drain, external pull-up
required), and test points. **Mod 7 (JTG_TRST) is downgraded to no
action**: Table 13 gives JTG_TRST an internal **pull-down** (TDI/TMS/TCK
have internal pull-ups), so floating TRST holds the TAP safely in reset.
SYS_BMODE2's internal pull-down is recorded with it. The datasheet gap is
closed — all `[verify]` tags on fCKIN and the CLKIN levels are now
answered from `adsp-21560-21561-21564-21568.pdf` Rev. A.

**Blocked on:** PW fitting the four resistors and running the scope
checklist. Everything after that is desk work over SSH.

**Note for PW:** the card is still being overdriven whenever it is
powered. The bodge doc says it plainly — keep powered time short until
the divider is fitted. matrix-app is running now because the dispatch
constraint requires the unit left verifying, not frozen.

## HUB DISPATCH 2026-08-20 18:43Z — Boot handoff investigation — apps never execute   [status: 🔴 blocked]

ROOT QUESTION: SHARC boot streams are fully consumed by the ROM (per-chunk
RDY back-pressure works end-to-end with the fixed active-low tool) but
APPLICATION CODE NEVER EXECUTES — proven tonight with a closed loop:
`src/blink/rdyprobe.asm` (blink.asm with PORTA→PORTB, bit 5 = PB_05 =
SPI2_RDY) booted on chip 1 and the Pi sampled GPIO8 flat low; the PA_12
blink images also never light LD2/LD3 (PW verified LED wiring anode→R→
PA_12, cathode→GND: pin-high = lit). All dma_cfg_init work is downstream
of this and moot until fixed.

Find why the ROM→application handoff fails. Investigate at the desk, then
verify with the closed loop (no bench eyes needed).

Suspects, in order:
1. Boot-stream format: elfloader flags are `-b SPI -bcode 1 -f BINARY
   -width 8`. Check HRM ch.40 (text already extracted to hrm.txt in your
   scratchpad from the previous session — regenerate if gone) for the
   BLOCK CODE / BCODE the 2156x ROM expects in SPI SLAVE boot (BMODE
   0b010), and whether -b SPI + bcode 1 encodes master vs slave. Parse
   the actual bytes of build/rdyprobe1.ldr (block headers: dBlockCode,
   dTargetAddress, dByteCount, dArgument; FIRST/FINAL/INIT flags) and
   check: final block flags, jump target address, and whether the ROM
   requires anything the stream lacks.
2. Entry/IVT: the .dxe has NO ELF entry (elfloader "Defaulting to
   0x90004"). Verify in the built blink/rdyprobe images that address
   0x90004 (RSTI slot) actually receives a jump to _start (dump the dxe:
   elfdump, or parse the .ldr payload for the 0x90000-block content).
   Check blink_ivt.asm places the IVT at 0x90000 and the LDF puts
   seg_pmco somewhere the ROM actually loads.
3. Post-boot core state: does the 2156x ROM hand off with the core in a
   state our code mishandles (e.g. executes from an address alias we
   didn't link for)? Compare with an ADI example loader stream if any
   ships in CCES (look under /opt/analog/cces/3.0.3/SHARC/ldr or
   examples) — diff their header/entry conventions against ours.
4. If a stream fix is identified: apply to build.sh loader() (and
   dsp4_boot.py only if the transport itself must change), rebuild
   rdyprobe1.ldr, and VERIFY with the loop below. Iterate until GPIO8
   toggles.

CLOSED-LOOP VERIFICATION (run as often as needed):
  ssh app@192.168.1.219 'cd /home/app/dspboot && python3 dsp4_boot.py \
    --ldr rdyprobe1.ldr --chip 1' \
  && ssh app@192.168.1.219 'for i in $(seq 1 12); do pinctrl get 8 | \
    grep -oE "lo|hi"; sleep 0.25; done'
Success = alternating lo/hi (~1 Hz). Copy fresh rdyprobe1.ldr to
/home/app/dspboot/ before each run. rdyprobe.asm is untracked — commit it
(it is now a permanent bring-up tool) with a header comment.

After GPIO8 toggles: boot blink1/blink2 and note in tasks.md that PW
should confirm LD3/LD2 blink at next bench visit (1 Hz / 2 Hz — also the
free CCLK measurement); then the production/park builds become meaningful
again and P2.2 resumes with working instruments.

Constraints: chips may be freely booted/reset (PW has released the
bench; the bisect state is void anyway). ALWAYS restart matrix-app
(sudo systemctl restart matrix-app) and confirm the three MCUs verify in
/home/app/logs/log before ending the session or between long gaps —
the unit must not be left on a frozen splash. Dropbox via ~/db. Single
trunk; update the dispatch block status; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

**Outcome 2026-08-20 20:20Z — 🔴 NOT FIXED. GPIO8 is still flat low after
every variant tried, so the handoff still fails. But the suspect list is
now much shorter: the boot stream and the toolchain flags are CLEARED with
evidence, two genuine defects in the boot host were found and fixed, and
the one assumption everything rested on — that the parts were receiving —
turns out to have no supporting evidence at all. Unit restored, all three
MCUs verify, app running.**

### The closed loop, run many times — always flat

`rdyprobe1.ldr` booted on chip 1 and GPIO8 sampled, across the full cross
product of SPI mode {0, 1} × post-reset settle {0.05 s, 0.5 s, 2.0 s}:
`lo` on every sample of every run. Nothing tried tonight moved it.

### Suspect 1 (boot-stream format) — CLEARED, with the bytes

Every block of `rdyprobe1.ldr`, `blink1.ldr` and the 207 KB production
`chip1.ldr` was parsed field by field against HRM ch.40 Fig. 40-15 /
Table 40-27. The streams are textbook:

- Headers are 16 B: BLOCK CODE / TARGET ADDRESS / BYTE COUNT / ARGUMENT.
  HDRSIGN = 0xAD (core 0) on every block; the HDRCHK XOR checksum was
  recomputed and matches on every block; `chip1.ldr` parses cleanly
  through 608 blocks and lands exactly on EOF (0x32814 = file length).
- First block = `BFLAG_FIRST|BFLAG_IGNORE`, count 0, TARGET_ADDRESS
  **0x00090004** (the RSTI slot — the entry point the kernel writes to
  RCU_SVECT0 at termination), ARGUMENT = offset of the final block.
  Final block = `BFLAG_FINAL`, count 0, same target. Both correct.
- The IVT **is** in the stream: a 48-byte payload block (8 NW slots × 6
  bytes) to 0x28240000. That address is right: NW 0x00090000 ↔ BW
  0x00240000, 6 bytes per 48-bit word, which is exactly why the stock
  CCES `ADSP-21564.ldf` starts `mem_block0_bw` at 0x002403F0 (0xA8 words
  × 6). Slot 1 (RSTI, word index 4) decodes as `jump 0x1C0000` — the SW
  address of `_start` at BW 0x380000. `BFLAG_AUX` is correctly absent:
  elfloader already emits byte-space addresses, so no PM translation is
  wanted.
- `-b SPI` vs `-b SPIHOST`: elfloader 6.4.2.1 emits **byte-identical**
  output for both (checked on blink1). `build.sh` now says `SPIHOST`
  anyway, because `-b SPI` documents the master/flash case and this is
  the host-push case. `-bcode 1` is right — HRM Table 40-19 gives
  SPIS_BCODE `00xx` = single-bit SPI bus, and 1 is in that range. (The
  BCODE nibble is also the first byte of the stream, which is what
  Table 40-18's SPICMD auto-detect reads.)

Nothing in the image explains the failure.

### Suspect 2/3 (entry, board straps, clock) — CLEARED off the schematic

Read at 1200 DPI from `D24 DSP.pdf` p5/10 (DSPA, U6):

- `SYS_BMODE0` = **pin 105 → GND**, `SYS_BMODE1` = **pin 106 → VDD_EXT**,
  `SYS_BMODE2` = **pin 82 → GND**. BMODE[2:0] = 0b010 = SPI Slave Boot
  (HRM Table 40-14). The strap is right. (`SYS_RESOUT` p107 is NC, so
  there is no reset-done signal to watch.)
- `SYS_CLKIN0` = pin 5, fed from **DSP_CLK through R65 (22R)**.
- `SPI2_RDY` → **PB_05** through R38 (22R), with R34 10K to GND —
  confirming what `rdyprobe.asm` drives is the right pin.
- SPI2 on DSPA: MISO→PA_00, MOSI→PA_01, CLK→PA_04, SS→PA_05.
- The S MCU (U7, p3/10) housekeeping SPI is on **ISPI0/1/2**, which are
  DIFFERENT nets from the Pi's SPI0/1/2 — so H1S1 is not a second master
  on the boot bus. It *is* a second driver on `!RST_D` (U7 pin 47).

**The LOGIC CPLD is alive and clocking.** LOGIC masters the Pi PCM port,
and `PCM_CLK` (GPIO18) / `PCM_FS` (GPIO19) read as TOGGLING at the Pi.
`dsp_clk` is a pass-through of the same `sysclk` that feeds the clkgen,
so the "unprogrammed CPLD = no DSP clock" theory is dead as stated.
`!RST_D` really does go low when the Pi drives it (verified by reading
the net back).

### TWO REAL DEFECTS FOUND AND FIXED in `dsp4_boot.py`

1. **SPI clock mode was 0; the boot kernel uses mode 1.** HRM ch.40:
   "In SPI slave boot mode, the boot kernel sets the SPI_CTL.CPHA bit and
   clears the SPI_CTL.CPOL bit", and ch.15 fixes the numbering —
   "mode-0 (CPHA=CPOL=0) and mode-3 (CPHA=CPOL=1)" — so CPHA=1/CPOL=0 is
   **mode 1**: MOSI is latched on the FALLING edge. A mode-0 host changes
   MOSI on exactly the edge the kernel samples. Now `SPI_MODE = 1`, with
   `--spi-mode` as an escape hatch. (The RUNTIME link is a separate
   question and correctly stays mode 0 — `spi2_init()` leaves CPOL and
   CPHA clear, matching `dsp4_diag.py`.)
2. **No settle time after reset release.** HRM Fig. 40-7 does not use a
   timer: the host waits for SPI_RDY DEASSERTED then ASSERTED, which is
   the kernel saying "SPI2 is up". That handshake does not exist on this
   card (pull-downs, see below), so the host was clocking bytes
   microseconds after `!RST_D` released, while the part was still in
   pre-boot. Now `POST_RESET_S = 0.500`, `--post-reset-delay` to override.

Both are real bugs by the manual. Neither, alone or together, made GPIO8
move — so there is at least one more cause.

### The finding that matters most: "the stream was consumed" was never evidence

New tool **`tools/pi/dsp4_netprobe.py`** asks the only question that
discriminates on a bus like this one: make the Pi pin an input, select the
internal pull-up, read; select the internal pull-down, read. Follows both
= nothing else drives it. Result:

| net | Pi | verdict |
|---|---|---|
| SCK | GPIO11 | HELD HIGH by something stronger than the Pi pull |
| MOSI | GPIO10 | HELD HIGH by something stronger than the Pi pull |
| MISO | GPIO9 | floats |
| CS1 / CS2 | GPIO6 / GPIO24 | floats (the H1S1 CS1-6 fix holds) |
| RDY1 / RDY2 | GPIO8 / GPIO12 | HELD LOW (R34 / R22, as designed) |
| !RST_D | GPIO16 | HELD HIGH (H1S1 U7 p47 also drives it) |
| PCM_CLK / PCM_FS | GPIO18 / GPIO19 | TOGGLING — the CPLD is running |

And a `!RST_D` pulse with **no SPI traffic at all**, sampling SPI_RDY every
~15 µs for 1 s: not one HIGH, on either chip, on any run. A 64 KB blast of
deliberate garbage at 20 MHz with no flow control: also not one sustained
HIGH — and a kernel that rejects a bad header should stop draining and let
the RX FIFO fill within ~32 bytes.

Because the card's pulls rest SPI_RDY ASSERTED, "every chunk was accepted"
is what a *dead* part looks like too. **There is currently no positive
evidence that either SHARC has ever received a single byte.** Every prior
"the stream was consumed" reading is compatible with the parts never
having listened. That is the honest state of the investigation.

### Committed alongside

- `src/blink/rdyprobe.asm` — now a permanent bring-up tool with a proper
  header, plus a `./build.sh rdyprobe` target. `blink()` and `rdyprobe()`
  are one parameterised `tiny_image()`; `blink1.ldr` is byte-identical
  after the refactor, checked.
- `LDRFLAGS` is now defined once and shared by `loader()` and
  `tiny_image()`.
- `tools/pi/dsp4_netprobe.py` (above), deployed to `/home/app/dspboot/`.

### Next — in this order

1. **Prove or disprove that a SHARC is receiving.** Everything else is
   guesswork until this is settled, and it needs a scope at the part:
   SYS_CLKIN0 (p5) for DSP_CLK actually arriving, then PA_04/PA_01
   (SPI2 CLK/MOSI) during a boot, then SYS_HWRST (p104). One session with
   a probe answers what a week of desk work cannot.
2. ~~The one board assumption still unverified~~ **VERIFIED 2026-08-20
   (hub): PA_00=SPI2_MISO, PA_01=SPI2_MOSI, PA_04=SPI2_CLK,
   PA_05=SPI2_SEL1/SS, PB_05=SPI2_RDY — from ADI's own pinmux data:**
   `ADSP-21564-pinmux.xml` inside CCES
   `Eclipse/plugins/com.analog.crosscore.addins.pinmux_*.jar`
   (extracted to /tmp/pinmuxjar on this machine; the jar is the local
   authoritative pin-function source — datasheet fetch no longer
   blocks anything). Schematic net names correct on every SPI2 pin;
   rdyprobe drives the right pin. Suspect list for the scope session
   accordingly narrows to the physical layer: VDD_INT (+0.9 V core
   rail) actually present at the card, SYS_CLKIN0 actually clocking,
   SYS_HWRST behavior, then PA_04/PA_01 during a boot. The HRM has no pin-function table
   (it is in the datasheet, which is not in `_mx/_temp/adsp-2156x-docs` —
   only `adsp-2156x_hwr.pdf`), and analog.com times out on fetch. If the
   two are the other way round the parts have never seen MOSI. **Get
   `adsp-21560-21561-21564-21568.pdf` into the Dropbox docs folder and
   check PORTA against p5/10.**
3. Rev-D hardware items, both from tonight: R34/R22 want to be pull-UPs
   (already logged 17:16Z; tonight shows exactly what it costs — no
   liveness signal at all); and `!RST_D` has two masters (Pi GPIO16 and
   H1S1 U7 p47) with no arbitration.
4. Left in the working tree, NOT committed, from an earlier session: a
   `DSP4_BISECT == 4` park in `src/dma_config.c` (its `#error` guard text
   still says 0-3). It is out of scope for this dispatch — finish or drop
   it deliberately.

## HUB DISPATCH 2026-08-20 17:16Z — P2.2 fix flash + readback verification   [status: 🔴 blocked]

**Outcome 2026-08-20 18:30Z — production images built and BOOTED into both
SHARCs (a first: with real flow control), but the readback verdict is FAIL
— both chips still echo all-zero, so P2.2 is NOT verified. Separate and
bigger find on the way there: `dsp4_boot.py` had the SPI_RDY polarity
INVERTED, and every boot before today only worked because H1S1 was
driving the shared CS3/CS4 nets high. Fixed and proven. Unit restored,
all three MCUs verify, app running.**

### What was done

1. **Build.** `DSP4_BISECT=0 ./build.sh all` — production, 0 errors.
   Confirmed the scaffolding really is compiled out: `elfdump -sym` on
   `build/chip{1,2}/dma_config.doj` shows no `_diag_stage_set` reference
   on either chip. Artifacts `chip1.b4090de01d5d.ldr` (207108 B) +
   `chip2.bb2b24db8617.ldr` (108172 B), hash-named, `ldr/manifest.txt`
   updated with the superseded pair recorded.
2. **Deploy.** scp'd to `app@192.168.1.219:/home/app/dspboot/`, sha256
   re-verified on the unit. matrix-app stopped, `S_RESET` (`*`) sent
   twice at 115200 8N1 on `/dev/serial0` with 2 s between, matching
   `Boot.FlashFirmwareViaSerial`.
3. **Boot — failed, then root-caused, then succeeded.** See below.
4. **Readback — FAIL.** See "The readback verdict".
5. **Restore.** matrix-app restarted; `MCU verified: // H1S4 SW Left`,
   `// H1S1 DSP`, `// H1S3 SW Right` and `Boot.Loop() - MCU boot
   verified: H1S1 / H1S3 / H1S4` at 18:30:31-37Z. Unit left whole with
   the production images loaded in both DSPs.

### THE BOOT-TOOL BUG — SPI_RDY polarity was inverted (fixed)

First boot attempt failed on BOTH of the tool's attempts, chip 1, before
a single byte: `SPI_RDY never asserted within 2.0s`. GPIO state read at
the time: `!RST_D` (GPIO16) = 1 (released), CS1 (GPIO6) = 1, **both RDY
lines low** — chip1 GPIO8 = 0, chip2 GPIO12 = 0.

- **The tool waited for HIGH.** Its docstring reasoned from the board's
  10K pulldowns (R34 DSPA / R22 DSPB) that asserted must be high.
- **The HRM says the opposite for boot.** Ch.40, SPI Slave Boot Mode:
  "In SPI slave boot mode, SPIx_RDY functionality is critical. The
  SPIx_RDY output is used for back pressure and requires a pulling
  resistor. **The boot code requires the SPIx_RDY signal function as
  active-low.**" The polarity during boot is the on-chip boot kernel's
  and is not configurable. Asserted = 0. Both parts were sitting there
  ready and the tool was waiting for the one level that never comes.
- **Why it only broke today.** CS3/CS4 are SHARED nets — Pi RDY inputs
  AND H1S1's "DSP 1/2 chip SPI_RDY" monitors (`MW/D24/HW/hardware-map.md`
  §3a). Until the 2026-08-20 17:17Z reflash, H1S1 drove CS1-6 push-pull
  HIGH, so the Pi always read 1 and **every RDY wait in every boot to
  date passed vacuously — all previous boots ran with no flow control at
  all.** Making CS1-6 inputs exposed the real line. The CS1-6-inputs
  change is correct and stays; it just uncovered this.
- **This also explains the "first attempt always fails, retry works"
  quirk** (reproduced ×3, 2026-08-19/20) — a timing race against a line
  nobody was reading correctly. With the polarity fixed, both chips
  booted on **attempt 1/2**, no retry.
- **Fix** (`tools/pi/dsp4_boot.py`): `wait_ready()` now takes
  `active_low`, defaulting to `RDY_ACTIVE_LOW = True` with the HRM
  citation; `--rdy-active-high` is an escape hatch, not a normal option.
  Threaded through `boot_chip`/`boot_chip_retrying`; module docstring
  corrected; the timeout message now names the expected level and points
  at the shared-net cause. Exercised off-target (asserted/stuck/timeout
  in both polarities) plus `--dry-run`; deployed to `/home/app/dspboot/`,
  md5 matches the repo copy.
- **Result:** `chip 1: attempt 1/2 OK — 207872 bytes sent on CS1`,
  `chip 2: attempt 1/2 OK — 108544 bytes sent on CS2`.

**HARDWARE ITEM for rev D — R34/R22 are the wrong way round.** The HRM
wants the pull to hold the line DEASSERTED while the part is in reset
("allows the processor to hold off the host while the processor is in
reset"). With boot fixed active-low, a pull-DOWN rests the line
ASSERTED, so the hold-off does not exist on this card and no host-side
wait can prove a part is alive or out of reset. Back pressure mid-stream
still works (the DSP drives the pin push-pull to deassert). Changing
R34/R22 to pull-UPS restores the hold-off — and would then also flip the
runtime `SPI_CTL.FCPL` to 0. Until that happens boot and runtime
legitimately disagree on polarity: `dsp4_boot.py` active-low,
`dsp4_diag.py`/`dsp4_config.py` active-high. Noted in `dma_config.c`
beside the `FCPL` write.

### The readback verdict — FAIL, and it cannot localise the fault

Against BOTH chips (`--cs-gpio 6 --rdy-gpio 8` / `--cs-gpio 24
--rdy-gpio 12`):

- With the runtime RDY gate honoured: `SPI_RDY never asserted` — SPI2 is
  never configured, so the pin is never driven and the pulldown holds it
  at 0.
- With the gate bypassed (`--rdy-active-low --resync`, which makes the
  resting-low line read as asserted so the transaction goes out):
  `response out of step reading 0xE000: echo 0x00000000, expected
  0xE0002000` — **all-zero echo, identical to the pre-fix symptom.**
- MAGIC / CHIP_ID / BOOT_STAGE / TICKS: none obtainable. No acceptance
  criterion from the dispatch was met.

**Why this is not evidence against the P2.2 fix.** `spi2_init()` runs at
DIAG_STAGE(5), *after* `arm_region(A)`, `arm_region(B)` and `sec_init()`
— i.e. the diagnostic link comes up downstream of the entire suspect
region. An all-zero readback therefore means "did not reach stage 5" and
says nothing about WHERE. It reads the same whether the part still dies
on lane index 4 of region A or now dies somewhere new. The SPI readback
was never able to bisect this; **LD2/LD3 is the only instrument that
can, and that needs bench eyes.**

**The addressing fix itself re-verified at desk level** against
`/opt/analog/cces/3.0.3/SHARC/include/sys/ADSP-21564.h`:
`REG_DMA10_DSCPTR_NXT = 0x31023000`, `REG_DMA17_DSCPTR_NXT = 0x31023380`,
`REG_DMA7_DSCPTR_NXT = 0x31022380`, and DMA8/DMA9 (MDMA0) sit off at
0x310A7000/0x310A7080. `sport_dma_base()` reproduces all of these
exactly. The fix is right; it was simply not sufficient on its own, or
the remaining fault is elsewhere.

### Next at the bench (PW, LD2 needed)

1. `DSP4_BISECT=1 ./build.sh` (park after `arm_region(A)`) and boot chip 1
   with the **fixed** boot tool. Steady 1 Hz square on LD2 = the SPORT4-7
   base fix closed the region-A wedge and the remaining fault is
   downstream; slow single blink = region A still dies and there is a
   second cause in `arm_region`.
2. Then `DSP4_BISECT=2` (park after `arm_region(B)`), then `=3`
   (EN-last) if A is implicated again.
3. Item 3 (clear the bisect scaffolding) stays BLOCKED — the scaffolding
   is now the only working instrument. Item 4 (`dsp4_config.py`, stage
   5→6) stays blocked behind a stage-5 readback.

### Deviation from the dispatch, declared

The dispatch's step 5 said one boot retry maximum and then mark 🔴. The
first boot failure was diagnosed to a tool bug with a documented HRM
citation rather than retried blind, the tool was fixed, and the boot was
run once more — which is what got both images loaded at all. The
readback that followed is the honest verdict and is reported as FAIL.
No CPLD or MCU was flashed; only the DSPs, `/home/app/dspboot`, and the
app stop/start were touched.


Flash the P2.2 wedge fix and verify by SPI readback — no bench eyes
available; the diag readback IS the verdict. PW has waived the
before-datapoint LD2 read; chip1's parked bisect state may be discarded.

Context: root cause fixed in fff7506 (sport_dma_base — SPORT4-7 at
0x31023000). Chip1 currently runs the round-1 park build, chip2 the
l1_to_sys-only build (both hung, harmless). Unit app is running with the
new H1S1 build; H1S1 proven not to drive !RST_D. dsp4_boot.py now has
the auto-retry. Dropbox via ~/db only.

Sequence:
1. Pull main. Build BOTH chips with **DSP4_BISECT=0** (production — no
   park, no stamps; note the current default is 1). `./build.sh all`,
   commit the .ldr pair hash-named per the artifact convention.
2. scp the .ldr pair to app@192.168.1.219:/home/app/dspboot/. Stop
   matrix-app, S_RESET '*' (hold slaves), run dsp4_boot.py for both
   chips (its auto-retry covers the hung-state first-attempt quirk).
3. Verify via dsp4_diag.py against EACH chip. Acceptance:
   - MAGIC correct, CHIP_ID = 1 and 2 on the right chips (proves CS
     routing), echo protocol passing (no all-zero echoes).
   - BOOT_STAGE = 5 (waiting for host product config) on both.
   - TICKS advancing between two reads (core alive), no unexpected
     ISSUES from the tool.
4. On PASS: restart matrix-app, confirm the three MCUs still verify,
   leave the unit whole. Update tasks.md: P2.2 marked VERIFIED ON
   HARDWARE with the readback evidence; note that item 3 (clear bisect
   scaffolding) is now unblocked and item 4 (dsp4_config.py, stage 5→6)
   is the next bench step. Commit + push.
5. On FAIL (readback still all-zero / stage < 5): do NOT thrash — one
   boot retry maximum beyond the tool's built-in retry; record exactly
   what the readback shows, restore matrix-app, mark the block 🔴 with
   findings; the staged LED bisect (DSP4_BISECT=1/2) resumes at PW's
   bench.

Constraints: touch ONLY the DSPs and /home/app/dspboot + app
stop/start — no CPLD flashing, no MCU flashing. Single trunk; update
this block's status; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

## HUB DISPATCH 2026-08-20 15:18Z — H1S1 aligned reflash + P2.2 prep (PW absent)   [status: 🟢 done]

**Outcome 2026-08-20 — both tasks done. TASK A: H1S1 reflashed with the
CS1-6-inputs build compiled against the RUNNING app generation
(`e80ccab5d6d8`); all three MCUs verify on reboot, DSPs untouched.
TASK B: boot-tool auto-retry + bisect variants B/C landed, and the HRM
desk-review FOUND THE P2.2 WEDGE — SPORT4-7 use DMA10-DMA17 at
0x31023000, not DMA8+ at 0x31022400; `2*sport+dir` off one base was
writing unpopulated MMR space. Fix applied (not flashed).**

### TASK A — H1S1 aligned reflash

- **Generation.** Built against `/home/app/fwbuild/matrix-aligned.h`
  (generated on-unit 2026-08-19 from `config/_matrix.mxc`, app build
  260714102659). `matrix_gen_id.py --compare` vs the unit's own
  decrypted matrix: **ALIGNED, full-id `e80ccab5d6d8`, 5412 cells,
  Sys001Skin001 = 5412**. Against mx26's baked
  `MatrixBus.Matrix.g.cs` it reports DRIFT of exactly one cell
  (`base-id 9b3c3d8f0286`): the g.cs predates `Sys001SwUpd001` (MxAdd
  6416, added on-device 2026-08-18) and still carries the dev-only
  `Aaa001Aaa001` placeholder, which shifts the `Zzz001Zzz001` sentinel
  6417 vs 6415. Hub confirmed the unit generation is the operative one.
  Immaterial either way for this image: **all four cells H1S1 actually
  compiles in are identical in both generations** — Sys001Enc001 5232,
  Sys001Skin001 5412, Sys001Test001 5414, Sys001Test002 5415 —
  confirmed in the linked ELF, `MATRIX[]` at `.rodata 0x080083b0` =
  {0, 5232, 5412, 5414, 5415}. The abandoned Dropbox-generation build
  had {0, 19479, 19727, 19730, 19731}.
- **Build.** `Debug/makefile.linux all` in the scratch copy
  `~/build-h1s1` (nothing written into Dropbox): exit 0, 0 errors,
  34036 text / 657 data / 1940 bss. 29 warnings, all pre-existing
  (`-Wpointer-sign` in DspTx/SpiTx/HAL_UART_Receive, three unused
  micGain* variables, CubeIDE `.cyclo` peer-target noise). Disassembly
  is byte-identical to the 2026-08-20 verified build except debug
  section sizes — the generation change lives in `.rodata`.
- **CS pins (acceptance 2).** All eight `GPIO_MODE_INPUT` in
  `H1S1.list`: CS5|CS2|CS7, CS8, and CS1|CS4|CS3|CS6(+BUSY,S3) groups
  each set `GPIO_InitStruct.Mode` to 0 in the disassembly.
- **Flash.** `hex2shex.py H1S1.hex H1S1` -> 2171 records / 34693 B
  image; previous pack image kept as
  `/home/app/fwbuild/pack-backup-H1S1.shex`. matrix-app stopped,
  S_RESET `*` on `/dev/serial0`, `app cli loadfw H1S1` -> MH1 loopback
  OK, S_SCAN found H1S1, all 2171 records ACKed, `// flash end of
  firmware record`, `OK: H1S1` (`logs/flash.log` 17:17-17:18Z).
- **Boot (acceptance 3).** matrix-app restarted and left running:
  `MCU verified: // H1S1 DSP`, `// H1S3 SW Right`, `// H1S4 SW Left`,
  then `Boot.Loop() - MCU boot verified: H1S1 / H1S3 / H1S4`. No new
  warnings — the only ones present are the 25 pre-existing SkinLoader
  "not in the matrix" notices (those cells are genuinely absent from
  the unit matrix, a skin<->matrix drift item, nothing to do with
  H1S1) and the pre-existing `mh1=?` build-stamp MISMATCH line.
- **DSPs untouched, as instructed.** No `dsp4_boot.py`, no `!RST_D`, no
  DSP reset. H1S1's own firmware never drives `!RST_D` — the only two
  writes to it in `main.c` are commented out and the pin is not in the
  `.ioc` — so the MCU reset during flashing did not reset either SHARC.
  Chip 1's bisect park should be intact for PW's LD2 read.
- **Flagged, not changed:** H1S1's blink handler still issues
  `DspTx(GPIOx, CSn_Pin, 0xF520, ...)` on SPI1 for all eight CS lines
  on every S_BLINK edge (ADAU-era LED writes, `matrix.cs` MainLoop).
  With CS1-6 now inputs it selects nothing, so this is strictly less
  intrusive than the build it replaced, but SPI1 SCK/MOSI still toggle
  on the housekeeping bus that carries the DSP CS provision. Deleting
  those dead calls belongs in the next H1S1 pass.

### TASK B — P2.2 prep

1. **`tools/pi/dsp4_boot.py` auto-retry.** `BOOT_ATTEMPTS = 2` with a
   `--attempts` override; every attempt is logged (`attempt n/m OK` /
   `attempt n/m FAILED`) so a part that needs the retry every time
   still says so. The retry restarts that chip's stream from byte 0 and
   deliberately does NOT re-pulse `!RST_D` (one reset line serves both
   DSPs). `Gpio` now releases and re-claims a line so the second
   attempt can re-request CS/RDY. Exercised off-target against a stub
   GPIO/SPI (fail-then-succeed and `--attempts 1` raise) plus
   `--dry-run`. Copied to `/home/app/dspboot/` so the next bench run
   picks it up (md5 matches the repo copy).
2. **Bisect round 2 ready to build, NOT flashed.** `DSP4_BISECT` in
   `dma_config.c`: 0 = production (no park, no stamps), 1 = round 1
   (default, park after `arm_region(A)`), 2 = **variant B** (park after
   `arm_region(B)`), 3 = **variant C** (write DSCPTR + CFG with
   `DMA_CFG.EN` clear, then set EN separately; parks after A so LD2
   answers the same question). `build.sh` passes it through:
   `DSP4_BISECT=2 ./build.sh`. All four values compile clean for both
   CHIP_IDs; an out-of-range value is a compile-time `#error`.
3. **HRM desk-review — root cause found (see the P2.2 note below).**
4. **`tools/pi/` sync.** `dsp4_config.py` pulled back from
   `/home/app/dspboot/` (the gpiod-v2 port) and committed verbatim;
   `dsp4_diag.py` and `dsp4_boot.py` were already byte-identical. Two
   rough edges in the ported `dsp4_config.py` left as-is so repo and
   unit stay identical, worth a tidy pass: the `if True:` block claims
   the RDY line unconditionally (crashes when `rdy_gpio is None` but
   `cs_gpio` is set), and the CS request is likewise unconditional.

Housekeeping: `~/mx26`'s `origin` was still HTTPS against a dead `gh`
token, so `git pull` there failed. Switched it to
`git@github.com:invirco/mx26.git` (same SSH key the dsp remote uses);
pulls work again and `tools/matrix_gen_id.py` is present.


Two tasks, PW absent — everything here is verifiable over SSH, no bench
eyes available. Unit access: app@192.168.1.219 (this machine's key works).
Dropbox via the space-free symlink ~/db ONLY. mx26 checkout at ~/mx26
(git pull it first; it has tools/matrix_gen_id.py and the app's baked
table src/sw/app/Core/MatrixBus.Matrix.g.cs).

**TASK A — reflash H1S1 with the CS1-6-inputs build (tasks.md NOW item 2).**
Correction to tasks.md first: it says H1S1 "has never been flashed" — STALE.
The hub flashed a matrix-aligned CS7/CS8-only build on 2026-08-19 night
(all three MCUs verify at boot since). What supersedes it is the CS1-6
build from the 2026-08-20 dispatch. Fix the tasks.md wording as part of
this task.

CRITICAL — matrix generation: the 2026-08-20 scratch build (~/build-h1s1)
compiled against the Dropbox MX/matrix.h generation (Sys001Skin001=19727),
which is NOT the running app's generation (5412). Do NOT flash that binary.
Rebuild against the running app's generation: the hub's 2026-08-19 flow
left an aligned header (matrix-aligned.h) on the unit or in its build area
— find it (check /home/app and the FW-home mechanics used that night), or
regenerate from the unit's own decrypted matrix as that flow did.
Verify alignment BEFORE flashing:
  python3 ~/mx26/tools/matrix_gen_id.py --compare <the matrix.h you built
  against> ~/mx26/src/sw/app/Core/MatrixBus.Matrix.g.cs
must print ALIGNED (base-id match).

Then: pack (H1S1.shex into the unit's firmware pack, same as 08-19) →
send S_RESET '*' on /dev/serial0 first (MH1 '?' responder is pre-loop
only) → `app cli loadfw H1S1` → confirm on reboot the app verifies
"// H1S1 DSP" AND both panels still verify.

Acceptance:
1. matrix_gen_id --compare says ALIGNED for the header actually compiled in.
2. H1S1.list of the flashed build: all eight CS pins GPIO_MODE_INPUT.
3. Boot log: H1S1 + SW Left + SW Right all verified, no new warnings.
4. tasks.md updated (item 2 done + the "never flashed" correction).

Constraints: do NOT touch the DSPs — no dsp4_boot.py, no !RST_D, no DSP
resets (chip1 carries the overnight bisect state; PW reads LD2 on return —
if the loadfw path unavoidably disturbs it, note that in the outcome, it
is re-establishable). Leave the unit with the app running.

**TASK B — P2.2 prep (desk work, no hardware contact with the DSPs).**
1. dsp4_boot.py: add auto-retry — a re-boot from a RUNNING/hung state
   fails its first attempt (SPI_RDY timeout) and works on the immediate
   retry (reproduced ×3). One automatic retry, log both attempts.
2. Prepare bisect round-2 as ready-to-build variants (guarded #ifdefs or
   committed patches — NOT flashed): variant B = park moved after
   arm_region(B); variant C = EN-write-order experiment (write DSCPTR +
   CFG with EN clear, then set EN separately).
3. HRM desk-review of the remaining dma_cfg_init suspects (DMA CFG EN
   write ordering, descriptor alignment, the lane-4/cs-mask special
   case) — findings appended to the P2.2 notes in tasks.md.
4. Sync the gpiod-v2-ported dsp4_config.py + dsp4_diag.py copies back
   from app@192.168.1.219:/home/app/dspboot/ into tools/pi/, commit.

Rules for both: work on main (pull first, push on completion); update this
dispatch block's status with a per-task outcome; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

# tasks — dsp spoke

Status: active · reprioritized 2026-08-20 (hub declutter — the full prior
text, day logs, and done-evidence live verbatim in
[archive/tasks-archive-2026-08-20.md](archive/tasks-archive-2026-08-20.md);
nothing was deleted).
Purpose: current work state for the mx26 → mx-dsp workflow and DSP4
firmware. This file is also the HUB DISPATCH queue (mx26 "machines"
model): the hub prepends dispatch blocks; sessions on this machine
execute them, commit, push `main`; the hub reviews on pull.

Trunk is `main` (`master` deleted + blocked). Mandates: `CLAUDE.md`.
Contract pin: **defs-v2026.08.20** (mx26 `345470a`; see `defs.lock` —
sync-from-mx26.sh now refuses an untagged mx26 HEAD).

## NOW — priority order (reordered 2026-08-21: SHARC BOOT SOLVED)

**MILESTONE 2026-08-21: both SHARCs boot and run application code.** Root
cause of the five-month boot-handoff failure was the boot host never
sending the **SPICMD byte** the SPI-target boot kernel reads as its first
byte (HRM ch.36 Table 36-18: 0x03 = keep single-bit); the ROM ate the
first `.ldr` byte as the command and every block header was misaligned by
one — which is why the 08-20 byte-by-byte stream audit found nothing (the
framing was right, the host was one byte early). `dsp4_boot.py --spi-cmd`
(default 0x03) fixes it; `--spi-cmd none` reproduces the flat-low failure
on demand. GPIO8 ~1 Hz on chip 1, GPIO12 ~2 Hz on chip 2, matrix-app up
(D14). **Parts were never damaged — no fresh card needed.** The clock
mods (÷2 + level-shift, D10) were real and are kept — an out-of-spec clock
had to be fixed regardless — but they were necessary, not the blocker.
Item 0 is DONE; the queue moves to P2.2 with working boot AND working LD2
blink as an instrument.

**MILESTONE 2026-08-21 (17:2xZ): chip 2's FULL FIRMWARE EXECUTES** — a
`DSP4_BISECT=5` park on `_start`'s first instruction fires 5/6. Two
independent faults were in the way and both are characterised in the
14:37Z dispatch outcome above: elfloader's ZERO-FILL blocks (fixed with
`-NoFillBlock` + a build-time guard) and U7/H1S1's ADAU poll on the
shared boot bus (mitigated with `dsp4_boot.py --sync-poll` at 10–11 MHz).
The ">8 KB block-size limit" is retired — it never existed.

**NEW NOW ITEM — zero the delay buffers in firmware startup.** With
`-NoFillBlock` every zero-initialised byte is clocked into the part for
real, so `sec_delay`/`sec_delay_ovf` (~1.7 MB) are now `NO_INIT` in the
LDF — otherwise chip 2 becomes a 1.9 MB, ~2.4 s stream that cannot
possibly boot. **Until firmware clears them at startup, the delay lines
come up holding whatever was in L2.** Owner: next SHARC dispatch.

**DONE 2026-08-21 — H1S1 reflashed, the boot bus has one master again.**
Its two SPI1 call sites (periodic `TestMicPres()`, and the CS1–CS8
`DspTx` LED writes) are removed and it was reflashed through MH1. The bus
measures 0 events in 15 s and **chip 1's full 258 KB firmware now boots
6/6 unsynced**. Full detail in the 14:37Z addendum above.

**NEW NOW ITEM — the `_sru_init` fault is the top SHARC item now.** With
both images loading reliably, the firmware hangs in `_sru_init`'s DAI0
half (the first SRU register writes). No loop in that function, so it is
a fault, not a spin. `dma_cfg_init` and the `sport_dma_base()` fix are
still untested — they are downstream of it.

**Context:** the rev-C card is LIVE on the fresh digital board — CPLD
`a1f6672af6c3` flashed 2026-08-21 (the ÷2 clock fix; supersedes
`fd6a5ec69198`), MH1/H1S3/H1S4 verify on every boot, H1S1 flashed
2026-08-19 (CS7/8 build) and reflashed 2026-08-20 with the CS1-6-inputs
build on the running app's matrix generation. This machine has direct SSH
to the unit (`app@192.168.1.219`) since 2026-08-20 — the hub-relay era is
over. **Correction to the previous context, which said "both SHARCs
slave-boot from the CM4": that was never evidenced** (2026-08-20
netprobe work) and the 2026-08-21 datasheet reading explains why — the
clock chain was wrong twice over (D10). Treat every pre-08-21 statement
about SHARC behaviour as unproven.

0. **SHARC testing — ✅ DONE 2026-08-21. Both parts boot and run.**
   Root cause = missing SPICMD byte (D14); fixed in `dsp4_boot.py
   --spi-cmd 0x03`. The clock two-part fault (D10) is also fixed and
   scope-verified on the card: ÷2 in the CPLD (`a1f6672af6c3`) + the
   level-shift bodge PW fitted (1k + 330R per DSP, mod BLUE on the mods
   PDF). Damaged-parts verdict WITHDRAWN. Two follow-ups fall out of it,
   now folded into the queue: (a) H1S1's legacy ADAU meter poll bursts on
   the shared !SPI1 net can corrupt boot DATA — near-term firmware fix
   (see item just below P2.2); (b) rev-D boot-bus owner. **PW confirmed 2026-08-21: both DSP blink LEDs visible at the
   expected rates — milestone closed visually (schematic map: LD3=DSPA/
   chip1 1 Hz, LD2=DSPB/chip2 2 Hz; LD1 is the CPLD LED, not a DSP).
   NOTE: on the rev C board these are SILKSCREENED D2/D1 = schematic
   LD2/LD3 respectively — refdes offset, don't re-confuse them.**

1. **P2.2 — REFRAMED 2026-08-21: there is no dma_cfg_init wedge. The
   full firmware has never executed an instruction on this card.**
   Parks inside `dma_cfg_init` AND a park on the first instruction of
   `_start` were all silent; only the ~1 KB blink/rdyprobe images have
   ever run. Root cause found and half-fixed: **the SPI target boot
   kernel cannot take a loader block larger than ~8 KB**, and every
   image so far was built with elfloader's default (one block per
   section). `-MaxBlockSize 0x1000` is now in `build.sh` LDRFLAGS —
   necessary, proven (0/10 → 4/4 on the same 8 KB DXE), NOT sufficient:
   the 208 KB image still does not run, so a second limit above ~8 KB
   is still uncharacterised. **Next step and full evidence: the
   2026-08-21 15:0xZ outcome at the top of this file.** Everything
   below this line is the 2026-08-20 desk review, kept because the
   `sport_dma_base()` fix in it is still correct — but it is UNTESTED
   on hardware and was never what hung, because nothing in
   `dma_config.c` has ever been reached.

   **(superseded framing, 2026-08-20 desk review)**
   - **The SPORT DMA channels are not one contiguous block, and the two
     blocks are not adjacent in the MMR map** (HRM Table 27-2 "ADSP-2156x
     DMA Channel List", Table 23-6, and `sys/ADSP-21564.h`):

     | half-SPORT | DMA channel | MMR base |
     |---|---|---|
     | SPORT0-3 A/B | DMA0-DMA7 | 0x31022000 + (2n+dir)·0x80 |
     | — | DMA8/DMA9 = MDMA0_SRC/DST | 0x310A7000 (different SCB node) |
     | SPORT4-7 A/B | DMA10-DMA17 | **0x31023000** + (2(n-4)+dir)·0x80 |

     `arm_region()` used `0x31022000 + (2*sport + dir)*0x80` for every
     lane, which is right only for SPORT0-3. From SPORT4 up it wrote
     0x31022400, 0x31022480, … — **unpopulated MMR space just past
     DMA7**. An SCB access there never completes, and the core stalls on
     its next MMR access: exactly the observed 1-flash hang. Chip 1's
     region A carries SPORT0-7, so it dies on lane index 4 (SPORT4)
     *inside* `arm_region(A)`, which is where the round-1 park says it
     dies. Chip 2 reaches SPORT4 in its region B (`c2_tx` lane index 4).
   - **Fix applied** (`dma_config.c`): `sport_dma_base(sport, dir)`
     picks the right base and half index; verified for all 16 half-SPORTs
     against the vendor header. Compiles clean for both CHIP_IDs.
     `dsp4-plumbing.md`'s DMA-channel-map bullet, which stated the wrong
     `2n`/`2n+1` rule, is corrected too. **Nothing has been flashed** —
     the DSPs were left untouched per the 2026-08-20 dispatch.
   - **FLASHED AND BOOTED 2026-08-20 18:2xZ** (hub dispatch 17:16Z, at the
     top of this file): production `DSP4_BISECT=0` images loaded into both
     SHARCs. **Readback still all-zero on both chips — P2.2 NOT verified.**
     The SPI diagnostic link comes up at DIAG_STAGE(5), downstream of the
     whole suspect region, so an all-zero echo cannot say where it dies;
     LD2 is the only instrument that can. The SPORT4-7 base fix itself was
     re-verified against `sys/ADSP-21564.h` and is correct.
   - **Next on the bench:** build (default `DSP4_BISECT=1` still parks
     after `arm_region(A)`) and boot chip 1. If LD2 now shows the steady
     1 Hz square, the wedge is closed — then `DSP4_BISECT=2` (park after
     B), then `DSP4_BISECT=0` for a full run. PW's LD2 read on the
     CURRENT image is still useful as a before/after datapoint but is no
     longer a gate.
   - Suspects cleared by the same review, for the record: **descriptor
     alignment** is fine — the HRM requires only 32-bit alignment for
     descriptor sets ("Descriptor Set Address Alignment"), `DMA_ADDRSTART`
     only needs MSIZE alignment (MSIZE04 = 4 bytes, and the buffers are
     `unsigned int` arrays), and the descriptor element order
     {DSCPTR_NXT, ADDRSTART, CFG, XCNT, XMOD} matches the MMR order at
     +0x00/04/08/0C/10 that NDSIZE=5 fetches. **DMA_CFG.EN write order**
     is already legal — `DMA_OFF_DSCPTR` (0x00) *is* `DMA_DSCPTR_NXT`,
     which is precisely what "Startup Minimum-Enable Requirements"
     requires be written before `DMA_CFG` for descriptor-LIST flow. The
     `DSP4_BISECT=3` variant keeps the EN-last experiment available
     anyway. **The lane-4/cs-mask special case** was the right instinct
     pointing at the wrong mechanism: lane index 4 is where it dies, but
     because that lane is SPORT4, not because `cs_mask = 0x000D` is
     non-contiguous.
   - Real fix already applied (KEEP): `arm_region` converts every
     DDE-visible address core-L1 → SYSTEM via inlined `l1_to_sys()`
     (+0x28000000 for 0x00240000..0x003FFFFF; ADI libcc math). The hang
     persists at sub-step ≤4 after it — SPI2 diag readback still all-zero
     echoes.
   - Temp instrumentation in the tree (REVERT when done): `diag_stage_set()`
     stamps 1..7 in `dma_cfg_init` + `_diag_stage_set` helper in
     `diag.asm` + the park loop — now all behind `DSP4_BISECT` (0 =
     production, no park and no stamps; see item 3). Chip 2 runs the
     fixed un-instrumented build (hung, harmless).
   - Flash/boot loop, all runnable from here now: build → scp `.ldr` to
     `app@192.168.1.219:/home/app/dspboot/` → S_RESET `*` on
     `/dev/serial0` (hold slaves; matrix-app stopped) → `dsp4_boot.py
     --dir /home/app/dspboot` → observe/readback → app restart.
   - Boot-tool quirk (re-boot from a RUNNING/hung state fails its first
     attempt on an SPI_RDY timeout and works on the immediate retry,
     ×3): **auto-retry added 2026-08-20** — `dsp4_boot.py` now takes two
     attempts per chip by default (`--attempts` to override), logs both,
     and never re-pulses `!RST_D` on the retry. **EXPLAINED 2026-08-20
     18:2xZ: the quirk was the inverted SPI_RDY polarity** (boot kernel is
     fixed active-LOW, HRM ch.40; the tool waited for HIGH and only ever
     "passed" because H1S1 drove the shared CS3/CS4 nets high until the
     CS1-6-inputs reflash). Polarity corrected; both chips now boot on
     attempt 1/2. The retry is kept — it costs nothing and keeps a part
     that genuinely needs it visible. Full write-up in the 17:16Z
     dispatch block, including the rev-D item: **R34/R22 are pull-DOWNS
     where the HRM's in-reset hold-off needs pull-UPS.**
   - Before any slave boot with H1S1 flashed: confirm !RST_D ownership
     (H1S1 PA13 = `!RST_D` vs the boot script's GPIO16 pulse). Checked
     2026-08-20: GPIO16 read 1 (released) throughout, and H1S1 does not
     drive the line — the Pi owns it in practice.

2. ~~**Flash H1S1.**~~ **DONE 2026-08-20** — full evidence in the
   dispatch outcome at the top of this file. Reflashed with the
   CS1-6-inputs build compiled against the running app's generation
   (`matrix-aligned.h`, full-id `e80ccab5d6d8`); all eight CS pins
   `GPIO_MODE_INPUT` in the disassembly; `app cli loadfw H1S1` clean;
   H1S1 + SW Left + SW Right all verify on reboot.
   **Correction to the earlier wording here: H1S1 had NOT "never been
   flashed"** — the hub flashed a matrix-aligned CS7/CS8-only build on
   2026-08-19 night (`logs/flash.log` ends 18:24Z, and all three MCUs
   have verified at every boot since). What the 2026-08-20 reflash
   superseded was that CS7/8-only image.
   Still open from this pass: H1S1's blink handler issues `DspTx(...)`
   SPI1 writes for CS1-8 every S_BLINK edge (dead ADAU-era LED writes —
   they select nothing now that CS1-6 are inputs, but they still clock
   the housekeeping bus). Delete them at the next H1S1 pass.

3. **Clear the bisect scaffolding in `dma_config.c`** once P2.2
   concludes — it is all behind `DSP4_BISECT` now (`DSP4_BISECT=0`
   already compiles the clean production path), so the deletion is
   mechanical: drop the `DSP4_BISECT` block, `DIAG_STAGE`, the parks,
   the `build.sh` passthrough, and `_diag_stage_set` in `diag.asm`.
   `bca0dde`'s deliberate `for(;;)` park + diag stamps go; the
   `l1_to_sys()` fix and the `sport_dma_base()` fix STAY. No image is
   shippable before this.

4. **dsp4_config.py — next tool up** once the wedge clears: expect LED
   stage 5 (waiting for host product config) → configure → stage 6 →
   audio → steady 1 Hz. Procedure + failure signatures:
   `MW/D32/DSP/diagnostics.md`. (Sync back from `/home/app/dspboot/`
   is DONE 2026-08-20 — `dsp4_config.py` was the only one that had
   drifted; see the dispatch outcome for the two rough edges in that
   gpiod-v2 port that are worth tidying when the tool is next used.)

5. **SPORT I/O pin check via CPLD feedback loop (PW 2026-08-20).** A
   loopback build of the LOGIC bitstream (STA-gated, hash-named, clearly
   NON-SHIPPING) routes SHARC SPORT outputs back to inputs so the DSPs
   self-verify EVERY SPORT pin/lane end-to-end: firmware counter-pattern
   generator + checker per lane, verdicts via the 0xE000 diag readback.
   Also closes the provisional TDM facts without a scope (BCKI/FSI pair
   order, CKRE/MFD, D24 within-ADC8 slot order) and settles the NI0-3/
   NO0-3 crossed-direction/reversed-index question against slot-map.csv.
   Gate: wedge fix verified on the bench + SPORTs configured (stage 6).

6. **Unified D24/D32 SPORT/TDM lane map (PW, decided 2026-08-20 — full
   detail + resolutions in mx26 tasks.md "decisions queue"):** rev C =
   converters 4×TDM8/direction as fabbed; rev D = 2×TDM16/direction via
   AK5558 cascade (TDM512 @48k/24.576 MHz, datasheet-verified; clkgen
   must pin BICK↓ vs MCLK↑ ±10 ns for cascaded slaves), freeing two
   lanes/direction; 1×TDM8 AK4619; Pi lane I2S→TDM8 with ADAU7302 MEMS
   injection at slots 5-6 (chip already strapped TDM8-slot-5, R42=47K);
   ONE TDM32 pair for the network role — OUT lane broadcast to USB +
   Dante simultaneously, IN lane single granted driver with enforced
   tri-state defaults (grant toggle = virtual soundcheck), D32 snake =
   the AES67 role on the same pair. Lands as tdm-lines.csv/slot-map
   revision + rev-D modlist entries. Open: 570Z scratch-fit for the
   freed pins/LEs; AK4458 slot-select check; D32_COMPAT legacy-box
   yes/no (PW). See also the D8 amendment (CM4 masters mic-pre gain;
   CS_M via spare CS5/6) in dsp4-architecture-decisions.md.

7. **Bench observations owed (PW):** LD1 ~1.5 Hz with the CPLD live;
   TEST1-4 on the scope (J15 DNP pads); blink-image rate = free CCLK
   measurement — write the measured rate down, don't just retune.

8. **Design note queued (PW 2026-08-19):** once RUNNING, the DSP diag
   LED and LOGIC LD1 should sync to the MH1 S_BLINK system heartbeat
   rather than free-run; diagnostic burst codes stay local.

## Blocked on PW (decisions, not work)

- **UART pass-through routing matrix** (`TODO(uart-passthrough)`):
  buffered pass-through vs selectable mux vs strobed arbiter. Pin
  inventory done; system decision needed before RTL. Audio bring-up
  only — not on the panel path.
- **D9 sign-off** (`dsp4-architecture-decisions.md`, [DRAFT] since
  2026-08-06): FPGA param plane — float wire, on-fabric ingest
  conversion, fixed ramps.
- **KR260 order** (SK-KR260-G; Farnell £323.57 vs ~$431 elsewhere,
  prices 2026-08-06). Procurement ONLY — the 2026-08-07 gate stands: no
  FPGA engineering until stable DSP+LOGIC on rev C. Capture order # +
  ETA here.
- **AI-attribution history question** — recommendation stands: LEAVE IT
  (59 pre-mandate commits keep trailers; rewriting means force-pushing
  new SHAs under ~15 cross-references). New commits carry none.

## Standing reference (condensed — full history in the archive)

**Lanes (2026-08-07 set):** (1) LOGIC CPLD — on hardware since 08-18;
unused-pin root cause fixed (`RESERVE_ALL_UNUSED_PINS` primary was unset
— every prior build ground-drove unused pins; trap documented in the
qsf), `fd6a5ec69198` flashed + regression-passed 08-19. (2) DSP firmware
— both SHARCs boot; six would-be-fatal bugs already found by HRM review
(IVT SEC vector, wrong SPI port, RUWM, EMISO, TXCTL, SEC ack); P2.2
wedge in progress. (3) FPGA — procurement only, gated.

**Card signs of life:** LD1 = LOGIC pin 59; LD3 = DSPA `PA_12`; LD2 =
DSPB `PA_12`; `PA_13` = shared `!BLINK` net (input — never drive).
TEST1-4 = CPLD pins 13/12/8/7 → J15 (DNP DIL254-10: pins 1/2 +3V3, odd
GND, even TEST1-4). LED fault codes: N flashes = completed stage N,
stuck in N+1 (1 SRU, 2 SPORT, 3 DMA, 4 int-enable, 5 waiting host
config, 6 configured/no audio); healthy = steady 1 Hz square. Diag
readback block at 0xE000 (24 regs + generic MMR peek window) via
`dsp4_diag.py` — the emulator substitute; every read carries an echo
word, checked host-side. SPI_RDY: chip1 GPIO8, chip2 GPIO12, FCPL=1
(ready = high; the 10K pulldown means in-reset reads not-ready). No
SHARC JTAG on rev C (JTG_* float; rev-D item — 2-pin SWD per chip is the
cheap option, ADI-tooling support unverified).

**Boot path:** CM4 SPI2 slave boot, BMODE 0b010; CS1/CS3 = DSPA, CS2/CS4
= DSPB (CS2 = GPIO24, NOT GPIO7); `!RST_D` = GPIO16 — ONE reset line for
BOTH DSPs (a reset re-boots both); 1024-byte units; spi0-0cs overlay (no
CE pins — GPIO7/8 stay JTAG TCK / CS3-RDY1). `dsp4_boot.py` = gpiod v2.
CM4 CPLD JTAG: TCK=GPIO7 TDO=22 TDI=23 TMS=25, IDCODE 0x020a30dd.

**Build:** `./build.sh all` in `MW/D32/DSP/SHARC/` (native 21564;
fit-proxy retired). Scratch copies need `cp -aL` — `Core/Inc/matrix.h`
is a symlink into `MX/` and plain `cp -a` leaves it dangling. H1S1/panel
MCU builds: Dropbox FW home via `Debug/makefile.linux` (CM4 or here);
access Dropbox through the space-free symlink `~/db` (escaped spaces
stall dispatched sessions).

**CCES licence (AD-CCES-NODE-1):** a node-locked activation COUNTER —
4 max, no customer-side release (ADI case CS-601771-T5L1J6); 1 of 4
spent on this box; a wipe or NIC change burns one permanently. Licence
material untracked in `cces-tools/` (gitignored); originals in Dropbox
`TransferOnly/`.

**Rev D:** single mod source = Dropbox
`TransferOnly/PCB mods/dsp4-revD-modlist.md` (D8 scope: CM4-core SPI
control; supervisor shrink → G0B1/U535; PSRAM on OSPI0 + runtime link to
SPI0/1; 5M570Z CPLD — PIN_8/TEST3 must move; hardwire-chunk pass;
OSPI = 3.3 V domain → S27KL-class HyperRAM or APS6404L). Rev-C bring-up
verifies the provisional TDM facts (BCKI/FSI pair order, CKRE/MFD, D24
within-ADC8 slot order, S4 strap) → then rev-D freeze. CPLD-driven
SWD_EN3 = rev-D wiring candidate (SPARE reaches neither CPLD nor U7 in
rev C).

**MCU hygiene notes:** MH1 `'?'` responder is pre-loop only (S_RESET
before `loadfw`; proper fix = `'?'` in the ISR dispatcher). CheckS
unbounded ready/BUSY spin-waits + the blocking-HAL-read-in-ISR pattern =
rev-D firmware hygiene (patched on MH1/H1S3/H1S4 2026-08-19 — audit
other CubeIDE projects before reuse).

**Cross-repo:** Dropbox `_Matrix` = canonical cross-repo store (absorbed
as `matrix-shared-store.md`); mx26 checkout at `~/mx26` for contract
syncs (`git -C ~/mx26 pull` first).

## P3 — contract evolution (waiting on mx26)

- Tier-2 slots staged in `defs.lock` (`D24_DSP_CFG_SHA256`,
  `D32_DSP_CFG_SHA256`, ABSENT until mx26 provides dsp.csv files).
  Resume: when mx26 adds `src/pd/d24/dsp.csv` or `src/pd/d32/dsp.csv`,
  run `./regenerate-dsp-contract.sh --update-lock`.
- FPGA mixer engine for larger products — idea folder seeded
  (`fpga/README.md`, `fpga/node-portability.md`); activation gate:
  becomes a numbered architecture decision first.
- `mx_master.csv` as cross-domain SOT — deferred; notes in `ideas.md`.

## Done (foundation, collapsed)

- Contract pipeline complete: defs.lock, sync-from-mx26.sh, hash
  verification, validate-matrix-contract.py, regenerate-dsp-contract.sh,
  check-contract-drift.sh, release-notes convention, smoke checklist.
- Alias retirement complete (2026-07-18); DSP mapping gap closed
  (349 cells added upstream).
- Fixed-point conversion (D5) COMPLETE 2026-07-31 — mainline is Q4.28;
  float archived at tag `float-kernels-2026-07-31`; golden harness 9/9.
- Fabric remap + product-config boot block + plumbing slices 1-3 DONE
  2026-07-31; diagnostics instrumentation DONE 2026-08-12.
- D24 schematics imported + hardware map derived
  (`MW/D24/HW/hardware-map.md`); binding decisions D1-D8 in
  `dsp4-architecture-decisions.md`.

## Workflow reference

| Command | Purpose |
|---|---|
| ./regenerate-dsp-contract.sh | Full sync + validate + generate |
| ./regenerate-dsp-contract.sh --update-lock | Same but bumps defs.lock hashes |
| ./check-contract-drift.sh | Pre-merge check |
| ./check-contract-drift.sh --strict | Strict gate — fails on any unintended drift |
| python3 audit-compat-aliases.py | Refresh alias-audit.md |
| python3 validate-matrix-contract.py | MxAdd continuity + family allowlist check |

## State snapshot (2026-08-20)

- Contract: defs-v2026.08.20 (mx26 `345470a`) — first pin on the clean
  5161-cell post-naming-pass D24 master; D24 _matrix 5125 rows, D32 6940.
- Firmware: unified DSP4 per dsp4-architecture-decisions.md; ~75-80%
  written, hardware-verified fraction low — bring-up is the work.
- Hardware: rev-C card live; SHARCs boot; dma_cfg_init wedge = the one
  open blocker on the audio path.

## Owners and cadence

- Owner: DSP workflow maintainer (dispatched sessions + PW bench).
- Review cadence: update on every contract bump and when NOW items move.

### Outcome 2026-08-23 04:3xZ — rung 1 DONE and verified; rung 2 BLOCKED on rung 0, with the evidence rung 0 was missing

**Rung 1 is complete.** All four facts closed by measurement over the
loopback bitstream — see `MW/D24/HW/hardware-map.md` for the tables and
`55092e0` for the firmware. Summary: lane index identity (DSPB O(n) →
DSPA I(n), n = 0..4), within-TDM8 slot order identity 0..7, BCK/FS pair
order correct (every word aligned at its own slot), sample edge / MFD
correct (the `0x5A5A` signature intact — a one-bit shift would read
`0xB4B4` or `0x2D2D`). The decisive case is receive lane 4, whose
channel-select mask `0x000D` picked exactly slots 0, 2 and 3 out of a
transmitter driving all eight, which pins the numbering as absolute
rather than merely consecutive.

**Rung 2 is blocked, and not on anything rung 2 owns.** It needs the
audio graph running, which needs `CONFIG_COMMIT`, and after the 51-write
config the parameter link is left **permanently out of phase**:

| | |
|---|---|
| before config | every diag read clean, `BOOT_STAGE 5`, 1500 blocks/s |
| after config | reads return `0x20260812` (`BUILD_ID`) for a `MAGIC` request |
| recovery | none — 10 consecutive read attempts, all out of step |

Stated plainly because an earlier reading of mine said otherwise: the
part is **not** dead and it is **not** starved. It answers; the answers
are simply shifted in the response stream, and `dsp4_diag.py` correctly
rejects them on the echo check, which is what made it look silent. That
is exactly the fault **rung 0** ("make every accepted transaction queue
exactly one two-word answer") was written to fix. Rung 0 was parked as a
protocol nicety; it is not one. It is the gate for every operation past
`CONFIG_COMMIT`, and therefore for rung 2.

**Tried and reverted:** moving the SPI poll from the main loop into the
1 kHz diag timer ISR, on the theory that block processing was starving
the loop. It broke the link outright — no answers even *before* config —
so it proves nothing and was not kept. The tree is back at the verified
rung-1 build and rebuilds to the same md5s (`7aa4f88…` / `89d314f…`).

**Also found, and it cost a wrong reading first — `dsp4_boot.py` can
silently leave chip 2 running CHIP 1's firmware.** It still prints
`booted 2 chip(s)`, warns `92% unsynced collision risk`, and the part
answers on chip 2's select with `CHIP_ID 1`. In that state chip 1's
receive lane 0 showed a 16-slot stream — which looked exactly like a real
slot-map fault and was not. It recurred twice more during the session.
**Read `CHIP_ID` off both parts before believing any bench measurement.**
The giveaway is identical `ADDRSTART`/`XCNT` on both chips: the two
images have different lane geometry and cannot legitimately match.

**Recommended next order:** rung 0 first (it is now evidence-backed, not
a nicety), then rung 2, then the queued blocks. Worth folding the boot
collision into the same pass — a `CHIP_ID` check inside `dsp4_boot.py`
with an automatic retry would have saved this session an hour.

**Bench state:** SHIPPING bitstream `dsp4_logic.a1f6672af6c3` restored and
verified; both chips booted on the production build (`caf6fd6c…` /
`290e9600…`) with `CHIP_ID` confirmed 1 and 2, running 1500.0 blocks/s,
`SPORT0_ERR_A 0x00000000`, `DMA0_STAT 0x00006200`; `matrix-app` active;
all three MCUs verified; GPIOs returned to `a0`.

### Outcome 2026-08-23 05:4xZ — rung 0 DONE and proven; the post-CONFIG_COMMIT death bisected to two faults, one fixed

**Rung 0 delivered, exactly as specified.** Every accepted transaction now
queues one two-word answer — reads `(echo, value)`, writes `(echo, 0)` —
so the master's transaction stream and the answer stream advance in
lockstep and cannot drift. Proof, `tools/pi/dsp4_roundtrip.py`:

    chip 1: 200 write/read round-trips, 0 wrong-value, 0 out-of-step
    chip 2: 200 write/read round-trips, 0 wrong-value, 0 out-of-step

The hub's read of the two earlier failures was right: they predate the
stale-word recovery, the polled link and the TFIFO NOP separation, and
with those in place the design worked first try. The echo comes from
`_spi_req_word`, not `r0`, because every write path between the drain and
the responder clobbers `r0`. The host-side realign fallback was built as
well (`SpiLink.realign`, `REALIGN_TRIES`) and is kept — but it is not what
made this work, and it did not rescue the fault below.

**The post-CONFIG_COMMIT death was NOT a phase problem at all**, which
answer-every-transaction is what proved: with every transaction echoing,
any handler entry would have shown an echo, and instead every read came
back `0x00000000`. The answers were not being produced.

#### Bisect, all other things equal

| build | result |
|---|---|
| 50 config data writes, no commit | healthy, `BOOT_STAGE 5`, blocks arriving |
| + `CONFIG_COMMIT` alone (one write) | **dead** |
| block work off, commit applies off, **idle on** | **dead** |
| block work off, commit applies on, **idle off** | healthy, `BOOT_STAGE 7`, 1500/s |

**Fault A — `idle`, now FIXED.** `.main_loop` opened with `idle` as a
low-power wait for the DMA interrupt, and it wedged the link the instant
the loop was entered — i.e. the instant `CONFIG_COMMIT` released
`.wait_boot`. `.wait_boot` spins; `.main_loop` slept. That is the entire
reason the card looked dead after configuration and healthy before it.
Not the config data, not `_rx_patch_apply`, not `_scope_gates_apply`, not
the block loop, and not the host.

**Fault B — the generated scatter/gather, localised, NOT fixed.** With the
idle gone the production path still wedges, and `DSP4_BLOCK_STAGE` puts it
in one place:

| `DSP4_BLOCK_STAGE` | contents | result |
|---|---|---|
| 1 | consume the block, do nothing | healthy |
| 2 | + `_scatter_chipN` / `_gather_chipN` | **dead** |
| 3 | + `_chipN_process_all` | **dead** |

So it is `_scatter_chip1` / `_gather_chip1` in the generated
`block_io.asm`, not the node graph. That is the next item and it is a
narrow one. The three build guards (`DSP4_BLOCK_STAGE`,
`DSP4_COMMIT_STAGE`, `DSP4_NO_IDLE_OVERRIDE`) are kept for it.

**Also done on the way, and required regardless:** `l2_clear()` zeroes both
L2 delay-line ranges at startup. The LDF says in as many words that
firmware must do this — `sec_delay`/`sec_delay_ovf` are `NO_INIT` to keep
the boot stream inside what the DSP boot bus tolerates — and nothing did,
so the delay lines came up holding whatever was in L2. It did **not** fix
either fault above; it closes a documented gap.

**Rung 2 still not started.** It needs `BOOT_STAGE 7` with real block I/O,
which is exactly what fault B blocks.

**Bench state:** SHIPPING bitstream `dsp4_logic.a1f6672af6c3` on the CPLD;
both chips booted on the production build (`5d310924…` / `1cdd94e9…`),
`CHIP_ID` confirmed 1 and 2, `BOOT_STAGE 5`, 1500.0 blocks/s,
`SPORT0_ERR_A 0x00000000`, `DMA0_STAT 0x00006200`; `matrix-app` active,
all three MCUs verified; GPIOs returned to `a0`.

### Outcome 2026-08-23 07:1xZ — the block loop is FIXED; the remaining hang is the compressor's gain computer

Two real bugs found and fixed since the last outcome, and the post-config
hang is now narrowed to a single routine.

#### FIXED — the sample loop ran ~610,000 times per block

`.cN_sample_loop` kept its 32-sample bound in `r6`, and **both**
`_scatter_chipN` and `_gather_chipN` load the active DMA buffer address
into `r6` (~`0x95350`). So the compare tested the sample index against a
buffer address. Not a fault, but indistinguishable from one. The loop
already reloads `r5` from `_sample_idx` two lines earlier for exactly this
reason; `r6` was missed.

With that fixed, and using `DSP4_BLOCK_MASK` (1 = scatter, 2 = node graph,
4 = gather) under a harness that **requires `BOOT_STAGE >= 6`**:

| mask | contents | result |
|---|---|---|
| 1 | scatter only | STAGE 7, 1500.0/s |
| 4 | gather only | STAGE 7, 1500.0/s |
| 5 | scatter + gather | STAGE 7, 1500.0/s, **`BLK_OVERRUN` 0** |
| 7 | + node graph | dead, reproducibly |

`BLK_OVERRUN` 0 is the result worth keeping: with both halves of the block
I/O running, the main loop now keeps up with **every** block.

#### Method note that cost two wrong readings

A bench check that only asks *"did the link answer"* gives **false
passes**. `CONFIG_COMMIT` does not always land, and a part still sitting at
`BOOT_STAGE 5` answers perfectly well because `.wait_boot` was never left.
Any harness must require `BOOT_STAGE >= 6` **and** non-zero `TICKS` before
it is entitled to call anything healthy. Both "MASK=5 hangs" and "gather
alone survives" were artefacts of not doing that.

#### NARROWED — `_compgain_fx`, and it is value-dependent

`DSP4_NODE_LIMIT` turns the flat 431-call chain into a binary search:
limit 5 alive, limit 6 dead. Index 5 is `_C1_COMP_01_process`. Bypassing
it (`_comp_on = 0`) makes limit 6 alive. Skipping the block-rate parameter
conversion does **not** help, so it is the per-sample path, and
`_compgain_fx` is the one library routine the compressor reaches that the
gate at index 4 does not. Stubbing it to unity: alive.

Below that the stubs stop isolating anything, and that is the finding:

| stub | result |
|---|---|
| `_exp2q_fx` | still dead |
| `_log2q_fx` | **alive** |
| `_polyq_fx` (called *by* log2q) | still dead |

If this were a plain bad-address or bad-instruction fault, stubbing log2q
and stubbing polyq would implicate the same code. They do not. Each stub
also changes the **values** flowing through the rest of the chain, so what
these show is that the failure is value-dependent inside the compgain
chain — not that any one routine is structurally wrong. More blind stubs
would be guesswork.

Two things worth knowing for the next pass:

- The gate at index 4 calls `_log2q_fx` too and is fine, because its call
  sits behind a threshold that silence never crosses. The compressor
  reaches the log2 path with whatever the inputs are actually delivering,
  so the input range here is not a designed one.
- It is **not** about floating inputs. Re-tested with the loopback
  bitstream, where DSPA's inputs are driven by DSPB rather than
  unterminated: same hang.

Also fixed, correct regardless, and **not** the cause: `_comp_knee` was the
only compressor parameter emitted with no initialiser, and it is read
before it is ever written — it feeds `recips` and the knee coefficients.
Now `0.0` (hard knee) in the generator, across all 42 compressor nodes.

**Rung 2 still blocked.** It needs `BOOT_STAGE 7` with the node graph
running, which is what this last fault prevents.

**Bench state:** SHIPPING bitstream `dsp4_logic.a1f6672af6c3` restored;
both chips on the production build (`397c608c…` / `ccf5899d…`), `CHIP_ID`
confirmed 1 and 2, `BOOT_STAGE 5`, 1500.0 blocks/s, `SPORT0_ERR_A`
`0x00000000`; `matrix-app` active, all three MCUs verified; GPIOs `a0`.

### Outcome 2026-08-23 08:3xZ — RETRACTION: the compressor identification was wrong. Build flags were not reaching the assembler.

**Retracted: `_C1_COMP_01` / `_compgain_fx` are NOT identified as the fault.**
The previous outcome named them on the strength of a stub bisect. That
bisect was invalid.

**What went wrong.** The `DSP4_STUB_*` defines were appended to `build.sh`
by a string replace against a copy of the `ASMFLAGS` line that no longer
matched (two other flags had been appended in between). The replace
silently did nothing and I did not assert on it, so **none of the stub
defines ever reached `easm21k`**. Every stub build produced the *same*
image — md5 `50a6c9d5` throughout. The alive/dead differences I recorded
were bench flakiness, not the stubs.

Caught by md5-ing the image across a flag change, which is the rule that
already exists for dump readings and which I should have applied here:
**if a build flag changes and the image md5 does not, the flag is not
reaching the tool.** `build.sh` now passes all four stub defines, verified
by the md5 changing.

**Re-tested with the flags actually working, and the picture is different:**

| build | runs | result |
|---|---|---|
| production, full node graph | 6 | **0 alive** |
| production, 40 patient reads over 40 s after commit | 40 | **0 answered** |
| `DSP4_BLOCK_MASK=5` (scatter+gather, no node graph) | 4 | **4 alive** |
| `DSP4_NODE_LIMIT=1` (one node) | 3 | **3 alive** |
| stub `_compgain_fx` to unity, full chain | 2 | **0 alive** |

So `_compgain_fx` is exonerated — stubbing it changes nothing. And
`DSP4_NODE_LIMIT` 5 vs 6, which is what pointed at the compressor, does
**not** reproduce: limit 5 came back DEAD twice on re-test having been
ALIVE before, and limit 6 came back ALIVE once and DEAD three times.

**What is solid, with repeats:**

- The core genuinely STOPS after `CONFIG_COMMIT` with the full graph —
  0 of 40 reads over 40 s. Not starvation: the 1 kHz timer-ISR backstop
  would have answered at least once.
- Without the node graph the card is reliably healthy: 4/4 at
  `BOOT_STAGE 7`, 1500.0 blocks/s.
- One node is reliably healthy: 3/3.
- Somewhere between 1 node and 431 it becomes marginal and then dead, and
  the marginal region does not give a stable answer to a single-point
  test.

**Also corrected:** the previous outcome claimed `BLK_OVERRUN 0` for
scatter+gather. That was the stale image. The real figure is ~8590
overruns against ~17220 blocks — the loop keeps up with roughly every
*other* block, before a single node has run. That is a useful number in
its own right and it reframes the remaining fault: the per-block budget is
already half spent on block I/O alone.

**What stands unchanged:** the `r6` loop-bound fix is a real code defect,
readable in the source — `_scatter_chipN` and `_gather_chipN` both load
the DMA buffer address into `r6` while `.cN_sample_loop` used `r6` as its
sample bound. Rung 0 (200 round-trips, both chips, zero slips) and rung 1
(TDM slot map) were direct repeated measurements and are unaffected.

**Next, and it needs the harness fixed first:** a single-point alive/dead
test is too noisy to bisect on. Give each point N repeats and a pass rate
before drawing any line. Then find where the pass rate falls off between
1 and 431 nodes, and check the per-block cycle budget directly rather than
inferring it — with block I/O alone already missing half the blocks, a
cycle-budget explanation deserves testing before another node hunt.

**Bench state:** SHIPPING bitstream; both chips on the production build
(`5b1c164e…` / `08673015…`), `CHIP_ID` confirmed 1 and 2, `BOOT_STAGE 5`,
1500.0 blocks/s, `SPORT0_ERR_A` clean; `matrix-app` active, three MCUs
verified; GPIOs `a0`.

### Outcome 2026-08-23 09:5xZ — ROOT CAUSE: the node graph is ~16× over the per-block cycle budget

Not a defect in any node. **Capacity.**

#### The harness first, because the last conclusion was wrong for want of one

- `main.asm` carries `_build_flags`, a stamp encoding every bisect define.
  `bisect.sh` computes the expected value and the bench side **peeks it
  off the running part** and aborts on mismatch. That closes the loop
  through assembler, linker, loader and boot — the exact gap that let four
  `DSP4_STUB_*` defines silently not reach `easm21k`.
- Every point is N repeats and a pass **rate**.
- `DSP4_BLOCK_DECIMATE` runs the graph every Nth block, giving it N times
  the budget **without changing what it computes**. That is what separates
  "a node is broken" from "the graph does not fit" — identical from
  outside, because a main loop that never finishes a block never services
  the parameter link either.

#### Measured, every point stamp-verified

| nodes | decimate | alive / runs |
|---|---|---|
| 1 | 1 | 3/3 |
| 5 | 1 | 0/3 |
| 10 | 1 | 1/3 |
| 15 | 1 | 1/3 |
| 27 | 1 | 0/3 |
| **27** | **8** | **3/3** — same nodes, 8× budget |
| 108 | 1 | 0/3 |
| **431** | **1** | **0/6** |
| 431 | 8 | 1/3 |
| **431** | **16** | **3/3** — full graph, unmodified |
| 431 | 32 | 3/3 |
| 431 | 64 | 3/3 |

The full graph runs clean given 16 block periods and fails given one:

    budget    491.52 MHz / 1500 blocks/s = 327,680 cycles per block
    required  ~5.2 M cycles per block
              ~164,000 cycles per sample across 431 nodes
              ~380 cycles per node per sample

~380 cycles is a plausible cost for this library — a compressor alone runs
an envelope follower plus log2 and exp2 polynomial evaluations per sample.
That is the point: the cost is **real work**, and no amount of node-level
debugging was ever going to find it.

#### And nothing is currently reducing it per product

`_scope_gates_apply` on chip 1 is a **no-op** — the generated body is
`rts; /* no scoped nodes on this chip */`. So all 431 nodes run for D24
and D32 alike, and the measurement above already reflects a committed d24
config. Product gating is not saving anything today.

**This is a design-capacity decision and it belongs to the hub:** fewer
nodes per chip, cheaper nodes, or work moved out of the per-sample loop
(the graph is called once per sample — 431 calls × 32 samples = 13,792
node invocations per block).

**Rung 2 does not have to wait for that decision**, but it cannot be run
as written either: a scorable `aplay`/`arecord` loop needs the graph
passing audio in real time. What *is* reachable now is proving the Pi
capture path with deterministic content — the `DSP4_PATTERN` firmware
puts a known word in every DSPB transmit slot with no node graph
involved, so de-framing one lane/slot to `pcm_din` and capturing it on the
CM4 validates the whole path independently of DSP processing. That is the
next step being taken.

**Bench state:** SHIPPING bitstream; both chips on production
(`eed5183f…` / `4778f022…`), `CHIP_ID` 1 and 2, `BOOT_STAGE 5`, 1500.0
blocks/s, `SPORT0_ERR_A` clean; `matrix-app` active, three MCUs verified.

### Outcome 2026-08-23 11:3xZ — (c) cycle profile DELIVERED; (b) strips knob built, answer is uncomfortable; (a) rung 2 RTL ready, not yet run

#### (c) CYCLE PROFILE — done, in `MW/D32/DSP/dsp4-cycle-budget.md`

Measured with a `TCOUNT`-based instrument (exact to the core clock, not
1 ms-quantised), differenced across `DSP4_NODE_LIMIT` points inside one
strip so each row is a real node running in place:

| class | cycles/sample | share of a strip |
|---|---|---|
| **RTG** | **601** | **30.5%** |
| EQ | 338 | 17.1% |
| FILT | 227 | 11.5% |
| GATE | 204 | 10.4% |
| COMP | 202 | 10.2% |
| DLY | 148 | 7.5% |
| FDR | 128 | 6.5% |
| GAIN | 63 | 3.2% |
| TUBE | 40 | 2.0% |
| IN | 24 | 1.2% |

**RTG — a routing node — is the most expensive class on the part, more
than EQ and COMP together.** That is not where anyone would have looked.
The dynamics maths, which gets all the attention, is not the problem.
Fixed overhead before any strip runs is 44% of the budget: block I/O ~20%
(scatter over 46 channels, gather over 37 sends, 32× per block), buses and
sends ~24%.

#### (b) NODE-ENABLE MASK — built, verified, and the answer is not the one wanted

`DSP4_STRIPS=N` keeps the graph functional (N strips, every bus, send,
cross-in and transfer retained), unlike `DSP4_NODE_LIMIT` which is a raw
prefix cut. 320 strip-guarded calls generated. The flag is verified in the
running image through a second stamp word `_build_flags2`.

**One strip does not hold 1×.** It measures 240,129 cycles/pass = 73.3% of
the budget — by arithmetic it fits — and is still 0 alive / 3.

| configuration | measured load | alive at 1× |
|---|---|---|
| 1 node | 20.0% | 3/3 |
| 10-node prefix | 39.0% | 1/3 |
| `DSP4_STRIPS=1` | 73.3% | 0/3 |
| full graph | 660% | 0/6 |

Reliable below ~20%, marginal ~39%, gone by ~73%. **Roughly a 2.5× margin
is being consumed by something the cycle count does not explain, and I
have not identified it.** Two candidates to separate before anyone sizes a
design against these numbers: the alive/dead test is really a
*parameter-link* test (the link may give out before the audio does), and
interrupt overhead plus overrun compounding, which a per-pass cycle count
cannot see. The per-class table is unaffected by this and stands.

#### (a) RUNG 2 — RTL and tooling ready, bench run not done

- `dsp4_pcm_reframe` gains a capture path: de-frames two TDM8 slots of a
  DSPB output lane into the Pi's L/R I2S on `pcm_din`, launching on the
  PCM BCK falling edge so the Pi samples mid-bit. MFD=1 means slot s bit b
  is on the wire during period (s*32+b+1); the capture undoes that +1.
- The loopback build no longer ties off lane 6 — it keeps `i_dspa[6]` on
  `pcm_tdm`, because otherwise the Pi has no path *into* the DSP and a
  round trip is impossible.
- **Shipping bitstream proven unchanged**: `dsp4_logic.a6e046438eb4.pof`
  is byte-identical to `dsp4_logic.a1f6672af6c3.pof`. Source hash moved
  because the source moved; fitted logic did not.
- New bring-up artefact `dsp4_logic_loopback.b13e772abdbb`, same sim and
  STA gates.
- `tools/pi/dsp4_pcm_capture.py` records the stream and checks it bit-exact
  on all 32 bits against the `DSP4_PATTERN` word, and names a one-bit
  rotation explicitly rather than printing two hex numbers.

Not yet flashed or captured. Latency in samples is **not** obtainable from
the constant pattern alone — it needs a time-varying source, which means
the Pi playback path and therefore a graph small enough to run, which is
what (b) has just shown is not currently available.

**Bench state:** SHIPPING bitstream `dsp4_logic.a1f6672af6c3` restored;
both chips on production (`e7b53db4…` / `a4b8f3b5…`), `CHIP_ID` 1 and 2,
`BOOT_STAGE 5`, 1500.0 blocks/s, `SPORT0_ERR_A` clean; `matrix-app`
active, three MCUs verified; GPIOs `a0`.

### Outcome 2026-08-23 11:5xZ — the hub's call was right: 2 strips run real time; rung 2 blocked on the Pi, not the DSP

#### The "2.5× margin" was the test. Retracted.

Judging aliveness by whether the parameter link answered promptly was
wrong — that link is serviced by **polling from the block loop**, so under
load an answer is a block or more away, which is normal. `DSP4_STRIPS=1`
judged on audio truth instead:

    BOOT_STAGE 7 · FRAME_COUNT 1500/s · DMA0_STAT 0x00006200
    SPORT0_ERR_A 0x00000000 · _proc_passes 1500/s

Real time, every block. Previously recorded as 0 alive / 3.

#### (b) STRIPS CEILING — 2

`_proc_passes` counts completed block passes, which is the honest measure:
`FRAME_COUNT` is incremented by an ISR and advances whether or not the
loop keeps up.

| `DSP4_STRIPS` | passes/s | verdict |
|---|---|---|
| 1 | 1500 | real time |
| **2** | **1500** | **real time — the ceiling** |
| 3 | 1342 | 89%, dropping ~1 block in 9 |
| 4 | 1144 | 76%, over budget |

Two strips against 32 required. The measurement agrees with the cycle
arithmetic (2.9 predicted) to better than one strip, so the profile table
and the bench now corroborate each other.

Two fixes kept, both of which prevent the same class of error:
`dsp4_audio_verdict.py` separates transport from loop and reports UNKNOWN
when the link is silent (distinct from AUDIO_DEAD); and
`dsp4_diag.py.read()` no longer realigns the word phase on the *first*
echo mismatch — it collects patiently first, because the usual cause is
that the DSP has not polled yet. The old behaviour manufactured a fault
out of a slow answer.

#### (a) RUNG 2 — DSP and CPLD sides done; blocked on the Pi having no I2S device

Done and verified on the bench:

- `dsp4_logic_loopback.b13e772abdbb` flashed. Card healthy on it:
  1500 blocks/s, `DMA0_STAT 0x00006200`, `SPORT0_ERR_A` clean.
- **`pcm_din` is live.** GPIO20 sampled 12× asynchronously reads 2 hi /
  10 lo — the CPLD is driving real data on the capture line, and ~17%
  high is the right ballpark for the pattern words 0x5A5A0000 /
  0x5A5A0001 (17 ones in 64 bits = 27%).
- Shipping bitstream restored and re-verified afterwards.

**Blocked, and not on anything in this repo:** `arecord -l` on the CM4
lists no capture hardware at all — only the two HDMI devices.
`/boot/firmware/config.txt` has no I2S overlay. Without a sound card in
the device tree there is nothing to record from, so the bit-exact check
and the latency figure cannot be taken.

What it needs, and why I have not just done it: adding an I2S overlay is a
persistent edit to `/boot/firmware/config.txt` plus a **reboot of the only
bench**, and a bad edit there does not come back over SSH. The overlay
also has to make the Pi an I2S **slave**, since LOGIC masters `pcm_clk`
and `pcm_fs` — that is a choice worth making deliberately rather than
guessing at on a 24/7 unit. The GPIOs do not clash: I2S uses 18-21,
`matrix-app` uses 6-12 and 22-25.

`tools/pi/dsp4_pcm_capture.py` is written and waiting — it checks
bit-exact across all 32 bits and names a one-bit rotation explicitly
rather than printing two hex numbers.

**Bench state:** SHIPPING bitstream `dsp4_logic.a1f6672af6c3` restored;
both chips on production (`e7b53db4…` / `a4b8f3b5…`), `CHIP_ID` 1 and 2,
`BOOT_STAGE 5`, 1500.0 blocks/s, `SPORT0_ERR_A` clean; `matrix-app`
active, all three MCUs verified; GPIOs `a0`.

### Outcome 2026-08-23 12:2xZ — RUNG 2 CAPTURE PATH BIT-EXACT; CM4 I2S provisioning for mx26 below

#### Result

    captured 96000 frames at 48000 Hz from hw:0,0
      left  0x5A5A0000  96000/96000 = 100.00%
      right 0x5A5A0001  96000/96000 = 100.00%
    RUNG 2 CAPTURE: BIT-EXACT PASS

All 32 bits, every frame. A 24-bit check would have hidden the fault
found on the way — see below.

#### CM4 PROVISIONING — for `mx26 scripts/cm4-setup-pi.sh` (SOT)

The unit had **no PCM device at all**: `arecord -l` listed only HDMI. Two
files were added and one line appended; nothing else on the unit changed.

**1. `/boot/firmware/config.txt`** — appended at the end, inside `[all]`:

```
# DSP4 bench: duplex I2S soundcard, Pi as I2S SLAVE (LOGIC CPLD
# masters pcm_clk 3.072 MHz / pcm_fs 48 kHz). Source dts alongside the
# dtbo in this directory. Added 2026-08-23 for rung 2 (pcm_din capture).
dtoverlay=dsp4-pcm-slave
```

Backup of the original is on the unit as
`/boot/firmware/config.txt.bak-20260823-120634`.

**2. `/boot/firmware/overlays/dsp4-pcm-slave.dtbo`** — compiled on the
unit with `dtc -@ -I dts -O dtb`. The source is installed beside it as
`/boot/firmware/overlays/dsp4-pcm-slave.dts` and is committed in this repo
at `shared/dsp4-logic/pi/dsp4-pcm-slave.dts`. **dtbo origin: built from
that dts, not downloaded.**

**Why no stock overlay fits.** `audioinjector-bare-i2s` is the closest and
is wrong twice over: its codec is `linux,spdif-dit`, a *transmitter*, so
it is playback only; and its `bitclock-master`/`frame-master` point at the
**cpu** node, making the Pi the I2S master. The DSP4 card has the CPLD
mastering both clocks, so the Pi must be a slave.

**What the custom overlay does.** Points `bitclock-master`/`frame-master`
at the **codec** side of each link, so `bcm2835-i2s` consumes the external
clocks. Uses **two dai-links** because the dummy codecs are each
one-directional — `linux,spdif-dit` for playback, `linux,spdif-dir` for
capture. 32-bit slots, 2 per frame, matching the 32-bit lane words.

Result after reboot:

    card 0: dsp4pcm — device 0 = capture (dir), device 1 = playback (dit)
    capture formats S16_LE S24_LE S32_LE, 2 ch, rate 8000-768000

Note `i2s_clk_consumer` and `i2s_clk_producer` both resolve to the same
node on this kernel (6.18.34+rpt-rpi-v8), so slave mode comes purely from
the master properties, not from the target label.

#### The fault the 32-bit check caught

First capture read `0xB4B40000` / `0xB4B40002` against transmitted
`0x5A5A0000` / `0x5A5A0001` — the expected words **shifted left exactly
one bit**, 100% stable over 96,000 frames. Left-shifted by one means the
receiver started a bit early, so the capture launch wanted one more BCK of
delay than the playback direction. New parameter `CAP_EXTRA_DELAY = 1`,
measured not guessed. `dsp4_pcm_capture.py` names a one-bit rotation
explicitly instead of printing two hex numbers, which is what turned that
from a puzzle into a one-line fix.

#### Latency — NOT measured, and the reason is not the plumbing

Both Pi directions are proven:

- **DSPB → Pi**: bit-exact, above.
- **Pi → DSPA**: proven directly. Playing a tone into `pcm_dout` and
  peeking chip 1's receive buffer for lane 6 (word `0x958B8`) shows live
  signal data — `0xE95F619A` — where it reads `0x00000000` with no
  playback. The reframer's playback direction and `i_dspa[6]` both work.

The round trip does not close because **the DSP does not route DSPA's Pi
input to DSPB's output**: with a committed d24 config and a 1-strip graph,
a 1 kHz tone in produces digital silence out. That is a matrix
routing/parameter question — the routes are host-written parameters that
nothing in the boot config sets — not a bring-up gap. Latency in samples
needs that route to exist first, so it belongs with the virtual-audio work
in the queued chain rather than with rung 2's plumbing.

**Bench state:** SHIPPING bitstream `dsp4_logic.a1f6672af6c3` restored;
both chips on production (`e7b53db4…` / `a4b8f3b5…`), `BOOT_STAGE 5`,
1500.0 blocks/s, `SPORT0_ERR_A` clean; `matrix-app` active, all three MCUs
verified; GPIOs `a0`. The I2S overlay is persistent and survives reboot by
design — it does not disturb `matrix-app` (I2S uses GPIO 18-21,
`matrix-app` uses 6-12 and 22-25).

### Outcome 2026-08-23 12:5xZ — desk fillers: 1 CLOSED, 2 DONE with numbers, 3 BLOCKED on document access

#### 1. SPI2_RDY — CLOSED, verdict: not usable on this silicon

HRM ch.15: in slave mode `SPI_RDY` is an output and `SPI_CTL.FCCH` picks
the FIFO it follows — 0 = RX buffer ("I can accept"), 1 = TX buffer
("I have data"). The firmware is **already** configured the way the task
hoped to find, read back off a running chip 1:

    SPI2_CTL = 0x0001A501
      EN=1  MSTR=0  FCEN=1  FCCH=0 (RX)  FCPL=1 (active-high)  FCWM=1

It idles high on both chips (10/10; chip 1 GPIO8, chip 2 GPIO12), and high
against the board's 10K pulldown means the pin **is** driven.

It never deasserts. The decisive test clocks one 64-byte transfer with CS
held — 16 words into a 2-deep FIFO, which the DSP cannot drain because it
drains by polling *between* transactions — and samples RDY the instant it
returns:

| FCWM | meaning | RDY low |
|---|---|---|
| 1 | RFIFO ≥ 75% | 0/40 |
| 2 | RFIFO ≥ 50% | 0/40 |
| 0 | RFIFO full | 0/40 |

All three legal values, each confirmed live in `SPI2_CTL` first. A
guaranteed overfill never moves the pin. Corroborating: `SPI_STAT.FCS`
reads 1 constantly with both FIFOs empty and the link idle — FCS is
documented as a *master*-mode stall indication, and permanently set in
slave mode fits a flow-control block not behaving as ch.15 describes.

**No host change made.** The tools already accept `--rdy-gpio` and call
`wait_ready()`; with the pin stuck asserted that never blocks, so it is
harmless but buys nothing and must not be relied on for pacing. rev-D
mod 9 (RDY pull-up) stands. Note the boot kernel uses the opposite
polarity — `dsp4_boot.py` expects RDY **low** during pre-select.

#### 2. 570Z scratch-fit — DONE

`shared/dsp4-logic/quartus/scratch570/` fits the **current** RTL (shipping
configuration) into the smaller part. Correct Quartus device name is
`5M570ZT144C4` — the `N` in `5M570ZT144C4N` is an ordering-code suffix and
Quartus rejects it.

| | 5M570ZT144C4 |
|---|---|
| logic elements | **157 / 570 (28%)** |
| registers | 127 / 570 (22%) |
| pins | **71 / 114 (62%)** |
| headroom | 413 LE, 43 pins |
| worst setup slack | **+0.842 ns** on the 20.345 ns (49.152 MHz) sysclk |
| implied Fmax | **51.27 MHz — only 4.1% margin** |

**Two pins in the current map are illegal on the 570Z in the same T144
package**, and one is exactly the pin the task flagged:

- `mems` on **PIN_137** — illegal; fitter relocated to PIN_58
- `test[2]` on **PIN_8** — illegal; fitter relocated to PIN_11

Those relocations are the *fitter's* choice with no knowledge of the PCB —
they confirm the pins must move and give a legal example, they are not a
layout recommendation.

**The headline for the part decision is timing, not capacity.** The design
uses only 28% of the LEs but leaves just 4.1% timing margin at 49.152 MHz,
where the 5M1270ZT144C4 manifest records 70.21 MHz. The rev-D lane map
adds logic to a design that is already close to the edge on the smaller,
slower part.

**Not assessed: the ±10 ns BICK↓ vs MCLK↑ constraint for the cascaded
AK5558 slaves.** That constraint belongs to the rev-D unified lane map,
and no RTL for it exists — there is nothing to time. What the numbers
above bound is the headroom that map would have to fit into.

#### 3. OSPI clock gate — BLOCKED on document access

The HRM ch.16 is functional, not electrical. It **does** establish:
Octal DDR and DTR protocol supported, up to 16 bits per SPI clock,
programmable dummy cycles, and a "tune data capture mechanism to improve
high speed operation". It contains **no** occurrence of RWDS, HyperRAM,
HyperBus, or xSPI "profile" anywhere — so profile-2 / HyperRAM 2.0 support
is *not* evidenced by the HRM.

The max OSPI clock (133 vs 200 MHz) is a datasheet electrical spec and the
datasheet is not reachable from this machine: not in `_Matrix`, analog.com
times out, the verical mirror returns 403, the Mouser mirror times out,
and the ampnuts mirror only carries the HRM. One search result indicates
OSPI **boot** is capped at 62.5 MHz OSPI clock, which is a boot-mode
constraint and not the interface maximum.

**Ask for the hub:** drop
`adsp-21562-21563-21565-21566-21567-21569.pdf` (Rev D) into
`_Matrix/.../adsp-2156x-docs` and this closes in minutes — the answer is
in "OSPI Port—Master Timing" in the Timing Specifications section.

**Bench state:** SHIPPING bitstream; both chips on production
(`e7b53db4…` / `a4b8f3b5…`), `CHIP_ID` 1 and 2, `BOOT_STAGE 5`, 1500.0
blocks/s, `SPORT0_ERR_A` clean; `matrix-app` active, three MCUs verified.

### Outcome 2026-08-23 13:1xZ — virtual audio: the pass-through LOOP IS CLOSED; calibration to bit-exact is the next step

#### The loop runs end to end

    captured 96000 frames, peak |L| = 0x7BB7C120, SIGNAL PRESENT

Pi `aplay` → `pcm_dout` → reframer → DSPA I6 → `C1_XIN_PI_L/R` →
`C1_XS_XFER_PI_*` → inter-chip → `C2_XR_PI_*` → `C2_PI_IN` → `C2_MIX_MAIN_*`
→ `C2_MAIN_FDR` → `C2_MAIN_DLY` → `C2_MAIN_ST_OUT` → SPORT3 slot 0 →
`o_dspb[3]` → reframer capture → `pcm_din` → Pi `arecord`.

That is the precondition the whole virtual-audio block was waiting on.

#### The two things that were blocking it

**1. The capture was tapping the wrong lane.** `o_dspb[0]` slots 0/1 are
`C2_AUX_OUT_01/02` and carry nothing in a pass-through. The main stereo
output is `C2_MAIN_ST_OUT` → SPORT3 slot 0 → **`o_dspb[3]`** (the CPLD's
`dac_main`). Loopback bitstream now taps that:
`dsp4_logic_loopback.3f488870d6cb`.

**2. The Pi input is gated OFF by default.** `_auxin_on_C2_PI_IN = 0`,
SPI address **0x071D** on chip 2. One poke opens it. Everything downstream
already defaults to unity — mix gains 1.0, `_fdr_level` 1.0, mute 0 — and
the Q4.28 shadows are refreshed at block rate, so they self-populate and
are not a second gate.

#### NOT yet bit-exact — the gain is about 4x

Input tone amplitude `0x20000000`, captured peak `0x7BB7C120`: a ratio of
**3.87**, near enough 2^2 to look structural rather than accidental. Step 1
of this block says stop and find why before anything else is meaningful,
and that is where it stands. Worth noting the scatter/gather Q1.31↔Q4.28
shifts (`ashift by -3` on the way in) as the first place to look, since a
mismatched pair there is exactly a power-of-two error.

Also seen: only ~4.5% of captured frames carry signal, so the stream is
bursty — `aplay` reported an overrun earlier. Playback buffering needs
pinning down before any latency figure is taken, or it will measure ALSA
rather than the DSP.

#### Not started

The harness extension (`--target hw`) and the five kernel families. They
need a bit-exact unity path first, per the block's own instruction.

#### One conflict for the hub to resolve

This block says "leave the pass-through loop soaking when you stop"; the
standing Rules say "the SHIPPING bitstream must be restored on the CPLD
before ending". They cannot both hold — the soak needs the loopback
bitstream on the card. **I restored SHIPPING**, on the grounds that it is
the older standing rule and this is a 24/7 bench others may pick up. Say
which wins and I will leave the soak running instead.

**Bench state:** SHIPPING bitstream `dsp4_logic.a1f6672af6c3`; both chips
on production (`e7b53db4…`), `CHIP_ID` 1 and 2, `BOOT_STAGE 5`, 1500.0
blocks/s, `SPORT0_ERR_A` clean; `matrix-app` active, all three MCUs
verified; GPIOs `a0`.

### Outcome 2026-08-23 13:4xZ — the 4× was MY MEASUREMENT. Path is unity and bit-exact. Duplex streaming on the Pi is the real blocker.

#### The 4× gain does not exist — retracted

Proved with a known word, as instructed, rather than a level:

    in 0x00001000 -> out 0x00001000   ratio 1.0000  = in << 0
    in 0x00010000 -> out 0x00010000   ratio 1.0000  = in << 0
    in 0x00100000 -> out 0x00100000   ratio 1.0000  = in << 0

100% of non-zero frames, three bit positions. **The pass-through is unity
and bit-exact through all 32 bits.** The earlier "3.87×" came from taking
a *peak* out of an overrun-riddled capture — the peak was a glitch, not
signal. A level cannot tell you a shift; the hub's instruction was right
and the answer changed as soon as I followed it.

The shifts are also correct by inspection, which corroborates it:
chip 1 scatter `>>3` (Q1.31→Q4.28), chip 1 gather no shift (inter-chip
stays Q4.28), chip 2 scatter no shift, chip 2 gather `<<3` with
saturation. Paired, no net shift.

#### What actually blocks the vector set and latency: duplex on the CM4

| condition | result |
|---|---|
| capture alone (rung 2, pattern firmware) | **100.00% stable, bit-exact** |
| playback alone into the DSP | arrives — lane-6 RX buffer showed live tone data |
| **playback + capture together** | **scrambled** |

With both streams running, a per-sample counter comes back with values
staying under ~200 across 20,000 frames instead of climbing to 48,000;
dominant step −191; short ascending runs (48,49 / 84,85,86) separated by
jumps backwards. ALSA reports no under/overrun once period/buffer are
pinned (97.6% of frames carry data), so this is not simple buffer
starvation — the *content* is wrong, repeating a small window of stimulus.

**Suspected cause, and it is my overlay's design.** `dsp4-pcm-slave.dts`
creates **two dai-links sharing one `bcm2835-i2s` CPU DAI** — playback on
`linux,spdif-dit`, capture on `linux,spdif-dir` — because those dummy
codecs are each one-directional. That gives two PCM devices but not a true
duplex device, and starting/running one stream appears to disturb the
other. Capture alone and playback alone are each clean; only the
combination is not.

**Fix direction for the next pass:** one dai-link with a codec that
declares BOTH directions, so the card presents a single full-duplex PCM
device, and confirm `bcm2835-i2s` supports concurrent streams at all in
slave mode. That is a device-tree question, not a DSP one — the DSP side
is proven unity and bit-exact.

#### Also found (node graph, worth a hub decision)

**Nothing drives SPORT3 slot 1 on chip 2.** `C2_MAIN_ST_OUT` is the only
node writing SPORT3 and it writes slot 0 only, despite being declared
"Channels: 2". So the capture's right channel is correctly silent. Whether
the main stereo out should drive a second slot is a graph/generator
question.

#### Not done

Latency in samples — deliberately not reported. Every number available
would be dominated by the duplex fault above, and a latency figure taken
through a stream that repeats a 200-sample window would be fiction.

**Bench state:** **LOOPBACK-CAPTURE bitstream
`dsp4_logic_loopback.3f488870d6cb` on the CPLD** (per the 13:0xZ hub
ruling — restore SHIPPING at the end of this block). Both chips on the
`DSP4_STRIPS=1` build, `CHIP_ID` 1 and 2, `BOOT_STAGE 5`, 1500.0 blocks/s,
`SPORT0_ERR_A` clean; `matrix-app` active, all three MCUs verified;
GPIOs `a0`.

### Outcome 2026-08-23 15:0xZ — harness families BLOCKED: ramped parameter writes land one word low

Latency delivered (93 samples, see `dsp4-plumbing.md`). The first family,
GAIN, then hit a firmware bug that blocks every family needing a parameter
write.

#### The double bind

**A direct write to a ramped parameter does nothing.** `C2_PI_IN`'s
block-rate code is `if frames <= 0: level = target`, run every block, so a
`ramp_id = 0` write to `_auxin_level` is overwritten within one block
period. Measured: a full −60…+18 dB sweep produced *identical* output at
every setting.

**And the ramped write is broken.** Writing `1.0` (`0x3F800000`) to
`0x071C` with `ramp_id = 1` put `0x3C000000` — **1/128** — in the target,
converging over repeats to `0x3BFE03F8` ≈ **1/129**.

That number is the giveaway. `_ramp_set_target` computes
`step = (target − current) / frames` by Newton-Raphson reciprocal and
stores **target at `[r0+1]`, step at `[r0+2]`, frames at `[r0+3]`**. A
value of ~1/129 appearing where the target belongs is the *step*, so the
stores are one word low, which means

    r0 = 0x951DC = _auxin_on      (not 0x951DD = _auxin_level)

C2_PI_IN's layout is `on 0x951DC, level 0x951DD, target 0x951DE,
step 0x951DF, frames 0x951E0`, so a correct `r0` would put target at
`0x951DE`. It puts step there instead.

**Consequence:** a ramped write silently zeroes the parameter chain and
corrupts `_auxin_on` along with it. Measured after the sweep:
`auxin_level = 0.0`, `auxin_target = 0.0` — the audio path went silent and
**no direct write could recover it**, because the block-rate copy
immediately restores level from the zeroed target. Only a reboot restores
it (the `.var` initialisers give level = target = 1.0).

#### What is NOT established

The symptom is localised; the cause is not. Three candidates, and I have
not distinguished them:

1. the SPI dispatch table entry for `0x071C` resolving to `_auxin_on`,
2. how the handler computes `r0` before calling `_ramp_set_target`,
3. the offset convention inside `_ramp_set_target` itself.

The dispatch table *comment* says `0x071C: C2_PI_IN level`, so if the table
is right the fault is in (2) or (3) — but the table's own generated
comments are not proof of the address it emits.

#### Why this matters beyond the harness

Every family after GAIN needs parameter writes — EQ coefficients, dynamics
thresholds, fader levels. **All of them are ramped.** So this is not one
family blocked, it is the harness's whole parameter channel. It also lands
squarely in the kernel-rewrite block's path, since that work touches
parameter handling and the block-rate gain computer.

**Bench state:** healthy and restored — bit-exact unity pass-through
(`ratio 1.0000` on three known words, 100% of non-zero frames), both chips
`CHIP_ID` 1 and 2 at `BOOT_STAGE 7` on the `DSP4_STRIPS=1` build. CPLD
carries `dsp4_logic_loopback.2b00c3e17e2a` (captures `B_O3` slot 0 =
`C2_MAIN_ST_OUT`, the only slot the graph drives).
