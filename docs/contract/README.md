Generated in this repo by `tools/dsp/wire_contract.py` — regenerate with
`python3 tools/dsp/wire_contract.py --product d32 --inert-md ... --proposals-md ...`:

  conformance-harness.md      what the harness is, how to run it, the bar
  inert-cells-d38.md          the authoritative D38 inert list, by class
  wire-units-proposals.md     UNDECLARED families whose unit can be
                              inferred, as PROPOSALS for the defs repo's
                              wire-units.csv — adopted nowhere here, plus
                              the documented cells that reach no DSP
                              address at all

THE WIRE TABLES ARE NOT HERE ANY MORE. `d24-wire-table.csv`,
`d32-wire-table.csv` and `wire-units.csv` used to sit in this directory as
distribution copies of mx26's generated tables. They are declarations, and
declarations live in the `defs` submodule — `defs/gen/matrix/<p>-wire-
table.csv` and `defs/common/wire/wire-units.csv`, which is where
`wire_contract.py` now reads them. A copy in this tree is a second source
of truth by another name (defs S1, 2026-09-08).

A family with unit=UNDECLARED gets presence/echo testing only until its
unit is declared in defs's wire-units.csv.

Nothing in this directory is a build input.
