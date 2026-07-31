# Float→fixed conversion plan for the SHARC kernels (pre-shipping window)

Context: 21564 firmware has not shipped or run on hardware, so the
numeric foundation CAN still be changed. This plan prices converting
the kernels to the shared fixed-point spec (number-format.md, option C
/ single-format verdict) while KEEPING the float backend.

## Contract-preserving design (the key constraint)

The SPI wire already carries float32 words. Do NOT change the wire:
convert float→fixed ON-TARGET at the parameter-write/ramp boundary
(one conversion routine in the dispatch/ramp path). Consequences:
- mx26 contract, cell tables, address map, ghost_cells, H1S1 headers,
  Pi tooling: ALL untouched. No contract bump.
- The whole conversion is contained in: kernel generators, asm lib,
  and the ramp/dispatch boundary.

## Keeping the float work

`dsp_codegen.py` gains a `--format fixed|float` backend switch; float
kernel emission stays intact and regenerable. Float remains the DEFAULT
build until the fixed build passes the golden harness — hardware
bring-up proceeds on float regardless of conversion progress.

## Mixed-format escape hatch (removes the biggest risk)

The SHARC+ is dual-format per instruction: FX engines (reverbs — the
one genuinely hard fixed redesign, feedback-loop stability etc.) can
simply STAY FLOAT on the same core, indefinitely. Fixed strips/buses +
float FX is a fully supported steady state.

## Work breakdown

1. Format spec (Q-format e.g. Q4.28 samples, coeff formats per family,
   saturation policy, headroom) — SMALL; the review-heavy part.
2. Golden harness: Python fixed-point reference models per kernel +
   vector export/tolerance compare in dsp_simulate.py — MEDIUM;
   shared cost with the FPGA project; DO THIS FIRST.
3. Biquad family (shared core: EQ/HPF/LPF/GEQ/xover/anti-FB) — MEDIUM.
4. Gains/faders/pan/routing/summing/DCA/ramps/meters — MEDIUM (simple
   math, many generators). Mix summing gains exact 80-bit accumulation.
5. Dynamics (gate/comp/limiter) — LARGE: log2/exp2 approximants for the
   gain computer in fixed, knee curves; the real kernel work.
6. FX engines — DEFERRED (stay float; convert later only if ever
   needed: +1-2 weeks).
7. Codegen plumbing (--format flag, dual lib variants, build) — SMALL-
   MEDIUM.

Estimate: ~2-3 weeks of focused sessions to fixed-parity on
strips/buses/summing (parity = golden harness within agreed tolerances
+ clean fit-proxy builds), FX remaining float.

## Sequencing

Golden harness first (item 2) — it is the acceptance test for the
fixed port AND the future FPGA, and retroactively tightens the float
firmware. Then spec (1), then families 3→5 in order of increasing
difficulty, converting the default build only when everything passes.
