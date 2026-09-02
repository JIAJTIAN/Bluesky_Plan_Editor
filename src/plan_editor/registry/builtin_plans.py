"""Built-in Bluesky plan node definitions.

Rule: only port_type="plan" appears as a connectable socket.
Everything else (motor, detector, numbers) is a plain param field.
"""
from __future__ import annotations

from plan_editor.registry.schema import NodeSchema, PortSpec

# ── ophyd.sim simulated devices ───────────────────────────────────────────────
SIM_DETECTORS = ["det", "det1", "det2", "noisy_det", "rand", "rand2",
                 "ab_det", "direct_img", "direct_img_list"]
SIM_MOTORS    = ["motor", "motor1", "motor2"]
SIM_DEVICES   = SIM_DETECTORS + SIM_MOTORS + ["flyer1", "flyer2"]

BUILTIN_NODES: list[NodeSchema] = [

    # ── Leaf plans — each has a flow-in and flow-out so they chain linearly ────
    NodeSchema(
        node_id="scan",
        title="scan",
        category="scan",
        inputs=[PortSpec("in", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={"detectors": "", "num": 11, "md": ""},
        value_inputs=("detectors", "motors", "positions"),
        param_choices={"detectors": SIM_DETECTORS},
        desc="Step-scan. Type detectors directly or wire a 'devices' node. Wire a 'devices' node → motors and a 'scan range' node → positions.",
    ),
    NodeSchema(
        node_id="rel_scan",
        title="rel_scan",
        category="scan",
        inputs=[PortSpec("in", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={"detectors": "", "num": 11, "md": ""},
        value_inputs=("detectors", "motors", "positions"),
        param_choices={"detectors": SIM_DETECTORS},
        desc="Relative scan. Type detectors directly or wire a 'devices' node. Wire motors and scan range as usual.",
    ),
    NodeSchema(
        node_id="grid_scan",
        title="grid_scan",
        category="scan",
        inputs=[PortSpec("in", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={"detectors": "", "motor1": "", "start1": 0.0, "stop1": 1.0, "num1": 5,
                "snake1": False,
                "motor2": "", "start2": 0.0, "stop2": 1.0, "num2": 5,
                "snake2": False},
        value_inputs=("detectors", "motor1", "motor2"),
        param_choices={"detectors": SIM_DETECTORS, "motor1": SIM_MOTORS, "motor2": SIM_MOTORS},
        desc="2D mesh scan. Type detectors/motors directly or wire 'devices' nodes. snake=True reverses direction on alternate rows.",
    ),
    NodeSchema(
        node_id="scan_w_delay",
        title="scan  (shutter + delay)",
        category="scan",
        inputs=[PortSpec("in", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={"detectors": "", "shutter": "", "delay": 0.0, "num": 11},
        value_inputs=("detectors", "motors", "positions"),
        param_choices={"detectors": SIM_DETECTORS, "shutter": SIM_DEVICES},
        desc="Step-scan with per-step shutter and delay. Type detectors directly or wire them. Wire motors and scan range as usual.",
    ),
    NodeSchema(
        node_id="count",
        title="count",
        category="scan",
        inputs=[PortSpec("in", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={"detectors": "", "num": 1, "delay": 0.0, "md": ""},
        value_inputs=("detectors",),
        param_choices={"detectors": SIM_DETECTORS},
        desc="Trigger and read detectors num times. Type detector names (comma-separated) or wire a 'devices' node.",
    ),
    NodeSchema(
        node_id="mv",
        title="mv  (move)",
        category="motion",
        inputs=[PortSpec("in", "plan"), PortSpec("device", "value")],
        outputs=[PortSpec("out", "plan")],
        params={},
        expandable_ports=True,
        expand_port_type="value",
        expand_port_name="device",
        min_ports=2,
        desc="Move motors to absolute positions. Wire Motor device nodes to each 'device' port. Use + / − to add more motors.",
    ),
    NodeSchema(
        node_id="mvr",
        title="mvr  (relative move)",
        category="motion",
        inputs=[PortSpec("in", "plan"), PortSpec("device", "value")],
        outputs=[PortSpec("out", "plan")],
        params={},
        expandable_ports=True,
        expand_port_type="value",
        expand_port_name="device",
        min_ports=2,
        desc="Move motors by relative offsets. Wire Motor device nodes (use the delta field for the offset) to each 'device' port. Use + / − to add more motors.",
    ),
    NodeSchema(
        node_id="sleep",
        title="sleep",
        category="motion",
        inputs=[PortSpec("in", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={"delay": 1.0},
        desc="Pause execution for a fixed number of seconds. The RunEngine remains responsive during the wait.",
    ),

    # ── Loop ──────────────────────────────────────────────────────────────────
    NodeSchema(
        node_id="zip_loop",
        title="zip loop",
        category="loop",
        inputs=[],
        outputs=[],
        params={},
        desc="Frame container. Nodes placed inside execute as the loop body. Add list inputs with +; auto-creates a variable node inside for each list. Variables hold list[index] each iteration.",
    ),
    NodeSchema(
        node_id="for_each",
        title="for each",
        category="loop",
        inputs=[PortSpec("in", "plan"), PortSpec("body", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={"variable": "_val", "values": "0, 1, 2", "delay": 0.0},
        value_inputs=("values",),
        desc="Loop over a list of values. Connect the plan to run at each step to the 'body' port. Use the variable name (e.g. _val) in downstream param fields — it is a live Python identifier inside the loop.",
    ),

    # ── Acquire ───────────────────────────────────────────────────────────────
    NodeSchema(
        node_id="trigger_and_read",
        title="trigger_and_read",
        category="acquire",
        inputs=[PortSpec("in", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={"devices": ""},
        value_inputs=("devices",),
        param_choices={"devices": SIM_DEVICES},
        desc="Trigger and read devices. Type names directly (comma-separated) or wire a 'devices' node.",
    ),

    # ── Run boundary ──────────────────────────────────────────────────────────
    NodeSchema(
        node_id="open_run",
        title="open_run",
        category="run",
        inputs=[PortSpec("in", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={"md": ""},
        desc="Open a bluesky run (data boundary). All trigger_and_read events between open_run and close_run are recorded in the same run document. Must be paired with a close_run node.",
    ),
    NodeSchema(
        node_id="close_run",
        title="close_run",
        category="run",
        inputs=[PortSpec("in", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={},
        desc="Close the currently open bluesky run. Must follow an open_run node earlier in the chain.",
    ),

    # ── Control ───────────────────────────────────────────────────────────────
    NodeSchema(
        node_id="checkpoint",
        title="checkpoint",
        category="control",
        inputs=[PortSpec("in", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={},
        desc="Insert a RunEngine pause/resume checkpoint. The operator can pause the RunEngine here and resume from this exact point. Place inside loops to allow graceful interruption between iterations.",
    ),
    NodeSchema(
        node_id="pause",
        title="pause",
        category="control",
        inputs=[PortSpec("in", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={},
        desc="Hard pause — the RunEngine stops immediately and waits for the operator to call RE.resume() or RE.abort(). Use for sample swaps, beam checks, or any step requiring hands-on intervention.",
    ),
    NodeSchema(
        node_id="configure",
        title="configure",
        category="control",
        inputs=[PortSpec("in", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={"device": "", "config": ""},
        value_inputs=("device",),
        param_choices={"device": SIM_DEVICES},
        desc="Change a device's configuration mid-plan. Type or pick a device; enter config as key=value pairs, e.g. 'acquire_time=0.5, gain=2'.",
    ),
    NodeSchema(
        node_id="stage_all",
        title="stage_all",
        category="control",
        inputs=[PortSpec("in", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={"devices": ""},
        value_inputs=("devices",),
        param_choices={"devices": SIM_DEVICES},
        desc="Arm / prepare devices before acquisition. Type names directly or wire a 'devices' node.",
    ),
    NodeSchema(
        node_id="unstage_all",
        title="unstage_all",
        category="control",
        inputs=[PortSpec("in", "plan")],
        outputs=[PortSpec("out", "plan")],
        params={"devices": ""},
        value_inputs=("devices",),
        param_choices={"devices": SIM_DEVICES},
        desc="Disarm / release devices after acquisition. Type names directly or wire a 'devices' node.",
    ),

    # ── Composition nodes (take plan inputs, produce plan output) ─────────────
    NodeSchema(
        node_id="if_block",
        title="if / else",
        category="flow",
        inputs=[
            PortSpec("in",        "plan"),
            PortSpec("condition", "value"),   # wire a loop_var, sensor reading, etc.
            PortSpec("true ▶",   "plan"),    # plan body when condition is true
            PortSpec("false ▶",  "plan"),    # plan body when condition is false
        ],
        outputs=[
            PortSpec("true out",  "plan"),   # continuation after the true branch
            PortSpec("false out", "plan"),   # continuation after the false branch
        ],
        params={"operator": "==", "threshold": ""},
        param_choices={"operator": ["==", "!=", ">", "<", ">=", "<=", "is", "is not"]},
        desc=(
            "Conditional branch. Wire a value node (e.g. loop variable) to 'condition', "
            "choose an operator, and enter a threshold. "
            "Wire plan bodies to 'true ▶' / 'false ▶'. "
            "Continue each branch from 'true out' / 'false out'."
        ),
    ),
    NodeSchema(
        node_id="sequence",
        title="sequence",
        category="flow",
        inputs=[PortSpec("plan 1", "plan"), PortSpec("plan 2", "plan")],
        outputs=[PortSpec("plan", "plan")],
        params={},
        expandable_ports=True,
        desc="Run plans one after another in port order. Use + to add more inputs, − to remove the last one.",
    ),

    # ── Device nodes ─────────────────────────────────────────────────────────
    NodeSchema(
        node_id="motor_device",
        title="Motor",
        category="device",
        inputs=[],
        outputs=[PortSpec("value", "value")],
        params={"motor_0": "", "pos_0": 0.0},
        param_pairs=("motor", "pos"),
        inline_pairs=True,
        param_choices={"motor": SIM_MOTORS},
        desc="Motor + target position. Each row is one motor/position pair. Use + to add more. Wire to mv 'device' ports, or to scan nodes.",
    ),
    NodeSchema(
        node_id="motor_device_rel",
        title="Motor (rel)",
        category="device",
        inputs=[],
        outputs=[PortSpec("value", "value")],
        params={"motor_0": "", "delta_0": 0.0},
        param_pairs=("motor", "delta"),
        inline_pairs=True,
        param_choices={"motor": SIM_MOTORS},
        desc="Motor + relative offset (delta). Each row is one motor/delta pair. Use + to add more. Wire to mvr 'device' ports.",
    ),
    NodeSchema(
        node_id="detector_device",
        title="Detector",
        category="device",
        inputs=[],
        outputs=[PortSpec("value", "value")],
        params={"detector_0": ""},
        param_pairs=("detector",),
        param_choices={"detector": SIM_DETECTORS},
        desc="One or more detectors. Use + / − to add detectors. Wire to trigger_and_read, count, or scan 'device' ports.",
    ),
    NodeSchema(
        node_id="shutter_device",
        title="Shutter",
        category="device",
        inputs=[],
        outputs=[PortSpec("value", "value")],
        params={"shutter_0": "", "pos_0": 0.0},
        param_pairs=("shutter", "pos"),
        inline_pairs=True,
        param_choices={"shutter": SIM_DEVICES},
        desc="Shutter + state (0 = closed, 1 = open). Wire to mv 'device' ports.",
    ),

    # ── Custom ────────────────────────────────────────────────────────────────
    NodeSchema(
        node_id="scan_range",
        title="scan range",
        category="custom",
        inputs=[],
        outputs=[PortSpec("value", "value")],
        params={"start_0": -1.0, "stop_0": 1.0, "num": 11},
        param_pairs=("start", "stop"),
        desc="Position ranges for each motor axis. Add one start/stop row per motor (1:1 with a motors 'devices' node). Wire to the 'positions' port of a scan node.",
    ),
    NodeSchema(
        node_id="loop_var",
        title="loop var",
        category="custom",
        inputs=[],
        outputs=[PortSpec("value", "value")],
        params={},
        hidden=True,
        title_param="var_name",
        desc="Auto-created by zip loop frame. Header shows the variable name set in the frame. Wire its output to any value input port inside the loop.",
    ),
    NodeSchema(
        node_id="devices",
        title="devices",
        category="custom",
        inputs=[],
        outputs=[PortSpec("value", "value")],
        params={"device_0": ""},
        param_pairs=("device",),
        param_choices={"device": SIM_DEVICES},
        desc="One or more device objects. Click a row to pick from available devices. Use + / − to add or remove slots. Emits a bare name (1 device) or a list [d1, d2] (multiple). Wire to any amber value port.",
    ),
    NodeSchema(
        node_id="string_input",
        title="string",
        category="custom",
        inputs=[],
        outputs=[PortSpec("value", "value")],
        params={"value": ""},
        desc="A string literal. Wire its amber output to any value port. The value is emitted as a quoted Python string: 'your text'.",
    ),
    NodeSchema(
        node_id="array_input",
        title="array",
        category="custom",
        inputs=[],
        outputs=[PortSpec("col 1", "value")],
        params={"values_0": ""},
        param_pairs=("values",),
        expand_output_ports=True,
        supports_csv=True,
        desc="One or more column arrays. Each row is one array. Enter comma-separated values or load a no-header CSV — each column becomes one row. Each row gets its own output port.",
    ),
    NodeSchema(
        node_id="custom_call",
        title="custom call",
        category="custom",
        inputs=[PortSpec("in", "plan"), PortSpec("func", "value")],
        outputs=[PortSpec("out", "plan")],
        params={"extra_args": ""},
        expandable_ports=True,
        expand_port_type="value",
        min_ports=2,
        desc="Call a custom plan function. Wire a 'device / var' to 'func' for the function name. Click + to add arg ports and wire arguments. Use extra_args for any remaining literal values.",
    ),

    # ── Output ────────────────────────────────────────────────────────────────
    NodeSchema(
        node_id="plan_output",
        title="Run / Export",
        category="output",
        inputs=[PortSpec("plan", "plan")],
        outputs=[],
        params={},
        desc="Terminal node. Connect your top-level plan here to generate code or submit to the queue server.",
    ),
]

BUILTIN_BY_ID: dict[str, NodeSchema] = {n.node_id: n for n in BUILTIN_NODES}
