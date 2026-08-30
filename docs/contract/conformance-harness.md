provenance: AI-drafted 2026-08-29 — prose may carry a statistical watermark; rewrite by hand before publication, then remove this header.

# The contract conformance harness

Status: active, standing per-session bar (PW addendum 2026-08-29)
Scope: D32/D24 DSP4 SPI parameter plane, both chips

## What it is for

Every other instrument in this tree measures the kernel **against
itself**. `bqst` diffs two assembly forms of the biquad, `dynst` diffs
two forms of the dynamics, `busgold` diffs a bus capture against a
stored bus capture, `golden_harness` diffs the model against exact
arithmetic. All of them are necessary and none of them can see a cell
that is addressed to the wrong variable, served in the wrong unit, or
wired to nothing at all — such a cell reproduces its own goldens
perfectly, forever.

This harness asks the other question: **does the DSP implement the
control surface the masters document?** The masters are the contract
(mx26 is SOT for cell semantics), so where the two disagree, the kernel
is what moves.

## The three phases

| phase | question | instrument |
|---|---|---|
| PRESENCE | does every documented address accept a write and read back? | the protocol's own read path, plus the part's `SPI_ERR_COUNT` |
| EFFECT | for a family whose unit is DECLARED, does the documented value produce the documented consequence? | diag peek of the coefficient the kernel derives |
| INERT | does a write change anything kernel-visible at all? | bus capture before/after, against a positive control |

**PRESENCE** writes each address at the boundary values its master
`Table` string names, and reads it back. The mapped/unmapped verdict does
*not* come from the read-back: an unmapped address and a mapped one whose
target the kernel clears every block both read back zero, and the
coefficient-set swap triggers are exactly the second case. `SPI_ERR_COUNT`
settles it — `spi_handler.asm` increments it only on the `.spi_error`
path, which is reached only when the dispatch entry is 0 or the address
is out of bounds. One counter read either side of the probe batch turns a
guess into a measurement, and disagreement with what the dispatch table in
the tree predicts is **drift between source and image**.

**EFFECT** predicts the coefficient from the documented unit *and from
nothing else*. It does not consult `dsp_codegen`: a check that derived
its expectation from the generator would agree with whatever conversion
the generator happened to implement, including a wrong one. Tolerance is
relative (3e-5 of full scale, about 0.0003 dB) because the contract under
test is a unit, not a rounding rule.

**INERT** confirms the static candidates from
`tools/dsp/wire_contract.py` on the part. Its **positive control is the
point**: a capture comparison that cannot fail proves nothing, and this
one is easy to make unable to fail — capture a silent bus, or capture
through a graph whose control epoch never advances, and every address on
earth looks inert. So the same procedure runs first on cells known to be
wired, and the inert verdicts are reported only if those controls moved
the bus by more than three times what the same wait moves on its own.

### The driven graph, and the four things it took (2026-08-30)

Session 4 could not report an inert verdict at all. Its window was the
strip's CONTROL STATE on an idle graph and it failed its own control: 2–8
of 97 quiet words moved under a write while 0–22 moved unwritten. The
window is now the MAIN BUS with the graph DRIVEN, which is what
"kernel-visible" was always supposed to mean, and getting there was four
separate corrections — each of which produced a probe that looked like it
worked and answered the wrong question:

1. **The injection address.** Session 4 drove `_buf_C1_IN_01` and
   concluded the shipping build's scope injection "does not reach the
   chain". It reaches it; that is the input node's OUTPUT, and the node
   copies `_rx_slot_C1_IN_01` over it on every sample. The slot the step
   has to go into is `_rx_slot_*` in a per-sample build and the pool in a
   block build, and the symbol table settles which.
2. **The strip has to be driven ON PURPOSE.** A boot leaves the fader,
   its pan legs and the DCA wherever the config commit left them, so the
   strip contributes nothing to the main bus and the capture is all
   zeros — which is also what a dead strip, a dropped arm and a muted
   graph look like. `drive_strip()` writes the gain, the fader, the mute,
   the dynamics and their time constants before anything is captured.
3. **The graph has to be at REST before each capture.** The scope only
   drives while it is armed, so between captures the graph falls silent
   and releases for however long the host happened to take; two
   back-to-back captures then differed in **32 of 32 words**. A fixed
   rest interval before every arm makes each capture start from the same
   place — the noise floor is now **zero words**.
4. **The window sits at sample 900, not sample 0.** The first thirty-odd
   samples after the step are the graph's instantaneous response: the
   gate has not opened and the compressor's envelope has barely left
   zero. With the window at the start, writing the compressor THRESHOLD
   moved **zero** words — a control that fails because the window is
   blind to the entire dynamics section.

**A fifth thing was found on the way and it is not a probe defect.** With
`CompPar` at its default the compressor is fully DRY: the blend is
`out = dry + par*(wet − dry)`, so a compressor that is on, above
threshold and visibly reducing gain in `_comp_gain_*` passes the input
through unchanged. Measured: the bus read `0x03FFFFEE` at both a −20 dB
and a −55 dB threshold, to the word, while `_comp_gain_C1_COMP_01` moved
from `0x10000000` to `0x04FE8E90`. The probe therefore sets `CompPar` as
part of driving the strip, and the fact is recorded here because it means
**a default-configured strip's compressor threshold is not an audible
control at all**.

There are now TWO positive controls and a run needs both. `Chan001Gain001`
is a linear multiply the sample path reads on every sample and proves the
window sees the strip; `Chan001CompThr001` moves nothing until the
envelope has moved and proves the window reaches past the transient into
the dynamics. The first alone would let a window that is blind to
everything with a time constant report inert verdicts about dynamics
cells.

`--inert-window=state` puts session 4's control-state window back, so the
two can be compared rather than asserted against each other.

## The negative controls, which are part of every run

A harness whose expectations cannot fail is a harness that proves
nothing, so both controls run with `NEGCTL=1` and the scorer **fails the
run if they do not fire**:

- `--negctl-unit <family>` predicts one family from the unit the *kernel*
  assumes instead of the one the masters document — exactly the
  corruption a wrong row in `wire-units.csv` would introduce. That family
  must FAIL.
- `--no-verify` writes without reading back. Every address it touches
  must come out `UNVERIFIED`, never `PASS`: the run is required to *know*
  it did not check.

## Running it

```
cd MW/D32/DSP/SHARC
./conform.sh                          # both chips, all phases, shipping build
NEGCTL=1 ./conform.sh                 # with the negative controls (requal)
PHASE=effect ./conform.sh             # the declared-unit checks only (fast)
CHIPS=1 LIMIT=200 ./conform.sh        # pilot
BUILD=0 ./conform.sh                  # against whatever is already on the bench
TAG=after ./conform.sh                # name the result files
INERTN=64 ./conform.sh                # confirm more inert candidates
INERTWIN=state ./conform.sh           # session 4's control-state window
```

The plan is built **in the tree, from the contract**, by
`tools/dsp/wire_contract.py` — so a run always tests the surface the
current contract describes, and a contract bump the kernel has not caught
up with fails here instead of being tested against its own stale copy.

`conform.sh` builds the **shipping configuration** (plain `./build.sh`),
not a research build: the contract is a promise about the image that
ships, and conformance of a firmware no product runs is not conformance.
That build also reproduces the bench baseline byte for byte, so it is the
W0 check as well as the setup.

## Files

| file | role |
|---|---|
| `tools/dsp/wire_contract.py` | assembles the plan from `_matrix.csv`, the dispatch tables, `wire-units.csv` and the wire table; also emits the D38 inert list and the mx26 unit proposals |
| `tools/pi/dsp4_conform.py` | the bench half: presence, effect, inert, negative controls |
| `tools/pi/dsp4_conform_report.py` | the scorer and the results table, kept apart so a stored run can be re-scored |
| `MW/D32/DSP/SHARC/conform.sh` | the driver (plan → build → stage → run → pull → report) |
| `MW/D32/DSP/SHARC/conform_run.sh` | the bench half's boot/config ladder |
| `docs/contract/inert-cells-d38.md` | generated: the authoritative inert list |
| `docs/contract/wire-units-proposals.md` | generated: unit proposals for mx26, adopted nowhere here |

## Reading a verdict

| presence verdict | meaning |
|---|---|
| `ECHO` | the word lands and reads back — the cell is present and stores |
| `CLEARED` | mapped, accepted without error, reads back zero: the kernel consumed it (the swap triggers do this by design) |
| `VOLATILE` | the kernel overwrote it with something else |
| `UNMAPPED` | the part counted an error for every write — the dispatch entry is 0 |
| `INDETERMINATE` | the error count moved by less than the write count: writes were dropped on the link and this address cannot be classified from this run |

`INDETERMINATE` is not scored as drift. It is counted and shown, because
a link fault must not be able to masquerade as a contract finding in
either direction.

## The bar

A run PASSES when every address's live verdict agrees with the dispatch
table, every declared-unit check passes except the mismatches named
one-by-one in `dsp4_conform_report.KNOWN_MISMATCH` (each carrying its
review finding id), both negative controls fired, no address wedged the
part, and the part was healthy at exit. Class-level exemptions are
deliberately not available: they would silently absorb the next mismatch
of the same shape, which is the failure mode this harness exists to
remove.
