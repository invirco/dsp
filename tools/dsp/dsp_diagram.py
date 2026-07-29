#!/usr/bin/env python3
"""dsp_diagram.py — Generates a block diagram PNG from dsp.csv using Graphviz.

Usage: python3 dsp_diagram.py [path/to/dsp.csv] [output.png]
       Default input:  ../dsp.csv (relative to this script)
       Default output: ../dsp_diagram.png

Requires: graphviz Python package (`pip install graphviz`)
          and the `dot` binary (`apt install graphviz`)
"""

import csv
import sys
import os

try:
    import graphviz
except ImportError:
    print("ERROR: 'graphviz' package not installed. Run: pip install graphviz", file=sys.stderr)
    sys.exit(1)


# Node type → display colour
TYPE_COLORS = {
    'INPUT_TDM':      '#4CAF50',  # green
    'OUTPUT_TDM':     '#F44336',  # red
    'GAIN':           '#2196F3',  # blue
    'EQ_BIQUAD':      '#9C27B0',  # purple
    'EQ_MASTER':      '#9C27B0',
    'FIR':            '#673AB7',  # deep purple
    'COMPRESSOR':     '#FF9800',  # orange
    'GATE':           '#FF5722',  # deep orange
    'LIMITER':        '#E91E63',  # pink
    'MIX_BUS':        '#009688',  # teal
    'REVERB':         '#00BCD4',  # cyan
    'DELAY':          '#607D8B',  # blue-grey
    'ROUTER':         '#795548',  # brown
    'ASRC':           '#CDDC39',  # lime
    'INTERCHIP_SEND': '#FFC107',  # amber
    'INTERCHIP_RECV': '#FFC107',
}

# Node types that are "compact" — many identical instances, group label only
COMPACT_TYPES = {'INPUT_TDM', 'GAIN', 'EQ_BIQUAD', 'COMPRESSOR', 'GATE',
                 'FIR', 'INTERCHIP_SEND', 'INTERCHIP_RECV'}


def parse_id_list(cell):
    cell = cell.strip().strip('"')
    if not cell:
        return []
    return [x.strip() for x in cell.split(';') if x.strip()]


def load_csv(csv_path):
    with open(csv_path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def group_compact_nodes(rows):
    """Group consecutive compact nodes of same type on same chip into summary nodes."""
    groups = []
    current_group = None

    for row in rows:
        ntype = row['type'].strip()
        chip = row['chip'].strip()
        nid = row['id'].strip()

        if ntype in COMPACT_TYPES:
            if current_group and current_group['type'] == ntype and current_group['chip'] == chip:
                current_group['ids'].append(nid)
                current_group['count'] += 1
            else:
                if current_group:
                    groups.append(current_group)
                current_group = {
                    'type': ntype,
                    'chip': chip,
                    'ids': [nid],
                    'count': 1,
                    'group_id': f"GRP_{ntype}_{chip}_{nid}",
                    'label': row.get('label', '').strip(),
                }
        else:
            if current_group:
                groups.append(current_group)
                current_group = None
            groups.append({
                'type': ntype,
                'chip': chip,
                'ids': [nid],
                'count': 1,
                'group_id': nid,
                'label': row.get('label', '').strip(),
            })

    if current_group:
        groups.append(current_group)

    return groups


def build_id_to_group(groups):
    """Map individual node IDs to their group ID."""
    mapping = {}
    for g in groups:
        for nid in g['ids']:
            mapping[nid] = g['group_id']
    return mapping


def generate_diagram(csv_path, output_path):
    rows = load_csv(csv_path)
    if not rows:
        print("ERROR: dsp.csv is empty", file=sys.stderr)
        return 1

    groups = group_compact_nodes(rows)
    id_to_group = build_id_to_group(groups)

    dot = graphviz.Digraph(
        'DSP Signal Flow',
        format='png',
        graph_attr={
            'rankdir': 'LR',
            'fontname': 'Helvetica',
            'fontsize': '12',
            'bgcolor': '#1e1e1e',
            'pad': '0.5',
            'nodesep': '0.4',
            'ranksep': '1.2',
        },
        node_attr={
            'fontname': 'Helvetica',
            'fontsize': '10',
            'style': 'filled',
            'shape': 'box',
            'fontcolor': 'white',
        },
        edge_attr={
            'color': '#888888',
            'arrowsize': '0.7',
        },
    )

    # Create chip subgraphs
    with dot.subgraph(name='cluster_chip1') as c1:
        c1.attr(label='CHIP 1 — Input DSP', style='dashed', color='#4CAF50',
                fontcolor='#4CAF50', fontsize='14')
        for g in groups:
            if g['chip'] == '1':
                color = TYPE_COLORS.get(g['type'], '#888888')
                if g['count'] > 1:
                    label = f"{g['type']}\\n×{g['count']}"
                else:
                    label = f"{g['label']}\\n({g['type']})"
                c1.node(g['group_id'], label=label, fillcolor=color)

    with dot.subgraph(name='cluster_chip2') as c2:
        c2.attr(label='CHIP 2 — Output DSP', style='dashed', color='#F44336',
                fontcolor='#F44336', fontsize='14')
        for g in groups:
            if g['chip'] == '2':
                color = TYPE_COLORS.get(g['type'], '#888888')
                if g['count'] > 1:
                    label = f"{g['type']}\\n×{g['count']}"
                else:
                    label = f"{g['label']}\\n({g['type']})"
                c2.node(g['group_id'], label=label, fillcolor=color)

    # Build edges from CSV outputs
    edges_added = set()
    for row in rows:
        nid = row['id'].strip()
        outputs = parse_id_list(row.get('outputs', ''))
        src_group = id_to_group.get(nid)
        if not src_group:
            continue
        for out_id in outputs:
            dst_group = id_to_group.get(out_id)
            if not dst_group:
                continue
            edge_key = (src_group, dst_group)
            if edge_key not in edges_added:
                # Inter-chip edges get special styling
                src_chip = None
                dst_chip = None
                for g in groups:
                    if g['group_id'] == src_group:
                        src_chip = g['chip']
                    if g['group_id'] == dst_group:
                        dst_chip = g['chip']

                if src_chip != dst_chip:
                    dot.edge(src_group, dst_group, color='#FFC107', style='bold',
                             label='TDM32', fontcolor='#FFC107', fontsize='9')
                else:
                    dot.edge(src_group, dst_group)
                edges_added.add(edge_key)

    # Add H1S1 SPI control node
    dot.node('H1S1', 'H1S1 MCU\\n(STM32U575)\\nSPI Control',
             shape='ellipse', fillcolor='#455A64', fontcolor='white')
    dot.node('PI', 'Pi (MH1)\\nMatrix App',
             shape='ellipse', fillcolor='#37474F', fontcolor='white')

    dot.edge('PI', 'H1S1', label='Serial', color='#90A4AE', fontcolor='#90A4AE', fontsize='9')

    # Find first chip1 node for SPI arrow
    chip1_groups = [g for g in groups if g['chip'] == '1']
    if chip1_groups:
        dot.edge('H1S1', chip1_groups[0]['group_id'], label='SPI', color='#90A4AE',
                 fontcolor='#90A4AE', fontsize='9', style='dashed')

    # Render
    output_base = output_path.rsplit('.', 1)[0] if '.' in output_path else output_path
    dot.render(output_base, cleanup=True)
    print(f"Diagram written to: {output_path}")
    return 0


if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))

    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    else:
        csv_path = os.path.join(script_dir, '..', 'dsp.csv')

    if len(sys.argv) > 2:
        out_path = sys.argv[2]
    else:
        out_path = os.path.join(script_dir, '..', 'dsp_diagram.png')

    sys.exit(generate_diagram(csv_path, out_path))
