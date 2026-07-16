# mx26 <-> mx-dsp integration guide

Status: draft
Date: 2026-07-15
Scope: define how matrix simplification work in mx26 drives DSP implementation work in mx-dsp without coupling the repos.

## 1) Goal

Keep mx26 as the matrix definition hub and keep mx-dsp as a DSP implementation repo.

This gives you:
- One source of truth for product matrix intent (mx26)
- One place for DSP execution details and generated firmware assets (mx-dsp)
- Explicit, versioned handoff between intent and implementation

## 2) What each repo should own

## mx26 (definition hub)
- Product feature definitions (example: src/pd/d24.csv, src/pd/d32.csv)
- Product hardware config definitions (example: src/pd/d24/fw.csv, src/pd/d32/fw.csv)
- Cell library and generated per-product masters (d24-mx-master.csv, d32-mx-master.csv)
- Matrix-generation tools (tools/def_master.py, tools/expand_matrix.py)
- Topology and policy docs (sot.md, matrix_direction.md)

## mx-dsp (implementation spoke)
- DSP architecture and mapping docs (MW/D32/DSP/dsp-def.md)
- DSP codegen and backfill logic (MW/D32/DSP/gen_dsp.py)
- SHARC source and generated outputs (MW/D32/DSP/SHARC/...)
- Product runtime matrix snapshots used by firmware build and validation (MW/*/MX/_matrix.csv)
- Shared compatibility references used by local tooling (shared/mx_master.csv)

## 3) Current coupling points already in mx-dsp

These files show where matrix-definition changes will land first:
- sync-from-app.sh pulls shared/mx_master.csv from another repo path
- MW/D32/DSP/gen_dsp.py reads MW/D32/MX/_matrix.csv and backfills DSP columns
- MW/D32/DSP/dsp-def.md describes matrix-to-DSP mapping assumptions
- shared/mx_master.csv contains the matrix cell library used as a compatibility baseline

Practical conclusion:
- The real integration seam is the CSV contract, not source-code imports.

## 4) Recommended contract between repos

Use a versioned definitions contract published from mx26 and consumed by mx-dsp.

## Contract payload (minimum)
For each product (at least D24 and D32), publish:
- src/pd/dNN.csv (feature definition)
- src/pd/dNN/fw.csv (hardware config definition)
- src/pd/dNN-mx-master.csv (expanded product master)
- Generated _matrix.csv for that product
- Manifest file with sha256 hashes for all contract files
- A contract version string (tag or timestamp + commit)

Example lock metadata in mx-dsp (new file concept):
- defs.lock with fields:
  - source_repo = invirco/mx26
  - source_commit = <sha>
  - contract_version = defs-vYYYY.MM.DD
  - product hashes for D24/D32 files

## Why this matters for your simplification work
As matrix definitions become simpler and more expressive in mx26, mx-dsp gets a stable intake format. New capability only needs definition changes first, then deliberate uptake in DSP tooling.

## 5) Impact of matrix simplification/power upgrades on mx-dsp

When you simplify or extend matrix semantics in mx26, mx-dsp is affected in three layers.

## Layer A: schema and naming impact (highest risk)
Changes to cell names, ranges, or routing families affect:
- Parsing assumptions in MW/D32/DSP/gen_dsp.py
- Existing DspAdd/DspSpi backfill matching
- Any firmware tables generated from the matrix rows

Guardrail:
- Keep backward-compatible aliases for renamed families during transition windows.
- Fail loudly when unknown cell families appear (already aligned with mx26 no-fallback policy).

## Layer B: count/capability impact (medium risk)
Changes like ch=24->32, aux count, fx slot counts, or new routing buses affect:
- Address allocation density and table sizes
- SHARC dispatch table dimensions
- ghost_cells outputs and firmware memory footprint

Guardrail:
- Validate row counts and address continuity on every contract update.
- Compare generated totals against known product ceilings before merge.

## Layer C: behavior profile impact (medium risk)
Changes to ramping classes, routing semantics, or control class intent affect:
- Ramp metadata and profile selection
- Runtime behavior consistency versus current field units
- Scene/recall expectations in control paths

Guardrail:
- Freeze behavior-class mapping per contract version.
- Introduce behavior changes behind explicit contract bumps.

## 6) Operating workflow (recommended)

1. Author definitions in mx26
- Update dNN.csv and product config rows.
- Regenerate dNN-mx-master.csv and _matrix.csv.
- Publish manifest + version tag.

2. Consume in mx-dsp
- Run a sync script in mx-dsp that copies contract files and verifies hashes.
- Update defs.lock in one reviewable commit.

3. Regenerate DSP artifacts in mx-dsp
- Run MW/D32/DSP/gen_dsp.py (and any companion generators).
- Regenerate ghost cells, address maps, and SHARC params.

4. Validate
- No unknown-family parser errors.
- No address collisions or missing mappings.
- Product-level smoke checks for D24 and D32.

5. Promote
- Merge with contract version recorded in commit message and release notes.

## 7) Suggested near-term changes in mx-dsp

1. Replace sync-from-app.sh with sync-from-mx26.sh
- Source from mx26 contract outputs, not app-local paths.
- Keep a compatibility mode until cutover is complete.

2. Add defs.lock to mx-dsp root
- Pin exact mx26 commit/version for repeatable builds.

3. Add contract verification script
- Verify sha256 for imported CSVs before running generators.

4. Add a matrix-compat check
- Compare incoming matrix families against known support in gen_dsp.py.
- Emit actionable errors for unsupported new families.

## 8) Division of authority

- mx26 decides what the matrix means.
- mx-dsp decides how DSP firmware realizes that meaning.
- The contract version decides exactly which meaning an mx-dsp build is targeting.

This keeps the matrix concept both simpler (single definition source) and more powerful (explicit versioned evolution) without forcing monorepo coupling.

## 9) Minimum adoption plan

Phase 1 (now)
- Keep current mx-dsp build flow.
- Add defs.lock and hash verification.
- Import mx26 d24/d32 contract outputs manually at first.

Phase 2
- Automate sync + verify + regenerate in one command.
- Add CI check that fails if defs.lock and imported files diverge.

Phase 3
- Expand contract to include additional tier-2 files (dsp.csv/logic.csv) when they become authoritative in mx26.

## 10) Success criteria

You know the repos are working together correctly when:
- Any mx26 matrix change appears in mx-dsp through a single lockfile bump.
- Regeneration is deterministic and hash-verified.
- D24 and D32 can intentionally lag or advance by contract version without ambiguity.
- Cross-repo discussions reference contract versions instead of ad-hoc file copies.
