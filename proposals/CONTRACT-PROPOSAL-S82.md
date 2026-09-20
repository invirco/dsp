provenance: AI-drafted 2026-09-20 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# Contract proposal S82 — the signed DSP configuration, its three numeric bounds, and the CPLD diagnostic knock

**Status: PROPOSED, not landed.** Nothing here writes a def, a master row or a
`_matrix.csv` row, and nothing in `defs/` is edited by this session. Two of the
three parts below are records of decisions PW has already taken; the third is a
placement question the hub answered in S81-Q5 and which wants writing down.

Evidence: `MW/D24/DSP/s82/signed.md`, findings S82-1..n,
`MW/D32/DSP/SHARC/shipping.config` (the file the build reads),
`tools/dsp/cfg_words.py` (the words the part reads back).

---

## 1. The signed configuration

PW signed the SIMD pairing configuration on 2026-09-20 ("sign it"). The four
switches the signature covers are `DSP4_SIMD_DYN`, `DSP4_STRIP_FUSED`,
`DSP4_DYN_LUT` and `DSP4_GATE_LINTHR`, on top of the levers already shipping
(`DSP4_SHARED_KERNELS=15`, `DSP4_AUXIN_BYPASS`, the product-driven scope gate
`DSP4_SCOPE_GATE`).

**The configuration is not prose; it is a file and three words the part reads
back.** `MW/D32/DSP/SHARC/shipping.config` is the file; the words are
`DIAG_BUILD_CFG` (`0xE0EA`), `DIAG_BUILD_CFG2` (`0xE0EB`) and
`DIAG_BUILD_CFG3` (`0xE0EC`). A shipping image reads:

| word | before S82 | **signed (S82)** |
|---|---|---|
| `DIAG_BUILD_CFG` | `0xCF45FF10` | `0xCF45FF10` (unchanged) |
| `DIAG_BUILD_CFG2` | `0xE2018264` | **`0xE2018E6F`** |
| `DIAG_BUILD_CFG3` | `0xC47C0F26` | `0xC47C0F26` (unchanged) |

Only the second word moves, by five bits — `0xE2018264 ^ 0xE2018E6F =
0x00000C0B` = bits 0 `DSP4_STRIP_FUSED`, 1 `DSP4_SIMD_DYN`, 3
`DSP4_SIMD_STRIPS`, 10 `DSP4_DYN_LUT`, 11 `DSP4_GATE_LINTHR`. That is the four
signed switches plus the `DSP4_SIMD_STRIPS` that `DSP4_SIMD_DYN` brings with
it, and nothing else. Words 1 and 3 not moving is a **check, not a
coincidence**: none of the four lives in either, so any movement there would
say the signing had changed something it was not signing.

**Measured on the part, both chips** (S82, signed pair `e3e25a79…` /
`41a6b913…` booted on the post-S34 shipping bitstream): `raw 0xCF45FF10 / raw2
0xE2018E6F / raw3 0xC47C0F26`, `== the shipping configuration`. Negative
control: the same tool given the OLD triple refuses the same part and names
all five bits.

### 1.1 Every switch a word carries is now named in the file

`shipping.config` names all thirty-seven switches that the three words carry,
rather than letting `build.sh` defaults carry any of them, and
`check_shipping_config.sh` enforces that as a rule instead of a patch. The
exemption is `DSP4_BQ_GUARD`, which no configuration can set (`src/dsp_block.h`
forces it to 0 under `DSP4_BQ_FLOAT`), and the exemption list is itself checked
in both directions.

This is the fifth occurrence of one fault — S8-2/S9-1 (block, block kernels,
core clock), S11-1 (`DSP4_STRIP_FUSED` / `DSP4_SIMD_DYN`), S76
(`DSP4_SHARED_KERNELS`), S79 (`DSP4_AUXIN_BYPASS`) — and the first time the fix
generalises. **It is proposed here because it is a property of the contract,
not of the build**: the three words are what a host, a factory jig or a field
diagnostic reads to say "this part is the product", and that claim is only
worth what the file behind it names.

---

## 2. The three accepted numeric bounds

PW accepted three numeric deviations with the signature. **They are contract
terms, not measurements**: a re-measurement outside its bound is a STOP and a
re-signing question, not a new bound.

| bound | value | what it is | where the number is PRODUCED |
|---|---|---|---|
| `DSP4_DYN_LUT` | **≤ 0.0950 dB** | worst-case gain error of the baked level→gain table over the whole documented COMPRESSOR/LIMITER parameter sweep, at the shipped K = 4 | `tools/dsp/dyn_lut_design.py --sweep` |
| `DSP4_GATE_LINTHR` | **≤ 0.0002 dB** | shift in the GATE's effective threshold from comparing in the linear domain instead of log2 | `tools/dsp/dyn_state_bound.py` §6 |
| `COMPRESSOR` numeric | **≤ 0.00518 dB** | one verdict of `famverify`'s twenty moves numerically against `fixed_ref`; this is how far | `famverify.sh` → `dsp4_node_verify.py::numeric_phase` |

Three things the table's right-hand column is doing deliberately.

**The bound is quoted against the tool that computes it, not against a
constant.** `dyn_lut_design.py` derives 0.0950 dB from the table design and the
parameter sweep; it is not stored as a literal anywhere that could drift from
the design. `dyn_state_bound.py` carries `LINTHR_BAR = 0.0002` as a module
constant and reports every point that exceeds it.

**`GATE_LINTHR`'s bound has a documented exceedance region and it is inside the
contract range, not outside the bound.** The full 801-point sweep finds 19
points over 0.0002 dB, *all* at thresholds at or below −77.1 dB, worst
+0.000320 dB at −79.9 dB, where the linear word is a few tens of Q4.28 LSBs and
one LSB of quantisation is already larger than the bar. Over any threshold at
or above −60 dB the worst shift is +0.000122 dB. **The contract term should say
so**: ≤ 0.0002 dB for `GateThr ≥ −60 dB`, and ≤ 0.00035 dB below it. A bound
that is quietly exceeded at the edge of its range is the shape this project
calls a defect in the instrument.

**`DSP4_DYN_LUT` sits exactly on its bound with no margin.** 0.0950 dB against
PW's 0.1 dB ruling, worst case `comp thr −60.0 ratio 100.0 knee 0.0` at
−60.0 dBFS. It passes, and the hub should know it passes by 0.005 dB and not by
a comfortable margin: a future change to the table's K, its chunking or the
parameter range has almost no room.

### 2.1 What the bounds are measured against, and the one bar that isolates them

`busgold.sh` captures 256 consecutive words of `_buf_C1_BUS_MAIN_L` out of a
running graph with the strip compressor fully wet. S20-6's three arms are the
isolation:

* the signed configuration with `DSP4_DYN_LUT=0 DSP4_GATE_LINTHR=0` reproduces
  the 2026-08-30 golden **bit for bit** (0 of 256 words);
* the signed configuration entire differs in 235 of 256 words, worst
  **0.03934 dB**, with not one word zero in one capture and non-zero in the
  other (the signature a dead node leaves);
* `DSP4_STRIP_FUSED` + `DSP4_SIMD_DYN` + the chip-2 pairing + `DSP4_TX_EARLY=2`
  together change **not one bus word**.

So the whole audible content of the signing is these two switches, at
0.03934 dB in the bus capture against a 0.0950 dB design bound.

---

## 3. The CPLD diagnostic knock is OUTSIDE the matrix contract (S81-Q5)

S81 asked whether `dsp4_cdc_witness.py`'s second knock word pair belongs in
`release-notes-contract-convention.md`'s scope. **The hub's answer, carried
here: no — it is a CPLD diagnostic, recorded the way `DIAG_BUILD_CFG3` is
recorded, and it is not a matrix cell.**

The reasoning is the same one that puts the `0xE0xx` diag words outside the
contract: nothing in `defs/` declares it, no host writes it as a parameter, no
`_matrix.csv` row addresses it, and changing it changes no product behaviour.
What it *is* is a small interface between a bitstream and a bench tool, and
interfaces want one written-down home. That home is this section plus the
manifest `build.sh` emits beside every artifact.

### 3.1 The two knocks, as they now ship in EVERY configuration

Both ride the CM4's PCM link. Play the L/R word pair on `hw:dsp4pcm`, record,
and read 128 frames of reply. Both are built unconditionally — the whole point
is that whatever is flashed can answer — and both cost the return stream
2.7 ms on a false trigger.

| knock | play | reply |
|---|---|---|
| design ID (S5-9) | `L=0xD5D51D1D, R=0x2A2AE2E2` | `L = design_id`, `R = 0xD594<cfg_bits>` |
| CDC_O witness (S81) | `L=0xCD0432B4, R=0x32FBCD4B` | `L = {7'b0, cdc_ones_last[8:0], 7'b0, cdc_ones_max[8:0]}`, `R = {0xCD04, cdc_toggles_last[8:0], frame_counter[15:9]}` |

`cdc_ones` / `cdc_toggles` are per 48 kHz frame over 256 TDM8 bit periods;
`cdc_ones_max` is the high-water mark since power-up. **The free-running frame
counter is the instrument's own negative control**: it advances every 10.7 ms,
so two knocks a quarter-second apart must differ, and the tool refuses to
report its zeros as a measurement if they do not.

### 3.2 And a rule the bench now enforces: no design ID, no flash

S81-Q2 asked whether a bitstream that cannot identify itself should be allowed
on the bench. **Ruled: no.** `dsp4_logic.a1f6672af6c3` — what every session
since S37 called "shipping" — predates the design-ID stamp, so the part could
not be asked what was on it and its identity rested on a flash log. Ten
sessions then diagnosed a converter fault that was the bitstream.

`loadlogic.sh` now reads the `design_id:` line out of the manifest beside the
artifact and refuses to stage anything without one; the check is on the
manifest rather than on a list of names kept in the script, because a list is a
second copy of a fact. `a1f6672af6c3` is retired to
`shared/dsp4-logic/bitstream/retired/` and named in the script only so the
refusal is a sentence.

**The shipping LOGIC artifact is `dsp4_logic.7a6a4529f29c`**, design ID
`0x4529f29c`, cfg_bits `0x0010`, POF md5 `7dc0976d7b13d98b4a37795d1eeaf49e`,
Fmax 67.25 MHz, sim gate PASS, slot map
`sha256:c4a3ca82f956b9c587e80fbfdf3079bd0c8f12dd213e9ebdcd84414618477cdd`. It
rebuilds byte-identically from HEAD (S82 gate 0, POF hashed — the SVF carries a
wall-clock comment line and is identical with that line stripped), and the part
answers `design_id: 32'h4529f29c cfg_bits: 16'h0010 SHIPPING` when asked.

---

## 4. What this proposal does NOT ask for

* **No def key, no new matrix cell, no address.** Everything above is either a
  build-configuration fact or a diagnostic, and both are outside the matrix
  contract by the same rule that keeps `0xE0xx` out of it.
* **No change to `defs/`.** This spoke is a consumer; the hub lands whatever of
  this belongs in `defs/docs`.
* **No re-opening of `DSP4_C2_BQ_GRAPH`.** Chip 2's paired aux and main
  biquads are not in the signature and stay 0. `DSP4_DYN_TABLES` also stays 0,
  and with the pairing signed that line is now load-bearing rather than a
  placeholder: the two switches are incompatible and the assembler refuses the
  combination.
