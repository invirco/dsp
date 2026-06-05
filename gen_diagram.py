#!/usr/bin/env python3
"""
gen_diagram.py – derive a partial DSP block diagram from mx_master.csv.

Reads the StripType, StripOrder and Function columns to build per-strip
processing chains, then emits:
  block_diagram.dot   – Graphviz DOT (render: dot -Tsvg block_diagram.dot -o block_diagram.svg)
  block_diagram.md    – Mermaid flowchart (renders natively on GitHub)

Only DSP-relevant rows are used (Save2Mix != false and Function not empty
and StripType in the signal-path set).  Meter rows (Chan_Mtr, MainMtr, …)
are shown as side-taps, not in the main flow.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

CSV_PATH = Path(__file__).parent / "mx_master.csv"
DOT_PATH = Path(__file__).parent / "block_diagram.dot"
MD_PATH  = Path(__file__).parent / "block_diagram.md"

# Strip types to include and their display order (left → right / top → bottom)
STRIP_ORDER = ["Chan", "Grp", "Fx", "Aux", "Main", "Sub", "Mon"]

# Human labels for each strip type
STRIP_LABEL = {
    "Chan": "Channel Strip\n(×32)",
    "Grp":  "Group Bus\n(×4)",
    "Fx":   "FX Engine\n(×6)",
    "Aux":  "Aux Bus\n(×12)",
    "Main": "Main L/R",
    "Sub":  "Sub",
    "Mon":  "Monitor",
}

# Colour per strip type (Graphviz named colours)
STRIP_COLOR = {
    "Chan": "#d0e8ff",
    "Grp":  "#d4f5d4",
    "Fx":   "#fff3cd",
    "Aux":  "#fde8d8",
    "Main": "#e8d4f5",
    "Sub":  "#f5d4d4",
    "Mon":  "#d4ecf5",
}

# Nice labels for Function groups
FUNC_LABEL = {
    "ChanInput":    "Input\n(Gain/HPF/Pol/Insert)",
    "Chan_Eq":      "EQ\n(HPF + 4-band PEQ)",
    "ChanGate":     "Gate",
    "ChanComp":     "Compressor",
    "ChanDelay":    "Delay",
    "Chan_Rtg":     "Fader / Pan\n& Routing",
    "Chan_Mtr":     "Meters",
    "GrpEq":        "EQ\n(HPF + 4-band PEQ)",
    "GrpGate":      "Gate",
    "GrpComp":      "Compressor",
    "GrpRtg":       "Fader",
    "FxCtrl":       "FX Engine\n(Echo/Reverb/Chorus…)",
    "AuxEq":        "EQ\n(HPF + GEQ + PEQ)",
    "AuxLimiter":   "Limiter",
    "AuxRtg":       "Level / Pan\n& Routing",
    "AuxAntiFb":    "Anti-Feedback\n(6 notch filters)",
    "AuxDelay":     "Delay",
    "MainEq":       "GEQ + 4-band PEQ",
    "MainComp":     "Compressor",
    "MainLimiter":  "Limiter",
    "MainCrossover":"Crossover",
    "MainRtg":      "Level / Routing",
    "MainMtr":      "Meters",
    "MainPeq":      "Graphic EQ (PEQ)",
    "SubEq":        "EQ\n(HPF + 4-band PEQ)",
    "SubComp":      "Compressor",
    "SubLimiter":   "Limiter",
    "SubRtg":       "Level",
    "SubMtr":       "Meters",
    "MonCtrl":      "Level / Source\n& Delay",
    "DcaCtrl":      "DCA Faders\n(×8)",
    "NoiseGen":     "Noise / Tone\nGenerator",
}

# Meter function groups (shown as side-taps, not in main chain)
METER_FUNCS = {"Chan_Mtr", "MainMtr", "SubMtr", "AuxMtr"}

# DSP-relevant strip types (exclude pure UI / sys rows)
DSP_STRIPS = {"Chan", "Grp", "Fx", "Aux", "Main", "Sub", "Mon"}


def load_chains(csv_path):
    """Return {strip_type: [(strip_order, function), …]} sorted by order."""
    seen = {}   # (strip_type, function) → strip_order

    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            save2mix = row.get("Save2Mix", "").strip().lower()
            if save2mix == "false":
                continue
            strip_type = row.get("StripType", "").strip()
            function   = (row.get("ShFunction", "").strip()
                          or row.get("Function", "").strip())
            order_raw  = row.get("StripOrder","").strip()
            if not strip_type or not function or strip_type not in DSP_STRIPS:
                continue
            try:
                order = int(order_raw) if order_raw else 999
            except ValueError:
                order = 999
            key = (strip_type, function)
            if key not in seen or order < seen[key]:
                seen[key] = order

    chains = defaultdict(list)
    for (strip_type, function), order in seen.items():
        chains[strip_type].append((order, function))

    for st in chains:
        chains[st].sort()

    return dict(chains)


# ─── Graphviz DOT ────────────────────────────────────────────────────────────

def node_id(strip_type, function):
    return f"{strip_type}_{function}".replace(" ", "_").replace("-", "_")


def build_dot(chains):
    lines = [
        "digraph dsp_block_diagram {",
        "  graph [rankdir=LR fontname=\"Helvetica\" splines=polyline nodesep=0.5];",
        "  node  [shape=box style=\"filled,rounded\" fontname=\"Helvetica\" fontsize=10];",
        "  edge  [fontname=\"Helvetica\" fontsize=9];",
        "",
    ]

    # Declare a virtual source and sink
    lines += [
        "  // ── Sources & Sinks ──────────────────────────────────────────",
        "  MIC_LINE [label=\"Mic / Line\\nInput (×32)\" shape=parallelogram"
        " fillcolor=\"#eeeeee\"];",
        "  DIGITAL_IN [label=\"Digital / USB\\nInput\" shape=parallelogram"
        " fillcolor=\"#eeeeee\"];",
        "  MAIN_OUT [label=\"Main L/R\\nOutput\" shape=parallelogram"
        " fillcolor=\"#cccccc\"];",
        "  SUB_OUT  [label=\"Sub\\nOutput\"  shape=parallelogram"
        " fillcolor=\"#cccccc\"];",
        "  AUX_OUT  [label=\"Aux Outputs\\n(×12)\" shape=parallelogram"
        " fillcolor=\"#cccccc\"];",
        "  MON_OUT  [label=\"Monitor\\nOutput\" shape=parallelogram"
        " fillcolor=\"#cccccc\"];",
        "  FX_RETURN [label=\"FX Return\\n(×6)\" shape=parallelogram"
        " fillcolor=\"#fff3cd\"];",
        "",
    ]

    for strip_type in STRIP_ORDER:
        if strip_type not in chains:
            continue
        funcs = chains[strip_type]
        color = STRIP_COLOR.get(strip_type, "#ffffff")
        lines.append(f"  // ── {strip_type} ──────────────────────────────────────────────")
        lines.append(f"  subgraph cluster_{strip_type} {{")
        lines.append(f"    label=\"{STRIP_LABEL.get(strip_type, strip_type)}\";")
        lines.append(f"    style=filled; fillcolor=\"{color}\"; color=\"#888888\";")
        lines.append(f"    fontname=\"Helvetica\"; fontsize=11; fontcolor=\"#333333\";")

        prev_main = None
        meter_node = None

        for order, func in funcs:
            nid = node_id(strip_type, func)
            label = FUNC_LABEL.get(func, func)
            if func in METER_FUNCS:
                meter_node = nid
                lines.append(f"    {nid} [label=\"{label}\" fillcolor=\"#f0f0f0\""
                              " style=\"filled,dashed,rounded\"];")
            else:
                lines.append(f"    {nid} [label=\"{label}\" fillcolor=\"{color}\"];")
                if prev_main:
                    lines.append(f"    {prev_main} -> {nid};")
                prev_main = nid

        # Meter tap off last main node
        if meter_node and prev_main:
            lines.append(f"    {prev_main} -> {meter_node} [style=dashed arrowhead=odot"
                         " label=\"tap\"];")

        # Store first/last main node for inter-strip edges
        main_nodes = [(o, f) for (o, f) in funcs if f not in METER_FUNCS]
        first_func = main_nodes[0][1]  if main_nodes else None
        last_func  = main_nodes[-1][1] if main_nodes else None
        chains[strip_type + "_first"] = node_id(strip_type, first_func) if first_func else None
        chains[strip_type + "_last"]  = node_id(strip_type, last_func)  if last_func  else None

        lines.append("  }")
        lines.append("")

    # ── Inter-strip routing edges ─────────────────────────────────────────
    lines.append("  // ── Signal routing ─────────────────────────────────────────────")

    def last(st):
        return chains.get(st + "_last")

    def first(st):
        return chains.get(st + "_first")

    # Inputs → Chan
    if first("Chan"):
        lines.append(f"  MIC_LINE   -> {first('Chan')};")
        lines.append(f"  DIGITAL_IN -> {first('Chan')} [style=dashed];")

    # Chan routing → downstream buses
    chan_rtg = node_id("Chan", "Chan_Rtg")
    if "Grp"  in chains: lines.append(f"  {chan_rtg} -> {first('Grp')}  [label=\"Grp send\"];")
    if "Aux"  in chains: lines.append(f"  {chan_rtg} -> {first('Aux')}  [label=\"Aux send\"];")
    if "Fx"   in chains: lines.append(f"  {chan_rtg} -> {first('Fx')}   [label=\"FX send\"];")
    lines.append(f"  {chan_rtg} -> MAIN_OUT [label=\"Main assign\" style=dashed];")

    # FX return → Main
    if "Fx" in chains:
        lines.append(f"  {last('Fx')} -> FX_RETURN;")
        lines.append(f"  FX_RETURN -> MAIN_OUT [label=\"FX return\"];")
        if "Aux" in chains:
            lines.append(f"  FX_RETURN -> {first('Aux')} [style=dashed label=\"FX→Aux\"];")

    # Grp → Main / Sub
    if "Grp" in chains:
        lines.append(f"  {last('Grp')} -> MAIN_OUT [label=\"Grp→Main\"];")
        if "Sub" in chains:
            lines.append(f"  {last('Grp')} -> {first('Sub')} [label=\"Grp→Sub\" style=dashed];")

    # Aux output
    if "Aux" in chains:
        lines.append(f"  {last('Aux')} -> AUX_OUT;")

    # Main → Sub crossover feed
    if "Main" in chains and "Sub" in chains:
        lines.append(f"  {last('Main')} -> MAIN_OUT;")
        lines.append(f"  {last('Sub')}  -> SUB_OUT;")

    # Mon source
    if "Mon" in chains:
        lines.append(f"  MAIN_OUT -> {first('Mon')} [style=dashed label=\"Mon src\"];")
        lines.append(f"  {last('Mon')} -> MON_OUT;")

    lines.append("}")
    return "\n".join(lines)


# ─── Mermaid flowchart ───────────────────────────────────────────────────────

def mermaid_id(strip_type, function):
    return re.sub(r"[^A-Za-z0-9_]", "_", f"{strip_type}_{function}")


def build_mermaid(chains):
    lines = [
        "```mermaid",
        "flowchart LR",
        "",
        "    %% ── Sources ──────────────────────────────────────────────────",
        "    MIC([\"Mic / Line\\nInput ×32\"])",
        "    DIG([\"Digital / USB\\nInput\"])",
        "",
    ]

    all_strip_nodes = {}  # strip_type → [mermaid_ids in order]

    for strip_type in STRIP_ORDER:
        if strip_type not in chains:
            continue
        funcs = [(o, f) for (o, f) in chains[strip_type] if f not in METER_FUNCS]
        if not funcs:
            continue
        lines.append(f"    %% ── {strip_type} ─────────────────────────────────────────────")
        lines.append(f"    subgraph {strip_type}[\"{STRIP_LABEL.get(strip_type, strip_type)}\"]")

        ids = []
        for order, func in funcs:
            mid = mermaid_id(strip_type, func)
            label = FUNC_LABEL.get(func, func).replace("\n", "\\n")
            lines.append(f"        {mid}[\"{label}\"]")
            ids.append(mid)

        # Chain within subgraph
        for i in range(len(ids) - 1):
            lines.append(f"        {ids[i]} --> {ids[i+1]}")

        lines.append("    end")
        lines.append("")
        all_strip_nodes[strip_type] = ids

    # Outputs
    lines += [
        "    %% ── Sinks ──────────────────────────────────────────────────",
        "    MAIN_OUT([\"Main L/R\\nOutput\"])",
        "    SUB_OUT([\"Sub\\nOutput\"])",
        "    AUX_OUT([\"Aux Outputs\\n×12\"])",
        "    MON_OUT([\"Monitor\\nOutput\"])",
        "    FX_RET([\"FX Return\\n×6\"])",
        "",
        "    %% ── Routing ─────────────────────────────────────────────────",
    ]

    def first_id(st):
        n = all_strip_nodes.get(st, [])
        return n[0] if n else None

    def last_id(st):
        n = all_strip_nodes.get(st, [])
        return n[-1] if n else None

    # Inputs → Chan
    fi = first_id("Chan")
    if fi:
        lines.append(f"    MIC --> {fi}")
        lines.append(f"    DIG -.-> {fi}")

    # Chan → buses
    chan_rtg = mermaid_id("Chan", "Chan_Rtg")
    if first_id("Grp"):  lines.append(f"    {chan_rtg} -->|Grp send| {first_id('Grp')}")
    if first_id("Aux"):  lines.append(f"    {chan_rtg} -->|Aux send| {first_id('Aux')}")
    if first_id("Fx"):   lines.append(f"    {chan_rtg} -->|FX send|  {first_id('Fx')}")
    lines.append(f"    {chan_rtg} -.->|Main assign| MAIN_OUT")

    # FX return
    if last_id("Fx"):
        lines.append(f"    {last_id('Fx')} --> FX_RET")
        lines.append(f"    FX_RET --> MAIN_OUT")

    # Grp → main/sub
    if last_id("Grp"):
        lines.append(f"    {last_id('Grp')} -->|Grp→Main| MAIN_OUT")
        if first_id("Sub"):
            lines.append(f"    {last_id('Grp')} -.->|Grp→Sub| {first_id('Sub')}")

    # Aux output
    if last_id("Aux"):
        lines.append(f"    {last_id('Aux')} --> AUX_OUT")

    # Main/Sub outputs
    if last_id("Main"):
        lines.append(f"    {last_id('Main')} --> MAIN_OUT")
    if last_id("Sub"):
        lines.append(f"    {last_id('Sub')} --> SUB_OUT")

    # Mon
    if first_id("Mon") and last_id("Mon"):
        lines.append(f"    MAIN_OUT -.->|Mon src| {first_id('Mon')}")
        lines.append(f"    {last_id('Mon')} --> MON_OUT")

    lines.append("```")
    return "\n".join(lines)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    chains = load_chains(CSV_PATH)

    # Print what was found
    for st in STRIP_ORDER:
        if st in chains:
            print(f"  {st:6s}: " +
                  " → ".join(f"{f}({o})" for o, f in chains[st]))

    # DOT
    dot = build_dot(chains)
    DOT_PATH.write_text(dot, encoding="utf-8")
    print(f"\nWrote {DOT_PATH}")
    print("  Render: dot -Tsvg block_diagram.dot -o block_diagram.svg")

    # Mermaid markdown
    mermaid = build_mermaid(chains)
    md_content = (
        "# DSP Block Diagram (partial)\n\n"
        "> Generated from `mx_master.csv` by `gen_diagram.py`.  \n"
        "> Rows with `Save2Mix=false` (UI-only / sys control) are excluded.  \n"
        "> Each strip shows the DSP processing stages in signal-flow order\n"
        "> derived from the `StripOrder` column.\n\n"
        "## Channel Strip → Bus Overview\n\n"
        + mermaid + "\n\n"
        "## Strip Types Decoded\n\n"
        "| StripType | Count | Processing Chain |\n"
        "|-----------|-------|------------------|\n"
    )
    for st in STRIP_ORDER:
        if st not in chains:
            continue
        funcs = [f for _, f in chains[st] if f not in METER_FUNCS]
        counts = {"Chan": "×32", "Grp": "×4", "Fx": "×6", "Aux": "×12",
                  "Main": "×1", "Sub": "×1", "Mon": "×1"}
        chain_str = " → ".join(funcs)
        md_content += f"| **{st}** | {counts.get(st,'')} | {chain_str} |\n"

    MD_PATH.write_text(md_content, encoding="utf-8")
    print(f"Wrote {MD_PATH}")


if __name__ == "__main__":
    main()
