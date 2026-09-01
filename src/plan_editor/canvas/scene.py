from __future__ import annotations

from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainterPath, QPainterPathStroker, QPen
from PySide6.QtWidgets import QGraphicsLineItem, QGraphicsScene

from .frame import FrameNode
from .loop_frame import LoopFrame
from .node import BaseNode, NodeSchema
from .port import Port, PortKind
from .wire import Wire

PORT_HIT = 14   # px radius for port click tolerance


def _find_port(scene: QGraphicsScene, pos: QPointF, kind: PortKind,
               port_type: str | None = None) -> Port | None:
    """Return the nearest port of the given kind (and optional type) within PORT_HIT px."""
    for item in scene.items(QRectF(pos.x() - PORT_HIT, pos.y() - PORT_HIT,
                                   PORT_HIT * 2, PORT_HIT * 2)):
        if isinstance(item, Port) and item.kind == kind:
            if port_type is None or item.port_type == port_type:
                return item
    return None


def _wire_hits_line(wire: Wire, line: QLineF) -> bool:
    """True if the wire's Bezier path crosses the cut line segment."""
    cut = QPainterPath()
    cut.moveTo(line.p1())
    cut.lineTo(line.p2())
    stroker = QPainterPathStroker()
    stroker.setWidth(10)
    fat = stroker.createStroke(cut)
    return fat.intersects(wire.path())


_UNDO_LIMIT = 50   # max snapshots kept


class NodeScene(QGraphicsScene):
    wire_connected         = Signal(Port, Port)
    selection_changed_node = Signal(object)   # BaseNode | None
    graph_changed          = Signal()          # wires added/removed, nodes added

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackgroundBrush(QColor("#0f1117"))

        self._drag_wire: Wire | None = None
        self._drag_src:  Port | None = None

        self._cut_line:  QGraphicsLineItem | None = None
        self._cut_start: QPointF | None = None

        self._undo_stack: list[dict] = []

        self.selectionChanged.connect(self._on_selection_changed)

    # ── node factory ──────────────────────────────────────────────────────────
    def add_node(self, schema: NodeSchema, pos: QPointF = QPointF(0, 0)):
        self.push_undo()
        if schema.node_id == "zip_loop":
            return self._add_loop_frame(pos)
        node = BaseNode(schema, pos)
        self.addItem(node)
        self.graph_changed.emit()
        return node

    def _add_loop_frame(self, pos: QPointF = QPointF(0, 0)) -> LoopFrame:
        frame = LoopFrame(pos)
        self.addItem(frame)
        frame.init_after_add()   # creates first list port + LoopVarNode in scene
        self.graph_changed.emit()
        return frame

    # ── mouse press ───────────────────────────────────────────────────────────
    def mousePressEvent(self, event):
        pos = event.scenePos()

        if event.button() == Qt.LeftButton:
            # drag from occupied INPUT → detach wire and re-drag from its source
            inp = _find_port(self, pos, PortKind.INPUT)
            if inp and inp.wires:
                wire = inp.wires[0]
                src  = wire.src
                wire.remove()
                self._begin_wire(src, src.scene_pos())
                event.accept()
                return
            # drag from OUTPUT → start new wire
            port = _find_port(self, pos, PortKind.OUTPUT)
            if port:
                self._begin_wire(port, pos)
                event.accept()
                return

        elif event.button() == Qt.RightButton:
            # right-click on a wire → delete immediately
            for item in self.items(pos):
                if isinstance(item, Wire):
                    self.push_undo()
                    item.remove()
                    self.graph_changed.emit()
                    event.accept()
                    return
            # right-click on empty canvas → start scissor
            hit = next((i for i in self.items(pos)
                        if isinstance(i, (BaseNode, Port))), None)
            if hit is None:
                self._begin_cut(pos)
                event.accept()
                return

        super().mousePressEvent(event)

    # ── mouse move ────────────────────────────────────────────────────────────
    def mouseMoveEvent(self, event):
        pos = event.scenePos()

        if self._drag_wire is not None:
            dst = _find_port(self, pos, PortKind.INPUT, self._drag_src.port_type)
            snap = (dst.scene_pos()
                    if dst and dst.node is not self._drag_src.node
                    else pos)
            self._drag_wire.set_drag_pos(snap)
            event.accept()
            return

        if self._cut_line is not None:
            self._cut_line.setLine(QLineF(self._cut_start, pos))
            self._update_cut_preview()
            event.accept()
            return

        super().mouseMoveEvent(event)

    # ── mouse release ─────────────────────────────────────────────────────────
    def mouseReleaseEvent(self, event):
        pos = event.scenePos()

        if self._drag_wire is not None and event.button() == Qt.LeftButton:
            dst = _find_port(self, pos, PortKind.INPUT, self._drag_src.port_type)
            if (dst is not None
                    and dst.node is not self._drag_src.node):
                self.push_undo()
                self._drag_wire.finalize(dst)
                self.wire_connected.emit(self._drag_src, dst)
                self.graph_changed.emit()
            else:
                self.removeItem(self._drag_wire)
            self._drag_wire = None
            self._drag_src  = None
            event.accept()
            return

        if self._cut_line is not None and event.button() == Qt.RightButton:
            self._apply_cut()
            event.accept()
            return

        super().mouseReleaseEvent(event)

    # ── wire drag ─────────────────────────────────────────────────────────────
    def _begin_wire(self, src: Port, pos: QPointF):
        self._drag_src  = src
        self._drag_wire = Wire(src)
        self._drag_wire.set_drag_pos(pos)
        self.addItem(self._drag_wire)

    # ── scissor cut ───────────────────────────────────────────────────────────
    _CUT_PEN = QPen(QColor("#ef4444"), 1.5, Qt.DashLine)

    def _begin_cut(self, pos: QPointF):
        self._cut_start = pos
        self._cut_line  = QGraphicsLineItem(QLineF(pos, pos))
        self._cut_line.setPen(self._CUT_PEN)
        self._cut_line.setZValue(99)
        self.addItem(self._cut_line)

    def _update_cut_preview(self):
        line = self._cut_line.line()
        for item in self.items():
            if isinstance(item, Wire):
                item.setOpacity(0.25 if _wire_hits_line(item, line) else 0.85)

    def _apply_cut(self):
        line = self._cut_line.line()
        victims = [w for w in self.items() if isinstance(w, Wire)
                   and _wire_hits_line(w, line)]
        if victims:
            self.push_undo()
        for w in victims:
            w.remove()
        self.removeItem(self._cut_line)
        self._cut_line  = None
        self._cut_start = None
        for item in self.items():
            if isinstance(item, Wire):
                item.setOpacity(0.85)
        if victims:
            self.graph_changed.emit()

    # ── undo ──────────────────────────────────────────────────────────────────
    def push_undo(self):
        """Snapshot the current graph state onto the undo stack."""
        snap = self._snapshot()
        self._undo_stack.append(snap)
        if len(self._undo_stack) > _UNDO_LIMIT:
            self._undo_stack.pop(0)

    def undo(self):
        """Restore the previous graph state."""
        if not self._undo_stack:
            return
        snap = self._undo_stack.pop()
        self._restore(snap)

    # ── serialisation helpers ─────────────────────────────────────────────────
    def _snapshot(self) -> dict:
        # Assign sequential IDs to all serialisable items
        item_to_sid: dict[int, int] = {}
        sid = 0
        for item in self.items():
            if isinstance(item, (BaseNode, LoopFrame)):
                item_to_sid[id(item)] = sid
                sid += 1

        # IDs of var-nodes owned by frames (serialised inside the frame)
        frame_var_ids: set[int] = set()
        for item in self.items():
            if isinstance(item, LoopFrame):
                frame_var_ids.update(id(vn) for vn in item._var_nodes if vn is not None)

        nodes: dict = {}
        for item in self.items():
            if not isinstance(item, BaseNode) or id(item) in frame_var_ids:
                continue
            s = item_to_sid[id(item)]
            n_fixed = len(item.schema.inputs) + len(item.schema.value_inputs)
            n_extra = max(0, len(item.input_ports) - n_fixed) if item.schema.expandable_ports else 0
            nodes[s] = {
                "schema_id": item.schema.node_id,
                "pos":       [item.pos().x(), item.pos().y()],
                "params":    dict(item.params),
                "num_pairs": item._num_pairs,
                "n_extra":   n_extra,
            }

        frames: dict = {}
        for item in self.items():
            if not isinstance(item, LoopFrame):
                continue
            s = item_to_sid[id(item)]
            # Capture wires from each var_node output to non-var destinations
            var_wires = []
            for vi, vn in enumerate(item._var_nodes):
                if vn is None:
                    continue
                for vp in vn.output_ports:
                    for wo in vp.wires:
                        dn = wo.dst.node
                        if id(dn) in frame_var_ids:
                            continue
                        dst_sid = item_to_sid.get(id(dn))
                        if dst_sid is None:
                            continue
                        try:
                            dst_port_idx = dn.input_ports.index(wo.dst)
                            var_wires.append({
                                "var_idx":  vi,
                                "dst_id":   dst_sid,
                                "dst_port": dst_port_idx,
                            })
                        except ValueError:
                            pass
            frames[s] = {
                "pos":       [item.pos().x(), item.pos().y()],
                "n_lists":   len(item._list_ports),
                "n_bodies":  len(item._body_ports),
                "var_names": [item.var_name(i) for i in range(len(item._list_ports))],
                "var_wires": var_wires,
            }

        wires = []
        for item in self.items():
            if not isinstance(item, Wire):
                continue
            try:
                sn, dn = item.src.node, item.dst.node
                if sn is None or dn is None:
                    continue
                # skip wires that touch frame-owned var nodes
                if id(sn) in frame_var_ids or id(dn) in frame_var_ids:
                    continue
                src_sid = item_to_sid.get(id(sn))
                dst_sid = item_to_sid.get(id(dn))
                if src_sid is None or dst_sid is None:
                    continue
                wires.append({
                    "src_id":   src_sid,
                    "src_port": sn.output_ports.index(item.src),
                    "dst_id":   dst_sid,
                    "dst_port": dn.input_ports.index(item.dst),
                })
            except (ValueError, AttributeError):
                pass

        return {"nodes": nodes, "frames": frames, "wires": wires}

    def _restore(self, snap: dict):
        from plan_editor.registry.builtin_plans import BUILTIN_BY_ID

        # ── clear ──────────────────────────────────────────────────────────────
        for item in list(self.items()):
            if isinstance(item, Wire):
                item.src.wires.clear()
                if item.dst:
                    item.dst.wires.clear()
                self.removeItem(item)
        for item in list(self.items()):
            if isinstance(item, LoopFrame):
                for vn in item._var_nodes:
                    if vn is not None and vn.scene():
                        self.removeItem(vn)
                self.removeItem(item)
        for item in list(self.items()):
            if isinstance(item, BaseNode):
                self.removeItem(item)

        sid_to_new: dict[int, object] = {}   # serial-id → BaseNode | LoopFrame

        # ── recreate frames ────────────────────────────────────────────────────
        for s, fd in snap.get("frames", {}).items():
            frame = LoopFrame(QPointF(*fd["pos"]))
            self.addItem(frame)
            frame.init_after_add()                          # 1 list + 1 body
            while len(frame._list_ports)  < fd["n_lists"]:
                frame._add_list()
            while len(frame._body_ports) < fd["n_bodies"]:
                frame._add_body()
            for i, name in enumerate(fd.get("var_names", [])):
                if i < len(frame._var_proxies):
                    frame._var_proxies[i].widget().setText(name)
                    frame._on_var_changed(i)
            sid_to_new[int(s)] = frame

        # ── recreate standalone nodes ──────────────────────────────────────────
        for s, nd in snap.get("nodes", {}).items():
            schema = BUILTIN_BY_ID.get(nd["schema_id"])
            if schema is None:
                continue
            node = BaseNode(schema, QPointF(*nd["pos"]))
            node.params.update(nd["params"])
            if schema.param_pairs:
                while node._num_pairs < nd["num_pairs"]:
                    node._add_pair()
                while node._num_pairs > nd["num_pairs"] and node._num_pairs > 1:
                    node._remove_pair()
            if schema.expandable_ports:
                for _ in range(nd["n_extra"]):
                    node._add_port()
            node._rebuild()
            self.addItem(node)
            sid_to_new[int(s)] = node

        # ── recreate wires ─────────────────────────────────────────────────────
        for wd in snap.get("wires", []):
            sn = sid_to_new.get(wd["src_id"])
            dn = sid_to_new.get(wd["dst_id"])
            if sn is None or dn is None:
                continue
            si, di = wd["src_port"], wd["dst_port"]
            if si < len(sn.output_ports) and di < len(dn.input_ports):
                w = Wire(sn.output_ports[si])
                self.addItem(w)
                w.finalize(dn.input_ports[di])

        # ── recreate var-node wires (loop_var → downstream value ports) ────────
        for s, fd in snap.get("frames", {}).items():
            frame = sid_to_new.get(int(s))
            if not isinstance(frame, LoopFrame):
                continue
            for vw in fd.get("var_wires", []):
                vi  = vw["var_idx"]
                dn  = sid_to_new.get(vw["dst_id"])
                if dn is None or vi >= len(frame._var_nodes):
                    continue
                vn = frame._var_nodes[vi]
                if vn is None or not vn.output_ports:
                    continue
                di = vw["dst_port"]
                if di < len(dn.input_ports):
                    w = Wire(vn.output_ports[0])
                    self.addItem(w)
                    w.finalize(dn.input_ports[di])

        self.graph_changed.emit()

    # ── file save / load ───────────────────────────────────────────────────────
    def save_to_file(self, path: str):
        import json
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._snapshot(), f, indent=2)

    def load_from_file(self, path: str):
        import json
        with open(path, encoding="utf-8") as f:
            snap = json.load(f)
        # JSON keys are strings — convert node/frame dicts to int-keyed
        if "nodes" in snap:
            snap["nodes"] = {int(k): v for k, v in snap["nodes"].items()}
        if "frames" in snap:
            snap["frames"] = {int(k): v for k, v in snap["frames"].items()}
        self._restore(snap)

    # ── frame ─────────────────────────────────────────────────────────────────
    def create_frame_around_selected(self):
        nodes = [i for i in self.selectedItems() if isinstance(i, BaseNode)]
        if not nodes:
            return
        frame = FrameNode(QRectF(), f"Frame {len([i for i in self.items() if isinstance(i, FrameNode)]) + 1}")
        self.addItem(frame)
        frame.resize_to_nodes(nodes)

    # ── selection ─────────────────────────────────────────────────────────────
    def _on_selection_changed(self):
        nodes = [i for i in self.selectedItems() if isinstance(i, BaseNode)]
        self.selection_changed_node.emit(nodes[0] if nodes else None)
