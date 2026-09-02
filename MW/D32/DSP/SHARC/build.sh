#!/bin/bash
# build.sh — Native Linux CCES CLI build script for ADSP-21564 (D32)
#
# Prerequisites:
#   1. Install CCES for Linux: sudo dpkg -i adi-cces-linux-amd64-3.0.3.deb
#   2. Install SHARC Linux Command-Line Tools via Help > Install New Software
#      (or manually: extract sharc_linux.jar and sudo tar xf support_files.tar.gz -C /opt/analog/cces/3.0.3)
#   3. Activate license via Help > Manage Licenses in the CCES IDE
#
# Usage:
#   ./build.sh [clean|build|all|count]
#   Default: build

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# DSP_SRC_DIR/DSP_BUILD_DIR overrides support out-of-tree builds
# (e.g. the D5 fixed-point tree during conversion).
SRC_DIR="${DSP_SRC_DIR:-$SCRIPT_DIR/src}"
BUILD_DIR="${DSP_BUILD_DIR:-$SCRIPT_DIR/build}"
LDF="$SCRIPT_DIR/ADSP-21564.ldf"

# Native Linux CCES tool paths
CCES_DIR="/opt/analog/cces/3.0.3"
export ANALOGD_LICENSE_FILE="$HOME/.analog/cces/license.dat"
CC21K="$CCES_DIR/cc21k"
ASM21K="$CCES_DIR/easm21k"
LD21K="$CCES_DIR/linker"
LDR21K="$CCES_DIR/elfloader"

# Processor target
# Default target is ADSP-21564. Set PROC_TARGET=ADSP-21568 only when using
# a 21568-only license for a fit-proxy build.
PROC_TARGET="${PROC_TARGET:-ADSP-21564}"
PROC="-proc $PROC_TARGET"

# Assembler flags. -I <src> so shared asm headers (src/diag.h) resolve the
# same way from src/, src/chipN/ and src/lib/.
ASMFLAGS="$PROC -I $SRC_DIR"

# Compiler flags (for any C files). -I <src> for the generated headers
# (dsp_block.h carries the block size to dma_config.c).
CFLAGS="$PROC -O -DNDEBUG -I $SRC_DIR"

# P2.2 bisect variant selector (TEMPORARY — goes with the scaffolding when
# tasks.md NOW item 3 lands). See the DSP4_BISECT block at the top of
# src/dma_config.c for what each value parks on:
#   0 = production, 1 = round 1 (default, park after arm_region(A)),
#   2 = variant B (park after arm_region(B)), 3 = variant C (EN last),
#   4 = park on entry to dma_cfg_init, 5 = park on the first instruction
#   of _start (does the image execute at all?).
# The define goes to the ASSEMBLER too: with a bisect variant selected,
# diag.asm mirrors the status LED onto PB_05 (SPI2_RDY -> Pi GPIO8/GPIO12)
# so the bisect can be read over ssh instead of needing eyes on LD3/LD2.
# Always passed explicitly (defaulting to the same 1 that dma_config.c
# falls back to) so the C and asm halves can never disagree about which
# variant is being built.
# Default is 0 = PRODUCTION. It used to be 1, which is a debug variant that
# PARKS the firmware inside dma_cfg_init -- so a plain ./build.sh produced an
# image that never reached the main loop and never brought SPI2 up. On the
# bench that looks exactly like a hung part: no parameter link on either chip,
# and dsp4_stagewatch.py reports the park pulses as "stuck after stage 2".
# Cost half a session on 2026-08-23. A debugging aid must never be the default.
DSP4_BISECT="${DSP4_BISECT:-0}"
CFLAGS="$CFLAGS -DDSP4_BISECT=$DSP4_BISECT"
ASMFLAGS="$ASMFLAGS -DDSP4_BISECT=$DSP4_BISECT"
if [ "$DSP4_BISECT" != "0" ]; then
    echo "  *** DEBUG BUILD: DSP4_BISECT=$DSP4_BISECT parks the firmware ***"
    echo "  *** the parameter link will NOT come up. Use 0 for production. ***"
else
    echo "  (production build: DSP4_BISECT=0)"
fi

# Ring-mode switches (see dma_config.c). DSP4_DMA_AUTOBUF=0 goes back to
# descriptor lists; DSP4_RX0_L2=1 puts the block-clock lane's destination
# in L2 instead of the L1 alias, which is how a DDE-write-to-L1 fault is
# told apart from a descriptor or address-translation one.
DSP4_DMA_AUTOBUF="${DSP4_DMA_AUTOBUF:-1}"
DSP4_RX0_L2="${DSP4_RX0_L2:-0}"
# DSP4_PATTERN=1 fills the transmit region with the rung-1 loopback
# pattern (dma_config.c). Bring-up only; never a shipping build.
DSP4_PATTERN="${DSP4_PATTERN:-0}"
# Diagnostic: service the parameter link ONLY from the diag timer ISR,
# so the ISR backstop can be tested independently of the main loop.
DSP4_POLL_ISR_ONLY="${DSP4_POLL_ISR_ONLY:-0}"
# Block-loop bisect bitmask: 1 = scatter, 2 = node graph, 4 = gather.
# 7 = production. 0 = consume the block and do nothing with it.
DSP4_BLOCK_MASK="${DSP4_BLOCK_MASK:-7}"
# Node-chain bisect: 0 = every node (production), N = only the first N.
DSP4_NODE_LIMIT="${DSP4_NODE_LIMIT:-0}"
# Chip 2's own prefix cut (review finding D16). Defaults to
# DSP4_NODE_LIMIT, so every existing invocation cuts both chains as it
# always did; a CHIP-2 class profile sets DSP4_NODE_LIMIT=0 and this to
# N, which leaves chip 1 running whole and feeding chip 2 real signal.
DSP4_NODE_LIMIT2="${DSP4_NODE_LIMIT2:-$DSP4_NODE_LIMIT}"
# TEMP bisect: skip the compressor block-rate parameter conversion.
# Per-BLOCK kernels (KERNEL REWRITE block). 0 = the shipping per-sample
# path, which stays the bit-exact reference to diff against. 1 = one call
# per node per block with the 32-sample loop inside the kernel, block-rate
# work done once at entry with no per-sample guard. Staged: only the node
# classes already converted are affected, so intermediate values are only
# meaningful up to the converted prefix of the chain.
DSP4_BLOCK_KERNELS="${DSP4_BLOCK_KERNELS:-0}"
CFLAGS="$CFLAGS -DDSP4_BLOCK_KERNELS=$DSP4_BLOCK_KERNELS"
ASMFLAGS="$ASMFLAGS -DDSP4_BLOCK_KERNELS=$DSP4_BLOCK_KERNELS"

# Product-scope gating: skip nodes scoped to the other product at the
# dispatch table instead of entering the kernel. Block-kernel builds only
# (per-sample the test costs 32x what it saves). 0 = control build, used to
# measure what the gating is worth.
DSP4_SCOPE_GATE="${DSP4_SCOPE_GATE:-1}"
CFLAGS="$CFLAGS -DDSP4_SCOPE_GATE=$DSP4_SCOPE_GATE"
ASMFLAGS="$ASMFLAGS -DDSP4_SCOPE_GATE=$DSP4_SCOPE_GATE"

# Biquad block-cascade self-test (debug only, never in a shipping image):
# runs _bq_fx_cascade_blk and _bq_fx_cascade_N on identical data inside the
# part and diffs them, to separate the routine from the node wrapper.
DSP4_BQ_SELFTEST="${DSP4_BQ_SELFTEST:-0}"
CFLAGS="$CFLAGS -DDSP4_BQ_SELFTEST=$DSP4_BQ_SELFTEST"
ASMFLAGS="$ASMFLAGS -DDSP4_BQ_SELFTEST=$DSP4_BQ_SELFTEST"

# STRIP FUSION (2026-08-24 dispatch): fused kernels that keep intermediate
# state in registers and the MAC accumulator instead of round-tripping it
# through memory. Block-kernel builds only; default 0 so the shipping image
# is untouched.
DSP4_STRIP_FUSED="${DSP4_STRIP_FUSED:-0}"
CFLAGS="$CFLAGS -DDSP4_STRIP_FUSED=$DSP4_STRIP_FUSED"
ASMFLAGS="$ASMFLAGS -DDSP4_STRIP_FUSED=$DSP4_STRIP_FUSED"

# DSP4_CTL_ALWAYS=1 removes the control-rate gate (review findings D22/D24):
# every gated node runs its prep section unconditionally every block, the way
# it did before the gate. This is the NEGATIVE CONTROL for the gate's
# bit-exactness claim -- the gated and ungated images must produce identical
# audio -- and it is also the fallback if a gate is ever found to be missing a
# dependency. It is not a performance option: 1 is the slow build.
DSP4_CTL_ALWAYS="${DSP4_CTL_ALWAYS:-0}"
CFLAGS="$CFLAGS -DDSP4_CTL_ALWAYS=$DSP4_CTL_ALWAYS"
ASMFLAGS="$ASMFLAGS -DDSP4_CTL_ALWAYS=$DSP4_CTL_ALWAYS"

# DSP4_CTL_NEGCTL=1 keeps the gate but removes the SPI handler's control-epoch
# bump: the gated nodes then never learn that a parameter was written and hold
# whatever they prepped at boot. It is the NEGATIVE CONTROL for the gate proof
# (ctlgate.sh) -- the capture comparison must FAIL under it, or the comparison
# was not testing anything.
DSP4_CTL_NEGCTL="${DSP4_CTL_NEGCTL:-0}"
CFLAGS="$CFLAGS -DDSP4_CTL_NEGCTL=$DSP4_CTL_NEGCTL"
ASMFLAGS="$ASMFLAGS -DDSP4_CTL_NEGCTL=$DSP4_CTL_NEGCTL"

# SIMD (PEx/PEy) feasibility probe: pairs two strips into one instruction
# stream. Measurement only, not wired into the graph.
DSP4_SIMD_PROBE="${DSP4_SIMD_PROBE:-0}"
CFLAGS="$CFLAGS -DDSP4_SIMD_PROBE=$DSP4_SIMD_PROBE"
ASMFLAGS="$ASMFLAGS -DDSP4_SIMD_PROBE=$DSP4_SIMD_PROBE"

# Profiling with a signal present. The bench is silent and both dynamics
# nodes short-circuit on a zero envelope before reaching log2, so a silent
# profile measures the cheap path. 0 = normal.
DSP4_PROFILE_SIGNAL="${DSP4_PROFILE_SIGNAL:-0}"
CFLAGS="$CFLAGS -DDSP4_PROFILE_SIGNAL=$DSP4_PROFILE_SIGNAL"
ASMFLAGS="$ASMFLAGS -DDSP4_PROFILE_SIGNAL=$DSP4_PROFILE_SIGNAL"

# Core clock. 0 = CGU reset defaults (491.52 MHz), which is what every
# shipping image has ever run. 786 = 786.432 MHz (legal on both speed
# grades), 983 = 983.04 MHz (ADSP-21564KSWZ10 only -- OUT OF SPEC on a
# KSWZ8). DO NOT set this until the part marking on U5/U6 has been read.
DSP4_CCLK_TARGET="${DSP4_CCLK_TARGET:-0}"
CFLAGS="$CFLAGS -DDSP4_CCLK_TARGET=$DSP4_CCLK_TARGET"
ASMFLAGS="$ASMFLAGS -DDSP4_CCLK_TARGET=$DSP4_CCLK_TARGET"

# GATE threshold compared in the LINEAR domain instead of log2. Deletes a
# _log2q_fx call per sample. NOT bit-exact against the current fixed_ref --
# the gate's effective threshold shifts by at most 0.0002 dB -- so it needs
# a numeric-spec amendment and PW sign-off before it ships. Default 0.
DSP4_GATE_LINTHR="${DSP4_GATE_LINTHR:-0}"
CFLAGS="$CFLAGS -DDSP4_GATE_LINTHR=$DSP4_GATE_LINTHR"
ASMFLAGS="$ASMFLAGS -DDSP4_GATE_LINTHR=$DSP4_GATE_LINTHR"

# log2/exp2 by interpolated table instead of a 6-term polynomial. MORE
# accurate than what it replaces (0.000016 / 0.000008 dB against 0.0001 dB)
# but still a deviation from the current fixed_ref, so it needs a
# numeric-spec amendment and PW sign-off. Costs 1,024 words of DM.
DSP4_DYN_TABLES="${DSP4_DYN_TABLES:-0}"
CFLAGS="$CFLAGS -DDSP4_DYN_TABLES=$DSP4_DYN_TABLES"
ASMFLAGS="$ASMFLAGS -DDSP4_DYN_TABLES=$DSP4_DYN_TABLES"

# SIMD on the DYNAMICS: GATE and COMP for two channels in one instruction
# stream (src/lib/dyn_simd_fx.asm). Needs the POLYNOMIAL log2/exp2 -- a
# table lookup is a gather at two indices and the DAGs are shared -- so it
# is incompatible with DSP4_DYN_TABLES=1 and the assembler says so. It also
# needs the per-ISR PEYEN clear, which lives under DSP4_SIMD_STRIPS, so
# enabling this defaults that on. Default 0; the shipping image is
# byte-identical with it off.
DSP4_SIMD_DYN="${DSP4_SIMD_DYN:-0}"
CFLAGS="$CFLAGS -DDSP4_SIMD_DYN=$DSP4_SIMD_DYN"
ASMFLAGS="$ASMFLAGS -DDSP4_SIMD_DYN=$DSP4_SIMD_DYN"
# Negative control for the paired-dynamics self-test: gather channel B
# from channel A, so the pair computes one channel twice. The diff MUST
# fail with this set.
DSP4_SIMD_NEGCTL="${DSP4_SIMD_NEGCTL:-0}"
CFLAGS="$CFLAGS -DDSP4_SIMD_NEGCTL=$DSP4_SIMD_NEGCTL"
ASMFLAGS="$ASMFLAGS -DDSP4_SIMD_NEGCTL=$DSP4_SIMD_NEGCTL"
# Wire the GRAPH for pairing: the odd block pool, the per-pair dynamics
# drivers and the pair-ordered chain (2026-08-28). Separate from
# DSP4_SIMD_DYN, which only puts the paired KERNELS in the image, because
# the self-test build wants the kernels and their scalar twins WITHOUT the
# 32 drivers -- with both, chip 1 overflows sec_swco. Defaults on whenever
# the kernels are in, so DSP4_SIMD_DYN=1 alone gives a paired graph.
DSP4_SIMD_GRAPH="${DSP4_SIMD_GRAPH:-1}"
CFLAGS="$CFLAGS -DDSP4_SIMD_GRAPH=$DSP4_SIMD_GRAPH"
ASMFLAGS="$ASMFLAGS -DDSP4_SIMD_GRAPH=$DSP4_SIMD_GRAPH"
# PAIRED BIQUADS IN THE GRAPH (2026-08-29). The FILT and EQ classes of a
# strip PAIR run as one SIMD instruction stream, the way the dynamics have
# since 08-28. Only takes effect in a paired-graph build (it needs the odd
# pool and the pair-ordered chain), so it defaults ON and DSP4_BQ_GRAPH=0 is
# the CONTROL: same image, dynamics-only pairs, which is what the session-3
# capacity table was measured on.
DSP4_BQ_GRAPH="${DSP4_BQ_GRAPH:-1}"
CFLAGS="$CFLAGS -DDSP4_BQ_GRAPH=$DSP4_BQ_GRAPH"
ASMFLAGS="$ASMFLAGS -DDSP4_BQ_GRAPH=$DSP4_BQ_GRAPH"
# PAIRED BIQUAD CASCADES ON CHIP 2 (2026-09-02), NATIVE INTERLEAVE. The
# pair OWNS the interleaved coefficient and state arrays and latches them,
# so there is no per-block gather -- chip 1's _bq_pair_blk gathers on every
# block, which is 4.25 cycles per band-sample whatever the stage count.
# Only takes effect in a paired-graph build, so it defaults ON and
# DSP4_C2_BQ_GRAPH=0 is the CONTROL: the same image with chip 2's biquad
# classes back in the chain as scalar nodes and the dynamics pairs
# untouched, which is what 240,681 cycles/block was measured on.
DSP4_C2_BQ_GRAPH="${DSP4_C2_BQ_GRAPH:-1}"
CFLAGS="$CFLAGS -DDSP4_C2_BQ_GRAPH=$DSP4_C2_BQ_GRAPH"
ASMFLAGS="$ASMFLAGS -DDSP4_C2_BQ_GRAPH=$DSP4_C2_BQ_GRAPH"
# THE ROUND-TRIP ARM for chip 2's biquad pairing. 1 scatters the state back
# and drops the pair latch on EVERY block, so the engage/disengage
# bookkeeping -- once per coefficient swap in a real build -- runs at block
# rate. It must stay bit-exact against both the scalar and the latched arm,
# and the cost difference against the latched arm is the per-block gather
# the latch exists to remove. Debug and measurement only.
DSP4_C2_BQ_NOLATCH="${DSP4_C2_BQ_NOLATCH:-0}"
CFLAGS="$CFLAGS -DDSP4_C2_BQ_NOLATCH=$DSP4_C2_BQ_NOLATCH"
ASMFLAGS="$ASMFLAGS -DDSP4_C2_BQ_NOLATCH=$DSP4_C2_BQ_NOLATCH"
# NEGATIVE CONTROL for chip 2's biquad pairing: channel B's coefficients
# are gathered as ZERO at engage, so B runs a dead filter and A does not.
# Every channel-B cascade output must move and no channel-A one may.
# A cross-feed control (B takes A's coefficients, which is what
# DSP4_BQ_NEGCTL does on chip 1) is DEAD on chip 2, because every chip-2
# cascade runs on the same .var bypass initialisers. Debug only.
DSP4_C2_BQ_NEGCTL="${DSP4_C2_BQ_NEGCTL:-0}"
CFLAGS="$CFLAGS -DDSP4_C2_BQ_NEGCTL=$DSP4_C2_BQ_NEGCTL"
ASMFLAGS="$ASMFLAGS -DDSP4_C2_BQ_NEGCTL=$DSP4_C2_BQ_NEGCTL"
# NEGATIVE CONTROL for the paired-biquad graph: the pair takes strip B's
# coefficients and state from strip A, so it computes one channel twice.
# The bus capture MUST differ under this, or bqgraph.sh's bit-exact verdict
# is a diff that cannot fail. Debug only.
DSP4_BQ_NEGCTL="${DSP4_BQ_NEGCTL:-0}"
CFLAGS="$CFLAGS -DDSP4_BQ_NEGCTL=$DSP4_BQ_NEGCTL"
ASMFLAGS="$ASMFLAGS -DDSP4_BQ_NEGCTL=$DSP4_BQ_NEGCTL"

# The per-ISR PEYEN clear lives under DSP4_SIMD_STRIPS, and EVERY routine
# that sets PEYEN needs it -- the paired dynamics and the paired biquad
# cascade alike. It used to default on for DSP4_SIMD_DYN only, which left a
# DSP4_SIMD_PROBE build (the biquad self-test) running SIMD kernels with no
# ISR protection at all.
if [ "$DSP4_SIMD_DYN" != "0" ] || [ "${DSP4_SIMD_PROBE:-0}" != "0" ]; then
    DSP4_SIMD_STRIPS_DEFAULT=1
else
    DSP4_SIMD_STRIPS_DEFAULT=0
fi

# Strip pairing for SIMD: adds one pool slot to park strip N's block while
# strip N+1 catches up, and emits the biquad section of a strip PAIR as a
# single paired call. Block-kernel builds only, default 0.
DSP4_SIMD_STRIPS="${DSP4_SIMD_STRIPS:-$DSP4_SIMD_STRIPS_DEFAULT}"
CFLAGS="$CFLAGS -DDSP4_SIMD_STRIPS=$DSP4_SIMD_STRIPS"
ASMFLAGS="$ASMFLAGS -DDSP4_SIMD_STRIPS=$DSP4_SIMD_STRIPS"
# The paired-dynamics SELF-TEST (lib/dyn_selftest.asm) is an instrument,
# not a kernel: 2,240 bytes of program memory plus its stimulus tables. It
# used to be gated on DSP4_SIMD_DYN, so EVERY paired build -- including a
# shipping one -- carried it, which is 2,240 bytes of the wall session 3
# ran into. It now has its own switch, defaulting to DSP4_SIMD_PROBE so
# dynst.sh (which sets PROBE=1) keeps working unchanged.
DSP4_DYN_SELFTEST="${DSP4_DYN_SELFTEST:-${DSP4_SIMD_PROBE:-0}}"
CFLAGS="$CFLAGS -DDSP4_DYN_SELFTEST=$DSP4_DYN_SELFTEST"
ASMFLAGS="$ASMFLAGS -DDSP4_DYN_SELFTEST=$DSP4_DYN_SELFTEST"
DSP4_SKIP_PAIR="${DSP4_SKIP_PAIR:-0}"   # bisect hook for the selftest hang
CFLAGS="$CFLAGS -DDSP4_SKIP_PAIR=$DSP4_SKIP_PAIR"
ASMFLAGS="$ASMFLAGS -DDSP4_SKIP_PAIR=$DSP4_SKIP_PAIR"
# NEGATIVE CONTROL for the paired-cascade hang fix (2026-08-29). 1 skips
# the reload of the pointers _bq_pair_blk parked before calling
# _bq_fx_cascade_simd, which puts the pre-fix behaviour back: the scatter
# then runs on the cascade's leftover registers and the state loop takes
# lcntr = 0x10000000. The self-test MUST fail to complete with this set,
# or the fix was not what fixed it.
DSP4_BQP_NOSAVE="${DSP4_BQP_NOSAVE:-0}"
CFLAGS="$CFLAGS -DDSP4_BQP_NOSAVE=$DSP4_BQP_NOSAVE"
ASMFLAGS="$ASMFLAGS -DDSP4_BQP_NOSAVE=$DSP4_BQP_NOSAVE"
# FAULT-VECTOR TRAP (2026-08-30). Unmasks the fault interrupts and puts a
# counting handler on each one. Every fault vector ships as a bare `rti`
# AND masked, so a fault is invisible twice over -- see the note in
# main.asm. Diagnostic only; default 0 and the shipping image is
# byte-identical with it off.
# SECONDARY-DAG probe / fix (2026-08-30). Every ISR runs with SRD1L|SRD1H
# set, on a secondary DAG1 whose LENGTH registers are written nowhere in
# the tree -- C_RUNTIME_INIT zeroes the PRIMARY set. DSP4_DAG_PROBE reads
# what the boot kernel left; DSP4_DAG_SEC_INIT zeroes it. Both default 0
# so the shipping image is byte-identical until the fix is taken
# deliberately.
# DSP4_CFG_WATCH (2026-08-30, session 13) — bound _cgu_raise_cclk's four
# UNBOUNDED spin-waits on CGU0_STAT, publish how many iterations each one
# takes, and stamp how far _product_config_commit got. A wedged cycle
# answers every diag read with a well-formed (echo, 0), so nothing on the
# part could report anything; this is what makes it speak. Default 0 —
# it changes the shipping image.
DSP4_CFG_WATCH="${DSP4_CFG_WATCH:-0}"
CFLAGS="$CFLAGS -DDSP4_CFG_WATCH=$DSP4_CFG_WATCH"
ASMFLAGS="$ASMFLAGS -DDSP4_CFG_WATCH=$DSP4_CFG_WATCH"
# DSP4_SPI_PARTIAL_FIX2 (2026-08-30, session 13) — arm the stuck-partial
# request recovery only while the parameter link is standing still, so a
# config burst in flight can no longer be mistaken for a stale fragment
# and have one of its words discarded. Fixes D71 (lost CONFIG_COMMIT
# transaction): 0 D71 events in 350 pooled fixed-path cycles vs 2/136
# unfixed.
#
# SESSION 14 TRIED DEFAULT-ON AND REVERTED IT THE SAME SESSION (D74): with
# this flag on, busgold.sh's dsp4_scope.py read path failed to capture 4 of
# 4 times ("register 0xE001 never settled" / "link answers as CHIP 0"),
# while the flag off passed 2 of 2.
#
# SESSION 15 ROOT-CAUSED D74 AND IT IS NOT IN THIS FLAG. The link answers
# every transaction with (echo, value) and the host's 8-byte windows can
# sit on either of two offsets in that word stream; the echo lands in word
# 1 in BOTH, so the host's echo check passed while handing back the
# PREVIOUS request's value — 0, after a NOP collect. That is the whole of
# "answers as CHIP 0". The old unconditional word discard was the only
# thing that ever moved that phase, so suppressing it left the scope path
# stuck in the wrong one. The fix is host-side: tools/pi/dsp4_diag.py now
# CALIBRATES the phase against DIAG_MAGIC and decodes with it. With that in
# place this flag is safe on, and it is on: it fixes D71.
DSP4_SPI_PARTIAL_FIX2="${DSP4_SPI_PARTIAL_FIX2:-1}"
CFLAGS="$CFLAGS -DDSP4_SPI_PARTIAL_FIX2=$DSP4_SPI_PARTIAL_FIX2"
ASMFLAGS="$ASMFLAGS -DDSP4_SPI_PARTIAL_FIX2=$DSP4_SPI_PARTIAL_FIX2"
DSP4_DAG_PROBE="${DSP4_DAG_PROBE:-0}"
CFLAGS="$CFLAGS -DDSP4_DAG_PROBE=$DSP4_DAG_PROBE"
ASMFLAGS="$ASMFLAGS -DDSP4_DAG_PROBE=$DSP4_DAG_PROBE"
DSP4_DAG_SEC_INIT="${DSP4_DAG_SEC_INIT:-0}"
CFLAGS="$CFLAGS -DDSP4_DAG_SEC_INIT=$DSP4_DAG_SEC_INIT"
ASMFLAGS="$ASMFLAGS -DDSP4_DAG_SEC_INIT=$DSP4_DAG_SEC_INIT"
DSP4_FAULT_TRAP="${DSP4_FAULT_TRAP:-0}"
CFLAGS="$CFLAGS -DDSP4_FAULT_TRAP=$DSP4_FAULT_TRAP"
ASMFLAGS="$ASMFLAGS -DDSP4_FAULT_TRAP=$DSP4_FAULT_TRAP"
# EXACT ITERATION COUNTING in the paired cascade and its wrapper: a phase
# marker plus stage and sample loop counters, so a wedge says WHICH loop it
# is in rather than only that the self-test never finished. Diagnostic
# only; default 0.
DSP4_BQ_TRACE="${DSP4_BQ_TRACE:-0}"
CFLAGS="$CFLAGS -DDSP4_BQ_TRACE=$DSP4_BQ_TRACE"
ASMFLAGS="$ASMFLAGS -DDSP4_BQ_TRACE=$DSP4_BQ_TRACE"
DSP4_SKIP_SIMDCALL="${DSP4_SKIP_SIMDCALL:-0}"
CFLAGS="$CFLAGS -DDSP4_SKIP_SIMDCALL=$DSP4_SKIP_SIMDCALL"
ASMFLAGS="$ASMFLAGS -DDSP4_SKIP_SIMDCALL=$DSP4_SKIP_SIMDCALL"
# Stages the paired-cascade self-test arm asks for (1..4). A bisect knob
# for the _bq_fx_cascade_simd hang, not a mode.
DSP4_BQ_PAIR_STAGES="${DSP4_BQ_PAIR_STAGES:-4}"
ASMFLAGS="$ASMFLAGS -DDSP4_BQ_PAIR_STAGES=$DSP4_BQ_PAIR_STAGES"

# NUMERIC BOUNDARY SELF-TEST (2026-08-29, review findings D1/D3). Runs
# the REAL _acc64_mac/_acc64_rns28 and the generated crossfade blend over
# vectors that straddle the wide-accumulator and 32-bit-difference
# boundaries, inside the part, and leaves the results in DM for
# tools/pi/dsp4_num_verify.py to diff against fixed_ref.
# DSP4_NUM_NEGCTL=1 swaps in the PRE-FIX arithmetic: the same vectors
# must then FAIL, and fail exactly where the model predicts. Debug only.
DSP4_NUM_SELFTEST="${DSP4_NUM_SELFTEST:-0}"
DSP4_NUM_NEGCTL="${DSP4_NUM_NEGCTL:-0}"
CFLAGS="$CFLAGS -DDSP4_NUM_SELFTEST=$DSP4_NUM_SELFTEST -DDSP4_NUM_NEGCTL=$DSP4_NUM_NEGCTL"
ASMFLAGS="$ASMFLAGS -DDSP4_NUM_SELFTEST=$DSP4_NUM_SELFTEST -DDSP4_NUM_NEGCTL=$DSP4_NUM_NEGCTL"

# INLINE THE PAIRED-DYNAMICS CALL SITES (2026-08-30, review finding D66).
# A call/rts pair costs 15.04 cycles of pipeline refill on this part,
# measured, and the two pair kernels made ten of them per SIMD sample.
#   0 = every site is a call -- the pre-inlining CONTROL, and the form the
#       standalone _..._simd routines still document
#   1 = _mrf_rns28_simd inlined (3 sites, no nested hardware loop)
#   2 = + _compgain_simd and _log2q_simd inlined with their nested
#       _polyq_simd/_exp2q_simd (7 more sites)
# Levels exist so a numeric or a hang regression can be bisected to the
# class of inlining that caused it rather than to the whole change.
DSP4_DYN_INLINE="${DSP4_DYN_INLINE:-2}"
CFLAGS="$CFLAGS -DDSP4_DYN_INLINE=$DSP4_DYN_INLINE"
ASMFLAGS="$ASMFLAGS -DDSP4_DYN_INLINE=$DSP4_DYN_INLINE"

# CALL/RTS CALIBRATION LADDER (2026-08-30, review finding D66). An
# on-part instrument, not a mode: eight timed loops that price a bare
# call/rts pair, the same pair around a real body, the same body inlined,
# and TUBE's per-sample body both ways. It answers whether the ~17
# cycles/sample/pair session 9 inferred is generic branch overhead or
# something specific to _mrf_rns28 -- which is what decides whether AXIS
# 1's floor rows are understated. Debug only; never in a shipping image.
DSP4_CALL_SELFTEST="${DSP4_CALL_SELFTEST:-0}"
CFLAGS="$CFLAGS -DDSP4_CALL_SELFTEST=$DSP4_CALL_SELFTEST"
ASMFLAGS="$ASMFLAGS -DDSP4_CALL_SELFTEST=$DSP4_CALL_SELFTEST"

# Meter bisect hooks (2026-08-28 rebuild). NOFOLD stops at the per-sample
# accumulation, NOCVT stops before the float readback, NOSQRT stops before
# the square root. All 0 = the real meter.
DSP4_MTR_NOFOLD="${DSP4_MTR_NOFOLD:-0}"
DSP4_MTR_NOCVT="${DSP4_MTR_NOCVT:-0}"
DSP4_MTR_NOSQRT="${DSP4_MTR_NOSQRT:-0}"
# MTR_OFF makes every meter node an immediate rts: what the meters cost,
# measured by removing them. Never a shipping build.
DSP4_MTR_OFF="${DSP4_MTR_OFF:-0}"
ASMFLAGS="$ASMFLAGS -DDSP4_MTR_NOFOLD=$DSP4_MTR_NOFOLD -DDSP4_MTR_NOCVT=$DSP4_MTR_NOCVT -DDSP4_MTR_NOSQRT=$DSP4_MTR_NOSQRT -DDSP4_MTR_OFF=$DSP4_MTR_OFF"

DSP4_COMP_NOCVT="${DSP4_COMP_NOCVT:-0}"
# Run the node graph only every Nth block (measurement, not a mode).
DSP4_BLOCK_DECIMATE="${DSP4_BLOCK_DECIMATE:-1}"
# Keep only the first N channel strips (0 = all). Unlike DSP4_NODE_LIMIT
# this leaves the graph FUNCTIONAL: buses, sends and transfers all stay.
DSP4_STRIPS="${DSP4_STRIPS:-0}"
# SPI2 flow-control watermark: 0 = RFIFO full, 1 = 75%, 2 = 50%.
DSP4_FCWM="${DSP4_FCWM:-1}"
# TEMP bisect: make _compgain_fx return unity immediately.
DSP4_STUB_COMPGAIN="${DSP4_STUB_COMPGAIN:-0}"
DSP4_STUB_EXP2="${DSP4_STUB_EXP2:-0}"
DSP4_STUB_LOG2="${DSP4_STUB_LOG2:-0}"
DSP4_STUB_POLY="${DSP4_STUB_POLY:-0}"
# CONFIG_COMMIT bisect: 0 = neither apply call, 1 = rx patch only, 2 = both.
DSP4_COMMIT_STAGE="${DSP4_COMMIT_STAGE:-2}"
# Diagnostic: put the main loop's `idle` back (it wedges the parameter
# link -- see main.asm). Off by default; the loop spins.
DSP4_NO_IDLE_OVERRIDE="${DSP4_NO_IDLE_OVERRIDE:-0}"
CFLAGS="$CFLAGS -DDSP4_DMA_AUTOBUF=$DSP4_DMA_AUTOBUF -DDSP4_RX0_L2=$DSP4_RX0_L2 -DDSP4_PATTERN=$DSP4_PATTERN -DDSP4_FCWM=$DSP4_FCWM"
ASMFLAGS="$ASMFLAGS -DDSP4_POLL_ISR_ONLY=$DSP4_POLL_ISR_ONLY -DDSP4_BLOCK_MASK=$DSP4_BLOCK_MASK -DDSP4_NODE_LIMIT=$DSP4_NODE_LIMIT -DDSP4_NODE_LIMIT2=$DSP4_NODE_LIMIT2 -DDSP4_COMP_NOCVT=$DSP4_COMP_NOCVT -DDSP4_COMMIT_STAGE=$DSP4_COMMIT_STAGE -DDSP4_NO_IDLE_OVERRIDE=$DSP4_NO_IDLE_OVERRIDE -DDSP4_STUB_COMPGAIN=$DSP4_STUB_COMPGAIN -DDSP4_STUB_EXP2=$DSP4_STUB_EXP2 -DDSP4_STUB_LOG2=$DSP4_STUB_LOG2 -DDSP4_STUB_POLY=$DSP4_STUB_POLY -DDSP4_BLOCK_DECIMATE=$DSP4_BLOCK_DECIMATE -DDSP4_STRIPS=$DSP4_STRIPS"

# Linker flags — LDF resolved in build(): the repo LDF hardcodes
# ARCHITECTURE(ADSP-21564); for a fit-proxy build under a different
# PROC_TARGET a matching temp LDF is generated in the build dir (same
# memory map — 21568 = same core/L1/L2). Never commit a non-21564 LDF.
resolve_ldf() {
    if [ "$PROC_TARGET" != "ADSP-21564" ]; then
        mkdir -p "$BUILD_DIR"
        local proxy_ldf="$BUILD_DIR/${PROC_TARGET}.ldf"
        sed "s/ARCHITECTURE(ADSP-21564)/ARCHITECTURE($PROC_TARGET)/" "$LDF" > "$proxy_ldf"
        LDF="$proxy_ldf"
        echo "  (fit-proxy: using generated $proxy_ldf)"
    fi
    LDFLAGS="$PROC -T $LDF"
}

# A non-21564 build is a temporary compatibility (fit-proxy) image only —
# same core/L1/L2, different part number. Banner it and drop a marker beside
# the DXEs so the output can never be mistaken for a production card image.
compat_banner() {
    [ "$PROC_TARGET" = "ADSP-21564" ] && return 0
    echo "*********************************************************************"
    echo "*  TEMPORARY COMPATIBILITY BUILD — target $PROC_TARGET, NOT 21564"
    echo "*  Fit proxy only (21564 constraints + memory map). Do NOT flash or"
    echo "*  release as a production D32/DSP4 image."
    echo "*********************************************************************"
}

compat_marker() {
    [ "$PROC_TARGET" = "ADSP-21564" ] && return 0
    cat > "$BUILD_DIR/COMPAT-BUILD.txt" <<EOF
TEMPORARY COMPATIBILITY BUILD — NOT A PRODUCTION IMAGE

Target:      $PROC_TARGET (fit proxy for ADSP-21564)
LDF:         $LDF (generated; ARCHITECTURE rewritten, memory map unchanged)
Built:       $(date -u '+%Y-%m-%dT%H:%M:%SZ')
Reason:      full CCES licence (AD-CCES-NODE-1) pending; this host is
             entitled to ADSP-21568 only, so -proc ADSP-21564 fails.
Validity:    proves toolchain, codegen, link and memory fit. Says nothing
             about 21564 part-specific behaviour. Do not flash to hardware
             or publish as a release artifact. This applies to the .ldr
             boot streams beside the DXEs too — they are bootable, and a
             fit-proxy image booted into a real 21564 is not a test, it
             is an unknown.
EOF
    echo "  Marker: $BUILD_DIR/COMPAT-BUILD.txt"
}
LDFLAGS="$PROC -T $LDF"

clean() {
    echo "=== Clean ==="
    rm -rf "$BUILD_DIR"
    echo "Cleaned."
}

count() {
    echo "=== Source file count ==="
    echo "Chip 1 node ASM:  $(find "$SRC_DIR/chip1/nodes" -name '*.asm' 2>/dev/null | wc -l)"
    echo "Chip 2 node ASM:  $(find "$SRC_DIR/chip2/nodes" -name '*.asm' 2>/dev/null | wc -l)"
    echo "Chip 1 infra ASM: $(find "$SRC_DIR/chip1" -maxdepth 1 -name '*.asm' 2>/dev/null | wc -l)"
    echo "Chip 2 infra ASM: $(find "$SRC_DIR/chip2" -maxdepth 1 -name '*.asm' 2>/dev/null | wc -l)"
    echo "Shared ASM:       $(find "$SRC_DIR" -maxdepth 1 -name '*.asm' 2>/dev/null | wc -l)"
    echo "Library ASM:      $(find "$SRC_DIR/lib" -name '*.asm' 2>/dev/null | wc -l)"
    echo "Total ASM:        $(find "$SRC_DIR" -name '*.asm' 2>/dev/null | wc -l)"
}

single() {
    local asm_path="$1"
    if [ -z "$asm_path" ]; then
        echo "Usage: $0 single <asm-file>"
        exit 1
    fi

    if [[ "$asm_path" != /* ]]; then
        asm_path="$SCRIPT_DIR/$asm_path"
    fi

    if [ ! -f "$asm_path" ]; then
        echo "ERROR: file not found: $asm_path"
        exit 1
    fi

    mkdir -p "$BUILD_DIR"
    local base
    base=$(basename "$asm_path" .asm)
    local out_path="$BUILD_DIR/$base.doj"

    echo "=== Single-file assemble ==="
    echo "ASM: $asm_path"
    $ASM21K $ASMFLAGS -o "$out_path" "$asm_path"
    echo "Wrote: $out_path"
}

assemble_dir() {
    local src_dir="$1"
    local out_dir="$2"
    local label="$3"
    local extra_flags="${4:-}"

    local count=0
    local errors=0

    for asm in "$src_dir"/*.asm; do
        [ -f "$asm" ] || continue
        base=$(basename "$asm" .asm)
        echo "  ASM: $base"
        $ASM21K $ASMFLAGS $extra_flags -o "$out_dir/$base.doj" "$asm" || errors=$((errors+1))
        count=$((count+1))
    done

    echo "  ($label: $count files, $errors errors)"
    return $errors
}

build() {
    echo "=== Build D32 DSP ==="
    compat_banner
    resolve_ldf
    mkdir -p "$BUILD_DIR/chip1" "$BUILD_DIR/chip2" "$BUILD_DIR/lib"

    local total_errors=0

    # ---- Shared library (chip-agnostic: biquad, dynamics, delay, ramp) ----
    echo "--- Library: Assembling ---"
    assemble_dir "$SRC_DIR/lib" "$BUILD_DIR/lib" "lib" || total_errors=$((total_errors+$?))

    # ---- CHIP-2-ONLY library ----
    # src/lib is linked into BOTH chips, so a kernel only chip 2 can use
    # still costs chip 1 the program memory -- and chip 1 has none to
    # spare: _lim_pair_blk in src/lib overflowed sec_swco on every build
    # carrying DSP4_PROFILE_SIGNAL (2026-09-02). src/lib2 is assembled
    # here and linked into chip 2 ALONE.
    echo "--- Library (chip 2 only): Assembling ---"
    mkdir -p "$BUILD_DIR/lib2"
    assemble_dir "$SRC_DIR/lib2" "$BUILD_DIR/lib2" "lib2" || total_errors=$((total_errors+$?))

    # ---- Shared infrastructure — assembled TWICE with CHIP_ID define ----
    # Files like main.asm, ivt.asm, sport_init.asm use #if CHIP_ID == N
    # to conditionally include chip-specific externs and code paths.
    echo "--- Shared (Chip 1): Assembling ---"
    assemble_dir "$SRC_DIR" "$BUILD_DIR/chip1" "shared-c1" "-DCHIP_ID=1" || total_errors=$((total_errors+$?))

    echo "--- Shared (Chip 2): Assembling ---"
    assemble_dir "$SRC_DIR" "$BUILD_DIR/chip2" "shared-c2" "-DCHIP_ID=2" || total_errors=$((total_errors+$?))

    # IVT must use -nwc (Normal Word Code) for fixed vector table alignment.
    # The default VISA mode produces SW sections that don't match the PM
    # qualifier required for the NW IVT memory region.
    echo "  Re-assembling IVT with -nwc (NW mode for vector table)"
    $ASM21K $ASMFLAGS -DCHIP_ID=1 -nwc -o "$BUILD_DIR/chip1/ivt.doj" "$SRC_DIR/ivt.asm" || total_errors=$((total_errors+1))
    $ASM21K $ASMFLAGS -DCHIP_ID=2 -nwc -o "$BUILD_DIR/chip2/ivt.doj" "$SRC_DIR/ivt.asm" || total_errors=$((total_errors+1))

    # ---- Chip 1: Infrastructure + dsp_params ----
    echo "--- Chip 1: Infrastructure ---"
    assemble_dir "$SRC_DIR/chip1" "$BUILD_DIR/chip1" "chip1-infra" "-DCHIP_ID=1" || total_errors=$((total_errors+$?))

    # ---- Chip 1: Node skeletons ----
    echo "--- Chip 1: Nodes ---"
    assemble_dir "$SRC_DIR/chip1/nodes" "$BUILD_DIR/chip1" "chip1-nodes" || total_errors=$((total_errors+$?))

    # ---- Chip 2: Infrastructure + dsp_params ----
    echo "--- Chip 2: Infrastructure ---"
    assemble_dir "$SRC_DIR/chip2" "$BUILD_DIR/chip2" "chip2-infra" "-DCHIP_ID=2" || total_errors=$((total_errors+$?))

    # ---- Chip 2: Node skeletons ----
    echo "--- Chip 2: Nodes ---"
    assemble_dir "$SRC_DIR/chip2/nodes" "$BUILD_DIR/chip2" "chip2-nodes" || total_errors=$((total_errors+$?))

    # ---- Compile C files ----
    # Shared (root src/) C is compiled TWICE with -DCHIP_ID, like the
    # shared asm infra; chipN/ C compiles once with its chip define.
    for csrc in "$SRC_DIR"/*.c; do
        [ -f "$csrc" ] || continue
        base=$(basename "$csrc" .c)
        for chip in 1 2; do
            echo "  CC: $base.c (CHIP_ID=$chip)"
            $CC21K $CFLAGS -DCHIP_ID=$chip -c \
                -o "$BUILD_DIR/chip$chip/$base.doj" "$csrc" || total_errors=$((total_errors+1))
        done
    done
    for chip in 1 2; do
        for csrc in "$SRC_DIR"/chip$chip/*.c; do
            [ -f "$csrc" ] || continue
            base=$(basename "$csrc" .c)
            echo "  CC: chip$chip/$base.c"
            $CC21K $CFLAGS -DCHIP_ID=$chip -c \
                -o "$BUILD_DIR/chip$chip/$base.doj" "$csrc" || total_errors=$((total_errors+1))
        done
    done

    # ---- Link Chip 1 ----
    # chip1/ has: shared infra (CHIP_ID=1), chip1 infra, chip1 nodes, dsp_params
    # lib/ has: chip-agnostic library
    echo "--- Chip 1: Linking ---"
    chip1_objs=$(find "$BUILD_DIR/chip1" "$BUILD_DIR/lib" -name '*.doj' 2>/dev/null | sort)
    if [ -n "$chip1_objs" ]; then
        echo "  Objects: $(echo "$chip1_objs" | wc -l) files"
        $LD21K $LDFLAGS -Map "$BUILD_DIR/chip1.map.xml" -o "$BUILD_DIR/chip1.dxe" $chip1_objs || total_errors=$((total_errors+1))
    else
        echo "  WARNING: No object files for Chip 1"
    fi

    # ---- Link Chip 2 ----
    echo "--- Chip 2: Linking ---"
    chip2_objs=$(find "$BUILD_DIR/chip2" "$BUILD_DIR/lib" "$BUILD_DIR/lib2" \
                      -name '*.doj' 2>/dev/null | sort)
    if [ -n "$chip2_objs" ]; then
        echo "  Objects: $(echo "$chip2_objs" | wc -l) files"
        $LD21K $LDFLAGS -Map "$BUILD_DIR/chip2.map.xml" -o "$BUILD_DIR/chip2.dxe" $chip2_objs || total_errors=$((total_errors+1))
    else
        echo "  WARNING: No object files for Chip 2"
    fi

    if [ $total_errors -gt 0 ]; then
        echo "=== Build FAILED ($total_errors errors) ==="
        return 1
    fi

    echo "=== Build OK ==="
    echo "  Chip 1: $BUILD_DIR/chip1.dxe"
    echo "  Chip 2: $BUILD_DIR/chip2.dxe"
    loader || total_errors=$((total_errors+1))
    compat_marker
    compat_banner
    echo ""
    count
}

# ---- Boot streams (.ldr) ------------------------------------------------
# A .dxe is not bootable. The card has no boot flash: SYS_BMODE[2:0] is
# strapped 0b010 = SPI slave boot through the SPI2 peripheral, and the
# CM4 pushes the stream (CS1 -> chip 1, CS2 -> chip 2). See
# tools/pi/dsp4_boot.py for the host side.
#
#   -b SPIHOST  "SPI Host boot" = the slave-boot case, where a host
#               pushes the stream in. -b SPI is the master case (the part
#               reads a flash itself) and is the wrong intent here.
#               elfloader 6.4.2.1 emits byte-identical output for both
#               (checked 2026-08-20), so this is a statement of intent
#               rather than a change of image — but state the intent, so
#               a toolchain that starts distinguishing them gets it right.
#   -bcode 1    single-bit SPI (HRM Table 40-19, SPIS_BCODE 00xx). The
#               BCODE nibble sits in the low byte of every block header,
#               and the boot kernel reads the first byte of the stream as
#               its SPICMD auto-detect (HRM Table 40-18), so this is also
#               what tells the kernel to stay in single-bit mode.
#   -f BINARY   raw bytes for spidev, not ASCII hex
#   -width 8    byte-wide stream
#   -NoFillBlock
#               HARD REQUIREMENT on this part in SPI target boot, found
#               2026-08-21. By default elfloader compresses runs of zeros
#               into ZERO-FILL blocks: a header with a byte count and no
#               payload. The boot kernel does not survive one. A fill
#               block that is followed by any further block loses the
#               kernel its place in the stream, every header after it is
#               garbage, and the part never executes an instruction --
#               while the host still clocks the whole stream out and
#               reports success.
#
#               Measured at the bench, chip 2, gap-synced 11 MHz:
#                 one 640 B fill inserted at the FRONT of an image that
#                   otherwise boots            3/3  ->  0/3
#                 the identical block APPENDED instead
#                                              3/3  ->  3/3
#                 chip2 firmware as elfloader emits it (324 blocks,
#                   152 of them fills)               0/6
#                 same firmware, -NoFillBlock (6 blocks, no fills)
#                                                    5/6
#               A fill block that happens to be LAST is harmless, which
#               is why nothing downstream of it ever noticed.
#
#               This is what kept the D32 firmware from ever running.
#               The earlier `-MaxBlockSize 0x1000` theory (a block-size
#               ceiling around 8 KB) was WRONG and has been removed: an
#               A/B of the same DXE capped vs uncapped, 8 runs each,
#               scored 7/8 and 6/8 -- indistinguishable. That reading
#               came from a ~50% per-attempt failure rate whose real
#               cause was the boot bus's second master (see below), not
#               the block size.
#
#               COST: the zeros now travel in the stream. Delay-line
#               buffers are marked NO_INIT in the LDF for exactly this
#               reason -- see the note beside sec_delay there -- without
#               which chip2 would be a 1.9 MB stream.
#
#               tools/dsp/ldr_stream.py check enforces this, and loader()
#               below runs it on every image built.
#
# BOOT-STREAM TIME BUDGET (the other half of the 2026-08-21 finding).
# The DSP boot bus has a SECOND MASTER: U7/H1S1 runs a legacy ADAU meter
# poll on the same SCK/MOSI nets, a ~0.6 ms burst roughly every 260 ms
# (MW/D24/HW/hardware-map.md 3). The Pi clamps SCK but not MOSI, so a
# burst landing mid-stream corrupts the boot data. Boot failure
# probability tracks stream ELAPSED TIME almost exactly -- proved by
# running one unchanged image at three clocks: 3 KB booted 5/6 at 1 MHz
# (25 ms) and 0/6 at 100 kHz (246 ms). dsp4_boot.py --sync-poll starts
# the stream just after a burst and buys most of a gap; 11 MHz is the
# fastest clock this bus takes (12 MHz and up fail outright).
# RESOLVED 2026-08-21, same day: the two interfering call sites were
# removed from H1S1's firmware and it was reflashed through MH1. The bus
# now measures ZERO events in 15 s, and chip1's full 258 KB image boots
# 6/6 at 10 MHz unsynced and 2/2 at 1 MHz on a 3.45 s stream. There is no
# longer a stream-length budget on this unit. The --sync-poll and clock
# advice above is kept because the two-master WIRING is still a rev-D
# item: any board whose H1S1 has not been reflashed has the limit back.
LDRFLAGS="-b SPIHOST -bcode 1 -f BINARY -width 8 -NoFillBlock"
#
# The entry address is NOT passed on the command line: the ELF header
# carries no entry point, so elfloader defaults to 0x90004 — which IS the
# right answer here (IVT base 0x00090000 + RSTI at offset 0x004). The
# check below asserts that, because if the IVT layout ever moves, a
# silently wrong entry address produces a board that boots into garbage.
loader() {
    local rc=0 f
    echo "--- Boot streams ---"
    for f in chip1 chip2; do
        [ -f "$BUILD_DIR/$f.dxe" ] || continue
        if ! "$LDR21K" $PROC $LDRFLAGS \
                -o "$BUILD_DIR/$f.ldr" "$BUILD_DIR/$f.dxe" \
                > "$BUILD_DIR/$f.ldr.log" 2>&1; then
            echo "  ERROR: elfloader failed for $f (see $BUILD_DIR/$f.ldr.log)"
            rc=1
            continue
        fi
        if ! grep -q "Defaulting to 0x90004" "$BUILD_DIR/$f.ldr.log"; then
            echo "  ERROR: $f.ldr entry address is not the RSTI vector 0x90004."
            echo "         Check seg_rth placement in the LDF and src/ivt.asm."
            rc=1
            continue
        fi
        echo "  $f.ldr: $(stat -c %s "$BUILD_DIR/$f.ldr") bytes"
        # An image with a mid-stream zero-fill block is not bootable (see
        # -NoFillBlock above). Catch it here rather than at the bench.
        if ! python3 "$SCRIPT_DIR/../../../../tools/dsp/ldr_stream.py" \
                check "$BUILD_DIR/$f.ldr"; then
            rc=1
        fi
    done
    return $rc
}

# ---- Bring-up images ("is this board alive?") ----------------------------
# Standalone minimal images: one pin toggling and nothing else — no SRU,
# no SPORT, no DMA, no SEC, no SPI. They separate "the boot stream never
# landed" from "it landed but the plumbing hangs", and they are the only
# instrument that can tell those apart, so they are permanent tools, not
# scaffolding. Both link against the same LDF; the unused regions simply
# stay empty.
#
#   blink     — toggles PA_12 (LD3 on DSPA / LD2 on DSPB). Needs eyes at
#               the bench, but needs nothing else to be working.
#   rdyprobe  — toggles PB_05 (the SPI2_RDY net, which reaches the Pi as
#               GPIO8 / GPIO12). Same answer, readable over ssh.
#
# $1 = image base name, $2 = source file under src/blink/, $3 = pin note.
tiny_image() {
    local img="$1" src="$2" note="$3"
    echo "=== Build $img image ==="
    compat_banner
    resolve_ldf
    mkdir -p "$BUILD_DIR/blink"
    local rc=0 c
    for c in 1 2; do
        $ASM21K $ASMFLAGS -DCHIP_ID=$c \
            -o "$BUILD_DIR/blink/$img$c.doj" "$SRC_DIR/blink/$src" \
            || { rc=1; continue; }
        $ASM21K $ASMFLAGS -DCHIP_ID=$c -nwc \
            -o "$BUILD_DIR/blink/${img}_ivt$c.doj" "$SRC_DIR/blink/blink_ivt.asm" \
            || { rc=1; continue; }
        $LD21K $LDFLAGS -Map "$BUILD_DIR/$img$c.map.xml" \
            -o "$BUILD_DIR/$img$c.dxe" \
            "$BUILD_DIR/blink/${img}_ivt$c.doj" "$BUILD_DIR/blink/$img$c.doj" \
            || { rc=1; continue; }
        "$LDR21K" $PROC $LDRFLAGS \
            -o "$BUILD_DIR/$img$c.ldr" "$BUILD_DIR/$img$c.dxe" \
            > "$BUILD_DIR/$img$c.ldr.log" 2>&1 || { rc=1; continue; }
        if ! grep -q "Defaulting to 0x90004" "$BUILD_DIR/$img$c.ldr.log"; then
            echo "  ERROR: $img$c.ldr entry address is not the RSTI vector"
            rc=1; continue
        fi
        echo "  $img$c.ldr: $(stat -c %s "$BUILD_DIR/$img$c.ldr") bytes" \
             "(chip $c, ~$([ $c = 1 ] && echo 1 || echo 2) Hz on $note)"
    done
    compat_marker
    [ $rc -eq 0 ] && echo "=== ${img} OK ===" || echo "=== ${img} FAILED ==="
    return $rc
}

blink()    { tiny_image blink    blink.asm    PA_12; }
rdyprobe() { tiny_image rdyprobe rdyprobe.asm "PB_05 = Pi GPIO8/GPIO12"; }
# clkprobe — dumps the CGU registers and probes whether a peripheral MMR
# READ returns, all timed off the core timer so the pulse widths measure
# CCLK directly. See src/blink/clkprobe.asm; decoded by
# tools/pi/dsp4_clkprobe.py. Not a blink: it emits a frame, not a rate.
clkprobe() { tiny_image clkprobe clkprobe.asm "PB_05 = Pi GPIO8/GPIO12"; }
# sruprobe — the DAI0 half of sru_init()'s SRU writes, one at a time, in
# an image with no C, no stack and no interrupts. See
# src/blink/sruprobe.asm; decoded by tools/pi/dsp4_clkprobe.py --rle.
sruprobe() { tiny_image sruprobe sruprobe.asm "PB_05 = Pi GPIO8/GPIO12"; }

# ---- Boot-size probe (see src/blink/bulkprobe.asm) -----------------------
# rdyprobe plus a slab of never-executed code, at five sizes, chip 1 only.
# Built as a ladder because the question is where slave boot stops
# working, not whether one particular size does.
bulkprobe() {
    echo "=== Build bulkprobe ladder (chip 1) ==="
    resolve_ldf
    mkdir -p "$BUILD_DIR/blink"
    local rc=0 b
    for b in ${BULK_LEVELS:-0 1 2 3 4}; do
        $ASM21K $ASMFLAGS -DCHIP_ID=1 -DBULK=$b \
            -o "$BUILD_DIR/blink/bulkprobe$b.doj" "$SRC_DIR/blink/bulkprobe.asm" \
            || { rc=1; continue; }
        $ASM21K $ASMFLAGS -DCHIP_ID=1 -nwc \
            -o "$BUILD_DIR/blink/bulkprobe_ivt.doj" "$SRC_DIR/blink/blink_ivt.asm" \
            || { rc=1; continue; }
        $LD21K $LDFLAGS -Map "$BUILD_DIR/bulkprobe$b.map.xml" \
            -o "$BUILD_DIR/bulkprobe$b.dxe" \
            "$BUILD_DIR/blink/bulkprobe_ivt.doj" "$BUILD_DIR/blink/bulkprobe$b.doj" \
            || { rc=1; continue; }
        "$LDR21K" $PROC $LDRFLAGS \
            -o "$BUILD_DIR/bulkprobe$b.ldr" "$BUILD_DIR/bulkprobe$b.dxe" \
            > "$BUILD_DIR/bulkprobe$b.ldr.log" 2>&1 || { rc=1; continue; }
        echo "  bulkprobe$b.ldr: $(stat -c %s "$BUILD_DIR/bulkprobe$b.ldr") bytes"
    done
    [ $rc -eq 0 ] && echo "=== bulkprobe OK ===" || echo "=== bulkprobe FAILED ==="
    return $rc
}

case "${1:-build}" in
    clean) clean ;;
    build) build ;;
    all)   clean && build ;;
    blink) blink ;;
    rdyprobe) rdyprobe ;;
    clkprobe) clkprobe ;;
    sruprobe) sruprobe ;;
    bulkprobe) bulkprobe ;;
    count) count ;;
    single) single "$2" ;;
    *)     echo "Usage: $0 [clean|build|all|blink|rdyprobe|clkprobe|sruprobe|bulkprobe|count|single <asm-file>]"
           exit 1 ;;
esac
