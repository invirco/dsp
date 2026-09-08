# workflow quickstart

Status: active
Date: 2026-09-08
Audience: day-to-day defs -> mx-dsp workflow users.

## Source-doc location

- The DEFINITIONS are the `defs` submodule (`defs/`), pinned by `defs.lock`.
- For source documents, reference material, and bulky source assets, work from
the Dropbox `_Matrix` store under `Products/<Product>/...`.
- Keep generated DSP artifacts, contract files, implementation notes, and
build outputs in this repo.
- Do not create repo-local copies of the shared source docs; reference the
store location and keep the repo free of large binaries.

## Normal daily flow

1. Sync + validate + regenerate:
   - ./regenerate-dsp-contract.sh
2. Optional pre-merge check:
   - ./check-contract-drift.sh
3. Strict merge gate (if branch is expected clean on contract files):
   - ./check-contract-drift.sh --strict
4. Optional check that the expansion in this tree is untouched:
   - python3 audit-compat-aliases.py

## Intentional contract bump flow

1. Move the defs submodule onto the new defs-v* tag:
   - git -C defs fetch --tags && git -C defs checkout defs-vYYYY.MM.DD
2. Re-pin the lock:
   - ./regenerate-dsp-contract.sh --update-lock
3. Re-run normal flow to confirm lock-consistent state:
   - ./regenerate-dsp-contract.sh
4. Complete smoke checklist:
   - see smoke-checklist.md
5. Include contract bump note fields:
   - see release-notes-contract-convention.md

## Where files come from, and where they land

Read (in the `defs` submodule — never copied into this tree):

- defs/products/d24/{d24.csv,fw.csv}, defs/gen/matrix/d24-mx-master.csv
- defs/products/d32/{d32.csv,fw.csv}, defs/gen/matrix/d32-mx-master.csv
- defs/common/cells/mx_master.csv, defs/common/wire/wire-units.csv
- defs/gen/matrix/{d24,d32}-wire-table.csv

Written (generated, committed):

- MW/D24/MX/_matrix.csv, MW/D32/MX/_matrix.csv
  (expand_matrix.py output + the DSP address backfill from gen_dsp.py)
- MW/D32/DSP/{ghost_cells.h,dsp_address_map.md}
- MW/D32/DSP/SHARC/src/chip{1,2}/dsp_params.asm
- MW/D32/FW/H1S1/Core/{Inc/ghost_cells.h,Src/ghost_cells.c,Inc/mx_dsp_map.h}

## Lock behavior

- defs.lock is authoritative: it pins the defs commit + tag, a hash over the
  whole defs content manifest, the hash of each declaration this repo reads,
  and the hash + matrix generation id of each expansion.
- The pin must be a real defs-v* tag; --update-lock refuses an untagged HEAD.
- --update-lock reads the submodule as checked out, so move it to the intended
  tag FIRST.

## Troubleshooting

- Hash mismatch: verify the intended definition change, then run --update-lock
  if this is an approved bump.
- "defs/ working tree is not the commit this repo records": run
  `git submodule update defs`.
- Unexpected family error: review validate-matrix-contract.py output, then
  update matrix-families-allowlist.txt intentionally.
- Submodule missing after clone: `git submodule update --init defs`.
