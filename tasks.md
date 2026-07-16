# tasks

Status: active
Date: 2026-07-15
Purpose: prioritize the work needed for the mx26 -> mx-dsp workflow to succeed.

Status colors:
- <span style="color:#16a34a"><b>DONE</b></span>
- <span style="color:#d97706"><b>IN PROGRESS</b></span>
- <span style="color:#2563eb"><b>NEXT</b></span>
- <span style="color:#6b7280"><b>BLOCKED/DEFERRED</b></span>

## P0 - Foundation (do first)

- [x] <span style="color:#16a34a"><b>DONE</b></span> Create defs.lock at repo root
  - Why: pin mx-dsp to an exact mx26 definition state.
  - Include: source repo, commit sha, contract version, per-product hashes.
  - Done when: anyone can identify exactly which mx26 definition set this repo targets.

- [x] <span style="color:#16a34a"><b>DONE</b></span> Replace sync-from-app.sh with sync-from-mx26.sh (or add as parallel path)
  - Why: remove dependency on app-local config copies.
  - Source should be mx26 contract outputs, not a local app path.
  - Done when: one command imports D24 and D32 contract files from mx26 locations.

- [x] <span style="color:#16a34a"><b>DONE</b></span> Add contract hash verification step
  - Why: prevent stale or partial file copies.
  - Verify: d24.csv, d32.csv, d24-mx-master.csv, d32-mx-master.csv, generated _matrix.csv files.
  - Done when: sync fails loudly on hash mismatch.

- [x] <span style="color:#16a34a"><b>DONE</b></span> Define and document the minimum contract payload
  - Use: [mx26-mx-dsp-integration.md](mx26-mx-dsp-integration.md)
  - Done when: payload list and required fields are explicit in this repo and stable.

## P1 - Safe generation and compatibility gates

- [x] <span style="color:#16a34a"><b>DONE</b></span> Add matrix compatibility checker before DSP generation
  - Why: detect new or renamed cell families before gen_dsp.py runs.
  - Check: incoming families against supported parser/mapping assumptions.
  - Implemented in: [validate-matrix-contract.py](validate-matrix-contract.py) + [matrix-families-allowlist.txt](matrix-families-allowlist.txt)
  - Done when: unsupported matrix vocabulary produces actionable errors.

- [x] <span style="color:#16a34a"><b>DONE</b></span> Add deterministic regenerate command
  - Flow: sync -> verify -> generate -> report.
  - Targets: MW/D32/DSP/gen_dsp.py and downstream generated outputs.
  - Done when: one command reproduces expected generated files with no manual steps.

- [x] <span style="color:#16a34a"><b>DONE</b></span> Add row-count and address sanity checks
  - Check: address continuity, collision detection, and expected row counts per product.
  - Implemented in: [validate-matrix-contract.py](validate-matrix-contract.py)
  - Done when: bad mappings fail early before firmware integration.

- [x] <span style="color:#16a34a"><b>DONE</b></span> Record generator output baselines
  - Track expected counts for key generated artifacts (for D24 and D32).
  - Baseline file: [contract-baseline.md](contract-baseline.md)
  - Done when: regressions are obvious in code review.

## P2 - Workflow hardening

- [x] <span style="color:#16a34a"><b>DONE</b></span> Add CI or pre-merge script for contract drift detection
  - Ensure defs.lock and imported files remain in sync.
  - Implemented in: [check-contract-drift.sh](check-contract-drift.sh)
  - Done when: drift is blocked automatically.

- [x] <span style="color:#16a34a"><b>DONE</b></span> Add release-note convention for contract bumps
  - Require contract version in merge/commit notes when matrix contract changes.
  - Implemented in: [release-notes-contract-convention.md](release-notes-contract-convention.md)
  - Done when: every behavior change maps to a specific contract version.

- [x] <span style="color:#16a34a"><b>DONE</b></span> Establish D24 and D32 smoke test checklist after regeneration
  - Include: no unknown-family errors, no mapping holes, expected generated file presence.
  - Implemented in: [smoke-checklist.md](smoke-checklist.md)
  - Done when: each contract bump has repeatable validation evidence.

## P3 - Evolution work (after stabilization)

- [ ] <span style="color:#d97706"><b>IN PROGRESS</b></span> Expand contract beyond current CSV set as needed
  - Candidates: tier-2 product files such as dsp.csv and logic.csv when authoritative.
  - Staged: optional DSP config tracking added via defs.lock keys D24_DSP_CFG_SHA256 and D32_DSP_CFG_SHA256 (ABSENT until mx26 provides files).
  - Resume: when mx26 adds src/pd/d24/dsp.csv or src/pd/d32/dsp.csv, run ./regenerate-dsp-contract.sh --update-lock to pin them automatically.
  - Workflow notes: [workflow-quickstart.md](workflow-quickstart.md)
  - Done when: additional config sources are versioned with same lock and hash model.

- [ ] <span style="color:#d97706"><b>IN PROGRESS</b></span> Reduce transitional aliases after migration window
  - Plan: [alias-retirement-plan.md](alias-retirement-plan.md)
  - Audit: [alias-audit.md](alias-audit.md) — run python3 audit-compat-aliases.py to refresh.
  - Config: [alias-retire-families.txt](alias-retire-families.txt) — add a family here then run ./sync-from-mx26.sh --update-lock.
  - Retired (non-DSP-mapped, safe to remove): FxDuckThr, MainMtr, MainPeqGain.
  - Blocked (alias rows remain in matrix, need mx26 to remove from master definition):
    - FxEqHi → canonical FxEqPresence; 6 alias rows, **0 DSP-mapped**. Ready to retire once mx26 drops FxEqHi from master.
    - AuxPeq → canonical AuxGeq; 144 alias rows, **0 DSP-mapped**. Ready to retire once mx26 drops AuxPeq from master.
    - SubMtr → canonical AaSubMtr; 1 alias row, **0 DSP-mapped**. Ready to retire once mx26 drops SubMtr from master.
    - AaChanDynMtr → canonical AaChanCompMtr; 32 alias rows, **0 DSP-mapped**. Ready to retire once mx26 drops DynMtr from master.
    - FxLfoMode → canonical FxLfoShape; 6 alias rows, **0 DSP-mapped**. Ready to retire once mx26 drops FxLfoMode from master.
  - Resume sequence for each blocked family:
    1. Make rename/alias removal in mx26 master cell library.
    2. Regenerate mx26 mx-master CSVs and tag new contract version.
    3. Run ./regenerate-dsp-contract.sh --update-lock in mx-dsp.
    4. Confirm audit shows alias rows = 0 and no DSP mapping gaps.
    5. Add family to alias-retire-families.txt and run --update-lock again.
  - Done when: all six audit families show status "ready (alias absent)".

## P4 - DSP mapping gap closure (tracked work)

- [ ] <span style="color:#2563eb"><b>NEXT</b></span> Add ChanRtgFxPick family to mx26 master (192 cells, 32 ch × 6 FX pick modes)
  - Why: gen_dsp.py defines pre/post EQ/Fdr pick-off points but matrix has no rows.
  - Action: raise mx26 PR to add ChanRtgFxPick001-006 per channel in d32-mx-master.csv.
  - Blocked on: mx26 repo access.

- [ ] <span style="color:#2563eb"><b>NEXT</b></span> Add ChanEqLpf family to mx26 master (32 cells)
  - Why: channel EQ LPF is a real DSP parameter missing from the matrix.

- [ ] <span style="color:#2563eb"><b>NEXT</b></span> Add AuxLimiterAtt/Rel families to mx26 master (24 cells)
  - Why: aux limiter timing parameters are defined in DSP but not in matrix.

- [ ] <span style="color:#2563eb"><b>NEXT</b></span> Add GrpComp/MainComp sidechain params to mx26 master (56 cells)
  - Why: compressor advanced params (DetSrc, EqPos, FilterHpf/Lpf/On/Q, Key, LimMode) defined in DSP but absent from matrix.

- [ ] <span style="color:#6b7280"><b>BLOCKED/DEFERRED</b></span> Implement Group GEQ DSP node
  - Why: matrix has 48 GrpPeq rows (4 groups × 12 bands) but no GEQ nodes in dsp.csv.
  - Action: add group GEQ nodes to dsp.csv (gen_dsp_csv.py source), then rename GrpPeq→GrpGeq.
  - Blocked on: CCES license for build verification.

- [ ] <span style="color:#6b7280"><b>BLOCKED/DEFERRED</b></span> Retire AuxPeq alias (pending mx26)
  - Why: 192 stale alias rows in matrix. DSP now maps canonical AuxGeq correctly.
  - Action: once mx26 removes AuxPeq from master, run prune then remove from audit script.

## Workflow reference (to resume quickly)

| Command | Purpose |
|---|---|
| ./regenerate-dsp-contract.sh | Full sync + validate + generate |
| ./regenerate-dsp-contract.sh --update-lock | Same but bumps defs.lock hashes |
| ./check-contract-drift.sh | Pre-merge check |
| ./check-contract-drift.sh --strict | Strict gate — fails on any unintended drift |
| python3 audit-compat-aliases.py | Refresh alias-audit.md |
| python3 validate-matrix-contract.py | MxAdd continuity + family allowlist check |

## State on last save (2026-07-16)

- Contract version: defs-v2026.07.15
- Source commit: 96c54d0632a43bfcd53a3ae3012393949bfbdc3c
- D24 matrix rows: 4835
- D32 matrix rows: 6694
- D32 cells matched/backfilled: 5056 (final after all naming renames)
- Alias families retired: 3 of 6 (FxDuckThr, MainMtr, MainPeqGain — 0 rows removed, already absent)
- Alias families with DSP de-risked (0 DSP-mapped, waiting on mx26 to remove alias rows):
  - FxEqHi→FxEqPresence (6 rows), AuxPeq→AuxGeq (144 rows), SubMtr→AaSubMtr (1 row)
  - AaChanDynMtr→AaChanCompMtr (32 rows), FxLfoMode→FxLfoShape (6 rows)
- DSP gap (final): 349 DSP cells not in matrix (all need mx26 master additions), 1140 matrix cells without DSP mapping
- Bug fixes applied 2026-07-16:
  - gen_dsp.py: stripped blank column header from read_matrix_csv()
  - gen_dsp.py: expand_geq renamed cell suffix Peq→Geq (+220 cells matched)
  - defs.lock: D32_MATRIX_SHA256 updated to 0eb2b04b...
  - contract-baseline.md: metrics and hash updated
- Tier-2 DSP config slots: staged and hash-tracked as ABSENT
- All P0, P1, P2 tasks complete.

## DSP mapping gap summary (2026-07-16)

### DSP cells not in matrix (349) — mx26 action required

Each family below exists in the DSP (`dsp_address_map.md`) but has no rows in `_matrix.csv`. The mx26 agent must add these rows to `src/pd/d32/d32-mx-master.csv`.

**How to add a row**: copy an existing adjacent cell of the same ShFunction group, increment MxAdd sequentially, set `_Cell` to the exact name, set `Type` and `Table` as specified, leave DspSpi/DspPage/DspAdd blank (filled by gen_dsp.py after sync).

| Family | Count | Cell name range | ShFunction (copy from) | Type/RampProfile | Table |
|---|---|---|---|---|---|
| ChanRtgFxPick | 192 | `Chan001RtgFxPick001`..`Chan032RtgFxPick006` | Chan_Rtg (Chan001RtgFxSend001) | InstantCtl | — |
| ChanEqLpf | 32 | `Chan001EqLpf001`..`Chan032EqLpf001` | Chan_Eq (Chan001EqHpf001) | EqSafe | `0=1000/127=20000/[Log]` |
| AuxLimiterAtt | 12 | `Aux001LimiterAtt001`..`Aux012LimiterAtt001` | — (Aux001LimiterOn001) | DynSafe | `0=0.1/127=100/[Log]` |
| AuxLimiterRel | 12 | `Aux001LimiterRel001`..`Aux012LimiterRel001` | — (Aux001LimiterOn001) | DynSafe | `0=5/127=2000/[Log]` |
| GrpCompDetSrc | 4 | `Grp001CompDetSrc001`..`Grp004CompDetSrc001` | GrpComp (Grp001CompOn001) | InstantCtl | — |
| GrpCompEqPos | 4 | `Grp001CompEqPos001`..`Grp004CompEqPos001` | GrpComp | InstantCtl | — |
| GrpCompFilterHpf | 4 | `Grp001CompFilterHpf001`..`Grp004CompFilterHpf001` | GrpComp | InstantCtl | `0=20/64=1000/[Log]` |
| GrpCompFilterLpf | 4 | `Grp001CompFilterLpf001`..`Grp004CompFilterLpf001` | GrpComp | InstantCtl | `0=500/127=20000/[Log]` |
| GrpCompFilterOn | 4 | `Grp001CompFilterOn001`..`Grp004CompFilterOn001` | GrpComp | InstantCtl | — |
| GrpCompFilterQ | 4 | `Grp001CompFilterQ001`..`Grp004CompFilterQ001` | GrpComp | InstantCtl | `0=0.1/14=10/[Log]` |
| GrpCompKey | 4 | `Grp001CompKey001`..`Grp004CompKey001` | GrpComp | InstantCtl | — |
| GrpCompLimMode | 4 | `Grp001CompLimMode001`..`Grp004CompLimMode001` | GrpComp | InstantCtl | — |
| GrpGateDetSrc | 4 | `Grp001GateDetSrc001`..`Grp004GateDetSrc001` | GrpGate (Grp001GateOn001) | InstantCtl | — |
| GrpGateFilterHpf | 4 | `Grp001GateFilterHpf001`..`Grp004GateFilterHpf001` | GrpGate | InstantCtl | `0=20/64=1000/[Log]` |
| GrpGateFilterLpf | 4 | `Grp001GateFilterLpf001`..`Grp004GateFilterLpf001` | GrpGate | InstantCtl | `0=500/127=20000/[Log]` |
| GrpGateFilterOn | 4 | `Grp001GateFilterOn001`..`Grp004GateFilterOn001` | GrpGate | InstantCtl | — |
| GrpGateFilterQ | 4 | `Grp001GateFilterQ001`..`Grp004GateFilterQ001` | GrpGate | InstantCtl | `0=0.1/14=10/[Log]` |
| MainCompDetSrc | 4 | `Main001CompDetSrc001`..`Main004CompDetSrc001` | MainComp (Main001CompOn001) | InstantCtl | — |
| MainCompEqPos | 4 | `Main001CompEqPos001`..`Main004CompEqPos001` | MainComp | InstantCtl | — |
| MainCompFilterHpf | 4 | `Main001CompFilterHpf001`..`Main004CompFilterHpf001` | MainComp | InstantCtl | `0=20/64=1000/[Log]` |
| MainCompFilterLpf | 4 | `Main001CompFilterLpf001`..`Main004CompFilterLpf001` | MainComp | InstantCtl | `0=500/127=20000/[Log]` |
| MainCompFilterOn | 4 | `Main001CompFilterOn001`..`Main004CompFilterOn001` | MainComp | InstantCtl | — |
| MainCompFilterQ | 4 | `Main001CompFilterQ001`..`Main004CompFilterQ001` | MainComp | InstantCtl | `0=0.1/14=10/[Log]` |
| MainCompKey | 4 | `Main001CompKey001`..`Main004CompKey001` | MainComp | InstantCtl | — |
| MainCompLimMode | 4 | `Main001CompLimMode001`..`Main004CompLimMode001` | MainComp | InstantCtl | — |
| SubEqShelf | 2 | `Sub001EqShelf001`..`Sub001EqShelf002` | SubEq (Sub001EqOn001) | InstantCtl | — |
| SubLimiterAtt | 1 | `Sub001LimiterAtt001` | SubLim (Sub001LimiterOn001) | DynSafe | `0=0.1/127=100/[Log]` |
| SubLimiterRel | 1 | `Sub001LimiterRel001` | SubLim | DynSafe | `0=5/127=2000/[Log]` |
| SubCompDetSrc | 1 | `Sub001CompDetSrc001` | SubComp (Sub001CompOn001) | InstantCtl | — |
| SubCompEqPos | 1 | `Sub001CompEqPos001` | SubComp | InstantCtl | — |
| SubCompFilterHpf | 1 | `Sub001CompFilterHpf001` | SubComp | InstantCtl | `0=20/64=1000/[Log]` |
| SubCompFilterLpf | 1 | `Sub001CompFilterLpf001` | SubComp | InstantCtl | `0=500/127=20000/[Log]` |
| SubCompFilterOn | 1 | `Sub001CompFilterOn001` | SubComp | InstantCtl | — |
| SubCompFilterQ | 1 | `Sub001CompFilterQ001` | SubComp | InstantCtl | `0=0.1/14=10/[Log]` |
| SubCompKey | 1 | `Sub001CompKey001` | SubComp | InstantCtl | — |
| SubCompLimMode | 1 | `Sub001CompLimMode001` | SubComp | InstantCtl | — |
| SubRtgDca | 1 | `Sub001RtgDca001` | SubRtg (Sub001RtgLevel001) | InstantCtl | — |
| MainRtgDca | 1 | `Main001RtgDca001` | MainRtg (Main001RtgLevel001) | InstantCtl | — |
| MainRtgMute | 1 | `Main001RtgMute001` | MainRtg | InstantCtl | — |
| UsbLevel | 1 | `Usb001Level001` | Usb | GainFast | `0=-20/127=6/[Lin]` |
| UsbOn | 1 | `Usb001On001` | Usb | InstantCtl | — |

After adding rows and regenerating the mx26 contract, run `./regenerate-dsp-contract.sh --update-lock` in this repo to sync and verify.

### Alias rows to remove from mx26 master — mx26 action required

Remove all rows whose `_Cell` matches these prefixes from `src/pd/d32/d32-mx-master.csv`. The DSP already maps to canonical names; these are dead alias rows.

| Alias prefix | Count | Canonical (already in matrix) | Notes |
|---|---|---|---|
| `Aux???Peq???` | 144 | `Aux???Geq001`..`Aux???Geq028` | Aux GEQ alias — DSP now uses AuxGeq |
| `Fx???EqHi???` | 6 | `Fx???EqPresence001` | FX high EQ alias — DSP now uses EqPresence |
| `Sub???Mtr???` | 1 | `AaSub???Mtr001` | Sub meter alias — DSP now uses AaSubMtr |
| `AaChan???DynMtr???` | 32 | `AaChan???CompMtr001` | Comp GR meter alias — DSP now uses CompMtr |
| `Fx???LfoMode???` | 6 | `Fx???LfoShape001` | LFO mode alias — DSP now uses LfoShape |

After removing alias rows and regenerating the mx26 contract, run `./sync-from-mx26.sh` then `prune-compat-aliases.py` in this repo, and update `audit-compat-aliases.py` to move those families from PAIRS to RETIRED.

### Matrix cells without DSP mapping — categorized (no mx26 action needed for most)
| Family | Count | Action |
|---|---|---|
| ChanMuteGrp | 256 | MCU-only routing flag — no DSP needed |
| FxRtgAuxOn/Send | 144 | MCU-only routing — no DSP needed |
| ChanRtgMatrixOn/Send | 128 | MCU-only routing — no DSP needed |
| FxMuteGrp | 48 | MCU-only mute group — no DSP needed |
| GrpPeq | 48 | Group GEQ — needs new GEQ DSP node in dsp.csv (CCES blocked) |
| ChanAntiClip/Color/CueSel/LcrOn/Link/PadOn/InsertOn | 224 | MCU-only config — no DSP needed |
| FxPingPongStart/ReturnWetLock/Tap | 18 | MCU-only FX triggers — no DSP needed |
| PhonesLevel/Src, TalkRtg, NoiseRtg, MatrixRtg, misc | ~80 | MCU-only routing/config |

## Owners and cadence

- Owner: DSP workflow maintainer
- Review cadence: update this file on every contract bump and at least once per week while alias retirement is active
