# Fixed vs floating point for the FPGA audio path

Question: to keep code as consistent as possible with the SHARC
firmware, should the FPGA work audio in fixed or floating point?

Short answer: **if we may pick silicon with hardened FP32 DSP blocks,
use FP32 end-to-end — that maximizes consistency with the SHARC. If we
end up on mid-range fabric without hard FP, use fixed-point inside the
engines but keep every interface float — consistency then lives at the
boundaries, enforced by the golden model.** Decide the platform and the
format together; they are one decision, not two.

## The consistency landscape

The SHARC kernels are FP32 (2156x native). "Consistent" can mean three
different things, worth separating:

1. **Contract/host consistency** — cell values, tables, addresses,
   ramps. Format-independent; identical either way (see README).
2. **Coefficient-pipeline consistency** — the math that turns cell
   values into biquad coeffs, envelope rates, gain words. Keep this
   FLOAT in both worlds regardless of the audio path: it runs at
   control rate, costs nothing, and means one shared derivation
   (today's kernels / a shared library / the Pi). Fixed-point engines
   then quantize coefficients at load time, in one documented place.
3. **Sample-path consistency** — the per-sample arithmetic itself.
   This is the real question.

## FP32 sample path

For: near-1:1 port of the existing kernel semantics (same headroom
model — no per-node scaling analysis, no saturation design), same
failure modes as the shipping DSP, golden-vector deltas tiny, one
mental model across firmware and fabric. Engineers touch one numeric
world.

Against: on fabric WITHOUT hardened FP, every multiply-add costs
several DSP slices + LUTs + deep pipelines — it wrecks the
time-multiplexing budget that makes the FPGA attractive. With hardened
FP32 (Intel Cyclone 10 GX / Arria 10 / Agilex: hard FP32 FMA per DSP
block; AMD Versal DSP58: native FP32) the penalty mostly disappears —
FP32 FMA at one op/block/cycle. Also inherit FP32's known audio wart:
24-bit mantissa makes low-frequency biquads noisy/sensitive — the
SHARC has the same wart, which is exactly what "consistent" means; we
live with it today.

## Fixed-point sample path

For: native on ALL fabric (18×19/27×27 multipliers, 48-64-bit
accumulators), highest channel count per dollar/watt, deterministic
rounding, and *numerically better than FP32* for the biquad-heavy parts
(wide accumulators kill the LF noise issue; no denormals). This is the
classic big-console approach.

Against: it is a genuine second numeric world: per-node headroom/
scaling analysis, saturation policy, wrap-vs-clip decisions, and the
dynamics side-chain (log/exp shaped curves) needs LUT/poly redesign.
Every kernel needs re-verification, and future DSP-side algorithm
changes must be re-ported rather than re-generated. That's the
consistency cost — paid forever, not once.

## Recommendation

1. **Make hardened-FP silicon a strong selection criterion.** If the
   larger-mixer platform lands on Agilex/Cyclone 10 GX or Versal, run
   the audio path FP32 and the port stays a translation, not a
   redesign. This is the maximum-consistency outcome and the default
   position.
2. **If the platform forces fixed point**, contain it: engines are
   fixed (27-bit data, ≥48-bit accumulators, saturating), but all
   interfaces — coefficients in, meters out, golden vectors — stay
   float, converted at one boundary per engine. Above that boundary
   the two targets remain identical.
3. **Either way, promote `dsp_simulate.py` (float64) to the normative
   reference now.** Both FP32-SHARC and any fixed engine are
   approximations of the float64 model; parity is defined as
   tolerance-vs-golden, not target-vs-target. This also retroactively
   tightens SHARC validation.
4. Skip the middle grounds (block floating point, mixed per-node
   formats) — they buy little and cost a third mental model.

## Option C: all-fixed everywhere (the 21564 is dual-format)

Correction worth recording: the SHARC+ core is genuinely dual-format —
32-bit fixed point runs natively at the same single-cycle throughput as
float, with 80-bit MAC accumulators (wider than anything we'd build in
fabric). So if the FPGA lands on fixed point, a third option exists:
run the SHARC fixed too, sharing ONE numeric design (Q formats,
saturation policy, wide accumulators) across both targets — the
tightest consistency of any option, plausibly near-bit-exact, and it
would improve the SHARC's LF biquad noise as a side effect. Because
kernels are generated, this is a generator rewrite, not a hand-port.

Sequencing recommendation: NOT now. DSP4 is ~80% written in float,
fit-proxy verified, and un-run on hardware — reopening the numeric
foundation before first bring-up is schedule risk for no immediate
gain. Ship DSP4 float; when the FPGA activates AND lands on fixed,
weigh option C then, knowing the fixed-point design work (scaling
analysis, log/exp shaping for dynamics) is shared between targets
rather than duplicated.

One nuance worth writing down: even in the all-FP32 case, consider
fixed-point (or FP32-with-wide-accumulator tricks) for the mix summing
specifically — summing 128 sends in FP32 has order-dependent rounding,
whereas a 64-bit fixed accumulator is exact and order-independent.
The SHARC sums in FP32 today, so this would be a deliberate,
documented *improvement*, not an inconsistency.
