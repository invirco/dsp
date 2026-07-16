# alias audit

Status: active
Date: 2026-07-15
Scope: compatibility alias usage in MW/D32/MX/_matrix.csv.

| Alias family | Canonical family | Alias rows | Alias DSP-mapped | Canonical rows | Status | Notes |
|---|---|---:|---:|---:|---|---|
| FxDuckThr | FxDuckSens | 0 | 0 | 6 | ready (alias absent) | Legacy threshold alias of DuckSens |
| FxEqHi | FxEqPresence | 6 | 6 | 6 | in progress (alias still DSP-mapped) | Legacy FX high EQ alias |
| AuxPeq | AuxGeq | 144 | 144 | 336 | in progress (alias still DSP-mapped) | Compatibility alias for GEQ gains |
| MainPeqGain | MainGeq | 0 | 0 | 28 | ready (alias absent) | Compatibility alias for main GEQ gains |
| MainMtr | AaMainMtr | 0 | 0 | 8 | ready (alias absent) | Unprefixed main meter alias |
| SubMtr | AaSubMtr | 1 | 1 | 1 | in progress (alias still DSP-mapped) | Unprefixed sub meter alias |

## Gate for retirement

A family can be removed when:
- alias rows are 0 in generated matrix,
- canonical family rows are non-zero,
- strict drift and smoke checks pass.
