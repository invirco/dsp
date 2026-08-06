# 32-ch tier sizing pass — closes the D7 "Lattice 18×18" gate

Status: first pass, 2026-08-06. Answers the D7 design gate *"Lattice 32-ch
sizing incl. the 18×18 composition factor"* and the question behind it —
does Lattice's narrower DSP primitive cost us against Xilinx at this tier?

**Verdict: no. DSP capacity is not the constraint on either candidate, and
the 18×18 composition factor is not a differentiator at our operand widths.
The 32-ch part choice is a DRAM-interface and pin question.**

Candidates: **Lattice ECP5-85 (LFE5U-85F)** vs **AMD Spartan US+ SU35P
(XCSU35P)** — the pairing left standing after the 2026-08-05 price
correction (CPNX-100 at ~$131 catalog removed it from the cheap slot; see
`platform-shortlist.md`).

## 1. Workload (from MW/D32/DEFS/d32.csv, at 96 kHz)

The 32-ch tier is 32 ch, 12 aux, 4 grp, 12 mtx, LR main, 1 sub —
**~31 bus destinations**.

| Item | Count | MACs/sample |
|---|---|---|
| Matrix sends (32 ch × 31 dest) | 992 | 992 |
| Channel biquads (32 × [4 EQ + HPF + LPF]) | 192 biquads | 960 |
| Aux biquads (12 × 4 EQ) | 48 | 240 |
| Group biquads (4 × 4 EQ) | 16 | 80 |
| Main GEQ (31 bands × LR) | 62 | 310 |
| Dynamics (ch comp+gate, aux/grp/main comp+lim) | ~90 units | ~500 |
| **Total** | | **~3,100** |

Biquads are 5 MACs each (offset-coefficient DF1, `shared/numeric-spec.md`).
`ch.fir` — the biggest DSP swing factor in the d128 budget — **is not in
d32.csv**; it is a flagship feature, so it does not load this tier.

At 250 MHz a 96 kHz sample period is ~2,600 cycles, so ~3,100 MACs needs
**two time-multiplexed MAC lanes** (one lane at 400 MHz).

## 2. The 18×18 question

Operands are Q4.28 × Q4.28 — **32×32** on both sides (data AND
coefficients; `shared/numeric-spec.md` stores biquad coefficients and
linear gains in Q4.28).

| | Primitive | Primitives per 32×32 |
|---|---|---|
| Xilinx US+ | DSP48E2, 27×18 | ceil(32/27) × ceil(32/18) = **4** |
| Lattice ECP5 | sysDSP, 18×18 | ceil(32/18) × ceil(32/18) = **4** |

**Same count.** The 18×18 penalty only appears when operands fit Xilinx's
asymmetric 27×18 shape but not 18×18 — e.g. a 27-bit data path with ≤18-bit
coefficients would be 1 DSP48E2 vs 2 sysDSP. That is not our numeric spec,
and narrowing coefficients to 18 bits is ruled out by the LF biquad
measurements behind D5.

Two MAC lanes × 4 primitives = **~8 multiplier primitives**:

| Part | DSP resource | Our demand |
|---|---|---|
| ECP5-85 | 156 × 18×18 (78 sysDSP slices) | ~5% |
| SU35P | 48 DSP48E2 *(needs confirming, see §5)* | ~17% |

Both have an order of magnitude of headroom. Xilinx's real advantages are
elsewhere and do not change this verdict: DSP48E2 cascade + 48-bit
accumulator sum partial products inside the DSP column with no fabric
logic, and the blocks clock higher. Neither vendor reaches the ≥64-bit
accumulation the numeric spec requires for exact mix summing — that is
fabric adders on both.

## 3. The actual constraint: delay memory

`MW/D32/DSP/dsp-def.md` already budgets the D32 delay pool at 48 kHz, using
the *optimised* tiered scheme (20 ms × 32 fixed + 8 extended slots @ 250 ms):

| Buffer | 48 kHz |
|---|---|
| Input channel delays (tiered, N=8) | 474 KB |
| Aux output delays ×12 @ 250 ms | 576 KB |
| Main out delays ×4 @ 250 ms | 192 KB |
| Monitor delay | 47 KB |
| **Subtotal (excl. reverb tanks)** | **~1.29 MB** |

**At 96 kHz that doubles to ~2.6 MB ≈ 20.6 Mb.**

| Part | Total block RAM |
|---|---|
| ECP5-85 | 3.7 Mb (3,833,856 bits EBR) |
| SU35P | 1.7 Mb (48 × 36 Kb) |

Neither is within 5× of the requirement. **External DRAM is mandatory at
this tier on either vendor** — the delay pool is a memory-interface
question, not a BRAM question, and ECP5-85's 2.2× BRAM advantage buys
coefficient/state tables and DDR burst buffers, not delay lines.

This confirms the `fpga/README.md` position ("real constraints: BRAM, a DDR
interface, pins") and promotes DRAM support to the deciding criterion at
32 ch.

## 4. What decides the 32-ch part, in order

1. **DRAM interface** — what each part supports (ECP5 DDR3 vs SU35P
   DDR4/LPDDR4), soft vs hardened controller, and the LUT cost of the
   controller. Then the XDELAY access pattern against it.
2. **Pins** — TDM lanes + DRAM + RGMII; the per-tier pin budget (D7 gate,
   still open) is the same table this needs.
3. **Fmax** — sets whether 1 or 2 MAC lanes, and how deep the TM engine
   multiplexes. Not a capacity risk either way.
4. **Price** — post-correction, SU35P is ~$86.89 catalog; ECP5-85 needs a
   real quote (the ~$25-50 figure in the old shortlist was for small ECP5
   module parts, not this one).
5. **DSP capacity** — last, and only if `ch.fir` ever descends to this tier.

## 5. Open / unverified

- **SU35P DSP48E2 count (48)** comes from search summaries of the AMD
  selection guide, not a primary table read; SU35P also has 48 × 36 Kb BRAM
  blocks, so the two figures may have been conflated. Confirm against DS930
  before quoting it. The verdict is insensitive to this — even 48 leaves
  ~17% utilisation.
- ECP5-85 and SU35P **DSP Fmax** not captured.
- **DRAM support per part** not captured — item 1 above, and the next thing
  to chase.
- Reverb tank memory excluded from the delay total (528 KB at 48 kHz for
  6 engines on D32); FX placement at this tier is fabric-light per D7.

Sources: Lattice ECP5 family (156 × 18×18, 3,833,856 bits EBR) via
[fpgakey LFE5U-85F](https://www.fpgakey.com/lattice-parts/lfe5u-85f-8mg285i);
Spartan US+ resources via the
[AMD UltraScale+ Product Selection Guide](https://www.mouser.com/pdfDocs/amd-ultrascale-plus-fpga-product-selection-guide.pdf)
and [DS930](https://docs.amd.com/r/en-US/ds930-spartan-ultrascale-plus).
