# SWOT Analysis — CSV-Driven DSP Code Generation

Approach under review: a single `dsp.csv` file defines the entire signal graph (201 nodes, 32 channels). Python tools validate it, generate a block diagram, and emit per-node SHARC+ ASM skeleton files. All DSP topology decisions live in the CSV; actual algorithm implementation is manual ASM inside the generated skeletons.

---

## Strengths

| # | Strength | Detail |
|---|----------|--------|
| S1 | **Single source of truth** | One CSV defines topology, connectivity, channel counts, SPI addressing, and default params. No redundant definitions across ASM, C, or MCU code to keep in sync. |
| S2 | **Git-diffable** | Plain-text CSV produces meaningful diffs. A topology change (add a node, rewire, change SPI address) is a one-line diff reviewable in any git tool. Binary SigmaStudio project files had no usable diff. |
| S3 | **Early error detection** | `dsp_validate.py` catches 14 categories of error (orphan nodes, cross-chip audio links, duplicate SPI addresses, missing INTERCHIP pairs, bidirectional link mismatches) before any ASM is compiled. Errors that would otherwise surface as silent audio failures or SPI collisions at runtime. |
| S4 | **Visual cross-check** | `dsp_diagram.py` renders the CSV to PNG for engineer review. Catches conceptual errors (wrong signal flow, missing connections) that are hard to spot reading 201 CSV rows or 203 ASM files. |
| S5 | **Consistent skeletons** | Codegen guarantees uniform file structure: every node gets the same header format, section declarations, buffer naming convention, and process function signature. Eliminates copy-paste errors across 203 files. |
| S6 | **Aligns with existing Matrix system** | `spi_page` / `spi_addr` columns map directly to `matrix.csv` `DspPage` / `DspAdd` columns. Control chain (App → Pi → H1S1 → SPI → DSP) is already defined; CSV bridges the gap between matrix control and DSP internals. |
| S7 | **Product variant support** | D24 and D32 share the same CSV and binary. Channel masking is a runtime config, not a build-time fork. No divergent codebases to maintain. |
| S8 | **Separation of concerns** | Topology (what connects to what) is separated from implementation (how each node processes audio). A topology change doesn't require touching ASM; an algorithm change doesn't require editing the CSV. |
| S9 | **Low tooling dependencies** | Python 3 + `csv` (stdlib) + `graphviz` (optional, for diagrams). No proprietary tools needed until compile time. Any engineer can validate and visualise the graph on any machine. |
| S10 | **Familiar to the team** | Matrix system already uses CSV extensively (`matrix.csv`, `settings.csv`, `broadcast.csv`, `fw.csv`). This is not a new format or paradigm — it extends a pattern the project already relies on. |

## Weaknesses

| # | Weakness | Detail | Mitigation |
|---|----------|--------|------------|
| W1 | **Skeletons are stubs only** | Codegen produces pass-through placeholders with TODO comments. 100% of actual DSP algorithm work (EQ, compressor, reverb, etc.) is still manual ASM. The tooling accelerates scaffolding but not the hard part. | Accepted — the value is in topology correctness and consistency, not algorithm generation. |
| W2 | **No runtime simulation** | Pipeline validates structure but cannot test audio behaviour. A correctly-validated CSV with broken ASM inside the skeletons will pass all checks. No way to hear or measure DSP output without hardware. | Could add a Python/NumPy simulation mode later (see O3). |
| W3 | **CSV is flat** | Cannot express hierarchical structures (e.g., a "channel strip" macro containing GAIN + EQ + COMP), conditional routing (bypass paths, scene-dependent rewiring), or loopback connections. Every node is a flat row. | For the current 201-node topology this is manageable. If topology grows significantly, consider a preprocessor that expands macros to flat CSV. |
| W4 | **Memory layout not modelled** | CSV has no concept of L1/L2 SRAM placement, DMA buffer alignment, circular buffer base/length registers, or section placement. These critical SHARC concerns must be handled manually in ASM/linker scripts. | Memory layout is inherently chip-specific; keeping it out of the CSV avoids false abstraction. Linker .ldf files handle placement. |
| W5 | **No block-size awareness** | Generated code assumes sample-by-sample processing. Some algorithms (FFT-based EQ, block convolution) require frame-based processing. CSV has no `block_size` concept. | Current use case (biquad EQ, gain, comp, limiter) is sample-based. Add `block_size` param to node types if block processing is needed later. |
| W6 | **CSV can diverge from ASM** | If an engineer modifies a generated ASM file (adds nodes, changes connectivity) without updating the CSV, the source of truth is broken. Re-running codegen would overwrite the changes. | Convention: never hand-edit connectivity in ASM — always edit CSV and regenerate. Codegen should warn/refuse to overwrite files with manual changes (see O4). |
| W7 | **Limited parameter expressiveness** | Params are flat `key=value` strings. Complex structures (per-band EQ curves, routing matrices with 32×2 gain coefficients) are awkward to express inline. | Params define *initial defaults* only. Runtime state is managed via SPI writes from H1S1. Complex preset data lives in H1S1 flash, not in the CSV. |
| W8 | **CCES under Wine is untested** | The compile step (`build.sh` → `wine asm21k.exe`) is unproven. CCES CLI may have Wine-incompatible behaviours (licensing, temp file paths, console encoding). | Keep a fallback plan: compile on a Windows machine or VM. Wine is a convenience, not a hard dependency. |

## Opportunities

| # | Opportunity | Detail |
|---|-------------|--------|
| O1 | **Auto-generate SPI address map for H1S1** | Extend `dsp_codegen.py` (or add a new tool) to emit a C header mapping every `spi_page`/`spi_addr` to a parameter name and type. H1S1 MCU firmware would `#include` this header, eliminating manual address table maintenance. Single source for both DSP and MCU. |
| O2 | **Auto-generate matrix.csv DspSpi columns** | Tool could emit the `DspSpi`/`DspPage`/`DspAdd` columns for `matrix.csv` directly from `dsp.csv`. Closes the loop between UI controls and DSP parameters with zero manual mapping. |
| O3 | **Python audio simulation** | Add a `dsp_simulate.py` tool that reads `dsp.csv` and executes a NumPy-based functional equivalent of each node type. Input: WAV file or test tone. Output: WAV file + per-node level meters. Allows signal flow validation before hardware is available. |
| O4 | **Guard against skeleton overwrite** | Hash or timestamp tracking: codegen writes a checksum into each generated file header. On re-run, if the file has been modified (checksum mismatch), codegen warns instead of overwriting. Protects manual DSP work while keeping regeneration safe for unchanged files. |
| O5 | **D24 variant CSV generation** | Tool to produce a D24-specific reduced CSV from the D32 master (mask 8 channels, remove their nodes, re-validate). Useful for documentation and testing even though runtime uses channel masking. |
| O6 | **Generate DMA descriptor tables** | CSV already defines SPORT IDs and slot assignments. A tool could generate the DMA descriptor chain structures for SPORT I/O configuration, reducing manual C init code. |
| O7 | **CI integration** | Add `dsp_validate.py` to a git pre-commit hook or CI pipeline. Topology errors caught on commit, before anyone attempts a build. |
| O8 | **CCES .dpj project file generation** | Auto-generate the CCES IDE project file from the file list and build flags in `build.sh`. Enables CCES IDE debugging while keeping CSV as the primary definition. |

## Threats

| # | Threat | Likelihood | Impact | Mitigation |
|---|--------|------------|--------|------------|
| T1 | **Topology-implementation drift** | High | Medium | If ASM files are modified without updating CSV, the diagram and validator become unreliable. Mitigate with O4 (overwrite guards) and team discipline. |
| T2 | **Over-engineering the tooling** | Medium | High | Time spent adding tooling features (simulation, CI, macro expansion) is time not spent on actual DSP algorithm implementation. The tooling is a means, not the product. Strict scope discipline required. |
| T3 | **Architecture changes from hardware reality** | Medium | High | Real hardware testing may reveal that sample-by-sample processing is too slow, or that SPORT TDM32 inter-chip link needs restructuring. CSV topology may need significant rework. Mitigate by keeping CSV editable and regeneration cheap. |
| T4 | **Wine/CCES compatibility failure** | Medium | Medium | If CCES CLI doesn't work under Wine, compile workflow needs a Windows machine or VM, adding friction. Not a threat to the CSV approach itself, only to the build step. |
| T5 | **Scale limits of flat CSV** | Low | Medium | 201 nodes is manageable. If future products need 500+ nodes (e.g., per-channel aux sends, multiple reverb instances, matrix routing), flat CSV becomes hard to read and edit. Mitigate with tooling (macro preprocessor, spreadsheet filters). |
| T6 | **Reverb quality risk** | Medium | Medium | Freeverb is a 1990s algorithm. Quality may not meet professional mixer expectations. Mitigation is the modular architecture — reverb node is isolated, swappable without topology changes. |
| T7 | **No debugger integration** | High | Medium | CSV tooling provides no visibility into runtime DSP state (register values, buffer contents, cycle counts). All runtime debugging depends on JTAG + CCES debugger — a completely separate workflow from the CSV pipeline. |

---

## Comparison with Alternatives

| Aspect | CSV + Codegen (this approach) | SigmaStudio | MATLAB/Simulink Codegen | Hand-written ASM |
|--------|-------------------------------|-------------|------------------------|------------------|
| Topology definition | CSV (text, git-friendly) | GUI (binary project file) | GUI (binary .slx) | Implicit in code |
| Validation | Automated (14 rules) | Built-in | Built-in | Manual review |
| Code output | ASM skeletons (stubs) | SigmaDSP microcode | C/C++ (not SHARC ASM) | Complete ASM |
| Target flexibility | SHARC+ specific | ADAU1466 only | Multi-target | SHARC+ specific |
| Algorithm quality | Manual (full control) | Pre-built blocks | Pre-built blocks + custom | Manual (full control) |
| Runtime debugging | JTAG only | SigmaStudio real-time | Simulink real-time | JTAG only |
| Learning curve | Low (CSV + Python) | Medium (SigmaStudio) | High (MATLAB licence + workflow) | N/A |
| Vendor lock-in | None | ADI SigmaDSP only | MathWorks licence | None |
| Git workflow | Native | Poor (binary files) | Poor (binary files) | Native |

## Summary

The CSV-driven approach is a strong fit for this project:
- It extends patterns already established in the Matrix system (CSV-centric configuration)
- It catches structural errors early and provides visual verification
- It does not attempt to generate DSP algorithms, which would be the wrong abstraction for hand-optimised SHARC+ ASM

The primary risks are **topology-implementation drift** (W6/T1) and **over-investing in tooling** (T2). Both are managed through discipline rather than technology. The approach delivers its highest value in the current phase (topology definition and scaffolding) and its value decreases as work shifts to algorithm implementation (Phase 5), where the generated stubs are replaced with real DSP code and the CSV becomes a documentation/validation artifact rather than a generation source.
