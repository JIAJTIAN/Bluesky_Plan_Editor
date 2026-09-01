from __future__ import annotations

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QGraphicsView, QInputDialog

from .node import BaseNode
from .wire import Wire

GRID_MINOR = 24
GRID_MAJOR = 120


class NodeView(QGraphicsView):
    request_add_node = Signal(QPointF)   # Shift+A → scene pos at cursor
    request_find     = Signal()          # Ctrl+F

    def __init__(self, scene, parent=None):
        super().__init__(scene, parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor("#0f1117"))
        self.setStyleSheet("border: none;")

        self._cursor_scene_pos = QPointF(0, 0)
        self._clipboard: list[dict] = []   # internal copy buffer

    # ── track cursor ──────────────────────────────────────────────────────────
    def mouseMoveEvent(self, event):
        self._cursor_scene_pos = self.mapToScene(event.pos())
        super().mouseMoveEvent(event)

    # ── zoom ──────────────────────────────────────────────────────────────────
    def wheelEvent(self, event: QWheelEvent):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    # ── pan: middle-button → temporarily become ScrollHandDrag ───────────────
    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            # feed a fake left-press so Qt's built-in scroll-hand drag starts
            fake = QMouseEvent(
                event.type(), event.position(), event.globalPosition(),
                Qt.LeftButton, Qt.LeftButton, event.modifiers(),
            )
            super().mousePressEvent(fake)
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton:
            fake = QMouseEvent(
                event.type(), event.position(), event.globalPosition(),
                Qt.LeftButton, Qt.NoButton, event.modifiers(),
            )
            super().mouseReleaseEvent(fake)
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.setCursor(Qt.ArrowCursor)
            return
        super().mouseReleaseEvent(event)

    # ── keyboard shortcuts ────────────────────────────────────────────────────
    def keyPressEvent(self, event: QKeyEvent):
        # If a text field has focus, let Qt route the key normally — don't
        # intercept letters like X, H, M that are also shortcuts.
        # Check both the app-level focus widget AND the scene's focused item
        # (embedded QLineEdit inside QGraphicsProxyWidget reports focus differently).
        from PySide6.QtWidgets import QApplication, QLineEdit, QGraphicsProxyWidget
        fw = QApplication.focusWidget()
        if isinstance(fw, QLineEdit):
            super().keyPressEvent(event)
            return
        if isinstance(self.scene().focusItem(), QGraphicsProxyWidget):
            super().keyPressEvent(event)
            return

        key  = event.key()
        mod  = event.modifiers()
        scene = self.scene()

        # Shift+A — add node search popup
        if key == Qt.Key_A and mod == Qt.ShiftModifier:
            self.request_add_node.emit(self._cursor_scene_pos)
            return

        # H — collapse/expand selected nodes
        if key == Qt.Key_H and mod == Qt.NoModifier:
            for n in self._selected_nodes():
                n.toggle_collapsed()
            return

        # M — mute/unmute selected nodes
        if key == Qt.Key_M and mod == Qt.NoModifier:
            for n in self._selected_nodes():
                n.toggle_muted()
            return

        # X / Del — delete selected
        if key in (Qt.Key_X, Qt.Key_Delete) and mod == Qt.NoModifier:
            if self._selected_items():
                scene.push_undo()
            self._delete_selected(reconnect=False)
            return

        # Shift+X / Ctrl+Del — delete with reconnect
        if (key == Qt.Key_X and mod == Qt.ShiftModifier) or \
           (key == Qt.Key_Delete and mod == Qt.ControlModifier):
            if self._selected_items():
                scene.push_undo()
            self._delete_selected(reconnect=True)
            return

        # Ctrl+J — frame selected nodes
        if key == Qt.Key_J and mod == Qt.ControlModifier:
            scene.create_frame_around_selected()
            return

        # Ctrl+C — copy selected nodes
        if key == Qt.Key_C and mod == Qt.ControlModifier:
            self._copy_selected()
            return

        # Ctrl+Z — undo
        if key == Qt.Key_Z and mod == Qt.ControlModifier:
            scene.undo()
            return

        # Ctrl+V — paste copied nodes
        if key == Qt.Key_V and mod == Qt.ControlModifier:
            if self._clipboard:
                scene.push_undo()
            self._paste_nodes()
            return

        # Ctrl+F — find node
        if key == Qt.Key_F and mod == Qt.ControlModifier:
            self._find_node()
            return

        # Home — view all
        if key == Qt.Key_Home:
            self.fitInView(scene.itemsBoundingRect().adjusted(-40, -40, 40, 40),
                           Qt.KeepAspectRatio)
            return

        # Numpad . — view selected
        if key == Qt.Key_Period and mod == Qt.NoModifier:
            sel = scene.selectedItems()
            if sel:
                r = sel[0].sceneBoundingRect()
                for i in sel[1:]:
                    r = r.united(i.sceneBoundingRect())
                self.fitInView(r.adjusted(-60, -60, 60, 60), Qt.KeepAspectRatio)
            return

        # Ctrl+A — select all  (QGraphicsScene has no selectAll())
        if key == Qt.Key_A and mod == Qt.ControlModifier:
            for item in scene.items():
                item.setSelected(True)
            return

        super().keyPressEvent(event)

    # ── helpers ───────────────────────────────────────────────────────────────
    def _selected_nodes(self) -> list[BaseNode]:
        """BaseNode items only — use _selected_items() for full selection."""
        return [i for i in self.scene().selectedItems() if isinstance(i, BaseNode)]

    def _selected_items(self):
        """All deletable selected items: BaseNode + LoopFrame."""
        from .loop_frame import LoopFrame
        return [i for i in self.scene().selectedItems()
                if isinstance(i, (BaseNode, LoopFrame))]

    def _delete_selected(self, reconnect: bool):
        from .loop_frame import LoopFrame
        scene = self.scene()
        deleted = False
        for item in self._selected_items():
            if isinstance(item, LoopFrame):
                # clean up frame: remove all port wires, then orphaned var-nodes
                for p in item.input_ports + item.output_ports:
                    for w in list(p.wires):
                        w.remove()
                for vn in item._var_nodes:
                    if vn is not None and vn.scene():
                        for p in vn.input_ports + vn.output_ports:
                            for w in list(p.wires):
                                w.remove()
                        scene.removeItem(vn)
                scene.removeItem(item)
                deleted = True
            else:
                if reconnect:
                    _rewire_around(item, scene)
                for p in item.input_ports + item.output_ports:
                    for w in list(p.wires):
                        w.remove()
                scene.removeItem(item)
                deleted = True
        if deleted:
            scene.graph_changed.emit()

    def _copy_selected(self):
        nodes = self._selected_nodes()
        if not nodes:
            return
        self._clipboard = []
        for n in nodes:
            n_extra = 0
            if n.schema.expandable_ports:
                # count ports added beyond the fixed schema ports + value_inputs
                n_fixed = len(n.schema.inputs) + len(n.schema.value_inputs)
                n_extra = max(0, len(n.input_ports) - n_fixed)
            self._clipboard.append({
                "node_id":  n.schema.node_id,
                "params":   dict(n.params),
                "num_pairs": n._num_pairs,
                "n_extra":  n_extra,
                "pos":      n.pos(),
            })

    def _paste_nodes(self):
        if not self._clipboard:
            return
        from plan_editor.canvas.node import BaseNode
        from plan_editor.registry.builtin_plans import BUILTIN_BY_ID
        scene = self.scene()
        scene.clearSelection()
        OFFSET = QPointF(30, 30)
        pasted = []
        for entry in self._clipboard:
            schema = BUILTIN_BY_ID.get(entry["node_id"])
            if schema is None:
                continue
            # Construct directly — avoids the push_undo() inside scene.add_node()
            node = BaseNode(schema, entry["pos"] + OFFSET)
            node.params.update(entry["params"])
            if schema.param_pairs and entry["num_pairs"] > node._num_pairs:
                for _ in range(entry["num_pairs"] - node._num_pairs):
                    node._add_pair()
            for _ in range(entry["n_extra"]):
                node._add_port()
            node._rebuild()
            scene.addItem(node)
            node.setSelected(True)
            pasted.append(node)
        if pasted:
            scene.graph_changed.emit()
        # next paste will stack another 30px further
        for entry in self._clipboard:
            entry["pos"] = entry["pos"] + OFFSET

    def _find_node(self):
        scene = self.scene()
        nodes = [i for i in scene.items() if isinstance(i, BaseNode)]
        names = [n.schema.title for n in nodes]
        if not names:
            return
        title, ok = QInputDialog.getItem(self, "Find Node", "Title:", sorted(set(names)),
                                         editable=True)
        if not ok:
            return
        matches = [n for n in nodes if title.lower() in n.schema.title.lower()]
        if matches:
            scene.clearSelection()
            for n in matches:
                n.setSelected(True)
            r = matches[0].sceneBoundingRect()
            self.fitInView(r.adjusted(-80, -80, 80, 80), Qt.KeepAspectRatio)

    # ── grid background ───────────────────────────────────────────────────────
    def drawBackground(self, painter: QPainter, rect):
        super().drawBackground(painter, rect)
        left = int(rect.left()) - (int(rect.left()) % GRID_MINOR)
        top  = int(rect.top())  - (int(rect.top())  % GRID_MINOR)
        minor_pen = QPen(QColor("#1a2030"), 0)
        major_pen = QPen(QColor("#1e2d40"), 0)
        x = left
        while x < rect.right():
            painter.setPen(major_pen if x % GRID_MAJOR == 0 else minor_pen)
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
            x += GRID_MINOR
        y = top
        while y < rect.bottom():
            painter.setPen(major_pen if y % GRID_MAJOR == 0 else minor_pen)
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)
            y += GRID_MINOR


def _rewire_around(node: BaseNode, scene):
    """Connect upstream output → downstream input, bypassing node."""
    from .wire import Wire
    ups  = [w.src for p in node.input_ports  for w in p.wires]
    dns  = [w.dst for p in node.output_ports for w in p.wires]
    for src in ups:
        for dst in dns:
            if dst and src and dst.node is not src.node:
                w = Wire(src)
                scene.addItem(w)
                w.finalize(dst)
