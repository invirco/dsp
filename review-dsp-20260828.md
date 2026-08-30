# DSP codebase review — 2026-08-28 (efficiency floors, correctness sweep, headroom proof)

provenance: AI-drafted 2026-08-28 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

Desk review against the tree at HEAD (84ec0d1) and this week's calibrated
record (`MW/D32/DSP/dsp4-function-costs.csv`, 2026-08-28 fourth session;
`dsp4-cycle-budget.md`). FINDINGS ONLY — nothing in the tree was changed,
nothing was built, nothing was flashed. Every claim carries file:line.
Where a claim needs a measurement that does not exist, it says "needs
measurement" instead of arguing.

Findings are numbered D1–D43, grouped by axis (the numbering is not
dense: D15 and D17–D19 are unassigned). Severity: **SEVERE** (wrong
audio the record cannot see), **MAJOR** (correctness hazard or a
capacity-relevant structural defect), **MODERATE**, **MINOR**. Effort:
S (< half a day), M (a session), L (multiple sessions).

### Index

FIX SESSION 1 (2026-08-29) closed D1, D2, D3, D5, D6, D8, D9, D10, D11,
D12 and D33. FIX SESSION 2 (same day) closed D14, D21, D22 and most of
D25, WITHDREW D23 as misread, and left D20 and D24 open with the
measurements that say why. The `status` column carries the commit. D13
was already cleared by the review itself.

| # | sev | one line | effort | status (2026-08-29) |
|---|---|---|---|---|
| D1 | SEVERE | 64-bit bus accumulators wrap at Σ ≥ 128.0 linear; mr2f discarded, no saturation before readout | M | **FIXED** 87fded2 — 80-bit [lo,hi,ex] accumulators, +2.003 c/MAC measured on the part; 57/57 bit-exact, negctl 31/31 |
| D2 | MAJOR | biquad efb 64-bit store-back wraps for \|acc\| ≥ 2^63 (extreme coefficient sets); model unbounded | S (bound it) | **BOUNDED** dfa02b0, **RE-MEASURED 2026-08-29 AND THE MARGIN IMPROVED**: reachable \|efb\| = 2^61.648, 1.352 bits (2.553×), against 2^62.606 and 0.394 bits. The old worst set was one of the 1,323 whose n1 saturated at conversion, so the bound was measuring a more extreme filter than the settings ask for. Halved-n1 fixed that as a side effect |
| D3 | MAJOR | crossfade blend's 32-bit new−old difference wraps at straddled full scale mid-swap | S | **FIXED** 87fded2 — difference via two MRF MACs, same instruction count; proven on the part with the D33 model |
| D4 | MINOR | COMP blend / TUBE gain add unguarded against out-of-range host params (needs DEFS clamp answer) | S | open |
| D5 | MAJOR | chip-2 main mix reads USB/BT one sample stale (shipping call order) | S | **FIXED** 5998698 — chain order resolved from the graph + a cycle check in two independent tools; chip 1 byte-identical |
| D6 | MAJOR | legacy peak decay 0.99950 derived for 1500 blocks/s, applied at 6000 → 4× fast, shipping image | S | **FIXED** 1cbd9a1 — DSP4_MTR_DECAY_F32 from the block rate; τ 0.333 s → 1.333 s in the SHIPPING image |
| D7 | MAJOR? | four loop shapes violate the recorded call-in-last-3 rule — incl. shipping RTG, which measurably works; rule needs the SHARC+ Core PRM (not in local docs) | S | open |
| D8 | MINOR | dead `_biquad_cascade_N` has `rts` as its loop-end — remove | S | **FIXED** a774437 — dead block routines removed; `_biquad_cascade_N` rewritten (its `rts` was the loop-end, so it ran ONE stage) |
| D9 | MINOR | generator odd-tail pool comment contradicts the code | S | **FIXED** 96f58d4 — comment corrected to _P1, rule stated; tree byte-identical |
| D10 | MAJOR | `gen_dsp.py` bakes ramp frame counts at the block-32 frame period → ghost_cells 4× wrong | S | **FIXED** d21da3a — frame period imported from dsp_codegen; ghost_cells frame counts ×4, now agree with ramp_tables.asm |
| D11 | MINOR | stale unused `#define BLOCK_SIZE 32` in sport_init.asm | S | **FIXED** 2b336d3 — the four dead defines removed; image byte-identical |
| D12 | MAJOR | generation-time `.var` sizes vs build-time `DSP4_BLOCK_SIZE`: no consistency check; silent OOB on mismatch | S | **FIXED** 39eaa40 — `#if DSP4_BLOCK_SIZE != N / #error` in all four baking files; negative control FAILS the build |
| D13 | — | literal sweep otherwise CLEAN: the `lcntr=31` class is extinct (evidence in Axis 3) | — | cleared, not a fix — the two dead biquad routines it named left with D8 |
| D14 | MAJOR | block-kernel builds: legacy input-peak scan reads never-written slot vars → frozen host meters + waste | S | **FIXED** f179002 — scan returns immediately under block kernels; confirmed the slot vars are never written (`_scatter_chip1` already early-returns), so no host value changes |
| D16 | MAJOR | chip 2 has no block kernels: block-8 record is chip-1-only; block-8 shipping gated on chip-2 conversion | L | open |
| D20 | MAJOR | GAIN=1MAC fold ruled, not yet implemented (−17 c/s/strip) | S | **STILL BLOCKED, and the metering half is now settled 2026-08-29 (session 5).** PW's wide-word ruling took the METER off the rounded post-trim store — the meter accumulates the MS word of GAIN's own product in register and nothing is stored for it. That does not unblock the fold, because the ruling's premise ("BLK_TAP_TRIM's only consumer is a meter") is not the graph: the ROUTER reads it for pickoff 0 and needs a Q4.28 sample, and GAIN still has to write BLK_CHAIN_B for FILT. The −17 is the round/saturate plus those two stores, so what remains of D20 is the GAIN→FILT COEFFICIENT fold (g into stage 1's b0/nh/n2) plus an on-demand materialisation of the post-trim tap for the sends that actually select pickoff 0 — a numeric-spec amendment, not a meter question. Said in the emitted node |
| D21 | MAJOR | biquad inner loop ~1.6–2× over packed floor (branch saturation, no multifunction packing) | M | **FIXED** 7c0bae9 — branch-free conditional-move saturation, the rounding half out of MRF, x-history shifted before the extraction to cover the multiplier latency; bq_selftest ndiff 0/64 on real data |
| D22 | MAJOR | RTG rebuilds control state every block: 15–29× over floor, largest gap in the strip | M | **FIXED** f179002 — per-strip control-epoch counter bumped by the SPI handler, plus published ramp-busy words; 0 of 256 bus words differ against the pre-batch golden |
| D23 | MAJOR | `_acc64_mac_blk` reloads the 64-bit accumulator every sample (~3.4× on the accumulate) | S | **WITHDRAWN as written** — the accumulator is BLOCK triples, one per SAMPLE, not one per bus: the "load once, 8 MACs, store once" form the finding prescribes does not exist. The reload is per-sample because the accumulator is. See the session outcome for what is and is not available here |
| D24 | MAJOR | per-block parameter conversion belongs at control rate (dirty flag); also most of the pair drivers' overhead | M | **RE-EVALUATED 2026-08-29 — THE MEMORY OBJECTION IS GONE, THE CYCLE CASE IS NOT MADE.** The paired+fused build now has 11,942 bytes free against the 1,312 that blocked it, so the ~1,124-byte gate fits with room. What has not changed is what it buys: ~9 cycles/sample against a paired strip of ~1,187, i.e. 0.76 % — below the ±2 % band this profiling instrument has always shown, and 0.24 of a channel against ceilings whose granularity is one channel in 22 (4.5 %). Landing it could not move a single measured row. NOT landed; the decision is now PW's on grounds of value, not of memory. The real prize named in the finding — the pair drivers' sample-0 overhead — is still a restructure, not a gate |
| D25 | MINOR | batched small wastes: SEND copies, EQ tap loop, TUBE bypass copy, DLY addressing, dead scan | S ea | **PARTLY FIXED** f179002 — DLY circular DAG addressing (17 → 5 instr/sample), the 37 INTERCHIP_SEND copy bodies deleted, dead scan with D14. EQ tap fold and TUBE bypass NOT taken: both ~2 c/s against a slot-protocol change, costed in the session outcome |
| D26 | MAJOR | meter model never exercised by golden_harness | S | open |
| D27 | MAJOR | `_bq_fx_convert_N` (the b1=0 site) has no automated regression | S | open |
| D28 | MAJOR | COMP wet path (makeup 2nd round + parallel blend) unmodelled | S–M | open |
| D29 | MAJOR | TUBE: zero coverage of any kind; active cost also unmeasured | S | open |
| D30 | MODERATE | GATE node state machine unmodelled | M | open |
| D31 | MODERATE | FDR pan law / level·dca unmodelled (site of the squared-gain bug) | S | open |
| D32 | MODERATE | bench probes reimplement rns() instead of importing fixed_ref | S | open |
| D33 | MODERATE | crossfade blend unmodelled (blocks D3's fix from being provable) | S | **FIXED** 258bde2 — fixed_ref.xfade_blend + boundary_vectors.py; harness 9/9 → 16/16 |
| D34 | MINOR | TDM boundary conversions have zero test surface | S | open |
| D35 | MINOR | in-part selftests are ASM-vs-ASM only | M | **PARTIAL 6938840** — the biquad now has an asm-vs-MODEL instrument on the part: `tools/pi/dsp4_bq_verify.py` reads bq_selftest's own coefficients, stimulus and both result buffers off the DSP and re-runs fixed_ref over the same words, with a negative control that fires. 0 of 16 on both cascade forms. The dynamics self-test and the pair self-test are still ASM-vs-ASM |
| D36 | MINOR | spec bookkeeping: "9/9" stale, −90 dBFS null test untooled, NOISE exception undocumented | S | PARTIAL 87fded2 — the stale "9/9" is corrected to 16/16 and the spec now records where the bit-exact half is checked; the −90 dBFS null test and the NOISE exception are still open |
| D37 | MAJOR | gate_gr/comp_gr taps unresolvable (needs mx26); comp_gr served as a live literal-0 cell | — | open |
| D38 | MAJOR | ~600 writable-but-inert SPI slots (comp/gate routing, AFB no bypass, FX surface, DCA, MON, TALK) | M–L | **ENUMERATED** — `tools/dsp/wire_contract.py` makes it a generated artefact: **896 addresses naming 762 master cells**, by kernel class, in `docs/contract/inert-cells-d38.md`. The estimate was low. The test is conservative in the safe direction — a symbol reached by OFFSET from a used neighbour (70 addresses, the meters among them) is counted separately rather than claimed dead — so everything on the list is provably unreferenced by any emitted line. WIRE-vs-RESERVE is still PW's prioritisation |
| D39 | MAJOR | GateRng: masters say dB, kernel treats wire value as linear — documented writes give garbage | S | **FIXED** — the kernel now converts dB→linear at block rate (`10^(-dB/20)` via `_exp2q_fx`, clamped to the documented 0..60 dB) in both the per-sample and block-kernel GATE bodies. Proven on the part by `conform.sh`, before and after on the same instrument: **before**, 20/40/60 dB all returned `0xFFFFFFFF`; **after**, 20 dB gives `0x0199999A` and 40 dB `0x0028F5C3` exactly, 60 dB within 1 LSB, 0 dB within 27 LSB of unity (the exp2 table's own error). The negative control — predicting from the unit the kernel used to assume — fails all four values, so the check is testing the unit |
| D40 | MAJOR | CompPar: masters say percent, kernel wants 0..1 — control is all-or-nothing | S | **FIXED** — clamped to the documented 0..100 and scaled by 2^31/100. Before: 25 % and 50 % both pinned at `0x7FFFFFFF` (fully wet, the control dead). After: `0x20000000` and `0x40000000` exactly, 0 % and 100 % unchanged. Same instrument, same run |
| D41 | MAJOR | ms-vs-native units (att/rel alphas, delay samples, hold samples) + float32-wire contract contradiction — needs a per-cell wire table (cross-repo) | M | open |
| D42 | MODERATE | pan law linear vs documented constant-power (~3 dB centre dip) — PW decision, not a quiet fix | S | open |
| D43 | MODERATE | D24: orphaned gate DEFS cells; family allowlist never checks D24 | S | open |
| D44 | MAJOR | `_bq_pair_blk` carries its scatter-back pointers in registers across `_bq_fx_cascade_simd`, which writes r0-r15 | S | **FIXED** 2fadf39 — five words of DM at block rate. This WAS the paired-cascade "hang": the scatter ran on the cascade's leftovers and the state loop took lcntr = 0x10000000, so the part spent 268 million iterations per call scribbling, with the diag ISR still answering. Negative control `DSP4_BQP_NOSAVE=1` reproduces the session-2 symptom verbatim |
| D45 | MAJOR | DLY's per-sample body is unreachable under `DSP4_BLOCK_KERNELS` (its block kernel has no fallback into it) yet still linked — 13,568 bytes on chip 1 | S | **FIXED** 81b5ee4 — gated `!DSP4_BLOCK_KERNELS` in the generator. This is most of what unblocked the fused+paired link |
| D46 | MAJOR | `dyn_selftest` was gated on `DSP4_SIMD_DYN`, so an instrument rode in every paired build including a shipping one — 2,240 bytes | S | **FIXED** 81b5ee4 — its own `DSP4_DYN_SELFTEST`, defaulting to `DSP4_SIMD_PROBE` so dynst.sh is unchanged |
| D47 | MINOR | `lib/dynamics.asm` and `lib/delay.asm` are float-era routines with no caller anywhere, linked because they are on the linker's command line — 888 bytes | S | **FIXED** 81b5ee4 — gated out of block-kernel builds. Deleting them outright would move every address after them, so it waits for an authorised shipping-image change |
| D48 | MAJOR | ten low-shelf design sets (18.9-20 kHz, +14..15 dB, shelf-Q 2.8-3.5) still saturate n1 even at Q5.27: \|n1\| reaches 17.835 | S (a ruling) | **OPEN — PW range decision.** The halved-n1 encoding cleared 1,313 of the 1,323 saturating sets; no encoding at this width reaches the last ten. Either the DEFS bound low-shelf f0 (a low shelf at the top of the band is not a control anyone means to offer) or n1 needs a third bit and a third MAC. Until then those ten convert to a different filter, silently |
| D49 | MINOR | `dsp_codegen.py` wrote `tools/pi/dsp4_block.py` from the SCRIPT's location, not the output tree, so generating a scratch tree at another block size relabelled the bench verdict for every later run | S | **FIXED** — the file is now written beside the generated tree always, and into `tools/pi` only when `DSP4_GEN_BLOCK` is unset. Harmless in practice (the honest full-rate rule is applied by hand, not read off the label) but it made every block-8 log say "of 1500" |
| D50 | MODERATE | chip 2's `C2_AUX_DLY_*` nodes take the non-pool DLY template and so have no block kernel at all | S–M | open — chip-2 workstream, see D16 |
| D51 | MAJOR | the EQ/GEQ/FILT wire plane carries biquad COEFFICIENTS, not the parameters the masters document: 1,036 master cells collapse onto 322 addresses, and `Chan001EqFreq001`, `EqGain001`, `EqQ001` and `EqShelf001` all resolve to word 0 of `_eq_coeffs_next_C1_EQ_01`. The host is therefore expected to compute the biquad, which no line of the masters says | M (a contract page, cross-repo) | open — enumerated in `docs/contract/wire-units-proposals.md`, raised as a proposal for mx26 |
| D52 | MODERATE | the masters name THREE main output chains (`MainL`, `MainR`, `MainSub`) and the DSP has FOUR (`C2_MAIN_OEQ/OCOMP/OLIM_01..04`, addressed as `Main001`..`Main004`); nothing in either repo states the correspondence, so 134 documented main-output cells cannot be resolved to an address by name | S (a ruling) | open — cross-repo, mx26 |
| D53 | MODERATE | 1,331 documented cells reach no DSP address after subtracting `mcu-only-prefixes.txt` — the largest blocks are `Chan_Rtg` (608), `FxCtrl` (241) and `ChanInput` (192: AntiClip, Color, InsertOn, LcrOn, Link, PadOn, all present in `_matrix.csv`). Nothing in the tree records whether that is intended | M | open — table in `docs/contract/wire-units-proposals.md` |
| D54 | MODERATE | **1,244 mapped addresses carry a documented non-Instant ramp profile but have no ramp state** (`_spi_dispatch_*_stride` = 0), so `spi_handler` falls back to the plain instant write and the profile in the wire word is discarded: DynSafe 395, EqSafe 777, GainFast 42, GainSafe 30. EqSafe is defensible — the EQ/FILT coefficient sets ramp by dual-instance crossfade rather than by `_ramp_set_target` — but that leaves 467 addresses, `Chan001GateThr001` among them, whose documented ramp simply does not happen. Measured on the part: a DynSafe threshold write arrives in 2.7 ms against a documented 20 | S–M | open |
| D55 | MAJOR | **FILT's and EQ's TRANSIENT block paths used different pool slots from their steady-state paths and from each other**: FILT's crossfade path wrote `BLK_CHAIN_A` while its steady path worked in place on `BLK_CHAIN_B`, and EQ's crossfade path READ `BLK_CHAIN_A`. Consistent only when both classes crossfade at the same time. With EQ crossfading and FILT steady — an EQ band written while the filters sit still, which is the common case — EQ cascaded the block GAIN read instead of the one it wrote, so the strip's trim, HPF and LPF vanished for the 576 samples of the fade; with FILT crossfading and EQ steady, FILT's output was dropped on the floor. Block-kernel builds only, so not in the shipping per-sample image | S | **FIXED 2026-08-29 (session 5)** — both classes read and write `BLK_CHAIN_B` on every path, which also makes the paired FILT/EQ fallback net-preserving |
| D56 | MODERATE | **the GATE does not shut on silence at BLOCK 8, and does at BLOCK 32.** Every BLOCK-8 silence point in the session-5 ceiling sweep is witnessed `gate OPEN N / SHUT 0` with the compressors correctly on the unity path, and the scorer marks the row MIXED/UNPROVEN for exactly that reason; every BLOCK-32 silence point on the same firmware, same day, reads `gate OPEN 0 / SHUT N`. The gate's attack, hold and release constants are block-rate derived, which is the same class D6 was (the meter's peak decay, derived for 1500 blocks/s and applied at 6000). Not chased in session 5: the silence rows are a control, not a product configuration, and the signal rows are the ones the table quotes | S–M | **open, and the BLOCK-8 silence ceilings in the session-5 table are quoted as measured with the witness stated rather than as witnessed rows** |
| D57 | MAJOR | **`Chan001RtgDca001` is documented as a DCA ASSIGNMENT and the kernel treats it as a linear GAIN.** The masters give it no scale law and the `InstantCtl` profile — the shape of a selector — and the dispatch lands the written word in `_fdr_dca_gain_*`, which `FADER_PAN` multiplies into its Q4.28 coefficient. Writing the obvious "no DCA assigned" value of 0 therefore sets the strip's fader gain to ZERO and the channel goes silent, with `_fdr_level_*` still reading 1.0 and nothing else in the strip looking wrong. Found on the part 2026-08-30 when it silenced the conformance probe's driven strip three runs in a row; the chain witness located it at `_buf_C1_FDR_01 = 0` with `_buf_C1_DLY_01` carrying signal. Same class as D39/D40 — a cell served in a unit the masters do not document — and it is the one the harness's own declared-unit phase cannot catch, because `RtgDca`'s family has no unit declared in `wire-units.csv` | S | **open — needs an mx26 answer on what the cell means before the kernel moves**, and it is a PROPOSAL for `wire-units.csv` either way |

The build-flag ground truth all of this sits on: the shipping image is
still the PER-SAMPLE build (`build.sh:98` — `DSP4_BLOCK_KERNELS` defaults
0), and every capacity figure in the record was measured with
`DSP4_BLOCK_KERNELS=1`. The block-8 per-class record was taken with
`DSP4_STRIP_FUSED=0` (`dsp4-function-costs.csv:9`), so the fused biquad
gains (−32 % on FILT/EQ, measured at block 32) are **not inside the
block-8 strip figure of 11,726**. That matters for Axis 2 and it is
stated where it is used.

---

## AXIS 1 — EFFICIENCY FLOORS PER CLASS

Method. The floor is the instruction count of the emitted arithmetic
under the ruled spec — Q4.28 interchange, offset-DF1 biquad with 64-bit
error feedback, round-to-nearest-then-saturate at every 32-bit store,
the GAIN=1MAC fold amendment (PW 2026-08-28 ~17:35), polynomial
log2/exp2 (the table forms and GATE-LINTHR are unsanctioned levers,
`build.sh:150,158` both default 0) — assuming the hardware is used as the
2156x allows: one compute plus a data move per cycle (multifunction),
dual MAC+ALU where register classes permit, MRF/MRB interleave,
conditional-move saturation instead of branches, zero-overhead hardware
loops. Floors are instruction-count estimates, not measurements; they
exclude unknown memory stalls (flagged where L2 is involved). "Emitted"
is the measured block-8 figure from `dsp4-function-costs.csv` (signal
present, per sample, block-rate sections amortised over 8).

| class | emitted c/s (block 8, measured) | floor c/s | gap | dominant waste (named) | packed-replacement sketch | effort |
|---|---|---|---|---|---|---|
| IN | inside block I/O | 2–3 | ~1× | none worth naming — load/shift/store loop (`C1_IN_01.asm:123-129`) | dual-issue load with store | — |
| GAIN | 22.9 (incl. its meter) | 1–2 (under the GAIN=1MAC fold) | ~10× vs amendment; ~1.1× vs pre-amendment code | the sanctioned-but-unimplemented fold: 1 MAC + 12 round/sat instructions + 2 block stores per sample (`C1_GAIN_01.asm:202-223`); the loop already runs ~1 instr/cycle, so only the fold moves it | scale [b0,n1,n2] by g at control rate (`tasks.md:1004` derivation); keep only the tap store the meter/router need | S (ruled; "rides the next kernel session") |
| FILT (2 biquad stages) | 136.9 | 41–49 | 2.8–3.3× | unfused in the block-8 record (`dsp4-function-costs.csv:9`, `DSP4_STRIP_FUSED=0`): efb rebuilt into MRF per sample (`biquad_fx.asm:296-304`), i0 coeff reload + rewind per sample (`biquad_fx.asm:306-319`); fused form (measured 84.1 c/s at block 32) still leaves: saturation via taken branch (`biquad_fx.asm:228`), 3-MAC unity term where 2 suffice (`biquad_fx.asm:215-217` vs the scalar's 2-MAC form at `:81-83`), zero multifunction pairing of the load/store/moves | fused inner loop with: 13 MACs (2^29 register held), branch-free sat as the SIMD form already does (`biquad_fx.asm:578`), load/store folded into MAC lines → 19–23 c/stage | M |
| EQ (4 stages) | 265.75 | 79–97 | 2.7–3.4× | same as FILT ×4, plus a separate 2-op/sample tap-copy loop (`C1_EQ_01.asm:110-114`) | fold the tap store into the last stage's store (dual data move) | M (rides the biquad pack) |
| GATE | 259.75 | 60–75 (poly log2 ruled) | 3.5–4.3× | 3 call/rts per sample (`C1_GATE_01.asm:211,235,240` — `_envq_fx` ×2, `_mrf_rns28`) ≈ 30 c/s of pure call; 2 nops for the loop-tail hazard (`:241-242`); `_envq_fx`/`_mrf_rns28` bodies unpacked (each ~12 instr where ~7 pack) | inline both one-poles and the round with constants hoisted (the GAIN treatment, applied inside GATE's loop); LINTHR (−95 c/s measured, 0 of 120 samples deviate) is a stated OPTION, unsanctioned, sign-off pending | M |
| COMP | 433.1 | 110–135 (poly ruled) | 3.2–3.9× | ~9 call/rts pairs per sample (`C1_COMP_01.asm:161,164,169,172` + `_compgain_fx`'s nested `_log2q_fx`→`_polyq_fx`, `_exp2q_fx`→`_polyq_fx`, `dyn_fx.asm:299,344,181,202`) ≈ 45–60 c/s; `_polyq_fx` Horner iteration is 10 instr where ~7 pack, ×10 poly terms/sample; per-sample display store (`C1_COMP_01.asm:165`), `relq`/`i0` reloads in-loop (`:160,163`), 2 nops (`:185-186`) | inline the whole gain computer into the block kernel, pack Horner (MAC + extraction overlapped), hoist `i0`/constants; DYN_TABLES (−160 c/s GATE+COMP measured, 0.00009 dB, MORE accurate than the poly) is a stated OPTION needing the spec amendment it already has queued | L |
| TUBE | 11.6 bypassed; ACTIVE NOT MEASURED (open since 08-24) | 0 bypassed (skip + ping-pong flip); 20–24 active | copy is pure waste | bypassed: an 8-sample copy loop + call (`C1_TUBE_01.asm:86-90`) to move data nothing changed; active: 3 chained `call _mrf_rns28` (`C1_TUBE_01.asm:69-83`) | bypass: emit the strip with TUBE's slot direction folded away at generation time (slot protocol is generator-owned); active: inline the three rounds | S (bypass) / needs measurement (active) |
| DLY | 63.1 | 6–12 (+ L2 wait states, unmeasured) | ~5–10× (arith only) | write address rebuilt from base + modify every sample, read address likewise, wrap by compare (`C1_DLY_01.asm:116-133` — 5 address instructions per sample for 2 accesses); delay lines live in `seg_delay` = L2 (`C1_DLY_01.asm:23`), latency never isolated | circular DAG addressing (b/l registers do the wrap free): write `dm(i0,1)`, read via a second circular index, ~5 instr/sample | M; L2 cost **needs measurement** |
| FDR | 40.4 | 8–12 | 3.4–5× | the 17-instr round/sat loop around 1 MAC (`C1_FDR_01.asm:226-248` unfused: manual-counter loop with a branch per sample); float ramp + pan-leg section re-runs every block when idle (`C1_FDR_01.asm:66-164`, ~11 c/s amortised at block 8) | packed MAC+extract ≈ 7 c/s; ramps to true control rate (D24 below) | S–M |
| RTG | 232.6 | 8–15 | 15–29× — **the largest gap in the strip** | see D22: the whole control-rate section (18 send ramps, pickoff resolution, 25-crosspoint list rebuild, `C1_RTG_01.asm:100-571`) runs EVERY BLOCK for state that changes at control rate; plus `_acc64_mac_blk` reloads/stores the 64-bit accumulator per sample (D23) | dirty-flag rebuild + MRF-resident accumulate | M |
| MTR (new fixed meter) | inside GAIN's 22.9 | 12–16 | ~1.3× | already near floor: 4-instr loop (`C1_MTR_01.asm:65-70`; load pairs with MAC → 3), fold ~90 instr/block | dual-issue the loop; nothing else worth taking | — |
| MIX_BUS readout (×25) | ~19 instr/sample emitted (`C1_BUS_MAIN_L.asm:53-72`, block form, not separately measured at block 8) | 8–9 | ~2× | unpaired extraction, same shape as the biquad's | pack extraction with the next pair's loads | S |
| INTERCHIP_SEND | 2 mem ops/sample × 37 nodes (`C1_BUS_MAIN_L_SEND.asm:36-38`) | 0 | ∞ | the copy exists so the gather has a named array; the gather already walks a pointer table (`block_io.asm:479-516`) | point `_c1_ic_tx_ptrs` at `_buf_<bus>` / the tap arrays and delete the SEND bodies | S–M |
| block I/O + driver | ≈ 18.8k c/block fixed (derived, Axis 2) | — | — | `_meter_scan_chip1` runs 46 iterations/block reading vars that are never written under block kernels (D14); scatter loop per-sample scaffold (`main.asm:719-731`) is honest overhead | delete the dead scan under block kernels | S |

Per-channel floors for the SIMD-PAIRED forms (both channels of a pair,
divided by two, plus the measured-shape gather/scatter and sample-0
overhead the drivers pay — `dyn_pairs.asm:515-548`, `dyn_simd_fx.asm:382-402`):

| paired class | emitted c/s/channel (measured, graph) | floor c/s/channel | gap |
|---|---|---|---|
| GATE pair | 142.8 (`dsp4-function-costs.csv:60`) | 35–43 | 3.3–4.1× |
| COMP pair | 251.4 (`:61`) | 61–74 | 3.4–4.1× |
| FILT pair | not wired (biquad-pair hang unresolved, `dsp4-cycle-budget.md:146-163`) | 22–27 | — |
| EQ pair | not wired (same) | 43–52 | — |

The kernel-vs-graph gap on the dynamics pairs (2.43× kernel vs 1.82×
graph on GATE) is mostly sample 0 through the full scalar body — for
COMP that is the whole ~90-line parameter conversion every block
(`dyn_pairs.asm:578-593`). At block 8 that is 1/8 of the work through
the slowest path; at block 32 it was 1/32. A one-time-converted
parameter shadow (control-rate conversion, D24) removes most of it.

**Scaffolding that repeats per sample/block but is control-rate state**
(no ruling touched by moving it): the RTG prep (D22), the GAIN/FDR/
COMP/TUBE ramp-idle snap paths that re-store the same target every
block (`C1_GAIN_01.asm:83-85`, `C1_FDR_01.asm:92-94,121-123`), COMP's
per-sample gain-display store (`C1_COMP_01.asm:165`), and the EQ tap
copy loop (`C1_EQ_01.asm:110-114`).

---

## AXIS 2 — THE CLOSING SUM

All figures block 8, per chip, cycles per block; budget = clock / 6000.

**Fixed overhead (block I/O + fabric + driver) at block 8 is DERIVED,
not directly measured** — the record never profiled the fabric at
block 8. Derivation from the two paired-ceiling points
(`dsp4-function-costs.csv:69,78`): 16 paired strips miss by 4.2 % of
budget → F = 1.042·163,840 − 16·9,496 = **18,785**; check against the
accepted point: 18,785 + 15·9,496 = 161,225 = 98.4 % of budget ✓, and
the predicted 16-strip rate 6000·163,840/170,721 = 5,758/s against the
measured 5,756/s (0.03 %). The scalar points cross-check to 1.5 %
(12·11,726 + 18,785 = 97.3 % ✓). F is treated as clock-independent
(cycle counts are properties of the code; L2/DMA wait-state scaling is
the residual risk in that assumption).

Available for strips, and the per-strip line for 32:

| clock | budget | − F | per strip (÷32) | per sample (÷8) |
|---|---|---|---|---|
| 983.04 | 163,840 | 145,055 | 4,533 | **566.6 c/s** |
| 786.432 | 131,072 | 112,287 | 3,509 | **438.6 c/s** |

(The dispatch's goal line of ~550 c/s at 983 corresponds to F ≈ 23k;
the derived F is smaller, so 566.6 is used and the arithmetic above is
the whole of the derivation — no rounding in either direction.)

Floor strips, summed from Axis 1 (poly dynamics, GAIN-fold in, TUBE
bypassed, MTR included, block-8 amortisation included). Ranges are the
honest spread of the instruction-count estimates; the VERDICT uses the
pessimistic (high) end:

- **Scalar floor strip: 330–420 c/s**
  (IN 3, GAIN 2, FILT 41–49, EQ 79–97, GATE 60–75, COMP 110–135,
  TUBE 0, DLY 6–12, FDR 8–12, RTG 8–15, MTR 12–16)
- **Paired floor strip: 200–256 c/s/channel**
  (biquads and dynamics halved plus interleave overhead; rest scalar)

### The verdicts (in the required form)

- **983.04, scalar at floor: 32 fits at floor with margin ≥ 35 %**
  (566.6 available vs ≤ 420 floor; 43 channels at floor).
- **983.04, paired at floor: 32 fits at floor with margin ≥ 2.2×**
  (566.6 vs ≤ 256; ~70 channels at floor — the floor is not the
  constraint at this clock, the code is).
- **786.432, scalar at floor: 32 fits at floor with margin 4 %** at the
  pessimistic floor end (438.6 vs 420) and 33 % at the optimistic end —
  a fit, but thin enough that scalar-only at 786 should not be planned on.
- **786.432, paired at floor: 32 fits at floor with margin ≥ 71 %**
  (438.6 vs ≤ 256).

### Margin remaining AT 32 (PW ruling 2026-08-28 ~21:25: this column is
the deliverable — 32 is the minimum, the margin is the plugin headroom)

Cycles remaining per chip per block with 32 strips loaded, and the same
as a share of the block budget. Floor rows use the PESSIMISTIC floor
end; the optimistic end is in parentheses:

| configuration | c/s/strip remaining | c/block remaining at 32 | % of budget |
|---|---|---|---|
| 983.04, scalar at floor | 146.6 (236.6) | 37,535 (60,575) | **22.9 % (37.0 %)** |
| 983.04, paired at floor | 310.6 (366.6) | 79,519 (93,855) | **48.5 % (57.3 %)** |
| 786.432, scalar at floor | 18.6 (108.6) | 4,767 (27,807) | **3.6 % (21.2 %)** — no plugin headroom at the pessimistic end |
| 786.432, paired at floor | 182.6 (238.6) | 46,751 (61,087) | **35.7 % (46.6 %)** |
| 983.04, TODAY'S paired code | **−620.4** | −158,822 | 32 does not fit today; the margin column goes positive only as the floor work lands |

So under the margin-at-32 ruling the honest statement is: **at floors,
983.04 paired leaves roughly half the chip for plugins; 786.432 scalar
leaves essentially nothing and is not a fit in the ruling's sense.**

### What stands between today's code and those floors

Today's measured paired strip is 1,187 c/s (`dsp4-function-costs.csv:69`)
against the 566.6 line: **the emitted code misses 32-at-983 by 2.1×,
and the floor says that entire factor is in the code, not in the
rulings.** The two largest pieces: the dynamics at 3.3–4.1× over their
paired floors (394 of the 1,187), and RTG at 15–29× over (232.6 of it).
Landing D22+D23 (RTG restructure, no numeric change) and the dynamics
inlining alone reaches ≈ 700 c/s; the biquad pack and GAIN fold take it
to ≈ 480–550. Every step is bit-exact under the current rulings.

Caveats that bound this sum, stated rather than shaded:

1. **The paired biquads hang** (`dsp4-cycle-budget.md:146-163`,
   unresolved). The paired floor assumes FILT/EQ pair; until the hang
   is root-caused the paired column rests on the dynamics pairs only.
2. **Fusion at block 8 is unmeasured** — the block-8 record is
   `STRIP_FUSED=0`; fused+paired at block 8 has never been built
   together. Needs measurement before any of the ≈ 480–700 projections
   above is quoted as more than arithmetic.
3. **Chip 2 is outside every number here** (D16): it has no block
   kernels at all, measured 3.8× over budget at block 32 in silence,
   never measured at block 8. 32-in-one-21564 for the D32 PRODUCT still
   requires chip 2's graph to fit somewhere.
4. F itself contains removable waste (D14, D25) — the floors above
   leave F at its measured value rather than crediting its own floor.

---

## AXIS 6 — HEADROOM AND ROUNDING PROOF

Every 32-bit touchpoint in the audio path, and whether it can wrap.

### Touchpoints that SATURATE correctly (verified in the emitted code)

| touchpoint | mechanism | evidence |
|---|---|---|
| every strip chain-slot store | rns28 then sat by `ashift(hi,−28) == ashift(y,−31)`, branch form (`_mrf_rns28`) or conditional-move form | `mac64_fx.asm:49-66`; inlined: `C1_GAIN_01.asm:207-217`, `C1_FDR_01.asm:229-242`, fused biquad `biquad_fx.asm:219-233`, SIMD `dyn_simd_fx.asm:240-256` |
| bus readout (the single mix round) | same check per sample over the accumulator array | `C1_BUS_MAIN_L.asm:53-72` |
| TDM output Q4.28→Q1.31 | `<<3` with back-shift equality check, sat by sign | `chip2/block_io.asm:311-320` |
| TDM input Q1.31→Q4.28 | `ashift −3` (spec: truncation is the ruled conversion) | `chip1/block_io.asm:552`, `numeric-spec.md:18-20` |
| interchip TX/RX | raw Q4.28 copy, no arithmetic | `chip1/block_io.asm:584-610`, `chip2/block_io.asm:262-288` |
| delay-line write/read | copy of already-saturated words | `C1_DLY_01.asm:116-133` |
| meter block accumulators | sum of 8 squares ≤ 2^65 in the 80-bit MRF; ms_blk overflow checked (`if ne r0 = r6`), −min guarded at exactly −2^31 | `meter_fx.asm:106-135` |
| envelope one-poles | env′ bounded by max(env, x): no overflow reachable from saturated inputs | `dyn_fx.asm:237-257` (model's sat32 is defensive only) |

### Touchpoints that CAN WRAP

**D1 — SEVERE. The 64-bit bus accumulators wrap at |sum| ≥ 128.0 and
nothing saturates them.** `_acc64_mac` and `_acc64_mac_blk` accumulate
in the 80-bit MRF but store back only `mr1f:mr0f`, discarding `mr2f`
(`mac64_fx.asm:31-35`, `bus_accumulators.asm:128-135`). The stored pair
is Q8.56 in 64 bits: range ±128.0 linear. The dispatch's coherent case —
32 channels at 0 dBFS, unity routing — sums to 32.0: **that case holds
with 12 dB of margin and the answer to "are the accumulators 64-bit end
to end, saturating only at the final round" is yes-and-that-is-the-
problem: the only saturation is at readout, applied to a value that has
already wrapped.** The representable worst case is far past the
boundary: strip exits saturate at ±7.999 (+18 dBFS internal) and a
single crosspoint coefficient is Q4.28 up to 7.999 (the spec allows
+24 dB composed, +18 dB in one coefficient, `numeric-spec.md:41-42`),
so one contribution reaches 64.0 and **three such channels wrap the
bus** — 32 can exceed the boundary by 16×. A wrapped sum re-enters
range and the readout's sat check passes it as a clean wrong sample:
full-scale-opposite-sign audio, not a clip. `fixed_ref.mix_sum` uses
unbounded Python ints (`fixed_ref.py:105-109`), so the normative model
does NOT wrap — the asm diverges from the reference exactly at the
boundary, and no golden vector reaches it. Fix shapes: store mr2f (3-word
accumulators, +25×BLOCK words DM, ~2 cycles/MAC), or a saturating
accumulate, or a control-rate bound on Σ|coeff| per bus. Effort M.
Severity is per the task's own rule: a touchpoint that can wrap.

**D2 — MAJOR (bounded). The biquad error-feedback store-back can wrap
for |acc| ≥ 2^63.** The cascade's acc is exact in the 80-bit MRF, but
efb′ = acc − (y≪28) is stored as a 64-bit pair
(`biquad_fx.asm:110-117, 243-247`). With all five coefficients and all
four state words at their Q4.28 extremes the 11-term sum reaches
≈ 2^66. Table-derived stable filters stay orders below 2^63; a hostile
or corrupted coefficient SET (the wire carries raw floats;
`_bq_fx_convert_N` bounds each coefficient only to what a 32-bit `fix`
produces — and whether that `fix` saturates or wraps for out-of-range
floats is itself part of D27's untested surface) driving the recursion
unstable can reach it. Consequence: efb corruption → sustained
wrong LSBs, and divergence from fixed_ref (whose efb is unbounded,
`fixed_ref.py:85`). Bound and either accept with a written justification
or clamp acc's headroom at conversion time (bound Σ|coeff| per stage).
Effort S (analysis) — no code change may be needed, but the bound
belongs in `numeric-spec.md`.

**D3 — MAJOR (transient). The crossfade blend's 32-bit difference can
wrap mid-swap.** `r5 = r0 − r14` (new − old) in the EQ/FILT/crossover
dual-instance blend (`C1_EQ_01.asm:179`, `C1_FILT_01.asm:199`,
generator `dsp_codegen.py:5266-5292` and the crossover twin) wraps when
the two instances' outputs straddle full scale with |new−old| > 2^31−1
— reachable with hot program material during a coefficient swap, since
both operands are independently saturated ±8.0 outputs. Consequence: up
to a block of full-scale-wrong blended samples (a click), self-clearing
when the fade ends. No fixed_ref model exists for the blend at all
(Axis 4, D33). Fix: 64-bit difference via MRF (2 extra instructions on
a transient path). Effort S.

**D4 — MINOR (contingent on host ranges). COMP's parallel blend and
TUBE's gain add are unguarded against out-of-range host parameters.**
`wet − dry` (`C1_COMP_01.asm:369`) cannot wrap only because gain and
makeup are non-negative; a NEGATIVE makeup float from the host makes
wet and dry opposite-signed at full scale and wraps the difference.
TUBE's `r10 = 0x10000000 + r0` (`C1_TUBE_01.asm:77-78`) wraps for
sat > 7.0. Both are unreachable if the DEFS ranges clamp makeup ≥ 0 and
sat ≤ 1 — the firmware itself enforces neither (the comp PARALLEL clamp
at `C1_COMP_01.asm:260-271` shows the pattern that is missing here).
Cross-reference the contract audit (Axis 5). Effort S.

### Rounding-site inventory, and the single-round claim

The ruled claim (dispatch: "single round/saturate per strip"; the
record's form: ONE round at the strip boundary into the bus, one per
32-bit store elsewhere, `tasks.md:3008`) — what the emitted code does:

- **One round per store holds everywhere**: every rns is immediately
  followed by its store or feeds the next stage's exact accumulation;
  no value is rounded twice on the same path *between nodes*. The
  GAIN→FILT intermediate round exists today and its DELETION is the
  sanctioned GAIN-fold amendment (not yet implemented).
- **Within-node multi-round sites** (each rounds a chained product, as
  the float node it ports did): COMP wet path — `rns(dry·g)` then
  `rns(wet·makeup)` then the blend's rns31 (`C1_COMP_01.asm:358-380`):
  three rounds per sample, of which the makeup round is **unmodelled**
  (no fixed_ref, D28). TUBE — three chained rns28
  (`C1_TUBE_01.asm:69-83`), all three unmodelled (D29). Biquad — one
  round per stage, remainder carried exactly in efb: conformant.
  Envelope/smoother — rns31 per one-pole step: conformant
  (`fixed_ref.envelope_step`).
- Bus summing: exact 64-bit (with D1's wrap caveat), one round at
  readout: conformant with `fixed_ref.mix_sum`.

So the single-round claim holds at strip and bus boundaries; the two
in-node exceptions (COMP makeup, TUBE) are float-port structure, not
regressions — but they are exactly where no reference exists (D28, D29).

---

## AXIS 1 FINDINGS (efficiency, numbered)

**D20 — MAJOR / S. The GAIN=1MAC fold is ruled and unimplemented.**
The amendment (tasks.md:80-88) sanctions deleting GAIN's round/saturate
and the two block stores' FILT consumer; the emitted node still pays all
seventeen instructions per sample (`C1_GAIN_01.asm:202-223`). Worth
−17 c/s/strip. Implementation is already assigned to the next kernel
session; recorded here so the floor table's 10× row is not read as an
open question.

**D21 — MAJOR / M. The biquad inner loop misses its packed floor by
~1.6–2× even fused.** Named waste: saturation by taken branch
(`biquad_fx.asm:228` — the SIMD twin already has the branch-free
conditional-move at `:578`; the scalar forms should adopt it), the
3-MAC unity term (`biquad_fx.asm:215-217`) where the per-sample form
proves 2 MACs suffice (`:81-83`), and zero use of compute+data-move
multifunction lines — every load, store and register move is its own
cycle. Packed floor 19–23 c/stage vs ~30-32 emitted (fused) and ~66
(unfused block-8 record). This is 6 stages × 32 strips of the strip's
largest arithmetic block.

**D22 — MAJOR / M. RTG rebuilds control state every block — the single
largest floor gap in the strip (15–29×).** The 18 send ramps, pickoff
resolution, coefficient prep and 25-crosspoint list rebuild
(`C1_RTG_01.asm:100-571`) run unconditionally every block, for state
that changes only on SPI writes or while a ramp runs. At block 8 that
is 232.6 c/s/strip of the 1,466 scalar strip — RTG is the record's own
"largest remaining block-invariant item" (`dsp4-function-costs.csv:51`).
A dirty flag set by the SPI dispatch entries that touch this node, plus
a ramps-active counter, moves all of it to true control rate with NO
numeric change — the audio-path arithmetic is untouched, so no ruling
is implicated. Sketch: `_rtg_dirty_<nid>` set by spi_handler on any
write into the node's page range; prep runs when dirty or frames>0.

**D23 — MAJOR / S. `_acc64_mac_blk` reloads and re-stores the 64-bit
accumulator every sample** (`bus_accumulators.asm:118-137`): 11
instructions per sample per crosspoint where an MRF-resident form —
load the pair once, 8 dual-issued load+MACs, store once — is ~12 per
BLOCK (≈3.4× on the accumulate path, and it composes with whatever D1's
wrap fix chooses, since both touch the same store).

**D24 — MAJOR / M. Block-rate parameter conversion belongs at control
rate.** Every strip node re-runs its float→fixed conversion (and the
ramp-idle "snap" re-store of an unchanged target) every block:
`C1_GAIN_01.asm:59-109`, `C1_FDR_01.asm:66-164`, GATE's conversion +
exp2 (`C1_GATE_01.asm:132-196`), COMP's ~90-line conversion via the
sample-0-through-scalar-body driver (`dyn_pairs.asm:578-593`). At
block 8 this is roughly 40–60 c/s/strip across the classes, and it is
also most of the paired kernels' kernel-vs-graph gap. Same dirty-flag
mechanism as D22; bit-exact by construction (the converted values are
identical, only recomputed less often). One care point: ramped
parameters must keep converting while frames > 0.

**D25 — MINOR / S each. Batched small wastes, all named above:** the
37 INTERCHIP_SEND copy bodies (gather can read the source arrays
directly through `_c1_ic_tx_ptrs`, `block_io.asm:479-516`); the EQ tap
copy loop (`C1_EQ_01.asm:110-114`, fold into the cascade's last-stage
store); TUBE's bypass copy (fold the slot flip into generation); DLY's
per-sample address regeneration (`C1_DLY_01.asm:116-133`, use circular
DAG addressing; L2 latency share **needs measurement**); COMP's
per-sample gain-display store (`C1_COMP_01.asm:165`); the dead
46-iteration legacy meter scan under block kernels (D14).

---

## AXIS 3 — CORRECTNESS SWEEP

### Graph wiring and process order

**D5 — MAJOR. Chip 2's main mix reads USB and BT one sample stale in
the shipping image.** `_C2_MIX_MAIN_L/R_process` are called at
`chip2/process_chain.asm:831,834` and read `_buf_C2_USB_IN` /
`_buf_C2_BT_IN` (`chip2/nodes/C2_MIX_MAIN_L.asm:149,152`), but the sole
writers run at `process_chain.asm:1008,1011` — after the mix, in the
same per-sample chain. USB and Bluetooth therefore enter the main mix
one sample later than the other 15 sources (verified against the call
order; the other 15 are all called before 831). Consequence: a
one-sample skew (20.8 µs) on those two sources — audible only as a comb
if the same source reaches the bus by a second path, but it is the
wrong-graph-order class this axis exists to catch, and it is in the
shipping image. Fix: reorder the input calls ahead of the mix in the
generator's chip-2 chain emission. Effort S.

**D14 — MAJOR (block-kernel builds). The legacy input-peak path reads
variables that are never written.** Under `DSP4_BLOCK_KERNELS` the
input kernels read the DMA buffer directly and `_scatter_chip1` is a
bare `rts` (`chip1/block_io.asm:531-533`), so the 46 `_rx_slot_*`
scalars are never written (`C1_IN_01.asm:21-25` says so itself) — yet
`_meter_scan_chip1` still runs every block (`main.asm:837`) reading
exactly those scalars (`chip1/block_io.asm:560-582`) into
`_meter_peaks`, the host-visible input peak array. Every block-kernel
build reports frozen/zero input peaks, and pays ~550 c/block doing it.
The 21-meter wrong-source class, surviving in the legacy path after the
new meters were fixed. Effort S (gate the scan out of block builds, or
point it at the pool taps).

**D6 — MAJOR (shipping image). The legacy peak decay runs 4× fast at
block 8.** `_meter_decay = 0.99950` is a hand constant derived for
1,500 blocks/s (`lib/meter.asm:10-12,31`) and is applied once per block
(`main.asm:838-839`); at the ruled block-8 operating point the block
rate is 6,000/s, so the documented τ ≈ 1.33 s decays in ≈ 0.33 s. This
is the recorded meter-defect class ("a constant derived for one block
rate applied at another") in the one meter path that was NOT rebuilt,
and unlike D14 it is live in the per-sample SHIPPING build, which is
also generated at BLOCK=8. Fix: derive from `DSP4_BLOCK_RATE` in
`dsp_block.h` like `DSP4_MTR_ALPHA_Q`/`BETA_Q` were. Effort S.

### DO-loop tails vs the two recorded SHARC hazards

The recorded rules (tasks.md:1143-1147): (a) a DO loop's last three
instructions may not be a branch or a call; (b) a conditional branch
landing on a loop's own end instruction hangs the core. A scripted
sweep of all 1,504 hardware loops in `src/**/*.asm` found **no instance
of hazard (b)** anywhere, and the following against hazard (a):

**D7 — MAJOR, but the evidence cuts both ways and the rule itself needs
settling.** Four loop shapes carry a `call` inside the last-three
window:

1. **`C1_RTG_01.asm:585-600` (all 32 RTG instances, BOTH builds
   including shipping):** `i2 = r3; call _acc64_mac; .rtg_xp: nop;` —
   call second-from-last, executed on every sample of every live
   crosspoint. This shape has run bit-exact through every chain proof
   in the record (the `GAIN→FDR→RTG→BUS` 0-LSB results went through
   this exact loop), which is strong empirical evidence the SHAPE is
   legal on this silicon.
2. **FILT crossfade fallback** (`C1_FILT_01.asm:84-89`, ×32) and
   **TUBE ramp fallback** (`C1_TUBE_02.asm:93-98` shape, ×32): call
   third-from-last; block-kernel builds only. Note the TUBE block
   steady loop (`C1_TUBE_01.asm:69-83`) carries two trailing `nop`s for
   exactly this rule while its `.tkb_rl` sibling does not — the
   generator applies the mitigation inconsistently.
3. **`bq_selftest.asm:252-257, 268-275`**: self-test only
   (`DSP4_BQ_SELFTEST=0` default); `build.sh:204`'s
   "bisect hook for the selftest hang" comment suggests this one has
   already bitten on the bench.

The contradiction — the shipping RTG shape violating rule (a) while
demonstrably correct — means the rule as recorded is broader than what
the silicon enforces for a call-that-returns-into-the-loop, OR the
failures are condition-dependent (the two bench incidents that produced
the rule involved the unresolved `_bq_fx_cascade_simd` context). It
cannot be settled from the local documents: the loop restrictions live
in the SHARC+ Core Programming Reference, which is NOT in
`_Matrix/_ref/adsp-2156x-docs/` (that set holds the SoC HRM, HWR,
datasheet, anomaly list and EE-461 — checked tonight; the SoC HRM has
no `lcntr` material). Two actions, both cheap: fetch the SHARC+ Core
PRM into the doc set and settle the exact rule; until then, make the
generator apply the two-`nop` tail uniformly to the fallback loops
(shapes 2), which costs 2 c/s on transient paths only. **Do not
"fix" the RTG loop ahead of the PRM check** — it is the highest-rate
loop in the product and it measurably works.

**D8 — MINOR. `_biquad_cascade_N` has `rts` as its loop-end
instruction** (`lib/biquad.asm:93-98`) — the worst possible form of
hazard (a). It has no callers anywhere in the tree (dead float-era
code): remove it rather than leave a routine that hangs the core on
first use.

**D9 — MINOR (doc). The generator's odd-tail comment says the unpaired
tail strip runs "on the EVEN pool"; the code puts every odd-numbered
strip on the `_P1` pool** (`dsp_codegen.py:8756-8760` vs `:8868`).
Currently dead (32 strips pair evenly) and each node file is generated
self-consistently, but the comment will mislead the first odd-count
product.

### Wiring verified clean (method stated, so it can be trusted)

Scripted checks over all 352 chip-1 strip-class node files and both
chains: chain order (each MTR immediately after its own strip's GAIN,
each RTG after its FDR — 32/32 in both the paired and scalar branches
of `chip1/process_chain.asm`); zero cross-strip symbol references;
pool parity (odd strip → `_P1` in every node of the strip, even → base;
0 mismatches; `BLK_PAIR_PARK` confirmed unused); all 16 `dyn_pairs.asm`
drivers reference only their own two strips' symbols with
parity-correct pools, and both scalar fallbacks are net-preserving
(B-in/B-out per pool); chip 2 contains no `_P1`/pool-tap leakage and no
strip pairs; `C1_XIN_*` private buffers stayed private (the recorded
slot-clobber fix held); and every `.extern` across `src/**/*.asm`
resolves (the four apparent orphans are C `#pragma linkage_name`
symbols and an LDF symbol).

### The block-kernel boundary

**D16 — MAJOR (structural). Chip 2 has no block kernels at all.** Under
`DSP4_BLOCK_KERNELS` chip 2's main loop calls `_chip2_process_all`
once per block (`main.asm:866-886`) but every chip-2 node body is
per-sample — a block-kernel image on chip 2 processes one sample in
eight through the whole graph. This is the recorded
"not functionally equivalent" trap at whole-chip scale: every block-8
capacity number in the record is chip-1-only, chip 2's block-8 cost is
unmeasured, and the block-8 operating point cannot ship until chip 2
is either converted or explicitly kept per-sample (which its 3.8×
block-32 silence overrun already makes doubtful). Effort L, and it
gates the product-level closing sum (Axis 2, caveat 3).

### Block-size literals

The full literal sweep (all 666 generated node files, the 9,286-line
generator read whole, every hand `.asm`/`.h`/`.c`/`.sh`/`.py` in the
build and bench path) found the six 2026-08-28 literals fixed and
**three live stragglers plus one structural seam**:

**D10 — MAJOR. `gen_dsp.py` still computes ramp frame counts at the
BLOCK-32 frame period.** `frame_667us = 0.667` (`gen_dsp.py:1162`,
"ms per frame at 48 kHz / 32 samples") divides every ramp profile's
`up_ms`/`down_ms` (`gen_dsp.py:1216-1217`) — at block 8 the frame is
166.7 µs, so the `ramp_up_frames`/`ramp_down_frames` baked into
`ghost_cells.c` (this tree AND the H1S1 firmware copy) are 4× too few.
`gen_dsp.py` contains no reference to BLOCK at all. No observed symptom
yet only because no H1S1 code reads those fields — the artifact is
silently wrong at every regeneration. Same family as the ramp ×BLOCK
defect already fixed on the DSP side. Effort S.

**D11 — MINOR. `sport_init.asm:30` carries a stale local
`#define BLOCK_SIZE 32`** — currently unreferenced in the file (each
`.asm` assembles independently, so it collides with nothing), but it
sits in exactly the file where a future use would silently mean 32.
Delete it or include `dsp_block.h`. Effort S.

**D12 — MAJOR (structural). Generated `.var` sizes are frozen at
GENERATION time while loop counts resolve at BUILD time, and nothing
ties the two together.** `build.sh` never passes `-DDSP4_BLOCK_SIZE`
(verified — the size reaches the build only through the generated
`dsp_block.h`); but `bus_accumulators.asm` bakes `_blk_pool[72]/[64]`
and 25× `_bus_acc_*[16]` as Python literals
(`dsp_codegen.py:6897-7055`), and `lane_config.c` bakes the DMA region
words (`c1_rx_region_words = 368` = count×BLOCK,
`dsp_codegen.py:4697-4698, 5019-5051`) — while `_bus_clear_all`,
`_acc64_mac_blk` and the `BLK(n)` pool macros compute from
`DSP4_BLOCK_SIZE` at build time. A hand-edited `dsp_block.h`, or a
stale generated tree rebuilt against a fresh header, walks
`2·DSP4_BLOCK_SIZE` over arrays sized for the old block — a silent
out-of-bounds DM write with no assembler, link or runtime guard. There
is NO consistency check anywhere in the generator (searched). Fix
shape: emit `#if DSP4_BLOCK_SIZE != 8` `#error "regenerate"` `#endif`
into every generated file that bakes a size (one generator line), or
size the `.var`s with the macro. Effort S, and it retires the exact
mechanism the six 08-28 literals exploited.

**D13 — Cleared, for the record (so "find the rest" has an answer):**
the `lcntr = 31` class is extinct — zero literal block-derived loop
counts, m-register strides, array sizes or IEEE block constants remain
in the 666 node files or the lib/hand asm (the fixed `−2*DSP4_BLOCK_SIZE`
rewind at `biquad_fx.asm:490` confirmed); `dynst_read.py` imports BLOCK;
`fixed_ref.meter_coeffs`/`dsp_simulate` are parameterised; the SPORT
`SLEN=31`/`WSIZE` values are hardware word-width fields, not block
size; `dyn_selftest.asm`'s `[64]` scratch is documented headroom
("any block size up to 32"); `lib/biquad.asm`'s `_biquad_block_32` is
dead float-era code (stale only in NAME — its loop uses the macro) and
should leave with D8's routine. The one live block-rate constant in
shipping audio-path code is D6's `_meter_decay`, found independently by
this sweep and by the wiring pass.

---

## AXIS 4 — GOLDEN-REFERENCE COVERAGE MAP

Verification architecture per `numeric-spec.md:93-96`: asm ≡ fixed_ref
(bit-exact), fixed_ref ≈ float64 (tolerances, `golden_harness.py`).
What the harness actually runs: four test families producing ten
checks — biquad (magnitude ×2 + noise floor), gain, 128-way mix sum,
log2, exp2, compressor static curve, soft-knee boundary, envelope tau
(`golden_harness.py:207-210`). Coverage of the emitted audio path:

| path | fixed_ref model | golden vectors | on-part check |
|---|---|---|---|
| biquad core (offset-DF1 + efb) | yes | yes | ASM-vs-ASM selftest only, debug builds |
| biquad coeff conversion `_bq_fx_convert_N` | yes (`biquad_coeffs_q`) | **no** | **manual only** |
| crossfade blend (EQ/FILT/XOVER dual instance) | **no** | no | no |
| gain / mix summing / `_acc64_*` | yes | yes | bench probes with **ad-hoc reimplemented rns()** |
| log2/exp2 poly | yes | yes | no |
| comp gain computer | yes | yes | no |
| **comp wet path (makeup round + parallel blend)** | **no** | no | pair-vs-scalar ASM only |
| limiter | reuses comp_gain | not with limiter params | no |
| envelope / gate primitives | yes | yes | ASM-vs-ASM |
| **gate node state machine (hold, range, smoother)** | **no** | no | ASM-vs-ASM (debug) |
| **tube saturation (3 chained rounds)** | **no** | **no** | **none at all** |
| delay | n/a (pure copy) | — | clamp logic untested |
| **fader pan law + level·dca composite** | **no** | no | ad-hoc probe math |
| **RTG coefficient prep + live list + pickoff** | **no** | no | bench probes, ad-hoc rns() |
| meter (rebuilt 2026-08-28) | yes | **no — harness never calls it** | **yes, strong** (`dsp4_mtr_verify.py`, bit-exact + negative control) |
| TDM boundary Q1.31↔Q4.28 | no | no | no |
| GEQ / AFB / XOVER (chip 2) | reuse biquad cascade | inherited | inherited gaps |
| FX engines / NOISE / DCA / ramps | float islands / control plane | by design | — |

Numbered findings:

**D26 — MAJOR. The meter model is in fixed_ref but `golden_harness.py`
never exercises it** — zero calls to `meter_block`/`meter_coeffs`/
`meter_readback` in the harness (confirmed by full read). The on-part
check (`tools/pi/dsp4_mtr_verify.py:108-125`) is strong — bit-exact
64-bit state with a negative control — but the model-vs-float64
tolerance leg the spec requires runs nowhere. Effort S.

**D27 — MAJOR. `_bq_fx_convert_N` has no automated regression
anywhere** (`biquad_fx.asm:404-449` vs `fixed_ref.py:95-98`) — and it
is the function that shipped the b1=0 defect the file's own header
documents (`biquad_fx.asm:386-397`). `dsp4_eq_probe.py:16-18` says the
fixed_ref comparison "happens on the dev box", i.e. by hand. Effort S
(a vector table in the harness plus one bench verdict script).

**D28 — MAJOR. COMP's wet path is unmodelled**: the makeup multiply's
second rounding and the parallel blend (`dsp_codegen.py:8151-8174`)
appear in no fixed_ref function — `comp_gain` stops at the gain
computer. The one existing check is pair-vs-scalar ASM
(`dyn_selftest.asm`), which proves the two asm paths agree, not that
either is right. This is also where Axis 6's D4 lives. Effort S-M.

**D29 — MAJOR. TUBE has zero coverage of any kind** — no model, no
vectors, no on-part check, for three chained roundings
(`dsp_codegen.py:7513-7522`) whose ACTIVE cost is also unmeasured
(Axis 1). The meter's before-state, exactly. Effort S.

**D30 — MODERATE. The GATE node-level state machine is unmodelled**
(hold counter, range floor, smoother; `dsp_codegen.py:8402-8435`) —
only its primitives have references; the composite behaviour's one twin
is debug-only ASM (`dyn_selftest.asm:275-327`).

**D31 — MODERATE. FDR's pan law and level·dca composite are
unmodelled** (`dsp_codegen.py:6337-6348,6449-6465`) — the exact site of
the 2026-08-23 squared-gain bug, still without a reference.

**D32 — MODERATE. The bench probes reimplement `rns()` by hand**
(`dsp4_send_proof.py:27-29`, `dsp4_xpoint_chain.py:30-31`) instead of
importing fixed_ref — two more copies of normative arithmetic free to
drift. Effort S (import the model).

**D33 — MODERATE. The dual-instance crossfade blend is unmodelled**
(EQ `dsp_codegen.py:5266-5292`; doubled in the crossover) — the
arithmetic Axis 6's D3 shows can wrap has no reference to test the fix
against.

**D34 — MINOR. The TDM boundary conversions (>>3 in, <<3+sat out) have
no test surface at all** (`chip1/block_io.asm:552`,
`chip2/block_io.asm:311-320`) — spec'd (`numeric-spec.md:18-20`),
simple, and unchecked.

**D35 — MINOR. Both in-part selftests compare ASM against ASM**
(`bq_selftest.asm`, `dyn_selftest.asm`, both "not built into any
shipping image") — the normative asm ≡ fixed_ref leg is proven only for
the paths the bench probes cover.

**D36 — MINOR. Spec bookkeeping:** `numeric-spec.md:3`'s "9/9" is stale
(the harness runs 10 checks); the end-to-end −90 dBFS strip null test
(`numeric-spec.md:90-91`) has no tooling anywhere; NOISE_GEN's float
island is undocumented in the scope-exceptions list
(`dsp_codegen.py:7822` vs `numeric-spec.md:72-77`).

---

## AXIS 5 — CONTRACT AUDIT (dsp.csv vs the mx26 masters)

Baseline: `defs.lock` at `defs-v2026.08.20`. **Drift check: clean** —
every generator stage reproduces the tracked tree byte-for-byte from
the synced contract (`gen_dsp_csv.py` output md5-identical to the
tracked `SHARC/dsp.csv`; `gen_dsp.py --dry-run` matches
`GHOST_CELLS_COUNT 5537` and both `dsp_params.asm` line counts exactly;
`dsp_codegen.py` regenerated into scratch diffs zero across all 683
generated files; `dsp_validate.py` OK, 666 nodes; `git status` clean
throughout). Family allowlist: D32's 307 families ⊆ the 310 allowlisted
(3 reserved ahead: `FxDuckThr`, `MainMtr`, `MainPeqGain`); no dangling
SPI dispatch symbols (all 2,421 externs resolve).

**D37 — MAJOR. The gate_gr/comp_gr class, verified with its mechanism.**
`dsp.csv` meter rows name taps `gate_gr;comp_gr` that resolve to no
node id. `gate_gr` gets a real but permanently-unwritten symbol
(`_mtr_gr_<nid>`, `gen_dsp.py` meter expansion ~:496, and the node's
own tail comment `C1_MTR_01.asm:125-130`); `comp_gr` gets
`add_dispatch(..., None, ...)` — a literal-0 dispatch slot — while
`ghost_cells` still names it as a pollable cell (`AaChan001CompMtr001`,
addr 4611). Host-visible symptom for both: gain-reduction metering
reads 0.0 forever, on all 32 strips. Fix needs mx26 to name a
resolvable GR source (already the recorded position); until then the
cells should be marked reserved rather than served as live zeros.

**D38 — MAJOR. A large writable-but-inert control surface.** Cells that
exist in the masters, are addressed in the dispatch tables, and are
never read by any emitted process body:
- COMPRESSOR mode/routing: `CompType`, `CompKey`, `CompDetSrc`,
  `CompLimMode`, `CompEqPos`, `CompFilterOn`, `CompFilterHpf/Lpf/Q`
  (`gen_dsp.py:293-311` create them; declared `dsp_codegen.py:1615-1622`
  float / `:8046-8053` fixed; full read of a COMP node confirms none is
  ever loaded). ≈ 212+ dead slots over 42 instances — sidechain filter,
  external key, detector point and compressor type are all no-ops.
- GATE `key_src`/`det_src` (`dsp_codegen.py:1486-1487, 8291-8292`) —
  unread, while the sibling `_gate_filter_on_` IS wired, so the routing
  half was specifically dropped. 36 instances.
- AUX_AFB: `_afb_on_`, `_afb_ctrl_on_` and the three per-notch arrays
  are inert; the cascade runs unconditionally — **there is no DSP-side
  way to disable an anti-feedback node** (`dsp_codegen.py:2530-2650`).
- FX_ENGINE: only `_fx_type_` (3 of ~7 enum values do anything),
  `_fx_mix_`, `_fx_feedback_`, `_fx_damp_` are consumed; `_fx_on_`
  (bypass!), decay, predelay, delay_ms, the 3-band EQ, mod rate/level,
  LFO shape and width are dead (~96 slots over 6 instances). Root
  cause for the dead echo/modulation branches: the generator selects on
  a params key `fx_class` (`dsp_codegen.py:2740`) that
  `gen_dsp_csv.py:681` never emits (it emits `type=Reverb`, which the
  generator only puts in a comment). Also: the reverb path never writes
  `_buf_R_<nid>` — the FX right output is permanently stale.
- DCA: the node's own ramped `_dca_level_` is computed and discarded —
  faders read the separate `_fdr_dca_gain_` cell (`dsp_codegen.py:
  4128-4165` vs `:6372-6373`); `_dca_mute_` unreferenced. MONITOR's
  `_mon_source_` select is read nowhere (the comment above the dead
  code describes the feature, `dsp_codegen.py:3660-3705`). TALKBACK's
  route array exposes only offset 0 and ignores it.
All of this is "unknown cell must fail loudly" policy inverted: the
cells succeed silently and do nothing. Either wire them, or mark them
MCU-managed/reserved in the masters so the host knows.

**D39 — MAJOR. Gate RANGE unit mismatch, provable in-repo.** The master
documents dB (`d32-mx-master.csv:80`, "Gate depth/range 0-60dB",
`0=0/254=60`); the kernel scales the wire float straight by 2^28 as a
LINEAR gain (`dsp_codegen.py:291-296, 8358-8364`; the emitted var's own
comment says "linear floor", default 0.001 = a hand-pre-converted
−60 dB). `dsp_simulate.py:237` performs the dB→linear conversion the
firmware never does, proving the CSV-level convention is dB. A host
writing the documented value (say 40.0) gets 40.0 scaled by 2^28 —
saturated garbage — instead of −40 dB.

**D40 — MAJOR. Comp PARALLEL percent-vs-fraction mismatch.** The master
says percent (`d32-mx-master.csv:43`, `0=0/127=100`); the kernel
multiplies the raw wire value by 2^31 with no /100
(`dsp_codegen.py:8118-8134`), and its own clamp comment discusses
0.999/1.0 as the working domain. Any percent value ≥ 1 pins fully wet:
the blend control cannot take intermediate values as documented.

**D41 — MAJOR (cross-repo caveat). The ms-vs-native family.** The
kernels want a one-pole alpha for attack/release
(`dynamics.asm:180-181` documents `1−exp(−1/(Fs·T))`), raw SAMPLES for
delay `read_offset` (`dsp_codegen.py:1791`) and gate `hold`
(`.var = 2400` = 50 ms at 48 kHz, integer, `dsp_codegen.py:8286`); the
masters document ms for all of them, and NO conversion exists anywhere
in this repo (the `1−exp` form appears only in `dsp_simulate.py` and
`golden_harness.py`). Whether the Pi/MCU pre-converts before the SPI
write cannot be settled from this tree — but either the masters'
units column or the wire contract is wrong as written, and
`numeric-spec.md:58-61`'s "the wire carries float32 words" is already
contradicted by the integer cells (`spi_handler.asm:19-20` admits
"float32 or integer" with no per-cell table). Needs one page in the
contract stating per-cell wire encoding and units — this is the same
class that made gain ramps run 32× long before it was caught.

**D42 — MODERATE. Pan law: linear vs the documented constant-power.**
`dsp-def.md:860,418` documents constant-power pan; both kernels
implement linear `1−pan`/`pan` (`dsp_codegen.py:1995-2000, 6329` — the
fixed node's comment honestly admits it). ~3 dB centre dip against the
documented law on every fader. A law change is a numeric-spec change:
state it for PW rather than fix it quietly.

**D43 — MODERATE. D24 blind spots.** D24's DEFS still declare
`Chan[1-24]GateThr/GateRng` but D24's dsp.csv generates NO GATE nodes
at all (orphaned cells); and `validate-matrix-contract.py` scopes the
family allowlist to D32 only — D24's matrix carries 95 families the
allowlist never sees, so an unwanted family landing in D24's contract
would pass silently. The no-fallback policy has a product-sized hole.

---

## NEEDS MEASUREMENT (collected, for the fix sessions)

1. TUBE active cost — never measured (open since 08-24; Axis 1).
2. L2 (`seg_delay`) access latency isolated from DLY's arithmetic — the
   DLY floor and the delay-pool placement decision both hang on it.
3. Fused (`DSP4_STRIP_FUSED=1`) + paired at BLOCK=8 — the block-8
   record is unfused; the Axis-2 projections assume the block-32 fusion
   gains carry over.
4. Block I/O + fabric profiled directly at block 8 (F = 18,785 here is
   derived from the ceiling points, not profiled).
5. Chip 2 at block 8, in any form (D16 gates this).
6. The SHARC+ Core Programming Reference loop-restriction text (D7) —
   a document fetch, then at most one bench experiment.

## THE SHAPE OF IT

The rulings are not the obstacle. Under Q4.28, the offset biquad with
error feedback, polynomial dynamics and the block-8 operating point,
the floor sum says 32 channels fit one 21564 at 983.04 with margin —
scalar at floor already fits, paired at floor fits twice over. The
2.1× that separates today's measured paired strip from the 32-channel
line is call/rts scaffolding, unpacked instruction streams, and
control-rate work executed at block rate — all of it removable
bit-exactly. The three things that can sink the goal regardless of
code quality are D1 (the one wrap that can pass audibly wrong audio
through a clean-looking bus), D16 (chip 2 has no block-kernel story at
all), and the unresolved biquad-pair hang. Those, plus the contract
mismatches a host will eventually trip (D39–D41), are where the next
sessions should land first.

