"""Per-node call-string builders: _build_call and its helpers.

Each branch handles one node type and returns the Python expression that
yield-from will run.  Add a new elif here when adding a new node schema.
"""
from __future__ import annotations

from plan_editor.codegen.utils import (
    _bool, _det_list, _extract_pairs, _float, _int,
    _md_kwarg, _motor_range_args, _val_list,
)


# ── value resolution ──────────────────────────────────────────────────────────

def _node_value(node) -> str:
    """Return the Python expression emitted by a source value node."""
    nid = node.schema.node_id
    if nid == "devices":
        parts, i = [], 0
        while f"device_{i}" in node.params:
            v = str(node.params[f"device_{i}"]).strip()
            if v:
                parts.append(v)
            i += 1
        if not parts:
            return "[]"
        return parts[0] if len(parts) == 1 else "[" + ", ".join(parts) + "]"
    if nid == "string_input":
        return repr(str(node.params.get("value", "")))
    if nid == "array_input":
        return _val_list(str(node.params.get("values", "")).strip())
    if nid == "loop_var":
        return str(node.params.get("var_name", "_val")).strip()
    if nid == "scan_range":
        parts, i = [], 0
        while f"start_{i}" in node.params:
            s = node.params[f"start_{i}"]
            e = node.params[f"stop_{i}"]
            parts.append(f"({s}, {e})")
            i += 1
        return "[" + ", ".join(parts) + "]"
    return str(node.params.get("name", node.schema.title)).strip()


def _node_value_from_port(src_port) -> str:
    """Return value expression for a specific source port (handles multi-output nodes)."""
    node = src_port.node
    nid  = node.schema.node_id
    if nid == "array_input" and getattr(node.schema, "expand_output_ports", False):
        key = f"values_{src_port.index}"
        return _val_list(str(node.params.get(key, "")).strip())
    return _node_value(node)


def _resolve_params(node) -> dict:
    """Return params dict with wired value-port expressions overriding text fields."""
    p = dict(node.params)
    n_flow = len(node.schema.inputs)
    for idx, name in enumerate(node.schema.value_inputs):
        port_idx = n_flow + idx
        if port_idx < len(node.input_ports):
            port = node.input_ports[port_idx]
            if port.wires:
                p[name] = _node_value_from_port(port.wires[0].src)
    return p


def _get_wired_node(node, param_name: str):
    """Return the source node wired to the named value_input port, or None."""
    n_flow = len(node.schema.inputs)
    for idx, name in enumerate(node.schema.value_inputs):
        if name == param_name:
            port_idx = n_flow + idx
            if port_idx < len(node.input_ports):
                port = node.input_ports[port_idx]
                if port.wires:
                    return port.wires[0].src.node
    return None


def _zip_motor_position_args(motors_node, positions_node) -> str:
    """Build interleaved 'motor, start, stop' args from a devices + scan_range pair."""
    motors: list[str] = []
    i = 0
    while f"device_{i}" in motors_node.params:
        v = str(motors_node.params[f"device_{i}"]).strip()
        if v:
            motors.append(v)
        i += 1
    if not motors:
        motors = ["motor"]
    parts = []
    for j, m in enumerate(motors):
        s = positions_node.params.get(f"start_{j}", 0)
        e = positions_node.params.get(f"stop_{j}",  1)
        parts.append(f"{m}, {s}, {e}")
    return ", ".join(parts) if parts else "motor, 0, 1"


# ── main builder ──────────────────────────────────────────────────────────────

def _build_call(node) -> str:
    """Return a Python expression string for one node (no 'yield from' prefix)."""
    nid = node.schema.node_id
    p   = _resolve_params(node)

    if nid in ("scan", "rel_scan"):
        fn   = "bp.scan" if nid == "scan" else "bp.rel_scan"
        dets = str(p.get("detectors", "[]"))
        if dets and not dets.startswith("["):
            dets = "[" + dets + "]"
        if not dets:
            dets = "[]"
        md = _md_kwarg(p.get("md", ""))
        motors_src    = _get_wired_node(node, "motors")
        positions_src = _get_wired_node(node, "positions")
        if motors_src and positions_src:
            motor_args = _zip_motor_position_args(motors_src, positions_src)
            num = _int(positions_src.params.get("num", p.get("num", 11)))
        else:
            motor_args = _motor_range_args(p) or "motor, 0, 1"
            num = _int(p.get("num", 11))
        return f"{fn}({dets}, {motor_args}, num={num}{md})"

    if nid == "grid_scan":
        dets   = _det_list(p.get("detectors", ""))
        snake1 = _bool(p.get("snake1", False))
        snake2 = _bool(p.get("snake2", False))
        return (f"bp.grid_scan({dets}, "
                f"{p['motor1']}, {p['start1']}, {p['stop1']}, {_int(p['num1'])}, {snake1}, "
                f"{p['motor2']}, {p['start2']}, {p['stop2']}, {_int(p['num2'])}, {snake2})")

    if nid == "count":
        dets = _det_list(p.get("detectors", ""))
        md   = _md_kwarg(p.get("md", ""))
        return (f"bp.count({dets}, "
                f"num={_int(p.get('num', 1))}, delay={_float(p.get('delay', 0))}{md})")

    if nid == "custom_call":
        def _pv(port):
            return _node_value(port.wires[0].src.node) if port.wires else ""
        func   = _pv(node.input_ports[1]) if len(node.input_ports) > 1 else ""
        wired  = [_pv(port) for port in node.input_ports[2:] if _pv(port)]
        extra  = str(p.get("extra_args", "")).strip()
        all_args = ", ".join(wired + ([extra] if extra else []))
        if not func:
            return "pass  # custom_call: func port not connected"
        return f"{func}({all_args})" if all_args else f"{func}()"

    if nid == "mv":
        positions_src = _get_wired_node(node, "positions")
        if positions_src is not None:
            pos_expr = _node_value(positions_src)
            motors = [str(p[k]).strip() for k in sorted(p)
                      if k.startswith("motor_") and str(p[k]).strip()]
            args = ", ".join(f"{m}, {pos_expr}" for m in motors) if motors else f"motor, {pos_expr}"
        else:
            pairs = _extract_pairs(p, "motor", "pos")
            args  = ", ".join(f"{m}, {v}" for m, v in pairs)
        return f"bps.mv({args})"

    if nid == "mvr":
        positions_src = _get_wired_node(node, "positions")
        if positions_src is not None:
            pos_expr = _node_value(positions_src)
            motors = [str(p[k]).strip() for k in sorted(p)
                      if k.startswith("motor_") and str(p[k]).strip()]
            args = ", ".join(f"{m}, {pos_expr}" for m in motors) if motors else f"motor, {pos_expr}"
        else:
            pairs = _extract_pairs(p, "motor", "delta")
            args  = ", ".join(f"{m}, {d}" for m, d in pairs)
        return f"bps.mvr({args})"

    if nid == "sleep":
        return f"bps.sleep({p['delay']})"

    if nid == "trigger_and_read":
        devs = _det_list(p.get("devices", ""))
        return f"bps.trigger_and_read({devs})"

    if nid == "open_run":
        md_raw = str(p.get("md", "")).strip()
        if md_raw:
            md: dict = {}
            for part in md_raw.split(","):
                if "=" in part:
                    k, _, v = part.partition("=")
                    md[k.strip()] = v.strip()
                elif part.strip():
                    md["label"] = part.strip()
            return f"bps.open_run(md={md!r})"
        return "bps.open_run()"

    if nid == "close_run":
        return "bps.close_run()"

    if nid == "checkpoint":
        return "bps.checkpoint()"

    if nid == "pause":
        return "bps.pause()"

    if nid == "configure":
        dev = str(p.get("device", "")).strip()
        config_raw = str(p.get("config", "")).strip()
        if config_raw:
            kw: dict = {}
            for part in config_raw.split(","):
                if "=" in part:
                    k, _, v = part.partition("=")
                    kw[k.strip()] = v.strip()
            kw_str = ", ".join(f"{k}={v}" for k, v in kw.items())
            return f"bps.configure({dev}, {kw_str})"
        return f"bps.configure({dev})"

    if nid == "stage_all":
        return f"bps.stage_all(*{_det_list(p.get('devices', ''))})"

    if nid == "unstage_all":
        return f"bps.unstage_all(*{_det_list(p.get('devices', ''))})"

    if nid == "plan_output":
        return ""

    # Unknown / user-added node — emit a generic keyword-arg call
    kwargs = ", ".join(f"{k}={v!r}" for k, v in p.items())
    return f"{nid}({kwargs})"
