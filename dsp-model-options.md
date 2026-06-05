# DSP Model Options — mx_master.csv → Block Diagram + Code Generation

> **Purpose:** Evaluate approaches for creating a model derived from `mx_master.csv` that can
> (a) render a readable PNG/SVG block diagram and (b) generate complete DSP assembler/C code
> for 1 or 2 ADSP-21564 chips.

---

## Background — What Already Exists

The D32 project already has a working code-generation pipeline:

| Artefact | Location | Role |
|----------|----------|------|
| `mx_master.csv` | repo root | Master parameter registry — name, range, function group, scale, SPI metadata |
| `ref/mx/MW/D32/DSP/SHARC/dsp.csv` | D32 ref | Per-node DSP graph: chip, type, inputs/outputs, SPI addr, default params, ramp profile |
| `ref/mx/MW/D32/DSP/gen_dsp.py` | D32 ref | Build tool: reads `dsp.csv`, backfills `mx_master.csv`, emits `dsp_params.asm`, `ghost_cells.h`, `mx_dsp_map.h`, and `dsp_address_map.md` |
| `ref/mx/MW/D32/DSP/SHARC/src/` | D32 ref | Hand-written SHARC+ ASM: `main.asm`, `block_io.asm`, `process_chain.asm`, `spi_handler.asm`, `ramp_engine.asm`, per-chip `dsp_params.asm` |

**Key insight:** `mx_master.csv` is a *parameter* registry, not a signal graph.  
`dsp.csv` (D32) is the *graph* — it encodes nodes, connections, chip assignment, and SPI addresses.  
The question is whether `mx_master.csv` alone is sufficient to drive both diagram and code generation, or whether the `dsp.csv` graph layer must always sit between them.

---

## What mx_master.csv Contains

Each row is a unique parameter (or expandable parameter range) with:

| Column | Content |
|--------|---------|
| `_Cell` | Name with optional range notation, e.g. `Chan[1-32]CompAtt[1-1]` |
| `Notes` | Human-readable description |
| `MxDat` / `MxDatS` | MIDI/SPI value range and centre |
| `Function` / `ShFunction` | Processing module group, e.g. `ChanComp`, `Chan_Eq`, `GrpGate` |
| `Table` | Scale/curve definition, e.g. `0=-60/140=10/[Lin]` |
| `DspSpi`, `DspPage`, `DspAdd`, `DspAddHex` | Currently blank — populated by `gen_dsp.py` |
| `SigmaKey` / `Sigma` | Legacy SigmaStudio node references (D24 era) |

`mx_master.csv` **does not** encode:
- Which nodes connect to which (signal flow / graph edges)
- Which chip a node runs on
- Block-size, sample-rate, SPORT/TDM mapping
- Ramp profile per parameter
- Biquad coefficient formulas (only the parameter scale is present)

That information lives in `dsp.csv` (D32) or was historically in SigmaStudio projects (D24).

---

## Approach Options

### Option A — Extend the existing dsp.csv + gen_dsp.py pipeline  *(recommended near-term)*

Add a new output target to `gen_dsp.py` that reads the same `dsp.csv` graph and emits a
Graphviz DOT file (or Mermaid diagram), which is then rendered to SVG/PNG.

**Diagram generation additions to gen_dsp.py:**
- Walk nodes in `dsp.csv` in topological order
- Emit a DOT `digraph` with one node per DSP node (labelled with type + label from dsp.csv)
- Group nodes by chip (subgraph clusters)
- Colour-code by node type (INPUT, GAIN, EQ_BIQUAD, GATE, COMPRESSOR, FADER_PAN, ROUTING, BUS, FX, OUTPUT)
- Render with `dot -Tsvg` or `dot -Tpng` (Graphviz CLI, one command)

**Code generation is already there** — `gen_dsp.py` already emits `dsp_params.asm`.  
What is missing is the kernel-level ASM/C stubs for each node type (the `nodes/` subdirectory).

| | |
|--|--|
| **Pros** | Least new work; consistent with what already builds; diagram data and code data share one source of truth (`dsp.csv`); DOT renders cleanly at any scale |
| **Cons** | Diagram is generated from `dsp.csv`, not `mx_master.csv` directly; any new channel or bus type needs both files updated |
| **Issues** | DOT layout can be wide/ugly for 32-channel graphs — needs `rankdir=LR` + subgraph grouping; Graphviz must be installed |

---

### Option B — New model layer directly from mx_master.csv

Parse `mx_master.csv` using the `Function` column to infer which processing blocks exist per channel,
then synthesise a signal-flow graph automatically.

**Parsing logic:**
1. Extract all unique `Function` values → one node type per function group
2. Expand range notation in `_Cell` names → one node instance per channel/bus
3. Hard-code the canonical processing order per strip type (e.g. INPUT → GAIN → HPF → EQ → GATE → COMP → DELAY → FADER → ROUTING)
4. Generate a graph from that order, using the `Function` groups as node labels

**Diagram generation:**
- Same Graphviz/DOT or Mermaid approach as Option A once the graph is built

**Code generation:**
- For each expanded function group, emit a templated ASM/C stub or call to a named kernel function
- Assign SPI addresses by counting entries (can replicate `gen_dsp.py` logic)

| | |
|--|--|
| **Pros** | Single input source (`mx_master.csv` only); adding a new parameter row automatically updates diagram and code |
| **Cons** | Signal flow is not in `mx_master.csv` — it must be hard-coded or inferred, which is fragile; loses the per-chip assignment, SPORT mapping, and ramp profile data already in `dsp.csv`; effectively re-implements gen_dsp.py |
| **Issues** | `mx_master.csv` has no graph edges — cross-channel routing (aux sends, FX sends, groups) cannot be inferred from parameter names alone; sidechain connections (compressor key, gate key) are parameters, not edges |

---

### Option C — Hybrid: mx_master.csv drives the model, dsp.csv is generated from it

Promote `mx_master.csv` to the top-level source of truth by adding a small set of columns
(or a companion YAML/TOML file) that capture the missing graph information:

| What to add | How |
|-------------|-----|
| Signal-flow order per strip type | New column `StripOrder` or a small JSON sidecar |
| Chip assignment per function group | New column `DspChip` (1 or 2) |
| Ramp profile per parameter | Already implicit in `Function` — could be a lookup table |
| SPORT/TDM mapping | New rows or a separate `hw_map.csv` |

Then regenerate `dsp.csv` from the augmented `mx_master.csv`, and feed that into the existing
`gen_dsp.py` (or a rewrite) for both diagram and code.

| | |
|--|--|
| **Pros** | True single source of truth; cleanest long-term architecture; diagram and code always in sync with parameter definitions |
| **Cons** | Most upfront design work; requires schema decisions before any tooling is written; `mx_master.csv` becomes more complex |
| **Issues** | Schema creep risk — the CSV format may not be the right container for graph data; consider whether a YAML/TOML model file would be cleaner than extending the CSV |

---

## Diagram Tooling Comparison

| Tool | Format | Pros | Cons |
|------|--------|------|------|
| **Graphviz DOT** | SVG / PNG | Industry standard; automatic layout; CLI render; handles large graphs; free | Layout can be messy for 32+ nodes without manual hints; requires Graphviz install |
| **Mermaid** | SVG (browser/CLI) | Markdown-embeddable; GitHub renders natively; easy to write | Struggles with very large graphs; limited layout control |
| **draw.io XML** | SVG / PNG | Very readable output; pixel-perfect placement | Layout is manual; hard to generate programmatically |
| **Custom SVG (Python)** | SVG | Full control | Significant effort for a nice result; not worth it vs Graphviz |
| **PlantUML component** | PNG / SVG | Good for component/block diagrams; free | Less common in DSP toolchains; Java dependency |

**Recommendation:** Graphviz DOT for generated diagrams.  
Use `rankdir=LR`, cluster chips as subgraphs, and limit to ~15–20 visible nodes by splitting
the diagram into three separate views: (1) Chip 1 per-channel strip, (2) Chip 2 bus/output
section, (3) Inter-chip routing overview.

---

## Code Generation Options

### 1. Continue the existing SHARC ASM approach (current D32 path)

`gen_dsp.py` already emits `dsp_params.asm` (SPI dispatch tables + extern declarations).
The hand-written ASM kernels in `src/chip1/` and `src/chip2/` are the bulk of the firmware.

What is needed to reach "100% generated" code:

| Missing piece | Effort | Notes |
|---------------|--------|-------|
| Node kernel stubs (`nodes/` ASM files) | Medium | Template per node type; instantiated per channel |
| `process_chain.asm` generation | Medium | Call sequence per chip — currently hand-written |
| `block_io.asm` (SPORT/TDM) | Low | Largely mechanical; parameters from hw_map |
| Biquad coefficient formulas | Medium | EQ, HPF, LPF: standard bilinear transform; already spec'd in dsp-def.md |
| Compressor/gate time-constant math | Medium | Standard log/exp approximations |

### 2. Generate C with inline SHARC intrinsics

Use the CCES C compiler (SHARC+ target) and emit generated C code calling ADI-provided
DSP library functions (`adi_dsp_biquad`, etc.) plus custom inline for compressor/gate.

| | |
|--|--|
| **Pros** | Easier to read and maintain than raw ASM; CCES optimises reasonably well; faster to write kernel templates |
| **Cons** | ~2–3× slower than hand-optimised ASM for tight inner loops; HW IIR/FIR accelerator access is less obvious from C |
| **Issues** | The CCES SHARC compiler licence is required (noted as pending in dsp-def.md); C-generated binaries will need cycle-budget validation before committing to a single chip |

### 3. Mixed: generated C for most stages, hand ASM for inner loops

Generate C for the process chain structure (calls, routing accumulation, parameter dispatch)
and keep hand-ASM only for the innermost biquad/gain loops where the HW accelerator matters.

| | |
|--|--|
| **Pros** | Pragmatic balance; most of the code (routing sums, compressor envelope, ramp engine) is not cycle-critical and benefits from readable C |
| **Cons** | Two languages to maintain; boundary between C and ASM call convention needs care |

---

## Practical Issues and Blockers

### mx_master.csv Issues

1. **No graph edges.** The CSV has no concept of "output of node X feeds input of node Y." Any
   graph generation must supply that from an external source or hard-coded topology.

2. **Range notation must be expanded.** `Chan[1-32]CompAtt[1-1]` must be expanded to 32 individual
   entries. `gen_dsp.py` already does this for `dsp.csv`; the same logic is needed for `mx_master.csv`.

3. **`Function` groups are not node types.** `ChanComp` covers ~15 parameters across one processing
   block. The code generator needs a mapping from function group → node type → kernel template.

4. **Missing parameters for some rows.** Several rows have empty `Function` fields (e.g. `Chan[1-32]Gain`,
   `Chan[1-32]Delay`, `Chan[1-32]Pol`). These must be assigned to a function group before they
   can be placed in the graph.

5. **Meters and UI-only cells** (rows with `Save2Mix=false`, e.g. `AaChan[1-32]Mtr`) are not DSP
   nodes. They must be filtered out before building the signal-flow graph.

### Diagram Readability Issues

6. **32-channel repetition.** A full 32-channel block diagram is unreadable at any scale if all
   channels are drawn individually. The useful diagrams are:
   - One representative strip (Ch 1) showing all stages
   - A bus/routing overview showing how channels sum into buses
   - A chip-level view showing the SPORT interconnect

7. **Dual-chip inter-chip bus.** The 128-slot TDM bus between Chip 1 and Chip 2 is logically
   simple (8 SPORT lanes × 16 slots) but visually complex if every route is drawn. A bus-of-buses
   abstraction works better in the diagram than individual connections.

### Code Generation Issues

8. **Biquad coefficient formulas are not in mx_master.csv.** The CSV has the parameter range
   (e.g. frequency min/max/curve) but not the bilinear transform formulas. These must be
   implemented in the coefficient-update routines and are currently only partially specified
   in `dsp-def.md`.

9. **Compressor/gate non-linearities require lookup tables or polynomial approximations.**
   Log/exp operations (`logf`, `expf`) cost 30–50 cycles each in libm. Fast polynomial
   approximations (~8–12 cycles) must be implemented before the Chip 1 cycle budget is firm.

10. **Single vs dual chip.** The existing `dsp.csv` already encodes chip assignment per node.
    If building from `mx_master.csv` alone, the chip boundary must be added back. See dsp-def.md
    §1d for the full analysis: two chips is the recommended D32 choice; single chip is viable
    as a cost-reduction rev B with tiered input delays.

11. **CCES licence.** The CCES toolchain licence is noted as pending (dsp-def.md §1). The D32
    SHARC code is currently built via the outside-IDE `fw.sh` script using the assembler/linker
    only. C code generation requires a full CCES licence.

12. **No SigmaStudio involvement needed.** The D24 project used SigmaStudio (`DSP.ssprj`). The
    D32 project deliberately moved away from this. Any new model must not reintroduce a
    SigmaStudio dependency.

---

## Recommended Path Forward

| Step | What | Why |
|------|------|-----|
| **1** | Add a `--diagram` flag to `gen_dsp.py` that emits a Graphviz DOT file from `dsp.csv` | Fastest path to a readable block diagram; no new infrastructure |
| **2** | Render three DOT views: strip (Ch 1), bus overview, chip overview | Keeps each diagram readable at A4/letter size |
| **3** | Add node kernel templates to `gen_dsp.py` — emit `process_chain.asm` and per-node stub files from `dsp.csv` | Closes the gap to "100% generated" ASM |
| **4** | Evaluate whether `mx_master.csv` needs new columns or a sidecar file to encode the graph topology | Only needed if you want `mx_master.csv` to be the single source; dsp.csv is already the graph |
| **5 (later)** | If switching to C: add a `--emit-c` mode to gen_dsp.py and validate cycle budget against the ASM baseline | After CCES licence is in place |

The cleanest outcome is: `dsp.csv` (graph model) + `mx_master.csv` (parameter model) remain
separate concerns, both feeding a single `gen_dsp.py` that emits diagrams, ASM/C, header files,
and address maps — all from one `python3 gen_dsp.py` invocation.
