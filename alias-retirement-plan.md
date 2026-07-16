# alias retirement plan

Status: active
Date: 2026-07-15
Scope: phased removal of compatibility aliases from D32 contract outputs.

## Why

Compatibility aliases are useful during migration but increase long-term ambiguity and maintenance cost. Retirement must be deliberate and evidence-based.

## Inputs

- Matrix data: MW/D32/MX/_matrix.csv
- Alias audit: alias-audit.md
- Contract checks: check-contract-drift.sh, smoke-checklist.md

## Phases

1. Baseline
- Run audit-compat-aliases.py and commit alias-audit.md.
- Confirm canonical family exists for each alias candidate.

2. Deprecation
- Mark alias families as deprecated in product-definition docs.
- Keep generation behavior unchanged for one contract cycle.

3. Removal
- Remove alias rows at source definition level.
- Regenerate contract artifacts and run full checks.

4. Stabilization
- Keep strict drift checks and smoke checks across at least one additional contract bump.

## Retirement gate per alias family

All must be true:
- Alias rows: 0
- Canonical rows: >0
- Alias DSP-mapped rows: 0
- regenerate-dsp-contract.sh passes
- check-contract-drift.sh --strict passes
- Smoke checklist complete

## Command sequence

1. python3 audit-compat-aliases.py
2. ./regenerate-dsp-contract.sh
3. ./check-contract-drift.sh --strict

## Output artifacts

- alias-audit.md
- Updated contract-baseline.md metrics and notes
- release note entry per release-notes-contract-convention.md
