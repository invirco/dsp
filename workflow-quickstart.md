# workflow quickstart

Status: active
Date: 2026-07-15
Audience: day-to-day mx26 -> mx-dsp workflow users.

## Normal daily flow

1. Sync + validate + regenerate:
   - ./regenerate-dsp-contract.sh
2. Optional pre-merge check:
   - ./check-contract-drift.sh
3. Strict merge gate (if branch is expected clean on contract files):
   - ./check-contract-drift.sh --strict
4. Optional alias retirement signal check:
   - python3 audit-compat-aliases.py

## Intentional contract bump flow

1. Pull/update mx26 source checkout.
2. Bump lock and hashes:
   - ./regenerate-dsp-contract.sh --update-lock
3. Re-run normal flow to confirm lock-consistent state:
   - ./regenerate-dsp-contract.sh
4. Complete smoke checklist:
   - see smoke-checklist.md
5. Include contract bump note fields:
   - see release-notes-contract-convention.md

## Where files land

- D24:
  - MW/D24/DEFS/d24.csv
  - MW/D24/FW/fw.csv
  - MW/D24/MX/d24-mx-master.csv
  - MW/D24/MX/_matrix.csv
  - MW/D24/DSPCFG/dsp.csv (optional, only when present in mx26)
- D32:
  - MW/D32/DEFS/d32.csv
  - MW/D32/FW/fw.csv
  - MW/D32/MX/d32-mx-master.csv
  - MW/D32/MX/_matrix.csv
  - MW/D32/DSPCFG/dsp.csv (optional, only when present in mx26)

## Lock behavior

- defs.lock is authoritative for expected contract hashes.
- Optional tier-2 DSP config hash keys use ABSENT until mx26 provides src/pd/d24/dsp.csv or src/pd/d32/dsp.csv.
- Once those files appear upstream, run --update-lock intentionally to pin them.
- Sync flow also applies configured alias retirement pruning from alias-retire-families.txt.

## Troubleshooting

- Hash mismatch: verify intended source change, then run --update-lock if this is an approved bump.
- Unexpected family error: review validate-matrix-contract.py output, then update matrix-families-allowlist.txt intentionally.
- Missing mx26 source path: set MX26_REPO to the correct local checkout path.
