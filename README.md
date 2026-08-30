# mx-dsp

DSP implementation repo for Invirco matrix-based products. Matrix *definitions*
live in the **mx26** repo (the hub); this repo consumes a versioned CSV contract
from mx26 and turns it into DSP firmware artifacts (the spoke). See
[mx26-mx-dsp-integration.md](mx26-mx-dsp-integration.md) for the full model.

For source documents and bulky source assets, use the mx26-owned Dropbox
`_Matrix` store as the working location. Keep generated DSP artifacts,
contract files, and repo-local implementation notes here in the repo; the
contract sync path still comes from the mx26 checkout unless mx26 changes that
flow.

## Layout

```
defs.lock                     # pins the exact mx26 contract state (authoritative)
tasks.md                      # active task tracker — update on every contract bump
scaffold-product.sh           # creates a new MW/<PRODUCT> tree + integration checklist
shared/mx_master.csv          # matrix cell-library compatibility baseline
tools/dsp/                    # shared DSP codegen package (all products)
    dsp_codegen.py            #   dsp.csv -> SHARC ASM (nodes, ramp engine, block_io)
    gen_dsp_csv.py            #   matrix -> dsp.csv graph source
    dsp_validate.py           #   dsp.csv graph rules check
    dsp_simulate.py           #   node-level simulation harness
    dsp_diagram.py            #   dsp.csv -> Graphviz diagram
    wire_contract.py          #   the SPI wire contract, assembled from
                              #   _matrix.csv + the dispatch tables +
                              #   wire-units.csv; feeds the conformance
                              #   harness and emits the D38 inert list
MW/<PRODUCT>/                 # one tree per product (D24, D32, ...)
    DEFS/  dNN.csv            # feature definition        (synced from mx26)
    FW/    fw.csv             # hardware config           (synced from mx26)
    MX/    dNN-mx-master.csv  # expanded product master   (synced from mx26)
           _matrix.csv        # runtime matrix snapshot   (synced + DSP backfill)
    DSPCFG/                   # tier-2 dsp.csv when mx26 provides it (currently absent)
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

New matrix products get a new `MW/<PRODUCT>/` tree following the same
DEFS/FW/MX/DSPCFG/DSP shape, driven by the same contract flow.

## Daily workflow

| Command | Purpose |
|---|---|
| `./regenerate-dsp-contract.sh` | Sync from mx26 + validate + regenerate DSP artifacts |
| `./regenerate-dsp-contract.sh --update-lock` | Same, but bump defs.lock hashes (intentional contract bump) |
| `./check-contract-drift.sh [--strict]` | Pre-merge drift gate |
| `python3 validate-matrix-contract.py` | MxAdd continuity + family allowlist check |
| `python3 audit-compat-aliases.py` | Refresh alias-audit.md |
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
