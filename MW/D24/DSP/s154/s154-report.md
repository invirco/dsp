provenance: AI-drafted 2026-09-30 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S154 — the MAIN output clamp, the pan law, and two patch-test fixes

Hub dispatch `tasks.md` 2026-09-30 16:03Z (+ the constant-power addendum).
Unit: MW-D24-2 (app@192.168.1.219). Everything below was measured on the part
unless it says otherwise.

## 1. The MAIN clamp: four dynamics stages that no cell could reach

**Cause.** The chip-2 main path runs through `C2_MAIN_COMP` (the bus
compressor), `C2_MAIN_LIM` (the bus brick wall), and `C2_MAIN_OCOMP_01/02`
(a compressor on each MAIN output). All four were generated with `_on_ = 1`
at the compressor default (−20 dB, 4:1) or the limiter default (−0.5 dB).
**None of them has a cell in the D24 contract**, so neither the app nor the
factory station could ever switch them. The contract's main-path dynamics are
the two per-output limiters (`MainL/MainR Limiter*` = `C2_MAIN_OLIM_01/02`)
and nothing else. The monitor/phones pick-off is `C2_MAIN_FDR`, ahead of all
four, which is why it read clean to full scale.

Read off the running v3 pair through its own dispatch table: `c2@1414`
(`C2_MAIN_COMP` On) = 1, thr −20.0, ratio 4.0; `c2@1464` / `c2@1509` (OCOMP 1/2)
= 1, −20.0, 4.0; `c2@1430` (`C2_MAIN_LIM`) = 1, −0.5.

**The hub's sweep reproduced, then cleared, on the v3 pair.** Strip 24, TEST_OSC,
hard left, all output-bus processing off:

| osc | AUX_OUT_01 | MAIN_OUT_01, as found | MAIN_OUT_01, three comps' On words = 0 |
|---|---|---|---|
| −32 | −32.00 | −32.00 | −32.07 (both columns, same instant) |
| −22 | −22.00 | −22.07 | −22.00 |
| −12 | −12.00 | **−18.42** | −12.07 (both) |
| −6 | −6.00 | **−18.04** | −6.00 |

**Fix (generator, not a hand edit).**
- `tools/dsp/dsp_codegen.py::dyn_on_default()`: every compressor and limiter
  takes its power-on `_on_` word from the graph's `on=` param, which defaults to 1.
- `tools/dsp/gen_dsp_csv.py` gives the four stages `on=0`. Their SPI words stay,
  so the address map does not move.
- `tools/dsp/dsp_validate.py::check_uncelled_dynamics` is the guard. It fails
  any compressor or limiter master that has no cell in
  `defs/products/d24/dsp.csv` and boots on. The only exemptions are the
  firmware-masked paths (strips 25–32, aux 9–12). Against the old graph it
  names exactly these four.
- Only those four rows of `dsp.csv` change. `check-sharc-codegen-drift.sh`
  passes and `test_dsp_validate.py` is 20/20.

## 2. MAIN vs AUX, and the pan law (PW ruling 2026-09-30: constant power)

**The ~6.7 dB question.** At centre pan the old image put **6.02 dB** in
the pan law. That was linear: `(1−p, p)`, 0.5 per side, as the MON/PHN pick-off
showed. The remaining ~0.7 dB is consistent with the uncelled compressors of
§1 acting on a −18 dBFS peak with their −20 dB threshold. Neither is in the
block: the compressors have no cells, and PW has now ruled the law.

**Where the law lives now.** The table is `tools/dsp/pan_table.py`, which is
already the single source for the generator, the bench probes and
`fixed_ref`.
- **Law 2** is new: *stereo constant power*, `L = cos(p·90°)`, `R = sin(p·90°)`,
  with the far side forced to an exact zero at the extremes.
- It is **`DEFAULT_LAW`**. The codegen emits `_sys_lcr_law` from it, and the
  `_pan_legs` read selects among three resident tables.
- Laws 0 and 1 (R5) are unchanged word for word. Law 2 answers the question
  R5 left open: what a non-LCR strip reads under constant power.
- No D24 cell selects the law (there is no `Sys LcrLaw` and no `Chan LcrOn`),
  so the boot word *is* the product's pan law. `pan_table.py`'s self-test
  asserts law 2 is the boot law.
- It cannot drift back silently: `check-sharc-codegen-drift.sh` fails on a
  hand edit, and the self-test fails on a law change.
- Pan 0.25 is not on the 127-position grid. It lands on index 32
  (θ = 22.86°, not 22.5°), so it reads −0.71 / −8.21 dB rather than the ideal
  −0.69 / −8.34.

**The proof, on the S154 pair (factory-test-v4), at the chip-2 TX slots**
(`_tx_out_slot_*`, what the DACs are sent; `s154_sweep_fixed.out`). The MAIN
columns are MAIN minus AUX at the same send:

| pan | osc −32 / −22 / −12 / −6 | MAIN L − AUX | MAIN R − AUX |
|---|---|---|---|
| 0 (hard L) | AUX = drive to 0.00 at all four | **+0.00** | silent |
| 1 (hard R) | same | silent | **+0.00** |
| 0.5 | same | **−3.01** | **−3.01** |
| 0.25 | same | **−0.71** | **−8.21** |

MON L/R and PHN L/R follow the same law, to the hundredth, at every row.

*Instrument note.* The live `_blk_` of `C2_MON_OUT_R`, `C2_MON_R` and
`C2_PHN_R` read constants, so they are not audio buffers. `_blk_C2_MON_OUT_L`
and `_blk_C2_PHN_OUT_L` read signal at hard right. Both are symbol artefacts:
the TX slots are clean. Read outputs at `_tx_out_slot_`. A bulk read of a live
block fails its checksum (the block moves), so the tool takes 400 single-word
peeks at random offsets and times; a fixed stride phase-locked to the tone and
read whole rows 0.69 dB low.

## 3. Phones L/R: the design is symmetric, so the 2 dB is a part

The chain comes from the D24 Analog rev B schematic (sheets 12, 59, 60) and
`~/mx26/docs/d24-netlist-global-pins.csv`.

| Stage | L (DAC_09) | R (DAC_10) |
|---|---|---|
| DAC | U92.19 / .18 | U92.22 / .23 |
| Input resistors | 2 × 1k: R1977, R1979 | 2 × 1k: R1987, R1989 |
| Op-amp (NJM4580) | U90:B | U91:B |
| Feedback | 6k2: R1975 | 6k2: R1985 |
| Output | U90:A follower, 2 × 33R | U91:A follower, 2 × 33R |
| Jack | J10 tip | J10 ring |

- **L and R are identical by design:** the same values (0.1% parts), the same
  NJM4580, and no volume stage.
- Both channels have the same gain from the DAC N pin: −6k2 / 2k = −3.1
  (+9.8 dB).
- L and R are not swapped.

So a **steady** 2 dB with R the louder side is not designed in. It points to
a part or assembly fault. A flat offset fits one of:
- R1977 or R1979 high, or R1975 low (L quiet)
- R1985 high, or R1987 or R1989 low (R loud)
- a bad joint at U92.19

A frequency-dependent offset would instead point at a filter capacitor:
C840–C842 on L, C849–C851 on R.

**Bench asks:**
- Compare the offset at 100 Hz and at 10 kHz.
- With the power off, measure R1975 against R1985, and R1977+R1979 against
  R1987+R1989.

This is a hardware item for mx26's `docs/d24-pcb-supplier-notes.md`, which
this spoke does not own. It is not code.

*Reported by the netlist read, not verified here.* Pin 5 (+ input) of U90 and
U91 is on GND, so only the DAC's N pin drives each channel and the P leg
(R1982/C843, R1992/C852) is a dummy load. There is no DC block at J10. U82.5
(line outputs) is also on GND, so the claim that the line stage is drawn
differently was **not** confirmed.

## 4. The patch test: every processing stage bypassed, and restored

PW ruling 2026-09-30 ~16:45.

**Generator.** `tools/accept/gen_patch_paths.py::cells_processing_bypass` builds
the bypass from the defs rows, with no hand list. It is written as
`_standing_bypass` in `patch-routes.csv` (219 cells). It takes, on every cell
category a patch's signal can pass through (Chan 1–24, Aux 1–8, Grp,
Main/MainL/MainR/MainCtr/MainSub, Mon):
- every processing node's On switch (EQ, HPF/LPF, GEQ, crossover, limiter,
  compressor, gate, anti-feedback, tube), set to 0
- every delay, set to 0 ms
- each strip's HPF corner, set to its lowest (the strip HPF has no On)

The side-chain filter switches are left alone, because they are not stages in
the path. The processing cells were removed from the hand-written standing
lists.

**The 219 cells, by family:**
- **Chan ×24:** CompOn, GateOn, EqOn, TubeOn, Delay, EqHpf
- **Aux ×8:** EqOn, LimiterOn, AntiFbOn, AntiFbCtrlOn, AntiFbLimOn, Delay
- **Grp ×4:** CompOn, EqOn
- **Main:** AntiFbOn, AntiFbCtrlOn, AntiFbLimOn, CrossoverOn, Delay, Out3Delay
- **MainL / MainR / MainSub:** EqOn, LimiterOn
- **MainCtr:** EqOn, LimiterOn, AntiFbOn, AntiFbCtrlOn, AntiFbLimOn
- **Mon:** Delay, PhonesDelay

**Not bypassable, and said so:**
- The GEQs have no On or Bypass cell. Their only cells are the 31 band gains.
  They boot flat.
- Bus-EQ `EqHpf` cells are coefficient bases, covered by their EQ's `EqOn`.

**Runner** (`tools/pi/d24_patch.py`).
- `Station.bypass_capture()` reads every bypass cell before the standing
  write. It writes what it found to `/home/app/selftest/bypass-found.json`
  before anything is changed.
- `Station.bypass_restore()` runs first in `teardown()`. It writes the found
  values back and verifies them. The record is deleted only when all of them
  read back.
- If a pass dies before its handback, the next pass restores from the record
  and does **not** take the bypassed zeros as the product's settings. This is
  proved on `SimUnit`.
- The whole-list dry run is unchanged: 246 PASS, 1 NO DATA (standing).

**Proof on the part** (`s154_bypass_proof.py`, the station's own methods, v4
pair at its boot settings):
- 219 read, and 64 were found non-zero: all 8 aux limiters, all 24 strip
  compressors, the 24 strip HPF words, the 4 group compressors, and the
  MainL/MainR/MainCtr/MainSub limiters.
- MAIN − AUX is **+0.00 dB** at −12 and −6, hard L on MAIN_OUT_01 and hard R
  on MAIN_OUT_02. The limit was 0.5 dB.
- Restore: 219 of 219 equal to the value found, and the record was removed.
- A first run of the same proof, taken after the old standing write had
  already zeroed the strip and aux processing, found only 7 non-zero. That
  set is the hub's `restore-processing-2026-09-30.txt`, which was taken from
  the same kind of state.

## 5. A resumed pass boots a dead pair

`d24_runall.one_pass()` now calls `ensure_pair()` before the resume branch,
so it runs on every pass, fresh or resumed. That runs `d24_selftest.py
--local --ensure-pair`, which is the existing `link_alive()` / `boot_pair()`
path and nothing new:
- If the pair answers, nothing is written.
- If it doesn't: AN_EN is lowered if it was high, the pair is booted twice
  with config, the sign-bit gate runs, then S_RUN
  (`codec4619.py --run --reinit`) and the 595 chain to SAFE.
- The rails are left down for the station to raise, as it does today.

On the part:
- **Pair up** (`ensure_pair_alive.out`): "the pair is up; nothing written",
  and AN_EN was untouched.
- **Pair down** (`ensure_pair_dead.out`): AN_EN was lowered first, then
  `!RST_D` dipped, as a reboot leaves it. Both chips were NOT answering; the
  run booted `/home/app/loopthd/s154` via `pair.conf`, CHIP_ID was verified,
  the sign-bit gate read CLEAN on both lanes, S_RUN ok, SAFE VERIFIED
  200/200, both chips answered at BOOT_STAGE 7, AN_EN was left low, and there
  was no wrong-image line.
- The AN_EN-high branch was **not** staged, because `!RST_D` is never pulsed
  with the rails up (PW 09-10).
- The bench START after a real reboot is PW's call.

## 6. factory-test-v4, deployed

**The image.**
- S146 arm C from the S154 tree: chip1 `7caa1bf46f4b325c39d60b7df2fe93e1`,
  chip2 `4a9406ed755e8bc0d02ac9937c70590f`.
- The triple does not move (no flag moved): `0xCF45FF10 / 0xE3019E6F /
  0xC47C0FA6`, read off both chips.
- The control build of HEAD reproduces v3 byte for byte (`c031613a…` /
  `0b63f4e0…`).

**On the unit.**
- The new pair is `/home/app/loopthd/s154`. `/home/app/loopthd/s151` is
  untouched.
- `pair.conf` is repointed, and the s90 stage holds the v4 pair.
- Deployed `d24_selftest.py` `b6443328`,
  `d24_patch.py` `eddadf49`, `d24_runall.py` `ea21925d` and
  `s121/patch-routes.csv` `003cab2a`.
- The backup is `/home/app/backup-s154-pre/`, with a MANIFEST.md5 of the v3
  s90 files, `pair.conf` and all four tools.
- **Rollback:** `echo /home/app/loopthd/s151 > /home/app/selftest/pair.conf`,
  restore the four files from the backup, then boot.
- Every S146 arm's md5 moves with this tree, including shipping arm B.
  `build-images.sh` records the new values. The **shipping pair is not
  re-signed here.**

## 7. Handback, and what is not done

**As left on MW-D24-2:**
- The factory-test-v4 pair is booted, from `pair.conf` → `/home/app/loopthd/s154`.
- AN_EN is **low** (the station raises it), CS_M is driven high, and the 595
  chain is SAFE (VERIFIED 200/200).
- TEST_OSC is off, `d24-factory` and `matrix-app` are inactive, and
  `d24-testui` is active.
- There is no `bypass-found.json`, and `runall/state.json` was not touched,
  so the stopped pass is still resumable.
- The product settings in `restore-processing-2026-09-30.txt` read back as
  found: MainL/MainR/MainSub limiters and Grp1–4 compressors are all 1. They
  are also v4's boot defaults.
- The strip-24 route and the strip-transparent standing cells from the proof
  are left written. The next pass writes its own standing over them.

**`regenerate-dsp-contract.sh`** runs its codegen, sync and validate steps
clean, then stops at `gen_dsp.py`'s landed-contract gate. That gate reports
the 176 S150 aux-matrix cells, which are proposed and not landed. HEAD fails
it identically, so this change does not cause it. No contract bump is made:
no cell or address moved.

**Owed to PW / the hub:**
- One bench START after a real reboot, to see the resumed-pass boot on the
  glass.
- The phones resistor and joint check (§3).
- Signing shipping arm B if the S154 graph is to ship. Its md5s moved and it
  is not re-signed.
- Recording the phones item in mx26's supplier notes.
