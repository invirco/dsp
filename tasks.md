**PW RULING 2026-08-30 (~09:45): TUBE IS A PLUG-IN OPTION, not a fixed
strip feature.** Consequences: the BASE strip's floors, ceilings and
margin-at-32 are computed with TUBE bypassed/absent (already the
measured convention — now ruled); TUBE's ACTIVE cost is accounted
against the PLUGIN headroom, not the base budget; its golden coverage
(D29) is built as plugin-class coverage (model + vectors for the active
path, engaged like any plugin would be), and the bypass path's
zero-cost skip is the base-strip requirement. Capacity reporting keeps
TUBE out of the required-strip rows.

## HUB DISPATCH 2026-08-30 09:07Z — session 7: Rtg retirement propagation, Dca/DcaOn host-managed, address-authority finding   [status: 🟢 done — **THE Rtg RETIREMENT IS PROPAGATED AND `Dca`/`DcaOn` HAVE LEFT THE DSP, WITH THE AUDIO PROVEN BIT-EXACT ON THE PART THREE INDEPENDENT WAYS.** The generator emits the masters' current spelling — the wire tables in `docs/contract/`, verified byte-identical to mx26 HEAD's own, are the authority — and `tools/dsp/master_names.py` is the ONE rename table the generator, the wire-contract join and the bench probes share. **The pinned `_matrix.csv` cannot follow and that is now a stated, measured fact rather than a silent mismatch (D62)**: `defs.lock` pins `defs-v2026.08.20`, the rename landed after it on an mx26 commit carrying no contract tag, and `sync-from-mx26.sh --update-lock` refuses an untagged HEAD by design — so the backfill resolves current-name-first, legacy-name-second, and REPORTS the split (**2,064 rows through the legacy spelling today, 0 the day the pin advances**). A rename that reaches no matrix row is a hard failure, because `--force` would otherwise CLEAR the DSP columns of rows it merely failed to find. **Two of the fifteen renames change the word, and one of them mattered**: the harness used to bridge the spellings by INSERTING `Rtg`, which cannot produce `RtgFx`, so **192 `FxOn` cells and 16 `Dest` cells were being reported as reaching no DSP address when they do — coverage moves 5,076 → 5,270 addressed on no kernel change at all.** **PW's Q2 ruling applied in full: `_fdr_dca_sel_` AND `_fdr_dca_gain_` are GONE rather than dormant**, the word at base+3 is RESERVED (compacting it would move every address after it in a 144-word channel block), and dsp.csv is the single source — the nodes that carried it declare `host_cells=Dca,DcaOn` and the generator, the contract report and `conform.sh` all read it from there. **D38 returns to 896 addresses / 762 cells** — the 56 did not become less inert, they stopped being addresses — the MCU ghost table goes 5,537 → 5,481, and `conform.sh` gives **exactly the predicted classes: 6,032 ECHO / 388 UNMAPPED / 117 CLEARED / 159 skipped / 56 HOST_MANAGED, `VERDICT: PASS`** with both negative controls firing. **W0: the image changes and gets SMALLER (301,988 → 301,732 and 182,540 → 182,060 bytes; new baseline chip1.ldr `3f0e479a`, chip2.ldr `ab43c75b` from `033d2921`/`f8883d4c`) and the AUDIO IS BIT-EXACT — `x * 1.0` is exactly `x` in IEEE 754.** Measured, not argued: **the bus golden reads 0 of 256 against a golden that was NOT re-taken**, the inert probe's driven window reads **`0x015E7E31`, the same word as session 6**, and `dcapar.sh`'s four D59 numbers come back identical to session 6's. `dcapar.sh`'s DCA rows now measure the RULING instead of D57 — **`SPI_ERR_COUNT` 1 → 1 across the mapped neighbour 0x0052 and 1 → 2 across 0x0053, with 0 of 32 bus words moving** — which subsumes D57, because an address the handler rejects cannot scale anything. **THREE FINDINGS OPENED, THE ONE THE DISPATCH ASKED FOR AND TWO FOUND WHILE DOING IT. D61: the DSP wire addresses have no authority outside this spoke** — mx26's masters have no `Dsp*` COLUMNS AT ALL, `AddrAlloc` in `gen_dsp_csv.py` is an unanchored bump counter, and **giving the channel GAIN node one extra word moves 347 of chip 1's 348 addressed nodes and renumbers 4,794 of the 4,798 addresses chip 1 uses, with nothing in the hub able to see it**; `MW/D24/MX/_matrix.csv` carries 0 of 5,125 rows with a `DspAdd`, so D24's half of the "single shared address map" exists only as D32's copy. The proposal is stated in full (masters carry authored address columns seeded from today's backfill, the generator reads instead of allocating, the backfill inverts into a check, the contract version starts covering the map). **D62**: two contract vintages, plus the operational trap that `check-contract-drift.sh` reads the mx26 WORKING TREE — a plain `git pull` in `~/mx26` makes it fail with `ERROR: Hash mismatch for D24_DEF_SHA256`, which is why this session ran the whole contract flow against a worktree pinned at the tag. **D63**: `Fx001Mute001` and `Main001Mute001` are in the pinned matrix under BOTH spellings, so their address was ambiguous between two rows; the generator now names them and states its rule. ALL STANDING BARS PASS: conform `VERDICT: PASS` (6,032/388/117/159/56, both negative controls firing), inert phase PASS on its own boot with 12 of 12 classes inert and both positive controls at 32 of 32, busgold **0 of 256 GRAPH BIT-EXACT**, dcapar `VERDICT: PASS`, bqst 0 of 16 on all three arms with its negative control at 15 of 16, dynst 0 of 32 on all three arms, mtrverify `METER_BIT_EXACT` with both negative controls firing, and numverify 57 of 57 with `NEGCTL PASSED` **on a re-run**. **THAT RE-RUN IS THE ONE THING THAT DID NOT GO CLEANLY, AND IT WAS NOT THE ARITHMETIC**: the first run's negative-control arm got `link never usable` on three consecutive boot cycles, and on the re-run the IDENTICAL positive image (`0105a7e6`) that had passed 57 of 57 nine minutes earlier failed its first cycle and passed its second — an image that is bit-exact, then unreachable, then bit-exact again on the same hash is a link fault, and it is recorded against the standing chip-ID/link intermittent rather than chased. `bqst` met the same class and ABSORBED it, because D60's fix votes on the same `Scope` object instead of believing one read. Bench restored to the new baseline and verified on the part; the CPLD was never touched.]   [model: opus]

model: opus

SESSION 7 — contract naming + the Q1/Q2 consequences (rulings f23ec5a,
04455cd). Mechanical under recorded rulings; no new decisions.

1. RTG RETIREMENT PROPAGATION: the masters retired the Rtg prefix
   (2026-08-25) but dsp.csv never followed. Rename through dsp.csv, the
   generated kernel labels, and every harness/tool reference
   (RtgDca->Dca, RtgMute->Mute-family names per the current masters in
   docs/contract/ wire tables — the wire table's cell column is the
   authority for spelling). Byte-identical control where the change is
   name-only; conform.sh re-run proves the renamed surface end to end.
2. DcaOn INTAKE: the new DcaOn family exists in the contract
   (docs/contract updated). Host-managed like Dca — the DSP does NOT
   read it; it appears in dsp.csv marked host-managed so conform.sh
   expects store-only behavior for both.
3. Q2 CONSEQUENCES: mark Dca + DcaOn host-managed; REMOVE the
   `_fdr_dca_gain_*` hook (not dormant — gone); conform results table
   updated (the 56+ addresses move to the host-managed class, out of
   the DSP-writable surface); W0 for the image change.
4. ADDRESS-AUTHORITY FINDING (flagged in the ruling): document, as a
   numbered finding with a concrete proposal, that dsp.csv currently
   invents SPI page/addresses because the masters' Dsp columns are
   empty — proposal: masters (mx26) become the address SOT and dsp.csv
   becomes generated. Findings only on this item; the migration is its
   own future workstream.
5. All standing bars re-run; bench restored verified; push main;
   review index updated.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

**PW RULING 2026-08-30: Q2 CLOSED — DCA GAIN IS APPLIED BY THE CM4,
inside the isolated control-plane daemon.** Composite architecture
ruling: (1) ALL non-GUI code moves to a dedicated CM4 control daemon —
separate PROCESS, pinned to an isolated core (core 3: isolcpus/
nohz_full, SPI IRQ affinity, RT priority) — owning SPI mastering, ramp
TARGET writes (stepping stays in the DSP ramp engine; targets only ever
cross the wire), DCA folds (effective fader = fader dB + DCA dB, mutes
OR-ed, written through the existing ramps), coeff prep, preamp gain,
meter ingest, scene recall. GUI owns cores 0-2. (2) Meters: control
core drains the wire at wire rate into a SHARED-MEMORY RING; the GUI
samples it once per frame — wire rate and paint rate decoupled.
(3) Kernel-side consequences, this repo: `Dca`/`DcaOn` are HOST-MANAGED
cells — the DSP never reads them; remove the `_fdr_dca_gain_*` hook
rather than leaving it dormant; conform.sh marks the family
host-managed; the 56 addresses leave the DSP-writable surface.
(4) Core-isolation parameters land in cm4-setup-pi.sh (provisioning
mandate — parameters, never hand-tweaks). App-side daemon split is an
mx26 workstream with a design pass first.

**PW RULINGS 2026-08-30 (morning): Q1 CLOSED + DcaOn minted + Rtg
propagation ordered.** (1) Dca assignment encoding = INTEGER index,
0 = unassigned, 1..8 = DCA n (option a). (2) NEW CELL FAMILY `DcaOn`
(on/off) minted in the mx26 masters beside every Dca assignment cell —
the strip FOLLOWS its assigned DCA only while DcaOn is on; the
assignment is preserved while off (value+On idiom, like AuxSend/AuxOn).
Wire tables in docs/contract/ updated. (3) The Rtg prefix was RETIRED
in the masters (ruling 2026-08-25, 43 seeds renamed) but dsp.csv never
followed — propagate the retirement through dsp.csv/kernel labels and
the harness (RtgDca -> Dca etc.), and while in there: the masters carry
no DSP addresses for these rows, so dsp.csv is inventing SPI addresses —
flag the address-authority gap as a finding with a proposal (masters as
address SOT, generated outward). Q2 (DCA architecture across chips) is
STILL OPEN — assignments remain stored-and-inert until PW rules it.

---

### Outcome 2026-08-30 (session 7) — the Rtg retirement, and DCA leaving the DSP

Commits `<C1>`, `<C2>` and the documentation commit carrying this block.

#### W0, stated before any of it was built

The tree at `6a5040f` was built first and reproduced the bench's running
baseline exactly — `chip1.ldr 033d2921`, `chip2.ldr f8883d4c` — so the
"before" column below is the image the product was running.

| item | expected image delta | actual |
|---|---|---|
| the `Rtg` retirement | cell NAMES only: `_matrix.csv`, `ghost_cells.c/.h`, `mx_dsp_map.h`, `dsp_address_map.md`. No SHARC source line changes, so **no contribution to the image at all** | as predicted — every changed `.asm` in this session is a FADER_PAN, and those changed for the DCA removal below |
| `Dca`/`DcaOn` host-managed: `_fdr_dca_sel_` and `_fdr_dca_gain_` removed, 0x0053 reserved | **the image CHANGES and gets SMALLER** — two DM words and two instructions gone from each of 56 FADER_PAN nodes, 56 dispatch entries to 0, 56 `.extern` lines gone. **AUDIO BIT-EXACT**: `_fdr_dca_gain_` is 1.0 and `f1 * 1.0` is exactly `f1` in IEEE 754, and `_fdr_dca_sel_` was read by no emitted line | **new baseline chip1.ldr `3f0e479a`, chip2.ldr `ab43c75b`**, `301,988 → 301,732` and `182,540 → 182,060` bytes; `_fdr_dca_*` is 0 symbols of 5,463 in the chip-1 map, `_fdr_level_*` still 32 |
| the bench probes stop writing 0x0053 | no image change; audio-neutral, because the cell already reached no audio (0 of 32 bus words, measured session 6) | the bus golden was **NOT re-taken** — it is the check on this prediction |


#### 1. The Rtg retirement, propagated — and the pin that could not follow it

The masters dropped the `Rtg` infix on 2026-08-25. The generator now emits
the current spelling and **`docs/contract/d32-wire-table.csv` is the
authority for it** — that file is byte-identical to mx26 HEAD's own
generated wire table, which was checked rather than assumed.

The map is not "strip `Rtg`". Two of the fifteen renames change the word:

| generator emits | the pinned `_matrix.csv` carries | why |
|---|---|---|
| `Chan001FxOn001` | `Chan001RtgFx001` | the family is an on/off, and the masters spell it `Chan[1-32]FxOn[1-6]` |
| `Talk001Dest001`, `Noise001Dest001` | `Talk001Rtg001`, `Noise001Rtg001` | `Talk[1-1]Dest[1-3]`, `Noise[1-1]Dest[1-10]` |

and the other thirteen (`Level`, `Pan`, `Mute`, `MainOn`, `CtrOn`,
`GrpOn`, `AuxOn`, `AuxSend`, `AuxPick`, `FxSend`, `FxPick`, `MatrixOn`,
`MatrixSend`) do drop the infix. **`RtgFx` is the one that mattered**: the
harness used to bridge the two spellings by INSERTING `Rtg` into a
wire-table name, which turns `Chan001FxOn001` into `Chan001RtgFxOn001` —
a cell that does not exist — so 192 documented `FxOn` cells and 16
`Dest` cells were being counted as reaching no DSP address when they do.
Coverage against the wire table moves **5,076 → 5,270 addressed** and
**513 → 305 absent from `_matrix.csv`** on no change to the kernel at
all: that is the rename buying back 194 cells of accuracy in the report.

**The masters in this repo did not follow, and cannot be made to.**
`defs.lock` pins `defs-v2026.08.20`; the rename landed after it, mx26
carries exactly one contract tag and it is that one, and
`sync-from-mx26.sh --update-lock` refuses an untagged HEAD by design. So
the tree runs on two contract vintages — wire tables at HEAD, masters at
the pin — and that is filed as **D62**, with the bridge stated rather
than hidden:

* `tools/dsp/master_names.py` holds the rename table, and the generator,
  the wire-contract join and the bench probes all import it. One table,
  because three copies of a temporary translation is how a temporary
  translation becomes permanent.
* `gen_dsp.py` resolves each generated cell against the matrix by its
  CURRENT name first and its LEGACY name second, and **reports the split:
  2,064 rows reached through the legacy spelling today**. That count goes
  to 0 the day the pin advances, which is the retirement test for the
  whole module.
* A rename that reaches nothing is a **hard failure**, not a silent miss.
  Map `FxOn` to `Fx` instead of `RtgFx` and 192 rows quietly stop
  matching — and `--force` then CLEARS the DSP columns of rows it merely
  failed to find. The generator refuses to backfill in that case and says
  which rename is wrong.

Two more things fell out of doing it. **`_matrix.csv` carries two cells
under BOTH spellings** — `Fx001Mute001`/`Fx001RtgMute001` and
`Main001Mute001`/`Main001RtgMute001`, instance 001 only in both families —
so their address is ambiguous between two rows; that is **D63**, and the
generator now names both and states its rule (the current-spelling row
takes the address, the legacy twin is cleared). And of the 2,109 cells the
generator emits in a renamed family, **2,107 are documented in the wire
table under exactly that name**; the two that are not are
`Sub001Level001` and `Sub001Mute001`, because the masters also moved the
category `Sub` to `MainSub` — which is D52's territory, and is named so
that 2,107 is not read as 2,109.

#### 2. `Dca` and `DcaOn` are host-managed, and they are off the DSP

PW closed Q2 the same morning: the CM4 control daemon owns the fold —
effective fader = fader dB + DCA dB, mutes OR-ed, written through the
level TARGET the DSP already ramps — and only ramp targets cross the
wire. So the DSP needs neither the assignment nor a master gain.

**Both hooks are gone rather than dormant, which is what the ruling
says.** `_fdr_dca_gain_` was the resolved master gain, sitting at unity
and multiplied into the Q4.28 fader coefficient every block;
`_fdr_dca_sel_` was D57's stored assignment, correct for a cell the
kernel must not scale by and pointless once nothing on the DSP resolves
it. Neither exists now, in either the fixed or the archived float
template.

**The word is RESERVED, not reclaimed.** 0x0053 keeps its place in the
144-word channel block with a dispatch entry of 0. Compacting it would
have moved every address after it — the whole map, the MCU ghost table
and every stored golden — to save one word of a page that is nowhere
near full. That restraint is the same hazard D61 is about, met once in
this session.

The fact is single-sourced in **dsp.csv**: the FADER_PAN nodes that used
to carry the word declare `host_cells=Dca,DcaOn`, and everything else
reads it from there — `gen_dsp.py` reserves the word and mints no cell,
`wire_contract.py` reports the families as a class of their own, and
`dsp4_conform.py` classifies the address from the generator's own
dispatch comment rather than from a cell list that would go stale.

What moved, all of it checkable:

| | before | after |
|---|---|---|
| D38 inert addresses / cells | 952 / 818 | **896 / 762** — the 56 did not become less inert, they stopped being addresses |
| dispatch entries unmapped | 420 | **476** |
| ghost cells (the MCU's table) | 5,537 | **5,481** |
| `_matrix.csv` rows with DSP columns | — | the 56 `RtgDca` rows are CLEARED by `--force` |
| conform presence classes, measured on the part | 6,088 ECHO / 388 UNMAPPED / 117 CLEARED / 159 skipped | **6,032 ECHO / 388 UNMAPPED / 117 CLEARED / 159 skipped / 56 HOST_MANAGED** — the prediction, to the address |

`HOST_MANAGED` is its own presence class on purpose: unmapped BY RULING
and unmapped BY OMISSION look identical from the part, and the whole
value of the `UNMAPPED` total is that it means "nobody has said why".

#### 3. D61 — the addresses have no authority outside this spoke

The dispatch asked for this as a finding with a concrete proposal, and
not to start the migration. Stated as measured facts:

* **the masters carry no addresses at all.** `src/pd/d32-mx-master.csv`
  and `d24-mx-master.csv` have no `Dsp*` COLUMNS — not empty ones, none —
  and `expand_matrix.py` emits `DspSpi`/`DspPage`/`DspAdd`/`DspAddHex`
  empty into `_matrix.csv`.
* **this repo invents them, positionally.** `AddrAlloc` in
  `tools/dsp/gen_dsp_csv.py` is a bump counter with no anchor, so every
  address is a consequence of the ORDER of the `add()` calls in one
  Python file, and `gen_dsp.py` backfills the result into the hub's own
  copy of the contract.
* **the blast radius, measured rather than asserted:** giving the channel
  GAIN node one extra word — the most ordinary contract change there is —
  **moves 347 of chip 1's 348 addressed nodes and renumbers every
  address from 4 to 4,797 — 4,794 of the 4,798 chip 1 uses**, and nothing in mx26 would see it.

A fourth fact, found while checking the third and folded into D61: the
architecture rules ONE firmware and ONE shared address map for D24 and
D32, `gen_dsp.py` backfills only `MW/D32`, and **`MW/D24/MX/_matrix.csv`
carries 0 of 5,125 rows with a `DspAdd`** — so `wire_contract.py
--product d24` joins 4,946 documented cells to nothing, and D24's half of
the shared map exists only as D32's copy of it.

The proposal is in D61 in the review index: mx26's master carries
`DspSpi`/`DspPage`/`DspAdd` as AUTHORED columns seeded once from the
current backfill (so no address moves on adoption day), `gen_dsp_csv.py`
stops allocating and reads them, `gen_dsp.py`'s backfill inverts into a
check, and the contract version starts covering the address map as well
as the cell surface — which is the property the flow is missing today.

#### 4. The standing bars

| bar | result |
|---|---|
| **contract conformance** | **`VERDICT: PASS`** — **6,032 ECHO / 388 UNMAPPED / 117 CLEARED / 159 meters skipped / 56 HOST_MANAGED**, which is the prediction above to the address; 12 declared-unit checks pass and the 16 that fail are the named D41 known mismatches, `ChanCompPar` still exact at 0/25/50/100 %; both negative controls fired (wrong-unit 4 of 4, no-verify 64 of 64 UNVERIFIED). Table at `goldens/conformance-20260830-s7.md` |
| **inert phase** | **PASS on its own boot** — driven window at peak **`0x015E7E31`, the same word session 6 measured**, noise floor ZERO, both positive controls 32 of 32, 12 of 12 sampled classes INERT. `0x0053` is no longer among the candidates because it is no longer an address; `0x00D0 Chan002CompType001` took its place. Stored at `goldens/conformance-20260830-s7-inert.md` |
| **bus golden** | **0 of 256 — GRAPH BIT-EXACT**, sha256 `ba3f52ec…` against `busgraph-postD59-20260830.json`, which was NOT re-taken. That is the W0 audio claim measured rather than argued: the `_fdr_dca_gain_` multiply came out of every fader and the bus did not move by one word |
| **cell semantics** | **`VERDICT: PASS`**, with the DCA rows rewritten to measure the ruling instead of D57. **DCA-U: `SPI_ERR_COUNT` 1 → 1 across the MAPPED neighbour 0x0052 and 1 → 2 across 0x0053** — the reserved address is rejected, and the negative control in the same batch says the counter is measuring the address rather than the link. **DCA-A: 0 of 32 bus words differ across that rejected write**, bus peak `0x015E7DD7`. The D59 rows read **`0x0579F843` → `0x00444578`** on the gain-reduction control and **`0x015E7DD7` / `0x0011114D`** on the bus — the same four words session 6 measured, which is a third independent statement that the audio did not move |
| **biquad vs model** | **0 of 16 on all three arms** (ref vs blk, ref vs model, blk vs model), negative control fires at 15 of 16 — **and the D60 fix earned itself again on the way**: the link answered `CHIP 0` three times before settling, and because `check_chip()` votes on the same `Scope` object rather than believing one read, the bar absorbed it and ran instead of reporting a dead part |
| **dynamics** | **0 of 32 on all three arms** (COMP, GATE, BQ4); pairing 2.04× / 2.27× / 1.43× |
| **numerics** | **57 of 57 BIT-EXACT, `NEGCTL PASSED`** — 31 of 31 boundary vectors detected, 26 of 26 non-boundary untouched, third-word cost +2.043 c/MAC. **It took two runs and the reason is not the arithmetic**: the first run's negative-control arm reported `link never usable` on three consecutive boot cycles, and on the re-run the SAME positive image (`0105a7e6`) that had passed 57/57 nine minutes earlier also failed its first cycle and passed its second. An image that is bit-exact, then unreachable, then bit-exact again on the identical hash is a LINK fault, and it is recorded as one rather than chased |
| **meter** | **`METER_BIT_EXACT`** with both negative controls firing — wide model `pk_blk>>4 4169139 / ms_blk 16576495` at gain 0.497, narrow model correctly rejected; the same words session 6 read |

#### The link fault this session ran into, recorded and not chased

It cost a bar re-run and it is worth naming, because it looked twice like
a result. `numverify`'s negative-control arm reported `link never usable`
on three consecutive boot cycles and the bar exited non-zero. On the
re-run, **the identical positive image — same hash, `0105a7e6` — that had
passed 57 of 57 nine minutes earlier failed its FIRST boot cycle and
passed its second**, and then the negative control passed cleanly. An
image that is bit-exact, then unreachable, then bit-exact again on the
same hash is a LINK fault and cannot be an arithmetic one.

`bqst` hit the same class from the other side: the link answered `CHIP 0`
three times before settling, and the bar ran anyway because D60's fix
votes on the same `Scope` object instead of believing one read. That is
the difference between the two: the instrument that votes absorbed it,
the instrument that boots-and-hopes reported it as a failure. Recorded
against the standing chip-ID/link intermittent, not diagnosed.

#### Bench hand-back

Restored to the NEW shipping baseline and verified on the part, not from
a summary. `chip1.ldr 3f0e479a`, `chip2.ldr ab43c75b`, md5-matched on the
Pi against the build — and that build is the FOURTH independent
reproduction of those two hashes this session (this session's first
build, `conform.sh`'s, `dcapar.sh`'s and the restore build all agree).

Both chips read through `dsp4_audio_verdict.py`: **`BOOT_STAGE 7`,
`FRAME_COUNT` advancing at 6000/s on chip 1 and 5999/s on chip 2** (48 kHz
/ block 8 — the "expect ~1500" in that tool's output is the BLOCK=32 label
of review finding D49, not a shortfall), `SPORT0_ERR_A 0x00000000` on
both, `DMA0_STAT 0x00006201` and `0x00006200`, `SPI_ERR_COUNT 0`,
`PRODUCT_ID 0x00540001`. GPIOs released; **`matrix-app active` with all
three MCUs verified on the FIRST restart** (H1S1, H1S4, H1S3 at
11:06:20, read from `/home/app/logs/log`). The CPLD was never touched and
no JTAG operation was run this session, so its bitstream is as it was.

## HUB DISPATCH 2026-08-30 02:57Z — session 6: D57 DCA semantics, CompPar dry default, captable cache   [status: 🟢 done — **BOTH CELL-SEMANTICS DEFECTS ARE FIXED AND PROVEN ON THE PART WITH THE SAME INSTRUMENT ON BOTH SIDES OF THE CHANGE. D57: `RtgDca` now ASSIGNS — before, writing the masters' documented "off" value of 0 gave a SILENT bus (peak `0x0000000F`) with the chain witness naming `_buf_C1_FDR_01 = 0` while `_buf_C1_DLY_01` carried `0x02BCFACA`; after, RtgDca=0 gives bus peak `0x015E7DD7` and reads WORD FOR WORD identical to RtgDca=1.0, 0 of 32 differing** — the cell reaches no audio at all, which is the fix, and `conform.sh` now drives its strip with RtgDca=0 so it has a standing witness. The 56 addresses join the D38 inert list (896 → 952) and the harness confirmed `Chan001RtgDca001` INERT on the part. **D59: `CompPar`'s default was 0 and left the compressor FULLY DRY — before, the bus read `0x03FFFF74` at BOTH a −20 dB and a −55 dB threshold, 0 of 32 words differing, while `_comp_gain_` captured on the driven graph moved `0x0579F843` → `0x00444578`; after, the same two thresholds give `0x015E7DD7` and `0x0011114D`, 32 of 32 differing.** The masters rule the UNIT and document NO DEFAULT (`MxDat` is empty on the row), so 100 % is the dispatch's reading and that gap is filed as a PW question along with D57's two. **W0: the image changes and D59 changes the audio BY DESIGN — new baseline chip1.ldr `033d2921`, chip2.ldr `f8883d4c`** from `e9ac266e`/`73b4f168`, and the pre-fix tree was rebuilt in a worktree to reproduce the bench's running baseline exactly before anything was measured. **The bus golden was re-taken IN THIS SESSION** (234 of 256 words differ, then **0 of 256** against the re-take on a second independently built image), which is the rule D58 left. `captable.sh`'s scratch tree is now keyed by a digest of block size + `dsp.csv` + the codegen + every file of `src/`, so a stale reproduction is impossible rather than unlikely; the spot row was rebuilt from `src32-b4da7d1cfa5fa868` — which contains `bq_pairs.asm`, `_fdr_dca_sel_` and `_comp_parallel_ = 100.0` — and measured **654,819 cycles/pass against session 5's 657,082**, 0.34 % apart, so **32 channels at BLOCK 32 / 983.04 MHz is still ON THE LINE** (99.92 % of budget one run, 100.26 % the other) and no improvement is claimed. **ALL BARS PASS: conform `VERDICT: PASS`** (6,088 ECHO / 388 UNMAPPED / 117 CLEARED / 159 skipped, identical to sessions 4 and 5, both negative controls firing), inert phase PASS on its own boot with both positive controls at 32 of 32, busgold 0 of 256, bqst 0 of 16 on all three arms, dynst 0 of 32 on all three, numverify 57/57 with NEGCTL PASSED, mtrverify `METER_BIT_EXACT`, dcapar `VERDICT: PASS`. **TWO OF THOSE BARS HAD TO BE REPAIRED FIRST AND NEITHER FAILURE WAS THIS SESSION'S CODE**: `bqst.sh` had been reading the part through `dsp4_diag` and reported `MAGIC 0x00000000` five boots running — proven pre-existing by reproducing it from a worktree at the previous HEAD — and `numverify.sh` scored a dead link as an arithmetic failure, because **a ZERO votes as cleanly as a value**. Both now read through the paced instrument and corroborate a zero before believing it. Bench restored to the new baseline and verified on the part: both chips `BOOT_STAGE 7`, 6000 and 5999 frames/s, `DMA0_STAT 0x00006200`, `SPORT0_ERR_A 0`, `SPI_ERR_COUNT 0`, GPIOs released, `matrix-app active` with all three MCUs verified on the FIRST restart; CPLD never touched.]   [model: opus]

model: opus

SESSION 6 — the two active contract bugs from session 5, plus harness
hygiene. Mandate-covered (cell semantics = the masters, ruled at
session 4); capacity levers wait for PW's morning.

1. D57: Chan RtgDca is documented as a DCA ASSIGNMENT; the kernel
   treats it as linear gain (writing 0 silences the channel while the
   level word reads 1.0). Fix per the masters' semantics: the cell
   selects/assigns, it does not scale. If the masters' documented
   semantics are ambiguous about the assignment encoding, implement the
   unambiguous part (0 must NOT silence) and file the residue as a PW
   question with the options stated.
2. CompPar default leaves the compressor FULLY DRY (session 5 measured:
   bus unchanged across thresholds while comp_gain moved) — a
   default-configured strip has a compressor that does nothing. Fix the
   DEFAULT to the masters' documented default (100% wet unless the
   masters say otherwise — cite the row); prove on the part with the
   session-5 method (bus moves with threshold at default).
3. captable.sh cache bug (session 5's false-table cause): key the cache
   by source-tree state, not block size — a stale reproduction must be
   impossible; state the fix and re-run one spot row to prove it.
4. Re-run conform.sh + all standing bars after 1-2; update the
   conformance results table; both fixes get before/after harness rows.
5. Ledger W0 (image changes by design); bench restored verified; push
   main; update review index (D55/D57/D58 statuses with commits).

NOT in scope: capacity levers, D20's remaining coefficient-fold
amendment (PW ruling), D38 wiring prioritization — all queued for PW.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

---

### Outcome 2026-08-30 (session 6) — D57, D59, and a cache that could not go stale

Commits `dfce458`, `9624d0d` and the documentation commit carrying this
block.

#### W0, stated before any of it was built

| item | expected image delta | actual |
|---|---|---|
| D57 (`RtgDca` → `_fdr_dca_sel_`) | changes the shipping image: the dispatch table moves and every FADER_PAN grows a word. **Audio-neutral** — nothing reads the new word and `_fdr_dca_gain_` stays 1.0 | proven audio-neutral on the part (DCA-0 and DCA-1 captures agree word for word) |
| D59 (`CompPar` default 0 → 100 %) | changes the shipping image AND THE AUDIO BY DESIGN: a default strip's compressor goes from fully dry to fully wet | **new baseline chip1.ldr `033d2921`, chip2.ldr `f8883d4c`** from `e9ac266e`/`73b4f168` |
| `captable.sh` cache key | no image, no source change at all — a harness-side directory name | shipping build byte-identical either side |

The pre-fix tree was built in a clean worktree at `83a95ee` and reproduced
the bench's running baseline exactly — `e9ac266e` / `73b4f168` — so the
"before" column below is the image the product was running, not an
approximation of it. `conform.sh` then rebuilt the fixed configuration
independently and got `033d2921` / `f8883d4c` again.

#### 1. D57 — the DCA assignment that silenced the channel

`<Cat>[n]RtgDca[1-1]` is documented as **"DCA group assignment (1-8 or
off)"**, MxDatS 9, no Table, no unit, the `InstantCtl` profile of a
selector — and the dispatch landed the written word in
`_fdr_dca_gain_*`, which `FADER_PAN` multiplies into its Q4.28
coefficient. Writing the documented "off" value of 0 set the strip's
fader gain to zero.

**The masters win: the cell selects, it does not scale.** It now
dispatches to `_fdr_dca_sel_*`, a stored assignment no line of the sample
path reads. `_fdr_dca_gain_*` remains as the RESOLVED master gain, at
unity, and nothing but a ruling writes it.

**Measured on the part, same instrument both sides** (`dcapar.sh`, new
this session and written to run against either image — a fix with no
before is an assertion):

| row | BEFORE — `e9ac266e` | AFTER — `033d2921` |
|---|---|---|
| NULL | the driven bus repeats word for word after 3 captures | the same |
| DCA-0 (`RtgDca = 0`) | **bus peak `0x0000000F` — SILENT**, chain witness: signal reaches `_buf_C1_DLY_01` at `0x02BCFACA` and stops at `_buf_C1_FDR_01 = 0` | **bus peak `0x015E7DD7`** against an injected `0x08000000` |
| DCA-1 (`RtgDca = 1.0`) | bus peak `0x015E7DD7`, **32 of 32 words differ** from DCA-0 | bus peak `0x015E7DD7`, **0 of 32 words differ** from DCA-0 |

The last row is the fix stated as a measurement: after it, the two values
a host might write for "no DCA" produce the same 32 bus words, because
the cell reaches no audio at all.

**`conform.sh` now drives its strip with `RtgDca = 0`** — the value that
used to kill it — so the fix has a standing witness in a bar that runs
every session, rather than a note in a document.

#### 2. D59 — the compressor that was on, working, and inaudible

The blend is `out = dry + par*(wet − dry)` and the kernel's power-on
`_comp_parallel_` was **0**, so a compressor that is ON, above threshold
and visibly reducing gain passed the input through UNCHANGED. Session 5
found it while driving a strip; this session measured it as a default and
fixed it.

**What the masters do and do not say, cited.** `Chan[1-32]CompPar[1-1]`
carries Notes "Parallel compression blend (dry/wet)", MxDatS 33 and Table
`0=0/127=100/[Lin]`. The unit is therefore ruled and is percent (that was
D40). The DEFAULT is not: the `MxDat` column — the one that carries a
documented default where the masters have one, `EqGain` 60 of 121,
`EqFreq` 127 of 255 — **is empty on this row and on `Main[1-4]CompPar`**.
So 100 % is the hub dispatch's reading rather than a citation, it is the
only value at which a default-configured compressor behaves like a
compressor, and **that the masters document no default at all is filed as
a PW question** rather than buried in the kernel.

The value comes from the node's own `parallel=` param
(`gen_dsp_csv.py` → `dsp.csv` → `comp_par_default()`), not from a
constant in a generator, so a ruled default lands by changing the graph
source. 100 % scales to exactly 2^31, which int32 cannot hold, so the
power-on `_comp_parq_` is `0x7FFFFFFF` — the same clamp the block-rate
conversion applies, stated at the declaration so the first converted word
and the power-on word are the same number.

| row | BEFORE — `e9ac266e` | AFTER — `033d2921` |
|---|---|---|
| GR (the positive control): `_comp_gain_C1_COMP_01` captured on the DRIVEN graph, CompThr −20 dB vs −55 dB | `0x0579F843` → `0x00444578`, 32 of 32 words differ | **identical to the before run**, `0x0579F843` → `0x00444578` |
| PAR: the BUS at those same two thresholds, CompPar UNTOUCHED | `0x03FFFF74` at BOTH, **0 of 32 words differ** | `0x015E7DD7` and `0x0011114D`, **32 of 32 differ** |

The gain-reduction control reading the same numbers on both images is the
point of having it: the compressor's arithmetic did not change, only
whether the bus hears it.

**Two probe defects were found and fixed getting there, and both would
have produced a confident wrong answer.** The first version of the probe
ran its DCA rows first — and `drive_strip()` writes `CompPar = 100 %`, so
the compressor rows then measured that write instead of the power-on
default and reported a threshold moving the bus on the PRE-fix image. A
power-on default can only be read before anything writes the cell, and
the probe now says so in its docstring and skips the write. The second:
with the compressor DRY the strip runs at full scale into the fader and
two back-to-back captures differ in 32 of 32 words — session 5's fixed
rest interval got a zero noise floor from a graph whose compressor was
WET and squashing the gate's residual ripple. The probe now captures
until two consecutive captures agree and reports how many it took (three,
on both images), so "the graph is at rest" is measured rather than
asserted.

#### 3. `captable.sh` — a cache that cannot reproduce a stale tree

Session 5's `captable.sh` cached its BLOCK-32 scratch tree on the block
size alone and rebuilt a whole half-table from a day-old tree. The repair
it shipped was "regenerate every run", marked with a `.generated-$$`
file — and that is weaker than it looks: `$$` is a PID, PIDs are reused,
and two runs in the same second collide on one directory. A stale
reproduction stayed POSSIBLE, just unlikely.

**The tree is now keyed by the state of everything it is generated
from** — block size, `dsp.csv`, `dsp_codegen.py` and every file under
`src/`, hashed into the directory NAME. A tree built from different
inputs is a different directory and cannot be picked up by accident;
`.srckey` is written LAST and re-checked, so a tree left half-generated
by a killed run is regenerated rather than built from. Cost: one sha256
pass over `src/` per run, about 0.3 s.

Proven four ways, in the tree:

| check | result |
|---|---|
| same inputs → same tree | `src32-df51d83892f25f74` reused, and it contains `chip1/bq_pairs.asm`, the D57 fader and the D59 compressor |
| touch `dsp_codegen.py` | key `df51d838…` → `9e0799223091c86b` |
| touch one node `.asm` under `src/` | key → `c510c76284411b01` |
| restore both | key returns to `df51d838…` — the key is a function of the inputs, not of time |
| delete `.srckey` and a generated file (a killed run) | the tree is regenerated, not built from |

**The spot row, on the part**: `MODE=cyc ./captable.sh 32:983:1:32` —
the session-5 headline point — **654,819 cycles/pass** against session 5's
**657,082**, and the scratch tree it was built from is
`/tmp/captable/src32-b4da7d1cfa5fa868`, which contains `chip1/bq_pairs.asm`,
`_fdr_dca_sel_C1_FDR_01` and `_comp_parallel_C1_COMP_01 = 100.0`. That is
the check the bug asks for: the tree carries THIS session's source, so the
number cannot be a reproduction of a previous session's.

**The two numbers are 0.34 % apart and the honest reading of the pair is
unchanged: 32 channels at BLOCK 32 and 983.04 MHz is ON THE LINE.** 654,819
is 99.92 % of the 655,360-cycle budget and 657,082 was 100.26 %; one run
lands just inside and one just outside, which is what "on the line" means.
Nothing in this session changed a per-sample instruction, so the difference
is the instrument's own spread across boots, and it is quoted as measured
rather than claimed as an improvement.

#### 4. The standing bars

| bar | result |
|---|---|
| **contract conformance** | **`VERDICT: PASS`** — 6,088 ECHO / 388 UNMAPPED / 117 CLEARED / 159 meters skipped, **identical to sessions 4 and 5**; 18 declared-unit checks pass and the 16 that fail are the named D41 known mismatches, `ChanCompPar` among the passes at 0/25/50/100 %; both negative controls fired (wrong-unit 4 of 4, no-verify 64 of 64 UNVERIFIED). Table stored at `goldens/conformance-20260830-s6.md` |
| **inert phase** | **PASS on its own boot** — driven window at peak `0x015E7E31`, noise floor ZERO, both positive controls 32 of 32, **12 of 12 sampled classes inert including `0x0053 Chan001RtgDca001`** — D57's fix confirmed by the harness rather than asserted. Stored at `goldens/conformance-20260830-s6-inert.md` |
| **bus golden** | **234 of 256 differ against the postD40 golden — INTENDED (D59)** — then **0 of 256 against the re-baseline**, on a second independently built and booted image |
| **biquad vs model** | **0 of 16 on all three arms** (ref vs blk, ref vs model, blk vs model), negative control fires at 15 of 16 — after the bar itself was repaired, see below |
| **dynamics** | **0 of 32 on all three arms** (COMP, GATE, BQ4); pairing 1.96× / 2.20× / 1.43× |
| **numerics** | **57 of 57 BIT-EXACT**, `NEGCTL PASSED` — 31 of 31 boundary vectors detected, 26 of 26 non-boundary untouched, third-word cost +2.016 c/MAC — after the bar itself was repaired, see below |
| **meter** | **`METER_BIT_EXACT`** with both negative controls firing — wide model `pk_blk>>4 4169139 / ms_blk 16576495` at gain 0.497, narrow model correctly rejected |
| **cell semantics** (new) | **`VERDICT: PASS`** — the table in §1 and §2 |

**TWO OF THE STANDING BARS WERE NOT RUNNABLE, AND NEITHER FAILURE WAS THIS
SESSION'S CODE.** Both were reading the part through an instrument that
cannot answer it — the same defect session 5 took out of
`pairgraph_run.sh`, still sitting in two other bars:

* **`bqst.sh` had been failing on the unpaced reader.** It reported
  `MAGIC 0x00000000 — this is NOT diag firmware` five boots running. The
  part was fine: `dsp4_scope`'s paced read got `MAGIC 0xD5B40001`,
  `CHIP_ID 1` and a moving `FRAME_COUNT` off the same part seconds later.
  **Proven not to be this session's change by building the pre-fix tree
  in a worktree and reproducing the failure identically.** Three things
  were wrong and all three are fixed: `bqst_run.sh` gated on
  `dsp4_diag.py`; `dsp4_bq_verify.py` read the part through `DiagLink`;
  and its `check_chip()` was single-shot, so one dropped read ("CHIP 0")
  killed the run. It now votes on the same `Scope` object — constructing
  a second one takes the RDY GPIO from the first and fails with EBUSY,
  which looks like a dead part and is not.
* **`numverify.sh` scored a link failure as an arithmetic failure.** Its
  peek is voted, but **a ZERO votes just as cleanly as a value**: the
  last four vectors of one arm and six of the next settled on 0, the
  timing block that follows them read a null loop of 0 cycles and 16,071
  cycles/MAC, and the scorer duly reported `NUMERIC BOUNDARY DIFFERS` and
  `NEGCTL FAILED` on arithmetic nothing had touched. A zero now has to be
  corroborated through the SAME peek path — a sentinel word the part is
  known to hold at 1 — before it is believed. Checking `MAGIC` with the
  register reader was tried first and was NOT enough: the register path
  answered perfectly while a peek settled twice on a false 0.

Both fixes are the same lesson session 5 wrote down about `pairgraph_run.sh`
and D58 wrote down about goldens: **an instrument that cannot fail, or that
cannot tell its own silence from a result, is not an instrument.**

#### 5. The PW question filed with D57 and D59

Three, and they are the residue the dispatch asked to have stated with
options rather than decided here.

**Q1 — `RtgDca`'s assignment encoding.** The masters give the family nine
states ("1-8 or off", MxDatS 9), no Table and no unit, and the kernel now
stores the word without acting on it. Before it can act:

* **(a) an integer index, 0 = off, 1..8 = DCA n.** What MxDatS 9 reads
  as, and what every sibling `InstantCtl` cell on this wire (`RtgMute`,
  `RtgMainOn`) already is. **Recommended.**
* (b) a float index (`0.0`, `1.0` … `8.0`), matching the float words the
  gain cells carry — the host would then write `f32(n)`.
* (c) a membership bitmask, so a strip can belong to several DCAs. This
  contradicts the row as written (a mask needs MxDatS 255), so it is
  listed only because it is what a console usually wants.

**Q2 — who applies DCA gain, and how does a chip-1 channel reach a
chip-2 master?** The eight DCA masters (`Dca[1-8]Level/Mute`) are nodes
on CHIP 2. All 32 channel strips are on CHIP 1. A channel fader therefore
cannot read the master it is assigned to, whatever the encoding says.

* (i) give the DCA masters an address on BOTH chips, so the host writes
  both and each chip resolves locally — a contract change, 16 addresses
  added to chip 1's map;
* (ii) the host folds the DCA into the fader level it already sends, and
  `RtgDca` is marked MCU-managed/reserved in the masters — no kernel
  work, and 56 addresses leave the writable surface;
* (iii) the host computes the per-strip DCA gain and writes it to a
  dedicated cell per strip — `_fdr_dca_gain_*` is exactly that hook and
  is sitting at unity.

Until this is ruled the assignment is stored and inert, and the D38 list
says so: **896 → 952 addresses, 762 → 818 master cells**. That growth is
the fix being honest, not a regression.

**Q3 — `CompPar`'s default.** The masters rule the unit and document no
default: `MxDat` is empty for `Chan[1-32]CompPar[1-1]` and
`Main[1-4]CompPar`, where the same column carries 60 of 121 for `EqGain`
and 127 of 255 for `EqFreq`. The kernel now powers on at **100 %** — a
normal serial compressor — because 0 shipped a compressor that did
nothing. If the masters intend another value, put it in `MxDat`: the
generator takes the default from the node's `parallel=` param, so it is
a one-line change in `gen_dsp_csv.py` and a regeneration, not a kernel
edit.

The same question exists for `GateRng`, `CompThr` and every other
dynamics cell with an empty `MxDat` — this session did not go looking,
and only names the one it measured.

#### Bench hand-back

Restored to the NEW shipping baseline and verified on the part, not from a
summary: `chip1.ldr 033d2921`, `chip2.ldr f8883d4c`, md5-matched on the Pi
against the build. Both chips `BOOT_STAGE 7` with `FRAME_COUNT` advancing at
**6000 and 5999 frames/s** (48 kHz / block 8), `DMA0_STAT 0x00006200`,
`SPORT0_ERR_A 0x00000000`, `SPI_ERR_COUNT 0` and `PRODUCT_ID 1` on both;
GPIOs released; `matrix-app active` with **all three MCUs verified on the
FIRST restart** (H1S1, H1S4, H1S3 at 05:47:04–05, read from
`/home/app/logs/log`, not the journal). The CPLD was never touched and no
JTAG operation was run this session, so its bitstream is as it was.

**The chip-2 CHIP_ID symptom recurred, was captured, and was not chased**,
per the standing discipline. Read straight after a boot with NO product
config, the CS2 link answered `CHIP_ID 1` on eight consecutive voted reads
and `SPI_ERR_COUNT 3305`, while reporting `BOOT_STAGE 7`, 6000 frames/s and
`DMA0_STAT 0x00006200`. One boot+config cycle later the same link answered
`CHIP_ID 2` on the FIRST attempt with `SPI_ERR_COUNT 0`. The boot loader
had sent the right image to the right part (183,296 bytes on CS2, 302,080
on CS1), so what this looks like is a link state that survives a boot and
not a mis-flashed chip — recorded, not diagnosed.

## HUB DISPATCH 2026-08-29 21:04Z — session 5: wide-word metering, FILT/EQ pairs in graph, driven inert probe   [status: 🟢 done — **32 CHANNELS ON ONE CHIP IS REACHED AT BLOCK 32 AND 983.04 MHz — 1500 OF 1500 PASSES/s WITH ALL 32 GATES OPEN AND ALL 32 COMPRESSORS ACTIVE, ON TWO SEPARATE BOOTS — AND THE CYCLE INSTRUMENT PUTS THE SAME GRAPH 0.26 % OVER BUDGET, SO IT IS ON THE LINE RATHER THAN COMFORTABLY INSIDE IT. THE RULED OPERATING POINT IS BLOCK 8, WHERE THE CEILING IS 23: block 32 is four times the block latency and the 32-channel row says what the arithmetic can be made to fit, not what the product runs today.** Session 3's best was 12.4 % over. Full table, fused + paired + biquad-paired, honest full-rate rule, every accepted point witnessed: block 8 signal **18 / 23** (was 16 / 22), block 8 silence 19 / 25, block 32 signal **24 / 32** (was 21 / 28), block 32 silence 25 / 32. **D24's 24 channels now fit one chip at 786.432 and BLOCK 32** (24 = 1500/s, 25 = 1458/s), which session 2 recorded as not fitting. Margin at 32 channels, 983.04, cycles per graph pass: 226,462 → 233,714 (wide-word metering) → **214,249 at BLOCK 8 (130.8 %)** and 736,848 → 743,884 → **657,082 at BLOCK 32 (100.26 %, 1,722 cycles over)**. **THE WIDE-WORD METER IS LANDED AND PROVEN: `METER_BIT_EXACT` with BOTH negative controls firing**, and the second one needed its own operating point because **at unity gain the wide word and the rounded store carry the same value** — the standing meter bar could not have told the ruling's arithmetic from the arithmetic it replaced. At gain 0.497 they separate and the part reads the wide model exactly (pk_blk>>4 4169139, ms_blk 16576495) against the narrow model's 4169138 / 16576493. **It costs about 220 cycles per strip per BLOCK — +3.2 % at block 8, +1.0 % at block 32 — and the pipelining fix I built for a multiplier-stall hypothesis did not help; the measurement says so and the ledger corrects the commit message rather than leaving it standing.** **D20 IS STILL BLOCKED AND THE RULING'S PREMISE IS NOT THIS GRAPH**: `BLK_TAP_TRIM` is read by ROUTING's pickoff 0 and GAIN still writes `BLK_CHAIN_B` for FILT, so "kill every tap store whose only consumer is a meter" kills nothing; what remains of D20 is the GAIN→FILT COEFFICIENT fold, a numeric-spec amendment. **THE PAIRED BIQUADS ARE BIT-EXACT WITH A FIRING NEGATIVE CONTROL**: 0 of 64 main-bus words differ against the dynamics-only build, 56 of 64 differ under `DSP4_BQ_NEGCTL` — and the comparison is only worth anything because `bqgraph.sh` writes REAL filter designs first: at bypass the paired and scalar cascades are bit-identical by construction, which is exactly why session 3's bus golden had no biquad coverage. **D55 found and fixed on the way**: FILT's and EQ's transient paths used different pool slots from their steady paths and from each other, so an EQ band written while the filters sat still made the strip's trim, HPF and LPF vanish for the 576 samples of the fade. **THE DRIVEN INERT PROBE WORKS AND SESSION 4'S GAP IS CLOSED: 64 of chip 1's 288 candidates INERT CONFIRMED, noise floor ZERO bus words, both positive controls moving 32 of 32.** Session 4's "the scope injection does not reach the chain" was the PROBE's bug, not the firmware's — it drove the input node's OUTPUT, which the node overwrites every sample. **TWO NEW CONTRACT FINDINGS FROM THE PART: D57**, `Chan001RtgDca001` is documented as a DCA ASSIGNMENT and the kernel treats it as a linear GAIN, so writing the obvious 0 silences the channel with the level word still reading 1.0; and **with `CompPar` at its default the compressor is fully DRY** — the bus read `0x03FFFFEE` at both a −20 dB and a −55 dB threshold while `_comp_gain_*` moved from `0x10000000` to `0x04FE8E90`, so a default-configured strip's compressor threshold is not an audible control at all. **D56**: the gate does not shut on silence at BLOCK 8 and does at BLOCK 32; not chased. **ALL SIX STANDING BARS PASS: conform `VERDICT: PASS`, busgold 0 of 256, bqst 0 of 16 both arms with a firing negative control, dynst 0 of 32 on all three arms, numverify 57/57, mtrverify `METER_BIT_EXACT`. **D58, found by running them: the bus golden went stale at session 4's D39/D40 unit fixes and the bar had been silently unrunnable for a session — bisected on the part to three points, re-baselined, and the last point (`a2f1a00a` on both session 4's HEAD and session 5's) is this session's own W0 proof that none of this work changed the audio.** **A FALSE CAPACITY TABLE WAS MEASURED FIRST AND CAUGHT** — `captable.sh` cached its BLOCK-32 scratch tree on the block size alone and reproduced session 3's numbers exactly from a day-old tree, which is what made it visible; the tree is regenerated every run now. Program memory is the new binding constraint on chip 1: shipping paired+fused links with 4,058 bytes free, the measurement image with 1,478, after three rounds of shrinking the drivers and sharing the meter routines. W0: metering changes the shipping image BY DESIGN — **new baseline chip1.ldr `e9ac266e`, chip2.ldr `73b4f168`**. `conform.sh` VERDICT: PASS, 6,088 ECHO / 388 UNMAPPED / 117 CLEARED / 159 meters skipped, unchanged from session 4, both negative controls firing.]   [model: opus]

model: opus

SESSION 5 — wide-word metering + FILT/EQ pairs into the graph + the
driven-graph inert probe. All three are ruled/queued items; together
they aim at the remaining 12.4% and finish the harness's live leg.

1. WIDE-WORD METERING EVERYWHERE (PW ruling 74d852e): every meter taps
   the MS word / in-register wide value at its tap point; kill every
   round/sat tap store whose only consumer is a meter (BLK_TAP_TRIM
   class); input meter = post-trim via the MS word with GAIN as one
   real MAC feeding stage 1 unrounded (covered by the fold amendment).
   Goldens updated where sources change; negative controls; measured
   per-class deltas. Applies to input/GR/aux/group/main and chip-2
   meters alike.
2. FILT/EQ PAIRS INTO THE GRAPH (hang is fixed, factor measured
   1.43-1.54x at kernel level): pair-order the biquad classes in the
   graph like the dynamics, bit-exact bar + negative control, then
   RE-SWEEP the ceilings (block 8 AND 32, 786 AND 983, signal+silence)
   and restate the margin-at-32 table. This is the lever the capacity
   arithmetic says closes most of the 12.4%.
3. DRIVEN-GRAPH INERT PROBE (session 4's honest gap): the live inert
   confirmation failed its own noise-floor control on an idle graph —
   drive the graph (witnessed stimulus) so the state-window probe
   clears its 3x noise bar, then CONFIRM the 896-entry D38 list from
   the part (or amend it). conform.sh stays the standing bar; its
   results table updates.
4. Note but do not chase: the chip-2 CHIP_ID intermittent boot
   behaviour — if it recurs, capture SRSR/boot evidence and file the
   finding; do not debug it mid-session.
5. Ledger/options paper/review index/scoreboard data updated; the hub
   relays the new table to PW.

Rules: W0 (metering changes the image by design); bench restored
verified; standing traps; ladder discipline; push main.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

---

### Outcome 2026-08-30 (session 5) — wide-word metering, FILT/EQ pairs, the driven inert probe

Commits `7072ceb`, `2d09b9a`, `7876a7c`, `60d49b4`, `30b6888`, `48381d4`,
`47b8812` and the documentation commit carrying this block.

#### W0, stated before any of it was built

| item | expected image delta | actual |
|---|---|---|
| wide-word metering | changes the shipping image BY DESIGN (the ruling touches both the per-sample and the block path) | **new baseline chip1.ldr `e9ac266e`, chip2.ldr `73b4f168`** from `d3cdb0c1`/`a88ac883` |
| paired biquads (`DSP4_BQ_GRAPH`) | block-kernel + paired builds only; whole driver file inside `#if DSP4_BQ_PAIRED_GRAPH` | shipping image untouched by it |
| D55 (FILT/EQ transient slot) | block-kernel builds only | shipping image untouched by it |

`conform.sh` rebuilt the shipping configuration independently and got the
same two hashes, which is the W0 check as well as the setup.

#### 1. WIDE-WORD METERING — landed, proven, and it is not free

Every meter now taps the MS 32-bit word of the accumulator at its tap
point, unrounded and unsaturated. Where the source has a live MAC there
(chip 1's 32 GAINs, the six metered chip-2 FADER_PANs) the meter's three
per-sample instructions moved INTO the source's loop and read `mr1b` in
register; the source hands the finished block accumulators over five words
once per block and the meter node does nothing per sample at all. Chip 2's
OUTPUT_TDM and bus COMPRESSOR have no accumulator at their tap point, so
they publish the same value in the meter's Q8.24 format instead — those 21
meters lose four bits at the bottom (−144 dB instead of −168) and their
one-sample-per-block decimation is unchanged and still recorded.

**On the part: `METER_BIT_EXACT`, C1_MTR_01, BLOCK 8, with BOTH negative
controls firing.** The second control is the interesting one and it needed
its own operating point: **at unity gain the wide word and the rounded
store carry the same value**, so the standing meter bar could not have
told the ruling's arithmetic from the arithmetic it replaced. At gain
0.497 they separate exactly and the part reads the wide model's
`pk_blk>>4 = 4169139` / `ms_blk = 16576495` against the narrow model's
4169138 / 16576493.

**COST, measured at 32 strips: +7,252 cycles/block at BLOCK 8 (+3.2 %) and
+7,036 at BLOCK 32 (+1.0 %).** Nearly the same absolute number at both, so
it is a per-BLOCK constant of about 220 cycles per strip, not a per-sample
cost. **I built a pipelining fix for a multiplier-stall hypothesis and the
measurement does not support it** — 232,991 before, 233,714 after — and
the ledger says so rather than leaving the commit message standing. What
is known: a metered node gives up the `DSP4_STRIP_FUSED` two-at-a-time
loop because the meter owns MRF, and the hand-over adds two calls per
strip per block. Those do not add up to 220 and the remainder is carried
as measured.

**D20 IS STILL BLOCKED AND THE RULING'S PREMISE IS NOT THIS GRAPH.** "Kill
every tap store whose only consumer is a meter (BLK_TAP_TRIM class)" kills
nothing: ROUTING reads `BLK_TAP_TRIM` for pickoff 0 and needs a Q4.28
sample, and GAIN still writes `BLK_CHAIN_B` for FILT. The −17 c/s/strip is
the round/saturate plus those two stores. What remains of D20 is the
GAIN→FILT COEFFICIENT fold plus materialising the post-trim tap only for
sends that actually select pickoff 0 — a numeric-spec amendment, not a
meter question. It is written into the emitted node.

#### 2. FILT/EQ PAIRS IN THE GRAPH — landed, bit-exact, and the lever is real

FILT and EQ run as one SIMD instruction stream per strip pair, in the same
two-pool arrangement the dynamics use. Safe to reorder because both work
in place on their own pool's `BLK_CHAIN_B`; a pair not in steady state
falls back to the two scalar nodes, which work in place too.

**Bit-exact with a firing negative control**: strip 1 driven, strip 2
muted, REAL filter designs in both, `DSP4_BQ_GRAPH=0` vs `=1` → **0 of 64
main-bus words differ**; against `DSP4_BQ_NEGCTL=1` (strip B gets strip
A's coefficients, so the pair computes one channel twice) → **56 of 64
differ, maxdiff 69,476,676**. **The bypass trap is why `bqgraph.sh` writes
real coefficients**: at bypass the paired and scalar cascades are
bit-identical by construction, which is exactly why session 3's bus golden
reproduced with no biquad coefficient coverage at all.

**D55, found on the way and fixed**: FILT's and EQ's TRANSIENT block paths
used different pool slots from their steady paths and from each other —
FILT's crossfade wrote `BLK_CHAIN_A`, EQ's crossfade read it. Consistent
only when both crossfade at once. With EQ crossfading and FILT steady (an
EQ band written while the filters sit still — the common case) EQ cascaded
the block GAIN read instead of the one it wrote, so the strip's trim, HPF
and LPF vanished for the 576 samples of the fade.

**Program memory is now the binding constraint on chip 1.** The first cut
of the drivers was 7,488 bytes and the measurement image would not link at
all; three size cuts took them to 5,670 and the shared meter routines
bought another 3,400. Shipping paired+fused links with **4,058 bytes
free**, the 983 MHz profile-stimulus image with **1,478**.

#### 3. THE TABLE — and 32 channels on one chip is reached at BLOCK 32

| | 786.432 MHz | 983.04 MHz |
|---|---|---|
| BLOCK 8, signal | **18** | **23** |
| BLOCK 8, silence | **19** | **25** |
| BLOCK 32, signal | **24** | **32 — the whole product** |
| BLOCK 32, silence | **25** | **32** |

Against session 3: 16 / 22, 18 / 23, 21 / 28, 22 / 28. Misses, so they
read as misses: block 8 at 983.04, 23 = 5999/s and 24 = 5918/s; at
786.432, 18 = 5999/s and 19 = 5667/s. Block 32 at 786.432, 24 = 1500/s
and 25 = 1458/s. **Block 32 at 983.04 has no rejected point because the
graph runs out before the chip does** — 32 strips scores 1500 of 1500
passes/s with all 32 gates open and all 32 compressors active, on two
separate boots.

**MARGIN AT 32, 983.04 MHz, cycles per graph pass:**

| config | BLOCK 8 (budget 163,840) | BLOCK 32 (budget 655,360) |
|---|---|---|
| session 3: paired + fused | 226,462 — 138.2 % | 736,848 — 112.4 % |
| + wide-word metering | 233,714 — 142.6 % | 743,884 — 113.5 % |
| **+ paired biquads** | **214,249 — 130.8 %** | **657,082 — 100.26 %** |

**THE TWO INSTRUMENTS DISAGREE AT THE HEADLINE POINT AND BOTH ARE
REPORTED.** The pass-rate instrument says 32 strips at BLOCK 32 / 983.04
runs at full rate; the cycle instrument says the same graph is 1,722
cycles over its budget, 0.26 %. That is beneath the pass-rate counter's
resolution — 0.26 % of 1500 blocks/s is under four blocks a second — so
**the honest statement is that 32-on-one-chip at BLOCK 32 and 983.04 MHz
is ON THE LINE: reached by one instrument, 0.26 % over by the other, and
not the comfortable fit a product decision would want.** Session 3's best
was 12.4 % over.

Two more the table says: **D24's 24 channels now fit one chip at 786.432
and BLOCK 32** (24 = 1500/s, 25 = 1458/s), which session 2 recorded as not
fitting; and a two-chip D32 split at 16/chip is under every ceiling in the
table.

**A FALSE TABLE WAS MEASURED FIRST AND CAUGHT.** `captable.sh` cached its
BLOCK-32 scratch source tree on the block size alone, so the first BLOCK-32
half of this table was built from a day-old tree with no `bq_pairs.asm`,
no wide-word metering and no D55 fix — and returned 28 / 21 / 28 / 22 and
737,160 cycles, i.e. session 3's numbers. **Reproducing the previous
session's table exactly is what made it visible.** The tree is now
regenerated every run and the generated header is checked.

#### 4. THE DRIVEN-GRAPH INERT PROBE — session 4's gap, closed

**64 of chip 1's 288 inert candidates INERT CONFIRMED from a driven graph,
noise floor ZERO bus words, both positive controls moving 32 of 32.**

Session 4's window was the strip's control state on an idle graph and it
failed its own control (2–8 of 97 words under a write, 0–22 unwritten).
The window is now the main bus with the graph driven. Four corrections,
each of which first produced a probe that looked like it worked:

* **The injection address.** Session 4 drove `_buf_C1_IN_01` and concluded
  the shipping build's scope injection "does not reach the chain". It
  reaches it — that is the input node's OUTPUT and the node copies
  `_rx_slot_C1_IN_01` over it every sample. **No firmware defect existed.**
* **The strip has to be driven on purpose**, or the capture is all zeros,
  which is what a dead strip also looks like.
* **The graph has to be at rest before each capture.** Two back-to-back
  captures differed in 32 of 32 words until a fixed rest interval was
  added; the noise floor is now zero.
* **The window sits at sample 900, not 0.** With it at the start, writing
  the compressor THRESHOLD moved zero words — the window was blind to the
  whole dynamics section.

**A chain witness was added because "non-zero" is not a witness**: a bus
reading `0xFFFFFFF3` in every word passed a non-zero test while the
fader's output was exactly zero. The probe now tests PEAK against the
injected amplitude and, when the window is silent, walks the strip and
names the node where the signal stops. It did, and it found D57.

**TWO NEW FINDINGS, both from the part:**

* **D57 (MAJOR): `Chan001RtgDca001` is documented as a DCA ASSIGNMENT and
  the kernel treats it as a linear GAIN.** No scale law, `InstantCtl`
  profile, and the dispatch lands it in `_fdr_dca_gain_*`, which the fader
  multiplies into its coefficient. Writing the obvious "no DCA assigned"
  value of 0 sets the strip's fader gain to ZERO and the channel goes
  silent with the level word still reading 1.0. Same class as D39/D40 and
  the one the declared-unit phase cannot catch, because RtgDca has no unit
  declared in `wire-units.csv`. Needs an mx26 answer.
* **With `CompPar` at its default the compressor is fully DRY.** The blend
  is `out = dry + par*(wet − dry)`, so a compressor that is ON, above
  threshold and visibly reducing gain passes the input through unchanged:
  the bus read `0x03FFFFEE` at BOTH a −20 dB and a −55 dB threshold, to
  the word, while `_comp_gain_C1_COMP_01` moved from `0x10000000` to
  `0x04FE8E90`. **A default-configured strip's compressor threshold is not
  an audible control at all.**
* **D56 (MODERATE): the GATE does not shut on silence at BLOCK 8 and does
  at BLOCK 32.** Every BLOCK-8 silence point is witnessed `gate OPEN N /
  SHUT 0` and the scorer marks those rows MIXED/UNPROVEN for that reason;
  every BLOCK-32 silence point on the same firmware reads `gate OPEN 0 /
  SHUT N`. The gate's constants are block-rate derived, which is the class
  D6 was. Not chased — the silence rows are a control, not a product
  configuration — and the BLOCK-8 silence ceilings above are quoted as
  measured with the witness stated rather than as witnessed rows.


#### 5. The standing bars — and one of them had been unrunnable for a session

| bar | result |
|---|---|
| **contract conformance** | `VERDICT: PASS` — 6,088 ECHO / 388 UNMAPPED / 117 CLEARED / 159 meters skipped, identical to session 4, both negative controls firing |
| **bus golden** | **0 of 256 words differ — after re-baselining, see below** |
| **biquad vs model** | 0 of 16 on both arms; the negative control fired at 15 of 16 |
| **dynamics** | 0 of 32 on all three arms (COMP, GATE, BQ4) |
| **numerics** | 57/57 — 31 boundary vectors failed as required, 26 non-boundary exact |
| **meter** | `METER_BIT_EXACT` with both negative controls firing |

**D58: the bus golden went stale at `0f0b3bb` and nobody found out for a
session.** Session 4's D39/D40 unit fixes changed the AUDIO by design — a
default strip's compressor went from fully wet to DRY, and the gate went
from an encoding that could not attenuate to real decibels — and session 4
neither re-ran `busgold.sh` nor re-baselined it. The first session to run
it got 62 of 256 words differing with no way to tell an intended change
from a regression.

**Bisected on the part, three points, one bench session, same instrument:**

| tree | sha256 | vs the stored golden |
|---|---|---|
| `241b7d2` — immediately before D39/D40 | `811af470` | **0 of 256** |
| `7afe947` — session 4's HEAD | `a2f1a00a` | 62 of 256 |
| session 5 HEAD | `a2f1a00a` | 62 of 256 |

**The last row is this session's own W0 proof: the wide-word metering, the
D55 fix and the paired biquads produce a bus capture BYTE-IDENTICAL to the
tree they were built on.** The golden is re-baselined to
`goldens/busgraph-postD40-20260830.json`, the retired one is kept beside it
as evidence, and the bisect is written into `busgold.sh`'s header. The rule
it breaks is worth stating: **a golden that a ruled change invalidates has
to be re-taken in the session that makes the change.**

**And `pairgraph_run.sh` was gating on the instrument that cannot read the
link.** `conform_run.sh` recorded on 2026-08-29 that `dsp4_diag.py` can
fail to answer after a config while `dsp4_scope`'s paced, voted read
returns `BOOT_STAGE 7` off the same part, first try — and `pairgraph_run.sh`
kept the diag gate. It spent this session discarding good boots for it:
`busgold` burned all five of its attempts twice, and every `captable` point
that reported `BOOT_STAGE reads  — link down` was that. With the paced
probe ported across, the very next `busgold` run booted, configured and
captured on its FIRST attempt.

#### 6. Item 4 — the chip-2 boot intermittent, noted and not chased

**The specific symptom the dispatch named did not recur in a diagnosable
form.** Chip 2 never reported `CHIP_ID 1`, and the boot ladders'
`CHIP_ID == 2` gate passed within three attempts every time. What DID
recur, repeatedly, is a different pair of things and both are worth
recording because they cost real bench time and one of them was mine:

* **The scope link needs a resync the diag link does not.**
  `dsp4_diag.py --chip 1` answers cleanly while `Scope(1).check_chip()`
  reads `CHIP 0` on the same part seconds later; a diag read walks the
  parameter link back into phase. `pairgraph_run.sh` now takes one in
  front of every scope-side tool and retries, which turned five wasted
  boot attempts into none.
* **Killed sweeps leak processes onto the Pi that hold the CS and RDY
  GPIO lines.** After I killed a `captable.sh` run locally, `gainfix.py`
  and `dsp4_dyn_witness.py` kept running on the bench and every
  subsequent boot failed with `EBUSY` or `SPI_RDY never asserted`. One
  run in between returned an **all-zero meter state**, which is what a
  silent strip, a dead link and a broken meter all look like — the same
  image read `METER_BIT_EXACT` once the leaked processes were killed.
  **Kill the remote process, not just the local one.**

#### What was NOT done, and why

* **The full 896-address inert confirmation.** 64 of chip 1's 288
  candidates are confirmed; at about nine seconds each the whole list is
  roughly two hours of bench. `INERTN=<n>` raises it and the list says so.
* **Chip 2's OUTPUT_TDM and bus-COMPRESSOR meters are still decimated to
  one sample per block.** They read the wide form now, but the
  decimation is a property of unconverted per-sample sources and fixing
  it means block-converting them (D16/D50 territory).
* **D20's remainder — the GAIN→FILT coefficient fold — is not taken.** It
  is a numeric-spec amendment and PW's ruling addressed the meter half,
  which turns out not to be the blocker.
* **The 220 cycles per strip per block that the wide-word meter costs are
  not fully attributed.** Two shared calls and the lost strip fusion do
  not add up to it, and the pipelining fix built for the stall hypothesis
  did not help. Carried as measured.
* **D56 (the gate not shutting on silence at BLOCK 8) is filed, not
  chased**, per the dispatch's own discipline on incidental behaviour.

#### Bench hand-back

Restored to the new shipping baseline and verified on the part, not from a
summary: `chip1.ldr e9ac266e`, `chip2.ldr 73b4f168` md5-matched on the Pi
against the build; both chips `BOOT_STAGE 7` with `FRAME_COUNT` advancing
at **6007 and 6008 frames/s** (48 kHz / block 8), `DMA0_STAT 0x00006200`,
`SPORT0_ERR_A 0x00000000` and `SPI_ERR_COUNT 0` on both; GPIOs released;
`matrix-app active` with **all three MCUs verified on the FIRST restart**
(H1S1, H1S4, H1S3 at 03:42:51 and boot-verified at 03:42:57, read from
`/home/app/logs/log`, not the journal). The CPLD was never touched and no
JTAG operation was run this session, so its bitstream is as it was.

The frame counter had to be read UNVOTED to get a rate: `dsp4_scope`'s
voting reader requires two agreeing reads and a live frame counter never
gives them, so it throws `never settled` — which is the counter advancing,
not a fault. Worth knowing before someone reads that exception as a dead
part.

## HUB DISPATCH 2026-08-29 19:45Z — session 4: contract conformance harness — protocol goldens, standing bar   [status: 🟢 done — **THE CONTRACT IS NOW MEASURED AGAINST THE MASTERS AND THE SURFACE AGREES WITH THE TREE ADDRESS FOR ADDRESS; D39 AND D40 ARE FIXED AND PROVEN ON THE PART; THE D38 LIST IS 896, NOT ~600; THE LIVE INERT CONFIRMATION FAILED ITS OWN CONTROL AND IS NOT CLAIMED.** Every other bar in this tree measures the kernel against ITSELF, so a cell addressed to the wrong variable or served in the wrong unit reproduces its own goldens forever; `conform.sh` asks the other question and is now a standing per-session bar in `smoke-checklist.md`. **PRESENCE: 6,752 addresses on both chips — 6,088 ECHO, 388 UNMAPPED, 117 CLEARED, 159 meters skipped — and NOT ONE answered differently from what the dispatch table in the tree predicts** (chip 1 4,800 in 293.9 s, chip 2 1,952 in 120.4 s, zero indeterminate). **The mapped/unmapped verdict comes from the PART, not from the read-back**: an unmapped address and a mapped one the kernel clears every block both read back zero — the coefficient-set swap triggers are exactly the second case — so `SPI_ERR_COUNT` is what settles it, and the error delta matched the write count on all 388 unmapped addresses and was zero on all mapped ones. It also finds D37's `comp_gr` independently, from the part, as 32 literal-0 dispatch slots. **D39: GateRng 20/40/60 dB went from `0xFFFFFFFF` — the deepest gate the protocol can ask for producing NO attenuation at all — to `0x0199999A`, `0x0028F5C3`, `0x00041894`, exact, exact and 1 LSB.** **D40: CompPar 25 % and 50 % went from `0x7FFFFFFF` (fully wet, the control dead) to `0x20000000` and `0x40000000` exactly.** Both measured before and after on the same script; the wrong-unit negative control fails all four GateRng values, so the check tests the unit and not the code. W0: the harness left the image byte-identical (the pre-fix build reproduced `ea4c9f5f`/`f0a47584`); the unit fixes change it BY DESIGN — **new baseline chip1.ldr `d3cdb0c1`, chip2.ldr `a88ac883`**, +2,496 bytes on chip 1, 78 node files and no others. **D38 IS ENUMERATED AND THE ESTIMATE WAS LOW: 896 addresses naming 762 master cells**, generated by kernel class into `docs/contract/inert-cells-d38.md`, conservative by construction — 70 offset-reachable addresses are counted separately rather than claimed dead, which is what keeps `_mtr_rms` off the list. **THE LIVE INERT CONFIRMATION IS THE ONE THING NOT DELIVERED**: two probes were built and both were rejected by their own positive control — the bus capture because the shipping per-sample build's scope injection does not reach the chain (a −6 dBFS step into `_buf_C1_IN_01` never lands), and the state-window probe because the control moved 2 words of 97 while the unwritten interval moved 0–13. No inert verdict is reported from the part, the bar now requires the control to clear its noise floor 3×, and the fix is a driven graph. **FOUR NEW FINDINGS, all generated rather than asserted: D51** the EQ/GEQ/FILT wire plane carries biquad COEFFICIENTS, not the documented parameters — 1,036 master cells collapse onto 322 addresses and `EqFreq`/`EqGain`/`EqQ`/`EqShelf` all resolve to word 0 of one coefficient set, so the host is expected to compute the biquad and no line of the masters says so; **D52** the masters name three main output chains and the DSP has four, with no stated correspondence, leaving 134 cells unresolvable by name; **D53** 1,331 documented cells reach no DSP address after subtracting the MCU-only prefixes; **D54** 1,244 mapped addresses carry a documented non-Instant ramp profile but have no ramp state, so the profile is discarded — 467 of them with no crossfade alternative, `Chan001GateThr001` among them. 199 UNDECLARED families are written up as PROPOSALS for mx26's `wire-units.csv` and adopted nowhere here. Both negative controls fired and the scorer fails a run in which either does not. Bench restored to the new baseline, md5-verified on the part, both chips at BOOT_STAGE 7 with frames advancing and DMA/SPORT clean, matrix-app active with all three MCUs verified on the second restart; CPLD never touched. Commits 241b7d2, 0f0b3bb, 540f437 and the documentation commit carrying this block.]   [model: opus]

model: opus

SESSION 4 — THE CONTRACT CONFORMANCE HARNESS (PW ruling 97a4d5d; PW
order: after session 3, before the metering/wiring session). Protocol
goldens: prove the live SPI contract does what the masters document,
and make the proof a STANDING per-session bar.

Contract source: docs/contract/ (distribution copies of the mx26 wire
tables — mx26 is SOT). unit=UNDECLARED families get presence/echo
testing only; declared families get semantic tests.

1. BUILD the harness (tools/pi/, alongside the existing bench tools):
   for EVERY cell in the wire table — write over live SPI at boundary
   values (min, max, mid, and the scale-law knees where Table strings
   define them), then verify:
   a. ECHO/presence: the value is accepted and readable back where the
      protocol provides readback.
   b. EFFECT: for declared families, the kernel-visible consequence
      matches the documented unit/range/law (coefficient lands where it
      should, gain moves by the documented dB, mute mutes, ramp reaches
      target in the documented time class) — use the existing calibrated
      instruments (diag peeks, busgraph capture, meter words) as probes.
   c. INERT detection: a write that changes NOTHING kernel-visible goes
      on the authoritative D38 inert list with its cell name.
2. NEGATIVE CONTROLS: prove the harness can fail — a deliberately wrong
   expected-unit entry must FAIL its cell; a write to a known-good cell
   with verification disabled must be DETECTED as unverified.
3. KNOWN MISMATCHES (D39 GateRng dB-vs-linear, D40 CompPar %-vs-0..1):
   fix the KERNEL side to match the documented unit (masters win — cell
   semantics are the contract), each with before/after harness runs.
4. RUN the full sweep on both chips' graphs as configured today; commit
   the results table (pass/fail/inert per cell) as the harness's first
   baseline; wire the harness into the standing acceptance ladder (a
   session's requal now includes a harness run; document the invocation
   next to the smoke scripts).
5. OUTPUTS for the hub: the D38 authoritative inert list (counted,
   named); any UNDECLARED family whose observed behavior lets a unit be
   inferred — reported as PROPOSALS for mx26's wire-units.csv, never
   silently adopted.

Rules: W0 (kernel fixes in item 3 change the image by design — ledger);
bench restored verified; standing traps; ladder discipline; push main.
The hub relays the results table and the inert count to PW on landing.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

**PW RULING 2026-08-29 (~17:05): METER FROM THE WIDE WORD — ALL DSP
METERING.** Every meter taps the SIGNAL'S WIDE FORM at its tap point —
the accumulator's most-significant 32-bit word (Q8.24 view: sign, full
range incl. over-range, 24 fractional bits ≈ −144 dB floor) or the
in-register value — NEVER a dedicated rounded/saturated 32-bit store
made for the meter's benefit. Truncation is fine for metering; the
absence of saturation is a FEATURE (meters see genuine over-range).
Kill every tap store whose only consumer is a meter (BLK_TAP_TRIM
class). This CLOSES D20: the input meter is post-trim, measured, via
the MS word — GAIN stays one real MAC feeding stage 1 unrounded (the
intermediate-round deletion is covered by the GAIN-fold numeric
amendment), total ≈ 3–4 c/s/ch vs 17. Applies to input, GR, aux/group/
main and chip-2 meters alike; goldens updated where a meter's source
changes (same bit-exact bar, negative controls). Implementation is its
own session after the conformance harness (order: session 3 PM+table →
4 harness → 5 metering); do not bolt it onto a running session.

## HUB DISPATCH 2026-08-29 16:31Z — session 3: program-memory recovery, pair hang, min-Q, the capacity table   [status: 🟢 done — **THE MEMORY WALL IS DOWN, FUSED+PAIRED LINKS AND IS MEASURED, THE PAIR HANG IS ROOT-CAUSED, AND THE CAPACITY TABLE IS BUILT — BUT 32 CHANNELS ON ONE CHIP IS NOT REACHED IN ANY MEASURED CONFIGURATION.** **The linker's own shortfall was 0x131a = 4,890 bytes and three measured reclamations returned 16,824: the DLY per-sample body (13,568 — dead under block kernels because that class's block kernel, unlike GATE/COMP/EQ/FILT/TUBE, has no fallback into it and the node file carries no `_process_sample` label at all), `dyn_selftest` (2,240 — gated on DSP4_SIMD_DYN, so the instrument rode in every paired build including a shipping one), and the float-era `lib/dynamics.asm` + `lib/delay.asm` (888 — no caller anywhere since the D5 pivot, placed because the linker places every command-line object).** Chip 1 code free went 15,062 → 29,518 scalar-unfused, 9,882 → 24,338 scalar-fused, 418 → 17,134 paired-unfused, and **−4,890 (would not link) → 11,954 paired+fused**. `tools/dsp/pm_audit.py` is the new instrument that made it a ten-minute question. **THE BIQUAD-PAIR HANG IS A CLOBBERED REGISTER, not a hazard, a loop tail or an interrupt mask: `_bq_fx_cascade_simd` writes r0-r15, and `_bq_pair_blk` read r10/r13/r14 back afterwards for its scatter — r13 returns as 0x10000000 and r14 as 0x08000000, so it wrote a block to address 0x10000000 and entered a hardware loop with lcntr = 0x10000000. 268 million iterations, scribbling, on every call**, which is exactly why the part never looked crashed while BOOT_STAGE sat at 5 and the diag ISR kept answering. Five words of DM fix it; **negative control DSP4_BQP_NOSAVE=1 reproduces the session-2 symptom verbatim**. It also explains both prior eliminations (SKIP_SIMDCALL boots because the registers survive; one stage hung as four did because the corrupt lcntr does not depend on the stage count). **THE PAIRING FACTOR IS 1.43-1.54×, NOT THE 2.39× ON RECORD** — that was measured against the OLD cascade and strip fusion has already taken 32 % out of that baseline; COMP 2.04×, GATE 2.27×, all three arms ndiff 0 of 32. **THE MIN-Q RULING LANDED and it is not free**: n1 halved into Q5.27, product accumulated twice, all four cascade forms, proven ON THE PART by a new asm-vs-MODEL instrument the biquad never had (`dsp4_bq_verify.py`, 0/16 both forms, negative control 15/16). Over the full 869,627-set design space it clears **1,313 of the 1,323 sets that saturated Q4.28** — and **TEN STILL SATURATE (D48, new): a LOW SHELF at 18.9-20 kHz, +14..15 dB, shelf-Q 2.8-3.5, where |n1| reaches 17.835. No encoding at this width reaches them; closing them is a RANGE decision for PW.** The cost is measured: worst LF magnitude error **0.046151 → 0.060560 dB**, unchanged at 0.003479 for f0 ≥ 50 Hz, harness bar moved 0.05 → 0.07 dB, still 6.6× better than shipping FP32. **A six-word block splitting n1 into two Q4.28 halves would give the same range at the same +1 MAC with NO resolution loss and is costed in numeric-spec.md for PW; it is not taken because the ruling names the halved form.** Side effect: D2's reachable |efb| bound IMPROVED to 2^61.648, 1.352 bits, from 2^62.606 and 0.394. **THE TABLE. Ceilings, fused+paired, honest full-rate rule, every point witnessed: block 8 — 16 at 786.432 and 22 at 983.04 signal, 18 and 23 silence; block 32 — 21 and 28 signal, 22 and 28 silence.** Against 12 scalar-unfused, 15 paired-unfused and 16 scalar-fused on the same point. **MARGIN AT 32 IS NEGATIVE IN EVERY ROW**: block 8 at 983.04 goes 213.4 % → 185.2 % → 167.5 % → **138.2 %** of budget across the four configs, block 32 goes 195.4 % → 167.2 % → 140.8 % → **112.4 %**. **The best measured configuration is 12.4 % OVER the budget, not under it** — the gap has gone from about a factor of two to 12.4 %, which is progress and is not a fit. **Two chips is the part that moved: 16/chip is what a D32 split needs and block 8 at 983.04 now reaches 22, against exactly 16 last session.** The two instruments cross-check and share no arithmetic (cycles ratio 1.340 against ceiling ratio 22/16 = 1.375), the per-class profile sums to within 0.9 % of the whole-pair measurement and within 0.1 % of the independent 32-strip count, and **the silence control has almost stopped mattering — one channel at block 8, none at block 32, against the ~29 % it used to flatter by.** Strip total fused+paired **6,580 cycles/block/channel, −35.5 % on the 10,198 it replaces.** **NEXT LEVER, arithmetic not measurement: FILT+EQ is 29.6 % of the strip and the pair kernel is 1.43-1.54×, so wiring a FILT/EQ pair driver takes block 8 at 32 channels to ~125-127 % of budget. It does not reach 32 either.** **D24 re-evaluated: the memory objection is gone (1,124 bytes against 11,942 free) but it buys 0.76 % of a paired strip — below this instrument's ±2 % band and 0.24 of a channel — so it could not move a single row; NOT landed, and the decision is now PW's on value rather than memory.** W0: the PM reclamation left the shipping image byte-identical; the min-Q ruling changes it BY DESIGN — **new baseline chip1.ldr ea4c9f5f, chip2.ldr f0a47584** from 2072e0de/a248d25d. Bars: golden_harness 16/16, bqst 0/16 both arms with the model check and a firing negative control, dynst 0/32 on all three arms, busgold 0 of 256 words, numverify 57/57. **The busgold golden reproducing is a COVERAGE finding, not reassurance: it reproduced because the harness leaves the biquads bypassed, and bypass is bit-identical under the halved encoding by construction, so that golden has no biquad-coefficient coverage at all.** Bench restored to the new baseline, md5-verified on the part, both chips booting with frames arriving and DMA/SPORT clean, matrix-app active with all three MCUs verified on the FIRST restart. CPLD never touched. Commits 81b5ee4, 6938840, 2fadf39, 7475398, e28c800, f001320, 4918172.]   [model: opus]

model: opus

SESSION 3 — PROGRAM-MEMORY RECOVERY, then the capacity table (PW order:
this first, conformance harness immediately after as session 4).

THE WALL (session 2): chip 1 sec_swco is 131,070/131,072; fused+paired
DOES NOT LINK (paired-unfused leaves 418 B; paired + profile stimulus
fails even alone). The capacity table is blocked on BYTES.

1. RECLAIM PM on chip 1: audit the link map — what fills sec_swco per
   build config. Prime suspects from the review: legacy per-sample node
   bodies compiled alongside block kernels, dead scan paths (D14 class),
   self-test/instrument code not behind flags, duplicated library
   routines. Gate legacy code OUT of block-kernel builds (#if), delete
   the provably dead. W0 discipline: the default per-sample shipping
   image must remain byte-identical (its code is the legacy path — gate,
   do not break); state the reclaimed bytes per change, and keep a
   before/after link-map summary in the block.
2. LINK fused+paired at block 8. If it still does not fit after honest
   reclamation, say by how much and what the next options cost.
3. THE BIQUAD-PAIR HANG (localized to _bq_pair_blk, DO-tail hazard
   eliminated): root-cause it — the paired table's FILT/EQ column
   depends on it. Timebox; if it resists, the table ships with
   dynamics-only pairs and the hang gets its own finding update.
4. LAND the min-Q halved-n1 encoding (PW ruling 060e605, queued from
   session 2) — uniform +1 MAC/stage, bit-exact by construction against
   regenerated goldens; corner vectors still ride D27 later.
5. Re-evaluate D24 (dynamics parameter shadows) under the recovered PM
   budget — land it if it now fits comfortably (it was deferred at
   1,124 B cost when only 1,312 B remained).
6. THE CAPACITY TABLE (the deliverable): fused + paired together,
   per-class re-profile, ceilings at BLOCK=8 AND 32, 786.432 AND
   983.04, signal AND silence, honest full-rate rule, witnessed
   stimulus; the MARGIN-AT-32 table per the standing ruling. Measured
   rows only. Update ledger + options paper + review index.

Rules: W0 throughout; bench restored verified; standing traps; ladder
discipline; push main. The hub relays the table to PW on landing.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

**PW RULING 2026-08-29 (~13:40): FULL PROTOCOL TESTING PULLED FORWARD.**
Contract conformance is interleaved with the capacity work, not queued
behind it. Session 3 (after the running efficiency session) = the
CONTRACT CONFORMANCE HARNESS: write every documented cell over the live
SPI plane with boundary values, verify the kernel's behavior matches the
master's documented unit/range/effect — protocol goldens that fail
loudly on drift. Rides with it: the D39/D40 unit fixes, D37 gr-meter
taps (mx26 supplies the ids), and application of the per-cell wire table
(D41 — mx26 builds it, hub-side, in parallel with the bench sessions).
D38's ~600 inert slots: the harness produces the authoritative list;
which get WIRED vs documented-deferred is then a PW prioritization.
Capacity floor remainders move to session 4 unless session 2 leaves
little behind. **PW addendum (~13:45): once built, the conformance
harness joins the STANDING per-session acceptance bars** — it runs in
every session's requal like the smokes and goldens do, so the many test
passes each re-prove the contract for free.

**PW RULING 2026-08-29 (~13:10): MINIMUM EQ Q = 0.10** (matching the
wide-gentle extreme of the console field, not the mainstream 0.3 floor).
The +15 dB / Q <= 0.12 corner (session-1 finding: n1 = 8.318 exceeds
Q4.28) is IN SPEC and is handled by the halved-n1 encoding — store
n1/2, accumulate its product twice into the MRF (bit-exact by
construction, uniform +1 MAC per biquad stage, ~+6 c/s scalar strip /
+3 paired per channel). UNIFORM always-on, not conditional: the kernel's
instruction stream must not vary with loaded settings or measured
ceilings become setting-dependent. Conversion rejects Q < 0.10. Record
in numeric-spec.md; golden vectors at the corner ride the D27 coverage
work; floors and the capacity arithmetic absorb the +1.

## HUB DISPATCH 2026-08-29 10:45Z — fix session 2: efficiency batch D20-D25 + biquad pair + measured capacity table   [status: 🔴 blocked — **THE EFFICIENCY WORK LANDED AND IS MEASURED; THE CAPACITY TABLE THE SESSION WAS SENT TO PRODUCE CANNOT BE BUILT, AND THE REASON IS PROGRAM MEMORY.** **D22 is the whole story on cycles: RTG 1,861 → 416 cycles/block, −1,445, twenty times the instrument's noise, and the strip goes 11,726 → 10,198, −13.0 %** (block 8, signal, unfused, same script and same switches as the record it replaces; GAIN, FILT, EQ+GATE and COMP all reproduce to within 2 %, which is what makes RTG attributable). The gate is an EPOCH COUNTER, not a dirty flag, because a flag has to be cleared by its consumer and two nodes watching one strip then race; the strip index is addr/144 computed as (addr·7282)>>20, EXACT over the whole 0..4607 range, no divide and no MR register because the handler is an ISR and must not disturb the multiplier the audio path is using. **D25: the delay line went from 17 instructions per sample to 5 (circular DAG addressing) and the class moved 598 → 531 — which ANSWERS the review's open L2 question: 96 instructions per block were deleted and 67 came back, so of DLY's 63 cycles/sample only 8.4 was addressing and ~55 is L2 latency that no address arithmetic will touch.** The 37 INTERCHIP_SEND bodies are gone (the gather points at the bus buffers), and **D14** with them — confirmed first that nothing writes the RX slot vars under block kernels, so the legacy input peaks were ALREADY frozen and deleting the scan changes no host-visible value. **D21: the fused biquad inner loop is packed** — branch-free conditional-move saturation (the branch was taken on essentially every sample), the rounding half moved out of MRF (two MACs became an add and a carry-add, and the undo disappeared), and the x-history shifted before the extraction to put two moves between the last MAC and the first MR read. **bq_selftest: ndiff 0 of 64, maxdiff 0, on REAL data** (ref 520298, 1974192, …), not the untouched zeros an earlier run of that test compared. **THE BIQUAD-PAIR HANG IS LOCALISED AND ONE SUSPECT IS ELIMINATED:** the self-test would not complete at all until DSP4_SKIP_PAIR=1 — BOOT_STAGE 5 and done=0 while the diag ISR kept answering the link — and with the identical image and only that call removed, BOOT_STAGE 7 and done=1. So it is inside `_bq_pair_blk`, and **it is NOT the DO-loop-tail hazard**: the loop two lines above has exactly the same shape, `call _bq_fx_cascade_blk` second-from-last inside a hardware loop, and runs perfectly. **BIT-EXACTNESS, and the instrument is new: goldens/busgraph-prebatch-20260829.json** — 256 words of the main bus captured out of a running graph on 87fded2, sha256 811af470…. The whole batch reproduces it, **0 of 256 words differ**, and it can fail because the harness writes ~20 parameters per strip over SPI with opposite dynamics on the two strips before capturing. Two negative-control switches exist (DSP4_CTL_ALWAYS removes the gate, DSP4_CTL_NEGCTL makes it deaf to writes). **MEASURED CEILING: 16 channels/chip at 983.04, scalar+fused, block 8, signal present, honest 6000/s rule, every strip witnessed gate-OPEN and comp-ACTIVE** (16 = 5999/s, 17 = 5779/s). Against 12 for scalar-unfused on 08-28. The slope model calibrates on that: it predicts 12 before and 14 for scalar-unfused after, and 16 fused. **AND HERE IS THE BLOCK. Dispatch item 8 — build fused + paired TOGETHER at block 8 for the first time — DOES NOT LINK. Chip 1 is out of PROGRAM MEMORY.** `sec_swco` is FULL (131,070 of 131,072) in every block-kernel build and everything spills to block 2's overflow; free bytes there are 15,062 scalar-unfused, 9,882 scalar-fused, 418 paired-unfused, and **paired+fused is over**. **It is not the gate** — the same build with DSP4_CTL_ALWAYS=1 still overflows. Nor is the paired SIGNAL-PRESENT ceiling measurable any more: paired + the profile stimulus fails to link WITH AND WITHOUT the gate, so it is pre-existing growth, not a regression from this session. That is why the record has never carried a fused+paired number, and the reason is now measured instead of assumed. **The lever is structural and this session demonstrated it in miniature**: the gate began as nine inline instructions per node — ~41 bytes each because a directly-addressed DM access is a LONG VISA instruction, 1,320 across 32 nodes, which BY ITSELF stopped the paired build linking — and became a three-instruction call into one shared routine over indexed per-strip arrays, giving 896 bytes back for ~2.5 cycles/sample/strip. The same move applied to ROUTING's whole prep (~600 lines × 32) and to the dynamics bodies is what buys the room fused+paired needs. Recorded in dsp4-cycle-budget.md. **NOT LANDED, each with the number that says why: D20** — the GAIN=1MAC fold deletes GAIN's BLK_CHAIN_B store and NOTHING ELSE (~1 c/s): the round/saturate and the tap store exist for the METER and the router's pickoff-0, both of which need a Q4.28 post-trim sample, so −17 c/s is gated on a ruling about what the input meter measures, not on implementation. **D23 — WITHDRAWN as written**: the bus accumulator is BLOCK triples, one per SAMPLE, not one per bus, so the "load once, 8 MACs, store once per block" form the finding prescribes does not exist; the reload is per-sample because the accumulator is. **D24 — implemented, then REVERTED on the measurement**: gates on GAIN/FDR/GATE cost ~1,124 bytes of the 1,312 left in the paired build and buy ~9 cycles/sample of 1,466. EQ tap fold and TUBE bypass: ~2 c/s each against a slot-protocol change, not taken. **A NEW PW RULING LANDED MID-SESSION (060e605, minimum EQ Q = 0.10 via halved-n1 double-accumulate) AND IS DELIBERATELY NOT ABSORBED HERE** — it adds +1 MAC per biquad stage, uniform, so every number above predates it and the ruling's own +6 c/s scalar strip has to be added. It should be the first thing the next kernel session lands, on top of the packed loop. **W0: the shipping per-sample image is BYTE-IDENTICAL through all of it — chip1.ldr 2072e0de, chip2.ldr a248d25d, unchanged from fix session 1.** Every line is behind DSP4_BLOCK_KERNELS, and ctl_epoch.asm additionally behind CHIP_ID == 1. Bench restored: those exact images rebuilt from a clean tree (md5s checked), reflashed, matrix-app started clean on the FIRST restart at 14:21:43 — the three-MCU verification line itself was not read back, so it is recorded as "app up on the first restart", not as a full MCU witness. CPLD never touched. Commits 7c0bae9, f179002.]   [model: opus]

model: opus

FIX SESSION 2 — the efficiency batch, from review-dsp-20260828.md
(chained per PW's overnight authorization; session 1 landed all ten
correctness items). The campaign ruling in force: 32 channels is the
MINIMUM; the finish line is floors; report margin-at-32. Bench is free.

LAND, each bit-exact against its golden (regenerated per the amended
reference where a ruling changed the arithmetic), each with its cycle
delta MEASURED per class:
1. D20 — GAIN=1MAC fold (PW numeric amendment 08-28 ~17:35): scale
   [b0,n1,n2] at control rate, delete the round/sat + tap stores;
   goldens regenerate from updated fixed_ref; expect GAIN ~22.9 → ~2.
2. D21 — multifunction-pack `_bq_fx_cascade_N` (and the block form):
   fuse loads into MAC lines, conditional-move saturation, target
   ≤22–24 instr/stage scalar; per-stage before/after measured.
3. D22 — RTG: move the control-rate section (send ramps, pickoff
   resolution, crosspoint-list rebuild) to control rate behind a dirty
   flag; the largest single gap in the strip (232.6 → floor 8–15).
4. D23 — `_acc64_mac_blk`: keep the 80-bit accumulator in MRF across
   the block (reclaims session 1's +2/MAC and the reload waste).
5. D24 — one-time-converted parameter shadows for the dynamics
   (control-rate conversion, dirty flag) — also removes most of the
   pair drivers' sample-0 overhead.
6. D25 — the batched small wastes (SEND copies, EQ tap fold, TUBE
   bypass ping-pong, DLY pointer-resident addressing, dead scan D14 if
   not already gone).
7. THE BIQUAD-PAIR HANG — root-cause it (the two recorded loop hazards
   are prime suspects), wire FILT/EQ pairs, measure the TRUE pair
   factor against the fused cascade. If it resists a reasonable
   timebox, land everything else with measurements and write findings.

THEN MEASURE — the session's deliverable is the honest capacity table:
8. Build fused + paired TOGETHER at block 8 for the first time; full
   per-class re-profile (update dsp4-function-costs.csv, block-tagged);
   ceilings at BLOCK=8 AND BLOCK=32, 786.432 AND 983.04, signal AND
   silence controls, honest full-rate rule, witnessed stimulus.
9. Report the margin-at-32 table (cycles + % of budget remaining at 32
   channels, per config) exactly per the PW ruling at the top of this
   file's parent block. No projections — measured rows only.
10. Update the ledger + options paper; tasks.md + review index (D#
    statuses with commits).

NOT in scope: D2's efb clamp (parked for PW — session 1's bound
stands); chip 2 (D16, its own workstream); contract items D37–D43.

Rules: W0 throughout (state expected image deltas up front — these
change the wire image BY DESIGN); bench restored verified at the end;
standing traps; ladder discipline; push main.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

## HUB DISPATCH 2026-08-29 08:46Z — fix session 1: wraps and shipping correctness (D1-D6, hygiene)   [status: 🟢 done — **ALL TEN ITEMS LANDED; THE SEVERE IS FIXED, MEASURED AND PROVEN ON THE PART.** **D1**: the bus accumulators are 80-bit triples [lo, hi, ex] — MR2F was discarded on store and rebuilt from the sign of `hi` on load, capping them at 64-bit Q8.56 = ±128.0 with nothing saturating them, and the readout's saturation check then ran on a value that had ALREADY wrapped, so a wrapped bus sum came out as a clean, full-scale, WRONG-SIGN sample. **The fix shape is mr2f-store, not a saturating accumulate, and the trade is written down: saturating at ±128 clips a PARTIAL sum, so a bus whose contributions cancel returns the wrong answer order-dependently, while 80 bits sums exactly and leaves the single ruled round at readout.** Cost MEASURED, not argued: **+2.003 cycles/MAC per-sample and +2.005 in the block kernel** (200k iterations against TCOUNT+tick at 491.52 MHz) — +2 for both even though the block form costs three more instructions, because the extra load and store pipeline against each other, which the instruction count did NOT predict. Against ~5–6 for a saturating accumulate: cheaper AND stronger. D23 will take the +2 back. Normative bound now in numeric-spec: |Σ| ≤ 4096 = 2^12 against 2^23, eleven bits, wrap unreachable. **D3**: the crossfade blend forms `new − old` as two MRF MACs — same instruction count, identical arithmetic wherever the 32-bit subtract did not wrap — and the five duplicated copies now come from ONE generator expression, which is also what emits the self-test's probe. **THE PROOF IS A NEW INSTRUMENT AND IT CUTS BOTH WAYS: numverify.sh + the generated lib/num_selftest.asm + tools/pi/dsp4_num_verify.py run the REAL `_acc64_mac`/`_acc64_rns28` and the generated blend over 15 mix and 42 blend vectors that straddle both boundaries — 57 of 57 BIT-EXACT against fixed_ref, per-sample AND block-kernel builds; DSP4_NUM_NEGCTL=1 puts the pre-fix arithmetic back in the same image and 31 of 31 boundary vectors are DETECTED with 26 of 26 non-boundary vectors untouched.** **THE PART CORRECTED THE MODEL ONCE, and it is worth the record: the alpha quantisation is FLOAT32, not float64** — modelling it in float64 disagreed by 15 LSB at alpha = 1−1/576. Also measured: `fix(2^31)` returns 0xFFFFFFFF on this core, not a saturated 0x7FFFFFFF; alpha = 1.0 is unreachable because the kernel's own ramp guard cannot present it, and numeric-spec now says a change to that ramp must preserve alpha < 1.0. **D2**: bounded, not fixed, with the arithmetic in tools/dsp/bound_efb.py. The pessimistic bound does NOT close inside the product's own design space (worst S = 38.56 → |acc| ≤ 2^64.27 > 2^63), so a conversion-time clamp on Σ|coeff| is CLOSED as an option — it would reject settings the DEFS allow. The REACHABLE bound, from full-scale adversarial drive on the worst sets, is **|efb| = 2^62.606 — 0.394 bits of margin, and it is recorded as thin**; growth needs sustained output saturation, and away from saturation |efb| ≤ 2^27, thirty-six bits clear. The option not taken (saturate the store at ±(2^63−1), bit-identical in the reachable domain, ~3 instr/stage/sample) is stated for PW and pointed at D21's rework. **One new finding from the same corner: at +15 dB with Q ≤ 0.12 the peaking design gives n1 = 8.318, which does not fit Q4.28 and SATURATES at conversion — 1323 of 909,315 swept sets, the filter silently becomes a different filter.** **D5**: fixed by resolving the chain order FROM THE GRAPH in the generator, with a minimal stable repair and a hard error on a cycle, plus the same check as an INDEPENDENT instrument in dsp_validate.py. Both agree: 4 edges on chip 2, 0 on chip 1, no cycle; the cycle path is negative-controlled. **The audible consequence is stated honestly and it is NOT the one-sample comb the finding predicted: nothing writes those two buffers at all** — no scatter, no XFER, no SPI cell — so USB and BT contribute silence regardless of order. The skew is what the defect BECOMES when the D24 USB/BT path is wired. Chip 1 is byte-identical through it, which is the control. **D6**: the legacy peak decay is derived from DSP4_BLOCK_RATE — 0.99950 was derived for 1500 blocks/s and applied at 6000, so the documented 1.33 s peak hold decayed in 0.333 s, −26.07 dB/s instead of −6.5, IN THE SHIPPING IMAGE. Proven at bit level: elfdump finds 0x3F7FF7CE exactly once and the old 0x3F7FDF3B nowhere. **Hygiene, one commit each**: D8 (the dead routines went, and `_biquad_cascade_N` was worse than a loop hazard — its `rts` WAS the loop-end, so an N-stage float cascade ran ONE stage; rewritten because the float generator emits 22 calls to it), D9 (comment, tree byte-identical), D10 (ghost-cell ramp frames were 4× short at BLOCK=8; now imported from dsp_codegen and the two sides agree — DSP 18/48, 60/180, 72/72, 36/120 — where ghost_cells had 4/12, 15/45, 18/18, 9/30), D11 (image byte-identical), D12 (a `#if DSP4_BLOCK_SIZE != N / #error` in all four baking files; **negative control: dsp_block.h edited to 16 now FAILS the build in all six translation units, where before it built cleanly and wrote past the bus accumulators**). Harness 9/9 → **16/16**, D36's stale count corrected on the way. **W0, stated up front and honoured: D1, D3, D5 and D6 change the shipping image BY DESIGN; D8 shrinks it by 320 bytes of dead PM; D9, D11 and D12 are byte-identical, and D10 touches no SHARC image at all.** New shipping baseline **chip1.ldr 2072e0de, chip2.ldr a248d25d** (from 45f5f2dd / f6733b6d). The self-test costs the default image nothing. **Bench restored to the new baseline and verified: both parts boot to BOOT_STAGE 5 with frames arriving, matrix-app active, all three MCUs verified 11:27:15 on the FIRST restart.** CPLD never touched. **One thing checked rather than assumed: BLK_OVERRUN ≈ FRAME_COUNT at BOOT_STAGE 5 on both chips — the PRE-SESSION image (45f5f2dd, rebuilt from fdae4b5 in a worktree and flashed as a control) does exactly the same, so it is pre-existing and untouched by this session.** NOT started, as directed: D20–D25, the biquad hang, fused+paired measurements.]   [model: opus]

model: opus

FIX SESSION 1 — wraps and shipping correctness, from review-dsp-20260828.md
(hub-verified D1 against the tree; PW's standing ruling: every 32-bit
touchpoint saturates, a touchpoint that can wrap is SEVERE). Bench is
free; measure on the part where the standing instruments reach.

1. D1 (SEVERE) — bus accumulators must SATURATE, never wrap. Choose the
   fix shape (saturating accumulate / mr2f store / control-rate bound)
   with the trade written down and the per-MAC cost MEASURED, not
   argued. fixed_ref.mix_sum currently models an unbounded sum: update
   the model to saturate at the same boundary (this executes the PW
   saturate-never-wrap ruling — record it in numeric-spec.md), add
   golden vectors AT and ACROSS the boundary, prove asm==model on both
   sides, negative control (the unfixed behavior must fail the new
   vectors).
2. D3 — crossfade blend 64-bit difference via MRF; add the minimal
   blend model (D33) first so the fix is provable; boundary vectors.
3. D2 — bound the efb store-back analytically; clamp at conversion time
   OR accept with written justification; the bound lands in
   numeric-spec.md either way.
4. D5 — chip-2 main mix reads USB/BT one sample stale: fix the call
   order; state the audible consequence it had; prove with the graph
   process-order check.
5. D6 — legacy peak decay constant derived for 1500 blocks/s applied at
   6000: derive from the block rate (the meter rebuild already
   established the pattern); this is in the SHIPPING image — say so in
   the outcome.
6. Hygiene batch, one commit each, trivial: D8 (dead routine with rts
   loop-end), D9 (comment vs code), D11 (stale define), D10 (ramp frame
   counts from block rate), D12 (generation-vs-build block-size
   consistency check that FAILS the build on mismatch).
7. W0 discipline throughout: state expected image deltas up front
   (D5/D6 change the shipping image BY DESIGN — new ledger entries);
   bench restored verified at the end; per-fix bit-exact bars.

NOT in this session: the efficiency batch (D20-D25), the biquad hang,
fused+paired measurements — they are FIX SESSION 2, dispatched after
this lands. Do not start them.

Rules: standing traps; ladder discipline; findings for anything that
resists; push main; update the review index (mark each D# fixed with
the commit) and this block.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

**PW RULING 2026-08-28 (~21:25): 32 CHANNELS IS THE MINIMUM, NOT THE
GOAL.** The capacity requirement is 32 strips in one 21564 PLUS headroom:
margin for a few plugins and for whatever the preliminary spec missed.
Consequence for all capacity reporting from now on: the deliverable
number is not "does 32 fit" but "cycles/percent REMAINING at 32
channels" — a fit with no headroom is not a fit. Floors, ceilings and
the review's closing sum are to be stated with the margin-at-32 column.
Reaching 32 does NOT end the optimization program: work continues until
every kernel sits at its derived floor under the ruled numeric spec (or
a remaining gap demonstrably costs more than it buys) — the finish line
is floors reached, and the margin at 32 at that point is the product's
plugin headroom.

### Outcome 2026-08-29 (session 4) — the contract conformance harness

The tree gained the instrument it did not have: one that measures the
kernel against the **masters** rather than against itself. `bqst`,
`dynst`, `busgold`, `golden_harness` and `numverify` all compare the
kernel to another form of the kernel, so a cell addressed to the wrong
variable, served in the wrong unit, or wired to nothing reproduces its
own goldens perfectly and forever. Two of the three MAJOR unit findings
on the review index were exactly that shape; both are now closed and
both were proved closed on the part, before and after, on one instrument.

#### W0, stated before any of it was built

| item | expected image delta | actual |
|---|---|---|
| the harness (`tools/dsp/wire_contract.py`, `tools/pi/dsp4_conform*.py`, `conform.sh`) | none — host-side only | shipping **byte-identical**: this tree's pre-fix build reproduced chip1.ldr `ea4c9f5f` and chip2.ldr `f0a47584`, which is how the bench baseline was confirmed as well |
| D39 GateRng dB→linear + D40 CompPar percent | **CHANGES THE SHIPPING IMAGE BY DESIGN** — masters win on cell semantics | **new baseline chip1.ldr `d3cdb0c1`, chip2.ldr `a88ac883`**; +2,496 bytes of chip-1 code (173,866 from 171,370) against ~29,518 free |

The regeneration touched **78 node files and no others** — 32 GATE and 32
COMP on chip 1, 4 GRP_GATE, 4 GRP_COMP, 4 MAIN_OCOMP, MAIN_COMP and
SUB_COMP on chip 2 — which is also a check that the committed node source
was in step with its generator before the change. No contract bump: the
def CSVs, `defs.lock`, `ghost_cells` and both `dsp_params.asm` are
untouched, and `check-contract-drift.sh` passes.

#### 1. The contract, assembled from the four files that each hold part of it

`tools/dsp/wire_contract.py` joins `_matrix.csv` (cell → chip/address,
Table, RampProfile), the two `dsp_params.asm` dispatch arrays (address →
DM symbol, or 0), `wire-units.csv` (family → documented unit) and the
wire table. **The dispatch array is the authority**, not `ghost_cells`:
both are generated from the same matrix rows, so checking one against the
other proves only that the generator ran, while the dispatch array is what
the SPI handler indexes at run time and the only artefact in the tree that
can say an address is unmapped.

| | chip 1 | chip 2 | total |
|---|---|---|---|
| addresses in the dispatch table | 4,800 | 1,952 | **6,752** |
| mapped to a DM symbol | 4,555 | 1,777 | 6,332 |
| unmapped (a write is an error) | 245 | 175 | 420 |
| named by a master cell | 3,467 | 1,356 | 4,823 |
| **INERT — nothing reads or writes the target** | 448 | 448 | **896** |
| reachable by offset, not claimed either way | 66 | 4 | 70 |

#### 2. PRESENCE: every address, written and read back, and it all agrees

**Chip 1: 4,800 addresses swept in 293.9 s, and every one of them answered
as the dispatch table in the tree predicts — zero drift, zero
indeterminate.**

| verdict | addresses | what it means |
|---|---|---|
| `ECHO` | 4,363 | the word lands and reads back |
| `CLEARED` | 96 | mapped, accepted without error, reads back zero — the kernel consumed it (the EQ/HPF/LPF coefficient-set swap triggers, by design) |
| `UNMAPPED` | 213 | the part counted one SPI error per write: the dispatch entry is 0 |
| `SKIPPED_METER` | 128 | device→host readback, not written |

**The mapped/unmapped verdict is taken from the part, not from the
read-back**, and that distinction is what makes the sweep worth running.
An unmapped address and a mapped one the kernel clears every block both
read back zero — the swap triggers are exactly the second case — so a
read-back alone cannot tell "there is nothing here" from "the kernel took
it". `SPI_ERR_COUNT` can: `spi_handler.asm` increments it only on the
`.spi_error` path, reached only when the dispatch entry is 0 or the
address is out of bounds. One counter read either side of each probe
batch turns the guess into a measurement, and the error delta matched the
write count exactly on all 213 unmapped addresses and was zero on all
4,459 mapped ones.

Two things worth recording from the sweep itself. The 32 chip-1 meter
addresses that read as unmapped are **D37's `comp_gr`** — `gen_dsp.py`
gives it `add_dispatch(..., None, ...)`, a literal-0 slot, while
`ghost_cells` still serves it as a pollable cell; the sweep finds it
independently, from the part. And the meter addresses that could not be
restored (six of them) are meters doing their job: the kernel rewrites
them faster than a write-then-read can hold, and `AaChan032Mtr001` read
`0x3fbff5e2`, a live level, rather than the permanent zero the GR meters
show.

#### 3. D39 and D40: the two unit mismatches, before and after on one instrument

Both fixes are in the generator, in both the per-sample and block-kernel
bodies, and both were measured on the part with the same script before
and after — `conform.sh` on chip 1, effect phase.

**D39 — gate range.** The master documents depth in dB (`0=0/127=60`,
"Gate depth/range 0-60dB"); the kernel scaled the wire float straight by
2^28 and used it as a linear floor. The fix converts at block rate,
`10^(-dB/20)` = `2^(-dB·log2(10)/20)` through `_exp2q_fx`, clamped to the
documented range. `_exp2q_fx` preserves r6-r15 in both its table and
polynomial forms, so the live sample in r13 survives the call.

| documented write | before (`ea4c9f5f`) | after (`d3cdb0c1`) | expected |
|---|---|---|---|
| 0 dB | `0x00000000` | `0x0FFFFFE5` | `0x10000000` (unity; 27 LSB is the exp2 table's own error) |
| 20 dB | `0xFFFFFFFF` | **`0x0199999A`** | `0x0199999A` exact |
| 40 dB | `0xFFFFFFFF` | **`0x0028F5C3`** | `0x0028F5C3` exact |
| 60 dB | `0xFFFFFFFF` | `0x00041894` | `0x00041893`, 1 LSB |

Before the fix the deepest gate the protocol can ask for produced **no
attenuation at all** — `fix` of `40.0 × 2^28` wraps to −1.

**D40 — parallel blend.** The master documents percent (`0=0/127=100`);
the kernel multiplied the raw value by 2^31 with no `/100`, so any
documented value of 1 % or more pinned the blend fully wet.

| documented write | before | after | expected |
|---|---|---|---|
| 0 % | `0x00000000` | `0x00000000` | exact |
| 25 % | `0x7FFFFFFF` | **`0x20000000`** | exact |
| 50 % | `0x7FFFFFFF` | **`0x40000000`** | exact |
| 100 % | `0x7FFFFFFF` | `0x7FFFFFFF` | exact (the existing wrap clamp still carries it) |

Tolerance is **relative** (3e-5 of full scale, about 0.0003 dB) and
stated as such: the contract under test is a unit, not a rounding rule,
and the kernel is entitled to reach the documented value through float32
control arithmetic and a table-driven exp2.

`ChanPol` and `ChanMute` pass as relations rather than predicted words —
polarity must produce the exact negation (it does: `268435456` against
`-268435456`) and mute must fold the composite coefficient to exact zero
(it does: `0x10000000` unmuted, `0x0` muted). The mute check found the
harness wrong before it found anything else: it first probed `_fdr_lq`,
which is the pan leg and carries no mute, and reported a working mute as
a contract violation. The fold is in `_fdr_gq`, exactly where
`dsp_codegen`'s own comment says it is.

**Chip 2: 1,952 addresses in 120.4 s, also clean** — 1,725 `ECHO`, 21
`CLEARED`, 175 `UNMAPPED` (exactly the 175 the dispatch table predicts),
31 `SKIPPED_METER`; zero drift, zero indeterminate, zero restore
failures. **Both chips together: 6,752 addresses, 6,088 ECHO, 388
UNMAPPED, 117 CLEARED, 159 meters skipped, and not one address answered
differently from the tree.**

The first chip-2 pass was not clean and the reason is worth recording,
because it was the harness: 27 meter addresses came back as unsettled
reads. Chip 1's dispatch comments name the tap (`post_trim`,
`post_fader`) while chip 2's name the node (`C2_MTR_AUX_01`), and
`\bMtr\b` does not match inside `MTR_AUX` — the underscore is a word
character. So the harness wrote and read 27 device→host meter words as
if they were parameters. Fixed, re-run, clean.

The committed baseline is `goldens/conformance-20260829-baseline.csv`,
one row per address, which diffs line by line; the full result files run
to megabytes and are not what a later run needs to be compared against.

#### 4. The D38 inert list

**896 addresses naming 762 master cells, by kernel class, generated:**
`docs/contract/inert-cells-d38.md`. The review's estimate of ~600 was
low. The classes are the ones D38 named, with counts:

| class | addresses | class | addresses |
|---|---|---|---|
| CompFilter HPF/LPF coeffs | 212 | GateKey / GateDetSrc | 72 |
| AFB NotchFreq/Gain/Q | 216 | FX HPF coeffs | 30 |
| CompType/Key/DetSrc/LimMode/EqPos/FilterOn | 252 | DLY pool_slot | 15 |
| AFB On / CtrlOn | 24 | DCA mute | 8 |
| FX On/Decay/PreDelay/DelayTime/EqLo/EqMid/EqPresence/ModRate/ModLevel/LfoShape/Width | 66 | MON source | 1 |

**The test is a proof about the emitted source, and it is conservative in
the safe direction.** An address is inert here when no emitted line of
any node body, shared source or library file names its dispatch target
except its own declaration. A symbol reached by OFFSET from a neighbour
that IS used is counted separately (70 addresses) and claimed neither
way — that class exists because `C1_MTR_01`'s own comment says it takes
the address of `_mtr_peak` and "reaches the rest by offset", and a
per-symbol reference count called `_mtr_rms` unreferenced. Catching that
is what keeps a live meter word off a published dead list.

**THE LIVE CONFIRMATION WAS ATTEMPTED AND DID NOT SUCCEED, and no inert
verdict is reported from the part.** Two probes were built and both were
rejected by their own controls:

- A **bus capture** before and after each write, with a positive control
  on `Chan001CompThr001`. The control did not move the bus — because the
  bus is silent, and the shipping per-sample build's scope injection does
  not reach the chain: injecting a −6 dBFS step into `_buf_C1_IN_01` and
  capturing that same address returns the pre-existing word, so the
  stimulus never lands. `dsp4_pairgraph` injects into `_blk_pool`, which
  exists only in a block-kernel build.
- A **strip control-state window** — every DM word of strip 1's nodes,
  with a per-candidate null interval to calibrate drift. After excluding
  the wandering classes and adding the two-agreeing-reads guard that
  `dsp4_bq_verify` already carries, the positive control moved **2 words
  of 97 while the unwritten interval moved 0–13**. A control that does
  not clear its own noise floor cannot support a verdict underneath it,
  so the harness withholds every candidate verdict and says why.

The bar is now written so this cannot pass quietly: the control must move
more than three times the null interval, and the scorer fails any run that
reports an inert verdict without a working control. **What it needs is a
driven graph** — either the block-kernel build where `dsp4_pairgraph`'s
injection is known to work, or an injection point in the per-sample
scatter that actually lands. That is the next session's first hour, not a
rewrite.

#### 5. What the harness found that was not on the list

Four findings the review did not have, all generated rather than
asserted, all in `docs/contract/wire-units-proposals.md`:

- **D51 — the EQ/GEQ/FILT wire plane carries biquad COEFFICIENTS, not
  the parameters the masters document.** 1,036 master cells collapse onto
  322 addresses: `Chan001EqFreq001`, `EqGain001`, `EqQ001` and
  `EqShelf001` all resolve to word 0 of `_eq_coeffs_next_C1_EQ_01`. The
  host is therefore expected to compute the biquad, which no line of the
  masters says. This is the largest single disagreement in the surface
  and it is a contract page for mx26, not a kernel fix.
- **D52 — the main output chains do not line up.** The masters name three
  (`MainL`, `MainR`, `MainSub`); the DSP has four
  (`C2_MAIN_OEQ/OCOMP/OLIM_01..04`, addressed as `Main001`..`Main004`),
  and nothing in either repo states the correspondence. 134 documented
  main-output cells cannot be resolved to an address by name.
- **D53 — 1,331 documented cells reach no DSP address** after subtracting
  the families `mcu-only-prefixes.txt` already records as MCU-only. The
  largest blocks are `Chan_Rtg` (608), `FxCtrl` (241) and `ChanInput`
  (192: AntiClip, Color, InsertOn, LcrOn, Link, PadOn — all present in
  `_matrix.csv`, none reaching the DSP).
- **D54 — 1,244 mapped addresses carry a documented non-Instant ramp
  profile but have no ramp state** (`stride` = 0), so `spi_handler` falls
  back to the plain instant write and the profile in the wire word is
  discarded: DynSafe 395, EqSafe 777, GainFast 42, GainSafe 30. EqSafe is
  defensible — the EQ/FILT coefficient sets ramp by dual-instance
  crossfade rather than by `_ramp_set_target` — which still leaves 467
  addresses, `Chan001GateThr001` among them, whose documented ramp does
  not happen. Measured on the part: a DynSafe threshold write arrives in
  **2.7 ms against a documented 20**, while GainFast on a cell that DOES
  have ramp state arrives in **21.6 ms and 48.5 ms against a documented 3
  and 8**. The ramp check's own resolution is ~2 ms per sample, so it
  claims arrival and a bound, not a shape.

199 UNDECLARED families are written up as **proposals for mx26's
`wire-units.csv` and adopted nowhere here**. mx26 owns cell semantics; a
spoke that declares a unit for itself has forked the contract.

#### 6. The negative controls

Both ran, both fired, and the scorer fails the run if either does not.

- **Wrong unit.** `--negctl-unit ChanGateRng` predicts the family from
  the unit the kernel used to assume instead of the documented one — the
  corruption a wrong row in `wire-units.csv` would introduce. It failed
  **4 of 4** values on the fixed image (and 3 of 4 before the fix, the
  fourth being 0 dB, where both conventions agree on zero).
- **No read-back.** `--no-verify` writes without reading back. All **64**
  addresses came out `UNVERIFIED`; none came out `PASS`. A partial
  no-readback control is not counted as a truncated sweep — it is a
  64-address exercise by design, and the scorer distinguishes the two.

A third control is structural rather than scripted: the mute check
initially failed on a working kernel because it probed the pan leg. The
harness was wrong and the finding was retracted before it was written
down, which is the behaviour the negative controls exist to produce.

#### What was NOT done, and why

- **The live inert confirmation** (item 1c). Built twice, rejected by its
  own controls both times, reported as unavailable rather than answered.
  See section 4 for exactly what it needs.
- **The D41 family is still open and still fails**, by design: attack,
  release, hold and delay are documented in milliseconds and the kernel
  keeps one-pole alphas and raw sample counts. Those six checks are named
  one by one in `dsp4_conform_report.KNOWN_MISMATCH`, each carrying D41,
  so they do not fail the run — and a class-level exemption is
  deliberately not available, because it would silently absorb the next
  mismatch of the same shape.
- **Chip 2 gets presence testing only.** Every family whose unit is
  declared in `wire-units.csv` is a `Chan*` family and lives on chip 1's
  strips; chip 2 carries the group, aux and main output chains, all
  UNDECLARED. The harness says so in the result file rather than running
  probes against symbols that do not exist and counting the NO_SYMBOL
  rows as coverage.
- **The `MainL`/`MainR`/`MainSub` addresses were swept under their matrix
  names** (`Main001`..`Main004`), not their documented ones, because D52
  is unresolved. The addresses are covered; the names are not joined.

#### Bench hand-back

New baseline **md5-verified on the part**: chip1.ldr **`d3cdb0c1`**,
chip2.ldr **`a88ac883`** — the baseline this session created by design,
not the one it started with. Both chips boot on it: MAGIC `0xD5B40001`,
BOOT_STAGE 7, PRODUCT_ID 1, DMA0_STAT `0x00006200`, SPORT0_ERR_A
`0x00000000`, FRAME_COUNT advancing on both. matrix-app active, **all
three MCUs verified on the second restart** (H1S1, H1S4, H1S3 at
21:48:56, boot-verified at 21:49:02) — the documented second-restart
pattern. GPIOs released. **CPLD never touched.**

**Stated rather than glossed:** on the final restore boot, chip 2 answers
`CHIP_ID` 1 — consistently, over six resynced reads. `dsp4_boot.py` sent
182,272 bytes on CS2 against 301,056 on CS1, so the right file went to
the right chip select, and the same part identified correctly as chip 2
during the sweep an hour earlier. `dsp4_scope.Scope.check_chip` already
carries this warning ("dsp4_boot.py can silently leave chip 2 running
chip 1's firmware"), and the conformance harness inherits it: it refuses
to measure a part that does not identify, which is why the chip-2
baseline above was taken on a boot that did. It is recorded as an
intermittent boot behaviour on this bench, not as a property of the new
image, and matrix-app performs its own DSP boot on start.

### Outcome 2026-08-29 (session 3) — the memory recovered, the hang root-caused, and the table

Four commits: `81b5ee4` (program-memory reclamation), `6938840` (the
min-Q ruling), `2fadf39` (the paired-cascade hang), and the documentation
commit that carries this block. Finding numbers are from
`review-dsp-20260828.md`, whose index carries them; D44-D50 are new this
session.

#### W0, stated before any of it was built

| item | expected image delta | actual |
|---|---|---|
| PM reclamation (D45/D46/D47) | none — every reclamation is behind `!DSP4_BLOCK_KERNELS` or a new default-off switch | shipping **byte-identical**, chip1.ldr 2072e0de, chip2.ldr a248d25d |
| min-Q halved-n1 | **CHANGES THE SHIPPING IMAGE BY DESIGN** — new arithmetic, new bypass literal | **new baseline chip1.ldr ea4c9f5f, chip2.ldr f0a47584** |
| paired-cascade fix (D44) | probe builds only (`_bq_pair_blk` is behind `DSP4_SIMD_PROBE`) | shipping unaffected |

#### 1-2. Program memory: the wall came down, and the linker's own number closed it

Session 2 stopped because chip 1 would not link fused+paired. The
shortfall has a measured value — the linker reports **0x131a = 4,890
bytes** not mapped — and three reclamations, each measured on its own,
returned **16,824**:

| reclamation | bytes | why it was there |
|---|---|---|
| DLY per-sample body (D45) | 13,568 | 424 in each of 32 nodes. GATE/COMP/EQ/FILT/TUBE block kernels call BACK into their per-sample bodies for the sidechain-filter, sample-0 and ramping cases. DLY's does not — it handles every slot, offset and wrap case itself and returns — and the node file carries no `_process_sample` label at all, so the whole tail was unreachable code the linker still had to place |
| `dyn_selftest` (D46) | 2,240 | gated on `DSP4_SIMD_DYN`, so the instrument rode in every paired build including a shipping one. Now `DSP4_DYN_SELFTEST`, defaulting to `DSP4_SIMD_PROBE` |
| float-era library (D47) | 888 | `lib/dynamics.asm` and `lib/delay.asm`: no caller anywhere in the tree since the D5 pivot, but the linker places every object on its command line whether it is reachable or not |

Chip 1 code free, block 3 + block 2 together, out of 262,144:

| config | before | after |
|---|---|---|
| scalar, unfused | 15,062 | 29,518 |
| scalar, fused | 9,882 | 24,338 |
| paired, unfused | 418 | 17,134 |
| **paired + fused** | **−4,890, would not link** | **11,954** |

The min-Q MAC then took 12 bytes back, leaving 11,942.

`tools/dsp/pm_audit.py` is new and is what made this a ten-minute
question instead of a guess: it attributes every byte of the code output
sections to the object that contributed it, rolls objects up by node
class, and diffs two maps. `dsp_memreport.py` says how much is left;
this says who is using it.

**The structural lever named in session 2 is still there and is still the
biggest single item.** RTG is 41,344 bytes of the paired+fused image —
16.6 %, 1,292 bytes per node across 32 nodes. The indexed-array move that
took the control-rate gate from ~41 bytes per node to 3 has not been
applied to the rest of RTG's prep.

#### 3. The biquad-pair hang: a clobbered register, not a hazard (D44)

`_bq_fx_cascade_simd` writes r0-r15 — r4-r8 are the stage's five
coefficients, r9-r12 its four state words, r13/r14/r15 its constants — so
nothing `_bq_pair_blk` held in a register survived the call. The code
after it did `i0 = r10; i1 = r13;` for the signal scatter and rebuilt the
state length from r14, reading the cascade's leftovers: **r13 comes back
as 0x10000000 and r14 as 0x08000000, so the scatter wrote a block to
address 0x10000000 and then entered a hardware loop with
lcntr = 0x10000000.**

**268 million iterations, scribbling as it went, on every call.** That is
why the part never looked crashed: the diag ISR kept answering the link
while BOOT_STAGE sat at 5 and `done` never went to 1. It was not hung; it
was inside a quarter-billion-iteration loop.

It accounts for both eliminations already on record. `DSP4_SKIP_SIMDCALL=1`
boots because the registers then survive. One stage hung exactly as four
did because the corrupt lcntr does not depend on the stage count. And the
paired dynamics — same PEYEN, no interrupt mask — never hung, because
their drivers carry no pointers across the paired kernel.

Fix: five words of DM at block rate. **Negative control in the tree:**
`DSP4_BQP_NOSAVE=1` skips the reload and reproduces the session-2 symptom
verbatim — "never reached stage 6" on all three attempts, where the same
image with it at 0 completes.

**And the pairing factor is now measurable.** dynst.sh, block 8, 983.04,
two runs, all three arms `ndiff = 0 of 32` against their scalar twins:

| arm | scalar | paired | factor |
|---|---|---|---|
| COMP | 412.5 c/s/channel | 202.5 | 2.04× |
| GATE | 255.0 | 112.5 | 2.27× |
| BQ4 | 150.0 | 97.5–105.0 | 1.43–1.54× |
| BQ2 | 75.0 | 52.5 | 1.43–1.57× |

**The biquad pairing factor is 1.4–1.5×, not the 2.39× on record.** The
2.39× was measured against the OLD block cascade; strip fusion then took
32 % out of that baseline, so most of what pairing used to buy has already
been bought. The spread is tick quantisation — the paired arm is 13-14
ticks against a 1-tick null loop, so one tick is 7 %.

**It is NOT wired into the graph.** `_bq_pair_blk` is still behind
`DSP4_SIMD_PROBE` and only the self-test calls it, so the paired ceilings
below pair the DYNAMICS only. Wiring a FILT/EQ pair driver is the next
lever and it now has a number instead of a hang.

#### 4. The min-Q ruling landed, and it is not free

n1 = b1 + 2·b0 is stored HALVED in Q5.27 and its product accumulated
twice into the exact 80-bit MRF, in all four cascade forms and in
`fixed_ref.biquad`. `_bq_fx_convert_N` scales by 2^27 instead of 2^28 —
the halving is the existing multiply, not a new instruction, and the
constant goes in f1 rather than a hoisted f9 because the register file is
unified and `r9 = fix f5` one line earlier would have destroyed it.

**Proven on the part, with an instrument the biquad did not have.**
`bq_selftest` only ever diffed two asm cascades against each other, which
proves they agree, not that either is the ruled arithmetic (review finding
D35). `tools/pi/dsp4_bq_verify.py` reads the self-test's own coefficients,
stimulus and both result buffers off the DSP and re-runs `fixed_ref` over
the same words:

| build | ref vs blk | ref vs MODEL | blk vs MODEL | NEGCTL |
|---|---|---|---|---|
| FUSED=1 | 0/16 | 0/16 | 0/16 | 15/16 differ, first at sample 1 |
| FUSED=0 | 0/16 | 0/16 | 0/16 | 15/16 differ, first at sample 1 |

The negative control is the pre-ruling single-accumulation model. It
fires, so the stimulus does exercise n1 and the match means something.

**What it fixes**, over the full swept design space that
`bound_efb.design_space` enumerates — 869,627 quantised sets: **1,323
reached |n1| ≥ 8 and saturated Q4.28**, silently becoming a different
filter. Q5.27 clears **1,313** of them.

**TEN STILL SATURATE, and it is a new finding (D48).** The largest |n1|
in the space is **17.835**, and it is not the peaking corner the ruling
was written for: it is a LOW SHELF at 18.9–20 kHz, +14…15 dB, shelf-Q
2.8–3.5. No encoding at this width reaches them. Closing them is a RANGE
decision for PW — bound low-shelf f0, or a third bit and a third MAC.

**What it costs, measured**: worst magnitude error against float64
**0.046151 → 0.060560 dB**, both at f0 = 20 Hz / −12 dB / Q = 4, and
**unchanged at 0.003479 dB for f0 ≥ 50 Hz** — the cost lands only at LF,
which is exactly where the offset form's benefit lives. golden_harness's
bar moved 0.05 → 0.07 dB to match; still 6.6× better than the shipping
FP32 firmware's 0.4 dB on the same case. Harness 16/16.

**An option PW should see, because the ruling was written believing the
encoding was free.** A six-word coefficient block splitting n1 into two
Q4.28 halves that sum EXACTLY to `round(n1·2^28)` gives the same doubled
range at the same +1 MAC with NO resolution loss — the arithmetic would
stay bit-identical to the pre-ruling kernel wherever n1 already fitted,
and only the saturating sets would change. It costs one DM word per stage
(EQ: 4 stages × 3 buffers × 32 nodes = 384 words per chip, against 177 KB
free) and changes the internal coefficient stride from 5 to 6. Costed in
`numeric-spec.md`. Not taken here because the ruling names the halved
form.

**A side effect on D2, and it is an improvement**: the reachable |efb|
bound re-measures at **2^61.648, 1.352 bits of margin (2.553×)**, against
2^62.606 and 0.394 bits. The old worst set was one of the 1,323 whose n1
saturated, so what that bound measured there was a more extreme filter
than the settings ask for.

Minimum Q = 0.10 is enforced where this repo converts — `fixed_ref
.check_q` and `dsp_simulate.check_q` REJECT, they do not clamp. **The
product-side (f0, Q, gain) → RBJ conversion lives outside this repo and
needs the same floor**; that is a hub item.

#### 5. D24 re-evaluated: the memory objection is gone, the cycle case is not made

The paired+fused build now has 11,942 bytes free against the 1,312 that
blocked it, so the ~1,124-byte gate fits with room. What has not changed
is what it buys: **~9 cycles/sample against a paired strip of ~1,187, i.e.
0.76 %** — below the ±2 % band this profiling instrument has always shown,
and 0.24 of a channel against ceilings whose granularity is one channel in
22 (4.5 %). **Landing it could not move a single measured row in the table
below.** NOT landed. The decision is now PW's on grounds of value rather
than of memory, and it is stated that way in the review index rather than
quietly deferred.

#### 6. THE CAPACITY TABLE — the deliverable

Full detail is in `MW/D32/DSP/dsp4-cycle-budget.md` (new top section) and
`dsp4-function-costs.csv` (block-tagged rows). The harness is new:
`captable.sh` builds the whole point matrix in parallel and then walks the
bench once, because the bench is the only serial resource and a table's
points are all known up front.

**Ceilings, channels per chip, fused + paired, honest full-rate rule,
every point witnessed (all N gates OPEN and all N compressors ACTIVE for a
signal row, all N SHUT and unity for a silence row):**

| | 786.432 MHz | 983.04 MHz |
|---|---|---|
| BLOCK 8, signal | **16** | **22** |
| BLOCK 8, silence | **18** | **23** |
| BLOCK 32, signal | **21** | **28** |
| BLOCK 32, silence | **22** | **28** |

Block 8 at 983.04 signal present was 12 scalar-unfused and 15
paired-unfused on 08-28, and 16 scalar-fused in session 2. **It is now 22.**

**MARGIN AT 32 CHANNELS**, cycles per graph pass at 32 strips, signal
present, graph decimated so it completes whether or not it fits:

| config | BLOCK 8 (budget 163,840) | BLOCK 32 (budget 655,360) |
|---|---|---|
| scalar, unfused | 349,555 — 213.4 % | 1,280,847 — 195.4 % |
| scalar, fused | 303,355 — 185.2 % | 1,095,628 — 167.2 % |
| paired, unfused | 274,419 — 167.5 % | 922,754 — 140.8 % |
| **paired + fused** | **226,462 — 138.2 %** | **736,848 — 112.4 %** |

At 786.432: 174.0 % at BLOCK 8, 140.6 % at BLOCK 32.

**THE MARGIN AT 32 IS NEGATIVE IN EVERY MEASURED CONFIGURATION.** The best
is BLOCK 32 at 983.04 fused and paired, and it is **12.4 % OVER budget**.
Nothing measured reaches 32 channels on one 21564. What can be said is
that the gap has gone from about a factor of two to 12.4 %.

**Two chips is the part that moved.** A two-chip D32 needs 16 per chip; at
block 8 and 983.04 the ceiling is 22, against exactly 16 in session 2.

**The two instruments agree and share no arithmetic.** Ratio of cycles at
32 strips, scalar-fused against paired-fused: **1.340**. Ratio of the
ceilings those configs reach at block 8 / 983.04: **22/16 = 1.375**. Three
per cent apart.

**The silence control has almost stopped mattering** — one channel at
block 8, none at block 32, against the ~29 % it used to flatter a ceiling
by. Pairing moved the dynamics off the branch silence was cheating on.

**Per-class re-profile, fused + paired, block 8, 983.04, cycles/block per
channel** (the pair-ordered chain gives A and B as two independent
readings of every scalar class in the same run):

| class | A | B | mean | c/sample |
|---|---|---|---|---|
| IN | (in baseline) | 28 | 28 | 3.5 |
| GAIN + meter | 338 | 343 | 340.5 | 42.6 |
| FILT | 657 | 650 | 653.5 | 81.7 |
| EQ | 1,321 | 1,273 | 1,297 | 162.1 |
| GATE pair | 2,609 for TWO | | 1,304.5 | 163.1 |
| COMP pair | 3,801 for TWO | | 1,900.5 | 237.6 |
| TUBE | −75 (noise) | 68 | 34 | 4.2 |
| DLY | 492 | 481 | 486.5 | 60.8 |
| FDR | 225 | 218 | 221.5 | 27.7 |
| RTG | 363 | 378 | 370.5 | 46.3 |
| **STRIP TOTAL** | | | **6,580.5** | **822.6** |

Against the 10,198 cycles/block unfused-and-unpaired strip: **−35.5 %**.

**The instrument cross-checks itself three ways on this run.** A against B
on the same class: 1.1–4.0 % apart. Sum of parts against the whole-pair
difference: 6,636 against 6,580, **0.9 %**. Per-class total against the
independent 32-strip cycle count: 32 × 6,580 = 210,576 against 226,462 for
the whole graph, the 15,886 difference being the fixed per-block overhead
and the bus fabric a node-limited chain cuts off (the limit-1 point alone
is 8,528).

**The next lever, and it is arithmetic on measured parts rather than a
measured row:** FILT + EQ is 1,950 of the 6,580 cycles/block/channel —
**29.6 % of the strip** — and the biquad pair kernel measures 1.43–1.54×
against the fused cascade. A FILT/EQ pair driver would take the 32-channel
block-8 figure from 226,462 to roughly 205,000–208,000, i.e. 125–127 % of
budget against 138.2 % today, before the gather/scatter a driver adds. **It
does not reach 32 either.**

#### Acceptance bars run this session

| bar | result |
|---|---|
| `golden_harness.py` | **16/16** (the biquad LF bar moved 0.05 → 0.07 dB, with the measurement that moved it) |
| `bqst.sh`, both FUSED arms | ref vs blk **0/16**, ref vs MODEL **0/16**, blk vs MODEL **0/16**, negative control fires 15/16 |
| `dynst.sh` | COMP, GATE and BQ4 all **ndiff 0 of 32**; the pair hang is gone and its negative control reproduces it |
| `busgold.sh` vs `busgraph-prebatch-20260829.json` | **0 of 256 words differ, sha256 identical** |
| `numverify.sh pos` | **57 of 57 vectors bit-exact** against fixed_ref; third-word cost re-reads +2.016 c/MAC |
| `bound_efb.py` | full 869,627-set sweep re-run; the reachable bound improved to 2^61.648 |

**The busgraph golden reproducing is worth reading carefully rather than
as reassurance.** The min-Q change alters biquad coefficient words, so a
capture that exercised a real filter could not have reproduced. It
reproduced because the harness leaves the biquads at their BYPASS
coefficients, and bypass is bit-identical under the halved encoding by
construction — n1 = 2.0 becomes nh = 1.0, and 2 × 0x10000000 is exactly
0x20000000. **So that golden has no biquad-coefficient coverage at all**,
which is worth knowing before it is cited as one. The instrument that CAN
see this change is `dsp4_bq_verify.py`, and its negative control does.

The same run re-establishes the D22 control-rate gate transitively: the
gated build (`DSP4_CTL_ALWAYS=0`) reproduces word for word a capture taken
on 87fded2, before the gate existed. `ctlgate.sh` itself was attempted and
abandoned — the diag link had been through some sixty boot cycles by then
and no arm could get a clean capture in five attempts each.

#### Bench hand-back

Shipping images restored and **verified by md5 on the bench**: chip1.ldr
**ea4c9f5f**, chip2.ldr **f0a47584** — the new baseline this session
created, not the one it started with. Both parts boot on them: MAGIC
0xD5B40001 on both, FRAME_COUNT advancing (33,102 and 34,454 on the
restore pass), DMA0_STAT 0x00006200, SPORT0_ERR_A 0x00000000. matrix-app
**active on the FIRST restart with all three MCUs verified** —
20:24:45 for H1S1, H1S4 and H1S3, and again at boot-verified 20:24:51.
CPLD never touched. GPIOs released.

**Stated rather than glossed:** the STANDALONE `dsp4_config.py` path did
not commit — BOOT_STAGE stayed at 5 across five boot+config attempts at
the end of the session. That is the same signature session 1 recorded on
its own restore ("both parts boot to BOOT_STAGE 5 with frames arriving"),
matrix-app performs its own configuration, and the standalone path
succeeded repeatedly earlier tonight on these same parts. It is recorded
as a link that degrades over a long session of reboots, not as a property
of the new image.

#### What was NOT done, and why

- **FILT/EQ pairs are not wired into the graph.** The hang is fixed and
  the factor measured, but `_bq_pair_blk` is still probe-only. The
  dispatch anticipated this ("the table ships with dynamics-only pairs").
- **D24 not landed** — see item 5. It fits now; it buys 0.76 %.
- **The GAIN fold (D20) is unblocked but not taken here.** PW's
  wide-word metering ruling landed at ~17:05, mid-session, and closes the
  question this session's numbers were measured under. Every figure above
  therefore still carries GAIN's round/saturate and its tap store, and the
  ruling schedules the metering rework as its own session after the
  conformance harness. `dsp4-function-costs.csv` puts GAIN + its meter at
  340.5 cycles/block/channel, 42.6 per sample, which is the number that
  work starts from.
- **`ctlgate.sh` not re-run to completion** — bench link, above. Its claim
  is re-established transitively by the busgold run.
- **Chip 2** untouched, as directed (review finding D16), and D50 is new:
  its `C2_AUX_DLY_*` nodes take the non-pool DLY template and so have no
  block kernel at all.

---

### Outcome 2026-08-29 (fix session 2) — the efficiency batch, and the wall it ran into

Two commits, `7c0bae9` (D21) and `f179002` (D22 + D25 + D14). Finding
numbers are from `review-dsp-20260828.md`, whose index carries them.

#### W0, stated before any of it was built

| item | expected image delta | actual |
|---|---|---|
| D21 | fused path only; shipping build is `STRIP_FUSED=0` | shipping byte-identical |
| D22, D25, D14 | block-kernel builds only, BY DESIGN | shipping byte-identical |
| shipping baseline | unchanged | **chip1.ldr 2072e0de, chip2.ldr a248d25d** |

Keeping the shipping image byte-identical was not free and it is worth
saying how: the first cut declared the gate's state words and the
handler's epoch bump unconditionally, and the per-sample image moved.
Everything is now behind `DSP4_BLOCK_KERNELS`, and `ctl_epoch.asm`
additionally behind `CHIP_ID == 1` because every file under `src/` is
assembled once per chip and the fader-busy pointer table names chip-1
symbols a chip-2 link does not have.

#### The per-class re-profile — block 8, signal present, unfused, scalar

Same instrument and the same switches as the record it replaces
(`sigprofile.sh`, DEC=32, `DSP4_PROFILE_SIGNAL=1`, `DSP4_STRIP_FUSED=0`,
every point witnessed). Limits 4 and 7 lost their witness to the bench
link, so EQ+GATE and TUBE+DLY are carried as pairs.

| class | 08-28 | 08-29 | Δ cycles/block | what it is |
|---|---|---|---|---|
| GAIN (+MTR) | 183 | 187 | +4 | untouched — instrument noise |
| FILT | 1095 | 1085 | −10 | untouched (D21 is the FUSED path) |
| EQ+GATE | 4201 | 4163 | −38 | untouched |
| COMP | 3465 | 3538 | +73 | untouched |
| TUBE+DLY | 598 | 531 | **−67** | **D25, circular DAG addressing** |
| FDR | 323 | 278 | −45 | untouched — see the flag below |
| RTG | 1861 | **416** | **−1,445** | **D22, the control-rate gate** |
| **STRIP** | **11,726** | **10,198** | **−1,528 (−13.0 %)** | |

**The instrument is calibrated by the classes that did not change**:
four of them land inside ±2 %, which is the band this instrument has
always shown (the record's own two readings of the strip are 1.1 %
apart). RTG's −1,445 is twenty times that. **FDR's −45 is OUTSIDE the
band and is not explained by anything in this batch** — that kernel was
not touched — so it is carried as measured and flagged rather than
attributed; re-read it before anything is built on the difference.

**The delay-line result answers a question the review left open.** D25
removed twelve instructions per sample, which is 96 per block, and 67
came back. So of DLY's 63.1 cycles/sample the ADDRESSING was worth 8.4
and about 55 is L2 latency on the delay lines. "L2 cost needs
measurement" is now measured, and the answer is that the class is
memory-bound: no further address arithmetic will touch it.

#### The measured ceiling, and the honest rule

983.04 MHz, block 8, signal present, full-rate rule (6000 blocks/s),
per chip, every point witnessed gate-OPEN and compressor-ACTIVE on every
retained strip:

| configuration | ch/chip | evidence |
|---|---|---|
| scalar, unfused, 08-28 | 12 | recorded |
| **scalar, FUSED, after this batch** | **16** | 16 = 5999/s, 17 = 5779/s |

The slope model calibrates against both ends: holding the derived
block-8 fixed overhead F = 18,785 cycles/block, the 17-strip point
(5779/s → 170,104 cycles/block) puts the fused strip at 8,901
cycles/block = 1,112.6 cycles/sample, which predicts 16 at 983.04 — and
the same model with the measured unfused strip predicts 12 before the
batch and 14 after it, against 12 measured before. Two arithmetics that
share nothing agree.

#### Margin at 32 (the PW ruling's deliverable column)

Available per strip at 32 channels is `(budget − F) / 32`: **566.6
cycles/sample at 983.04**, 438.6 at 786.432.

| configuration | strip c/s | margin at 32, c/s/strip | % of budget |
|---|---|---|---|
| 983.04 scalar unfused, BEFORE | 1,465.8 | −899.2 | **−175.9 %** |
| 983.04 scalar unfused, AFTER | 1,274.8 | −708.2 | **−138.6 %** |
| 983.04 scalar FUSED, AFTER | 1,112.6 | −546.0 | **−106.8 %** |
| 983.04 paired unfused (08-28) | 1,187.0 | −620.4 | −121.4 % |
| 983.04 paired + fused | **not buildable** | — | — |

**32 still does not fit, and the batch moved it from 2.59× over to
1.96× over.** No row here is a projection: each strip figure is either
measured per class or derived from a measured ceiling with F held at the
value the record already derived. The floors say the remaining factor is
still in the code — the two dynamics classes are 7,701 of the 10,198
strip, 76 %, and neither was touched today.

#### THE BLOCK: chip 1 is out of program memory

Dispatch item 8 was "build fused + paired TOGETHER at block 8 for the
first time". **It does not link.** Measured on the link map, all 32
strips' node bodies present (`DSP4_STRIPS` gates chain CALLS, not code):

| configuration | free bytes | links? |
|---|---|---|
| scalar unfused | 15,062 | yes |
| scalar fused | 9,882 | yes |
| paired unfused | 418 | yes |
| **paired + fused** | **over** | **NO** |

`sec_swco` is FULL — 131,070 of 131,072 — in every block-kernel build,
so everything else spills into block 2's overflow section, and the
paired+fused build exhausts that too. **It is not this session's gate**:
the same build with `DSP4_CTL_ALWAYS=1`, which compiles the gate out
entirely, still overflows. Nor is the paired SIGNAL-PRESENT ceiling
measurable any more — paired plus the profile stimulus fails to link
with and without the gate, so that is pre-existing growth rather than a
regression from today, and it is why item 8's paired column is empty.

**The lever is structural, and this session demonstrated it in
miniature.** The gate began as nine inline instructions per node. A
directly-addressed DM access is a LONG VISA instruction, so that came to
~41 bytes per node, 1,320 across 32 ROUTING nodes — by itself enough to
stop the paired build linking. Rewritten as indexed per-strip arrays
plus one shared `_ctl_strip_prep_needed`, the caller is three
instructions: 896 bytes back, ~2.5 cycles/sample/strip paid, against the
~180 the gate saves. The graph is 431 node files each carrying its own
copy of a kernel that differs from its neighbours only in which
variables it names; ROUTING is ~600 lines × 32. Applying the same move
to ROUTING's whole prep and then to the dynamics bodies is what buys the
room fused+paired needs. Recorded in `dsp4-cycle-budget.md`.

#### What did not land, and the number that says why

- **D20 (GAIN = 1 MAC).** The fold deletes GAIN's `BLK_CHAIN_B` store
  and nothing else — about 1 cycle/sample. The twelve-instruction
  round/saturate and the tap store are not there for FILT; they are
  there for the **METER** and for the router's **pickoff-0**, and both
  need a Q4.28 post-trim sample that the fold makes cease to exist. The
  two ways out are (a) fuse the meter into GAIN's loop and fold the
  pickoff into the crosspoint coefficients — still leaves the
  round/saturate, worth ~4 c/s — or (b) meter the PRE-trim signal and
  scale at fold time (peak ×|g|, mean square ×g²), which is the only
  form that reaches ~2 c/s and which CHANGES WHAT THE INPUT METER
  MEASURES. That is a ruling, not an implementation, and the 17:35
  amendment does not cover it: it sanctions deleting the intermediate
  rounding between GAIN and the biquad, not moving the meter's tap.
- **D23 — withdrawn as written.** The finding says `_acc64_mac_blk`
  "reloads the 64-bit accumulator every sample" and prescribes "load the
  pair once, 8 dual-issued load+MACs, store once". **The accumulator is
  BLOCK triples — one `[lo, hi, ex]` per SAMPLE of the block, not one
  per bus** (`bus_accumulators.asm:32-56`), because the bus produces a
  block of output samples. The reload is per-sample because the
  accumulator is. The loop-inversion that WOULD make an MRF-resident
  form possible needs the crosspoint sources to stay live across strips,
  and they do not: `BLK_CHAIN_A` is a two-pool ping-pong reused by the
  next strip. What is left in RTG's 416 cycles/block is that accumulate,
  14 instructions per sample per live crosspoint, and it is the next
  real target — but not in the shape the finding describes.
- **D24 — implemented, then reverted on the measurement.** Gates on
  GAIN, FADER_PAN and GATE cost **~1,124 bytes** of the 1,312 left in
  the paired build and buy **~9 cycles/sample of 1,466** (GAIN 2.5, FDR
  4.9, GATE 2.0 by instruction count). Against the binding constraint
  that is a bad trade, and it is the constraint the previous section is
  about. The part of D24 that is worth real money — the pair drivers'
  sample-0-through-the-scalar-body overhead — is a restructure of
  `dyn_pairs.asm`, not a gate, and is still open.
- **D25 remainder.** The EQ tap-copy loop and the TUBE bypass copy are
  ~2 cycles/sample each and both need the generator's slot protocol
  changed (TUBE would have to run in place so the ping-pong survives its
  runtime bypass). Not taken: the risk is a silent wiring error in 32
  strips for 0.14 % each.

#### The biquad-pair hang — localised, and one suspect eliminated

The D21 self-test would not run at all: `_bqst_done` stayed 0, the part
stamped BOOT_STAGE 5 and the diag timer ISR kept answering the link,
which is exactly the recorded signature of firmware that never ran. With
`DSP4_SKIP_PAIR=1` — the identical image with only the `_bq_pair_blk`
call removed — BOOT_STAGE 7 and done=1.

So the hang is inside `_bq_pair_blk` or what it calls, and **the DO-loop
tail hazard is eliminated as the cause**: the loop two lines above it in
the same routine has exactly the same shape, `call _bq_fx_cascade_blk`
as the second-from-last instruction of a hardware loop, and runs
perfectly. Together with the shipping RTG loop (review finding D7),
that is now a second piece of evidence that rule (a) as recorded is
broader than what this silicon enforces for a call that returns into its
loop. `bqst.sh` defaults `SKIP_PAIR=1` so the instrument is usable while
the pair is unresolved.

#### New instruments

- **`goldens/busgraph-prebatch-20260829.json`** — 256 words of the main
  bus, captured out of a running graph on `87fded2`. The efficiency
  batch is bit-exact by construction, so one capture tests all of it.
- **`busgold.sh`** — builds the current tree and holds it to that
  capture. Result: 0 of 256 words differ, same sha256.
- **`ctlgate.sh`** — the gate against its own controls: `DSP4_CTL_ALWAYS`
  (gate compiled out) and `DSP4_CTL_NEGCTL` (gate present, handler's
  epoch bump removed, so the gate goes deaf to host writes).
- **`bqst.sh`** — the local driver `bq_selftest.asm` never had.

#### Not done, and it is the dispatch's own item list

Items 8, 9 and 10 are complete only as far as the program-memory wall
allows. **Measured**: the per-class re-profile at block 8 unfused, the
fused scalar ceiling at 983.04, and the margin-at-32 table above.
**Not measured**: 786.432 (no points taken), the silence controls, block
32, and every paired row — the last three because paired-plus-stimulus
does not link. The options paper and ledger carry the memory finding;
`dsp4-function-costs.csv` carries the new per-class numbers with the old
ones beside them.

---

### Outcome 2026-08-29 (fix session 1) — the wraps, and what the part said about them

Ten items, ten commits, `fdae4b5..87fded2`. Every finding number below is
from `review-dsp-20260828.md`, whose index now carries the commit for
each.

#### W0, stated before any of it was built

| item | expected image delta | actual |
|---|---|---|
| D8 | shrinks (dead PM removed), no behaviour change | −320 bytes both chips |
| D9, D11, D12 | none | byte-identical |
| D10 | none (MCU-side artifact) | no SHARC change |
| D5 | chip 2 only, BY DESIGN | chip 2 moved, **chip 1 byte-identical** |
| D6 | both chips, BY DESIGN (shipping ballistics) | both moved |
| D1, D3 | both chips, BY DESIGN (shipping arithmetic) | both moved |

Baseline `chip1.ldr 45f5f2dd, chip2.ldr f6733b6d` (the md5s the SIMD
graph-wiring session recorded, reproduced from a clean tree at the start
of this one). New shipping baseline **`chip1.ldr 2072e0de,
chip2.ldr a248d25d`**.

#### D1 (SEVERE) — the bus accumulators

`_acc64_mac` and `_acc64_mac_blk` accumulated in the 80-bit MRF and
stored MR1F:MR0F, discarding MR2F and rebuilding it from the sign of
`hi` on the next load. That is a 64-bit Q8.56 store, range ±128.0, with
nothing saturating it — and the readout's saturation check then ran on a
value that had already wrapped, so a wrapped sum passed as a clean
sample. Reachable: one contribution reaches 64.0 (strip exit ±7.999 ×
crosspoint coefficient ±7.999), so three cross it; 32 coherent channels
at full scale exceed it by 16× and read back as −32 LSB, which is to say
SILENCE.

**The fix shape, chosen and written down.** Three words per accumulator
slot, `[lo, hi, ex]` — the whole MRF — not a saturating 64-bit
accumulate. Saturating at ±128.0 clips a PARTIAL SUM: a bus whose
contributions cancel (+100 and −100) has a legitimate small answer and a
saturating accumulate returns the wrong one, order-dependently.
Exactness and order-independence are what a wide accumulator is for, and
the ruled single round stays at readout where the spec puts it.

**The cost, MEASURED.** `numverify.sh`'s timing arm, 200,000 iterations
per arm against TCOUNT plus the 1 kHz tick (ticks alone quantise to
2.46 cycles/MAC and cannot see this), 491.52 MHz:

| form | pre-fix | fixed | delta |
|---|---|---|---|
| `_acc64_mac` (per-sample) | 27.073 | 29.076 | **+2.003 cycles/MAC** |
| `_acc64_mac_blk` (block) | 15.290 | 17.296 | **+2.005 cycles/MAC** |

+2 for both, although the block form costs THREE more instructions — the
extra load and store pipeline against each other. The instruction count
predicted +3 and was wrong, which is the reason the dispatch asked for a
measurement. Against ~5–6 for a saturating accumulate (the MV test plus
a conditional 64-bit clamp): cheaper and stronger. Memory is +1 word per
slot — 25 words per-sample, 200 at BLOCK=8. Finding D23 deletes the
memory round-trip from the block form entirely and takes this +2 with
it.

`fixed_ref.mix_sum` now saturates at the 80-bit boundary instead of
using unbounded ints. That is PW's saturate-never-wrap ruling applied to
a wider-than-32 touchpoint, and it is what let the model see D1 at all —
until 2026-08-29 the model was RIGHT and the assembly was wrong, and no
golden vector went near the boundary. The bound is in
`shared/numeric-spec.md`: a bus takes ≤ ~64 contributions each ≤ 64.0,
so |Σ| ≤ 4096 = 2^12 against the store's 2^23 — eleven bits, 2048×.

#### D3 — the crossfade blend

`r5 = r0 - r14` wrapped when the two dual-instance outputs straddled
full scale mid-swap. It is now `mrf = new*alpha; mrf = mrf - old*alpha`:
the same two instructions, the difference never formed in 32 bits, and
identical arithmetic everywhere the subtract did not wrap. The five
duplicated copies (EQ, the GEQ/AFB helper, FILT, both crossover legs)
now come from ONE generator expression, `_xfade_blend_core()`, which is
also what emits the self-test's probe — so the instructions proved
bit-exact are the instructions 66 nodes run. The refactor is
comment-only in emitted bytes, verified by md5.

The blend had no model at all (D33). It has one now, with the final
add's non-overflow as a proven bound rather than an assumption.

#### THE INSTRUMENT, and it cuts both ways

`MW/D32/DSP/SHARC/numverify.sh` → `src/lib/num_selftest.asm` (generated)
→ `tools/pi/dsp4_num_verify.py`. Vectors live once, in
`tools/dsp/boundary_vectors.py`, and are consumed by the golden harness,
the generated `.var` tables and the Pi-side reader — nobody retypes a
number. 15 mix vectors (7 across the 64-bit boundary, including 128 ×
1.0 which lands EXACTLY on it and 127/129 either side) and 42 blend
vectors (24 across the 32-bit difference).

    POSITIVE   57 of 57 BIT-EXACT against fixed_ref, in a per-sample
               build and in a DSP4_BLOCK_KERNELS build
    NEGATIVE   DSP4_NUM_NEGCTL=1 puts the pre-fix arithmetic back in the
               SAME image: 31 of 31 boundary vectors DETECTED, 26 of 26
               non-boundary vectors untouched

The negative control's bar is "differs from the fixed model on exactly
the vectors that cross a boundary, and matches it everywhere else" — a
control that merely fails proves little.

**Two things the part corrected, both worth the record:**

1. **The alpha quantisation is FLOAT32.** The parameter plane is float32
   by ruling, so alpha is a float32 and `f4 = f4 * f5` is a float32
   multiply by 2^31 before `fix`. Modelling it in float64 disagreed with
   the part by 15 LSB at alpha = 1 − 1/576; float32 agrees on every
   vector. `fix(2^31)` was measured to return 0xFFFFFFFF on this core,
   not a saturated 0x7FFFFFFF — but alpha = 1.0 is unreachable, because
   the kernel stores the advanced alpha only while it is still below
   1.0 and otherwise ends the fade. numeric-spec now says so, and says
   any change to that ramp must preserve alpha < 1.0.
2. **An unvoted `peek` produced a false mismatch** and cost a round of
   theorising about SHARC MAC saturation before a re-read showed the
   model had been right. A dropped answer on this link comes back as a
   well-formed stale word, not as an error. Every result word is now
   read until the same value returns twice.

#### D2 — bounded, not fixed, and the margin is thin

`tools/dsp/bound_efb.py` reproduces all of it.

- **Provably safe region:** when the stage does not saturate,
  `efb = acc − (y<<28)` IS the rounding remainder, |efb| ≤ 2^27 —
  thirty-six bits below the store. Growth needs the saturation branch.
- **The pessimistic bound does not close.** With the four state words
  independent at ±8.0 and adversarial signs, |acc| ≤ 8·S·2^56 where
  S = 4|b0|+|n1|+|n2|+|c1|+|c2|+3. Over the product's own DEFS ranges
  (f0 20 Hz–20 kHz, ±15 dB, Q 0.1–10) the worst S is **38.56** →
  |acc| ≤ 2^64.27, above 2^63. **So the conversion-time clamp option is
  CLOSED**: it would have to demand S ≤ 16 and would reject settings the
  contract allows.
- **The reachable bound, measured:** full-scale adversarial drive
  (random ±FS, square at f0, DC; 200 k samples per set; a greedy
  per-sample adversary as a cross-check) on the worst design-space sets
  gives **|efb| = 2^62.606** at f0 = 14.16 kHz, +15 dB, Q = 0.1.
  **0.394 bits of margin (1.314×), and it is recorded as thin.**

Consequence of exceeding it is not a rounding error: a wrapped efb of
order 2^63 re-enters the next accumulation as ~2^35 in Q4.28 and pins
the stage output at full scale until the state washes out. The option
NOT taken — saturate the efb store at ±(2^63−1), bit-identical in the
reachable domain, ~3 instructions per stage per sample — is in
numeric-spec for PW, pointed at D21's biquad rework where it is cheaper
to fold in than to add now.

**ONE NEW FINDING, from the same corner.** At +15 dB with Q ≤ 0.12 the
peaking design gives `n1 = b1 + 2·b0` up to **8.318**, which does not fit
Q4.28 and SATURATES at conversion — the filter silently becomes a
different filter. 1323 of 909,315 swept design-space sets, all in that
corner. Recorded beside the bound; the missing coverage for
`_bq_fx_convert_N` is D27.

#### D5 — chip-2 process order, and what it actually cost

Fixed by resolving the chain order FROM the graph (`dsp.csv` inputs) in
the generator: a minimal, stable repair that keeps CSV order except
where a dependency forces a move, and a hard error on a cycle rather
than a quiet linearisation. `dsp_validate.py` gains the same check as an
INDEPENDENT instrument. Both agree — 4 edges on chip 2, 0 on chip 1, no
cycle — and the cycle path has its own negative control (an edited
`dsp.csv` makes the validator name the cycle and the generator raise).

**The audible consequence, stated honestly, is not the one-sample comb
the finding predicted.** Nothing writes `_buf_C2_USB_IN` or
`_buf_C2_BT_IN` at all: chip 2's scatter handles only the 37 inter-chip
receives, no XFER node targets them, no SPI cell writes them, and the
AUX_INPUT kernel reads and rewrites its own buffer in place. From reset
the value is 0 and stays 0, so USB and BT contribute silence to the main
mix regardless of call order. The skew is what the defect BECOMES the
moment those inputs are wired — the D24 USB/BT path is exactly that —
and the wrong-graph-order CLASS is what the fix retires. That the two
nodes are inert at all belongs to D38.

Chip 1 had zero violations, so the repair is a no-op there and chip1.ldr
is byte-identical through the change. That is the control.

#### D6 — the legacy peak decay, in the shipping image

`_meter_decay = 0.99950` was derived for 48 kHz/32 = 1500 blocks/s and
applied once per block at 6000. Ballistics at the shipping operating
point: **τ = 0.3332 s, −26.07 dB/s**, against the file's own documented
1.33 s and −6.5 dB/s. It now takes `DSP4_MTR_DECAY_F32` from the
generated `dsp_block.h`, computed as exp(−1/(rate·τ)) from
`fixed_ref.METER_TAU_PEAK_S` — the same time constant the rebuilt
in-kernel meter's `DSP4_MTR_BETA_Q` uses, so the two meters now agree by
construction. **τ = 1.3327 s, −6.52 dB/s.** Proven at bit level: elfdump
of chip1.dxe finds 0x3F7FF7CE exactly once, in the initialiser for the
word `_meter_decay_block` reads, and the old 0x3F7FDF3B nowhere.

#### Hygiene, one commit each

- **D8** the dead block routines went (~90 instructions of PM plus an
  8-word scratch, linked into every shipping image). `_biquad_cascade_N`
  was worse than the loop hazard D8 named: its `rts` WAS the loop-end
  instruction, so `do .cascade_loop until lce` executed the return on
  the FIRST iteration — an N-stage float cascade ran ONE stage and
  returned from inside a live hardware loop. It is REWRITTEN rather than
  removed, because the archived `--format float` generator emits 22
  calls to it and deleting the symbol would only move the failure to the
  link. Verified: float generation still produces an assembling EQ node.
- **D9** comment corrected to `_P1`, with the rule (pool parity follows
  the strip NUMBER) rather than the conclusion. Tree byte-identical.
- **D10** ghost-cell ramp frames were computed against a hardcoded
  0.667 ms — the BLOCK-32 frame period — so every count in
  `ghost_cells.c` was 4× short at BLOCK=8. `gen_dsp.py` now imports
  BLOCK/FRAME_MS/ms_to_frames from `dsp_codegen.py` and fails loudly if
  it cannot. The two sides now agree, and did not before: DSP
  `ramp_tables.asm` has always carried 18/48, 60/180, 72/72, 36/120;
  `ghost_cells.c` carried 4/12, 15/45, 18/18, 9/30.
- **D11** four dead defines removed; image byte-identical.
- **D12** a `#if DSP4_BLOCK_SIZE != <generation BLOCK> / #error` is now
  emitted into every generated file that BAKES a size —
  `bus_accumulators.asm`, `ramp_tables.asm` and both `lane_config.c`
  (two of which did not include `dsp_block.h` at all). **Negative
  control: `dsp_block.h` edited to 16 with the tree still generated at 8
  now FAILS the build, rc=1, all six translation units naming the
  #error. Before this commit the same edit built cleanly and produced an
  image that writes past the bus accumulators.**

`golden_harness.py` is **16/16** (was 9/9 in the spec's stale count —
D36 — then 10/10). The two new families carry structural negative
controls: the pre-fix arithmetic must get wrong EXACTLY the vectors
predicted to cross a boundary, and the predicted set is computed from
the vectors rather than written down, so a vector added later cannot
quietly stop testing anything.

#### Bench

Restored to the new baseline and verified: `chip1.ldr 2072e0de,
chip2.ldr a248d25d` flashed, both parts boot to BOOT_STAGE 5 with frames
arriving, matrix-app active, **all three MCUs verified 11:27:15 on the
FIRST restart**. CPLD never touched.

**One thing checked rather than assumed.** BLK_OVERRUN reads ≈
FRAME_COUNT on both chips at BOOT_STAGE 5. The PRE-SESSION image
(45f5f2dd, rebuilt from `fdae4b5` in a throwaway worktree and flashed as
a control) does exactly the same, so it is pre-existing and untouched by
this session. Not chased further here.

#### Not started, as directed

D20–D25 (the efficiency batch), the biquad-pair hang, fused+paired
measurements. Those are fix session 2.

## HUB DISPATCH 2026-08-28 21:19Z — dsp codebase review — efficiency floors, correctness sweep, headroom proof   [status: 🟢 done — `review-dsp-20260828.md` at repo root: 38 assigned findings D1–D43 with file:line. AXIS 2 VERDICT: **32 fits at floor with margin at 983.04 — scalar floor 330–420 c/s vs 566.6 available (≥35 %), paired floor 200–256 vs the same (≥2.2×); at 786.432 scalar is a 4 % fit at the pessimistic floor end, paired ≥71 %** — fixed overhead 18,785 c/block DERIVED from the two paired-ceiling points (predicts the measured 5,756/s 16-strip miss to 0.03 %); today's paired strip misses the 32-line by 2.1× and the floors say that whole factor is code (RTG 15–29× over floor from control-rate work run every block; dynamics 3.3–4.1×; biquads ~2× even fused), not rulings. ONE SEVERE: the 64-bit bus accumulators DISCARD MR2F and wrap at Σ≥128.0 linear with no saturation before readout — the +30 dB coherent case holds with 12 dB margin but hot strip exits × boost sends wrap, and fixed_ref (unbounded ints) cannot see it. Correctness: chip-2 main mix reads USB/BT one sample stale (shipping); legacy peak decay 4× fast at block 8 (shipping); block-kernel builds report frozen input peaks off never-written slot vars; gen_dsp.py still bakes ramp frames at the 0.667 ms block-32 period into ghost_cells; the recorded call-in-last-3 loop rule is CONTRADICTED by the shipping RTG loop that measurably works — needs the SHARC+ Core PRM (not in the local doc set) before anyone "fixes" it; generation-time .var sizes vs build-time DSP4_BLOCK_SIZE have no consistency check (the lcntr=31 mechanism, still open at the seam — otherwise the literal class is EXTINCT, swept to zero across 666 node files). Coverage: COMP wet path, TUBE (zero coverage of any kind), GATE state machine, pan law, crossfade blend and _bq_fx_convert_N (the b1=0 site) all lack references; meter model never runs in golden_harness. Contract: gate_gr/comp_gr confirmed with mechanism (comp_gr is a live literal-0 cell); ~600 writable-but-inert SPI slots incl. AFB with NO bypass and an FX param key (fx_class) the CSV never emits; GateRng documented dB but consumed LINEAR; CompPar percent vs 0..1; att/rel/hold/delay ms-vs-native undecided cross-repo; pan law linear vs documented constant-power (PW decision). Chip 2 has no block kernels — every block-8 number is chip-1-only and block-8 shipping is gated on it. Desk work only: no builds, no flashes, tree clean. The ~21:25 margin-at-32 ruling landed mid-review and is honoured: the closing sum carries the margin-at-32 column (at floor: 147–237 c/s/strip remaining at 983 scalar, 311–367 paired; today's code: NEGATIVE, −620 c/s) and the review's own finish-line framing (floors, then margin-at-32 = plugin headroom) matches the 696523c addendum.]   [model: fable]

model: fable

DSP CODEBASE REVIEW — full-depth, findings only (PW go, 2026-08-28
evening). PW's goal is 32 channels in a single 21564 at 983.04 MHz and
believes efficient coding gets there; this review serves that goal by
being EXACT — no optimistic shading, no projection language. Every claim
names file:line and is stated so the hub (and PW, who writes asm) can
verify it by reading the tree. FINDINGS ONLY: no fixes land, no source
changes, no flashing — desk work against the existing tree and the
existing measured record (this week's calibrated numbers). Where a
finding genuinely needs a new measurement to be actionable, mark it
"needs measurement" for the fix session rather than arguing it.

Deliverable: `review-dsp-20260828.md` at repo root, committed and
pushed. Numbered findings D1..Dn, each with severity, evidence
(file:line + the measured record), and effort size (S/M/L). Plus the
two tables below.

AXIS 1 — EFFICIENCY FLOORS, per node class (the core of the review):
For every generated kernel class (GAIN, EQ, FILT, GATE, COMP, TUBE,
DLY, FDR, RTG, meter, and the block-rate/driver sections): derive the
INSTRUCTION FLOOR from the ruled numeric spec (Q4.28 interchange, 64-bit
error feedback where ruled, single round/saturate per strip, the
GAIN-fold amendment, multifunction packing and dual-fetch as the
hardware allows), then COUNT the emitted code against it. Known entry
point: `_bq_fx_cascade_N` emits ~40/stage against a packed floor
estimated 18-22 (loads not fused into MAC lines) — do this analysis for
EVERY class, and for the SIMD-paired forms state floors per CHANNEL.
Table: class | emitted (cyc/sample, measured where the record has it) |
floor | gap | dominant waste (named lines) | packed-replacement sketch |
effort. Also flag scaffolding that repeats per sample but could move to
block rate or control rate without violating a ruling.

AXIS 2 — THE CLOSING SUM: floors + measured fabric/block-I/O + driver
per-block work, at BLOCK=8, per chip, 983.04 and 786.432: how many
channels fit AT FLOOR, scalar and paired. State the verdict in one of
three forms ONLY: "32 fits at floor with margin X", "32 misses floor by
X", or "32 fits only if numeric ruling Y is relaxed (state the trade)".
The 32-in-one goal line is ~550 cycles/sample/strip at 983 after
measured overheads — show the arithmetic, do not round in the goal's
favour.

AXIS 3 — CORRECTNESS SWEEP (the classes that bit this week):
- Block-size literals: audit EVERY numeric literal in the generator and
  kernels that encodes 32/31/8/BLOCK-derived values, INCLUDING code
  behind guards where the byte-identical control is blind (the lcntr=31
  class — six found today; find the rest or state there are none).
- Graph wiring: every tap, pool reference, and guard in generated nodes
  resolved FROM the graph, never assumed (the 21-meter wrong-source
  class); pool ownership consistency on both chips.
- The two recorded SHARC loop hazards: audit every DO-loop tail and
  branch target in emitted code against them.
AXIS 4 — GOLDEN-REFERENCE COVERAGE MAP: which numeric paths have
fixed_ref goldens and which do not (the meter had NONE until
yesterday); list every uncovered path as a finding.
AXIS 5 — CONTRACT AUDIT: dsp.csv vs the mx26 masters — every named tap
or parameter that lacks an id (the gate_gr/comp_gr class), every id
that maps to nothing, every unit/scale mismatch.
AXIS 6 — HEADROOM AND ROUNDING PROOF (PW ask, tonight): enumerate EVERY
32-bit touchpoint in the audio path (strip exits, bus taps, delay-line
stores, TDM output, meter taps); verify each SATURATES and cannot wrap;
bound the bus-summing worst case (32 coherent channels = +30 dB — are
the bus accumulators 64-bit end to end, saturating only at the final
output round?); inventory every rounding site and confirm the
single-round-per-strip claim holds everywhere. Any touchpoint that can
wrap is a SEVERE finding.

Rules: no fixes, no reordering of PW's rulings (Q4.28, error feedback,
block-8 operating point, GAIN-fold amendment are the spec — floors are
derived UNDER them, and relaxations may only be STATED as options with
trades, never assumed); severity honest; push main when the document is
committed. This is overnight desk work — take the time the depth needs.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

**PW RULING 2026-08-28 (~17:35): GAIN=1MAC NUMERIC AMENDMENT — the
gain-into-biquad fold's arithmetic IS the new reference.** The fold
(scale [b0, n1, n2] by g at control rate, x-history unscaled) deletes
the intermediate Q4.28 round/saturate between GAIN and the first biquad
stage; that deletion is SANCTIONED. Bit-exactness bar unchanged in form:
exact match against fixed_ref UPDATED to the folded arithmetic (goldens
regenerated from it), negative controls still required — not against the
old per-stage-rounded chain. Unblocks GAIN = 1 MAC (−17 cycles/sample).
Implementation rides the next kernel session after the SIMD wiring rung.

## HUB DISPATCH 2026-08-28 17:17Z — SIMD graph wiring — measured paired-strip ceilings at block 8 and 32   [status: 🟢 done — **THE GRAPH IS PAIRED AND MEASURED, AND THE NUMBERS THIS RUNG WAS SENT TO BUILD ON WERE WRONG.** Six block-32 literals survived the block-size parameterisation, invisible to its byte-identical control because every one lives behind a block-kernel or self-test guard. The worst is `lcntr = 31` in the generator's COMPRESSOR block kernel: at BLOCK=8 **COMP ran 32 samples of an 8-sample block**, four times the work, writing three slots past `BLK_CHAIN_B` over the trim tap. **That is the whole of "COMP is block-invariant, 13.5k cycles/block, 73 % of the strip" — WITHDRAWN.** Re-measured: COMP is 3,465 cycles/block = 433.1 cycles/sample against 426.1 at block 32, the strip is 11,726 (second reading 11,859, 1.1 % apart), and the block-8 penalty is 1.19x per sample, not 2.21x. Every other class reproduces its recorded figure to within 0.5 %, which is what makes COMP's move attributable. **THE CEILINGS ROUGHLY DOUBLE AND THE PAIRED ONES ARE MEASURED, signal present, honest 6000/s, per chip: scalar 9 at 786 and 12 at 983 (was 5 and 6); PAIRED 11 and 15.** **16/chip at 983 — what a two-chip D32 split needs — now misses by 4.2 % of the block budget, not by a factor.** Pairing is worth +22 % at 786 and +25 % at 983 in the GRAPH, less than the kernel factors alone because the driver's per-block work is inside the number. **THE WIRING IS TWO POOLS, NOT A PARK:** the odd strip of each pair is GENERATED against a second block pool so both strips are live at once with NO copying, the chain is pair-ordered, the block-rate conversion is not duplicated (sample 0 goes through the scalar body, the pair takes BLOCK-1 via a new `_dsim_n`), the fallback is net-preserving and odd strip counts fall out of it — the 11- and 15-strip ceilings are both odd, so that path is exercised in the measurement. GATE's variable layout had to move to satisfy the pair interface and **the build now checks the addresses out of the .map instead of trusting declaration order**. Chip 2 has no strip-shaped dynamics: not applicable, unchanged. **KERNEL BIT-EXACTNESS RE-ESTABLISHED WITH A DIFF THAT CAN NOW FAIL** (it compared untouched zeros at block 8 before): COMP and GATE 0 of 32 positive, **16 of 32 under NEGCTL** — exactly one channel of the pair — at 2.07x and 2.43x. **THE GRAPH-LEVEL BIT-EXACTNESS BAR IS NOT MET:** the probe and harness are in the tree and correct, but every attempt was lost to the bench link (BOOT_STAGE 0, `answers as CHIP 0`, then empty reads after ~45 boot cycles), one of them to a bug of mine in the probe's retry that is fixed. What IS established at graph level is that the paired graph boots, configures and runs real-time with gate OPEN and comp ACTIVE on ALL N strips at every accepted point to 15 — a functional witness, labelled as one. **ONE BUG OF MY OWN WORTH THE RECORD:** process_chain.asm did not include dsp_block.h, so every "paired" build ran the SCALAR chain; it presented as the paired GATE costing 153 cycles LESS than not running it. Fixed and verified statically (33 driver calls vs 0). The biquad-pair hang SURVIVES two real fixes (`m2 = -64`, and the IRPTEN mask the dynamics kernels prove unnecessary); one stage hangs exactly as four do, so it is not the per-stage rewind — recorded, not chased further, and nothing in the graph calls it. **W0: the default image is byte-identical through all of it — chip1.ldr 45f5f2dd, chip2.ldr f6733b6d.**]   [model: opus]

model: opus

SIMD GRAPH-WIRING RUNG — pre-authorized by PW ("report back when simd
strip is measured"). The dynamics pair bit-exact with measured factors
(963f181: COMP 2.04-2.12x, GATE 2.36-2.54x) but NO strip runs paired:
the chain blocks are reused strip-by-strip, so the graph cannot hold a
pair's two strips live at once. This rung turns the projection into a
measured ceiling. Block size is now a build parameter (744b2e6), so
measure BOTH operating points — the numbers from this session are what
PW decides block 8 vs 32 with.

1. WIRE PAIRING THROUGH THE GRAPH (generator change): both strips of a
   pair hold live chain blocks simultaneously; strip-ordered chain
   becomes pair-ordered where DSP4_SIMD_DYN is on; scatter/gather stays
   inside the timed span as in the kernel measurements. Odd strip counts
   handled (last strip scalar). Bit-exactness bar: chain.py configured
   probes + negative controls (the NEGCTL discipline from 963f181), on
   the part, both chips' graphs where applicable.

2. THE BIQUAD HANG, in this session (it blocks the number that matters):
   `_bq_fx_cascade_simd` hangs the part when driven from the main loop
   with the graph configured — bisected to the routine on 08-28, timeboxed
   away. Root-cause it (the two recorded SHARC loop hazards are prime
   suspects), then RE-MEASURE the biquad pair factor against the FUSED
   cascade (the 2.39x on record predates fusion and is stale). If it
   resists beyond a reasonable timebox, land dynamics-only pairing with
   measurements and mark the biquad half with findings — do not hold the
   rung hostage.

3. MEASURE, per the standing honest rules (full-rate bar, witnessed
   stimulus, signal present AND silence controls, 786.432 AND 983.04):
   - paired strip per-class table (cycles/block and /sample);
   - ceilings at BLOCK=8 AND BLOCK=32 — four sweep points minimum
     (block x clock), ledger figures carry block size;
   - SPECIFICALLY: what pairing does to COMP's block-invariant section
     (13.5k cycles/block, 73% of the block-8 strip per 340b133) — the
     pair factor on the per-block section vs the per-sample section,
     separately. That single number decides whether a COMP block-rate
     cut is still needed after SIMD.

4. Update ledger + options paper (block-tagged rows); tasks.md status.
   Not in scope: the COMP block-rate conversion cut, the CONFIG_COMMIT
   diag-link defect, chip-2 OUTPUT_TDM/COMPRESSOR block conversion —
   all queued at the hub, do not start them.

Rules: W0 throughout; bench restored to a verified state at the end;
ladder discipline; standing traps (DO-loop branch hazards, one tty
reader, CFG_COMMIT gain witness). PW is around — report blocks promptly.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-28 (fourth session) — the graph is paired, and the numbers it was sent to build on were wrong

#### 1. THE FINDING THAT COMES FIRST: six block-32 literals survived the parameterisation

The block-8 session made block size a build parameter and proved it a pure
refactor with a byte-identical block-32 control. The control was sound and
the refactor was almost complete — but **six numbers stayed literal**, and
because each is only reachable in a block-kernel or self-test build, not
one of them could move the control image by a single byte. All six are now
derived from `DSP4_BLOCK_SIZE`:

| where | was | what it did at BLOCK=8 |
|---|---|---|
| `dsp_codegen.py::_COMP_BLK_BODY` | `lcntr = 31` | **COMP ran 1+31 = 32 samples of an 8-sample block** — 4x the work, reading 32 words from `BLK_CHAIN_A` and writing 32 to `BLK_CHAIN_B`, three slots past the end of each, over `BLK_FDR_L/R` and `BLK_TAP_TRIM` |
| `dsp_codegen.py::gen_bus_accumulators_fixed` | `r3 = 64` | `_bus_clear_all` zeroed 64 words from each of 25 bus bases where each array is 16 |
| `biquad_fx.asm::_bq_fx_cascade_simd` | `r15 = -64` | the per-stage rewind of the INTERLEAVED block; stage 2 read and WROTE 48 words before `_bqp_sig` |
| `dyn_selftest.asm` (3 sites) | `63` | the backwards diff started at word 63 of arrays whose first 16 held the data — **the paired-dynamics bit-exactness test compared untouched zeros and could not fail**, negative control included |
| `bq_selftest.asm` | `63` | the same, for the biquad diff |
| `dynst_read.py` | `/32`, `of 128` | every paired cycles/sample figure read four times too cheap |

and one that is not a literal but the same mistake: `dyn_selftest`'s
stimulus was a 64-word initialiser with block 2 starting at index 32, so at
BLOCK=8 both "blocks" came out of block 1's square wave and the test lost
the opposite-branch-arm coverage that is the whole reason block 2 exists.
It is filled at run time from `DSP4_BLOCK_SIZE` now.

**The shipping image never ran any of it.** The default build is per-sample
(`DSP4_BLOCK_KERNELS=0`) and every affected line sits behind a block-kernel
or self-test guard. The byte-identical control holds after all six fixes
and after the whole pairing change: **chip1.ldr 45f5f2dd, chip2.ldr
f6733b6d.**

Corroboration that the bus-clear fix is real and not bookkeeping: the
NODE_LIMIT=1 point fell from 10,222 to 9,022 cycles/block — 1,200 cycles,
which is exactly the 25 buses x 48 excess words the defect wrote.

#### 2. "COMP is block-invariant" is WITHDRAWN

The block-8 re-baseline's headline was that 15,856 cycles/block of the
strip is block-INVARIANT (73 % of it at block 8), that 13.5k of that is
COMP alone, and therefore that cutting COMP's once-per-block section is
worth more at block 8 than SIMD is. **All of it was the `lcntr = 31`.** A
node that does the same 32 samples of work whatever the block size measures
as block-invariant because it IS invariant. The measurement was honest; the
instrument was reading a defect.

Re-measured on the same instrument, signal present, block 8:

| | recorded 08-28 (3rd session) | **measured now** | block 32 | per sample |
|---|---|---|---|---|
| COMP | 13,870 cycles/block | **3,465** | 13,635 | **433.1 vs 426.1** |
| strip | 21,760 | **11,726** | 39,470 | 1,465.8 vs 1,233.4 |

COMP is per-sample work like everything else — 433.1 cycles/sample at block
8 against 426.1 at block 32, 1.6 % apart — and the paired-dynamics
self-test's scalar arm agrees independently at 420.0 cycles/sample/channel.
The block-8 penalty on the strip is **1.19x per sample, not 2.21x**.

The strip was read TWICE in the same sweep: limits 1→10 give 11,726 and
limits 10→20 (the second strip) give 11,859, 1.1 % apart. Every other class
reproduces its recorded figure — FILT 1,095 against 1,089, EQ+GATE 4,201
against 4,204, RTG 1,861 against 1,872 — which is what makes COMP's move
attributable to the fix and not to the instrument. **The largest remaining
block-invariant item in the strip is now RTG.**

#### 3. Wiring the graph for pairing: two pools, not a park

The kernels have paired the dynamics since 963f181. Nothing in the GRAPH ran
paired, because the chain is strip-ordered and the pool is reused strip by
strip. The scaffolding in the tree parked ONE slot and copied into and out
of it — enough for a biquad pair inside one strip's kernel, and **not**
enough for a pair of whole strips: the TAPS (trim, EQ, pre-fader) are
written in the HEAD and read by the router in the TAIL, so parking the chain
block alone leaves strip A's router reading strip B's taps.

So the ODD strip of each pair gets a whole SECOND POOL (`_blk_pool1`, 8
slots x BLOCK = 64 words at BLOCK=8) and the even strip keeps the original.
**No copying at all**: the odd strip's nodes are GENERATED against
`BLK_*_P1` and the even strip's against `BLK_*`, both pools are live across
the pair, and the paired kernels read one channel from each.

    A: IN GAIN FILT EQ        (odd strip, pool 1)
    B: IN GAIN FILT EQ        (even strip, pool 0)
    GATE pair, COMP pair      (one channel from each pool)
    A: TUBE DLY FDR RTG
    B: TUBE DLY FDR RTG

The paired dynamics run IN PLACE on each pool's `BLK_CHAIN_B`, the same net
slot movement as the scalar ping-pong (B -GATE-> A -COMP-> B), so the tails
are untouched. With `DSP4_SIMD_DYN` off every `BLK_*_P1` macro aliases its
original, which is what keeps the shipping image byte-identical while the
generator emits P1 names for sixteen strips.

Three places it could have been silently wrong, and what was done:

- **The block-rate parameter conversion is not duplicated.** Both dynamics
  classes convert once per block inside their own per-sample body behind the
  `_sample_idx == 0` guard, and the scalar COMPRESSOR block kernel already
  drives that body for sample 0 for exactly this reason. The pair driver
  does the same for both channels and hands the pair kernel the remaining
  BLOCK-1 through a new `_dsim_n`. Sample 0 is bit-identical to the scalar
  path by construction, and there is no second copy of the conversion to
  drift.
- **Declaration order is the pair interface, and GATE's was wrong for it.**
  `_gate_pair_blk` reads five consecutive parameter words and scatters four
  consecutive state words. COMP's eight were already consecutive,
  deliberately. GATE's were not — `hold` sat in the host parameter block and
  `hold_count` beside it, so a pair would have read `_buf_` as `hold` and
  written the hold count over `attq`. Both move under a paired graph,
  guarded, and **the build now CHECKS the addresses out of the .map** rather
  than trusting declaration order: GATE params 0x92711-0x92715, GATE state
  0x9270d-0x92710, COMP params 0x90705-0x9070c, all verified consecutive.
- **The fallback is net-preserving.** A pair whose channels disagree runs
  the two scalar nodes and squares the slots up, so "the dynamics section
  reads BLK_CHAIN_B and writes BLK_CHAIN_B" holds on both paths. Odd strip
  counts fall out of the same mechanism, and the 11-strip and 15-strip
  ceiling points below are odd — the last strip's dynamics ran scalar on its
  own pool in both.

**Chip 2 is not applicable**: its dynamics are `C2_GRP_COMP`,
`C2_MAIN_COMP` and friends, which do not match the strip-node pattern, have
no block kernel and have no pair. Its chain file is unchanged.

`DSP4_SIMD_GRAPH` is new and separates "the paired KERNELS are in the image"
from "the graph is WIRED for them" — they have to be separable, because with
the kernels and the 32 drivers both in, chip 1 overflows `sec_swco`.

**ONE BUG OF MY OWN, found by the measurement and worth recording because
of how it presented:** `process_chain.asm` did not `#include "dsp_block.h"`,
so `DSP4_PAIRED_GRAPH` was undefined in the one file that decides which
chain order is emitted, and **every "paired" build ran the SCALAR chain**.
It showed up as the paired GATE costing 153 cycles LESS than not running it
at all — the shape of a measurement of nothing. Fixed, and verified
statically: the paired chain now emits 33 pair-driver calls where it emitted
zero, and the scalar build still emits none.

#### 4. Bit-exactness: the kernels, with a diff that can now fail

Same self-test, at block 8, with the diff index derived and the stimulus
laid out one block apart:

| | positive | NEGCTL (pair gathers B from A) |
|---|---|---|
| COMP | **0 of 32** | **16 of 32**, maxdiff 1.87e8, first=0 |
| GATE | **0 of 32** | **16 of 32**, maxdiff 1.79e8, first=0 |

16 of 32 is exactly one channel of the pair: channel B differs on every
sample, channel A matches. That is the precise signature of the fault the
bar exists to catch, and it is the first time this test could produce it at
block 8.

Kernel factors, block 8, with the corrected divisor: **COMP 420.0 → 202.5
cycles/sample/channel (2.07x), GATE 255.0 → 105.0 (2.43x)**, against
2.04-2.12x and 2.36-2.54x measured at block 32. The factors carry.

**THE GRAPH-LEVEL BAR IS NOT MET, AND THE REASON IS THE BENCH, NOT THE
PAIRING.** `tools/pi/dsp4_pairgraph.py` and `pairgraph.sh` are in the tree
and do the right thing — configure both lanes of a pair differently, drive
one and mute the other so the two lanes sit in OPPOSITE arms of every
predicated branch, capture the main bus (the one symbol both builds share,
since the odd strip's pool moves), diff two builds, and require the NEGCTL
build to differ. Four attempts, none of them reaching a capture:

- the first two to the link — `BOOT_STAGE 0` and `link answers as CHIP 0`;
- the third to a bug of mine in the probe's own hardening: the `check_chip`
  retry constructed a SECOND `Scope` while the first still held the RDY
  GPIO line, so the request failed with `Errno 16, Device or resource busy`
  — which looks exactly like a dead part and is not. Fixed: the retry now
  re-votes on the same Scope, which is all the retry that was ever wanted;
- the fourth to the link again, by then reporting an EMPTY `BOOT_STAGE`
  after ~45 boot cycles on the day.

A fifth was run after restoring the bench and it got furthest, leaving two
precise leads rather than "the bench was flaky":

1. **The SCALAR reference capture SUCCEEDED** — `strip 1 driven, 2 muted,
   paired_build=False: 48/48 non-zero, sha256 d6360646efec1e97`, taken at
   BOOT_STAGE 7 with SPORT and DMA clean. So the probe, the injection, the
   configuration and the capture path all work. What is missing is the
   other side of the comparison.
2. **The PAIRED build would not come up to a readable state at
   `DSP4_STRIPS=2`** — repeated `BOOT_STAGE` empty or 0 — on the same run,
   minutes after the scalar build captured cleanly. **This is NOT evidence
   that the paired graph is broken**: the same paired image ran real-time
   at up to 15 strips per chip through sixteen witnessed ceiling points on
   this bench today. It is an unexplained asymmetry at this ONE
   configuration (2 strips, no clock override) and it is where to start.

Earlier attempts also showed `Scope.rd`'s paced read answering "CHIP 0"
while `dsp4_diag.py` read BOOT_STAGE 7 on the same part in the same second,
so the scope read path is a second thing worth looking at.

**What IS established at graph level**: the paired graph builds, boots,
configures and runs real-time up to 15 strips per chip, and
`dsp4_dyn_witness.py` reads gate OPEN and compressor ACTIVE on ALL N strips
at every accepted ceiling point — the paired dynamics produce correct
per-strip state on every strip, including the odd last strip that falls back
to scalar. That is a functional witness, not bit-exactness, and it is
labelled as one. **The bar itself is unfinished and the instrument to finish
it is in the tree.**

#### 5. The measured ceilings — signal present, honest 6000 blocks/s rule, channels per chip

| | 786.432 MHz | 983.04 MHz |
|---|---|---|
| block 32 (2026-08-27) | 11 | 14 |
| block 8 as recorded 08-28 (defective COMP) | 5 | 6 |
| **block 8, scalar** | **9** | **12** |
| **block 8, SIMD paired** | **11** | **15** |

Every accepted point witnessed with all N gates OPEN and all N compressors
ACTIVE; every rejection a clean miss:

    scalar 786:  8 = 5999/s   9 = 5999/s   10 = 5679/s   11 = 5234/s
    scalar 983: 11 = 6000/s  12 = 5999/s   13 = 5656/s   14 = 5297/s
    paired 786: 11 = 5999/s  12 = 5903/s   13 = 5422/s   14 = 5173/s
    paired 983: 14 = 5999/s  15 = 5999/s   16 = 5756/s   17 = 5384/s

The 12-strip paired point at 786 hit the CFG_COMMIT parameter slip on strip
1 mid-run and gainfix could not repair it on the first pass. A dead strip is
a CHEAP strip, so 5,903/s is if anything flattered — 12 is over budget
either way and the ceiling of 11 stands.

**What pairing is worth in the graph: +22 % at 786 (9 → 11) and +25 % at
983 (12 → 15).** That is less than the kernel factors alone would give,
and the difference is real work, not measurement: the pair driver runs
sample 0 of each channel through the scalar body for its block-rate
conversion, sets up pointers, and copies the compressor gain display back
per channel, and the pair kernels gather and scatter their own interleaved
park. All of that is inside the measured ceiling.

**Measured per class on the PAIR-ORDERED chain** (NODE_LIMIT counts
pair-order positions there: 8 = both heads, 9 = + the GATE pair, 10 = + the
COMP pair, 18 = the whole pair):

| | for TWO channels | scalar for two | graph factor | kernel factor |
|---|---|---|---|---|
| GATE pair | **2,284** cycles/block | 4,156 | **1.82x** | 2.43x |
| COMP pair | **4,023** | 6,930 | **1.72x** | 2.07x |

and the whole pair reads 28,147 against 32,607 for two scalar strips —
4,460 cycles/block per pair, 2,230 per channel, taking the strip from
11,726 to **9,496 (−19 %)**. The per-class parts sum to 4,779 for the pair,
7 % from the whole-pair figure, the difference being the two meters the
paired limit carries and the scalar limit does not.

**THE MODEL PREDICTS BOTH PAIRED CEILINGS.** Backing the fixed overhead out
of the SCALAR ceilings and re-solving with the paired strip gives **11.3 at
786 and 15.1 at 983, against 11 and 15 measured.** The per-class profile
and the ceiling sweeps share no arithmetic, so that is two independent
instruments agreeing.

**THE DECIDING NUMBER: 16 per chip at 983 — what a two-chip D32 split needs
— now misses by 4.2 % of the block budget.** Before this session the same
question read 6 against 16. It is a margin now, not a factor.

#### 6. The paired biquad cascade still hangs

`_bq_fx_cascade_simd` hangs the part when driven from the main loop with the
graph configured; it presents as "never reached stage 6" — the part not
answering the link while the self-test owns the main loop. **Nothing in the
GRAPH calls it**; only the self-tests do, so it does not block this rung.

Two real defects in it were found and fixed and neither cleared the hang:
the per-stage rewind `m2 = -64` (right only at BLOCK=32; at BLOCK=8 stage
two read and WROTE 48 words before `_bqp_sig`), and the IRPTEN mask around
the whole cascade — the paired DYNAMICS kernels mask nothing and rely on the
per-ISR PEYEN clear, and masking is what a self-test calling the cascade
thousands of times in a hardware loop cannot afford. `DSP4_SIMD_STRIPS`
(which carries that per-ISR PEYEN clear and the IICDI handler) now also
defaults on for a `DSP4_SIMD_PROBE` build, which previously ran SIMD kernels
with no ISR protection at all.

What the bisect says now: `DSP4_SKIP_SIMDCALL=1` boots and runs cleanly
through `_bq_pair_blk`'s interleave and scatter; **one stage hangs exactly
as four do** (new knob `DSP4_BQ_PAIR_STAGES`), so it is not the per-stage
rewind or the state advance; and removing the interrupt mask does not change
it. That leaves the sample loop and the MODE1 entry/exit. The stale 2.39x
biquad pairing figure is therefore still unreplaced.

#### 7. Bench

Restored and verified. The default shipping image rebuilt **byte-identical
— chip1.ldr 45f5f2dd, chip2.ldr f6733b6d** — and was flashed; both parts
boot and run: chip 1 MAGIC 0xD5B40001, BOOT_STAGE 5, **FRAME_COUNT
advancing 576,097 → 602,062 → 627,979 across three reads with TICKS
advancing with it**; chip 2 the same at BOOT_STAGE 5 with its own frame
count; matrix-app active. The CPLD was never touched — everything this
session went the firmware route.

The frame counts are quoted as a SEQUENCE on purpose. The first read of
chip 1 after this flash returned `MAGIC 0x00000000`, which the tool
correctly refuses to interpret, and a restore script that had stopped there
would have reported a dead part. Re-reading gave a healthy one three times
running. **One read is not a verification on this link** — which is the
cheap version of the lesson the graph-bar attempts above taught expensively.

Two instrument occurrences logged again: `dsp4_diag.py --chip 2` answering
`CHIP_ID 1` (both parts confirmed alive by their own frame counts), and the
CFG_COMMIT parameter slip on roughly a third of boots, which `gainfix.py`
repairs over the link before any point is scored.

#### 8. What is NOT in this session

- Ceilings at BLOCK=32 with the corrected code. The block-32 rows above are
  from 2026-08-27 and are unaffected by the COMP fix (at BLOCK=32 the
  defective loop count was the right one), but the PAIRED block-32 ceiling
  was not measured.
- Silence controls at block 8. The 8 and 11 recorded earlier on 08-28 were
  measured with the defective COMP and are withdrawn; they were not
  re-measured.
- The EQ point of the per-class profile (limit 4) lost its witness three
  times to the link fault, so EQ and GATE are carried as a combined 4,201
  cycles/block, which is 0.07 % from the sum of their separately measured
  figures.
- Digital latency: still derived, not measured. The blocker is unchanged
  (the boot config sets no Pi-in-to-Pi-out route).

## HUB DISPATCH 2026-08-28 13:26Z — block-8 parameterization + in-kernel meter rebuild + re-baseline   [status: 🟢 done — **BLOCK SIZE IS A BUILD PARAMETER AND 8 IS THE OPERATING POINT; THE METER IS REBUILT AND BIT-EXACT AGAINST A REFERENCE THAT DID NOT EXIST; THE BLOCK-8 CEILINGS ARE MEASURED AND THEY COST A FACTOR OF 2.2.** Parameterization is proven a PURE REFACTOR: with BLOCK set back to 32 the build reproduces the previous images byte for byte (chip1.ldr a2fcda81, chip2.ldr 30291013), so block size is the only variable. One source (dsp_codegen.BLOCK) feeds a generated dsp_block.h for the assembler and C, and a generated dsp4_block.py for the bench tools, so a verdict can never be scored against a block size the image was not built with; the real-time bar is now 48000/BLOCK with the thresholds as fractions of it instead of 1450/1500 literals. **THE METER: three instructions per sample, no memory traffic beyond the source read, and one fold per block in 64-bit Q8.56 state** — max, min, and an exact sum of squares in the MRF, folded into a one-pole RMS window and a peak-hold whose coefficients are generated FROM THE BLOCK RATE (which is exactly the third recorded defect: a constant derived for 1500 blocks/s applied per sample). **THE BAR WAS MET ON THE PART: ms64 EXACT, both pk64 words EXACT, float readback exact, negative control against the block-32 coefficients correctly rejected.** The peak is compared word-wise because it sits in a two-state limit cycle stepping every 167 us while a diag peek takes a millisecond — the first run of the test read lo from one phase and hi from the other and called it a mismatch, which was the test being wrong. Three of the four recorded defects are gone by construction; **the fourth (_mtr_gr never written) is NOT a numerics bug and cannot be fixed in this repo** — dsp.csv names gate_gr and comp_gr in the meter's taps but carries no ids for them, so it needs an mx26 contract change. **A FIFTH DEFECT FOUND: every meter read BLK_CHAIN_B unconditionally, and on chip 2 that is not its source** — FADER_PAN reads BLK_CHAIN_B and writes BLK_CHAIN_A, OUTPUT_TDM and COMPRESSOR never touch the pool, so twenty-one chip-2 meters were metering another node's signal. Sources are now resolved per meter from the graph. **THE RE-BASELINE, AND IT IS THE UNCOMFORTABLE PART: block 8 costs 2.2x the cycles per sample and the ceilings fall with it.** Measured, honest 6000/s rule, per chip: signal-present **5 at 786 and 6 at 983** (was 11 and 14 at block 32); silence **8 and 11** (was 15 and 20). Two independent methods agree on the strip to 0.17% (per-class profile 21,760 cycles/block, ceiling-slope 21,798) and the slope model predicts both signal ceilings (5.03 and 6.52). **THE CAUSE IS ONE NODE.** A two-point fit of the same code at both block sizes — today's block-32 control reproduces this morning's strip to 0.1%, which is what makes the fit legitimate — puts 15,856 cycles/block of the strip in BLOCK-INVARIANT work (40% of the strip at block 32, 73% at block 8), **and 13.5k of that 15.9k is COMP**, whose cost is block-invariant to within measurement error (13,484 at block 32, 13,870 at block 8). The fabric, by contrast, is 97.6% per-sample work and scales almost perfectly. **So the block-8 penalty is not diffuse and it is not the price of latency: it is the compressor's once-per-block section, and cutting it is worth more at block 8 than SIMD is.** **LATENCY WAS NOT MEASURED and the blocker is pre-existing**: the DSP does not route Pi input to a Pi-visible output under the boot config (routes are host-written matrix parameters), and dsp4_passthru.py's ALSA device names do not match this Pi. What IS measured is the block rate — FRAME_COUNT 5999–6000/s, so the block period is 166.7 us against 666.7 us — and the ring geometry and ping-pong depth are unchanged by construction, only the row length. The ~23 samples / 0.48 ms figure therefore stands as a derivation, not a measurement, and is labelled that way. **A SEPARATE FAILURE FOUND AND EXONERATED: the per-sample (shipping) image cannot answer the diag link after CONFIG_COMMIT — and this is PRE-EXISTING.** It presents as "response out of step ... neither is the echo". It reproduces at block 8, at block 16, at block 32, with the meters removed entirely, AND **on the exact bytes that shipped (a2fcda81) reflashed from a saved copy** — so it is not block size, not the meter, not this session. It needs its own dispatch. **Bench restored and verified: the new default block-8 images (chip1.ldr 45f5f2dd, chip2.ldr f6733b6d) flashed, both parts booted to BOOT_STAGE 5 with frames arriving, matrix-app started, all three MCUs verified 17:57:23 ON THE FIRST RESTART.** CPLD never touched. The previous shipping md5s a2fcda81/30291013 are superseded: block 8 changes the image by design.]   [model: opus]

model: opus

BLOCK-8 + METER-REBUILD SESSION — executes the two PW rulings recorded
2026-08-28 at the top of tasks.md (block size 8 working operating point;
meter rebuilt in-kernel). The sequencing gate is met: SIMD landed at 32
(963f181) so lever attribution against the 32-baseline ledger is clean.
Bench is free. Both items rewrite the generated kernel loop — that is why
they share one session; do them in this order:

1. BLOCK SIZE AS A CLEAN BUILD PARAMETER first (per the block-8 ruling):
   generator loop counts, DMA ring/2D geometry, scatter/gather, BLK_*
   sizing, the `_sample_idx == 31` guard class, verdict rate 1500→6000
   blocks/s in every harness/verdict tool. Nothing hardcodes 32 when this
   step is done.

2. METER REBUILD IN-KERNEL per the ruling's agreed design: per-sample
   multifunction line — multiplier accumulates x² into RMS state while
   the ALU does peak MAX on the in-register post-trim value; per-block —
   one-pole RMS window fold (300 ms-class coefficient) + block-max into
   peak-hold/decay. Target ≈2 cycles/sample/channel vs ~20 today.
   Ride-alongs from the same ruling, all in this session:
   - GAIN = 1 MAC un-gated: meter reads the register, not the post-trim
     block; fold the router's post-trim pickoff into crosspoint
     coefficients per Bible ch 10 doctrine — VERIFY the fold, then the
     round/store dies (−17 cycles/sample).
   - The four recorded meter numerics defects fixed BY CONSTRUCTION
     (native Q4.28, true windowed RMS, sample-accurate peak).
   - Bit-exactness bar: golden-reference tests for RMS window + peak
     against fixed_ref (write new reference functions as needed) — NOT
     just A/B against the defective meter.

3. BLOCK-8 RE-BASELINE last: capacity sweeps at 786 AND 983 MHz, silence
   AND signal, honest 6000 blocks/s rule; digital latency MEASURED on the
   part (prediction ~23 samples ≈ 0.48 ms); per-class costs re-measured —
   per-block hoisted work now runs 4x per sample and that concentration
   is measured, not estimated. Every ledger/options-paper figure carries
   its block size from now on; existing figures stay labeled block-32
   until superseded.

4. Update the ledger + options paper with the block-8 numbers and the
   meter/GAIN recoveries; tasks.md statuses (the two ruling paragraphs
   can be marked executed with pointers to the evidence).

Rules: ladder discipline — if the meter fold or the GAIN pickoff fold
resists verification, land block-8 parameterization + re-baseline and
mark the resisting item with findings rather than holding the session
hostage; standing traps; PW is around today — report blocks promptly.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-28 (third session) — block 8, the meter, and what block 8 costs

#### 1. Block size is a build parameter, and the proof is a byte-identical control

`tools/dsp/dsp_codegen.py::BLOCK` is the single source. The generator
writes it to `src/dsp_block.h` (`DSP4_BLOCK_SIZE` / `_HALF` / `_SHIFT` /
`_F32` / `_RATE`, plus the meter coefficients that are functions of the
block rate) for the assembler and the C DMA configuration, and to
`tools/pi/dsp4_block.py` for the bench tools. Both are generated, so a
verdict cannot be scored against a block size the image was not built
with, and the harness scripts stage both onto the bench beside the .ldr.

What is now derived from that one number: every block-length hardware
loop in the generated kernels and the two-samples-per-iteration fused
kernels (BLOCK/2); slot and buffer arrays, the shared block pool and the
64-bit bus accumulators; the DMA ring geometry (lane offsets and
`region_words` in the generated `lane_config.c`, XCNT/YMOD and the
descriptor word count in `dma_config.c`); the ramp plane (`FRAME_MS`, the
profile frame tables, the per-BLOCK ramp step and its float scale, and
spi_handler's block-frames-to-samples shift); the scope stimulus fills;
the hand-maintained `src/lib` kernels; and the real-time bar in
`dsp4_audio_verdict.py`.

**THE CONTROL IS THE POINT.** With `BLOCK` set back to 32 the build
reproduces the previous images byte for byte — **chip1.ldr a2fcda81,
chip2.ldr 30291013** — so this is a pure refactor and block size is the
only variable in everything below. It was re-run after every later
generator change and held both times.

At BLOCK=8 the block rate is confirmed end to end on the part:
**FRAME_COUNT 5999–6000/s** against 1500 before, with the SPORT still
running at 48 kHz. The DMA geometry change is right.

#### 2. The meter, rebuilt

Per sample, inside the node's own block kernel, touching no memory beyond
the source read:

```
    r8 = max(r8, x);            running maximum
    mrf = mrf + x * x (ssi);    exact sum of squares, 80-bit
    r9 = min(r9, x);            running minimum
```

Peak comes from max and min rather than `abs(x)` because MAX and MIN are
one ALU op each and an abs would be a third on top of a max; the sign
fold happens once per block. Then one fold (`src/lib/meter_fx.asm`).

**The state is 64-bit Q8.56 and that is not an indulgence.** Both
one-poles have time constants of hundreds of blocks, so the per-block
correction is ~1e-4 of the state; held in Q4.28 it rounds to zero below
about -50 dBFS and the meter simply stops moving — a dead zone in the
middle of the useful range. In Q8.56, which is what the multiplier
produces anyway, the correction is one exact MAC and the smallest step is
2^-56. The block mean costs no divide: BLOCK is a power of two, so it is
part of the same shift that takes Q8.56 to Q4.28.

#### 3. The bar: golden reference, not A/B

`fixed_ref.meter_block` is new — the meter had no reference model at all,
which is how four defects survived. `tools/pi/dsp4_mtr_verify.py` drives
the DSP4_PROFILE_SIGNAL square wave, which makes every block identical
and the recurrence's limit set small and exact, and compares the
**fixed-point state**:

| | read on the part | verdict |
|---|---|---|
| `ms64` | 18014398509513833 | **EXACT** |
| `pk_lo` | 0x00000000 / 0x38000000 | **EXACT** |
| `pk_hi` | 0x007FFBE7 / 0x00800000 | **EXACT** |
| peak / rms float | 0.5 / 0.5 | relative error 0 / 0 |
| negative control (block-32 coefficients) | | **correctly rejected** |

Every word is exactly an integer the reference produces from a zero state
under the same stimulus. **The peak is compared word-wise, and the reason
is worth keeping:** it sits in a two-state limit cycle that steps once per
block (167 us) while a diag peek takes about a millisecond, so the two
halves of `pk64` are necessarily read in different phases. The first run
of the test read `lo` from the decay state and `hi` from the latch state
and reported a mismatch — the test was wrong, not the meter, and a test
that cannot tell those apart is not testing anything.

#### 4. The four defects, and a fifth

1. **Q4.28 read as an IEEE float** — gone. The path is native Q4.28 and
   the only float is the readback convert.
2. **RMS never advanced** (the new-peak branch returned first) — gone.
   There are no branches in the per-sample line at all.
3. **Decay 32x fast** — gone by construction. `DSP4_MTR_ALPHA_Q` and
   `DSP4_MTR_BETA_Q` are generated from the BLOCK RATE, so they move when
   the block moves. That defect could only exist because the rate was
   written into the constant by hand.
4. **`_mtr_gr` never written** — **NOT fixed, and it is not a numerics
   bug.** The meter's `taps` parameter names `gate_gr` and `comp_gr` but
   dsp.csv carries no ids for them, so there is nothing to read without
   inventing a naming convention between MTR_nn and GATE_nn. **That is an
   mx26 contract change, not a spoke fix.**

**FIFTH, found here: the source tap was wrong on chip 2.** Every meter
read `BLK_CHAIN_B` unconditionally. On chip 1 that is GAIN's output and
correct; on chip 2 FADER_PAN *reads* BLK_CHAIN_B and writes BLK_CHAIN_A,
and OUTPUT_TDM and COMPRESSOR never touch the pool at all — so **21
chip-2 meters were metering another node's signal.** Sources are now
resolved per meter from the graph (GAIN → BLK_TAP_TRIM, FADER_PAN →
BLK_CHAIN_A) and a source that publishes no block falls back to its
scalar `_buf_` — one sample per block, correctly converted, with the
limitation stated in the generated node itself. Fixing those 21 properly
means block-converting OUTPUT_TDM and COMPRESSOR on chip 2.

#### 5. What the meter rebuild is worth, honestly

Full graph, signal present, block 8: **721,205 cycles/block with the new
meter against 722,354 with the old — 1,149 cycles/block, 0.16%.**

The ruling projected ~21k. That projection was a BLOCK-32 number and both
sides of it scale with the block: the old meter's per-sample cost fell by
4x when the block did, and the new meter's per-block fold now runs 4x as
often per sample. **At block 8 the rebuild is close to cost-neutral.** Its
value here is correctness — four defects, a fifth found, and a reference
model that did not exist — plus un-gating GAIN = 1 MAC. It is not a
capacity lever at this block size, and it should not be quoted as one.

#### 6. The re-baseline, and the number PW needs

Measured on the part, honest full-rate rule (6000 blocks/s), channels per
chip, `DSP4_STRIP_FUSED=0`:

| | 786.432 MHz | 983.04 MHz |
|---|---|---|
| signal present, **block 8** | **5** | **6** |
| signal present, block 32 | 11 | 14 |
| silence, **block 8** | **8** | **11** |
| silence, block 32 | 15 | 20 |

Every point witnessed: gate OPEN and compressor ACTIVE on all N strips
for the signal rows, gate SHUT and comp unity for the silence rows, and
strip 1's GAIN coefficient at 1.0f. 6 at 983 reads 5999/s and 7 reads
5645/s; 5 at 786 reads 5999/s and 6 reads 5163/s. The 786 silence row is
called at 8 because 9 reads 5802/s — `audio_verdict.py` labels that
REAL_TIME because it clears 97 %, and by the honest rule it is dropping
blocks.

**Two independent methods agree on the strip to 0.17 %**: the per-class
profile gives 21,760 cycles/block and the 983 sweep's pass-rate slope
gives 21,798, and they share no arithmetic. The slope model predicts both
signal ceilings (5.03 and 6.52).

#### 7. Where the 2.2x goes, and it is one node

Per class, signal present, cycles/block (the full table is in
`dsp4-function-costs.csv`, and every figure there now carries its block
size):

| class | block 32 | block 8 | per sample, 32 → 8 |
|---|---|---|---|
| GAIN | 566 | 189 | 17.7 → 23.6 |
| FILT | 3,946 | 1,089 | 123.3 → 136.1 |
| EQ | 7,934 | 2,126 | 247.9 → 265.8 |
| GATE | 7,946 | 2,078 | 248.3 → 259.8 |
| **COMP** | **13,635** | **13,870** | **426.1 → 1,733.8** |
| RTG | 2,263 | 1,872 | 70.7 → 234.1 |
| **strip** | **39,470** | **21,760** | **1,233.4 → 2,719.9** |

**Today's block-32 control reproduces this morning's strip to 0.1 %**
(39,470 against 39,417), which is what makes a two-point fit of the same
code legitimate. That fit puts **15,856 cycles/block of the strip in
BLOCK-INVARIANT work** — 40 % of the strip at block 32, **73 % at block
8** — and **13.5k of those 15.9k are COMP alone**, whose cost is
block-invariant to within measurement error (13,484 at block 32, 13,870
at block 8, 2.9 % apart, measured on the same instrument the same day).

The fabric is the opposite: fitted at 1,908 cycles/block invariant plus
2,466 cycles/sample, i.e. **97.6 % per-sample work**, and it scales almost
perfectly with the block (80,824 → 21,635 at 983).

**So the block-8 capacity loss is not the diffuse price of a shorter
block. It is the compressor's once-per-block section, and at block 8 that
one section is worth more than SIMD.** `DSP4_COMP_NOCVT=1` drops COMP from
13,870 to 5,228 cycles/block, which bounds the parameter conversion at
≤8.6k — but NOCVT also leaves the sample path running on unconverted
parameters and therefore cheapens it too, so treat 8.6k as an upper bound
on the conversion and a lower bound on what is recoverable. **Isolating
and cutting it is the next rung, ahead of anything else on the ledger.**

One consequence for the ledger: the SIMD pairing figures (GATE 106.8,
COMP 204.2 cycles/sample) were measured at block 32 on the SAMPLE path.
At block 8 those classes are dominated by block-invariant work, so
pairing buys much less. They are not carried forward.

#### 8. Latency: NOT measured, and the blocker is not new

The block PERIOD is measured — FRAME_COUNT 5999–6000/s, so 166.7 us
against 666.7 us — and the ring geometry, the ping-pong depth and the
core sequence are unchanged by construction; only the row length moved.
The ~23 samples / 0.48 ms figure therefore stands as a **derivation from
the measured 93-at-block-32 pipeline, not a measurement**, and is
labelled that way everywhere.

Two things block the end-to-end measurement, and the first is recorded
from an earlier session: **the DSP does not route Pi input to a
Pi-visible output under the boot config** — routes are host-written matrix
parameters that nothing in boot config sets — and `dsp4_passthru.py`'s
ALSA device names do not match this Pi (`hw:dsp4pcm,0/1`). Attempted on a
real-time block-8 build and both bit. **Reported rather than worked
around: it needs the routing work, not this session.**

#### 9. A separate failure, found and then exonerated

**The per-sample (shipping) image cannot answer the diag link after
CONFIG_COMMIT.** It presents as `response out of step ... neither is the
echo`, with the core running underneath.

It looked like block-8 fallout and it is not. It reproduces at block 8,
at block 16, at **block 32**, with the meters removed entirely
(`DSP4_MTR_OFF=1`), and — the control that settles it — **on the exact
bytes that shipped, `chip1.ldr a2fcda81`, reflashed from a saved copy.**
So it is not block size, not the meter, not this session. It is
pre-existing and it needs its own dispatch.

The one change made while chasing it is kept because it is right on its
own terms: the per-sample loop's SPI poll mask is now
`(DSP4_BLOCK_SIZE/4)-1`, four polls per pass at any block size, where a
bare 7 gave four at block 32 and one at block 8. At block 32 it still
expands to 7. It did **not** fix the failure above and `main.asm` says so.

#### 10. Bench

Default block-8 images **chip1.ldr 45f5f2dd, chip2.ldr f6733b6d** built,
flashed and verified: both parts boot to BOOT_STAGE 5 with frames
arriving, matrix-app started, **all three MCUs verified 17:57:23 on the
FIRST restart**. CPLD never touched. The previous shipping md5s
a2fcda81/30291013 are superseded — block 8 changes the image by design,
and the byte-identical control above is what shows the change is only the
block size plus the meter.

One instrument quirk logged again: `dsp4_diag.py --chip 2` sometimes
answers `CHIP_ID 1`. Both parts were confirmed alive by their own frame
counts.

**PW RULING 2026-08-28 (~13:00): WORK WITH BLOCK SIZE 8 FOR NOW.** [EXECUTED 2026-08-28 — see the outcome above. Block size is a build parameter (dsp_codegen.BLOCK -> dsp_block.h + dsp4_block.py), proven a pure refactor by a byte-identical block-32 control, and the block-8 re-baseline is measured. The predicted latency is NOT measured: the route the measurement needs does not exist yet.] Target
digital latency ~23 samples ≈ 0.48 ms (from the measured 93-at-block-32
pipeline ratio), leaving room under 1 ms for converter group delay. This
supersedes the "block stays 32" line in the 08-24 fusion dispatch (that
line vetoed block-64 for capacity; the veto on 64 stands). Consequences to
handle in the NEXT dispatch after SIMD lands (SIMD finishes at 32 so its
lever attribution stays clean against the 32-baseline ledger):
- If block size is not yet a clean build parameter, MAKE it one first
  (generator loop counts, DMA ring/2D geometry, scatter/gather, BLK_*
  sizing, the `_sample_idx == 31` class of guards, verdict rate 1500→6000
  blocks/s in every harness/verdict tool).
- Then the block-8 re-baseline: capacity sweeps at 786 AND 983, silence +
  signal, honest 6000/s rule; measured digital latency on the part
  (predict ~23 samples); per-class costs re-measured (per-block hoisted
  work runs 4x per sample — the concentration is the number to measure,
  not estimate).
- Every ceiling in the ledger/options paper is a block-32 number until
  the re-baseline lands; quote block size with every figure from now on.

**PW RULING 2026-08-28 (~13:15): THE METER RULING IS MADE — REBUILD
IN-KERNEL** [EXECUTED 2026-08-28 — rebuilt, bit-exact against a new fixed_ref.meter_block with a negative control, three of the four defects fixed by construction and a fifth found. TWO PARTS NOT DONE and both are recorded above: _mtr_gr needs an mx26 contract change, and GAIN = 1 MAC is still gated — not on the meter any more, but on the gain-into-biquad fold, which is derived but unimplemented and is NOT bit-exact (it deletes a rounding), so it needs a numeric-spec amendment. The ~21k recovery was a block-32 figure; at block 8 the rebuild measures 1,149 cycles/block, near cost-neutral.] (retire and naive-decimate are off the table). Design agreed
with the hub: per-sample multifunction line inside the fused kernel —
multiplier accumulates x² into the RMS state while the ALU does peak MAX
on the in-register post-trim value (~1 cycle/sample/channel, zero memory
traffic); per 8-sample block — one-pole RMS window fold (300 ms-class
coefficient) + block-max into peak-hold/decay (~1 cycle/sample
equivalent). Target ≈ 2 cycles/sample/channel vs ~20 today (~590
cycles/sample recovered at 32 channels). CONSEQUENCES THIS UNLOCKS, all
to land in the same session: GAIN = 1 MAC (meter stops tapping the
post-trim BLOCK — reads the register; FILT already folded; fold the
router's post-trim pickoff into crosspoint coefficients per Bible ch 10
doctrine — verify, then the round/store dies, −17 cycles/sample); the
four recorded meter numerics defects are fixed BY CONSTRUCTION (native
Q4.28, true windowed RMS, sample-accurate peak); the remaining ~21k
fabric meter cost collapses. Bit-exactness bar: golden-reference tests
for RMS window + peak against fixed_ref (new reference functions as
needed), not just A/B vs the defective meter. SEQUENCING: this rides in
the SAME session as block-8 parameterization (both rewrite the generated
kernel loop) — dispatch after SIMD lands.

## HUB DISPATCH 2026-08-28 11:47Z — SIMD pairing on the fused strip — dynamics first (32-in-one lever)   [status: 🟢 done — **THE DYNAMICS ARE PAIRED, BIT-EXACT ON THE PART, AND MEASURED: COMP 412.5 → 195.0–202.5 cycles/sample/channel (2.04–2.12x) and GATE 247.5 → 97.5–105.0 (2.36–2.54x)**, with the pair's gather and scatter INSIDE the timed span and no numeric deviation anywhere in the sample path — ndiff **0 of 128** for both, twice, maxdiff 0. **THE NEGATIVE CONTROL IS THE POINT:** the fusion session's bar was that a pair which quietly computes channel N twice must not pass, so `DSP4_SIMD_NEGCTL` gathers channel B from channel A's pointers and the same test then reports **64 of 128 differing, first=0, maxdiff 2.1e8** for COMP and GATE alike — the diff detects exactly the fault the bar names. Every channel-dependent quantity differs between the two lanes (stimulus, attack, release, threshold, ratio, makeup, parallel blend, knee, range, hold) and block 2 puts them in OPPOSITE arms of every predicated branch: A silent on the compressor's unity path with its gate closing into hold, B at −24 dBFS on the SOFT knee with its gate held open, A's knee HARD where B's is soft. **WHAT MADE IT POSSIBLE, and it is three facts about this core, not effort:** (1) a branch takes PEx's condition for BOTH units, so every data-dependent branch in the dynamics — the envelope's attack/release select, the compressor's unity/hard/soft split, exp2's three-way shift, the gate's open/hold/close ladder — is rewritten as per-unit CONDITIONAL COMPUTE, building the alternative value BEFORE the compare that selects it; (2) a data access reads two CONSECUTIVE words, so per-channel operands are interleaved and shared constants are DOUBLED — the log2/exp2 coefficients now generate a `_log2_poly_dup`/`_exp2_poly_dup` twin from the same fixed_ref integers; (3) **the TABLE forms of log2/exp2 cannot be paired at all** — a table lookup is a gather at two indices and the DAGs are shared — so SIMD dynamics and `DSP4_DYN_TABLES=1` are mutually exclusive and the assembler now says so. **COST OF THE LAYOUT DECISION, stated before it was wired:** gather/scatter into a private interleaved park rather than repartitioning the block pool into 16 pairs — 156 words of DM total, ~4.6 cycles/sample/channel of copying, and it leaves the pool, the node buffers and every other kernel untouched. That overhead is inside every number above. **HOW MUCH OF THE >2x IS SIMD:** not all of it. The paired kernels also hoist the four `_comp_cgp` words into registers where the scalar re-reads them per sample, so a scalar block kernel could recover part of the margin above 2.0x without any pairing. The honest reading is 'pairing delivers essentially the full 2x on the dynamics, plus a little'. **WHAT THAT DOES TO THE STRIP, as arithmetic on measured parts and NOT as a measured strip:** GATE 252.1 → 106.8 and COMP 416.6 → 204.2 at the conservative ends, so 668.7 → 311.0 and the strip 1,098.8 → **741.1 cycles/sample, −32.6 %**. Scaling the measured fused ceilings by that gives **18.8 at 786 and 24.2 at 983** — projections, recorded as projections. **NO CEILING WAS RE-MEASURED, because no strip runs paired: the graph is not wired for pairing and wiring it is a generator change (the chain is strip-ordered and BLK_CHAIN_A/B are reused strip by strip, so a pair needs both strips' blocks live at once).** That is where SIMD stops today and it is the next rung. **WHERE THE BIQUADS STOPPED, and this matters because the 2.39x on record is now known to be stale:** that figure was measured against the PRE-fusion cascade, which fusion then made 32 % cheaper, so the pairing factor on the cascade the graph actually runs is an open number. Re-measuring it failed: **`_bq_fx_cascade_simd` hangs the part** when driven from the main loop with the graph configured — bisected to that routine and not to its wrapper by `DSP4_SKIP_SIMDCALL=1`, which boots and runs cleanly through `_bq_pair_blk`'s interleave and scatter. Not chased further, per the hub's timebox. What WAS gained: the fused biquad SCALAR baseline is re-measured on this instrument at **165.0 cycles/sample/channel for 4 stages and 82.5 for 2**, against sigprofile's 168.5 (EQ) and 84.1 (FILT) — 2 % apart. **THE CALIBRATION IS WHY ANY OF THIS IS QUOTABLE:** the self-test's scalar arm is a second instrument that shares no arithmetic with sigprofile.sh, and it reproduces the fused per-class table to within 1–3 % on all four classes it can see (COMP 412.5 vs 416.6, GATE 247.5 vs 252.1, 4-stage 165.0 vs 168.5, 2-stage 82.5 vs 84.1). GAIN and FDR were not attempted: 1.6 % and 1.9 % of the strip, both already ~1 instruction/cycle. DLY and RTG remain unpairable. **W0: the default image is byte-identical — chip1.ldr a2fcda81, chip2.ldr 30291013**, the same md5s the fusion session recorded, with the generator change and 1,200 lines of new ASM in the tree; `DSP4_SIMD_DYN` and `DSP4_STRIP_FUSED` both stay default 0. Bench restored to those images and verified: booted, matrix-app active, **all three MCUs verified 13:43:47 on the FIRST restart** (logged as a counter-occurrence to the second/third-restart pattern). CPLD never touched. **One bench-instrument limit found and written down:** the self-test owns the main loop while it runs and the main loop is what drains the SPI2 request FIFO — at 8192 iterations the arms total ~700 ms of link silence and the response stream comes back permanently out of phase, so the iteration count is capped at 2048 (~180 ms) and the price is ±1 tick quantisation, which is why the factors above are quoted as ranges from repeated runs rather than as single numbers.]   [model: opus]

model: opus

SIMD PAIRING on the fused strip — options-paper item B, the 32-in-one
lever, with the fusion session's item-4 map (08-28 block) as the brief.

The measured starting point: fused strip 1,098.8 cycles/sample signal-
present; ceilings 12@786 / 16@983 per chip. GATE+COMP is 61% of the strip
(GATE 248.3 + COMP 426.1) — **SIMD must pair the dynamics to matter**;
biquad-only pairing caps at ~11%. DLY+RTG (130.3, 12%) are unpairable.
The projection TO TEST, not to claim: 2.39x (measured on a biquad pair)
across the pairable remainder puts the strip near 535 cycles/sample =
33 channels at 983 — 32-in-one with margin. 983 is confirmed-legal:
PW read U5/U6 = KSWZ10 (1 GHz grade) on 08-24.

Approach:
1. Data layout first: paired-channel operands through the fused kernel
   (channel N and N+1 resident in the paired register sets). State the
   layout decision and its DM cost in the block before wiring.
2. Wire SIMD through the pairable classes IN COST ORDER: COMP, GATE
   (the 61%), then EQ/FILT biquad cascades, GAIN/FDR. Per class: measure
   the paired cost on the part, bit-exact proof per the fusion session's
   bar (scalar-vs-paired self-test with DIFFERENT data per channel — a
   pair that computes channel N twice would pass identical-data tests).
3. The dynamics' log2/exp2 polynomials and envelope state are per-channel
   — if true pairing stalls on divergent branches, measure the honest
   cost and say what caps it; a partial SIMD strip with measured numbers
   beats a claimed full one.
4. Re-measure ceilings at 786 and 983, silence + signal, honest 1500/s
   rule. Update the cost model CSV and the ledger.
5. DSP4_STRIP_FUSED stays default 0; SIMD behind its own flag likewise —
   shipping image byte-identical throughout, proven per W0.

Known traps now written down (respect them): DO-loop last-three-
instruction rule; conditional branch onto a loop end hangs the core with
the diag ISR still answering (presents as firmware that never ran);
CFG_COMMIT header-word slip on strip 1 (use sigprofile.sh's per-point
gain witness); matrix-app may need up to three restarts to verify all
MCUs (log occurrences). Bench restored to shipping verified at the end;
hand-back per ladder rules if pairing stops converging — land the
largest measured bit-exact subset.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-28 (second session) — SIMD pairing: the dynamics, measured

#### What landed

`src/lib/dyn_simd_fx.asm` (new, hand-maintained) — the dynamics for two
channels in one instruction stream: `_polyq_simd`, `_log2q_simd`,
`_exp2q_simd`, `_mrf_rns28_simd`, `_compgain_simd`, and the two block
kernels `_comp_pair_blk` and `_gate_pair_blk`. Behind `DSP4_SIMD_DYN`,
default 0. `src/lib/dyn_selftest.asm` (new) is the acceptance and the
instrument; `dynst.sh` / `dynst_run.sh` / `dynst_read.py` drive it.

#### The measured result

| | scalar c/s/ch | paired c/s/ch | factor | ticks (2048 iterations) |
|---|---|---|---|---|
| COMP | 412.5 | 195.0 – 202.5 | **2.04 – 2.12x** | 55 vs 26–27 |
| GATE | 247.5 | 97.5 – 105.0 | **2.36 – 2.54x** | 33 vs 13–14 |
| cascade, 4 stages | 165.0 | — | — | 22 |
| cascade, 2 stages | 82.5 | — | — | 11 |

Per CHANNEL, gather and scatter inside the span, three runs. The spread is
tick quantisation on the shorter arm, not scatter: every scalar arm read
the same tick count every time.

**Bit-exact, both classes, 0 of 128 samples differing, maxdiff 0** —
two consecutive blocks per channel so envelope, gain, target and hold
count have to survive the park's gather and scatter, and a block-boundary
persistence fault cannot hide.

**The negative control fails the way it must.** `DSP4_SIMD_NEGCTL=1`
gathers channel B from channel A's pointers — the pair then computes one
channel twice, which is precisely the fault the fusion session's bar
names and precisely what an identical-data test cannot see. The same diff
reports **64 of 128 differing, first=0, maxdiff 210,729,160 (COMP) and
394,251,093 (GATE)**.

#### The calibration, and why the numbers are quotable

The self-test's scalar arm is a second instrument. It shares no arithmetic
with `sigprofile.sh` — a 1 kHz tick over 2048 iterations against
TCOUNT/`_proc_cyc` on a `DSP4_NODE_LIMIT` prefix cut — and it reproduces
the fused per-class table on all four classes it can reach:

| class | sigprofile (fused) | self-test scalar | apart |
|---|---|---|---|
| COMP | 416.6 | 412.5 | 1.0 % |
| GATE | 252.1 | 247.5 | 1.8 % |
| EQ (4 stages) | 168.5 | 165.0 | 2.1 % |
| FILT (2 stages) | 84.1 | 82.5 | 1.9 % |

#### The three facts about this core that shaped the code

1. **A branch takes PEx's condition for both units.** Every data-dependent
   branch in the dynamics is rewritten as per-unit CONDITIONAL COMPUTE:
   the envelope's attack/release select, the compressor's
   unity/hard-knee/soft-knee split, `exp2`'s three-way shift, and the
   gate's open/hold/close ladder. The trap that governs the whole idiom is
   that an ALU op between `comp` and the conditional move overwrites the
   flags, so every alternative value is built BEFORE the compare that
   selects it — the same rule the biquad pair's saturation follows.
2. **A data access reads two consecutive words.** Per-channel operands are
   interleaved; shared constants are DOUBLED. The log2/exp2 coefficients
   therefore gained a generated twin, `_log2_poly_dup` / `_exp2_poly_dup`,
   emitted from the same `fixed_ref` integers so there is still one source
   for the numbers.
3. **The TABLE forms of log2/exp2 cannot be paired at all.** A table
   lookup is a gather at two different indices and the DAGs are shared —
   one address per access, whatever PEYEN says. Only the polynomial forms
   pair, which is what `DSP4_DYN_TABLES=0` (the default) already selects;
   `DSP4_SIMD_DYN` with tables on is now an assembler error rather than a
   silent wrong answer.

Two smaller ones worth keeping. `_compgain_simd` cannot fold the unity
case into the exponent — `exp2q(0)` is `0x0FFFFFE5`, not the `0x10000000`
the scalar's unity path returns — so unity is carried as a per-unit flag
in r7 and applied AFTER exp2, and paying for that register is why the COMP
loop reloads the release alpha from the park each sample. And interrupts
are NOT masked around these kernels: the per-ISR PEYEN clear already in
the tree is the systemic fix, and masking around a whole block of
dynamics would be a ~40 us blackout against a 667 us block.

#### The layout decision, stated before it was wired

Gather and scatter into a private interleaved park — 82 words for COMP, 74
for GATE, one park shared by all pairs because pairs run one after
another — rather than repartitioning the block pool into 16 channel pairs.
That is ~4.6 cycles/sample/channel of copying against the several hundred
a paired dynamics stage saves, it is inside every number above, and it
leaves the pool, the node buffers and every other kernel untouched.

#### How much of the >2x is actually SIMD

Not all of it. The paired kernels also hoist the four `_comp_cgp` words
into registers where the scalar re-reads them from DM every sample, so a
scalar block kernel could recover part of the margin above 2.0x with no
pairing at all. The honest reading is that pairing delivers essentially
the full 2x on the dynamics, plus a little.

#### What it does to the strip — arithmetic, not a measurement

GATE 252.1 → 106.8 and COMP 416.6 → 204.2 at the conservative ends of the
measured ranges: 668.7 → 311.0, and the strip **1,098.8 → 741.1
cycles/sample, −32.6 %**. Scaling the measured fused ceilings by that
gives **18.8 at 786 and 24.2 at 983**.

**Those are projections and nothing here measured a ceiling.** No strip
runs paired: the chain is strip-ordered and `BLK_CHAIN_A`/`B` are reused
strip by strip, so a pair needs both strips' blocks live at the same time
and the generator has to emit a pair-aware chain order. That wiring is the
next rung, and it is where SIMD stops today.

#### Where the biquads stopped, and a stale number retired

**The 2.39x on record for the biquad pair was measured against the
PRE-fusion cascade.** Fusion then took 32 % out of that baseline, so the
pairing factor on the cascade the graph actually runs is an open number
and the 2.39x must not be carried into any projection.

Re-measuring it failed. **`_bq_fx_cascade_simd` hangs the part** when
driven from the main loop with the graph configured — the link goes fully
dead, not the "diag ISR still answering" signature. It is bisected to that
routine and not to its wrapper: with `DSP4_SKIP_SIMDCALL=1` the same build
boots, runs, and completes `_bq_pair_blk`'s interleave and scatter cleanly
(and the diff then reports 127 of 128 differing, which is what a pairing
wrapper that does no arithmetic should report). Not chased further, per
the hub's timebox. The fused cascade's SCALAR cost was re-measured on the
way past and is in the table above.

GAIN and FDR were not attempted: 1.6 % and 1.9 % of the strip, both
already running at about one instruction per cycle. DLY and RTG stay
unpairable — per-strip, data-dependent addressing against shared DAGs.

#### One bench-instrument limit, found and written down

The self-test owns the main loop while it runs, and the main loop is what
drains the SPI2 request FIFO. At 8192 iterations the arms total ~700 ms of
link silence and the response stream comes back permanently out of phase —
the same failure mode that made the self-test's first placement unusable.
The iteration count is capped at 2048 (~180 ms); the price is ±1 tick on
the shortest arm, which is why the factors are quoted as ranges from
repeated runs rather than as single numbers.

#### Bench

**Default image byte-identical either side of everything above: chip1.ldr
a2fcda81, chip2.ldr 30291013** — the same md5s the fusion session
recorded, with the generator change and ~1,200 lines of new ASM in the
tree. `DSP4_SIMD_DYN` and `DSP4_STRIP_FUSED` both stay default 0.

Bench restored to those images and verified: booted to BOOT_STAGE 5 on the
shipping firmware, matrix-app started, **all three MCUs verified at
13:43:47 — on the FIRST restart**, which is a counter-occurrence to the
second/third-restart pattern and is logged as one. CPLD never touched.

Measurement points were witnessed at the point of measurement:
BOOT_STAGE 7, `DMA0_STAT 0x00006200`, `SPORT0_ERR_A 0x00000000`. Note the
distinction the harness now makes explicit: MAGIC reading while peeks
return None means the MAIN LOOP is wedged, because a peek is a
two-transaction handshake the diag ISR backstop cannot serve. That is how
the biquad hang was recognised as a hang rather than as a zero.

## HUB DISPATCH 2026-08-28 09:02Z — strip fusion — the 08-24 main event (per-class baseline, fused kernel, GAIN=1 MAC acceptance)   [status: 🟢 done — **STRIP FUSION LANDED AND MEASURED: the signal-present strip is 1,231.8 → 1,098.8 cycles/sample (−10.8 %), and the measured ceilings move 11 → 12 at 786 and 14 → 16 at 983, per chip, signal present, every point witnessed.** **THE ROW THAT MATTERS: a two-chip D32 split at 983.04 MHz needs 16 channels/chip and the part now delivers 16** — last night that row read 14 and the answer was "it does not fit"; the gap was 9.4 % and fusion returned 10.8 %. It is a fit with no headroom (16 strips = 98.2 % of the 983 budget) and it rests on 983.04 MHz, a KSWZ10 clock that is OUT OF SPEC on a KSWZ8, so the U5/U6 marking still has to be read. Silence controls moved by the same proportion (15 → 18 at 786, 20 → 24 at 983, both +20 %), which is what says the gain is in the strip and not in an interaction with the stimulus. **BASELINE FIRST, published per class** (`sigprofile.sh`, new today — the signal-present twin of profile.sh, with a per-point gain witness because three of the first ten points came up carrying the CFG_COMMIT header word in strip 1's coefficient and would have reported the SILENCE cost with everything else reading clean): GAIN 17.7, FILT 123.3, EQ 247.9, GATE 248.3, COMP 426.1, TUBE ~0 (bypassed), DLY 62.0, FDR 37.3, RTG 70.7 = **1,231.8 cycles/sample**, against 1,238.4 from the ceiling-slope model that shares no arithmetic with it — 0.5 % apart. **WHAT FUSION DELETED:** the fused biquad cascade (written 08-24, never measured until today) keeps the error feedback in the 80-bit MRF across samples instead of taking it apart into two words and pushing it back every sample, and hoists the five coefficients per stage — FILT −31.8 %, EQ −32.1 %; FADER_PAN −43.8 %, mostly from replacing a manual counter loop with a hardware one. **BIT-EXACT, proven twice on the part:** the scalar-vs-block self-test was reinstated for the fused routine (a proof of the routine being replaced is not a proof of the replacement) — two stages with DIFFERENT coefficients over two consecutive blocks, impulse then silence, **ndiff=0 of 64, maxdiff=0**; and chain.py on the fused build is **BIT-EXACT, 0 of 7**, negative control passing, with the unfused control run first on the same tree. No numeric deviation to bound and no tolerance loosened — the arithmetic is unchanged, only the plumbing around it. **THE GAIN ACCEPTANCE IS NOT MET AND THE REASON IS STRUCTURAL: GAIN measures 17.8 cycles/sample, unchanged.** One of its seventeen instructions is the MAC; twelve are the single Q4.28 round/saturate and two are block stores, and those exist because THREE consumers want the post-trim block — FILT, the post-trim METER, and the router's post-trim pickoff. Fusion removes FILT from that list exactly and for free (the gain folds into the first biquad stage's numerator triple at control rate: the offset form stores n1 = b1 + 2·b0 and n2 = b2 − b0, both of which scale with b0, so scaling [b0,n1,n2] by g is identical to scaling the input by g at infinite precision, with the x-history left unscaled — and it deletes the intermediate rounding rather than moving it). **It cannot remove the meter**, which reads BLK_CHAIN_B directly; moving what the meter taps belongs in the parked meter ruling, not in a fusion commit. So GAIN = 1 MAC is reachable, the arithmetic for it is derived and written down, and it is gated on that ruling — worth at most 17 cycles/sample, 1.5 % of the strip. A second thing is recorded as buying nothing: the 2-sample interleave was applied to GAIN and FADER_PAN expecting stalls to hide, and the baseline says there are none (17.7 cycles/sample for seventeen instructions is about one per cycle). **FOR SIMD (item 4, not done here):** GATE+COMP is now **61 %** of a fused strip, up from 54.7 %, because fusion took cycles out of everything else and none out of the dynamics — SIMD that pairs only the biquads now caps at ~11 % of a strip and has to reach the dynamics to matter; DLY and RTG (130.3 cycles/sample, 12 %) are not pairable at all; at the 2.39x measured on a biquad pair the pairable remainder would put the strip near 535 cycles/sample = 33 channels at 983 and 26 at 786, which is the projection to test, not a claim. Two SHARC loop hazards cost a bench cycle each and are now written down where they bite (a DO loop's last three instructions may not be a branch or a call; a conditional branch onto a loop's own end instruction hangs the core while the diag timer ISR keeps answering the link, so it presents as firmware that never ran). Default image byte-identical either side of the generator change (chip1.ldr a2fcda81, chip2.ldr 30291013). Bench restored to shipping and verified: those images reflashed, matrix-app active, all three MCUs verified 12:41:32 — on the THIRD restart, one more than the filed bug's second-restart pattern, logged as another occurrence. CPLD never touched.]   [model: opus]

model: opus

STRIP FUSION — execute the still-open main event of the 08-24 11:00Z
dispatch (its item 2; PW re-affirmed today: "gain should be a single MAC,
we discussed this before"). The preconditions that dispatch lacked now
exist: fabric is AT its 40k target, the strip is 881.6 cycles/sample
per-node-converted, ROUTING is active-list, the ramp/SPI plane is fixed,
and the measurement infrastructure is hardened (config-commit stimulus
trap root-caused 8a87d17).

0. BASELINE FIRST: per-class re-profile of the current 881.6 (TCOUNT
   methodology, signal-present stimulus, the hardened probes) — the
   honest map fusion is judged against. Publish the table in the block.
1. FUSION, via the GENERATOR per the 08-24 spec: ONE fused kernel per
   strip — samples resident in registers/MR across
   GAIN→EQ→FILT→GATE→COMP→TUBE→DLY→FDR; stage-to-stage handoff ZERO
   instructions (stage N's result register IS stage N+1's operand);
   intermediate stages bare MACs/cascades at 64-bit precision; ONE
   round/saturate/store at the strip boundary; multifunction lines so
   next-stage state loads overlap current maths; pipeline order
   hard-coded by the generator from the product definition. Block-rate
   section (ramps, Q shadows, coefficient swaps) once at kernel entry.
   GAIN inside the fused strip must measure as ~1 cycle/sample marginal
   cost — that is the acceptance PW named.
2. PROVE bit-exactness per the standing bar: chain.py configured probes,
   negative controls, stimulus that could fail; per-stage crossfade and
   mid-block semantics preserved (the _process_sample lessons apply).
3. RE-MEASURE: strip cycles/sample fused; ceilings at 786 AND 983,
   silence and signal-present, honest 1500/s rule. Update
   dsp4-function-costs.csv.
4. SIMD wiring (the measured-2.39x lever) is NOT in this dispatch — it
   follows fusion in its own session; note in the block what fusion
   leaves as SIMD's starting shape.

Rules: W0 throughout; bench restored to shipping verified at the end;
ladder discipline; hand-back if the generator rewrite stops being
convergent in one session — land the largest bit-exact subset (e.g.
GAIN→EQ→FILT fused) with measurements rather than an all-or-nothing
branch. Push main; update the 08-24 block AND this one.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-28 — strip fusion: the per-class baseline, the fused kernel, and what it moved

#### 0. The baseline, signal present, per class

`sigprofile.sh` — the signal-present twin of `profile.sh`, added today: same
TCOUNT/`_proc_cyc` methodology, same `DSP4_NODE_LIMIT` prefix cut, same DEC=32,
with `DSP4_PROFILE_SIGNAL=1` and a witness on every point. The witness is not
optional: three of the first sweep's ten points came up with strip 1's GAIN
coefficient holding the CFG_COMMIT header word (root-caused last night), which
reports the SILENCE cost with BOOT_STAGE, pass rate, DMA and SPORT all clean.
`gainfix.py` repairs that over the link in a second rather than spending a
40-second reboot on it.

| class | cycles/block | cycles/sample | share of strip |
|---|---|---|---|
| GAIN | 566 | 17.7 | 1.4 % |
| FILT | 3,946 | 123.3 | 10.0 % |
| EQ | 7,934 | 247.9 | 20.1 % |
| GATE | 7,946 | 248.3 | 20.2 % |
| COMP | 13,635 | 426.1 | 34.6 % |
| TUBE | ~0 | ~0 | — (bypassed) |
| DLY | 1,985 | 62.0 | 5.0 % |
| FDR | 1,195 | 37.3 | 3.0 % |
| RTG | 2,263 | 70.7 | 5.7 % |
| **strip (GAIN..RTG)** | **39,417** | **1,231.8** | |

**Two independent methods agree.** The ceiling-slope model put the same strip
at 1,238.4 cycles/sample — 0.5 % apart, and it shares no arithmetic with this
one. GATE+COMP measures 674.4 here against 668.7 from the slope, 0.9 % apart.
The 2026-08-24 table this replaces was taken at 491.52 MHz, before the
crosspoint fold, the active-crosspoint list and the fabric move out of L2, and
its GATE and COMP rows were silence readings; `dsp4-function-costs.csv` is
rewritten on today's numbers.

TUBE reads ~0 both times and the two readings differ by less than the scatter,
which is what a bypassed node's block copy should look like. **Its ACTIVE cost
is still unmeasured** — same open item as 08-24.

#### 1. What fusion is, in this tree

The 08-24 spec asked for one kernel per strip with samples resident in
registers across every stage. Two things about the tree as it now stands bound
what that can be, and both are worth stating because they are structural, not
effort:

- **The biquad section cannot be sample-resident.** FILT+EQ is six biquad
  stages and each carries six words of state. Sample-major residency across the
  strip would need thirty-six state words live at once in sixteen registers.
  The cascade is therefore stage-major, and the fusion that IS available there
  is between the SAMPLES of a stage, not between the stages.
- **Two stage boundaries are pinned by consumers outside the strip.** GAIN's
  output block is read by the post-trim meter and by the router's post-trim
  pickoff; EQ's and DLY's by the other two pickoffs. A stage whose block another
  node reads has to materialise that block, so its round/saturate and store are
  not fusion overhead — they are the interface.

So what landed is fusion where the graph actually permits it:

- **The fused biquad cascade** (`DSP4_STRIP_FUSED`, written 08-24, never
  measured): the error feedback stays in the 80-bit MRF from sample to sample
  instead of being taken apart into two words, stored, and pushed back with a
  sign extension every sample; the five coefficients are hoisted into registers
  for the whole stage instead of re-read per sample. That is ~15 instructions
  per stage per sample deleted, over six stages.
- **GAIN and FADER_PAN**, two samples per iteration, interleaved, the second
  accumulating in MRB. FADER_PAN also loses a manual counter loop and the branch
  at the bottom of it.

**`DSP4_STRIP_FUSED` stays default 0.** Everything above is proven and the
shipping image is byte-identical either way (it is a per-sample build, where the
flag is compiled out entirely), so flipping the default is a decision about
which build ships, not about whether fusion works — and that belongs to the hub
along with the block-kernel default it sits behind.

#### 2. Bit-exactness

- **The fused cascade against the per-sample reference, inside the part.** The
  scalar-vs-block self-test was reinstated for exactly this (it had been retired
  once the OLD block routine was proved, and a proof of the routine being
  replaced is not a proof of the replacement). Two stages with DIFFERENT
  coefficients — equal stages hide a stage-pointer fault and unity stages hide
  everything — over two consecutive blocks, impulse then silence, so every
  sample of block 2 is pure feedback tail and a block-boundary persistence fault
  cannot hide. **done=1, ndiff=0 of 64, maxdiff=0, first=-1**, with a real
  impulse response either side of the boundary.
- **`chain.py` on the fused build: BIT-EXACT, 0 of 7 cases**, negative control
  passing (halving the gain changes the reading). The unfused control was run
  first on the same tree and also passed 0 of 7, so a difference would have been
  attributable.
- Nothing in either change alters the arithmetic — same operations, same order
  within a sample, same single rounding — so both are bit-exact by construction.
  There was no numeric deviation to bound, and no tolerance was loosened.

Two SHARC loop hazards cost a bench cycle each and are now written down where
they bite: a DO loop's last three instructions may not be a branch or a call,
and a conditional branch landing on a loop's own end instruction hangs the core
— while the part keeps answering the parameter link from the diag timer ISR, so
it presents as firmware that simply never ran the test.

#### 3. What it moved

| class | baseline c/s | fused c/s | change |
|---|---|---|---|
| GAIN | 17.7 | 17.8 | +0.9 % |
| FILT | 123.3 | 84.1 | **−31.8 %** |
| EQ | 247.9 | 168.5 | **−32.1 %** |
| GATE | 248.3 | 252.1 | +1.5 % |
| COMP | 426.1 | 416.6 | −2.2 % |
| DLY | 62.0 | 76.8 | +23.7 % |
| FDR | 37.3 | 21.0 | **−43.8 %** |
| RTG | 70.7 | 53.5 | −24.3 % |
| **strip** | **1,231.8** | **1,098.8** | **−10.8 %** |

The untouched classes move by a few percent either way because the code moves
in memory; that is layout scatter, not attribution. **The check that it is
scatter:** the four touched classes account for −4,315 cycles/block and the
whole strip fell by −4,255, so the six untouched ones net +60 — 0.15 % of the
strip. The total is the number to trust and the per-class split is consistent
with it.

#### 4. The ceilings, measured, per chip

`sigstrips.sh` with the fused build, judged on `_proc_passes` by the honest
1500/s rule (not the tool's 1450 threshold), every point witnessed for the
dynamics path AND for all N strips' gain coefficients:

| | baseline | fused | measured points |
|---|---|---|---|
| 786.432 MHz, signal present | 11 | **12** | 12 = 1500/s, 13 = 1463/s |
| 983.04 MHz, signal present | 14 | **16** | 15, 16 = 1500/s, 17 = 1448/s |
| 786.432 MHz, silence | 15 | **18** | 17, 18 = 1500/s, 19 = 1479/s |
| 983.04 MHz, silence | 20 | **24** | 23, 24 = 1500/s, 25 = 1460/s |

The cycle model reproduces every signal-present point from the profile numbers
alone: 786 → 12.69 and 983 → 16.34 against 12 and 16 measured, and 11.32 / 14.58
against the 11 and 14 recorded last night. Four points, no fitting.

**THE ROW THAT MATTERS: a two-chip D32 split at 983.04 MHz needs 16
channels/chip, and the part now delivers 16, signal present, with all sixteen
strips witnessed gate OPEN and compressor ACTIVE.** Last night that row read 14
and the answer was "it does not fit"; the gap was 9.4 % and fusion returned
10.8 %. It is a margin of one block in fifty (16 strips = 98.2 % of the 983
budget), so it is a fit with no headroom, not a comfortable one — and it rests
on 983.04 MHz, which is a KSWZ10 part and OUT OF SPEC on a KSWZ8. The U5/U6
marking still has to be read.

The silence rows moved by the same proportion (15 → 18 and 20 → 24, both
+20 %), which is the control that says the gain is in the strip and not in
some interaction with the stimulus. **Do not read the silence rows as a
feasibility answer** — D24's 24 channels fit one chip at 983 in silence and
that is exactly the reading the 08-27 rung existed to disqualify.

Everything else is still a factor, not a margin: D24's 24-on-one at 983 is
short by 8 with signal present, 32-in-one is 2.0x at 983 and 2.7x at 786, and chip 2 was not
touched and remains 3.8x over its own budget.

#### 5. The GAIN acceptance, answered honestly: NOT met, and why

PW's acceptance was that GAIN measure ~1 cycle/sample marginal inside the fused
strip. **It measures 17.8, unchanged.** The reason is structural and worth the
ruling it implies:

GAIN is seventeen instructions. One is the MAC. Twelve are the single Q4.28
round-and-saturate and two are block stores — and those exist because three
consumers want the post-trim block: FILT, the post-trim METER, and the router's
post-trim pickoff. Fusion removes FILT from that list for free and exactly: the
gain folds into the first biquad stage's numerator triple at control rate,
because the offset form stores n1 = b1 + 2·b0 and n2 = b2 − b0, both of which
scale with b0, so scaling [b0, n1, n2] by g is identical to scaling the input by
g at infinite precision — with the stored x-history left unscaled. Three
multiplies per block instead of a MAC per sample, and it deletes the
intermediate rounding rather than moving it.

**What it cannot remove is the meter.** Every chip-1 meter taps its channel's
GAIN output and reads `BLK_CHAIN_B` directly, so if GAIN stops materialising
that block the meter reads pre-trim. The meter is already the subject of a
parked ruling (fix-numerics / decimate / retire; it reads a Q4.28 word as an
IEEE float, among four recorded defects), and moving what it taps belongs in
that ruling, not in a fusion commit. **So: GAIN = 1 MAC is reachable and the
arithmetic for it is derived and written down; it is gated on the meter
decision, not on the kernel.** Worth at most 17 cycles/sample — 1.5 % of the
strip — which is why it was not worth pre-empting a ruling for.

The same is true one level down: the interleave was applied to GAIN and
FADER_PAN expecting stalls to hide, and GAIN's baseline says there are none
(17.7 cycles/sample for seventeen instructions is about one per cycle). It
bought GAIN nothing, and it is recorded as buying nothing. FADER_PAN's −43.8 %
came from replacing its manual counter loop with a hardware loop, not from the
interleave.

#### 6. What fusion leaves as SIMD's starting shape (item 4, not done here)

- The strip is **1,098.8 cycles/sample signal present**, of which **GATE+COMP is
  668.7 = 61 %** — up from 54.7 % before fusion, because fusion took cycles out
  of everything else and none out of the dynamics. **SIMD that pairs only the
  biquads now caps at ~11 % of a strip.** To matter it has to reach the
  dynamics, and the dynamics are a chain of polynomial calls with four surviving
  registers across them.
- **DLY (76.8) and RTG (53.5) are not pairable** — per-strip and data-dependent
  addressing — so 130.3 cycles/sample, 12 % of the strip, is off the table
  whatever SIMD achieves.
- The pairable remainder is 968.5 cycles/sample. At the 2.39x measured on a
  biquad pair, the strip would land near 535 cycles/sample: **33 channels at
  983 and 26 at 786**. That is the projection to test, not a claim — the 2.39x
  was measured on biquads and the biquads are now the small half.
- The pairing scaffolding fusion inherits is already in the tree
  (`DSP4_SIMD_STRIPS`, `_bq_pair_blk`, `BLK_PAIR_PARK`), and it pairs the
  cascade, which is the fused routine now rather than the one it was written
  against.

#### 7. Bench

Restored to shipping and verified: the default build is byte-identical either
side of the generator change (chip1.ldr **a2fcda81**, chip2.ldr **30291013**,
same md5 before regenerating all 89 touched node files and after), those images
are what is staged and booted on the bench, and matrix-app is active with **all
three MCUs verified at 12:41:32** (H1S1 DSP, H1S3 SW Right, H1S4 SW Left). The
CPLD was never touched — everything today went the firmware route.

**Stated precisely, because the last stop is where it is easiest to overclaim:
the restored shipping image's own BOOT_STAGE/DMA/SPORT registers were NOT read
back.** With the unconverted full graph the part is ~16x over the per-block
budget, the parameter link is polled from the starved main loop, and it stops
answering the moment CONFIG_COMMIT lands — five boot+config cycles all reached
stage 5 and then went quiet, which is the documented behaviour of this image
and not a fault. What IS verified is the layer above: matrix-app boots and
configures the card itself, and it announced all three MCUs. Every measurement
in this block was taken on converted builds whose registers read clean at the
point of measurement (DMA0_STAT 0x00006200, SPORT0_ERR_A 0x00000000, BOOT_STAGE
7 at every witnessed ceiling point).

Two occurrences to keep logging: matrix-app needed a **THIRD** restart to
announce all three MCUs, one more than the filed second-restart pattern; and
the CFG_COMMIT parameter-slip appeared on roughly a third of boots all day,
including on strips other than strip 1 — which is why `gainfix.py` now repairs
any strip and `sigstrips_run.sh` calls it before scoring. A dead strip is a
CHEAP strip, so that defect flatters a ceiling rather than failing it: the
first 12-strip point at 786 came back 1500/s with one strip's coefficient
zeroed, and would have been quotable if the witness had not counted strips.

## HUB DISPATCH 2026-08-27 22:59Z — signal-present ceiling sweep at 786 and 983 (queued rung)   [status: 🟢 done — **MEASURED signal-present ceilings, converted build, chip 1, honest 1500/s rule: 11 at 786.432 MHz and 14 at 983.04 MHz** (silence 15 and 20). Stimulus: a full-rate +/-0.5 (-6 dBFS) square wave ADDED to the real DMA word inside every retained strip's IN kernel (DSP4_PROFILE_SIGNAL, upgraded from the old constant so the production read is still paid for and the sample word varies); proven on the part at every sweep point by a new witness that reads the dynamics state — gate OPEN and compressor ACTIVE on all N strips, envelope exactly 0.500000 and comp gain 0x04C8FBF3 = **-10.48 dB GR against -10.5 dB predicted**, which is only reachable through log2 -> knee -> exp2. Negative control on the same tree: gate gain 0x000418F7 (the 0.001 range floor), comp unity, envelope exactly 0 — so every ceiling ever recorded on this bench really was a silence number. Silence controls re-run through the same harness reproduce last night EXACTLY (15 at 786 and 20 at 983, both 1500/s). **THE DECIDING ANSWER: a two-chip D32 split needs 16/chip at 983 and the part delivers 14. It does not fit — and the ~15-16 estimate was optimistic, not conservative.** Signal costs +40.5% on the strip (881.6 -> 1,238.4 cycles/sample) and 27-30% of the channels. **ALL of it is GATE+COMP** (+360.7 cycles/sample measured independently by node profile, against +356.8 from the sweep slope — 1.1% apart); the two dynamics nodes are now **54% of a signal-present strip**. The cycle model reproduces both ceilings from the pass-rate slope (786: fixed 77,912 + 39,627/strip -> 11.26; 983: fixed 80,824 + 39,438/strip -> 14.57, and it predicts the marginal 15th strip at 1,457/s against 1,462 measured). **One row is a margin rather than a factor:** 16/chip at 983 needs the strip down 9.4%, and the dynamics pair alone would deliver it with a 17.4% cut. Everything else is still a factor: D24 24-on-one at 983 is short by 10, 32-in-one is 2.3x at 983 and 2.9x at 786, and chip 2 is NOT spare capacity (1,978,933 cycles/block on 2026-08-24, 3.8x over its own budget, itself a silence reading). NOT quoted: the GATE-vs-COMP split — the NODE_LIMIT=5 build's gate reads envelope exactly 0 with the stimulus compiled in and measurably executing, while NODE_LIMIT=6's is open, so chain truncation interacts with the stimulus in a way I could not explain and I will not publish a number that rests on it. (RESOLVED 2026-08-28: it was the CFG_COMMIT parameter slip, not chain truncation — the limit-5 point had been taken with strip 1's GAIN coefficient carrying the CFG_COMMIT header word. Re-measured through a witnessed harness, the split is **GATE 248.3 and COMP 426.1 cycles/sample**, summing to 674.4 against 668.7 from the slope.) Bench restored to shipping byte-identical (25a1afed/7052c5d1), BOOT_STAGE 7 at 1500/s, DMA0_STAT 0x00006200, SPORT0_ERR_A clean, CPLD never touched (firmware route, not the loopback bitstream), matrix-app active with all three MCUs verified 01:10:55.]   [model: opus]

model: opus

Execute the queued rung from tonight's crosspoint/fabric session (commit
c5a6e36 "queue the signal-present ceiling sweep as the next rung" — read
its notes first; they define the methodology): the SIGNAL-PRESENT ceiling
sweep on the converted build, at 786 AND 983.

Why it matters (docs/plan-32ch-options.md in mx26 leads with this): the
measured ceilings 15@786 / 20@983 are SILENCE numbers; signal-present is
estimated ~25% lower (~11–12 / ~15–16) from the one recorded
signal-present point (10 @ 786, pre-fabric). This sweep converts every
feasibility verdict — especially D32-on-card at 983 (needs 16/chip) —
from estimate to fact. PW reads the result at breakfast.

Requirements:
- Same _proc_passes methodology and the honest 1500/s rule (not the
  tool's 1450 threshold), exactly as tonight's sweeps.
- Signal path per the recorded recipe (the known-word/loopback technique
  from the virtual-audio work) — the stimulus must be one that could
  fail; no all-zero data taking cheap paths. State in the outcome WHAT
  signal was driven and through which path.
- Sweep strip counts to the over-budget point at both clocks; report the
  measured signal-present ceiling per clock, the effective signal cost vs
  silence (%), and the updated D24/D32/32-in-one verdicts in the same
  table form as the block.
- Standing traps all apply (W0, CHIP_ID before believing, one ttyACM0
  reader, second-restart pattern). Bench restored to shipping and
  verified at the end; outcome appended to the tonight block; push.
- Hand-back: if the signal path won't come up cleanly (routes are
  host-written parameters — use tonight's fixed ramp/SPI writes to set
  them), record what blocks and stop rather than quoting a compromised
  number. A wrong ceiling at breakfast is worse than none.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

## HUB DISPATCH 2026-08-27 22:49Z — R3-R6 review-hardening mechanical pass (desk only)   [status: 🟢 done — all four items landed as 5 small commits, golden harness 10/10 and gen_dsp_csv.py/dsp_validate.py/gen_dsp.py outputs verified byte-identical throughout. R3: GEQ-insertion next() and sport_map.json now fail with contextual ValueErrors (pre-flight checks all buses at load, not per-use). R4: duplicate node IDs short-circuit the rest of that row's checks instead of being validated and forwarded; params cross-checked against a new per-type allowed-key table (required ∪ observed-optional, derived from current dsp.csv). R5: log2_q() raises on negative input; x==0 keeps the -32 sentinel — verified out-of-range (smallest legitimate positive value already floors at -28) and documented, since comp_gain's x_abs legitimately hits 0 on silence; added a golden-harness soft-knee boundary test at over==+/-half_knee (both configs land within 0.00003 dB, branch split is not actually asymmetric in effect). R6: parse_id_list()/parse_params() deduped into tools/dsp/csv_fields.py; dsp_simulate.py's WAV path now reuses the one DSPSimulator via a new reset() instead of a second CSV load (proved byte-identical against a from-scratch instance); biquad_cascade()'s block.copy() removed (biquad_process already returns a fresh array); fixed_ref.py's LOG2_POLY/EXP2_POLY hardcoded as checked-in constants with the fit moved to tools/dsp/fit_log2exp2_poly.py; gen_dsp.py's MCU-only prefixes moved to mcu-only-prefixes.txt alongside matrix-families-allowlist.txt, and the two generated-file writes missing a makedirs guard got one. Nothing hit the hand-back rule — no sub-item stopped looking mechanical. Board untouched throughout, desk-only as scoped.]   [model: sonnet]

model: sonnet

Mechanical desk pass — NO bench work, NO flashing, the board is on verified
shipping images and stays untouched. Execute R3–R6 from the HUB REVIEW
2026-08-27 block in this file, using review.txt §5's patches as the
starting point (they are suggestions — verify each against current HEAD
before applying; several files changed today):

1. R3 — gen_dsp_csv.py: GEQ-insertion `next(...)` StopIteration → clear
   contextual ValueError; sport_map.json pre-flight validated once at load
   (collect ALL inconsistent entries into one error) instead of per-use
   asserts.
2. R4 — dsp_validate.py: duplicate node IDs rejected (skipped after
   reporting, not re-processed); parse_id_list()/parse_params()
   cross-checked against the known node-id set and a per-type
   expected-param-keys table; contextual errors with node id.
3. R5 — fixed_ref.py: log2_q() raises on x <= 0 instead of the silent
   sentinel (check callers first — if a caller legitimately feeds x<=0,
   use a verified out-of-range sentinel and document at the call site);
   add the soft-knee boundary test at over == ±half_knee.
4. R6 — opportunistic, same files only: dedupe the parse helpers between
   dsp_validate.py and dsp_simulate.py into a shared module; drop
   dsp_simulate.py's second DSPSimulator instantiation and the per-stage
   block.copy(); hardcode fixed_ref.py's fitted LOG2/EXP2 polynomial
   coefficients as checked-in constants (keep the fit code as a separate
   regeneration script); makedirs guards on gen_dsp.py's generated-file
   writes; MCU-only prefixes loaded from a config file alongside
   matrix-families-allowlist.txt instead of the hardcoded tuple.

Acceptance: every change keeps the golden harness green (run the relevant
host-side tests/generators; the default generated outputs must be
byte-identical except where an error path is the change); small commits,
one concern each. Do NOT touch dsp_codegen.py's kernel/generator logic —
today's sessions own that ground. Hand-back rule: anything that stops
looking mechanical (a caller genuinely depends on the sentinel, a
validator change breaks generation), record it, mark that sub-item, move
to the next; 🔴 only if everything blocks.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

## HUB DISPATCH 2026-08-27 18:21Z — crosspoint-coefficient audit + enforce (08-25 mandate)   [status: 🟢 done — every in-scope violation folded and PROVEN ON THE PART: strip 1 BIT-EXACT at all 7 level/pan points plus mute and polarity, and routing sends WORK for the first time in the converted build (all 4 pickoffs, negative control passing). Three defects found on the way, all pre-existing and all severe: (1) the ramp-stride table matched only 610 of the ramped parameters, so **every GAIN, FADER_PAN and MONITOR ramped parameter was unsettable over SPI** — proven on the part, and fixed; (2) 132 nodes carried a `_sample_idx == 0` guard that never fires in a block-kernel build, which is why ROUTING never computed a send coefficient there; (3) the chip-1 DM ceiling was an LDF ordering artifact — the overflow region was 0% used and the converted build would not link at all at HEAD. Cycle deltas, converted build, per strip: FDR 1,908 → 1,011 cycles/block (1.89×); RTG 2,617 (prep dead) → 3,196 (prep live, sends working) → 3,667 (folded); FDR+RTG −426 cycles/block against the honest baseline = −13.3 cycles/sample. Capacity: 1,269 → ~1,256 cycles/sample/channel, converted-build ceiling stays 10 — this does NOT move the 32-in-one verdict. **FOLLOW-THROUGH on the same-evening hub steer, all four items done:** the compacted active-crosspoint list landed and is what actually recovers the walk — ROUTING 589.2 → 202.3 cycles/sample (2.91×) and **the SHIPPING ceiling moved from 2 strips to 3** (STRIPS=3 now 1500 passes/s, 4 over budget); the per-sample delta is measured across four tree states (fold −79.8, list −404.9, total **−484.7 cycles/sample**, and the LDF/Block-1 spill costs a measured nothing); the dynamics guard fixes are re-verified on the part, 11 classes across both chips, 0 failures. **TWO OF MY OWN CLAIMS CORRECTED:** the dead-guard count was 132 and is really **68** — chip 1's COMP and GATE drive `_sample_idx` from their own block kernels, so blanket-removing their guard was itself a regression (GATE's sidechain fallback would have converted 32× a block), now decided per node; and the "3 MCUs could not be verified" note was **wrong** — matrix-app logs to `/home/app/logs/log`, not the journal, as the 08-22 block already said, and all three had verified. No app regression exists. Bench restored, all three MCUs verified. **OVERNIGHT RUNG — fabric 40k + measured 32-channel feasibility:** the ledger's fabric row is **NOT double-counted** — measured at its own boundary it reads 86,212 against 85,475 recorded, 0.9% apart, so it was a real still-open lever. Root cause of the fabric cost was the ADDRESS, not the arithmetic: the 25 bus accumulators sat in L2, which the 08-24 note blamed on a DM limit that was really the LDF ordering defect fixed earlier the same evening. Moving them internal + inlining the bus readout: **fabric 86,212 → 51,645 (−40.1%), 2.16x → 1.29x of target**, full graph −7.2%, and the STRIPS fell 41,784 too because ROUTING's crosspoint MACs were paying the same L2 penalty. Bit-exact on the part; per-sample image byte-identical. **MEASURED ceilings, converted build, per chip: 786 → 15, 983 → 20**, and the cycle model predicts both EXACTLY (strip 881.6 cycles/sample, fabric 51,645, block I/O 32,707). **CAVEAT THAT GOVERNS THE FEASIBILITY ANSWER: these are SILENCE measurements.** The recorded 786 ceiling of 10 was signal-present; the same pre-fabric arithmetic projects 13.3, so signal costs ~25% and the signal-present equivalents are **~11–12 at 786 and ~15–16 at 983**. **D24's 24 channels do NOT fit one chip at 983**; D32's 32 are further still; chip 2 remains 3.8x over its own budget. Progress is real (786 ceiling 10 → 15) but the remaining gap is a factor, not a margin. **Meter call then inlined** (numerics-neutral half, standing approval): meters 32,324 → 20,921, **fabric 40,109 = the 40k target MET (2.16x → 1.00x)**, settled meter state bit-identical across builds. **BUT THE CEILINGS DID NOT MOVE** — read by the honest rule (1500/s, not the tool's 1450 threshold) they are still **15 at 786 and 20 at 983**; the inline bought half a channel of margin, moving the next strip count from over-budget to marginal. Both things are true at once and the second is the one that matters. The ledger's fabric row is now SPENT; what remains for 32-in-one is SIMD and the dynamics rework, and the strip is untouched at 881.6 cycles/sample. **PARKED FOR PW: meter decimation, now ~21k cycles/block** — 52% of the remaining fabric; the numerics-neutral part is taken, all that is left comes from sampling less often, and the meters already carry four recorded defects; fix-numerics / decimate / retire is one ruling]   [model: opus]

model: opus

Execute the standing HUB MANDATE 2026-08-25 block in this file:
"crosspoint-coefficient mixing is Bible doctrine; dsp code must follow it"
(status 🔴 audit + enforce). It is next in the queue now that the 08-27
review dispatch is closed.

Scope reminder from the mandate: audit the per-block kernels and generated
strip/routing code for violations of the crosspoint-coefficient fold —
per-sample branches on mute/assign state, gain chains applied as separate
multiplies (fader then pan then mute), any control-state test inside the MAC
loops — and fold them into the per-crosspoint coefficient at control rate.
Nonlinear/structural elements (comp, gate, tube, path enables) are graph
structure, not coefficients — out of scope for the fold. Report findings and
cycle deltas against the strip-fusion ledger. Remember today's ramp-engine
work (stride-aware companion writes, F1 profile-0 fix) sits in this same
code path — build on the fixed generator, and note the capacity arithmetic
impact: every cycle recovered here counts toward the 32-strips-in-one goal
at 786 (PW #1 priority).

W0 discipline throughout; bench restored to shipping at the end; update the
mandate block's status with findings + deltas.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

## NEXT RUNG (queued 2026-08-28 00:0xZ) — SIGNAL-PRESENT ceiling sweep   [status: 🟢 done 2026-08-28 — executed as the 22:59Z dispatch above. Measured 11 at 786 and 14 at 983 against the 11-12 / 15-16 estimate: the 786 estimate held, the 983 one was optimistic and the D32-on-card boundary question is answered NO. Route taken was the firmware stimulus behind DSP4_PROFILE_SIGNAL, not the loopback bitstream; the gate-is-open proof the block demanded is `tools/pi/dsp4_dyn_witness.py` and it ran at every sweep point. Both caveats travelled with the answer.]

model: opus

**This is the number that decides D32-on-card at 983.** Every ceiling measured
on 2026-08-27/28 is a SILENCE measurement: `strips_run.sh` injects nothing and
the bench has no analog input, so the gate sits closed and the compressor idle
and both take their cheap path. Measured silence ceilings are **15 at 786 and
20 at 983** per chip, converted build. The signal-present equivalents are
estimated at **~11–12 and ~15–16**, from a bias sized against the one
signal-present figure on record (the 786 ceiling of 10, versus 13.3 projected
by the same arithmetic — so signal costs roughly a quarter of the headroom).

**Why it is the deciding measurement.** A two-chip D32 split needs 16
channels/chip. The signal-present estimate at 983 is 15–16. That is a margin
question sitting exactly on the boundary, and an estimate carrying a ±25 %
bias correction cannot answer it. A measured number can.

**Two caveats that must travel with the answer, or it will be over-read:**

1. **16/chip is not a free split.** Chip 2 is not idle capacity — its own
   graph measured **1,978,933 cycles/block on 2026-08-24, 3.8x over the same
   budget**, and that was itself a silence reading. "32 across two chips"
   requires chip 2's existing load to be cut first, which nothing this week
   touched. Do not report a per-chip figure as a per-card answer.
2. The 2026-08-24 note "chip 2 is comparatively idle" was retracted as an
   assumption that was never measured. It should not creep back.

### How to get signal on all 32 strips at once — the actual obstacle

The scope injects into ONE input slot (`sc.arm(src, inj, amp, mode)`), so it
cannot drive a 32-strip sweep. Two routes, cheaper one first:

- **A firmware stimulus behind a build flag** (`DSP4_STIM`), written into every
  strip's input by the scatter or the IN kernel. Self-contained, needs no
  bitstream change, and is the same class of measurement scaffolding as
  `DSP4_STRIPS` and `DSP4_NODE_LIMIT`. **The amplitude has to be chosen so the
  dynamics take their REAL path** — above the gate threshold (default
  −40 dBFS) and above the compressor threshold (default −20 dBFS), and clear of
  saturation. A stimulus that leaves the gate shut measures silence with extra
  steps, so the sweep must prove the gate is open before it reports a ceiling
  (read `_gate_gain` or the GR meter, and require it to show the gate passing).
- **The loopback CPLD bitstream + `DSP4_PATTERN`** feeds the TDM inputs for
  real. Higher fidelity, but it means flashing the CPLD, and the shipping
  bitstream must be restored afterwards.

### Deliverable

Measured signal-present ceilings per chip at 786 AND 983, converted build,
`_proc_passes` methodology, judged by the honest rule (**1500/s is real time;
`dsp4_audio_verdict.py`'s REAL_TIME label only means it cleared a 1450
threshold**). Report alongside the silence figures so the bias is visible
rather than folded away, and state the chip-2 caveat with the per-card answer.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status; no AI attribution.

## HUB DISPATCH 2026-08-27 17:27Z — review R1 ramp-write root cause + fix, R2 codegen fail-loudly   [status: 🟢 done — R1 was already fixed 08-23 (d2e4dc6, candidate 3) and is RE-PROVEN on the part; R2 landed byte-identical; F1 (profile-0 discard) fixed per hub ruling; **F3 FOUND AND FIXED — array-valued ramped params (576 routing crosspoints) wrote their ramp state onto neighbouring sends, so aux/fx sends could never be set over SPI at all**. GAIN family unblocked: full −60…+18 dB sweep monotonic, unity bit-exact. Bench restored, 3 MCUs verified. F2 closed: D24 ramp engine regenerated, now byte-identical to the bench-proven D32 file (D24 still builds no image — retired Wine flow, pre-existing)]

model: opus

Review follow-through (HUB REVIEW 2026-08-27 block): R1 + R2 only — R3–R6
stay queued for a later mechanical pass; do not fold them in.

1. R1 — ROOT-CAUSE AND FIX the ramped-parameter write bug (the 2026-08-23
   15:0xZ outcome at the bottom of this file; review §2.1). Three
   candidates — distinguish by evidence, not comments: (a) the generated
   SPI dispatch-table ADDRESS for 0x071C (read the emitted table/asm, not
   its comment), (b) the handler's r0 computation before
   `_ramp_set_target`, (c) `_ramp_set_target`'s own offset convention.
   Whichever it is, establish whether the SAME off-by-one hits every
   ramped cell or only some (generator vs runtime decides the blast
   radius). Fix, then verify ON THE PART over the SPI link: a ramped
   write of 1.0 to 0x071C lands the target at 0x951DE (not 0x951DF),
   `_auxin_on` preserved, a −60…+18 dB ramped sweep produces measurably
   different output, repeatable without reboot. Then re-run the GAIN
   harness family as the unblock proof.
2. R2 — codegen fail-loudly (review §5.1): `GENERATORS.get` raises with
   node type + node id on a miss; delete `gen_generic` or gate it behind
   an explicit opt-in list. Regenerate: the default image must be
   BYTE-IDENTICAL (md5) since no known node type changes — that md5 check
   IS the proof.
3. If the session has room after 1–2: resume the 08-25
   crosspoint-coefficient audit mandate (block above) — R1's fix sits in
   its path anyway.

Bench rules: standing traps apply (W0 discipline; shipping
bitstream/firmware restored at end; matrix-app active with all 3 MCUs
verified — expect the second-restart pattern). Hand-back: if R1's root
cause is none of the three candidates or spans the generator contract,
record findings, mark 🔴, push, stop.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

## FOUND 2026-08-28 — CONFIG COMMIT CAN WRITE A LIVE AUDIO PARAMETER   [status: 🔴 open — needs a fix and a product-path check]

Root-caused while chasing a measurement artifact (outcome below). On roughly
a THIRD of boot+config cycles, `_gain_coeff_C1_GAIN_01` and
`_gain_target_C1_GAIN_01` come up holding **`0xF0040000`** instead of 1.0.
That value is the `CFG_COMMIT` (register 0xF004) transaction's own word0
header — a one-word phase slip in the two-word parameter protocol landing the
header where a value belongs. Strip 1 then multiplies by −1.6e29 and
everything downstream of GAIN runs on zero, while BOOT_STAGE 7, pass rate,
DMA0_STAT and SPORT0_ERR_A all stay clean.

Negative control is clean: **6/6 boots with no config write leave the
coefficient correct**, so this arrives with `dsp4_config.py`, not the image.
Blast radius is exactly those two adjacent words — the other 15 strips'
coefficients and the neighbouring `_mute`/`_polarity` are untouched.

The "config commit desyncs the parameter link" behaviour has been on record
since the bench recipe was written and was treated as cosmetic. It is not: it
can corrupt a live audio parameter.

**Why it may be a shipping defect, not a bench nuisance:** per D1 the Pi
masters the DSP and writes this same config through the same commit at every
product boot, so a shipped card could come up with channel 1 at a garbage
gain and nothing to show for it. NOT YET CONFIRMED on the shipping app's
config path — the shipping image's symbol map is not in this tree, so the
coefficient could not be read back on it. **That check comes first**, then the
fix in `spi_handler.asm` / `product_config.asm`.

Legend: 🔴 not started/blocked · 🟡 in progress · 🟢 done

### Outcome 2026-08-28 (early, second rung) — the NODE_LIMIT=5 "stimulus gap", root-caused

Hub task: root-cause the gap, because it is measurement-infrastructure
integrity and every future per-node figure depends on it. **Root-caused, and
it is not what it looked like.**

#### It was never about NODE_LIMIT

The first thing that had to go was my own characterization. Rebuilding the
same `DSP4_NODE_LIMIT=5` configuration and walking the chain showed the
stimulus arriving perfectly — ±0.5 through the pool, FILT and EQ state, into
an open gate. Booting **the same image** repeatedly then reproduced both
outcomes: signal, zero, signal. It is **intermittent, roughly a third of
boots**, and NODE_LIMIT had nothing to do with it. The original limit-5 /
limit-6 pair was two boots that happened to land on opposite sides of a coin
flip, and I read a mechanism into it that was not there.

#### A second wrong turn, worth recording because the evidence looked strong

The failing boots showed FILT's captured input word at exactly `+1 LSB`, which
requires a pre-add sample of `−0x07FFFFFF` — i.e. the value the IN kernel read
was ≈ −0.5, not the −1 LSB idle. Since the stimulus was ADDED to the input,
that reads as a feedback loop: the strip's own output returning in antiphase
and cancelling the stimulus. It is a coherent story and it was wrong. Changing
the stimulus to discard the input word (below) did **not** stop the failures —
3 of 8 boots still came up dead. What that reasoning missed is that **pool A is
written LAST by GATE**, not by IN, so "pool A reads zero" never was evidence
about the IN kernel at all. Every inference built on it was unsound.

#### The actual cause: the config commit writes a garbage gain coefficient

On a failing boot, exactly **two adjacent words** are wrong, and nothing else
in the image is:

    _gain_coeff_C1_GAIN_01   @92F3C  F0040000   (should be 3F800000 = 1.0)
    _gain_target_C1_GAIN_01  @92F3D  F0040000
    gain_coeff across strips 1..16:  ok=15  bad=1
    _mute/_polarity (next words), FILT and EQ coefficients:  all correct

**`0xF0040000` is not garbage — it is the `CFG_COMMIT` transaction's own header
word.** The parameter protocol is two 32-bit words, `word0[31:16] = address`,
and `CFG_COMMIT` is register `0xF004`, so its word0 is `0xF004 << 16 =
0xF0040000` exactly. A one-word phase slip in that two-word stream lands the
header where a value belongs, and it lands on the two words a ramped GAIN
write sets.

So this is the **already-recorded "the config commit desyncs the parameter
link every time"** behaviour — but it does more than desync the link. It can
**write a live audio parameter**. That was not known.

**Negative control, and it is clean: 6/6 boots with NO config write leave the
coefficient at `3F800000`.** The boot stream is exonerated; the corruption
arrives with `dsp4_config.py`, not with the image.

Strip 1 then multiplies by a coefficient of −1.6e29, and everything downstream
of GAIN runs on approximately zero.

#### Why nothing caught it — and what it costs a measurement

In that state the card reports **BOOT_STAGE 7, a clean 47/s decimated pass
rate, `DMA0_STAT 0x00006200` and `SPORT0_ERR_A` clean**. Every health
indicator this bench has says the run is good. The only instrument that sees
it is the dynamics witness.

And it changes the number. Measured at `NODE_LIMIT=6`, 8 boots, perfect
correlation:

| state | `_gate_envelope` | `_comp_gain` | pool0 | `_proc_cyc` |
|---|---|---|---|---|
| signal (5 boots) | 0.500000 | 0x04C8FBF4 | 0x08000000 | **66,416–66,428** |
| zero-strip (3 boots) | 0.000000 | 0x10000000 (unity) | 0x00000000 | **54,942–54,949** |

54,94x is the **silence** figure (54,825 measured directly) and 66,42x is the
**signal** figure (66,422). **A build that says signal silently returns the
silence cost, 17 % low, with nothing to indicate it.** That is the
infrastructure defect in one line.

#### What this does and does not invalidate

- **The 786/983 ceilings stand.** Every sweep point ran the witness across
  ALL N strips and reported gate OPEN and comp ACTIVE on every one; a
  corrupted strip reads SHUT. The failure mode is exactly what that check was
  put there to catch, and it did not fire on any reported point.
- **The GATE-versus-COMP split is now explained.** The limit-5 point was taken
  in the corrupt state, which is why GATE appeared to cost nothing and
  `DSP4_GATE_LINTHR` appeared to buy nothing. Declining to publish those was
  right, and they remain unpublished — the split needs re-measuring with a
  witness at each point, which is now cheap.
- **Silence measurements are cycle-safe but semantically blind**: a strip
  running on a garbage coefficient takes the same cheap branch as a strip
  running on silence, so the cycle count is unaffected — but nothing would
  have revealed the fault either.

#### This is very likely a PRODUCT defect, not a bench nuisance

Per decision D1 the Pi masters the DSP and writes this same product config at
every boot, through the same two-word protocol and the same commit. If the
slip happens there, a shipped card can come up with **channel 1 at a garbage
gain** and no indication anywhere. **Not yet confirmed against the shipping
app's config path** — the shipping image's symbol map is not in this tree, so
the coefficient could not be read back on it tonight. That is the next check
and it should happen before this is filed as bench-only.

#### Landed

1. **`DSP4_PROFILE_SIGNAL` now discards the input word** rather than adding to
   it. This was NOT the root cause and is not presented as the fix — it is
   hardening that the investigation showed was needed anyway: a stimulus must
   not be a function of anything the graph it stimulates can influence. The
   production read and shift still execute, so the cost is still a superset of
   production; only the value is dropped. Proven: the pool now reads exactly
   `0x08000000` where it previously read `0x07FFFFFF` (the input's −1 LSB
   leaking in). The flag-off build stays byte-identical to HEAD.
2. **`sigstrips_run.sh` retries on a failed witness.** The witness already
   refused to certify these runs; now it also re-runs boot+config, which
   clears the state. Sweeps become self-healing instead of silently losing a
   third of their points.

#### Not done

- **The desync itself is not fixed.** That is `spi_handler.asm` /
  `product_config.asm` ground and a larger piece of work than this rung; it is
  recorded here with the mechanism named rather than half-fixed.
- Confirming it on the shipping app's config path (see above).
- Re-measuring the GATE/COMP split with a per-point witness.

#### Bench hand-back

Shipping firmware restored byte-identical (`25a1afed…` / `7052c5d1…`),
BOOT_STAGE 7 at 1500/s, DMA0_STAT 0x00006200, SPORT0_ERR_A clean, CPLD never
touched. matrix-app active, all three MCUs verified 01:49:39.


### Outcome 2026-08-28 (early) — the SIGNAL-PRESENT ceilings, measured

The rung queued at c5a6e36. Every ceiling on record was taken on a silent
bench; this replaces the ±25 % bias correction with a measurement, at both
clocks, on the converted build.

#### The stimulus, and why this one

Route taken was the cheap one the block listed first: a firmware stimulus
behind a build flag, not the loopback CPLD bitstream. `DSP4_PROFILE_SIGNAL`
already existed and already substituted a constant −6 dBFS in the IN kernel;
it was upgraded rather than replaced, in two ways that both matter to whether
the number can be trusted:

1. **It now ADDS to the real DMA word instead of replacing it.** The old form
   returned early and never executed the `dm(i0, m0)` read or the Q1.31 →
   Q4.28 shift, so it measured a strip whose input node was *cheaper* than the
   production one. The new form pays the production read and then adds the
   stimulus, so it cannot understate the node it stands in for. It overstates
   it instead, by the add and the negate — **measured at 54 cycles/block per
   strip, 1.7 cycles/sample out of 1,238**, which is 0.14 % and in the safe
   direction.
2. **The sample word alternates** (+0.5, −0.5, … at full rate) while |x| stays
   constant. Constant magnitude is what keeps the dynamics on their expensive
   branch at *every* sample rather than dipping back mid-block; the
   alternating word is what stops a stuck, bypassed or stale-slot path from
   looking like a working one. A DC constant would have survived most of those.

−6 dBFS sits above the −40 dB gate threshold and the −20 dB compressor
threshold at the shipping defaults, which is the condition the block set.

#### Proof that the signal was actually there — every point, not once

`tools/pi/dsp4_dyn_witness.py` reads the dynamics state and refuses to report
a value that two consecutive reads do not agree on (the diag link answers
0xFFFFFFFF intermittently, and one read cannot tell that from a value —
recorded 2026-08-27 and it bit this probe too).

    strip  gate_env   gate_gain          comp_env   comp_gain
        1  0.500000   0x10000000 OPEN    0.500000   0x04C8FBF3  −10.48 dB GR

**The comp gain is the strong witness, not the gate.** With thr −20 dB, ratio
4 and a hard knee, −6 dBFS predicts 2^−(0.75·log2(0.5/0.1)) = 0.2988 → −10.50
dB. The part returned 0x04C8FBF3 = 0.298873 → **−10.48 dB**. That value is
only reachable by running log2, the knee and exp2 end to end; "non-zero" would
not have proved it.

**Negative control, same tree, stimulus off:** gate gain 0x000418F7 — the
0.001 range floor, i.e. shut — comp unity, envelopes exactly 0, on every
strip. So the bench really is silent without this, and **every ceiling
previously recorded on it really is a silence number.** That was an assumption
until tonight.

#### MEASURED signal-present ceilings, converted build, chip 1

Judged by the honest rule: 1500 passes/s is real time; `audio_verdict.py`
labels anything over 1450 REAL_TIME and that label is wrong.

| `DSP4_STRIPS` | 786.432 MHz | 983.04 MHz |
|---|---|---|
| **11** | **1500/s — ceiling** | — |
| 12 | 1421/s over budget | — |
| 13 | 1326/s over budget | — |
| **14** | 1243/s over budget | **1500/s — ceiling** |
| 15 | — | 1462/s — **marginal** (the tool calls this REAL_TIME) |
| 16 | — | 1381/s over budget |

Witness at every one of those points: gate OPEN and comp ACTIVE on **all N**
strips, 0 unreadable.

**Silence controls re-run through the same harness**, so the only variable
between the two columns is the stimulus: **15 at 786 = 1500/s** and **20 at
983 = 1500/s**, witness reporting every strip on the cheap branch. Those
reproduce 2026-08-27 exactly.

| | silence (measured) | estimated | **signal-present (MEASURED)** |
|---|---|---|---|
| 786.432 | 15 | ~11–12 | **11** |
| 983.04 | 20 | ~15–16 | **14** |

**The 786 estimate held. The 983 estimate was optimistic, and that is the one
the feasibility answer turned on.**

#### What signal costs

Taken from the pass-rate slope, which needs no chain truncation: at a strip
count that is over budget, cycles/block = CCLK / passes_per_second.

| clock | points used | cycles per strip | fixed cost | predicted ceiling | measured |
|---|---|---|---|---|---|
| 786.432 | 12, 13, 14 | 39,627 | 77,912 | 11.26 → **11** | **11** |
| 983.04 | 15, 16 | 39,438 | 80,824 | 14.57 → **14** | **14** |

The two clocks agree on the strip to 0.5 % — as they must, since it is core
cycles. The model also predicts the *marginal* point: 14.57 strips of capacity
means 15 strips run at 97.1 % = 1,457/s, and 1,462/s was measured.

- **A signal-present strip is 39,627 cycles/block = 1,238.4 cycles/sample**,
  against 881.6 silent. **+40.5 %.**
- In channels: 15 → 11 at 786 (−26.7 %), 20 → 14 at 983 (−30.0 %). The "signal
  costs roughly a quarter of the headroom" bias was close at 786 and too kind
  at 983.
- Fixed cost grows 3.7 % between the clocks (77,912 → 80,824 core cycles)
  because part of it is off-core and clocked by SYSCLK, not CCLK. It is a
  small effect but it is real, and it is why the ceiling ratio (1.29) is not
  the clock ratio (1.25).

#### ALL of it is the two dynamics nodes

Independent method — `profile.sh`, `DSP4_NODE_LIMIT` 6 versus 4, run with the
stimulus on and off. Limit 4 is IN+GAIN+FILT+EQ, limit 6 adds GATE and COMP.

| | limit 4 | limit 6 | GATE+COMP |
|---|---|---|---|
| silence | 44,969 | 54,825 | 9,856 |
| signal | 45,023 | 66,422 | **21,399** |
| delta | +54 | | **+11,543 = +360.7 cycles/sample** |

+360.7 against **+356.8** from the ceiling-sweep slope: **1.1 % apart, two
methods that share no arithmetic.** And the limit-4 row is the control that
makes it safe — the rest of the chain moves by 54 cycles/block, which is
exactly the stimulus's own overhead, so IN/GAIN/FILT/EQ are data-independent
as expected.

**GATE+COMP with signal = 21,399 cycles/block = 668.7 cycles/sample = 54 % of
the entire signal-present strip.** The dynamics rework is no longer one lever
among several; it is most of what is left.

#### The 32-channel answer, restated on measurements

- **D32 as a two-chip split at 983 needs 16 channels/chip. The part delivers
  14. It does not fit.** This was the question the rung existed to answer, and
  the estimate that made it look like a boundary case was optimistic.
- **BUT this is the one row that is a margin rather than a factor.** 16/chip
  at 983 needs the strip down from 1,238.4 to 1,122.2 cycles/sample — **−9.4
  %**. GATE+COMP is 668.7 of that strip, so a **17.4 % cut in the dynamics
  pair alone** closes it. Nothing else on this page is that close.
- **D24, 24 channels on one chip at 983: short by 10** (14 measured). Needs
  748.1 cycles/sample against 1,238.4 — a factor of 1.66.
- **D32, 32 channels on one chip: 2.29x short at 983, 2.91x at 786.**
- **Chip 2 is still not the escape route, and the per-chip figure is not a
  per-card answer.** Its own graph measured 1,978,933 cycles/block on
  2026-08-24, 3.8x over the same budget, and that was itself a silence
  reading. Nothing this week touched it, and it was not measured with signal
  tonight either. "32 across two chips" requires chip 2's load to be cut
  first.
- The 2026-08-24 note "chip 2 is comparatively idle" stays retracted.

#### One thing I could not explain, so it is not quoted

The GATE-versus-COMP split. Profiling at `DSP4_NODE_LIMIT` 5 makes GATE the
last node in the chain, and in that build the witness reads
`_gate_envelope` = **exactly 0** with the stimulus compiled in and
**measurably executing** (the limit-4 cost carries its +54). At
`DSP4_NODE_LIMIT` 6 the same stimulus reaches an OPEN gate and an ACTIVE
compressor. Truncating the chain therefore interacts with the stimulus in a
way I did not get to the bottom of, and every per-node number that leans on
the limit-5 point is unsafe:

- **GATE alone and COMP alone are NOT reported.** The limit-5 readings make
  GATE look free (4,903 silent, 4,710 with signal, 4,712 with log2 stubbed)
  and put the whole cost in COMP; that would be an interesting claim about
  `_log2q_fx` and it is exactly the claim the suspect point would produce.
- For the same reason **the reading that `DSP4_GATE_LINTHR`'s recorded "~95
  cycles/sample" is not real is NOT asserted here**, even though three
  measurements pointed that way. That flag is carried as a lever needing a
  numeric-spec amendment and PW's sign-off; re-price it once the truncation
  interaction is understood, before anyone spends the amendment on it.
- **GATE+COMP together is safe** and is what is reported above: at limit 6
  both builds are internally consistent — the signal build has signal at both
  nodes, the silence build at neither.

#### Also not done

- **Chip 2 was not measured with signal.** Its 3.8x is a silence figure and
  the correct signal-present figure is worse by something like the 40 % found
  on chip 1, but that is an inference and is not quoted as a measurement.
- The stimulus is **steady state**. It holds both dynamics on the expensive
  branch continuously, which is the right worst case for a ceiling, but it
  does not exercise transients — makeup ramps, gate hold expiry, knee
  traversal. A programme-material ceiling would sit between this and silence,
  nearer this end.
- **TUBE is off at the shipping default**, so it takes its copy path in both
  columns and its active cost is in neither number. That has been an open item
  since 2026-08-24 and still is.
- The knee is 0 at the default, so COMP takes the hard-knee path. Soft knee is
  a longer path and is not measured.

#### Bench hand-back

Shipping firmware restored byte-identical (`25a1afed…` / `7052c5d1…`),
BOOT_STAGE 7 at 1500/s, DMA0_STAT 0x00006200, SPORT0_ERR_A clean. The CPLD was
never touched — the firmware-stimulus route was taken precisely so the
shipping bitstream never had to move. matrix-app active, all three MCUs
verified at 01:10:55 (H1S1, H1S3, H1S4); the second-restart pattern held
again. The default per-sample image rebuilds to `a2fcda81…`, the same md5
recorded on 2026-08-27, and the converted build with the flag off is
byte-identical to HEAD — so the stimulus is inert in everything that is not
explicitly asking for it.


### Outcome 2026-08-27/28 (overnight) — fabric 40k rung, and a measured 32-channel feasibility update

Hub steer: fabric 40k target on the converted build, then a measured ceiling at
786 AND 983 so the D24-fits / D32-gap rows stop being projections.

#### The double-counting question, answered: NOT double-counted

Measured at exactly the ledger's own boundary (`NODE_LIMIT` 320 versus 0), the
fabric reads **86,212 cycles/block** against the **85,475** recorded on
2026-08-24 — **0.9 % apart**. The meters are inside that boundary in both
measurements, so nothing was reclassified out of it and nothing had improved.
**The 40k row was a real, still-open lever**, and an earlier speculation of mine
that it was stale reclassification was wrong.

A wrong turn worth recording, because it nearly became the answer. The first
decomposition numbered the chain by counting `call` lines in
`process_chain.asm` — but block-kernel meters are emitted TWICE there, once at
their own index for the per-sample build and once after their source for the
block build. The true `call_sequence` is **431 nodes, not 463**, with the
meters at **321..352, not 353..384**. Every `NODE_LIMIT` point was therefore
measuring the wrong segment, and it produced a confident and completely wrong
reading ("the meters are the fabric's largest single item"). What caught it:
`NODE_LIMIT` 451 and 0 returned byte-identical counts, which is only possible
if 451 is past the end of the chain. That accident is also the best noise
measurement of the session — the same build measured twice, to the cycle.

#### Where the fabric actually goes

| segment | cycles/block | share |
|---|---|---|
| 32 meters (321..352) | 32,324 | 37.5 % |
| cross-ins + talkback + noise (353..369) | 1,106 | 1.3 % |
| **25 buses + 25 sends (370..419)** | **52,427** | **60.8 %** |
| 12 inter-chip transfers (420..431) | 355 | 0.4 % |

#### The buses were expensive because of their ADDRESS, not their arithmetic

52,427 cycles/block is **32.8 cycles/sample per bus node** for what is one
round-and-saturate. The arithmetic does not explain that. The 25 x 64-word
accumulators were declared in `seg_delay` — **L2 at 0x20000000, off-core, and
contending with the DMA streaming audio through the same fabric.** Every
`_acc64_mac_blk` reads two words and writes two back per sample per live
crosspoint; every readout reads two more.

They were in L2 because putting them internal "overflowed sec_stak"
(2026-08-24). **That was never a memory limit** — it was the LDF ordering
defect fixed earlier the same evening, where `sec_stak` was declared after
`sec_dmda` so Block 0 had to hold everything while the overflow region sat at
0 %. Chip 1 now has ~178 KB of DM free and these 1,600 words fit with room to
spare. So the fix for the largest item in the fabric was already paid for by an
unrelated change made hours earlier; it just had not been collected.

Landed, both numerics-neutral:

1. **Bus accumulators moved to internal DM** (block build only).
2. **`_acc64_rns28` + `_mrf_rns28` inlined into the chip-1 bus readout** with
   their three constants hoisted — 800 invocations per block were each paying a
   call, an rts and two constant reloads. The saturation fix-up becomes a
   conditional move so the body stays inside a hardware loop.

| segment | before | after | delta |
|---|---|---|---|
| 32 strips (1..320) | 977,214 | 935,430 | **−41,784** |
| 32 meters | 32,324 | 31,816 | −508 |
| cross-ins + buses + sends | 53,533 | 19,531 | **−34,002 (−63.5 %)** |
| inter-chip transfers | 355 | 298 | −57 |
| **full graph** | **1,063,426** | **987,075** | **−76,351 (−7.2 %)** |
| **FABRIC (320 vs 0)** | **86,212** | **51,645** | **−34,567 (−40.1 %)** |

Note the strips fell by **more than the buses did**. That is ROUTING's
`_acc64_mac_blk` paying the same L2 penalty on every crosspoint MAC. Moving one
array made both cheaper.

**Fabric against its target: 2.16x → 1.29x.** Not reached; materially closer.

Verified on the part, converted build, `dsp4_send_proof.py` with its negative
control passing: `SENDS WORK (0 checks mismatched)` across all four pickoffs,
every coefficient and bus value bit-exact. **The per-sample image is
byte-identical** (`a2fcda81...`), which is the proof both changes touch only
the converted build.

#### MEASURED ceilings, converted build, per chip

`strips.sh` methodology, judged on `_proc_passes`, no decimation:

| `DSP4_STRIPS` | 786.432 MHz | 983.04 MHz |
|---|---|---|
| 12 | 1500/s real time | — |
| 14 | 1499/s real time | — |
| **15** | **1500/s — ceiling** | — |
| 16 | 1446/s over budget | — |
| 18 | — | 1500/s real time |
| 19 | — | 1500/s real time |
| **20** | — | **1500/s — ceiling** |
| 21 | — | 1442/s over budget |

**786: 15 channels/chip. 983: 20 channels/chip.** Both post-fabric.

The cycle model and the bench now corroborate exactly. With block I/O 32,707
(carried from 2026-08-24, not re-measured tonight), fabric 51,645 and a strip
of **28,210 cycles/block = 881.6 cycles/sample**:

| clock | budget/block | predicted | measured |
|---|---|---|---|
| 786.432 | 524,288 | 15 | **15** |
| 983.04 | 655,360 | 20 | **20** |

Two independent methods agreeing to the channel is the strongest form this
number has taken. It also retro-validates the carried-over block I/O figure:
no other value of it predicts both ceilings.

#### THE CAVEAT THAT GOVERNS THESE NUMBERS — silence, not signal

`strips_run.sh` injects nothing and the bench has no analog input, so this is a
**silence** measurement: the gate is closed and the compressor idle, and both
take their cheap path. The recorded 786 ceiling of **10** was taken "signal
present, so the dynamics take their real path".

Sizing the bias from my own data: the PRE-fabric numbers measured tonight
project **13.3** channels at 786, against that recorded **10** with signal.
**Signal costs roughly a quarter of the headroom.** Applying that to tonight's
measurements:

| | silence (measured) | signal-present estimate |
|---|---|---|
| 786.432 | 15 | **~11–12** |
| 983.04 | 20 | **~15–16** |

**The silence figures are an upper bound and must not be quoted as the
feasibility answer.** Closing this properly needs a signal-present sweep, which
needs a stimulus on all strips at once — the scope injects into one input slot,
so it does not reach. Recorded as the next measurement this line of work needs.

#### The 32-channel answer, stated against what PW asked

- **D24 (24 channels): does NOT fit one chip at 983.** Measured 20 in silence,
  ~15–16 with signal. Short by 4 channels at best, 8 at worst.
- **D32 (32 channels): further away** — 1.6x the silence ceiling, ~2x the
  signal-present estimate.
- **Chip 2 is not the escape route** and that has not changed: its own graph
  measured 1,978,933 cycles/block on 2026-08-24, 3.8x over the same budget, on
  a silence reading. Nothing tonight touched it.
- Progress is real: at 786 the ceiling has gone **10 → 15** in silence terms
  across this week's work, and the fabric is 40 % cheaper tonight alone. But
  the remaining gap to 24-on-one-chip is a **factor**, not a margin, and no
  single lever left in the fabric closes it.

#### Meter call inlined — and the 40k target is MET

The numerics-neutral half of the parked meter item, taken under standing
approval: `_mtr_step` is inlined into the block loop, deleting a call and an
rts on every one of 32 samples x 32 meters = **1,024 invocations per block**,
with the two constants hoisted into f2 and f5 across the whole loop (nothing
in the body touches them).

**The arithmetic is reproduced exactly, including its oddity**: the new-peak
path stores the peak and does NOT update the RMS, so the RMS only advances on
decay samples. That is what the shared step did; it is preserved deliberately
rather than tidied, because the numerics are PW's call.

| | before tonight | after bus fix | + meter inline |
|---|---|---|---|
| 32 meters | 32,324 | 31,816 | **20,921** |
| **FABRIC (320 vs 0)** | 86,212 | 51,645 | **40,109** |
| **vs the 40k target** | 2.16x | 1.29x | **1.00x — MET** |
| full graph | 1,063,426 | 987,075 | 975,578 |
| 32 strips | 977,214 | 935,430 | 935,469 |

The inline recovered **10,895 cycles/block**, twice the ~5,000 estimated. The
strips moved +39 — nothing — which is the right control, since the meters are
not in the strip and should not have shifted.

**Bit-exactness, and two instrument traps it walked into first.**

The obvious probe -- point the scope at `_mtr_peak` and diff a 32-sample trace
between builds -- **does not work**, and the way it fails is worth recording:
`_scope_record` runs in the GATHER loop, after the whole chain has run, so it
cannot see a per-block kernel's state evolving mid-block. It returned two
plausible words followed by uninitialised buffer, which would have read as
corruption if trusted. Second, the diag link intermittently answers
`0xFFFFFFFF` to a peek and a single read cannot tell that from a value -- the
first version of the probe duly reported the peak as NaN twice.

`tools/pi/dsp4_mtr_state.py` therefore compares the SETTLED state, and requires
two consecutive agreeing reads. Identical across both builds:

    amp=0x40000000  rms=407FFFCE (3.999988)      <- twice, both builds
    amp=0x20000000  rms=03C94582 (1.182968e-36)  <- both builds

The second row is the stronger evidence: a history-dependent mid-settle value
that both builds arrive at bit-for-bit. The peak reads UNREADABLE in both, and
that is the check working -- with a constant input the peak sits in a
two-sample limit cycle, so no two reads agree and the probe refuses to report
an unstable value rather than inventing one. `SENDS WORK (0 mismatched)` still
passes on the same image, and the per-sample image stays byte-identical
(`a2fcda81...`).

**Limits of this proof, stated plainly:** it compares fixed points, not
sample-by-sample behaviour. It would catch a clobbered constant, a wrong
branch or a wrong iteration count -- the realistic failure modes -- but it is
not the bit-exact-per-sample proof the strip nodes got.

#### Ceilings after the meter inline — read by the HONEST rule, not the tool's

| `DSP4_STRIPS` | 786.432 MHz | 983.04 MHz |
|---|---|---|
| 15 | **1500/s — ceiling** | — |
| 16 | 1487/s — **marginal** | — |
| 17 | 1413/s over budget | — |
| 20 | — | **1499/s — ceiling** |
| 21 | — | 1471/s — **marginal** |

**The tool labels 1487 and 1471 REAL_TIME and that label is wrong**, for the
reason already recorded on 2026-08-24: `dsp4_audio_verdict.py`'s threshold is
1450, but anything below 1500 is dropping blocks. By that rule **the ceilings
are unchanged at 15 and 20** — what the meter inline bought is half a channel
of margin, visible as the next strip count moving from clearly over budget
(1446 and 1442) to marginal (1487 and 1471). The cycle model predicting 16 at
786 is consistent with 16 sitting right on the edge.

**So: the fabric target is met and the ceilings did not move.** Both of those
are true at once, and the second is the one that matters for feasibility.

#### PARKED FOR PW — meter decimation, worth ~21k cycles/block

**The decision:** should the 32 channel meters keep sampling every sample, or
be decimated to once per block (or retired)?

**What it is worth, updated after the inline:** the meters now cost **20,921
cycles/block** — still the largest single item in a 40,109-cycle fabric, at
52 % of it. The numerics-neutral part has been taken (the call inline, worth
10,895). What remains is worth roughly **21,000 cycles/block** and CANNOT be
taken without a ruling, because all of it comes from sampling less often.

**Why it is not mine to take:** decimation changes what the meters REPORT, not
just when they sample — a peak meter that looks at 1 sample in 32 will miss
transients. The generator is explicit that block conversion "fixes only WHEN it
samples, not WHAT it computes", deliberately, because the meters carry **four
recorded defects** — including reading a Q4.28 word as an IEEE float — and the
decision on whether to fix or retire them has been open since 2026-08-24.
Changing their sampling while their numerics are already wrong would bury one
fault under another.

**What PW needs to rule on, in one read:** fix the numerics, decimate, or
retire. If the meters are to be fixed anyway, decimation should be decided at
the same time, since both touch the same code. If they are to be retired, 32,324
cycles/block comes back for nothing.

#### Bench hand-back

Shipping firmware restored byte-identical (`25a1afed...` / `7052c5d1...`),
BOOT_STAGE 7 at 1500/s, DMA0_STAT 0x00006200, SPORT0_ERR_A clean; CPLD IDCODE
0x020a30dd on the untouched shipping bitstream; GPIOs released; matrix-app
active with all three MCUs verified (H1S1, H1S3, H1S4 at 23:39:05) — second
restart again, the first announcing only H1S3.

#### What the lever stack looks like now

The ledger's "+ fabric at its 40k target" row is **spent** — everything it
attributed to the fabric has been collected, and the fabric is at 40,109. What
is left for 32-in-one is SIMD across the strip and the dynamics rework, and
**the strip itself is untouched at 881.6 cycles/sample**. Hitting the fabric
target closed the fabric gap; it did not close the channel gap.

#### Not done

- **Signal-present sweeps** (see the caveat above) — the number that would turn
  the feasibility estimate into a fact.
- **Block I/O was not re-measured**; 32,707 is carried from 2026-08-24. It is
  corroborated by predicting both ceilings exactly, but that is inference.
- **Meter call inlining** (~5,000 cycles/block, numerics-neutral) was left with
  the parked decision rather than taken piecemeal.
- The **chip-2 graph** was not touched and remains 3.8x over budget.


### Outcome 2026-08-27 (late) — active-crosspoint list, per-sample deltas, dynamics re-verified

Hub steer of the same evening: build the compacted active-crosspoint list for
the shipping path and measure it; measure the per-sample delta properly; re-
verify the dynamics guard fixes on the part; name the matrix-app build that
stopped emitting `H1S*`.

#### 1. The compacted active-crosspoint list — the shipping ceiling is now 3

ROUTING now resolves WHICH crosspoints are live at control rate, into a dense
list of (source address, bus accumulator, coefficient) triples plus a count,
and the audio path iterates over live crosspoints only. Nothing in it reads or
tests control state, and there is no walk over dead crosspoints: a channel
assigned to main only goes from 25 iterations per sample to 2.

Measured on the part with `profile.sh` (TCOUNT, `DSP4_NODE_LIMIT`, DEC=32),
per-sample build, per strip:

| ROUTING | cycles/block | cycles/sample |
|---|---|---|
| before any of this work | 18,853 | 589.2 |
| + crosspoint fold (committed earlier today) | 19,140 | 598.1 |
| + active-crosspoint list | **6,474** | **202.3** |

**RTG 589.2 → 202.3 cycles/sample, 2.91×.** The middle row is the point: the
fold on its own did NOT make the per-sample router cheaper — it made the
per-crosspoint work cheaper but still walked all 25 every sample, and paid new
control-rate prep on top. The list is what recovers it, which is what the steer
predicted.

**And the shipping ceiling moved.** `strips.sh` at the default clock, judged on
`_proc_passes` (audio truth, not link responsiveness):

| `DSP4_STRIPS` | `_proc_passes` | verdict |
|---|---|---|
| 2 | 1500/s | real time |
| **3** | **1500/s** | **real time — the new ceiling** |
| 4 | 1334/s | over budget |

That is **2 → 3 strips** on the shipping image, against a ceiling of 2 recorded
since 2026-08-22 (where STRIPS=3 measured 1342/s, 89 %). Same clock, same
harness, same verdict rule.

#### 2. The per-sample delta, measured across four tree states

Four states so the memory-layout change is separated from the fold and the fold
from the list. Limits 1/2/8/9/10 give GAIN, FADER_PAN and ROUTING respectively.

| variant | GAIN | FADER_PAN | ROUTING | chain @ L10 |
|---|---|---|---|---|
| A — before this work | 71.7 | 147.6 | 589.2 | 130,185 |
| B — A + the LDF reorder only | 71.0 | 147.2 | 590.2 | 130,215 |
| C — crosspoint fold | 64.4 | 75.0 | 598.1 | 127,631 |
| D — fold + active list | 64.3 | 60.8 | 202.3 | 114,675 |

(cycles/sample per strip; chain figure is cycles/block)

| step | whole chain |
|---|---|
| LDF reorder / Block-1 spill (A→B) | **+30 cycles/block — nothing** |
| crosspoint fold (A→C) | −2,554 (−79.8 cycles/sample) |
| active list (C→D) | −12,956 (−404.9 cycles/sample) |
| **total (A→D)** | **−15,510 cycles/block, −484.7 cycles/sample** |

Two things worth reading off this rather than asserting:

- **Spilling DM into Block 1 costs nothing measurable.** A and B are the same
  code at different addresses and differ by 30 cycles/block over the whole
  chain, which is the noise floor itself. The LDF reorder was free.
- **The per-node figures carry layout noise; the chain figure does not.**
  FADER_PAN is byte-identical in C and D yet reads 75.0 and 60.8 — RTG's code
  grew, which moved later objects and changed instruction-fetch alignment for
  nodes that run 32× per block. The trustworthy FADER_PAN number is the A→C
  one, **−72.6 cycles/sample**, and it agrees almost exactly with the two
  `_mrf_rns28` calls the fold deleted (~36 cycles each). GAIN's −7.3 likewise
  matches the ~7 instructions of mute and polarity test removed. Where a
  per-node delta and the chain delta disagree, the chain delta is the one to
  quote.

**In the converted build the list is neutral**: 63,156 → 63,203 cycles/block,
+47, inside noise. There the accumulate already ran once per block, so
compacting saves about what building the list costs. It is kept in both builds
because it is one code path and the doctrine is the same; the measurement is
recorded so nobody re-derives it.

**Capacity.** The 786 MHz ledger arithmetic is on the CONVERTED build, which is
unchanged — **that ceiling stays 10 and the 32-in-one verdict is untouched.**
The gain here lands on the shipping image, which is the per-sample build, and
there it is worth a whole strip.

#### 3. Dynamics guard fixes re-verified — and my own count was wrong

**Correction: it was 68 nodes, not 132.** The naive scan counted any surviving
`_sample_idx == 0` guard under DSP4_BLOCK_KERNELS. That is not sufficient:
chip 1's COMPRESSOR and GATE emit a block kernel that DRIVES `_sample_idx`
itself before reaching the guard, so their guard fires exactly once per block
and was never dead. 64 of the 132 were those, and they are false positives.

**Worse, blanket-removing the guard was a regression for them, and the bench
found it.** GATE's sidechain-filter fallback hands the block to the per-sample
body **32 times**, driving `_sample_idx` 0 then 1 — so with the guard gone the
entire parameter conversion ran on every sample of the block whenever a gate
had its sidechain filter enabled. The guard decision is now made PER NODE, from
whether that node actually has a block kernel: kept where something drives the
index (chip 1 COMP and GATE, 64 nodes), dropped in the block build everywhere
else. The scan reports 0 genuinely-dead guards. **The per-sample image is
byte-identical across that correction** (`a2fcda81...`), which is the proof it
touches only the converted build.

Genuinely affected, and now verified: ROUTING 32 and TALKBACK 2 on chip 1;
AUX_LIM 12, GRP_COMP 4, GRP_GATE 4, MAIN_COMP 1, MAIN_LIM 1, MAIN_OCOMP 4,
MAIN_OLIM 4, MIX_MAIN 2, SUB_COMP 1, SUB_LIM 1 on chip 2 — 68 in all.

On the part, converted build, `tools/pi/dsp4_dyn_convert.py`, writing two host
floats per class and requiring the converted Q0.31 shadow to track both (one
value could match an initialiser by luck; two cannot):

    DYNAMICS BLOCK-RATE CONVERSION RUNS (0 of 2 classes failed)     chip 1
    DYNAMICS BLOCK-RATE CONVERSION RUNS (0 of 9 classes failed)     chip 2

covering GATE and COMP on chip 1 and AUX_LIM, GRP_GATE, GRP_COMP, SUB_COMP,
SUB_LIM, MAIN_COMP, MAIN_LIM, MAIN_OCOMP and MAIN_OLIM on chip 2 — every
dynamics class in the affected set.

**A trap the probe had to learn, recorded because it produced a false
failure first:** every one of these nodes tests its on-flag BEFORE the
block-rate conversion and bypasses the whole body when it is clear, so a
bypassed node does not convert. The first run followed `dsp4_send_proof.py`,
which switches the gate and compressor off to get a transparent strip, and read
two stuck shadows as a conversion failure. The probe now enables the node
first, and peeks the HOST FLOAT as well as the shadow so that "the write never
landed" and "the conversion never ran" cannot be confused.

#### 4. The `H1S*` verify lines — no app regression; the instrument was mine

**There is nothing to name, and the earlier entry was wrong.** matrix-app has
never logged `H1S*` to the systemd journal: `journalctl -u matrix-app` returns
zero matches across the whole retention window, and the binary (2026-08-18,
unchanged) carries no such strings. It logs to **`/home/app/logs/log`**, which
the 2026-08-22 dispatch block already specified — "confirm the three MCUs
verify in /home/app/logs/log". I grepped the journal, found silence, and
reported the absence as a possible bench-instrumentation regression. It is not
one.

The bench was in fact verified at the time: `MCU verified: // H1S1 DSP`,
`// H1S4 SW Left`, `// H1S3 SW Right` at 20:42:12, all three `MCU boot
verified` at 20:42:18.

To stop this recurring, `smoke-checklist.md` now carries a **Bench hand-back**
table that names the instrument for every check — firmware md5, boot verdict,
CPLD IDCODE, GPIO release, matrix-app, and the MCU grep — and states plainly
that the MCU check reads `/home/app/logs/log` and not the journal. The two
bench helpers this session had been running out of scratch are committed as
`tools/pi/dsp4_boot_verify.sh` and `tools/pi/dsp4_probe_after_boot.sh`.

#### Proven on the part, this pass

Shipping (per-sample) build with the active list, `dsp4_xpoint_chain.py`:

    CHAIN BIT-EXACT (0 checks mismatched)

now including pan 0.0 and pan 1.0 — which drive one main-bus coefficient to
exactly zero, so the crosspoint is absent from the list entirely and the bus
must read 0 — and a live-count sweep over main/sub/group that reads
2 → 3 → 4 → 2 → 2 as the assignment changes. Negative control passing.

Converted build, `dsp4_send_proof.py`: `SENDS WORK (0 checks mismatched)`,
all four pickoffs, negative control passing.

#### Bench hand-back

Shipping firmware restored byte-identical (`25a1afed...` / `7052c5d1...`),
BOOT_STAGE 7 at 1500/s with DMA0_STAT 0x00006200 and SPORT0_ERR_A clean; CPLD
IDCODE 0x020a30dd on the untouched shipping bitstream; GPIOs released;
matrix-app active with **all three MCUs verified** (H1S1, H1S3, H1S4 at
22:08:21) — and the documented second-restart pattern held again, the first
restart announcing only H1S4.

#### Still not done

- The converted build's fabric is where the 786 MHz capacity lever lives and
  this work did not move it. The next item there is the one the ledger already
  names: the fabric against its 40k target.
- `dsp4_xpoint_chain.py` exercises strip 1 only. Summing several strips into one
  bus is where the folded form should be strictly MORE exact than the old one
  (one rounding at the bus instead of one per source) and that has not been
  measured.
- TALKBACK's block-rate HPF coefficient refresh is in the genuinely-affected 68
  but was covered by the static scan only, not on the part; it has no attack
  parameter to drive the generic probe with.


### Outcome 2026-08-27 (evening) — crosspoint-coefficient audit + enforce

**Audit method.** Scanned the EMITTED node ASM, not the generators, resolving
`#if DSP4_BLOCK_KERNELS` for both builds and separating the per-sample region
from the control-rate one, then counted control-state reads inside MAC paths
and round-and-saturate stages per sample. That is what made the findings below
countable rather than anecdotal, and re-running it is the check that the folds
landed: it now reports zero in-scope violations in both builds.

#### The folds (the mandate's actual task)

| violation | where | fold |
|---|---|---|
| `_mute` + `_polarity` tested per sample | GAIN × 32 | into `_gain_q` at control rate |
| `_fdr_mute` tested per sample | FADER_PAN × 56 (both chips) | into `_fdr_gq` at control rate |
| fader → pan → unity-MAC, three round/saturate stages | FADER_PAN → ROUTING | pan leg IS the main-bus crosspoint coefficient; two stages deleted |
| `_rtg_main/sub/grp/aux/fx_on` read in the accumulate path | ROUTING × 32 | folded into per-crosspoint coefficients (`_rtg_mlq/_mrq/_subq/_grpq`, and into the send shadow) |
| pickoff enum decision tree in the accumulate path | ROUTING × 32 | resolved to a source ADDRESS at control rate (`_rtg_aux_src`, `_rtg_fx_src`) |
| `_auxin_on` tested per sample, and the whole float→Q4.28 conversion running per sample | AUX_INPUT × 12 | assign folded into `_auxin_q`; conversion moved to control rate |
| L/R levels converted per sample; ramp quad unrepresentable | MONITOR | control-rate conversion, two independent ramp quads |

Polarity folding is also the more correct form, not just the cheaper one:
`fixed_ref.gain(x, g)` with g negative is `sat(rns(x*-g))`, whereas the old
per-sample code computed `-sat(rns(x*|g|))`. Those differ by one LSB when the
product lands on a rounding tie, because `rns` rounds half toward +inf and that
is not symmetric under negation. The folded form is the reference form.

The main-bus fold is bit-identical for a single source and strictly better for
several: the old path rounded `mono * pan` into `_buf_L` and then accumulated
that with a unity coefficient, so N sources rounded N times; the folded path
accumulates `mono * pan` exactly in 64 bits and rounds once at the bus.

#### Three defects found on the way, none of them mine, all severe

**1. The ramp-stride table matched only 610 of the ramped parameters, and
every GAIN, FADER_PAN and MONITOR ramped parameter was unsettable over SPI.**
Proven on the part before I changed anything: a ramped write of 0.5 to SPI
0x0000 left `_gain_target` at 1.0, and reading the dispatch and stride tables
off the running chip showed the dispatch ADDRESS correct and the stride ZERO.
Stride 0 means "plain word, direct write", so the value went straight into the
value word and the node's own block-rate code then did
`if frames <= 0: value = target` and clobbered it from a target nothing had
set. Two independent causes in one regex: it was anchored at column 0, so
generators that emit their `.var` lines INDENTED (FADER_PAN among them) matched
nothing at all; and where it did match it assumed the value symbol is the
target's name minus `_target`, which is false for GAIN (`_gain_coeff` vs
`_gain_target`). The "fail if no ramped params were found" guard passed
throughout, because ROUTING, TUBE_SAT and TALKBACK do emit at column 0 and
supplied 610 entries between them.

Fixed by pairing on LAYOUT rather than names — `_ramp_set_target` addresses
the companions at +s/+2s/+3s from the VALUE, and the node emits the value
immediately before its target, so that adjacency IS the contract and it is what
the scan now reads. It also validates the quad (value, target, step, frames,
consecutive, same width, same family stem) and requires the number of quads
recognised to equal the number of `_frames_` declarations in the file, so a
node whose layout changes is an error rather than a silent zero. Counts:
chip 1 610 {1: 34, 6: 192, 12: 384} → **738 {1: 162, 6: 192, 12: 384}**;
chip 2 28 {1: 28} → **86 {1: 86}**. Re-proven on the part: a ramped write of
0.5 to 0x0000 now lands, and the full chain harness passes.

That check immediately caught two more things. `_gate_gain_target_q` and
`_eq_xfade_step` contain the suffixes but are not ramps, which is why the
recogniser needs the complete quad and not a name match. And MONITOR really
was shaped wrongly: `_mon_level_l` and `_mon_level_r` shared ONE step and ONE
frames word with their targets interleaved, and no single stride can describe
that — so both monitor levels were unsettable for the same reason. Each level
now carries its own quad.

**2. Nodes carrying a block-rate guard that never fires in the converted
build.** (Counted as 132 here; **corrected to 68** in the later outcome above —
chip 1's COMPRESSOR and GATE drive `_sample_idx` from their own block kernels,
so their guard was never dead, and removing it there was itself a regression.) `_sample_idx` is left at 31 by the scatter loop, so a surviving
`_sample_idx == 0` test never fires and the node runs on its `.var`
initialisers. This was RECORDED as a trap on 2026-08-22 but never enumerated
or fixed. Enumerated now: COMP 32, GATE 32, RTG 32, TALK 2 on chip 1; AUX_LIM
12, GRP_COMP 4, GRP_GATE 4, MAIN_COMP 1, MAIN_LIM 1, MAIN_OCOMP 4, MAIN_OLIM 4,
MIX_MAIN 2, SUB_COMP 1, SUB_LIM 1 on chip 2. The one in this mandate's path is
ROUTING: its send ramps never advanced and its 576 aux/fx crosspoint
coefficients were never computed, so **no send could carry signal in the
converted build at all.** The guard is now `#if !DSP4_BLOCK_KERNELS` in all
six generators that emitted it. Landed on its own first, and the default image
came out **byte-identical** (11f166ab.../89fbe274...) — that md5 is the proof
it touches only the converted build.

**3. The converted build's aux/fx pickoffs read garbage, and BLK_TAP_TRIM was
never written.** In block form the pickoff handed `_acc64_mac_blk` the address
of a SCALAR tap and let it walk 32 words off the end of it; only the default
post-fader pickoff, which resolves to a real pool slot, was correct.
`BLK_TAP_TRIM`/`BLK_TAP_EQ`/`BLK_TAP_PREFDR` were declared in `blk_pool.h` for
exactly this and two of the three were written by EQ and DLY but never read.
ROUTING now resolves to the pool slots, and GAIN publishes its post-trim tap as
a block (one store per sample).

#### The DM ceiling was an LDF ordering artifact

The first build of the fold failed with `Out of memory in output section
'sec_stak'`, which is what the 2026-08-24 note "DM headroom is under ~1,600
words" was describing. Measured: the true margin at that point was **262
words**, and `mem_block1_bw` — the overflow region `sec_dmda_ovf` exists to
reach — was at **0%** with 180,224 bytes free and had never received a single
word. Output sections mapped to the same region are placed in declaration
order, and `sec_stak` was declared LAST, so `sec_dmda` took Block 0 greedily
and the stack reserve got the remainder. Reserving the stack FIRST fixes it:
chip 1 now sits at Block 0 89.7% + Block 1 11.9%, 178,840 bytes free overall.
`ldf_stack_space`/`ldf_stack_length` are read by the startup code so the stack
follows the reserve; nothing hard-codes the address.

Worth stating plainly: **the converted build did not link at HEAD.** Today's
stride table pushed it past the same ceiling, so the DSP4_BLOCK_KERNELS build
was unbuildable until this change.

#### Proven on the part

Shipping (per-sample) build, `tools/pi/dsp4_xpoint_chain.py`, negative control
passing (halving the gain must change the reading, and does):

    CHAIN BIT-EXACT (0 checks mismatched)

— all 7 level/pan points exact against the reference arithmetic, FDR mute
folding to a zero coefficient and back, GAIN polarity folding and back.

Converted build, `tools/pi/dsp4_send_proof.py`, negative control passing (send
off must give a silent aux bus, and does):

    SENDS WORK (0 checks mismatched)

— all four pickoffs (post-fader, post-trim, post-EQ, pre-fader), each at two
send levels, with the crosspoint coefficient read back exactly and the resolved
source address landing on the right pool slot. This is the first time a routing
send has carried signal in a block-kernel build.

Both images: BOOT_STAGE 7, FRAME_COUNT 1500/s, DMA0_STAT 0x00006200,
SPORT0_ERR_A 0x00000000 — the same as the control image.

#### Cycle deltas against the strip-fusion ledger

Measured with `profile.sh` (TCOUNT, DSP4_NODE_LIMIT 8/9/10, DEC=32) on the
CONVERTED build, which is what the ledger's capacity arithmetic uses. Three
variants, so the correctness cost and the fold cost are separated rather than
lumped:

| ROUTING variant | cycles/block | cycles/sample |
|---|---|---|
| HEAD — send prep never ran, sends dead | 2,617 | 81.8 |
| HEAD + dead-guard fix — prep runs, sends work | 3,196 | 99.9 |
| + crosspoint fold (this work) | 3,667 | 114.6 |

| FADER_PAN | cycles/block | cycles/sample |
|---|---|---|
| before | 1,908 | 59.6 |
| after (two round/saturate stages deleted) | **1,011** | **31.6** |

So ROUTING costs +579 cycles/block to make the sends work at all — that is a
correctness price, not a regression, and HEAD's cheaper number is for a graph
that cannot route a send. The fold itself adds a further +471 cycles/block of
control-rate prep and buys a MAC path with no control-state reads in it. Against
the honest baseline (prep live) the strip nets **−426 cycles/block, −13.3
cycles/sample**.

**Capacity arithmetic, stated so it cannot be over-read.** At 786.432 MHz the
ledger has 406,106 cycles/block available for channels and a measured 1,269
cycles/sample/channel, giving 10. This takes it to ~1,256, i.e. 10.1 channels.
**The ceiling stays 10 and the 32-in-one verdict is unchanged.** Every cycle
counts toward PW #1, but the honest headline of this work is correctness, not
capacity.

#### Not done, and deliberately

- ~~**The shipping build's ROUTING still walks all 22 crosspoints per sample.**~~
  DONE the same evening — see the later outcome above: the compacted list
  landed, ROUTING went 589.2 → 202.3 cycles/sample and the shipping ceiling
  moved from 2 strips to 3. Original note follows.
- **The shipping build's ROUTING still walks all 22 crosspoints per sample.**
  Each iteration is cheaper now (one coefficient load instead of a coefficient
  plus an assign word, no pickoff tree) but it is still a per-sample loop. The
  doctrinal end state is a COMPACTED active-crosspoint list built at control
  rate, so the audio path iterates only over live crosspoints. That needs
  ~2,100 words of DM, which is why it was not attempted before — and the LDF
  fix above now makes the room available. Recommended next.
- ~~**The per-sample build's cycle delta was not measured.**~~ MEASURED the
  same evening across four tree states — see the later outcome above.
- **MONITOR's sample path is still MONO** and uses the L level only, so
  `_mon_level_r` is settable and has no effect. Making MONITOR stereo is a
  graph change, not a coefficient fold, and was left alone.
- **The remaining dead-guard nodes on the dynamics classes** — re-verified on
  the part in the later outcome above, and the count corrected from 132 to 68.
- **The "3 MCUs verified" bench step could not be reproduced.** **WRONG, and
  corrected in the later outcome above:** matrix-app logs to
  `/home/app/logs/log`, not the journal, and all three MCUs had in fact
  verified at 20:42. The rest of the hand-back stands: matrix-app active, CPLD
  IDCODE 0x020a30dd on the shipping bitstream (never touched), GPIOs released,
  shipping .ldr byte-identical to how the session found them.

#### Artifacts

| | |
|---|---|
| default image, this work | chip1 `24c45566b151849e57e69b5b8c764cad`, chip2 `302910134ba62681a52f3aa822ca4e8d` |
| dead-guard fix alone | byte-identical to HEAD (`11f166ab...` / `89fbe274...`) |
| bench restored to | chip1 `25a1afed0e0097ee94e04f0d9be8b383`, chip2 `7052c5d1810975f5b64130c73a048a46` |
| CPLD | `dsp4_logic.a1f6672af6c3`, IDCODE 0x020a30dd verified, untouched |
| new probes | `tools/pi/dsp4_xpoint_chain.py`, `tools/pi/dsp4_send_proof.py` |


### Outcome 2026-08-27 (rev 2, after bench access) — R1 re-proven, F1 fixed, F3 found and fixed, GAIN unblocked

**Bench access correction:** the `MW-D32-*` aliases in `~/.ssh/config` are
stale (old 192.168.0.x subnet, per-unit IdentityFile the unit no longer
accepts). The rig is `app@192.168.1.219` (MW-D24-2) with the default
`id_ed25519`. First pass this session wrongly reported the bench
unreachable; everything below was then run on the part.

**F3 — THE HEADLINE, and it was not in the review or the queue: a ramped
write to an ARRAY-valued parameter wrote its ramp state onto the
neighbouring crosspoints and never reached its own.** `_ramp_set_target`
assumed target/step/frames sit at +1/+2/+3. That holds for a SCALAR
parameter, which emits them right after the value. The routing sends do not:
they emit four PARALLEL arrays —

    _rtg_aux_send        [12]   <- the dispatch table points in here
    _rtg_aux_send_target [12]
    _rtg_aux_send_step   [12]
    _rtg_aux_send_frames [12]

— so element i's companions are 12/24/36 words away, not 1/2/3. A ramped
write to AuxSend[1] therefore stored target/step/frames onto AuxSend[2],
[3] and [4]'s LEVELS, and left its own target/step/frames untouched at
zero. The block-rate code reads the parallel arrays and runs
`if frames <= 0: level = target`, so every send snapped back to its
zero-initialised target every block. Net effect: **the aux and fx sends
could never be set over SPI at all**, and trying corrupted three
neighbouring crosspoints on the way. Scope: `_rtg_aux_send` (stride 12) and
`_rtg_fx_send` (stride 6) across 32 RTG nodes on chip 1 = **576 crosspoint
controls**, i.e. every send in the routing layer; the 130 scalar ramped
params were already correct after `d2e4dc6`. This sits directly in the
08-25 crosspoint-coefficient mandate's path.

**The fix — one stride per dispatch entry, derived from the artifact, not
asserted.** `gen_dsp.py` now emits `_spi_dispatch_cN_stride[]`, parallel to
and same-indexed as the dispatch table: 0 = plain word (direct write), s ≥ 1
= ramped with target at +s, step at +2s, frames at +3s. Scalars are stride
1, so their behaviour is unchanged by construction. The map is built by
SCANNING THE EMITTED NODE ASM for each `_..._target_<nid>` declaration and
its array width — restating "which params ramp and how wide" by hand in a
second generator is the same duplicated-assumption bug this table exists to
fix, and it would drift silently; reading the artifact cannot. It fails
loudly if the node ASM is missing or yields no ramped params. Emitted
counts, visible in the file header: chip 1 610 ramped entries
{1: 34, 6: 192, 12: 384}, chip 2 28 {1: 28}. `_ramp_set_target` takes the
stride in r4 (stashed to r12 immediately — the slew path loads the current
value into f4, and f4 IS r4); both SPI handlers look the stride up and pass
it. Cost: one word per dispatch entry — chip 1 +19 KB, chip 2 +7.9 KB of DM.
Packing to 4 bits is available later if DM gets tight; correctness first.

**F1 — fixed per the hub ruling (generator flag table), and it fell out of
the same table.** `.spi_instant` wrote only the level word, so a profile-0
write to a ramped parameter was undone within one block. It now consults the
stride: 0 → direct write as before; s ≥ 1 → routed through
`_ramp_set_target` in Instant mode, which sets level AND target and clears
frames. A ramp profile aimed at a stride-0 word falls back to a plain write
rather than scribbling on its neighbours.

#### Proven on the part (chip 1 + chip 2, DSP4_STRIPS=1, BOOT_STAGE 7, 1500 blocks/s, SPORT/DMA clean)

    A  R1  0x071C ramp_id=1   target 0.5 landed at 0x951DE, level converged
                              1.0 -> 0.5 (caught mid-ramp at 0.529955),
                              step -0.0013, _auxin_on preserved        PASS
    B  F1  0x071C ramp_id=0   level AND target = 0.25, frames 0, and it
                              SURVIVED ~1500 blocks (pre-fix: reverted
                              within one block)                        PASS
    C  F3  0x0066 ramp_id=1   AuxSend[1] -> send[0] 0.75, target[0] 0.75 at
                              0x92C36 (base+12), step[0] 0.00586 at
                              0x92C42 (base+24); neighbours send[1..3]
                              UNCHANGED at 0                           PASS

Linked addresses confirm the stride in the image: `_rtg_aux_send_C1_RTG_01`
0x92C2A, target 0x92C36 (+12), step 0x92C42 (+24), frames 0x92C4E (+36).

**GAIN harness family — UNBLOCKED.** Full −60…+18 dB sweep through the
ramped path, DC 0x00100000 in, captured over the loopback bitstream:

    -60 dB   1048 (exp 1048.6)      0 dB  1048576 (exp 1048576, BIT-EXACT)
    -36 dB  16616 (exp 16618.8)    +6 dB  2092184 (exp 2092184.2)
    -12 dB 263392 (exp 263390.4)  +18 dB  8329136 (exp 8329135.2)

Monotonic across all 13 points, unity bit-exact, worst error 549 ppm at
−60 dB where the output is only 1048 counts (sub-LSB for Q4.28) and ≤ 10 ppm
from −24 dB up. Compare 2026-08-23, which produced *identical* output at
every setting. One harness note recorded: the sweep does not set
`_auxin_on_C2_PI_IN`, which initialises to 0 and forces the node output to
zero, so the first run reads NONE at every level regardless of gain —
write 1 to 0x071D first.

**Not caused by this change, re-confirmed:** the post-CONFIG_COMMIT link
desync reproduces identically on the ORIGINAL bench image, and clears on the
second boot+config cycle. matrix-app needed its usual SECOND restart to
announce all three MCUs (first gave H1S3 only) — another occurrence for the
hub's mx26 app-bug tally.

**Bench restored and verified:** shipping CPLD `dsp4_logic.a1f6672af6c3`
(md5 dd1e09185804cb2e451d5089cdd56be3) re-flashed, IDCODE 0x020a30dd
verified, GPIOs `a0`; shipping firmware restored byte-for-byte
(25a1afed0e0097ee94e04f0d9be8b383 / 7052c5d1810975f5b64130c73a048a46, kept
in `~/dspboot/bak-20260827/`); matrix-app active, H1S1/H1S3/H1S4 all
verified. NOTE for the hub: the image on the bench is NOT the recorded
production build — this tree reproduces production
(0df38e8270c14e01ba6ffc57c2122563 / 130ddb0f546966b38ec23b6d9b923748)
exactly, but `~/dspboot` held a larger Aug-24 build. Left as found.

**Default image necessarily MOVES** (this is a behaviour fix, not a
refactor): 11f166ab3cd701f76e3b7b38b097aa10 /
89fbe274eb12dd45951a2f9d23be7c8f. Both generators re-verified deterministic;
`check-contract-drift.sh` clean.

#### F2 closed 2026-08-27 — D24 ramp engine regenerated from the fixed generator

Per the generated-files mandate: regenerated, not hand-edited.
`MW/D24/DSP/SHARC/src/ramp_engine.asm` and `ramp_tables.asm` re-emitted from
`tools/dsp/dsp_codegen.py`, so D24 now carries BOTH the 08-23 post-modify fix
and today's stride fix.

    ramp_engine.asm   a497c0cc50010dbce4a8fc4cb0c1fc63 -> fa9278c2ae595ab96ad1bd5f7f9bdbf8
    ramp_tables.asm   e5eb1fa6a0df779bc2a94644fdd1c8bf -> b60fcb907ca4b3248e845872987d4ae8

`gen_ramp_engine()` takes no product argument, so the emitted
`ramp_engine.asm` is **byte-identical to D32's** — the same
`fa9278c2ae595ab96ad1bd5f7f9bdbf8` that was proven on the part today by
tests A/B/C and the GAIN sweep. `ramp_tables.asm` also dropped five stale
`.global _ramp_profile_<name>` aliases whose definitions the generator
stopped emitting (declared, never defined — a latent link hazard); nothing in
D24 referenced them. Regeneration is idempotent, and the change is confined
to those two files.

**Scoped deliberately to the ramp files, not a whole-tree regenerate.** A
full `dsp_codegen.py` run against `MW/D24/DSP/SHARC/dsp.csv` rewrites **212
files** — it would port D24's entire lagging tree forward (fixed-point
conversion, block kernels, bus accumulators, lane config), which is a
different and much larger piece of work than F2 and is not reviewable as part
of it. Flagged for the hub as its own decision.

**Build: the two files assemble clean, but D24 STILL PRODUCES NO IMAGE, and
that is pre-existing.** `MW/D24/DSP/SHARC/build.sh` is the retired
**Wine-wrapped** CCES flow (`~/.wine/drive_c/CCES/asm21k.exe`); it has not
been touched since the initial commit (`06c3f0f`, 2026-04-21) and fails with
207 errors at baseline, before any change of mine — D32 migrated to native
Linux CCES and D24 never followed. So "build clean" was verified the only way
it honestly can be: both files assembled standalone with the native
`easm21k -proc ADSP-21564` for `CHIP_ID` 1 and 2 — 4 of 4 OK, 0 errors, 0
warnings (ramp_engine 1108 B, ramp_tables 956 B each). Porting D24's build.sh
to native CCES is a separate item.

**Bench re-verification: there is no runtime path to exercise, and I did not
manufacture one.** Three independent reasons: D24's tree produces no image
(above); `_ramp_set_target` has **no callers anywhere in D24** — the tree has
no `spi_handler.asm` and no `dsp_params.asm`, so the SPI dispatch layer does
not exist there; and no D24 SHARC image runs on any bench (the reachable unit
reports hostname `MW-D24-2` but carries the DSP4 card running D32 firmware).
Booting something and watching a link answer would be exactly the false pass
this file already records from 08-22. The real evidence is stronger and it is
on the record above: the emitted file is byte-identical to the D32 one
verified on the part today. What remains unverified is D24-specific
integration, which does not yet exist — when D24 gains an SPI handler it must
supply the stride in r4 and needs its own `_spi_dispatch_cN_stride` table,
or `_ramp_set_target` will scatter companion words at whatever offset r4
happens to hold.

### Outcome 2026-08-27 (rev 1) — R1 was already fixed; R2 landed; two new findings

**R1 — the bug was root-caused and fixed on 2026-08-23, an hour after the
outcome the review quotes.** Commit `d2e4dc6` ("FIX: ramp engine wrote one
word low — dm(i4, N) is post-modify, not indexed"), 2026-08-23 16:09. The
review (08-25/26) and the HUB REVIEW block read the 15:0xZ bench outcome at
the bottom of this file and did not check the log, so R1 was carried forward
as open. It is not.

**Which candidate it was — (3), the offset convention inside
`_ramp_set_target`.** Evidence, read off the emitted artifacts rather than
their comments:

- *Candidate (1), the dispatch-table address for `0x071C`: CLEAN.*
  `_spi_dispatch_c2` is a symbolic array; index 1820 = 0x071C is
  `_auxin_level_C2_PI_IN` (dsp_params.asm:2527) — the LEVEL, matching its
  comment. The 08-23 note's inference that `r0 = 0x951DC = _auxin_on` was
  wrong.
- *Candidate (2), the handler's `r0`: CLEAN.* spi_handler.asm does
  `i0 = _spi_dispatch_c2; m0 = r2; modify(i0, m0); r0 = dm(i0, 0)` — a
  straight table load, no arithmetic that could bias it by a word.
- *Candidate (3), `_ramp_set_target`: THE FAULT.* It used `dm(i4, 1)` /
  `dm(i4, 2)` / `dm(i4, 3)`, which on SHARC is POST-modify: it writes the
  address currently in i4 and THEN adds the modifier. So target landed on
  [r0+0] (level), step on [r0+1] (target), frames on [r0+3] by luck. With
  `r0` correctly = level, step lands in the target slot at 0x951DE — exactly
  the 1/128 → 1/129 the bench saw. The two clean candidates and the observed
  address agree only on this explanation.

**Blast radius: every ramped cell, uniformly — runtime, not generator.**
`_ramp_set_target` is one shared routine that both chips' handlers call for
every ramped write; the dispatch table supplies only the base pointer, and
the generator's per-node variable order (`on, level, target, step, frames`,
verified on C2_PI_IN) is consistent across nodes. So there was no
per-cell variation — 392 of 670 nodes carry a ramping profile (GainFast 175,
EqSafe 115, DynSafe 96, GainSafe 6) and all were hit identically.

**The fix is in the GENERATOR, not just the .asm.** `d2e4dc6` touched only
`ramp_engine.asm`; `gen_ramp_engine()` in dsp_codegen.py picked the same text
up in `2ef49fd`. Verified by regenerating the whole D32 tree into a scratch
dir: all 711 files byte-identical to the working tree, so the fix survives
the next regenerate rather than being edited away.

**Still owed on R1: the on-the-part re-verification and the GAIN harness
family re-run.** The original fix was proven over SPI on both chips by
known-word write + full read-back (recorded in `d2e4dc6`: chip 2 `0x071C`
write 2.0 → target 2.0/level 2.0/step +0.0117; chip 1 `0x0000` caught
mid-ramp at level 1.402, frames 42, settling to 2.0). This session could not
repeat it or run the harness: the bench Pis are on 192.168.0.0/24 and this
machine is on 192.168.1.0/24 with no route (`MW-D32-1/-2` both time out).
`tools/pi/dsp4_ramp_proof.py` is the ready-made proof script for whoever is
next at the bench.

**R2 — codegen fail-loudly: LANDED.** `GENERATORS.get(node['type'],
gen_generic)` is replaced by a format-aware lookup that raises `ValueError`
naming node type, id, chip and label; `gen_generic` (the `/* TODO:
implement */` stub) is deleted, with no remaining references. The check
resolves FIXED_GENERATORS first and raises only if neither table serves the
active format, so a fixed-only generator is still legal. Proof both ways:
- *Positive:* regenerated D32 tree md5 manifest is unchanged —
  `2703989fc79e72cac757d99778561a96` before and after, all 711 files
  byte-for-byte identical. No known node type changes behaviour.
- *Negative:* a dsp.csv row with type `WIDGET_XYZ` now aborts generation
  with `no fixed codegen for node type 'WIDGET_XYZ' (node C1_IN_01, chip 1,
  label 'Ch 1 Input')` instead of silently emitting a dead node.
No current node type used the fallback (all 25 types in dsp.csv are in
GENERATORS), which is why the image could not move.

#### New findings from this pass (not fixed here — both need a decision)

- 🟢 **F1 — FIXED 2026-08-27 (hub ruling: generator flag table). Was: a
  profile-0 write to a ramped parameter is silently discarded.** The SPI
  handler intercepts `RAMP_INSTANT` before `_ramp_set_target` and takes
  `.spi_instant`, which writes ONLY the level word (`dm(i1, 0) = r1`). For a
  node with a ramp triplet the block-rate code runs `if frames <= 0: level =
  target` every block, so the write is undone within one block period —
  which is what "a direct write to a ramped parameter does nothing" was on
  08-23. `d2e4dc6` fixed `.ramp_instant` INSIDE `_ramp_set_target`, but that
  label is unreachable from SPI: profile 0 is intercepted first, and
  profiles 1–4 all carry mode ≠ 0 (ramp_tables.asm). Scope is exact — the 48
  `InstantCtl` nodes have no triplet (verified: zero target/step/frames refs
  in their node .asm) so the direct write is correct for them; the 392
  ramped-profile nodes lose the write. Severity is below R1: it is a silent
  no-op, not the state corruption R1 caused. **Not fixed here because the
  clean fix spans the generator contract** — the handler cannot tell a
  triplet-bearing entry from a bare scalar without a new generator-emitted
  parallel flag table (e.g. `_spi_ramped_c2[]`), and the hand-back rule for
  this dispatch reserves generator-contract changes for the hub. Cheap
  alternative if the hub prefers it: rule profile 0 unsupported on ramped
  parameters and have the host always send a ramp profile.
- 🟢 **F2 — CLOSED 2026-08-27 (regenerated; see the F2 section above). Was: D24's `ramp_engine.asm` carried the pre-fix buggy form.**
  `MW/D24/DSP/SHARC/src/ramp_engine.asm` still has `dm(i4, 1)/(i4, 2)/(i4,
  3)`; last touched 2026-07-29 (`d2a264d`), i.e. it predates the 08-23 fix.
  `gen_ramp_engine()` takes no product argument, so a D24 regenerate would
  emit the corrected file — this is D24 tree lag, not a second generator
  bug. Left alone deliberately: regenerating D24 would churn a tree that is
  known to lag D32 and is out of this dispatch's scope. Anyone bringing D24
  SHARC up must regenerate before trusting a ramped write.


**PW DECISION (2026-08-24): TUBE SATURATION IS A PLUGIN, NOT A FIXED CHANNEL
FUNCTION.** Only a few selected channels will use it, so it comes out of the
basic strip for capacity purposes. Two levels to this and they are different:

- **Runtime, already supported.** `_tube_on_<nid>` is an SPI parameter and the
  per-block kernel already branches to a plain block copy when it is 0, so a
  channel with the plugin off pays only that copy today. Measure it before
  claiming it is free — a 32-word copy is not zero.
- **Removed from the graph — needs a CONTRACT change and the hub owns it.**
  The 32 `TUBE_SAT` nodes come from the matrix definition via the mx26
  contract into `dsp.csv`; `defs.lock` is authoritative and these files are
  never hand-edited here. Taking TUBE out of the fixed strip (and giving it
  to selected channels only) is an mx26 matrix-definition change. That is
  what actually recovers TUBE's cycles AND its DM state, so it is the version
  that counts for the 32-channel fit.

**RAIL MEASURED 2026-08-24 20:3xZ (PW, DMM at the DSP card, both chips
running at 983.04): +0.9 V rail = 0.87 V — INSIDE the 0.855–0.945 V window
with ~15 mV margin, DIL100 stack drop included. THE 983.04 OPERATING POINT
IS CLOSED FOR SHIPPING: grade KSWZ10 confirmed, CCLK verified, bit-exact,
real-time, thermally comfortable (heatsinkless, cool), regulator AP64501 at
~3x current margin, rail in-window under load. One opportunistic residual:
re-touch the rail at a confirmed max-strip load when the bench next allows —
the margin arithmetic says it stays inside, but a reading beats arithmetic.**

**PW BENCH OBSERVATION 2026-08-24 19:1xZ: SHARCs at 983.04 have NO heatsink
and run COOL to the touch under sustained operation — thermal half of the
power question CLOSED (consistent with ~0.7 W/chip at 0.9 V). REMAINING for
ship sign-off: the +0.9 V RAIL itself — voltage under load at 983 (must hold
≥ ~0.855 V) and ideally the motherboard regulator's current rating vs the
~1.5 A pair draw. One DMM reading whenever PW is next probing; until then
983 stays "enabled for measurement", 786 the one-flag fallback.
UPDATE (PW, 19:2xZ): the 0.9 V regulator is an **AP64501** on the Digital
schematic — a 5 A-class synchronous buck, so ~3× current margin at the
~1.5 A pair draw. Rating half CLOSED. The remaining reading is the rail
VOLTAGE at the DSP card under load at 983 — the risk is drop through the
DIL100 stack contacts and tracks at 1.5 A, not the regulator; ≥ ~0.855 V
at the card = ship sign-off for the 983 operating point.**

**PW BENCH READ 2026-08-24 18:4xZ: U5/U6 MARKING = ADSP-21564KSWZ10 (1 GHz
grade). The 983.04 MHz target is LEGAL on the fitted parts. ENABLE
`DSP4_CCLK_TARGET=983` with the same discipline as 786: measure CCLK off the
diag tick, prove stability on BOTH chips (sustained 1500 blocks/s, harness
chain 0 LSB, SPORT/DMA clean, thermal eye over a sustained run — the
power/thermal margin at 983 was flagged unchecked and gets checked now, IDD
figures from the datasheet vs the rails), then continue SIMD, fabric and the
ceiling AT 983.04 — budget 655,360 cycles/block, 32-in-one goal line ~497
cycles/sample/strip after fixed costs. 786 remains the fallback operating
point one flag away.**

**PW CLARIFICATION 2026-08-24 18:1xZ: TUBE IS AN OPTION, NOT FIXED-STRIP.**
Definition-vs-implementation drift found: diagram-master.csv (the signal-flow
authority) has NO tube node; only Chan TubeSat/TubeOn cells exist (default
off) — yet the generator emits C1_TUBE_xx into every channel. Per the
mandate, implementation follows the diagram: TUBE leaves the always-emitted
pipeline (conditionally emitted per product config; cells remain the option
interface), reclaiming its DM. Note: its ACTIVE cost was never measured —
measure it once, as an option, before any product enables it.

**PW DIRECTIVE 2026-08-24 16:3xZ: GAIN IS A SINGLE MAC — full strip fusion
is now the PRIMARY lever, ahead of everything except the in-flight comp-probe
fix. The generator emits ONE kernel per strip: samples stay in registers/MR
from GAIN through FDR, stages are bare MACs/cascades at 64-bit precision, the
Q4.28 round/saturate/store happens ONCE at the strip boundary. The ~14-cycle
per-stage exit tax (measured in GAIN's 18 cycles for 1 cycle of maths) is
deleted at every stage, not optimised. SIMD pairing applies to the fused
kernel. Then fabric to 40k, then the ceiling at 786.
ADDENDUM (PW, 16:5xZ): stage-to-stage handoff inside the fused strip is ZERO
instructions — stage N's result register IS stage N+1's operand; at most one
positioning move where the MAC accumulator demands it. Use the multifunction
lines (multiplier + ALU + two data moves per cycle) so next-stage state loads
overlap current-stage maths. Pipeline ORDER is hard-coded by the generator
from the product definition — no runtime stage dispatch inside a strip. The
fused kernel is judged against the floor: maths + persistent state +
delay-line memory + one load/store/round-saturate at the strip ends;
anything else emitted is structure to delete.**

**PW DECISION 2026-08-24 14:0xZ: GO WITH THE 800 MHz OPERATING POINT —
enable `DSP4_CCLK_TARGET=786` (786.432 MHz, legal on both speed grades;
983.04/KSWZ10 stays prepared but OFF). Budget becomes 524,288 cycles/block
(786.432 MHz / 1500). Sequence: enable, verify CCLK by measurement, prove
stability (audio 1500 blocks/s sustained + harness chain 0 LSB + thermal
sanity), THEN continue the fabric conversion and all capacity measurements
at the new operating point — every ceiling number from here on is quoted at
786.432 MHz.**

**PW PRIORITY (2026-08-24): #1 for the dsp side is CAPACITY-FIT — prove the
full product processing fits the chips as fabbed (goal line: 32 basic strips
real-time in ONE 21564; two on the card = margin/product headroom). Everything
else queues behind it. No FPGA, no block-64, no PCB change: efficiency of the
generated code is the lever, per the Matrix principle — single source,
generate the efficient form. The strip-fusion dispatch below is this
priority's execution; do not drift to other work until the fit is proven or
disproven with measurements.**

## HUB REVIEW 2026-08-27 — review.txt (accuracy/efficiency codebase review, 2026-08-25/26) folded into the queue   [status: 🟡 R1 🟢 fixed 08-23 + re-proven on the part 08-27 · R2 🟢 landed byte-identical · F1 🟢 fixed · F3 🟢 found+fixed (array-stride ramp corruption, 576 routing crosspoints — the review missed it) · F2 🟢 D24 ramp engine regenerated · R3–R5 open hardening · R6 opportunistic]

`review.txt` (committed 08-25, code suggestions §5 appended 08-26) reviewed
the contract layer, the codegen/tooling layer and the bit-exact reference
model at HEAD. The contract/governance layer (sync-from-mx26.sh,
validate-matrix-contract.py, check-contract-drift.sh,
regenerate-dsp-contract.sh) came back CLEAN — no bugs found, no action.
Capacity-fit (PW #1) is unchanged by this review: §3.1 only confirms the
already-tracked, already-measured ~10-channels-per-chip vs 32 gap and adds
no new measurements. The rest, folded into tracked items — §5's patches are
suggestions only, NONE applied; land each as its own small change:

- 🟢 **R1 — ramped-parameter writes land one word low (review §2.1 = the
  2026-08-23 15:0xZ outcome at the bottom of this file).** Already tracked;
  the review restates it as the top ACCURACY item in the codebase: one
  ramped SPI write stores the step in the *target* slot and zeroes the
  `_..._on` flag — silently mutes the channel, reboot-only recovery, blocks
  parameter testing of EVERY family after GAIN. Root cause still not
  isolated (dispatch-table address vs `r0` computation vs `_ramp_set_target`
  offset convention). **RESOLVED — and was already resolved when the review
  was written:** commit `d2e4dc6` (2026-08-23 16:09) fixed it; the cause was
  the `_ramp_set_target` offset convention (`dm(i4, N)` is post-modify, not
  indexed). Dispatch-table address and handler `r0` both verified clean.
  See the 08-27 outcome above. Residual: bench re-verification + GAIN
  harness re-run still owed, and F1 (profile-0 writes) is still open.
- 🟢 **R2 — codegen must fail loudly on unknown node types (review §2.2,
  patch §5.1).** `GENERATORS.get(node['type'], gen_generic)`
  (dsp_codegen.py ~7748) silently emits a `/* TODO */` stub for any unknown
  type — violates the no-fallback policy that the contract layer already
  enforces. Small change: raise with node context; delete `gen_generic` or
  make it explicit opt-in. **DONE 2026-08-27** — raises with type/id/chip/
  label, `gen_generic` deleted, regenerated image byte-identical
  (manifest md5 `2703989f…` unchanged).
- 🔴 **R3 — gen_dsp_csv.py error hardening (review §2.4, patch §5.2):** the
  GEQ-insertion `next(...)` raises bare StopIteration when the graph is out
  of sync → contextual ValueError; sport_map.json pre-flight-validated once
  at load (collect all inconsistent entries) instead of asserted per use.
- 🔴 **R4 — dsp_validate.py tightening (review §2.5, patch §5.3):**
  duplicate node IDs must be rejected, not reported once and re-processed;
  `parse_id_list()`/`parse_params()` cross-checked against the known
  node-id set and a per-type expected-param-keys table so malformed dsp.csv
  rows cannot flow through to codegen.
- 🔴 **R5 — fixed_ref.py: silent sentinel + knee boundary (review §2.6,
  patch §5.5):** `log2_q()` returns a fixed sentinel for `x <= 0` — raise
  instead, or prove the sentinel unreachable by legitimate values and
  document it; add a soft-knee boundary test at `over == ±half_knee`. This
  file is the SHARC/FPGA bit-exactness reference — silent behaviour here is
  contract risk.
- 🔴 **R6 — opportunistic cleanups (review §2.3, §2.7, §3.2–3.5, patch
  §5.4), do when touching each file, not as their own dispatch:**
  gen_dsp.py's MCU-only prefixes from config (single registration point
  with the allowlist) instead of a hardcoded tuple, plus makedirs guards on
  the generated-file writes; dedupe the parse helpers between
  dsp_validate.py and dsp_simulate.py (and drop dsp_simulate's second
  DSPSimulator instantiation / per-stage block.copy()); hardcode
  fixed_ref.py's fitted polynomial coefficients (fit script kept for
  regeneration); single-pass GEQ insertion; assert-guarded template
  rewrites → marker-based with node/file context in the error.

## HUB MANDATE 2026-08-25 — crosspoint-coefficient mixing is Bible doctrine; dsp code must follow it   [status: 🟢 ENFORCED 2026-08-27 — audit clean, folds landed, proven on the part. No MAC path in either build now reads control state: fader/DCA/mute, pan leg, bus assign, send level and input assign are all folded into one Q4.28 coefficient per crosspoint at control rate, and the pickoff enum is resolved to a source ADDRESS at control rate too. Out of scope and left as graph structure, as the mandate directs: GATE filter enable, TUBE on, NOISE on, TALKBACK HPF enable. Findings, deltas and what is NOT done are in the TWO outcomes dated 2026-08-27 (evening, then late) at the bottom of this file. The late one closes the doctrine properly: the audio path no longer even WALKS dead crosspoints — which are live is resolved at control rate into a compact list — and that is worth ROUTING 589.2 → 202.3 cycles/sample and a shipping ceiling of 3 strips against 2]

PW engraved the concept in the mx26 Bible (docs/bible/10-cell-data-and-protocol.md,
"Crosspoint-coefficient (matrix-gain) mixing"): one precomputed coefficient per
source×bus crosspoint; ALL linear gain terms — fader, pan leg, bus assign,
mute, aux/matrix sends, trims — fold into that coefficient at CONTROL rate
(coefficient prep on the control core per D8, never in the audio path); the
audio path is pure MACs and never branches on control state; mute = coefficient
set to zero. Nonlinear/structural elements (comp, gate, tube, path enables) are
graph structure, not coefficients — the fold does not apply to them.

This generalises the 08-24 "GAIN IS A SINGLE MAC" directive to the whole
routing layer. TASK: audit the per-block kernels and the generated strip/
routing code for violations — per-sample branches on mute/assign state,
gain chains applied as separate multiplies (fader then pan then mute), any
control-state test inside the MAC loops — and fold them. Report findings and
cycle deltas against the strip-fusion ledger; the Rtg* cells in the matrix
are the coefficient-prep inputs, performer-state cells (e.g. Mute) never
reach the DSP directly.

## HUB DISPATCH 2026-08-24 11:00Z — STRIP FUSION: single-MAC stages, one round/saturate per strip (PW constraints: no FPGA, no block-64; target = 32 basic strips in ONE 21564)   [status: 🟡 786 MHz LIVE AND VERIFIED; 32-IN-ONE IS NOT REACHABLE AT THIS CLOCK — measured ceiling 10 channels/chip.
  CLOCK: DSP4_CCLK_TARGET=786 enabled. CCLK measured 786.29 MHz off the diag tick against a 786.43 target (0.02%); a failed CGU write would have read 625/s instead of 999.8/s. Budget 327,680 -> 524,288 cycles/block (1.60x). Legal on BOTH speed grades so it needed no answer on the U5/U6 marking. 983 stays prepared and off. Real-time, SPORT/DMA clean, BLK_OVERRUN static at its boot value. Anomaly list checked: 13 entries, none touches the CGU or PLL.
  BIT-EXACT AT 786: chain.py rewritten to CONFIGURE the strip it tests (unity gain/filters/EQ, dynamics bypassed, no delay) instead of assuming transparency - the old probe's assumption expired when the dynamics were converted and left on by default. 0 of 7 cases. Its NEGATIVE CONTROL caught a real fault on the first run: ramped params were going out with ramp_id=0, which takes the instant path and is then clobbered by the node's own block-rate code from a target never written. Third check on this bench that could not have failed as first written; the lesson is now IN the probes.
  FABRIC: 95,434 -> 85,475 cycles/block. Only 1.12x, NOT the 1.75x an intermediate reading suggested - that figure had the 32 meters running once per block instead of 32 times, i.e. counted at a 32nd of their work. Correcting them costs 30,821. Recorded rather than quietly replaced. Still 2.1x over the 40k target; 16.3% of the new budget.
  METERS: every chip-1 meter taps its channel's GAIN output, which in block builds lives in a pool slot the next strip overwrites - at chain index 320+ each was reading data 31 channels stale. Now run immediately after their source, sampling all 32 samples. Arithmetic DELIBERATELY unchanged: the four recorded MTR defects and the fix-or-retire decision are the hub's and still open. 30,821 cycles/block of known-defective work is itself an argument for settling it.
  MEASURED CEILING (fully converted, SIGNAL PRESENT, 1x, _proc_passes): 8/9/10 strips = 1500/s clean; 11 = 1472/s MARGINAL (audio_verdict calls it REAL_TIME on a 1450 threshold, but blocks are being dropped); 12 = 1377/s; 14 = 1219/s. HONEST CEILING = 10. Agrees with the arithmetic (predicted 11) to within one channel. Two rows discarded rather than read as data: a STRIPS=10 run that never got past BOOT_STAGE 5, and a STRIPS=11 link failure caused by ME running a second build in the same tree during the sweep.
  THE VERDICT: available 406,106 cycles/block; 32 channels need 397 cycles/sample; actual is 1,269. 3.2x short. With EVERY remaining lever - SIMD across the strip (2.39x measured, not yet wired), both dynamics changes, and the fabric reaching a target it is 2.1x away from - 786 MHz reaches ~29 channels, NOT 32. The same stack at 983.04 MHz reaches ~37 and does close it, but that needs a KSWZ10.
  CHIP 2 IS NOT THE ESCAPE ROUTE, and this corrects me: its own graph measures 1,978,933 cycles/block, 3.8x over the same budget, essentially the same load as chip 1 - and that is a SILENCE reading so the truth is worse. I had called it "comparatively idle" and built two-chip splits on that. It was an assumption, never measured, and it was wrong.
  FOR PW: the 32-in-one goal now hinges on the U5/U6 part marking. A KSWZ10 at 983.04 MHz reaches it with the levers; a KSWZ8 does not, at any combination measured. Cost model updated at MW/D32/DSP/dsp4-function-costs.csv and the interactive page.
  BENCH: shipping CPLD untouched; production firmware and matrix-app restored at the end of the block
  ITEM 2 CLOSED 2026-08-28 — STRIP FUSION IS DONE AND MEASURED. The strip is
  1,231.8 -> 1,098.8 cycles/sample signal present (-10.8%), bit-exact on the
  part twice over, and the measured ceiling is 12 at 786 and 16 at 983 per
  chip against 11 and 14 before it. THE 08-24 VERDICT ABOVE IS NOW OUT OF
  DATE IN ONE ROW AND ONE ROW ONLY: a two-chip D32 split at 983 needs 16 per
  chip and the part delivers 16. 32-in-one on ONE part is still 2.0x short at
  983 and 2.7x at 786, so this block's headline finding stands.
  Item 2's own target of <=200 cycles/sample/strip is NOT met and was never
  reachable by fusion alone: GATE+COMP is 668.7 cycles/sample of the 1,098.8
  and fusion does not touch the dynamics maths. Item 1's TUBE conversion is
  still open (measured bypassed, ~0; its ACTIVE cost is still unmeasured).
  Item 3 (SIMD) is the next rung and item 4 (fabric) is spent -- see the
  2026-08-28 block at the top of this file for the full outcome.]

model: opus

Context: per-node conversion is done bar COMP+TUBE; strip 1,005 cycles/sample,
ceiling ~6.8 strips, D24 3.5x over. The remaining cost is BETWEEN nodes: each
stage exits to memory in Q4.28, paying splice+round+saturate+store per node
(GAIN: 1 MAC + ~12 plumbing instructions — PW: "gain should be a single MAC",
and inside a fused strip it is). PW has ruled out FPGA and block-64; block
stays 32 samples; the target is efficient code, not shape-of-product change.

1. FINISH THE CLASSES: retest COMP with real hoisting (your own GATE evidence
   says the wrap verdict was premature) and convert TUBE. Harness-verified.
2. STRIP FUSION, the main event, via the GENERATOR: emit ONE fused kernel per
   strip — samples resident in registers/MR across GAIN->EQ->FILT->GATE->COMP
   ->TUBE->DLY->FDR, intermediate stages as bare MACs/cascades at full 64-bit
   precision, ONE round/saturate/store at the strip boundary into the bus
   accumulator. Block-rate work (ramps, Q shadows, coefficient swaps) once at
   kernel entry. Numerically this is BETTER than per-node rounding — where
   bit-exactness vs the per-node path cannot hold (single vs per-stage
   rounding), verify against fixed_ref configured the same way and record the
   difference bound in the harness report, not as a tolerance loosening but
   as the fused reference. Prove on ONE strip (chip 1, full class chain),
   measure cycles/sample and verify, THEN roll to all strips via the
   generator. Target: <=200 cycles/sample/strip.
3. SIMD PAIRING: strips are per-channel and independent — process two strips
   per instruction stream with the secondary datapath where the kernel
   allows; measure the actual factor, do not assume 2x.
4. BUS/SEND FABRIC (23% of budget fixed): same lift-out treatment — routing
   masks at block rate, accumulators back in internal DM (they are parked in
   L2), sends as N MACs. Target: <=40k cycles/block.
5. RE-MEASURE: strips ceiling at 1x on the fused build (use _proc_passes,
   dsp4_audio_verdict.py), refreshed cycle table, STATUS one-read. The goal
   line: 32 basic strips real-time on ONE 21564 with margin; report the
   measured number against it honestly.

Rules: default/shipping image byte-identical throughout (fusion behind
DSP4_STRIP_FUSED, default 0); bench = rev-C CM4 app@192.168.1.219 24/7;
matrix-app running + 3 MCUs verified at every stop (NOTE the second-restart
pattern is filed with the hub as an mx26 app bug — keep logging occurrences);
rev A hands-off; single trunk; no AI attribution.

## HUB DISPATCH 2026-08-22 21:05Z — EARLY AUDIO: word-phase fix, then CPLD loopback bitstream + Pi capture path (no analog boards, no hands)   [status: 🟢 STRIP FULLY CONVERTED BAR COMP+TUBE - FILT, EQ, GATE and DLY all converted to per-block kernels today and all bit-exact on the part. FILT 6,973 -> 4,062 (1.72x), EQ 11,590 -> 7,998 (1.45x), GATE 5,999 -> 4,891 (1.23x), DLY 4,185 -> 2,000 (2.09x); every baseline re-measured on the CURRENT build, not taken from the pre-rewrite table. STRIP 1,973 -> 1,005 cycles/sample over the whole rewrite; projected ceiling 2.91 -> 6.79 strips; D24 4.6x -> 3.5x over. Only COMP and TUBE remain (243 cycles/sample together, 24% of a strip); converting them at DLY's rate reaches ~7.7 strips, STILL 3.1x short of D24 - so every class is now converted or measured, the total is better by a factor of two, and it does not close the gap. WHAT UNBLOCKED THE BIQUADS: a self-test on the part (DSP4_BQ_SELFTEST) ran _bq_fx_cascade_blk against _bq_fx_cascade_N on identical data - two stages with DIFFERENT coefficients, across a block boundary - and found 0 differing samples of 64. The routine was never the fault; the wrapper was. Three things it must get right: input and output are DIFFERENT pool slots (the cascade works in place), i1 carries HPF -> LPF, and crossfades are handed to the per-sample body a sample at a time via a new _<nid>_process_sample label so the alpha bookkeeping and mid-block completion are right by construction. COMP's 'not worth converting' verdict is now SUSPECT and should be retested: it was judged on a bare WRAP, and GATE - same class, also 8% slower wrapped - converted at 1.23x once the block-invariant work was hoisted (the _sample_idx guard, on/off tests, four constant reloads, register-resident state). TWO TRAPS RECORDED: (1) under DSP4_BLOCK_KERNELS _sample_idx is 31 when the chain runs, so any unconverted node converting its parameters under a _sample_idx == 0 guard NEVER converts and runs on its .var initialisers; (2) verifying DLY produced two blind passes first - an impulse never opens the gate, so '0 mismatches over 27 samples' was 27 samples of zeros, and a second attempt compared two scope arms through stateful filters and saw 1-3 LSB that had nothing to do with the delay. The probes now refuse to report a pass unless the stimulus could have failed. BENCH: shipping CPLD dsp4_logic.a1f6672af6c3 (md5 dd1e09185804cb2e451d5089cdd56be3, IDCODE 0x020a30dd verified), production firmware 0df38e8270c14e01ba6ffc57c2122563 / 130ddb0f546966b38ec23b6d9b923748 - byte-identical to before this work - matrix-app active, all 3 MCUs verified. FLAG FOR THE HUB: matrix-app needed a SECOND restart to get all three MCUs to announce, twice today (first restart gave H1S3 only, then none of the three). It always succeeded on the retry, but 'first restart after a DSP reflash does not verify' is a repeatable pattern now, not a one-off. Old status follows] [was: 🟢 KERNEL REWRITE - STEERED ITEMS ALL CLOSED, and the headline is a capacity answer, not an optimisation one. SCOPE GATING DONE and the first mechanism I built was a NET LOSS - that is the finding. Only 34 of 431 nodes carry a scope= (32 D32-only, 2 D24-only, all TDM in/out, interchip send/recv, aux input). Measured booted d24: control (no gating) 243,235 cycles/block, per-NODE skip table 244,795 (+1,560 WORSE), contiguous-RUN gating 241,744 (-1,491, kept). A table read+test before ALL 431 dispatch calls costs more than not calling the 34, and the ratio does not improve per-sample - check and node cost both scale 32x. The mechanism that works is one compare and one branch per contiguous RUN: 2 runs on chip 1, ~8 cycles/block against 1,491 saved. Behind DSP4_SCOPE_GATE (default 1) so the control stays buildable. DEFAULT IMAGE BYTE-IDENTICAL throughout (d1c3dd5c96d6516d76b5355474a73a95 / 85d546f9262bd3ef33604f1b577b2748) - my first cut moved _scope_gate_count and the chip-2 gate table and so changed the SHIPPING image; caught by the md5 check, legacy generator output now emitted verbatim on the default path. Chain still 0 LSB at all 7 level/pan points with a run branched over. CEILING RE-MEASURED AT 1x: STILL 2 (STRIPS=2 1500 transport/1500 _proc_passes REAL_TIME; STRIPS=3 1500/1329 OVER_BUDGET, reproducing the 1342 measured pre-rewrite). That is the CORRECT answer, not a disappointment - the default image is byte-identical so its ceiling could not have moved; every conversion sits behind DSP4_BLOCK_KERNELS. The CONVERTED build's ceiling is NOT yet honestly measurable and was not measured: there the six unconverted classes run once per block instead of 32x, so a sweep would flatter itself ~32x on 88% of the strip. MEASUREMENT TRAP recorded: a first sweep judged real time by FRAME_COUNT over a nominal dwell and produced an impossible 2023 blocks/s - FRAME_COUNT is advanced by the block ISR and is structurally blind to an over-budget loop. Use _proc_passes; dsp4_audio_verdict.py exists for exactly this and answered first try on a link that had refused 15 attempts. THE DECISION-GRADE ARITHMETIC: post-conversion strip 63,131 -> 42,306 cycles/block, fixed overhead 144,166 -> 109,064, so 218,616 available = 5.17 strips projected (up from 2.91). D24 needs 24 strips = 1,015,344 -> 4.6x OVER. D32 needs 32 -> 6.2x over. The six UNCONVERTED classes are 88% of what a strip now costs (EQ 338 + FILT 227 + GATE 204 + COMP 202 + DLY 148 + TUBE 40 = 1,159 of 1,329 cycles/sample); halve ALL SIX and you reach 9.2 strips, still 2.6x short of D24. Scope gating at 0.46% of budget does not change this and neither does any single node class - closing it needs a change of SHAPE (fewer nodes per strip, bigger block, or strips per part), which is a hub decision. FILT/EQ retry: PARKED, with the recorded reasoning CORRECTED - a both_unity pass at 0 LSB cannot exonerate the state handling, because with unity coefficients y=x and the stored state contributes NOTHING, so unity is blind to exactly the class of fault present. Any wrong state pointer passes it and fails every real filter. New suspect order: (1) the state pointer the wrapper hands i1 (test with two sections carrying DIFFERENT coefficients), (2) persistence across block boundaries, (3) only then MAC-unit implicit registers. A line-by-line diff proves the arithmetic, MAC order, rounding, saturation, error feedback and state store order are IDENTICAL to _bq_fx_cascade_N - it is not the maths. i0-advance-between-stages fix is IN, so EQ at r4=4 is unblocked. BENCH RESTORED: shipping CPLD dsp4_logic.a1f6672af6c3.svf (md5 dd1e09185804cb2e451d5089cdd56be3) flashed, IDCODE 0x020a30dd verified, GPIOs released; production firmware 0df38e8270c14e01ba6ffc57c2122563 / 130ddb0f546966b38ec23b6d9b923748; matrix-app active with all 3 MCUs verified (H1S1, H1S3, H1S4 - first restart showed only H1S3, a second restart brought all three). Old status follows] [was: 🟢 RUNG 2 CAPTURE PATH BIT-EXACT - 0x5A5A0000 / 0x5A5A0001, 96000/96000 frames, all 32 bits. CM4 I2S PROVISIONING FOR mx26 cm4-setup-pi.sh is recorded in the outcome below: one appended line 'dtoverlay=dsp4-pcm-slave' in /boot/firmware/config.txt (backup .bak-20260823-120634 on the unit) plus a custom overlay compiled ON the unit with dtc from source now committed at shared/dsp4-logic/pi/dsp4-pcm-slave.dts - dtbo origin is that dts, not a download. NO stock overlay fits: audioinjector-bare-i2s is playback-only (codec is linux,spdif-dit, a transmitter) AND Pi-master, while the DSP4 card has the CPLD mastering pcm_clk/pcm_fs so the Pi must be SLAVE. The custom overlay points bitclock/frame-master at the CODEC side and uses TWO dai-links because the dummy codecs are one-directional (dit=playback, dir=capture), 32-bit slots. Gives card 0 dsp4pcm, device 0 capture / device 1 playback. THE 32-BIT CHECK EARNED ITS KEEP: first capture read 0xB4B40000 vs 0x5A5A0000 - the expected word shifted LEFT exactly one bit - so the capture launch needed one more BCK of delay than playback (CAP_EXTRA_DELAY=1, measured). A 24-bit check would have hidden it. LATENCY NOT MEASURED and not for want of plumbing: both Pi directions are proven (DSPB->Pi bit-exact; Pi->DSPA shown by a tone appearing as 0xE95F619A in chip 1's lane-6 RX buffer where silence reads 0x00000000), but the DSP does not ROUTE the Pi input to DSPB's output - a 1 kHz tone in gives digital silence out with a committed d24 config. Routes are host-written matrix parameters that nothing in boot config sets, so latency belongs with the virtual-audio work in the queued chain. Old status follows] [was: 🟢 HUB WAS RIGHT - the 2.5x margin was my test, retracted. Aliveness was judged by whether the parameter link answered promptly, and that link is POLLED from the block loop, so under load an answer is a block away - normal, not a fault. Judged on audio truth, DSP4_STRIPS=1 is BOOT_STAGE 7, FRAME_COUNT 1500/s, _proc_passes 1500/s, DMA and SPORT clean: real time, every block, where it was previously recorded 0 alive/3. STRIPS CEILING = 2 (1: 1500 passes/s, 2: 1500, 3: 1342 = 89%, 4: 1144 = 76%), which agrees with the cycle arithmetic (2.9 predicted) to better than one strip - profile and bench now corroborate. Two strips against 32 required. Fixes kept: dsp4_audio_verdict.py separates transport from loop and reports UNKNOWN distinctly from AUDIO_DEAD; dsp4_diag.py read() collects patiently before realigning, since the old behaviour manufactured a fault out of a slow answer. RUNG 2: DSP and CPLD sides DONE - loopback capture bitstream flashed, card healthy on it, and pcm_din is LIVE (GPIO20 reads 2 hi/10 lo, right ballpark for the pattern words). BLOCKED on the Pi: arecord -l lists NO capture hardware, /boot/firmware/config.txt has no I2S overlay, so there is nothing to record from. That needs a persistent boot-config edit plus a reboot of the ONLY bench, and the overlay must make the Pi an I2S SLAVE since LOGIC masters pcm_clk/pcm_fs - flagging rather than guessing on a 24/7 unit. GPIOs do not clash (I2S 18-21, matrix-app 6-12/22-25). dsp4_pcm_capture.py is written and waiting. Old status follows] [was: 🟢 (c) CYCLE PROFILE DELIVERED in MW/D32/DSP/dsp4-cycle-budget.md - measured per node class with a TCOUNT instrument exact to the core clock. HEADLINE: RTG, a ROUTING node, is the most expensive class at 601 cycles/sample - 30.5% of a channel strip, more than EQ (338) and COMP (202) together. The dynamics maths is not the problem. Fixed overhead is 44% of budget before any strip runs (block I/O ~20%, buses/sends ~24%). Full graph 660% of budget. (b) DSP4_STRIPS built and flag-verified in the running image via a second stamp word, but the answer is uncomfortable: ONE strip measures 73.3% of budget - it fits by arithmetic - and is still 0 alive/3 at 1x. Reliable below ~20% load, marginal ~39%, gone by ~73%, so roughly a 2.5x margin is being eaten by something the cycle count does not explain and I have NOT identified it; candidates are that the alive/dead test is really a parameter-link test, and interrupt/overrun effects a per-pass count cannot see. The per-class table is unaffected and stands. (a) RUNG 2 RTL ready: reframer capture path de-frames a DSPB slot to pcm_din, loopback keeps lane 6 on the Pi path, dsp4_logic_loopback.b13e772abdbb built through sim+STA, SHIPPING POF proven BYTE-IDENTICAL, dsp4_pcm_capture.py written - but not yet flashed or captured, and latency needs a time-varying source which needs a graph that runs, which (b) says we do not have. Old status follows] [was: 🟢 ROOT CAUSE FOUND - the node graph is ~16x over the per-block cycle budget. Not a defect in any node: the FULL 431-node graph runs 3/3 clean given 16 block periods (DSP4_BLOCK_DECIMATE) and 0/6 given one, with 27 nodes 0/3 at 1x and 3/3 at 8x - same code, more time. Budget is 491.52 MHz / 1500 = 327,680 cycles per block; the graph needs ~5.2 M, about 380 cycles per node per sample, which is plausible real work for this library (a compressor runs log2+exp2 polynomials per sample). The graph is invoked ONCE PER SAMPLE - 431 calls x 32 samples = 13,792 node invocations per block. And nothing reduces it per product: _scope_gates_apply on chip 1 is a no-op ('no scoped nodes on this chip'), so all 431 run for D24 and D32 alike, and the measurement already had a d24 config committed. HARNESS FIXED FIRST: main.asm now carries a _build_flags stamp that bisect.sh peeks off the RUNNING part and aborts on mismatch, closing the assembler/linker/loader/boot loop that let the DSP4_STUB_* defines silently vanish; every point is now N repeats and a pass rate. THIS IS A DESIGN-CAPACITY DECISION FOR THE HUB - fewer nodes, cheaper nodes, or work moved out of the per-sample loop. Rung 2 cannot run as written (a scorable loop needs real-time audio) but the Pi capture path can still be proven with the DSP4_PATTERN firmware, which needs no node graph. Old status follows] [was: 🟠 RETRACTION - the compressor identification was WRONG and is withdrawn. The DSP4_STUB_* defines never reached easm21k (a build.sh string replace silently no-opped), so every stub build was the SAME image, md5 50a6c9d5, and the alive/dead differences were bench flakiness. Caught by md5-ing the image across a flag change. build.sh now passes them, verified by the md5 changing. Re-tested with repeats: production full graph 0 alive / 6, and 0 of 40 patient reads over 40 s after commit, so the core genuinely STOPS (not starvation - the 1 kHz ISR backstop would have answered). Without the node graph 4/4 alive at STAGE 7, 1500.0 blocks/s. One node 3/3 alive. Stubbing _compgain_fx changes nothing (0/2), and NODE_LIMIT 5 vs 6 does not reproduce, so no specific node is identified. ALSO CORRECTED: the BLK_OVERRUN 0 figure was from the stale image - the real number is ~8590 overruns per ~17220 blocks with block I/O ALONE, so half the per-block budget is gone before any node runs, which makes a cycle-budget explanation worth testing before another node hunt. STANDS: the r6 loop-bound fix (a real defect, readable in source), rung 0 (200 round-trips, 0 slips) and rung 1 (TDM slot map). NEXT: give every bisect point N repeats and a pass rate - single-point alive/dead is too noisy to bisect on. Old status follows] [was: 🟠 block loop FIXED, one fault left and it is narrow. FIXED: .cN_sample_loop kept its 32-sample bound in r6 while BOTH _scatter_chipN and _gather_chipN load the DMA buffer address into r6, so the loop ran about 610,000 times per block - indistinguishable from a hang. With that fixed, scatter+gather run at STAGE 7, 1500.0 blocks/s with BLK_OVERRUN 0: the main loop now keeps up with every block. REMAINING: DSP4_NODE_LIMIT binary-searches the 431-call chain to index 5 = _C1_COMP_01_process; bypassing it is alive, skipping its block-rate conversion is not, and stubbing _compgain_fx to unity is alive. Below that the stubs stop isolating (stub log2q ALIVE, stub polyq DEAD even though polyq is called BY log2q), which means the failure is VALUE-DEPENDENT in the compgain chain rather than one structurally broken routine - more blind stubbing is guesswork. NOT floating inputs: same hang with the loopback bitstream driving DSPA. Also fixed, not the cause: _comp_knee was read before ever being written, now 0.0 in the generator across 42 nodes. METHOD NOTE that cost two wrong readings: a harness that only asks 'did the link answer' gives FALSE PASSES, because a part still at BOOT_STAGE 5 answers fine - require BOOT_STAGE >= 6 and non-zero TICKS. Rung 2 still blocked on this last fault. Old status follows] [was: 🟢 RUNG 0 DONE (200 round-trips both chips, 0 slips, 0 out-of-step) + audio 1500.0/s + rung 1 verified. The post-CONFIG_COMMIT death was NOT a phase fault - answer-every-transaction is what proved it, since every read came back 0x00000000 rather than a wrong echo. Bisected to TWO faults: (A) FIXED - .main_loop opened with `idle`, which wedged the parameter link the instant CONFIG_COMMIT released .wait_boot (.wait_boot spins, .main_loop slept); proven by block-work-off + commit-applies-off + idle-ON = dead vs block-work-off + commit-applies-ON + idle-off = BOOT_STAGE 7 at 1500/s healthy. (B) OPEN and narrow - with idle gone, DSP4_BLOCK_STAGE puts the remaining wedge in the GENERATED scatter/gather (stage 1 healthy, stage 2 _scatter/_gather DEAD, stage 3 node graph also dead), so block_io.asm's _scatter_chip1/_gather_chip1 is the next item. Also landed: l2_clear() zeroes the L2 delay lines at startup, which the LDF explicitly requires and nothing did (did not fix either fault); host-side SpiLink.realign fallback. Rung 2 not started - it needs BOOT_STAGE 7 with real block I/O, which is what fault B blocks. Old status follows] [was: 🟢 AUDIO RUNS + RUNG 1 DONE; rung 2 blocked on rung 0. Audio: 1500.0 blocks/s on both chips (48 kHz / 32-sample blocks), SPORT0_ERR_A clean, DMA0_STAT 0x00006200, real 2D ping/pong. Four faults fixed to get there: PADS0_DAI0_IE/DAI1_IE never written (reset 0 = every DAI input buffer OFF, so BCK/FS never got past the pad while the SPORT read back perfectly configured); the DDE issuing NON-SECURE writes that memory refused (ERRC 3 for both the L1 alias and plain L2, with SMPU3_BADDR naming the exact address and BDTLS.SECURE = 0, against SPU0_SECURECHK = 0xFFFFFFFF for the core) fixed by SPU_SECUREP[n].MSEC; DMA_STAT.IRQDONE never W1C'd so the SEC re-entered the ISR forever (11e6 frames in 4.6 s); and DMA_CFG.TWOD unset, which made ping/pong a fiction that the block rate could not reveal. Descriptor-list arming is broken on this part, so the rings use AUTOBUFFER. RUNG 1 CLOSED by loopback measurement, recorded in hardware-map.md: lane index identity, slot order identity, BCK/FS pair order and sample edge/MFD all correct, proven decisively by masked lane 4 receiving exactly slots 0,2,3. RUNG 2 BLOCKED: after the 51-write CONFIG_COMMIT the parameter link is permanently out of phase (reads return BUILD_ID for a MAGIC request, no recovery in 10 attempts) - the part is alive and answering, just shifted, which is exactly what rung 0 exists to fix. Rung 0 is NOT a nicety; it gates everything past config. Also: dsp4_boot.py can silently leave chip 2 running chip 1's firmware - read CHIP_ID before believing any measurement. Old status follows] [was: 🟢 AUDIO RUNS — the gate is MET on BOTH chips at exactly 1500 blocks/s (48 kHz / 32-sample blocks), SPORT0_ERR_A clean, DMA0_STAT 0x00006200 (RUN 2, no error). THREE faults, none of them where the last several sessions were looking. (1) PADS0_DAI0_IE / PADS0_DAI1_IE were never written by this firmware and come out of reset at ZERO — every DAI input buffer was off, so BCK0/FS0 never got past the pad while SPORT0_A read back perfectly configured and enabled. The SRU only connects signals already inside the part. (2) The DDE issues NON-SECURE transactions and memory refused them: the first memory write of every transfer failed with ERRC 3 for BOTH the l1_to_sys() alias and a plain L2 address, and SMPU3 named the culprit — SMPU3_BADDR = 0x20000000, the exact target, with SMPU_BDTLS.SECURE = 0, while the core reads SPU0_SECURECHK = 0xFFFFFFFF and is therefore SECURE. Setting SPU_SECUREP[n].MSEC fixed it. (3) _sport_dma_work never W1C'd DMA_STAT.IRQDONE, so the channel held its request asserted and the SEC re-entered the ISR forever — 11e6 frames in 4.6 s until acked. Also fixed on the way: descriptor-list arming is broken on this part (ERRC 3 even for a self-referencing descriptor built in the probe), so the rings now use AUTOBUFFER flow; and the rung-31 probe was missing WNR, which had made a working channel look dead. Rung 1's pattern firmware and rung 2 NOT started — the audio path is up but the four slot-map facts are still unverified. Old status follows] [was: 🟠 rung 1 blocked on the DMA channel; SPU/SMPU checked and EXCLUDED, and the earlier conclusion OVERTURNED — the boot kernel does leave SMPU_CTL.RSDIS = 1 on all five instances (read addresses checked, no regions configured — a real latent hazard) but turning it off changes nothing. The decisive test: DMA0 armed REGISTER-BASED with FLOW=STOP and NO descriptor at all still raises ERRC = 3, both with the L1 alias and with an unambiguous L2 address, while ADDRSTART and XCNT now read back exactly what was written. So it is neither the descriptor fetch nor the address translation: the channel refuses to run whatever it is pointed at. Clearing the sticky IRQERR before arming does not help, so the error is raised live on enable. Caveat recorded: the probe omits WNR, which should be corrected before the conclusion is called final. Eleven hypotheses now eliminated. Next: fix the probe's WNR, then whether the SPORT/DMA block is clocked or gated at all — nothing in this firmware enables it. Old status follows] [was: 🟠 rung 1 blocked on the DMA channel; descriptor bug fixed, five hypotheses now eliminated — HRM Table 27-10 CONFIRMS the descriptor element order the code already used ({NXT, ADDRSTART, CFG, XCNT, XMOD}), so that is verified not assumed. Sharpened symptom: the channel advances DSCPTR_CUR by exactly five words (fetch 'complete') yet loads XCNT=0 and ADDRSTART=0 from memory the core reads back correctly. Excluded with evidence: element order; descriptor contents (correct after the volatile fix); store-buffer race (barrier changed nothing); DMA_CFG (reads back exactly as written); alignment; and L1 fabric visibility — the descriptors were moved to L2 (confirmed in the map at 0x2007bc00) and the fetch STILL returned zeros, so it is not an L1-alias problem. That L2 placement was reverted since it fixed nothing. Strongest remaining candidate: the SPU/SMPU system protection units, which nothing in this firmware programs — a gated fabric read that returns zeros and raises a memory-access error fits the signature better than anything else. Old status follows] [was: 🟠 rung 1 blocked on a REAL DMA BUG, now half fixed — **the DMA descriptors were being optimised away.** Nothing in C reads them (only the DDE does, through the fabric) so at -O the stores filling them were dead-store eliminated; taking &desc[i][0][0] does not save them because the address is only converted to an integer. Descriptor words read back 0x00000000 before and 0x282549D4 / 0x28254D40 after making them volatile — correct L1 aliases, correct ring. THAT is why no audio block has ever arrived on this card. Found from DMA_STAT 0x00006032 = IRQERR, ERRC 3 ("Memory Access or Fabric Error"), RUN 0. STILL FAILING: with correct descriptors the channel is unchanged (ADDRSTART 0, FRAME_COUNT 0, SEC_COUNT 0), and a write-completion barrier changed nothing, so it is not a store-buffer race; CFG reads back exactly as written. Next and specific: HRM ch.27 descriptor ELEMENT ORDER and alignment — the code assumes {NXT, ADDRSTART, CFG, XCNT, XMOD} but the data sheet prose says link/address/LENGTH/CONFIG. Five-minute check. Also corrected: the DMA channel, not the SPI link, is rung 1's real gate — the pattern firmware cannot mean anything until one block completes. Old status follows] [was: 🟡 rung 1 HALF DONE — the CPLD half is complete: `dsp4_logic_loopback.48fa9b8590d5` built through the sim and STA gates (47 LE vs shipping 156, Fmax 167.98 vs 70.21 — the fitter prunes the now-unused input muxes and the PCM reframer, which matters for rung 2), flashed over the CM4 JTAG bit-bang, and proven healthy on the card: both DSPs still boot (so DSP_CLK survives) and PCM_CLK/PCM_FS still toggle. **SHIPPING BITSTREAM RESTORED and re-verified** — IDCODE good, clocks toggling, chip 1 answers MAGIC/CHIP_ID/BOOT_STAGE. The pattern generator/checker firmware is NOT written, so none of the four facts rung 1 exists to close are established and no PROVISIONAL tags were retired. OPERATIONAL TRAP now documented in shared/dsp4-logic/README.md: OpenOCD's linuxgpiod leaves its GPIOs claimed on exit, so `pinctrl set ... a0` after every flash is MANDATORY — without it the SPI link is dead on both chips with a known-good bitstream and it looks exactly like a bricked card. Recommendation: run rung 1's verdicts over the PB_05 dump, not the SPI link. Old status follows] [was: 🟡 link now POLLED and much improved; rung 1 NOT started — the parameter link is off the SEC entirely: `sec_init()` keeps only the audio block clock and `_spi_poll` collects requests from the main loop AND from `.wait_boot` (the latter is mandatory — the config that releases that loop arrives over the link being polled, and omitting it deadlocks). Plus the two SPI_TFIFO pushes are separated by NOPs: back to back one was being lost and every read came back as (value, value). Production reads did not work AT ALL before this; they now run 11 of 12 consecutive full-block reads clean, with writes landing (PRODUCT_ID reads back 1). Read-after-write in one session is still an intermittent race — better, not solved; the echo is checked on every read so a bad answer is rejected rather than believed. Rung 1 deliberately not started at the tail of a long session: toolchain all verified present (Quartus 21.1, iverilog 12.0, OpenOCD + cpld-jtag.cfg, IDCODE 0x020a30dd, shipping .pof/.svf on the Pi ready to restore), and the recommendation is to read rung-1 verdicts over the PB_05 dump rather than the SPI link. SHIPPING CPLD bitstream UNTOUCHED. Old status follows] [was: 🟡 gate MET + read regression largely fixed; rungs 1-2 not started — the two all-zero-MISO events were ONE fault and it was in the RECEIVE side, not the response path: the RFIFO was left holding a single stale word around the boot handover, so with the correct RFS==FULL drain guard the level could never reach FULL again and the handler stopped firing (SPI2_STAT 0x00142001, RFS=2, counters FROZEN at 74 and IDENTICAL across two runs with different traffic, one with matrix-app stopped). Fixed with stuck-partial recovery in the diag timer ISR (three consecutive 1 ms ticks half-full = stale, discard a word) — SPI2_STAT now 0x00540001, everything empty and clean. Answers then come back rotated by one word, which dsp4_diag.py now tolerates with the ECHO as the check, so a wrong guess cannot be read as data. POLLED variant (rung 27) reads the full diag block RELIABLY; interrupt-driven production reads most of it then drops/duplicates one word. Per the steer the pipeline is not stopped on this: rung 1 proceeds on the polled channel. Remaining suspicion recorded — the ISR can enter mid-transfer when FULL is momentarily true, which the polled loop cannot; gate the drain on the transaction boundary. Old status follows] [was: 🟡 gate MET, rungs 1-2 not started — **BOOT_STAGE 6 on BOTH chips**, proven on the PB_05 dump (BOOT_STAGE 6, BOOT_CFG 1, PRODUCT_ID 1 on each; images md5-checked before flashing). Root cause of the config never landing was NOT rung 0: the drain guard tested SPI_STAT.RFE ("not empty") when a request is TWO words, so entering with a single word present drained one real word and one garbage one and desynced the stream permanently. Guarding on RFS == 4 (Full RFIFO) gives a clean 1:1 — chip 2 shows 5 handler entries for 5 writes where RFE gave 2.3x — and CONFIG_COMMIT then applies. REGRESSION, stated plainly: the same change broke READS, which now return all-zeros on MISO; the two states are (RFE: reads work, config never lands) and (RFS: config lands, reads dead). RFS is kept because it is provably the right condition and it reaches the gate. Rungs 1-2 not started — building a CPLD bitstream on a link that cannot be read back would be building on an unverifiable channel. Next: the read fault is between .spi_read and the TFIFO writes, everything upstream is excluded; see the outcome. Old status follows] [was: 🔴 blocked at rung 0 — the word-phase fix was implemented twice and REVERTED both times; nothing shipped and the tree is back at `f2bdb93`, rebuilt and re-verified on the bench. Making every transaction answer turned MISO to ALL-ZEROS on every transaction, reads included — worse than the known-good, which reads fine. The failing build is healthy everywhere except the answer: core alive, SEC_COUNT = SPI_RX_COUNT = 86, SPI2_STAT = 0x00540001 (RFIFO empty, no ROR/TUR/RUWM), RESP_DROP = 0 — so receive, delivery and dispatch all still work and only the queued answer is wrong. Both variants failed identically: echo stashed in a .var (the var read back CORRECTLY as 0xE0FE0000 from the main loop, yet answers were still zero) and echo queued while r0 is still live via a new subroutine. Rungs 1 and 2 not started — rung 0 is their gate. Full state note, four ranked next suspects and a recommendation to retry as a strictly smaller step are in the outcome below]

**HUB STEER 2026-08-23 10:20Z — capacity finding accepted; decision goes to PW (see
"DECISION ASK" below). Do NOT start a graph/kernel restructure. Proceed:**
(a) RUNG 2 via DSP4_PATTERN: prove the Pi capture path (pcm_din de-frame)
with the pattern firmware — Pi plays a known file into I6, pattern/pass-through
on the loop, Pi records it back; bit-exact on all 32 bits (the lanes carry
32-bit words); record latency in samples. (b) NODE-ENABLE MASK: add a per-strip
enable to product config (or a DSP4_STRIPS=N build knob) so a 1-strip graph
(IN→GAIN→EQ→FILT→COMP→GATE→FDR→bus) runs in REAL TIME at 1x — that is what the
virtual-audio harness needs; prove 1 strip 3/3 at 1x and find the max N that
holds 1x. (c) CYCLE PROFILE: cycles/sample per node CLASS (GAIN, FDR, EQ,
FILT, COMP, GATE, DLY, TUBE, BUS, MTR, RTG, XIN/XS) measured on the part, one
table in hardware-map.md or a new dsp4-cycle-budget.md — this is the data PW's
decision needs. Then the queued chain (desk fillers; virtual audio on the
1-strip graph). Keep going without stopping to ask.

**PW DECISIONS 2026-08-23 16:2xZ (recorded by the hub): (1) CM4 path = TDM8 —
8 channels Pi→DSP on A_I6 and 8 channels DSP→Pi on B_O3, LOGIC regroups
frames; allocate at the single source (slot-map.csv) — supersedes the stereo
B_O3 2/3 allocation (which is now a subset). (2) Rev-D mod 3 DROPPED: the
5M1270Z stays (738 LE + 4.1 % timing margin rule out the 570Z); recorded in
TransferOnly/PCB mods/dsp4-revD-modlist.md. The cycle-budget decision below
is still open.**

**PW DECISION 2026-08-23 16:5xZ: GO on 1 + 2 + 3 (per-block kernels; cheaper
RTG/bus/dynamics math; product scope gating). Option 4 (bigger blocks) NOT
taken. Dispatched as the QUEUED block "KERNEL REWRITE" below the virtual-audio
block; the harness families on the current code are the baseline first.**

**(resolved) DECISION ASK (PW): node graph is ~16x over the per-block cycle budget
(needs ~5.2 M cycles/block vs 327,680 available at 491.52 MHz / 1500
blocks/s; 431 nodes × 32 samples = 13,792 per-sample node CALLS per block).
Options: (1) per-BLOCK kernels — each node processes the 32-sample block in
an inner loop (generator change, not 431 hand edits): removes ~13k call
overheads per block and opens SIMD/pipelining; typical gain 3-8x. (2) cheaper
math — dynamics gain computer at block rate or every 4th sample (envelope
stays per-sample), biquads in the already-decided fixed point with wide
accumulators (D5). (3) fewer nodes per product — real scope gating (D24 ≠
D32), lazy nodes (bypassed = skipped). (4) larger block (64/128 samples) —
amortises overhead, costs latency. Hub recommendation: 1 + 2 + 3 together,
in that order; 4 only if the profile says the remaining gap is overhead-bound.
This reopens nothing in the rev-D PCB.
PROFILE UPDATE 10:5xZ (MW/D32/DSP/dsp4-cycle-budget.md): fixed overhead 44 %
before any strip (block I/O 20 %, buses/sends 24 %); one strip 19.3 %; full
graph 660 %. RTG (a ROUTING node) is the most expensive class at 601
cycles/sample = 30.5 % of a strip — more than EQ+COMP together. So option 1
(per-block kernels) plus a rewrite of RTG and the bus/send path are the big
levers; dynamics maths is NOT the problem.**

**HUB STEER 2026-08-23 11:55Z — the "2.5x margin" is most likely the test,
not the DSP.** Aliveness is judged over the parameter link, which is polled
from the MAIN LOOP — at 73 % block load the poll is starved and the link
looks dead while audio may be running fine. Do this first: judge aliveness by
FRAME_COUNT advancing + DMA0_STAT + SPORT_ERR over 3 s (audio truth), not by
the link. If audio runs at 1 strip/1x, move the SPI poll into the per-block
work (once per block = 1500 Hz, ample) so the link survives load; re-measure
the strips ceiling. Then RUNG 2: flash the loopback-capture bitstream, prove
pcm_din bit-exact (all 32 bits) with the pattern firmware, then latency with
the 1-strip graph. Then the queued chain.

model: opus

**HUB STEER 2026-08-22 22:05Z — rung 0 PARKED, pipeline continues.** Reads
work and the bounded re-ask workaround in dsp4_diag.py covers writes, so
rung 0 is a protocol nicety, not a gate. Do NOT retry it now. Proceed:
(a) `dsp4_config.py` end to end to BOOT_STAGE 6 on both chips USING the
re-ask workaround, verifying every CONFIG_COMMIT write by re-read; if a
write provably does not land even with re-ask, that and only that reopens
rung 0. (b) Rung 1, then rung 2, then chain into the queued blocks. Rung 0
becomes a separate item — "SPI answer-every-transaction" — to be tried at a
quiet point with a 1-hour time-box, in your own suspect order (TFIFO
occupancy on a verified build first, then inline the queue to drop the
nesting depth, then the r0 preservation in `_diag_read`). Rebuild-and-md5
before every dump reading — keep that rule.

**HUB STEER 2026-08-23 05:40Z — rung 0 UNPARKED: it gates rung 2.** Evidence
accepted (link permanently out of phase after CONFIG_COMMIT). Retry the
answer-every-transaction design FRESH — both failed attempts predate the
stale-word recovery, the polled link and the TFIFO NOP fix, so their
all-zero result may have been those faults, not the design. 3-hour box.
Fallback if it still resists: host-side resync — `dsp4_diag.py` detects
the phase error by ECHO mismatch and issues one 1-word (4-byte) transfer to
realign, repeated until ECHO matches; protocol note says "phase repair is
host-side". Either way, rung 2 follows immediately, then the queued chain.

Rung 0 — WORD-PHASE FIX (UNPARKED 05:40Z — see steer) (your own finding, 20:3xZ outcome): make every
accepted transaction queue exactly one two-word answer — a write echoes its
request word with value 0 — in BOTH `spi_handler.asm` variants + the protocol
note in `diag.asm`; update `dsp4_diag.py`/`dsp4_config.py` to expect it and
remove the bounded re-ask workaround. Prove: 200 alternating write/read
round-trips on chip 1 and chip 2 with zero phase slips, `--led` reliable.
Then run `dsp4_config.py` end to end → BOOT_STAGE 6 on both chips. Stage 6
is the gate for rung 1. Commit + push before starting rung 1.

Rung 1 — CPLD FEEDBACK LOOP (tasks item 5, PW 2026-08-20). Non-shipping,
STA-gated, hash-named LOGIC build: `i_dspa[k] = o_dspb[k]` for k=0..7 (and
`ni[k] = no[k]`), everything else identical to the shipping bitstream.
Firmware: counter-pattern generator per lane on DSPB, checker per lane/slot on
DSPA, verdicts via the 0xE000 diag readback. Closes without a scope: BCKI/FSI
pair order, CKRE/MFD, within-TDM8 slot order, NI/NO crossed-index vs
slot-map.csv. Record each fact in hardware-map.md as VERIFIED with the build
hash + date; retire the PROVISIONAL tags.

Rung 2 — PI CAPTURE PATH. `pcm_din` (LOGIC -> Pi) is tied off in
dsp4_pcm_reframe.v. In the SAME loopback build, de-frame one DSPB output
lane/slot pair to I2S on pcm_din (document which). Then on the CM4:
`aplay` a known file -> DSPA I6 via the reframer, `arecord` the return;
Pi -> DSPA -> fabric -> DSPB -> Pi becomes a software-scorable loop. Reuse
the net repo's long-soak scorer (torn/gaps/dups/silence) — do not write a new
one. Deliver: one 10-minute clean pass on chip 1 + chip 2, then leave a
≥12 h soak running with the verdict log path in this block.

Rules as the block above: bench = rev-C CM4 app@192.168.1.219; rev A
hands-off; always leave matrix-app running + 3 MCUs verified; the SHIPPING
bitstream must be restored on the CPLD before ending; single trunk; no AI
attribution. Rung 3 (real ADC/DAC via J41/J42, codec) is PW-hands and NOT
part of this dispatch.

### Outcome 2026-08-23 02:0xZ — SPU/SMPU checked and EXCLUDED. The channel errors with no descriptor and a valid L2 address.

The hub's hypothesis was worth testing and the registers do show the boot
kernel leaves protection active — but it is not the cause.

#### What the SPU/SMPU actually read back

| register | value | meaning |
|---|---|---|
| `SMPU0/2/3/9/11_CTL` | `0x00000001` each | **RSDIS = 1 on ALL FIVE** — "read addresses are checked before being sent to the slave" |
| `SMPU0_STAT` | `0x00000000` | no violation latched |
| `SPU0_CTL` | `0x000000AD` | GLCK set — MMR write locking, not memory access |
| `SPU0_STAT` | `0x00000000` | nothing |

So the boot kernel does hand over with read-address checking enabled on
every SMPU instance and no regions configured — a real finding, and a
latent hazard worth knowing about.

**But turning it off changes nothing.** Writing 0 to all five CTLs before
arming (verified: `SMPU0_CTL` then reads `0x00000000`) left `DMA_STAT` at
`0x00006032` and `XCNT` at 0. The probe was reverted afterwards rather
than kept, since it fixes nothing and an unexplained write to five
protection units would mislead the next reader.

`SPU0_CTL.GLCK` is about locking MMR *writes*, and our MMR writes
demonstrably land (`DMA_CFG` reads back exactly as written), so the SPU
was never a candidate on the evidence.

#### The decisive test, and what it overturned

`ADDRSTART` and `XCNT` reading 0 was NOT proof that the fetch returned
zeros — it is equally what you see if the fetch never happened, because
nothing else ever writes those registers. So DMA0 was armed
**register-based, FLOW = STOP, no descriptor anywhere**:

| arming | ADDRSTART | XCNT | DMA_STAT |
|---|---|---|---|
| descriptor-list | 0 | 0 | `0x00006032` |
| register-based, L1 alias `0x28254D40` | `0x28254D40` | `0x100` | `0x00006032` |
| register-based, **L2 `0x200F0000`** | `0x200F0000` | `0x100` | `0x00006032` |

The registers now hold exactly what was written, so MMR writes are fine —
and the channel still raises ERRC = 3 the moment `EN` is set, pointed at
unambiguous system memory, with no descriptor involved. Clearing the
sticky `IRQERR` (W1C, bit 1) immediately before arming did not help
either, so it is re-raised live on enable rather than inherited.

**That overturns the previous conclusion.** The descriptor fetch is not
the fault and neither is the address translation. The channel refuses to
run at all.

Caveat on the last two rows, stated because it matters: the rung-31 probe
omits `WNR`, so it arms as a memory READ where SPORT0 half A wants a
memory WRITE. That is worth correcting before drawing a final conclusion
from it — though a transmit DMA reading valid L2 should still not raise a
memory-access error.

#### Cumulative elimination list for the DMA channel

Order (HRM Table 27-10) · descriptor contents · store-buffer race ·
`DMA_CFG` contents · address alignment · L1-vs-L2 for the descriptor ·
L1-vs-L2 for the buffer · SMPU read checking · SPU MMR locking · sticky
`IRQERR` · descriptor fetch as a whole.

#### What is left

Something gates this DMA channel from running irrespective of what it is
pointed at. Candidates, in the order worth trying:

1. **Fix the rung-31 probe (add `WNR`) and re-run** — cheapest, and it
   removes the one caveat above.
2. **Is the channel clocked?** SCLK0 gates SPORT and DMA. SCLK0 is
   present (SPI2 runs on it), but per-peripheral clock or reset gating
   for the SPORT/DMA block has never been checked. There is no such
   enable in this firmware.
3. **SPORT0 itself.** `SPORT0_ERR_A` reads 0, but the SPORT's own enable
   and its DMA request path have never been verified independently of
   the DMA channel.
4. `CMMR_SYSCTL.IMDWBLK*`, which needs the SHARC+ Core Programming
   Reference — not in the local doc set and worth fetching.

**Bench state:** SHIPPING CPLD bitstream on the card; both chips hold the
production build and chip 1 answers MAGIC / CHIP_ID / BOOT_STAGE 5; GPIOs
`a0`; `matrix-app` restarted; three MCUs verified 02:05.

### Outcome 2026-08-23 01:2xZ — descriptor ORDER confirmed correct; L1-vs-L2 excluded. The DDE fetches ZEROS from memory that demonstrably holds the right values.

**HRM ch.27 Table 27-10 / 27-12 settle the element order and the code was
already right:**

| offset | register |
|---|---|
| 0x00 | `DMA_DSCPTR_NXT` |
| 0x04 | `DMA_ADDRSTART` |
| 0x08 | `DMA_CFG` |
| 0x0C | `DMA_XCNT` |
| 0x10 | `DMA_XMOD` |

`{NXT, ADDRSTART, CFG, XCNT, XMOD}` — exactly what `arm_region()` builds.
The data sheet's "link pointer, an address, a length, and a
configuration" is loose prose; the HRM table is the hardware. **That
assumption is now verified rather than assumed, and it is not the fault.**

#### The sharpened symptom

After the descriptor fetch:

| | value |
|---|---|
| `DMA0_DSCPTR_CUR` | given + 0x14 — i.e. five words consumed, fetch "complete" |
| `DMA0_XCNT` | **0** (descriptor holds 256) |
| `DMA0_ADDRSTART` | **0** (descriptor holds a valid buffer address) |
| `DMA0_STAT` | `0x00006032` — IRQERR, ERRC = 3, RUN = 0 |

So the channel walks the descriptor, advances its pointer by exactly the
right amount, and loads **zeros** into every register — from memory the
core reads back correctly at that same address.

#### Excluded tonight, with evidence

- **Descriptor element order** — HRM Table 27-10, above.
- **Descriptor contents** — read back correct from the core after the
  `volatile` fix (`NXT 0x282549D4`, `ADDRSTART 0x28254D40`).
- **Store-buffer race** — a volatile read-back barrier before arming
  changed nothing.
- **`DMA_CFG`** — reads back `0x00144223`: EN, WNR, PSIZE/MSIZE 4 bytes,
  FLOW = DSCLIST, NDSIZE = fetch-five, XCNT_INT. Exactly as written.
- **Address alignment** — descriptor at ...C0, buffer at ...40; MSIZE
  4 bytes needs only ADDR[1:0] == 0.
- **L1 fabric visibility** — the whole descriptor array was moved to L2
  (confirmed in the linker map at `0x2007bc00`, not merely intended) and
  the fetch STILL returned zeros. So this is not an L1-alias or
  L1-exposure problem. The L2 placement was reverted afterwards, because
  keeping a change that fixed nothing would mislead the next reader.

#### What that leaves

The DDE performs the fetch motions but reads zeros regardless of where
the descriptor lives. That points at the channel's SCB read path itself
rather than at the descriptor, the address or the memory: something
about how this DMA channel is enabled for fabric access. Worth looking at
next, in order:

1. **SPU / SMPU.** The system protection units gate master access per
   peripheral. Nothing in this firmware programs them, and a blocked
   fabric read that returns zeros and raises a memory-access error is
   exactly what a protection block looks like. `REG_SPU0_*` and
   `REG_SMPU*` are in the header; the HRM has a chapter each. **This is
   the strongest remaining candidate and it fits the "reads as zeros"
   signature better than anything else.**
2. Whether the SPORT is actually requesting at all — if it is not, work
   out whether ERRC = 3 can be raised without a real memory access.
3. `CMMR_SYSCTL.IMDWBLK*` (internal memory data width per L1 block),
   documented in the SHARC+ Core Programming Reference which is not in
   the local doc set — would need fetching.

#### Rung 1

Unchanged: CPLD half done, pattern firmware deliberately unwritten. The
DMA channel is the gate, and it is now a well-bounded problem with five
hypotheses eliminated rather than a vague one.

**Bench state:** SHIPPING CPLD bitstream on the card (restored 00:44,
IDCODE verified); both chips hold the production build and chip 1 answers
MAGIC / CHIP_ID / BOOT_STAGE 5; GPIOs `a0`; `matrix-app` restarted; three
MCUs verified 01:17.

### Outcome 2026-08-23 00:5xZ — 🟠 THE DMA DESCRIPTORS WERE BEING OPTIMISED AWAY. Fixed. Channel still errors — one step left.

**This is why no audio block has ever arrived on this card.** Nothing in C
ever READS the DMA descriptors — only the DMA engine does, through the
fabric, which the compiler cannot see. At `-O` the stores that fill them
are dead by the compiler's reckoning and were being eliminated. Taking
`&desc[i][0][0]` does not save them: the address is only converted to an
integer and never dereferenced in C.

Measured, on md5-verified builds, over the PB_05 dump (no SPI link
involved):

| | before | after `volatile` |
|---|---|---|
| descriptor word 0 (ring next ptr) | `0x00000000` | **`0x282549D4`** |
| descriptor word 1 (ADDRSTART) | `0x00000000` | **`0x28254D40`** |

Both post-fix values are correct L1-alias addresses, and `0x282549D4` is
exactly the second descriptor of the pair — the ring is right.

`desc_a`/`desc_b` and `arm_region()`'s parameter are now `volatile`, with
the reasoning written where the arrays are declared so it cannot be
"tidied" away again.

#### How it was found

`DMA_STAT = 0x00006032` decodes as **IRQERR set, ERRC = 3, RUN = 0** —
ERRC 3 is *"Memory Access or Fabric Error"* (HRM Table 27-25). The channel
had errored on its very first work unit and stopped. Dumping what
`arm_region()` actually handed the DDE showed the descriptor address was
sane (`0x282549C0`, a valid block-0 alias) while the descriptor CONTENT
read back as zeros — so the DDE was faithfully fetching zeros and then
aiming a transfer at address 0.

#### STILL FAILING, and the next step is specific

With correct descriptors in memory the channel is unchanged:
`DMA0_ADDRSTART` still reads `0x00000000`, `DMA_STAT` still `0x00006032`,
`FRAME_COUNT` and `SEC_COUNT` still 0. So the DDE is not applying the
descriptor it fetches.

Excluded already:
- `DMA0_CFG` reads back `0x00144223` = EN, WNR, PSIZE 4B, MSIZE 4B,
  FLOW = DSCLIST, NDSIZE = fetch-5, XCNT_INT — exactly as written.
- The descriptor address handed over is a valid alias.
- The descriptor contents are now correct.
- A write-completion barrier before arming (volatile read-back of two
  descriptor words) changed nothing, so it is not a store-buffer race.

That leaves the **descriptor element order and alignment**. The code
assumes `{DSCPTR_NXT, ADDRSTART, CFG, XCNT, XMOD}`, the ADI convention.
The data sheet's prose describes a 1D descriptor as *"a link pointer, an
address, a length, and a configuration"* — CFG and XCNT the other way
round. One of those is loose wording and the other is the hardware; HRM
ch.27 has a "Descriptor Set Address Alignment" table and an element-order
definition that settles it. **Read that first next session** — it is a
five-minute check that either confirms the layout or explains everything.

#### Rung 1 status

The CPLD half is done (see the previous outcome). The pattern
generator/checker firmware is still not written, and now clearly should
not be: a pattern test cannot mean anything until a single DMA block
completes. **The DMA channel is the real gate for rung 1, not the
verification channel** — that was the wrong diagnosis, and chasing the SPI
link earlier was chasing the wrong thing.

**Bench state:** SHIPPING CPLD bitstream restored and verified (IDCODE
`0x020a30dd`, chip 1 boots and answers MAGIC/CHIP_ID/BOOT_STAGE 5); both
chips hold the production build; GPIOs back to `a0` after the flash;
`matrix-app` restarted; three MCUs verified 00:44.

### Outcome 2026-08-23 00:2xZ — 🟡 rung 1 HALF DONE: loopback bitstream built, flashed and proven; pattern firmware not written. SHIPPING RESTORED.

**The CPLD half of rung 1 is complete and reusable.** The firmware half —
per-lane pattern generator on DSPB, per-lane/slot checker on DSPA — is not
started.

#### Built, flashed, verified, reverted

`dsp4_logic_loopback.48fa9b8590d5` — non-shipping, both gates passed:

| | shipping `a1f6672af6c3` | loopback `48fa9b8590d5` |
|---|---|---|
| logic elements | 156 / 1270 | **47 / 1270** |
| Fmax | 70.21 MHz | **167.98 MHz** |
| sim gate | PASS | PASS (on the shipping path) |
| STA gate | met | met |

The LE drop is expected and worth understanding: with `i_dspa = o_dspb`
the ADC/NET input muxes and the whole PCM reframer have no consumer, so
the fitter prunes them. **That matters for rung 2** — the reframer must
come back, and it will, because rung 2 gives `pcm_din` a real source.

Implementation is a single `\`ifdef DSP4_LOOPBACK` in
`rtl/dsp4_logic_top.v` (`assign i_dspa = o_dspb;`) plus `LOOPBACK=1` in
`build.sh`, which passes the macro to Quartus, folds it into the hash
input and labels the artifact `dsp4_logic_loopback.<hash>` so it can
never be confused with a shipping one. The manifest says `SHIPPING: NO`
in as many words.

#### Flashed and proven healthy on the card

Programmed over the CM4 JTAG bit-bang (`openocd -f cpld-jtag.cfg`,
IDCODE `0x020a30dd` before and after). With the loopback bitstream
loaded: both DSPs still boot — which is itself the proof that `DSP_CLK`
survives — and PCM_CLK/PCM_FS still toggle on the netprobe, so clkgen is
untouched.

**The SHIPPING bitstream has been restored** and re-verified the same
way: IDCODE good, clocks toggling, chip 1 boots and answers
`MAGIC 0xD5B40001`, `CHIP_ID 1`, `BOOT_STAGE 5`.

#### OPERATIONAL TRAP, cost me a while

**OpenOCD's `linuxgpiod` adapter leaves its GPIOs claimed on exit and
does not hand them back.** After any CPLD flash the SPI link is dead
until `pinctrl set 6,7,8,9,10,11,12,22,23,24,25 a0` is run. It looks
exactly like a bricked card: reads return nothing at all, on either chip,
with the shipping bitstream loaded. This is the same class of trap as the
gpiod/spidev one already recorded for GPIO9/10/11 — same cause, different
tool. Always restore the pins after flashing.

#### Where rung 1 stopped

The remaining work is the pattern firmware and its verdict readout. It did
not start because the verdict channel is not yet trustworthy enough to
carry it: after `CONFIG_COMMIT` the parameter link stops answering, and a
`DSP4_BISECT=29` build added to report from *after* the handshake never
produced a frame — its link was dead from boot, which was not diagnosed.
(One self-inflicted detour on the way: that rung first read a GUESSED
`DMA0_STAT` at 0x31022008; the real address is 0x31022030 and an unmapped
MMR read hangs this core. Named constants only — the header has them.)

**The honest recommendation stands and is now stronger:** run the rung-1
pattern test with its verdicts on the **PB_05 dump**, not the SPI link.
That channel has been reliable all session and every hard fact of the last
three days came off it. The pattern firmware should write its per-lane
results into DM variables and a bisect rung should frame them out — no
host protocol involved.

**Nothing about the four facts rung 1 exists to close** — BCKI/FSI pair
order, sample edge / MFD, within-TDM8 slot order, NET crossed-index — has
been established. They remain PROVISIONAL in `hardware-map.md` and no tags
were retired.

**Bench state:** SHIPPING CPLD bitstream restored and verified; both chips
hold the polled-link production build; GPIOs returned to `a0`;
`matrix-app` restarted and active; three MCUs verified.

### Outcome 2026-08-22 23:5xZ — 🟡 link moved to a polled architecture; much better, still not clean. Rung 1 NOT started.

**Design change, not a workaround: the parameter link is now POLLED from
the DSP main loop and `SPI2_STAT` is no longer routed to the SEC.**
`sec_init()` keeps the audio block clock — the source that genuinely
needs an interrupt — and drops the SPI route; `_spi_poll` in `main.asm`
collects a request whenever `SPI_STAT.RFS` says a whole two-word one has
landed, and is called from both the main loop and `.wait_boot`.

Why: interrupt delivery could enter the handler while the host was still
clocking, so FIFO-full was momentarily true mid-transfer and the drain
took one real word plus one still arriving. Polling only ever looks
BETWEEN transactions, which is exactly why the polled variant read
cleanly all along where the interrupt path never did. Cost is nil — the
loop already wakes on the 1 kHz diag tick with no audio, and per block
with audio.

**`.wait_boot` must poll too, and that is not optional:** the config that
releases that loop arrives over the very link being polled, so with the
SEC route removed and no poll there the firmware waits forever for a
message nothing is collecting. That deadlock happened once during this
work and is now commented in place.

**Second fix: the two `SPI_TFIFO` pushes are separated by NOPs.** Back to
back, the host saw the SAME word twice instead of (echo, value) — one
push was being lost, which is what a FIFO write hazard looks like from
outside. Reads returned (value, value) for every register until the NOPs
went in.

#### Honest state of the link

| case | result |
|---|---|
| reads only, full 24-register block | **11 of 12 consecutive runs clean**; one failed on a single register |
| a write, then reads in the same session | intermittent — sometimes a clean coherent set, sometimes (value, value) |
| writes landing | yes — `PRODUCT_ID` reads back 1 after config, and BOOT_STAGE 6 was proven on both chips earlier via the PB_05 dump |

So it is much better than it was (production reads did not work AT ALL
before this) but it is a race, not a solved problem. Retry-with-echo-check
makes it usable; the echo is verified on every read, so a bad answer is
rejected rather than believed.

#### Why rung 1 is not started

Rung 1 needs: a non-shipping loopback bitstream (build, sim gate, STA
gate, hash label), an OpenOCD flash over the CM4 JTAG bit-bang, pattern
generator and checker firmware on BOTH chips, verdicts read back, four
hardware facts recorded in hardware-map.md, and the shipping bitstream
restored. The toolchain is all present and verified this session —
Quartus 21.1, iverilog 12.0, OpenOCD 0.12 with `/home/app/cpld-jtag.cfg`
(IDCODE 0x020a30dd), and the shipping artifact
`dsp4_logic.a1f6672af6c3.{pof,svf}` is on the Pi ready to restore.

That is several hours of fresh work. Starting it at the end of a session
that has already had one thrashing stretch would repeat the mistake, and
rung 1's whole value is a trustworthy verdict — which wants a link that
is not a race, or a deliberate decision to read verdicts over the PB_05
dump instead (which HAS been reliable all session and is the honest
fallback).

**Recommendation for whoever takes rung 1:** use the PB_05 dump as the
verdict channel from the start rather than the SPI link. It is
out-of-band, it needs no host protocol, and every hard fact established
in the last two days came off it.

**Bench state:** both chips hold the polled-link production build;
`matrix-app` restarted and active; three MCUs verified; GPIOs back to
`a0`. The SHIPPING CPLD bitstream is untouched — no loopback bitstream
was built or flashed.

### Outcome 2026-08-22 23:0xZ — 🟡 read regression largely fixed; polled channel is reliable, interrupt-driven is intermittent

**The two all-zero-MISO events were one fault, and the hub's framing was
right.** It was not the response path at all: the RECEIVE FIFO was being
left holding a single stale word, and with the (correct) RFS==FULL drain
guard the level can then never reach FULL again, so the handler stops
firing and the link is dead from that moment.

Measured, on a verified build (md5 checked both ends):

| | value | meaning |
|---|---|---|
| `SPI2_STAT` | `0x00142001` | **RFS = 2 — one word of two** |
| `SEC_COUNT` / `SPI_RX_COUNT` | frozen at 74 | handler could no longer fire |
| `RESP_DROP` | 0 | nothing was being dropped |

The counters were **identical across two runs with completely different
host traffic**, including one with `matrix-app` stopped to rule out the
other SPI master. That is what proved the handler had stopped rather than
misbehaving.

The residue arrives around the boot handover: `spi2_init()`'s EN-low flush
happens before the host has finished with the port, so a fragment can land
after it.

#### Fix 1 — stuck-partial recovery in the diag timer ISR

A genuine request is only half-arrived for microseconds, so three
consecutive 1 ms ticks with `RFS` neither empty nor full means stale.
Discard one word; if still stuck, discard another. Cheaper and less
disruptive than an EN off/on, which would also throw away a legitimately
queued answer. `_spi_partial_fix` counts how often it fires.

Effect: `SPI2_STAT` goes to `0x00540001` — RFIFO empty, TFIFO empty, no
ROR/TUR/RUWM — and the counters move again.

#### Fix 2 — the host tolerates a one-word rotation, checked by the echo

With the wedge cleared, answers come back but the (echo, value) pair can
arrive rotated — value first. `dsp4_diag.py` now tries both arrangements
and **the echo decides**: an answer is only accepted when the request word
comes back verbatim, so a wrong guess cannot be mistaken for data.

#### Where it stands

| build | reads |
|---|---|
| **polled (bisect rung 27)** | **reliable** — full diag block: MAGIC 0xD5B40001, CHIP_ID 1, BOOT_STAGE 5, TICKS, SEC_COUNT 87, LAST_CSID 71 |
| interrupt-driven (production) | **intermittent** — reads most of the block, then fails on one register with a duplicated word (e.g. 0xE014 returning DMA0_STAT's value twice) |

So the regression is largely fixed but the interrupt path is not yet
trustworthy enough to verify anything else through.

#### Per the hub steer, the pipeline is NOT stopped on this

Rung 1 should proceed using the **polled variant as the verification
channel**, which reads reliably, plus `dsp4_boot`/`stagewatch`. The RFS
build stays on the chips: `CONFIG_COMMIT` lands and BOOT_STAGE 6 is
reached on both.

**Remaining suspicion for the intermittent case,** for whoever picks it
up: the interrupt path can enter the handler while the host is still
clocking the next transaction, so the FULL condition is momentarily true
mid-transfer and the drain takes one real word plus one that is still
arriving. The polled loop only ever looks between transactions, which is
exactly why it is clean. If that is right, the fix is to gate the drain on
the transaction boundary (SPI_STAT.SPIF or the slave-select edge) rather
than on FIFO level alone — worth a look before anything more elaborate.

**Bench state:** chip 1 holds the production RFS build; `matrix-app`
restarted and active; three MCUs verified; GPIOs back to `a0`.

### Outcome 2026-08-22 22:2xZ — 🟡 BOOT_STAGE 6 reached on BOTH chips; the read path regressed doing it

**The rung-1 gate is met.** `dsp4_config.py --product d24` applied on chip 1
and chip 2, proven on a channel that does not use the SPI response stream
at all:

| | chip 1 | chip 2 |
|---|---|---|
| `BOOT_STAGE` | **6** | **6** |
| `BOOT_CFG` | 1 | 1 |
| `PRODUCT_ID` | 1 (d24) | 1 (d24) |
| `SPI_RX_COUNT` vs writes sent | 118 / 51 | **5 / 5** |

Read out with the rung-23 PB_05 dump, which frames `_diag_boot_stage`,
`_boot_config_received` and `_product_id` straight out of DM. Both images
md5-checked on the Pi against the local build before flashing.

#### ROOT CAUSE of the config never landing: the drain guard was on the wrong bit

The handler drains TWO words — a request is two words — but the guard
added on 2026-08-22 tested `SPI_STAT.RFE`, which only means "not empty".
Entering with a SINGLE word present drained one real word and one garbage
one, and from that moment every later pair was shifted by a word.
Permanent desync, and it explains three separate symptoms at once: the
2.3x-too-many handler entries, the host-side word-phase slip, and
CONFIG_COMMIT never being applied.

The right condition is `SPI_STAT.RFS == 4` (Full RFIFO — 2 words at
32-bit word size), which is also exactly what the RUWM=FULL interrupt
trigger means. With it:

- chip 2 shows **5 handler entries for 5 writes**, a clean 1:1 where the
  RFE guard gave 2.3x;
- `CONFIG_COMMIT` applies and `BOOT_STAGE` goes to 6 on both chips.

Before the change, with the RFE guard, the same 51 writes left
`BOOT_STAGE 5`, `BOOT_CFG 0`, `PRODUCT_ID 0` — the config was being
received and thrown away.

#### REGRESSION, and it is honest: reads now return all-zeros

The same change broke the read path. On a production (`DSP4_BISECT=0`)
build with the RFS guard, every raw read returns `0x00000000` on MISO —
chip 1 alone and with both chips booted, at 1 MHz, tested repeatedly. The
200-round-trip harness fails on the first read.

So the two states are:

| build | writes / CONFIG_COMMIT | reads |
|---|---|---|
| `f2bdb93` (RFE guard) | **do not land** — stage stuck at 5 | work |
| RFS guard (this commit) | **land** — stage 6 both chips | return zeros |

The RFS guard is kept because it is provably the correct condition for a
two-word protocol and it is what reaches stage 6, which is the gate the
pipeline needs. The read breakage is a second, adjacent defect and it is
NOT the parked rung-0 item — rung 0 is about writes *answering*, this is
about reads *being answered at all*.

**What is excluded already:** the handler runs (`SPI_RX_COUNT` climbs
1:1), it returns (later transactions are still processed), the receive
side is clean, and the write dispatch works end to end. So the fault is
between `.spi_read` and the two `dm(SPI2_TFIFO)` writes. First thing to
check next session is whether `_diag_read` still leaves r0 intact now that
the guard changed which register holds what on entry — the guard's compare
now uses r2/r3 where the RFE version used r2/r3 differently, and r2 is the
decoded address the read path depends on.

#### Also in this commit

- `dsp4_config.py` had chip 2 documented and defaulted as **GPIO7**; it is
  **GPIO24**, the same defect already fixed in `dsp4_diag.py`. Corrected in
  the docstring, the `--cs-gpio` help and a new default.
- `dsp4_config.py --verify` reads `BOOT_STAGE` / `BOOT_CFG` / `PRODUCT_ID`
  / `SPI_ERR_COUNT` / `RESP_DROP` back after writing and says whether the
  commit landed. It works only when the read path does, so it is not
  usable on this build — kept because it is the right shape for the tool
  and costs nothing.
- The rung-23 dump now carries `BOOT_STAGE`, `BOOT_CFG` and `PRODUCT_ID`
  in place of the SEC route words, which is what made this diagnosable
  without the SPI response stream.

**Rungs 1 and 2 not started.** The gate is met, but starting a CPLD
bitstream while the parameter link cannot be read back would be building
on a channel I cannot verify.

**Bench state:** both chips hold the rung-23 config-dump images from the
last measurement; `matrix-app` restarted and active; three MCUs verified;
GPIOs returned to `a0`.

### Outcome 2026-08-22 21:4xZ — 🔴 rung 0 attempted and REVERTED; tree is back at the known-good commit

**Nothing shipped. The tree is exactly `f2bdb93` for all firmware and host
files, rebuilt and re-verified on the bench after the revert: chip 1 reads
its whole diagnostic block with both chips booted.** Rungs 1 and 2 were not
started — rung 0 is their gate.

#### What was tried

The word-phase fix as specified: make every accepted transaction queue
exactly one two-word answer (write / unmapped-address / `DIAG_NOP` answer
with value 0), in both `spi_handler.asm` variants, with the protocol notes
in `diag.asm` and `diag.h` updated and `dsp4_diag.py` restored to the plain
two-step read.

**Result: MISO went to all-zeros on every transaction, reads included** —
i.e. worse than the known-good, which reads correctly. Two variants, same
outcome:

1. **Echo stashed in a `.var`,** reloaded in the responder because the
   write paths clobber r0. The variable itself was fine — a rung-23 dump
   read `_spi_req_word = 0xE0FE0000`, the last `DIAG_NOP` request, exactly
   right. But every answer still went out as zero.
2. **Echo queued while r0 is still live** — the write side calls a new
   `_spi_queue_resp` subroutine immediately after the READ-flag branch,
   before the dispatch clobbers r0; the read path calls the same
   subroutine. No memory round trip at all. Same all-zero result.

#### What the evidence says, and does not say

On the failing build the part is **healthy everywhere except the answer**:

| | value |
|---|---|
| core alive | `DIAG_TICKS` climbing |
| handler running | `SEC_COUNT` = `SPI_RX_COUNT` = 86 over ~48 words |
| receive side | `SPI2_STAT = 0x00540001` — RFIFO empty, no ROR, no TUR, no RUWM |
| responses dropped | `RESP_DROP = 0` |

So the receive path, the interrupt delivery and the dispatch are all still
working; only the queued answer is wrong. That points at the two `dm(SPI2_TFIFO)`
writes or the registers feeding them, not at anything upstream.

**Do not trust one earlier reading.** A `RESP_DROP = 0` / `REQ_WORD = 0`
pair was taken from a STALE image: the rung-23 build failed on an
unresolved symbol (`_spi_req_word` needed `.global`), but the shell chain
continued because the `grep` guarding it matched the error text and exited
0, so the previous `.ldr` was flashed and read. Caught and re-run after
fixing the link; the numbers in the table above are from a verified build.
**Rebuild-and-md5 before every dump reading from here on.**

#### Next suspects, in the order worth trying

1. **TFIFO occupancy.** Once every transaction queues, a two-deep TFIFO is
   written on every transaction instead of only on reads. If the read
   answer is queued while the previous write answer is still unshifted it
   takes `.spi_read_drop` — which should show in `RESP_DROP`, and did not,
   but that counter deserves re-checking on a verified build before the
   theory is discarded.
2. **PC-stack depth inside the SEC ISR.** Variant 2 adds a third nested
   `call` (`_sec_isr` → `_spi2_rx_work` → `_spi_queue_resp`, and
   `_diag_read` is already a third on the read path, making four). Cheap
   to test: inline the queue instead of calling it.
3. **Does `_diag_read` really preserve r0?** Its comment says so and the
   known-good code depends on it, but the known-good code reads r0 at a
   different point in the flow than variant 2 does.
4. **Fall-through.** `.spi_read_zero` used to fall into the responder
   label; after the restructure that label is a subroutine ending in
   `rts`, so the zero path now returns straight to `_sec_isr` and skips
   the `.spi_done` epilogue (the ILAT/STAT clear). Not the cause of the
   all-zero MISO — `.spi_read_zero` is only reached for out-of-range or
   unmapped addresses — but it is a real defect in the reverted-away code
   and must not come back when this is retried.

#### Recommendation

Retry rung 0 as a **strictly smaller step**: leave the read path exactly as
it is in the known-good build, and add the write-side answer alone, inline,
with no new subroutine and no new variable. Verify MISO on a raw read
BEFORE adding the 200-round-trip harness — the harness masked which half
broke for two build cycles.

**Bench state:** both chips hold the known-good production images
(`chip1.ldr`/`chip2.ldr` = the `f2bdb93` build); `matrix-app` restarted and
active; all three MCUs verified; GPIOs returned to `a0`.

## QUEUED DISPATCH (fire after the early-audio block) — DESK FILLERS: SPI2_RDY never asserts · 570Z scratch-fit · OSPI clock gate   [status: 🟢 ALL THREE DONE — (1) SPI2_RDY CLOSED, not usable on this silicon (already FCEN/FCCH/FCPL as hoped, pin driven and idling asserted, but a guaranteed 16-word overfill never deasserts it at any of the three legal FCWM values, 0/40 each). (2) 570Z scratch-fit DONE and then OVERTAKEN BY EVENTS: 157/570 LE but only +0.842 ns slack, then FAILS timing at -0.198 ns once the Pi return is added, and the 8-channel CM4 link needs 738 LE which does not fit 570 at all — PW has since dropped rev-D mod 3 and kept the 1270Z. (3) OSPI/xSPI CLOSED by the hub from the datasheet now in _Matrix/_ref/adsp-2156x-docs: octal + DDR + HyperBus (HyperFlash AND HyperRAM), dedicated xSPI0_RWDS pin, DQS; 50 MHz untrained / 80 MHz trained no-DQS / 125 MHz trained with DQS, Table 37 characterised at 166.66 MHz, MASTER ONLY. Verdict for mod 1: HyperRAM 2.0 at 125 MHz DDR = 250 MB/s, not 200 MHz. PLUS a pin finding the timing verdict does not cover — Table 10 shows xSPI0 is MUXED ONTO THE SPI2 PINS: PA_00 MISO/D1, PA_01 MOSI/D0, PA_04 CLK, PA_05 SEL1, and D2-D7 take PA_02/03/06-09. SPI2 on PA_00/01/04/05 is this card's host parameter link AND the BMODE=0b010 slave-boot port, so fitting xSPI0 octal consumes it entirely. SPI1 (PA_10-13) is the only SPI clear of xSPI0. That is a mod-1 design question, not a timing one, and it would otherwise surface at PCB stage]) are both illegal on the 570Z in the same T144 package and must move. The AK5558 BICK/MCLK constraint is NOT assessed - the rev-D lane map has no RTL. (3) OSPI BLOCKED on document access: HRM ch.16 confirms Octal DDR/DTR and data-capture tuning but contains NO mention of RWDS, HyperRAM, HyperBus or xSPI 'profile'; the max-clock figure is a datasheet spec and every route is blocked (analog.com times out, verical 403, mouser times out). ASK: drop the Rev D datasheet into _Matrix adsp-2156x-docs and this closes in minutes]

model: opus

All desk work, no bench contention beyond a register read; do them in order,
stop when done or blocked, push main.

1. **SPI2_RDY never asserts** (20:3xZ loose end). With RFIFO empty the part
   holds FCS set and PB_05 low under FCPL=1/FCWM=1. Read HRM ch.15 flow
   control end to end (FCEN, FCCH = which channel RDY follows, FCPL, FCWM,
   the TX-channel rule — RDY may be following the TFIFO, not the RFIFO) and
   find the configuration under which RDY means "slave can accept a
   transaction". Prove with a register dump + PB_05 reading on the bench.
   If RDY can be made meaningful, add `--rdy-gpio 8` honouring to spiraw.py
   / dsp4_diag.py and re-measure; if it cannot on this silicon, write that
   verdict and close the item — either way rev-D mod 9 (RDY pull-up) stands.
2. **570Z scratch-fit** (tasks item 6 open): fit the rev-D unified lane map
   (2×TDM16/direction AK5558 cascade, 1×TDM8 AK4619, Pi I2S→TDM8 with MEMS
   at slots 5-6, one TDM32 NET pair, D32 snake on the same pair) into a
   5M570ZT144C4N scratch Quartus project from the current dsp4_logic RTL.
   Record LE/pin utilisation, the MEMS-input pin move off PIN_137, and
   whether clkgen meets the ±10 ns BICK↓ vs MCLK↑ constraint for the
   cascaded slaves. Deliver numbers into the rev-D list (mod 3/4 rows via
   the hub — report, do not edit TransferOnly from this machine).
3. **OSPI clock gate** (rev-D list §D, open): from the ADSP-2156x data
   sheet OSPI timing section, the max OSPI clock (133 vs 200 MHz) and
   whether xSPI profile-2 / RWDS-strobe HyperRAM 2.0 is supported; confirm
   against the EV-21568-SOM reference design. Verdict for mod 1's final part
   pick; report to the hub.

Rules as above: bench = rev-C CM4 app@192.168.1.219; rev A hands-off; leave
matrix-app running + 3 MCUs verified; single trunk; no AI attribution.
When done or blocked, continue straight into the next QUEUED block.


**CM4 stereo send + return = the USB 2-track path.** The *requirement* is
PW's ("on final product cm4 pi needs a stereo send and return to dsp", plus
"this same stereo path is the source/sink for USB 2-track audio play/rec").
**The slot allocation below is NOT PW's — PW said "you can choose most
convenient slots". It is HUB-ACCEPTED 2026-08-23, PW TO RATIFY.** It is
sensible on the face of it (no PCB change, no new pin) but it has not been
ratified:

| direction | line | slots | signal | USB role |
|---|---|---|---|---|
| Pi → DSP | `A_I6` | 0, 1 | `PI_PCM_L/R` | 2-track **PLAY** sink |
| DSP → Pi | `B_O3` | **2, 3** | `PI_RET_L/R` | 2-track **REC** source |

Chosen because `B_O3` had only slots 0/1 used (provisional `DAC_MAIN`, no
D24 sink), 2/3 keep clear of DAC MAIN on D32, and it needs **no PCB change
and no new pin** — `B_O3` already reaches LOGIC as `dac_main` and `pcm_din`
is an existing net to GPIO20. Done at the single source (`slot-map.csv`),
so one edit feeds both the CPLD constants and the DSP SPORT map; new slot
map hash `sha256:1507e8813e3db2bb…`. Documented in
`MW/D32/DSP/dsp4-plumbing.md`. 48 kHz only — D7 excludes USB audio on the
96 kHz products.

The capture path is now a **product feature**, out of the `DSP4_LOOPBACK`
ifdef, so the shipping bitstream changes deliberately: **156 → 312/1270 LE
(25%), Fmax 70.21 → 66.18 MHz**, still 35% margin at 49.152 MHz.
**This flips the 570Z answer**: the same design is 312/570 LE (55%) and now
**fails timing at −0.198 ns**, where it met +0.842 ns before the return.

**Open, and it is a matrix question:** nothing writes `B_O3` slots 2/3 yet,
so the return is silent. What feeds `PI_RET_L/R` — a dedicated stereo bus
(recommended: a USB recording usually wants its own mix) or a copy of the
main mix? Needs node definitions from mx26.

**Bitstreams:** shipping `dsp4_logic.758b7c82ef6e`, bring-up
`dsp4_logic_loopback.1e831a2cf29d`. The bench still carries
`dsp4_logic_loopback.3f488870d6cb` on purpose — that one captures `B_O3`
slot 0 (`MAIN_ST_OUT`), which is the only slot anything drives today.

## QUEUED DISPATCH (fire after the desk fillers) — VIRTUAL AUDIO TESTS over the CPLD feedback loop: the golden harness gets a hardware target   [status: 🟡 PASS-THROUGH IS UNITY AND BIT-EXACT; blocked on Pi duplex streaming. The 4x is RETRACTED - it was my measurement, a peak taken from an overrun-riddled capture. Known-word test (hub's method): 0x00001000/0x00010000/0x00100000 all return identically, ratio 1.0000, in << 0, 100% of non-zero frames. Shifts corroborate: chip1 scatter >>3, chip1 gather none, chip2 scatter none, chip2 gather <<3 saturating - paired, no net shift. REAL BLOCKER is the CM4 soundcard: capture alone is 100% stable (rung 2) and playback alone reaches the DSP (lane-6 RX shows live tone), but BOTH TOGETHER scramble - a per-sample counter returns values under ~200 across 20,000 frames instead of climbing to 48,000, dominant step -191, with ALSA reporting no under/overrun once period/buffer are pinned. Suspect my own overlay: dsp4-pcm-slave.dts uses TWO dai-links sharing one bcm2835-i2s CPU DAI (dit=playback, dir=capture) because the dummy codecs are one-directional - two PCM devices, not a true duplex device. FIX DIRECTION: one dai-link with a codec declaring both directions; device-tree work, not DSP. Latency deliberately NOT reported - it would be fiction through a stream repeating a 200-sample window. ALSO: nothing drives SPORT3 slot 1 on chip 2 (C2_MAIN_ST_OUT writes slot 0 only despite 'Channels: 2'), so the capture's right channel is correctly silent - graph/generator question for the hub. CPLD carries dsp4_logic_loopback.3f488870d6cb per the hub ruling] -> reframer capture -> pcm_din -> arecord. SIGNAL PRESENT, peak 0x7BB7C120. Two blockers cleared: the capture was tapping o_dspb[0] (AUX_OUT_01/02, silent in a pass-through) instead of o_dspb[3] (MAIN_ST_OUT) - new bitstream dsp4_logic_loopback.3f488870d6cb; and the Pi input is gated OFF by default, _auxin_on_C2_PI_IN at SPI 0x071D on chip 2, one poke opens it. Everything downstream already defaults to unity and the Q4.28 shadows refresh at block rate, so they are not a second gate. NOT bit-exact yet: input 0x20000000 comes back 0x7BB7C120, a ratio of 3.87 - close enough to 2^2 to look structural, and the scatter/gather Q1.31<->Q4.28 shifts are the first place to look. Also bursty (~4.5% of frames carry signal, aplay reported an overrun), so playback buffering must be pinned before any latency figure or it measures ALSA. Harness --target hw and the five families NOT started - the block itself says fix bit-exactness first. CONFLICT for the hub: this block says leave the loop soaking, the standing Rules say restore the SHIPPING bitstream; they cannot both hold. I restored SHIPPING as the older standing rule on a 24/7 bench - say which wins]

model: opus

Precondition: early-audio rung 2 delivered (Pi aplay → DSPA I6, DSPB lane
de-framed back to Pi arecord over the CPLD loopback bitstream; soak clean).
Purpose (PW 2026-08-22): exercise gain, EQ, dynamics etc. with generated
tones and levels through the REAL SHARC path and measure, no ears, no
converters. The yardstick already exists — `shared/numeric-spec.md`
"Acceptance tolerances (golden harness)", `tools/dsp/golden_harness.py`,
`tools/dsp/fixed_ref.py`. The hardware becomes a third target of the same
harness: target ≡ fixed_ref (bit-exact), fixed_ref ≈ float64 (tolerances).

1. **Path calibration first.** Pass-through strip (all nodes unity/bypass):
   play the standard vector set, capture, align by a known preamble, and
   prove the loop is bit-exact end to end (Pi I2S → TDM slot → SPORT → node
   chain → SPORT → TDM → I2S). Record fixed latency in samples. If the loop
   is not bit-exact, STOP and find why (slot/justification/MSB-first,
   24-vs-32-bit, sign extension) — nothing below is meaningful until it is.
2. **Harness extension.** `golden_harness.py --target hw`: for each vector
   and parameter set, push parameters over the SPI link (dsp4_config.py /
   diag protocol, float32 words as today), play, capture, compare against
   fixed_ref bit-exact and float64 within the spec tolerances. One report
   per kernel family with pass/fail and worst-case deviation.
3. **Families, in this order** (each on one channel strip, chip 1, then the
   output-side twin on chip 2 where one exists):
   - GAIN / FDR: stepped levels −60…+18 dB, ±0.5 LSB; fader ramps — no
     zipper (spectral check during a ramp), ramp time vs cell table ±2 %.
   - EQ / FILT / GEQ: swept sine or MLS → magnitude/phase per band at several
     f0/Q/gain, ±0.01 dB (≥50 Hz), ±0.05 dB at 20 Hz; residual < −120 dBFS.
   - COMP / GATE / LIM: tone bursts at stepped levels → static curve ±0.05 dB
     (threshold, ratio, knee, make-up); attack/release from envelope fits
     ±2 %; gate hold/range; limiter ceiling never exceeded.
   - DLY: sample-exact delay vs setting; TUBE: harmonic series vs reference.
   - Bus summing: exact to LSB; MTR: peak readback over SPI vs captured peak.
4. **Keep the vectors.** Commit stimulus generators (not WAVs), the hw
   capture alignment tool, and the per-family reports under tools/dsp/;
   results table into findings (dsp4-architecture-decisions.md D5 gets a
   "hardware-verified" line per family with date + build id). Any family
   that fails is a firmware bug or a spec [REVIEW] to resolve — report it,
   do not loosen the tolerance.
5. Leave the pass-through loop soaking when you stop.
   **HUB RULING 2026-08-23 14:30Z on the bitstream conflict: while THIS block
   runs, the loopback-capture bitstream stays on the CPLD (the soak needs it;
   the bench is 24/7 and nobody else is on the unit). The standing rule
   "restore SHIPPING before ending" applies at the END of this block, before
   any hand-off to PW, or the moment PW says the unit is needed — the hub
   will say so. Record the currently-flashed bitstream hash in the block
   status at every stop so the state is never ambiguous.**

Rules as above. This is the item PW most wants to see results from; write
the results table so it reads at a glance.

## QUEUED DISPATCH (fire after the virtual-audio block) — KERNEL REWRITE: per-block kernels + cheaper RTG/bus/dynamics + scope gating (PW GO 2026-08-23)   [status: 🔴 queued]

model: opus

Goal: the full 32-strip D24 graph in real time on the two SHARCs as fabbed,
with margin — target ≤ 70 % of the 327,680-cycle block budget on chip 1, chip
2 lower, at 32-sample blocks (block size does NOT change; latency preserved).
Evidence: MW/D32/DSP/dsp4-cycle-budget.md (today 660 %; RTG 601 cyc/sample,
EQ 338, fixed overhead 44 %). Numeric contract: shared/numeric-spec.md (D5).

Method — one family at a time, in profile order, measured after each:
0. BASELINE: the virtual-audio harness results on the CURRENT kernels (the
   block above) are the reference; every rewritten family must pass the same
   rows bit-exact vs fixed_ref before it replaces the old one. The cycle
   instrument (TCOUNT per class) runs on every build — update the table.
0a. STATUS 2026-08-24 (one-read picture)
   CONVERTED AND VERIFIED, default build byte-identical throughout:
     block I/O + IN   67,809 -> 32,707 cycles/block   2.07x  (scatter deleted)
     GAIN              2,321 ->    574                4.04x
     FDR               4,404 ->  1,886                2.33x
     RTG              19,186 ->  2,626                7.3x
     FILT              6,973 ->  4,062                1.72x
     EQ               11,590 ->  7,998                1.45x
     GATE              5,999 ->  4,891                1.23x
     DLY               4,185 ->  2,000                2.09x
   Only COMP and TUBE remain unconverted (243 cycles/sample together, 24%
   of a strip). STRIP 1,973 -> 1,005 cycles/sample over the whole rewrite.
   PROJECTED CEILING 2.91 -> 6.79 strips. D24 4.6x -> 3.5x over. Converting
   the last two at DLY's 2.09x would reach ~7.7 strips, still 3.1x short of
   D24 - every class is now converted or measured, the total is better by a
   factor of two, and it does not close the gap.
   BIT-EXACT END TO END: GAIN -> FDR -> RTG -> BUS verifies 0 LSB at 7
   points (level 1.0/0.5/0.25 x pan 0/0.25/0.5/0.75) - mono, pan-split L
   and the summed bus, including the 64-bit accumulator's single round at
   readout. RTG's earlier cycles-only caveat is CLOSED.
   Boot-time input patch (_rx_patch_regs) folded into the per-node offset,
   so the D24 console interleave still applies with DMA-direct kernels.
   sec_dmda 21,046 words vs 20,840 default, ceiling ~22,500. Bus
   accumulators sit in L2 (no room internally), so RTG is conservative.

   STRIPS CEILING - MEASURED 2026-08-24 on the default build: STILL 2.
     STRIPS=2  1500 transport / 1500 _proc_passes  REAL_TIME
     STRIPS=3  1500 transport / 1329 _proc_passes  OVER_BUDGET
   That is the expected answer, not a disappointment: the default image is
   byte-identical (d1c3dd5c/85d546f9), so its ceiling could not have moved
   - every conversion sits behind DSP4_BLOCK_KERNELS. 1329 reproduces the
   1342 measured before the rewrite.
   The CONVERTED build's ceiling cannot honestly be measured yet and was
   not: there the six unconverted classes run once per block instead of 32
   times, so a strips sweep would flatter itself ~32x on 88% of the strip.
   Use _proc_passes, never FRAME_COUNT - the ISR advances FRAME_COUNT
   whether or not the loop keeps up, and a first attempt that used it
   reported an impossible 2023 blocks/s.
   PROJECTED for the converted build: 2.91 -> 5.17 strips at 1x.
     per strip 63,131 -> 42,306 cycles/block (saved 20,825)
     fixed overhead 144,166 -> 109,064 (block I/O saved 35,102)
     328k budget - 109k fixed = 219k / 42.3k per strip = 5.17
   NOT measured, and deliberately so: a strips run on the block build would
   flatter itself badly, because the six unconverted strip nodes only run
   ONCE per block there and so appear 32x cheaper than they are. A real
   ceiling needs the whole strip converted. Against 32 strips required,
   5.17 says the remaining classes still have to come.

   PARKED, with state notes below and in dsp4-cycle-budget.md:
     FILT/EQ  CONVERTED 2026-08-24 (fourth attempt) - both bit-exact.
              FILT 6,973 -> 4,062 cycles/block (1.72x); EQ 11,590 ->
              7,998 (1.45x); both baselines re-measured on the CURRENT
              build, not taken from the pre-rewrite table. Strip 1,329 ->
              1,141 cycles/sample, projected ceiling 5.17 -> 5.99 strips,
              unconverted share 88% -> 52%, D24 4.6x -> 4.0x over.
              WHAT UNBLOCKED IT: a self-test on the part (DSP4_BQ_SELFTEST)
              ran _bq_fx_cascade_blk against _bq_fx_cascade_N on identical
              data - two stages with DIFFERENT coefficients, across a block
              boundary - and found 0 differing samples of 64. The routine
              was never the fault; the wrapper was. Three things it has to
              get right: input and output are DIFFERENT pool slots (the
              cascade works in place); i1 carries over HPF -> LPF; and
              crossfades are handed to the per-sample body a sample at a
              time via a new _<nid>_process_sample label, so the alpha
              bookkeeping and mid-block completion are right by
              construction instead of re-derived - re-deriving them is what
              defeated attempt one.
              Historical note, superseded: PARKED after three attempts. _bq_fx_cascade_blk is written,
              assembles, and its i0-advance-between-stages bug is now FIXED
              (it was only correct for r4=1, so EQ at r4=4 would have run
              every band with band 0's coefficients). That fix does NOT
              explain the failure: FILT calls it with r4=1, so i0 never
              advanced there. Wired, both_unity passes at 0 LSB and every
              real filter fails.
              CORRECTION, and it is the useful product of attempt three:
              the earlier reading of that unity pass was WRONG. With unity
              coefficients b1=b2=a1=a2=0, so y=x and the stored state
              contributes NOTHING - unity is blind to state. It therefore
              does NOT show that "the block plumbing is exercised and
              correct". Any wrong state pointer (wrong instance, wrong
              stride, HPF and LPF sharing a state block, state not
              persisted across blocks, the A/B crossfade instance) passes
              unity at 0 LSB and fails every real filter. Suspect order is
              now: (1) the state pointer the wrapper hands to i1 - test it
              with two sections carrying DIFFERENT coefficients; (2) state
              persistence across block boundaries; (3) only then MAC-unit
              implicit registers and m-register interference.
              A line-by-line diff of the two inner bodies was done: the
              arithmetic, MAC order, rounding, saturation test, error
              feedback and state store order are IDENTICAL to
              _bq_fx_cascade_N. It is not the maths. The block cascade is
              present but currently UNWIRED.
     COMP  still unconverted, but the "not worth converting" verdict is
              now SUSPECT and should be retested. It was judged on a bare
              WRAP, and GATE - the same class of node, also 8% slower under
              a wrap - converted at 1.23x once the block-invariant work was
              hoisted out of the sample loop (the _sample_idx guard, the
              on/off tests, four constant reloads, register-resident
              state). The general lesson on this page says a wrap alone
              buys nothing; COMP was measured that way and no other.
     TUBE  unconverted, 40 cycles/sample, trivial.
     Historical note, superseded: COMP/GATE NOT WORTH CONVERTING. A wrap alone measured
              8% SLOWER; the gain computer everyone assumed was the cost is
              only 9.6% of COMP; and _compgain_fx clobbers all but four
              registers so almost nothing can be hoisted across it. Ceiling
              is ~5% net. Step 4 of this plan (block-rate gain computer +
              interpolation, needing a numeric-spec amendment) is withdrawn
              on those numbers.

   THE GENERAL LESSON, measured three ways: a wrap on its own buys nothing.
   Every win so far came from work LIFTED OUT of the sample loop - the
   guard, hoisted invariants, inlined helpers, a gating tree run once. Ask
   of each remaining class "how much can be lifted", not "can it be wrapped".

   SCOPE GATING (step 6) DONE - and the projection above that called it
   "the biggest single remaining lever" was WRONG. Only 34 of the 431 nodes
   carry a scope= at all (32 D32-only, 2 D24-only, all of them TDM in/out,
   interchip send/recv and aux input). Measured booted as d24:
     no gating at all (control)   243,235 cycles/block
     per-NODE skip table          244,795   +1,560  A NET LOSS
     contiguous-RUN gating        241,744   -1,491  kept
   The per-node table loses because a table read and test before ALL 431
   dispatch calls costs more than not calling the 34 scoped ones, and that
   ratio does not improve per-sample either - check and node cost both
   scale by 32. The mechanism that works is one compare and one branch per
   contiguous RUN of same-scope nodes: two runs on chip 1, ~8 cycles/block
   against 1,491 saved. DSP4_SCOPE_GATE=1 selects it; the default image
   stays byte-identical. Chain still 0 LSB with a run branched over.
   Worth 0.46% of budget here, up to ~14% inferred for a per-sample build.
   Either way it is NOT a lever that changes the capacity picture.

0b. BASELINE MEASURED 2026-08-24 (post-fix build). Harness families are
   green and recorded in tools/dsp/hw-reports/README.md - that is the
   bit-exactness reference. GAIN cycle baseline re-measured on the current
   build: NODE_LIMIT=1 (IN only) 67,809 cycles/pass, NODE_LIMIT=2 (IN+GAIN)
   70,130, so GAIN = 2,321 cycles/block = 72.5 cycles/sample. Almost all of
   that is overhead - a call/rts per sample, the _sample_idx==0 guard
   evaluated 32x, and a second call/rts into _mrf_rns28.

0c. DESIGN, decided 2026-08-24 before any code. The conversion is NOT
   node-local: a per-block kernel needs per-block BUFFERS, so the sample
   loop, scatter/gather and every node buffer move together. Shape:
       for s in 0..31: scatter(s)        -> fills 32-word input buffers
       process_all_block()               -> one call per node per block
       for s in 0..31: gather(s)         -> drains 32-word output buffers
   Each node's `.var _buf_X` becomes `.var _buf_X[32]`; the block-rate
   section (ramp + Q4.28 shadow refresh) runs ONCE at kernel entry with no
   guard, and the 32-sample loop wraps only the arithmetic. _mrf_rns28
   should be inlined in the loop rather than called.
   Do it behind DSP4_BLOCK_KERNELS (default 0) so the tree stays buildable
   and the per-sample path remains the reference to diff against. Convert
   IN + GAIN first and profile at NODE_LIMIT=2, which needs no other node
   to change; roll the rest of the chain class by class after.
   Expected for GAIN: the arithmetic is ~8-12 cycles/sample, so the target
   is under ~400 cycles/block against 2,321 - a 6x class of win, and the
   same overhead is paid by every one of the 431 nodes.

1. GENERATOR: nodes become per-BLOCK kernels — one call per node per block,
   the 32-sample loop inside the kernel, parameters fixed once per block (as
   D5 already specifies). Control/ramp plane unchanged. Prove on GAIN first
   (simplest): bit-exact + cycles/sample, then roll the generator change
   across the classes as each kernel is rewritten.
2. RTG + bus/send path (the measured hot spot, 601 cyc/sample + 24 % fixed):
   a send to N buses is N MACs; drop per-sample table walks, compute routing
   masks at block rate, SIMD the accumulate. Target ≤ 40 cyc/sample.
3. EQ / FILT: D5 fixed-point biquads, wide accumulators, SIMD two channels
   or two sections; coefficient staging at crossfade-swap as implemented.
   Target ≤ 25 cyc/sample for the strip's bands.
4. COMP / GATE / LIM: envelope per sample (one-pole Q4.28), gain computer
   (log2/exp2 polynomials) at BLOCK rate with per-sample interpolation of the
   gain — write the interpolation as a numeric-spec amendment with its error
   bound, verified by the harness dynamics rows. Target ≤ 50 cyc/sample for
   COMP+GATE.
5. Block I/O (20 % fixed): scatter/gather without the per-sample Q-format
   shuffles — convert once per lane per block; meter scan at block rate.
5b. METERS — fold in the MTR-node rework (added 2026-08-24 by hub steer).
   Measured 2026-08-23: the MTR node class is numerically meaningless. It
   loads a Q4.28 INTEGER and does `f0 = abs f0`, and r0/f0 are the same
   SHARC register, so the bit pattern is reinterpreted as IEEE-754 — peak
   read 3.85e-34 for a 0.5 input. RMS is dead (the peak branch takes an
   early rts before the RMS update), decay runs per sample against a
   comment written for the 1500 Hz block rate so the time constant is 32x
   fast, and _mtr_gr is declared and never written. Values are host-visible
   at SPI 0x1200/0x1201 with mislabelled dispatch comments.
   The LIBRARY meter path (_meter_peaks[], _meter_scan_chip1) is correct
   and is what the host readback contract uses — measured 0.49975 for a 0.5
   input, converting properly and decaying per block.
   OPTION FOR THE HUB TO DECIDE HERE: if the library meter is the only path
   the host contract uses, RETIRE the MTR nodes rather than repair them —
   that removes ~32 nodes per chip from the per-sample graph, which serves
   this block's cycle-budget goal directly. If they are kept, they need the
   fixed->float conversion, the RMS ordering fix, a decay-rate decision,
   and a meter model added to fixed_ref.py (there is none) before they can
   go under the harness. Report: tools/dsp/hw-reports/mtr-2026-08-23.md.
   Also unmeasured but found by inspection: _meter_decay_block decays 32
   entries while _meter_scan_chip1 writes 46, so 32-45 never decay.

6. SCOPE GATING (option 3): make _scope_gates_apply real — D24 runs only D24
   nodes; bypassed nodes are skipped at the dispatch table, not inside the
   kernel. Measure the D24 graph, not D32's.
7. After each step: re-run the cycle table + the harness rows for the touched
   family; record cyc/sample before/after in dsp4-cycle-budget.md; commit.
   Stop condition for the block: 32 strips at 1x with FRAME_COUNT 1500/s and
   all harness families green, or a precise state note of where it stands.

Rules: bench = rev-C CM4 app@192.168.1.219; the loopback-capture bitstream
may stay flashed while this block runs (same ruling as the virtual-audio
block); restore SHIPPING at the end; rev A hands-off; matrix-app running +
3 MCUs verified at every stop; single trunk; no AI attribution; numeric-spec
changes are amendments with a date, never silent.

## QUEUED — PRODUCT CONCEPT (PW 2026-08-23): low-cost 8x8 mixer on a Pi, software DSP, dual FX   [status: 🔵 concept, not scheduled — for PW/hub decision, no build work started]

model: opus

PW floated this in conversation on 2026-08-23; recorded here so it is not lost.
NOT a dispatch. Nothing is committed to and no schedule is implied.

THE CONCEPT: 8 in / 8 out mixer, DSP done in software on the Pi itself (no
SHARC card), dual FX only, small screen, no buttons, simple and low cost.
Candidate platform floated: Raspberry Pi Zero 2 W.

WHERE IT SITS IN THE RANGE: below everything D6/D7 govern (those start at
32 ch). It does not conflict with the D6 platform split or the D7
fabric-only baseline. It WOULD introduce a THIRD engine platform alongside
SHARC (D5 fixed-point) and FPGA fabric — that is the strategic cost and it
is a hub/PW call, not an engineering one.

MEASURED (this bench, 2026-08-23):
- matrix-app RSS = 237 MB (self-contained .NET/Avalonia, VSZ 3.6 GB) on the
  rev-C CM4, which has 730 MB usable. That is the number any UI alternative
  has to beat, and it is over half a 512 MB Zero 2 W before audio allocates.
- bcm2835-i2s is hard-limited to 2 channels per direction (already recorded
  in MW/D32/DSP/dsp4-plumbing.md). 8x8 at 48 kHz CANNOT come off the Pi PCM
  pins directly.
- Route A works and is proven: 2 ch x 32 bit @ 192 kHz = 12.288 Mbit/s =
  exactly 8 ch x 32 bit @ 48 kHz. Duplex measured 191999/191999 frames clean.
  So one stereo 192 kHz link carries all 8 channels each way — but ONLY with
  external re-framing logic (dsp4_pcm_reframe.v already does this).

ESTIMATED, NOT MEASURED — flagged as such:
- 8 strips + 8x8 matrix + 8 output strips + 2 FX is roughly 2,700 flops per
  sample, ~130 MFLOP/s at 48 kHz: order 10 % of ONE A53 core with NEON.
  The DSP maths is not the constraint. Do not quote this as measured.
- The SHARC 6.6x-over-budget finding does NOT transfer: that graph is 431
  nodes invoked PER SAMPLE (13,792 calls/block). A block-processed software
  design does not inherit that structure.
- Pi Zero 2 W carries the same BCM283x PCM block as the CM4 and should take
  the existing dsp4-pcm-slave.dts unchanged (it is compatible = "brcm,bcm2835"
  and targets the generic &i2s_clk_consumer / &sound labels). UNVERIFIED —
  no Zero 2 W has been on this bench.

THE REAL RISKS, in order:
1. Linux real-time behaviour, not MIPS. SDIO Wi-Fi DMA contention, non-RT
   preemption and thermal throttling are the likely xrun sources. Needs
   PREEMPT_RT, isolcpus, SCHED_FIFO, Wi-Fi power-save off. Which cause
   actually dominates is MEASURABLE (cyclictest + xrun counters) and should
   be measured before any distro or platform commitment.
2. You still need a logic device. The CPLD does not go away; it is cheap
   (re-framing only, far simpler than DSP4 LOGIC) but it is in the BOM.
3. Zero 2 W is a BOARD, not a module — no castellations, no SO-DIMM, and
   RPi guidance for products is Compute Module. Designing it in means a
   40-pin mezzanine plus connectors you do not want. CM4 Lite costs ~$15-20
   more on a BOM dominated by converters, 16 channels of connectors, PSU and
   enclosure. RECOMMENDATION ON RECORD: CM4 Lite unless the price point
   genuinely turns on that delta.

OPEN DECISIONS (these gate everything else, and they are PW's):
- (a) CONTROL SURFACE. "Small screen, no buttons" — touchscreen, or is the
  screen status-only with control from a phone/web app? If the phone is the
  control surface, the on-device UI becomes a few hundred lines of SDL or
  framebuffer, .NET disappears, Buildroot becomes easy and 512 MB stops
  mattering. This is the highest-leverage question in the whole concept and
  it is upstream of (b) and (c).
- (b) UI STACK. If the product stays inside the matrix ecosystem, keep
  Avalonia and use PublishAot + trimming (the cell/MxAdd/CellRebinder
  binding layer is the expensive part to replace, not the widgets). If it is
  a standalone appliance, Slint is preferred over LVGL for its declarative
  binding — but Slint is GPLv3 or paid commercial, and Qt licensing is a
  real cost at this price point. Chromium kiosk and Flutter ruled out at
  512 MB.
- (c) DISTRO. Buildroot buys boot time (~2-5 s vs 20-30 s), a read-only
  rootfs (power-fail immunity on SD — arguably the strongest argument), and
  easy PREEMPT_RT integration. It buys NOTHING for the DSP or the PCM limit,
  and it fights back hard if the product needs BlueZ + PipeWire for the
  Bluetooth path or .NET for the UI. Decide AFTER (a) and (b). A pinned
  defconfig in git would fit the defs.lock discipline and would replace the
  current hand-applied config.txt provisioning.
- (d) NUMERIC SPEC. D5 says one numeric spec across targets. An ARM engine
  should therefore arguably be Q4.28 fixed-point, not float, so
  dsp_simulate.py golden vectors stay normative across all three platforms.
  A53 does fixed-point fine. Float would be a deliberate deviation needing
  a D-number.

USB MULTITRACK RECORD/PLAY (PW asked 2026-08-23): 8 ch to removable media.
ESTIMATED, NOT MEASURED.
- Bandwidth is a non-issue: 8 ch x 48 kHz x 24 bit = 1.15 MB/s, ~2.3 MB/s
  if record and play run together, against 15-25 MB/s realistic for USB 2.0
  HS on this part. One hour of 8-track 24/48 is ~4.15 GB.
- THE RISK IS NOT BANDWIDTH, it is USB host overhead colliding with the
  real-time audio thread. The Pi's DWC2 controller does much of its work in
  software (FIQ-driven) and USB traffic causing audio dropouts is a
  well-known Pi failure mode. This lands on top of risk 1 above and is the
  thing to MEASURE early, not reason about.
- Single OTG port, no onboard hub. The stick occupies the only port, and it
  is the same port the USB 2-track audio path would want.
- USB sticks stall for hundreds of ms during wear-levelling, which is fatal
  for live recording. Mitigation is cheap: 30 s of 8-track ring buffer is
  ~35 MB, affordable even in 512 MB, behind a writer thread.
- Recommend: specify a USB SSD rather than a stick; write PER-TRACK mono
  files (518 MB/hour each, dodges the FAT32 4 GB ceiling that an
  interleaved 8-ch WAV hits at 57 minutes); consider an SD partition
  instead, which skips USB host overhead entirely at the cost of swappable
  media.
- OPEN QUESTION for PW, changes the storage spec more than the Pi choice
  does: are record and play SIMULTANEOUS, or separate modes? Multitrack
  record and virtual-soundcheck playback usually are not concurrent; only
  overdubbing needs both. Separate modes halve the load and keep the media
  in the one-direction case where cheap flash behaves best.

CHEAPEST NEXT STEP IF IT IS TAKEN FURTHER: publish a stripped Avalonia
sample with PublishAot=true for linux-arm64 and measure RSS on the bench
CM4. One afternoon, and it settles whether the existing stack fits a tight
platform or whether a second UI line is genuinely needed.

POSSIBLE REUSE, worth weighing against the third-platform cost:
tools/dsp/dsp_codegen.py already generates node code from dsp.csv and could
emit C instead of SHARC ASM; dsp_simulate.py golden vectors are normative
per D6 and would validate an ARM build too.


## HUB DISPATCH 2026-08-22 19:05Z — SPI PARAMETER LINK — the handler runs exactly ONCE per reset (RX FIFO above watermark / ROR / host ignores RDY)   [status: 🟢 done — **the link is UP on both chips and the whole diagnostic register block now reads off a running SHARC, a first for this card.** Root cause of once-per-reset: the SEC handshake is TWO-step and `_sec_isr` only did steps 1 and 4 — it never wrote `SEC_CSID0` back to acknowledge, so the SEC never arbitrated another request. One line took SEC_COUNT from 1 to 94. Proved by bisect rung 27, which polls the SAME handler and round-tripped correctly while the interrupt build was stuck at one. Three more fixed: the RFIFO came out of boot FULL (no flush bit exists — `SPI_CTL.EN` must go low, HRM 15; now measured empty, ROR/RUWM clear); the handler drained an empty FIFO and dispatched the garbage (RFE guard added); and `dsp4_diag.py` asserted GPIO7 for chip 2 where `dsp4_boot.py` has always used GPIO24 — the whole reason chip 2 read all-zero. Chip 1 and chip 2 both return MAGIC 0xD5B40001 and their own CHIP_ID. STILL OPEN, precisely characterised: a write (or DIAG_NOP) queues no answer but still clocks two words out of the 2-deep TFIFO, leaving an odd word outstanding and slipping every later echo by one — so reads are solid but write-then-read-back is not. Real fix is DSP-side: make every accepted transaction queue exactly one two-word answer. Also open: SPI2_RDY never asserts even with the RFIFO empty, so dispatch task 2 as written is not actionable — a host honouring this RDY would wait forever]

model: opus

Continue the 🟡 SPI PARAMETER LINK item above. Two root causes are fixed
(SPI2 pins never routed; IIVT never set). Remaining: ~21 host transactions →
`SEC_COUNT = 1`, `SPI_RX_COUNT = 1`, MISO a constant `0x697EBB71`;
`SPI2_STAT = 0x00144033` = RUWM still asserted after the two-word drain,
ROR + TUR + FCS set, PB_05/RDY low. Clearing `SPI2_ILAT` is in the tree and
changed nothing — keep it, do not call it a fix. Read your own notes in the
🟡 block first.

Bench: the rev-C unit, CM4 app@192.168.1.219 (`/home/app/dspboot`: dsp4_boot.py,
spiraw.py, dsp4_diag.py, dsp4_stagewatch.py), reachable now and 24/7. The rev-A
show unit (.115) is hands-off — never touch it.

TASK (hands-off desk + bench work, chase it to ground):
1. WHY does the RX FIFO stay above the watermark after a two-word drain? Check
   the 2-deep-FIFO / UWM_FULL reasoning in `spi2_init()`'s comment against the
   HRM SPI chapter (RFIFO depth, RUWM semantics, what clears RUWM). Determine
   whether ROR needs an explicit flush (RFIFO flush bit / status W1C) or an
   SPI_EN off→on before the channel resumes. Prove it with a register dump
   before/after — no inference.
2. Make the host honour RDY: pass `--rdy-gpio 8` (or add it) to spiraw.py and
   dsp4_diag.py so the master stops clocking a stalled slave. Re-measure the
   21-transaction probe with RDY honoured; record SEC/RX counts + SPI2_STAT.
3. Only then the response framing: the read path queues its answer for the
   master's NEXT transaction. Exercise it: write a parameter, read it back on
   the following transaction, prove the value round-trips on chip 1 then chip 2.
4. Record the verdict in the 🟡 block (flip to 🟢 when the link round-trips);
   if a fault is in the PCB, it is a red mod in the mods PDF — tell the hub,
   do NOT edit the PDF from this machine (its Dropbox scope is _Matrix,
   TransferOnly, _fx, config only; the hub owns the SOT markup).
5. If it cannot be closed, leave a precise state note (register dumps, what
   was tried, what is excluded) and stop.
Constraints: chips freely bootable; ALWAYS restart matrix-app + confirm the 3
MCUs verify before ending or between long gaps — never leave the unit on a
frozen splash; ~/db Dropbox; single trunk; no AI attribution; disk is now
222 GB free — do not recreate the buildroot tree.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-22 20:3xZ — 🟢 the SPI parameter link is UP on both chips

**The full diagnostic register block now reads off a running SHARC.** That
has never happened before on this card. Chip 1, production build
(`DSP4_BISECT=0`), interrupt-driven:

```
MAGIC 0xD5B40001   CHIP_ID 1 (DSPA/U6)   BOOT_STAGE 5 (waiting for host
config)   TICKS 74671   SEC_COUNT 38   LAST_CSID 71 (SPI2_STAT)
SPI_RX_COUNT 48   SPI_ERR_COUNT 0   UNK_COUNT 0   RESP_DROP 0
SPI_STAT 0x00540001   BUILD_ID 0x20260812
```

Chip 2 answers too: MAGIC `0xD5B40001`, **CHIP_ID 2**, BUILD_ID
`0x20260812`.

#### ROOT CAUSE of "the handler runs exactly ONCE" — the SEC handshake is two-step

`_sec_isr` read `SEC_CSID0` and wrote `SEC_END`, but never did the step in
between. HRM ch.6, *Core/SEC Handshake Requirements*, is explicit:

1. read `SEC_CSID[n]` for the source id
2. **write that value BACK to `SEC_CSID[n]`** — the acknowledge that tells
   the SEC the core has accepted the request
3. run the handler
4. write the same id to `SEC_END`

Without step 2, *"the SEC knows what it passed to the core because of the
write to the SEC_CSID[n] register"* never happens, so it never arbitrates
another request. **One SECI per reset, exactly as observed.** One line in
`sport_init.asm` took SEC_COUNT from **1 to 94** over the same probe.

What proved it was delivery rather than the SPI block: bisect rung 27
polls `SPI_STAT.RFE` in the main loop and calls the SAME handler. Polled,
the link round-tripped MAGIC, CHIP_ID and BUILD_ID perfectly while the
interrupt-driven build was still stuck at one. Handler good, SPI good,
delivery broken.

#### Three more faults fixed on the way

**The RFIFO came out of boot already full.** There is no flush bit on this
part — *"the receive FIFO is reset (cleared) when the SPI is disabled after
being enabled"* (HRM 15) — and the boot kernel hands over with SPI2 still
enabled. `spi2_init()` now takes `SPI_CTL.EN` low before configuring.
Measured before/after on a fresh boot with no host traffic at all:

| | before | after |
|---|---|---|
| `SPI2_STAT` | `0x00144033` | `0x00540020` |
| RFIFO level | **FULL** | **empty** (RFE=1) |
| ROR / RUWM | set / set | **clear / clear** |

**The handler drained an empty FIFO.** The SEC can deliver more events
than there are transactions — 94 handler entries against 48 words actually
clocked in. Reading `SPI_RFIFO` empty returns garbage, and that garbage
was then dispatched as a request, which is why the host saw one constant
meaningless answer. Both `spi_handler.asm` variants now check
`SPI_STAT.RFE` before draining, the same check the polled variant used.

**`dsp4_diag.py` asserted the wrong chip select for chip 2.** It defaulted
to GPIO7; `dsp4_boot.py` has always had the right map (`CS_GPIO = {1: 6,
2: 24}`). That is the whole of why chip 2 answered all-zero on MISO while
chip 1 worked — the tool was selecting something DSPB does not listen on.
Fixed in `dsp4_diag.py`.

#### The transmit path was never broken

Priming `SPI_TFIFO` with `0xA5A5A5A5` made MISO return `0xA5A5A5A5` for
every transaction, which identifies the old constant `0x697EBB71` as
nothing more than an unloaded shift register. The priming was removed
again once it had answered the question — it puts every response one
transaction out of step.

#### STILL OPEN — a write between reads slips the word phase

Reads pipeline correctly: each transaction carries the previous request's
echo and value, exactly as `diag.asm` describes. But a transaction that
produces NO response — a register write, or `DIAG_NOP` — still clocks two
words out of the 2-deep `SPI_TFIFO`, leaving an ODD number of words
outstanding. Every later echo then lands where a value should be, and it
does not self-correct: re-asking consumes two more words and preserves the
bad phase. A one-word (4-byte) transfer would re-align it.

So `dsp4_diag.py` reads a whole register block cleanly, but the
write-then-read-back round-trip (`--led`, and hence `dsp4_config.py`'s
CONFIG_COMMIT path) is not yet reliable.

**The real fix is DSP-side and small: make every accepted transaction
queue exactly one two-word answer** — a write echoing its request word
with value 0 — so the stream is aligned by construction instead of by
convention. It touches both `spi_handler.asm` variants and the protocol
note in `diag.asm`, and it shifts what `dsp4_config.py` sees, so it wants
doing deliberately rather than at the end of a long session. A bounded
re-ask is in `dsp4_diag.py` now as a WORKAROUND and is commented as one.

#### Loose ends worth knowing

- **`SPI2_RDY` never asserts.** On a fresh boot with the RFIFO verifiably
  EMPTY (RFE=1, ROR=0, RUWM=0) the part still has `FCS` set and drives
  PB_05 low. With FCPL=1 (active-high per HRM Table 15-18) and FCWM=1
  (RFIFO ≥ 75% full), an empty FIFO should read READY. It does not, and
  the RX-channel flow-control rule alone does not explain it. The link
  works anyway because the host never waits on RDY. Task 2 of the dispatch
  — "make the host honour RDY" — is therefore NOT actionable as written:
  a host that honoured this RDY would wait forever. Left open.
- `SPI_STAT` sticky bits after a good session are TUR and FCS only. TUR is
  expected: TEN is set and the TFIFO is empty between responses.
- FRAME_COUNT is 0 and DMA0_STAT reads `0x00006032` — no audio block has
  arrived, which is expected while the LOGIC CPLD is not sourcing frame
  syncs. Not a link fault.

**Bench state:** both chips hold the production `c1_p8`/`c2_p8` images
(all fixes, `DSP4_BISECT=0`); `matrix-app` restarted and active; all three
MCUs verified 20:34-20:35; GPIO 6/7/8/9/10/11/12/24 returned to `a0`.

## SPI PARAMETER LINK 2026-08-22 — 🟡 two more root causes fixed, one still open

Follow-on from the P2.2 close below, working the one thing that blocked
everything downstream. Two more faults of the same family as D15 —
things `___lib_setup_c` does that this firmware never did, and things
configured but never connected.

### FIXED 1 — the SPI2 pins were never routed to the pads

New instrument, `DSP4_BISECT=22`: read SPI2_CTL/RXCTL/TXCTL/STAT and the
PORTA/PORTB FER and MUX registers off the running part and frame them
onto PB_05 in clkprobe's encoding, so the question can be answered
without the link that is broken. Registers are snapshotted BEFORE the
pin is taken, because taking it clears PORTB_FER — one of the values in
question.

| register | before | after |
|---|---|---|
| `SPI2_CTL` | `0x0001A501` | unchanged |
| `PORTA_FER` | **`0x00000000`** | `0x00000033` |
| `PORTB_FER` | **`0x00000000`** | `0x00000020` |
| `PORTB_MUX` | **`0x00000000`** | `0x00000400` |

`spi2_init()`'s writes had ALWAYS taken — CTL decodes as EN, EMISO,
SIZE32, FCEN, FCPL, FCWM, MSTR=0, exactly as written. The block was
correctly configured **and wired to nothing**. Nothing in this firmware
had ever set a FER or MUX bit; the only port writes it made were to
CLEAR FER, for the LED and the RDY mirror.

Pin assignment now in `spi2_init()`, from the data sheet Rev. A Tables
10/11 — **the GPIO multiplexing table earlier notes recorded as missing;
it is in the datasheet already in Dropbox**: PA_00 SPI2_MISO, PA_01
SPI2_MOSI, PA_04 SPI2_CLK, PA_05 SPI2_SEL1 (with SPI2_SS on the input
tap, which is the host's CS), all mux function 0; PB_05 SPI2_RDY, mux
function **1**. Port A's mux is already 0 at reset so only FER is set
there; port B's MUX5 is read-modify-written so other pins keep theirs.

**Effect: the part now drives MISO.** Every readback was `0x00000000`
before; it is real data after.

### FIXED 2 — CMMR_SYSCTL.IIVT was never set, so no interrupt could be taken

Found by bisecting the interrupt path with three new rungs. Rung 25
(mask everything) was the control that proved the dump instrument
works — it reported `IRPTL = 0x00408820`, i.e. TMZLI, TMZHI, SECI and
CB7I all LATCHED, with `DIAG_TICKS = 0`. Rung 24 (only the core timer
unmasked) went dead. **Rung 26 — the same thing with an RTI-only TMZLI
vector — also went dead**, which is what says the fault was in TAKING
the interrupt, not in any handler.

`CMMR_SYSCTL.IIVT` selects the INTERNAL interrupt vector table, the one
`src/ivt.asm` assembles at 0x00090000. Reset entry does not need it,
because the boot kernel jumps straight to the entry address rather than
vectoring — so everything looks healthy right up until the first
interrupt is taken. `___lib_setup_c` sets it for every SHARC+ part; this
firmware does not link it. It is now in `C_RUNTIME_INIT` (`src/c_abi.h`)
with the rest of that family.

**Effect, measured: `DIAG_TICKS = 0x3213` — 12819 ticks over a 12 s
window at the 1 ms tick.** The core-timer ISR had never run before
today. The LED fault codes work for the first time as a consequence.

With SECI unmasked as well: `SEC_COUNT = 1`, `SPI_RX_COUNT = 1`, and
`SEC0_SCTL71 = 0x5` (IEN bit 0, SEN bit 2 — both set, so the SPI2_STAT
route is correct). The SEC ISR runs, demuxes, and the SPI handler runs.
**The whole chain SEC route -> SEC ISR -> SPI handler is proved.**

### STILL OPEN — the handler runs exactly ONCE per reset

~21 host transactions produce `SEC_COUNT = 1`, `SPI_RX_COUNT = 1`, and
MISO stuck on a constant `0x697EBB71` — the same word for every input,
at every clock, in either SPI mode, which is a TX FIFO nobody reloads.
`SPI2_STAT = 0x00144033` decodes as **RUWM still asserted after the
handler drained two words, ROR (receive overrun) set, TUR set, and FCS
(flow-control stall) set** — and PB_05/RDY reads low, i.e. the part is
telling the host to stop, which `spiraw.py` and `dsp4_diag.py` both
ignore because neither passes `--rdy-gpio`.

Clearing `SPI2_ILAT` in the handler was the obvious candidate and is now
in the tree (ADI's own drivers do it), but **it changed nothing** — the
measurement after it is bit-identical. It is kept as correct-but-not-
the-cause, and the comment in `spi_handler.asm` says so. Do not read it
as a fix.

**Next, in order.** (1) Why does the RX FIFO stay above the watermark
after a two-word drain — is the 2-deep-FIFO/UWM_FULL reasoning in
`spi2_init()`'s comment right, and does ROR need an explicit flush, or
an EN off/on, before the channel resumes? (2) Have the host honour RDY
(`--rdy-gpio 8`) so it stops overrunning a stalled slave; that may be
half the picture. (3) Only then the response framing — the read path
queues its answer for the master's NEXT transaction, and none of that
has been exercised yet.

### Also fixed on the way

- `dsp4_config.py` requested the RDY line even when none was asked for,
  passing `None` to gpiod — which is why `dsp4_diag.py` crashed on
  start. It runs now.
- `dsp4_clkprobe.py` gained `--frame spi2` / `--frame secspi` decoders, a
  pulse-burst counter, and MAGIC alignment for every framed image (a
  capture may start mid-transcript). Two bit tables in it were written
  from memory and were WRONG — SPI_CTL's EMISO/FCEN/FCPL positions, and
  SEC_SCTL's SEN/IEN — both corrected against `sys/ADSP-21564.h`.

**Bench state:** production images built with all of the above; chip 1
holds the rung-23 diagnostic image from the last measurement.

## HUB DISPATCH 2026-08-21 20:34Z — P2.2 cont'd — _sru_init hang + the ~190 vs 400 MHz CCLK suspect (nail the clock, get past SRU, reach dma_cfg_init)   [status: 🟢 done — **P2.2's wedge is closed: both chips now run the ENTIRE init sequence** — SRU, SPORTs, DMA rings, SEC, SPI2 — and park at the host handshake (bisect rung 21, chip 1 and chip 2). CCLK is **491.52 MHz**, measured off the core timer and confirmed against the CGU registers read out of the running part; the "~190 MHz" figure is RETRACTED (it divided by an assumed 5 cycles per delay-loop iteration; the real cost is 13). The CGU is left at its reset defaults by decision — they already give a fully in-spec tree from 24.576 MHz — and the firmware's own constants are corrected instead. `_sru_init` was never a clock or a peripheral fault: **main.asm was calling C with the wrong ABI**, and the four assembly helpers C calls returned with `rts`. Two real bugs fixed: the cc21k call convention (new `src/c_abi.h`, decision D15) and **IMASK/IRPTL never cleared after boot**, which killed the core as soon as eleven DMA channels were armed with the boot kernel's interrupts still live. `dma_cfg_init`, `sport_dma_base()` and `l1_to_sys()` all now have their hardware test and all pass. STILL OPEN, and it is a different subsystem: the SPI parameter link answers all-zero, so nothing downstream of the handshake is proven — that is the next item]   [model: opus]

model: opus

BIG progress: the >8KB boot-stream limit is resolved and chip 1's FULL
firmware now executes (dsp 9100107 — the boot bus has one master again).
P2.2 is NOT closed: the firmware now hangs in `_sru_init`'s DAI0 half on the
first SRU register writes; dma_cfg_init + the sport_dma_base() fix remain
untested downstream. Standing prime suspect: **CCLK is ~190 MHz but the
firmware assumes 400 MHz** (SRU/DAI timing, waits). Read your own last
session's notes + the commits first.

TASK (overnight desk work — chase it to ground, hands-off):
1. NAIL the actual CCLK. Compute it from the fitted clock chain: SYS_CLKIN0
   = 24.576 MHz (the ÷2 CPLD + level-shift bodge) → CGU reset defaults
   (MSEL/DF/CSEL from the HRM) → CCLK. If that yields ~190 MHz, the firmware
   MUST configure the CGU (or its assumptions) for the real clock. Confirm
   against a measurable (LD3/CCLK cadence via stagewatch, or a known-rate
   blink) rather than assuming.
2. If CCLK ≠ 400 MHz: either (a) program the CGU in firmware early-init to
   reach the intended CCLK from 24.576 MHz CLKIN, or (b) correct the
   firmware's clock assumptions (SRU/DAI wait counts, any 400 MHz constants).
   Decide which is right (design note in dsp4-architecture-decisions.md).
3. Get past `_sru_init`: with the clock correct, does DAI0 SRU init complete?
   Walk forward (your DSP4_BISECT / stagewatch instruments) to dma_cfg_init;
   the sport_dma_base()/l1_to_sys() fixes finally get their hardware test.
4. Iterate to a full chip-1 run, then chip 2. Record the verdict; when
   closed, revert temp instrumentation + rebuild clean production images.
5. If it can't be closed tonight, leave a precise state note (where it hangs,
   the measured CCLK, what you tried) for the morning.
Constraints: chips freely bootable; ALWAYS restart matrix-app + confirm the
3 MCUs verify before ending or between long gaps — never leave the unit on a
frozen splash; ~/db Dropbox; single trunk; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 22:4xZ — 🟢 the init sequence runs end to end on both chips

**Headline: `_sru_init` was a C-calling-convention bug, not a clock and
not a peripheral.** Every register write in it always completed. What it
could not do was return.

#### 1. CCLK is 491.52 MHz. Measured, not inferred.

New instrument, `src/blink/clkprobe.asm` + `tools/pi/dsp4_clkprobe.py`:
a standalone image that times everything off the SHARC **core timer**,
which decrements once per core-clock cycle by construction, and frames
the result onto PB_05 as pulse-width-coded words. Two independent
readings in one transcript — the tick unit and a 32-tick square — both
gave **491.52 MHz** to five figures. The same image reads the CGU back
out of the running part:

| register | value | fields |
|---|---|---|
| `CGU0_CTL`   | `0x00002800` | DF=0, MSEL=40 |
| `CGU0_DIV`   | `0x05144281` | CSEL=1, SYSSEL=2, S0SEL=4, S1SEL=2 |
| `CGU0_STAT`  | `0x00000005` | |
| `CGU0_DIVEX` | `0x00200030` | |

Those are the reset defaults, and with SYS_CLKIN0 = 24.576 MHz and the
2156x PLL's built-in /2 they give PLLCLK/CCLK 491.52, SYSCLK 245.76,
SCLK0 61.44, SCLK1 122.88 MHz — all inside the datasheet ranges, and
fCCLK = 2 × fSYSCLK as required. **This is exactly what D10 predicted.**

**DECISION (dispatch item 2): do NOT program the CGU; correct the
firmware's assumptions.** The defaults are already in spec and
audio-rational, so a CGU write in early init buys nothing and costs a
PLL relock during boot on the shared SPI port. Written up as the D10
addendum in `dsp4-architecture-decisions.md`. `DIAG_TPERIOD` is now
491520 (a 1.000 ms tick) and the blink images carry
`CCLK_HZ = 491520000`.

**RETRACTED: "~190 MHz".** It came from the blink rate divided by an
*assumed* 5 cycles per iteration of a two-instruction delay loop. The
real figure is **13 cycles** (measured: the park's 15,000,000-iteration
half period is 397 ms at 491.52 MHz), and 13/5 × 400/491.52 = 2.12 —
the whole of the "2.1x slow" observation. Nothing was wrong with the
clock. Every 400 MHz and 190 MHz constant and comment in the tree is
now corrected or deleted.

#### 2. The SRU register space was innocent — proved before touching it

`src/blink/sruprobe.asm` performs the DAI0 half of `sru_init()`
write-for-write in a standalone image with no C, no stack and no
interrupts, pulsing PB_05 after each one. **All 36 writes complete**,
repeatedly, and the routing reads back changed (`DAI0_DAT0` 0x08144040
at reset → 0x02144040 after; `DAI0_CLK0` 0x24992649; `DAI0_PIN0`
0x03480B14). So "the DAI0 block is unclocked / not answering the bus"
is dead as a theory, and so is the CCLK suspicion behind it.

#### 3. ROOT CAUSE — the cc21k C ABI was never being met

`cc21k` returns from a C function with `jump (m14,i12) (db); rframe;`
after fetching the return address with `i12 = dm(m7,i6)`, and callers
must use `cjump fn (db); dm(i7,m7)=r2; dm(i7,m7)=pc;`. `main.asm` used a
plain `call` and set up the stack **B/I/L registers but not one M
register** — with M7 and M14 left at whatever the boot kernel had put
there, the frame push and the return both went somewhere arbitrary.
The same mismatch ran the other way for the four assembly helpers C
calls (`_diag_stage_set`, `_diag_irq_off`, `_set_rx_bufs`,
`_set_tx_bufs`), which all returned with `rts`.

Fixed by a new `src/c_abi.h` — `C_RUNTIME_INIT`, `CCALL()`, `C_RETURN`,
copied from what the compiler emits and from CCES's own
`SHARC/lib/src/libc_src/set_c.asm`, with every deliberate divergence
from `___lib_setup_c` documented in the file (L6/L7 linear; NESTM NOT
set, because `diag.asm` and `_sec_isr` require non-nesting interrupts;
MMASK and IRPTEN left to their owners). Recorded as **decision D15**.

**Result on hardware: bisect rung 8 (park after `_sru_init` returns)
went from 0/6 silent to firing 6/6.**

#### 4. SECOND BUG — IMASK and IRPTL are never cleared after boot

Found by bisecting inside `dma_cfg_init` once it became reachable. Rung
16 (a pulse per lane, no park) showed **all 8 region-A lanes and all 3
region-B lanes arming and both `arm_region()` calls returning** — while
rung 1, whose park is two statements later, stayed silent. Rung 17 (rung
1 with interrupts turned off *before* arming instead of after) fired.
So the variable was the live interrupt, not the DMA.

The SPI target boot kernel hands over with its own interrupts still
unmasked and latched; `_diag_init` only ORs TMZLI in, so those survive
and fire into an IVT with no handler the moment IRPTEN goes on. Adding
`imask = 0; irptl = 0;` to `_start` (what `___lib_setup_c` does, and for
this exact reason) made rung 1 fire immediately. Also in D15.

#### 5. Where the firmware is now — all of it runs

Bisect ladder on chip 1, six boots' worth of sampling per rung, read
over ssh with `dsp4_stagewatch.py`:

| rung | park point | before | after |
|---|---|---|---|
| 8 | after `_sru_init` | **0/6 silent** | fires |
| 9 | after `_sport_cfg_init` | 0/6 silent | fires |
| 4 | entry to `dma_cfg_init` | 0/6 silent | fires |
| 13/14/15 | first lane: before DSCPTR / before CFG / after CFG | — | all fire |
| 16 | a mark per lane (does not stop) | — | 8 + 3 lanes, both regions |
| 1 | after `arm_region(A)` | silent | fires (needed the IMASK clear) |
| 2 | after `arm_region(B)` | silent | fires |
| 20 | after `enable_region` = end of `dma_cfg_init` | — | **fires** |
| 21 | main.asm, at the `.wait_boot` host handshake | — | **fires on chip 1 AND chip 2** |

**`dma_cfg_init` is closed.** The `sport_dma_base()` SPORT4-7 DMA-base
fix and `l1_to_sys()` finally have their hardware test and both pass:
every lane arms, including the four on the second DMA MMR bank, and the
core survives every descriptor fetch. `l1_to_sys()`'s +0x28000000 is
confirmed against the datasheet (Rev. A Table 4: L1 block 0 private
0x00240000–0x0026FFFF ↔ completer-port 0x28240000–0x2826FFFF, and the
same offset for blocks 1-3).

#### 6. WHAT IS STILL OPEN — and it is a different subsystem

The **SPI parameter link answers all-zero**. `dsp4_diag.py` now runs
(it was crashing before — `dsp4_config.py` requested the RDY line even
when none was given, passing `None` to gpiod; fixed), but a read of
`DIAG_MAGIC` comes back `0x00000000` with the response out of step. So:
the core reaches the handshake, and nothing past it is proven — no
register in `diagnostics.md` has been read off a running part. That is
the next item, and it is the SPI2 slave protocol (watermark, RDY
polarity/timing, response framing), not `dma_cfg_init`.

Because of that the DSP4_BISECT scaffolding **stays** for now, and
build.sh's default is still 1 — but the comment beside it has been
corrected: a plain rebuild now produces an image that parks after
`arm_region(A)` on purpose, because a build that runs on into the
unproven SPI link cannot be read on this bench. `DSP4_BISECT=0` gives a
production image, `21` proves the init sequence.

#### Instruments added (they earn their keep, keep them)

- `src/blink/clkprobe.asm` — CCLK and any MMR, read out over PB_05,
  timed off the core timer. This is how a clock gets measured on a part
  with no emulator; do not infer one from a blink rate again.
- `src/blink/sruprobe.asm` — the DAI0 SRU sequence standalone, one
  pulse per write.
- `tools/pi/dsp4_clkprobe.py` — decoder for both, with `--rle` and a
  pulse-burst counter.
- `DSP4_BISECT` rungs 11 (mirror, no park), 13-15 (inside the first
  lane), 16 (a mark per lane, does not stop), 17 (the interrupt
  control), 18-20 (the tail of `dma_cfg_init`), 21 (the handshake).

**Bench state at hand-off:** `matrix-app` restarted and active, all
three MCUs verified 22:39-22:40 (H1S1, H1S3, H1S4 — "MCU verified" and
"MCU boot verified"), GPIO 8/9/10/11/12 back to `a0`. Both SHARCs hold
the rung-21 image and are parked at the handshake, blinking 3 long
pulses on their RDY line.

## HUB DISPATCH 2026-08-21 14:37Z — P2.2 cont'd — characterise the >8KB boot-stream limit so the full 208KB image runs, then dma_cfg_init   [status: 🟢 done — **BOTH SHARCs now load and execute their full firmware, deterministically.** The ">8 KB block-size limit" never existed and is retired. Two real faults, both fixed: (1) elfloader's ZERO-FILL blocks desynchronise the boot kernel — fixed with `-NoFillBlock` plus a build-time guard; (2) U7/H1S1 was a second master on the boot bus — the two offending call sites were removed from its firmware and it was reflashed through MH1, after which the bus measures ZERO events in 15 s and chip 1's 258 KB image boots 6/6 unsynced at 10 MHz and 2/2 at 1 MHz on a 3.45 s stream. The stream-length budget is gone. **P2.2 itself is NOT closed**: with the image finally running, the firmware hangs in `_sru_init`'s DAI0 half — the very first SRU register writes — so `dma_cfg_init` and the `sport_dma_base()` fix are still untested. That is a new, separate item]   [model: opus]

model: opus

rev C is FREE again (the app/panel work is deferred — blocked on the matrix
drift, not the unit). Resume P2.2 from where the 09:xx session left it
(commit 0ce2b7e, "P2.2 reframed"). Read that commit + the 13:09Z block first.

STATE: the SPICMD fix boots ~1 KB images (blink/rdyprobe/bulkprobe) but the
full 208 KB firmware has NEVER executed an instruction — a park on the first
instruction of _start stayed silent. You bisected a boot-stream BLOCK-SIZE
limit: 180 B boots 10/10, 8364 B fails 0/10, and -MaxBlockSize 0x1000 (now in
build.sh LDRFLAGS) boots the 8 KB ladder 4/4. But a SECOND limit above ~8 KB
is still uncharacterised — the 208 KB image still does not run. dma_cfg_init
is downstream and untestable until the full image boots.

TASK — get the full firmware to execute, then close P2.2.
1. Characterise the second limit. Extend the bulkprobe size ladder (build.sh
   bulkprobe) above 8 KB — 16/32/64/128/208 KB — with -MaxBlockSize 0x1000
   already set; find where it stops booting. Use dsp4_stagewatch.py (no bench
   eyes). Hypotheses to test: total stream size vs a per-section/DMA-count
   limit; a boot-kernel scratch/heap ceiling; a second block-count or address
   window; whether multiple blocks vs one big section behaves differently.
   HRM ch.36/40 for any documented SPI-target-boot size/scratch limits.
2. Once the full image boots (park on _start's first instruction fires), move
   the park forward: does dma_cfg_init now run? Then the sport_dma_base() /
   l1_to_sys() fixes finally get a real hardware test. Use DSP4_BISECT to
   walk arm_region(A)/(B) → full run.
3. When the 208 KB production image runs on both chips: revert temp
   instrumentation, rebuild clean production .ldr (fix ldr/manifest.txt which
   currently records the two artifacts as NOT bootable), reflash, verify LD3/
   LD2 + a sane SPI readback. Update P2.2 → 🟢 with the size-limit root cause.
4. If the full image cannot be made to boot as one stream: characterise the
   hard limit and propose the workaround (multi-DXE boot, second-stage loader,
   or a smaller image), with evidence — do not leave it guessing.
Constraints: rev C is yours (app work deferred); ALWAYS restart matrix-app +
verify 3 MCUs before ending; ~/db Dropbox; single trunk; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 17:2xZ — the boot-stream limit is characterised; it was never a size limit

**Headline: chip 2's full firmware executes.** A `DSP4_BISECT=5` build —
the park on the FIRST INSTRUCTION of `_start` — fired 5/6 at the bench.
Every previous session's premise ("the full image never runs") is now
resolved for chip 2, and the reason it never ran is understood.

**What the previous session's finding actually was.** `-MaxBlockSize
0x1000` does nothing. A/B of the identical DXE, capped vs uncapped, 8
boots each at 4 MHz: **7/8 vs 6/8**. The earlier "0/10 then 4/4" was a
~50% coin flip read as a signal. The flag is REMOVED from build.sh and
the claim retracted in `ldr/manifest.txt`.

**FAULT 1 — zero-fill blocks (this is what kept the firmware from ever
running).** elfloader compresses zero runs into ZERO-FILL blocks: a
header with a byte count and no payload. The SPI target boot kernel does
not survive one. A fill block followed by ANY further block loses the
kernel its place in the stream; a fill that happens to be last is
harmless, which is why nothing ever noticed.

| test (chip 2, gap-synced 11 MHz) | result |
|---|---|
| image that boots, one 640 B fill inserted at the FRONT | 3/3 → **0/3** |
| identical block APPENDED instead | 3/3 → **3/3** |
| chip2 firmware as elfloader emits it (324 blocks, 152 fills) | **0/6** |
| same firmware, `-NoFillBlock` (6 blocks, no fills) | **5/6** |

Found by grafting the firmware's first N blocks in front of a tiny probe
that toggles PB_05, so a boot proves the kernel consumed them: N=0 boots
3/3, N=1 (a single leading fill) **0/3**.

FIX IN TREE: `-NoFillBlock` in `build.sh` LDRFLAGS, and
`tools/dsp/ldr_stream.py check` runs on every image the build produces,
so the shape cannot come back silently. Because the zeros now travel for
real, `sec_delay`/`sec_delay_ovf` are marked `NO_INIT` in the LDF —
without that chip 2 would be a 1.9 MB stream. **Those delay buffers must
now be cleared by firmware at startup; that is a new NOW item below.**

**FAULT 2 — the boot bus's second master sets a TIME budget.** U7/H1S1's
legacy ADAU meter poll bursts ~0.5 ms on the shared SCK/MOSI every
~185–254 ms (63 bursts in 11.67 s, measured). Boot success tracks stream
ELAPSED TIME, not size and not block size — the cleanest proof is one
unchanged 3 KB image at three clocks: **5/6 at 1 MHz (25 ms), 5/6 at
4 MHz, 0/6 at 100 kHz (246 ms)**. Faster is safer; 10 and 11 MHz boot
cleanly, **12 MHz and above fail outright**. `dsp4_boot.py --sync-poll`
(new) starts the stream just after a burst. Budget with it: ~220 ms
≈ 240 KB at 11 MHz — a 107 KB probe boots 6/6, 176 KB 5/6, 197 KB 0/6.

**Chip 1 — FIXED the same day; see the addendum below.** 258 KB, ~320 ms
on the wire. It did not fit between two bursts at any clock, so no
host-side trick reached it. **CORRECTED 2026-08-21: it is not an "ADAU
meter poll" and it is NOT absent from the current sources** — `main.c`
line 24 `#include "matrix.cs"`, so that file is compiled. The two
interferers are `TimeSplice()`'s periodic `TestMicPres()` (25 bytes on
the mic-preamp CS, fired off a MainLoop ITERATION COUNTER, which is why
the period wanders 40–254 ms) and `MainLoop()`'s `DspTx(0xF520)` writes
to **CS1–CS8** on every blink transition — the latter asserting the very
chip selects the Pi boots through, for a legacy register the SHARC
firmware does not implement. Both are removable in a few lines;
`TestMicPres()` is also called once at init, so mic gain survives.
**NOT DONE, it needs PW's go-ahead** (and the 13:09Z
dispatch fenced the ADAU-poll item off).

**item 2 — the wedge is in `_sru_init`, NOT `dma_cfg_init`.** Redone on
clean `-NoFillBlock` chip-2 builds (the first pass used a fill-STRIPPED
diagnostic image with uninitialised BSS and reported `_diag_init`; that
reading is WITHDRAWN). Park rungs added to `main.asm` at each step of
`_start`'s init sequence, 6 boots each, read over ssh on PB_05:

| rung | park point | result |
|---|---|---|
| 6 | after the C stack prologue | **6/6 fires** |
| 7 | after `_diag_init` returns | **5/6 fires** |
| 8 | after `_sru_init` returns | **0/6 silent** |
| 9 | after `_sport_cfg_init` returns | 0/6 silent |
| 4 | entry to `dma_cfg_init` | 0/6 silent |

`_sru_init` never returns. Split further with rung 10 (an early `return`
in `sru_config.c` at the DAI0/DAI1 boundary): also **0/6**, so the hang
is in the **DAI0 half — the very first SRU register writes**, not the
DAI1/SPORT4-7 ones.

`sru_init()` is straight-line `SRU()` macro register writes with no loop
in it, so "never returns" is a FAULT, not a spin — the core vectors
somewhere and stays there. The obvious suspect is the DAI/SRU register
space not being reachable yet (clock/power gating, or a CGU that is not
where the code assumes). Note the independent evidence: **CCLK on this
card measures ~190 MHz, not the 400 MHz every delay constant assumes**
(diag.h), and the standalone blink images run ~2x slow — PW confirmed
both LEDs blinking at the slow rate 2026-08-21. Next session: read the
fault status registers at the park, and confirm DAI0 is clocked before
`sru_init` touches it. **`dma_cfg_init` and the `sport_dma_base()` fix
remain untested on hardware — they are three calls downstream of a
function that never returns.**

**Also worth knowing (cost me an hour).** Claiming GPIO9/10/11 with
gpiod/`gpiomon` takes them out of `a0` and **spidev does not put them
back** — every boot then fails and looks exactly like a dead part.
`pinctrl set 9,10,11 a0` restores it; `--sync-poll` does it automatically.
Separately, stopping `matrix-app` makes DSP boot fail outright (0/6 where
it was 5/6) — not chased, but do not debug boot with the app stopped.

**Bench state at hand-off:** `matrix-app` restarted and active, all three
MCUs verified 17:16–17:17 (H1S1, H1S3, H1S4 — "MCU verified" and "MCU
boot verified"), GPIO9/10/11 back to `a0`, spidev bufsiz back to its
4096 default. Chip 2 holds a production `chip2.ldr` from the last boot
attempt; chip 1 holds nothing running.

**NEXT, in order.** (1) H1S1 reflash — DONE, see the addendum.
(2) Zero `sec_delay`/`sec_delay_ovf` in firmware startup (new NOW item).
(3) Chase the `_sru_init` fault: read the fault status registers at the
park, and check DAI0 is clocked/ungated before `sru_init` writes to it —
CCLK measuring ~190 MHz against code assuming 400 MHz says the clock tree
is not where this firmware thinks it is.
(4) Production verification of chip 2 needs eyes on LD2, or a working
`dsp4_diag.py` — it crashes on start (`TypeError` in the gpiod line
request), unrelated to any of this.

### Addendum 2026-08-21 20:2xZ — H1S1 reflashed; the boot bus has one master again

PW authorised the change. Both interfering call sites removed from
`~/build-h1s1/Core/Inc/matrix.cs`:

* `TestMicPres()` dropped from `TimeSplice()`'s periodic path. It pushed
  25 bytes at CS_M every ~1e6 MainLoop iterations. It is STILL called
  once at init, so mic gain is still applied — only the pointless
  re-application every million loops is gone.
* the CS1–CS8 `DspTx(0xF520)` block deleted from `MainLoop()`. Those
  asserted the SHARCs' own boot chip selects, for a legacy ADAU-era
  register the SHARC firmware does not implement.

Built with `Debug/fw.sh` (text 34036 -> 33476 B). **Verified in the
disassembly, not from the source edit:** zero callers of `DspTx`,
exactly one caller of `TestMicPres` (the init one), and `TimeSplice`
contains no `bl` instruction at all. Packed with `hex2shex.py`
(2171 -> 2136 records, 34693 -> 34133 B) and flashed through MH1 with
`app cli loadfw H1S1` — the same path H1S3/H1S4 use, per PW. Previous
pack image kept at
`/home/app/fwbuild/pack-backup-H1S1-2026-08-21-preSPIfix.shex`.
All three MCUs verify after the reflash (20:24).

**Result, measured both ways:**

| | before | after |
|---|---|---|
| SCK/MOSI/MISO activity, gpiomon | 8530 events, 63 bursts / 11.67 s | **0 events / 15 s** |
| chip 1 full firmware, 258 KB @ 10 MHz, unsynced | 0/6 | **6/6** (350 ms) |
| chip 1 @ 1 MHz — a 3.45 SECOND stream | hopeless | **2/2** |
| chip 2 full firmware @ 10 MHz | needed --sync-poll | **3/3** |

There is no longer a stream-length budget on this unit, at any clock.
`--sync-poll` and the 11 MHz ceiling stay in `dsp4_boot.py` because the
two-master WIRING is still a rev-D item — any board whose H1S1 has not
been reflashed has the limit straight back.

**Canonical source updated too.** `~/build-h1s1` is not a git repo, so
the edit would have lived on one workstation only and the next rebuild
from the canonical tree would have silently reintroduced the fault. The
Dropbox copy at `_mx/MW/D24/FW/H1S1/Core/Inc/matrix.cs` was verified
byte-identical to the pre-edit original first, then updated, with the
original kept beside it as `matrix.cs.pre-spi-fix-2026-08-21`. Source and
flashed image now agree.

**Incidental observation, not touched:** `/home/app/firmware/H1S3.shex`
carries the MCU-ID `H1S4` in its type-04 record (and fwbuild holds
`left-slot3-H1S4content.shex` / `right-slot4-H1S3content.shex`), so the
slot/content mapping looks deliberately crossed. All three MCUs verify,
so this is either intended or long-standing. Flagged for PW, not changed.

## HUB DISPATCH 2026-08-21 13:09Z — P2.2 — close the dma_cfg_init wedge with working boot + LD blink instrument   [status: 🔴 blocked — the wedge is NOT in dma_cfg_init: the full firmware has never executed a single instruction on this card. Root cause found and half-fixed — the SPI target boot kernel cannot take a loader block larger than ~8 KB, so every production image built without `-MaxBlockSize` is a stream the host clocks out in full and the part never runs. `-MaxBlockSize 0x1000` added to build.sh's LDRFLAGS and proved on the bench (0/10 → 4/4 on the same DXE at 8 KB), but the 208 KB firmware still does not run, so a SECOND limit above ~8 KB remains uncharacterised. Bench released to PW mid-bisect for an app/panel reflash]   [model: opus]

model: opus

SHARC boot is SOLVED (SPICMD, D14) and BOTH DSP blink LEDs are confirmed
running at the bench — you now have a working boot AND LD2/LD3 as live
instruments, which is exactly what the P2.2 bisect was blocked on. Resume
P2.2 per NOW item 1.

TASK — close the dma_cfg_init wedge.
1. The SPORT4-7 DMA-base fix (`sport_dma_base()` in dma_config.c) is in the
   tree, verified against sys/ADSP-21564.h, never confirmed on hardware
   because nothing booted before. Now it can be. Build `DSP4_BISECT=1`
   (parks after arm_region(A)); boot chip 1 with the SPICMD fix
   (dsp4_boot.py default 0x03); read LD3 (DSPA, chip 1): a steady ~1 Hz
   square = arm_region(A) survived. If it parks (slow single blink), the
   SPORT4 base was still not it — capture and reassess.
2. If A is clean: `DSP4_BISECT=2` (park after B), boot, LD3 again. Then
   `DSP4_BISECT=0` (production, no park/stamps) for a full run on BOTH
   chips; confirm LD3 (1 Hz) and LD2 (2 Hz) steady, and the SPI2 diag
   readback is non-zero / sane now that the core runs past dma_cfg_init.
3. When closed: REVERT the temp instrumentation (diag_stage_set / diag.asm
   stamps / the park loop behind DSP4_BISECT per item 3), rebuild the
   clean production images, reflash both chips, verify LEDs + readback,
   commit the production .ldr hash-named. Update P2.2 to 🟢 with the
   verdict; note the SPICMD dependency (production boot path must carry
   --spi-cmd 0x03).
4. If the wedge does NOT close on the SPORT4 fix: bisect further with the
   LED (now a real instrument) rather than the all-zero SPI readback, and
   write up where it dies.
Do NOT touch the CLKIN mods (blue, done) or the H1S1 ADAU-poll item (that
is a separate near-term firmware task needing the real H1S1 sources).
Constraints: matrix-app restarted + 3 MCUs verified before ending; ~/db
Dropbox; single trunk; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 15:0xZ — 🔴 stopped mid-bisect (bench released to PW); P2.2's premise is refuted

**The dma_cfg_init wedge does not exist as described.** Every park placed
inside `dma_cfg_init` stayed silent, and so did a park on the FIRST
INSTRUCTION of `_start`. The full firmware has never run on this card —
not once, at any point in this investigation. Only the ~1 KB standalone
`blink` / `rdyprobe` images ever have, which is why "the DSPs boot" read
as settled after the SPICMD fix (D14): that conclusion was drawn entirely
from 1 KB images and does not generalise.

**ROOT CAUSE (partial): the boot kernel cannot take a large loader
block.** Bisected with a new instrument, `src/blink/bulkprobe.asm` —
rdyprobe plus a slab of never-executed code, so boot-stream size is the
only variable — chip 1, ten boots per rung, verdict read over ssh:

| image | stream | biggest block | boots |
|---|---|---|---|
| bulkprobe0 | 180 B | 68 B | **10/10** |
| bulkprobe2 | 8 364 B | 8 252 B | **0/10** |
| bulkprobe2, same DXE, `-MaxBlockSize 0x400` | 8 492 B | 1 KB | **4/4** |
| bulkprobe2, same DXE, `-MaxBlockSize 0x1000` | 8 396 B | 4 KB | **4/4** |

Nothing else moves the result. Not the SPI clock (100 kHz behaves exactly
as 1 MHz — so it is not a timing race). Not the host transfer size
(`--chunk 1024 / 2048 / 4096` all identical — so it is not a spidev or
CS-window artefact; `--chunk` was added to `dsp4_boot.py` for this). Not
the zero-fill blocks (deleting the 506 KB L2 fill via a temporary
`NO_INIT` on `sec_delay` changed nothing). It is the byte count in a
single block header.

`-MaxBlockSize 0x1000` is now in `build.sh`'s `LDRFLAGS`, with the
evidence written into the comment beside it.

**It is necessary and NOT sufficient.** The full 208 KB chip-1 image
built with the cap still does not execute (`DSP4_BISECT=5` park silent).
So there is a SECOND limit somewhere above ~8 KB — total image size,
block count, or the fill blocks. **That is exactly where this stopped.**

**NEXT STEP, and it is one command's worth of work:** the bulkprobe
ladder rebuilt with the cap in place, run up the sizes —

```
cd MW/D32/DSP/SHARC && BULK_LEVELS="2 3 4" ./build.sh bulkprobe
# bulkprobe2 8 KB (known good with the cap), 3 = 33 KB, 4 = 66 KB
scp build/bulkprobe{2,3,4}.ldr app@192.168.1.219:/home/app/dspboot/
# per image: dsp4_boot.py --ldr bulkprobeN.ldr --chip 1
#            dsp4_stagewatch.py --chip 1 --seconds 6
```

If 3 and 4 boot, the second limit is not raw size and the next variable
is the fill blocks (`-MaxFillBlockSize`) or the block count. If they do
not, bisect between 8 KB and 33 KB the same way. Either way the answer is
a loader flag, not firmware.

**What this retires.** The SPORT4-7 `sport_dma_base()` fix is still
correct against `sys/ADSP-21564.h` and stays, but it is UNTESTED on
hardware and was never the thing that hung: nothing in `dma_config.c` has
ever been reached. The "1-flash hang inside `arm_region`" reading from
2026-08-19 was an LED code from an image that had not loaded, not a hang.
`ldr/manifest.txt` now carries a WITHDRAWN note: the two production
`.ldr`s on record are not bootable images.

**New instruments, all committed and deployed to `/home/app/dspboot`
(md5-checked both ends):**

| tool | what it does |
|---|---|
| `tools/pi/dsp4_stagewatch.py` | samples GPIO8/GPIO12 at 1 kHz and decodes the DSP status-LED pattern into a verdict — steady square = running, N flashes = stuck after stage N, flat = not running. Removes the need for eyes on LD3/LD2 for every bisect round. |
| `src/blink/bulkprobe.asm` + `./build.sh bulkprobe` | the boot-size ladder above. `BULK_LEVELS="..."` selects rungs. |
| `dsp4_boot.py --chunk N` | host transfer size, to separate a kernel limit from a transfer-boundary artefact. |
| `DSP4_BISECT=4` / `=5` | park on entry to `dma_cfg_init` / on the first instruction of `_start`. Parks now pulse PB_05 (Pi GPIO8/12) with interrupts OFF instead of relying on the timer-ISR LED, so a park answers "was this point reached?" without also asking about the interrupt path. |

All of the above is still TEMPORARY scaffolding and still goes with NOW
item 3 — except `-MaxBlockSize`, `dsp4_stagewatch.py`, `bulkprobe.asm`
and `--chunk`, which stay.

**Bench state at hand-off (PW took rev C for an app/panel reflash):**
`matrix-app` restarted and active, all three MCUs verified at 14:58
(H1S1, H1S3, H1S4 — "MCU verified" and "MCU boot verified" both), GPIO
9/10/11 back to `a0`, GPIO8/12 inputs, GPIO16 output high. Chip 1 holds a
non-running `DSP4_BISECT=5` image and chip 2 was last reset without one;
neither runs code, which is the same state as before this session and
harmless. Nothing further was booted or flashed after the hand-off
request.


## HUB DISPATCH 2026-08-21 11:26Z — SHARC ③ — scope-driver + boot-bus toggle capture (rails good; CPLD cannot mirror SPI/RST)   [status: 🟢 done — **ROOT CAUSE FOUND AND FIXED. Both SHARCs boot and run application code.** The boot host never sent the SPICMD byte the SPI-target boot kernel reads as its FIRST byte (HRM Table 36-18: 0x03 = keep single-bit mode), so the ROM consumed the first byte of the .ldr as the command and every block header after it was shifted by one. Added `--spi-cmd` (default 0x03) to dsp4_boot.py: GPIO8 now toggles at ~1 Hz on chip 1 and GPIO12 at ~2 Hz on chip 2, and an A/B/A control with `--spi-cmd none` reproduces the old flat-low failure exactly. The parts were never damaged]   [model: opus]
model: opus

Rails are GOOD at the bench (PW): +0.9V, +1V8 VDD_REF, +3V3 all in spec —
suspect (1) power CLEARED. The liveness checklist now needs a live scope of
SPI2 CLK/MOSI and SYS_HWRST during a boot. Hub netlist check: neither the
Pi-mastered boot SPI to the DSPs nor RST_D routes to the CPLD, so a CPLD
patch cannot bring them out — do NOT build one for that. All three signals
are reachable natively:
  test 1 CLKIN  = R65.2/R33.2 pad (PW verified good).
  test 2 boot SPI = Pi header J6 pin 23 (SCK/GPIO11), pin 19 (MOSI/GPIO10),
    0.1"; DSP-side confirm R52.2/R51.2 (DSPA), R19.2/R18.2 (DSPB) 0402 pads.
  test 3 SYS_HWRST = J6 pin 36 (RST_D/GPIO16), 0.1"; expect a clean low pulse
    >= 11 x tCKIN (~450 ns at 24.576 MHz) at each boot.

**PW BENCH RESULT + NEW LEAD 2026-08-21 (highest priority now):** with the
square-wave driver running, PW scoped the Pi header: J6.23 (SCK) TOGGLING,
J6.19 (MOSI) TOGGLING, **J6.36 (RST_D/SYS_HWRST) STUCK HIGH — not toggling.**
The Pi drives the boot bus fine, but it CANNOT toggle RST_D. This matches the
netprobe ("!RST_D held high, U7 p47 also drives it") and the dual-master
errata: the S MCU H1S1 (U7 PA13, pin 47) drives RST_D push-pull and wins over
the Pi's GPIO16. CONSEQUENCE: the Pi has never been able to pulse SYS_HWRST low,
so the two SHARCs came out of reset once at power-on (ran the boot ROM with
nothing to receive) and every dsp4_boot since sent a stream to a part not in
its boot-listen window — exactly "boot reports OK, GPIO8 flat".

DO THIS:
1. CONFIRM contention (not a script miss): with the Pi driving GPIO16 LOW
   push-pull, read GPIO16 back — if it reads HIGH while driven low, U7 is
   overpowering it = confirmed. (If it reads low, the earlier script just
   didn't drive it — fix and re-scope.)
2. RELEASE RST_D to the Pi so a real reset is possible. Options, cheapest
   first: (a) does current H1S1 firmware drive PA13, or is this the rev-A
   image that should leave it as input? Check the H1S1 source (Core/... 
   the errata "H1S1 fw leaves PA13 as input" rule). (b) Hold H1S1 in reset
   (its NRST) during a DSP boot so PA13 goes hi-Z and the Pi owns RST_D —
   find how NRST is reachable (power-MCU? a GPIO? the SWD/prog path?).
   (c) If neither is quick, PW bench: physically lift U7 PA13 or the RST_D
   link — record as a red mod.
3. With RST_D released, run dsp4_boot (which pulses RST_D low then streams)
   and check GPIO8. THIS is the real boot test — the clock is good, the bus
   toggles, and now the part can actually be reset into boot mode.
4. Record the verdict. If GPIO8 finally toggles: the boot-handoff root cause
   = RST_D dual-master (H1S1 held the DSPs out of Pi-controlled reset), not
   damaged parts — a firmware/mod fix, no new card needed. Update the
   dual-master item on the mods PDF accordingly (still a rev-D hardware fix,
   but the immediate unblock is releasing PA13).

**PW REFINEMENT (do this FIRST, priority over the boot loop):** PW wants
INDEPENDENT steady repeating signals on each of the three pins to scope
directly — not boot-shaped bursts. Deploy a small script on the Pi
(app@192.168.1.219, /home/app/dspboot) that drives, as plain GPIO outputs,
a clean square wave PW can catch and level-check at the DSP-side pad:
  - SCK  = GPIO11  (scope at J6 pin 23 or R52/R19 DSP pad)
  - MOSI = GPIO10  (scope at J6 pin 19 or R51/R18 DSP pad)
  - SYS_HWRST = GPIO16 / RST_D (scope at J6 pin 36; note this RESETS both
    DSPs each cycle — fine)
Pick a scope-friendly rate (~1 kHz square, 50% duty) and drive all three
continuously; give PW a one-liner to start and to stop (and to restore the
pins after). CRITICAL: GPIO10/11 are normally spidev's — release/stop any
spidev claim first (the netprobe path already toggles these as GPIO), and
drive them push-pull so the scope shows whether the Pi can actually swing
the net or something clamps it (netprobe saw SCK/MOSI 'held high by
something stronger than the Pi pull' — this square wave at the DSP pad is
the direct test of that: if the Pi drives 0/1 at J6 but the DSP-side pad
stays stuck, there is a break/contention between them). Log the Pi-side
readback while driving. THEN the boot loop below for the realistic view.

TASK A — scope-driver so PW can probe live. Provide a repeating desk-driven
boot on demand: a small loop that boots rdyprobe1.ldr on chip 1 every ~3 s
(and a chip-2 variant), so the SPI2 CLK/MOSI and RST_D edges recur on the
scope. Deploy to /home/app/dspboot as a named script; give PW the exact
one-liner to start/stop it. While it runs, capture on the Pi side what the
boot bus is doing (dsp4_netprobe during the loop) and log it.

TASK B — the discriminating capture (no bench eyes): during the boot loop,
use the Pi to sample, at the DSP boot bus, whether SCK (GPIO11) and MOSI
(GPIO10) actually TOGGLE during the CS-asserted window, vs the netprobe's
earlier "held high" static read. If they are static during boot, the Pi is
not clocking the DSP (host/driver/contention problem) — a different class
than a dead DSP. If they toggle but RDY never deasserts and GPIO8 stays
flat, the DSP is receiving clock+data+reset and still not running = the
parts themselves. State which of these the evidence supports.

TASK C — bookkeeping. Write the scope-point map (the table above, with the
J6 header pin numbers and the resistor pads) into the liveness checklist
doc so PW has it at the bench, and record the CPLD-cannot-mirror-2/3
finding. If TASK B points at the parts, say so plainly and the fresh-card
build is next; if it points at the Pi-side boot drive, propose the fix.
Do NOT build a CPLD patch. Constraints: restart matrix-app + verify 3 MCUs
before ending; ~/db Dropbox; single trunk; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 13:05Z — 🔴 BLOCKED on one DMM measurement at the bench

**TASK A — done, deployed, exercised.** Three new tools in `tools/pi/`,
copied to `/home/app/dspboot` (md5-checked both ends):

| tool | what it does |
|---|---|
| `dsp4_scopedrive.py` + `.sh` | PW's refinement, built first. Drives SCK/MOSI/!RST_D as **plain push-pull GPIO square waves**, one frequency per pin so the scope identifies the pin without moving the probe: SCK 1 kHz, MOSI 500 Hz, !RST_D 250 Hz. Also `hold RST_D=0` for a DC level a meter can read. Releases and **restores spidev's ALT0 pinmux** on stop. |
| `dsp4_bootloop.sh` | repeats a real `dsp4_boot.py` boot every ~3 s (chip 1 or 2) so the boot-shaped edges recur. |
| `dsp4_busmon.py` | **passive** GPLEV0 capture through `/dev/gpiomem` at ~1.3 MSa/s. Claims no line and changes no pull, so it runs *during* a boot — which `dsp4_netprobe.py` structurally cannot do, because its bias-and-read method takes SCK/MOSI away from SPI0 and would break the transfer it is meant to watch. That is why netprobe only ever reported the bus at rest. |

One-liners for the bench (all in the checklist doc):
`cd /home/app/dspboot && ./dsp4_scopedrive.sh start | stop | hold RST_D=0`,
`./dsp4_bootloop.sh start [chip] [period] | stop`. Both stop `matrix-app`
on start and restart it on stop.

**A live-fire hazard found and fixed while building this:** `pinctrl get
9,10,11` read **`ip` (plain inputs)**, not `a0`. Releasing a gpiod line
leaves the pin an input and nothing restores the SPI0 pinmux — not a
`matrix-app` restart. `dsp4_netprobe.py` had left them that way at the end
of the 08-20 session, so any boot run afterwards would have clocked
nothing while still reporting OK. Both new wrappers now set `a0`
explicitly, and `dsp4_scopedrive --restore` puts it back.

**TASK B — the discriminating capture: the Pi IS clocking the DSPs.**
`dsp4_busmon.py` around a real `rdyprobe1.ldr` boot, 3 267 584 samples in
2.5 s:

| net | whole capture | inside the CS1-low window |
|---|---|---|
| SCK (GPIO11) | ACTIVE, 16 170 transitions | **16 170 — all of them** |
| MOSI (GPIO10) | ACTIVE, 1066 transitions | 498 |
| !RST_D (GPIO16) | low for **51.7 ms** (the tool's 50 ms pulse) | — |
| MISO, RDY1, RDY2 | STATIC low throughout | STATIC low |

1024 bytes × 8 = 8192 SPI clocks = 16 384 edges; 16 170 observed, the
deficit being a 0.77 µs sampler aliasing a 1 MHz clock, not lost cycles.
PW's scope agrees at the header (J6.23 and J6.19 both toggling). **So the
netprobe's "MOSI/SCK held high" was a statement about an idle bus, not a
dead one, and TASK B's host-side-drive branch is closed.**

**The hub's PA13 mechanism is refuted — but the conclusion survives.**

- H1S1 firmware (`~/build-h1s1`): **PA13 is not configured at all.** It is
  absent from the `.ioc` pin list, `RST_D_Pin`/`RST_D_GPIO_Port` are not
  defined in `main.h`, and the only two references in `main.c` are
  commented out. PA13 sits in the STM32U5 reset default — SWDIO alternate
  function, ~40 kΩ internal pull-up. That is what beats the Pi's ~50 kΩ
  internal pull-down in netprobe; it cannot fight a push-pull output.
- Pi GPIO16 at the CM4 pad, 2000 samples per state: input+pull-down →
  **high** (the PA13 pull-up), input+pull-up → high, **driven low
  push-pull → low, 2000/2000**, driven high → high, square wave → follows
  0/1. The Pi owns the net at its own end.
- So there is nothing to release: holding H1S1 in reset or lifting PA13
  would change nothing, and dispatch options 2(a)/(b)/(c) are all moot.

**Net topology, settled from the schematic (ROOT sheet p1/10).** The DSPA
and DSPB hierarchy blocks each take `!RST_D` into a port named `RST`, and
on the DSPA sheet (p5) that sheet-local `RST` lands on **U6 p104,
SYS_HWRST** — same for DSPB/U5. One net: **CM4 GPIO16 · U7 PA13 · J6.36 ·
DIL100 P13 · U5 p104 · U6 p104**, no series resistor. Recorded in
`hardware-map.md` §3. (A wrong turn on the way, corrected by PW at the
desk: the DSP sheets are sub-sheets and their labels are sheet-local, so
the `RST` on the M MCU sheet is U8's own NRST — a different net. It was
briefly tested as a way to reset the DSPs: an AIRCR SYSRESETREQ on U8 does
pull its NRST low, proven by RCC_CSR going 0x00000000 → **0x14000000**
(SFTRSTF **and PINRSTF**) across a pure software reset, but that net does
not reach the parts, and booting after it left GPIO8 flat as expected.)

**Which leaves one physical reading of PW's bench result.** The Pi's end
of `!RST_D` is at 0 V while J6.36 on the card is at 3.3 V, on one net. That
is an **open between the CM4 and the DSP4 card** — a DIL100 P13 contact, a
broken track/via, or an unstuffed link — with PA13's pull-up holding the
isolated card-side segment high. If so, neither SHARC has ever been reset
by the host: both came out of reset once at power-on, ran the boot ROM with
nothing sending, and have never re-entered the boot window since. That is
"boot reports OK, GPIO8 flat", every time, since March.

**TASK C — bookkeeping done.**

- `~/db/TransferOnly/PCB mods/dsp4-revC-liveness-checklist.md`: new §1a
  probe-point map (J6 pin numbers + the DSP-side 0402 pads + the bench
  one-liners), the CPLD-cannot-mirror-2/3 finding recorded, step 1 marked
  PASS (rails), step 2 marked pass-at-the-header, and **step 3 rewritten as
  the open item** with all the evidence above and a four-step procedure.
- `MW/D24/HW/hardware-map.md` §3: the `!RST_D` net traced end to end, the
  sub-sheet naming trap, and the PA13-unconfigured finding.

**Blocked on — one measurement, no scope needed:**

```
ssh app@192.168.1.219 'cd /home/app/dspboot && ./dsp4_scopedrive.sh hold RST_D=0'
```

then meter **J6 pin 36** (and p104 on U5/U6 if reachable);
`./dsp4_scopedrive.sh stop` after.

- Both ~0 V → the net is sound, the earlier scope reading was a pin out,
  and the investigation goes to the parts (checklist step 4: fresh card /
  fresh SHARCs).
- J6.36 at 3.3 V → **open confirmed**; find the segment with a continuity
  check power-off, bodge it, re-run `./dsp4_bootloop.sh start` and watch
  GPIO8. Red mod on rev C, item on rev D.
- If the break is unreachable, the card-side fallback is real: U7 PA13 is
  on that net, doing nothing. Configure it as a push-pull output with a
  "pulse !RST_D" command in H1S1 and the supervisor can reset the DSPs —
  which the schematic annotation always claimed it could.

Unit left with `matrix-app` running, all three MCUs verified (H1S1, H1S3,
H1S4 at 12:46), GPIO5/13 back to inputs, GPIO9/10/11 back to `a0`, GPIO16
output high.


### Addendum 2026-08-21 14:00Z — 🟢 ROOT CAUSE: the missing SPICMD byte

**Both SHARCs boot and run application code. The parts are fine.**

PW put a scope on **DSP pin 10, SYS_CLKOUT**, and read **24.5 MHz at 3.3 V**
— the first positive liveness signal this card has ever produced, and the
thing that turned the investigation around. HRM §"CLKOUT Selections":
*"BMODE = (non zero) — When a hardware reset is deasserted, SYS_CLKIN is
selected by default"*, routed DIRECT per Figure 2-2. Our BMODE is 0b010, so
pin 10 is a straight mux from pin 5. That single reading proves VDD_EXT is
present at the die, the output driver works, SYS_CLKIN0 is reaching and
being received correctly *through the part* (better evidence than the pad
scope), and a hardware reset has been deasserted. It also proves BMODE is
non-zero, i.e. not the 000 No-Boot strap.

Then, with `!RST_D` held low from the desk, **PW read pin 10 LOW** — CLKOUT
stops. So the reset reaches the die too, closing the last unverified hop.
Every precondition was verified good on a part that was demonstrably alive,
which meant the fault had to be in the boot handshake itself.

**It was.** HRM ch.36, *SPI Target Boot Mode*:

> "The SPI target processor detects the correct boot mode from the host SPI
> device by reading **the first byte sent, defined as SPICMD**. … These
> additional bytes **must be sent prior to transmitting the data** to
> configure the SPI device."

Table 36-18, host starting in single-bit mode: **0x3 = keep single-bit
mode** (0x7 dual, 0xB quad). `dsp4_boot.py` sent the `.ldr` straight in with
no command byte, so the boot kernel ate the first byte of the first block
header as SPICMD and every header after it was misaligned by one byte:
HDRSIGN never 0xAD, no block ever passed its XOR check, the boot never
completed — while the host still saw a stream clocked out from end to end.
That is precisely the signature this card has had since March.

`--spi-cmd` added to `dsp4_boot.py`, default `0x03`, sent with SS asserted
and before the first stream byte per the host flow in HRM Figure 36-6.

**Result, and the A/B/A control that makes it causation:**

| run | GPIO8 / GPIO12 |
|---|---|
| chip 1, rdyprobe1, SPICMD `0x03` | `hi hi hi hi lo lo lo lo hi hi …` — **~1 Hz** |
| chip 2, rdyprobe2, SPICMD `0x03` | `hi hi lo lo hi hi lo lo …` — **~2 Hz** |
| chip 1, `--spi-cmd none` | `lo lo lo lo …` — the old failure, exactly |
| chip 1, SPICMD back on | toggling again |
| chip 1 rdyprobe + chip 2 blink2, **matrix-app running** | GPIO8 toggling; LD2 should blink |

**What this retires.** The "damaged parts / fresh card / fresh SHARCs"
verdict recorded earlier today is **withdrawn** — do not order parts on it.
Both SHARCs survived the SYS_CLKIN0 overdrive. Everything the earlier
rounds fixed was real and necessary (the ÷2 CPLD clock, the level-shift
bodge, the active-low RDY correction, the H1S1 CS1-6 reflash, the SPI0
pinmux restore), but none of it was sufficient, because the host had never
spoken the first byte of the protocol.

**What stands.** The two-master contention on the boot bus (H1S1's legacy
ADAU meter poll, ~600 µs every ~260 ms) is still real and still worth
removing — it is now the most likely cause of any *intermittent* boot
failure, at ~5.6 % per attempt. The RDY pull-downs (R34/R22) are still
backwards versus HRM Figure 36-4, which wants a 10 K pull-**up** to
VDD_EXT; back pressure works anyway because the part drives the pin, but
the in-reset hold-off does not, and the fixed 500 ms settle is standing in
for a handshake we cannot see. Both are rev-D items.

Unit left with matrix-app running, all three MCUs verified (13:57), chip 1
running rdyprobe1 and chip 2 running blink2.


### Addendum 2026-08-21 13:20Z — 🟢 the open item closed at the bench, verdict: the parts

**!RST_D is good.** PW watched the pin go LOW the moment
`./dsp4_scopedrive.sh hold RST_D=0` was started. The earlier "J6.36 stuck
high" was measured with GPIO16 at its idle level — the tool parks !RST_D as
an output HIGH whenever it is not deliberately driving, and so does every
`stop`, so a high reading in that state is correct and discriminates
nothing. There is no open and no contention. (The confirmed low was at the
header end; the last hop to p104 is netlist inference, no series R on the
net.)

**The closed loop, re-run on both parts with every precondition verified**
(`dsp4_busmon.py` capturing passively through the whole boot, GPIO9/10/11
confirmed at `a0` first):

| | chip 1 | chip 2 |
|---|---|---|
| `!RST_D` low pulse | 158.6 → 209.1 ms (50.5 ms) | 158.7 → 209.2 ms (50.5 ms) |
| CS low | 714.5 → 728.5 ms | 712.3 → 726.3 ms |
| SCK inside the CS window | **16 334 transitions, one burst, 50 % duty** | **16 332, 49 %** |
| MOSI inside the CS window | 236 transitions | 232 |
| MISO | static low throughout | static low |
| SPI_RDY (GPIO8 / GPIO12) | static low, and flat for 6 s after | static low |

16 384 edges are expected for 1024 B; the shortfall is a 0.75 µs sampler
aliasing a 1 MHz clock. Reset, settle, one clean burst inside the select
window — and neither part drives MISO or SPI_RDY, ever.

**Verdict.** SYS_CLKIN0 correct and scope-verified at the pin; +0.9 V,
+1V8 VDD_REF and +3V3 all in spec on a meter; !RST_D reaching the net; and
1 kB of correctly-framed data clocked into each part at the right moment.
Every precondition for a boot is verified good and neither SHARC has ever
driven a pin. **Nothing on the host side is left to fix — the next step is
a fresh card / fresh SHARCs** (checklist step 4), with the corrected clock
chain fitted before first power-up. Both parts were overdriven ~80 mA into
a 6 mA-max clamp on SYS_CLKIN0 from March until 2026-08-21, which remains
the only mechanism on the table that fits.

**Checklist step 0 is closed too, PASS:** PW confirms the decoupling caps
ARE fitted to both DSP chips — they are simply absent from the printed
schematic. The blank `CAPS` sub-sheets (PDF pages 9/10) are a documentation
defect, not a hardware one, so it is not a rev-C fault and not a suspect.
Rev-D mod 14 is downgraded from RED to a drawing item (draw the two CAPS
sub-sheets). Reading lesson recorded in the checklist: a blank sub-sheet in
this project does not mean an empty net.

With that, **every suspect on the list is closed except the parts.**

**A second, unarbitrated SPI master on the DSP boot bus — identified and
confirmed 2026-08-21.** PW named it from the history: H1S1 used to drive
these pins to **read ADAU meter levels, periodically**, and the flashed
image still does. The measurement confirms it and shows why it was
invisible.

With the Pi's `SPI_MOSI` idle, `!SPI1` carries a burst of ~80 transitions
every ~256 ms, and `SCK` showed **zero** transitions — which made no sense
for an SPI transfer. It made sense once GPIO9/10/11 were taken out of `a0`
and made plain inputs:

| | Pi SPI0 attached (`a0`) | Pi SPI0 released (inputs) |
|---|---|---|
| SCK transitions in 1.5 s | **0** | **1630, in 7 bursts** |
| SCK idle level | held LOW by the Pi's output | **99.9 % high** |
| burst period | — | **~260 ms** (260.7 / 260.0 / 263.1 / 261.2) |
| burst length | — | ~600 µs, ~240 edges each |
| MOSI | 472 transitions | 480 transitions, same bursts |
| MISO | static low | static low — nothing answers |

So **the Pi's SPI0, whenever it is enabled, actively clamps SCK and shorts
out H1S1's clock.** H1S1 has been polling into a dead bus, its clock
swallowed by the Pi's push-pull output, and nothing answers on MISO — the
ADAU those meter reads were written for is not there to reply. The idle-
high SCK also says H1S1 runs that bus in a CPOL=1 mode, against the Pi's
mode 0/1: two masters, two clock polarities, no arbitration.

(The tree at `~/build-h1s1` has its `DspTx()` — `buffer[0]=0`, address hi,
address lo, payload over `CS_C`/`CS_M`, the SigmaDSP/ADAU write format —
entirely commented out, and `MainInit`/`MainLoop` are not in it at all. So
that tree is not the flashed image; the running `firmware/H1S1.shex` still
carries the poll.)

**Could it corrupt a DSP boot? Yes, but only the data, and only ~5 % of
the time — and it did not corrupt the boots that failed.**

- **Not the clock.** The same clamping that hid the poll protects the boot:
  with GPIO11 in `a0` the Pi's SPI0 output holds SCK, and the measurement
  is direct — **zero** foreign SCK transitions with `a0` attached, 1630
  without. A boot necessarily runs with GPIO11 in `a0`, so the clock the
  DSP sees during a boot is always the Pi's. (Earlier phrasing "injects
  foreign clock and data" was wrong on the clock half.)
- **The data, yes.** MOSI shows H1S1's bursts even with `a0` attached (472
  transitions vs 480 released), so H1S1 wins, or at least contends
  successfully, on that line. The DSPs' `SPI2_MOSI` (PA_01) hangs off it
  through the 22 R network, and during a boot the Pi has CS asserted, so
  the part *is* listening. A burst landing inside the transfer would put
  foreign bits into the stream and the block would fail its HDRSIGN/HDRCHK.
- **Probability:** ~600 µs of burst every ~260 ms against a 14 ms transfer
  ≈ **5.6 % per boot attempt**, one in eighteen. That is an intermittent
  failure nothing in the host logs could explain — worth removing — but it
  cannot produce the 100 % failure seen since March across hundreds of
  boots.
- **And it is excluded for the boots that matter.** Both of today's boots
  were captured end to end: the bursts fell at 48.3, 301.2, 557.2 and
  808.2 ms while the chip-1 boot ran 714.6 → 728.4 ms, and SCK showed
  exactly one burst, entirely inside the CS window, 16 334 of 16 384 edges
  at 50 % duty. Those two streams were clean, and the parts still did not
  respond.

**Actions:**

1. **Near term: remove the ADAU meter poll from the H1S1 firmware.** The
   part it polls is gone — this card is the SHARC DSP4 — so the poll is
   dead legacy whose only effect is contention on the boot bus. The unit
   already flashes H1S1 from `/home/app/firmware`. Needs the real H1S1
   sources; the tree at `~/build-h1s1` is not the flashed image.
2. **Rev D: give the DSP boot bus an owner.** Either separate it from the
   S-MCU housekeeping bus, or arbitrate it properly. D1 already says the Pi
   masters DSP SPI directly; the schematic quietly puts a second master on
   the same three wires.
3. Note for anyone reading `dsp4_netprobe.py` output: "MOSI/SCK HELD HIGH"
   is this — an external master idling its bus high — not a fault.

Unit left with matrix-app running and all three MCUs verified (13:17).


## HUB DISPATCH 2026-08-21 10:46Z — SHARC testing ② — boot retest on corrected CLKIN (÷2 + level-shift fitted)   [status: 🔴 blocked — clock now verified good at the pad and BOTH chips are still flat (GPIO8/GPIO12 never move, no RDY high in a reset-pulse trace); new lead found at the desk: neither SHARC has any decoupling in the rev-C schematic — PW checklist written, ordered by cost]   [model: opus]

model: opus

PW fitted the CLKIN level-shift bodge (variant: 1k replacing R33/R65 +
330R from the DSP-side pad to GND, per DSP — same 0.245 ratio as the 1k2/390R
in your mod doc) and the card is back in the rev C unit, which rebooted
11:45 local (matrix-app active, H1S1/H1S3/H1S4 verified). CPLD is already on
the ÷2 bitstream a1f6672af6c3. The unit is yours.

**PW BENCH RESULT 2026-08-21 (feed into this task):** scope at the R33/R65
pad shows CLKIN LEVEL and FREQ both good now (0.7-0.82 V, 24.576 MHz) — the
clock suspect is CLEARED electrically, mod restated BLUE on the mods PDF. BUT
the DSP LEDs (LD2/LD3) show NO activity after boot. So: the clock fix alone
did not bring the parts up. Your GPIO8 rdyprobe loop is now the discriminator
— run it FIRST. If GPIO8 also stays flat with a verified-good clock, the
live suspects narrow to: (1) damaged SHARCs (both overdriven ~80 mA into the
0.9 V clamp since March — check the datasheet abs-max exposure, and whether
a fresh card / fresh parts is the only proof), (2) SYS_HWRST behaviour at
p104 (never met the 11xtCKIN-after-supplies-stable spec before), (3) a
boot-stream/entry issue that the earlier "stream consumed" evidence never
actually ruled in. Rank these by cost for PW; do not iterate blind.

TASK — SHARC testing ②: boot retest on the corrected clock.
1. Baseline first, no bench eyes: netprobe PCM_CLK/PCM_FS toggling (CPLD
   alive), RDY1/RDY2 resting state, +0.9 V sanity if readable. Note that
   PW has NOT scoped the clock level yet — if anything below behaves
   oddly, the first hands request is "scope R33/R65 pad: 0.70–0.82 V
   high, ≤0.10 V low, 24.576 MHz; if >0.82 V swap shunt to 300R".
2. Closed loop exactly as the 08-20 dispatch: rdyprobe1.ldr on chip 1,
   sample GPIO8 — success = ~1 Hz lo/hi. Then chip 2. Also repeat the
   "!RST_D pulse, no SPI traffic" RDY observation and compare with the
   dead-part baseline you recorded.
3. If the loop passes: blink1/blink2 (tell PW to eyeball LD3/LD2 at 1 Hz /
   2 Hz), then the production chip1/chip2 images and resume P2.2
   (dma_cfg_init) with working instruments. Record the verdict:
   "rev C CLKIN (freq + level) — root cause of the boot-handoff failure;
   fixed ÷2 in CPLD + level-shift bodge; rev D crystal per DSP".
4. If still flat: the fault is either the clock level at the pad (PW
   scope, see 1), damaged parts (both overdriven since March — a second
   card/fresh SHARCs is then the path), or something downstream; write
   the PW bench checklist ordered by cost and stop. Do not iterate blind.
5. Bookkeeping: mark the 07:23Z block 🟢/🔴 with the verdict; the mod
   goes BLUE on D24 DSP mods.pdf only after PW verifies on the scope —
   leave that to the hub, just record "fitted 2026-08-21 (1k+330R),
   scope verification pending" in the decisions doc.
Constraints: always restart matrix-app and confirm the three MCUs verify
before ending; Dropbox via ~/db; single trunk; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 11:05Z — 🔴 BLOCKED. Clock cleared, parts still dead.

**Verdict: the corrected CLKIN is NOT the root cause of the boot-handoff
failure.** With the clock verified good at the pad by PW's scope
(0.70–0.82 V, 24.576 MHz) and the ÷2 bitstream on the CPLD, every liveness
test reads exactly as it did against the dead-part baseline of 08-20.

| test | result |
|---|---|
| `dsp4_netprobe.py` full sweep (matrix-app stopped) | identical to the 08-20 baseline: PCM_CLK/PCM_FS **toggling** (CPLD alive), RDY1/RDY2 held low on R34/R22, MOSI/SCK held high, !RST_D held high by U7, MISO/CS floating |
| `dsp4_boot.py --ldr rdyprobe1.ldr --chip 1`, then 20 × `pinctrl get 8` | boot reported OK (1024 B on CS1); GPIO8 **`lo` on every sample** |
| `dsp4_boot.py --ldr rdyprobe2.ldr --chip 2`, then 20 × `pinctrl get 12` | boot reported OK (1024 B on CS2); GPIO12 **`lo` on every sample** |
| `--rdy-trace 1 --window 1.0` (!RST_D pulse, no SPI traffic, ~14 µs sampling) | 69727 samples, **no HIGH** |
| `--rdy-trace 2 --window 1.0` | 70789 samples, **no HIGH** |
| LD2/LD3 after a boot (PW, bench) | no activity |

No blind iteration beyond that: two boots per chip, one trace per chip.
Images on the unit were hash-checked against `build/` first (rdyprobe1
`6f8da654…`, rdyprobe2 `049792ab…`) — identical, so nothing stale was booted.

### The new lead, found at the desk: neither SHARC has any decoupling

The DSPA (p5) and DSPB (p4) sheets of `D24 DSP.pdf` each instantiate a
sub-sheet block labelled **CAPS** carrying VDD_INT / VDD_EXT / VDD_REF —
and both of those sheets (PDF pages 9 and 10) are **blank**: title block,
zero ink, measured. There are no C-designators anywhere on either DSP
sheet, while every other device on the card is decoupled (CPLD C8–C21, the
1V8 regulator C3/C4/C6/C7, the XO C2/C5, the M MCU C202–C205). Each part
has ~25 VDD_INT pins plus VDD_EXT and VDD_REF (the PLL/OTP supply), all
arriving over the DIL100 stack.

Unverified against the layout/BOM (the Proteus project is on the Windows
machine), so it is a lead, not a finding — but it is a **one-minute check
with the board in hand**, it would explain everything seen since March, and
the bodge is a handful of 0402s. It is step 0 of the checklist below and
rev-D **mod 14**.

### Two suspects cleared from the desk (do not spend bench time on them)

- **Reset timing.** `dsp4_boot.py` holds `!RST_D` low 50 ms and waits
  500 ms before the first byte; the datasheet asks 11 × tCKIN ≈ 0.45 µs for
  both tWRST and tRST_IN_PWR (Tables 22/23), with supplies long stable. The
  timing half of the HWRST suspect is answered; only the *level* at pin 104
  is unproven, given the two unarbitrated masters on that net.
- **CGU arithmetic — and a correction to this dispatch's premise.** The HRM
  gives **PLLCLK = SYS_CLKIN × MSEL / 2** with reset defaults **MSEL = 40,
  CSEL = 1, SYSSEL = 2, S0SEL = 4** (Tables 2-10/2-11 + register diagrams).
  So at 24.576 MHz: PLLCLK 491.5 MHz, CCLK 491.5 MHz, SYSCLK 245.8 MHz,
  SCLK0 61.4 MHz — every one inside spec, ROM correctly clocked with no CGU
  programming (there is none anywhere in `SHARC/src`, correctly). At the old
  49.152 MHz it was 983 MHz PLLCLK/CCLK — inside the *family* maxima though
  about double the 21564 grade. The 07:23Z claim "MSEL = 60, DF = 0 →
  2.95 GHz, cannot lock, the ROM can never have run" was wrong twice (it
  dropped the /2 and used the wrong default). The ÷2 is still right — fCKIN
  20–30 MHz is an input-pin spec and 49.152 MHz violated it by 64 % — but
  the mechanism was not "the PLL could not lock", and nothing should rest on
  that story. Recorded in D10.

### Checklist written for PW, ordered by cost

`~/db/TransferOnly/PCB mods/dsp4-revC-liveness-checklist.md` (new):

0. **Eyes, no instruments** — are there ANY caps on the DSP power pins;
   does the layout/BOM have what the schematic lacks.
1. **DMM** — +0.9 V (0.855–0.945), **+1V8 VDD_REF** (1.71–1.89, U2 output;
   never measured, and without it the PLL cannot lock), +3V3.
2. **Scope during a desk-driven boot** — SPI2 CLK/MOSI at R52/R51 (DSPA),
   R19/R18 (DSPB): 1 MHz burst, mode 1. First proof a part receives data.
3. **Scope** — SYS_HWRST at p104 across the !RST_D pulse: does it actually
   reach VIL ≤ 0.7 V with U7 pin 47 also driving that net.
4. **The parts.** If 0–3 are clean and RDY still never moves: both were
   overdriven ~80 mA into a 6 mA-max clamp since March. Fresh card / fresh
   SHARCs is the only clean proof; a JTAG bodge is the alternative — and
   note the DSP TAP pins (99–103) are terminals that reach *nothing* on
   rev C, not even each other, so it is 5 wires per part on 0.5 mm pitch.
5. **Boot stream** last: it was verified byte-by-byte on 08-20 and cannot
   be ruled in until step 2 passes.

### Bookkeeping done

- Mod doc `dsp4-revC-clkin-bodge.md`: status → **fitted and scope-verified**,
  the as-fitted 1 k + 330 R recorded against the specified 1k2 + 390 R, a
  second trim ladder added for the 1 k series (300 R is the trim-down if a
  card reads > 0.82 V), the fault-1 mechanism corrected, and §6 records the
  retest result. Hub: the mod can go BLUE on the mods PDF — PW has scoped it.
- `dsp4-revD-modlist.md`: **mod 14 (DSP decoupling, RED)** added; mod 8
  annotated as fixed-and-verified-but-not-the-cause; mod 11 gains the "the
  TAP pins connect to nothing" detail.
- `dsp4-architecture-decisions.md` **D10**: bodge fitted + verified,
  the CGU correction, and what the fix did not fix.
- `MW/D24/HW/hardware-map.md` §3: verified clock chain, the decoupling
  observation, the three DSP supplies and where they come from (VDD_REF is
  on-card from U2), JTAG/RESOUT/FAULT connectivity.
- Unit left with matrix-app running and all three MCUs verifying.

**Blocked on:** PW at the board — checklist step 0 (eyes) and step 1 (DMM)
need nobody's permission and may end this investigation; steps 2–3 need a
scope on a powered card, and the boot side of them can be driven from the
desk.

## HUB DISPATCH 2026-08-21 07:23Z — SHARC testing ① — CPLD dsp_clk ÷2 (CLKIN out of range) + closed-loop retest   [status: 🔴 closed — VERDICT 2026-08-21: the clock chain was a real two-part fault (fCKIN out of range + a 3.3 V drive on a VDD_INT pin), both halves are now fixed and scope-verified on the card, and the boot handoff is STILL dead — so CLKIN was necessary but not sufficient, and this block's premise that it was the root cause is not confirmed]   [model: opus]

**Outcome 2026-08-21 09:55Z — 🔴 BLOCKED ON PW HANDS. Desk half done: ÷2 built, flashed and verified on the card; the level-shift bodge is specified and waiting to be fitted. No boot retest attempted — by the 08:45Z addendum it would not have produced a verdict.** See the outcome section at the end of this block.

model: opus

PW decision 2026-08-21: SHARC testing is the TOP priority for this machine;
reorder the NOW queue behind it (edit the NOW header to say so).

HUB HARDWARE REVIEW RESULT (mx26 docs/backlog-d24-schematic-errata.md
"DSP4 rev C", commit 5e1d419 — read it first): **SYS_CLKIN0 is driven at
49.152 MHz, outside the ADSP-2156x CLKIN range (20–30 MHz).** The CPLD
passes the XO straight through (`shared/dsp4-logic/rtl/dsp4_logic_top.v`
line ~100: `assign dsp_clk = sysclk;`). HRM CGU: reset-default MSEL = 60,
DF = 0 → PLLCLK ≈ 2.95 GHz at reset; the boot ROM can never have run.
This fits your 08-20 conclusion that there is no evidence either SHARC
ever received a byte. It is the prime suspect — test it first.

**TASK A — CPLD dsp_clk ÷2 (24.576 MHz).**
1. Replace the pass-through with a divide-by-2 flop on sysclk (50 % duty,
   glitch-free), keep pin 140; no other RTL changes. Add an SDC
   `create_generated_clock` for it. Update tb_logic_top to check dsp_clk
   = sysclk/2. Quartus build: fitter clean, STA met, LE delta noted.
   Commit the bitstream hash-named per the existing convention.
2. Flash it via the proven path (hub did it 08-19: SVF over the CM4 at
   app@192.168.1.219 — see mx26 tasks.md "dsp4_logic.fd6a5ec69198" and
   the IDCODE 0x020a30dd before/after check). Verify PCM_CLK/PCM_FS
   still toggle (netprobe) so the rest of the CPLD is unaffected.
3. Rerun the closed loop exactly as the 08-20 dispatch defines it
   (rdyprobe1.ldr on chip 1, sample GPIO8). Also repeat the
   "!RST_D pulse with no SPI traffic" RDY observation: with a live
   part the kernel should now show behaviour that differs from the
   dead-part baseline you recorded.
4. If GPIO8 toggles: boot blink1/blink2 (LD3/LD2 for PW at the bench),
   then the production chip1/chip2 images, and resume P2.2
   (dma_cfg_init) with working instruments. Record the verdict in
   findings/tasks as "CLKIN out of range — fixed in CPLD; rev D errata".
5. If still flat after a correct ÷2 (verified by build + a GPIO-side
   sanity where possible): STOP and write the scope checklist for PW's
   bench session — probe points are the 22R pads only: R65/R33 (CLKIN,
   expect 24.576 MHz, 3V3 swing), R51/R52 (SPI2 MOSI/CLK during a
   boot), p104 (HWRST), +0.9 V at J1 P1-6. Then the JTAG-bodge decision
   goes to PW (no DSP JTAG exists on the board).

**TASK B — bookkeeping.** Restate the clock finding in
dsp4-architecture-decisions.md (CPLD is the DSP clock source; 24.576 MHz
is the contract; programmable is a feature). Add the rev-D items from the
errata list to your "Blocked on PW" or rev-D section if not already there
(no JTAG, TRST floating, RDY pull-down, !RST_D dual master + PA13=SWDIO,
RESOUT/FAULT N/C, no test points). Datasheet gap: the 21560/61/64/68
datasheet is NOT in Dropbox or the repo (analog.com blocks fetch) — PW
asked to drop it into `_mx/_temp/adsp-2156x-docs/`; when it appears,
confirm the fCLKIN min/max line and close the [verify] tags.

**HUB ADDENDUM 2026-08-21 09:20Z — session restarted (permission mode
change only).** The previous session was killed by the hub mid-task to
relaunch under bypassPermissions; nothing of its work is lost: the working
tree holds the uncommitted ÷2 RTL/SDC/tb edits and the new bitstream
`dsp4_logic.a1f6672af6c3.*` (old fd6a5ec69198 files deleted), the board
was reported flashed with the ÷2 image and baseline netprobes taken, and a
mod document (CLKIN level-shift sizing against the datasheet) was being
written. Resume from `git status`: review those edits as your own, finish
the mod document, commit, and continue the 08:45Z addendum plan.

**HUB ADDENDUM 2026-08-21 08:45Z — datasheet now in hand (PW).** Files:
`~/db/_mx/_temp/adsp-2156x-docs/adsp-21560-21561-21564-21568.pdf` (Rev. A,
Feb 2026) + the 21564-specific HRM, EE-461 and the anomaly list, same
folder. mx26 errata DSP4 section updated (mx26 3371173). Two CONFIRMED
clock faults, which change TASK A:
1. fCKIN = 20–30 MHz (Table 23, crystal and external alike) — the ÷2 is
   right; finish step 1 (RTL/SDC/tb/build/commit).
2. **SYS_CLKIN0 is a VDD_INT-domain pin.** Abs max SYS_CLKIN0 input =
   –0.3 V to VDD_INT (Table 19); VIHCLKIN max = VDD_INT, VILCLKIN max
   +0.12 V; "must not exceed the internal (VDD_INT) voltage level". The
   CPLD drives it at 3.3 V through 22R → both SHARCs overdriven since
   first power-up; the pin clamp pumps the +0.9 V rail; parts may be
   damaged.
So: do NOT flash + retest expecting a verdict. Instead (a) commit the ÷2
build; (b) size a proto level-shift at R65/R33 to a ~0.8 V swing at pin 5
(e.g. ~560R series + ~180R shunt on the DSP side; check RC against the
24.576 MHz edges and the CPLD drive) and write it as a RED mod for PW to
fit, plus the scope checklist (first: +0.9 V sane with the card fitted,
clamping at pin 5); (c) downgrade TRST (internal pull-down per the signal
table), note BMODE2 internal PD and SYS_FAULT open-drain (external pull-up
if used). Record in this block + the decisions doc; when the desk work is
done mark the block 🔴 blocked on PW hands (bodge); push.

Constraints: chips may be freely booted/reset; ALWAYS restart matrix-app
and confirm the three MCUs verify before ending the session or between
long gaps; Dropbox via ~/db. The rev C unit is yours (no other machine
dispatched to it). Single trunk; update the dispatch block status; no AI
attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

### Outcome 2026-08-21 — what was done

**TASK A step 1 — done and committed (a4ee3d1).** `dsp_clk` is now a
dedicated toggle flop off sysclk: 24.576 MHz, exact 50 % duty (datasheet
asks 45-55 %), glitch-free by construction, `preserve`d so the
synthesiser cannot merge it into the heartbeat counter's carry chain and
put the DSPs' only clock on an LE mid-chain. SDC gains a
`create_generated_clock` (with a comment recording why Quartus warning
332088 is benign here — nothing inside the CPLD is clocked by dsp_clk).
`tb_logic_top` now checks period = 2 sysclk and high = 1 sysclk instead
of pass-through equality. Build: fitter clean, timing met, **157/1270 LE
(+1 for the flop)**, fmax 70.21 MHz, sim gate PASS, bitstream
`dsp4_logic.a1f6672af6c3` (source hash recomputed and matched before
committing).

**TASK A step 2 — done, verified on the card.** Programmed over the CM4
JTAG bit-bang path: IDCODE `0x020a30dd` before and after, **40779 SVF
commands, 0 errors, 58 s**. `dsp4_netprobe.py` after the flash: PCM_CLK
(GPIO18) and PCM_FS (GPIO19) still TOGGLING, every other net reads
exactly as it did on 08-20 — the rest of the CPLD is unaffected.
matrix-app restarted; **all three MCUs verify** (H1S1 "// H1S1 DSP",
H1S3 SW Right, H1S4 SW Left).

**TASK A steps 3-5 — deliberately NOT run.** Per the 08:45Z addendum a
retest cannot produce a verdict while the second fault stands, and each
boot attempt is more powered time on an overdriven pin. The scope
checklist replaces them.

**The second fault, sized and written up (the 08:45Z addendum's (b)).**
`SYS_CLKIN0` is the one signal pin in the **VDD_INT** domain: Table 7
(power domains), Table 13 (designer quick reference), Table 19 (abs max
= −0.3 V to VDD_INT), operating conditions (VIHCLKIN 0.68 V…VDD_INT,
VILCLKIN ≤ +0.12 V, VDD_INT 0.855/0.900/0.945 V), and the crystal
section's flat statement that the external clock "must not exceed the
internal (VDD_INT) voltage level". Rev C drives it at 3.3 V through 22 R
— R65 → DSPA U6 p5, R33 → DSPB U5 p5, both confirmed off the schematic
at 400 DPI, along with DSP_CLK on CPLD pin 140 in a **+3V3** bank
(VCCIO2_1/2_2 both on +3V3, so the swing really is 3.3 V). Through 22 R
the clamp demand is ~80 mA per part against a 6 mA per-pin absolute
maximum, injected into the +0.9 V core rail, continuously since March.

**Mod written: `TransferOnly/PCB mods/dsp4-revC-clkin-bodge.md`** (RED,
awaiting PW). Per DSP: R65/R33 22 R → **1k2**, plus a new **390 R** to
GND at the DSP-side pad. Ratio 0.245 → ~0.77 V high against a 0.68-0.855 V
window; ~2 mA per DSP (4 mA total on CPLD pin 140) instead of the ~160 mA
the two clamps are asking for now; Thevenin 294 R into ~7 pF → ~4.6 ns
edges on a 40.7 ns period, so tCKINH/L stay far above the 16.67 ns
minimum. Includes a trim ladder (360/390/430 R), the physical fitting
notes, and the **bench scope checklist** — ordered, with expected values:
+0.9 V rail first (a high reading means the clamps are pumping it), then
the clamped ~1.2-1.6 V clock at R65/R33 as direct confirmation of the
fault, then post-mod acceptance (0.70-0.82 V high, ≤0.10 V low,
24.576 MHz), then the boot retest with SPI2 CLK/MOSI at R52/R51 and
HWRST at p104. Failure branch spelled out: clean clock + good rail +
visible SPI traffic and still no RDY ⇒ the parts themselves, and the
JTAG-bodge / replace decision is PW's (there is no DSP JTAG on the card).

**TASK B — done.** New binding decision **D10** in
`dsp4-architecture-decisions.md`: the CPLD is the single DSP clock
source, 24.576 MHz is the contract, fCKIN must stay inside 20-30 MHz,
SYS_CLKIN0 must be level-translated to 0.68-0.855 V on any DSP4-derived
board, and the per-DSP-crystal alternative is explicitly rejected (it
would give up the programmable single source). `hardware-map.md` §3
records the R65/R33 topology and both faults. Rev-D list gains **mods
8-13**: the clock chain (mod 8, RED), RDY pulls → pull-ups, `!RST_D`
dual master (Pi GPIO16 + U7 p47 = PA13/SWDIO), a DSP JTAG header,
RESOUT/SYS_FAULT liveness (FAULT is open-drain, external pull-up
required), and test points. **Mod 7 (JTG_TRST) is downgraded to no
action**: Table 13 gives JTG_TRST an internal **pull-down** (TDI/TMS/TCK
have internal pull-ups), so floating TRST holds the TAP safely in reset.
SYS_BMODE2's internal pull-down is recorded with it. The datasheet gap is
closed — all `[verify]` tags on fCKIN and the CLKIN levels are now
answered from `adsp-21560-21561-21564-21568.pdf` Rev. A.

**Blocked on:** PW fitting the four resistors and running the scope
checklist. Everything after that is desk work over SSH.

**Note for PW:** the card is still being overdriven whenever it is
powered. The bodge doc says it plainly — keep powered time short until
the divider is fitted. matrix-app is running now because the dispatch
constraint requires the unit left verifying, not frozen.

## HUB DISPATCH 2026-08-20 18:43Z — Boot handoff investigation — apps never execute   [status: 🔴 blocked]

ROOT QUESTION: SHARC boot streams are fully consumed by the ROM (per-chunk
RDY back-pressure works end-to-end with the fixed active-low tool) but
APPLICATION CODE NEVER EXECUTES — proven tonight with a closed loop:
`src/blink/rdyprobe.asm` (blink.asm with PORTA→PORTB, bit 5 = PB_05 =
SPI2_RDY) booted on chip 1 and the Pi sampled GPIO8 flat low; the PA_12
blink images also never light LD2/LD3 (PW verified LED wiring anode→R→
PA_12, cathode→GND: pin-high = lit). All dma_cfg_init work is downstream
of this and moot until fixed.

Find why the ROM→application handoff fails. Investigate at the desk, then
verify with the closed loop (no bench eyes needed).

Suspects, in order:
1. Boot-stream format: elfloader flags are `-b SPI -bcode 1 -f BINARY
   -width 8`. Check HRM ch.40 (text already extracted to hrm.txt in your
   scratchpad from the previous session — regenerate if gone) for the
   BLOCK CODE / BCODE the 2156x ROM expects in SPI SLAVE boot (BMODE
   0b010), and whether -b SPI + bcode 1 encodes master vs slave. Parse
   the actual bytes of build/rdyprobe1.ldr (block headers: dBlockCode,
   dTargetAddress, dByteCount, dArgument; FIRST/FINAL/INIT flags) and
   check: final block flags, jump target address, and whether the ROM
   requires anything the stream lacks.
2. Entry/IVT: the .dxe has NO ELF entry (elfloader "Defaulting to
   0x90004"). Verify in the built blink/rdyprobe images that address
   0x90004 (RSTI slot) actually receives a jump to _start (dump the dxe:
   elfdump, or parse the .ldr payload for the 0x90000-block content).
   Check blink_ivt.asm places the IVT at 0x90000 and the LDF puts
   seg_pmco somewhere the ROM actually loads.
3. Post-boot core state: does the 2156x ROM hand off with the core in a
   state our code mishandles (e.g. executes from an address alias we
   didn't link for)? Compare with an ADI example loader stream if any
   ships in CCES (look under /opt/analog/cces/3.0.3/SHARC/ldr or
   examples) — diff their header/entry conventions against ours.
4. If a stream fix is identified: apply to build.sh loader() (and
   dsp4_boot.py only if the transport itself must change), rebuild
   rdyprobe1.ldr, and VERIFY with the loop below. Iterate until GPIO8
   toggles.

CLOSED-LOOP VERIFICATION (run as often as needed):
  ssh app@192.168.1.219 'cd /home/app/dspboot && python3 dsp4_boot.py \
    --ldr rdyprobe1.ldr --chip 1' \
  && ssh app@192.168.1.219 'for i in $(seq 1 12); do pinctrl get 8 | \
    grep -oE "lo|hi"; sleep 0.25; done'
Success = alternating lo/hi (~1 Hz). Copy fresh rdyprobe1.ldr to
/home/app/dspboot/ before each run. rdyprobe.asm is untracked — commit it
(it is now a permanent bring-up tool) with a header comment.

After GPIO8 toggles: boot blink1/blink2 and note in tasks.md that PW
should confirm LD3/LD2 blink at next bench visit (1 Hz / 2 Hz — also the
free CCLK measurement); then the production/park builds become meaningful
again and P2.2 resumes with working instruments.

Constraints: chips may be freely booted/reset (PW has released the
bench; the bisect state is void anyway). ALWAYS restart matrix-app
(sudo systemctl restart matrix-app) and confirm the three MCUs verify in
/home/app/logs/log before ending the session or between long gaps —
the unit must not be left on a frozen splash. Dropbox via ~/db. Single
trunk; update the dispatch block status; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

**Outcome 2026-08-20 20:20Z — 🔴 NOT FIXED. GPIO8 is still flat low after
every variant tried, so the handoff still fails. But the suspect list is
now much shorter: the boot stream and the toolchain flags are CLEARED with
evidence, two genuine defects in the boot host were found and fixed, and
the one assumption everything rested on — that the parts were receiving —
turns out to have no supporting evidence at all. Unit restored, all three
MCUs verify, app running.**

### The closed loop, run many times — always flat

`rdyprobe1.ldr` booted on chip 1 and GPIO8 sampled, across the full cross
product of SPI mode {0, 1} × post-reset settle {0.05 s, 0.5 s, 2.0 s}:
`lo` on every sample of every run. Nothing tried tonight moved it.

### Suspect 1 (boot-stream format) — CLEARED, with the bytes

Every block of `rdyprobe1.ldr`, `blink1.ldr` and the 207 KB production
`chip1.ldr` was parsed field by field against HRM ch.40 Fig. 40-15 /
Table 40-27. The streams are textbook:

- Headers are 16 B: BLOCK CODE / TARGET ADDRESS / BYTE COUNT / ARGUMENT.
  HDRSIGN = 0xAD (core 0) on every block; the HDRCHK XOR checksum was
  recomputed and matches on every block; `chip1.ldr` parses cleanly
  through 608 blocks and lands exactly on EOF (0x32814 = file length).
- First block = `BFLAG_FIRST|BFLAG_IGNORE`, count 0, TARGET_ADDRESS
  **0x00090004** (the RSTI slot — the entry point the kernel writes to
  RCU_SVECT0 at termination), ARGUMENT = offset of the final block.
  Final block = `BFLAG_FINAL`, count 0, same target. Both correct.
- The IVT **is** in the stream: a 48-byte payload block (8 NW slots × 6
  bytes) to 0x28240000. That address is right: NW 0x00090000 ↔ BW
  0x00240000, 6 bytes per 48-bit word, which is exactly why the stock
  CCES `ADSP-21564.ldf` starts `mem_block0_bw` at 0x002403F0 (0xA8 words
  × 6). Slot 1 (RSTI, word index 4) decodes as `jump 0x1C0000` — the SW
  address of `_start` at BW 0x380000. `BFLAG_AUX` is correctly absent:
  elfloader already emits byte-space addresses, so no PM translation is
  wanted.
- `-b SPI` vs `-b SPIHOST`: elfloader 6.4.2.1 emits **byte-identical**
  output for both (checked on blink1). `build.sh` now says `SPIHOST`
  anyway, because `-b SPI` documents the master/flash case and this is
  the host-push case. `-bcode 1` is right — HRM Table 40-19 gives
  SPIS_BCODE `00xx` = single-bit SPI bus, and 1 is in that range. (The
  BCODE nibble is also the first byte of the stream, which is what
  Table 40-18's SPICMD auto-detect reads.)

Nothing in the image explains the failure.

### Suspect 2/3 (entry, board straps, clock) — CLEARED off the schematic

Read at 1200 DPI from `D24 DSP.pdf` p5/10 (DSPA, U6):

- `SYS_BMODE0` = **pin 105 → GND**, `SYS_BMODE1` = **pin 106 → VDD_EXT**,
  `SYS_BMODE2` = **pin 82 → GND**. BMODE[2:0] = 0b010 = SPI Slave Boot
  (HRM Table 40-14). The strap is right. (`SYS_RESOUT` p107 is NC, so
  there is no reset-done signal to watch.)
- `SYS_CLKIN0` = pin 5, fed from **DSP_CLK through R65 (22R)**.
- `SPI2_RDY` → **PB_05** through R38 (22R), with R34 10K to GND —
  confirming what `rdyprobe.asm` drives is the right pin.
- SPI2 on DSPA: MISO→PA_00, MOSI→PA_01, CLK→PA_04, SS→PA_05.
- The S MCU (U7, p3/10) housekeeping SPI is on **ISPI0/1/2**, which are
  DIFFERENT nets from the Pi's SPI0/1/2 — so H1S1 is not a second master
  on the boot bus. It *is* a second driver on `!RST_D` (U7 pin 47).

**The LOGIC CPLD is alive and clocking.** LOGIC masters the Pi PCM port,
and `PCM_CLK` (GPIO18) / `PCM_FS` (GPIO19) read as TOGGLING at the Pi.
`dsp_clk` is a pass-through of the same `sysclk` that feeds the clkgen,
so the "unprogrammed CPLD = no DSP clock" theory is dead as stated.
`!RST_D` really does go low when the Pi drives it (verified by reading
the net back).

### TWO REAL DEFECTS FOUND AND FIXED in `dsp4_boot.py`

1. **SPI clock mode was 0; the boot kernel uses mode 1.** HRM ch.40:
   "In SPI slave boot mode, the boot kernel sets the SPI_CTL.CPHA bit and
   clears the SPI_CTL.CPOL bit", and ch.15 fixes the numbering —
   "mode-0 (CPHA=CPOL=0) and mode-3 (CPHA=CPOL=1)" — so CPHA=1/CPOL=0 is
   **mode 1**: MOSI is latched on the FALLING edge. A mode-0 host changes
   MOSI on exactly the edge the kernel samples. Now `SPI_MODE = 1`, with
   `--spi-mode` as an escape hatch. (The RUNTIME link is a separate
   question and correctly stays mode 0 — `spi2_init()` leaves CPOL and
   CPHA clear, matching `dsp4_diag.py`.)
2. **No settle time after reset release.** HRM Fig. 40-7 does not use a
   timer: the host waits for SPI_RDY DEASSERTED then ASSERTED, which is
   the kernel saying "SPI2 is up". That handshake does not exist on this
   card (pull-downs, see below), so the host was clocking bytes
   microseconds after `!RST_D` released, while the part was still in
   pre-boot. Now `POST_RESET_S = 0.500`, `--post-reset-delay` to override.

Both are real bugs by the manual. Neither, alone or together, made GPIO8
move — so there is at least one more cause.

### The finding that matters most: "the stream was consumed" was never evidence

New tool **`tools/pi/dsp4_netprobe.py`** asks the only question that
discriminates on a bus like this one: make the Pi pin an input, select the
internal pull-up, read; select the internal pull-down, read. Follows both
= nothing else drives it. Result:

| net | Pi | verdict |
|---|---|---|
| SCK | GPIO11 | HELD HIGH by something stronger than the Pi pull |
| MOSI | GPIO10 | HELD HIGH by something stronger than the Pi pull |
| MISO | GPIO9 | floats |
| CS1 / CS2 | GPIO6 / GPIO24 | floats (the H1S1 CS1-6 fix holds) |
| RDY1 / RDY2 | GPIO8 / GPIO12 | HELD LOW (R34 / R22, as designed) |
| !RST_D | GPIO16 | HELD HIGH (H1S1 U7 p47 also drives it) |
| PCM_CLK / PCM_FS | GPIO18 / GPIO19 | TOGGLING — the CPLD is running |

And a `!RST_D` pulse with **no SPI traffic at all**, sampling SPI_RDY every
~15 µs for 1 s: not one HIGH, on either chip, on any run. A 64 KB blast of
deliberate garbage at 20 MHz with no flow control: also not one sustained
HIGH — and a kernel that rejects a bad header should stop draining and let
the RX FIFO fill within ~32 bytes.

Because the card's pulls rest SPI_RDY ASSERTED, "every chunk was accepted"
is what a *dead* part looks like too. **There is currently no positive
evidence that either SHARC has ever received a single byte.** Every prior
"the stream was consumed" reading is compatible with the parts never
having listened. That is the honest state of the investigation.

### Committed alongside

- `src/blink/rdyprobe.asm` — now a permanent bring-up tool with a proper
  header, plus a `./build.sh rdyprobe` target. `blink()` and `rdyprobe()`
  are one parameterised `tiny_image()`; `blink1.ldr` is byte-identical
  after the refactor, checked.
- `LDRFLAGS` is now defined once and shared by `loader()` and
  `tiny_image()`.
- `tools/pi/dsp4_netprobe.py` (above), deployed to `/home/app/dspboot/`.

### Next — in this order

1. **Prove or disprove that a SHARC is receiving.** Everything else is
   guesswork until this is settled, and it needs a scope at the part:
   SYS_CLKIN0 (p5) for DSP_CLK actually arriving, then PA_04/PA_01
   (SPI2 CLK/MOSI) during a boot, then SYS_HWRST (p104). One session with
   a probe answers what a week of desk work cannot.
2. ~~The one board assumption still unverified~~ **VERIFIED 2026-08-20
   (hub): PA_00=SPI2_MISO, PA_01=SPI2_MOSI, PA_04=SPI2_CLK,
   PA_05=SPI2_SEL1/SS, PB_05=SPI2_RDY — from ADI's own pinmux data:**
   `ADSP-21564-pinmux.xml` inside CCES
   `Eclipse/plugins/com.analog.crosscore.addins.pinmux_*.jar`
   (extracted to /tmp/pinmuxjar on this machine; the jar is the local
   authoritative pin-function source — datasheet fetch no longer
   blocks anything). Schematic net names correct on every SPI2 pin;
   rdyprobe drives the right pin. Suspect list for the scope session
   accordingly narrows to the physical layer: VDD_INT (+0.9 V core
   rail) actually present at the card, SYS_CLKIN0 actually clocking,
   SYS_HWRST behavior, then PA_04/PA_01 during a boot. The HRM has no pin-function table
   (it is in the datasheet, which is not in `_mx/_temp/adsp-2156x-docs` —
   only `adsp-2156x_hwr.pdf`), and analog.com times out on fetch. If the
   two are the other way round the parts have never seen MOSI. **Get
   `adsp-21560-21561-21564-21568.pdf` into the Dropbox docs folder and
   check PORTA against p5/10.**
3. Rev-D hardware items, both from tonight: R34/R22 want to be pull-UPs
   (already logged 17:16Z; tonight shows exactly what it costs — no
   liveness signal at all); and `!RST_D` has two masters (Pi GPIO16 and
   H1S1 U7 p47) with no arbitration.
4. Left in the working tree, NOT committed, from an earlier session: a
   `DSP4_BISECT == 4` park in `src/dma_config.c` (its `#error` guard text
   still says 0-3). It is out of scope for this dispatch — finish or drop
   it deliberately.

## HUB DISPATCH 2026-08-20 17:16Z — P2.2 fix flash + readback verification   [status: 🔴 blocked]

**Outcome 2026-08-20 18:30Z — production images built and BOOTED into both
SHARCs (a first: with real flow control), but the readback verdict is FAIL
— both chips still echo all-zero, so P2.2 is NOT verified. Separate and
bigger find on the way there: `dsp4_boot.py` had the SPI_RDY polarity
INVERTED, and every boot before today only worked because H1S1 was
driving the shared CS3/CS4 nets high. Fixed and proven. Unit restored,
all three MCUs verify, app running.**

### What was done

1. **Build.** `DSP4_BISECT=0 ./build.sh all` — production, 0 errors.
   Confirmed the scaffolding really is compiled out: `elfdump -sym` on
   `build/chip{1,2}/dma_config.doj` shows no `_diag_stage_set` reference
   on either chip. Artifacts `chip1.b4090de01d5d.ldr` (207108 B) +
   `chip2.bb2b24db8617.ldr` (108172 B), hash-named, `ldr/manifest.txt`
   updated with the superseded pair recorded.
2. **Deploy.** scp'd to `app@192.168.1.219:/home/app/dspboot/`, sha256
   re-verified on the unit. matrix-app stopped, `S_RESET` (`*`) sent
   twice at 115200 8N1 on `/dev/serial0` with 2 s between, matching
   `Boot.FlashFirmwareViaSerial`.
3. **Boot — failed, then root-caused, then succeeded.** See below.
4. **Readback — FAIL.** See "The readback verdict".
5. **Restore.** matrix-app restarted; `MCU verified: // H1S4 SW Left`,
   `// H1S1 DSP`, `// H1S3 SW Right` and `Boot.Loop() - MCU boot
   verified: H1S1 / H1S3 / H1S4` at 18:30:31-37Z. Unit left whole with
   the production images loaded in both DSPs.

### THE BOOT-TOOL BUG — SPI_RDY polarity was inverted (fixed)

First boot attempt failed on BOTH of the tool's attempts, chip 1, before
a single byte: `SPI_RDY never asserted within 2.0s`. GPIO state read at
the time: `!RST_D` (GPIO16) = 1 (released), CS1 (GPIO6) = 1, **both RDY
lines low** — chip1 GPIO8 = 0, chip2 GPIO12 = 0.

- **The tool waited for HIGH.** Its docstring reasoned from the board's
  10K pulldowns (R34 DSPA / R22 DSPB) that asserted must be high.
- **The HRM says the opposite for boot.** Ch.40, SPI Slave Boot Mode:
  "In SPI slave boot mode, SPIx_RDY functionality is critical. The
  SPIx_RDY output is used for back pressure and requires a pulling
  resistor. **The boot code requires the SPIx_RDY signal function as
  active-low.**" The polarity during boot is the on-chip boot kernel's
  and is not configurable. Asserted = 0. Both parts were sitting there
  ready and the tool was waiting for the one level that never comes.
- **Why it only broke today.** CS3/CS4 are SHARED nets — Pi RDY inputs
  AND H1S1's "DSP 1/2 chip SPI_RDY" monitors (`MW/D24/HW/hardware-map.md`
  §3a). Until the 2026-08-20 17:17Z reflash, H1S1 drove CS1-6 push-pull
  HIGH, so the Pi always read 1 and **every RDY wait in every boot to
  date passed vacuously — all previous boots ran with no flow control at
  all.** Making CS1-6 inputs exposed the real line. The CS1-6-inputs
  change is correct and stays; it just uncovered this.
- **This also explains the "first attempt always fails, retry works"
  quirk** (reproduced ×3, 2026-08-19/20) — a timing race against a line
  nobody was reading correctly. With the polarity fixed, both chips
  booted on **attempt 1/2**, no retry.
- **Fix** (`tools/pi/dsp4_boot.py`): `wait_ready()` now takes
  `active_low`, defaulting to `RDY_ACTIVE_LOW = True` with the HRM
  citation; `--rdy-active-high` is an escape hatch, not a normal option.
  Threaded through `boot_chip`/`boot_chip_retrying`; module docstring
  corrected; the timeout message now names the expected level and points
  at the shared-net cause. Exercised off-target (asserted/stuck/timeout
  in both polarities) plus `--dry-run`; deployed to `/home/app/dspboot/`,
  md5 matches the repo copy.
- **Result:** `chip 1: attempt 1/2 OK — 207872 bytes sent on CS1`,
  `chip 2: attempt 1/2 OK — 108544 bytes sent on CS2`.

**HARDWARE ITEM for rev D — R34/R22 are the wrong way round.** The HRM
wants the pull to hold the line DEASSERTED while the part is in reset
("allows the processor to hold off the host while the processor is in
reset"). With boot fixed active-low, a pull-DOWN rests the line
ASSERTED, so the hold-off does not exist on this card and no host-side
wait can prove a part is alive or out of reset. Back pressure mid-stream
still works (the DSP drives the pin push-pull to deassert). Changing
R34/R22 to pull-UPS restores the hold-off — and would then also flip the
runtime `SPI_CTL.FCPL` to 0. Until that happens boot and runtime
legitimately disagree on polarity: `dsp4_boot.py` active-low,
`dsp4_diag.py`/`dsp4_config.py` active-high. Noted in `dma_config.c`
beside the `FCPL` write.

### The readback verdict — FAIL, and it cannot localise the fault

Against BOTH chips (`--cs-gpio 6 --rdy-gpio 8` / `--cs-gpio 24
--rdy-gpio 12`):

- With the runtime RDY gate honoured: `SPI_RDY never asserted` — SPI2 is
  never configured, so the pin is never driven and the pulldown holds it
  at 0.
- With the gate bypassed (`--rdy-active-low --resync`, which makes the
  resting-low line read as asserted so the transaction goes out):
  `response out of step reading 0xE000: echo 0x00000000, expected
  0xE0002000` — **all-zero echo, identical to the pre-fix symptom.**
- MAGIC / CHIP_ID / BOOT_STAGE / TICKS: none obtainable. No acceptance
  criterion from the dispatch was met.

**Why this is not evidence against the P2.2 fix.** `spi2_init()` runs at
DIAG_STAGE(5), *after* `arm_region(A)`, `arm_region(B)` and `sec_init()`
— i.e. the diagnostic link comes up downstream of the entire suspect
region. An all-zero readback therefore means "did not reach stage 5" and
says nothing about WHERE. It reads the same whether the part still dies
on lane index 4 of region A or now dies somewhere new. The SPI readback
was never able to bisect this; **LD2/LD3 is the only instrument that
can, and that needs bench eyes.**

**The addressing fix itself re-verified at desk level** against
`/opt/analog/cces/3.0.3/SHARC/include/sys/ADSP-21564.h`:
`REG_DMA10_DSCPTR_NXT = 0x31023000`, `REG_DMA17_DSCPTR_NXT = 0x31023380`,
`REG_DMA7_DSCPTR_NXT = 0x31022380`, and DMA8/DMA9 (MDMA0) sit off at
0x310A7000/0x310A7080. `sport_dma_base()` reproduces all of these
exactly. The fix is right; it was simply not sufficient on its own, or
the remaining fault is elsewhere.

### Next at the bench (PW, LD2 needed)

1. `DSP4_BISECT=1 ./build.sh` (park after `arm_region(A)`) and boot chip 1
   with the **fixed** boot tool. Steady 1 Hz square on LD2 = the SPORT4-7
   base fix closed the region-A wedge and the remaining fault is
   downstream; slow single blink = region A still dies and there is a
   second cause in `arm_region`.
2. Then `DSP4_BISECT=2` (park after `arm_region(B)`), then `=3`
   (EN-last) if A is implicated again.
3. Item 3 (clear the bisect scaffolding) stays BLOCKED — the scaffolding
   is now the only working instrument. Item 4 (`dsp4_config.py`, stage
   5→6) stays blocked behind a stage-5 readback.

### Deviation from the dispatch, declared

The dispatch's step 5 said one boot retry maximum and then mark 🔴. The
first boot failure was diagnosed to a tool bug with a documented HRM
citation rather than retried blind, the tool was fixed, and the boot was
run once more — which is what got both images loaded at all. The
readback that followed is the honest verdict and is reported as FAIL.
No CPLD or MCU was flashed; only the DSPs, `/home/app/dspboot`, and the
app stop/start were touched.


Flash the P2.2 wedge fix and verify by SPI readback — no bench eyes
available; the diag readback IS the verdict. PW has waived the
before-datapoint LD2 read; chip1's parked bisect state may be discarded.

Context: root cause fixed in fff7506 (sport_dma_base — SPORT4-7 at
0x31023000). Chip1 currently runs the round-1 park build, chip2 the
l1_to_sys-only build (both hung, harmless). Unit app is running with the
new H1S1 build; H1S1 proven not to drive !RST_D. dsp4_boot.py now has
the auto-retry. Dropbox via ~/db only.

Sequence:
1. Pull main. Build BOTH chips with **DSP4_BISECT=0** (production — no
   park, no stamps; note the current default is 1). `./build.sh all`,
   commit the .ldr pair hash-named per the artifact convention.
2. scp the .ldr pair to app@192.168.1.219:/home/app/dspboot/. Stop
   matrix-app, S_RESET '*' (hold slaves), run dsp4_boot.py for both
   chips (its auto-retry covers the hung-state first-attempt quirk).
3. Verify via dsp4_diag.py against EACH chip. Acceptance:
   - MAGIC correct, CHIP_ID = 1 and 2 on the right chips (proves CS
     routing), echo protocol passing (no all-zero echoes).
   - BOOT_STAGE = 5 (waiting for host product config) on both.
   - TICKS advancing between two reads (core alive), no unexpected
     ISSUES from the tool.
4. On PASS: restart matrix-app, confirm the three MCUs still verify,
   leave the unit whole. Update tasks.md: P2.2 marked VERIFIED ON
   HARDWARE with the readback evidence; note that item 3 (clear bisect
   scaffolding) is now unblocked and item 4 (dsp4_config.py, stage 5→6)
   is the next bench step. Commit + push.
5. On FAIL (readback still all-zero / stage < 5): do NOT thrash — one
   boot retry maximum beyond the tool's built-in retry; record exactly
   what the readback shows, restore matrix-app, mark the block 🔴 with
   findings; the staged LED bisect (DSP4_BISECT=1/2) resumes at PW's
   bench.

Constraints: touch ONLY the DSPs and /home/app/dspboot + app
stop/start — no CPLD flashing, no MCU flashing. Single trunk; update
this block's status; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

## HUB DISPATCH 2026-08-20 15:18Z — H1S1 aligned reflash + P2.2 prep (PW absent)   [status: 🟢 done]

**Outcome 2026-08-20 — both tasks done. TASK A: H1S1 reflashed with the
CS1-6-inputs build compiled against the RUNNING app generation
(`e80ccab5d6d8`); all three MCUs verify on reboot, DSPs untouched.
TASK B: boot-tool auto-retry + bisect variants B/C landed, and the HRM
desk-review FOUND THE P2.2 WEDGE — SPORT4-7 use DMA10-DMA17 at
0x31023000, not DMA8+ at 0x31022400; `2*sport+dir` off one base was
writing unpopulated MMR space. Fix applied (not flashed).**

### TASK A — H1S1 aligned reflash

- **Generation.** Built against `/home/app/fwbuild/matrix-aligned.h`
  (generated on-unit 2026-08-19 from `config/_matrix.mxc`, app build
  260714102659). `matrix_gen_id.py --compare` vs the unit's own
  decrypted matrix: **ALIGNED, full-id `e80ccab5d6d8`, 5412 cells,
  Sys001Skin001 = 5412**. Against mx26's baked
  `MatrixBus.Matrix.g.cs` it reports DRIFT of exactly one cell
  (`base-id 9b3c3d8f0286`): the g.cs predates `Sys001SwUpd001` (MxAdd
  6416, added on-device 2026-08-18) and still carries the dev-only
  `Aaa001Aaa001` placeholder, which shifts the `Zzz001Zzz001` sentinel
  6417 vs 6415. Hub confirmed the unit generation is the operative one.
  Immaterial either way for this image: **all four cells H1S1 actually
  compiles in are identical in both generations** — Sys001Enc001 5232,
  Sys001Skin001 5412, Sys001Test001 5414, Sys001Test002 5415 —
  confirmed in the linked ELF, `MATRIX[]` at `.rodata 0x080083b0` =
  {0, 5232, 5412, 5414, 5415}. The abandoned Dropbox-generation build
  had {0, 19479, 19727, 19730, 19731}.
- **Build.** `Debug/makefile.linux all` in the scratch copy
  `~/build-h1s1` (nothing written into Dropbox): exit 0, 0 errors,
  34036 text / 657 data / 1940 bss. 29 warnings, all pre-existing
  (`-Wpointer-sign` in DspTx/SpiTx/HAL_UART_Receive, three unused
  micGain* variables, CubeIDE `.cyclo` peer-target noise). Disassembly
  is byte-identical to the 2026-08-20 verified build except debug
  section sizes — the generation change lives in `.rodata`.
- **CS pins (acceptance 2).** All eight `GPIO_MODE_INPUT` in
  `H1S1.list`: CS5|CS2|CS7, CS8, and CS1|CS4|CS3|CS6(+BUSY,S3) groups
  each set `GPIO_InitStruct.Mode` to 0 in the disassembly.
- **Flash.** `hex2shex.py H1S1.hex H1S1` -> 2171 records / 34693 B
  image; previous pack image kept as
  `/home/app/fwbuild/pack-backup-H1S1.shex`. matrix-app stopped,
  S_RESET `*` on `/dev/serial0`, `app cli loadfw H1S1` -> MH1 loopback
  OK, S_SCAN found H1S1, all 2171 records ACKed, `// flash end of
  firmware record`, `OK: H1S1` (`logs/flash.log` 17:17-17:18Z).
- **Boot (acceptance 3).** matrix-app restarted and left running:
  `MCU verified: // H1S1 DSP`, `// H1S3 SW Right`, `// H1S4 SW Left`,
  then `Boot.Loop() - MCU boot verified: H1S1 / H1S3 / H1S4`. No new
  warnings — the only ones present are the 25 pre-existing SkinLoader
  "not in the matrix" notices (those cells are genuinely absent from
  the unit matrix, a skin<->matrix drift item, nothing to do with
  H1S1) and the pre-existing `mh1=?` build-stamp MISMATCH line.
- **DSPs untouched, as instructed.** No `dsp4_boot.py`, no `!RST_D`, no
  DSP reset. H1S1's own firmware never drives `!RST_D` — the only two
  writes to it in `main.c` are commented out and the pin is not in the
  `.ioc` — so the MCU reset during flashing did not reset either SHARC.
  Chip 1's bisect park should be intact for PW's LD2 read.
- **Flagged, not changed:** H1S1's blink handler still issues
  `DspTx(GPIOx, CSn_Pin, 0xF520, ...)` on SPI1 for all eight CS lines
  on every S_BLINK edge (ADAU-era LED writes, `matrix.cs` MainLoop).
  With CS1-6 now inputs it selects nothing, so this is strictly less
  intrusive than the build it replaced, but SPI1 SCK/MOSI still toggle
  on the housekeeping bus that carries the DSP CS provision. Deleting
  those dead calls belongs in the next H1S1 pass.

### TASK B — P2.2 prep

1. **`tools/pi/dsp4_boot.py` auto-retry.** `BOOT_ATTEMPTS = 2` with a
   `--attempts` override; every attempt is logged (`attempt n/m OK` /
   `attempt n/m FAILED`) so a part that needs the retry every time
   still says so. The retry restarts that chip's stream from byte 0 and
   deliberately does NOT re-pulse `!RST_D` (one reset line serves both
   DSPs). `Gpio` now releases and re-claims a line so the second
   attempt can re-request CS/RDY. Exercised off-target against a stub
   GPIO/SPI (fail-then-succeed and `--attempts 1` raise) plus
   `--dry-run`. Copied to `/home/app/dspboot/` so the next bench run
   picks it up (md5 matches the repo copy).
2. **Bisect round 2 ready to build, NOT flashed.** `DSP4_BISECT` in
   `dma_config.c`: 0 = production (no park, no stamps), 1 = round 1
   (default, park after `arm_region(A)`), 2 = **variant B** (park after
   `arm_region(B)`), 3 = **variant C** (write DSCPTR + CFG with
   `DMA_CFG.EN` clear, then set EN separately; parks after A so LD2
   answers the same question). `build.sh` passes it through:
   `DSP4_BISECT=2 ./build.sh`. All four values compile clean for both
   CHIP_IDs; an out-of-range value is a compile-time `#error`.
3. **HRM desk-review — root cause found (see the P2.2 note below).**
4. **`tools/pi/` sync.** `dsp4_config.py` pulled back from
   `/home/app/dspboot/` (the gpiod-v2 port) and committed verbatim;
   `dsp4_diag.py` and `dsp4_boot.py` were already byte-identical. Two
   rough edges in the ported `dsp4_config.py` left as-is so repo and
   unit stay identical, worth a tidy pass: the `if True:` block claims
   the RDY line unconditionally (crashes when `rdy_gpio is None` but
   `cs_gpio` is set), and the CS request is likewise unconditional.

Housekeeping: `~/mx26`'s `origin` was still HTTPS against a dead `gh`
token, so `git pull` there failed. Switched it to
`git@github.com:invirco/mx26.git` (same SSH key the dsp remote uses);
pulls work again and `tools/matrix_gen_id.py` is present.


Two tasks, PW absent — everything here is verifiable over SSH, no bench
eyes available. Unit access: app@192.168.1.219 (this machine's key works).
Dropbox via the space-free symlink ~/db ONLY. mx26 checkout at ~/mx26
(git pull it first; it has tools/matrix_gen_id.py and the app's baked
table src/sw/app/Core/MatrixBus.Matrix.g.cs).

**TASK A — reflash H1S1 with the CS1-6-inputs build (tasks.md NOW item 2).**
Correction to tasks.md first: it says H1S1 "has never been flashed" — STALE.
The hub flashed a matrix-aligned CS7/CS8-only build on 2026-08-19 night
(all three MCUs verify at boot since). What supersedes it is the CS1-6
build from the 2026-08-20 dispatch. Fix the tasks.md wording as part of
this task.

CRITICAL — matrix generation: the 2026-08-20 scratch build (~/build-h1s1)
compiled against the Dropbox MX/matrix.h generation (Sys001Skin001=19727),
which is NOT the running app's generation (5412). Do NOT flash that binary.
Rebuild against the running app's generation: the hub's 2026-08-19 flow
left an aligned header (matrix-aligned.h) on the unit or in its build area
— find it (check /home/app and the FW-home mechanics used that night), or
regenerate from the unit's own decrypted matrix as that flow did.
Verify alignment BEFORE flashing:
  python3 ~/mx26/tools/matrix_gen_id.py --compare <the matrix.h you built
  against> ~/mx26/src/sw/app/Core/MatrixBus.Matrix.g.cs
must print ALIGNED (base-id match).

Then: pack (H1S1.shex into the unit's firmware pack, same as 08-19) →
send S_RESET '*' on /dev/serial0 first (MH1 '?' responder is pre-loop
only) → `app cli loadfw H1S1` → confirm on reboot the app verifies
"// H1S1 DSP" AND both panels still verify.

Acceptance:
1. matrix_gen_id --compare says ALIGNED for the header actually compiled in.
2. H1S1.list of the flashed build: all eight CS pins GPIO_MODE_INPUT.
3. Boot log: H1S1 + SW Left + SW Right all verified, no new warnings.
4. tasks.md updated (item 2 done + the "never flashed" correction).

Constraints: do NOT touch the DSPs — no dsp4_boot.py, no !RST_D, no DSP
resets (chip1 carries the overnight bisect state; PW reads LD2 on return —
if the loadfw path unavoidably disturbs it, note that in the outcome, it
is re-establishable). Leave the unit with the app running.

**TASK B — P2.2 prep (desk work, no hardware contact with the DSPs).**
1. dsp4_boot.py: add auto-retry — a re-boot from a RUNNING/hung state
   fails its first attempt (SPI_RDY timeout) and works on the immediate
   retry (reproduced ×3). One automatic retry, log both attempts.
2. Prepare bisect round-2 as ready-to-build variants (guarded #ifdefs or
   committed patches — NOT flashed): variant B = park moved after
   arm_region(B); variant C = EN-write-order experiment (write DSCPTR +
   CFG with EN clear, then set EN separately).
3. HRM desk-review of the remaining dma_cfg_init suspects (DMA CFG EN
   write ordering, descriptor alignment, the lane-4/cs-mask special
   case) — findings appended to the P2.2 notes in tasks.md.
4. Sync the gpiod-v2-ported dsp4_config.py + dsp4_diag.py copies back
   from app@192.168.1.219:/home/app/dspboot/ into tools/pi/, commit.

Rules for both: work on main (pull first, push on completion); update this
dispatch block's status with a per-task outcome; no AI attribution.

Rules: single trunk — pull main first, commit + push main on completion;
update this block's status (🟢 done / 🔴 blocked) with a short outcome;
no AI attribution in commits or any work product.

# tasks — dsp spoke

Status: active · reprioritized 2026-08-20 (hub declutter — the full prior
text, day logs, and done-evidence live verbatim in
[archive/tasks-archive-2026-08-20.md](archive/tasks-archive-2026-08-20.md);
nothing was deleted).
Purpose: current work state for the mx26 → mx-dsp workflow and DSP4
firmware. This file is also the HUB DISPATCH queue (mx26 "machines"
model): the hub prepends dispatch blocks; sessions on this machine
execute them, commit, push `main`; the hub reviews on pull.

Trunk is `main` (`master` deleted + blocked). Mandates: `CLAUDE.md`.
Contract pin: **defs-v2026.08.20** (mx26 `345470a`; see `defs.lock` —
sync-from-mx26.sh now refuses an untagged mx26 HEAD).

## NOW — priority order (reordered 2026-08-21: SHARC BOOT SOLVED)

**MILESTONE 2026-08-21: both SHARCs boot and run application code.** Root
cause of the five-month boot-handoff failure was the boot host never
sending the **SPICMD byte** the SPI-target boot kernel reads as its first
byte (HRM ch.36 Table 36-18: 0x03 = keep single-bit); the ROM ate the
first `.ldr` byte as the command and every block header was misaligned by
one — which is why the 08-20 byte-by-byte stream audit found nothing (the
framing was right, the host was one byte early). `dsp4_boot.py --spi-cmd`
(default 0x03) fixes it; `--spi-cmd none` reproduces the flat-low failure
on demand. GPIO8 ~1 Hz on chip 1, GPIO12 ~2 Hz on chip 2, matrix-app up
(D14). **Parts were never damaged — no fresh card needed.** The clock
mods (÷2 + level-shift, D10) were real and are kept — an out-of-spec clock
had to be fixed regardless — but they were necessary, not the blocker.
Item 0 is DONE; the queue moves to P2.2 with working boot AND working LD2
blink as an instrument.

**MILESTONE 2026-08-21 (17:2xZ): chip 2's FULL FIRMWARE EXECUTES** — a
`DSP4_BISECT=5` park on `_start`'s first instruction fires 5/6. Two
independent faults were in the way and both are characterised in the
14:37Z dispatch outcome above: elfloader's ZERO-FILL blocks (fixed with
`-NoFillBlock` + a build-time guard) and U7/H1S1's ADAU poll on the
shared boot bus (mitigated with `dsp4_boot.py --sync-poll` at 10–11 MHz).
The ">8 KB block-size limit" is retired — it never existed.

**NEW NOW ITEM — zero the delay buffers in firmware startup.** With
`-NoFillBlock` every zero-initialised byte is clocked into the part for
real, so `sec_delay`/`sec_delay_ovf` (~1.7 MB) are now `NO_INIT` in the
LDF — otherwise chip 2 becomes a 1.9 MB, ~2.4 s stream that cannot
possibly boot. **Until firmware clears them at startup, the delay lines
come up holding whatever was in L2.** Owner: next SHARC dispatch.

**DONE 2026-08-21 — H1S1 reflashed, the boot bus has one master again.**
Its two SPI1 call sites (periodic `TestMicPres()`, and the CS1–CS8
`DspTx` LED writes) are removed and it was reflashed through MH1. The bus
measures 0 events in 15 s and **chip 1's full 258 KB firmware now boots
6/6 unsynced**. Full detail in the 14:37Z addendum above.

**NEW NOW ITEM — the `_sru_init` fault is the top SHARC item now.** With
both images loading reliably, the firmware hangs in `_sru_init`'s DAI0
half (the first SRU register writes). No loop in that function, so it is
a fault, not a spin. `dma_cfg_init` and the `sport_dma_base()` fix are
still untested — they are downstream of it.

**Context:** the rev-C card is LIVE on the fresh digital board — CPLD
`a1f6672af6c3` flashed 2026-08-21 (the ÷2 clock fix; supersedes
`fd6a5ec69198`), MH1/H1S3/H1S4 verify on every boot, H1S1 flashed
2026-08-19 (CS7/8 build) and reflashed 2026-08-20 with the CS1-6-inputs
build on the running app's matrix generation. This machine has direct SSH
to the unit (`app@192.168.1.219`) since 2026-08-20 — the hub-relay era is
over. **Correction to the previous context, which said "both SHARCs
slave-boot from the CM4": that was never evidenced** (2026-08-20
netprobe work) and the 2026-08-21 datasheet reading explains why — the
clock chain was wrong twice over (D10). Treat every pre-08-21 statement
about SHARC behaviour as unproven.

0. **SHARC testing — ✅ DONE 2026-08-21. Both parts boot and run.**
   Root cause = missing SPICMD byte (D14); fixed in `dsp4_boot.py
   --spi-cmd 0x03`. The clock two-part fault (D10) is also fixed and
   scope-verified on the card: ÷2 in the CPLD (`a1f6672af6c3`) + the
   level-shift bodge PW fitted (1k + 330R per DSP, mod BLUE on the mods
   PDF). Damaged-parts verdict WITHDRAWN. Two follow-ups fall out of it,
   now folded into the queue: (a) H1S1's legacy ADAU meter poll bursts on
   the shared !SPI1 net can corrupt boot DATA — near-term firmware fix
   (see item just below P2.2); (b) rev-D boot-bus owner. **PW confirmed 2026-08-21: both DSP blink LEDs visible at the
   expected rates — milestone closed visually (schematic map: LD3=DSPA/
   chip1 1 Hz, LD2=DSPB/chip2 2 Hz; LD1 is the CPLD LED, not a DSP).
   NOTE: on the rev C board these are SILKSCREENED D2/D1 = schematic
   LD2/LD3 respectively — refdes offset, don't re-confuse them.**

1. **P2.2 — REFRAMED 2026-08-21: there is no dma_cfg_init wedge. The
   full firmware has never executed an instruction on this card.**
   Parks inside `dma_cfg_init` AND a park on the first instruction of
   `_start` were all silent; only the ~1 KB blink/rdyprobe images have
   ever run. Root cause found and half-fixed: **the SPI target boot
   kernel cannot take a loader block larger than ~8 KB**, and every
   image so far was built with elfloader's default (one block per
   section). `-MaxBlockSize 0x1000` is now in `build.sh` LDRFLAGS —
   necessary, proven (0/10 → 4/4 on the same 8 KB DXE), NOT sufficient:
   the 208 KB image still does not run, so a second limit above ~8 KB
   is still uncharacterised. **Next step and full evidence: the
   2026-08-21 15:0xZ outcome at the top of this file.** Everything
   below this line is the 2026-08-20 desk review, kept because the
   `sport_dma_base()` fix in it is still correct — but it is UNTESTED
   on hardware and was never what hung, because nothing in
   `dma_config.c` has ever been reached.

   **(superseded framing, 2026-08-20 desk review)**
   - **The SPORT DMA channels are not one contiguous block, and the two
     blocks are not adjacent in the MMR map** (HRM Table 27-2 "ADSP-2156x
     DMA Channel List", Table 23-6, and `sys/ADSP-21564.h`):

     | half-SPORT | DMA channel | MMR base |
     |---|---|---|
     | SPORT0-3 A/B | DMA0-DMA7 | 0x31022000 + (2n+dir)·0x80 |
     | — | DMA8/DMA9 = MDMA0_SRC/DST | 0x310A7000 (different SCB node) |
     | SPORT4-7 A/B | DMA10-DMA17 | **0x31023000** + (2(n-4)+dir)·0x80 |

     `arm_region()` used `0x31022000 + (2*sport + dir)*0x80` for every
     lane, which is right only for SPORT0-3. From SPORT4 up it wrote
     0x31022400, 0x31022480, … — **unpopulated MMR space just past
     DMA7**. An SCB access there never completes, and the core stalls on
     its next MMR access: exactly the observed 1-flash hang. Chip 1's
     region A carries SPORT0-7, so it dies on lane index 4 (SPORT4)
     *inside* `arm_region(A)`, which is where the round-1 park says it
     dies. Chip 2 reaches SPORT4 in its region B (`c2_tx` lane index 4).
   - **Fix applied** (`dma_config.c`): `sport_dma_base(sport, dir)`
     picks the right base and half index; verified for all 16 half-SPORTs
     against the vendor header. Compiles clean for both CHIP_IDs.
     `dsp4-plumbing.md`'s DMA-channel-map bullet, which stated the wrong
     `2n`/`2n+1` rule, is corrected too. **Nothing has been flashed** —
     the DSPs were left untouched per the 2026-08-20 dispatch.
   - **FLASHED AND BOOTED 2026-08-20 18:2xZ** (hub dispatch 17:16Z, at the
     top of this file): production `DSP4_BISECT=0` images loaded into both
     SHARCs. **Readback still all-zero on both chips — P2.2 NOT verified.**
     The SPI diagnostic link comes up at DIAG_STAGE(5), downstream of the
     whole suspect region, so an all-zero echo cannot say where it dies;
     LD2 is the only instrument that can. The SPORT4-7 base fix itself was
     re-verified against `sys/ADSP-21564.h` and is correct.
   - **Next on the bench:** build (default `DSP4_BISECT=1` still parks
     after `arm_region(A)`) and boot chip 1. If LD2 now shows the steady
     1 Hz square, the wedge is closed — then `DSP4_BISECT=2` (park after
     B), then `DSP4_BISECT=0` for a full run. PW's LD2 read on the
     CURRENT image is still useful as a before/after datapoint but is no
     longer a gate.
   - Suspects cleared by the same review, for the record: **descriptor
     alignment** is fine — the HRM requires only 32-bit alignment for
     descriptor sets ("Descriptor Set Address Alignment"), `DMA_ADDRSTART`
     only needs MSIZE alignment (MSIZE04 = 4 bytes, and the buffers are
     `unsigned int` arrays), and the descriptor element order
     {DSCPTR_NXT, ADDRSTART, CFG, XCNT, XMOD} matches the MMR order at
     +0x00/04/08/0C/10 that NDSIZE=5 fetches. **DMA_CFG.EN write order**
     is already legal — `DMA_OFF_DSCPTR` (0x00) *is* `DMA_DSCPTR_NXT`,
     which is precisely what "Startup Minimum-Enable Requirements"
     requires be written before `DMA_CFG` for descriptor-LIST flow. The
     `DSP4_BISECT=3` variant keeps the EN-last experiment available
     anyway. **The lane-4/cs-mask special case** was the right instinct
     pointing at the wrong mechanism: lane index 4 is where it dies, but
     because that lane is SPORT4, not because `cs_mask = 0x000D` is
     non-contiguous.
   - Real fix already applied (KEEP): `arm_region` converts every
     DDE-visible address core-L1 → SYSTEM via inlined `l1_to_sys()`
     (+0x28000000 for 0x00240000..0x003FFFFF; ADI libcc math). The hang
     persists at sub-step ≤4 after it — SPI2 diag readback still all-zero
     echoes.
   - Temp instrumentation in the tree (REVERT when done): `diag_stage_set()`
     stamps 1..7 in `dma_cfg_init` + `_diag_stage_set` helper in
     `diag.asm` + the park loop — now all behind `DSP4_BISECT` (0 =
     production, no park and no stamps; see item 3). Chip 2 runs the
     fixed un-instrumented build (hung, harmless).
   - Flash/boot loop, all runnable from here now: build → scp `.ldr` to
     `app@192.168.1.219:/home/app/dspboot/` → S_RESET `*` on
     `/dev/serial0` (hold slaves; matrix-app stopped) → `dsp4_boot.py
     --dir /home/app/dspboot` → observe/readback → app restart.
   - Boot-tool quirk (re-boot from a RUNNING/hung state fails its first
     attempt on an SPI_RDY timeout and works on the immediate retry,
     ×3): **auto-retry added 2026-08-20** — `dsp4_boot.py` now takes two
     attempts per chip by default (`--attempts` to override), logs both,
     and never re-pulses `!RST_D` on the retry. **EXPLAINED 2026-08-20
     18:2xZ: the quirk was the inverted SPI_RDY polarity** (boot kernel is
     fixed active-LOW, HRM ch.40; the tool waited for HIGH and only ever
     "passed" because H1S1 drove the shared CS3/CS4 nets high until the
     CS1-6-inputs reflash). Polarity corrected; both chips now boot on
     attempt 1/2. The retry is kept — it costs nothing and keeps a part
     that genuinely needs it visible. Full write-up in the 17:16Z
     dispatch block, including the rev-D item: **R34/R22 are pull-DOWNS
     where the HRM's in-reset hold-off needs pull-UPS.**
   - Before any slave boot with H1S1 flashed: confirm !RST_D ownership
     (H1S1 PA13 = `!RST_D` vs the boot script's GPIO16 pulse). Checked
     2026-08-20: GPIO16 read 1 (released) throughout, and H1S1 does not
     drive the line — the Pi owns it in practice.

2. ~~**Flash H1S1.**~~ **DONE 2026-08-20** — full evidence in the
   dispatch outcome at the top of this file. Reflashed with the
   CS1-6-inputs build compiled against the running app's generation
   (`matrix-aligned.h`, full-id `e80ccab5d6d8`); all eight CS pins
   `GPIO_MODE_INPUT` in the disassembly; `app cli loadfw H1S1` clean;
   H1S1 + SW Left + SW Right all verify on reboot.
   **Correction to the earlier wording here: H1S1 had NOT "never been
   flashed"** — the hub flashed a matrix-aligned CS7/CS8-only build on
   2026-08-19 night (`logs/flash.log` ends 18:24Z, and all three MCUs
   have verified at every boot since). What the 2026-08-20 reflash
   superseded was that CS7/8-only image.
   Still open from this pass: H1S1's blink handler issues `DspTx(...)`
   SPI1 writes for CS1-8 every S_BLINK edge (dead ADAU-era LED writes —
   they select nothing now that CS1-6 are inputs, but they still clock
   the housekeeping bus). Delete them at the next H1S1 pass.

3. **Clear the bisect scaffolding in `dma_config.c`** once P2.2
   concludes — it is all behind `DSP4_BISECT` now (`DSP4_BISECT=0`
   already compiles the clean production path), so the deletion is
   mechanical: drop the `DSP4_BISECT` block, `DIAG_STAGE`, the parks,
   the `build.sh` passthrough, and `_diag_stage_set` in `diag.asm`.
   `bca0dde`'s deliberate `for(;;)` park + diag stamps go; the
   `l1_to_sys()` fix and the `sport_dma_base()` fix STAY. No image is
   shippable before this.

4. **dsp4_config.py — next tool up** once the wedge clears: expect LED
   stage 5 (waiting for host product config) → configure → stage 6 →
   audio → steady 1 Hz. Procedure + failure signatures:
   `MW/D32/DSP/diagnostics.md`. (Sync back from `/home/app/dspboot/`
   is DONE 2026-08-20 — `dsp4_config.py` was the only one that had
   drifted; see the dispatch outcome for the two rough edges in that
   gpiod-v2 port that are worth tidying when the tool is next used.)

5. **SPORT I/O pin check via CPLD feedback loop (PW 2026-08-20).** A
   loopback build of the LOGIC bitstream (STA-gated, hash-named, clearly
   NON-SHIPPING) routes SHARC SPORT outputs back to inputs so the DSPs
   self-verify EVERY SPORT pin/lane end-to-end: firmware counter-pattern
   generator + checker per lane, verdicts via the 0xE000 diag readback.
   Also closes the provisional TDM facts without a scope (BCKI/FSI pair
   order, CKRE/MFD, D24 within-ADC8 slot order) and settles the NI0-3/
   NO0-3 crossed-direction/reversed-index question against slot-map.csv.
   Gate: wedge fix verified on the bench + SPORTs configured (stage 6).

6. **Unified D24/D32 SPORT/TDM lane map (PW, decided 2026-08-20 — full
   detail + resolutions in mx26 tasks.md "decisions queue"):** rev C =
   converters 4×TDM8/direction as fabbed; rev D = 2×TDM16/direction via
   AK5558 cascade (TDM512 @48k/24.576 MHz, datasheet-verified; clkgen
   must pin BICK↓ vs MCLK↑ ±10 ns for cascaded slaves), freeing two
   lanes/direction; 1×TDM8 AK4619; Pi lane I2S→TDM8 with ADAU7302 MEMS
   injection at slots 5-6 (chip already strapped TDM8-slot-5, R42=47K);
   ONE TDM32 pair for the network role — OUT lane broadcast to USB +
   Dante simultaneously, IN lane single granted driver with enforced
   tri-state defaults (grant toggle = virtual soundcheck), D32 snake =
   the AES67 role on the same pair. Lands as tdm-lines.csv/slot-map
   revision + rev-D modlist entries. Open: 570Z scratch-fit for the
   freed pins/LEs; AK4458 slot-select check; D32_COMPAT legacy-box
   yes/no (PW). See also the D8 amendment (CM4 masters mic-pre gain;
   CS_M via spare CS5/6) in dsp4-architecture-decisions.md.

7. **Bench observations owed (PW):** LD1 ~1.5 Hz with the CPLD live;
   TEST1-4 on the scope (J15 DNP pads); blink-image rate = free CCLK
   measurement — write the measured rate down, don't just retune.

8. **Design note queued (PW 2026-08-19):** once RUNNING, the DSP diag
   LED and LOGIC LD1 should sync to the MH1 S_BLINK system heartbeat
   rather than free-run; diagnostic burst codes stay local.

## Blocked on PW (decisions, not work)

- **UART pass-through routing matrix** (`TODO(uart-passthrough)`):
  buffered pass-through vs selectable mux vs strobed arbiter. Pin
  inventory done; system decision needed before RTL. Audio bring-up
  only — not on the panel path.
- **D9 sign-off** (`dsp4-architecture-decisions.md`, [DRAFT] since
  2026-08-06): FPGA param plane — float wire, on-fabric ingest
  conversion, fixed ramps.
- **KR260 order** (SK-KR260-G; Farnell £323.57 vs ~$431 elsewhere,
  prices 2026-08-06). Procurement ONLY — the 2026-08-07 gate stands: no
  FPGA engineering until stable DSP+LOGIC on rev C. Capture order # +
  ETA here.
- **AI-attribution history question** — recommendation stands: LEAVE IT
  (59 pre-mandate commits keep trailers; rewriting means force-pushing
  new SHAs under ~15 cross-references). New commits carry none.

## Standing reference (condensed — full history in the archive)

**Lanes (2026-08-07 set):** (1) LOGIC CPLD — on hardware since 08-18;
unused-pin root cause fixed (`RESERVE_ALL_UNUSED_PINS` primary was unset
— every prior build ground-drove unused pins; trap documented in the
qsf), `fd6a5ec69198` flashed + regression-passed 08-19. (2) DSP firmware
— both SHARCs boot; six would-be-fatal bugs already found by HRM review
(IVT SEC vector, wrong SPI port, RUWM, EMISO, TXCTL, SEC ack); P2.2
wedge in progress. (3) FPGA — procurement only, gated.

**Card signs of life:** LD1 = LOGIC pin 59; LD3 = DSPA `PA_12`; LD2 =
DSPB `PA_12`; `PA_13` = shared `!BLINK` net (input — never drive).
TEST1-4 = CPLD pins 13/12/8/7 → J15 (DNP DIL254-10: pins 1/2 +3V3, odd
GND, even TEST1-4). LED fault codes: N flashes = completed stage N,
stuck in N+1 (1 SRU, 2 SPORT, 3 DMA, 4 int-enable, 5 waiting host
config, 6 configured/no audio); healthy = steady 1 Hz square. Diag
readback block at 0xE000 (24 regs + generic MMR peek window) via
`dsp4_diag.py` — the emulator substitute; every read carries an echo
word, checked host-side. SPI_RDY: chip1 GPIO8, chip2 GPIO12, FCPL=1
(ready = high; the 10K pulldown means in-reset reads not-ready). No
SHARC JTAG on rev C (JTG_* float; rev-D item — 2-pin SWD per chip is the
cheap option, ADI-tooling support unverified).

**Boot path:** CM4 SPI2 slave boot, BMODE 0b010; CS1/CS3 = DSPA, CS2/CS4
= DSPB (CS2 = GPIO24, NOT GPIO7); `!RST_D` = GPIO16 — ONE reset line for
BOTH DSPs (a reset re-boots both); 1024-byte units; spi0-0cs overlay (no
CE pins — GPIO7/8 stay JTAG TCK / CS3-RDY1). `dsp4_boot.py` = gpiod v2.
CM4 CPLD JTAG: TCK=GPIO7 TDO=22 TDI=23 TMS=25, IDCODE 0x020a30dd.

**Build:** `./build.sh all` in `MW/D32/DSP/SHARC/` (native 21564;
fit-proxy retired). Scratch copies need `cp -aL` — `Core/Inc/matrix.h`
is a symlink into `MX/` and plain `cp -a` leaves it dangling. H1S1/panel
MCU builds: Dropbox FW home via `Debug/makefile.linux` (CM4 or here);
access Dropbox through the space-free symlink `~/db` (escaped spaces
stall dispatched sessions).

**CCES licence (AD-CCES-NODE-1):** a node-locked activation COUNTER —
4 max, no customer-side release (ADI case CS-601771-T5L1J6); 1 of 4
spent on this box; a wipe or NIC change burns one permanently. Licence
material untracked in `cces-tools/` (gitignored); originals in Dropbox
`TransferOnly/`.

**Rev D:** single mod source = Dropbox
`TransferOnly/PCB mods/dsp4-revD-modlist.md` (D8 scope: CM4-core SPI
control; supervisor shrink → G0B1/U535; PSRAM on OSPI0 + runtime link to
SPI0/1; 5M570Z CPLD — PIN_8/TEST3 must move; hardwire-chunk pass;
OSPI = 3.3 V domain → S27KL-class HyperRAM or APS6404L). Rev-C bring-up
verifies the provisional TDM facts (BCKI/FSI pair order, CKRE/MFD, D24
within-ADC8 slot order, S4 strap) → then rev-D freeze. CPLD-driven
SWD_EN3 = rev-D wiring candidate (SPARE reaches neither CPLD nor U7 in
rev C).

**MCU hygiene notes:** MH1 `'?'` responder is pre-loop only (S_RESET
before `loadfw`; proper fix = `'?'` in the ISR dispatcher). CheckS
unbounded ready/BUSY spin-waits + the blocking-HAL-read-in-ISR pattern =
rev-D firmware hygiene (patched on MH1/H1S3/H1S4 2026-08-19 — audit
other CubeIDE projects before reuse).

**Cross-repo:** Dropbox `_Matrix` = canonical cross-repo store (absorbed
as `matrix-shared-store.md`); mx26 checkout at `~/mx26` for contract
syncs (`git -C ~/mx26 pull` first).

## P3 — contract evolution (waiting on mx26)

- Tier-2 slots staged in `defs.lock` (`D24_DSP_CFG_SHA256`,
  `D32_DSP_CFG_SHA256`, ABSENT until mx26 provides dsp.csv files).
  Resume: when mx26 adds `src/pd/d24/dsp.csv` or `src/pd/d32/dsp.csv`,
  run `./regenerate-dsp-contract.sh --update-lock`.
- FPGA mixer engine for larger products — idea folder seeded
  (`fpga/README.md`, `fpga/node-portability.md`); activation gate:
  becomes a numbered architecture decision first.
- `mx_master.csv` as cross-domain SOT — deferred; notes in `ideas.md`.

## Done (foundation, collapsed)

- Contract pipeline complete: defs.lock, sync-from-mx26.sh, hash
  verification, validate-matrix-contract.py, regenerate-dsp-contract.sh,
  check-contract-drift.sh, release-notes convention, smoke checklist.
- Alias retirement complete (2026-07-18); DSP mapping gap closed
  (349 cells added upstream).
- Fixed-point conversion (D5) COMPLETE 2026-07-31 — mainline is Q4.28;
  float archived at tag `float-kernels-2026-07-31`; golden harness 9/9.
- Fabric remap + product-config boot block + plumbing slices 1-3 DONE
  2026-07-31; diagnostics instrumentation DONE 2026-08-12.
- D24 schematics imported + hardware map derived
  (`MW/D24/HW/hardware-map.md`); binding decisions D1-D8 in
  `dsp4-architecture-decisions.md`.

## Workflow reference

| Command | Purpose |
|---|---|
| ./regenerate-dsp-contract.sh | Full sync + validate + generate |
| ./regenerate-dsp-contract.sh --update-lock | Same but bumps defs.lock hashes |
| ./check-contract-drift.sh | Pre-merge check |
| ./check-contract-drift.sh --strict | Strict gate — fails on any unintended drift |
| python3 audit-compat-aliases.py | Refresh alias-audit.md |
| python3 validate-matrix-contract.py | MxAdd continuity + family allowlist check |

## State snapshot (2026-08-20)

- Contract: defs-v2026.08.20 (mx26 `345470a`) — first pin on the clean
  5161-cell post-naming-pass D24 master; D24 _matrix 5125 rows, D32 6940.
- Firmware: unified DSP4 per dsp4-architecture-decisions.md; ~75-80%
  written, hardware-verified fraction low — bring-up is the work.
- Hardware: rev-C card live; SHARCs boot; dma_cfg_init wedge = the one
  open blocker on the audio path.

## Owners and cadence

- Owner: DSP workflow maintainer (dispatched sessions + PW bench).
- Review cadence: update on every contract bump and when NOW items move.

### Outcome 2026-08-23 04:3xZ — rung 1 DONE and verified; rung 2 BLOCKED on rung 0, with the evidence rung 0 was missing

**Rung 1 is complete.** All four facts closed by measurement over the
loopback bitstream — see `MW/D24/HW/hardware-map.md` for the tables and
`55092e0` for the firmware. Summary: lane index identity (DSPB O(n) →
DSPA I(n), n = 0..4), within-TDM8 slot order identity 0..7, BCK/FS pair
order correct (every word aligned at its own slot), sample edge / MFD
correct (the `0x5A5A` signature intact — a one-bit shift would read
`0xB4B4` or `0x2D2D`). The decisive case is receive lane 4, whose
channel-select mask `0x000D` picked exactly slots 0, 2 and 3 out of a
transmitter driving all eight, which pins the numbering as absolute
rather than merely consecutive.

**Rung 2 is blocked, and not on anything rung 2 owns.** It needs the
audio graph running, which needs `CONFIG_COMMIT`, and after the 51-write
config the parameter link is left **permanently out of phase**:

| | |
|---|---|
| before config | every diag read clean, `BOOT_STAGE 5`, 1500 blocks/s |
| after config | reads return `0x20260812` (`BUILD_ID`) for a `MAGIC` request |
| recovery | none — 10 consecutive read attempts, all out of step |

Stated plainly because an earlier reading of mine said otherwise: the
part is **not** dead and it is **not** starved. It answers; the answers
are simply shifted in the response stream, and `dsp4_diag.py` correctly
rejects them on the echo check, which is what made it look silent. That
is exactly the fault **rung 0** ("make every accepted transaction queue
exactly one two-word answer") was written to fix. Rung 0 was parked as a
protocol nicety; it is not one. It is the gate for every operation past
`CONFIG_COMMIT`, and therefore for rung 2.

**Tried and reverted:** moving the SPI poll from the main loop into the
1 kHz diag timer ISR, on the theory that block processing was starving
the loop. It broke the link outright — no answers even *before* config —
so it proves nothing and was not kept. The tree is back at the verified
rung-1 build and rebuilds to the same md5s (`7aa4f88…` / `89d314f…`).

**Also found, and it cost a wrong reading first — `dsp4_boot.py` can
silently leave chip 2 running CHIP 1's firmware.** It still prints
`booted 2 chip(s)`, warns `92% unsynced collision risk`, and the part
answers on chip 2's select with `CHIP_ID 1`. In that state chip 1's
receive lane 0 showed a 16-slot stream — which looked exactly like a real
slot-map fault and was not. It recurred twice more during the session.
**Read `CHIP_ID` off both parts before believing any bench measurement.**
The giveaway is identical `ADDRSTART`/`XCNT` on both chips: the two
images have different lane geometry and cannot legitimately match.

**Recommended next order:** rung 0 first (it is now evidence-backed, not
a nicety), then rung 2, then the queued blocks. Worth folding the boot
collision into the same pass — a `CHIP_ID` check inside `dsp4_boot.py`
with an automatic retry would have saved this session an hour.

**Bench state:** SHIPPING bitstream `dsp4_logic.a1f6672af6c3` restored and
verified; both chips booted on the production build (`caf6fd6c…` /
`290e9600…`) with `CHIP_ID` confirmed 1 and 2, running 1500.0 blocks/s,
`SPORT0_ERR_A 0x00000000`, `DMA0_STAT 0x00006200`; `matrix-app` active;
all three MCUs verified; GPIOs returned to `a0`.

### Outcome 2026-08-23 05:4xZ — rung 0 DONE and proven; the post-CONFIG_COMMIT death bisected to two faults, one fixed

**Rung 0 delivered, exactly as specified.** Every accepted transaction now
queues one two-word answer — reads `(echo, value)`, writes `(echo, 0)` —
so the master's transaction stream and the answer stream advance in
lockstep and cannot drift. Proof, `tools/pi/dsp4_roundtrip.py`:

    chip 1: 200 write/read round-trips, 0 wrong-value, 0 out-of-step
    chip 2: 200 write/read round-trips, 0 wrong-value, 0 out-of-step

The hub's read of the two earlier failures was right: they predate the
stale-word recovery, the polled link and the TFIFO NOP separation, and
with those in place the design worked first try. The echo comes from
`_spi_req_word`, not `r0`, because every write path between the drain and
the responder clobbers `r0`. The host-side realign fallback was built as
well (`SpiLink.realign`, `REALIGN_TRIES`) and is kept — but it is not what
made this work, and it did not rescue the fault below.

**The post-CONFIG_COMMIT death was NOT a phase problem at all**, which
answer-every-transaction is what proved: with every transaction echoing,
any handler entry would have shown an echo, and instead every read came
back `0x00000000`. The answers were not being produced.

#### Bisect, all other things equal

| build | result |
|---|---|
| 50 config data writes, no commit | healthy, `BOOT_STAGE 5`, blocks arriving |
| + `CONFIG_COMMIT` alone (one write) | **dead** |
| block work off, commit applies off, **idle on** | **dead** |
| block work off, commit applies on, **idle off** | healthy, `BOOT_STAGE 7`, 1500/s |

**Fault A — `idle`, now FIXED.** `.main_loop` opened with `idle` as a
low-power wait for the DMA interrupt, and it wedged the link the instant
the loop was entered — i.e. the instant `CONFIG_COMMIT` released
`.wait_boot`. `.wait_boot` spins; `.main_loop` slept. That is the entire
reason the card looked dead after configuration and healthy before it.
Not the config data, not `_rx_patch_apply`, not `_scope_gates_apply`, not
the block loop, and not the host.

**Fault B — the generated scatter/gather, localised, NOT fixed.** With the
idle gone the production path still wedges, and `DSP4_BLOCK_STAGE` puts it
in one place:

| `DSP4_BLOCK_STAGE` | contents | result |
|---|---|---|
| 1 | consume the block, do nothing | healthy |
| 2 | + `_scatter_chipN` / `_gather_chipN` | **dead** |
| 3 | + `_chipN_process_all` | **dead** |

So it is `_scatter_chip1` / `_gather_chip1` in the generated
`block_io.asm`, not the node graph. That is the next item and it is a
narrow one. The three build guards (`DSP4_BLOCK_STAGE`,
`DSP4_COMMIT_STAGE`, `DSP4_NO_IDLE_OVERRIDE`) are kept for it.

**Also done on the way, and required regardless:** `l2_clear()` zeroes both
L2 delay-line ranges at startup. The LDF says in as many words that
firmware must do this — `sec_delay`/`sec_delay_ovf` are `NO_INIT` to keep
the boot stream inside what the DSP boot bus tolerates — and nothing did,
so the delay lines came up holding whatever was in L2. It did **not** fix
either fault above; it closes a documented gap.

**Rung 2 still not started.** It needs `BOOT_STAGE 7` with real block I/O,
which is exactly what fault B blocks.

**Bench state:** SHIPPING bitstream `dsp4_logic.a1f6672af6c3` on the CPLD;
both chips booted on the production build (`5d310924…` / `1cdd94e9…`),
`CHIP_ID` confirmed 1 and 2, `BOOT_STAGE 5`, 1500.0 blocks/s,
`SPORT0_ERR_A 0x00000000`, `DMA0_STAT 0x00006200`; `matrix-app` active,
all three MCUs verified; GPIOs returned to `a0`.

### Outcome 2026-08-23 07:1xZ — the block loop is FIXED; the remaining hang is the compressor's gain computer

Two real bugs found and fixed since the last outcome, and the post-config
hang is now narrowed to a single routine.

#### FIXED — the sample loop ran ~610,000 times per block

`.cN_sample_loop` kept its 32-sample bound in `r6`, and **both**
`_scatter_chipN` and `_gather_chipN` load the active DMA buffer address
into `r6` (~`0x95350`). So the compare tested the sample index against a
buffer address. Not a fault, but indistinguishable from one. The loop
already reloads `r5` from `_sample_idx` two lines earlier for exactly this
reason; `r6` was missed.

With that fixed, and using `DSP4_BLOCK_MASK` (1 = scatter, 2 = node graph,
4 = gather) under a harness that **requires `BOOT_STAGE >= 6`**:

| mask | contents | result |
|---|---|---|
| 1 | scatter only | STAGE 7, 1500.0/s |
| 4 | gather only | STAGE 7, 1500.0/s |
| 5 | scatter + gather | STAGE 7, 1500.0/s, **`BLK_OVERRUN` 0** |
| 7 | + node graph | dead, reproducibly |

`BLK_OVERRUN` 0 is the result worth keeping: with both halves of the block
I/O running, the main loop now keeps up with **every** block.

#### Method note that cost two wrong readings

A bench check that only asks *"did the link answer"* gives **false
passes**. `CONFIG_COMMIT` does not always land, and a part still sitting at
`BOOT_STAGE 5` answers perfectly well because `.wait_boot` was never left.
Any harness must require `BOOT_STAGE >= 6` **and** non-zero `TICKS` before
it is entitled to call anything healthy. Both "MASK=5 hangs" and "gather
alone survives" were artefacts of not doing that.

#### NARROWED — `_compgain_fx`, and it is value-dependent

`DSP4_NODE_LIMIT` turns the flat 431-call chain into a binary search:
limit 5 alive, limit 6 dead. Index 5 is `_C1_COMP_01_process`. Bypassing
it (`_comp_on = 0`) makes limit 6 alive. Skipping the block-rate parameter
conversion does **not** help, so it is the per-sample path, and
`_compgain_fx` is the one library routine the compressor reaches that the
gate at index 4 does not. Stubbing it to unity: alive.

Below that the stubs stop isolating anything, and that is the finding:

| stub | result |
|---|---|
| `_exp2q_fx` | still dead |
| `_log2q_fx` | **alive** |
| `_polyq_fx` (called *by* log2q) | still dead |

If this were a plain bad-address or bad-instruction fault, stubbing log2q
and stubbing polyq would implicate the same code. They do not. Each stub
also changes the **values** flowing through the rest of the chain, so what
these show is that the failure is value-dependent inside the compgain
chain — not that any one routine is structurally wrong. More blind stubs
would be guesswork.

Two things worth knowing for the next pass:

- The gate at index 4 calls `_log2q_fx` too and is fine, because its call
  sits behind a threshold that silence never crosses. The compressor
  reaches the log2 path with whatever the inputs are actually delivering,
  so the input range here is not a designed one.
- It is **not** about floating inputs. Re-tested with the loopback
  bitstream, where DSPA's inputs are driven by DSPB rather than
  unterminated: same hang.

Also fixed, correct regardless, and **not** the cause: `_comp_knee` was the
only compressor parameter emitted with no initialiser, and it is read
before it is ever written — it feeds `recips` and the knee coefficients.
Now `0.0` (hard knee) in the generator, across all 42 compressor nodes.

**Rung 2 still blocked.** It needs `BOOT_STAGE 7` with the node graph
running, which is what this last fault prevents.

**Bench state:** SHIPPING bitstream `dsp4_logic.a1f6672af6c3` restored;
both chips on the production build (`397c608c…` / `ccf5899d…`), `CHIP_ID`
confirmed 1 and 2, `BOOT_STAGE 5`, 1500.0 blocks/s, `SPORT0_ERR_A`
`0x00000000`; `matrix-app` active, all three MCUs verified; GPIOs `a0`.

### Outcome 2026-08-23 08:3xZ — RETRACTION: the compressor identification was wrong. Build flags were not reaching the assembler.

**Retracted: `_C1_COMP_01` / `_compgain_fx` are NOT identified as the fault.**
The previous outcome named them on the strength of a stub bisect. That
bisect was invalid.

**What went wrong.** The `DSP4_STUB_*` defines were appended to `build.sh`
by a string replace against a copy of the `ASMFLAGS` line that no longer
matched (two other flags had been appended in between). The replace
silently did nothing and I did not assert on it, so **none of the stub
defines ever reached `easm21k`**. Every stub build produced the *same*
image — md5 `50a6c9d5` throughout. The alive/dead differences I recorded
were bench flakiness, not the stubs.

Caught by md5-ing the image across a flag change, which is the rule that
already exists for dump readings and which I should have applied here:
**if a build flag changes and the image md5 does not, the flag is not
reaching the tool.** `build.sh` now passes all four stub defines, verified
by the md5 changing.

**Re-tested with the flags actually working, and the picture is different:**

| build | runs | result |
|---|---|---|
| production, full node graph | 6 | **0 alive** |
| production, 40 patient reads over 40 s after commit | 40 | **0 answered** |
| `DSP4_BLOCK_MASK=5` (scatter+gather, no node graph) | 4 | **4 alive** |
| `DSP4_NODE_LIMIT=1` (one node) | 3 | **3 alive** |
| stub `_compgain_fx` to unity, full chain | 2 | **0 alive** |

So `_compgain_fx` is exonerated — stubbing it changes nothing. And
`DSP4_NODE_LIMIT` 5 vs 6, which is what pointed at the compressor, does
**not** reproduce: limit 5 came back DEAD twice on re-test having been
ALIVE before, and limit 6 came back ALIVE once and DEAD three times.

**What is solid, with repeats:**

- The core genuinely STOPS after `CONFIG_COMMIT` with the full graph —
  0 of 40 reads over 40 s. Not starvation: the 1 kHz timer-ISR backstop
  would have answered at least once.
- Without the node graph the card is reliably healthy: 4/4 at
  `BOOT_STAGE 7`, 1500.0 blocks/s.
- One node is reliably healthy: 3/3.
- Somewhere between 1 node and 431 it becomes marginal and then dead, and
  the marginal region does not give a stable answer to a single-point
  test.

**Also corrected:** the previous outcome claimed `BLK_OVERRUN 0` for
scatter+gather. That was the stale image. The real figure is ~8590
overruns against ~17220 blocks — the loop keeps up with roughly every
*other* block, before a single node has run. That is a useful number in
its own right and it reframes the remaining fault: the per-block budget is
already half spent on block I/O alone.

**What stands unchanged:** the `r6` loop-bound fix is a real code defect,
readable in the source — `_scatter_chipN` and `_gather_chipN` both load
the DMA buffer address into `r6` while `.cN_sample_loop` used `r6` as its
sample bound. Rung 0 (200 round-trips, both chips, zero slips) and rung 1
(TDM slot map) were direct repeated measurements and are unaffected.

**Next, and it needs the harness fixed first:** a single-point alive/dead
test is too noisy to bisect on. Give each point N repeats and a pass rate
before drawing any line. Then find where the pass rate falls off between
1 and 431 nodes, and check the per-block cycle budget directly rather than
inferring it — with block I/O alone already missing half the blocks, a
cycle-budget explanation deserves testing before another node hunt.

**Bench state:** SHIPPING bitstream; both chips on the production build
(`5b1c164e…` / `08673015…`), `CHIP_ID` confirmed 1 and 2, `BOOT_STAGE 5`,
1500.0 blocks/s, `SPORT0_ERR_A` clean; `matrix-app` active, three MCUs
verified; GPIOs `a0`.

### Outcome 2026-08-23 09:5xZ — ROOT CAUSE: the node graph is ~16× over the per-block cycle budget

Not a defect in any node. **Capacity.**

#### The harness first, because the last conclusion was wrong for want of one

- `main.asm` carries `_build_flags`, a stamp encoding every bisect define.
  `bisect.sh` computes the expected value and the bench side **peeks it
  off the running part** and aborts on mismatch. That closes the loop
  through assembler, linker, loader and boot — the exact gap that let four
  `DSP4_STUB_*` defines silently not reach `easm21k`.
- Every point is N repeats and a pass **rate**.
- `DSP4_BLOCK_DECIMATE` runs the graph every Nth block, giving it N times
  the budget **without changing what it computes**. That is what separates
  "a node is broken" from "the graph does not fit" — identical from
  outside, because a main loop that never finishes a block never services
  the parameter link either.

#### Measured, every point stamp-verified

| nodes | decimate | alive / runs |
|---|---|---|
| 1 | 1 | 3/3 |
| 5 | 1 | 0/3 |
| 10 | 1 | 1/3 |
| 15 | 1 | 1/3 |
| 27 | 1 | 0/3 |
| **27** | **8** | **3/3** — same nodes, 8× budget |
| 108 | 1 | 0/3 |
| **431** | **1** | **0/6** |
| 431 | 8 | 1/3 |
| **431** | **16** | **3/3** — full graph, unmodified |
| 431 | 32 | 3/3 |
| 431 | 64 | 3/3 |

The full graph runs clean given 16 block periods and fails given one:

    budget    491.52 MHz / 1500 blocks/s = 327,680 cycles per block
    required  ~5.2 M cycles per block
              ~164,000 cycles per sample across 431 nodes
              ~380 cycles per node per sample

~380 cycles is a plausible cost for this library — a compressor alone runs
an envelope follower plus log2 and exp2 polynomial evaluations per sample.
That is the point: the cost is **real work**, and no amount of node-level
debugging was ever going to find it.

#### And nothing is currently reducing it per product

`_scope_gates_apply` on chip 1 is a **no-op** — the generated body is
`rts; /* no scoped nodes on this chip */`. So all 431 nodes run for D24
and D32 alike, and the measurement above already reflects a committed d24
config. Product gating is not saving anything today.

**This is a design-capacity decision and it belongs to the hub:** fewer
nodes per chip, cheaper nodes, or work moved out of the per-sample loop
(the graph is called once per sample — 431 calls × 32 samples = 13,792
node invocations per block).

**Rung 2 does not have to wait for that decision**, but it cannot be run
as written either: a scorable `aplay`/`arecord` loop needs the graph
passing audio in real time. What *is* reachable now is proving the Pi
capture path with deterministic content — the `DSP4_PATTERN` firmware
puts a known word in every DSPB transmit slot with no node graph
involved, so de-framing one lane/slot to `pcm_din` and capturing it on the
CM4 validates the whole path independently of DSP processing. That is the
next step being taken.

**Bench state:** SHIPPING bitstream; both chips on production
(`eed5183f…` / `4778f022…`), `CHIP_ID` 1 and 2, `BOOT_STAGE 5`, 1500.0
blocks/s, `SPORT0_ERR_A` clean; `matrix-app` active, three MCUs verified.

### Outcome 2026-08-23 11:3xZ — (c) cycle profile DELIVERED; (b) strips knob built, answer is uncomfortable; (a) rung 2 RTL ready, not yet run

#### (c) CYCLE PROFILE — done, in `MW/D32/DSP/dsp4-cycle-budget.md`

Measured with a `TCOUNT`-based instrument (exact to the core clock, not
1 ms-quantised), differenced across `DSP4_NODE_LIMIT` points inside one
strip so each row is a real node running in place:

| class | cycles/sample | share of a strip |
|---|---|---|
| **RTG** | **601** | **30.5%** |
| EQ | 338 | 17.1% |
| FILT | 227 | 11.5% |
| GATE | 204 | 10.4% |
| COMP | 202 | 10.2% |
| DLY | 148 | 7.5% |
| FDR | 128 | 6.5% |
| GAIN | 63 | 3.2% |
| TUBE | 40 | 2.0% |
| IN | 24 | 1.2% |

**RTG — a routing node — is the most expensive class on the part, more
than EQ and COMP together.** That is not where anyone would have looked.
The dynamics maths, which gets all the attention, is not the problem.
Fixed overhead before any strip runs is 44% of the budget: block I/O ~20%
(scatter over 46 channels, gather over 37 sends, 32× per block), buses and
sends ~24%.

#### (b) NODE-ENABLE MASK — built, verified, and the answer is not the one wanted

`DSP4_STRIPS=N` keeps the graph functional (N strips, every bus, send,
cross-in and transfer retained), unlike `DSP4_NODE_LIMIT` which is a raw
prefix cut. 320 strip-guarded calls generated. The flag is verified in the
running image through a second stamp word `_build_flags2`.

**One strip does not hold 1×.** It measures 240,129 cycles/pass = 73.3% of
the budget — by arithmetic it fits — and is still 0 alive / 3.

| configuration | measured load | alive at 1× |
|---|---|---|
| 1 node | 20.0% | 3/3 |
| 10-node prefix | 39.0% | 1/3 |
| `DSP4_STRIPS=1` | 73.3% | 0/3 |
| full graph | 660% | 0/6 |

Reliable below ~20%, marginal ~39%, gone by ~73%. **Roughly a 2.5× margin
is being consumed by something the cycle count does not explain, and I
have not identified it.** Two candidates to separate before anyone sizes a
design against these numbers: the alive/dead test is really a
*parameter-link* test (the link may give out before the audio does), and
interrupt overhead plus overrun compounding, which a per-pass cycle count
cannot see. The per-class table is unaffected by this and stands.

#### (a) RUNG 2 — RTL and tooling ready, bench run not done

- `dsp4_pcm_reframe` gains a capture path: de-frames two TDM8 slots of a
  DSPB output lane into the Pi's L/R I2S on `pcm_din`, launching on the
  PCM BCK falling edge so the Pi samples mid-bit. MFD=1 means slot s bit b
  is on the wire during period (s*32+b+1); the capture undoes that +1.
- The loopback build no longer ties off lane 6 — it keeps `i_dspa[6]` on
  `pcm_tdm`, because otherwise the Pi has no path *into* the DSP and a
  round trip is impossible.
- **Shipping bitstream proven unchanged**: `dsp4_logic.a6e046438eb4.pof`
  is byte-identical to `dsp4_logic.a1f6672af6c3.pof`. Source hash moved
  because the source moved; fitted logic did not.
- New bring-up artefact `dsp4_logic_loopback.b13e772abdbb`, same sim and
  STA gates.
- `tools/pi/dsp4_pcm_capture.py` records the stream and checks it bit-exact
  on all 32 bits against the `DSP4_PATTERN` word, and names a one-bit
  rotation explicitly rather than printing two hex numbers.

Not yet flashed or captured. Latency in samples is **not** obtainable from
the constant pattern alone — it needs a time-varying source, which means
the Pi playback path and therefore a graph small enough to run, which is
what (b) has just shown is not currently available.

**Bench state:** SHIPPING bitstream `dsp4_logic.a1f6672af6c3` restored;
both chips on production (`e7b53db4…` / `a4b8f3b5…`), `CHIP_ID` 1 and 2,
`BOOT_STAGE 5`, 1500.0 blocks/s, `SPORT0_ERR_A` clean; `matrix-app`
active, three MCUs verified; GPIOs `a0`.

### Outcome 2026-08-23 11:5xZ — the hub's call was right: 2 strips run real time; rung 2 blocked on the Pi, not the DSP

#### The "2.5× margin" was the test. Retracted.

Judging aliveness by whether the parameter link answered promptly was
wrong — that link is serviced by **polling from the block loop**, so under
load an answer is a block or more away, which is normal. `DSP4_STRIPS=1`
judged on audio truth instead:

    BOOT_STAGE 7 · FRAME_COUNT 1500/s · DMA0_STAT 0x00006200
    SPORT0_ERR_A 0x00000000 · _proc_passes 1500/s

Real time, every block. Previously recorded as 0 alive / 3.

#### (b) STRIPS CEILING — 2

`_proc_passes` counts completed block passes, which is the honest measure:
`FRAME_COUNT` is incremented by an ISR and advances whether or not the
loop keeps up.

| `DSP4_STRIPS` | passes/s | verdict |
|---|---|---|
| 1 | 1500 | real time |
| **2** | **1500** | **real time — the ceiling** |
| 3 | 1342 | 89%, dropping ~1 block in 9 |
| 4 | 1144 | 76%, over budget |

Two strips against 32 required. The measurement agrees with the cycle
arithmetic (2.9 predicted) to better than one strip, so the profile table
and the bench now corroborate each other.

Two fixes kept, both of which prevent the same class of error:
`dsp4_audio_verdict.py` separates transport from loop and reports UNKNOWN
when the link is silent (distinct from AUDIO_DEAD); and
`dsp4_diag.py.read()` no longer realigns the word phase on the *first*
echo mismatch — it collects patiently first, because the usual cause is
that the DSP has not polled yet. The old behaviour manufactured a fault
out of a slow answer.

#### (a) RUNG 2 — DSP and CPLD sides done; blocked on the Pi having no I2S device

Done and verified on the bench:

- `dsp4_logic_loopback.b13e772abdbb` flashed. Card healthy on it:
  1500 blocks/s, `DMA0_STAT 0x00006200`, `SPORT0_ERR_A` clean.
- **`pcm_din` is live.** GPIO20 sampled 12× asynchronously reads 2 hi /
  10 lo — the CPLD is driving real data on the capture line, and ~17%
  high is the right ballpark for the pattern words 0x5A5A0000 /
  0x5A5A0001 (17 ones in 64 bits = 27%).
- Shipping bitstream restored and re-verified afterwards.

**Blocked, and not on anything in this repo:** `arecord -l` on the CM4
lists no capture hardware at all — only the two HDMI devices.
`/boot/firmware/config.txt` has no I2S overlay. Without a sound card in
the device tree there is nothing to record from, so the bit-exact check
and the latency figure cannot be taken.

What it needs, and why I have not just done it: adding an I2S overlay is a
persistent edit to `/boot/firmware/config.txt` plus a **reboot of the only
bench**, and a bad edit there does not come back over SSH. The overlay
also has to make the Pi an I2S **slave**, since LOGIC masters `pcm_clk`
and `pcm_fs` — that is a choice worth making deliberately rather than
guessing at on a 24/7 unit. The GPIOs do not clash: I2S uses 18-21,
`matrix-app` uses 6-12 and 22-25.

`tools/pi/dsp4_pcm_capture.py` is written and waiting — it checks
bit-exact across all 32 bits and names a one-bit rotation explicitly
rather than printing two hex numbers.

**Bench state:** SHIPPING bitstream `dsp4_logic.a1f6672af6c3` restored;
both chips on production (`e7b53db4…` / `a4b8f3b5…`), `CHIP_ID` 1 and 2,
`BOOT_STAGE 5`, 1500.0 blocks/s, `SPORT0_ERR_A` clean; `matrix-app`
active, all three MCUs verified; GPIOs `a0`.

### Outcome 2026-08-23 12:2xZ — RUNG 2 CAPTURE PATH BIT-EXACT; CM4 I2S provisioning for mx26 below

#### Result

    captured 96000 frames at 48000 Hz from hw:0,0
      left  0x5A5A0000  96000/96000 = 100.00%
      right 0x5A5A0001  96000/96000 = 100.00%
    RUNG 2 CAPTURE: BIT-EXACT PASS

All 32 bits, every frame. A 24-bit check would have hidden the fault
found on the way — see below.

#### CM4 PROVISIONING — for `mx26 scripts/cm4-setup-pi.sh` (SOT)

The unit had **no PCM device at all**: `arecord -l` listed only HDMI. Two
files were added and one line appended; nothing else on the unit changed.

**1. `/boot/firmware/config.txt`** — appended at the end, inside `[all]`:

```
# DSP4 bench: duplex I2S soundcard, Pi as I2S SLAVE (LOGIC CPLD
# masters pcm_clk 3.072 MHz / pcm_fs 48 kHz). Source dts alongside the
# dtbo in this directory. Added 2026-08-23 for rung 2 (pcm_din capture).
dtoverlay=dsp4-pcm-slave
```

Backup of the original is on the unit as
`/boot/firmware/config.txt.bak-20260823-120634`.

**2. `/boot/firmware/overlays/dsp4-pcm-slave.dtbo`** — compiled on the
unit with `dtc -@ -I dts -O dtb`. The source is installed beside it as
`/boot/firmware/overlays/dsp4-pcm-slave.dts` and is committed in this repo
at `shared/dsp4-logic/pi/dsp4-pcm-slave.dts`. **dtbo origin: built from
that dts, not downloaded.**

**Why no stock overlay fits.** `audioinjector-bare-i2s` is the closest and
is wrong twice over: its codec is `linux,spdif-dit`, a *transmitter*, so
it is playback only; and its `bitclock-master`/`frame-master` point at the
**cpu** node, making the Pi the I2S master. The DSP4 card has the CPLD
mastering both clocks, so the Pi must be a slave.

**What the custom overlay does.** Points `bitclock-master`/`frame-master`
at the **codec** side of each link, so `bcm2835-i2s` consumes the external
clocks. Uses **two dai-links** because the dummy codecs are each
one-directional — `linux,spdif-dit` for playback, `linux,spdif-dir` for
capture. 32-bit slots, 2 per frame, matching the 32-bit lane words.

Result after reboot:

    card 0: dsp4pcm — device 0 = capture (dir), device 1 = playback (dit)
    capture formats S16_LE S24_LE S32_LE, 2 ch, rate 8000-768000

Note `i2s_clk_consumer` and `i2s_clk_producer` both resolve to the same
node on this kernel (6.18.34+rpt-rpi-v8), so slave mode comes purely from
the master properties, not from the target label.

#### The fault the 32-bit check caught

First capture read `0xB4B40000` / `0xB4B40002` against transmitted
`0x5A5A0000` / `0x5A5A0001` — the expected words **shifted left exactly
one bit**, 100% stable over 96,000 frames. Left-shifted by one means the
receiver started a bit early, so the capture launch wanted one more BCK of
delay than the playback direction. New parameter `CAP_EXTRA_DELAY = 1`,
measured not guessed. `dsp4_pcm_capture.py` names a one-bit rotation
explicitly instead of printing two hex numbers, which is what turned that
from a puzzle into a one-line fix.

#### Latency — NOT measured, and the reason is not the plumbing

Both Pi directions are proven:

- **DSPB → Pi**: bit-exact, above.
- **Pi → DSPA**: proven directly. Playing a tone into `pcm_dout` and
  peeking chip 1's receive buffer for lane 6 (word `0x958B8`) shows live
  signal data — `0xE95F619A` — where it reads `0x00000000` with no
  playback. The reframer's playback direction and `i_dspa[6]` both work.

The round trip does not close because **the DSP does not route DSPA's Pi
input to DSPB's output**: with a committed d24 config and a 1-strip graph,
a 1 kHz tone in produces digital silence out. That is a matrix
routing/parameter question — the routes are host-written parameters that
nothing in the boot config sets — not a bring-up gap. Latency in samples
needs that route to exist first, so it belongs with the virtual-audio work
in the queued chain rather than with rung 2's plumbing.

**Bench state:** SHIPPING bitstream `dsp4_logic.a1f6672af6c3` restored;
both chips on production (`e7b53db4…` / `a4b8f3b5…`), `BOOT_STAGE 5`,
1500.0 blocks/s, `SPORT0_ERR_A` clean; `matrix-app` active, all three MCUs
verified; GPIOs `a0`. The I2S overlay is persistent and survives reboot by
design — it does not disturb `matrix-app` (I2S uses GPIO 18-21,
`matrix-app` uses 6-12 and 22-25).

### Outcome 2026-08-23 12:5xZ — desk fillers: 1 CLOSED, 2 DONE with numbers, 3 BLOCKED on document access

#### 1. SPI2_RDY — CLOSED, verdict: not usable on this silicon

HRM ch.15: in slave mode `SPI_RDY` is an output and `SPI_CTL.FCCH` picks
the FIFO it follows — 0 = RX buffer ("I can accept"), 1 = TX buffer
("I have data"). The firmware is **already** configured the way the task
hoped to find, read back off a running chip 1:

    SPI2_CTL = 0x0001A501
      EN=1  MSTR=0  FCEN=1  FCCH=0 (RX)  FCPL=1 (active-high)  FCWM=1

It idles high on both chips (10/10; chip 1 GPIO8, chip 2 GPIO12), and high
against the board's 10K pulldown means the pin **is** driven.

It never deasserts. The decisive test clocks one 64-byte transfer with CS
held — 16 words into a 2-deep FIFO, which the DSP cannot drain because it
drains by polling *between* transactions — and samples RDY the instant it
returns:

| FCWM | meaning | RDY low |
|---|---|---|
| 1 | RFIFO ≥ 75% | 0/40 |
| 2 | RFIFO ≥ 50% | 0/40 |
| 0 | RFIFO full | 0/40 |

All three legal values, each confirmed live in `SPI2_CTL` first. A
guaranteed overfill never moves the pin. Corroborating: `SPI_STAT.FCS`
reads 1 constantly with both FIFOs empty and the link idle — FCS is
documented as a *master*-mode stall indication, and permanently set in
slave mode fits a flow-control block not behaving as ch.15 describes.

**No host change made.** The tools already accept `--rdy-gpio` and call
`wait_ready()`; with the pin stuck asserted that never blocks, so it is
harmless but buys nothing and must not be relied on for pacing. rev-D
mod 9 (RDY pull-up) stands. Note the boot kernel uses the opposite
polarity — `dsp4_boot.py` expects RDY **low** during pre-select.

#### 2. 570Z scratch-fit — DONE

`shared/dsp4-logic/quartus/scratch570/` fits the **current** RTL (shipping
configuration) into the smaller part. Correct Quartus device name is
`5M570ZT144C4` — the `N` in `5M570ZT144C4N` is an ordering-code suffix and
Quartus rejects it.

| | 5M570ZT144C4 |
|---|---|
| logic elements | **157 / 570 (28%)** |
| registers | 127 / 570 (22%) |
| pins | **71 / 114 (62%)** |
| headroom | 413 LE, 43 pins |
| worst setup slack | **+0.842 ns** on the 20.345 ns (49.152 MHz) sysclk |
| implied Fmax | **51.27 MHz — only 4.1% margin** |

**Two pins in the current map are illegal on the 570Z in the same T144
package**, and one is exactly the pin the task flagged:

- `mems` on **PIN_137** — illegal; fitter relocated to PIN_58
- `test[2]` on **PIN_8** — illegal; fitter relocated to PIN_11

Those relocations are the *fitter's* choice with no knowledge of the PCB —
they confirm the pins must move and give a legal example, they are not a
layout recommendation.

**The headline for the part decision is timing, not capacity.** The design
uses only 28% of the LEs but leaves just 4.1% timing margin at 49.152 MHz,
where the 5M1270ZT144C4 manifest records 70.21 MHz. The rev-D lane map
adds logic to a design that is already close to the edge on the smaller,
slower part.

**Not assessed: the ±10 ns BICK↓ vs MCLK↑ constraint for the cascaded
AK5558 slaves.** That constraint belongs to the rev-D unified lane map,
and no RTL for it exists — there is nothing to time. What the numbers
above bound is the headroom that map would have to fit into.

#### 3. OSPI clock gate — BLOCKED on document access

The HRM ch.16 is functional, not electrical. It **does** establish:
Octal DDR and DTR protocol supported, up to 16 bits per SPI clock,
programmable dummy cycles, and a "tune data capture mechanism to improve
high speed operation". It contains **no** occurrence of RWDS, HyperRAM,
HyperBus, or xSPI "profile" anywhere — so profile-2 / HyperRAM 2.0 support
is *not* evidenced by the HRM.

The max OSPI clock (133 vs 200 MHz) is a datasheet electrical spec and the
datasheet is not reachable from this machine: not in `_Matrix`, analog.com
times out, the verical mirror returns 403, the Mouser mirror times out,
and the ampnuts mirror only carries the HRM. One search result indicates
OSPI **boot** is capped at 62.5 MHz OSPI clock, which is a boot-mode
constraint and not the interface maximum.

**Ask for the hub:** drop
`adsp-21562-21563-21565-21566-21567-21569.pdf` (Rev D) into
`_Matrix/.../adsp-2156x-docs` and this closes in minutes — the answer is
in "OSPI Port—Master Timing" in the Timing Specifications section.

**Bench state:** SHIPPING bitstream; both chips on production
(`e7b53db4…` / `a4b8f3b5…`), `CHIP_ID` 1 and 2, `BOOT_STAGE 5`, 1500.0
blocks/s, `SPORT0_ERR_A` clean; `matrix-app` active, three MCUs verified.

### Outcome 2026-08-23 13:1xZ — virtual audio: the pass-through LOOP IS CLOSED; calibration to bit-exact is the next step

#### The loop runs end to end

    captured 96000 frames, peak |L| = 0x7BB7C120, SIGNAL PRESENT

Pi `aplay` → `pcm_dout` → reframer → DSPA I6 → `C1_XIN_PI_L/R` →
`C1_XS_XFER_PI_*` → inter-chip → `C2_XR_PI_*` → `C2_PI_IN` → `C2_MIX_MAIN_*`
→ `C2_MAIN_FDR` → `C2_MAIN_DLY` → `C2_MAIN_ST_OUT` → SPORT3 slot 0 →
`o_dspb[3]` → reframer capture → `pcm_din` → Pi `arecord`.

That is the precondition the whole virtual-audio block was waiting on.

#### The two things that were blocking it

**1. The capture was tapping the wrong lane.** `o_dspb[0]` slots 0/1 are
`C2_AUX_OUT_01/02` and carry nothing in a pass-through. The main stereo
output is `C2_MAIN_ST_OUT` → SPORT3 slot 0 → **`o_dspb[3]`** (the CPLD's
`dac_main`). Loopback bitstream now taps that:
`dsp4_logic_loopback.3f488870d6cb`.

**2. The Pi input is gated OFF by default.** `_auxin_on_C2_PI_IN = 0`,
SPI address **0x071D** on chip 2. One poke opens it. Everything downstream
already defaults to unity — mix gains 1.0, `_fdr_level` 1.0, mute 0 — and
the Q4.28 shadows are refreshed at block rate, so they self-populate and
are not a second gate.

#### NOT yet bit-exact — the gain is about 4x

Input tone amplitude `0x20000000`, captured peak `0x7BB7C120`: a ratio of
**3.87**, near enough 2^2 to look structural rather than accidental. Step 1
of this block says stop and find why before anything else is meaningful,
and that is where it stands. Worth noting the scatter/gather Q1.31↔Q4.28
shifts (`ashift by -3` on the way in) as the first place to look, since a
mismatched pair there is exactly a power-of-two error.

Also seen: only ~4.5% of captured frames carry signal, so the stream is
bursty — `aplay` reported an overrun earlier. Playback buffering needs
pinning down before any latency figure is taken, or it will measure ALSA
rather than the DSP.

#### Not started

The harness extension (`--target hw`) and the five kernel families. They
need a bit-exact unity path first, per the block's own instruction.

#### One conflict for the hub to resolve

This block says "leave the pass-through loop soaking when you stop"; the
standing Rules say "the SHIPPING bitstream must be restored on the CPLD
before ending". They cannot both hold — the soak needs the loopback
bitstream on the card. **I restored SHIPPING**, on the grounds that it is
the older standing rule and this is a 24/7 bench others may pick up. Say
which wins and I will leave the soak running instead.

**Bench state:** SHIPPING bitstream `dsp4_logic.a1f6672af6c3`; both chips
on production (`e7b53db4…`), `CHIP_ID` 1 and 2, `BOOT_STAGE 5`, 1500.0
blocks/s, `SPORT0_ERR_A` clean; `matrix-app` active, all three MCUs
verified; GPIOs `a0`.

### Outcome 2026-08-23 13:4xZ — the 4× was MY MEASUREMENT. Path is unity and bit-exact. Duplex streaming on the Pi is the real blocker.

#### The 4× gain does not exist — retracted

Proved with a known word, as instructed, rather than a level:

    in 0x00001000 -> out 0x00001000   ratio 1.0000  = in << 0
    in 0x00010000 -> out 0x00010000   ratio 1.0000  = in << 0
    in 0x00100000 -> out 0x00100000   ratio 1.0000  = in << 0

100% of non-zero frames, three bit positions. **The pass-through is unity
and bit-exact through all 32 bits.** The earlier "3.87×" came from taking
a *peak* out of an overrun-riddled capture — the peak was a glitch, not
signal. A level cannot tell you a shift; the hub's instruction was right
and the answer changed as soon as I followed it.

The shifts are also correct by inspection, which corroborates it:
chip 1 scatter `>>3` (Q1.31→Q4.28), chip 1 gather no shift (inter-chip
stays Q4.28), chip 2 scatter no shift, chip 2 gather `<<3` with
saturation. Paired, no net shift.

#### What actually blocks the vector set and latency: duplex on the CM4

| condition | result |
|---|---|
| capture alone (rung 2, pattern firmware) | **100.00% stable, bit-exact** |
| playback alone into the DSP | arrives — lane-6 RX buffer showed live tone data |
| **playback + capture together** | **scrambled** |

With both streams running, a per-sample counter comes back with values
staying under ~200 across 20,000 frames instead of climbing to 48,000;
dominant step −191; short ascending runs (48,49 / 84,85,86) separated by
jumps backwards. ALSA reports no under/overrun once period/buffer are
pinned (97.6% of frames carry data), so this is not simple buffer
starvation — the *content* is wrong, repeating a small window of stimulus.

**Suspected cause, and it is my overlay's design.** `dsp4-pcm-slave.dts`
creates **two dai-links sharing one `bcm2835-i2s` CPU DAI** — playback on
`linux,spdif-dit`, capture on `linux,spdif-dir` — because those dummy
codecs are each one-directional. That gives two PCM devices but not a true
duplex device, and starting/running one stream appears to disturb the
other. Capture alone and playback alone are each clean; only the
combination is not.

**Fix direction for the next pass:** one dai-link with a codec that
declares BOTH directions, so the card presents a single full-duplex PCM
device, and confirm `bcm2835-i2s` supports concurrent streams at all in
slave mode. That is a device-tree question, not a DSP one — the DSP side
is proven unity and bit-exact.

#### Also found (node graph, worth a hub decision)

**Nothing drives SPORT3 slot 1 on chip 2.** `C2_MAIN_ST_OUT` is the only
node writing SPORT3 and it writes slot 0 only, despite being declared
"Channels: 2". So the capture's right channel is correctly silent. Whether
the main stereo out should drive a second slot is a graph/generator
question.

#### Not done

Latency in samples — deliberately not reported. Every number available
would be dominated by the duplex fault above, and a latency figure taken
through a stream that repeats a 200-sample window would be fiction.

**Bench state:** **LOOPBACK-CAPTURE bitstream
`dsp4_logic_loopback.3f488870d6cb` on the CPLD** (per the 13:0xZ hub
ruling — restore SHIPPING at the end of this block). Both chips on the
`DSP4_STRIPS=1` build, `CHIP_ID` 1 and 2, `BOOT_STAGE 5`, 1500.0 blocks/s,
`SPORT0_ERR_A` clean; `matrix-app` active, all three MCUs verified;
GPIOs `a0`.

### Outcome 2026-08-23 15:0xZ — harness families BLOCKED: ramped parameter writes land one word low

Latency delivered (93 samples, see `dsp4-plumbing.md`). The first family,
GAIN, then hit a firmware bug that blocks every family needing a parameter
write.

#### The double bind

**A direct write to a ramped parameter does nothing.** `C2_PI_IN`'s
block-rate code is `if frames <= 0: level = target`, run every block, so a
`ramp_id = 0` write to `_auxin_level` is overwritten within one block
period. Measured: a full −60…+18 dB sweep produced *identical* output at
every setting.

**And the ramped write is broken.** Writing `1.0` (`0x3F800000`) to
`0x071C` with `ramp_id = 1` put `0x3C000000` — **1/128** — in the target,
converging over repeats to `0x3BFE03F8` ≈ **1/129**.

That number is the giveaway. `_ramp_set_target` computes
`step = (target − current) / frames` by Newton-Raphson reciprocal and
stores **target at `[r0+1]`, step at `[r0+2]`, frames at `[r0+3]`**. A
value of ~1/129 appearing where the target belongs is the *step*, so the
stores are one word low, which means

    r0 = 0x951DC = _auxin_on      (not 0x951DD = _auxin_level)

C2_PI_IN's layout is `on 0x951DC, level 0x951DD, target 0x951DE,
step 0x951DF, frames 0x951E0`, so a correct `r0` would put target at
`0x951DE`. It puts step there instead.

**Consequence:** a ramped write silently zeroes the parameter chain and
corrupts `_auxin_on` along with it. Measured after the sweep:
`auxin_level = 0.0`, `auxin_target = 0.0` — the audio path went silent and
**no direct write could recover it**, because the block-rate copy
immediately restores level from the zeroed target. Only a reboot restores
it (the `.var` initialisers give level = target = 1.0).

#### What is NOT established

The symptom is localised; the cause is not. Three candidates, and I have
not distinguished them:

1. the SPI dispatch table entry for `0x071C` resolving to `_auxin_on`,
2. how the handler computes `r0` before calling `_ramp_set_target`,
3. the offset convention inside `_ramp_set_target` itself.

The dispatch table *comment* says `0x071C: C2_PI_IN level`, so if the table
is right the fault is in (2) or (3) — but the table's own generated
comments are not proof of the address it emits.

#### Why this matters beyond the harness

Every family after GAIN needs parameter writes — EQ coefficients, dynamics
thresholds, fader levels. **All of them are ramped.** So this is not one
family blocked, it is the harness's whole parameter channel. It also lands
squarely in the kernel-rewrite block's path, since that work touches
parameter handling and the block-rate gain computer.

**Bench state:** healthy and restored — bit-exact unity pass-through
(`ratio 1.0000` on three known words, 100% of non-zero frames), both chips
`CHIP_ID` 1 and 2 at `BOOT_STAGE 7` on the `DSP4_STRIPS=1` build. CPLD
carries `dsp4_logic_loopback.2b00c3e17e2a` (captures `B_O3` slot 0 =
`C2_MAIN_ST_OUT`, the only slot the graph drives).
