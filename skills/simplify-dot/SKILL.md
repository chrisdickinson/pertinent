---
name: simplify-dot
description: Visually simplify a Graphviz DOT graph that is too dense to read, without losing information. Label detail moves into tooltips; clusters collapse; views focus on a node's neighborhood. Use when asked to simplify, declutter, tidy, or make an overview of a .dot diagram, or when a rendered graph is unreadable.
---

# Simplify DOT

**Core principle**: a simplified graph is a *view* of the source, not a
replacement. Never edit the source `.dot`. Write siblings next to it. Move
text into tooltips instead of deleting it, so an SVG render shows it on hover.

The script is `scripts/simplify_dot.py` in this skill's base directory.
It needs Python 3.9+ and nothing else. Rendering needs Graphviz `dot`.

## Workflow

1. **Measure.** `python3 <base>/scripts/simplify_dot.py stats IN.dot`.
   Read the cluster sizes, the heaviest labels, the share of label text the
   detail pass would move, and the lint.
2. **Report lint as a source bug.** A lint line ending `<- drawn inside X`
   means an edge written inside cluster X pulled a node into X that is
   declared elsewhere. Graphviz draws a node in the first cluster that
   mentions it. The `hoist` pass fixes the view. Tell the user so the source
   can be fixed too, by moving that edge out of the cluster body.
3. **Simplify.** Start with the default preset:
   ```bash
   python3 <base>/scripts/simplify_dot.py simplify IN.dot -o IN.tidy.dot --render png --dpi 40
   ```
4. **Look.** Read the PNG. Check it against the checklist below.
5. **Escalate one step at a time.** Try `--preset overview`, then
   `--collapse`, `--collapse-except`, or `--focus` for a view that answers
   one question. Re-render and look after each step.
6. **Deliver SVG.** Re-run with `--render svg` for the final file. SVG keeps
   the tooltips, which PNG does not.
7. **Report.** Give the before → after line the script prints. Say what moved
   to tooltips and what was removed (`drop-undirected`, `chains`, `tred` and
   `collapse` remove or merge nodes and edges).

## Presets

| Preset     | Passes                                                                 | Loses information? |
| ---------- | ---------------------------------------------------------------------- | ------------------ |
| `tidy`     | hoist, merge-parallel, detail, edge-labels (40 chars)                  | no — text moves to tooltips |
| `overview` | tidy + drop-undirected, label-lines 3, edge-labels 24, chains, tred    | drops association and redundant edges; merges chains |
| `none`     | only the passes you add                                                | —                  |

Adjust with `--add PASS`, `--skip PASS`, `--edge-label-max N`, and
`--label-lines N`.

## Passes

| Pass              | Effect |
| ----------------- | ------ |
| `hoist`           | Moves cluster-body edges with a foreign endpoint to the root, so nodes draw in their own cluster. |
| `focus`           | `--focus a,b --depth N` keeps nodes within N hops. |
| `collapse`        | `--collapse NAME` (repeatable) or `--collapse-except NAME` replaces clusters with one summary node. The member list goes to its tooltip. NAME matches the cluster id, the id without `cluster_`, or a label substring. |
| `drop-undirected` | Drops `dir=none` association edges. |
| `merge-parallel`  | Merges edges with the same tail, head, `dir` and `style`, joining their labels. |
| `detail`          | In HTML node labels, strips `<font>` runs set in a monospace face or smaller than the node's font size. Graph and cluster labels lose only monospace runs, so legends stay. `--detail-mono-only` narrows node labels the same way. |
| `label-lines`     | Caps node labels at N lines. Labels built from HTML tables are left alone. |
| `edge-labels`     | Shortens edge labels to one line at a word boundary. `--edge-labels none` moves them all to tooltips. |
| `chains`          | Merges runs of 1-in/1-out nodes within one cluster, joined by unlabeled edges, into one node. `--chains-labeled` also absorbs labeled edges. |
| `tred`            | Drops unlabeled edges implied by another path. `--tred-labeled` also drops labeled ones. |

Layout knobs go through `--set`, e.g. `--set graph.ranksep=0.3`,
`--set graph.nodesep=0.15`, `--set graph.splines=polyline`,
`--set graph.concentrate=true`, `--set node.fontsize=10`.
`splines=ortho` cannot place edge labels; pair it with `--edge-labels none`.

## Visual checklist

- Every node sits in the cluster it belongs to (lint is clean after hoist).
- Node labels read at the intended zoom: 1–3 short lines.
- No cluster dominates the page. If one does, collapse it or give it its own
  `--focus` view.
- Long edges crossing the whole graph are few. Many long edges mean the
  question needs a narrower view, not a tidier one.
- Past ~60 nodes, prefer several focused views over one overview.
- The legend still explains every line style and fill that remains.

## Limits

- Tooltip de-duplication is heuristic. A moved line is skipped when the
  tooltip already holds the line, or the basename of every path in it.
  Expect some near-duplicate lines.
- Comments in the source are not carried into the output.
- Edge statements with subgraph endpoints (`a -> {b c}`) are expanded into
  one edge per pair.
