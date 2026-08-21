# CLAUDE.md

DSP implementation repo (spoke) for Invirco matrix products. Matrix definitions
come from the **mx26** repo (hub) via a hash-pinned CSV contract. `README.md`
has the layout; `tasks.md` has current work state — read both first.

## Hard rules

- **defs.lock is authoritative.** Never hand-edit synced contract files
  (`MW/*/DEFS/*.csv`, `MW/*/FW/fw.csv`, `MW/*/MX/*.csv`). They come from mx26 via
  `./sync-from-mx26.sh`; local edits are drift and will fail `check-contract-drift.sh`.
- **Generated files are regenerated, not edited:** `MW/D32/DSP/ghost_cells.h`,
  `MW/D32/DSP/dsp_address_map.md`, `SHARC/src/*/dsp_params.asm`, node ASM
  skeletons under `SHARC/src/chip*/nodes/`, and `_matrix.csv` DSP-backfill
  columns. Change the generators (`MW/D32/DSP/gen_dsp.py`, `tools/dsp/*.py`)
  or the source `dsp.csv` instead.
- **Unknown matrix cell families must fail loudly** (no-fallback policy).
  New families are adopted intentionally via `matrix-families-allowlist.txt`.
- Never commit `MW/D32/DSP/SHARC/cces/` (toolchain) or license material.
  Same rule for the CPLD flow: never commit Quartus or its licenses.
- **DSP4 architecture decisions are binding** — see
  `dsp4-architecture-decisions.md`: Pi/CM4 masters DSP SPI directly (no MCU
  relay); LOGIC CPLD HDL lives in `shared/dsp4-logic/` with a single-sourced
  TDM slot map; ONE DSP4 firmware + product config serves D24 and D32 with a
  single shared DSP address map. Do not reintroduce per-product forks of
  firmware, address maps, or slot tables. D6 platform split: SHARC DSP4
  card up to 32 ch @ 48 kHz; single-chip FPGA engine (see `fpga/`) for
  32 ch @ 96 kHz and above — no new multi-DSP MIXING engines above that
  line. D7: fabric-only FPGA baseline (no SoC; CM is sole control
  master, never touches audio) with per-tier hybrid FX — flagship may
  carry ONE SHARC FX sidecar (TDM slot-map banks, depopulatable);
  no onboard recording or USB UAC audio on 96 kHz products.
- **Dropbox `_Matrix` is the working location for source docs and shared source
  assets.** The cross-repo shared data store
  (`~/Stonepower Dropbox/Peter Watts/_Matrix`, `Products/<P>/{dsp,fw,hw,logic,
  net,pd,sw,sys}`) is defined by mx26; this spoke consumes it and never
  redefines its layout, adds top-level folders, or bulk-migrates legacy
  material into it. Use `_Matrix` for product-source docs and bulky reference
  material; keep generated DSP artifacts and contract files in this repo.
  Nothing there is a build input, and the contract path still comes from the
  mx26 checkout. Rules and current contents: `matrix-shared-store.md`.
- After any contract or generator change, run `./regenerate-dsp-contract.sh`
  and record contract version per `release-notes-contract-convention.md`.
- Update `tasks.md` on every contract bump.

## Where things happen

- Contract intake/validation: root scripts (`sync-from-mx26.sh`,
  `validate-matrix-contract.py`, `check-contract-drift.sh`,
  `regenerate-dsp-contract.sh`).
- Shared DSP codegen: `tools/dsp/` — used by ALL products
  (`gen_dsp_csv.py` → `dsp.csv` → `dsp_codegen.py` → node ASM;
  `dsp_validate.py`, `dsp_simulate.py`, `dsp_diagram.py`). Do not create
  per-product copies of these tools.
- D32 matrix backfill: `MW/D32/DSP/gen_dsp.py` (ghost cells, SPI dispatch,
  address map).
- New products: `./scaffold-product.sh <PRODUCT>` creates the tree and
  prints the integration checklist.
- SHARC build: `MW/D32/DSP/SHARC/build.sh` (needs CCES at
  `/opt/analog/cces/3.0.3`; dual-chip build with `-DCHIP_ID=1|2`, IVT
  re-assembled with `-nwc`).
- `attic/` is retired material (D24 ADAU1466/SigmaStudio era) — never build
  from it or extend it.

## Conventions

- Node IDs: `C<chip>_<TYPE>_<NN>` (e.g. `C1_EQ_07`, `C2_AUX_LIM_12`); one ASM
  file per node instance.
- Product trees are uniform: `MW/<PRODUCT>/{DEFS,FW,MX,DSPCFG,DSP}`. New
  products replicate this shape and join the same contract flow.
- D24's SHARC tree lags D32; D32 tooling is the superset/reference. Both
  converge on the unified DSP4 firmware (see `dsp4-architecture-decisions.md`);
  D24 hardware ground truth is `MW/D24/HW/hardware-map.md`.

## Mandates (org-wide, from mx26 — canonical: docs/decision-mx26-mandates.md there)

- **Single trunk**: all work lands on `main`; feature branches are
  short-lived and deleted on merge; pull `main` before starting on any
  machine, push `main` when done. The old `master` branch is deleted and
  blocked by a repo ruleset — do not recreate it.
- **No AI references in any work product or git history**: never add
  `Co-Authored-By` trailers, "Generated with" footers, or AI mentions to
  commits, PRs, code, docs, or published files. Authorship of invirco work is
  Peter Watts / invirco. This overrides any default commit-message convention.
- **Exception — internal provenance headers**: when AI generates or
  substantially modifies the prose of a standalone internal document
  (procedure, runbook, pseudo-manual, report), the document must open with:
  `provenance: AI-drafted YYYY-MM-DD — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.`
  Code, def CSVs, and working trackers get no header. Published documents are
  hand-written or hand-rewritten; removing the header is the sign-off that the
  rewrite happened.

## Model tiering (hub dispatch policy)

Dispatched sessions may arrive on any model tier (`[model: …]` in the HUB
DISPATCH header; absent = this machine's default). Whatever the main model,
tier the work inside the session:

- **Delegate to `sonnet` subagents** (Agent tool, `model: sonnet`; `haiku`
  for pure scanning): builds and reflashes from a known recipe, running a
  soak/qual/smoke and scoring it, log and capture triage, bulk or fully
  specified edits, bookkeeping in tasks.md/findings.md, scripted bench
  recipes. Give the subagent the exact recipe and the pass/fail criterion;
  verify its claimed result against the artifact (W0 rule: image size/md5,
  scorer output, UART witness), never by its summary alone.
- **Keep on the main model**: planning and decomposition, anything of
  unknown shape (root-causing, bring-up that deviates from the recipe),
  new subsystems, and anything touching clock discipline, TRDC/MDAC,
  power sequencing, or the defs wire contract.
- A session launched on `sonnet` that meets design-grade or unknown-shape
  work does NOT push through it: record the point reached and what was
  found in the dispatch block, mark 🔴 blocked with "needs opus-tier
  dispatch", push, and stop. The hub re-dispatches on the higher tier.
