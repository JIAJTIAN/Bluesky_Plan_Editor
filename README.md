# Bluesky Plan Editor

A visual node-graph editor for composing [Bluesky](https://blueskyproject.io/) experiment plans at synchrotron beamlines, built with PySide6/Qt6.

![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![PySide6](https://img.shields.io/badge/UI-PySide6-green)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

## What it does

Instead of writing Python by hand, you drag and drop plan nodes onto a canvas, wire them together, and the editor generates a ready-to-run Bluesky plan function. Plans can be submitted directly to a running [bluesky-queueserver](https://blueskyproject.io/bluesky-queueserver/) or copied as Python code.

**Key features**

- **Node palette** — browse scans, motions, detectors, run boundaries, and flow-control nodes by category
- **Loop frames** — wrap any chain of nodes in a `for … in` or `for x, y in zip(…)` loop; nest frames for multi-axis scans
- **Live code preview** — the generated Python plan updates in real time as you edit the canvas
- **Save / load** — canvases are stored as plain JSON (`.plan.json`)
- **Queue Server submission** — one-click submit to bluesky-queueserver over HTTP
- **Example templates** — load a simplified or full nested energy scan from the Examples menu

## Built-in node types

| Category | Nodes |
|---|---|
| Scan | `scan`, `rel_scan`, `grid_scan`, `scan_w_delay` |
| Motion | `mv`, `mvr` |
| Acquire | `trigger_and_read`, `count` |
| Run | `open_run`, `close_run` |
| Control | `sleep`, `checkpoint`, `pause` |
| Flow | `sequence`, `for_each`, `zip_loop` |
| Device | `configure`, `stage_all`, `unstage_all` |
| Custom | `custom_call` |
| Output | `plan_output` |

## Installation

```bash
git clone https://github.com/JIAJTIAN/Bluesky_Plan_Editor.git
cd Bluesky_Plan_Editor
pip install -e .
```

**Dependencies:** PySide6 ≥ 6.7, bluesky ≥ 1.13, ophyd ≥ 1.9, numpy

## Usage

```bash
plan-editor
```

| Action | How |
|---|---|
| Add node | Double-click palette, or **Shift+A** to search |
| Add loop frame | **Ctrl+J** |
| Connect nodes | Drag from an output port to an input port |
| Delete | Select + **Delete** key |
| Pan / zoom | Middle-drag / scroll wheel |
| Undo / redo | **Ctrl+Z** / **Ctrl+Y** |
| Save | **Ctrl+S** |
| Load example | **Examples** menu |

## Project structure

```
src/plan_editor/
├── canvas/       # Qt scene, nodes, loop frames, ports, wires
├── codegen/      # Plan code generation and queue-server serialisation
├── registry/     # Node schema definitions (BUILTIN_NODES)
└── ui/           # Main window, palette, properties panel, search popup
```

## Development

```bash
pip install -e ".[dev]"
pytest
```

---

Developed at [ChemMatCARS](https://chemmatcars.uchicago.edu/), University of Chicago / Advanced Photon Source.
