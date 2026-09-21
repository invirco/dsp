provenance: AI-drafted 2026-09-21 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S89b — pricing the two single-switch-off options

Session 89b, 2026-09-21, host-side only, unit parked as S89 left it. Hub dispatch
`tasks.md` 2026-09-21 (same-session continuation).

## Outcome in one paragraph

**Gate 1 is complete and its 🔴 trigger does NOT fire**: `DSP4_SIMD_DYN=0` with
`DSP4_STRIP_FUSED=1` is a real, buildable, meaningful configuration, so the two
options the dispatch names are both available and there is no need to fall back to
pricing `SIMD_DYN=0 + STRIP_FUSED=0` together. Both arms build clean from the signed
set with exactly one switch moved, and each moves exactly one bit of one word of the
signed triple. **Gates 2, 3 and 4 cannot be done host-side** — the driven row, the
family verification and the cable-loop THD row are all on-part measurements, and one
of them additionally needs a CPLD flash that the parked-unit constraint forbids. That
is S89b-Q1 below, and it is the only thing standing between this and a finished
table.

## The control that makes the rest trustworthy

The signed baseline was rebuilt from this tree and **reproduces the S82 pair byte for
byte**:

    chip1.ldr  e3e25a79c4619d1a44305258f99fac7d   (426,464 B)
    chip2.ldr  41a6b913e5f77bac698e136abd9aac65   (367,024 B)

which are the md5s in `~/dspboot/candidate-s82/README.txt` and in
`MW/D24/DSP/s82/signed.md`. The host-side config mirror independently computes the
signed triple as `0xCF45FF10 / 0xE2018E6F / 0xC47C0F26`, which is what the part reads
back. So this build environment *is* the signing environment, and anything built here
is directly comparable to the signed pair rather than merely similar to it.

## Gate 1 — both options are buildable, and the 🔴 does not fire

**`DSP4_SIMD_DYN=0` with `DSP4_STRIP_FUSED=1` builds and is meaningful.** Checked
three ways rather than assumed:

- **No build-time coupling exists.** The only `#error` guarding `DSP4_SIMD_DYN` is
  `dyn_simd_fx.asm:847` — *"DSP4_SIMD_DYN needs the POLYNOMIAL log2/exp2 … Build with
  DSP4_DYN_TABLES=0"* — and `shipping.config` already carries `DSP4_DYN_TABLES=0`, so
  it is satisfied. Nothing anywhere makes `STRIP_FUSED` depend on `SIMD_DYN`.
- **The generated tree carries both branches**, so no regeneration is needed and the
  switch is a genuine build-time lever: `dsp_codegen.py` emits the paired forms behind
  `#if DSP4_SIMD_DYN`, and with it off *"every `BLK_*_P1` collapses onto its `BLK_*`"*
  and *"every `_P1` macro aliases its original"* (its own comments, lines 12612 and
  19106).
- **It builds, clean, both chips.**

The capacity doc's phrase that `SIMD_DYN` and `STRIP_FUSED` *"ship together"* is a
statement about how they were **priced** (as a pair, ~65 points of chip-1 base load
between them), not a dependency. They can be moved independently.

## The signed triple: each option moves exactly one bit

Computed host-side by `tools/dsp/cfg_words.py`, the same mirror
`check_shipping_config.sh` uses and the same one the part is scored against:

| configuration | DIAG_BUILD_CFG | DIAG_BUILD_CFG2 | DIAG_BUILD_CFG3 |
|---|---|---|---|
| signed | `0xCF45FF10` | `0xE2018E6F` | `0xC47C0F26` |
| `DSP4_SIMD_DYN=0` | unchanged | **`0xE2018E6D`** | unchanged |
| `DSP4_DYN_LUT=0` | unchanged | **`0xE2018A6F`** | unchanged |

One named switch each, one bit each, stated — which is the form the S89 dispatch
required for any move of the triple.

## What the two switches cost in MEMORY (host-side, measured)

This is not the driven row and does not answer the dispatch's question. It is
included because it is real, it is free, and it shows the two switches spend in
**different pools** — which is itself useful to PW.

| | chip 1 code | chip 1 DM data | chip 2 code | chip 2 DM data |
|---|--:|--:|--:|--:|
| signed | 181,490 (69.2 %) | 309,612 (82.5 %) | 152,548 (58.2 %) | 279,116 (74.4 %) |
| `SIMD_DYN=0` | 161,004 (61.4 %) | 307,988 (82.1 %) | 140,010 (53.4 %) | 277,292 (73.9 %) |
| `DYN_LUT=0` | 178,970 (68.3 %) | 265,492 (70.7 %) | 148,048 (56.5 %) | 240,596 (64.1 %) |
| **freed by `SIMD_DYN=0`** | **−20,486** | −1,624 | **−12,538** | −1,824 |
| **freed by `DYN_LUT=0`** | −2,520 | **−44,120** | −4,500 | **−38,520** |

**`SIMD_DYN` is a code lever; `DYN_LUT` is a data lever** — the tables are the DM.
All pools stay below 90 % on both arms, so **neither option is blocked on memory**,
and `DYN_LUT=0` additionally takes chip 1's DM primary region off the 100 %-spilling
condition (195,040/195,040 → 185,740/195,040, no longer full).

Image sizes: signed 426,464 / 367,024 B; `SIMD_DYN=0` 404,352 / 352,660 B;
`DYN_LUT=0` 379,824 / 324,004 B.

## S89b-Q1 🔴 — gates 2, 3 and 4 are not host-side, and one of them conflicts with the parked unit

The dispatch opens *"No bench needed: this is a host-side capacity re-measurement"*.
That premise does not hold, and it is better to say so now than to return a table
with three invented columns:

- **Gate 2, the driven row, is an on-part measurement.** `capacity.sh --driven` scps
  the images to the bench and runs `capacity_run.sh` / `dsp4_capacity.py` there.
  `cap_table.py` only *formats* the JSON that run writes; there is no host-side model
  that produces a driven-row percentage. **And the driven regime specifically needs
  the `driveall` diagnostic bitstream flashed** (`capacity.sh`'s own header points at
  `loadlogic.sh driveall` / `drive_audio.sh`; the stimulus is in the CPLD by design
  since S19, precisely so silent and driven are the same image). Flashing it
  contradicts *"the unit stays parked … shipping CPLD in flash"*, and it is the flash
  that cost S88 most of a session when it was left on the part by mistake.
- **Gate 3, `famverify`, is an on-part measurement too** — `famverify.sh` stages to
  `app@192.168.1.219` and scores the families on the DSP.
- **Gate 4's fold column** requires the cable-loop THD row, which is analog: DAC →
  cable → ADC. It also currently needs PW, because the loop cable is on **Monitor L**,
  not AUX 1 — PW moved it for the TRS jack set and the hub held it there (S89-Q2, still
  open).

**Three ways forward — hub picks one:**

  a) **Authorise the bench and the `driveall` flash.** The full table as specified,
     restoring the shipping bitstream afterwards (the S88 runbook step: flash →
     design-ID readback → DSP double boot+config). Roughly two hours: two arms × two
     products × the driven ladder, plus famverify, plus the fold row.
  b) **Bench but no CPLD flash.** `capacity.sh` without `--driven` gives the
     silent-default and silent-loaded rows on both arms, no bitstream change, unit
     stays parked. That **ranks** the two options against each other, which is the
     decision PW actually has to make, but it cannot say whether either holds the
     **84.47 % driven** bar, because that bar is a driven number. Roughly 40 minutes.
  c) **Host-side only, as scoped.** What is above is all of it: buildability, the
     triples and the memory deltas. The capacity question stays open.

My recommendation is **(b) tonight, (a) when the bench is next free** — (b) answers
"which is cheaper" without touching the bitstream or the parked state, and (a) is the
only thing that can answer "does it still fit".

**I have not recommended a switch to drop**, because on the evidence that exists the
honest ranking is a memory ranking, and the bar is a cycle bar. Recommending on
memory alone would be exactly the silent trade the S89 dispatch said was PW's to make.

## Files

- `MW/D24/DSP/s89/switch-price.md` — this report.
- Arms built and kept for whichever option the hub picks (scratch, not committed):
  signed baseline, `DSP4_SIMD_DYN=0`, `DSP4_DYN_LUT=0`.
