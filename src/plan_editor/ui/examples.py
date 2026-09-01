"""Pre-built example canvas graphs.

Each public function takes a NodeScene and a NodeView and populates the canvas
with a ready-to-run example plan.  Call scene._restore({}) first to clear.

Public functions
----------------
energy_scan_simple(scene, view)
    Single zip-loop over energies: mv → sleep → shutter → trigger_and_read.

energy_scan_full(scene, view)
    Nested zip-loops: outer (energy) → mono + undulator moves,
    inner (sample x/y positions) → open_run → trigger → close_run.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt


def _add_node(scene, node_id: str, x: float, y: float, **params):
    from plan_editor.registry.builtin_plans import BUILTIN_BY_ID
    node = scene.add_node(BUILTIN_BY_ID[node_id], QPointF(x, y))
    if params:
        node.params.update(params)
        node._rebuild()
    return node


def _wire(scene, src_port, dst_port):
    from plan_editor.canvas.wire import Wire
    w = Wire(src_port)
    scene.addItem(w)
    w.finalize(dst_port)


def energy_scan_simple(scene, view):
    """Single energy loop: mv(mono) → sleep → mv(shutter,0) → sleep → trigger → mv(shutter,1).

    Graph layout
    ------------
    array_input(energies)
        ↓ list 1
    zip_loop(energy)  ── func 1 ──▶  mv(mono_energy) → sleep(0.5)
        ↓ out                         → mv(shutter,0) → sleep(0.3)
    plan_output                       → trigger_and_read → mv(shutter,1)

    loop_var(energy) ──▶ mv(mono).positions
    """
    arr   = _add_node(scene, "array_input", 60, 460, values_0="8000, 8050, 8100, 8150, 8200")
    frame = scene._add_loop_frame(QPointF(300, 200))
    frame._var_proxies[0].widget().setText("energy")
    frame._on_var_changed(0)

    x0, y0 = 880, 310
    mv_e  = _add_node(scene, "mv",              x0,      y0, motor_0="mono_energy")
    slp1  = _add_node(scene, "sleep",           x0+220,  y0, delay=0.5)
    mv_s0 = _add_node(scene, "mv",              x0+420,  y0, motor_0="shutter", pos_0=0.0)
    slp2  = _add_node(scene, "sleep",           x0+640,  y0, delay=0.3)
    trig  = _add_node(scene, "trigger_and_read",x0+840,  y0, devices="det")
    mv_s1 = _add_node(scene, "mv",              x0+1060, y0, motor_0="shutter", pos_0=1.0)
    out_n = _add_node(scene, "plan_output", 680, 580)

    _wire(scene, arr.output_ports[0],   frame._list_ports[0])
    var_node = frame._var_nodes[0]
    if var_node:
        _wire(scene, var_node.output_ports[0], mv_e.input_ports[1])
    _wire(scene, frame._body_ports[0],  mv_e.input_ports[0])
    _wire(scene, mv_e.output_ports[0],  slp1.input_ports[0])
    _wire(scene, slp1.output_ports[0],  mv_s0.input_ports[0])
    _wire(scene, mv_s0.output_ports[0], slp2.input_ports[0])
    _wire(scene, slp2.output_ports[0],  trig.input_ports[0])
    _wire(scene, trig.output_ports[0],  mv_s1.input_ports[0])
    _wire(scene, frame.output_ports[0], out_n.input_ports[0])

    scene.graph_changed.emit()
    view.fitInView(scene.itemsBoundingRect().adjusted(-40, -40, 40, 40), Qt.KeepAspectRatio)


def energy_scan_full(scene, view):
    """Nested energy + position loops with run boundaries and checkpoint.

    Outer loop: energy → mv(mono) + mv(undulator) + sleep
    Inner loop: (sx, sy) positions → mv(x) → mv(y) → open_run → checkpoint
                                    → mv(shutter,0) → sleep → trigger → mv(shutter,1) → close_run

    Note: undulator uses pos_0='energy' (the variable name as a literal string)
    because one loop_var output cannot wire to two position inputs cleanly.
    Replace with real device objects in production.
    """
    # ── Outer loop: energy ────────────────────────────────────────────────────
    arr_e = _add_node(scene, "array_input", 60, 100,
                      values_0="8000, 8050, 8100, 8150, 8200")
    outer = scene._add_loop_frame(QPointF(300, 60))
    outer._var_proxies[0].widget().setText("energy")
    outer._on_var_changed(0)
    outer._add_body()   # second func port → inner loop

    x1, y1 = 900, 100
    mv_mono = _add_node(scene, "mv",    x1,     y1, motor_0="mono_energy")
    mv_und  = _add_node(scene, "mv",    x1+220, y1, motor_0="undulator", pos_0="energy")
    slp_e   = _add_node(scene, "sleep", x1+440, y1, delay=1.0)

    # ── Inner loop: sample x/y positions ─────────────────────────────────────
    arr_x = _add_node(scene, "array_input", 60, 560, values_0="0.0, 1.0, 2.0")
    arr_y = _add_node(scene, "array_input", 60, 640, values_0="0.0, 0.5, 1.0")
    inner = scene._add_loop_frame(QPointF(300, 480))
    inner._add_list()
    inner._var_proxies[0].widget().setText("sx")
    inner._on_var_changed(0)
    inner._var_proxies[1].widget().setText("sy")
    inner._on_var_changed(1)

    x2, y2 = 900, 520
    mv_x  = _add_node(scene, "mv",               x2,      y2, motor_0="x_motor")
    mv_y  = _add_node(scene, "mv",               x2+200,  y2, motor_0="y_motor")
    orun  = _add_node(scene, "open_run",          x2+400,  y2)
    chkpt = _add_node(scene, "checkpoint",        x2+600,  y2)
    mv_s0 = _add_node(scene, "mv",               x2+780,  y2, motor_0="shutter", pos_0=0.0)
    slp_a = _add_node(scene, "sleep",             x2+980,  y2, delay=0.3)
    trig  = _add_node(scene, "trigger_and_read",  x2+1160, y2, devices="det")
    mv_s1 = _add_node(scene, "mv",               x2+1360, y2, motor_0="shutter", pos_0=1.0)
    crun  = _add_node(scene, "close_run",         x2+1560, y2)
    out_n = _add_node(scene, "plan_output", 680, 340)

    # Outer loop wires
    _wire(scene, arr_e.output_ports[0], outer._list_ports[0])
    e_var = outer._var_nodes[0]
    if e_var:
        _wire(scene, e_var.output_ports[0], mv_mono.input_ports[1])
    _wire(scene, outer._body_ports[0],    mv_mono.input_ports[0])
    _wire(scene, mv_mono.output_ports[0], mv_und.input_ports[0])
    _wire(scene, mv_und.output_ports[0],  slp_e.input_ports[0])
    _wire(scene, outer._body_ports[1],    inner._in_port)
    _wire(scene, outer.output_ports[0],   out_n.input_ports[0])

    # Inner loop wires
    _wire(scene, arr_x.output_ports[0], inner._list_ports[0])
    _wire(scene, arr_y.output_ports[0], inner._list_ports[1])
    sx_var = inner._var_nodes[0]
    sy_var = inner._var_nodes[1]
    if sx_var:
        _wire(scene, sx_var.output_ports[0], mv_x.input_ports[1])
    if sy_var:
        _wire(scene, sy_var.output_ports[0], mv_y.input_ports[1])
    _wire(scene, inner._body_ports[0],  mv_x.input_ports[0])
    _wire(scene, mv_x.output_ports[0],  mv_y.input_ports[0])
    _wire(scene, mv_y.output_ports[0],  orun.input_ports[0])
    _wire(scene, orun.output_ports[0],  chkpt.input_ports[0])
    _wire(scene, chkpt.output_ports[0], mv_s0.input_ports[0])
    _wire(scene, mv_s0.output_ports[0], slp_a.input_ports[0])
    _wire(scene, slp_a.output_ports[0], trig.input_ports[0])
    _wire(scene, trig.output_ports[0],  mv_s1.input_ports[0])
    _wire(scene, mv_s1.output_ports[0], crun.input_ports[0])

    scene.graph_changed.emit()
    view.fitInView(scene.itemsBoundingRect().adjusted(-40, -40, 40, 40), Qt.KeepAspectRatio)
