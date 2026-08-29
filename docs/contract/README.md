Wire tables generated in mx26 (src/pd/, tools/def_wire_table.py) — mx26 is
the SOT; these are distribution copies for the conformance harness. A
family with unit=UNDECLARED gets presence/echo testing only until its
unit is declared in mx26's wire-units.csv.

Also here, and GENERATED IN THIS REPO rather than synced — regenerate with
`python3 tools/dsp/wire_contract.py --product d32 --inert-md ... --proposals-md ...`:

  conformance-harness.md      what the harness is, how to run it, the bar
  inert-cells-d38.md          the authoritative D38 inert list, by class
  wire-units-proposals.md     UNDECLARED families whose unit can be
                              inferred, as PROPOSALS for mx26's
                              wire-units.csv — adopted nowhere here, plus
                              the documented cells that reach no DSP
                              address at all

Nothing in this directory is a build input. The contract path still comes
from the mx26 checkout.
