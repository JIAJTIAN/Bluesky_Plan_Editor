"""DAG traversal and Python code generation for Bluesky plans.

Wires carry execution ORDER, not data.  The graph is walked backwards from
the plan_output sink, then code is emitted top-to-bottom.

Wire direction:  upstream.output_port ──wire──▶ downstream.input_port
Execution order: upstream runs BEFORE downstream.

Entry points
------------
generate_plan_code(scene) -> str
    Full Python function string ready to run or copy.
"""
from __future__ import annotations

from plan_editor.codegen.call_builders import (
    _build_call, _get_wired_node, _node_value_from_port,
    _resolve_params, _zip_motor_position_args,
)
from plan_editor.codegen.utils import _float, _int, _motor_range_args, _val_list

_IMPORTS = """\
import bluesky.plans as bp
import bluesky.plan_stubs as bps
import bluesky.preprocessors as bpp
from ophyd.sim import (det, det1, det2, noisy_det, rand, rand2,
                       ab_det, direct_img, direct_img_list,
                       motor, motor1, motor2, flyer1, flyer2)
"""


def generate_plan_code(scene) -> str:
    """Walk the node graph and return a complete Python plan function string."""
    from plan_editor.canvas.node import BaseNode

    nodes = [i for i in scene.items() if isinstance(i, BaseNode)]
    sink  = next((n for n in nodes if n.schema.node_id == "plan_output"), None)

    if sink is None:
        return "# Add a 'Run / Export' node to the canvas to see generated code."

    lines = [_IMPORTS, "def my_plan():"]
    if sink.input_ports and sink.input_ports[0].wires:
        src_node = sink.input_ports[0].wires[0].src.node
        lines.extend(_gen_item(src_node, indent=1, visited=frozenset()))
    else:
        lines.append("    pass  # connect a plan to the Run / Export node")

    return "\n".join(lines)


# ── dispatch ──────────────────────────────────────────────────────────────────

def _gen_item(item, indent: int, visited: frozenset) -> list[str]:
    """Dispatch to LoopFrame or BaseNode generator."""
    from plan_editor.canvas.loop_frame import LoopFrame
    if isinstance(item, LoopFrame):
        return _gen_loop_frame(item, indent, visited)
    return _gen_node(item, indent, visited)


# ── loop-frame generator ──────────────────────────────────────────────────────

def _gen_body_chain(start_node, indent: int, visited: frozenset) -> list[str]:
    """Walk the plan-output chain from start_node, emitting one call per step.

    Does NOT recurse upstream — the loop frame already owns ordering.
    Nested LoopFrames and for_each nodes dispatch to their own generators.
    """
    from plan_editor.canvas.loop_frame import LoopFrame
    pad   = "    " * indent
    lines: list[str] = []
    node  = start_node
    seen: frozenset = frozenset()

    while node is not None and id(node) not in seen and id(node) not in visited:
        seen = seen | frozenset([id(node)])

        if isinstance(node, LoopFrame):
            lines.extend(_gen_loop_frame(node, indent, visited | seen))
        elif node.schema.node_id == "for_each":
            lines.extend(_gen_node(node, indent, visited | seen))
        else:
            call = _build_call(node)
            if call:
                lines.append(f"{pad}yield from {call}")

        next_node = None
        for p in node.output_ports:
            if p.port_type == "plan" and p.wires:
                cand = p.wires[0].dst.node
                if id(cand) not in seen and id(cand) not in visited:
                    next_node = cand
                    break
        node = next_node

    return lines


def _gen_loop_frame(frame, indent: int, visited: frozenset) -> list[str]:
    """Generate a 'for … in zip(…):' block for a LoopFrame."""
    if id(frame) in visited:
        return [f"{'    ' * indent}# (cycle — skipping loop frame)"]
    visited = visited | frozenset([id(frame)])
    pad = "    " * indent

    lines: list[str] = []

    # Nodes upstream of the frame's flow-in port (skip already-visited to avoid
    # cycle comments when a body_port wire connects directly to this frame)
    if frame._in_port.wires:
        up = frame._in_port.wires[0].src.node
        if id(up) not in visited:
            lines.extend(_gen_item(up, indent, visited))

    # Zip variable names and list expressions (one per list port)
    zip_vars:  list[str] = []
    zip_lists: list[str] = []
    for i, port in enumerate(frame._list_ports):
        var = frame.var_name(i)
        lst = _node_value_from_port(port.wires[0].src) if port.wires else f"[]  # list {i+1} not connected"
        zip_vars.append(var)
        zip_lists.append(lst)

    # Body: follow plan chain from each func port
    inner_visited = visited | frozenset([id(frame)])
    body_lines: list[str] = []
    for bp in frame._body_ports:
        if bp.wires:
            body_lines.extend(_gen_body_chain(bp.wires[0].dst.node, indent + 1, inner_visited))
    if not body_lines:
        body_lines = [f"{pad}    pass  # wire func ports to plan nodes"]

    vars_str  = ", ".join(zip_vars)  if zip_vars  else "_v"
    lists_str = ", ".join(zip_lists) if zip_lists else "[]"
    if len(zip_lists) == 1:
        lines.append(f"{pad}for {vars_str} in {lists_str}:")
    else:
        lines.append(f"{pad}for {vars_str} in zip({lists_str}):")
    lines.extend(body_lines)
    return lines


# ── node generator ────────────────────────────────────────────────────────────

def _gen_node(node, indent: int, visited: frozenset) -> list[str]:
    """Return lines of Python that execute this node (and all its upstream nodes)."""
    from plan_editor.canvas.loop_frame import LoopFrame
    if isinstance(node, LoopFrame):
        return _gen_loop_frame(node, indent, visited)
    if id(node) in visited:
        return [f"{'    ' * indent}# (cycle — skipping {node.schema.title!r})"]
    visited = visited | frozenset([id(node)])

    pad = "    " * indent
    nid = node.schema.node_id
    p   = _resolve_params(node)

    # ── if / else block ───────────────────────────────────────────────────────
    if nid == "if_block":
        condition = str(p.get("condition", "True")).strip()
        lines: list[str] = []
        if node.input_ports and node.input_ports[0].wires:
            lines.extend(_gen_item(node.input_ports[0].wires[0].src.node, indent, visited))
        lines.append(f"{pad}if {condition}:")
        if len(node.input_ports) > 1 and node.input_ports[1].wires:
            lines.extend(_gen_node(node.input_ports[1].wires[0].src.node, indent + 1, visited))
        else:
            lines.append(f"{pad}    pass")
        if len(node.input_ports) > 2 and node.input_ports[2].wires:
            lines.append(f"{pad}else:")
            lines.extend(_gen_node(node.input_ports[2].wires[0].src.node, indent + 1, visited))
        return lines

    # ── sequence: run each input branch in port order ─────────────────────────
    if nid == "sequence":
        lines: list[str] = []
        for port in node.input_ports:
            if port.wires:
                lines.extend(_gen_node(port.wires[0].src.node, indent, visited))
        return lines or [f"{pad}pass  # sequence: no plans connected"]

    # ── for_each: loop over a value list; body comes from input port 1 ────────
    if nid == "for_each":
        var        = str(p.get("variable", "_val")).strip() or "_val"
        delay      = _float(p.get("delay", 0))
        values_raw = str(p.get("values", "0")).strip()

        lines = []
        if node.input_ports and node.input_ports[0].wires:
            lines.extend(_gen_item(node.input_ports[0].wires[0].src.node, indent, visited))

        body_lines: list[str] = []
        if len(node.input_ports) > 1 and node.input_ports[1].wires:
            body_lines = _gen_node(node.input_ports[1].wires[0].src.node, indent + 1, visited)

        lines.append(f"{pad}for {var} in {_val_list(values_raw)}:")
        lines.extend(body_lines or [f"{pad}    pass"])
        if delay > 0:
            lines.append(f"{pad}    yield from bps.sleep({delay})")
        return lines

    # ── scan_w_delay: scan with per-step shutter + delay ─────────────────────
    if nid == "scan_w_delay":
        lines = []
        if node.input_ports and node.input_ports[0].wires:
            lines.extend(_gen_item(node.input_ports[0].wires[0].src.node, indent, visited))
        fn_name  = f"_step_{id(node) & 0xFFFF:04x}"
        dets_raw = str(p.get("detectors", "[]"))
        dets     = dets_raw if dets_raw.startswith("[") else (f"[{dets_raw}]" if dets_raw else "[]")
        num      = _int(p.get("num", 11))
        shutter  = str(p.get("shutter", "")).strip()
        delay    = _float(p.get("delay", 0))
        motors_src    = _get_wired_node(node, "motors")
        positions_src = _get_wired_node(node, "positions")
        if motors_src and positions_src:
            motor_args = _zip_motor_position_args(motors_src, positions_src)
            num = _int(positions_src.params.get("num", num))
        else:
            motor_args = _motor_range_args(p) or "motor, 0, 1"
        fp = "    " * (indent + 1)
        lines += [
            f"{pad}def {fn_name}(detectors, step, pos_cache):",
            f"{fp}yield from bps.move_per_step(step, pos_cache)",
        ]
        if shutter:
            lines += [f"{fp}yield from bps.mv({shutter}, 0)",
                      f"{fp}yield from bps.sleep(0.3)"]
        lines.append(f"{fp}yield from bps.trigger_and_read(list(detectors) + list(step.keys()))")
        if shutter:
            lines.append(f"{fp}yield from bps.mv({shutter}, 1)")
        if delay > 0:
            lines.append(f"{fp}yield from bps.sleep({delay})")
        lines.append(f"{pad}yield from bp.scan({dets}, {motor_args}, num={num}, per_step={fn_name})")
        return lines

    # ── generic leaf: generate upstream, then this node ───────────────────────
    lines = []
    if node.input_ports and node.input_ports[0].wires:
        lines.extend(_gen_item(node.input_ports[0].wires[0].src.node, indent, visited))
    call = _build_call(node)
    if call:
        lines.append(f"{pad}yield from {call}")
    return lines
