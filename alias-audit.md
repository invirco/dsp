# alias audit

Status: active
Date: 2026-07-18
Scope: compatibility alias usage in MW/D32/MX/_matrix.csv.

| Alias family | Canonical family | Alias rows | Alias DSP-mapped | Canonical rows | Status | Notes |
|---|---|---:|---:|---:|---|---|
| (none) | (none) | 0 | 0 | 0 | n/a | No active transitional alias families |

## Gate for retirement

A family can be removed when:
- alias rows are 0 in generated matrix,
- canonical family rows are non-zero,
- strict drift and smoke checks pass.

## Retired families

| Alias family | Canonical family | Notes |
|---|---|---|
| FxDuckThr | FxDuckSens | Legacy threshold alias of DuckSens |
| MainPeqGain | MainGeq | Compatibility alias for main GEQ gains |
| MainMtr | AaMainMtr | Unprefixed main meter alias |
| FxEqHi | FxEqPresence | Legacy FX high EQ alias |
| AuxPeq | AuxGeq | Compatibility alias for GEQ gains |
| SubMtr | AaSubMtr | Unprefixed sub meter alias |
| AaChanDynMtr | AaChanCompMtr | DynMtr renamed to CompMtr for compressor GR |
| FxLfoMode | FxLfoShape | LfoMode renamed to LfoShape |
