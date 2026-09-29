provenance: AI-drafted 2026-09-29 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# S151 — why MAIN R and MAIN C were dead, and the pair that fixes them

Session 151, 2026-09-29. Hub dispatch `tasks.md` 2026-09-29 16:52Z, plus the
17:04Z addendum carrying PW's 18:04 BST **"go"**.

Two halves. The first is desk work: read the pair that was actually running
on MW-D24-2 and say, from its own generated sources, why two rear sockets
produce nothing. The second is the switch PW authorised, done on the unit
with nobody in front of it.

---

## 0. Outcome

| # | dispatch item | state |
|---|---|---|
| 1 | what feeds MAIN R and MAIN C in the running pair; what `Chan024Pan001` does; the −14.1 dBFS | 🟢 answered from the images |
| 2 | which built-but-unflashed stage fixes each, and what else the pair moves | 🟢 S143 and S144; the generation does NOT move |
| 3 | the factory list: a MAIN C row, MAIN R's route/limits right for the shipping pair | 🟢 regenerated |
| 4 | a flashable pair and the switch procedure | 🟢 built, gated, and **switched** under the addendum |
| 5 | the report | this file |

**Neither socket was faulty.** They failed for two different reasons and
neither of them is the board:

* **MAIN R** carried the LEFT bus, exactly as MAIN L did, and the route the
  factory list uses for it pans the donor hard right — which empties the only
  bus either MAIN XLR could carry. The test asked the R socket for a signal
  the image could not put there.
* **MAIN C** — the rear panel calls it **C/LF** — is DAC_14, which the running
  graph fed from aux bus 12. A D24 declares aux buses 1–8 and
  `CFG_AUX_MASK` masks the rest off in firmware, so no cell could ever open
  it. It was dead by construction, and the quick list said so by name instead
  of generating a patch that would fail.

---

## 1. The pair that was running, and what it does

`pair.conf` pointed at `/home/app/loopthd/s122` — **factory-test-v2**, chip1
`7f226919a5d181410c3804d92678da19`, chip2 `9e8a1a9edf19a90ce7ac3df1586c00f6`,
both re-read off the unit at 18:2x BST before anything was written. That pair
is the S122 tree, so everything below is read out of the generated sources at
commit `25f7340f` — the code that is in those two images, not a
reconstruction of it.

### 1.1 MAIN R: both MAIN XLRs carry the left bus

The output map is not in dispute and is not invented here:
`docs/d24-dac-lane-xlr-candidate-20260913.md` walked the Analog PCBA netlist
lane by lane and `tools/dsp/gen_dsp_csv.py`'s tables are what the firmware
emits. MAIN L is J56 = DAC_12 = `C2_MAIN_OUT_01`; MAIN R is J57 = DAC_11 =
`C2_MAIN_OUT_02`.

Three greps over the s122 tree settle the rest:

```
src/chip2/nodes/C2_MAIN_OEQ_01.asm:148:    i3 = _blk_C2_MAIN_XOVER;
src/chip2/nodes/C2_MAIN_OEQ_02.asm:148:    i3 = _blk_C2_MAIN_XOVER;
src/chip2/nodes/C2_MAIN_FDR.asm:200:    i0 = _blk_C2_MIX_MAIN_L;   /* input */
```

The two output EQs — the heads of the two output chains — read **the same
block**, and the block they read descends from a master fader that reads the
left mix and nothing else. That is S142-1, and this is it in the deployed
image: the chip-2 main chain is mono from `C2_MAIN_FDR` onward, and
`_blk_C2_MIX_MAIN_R` is computed every block and read by nothing.

### 1.2 `Chan024Pan001`: law, range, and which bus

`Chan024Pan001` is page 1, address 3393 — `C1_FDR_24`'s base (3392) + 1, a
`FADER_PAN` node on chip 1, ramp profile `GainFast` (3 ms up, 8 ms down).
The cell takes an IEEE-754 float 0..1 and `s89_set.py` writes that word raw;
nothing scales it on the way.

The law is linear and the two legs are computed in the node itself:

```
f6 = f2 - f5;            /* L gain = 1 - pan */
...
dm(_fdr_lq_C1_FDR_24) = r2;
f5 = f5 * f7;            /* R gain = pan */
dm(_fdr_rq_C1_FDR_24) = r2;
```

Under `DSP4_PAN_TABLE` the same numbers come out of the one 127-entry table
instead (`tools/dsp/pan_table.py`: index = `fix(pan × 126)`, and law 0's L/R
columns *are* this arithmetic word for word — that identity is the reason the
table could be switched on without moving a channel's audio). Either way:

| `Pan001` | index | L leg | R leg |
|---|---|---|---|
| `f0` | 0 | 1.0 | 0 |
| `f0.5` | 63 | 0.5 | 0.5 |
| `f1` | 126 | **exactly 0** | 1.0 |

`C1_RTG_24` then multiplies each leg by the bus-assign bit and nothing else —
`_rtg_mlq` = `_fdr_lq` × `_rtg_main_on`, with the fader, DCA and mute already
folded into the post-fader mono the coefficient multiplies.

So `mainR@24` (`Chan024MainOn001=1`, `Chan024Pan001=f1`) puts **exact digital
zero** on the left crosspoint. And the left bus is the only bus the chip-2
main chain reads. **Both MAIN XLRs go silent under the mainR route**, which
is what PW saw.

The complementary reading is the useful one: under `mainL@24`
(`Pan001=f0`) MAIN R carries the left bus at the same level MAIN L does. If
PW had moved the lead to MAIN R without changing the route, it would have
passed.

### 1.3 MAIN C / C/LF: masked off in firmware

```
dsp.csv:598  C2_AUX_OUT_12,2,OUTPUT_TDM,Aux 12 Out,1,C2_AUX_DLY_12,,1,1079,
             sport_id=1;slot_start=5;...;signal=DAC_14
```

DAC_14 is J55, the rear **C/LF** XLR ("Center/LF Out", catalog row 35, loop
partner MIC 11). In the s122 graph it is aux bus 12's output, and
`tools/pi/dsp4_config.py` sets `CFG_AUX_MASK = 0x000000FF` for a D24 — eight
aux buses. Aux 9–12 are gated off at block level in the firmware, and D24
declares no `Aux009..Aux012` cells to open them with in any case.

There is no host write, no route and no patch that could have made that
socket produce a sound on the running pair. The quick list already refused to
generate a patch for it and named the reason.

### 1.4 The −14.1 dBFS, and why it is the instrument

The dispatch asks this directly, and the answer changes what it means: **the
image says MAIN L is exact zero under `Pan001=f1`, so the −14.1 dBFS is not
a signal path at all.**

The arithmetic above gives a left crosspoint coefficient of exactly zero, and
no other route into `C2_MIX_MAIN_L` is open. That last clause is checked
rather than assumed — the DSP's own initialisers are

```
.var _rtg_main_on_C1_RTG_24 = 1;
.var _rtg_sub_on_C1_RTG_24  = 0;
.var _rtg_grp_on_C1_RTG_24[4] = 0, 0, 0, 0;
.var _rtg_aux_on_C1_RTG_24[12];      /* zero */
.var _rtg_fx_on_C1_RTG_24[6];        /* zero */
```

and `dsp4_config.py` writes only the config registers at `0xF000+`, never the
cell neutrals — so the group, aux and FX sends that *would* bypass the pan
(the matrix's own `Chan024GrpOn001..004` neutral is 1, and every crosspoint
into `C2_MIX_MAIN_L` boots at 1.0) are all shut on the part, and the station
never opens them.

What is left is the meter. The number the operator reads while a patch is
being made is the strip meter sweep, not the coherent fit the verdict uses,
and `d24_patch.py` says what that meter does in its own comment:

> *"A MIS-PATCH LIGHTS A LANE THAT WAS DARK; A METER TAIL IS A LANE GOING
> OUT. The strip meters hold their peak and decay slowly — measured on
> MW-D24-2, about 6 dB per second"*

The measured figure is **6.52 dB/s** (S138b-6). The preceding patch,
`mainL@24`, left MIC 10 at **−7.6 dBFS**; one second of that drain is
**−14.12 dBFS**. PW read **−14.1**.

So the "hard-right pan left MAIN L only 6.5 dB down" is a latched peak
draining for a second, not a path. It is worth saying plainly because the two
readings lead to opposite conclusions: a real −6.5 dB residue would mean the
pan was not landing, and there would be a bug in the strip. There is not.

**One bench line settles it either way** and needs no lead moved: with the
`mainR@24` route set, read MIC 10 twice about two seconds apart. A path holds
its level; a latch keeps falling at about 6.5 dB/s.

---

## 2. What fixes each, and what else moves

| socket | fixed by | how |
|---|---|---|
| MAIN R (J57, DAC_11) | **S143** | `C2_MAIN_OEQ_02` reads `C2_MAIN_XOVER_R`, a follower of `C2_MAIN_XOVER` down its own `C2_MAIN_FDR_R`/`GEQ_R`/`COMP_R`/`LIM_R`/`DLY_R` chain. Twelve follower nodes, no cell, no SPI address, no dispatch change. |
| MAIN C (J55, DAC_14) | **S144** | DAC_14 becomes `C2_OUT3_OUT` ← `C2_OUT3_DLY` ← `C2_OUT3_SEL` (`sel=0`) ← `C2_CTR_LIM` ← the Centre strip ← `C2_RECV_SUB` ← `C1_BUS_SUB`, which is every channel's `Chan*CtrOn` send. |

S147 signs `DSP4_C2_BQ_GRAPH=1`, S149 adds three chip-2 capacity levers and
S150's aux matrix ships **off**; all three are in the pair and none of them
touches either socket.

**One more socket pair moves and it matters to the factory list**: DAC_15/16
(J53/J54, the rear MONITOR jacks) stop being the main crossover's centre and
high-pass legs and become `C2_MON_OUT_L`/`_R`, the monitor bus. And PHONES
L/R (DAC_09/10) become reachable for the first time.

### 2.1 The generation does NOT move, and that is the whole reason this was a
### small switch

PW's 09-08 rule — app + matrix + firmware + registry together — applies when
the generation moves. It does not here, and that was checked rather than
assumed:

| | unit | repo |
|---|---|---|
| matrix generation | `46109e9fb812` | `46109e9fb812` (`defs.lock` `D24_MATRIX_GEN`) |
| pack `_matrix.mxc` | md5 `011636d0b1442c528561009fd3c5d13d` | not a build input; unchanged |
| panel MCUs H1S1/H1S3/H1S4 | carry `matrix.h` = `#define <Cell> <MxAdd>` | every `MxAdd` identical |
| app | md5 `9c43c397d949fdb5f612ac1977f80ab0` | no DSP addresses in the deployed pack, `dspWriteEnable` false |

So no app was built, no pack was republished and no panel MCU was reflashed.
**No request to the hub for an app build was needed.**

What *did* move is DSP-side only: the DSP address backfill in
`MW/D24/MX/_matrix.csv`, which the unit's pack does not carry (all 5,767 of
its `DspAdd` columns are empty), and `landed-d24.json`, which is how the
bench tools resolve a cell name.

### 2.2 The addresses that moved, and why they had to go with the pair

S144's proposals landed upstream at `defs-v2026.09.28.4`: 40 D24 addresses
changed and 104 were added. The unit's `landed-d24.json` was pinned five tags
back at `defs-v2026.09.19.3`, so on the new pair a bench tool asking for
`MainCtr001Level001` would have resolved 2171 — `C2_MAIN_OUT_03`'s old output
level — instead of 1320, `C2_CTR_FDR`. That is S146-2's trap and it is silent:
a lookup that succeeds is indistinguishable from one that is right. The map
therefore moves in the same step as the pair, not after it.

---

## 3. The factory list

`tools/accept/gen_patch_paths.py` **already refused to run** against the
landed contract before any of this session's changes:

```
cells named but not declared by the product:
  standing: MainCtr001Mute001
  standing: MainL001CrossoverFreq001
  standing: MainL001CrossoverSlope001
  standing: MainSub001Mute001
```

Four cells the standing write named are gone from generation `46109e9fb812`
— the crossover family is `Main Crossover*` now, and neither the Centre nor
the Woof strip has a mute cell of its own (the mute on that path is
`Main Out3Mute`). The no-fallback rule caught it; the deployed list predates
the drop.

What the regenerated list does:

* **A C/LF row joins the XLR output walk**, under the panel name the rear
  panel and the harness port table use: `C/LF`, catalog row 35, loop partner
  MIC 11. Its drive is the new `ctr` route — `Chan024CtrOn001=1`, pan left at
  centre, because a centre send is its own full-level assign into
  `C1_BUS_SUB` and not a pan position.
* **MAIN R's route needs no change and now works**: `main:R` is
  `Chan024MainOn001=1; Chan024Pan001=f1`, and with S143 that is the right bus
  reaching the right socket. Its `level_ref` stays `ref` — the same treatment
  every other XLR output gets, symmetric with MAIN L at `f0`.
* **MONITOR L/R move onto `main:L` / `main:R` at 1 kHz.** They were
  `xover:ctr` and `xover:sub`, and `xover:sub` was tested at 100 Hz precisely
  because a crossover exists to keep 1 kHz out of it. Neither is a crossover
  leg any more.
* **The monitor masters are opened at unity instead of shut.** They were shut
  to keep a 1 kHz tone out of the panel speaker for the length of a pass;
  since S122 the speaker's only source is `C2_HPT_01` and the monitor bus
  reaches no speaker at all. Shutting them now only silences two sockets
  under test.
* **No crossover cell is written at all.** `Main CrossoverOn` boots 0 and
  `_xover_coeffs_next_*` boots the compiled identity in all four stages, so
  both MAIN XLRs are full-range with no write; and nothing this station
  measures reads a crossover leg any more.
* **PHONES L/R stay out of the walk but stay named.** They are reachable now
  (DAC_09/10 = `C2_PHN_OUT_L/R` off the monitor pick-off, through
  `Mon PhonesLevel`), and `UNREACHABLE` carries them with that as their
  reason so they cannot fall off the list silently. A phones patch is a
  stereo TRS with its own null sub-test and a level cell nothing has ever
  measured; it is owed, not done.

Generated into `MW/D24/DSP/s151/list-full` (92 patches, 246 paths) and
`MW/D24/DSP/s151/list-quick` (the exclusions the unit actually runs —
MIC 1–6 and MIC 13–16). The quick list's input set is identical to the
deployed S130 list and it gains exactly one path: P9, C/LF → the reference
input, catalog row 35.

---

## 4. The pair, and the switch

PW said **"go"** at 18:04 BST and the hub's 17:04Z addendum set the
conditions. The unit was switched with nobody in front of it.

### 4.1 Which arm, and why it is not the shipping one

**The whole audio patch station lives behind `DSP4_TEST_NODES`.** TEST_OSC,
`Test MeasChan` and the `_meas_a`/`_meas_b` coherent fit every patch verdict
is built on are all inside `#if DSP4_TEST_NODES`, which `shipping.config`
sets to 0. So the shipping arm (S146 arm B) fixes MAIN R and C/LF in the
audio but **cannot run a single patch of the factory list**, and every
DSP-touching row of the automated set would report NO DATA "wrong image
loaded" besides (runbook §8.2).

The pair PW needs is therefore **S146 arm C — the same S142–S150 graph with
`DSP4_TEST_NODES=1` — promoted to `factory-test-v3`.** That is the
factory-test-v3 candidate S146 named and S148 re-priced; taking it means
moving a signed record, which the runbook reserved for PW, and PW's "go" is
what carries it. It is recorded as such rather than slipped in.

### 4.2 Built, gated, and the triple derived

`MW/D24/DSP/s146/build-images.sh C` rebuilt arm C and **gated it**:

```
chip1 c031613ac9a0a02e4c1d493bea19765d
chip2 0b63f4e044e00e4a7cbe7b2ff345c0b6
every arm built reproduces its recorded image byte for byte
```

with `check-sharc-codegen-drift.sh` clean beforehand (760 generated, 0
differ) and the tree at a committed HEAD.

The build-config triple was **derived, not guessed**: the effective `-D` set
was taken out of `build.sh` itself and run through `diag.h`'s own
`DIAG_BUILD_CFG*_VALUE` macros. The method was cross-validated by computing
the `DSP4_TEST_NODES=0` arm and getting `0xCF45FF10 / 0xE2019E6F /
0xC47C0FA6` — the signed shipping triple, exactly as S149 recorded it. Arm C
then computes `0xCF45FF10 / 0xE3019E6F / 0xC47C0FA6`, and **the part read
back that triple on both chips**, twice, after the switch.

Unlike v1 → v2, **the triple moves**: word 2 bit 12 is `DSP4_C2_BQ_GRAPH`,
0 → 1 (S147). So the image check now catches a substituted pair two ways.
Both md5s stay pinned regardless — S124-3 is the standing lesson and it does
not stop being true because the triple happened to move this time.

### 4.3 What was written, and the rollback

Read off the unit at 18:2x BST, before anything was written, and saved whole
into `/home/app/backup-s151-pre/` with a `MANIFEST.md5`:

| | md5 |
|---|---|
| `loopthd/s122/chip1.ldr` | `7f226919a5d181410c3804d92678da19` |
| `loopthd/s122/chip2.ldr` | `9e8a1a9edf19a90ce7ac3df1586c00f6` |
| `config/_matrix.mxc` | `011636d0b1442c528561009fd3c5d13d` |
| `/home/app/app` | `9c43c397d949fdb5f612ac1977f80ab0` |
| `dspboot/landed-d24.json` | `c5ec5357488e3c24e1520542dbf37a83` |
| `dspboot/dsp4_config.py` | `d92ac7b97dfa6a46c7271ce6f4a44bdc` |
| `dspboot/input_patch.json` | `b95cd6834fa4639a18e2e3b533652884` |
| `selftest/d24_selftest.py` | `4c63b0954efc11b88737a124a887201e` |
| `selftest/quick/` | the whole S130 list, 9 files |

Then, in this order:

1. **`/home/app/loopthd/s151/`** — a NEW directory; the old pair is not
   overwritten and survives the window untouched. Both `.ldr` md5s re-read on
   the unit and equal to the gated build.
2. **`dspboot/landed-d24.json`** — `defs-v2026.09.19.3` → **`.28.4`**, 3,800
   cells. This had to move with the pair, not after it: on the new graph a
   tool asking for `MainCtr001Level001` under the old map would have resolved
   2171 (`C2_MAIN_OUT_03`'s old output level) instead of 1320 (`C2_CTR_FDR`),
   and a lookup that succeeds is indistinguishable from one that is right.
3. **`dspboot/dsp4_config.py`** — `CFG_MTX_MASK` for D24 `0x3` → `0x0`
   (S143). One line; nothing else in the file differs.
4. **`dspboot/input_patch.json`** — contract tag only; the patch is
   byte-identical.
5. **`selftest/d24_selftest.py`** — the v3 record.
6. **`selftest/quick/`** — the regenerated list (§3).
7. **`selftest/pair.conf`** — `/home/app/loopthd/s122` →
   `/home/app/loopthd/s151`.

Every deployed file was md5-compared against the repo copy afterwards and
every one matches.

**The rollback is one line and a boot.** The SHARCs have no boot flash —
they are SPI slave-booted every session — so putting `/home/app/loopthd/s122`
back in `pair.conf` and booting is the whole DSP rollback. The host files
come back from `/home/app/backup-s151-pre/`.

**Not touched, because the generation did not move:** the app, the matrix
pack, H1S1/H1S3/H1S4, MH1 and the LOGIC CPLD. No app build was requested of
the hub because none was needed.

### 4.4 Verification on the part

* **Both images read back.** `md5sum` on the unit equals the gated build, in
  the pair directory and in the stage the runner copies to.
* **Both chips boot and answer**: `DR2 PASS  BOOT_STAGE 7/7, BUILD_ID
  0x20260812/0x20260812, 31 lanes CARRYING`.
* **Both chips report the v3 triple**: `('0xCF45FF10', '0xE3019E6F',
  '0xC47C0FA6')` on CS1 and CS2 — so `_check_factory_image()` accepts the
  pair, and **not one row anywhere reported "wrong image loaded"**.
* **Self-test sections B and C: 28 PASS / 1 FAIL / 14 NO DATA** (43 rows).
  Every NO DATA is a standing structural gap with its reason already in the
  record (no H1S1 version cell, CS6/7/8 are not DSP selects, AS-DAC retired,
  AS-CPLD unreadable under the slave design, AS-PWR has no reader).
* **`IC1 PASS  MAIN_L c1 −98.5 → c2 −102.8 dBFS, MAIN_R c1 −103.4 → c2
  −102.6 dBFS`** — the inter-chip test reads the two main lanes separately
  and both cross the link.
* **The inter-chip sign-bit gate is CLEAN on both lanes**, four reads
  (see §4.6 for the one transient).
* **All nineteen new standing-master cells write and read back**, at the
  S143/S144 addresses, on the part:
  `Mon Level1/2` 1789/1790, `Mon PickOff` 2404, `Main Out3Mode` 2400,
  `Main Out3Mute` 2417, `Main Out3Delay` 1368, `MainCtr Level` **1320**
  (`C2_CTR_FDR`, the Centre strip), `MainCtr EqOn` 1345, `MainCtr LimiterOn`
  1364, `MainCtr AntiFbOn` 2312, `MainSub Level` 2368 (`C2_WOOF_FDR`), and
  the `Main`/`MainL`/`MainR` masters. This is the one real risk the new list
  introduced — the standing write is a hard stop if a cell does not land —
  and it is closed on the part rather than argued.
* **The route cells land**: `Chan024CtrOn001` (chip 1, 3397) = 1,
  `Chan024MainOn001` = 1, `Chan024Pan001` = 1.0.

### 4.5 As left

| | |
|---|---|
| `pair.conf` | `/home/app/loopthd/s151` (factory-test-v3) |
| `list.conf` | `/home/app/selftest/quick` — unchanged |
| pair | booted, BOOT_STAGE 7 both chips, sign-bit gate CLEAN |
| AN_EN (GPIO26) | **lo** |
| CS_M (GPIO27) | driven **hi** |
| 595 chain | SAFE image VERIFIED 200/200 |
| `matrix-app` | **inactive**, as found |
| `d24-testui` | **active**, owns the screen, as found |
| old pair | `/home/app/loopthd/s122` intact |
| backup | `/home/app/backup-s151-pre/`, 2.5 MB, `MANIFEST.md5` |
| free | 843 MB |

### 4.6 The one FAIL, and it is not the switch

**AL1 fails, and it failed on the OLD pair too.** That is measured, not
argued.

| pair | base | tone | SNR | THD | verdict |
|---|---|---|---|---|---|
| v2, 16:41Z (PW's run) | −51.7 | −29.7 | 22.1 | −23.8 (6.43 %) | PASS |
| **v3**, 17:27Z | −50.0 | −29.4 | 20.7 | −21.9 (8.00 %) | FAIL CLIP |
| **v3** ×3, 17:29Z | −51.1 / −49.0 / −49.8 | −29.4 / −29.3 / −29.4 | 21.7 / 19.6 / 20.4 | −21.7 / −21.6 / −21.4 | FAIL CLIP |
| **v2 again** ×2, 17:31Z | −51.8 / −50.2 | −29.3 / −29.4 | 22.4 / 20.9 | −21.5 / −21.3 | **FAIL CLIP** |
| v3, 17:34Z | −56.5 | −29.3 | 27.2 | −20.8 (9.16 %) | FAIL CLIP |

The old pair, re-booted from `/home/app/loopthd/s122` and graded by the old
record out of a worktree at the pre-switch commit, fails **the same way with
the same numbers**. So the change is on the bench between 16:41Z and 17:30Z,
not in the images.

Two more things say the same. **The tone level never moves** — −29.3 to
−29.7 dBFS across every run of both pairs, against the S124 law's −29.8 — so
the drive, the speaker, the air and the MEMS chain are all doing what they
did. And **the path is byte-identical between the two pairs**: `C2_HPT_01`
and `C2_SPKR_OUT` have the same `dsp.csv` row, the same generated ASM and
the same SPI addresses (2175, 1796) in both trees, and on chip 1 — which is
the whole receive side — only `cue.asm` and `rta.asm` differ, and both files
are entirely inside `#if DSP4_CUE` / `#if DSP4_RTA && DSP4_CUE`, which are 0
in this arm. Chip 1's thirty-two node files and its process chain are
byte-identical.

**What actually moved is not settled and is left for the bench**: the
baseline wanders 2 dB run to run and the THD does not follow it, so this is
not simply a noisier room. The strongest candidate is the rails: PW's passing
run used `--al1-keep-rails` and held AN_EN up across the whole `[dsp]` batch,
while every run here raises it for about 18 s and drops it again. Recorded as
**S151-1**.

**One transient, recorded rather than smoothed over.** The inter-chip
sign-bit gate read `FOLDED` on both lanes once, immediately after a
reset-and-boot, with chip 1 sending 42/64 negative words and chip 2 seeing
none. Read again moments later on the same boot it was CLEAN, and CLEAN on
the three reads after that, and the full B,C run had read CLEAN on both lanes
before it. This is S89-1's known intermittent — `dsp4_boot_linked.sh` exists
to retry a boot on exactly this exit code — and it is not new here. Recorded
as **S151-2** because it was seen on this pair.

---

## 5. What PW should hear next session

Nothing audio was proved tonight and nothing could be: it needs a lead in a
socket. The list below is what the images predict, in the order that makes
each answer worth having. All of it runs off the factory station's own quick
list, which is already on the unit and already has the C/LF row.

1. **MAIN R, the headline.** `MAIN R → MIC 10` on patch **P8** should now
   read what MAIN L reads on P7 — about **−7.6 dBFS**, the same level, from
   the right bus. Before tonight this socket was silent under this route, on
   a healthy board.
2. **MAIN L must not change.** P7 is the control. If MAIN L moved, the
   stereo split did something it should not have.
3. **MAIN C — the rear panel's C/LF — is a patch for the first time.** New
   patch **P9**, `C/LF → MIC 10`, catalog row 35. It carries the **Centre**
   strip (`Main Out3Mode` = 0), fed by `Chan024CtrOn001`, and should read at
   about the same level as MAIN L. If it is silent, that is now a real
   finding about the socket rather than a graph that could never reach it.
4. **The two MONITOR jacks have changed what they carry.** P41/P42 are the
   monitor bus's left and right legs now, both at 1 kHz — not the crossover's
   centre and sub legs, and MONITOR R is no longer tested at 100 Hz. Expect
   both to read, and expect them to follow MAIN L and MAIN R.
5. **A stereo check worth one minute**: with `mainL@24` set (pan hard left),
   MAIN R should be **silent** and MAIN L loud; with `mainR@24`, the other
   way round. On the old pair both sockets carried left and this test had no
   meaning.
6. **The −14.1 dBFS reading, settled on the bench in two reads.** With the
   `mainR@24` route set, read MIC 10 twice about two seconds apart. A path
   holds its level; the strip meter's latch falls at about 6.5 dB/s. This
   confirms §1.4 without moving a lead.
7. **AL1 (S151-1).** Try it once with `--al1-keep-rails`, the way PW's
   passing run had it, before treating the CLIP verdict as a fault.

**PHONES L/R are reachable now and have no patch yet** — owed, and named in
the list's not-run section rather than left to fall off it.
