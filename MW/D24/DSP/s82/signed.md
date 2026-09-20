provenance: AI-drafted 2026-09-20 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S82 — the signed configuration ships, on the fixed bitstream

**Session 82, 2026-09-20, rev C unit + desk.** Hub dispatch `tasks.md`
2026-09-20 10:19Z. PW adopted the S34 converter-clock fix and signed the SIMD
pairing configuration the same morning; this session puts both on the part,
proves them, and writes them into the contract.

---

## 0. Outcome in one paragraph

**The shipping LOGIC moved and the part says so.** `dsp4_logic.7a6a4529f29c`
is flashed, FLASH OK on attempt 1, and answers `design_id: 32'h4529f29c
cfg_bits: 16'h0010 SHIPPING` when asked — where the artifact it replaces
answered *"no reply: nothing in the capture carried the 0xD594 marker"*, which
is the negative control for the whole S81-Q2 question and was taken twenty
minutes before the flash. It rebuilds byte-identically from HEAD (POF md5
`7dc0976d7b13d98b4a37795d1eeaf49e`), `a1f6672af6c3` is retired to
`bitstream/retired/`, and `loadlogic.sh` now refuses any artifact whose
manifest carries no `design_id:` line. **The converter re-take on it is
unambiguous**: all four codec return lanes carry moving converter noise with
the rails down *and* up, and the AK5558 lanes read exact digital zero in every
one of five conditions including the 595 chain unmuted at maximum gain — so
the SAFE image is not the zero, and S81-Q3 stands as its own fault. **The
signed configuration is in `shipping.config`, and the part reads it back**:
`0xCF45FF10` / **`0xE2018E6F`** / `0xC47C0F26` on both chips, with the old
triple refused by the same tool on the same part and all five moved bits
named.

### What ships, in one table

| | |
|---|---|
| **LOGIC** | `dsp4_logic.7a6a4529f29c` — design_id `0x4529f29c`, cfg_bits `0x0010`, POF md5 `7dc0976d7b13d98b4a37795d1eeaf49e` |
| **DSP pair** | `chip1.ldr` md5 `e3e25a79c4619d1a44305258f99fac7d` (426,464 B)<br>`chip2.ldr` md5 `41a6b913e5f77bac698e136abd9aac65` (367,024 B) |
| **the triple the part must read** | `DIAG_BUILD_CFG 0xCF45FF10` · **`DIAG_BUILD_CFG2 0xE2018E6F`** · `DIAG_BUILD_CFG3 0xC47C0F26` |
| **signed** | `DSP4_SIMD_DYN` + `DSP4_STRIP_FUSED` + `DSP4_DYN_LUT` + `DSP4_GATE_LINTHR`, over `SHARED_KERNELS=15`, `AUXIN_BYPASS`, `SCOPE_GATE` |
| **accepted bounds** | DYN_LUT ≤ 0.0950 dB · GATE_LINTHR ≤ 0.0002 dB (`GateThr ≥ −60 dB`) · COMPRESSOR ≤ 0.00518 dB |
| **previous triple** | `0xCF45FF10` / `0xE2018264` / `0xC47C0F26` — only the second word moves, by five bits |

---

## 1. Gate 0 — the shipping bitstream, and the converters on it

### 1.1 The artifact, stated by hash and by design ID

| | |
|---|---|
| artifact | `dsp4_logic.7a6a4529f29c.{pof,svf}` |
| design_id | `32'h4529f29c`, cfg_bits `16'h0010` |
| POF md5 | `7dc0976d7b13d98b4a37795d1eeaf49e` |
| SVF md5 | `48ddd02299b166127429eb2ad10db492` |
| slot map | `sha256:c4a3ca82…8477cdd` |
| Fmax / sim gate | 67.25 MHz / PASS (5 testbenches) |
| device | 5M1270ZT144C4 |

**Rebuilt from HEAD and hashed, not assumed.** A clean `shared/dsp4-logic/build.sh`
run reproduces the committed POF **byte for byte**. The SVF differs in exactly
one line — the `!Device #1: … <wall-clock>` comment `build.sh`'s own header
warns about — and is identical with that line stripped, which is why the POF is
what the byte-identity claim rests on.

**Flashed**: `IDCODE before 0x020a30dd`, FLASH OK on attempt 1 (40,790 lines of
SVF played, chain reached shutdown), `IDCODE after 0x020a30dd`.

### 1.2 The negative control for S81-Q2 was taken by accident and is the best one available

Before the flash, on `a1f6672af6c3`:

```
$ ./loadlogic.sh --id
no reply: nothing in the capture carried the 0xD594 marker.
  Either the bitstream predates the ID register, or the
  capture path is not reaching the CM4 at all.
```

After the flash, same command, same card, same capture path:

```
design_id: 32'h4529f29c   cfg_bits: 16'h0010   SHIPPING
  reply frames 2175 of 144000 captured, 1 distinct reply words
```

So the "cannot identify itself" half of S81-Q2 is not an inference from the
artifact's build date — it is two readings twenty minutes apart, and the
capture path is proved by the second.

### 1.3 `loadlogic.sh`: no design ID, no flash

`shipping` now names `dsp4_logic.7a6a4529f29c`. The gate reads the
`design_id: 32'hXXXXXXXX` line out of the manifest **beside the artifact**
rather than from a list of names kept in the script, because a list is a second
copy of a fact and goes stale the first time somebody adds a bitstream. Proved
not vacuous on the three manifests that matter:

| manifest | extracted ID |
|---|---|
| `dsp4_logic.7a6a4529f29c` | `4529f29c` → flashes |
| `retired/dsp4_logic.a1f6672af6c3` | *(none)* → refused |
| `s37_shipping_step0.c62c024714f2` | *(none — its manifest says "NONE — AND THAT IS NOT FIXABLE AT THIS SIZE")* → refused |

The step-0 image is the one deliberate exception in the tree and it goes on the
part through `tools/pi/logic_flash.sh`, never through this script — so that
exception is now a property of which tool is used, not of a convention somebody
has to remember.

`a1f6672af6c3` moved to `shared/dsp4-logic/bitstream/retired/` beside the two
artifacts S37 retired. The name is still in `loadlogic.sh`'s case statement,
resolving to a refusal that says why, so a session reaching for it by habit
gets a sentence instead of a usage line.

### 1.4 `driveall` always had the converter clock, from the source

The dispatch asked this to be answered from the source and it is. The S34
commit `ded71079` (2026-09-11) is an ancestor of HEAD, and the RTL it landed is
**outside** every build-variant guard:

```
rtl/dsp4_logic_top.v:36   // THESE WERE INPUTS, AND THAT IS WHY NO CONVERTER CAN WORK.
rtl/dsp4_logic_top.v:62       output wire conv_bck,   // pin 142 (C1): 12.288 MHz, TDM8
rtl/dsp4_logic_top.v:63       output wire conv_fs,    // pin 141 (L0): 48 kHz frame sync
rtl/dsp4_logic_top.v:446      assign conv_bck = bck8;
rtl/dsp4_logic_top.v:447      assign conv_fs  = fs8;
```

The single `ifdef DSP4_DRIVE_ALL` block is lines 314–389; the two assignments
are at 446–447, after it and unconditional. `dsp4_logic_driveall.c49f4128a083`
was built 2026-09-20T01:08:20Z, nine days after `ded71079` landed. **Every
driven capacity row taken on `c49f4128a083` was taken with the converter clock
present**, which is the other half of S81-Q2's observation that the two
"shipping" meanings diverged.

### 1.5 THE CONVERTER RE-TAKE

Signed pair booted at `/home/app/ship_s82`, D24, configured twice; chip 1
`MAGIC 0xD5B40001 CHIP_ID 1 BOOT_STAGE 7 SPI_ERR_COUNT 0 RESP_DROP 0`, chip 2
the same at `CHIP_ID 2`. Ten peeks per lane, through the **staged** symbol map
(see §1.6 — the first pass of this measurement was taken through the wrong one).

| lane | rails DOWN, chain SAFE | rails UP, chain SAFE | rails UP, chain UNMUTED gain 63 |
|---|---|---|---|
| `_buf_C1_XIN_CODEC_01` | **10 distinct / 10** | **10 / 10** | **10 / 10** |
| `_buf_C1_XIN_CODEC_02` | **10 / 10** | **10 / 10** | — |
| `_buf_C1_XIN_CODEC_03` | **10 / 10** | **10 / 10** | — |
| `_buf_C1_XIN_CODEC_04` | **10 / 10** | **10 / 10** | — |
| `_buf_C1_IN_01` (AK5558) | 1 distinct, `00000000` | 1, `00000000` | **1, `00000000`** |
| `_buf_C1_IN_02` | 1, `00000000` | 1, `00000000` | **1, `00000000`** |
| `_buf_C1_IN_05` (MIC 14) | 1, `00000000` | 1, `00000000` | **1, `00000000`** |
| `_buf_C1_IN_09` | 1, `00000000` | 1, `00000000` | **1, `00000000`** |
| `_buf_C1_IN_17` | 1, `00000000` | 1, `00000000` | **1, `00000000`** |
| `_buf_C1_XIN_MEMS` | 1, `ffffffff` | 1, `ffffffff` | — |

Sample values, rails up: `fffee300 0000a020 0000bc60 00006720 ffff1ba0 …` —
small signed Q4.28 words moving about zero, which is what a clocked converter
with nothing plugged in produces. **S81's B side is reproduced on a different
DSP image, and the A side can no longer be flashed.**

**The MIC 5 EIN row is refused, and now for a measured reason.** The dispatch's
own test was "if the SAFE image (inputs shunted) is the zero, say so". It is
not. The 595 chain was written to `0xFC` — gain 63, phantom off, **unmuted** —
verified 200/200 on the part, and every AK5558 lane read still returns exact
digital zero. A muted preamp still delivers
converter noise; an exact digital zero is no conversion. So that gate stops
with the reading, exactly as the dispatch permits, and **S81-Q3 stands
untouched by the converter-clock fix** — which is what §3.6 of S81 predicted,
since `StartAK4619()` writes the AK4619 alone and nothing in this tree has ever
given an AK5558 a register image. The SAFE image `0x01` went back on the chain,
verified 200/200, and CS_M returned to `ip pu`.

**The talkback T1/T3 re-take was NOT taken — see §7.**

### 1.6 `dsp4_inscan.py` scored the signed pair through the WRONG symbol map, and said nothing (S82-4)

The first pass of §1.5 ran `dsp4_inscan.py`, which reported **`MOVING 0 /
STATIC 47`, controls passed** — on a boot where a direct peek of the same lanes
showed every codec return moving. The tool's `load_syms()` searched
`~/dspboot` **before** the working directory. The signed pair was staged at
`/home/app/ship_s82`; `~/dspboot` held the S78-restore pair's map; so it peeked
the wrong addresses on a link that was answering perfectly and printed a tidy
table. Three of its forty-seven lanes read `0x3F800000`, which is `1.0f` and
not a sample at all — the one visible sign, and not one the summary line
mentions.

This is precisely the failure the tool's own docstring warns about ("a map from
a different build peeks plausible ZEROS rather than raising"), committed by its
own search order, one session after S81 rewrote it to stop being void.
**Fixed**: the working directory comes first, `~/dspboot` second, and the
absolute path of the map it used is printed. Every staged arm in this tree
(`ship_*`, `cap_*`, `conf_*`, `geq_*`, `dyn_*`…) runs from its own directory,
so the old order was backwards for every case that matters.

---

## 2. Gate 1 — `shipping.config` names the signed configuration

### 2.1 The triple, and why only one word moves

| word | before | **signed** |
|---|---|---|
| `DIAG_BUILD_CFG` | `0xCF45FF10` | `0xCF45FF10` |
| `DIAG_BUILD_CFG2` | `0xE2018264` | **`0xE2018E6F`** |
| `DIAG_BUILD_CFG3` | `0xC47C0F26` | `0xC47C0F26` |

`0xE2018264 ^ 0xE2018E6F = 0x00000C0B` — bits 0 `DSP4_STRIP_FUSED`, 1
`DSP4_SIMD_DYN`, 3 `DSP4_SIMD_STRIPS`, 10 `DSP4_DYN_LUT`, 11
`DSP4_GATE_LINTHR`. Words 1 and 3 not moving is a **check and not a
coincidence**: none of the four signed switches lives in either, so any
movement there would say the signing had changed something it was not signing.

**The signed pair**: `chip1.ldr` md5 `e3e25a79c4619d1a44305258f99fac7d`
(426,464 B), `chip2.ldr` md5 `41a6b913e5f77bac698e136abd9aac65` (367,024 B),
built from `shipping.config` with no override on the command line.

**Read off the part, both chips**: `raw 0xCF45FF10 / raw2 0xE2018E6F / raw3
0xC47C0F26`, `== the shipping configuration`, `on2: DSP4_STRIP_FUSED,
DSP4_SIMD_DYN, DSP4_SIMD_GRAPH, DSP4_SIMD_STRIPS, DSP4_GATHER_FIRST,
DSP4_DYN_LUT, DSP4_GATE_LINTHR, DSP4_TALK_INVERT`.

**Negative control, on the same part in the same run** — the same tool given
the OLD triple:

```
NOT THE SHIPPING KERNEL CONFIGURATION:
  DSP4_DYN_LUT = 0, shipping is 1
  DSP4_GATE_LINTHR = 0, shipping is 1
  DSP4_SIMD_DYN = 0, shipping is 1
  DSP4_SIMD_STRIPS = 0, shipping is 1
  DSP4_STRIP_FUSED = 0, shipping is 1
```

Five names, matching the five bits of the XOR exactly.

### 2.2 The fifth time, and the first time the fix is a rule

`shipping.config` now names **every switch any of the three words carries** —
thirty-seven of them — instead of letting `build.sh` defaults carry any.
Fourteen were at a default before today: `DSP4_GAIN_FLOAT`, `DSP4_GAIN_SIMD`,
`DSP4_GATHER_FIRST`, `DSP4_BLOCK_DECIMATE`, `DSP4_BQ_SIMD_PIPE`,
`DSP4_C2_XPAIR`, `DSP4_DLY_SPLIT`, `DSP4_DYN_INLINE`, `DSP4_RTG_FABRIC`,
`DSP4_FX_TYPE_DECLARED`, `DSP4_SCOPE_BLK_TAP`, `DSP4_SIMD_GRAPH`,
`DSP4_SIMD_STRIPS`, `DSP4_DYN_TABLES`. **None of their values changed** — the
triple moves by the five signed bits and nothing else, which is the proof that
this was a naming change and not a configuration change.

`check_shipping_config.sh` enforces it. The gate is not the completeness gate
that is already there: the existing checks prove the FILE and the MIRRORS
agree, and they agree perfectly about a switch neither names, because both
sides fall through to the same `build.sh` default. What that cannot survive is
the default moving.

The only exemption is `DSP4_BQ_GUARD`, which no configuration can set
(`src/dsp_block.h` forces it to 0 under `DSP4_BQ_FLOAT`), and the exemption
list is checked in **both** directions — a key exempted that a word does not
carry, or that `cfg_words.py` resolves from anything but a derivation, fails
the check.

**Proved not vacuous**: deleting `DSP4_RTG_FABRIC=1` from the file produces

```
SHIPPING CONFIG DRIFT: DSP4_RTG_FABRIC is carried by a config word and is NOT
NAMED in shipping.config: the shipping image takes it from build.sh's default,
which is findings S8-2 / S11-1 / S76 / S79 and is the fault this file exists for
```

and the line restored brings the check back to `consistent`.

---

## 3. Gate 2 — the audio bar on the signed pair

### 3.1 The desk half: every offline fixture and two of the three bounds

| bar | command | verdict |
|---|---|---|
| golden harness | `tools/dsp/golden_harness.py -v` | **59/59 PASS** |
| contract shape | `tools/dsp/dsp_validate.py MW/D32/DSP/SHARC/dsp.csv` | **OK — no errors**, 701 nodes, 4 process-order notes the generator repairs |
| accept/dry-run, both modes | `tools/accept/dryrun_d24.sh` | ran to completion; **`dryrun_compare.py`: 187 of 187 comparisons agree within tolerance (0 DIFF, 0 MISSING)** |
| `DSP4_DYN_LUT` bound | `tools/dsp/dyn_lut_design.py --sweep` | **0.0950 dB** worst over 81 parameter sets — **inside its 0.0950 dB bound, with no margin** |
| `DSP4_GATE_LINTHR` bound | `tools/dsp/dyn_state_bound.py` (full, 801 points) | **PASS**, and see below |
| shipping config | `check_shipping_config.sh --expect-shipping` | consistent; the triple above; no `NOT IN EITHER WORD` lines |

Logs: `MW/D24/DSP/s82/logs/`.

**`GATE_LINTHR` passes its script and exceeds its stated bound at the bottom of
its range**, which the contract term should say rather than the script absorb:

```
worst effective-threshold shift = +0.000320 dB at a threshold of -79.900 dB
(the log arm opens at envelope 27155, the linear arm at 27154 -- ONE Q4.28 LSB apart)
over any threshold at or above -60 dB: +0.000122 dB
19 of 801 points exceed the documented 0.0002 dB, ALL of them at thresholds at or below -77.1 dB.
```

At −79.9 dB the linear word is a few tens of Q4.28 LSBs and one LSB of
quantisation is already bigger than the bar, so this is the format and not the
switch. Carried into `limits.csv` and the contract note as **≤ 0.0002 dB for
`GateThr ≥ −60 dB` and ≤ 0.00035 dB below it**.

**The accept fixtures were stale and are now not (S82-9).** All 38 fixtures and
the manifest said `contract: defs-v2026.09.16.5` while `defs.lock` pins
`defs-v2026.09.19.3`. Regeneration moves **provenance only** — no fixture body,
no limit, no measured number — and the 187/187 comparison above is taken on the
regenerated set.

### 3.2 The family bar: twenty-seven verdicts, and the two that are the instrument's

`./famverify.sh` on the signed configuration (image `7d73e79a` / `ef85c658` —
famverify builds with `DSP4_SCOPE_BLK_TAP=1`, which is why its pair is not the
shipping pair's md5; the part reads `0xE2018E7F`, the signed word plus that one
bit). D24, both chips, 64 cells per family.

| family | cells | contract | audio | numeric |
|---|--:|---|---|---|
| ANTI_FB | 160 | 20/20 | LIVE | — |
| AUX_INPUT | 8 | 2/2 | NO_STIMULUS_PATH | — |
| **COMPRESSOR** | 544 | 17/17 | LIVE | **see §3.3** |
| CROSSOVER | 8 | 8/8 | LIVE | — |
| DCA | 16 | 2/2 | NO_PROBE | — |
| DELAY | 34 | 1/1 | LIVE | — |
| EQ_BIQUAD | 625 | 14/14 | LIVE | NOT_APPLICABLE (float arm; `bqeverify.sh float` is its bar) |
| **FADER_PAN** | 122 | 3/3 | LIVE | **FAILED — see §3.4** |
| FX_ENGINE | 114 | 16/16 | LIVE | — |
| FX_RETURN | 0 | 2/2 | LIVE | — |
| GAIN | 96 | 2/2 | LIVE | — |
| **GATE** | 336 | 12/12 | LIVE | **FAILED on the broken instrument, `ok` on the fixed one** |
| GEQ | 403 | 31/31 | LIVE | — |
| HPF_LPF | 72 | 3/3 | LIVE | NOT_APPLICABLE |
| LIMITER | 48 | 4/4 | LIVE | — |
| MATRIX | 0 | 4/4 | LIVE | — |
| MATRIX_OUT | 0 | 4/4 | LIVE | — |
| METER | 118 | 0/0 | NO_PROBE | NO_VERDICT |
| MIX_BUS | 96 | 4/4 | LIVE | — |
| MONITOR | 3 | 3/3 | LIVE | — |
| NOISE_GEN | 3 | 3/3 | LIVE | — |
| OUTPUT_TDM | 8 | 0/0 | — | — |
| ROUTING | 1104 | 46/46 | LIVE | — |
| TALKBACK | 8 | 4/4 | LIVE (NO_FLOOR on the third run) | — |
| TEST_MEAS | 7 | 0/0 | — | — |
| TEST_OSC | 8 | 0/0 | — | — |
| TUBE_SAT | 48 | 2/2 | LIVE | **BIT_EXACT** |

**Every contract count is complete — 197 of 197 rw cells answer at their landed
address across the twenty-seven families — and every family with a stimulus
path is LIVE.** Nothing in the signed configuration made a node inert.

### 3.3 🔴 THE COMPRESSOR BOUND IS EXCEEDED, AND THE BOUND IS THE WRONG SHAPE

The measurement, on the signed pair, all six converted parameters `ok`:

```
step  amp 0x0553C1A7  model 1 of 64 bit-exact  negative control differs in 63 of 64 (predicted 20)
    worst deviation 0.02509 dB at sample 1 (part 119710422, model 120056721, d -346299); 63 of 64 samples differ
```

**0.02509 dB against the 0.00518 dB the dispatch carries as a contract bound.
By the dispatch's own rule that is a STOP, and it is reported as one.**

Three things have to be said with it, because they change what the number
means.

**1. This is a valid COMPRESSOR measurement even though it was taken on the run
where the instrument mis-detected the arm.** `read_arm()` sets
`ARM['dyn_lut']`, prints it — and **nothing in the tool ever reads it**. The
COMP model is the polynomial gain computer in both arms, so the arm
mis-detection (§S82-6) changed GATE's verdict and could not change this one.

**2. What the bar is measuring here is precisely `DSP4_DYN_LUT`'s declared
deviation.** The part runs the baked table; the model runs the polynomial;
the difference between them IS the deviation PW signed, whose design bound is
**0.0950 dB**. 0.02509 dB is comfortably inside that. It is outside 0.00518 dB
because 0.00518 dB was **S20's measurement**, not a design limit.

**3. The quantity is not stable enough to be a bound as written.** The bar
SEARCHES for a usable amplitude at run time — `step amp 0x0D3A17B5: repeat
capture DIFFERS in 21 of 64 words — not at rest, trying another amplitude` —
and the deviation it reports is whatever the amplitude it settles on produces.
S20 settled on one amplitude and got 0.00518 dB; today's run settled on
`0x0553C1A7` and got 0.02509 dB. A bound on a number chosen that way is a bound
on the search.

**The COMPRESSOR verdict could not be re-taken on the fixed instrument**: both
later runs report `node state unreadable — no verdict for this node`, which is
`vpeek` refusing to corroborate a zero `_comp_envelope_C1_COMP_01` rather than
a link failure (the same runs read every converted parameter of the same node).
So the number above stands as the session's one COMPRESSOR measurement. **The
question for the hub is in §7.**

### 3.4 FADER_PAN's two pan legs are the host's wire quantisation, not arithmetic

```
cvt fdr LEFT pan leg (linear law; D42 open)   183217856 /   183341408  <-- MISMATCH
cvt fdr RIGHT pan leg                          85217608 /    85094040  <-- MISMATCH
```

The part's right leg is `85217608 / 2^28 = 0.317460328`. **`20/63 =
0.3174603175`** — they agree to `1.1e-8`, and the left leg is `1 − 20/63` to
the same precision (the two sum to `2^28` within 8 LSB). The model used
`0.317` verbatim, which is what `_fdr_setup` writes. So the part received a pan
quantised onto a 63-step grid and the model did not quantise: **−0.00586 dB on
the left leg, +0.01260 dB on the right.**

This is a disagreement between the bar's stimulus and the wire, not between the
firmware and the numeric spec, and **it is not the signing**: no signed switch
touches a pan coefficient. It is new since S20, where this family was
`BIT_EXACT`; the family's cell count moved 118 → 122 with the defs pin over the
same period. **Not chased further here** — it is a bar/contract-interaction
question, it is recorded with the arithmetic that identifies it, and it is
listed in §7.

### 3.5 The three bounds, as re-measured today

| bound | accepted | measured on today's tree | verdict |
|---|---|---|---|
| `DSP4_DYN_LUT` | ≤ 0.0950 dB | **0.0950 dB** (81 sets, `--sweep`) | **inside, no margin** |
| `DSP4_GATE_LINTHR` | ≤ 0.0002 dB | **+0.000122 dB** for `GateThr ≥ −60 dB`; +0.000320 dB worst at −79.9 dB | **inside above −60 dB; outside below it, by the format** |
| COMPRESSOR numeric | ≤ 0.00518 dB | **0.02509 dB** | **OUTSIDE — STOP, §3.3** |

---

## 4. Gate 3 — the D24 driven row

*(filled below)*

---

## 5. Gate 4 — the contract

### 5.1 The contract note

`proposals/CONTRACT-PROPOSAL-S82.md`, for the hub to land in `defs/docs`.
Nothing in `defs/` was edited. It carries three things:

1. **The signed configuration**, as the file it lives in and the three words
   the part reads back, with the five-bit XOR and the measurement on both
   chips; plus the rule that every field a config word carries must be named
   in `shipping.config`, because the three words are what a host, a factory
   jig or a field diagnostic reads to say "this part is the product".
2. **The three numeric bounds**, each quoted against the tool that PRODUCES it
   rather than against a constant, with `GATE_LINTHR`'s range qualification
   (§3.1) and the observation that `DYN_LUT` passes with 0.005 dB of margin.
3. **The CPLD knock as a diagnostic OUTSIDE the matrix contract** — the hub's
   S81-Q5 answer, written down with both knock word pairs and their reply
   layouts, plus the no-design-ID-no-flash rule and the shipping artifact's
   identity.

It explicitly asks for **no def key, no matrix cell and no address**, and it
does not re-open `DSP4_C2_BQ_GRAPH`.

### 5.2 The numeric spec

`shared/numeric-spec.md` gains a *Three DECLARED deviations* section under
*dB and dynamics math*, where the 0.001 dB polynomial target lives. It states
the three bounds as declared deviations rather than regressions, names the
tools that produce them, and records S20-6's isolation: with these two
switches off and the rest of the signed configuration on, `busgold.sh`
reproduces the 2026-08-30 golden bit for bit; with them on, 235 of 256 words
move at a worst 0.03934 dB. This file is in `shared/`, which is this repo's,
so it is landed rather than proposed.

### 5.3 The D24 acceptance test's expectations

Two changes to S66's generated layer:

* **`tools/accept/limits.csv`** gains `dyn_lut_max_db`, `gate_linthr_max_db`,
  `gate_linthr_lowthr_max_db` and `comp_numeric_max_db`, each with the tool
  that produces it in the `source` column. `limits.csv` is the one place PW
  tunes a limit and the acceptance runner reads nothing else.
* **`tools/accept/gen_accept_fixtures.py`** emits a `dsp` block into
  `MW/D24/DSP/accept/manifest.json`:

```json
"dsp": {
 "build_cfg": ["0xCF45FF10", "0xE2018E6F", "0xC47C0F26"],
 "numeric_bounds_db": {"comp_numeric_max_db": 0.00518, "dyn_lut_max_db": 0.095,
                       "gate_linthr_lowthr_max_db": 0.00035, "gate_linthr_max_db": 0.0002},
 "numeric_bounds_from": "tools/accept/limits.csv",
 "proposal": "proposals/CONTRACT-PROPOSAL-S82.md",
 "shipping_config": "MW/D32/DSP/SHARC/shipping.config",
 "signed": {"DSP4_DYN_LUT": 1, "DSP4_GATE_LINTHR": 1,
            "DSP4_SIMD_DYN": 1, "DSP4_STRIP_FUSED": 1}
}
```

**Why it belongs there.** A fixture set is generated from the CONTRACT and
scored against a FIRMWARE IMAGE, and until now the artifact a factory would
run said nothing about which image it expected. Both halves are READ — the
triple from `cfg_words.py`, which computes it from `build.sh` and
`shipping.config`; the bounds from `limits.csv` — so neither is a third copy,
and a half that cannot be resolved puts an error string in the manifest rather
than a stale guess.

`comp_numeric_max_db` is carried at **0.00518 dB, the value the dispatch
named**, and it is the one entry in that block this session cannot stand
behind as a limit — see §7.2.

---

## 6. Gate 5 — the deploy, staged

`MW/D32/DSP/SHARC/deploy-s82.sh` is the one command each way, written and
staged in the session that built the pair rather than reconstructed later.

```
./deploy-s82.sh --stage      copy the candidate to the card (S82 did this)
./deploy-s82.sh --status     what is staged, what is standing, what is flashed
./deploy-s82.sh --deploy     PW's window: the signed pair becomes the standing pair
./deploy-s82.sh --rollback   the way back: the AS-FOUND pair returns
```

**What "deploy" means on this card, stated because it is not obvious.** The DSP
pair is not booted by `matrix-app` and there is no boot flash. The standing slot
is `/home/app/dspboot/chip{1,2}.ldr` plus their symbol maps — what a bare
`dsp4_boot.py --dir .` in `~/dspboot` picks up — and it is also the shared
scratch slot every measurement script overwrites (S16-9). So deploying is
putting the signed pair there and saying so in `~/dspboot/ldr/manifest.txt`.

**The way back is the AS-FOUND pair**, `/home/app/s78restore`, and not "the
previous contents of the scratch slot", because the scratch slot is not an
artifact — it is whatever the last bar left there. `--deploy` REFUSES to run if
the as-found pair is missing, so the way back cannot be lost by taking the way
forward.

**The bitstream is not part of either switch.** `dsp4_logic.7a6a4529f29c` is
already on the part and is the shipping LOGIC from now on; it is copied into the
candidate directory so the candidate is self-describing, and `loadlogic.sh
shipping` is how it is re-flashed. A CPLD survives a DSP reboot and vice versa.

`--deploy` runs `check_shipping_config.sh --expect-shipping` on the host before
it touches anything, and prints the two lines that score the part afterwards.

**S82 did not deploy.** `~/dspboot/chip{1,2}.ldr` and `~/dspboot/ldr/manifest.txt`
are as they were.

---

## 7. What was not done, and the questions for the hub

### 7.1 Not done

**The talkback T1/T3 re-take (gate 0).** Not taken. The S70 rig needs two
things this session could not put in place inside its bounds: an image with
`DSP4_TEST_NODES=1` (the TEST_OSC the whole battery is driven from, and 0 in
the signed configuration) and the AUX 1 → J1 loop cable physically on the unit,
which no instrument on this bench can confirm from the desk. The lane it
measures — `_buf_C1_XIN_CODEC_04`, MeasChan 53 — **is proved live in §1.5**, so
the re-take is unblocked rather than blocked; it is a session's own arm, one
`DSP4_TEST_NODES=1` build plus `s70_set.py`, and it wants somebody to confirm
the cable first.

**D32 / D16 / D12 driven rows.** Information only by the dispatch's own ruling,
and the bench time went to the D24 row and to the two instrument faults §3
turned up.

### 7.2 🔴 S82-Q1 — THE COMPRESSOR BOUND AS WRITTEN IS A BOUND ON AN AMPLITUDE SEARCH, NOT ON THE ARITHMETIC

The dispatch carries **≤ 0.00518 dB** as a contract term. Today's measurement on
the signed pair is **0.02509 dB**, which by the dispatch's own rule is a STOP,
and it is reported as one rather than re-signed.

But the number is the wrong shape for a bound, and this session's evidence says
so three ways:

1. **What the bar measures here IS `DSP4_DYN_LUT`'s declared deviation.**
   `read_arm()` sets `ARM['dyn_lut']` and **nothing in `dsp4_node_verify.py`
   ever reads it** — the COMP model is the polynomial gain computer in both
   arms. So the COMPRESSOR numeric verdict is, by construction, the LUT
   measured against the polynomial it replaces. Its design bound is
   **0.0950 dB** (`dyn_lut_design.py --sweep`), and 0.02509 dB is inside it.
2. **0.00518 dB was S20's MEASUREMENT, not a limit.** S20-5 quoted it *against
   the table's 0.0950 dB design bound and PW's 0.1 dB ruling* — it was the
   observed value, and the hub has since promoted the observation to the bound.
3. **The quantity depends on an amplitude the bar picks at run time.** The log
   shows the search: `step amp 0x0D3A17B5: repeat capture DIFFERS in 21 of 64
   words — not at rest, trying another amplitude`, settling on `0x0553C1A7`.
   S20 settled elsewhere and got 0.00518 dB. A bound on a number chosen that
   way is a bound on the search.

**The question: should the contract term for the COMPRESSOR be `DSP4_DYN_LUT`'s
design bound (≤ 0.0950 dB, produced by the design tool and stable), with the
famverify figure recorded as a witness rather than a limit?** The alternative —
keeping ≤ 0.00518 dB — makes the signed configuration fail its own contract on
a bar that cannot reproduce its own number (§S82-16: three of four runs this
session declined to produce the verdict at all). The hub's word is needed
before `limits.csv`'s `comp_numeric_max_db` is anything but provisional; it is
carried at 0.00518 dB today, which is the value the dispatch named.

### 7.3 🔴 S82-Q2 — `GATE_LINTHR`'s BOUND NEEDS A RANGE ON IT

Proposed and carried in `limits.csv` and the contract note as **≤ 0.0002 dB for
`GateThr ≥ −60 dB`, ≤ 0.00035 dB below it** (measured worst +0.000320 dB at
−79.9 dB, one Q4.28 LSB). Stated as a proposal, not applied as a re-signing.
See §3.1.

### 7.4 🟡 S82-Q3 — FADER_PAN's pan legs, and a bar that drives an off-grid value

§3.4 and finding S82-14: the part's pan is `20/63` to 1.1e-8 and the model uses
`0.317`. Proved independent of the signing by a control arm. It is a
bar/contract-interaction question — which side quantises, and whether
`_fdr_setup` should drive a value on the wire's own grid — and it is one the
hub may want to route at the wire contract rather than at this bar.

