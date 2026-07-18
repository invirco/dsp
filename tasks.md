# tasks

Status: active
Date: 2026-07-18
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

- [x] <span style="color:#16a34a"><b>DONE</b></span> Finalize transitional alias retirement cleanup
  - Plan: [alias-retirement-plan.md](alias-retirement-plan.md)
  - Audit: [alias-audit.md](alias-audit.md) — run python3 audit-compat-aliases.py to refresh.
  - Config: [alias-retire-families.txt](alias-retire-families.txt) — add a family here then run ./sync-from-mx26.sh --update-lock.
  - Retired (non-DSP-mapped, safe to remove): FxDuckThr, MainMtr, MainPeqGain.
  - 2026-07-18 status: previously blocked alias families are now absent in generated D32 matrix and retired in local prune/audit config.
    - FxEqHi → FxEqPresence
    - AuxPeq → AuxGeq
    - SubMtr → AaSubMtr
    - AaChanDynMtr → AaChanCompMtr
    - FxLfoMode → FxLfoShape
  - Completed repo cleanup:
    1. Moved five now-absent families from PAIRS to RETIRED in audit-compat-aliases.py.
    2. Added these families to alias-retire-families.txt as a defensive prune guard.
    3. Re-ran ./regenerate-dsp-contract.sh and verified audit/compatibility remain stable.

## P4 - DSP mapping closure follow-up

- [x] <span style="color:#16a34a"><b>DONE</b></span> Sync mx26 matrix additions for prior DSP gap families (2026-07-18)
  - Added upstream and now present in generated matrix: ChanRtgFxPick, ChanEqLpf, AuxLimiterAtt/Rel, GrpComp/MainComp sidechain families, SubEqShelf, SubLimiterAtt/Rel, SubComp sidechain, SubRtgDca, MainRtgDca/Mute, UsbLevel/On.
  - Result: previous 349-cell "DSP not in matrix" gap resolved in current contract sync.

- [ ] <span style="color:#6b7280"><b>BLOCKED/DEFERRED</b></span> Implement Group GEQ DSP node
  - Why: matrix has 48 GrpPeq rows (4 groups × 12 bands) but no GEQ nodes in dsp.csv.
  - Action: add group GEQ nodes to dsp.csv (gen_dsp_csv.py source), then rename GrpPeq→GrpGeq.
  - Progress (2026-07-18): no-build draft patch prepared in MW/D32/DSP/gen_dsp.py with guarded flag --enable-grp-geq-alias for staged mapping.
  - Blocked on: CCES license for build verification.

## Workflow reference (to resume quickly)

| Command | Purpose |
|---|---|
| ./regenerate-dsp-contract.sh | Full sync + validate + generate |
| ./regenerate-dsp-contract.sh --update-lock | Same but bumps defs.lock hashes |
| ./check-contract-drift.sh | Pre-merge check |
| ./check-contract-drift.sh --strict | Strict gate — fails on any unintended drift |
| python3 audit-compat-aliases.py | Refresh alias-audit.md |
| python3 validate-matrix-contract.py | MxAdd continuity + family allowlist check |

## State on last save (2026-07-18)

- Contract version: defs-v2026.07.18
- Source commit: 2f92f8b9ef3465e716ea90bddaa67d91e0da77e8
- D24 matrix rows: 4702
- D32 matrix rows: 6856
- D32 cells matched/backfilled: 5405
- Alias transition state: no active transitional families; all tracked families are now listed under retired in alias audit.
- DSP gap update: previously missing 349 DSP-backed matrix cells were added upstream and are now present.
- Current informational gap: 951 _matrix.csv cells remain without DSP mapping (expected mix of MCU-only and deferred DSP work).
- Tier-2 DSP config slots: still ABSENT in defs.lock (D24_DSP_CFG_SHA256, D32_DSP_CFG_SHA256).
- All P0, P1, P2 tasks complete.

## DSP mapping status (2026-07-18)

- Resolved: mx26 master now includes previously missing families that blocked DSP parity.
- Remaining deferred DSP work:
  - Group GEQ DSP node implementation for existing GrpPeq matrix families (guarded alias bridge prepared; CCES build verification dependency remains).
- Remaining non-mapped matrix controls are currently tracked as expected MCU-only or deferred-path items.

## Owners and cadence

- Owner: DSP workflow maintainer
- Review cadence: update this file on every contract bump and at least once per week while alias retirement is active
