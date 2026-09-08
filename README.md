# mx-dsp

DSP implementation repo for Invirco matrix-based products. Matrix *definitions*
live in the **`invirco/defs`** repo, carried here as the `defs/` submodule and
pinned by `defs.lock` to a `defs-v*` tag; this repo consumes them and turns them
into DSP firmware artifacts (the spoke). mx26 remains the hub for decisions and
dispatch, and consumes the same submodule. See
[mx26-mx-dsp-integration.md](mx26-mx-dsp-integration.md) for the full model.

**This repo is a consumer, not a second source.** Nothing here copies a
definition CSV into the tree, and nothing here rewrites an expansion after
`defs/tools/expand_matrix.py` produced it — both were how this repo grew a
matrix generation of its own (`b4592dfb639e`, which matched neither the tag it
pinned nor the hub). The only DSP-side derived table is the address backfill
gen_dsp.py writes into `_matrix.csv`.

For source documents and bulky source assets, use the Dropbox `_Matrix` store as
the working location. Keep generated DSP artifacts and repo-local implementation
notes here in the repo.

## Layout

```
defs/                         # SUBMODULE: invirco/defs — every product def, the
                              #   cell master, the wire declaration, and the ONLY
                              #   matrix expander. Pinned to a defs-v* tag.
defs.lock                     # pins which defs commit + tag, and the hashes of
                              #   everything read out of it (authoritative)
sync-defs.sh                  # verify the pin, re-expand MW/<P>/MX/_matrix.csv
tasks.md                      # active task tracker — update on every contract bump
scaffold-product.sh           # creates a new MW/<PRODUCT> tree + integration checklist
tools/dsp/                    # shared DSP codegen package (all products)
    dsp_codegen.py            #   dsp.csv -> SHARC ASM (nodes, ramp engine, block_io)
    gen_dsp_csv.py            #   matrix -> dsp.csv graph source
    dsp_validate.py           #   dsp.csv graph rules check
    dsp_simulate.py           #   node-level simulation harness
    dsp_diagram.py            #   dsp.csv -> Graphviz diagram
    wire_contract.py          #   the SPI wire contract, assembled from
                              #   _matrix.csv + the dispatch tables +
                              #   defs/common/wire/wire-units.csv; feeds the
                              #   conformance harness and the D38 inert list
MW/<PRODUCT>/                 # one tree per product (D24, D32, ...)
    MX/    _matrix.csv        # GENERATED: defs/tools/expand_matrix.py output
                              #   + the DSP address backfill from gen_dsp.py.
                              #   The product def, fw.csv and the mx-master it
                              #   came from live in defs/, not here.
    DSP/                      # DSP implementation
        SHARC/                # ADSP-21564 source, codegen tools, build.sh
attic/                        # retired material (D24 ADAU1466/SigmaStudio era, Pi bootloader)
```

Root-level scripts and docs form the contract toolchain (see workflow below).

## Products

| Product | Platform | Status |
|---|---|---|
| D32 | 2× ADSP-21564 SHARC | Active — flagship; full codegen + contract flow |
| D24 | 2× ADSP-21564 SHARC | SHARC skeleton mirroring D32; earlier ADAU1466 era archived in `attic/` |

New matrix products get a new `MW/<PRODUCT>/` tree following the same MX/DSP
shape, driven by the same contract flow; their definitions are added to `defs`.

## Daily workflow

| Command | Purpose |
|---|---|
| `./sync-defs.sh` | Verify the `defs` pin and re-expand `MW/<P>/MX/_matrix.csv` |
| `./regenerate-dsp-contract.sh` | sync-defs + validate + regenerate DSP artifacts |
| `./regenerate-dsp-contract.sh --update-lock` | Same, but re-pin defs.lock (intentional contract bump — move the submodule to the new tag first) |
| `./check-contract-drift.sh [--strict]` | Pre-merge drift gate |
| `python3 validate-matrix-contract.py` | MxAdd continuity + family allowlist check |
| `python3 audit-compat-aliases.py` | Refresh alias-audit.md — proves the expansion in this tree is untouched |
| `python3 tools/dsp/dsp_codegen.py MW/<P>/DSP/SHARC/dsp.csv MW/<P>/DSP/SHARC/src` | Regenerate a product's SHARC source |
| `python3 tools/dsp/dsp_validate.py MW/<P>/DSP/SHARC/dsp.csv` | Validate a product's DSP graph |
| `python3 tools/dsp/dsp_memreport.py MW/<P>/DSP/SHARC/build/chip*.map.xml` | Memory headroom per primary+overflow pool (exit 1 above 90%) |
| `./scaffold-product.sh <PRODUCT>` | Create a new product tree + integration checklist |
| `MW/D32/DSP/SHARC/build.sh` | Assemble + link D32 DXEs (requires CCES at /opt/analog/cces) |
| `MW/D32/DSP/SHARC/conform.sh` | Contract conformance on the live part — a standing per-session bar ([docs/contract/conformance-harness.md](docs/contract/conformance-harness.md)) |
| `MW/D32/DSP/SHARC/dcapar.sh` | The cell-semantics evidence on the part — the DCA cell is host-managed and off the wire (the address is rejected and the bus does not move), and CompPar's default leaves the compressor wet. Runs against either image (`BUILD=0` uses whatever is on the bench), so both fixes have a before |
| `MW/D32/DSP/SHARC/bqgraph.sh` | Is the paired-biquad graph (`DSP4_BQ_GRAPH`) bit-exact against the dynamics-only one? Three builds, one bus capture each, real filter coefficients loaded — at bypass the two cascades are identical by construction and the comparison would prove nothing |
| `python3 tools/dsp/wire_contract.py --product d32 --coverage` | Which documented master cells reach a DSP address, and which are inert |

Quickstart and troubleshooting: [workflow-quickstart.md](workflow-quickstart.md).
Contract-bump checklist: [smoke-checklist.md](smoke-checklist.md) and
[release-notes-contract-convention.md](release-notes-contract-convention.md).

## Key docs

- [tasks.md](tasks.md) — prioritized work state (start here)
- [mx26-mx-dsp-integration.md](mx26-mx-dsp-integration.md) — repo contract model
- [matrix-shared-store.md](matrix-shared-store.md) — Dropbox `_Matrix` cross-repo
  data store (mx26-owned; where large binaries live instead of git)
- [contract-baseline.md](contract-baseline.md) — expected generator output counts
- [alias-retirement-plan.md](alias-retirement-plan.md) / [alias-audit.md](alias-audit.md) — cell-family alias lifecycle
- `MW/D32/DSP/dsp-def.md`, `MW/D32/DSP/dsp_address_map.md` — D32 DSP architecture and address map

## Notes

- The CCES toolchain is **not** tracked in git. Install CCES 3.0.3 to
  `/opt/analog/cces/3.0.3` (see header of `MW/D32/DSP/SHARC/build.sh`).
  A local toolchain copy may exist at `MW/D32/DSP/SHARC/cces/` (gitignored).
- License material (serials, `license.dat`) is gitignored — never commit it.
- Bulky per-product binaries (board fab outputs, CAD projects, vendor SDKs,
  bitstreams, tuning captures) live in the mx26-owned Dropbox `_Matrix` store,
  not in git — see [matrix-shared-store.md](matrix-shared-store.md). Nothing
  there is a build input.
