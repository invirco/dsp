# alias audit

Status: active
Date: 2026-07-16
Scope: compatibility alias usage in MW/D32/MX/_matrix.csv.

| Alias family | Canonical family | Alias rows | Alias DSP-mapped | Canonical rows | Status | Notes |
|---|---|---:|---:|---:|---|---|
| FxEqHi | FxEqPresence | 6 | 0 | 6 | in progress (alias still present) | Legacy FX high EQ alias |
| AuxPeq | AuxGeq | 144 | 0 | 336 | in progress (alias still present) | Compatibility alias for GEQ gains |
| SubMtr | AaSubMtr | 1 | 0 | 1 | in progress (alias still present) | Unprefixed sub meter alias |
| AaChanDynMtr | AaChanCompMtr | 32 | 0 | 32 | in progress (alias still present) | DynMtr renamed to CompMtr for compressor GR |
| FxLfoMode | FxLfoShape | 6 | 0 | 6 | in progress (alias still present) | LfoMode renamed to LfoShape |

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
