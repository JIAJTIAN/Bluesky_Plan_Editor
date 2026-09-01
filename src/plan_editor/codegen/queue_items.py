"""Convert canvas nodes to bluesky-queueserver plan-item dicts.

Used for simple linear chains that can be submitted as individual queue items
rather than a full Python script.
"""
from __future__ import annotations

from plan_editor.codegen.utils import (
    _extract_pairs, _float, _int, _parse_det_list, _try_float,
)


def build_queue_items(scene) -> list[dict]:
    """Return queue-server plan items for a simple linear chain.

    Returns an empty list if the graph contains composition nodes (e.g. sequence
    or loops), because those require a Python function — use generate_plan_code()
    and submit as a script in that case.
    """
    from plan_editor.canvas.node import BaseNode

    COMPOSITION = {"sequence"}
    nodes = [i for i in scene.items() if isinstance(i, BaseNode)]
    if any(n.schema.node_id in COMPOSITION for n in nodes):
        return []

    sink = next((n for n in nodes if n.schema.node_id == "plan_output"), None)
    if sink is None or not (sink.input_ports and sink.input_ports[0].wires):
        return []

    # Walk chain upstream from sink, then reverse to get execution order
    ordered: list = []
    cursor  = sink.input_ports[0].wires[0].src.node
    visited: set  = set()
    while cursor is not None and id(cursor) not in visited:
        visited.add(id(cursor))
        if cursor.schema.node_id != "plan_output":
            ordered.append(cursor)
        if cursor.input_ports and cursor.input_ports[0].wires:
            cursor = cursor.input_ports[0].wires[0].src.node
        else:
            break

    ordered.reverse()
    return [item for node in ordered for item in [_node_to_queue_item(node)] if item]


def _node_to_queue_item(node) -> dict | None:
    """Convert one leaf node to a queue-server plan item dict, or None if unsupported."""
    nid = node.schema.node_id
    p   = dict(node.params)

    if nid in ("scan", "rel_scan"):
        dets = _parse_det_list(p.get("detectors", ""))
        args: list = []
        i = 0
        while f"motor_{i}" in p:
            args += [p[f"motor_{i}"],
                     _try_float(p.get(f"start_{i}", 0)),
                     _try_float(p.get(f"stop_{i}",  1))]
            i += 1
        return {"name": nid, "item_type": "plan",
                "kwargs": {"detectors": dets, "args": args, "num": _int(p.get("num", 11))}}

    if nid == "count":
        dets = _parse_det_list(p.get("detectors", ""))
        return {"name": "count", "item_type": "plan",
                "kwargs": {"detectors": dets,
                           "num":   _int(p.get("num",   1)),
                           "delay": _float(p.get("delay", 0))}}

    if nid == "mv":
        pairs = _extract_pairs(p, "motor", "pos")
        args  = [x for m, v in pairs for x in (m, _try_float(v))]
        return {"name": "mv", "item_type": "plan", "kwargs": {"args": args}}

    if nid == "mvr":
        pairs = _extract_pairs(p, "motor", "delta")
        args  = [x for m, d in pairs for x in (m, _try_float(d))]
        return {"name": "mvr", "item_type": "plan", "kwargs": {"args": args}}

    if nid == "sleep":
        return {"name": "sleep", "item_type": "plan",
                "kwargs": {"time": _float(p["delay"])}}

    if nid == "grid_scan":
        dets = _parse_det_list(p.get("detectors", ""))
        return {"name": "grid_scan", "item_type": "plan",
                "kwargs": {"detectors": dets,
                           "args": [p["motor1"],
                                    _try_float(p["start1"]), _try_float(p["stop1"]), _int(p["num1"]),
                                    p["motor2"],
                                    _try_float(p["start2"]), _try_float(p["stop2"]), _int(p["num2"])]}}

    return None
